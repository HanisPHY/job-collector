# Scheduling & Logging

Three collectors run on a schedule, each writing to its own CSV:

| Wrapper argument | Collector | Output CSV | Suggested schedule |
|---|---|---|---|
| `run_newgrad_collector` | LinkedIn via JobSpy, 9 queries per run | `newgrad_classifications.csv` | every 60 min |
| `run_ats_collector` | company ATS APIs (Greenhouse, Lever, Ashby, ...) | `ats_jobs.csv` | every 6-12 hours |
| `run_ddg_collector` | DuckDuckGo X-ray discovery | `ddg_jobs.csv` | 2-3 times per day, **never hourly** |
| `run_daily_report` | reads the above, writes the daily report | `logs/daily/*.md` | once a day, e.g. 08:00 |

> `run_job_collector.bat` (the old "software engineer intern" search) is **deprecated**.
> It has no `--output`, so it writes into the default `job_classifications.csv`, which
> nothing else reads and whose last entry is from 2026-02. It is not covered by the
> logging system. Delete it or repoint it before relying on it again.

---

## Always schedule through `run_logged.bat`

Never point Task Scheduler at a collector `.bat` directly. `run_logged.bat` wraps it and:

- captures all stdout/stderr into `logs/<script_name>/<timestamp>.log`
- appends a `run_start` / `run_end` pair (with the exit code) to `logs/runs.jsonl`
- sets `PYTHONUTF8=1` — **required**. Once output is redirected to a file, Python falls
  back from the console's UTF-8 to the ANSI locale (cp1252 here), and printing a
  `company_type` containing CJK characters raises `UnicodeEncodeError` mid-run.
- sets `JOB_UNATTENDED=1` so the collectors skip their double-click hold-open guard.
  Task Scheduler launches the script as `cmd /c "...\run_ats_collector.bat"`, so
  the guard's `find` matches the script name in `%cmdcmdline%` and the guard fires. With
  no interactive console attached it returns immediately rather than blocking, but
  skipping it outright is cleaner - and the guard now uses `timeout /t 30` instead of
  `pause`, so it stays bounded even if a task is ever configured to run interactively.
- sets `JOB_RUN_ID`, which ties all 9 `main.py` invocations of one new-grad run
  together in `runs.jsonl`.

Manual runs work the same way:

```
run_logged.bat run_ats_collector
```

Double-clicking a collector `.bat` directly still works and still holds the window
open for 30 seconds at the end; it just doesn't produce a log file.

---

## No `conda activate` in scheduled scripts

The five scheduled `.bat` files resolve the interpreter through
**`resolve_python.bat`** and then call `"%JOB_PYTHON%" -u script.py`. None of them
calls `conda activate` any more.

**Why.** `conda activate` writes `%TEMP%\__conda_tmp_<pid>.txt`, which is not safe
against two tasks starting in the same second. On 2026-08-20 `ATS_12` and `DDG_12`
both fired at 12:00:00 and DDG_12 died before collecting anything:

```
The process cannot access the file because it is being used by another process.
The system cannot find the file C:\...\Temp\__conda_tmp_9245.txt
Error: Failed to activate conda environment 'job-classifier'
```

Calling the environment's `python.exe` directly needs no temp file, no PATH surgery
and no subshell, so concurrent tasks cannot collide. Verified with 8 simultaneous
resolutions.

`resolve_python.bat` also sets `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` before
returning. `run_logged.bat` already sets them, but these scripts are also
double-clicked, and then the console is cp1252: `dashboard.py` printing its circled
segment numbers (`①`) dies with `UnicodeEncodeError`.

To point at a different interpreter — a moved env, a test env — set `JOB_PYTHON`
before calling; an existing value that exists on disk is kept. Otherwise it probes,
in order:

```
D:\Apps\Miniconda\envs\job-classifier\python.exe      <- current
%USERPROFILE%\miniconda3\envs\job-classifier\python.exe
%USERPROFILE%\anaconda3\envs\job-classifier\python.exe
C:\ProgramData\miniconda3\envs\job-classifier\python.exe
```

`setup_environment.bat` still uses conda, correctly — it is what creates the env,
runs interactively, and never runs concurrently.

---

## ⚠ Two collectors must not run at once

`ats_direct.py --expand` and `ddg_search.py --update-registry` both
read-modify-write **`ats_registry.json`**, and `Registry.save()` writes a fixed
`<path>.tmp` then `os.replace()`s it. Concurrent runs do not corrupt the file — they
**lose updates**: whichever finishes last overwrites the other's newly discovered
boards, silently and with no error anywhere.

Each run takes about six minutes (ATS `elapsed_s 367.6`; DDG 17:00:02 → 17:05:57),
so a 12:00/12:00 pairing overlaps for its entire duration. Keep DDG off the ATS
grid (`03/06/09/12/15/18/21`). `retime_ddg12.ps1` moves `DDG_12` to 13:00, which
sits between ATS_12 finishing (~12:06) and ATS_15.

Run it **elevated** — see the next section for why:

```powershell
cd "D:\OneDrive\work\school\project\Job"
.\retime_ddg12.ps1 -WhatIf     # preview
.\retime_ddg12.ps1             # do it
```

---

## Windows Task Scheduler

### Existing tasks need repointing

Eleven enabled tasks were registered to run the collector scripts **directly**, so their
runs produce no log file and no `runs.jsonl` record:

```
ATS_03 ATS_06 ATS_09 ATS_12 ATS_15 ATS_18 ATS_21   -> run_ats_collector.bat
DDG_07 DDG_12 DDG_17                                -> run_ddg_collector.bat
ng job collector                                    -> run_newgrad_collector.bat
Job collector                                       -> run_job_collector.bat  (disabled, deprecated)
```

`repoint_scheduled_tasks.ps1` fixes them. It backs each definition up to
`logs\_task_backup\<name>.xml`, swaps only the ACTION to `run_logged.bat <collector>`,
then prints a verification table. Triggers, conditions, principal and run history are
untouched, and re-running it is a no-op on tasks already pointing at the wrapper.

**It must run elevated.** These tasks' security descriptors only permit an administrator
to modify them - an ordinary session gets `Access is denied` from both
`Set-ScheduledTask` and `schtasks /change`. (Registering a *new* task does not need
elevation; only modifying these existing ones does.)

Open PowerShell with **Run as administrator**, then:

```powershell
cd "D:\OneDrive\work\school\project\Job"
.\repoint_scheduled_tasks.ps1 -WhatIf     # preview, changes nothing
.\repoint_scheduled_tasks.ps1             # do it
```

To roll back, from an elevated prompt:

```powershell
Get-ChildItem "logs\_task_backup" -Filter *.xml | ForEach-Object {
    Register-ScheduledTask -Xml (Get-Content $_.FullName -Raw) -TaskName $_.BaseName -Force
}
```

### The daily report task

Already registered as **Job - Daily Report**, running `run_logged.bat run_daily_report`
daily at 08:00. Creating it needed no elevation. To recreate it from scratch:

```powershell
$dir = "D:\OneDrive\work\school\project\Job"
$action   = New-ScheduledTaskAction -Execute "$dir\run_logged.bat" -Argument "run_daily_report"
$trigger  = New-ScheduledTaskTrigger -Daily -At 8am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "Job - Daily Report" -Action $action -Trigger $trigger `
                       -Settings $settings
```

It also runs `dashboard.py` after `daily_report.py` — one task produces both the
markdown report and the HTML dashboard.

**`StartWhenAvailable` matters here.** It was `False` until 2026-08-21, which means a
laptop asleep at 08:00 lost that day's report entirely: Task Scheduler skips the
occurrence rather than catching up, and nothing anywhere says so. With it on, the run
happens as soon as the machine is available again. Changing it needed no elevation
(the task was registered by the current user):

```powershell
$t = Get-ScheduledTask -TaskName 'Job - Daily Report'
$t.Settings.StartWhenAvailable = $true
Set-ScheduledTask -TaskName 'Job - Daily Report' -Settings $t.Settings
```

The collector tasks are still `StartWhenAvailable = False`, deliberately — they run
every 1-3 hours, so a missed occurrence is picked up by the next one, and catching up
several at once on wake would just stampede the same APIs.

### The company-enrichment task

`run_daily_report.bat` now runs `dashboard.py` after `daily_report.py` (as its own
statement, so a failing report cannot skip the dashboard). The dashboard segments
jobs using `company_profiles.json`, which `enrich_companies.py` tops up — schedule it
at **07:30**, half an hour ahead of the 08:00 report. No elevation needed:

```powershell
cd "D:\OneDrive\work\school\project\Job"
.\register_enrich_task.ps1        # run_logged.bat run_enrich_companies, daily 07:30
```

Only companies missing from the cache are sent to the API, so a normal morning is a
few dozen names at roughly **$0.02**, and the whole run is capped at **300 s** of wall
clock — whatever does not fit stays unclassified and is retried the next day (the
dashboard says how many at the top). Monthly manual catch-up, deliberately *not*
scheduled: `python -u enrich_companies.py --deep` (gpt-4o, about $0.17; it recovers
intermediary labels that gpt-4o-mini misses).

Output: a self-contained bundle in `logs/dashboard/` — `latest.html` (the only HTML
file; that is the one to double-click), `dashboard.css`, `dashboard.js`,
`data-index.js` and one `data-<day>.js` block per natural day inside the 30-day
retention window — plus the read watermark in `logs/last_report.json`. There is no
per-day HTML page any more: a pinned page would keep pointing at data blocks that get
rewritten every morning, so it would silently re-judge rows. For a frozen snapshot run
`python -u dashboard.py --date YYYY-MM-DD --out <dir>`, which writes the whole bundle
recomputed under that anchor into a directory of its own.

### Creating a task from scratch (GUI)

1. `Win + R` -> `taskschd.msc` -> **Create Basic Task**
2. Name it, click Next
3. Trigger: **Daily**, start today, recur every 1 day -> Next
4. Action: **Start a program**
   - Program/script: `D:\OneDrive\work\school\project\Job\run_logged.bat`
   - **Add arguments**: the collector name, e.g. `run_newgrad_collector`
   - **Start in**: `D:\OneDrive\work\school\project\Job`
5. Check "Open the Properties dialog..." -> Finish
6. **Triggers** tab -> Edit -> check "Repeat task every" -> e.g. `1 hour`, duration `Indefinitely`
7. **Settings** tab -> check "Run task as soon as possible after a scheduled start is missed"

### Checking on them

```powershell
Get-ScheduledTask | Where-Object { ($_.Actions | Where-Object { $_.Execute -like "*project*Job*" }) } |
  ForEach-Object { $i = $_ | Get-ScheduledTaskInfo
    [PSCustomObject]@{ Task=$_.TaskName; LastRun=$i.LastRunTime; Result=$i.LastTaskResult } } |
  Format-Table -AutoSize
```

`Result` 0 means the last run exited cleanly. Any collector still pointed at its `.bat`
directly will show up in the daily report as `ran 0 time(s)` even when it did run - it
just produced no records. To silence a collector you have deliberately disabled, set
`enabled: False` for it in `EXPECTED_SCRIPTS` at the top of `daily_report.py`.

Keep `--time-filter` roughly double the schedule interval (the new-grad batch uses 120
minutes on an hourly schedule) so a skipped or delayed run doesn't leave a coverage gap.

---

## What lands where

```
logs/
  runs.jsonl                                  <- the only file the report parses
  run_newgrad_collector/2026-08-20_14-00-03.log
  run_ats_collector/2026-08-20_06-00-12.log
  run_ddg_collector/2026-08-20_09-00-05.log
  run_daily_report/2026-08-20_08-00-01.log
  daily/2026-08-20.md                         <- the report
```

`runs.jsonl` holds one JSON object per line:

- `run_start` / `run_end` — written by `run_logged.bat`. A `run_start` with no matching
  `run_end` means the run was killed or crashed hard.
- `run_summary` — written by the Python entry points via `run_log.py`, one per
  invocation (so nine per new-grad run), carrying that collector's own counters:
  `jobs_fetched`, `jobs_matched`, `new_jobs`, `http_errors`, `rate_limit_hits`,
  `challenges`, `elapsed_s`, `llm_cost_usd` / `llm_api_calls` / `llm_tokens` /
  `llm_model` on the LinkedIn path, and `error` / `traceback` on a crash.

The `.log` files are never parsed — they exist so you can read the raw output when the
report points you at one.

### ⚠ OneDrive

`logs/` sits inside the OneDrive-synced tree. The new-grad collector alone produces
roughly 1-3 MB of log per day, and OneDrive briefly locks files while uploading, which
can collide with the atomic `os.replace()` calls the collectors use. Either exclude
`logs/` from sync in the OneDrive settings, or move it entirely:

```
setx JOB_LOG_ROOT "%LOCALAPPDATA%\JobCollector\logs"
```

`run_log.py` and `daily_report.py` both honour `JOB_LOG_ROOT`.

---

## The daily report

```
python daily_report.py                    # today
python daily_report.py --date 2026-08-19  # a specific day
python daily_report.py --no-prune         # keep .log files older than 30 days
```

Writes `logs/daily/YYYY-MM-DD.md` and prints a summary. Three sections:

1. **今日待投** — jobs first recorded today whose `applied` column is still empty,
   grouped by company, Big Tech / unicorn / public companies first. Mark a job as
   applied by putting anything in its `applied` cell in the CSV and it drops off
   tomorrow's list.
2. **健康告警** — a collector that didn't run, a non-zero exit code, a run that never
   finished, zero new jobs all day, rate-limiting, or a mismatch between what the
   collectors reported writing and what is actually in the CSVs.
3. **运行概况** — one line per run with its counters, LLM cost, and log path.

### LLM cost

Only the LinkedIn path calls an LLM, and only to classify companies it has not seen
before; the ATS and DDG collectors never do. Spend runs a few cents a day at
`gpt-3.5-turbo` rates. The report shows the day's total against yesterday's in section 1,
the per-run figure in section 3, and raises an alert above
`LLM_DAILY_COST_ALERT_USD` (default $0.50) — a threshold that only trips if call volume
or the model changes.

`LLMCostTracker.MODEL_PRICING` in
[job_collector/tracking/cost_tracker.py](job_collector/tracking/cost_tracker.py) holds the
per-1K-token rates. **If you switch to a model that is not in that table, the cost comes
back as `None`** and the report labels those runs "unpriced" rather than billing them at
`gpt-3.5-turbo` rates — a wrong number presented as fact is worse than a missing one. Add
the model's rates to the table to restore the figure.

Job counts come from the `date_recorded` column of the CSVs, not from the logs — that
column is the first-seen timestamp and is preserved verbatim when a CSV is rewritten.
Rows are deduplicated by `unique_id` across all three files, because `ddg_search`
discovers ATS boards and genuinely re-finds jobs that `ats_direct` already has.

Sponsorship status is only a real classification on the `ats_direct` path. `ddg_search`
hardcodes `Not (Maybe Not) Sponsor` (a search results page has no job description) and
the LinkedIn path rarely finds a positive signal — read those as *unknown*, not as *no*.

Each report run also deletes `.log` files older than 30 days. `runs.jsonl` and the
reports themselves are never pruned.

---

## Troubleshooting

**Task runs but nothing happens** — open the newest file under `logs/<script>/`. If it's
empty, the failure is before Python started: check that "Start in" is set to the project
directory and that `conda` is on the PATH of the account running the task.

**A collector window that never closes** - the collector scripts end with a hold-open
guard for double-click use. Double-clicked from Explorer it waits, by design: press a
key or wait 30 seconds. Scheduled runs skip it entirely when launched through
`run_logged.bat`. If you find `cmd.exe` processes parented to `explorer.exe` lingering
for hours, those are double-clicked runs sitting on the guard - `taskkill /pid <id>`
clears them.

**`conda` not found** — either add conda to the system PATH, or replace
`call conda activate job-classifier` in the collector script with the full path:
`call C:\Users\<you>\anaconda3\Scripts\activate.bat job-classifier`

**Report says a count mismatch** — compare the `new_jobs` totals in `runs.jsonl` against
the CSV rows for that day. Common causes: a long ATS run that started before midnight
(its jobs are all stamped with the start date), or a CSV edited outside the pipeline.

**`RuntimeError: Could not read existing file ...`** — the CSV is corrupt or locked
(OneDrive, or open in Excel). The pipeline refuses to continue rather than rewrite the
file from the current batch, which would erase the history and the `applied` column.
Close the file or restore it, then re-run.
