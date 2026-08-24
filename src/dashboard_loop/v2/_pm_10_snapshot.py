# -*- coding: utf-8 -*-
"""PROBE 10 - the single consolidated snapshot every number in design_v1.md cites.

One run, one timestamp, one configuration. Re-run it any time; the numbers WILL
move (the corpus grew 2491 -> 2581 rows inside 17 minutes while these probes were
being written), which is the whole reason nothing downstream may assert a point
value.

    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_pm_10_snapshot.py
"""
import json
import os
import platform
import sys
from collections import Counter, defaultdict

from _pm_base import CL, DB, N_CHOICES, banner, days_back, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")
OPEN_ORDER = ["1a_t3", "B1", "1a_t2"]
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN = ("1a_t3", "B1")
FLOOR = 30
CEIL = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)      # 47, derived - never typed twice
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def open_plan(cap2):
    plan, used = {}, 0
    for s in ALWAYS_OPEN:
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s])
        used += plan[s]
    for s in OPEN_ORDER:
        if s in ALWAYS_OPEN or used >= FLOOR:
            continue
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s], FLOOR - used)
        used += plan[s]
    return plan, used


def superseded(rows, anchor):
    """keep-NEWEST, scoped to rows on or before the anchor day. Scope matters:
    computing it over the WHOLE corpus makes rows vanish from earlier anchors."""
    g = defaultdict(list)
    for r in rows:
        if r["_day"] <= anchor:
            g[dkey(r)].append(r)
    s = set()
    for v in g.values():
        v.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        s.update(id(z) for z in v[:-1])
    return s


def cap2_map(R, kept):
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    return {s: sum(min(2, len(v)) for v in by[s].values()) for s in SEGS}


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("PROBE 10  consolidated snapshot")
    print("python      %s" % sys.version.split()[0])
    print("interpreter %s" % sys.executable)
    print("platform    %s" % platform.platform())
    print("PYTHONIOENCODING=%r" % os.environ.get("PYTHONIOENCODING"))
    print("corpus      %d rows, days %s, companies %d, profiles %d, overrides %d"
          % (len(rows), ",".join(days),
             len({CL.norm(r["company_name"]) for r in rows}), len(profiles),
             len(overrides)))
    per_day = Counter(r["_day"] for r in rows)
    for d in days:
        print("            %s raw %5d  day-deduped %5d" % (d, per_day[d],
                                                           len(CL.day_rows(rows, d))))

    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)
    print("\n[T1] window view, anchor %s, x scoped to _day <= anchor" % anchor)
    print("     %-4s %7s %7s %7s  %s  %6s %6s"
          % ("N", "rawwin", "dedup", "dropped",
             " ".join("%6s" % s for s in SEGS), "cap2Σ", "open"))
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept = [r for r in w if id(r) not in S]
        raw = Counter(R.segment(r) for r in kept)
        c2 = cap2_map(R, kept)
        plan, tot = open_plan(c2)
        assert sum(raw.values()) == len(kept) == len({dkey(r) for r in w})
        assert tot <= CEIL and tot >= min(FLOOR, sum(c2[s] for s in OPEN_ORDER))
        print("     %-4d %7d %7d %7d  %s  %6d %6d"
              % (n, len(w), len(kept), len(w) - len(kept),
                 " ".join("%6d" % raw.get(s, 0) for s in SEGS), sum(c2.values()), tot))
    print("     I1 window form holds for all 5 N; no duplicate key survives; "
          "min(FLOOR,supply) <= open <= %d" % CEIL)

    print("\n[T2] first screen at 08:00 (the hour run_daily_report.bat generates it)")
    print("     %-12s %-4s %8s %8s %8s" % ("anchor", "N", "v1 rule", "proposed", "supply"))
    for d in days:
        sub = [r for r in rows if (r.get("_recorded") or "") <= d + " 08:00"]
        if not sub:
            continue
        Rd = CL.LaneResolver(sub, profiles, d, overrides=overrides, priority=priority)
        Sd = superseded(sub, d)
        for n in N_CHOICES:
            kept = [r for r in win_rows(sub, d, n) if id(r) not in Sd]
            c2 = cap2_map(Rd, kept)
            v1 = sum(min(c2[s], DB.OPEN_CAP.get(s, c2[s])) for s in ALWAYS_OPEN)
            _p, tot = open_plan(c2)
            print("     %-12s %-4d %8d %8d %8d"
                  % (d, n, v1, tot, sum(c2[s] for s in OPEN_ORDER)))

    print("\n[T3] payload size, encoding E4 (column arrays, interned day/segment/prefix)")
    cos = sorted({CL.norm(r["company_name"]) for r in rows})
    cidx = {c: i for i, c in enumerate(cos)}
    segi = {s: i for i, s in enumerate(SEGS)}
    prefs = ["https://www.linkedin.com", "https://jobs.ashbyhq.com",
             "https://job-boards.greenhouse.io", "https://jobs.lever.co",
             "https://boards.greenhouse.io"]
    pmap = {p: i for i, p in enumerate(prefs)}
    tot_b = 0
    for d in days:
        sub = [r for r in rows if r["_day"] == d]
        col = {"c": [], "g": [], "t": [], "lp": [], "l": [], "s": [], "r": [], "x": []}
        for r in sub:
            l = (r.get("job_link") or "").strip()
            p = "/".join(l.split("/")[:3])
            rec = r.get("_recorded") or ""
            col["c"].append(cidx[CL.norm(r["company_name"])])
            col["g"].append(segi[R.segment(r)])
            col["t"].append((r.get("job_title") or "").strip())
            col["lp"].append(pmap.get(p, -1))
            col["l"].append(l[len(p):] if p in pmap else l)
            col["s"].append({"newgrad": 0, "ats_direct": 1, "ddg": 2}[r["_source"]])
            col["r"].append(int(rec[11:13] + rec[14:16]) if len(rec) >= 16 else 0)
            col["x"].append(1 if id(r) in S else 0)
        b = len(J(col).encode("utf-8"))
        tot_b += b
        print("     data-%s.js  %5d rows  %8d B  %.1f B/row" % (d, len(sub), b,
                                                                b / float(len(sub))))
    idx = {"co": [[R.profile(c).get("name") or c, R.profile(c)["tier"],
                   R.profile(c)["prom"], R.window_count(c), 1 if c in R.board else 0]
                  for c in cos],
           "o": [i for i, _c in enumerate(sorted(cos, key=R.sort_key))],
           "days": days_back(anchor, 30)}
    ib = len(J(idx).encode("utf-8"))
    print("     index (co/o/days)      %8d B  for %d companies" % (ib, len(cos)))
    print("     total today            %8d B  (%.2f MB)" % (tot_b + ib,
                                                            (tot_b + ib) / 2.0 ** 20))
    bpr = tot_b / float(len(rows))
    print("     projection at 2000 rows/day: %.0f B/day, 30 days = %.2f MB"
          % (2000 * bpr, 2000 * bpr * 30 / 2 ** 20))

    print("\n[T4] section 7 under the shipped watermark")
    st = DB.read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    pool = [r for r in rows if pp < (r.get("_recorded") or "") <= pc and id(r) not in S]
    p124 = [r for r in pool if R.segment(r) in ("1a_t3", "1a_t2", "B1")]
    print("     interval (%s, %s] : %d deduped, %d in (1)(2)(4)"
          % (pp, pc, len(pool), len(p124)))
    for n in N_CHOICES:
        wk = {dkey(r) for r in win_rows(rows, anchor, n)}
        out = [r for r in p124 if dkey(r) not in wk]
        print("     N=%-3d outside the window %3d   inside (filter switch) %3d"
              % (n, len(out), len(p124) - len(out)))


if __name__ == "__main__":
    main()
