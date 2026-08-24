@echo off
REM DEPRECATED batch script for the old "software engineer intern" search.
REM Superseded by tasks\run_logged.bat run_newgrad_collector - see SCHEDULING.md.

REM Change to the project root - the scripts live under scripts/ since the reorg.
cd /d "%~dp0.."

REM Activate conda environment and run the script
call conda activate job-classifier
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate conda environment 'job-classifier'
    echo Make sure conda is installed and the environment exists
    pause
    exit /b %ERRORLEVEL%
)

python scripts\main.py --query "software engineer intern" --limit 50 --time-filter 20
REM To disable LLM classification (faster, less accurate), add --no-llm flag above

REM Optional: Log the output to a file
REM call conda activate job-classifier && python scripts\main.py --query "software engineer" --limit 50 --time-filter 30 >> job_collector.log 2>&1

REM Note: Remove 'pause' if running from Task Scheduler (it will hang)
REM Keep window open if there's an error (optional, remove if you want it to close automatically)
if %ERRORLEVEL% NEQ 0 (
    echo Error occurred. Exit code: %ERRORLEVEL%
    REM pause  REM Commented out for Task Scheduler - uncomment for manual testing
)

