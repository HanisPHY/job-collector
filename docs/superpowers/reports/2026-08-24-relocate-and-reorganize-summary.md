# Relocate + Reorganize: Summary Report

**Before:** `54bc6672002f1de7306eb83fbda8605c4ba0ed09` (project at `D:\OneDrive\work\school\project\Job`, ~50 loose files at root)
**Latest:** `d86a45dbbf702684d5c1cc9defe3c6e96b7842c7` (project at `D:\Dev\job-collector`, reorganized,
final-review findings fixed) — 18 commits

Plan: `docs/superpowers/plans/2026-08-23-relocate-and-reorganize.md`
Spec: `docs/superpowers/specs/2026-08-23-relocate-and-reorganize-design.md`
SDD ledger: `.superpowers/sdd/2026-08-23-relocate-and-reorganize/progress.md`

## Commit range

```
d86a45d Fix the reorg's final-review findings and the stale docs they missed
1c4f13c Data from the reorg's end-to-end smoke test run (Task 12)
d0f97d9 Fix remaining test_lane.py path/fixture regressions from the reorg
2d67b2c Scope the scripts/ sys.path strip with try/finally instead of a permanent removal
e04a837 Repoint tests/ imports at scripts/ and paths.py after the reorg
8dc00d9 Move Scheduled Task launchers into tasks/, fix cd and script/data paths
6a28477 Move deprecated job_collector.py entry point into deprecated/
36a75ad Fix import-shadow when scripts/ entry points import job_collector directly
7f9743e Move entry scripts into scripts/, default their paths off paths.py
775a67d Move data/config/state files into data/, config/, state/
30d1bb2 Fix load_rows() calls to use paths.DATA_DIR instead of paths.ROOT
8f8fa9f Fix ROOT path computation in dashboard_loop/v2 base files
a254c9a Delete finished dashboard_loop experiment artifacts, move v2/ into src/
2304ecc Move job_collector package into src/, default its paths off paths.py
b9cf28b Fix Task 4: revert wrapper script renames and fix sys.path calculation for new location
4602964 Move ddg_search package into src/, default its paths off paths.py
e15e6f1 Move ats_direct package into src/, default its paths off paths.py
9ca792c Add src/paths.py and pyproject.toml for the reorg's editable install
```

## What changed

- **New layout:** packages moved into `src/` (`job_collector/`, `ats_direct/`, `ddg_search/`, `dashboard_loop/v2/`), CLI entry points into `scripts/`, Scheduled Task launchers into `tasks/`, data files split into `data/`/`config/`/`state/`, one legacy entry point into `deprecated/`.
- **New `src/paths.py` + `pyproject.toml`:** single source of truth for where data/config/state live, installed editable (`pip install -e .`) so imports resolve regardless of working directory — replaced ~50 scattered hardcoded paths.
- **Physical move:** the whole project relocated from OneDrive to `D:\Dev\job-collector` via `robocopy /MOVE`. Copy succeeded fully and is verified; deleting the OneDrive source failed twice due to a file lock (OneDrive's sync service) — the user chose to delete it themselves via Explorer, so it may still exist at the old path.
- **13 Windows Scheduled Tasks** repointed at the new location, verified, and resumed — confirmed via a real live run (`ng job collector`, exit 0, all 9 queries completed, logged correctly in `logs/runs.jsonl`).
- **Tests:** full suite (89 tests) is green — 86 pass, 3 skip, 0 fail, 0 error.
- **Live smoke test (Task 12):** every collector (ATS, DDG, LinkedIn/newgrad, enrich_companies, daily_report, dashboard) run for real against live external services from the new location, all passed.

## Final-review findings — all five fixed

A final whole-branch review (dispatched on the most capable model, covering the
full 17-commit diff) found 4 Important issues and 1 bundled Minor. None affected
the live production path, which was already confirmed running correctly. **All
five are now fixed.** Items 1–3 had been applied in the working tree but never
committed; items 4–5, plus the documentation the fix brief explicitly scoped out,
landed in `d86a45d`.

1. ✅ **`src/dashboard_loop/v2/` — broken `ROOT` re-export.** An earlier task
   replaced `ROOT = os.path.dirname(...)` with `import paths` in three base
   modules (`_evalA_base.py`, `_pm2_base.py`, `_pm_base.py`) without noticing
   that other files in the same directory do `from _evalA_base import (..., ROOT,
   ...)`. Fixed by re-exporting `ROOT = paths.ROOT` from each base, plus the
   `dashboard.py` path in `_pm3_02_docfacts.py:50` that the move invalidated.
   Verified: all six modules (3 bases + 3 importers) import cleanly, `ROOT`
   resolves to `WindowsPath('D:/Dev/job-collector')`, and every consumer uses it
   through `os.walk` / `os.path.join` / `relpath`, all of which accept a `Path`.
2. ✅ **`tasks/repoint_scheduled_tasks.ps1`'s self-verification filter was
   stale.** The closing table filtered on `$_.Execute -like '*project*Job*'`,
   which matched the old OneDrive path. Now filters on `$_.Execute -eq $wrapper`
   (in scope from line 33, same value the script assigns at line 96). Verified
   against the live task list: the filter matches exactly the 13 managed tasks.
   The script's closing note was reworded to match — under the old glob the
   disabled `Job collector` task was listed and called out as an exception;
   under the new filter it is excluded, so the note said the opposite of what
   the script now does.
3. ✅ **Documentation described the old OneDrive location.** `SCHEDULING.md`'s
   `cd` examples, unprefixed script invocations, obsolete OneDrive-locks-`logs/`
   warning and broken `cost_tracker.py` link are all corrected; `QUICKSTART.md`
   gained the now-required `pip install -e .` step; `README.md`'s Project
   Structure tree was rewritten for the new layout and every path in it verified
   to exist.
4. ✅ **`tests/test_lane.py`'s `test_no_module_shadows_the_stdlib` was vacuous.**
   It checked `paths.ROOT`, which post-reorg holds no `.py` files at all. It now
   checks both directories the reorg actually put on `sys.path`: `scripts/`
   (Python's own `sys.path[0]` for every entry point) and `src/` (added by the
   editable install — `pyproject.toml` uses `package-dir = {"" = "src"}`, so a
   `src/queue.py` would shadow the stdlib just as surely). The original fix brief
   only called for `scripts/`. Verified by planting `scripts/queue.py` and
   `src/queue.py` in turn: each makes the test fail, and it passes once removed.
5. ✅ **`tasks/run_enrich_companies.bat` stale comment** — `python -u
   enrich_companies.py --deep` now carries the `scripts\` prefix.

### Also fixed, found while re-verifying

- **`deprecated/job_collector.py` was broken twice over.** `main.py` moved into
  `scripts/`, which is not on `sys.path` when this file is the script being run;
  and the file's own name shadows the `src/job_collector` package that `main.py`
  imports, so naively adding `scripts/` only converted the `ModuleNotFoundError`
  into a circular-import `ImportError`. It now bootstraps `scripts/` and drops
  its own directory from `sys.path` for the duration of the import — the same
  fix `scripts/` entry points use — and warns on stderr. Both launchers
  (`run_job_collector.bat`, `run_job_collector.sh`) had their `cd` and script
  paths corrected too.
- **`README.md` / `QUICKSTART.md` still taught the deprecated entry point.**
  14 occurrences of `python job_collector.py` now read `python scripts\main.py`.
  README's option list advertised `--use-api`, which `scripts/main.py` has never
  had, and omitted `--exclude-senior`, which it does; the `--output` default and
  the company-list / cache locations now name `data/` and `state/`. QUICKSTART
  pointed at `test_sample.py` and `example_usage.py`, neither of which exists in
  this repo — the test step now runs the real suite.
- **`test_F14_kayak_own_board_rows_are_A` was coupled to live data.** It
  hard-coded "KAYAK has 2 `ats_direct` rows", but `_ROWS = CL.load_rows(paths.DATA_DIR)`
  reads the live, gitignored `data/` CSVs. A genuine new KAYAK posting from the
  verification run below turned the suite red. The count was a fixture guard,
  not the assertion under test; it is now a non-empty check, with the segment
  assertion unchanged. This was pre-existing, not a reorg regression.

Left as-is, deliberately: the OneDrive references in `docs/req/` and
`src/dashboard_loop/v2/*.md` are frozen design history, and the "the tree lives
in OneDrive" rationale comments in `scripts/company_lane.py`, `dashboard.py` and
`enrich_companies.py` are stale reasoning for behaviour (atomic writes) that is
still correct. Also still outstanding, unchanged from before: the disabled,
deprecated `Job collector` Scheduled Task points at
`D:\OneDrive\work\school\project\Job\run_job_collector.bat`. Harmless while
disabled; update its Execute path to `D:\Dev\job-collector\deprecated\run_job_collector.bat`
or delete the task whenever convenient.

## Verification of the fixes

- **Test suite:** 89 tests, `OK (skipped=3)`. The three skips are by design — two
  need `JOB_TEST_LLM=1`, one names a seed fixture the dashboard_loop reorg
  intentionally removed.
- **Entry points:** all 11 scripts in `scripts/` run to exit 0.
  `run_log.py`, `company_lane.py` and `view.py` have no `__main__` block — they
  are library modules, covered by the suite's imports rather than by launching.
- **Every collector re-run for real** through `tasks\run_logged.bat` from the new
  location, on 2026-08-24:

  | lane | exit | result |
  |---|---|---|
  | `run_ats_collector` | 0 | 245/245 companies, 43091 jobs fetched, 200 matched, 1 new |
  | `run_ddg_collector` | 0 | 2/3 queries OK; the third gave up on a DuckDuckGo HTTP 202 challenge, which is the script's designed graceful degradation |
  | `run_enrich_companies` | 0 | +8 profiles, 2 calls, $0.0010 |
  | `run_newgrad_collector` | 0 | all 9 queries, 5 new jobs |
  | `run_daily_report` | 0 | report written, dashboard bundle 10 files / 6 day blocks / 0.58 MB |

- **`scripts/backfill_titles.py`** dry run: kept 4859, dropped 2, zero writes
  confirmed.
- **All three `tasks/*.ps1`** parse clean via `PSParser::Tokenize`.
- **13 live Scheduled Tasks** verified pointing at
  `D:\Dev\job-collector\tasks\run_logged.bat`.

## Next steps

The branch is ready for `superpowers:finishing-a-development-branch`.
