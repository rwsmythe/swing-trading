# Commissioning Brief — 19-C: weeknight-pipeline Windows Scheduled Task

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-C ([`phase19-scope-charc.md`](phase19-scope-charc.md)). **Committed:** 2026-07-03 HST. **Operator demand:** 2026-06-27 (unattended weeknight pipeline runs), unblocked by the 19-B full close (witnessed 2026-07-03).
**§3 verdict: TRIPWIRE CROSSED (new standing process — a scheduled job) → this brief IS the CHARC architecture pass. GO, with the §1 conditions BINDING.** No other tripwire: NO schema (v31), NO new `swing/` module (`scripts/` additions are outside the module tripwire), NO dependency, NO `swing/trades`/`swing/data` carve-out. A small `swing/cli.py` affordance is in-scope if the plan needs it (existing-module edit, sub-tripwire).

## §0 References (verified on disk 2026-07-03)

- **CLI:** `swing pipeline run` (`swing/cli.py:3729`, `pipeline_run_cmd`; also `pipeline list` / `pipeline force-clear` `:3754/:3777`). Entry point: `%APPDATA%\Python\Python314\Scripts\swing.exe` (user editable-install; CLAUDE.md §Quick Start PATH note).
- **Lease collision:** `acquire_lease` (`swing/pipeline/lease.py:242-291`) — race-safe `BEGIN IMMEDIATE` + the `ux_pipeline_one_running` partial unique index; a fresh-heartbeat active run raises **`ConcurrentRunBlockedError`**; `stale_lease_threshold_seconds` + `pipeline force-clear` exist for stale-lease recovery.
- **The 19-B protections (the safety floor, witnessed 2026-07-03):** anchor-consistency (a run reads+writes+pushes ONE config-derived root) · lease-or-silent (only leased runs post to comms) · the broken-context guard (suspicious-empty ⇒ write nothing + `warnings_json`). A wrong-context task run now SELF-CONTAINS instead of poisoning production.
- **Unattended-auth hardening (Phase 15/18-H):** the non-setup Schwab paths are protected by `_assert_v3_tokens_db_loadable_or_raise` + `call_on_auth=_raise_on_auth` + `open_browser_for_auth=False` — no `input()`/browser hang reachable headless; the market-data ladder falls through to yfinance on Schwab failure; domain writes are sandbox/production-gated.
- **Holiday evidence:** runs 118/119/120 all `data_asof=2026-07-02` (one nightly + two witness runs) — same-asof re-runs are live-proven harmless.
- The banked design-Q list: [`phase19-scope-charc.md`](phase19-scope-charc.md) 19-C row.

## §1 CHARC architecture pass — BINDING conditions

- **C1 — Launch context (the #5/RD-HOME-vector lesson):** the task runs **as the operator's user account** (`rwsmy`) with the standard profile — NEVER `SYSTEM`/a service account (a foreign `USERPROFILE` resolves a different home-anchored DB; the 19-B guard would suppress-and-warn, but the run would be useless). The task action uses **ABSOLUTE paths everywhere** (the exe; `--config` if passed) and sets **"Start in" = the MAIN repo root** (`C:\Users\rwsmy\swing-trading`). Never a worktree, never PATH-dependent resolution (a scheduled-task PATH is not the interactive PATH).
- **C2 — Collision = graceful skip:** `ConcurrentRunBlockedError` (an operator manual run in progress) maps to **exit 0 + a log line**, NOT a task failure (a red task icon on every benign collision is alarm fatigue). Task Scheduler policy: "Do not start a new instance." Stale-lease handling stays the existing `force-clear` operator path — the task does NOT auto-clear (an unattended auto-`force-clear` could kill a live manual run; explicitly OUT of scope).
- **C3 — No interactive auth reachable, verified:** a discriminating check that an unattended run with a stale/absent Schwab token COMPLETES (degraded to yfinance via the ladder) with no hang. The 7-day refresh-TTL expiring mid-week is EXPECTED steady-state; the degrade is the design, `swing schwab status` + 18-H.1 token-health surface the staleness.
- **C4 — Observability = the existing spine, plus a scheduler-level floor:** in-app logging (`pipeline.log`), the run ledger, the 18-D/18-E monitors, the GUI stoplights, and the lease-verified RED push already cover a completed-but-unhealthy run. The wrapper adds ONLY a minimal scheduler-level log (an append-one-line result file under `logs/` or similar) for the class that never reaches in-app logging (exe-not-found, config-missing, interpreter failure). No new monitoring machinery.
- **C5 — Holiday/weekend posture: no special logic required.** A holiday/weekend fire is a harmless same-asof re-prep (§0 evidence). An optional session-aware skip is POLISH, operator's preference at plan review — correctness does not depend on it.
- **C6 — The 19-B floor is a backstop, not the design.** Build the task CORRECT per C1; the anchor-consistency/guard/lease-or-silent protections are the net underneath, not the plan.

## §2 Scope

1. **A wrapper script** under `scripts/` (PowerShell) — absolute-path invocation of `swing pipeline run`, the C2 graceful-skip mapping, the C4 scheduler-level result line, ASCII-only output (the cp1252 CLI gotcha).
2. **Idempotent task registration** — a `scripts/` register script (`Register-ScheduledTask` or `schtasks`) creating/updating the task (+ an unregister path), so the task definition is CODE-REVIEWED and reproducible, not hand-clicked. Registration is executed BY THE OPERATOR (his account/credentials) at the witness.
3. **A small CLI affordance if the plan needs it** (e.g., a distinct exit code or `--skip-if-running` on `pipeline run` so the wrapper can distinguish `ConcurrentRunBlockedError` from real failures) — `swing/cli.py` existing-module edit, TDD'd.
4. **A runbook** (`docs/runbooks/`) — schedule, how to pause/resume/unregister, the collision/stale-lease/token-degrade playbook.

**Defaults to confirm with the operator at plan review:** fire time **17:30 HST** (market long closed at 10:00 HST; evening review window preserved) · days **Mon–Fri** · "run as soon as possible after a missed start" ON · wake-the-computer + battery/AC conditions = operator's power-reality call · logon type ("run only when logged on" vs S4U "whether logged on or not") = operator's preference at the witness.

## §3 Design questions for writing-plans (bounded)

Exact exit-code mapping for `ConcurrentRunBlockedError` through click (wrapper pattern-match vs the §2.3 CLI flag — prefer the flag: explicit contract over string-matching); `Register-ScheduledTask` idempotency (update-in-place vs unregister-recreate); the S4U environment realities (profile loading, HOME/USERPROFILE under batch logon — verify against C1 with a real scheduled fire, not assumptions); where the scheduler-level result line lives.

## §4 Gates

1. **CHARC plan-stage confirm** (my tripwire arc — the plan returns through me for the C1–C6 conditions check, like 19-B's config-shape confirm). Operator confirms the §2 schedule defaults at the same review. RD: fyi at return only (the weeknight cadence sits WITHIN the 18-D monitor assumptions; flag to RD if the plan unexpectedly touches monitor semantics).
2. TDD where testable (the wrapper mapping, the CLI flag); the registration script is verified at the witness, not unit-mocked into false confidence.
3. review-strong to convergence + codex-auto-review; merged-head no-false-green; ruff.
4. **BINDING OPERATOR WITNESS (two stages):** (a) register the task + a one-off NEAR-TERM scheduled fire (a real scheduler-context launch — NOT just right-click "Run now", and not only a manual shell invocation of the wrapper): verify the run completes, artifacts land in MAIN correctly, the run ledger shows the row, and a deliberate collision (manual run in progress) produces the graceful skip; (b) the FIRST real weeknight fire (next trading weeknight) confirms steady-state — the arc closes on (b).
5. The ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA; the implementer never posts to directors.

## §5 Sizing + dispatch recommendation

Small-medium; Windows-specific care (Task Scheduler logon types, cp1252, absolute-path discipline) over algorithmic depth. CHARC recommendation: **writing-plans `implementer-opus-high`** (bounded design Qs), **executing `implementer-opus-high`** (the unattended-context subtleties + this repo's gotcha density argue against sonnet here). Orchestrator owns the final cell selection + announces before spawn.
