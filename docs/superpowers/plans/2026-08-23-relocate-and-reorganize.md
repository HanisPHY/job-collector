# Relocate to D:\Dev and Reorganize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the project's ~50 loose root files into `src/`, `scripts/`, `tasks/`, `data/`, `config/`, `state/`, `deprecated/`, then relocate the whole tree from `D:\OneDrive\work\school\project\Job` to `D:\Dev\job-collector`, without breaking any of the 13 live Windows Scheduled Tasks.

**Architecture:** Every package (`job_collector/`, `ats_direct/`, `ddg_search/`, `dashboard_loop/v2/`) moves under `src/` and becomes pip-installable in editable mode, so `import job_collector` etc. resolve regardless of the caller's working directory. A new `src/paths.py` module (`ROOT`, `DATA_DIR`, `CONFIG_DIR`, `STATE_DIR`, all `pathlib.Path`) becomes the single source of truth for where data/config/state files live, replacing ~20 scattered hardcoded filenames and `HERE`/`ROOT`-from-`__file__` computations. CLI entry scripts move to `scripts/`, Scheduled Task launchers move to `tasks/` with one mechanical `cd` fix. The physical move to `D:\Dev\job-collector` happens only after everything is verified working in place.

**Tech Stack:** Python 3.10 (conda env `job-classifier`), setuptools src-layout editable install, Windows Task Scheduler / PowerShell, existing `unittest` suite in `tests/`.

**Spec:** `docs/superpowers/specs/2026-08-23-relocate-and-reorganize-design.md`

## Global Constraints

- No behavior change beyond path resolution — classification logic, rate limiting, ATS providers, dashboard rendering all stay byte-for-byte identical in what they compute.
- Every tracked file move is `git mv` (preserves history); every gitignored file move is a plain filesystem move.
- `paths.py` exposes `pathlib.Path` objects; anywhere the existing code string-concatenates a path (e.g. `output_file + ".tmp"`) the call site must pass `str(paths.X / "name")`, not a bare `Path`.
- Nothing in this plan touches Windows Scheduled Tasks or the physical folder location — that is Tasks 10-12, done only after Tasks 1-9 are verified working in place at the current OneDrive path.
- `agent_browser/` is out of scope — leave untouched.

---

## Task 1: Pause the live Scheduled Tasks

Nothing below this line should run against a half-moved project. `pause_scheduled_tasks.bat` self-elevates (UAC prompt) and disables all 13 tasks.

**Files:** none (uses existing `pause_scheduled_tasks.bat` at its current root location — it moves to `tasks/` in Task 7, after which `resume_scheduled_tasks.bat`'s new location is what re-enables them in Task 12).

- [ ] **Step 1: Run it**

```
pause_scheduled_tasks.bat
```

A UAC prompt appears — approve it. Wait for "Done. All tasks disabled."

- [ ] **Step 2: Verify**

```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -match '^(ATS_|DDG_|ng job collector|Job - )' } |
    Select-Object TaskName, State
```

Expected: every listed task shows `State: Disabled`.

No commit — this step touches no files.

---

## Task 2: Add `src/paths.py` and `pyproject.toml`

**Files:**
- Create: `src/paths.py`
- Create: `pyproject.toml`

**Interfaces:**
- Produces: `paths.ROOT`, `paths.DATA_DIR`, `paths.CONFIG_DIR`, `paths.STATE_DIR` (all `pathlib.Path`), importable as top-level `paths` from anywhere once the editable install is active. Every later task depends on this.

- [ ] **Step 1: Create `src/paths.py`**

```python
"""
Single source of truth for where data/config/state files live.

ROOT is derived from this file's own location, not the caller's CWD or
__file__, so `import paths` resolves identically whether it's a scheduled
task launched from tasks/, a script run from scripts/, or a package deep
under src/.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "job-collector"
version = "0.1.0"
requires-python = ">=3.10"

[tool.setuptools]
package-dir = {"" = "src"}
py-modules = ["paths"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 3: Editable-install into the `job-classifier` env and verify**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -m pip install -e .
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "import paths; print(paths.ROOT); print(paths.DATA_DIR)"
```

Expected: prints the current project root (still the OneDrive path at this point) and `<root>\data`. `data/` does not need to exist yet for this check — `paths.DATA_DIR` is just a `Path` value.

(If a different `job-classifier` interpreter path is in use on this machine, substitute it — see `resolve_python.bat`'s search list.)

- [ ] **Step 4: Commit**

```bash
git add src/paths.py pyproject.toml
git commit -m "Add src/paths.py and pyproject.toml for the reorg's editable install"
```

---

## Task 3: Move `ats_direct/` into `src/`, fix its path defaults

**Files:**
- Move: `ats_direct/__init__.py`, `ats_direct/registry.py`, `ats_direct/collector.py`, `ats_direct/rate_limiter.py`, `ats_direct/seed_companies.py`, `ats_direct/providers.py`, `ats_direct/ng_filter.py`, `ats_direct/us_filter.py`, `ats_direct/expand_registry.py`, `ats_direct/RATE_LIMITS.md`, `ats_direct/VERIFIED_ATS_PLATFORMS.md` → `src/ats_direct/...`
- Modify: `src/ats_direct/registry.py`, `src/ats_direct/collector.py`, `src/ats_direct/expand_registry.py`

**Interfaces:**
- Consumes: `paths.STATE_DIR`, `paths.DATA_DIR` (Task 2)
- Produces: `Registry(registry_path: str = str(paths.STATE_DIR / "ats_registry.json"))`, `collect(registry_path=..., output_file: str = str(paths.DATA_DIR / "ats_jobs.csv"))`, `expand(registry_path=...)` — unchanged call signatures, only the default values change. `scripts/ats_direct.py` (Task 6) relies on these new defaults matching its own argparse defaults.

- [ ] **Step 1: Move the directory**

```bash
mkdir -p src
git mv ats_direct src/ats_direct
```

- [ ] **Step 2: Fix `src/ats_direct/registry.py`**

```python
# before
REGISTRY_FILE = "ats_registry.json"

# after
import paths
REGISTRY_FILE = str(paths.STATE_DIR / "ats_registry.json")
```

(Add `import paths` near the top, alongside the existing `import os`/`import re`/`import json` block.)

- [ ] **Step 3: Fix `src/ats_direct/collector.py`**

```python
# before
def collect(registry_path: str = "ats_registry.json",
            output_file: str = "ats_jobs.csv",
            strict: bool = True,
            us_only: bool = True,
            max_companies: int = None,
            verbose: bool = True) -> RunStats:

# after
import paths

def collect(registry_path: str = str(paths.STATE_DIR / "ats_registry.json"),
            output_file: str = str(paths.DATA_DIR / "ats_jobs.csv"),
            strict: bool = True,
            us_only: bool = True,
            max_companies: int = None,
            verbose: bool = True) -> RunStats:
```

- [ ] **Step 4: Fix `src/ats_direct/expand_registry.py`**

```python
# before
def expand(registry_path: str = "ats_registry.json", verbose: bool = True,
           validate: bool = True) -> dict:

# after
import paths

def expand(registry_path: str = str(paths.STATE_DIR / "ats_registry.json"),
           verbose: bool = True, validate: bool = True) -> dict:
```

- [ ] **Step 5: Verify the package still imports and resolves the new defaults**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "from ats_direct.registry import Registry, REGISTRY_FILE; from ats_direct.collector import collect; print(REGISTRY_FILE)"
```

Expected: no ImportError, prints an absolute path ending in `state\ats_registry.json`.

- [ ] **Step 6: Commit**

```bash
git add src/ats_direct
git commit -m "Move ats_direct package into src/, default its paths off paths.py"
```

---

## Task 4: Move `ddg_search/` into `src/`, fix its path defaults

**Files:**
- Move: `ddg_search/__init__.py`, `ddg_search/collector.py`, `ddg_search/ddg_client.py`, `ddg_search/link_parser.py`, `ddg_search/RATE_LIMITS.md` → `src/ddg_search/...`
- Modify: `src/ddg_search/collector.py`

**Interfaces:**
- Consumes: `paths.DATA_DIR`, `paths.STATE_DIR` (Task 2)
- Produces: `collect(output_file: str = str(paths.DATA_DIR / "ddg_jobs.csv"), ..., state_file: str = str(paths.STATE_DIR / "ddg_state.json"))`

- [ ] **Step 1: Move the directory**

```bash
git mv ddg_search src/ddg_search
```

- [ ] **Step 2: Fix `src/ddg_search/collector.py`**

```python
# before
STATE_FILE = "ddg_state.json"
...
def collect(output_file: str = "ddg_jobs.csv",
            queries_per_run: int = 5,
            strict: bool = True,
            update_registry: bool = False,
            state_file: str = STATE_FILE):

# after
import paths

STATE_FILE = str(paths.STATE_DIR / "ddg_state.json")
...
def collect(output_file: str = str(paths.DATA_DIR / "ddg_jobs.csv"),
            queries_per_run: int = 5,
            strict: bool = True,
            update_registry: bool = False,
            state_file: str = STATE_FILE):
```

Leave the `registry = Registry()` call inside this file untouched — it already picks up `ats_direct.registry.REGISTRY_FILE`'s new default from Task 3.

- [ ] **Step 3: Verify**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "from ddg_search.collector import collect, STATE_FILE; print(STATE_FILE)"
```

Expected: prints an absolute path ending in `state\ddg_state.json`.

- [ ] **Step 4: Commit**

```bash
git add src/ddg_search
git commit -m "Move ddg_search package into src/, default its paths off paths.py"
```

---

## Task 5: Move `job_collector/` into `src/`, fix its path defaults, drop its manual sys.path hack

**Files:**
- Move: entire `job_collector/` tree → `src/job_collector/`
- Modify: `src/job_collector/database/company_db.py`, `src/job_collector/io/csv_handler.py`, `src/job_collector/pipeline/job_pipeline.py`, `src/job_collector/collectors/linkedin.py`, `src/job_collector/classifiers/title_relevance.py`

**Interfaces:**
- Consumes: `paths.DATA_DIR`, `paths.STATE_DIR` (Task 2), `ats_direct.ng_filter` (Task 3, now installed and importable without a manual `sys.path` hack)
- Produces: `JobClassificationPipeline.process(..., output_file: str = str(paths.DATA_DIR / "job_classifications.csv"))`, `CSVHandler.load_existing_jobs`/`save_to_csv` same new default, `CompanyDatabase(cache_file=None)` still defaulting to `CACHE_FILE = str(paths.STATE_DIR / "company_database_cache.json")`

- [ ] **Step 1: Move the directory**

```bash
git mv job_collector src/job_collector
```

- [ ] **Step 2: Fix `src/job_collector/database/company_db.py`**

```python
# before
class CompanyDatabase:
    ...
    CACHE_FILE = "company_database_cache.json"

# after
import paths

class CompanyDatabase:
    ...
    CACHE_FILE = str(paths.STATE_DIR / "company_database_cache.json")
```

```python
# before
    def _load_fortune_500(self) -> Set[str]:
        """Load Fortune 500 companies from local CSV or download."""
        companies = set()
        fortune_file = "fortune_500_companies.csv"

# after
    def _load_fortune_500(self) -> Set[str]:
        """Load Fortune 500 companies from local CSV or download."""
        companies = set()
        fortune_file = str(paths.DATA_DIR / "fortune_500_companies.csv")
```

```python
# before
    def _load_unicorn_companies(self) -> Set[str]:
        """Load unicorn companies from local CSV."""
        companies = set()
        unicorn_file = "unicorn_companies.csv"

# after
    def _load_unicorn_companies(self) -> Set[str]:
        """Load unicorn companies from local CSV."""
        companies = set()
        unicorn_file = str(paths.DATA_DIR / "unicorn_companies.csv")
```

- [ ] **Step 3: Fix `src/job_collector/io/csv_handler.py`**

```python
# before
from ..models import JobPosting
from ..utils import generate_job_id


class CSVHandler:
    """Handles reading and writing job postings to/from CSV files."""

    @staticmethod
    def load_existing_jobs(output_file: str = "job_classifications.csv") -> Tuple[Dict[str, JobPosting], Set[str]]:

# after
import paths

from ..models import JobPosting
from ..utils import generate_job_id


class CSVHandler:
    """Handles reading and writing job postings to/from CSV files."""

    @staticmethod
    def load_existing_jobs(output_file: str = str(paths.DATA_DIR / "job_classifications.csv")) -> Tuple[Dict[str, JobPosting], Set[str]]:
```

```python
# before
    @staticmethod
    def save_to_csv(jobs: List[JobPosting], output_file: str = "job_classifications.csv") -> Dict[str, int]:

# after
    @staticmethod
    def save_to_csv(jobs: List[JobPosting], output_file: str = str(paths.DATA_DIR / "job_classifications.csv")) -> Dict[str, int]:
```

- [ ] **Step 4: Fix `src/job_collector/pipeline/job_pipeline.py`**

```python
# before
import os
import time
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# after
import os
import time
from typing import List, Optional

import paths
```

```python
# before
        self.title_filter = TitleFilter(
            adjudicator=TitleAdjudicator(
                client=OpenAIChatClient(api_key=openai_key,
                                        cost_tracker=self.cost_tracker),
                cache_path=os.path.join(ROOT, 'title_verdicts.json'),
                cost_tracker=self.cost_tracker,
            ),
            drop_log_path=os.path.join(ROOT, 'logs', 'dropped_titles.jsonl'),
        )

# after
        self.title_filter = TitleFilter(
            adjudicator=TitleAdjudicator(
                client=OpenAIChatClient(api_key=openai_key,
                                        cost_tracker=self.cost_tracker),
                cache_path=str(paths.STATE_DIR / 'title_verdicts.json'),
                cost_tracker=self.cost_tracker,
            ),
            drop_log_path=str(paths.ROOT / 'logs' / 'dropped_titles.jsonl'),
        )
```

```python
# before (two occurrences: process() and save_to_csv())
    def process(self, search_query: str = "software engineer", limit: int = 50, time_filter_minutes: Optional[int] = None, output_file: str = "job_classifications.csv") -> List[JobPosting]:
...
    def save_to_csv(self, jobs: List[JobPosting], output_file: str = "job_classifications.csv"):

# after
    def process(self, search_query: str = "software engineer", limit: int = 50, time_filter_minutes: Optional[int] = None, output_file: str = str(paths.DATA_DIR / "job_classifications.csv")) -> List[JobPosting]:
...
    def save_to_csv(self, jobs: List[JobPosting], output_file: str = str(paths.DATA_DIR / "job_classifications.csv")):
```

- [ ] **Step 5: Fix `src/job_collector/collectors/linkedin.py`**

```python
# before
                # save jobs_df to csv
                jobs_df.to_csv('jobs_df.csv', index=False)

# after
                # save jobs_df to csv
                jobs_df.to_csv(str(paths.DATA_DIR / 'jobs_df.csv'), index=False)
```

Add `import paths` to this file's import block (it currently has none beyond `from typing import ...` and the `jobspy`/`..models`/`..utils` imports).

- [ ] **Step 6: Fix `src/job_collector/classifiers/title_relevance.py`** — drop the manual sys.path hack now that `ats_direct` is a real installed package

```python
# before
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ats_direct.ng_filter import DROP, GRAY, title_verdict   # noqa: E402

# after
import json
import os
import re
import tempfile

from ats_direct.ng_filter import DROP, GRAY, title_verdict
```

(Drop the now-unused `import sys` only if nothing else in the file uses `sys` — grep the file for other `sys.` uses before removing the import.)

- [ ] **Step 7: Run this package's existing tests to catch anything missed**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "from job_collector import JobClassificationPipeline; from job_collector.database.company_db import CompanyDatabase; from job_collector.io.csv_handler import CSVHandler; print('ok')"
```

Expected: `ok`, no ImportError/NameError (a leftover bare `ROOT` reference anywhere in `job_pipeline.py` would raise `NameError` at import or call time).

- [ ] **Step 8: Commit**

```bash
git add src/job_collector
git commit -m "Move job_collector package into src/, default its paths off paths.py"
```

---

## Task 6: Reorganize `dashboard_loop/` — delete the old experiment files, move `v2/` into `src/`

Per the approved design: everything in `dashboard_loop/` except `v2/` is finished research/experiment output from a completed design round and gets deleted. `v2/` is the current, still-referenced tooling and moves under `src/`.

**Files:**
- Delete (git rm): every file directly under `dashboard_loop/` (not `dashboard_loop/v2/`) — `SUMMARY_REPORT.html`, all `_evalA*.py`/`_evalB*.py`/`_pm*.py`/`_verify_*.py`/`_orch_*` files, `base.py`, `company_profiles.round2.json`, `company_profiles.sample.json`, `enrich_prompt_reference.py`, `enrich_v4.py`, `fn50.json`, `passes_v4.json`, `r2.py`, `round1_design.md`, `round1_eval_A.md`, `round1_eval_B.md`, `round2_design.md`, `round2_eval_A.md`, `round2_eval_B.md`, `round3_eval_A.md`, `round3_eval_B.md`, `round3_spec.md`, `stage2.py`, `stage2_gpt-4o-mini.json`, `stage2_gpt-4o.json`, `CONTEXT_BRIEF.md`
- Move: `dashboard_loop/v2/` → `src/dashboard_loop/v2/`
- Modify: `src/dashboard_loop/v2/_evalA_base.py`, `src/dashboard_loop/v2/_pm2_base.py`, `src/dashboard_loop/v2/_pm_base.py`

- [ ] **Step 1: Delete everything except `v2/`**

```bash
git rm dashboard_loop/SUMMARY_REPORT.html dashboard_loop/CONTEXT_BRIEF.md \
       dashboard_loop/_evalA2_*.py dashboard_loop/_evalA3_*.py dashboard_loop/_evalA_*.py \
       dashboard_loop/_verify_*.py dashboard_loop/base.py \
       dashboard_loop/company_profiles.round2.json dashboard_loop/company_profiles.sample.json \
       dashboard_loop/enrich_prompt_reference.py dashboard_loop/enrich_v4.py dashboard_loop/fn50.json \
       dashboard_loop/passes_v4.json dashboard_loop/r2.py dashboard_loop/round1_design.md \
       dashboard_loop/round1_eval_A.md dashboard_loop/round1_eval_B.md dashboard_loop/round2_design.md \
       dashboard_loop/round2_eval_A.md dashboard_loop/round2_eval_B.md dashboard_loop/round3_eval_A.md \
       dashboard_loop/round3_eval_B.md dashboard_loop/round3_spec.md dashboard_loop/stage2.py \
       dashboard_loop/stage2_gpt-4o-mini.json dashboard_loop/stage2_gpt-4o.json
rm -rf dashboard_loop/__pycache__
git status --short dashboard_loop
```

Expected: `git status --short dashboard_loop` shows only `dashboard_loop/v2/...` entries left as untouched/unmoved (still `A ` or plain, not deleted).

- [ ] **Step 2: Move `v2/` into `src/`**

```bash
git mv dashboard_loop/v2 src/dashboard_loop_v2
mkdir -p src/dashboard_loop
git mv src/dashboard_loop_v2 src/dashboard_loop/v2
rmdir dashboard_loop 2>/dev/null || true
```

(`dashboard_loop/` should now be empty and gone; if `rmdir` fails because the directory still exists with leftover empty subfolders like `__pycache__`, remove those first.)

- [ ] **Step 3: Fix the three files that compute `ROOT` and `import dashboard`**

```python
# before (identical pattern in _evalA_base.py, _pm2_base.py, _pm_base.py)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import dashboard as DB         # noqa: E402

# after
import paths

sys.path.insert(0, str(paths.ROOT / "scripts"))

import dashboard as DB         # noqa: E402
```

- [ ] **Step 4: Verify**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "import ast; [ast.parse(open(f, encoding='utf-8').read(), f) for f in ['src/dashboard_loop/v2/_evalA_base.py','src/dashboard_loop/v2/_pm2_base.py','src/dashboard_loop/v2/_pm_base.py']]; print('syntax ok')"
```

Expected: `syntax ok`. (A full import check needs `scripts/dashboard.py` to exist first, which happens in Task 8 — this step only confirms the edits are syntactically valid.)

- [ ] **Step 5: Commit**

```bash
git add -A dashboard_loop src/dashboard_loop
git commit -m "Delete finished dashboard_loop experiment artifacts, move v2/ into src/"
```

---

## Task 7: Create `data/`, `config/`, `state/`; move the data/config/state files into them

**Files:**
- Move (git mv, tracked): `ats_registry.json`, `company_database_cache.json`, `ddg_state.json`, `title_verdicts.json`, `company_profiles.json` → `state/`; `company_overrides.json`, `priority_companies.txt` → `config/`
- Move (plain `mv`, gitignored): `ats_jobs.csv`, `ddg_jobs.csv`, `newgrad_classifications.csv`, `newgrad_classifications.20260822-015719.bak.csv`, `job_classifications.csv`, `fortune_500_companies.csv`, `unicorn_companies.csv`, `jobs_df.csv` → `data/`

- [ ] **Step 1: Create the directories and move tracked files**

```bash
mkdir -p data config state
git mv ats_registry.json state/ats_registry.json
git mv company_database_cache.json state/company_database_cache.json
git mv ddg_state.json state/ddg_state.json
git mv title_verdicts.json state/title_verdicts.json
git mv company_profiles.json state/company_profiles.json
git mv company_overrides.json config/company_overrides.json
git mv priority_companies.txt config/priority_companies.txt
```

- [ ] **Step 2: Move gitignored data files (plain move, not tracked)**

```bash
mv ats_jobs.csv data/ats_jobs.csv
mv ddg_jobs.csv data/ddg_jobs.csv
mv newgrad_classifications.csv data/newgrad_classifications.csv
mv newgrad_classifications.20260822-015719.bak.csv data/newgrad_classifications.20260822-015719.bak.csv
mv job_classifications.csv data/job_classifications.csv
mv fortune_500_companies.csv data/fortune_500_companies.csv
mv unicorn_companies.csv data/unicorn_companies.csv
mv jobs_df.csv data/jobs_df.csv
```

- [ ] **Step 3: Verify nothing was left behind and paths.py agrees**

```bash
ls *.csv *.json *.txt 2>&1
```

Expected: `No such file or directory` for all three globs (root is clean of these).

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "import paths; import os; print(os.path.exists(paths.STATE_DIR / 'ats_registry.json')); print(os.path.exists(paths.DATA_DIR / 'ats_jobs.csv'))"
```

Expected: `True` / `True`.

- [ ] **Step 4: Commit**

```bash
git add -A data config state
git commit -m "Move data/config/state files into data/, config/, state/"
```

---

## Task 8: Move entry scripts into `scripts/`, fix their path references

**Files:**
- Move: `main.py`, `ats_direct.py`, `ddg_search.py`, `dashboard.py`, `daily_report.py`, `enrich_companies.py`, `view.py`, `backfill_titles.py`, `download_company_lists.py`, `company_lane.py`, `run_log.py` → `scripts/...`
- Modify: `scripts/main.py`, `scripts/ats_direct.py`, `scripts/ddg_search.py`, `scripts/dashboard.py`, `scripts/daily_report.py`, `scripts/enrich_companies.py`, `scripts/backfill_titles.py`, `scripts/download_company_lists.py`, `scripts/company_lane.py`, `scripts/run_log.py`

**Interfaces:**
- Consumes: `paths.ROOT`, `paths.DATA_DIR`, `paths.CONFIG_DIR`, `paths.STATE_DIR` (Task 2); `Registry`/`collect`/`expand` new defaults (Task 3); `ddg_search.collector.collect` new default (Task 4); `job_collector` package (Task 5)
- Produces: `company_lane.load_rows(root=paths.DATA_DIR)`, `company_lane.PROFILE_PATH`/`OVERRIDE_PATH`/`PRIORITY_PATH` now under `state/`/`config/` — `Task 9`'s test fixes rely on these.

- [ ] **Step 1: Move all eleven files**

```bash
mkdir -p scripts
git mv main.py scripts/main.py
git mv ats_direct.py scripts/ats_direct.py
git mv ddg_search.py scripts/ddg_search.py
git mv dashboard.py scripts/dashboard.py
git mv daily_report.py scripts/daily_report.py
git mv enrich_companies.py scripts/enrich_companies.py
git mv view.py scripts/view.py
git mv backfill_titles.py scripts/backfill_titles.py
git mv download_company_lists.py scripts/download_company_lists.py
git mv company_lane.py scripts/company_lane.py
git mv run_log.py scripts/run_log.py
```

- [ ] **Step 2: Fix `scripts/run_log.py`** (everything else in this task depends on `LOG_ROOT` being right — `daily_report.py` reuses `run_log.RUNS_FILE` directly)

```python
# before
import os
import json
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))

# logs/ sits inside the OneDrive-synced project tree by default. Set
# JOB_LOG_ROOT to move it elsewhere (e.g. %LOCALAPPDATA%\JobCollector\logs).
LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(_HERE, "logs")
RUNS_FILE = os.path.join(LOG_ROOT, "runs.jsonl")

# after
import os
import json
from datetime import datetime

import paths

# logs/ sits inside the synced project tree by default. Set
# JOB_LOG_ROOT to move it elsewhere (e.g. %LOCALAPPDATA%\JobCollector\logs).
LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(paths.ROOT, "logs")
RUNS_FILE = os.path.join(LOG_ROOT, "runs.jsonl")
```

- [ ] **Step 3: Fix `scripts/main.py`**

```python
# before
    parser.add_argument('--output', type=str, default='job_classifications.csv',
                       help='Output CSV file (default: job_classifications.csv)')

# after
    parser.add_argument('--output', type=str, default=str(paths.DATA_DIR / 'job_classifications.csv'),
                       help='Output CSV file (default: data/job_classifications.csv)')
```

Add `import paths` to the top import block (after the `dotenv` try/except, alongside `import run_log`).

- [ ] **Step 4: Fix `scripts/ats_direct.py`**

```python
# before
    parser.add_argument("--registry", default="ats_registry.json")
    parser.add_argument("--output", default="ats_jobs.csv")

# after
    parser.add_argument("--registry", default=str(paths.STATE_DIR / "ats_registry.json"))
    parser.add_argument("--output", default=str(paths.DATA_DIR / "ats_jobs.csv"))
```

Add `import paths` to the top import block (alongside `import run_log`).

- [ ] **Step 5: Fix `scripts/ddg_search.py`**

```python
# before
    parser.add_argument("--output", default="ddg_jobs.csv")

# after
    parser.add_argument("--output", default=str(paths.DATA_DIR / "ddg_jobs.csv"))
```

Add `import paths` to the top import block (alongside `import run_log`).

- [ ] **Step 6: Fix `scripts/company_lane.py`**

```python
# before
HERE = os.path.dirname(os.path.abspath(__file__))

PROFILE_PATH = os.environ.get("JOB_PROFILE_PATH") or os.path.join(HERE, "company_profiles.json")
OVERRIDE_PATH = os.path.join(HERE, "company_overrides.json")
PRIORITY_PATH = os.path.join(HERE, "priority_companies.txt")

# after
import paths

PROFILE_PATH = os.environ.get("JOB_PROFILE_PATH") or str(paths.STATE_DIR / "company_profiles.json")
OVERRIDE_PATH = str(paths.CONFIG_DIR / "company_overrides.json")
PRIORITY_PATH = str(paths.CONFIG_DIR / "priority_companies.txt")
```

```python
# before
def load_rows(root=HERE):

# after
def load_rows(root=paths.DATA_DIR):
```

- [ ] **Step 7: Fix `scripts/dashboard.py`**

```python
# before
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import company_lane as CL          # noqa: E402
import view                        # noqa: E402

LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(HERE, "logs")
OUT_DIR = os.path.join(LOG_ROOT, "dashboard")
STATE_PATH = os.path.join(LOG_ROOT, "last_report.json")
WEB_DIR = os.path.join(HERE, "web")

# after
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths
import company_lane as CL          # noqa: E402
import view                        # noqa: E402

LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(paths.ROOT, "logs")
OUT_DIR = os.path.join(LOG_ROOT, "dashboard")
STATE_PATH = os.path.join(LOG_ROOT, "last_report.json")
WEB_DIR = os.path.join(paths.ROOT, "web")
```

(`HERE` and its `sys.path.insert` stay — they're still needed so `import company_lane`/`import view` resolve when this file is run directly as `python scripts\dashboard.py` from a different CWD.)

```python
# before (around line 587)
    rows = CL.load_rows(HERE)

# after
    rows = CL.load_rows(paths.DATA_DIR)
```

- [ ] **Step 8: Fix `scripts/daily_report.py`**

```python
# before
        path = os.path.join(HERE, filename)

# after
        path = os.path.join(paths.DATA_DIR, filename)
```

Add `import paths` to the top import block, near where `HERE = os.path.dirname(os.path.abspath(__file__))` is defined (`HERE` itself can stay — nothing else in this file uses it after this fix, but leaving it is harmless; if a check shows it's now unused, delete the `HERE =` line too).

- [ ] **Step 9: Fix `scripts/enrich_companies.py`**

```python
# before
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import company_lane as CL          # noqa: E402
import run_log                     # noqa: E402
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402

# after
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paths
import company_lane as CL          # noqa: E402
import run_log                     # noqa: E402
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402
```

```python
# before
        rows = CL.load_rows(HERE)

# after
        rows = CL.load_rows(paths.DATA_DIR)
```

```python
# before
        env = os.path.join(HERE, ".env")

# after
        env = os.path.join(paths.ROOT, ".env")
```

- [ ] **Step 10: Fix `scripts/backfill_titles.py`**

```python
# before
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from job_collector.classifiers.title_relevance import (   # noqa: E402
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)

DEFAULT_CSV = os.path.join(ROOT, "newgrad_classifications.csv")

# after
import paths

from job_collector.classifiers.title_relevance import (
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)

DEFAULT_CSV = str(paths.DATA_DIR / "newgrad_classifications.csv")
```

```python
# before
        adjudicator=TitleAdjudicator(client=client,
                                     cache_path=os.path.join(ROOT, "title_verdicts.json"),
                                     cost_tracker=tracker),
        drop_log_path=os.path.join(ROOT, "logs", "dropped_titles.jsonl"),

# after
        adjudicator=TitleAdjudicator(client=client,
                                     cache_path=str(paths.STATE_DIR / "title_verdicts.json"),
                                     cost_tracker=tracker),
        drop_log_path=str(paths.ROOT / "logs" / "dropped_titles.jsonl"),
```

(Remove `sys` from the import list only if nothing else in the file references `sys.` — check before deleting.)

- [ ] **Step 11: Fix `scripts/download_company_lists.py`** (4 `open()` call sites)

```python
# before (appears twice, in two different functions)
                            with open('fortune_500_companies.csv', 'w', newline='', encoding='utf-8') as f:
...
    with open('fortune_500_companies.csv', 'w', newline='', encoding='utf-8') as f:

# after (both occurrences)
                            with open(str(paths.DATA_DIR / 'fortune_500_companies.csv'), 'w', newline='', encoding='utf-8') as f:
...
    with open(str(paths.DATA_DIR / 'fortune_500_companies.csv'), 'w', newline='', encoding='utf-8') as f:
```

```python
# before (appears twice, in two different functions)
                            with open('unicorn_companies.csv', 'w', newline='', encoding='utf-8') as f:
...
    with open('unicorn_companies.csv', 'w', newline='', encoding='utf-8') as f:

# after (both occurrences)
                            with open(str(paths.DATA_DIR / 'unicorn_companies.csv'), 'w', newline='', encoding='utf-8') as f:
...
    with open(str(paths.DATA_DIR / 'unicorn_companies.csv'), 'w', newline='', encoding='utf-8') as f:
```

Add `import paths` to the top of the file. Leave the two `print(f"  - fortune_500_companies.csv")` / `print(f"  - unicorn_companies.csv")` lines as-is — they're just a friendly summary message, not a path used for I/O.

- [ ] **Step 12: Syntax/import smoke check for the whole batch**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "
import sys, os
sys.path.insert(0, 'scripts')
import run_log, company_lane
print('run_log.RUNS_FILE =', run_log.RUNS_FILE)
print('company_lane.PROFILE_PATH =', company_lane.PROFILE_PATH)
print('company_lane.PRIORITY_PATH =', company_lane.PRIORITY_PATH)
"
```

Run this from the project root. Expected: all three printed paths are absolute and end in `logs\runs.jsonl`, `state\company_profiles.json`, `config\priority_companies.txt` respectively — no traceback.

- [ ] **Step 13: Commit**

```bash
git add -A scripts main.py ats_direct.py ddg_search.py dashboard.py daily_report.py enrich_companies.py view.py backfill_titles.py download_company_lists.py company_lane.py run_log.py
git commit -m "Move entry scripts into scripts/, default their paths off paths.py"
```

---

## Task 9: Move the deprecated legacy entry point into `deprecated/`

**Files:**
- Move: `job_collector.py`, `run_job_collector.bat`, `run_job_collector.sh` → `deprecated/...`

This is the already-disabled entry point `repoint_scheduled_tasks.ps1` itself calls out as "deliberately absent... disabled and deprecated." No path fixes needed inside it — it's not going to be run again, just kept for reference.

- [ ] **Step 1: Move**

```bash
mkdir -p deprecated
git mv job_collector.py deprecated/job_collector.py
git mv run_job_collector.bat deprecated/run_job_collector.bat
git mv run_job_collector.sh deprecated/run_job_collector.sh
```

- [ ] **Step 2: Commit**

```bash
git add -A deprecated job_collector.py run_job_collector.bat run_job_collector.sh
git commit -m "Move deprecated job_collector.py entry point into deprecated/"
```

---

## Task 10: Move Scheduled Task launchers into `tasks/`, fix the `cd` rule and script targets

**Files:**
- Move: `run_logged.bat`, `run_ats_collector.bat`, `run_ddg_collector.bat`, `run_newgrad_collector.bat`, `run_daily_report.bat`, `run_enrich_companies.bat`, `resolve_python.bat`, `pause_scheduled_tasks.bat`, `resume_scheduled_tasks.bat`, `register_enrich_task.ps1`, `repoint_scheduled_tasks.ps1`, `retime_ddg12.ps1` → `tasks/...`
- Modify: every `.bat` above except `resolve_python.bat`, `pause_scheduled_tasks.bat`, `resume_scheduled_tasks.bat`; `register_enrich_task.ps1`; `repoint_scheduled_tasks.ps1`; `retime_ddg12.ps1`

- [ ] **Step 1: Move all twelve files**

```bash
mkdir -p tasks
git mv run_logged.bat tasks/run_logged.bat
git mv run_ats_collector.bat tasks/run_ats_collector.bat
git mv run_ddg_collector.bat tasks/run_ddg_collector.bat
git mv run_newgrad_collector.bat tasks/run_newgrad_collector.bat
git mv run_daily_report.bat tasks/run_daily_report.bat
git mv run_enrich_companies.bat tasks/run_enrich_companies.bat
git mv resolve_python.bat tasks/resolve_python.bat
git mv pause_scheduled_tasks.bat tasks/pause_scheduled_tasks.bat
git mv resume_scheduled_tasks.bat tasks/resume_scheduled_tasks.bat
git mv register_enrich_task.ps1 tasks/register_enrich_task.ps1
git mv repoint_scheduled_tasks.ps1 tasks/repoint_scheduled_tasks.ps1
git mv retime_ddg12.ps1 tasks/retime_ddg12.ps1
```

- [ ] **Step 2: `run_logged.bat`** — only the `cd` line changes; every path inside it (`logs\%~1`, `%~dp0%~1.bat`) is already correct once CWD is the project root

```batch
:: before
cd /d "%~dp0"

:: after
cd /d "%~dp0.."
```

- [ ] **Step 3: `run_ats_collector.bat`**

```batch
:: before
cd /d "%~dp0"
...
"%JOB_PYTHON%" -u ats_direct.py --cleanup --expand --output ats_jobs.csv

:: after
cd /d "%~dp0.."
...
"%JOB_PYTHON%" -u scripts\ats_direct.py --cleanup --expand --output data\ats_jobs.csv
```

- [ ] **Step 4: `run_ddg_collector.bat`**

```batch
:: before
cd /d "%~dp0"
...
"%JOB_PYTHON%" -u ddg_search.py --queries 5 --update-registry --output ddg_jobs.csv

:: after
cd /d "%~dp0.."
...
"%JOB_PYTHON%" -u scripts\ddg_search.py --queries 5 --update-registry --output data\ddg_jobs.csv
```

- [ ] **Step 5: `run_newgrad_collector.bat`**

```batch
:: before
cd /d "%~dp0"
...
set OUTPUT=newgrad_classifications.csv
...
    "%JOB_PYTHON%" -u main.py --query "%%~Q" --limit %LIMIT% --time-filter %TIMEFILTER% --output %OUTPUT% --exclude-senior
:: (this "%JOB_PYTHON%" -u main.py ... line is repeated 3 times, once per query tier)

:: after
cd /d "%~dp0.."
...
set OUTPUT=data\newgrad_classifications.csv
...
    "%JOB_PYTHON%" -u scripts\main.py --query "%%~Q" --limit %LIMIT% --time-filter %TIMEFILTER% --output %OUTPUT% --exclude-senior
```

Apply the `main.py` → `scripts\main.py` change to all three occurrences (Tier 1, Tier 2, Tier 3 `for %%Q in (...)` blocks).

- [ ] **Step 6: `run_daily_report.bat`**

```batch
:: before
cd /d "%~dp0"
...
"%JOB_PYTHON%" -u daily_report.py
...
"%JOB_PYTHON%" -u dashboard.py

:: after
cd /d "%~dp0.."
...
"%JOB_PYTHON%" -u scripts\daily_report.py
...
"%JOB_PYTHON%" -u scripts\dashboard.py
```

- [ ] **Step 7: `run_enrich_companies.bat`**

```batch
:: before
cd /d "%~dp0"
...
"%JOB_PYTHON%" -u enrich_companies.py

:: after
cd /d "%~dp0.."
...
"%JOB_PYTHON%" -u scripts\enrich_companies.py
```

- [ ] **Step 8: `resolve_python.bat`, `pause_scheduled_tasks.bat`, `resume_scheduled_tasks.bat`** — no changes. `resolve_python.bat` only searches fixed conda env paths unrelated to the project location; the pause/resume scripts only call `schtasks /change /tn "<name>"` by task name, no file paths involved.

- [ ] **Step 9: `tasks/register_enrich_task.ps1`** — `$dir` (its own directory) is now `tasks/`, one level below the project root. The task's `-WorkingDirectory` should be the project root, not `tasks/`.

```powershell
# before
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

$action    = New-ScheduledTaskAction -Execute (Join-Path $dir 'run_logged.bat') `
                                     -Argument 'run_enrich_companies' `
                                     -WorkingDirectory $dir

# after
$dir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $dir

$action    = New-ScheduledTaskAction -Execute (Join-Path $dir 'run_logged.bat') `
                                     -Argument 'run_enrich_companies' `
                                     -WorkingDirectory $root
```

Also update the `.EXAMPLE` doc comment:

```powershell
# before
.EXAMPLE
    cd "D:\OneDrive\work\school\project\Job"
    .\register_enrich_task.ps1

# after
.EXAMPLE
    cd "D:\Dev\job-collector\tasks"
    .\register_enrich_task.ps1
```

- [ ] **Step 10: `tasks/repoint_scheduled_tasks.ps1`** — the `Execute` target ($wrapper) is already computed from the script's own `$MyInvocation.MyCommand.Path`, so it self-adjusts once this script is later run from its new `D:\Dev\job-collector\tasks\` location (Task 12). The one real bug: the backup path is joined onto `$dir` (now `tasks/`), but `logs/` lives at the project root, one level up.

```powershell
# before
$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$wrapper = Join-Path $dir 'run_logged.bat'
$backup  = Join-Path $dir 'logs\_task_backup'

# after
$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$root    = Split-Path -Parent $dir
$wrapper = Join-Path $dir 'run_logged.bat'
$backup  = Join-Path $root 'logs\_task_backup'
```

Also update the `.EXAMPLE` doc comment the same way as Step 9, and the verification `Where-Object` filter comment referencing `*project*Job*` is fine as-is (it's a loose glob, not an exact path).

- [ ] **Step 11: `tasks/retime_ddg12.ps1`** — same backup-path bug as Step 10.

```powershell
# before
$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$backups = Join-Path $dir 'logs\_task_backup'

# after
$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$root    = Split-Path -Parent $dir
$backups = Join-Path $root 'logs\_task_backup'
```

This script has already run once historically (it retimed `DDG_12` — that change persists in the live task and doesn't need re-running); this fix is so the script stays correct if it's ever re-run for reference, and so its rollback comment path (`logs\_task_backup\DDG_12.retime.xml`) still means the project-root `logs/`, not a nonexistent `tasks\logs\`.

- [ ] **Step 12: Verify batch file syntax** — Windows batch has no real "dry run"; the cheapest correctness check is grep for anything that still says `cd /d "%~dp0"` (should be zero, all became `%~dp0..`) and confirm every `.py`/data reference now carries its subfolder prefix.

```bash
grep -rn 'cd /d "%~dp0"' tasks/*.bat
```

Expected: no output (every occurrence became `%~dp0..`).

```bash
grep -n '\-u [a-z_]*\.py\|OUTPUT=[a-z]' tasks/run_ats_collector.bat tasks/run_ddg_collector.bat tasks/run_newgrad_collector.bat tasks/run_daily_report.bat tasks/run_enrich_companies.bat
```

Expected: every `.py` reference is prefixed `scripts\`, every `OUTPUT=`/`--output` value is prefixed `data\`.

- [ ] **Step 13: Commit**

```bash
git add -A tasks run_logged.bat run_ats_collector.bat run_ddg_collector.bat run_newgrad_collector.bat run_daily_report.bat run_enrich_companies.bat resolve_python.bat pause_scheduled_tasks.bat resume_scheduled_tasks.bat register_enrich_task.ps1 repoint_scheduled_tasks.ps1 retime_ddg12.ps1
git commit -m "Move Scheduled Task launchers into tasks/, fix cd and script/data paths"
```

---

## Task 11: Fix `tests/test_lane.py` and `tests/test_title_filter.py`, run the full suite

**Files:**
- Modify: `tests/test_lane.py`, `tests/test_title_filter.py`

**Interfaces:**
- Consumes: `paths.ROOT` (Task 2); `scripts/company_lane.py`, `scripts/dashboard.py`, `scripts/view.py` (Task 8)

- [ ] **Step 1: Fix `tests/test_lane.py`** — `company_lane`, `dashboard`, `view` are plain scripts (not installed packages), so they still need an explicit `sys.path` entry — now pointed at `scripts/` instead of the project root.

```python
# before
import contextlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import company_lane as CL           # noqa: E402
import dashboard as DASH            # noqa: E402
import view as VIEW                 # noqa: E402
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402

# after
import contextlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

import paths

sys.path.insert(0, str(paths.ROOT / "scripts"))

import company_lane as CL           # noqa: E402
import dashboard as DASH            # noqa: E402
import view as VIEW                 # noqa: E402
from job_collector.tracking.cost_tracker import LLMCostTracker   # noqa: E402
```

If this file references `ROOT` anywhere else (e.g. to build a fixture path), grep for `ROOT` in the rest of the file first and replace those usages with `paths.ROOT` too — do not leave a dangling `ROOT` name.

```bash
grep -n "\bROOT\b" tests/test_lane.py
```

- [ ] **Step 2: Fix `tests/test_title_filter.py`** — both its imports (`ats_direct.ng_filter`, `job_collector.classifiers.title_relevance`) are now installed packages; the manual `sys.path` hack is no longer needed at all.

```python
# before
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ats_direct.ng_filter import DROP, GRAY, KEEP, title_verdict   # noqa: E402
from job_collector.classifiers.title_relevance import (   # noqa: E402
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)

# after
import csv
import json
import os
import shutil
import tempfile
import unittest

from ats_direct.ng_filter import DROP, GRAY, KEEP, title_verdict
from job_collector.classifiers.title_relevance import (
    OpenAIChatClient,
    TitleAdjudicator,
    TitleFilter,
)
```

Check the rest of the file for other `os.path` uses that assumed `ROOT` (e.g. for fixture files under `tests/fixtures/`) — those should use `os.path.dirname(os.path.abspath(__file__))` (the test file's own directory, i.e. `tests/`) instead, which is unaffected by any of this reorg.

```bash
grep -n "\bROOT\b\|\bsys\b" tests/test_title_filter.py
```

Remove `import sys` too if nothing else in the file uses it after these edits.

- [ ] **Step 3: Run the full suite**

```
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -m unittest discover -s tests -v
```

Expected: same pass/fail counts as a run of this exact command taken **before** Task 1 started (capture that baseline first if it hasn't been captured yet — this is a reorg, not a behavior change, so no test's outcome should flip). F1/F2 in `test_lane.py` are skipped by default (`JOB_TEST_LLM` not set) in both runs.

- [ ] **Step 4: Commit**

```bash
git add tests/test_lane.py tests/test_title_filter.py
git commit -m "Repoint tests/ imports at scripts/ and paths.py after the reorg"
```

---

## Task 12: End-to-end smoke test of every collector from the new layout

No code changes in this task — this is the spec's step 5, verifying the reorganized-but-not-yet-moved project actually works before physically relocating it.

- [ ] **Step 1: ATS collector, small subset**

```
tasks\resolve_python.bat
%JOB_PYTHON% -u scripts\ats_direct.py --max-companies 3
```

Expected: runs to completion, prints a summary, and `data\ats_jobs.csv` + `state\ats_registry.json` show updated mtimes.

- [ ] **Step 2: DDG collector, one query**

```
%JOB_PYTHON% -u scripts\ddg_search.py --queries 1
```

Expected: runs to completion, `data\ddg_jobs.csv` mtime updates (or stays unchanged with a "no new results" message, which is normal for DDG).

- [ ] **Step 3: Newgrad/main.py collector, one query**

```
%JOB_PYTHON% -u scripts\main.py --query "software engineer new grad" --limit 5 --time-filter 120 --output data\newgrad_classifications.csv --exclude-senior
```

Expected: runs to completion, `data\newgrad_classifications.csv` mtime updates.

- [ ] **Step 4: Company enrichment**

```
%JOB_PYTHON% -u scripts\enrich_companies.py
```

Expected: runs to completion, `state\company_profiles.json` mtime updates (or "nothing to enrich" if the cache is already current).

- [ ] **Step 5: Daily report + dashboard**

```
%JOB_PYTHON% -u scripts\daily_report.py
%JOB_PYTHON% -u scripts\dashboard.py
```

Expected: both run to completion; `logs\dashboard\latest.html` regenerates and opens correctly in a browser (check it visually — company lanes, segments, and the trend chart should render exactly as before the reorg); `logs\last_report.json` mtime updates.

- [ ] **Step 6: Full task-wrapper smoke test** — run one collector through the actual `run_logged.bat` path, exactly as Task Scheduler will invoke it

```
tasks\run_logged.bat run_ats_collector
```

Expected: exits 0, a new `logs\run_ats_collector\<timestamp>.log` file appears with the run's output, and `logs\runs.jsonl` gets a matching `run_start`/`run_end` pair.

No commit — this task only runs commands and inspects output; nothing here is a source change.

---

## Task 13: Physical move to `D:\Dev\job-collector`

**Files:** none (filesystem operation)

- [ ] **Step 1: Confirm the working tree is clean**

```bash
git status --short
```

Expected: no output. If anything is dirty, stop and resolve it before moving (an uncommitted change left behind in a `git mv`-then-abandoned state is exactly the kind of thing this check exists to catch).

- [ ] **Step 2: Move**

```powershell
robocopy "D:\OneDrive\work\school\project\Job" "D:\Dev\job-collector" /E /MOVE /R:1 /W:1
```

`/E` copies all subdirectories including empty ones, `/MOVE` deletes the source after a successful copy, `/R:1 /W:1` keeps retry behavior from hanging indefinitely if OneDrive has a file locked (rerun the same command if it reports any failed files — `robocopy` is safe to resume, it skips files already copied unless their timestamps differ).

- [ ] **Step 3: Verify**

```powershell
Test-Path "D:\Dev\job-collector\.git"
Test-Path "D:\Dev\job-collector\pyproject.toml"
Test-Path "D:\OneDrive\work\school\project\Job"
```

Expected: first two `True`, last one `False` (source fully moved, not copied).

- [ ] **Step 4: Re-run the editable install from the new location and re-verify `paths.ROOT`**

```
cd "D:\Dev\job-collector"
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -m pip install -e .
"D:\Apps\Miniconda\envs\job-classifier\python.exe" -c "import paths; print(paths.ROOT)"
```

Expected: prints `D:\Dev\job-collector` (an editable install records an absolute path back to the source tree, so this must be re-run after the move — it will otherwise still point at the old, now-deleted, OneDrive path).

No commit — the git repository itself moved as a unit; nothing about its tracked content changed.

---

## Task 14: Repoint the 13 Scheduled Tasks, resume, verify

**Files:** none (Windows Task Scheduler state)

- [ ] **Step 1: Run the repoint script, elevated, from its new location**

```
cd "D:\Dev\job-collector\tasks"
```

Right-click PowerShell → Run as administrator, then:

```powershell
cd "D:\Dev\job-collector\tasks"
.\repoint_scheduled_tasks.ps1
```

Expected output: each of the 10 mapped tasks (`ATS_03`...`ATS_21`, `DDG_07`/`DDG_12`/`DDG_17`, `ng job collector`) reports `changed: <name> -> run_logged.bat <arg>`, and the final table shows every task's `Runs` column as `run_logged.bat` with `NextRun` unchanged from before the move.

- [ ] **Step 2: Repoint the two tasks `repoint_scheduled_tasks.ps1` doesn't cover** — `Job - Daily Report` and `Job - Enrich Companies` were registered directly (not through the `run_logged.bat <name>` wrapper map), per `pause_scheduled_tasks.bat`'s task list. Re-register `Job - Enrich Companies` with the new path:

```powershell
.\register_enrich_task.ps1
```

Expected: `Registered 'Job - Enrich Companies' -> run_logged.bat run_enrich_companies, daily 07:30`.

For `Job - Daily Report`, check what it currently points at and fix it the same way `repoint_scheduled_tasks.ps1` fixes the others:

```powershell
(Get-ScheduledTask -TaskName 'Job - Daily Report').Actions
```

If its `Execute`/`WorkingDirectory` still shows the old OneDrive path, update it:

```powershell
$action = New-ScheduledTaskAction -Execute 'D:\Dev\job-collector\tasks\run_logged.bat' `
                                  -Argument 'run_daily_report' `
                                  -WorkingDirectory 'D:\Dev\job-collector'
Set-ScheduledTask -TaskName 'Job - Daily Report' -Action $action
```

- [ ] **Step 3: Resume all tasks**

```
tasks\resume_scheduled_tasks.bat
```

A UAC prompt appears — approve it. Wait for "Done. All tasks enabled."

- [ ] **Step 4: Verify state and next-run times**

```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -match '^(ATS_|DDG_|ng job collector|Job - )' } |
    ForEach-Object {
        $info = $_ | Get-ScheduledTaskInfo
        [PSCustomObject]@{ Task = $_.TaskName; State = $_.State; NextRun = $info.NextRunTime }
    } | Sort-Object Task | Format-Table -AutoSize
```

Expected: every task `State: Ready`, `NextRun` populated with a sensible upcoming time.

- [ ] **Step 5: Watch the next live run land correctly** — wait for the next naturally-scheduled task to fire (or manually trigger one: `Start-ScheduledTask -TaskName 'ATS_15'`, adjusting to whichever task is next), then check:

```powershell
Get-Content "D:\Dev\job-collector\logs\runs.jsonl" -Tail 4
```

Expected: a fresh `run_start`/`run_end` pair for that task, `exit_code: 0`.

No commit — this task only touches Windows Task Scheduler state and observes log output.

---

## Task 15: Decide on the old OneDrive folder

This is a conversation with the user, not a coding task — `Task 13`'s `robocopy /MOVE` already deleted the source directory once it confirmed every file copied successfully, so by this point there is nothing left at the old path to decide about. Confirm that with the user and close out the migration (update any bookmarks/shortcuts they have pointing at the old path, if they mention any).

---

## Self-Review Notes

- **Spec coverage:** every numbered item in the spec's "Execution order" (pause → commit already done in a prior session → GitHub push already done in a prior session → reorganize in place → smoke-test → move → repoint → resume → decide) maps to Tasks 1, 8-9 (already complete before this plan), 2-11, 12, 13, 14, 15 respectively. The `paths.py`/`pyproject.toml` design section maps to Task 2. The task-launcher rule maps to Task 10. The full file-inventory table in the spec is covered across Tasks 3-10 (every row's destination matches).
- **Placeholder scan:** no TBD/TODO; every code step shows real before/after content read from the actual current files, not descriptions of changes.
- **Type consistency:** `paths.ROOT`/`DATA_DIR`/`CONFIG_DIR`/`STATE_DIR` are used with identical names and `Path` semantics everywhere they appear across Tasks 3-11; every call site that needs a `str` wraps with `str(...)` explicitly rather than relying on implicit coercion.
