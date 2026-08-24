# -*- coding: utf-8 -*-
"""ROUND-2 PROBE 2 - B1: the first screen repeats itself day after day.

Evaluator B measured it and is right: at the default N=3 the first screen is
89% identical to yesterday's. This probe asks the question that decides the fix:

    at each N, how many of the first-screen rows are things the user has NOT
    already been shown - i.e. arrived after the previous report's watermark?

If the answer is "N=3's first screen contains at least as many genuinely new rows
as N=1's", then the fix is a VIEW over the same data (a watermark-derived filter),
not a change of default N and not any persisted user state.

The watermark is simulated per anchor day the way the scheduler produces it:
the report runs at 08:00, so the cutoff of the previous issue is <anchor-1> 08:00
and the one before that is <anchor-2> 08:00.
"""
from collections import Counter

from _pm2_base import (CL, FLOOR, N_CHOICES, SEGS, banner, cap2_map, dkey,
                       first_screen_keys, load, open_plan, superseded, win_rows)


def watermarks(anchor):
    """(prev_prev, prev_cutoff, cutoff) as the 08:00 scheduler would have them."""
    from datetime import datetime, timedelta
    d0 = datetime.strptime(anchor, "%Y-%m-%d")
    f = lambda k: (d0 - timedelta(days=k)).strftime("%Y-%m-%d") + " 08:00"
    return f(2), f(1), f(0)


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    banner("ROUND-2 PROBE 2  B1 first-screen freshness")
    print("corpus %d rows, days %s" % (len(rows), ",".join(days)))

    # --------------------------------------------------- A. repeat, reproduced
    print("\n[A] day-to-day repeat of the first screen (evaluator B's finding)")
    screens = {}
    for n in N_CHOICES:
        for d in days:
            sub = [r for r in rows if (r.get("_recorded") or "") <= d + " 08:00"]
            if not sub:
                continue
            R = CL.LaneResolver(sub, profiles, d, overrides=overrides, priority=priority)
            S = superseded(sub, d)
            kept = [r for r in win_rows(sub, d, n) if id(r) not in S]
            screens[(n, d)] = (R, {dkey(r) for _s, _c, r in first_screen_keys(R, kept)},
                               kept)
    for n in N_CHOICES:
        line = []
        for i in range(1, len(days)):
            a, b = screens.get((n, days[i - 1])), screens.get((n, days[i]))
            if not a or not b:
                continue
            ov = len(a[1] & b[1])
            line.append("%s->%s %d/%d (%d%%)" % (days[i - 1][5:], days[i][5:], ov,
                                                 len(b[1]),
                                                 100 * ov // max(1, len(b[1]))))
        print("   N=%-3d %s" % (n, "   ".join(line)))

    # --------------------------------------- B. how many first-screen rows are NEW
    print("\n[B] of the first-screen rows, how many arrived since the PREVIOUS report")
    print("    (watermark simulated at 08:00 daily; '新' = _recorded > prev_cutoff)")
    print("   %-12s %-4s %8s %8s %8s %8s"
          % ("anchor", "N", "screen", "new", "new%", "win-new"))
    for d in days:
        pp, pc, _cut = watermarks(d)
        for n in N_CHOICES:
            got = screens.get((n, d))
            if not got:
                continue
            R, keys, kept = got
            scr = first_screen_keys(R, kept)
            new = sum(1 for _s, _c, r in scr if (r.get("_recorded") or "") > pc)
            win_new = sum(1 for r in kept if (r.get("_recorded") or "") > pc)
            print("   %-12s %-4d %8d %8d %7d%% %8d"
                  % (d, n, len(scr), new, 100 * new // max(1, len(scr)), win_new))

    # --------------------------------- C. the three-way watermark-derived filter
    print("\n[C] the filter that closes B1 without storing ANY user state")
    print("    all  = everything in the window")
    print("    new  = _recorded > cutoff of the previous report      (the '● 新' rows)")
    print("    wm   = prev_prev < _recorded <= prev_cutoff           (last issue's pool)")
    print("   %-12s %-4s %8s %8s %8s | first screen under each filter"
          % ("anchor", "N", "all", "new", "wm"))
    for d in days:
        pp, pc, _c = watermarks(d)
        for n in N_CHOICES:
            got = screens.get((n, d))
            if not got:
                continue
            R, _k, kept = got
            f_all = kept
            f_new = [r for r in kept if (r.get("_recorded") or "") > pc]
            f_wm = [r for r in kept if pp < (r.get("_recorded") or "") <= pc]
            outs = []
            for label, sel in (("all", f_all), ("new", f_new), ("wm", f_wm)):
                c2 = cap2_map(R, sel)
                _p, tot = open_plan(c2)
                outs.append("%s=%d" % (label, tot))
            print("   %-12s %-4d %8d %8d %8d | %s"
                  % (d, n, len(f_all), len(f_new), len(f_wm), "  ".join(outs)))

    # ------------------- D. does the 'new' filter actually remove the repetition?
    print("\n[D] day-to-day repeat WITH the 'new' filter on (should collapse to ~0)")
    for n in N_CHOICES:
        line = []
        prev = None
        for d in days:
            got = screens.get((n, d))
            if not got:
                continue
            R, _k, kept = got
            pp, pc, _c = watermarks(d)
            sel = [r for r in kept if (r.get("_recorded") or "") > pc]
            ks = {dkey(r) for _s, _c2, r in first_screen_keys(R, sel)}
            if prev is not None:
                ov = len(prev[1] & ks)
                line.append("%s->%s %d/%d" % (prev[0][5:], d[5:], ov, len(ks)))
            prev = (d, ks)
        print("   N=%-3d %s" % (n, "   ".join(line)))

    # --------------------------------------------- E. is the date column present?
    print("\n[E] req2 4.2 decision 4 requires a DATE column in the window view.")
    print("    spread of _day inside one first screen (if it is 1, the column is")
    print("    useless; if it is >1 the column is load-bearing):")
    for n in N_CHOICES:
        d = days[-1]
        got = screens.get((n, d))
        if not got:
            continue
        R, _k, kept = got
        c = Counter(r["_day"] for _s, _c2, r in first_screen_keys(R, kept))
        print("   N=%-3d anchor %s  first screen spans %d day(s): %s"
              % (n, d, len(c), dict(sorted(c.items()))))


if __name__ == "__main__":
    main()
