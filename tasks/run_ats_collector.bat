@echo off
REM ATS-direct NG SDE collector - for Windows Task Scheduler
REM Suggested schedule: every 6-12 hours (ATS boards change slowly;
REM hourly polling would waste requests without finding new jobs)

cd /d "%~dp0.."

echo [%TIME%] Starting ATS collector...
echo Registry has ~225 companies; --cleanup re-validates each at ~1 req/s,
echo so a full run takes several minutes. Progress prints as it goes.
echo.


REM Resolve the interpreter without `conda activate` - see resolve_python.bat
REM for why (concurrent tasks race on conda's %TEMP% file).
call "%~dp0resolve_python.bat"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

REM Weekly maintenance flags (cheap to run every time; cleanup re-validates
REM boards ~1 req/company, expand is 2 GitHub fetches + probes for new boards)
"%JOB_PYTHON%" -u scripts\ats_direct.py --cleanup --expand --output data\ats_jobs.csv

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
