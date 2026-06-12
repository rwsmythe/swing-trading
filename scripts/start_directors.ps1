<#
.SYNOPSIS
    Cold-start (or resume) the two director CC CLI windows outside VS Code.

.DESCRIPTION
    Comms Stage 1 launcher. Opens a long-lived Claude Code CLI session per
    director role (CHARC = tool director, RD = research director) in its own
    Windows Terminal tab (or a plain PowerShell window as a fallback), running
    the role's bootstrap prompt. Fresh mode generates a dated NAMED session and
    records it to comms/.sessions.json; resume mode reopens the recorded named
    session.

    CONTEXT RESET = FRESH MODE. When a director's context fills, do NOT resume
    -- run a fresh start for that role. It mints a new dated session name,
    updates the map, and leaves the old session untouched on disk.

.PARAMETER Role
    charc | rd | both  (default: both)

.PARAMETER Resume
    Switch. Reopen the recorded named session for the role(s) instead of a
    fresh start. If the map has no entry for a role, the script tells you to use
    fresh mode for it.

.PARAMETER NoWT
    Switch. Skip Windows Terminal; launch each role in a plain PowerShell
    window (-NoExit). This is also the automatic fallback when wt.exe is absent.

.PARAMETER DryRun
    Switch. Run the preflight and compute the session name(s) and exact claude
    command line(s), print them, and exit WITHOUT launching anything or writing
    the session map. Use this to verify the launcher before a real cold start.

.NOTES
    Observed claude CLI behavior (verified against v2.1.170 on 2026-06-11):
      * "-n, --name <name>"  EXISTS. It sets a DISPLAY name shown in the prompt
        box, the /resume picker, and the terminal title. (It is NOT a headless
        resume key by itself; the display name is how you find the session in
        the picker.)
      * "-r, --resume [value]" EXISTS. Given a session ID it resumes directly;
        given a non-ID search term it opens the interactive /resume picker
        filtered by that term. Because we resume by the DISPLAY NAME (not the
        opaque session id -- --session-id is unreliable in interactive mode,
        upstream #44607), resume opens the picker filtered to the unique dated
        name; select it to re-enter. This is the supported interactive path.
      * "--continue" and "--session-id" are DELIBERATELY NOT USED: --continue
        grabs the most-recently-touched session (wrong when two roles share this
        project dir); --session-id is unreliable interactively.
      * "--model <model>", "--effort <level>" (low, medium, high, xhigh, max)
        and "--permission-mode <mode>" (incl. "auto") EXIST. Directors launch
        with '--model fable --effort xhigh --permission-mode auto' on BOTH
        fresh and resume (operator directives 2026-06-11); every flag and
        value is preflight-verified before launch.
      * Auto-submit vs pre-fill of the positional [prompt]: documentation is
        ambiguous and this is version-dependent. The bootstrap prompts are
        SELF-CONTAINED, so either behavior works -- if claude pre-fills the
        input instead of auto-submitting, just press Enter in the new window.
        The definitive observation is made at the operator cold-start gate.

    PowerShell 5.1 compatible: no '&&', no ternary, no null-coalescing.
    ASCII-only console output (Windows cp1252 stdout). Roles are launched
    SERIALLY -- the comms/.sessions.json read-modify-write is not
    concurrency-safe, so never background these launches.
#>

[CmdletBinding()]
param(
    [ValidateSet('charc', 'rd', 'both')]
    [string]$Role = 'both',
    [switch]$Resume,
    [switch]$NoWT,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# --- paths -----------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$CommsDir = Join-Path $RepoRoot 'comms'
$SessionsPath = Join-Path $CommsDir '.sessions.json'

$BootstrapFiles = @{
    'charc' = Join-Path $ScriptDir 'director_bootstrap_charc.md'
    'rd'    = Join-Path $ScriptDir 'director_bootstrap_rd.md'
}
$RoleTitles = @{ 'charc' = 'CHARC'; 'rd' = 'RD' }

# Directors run on Fable at extra-high effort in auto permission mode
# (operator directives 2026-06-11). Applied to BOTH fresh and resume launches;
# preflight verifies each flag and value against the installed CLI before any
# window opens.
$LaunchArgs = @('--model', 'fable', '--effort', 'xhigh', '--permission-mode', 'auto')

# Short, quoting-safe directive prompts (no newlines, quotes, or semicolons --
# the full multi-line prompt content lives in the bootstrap files to keep the
# command line robust through wt.exe / Start-Process).
$FreshPromptFmt = 'Read and follow {0} -- it is your role bootstrap. Begin now.'
$ResumePrompt = 'Resuming your director session: re-read your charter section-of-record, run python scripts/role_mail.py read --role {0} --all to drain your inbox, then report current state and await the operator.'

# --- helpers ---------------------------------------------------------------

function Write-Info($msg) { Write-Host "[start-directors] $msg" }
function Write-Err($msg) { Write-Host "[start-directors] ERROR: $msg" }

function Invoke-Preflight {
    # Verify the claude CLI exists and carries the flags we depend on. Returns
    # the version string; throws on any failure (ASCII messages).
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw "claude CLI not found on PATH. Install Claude Code or open a shell where 'claude' resolves."
    }
    $version = ''
    try { $version = (claude --version | Out-String).Trim() }
    catch { throw "could not run 'claude --version': $($_.Exception.Message)" }

    $help = ''
    try { $help = (claude --help | Out-String) }
    catch { throw "could not run 'claude --help': $($_.Exception.Message)" }

    # Verify the EXACT flags this launcher uses: '-n' (fresh launch) and
    # '--resume'. Checking only '--name' would let a CLI that advertises
    # '--name' but not the '-n' short form pass preflight and then fail at
    # launch. The help line is '  -n, --name <name>'.
    if (-not ($help -match '(?m)(^|\s)-n[,\s]')) {
        throw "this claude CLI ($version) does not advertise the -n flag in --help (fresh launch uses 'claude -n'); refusing to launch with a guessed flag. Update the launcher to match the installed CLI."
    }
    if (-not ($help -match '--resume')) {
        throw "this claude CLI ($version) does not advertise --resume in --help; refusing to launch with a guessed flag."
    }
    if (-not ($help -match '--model')) {
        throw "this claude CLI ($version) does not advertise --model in --help (directors launch with '--model fable'); refusing to launch with a guessed flag."
    }
    if (-not ($help -match '--effort')) {
        throw "this claude CLI ($version) does not advertise --effort in --help (directors launch with '--effort xhigh'); refusing to launch with a guessed flag."
    }
    if (-not ($help -match 'xhigh')) {
        throw "this claude CLI ($version) does not list 'xhigh' as an effort level in --help; update the launcher's `$LaunchArgs to a level the installed CLI accepts."
    }
    if (-not ($help -match '--permission-mode')) {
        throw "this claude CLI ($version) does not advertise --permission-mode in --help (directors launch with '--permission-mode auto'); refusing to launch with a guessed flag."
    }
    if (-not ($help -match '"auto"')) {
        throw "this claude CLI ($version) does not list 'auto' as a --permission-mode choice in --help; update the launcher's `$LaunchArgs to a mode the installed CLI accepts."
    }
    return $version
}

function Get-SessionMap {
    # Returns a hashtable role -> @{ session_name; session_id; created }.
    $map = @{}
    if (Test-Path $SessionsPath) {
        $raw = Get-Content -Raw -Path $SessionsPath
        if ($raw -and $raw.Trim().Length -gt 0) {
            $obj = $raw | ConvertFrom-Json
            foreach ($prop in $obj.PSObject.Properties) {
                $entry = @{}
                foreach ($p in $prop.Value.PSObject.Properties) {
                    $entry[$p.Name] = $p.Value
                }
                $map[$prop.Name] = $entry
            }
        }
    }
    return $map
}

function Save-SessionMap($map) {
    if (-not (Test-Path $CommsDir)) {
        New-Item -ItemType Directory -Path $CommsDir -Force | Out-Null
    }
    $json = $map | ConvertTo-Json -Depth 5
    # UTF-8 without BOM so Python tooling can read it cleanly if ever needed.
    [System.IO.File]::WriteAllText($SessionsPath, $json)
}

function New-SessionName($role) {
    $stamp = (Get-Date).ToString('yyyyMMdd-HHmm')
    return "director-$role-$stamp"
}

function Build-LaunchCommand($role, $argList) {
    # The inner shell command for a spawned director window. Setting
    # $env:SWING_ROLE HERE (inside the spawned shell) is load-bearing: the
    # wt.exe new-tab path hands the tab to an ALREADY-RUNNING Windows Terminal
    # process, which spawns its shell from ITS OWN environment -- a
    # launcher-set $env:SWING_ROLE would NOT reliably propagate. So BOTH the wt
    # path and the -NoWT fallback wrap claude in a 'powershell -NoExit -Command'
    # shell that sets the role first. The backtick escapes the '$' so the OUTER
    # (launcher) shell passes '$env:SWING_ROLE' through literally while it DOES
    # expand $role and $RepoRoot.
    return "`$env:SWING_ROLE='$role'; Set-Location '$RepoRoot'; claude " + ($argList -join ' ')
}

function Start-RoleWindow($role, $title, $argList) {
    # $argList is the claude argument array (everything after 'claude'); the
    # spawned shell sets SWING_ROLE so the director's UserPromptSubmit hook fires.
    $inner = Build-LaunchCommand $role $argList
    $useWT = (-not $NoWT) -and ($null -ne (Get-Command wt.exe -ErrorAction SilentlyContinue))
    if ($useWT) {
        $wtArgs = @('-w', '0', 'new-tab', '--title', $title, '-d', $RepoRoot, 'powershell', '-NoExit', '-Command', $inner)
        Start-Process -FilePath 'wt.exe' -ArgumentList $wtArgs
    }
    else {
        if ($NoWT) { Write-Info "launching $title in a plain window (-NoWT)." }
        else { Write-Info "wt.exe not found; launching $title in a plain window." }
        Start-Process -FilePath 'powershell' -ArgumentList @('-NoExit', '-Command', $inner)
    }
}

function Format-Cmd($argList) {
    return 'claude ' + ($argList -join ' ')
}

# --- per-role launch -------------------------------------------------------

function Start-Fresh($role, $map) {
    $name = New-SessionName $role
    $bootstrap = $BootstrapFiles[$role]
    if (-not (Test-Path $bootstrap)) {
        throw "bootstrap file missing for $role at $bootstrap"
    }
    $prompt = [string]::Format($FreshPromptFmt, "scripts/$([System.IO.Path]::GetFileName($bootstrap))")
    $argList = $LaunchArgs + @('-n', "`"$name`"", "`"$prompt`"")
    Write-Info "fresh $role -> session name '$name'"
    Write-Info "  cmd: $(Format-Cmd $argList)"
    Write-Info "  launch: $(Build-LaunchCommand $role $argList)"
    if ($DryRun) { return $map }

    $map[$role] = @{ session_name = $name; session_id = $null; created = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }
    Save-SessionMap $map
    Start-RoleWindow $role $RoleTitles[$role] $argList
    return $map
}

function Start-Resume($role, $map) {
    if (-not $map.ContainsKey($role)) {
        Write-Err "no recorded session for '$role'. Use fresh mode: .\scripts\start_directors.ps1 -Role $role"
        return $map
    }
    $name = $map[$role].session_name
    if (-not $name) {
        Write-Err "recorded session for '$role' has no session_name. Use fresh mode."
        return $map
    }
    $prompt = [string]::Format($ResumePrompt, $role)
    $argList = $LaunchArgs + @('--resume', "`"$name`"", "`"$prompt`"")
    Write-Info "resume $role -> session name '$name'"
    Write-Info "  cmd: $(Format-Cmd $argList)"
    Write-Info "  launch: $(Build-LaunchCommand $role $argList)"
    Write-Info "  (--resume opens the /resume picker filtered to this name; select it to re-enter.)"
    if ($DryRun) { return $map }
    Start-RoleWindow $role $RoleTitles[$role] $argList
    return $map
}

# --- main ------------------------------------------------------------------

try {
    $version = Invoke-Preflight
}
catch {
    Write-Err $_.Exception.Message
    exit 1
}
Write-Info "claude CLI OK: $version"
if ($DryRun) { Write-Info "DRY RUN -- no windows launched, session map not written." }

if ($Role -eq 'both') { $roles = @('charc', 'rd') }
else { $roles = @($Role) }

$map = Get-SessionMap
# Launch roles SERIALLY (the session-map read-modify-write is not
# concurrency-safe). Each Start-* returns the (possibly updated) map.
foreach ($r in $roles) {
    if ($Resume) { $map = Start-Resume $r $map }
    else { $map = Start-Fresh $r $map }
}

Write-Info 'done.'
exit 0
