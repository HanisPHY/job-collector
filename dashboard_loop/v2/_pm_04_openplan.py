# -*- coding: utf-8 -*-
"""PROBE 4 - the first-screen MECHANISM, section 7, the check table, render volume.

The point of this probe: OPEN_CAP 35/12 is a CEILING and it works. It is not a
FLOOR, and the floor is where the current numbers actually fail. Measured below.
"""
from collections import Counter, defaultdict

from _pm_base import CL, DB, N_CHOICES, banner, dedup_keep, dkey, load, win_rows

SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")

# ---- proposed mechanism ---------------------------------------------------
OPEN_ORDER = ["1a_t3", "B1", "1a_t2"]       # (1), (4), then (2) only as filler
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN = ("1a_t3", "B1")
FLOOR, CEIL = 30, 50


def open_plan(cap2):
    """-> ({seg: rows_expanded}, total). Pure function of the cap2 counts.

    ceiling: min(cap2,SEG_OPEN_CAP) on the two always-open segments  -> <= 47
    floor:   segment (2) opens ONLY far enough to reach FLOOR         -> >= min(FLOOR, supply)
    """
    plan, used = {}, 0
    for s in ALWAYS_OPEN:
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s])
        used += plan[s]
    for s in OPEN_ORDER:
        if s in ALWAYS_OPEN or used >= FLOOR:
            continue
        plan[s] = min(cap2.get(s, 0), SEG_OPEN_CAP[s], FLOOR - used)
        used += plan[s]
    return plan, used


def cap2_map(R, kept, cap=2):
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    return {s: sum(min(cap, len(v)) for v in by[s].values()) for s in SEGS}


def main():
    rows, profiles, overrides, priority = load()
    days = sorted({r["_day"] for r in rows})
    day = days[-1]
    banner("PROBE 4  first-screen mechanism / section 7 / check / render volume")

    print("A. current OPEN_CAP=%r (ceiling only) vs proposed plan (ceiling+floor)"
          % DB.OPEN_CAP)
    print("   %-12s %-4s | %-22s | %s" % ("anchor", "N", "now: min(cap2,OPEN_CAP)",
                                          "proposed open_plan"))
    worst_now = worst_new = 10 ** 9
    best_new = 0
    for d in days:
        R = CL.LaneResolver(rows, profiles, d, overrides=overrides, priority=priority)
        for n in N_CHOICES:
            kept = [r for r in win_rows(rows, d, n) if not _superseded(rows, r)]
            c2 = cap2_map(R, kept)
            now = sum(min(c2[s], DB.OPEN_CAP.get(s, c2[s])) for s in ALWAYS_OPEN)
            plan, tot = open_plan(c2)
            supply = sum(c2[s] for s in OPEN_ORDER)
            worst_now = min(worst_now, now)
            worst_new = min(worst_new, tot)
            best_new = max(best_new, tot)
            assert tot <= CEIL, "ceiling broken"
            assert tot >= min(FLOOR, supply), "floor broken"
            print("   %-12s %-4d | %-22d | %-4d %s (supply %d)"
                  % (d, n, now, tot,
                     " ".join("%s=%d" % (s, plan[s]) for s in OPEN_ORDER if plan.get(s)),
                     supply))
    print("   worst first screen  now=%d  proposed=%d ; best proposed=%d"
          % (worst_now, worst_new, best_new))
    print("   INVARIANT (never goes stale): min(FLOOR, supply) <= visible <= 47")

    # ---- B. section 7 under the real watermark ----------------------------
    print("\nB. section 7 (last issue's unhandled) under the shipped watermark")
    st = DB.read_state()
    pc, pp = st.get("cutoff") or "", st.get("prev_cutoff") or ""
    print("   logs/last_report.json cutoff=%r prev_cutoff=%r" % (pc, pp))
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
    for lo, hi, label in ((pp, pc, "previous issue interval"),
                          (pc, "9999", "since the current cutoff")):
        pool = [r for r in rows if lo < (r.get("_recorded") or "") <= hi]
        ded = CL.dedup_rows(pool)[0]
        seg = Counter(R.segment(r) for r in ded)
        in124 = sum(seg[s] for s in ("1a_t3", "1a_t2", "B1"))
        print("   %-26s raw %5d  dedup %5d  in (1)(2)(4) %4d  days %s"
              % (label, len(pool), len(ded), in124,
                 ",".join(sorted({r["_day"] for r in pool})) or "-"))
    # overlap of section 7 with each N window
    print("   overlap of the section-7 pool with the N window:")
    pool = {dkey(r) for r in rows if pp < (r.get("_recorded") or "") <= pc}
    for n in N_CHOICES:
        w = {dkey(r) for r in win_rows(rows, day, n)}
        print("      N=%-3d section-7 keys %4d, of which inside the window %4d (%.0f%%)"
              % (n, len(pool), len(pool & w),
                 100.0 * len(pool & w) / max(1, len(pool))))

    # ---- C. check table size ----------------------------------------------
    print("\nC. size of a per-N check table (5 N x 6 segments x raw/cap2/checksum)")
    import json
    check = {}
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, day, n) if not _superseded(rows, r)]
        c2 = cap2_map(R, kept)
        raw = Counter(R.segment(r) for r in kept)
        plan, tot = open_plan(c2)
        check[str(n)] = {"dedup": len(kept), "open": tot,
                         "raw": {s: raw.get(s, 0) for s in SEGS},
                         "cap2": c2, "plan": plan}
    js = json.dumps(check, ensure_ascii=False, separators=(",", ":"))
    print("   %d bytes total for all 5 N" % len(js.encode("utf-8")))
    print("   sample N=7 -> %s" % json.dumps(check["7"], ensure_ascii=False,
                                             separators=(",", ":"))[:200])

    # ---- D. render volume --------------------------------------------------
    print("\nD. how many <tr> a full eager render would build")
    for n in N_CHOICES:
        kept = [r for r in win_rows(rows, day, n) if not _superseded(rows, r)]
        c2 = cap2_map(R, kept)
        plan, tot = open_plan(c2)
        print("   N=%-3d dedup %5d  cap2-heads %5d  open-on-load %3d  (lazy saves %5d rows)"
              % (n, len(kept), sum(c2.values()), tot, len(kept) - tot))
    print("   projection at 2000 rows/day: N=30 dedup ~%d rows; eager render is not an option"
          % (2000 * 30 * len(kept) / max(1, len(win_rows(rows, day, 30)))))

    # ---- E. unique_id redundancy ------------------------------------------
    print("\nE. is unique_id recoverable from job_link (i.e. dead weight in the payload)?")
    same = tot_n = 0
    for r in rows:
        uid = (r.get("unique_id") or "").strip()
        link = (r.get("job_link") or "").strip()
        tot_n += 1
        if uid and link.rstrip("/").endswith("/" + uid):
            same += 1
    print("   %d / %d rows have unique_id as the last path segment of job_link (%.1f%%)"
          % (same, tot_n, 100.0 * same / tot_n))


_SUP = None


def _superseded(rows, r):
    """keep-NEWEST dedup as a frozen per-row flag (see PROBE 3 section A)."""
    global _SUP
    if _SUP is None:
        grp = defaultdict(list)
        for x in rows:
            grp[dkey(x)].append(x)
        _SUP = set()
        for k, g in grp.items():
            g.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
            for x in g[:-1]:
                _SUP.add(id(x))
    return id(r) in _SUP


if __name__ == "__main__":
    main()
