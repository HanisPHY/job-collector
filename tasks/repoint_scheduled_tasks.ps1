<#
.SYNOPSIS
    Repoint the existing collector scheduled tasks at run_logged.bat.

.DESCRIPTION
    The collector tasks were registered to run e.g. run_ats_collector.bat directly,
    so their runs produce no log file and no runs.jsonl record. This script changes
    each task's ACTION to run run_logged.bat with the collector name as its argument.
    Triggers, conditions, principal and run history are not touched.

    Every task definition is exported to logs\_task_backup\<name>.xml first, so the
    change is fully reversible - see the rollback snippet at the bottom of this file.

    MUST RUN ELEVATED. The existing tasks' security descriptors only allow an
    administrator to modify them; a normal session gets "Access is denied".

.EXAMPLE
    Right-click PowerShell -> Run as administrator, then:
        cd "D:\Dev\job-collector\tasks"
        .\repoint_scheduled_tasks.ps1

.EXAMPLE
    Preview without changing anything:
        .\repoint_scheduled_tasks.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

$dir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$root    = Split-Path -Parent $dir
$wrapper = Join-Path $dir 'run_logged.bat'
$backup  = Join-Path $root 'logs\_task_backup'

# Task name -> the run_logged.bat argument it should be launched with.
# "Job collector" is deliberately absent: it is disabled and deprecated.
$map = [ordered]@{
    'ATS_03'           = 'run_ats_collector'
    'ATS_06'           = 'run_ats_collector'
    'ATS_09'           = 'run_ats_collector'
    'ATS_12'           = 'run_ats_collector'
    'ATS_15'           = 'run_ats_collector'
    'ATS_18'           = 'run_ats_collector'
    'ATS_21'           = 'run_ats_collector'
    'DDG_07'           = 'run_ddg_collector'
    'DDG_12'           = 'run_ddg_collector'
    'DDG_17'           = 'run_ddg_collector'
    'ng job collector' = 'run_newgrad_collector'
}

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning 'Not running as administrator - Set-ScheduledTask would fail with "Access is denied".'
    Write-Warning 'Nothing has been changed.'
    Write-Host ''
    Write-Host 'Relaunch elevated by running this from any PowerShell window'
    Write-Host '(a UAC prompt will appear; the new window stays open so you can read the result):'
    Write-Host ''
    Write-Host ("    Start-Process powershell -Verb RunAs -ArgumentList " +
                "'-NoExit','-ExecutionPolicy','Bypass','-File','{0}'" -f $PSCommandPath)
    Write-Host ''
    Write-Host 'Or: right-click PowerShell -> Run as administrator, then re-run this script.'
    if (-not $WhatIfPreference) { return }
}

if (-not (Test-Path $wrapper)) { throw "run_logged.bat not found at $wrapper" }
New-Item -ItemType Directory -Force -Path $backup | Out-Null

$changed = 0
$skipped = @()

foreach ($name in $map.Keys) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Warning "task not found, skipping: $name"
        $skipped += $name
        continue
    }

    # Already repointed? Leave it alone so the script is safe to re-run.
    if ($task.Actions[0].Execute -eq $wrapper -and
        $task.Actions[0].Arguments -eq $map[$name]) {
        Write-Host ("already correct: {0}" -f $name)
        continue
    }

    # Back up the full definition before touching it.
    Export-ScheduledTask -TaskName $name |
        Out-File -Encoding utf8 (Join-Path $backup "$name.xml")

    if ($PSCmdlet.ShouldProcess($name, "action -> run_logged.bat $($map[$name])")) {
        $action = New-ScheduledTaskAction -Execute $wrapper -Argument $map[$name]
        Set-ScheduledTask -TaskName $name -Action $action | Out-Null
        $changed++
        Write-Host ("changed: {0,-18} -> run_logged.bat {1}" -f $name, $map[$name])
    }
}

Write-Host ''
Write-Host ("{0} task(s) changed, {1} not found." -f $changed, $skipped.Count)
Write-Host ''

# Verification: every project task, what it now runs, and when it runs next.
Get-ScheduledTask |
    Where-Object { $_.Actions | Where-Object { $_.Execute -like '*project*Job*' } } |
    ForEach-Object {
        $info = $_ | Get-ScheduledTaskInfo
        [PSCustomObject]@{
            Task       = $_.TaskName
            State      = $_.State
            Runs       = Split-Path $_.Actions[0].Execute -Leaf
            Argument   = $_.Actions[0].Arguments
            NextRun    = $info.NextRunTime
            LastResult = $info.LastTaskResult
        }
    } | Sort-Object Task | Format-Table -AutoSize

Write-Host 'Expected: every task above runs run_logged.bat with a collector argument,'
Write-Host 'except "Job collector" (disabled, deprecated). NextRun should be unchanged.'
Write-Host ''
Write-Host 'To roll back, from an elevated prompt:'
Write-Host '    $backup = "logs\_task_backup"'
Write-Host '    Get-ChildItem $backup -Filter *.xml | ForEach-Object {'
Write-Host '        Register-ScheduledTask -Xml (Get-Content $_.FullName -Raw) `'
Write-Host '            -TaskName $_.BaseName -Force'
Write-Host '    }'
