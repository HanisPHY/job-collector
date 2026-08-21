@echo off
REM Sets JOB_PYTHON to the job-classifier interpreter and returns 0, or prints
REM what went wrong and returns 1.
REM
REM Why not `conda activate job-classifier`?
REM   It writes %TEMP%\__conda_tmp_<pid>.txt, and that is not safe against two
REM   scheduled tasks starting in the same second. ATS_12 and DDG_12 both fire at
REM   12:00, and on 2026-08-20 DDG_12 died on exactly this:
REM       The process cannot access the file because it is being used by another process.
REM       The system cannot find the file C:\...\Temp\__conda_tmp_9245.txt
REM       Error: Failed to activate conda environment 'job-classifier'
REM   Calling the environment's python.exe directly needs no temp file, no PATH
REM   surgery and no subshell, so concurrent tasks cannot collide.
REM
REM Callers: run_ats_collector, run_ddg_collector, run_newgrad_collector,
REM          run_daily_report, run_enrich_companies.
REM   call "%~dp0resolve_python.bat"
REM   if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
REM   "%JOB_PYTHON%" -u your_script.py
REM
REM Deliberately no `setlocal` - the whole point is to leave JOB_PYTHON set in the
REM caller's environment. Set JOB_PYTHON yourself beforehand to override, e.g. to
REM test against another interpreter; an existing value that exists is kept.

REM UTF-8 for stdout. run_logged.bat already sets these, but these scripts are also
REM double-clicked, and then the console is cp1252 here: dashboard.py printing its
REM segment numbers (the circled digits) dies with UnicodeEncodeError. Set before the
REM early return so an inherited JOB_PYTHON still gets them.
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
if not defined PYTHONIOENCODING set "PYTHONIOENCODING=utf-8"

if defined JOB_PYTHON if exist "%JOB_PYTHON%" exit /b 0

for %%P in (
    "D:\Apps\Miniconda\envs\job-classifier\python.exe"
    "%USERPROFILE%\miniconda3\envs\job-classifier\python.exe"
    "%USERPROFILE%\anaconda3\envs\job-classifier\python.exe"
    "C:\ProgramData\miniconda3\envs\job-classifier\python.exe"
) do (
    if exist %%P (
        set "JOB_PYTHON=%%~P"
        goto :found
    )
)

echo Error: could not find the 'job-classifier' interpreter.
echo Looked for python.exe under:
echo    D:\Apps\Miniconda\envs\job-classifier
echo    %USERPROFILE%\miniconda3\envs\job-classifier
echo    %USERPROFILE%\anaconda3\envs\job-classifier
echo    C:\ProgramData\miniconda3\envs\job-classifier
echo If the environment moved, set JOB_PYTHON to its python.exe.
exit /b 1

:found
exit /b 0
