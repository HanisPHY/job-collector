"""
Structured per-run bookkeeping for the collector entry points.

Every scheduled run appends one line to logs/runs.jsonl. run_logged.bat writes
the run_start/run_end pair; the Python entry points write the run_summary in
between. daily_report.py reads that file and nothing else - the raw .log files
are for humans only.

Deliberately tiny: no log levels, no handlers, no event framework. The
collectors already carry structured counters (ats_direct RunStats,
ddg_search stats dict); this only persists them.
"""

import os
import json
from datetime import datetime

import paths

# logs/ sits inside the synced project tree by default. Set
# JOB_LOG_ROOT to move it elsewhere (e.g. %LOCALAPPDATA%\JobCollector\logs).
LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(paths.ROOT, "logs")
RUNS_FILE = os.path.join(LOG_ROOT, "runs.jsonl")


def current_run_id() -> str:
    """Run id shared by every process inside one run_logged.bat invocation."""
    return (os.environ.get("JOB_RUN_ID")
            or "manual-" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))


def run_summary(script: str, **metrics) -> dict:
    """
    Append one run_summary record to logs/runs.jsonl.

    Never raises: a bookkeeping failure must not take down a collection run.
    """
    record = {
        "kind": "run_summary",
        "ts": datetime.now().isoformat(timespec="seconds"),
        "script": script,
        "run_id": current_run_id(),
    }
    record.update(metrics)
    try:
        os.makedirs(LOG_ROOT, exist_ok=True)
        # One open/write/close per record. The three collectors run on
        # independent schedules and will overlap; a single short append is
        # atomic enough on Windows, and readers tolerate a torn trailing line.
        line = json.dumps(record, ensure_ascii=True) + "\n"
        with open(RUNS_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"Warning: could not write run summary: {e}")
    return record
