<#
.SYNOPSIS
  Take ownership of and remove pytest/scratch directories that are locked
  by Codex Sandbox subprocess accounts and inaccessible from regular sessions.

.DESCRIPTION
  Discovers top-level directories under the project root that are either:
    (a) owned by a CodexSandbox* account (the MCP subprocess identity), or
    (b) inaccessible (Get-Acl or Get-ChildItem fails with access-denied).
  Filters those candidates against a scratch-name allowlist as defense-in-depth,
  then for each surviving directory runs:
    takeown /F <path> /R /D Y
    icacls <path> /grant rwsmy:F /T /C
    Remove-Item -Recurse -Force <path>

  REQUIRES: elevated PowerShell session (Run as Administrator). The takeown
  step fails without elevation; the script preflight-aborts if not elevated.

.PARAMETER ProjectRoot
  The project root to scan. Defaults to the directory the script lives in.

.PARAMETER DryRun
  Discover and filter candidates, but do NOT perform takeown / icacls / Remove.
  Reports what WOULD be done.

.PARAMETER GrantUser
  User to grant Full control via icacls. Defaults to the current user account
  (DOMAIN\username). For typical use, the default is correct.

.PARAMETER NoConfirm
  Skip the y/N confirmation prompt before destructive execution. Use with
  caution; intended for scripted re-runs after a verified dry-run.

.EXAMPLE
  PS C:\> .\cleanup-locked-scratch-dirs.ps1 -DryRun
  # Discover and report; no destructive actions.

.EXAMPLE
  PS C:\> .\cleanup-locked-scratch-dirs.ps1
  # Interactive: discover, report, confirm, then clean.

.NOTES
  Background: Codex MCP subprocess pytest runs leave behind scratch directories
  owned by sandbox accounts (CodexSandboxOffline, CodexSandboxUsers). The
  current user (rwsmy) lacks ownership and ACL grants for those directories,
  so they cannot be deleted from a normal Claude Code or PowerShell session.
  This script is the operator-witnessed elevated-cleanup path. See
  docs/phase3e-todo.md and conversation history (2026-04-28) for full context.
#>

[CmdletBinding(SupportsShouldProcess=$false)]
param(
  [string]$ProjectRoot = $PSScriptRoot,
  [switch]$DryRun,
  [string]$GrantUser = "$env:USERDOMAIN\$env:USERNAME",
  [switch]$NoConfirm
)

$ErrorActionPreference = 'Stop'

# --- Preflight 1: elevation check ---
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')
if (-not $isAdmin) {
  Write-Error "This script requires elevation. Right-click PowerShell, choose 'Run as Administrator', then re-run from an elevated session."
  exit 1
}

# --- Preflight 2: project-root sanity check ---
if (-not (Test-Path $ProjectRoot)) {
  Write-Error "ProjectRoot does not exist: $ProjectRoot"
  exit 1
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

if (-not (Test-Path (Join-Path $ProjectRoot '.git'))) {
  Write-Warning "ProjectRoot does not contain a .git directory: $ProjectRoot"
  Write-Warning "Refusing to proceed unless this looks like the swing-trading repo root."
  $confirm = Read-Host "Continue anyway? (y/N)"
  if ($confirm -ne 'y') { exit 1 }
}

Write-Output "Project root:      $ProjectRoot"
Write-Output "Grant target user: $GrantUser"
Write-Output "Mode:              $(if ($DryRun) { 'DRY-RUN (no destructive actions)' } else { 'EXECUTE' })"
Write-Output ""

# --- Discovery: find ACL-locked or sandbox-owned top-level directories ---
$candidates = New-Object System.Collections.ArrayList

$topLevelDirs = Get-ChildItem -LiteralPath $ProjectRoot -Directory -Force -ErrorAction SilentlyContinue
foreach ($dir in $topLevelDirs) {
  $reason = $null

  # Check 1: ownership
  try {
    $acl = Get-Acl -LiteralPath $dir.FullName -ErrorAction Stop
    if ($acl.Owner -like '*CodexSandbox*') {
      $reason = "Owned by $($acl.Owner)"
    }
  } catch {
    $reason = "Get-Acl failed: $($_.Exception.Message.Trim())"
  }

  # Check 2: traversability (only if not already flagged)
  if (-not $reason) {
    try {
      $null = Get-ChildItem -LiteralPath $dir.FullName -Force -ErrorAction Stop | Select-Object -First 1
    } catch {
      $reason = "Get-ChildItem failed: $($_.Exception.Message.Trim())"
    }
  }

  if ($reason) {
    [void]$candidates.Add([PSCustomObject]@{
      Name   = $dir.Name
      Path   = $dir.FullName
      Reason = $reason
    })
  }
}

if ($candidates.Count -eq 0) {
  Write-Output "No locked or sandbox-owned scratch directories found. Nothing to clean."
  exit 0
}

Write-Output "Discovered $($candidates.Count) candidate director$(if ($candidates.Count -eq 1) {'y'} else {'ies'}):"
$candidates | Format-Table Name, Reason -AutoSize

# --- Safety filter: scratch-name allowlist ---
# Pattern matches known scratch-naming conventions. Defense-in-depth against
# the discovery passes accidentally flagging a legitimate directory whose
# ACL state is anomalous for unrelated reasons.
$scratchPattern = '^(\.tmp[-_]|\.pytest[-_](tmp|temp)|tmp[-_]|task\d+_pytest|phase\d+basetemp|pytest_temp|ptemp$)'

$safe = @($candidates | Where-Object { $_.Name -match $scratchPattern })
$rejected = @($candidates | Where-Object { $_.Name -notmatch $scratchPattern })

if ($rejected.Count -gt 0) {
  Write-Warning "REJECTED $($rejected.Count) candidate$(if ($rejected.Count -eq 1) {''} else {'s'}) (does not match scratch-name pattern; will NOT be processed):"
  $rejected | Format-Table Name, Reason -AutoSize
  Write-Output ""
}

if ($safe.Count -eq 0) {
  Write-Output "No candidates passed the scratch-name safety filter. Nothing to clean."
  exit 0
}

Write-Output "WILL PROCESS $($safe.Count) director$(if ($safe.Count -eq 1) {'y'} else {'ies'}):"
$safe | Format-Table Name, Reason -AutoSize

# --- Confirmation ---
if (-not $DryRun -and -not $NoConfirm) {
  $confirm = Read-Host "Proceed with takeown + icacls + Remove-Item on the directories above? (y/N)"
  if ($confirm -ne 'y') {
    Write-Output "Aborted by user. No changes made."
    exit 0
  }
}

# --- Execution ---
$succeeded = 0
$failed = 0
$failures = New-Object System.Collections.ArrayList

foreach ($candidate in $safe) {
  $path = $candidate.Path
  Write-Output ""
  Write-Output "--- Processing: $($candidate.Name) ---"

  if ($DryRun) {
    Write-Output "  [DRY-RUN] Would run: takeown /F `"$path`" /R /D Y"
    Write-Output "  [DRY-RUN] Would run: icacls `"$path`" /grant `"${GrantUser}:F`" /T /C"
    Write-Output "  [DRY-RUN] Would run: Remove-Item -LiteralPath `"$path`" -Recurse -Force"
    continue
  }

  try {
    Write-Output "  [1/3] takeown..."
    & takeown /F $path /R /D Y *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "takeown returned exit code $LASTEXITCODE"
    }

    Write-Output "  [2/3] icacls grant..."
    & icacls $path /grant "${GrantUser}:F" /T /C *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "icacls returned exit code $LASTEXITCODE"
    }

    Write-Output "  [3/3] Remove-Item..."
    Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop

    Write-Output "  SUCCESS"
    $succeeded++
  } catch {
    $errMsg = $_.Exception.Message.Trim()
    Write-Warning "  FAILED: $errMsg"
    [void]$failures.Add([PSCustomObject]@{
      Name = $candidate.Name
      Path = $path
      Error = $errMsg
    })
    $failed++
  }
}

Write-Output ""
Write-Output "=== Summary ==="
Write-Output "  Succeeded: $succeeded"
Write-Output "  Failed:    $failed"
Write-Output "  Total:     $($safe.Count)"

if ($failed -gt 0) {
  Write-Output ""
  Write-Warning "Failures:"
  $failures | Format-Table Name, Error -AutoSize -Wrap
  Write-Warning "Re-run script after addressing root cause, OR investigate the persistent ACL state manually."
  exit 1
}

if ($DryRun) {
  Write-Output ""
  Write-Output "DRY-RUN complete. Re-run without -DryRun to execute."
}

exit 0
