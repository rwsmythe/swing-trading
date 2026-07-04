<#
.SYNOPSIS
    19-C: register (create-or-update) the weeknight-pipeline Windows Scheduled Task.

.DESCRIPTION
    Idempotently registers a Task Scheduler job that fires the weeknight-pipeline
    wrapper (scripts/run-weeknight-pipeline.ps1) as the OPERATOR'S OWN account
    with the standard interactive profile, so the pipeline resolves its
    home-anchored data root (~/swing-data) correctly (plan C1). RUN THIS FROM THE
    MAIN CHECKOUT, as yourself -- never from a worktree, never as SYSTEM.

    V1 supports ONLY the Interactive logon type ("run only when logged on"); S4U
    is HARD-REFUSED (a network/batch logon can resolve a different/empty
    USERPROFILE -> a foreign data root; deferred behind future explicit-data-root
    work -- plan sec 3.3).

    Schedule (operator-confirmed, plan sec 10): 17:30 HST, Mon-Fri,
    StartWhenAvailable ON (off-window catch-up accepted as harmless same-asof
    re-prep), WakeToRun OFF, battery-permissive, scheduler ExecutionTimeLimit 2h
    (the OUTER backstop; the wrapper's own -RunTimeoutMinutes is the inner bound).

.NOTES
    -IncludeOneOffAt <datetime> adds a one-off trigger ALONGSIDE the canonical
    weekly trigger for the stage-(a) near-term witness fire (no manual Task
    Scheduler mutation). Re-run WITHOUT it (plain -Force) to restore the
    canonical weekly-only definition before the stage-(b) weeknight fire.
#>
[CmdletBinding()]
param(
    [string]$TaskName = 'SwingWeeknightPipeline',
    [string]$WrapperPath = 'C:\Users\rwsmy\swing-trading\scripts\run-weeknight-pipeline.ps1',
    [string]$RepoRoot = 'C:\Users\rwsmy\swing-trading',
    [string]$Time = '17:30',
    [string[]]$DaysOfWeek = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'),
    [string]$LogonType = 'Interactive',
    [switch]$StartWhenAvailable = $true,
    [switch]$WakeToRun,
    [string]$ExecutionTimeLimit = '02:00:00',
    [Nullable[DateTime]]$IncludeOneOffAt = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Guard 1: hard-refuse S4U (and any non-Interactive logon type) in V1 ---
if ($LogonType -eq 'S4U') {
    throw "S4U logon is REFUSED in V1: a network/batch logon can resolve a " +
          "different or empty USERPROFILE, sending the pipeline to a foreign/empty " +
          "data root (the #5 launch-context vector). Use -LogonType Interactive. " +
          "S4U is deferred until the app resolves its data roots from an explicit " +
          "config/env the task sets deterministically (plan sec 3.3)."
}
if ($LogonType -ne 'Interactive') {
    throw "Unsupported -LogonType '$LogonType'. V1 accepts ONLY 'Interactive'."
}

# --- Guard 2: refuse a well-known service SID (never SYSTEM/LOCAL/NETWORK SERVICE) ---
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$userName = $identity.Name
$userSid = $identity.User.Value
$serviceSids = @('S-1-5-18', 'S-1-5-19', 'S-1-5-20')
if ($serviceSids -contains $userSid) {
    throw "Refusing to register as a service account (SID $userSid = " +
          "SYSTEM/LOCAL/NETWORK SERVICE). A foreign USERPROFILE resolves a " +
          "different home-anchored DB. Run this AS YOURSELF (an interactive " +
          "logon), not elevated-as-SYSTEM (plan C1)."
}

# --- Guard 3: the wrapper + repo must exist (fail early, before registering) ---
if (-not (Test-Path -LiteralPath $WrapperPath)) {
    throw "Wrapper not found: $WrapperPath (run from the MAIN checkout)."
}
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "Repo root not found: $RepoRoot."
}

# --- Build the task definition (absolute paths everywhere) ---
$powershellExe = Join-Path ([Environment]::SystemDirectory) 'WindowsPowerShell\v1.0\powershell.exe'
$action = New-ScheduledTaskAction `
    -Execute $powershellExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$WrapperPath`"" `
    -WorkingDirectory $RepoRoot

$triggers = @(
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $Time
)
if ($null -ne $IncludeOneOffAt) {
    $triggers += New-ScheduledTaskTrigger -Once -At $IncludeOneOffAt
}

# Battery-permissive + catch-up ON + wake OFF (plan sec 10). New-ScheduledTaskSettingsSet
# defaults DisallowStartIfOnBatteries/StopIfGoingOnBatteries to $true, so pass the
# permissive switches explicitly.
$settingsArgs = @{
    MultipleInstances        = 'IgnoreNew'
    StartWhenAvailable       = [bool]$StartWhenAvailable
    ExecutionTimeLimit       = [TimeSpan]::Parse($ExecutionTimeLimit)
    AllowStartIfOnBatteries  = $true
    DontStopIfGoingOnBatteries = $true
}
$settings = New-ScheduledTaskSettingsSet @settingsArgs
$settings.WakeToRun = [bool]$WakeToRun   # OFF by default

$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Principal $principal -Settings $settings -Force | Out-Null

# --- ASCII summary for the operator to eyeball (plan sec 5 stage a.2b) ---
$task = Get-ScheduledTask -TaskName $TaskName
Write-Output "Registered scheduled task: $TaskName"
Write-Output "  Principal.UserId : $($task.Principal.UserId)"
Write-Output "  Principal.LogonType : $($task.Principal.LogonType)"
Write-Output "  Resolved identity : $userName (SID $userSid)"
Write-Output "  Action : $powershellExe -File $WrapperPath"
Write-Output "  WorkingDirectory : $RepoRoot"
Write-Output "  Settings : MultipleInstances=IgnoreNew StartWhenAvailable=$([bool]$StartWhenAvailable) WakeToRun=$([bool]$WakeToRun) ExecutionTimeLimit=$ExecutionTimeLimit AllowStartIfOnBatteries=True DontStopIfGoingOnBatteries=True"
Write-Output "  Triggers :"
foreach ($t in $task.Triggers) {
    Write-Output "    - $($t.CimClass.CimClassName) start=$($t.StartBoundary)"
}
if ($null -ne $IncludeOneOffAt) {
    Write-Output "  NOTE: a one-off witness trigger was added. Re-run WITHOUT -IncludeOneOffAt (plain -Force) to restore the weekly-only definition before the stage-(b) weeknight fire."
}
