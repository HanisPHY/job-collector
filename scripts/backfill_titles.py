# -*- coding: utf-8 -*-
"""
Retro-apply the title filter to newgrad_classifications.csv.

The LinkedIn lane ran without a positive software gate until 2026-08-22, so the
file carries thousands of rows that were never software jobs. The collector now
filters at ingest; this script cleans what is already there.

    python -u backfill_titles.py                    # dry run, writes nothing
    python -u backfill_titles.py --apply            # rewrite, backup first
    python -u backfill_titles.py --apply --use-llm  # also adjudicate the gray band

Safety, in the order it matters:

  * dry run is the DEFAULT; --apply is required to write anything
  * the original bytes are copied to a timestamped .bak.csv BEFORE the rewrite
  * a row with a non-empty `applied` value is never dropped, whatever the filter
    says - you acted on it, so it stays
  * without --use-llm the gray band is kept wholesale (fail open), so a dry run
    costs nothing and an --apply without a key still cannot over-delete
"""

import argparse
import csv
import os
import shutil
import sys
from datetime import datetime

import paths

from job_collector.classifiers.title_relevance import (
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)

DEFAULT_CSV = str(paths.DATA_DIR / "newgrad_classifications.csv")


class _Row:
    """Adapter so TitleFilter, which reads .job_title, can partition CSV rows."""

    def __init__(self, data):
        self.data = data
        self.job_title = (data.get("job_title") or "").strip()
        self.company_name = (data.get("company_name") or "").strip()


def backfill_csv(path, title_filter, apply=False):
    """Returns {kept, dropped, protected, backup}. Writes only when apply is True."""
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]

    protected, candidates = [], []
    for r in rows:
        if (r.get("applied") or "").strip():
            protected.append(r)          # you acted on it; the filter has no say
        else:
            candidates.append(r)

    kept_objs, dropped_objs = title_filter.filter_jobs(
        [_Row(r) for r in candidates], record=apply)
    dropped_ids = {id(o.data) for o in dropped_objs}

    # Rebuild in the ORIGINAL order rather than kept+protected: the file is read
    # by company_lane, and reordering it would silently reshuffle the dashboard.
    survivors = [r for r in rows if id(r) not in dropped_ids]

    result = {"kept": len(survivors), "dropped": len(dropped_objs),
              "protected": len(protected), "backup": None}
    if not apply:
        return result

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = "%s.%s.bak.csv" % (os.path.splitext(path)[0], stamp)
    shutil.copy2(path, backup)
    result["backup"] = backup

    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in survivors:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    os.replace(tmp, path)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--apply", action="store_true",
                    help="actually rewrite the file (default is a dry run)")
    ap.add_argument("--use-llm", action="store_true",
                    help="adjudicate the gray band; without this it is kept wholesale")
    args = ap.parse_args()

    tracker = None
    client = None
    if args.use_llm:
        from job_collector.tracking.cost_tracker import LLMCostTracker
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            print("--use-llm needs OPENAI_API_KEY; the gray band would be kept anyway.")
            return 1
        tracker = LLMCostTracker()
        client = OpenAIChatClient(api_key=key, cost_tracker=tracker)

    title_filter = TitleFilter(
        adjudicator=TitleAdjudicator(client=client,
                                     cache_path=str(paths.STATE_DIR / "title_verdicts.json"),
                                     cost_tracker=tracker),
        drop_log_path=str(paths.ROOT / "logs" / "dropped_titles.jsonl"),
    )

    result = backfill_csv(args.csv, title_filter, apply=args.apply)

    print("=" * 64)
    print("%s  %s" % (os.path.basename(args.csv),
                      "APPLIED" if args.apply else "DRY RUN (nothing written)"))
    print("=" * 64)
    print("  kept       %d" % result["kept"])
    print("  dropped    %d" % result["dropped"])
    print("  protected  %d  (non-empty `applied`, never dropped)" % result["protected"])
    if result["backup"]:
        print("  backup     %s" % os.path.basename(result["backup"]))
    if tracker and tracker.api_calls:
        cost = tracker.calculate_cost()
        print("  llm        %d calls, %s" % (
            tracker.api_calls,
            "$%.4f" % cost if cost is not None else "unpriced"))
    if not args.apply:
        print("\nRe-run with --apply to write. Dropped rows are listed in "
              "logs/dropped_titles.jsonl either way.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
