"""
Daily report over the collector runs.

Answers two questions: did anything break today, and what did we actually
collect. Reads exactly two things:

  * logs/runs.jsonl   - one JSON record per run_start / run_end / run_summary
  * the collector CSVs - grouped by the date_recorded column

The raw .log files are never parsed; they are for humans, and the report just
prints their paths.

Usage:
    python daily_report.py                    # today
    python daily_report.py --date 2026-08-19
"""

import os
import io
import csv
import sys
import json
import glob
import argparse
from datetime import datetime, timedelta, date
from collections import defaultdict, OrderedDict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import paths
import run_log

LOG_ROOT = run_log.LOG_ROOT
RUNS_FILE = run_log.RUNS_FILE
DAILY_DIR = os.path.join(LOG_ROOT, "daily")

LOG_RETENTION_DAYS = 30

# This report runs under the same wrapper as the collectors, so its own
# run_end record does not exist yet while it is generating output. Exclude it
# from the health checks - it would otherwise always report itself crashed.
SELF_SCRIPT = "run_daily_report"

# Which wrapper scripts we expect to see run, and the minimum number of runs
# per day before the report complains. Set enabled=False for anything not yet
# registered in Task Scheduler, otherwise "0 runs today" fires every day.
EXPECTED_SCRIPTS = OrderedDict([
    ("run_newgrad_collector", {"enabled": True, "min_runs": 1}),
    ("run_ats_collector",     {"enabled": True, "min_runs": 1}),
    ("run_ddg_collector",     {"enabled": True, "min_runs": 1}),
])

# CSV -> label. All three share the unique_id space (ddg discovers ATS boards,
# so its rows genuinely overlap ats_jobs.csv), hence the global dedup below.
SOURCES = OrderedDict([
    ("newgrad_classifications.csv", "newgrad (LinkedIn)"),
    ("ats_jobs.csv",                "ats_direct"),
    ("ddg_jobs.csv",                "ddg_search"),
])

# Only ats_direct actually classifies sponsorship from a job description;
# ddg_search hardcodes "Not (Maybe Not) Sponsor" because a SERP has no
# description, and the LinkedIn path rarely finds a positive signal. Showing
# that value for the other sources would read as "does not sponsor" when it
# really means "unknown".
SPONSORSHIP_MEANINGFUL_SOURCES = {"ats_direct"}

BIG_TECH_MARKER = "Big Tech"

# Thresholds above which a collector's own counters are worth flagging.
ATS_HTTP_ERROR_THRESHOLD = 20
ATS_RATE_LIMIT_THRESHOLD = 1

# Only the LinkedIn path calls an LLM (company-type classification); the ATS
# and DDG collectors never do. At gpt-3.5-turbo rates a full day runs a few
# cents, so anything approaching a dollar means the call volume changed and
# is worth looking at before it becomes a habit.
LLM_DAILY_COST_ALERT_USD = 0.50


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_runs():
    """Parse logs/runs.jsonl, tolerating a torn trailing line."""
    records, bad_lines = [], 0
    if not os.path.exists(RUNS_FILE):
        return records, bad_lines
    with open(RUNS_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                bad_lines += 1
    return records, bad_lines


def day_of(value):
    """First 10 chars of a timestamp, only if they look like YYYY-MM-DD."""
    text = (value or "").strip()
    if len(text) >= 10:
        head = text[:10]
        try:
            datetime.strptime(head, "%Y-%m-%d")
            return head
        except ValueError:
            pass
    return None


def load_jobs(day):
    """
    Rows recorded on `day`, per source file, plus bookkeeping.

    Returns (rows_by_source, unparseable_by_source). Rows keep their source
    label so the dedup step can report which file a duplicate came from.
    """
    rows_by_source, unparseable = OrderedDict(), {}
    for filename, label in SOURCES.items():
        path = os.path.join(paths.DATA_DIR, filename)
        rows, bad = [], 0
        if os.path.exists(path):
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    recorded = day_of(row.get("date_recorded"))
                    if recorded is None:
                        bad += 1
                        continue
                    if recorded == day:
                        row["_source"] = label
                        rows.append(row)
        rows_by_source[label] = rows
        unparseable[label] = bad
    return rows_by_source, unparseable


def dedup(rows_by_source):
    """
    Collapse rows sharing a unique_id across files.

    ats_direct and ddg_search both key on generate_job_id(url) and ddg's whole
    job is finding ATS boards, so their outputs really do overlap - counting
    the raw per-file totals would inflate the daily number and make the
    self-check alert fire every single day.
    """
    seen, unique, duplicates = {}, [], 0
    for rows in rows_by_source.values():
        for row in rows:
            uid = row.get("unique_id")
            if uid and uid in seen:
                duplicates += 1
                continue
            if uid:
                seen[uid] = row
            unique.append(row)
    return unique, duplicates


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def group_runs(records, day):
    """
    Group records into one entry per run_id, keeping only runs on `day`.

    A run is dated by its run_start (the wrapper's timestamp). run_summary
    records emitted by a manual `python ats_direct.py` have no matching
    wrapper pair and are grouped under their own manual-* id.
    """
    runs = defaultdict(lambda: {"start": None, "end": None, "summaries": [],
                                "script": None, "log": None})
    for rec in records:
        run_id = rec.get("run_id")
        if not run_id:
            continue
        entry = runs[run_id]
        kind = rec.get("kind")
        if kind == "run_start":
            entry["start"] = rec
            entry["script"] = rec.get("script")
            entry["log"] = rec.get("log")
        elif kind == "run_end":
            entry["end"] = rec
            entry["script"] = entry["script"] or rec.get("script")
        elif kind == "run_summary":
            entry["summaries"].append(rec)
            entry["script"] = entry["script"] or rec.get("script")

    todays = {}
    for run_id, entry in runs.items():
        # run_id from the wrapper is "YYYY-MM-DD_HH-MM-SS"; manual ids are
        # "manual-YYYY-MM-DD_HH-MM-SS". Fall back to a summary timestamp.
        stamp = run_id[len("manual-"):] if run_id.startswith("manual-") else run_id
        run_day = day_of(stamp.replace("_", " "))
        if run_day is None and entry["summaries"]:
            run_day = day_of(entry["summaries"][0].get("ts"))
        if run_day == day:
            entry["run_id"] = run_id
            entry["day"] = run_day
            todays[run_id] = entry
    return todays


def run_status(entry):
    """-> (status, exit_code) where status is ok / failed / crashed / unknown."""
    end = entry.get("end")
    summaries = entry.get("summaries") or []
    if end is not None:
        code = end.get("exit_code", 0)
        return ("ok" if code == 0 else "failed"), code
    if entry.get("start") is not None:
        # Started under the wrapper but never reached the run_end line.
        return "crashed", None
    # No wrapper at all - a manual invocation. Trust the summary's own code.
    codes = [s.get("exit_code", 0) for s in summaries]
    if codes and any(c != 0 for c in codes):
        return "failed", max(codes)
    return ("ok", 0) if summaries else ("unknown", None)


def tracked_summaries(runs_today):
    """
    Run summaries that actually wrote to one of the CSVs this report counts.

    Smoke tests and one-off runs pointed at a scratch --output must not feed
    the new-jobs self-check, or it reports a mismatch against rows they never
    produced.
    """
    tracked = []
    for entry in runs_today.values():
        for summary in entry["summaries"]:
            output = os.path.basename((summary.get("output") or "").replace("\\", "/"))
            if output in SOURCES:
                tracked.append(summary)
    return tracked


def sum_metric(summaries, *names):
    total = 0
    for s in summaries:
        for name in names:
            value = s.get(name)
            if isinstance(value, (int, float)):
                total += value
    return total


def llm_usage(summaries):
    """
    Aggregate LLM spend across run summaries.

    `unpriced` counts runs that called the API under a model with no entry in
    LLMCostTracker.MODEL_PRICING - those contribute tokens and calls but no
    dollar figure, and the report says so rather than quietly under-reporting.
    """
    usage = {"cost_usd": 0.0, "calls": 0, "tokens": 0, "unpriced": 0,
             "runs": 0, "models": set()}
    for s in summaries:
        calls = s.get("llm_api_calls")
        cost = s.get("llm_cost_usd")
        if calls is None and cost is None:
            continue  # a run that never touched the LLM
        # Counted separately from `calls`: records written before llm_api_calls
        # was added carry a cost but no call count, and gating the report on
        # `calls` alone would hide their spend entirely.
        usage["runs"] += 1
        usage["calls"] += calls or 0
        usage["tokens"] += s.get("llm_tokens") or 0
        if s.get("llm_model"):
            usage["models"].add(s["llm_model"])
        if isinstance(cost, (int, float)):
            usage["cost_usd"] += cost
        else:
            usage["unpriced"] += 1
    return usage


def collect_llm_usage(records, day):
    """LLM spend for one day, taken straight from that day's run summaries."""
    summaries = [e for entry in group_runs(records, day).values()
                 for e in entry["summaries"]]
    return llm_usage(summaries)


def build_alerts(runs_today, jobs_today, duplicates, unparseable, bad_lines, day,
                 llm=None):
    alerts = []

    if llm:
        if llm["cost_usd"] >= LLM_DAILY_COST_ALERT_USD:
            alerts.append(
                f"**LLM spend ${llm['cost_usd']:.4f}** today across {llm['calls']} call(s), "
                f"over the ${LLM_DAILY_COST_ALERT_USD:.2f} threshold. Check whether the "
                f"call volume or the model changed."
            )
        if llm["unpriced"]:
            models = ", ".join(sorted(llm["models"])) or "unknown"
            alerts.append(
                f"**{llm['unpriced']} run(s) used an unpriced model** ({models}). "
                f"Their tokens are counted but their cost is not - add the model to "
                f"`LLMCostTracker.MODEL_PRICING`, otherwise today's total understates spend."
            )

    by_script = defaultdict(list)
    for entry in runs_today.values():
        by_script[entry.get("script") or "?"].append(entry)

    for script, config in EXPECTED_SCRIPTS.items():
        if not config["enabled"]:
            continue
        count = len(by_script.get(script, []))
        if count < config["min_runs"]:
            alerts.append(
                f"**{script}** ran {count} time(s), expected at least "
                f"{config['min_runs']} - check Task Scheduler."
            )

    for entry in runs_today.values():
        status, code = run_status(entry)
        script = entry.get("script") or "?"
        if script == SELF_SCRIPT:
            continue
        if status == "failed":
            alerts.append(f"**{script}** run `{entry['run_id']}` exited with code {code}. "
                          f"Log: `{entry.get('log') or 'n/a'}`")
        elif status == "crashed":
            alerts.append(f"**{script}** run `{entry['run_id']}` started but never finished "
                          f"(killed or crashed). Log: `{entry.get('log') or 'n/a'}`")
        for summary in entry["summaries"]:
            if summary.get("error"):
                alerts.append(
                    f"**{summary.get('script')}** raised `{summary['error']}`: "
                    f"{summary.get('error_message', '')}"
                )

    if not jobs_today:
        alerts.append("**No new jobs recorded all day.** Either every posting was a "
                      "duplicate, or collection is silently failing.")

    # Collector counters that signal a degraded (but exit-code-0) run.
    for entry in runs_today.values():
        if entry.get("script") == SELF_SCRIPT:
            continue
        for summary in entry["summaries"]:
            http_errors = summary.get("http_errors") or 0
            rate_limits = summary.get("rate_limit_hits") or 0
            challenges = summary.get("challenges") or 0
            if http_errors >= ATS_HTTP_ERROR_THRESHOLD:
                alerts.append(f"**ats_direct** hit {http_errors} HTTP errors "
                              f"(threshold {ATS_HTTP_ERROR_THRESHOLD}). Log: `{entry.get('log') or 'n/a'}`")
            if rate_limits >= ATS_RATE_LIMIT_THRESHOLD:
                alerts.append(f"**ats_direct** was rate-limited {rate_limits} time(s).")
            if challenges:
                alerts.append(f"**ddg_search** saw {challenges} rate-limit challenge(s) - "
                              f"consider running it less often.")

    # Self-check: what the collectors said they wrote vs what is on disk.
    tracked = tracked_summaries(runs_today)
    reported = sum_metric(tracked, "new_jobs", "jobs_new")
    if tracked and reported != len(jobs_today):
        alerts.append(
            f"**Count mismatch:** runs.jsonl reports {reported} new job(s) but the CSVs "
            f"hold {len(jobs_today)} row(s) dated {day} (after removing {duplicates} "
            f"cross-source duplicate(s)). Possible causes: a run crossing midnight, a "
            f"failed write, or a CSV edited outside the pipeline."
        )

    total_unparseable = sum(unparseable.values())
    if total_unparseable:
        detail = ", ".join(f"{label}: {n}" for label, n in unparseable.items() if n)
        alerts.append(f"{total_unparseable} CSV row(s) have an unreadable `date_recorded` "
                      f"and were excluded ({detail}).")

    if bad_lines:
        alerts.append(f"{bad_lines} unparseable line(s) in runs.jsonl (likely a torn "
                      f"concurrent write).")

    # Cross-midnight runs: date_recorded is stamped once at collect() start, so
    # a long ATS run begun at 23:5x files its jobs under the previous day.
    for entry in runs_today.values():
        for summary in entry["summaries"]:
            summary_day = day_of(summary.get("ts"))
            if summary_day and summary_day != entry["day"]:
                alerts.append(
                    f"Note: **{summary.get('script')}** run `{entry['run_id']}` started "
                    f"{entry['day']} but finished {summary_day}; its jobs are filed under "
                    f"the start date."
                )
    return alerts


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def is_big_tech(row):
    return BIG_TECH_MARKER in (row.get("company_type") or "")


def format_llm(llm, yesterday_llm=None):
    """One line summarising LLM spend, or None when nothing called the API."""
    if not llm or not llm["runs"]:
        return None
    cost = f"${llm['cost_usd']:.4f}"
    if llm["unpriced"]:
        cost += f" + {llm['unpriced']} unpriced run(s)"
    parts = [f"**LLM spend: {cost}**"]
    if llm["calls"]:
        parts.append(f"{llm['calls']} call(s)")
    if llm["tokens"]:
        parts.append(f"{llm['tokens']:,} tokens")
    parts.append(f"over {llm['runs']} run(s)")
    if llm["models"]:
        parts.append(", ".join(sorted(llm["models"])))
    line = parts[0] + " — " + " · ".join(parts[1:])
    if yesterday_llm and yesterday_llm["runs"]:
        line += f" (yesterday ${yesterday_llm['cost_usd']:.4f})"
    return line


def render_todo(rows, day, yesterday_count, duplicates, rows_by_source,
                llm=None, yesterday_llm=None):
    """Section 1: what to apply to today."""
    lines = []
    delta = len(rows) - yesterday_count
    sign = "+" if delta >= 0 else ""
    lines.append(f"**New today: {len(rows)}** (yesterday {yesterday_count}, {sign}{delta})")

    per_source = ", ".join(f"{label} {len(r)}" for label, r in rows_by_source.items())
    lines.append(f"By source: {per_source}"
                 + (f" — {duplicates} cross-source duplicate(s) removed" if duplicates else ""))

    llm_line = format_llm(llm, yesterday_llm)
    if llm_line:
        lines.append("")
        lines.append(llm_line)
    lines.append("")

    unapplied = [r for r in rows if not (r.get("applied") or "").strip()]
    already = len(rows) - len(unapplied)
    if already:
        lines.append(f"_{already} of today's postings are already marked applied._")
        lines.append("")

    if not unapplied:
        lines.append("Nothing new to apply to.")
        return lines

    # Big tech / unicorn / public first - that ordering is the whole point of
    # the company_type classifier.
    groups = defaultdict(list)
    for row in unapplied:
        groups[row.get("company_name") or "(unknown)"].append(row)

    def sort_key(item):
        company, jobs = item
        return (0 if any(is_big_tech(j) for j in jobs) else 1, -len(jobs), company.lower())

    for company, jobs in sorted(groups.items(), key=sort_key):
        tag = " 🏆" if any(is_big_tech(j) for j in jobs) else ""
        lines.append(f"### {company}{tag} — {len(jobs)}")
        for job in jobs:
            title = (job.get("job_title") or "(no title)").strip()
            link = (job.get("job_link") or "").strip()
            bits = [job.get("_source", "")]
            location = (job.get("location") or "").strip()
            if location:
                bits.append(location)
            # Sponsorship is only a real classification on the ATS path.
            if job.get("_source") in SPONSORSHIP_MEANINGFUL_SOURCES:
                bits.append(job.get("sponsorship_status") or "")
            meta = " · ".join(b for b in bits if b)
            lines.append(f"- [{title}]({link})  \n  <sub>{meta}</sub>" if link
                         else f"- {title}  \n  <sub>{meta}</sub>")
        lines.append("")

    lines.append("_Sponsorship status is only classified on the ats_direct path; the other "
                 "sources report `Not (Maybe Not) Sponsor` for everything because they never "
                 "see a job description — read it as unknown, not as a no._")
    return lines


def render_runs(runs_today):
    """Section 3: one line per run."""
    lines = []
    if not runs_today:
        lines.append("No runs recorded.")
        return lines

    for run_id, entry in sorted(runs_today.items()):
        status, code = run_status(entry)
        script = entry.get("script") or "?"
        if script == SELF_SCRIPT and status == "crashed":
            status = "running"  # this very report; its run_end comes later
        badge = {"ok": "ok", "failed": f"FAILED (exit {code})",
                 "crashed": "CRASHED (no run_end)", "unknown": "unknown",
                 "running": "running"}[status]
        summaries = entry["summaries"]

        elapsed = sum_metric(summaries, "elapsed_s")
        new_jobs = sum_metric(summaries, "new_jobs", "jobs_new")
        detail_bits = []
        fetched = sum_metric(summaries, "jobs_fetched")
        matched = sum_metric(summaries, "jobs_matched")
        collected = sum_metric(summaries, "collected")
        if fetched:
            detail_bits.append(f"fetched {fetched} → matched {matched}")
        if collected:
            detail_bits.append(f"collected {collected}")
        queries_ok = sum_metric(summaries, "queries_ok")
        if queries_ok:
            detail_bits.append(f"{queries_ok} queries ok")
        detail_bits.append(f"new {new_jobs}")

        usage = llm_usage(summaries)
        if usage["runs"]:
            bit = f"LLM ${usage['cost_usd']:.4f}"
            if usage["calls"]:
                bit += f" / {usage['calls']} call(s)"
            if usage["unpriced"]:
                bit += " (partly unpriced)"
            detail_bits.append(bit)

        problems = []
        for name, label in (("http_errors", "http errors"),
                            ("rate_limit_hits", "rate limits"),
                            ("challenges", "challenges")):
            count = sum_metric(summaries, name)
            if count:
                problems.append(f"{count} {label}")
        reasons = {s.get("reason") for s in summaries if s.get("reason")}
        if reasons:
            problems.append(", ".join(sorted(reasons)))

        lines.append(
            f"- `{script}` {run_id} — **{badge}** — {elapsed:.0f}s — "
            + " · ".join(detail_bits)
            + (f" — ⚠ {'; '.join(problems)}" if problems else "")
        )
        if entry.get("log"):
            lines.append(f"  <sub>`{entry['log']}`</sub>")
    return lines


def render(day, rows, rows_by_source, duplicates, yesterday_count, alerts, runs_today,
           llm=None, yesterday_llm=None):
    out = [f"# 求职收集日报 — {day}", ""]

    out.append("## 1. 今日待投")
    out.append("")
    out += render_todo(rows, day, yesterday_count, duplicates, rows_by_source,
                       llm, yesterday_llm)
    out.append("")

    out.append("## 2. 健康告警")
    out.append("")
    if alerts:
        out += [f"- {a}" for a in alerts]
    else:
        out.append("✅ 一切正常")
    out.append("")

    out.append("## 3. 运行概况")
    out.append("")
    out += render_runs(runs_today)
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# housekeeping
# --------------------------------------------------------------------------

def prune_logs(retention_days=LOG_RETENTION_DAYS):
    """Delete .log files older than the retention window. Whitelist by suffix
    so runs.jsonl and daily/*.md can never be caught by this."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for path in glob.glob(os.path.join(LOG_ROOT, "*", "*.log")):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Daily report over the collector runs")
    parser.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                        help="Report on this day instead of today")
    parser.add_argument("--no-prune", action="store_true",
                        help="Skip deleting .log files older than "
                             f"{LOG_RETENTION_DAYS} days")
    args = parser.parse_args()

    if args.date:
        try:
            day = datetime.strptime(args.date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            parser.error("--date expects YYYY-MM-DD")
    else:
        day = date.today().strftime("%Y-%m-%d")
    previous = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    records, bad_lines = load_runs()
    runs_today = group_runs(records, day)

    rows_by_source, unparseable = load_jobs(day)
    rows, duplicates = dedup(rows_by_source)
    yesterday_rows, _ = dedup(load_jobs(previous)[0])

    llm = collect_llm_usage(records, day)
    yesterday_llm = collect_llm_usage(records, previous)

    alerts = build_alerts(runs_today, rows, duplicates, unparseable, bad_lines, day, llm)
    report = render(day, rows, rows_by_source, duplicates, len(yesterday_rows),
                    alerts, runs_today, llm, yesterday_llm)

    os.makedirs(DAILY_DIR, exist_ok=True)
    out_path = os.path.join(DAILY_DIR, f"{day}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Console summary - the file has the detail.
    print(f"{'=' * 60}\nDaily report — {day}\n{'=' * 60}")
    print(f"New jobs: {len(rows)} (yesterday {len(yesterday_rows)})")
    print(f"Runs:     {len(runs_today)}")
    if llm["runs"]:
        unpriced = f" + {llm['unpriced']} unpriced" if llm["unpriced"] else ""
        detail = [f"{llm['runs']} run(s)"]
        if llm["calls"]:
            detail.insert(0, f"{llm['calls']} calls")
        if llm["tokens"]:
            detail.append(f"{llm['tokens']:,} tokens")
        detail.append(f"yesterday ${yesterday_llm['cost_usd']:.4f}")
        print(f"LLM:      ${llm['cost_usd']:.4f}{unpriced} ({', '.join(detail)})")
    if alerts:
        print(f"\n{len(alerts)} alert(s):")
        for alert in alerts:
            print(f"  - {alert.replace('**', '')}")
    else:
        print("Alerts:   none")
    if not args.no_prune:
        removed = prune_logs()
        if removed:
            print(f"\nPruned {removed} log file(s) older than {LOG_RETENTION_DAYS} days")
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
