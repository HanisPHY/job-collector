@echo off
REM DDG X-ray discovery collector - for Windows Task Scheduler
REM Suggested schedule: 2-3 times per DAY maximum (NOT hourly).
REM DDG rate-challenges aggressively; see ddg_search/RATE_LIMITS.md.
REM Yield is intermittent by design - its main job is discovering new
REM company boards and feeding them into ats_registry.json.

cd /d "%~dp0"

echo [%TIME%] Starting DDG collector...
echo.


call conda activate job-classifier
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate conda environment 'job-classifier'
    exit /b %ERRORLEVEL%
)

python -u ddg_search.py --queries 5 --update-registry --output ddg_jobs.csv

if %ERRORLEVEL% NEQ 0 (
    echo Error occurred. Exit code: %ERRORLEVEL%
)

REM Hold the window open when double-clicked from Explorer.
REM
REM Task Scheduler launches this as cmd /c "...<script>.bat", so %cmdcmdline% does
REM contain the script name and the find below matches there too. With no interactive
REM console attached the wait returns immediately, but run_logged.bat sets
REM JOB_UNATTENDED to skip it outright, and `timeout` rather than `pause` keeps it
REM bounded in every case.
if not defined JOB_UNATTENDED (echo %cmdcmdline% | find /i "%~0" >nul && timeout /t 30)
