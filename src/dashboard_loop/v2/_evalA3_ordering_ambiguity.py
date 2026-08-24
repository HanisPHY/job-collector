# -*- coding: utf-8 -*-
"""Round 3 - independent scrutiny of design_v3.md 3.10's checksum SEQUENCE
DEFINITION (the exact thing the round-3 prompt asks this evaluator to check "by
hand", not just by re-running the PM's own harness).

design_v3.md 3.5 (untouched since v2, still authoritative) says:
    "同公司内按 `(_recorded 降序, 标题)`"
    -- _recorded is the FULL "YYYY-MM-DD HH:MM" string from the CSV, which sorts
       correctly across day boundaries (lexicographic == chronological here).

design_v3.md 3.10 (NEW this round, defines the checksum's input sequence) says:
    "组内按 `(r 降序, 标题 降序)`，最后再以 `(天下标, 行下标)` 降序做确定性 tie-break"
    -- but `r` is explicitly defined in 3.2 as "HH*100+MM ... 配合 d 才是完整时间戳"
       i.e. `r` ALONE has no day information. Comparing `r` across rows from
       DIFFERENT calendar days is comparing time-of-day only, not chronological
       order, and design 3.10 only brings `(day, row)` in as a TIE-break (for
       identical r AND identical title), not as part of the primary key.

If an Engineer implements 3.10 literally (sort by the stored `r` field, day
brought in only to break literal ties), row order - and therefore which 2 rows
land in cap2 "head" vs "+N more" overflow for CAP=2 - would be WRONG for any
company whose surviving rows span more than one calendar day. This script
checks how often that actually happens on the real corpus, and whether it
would go unnoticed.
"""
from collections import defaultdict

from _evalA_base import CL, banner, load, resolver, win_rows
from _evalA2_base import superseded_ids


def r_int(rec):
    """The stored payload field: HH*100+MM, no day. '' if rec is empty/short."""
    hhmm = (rec or "")[11:16].replace(":", "")
    return int(hhmm) if hhmm else -1


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    anchor = days[-1]
    banner("3.10 order-key ambiguity: r-alone (literal 3.10 text) vs full "
           "_recorded (3.5's rule, and what the checksum test harness actually uses)")

    R = resolver(rows, profiles, anchor, overrides, priority)
    sup = superseded_ids(rows, anchor)

    for n in (3, 7, 30):
        w = win_rows(rows, anchor, n)
        kept = [r for r in w if id(r) not in sup]
        by = defaultdict(lambda: defaultdict(list))
        for r in kept:
            by[R.segment(r)][CL.norm(r["company_name"])].append(r)

        multi_day_groups = 0
        head_diverges = 0
        seg_examples = defaultdict(list)
        for seg, comp in by.items():
            for c, rs in comp.items():
                if len({r["_day"] for r in rs}) < 2:
                    continue
                multi_day_groups += 1
                correct = sorted(rs, key=lambda r: ((r.get("_recorded") or ""),
                                                     r.get("job_title") or ""),
                                  reverse=True)
                naive = sorted(rs, key=lambda r: (r_int(r.get("_recorded")),
                                                   r.get("job_title") or ""),
                                reverse=True)
                if [id(x) for x in correct[:2]] != [id(x) for x in naive[:2]]:
                    head_diverges += 1
                    if len(seg_examples[seg]) < 2:
                        seg_examples[seg].append(
                            (c, [(x["_day"], x.get("_recorded")) for x in rs]))

        print("\nN=%-3d multi-day company groups: %-4d  CAP=2 head selection "
              "differs (r-only vs full-timestamp order): %d (%.1f%%)"
              % (n, multi_day_groups, head_diverges,
                 100.0 * head_diverges / max(1, multi_day_groups)))
        for seg, exs in seg_examples.items():
            for c, rs_info in exs:
                print("   seg=%-6s company=%-30s rows(day,recorded)=%s" % (seg, c, rs_info))

    print("\nCONSEQUENCE: design_v3.md 3.10's own sentence uses the payload field name")
    print("`r` (defined in 3.2 as day-less HH*100+MM), not `_recorded` (3.5's field,")
    print("which is day-aware). If view.py's window_view / the JS renderer follow 3.10")
    print("literally on BOTH sides (Python producing hsum from an r-only sort AND JS")
    print("rendering with an r-only comparator), the two would still MATCH each other")
    print("(same wrong order on both sides) -- the checksum mechanism (A6) would stay")
    print("GREEN while segment order / which rows count as cap2-head is silently wrong")
    print("for the majority of multi-day company groups. This is a real risk BECAUSE")
    print("the checksum's job is to prove Python and JS agree with EACH OTHER, not that")
    print("either of them agrees with the intended (chronological) order.")
    print("If instead Python's view.py keeps sorting by the full _recorded string (per")
    print("3.5, unmodified) while a JS author follows 3.10's literal wording (payload")
    print("only has `r`, not `_recorded`), Python and JS would disagree on order for")
    print("~85-90%% of multi-day groups and EVERY page load would show a permanent red")
    print("banner -- a loud failure, not silent, but still a spec-clarity defect that")
    print("would cost real implementation time to track down.")


if __name__ == "__main__":
    main()
