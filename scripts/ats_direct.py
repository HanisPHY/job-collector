"""
ATS-direct new-grad SDE job collector - CLI entry point.

Collection path #2 (parallel to the LinkedIn/jobspy pipeline in main.py).
Pulls jobs straight from company ATS APIs (Greenhouse, Lever, Ashby,
SmartRecruiters, Workable, Workday, ...) - no search engine involved.

Usage:
    python ats_direct.py --probe            # resolve seed companies (one-time)
    python ats_direct.py                    # collect from resolved registry
    python ats_direct.py --loose            # keep any non-senior SDE title
    python ats_direct.py --add-company "Name:platform:slug"
    python ats_direct.py --max-companies 10 # smoke test on a subset
"""

import argparse
import sys
import io
import time
import traceback

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import paths
import run_log
from ats_direct.registry import Registry
from ats_direct.collector import collect
from ats_direct.rate_limiter import make_default_limiter
from ats_direct.seed_companies import PRE_RESOLVED, PROBE_NAMES


def seed_and_probe(registry_path: str, probe: bool):
    registry = Registry(registry_path)
    added = sum(registry.add(dict(e)) for e in PRE_RESOLVED)
    if added:
        print(f"Seeded {added} pre-resolved companies")
    if probe:
        limiter = make_default_limiter()
        todo = [n for n in PROBE_NAMES if not registry.has_company(n)]
        print(f"Probing {len(todo)} companies (rate-limited, ~1 req/s)...")
        for name in todo:
            registry.probe_company(name, limiter)
            registry.save()  # save incrementally so an interrupt loses nothing
    registry.save()
    resolved = registry.resolved()
    print(f"Registry: {len(resolved)} resolved / {len(registry.companies)} total")
    return registry


def main():
    parser = argparse.ArgumentParser(description="Collect NG SDE jobs directly from ATS APIs")
    parser.add_argument("--registry", default=str(paths.STATE_DIR / "ats_registry.json"))
    parser.add_argument("--output", default=str(paths.DATA_DIR / "ats_jobs.csv"))
    parser.add_argument("--probe", action="store_true",
                        help="Auto-detect platforms for seed companies (one-time)")
    parser.add_argument("--cleanup", action="store_true",
                        help="Re-validate resolved entries, drop/re-probe empty boards")
    parser.add_argument("--expand", action="store_true",
                        help="Harvest new companies from community NG GitHub lists")
    parser.add_argument("--loose", action="store_true",
                        help="Keep any non-senior SDE title, not just explicit NG titles")
    parser.add_argument("--all-locations", action="store_true",
                        help="Also keep clearly non-US postings (US-only is the default)")
    parser.add_argument("--max-companies", type=int, default=None)
    parser.add_argument("--add-company", type=str, default=None,
                        metavar="NAME:PLATFORM:SLUG",
                        help='e.g. "Acme:greenhouse:acme"')
    parser.add_argument("--no-collect", action="store_true",
                        help="Only seed/probe the registry, skip collection")
    args = parser.parse_args()

    # Collected as we go and emitted exactly once in the finally block, so
    # every exit path - including --add-company / --no-collect and crashes -
    # leaves a record in logs/runs.jsonl. A missing record means "the script
    # never ran", and daily_report.py alerts on that.
    metrics = {"exit_code": 0, "output": args.output, "started": time.time()}
    try:
        if args.add_company:
            metrics["mode"] = "add_company"
            try:
                name, platform, slug = args.add_company.split(":")
            except ValueError:
                parser.error("--add-company expects NAME:PLATFORM:SLUG")
            registry = Registry(args.registry)
            if registry.add({"name": name, "platform": platform, "slug": slug,
                             "source": "manual"}):
                registry.save()
                print(f"Added {name} -> {platform}/{slug}")
            else:
                print(f"{name} already in registry")
            return

        seed_and_probe(args.registry, probe=args.probe)

        if args.cleanup:
            registry = Registry(args.registry)
            limiter = make_default_limiter()
            print("\nRe-validating resolved entries...")
            cstats = registry.cleanup(limiter)
            print(f"cleanup: checked={cstats['checked']} dropped={cstats['dropped']} "
                  f"recovered={cstats['recovered']}")
            metrics.update(cstats)  # checked/dropped/recovered

        if args.expand:
            from ats_direct.expand_registry import expand
            print("\nExpanding registry from community NG lists...")
            estats = expand(args.registry)
            print(f"expand: sources_ok={estats['sources_ok']} "
                  f"unique_boards={estats['unique_boards']} added={estats['added']}")
            metrics.update(estats)  # sources_ok/unique_boards/added

        if args.no_collect:
            metrics["mode"] = "no_collect"
            return

        print(f"\n{'=' * 60}\nCollecting NG SDE jobs from ATS "
              f"({'loose' if args.loose else 'strict'} mode)\n{'=' * 60}")
        stats = collect(registry_path=args.registry, output_file=args.output,
                        strict=not args.loose, us_only=not args.all_locations,
                        max_companies=args.max_companies)

        s = stats.summary()
        # keys are disjoint from cleanup/expand stats; elapsed_s is renamed so
        # it doesn't collide with the whole-run timing added in `finally`
        metrics.update(s)
        metrics["collect_elapsed_s"] = metrics.pop("elapsed_s")
        print(f"\n{'=' * 60}\nRun metrics\n{'=' * 60}")
        for k, v in s.items():
            print(f"  {k:<22} {v}")
        print(f"\nResults appended to {args.output}")
    except BaseException as e:
        metrics["exit_code"] = 1
        metrics["error"] = type(e).__name__
        metrics["error_message"] = str(e)[:500]
        metrics["traceback"] = "".join(traceback.format_exc()).strip()[-2000:]
        raise
    finally:
        metrics["elapsed_s"] = round(time.time() - metrics.pop("started"), 1)
        run_log.run_summary("ats_direct", **metrics)


if __name__ == "__main__":
    main()
