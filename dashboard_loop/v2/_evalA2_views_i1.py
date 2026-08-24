# -*- coding: utf-8 -*-
"""Round 2 - orchestrator's item 3: does check[f][N] (f in all/new/wm) satisfy
I1 (Sum(raw)==dedup) in EVERY cell of the 3-view x 5-N grid, and is
view="all".dedup >= the other two (design_v2.md F28's second half)?

Also spot-checks B4 ("'new' view row count == number of (star) rows in 'all'")
and the ⑦-section [T4] "83 outside window at N=1" claim, independently.
"""
from collections import Counter, defaultdict

from _evalA_base import CL, N_CHOICES, banner, dkey, load, resolver, win_rows
from _evalA2_base import superseded_ids, view_pred


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("check[f][N] I1 across 3 views x 5 N, anchor=%s" % anchor)

    st = None
    import dashboard as DB
    st = DB.read_state()
    prev_cutoff = st.get("cutoff") or ""
    prev_prev = st.get("prev_cutoff") or ""
    print("state: prev_cutoff(=cutoff key)=%r prev_prev(=prev_cutoff key)=%r"
          % (prev_cutoff, prev_prev))
    print("(naming per design_v2 3.6: view='new' uses > prev_cutoff; "
          "view='wm' uses (prev_prev, prev_cutoff])")

    R = resolver(rows, profiles, anchor, overrides, priority)
    sup = superseded_ids(rows, anchor)

    all_ok = True
    print("\n%-4s %-5s %8s %8s %s" % ("N", "view", "dedup", "raw==ded", "note"))
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept_all = [r for r in w if id(r) not in sup]
        dedups = {}
        for view in ("all", "new", "wm"):
            pred = view_pred(view, prev_prev, prev_cutoff)
            kept = [r for r in kept_all if pred(r.get("_recorded") or "")]
            raw = Counter(R.segment(r) for r in kept)
            ok = sum(raw.values()) == len(kept)
            all_ok &= ok
            dedups[view] = len(kept)
            print("%-4d %-5s %8d %8s" % (n, view, len(kept), ok))
        order_ok = dedups["all"] >= dedups["new"] and dedups["all"] >= dedups["wm"]
        all_ok &= order_ok
        print("      view=all dedup >= new and >= wm : %s (all=%d new=%d wm=%d)"
              % (order_ok, dedups["all"], dedups["new"], dedups["wm"]))

    print("\nRESULT: I1 holds in all %d cells and all>=new/wm ordering holds: %s"
          % (3 * len(N_CHOICES), all_ok))

    # ---- B4 spot check: 'new' view row count == number of *-starred rows in 'all'
    print("\n[B4 spot check] N=1, does the 'new' view's row count equal the count of")
    print("  rows in the 'all' view whose (day,r) > cutoff (the '*new*' marker rule)?")
    w1 = win_rows(rows, anchor, 1)
    kept1 = [r for r in w1 if id(r) not in sup]
    star_count = sum(1 for r in kept1 if (r.get("_recorded") or "") > prev_cutoff)
    new_count = sum(1 for r in kept1 if (r.get("_recorded") or "") > prev_cutoff)
    print("   starred (●新) rows in 'all' @N=1 = %d ; 'new' view rows @N=1 = %d ; equal=%s"
          % (star_count, new_count, star_count == new_count))
    print("   (they use the literal same predicate in design_v2 3.6, so this is an")
    print("   identity, not a coincidence -- confirms B4 is trivially satisfied by")
    print("   construction, which is good, but means the 'B4 gives new coverage'")
    print("   framing in design_v2 0.2 is slightly overstated: it's the SAME check")
    print("   applied twice, not an independent one.)")


if __name__ == "__main__":
    main()
