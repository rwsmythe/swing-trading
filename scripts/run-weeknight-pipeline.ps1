<#
.SYNOPSIS
    19-C weeknight-pipeline Task Scheduler wrapper.

.DESCRIPTION
    Invokes `swing pipeline run --skip-if-running` by ABSOLUTE path under the
    scheduled-task launch context, translates the CLI exit code to a task-green
    outcome (a benign collision -> SKIP -> exit 0), bounds a hung run with a
    process-TREE kill, and always appends exactly ONE result line per fire to a
    fixed absolute result log. ASCII-only output (the Windows cp1252 CLI gotcha).

    Design lives in docs/plans/19-C-weeknight-scheduled-task-plan.md and the
    runbook docs/runbooks/weeknight-pipeline-scheduled-task.md. Run this from the
    MAIN checkout only (never a worktree); the CLI's own exit-78 guard fails
    closed if the running code tree diverges from the --config project root.

.NOTES
    -NoRun is a test/dot-source seam: when supplied the script defines its
    functions but does NOT execute the main body, so the pure helpers
    (Get-WeeknightOutcome / Write-WeeknightResultLine) are unit-testable.
#>
[CmdletBinding()]
param(
    [string]$SwingExe = 'C:\Users\rwsmy\AppData\Roaming\Python\Python314\Scripts\swing.exe',
    [string]$RepoRoot = 'C:\Users\rwsmy\swing-trading',
    [string]$ConfigPath = 'C:\Users\rwsmy\swing-trading\swing.config.toml',
    [string]$ResultLog = 'C:\Users\rwsmy\swing-data\logs\weeknight-task.log',
    [int]$RunTimeoutMinutes = 45,
    [switch]$NoRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-WeeknightOutcome {
    <#
      Pure exit-code -> outcome mapping (the one unit-testable slice).
        0   -> OK    (exit 0)
        75  -> SKIP  (exit 0; collision -> task stays green, EX_TEMPFAIL)
        1   -> FAIL  (exit 1; pipeline reported failure)
        78  -> ERROR (exit 78; the CLI code-tree/config-root fail-closed guard)
        any -> ERROR (exit <code>; includes 2 = wrapper/registration coding bug)
    #>
    param([int]$Code)
    switch ($Code) {
        0  { return [pscustomobject]@{ Tag = 'OK';    ExitCode = 0;     Message = '' } }
        75 { return [pscustomobject]@{ Tag = 'SKIP';  ExitCode = 0;     Message = 'another run in progress' } }
        1  { return [pscustomobject]@{ Tag = 'FAIL';  ExitCode = 1;     Message = 'pipeline reported failure' } }
        78 { return [pscustomobject]@{ Tag = 'ERROR'; ExitCode = 78;    Message = 'code-tree/config-root mismatch' } }
        default { return [pscustomobject]@{ Tag = 'ERROR'; ExitCode = $Code; Message = 'unexpected exit code' } }
    }
}

function Write-WeeknightResultLine {
    <# Append exactly ONE ASCII result line; mkdir -Force the parent first. #>
    param(
        [Parameter(Mandatory = $true)][string]$ResultLog,
        [Parameter(Mandatory = $true)][string]$Tag,
        [Parameter(Mandatory = $true)][int]$ExitCode,
        [string]$Message = ''
    )
    $dir = Split-Path -Parent $ResultLog
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $ts = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    $line = "$ts $Tag exit=$ExitCode"
    if ($Message) { $line = "$line $Message" }
    Add-Content -LiteralPath $ResultLog -Value $line -Encoding ASCII
}

function Invoke-WeeknightPipeline {
    <#
      Pre-flight (exe/repo present) -> bounded child run (process-tree kill on
      timeout) -> ONE result line -> return the wrapper exit code. Every path
      the wrapper survives writes a line; a wrapper-level hang is covered by
      Task Scheduler's own run history / LastTaskResult (see the runbook).
    #>
    param(
        [Parameter(Mandatory = $true)][string]$SwingExe,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$ConfigPath,
        [Parameter(Mandatory = $true)][string]$ResultLog,
        [int]$RunTimeoutMinutes = 45
    )

    # Pre-flight: a missing repo/exe is an environment/config error (exit 78),
    # surfaced as a loud ERROR line WITHOUT attempting the run.
    if (-not (Test-Path -LiteralPath $RepoRoot)) {
        Write-WeeknightResultLine -ResultLog $ResultLog -Tag 'ERROR' -ExitCode 78 `
            -Message "repo root not found: $RepoRoot"
        return 78
    }
    if (-not (Test-Path -LiteralPath $SwingExe)) {
        Write-WeeknightResultLine -ResultLog $ResultLog -Tag 'ERROR' -ExitCode 78 `
            -Message "swing exe not found: $SwingExe"
        return 78
    }

    Set-Location -LiteralPath $RepoRoot
    $taskkill = Join-Path ([Environment]::SystemDirectory) 'taskkill.exe'

    try {
        # Run swing.exe as a bounded child so a hang is caught HERE (not by the
        # scheduler's outer 2h ExecutionTimeLimit, which would kill the wrapper
        # before it could write a line). The absolute --config pins project_root
        # / the data roots (plan C1).
        $p = Start-Process -FilePath $SwingExe `
            -ArgumentList '--config', $ConfigPath, 'pipeline', 'run', '--skip-if-running' `
            -WorkingDirectory $RepoRoot -NoNewWindow -PassThru
        $null = $p.Handle  # cache the native handle so .ExitCode is reliable post-exit

        $timeoutMs = $RunTimeoutMinutes * 60 * 1000
        if (-not $p.WaitForExit($timeoutMs)) {
            # Process-TREE kill by absolute path: swing.exe is a launcher that
            # spawns python.exe; $p.Kill() would orphan the python child (still
            # holding the lease). /T reaches the descendant tree.
            & $taskkill /T /F /PID $p.Id | Out-Null
            if ($LASTEXITCODE -ne 0) {
                # $ErrorActionPreference='Stop' does NOT throw on a native
                # nonzero exit -- check $LASTEXITCODE explicitly. A failed kill
                # may leave a live python orphan holding the lease.
                Write-WeeknightResultLine -ResultLog $ResultLog -Tag 'TIMEOUT-KILL-FAILED' `
                    -ExitCode 1 `
                    -Message "pid=$($p.Id) after ${RunTimeoutMinutes}m; taskkill rc=$LASTEXITCODE; run 'swing pipeline force-clear' if a run is still live"
                return 1
            }
            Write-WeeknightResultLine -ResultLog $ResultLog -Tag 'TIMEOUT' -ExitCode 1 `
                -Message "killed process tree pid=$($p.Id) after ${RunTimeoutMinutes}m"
            return 1
        }
        $code = $p.ExitCode
    }
    catch {
        # A launch exception (interpreter failure, etc.) before the child runs.
        Write-WeeknightResultLine -ResultLog $ResultLog -Tag 'ERROR' -ExitCode 1 `
            -Message "launch exception: $($_.Exception.Message)"
        return 1
    }

    $outcome = Get-WeeknightOutcome -Code $code
    Write-WeeknightResultLine -ResultLog $ResultLog -Tag $outcome.Tag -ExitCode $code `
        -Message $outcome.Message
    return $outcome.ExitCode
}

if (-not $NoRun) {
    $rc = Invoke-WeeknightPipeline -SwingExe $SwingExe -RepoRoot $RepoRoot `
        -ConfigPath $ConfigPath -ResultLog $ResultLog -RunTimeoutMinutes $RunTimeoutMinutes
    exit $rc
}
