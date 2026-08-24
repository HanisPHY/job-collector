# -*- coding: utf-8 -*-
"""Shared loader for Evaluator A's own independent probes of design_v1.md.

Independent of dashboard_loop/v2/_pm_*.py on purpose (those are the PM's own
scripts; this evaluator does not just re-run them, it re-derives the same
numbers from company_lane.py / dashboard.py directly so a mistake in the PM's
harness would not silently survive into the review).

Run with:
    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalA_XX.py
"""
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import paths

ROOT = paths.ROOT

sys.path.insert(0, str(paths.ROOT / "scripts"))

import company_lane as CL      # noqa: E402
import dashboard as DB         # noqa: E402

N_CHOICES = [1, 3, 7, 14, 30]
SEGS = tuple(CL.SEGMENT_ORDER)   # ("1a_t3","1a_t2","1b","B1","B2","C")

# design_v1.md section 3 S2 / section 4.5 mechanism, transcribed from the design
# doc's own pseudocode (section 3, "S2 首屏 30-50 的机制"). Reproduced here
# independently rather than imported, since design_v1.md is prose/markdown, not
# an importable module -- this IS the reference implementation under review.
OPEN_ORDER = ["1a_t3", "B1", "1a_t2"]
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
ALWAYS_OPEN = ("1a_t3", "B1")
FLOOR = 30
CEIL = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)   # 47, derived, per design_v1 4.5


def open_plan(cap2):
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


def load():
    rows = CL.load_rows(str(paths.DATA_DIR))
    return rows, CL.load_profiles(), CL.load_overrides(), CL.load_priority()


def days_back(day, n):
    """n natural days ending at `day`, oldest first (includes empty days)."""
    d0 = datetime.strptime(day, "%Y-%m-%d")
    return [(d0 - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def win_rows(rows, day, n):
    ds = days_back(day, n)
    lo, hi = ds[0], ds[-1]
    return [r for r in rows if lo <= r["_day"] <= hi]


def dkey(r):
    return CL.norm(r.get("company_name")) + "\x00" + CL.tnorm(r.get("job_title"))


def dedup_keep_newest(rows):
    """Design's keep-NEWEST window dedup: newest _recorded (tie: unique_id) wins.

    Returns (kept_rows, dropped_count). This is what design_v1.md 5.3/S1 proposes
    to freeze into a per-row bit `x` (x=1 for the loser of its dedup group).
    """
    seq = sorted(rows, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""),
                 reverse=True)   # newest first
    seen, out = set(), []
    for r in seq:
        k = dkey(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out, len(rows) - len(out)


def superseded_flags(rows, scope_day):
    """design_v1.md S1: x[i]=1 iff row i is NOT the keep-NEWEST survivor of its
    dedup group, computed ONLY over rows with _day <= scope_day (never look into
    the future). Returns {id(row): 0/1} for every row in `rows` whose _day <=
    scope_day; rows with _day > scope_day are not covered by the returned dict.
    """
    pool = [r for r in rows if r["_day"] <= scope_day]
    grp = defaultdict(list)
    for r in pool:
        grp[dkey(r)].append(r)
    flags = {}
    for k, g in grp.items():
        g.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        for z in g[:-1]:
            flags[id(z)] = 1
        flags[id(g[-1])] = 0
    return flags


def resolver(rows, profiles, day, overrides=None, priority=None):
    return CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)


def cap2_of(rows_for_seg, cap=2):
    by = defaultdict(list)
    for r in rows_for_seg:
        by[CL.norm(r["company_name"])].append(r)
    return sum(min(cap, len(v)) for v in by.values())


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def banner(title):
    print("=" * 78)
    print("%s   [measured %s local]" % (title, stamp()))
    print("=" * 78)
