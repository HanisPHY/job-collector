# -*- coding: utf-8 -*-
"""Evaluator A - independent reproduction of design_v1.md's headline numbers.

Covers rubric item 1 (reproduce every key number) except the PIN_DAY drift
question (see _evalA_pinday_drift.py) and the open_plan math (see
_evalA_openplan_math.py).

Reproduces:
  [T1] 5-N window table: raw window rows, deduped rows, dropped, per-segment
       raw, cap2, first screen (uses THIS evaluator's own open_plan, not
       imported from the pm scripts)
  [T3] unique_id-is-job_link-suffix redundancy (92.4% claim)
  S1   keep-NEWEST vs keep-OLDEST: how many (group,N) differ; segment-1 date
       distribution keep-first vs keep-last; cross-group segment disagreement
  S1 trap: GLOBAL-scope x vs DAY<=anchor-scope x, dropped-row count for two
       historical anchors (10 / 28 claim)
  PROBE2-B cross-day duplicate keys (29 keys / 151 rows claim)
  PROBE2-A judgment ("segment") drift under generation-day resolver vs each
       row's own-day resolver (12/2491 claim)
  T4   section-7 (watermark interval) overlap with each N window (83/86 claim)
"""
from collections import Counter, defaultdict

from _evalA_base import (CL, DB, N_CHOICES, ROOT, SEGS, banner, cap2_of, dkey,
                          dedup_keep_newest, days_back, load, open_plan,
                          resolver, superseded_flags, win_rows)


def t1_window_table(rows, profiles, overrides, priority, anchor):
    R = resolver(rows, profiles, anchor, overrides, priority)
    print("\n[T1] window table, anchor=%s (own repro, keep-NEWEST dedup + own open_plan)"
          % anchor)
    print("%-4s %8s %8s %8s | %s | %8s %8s" %
          ("N", "rawwin", "dedup", "dropped", "  ".join("%6s" % s for s in SEGS),
           "cap2sum", "open"))
    out = {}
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        kept, dropped = dedup_keep_newest(w)
        raw = Counter(R.segment(r) for r in kept)
        assert sum(raw.values()) == len(kept), "I1 window form broken N=%d" % n
        cap2 = {s: cap2_of([r for r in kept if R.segment(r) == s]) for s in SEGS}
        plan, opened = open_plan(cap2)
        out[n] = (len(w), len(kept), dropped, raw, cap2, opened)
        print("%-4d %8d %8d %8d | %s | %8d %8d" %
              (n, len(w), len(kept), dropped,
               "  ".join("%6d" % raw.get(s, 0) for s in SEGS),
               sum(cap2.values()), opened))
        # distinct-key cardinality check
        distinct = len({dkey(r) for r in w})
        assert distinct == len(kept), "dedup cardinality mismatch N=%d" % n
    return out


def t3_unique_id_redundancy(rows):
    same = tot = 0
    for r in rows:
        uid = (r.get("unique_id") or "").strip()
        link = (r.get("job_link") or "").strip()
        tot += 1
        if uid and link.rstrip("/").endswith("/" + uid):
            same += 1
    print("\n[T3] unique_id recoverable from job_link tail: %d/%d = %.1f%%"
          % (same, tot, 100.0 * same / tot))
    return same, tot


def s1_newest_vs_oldest(rows, anchor):
    print("\n[S1] keep-NEWEST vs keep-OLDEST, anchor=%s" % anchor)
    R = resolver(rows, CL.load_profiles(), anchor, CL.load_overrides(), CL.load_priority())
    for n in N_CHOICES:
        w = win_rows(rows, anchor, n)
        newest, _ = dedup_keep_newest(w)
        # keep-OLDEST: reverse sort key
        seq = sorted(w, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""))
        seen, oldest = set(), []
        for r in seq:
            k = dkey(r)
            if k in seen:
                continue
            seen.add(k)
            oldest.append(r)
        assert len(newest) == len(oldest)
        segn = {dkey(r): R.segment(r) for r in newest}
        sego = {dkey(r): R.segment(r) for r in oldest}
        diff = sum(1 for k in segn if segn[k] != sego[k])
        # per-key survivor identity: does the SAME physical row survive both ways?
        idn = {dkey(r): id(r) for r in newest}
        ido = {dkey(r): id(r) for r in oldest}
        survivor_diff = sum(1 for k in idn if idn[k] != ido[k])
        print("   N=%-3d groups whose SEGMENT differs newest-vs-oldest: %d "
              "(survivor identity differs for %d/%d groups)"
              % (n, diff, survivor_diff, len(idn)))


def s1_scope_trap(rows, anchors):
    print("\n[S1 trap] GLOBAL-scope x  vs  (_day<=anchor)-scope x : dropped rows")
    for anchor in anchors:
        flags_global = superseded_flags(rows, max(r["_day"] for r in rows))  # scope = full corpus
        flags_scoped = superseded_flags(rows, anchor)   # scope = _day <= anchor, per design
        day_rows = [r for r in rows if r["_day"] == anchor]
        # "using the WRONG (global) x to render a view pinned/limited to `anchor`"
        wrongly_dropped = sum(1 for r in day_rows
                               if flags_global.get(id(r), 0) == 1
                               and flags_scoped.get(id(r), 0) == 0)
        print("   anchor=%s: rows on that day dropped by GLOBAL x but NOT by "
              "scoped x = %d" % (anchor, wrongly_dropped))


def probe2b_cross_day_dups(rows):
    print("\n[PROBE2-B] cross-day duplicate keys")
    g = defaultdict(set)
    for r in rows:
        g[dkey(r)].add(r["_day"])
    multi = {k: v for k, v in g.items() if len(v) > 1}
    n_rows_multi = sum(1 for r in rows if len(g[dkey(r)]) > 1)
    print("   distinct keys=%d  keys on >1 day=%d (%.2f%%)  rows in such groups=%d (%.2f%%)"
          % (len(g), len(multi), 100.0 * len(multi) / len(g),
             n_rows_multi, 100.0 * n_rows_multi / len(rows)))
    days = sorted({r["_day"] for r in rows})
    per_day_sum = sum(len(CL.day_rows(rows, d)) for d in days)
    whole = len({dkey(r) for r in rows})
    print("   sum(day_rows dedup per day)=%d  vs  whole-corpus window dedup=%d  delta=%d"
          % (per_day_sum, whole, per_day_sum - whole))


def probe2a_judgment_drift(rows, profiles, overrides, priority):
    print("\n[PROBE2-A] segment(row) under generation-day resolver vs row's own-day resolver")
    days = sorted({r["_day"] for r in rows})
    gen_day = days[-1]
    Rgen = resolver(rows, profiles, gen_day, overrides, priority)
    Rown = {d: resolver(rows, profiles, d, overrides, priority) for d in days}
    tot = drift = 0
    moves = Counter()
    for r in rows:
        a, b = Rgen.segment(r), Rown[r["_day"]].segment(r)
        tot += 1
        if a != b:
            drift += 1
            moves[(b, a)] += 1
    print("   rows=%d drift=%d (%.2f%%)" % (tot, drift, 100.0 * drift / tot))
    for (b, a), cnt in moves.most_common(10):
        print("      own-day %-6s -> gen-day %-6s : %d" % (b, a, cnt))
    cs = {CL.norm(r["company_name"]) for r in rows}
    lane_drift = [c for c in cs if Rgen.company_lane(c)[0] != Rown[days[0]].company_lane(c)[0]]
    print("   companies whose LANE differs gen-day(%s) vs earliest-day(%s): %d/%d"
          % (gen_day, days[0], len(lane_drift), len(cs)))


def t4_section7_overlap(rows, profiles, overrides, priority):
    print("\n[T4] section-7 (watermark interval) rows vs the N window")
    st = DB.read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    print("   state: cutoff=%r prev_cutoff=%r" % (pc, pp))
    day = max(r["_day"] for r in rows)
    R = resolver(rows, profiles, day, overrides, priority)
    pool = [r for r in rows if pp < (r.get("_recorded") or "") <= pc]
    ded, _ = CL.dedup_rows(pool)
    seg = Counter(R.segment(r) for r in ded)
    in124 = sum(seg[s] for s in ("1a_t3", "1a_t2", "B1"))
    print("   previous-issue interval: raw=%d dedup=%d in(1)(2)(4)=%d"
          % (len(pool), len(ded), in124))
    poolkeys = {dkey(r) for r in ded if R.segment(r) in ("1a_t3", "1a_t2", "B1")}
    for n in N_CHOICES:
        w = {dkey(r) for r in win_rows(rows, day, n)}
        inside = len(poolkeys & w)
        print("      N=%-3d in(1)(2)(4) inside window=%d  outside window=%d"
              % (n, inside, len(poolkeys) - inside))


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("EVALUATOR A - independent repro, corpus=%d rows over %s"
           % (len(rows), ",".join(days)))
    for d in days:
        print("   %s  raw=%5d  day_rows-dedup=%5d" % (d, sum(1 for r in rows if r["_day"] == d),
                                                        len(CL.day_rows(rows, d))))

    t1_window_table(rows, profiles, overrides, priority, anchor)
    t3_unique_id_redundancy(rows)
    s1_newest_vs_oldest(rows, anchor)
    s1_scope_trap(rows, days[:-1] if len(days) > 1 else days)
    probe2b_cross_day_dups(rows)
    probe2a_judgment_drift(rows, profiles, overrides, priority)
    t4_section7_overlap(rows, profiles, overrides, priority)


if __name__ == "__main__":
    main()
