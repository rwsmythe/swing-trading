<#
.SYNOPSIS
  Take ownership of and remove pytest/scratch directories AND orphaned
  worktree dirs that are locked by Codex Sandbox subprocess accounts or
  pytest-tmpdir ACL inheritance and inaccessible from regular sessions.

.DESCRIPTION
  Discovers two distinct categories of cleanup targets:

  (1) TOP-LEVEL scratch dirs under the project root, either:
      (a) owned by a CodexSandbox* account (the MCP subprocess identity), or
      (b) inaccessible (Get-Acl or Get-ChildItem fails with access-denied).
      Filtered against a scratch-name allowlist as defense-in-depth.

  (2) ORPHANED WORKTREE dirs (added 2026-05-05 per phase3e-todo.md
      trigger-gated entry; recurrence-trigger fired at Phase 7 cleanup
      with 5/5 worktrees affected by the .tmp/pytest-of-rwsmy/ ACL-lock
      pattern). Subdirs of `.worktrees/` OR `.claude/worktrees/` whose
      branch is NOT in `git worktree list` (i.e., `git worktree remove
      --force` succeeded at deregistering but failed to delete on-disk
      content). pytest's tmpdir machinery creates `.tmp/pytest-of-rwsmy/`
      subdirs whose ACL inheritance prevents normal-user delete; same
      takeown/icacls treatment as category (1) handles it.

      `.claude/worktrees/` coverage added 2026-05-09 after the Phase 8
      V1 polish dispatch chose this non-precedent path (per the
      `superpowers:using-git-worktrees` skill default) instead of the
      project-precedent `.worktrees/` location. Operator-elevated
      cleanup didn't reach the husk because the script only scanned
      `.worktrees/`; explicit `git worktree remove --force` on the
      orphaned `.claude/worktrees/phase8-v1-polish` path eventually
      cleared it. Script now scans BOTH paths to avoid the gap.

  For each surviving target runs:
    takeown /F <path> /R /D Y
    icacls <path> /reset /T /C /Q          # remove restrictive ACLs first
    icacls <path> /grant <GrantUser>:F /T /C  # explicit grant defense-in-depth
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

.PARAMETER SkipWorktrees
  Skip the orphaned-worktree discovery pass. Default $false (worktrees
  included). Set $true to scan only top-level scratch dirs (legacy behavior
  pre-2026-05-05).

.EXAMPLE
  PS C:\> .\cleanup-locked-scratch-dirs.ps1 -DryRun
  # Discover and report; no destructive actions.

.EXAMPLE
  PS C:\> .\cleanup-locked-scratch-dirs.ps1
  # Interactive: discover, report, confirm, then clean.

.NOTES
  Background: Two distinct lock-mechanisms produce on-disk dirs that the
  operator user (rwsmy) cannot delete from a normal session:

  - Codex MCP subprocess pytest runs leave behind scratch directories
    owned by sandbox accounts (CodexSandboxOffline, CodexSandboxUsers).
    Original 2026-04-28 motivation.

  - pytest tmpdir machinery inside worktrees creates `.tmp/pytest-of-rwsmy/`
    subdirs whose ACL inheritance prevents normal-user delete after the
    pytest run completes. `git worktree remove --force` fails with
    "Directory not empty"; deregistration succeeds but on-disk dir orphans.
    Recurrence trigger fired 2026-05-05 (Phases 5 + 6 + Phase 7 Sub-A/B/C
    all hit the pattern; 5/5 = durable). Worktree-extension landed
    2026-05-05 per phase3e-todo trigger-gated entry.

  This script is the operator-witnessed elevated-cleanup path. See
  docs/phase3e-todo.md and orchestrator-context.md for full context.
#>

[CmdletBinding(SupportsShouldProcess=$false)]
param(
  [string]$ProjectRoot = $PSScriptRoot,
  [switch]$DryRun,
  [string]$GrantUser = "$env:USERDOMAIN\$env:USERNAME",
  [switch]$NoConfirm,
  [switch]$SkipWorktrees
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

# --- Discovery: orphaned worktree subdirs (added 2026-05-05) ---
# After `git worktree remove --force` fails on `.tmp/pytest-of-rwsmy/` ACL-locked
# subdirs, the worktree REGISTRATION is removed but the on-disk dir remains.
# These are operator-owned (rwsmy) AT THE TOP LEVEL but the .tmp/pytest-of-rwsmy/
# subdir has restrictive permissions from pytest tmpdir ACL inheritance.
# Recurrence pattern: Phases 5 + 6 + Phase 7 Sub-A/B/C all hit the same lock.
# 5/5 recurrence rate confirmed durable 2026-05-05; phase3e-todo trigger-gated
# entry's tripwire fired; this discovery branch is the script extension.
if (-not $SkipWorktrees) {
  # Scan BOTH worktree base paths (project-precedent + skill-default).
  # `.worktrees/` is the project precedent (Phase 5/6/7/8/V1.5 polish dispatches).
  # `.claude/worktrees/` is the `superpowers:using-git-worktrees` skill default
  # (added 2026-05-09 after the Phase 8 V1 polish dispatch landed there and the
  # operator-elevated cleanup didn't reach the husk because the script only
  # scanned `.worktrees/`). See orchestrator-context.md §"Lessons captured"
  # 2026-05-08 entry on worktree directory path discipline + the 2026-05-09
  # cleanup-script extension that closes the gap.
  $worktreeBaseDirs = @(
    (Join-Path $ProjectRoot '.worktrees'),
    (Join-Path $ProjectRoot '.claude/worktrees')
  )

  # Get registered worktree paths from git ONCE (shared across both base scans).
  $registeredPaths = @()
  try {
    $worktreeListOutput = & git -C $ProjectRoot worktree list 2>&1
    foreach ($line in $worktreeListOutput) {
      # Format: "<path>  <sha> [<branch>]" — first whitespace-delimited token is path
      if ($line -match '^(\S+)\s+[a-f0-9]+\s+\[') {
        $regPath = $matches[1].Trim()
        # Normalize to absolute Windows path for comparison
        try {
          $registeredPaths += (Resolve-Path -LiteralPath $regPath -ErrorAction Stop).Path
        } catch {
          $registeredPaths += $regPath
        }
      }
    }
  } catch {
    Write-Warning "git worktree list failed: $($_.Exception.Message). Skipping orphaned-worktree discovery."
    $registeredPaths = $null
  }

  if ($null -ne $registeredPaths) {
    foreach ($worktreesDir in $worktreeBaseDirs) {
      if (-not (Test-Path $worktreesDir)) { continue }

      # Compute the relative-prefix label used in candidate Name (e.g.,
      # ".worktrees" or ".claude/worktrees"). Used both for display + for
      # the safety-filter admission check below.
      $relPrefix = ($worktreesDir.Substring($ProjectRoot.Length).TrimStart('\','/') -replace '\\','/')

      # Subdirs of <worktreesDir> whose absolute path is NOT in the registered set
      $worktreeSubdirs = Get-ChildItem -LiteralPath $worktreesDir -Directory -Force -ErrorAction SilentlyContinue
      foreach ($wt in $worktreeSubdirs) {
        $wtAbs = $wt.FullName
        $isRegistered = $false
        foreach ($regPath in $registeredPaths) {
          if ($wtAbs -ieq $regPath) {  # case-insensitive Windows path equality
            $isRegistered = $true
            break
          }
        }
        if (-not $isRegistered) {
          [void]$candidates.Add([PSCustomObject]@{
            Name   = "$relPrefix/$($wt.Name)"
            Path   = $wtAbs
            Reason = "Orphaned worktree (deregistered but on-disk dir remains; pytest-of-rwsmy ACL-lock pattern)"
          })
        }
      }
    }
  }
}

if ($candidates.Count -eq 0) {
  Write-Output "No locked or sandbox-owned scratch directories or orphaned worktrees found. Nothing to clean."
  exit 0
}

Write-Output "Discovered $($candidates.Count) candidate director$(if ($candidates.Count -eq 1) {'y'} else {'ies'}):"
$candidates | Format-Table Name, Reason -AutoSize

# --- Safety filter: scratch-name allowlist OR orphaned-worktree path ---
# Two-track allowlist:
#   (a) scratch-name pattern for top-level dirs (Codex sandbox + pytest scratch)
#   (b) `.worktrees/...` prefix for orphaned worktree subdirs (Reason carries
#       "Orphaned worktree" tag set by the discovery pass above)
#
# Recognized scratch-name patterns:
#   - .tmp                  (plain top-level temp dir; e.g., from CodexSandbox pytest)
#   - .tmp-foo, .tmp_foo    (pytest tmp variants)
#   - .pytest-tmp, .pytest_tmp, .pytest-temp, .pytest_temp
#   - tmp-foo, tmp_foo
#   - task<digits>_pytest
#   - phase<digits>basetemp
#   - pytest_temp
#   - ptemp
#   - .config-overrides-*   (Phase 5 first-attempt rogue test artifacts;
#                            tempfile.mkdtemp(dir=Path.cwd()) from a non-plan test)
#   - .codex-pytest-*       (Codex CLI sandbox pytest scratch dirs)
#   - pytest-run-*          (alternate pytest scratch naming)
#
# Orphaned-worktree path admission: candidate Reason starts with "Orphaned
# worktree" AND Name starts with ".worktrees/" OR ".claude/worktrees/" —
# both must hold (defense-in-depth against accidental admission). Two-prefix
# admission added 2026-05-09 alongside the discovery-pass extension that
# scans both base paths.
$scratchPattern = '^(\.tmp([-_].*|$)|\.pytest[-_](tmp|temp)|tmp[-_]|task\d+_pytest|phase\d+basetemp|pytest_temp|ptemp$|\.config-overrides-|\.codex-pytest-|pytest-run-)'
$worktreePathPattern = '^(\.worktrees|\.claude/worktrees)/'

$safe = @($candidates | Where-Object {
  ($_.Name -match $scratchPattern) -or
  ($_.Reason -like 'Orphaned worktree*' -and $_.Name -match $worktreePathPattern)
})
$rejected = @($candidates | Where-Object {
  -not (
    ($_.Name -match $scratchPattern) -or
    ($_.Reason -like 'Orphaned worktree*' -and $_.Name -match $worktreePathPattern)
  )
})

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
    Write-Output "  [DRY-RUN] Would run: icacls `"$path`" /reset /T /C /Q"
    Write-Output "  [DRY-RUN] Would run: icacls `"$path`" /grant `"${GrantUser}:F`" /T /C"
    Write-Output "  [DRY-RUN] Would run: Remove-Item -LiteralPath `"$path`" -Recurse -Force"
    continue
  }

  try {
    Write-Output "  [1/4] takeown..."
    & takeown /F $path /R /D Y *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "takeown returned exit code $LASTEXITCODE"
    }

    # icacls /reset BEFORE /grant: clears restrictive ACLs first (forces
    # inheritance from parent), then explicit grant adds operator full-control.
    # Two-step is more aggressive than /grant alone; needed for the deeply-
    # locked .tmp/pytest-of-rwsmy/ subdirs that resisted /grant-only on
    # Phase 6 manual cleanup attempt 2026-05-04 (got 1196/1198 success;
    # 2 files stuck under /grant-only treatment). Verified-empirical
    # evidence motivates the /reset additional step.
    Write-Output "  [2/4] icacls reset..."
    & icacls $path /reset /T /C /Q *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "icacls /reset returned exit code $LASTEXITCODE"
    }

    Write-Output "  [3/4] icacls grant..."
    & icacls $path /grant "${GrantUser}:F" /T /C *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "icacls /grant returned exit code $LASTEXITCODE"
    }

    Write-Output "  [4/4] Remove-Item..."
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
