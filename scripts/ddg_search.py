"""
DuckDuckGo-search new-grad SDE job collector - CLI entry point.

Collection path #3 (parallel to main.py / ats_direct.py). Supplementary
DISCOVERY source: finds ATS-hosted NG postings via DDG X-ray queries and can
feed newly-discovered company boards into the ATS registry.

DDG throttles aggressively (see ddg_search/RATE_LIMITS.md) so each run makes
only a handful of queries, ~25s apart. Schedule it infrequently (a few times
a day at most) - NOT hourly.

Usage:
    python ddg_search.py                       # 5 queries, write ddg_jobs.csv
    python ddg_search.py --queries 3
    python ddg_search.py --update-registry     # also grow ats_registry.json
    python ddg_search.py --loose               # keep any non-senior SDE title
"""

import argparse
import sys
import io
import time
import traceback

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import os

import paths
import run_log

sys.path = [p for p in sys.path if p != os.path.dirname(os.path.abspath(__file__))]
from ddg_search.collector import collect


def main():
    parser = argparse.ArgumentParser(description="Discover NG SDE jobs via DuckDuckGo X-ray search")
    parser.add_argument("--output", default=str(paths.DATA_DIR / "ddg_jobs.csv"))
    parser.add_argument("--queries", type=int, default=5,
                        help="Queries this run (cap 10; each takes ~25s)")
    parser.add_argument("--loose", action="store_true",
                        help="Keep any non-senior SDE title")
    parser.add_argument("--update-registry", action="store_true",
                        help="Add discovered company boards to ats_registry.json")
    args = parser.parse_args()

    # Emitted exactly once in `finally` so a crash still leaves a record in
    # logs/runs.jsonl - a missing record means "the script never ran".
    metrics = {"exit_code": 0, "output": args.output, "started": time.time()}
    try:
        print(f"{'=' * 60}\nDDG X-ray search ({args.queries} queries, ~25s apart)\n{'=' * 60}")
        stats = collect(output_file=args.output,
                        queries_per_run=args.queries,
                        strict=not args.loose,
                        update_registry=args.update_registry)
        metrics.update(stats)

        print(f"\n{'=' * 60}\nRun metrics\n{'=' * 60}")
        for k, v in stats.items():
            print(f"  {k:<20} {v}")
        print(f"\nResults appended to {args.output}")
    except BaseException as e:
        metrics["exit_code"] = 1
        metrics["error"] = type(e).__name__
        metrics["error_message"] = str(e)[:500]
        metrics["traceback"] = "".join(traceback.format_exc()).strip()[-2000:]
        raise
    finally:
        metrics["elapsed_s"] = round(time.time() - metrics.pop("started"), 1)
        run_log.run_summary("ddg_search", **metrics)


if __name__ == "__main__":
    main()
