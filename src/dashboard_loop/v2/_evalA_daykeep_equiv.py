# -*- coding: utf-8 -*-
"""Evaluator A - rubric item 6: is `segment_counts(day) == window_counts(day,1)`
(design_v1.md section 5, "safe" claim, 02:30 empirical check) actually an
INVARIANT, or does it happen to hold today by coincidence of the corpus?

The two functions use DIFFERENT dedup survivor policies:
  * company_lane.dedup_rows()  (used by day_rows / today's segment_counts):
      keep whichever row is encountered FIRST when the 3 CSVs are concatenated
      in SOURCE order (newgrad, then ats_direct, then ddg), each in file/row
      order. This is NOT time-based.
  * design_v1.md's window_view / `x` flag (used by the proposed window_counts):
      keep-NEWEST by `_recorded` timestamp (S1).

If, for some (company,title) dedup group within a single day, the two
policies pick a DIFFERENT physical row, the totals can still agree (both
still produce exactly one survivor per group) but WHICH row is shown, and in
the worst case WHICH SEGMENT it lands in, can differ. design_v1.md's own
_pm_01_window.py already checks this at the WHOLE-WINDOW level and finds 0
cross-segment groups; this script checks it at the SINGLE-DAY level (the
actual comparison the design's "safe" claim in section 5 rests on), across
every day in the corpus, not just the 3 spot-measured days.
"""
from collections import defaultdict

from _evalA_base import CL, banner, dkey, load


def keep_newest_by_day(rows, day):
    day_rows = [r for r in rows if r["_day"] == day]
    seq = sorted(day_rows, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""),
                 reverse=True)
    seen, out = set(), []
    for r in seq:
        k = dkey(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    banner("segment_counts(day) == window_counts(day,1): survivor-identity check per day")

    for day in days:
        R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
        src_first = CL.day_rows(rows, day)                 # today's segment_counts basis
        time_newest = keep_newest_by_day(rows, day)        # design's proposed basis

        assert len(src_first) == len(time_newest), \
            "day=%s: CARDINALITY differs: source-first=%d time-newest=%d" % (
                day, len(src_first), len(time_newest))

        by_key_src = {dkey(r): r for r in src_first}
        by_key_time = {dkey(r): r for r in time_newest}
        assert set(by_key_src) == set(by_key_time)

        survivor_diff = sum(1 for k in by_key_src if id(by_key_src[k]) != id(by_key_time[k]))
        seg_diff = 0
        examples = []
        for k in by_key_src:
            a, b = by_key_src[k], by_key_time[k]
            if id(a) == id(b):
                continue
            sa, sb = R.segment(a), R.segment(b)
            if sa != sb:
                seg_diff += 1
                examples.append((a, b, sa, sb))

        raw_src = defaultdict(int)
        raw_time = defaultdict(int)
        for r in src_first:
            raw_src[R.segment(r)] += 1
        for r in time_newest:
            raw_time[R.segment(r)] += 1
        counts_equal = all(raw_src.get(s, 0) == raw_time.get(s, 0) for s in CL.SEGMENT_ORDER)

        print("\nday=%s  rows=%-5d  dedup groups=%-5d" % (day, len(src_first), len(src_first)))
        print("   survivor differs (source-order-first vs time-newest): %d / %d groups"
              % (survivor_diff, len(by_key_src)))
        print("   of those, SEGMENT differs: %d" % seg_diff)
        print("   per-segment raw counts identical between the two policies: %s"
              % counts_equal)
        for a, b, sa, sb in examples[:5]:
            print("      SEGMENT MISMATCH: %-30s %-40s  source-first->%s  time-newest->%s"
                  % (a.get("company_name"), (a.get("job_title") or "")[:35], sa, sb))

    print("\nCONCLUSION: the F6/F7/F19 'safe to alias segment_counts(day) = window_counts"
          "(day,1)' claim")
    print("holds ONLY if survivor identity never crosses a segment boundary within a day.")
    print("If any day above shows a nonzero SEGMENT mismatch, the equivalence is an")
    print("empirical coincidence of today's corpus, not a structural invariant, and a")
    print("future day with a genuine intra-day duplicate (same company+title recorded")
    print("twice, once via newgrad.csv and once via ats_jobs.csv/ddg_jobs.csv, with")
    print("different underlying job postings) could make F6/F7/F19 and the window-based")
    print("fixtures disagree on segment 1's row set even though both report the same")
    print("total count.")


if __name__ == "__main__":
    main()
