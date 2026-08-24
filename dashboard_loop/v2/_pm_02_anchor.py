# -*- coding: utf-8 -*-
"""PROBE 2 - which resolver judges an OLD row, and how much does it matter.

req2 5.2 gives ONE flat companies[] table with one tier/prom/w/b per company, which
silently implies ONE resolver anchored at the generation day. The alternative is
"judge each row as of its own day" (what the per-day <day>.html snapshots do today).
That choice is not written down anywhere, so measure the difference before picking.

Also measures:
  * cross-day duplicate-key rate (drives the N=30 window size estimate)
  * per-anchor-day visible rows at every N (the FLOOR of the 30-50 band)
  * monotonicity of cap2 in N
"""
from collections import Counter, defaultdict

from _pm_base import CL, DB, N_CHOICES, banner, dedup_keep, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")


def cap2_map(R, kept):
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    return {s: sum(min(2, len(v)) for v in by[s].values()) for s in SEGS}


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    day = days[-1]
    banner("PROBE 2  anchor-day choice / cross-day dup / visible floor")

    # ---- A. anchored-at-generation-day vs anchored-at-own-day --------------
    Rgen = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
    Rown = {d: CL.LaneResolver(rows, profiles, d, overrides=overrides, priority=priority)
            for d in days}
    print("A. segment(row) under resolver@%s  vs  resolver@row's own day" % day)
    tot = drift = 0
    moves = Counter()
    for r in rows:
        a, b = Rgen.segment(r), Rown[r["_day"]].segment(r)
        tot += 1
        if a != b:
            drift += 1
            moves[(b, a)] += 1
    print("   rows %d, segment differs on %d (%.2f%%)" % (tot, drift, 100.0 * drift / tot))
    for (b, a), n in moves.most_common(10):
        print("      own-day %-6s -> gen-day %-6s : %d rows" % (b, a, n))
    print("   NOTE: window_count() and therefore S5 volume depend on the anchor;")
    print("         tier/prom/kind/board do not.")

    # per-company: how many companies change lane
    cs = {CL.norm(r["company_name"]) for r in rows}
    lane_drift = [c for c in cs
                  if Rgen.company_lane(c)[0] != Rown[days[0]].company_lane(c)[0]]
    print("   companies whose lane differs between anchor %s and %s: %d / %d"
          % (day, days[0], len(lane_drift), len(cs)))

    # ---- B. cross-day duplicate keys ---------------------------------------
    print("\nB. duplicate keys that span MORE THAN ONE natural day")
    g = defaultdict(set)
    for r in rows:
        g[dkey(r)].add(r["_day"])
    multi = {k: v for k, v in g.items() if len(v) > 1}
    print("   distinct keys %d, keys seen on >1 day: %d (%.2f%%)"
          % (len(g), len(multi), 100.0 * len(multi) / max(1, len(g))))
    n_rows_in_multi = sum(1 for r in rows if len(g[dkey(r)]) > 1)
    print("   rows belonging to a cross-day key: %d / %d (%.2f%%)"
          % (n_rows_in_multi, len(rows), 100.0 * n_rows_in_multi / len(rows)))
    print("   => window dedup removes cross-day repeats; per-day dedup would NOT.")
    per_day_sum = sum(len(CL.day_rows(rows, d)) for d in days)
    whole, _ = dedup_keep(rows, "first")
    print("   sum of per-day dedup = %d   vs   whole-window dedup = %d   (delta %d)"
          % (per_day_sum, len(whole), per_day_sum - len(whole)))

    # ---- C. visible floor at every anchor day x every N --------------------
    print("\nC. default-visible rows  min(cap2,OPEN_CAP=%r) summed over (1a_t3,B1)"
          % DB.OPEN_CAP)
    print("   %-12s %s" % ("anchor day", "  ".join("N=%-3d" % n for n in N_CHOICES)))
    for d in days:
        R = CL.LaneResolver(rows, profiles, d, overrides=overrides, priority=priority)
        line = []
        prev = None
        for n in N_CHOICES:
            kept, _ = dedup_keep(win_rows(rows, d, n), "first")
            c2 = cap2_map(R, kept)
            vis = sum(min(c2[s], DB.OPEN_CAP.get(s, c2[s])) for s in ("1a_t3", "B1"))
            line.append("%-5d" % vis)
            if prev is not None:
                assert c2["1a_t3"] >= prev["1a_t3"] and c2["B1"] >= prev["B1"], \
                    "cap2 must be monotone non-decreasing in N"
            prev = c2
        print("   %-12s %s" % (d, "  ".join(line)))
    print("   cap2 monotone non-decreasing in N: OK (asserted above)")

    # ---- D. the raw ceiling proof ------------------------------------------
    print("\nD. ceiling is structural: visible = min(cap2_1,35) + min(cap2_4,12) <= 47")
    print("   the only failure mode is the FLOOR (a thin day / early morning).")
    for d in days:
        R = CL.LaneResolver(rows, profiles, d, overrides=overrides, priority=priority)
        kept, _ = dedup_keep(win_rows(rows, d, 1), "first")
        c2 = cap2_map(R, kept)
        print("   N=1 anchor %s: cap2 1a_t3=%d 1a_t2=%d B1=%d -> visible %d"
              % (d, c2["1a_t3"], c2["1a_t2"], c2["B1"],
                 min(c2["1a_t3"], 35) + min(c2["B1"], 12)))


if __name__ == "__main__":
    main()
