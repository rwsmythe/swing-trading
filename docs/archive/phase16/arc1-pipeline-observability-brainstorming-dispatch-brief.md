# Brainstorming Dispatch Brief — Phase 16 / Arc 1: Pipeline-Run Observability

**Arc:** Phase 16 (Observability & Logging) / **Arc 1** — pipeline-run observability. The triggering arc: web-Run #96 (2026-06-08) took ~10m25s; Schwab calls were only 25.5s, leaving ~570s of pre-Schwab (yfinance-bound) work with ZERO timing visibility, *unloggable* because the web-spawned subprocess discards stdout/stderr. This arc makes the next slow run precisely attributable per step.
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). **FULL copowers cycle** (operator-chosen): this brainstorm → writing-plans → executing, each its own commission after orchestrator QA. The operator chose full-cycle partly to design the **Arc-1a-pipeline.log ↔ Arc-2a-centralized-`configure_logging` seam** up front (see OQ-1).
**Branch-from:** main HEAD at worktree creation (currently `20b07a2d`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel, so expect drift; rebase-onto-main + `merge --ff-only` is the merge discipline, not your concern at brainstorm).
**Schema:** **YES — this cycle touches schema (v24 → v25).** Operator decision (2026-06-08): 1b persists per-step durations to the DB (queryable, feeds the perf follow-on), NOT log-only. Migration `0025_*`; backup-gate strict equality `pre_version == 24 AND target >= 25`; the migration-runner explicit-`BEGIN`+`executescript`+`COMMIT` discipline (#9) applies. Lock the table/column SHAPE in the spec (this is the pivotal schema OQ-2).
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-08-pipeline-observability-design.md` + Codex convergence + `.copowers-findings.md` (prompts AND responses, gitignored).

---

## 1. Mandate (one line)

Design (a) a `pipeline.log` so the pipeline subprocess's per-step logs survive (today they're discarded), with Schwab redaction guaranteed on that surface, and (b) per-step DURATION capture (log line + DB persistence) across all pipeline steps — so the next slow run answers "which step owns the time" outright, instead of being inferred.

---

## 2. The current state (grounded on HEAD, verify before designing)

**1a — the subprocess output is discarded.** The web spawns `python -m swing.cli --config <path> pipeline run --manual` ([web/routes/pipeline.py:121-131](../swing/web/routes/pipeline.py)) with `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`. Nothing configures a `pipeline.log` handler — yet error messages tell operators to "check `swing-data/logs/pipeline.log`" (a file never created). The runner's per-step `log.info` + its built-in slow-step warning (`_walltime_elapsed > 60s/120s`, [runner.py:3214-3224](../swing/pipeline/runner.py) — that warning is CHARTS-step-only today) are lost for web-triggered runs. The ONLY configured file log today is `web.log` via `configure_web_logging(logs_dir)` ([defined middleware/request_id.py:32](../swing/web/middleware/request_id.py), a **`TimedRotatingFileHandler`** — dated rotation, which is why `web.log.2026-05-23` etc. accumulate; called [app.py:441](../swing/web/app.py)).

**The redaction surface.** Schwab secret redaction is `ensure_schwab_log_redaction_factory_installed()` ([client.py:201](../swing/integrations/schwab/client.py)), process-global `setLogRecordFactory`, installed defensively before Schwab calls. The pipeline subprocess makes Schwab calls (`schwab_snapshot`, `schwab_orders` steps) → **`pipeline.log` could leak tokens/accountHash without it.** 1a MUST install the factory in the subprocess entrypoint, early, before any logging (CLAUDE.md §Gotchas/Schwab: "schwabdev's own loggers must be covered by a content-redacting `setLogRecordFactory` … re-checks before each call").

**1b — the step model + what's persisted.** There are **13** `lease.step(name)` transitions in the runner ([runner.py](../swing/pipeline/runner.py)): `finviz_fetch, weather, evaluate, daily_management, watchlist, recommendations, pattern_detect, pattern_observe, schwab_snapshot, schwab_orders, charts, export, complete`. `lease.step()` ([lease.py:53](../swing/pipeline/lease.py)) opens its OWN connection + `with conn:` transaction and calls `update_step(... step, progress_ts)` → rewrites `pipeline_runs.current_step` + `last_step_progress_ts`. `pipeline_runs` ([migration 0003:120-143](../swing/data/migrations/0003_phase2_pipeline_trades.sql)) persists per-step STATUS as **discrete columns for only 6 steps** (`weather_status`/`evaluation_status`/`watchlist_status`/`recommendations_status`/`charts_status`/`export_status`) — NOT a generic step table. **No per-step DURATION anywhere.** Note: consecutive `last_step_progress_ts` deltas already *imply* per-step durations, but they're overwritten each transition and never captured.

---

## 3. The central design questions (the brainstorm's core deliverable)

1. **The Arc-1/Arc-2 seam (scope).** Should 1a build a *standalone* `pipeline.log` rotating-file handler now (refactored into Arc-2a's centralized `configure_logging(logs_dir, *, level, surface)` later — risks throwaway + a refactor), OR pull the centralized-config *seam* (the function shape + per-surface routing) FORWARD into Arc 1 so `pipeline.log` is born the right way, leaving Arc 2a to retention/level-knob/volume/correlation? Recommend + justify; the operator confirms (OQ-1). Do NOT build the full Arc-2 overhaul here regardless — design the seam, not the whole system.
2. **The 1b persistence shape (schema, pivotal).** Per-step duration as discrete `pipeline_runs` COLUMNS (mirrors the status-column pattern — but only 6 of 13 steps have those, doesn't scale, churns the wide table) vs a normalized child table **`pipeline_step_timings`** (`run_id` FK, `step_name`, `started_ts`, `finished_ts`/`duration_ms`, ordinal) — scales to all 13 + future steps, queryable for the perf follow-on, the cleaner relational shape. Recommend (lean: the child table) + lock the exact DDL (OQ-2).
3. **Where the timing is captured + WRITTEN.** Hook the `lease.step()` transition (record the *previous* step's end + duration when transitioning) vs a runner-level monotonic ledger flushed at `release()`. Whatever you choose MUST respect the fence/lock discipline — `lease.step()` already opens its own connection; the recent `database is locked` deadlock fix + the #16 fetch-hoist are fresh scars (CLAUDE.md §Gotchas/SQLite: "Service-layer `with conn:` opens its own transaction"; the `BEGIN IMMEDIATE` single-transaction contract). Do NOT add a new lock-contention point or a write inside an outer fenced transaction.

---

## 4. Things to nail (each needs a test where applicable)

- **Redaction on `pipeline.log` is proven, not assumed.** A sentinel-leak test: plant a non-token secret-shaped sentinel through a pipeline log path, assert it's redacted in `pipeline.log` (extend the existing Schwab sentinel-leak audit to the new surface). Factory installed BEFORE the first log emit in the subprocess entrypoint.
- **Subprocess self-containment.** The handler must work for BOTH web-spawned (DEVNULL parent) AND direct `swing pipeline run` CLI invocation — a file handler on the child, independent of parent stdout.
- **Windows encoding** (CLAUDE.md §Gotchas/Windows): the file handler must not choke on non-ASCII; the CLI stdout cp1252 footgun applies to any console echo path. Prefer ASCII in any new operator-facing strings; ensure the file handler uses UTF-8.
- **Every step timed, not just charts.** Promote the `_walltime_elapsed` slow-step warning pattern from charts-only to all 13 steps; the `complete` pseudo-step boundary must finalize the last real step's duration.
- **Failed / blocked / force_cleared runs.** Durations must persist (or degrade cleanly) when a run ends `failed`/`blocked` mid-step — partial timings are exactly what a slow/hung run needs. Tie the flush to `release()`/finalize, not only the happy path.
- **Migration round-trip + backup gate.** Migrate-twice no-op test; `pre_version == 24 AND target >= 25` strict-equality backup gate; the runner's explicit `BEGIN`+`executescript`+`COMMIT`+rollback path (#9). If any new CHECK/enum lands, the schema-CHECK + Python-constant + dataclass-validator land in ONE task (#11) with read-path `_row_to_*` widened alongside the write path.

---

## 5. Locks / invariants

- **Schema v24 → v25** (this cycle's one schema touch); DB stays OUTSIDE the Drive dir; busy_timeout unchanged.
- **Phase isolation:** the change loci are `swing/pipeline/` (runner, lease), `swing/web/routes/pipeline.py` (the spawn — possibly just removing DEVNULL if 1a uses a child-side handler), the logging-config surface, and `swing/data/migrations/` + the `pipeline_runs`/new-table repo. `swing/trades/` stays read-only.
- **1c (yfinance call-timing audit) is DEFERRED — OUT of this cycle.** It's optional + likely its own schema; flag anything that *enables* it but don't build it.
- **The perf follow-on is OUT** (gated on Arc 1's timing data — do NOT propose the yfinance cap/parallelize/cache fix in this spec; measuring is the whole point).
- **Discriminating tests** (`feedback_regression_test_arithmetic`): for the timing-persistence test, assert the persisted duration distinguishes a fast vs slow step (not just "a row exists").

---

## 6. Open questions for the operator (brainstorming surfaces + resolves these)

- **OQ-1 — the Arc-1/Arc-2 seam:** standalone `pipeline.log` handler now vs pull the centralized `configure_logging` seam forward. (The operator chose full-cycle to settle this; it's the lead decision.)
- **OQ-2 — 1b persistence shape:** `pipeline_runs` duration columns vs a `pipeline_step_timings` child table. Lock the DDL. (Pivotal — it's the schema.)
- **OQ-3 — duration granularity + units:** `duration_ms` int vs float seconds; whether to also persist per-step `started_ts`/`finished_ts` (enables gap analysis between steps) or duration only.
- **OQ-4 — log format/level for `pipeline.log`:** match `web.log`'s format/rotation (`TimedRotatingFileHandler`) for consistency now, or introduce the size-based rotation Arc-2b will want? (Don't solve retention here — but don't paint Arc 2 into a corner.)

---

## 7. copowers process (binding)

- Run `copowers:brainstorming` (wraps `superpowers:brainstorming` — explore the §6 OQs WITH the operator — then the adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED for this project).
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (the PATH prefix is REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` is unreachable from WSL — pre-generate the diff on Windows + tell Codex NOT to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR` line) to gitignored `.copowers-findings.md`.
- No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose (verify `git log -1 --format='%(trailers)'` is `[]`). Commit ONLY the spec doc this phase.
- **Return a report:** the spec path; the resolved §6 OQs (the seam decision + the locked table/column DDL + WHY); the Codex convergence verdict (round count + final line); anything flagged for writing-plans. Then STOP — do NOT proceed to writing-plans (a separate commission after the orchestrator QAs the spec).

---

## 8. What this arc is NOT

NOT the Arc-2 logging overhaul (centralized config beyond the seam, retention/cleanup of the 225MB logs dir, the level knob, volume right-sizing, web↔subprocess correlation — all separate). NOT 1c (yfinance audit, deferred). NOT the perf fix (gated on the data this arc produces). NOT Arc 3 (XMAX thumbnail) or Arc 4 (equity reconciliation). NOT a change to `swing/trades/` or the Schwab call logic itself — only its log-surface coverage.
