@echo off
REM Daily report over the collector runs.
REM
REM Schedule this once a day (e.g. 08:00) via run_logged.bat:
REM   Program:   run_logged.bat
REM   Arguments: run_daily_report
REM See SCHEDULING.md.

cd /d "%~dp0"

REM Resolve the interpreter without `conda activate` - see resolve_python.bat
REM for why (concurrent tasks race on conda's %TEMP% file).
call "%~dp0resolve_python.bat"
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

"%JOB_PYTHON%" -u daily_report.py

if %ERRORLEVEL% NEQ 0 (
    echo Error occurred. Exit code: %ERRORLEVEL%
)

REM The HTML dashboard runs unconditionally, NOT chained behind the markdown report:
REM they read the same CSVs but nothing else is shared, and a failure in one must not
REM take the other down. Keep this as its own statement, never `&&`.
"%JOB_PYTHON%" -u dashboard.py

if %ERRORLEVEL% NEQ 0 (
    echo Dashboard error. Exit code: %ERRORLEVEL%
)

REM Hold the window open when double-clicked from Explorer.
REM
REM Task Scheduler launches this as cmd /c "...<script>.bat", so %cmdcmdline% does
REM contain the script name and the find below matches there too. With no interactive
REM console attached the wait returns immediately, but run_logged.bat sets
REM JOB_UNATTENDED to skip it outright, and `timeout` rather than `pause` keeps it
REM bounded in every case.
if not defined JOB_UNATTENDED (echo %cmdcmdline% | find /i "%~0" >nul && timeout /t 30)
