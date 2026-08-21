@echo off
REM Company enrichment - tops up company_profiles.json for the HTML dashboard.
REM
REM Schedule once a day at 07:30 via run_logged.bat, i.e. BEFORE run_daily_report
REM (08:00) so the dashboard sees today's new companies already classified:
REM   Program:   run_logged.bat
REM   Arguments: run_enrich_companies
REM Registering it needs no elevation - see register_enrich_task.ps1.
REM
REM Only companies missing from the cache are sent to the API, so the steady-state
REM day is a few dozen names and about $0.02. The whole run is capped at 300 s of
REM wall clock; whatever does not fit stays stage 0 and is retried tomorrow.
REM
REM Monthly manual catch-up (gpt-4o, ~$0.17, recovers intermediary labels that
REM gpt-4o-mini misses) - NOT part of this scheduled run:
REM     python -u enrich_companies.py --deep

cd /d "%~dp0"

REM Resolve the interpreter without `conda activate` - see resolve_python.bat
REM for why (concurrent tasks race on conda's %TEMP% file).
call "%~dp0resolve_python.bat"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

"%JOB_PYTHON%" -u enrich_companies.py

if %ERRORLEVEL% NEQ 0 (
    echo Error occurred. Exit code: %ERRORLEVEL%
)

REM Hold the window open when double-clicked from Explorer.
if not defined JOB_UNATTENDED (echo %cmdcmdline% | find /i "%~0" >nul && timeout /t 30)
