@echo off
REM Disables all job collector scheduled tasks. Requires admin - self-elevates.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

schtasks /change /tn "ATS_03" /disable
schtasks /change /tn "ATS_06" /disable
schtasks /change /tn "ATS_09" /disable
schtasks /change /tn "ATS_12" /disable
schtasks /change /tn "ATS_15" /disable
schtasks /change /tn "ATS_18" /disable
schtasks /change /tn "ATS_21" /disable
schtasks /change /tn "DDG_07" /disable
schtasks /change /tn "DDG_12" /disable
schtasks /change /tn "DDG_17" /disable
schtasks /change /tn "ng job collector" /disable
schtasks /change /tn "Job - Daily Report" /disable
schtasks /change /tn "Job - Enrich Companies" /disable

echo.
echo Done. All tasks disabled.
pause
