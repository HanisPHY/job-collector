<#
.SYNOPSIS
    Move DDG_12 off its 12:00 collision with ATS_12.

.DESCRIPTION
    ATS_12 and DDG_12 both fire at 12:00:00 and both run for about six minutes
    (ATS elapsed_s 367.6; DDG 17:00:02 -> 17:05:57 on 2026-08-20), so they overlap
    for their entire run. Two problems came out of that:

      1. Both called `conda activate`, which writes %TEMP%\__conda_tmp_<pid>.txt.
         DDG_12 lost the race on 2026-08-20 and exited 3 without collecting
         anything. FIXED separately - the collectors now resolve the interpreter
         directly through resolve_python.bat and never call `conda activate`.

      2. The quieter one, still open until this script runs: `ats_direct.py
         --expand` and `ddg_search.py --update-registry` both read-modify-write
         ats_registry.json, and Registry.save() writes a fixed <path>.tmp then
         os.replace()s it. Concurrent runs do not corrupt the file, they LOSE
         UPDATES - whichever finishes last overwrites the other's newly
         discovered boards, silently.

    13:00 is chosen over 12:05 because ATS_12 is still running at 12:05. ATS runs
    every three hours (03/06/09/12/15/18/21), so 13:00 sits in a clean window:
    ATS_12 is done by ~12:06 and ATS_15 is two hours away.

    Backs the current definition up to logs\_task_backup\DDG_12.retime.xml first.

.NOTES
    MUST RUN ELEVATED. DDG_12 was registered by an administrator and its security
    descriptor rejects Set-ScheduledTask from an ordinary session with
    "Access is denied" - the same reason repoint_scheduled_tasks.ps1 needs
    elevation. Registering a NEW task does not.

.EXAMPLE
    # PowerShell, Run as administrator
    cd "D:\Dev\job-collector\tasks"
    .\retime_ddg12.ps1 -WhatIf      # preview
    .\retime_ddg12.ps1              # do it
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $TaskName = 'DDG_12',
    [string] $At       = '13:00'
)

$ErrorActionPreference = 'Stop'

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Not elevated - Set-ScheduledTask will fail with 'Access is denied'."
    Write-Warning "Reopen PowerShell with Run as administrator."
    exit 1
}

$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$root    = Split-Path -Parent $dir
$backups = Join-Path $root 'logs\_task_backup'
if (-not (Test-Path $backups)) { New-Item -ItemType Directory -Path $backups | Out-Null }

$task = Get-ScheduledTask -TaskName $TaskName
$old  = ($task.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString('HH:mm') }) -join ','
Write-Host "$TaskName currently fires at $old"

$backup = Join-Path $backups "$TaskName.retime.xml"
Export-ScheduledTask -TaskName $TaskName | Set-Content -Path $backup -Encoding utf8
Write-Host "backed up to $backup"

if ($PSCmdlet.ShouldProcess($TaskName, "move daily trigger from $old to $At")) {
    Set-ScheduledTask -TaskName $TaskName `
                      -Trigger (New-ScheduledTaskTrigger -Daily -At $At) | Out-Null

    $t = Get-ScheduledTask -TaskName $TaskName
    $i = $t | Get-ScheduledTaskInfo
    [PSCustomObject]@{
        Task    = $TaskName
        State   = $t.State
        At      = ($t.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString('HH:mm') }) -join ','
        NextRun = $i.NextRunTime
        Action  = ($t.Actions[0].Execute + ' ' + $t.Actions[0].Arguments)
    } | Format-List
}

# Rollback, elevated:
#   Register-ScheduledTask -Xml (Get-Content "logs\_task_backup\DDG_12.retime.xml" -Raw) `
#                          -TaskName DDG_12 -Force
