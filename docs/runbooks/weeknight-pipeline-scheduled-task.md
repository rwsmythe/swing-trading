# Runbook — weeknight-pipeline Windows Scheduled Task (19-C)

Unattended weeknight execution of `swing pipeline run` via Windows Task
Scheduler. This runbook is the operator surface for the schedule, the
register/pause/unregister actions, and the collision / stale-lease /
token-degrade playbook.

**Deliverables:**
- `scripts/run-weeknight-pipeline.ps1` — the wrapper Task Scheduler fires.
- `scripts/register-weeknight-task.ps1` — idempotent register/update.
- `scripts/unregister-weeknight-task.ps1` — idempotent teardown.

Run the register/unregister scripts **from the MAIN checkout, as yourself**
(`C:\Users\rwsmy\swing-trading`) — never a worktree, never elevated-as-SYSTEM.

---

## Schedule (operator-confirmed)

| Setting | Value |
|---|---|
| Fire time | **17:30 HST** |
| Days | **Mon-Fri** |
| Start ASAP after a missed start | **ON** (`-StartWhenAvailable`) |
| Wake the computer to run | **OFF** (`-WakeToRun` off) |
| Battery conditions | **permissive** (start on battery + do not stop on battery) |
| Multiple instances | **IgnoreNew** ("Do not start a new instance") |
| Logon type | **Interactive** ("run only when logged on") — S4U is hard-refused in V1 |
| Scheduler ExecutionTimeLimit | **2h** (the OUTER backstop) |
| Wrapper `-RunTimeoutMinutes` | **45** (the INNER process-tree-kill bound) |

### Schedule rationale (incl. the data-quality note)

17:30 HST is well after the 10:00 HST market close (evening review window
preserved). **The 17:30 HST slot (23:30 ET, ~7.5h post-close) is LATER than a
typical manual evening run, and plausibly REDUCES the ragged-SHAPE yfinance bar
inflow** (the invalid_ohlc capture-timing correlation): the later capture gives
the provider more time to finalize the day's adjusted-close, so fewer trailing
NaN-Close bars arrive. **The run time is a DATA-QUALITY parameter, not just
convenience — do NOT move it earlier without weighing the ragged-inflow
consideration** (the 19-D capture-timing trace will confirm or kill this
correlation later).

### Two logon-type / catch-up interactions to expect

- **Interactive only (V1).** The machine must be logged on (or locked while
  logged on) at fire time. If it is fully logged off / shut down, the fire is
  missed and — because `-StartWhenAvailable` is ON — runs LATER when the machine
  next becomes available and you next log on.
- **Off-window catch-up is EXPECTED and harmless.** A missed 17:30 fire can
  catch up on a Saturday, Sunday, or a weekday morning. That is a same-asof
  re-prep (the lease + collision-skip + the 19-B launch-context guard all still
  apply); it re-preps the last-completed session's data. An off-window line in
  `weeknight-task.log` is NOT a fault. If you prefer NO catch-up, re-register
  with `-StartWhenAvailable:$false` (a missed fire is then simply skipped).

---

## Register / update / pause / unregister

All commands run from `C:\Users\rwsmy\swing-trading`.

### Register or update (idempotent, `-Force`)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-weeknight-task.ps1
```

Re-running is safe (create-or-replace in one call). The script prints the
resolved principal, the Interactive logon type, and the trigger list — eyeball
that `Principal.UserId` is YOUR account and `LogonType` is `Interactive`.

### Pause / resume (without unregistering)

```powershell
Disable-ScheduledTask -TaskName 'SwingWeeknightPipeline'   # pause
Enable-ScheduledTask  -TaskName 'SwingWeeknightPipeline'   # resume
```

### Unregister (teardown)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\unregister-weeknight-task.ps1
```

Idempotent: prints "already absent" and exits 0 if the task is gone.

---

## Playbook

### Off-window catch-up
Expected (see above). A same-asof re-prep. Nothing to do.

### Collision (a manual run overlaps the scheduled fire)
Expected and benign when a LIVE manual run is in progress. The wrapper writes a
`SKIP` line and exits 0 (the task stays green — no red icon). The collision maps
`ConcurrentRunBlockedError` -> CLI exit 75 (EX_TEMPFAIL) -> wrapper SKIP ->
exit 0. Nothing to do.

**But a `SKIP` is NOT always benign.** The CLI returns `blocked` (-> exit 75 ->
`SKIP`) for BOTH cases below, and the wrapper cannot tell them apart from the
exit code alone:
1. a live manual run holding a fresh-heartbeat lease (benign — the SKIP is
   correct), OR
2. an ORPHANED `running` row left by a previously crashed / wrapper-killed run
   (a STALE lease — see below). This one does NOT self-heal: the
   `ux_pipeline_one_running` partial-unique index rejects every new insert while
   that row stays `running`, so EVERY later fire logs `SKIP` until the operator
   force-clears it. **The real signal here is the tool-health stoplight going
   RED** (`swing/monitoring/tool_health.py` pipeline-freshness: yellow at >=1
   session behind the last COMPLETE run, RED at >=2 / no completed run) — a
   string of `SKIP` lines with NO intervening `OK` while the stoplight is RED
   means a stale lease, not a live manual run.

### Stale lease (a crashed / killed run left the lease held)
The task NEVER auto-force-clears (an unattended auto-clear could kill a live
manual run — plan C2). A wrapper `TIMEOUT`/`TIMEOUT-KILL-FAILED` line, or
persistent `SKIP` lines with the pipeline-freshness stoplight RED, is your cue.
Recover manually:

```powershell
swing pipeline list                         # find the stuck run id + state
swing pipeline force-clear <id>             # two-signal staleness check
swing pipeline force-clear <id> --bypass-staleness-check   # crashed-worker case
```

`force-clear` requires BOTH staleness signals (heartbeat age AND step-progress
age) unless `--bypass-staleness-check` is passed. **Note:** a run killed by the
wrapper's process-tree kill leaves its `pipeline_runs` row `running` (the SIGKILL
skips graceful lease release); it does NOT auto-clear. The pipeline-freshness
stoplight is the backstop that surfaces the resulting stall; recovery is this
`force-clear`.

**Detection channels — the wedged-lease mode is PUSH-INVISIBLE (RD/CHARC, 2026-07-04).** The 18-H.7 research-health RD notify fires ONLY from a leased run; in the wedge NO run executes, so the RD inbox is structurally NEVER pinged — **do NOT wait for an inbox push that cannot come.** Detection rests on: (a) the tool-health pipeline-freshness stoplight going RED at the 18-F GUI (passive — requires looking); (b) the weekly-glance newest-artifact-age line (active, worst-case ~5 trading sessions to the Friday glance); (c) the result file's `TIMEOUT` -> `SKIP` -> `SKIP` morning pattern. The latency is acceptable — a wedged pipeline is pure staleness (no data corruption; CALIBRATION C accepts the missed sessions as historical once un-wedged, no monitor change) — but "the stall surfaces at the GUI" must NOT be read as "RD gets pinged": it does not.

### Token degrade (stale/absent Schwab token)
A stale 7-day Schwab refresh-TTL is EXPECTED steady-state; the run completes via
the yfinance ladder-fallthrough (no hang — the non-setup Schwab paths raise a
clean `SchwabAuthError` before any interactive prompt). `swing schwab status`
surfaces days-remaining. Recover a REAL token loss with a genuine re-auth:

```powershell
swing schwab logout
swing schwab setup
```

**For the C3 witness ONLY** (simulating absent tokens on demand) use the
REVERSIBLE token-file backup below — NOT `logout`/`setup`, which forces a
needless re-auth.

### Where to look
- `C:\Users\rwsmy\swing-data\logs\weeknight-task.log` — the scheduler-level
  floor: one line per fire the wrapper survives (OK / SKIP / FAIL / ERROR /
  TIMEOUT / TIMEOUT-KILL-FAILED).
- `C:\Users\rwsmy\swing-data\logs\pipeline.log` — the in-app run log.
- `swing pipeline list` — the run ledger.
- The GUI health stoplights (`swing web`).
- **Task Scheduler's own run history / `LastTaskResult`** — the ONLY surface for
  the residual case where the WRAPPER ITSELF was scheduler-killed at the 2h
  `ExecutionTimeLimit` (no in-file line, because PowerShell never resumed to
  write one). Wrapper-caught hangs (the normal case) DO write a `TIMEOUT` line.

---

## Operator witness procedures (two stages; the arc closes on stage b)

### Stage (a) — register + near-term real scheduler-context fire + demos

1. **Register** (as yourself):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-weeknight-task.ps1
   ```
2. **Principal check (C1):**
   ```powershell
   (Get-ScheduledTask SwingWeeknightPipeline).Principal.UserId       # your account
   (Get-ScheduledTask SwingWeeknightPipeline).Principal.LogonType    # Interactive
   [Security.Principal.WindowsIdentity]::GetCurrent().Name           # must match UserId
   ```
   Confirm the completed run's DB/exports resolved under YOUR
   `%USERPROFILE%\swing-data` (not a foreign/empty home).
3. **Near-term real scheduler-context fire** — script a one-off trigger ALONGSIDE
   the weekly one (no manual Task Scheduler clicking):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-weeknight-task.ps1 -IncludeOneOffAt (Get-Date).AddMinutes(3)
   ```
   Let **Task Scheduler** launch it (NOT right-click "Run now", NOT a manual
   shell invocation of the wrapper). Verify: the run completes, artifacts land in
   the MAIN tree, `swing pipeline list` shows the row, and `weeknight-task.log`
   gains one `OK` line.
4. **Schedule-integrity RESTORE (MANDATORY before stage b):**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register-weeknight-task.ps1
   (Get-ScheduledTask SwingWeeknightPipeline).Triggers   # weekly trigger ONLY
   ```

#### Collision demo (deterministic, heartbeat-kept lease holder)

Hold a FRESH-heartbeat lease in the PRODUCTION DB (so the scheduled fire
collides), then let the task fire and confirm exit 0 + a `SKIP` line + no red
icon + the held lease row unaffected. Do NOT use a bare `acquire_lease + sleep`
(a sleep past `block_if_running_within_seconds` = 120s ages the lease OUT of the
blocking window and silently stops exercising the collision). Use the SAME
heartbeat mechanism a real run uses. Run from the MAIN checkout:

```python
from swing.config import load
from swing.pipeline.lease import acquire_lease
from swing.pipeline.heartbeat import Heartbeat
import time

cfg = load("swing.config.toml")
L = acquire_lease(db_path=cfg.paths.db_path, trigger="manual",
                  data_asof_date="2026-07-02", action_session_date="2026-07-03")
hb = Heartbeat(lease=L, interval_seconds=cfg.pipeline.heartbeat_interval_seconds)
hb.start()
try:
    time.sleep(240)          # outlives block_if_running_within_seconds; stays FRESH via hb
finally:
    hb.stop()
    # DO NOT release as "complete" -- that would fabricate a false-green completed
    # run in the production pipeline_runs ledger. Release to force_cleared with an
    # explicit marker so the row is unambiguously a demo artifact, not a real run.
    L.release(state="force_cleared",
              error_message="19-C collision-demo synthetic lease; no pipeline executed")
```

#### C3 no-hang check (reversible token-file backup — NOT logout/setup)

Exercise the absent-token branch WITHOUT a destructive re-auth. The tokens DB is
`~/swing-data/schwab-tokens.<env>.db` (+ `-wal`/`-shm` if present):

```powershell
$db = "$env:USERPROFILE\swing-data\schwab-tokens.production.db"   # or .sandbox.db
Copy-Item $db "$db.bak" -Force                                    # reversible backup
Rename-Item $db "$db.aside"                                       # simulate absent tokens
# ... let a scheduled fire launch (or the -IncludeOneOffAt one-off) ...
# BINDING check: NO HANG -- the run terminates in the normal ~2-3 min, never at the
# 2h ExecutionTimeLimit; no input()/browser prompt. EXPECTED: a completed run via the
# yfinance ladder-fallthrough. A fast-fail without a hang also PASSES C3 (auth-safety)
# but flags a separate yfinance-fallthrough regression to investigate.
Rename-Item "$db.aside" $db                                       # restore -- no re-auth
```

### Stage (b) — the first real weeknight fire

The next trading weeknight's 17:30 HST fire confirms steady state. **The arc
closes on (b).**
