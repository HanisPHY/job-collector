# -*- coding: utf-8 -*-
"""EVAL B probe: does the open_plan first screen show the SAME job on consecutive
mornings? This is the rubric-1 question ("会不会让用户每天看到一样的东西"),
which none of the PM probes (_pm_01..10) directly measure -- they measure counts
and bounds, not day-to-day identity overlap of what lands on the first screen.

Method: for each pair of consecutive real anchor days in the corpus, build the
first-screen selection (open_plan over cap2, using the GENERATION-DAY resolver,
per design_v1.md S4/4.6) for the default N=3 window ending at that anchor, and
for N=1. Compare the (company_norm, tnorm(title)) identity set between the two
anchors' first screens.

Run:
  export PYTHONIOENCODING=utf-8
  D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalB_repeat.py
"""
from collections import defaultdict

from _pm_base import CL, banner, dkey, load, win_rows

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


def first_screen_keys(rows, profiles, overrides, priority, anchor, n):
    """-> set of dedup keys selected onto the first screen for (anchor, n)."""
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    win = win_rows(rows, anchor, n)
    # window dedup, keep-newest (per design S1)
    seq = sorted(win, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""),
                 reverse=True)
    seen, kept = set(), []
    for r in seq:
        k = dkey(r)
        if k in seen:
            continue
        seen.add(k)
        kept.append(r)

    by_seg = defaultdict(list)
    for r in kept:
        by_seg[R.segment(r)].append(r)

    # group by company, cap2 head, sorted by sort_key then (_recorded desc, title)
    heads = {}
    cap2 = {}
    for s in OPEN_ORDER:
        rs = by_seg.get(s, [])
        by_co = defaultdict(list)
        for r in rs:
            by_co[CL.norm(r["company_name"])].append(r)
        for v in by_co.values():
            v.sort(key=lambda r: (r.get("_recorded") or "", r.get("job_title") or ""),
                   reverse=True)
        ordered_cos = sorted(by_co.items(), key=lambda kv: R.sort_key(kv[0]))
        head = []
        for c, rs2 in ordered_cos:
            head.extend(rs2[:2])
        heads[s] = head
        cap2[s] = len(head)

    plan, _ = open_plan(cap2)
    keys = set()
    for s in OPEN_ORDER:
        take = plan.get(s, 0)
        for r in heads[s][:take]:
            keys.add(dkey(r))
    return keys, plan


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    banner("EVAL B - first-screen day-to-day repeat content, anchors=%s" % days)

    for n in (1, 3):
        print("\n=== N=%d ===" % n)
        prev = None
        for d in days:
            keys, plan = first_screen_keys(rows, profiles, overrides, priority, d, n)
            if prev is not None:
                pkeys, pd = prev
                inter = keys & pkeys
                union = keys | pkeys
                print("   %s -> %s : first-screen size %d/%d, overlap %d "
                      "(%.0f%% of today's screen was ALSO on yesterday's screen), plan=%r"
                      % (pd, d, len(pkeys), len(keys), len(inter),
                         100.0 * len(inter) / max(1, len(keys)), plan))
            else:
                print("   %s : first-screen size %d, plan=%r" % (d, len(keys), plan))
            prev = (keys, d)

    # also: how many of TODAY's screen keys were already visible on EVERY prior day
    # (i.e. a job a user would have seen 2+ days running under N=3 default)
    print("\n=== N=3 (default): keys present on first screen for >=2 consecutive anchors ===")
    n = 3
    screens = []
    for d in days:
        keys, _ = first_screen_keys(rows, profiles, overrides, priority, d, n)
        screens.append((d, keys))
    for i in range(1, len(screens)):
        d0, k0 = screens[i - 1]
        d1, k1 = screens[i]
        repeated = k0 & k1
        print("   %s & %s: %d keys in common (of %d today / %d yesterday)"
              % (d0, d1, len(repeated), len(k1), len(k0)))
        if repeated:
            sample = sorted(repeated)[:5]
            print("      sample keys: %s" % sample)


if __name__ == "__main__":
    main()
