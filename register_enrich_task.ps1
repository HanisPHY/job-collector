<#
.SYNOPSIS
    Register the daily company-enrichment task at 07:30.

.DESCRIPTION
    Creates (or updates) a scheduled task that runs

        run_logged.bat run_enrich_companies

    every day at 07:30, i.e. half an hour before the 08:00 daily report, so the
    dashboard sees the day's new companies already classified.

    Registering a task that runs as the CURRENT user needs no elevation - unlike
    repoint_scheduled_tasks.ps1, which modifies tasks somebody else registered.

.EXAMPLE
    cd "D:\OneDrive\work\school\project\Job"
    .\register_enrich_task.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $TaskName = 'Job - Enrich Companies',
    [string] $At       = '07:30'
)

$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

$action    = New-ScheduledTaskAction -Execute (Join-Path $dir 'run_logged.bat') `
                                     -Argument 'run_enrich_companies' `
                                     -WorkingDirectory $dir
$trigger   = New-ScheduledTaskTrigger -Daily -At $At
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable `
                                          -DontStopIfGoingOnBatteries `
                                          -AllowStartIfOnBatteries `
                                          -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

if ($PSCmdlet.ShouldProcess($TaskName, "register daily at $At")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                           -Settings $settings -Force | Out-Null
    Write-Host "Registered '$TaskName' -> run_logged.bat run_enrich_companies, daily $At"
    Get-ScheduledTask -TaskName $TaskName |
        Select-Object TaskName, State, @{n='NextRun';e={ ($_ | Get-ScheduledTaskInfo).NextRunTime }}
}

# Rollback:  Unregister-ScheduledTask -TaskName 'Job - Enrich Companies' -Confirm:$false
