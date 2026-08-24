# -*- coding: utf-8 -*-
"""ROUND-2 PROBE 1 - close A2 (open_plan contract) and A3 (two dedup rules).

A2: v1 claimed  min(FLOOR, supply) <= open <= CEIL  with supply = the UNTRUNCATED
    sum of cap2 over the three openable segments. Evaluator A found 1931/500000
    counterexamples. Reproduce, then verify the corrected contract as an EQUALITY
    (open == open_expected(cap2)), which leaves no hand-written bound to get wrong.

A3: v1 kept TWO dedup rules alive at once - CL.dedup_rows (source-order-first, used
    by CL.day_rows for the trend bars and by F6/F7/F19) and keep-NEWEST (used by the
    window view). Measure the divergence, then verify the subtraction: define the
    trend bar as "window survivors attributed to that day" and check that it is
    N-independent and sums EXACTLY to dedup, so the second rule can be deleted.
"""
import random
from collections import Counter, defaultdict

from _pm2_base import (ALWAYS_OPEN, CEIL, CL, FLOOR, N_CHOICES, OPEN_ORDER,
                       SEG_OPEN_CAP, SEGS, banner, cap2_map, dkey, load,
                       open_expected, open_plan, openable, superseded, win_rows)


def part_a2():
    print("\n[A2] open_plan contract")
    print("   v1 wrote   : min(FLOOR, Sum_of_raw_cap2) <= open <= CEIL")
    print("   v2 writes  : open == max(base, min(base+filler, FLOOR)),  base/filler")
    print("                already truncated by SEG_OPEN_CAP  ->  and therefore")
    print("                min(FLOOR, openable(cap2)) <= open <= CEIL")
    random.seed(20260821)
    bad_v1 = bad_v2 = bad_eq = 0
    worst_v1 = 0
    N = 500000
    for _ in range(N):
        cap2 = {s: random.randint(0, 200) for s in OPEN_ORDER}
        _plan, opened = open_plan(cap2)
        raw_supply = sum(cap2[s] for s in OPEN_ORDER)
        if opened < min(FLOOR, raw_supply):
            bad_v1 += 1
            worst_v1 = min(worst_v1, opened - min(FLOOR, raw_supply))
        if opened < min(FLOOR, openable(cap2)) or opened > CEIL:
            bad_v2 += 1
        if opened != open_expected(cap2):
            bad_eq += 1
    print("   %d random cap2 in [0,200]^3:" % N)
    print("      v1 lower bound violated : %d   (worst shortfall %d)" % (bad_v1, worst_v1))
    print("      v2 bounds violated      : %d" % bad_v2)
    print("      open != closed form     : %d" % bad_eq)

    hand = [
        {"1a_t3": 0, "B1": 1000, "1a_t2": 0},
        {"1a_t3": 1, "B1": 109, "1a_t2": 1},
        {"1a_t3": 0, "B1": 0, "1a_t2": 100000},
        {}, {"1a_t2": 40}, {"1a_t3": 29, "B1": 0, "1a_t2": 5},
        {"1a_t3": 10 ** 9, "B1": 10 ** 9, "1a_t2": 10 ** 9},
    ]
    print("   hand-picked adversarial shapes (incl. evaluator A's counterexamples):")
    for c in hand:
        _p, o = open_plan(c)
        print("      cap2=%-46s open=%-4d openable=%-8d closed_form=%-4d %s"
              % (c, o, openable(c), open_expected(c),
                 "OK" if (o == open_expected(c) and min(FLOOR, openable(c)) <= o <= CEIL)
                 else "*** FAIL ***"))
    print("   -> A2 closes by redefining the published bound, not by changing open_plan.")
    print("      (4) stays capped at %d on the first screen ON PURPOSE; the honest"
          % SEG_OPEN_CAP["B1"])
    print("      statement is 'fill to 30 out of what the three segments may contribute'.")


def part_a3(rows, profiles, overrides, priority):
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    print("\n[A3] how far apart are the two dedup rules today")
    tot_diff = tot_seg = 0
    for d in days:
        day_all = [r for r in rows if r["_day"] == d]
        a = {id(r) for r in CL.dedup_rows(day_all)[0]}          # source-order-first
        sup = superseded(day_all, d)
        b = {id(r) for r in day_all if id(r) not in sup}        # keep-newest
        assert len(a) == len(b)
        byk = defaultdict(list)
        for r in day_all:
            byk[dkey(r)].append(r)
        diff = seg = 0
        R = CL.LaneResolver(rows, profiles, d, overrides=overrides, priority=priority)
        for k, g in byk.items():
            ra = next(r for r in g if id(r) in a)
            rb = next(r for r in g if id(r) in b)
            if ra is not rb:
                diff += 1
                if R.segment(ra) != R.segment(rb):
                    seg += 1
        tot_diff += diff
        tot_seg += seg
        print("   %s  groups %5d  different survivor %3d  of which different SEGMENT %d"
              % (d, len(byk), diff, seg))
    print("   total: %d groups pick a different physical row, %d of them cross a segment"
          % (tot_diff, tot_seg))
    print("   -> today 0 cross a segment, which is exactly why v1's 'no fixture change'")
    print("      argument was a coincidence and not a mechanism.")

    print("\n[A3-fix] subtraction: ONE rule. Trend bar(d) = window survivors on day d.")
    S = superseded(rows, anchor)
    bar = Counter(r["_day"] for r in rows if id(r) not in S and r["_day"] <= anchor)
    old = {d: len(CL.day_rows(rows, d)) for d in days}
    print("   %-12s %10s %10s %8s" % ("day", "v1 bar", "v2 bar", "delta"))
    for d in days:
        print("   %-12s %10d %10d %8d" % (d, old[d], bar[d], bar[d] - old[d]))
    print("   %-12s %10d %10d %8d" % ("SUM", sum(old.values()), sum(bar.values()),
                                      sum(bar.values()) - sum(old.values())))
    print("\n   bar(d) must be N-independent, and sum(bar over window) == dedup(N):")
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept = [r for r in w if id(r) not in S]
        ds = sorted({r["_day"] for r in w})
        s_bar = sum(bar[d] for d in ds)
        per = Counter(r["_day"] for r in kept)
        same = all(per[d] == bar[d] for d in ds)
        raw = Counter(R.segment(r) for r in kept)
        print("      N=%-3d dedup %5d  sum(bar) %5d  match %s  bar N-independent %s  "
              "I1 %s" % (n, len(kept), s_bar, s_bar == len(kept), same,
                         sum(raw.values()) == len(kept)))
    print("   -> v1 needed a footnote ('sum of per-day dedup 2073 vs window 2035').")
    print("      With one rule the two numbers ARE the same number. Footnote deleted.")


def main():
    rows, profiles, overrides, priority = load()
    banner("ROUND-2 PROBE 1  A2 open_plan contract / A3 one dedup rule")
    print("corpus %d rows, days %s" % (len(rows), ",".join(sorted({r["_day"] for r in rows}))))
    part_a2()
    part_a3(rows, profiles, overrides, priority)


if __name__ == "__main__":
    main()
