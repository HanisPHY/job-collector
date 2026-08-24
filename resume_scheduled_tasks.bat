@echo off
REM Re-enables all job collector scheduled tasks. Requires admin - self-elevates.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

schtasks /change /tn "ATS_03" /enable
schtasks /change /tn "ATS_06" /enable
schtasks /change /tn "ATS_09" /enable
schtasks /change /tn "ATS_12" /enable
schtasks /change /tn "ATS_15" /enable
schtasks /change /tn "ATS_18" /enable
schtasks /change /tn "ATS_21" /enable
schtasks /change /tn "DDG_07" /enable
schtasks /change /tn "DDG_12" /enable
schtasks /change /tn "DDG_17" /enable
schtasks /change /tn "ng job collector" /enable
schtasks /change /tn "Job - Daily Report" /enable
schtasks /change /tn "Job - Enrich Companies" /enable

echo.
echo Done. All tasks enabled.
pause
