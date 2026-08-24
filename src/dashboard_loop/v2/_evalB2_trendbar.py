# -*- coding: utf-8 -*-
"""EVAL B round 2: orchestrator asked to verify/refute design_v2.md's trend-bar
claim -- "bar(d) is N-independent and sum(bar over window) == dedup(N)" --
SPECIFICALLY for an anchor that is NOT the last day in the corpus (design_v2's own
_pm2_01_fixes.py only tests anchor = days[-1], i.e. "today"; v1's design made the
same claim about "keep-NEWEST" being frozen but never anchored anywhere but the
final day either).

Also cross-checks the three watermark-derived views (all/new/wm) for
Sigma raw == dedup at every (view, N) cell, per design_v2.md S3.6/S3.10/F28.

Run:
  export PYTHONIOENCODING=utf-8
  D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalB2_trendbar.py
"""
from collections import Counter, defaultdict

from _pm2_base import CL, N_CHOICES, banner, cap2_map, dkey, load, superseded, win_rows


def bars_and_windows(rows, profiles, overrides, priority, anchor):
    """bar(d) using an anchor that may NOT be the last day in the corpus."""
    days_all = sorted({r["_day"] for r in rows if r["_day"] <= anchor})
    S = superseded(rows, anchor)  # scope _day <= anchor, per design S3.3
    bar = Counter(r["_day"] for r in rows
                  if r["_day"] <= anchor and id(r) not in S)
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    rows_out = []
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept = [r for r in w if id(r) not in S]
        ds = sorted({r["_day"] for r in w})
        s_bar = sum(bar[d] for d in ds)
        rows_out.append((n, len(kept), s_bar, s_bar == len(kept)))
    return days_all, bar, rows_out


def views_check(rows, profiles, overrides, priority, anchor, state):
    """Sigma raw == dedup for each (view, N) cell -- design_v2 F28."""
    S = superseded(rows, anchor)
    R = CL.LaneResolver(rows, profiles, anchor, overrides=overrides, priority=priority)
    prev_cutoff = state.get("cutoff") or ""
    prev_prev = state.get("prev_cutoff") or ""
    out = []
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept_all = [r for r in w if id(r) not in S]
        views = {
            "all": kept_all,
            "new": [r for r in kept_all if (r.get("_recorded") or "") > prev_cutoff],
            "wm": [r for r in kept_all
                   if prev_prev < (r.get("_recorded") or "") <= prev_cutoff],
        }
        row = {"n": n}
        for f, rs in views.items():
            raw = Counter(R.segment(r) for r in rs)
            row[f] = (sum(raw.values()), len(rs), sum(raw.values()) == len(rs))
        out.append(row)
    return out


def main():
    rows, profiles, overrides, priority = load()
    all_days = sorted({r["_day"] for r in rows})
    banner("EVAL B2 - trend bar N-independence for a NON-final anchor + 3-view I1")
    print("corpus days: %s (last day = 'today' = %s)" % (all_days, all_days[-1]))

    for anchor in all_days:  # includes non-final anchors, e.g. 2026-08-19, 2026-08-20
        tag = "TODAY" if anchor == all_days[-1] else "NOT today"
        print("\n--- anchor = %s (%s) ---" % (anchor, tag))
        days_all, bar, rows_out = bars_and_windows(rows, profiles, overrides, priority, anchor)
        print("   bar(d) for d <= anchor: %s"
              % ", ".join("%s=%d" % (d, bar[d]) for d in days_all))
        for n, dedup, s_bar, ok in rows_out:
            print("   N=%-3d dedup=%-6d sum(bar over window)=%-6d match=%s"
                  % (n, dedup, s_bar, ok))
        if not all(ok for *_, ok in rows_out):
            print("   *** MISMATCH at anchor=%s ***" % anchor)

    print("\n=== 3-view Sigma raw == dedup, anchor = last day (with real watermark) ===")
    st = None
    try:
        import dashboard as DB
        st = DB.read_state()
    except Exception as e:
        st = {}
    anchor = all_days[-1]
    print("   watermark state: cutoff=%r prev_cutoff=%r" % (st.get("cutoff"), st.get("prev_cutoff")))
    rows_v = views_check(rows, profiles, overrides, priority, anchor, st)
    for row in rows_v:
        n = row["n"]
        parts = []
        allok = True
        for f in ("all", "new", "wm"):
            raw, ded, ok = row[f]
            allok = allok and ok
            parts.append("%s(raw=%d,dedup=%d,%s)" % (f, raw, ded, "OK" if ok else "FAIL"))
        print("   N=%-3d %s  %s" % (n, " ".join(parts), "" if allok else "*** FAIL ***"))
        # also check design's claim "view=all dedup >= the other two" (F28 note)
        d_all = row["all"][1]
        for f in ("new", "wm"):
            if row[f][1] > d_all:
                print("      *** view=%s dedup (%d) > view=all dedup (%d) ***" % (f, row[f][1], d_all))


if __name__ == "__main__":
    main()
