# -*- coding: utf-8 -*-
"""PROBE 1 - the window view under the 5 preset N values.

Answers:
  * corpus size right now (re-measured, not copied from req2)
  * for N in 1/3/7/14/30: raw rows in window, deduped rows, per-segment raw,
    cap2, and OPEN_CAP-visible rows
  * I1 window form: sum(raw per segment) == deduped window rows
  * duplicate check: after window dedup, is (company, tnorm title) count 0?
  * S1: keep-first vs keep-last - does the choice change anything visible?
"""
from collections import Counter, defaultdict

from _pm_base import (CL, DB, N_CHOICES, banner, days_back, dedup_keep, dkey,
                      load, win_rows)

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")


def cap2_of(R, seg_rows, cap=2):
    by = defaultdict(list)
    for r in seg_rows:
        by[CL.norm(r["company_name"])].append(r)
    return sum(min(cap, len(v)) for v in by.values())


def main():
    rows, profiles, overrides, priority = load()
    day = max(r["_day"] for r in rows)
    banner("PROBE 1  window view, anchor day = %s" % day)

    per_day = Counter(r["_day"] for r in rows)
    print("load_rows total = %d rows over %d distinct days" % (len(rows), len(per_day)))
    for d in sorted(per_day):
        print("   %s  raw %5d   day-deduped %5d" % (d, per_day[d], len(CL.day_rows(rows, d))))

    # ONE resolver anchored at the generation day: the 7-day decision window is
    # fixed (I4), the view window N is a separate axis (req2 5.4).
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
    print("\nresolver decision window (fixed, I4): %s .. %s  (%d days)"
          % (R.win_lo, R.day, R.window_days))

    print("\n%-4s %7s %7s %7s | %s" % ("N", "rawwin", "dedup", "dropped",
                                       "  ".join("%7s" % s for s in SEGS)))
    results = {}
    for n in N_CHOICES:
        w = win_rows(rows, day, n)
        kept, dropped = dedup_keep(w, "first")
        raw = Counter(R.segment(r) for r in kept)
        cap2 = {s: cap2_of(R, [r for r in kept if R.segment(r) == s]) for s in SEGS}
        vis = sum(min(cap2[s], DB.OPEN_CAP.get(s, cap2[s])) for s in ("1a_t3", "B1"))
        results[n] = (len(w), len(kept), dropped, dict(raw), cap2, vis)
        print("%-4d %7d %7d %7d | %s" % (n, len(w), len(kept), dropped,
                                         "  ".join("%7d" % raw.get(s, 0) for s in SEGS)))
        assert sum(raw.values()) == len(kept), "I1 window form BROKEN for N=%d" % n

    print("\nI1 (window form) sum(raw) == deduped window rows: OK for all 5 N")

    print("\n%-4s | %s | %s" % ("N", "  ".join("%7s" % s for s in SEGS), "visible(1+4)"))
    for n in N_CHOICES:
        _rw, _k, _d, raw, cap2, vis = results[n]
        print("%-4d | %s | %d" % (n, "  ".join("%7d" % cap2[s] for s in SEGS), vis))

    # ---- duplicate check after window dedup --------------------------------
    print("\n-- duplicate (company, tnorm title) pairs surviving window dedup --")
    for n in N_CHOICES:
        w = win_rows(rows, day, n)
        kept, _ = dedup_keep(w, "first")
        c = Counter(dkey(r) for r in kept)
        dups = [(k, v) for k, v in c.items() if v > 1]
        print("   N=%-3d surviving duplicate keys: %d" % (n, len(dups)))

    # ---- S1: keep-first vs keep-last ---------------------------------------
    print("\n-- S1: keep-first (oldest survives) vs keep-last (newest survives) --")
    print("%-4s %8s | %-28s | %-28s | %s"
          % ("N", "dropped", "seg1 date dist KEEP-FIRST", "seg1 date dist KEEP-LAST",
             "seg drift"))
    for n in N_CHOICES:
        w = win_rows(rows, day, n)
        kf, df = dedup_keep(w, "first")
        kl, dl = dedup_keep(w, "last")
        assert len(kf) == len(kl), "dedup cardinality must not depend on keep policy"
        f1 = Counter(r["_day"] for r in kf if R.segment(r) == "1a_t3")
        l1 = Counter(r["_day"] for r in kl if R.segment(r) == "1a_t3")
        # segment drift: same key, different segment depending on which row survived
        segf = {dkey(r): R.segment(r) for r in kf}
        segl = {dkey(r): R.segment(r) for r in kl}
        drift = sum(1 for k in segf if segf[k] != segl[k])
        fmt = lambda c: ",".join("%s:%d" % (d[5:], c[d]) for d in sorted(c))
        print("%-4d %8d | %-28s | %-28s | %d" % (n, df, fmt(f1), fmt(l1), drift))

    # do any dedup groups have members whose segment disagrees? (tnorm collapses
    # case, but the entry-grade suffix regex \b(?:I|1)$ is case SENSITIVE)
    print("\n-- dedup groups whose members disagree on segment (worst case for S1) --")
    for n in N_CHOICES:
        w = win_rows(rows, day, n)
        g = defaultdict(set)
        for r in w:
            g[dkey(r)].add(R.segment(r))
        bad = {k: v for k, v in g.items() if len(v) > 1}
        print("   N=%-3d groups with >1 distinct segment: %d %s"
              % (n, len(bad), list(bad.items())[:3] if bad else ""))

    # ---- how many days actually have data at each N ------------------------
    print("\n-- window fill (how much of the requested N days actually exists) --")
    for n in N_CHOICES:
        ds = days_back(day, n)
        have = [d for d in ds if per_day.get(d)]
        print("   N=%-3d requested %2d days, %d have data (%s .. %s)"
              % (n, n, len(have), ds[0], ds[-1]))


if __name__ == "__main__":
    main()
