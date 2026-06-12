# Writing-Plans Dispatch Brief — Phase 16 / Arc 1: Pipeline-Run Observability

**Arc:** Phase 16 (Observability & Logging) / **Arc 1** — pipeline-run observability.
**Cycle stage:** `copowers:writing-plans` (produce an executing-ready implementation plan, Codex-converged). SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged to main (re-QA'd, incl. the finviz_fetch non-consecutive correction).
**Source of truth (LOCKED, merged to main):** [`docs/superpowers/specs/2026-06-08-pipeline-observability-design.md`](superpowers/specs/2026-06-08-pipeline-observability-design.md) — **READ IT END-TO-END.** The plan implements that spec; it does NOT re-litigate it. The §6 test contracts + §10 "flagged for writing-plans" are your raw material.
**Branch-from:** main HEAD at worktree creation (currently `e19cdad9`; **re-verify with `git log --oneline -3`** — the operator commits research to main in parallel; only docs have been added since the spec merged, so SOURCE line numbers should be unchanged, but re-confirm).
**Schema:** **v24 → v25** (migration `0025`). This is the one schema-touching Phase-16 item — the plan MUST carry the migration discipline (pure-DDL file under the existing `_apply_migration`; new `_phase16_backup_gate` with STRICT `current_version == 24 AND target >= 25`; migrate-twice no-op; #9 explicit-transaction path).
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-08-pipeline-observability-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED pipeline-observability spec into an ordered, TDD-structured, executing-ready task plan: the `configure_logging` seam + `pipeline.log` with the two-belt redaction (1a), and the `Lease` monotonic step-timing ledger + single flush-at-finalize + migration `0025` `pipeline_step_timings` + repo + per-step/aggregate log lines (1b) — each task with its failing-test-first ordering, exact files, discriminating acceptance, and commit message.

The design is settled (Codex-converged, 6 rounds, re-QA-passed). Your job is the **plan**: task decomposition, the TDD test→impl→commit ordering, exact per-task acceptance, and resolving the decisions the spec §10 deferred to writing-plans (§3 below). **Do NOT redesign** — if you believe the spec is wrong, STOP and flag it, don't silently deviate.

---

## 2. STEP 0 — re-ground (cheap; the spec already grounded these)

The spec grounded its anchors on the pre-merge HEAD; only docs were added since, so source lines should hold. On your worktree HEAD, re-confirm before pinning task line numbers:

- **1a surfaces:** the DEVNULL spawn @[web/routes/pipeline.py:127-131](../swing/web/routes/pipeline.py) (KEEP DEVNULL — spec §4.2); `configure_web_logging` @[middleware/request_id.py:32-50](../swing/web/middleware/request_id.py) (`TimedRotatingFileHandler`, becomes a shim); the CLI entrypoint `pipeline_run_cmd` @[cli.py:3210](../swing/cli.py) (configures no logging today — the wiring point); `ensure_schwab_log_redaction_factory_installed` @[client.py:201](../swing/integrations/schwab/client.py) + the per-record redactor @[client.py:170](../swing/integrations/schwab/client.py).
- **1b surfaces:** the **14** `lease.step()` call sites (13 distinct names; finviz_fetch @634 [inbox-empty] + @758 [unconditional], weather @723 between them — spec §2/§5.1); `lease.step()` @[lease.py:53-62](../swing/pipeline/lease.py); the `Lease` class @[lease.py:36](../swing/pipeline/lease.py); `run()`'s `finally` @[runner.py:1034](../swing/pipeline/runner.py) (where the flush call lands — currently `hb.stop()` + `audit_conn.close()`); the lease-always-bound proof (`acquire_lease` in the outer try @560-572 returns at 572 BEFORE the big try @586/finally @1034 — **orchestrator-verified on disk, it holds**); `_now_iso()` @[lease.py:28-29](../swing/pipeline/lease.py); the charts-only slow-step warning @[runner.py:3214-3226](../swing/pipeline/runner.py) (stays — additive).
- **Migration/DB surfaces:** `pipeline_runs` DDL @[0003:120-143](../swing/data/migrations/0003_phase2_pipeline_trades.sql); `_apply_migration` @[db.py:252-295](../swing/data/db.py); the `_b7_backup_gate` TEMPLATE @[db.py:1029-1066](../swing/data/db.py) + its wiring in `run_migrations` @[db.py:1141](../swing/data/db.py) + the migrate-twice early-return @[db.py:1090](../swing/data/db.py); the `connect()` helper @[db.py:65](../swing/data/db.py). **Confirm the latest migration is `0024` so `0025` is the next number** and v24→v25 is correct.

---

## 3. Decisions the spec §10 deferred to YOU (resolve in the plan)

1. **Slow-step advisory soft-budget (spec §5.4).** Pick the SINGLE advisory soft-budget constant (default the charts 60s shape) for the per-step `WARN` line. Log-severity ONLY — NOT a control-flow gate, NOT an error. Name it + place it (a module constant). Per-step budgets can be tuned later without schema churn; do not over-engineer a per-step table.
2. **Repo home (spec §5.5).** New `swing/data/repos/pipeline_step_timings.py` vs fold into `swing/data/repos/pipeline.py`. Spec leans **separate file** (focused unit). Resolve + justify.
3. **Ledger-on-`Lease` + single flush entry (spec §10).** Confirm the ledger state lives on `Lease` (co-located with `step()`), `flush_step_timings()` is the SOLE public flush entry, called EXACTLY once from `run()`'s `finally` (guarded by `_timings_flushed`, set True only AFTER commit), and no other `lease.step` caller path bypasses the finally. Make this an explicit task acceptance.
4. **`complete`-boundary semantics (spec §5.2).** Document in the plan that the final `lease.step("complete")` opens a pending entry closed at flush, whose `duration_ms` measures genuine post-`export` finalization (`_step_review_log_cadence` + `release` + teardown) — small but real; do NOT special-case or drop it. An executor must not "fix" the brief `complete` duration as a bug.

---

## 4. Plan shape (guidance — you own the final decomposition)

TDD tasks, each: write the failing test → see it fail → minimal impl → see it pass → commit (conventional, no Co-Authored-By). A natural ordering (map each to the spec §6 test contracts):

- **Task 1 — the `configure_logging` seam (spec §4.1).** New top-level `swing/logging_config.py` `configure_logging(logs_dir, *, surface, level=INFO, formatter=None)`; `configure_web_logging` → thin shim calling it (`surface="web"`). Schwab-agnostic (imports nothing from `swing.integrations.schwab`). Tests: §6.7 seam regression (`web.log` produced identically — existing web.log tests stay green), `pipeline.log` produced for `surface="pipeline"`, idempotent dedup by `baseFilename`, **and the R2-Major-2 case**: a `formatter=` supplied when a same-file default-formatter handler already exists must `setFormatter` (not silently no-op). NO schema, NO redaction yet.
- **Task 2 — `RedactingFormatter` (Belt B) + subprocess entrypoint wiring (spec §4.2).** `RedactingFormatter` in the Schwab integration package (consults the LIVE redactor per record via `_make_redactor_from_global()` — R2-Major-1). Wire `pipeline_run_cmd` (cli.py:3210) BEFORE `run_pipeline`: (1) `ensure_schwab_log_redaction_factory_installed()` [Belt A first], (2) `configure_logging(..., surface="pipeline", formatter=RedactingFormatter(...))` [Belt B]. Tests: §6.1 (BOTH belts — a sentinel through a **non-Schwabdev** logger AND inside an **exception traceback** AND a **late-registered** secret all redacted in the written `pipeline.log`; handler carries `RedactingFormatter` at attach time), §6.5 (direct `swing pipeline run` self-containment).
- **Task 3 — migration `0025` + `_phase16_backup_gate` (spec §5.3).** Pure-DDL `0025_phase16_pipeline_step_timings.sql` (the exact DDL in §5.3 — `UNIQUE(run_id, ordinal)`, no separate run_id index, no `step_name` CHECK enum, `NOT NULL` finished_ts/duration_ms, `ON DELETE CASCADE`). New `_phase16_backup_gate` mirroring `_b7_backup_gate`, STRICT `current_version == 24 AND target >= 25`, `PHASE16_PRE_MIGRATION_EXPECTED_TABLES` = the v24 set (NOT including `pipeline_step_timings`), wired after `_b7_backup_gate` in `run_migrations`. Tests: §6.6 (migrate-twice no-op via the real runner; v24→v25 backup, v24→v26 backup, v25→v26 inert; the explicit `BEGIN`/`executescript`/`COMMIT`/rollback path).
- **Task 4 — `StepTiming` dataclass + repo + mapper, ONE task (#11 atomicity, spec §5.5).** Frozen `StepTiming` + `_row_to_step_timing` + `insert_step_timings` (batch, `ON CONFLICT(run_id, ordinal) DO NOTHING` — §5.3 Major-9) + `list_step_timings` (`ORDER BY ordinal ASC`) + the mandatory `step_durations_by_name(conn, run_id) -> dict[str,int]` (`SUM(duration_ms) GROUP BY step_name`). Read-path + write-path land together. Tests: round-trip; aggregate-by-name; idempotent re-flush (§6.4c).
- **Task 5 — `Lease` ledger + `lease.step()` close/open + log lines (spec §5.1/§5.4).** Init the ledger in `Lease.__init__`; `step()` keeps its existing `update_step` write UNCHANGED and additionally closes the prior `_pending` (duration via `time.monotonic()`, integer-truncated) + opens a new entry (ordinal `_next_ordinal++`); emit the per-step `INFO` line **including `ordinal`** (R4-Major-1, so the two finviz_fetch entries are distinguishable) + the advisory `WARN` over the §3.1 soft-budget. NO consecutive-collapse rule (removed — spec §5.1). Tests: §6.2 (discriminating fast-vs-slow durations — compute the expected ordering under correct AND naive impls), **§6.3 (the REAL inbox-empty sequence `finviz_fetch`→`weather`→`finviz_fetch` through a runner/Lease harness → two finviz rows at ordinals 0/2, weather at 1; aggregation sums; NOT a synthetic two-in-a-row — cite the synthetic-vs-production-shape gotcha)**, §6.3b (non-empty path: weather=ordinal 0, finviz_fetch=ordinal 1, one finviz row).
- **Task 6 — `flush_step_timings()` + the `run()` finally call (spec §5.2/§5.4).** Single flush: close final `_pending`, emit the per-step final line + **the aggregate-by-`step_name` summary line BEFORE the fallible DB write (R5-Major-1)**, then the one `contextlib.closing(connect(db_path))` + single `with conn:` batch INSERT; `_timings_flushed=True` only AFTER commit. Call it from `run()`'s `finally` (lease always bound — §2) wrapped in `try/except Exception: log.error(...)` that NEVER re-raises (cannot mask an in-flight exception) and NEVER blocks finalization. Tests: §6.4 (terminal coverage — `failed` mid-step AND `force_cleared` mid-step persist partial timings via the fresh `connect()`), §6.4b (flush-failure degrades cleanly: run outcome unchanged, error logged, in-flight exception not masked, per-step lines AND the aggregate summary line present in `pipeline.log`).
- **Task 7 — full suite + ruff + Windows encoding (spec §6.8).** `python -m pytest -m "not slow" -q` green (isolate the 3 known xdist co-residency flakes — run `-n0` to confirm); `ruff check swing/`; assert no non-ASCII in new operator-facing strings; the file handler is utf-8.

Pin each task's exact files, the **discriminating assertion** ([[feedback_regression_test_arithmetic]] — compute the value under both correct and naive paths to confirm the test distinguishes), and the commit message.

---

## 5. Locks / invariants (from spec §8 — propagate; do not regress)

- **Schema v24 → v25** — the single schema touch; migration `0025` pure DDL; backup gate STRICT `pre_version == 24`; migrate-twice no-op. DB-outside-Drive. `busy_timeout` unchanged.
- **Phase isolation:** change loci = `swing/logging_config.py` (new), `swing/web/middleware/request_id.py` (shim), `swing/cli.py` (entrypoint wiring), `swing/pipeline/lease.py` + `swing/pipeline/runner.py` (ledger + flush call), `swing/data/migrations/0025_*.sql` + the new repo/dataclass + `swing/data/db.py` (backup gate). `swing/web/routes/pipeline.py` UNCHANGED (DEVNULL kept). **`swing/trades/` stays read-only.**
- **Redaction is two belts** — Belt A (factory) installed in the subprocess entrypoint BEFORE any emit; Belt B (`RedactingFormatter`) on the `pipeline.log` handler set BEFORE the handler is added to root (no unredacted window). `configure_logging` stays Schwab-agnostic (the CLI injects the formatter).
- **No new per-step lock-contention point** — timing persistence is ONE batch transaction at finalize on a plain `connect()` (respects the `database is locked` deadlock scars + the single-transaction `BEGIN IMMEDIATE` contract).
- **Corrected timing semantic** — ordinal = unique monotonic ordering key; `step_name` = non-unique aggregation key (finviz_fetch yields two rows); consumers `SUM(duration_ms) GROUP BY step_name`. No "strictly linear" assumption; no consecutive-collapse rule.

---

## 6. Out of scope / banked (carry to the plan's out-of-scope §)

- **Arc 2** (centralized config beyond the seam, retention/cleanup of the 225MB logs dir, the level knob beyond the `level` param existing, log-volume right-sizing, web↔subprocess correlation). The `level` param exists but is NOT wired to a knob here.
- **1c** (yfinance call-timing audit) and **the perf fix** (cap/parallelize/cache yfinance) — deferred / gated on the data THIS arc produces.
- **Arc 3** (XMAX thumbnail), **Arc 4** (equity reconciliation). No change to Schwab call LOGIC — only its log-surface coverage.

---

## 7. copowers process (binding)

- **Run `copowers:writing-plans`** — wraps `superpowers:writing-plans` then the adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Do not stop early; do not pad after convergence.
- **Codex transport (WSL CLI; the MCP `codex` tool is DEAD in the VS Code extension):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every Codex round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md` for independent orchestrator convergence-confirmation at QA.
- **No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose** (no `Word:`-leading line → trailer-parse hazard). Commit ONLY the plan doc.
- **Return a report:** the plan path; how you resolved the §3 deferred decisions (the soft-budget constant, the repo home, the single-flush-entry confirmation, the `complete`-boundary note); the Codex convergence verdict (round count + final line); anything flagged for executing. Then STOP — do NOT execute. Executing is a separate commission after the orchestrator QAs the plan.
