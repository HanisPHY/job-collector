# -*- coding: utf-8 -*-
"""PROBE 9 - what the page looks like at 08:00, the hour it is actually generated,
plus the refined section-7 rule and the cost of the per-day HTML snapshot.

The dashboard is generated at 08:00 by run_daily_report.bat. Every number anyone
has quoted for "today" was measured at the END of a day. Measure it at 08:00.
"""
import os
from collections import Counter, defaultdict

from _pm_base import CL, DB, N_CHOICES, banner, days_back, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")
OPEN_ORDER = ["1a_t3", "B1", "1a_t2"]
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN = ("1a_t3", "B1")
FLOOR = 30


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


def cap2_map(R, kept):
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    return {s: sum(min(2, len(v)) for v in by[s].values()) for s in SEGS}


def sup_set(rows):
    grp = defaultdict(list)
    for r in rows:
        grp[dkey(r)].append(r)
    s = set()
    for g in grp.values():
        g.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        s.update(id(z) for z in g[:-1])
    return s


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    day = days[-1]
    banner("PROBE 9  the 08:00 view / section 7 rule / snapshot cost")

    print("A. arrival curve: rows recorded by hour H of the day")
    for d in days:
        c = Counter((r.get("_recorded") or "")[11:13] for r in rows if r["_day"] == d)
        cum, line = 0, []
        for h in ("06", "08", "10", "12", "18", "23"):
            cum = sum(v for k, v in c.items() if k <= h)
            line.append("<=%s:%d" % (h, cum))
        print("   %s total %5d   %s" % (d, sum(c.values()), "  ".join(line)))

    print("\nB. the first screen AS OF 08:00 on the generation day")
    for d in days:
        cut = d + " 08:00"
        sub = [r for r in rows if (r.get("_recorded") or "") <= cut]
        if not sub:
            continue
        R = CL.LaneResolver(sub, profiles, d, overrides=overrides, priority=priority)
        sup = sup_set(sub)
        for n in N_CHOICES:
            kept = [r for r in win_rows(sub, d, n) if id(r) not in sup]
            c2 = cap2_map(R, kept)
            plan, tot = open_plan(c2)
            now = sum(min(c2[s], DB.OPEN_CAP.get(s, c2[s])) for s in ALWAYS_OPEN)
            supply = sum(c2[s] for s in OPEN_ORDER)
            print("   %s 08:00  N=%-3d dedup %5d  now %2d  proposed %2d  supply %4d  %s"
                  % (d, n, len(kept), now, tot, supply,
                     " ".join("%s=%d" % (s, plan[s]) for s in OPEN_ORDER if plan.get(s))))

    print("\nC. refined section-7 rule: watermark-interval rows in (1)(2)(4) that are")
    print("   NOT already inside the N-day window (one rule, no N-dependent mode)")
    st = DB.read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
    sup = sup_set(rows)
    pool = [r for r in rows if pp < (r.get("_recorded") or "") <= pc and id(r) not in sup]
    pool124 = [r for r in pool if R.segment(r) in ("1a_t3", "1a_t2", "B1")]
    print("   watermark interval (%s, %s]: %d deduped rows, %d in (1)(2)(4)"
          % (pp, pc, len(pool), len(pool124)))
    for n in N_CHOICES:
        wk = {dkey(r) for r in win_rows(rows, day, n)}
        outside = [r for r in pool124 if dkey(r) not in wk]
        print("      N=%-3d section 7 shows %3d rows (outside the window); "
              "%3d are already in the window and reachable by the filter switch"
              % (n, len(outside), len(pool124) - len(outside)))

    print("\nD. cost of the per-day HTML snapshot")
    outdir = os.path.join(DB.OUT_DIR)
    for f in sorted(os.listdir(outdir)):
        if f.endswith(".html"):
            print("   v1 %-22s %8d B" % (f, os.path.getsize(os.path.join(outdir, f))))
    print("   v2 skeleton (link + 2 script tags + a pinned day) is ~2 KB;")
    print("   the data it points at is the shared data-<day>.js files.")


if __name__ == "__main__":
    main()
