# -*- coding: utf-8 -*-
"""Round-2 shared helpers. Same loader as _pm_base, plus the CORRECTED open_plan
contract (evaluator A issue A2) and the single dedup rule (A3).

    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_pm2_XX.py
"""
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import paths

ROOT = paths.ROOT

sys.path.insert(0, str(paths.ROOT / "scripts"))

import company_lane as CL      # noqa: E402
import dashboard as DB         # noqa: E402

N_CHOICES = (1, 3, 7, 14, 30)
N_DEFAULT = 3
SEGS = ("1a_t3", "1a_t2", "1b", "B1", "B2", "C")

CAP = 2
OPEN_ORDER = ("1a_t3", "B1", "1a_t2")     # (1) -> (4) -> (2) as filler only
ALWAYS_OPEN = ("1a_t3", "B1")
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
FLOOR = 30
CEIL = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)      # 47, derived


def open_plan(cap2):
    """Unchanged from v1. What changes in v2 is the CONTRACT it is measured against."""
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


def openable(cap2):
    """A2 fix: what the three openable segments can ACTUALLY contribute, each under
    its own ceiling. v1 wrongly used the untruncated sum."""
    return sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in OPEN_ORDER)


def open_expected(cap2):
    """Closed form of open_plan's total. The fixture asserts equality against this,
    so there is no hand-written bound to get wrong."""
    base = sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in ALWAYS_OPEN)
    filler = sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s])
                 for s in OPEN_ORDER if s not in ALWAYS_OPEN)
    return max(base, min(base + filler, FLOOR))


def load():
    rows = CL.load_rows(str(paths.DATA_DIR))
    return rows, CL.load_profiles(), CL.load_overrides(), CL.load_priority()


def days_back(day, n):
    d0 = datetime.strptime(day, "%Y-%m-%d")
    return [(d0 - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def win_rows(rows, day, n):
    ds = days_back(day, n)
    lo, hi = ds[0], ds[-1]
    return [r for r in rows if lo <= r["_day"] <= hi]


def dkey(r):
    return CL.norm(r.get("company_name")) + chr(0) + CL.tnorm(r.get("job_title"))


def superseded(rows, anchor):
    """THE dedup rule (there is only one in v2): keep the newest row of each
    (company, normalised title) group, scoped to _day <= anchor."""
    g = defaultdict(list)
    for r in rows:
        if r["_day"] <= anchor:
            g[dkey(r)].append(r)
    out = set()
    for v in g.values():
        v.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        out.update(id(z) for z in v[:-1])
    return out


def cap2_map(R, kept):
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    return {s: sum(min(CAP, len(v)) for v in by[s].values()) for s in SEGS}


def first_screen_keys(R, kept):
    """The rows open_plan actually puts on the first screen, in render order."""
    by = defaultdict(lambda: defaultdict(list))
    for r in kept:
        by[R.segment(r)][CL.norm(r["company_name"])].append(r)
    cap2 = {s: sum(min(CAP, len(v)) for v in by[s].values()) for s in SEGS}
    plan, _tot = open_plan(cap2)
    out = []
    for s in OPEN_ORDER:
        n = plan.get(s, 0)
        if not n:
            continue
        groups = sorted(by[s].items(), key=lambda kv: R.sort_key(kv[0]))
        head = []
        for c, rs in groups:
            rs = sorted(rs, key=lambda r: ((r.get("_recorded") or ""),
                                           r.get("job_title") or ""), reverse=True)
            head.extend((c, r) for r in rs[:CAP])
        out.extend((s, c, r) for c, r in head[:n])
    return out


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def banner(t):
    print("=" * 78)
    print("%s   [measured %s local]" % (t, stamp()))
    print("=" * 78)
