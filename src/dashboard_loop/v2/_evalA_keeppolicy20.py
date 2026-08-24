# -*- coding: utf-8 -*-
"""Precisely reproduce design_v1.md S1's stated metric:

  "keep-NEWEST : (group,N) pairs whose window survivor != group's GLOBAL
   newest row = 0"
  "keep-OLDEST : (group,N) pairs whose window survivor != group's GLOBAL
   OLDEST row = 20"

i.e. the point being made is "is the survivor N-invariant": for keep-NEWEST,
compare each window's survivor against the group's overall newest occurrence
(across the full/largest available window); for keep-OLDEST, compare against
the group's overall OLDEST occurrence. A policy is "N-invariant / freezable"
iff this count is 0.
"""
from collections import defaultdict

from _evalA_base import N_CHOICES, banner, dkey, load, win_rows


def main():
    rows, *_ = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("keep-policy N-invariance check (group,N) mismatches, anchor=%s" % anchor)

    grp_all = defaultdict(list)
    for r in rows:
        grp_all[dkey(r)].append(r)
    global_newest, global_oldest = {}, {}
    for k, g in grp_all.items():
        g_sorted = sorted(g, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""))
        global_oldest[k] = id(g_sorted[0])
        global_newest[k] = id(g_sorted[-1])

    mism_newest = mism_oldest = pairs = 0
    per_n = {}
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        grp_w = defaultdict(list)
        for r in w:
            grp_w[dkey(r)].append(r)
        mn = mo = 0
        for k, g in grp_w.items():
            g_sorted = sorted(g, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""))
            newest_survivor = id(g_sorted[-1])
            oldest_survivor = id(g_sorted[0])
            pairs += 1
            if newest_survivor != global_newest[k]:
                mn += 1
            if oldest_survivor != global_oldest[k]:
                mo += 1
        mism_newest += mn
        mism_oldest += mo
        per_n[n] = (mn, mo, len(grp_w))
        print("   N=%-3d groups-in-window=%-5d  keep-NEWEST mismatch=%-4d  "
              "keep-OLDEST mismatch=%-4d" % (n, len(grp_w), mn, mo))

    print("\nTOTAL over the 5 N labels: keep-NEWEST mismatches=%d  keep-OLDEST mismatches=%d"
          % (mism_newest, mism_oldest))
    # design_v1 notes N=3/7/14/30 are literally the SAME window on this corpus
    # (only 3 days exist) - count DISTINCT windows too, to see if that is the
    # scope design_v1's "20" actually used.
    distinct_ns = []
    seen_spans = set()
    for n in N_CHOICES:
        ds = tuple(sorted({r["_day"] for r in win_rows(rows, anchor, n)}))
        if ds not in seen_spans:
            seen_spans.add(ds)
            distinct_ns.append(n)
    mn2 = sum(per_n[n][0] for n in distinct_ns)
    mo2 = sum(per_n[n][1] for n in distinct_ns)
    print("distinct window shapes at N=%s (rest are duplicates on this corpus): "
          "keep-NEWEST mismatches=%d  keep-OLDEST mismatches=%d" % (distinct_ns, mn2, mo2))


if __name__ == "__main__":
    main()
