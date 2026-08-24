# Relocate to D:\Dev and reorganize project layout

Date: 2026-08-23
Status: approved, pending implementation plan

## Motivation

The project currently lives at `D:\OneDrive\work\school\project\Job`, inside
OneDrive sync, with ~50 loose files (scripts, `.bat`/`.ps1` launchers, data
CSVs, JSON state/cache files) sitting directly in the project root. The user
wants it relocated to `D:\Dev\job-collector` and reorganized so the root is
readable again.

This is a live system: 13 Windows Scheduled Tasks run collectors on a cron
schedule via `run_logged.bat`, writing to `logs/`, `ats_jobs.csv`,
`ddg_jobs.csv`, `newgrad_classifications.csv`, and several JSON caches. There
is no git remote today — this OneDrive folder is the only copy of the commit
history. Both facts drive the execution order below.

## Target layout

```
job-collector/
├── pyproject.toml          # NEW — declares src/ as the package root; `pip install -e .`
├── README.md
├── QUICKSTART.md
├── SCHEDULING.md
├── setup_environment.bat
├── environment.yml
├── requirements.txt
├── .env
├── .gitignore
├── .claude/                 # unchanged
├── src/
│   ├── paths.py             # NEW — DATA_DIR / STATE_DIR / CONFIG_DIR constants
│   ├── job_collector/        # moved as-is (git mv)
│   ├── ats_direct/            # moved as-is (git mv)
│   ├── ddg_search/             # moved as-is (git mv)
│   └── dashboard_loop/          # only current v2/ survives; everything else deleted (git rm)
├── scripts/                  # CLI entry points (git mv from root)
│   ├── main.py
│   ├── ats_direct.py
│   ├── ddg_search.py
│   ├── dashboard.py
│   ├── daily_report.py
│   ├── enrich_companies.py
│   ├── view.py
│   ├── backfill_titles.py
│   ├── download_company_lists.py
│   ├── company_lane.py
│   └── run_log.py
├── tasks/                    # scheduled-task launchers (git mv from root)
│   ├── run_logged.bat
│   ├── run_ats_collector.bat
│   ├── run_ddg_collector.bat
│   ├── run_newgrad_collector.bat
│   ├── run_daily_report.bat
│   ├── run_enrich_companies.bat
│   ├── resolve_python.bat
│   ├── pause_scheduled_tasks.bat
│   ├── resume_scheduled_tasks.bat
│   ├── register_enrich_task.ps1
│   ├── repoint_scheduled_tasks.ps1   # rewritten to point at the new absolute path
│   └── retime_ddg12.ps1
├── deprecated/                # already-disabled legacy entry point, kept for reference
│   ├── job_collector.py
│   ├── run_job_collector.bat
│   └── run_job_collector.sh
├── data/                      # collector outputs
│   ├── ats_jobs.csv
│   ├── ddg_jobs.csv
│   ├── newgrad_classifications.csv
│   ├── newgrad_classifications.20260822-015719.bak.csv
│   ├── job_classifications.csv
│   ├── jobs_df.csv
│   ├── fortune_500_companies.csv
│   └── unicorn_companies.csv
├── config/                    # human-curated inputs
│   ├── priority_companies.txt
│   └── company_overrides.json
├── state/                     # machine-generated caches (git mv for tracked ones)
│   ├── ats_registry.json
│   ├── company_profiles.json
│   ├── company_database_cache.json
│   ├── ddg_state.json
│   └── title_verdicts.json
├── web/                        # unchanged
├── tests/                       # unchanged
├── docs/                         # unchanged
├── logs/                          # unchanged, gitignored
└── agent_browser/                  # empty, unreferenced anywhere in the codebase — left alone
```

## `src/paths.py`

The same handful of filenames (`ats_jobs.csv`, `ats_registry.json`,
`company_profiles.json`, ...) are hardcoded as defaults in ~50 places across
both the entry scripts *and* package internals (`job_collector/database/company_db.py`,
`job_collector/io/csv_handler.py`, `job_collector/pipeline/job_pipeline.py`,
`job_collector/collectors/linkedin.py`, `ats_direct/registry.py`,
`ats_direct/collector.py`, `ats_direct/expand_registry.py`,
`ddg_search/collector.py`). Moving those files into `data/`, `config/`, and
`state/` without a shared source of truth would mean chasing down each
literal individually and re-breaking on the next reorg.

`src/paths.py` exposes:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # project root, regardless of CWD
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
```

Every one of the ~50 reference sites is updated to build its path from these
constants (e.g. `STATE_DIR / "ats_registry.json"`) instead of a bare
filename. Because `ROOT` is derived from `paths.py`'s own file location, this
works regardless of the caller's CWD — removing the current implicit
assumption that every script is launched with the project root as CWD.

## Task launcher rule

Every `.bat` file moves into `tasks/`, one directory below the project root.
Each gets a single mechanical change: `cd /d "%~dp0"` → `cd /d "%~dp0.."`,
so CWD becomes the project root after that line runs — consistent with
where `scripts/`, `data/`, `state/`, `logs/` all live. Python invocations
gain a `scripts\` prefix (e.g. `ats_direct.py` → `scripts\ats_direct.py`).
Output arguments that used to be bare filenames (`--output ats_jobs.csv`)
become `data\ats_jobs.csv`.

`%~dp0resolve_python.bat`-style sibling calls inside these files are
**unaffected** — `%~dp0` is resolved from the invoking script's own path at
parse time, not from the current directory, so it still finds
`tasks\resolve_python.bat` correctly after the `cd ..` runs earlier in the
same script.

`run_logged.bat`'s own path references (`logs\%~1`, `%~dp0%~1.bat`) need no
change beyond the same `cd ..`: `logs/` stays at the project root, and its
sibling `.bat` files stay together with it in `tasks/`.

## Packaging: `pyproject.toml`

A minimal `pyproject.toml` declares `src/` as the package root and is
installed with `pip install -e .` into the `job-classifier` conda
environment once, post-move. This lets `import job_collector` / `import
ats_direct` / `import ddg_search` resolve regardless of which directory a
script is run from, replacing today's implicit "CWD happens to be the
project root" assumption.

## Scheduled Tasks (13 total)

`tasks/repoint_scheduled_tasks.ps1` already exists and repoints task
actions; it's extended to point every task's Execute/Start-in at
`D:\Dev\job-collector\tasks\run_logged.bat`. Still requires an elevated
PowerShell session, same as today. A full definition backup
(`Export-ScheduledTask`) is written before any change, as the script
already does.

## Execution order

1. **Pause** every scheduled task (`pause_scheduled_tasks.bat`) so nothing
   fires mid-migration.
2. **Review and commit** the current uncommitted work (several modified
   tracked files, several new untracked files including `.claude/`,
   `dashboard_loop/v2/`, `view.py`, `web/`) — done deliberately, not
   swept in with the reorg's own commits.
3. **Create a GitHub remote and push** — this OneDrive folder is currently
   the only copy of the history; this step exists specifically so leaving
   OneDrive doesn't also mean losing the backup.
4. **Reorganize in place**, still inside the OneDrive folder: `git mv`
   every tracked file/directory into its new home, `git rm` the deleted
   `dashboard_loop` experiment files, add `paths.py` and `pyproject.toml`,
   update the ~50 path references, rewrite the `tasks/*.bat` files per the
   rule above.
5. **Smoke-test** each collector end-to-end from the new layout before
   moving anything physically: `ats_direct.py`, `ddg_search.py`,
   `main.py` (newgrad path), `enrich_companies.py`, `daily_report.py` +
   `dashboard.py`. Run the existing `tests/` suite.
6. **Move** the verified folder to `D:\Dev\job-collector`.
7. **Repoint** the 13 Scheduled Tasks (elevated).
8. **Resume** tasks; watch the next couple of live runs land correctly in
   `logs/runs.jsonl`.
9. Decide together whether to delete the old OneDrive folder or leave it
   briefly as a safety net.

## Out of scope

- `agent_browser/` — empty, unreferenced anywhere in the codebase. Left
  untouched.
- Any change to what the collectors actually do (classification logic,
  rate limiting, ATS providers, etc.) — this is a pure relocation +
  reorganization, no behavior change beyond path resolution.
- Deleting the old OneDrive copy — deferred to step 9, a separate decision
  once the new location is confirmed working.

## Rollback

Every physical move within git-tracked territory is a `git mv`/`git rm`,
so `git reset --hard` at any point before step 6 returns to the pre-reorg
state. Scheduled Task changes are backed up to
`logs/_task_backup/<name>.xml` before being touched (existing behavior of
`repoint_scheduled_tasks.ps1`), with a documented rollback snippet. The old
OneDrive folder is not deleted until step 9, after the new location is
confirmed working end-to-end.
