# -*- coding: utf-8 -*-
"""Round-2 shared helpers for Evaluator A's own independent probes of design_v2.md.

Deliberately independent of dashboard_loop/v2/_pm2_*.py (the PM's own scripts):
this evaluator re-derives the numbers from company_lane.py directly so a mistake
in the PM's harness would not silently survive into the review. Reuses the
round-1 _evalA_base.py loader (this evaluator's own prior work, not the PM's).

Run with:
    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalA2_XX.py
"""
from collections import Counter, defaultdict

from _evalA_base import (CL, DB, N_CHOICES, ROOT, SEGS, banner, cap2_of, dkey,
                          load, resolver, stamp, win_rows)

# ---- design_v2.md 3.4 / 3.11 corrected open_plan contract -------------------
OPEN_ORDER = ("1a_t3", "B1", "1a_t2")
ALWAYS_OPEN = ("1a_t3", "B1")
SEG_OPEN_CAP = {"1a_t3": 35, "B1": 12, "1a_t2": 30}
FLOOR = 30
CEIL = sum(SEG_OPEN_CAP[s] for s in ALWAYS_OPEN)   # 47


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


def openable(cap2):
    """v2's fix for A2: capped contribution, not raw cap2 sum."""
    return sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in OPEN_ORDER)


def open_expected(cap2):
    base = sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in ALWAYS_OPEN)
    filler = sum(min(cap2.get(s, 0), SEG_OPEN_CAP[s]) for s in OPEN_ORDER
                 if s not in ALWAYS_OPEN)
    return max(base, min(base + filler, FLOOR))


# ---- design_v2.md 3.3: the ONE dedup rule -----------------------------------
def superseded_ids(rows, anchor):
    """id() set of rows that are NOT the keep-newest survivor of their
    (company,title) group, scoped to _day <= anchor (design_v2.md 3.3)."""
    g = defaultdict(list)
    for r in rows:
        if r["_day"] <= anchor:
            g[dkey(r)].append(r)
    out = set()
    for v in g.values():
        v.sort(key=lambda z: ((z.get("_recorded") or ""), z.get("unique_id") or ""))
        out.update(id(z) for z in v[:-1])
    return out


def bar_counts(rows, anchor):
    """design_v2.md 3.3 A3-fix: trend bar(d) = window survivors attributed to day d,
    under the ONE dedup rule, scoped to this anchor. N-independent by construction
    (doesn't take N as a parameter at all)."""
    sup = superseded_ids(rows, anchor)
    return Counter(r["_day"] for r in rows if r["_day"] <= anchor and id(r) not in sup)


# ---- design_v2.md 3.6: the three watermark-derived views --------------------
def view_pred(view, prev_prev, prev_cutoff):
    if view == "all":
        return lambda rec: True
    if view == "new":
        return lambda rec: rec > prev_cutoff
    if view == "wm":
        return lambda rec: prev_prev < rec <= prev_cutoff
    raise ValueError(view)
