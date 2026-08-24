# -*- coding: utf-8 -*-
"""EVAL B round 2: independently reproduce design_v2.md's central claim for closing
B1 (my round-1 must_fix) -- that switching the new three-way view to "new" collapses
the day-to-day first-screen repeat rate that _evalB_repeat.py (round 1) measured at
39-89%. This re-derives the number from scratch (not by trusting _pm2_02_freshness.py's
own printout) using the corrected open_plan contract (A2) and the real watermark.

Run:
  export PYTHONIOENCODING=utf-8
  D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalB2_freshness.py
"""
from collections import defaultdict

from _pm2_base import (ALWAYS_OPEN, CL, OPEN_ORDER, banner, dkey, load,
                       open_plan, superseded, win_rows)


def first_screen_keys(rows, profiles, overrides, priority, anchor, n, view, state):
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    S = superseded(rows, anchor)
    w = win_rows(rows, anchor, n)
    kept = [r for r in w if id(r) not in S]
    pc = state.get("cutoff") or ""
    pp = state.get("prev_cutoff") or ""
    if view == "new":
        kept = [r for r in kept if (r.get("_recorded") or "") > pc]
    elif view == "wm":
        kept = [r for r in kept if pp < (r.get("_recorded") or "") <= pc]

    by_seg = defaultdict(list)
    for r in kept:
        by_seg[R.segment(r)].append(r)
    heads, cap2 = {}, {}
    for s in OPEN_ORDER:
        rs = by_seg.get(s, [])
        by_co = defaultdict(list)
        for r in rs:
            by_co[CL.norm(r["company_name"])].append(r)
        for v in by_co.values():
            v.sort(key=lambda r: (r.get("_recorded") or "", r.get("job_title") or ""),
                   reverse=True)
        ordered = sorted(by_co.items(), key=lambda kv: R.sort_key(kv[0]))
        head = []
        for c, rs2 in ordered:
            head.extend(rs2[:2])
        heads[s] = head
        cap2[s] = len(head)
    plan, tot = open_plan(cap2)
    keys = set()
    for s in OPEN_ORDER:
        for r in heads[s][:plan.get(s, 0)]:
            keys.add(dkey(r))
    return keys, tot


def main():
    rows, profiles, overrides, priority = load()
    import dashboard as DB
    state = DB.read_state()
    days = sorted({r["_day"] for r in rows})
    banner("EVAL B2 - does switching to view=new really collapse day-to-day repeat?")
    print("watermark: cutoff=%r prev_cutoff=%r" % (state.get("cutoff"), state.get("prev_cutoff")))

    for view in ("all", "new"):
        print("\n=== view=%s, N=3 (default) ===" % view)
        prev = None
        for d in days:
            keys, tot = first_screen_keys(rows, profiles, overrides, priority, d, 3, view, state)
            if prev is not None:
                pkeys, pd = prev
                inter = keys & pkeys
                pct = 100.0 * len(inter) / max(1, len(keys))
                print("   %s -> %s : first-screen %d/%d, repeat from yesterday %d (%.1f%%)"
                      % (pd, d, len(pkeys), len(keys), len(inter), pct))
            else:
                print("   %s : first-screen size %d" % (d, len(keys)))
            prev = (keys, d)


if __name__ == "__main__":
    main()
