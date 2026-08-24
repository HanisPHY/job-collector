# -*- coding: utf-8 -*-
"""Shared loader for the pm-design probes of dashboard v2.

Run everything with:
    export PYTHONIOENCODING=utf-8
    D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_pm_XX.py

Nothing here writes to the repo. It only imports the shipped decision layer
(company_lane) and the shipped render layer (dashboard) read-only.
"""
import sys
from datetime import datetime, timedelta

import paths

sys.path.insert(0, str(paths.ROOT / "scripts"))

import company_lane as CL      # noqa: E402
import dashboard as DB         # noqa: E402

N_CHOICES = [1, 3, 7, 14, 30]


def load():
    rows = CL.load_rows(str(paths.DATA_DIR))
    return (rows, CL.load_profiles(), CL.load_overrides(), CL.load_priority())


def days_back(day, n):
    """The n natural days ending at `day`, oldest first (includes empty days)."""
    d0 = datetime.strptime(day, "%Y-%m-%d")
    return [(d0 - timedelta(days=n - 1 - i)).strftime("%Y-%m-%d") for i in range(n)]


def win_rows(rows, day, n):
    """Raw rows (no dedup) whose _day falls in the n-day view window ending at day."""
    ds = days_back(day, n)
    lo, hi = ds[0], ds[-1]
    return [r for r in rows if lo <= r["_day"] <= hi]


def dkey(r):
    return CL.norm(r.get("company_name")) + "\x00" + CL.tnorm(r.get("job_title"))


def dedup_keep(rows, keep="first"):
    """Window dedup by (norm company, tnorm title).

    keep="first"  -> the OLDEST row of the group survives (rows fed day-ascending)
    keep="last"   -> the NEWEST row of the group survives
    Returns (kept_rows_in_input_order, dropped_count).
    """
    seq = sorted(rows, key=lambda r: (r.get("_recorded") or "", r.get("unique_id") or ""))
    if keep == "last":
        seq = list(reversed(seq))
    seen, out = set(), []
    for r in seq:
        k = dkey(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out, len(rows) - len(out)


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def banner(title, rows=None):
    print("=" * 78)
    print("%s   [measured %s local]" % (title, stamp()))
    print("=" * 78)
