@echo off
REM Batch script to collect FULL-TIME NEW GRAD SWE jobs
REM Runs multiple search queries because new grad roles have no single
REM standard title. Duplicates across queries are handled automatically
REM by the unique_id dedup logic, so overlapping queries are safe.
REM
REM Intended schedule: every 60 minutes (see SCHEDULING.md)

cd /d "%~dp0"

call conda activate job-classifier
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate conda environment 'job-classifier'
    echo Make sure conda is installed and the environment exists
    exit /b %ERRORLEVEL%
)

REM Time filter is 120 minutes while the scheduler runs hourly, so a delayed
REM or skipped run does not create a gap in coverage.
set TIMEFILTER=120
set LIMIT=50
set OUTPUT=newgrad_classifications.csv

REM Tier 1: high-precision new grad keywords
for %%Q in (
    "software engineer new grad"
    "software engineer 2027"
    "software engineer university graduate"
    "software engineer entry level"
) do (
    echo.
    echo ============================================================
    echo Query: %%~Q
    echo ============================================================
    python main.py --query %%~Q --limit %LIMIT% --time-filter %TIMEFILTER% --output %OUTPUT% --exclude-senior
)

REM Tier 2: catches big-tech new grad roles whose titles carry no
REM "new grad" marker (Amazon SDE I, Uber SWE I, Twitch SWE I, etc).
REM --exclude-senior is essential here to drop the senior/staff noise.
for %%Q in (
    "software engineer I"
    "software development engineer I"
    "associate software engineer"
) do (
    echo.
    echo ============================================================
    echo Query: %%~Q
    echo ============================================================
    python main.py --query %%~Q --limit %LIMIT% --time-filter %TIMEFILTER% --output %OUTPUT% --exclude-senior
)

REM Tier 3: supplementary phrasings
for %%Q in (
    "software engineer early career"
    "software engineer college graduate"
) do (
    echo.
    echo ============================================================
    echo Query: %%~Q
    echo ============================================================
    python main.py --query %%~Q --limit %LIMIT% --time-filter %TIMEFILTER% --output %OUTPUT% --exclude-senior
)

echo.
echo All new grad queries complete. Results in %OUTPUT%
