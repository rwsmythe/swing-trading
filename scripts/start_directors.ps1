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

.PARAMETER Model
    fable | opus | sonnet. OVERRIDE for this launch only; when omitted each
    role starts on its bootstrap-declared model from $RoleLaunch. Applies to
    every role launched by this invocation (with -Role both, to both directors).

.PARAMETER Effort
    low | medium | high | xhigh | max. OVERRIDE for this launch only; when
    omitted each role starts at its bootstrap-declared effort from $RoleLaunch.

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
        and "--permission-mode <mode>" (incl. "auto") EXIST. Launches use
        '--permission-mode auto' on BOTH fresh and resume. Model AND effort are
        ROLE-AWARE ($RoleLaunch) and mirror each role's declared START
        configuration in its bootstrap file (operator-ruled 2026-09-01,
        e0582397): directors 'fable' / 'high', orchestrator 'opus' / 'high'.
        'xhigh' is an in-session escalation, never a start setting; the old
        opus/max + opus/xhigh table (2026-06-13, when fable was
        ITAR-unavailable) is RETIRED. An explicit --model on the command line
        overrides the user settings.json model, so this table -- not
        settings.json -- decides what a launched role runs on. Every flag is
        preflight-verified before launch. The model alias is NOT value-checked
        against --help (aliases rotate as new models ship; an invalid alias
        fails fast at launch, not silently).
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
    [ValidateSet('charc', 'rd', 'orchestrator', 'both')]
    [string]$Role = 'both',
    [ValidateSet('fable', 'opus', 'sonnet')]
    [string]$Model,
    [ValidateSet('low', 'medium', 'high', 'xhigh', 'max')]
    [string]$Effort,
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
    'charc'        = Join-Path $ScriptDir 'director_bootstrap_charc.md'
    'rd'           = Join-Path $ScriptDir 'director_bootstrap_rd.md'
    'orchestrator' = Join-Path $ScriptDir 'orchestrator_bootstrap.md'
}
$RoleTitles = @{ 'charc' = 'CHARC'; 'rd' = 'RD'; 'orchestrator' = 'ORCHESTRATOR' }

# Per-role START configuration -- the single source the launcher reads. It
# MUST match the "LAUNCH CONFIGURATION" block each role's bootstrap declares
# (scripts/director_bootstrap_charc.md, director_bootstrap_rd.md,
# orchestrator_bootstrap.md; operator-ruled 2026-09-01, e0582397): directors
# Fable 5.1 / high, orchestrator Opus 5 / high. 'xhigh' is an in-session
# escalation at the role's discretion, NOT a start setting. Applied to BOTH
# fresh and resume launches; preflight verifies each flag and the
# effort/permission VALUES against the installed CLI (the --model alias is
# not value-checked). tests/scripts/test_start_directors_orchestrator.py pins
# this table against the bootstrap text so the two cannot drift again (they
# did: 2026-09-01 .. 2026-09-06 every launcher-started role ran opus/max or
# opus/xhigh while the bootstraps declared fable/high and opus/high).
$RoleLaunch = @{
    'charc'        = @{ Model = 'fable'; Effort = 'high' }
    'rd'           = @{ Model = 'fable'; Effort = 'high' }
    'orchestrator' = @{ Model = 'opus';  Effort = 'high' }
}

# The per-session environment markers a running Claude session leaves in its
# shell. A successor launched FROM a session must not inherit them (see
# Build-LaunchCommand). Enumerated 2026-09-07 from a live director shell;
# tests/scripts/test_start_directors_orchestrator.py pins the scrub.
$SessionMarkers = @(
    'CLAUDE_CODE_CHILD_SESSION', 'CLAUDE_CODE_SESSION_ID', 'CLAUDECODE', 'CLAUDE_PID',
    'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN',
    'CLAUDE_CODE_BRIDGE_SESSION_ID', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_EXECPATH',
    'CLAUDE_EFFORT'
)

# Short, quoting-safe directive prompts (no newlines, quotes, or semicolons --
# the full multi-line prompt content lives in the bootstrap files to keep the
# command line robust through wt.exe / Start-Process).
$FreshPromptFmt = 'Read and follow {0} -- it is your role bootstrap. Begin now.'
$ResumePrompt = 'Resuming your session: re-read your role section-of-record, run python scripts/role_mail.py read --role {0} --all to drain your inbox, then report current state and await the operator.'

# --- helpers ---------------------------------------------------------------

function Write-Info($msg) { Write-Host "[start-directors] $msg" }
function Write-Err($msg) { Write-Host "[start-directors] ERROR: $msg" }

function Get-LaunchArgs($role) {
    # Per-role claude launch flags: model + effort from $RoleLaunch (the
    # bootstrap-declared START config) unless the operator overrode either for
    # this launch (-Model / -Effort; ValidateSet-bounded, so only the listed
    # values can reach the command line); the permission mode is shared.
    # NOTE: PowerShell variable names are case-INSENSITIVE, so the locals must
    # not be spelled $model/$effort or they shadow the -Model/-Effort params.
    $cfg = $RoleLaunch[$role]
    $useModel = $cfg.Model
    $useEffort = $cfg.Effort
    if ($script:Model) { $useModel = $script:Model }
    if ($script:Effort) { $useEffort = $script:Effort }
    return @('--model', $useModel, '--effort', $useEffort, '--permission-mode', 'auto')
}

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
        throw "this claude CLI ($version) does not advertise --model in --help (every role launches with an explicit --model from `$RoleLaunch); refusing to launch with a guessed flag."
    }
    if (-not ($help -match '--effort')) {
        throw "this claude CLI ($version) does not advertise --effort in --help (every role launches with an explicit --effort from `$RoleLaunch); refusing to launch with a guessed flag."
    }
    # Verify EVERY effort level the launcher actually uses (role-aware via
    # $RoleLaunch) resolves in --help, so a CLI that drops a level we use
    # fails preflight instead of at launch.
    $levels = @($RoleLaunch.Values | ForEach-Object { $_.Effort })
    if ($script:Effort) { $levels += $script:Effort }
    $levels = @($levels | Sort-Object -Unique)
    foreach ($lvl in $levels) {
        if (-not ($help -match $lvl)) {
            throw "this claude CLI ($version) does not list '$lvl' as an effort level in --help; update the launcher's `$RoleLaunch to levels the installed CLI accepts."
        }
    }
    if (-not ($help -match '--permission-mode')) {
        throw "this claude CLI ($version) does not advertise --permission-mode in --help (directors launch with '--permission-mode auto'); refusing to launch with a guessed flag."
    }
    if (-not ($help -match '"auto"')) {
        throw "this claude CLI ($version) does not list 'auto' as a --permission-mode choice in --help; update the launcher's launch flags (Get-LaunchArgs) to a mode the installed CLI accepts."
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
    # The orchestrator is not a director -- give it its own non-'director-'
    # display name; directors keep the established 'director-<role>-<stamp>'.
    if ($role -eq 'orchestrator') { return "orchestrator-$stamp" }
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
    #
    # SCRUB THE PARENT SESSION'S MARKERS FIRST (2026-09-07, the RD self-launch
    # finding; coa-chess verified the mechanism). When this launcher runs from
    # INSIDE a Claude session (the rollover sequence, harness-architecture
    # section 6), Start-Process inherits that session's environment, and a child
    # claude that sees CLAUDE_CODE_CHILD_SESSION / CLAUDE_CODE_SESSION_ID / the
    # messaging socket+token starts with TRANSCRIPT SAVING OFF (no resume, no
    # transcript for cell_depth.py to read) and the PARENT'S identity. The scrub
    # runs inside the spawned shell so it covers BOTH vehicles (wt tab, plain
    # window) identically. The global CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS flag
    # is deliberately NOT removed (harmless, not a session marker).
    $scrub = ($SessionMarkers | ForEach-Object { "Remove-Item Env:$_ -ErrorAction SilentlyContinue" }) -join '; '
    return "$scrub; `$env:SWING_ROLE='$role'; Set-Location '$RepoRoot'; claude " + ($argList -join ' ')
}

function Get-EncodedCommand($inner) {
    # Base64(UTF-16LE) payload for 'powershell -EncodedCommand'. This is the
    # ROBUST way to hand a multi-statement command to a window. wt.exe parses
    # ';' on its OWN command line as a tab delimiter, so passing
    # '-Command "a; b; c"' through 'wt new-tab' splits it into THREE tabs (the
    # SWING_ROLE assignment, a bogus 'Set-Location' executable tab, and claude
    # WITHOUT SWING_ROLE) -- which silently defeated the unread hook. An
    # EncodedCommand blob carries no ';' or quotes for wt to misparse, so the
    # whole command reaches one shell intact. Used on BOTH paths (no divergence).
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
}

function Start-RoleWindow($role, $title, $argList) {
    # $argList is the claude argument array (everything after 'claude'); the
    # spawned shell sets SWING_ROLE so the director's UserPromptSubmit hook fires.
    $inner = Build-LaunchCommand $role $argList
    $encoded = Get-EncodedCommand $inner
    $useWT = (-not $NoWT) -and ($null -ne (Get-Command wt.exe -ErrorAction SilentlyContinue))
    if ($useWT) {
        $wtArgs = @('-w', '0', 'new-tab', '--title', $title, '-d', $RepoRoot, 'powershell', '-NoExit', '-EncodedCommand', $encoded)
        Start-Process -FilePath 'wt.exe' -ArgumentList $wtArgs
    }
    else {
        if ($NoWT) { Write-Info "launching $title in a plain window (-NoWT)." }
        else { Write-Info "wt.exe not found; launching $title in a plain window." }
        Start-Process -FilePath 'powershell' -ArgumentList @('-NoExit', '-EncodedCommand', $encoded)
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
    $argList = (Get-LaunchArgs $role) + @('-n', "`"$name`"", "`"$prompt`"")
    Write-Info "fresh $role -> session name '$name'"
    Write-Info "  cmd: $(Format-Cmd $argList)"
    Write-Info "  launch: $(Build-LaunchCommand $role $argList)"
    Write-Info "  spawn : powershell -NoExit -EncodedCommand $(Get-EncodedCommand (Build-LaunchCommand $role $argList))"
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
    $argList = (Get-LaunchArgs $role) + @('--resume', "`"$name`"", "`"$prompt`"")
    Write-Info "resume $role -> session name '$name'"
    Write-Info "  cmd: $(Format-Cmd $argList)"
    Write-Info "  launch: $(Build-LaunchCommand $role $argList)"
    Write-Info "  spawn : powershell -NoExit -EncodedCommand $(Get-EncodedCommand (Build-LaunchCommand $role $argList))"
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
