<#
.SYNOPSIS
    19-C: unregister (tear down) the weeknight-pipeline Windows Scheduled Task.

.DESCRIPTION
    Idempotent: removes the task if present, else prints an "already absent"
    message and exits 0. A bare Unregister-ScheduledTask ERRORS on an absent
    task -- the existence check is what makes this a true no-op. RUN THIS FROM
    THE MAIN CHECKOUT, as yourself. This is teardown only; it is NOT part of the
    register/update path (re-run register-weeknight-task.ps1 -Force to update).
#>
[CmdletBinding()]
param(
    [string]$TaskName = 'SwingWeeknightPipeline'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Unregistered scheduled task: $TaskName"
}
else {
    Write-Output "Scheduled task already absent: $TaskName (no action)"
}
exit 0
