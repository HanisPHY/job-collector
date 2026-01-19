@echo off
REM Setup script for Windows to create Conda environment

echo ========================================
echo Job Classification System - Setup
echo ========================================
echo.

echo Creating Conda environment...
conda env create -f environment.yml

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error creating environment. Trying alternative method...
    conda create -n job-classifier python=3.10 -y
    call conda activate job-classifier
    pip install -r requirements.txt
) else (
    echo.
    echo Environment created successfully!
    echo.
    echo To activate the environment, run:
    echo   conda activate job-classifier
    echo.
    echo Next steps:
    echo   1. Install ChromeDriver (see README.md)
    echo   2. Optionally set OPENAI_API_KEY environment variable
    echo   3. Run: python job_collector.py --query "software engineer"
)

pause

