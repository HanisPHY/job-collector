# -*- coding: utf-8 -*-
"""Evaluator A - rubric item 2 (the orchestrator's flagged suspicion).

design_v1.md 4.1/4.4/S3 lay out this file layout:

    logs/dashboard/
        2026-08-20.html            <- written on 08-20's run, "PIN_DAY" pinned
        data-2026-08-20.js         <- SHARED block, one file, used by both
                                      2026-08-20.html AND (later) latest.html
        data-index-2026-08-20.js   <- written once, on 08-20's run

and 4.4 / S3-end says explicitly: "每天早上重写：index + 保留窗口内全部天块"
and the "判定漂移的处置" paragraph in S3 says the CURRENT run's day blocks (ALL
retained days, not just today) get "每天早上全部重算重写" using the
GENERATION-DAY resolver (i.e. anchored at TODAY, not at each block's own day).

The x flag (S1) is scoped "_day <= 生成日" where "生成日" is explicitly the day
of the RUN that is doing the writing - and because §4.4 rewrites ALL retained
day blocks on every run, "生成日" for data-2026-08-20.js is a DIFFERENT day
every morning (it is always "today"), even though the file name never changes.

This script measures, using the REAL corpus: if 2026-08-20.html was generated
on 08-20 (anchor=08-20, x/g computed with that scope) and is opened TODAY
(08-21) after data-2026-08-20.js has been overwritten by the 08-21 run
(anchor=08-21, per design's own daily-rewrite rule) -- do rows that were
visible in the original 08-20 page vanish (via x=1) or move segment (via a
different g) in the shared block it still points to?
"""
from collections import defaultdict

from _evalA_base import CL, banner, dkey, load, resolver, superseded_flags


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    banner("PIN_DAY drift: same shared data-<day>.js, two different generation anchors")
    print("corpus days: %s" % days)

    if len(days) < 2:
        print("corpus too small to demonstrate (need >=2 days); aborting")
        return

    pin_day = days[-2]     # e.g. 2026-08-20 -- the day the historical page is pinned to
    later_anchor = days[-1]  # e.g. 2026-08-21 -- today, when the shared block gets rewritten

    print("\nScenario: %s.html was generated on %s (its own run, anchor=%s)."
          % (pin_day, pin_day, pin_day))
    print("Per design_v1.md S3/4.4, data-%s.js is a block SHARED with latest.html and"
          % pin_day)
    print("gets rewritten every morning using THAT DAY's run as the generation anchor.")
    print("Today (%s) it has been rewritten with anchor=%s." % (later_anchor, later_anchor))

    rows_pin_day = [r for r in rows if r["_day"] == pin_day]
    print("\nrows physically on %s: %d" % (pin_day, len(rows_pin_day)))

    # ---- x (superseded) flag: as originally written (anchor=pin_day) vs as
    # overwritten today (anchor=later_anchor) --------------------------------
    x_asof_pin = superseded_flags(rows, pin_day)          # scope: _day <= pin_day
    x_asof_today = superseded_flags(rows, later_anchor)   # scope: _day <= later_anchor

    flips_dropped = 0     # was visible (x=0) originally, now marked superseded (x=1)
    flips_restored = 0    # was superseded originally, now visible (should not happen, sanity)
    for r in rows_pin_day:
        was = x_asof_pin.get(id(r), 0)
        now = x_asof_today.get(id(r), 0)
        if was == 0 and now == 1:
            flips_dropped += 1
        elif was == 1 and now == 0:
            flips_restored += 1
    print("\n[x flag] rows on %s that were VISIBLE when the page was first generated"
          % pin_day)
    print("         but are marked SUPERSEDED (x=1) in the block as it stands TODAY: %d"
          % flips_dropped)
    print("         (sanity, should be 0) rows that flipped the other way: %d"
          % flips_restored)
    print("         => if dashboard.js does `if (x[i]) continue`, these %d rows"
          % flips_dropped)
    print("            silently vanish from a page that claims to be pinned to %s,"
          % pin_day)
    print("            with NO code change and NO re-run of that day's own generation.")

    # ---- g (segment) drift on the SAME shared block ------------------------
    Rpin = resolver(rows, profiles, pin_day, overrides, priority)
    Rtoday = resolver(rows, profiles, later_anchor, overrides, priority)
    seg_drift = [(r, Rpin.segment(r), Rtoday.segment(r)) for r in rows_pin_day
                 if Rpin.segment(r) != Rtoday.segment(r)]
    print("\n[g flag] rows on %s whose SEGMENT differs between anchor=%s (as first"
          % (pin_day, pin_day))
    print("         generated) and anchor=%s (as the shared block stands today): %d / %d"
          % (later_anchor, len(seg_drift), len(rows_pin_day)))
    for r, a, b in seg_drift[:10]:
        print("            %-30s %-40s  %s -> %s"
              % (r.get("company_name"), (r.get("job_title") or "")[:38], a, b))

    # ---- does this actually change what a viewer SEES, combined -----------
    combined = flips_dropped + len(seg_drift)
    print("\n[combined] rows on %s affected by EITHER x-drift or g-drift when the"
          % pin_day)
    print("           shared block is read today instead of on its own generation day: %d"
          % len({id(r) for r in rows_pin_day
                 if (x_asof_pin.get(id(r), 0) == 0 and x_asof_today.get(id(r), 0) == 1)
                 or Rpin.segment(r) != Rtoday.segment(r)}))

    print("\n[does design_v1.md's `check` table give the pinned page any way to detect")
    print(" or reconcile this?] data-index-%s.js was written ONCE, on %s's own run, and"
          % (pin_day, pin_day))
    print(" is never rewritten again (only TODAY's data-index-%s.js is). Its embedded"
          % later_anchor)
    print(" check[N] therefore reflects the OLD (pin_day-anchored) counts forever, while")
    print(" the day block(s) it points to keep being overwritten under new anchors.")
    print(" 4.3's own L2 self-check (JS count vs check[N]) WOULD catch the mismatch and")
    print(" show a red banner on %s.html once this drift is nonzero -- but that means" % pin_day)
    print(" the historical snapshot goes from 'green' to permanently red-banner-broken")
    print(" the day after judgment drift first touches it, with no mechanism to fix it")
    print(" short of re-running dashboard.py for that historical date (which the design")
    print(" does not describe doing).")


if __name__ == "__main__":
    main()
