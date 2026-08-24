@echo off
REM Logging wrapper for the collector batch scripts.
REM
REM Usage:  run_logged.bat <script_name>        (without the .bat extension)
REM   e.g.  run_logged.bat run_ats_collector
REM
REM Point Windows Task Scheduler at THIS file and pass the collector name as
REM the argument - see SCHEDULING.md. The collector scripts themselves stay
REM unchanged; everything they print lands in logs\<script_name>\<ts>.log and
REM a run_start/run_end pair lands in logs\runs.jsonl for daily_report.py.

cd /d "%~dp0.."

if "%~1"=="" (
    echo Usage: run_logged.bat ^<script_name^>
    exit /b 2
)
if not exist "%~dp0%~1.bat" (
    echo Error: %~1.bat not found in %~dp0
    exit /b 2
)

REM PowerShell is the only locale-independent way to get a sortable timestamp
REM here - %DATE% follows the regional format and WMIC is gone on Win11 26200.
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "TS=%%T"
if not defined TS set "TS=unknown_%RANDOM%"

if not exist "logs\%~1" mkdir "logs\%~1"

set "JOB_RUN_ID=%TS%"
REM Tells the collector scripts to skip their double-click 'pause' guard.
set "JOB_UNATTENDED=1"
REM Critical: once stdout is redirected to a file, Python drops from the
REM console's UTF-8 back to the ANSI locale (cp1252 here) and printing a
REM company_type containing CJK characters raises UnicodeEncodeError.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "RUN_LOG=logs\%~1\%TS%.log"

REM JSON written straight from batch: every field is ASCII, and backslashes in
REM the path are swapped for forward slashes so the line stays valid JSON.
>>"logs\runs.jsonl" echo {"kind":"run_start","script":"%~1","run_id":"%TS%","log":"%RUN_LOG:\=/%"}

call "%~dp0%~1.bat" >>"%RUN_LOG%" 2>&1
set "RC=%ERRORLEVEL%"

>>"logs\runs.jsonl" echo {"kind":"run_end","script":"%~1","run_id":"%TS%","exit_code":%RC%}

echo Log: %RUN_LOG%
exit /b %RC%
