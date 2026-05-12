# Phase 9 — Risk_Policy + Reconciliation Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Decomposition:** plan is structured as 5 sub-bundles (A–E) per dispatch-brief §1.2; orchestrator dispatches each bundle as an independent executing-plans run with its own Codex review chain. Cross-bundle dependencies are flagged at each task's "Depends on" field.

**Goal:** Land schema v16 → v17 migration that creates five new tables (`risk_policy`, `reconciliation_runs`, `reconciliation_discrepancies`, `hypothesis_status_history`, `account_equity_snapshots`) + ADDs two columns (`trades.risk_policy_id_at_lock`, `review_log.risk_policy_id_at_review_completion`); implement repos + services + CLI surface for risk_policy editing; refactor `swing/journal/tos_import.py:reconcile_tos` to persist reconciliation_runs + per-discrepancy rows + extend coverage with close-price-mismatch + stop-mismatch + position-qty-mismatch + cash-movement-mismatch detection; wire route-layer sector/industry tamper rejection at `/trades/entry` mirroring chart_pattern hardening; append-only `hypothesis_status_history` audit via single-write-path service helper; manual `account_equity_snapshots` capture via CLI; per-row policy stamping at Phase 7 entry-lock + Phase 6 review-completion paths.

**Architecture:** Schema-first slice extends Phase 8 baseline (v16) with 5 new tables + 2 nullable column adds, ALL no-rebuild (CREATE TABLE / CREATE INDEX / ALTER ADD COLUMN per spec §9.2). Five new repo modules under `swing/data/repos/` (`risk_policy.py`, `reconciliation.py`, `account_equity_snapshots.py`); `hypothesis_status_history` repo helpers live alongside existing `hypothesis.py` (single hypothesis-domain module per project convention). Three new service modules under `swing/trades/` (`risk_policy.py` — CRUD + supersession 6-step sequence + cfg-mirror cascade; `reconciliation.py` — TOS-CSV reconciliation orchestration consuming refactored `swing/journal/tos_import.py:reconcile_tos`; `account_equity_snapshots.py` — snapshot capture + back-fill threshold flag). Hypothesis-status audit service helper lands in existing `swing/trades/hypothesis.py` (NEW module — the existing hypothesis CRUD is currently a thin CLI handler in `swing/cli.py` reading repo functions directly; Phase 9 introduces the service layer at `swing/trades/hypothesis.py:update_hypothesis_status_with_audit` per spec §3.4.1 single-write-path discipline). CLI extends `swing/cli.py` with three new command groups: `swing config policy {set,show,import-from-toml}`, `swing journal reconcile-tos {--csv-path,--period-end,--notes}` (REFACTORED from existing `swing journal import-tos`), `swing account snapshot {--equity,--date,--notes}`, `swing journal discrepancy {list,resolve,show}`. Route-layer sector/industry tamper hardening lands in `swing/web/routes/trades.py` (entry POST handler) mirroring chart_pattern hardening commits `117dc97` + `2b9d6f3`. Phase 7 `entry_create` service path + Phase 6 `complete_review_atomic` repo gain a one-line stamp from `risk_policy.is_active=1` per spec §3.1.1.

**Tech Stack:** SQLite (migration **0017** — verified next-available per §A.0 audit; PRAGMA foreign_keys=OFF runner discipline inherited from Phase 7 hotfix `283d4fa`); pytest; click (CLI extension); FastAPI + Starlette `TemplateResponse` + HTMX (existing route-layer infra); jinja2 (templates extending `base.html.j2`); existing `swing/journal/tos_import.py:reconcile_tos` (refactor target — preserves dataclass return shape, adds reconciliation_runs persistence side-effect); existing `swing/data/db.py:_apply_migration` (migration runner; no carve-out; backup gate fires only on `current_version == 16 AND target >= 17`).

---

## §A — Resolved-during-planning items (empirical-audit findings)

These are findings from the §0 empirical audit (Step 5 pre-plan grep recon per dispatch brief §5) that diverge from spec wording or surface implementation contracts that the spec deliberately deferred to writing-plans dispatch (per spec §1.2 + §10 + brief §1.1). The plan implements the reconciled positions below; they DO NOT contradict the spec's locked decisions in §3-§9 — they refine implementation paths and surface a small set of empirical-finding-driven design choices.

### §A.0 Migration filename + schema-version collision (BINDING ALL filename references)

**Spec §9.1 said:** "Migration file: `swing/data/migrations/0016_phase9_risk_policy_and_reconciliation.sql`" (with hedge: "check writing-plans for actual numbering against shipped migrations").

**Empirical finding:** the repo already has `swing/data/migrations/0016_phase8_daily_management.sql` (Phase 8 shipped 2026-05-07, merge `ddfdfcb`); `swing/data/db.py:EXPECTED_SCHEMA_VERSION = 16`. If Phase 9 ships at `0016_*` the runner (`run_migrations`) collides with the existing 0016 file.

**Resolution (BINDING for ALL plan tasks):** Phase 9 migration filename is **`0017_phase9_risk_policy_and_reconciliation.sql`**. Schema bump is v16 → v17 per spec §9.1 binding intent. Test filename is **`tests/data/test_migration_0017.py`** + **`tests/data/test_migration_0017_runner_discipline.py`**. Backup file `swing-pre-phase9-migration-<ISO>.db` (filename anchor independent of migration-number prefix). All task-spec text below uses `0017` consistently (per §J grep at writing-plans dispatch).

**Spec ambiguity disposition:** ACCEPT-WITH-RATIONALE per brief §1.1; flagged in return-report orchestrator-triage section. Pattern complement to Phase 8 plan §A.0 (same family — spec drafted before the prior phase's migration-number bump landed).

### §A.0.1 risk_policy column count reconciliation (Codex R1 Major #2 fix)

**Spec §3.1 said:** "**Field count:** 28 columns (7 metadata + supersession + 13 trading-risk + 5 statistics-methodology grade weights, etc.)."

**Empirical finding (Codex R1 Major #2):** counting the spec §3.1 column TABLE produces 34 distinct field names:
- 7 metadata: policy_id, effective_from, effective_to, is_active, superseded_by_policy_id, created_at, policy_notes.
- 7 trading-risk: max_account_risk_per_trade_pct, max_concurrent_positions, max_portfolio_heat_pct, max_sector_concentration_positions, consecutive_losses_pause_threshold, consecutive_losses_pause_action, consecutive_losses_streak_reset.
- 5 drawdown circuit breaker: drawdown_circuit_breaker_enabled, drawdown_pause_threshold_R, drawdown_pause_action, drawdown_size_reduction_pct, drawdown_recovery_threshold_R.
- 1 capital: capital_floor_constant_dollars.
- 9 statistics-methodology: scratch_epsilon_R, review_lag_threshold_days, low_sample_size_threshold_class_a/b/c/d_n, global_confidence_floor_n, bootstrap_resample_count.
- 3 grade weights: process_grade_weight_entry / management / exit.
- 3 MFE/MAE + trail-MA: mfe_mae_default_precision_level, trail_MA_period_days, trail_MA_post_2R_period_days.

Total: 7+7+5+1+9+3+3 = **34 columns**.

**Resolution (BINDING for T-A.1 + T-A.3):** the column LIST is the binding artifact; the spec's "28 columns" subtotal is a brainstorm-phase miscount. All plan tests + DDL + dataclass assert/check 34 columns. Migration DDL implements all 34 columns per the spec column table. The miscount does NOT change the schema — it changes the assertion target in tests.

**Spec ambiguity disposition:** ACCEPT-WITH-RATIONALE; flagged in return-report orchestrator-triage section. Spec text's "28 columns" subtotal is corrected at writing-plans dispatch time without amending the spec; spec column list (the actual binding artifact) is preserved.

### §A.1 Hypothesis-status audit service module placement

**Spec §3.4.1 said:** "every code path that UPDATEs `hypothesis_registry.status` MUST flow through a single `hypothesis_repo.update_status_with_audit(...)` helper."

**Empirical finding:** `swing/data/repos/hypothesis.py:90` defines `update_hypothesis_status(conn, hypothesis_id, status, change_reason)` — a thin repo-level function that UPDATEs `hypothesis_registry` columns. NO existing service module at `swing/trades/hypothesis.py`. The CLI handler for `swing hypothesis update` reads from `swing/cli.py` and calls the repo function directly. Spec's "single write path" requirement means BOTH the existing repo function AND any future caller must route through a service helper that owns BEGIN IMMEDIATE + appends history row + UPDATEs registry — all in one transaction. Phase 8 R3→R4 lesson ("reject + simple contract over auto-detect + complicate") applies.

**Resolution (BINDING for sub-bundle C):** introduce **NEW module `swing/trades/hypothesis.py`** owning `update_hypothesis_status_with_audit(conn, *, hypothesis_id, new_status, change_reason) -> Literal["transition","noop_identity"]`. This service:

1. Rejects caller-held transaction at entry (`if conn.in_transaction: raise CallerHeldTransactionError(...)` — mirror Phase 8 `record_event_log` contract).
2. `BEGIN IMMEDIATE TRANSACTION` (acquires write lock first).
3. SELECT current status from `hypothesis_registry` (now reads under the lock — Phase 9 spec R2 M2 fix).
4. If `current_status == new_status`: ROLLBACK + return `"noop_identity"` sentinel (Phase 9 spec R3 Minor #1 — distinct from error path; CLI renders as INFO).
5. UPDATE `hypothesis_status_history SET effective_to = ? WHERE hypothesis_id = ? AND effective_to IS NULL` (closes prior open interval).
6. INSERT new `hypothesis_status_history` row (status, effective_from=now_ms, effective_to=NULL, change_reason, recorded_at=now_ms).
7. UPDATE `hypothesis_registry SET status = ?, status_changed_at = ?, status_change_reason = ? WHERE id = ?`.
8. COMMIT.

`swing/data/repos/hypothesis.py:update_hypothesis_status` is **REFACTORED** to delegate to the service helper (or DELETED if no other caller exists post-CLI-rewire — see §A.1.1). The CLI handler in `swing/cli.py:hypothesis_update_cmd` is **rewired** to call the new service helper. Phase 9 ships single-write-path discipline with discriminating regression test (T-C.4.4) verifying that DIRECT calls to the OLD repo function path raise (or, if function is deleted, the test passes by import-error).

**§A.1.1 Disposition for `swing/data/repos/hypothesis.py:update_hypothesis_status`:**

The existing repo-level function is called from EXACTLY ONE site per grep recon: `swing/cli.py:hypothesis_update_cmd` (CLI handler for `swing hypothesis update`). No web routes, no pipeline steps, no other service modules. Plan disposition: **DELETE** the existing repo function in T-C.4.2 after rewiring the CLI handler in T-C.4.3 to call the new service helper. Discriminating test T-C.4.4 verifies the symbol is gone via `with pytest.raises(ImportError): from swing.data.repos.hypothesis import update_hypothesis_status`. Closes the single-write-path discipline at schema-level (no stale callable to invoke).

**Asymmetry note:** the service-layer `swing/trades/hypothesis.py:update_hypothesis_status_with_audit` is the canonical entry point for ANY operator-facing status change. A future hypothesis-management web surface MUST also route through it. Phase 10 plan dispatcher inherits this contract.

### §A.2 Reconciliation-service module placement + tos_import.py refactor scope

**Spec §4.2 + §6.5 said:** "The existing `swing/journal/tos_import.py:reconcile_tos` returns a `ReconciliationReport` dataclass; writing-plans refactors it to ALSO write `reconciliation_runs` + `reconciliation_discrepancies` rows as a side-effect within a single transaction."

**Empirical finding:** `swing/journal/tos_import.py` houses 9 module-level functions including `parse_tos_export`, `extract_cash_movements`, `extract_stock_fills`, and `reconcile_tos`. The function takes (csv_text, conn) + returns `ReconciliationReport`. Persistence is currently scattered: cash_movements are inserted inline; fills are inserted inline. No reconciliation-run-level audit table is consulted today.

**Resolution (BINDING for sub-bundle B):** introduce **NEW module `swing/trades/reconciliation.py`** owning `run_tos_reconciliation(conn, *, csv_path, period_end=None, notes=None, source_artifact_sha256_override=None) -> ReconciliationRun`. This service:

1. Rejects caller-held transaction at entry.
2. Reads + parses the TOS CSV via existing `parse_tos_export` (no change to that helper).
3. `BEGIN IMMEDIATE TRANSACTION`.
4. INSERTs `reconciliation_runs` row (`state='running'`, source='tos_csv', source_artifact_path, source_artifact_sha256, period_start, period_end, started_ts=now).
5. Calls REFACTORED `swing/journal/tos_import.py:reconcile_tos(conn, csv_text, *, run_id, emitter)` — the refactored signature accepts an emitter callable that receives `(discrepancy_type, **fields) -> int` (returning the inserted discrepancy_id). The refactor preserves the `ReconciliationReport` return shape so existing CLI consumers see no breakage. The emitter is the seam between the existing journal-import logic and the new reconciliation_discrepancies INSERT path.
6. Per-discrepancy emission inside same transaction via emitter callable (close_price_mismatch, stop_mismatch, position_qty_mismatch, cash_movement_mismatch, entry_price_mismatch, unmatched_open_fill, unmatched_close_fill, equity_delta per §6.1–§6.4).
7. UPDATE `reconciliation_runs SET state='completed', finished_ts=now, discrepancies_count=N, unresolved_discrepancies_count=N, trades_reconciled_count=..., fills_reconciled_count=..., summary_json=..., account_equity_*=...`.
8. COMMIT.
9. Failure-path (per spec §3.3.3, Codex R1 Major #1 fix — was previously specified as ROLLBACK+INSERT-new-row; corrected to match spec): catch the exception inside the same transaction → UPDATE the existing run row's `state='failed', finished_ts=now, error_message=str(e)` → COMMIT. The run row is PRESERVED so the operator sees what failed (mirrors `pipeline_runs` failure semantics). Discrepancies emitted prior to the failure are RETAINED inside the same commit as the failed-state UPDATE. This implies the BEGIN IMMEDIATE wraps step 4 (INSERT run row) + step 6 (emitter inserts) + step 7-or-9 (UPDATE state); a single transaction with two possible terminal UPDATEs.

**§A.2.1 cash_movements + fills inline-insert disposition:** the existing inline INSERTs of cash_movements + new fills inside `reconcile_tos` are RETAINED inside the new outer transaction. **Failure-path consequence (per Codex R1 Major #1 fix):** on exception, the same UPDATE-to-failed semantics apply — cash_movements + fills inserted PRIOR to the exception ARE PRESERVED in the committed transaction alongside the failed-state UPDATE. Operator-visible UX: a failed reconciliation may have partial data persisted (some fills imported successfully before the parse error hit a later row). This is intentional per spec §3.3.3 — audit-trail integrity prioritized over rollback purity. Discriminating regression test T-B.6.5: inject a synthetic exception AFTER emitter has fired for 2 discrepancies; assert run row present with state='failed' + error_message populated + 2 discrepancy rows present + transaction NOT in_transaction post-call.

**§A.2.2 CLI rename:** existing CLI `swing journal import-tos` is **RENAMED** to `swing journal reconcile-tos` per spec §4.2 wording. Backwards-compatibility: short-window deprecation alias for one phase (V1 Phase 9 ships both names; alias prints deprecation warning to stderr; alias removed in V2). Discriminating test T-B.7.3 verifies both invocations route to the same service.

### §A.3 Risk_Policy CLI surface decision (per spec §10.5 "writing-plans-decides")

**Locked:** V1 ships per-field CLI per spec §10.5 brainstorm recommendation. Bulk CLI + web form deferred to V2.

CLI commands:
- `swing config policy show` — print the active risk_policy row in human-readable form.
- `swing config policy set --field <name> --value <val> [--notes "..."]` — UPDATE one field via the supersession 6-step sequence.
- `swing config policy import-from-toml --field <name>` — copy current cfg value into a new policy row (operator's explicit ratification path per spec §3.1.3 R3 Minor #2).
- `swing config policy history [--limit N]` — print recent policy versions.

Bulk + web deferred per spec §10.5. Out-of-scope for V1 per same.

### §A.4 Sector/industry tamper hardening route-layer integration

**Spec §7 said:** "mirrors `chart_pattern` hardening at `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`."

**Empirical finding:** chart_pattern hardening at trade-entry POST does: (1) lookup cached candidate by `(ticker, action_session)`; (2) reject the POST if form-submitted chart_pattern doesn't match cached chart_pattern; (3) return HTMX-friendly error fragment.

**Resolution (BINDING for sub-bundle D):** Phase 9 extends the same handler with sector + industry rejection. Plan adds explicit acceptance criteria covering: (a) form sector matches cached → proceed; (b) form sector mismatches cached → reject + emit `sector_tamper` discrepancy in an ad-hoc reconciliation_run (`source='system_audit'` per spec §3.2 R1 Minor #2 enum value); (c) form industry mismatches cached → same. Discriminating test pattern clones the chart_pattern hardening tests (`tests/web/test_trade_entry_chart_pattern_*`); plan T-D.2.* adds `tests/web/test_trade_entry_sector_industry_tamper.py`.

**§A.4.1 ad-hoc reconciliation_run emission semantics:** the sector_tamper rejection emits a one-shot reconciliation_run with `source='system_audit'` and `state='completed'` inside the entry-POST handler. This is a SECOND transaction independent of the rejected entry (the entry POST is rejected, so its transaction does NOT commit; the audit row commits separately). Discriminating test T-D.2.5 verifies that even when the entry POST is rejected, the audit row persists.

### §A.5 cfg-mirror cascade at risk_policy save

**Spec §3.1.3 said:** "Phase 5 config page edit MUST cascade to a new `risk_policy` row (writing-plans wires this)."

**Empirical finding:** `swing/web/routes/config.py` (Phase 5) handles the config-page edits. Currently the route writes to `swing.config.toml` via `swing/config_overrides.py:write_overrides`. No risk_policy cascade today.

**Resolution (BINDING for sub-bundle A):** the cfg-mirror cascade is implemented in T-A.5 — when Phase 5 config-page edit lands a change to `cfg.account.risk_equity_floor`, the route ALSO calls `swing/trades/risk_policy.py:supersede_active_policy(conn, *, field_updates={"capital_floor_constant_dollars": new_value}, source="cfg_cascade", notes="...")`. The cfg-mirror logic lives in the existing Phase 5 route handler (no new route); the cascade is a one-liner call into the new service. **Other cfg fields** (`web.chase_factor`, `pipeline.chart_top_n_watch`) DO NOT cascade — they have no risk_policy correspondence per spec §3.1.3.

**§A.5.1 startup TOML divergence detection (Codex R3 Major #1 fix — architecturally revised):** the original plan had `swing/config.py:load_config` itself perform a DB-read divergence check and mutate `cfg.account.risk_equity_floor` in-place. This is NOT executable against the current architecture for three concrete reasons:

1. **`Config` and `Account` are frozen dataclasses** (verified at `swing/config.py:10`, `swing/config.py:23`, `swing/config.py:266`+; the project uses `@dataclass(frozen=True)` extensively for cfg). In-place attribute mutation raises `FrozenInstanceError`.
2. **`load(config_path)` is a pure function with no DB connection parameter** (verified at `swing/config.py:308`). Adding a `conn` parameter changes the public API of the config loader.
3. **CLI command lifecycle:** CLI handlers call `load_config()` BEFORE invoking `ensure_schema` (verified at `swing/cli.py:111`, `swing/cli.py:120`, `swing/cli.py:143`). Reading risk_policy from inside `load_config` would fail on (a) fresh DBs that have not yet migrated, (b) tests that monkey-patch a TOML path but use no DB at all, and (c) the `swing db-migrate` invocation itself which is supposed to bring the DB to v17.

**Revised disposition (BINDING for T-A.5 + T-A.5-tests):**

- `swing/config.py:load(config_path)` REMAINS PURE — no DB connection parameter, no risk_policy read. The function returns the immutable `Config` from TOML as today.
- A NEW helper `swing/trades/risk_policy.py:check_and_reconcile_toml_divergence(conn, cfg) -> tuple[Config, dict | None]` performs the divergence check. Returns `(new_config, divergence_info_or_None)`. When divergent, builds a corrected `Config` via `dataclasses.replace(cfg, account=dataclasses.replace(cfg.account, risk_equity_floor=policy_value))`; logs WARNING; returns the new immutable Config + divergence dict. When not divergent, returns `(cfg, None)`.
- The divergence check is invoked at TWO post-schema-validation hook points:
  - **CLI entry hook** in `swing/cli.py`: AFTER `ensure_schema(conn)` succeeds AND AFTER `load_config()` succeeds, a small startup sequence calls `check_and_reconcile_toml_divergence(conn, cfg)` to derive the corrected `cfg`. The CLI handler's local `cfg` variable is rebound to the corrected Config (since Config is immutable, the variable rebind is the only valid mutation surface). The divergence dict (if non-None) drives the stderr advisory banner per spec §3.1.3 R3 Minor #2.
  - **Web app startup** in `swing/web/app.py` (or wherever the FastAPI lifespan hook lives): same pattern. The web app's `app.state.cfg` is set to the corrected Config after divergence check.
- **The `db-migrate` CLI command** explicitly DOES NOT call the divergence check (since it's the path that brings the DB to v17; running divergence check before v17 is reached is the failure mode Codex flagged). Plan T-A.5 verifies via discriminating test that `swing db-migrate` from v16 → v17 succeeds with NO divergence-check side effect.
- **Fresh-DB / test fixtures** that don't have a risk_policy table yet (v16 schema or earlier) skip the divergence check entirely. The helper handles this via try/except `NoActivePolicyError` (or sniff schema_version) and returns `(cfg, None)` silently for pre-v17 DBs.

**Discriminating test T-A.5.4 (revised per Codex R3 M#1):** sets a divergent TOML value + invokes CLI command that triggers the post-schema-validation hook + asserts (a) WARNING log fires, (b) the returned corrected Config has `account.risk_equity_floor == policy_value`, (c) the original `cfg` from `load()` is unchanged (`is` identity test against the frozen dataclass), (d) TOML file on disk unmodified. Mirror test T-A.5.5: invoke `swing db-migrate` on a v16 DB; assert it succeeds with NO divergence check triggered (no WARNING log).

**Impact on T-A.5 and §B file map:** T-A.5 file modifications are revised:
- `swing/config.py` — UNCHANGED public API; no DB-read added. (Was previously planned to be modified.)
- `swing/cli.py` — extension at every CLI handler that needs a divergence-corrected cfg: invoke the helper after `ensure_schema`; rebind local `cfg` to the corrected value.
- `swing/web/app.py` (or lifespan/middleware) — same pattern at startup; sets `app.state.cfg` to corrected Config.
- `swing/trades/risk_policy.py` — `check_and_reconcile_toml_divergence(conn, cfg)` helper replaces the prior `apply_toml_divergence_correction(conn, cfg)` function.

The §B file map "modify `swing/config.py`" line is REMOVED from T-A.5; the cfg-cascade for Phase 5 config-page edits (the *other* §A.5 concern) still touches `swing/web/routes/config.py` but NOT `swing/config.py`.

### §A.6 Test count projection bias

Per dispatch brief §0.2 baseline 2328 fast tests + Phase 8 plan §A.7 precedent ("biased high"), Phase 9 plan projects **+200 to +320 fast tests** (range, NOT a single number) across all 5 sub-bundles. Per-task projections in §J biased high; subtotal is +245 baseline → executing-plans dispatch acceptance criteria use the RANGE not the point estimate.

### §A.7 In-flight production data state

Per CLAUDE.md HEAD `88c7d6b`: production DB at schema_version 16 with `daily_management_records` table + `trades.planned_target_R` column shipped. Per spec §9.4 + recent shipping notes: 4–5 trades total (VIR closed+reviewed; DHC/CC/YOU/LAR/VSAT or similar open; states `entered` / `managing` / `partial_exited`); 5+ fills; 11+ trade_events; 1+ review_log rows; 4 hypothesis_registry rows (seeded by migration 0008; none mutated).

**Backwards-compatibility consequences (LOCKED):**

1. All existing trades have `risk_policy_id_at_lock IS NULL` after migration — read paths treat NULL as "resolve to current `risk_policy.is_active=1` row" per spec §9.4. Discriminating regression test T-A.4.5 inserts legacy-style trade pre-migration + asserts read path returns current policy.
2. All existing review_log rows have `risk_policy_id_at_review_completion IS NULL` after migration — analogous read-path behavior. Discriminating regression test T-A.4.6.
3. Seed migration inserts ONE `hypothesis_status_history` row per existing hypothesis_registry row (4 rows total at writing-plans time per current DB state). Effective_from = hypothesis_registry.created_at normalized to millisecond precision per spec §3.4.1 R3 Major #2. Discriminating regression test T-C.1.5 verifies all 4 seed rows present + `effective_to IS NULL` + status matches registry.

### §A.8 No `INSERT OR REPLACE` in Phase 9 paths (preserved from CLAUDE.md gotcha)

Pre-plan grep recon (Step 5) confirmed **zero** matches for `INSERT OR REPLACE` / `REPLACE INTO` across `swing/`. Phase 8 closed the only outstanding instance via `upsert_snapshot` SELECT-then-UPDATE-or-INSERT pattern. Phase 9 inherits the discipline: 
- `risk_policy` supersession uses 6-step transactional sequence (UPDATE predecessor → INSERT successor → UPDATE FK pointer) per spec §4.1 — no REPLACE.
- `account_equity_snapshots` UPSERT per `(snapshot_date, source)` uses SELECT-then-UPDATE-or-INSERT per spec §3.5.
- `reconciliation_discrepancies.resolution` UPDATE on existing row (operator disposition) — UPDATE only, no REPLACE.
- `hypothesis_status_history` is append-only (closing UPDATE on `effective_to` of prior row; pure INSERT for successor row).

Discriminating regression test pattern T-A.6.5 / T-C.3.4 / T-C.4.4 etc. asserts the table behavior is preserved across reflow (PK stability — REPLACE would assign a new PK; UPDATE preserves it).

### §A.9 Session-anchor read/write predicate alignment

Per dispatch brief §0.3 #8 + CLAUDE.md gotcha "Session-anchor read/write mismatch" — Phase 9 introduces two session-keyed columns:

1. **`account_equity_snapshots.snapshot_date`** — writer (CLI `swing account snapshot`) defaults to `last_completed_session(now())` per spec §4.4. Reader (Phase 10 metric layer's `live_capital_denominator_dollars`) consumes MAX(snapshot_date <= asof_date). Reader's `asof_date` is caller-provided — no Phase 9 internal mismatch. **Phase 10 dispatcher inherits** the requirement to NOT use `action_session_for_run(now())` for "today's equity" lookups; must use `last_completed_session(now())` for symmetry with writer.
2. **`reconciliation_runs.period_end`** — writer (CLI `swing journal reconcile-tos`) defaults to last fill date in parsed CSV per spec §10.6, or operator-passed via `--period-end`. Reader queries are operator-anchored (no implicit "today" semantic). No mismatch surface.

Discriminating regression test T-C.2.5: invoke `swing account snapshot --equity 1000` on a Saturday evening + assert `snapshot_date = last_completed_session(now()).isoformat()` (Friday's date, not Saturday/Monday). Mirrors Phase 8 polish-bundle `cfacbc5` test pattern.

### §A.10 Server-stamping at CLI + route-handler entries (per Phase 8 §A series)

Per dispatch brief §0.3 #9 — Phase 9 form/CLI inputs that interact with audit-trail timestamps default to server-stamping at handler entry:

| Field | Surface | Disposition |
|---|---|---|
| `risk_policy.effective_from` | CLI `config policy set` | Server-stamped at service entry (BEGIN IMMEDIATE→now_ms); NOT operator-supplied. |
| `risk_policy.created_at` | CLI `config policy set` | Server-stamped (same instant as effective_from per spec §3.1 R4 Minor #1 bind-once). |
| `risk_policy.effective_to` | (predecessor row UPDATE) | Server-stamped same-transaction. |
| `account_equity_snapshots.recorded_at` | CLI `account snapshot` | Server-stamped. |
| `account_equity_snapshots.snapshot_date` | CLI `account snapshot` | Operator-supplied OR defaults to `last_completed_session(now())`. |
| `reconciliation_runs.started_ts` / `finished_ts` | CLI `journal reconcile-tos` | Server-stamped. |
| `reconciliation_runs.period_end` | CLI `journal reconcile-tos` | Operator-supplied OR derived from last-fill-date (defensible default). |
| `reconciliation_discrepancies.created_at` | (emitter callable inside reconcile service) | Server-stamped. |
| `reconciliation_discrepancies.resolved_at` / `resolved_by` | CLI `journal discrepancy resolve` | Server-stamped (`resolved_by='operator'` hardcoded V1; resolved_at server). |
| `hypothesis_status_history.effective_from` / `effective_to` / `recorded_at` | CLI `hypothesis update` | Server-stamped. |
| `trades.risk_policy_id_at_lock` | Phase 7 entry-create service | Server-stamped from `risk_policy.is_active=1` at lock-time. |
| `review_log.risk_policy_id_at_review_completion` | Phase 6 review-complete repo | Server-stamped from `risk_policy.is_active=1` at completion-time. |

V1 has NO HTML form for risk_policy / account-snapshot / reconciliation routes (deferred to V2 per §A.3). Phase 9 form-driven surfaces are limited to the existing Phase 5 config page extension (T-A.5) which already follows the Phase 5 R1 Major #1+#2 server-stamping pattern (HX-Request propagation + HX-Redirect success-path).

### §A.11 Datetime precision: SQLite `strftime` form

Per spec §3.1.3 R3 Major #1 + R4 Minor #1 fix — millisecond-precision form is `strftime('%Y-%m-%dT%H:%M:%f', 'now')` in SQL (produces `YYYY-MM-DDTHH:MM:SS.SSS`) AND a single bind in Python via:

```python
def now_ms() -> str:
    """Returns naive-UTC millisecond-precision ISO datetime string."""
    n = datetime.utcnow()
    return n.strftime('%Y-%m-%dT%H:%M:%S.') + f'{n.microsecond // 1000:03d}'
```

Lives in **new helper `swing/data/datetime_helpers.py:now_ms` + `validate_ms_iso(s: str) -> str`** (raises `ValueError` on non-conforming inputs). Plan T-A.0 lands this helper; all Phase 9 services + CLI handlers + migration seed values call it. Discriminating regression test T-A.0.4 verifies (a) two same-instant calls produce identical strings (microseconds truncated identically); (b) cross-day boundary; (c) validator rejects second-precision + tz-aware inputs.

---

## §B — File map

### Files to CREATE

| Path | Responsibility |
|---|---|
| `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql` | Schema bump v16 → v17: CREATE TABLE `risk_policy` (**34 columns** — spec §3.1's "28 columns" subtotal is a brainstorm-phase miscount; the actual column LIST in spec §3.1 enumerates 34 distinct fields, which is the binding artifact per Codex R1 Major #2 fix — see §A.0 for the count reconciliation) + 2 indexes + INSERT seed `policy_id=1`. CREATE TABLE `reconciliation_runs` (17 columns per spec §3.2) + 3 indexes. CREATE TABLE `reconciliation_discrepancies` (18 columns per spec §3.3) + 4 indexes. CREATE TABLE `hypothesis_status_history` (7 columns per spec §3.4) + 2 indexes + INSERT seed rows (one per existing hypothesis_registry row). CREATE TABLE `account_equity_snapshots` (8 columns per spec §3.5) + 2 indexes. ALTER TABLE `trades` ADD COLUMN `risk_policy_id_at_lock INTEGER REFERENCES risk_policy(policy_id)`. ALTER TABLE `review_log` ADD COLUMN `risk_policy_id_at_review_completion INTEGER REFERENCES risk_policy(policy_id)`. UPDATE schema_version SET version = 17. |
| `swing/data/datetime_helpers.py` | `now_ms() -> str` + `validate_ms_iso(s: str) -> str` per §A.11. Imported by all Phase 9 services. |
| `swing/data/repos/risk_policy.py` | Public API: `insert_policy(conn, *, policy_fields) -> int` (pure INSERT inside caller's transaction); `update_policy_active_flag(conn, *, policy_id, is_active, effective_to, superseded_by_policy_id) -> None` (pure UPDATE inside caller's transaction); `get_active_policy(conn) -> RiskPolicy` (raises `NoActivePolicyError` if zero rows match `is_active=1`); `get_policy_by_id(conn, policy_id) -> RiskPolicy | None`; `list_policy_history(conn, *, limit=None) -> list[RiskPolicy]` (ORDER BY effective_from DESC, policy_id DESC per spec §3.1 tiebreaker). |
| `swing/data/models.py` (EXTEND) | NEW dataclasses: `RiskPolicy` (**34 fields** matching schema per §A.0.1 reconciliation; `__post_init__` validator per dispatch brief §0.3 #4 + Bundle 2/3 pattern — NaN/inf rejection on REAL fields, CHECK-IN enum validation, sum-to-1.0 for process_grade_weight_*); `ReconciliationRun`; `ReconciliationDiscrepancy`; `HypothesisStatusHistory`; `AccountEquitySnapshot`. |
| `swing/trades/risk_policy.py` | Service entry-points. Public API: `supersede_active_policy(conn, *, field_updates: dict, notes: str | None = None, source: Literal["cli","cfg_cascade","import_from_toml"]="cli") -> int` (6-step transactional sequence per spec §4.1; rejects caller-held transaction; returns new policy_id); `read_active_policy(conn) -> RiskPolicy` (delegates to repo); `check_and_reconcile_toml_divergence(conn, cfg) -> tuple[Config, dict | None]` (per §A.5.1 — returns corrected immutable Config via `dataclasses.replace` + divergence dict when divergent; returns `(cfg, None)` for pre-v17 / no-active-policy fixtures; called from CLI + web app startup AFTER `ensure_schema`; NEVER from inside `swing/config.py:load`); `seed_initial_policy(conn, cfg) -> int` (called from migration runner OR migration SQL — see T-A.1; idempotent — no-ops if `risk_policy.is_active=1` row exists). |
| `swing/data/repos/reconciliation.py` | Public API: `insert_run(conn, *, run_fields) -> int`; `update_run_completed(conn, *, run_id, summary_fields) -> None`; `update_run_failed(conn, *, run_id, error_message) -> None`; `insert_discrepancy(conn, *, discrepancy_fields) -> int`; `update_discrepancy_resolution(conn, *, discrepancy_id, resolution, resolution_reason, resolved_by, resolved_at) -> None`; `get_run(conn, run_id) -> ReconciliationRun | None`; `get_discrepancy(conn, discrepancy_id) -> ReconciliationDiscrepancy | None`; `list_recent_runs(conn, *, limit=10) -> list[ReconciliationRun]` (two-read pattern per spec §3.2 — separate query for most-recent-COMPLETED + most-recent-STARTED); `list_discrepancies_for_run(conn, run_id) -> list[ReconciliationDiscrepancy]`; `list_unresolved_material_for_active_trades(conn) -> list[ReconciliationDiscrepancy]` (drives §5.1 CANONICAL #1 query); `list_unresolved_material_for_closed_trades(conn) -> list[ReconciliationDiscrepancy]` (drives §5.1 CANONICAL #2 query); `count_runs_for_artifact_sha256(conn, sha256) -> int` (advisory for re-run detection). |
| `swing/trades/reconciliation.py` | Service entry-point. Public API: `run_tos_reconciliation(conn, *, csv_path: Path, period_end: date | None = None, notes: str | None = None) -> ReconciliationRun` (per §A.2 contract); rejects caller-held transaction. `resolve_discrepancy(conn, *, discrepancy_id: int, resolution: str, resolution_reason: str | None = None) -> None` (validator rejects missing reason when resolution requires it per spec §3.3 nullability rule); `MATERIAL_BY_TYPE: dict[str, int]` lookup constant (10 entries per spec §3.3.1; emitter consults at INSERT time). `DISCREPANCY_TYPES: tuple[str, ...]` constant (10 entries per spec §3.3 CHECK enum). `RESOLUTION_TYPES: tuple[str, ...]` constant (5 entries per spec §3.3 CHECK enum). |
| `swing/data/repos/account_equity_snapshots.py` | Public API: `insert_snapshot(conn, *, snapshot_fields) -> int`; `upsert_snapshot(conn, *, snapshot_fields) -> int` (SELECT-then-UPDATE-or-INSERT per spec §3.5; preserves PK on UPDATE); `get_latest_snapshot_on_or_before(conn, *, asof_date: date, with_provenance: bool = False) -> AccountEquitySnapshot | tuple[AccountEquitySnapshot, list[AccountEquitySnapshot]] | None` (source-ladder precedence per spec §3.5 + §11.4; with_provenance returns (winner, suppressed_rows) per R4 Minor #3); `list_snapshots(conn, *, limit=20) -> list[AccountEquitySnapshot]`. |
| `swing/trades/account_equity_snapshots.py` | Service: `record_snapshot(conn, *, equity_dollars: float, snapshot_date: date | None = None, source: str = "manual", notes: str | None = None) -> int` (rejects caller-held transaction; defaults snapshot_date to `last_completed_session(now())` per §A.9; calls upsert; flags back-recorded per spec §3.5). `BACK_RECORD_THRESHOLD_DAYS: int = 7` (per spec §3.5 + writing-plans codification). `is_back_recorded(*, snapshot_date: date, recorded_at: datetime, threshold_days: int = BACK_RECORD_THRESHOLD_DAYS) -> bool`. |
| `swing/data/repos/hypothesis_status_history.py` | Public API (single module per project convention; hypothesis-domain). `insert_history(conn, *, history_fields) -> int`; `update_close_open_interval(conn, *, hypothesis_id, effective_to) -> None` (UPDATE WHERE effective_to IS NULL); `get_current_status(conn, hypothesis_id) -> HypothesisStatusHistory | None` (WHERE effective_to IS NULL); `list_history_for_hypothesis(conn, hypothesis_id) -> list[HypothesisStatusHistory]` (ORDER BY effective_from ASC); `list_all_history(conn) -> list[HypothesisStatusHistory]`. |
| `swing/trades/hypothesis.py` | Service entry-point per §A.1. `update_hypothesis_status_with_audit(conn, *, hypothesis_id: int, new_status: str, change_reason: str | None) -> Literal["transition", "noop_identity"]` (8-step transactional sequence per §A.1; rejects caller-held transaction). `class NoOpIdentityTransition` (sentinel — return shape; NOT an exception). Constants: `HYPOTHESIS_STATUSES: tuple[str, ...] = ("active", "paused", "closed-escaped", "closed-target-met")` (mirrors existing `hypothesis_registry.status` CHECK enum). |
| `tests/data/test_migration_0017.py` | Round-trip test: schema_version → 17; risk_policy table created with **34 columns** (per §A.0.1 reconciliation) + 2 indexes; reconciliation_runs created with 17 cols + 3 indexes; reconciliation_discrepancies created with 18 cols + 4 indexes; hypothesis_status_history created with 7 cols + 2 indexes; account_equity_snapshots created with 8 cols + 2 indexes; trades.risk_policy_id_at_lock column exists; review_log.risk_policy_id_at_review_completion column exists; seed risk_policy row exists at `policy_id=1`; seed hypothesis_status_history rows exist (one per existing hypothesis_registry row); migration is idempotent (running twice raises clean error per Phase 7 lesson). |
| `tests/data/test_migration_0017_runner_discipline.py` | Migration runner discipline: backup gate fires only on `current_version == 16 AND target >= 17`; backup file pattern `swing-pre-phase9-migration-*.db`; foreign_keys=OFF discipline preserved across the migration; `executescript()` partial-failure rollback via runner wrapper (Phase 7 hotfix `283d4fa` discipline). |
| `tests/data/test_datetime_helpers.py` | now_ms / validate_ms_iso unit tests: format conformance; cross-day boundary; bind-once idempotence; rejects tz-aware datetimes; rejects second-precision inputs. |
| `tests/data/test_risk_policy_repo.py` | risk_policy repo tests: insert_policy + get_active_policy + tiebreaker ORDER BY + list_policy_history. |
| `tests/trades/test_risk_policy_service.py` | risk_policy service tests: supersede_active_policy 6-step sequence + rejects caller-held transaction + RiskPolicy `__post_init__` validator (NaN/inf, CHECK enum, sum-to-1.0 cross-field, drawdown sign convention) + idempotency (no-op when fields match active row — V1 default is NO short-circuit per spec §4.1, but the test verifies actively-WRITTEN no-change rows are still distinct policy_ids); `check_and_reconcile_toml_divergence` 3-test suite per §A.5.1 (identity-no-divergence, divergent-with-frozen-Config-immutability, pre-v17 silent skip); seed_initial_policy idempotence. |
| `tests/data/test_reconciliation_repo.py` | reconciliation repo tests: insert_run + update_run_completed + update_run_failed + insert_discrepancy + list_recent_runs two-read pattern (most-recent-completed vs most-recent-started); list_unresolved_material_for_active_trades query semantics; list_unresolved_material_for_closed_trades query semantics; count_runs_for_artifact_sha256 advisory. |
| `tests/trades/test_reconciliation_service.py` | reconciliation service tests: run_tos_reconciliation against fixture CSVs covering each discrepancy type (close_price_mismatch, stop_mismatch, position_qty_mismatch, cash_movement_mismatch, entry_price_mismatch, unmatched_open_fill, unmatched_close_fill, equity_delta); **failure-path preserves the existing run row + UPDATEs `state='failed'` per spec §3.3.3 (Codex R1 Major #1 + R2 Major #2 fix — NOT a separate row); pre-failure emitted discrepancies + cash_movements + fills are PRESERVED alongside the failed-state UPDATE within the same commit**; within-run dedup verification; resolve_discrepancy lifecycle; MATERIAL_BY_TYPE lookup correctness; rejects caller-held transaction. |
| `tests/data/test_account_equity_snapshots_repo.py` | repo tests: insert + upsert + PK preservation + source-ladder precedence in get_latest_snapshot_on_or_before + with_provenance shape + back-recorded flag. |
| `tests/trades/test_account_equity_snapshots_service.py` | service tests: record_snapshot defaults snapshot_date to last_completed_session; back-recorded flag past 7-day threshold; rejects caller-held transaction. |
| `tests/data/test_hypothesis_status_history_repo.py` | repo tests: insert_history + update_close_open_interval + get_current_status + list_history_for_hypothesis ordering. |
| `tests/trades/test_hypothesis_service.py` | service tests: update_hypothesis_status_with_audit 8-step sequence + noop_identity sentinel + rejects caller-held transaction + history row + registry update in same transaction (rollback on failure); discriminating ImportError check for deleted repo function (T-C.4.4). |
| `tests/journal/test_tos_import_reconciliation_extension.py` | EXTENDS existing tos_import tests: close_price_mismatch detection (matched fill with price delta > tolerance); stop_mismatch detection (Account Order History parsing + WORKING SELL TO CLOSE STP comparison + open-trade-without-broker-stop + orphan broker-stop); position_qty_mismatch detection (Equities section parsing + qty comparison + orphan ticker + zero qty); cash_movement_mismatch detection (amount/kind delta on existing REF#). Includes fixture CSV files under `tests/fixtures/tos/` for each scenario. |
| `tests/journal/test_tos_import_cli_rename.py` | CLI rename + alias deprecation: `swing journal reconcile-tos` works; `swing journal import-tos` still works (V1 alias); alias prints deprecation warning to stderr. |
| `tests/cli/test_config_policy_cli.py` | CLI tests: `swing config policy show` / `set` / `import-from-toml` / `history`. |
| `tests/cli/test_account_snapshot_cli.py` | CLI tests: `swing account snapshot` happy path + `--date` override + default to last_completed_session. |
| `tests/cli/test_discrepancy_cli.py` | CLI tests: `swing journal discrepancy list` / `resolve` / `show`. |
| `tests/web/test_trade_entry_sector_industry_tamper.py` | Route-layer tamper hardening: form sector matches cached → entry proceeds; form sector mismatches → reject + emit sector_tamper discrepancy in ad-hoc reconciliation_run; form industry mismatches → same. Mirrors `tests/web/test_trade_entry_chart_pattern_*` pattern. |
| `tests/trades/test_phase7_entry_risk_policy_stamp.py` | Phase 7 entry_create lock-time stamp: after entry_create against open trade, `trades.risk_policy_id_at_lock` equals `risk_policy.is_active=1.policy_id`; legacy trades pre-migration have NULL → read-path-resolution returns current policy. |
| `tests/trades/test_phase6_review_risk_policy_stamp.py` | Phase 6 complete_review_atomic completion-time stamp: after review completion, `review_log.risk_policy_id_at_review_completion` set; legacy reviews pre-migration have NULL → similar read-path semantics. |
| `tests/integration/test_phase9_end_to_end.py` | E2E happy path: edit policy via CLI → cascade to risk_policy table → new trade entry stamps new policy_id → reconcile TOS CSV with deliberate discrepancies → discrepancies emitted with correct material_to_review → operator resolves via CLI → dashboard query for active-trade alerts returns expected count. |

### Files to MODIFY

| Path | Change |
|---|---|
| `swing/data/db.py` | EXPECTED_SCHEMA_VERSION 16 → 17. No other change (existing migration runner + backup gate handles 0017 automatically). |
| `swing/journal/tos_import.py` | REFACTOR `reconcile_tos` signature to accept `*, run_id: int, emitter: Callable[..., int]` per §A.2 + add stop-order extraction (Account Order History parsing per spec §6.2) + add equities section parsing (per spec §6.3) + add close-price comparison on matched close-fills (per spec §6.1) + add cash_movement amount/kind comparison (per spec §6.4). Preserves `ReconciliationReport` dataclass return shape. |
| `swing/cli.py` | ADD new commands: `swing config policy` group (show / set / import-from-toml / history) + `swing account snapshot` + `swing journal discrepancy` group (list / show / resolve). RENAME `swing journal import-tos` → `swing journal reconcile-tos` + deprecation alias. UPDATE `swing hypothesis update` to route through new service helper (delete inline repo call). |
| `swing/config.py` | **UNCHANGED (Codex R3 Major #1 fix).** Per §A.5.1 revision: `load(config_path)` remains pure with no DB connection parameter. The divergence check is moved to post-schema-validation hooks in CLI + web app startup. Frozen-dataclass mutation removed from plan. |
| `swing/cli.py` (additional) | ADD post-schema-validation hook at every CLI handler that needs a divergence-corrected cfg: after `ensure_schema(conn)` + `load_config()` both succeed, invoke `swing/trades/risk_policy.py:check_and_reconcile_toml_divergence(conn, cfg)` + rebind local `cfg` to the corrected Config + emit stderr advisory line when divergence dict is non-None. `swing db-migrate` CLI handler explicitly SKIPS this hook (the path that brings DB to v17). |
| `swing/web/app.py` (or lifespan/middleware) | ADD post-`ensure_schema` startup hook invoking `check_and_reconcile_toml_divergence` + setting `app.state.cfg` to the corrected Config. |
| `swing/trades/entry.py` | EXTEND `entry_create` to stamp `trades.risk_policy_id_at_lock = (SELECT policy_id FROM risk_policy WHERE is_active = 1)` at pre_trade_locked_at time (within existing transaction; no new transaction). |
| `swing/data/repos/review_log.py` | EXTEND `complete_review_atomic` to set `risk_policy_id_at_review_completion = (SELECT policy_id FROM risk_policy WHERE is_active = 1)` at completion-time (within existing transaction). |
| `swing/web/routes/trades.py` | ADD sector/industry tamper rejection at trade entry POST per §A.4 (mirrors chart_pattern hardening); emit `sector_tamper` discrepancy in ad-hoc reconciliation_run on rejection path. |
| `swing/web/routes/config.py` | EXTEND Phase 5 config-page POST handler: when `cfg.account.risk_equity_floor` field changes, ALSO call `swing/trades/risk_policy.py:supersede_active_policy(...)` per §A.5. Other cfg fields unchanged. |
| `swing/data/repos/hypothesis.py` | DELETE `update_hypothesis_status` (single-write-path discipline; CLI rewired to service per §A.1.1). |

### Files NOT modified (explicit phase isolation)

- `swing/data/repos/daily_management.py` (Phase 8 schema — Phase 9 only LEFT JOINs read-side per spec §5.3).
- `swing/data/repos/fills.py` (Phase 7 schema — Phase 9 only FK-references via reconciliation_discrepancies).
- `swing/data/repos/trades.py` (Phase 7 schema — Phase 9 only ADDs nullable column; existing repo functions unchanged).
- `swing/trades/stop_adjust.py` (Phase 7 service — Phase 9 does NOT call it from inside outer transaction; per CLAUDE.md gotcha + §A.1 transactional discipline).
- `swing/pipeline/runner.py` (Phase 8 pipeline — Phase 9 does NOT add a pipeline step; reconciliation is operator-paced per spec §4.2).
- `swing/web/view_models/dashboard.py` / `open_positions_row.py` (Phase 10 territory — reconciliation badge surface deferred to Phase 10 dispatcher per spec §11.2).
- `swing/web/templates/*` (no new templates V1 — V2 may add discrepancy detail page + risk_policy edit form).

---

## §C — Sub-bundle decomposition + dispatch ordering

Plan decomposes into 5 sub-bundles for executing-plans dispatch. Orchestrator dispatches each as an independent run with its own Codex review chain. **Recommended dispatch ordering:** A → B → C → D → E (each bundle locks schema/service surfaces consumed by the next).

| Sub-bundle | Scope | Tasks | Cross-bundle dependencies |
|---|---|---|---|
| **A — schema + risk_policy foundation** | **COMPLETE migration 0017** (all 5 new tables + 2 ALTER ADDs + risk_policy seed row + hypothesis_status_history seed rows + indexes — landed atomically in T-A.1); risk_policy repo + service + CLI; cfg-mirror cascade; trades.risk_policy_id_at_lock stamp at Phase 7 entry; review_log.risk_policy_id_at_review_completion stamp at Phase 6 review complete. | T-A.0 … T-A.7 | None — bottom of dependency stack. |
| **B — reconciliation depth** | Reconciliation repo + service (consumes tables landed in A); tos_import.py refactor (close-price + stop + equities + cash-movement compares); CLI `journal reconcile-tos` + `journal discrepancy`; `list_unresolved_material_for_active_trades` + `list_unresolved_material_for_closed_trades` queries. **No migration edits.** | T-B.0 … T-B.8 | Depends on A (migration landed; risk_policy + reconciliation_runs + reconciliation_discrepancies tables exist). |
| **C — hypothesis_status_history + account_equity_snapshots** | Repos + services (consume tables + seed rows landed in A); CLI `account snapshot`; rewire `swing hypothesis update` through new service helper. **No migration edits.** | T-C.0 … T-C.5 | Depends on A (migration landed; hypothesis_status_history seeded; account_equity_snapshots table exists). Independent of B. |
| **D — sector/industry tamper hardening** | Route-layer rejection at `/trades/entry` POST; ad-hoc reconciliation_run emission on rejection; mirrors chart_pattern hardening pattern. | T-D.0 … T-D.3 | Depends on A (risk_policy seed) + B (reconciliation_runs + reconciliation_discrepancies tables consumed via service entry). |
| **E — final polish + Phase 10 hand-off prep** | E2E integration test; CLAUDE.md gotcha promotion; docs/cycle-checklist.md update; orchestrator-context.md lesson capture; Phase 10 hand-off note in plan return report. | T-E.0 … T-E.2 | Depends on A + B + C + D (final polish across all surfaces). |

**Migration atomicity (Codex R1 Critical #1 fix):** the SINGLE migration file `0017_phase9_risk_policy_and_reconciliation.sql` is landed **complete-and-atomic** in T-A.1 (sub-bundle A's first schema task). All five new tables + 2 ALTER ADDs + risk_policy seed + hypothesis_status_history seed rows + indexes are created in this one file. The `UPDATE schema_version SET version = 17` happens at the END of that same file — **`EXPECTED_SCHEMA_VERSION` is bumped to 17 ONLY AFTER all schema work for the phase is in the migration file**. Sub-bundles B / C / D / E ship code that consumes the schema; they DO NOT modify the migration. This avoids the "schema_version bumped to 17 mid-phase while later sub-bundles still need to add tables" failure mode: if A shipped to production with only risk_policy created + version 17 stamped, then later B/C migration edits to `0017_*` would NEVER apply on the production DB (runner skips migrations with `version <= current`).

**Why a "schema bundle 0" wasn't carved out separately:** the alternative was a dedicated "Bundle 0 — migration only" with everything else (A through E) gated on its merge. Rejected because: (1) the migration depends on the risk_policy seed values from cfg, which is service-layer logic in T-A.4 (`seed_initial_policy` lives in `swing/trades/risk_policy.py`); the seed row in the migration is a literal INSERT with hardcoded cfg defaults, and the helper is for post-Phase-9 ratification paths; (2) operator-witnessed verification of the migration is best paired with the smallest-possible read surface (sub-bundle A's `swing config policy show`) — separate gates would add ceremony without catching anything. Discriminating test T-A.1.6 verifies the migration creates all 5 tables + 2 columns + all seed rows in a single executescript pass.

**Operator-witnessed gate sequencing:** sub-bundle A ships with its own gate (5 surfaces); B with 6 surfaces (includes A's surfaces + reconciliation-specific); C with 4 surfaces (account snapshot CLI + hypothesis status audit + read-path); D with 3 surfaces (sector/industry rejection + audit-row persistence); E is one combined E2E surface. Brief drafting for each sub-bundle codifies the surfaces.

---

## §D — Sub-bundle A: risk_policy foundation

**Goal:** Schema (risk_policy table + 2 column ALTERs) + repo + service + CLI + Phase 7/6 stamp wires + cfg-mirror cascade. Bottom of dependency stack — must ship first.

**Sub-bundle A surfaces 5 operator-witnessed gates** (codified in executing-plans dispatch brief):
- S1: Pre-migration baseline; production DB at v16; baseline test count green.
- S2: Post-migration; `swing config policy show` prints seed policy.
- S3: `swing config policy set --field max_account_risk_per_trade_pct --value 0.75 --notes "operator test"` creates new policy_id 2; `policy_id=1.is_active=0`.
- S4: New trade entry via web `/trades/entry` POST stamps `risk_policy_id_at_lock=2` on the new trade.
- S5: Review completion via web `/reviews/{id}/complete` POST stamps `risk_policy_id_at_review_completion=2` on the row.

### Task A.0: Datetime helpers (`swing/data/datetime_helpers.py`)

**Files:**
- Create: `swing/data/datetime_helpers.py`
- Test: `tests/data/test_datetime_helpers.py`

**Depends on:** none.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_datetime_helpers.py
import re
from datetime import datetime, timezone

import pytest

from swing.data.datetime_helpers import now_ms, validate_ms_iso

_MS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")


def test_now_ms_format_conformance():
    s = now_ms()
    assert _MS_RE.match(s) is not None, f"now_ms() returned non-conforming {s!r}"


def test_now_ms_bind_once_idempotence(monkeypatch):
    """Two calls to now_ms() backed by the SAME utcnow() must produce the SAME string."""
    fixed = datetime(2026, 5, 11, 14, 30, 45, 123456)
    monkeypatch.setattr("swing.data.datetime_helpers.datetime", _FixedDatetime(fixed))
    a = now_ms()
    b = now_ms()
    assert a == b == "2026-05-11T14:30:45.123"


class _FixedDatetime:
    def __init__(self, fixed):
        self._fixed = fixed
    def utcnow(self):
        return self._fixed


def test_validate_ms_iso_accepts_valid():
    s = "2026-05-11T14:30:45.123"
    assert validate_ms_iso(s) == s


def test_validate_ms_iso_rejects_second_precision():
    with pytest.raises(ValueError, match="millisecond precision"):
        validate_ms_iso("2026-05-11T14:30:45")


def test_validate_ms_iso_rejects_microsecond_precision():
    with pytest.raises(ValueError, match="millisecond precision"):
        validate_ms_iso("2026-05-11T14:30:45.123456")


def test_validate_ms_iso_rejects_tz_aware():
    with pytest.raises(ValueError, match="naive"):
        validate_ms_iso("2026-05-11T14:30:45.123+00:00")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/data/test_datetime_helpers.py -v`
Expected: FAIL with `ImportError: cannot import name 'now_ms' from 'swing.data.datetime_helpers'`.

- [ ] **Step 3: Write minimal implementation**

```python
# swing/data/datetime_helpers.py
"""Naive-UTC millisecond-precision datetime helpers for Phase 9 audit tables.

Per Phase 9 spec §9.3 + R2 Major #4 fix: TEXT datetime columns store
naive-UTC ISO datetimes with millisecond precision (YYYY-MM-DDTHH:MM:SS.SSS).
Lexicographic ordering is preserved when inputs are naive + uniform precision.
"""

from __future__ import annotations

import re
from datetime import datetime

_MS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")


def now_ms() -> str:
    """Return naive-UTC millisecond-precision ISO datetime string.

    Single bind to ``datetime.utcnow()`` ensures the seconds and millisecond
    fragment come from the same instant (Phase 9 spec §3.1.3 R4 Minor #1).
    """
    n = datetime.utcnow()
    return n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}"


def validate_ms_iso(s: str) -> str:
    """Validate that ``s`` matches the naive-UTC millisecond-precision form.

    Raises:
        ValueError: when input is second-precision, microsecond-precision, or
        timezone-aware. Phase 9 spec §9.3 binding contract.
    """
    if not isinstance(s, str):
        raise ValueError(f"expected str; got {type(s).__name__}")
    if "+" in s or s.endswith("Z"):
        raise ValueError(f"datetime must be naive (no tz suffix); got {s!r}")
    if not _MS_PATTERN.match(s):
        raise ValueError(
            f"datetime must be millisecond precision (YYYY-MM-DDTHH:MM:SS.SSS); got {s!r}"
        )
    return s
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/data/test_datetime_helpers.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add swing/data/datetime_helpers.py tests/data/test_datetime_helpers.py
git commit -m "feat(data): Task A.0 — naive-UTC millisecond-precision datetime helpers"
```

### Task A.1: Migration 0017 schema landing (risk_policy + ALTER ADDs + seed)

**Files:**
- Create: `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql`
- Modify: `swing/data/db.py` (EXPECTED_SCHEMA_VERSION 16 → 17)
- Test: `tests/data/test_migration_0017.py` (FULL scope — all 5 tables + 2 ALTERs + risk_policy seed + hypothesis_status_history seed rows per Codex R1 Critical #1 fix)
- Test: `tests/data/test_migration_0017_runner_discipline.py`

**Depends on:** T-A.0.

- [ ] **Step 1: Write the failing test for the migration**

```python
# tests/data/test_migration_0017.py
"""Test 0017 migration round-trip — FULL scope per Codex R1 Critical #1 fix.

Covers ALL Phase 9 schema landed atomically by T-A.1: risk_policy + indexes +
seed; reconciliation_runs + indexes; reconciliation_discrepancies + indexes;
hypothesis_status_history + indexes + per-hypothesis seed rows;
account_equity_snapshots + indexes; trades.risk_policy_id_at_lock column;
review_log.risk_policy_id_at_review_completion column; schema_version = 17.

The test scaffold below shows the risk_policy + ALTER coverage; the full file
adds analogous tests for reconciliation_runs (per spec §3.2), reconciliation_
discrepancies (per spec §3.3), hypothesis_status_history + seed rows (per spec
§3.4), account_equity_snapshots (per spec §3.5). Implementer expands the
scaffold to FULL coverage in T-A.1; no later task adds DDL or test cases."""

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, init_db


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase9.db"
    return init_db(db_path)


def test_schema_version_is_17(conn: sqlite3.Connection):
    assert EXPECTED_SCHEMA_VERSION == 17
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row[0] == 17


def test_risk_policy_table_exists_with_34_columns(conn: sqlite3.Connection):
    cur = conn.execute("PRAGMA table_info(risk_policy)")
    cols = [r[1] for r in cur.fetchall()]
    # Per spec §3.1 column list — 34 columns total. Spec text's "28 columns"
    # subtotal is a brainstorm-phase miscount per Codex R1 Major #2 fix; the
    # column LIST in spec §3.1 is the binding artifact (34 distinct fields).
    assert len(cols) == 34
    expected = {
        "policy_id", "effective_from", "effective_to", "is_active",
        "superseded_by_policy_id", "created_at", "policy_notes",
        "max_account_risk_per_trade_pct", "max_concurrent_positions",
        "max_portfolio_heat_pct", "max_sector_concentration_positions",
        "consecutive_losses_pause_threshold", "consecutive_losses_pause_action",
        "consecutive_losses_streak_reset",
        "drawdown_circuit_breaker_enabled", "drawdown_pause_threshold_R",
        "drawdown_pause_action", "drawdown_size_reduction_pct",
        "drawdown_recovery_threshold_R",
        "capital_floor_constant_dollars",
        "scratch_epsilon_R", "review_lag_threshold_days",
        "low_sample_size_threshold_class_a_n",
        "low_sample_size_threshold_class_b_n",
        "low_sample_size_threshold_class_c_n",
        "low_sample_size_threshold_class_d_n",
        "global_confidence_floor_n", "bootstrap_resample_count",
        "process_grade_weight_entry", "process_grade_weight_management",
        "process_grade_weight_exit",
        "mfe_mae_default_precision_level",
        "trail_MA_period_days", "trail_MA_post_2R_period_days",
    }
    assert set(cols) == expected, (
        f"column drift; missing {expected - set(cols)}; extra {set(cols) - expected}"
    )


def test_risk_policy_seed_row_exists(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT policy_id, is_active, capital_floor_constant_dollars, "
        "scratch_epsilon_R, max_concurrent_positions FROM risk_policy "
        "WHERE policy_id = 1"
    ).fetchone()
    assert row is not None
    assert row[1] == 1  # is_active = 1
    assert row[2] == 7500.0  # capital floor per spec §3.1.3 seed
    assert row[3] == 0.10  # scratch_epsilon_R seed
    assert row[4] >= 1  # from cfg.position_limits.hard_cap_open


def test_risk_policy_active_partial_unique_index(conn: sqlite3.Connection):
    """Forbids two non-superseded rows simultaneously per spec §3.1.2."""
    # Already one row is_active=1 (seed). Inserting a second should fail.
    # SQLite's actual error message is "UNIQUE constraint failed: risk_policy.is_active"
    # (NOT the index name; Codex R3 Minor #1 fix).
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute(
            "INSERT INTO risk_policy (effective_from, is_active, created_at, "
            "max_account_risk_per_trade_pct, max_concurrent_positions, "
            "max_portfolio_heat_pct, max_sector_concentration_positions, "
            "consecutive_losses_pause_threshold, consecutive_losses_pause_action, "
            "consecutive_losses_streak_reset, drawdown_circuit_breaker_enabled, "
            "capital_floor_constant_dollars, scratch_epsilon_R, "
            "review_lag_threshold_days, low_sample_size_threshold_class_a_n, "
            "low_sample_size_threshold_class_b_n, low_sample_size_threshold_class_c_n, "
            "low_sample_size_threshold_class_d_n, global_confidence_floor_n, "
            "bootstrap_resample_count, process_grade_weight_entry, "
            "process_grade_weight_management, process_grade_weight_exit, "
            "mfe_mae_default_precision_level, trail_MA_period_days) "
            "VALUES ('2026-05-11T00:00:00.000', 1, '2026-05-11T00:00:00.000', "
            "0.50, 6, 3.0, 3, 3, 'review_required', 'review_completed', 0, "
            "7500.0, 0.10, 7, 3, 5, 5, 10, 20, 1000, 0.40, 0.35, 0.25, "
            "'daily_approximate', 21)"
        )


def test_trades_risk_policy_id_at_lock_column_exists(conn: sqlite3.Connection):
    cur = conn.execute("PRAGMA table_info(trades)")
    cols = {r[1] for r in cur.fetchall()}
    assert "risk_policy_id_at_lock" in cols


def test_review_log_risk_policy_id_at_review_completion_column_exists(conn: sqlite3.Connection):
    cur = conn.execute("PRAGMA table_info(review_log)")
    cols = {r[1] for r in cur.fetchall()}
    assert "risk_policy_id_at_review_completion" in cols


def test_legacy_trades_have_null_risk_policy_id_at_lock(conn: sqlite3.Connection):
    """Trades pre-migration carry NULL stamp; read path resolves to current policy."""
    # Insert a legacy-style trade (post-Phase-7 schema, no Phase 9 column set)
    # Verifies the column is nullable.
    conn.execute(
        "INSERT INTO trades (ticker, action, state, entry_price, initial_stop, "
        "planned_risk_budget_dollars, current_size, current_avg_cost, current_stop, "
        "entry_date) "
        "VALUES ('TEST', 'BUY', 'entered', 100.0, 95.0, 500.0, 100, 100.0, 95.0, "
        "'2026-05-11')"
    )
    row = conn.execute(
        "SELECT risk_policy_id_at_lock FROM trades WHERE ticker = 'TEST'"
    ).fetchone()
    assert row[0] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/data/test_migration_0017.py -v`
Expected: FAIL (migration file doesn't exist; EXPECTED_SCHEMA_VERSION is 16).

- [ ] **Step 3: Implement migration file (COMPLETE-AND-ATOMIC per Codex R1 Critical #1 fix)**

Create `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql` per spec §3 schema sketches — **all 5 new tables + 2 ALTER ADDs + all seed rows + all 13 indexes** (the spec §A.0.1-reconciled 34-column risk_policy + 17-column reconciliation_runs + 18-column reconciliation_discrepancies + 7-column hypothesis_status_history + 8-column account_equity_snapshots). Use SQL `strftime('%Y-%m-%dT%H:%M:%f', 'now')` for all seed timestamps per §A.11. (FULL DDL drafting is executing-plans territory; the implementer derives from spec §3.1–§3.5 column tables verbatim.)

Key migration content (illustrative SKELETON for risk_policy only — implementer expands to all 5 tables + ALTERs + seeds per spec §3.1–§3.5 column tables):

```sql
-- 0017_phase9_risk_policy_and_reconciliation.sql
-- Schema bump v16 -> v17 LANDED ATOMICALLY (per Codex R1 Critical #1 fix).
-- Single file creates: risk_policy + reconciliation_runs + reconciliation_discrepancies +
-- hypothesis_status_history + account_equity_snapshots, plus 2 ALTER ADD columns on
-- trades + review_log, plus all seed rows (risk_policy.policy_id=1 + one
-- hypothesis_status_history row per existing hypothesis_registry row).
-- Per spec §9.2 mechanic: CREATE TABLE / CREATE INDEX / ALTER ADD COLUMN — no rebuilds.

-- Phase 7 hotfix 283d4fa discipline: foreign_keys=OFF wraps executescript at runner.

CREATE TABLE risk_policy (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)) DEFAULT 1,
    superseded_by_policy_id INTEGER REFERENCES risk_policy(policy_id),
    created_at TEXT NOT NULL,
    policy_notes TEXT,
    -- Trading-risk fields ...
    max_account_risk_per_trade_pct REAL NOT NULL CHECK (max_account_risk_per_trade_pct > 0),
    max_concurrent_positions INTEGER NOT NULL CHECK (max_concurrent_positions > 0),
    max_portfolio_heat_pct REAL NOT NULL CHECK (max_portfolio_heat_pct > 0),
    max_sector_concentration_positions INTEGER NOT NULL CHECK (max_sector_concentration_positions > 0),
    consecutive_losses_pause_threshold INTEGER NOT NULL CHECK (consecutive_losses_pause_threshold > 0),
    consecutive_losses_pause_action TEXT NOT NULL CHECK (consecutive_losses_pause_action IN ('review_required')),
    consecutive_losses_streak_reset TEXT NOT NULL CHECK (consecutive_losses_streak_reset IN ('review_completed')),
    -- Drawdown circuit breaker (default opt-in disabled per spec §1.4) ...
    drawdown_circuit_breaker_enabled INTEGER NOT NULL CHECK (drawdown_circuit_breaker_enabled IN (0, 1)) DEFAULT 0,
    drawdown_pause_threshold_R REAL CHECK (drawdown_pause_threshold_R IS NULL OR drawdown_pause_threshold_R < 0),
    drawdown_pause_action TEXT CHECK (drawdown_pause_action IS NULL OR drawdown_pause_action IN ('halt_new_entries', 'reduce_size')),
    drawdown_size_reduction_pct REAL CHECK (drawdown_size_reduction_pct IS NULL OR (drawdown_size_reduction_pct > 0 AND drawdown_size_reduction_pct <= 1)),
    drawdown_recovery_threshold_R REAL CHECK (drawdown_recovery_threshold_R IS NULL OR drawdown_recovery_threshold_R < 0),
    -- Capital + sizing ...
    capital_floor_constant_dollars REAL NOT NULL CHECK (capital_floor_constant_dollars > 0),
    -- Statistics-methodology knobs ...
    scratch_epsilon_R REAL NOT NULL CHECK (scratch_epsilon_R > 0),
    review_lag_threshold_days INTEGER NOT NULL CHECK (review_lag_threshold_days > 0),
    low_sample_size_threshold_class_a_n INTEGER NOT NULL CHECK (low_sample_size_threshold_class_a_n > 0),
    low_sample_size_threshold_class_b_n INTEGER NOT NULL CHECK (low_sample_size_threshold_class_b_n > 0),
    low_sample_size_threshold_class_c_n INTEGER NOT NULL CHECK (low_sample_size_threshold_class_c_n > 0),
    low_sample_size_threshold_class_d_n INTEGER NOT NULL CHECK (low_sample_size_threshold_class_d_n > 0),
    global_confidence_floor_n INTEGER NOT NULL CHECK (global_confidence_floor_n > 0),
    bootstrap_resample_count INTEGER NOT NULL CHECK (bootstrap_resample_count > 0),
    process_grade_weight_entry REAL NOT NULL CHECK (process_grade_weight_entry > 0 AND process_grade_weight_entry < 1),
    process_grade_weight_management REAL NOT NULL CHECK (process_grade_weight_management > 0 AND process_grade_weight_management < 1),
    process_grade_weight_exit REAL NOT NULL CHECK (process_grade_weight_exit > 0 AND process_grade_weight_exit < 1),
    -- MFE/MAE precision ...
    mfe_mae_default_precision_level TEXT NOT NULL CHECK (mfe_mae_default_precision_level IN ('daily_approximate', 'intraday_estimated', 'intraday_exact')),
    trail_MA_period_days INTEGER NOT NULL CHECK (trail_MA_period_days > 0),
    trail_MA_post_2R_period_days INTEGER CHECK (trail_MA_post_2R_period_days IS NULL OR trail_MA_post_2R_period_days > 0),
    -- Sum-to-1.0 defense-in-depth (per spec §3.1 R1 Minor #4) ...
    CHECK (ABS((process_grade_weight_entry + process_grade_weight_management + process_grade_weight_exit) - 1.0) < 1e-9)
);

CREATE UNIQUE INDEX ux_risk_policy_active
    ON risk_policy (is_active)
    WHERE is_active = 1;

CREATE INDEX ix_risk_policy_effective_from
    ON risk_policy (effective_from);

-- Seed policy_id = 1 per spec §3.1.3 seed map; values from cfg defaults.
INSERT INTO risk_policy (
    effective_from, is_active, created_at, policy_notes,
    max_account_risk_per_trade_pct, max_concurrent_positions, max_portfolio_heat_pct,
    max_sector_concentration_positions, consecutive_losses_pause_threshold,
    consecutive_losses_pause_action, consecutive_losses_streak_reset,
    drawdown_circuit_breaker_enabled,
    capital_floor_constant_dollars,
    scratch_epsilon_R, review_lag_threshold_days,
    low_sample_size_threshold_class_a_n, low_sample_size_threshold_class_b_n,
    low_sample_size_threshold_class_c_n, low_sample_size_threshold_class_d_n,
    global_confidence_floor_n, bootstrap_resample_count,
    process_grade_weight_entry, process_grade_weight_management, process_grade_weight_exit,
    mfe_mae_default_precision_level, trail_MA_period_days
) VALUES (
    strftime('%Y-%m-%dT%H:%M:%f', 'now'), 1, strftime('%Y-%m-%dT%H:%M:%f', 'now'),
    'Phase 9 seed from swing.config.toml defaults at migration apply time',
    0.50, 6, 3.0, 3, 3, 'review_required', 'review_completed', 0,
    7500.0, 0.10, 7, 3, 5, 5, 10, 20, 1000,
    0.40, 0.35, 0.25, 'daily_approximate', 21
);

-- IMPLEMENTER EXPANDS: append CREATE TABLE statements for the remaining
-- 4 tables (reconciliation_runs / reconciliation_discrepancies /
-- hypothesis_status_history / account_equity_snapshots) per spec §3.2–§3.5
-- column tables, plus their indexes (3+4+2+2 = 11 additional indexes).

-- ALTER TABLE ADDs (no rebuild)
ALTER TABLE trades ADD COLUMN risk_policy_id_at_lock INTEGER REFERENCES risk_policy(policy_id);
ALTER TABLE review_log ADD COLUMN risk_policy_id_at_review_completion INTEGER REFERENCES risk_policy(policy_id);

-- IMPLEMENTER EXPANDS: append seed INSERT for hypothesis_status_history per
-- spec §3.4.1 R3 Major #2 (one row per hypothesis_registry row; effective_from
-- = strftime('%Y-%m-%dT00:00:00.000', hypothesis_registry.created_at);
-- effective_to = NULL; status = current registry status; change_reason = NULL;
-- recorded_at = strftime('%Y-%m-%dT%H:%M:%f', 'now')).

UPDATE schema_version SET version = 17;
```

**Migration is COMPLETE-AND-ATOMIC at this task (Codex R1 Critical #1 fix).** T-A.1 lands ALL Phase 9 schema in this single file: risk_policy table + 2 indexes + seed; reconciliation_runs table + 3 indexes (per spec §3.2); reconciliation_discrepancies table + 4 indexes (per spec §3.3); hypothesis_status_history table + 2 indexes + per-hypothesis seed rows (per spec §3.4); account_equity_snapshots table + 2 indexes (per spec §3.5); 2 ALTER ADDs on trades + review_log. `UPDATE schema_version SET version = 17` is the LAST statement. Sub-bundles B/C/D/E DO NOT touch this file — they ship code that consumes the already-landed schema. Discriminating test T-A.1.6 (added below this step list) verifies all 5 tables + 2 columns + all seed rows + all 13 indexes (2+3+4+2+2) are present in a single post-T-A.1 DB.

**Test scope at T-A.1:** the test file `tests/data/test_migration_0017.py` lands with FULL coverage in T-A.1. The scaffold above shows the risk_policy + ALTERs + legacy-trade tests (7 tests). Implementer adds analogous tests for reconciliation_runs (4 tests verifying 17-col table + 3 indexes + FK CASCADE on discrepancies + CHECK enums) + reconciliation_discrepancies (verified alongside) + hypothesis_status_history (4 tests verifying 7-col table + 2 indexes + partial-unique-current-row index + per-hypothesis seed rows present + effective_to IS NULL on seeds) + account_equity_snapshots (3 tests verifying 8-col table + 2 indexes + unique-snapshot_date-source). Total: ~18 tests in T-A.1. Sub-bundles B/C/D/E DO NOT add migration tests; their consumer-side verification tasks (T-B.0 / T-C.0 / T-C.1) add 1-3 read-only schema-verification tests each against the v17 schema landed here.

- [ ] **Step 4: Bump EXPECTED_SCHEMA_VERSION**

Modify `swing/data/db.py:15`: `EXPECTED_SCHEMA_VERSION = 16` → `EXPECTED_SCHEMA_VERSION = 17`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/data/test_migration_0017.py -v`
Expected: PASS (all ~18 tests covering the COMPLETE Phase 9 schema landed atomically in this task per Codex R1 Critical #1 fix; T-B.0 / T-C.0 / T-C.1 add only consumer-side read-only schema verification tests in separate test files).

- [ ] **Step 6: Commit**

```bash
git add swing/data/db.py swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql tests/data/test_migration_0017.py
git commit -m "feat(data): Task A.1 — migration 0017 risk_policy table + ALTER ADD columns + seed"
```

### Task A.2: Migration runner discipline regression tests

**Files:**
- Test: `tests/data/test_migration_0017_runner_discipline.py`

**Depends on:** T-A.1.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_migration_0017_runner_discipline.py
"""Phase 9 migration runner discipline — backup gate + foreign_keys=OFF +
executescript() partial-failure rollback. Inherits Phase 7 hotfix 283d4fa
+ Phase 8 lesson 2026-05-07."""

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import EXPECTED_SCHEMA_VERSION, init_db, run_migrations


def _setup_v16_db(tmp_path: Path) -> Path:
    """Initialize a DB at exactly schema_version=16 (Phase 8 baseline)."""
    db_path = tmp_path / "phase8_baseline.db"
    conn = sqlite3.connect(db_path)
    # Apply migrations 0001..0016 via the runner targeting v16.
    run_migrations(conn, target_version=16)
    conn.close()
    return db_path


def test_backup_gate_fires_only_at_16_to_17(tmp_path: Path):
    """Backup file created when current=16 AND target>=17."""
    db_path = _setup_v16_db(tmp_path)
    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=17)
    conn.close()

    backups = list(tmp_path.glob("swing-pre-phase9-migration-*.db"))
    assert len(backups) == 1


def test_backup_gate_does_not_fire_on_fresh_db(tmp_path: Path):
    """Fresh DB walks past v16 -> v17 without backup gate (no v16 DB to back up)."""
    db_path = tmp_path / "fresh.db"
    conn = init_db(db_path)
    conn.close()

    backups = list(tmp_path.glob("swing-pre-phase9-migration-*.db"))
    assert len(backups) == 0


def test_foreign_keys_off_during_migration(tmp_path: Path):
    """Per Phase 7 hotfix 283d4fa — runner disables FK before executescript,
    re-enables after. Verified by snooping the PRAGMA during a migration
    that would fail if FKs were enforced mid-script."""
    db_path = _setup_v16_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn, target_version=17)
    # Post-migration: foreign_keys should be re-enabled to caller's prior state.
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1  # ON
    conn.close()


def test_executescript_partial_failure_rollback(tmp_path: Path, monkeypatch):
    """Per Phase 7 Sub-A R1 M3 lesson — runner wraps executescript in
    BEGIN/COMMIT with try/except rollback. A deliberately malformed migration
    must roll back cleanly + leave conn.in_transaction == False."""
    db_path = _setup_v16_db(tmp_path)
    conn = sqlite3.connect(db_path)

    # Inject a malformed migration via monkeypatch on the loader
    bad_sql = """
        CREATE TABLE _probe_phase9 (id INTEGER PRIMARY KEY);
        INSERT INTO _probe_phase9 (id) VALUES (1);
        SYNTAX ERROR HERE;
    """
    # ... (test fixture monkeypatches the 0017 SQL loader to return bad_sql)

    with pytest.raises(sqlite3.OperationalError):
        run_migrations(conn, target_version=17)

    assert conn.in_transaction is False  # runner's wrapper cleaned up
    # _probe_phase9 must be absent — runner-level rollback fired.
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_probe_phase9'"
    )
    assert cur.fetchone() is None
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail (BEFORE the monkeypatch fixture for the rollback test is wired)**

Run: `pytest tests/data/test_migration_0017_runner_discipline.py -v`
Expected: First 3 tests should pass (runner discipline already shipped). Fourth test fails on monkeypatch wiring — implementer wires per Phase 8 plan-template precedent.

- [ ] **Step 3: Wire monkeypatch fixture**

Per Phase 8 plan §A.0 lesson — discriminating test uses runner's actual rollback path via injected malformed SQL.

- [ ] **Step 4: Run tests to verify all pass**

Run: `pytest tests/data/test_migration_0017_runner_discipline.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/data/test_migration_0017_runner_discipline.py
git commit -m "test(data): Task A.2 — migration 0017 runner discipline regression tests"
```

### Task A.3: risk_policy dataclass + repo

**Files:**
- Modify: `swing/data/models.py` (add `RiskPolicy` dataclass)
- Create: `swing/data/repos/risk_policy.py`
- Test: `tests/data/test_risk_policy_repo.py`

**Depends on:** T-A.1.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_risk_policy_repo.py
"""risk_policy repo CRUD + dataclass validator tests."""

import sqlite3
import math

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.models import RiskPolicy
from swing.data.repos.risk_policy import (
    NoActivePolicyError,
    get_active_policy,
    get_policy_by_id,
    insert_policy,
    list_policy_history,
    update_policy_active_flag,
)


def _full_policy_kwargs(**overrides):
    base = dict(
        effective_from=now_ms(), effective_to=None, is_active=1,
        superseded_by_policy_id=None, created_at=now_ms(), policy_notes=None,
        max_account_risk_per_trade_pct=0.50, max_concurrent_positions=6,
        max_portfolio_heat_pct=3.0, max_sector_concentration_positions=3,
        consecutive_losses_pause_threshold=3,
        consecutive_losses_pause_action="review_required",
        consecutive_losses_streak_reset="review_completed",
        drawdown_circuit_breaker_enabled=0,
        drawdown_pause_threshold_R=None, drawdown_pause_action=None,
        drawdown_size_reduction_pct=None, drawdown_recovery_threshold_R=None,
        capital_floor_constant_dollars=7500.0,
        scratch_epsilon_R=0.10, review_lag_threshold_days=7,
        low_sample_size_threshold_class_a_n=3,
        low_sample_size_threshold_class_b_n=5,
        low_sample_size_threshold_class_c_n=5,
        low_sample_size_threshold_class_d_n=10,
        global_confidence_floor_n=20, bootstrap_resample_count=1000,
        process_grade_weight_entry=0.40, process_grade_weight_management=0.35,
        process_grade_weight_exit=0.25,
        mfe_mae_default_precision_level="daily_approximate",
        trail_MA_period_days=21, trail_MA_post_2R_period_days=None,
    )
    base.update(overrides)
    return base


def test_get_active_policy_returns_seed(conn):
    """Seed row inserted by migration is active."""
    p = get_active_policy(conn)
    assert p.policy_id == 1
    assert p.is_active == 1
    assert p.capital_floor_constant_dollars == 7500.0
    assert p.scratch_epsilon_R == 0.10


def test_get_active_policy_raises_when_no_active_row(conn):
    """When no row matches is_active=1, raises NoActivePolicyError."""
    conn.execute("UPDATE risk_policy SET is_active = 0")
    with pytest.raises(NoActivePolicyError):
        get_active_policy(conn)


def test_get_policy_by_id_returns_specific_row(conn):
    p = get_policy_by_id(conn, policy_id=1)
    assert p is not None
    assert p.policy_id == 1


def test_get_policy_by_id_returns_none_for_unknown(conn):
    assert get_policy_by_id(conn, policy_id=99999) is None


def test_insert_policy_returns_new_id(conn):
    """Pure INSERT inside caller's transaction; returns policy_id."""
    conn.execute("BEGIN IMMEDIATE")
    # Predecessor must be flagged is_active=0 first (per ux_risk_policy_active partial index).
    conn.execute("UPDATE risk_policy SET is_active = 0 WHERE policy_id = 1")
    new_id = insert_policy(conn, **_full_policy_kwargs(max_account_risk_per_trade_pct=0.75))
    conn.execute("COMMIT")
    assert new_id == 2
    p = get_policy_by_id(conn, policy_id=2)
    assert p.max_account_risk_per_trade_pct == 0.75


def test_list_policy_history_tiebreaker_order(conn):
    """Per spec §3.1 tiebreaker: ORDER BY effective_from DESC, policy_id DESC."""
    # Insert two more policies with same effective_from
    same_ts = now_ms()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("UPDATE risk_policy SET is_active = 0, effective_to = ?, "
                 "superseded_by_policy_id = ? WHERE policy_id = 1",
                 (same_ts, 2))
    insert_policy(conn, **_full_policy_kwargs(effective_from=same_ts, is_active=0,
                                              effective_to=same_ts))
    insert_policy(conn, **_full_policy_kwargs(effective_from=same_ts, is_active=1))
    conn.execute("COMMIT")
    rows = list_policy_history(conn)
    # Most recent should be policy_id=3 (last inserted at same_ts)
    assert rows[0].policy_id == 3


def test_riskpolicy_post_init_rejects_nan(conn):
    """__post_init__ validator rejects NaN per Bundle 2/3 pattern."""
    with pytest.raises(ValueError, match="NaN|inf"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          max_account_risk_per_trade_pct=float("nan")))


def test_riskpolicy_post_init_rejects_inf(conn):
    with pytest.raises(ValueError, match="NaN|inf"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          capital_floor_constant_dollars=float("inf")))


def test_riskpolicy_post_init_rejects_negative_capital(conn):
    """capital_floor > 0 CHECK at dataclass level."""
    with pytest.raises(ValueError, match="capital_floor"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          capital_floor_constant_dollars=-100.0))


def test_riskpolicy_post_init_rejects_drawdown_positive_threshold(conn):
    """drawdown_pause_threshold_R must be < 0 per Phase 10 sign convention."""
    with pytest.raises(ValueError, match="drawdown"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          drawdown_circuit_breaker_enabled=1,
                                          drawdown_pause_threshold_R=2.0,
                                          drawdown_pause_action="halt_new_entries",
                                          drawdown_recovery_threshold_R=-0.5))


def test_riskpolicy_post_init_rejects_invalid_enum(conn):
    with pytest.raises(ValueError, match="mfe_mae_default_precision_level"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          mfe_mae_default_precision_level="invalid"))


def test_riskpolicy_post_init_rejects_grade_weights_not_summing_to_1(conn):
    with pytest.raises(ValueError, match="process_grade_weight"):
        RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          process_grade_weight_entry=0.50,
                                          process_grade_weight_management=0.35,
                                          process_grade_weight_exit=0.25))


def test_riskpolicy_post_init_accepts_valid_weights(conn):
    p = RiskPolicy(**_full_policy_kwargs(policy_id=99,
                                          process_grade_weight_entry=0.40,
                                          process_grade_weight_management=0.35,
                                          process_grade_weight_exit=0.25))
    assert p.policy_id == 99


@pytest.fixture
def conn(tmp_path):
    from swing.data.db import init_db
    return init_db(tmp_path / "test.db")
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL on `ImportError` / `RiskPolicy` not defined.

- [ ] **Step 3: Implement dataclass + repo**

Add `RiskPolicy` dataclass in `swing/data/models.py` with `__post_init__` validator (NaN/inf rejection per Bundle 2/3 pattern; CHECK enum validation; sum-to-1.0 for process_grade_weight_*; drawdown sign convention per spec §3.1 R1 Major #7).

Implement `swing/data/repos/risk_policy.py` per file map. Repo functions: do NOT call `conn.commit()` (per Finviz I1 lesson — caller-controlled transaction scope).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/data/test_risk_policy_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/models.py swing/data/repos/risk_policy.py tests/data/test_risk_policy_repo.py
git commit -m "feat(data): Task A.3 — RiskPolicy dataclass + repo with __post_init__ validator"
```

### Task A.4: risk_policy service — supersede_active_policy + read_active_policy

**Files:**
- Create: `swing/trades/risk_policy.py`
- Test: `tests/trades/test_risk_policy_service.py`

**Depends on:** T-A.3.

- [ ] **Step 1: Write the failing tests**

```python
# tests/trades/test_risk_policy_service.py
"""risk_policy service tests — 6-step supersession sequence + caller-tx rejection +
__post_init__ integration."""

import pytest

from swing.trades.risk_policy import (
    CallerHeldTransactionError,
    supersede_active_policy,
    read_active_policy,
)
from swing.data.repos.risk_policy import get_active_policy, get_policy_by_id


def test_supersede_creates_new_active_policy(conn):
    """6-step sequence: predecessor (1) flagged is_active=0 + effective_to set;
    successor (2) inserted with is_active=1; predecessor.superseded_by_policy_id=2."""
    new_id = supersede_active_policy(
        conn,
        field_updates={"max_account_risk_per_trade_pct": 0.75},
        notes="operator test",
    )
    assert new_id == 2

    predecessor = get_policy_by_id(conn, policy_id=1)
    assert predecessor.is_active == 0
    assert predecessor.effective_to is not None
    assert predecessor.superseded_by_policy_id == 2

    successor = get_policy_by_id(conn, policy_id=2)
    assert successor.is_active == 1
    assert successor.effective_to is None
    assert successor.max_account_risk_per_trade_pct == 0.75
    assert successor.capital_floor_constant_dollars == 7500.0  # copied from predecessor


def test_supersede_rejects_caller_held_transaction(conn):
    """Per dispatch brief §0.3 #5 + Phase 8 R3->R4 lesson."""
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(CallerHeldTransactionError):
        supersede_active_policy(conn, field_updates={"max_account_risk_per_trade_pct": 0.75})
    conn.rollback()


def test_supersede_invalid_field_raises(conn):
    with pytest.raises(ValueError, match="not a risk_policy field"):
        supersede_active_policy(conn, field_updates={"not_a_field": 1.0})


def test_supersede_writes_atomic_on_failure(conn, monkeypatch):
    """Injected exception between predecessor UPDATE and successor INSERT
    rolls back the predecessor UPDATE. After failure: policy_id=1 still active,
    no policy_id=2 row."""
    # Monkeypatch insert_policy to raise mid-transaction.
    from swing.data.repos import risk_policy as repo_mod
    original = repo_mod.insert_policy

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic mid-tx fault")
    monkeypatch.setattr(repo_mod, "insert_policy", boom)

    with pytest.raises(RuntimeError, match="synthetic"):
        supersede_active_policy(conn, field_updates={"max_account_risk_per_trade_pct": 0.75})

    p = get_active_policy(conn)
    assert p.policy_id == 1
    assert p.is_active == 1


def test_read_active_policy_delegates(conn):
    p = read_active_policy(conn)
    assert p.policy_id == 1


def test_check_and_reconcile_toml_divergence_no_divergence(conn, cfg_fixture):
    """When TOML risk_equity_floor matches risk_policy.capital_floor_constant_dollars,
    returns (cfg, None) — original config unchanged."""
    from swing.trades.risk_policy import check_and_reconcile_toml_divergence
    # cfg_fixture starts with risk_equity_floor=7500.0 matching the seed.
    new_cfg, divergence = check_and_reconcile_toml_divergence(conn, cfg_fixture)
    assert divergence is None
    assert new_cfg is cfg_fixture  # identity test — no replacement when no divergence


def test_check_and_reconcile_toml_divergence_with_divergence(conn, cfg_fixture_5000, caplog):
    """When TOML diverges, return (corrected_cfg, divergence_dict). Original cfg unchanged
    per Codex R3 M#1 frozen-dataclass discipline."""
    from swing.trades.risk_policy import check_and_reconcile_toml_divergence
    original = cfg_fixture_5000  # risk_equity_floor=5000.0
    with caplog.at_level("WARNING"):
        new_cfg, divergence = check_and_reconcile_toml_divergence(conn, original)
    assert divergence == {
        "field": "capital_floor_constant_dollars",
        "toml_value": 5000.0,
        "policy_value": 7500.0,
    }
    assert "TOML diverges from risk_policy" in caplog.text
    # New corrected Config has updated value.
    assert new_cfg.account.risk_equity_floor == 7500.0
    # Original cfg UNCHANGED (frozen dataclass; immutability preserved).
    assert original.account.risk_equity_floor == 5000.0
    # new_cfg is a different object from original.
    assert new_cfg is not original


def test_check_and_reconcile_toml_divergence_pre_v17_silent_skip(tmp_path):
    """On a pre-v17 DB (no risk_policy table), the helper returns (cfg, None)
    silently — does NOT raise. Ensures `db-migrate` can run without hitting
    a divergence check that depends on the very schema it's about to create."""
    from swing.data.db import init_db_at_version
    from swing.trades.risk_policy import check_and_reconcile_toml_divergence
    # init_db_at_version is a test helper that stops migrations at the named version;
    # implementer wires per Phase 8 plan precedent if not already present.
    pre_v17_conn = init_db_at_version(tmp_path / "pre_v17.db", target_version=16)
    cfg = _fixture_cfg(risk_equity_floor=5000.0)
    new_cfg, divergence = check_and_reconcile_toml_divergence(pre_v17_conn, cfg)
    assert divergence is None
    assert new_cfg is cfg


@pytest.fixture
def conn(tmp_path):
    from swing.data.db import init_db
    return init_db(tmp_path / "test.db")


@pytest.fixture
def cfg_fixture():
    """Returns a real frozen Config dataclass with risk_equity_floor=7500.0 (matches seed)."""
    return _fixture_cfg(risk_equity_floor=7500.0)


@pytest.fixture
def cfg_fixture_5000():
    """Returns a real frozen Config with risk_equity_floor=5000.0 (diverges from seed)."""
    return _fixture_cfg(risk_equity_floor=5000.0)


def _fixture_cfg(*, risk_equity_floor: float):
    """Builds a minimal valid Config (frozen) for divergence tests. Implementer
    wires the full builder per the existing Config dataclass tree at swing/config.py;
    this stub indicates the test pattern."""
    from swing.config import Config, Account  # frozen dataclasses
    # ... build minimal Config via the actual frozen-dataclass constructors.
    raise NotImplementedError("implementer wires per existing Config tree shape")
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: FAIL on `ImportError`.

- [ ] **Step 3: Implement service**

Implement `swing/trades/risk_policy.py` per file map. Key design points:

```python
# swing/trades/risk_policy.py
"""risk_policy service layer — supersession 6-step transactional sequence +
cfg-mirror cascade + TOML divergence detection.

Transactional contract (per dispatch brief §0.3 #5 + Phase 8 R4 M1 lesson):
caller MUST NOT hold an open transaction; function ALWAYS owns BEGIN IMMEDIATE /
COMMIT / ROLLBACK; rejects (does not auto-detect) caller-held transactions.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Literal

from swing.data.datetime_helpers import now_ms
from swing.data.models import RiskPolicy
from swing.data.repos import risk_policy as repo

logger = logging.getLogger(__name__)

_VALID_FIELDS: frozenset[str] = frozenset({
    "max_account_risk_per_trade_pct", "max_concurrent_positions",
    "max_portfolio_heat_pct", "max_sector_concentration_positions",
    "consecutive_losses_pause_threshold", "consecutive_losses_pause_action",
    "consecutive_losses_streak_reset", "drawdown_circuit_breaker_enabled",
    "drawdown_pause_threshold_R", "drawdown_pause_action",
    "drawdown_size_reduction_pct", "drawdown_recovery_threshold_R",
    "capital_floor_constant_dollars", "scratch_epsilon_R",
    "review_lag_threshold_days",
    "low_sample_size_threshold_class_a_n", "low_sample_size_threshold_class_b_n",
    "low_sample_size_threshold_class_c_n", "low_sample_size_threshold_class_d_n",
    "global_confidence_floor_n", "bootstrap_resample_count",
    "process_grade_weight_entry", "process_grade_weight_management",
    "process_grade_weight_exit", "mfe_mae_default_precision_level",
    "trail_MA_period_days", "trail_MA_post_2R_period_days",
    "policy_notes",
})


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes a single-transaction service while holding
    an open transaction (Phase 8 R4 M1 lesson — reject + simple contract)."""


def supersede_active_policy(
    conn: sqlite3.Connection,
    *,
    field_updates: dict[str, Any],
    notes: str | None = None,
    source: Literal["cli", "cfg_cascade", "import_from_toml"] = "cli",
) -> int:
    """6-step supersession sequence per spec §4.1.

    Args:
        conn: SQLite connection. Caller MUST NOT hold an open transaction.
        field_updates: dict of risk_policy column -> new value. Unspecified fields
            are copied from the predecessor row.
        notes: optional free-text rationale stored in policy_notes.
        source: provenance tag (also stored in policy_notes if notes is None).

    Returns:
        Newly-inserted policy_id.

    Raises:
        CallerHeldTransactionError: caller has open transaction.
        ValueError: field_updates contains a non-risk_policy column.
        ValidationError (via RiskPolicy.__post_init__): values fail dataclass validation.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "supersede_active_policy owns its own transaction; caller MUST NOT "
            "hold an open transaction. See dispatch-brief §0.3 #5 + CLAUDE.md "
            "gotcha 'Service-layer with conn:'."
        )

    invalid = set(field_updates) - _VALID_FIELDS
    if invalid:
        raise ValueError(f"field_updates contains values not a risk_policy field: {invalid}")

    try:
        conn.execute("BEGIN IMMEDIATE")
        # Step 1: identify predecessor by exact PK (Phase 8 R3 M3 lesson).
        cur = conn.execute("SELECT policy_id FROM risk_policy WHERE is_active = 1")
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("No active policy — schema corrupted or seed missing")
        predecessor_id = row[0]
        predecessor = repo.get_policy_by_id(conn, policy_id=predecessor_id)

        ts = now_ms()

        # Step 2: flag predecessor is_active=0 + effective_to=ts (frees uniqueness slot).
        repo.update_policy_active_flag(
            conn, policy_id=predecessor_id, is_active=0, effective_to=ts,
            superseded_by_policy_id=None,  # set in step 5
        )

        # Step 3: build successor fields (copy predecessor, apply field_updates).
        successor_fields = predecessor.field_copy_excluding_pk_and_timeline()
        successor_fields.update(field_updates)
        successor_fields["effective_from"] = ts
        successor_fields["effective_to"] = None
        successor_fields["is_active"] = 1
        successor_fields["superseded_by_policy_id"] = None
        successor_fields["created_at"] = ts
        if notes is not None:
            successor_fields["policy_notes"] = notes
        elif source == "cfg_cascade":
            successor_fields["policy_notes"] = "auto-cascade from cfg.account.risk_equity_floor edit"
        # Validates via RiskPolicy dataclass __post_init__.
        validation_dataclass = RiskPolicy(policy_id=0, **successor_fields)

        # Step 4: INSERT successor; capture new policy_id.
        successor_id = repo.insert_policy(conn, **successor_fields)

        # Step 5: UPDATE predecessor.superseded_by_policy_id = successor_id.
        repo.update_policy_active_flag(
            conn, policy_id=predecessor_id, is_active=0, effective_to=ts,
            superseded_by_policy_id=successor_id,
        )

        # Step 6: COMMIT.
        conn.commit()
        return successor_id
    except Exception:
        conn.rollback()
        raise


def read_active_policy(conn: sqlite3.Connection) -> RiskPolicy:
    """Read-only delegate."""
    return repo.get_active_policy(conn)


def check_and_reconcile_toml_divergence(conn, cfg) -> tuple["Config", dict | None]:
    """Called at startup from CLI command handlers + web app lifespan AFTER
    `ensure_schema` has brought the DB to v17. Per Codex R3 M#1 fix:
    - `swing/config.py:load(config_path)` remains pure (no DB read in load).
    - This helper performs the DB read + divergence check.
    - Config is a frozen dataclass; corrected cfg is built via `dataclasses.replace`.
    - On a pre-v17 DB or no-active-policy (test fixtures, fresh DBs): returns
      (cfg, None) silently. NEVER raises.

    Returns:
        (new_cfg, divergence_dict_or_None). new_cfg is `cfg` itself when no
        divergence; a new Config (via dataclasses.replace) when divergent.
    """
    import dataclasses
    # First check schema version — only proceed with the divergence read when
    # the schema is at or past v17 (Codex R5 Minor #1 fix — was previously
    # catching all sqlite3.OperationalError, which could mask real post-v17
    # failures like DB lock or missing columns).
    cur = conn.execute("SELECT version FROM schema_version")
    row = cur.fetchone()
    if row is None or row[0] < 17:
        # Pre-v17 schema; risk_policy table not yet present. Skip silently
        # to keep `swing db-migrate` + fresh-DB fixtures unblocked.
        return cfg, None
    try:
        active = repo.get_active_policy(conn)
    except repo.NoActivePolicyError:
        # v17 schema present but no is_active=1 row (test fixture pre-seed).
        return cfg, None

    toml_v = cfg.account.risk_equity_floor
    policy_v = active.capital_floor_constant_dollars
    if abs(toml_v - policy_v) < 1e-9:
        return cfg, None

    logger.warning(
        "TOML diverges from risk_policy: cfg.account.risk_equity_floor=%s vs "
        "risk_policy.capital_floor_constant_dollars=%s; risk_policy is authoritative. "
        "To make TOML canonical, run: swing config policy import-from-toml --field capital_floor_constant_dollars",
        toml_v, policy_v,
    )
    new_account = dataclasses.replace(cfg.account, risk_equity_floor=policy_v)
    new_cfg = dataclasses.replace(cfg, account=new_account)
    divergence = {
        "field": "capital_floor_constant_dollars",
        "toml_value": toml_v,
        "policy_value": policy_v,
    }
    return new_cfg, divergence


def seed_initial_policy(conn, cfg) -> int:
    """Called from migration runner OR migration SQL. Idempotent — no-ops if
    risk_policy.is_active=1 row already exists.

    Returns:
        policy_id of the existing or newly-created policy.
    """
    try:
        active = repo.get_active_policy(conn)
        return active.policy_id
    except repo.NoActivePolicyError:
        pass
    # ... (insert seed row from cfg defaults — implementer draws from spec §3.1.3 seed table)
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/risk_policy.py tests/trades/test_risk_policy_service.py
git commit -m "feat(trades): Task A.4 — risk_policy service with 6-step supersession + caller-tx rejection"
```

### Task A.5: cfg-mirror cascade + post-schema-validation startup hook (Codex R3 M#1 + R4 M#1 fix)

**Files (revised per Codex R3 M#1 — `swing/config.py` is UNCHANGED):**
- Modify: `swing/web/routes/config.py` (cascade to risk_policy on risk_equity_floor edit)
- Modify: `swing/cli.py` (add post-schema-validation startup hook at every CLI handler that needs a divergence-corrected cfg; `db-migrate` handler explicitly SKIPS)
- Modify: `swing/web/app.py` (or lifespan/middleware; add post-`ensure_schema` startup hook setting `app.state.cfg` to the corrected immutable Config)
- Test: `tests/web/test_config_route_risk_policy_cascade.py`
- Test: `tests/cli/test_cli_toml_divergence_post_schema_hook.py` (CLI-entry hook)
- Test: `tests/web/test_web_lifespan_toml_divergence_hook.py` (web lifespan hook)
- Test: `tests/cli/test_db_migrate_skips_divergence_hook.py` (regression — `swing db-migrate` does NOT invoke the check on v16 → v17 DB)

**Depends on:** T-A.4 (helper `check_and_reconcile_toml_divergence` exists).

**Acceptance criteria (revised per Codex R3 M#1 + R4 M#1):**

1. **Phase 5 config-page cascade (existing scope, unchanged from R0):** when the Phase 5 config-page POST handler at `swing/web/routes/config.py` changes `cfg.account.risk_equity_floor`, ALSO call `swing/trades/risk_policy.py:supersede_active_policy(conn, field_updates={"capital_floor_constant_dollars": new_value}, source="cfg_cascade", notes="...")`. A new policy_id row is created with the updated capital_floor. Other cfg fields (`chase_factor`, `chart_top_n_watch`) DO NOT cascade.
2. **Post-schema-validation CLI hook (Codex R3 M#1 + R4 M#1 fix; replaces the prior `load_config` extension):** every CLI handler in `swing/cli.py` that needs a divergence-corrected cfg invokes — AFTER `ensure_schema(conn)` succeeds AND AFTER `load_config()` returns — `check_and_reconcile_toml_divergence(conn, cfg)`; rebinds the local `cfg` variable to the returned corrected Config. The `swing db-migrate` CLI handler explicitly SKIPS this hook (since it is the path that brings DB to v17). When divergence is detected, the CLI emits a stderr advisory line per spec §3.1.3 R3 Minor #2 (mirrors `pip` / `git` divergence-warning pattern).
3. **Post-`ensure_schema` web lifespan hook:** the web app startup invokes the same helper after `ensure_schema(conn)`; sets `app.state.cfg` to the corrected Config. Implementer wires the FastAPI lifespan / startup event in `swing/web/app.py` (or wherever lifespan currently lives — implementer reads current shape).
4. **`swing/config.py` is UNCHANGED.** `load(config_path)` remains pure with no DB connection parameter. No `apply_toml_divergence_correction` call from inside load. Confirmation via discriminating test: invoking `load(config_path)` on a fresh repo without any DB connection succeeds.
5. **Discriminating tests:**
   - `test_cli_handler_invokes_divergence_hook_after_ensure_schema`: monkey-patch `check_and_reconcile_toml_divergence` to capture invocation order; assert it fires AFTER `ensure_schema` for `swing config policy show`-style handlers.
   - `test_db_migrate_skips_divergence_hook`: invoke `swing db-migrate` on a v16 DB; assert (a) migration succeeds bringing DB to v17, (b) `check_and_reconcile_toml_divergence` is NOT invoked during the command (verified via monkey-patch / call-count fixture). Pre-fix expectation (if implementer forgot the skip): hook fires on the v16 DB, would catch `OperationalError` from missing risk_policy table, returns `(cfg, None)` — passes silently but burns a DB read. Post-fix expectation: zero invocations.
   - `test_web_lifespan_sets_corrected_app_state_cfg`: start TestClient lifespan against a DB with a divergent risk_policy seed; assert `app.state.cfg.account.risk_equity_floor` equals the policy value, not the TOML value.
   - `test_load_config_pure_no_db_required`: invoke `load(config_path)` with no DB present anywhere in the test environment; assert succeeds without raising.
6. **HTMX form lessons (Phase 5 R1 M1+M2) PRESERVED:** HX-Request propagation on embedded config-page form + HX-Redirect success-path response. Regression-clean.

(Step-by-step TDD cycle abbreviated; implementer follows Phase 8 plan precedent + dispatch brief §0.3 #9 server-stamping guidance — no hidden inputs added.)

- [ ] **Step 1: Write failing test for cfg-mirror cascade in Phase 5 config-page POST**
- [ ] **Step 2: Write failing tests for CLI post-schema hook + db-migrate skip + web lifespan + load() purity**
- [ ] **Step 3: Implement route cascade in `swing/web/routes/config.py`; implement CLI hook in `swing/cli.py`; implement web lifespan hook in `swing/web/app.py`**
- [ ] **Step 4: Verify HTMX surfaces still pass (HX-Request + HX-Redirect)**
- [ ] **Step 5: Verify TOML file not written by either cascade or divergence correction**
- [ ] **Step 6: Run + verify all pass**
- [ ] **Step 7: Commit**

```bash
git add swing/cli.py swing/web/app.py swing/web/routes/config.py tests/web/test_config_route_risk_policy_cascade.py tests/cli/test_cli_toml_divergence_post_schema_hook.py tests/web/test_web_lifespan_toml_divergence_hook.py tests/cli/test_db_migrate_skips_divergence_hook.py
git commit -m "feat(web,cli): Task A.5 — Phase 5 config cascade + post-schema-validation TOML divergence hooks (CLI + web lifespan); swing/config.py:load() remains pure"
```

### Task A.6: CLI surface for risk_policy editing

**Files:**
- Modify: `swing/cli.py` (add `swing config policy` group with show / set / import-from-toml / history)
- Test: `tests/cli/test_config_policy_cli.py`

**Depends on:** T-A.4.

**Acceptance criteria per spec §10.5 brainstorm rec + §A.3 plan lock:**
- `swing config policy show` prints active row in human-readable form.
- `swing config policy set --field <name> --value <val> [--notes "..."]` invokes supersede_active_policy. Field name is validated against `_VALID_FIELDS`.
- `swing config policy import-from-toml --field <name>` reads current cfg value + invokes supersede with `source='import_from_toml'`.
- `swing config policy history --limit 10` prints recent rows.
- All CLI commands server-stamp timestamps (per dispatch brief §0.3 #9).

(Step-by-step TDD cycle abbreviated; implementer follows Phase 8 plan precedent.)

- [ ] **Step 1: Write failing CLI test (click testing harness)**
- [ ] **Step 2: Implement CLI commands**
- [ ] **Step 3: Verify pass**
- [ ] **Step 4: Commit**

```bash
git add swing/cli.py tests/cli/test_config_policy_cli.py
git commit -m "feat(cli): Task A.6 — swing config policy CLI group (show / set / import-from-toml / history)"
```

### Task A.7: Phase 7 entry stamp + Phase 6 review stamp

**Files:**
- Modify: `swing/trades/entry.py` (stamp risk_policy_id_at_lock at entry_create)
- Modify: `swing/data/repos/review_log.py` (stamp risk_policy_id_at_review_completion in complete_review_atomic)
- Test: `tests/trades/test_phase7_entry_risk_policy_stamp.py`
- Test: `tests/trades/test_phase6_review_risk_policy_stamp.py`

**Depends on:** T-A.3 (repo readable).

**Acceptance criteria per spec §3.1.1:**
- After `entry_create` against a new trade, `trades.risk_policy_id_at_lock` equals `risk_policy.is_active=1.policy_id`.
- After `complete_review_atomic` on a review_log row, `risk_policy_id_at_review_completion` is set to current active policy_id.
- Stamps happen WITHIN the existing transaction (no new transaction opened).
- Legacy trades + reviews pre-migration have NULL — read-path resolution returns current policy (NOT an error).
- Discriminating test: supersede policy mid-test; assert NEW trade entry stamps NEW policy_id, NOT the prior one (read-time vs lock-time semantics work correctly).

(Step-by-step TDD cycle abbreviated; this is a one-line edit per service + corresponding regression tests.)

- [ ] **Step 1: Write failing entry-stamp test**
- [ ] **Step 2: Write failing review-stamp test**
- [ ] **Step 3: Implement one-line stamp in entry.py**
- [ ] **Step 4: Implement one-line stamp in review_log.py**
- [ ] **Step 5: Verify pass**
- [ ] **Step 6: Commit**

```bash
git add swing/trades/entry.py swing/data/repos/review_log.py tests/trades/test_phase7_entry_risk_policy_stamp.py tests/trades/test_phase6_review_risk_policy_stamp.py
git commit -m "feat(trades): Task A.7 — Phase 7 entry + Phase 6 review-complete stamps for risk_policy_id"
```

---

## §E — Sub-bundle B: reconciliation depth

**Goal:** Schema (reconciliation_runs + reconciliation_discrepancies tables — APPENDED to migration 0017) + repo + service + tos_import.py refactor + CLI for reconciliation runs + discrepancy resolution + the §5.1 canonical queries.

**Sub-bundle B surfaces 6 operator-witnessed gates:**
- S1: Post-A-merge baseline; risk_policy + entry/review stamps green.
- S2: Consumer-side schema verification (T-B.0) passes against the COMPLETE migration 0017 already landed in sub-bundle A (all 5 tables already present at v17; no new migration; B ships repo + service + CLI on top).
- S3: `swing journal reconcile-tos --csv-path data/fixtures/sample.csv` runs end-to-end; reconciliation_runs row + discrepancy rows persisted.
- S4: Deliberate price-mismatch CSV produces close_price_mismatch + entry_price_mismatch discrepancies; `swing journal discrepancy list` shows them.
- S5: `swing journal discrepancy resolve <id> --resolution journal_corrected --reason "..."` updates the row; `resolved_at` server-stamped.
- S6: `list_unresolved_material_for_active_trades` returns the open-trade alert set; `list_unresolved_material_for_closed_trades` returns the closed-trade attention set (per spec §5.1 canonical queries).

### Task B.0: Verify reconciliation schema from sub-bundle A migration (read-only)

**Files:**
- Test: `tests/data/test_phase9_reconciliation_schema_verification.py` (consumer-side schema verification)

**Depends on:** T-A.1 (migration already landed reconciliation_runs + reconciliation_discrepancies).

**Repurposed per Codex R1 Critical #1 fix:** the migration itself was completed atomically in T-A.1. This task adds a CONSUMER-SIDE verification that the schema sub-bundle B depends on is correctly provisioned before B's repo + service tasks build on it. No DDL changes.

**Acceptance criteria:**
- `reconciliation_runs` table exists with 17 columns per spec §3.2 (verified via PRAGMA table_info).
- 3 indexes present: `ix_reconciliation_runs_started_ts`, `ix_reconciliation_runs_state` (partial), `ix_reconciliation_runs_source` (composite). Verified via `PRAGMA index_list(reconciliation_runs)`.
- `reconciliation_discrepancies` table exists with 18 columns per spec §3.3.
- 4 indexes present including partials per spec §3.3.
- FK CASCADE on `reconciliation_discrepancies.run_id` → `reconciliation_runs(run_id)`: insert run + discrepancy + DELETE run + assert discrepancy absent.
- FK SET NULL on `trade_id`, `fill_id`, `cash_movement_id`, `linked_daily_management_record_id`: insert discrepancy referencing a trade + DELETE trade + assert discrepancy row survives with NULL trade_id.
- CHECK constraints on `discrepancy_type`, `resolution` enums per spec §3.3 reject invalid values.

(Step-by-step TDD cycle abbreviated.)

- [ ] **Step 1: Write schema-verification tests**
- [ ] **Step 2: Verify tests pass against the v17 schema landed by T-A.1**
- [ ] **Step 3: Commit**

```bash
git add tests/data/test_phase9_reconciliation_schema_verification.py
git commit -m "test(data): Task B.0 — verify reconciliation schema from T-A.1 migration (consumer-side)"
```

### Task B.1: Reconciliation dataclasses + repo

**Files:**
- Modify: `swing/data/models.py` (add `ReconciliationRun`, `ReconciliationDiscrepancy` dataclasses with `__post_init__` validators)
- Create: `swing/data/repos/reconciliation.py`
- Test: `tests/data/test_reconciliation_repo.py`

**Depends on:** T-B.0.

**Acceptance criteria:**
- Repo functions match file map signatures.
- `list_recent_runs` implements TWO-READ PATTERN per CLAUDE.md gotcha (separate query for most-recent-COMPLETED + most-recent-STARTED).
- `list_unresolved_material_for_active_trades` query matches spec §5.1 CANONICAL #1.
- `list_unresolved_material_for_closed_trades` query matches spec §5.1 CANONICAL #2.
- `count_runs_for_artifact_sha256` advisory for re-run detection.
- Repo functions do NOT call `conn.commit()` (per Finviz I1 lesson).
- Dataclass `__post_init__` validators reject invalid enum values / NaN / inf.

(Step-by-step TDD cycle abbreviated; implementer follows Phase 8 plan precedent.)

- [ ] **Step 1: Write failing repo tests**
- [ ] **Step 2: Implement dataclasses + repo**
- [ ] **Step 3: Verify pass**
- [ ] **Step 4: Commit**

```bash
git add swing/data/models.py swing/data/repos/reconciliation.py tests/data/test_reconciliation_repo.py
git commit -m "feat(data): Task B.1 — reconciliation dataclasses + repo with canonical queries"
```

### Task B.2: TOS-import refactor — extract emitter seam

**Files:**
- Modify: `swing/journal/tos_import.py` (refactor `reconcile_tos` signature to accept `*, run_id: int, emitter: Callable[..., int]`)
- Test: extend `tests/journal/test_tos_import.py` (regression — existing callers still work)

**Depends on:** T-B.1 (emitter target exists).

**Acceptance criteria:**
- New signature: `def reconcile_tos(conn, csv_text, *, run_id: int | None = None, emitter: Callable[..., int] | None = None) -> ReconciliationReport`.
- When `run_id` + `emitter` are None, behavior matches pre-refactor (backwards-compat — preserves existing CLI invocation that does NOT yet route through reconciliation_runs).
- When `run_id` + `emitter` provided, each detected discrepancy is forwarded via `emitter(discrepancy_type=<type>, ..., run_id=run_id)`.
- Existing `ReconciliationReport` dataclass return shape preserved.
- ALL existing tos_import tests still pass (regression-clean).

(Step-by-step TDD cycle abbreviated.)

- [ ] **Step 1: Write regression test verifying backwards-compat**
- [ ] **Step 2: Refactor signature**
- [ ] **Step 3: Verify all tos_import tests + new test pass**
- [ ] **Step 4: Commit**

```bash
git add swing/journal/tos_import.py tests/journal/test_tos_import.py
git commit -m "refactor(journal): Task B.2 — extract emitter seam in reconcile_tos (backwards-compat preserved)"
```

### Task B.3: TOS-import extension — close_price_mismatch + entry_price_mismatch detection

**Files:**
- Modify: `swing/journal/tos_import.py` (extend matched-fill loop to compare close prices)
- Test: `tests/journal/test_tos_import_reconciliation_extension.py` (add close_price + entry_price scenarios)
- Fixture: `tests/fixtures/tos/close_price_mismatch.csv`
- Fixture: `tests/fixtures/tos/entry_price_mismatch.csv`

**Depends on:** T-B.2.

**Acceptance criteria per spec §6.1:**
- When a matched close-fill has `abs(tos_price - journal_exit_fill_price) > price_tolerance` (strict greater-than per existing convention at `swing/journal/tos_import.py:365`), emit `close_price_mismatch` discrepancy via `emitter(discrepancy_type='close_price_mismatch', trade_id=t, fill_id=f, expected_value_json={...}, actual_value_json={...}, material_to_review=1, ticker=..., field_name='price')`.
- Same pattern for OPEN-fill (entry_price_mismatch — existing path).
- **`price_tolerance` LOCKED for V1 (Codex R2 Major #3 fix — was previously left as TBD with two candidate sources):** uses the existing function parameter `reconcile_tos(..., price_tolerance: float = 0.01, ...)` at `swing/journal/tos_import.py:326`. No new cfg field added in Phase 9 (avoiding cfg-vs-risk_policy ambiguity per spec §3.1.3 + risk_policy-mirror discipline). No `risk_policy.scratch_epsilon_R * entry_price` derivation in V1 (deferred to V2 — scratch_epsilon is R-unit threshold for win/loss classification, not price-tolerance dollars; the conflation was incorrect in the original plan text). The existing default 0.01 USD is the V1 binding; operator override path is the same function parameter via the CLI's `--price-tolerance` flag (which writing-plans codifies if not already present; otherwise inherits existing behavior — implementer verifies at T-B.7).
- delta_text rendered as `"$N.NN price difference"` (signed).
- Fixture CSVs cover: exact match (delta = 0) → NO emission; within tolerance (delta = 0.005) → NO emission; at boundary (delta = 0.01) → NO emission per strict-greater-than convention; outside tolerance (delta = 0.02) → EMIT. This is the discriminating boundary pattern.

(Step-by-step abbreviated.)

- [ ] **Step 1-7: TDD cycle for each fixture scenario + emitter wire**
- [ ] **Step 8: Commit**

```bash
git add swing/journal/tos_import.py tests/journal/test_tos_import_reconciliation_extension.py tests/fixtures/tos/
git commit -m "feat(journal): Task B.3 — close_price_mismatch + entry_price_mismatch detection per spec §6.1"
```

### Task B.4: TOS-import extension — stop_mismatch detection (Account Order History parsing)

**Files:**
- Modify: `swing/journal/tos_import.py` (add stop_order_extractor for Account Order History section per spec §6.2)
- Test: `tests/journal/test_tos_import_reconciliation_extension.py` (add stop_mismatch scenarios)
- Fixture: `tests/fixtures/tos/stop_mismatch_open_trade_no_broker_stop.csv`
- Fixture: `tests/fixtures/tos/stop_mismatch_broker_stop_no_open_trade.csv`
- Fixture: `tests/fixtures/tos/stop_mismatch_value_delta.csv`

**Depends on:** T-B.3.

**Acceptance criteria per spec §6.2:**
- Parse Account Order History section; extract WORKING SELL TO CLOSE STP rows.
- Output: `list[(ticker, working_stop_price, order_id_or_none)]`.
- For each open trade with current_stop: compare. **Mismatch (`abs(trades.current_stop - broker_working_stop) > price_tolerance`, i.e., difference OUTSIDE tolerance) → emit `stop_mismatch`** (Codex R1 Major #3 fix — earlier wording read "within tolerance" which was inverted; per spec §6.2 mismatch fires when the delta exceeds tolerance).
- Open trade with NO broker stop → emit with `actual_value_json={"working_stop_price": null, "order_id": null}`.
- Broker stop with NO matching journal trade → emit with `expected_value_json={}` (orphan).
- All three scenarios material=1.
- Discriminating test pattern (mirrors T-B.3 close-price-mismatch boundary convention; uses same `price_tolerance` parameter at `swing/journal/tos_import.py:326`, default 0.01): exact match (delta = 0) → NO emission; within tolerance (delta = 0.005) → NO emission; at boundary (delta = 0.01) → NO emission per existing strict-greater-than convention at `swing/journal/tos_import.py:365`; outside tolerance (delta = 0.02) → EMIT.

(Step-by-step abbreviated.)

- [ ] **Step 1-7: TDD cycle**
- [ ] **Step 8: Commit**

```bash
git add swing/journal/tos_import.py tests/journal/test_tos_import_reconciliation_extension.py tests/fixtures/tos/
git commit -m "feat(journal): Task B.4 — stop_mismatch detection via Account Order History parsing"
```

### Task B.5: TOS-import extension — position_qty_mismatch detection (Equities section parsing)

**Files:**
- Modify: `swing/journal/tos_import.py` (add Equities section parser per spec §6.3)
- Test: `tests/journal/test_tos_import_reconciliation_extension.py` (add position_qty scenarios)
- Fixture: `tests/fixtures/tos/position_qty_mismatch_*.csv` (3 variants)

**Depends on:** T-B.4.

**Acceptance criteria per spec §6.3:**
- Add 'Equities' to `_SECTION_LABELS` + new `equities_extractor` returning `dict[ticker, qty]`.
- For each open trade: compare `current_size` to TOS qty. Mismatch → emit.
- TOS ticker with no journal open trade → emit (trade_id=NULL, ticker populated).
- Journal open trade with no TOS qty → emit (actual_value_json shows qty=0).
- All scenarios material=1.

(Step-by-step abbreviated.)

- [ ] **Step 1-7: TDD cycle**
- [ ] **Step 8: Commit**

```bash
git add swing/journal/tos_import.py tests/journal/test_tos_import_reconciliation_extension.py tests/fixtures/tos/
git commit -m "feat(journal): Task B.5 — position_qty_mismatch via Equities section parser"
```

### Task B.6: TOS-import extension — cash_movement_mismatch + service orchestration

**Files:**
- Modify: `swing/journal/tos_import.py` (cash_movement amount/kind comparison per spec §6.4)
- Create: `swing/trades/reconciliation.py` (service per §A.2)
- Test: extend `tests/journal/test_tos_import_reconciliation_extension.py` (cash_movement scenarios)
- Test: `tests/trades/test_reconciliation_service.py`

**Depends on:** T-B.5.

**Acceptance criteria per spec §6.4 + §A.2:**
- Cash_movement_mismatch detection: when REF# duplicate but amount or kind differs, emit `cash_movement_mismatch` (material=0 — cash flow doesn't bear on trade review).
- `swing/trades/reconciliation.py:run_tos_reconciliation` orchestrates the full flow per §A.2 + spec §3.3.3: BEGIN IMMEDIATE → INSERT run row → call refactored reconcile_tos with run_id + emitter → on success, UPDATE run state='completed' + summary fields → COMMIT. **On exception (Codex R1 Major #1 fix):** catch inside the same transaction → UPDATE the existing run row's `state='failed', finished_ts=now, error_message=str(e)` → COMMIT. Run row preserved; discrepancies / fills / cash_movements emitted prior to failure are PRESERVED alongside the failed-state UPDATE per spec audit-trail-integrity-over-rollback-purity disposition.
- Service rejects caller-held transaction.
- `MATERIAL_BY_TYPE` lookup constant defined per spec §3.3.1.
- Within-run dedup via in-memory set (Phase 9 spec §5.1 R3 Major #4 fix).
- `source_artifact_sha256` computed at run-start.

(Step-by-step abbreviated; complex task — implementer breaks into TDD micro-cycles.)

- [ ] **Step 1-15: TDD cycles per spec §3.3.1 type table**
- [ ] **Step 16: Failure-path test per spec §3.3.3 + Codex R1 M#1 fix — inject synthetic exception AFTER emitter has fired for ≥1 discrepancy; assert: (a) reconciliation_runs row PRESENT with state='failed' (NOT absent), (b) error_message populated, (c) discrepancies emitted prior to failure ARE PRESERVED, (d) conn.in_transaction == False post-call. Pre-fix expectation (the spec-deviating original plan): row would be absent with discrepancies rolled back. Post-fix expectation: row present with state='failed' + partial discrepancies committed. This is the discriminating distinction.**
- [ ] **Step 17: Within-run dedup test**
- [ ] **Step 18: Caller-tx rejection test**
- [ ] **Step 19: Commit**

```bash
git add swing/journal/tos_import.py swing/trades/reconciliation.py tests/journal/test_tos_import_reconciliation_extension.py tests/trades/test_reconciliation_service.py tests/fixtures/tos/
git commit -m "feat(trades): Task B.6 — reconciliation service + cash_movement_mismatch detection"
```

### Task B.7: CLI surface — `swing journal reconcile-tos` (rename) + alias + `swing journal discrepancy`

**Files:**
- Modify: `swing/cli.py` (rename `import-tos` → `reconcile-tos` + add deprecation alias; add `discrepancy` group)
- Test: `tests/cli/test_discrepancy_cli.py`
- Test: `tests/journal/test_tos_import_cli_rename.py`

**Depends on:** T-B.6.

**Acceptance criteria per §A.2.2 + spec §4.2:**
- `swing journal reconcile-tos --csv-path <p> [--period-end <iso>] [--notes "..."]` invokes the new service.
- `swing journal import-tos <args>` is a deprecation alias — works, but prints stderr WARNING: "deprecated; use `swing journal reconcile-tos` instead".
- `swing journal discrepancy list [--unresolved] [--material] [--trade-id N]` lists rows.
- `swing journal discrepancy show <id>` prints full discrepancy detail (incl. expected/actual JSON, delta_text).
- `swing journal discrepancy resolve <id> --resolution <enum> --reason "..."` resolves; resolved_at + resolved_by server-stamped.

(Step-by-step abbreviated.)

- [ ] **Step 1-10: TDD cycle**
- [ ] **Step 11: Commit**

```bash
git add swing/cli.py tests/cli/test_discrepancy_cli.py tests/journal/test_tos_import_cli_rename.py
git commit -m "feat(cli): Task B.7 — swing journal reconcile-tos + alias + discrepancy CLI group"
```

### Task B.8: E2E reconciliation integration test

**Files:**
- Test: extend `tests/integration/test_phase9_end_to_end.py` (B sub-bundle scope: reconciliation E2E)

**Depends on:** T-B.7.

**Acceptance criteria:**
- Reconcile a CSV with 1 close_price_mismatch + 1 stop_mismatch + 1 position_qty_mismatch + 1 cash_movement_mismatch.
- Assert 4 discrepancies persisted with correct material_to_review per MATERIAL_BY_TYPE.
- Assert `list_unresolved_material_for_active_trades` returns 2 attention rows (close_price + stop + position_qty are MATERIAL=1; cash_movement is MATERIAL=0 + has no trade_id — query returns active trades with material discrepancies).
- Operator resolves one via CLI → assert row's resolution + resolved_at updated.

(Step-by-step abbreviated.)

- [ ] **Step 1-5: E2E TDD cycle**
- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_phase9_end_to_end.py
git commit -m "test(integration): Task B.8 — reconciliation E2E with all 4 discrepancy types"
```

---

## §F — Sub-bundle C: hypothesis_status_history + account_equity_snapshots

**Goal:** Schema (hypothesis_status_history + account_equity_snapshots — APPENDED to migration 0017) + repos + services + CLI `account snapshot` + rewire `swing hypothesis update` through new service helper.

**Sub-bundle C surfaces 4 operator-witnessed gates:**
- S1: Consumer-side schema verification (T-C.0 + T-C.1) passes against the COMPLETE migration 0017 already landed in sub-bundle A (hypothesis_status_history + account_equity_snapshots tables already present at v17; seed rows already inserted; no new migration; C ships repo + service + CLI on top).
- S2: `swing account snapshot --equity 1300` writes row; `swing account snapshot --equity 1400 --date 2026-04-01` upserts.
- S3: `swing hypothesis update --hypothesis VIR --status paused --reason "..."` writes hypothesis_status_history row AND closes prior open interval; rejects identity transitions with INFO-level message.
- S4: Read-path: `get_latest_snapshot_on_or_before(asof=today)` returns the most-recent snapshot under source-ladder precedence.

### Task C.0: Verify hypothesis_status_history + account_equity_snapshots schema from sub-bundle A (read-only)

**Files:**
- Test: `tests/data/test_phase9_audit_tables_schema_verification.py` (consumer-side schema verification)

**Depends on:** T-A.1.

**Repurposed per Codex R1 Critical #1 fix:** migration landed atomically in T-A.1. This task verifies sub-bundle C dependencies before C builds repo + service tasks.

**Acceptance criteria:**
- `hypothesis_status_history` (7 columns) + 2 indexes per spec §3.4.
- Partial-unique index `ux_hypothesis_status_history_current` (one row per hypothesis with effective_to IS NULL).
- `account_equity_snapshots` (8 columns) + 2 indexes per spec §3.5.
- Unique index `(snapshot_date, source)` per spec §3.5.
- FK CASCADE on `hypothesis_status_history.hypothesis_id` → `hypothesis_registry(id)`.

- [ ] **Step 1: Write schema-verification tests (PRAGMA-driven)**
- [ ] **Step 2: Verify tests pass against the v17 schema landed by T-A.1**
- [ ] **Step 3: Commit**

```bash
git add tests/data/test_phase9_audit_tables_schema_verification.py
git commit -m "test(data): Task C.0 — verify hypothesis_status_history + account_equity_snapshots schema from T-A.1"
```

### Task C.1: Verify hypothesis_status_history seed rows from sub-bundle A migration (read-only)

**Files:**
- Test: `tests/data/test_phase9_hypothesis_seed_verification.py`

**Depends on:** T-A.1 (migration seeded hypothesis_status_history rows from existing hypothesis_registry rows).

**Repurposed per Codex R1 Critical #1 fix:** migration seed rows landed in T-A.1. This task verifies the seed shape post-T-A.1.

**Acceptance criteria per spec §3.4.1 R3 Major #2:**
- Production DB has N hypotheses → post-migration, N rows exist in hypothesis_status_history with effective_to IS NULL.
- For each seed row: `effective_from` matches `strftime('%Y-%m-%dT00:00:00.000', hypothesis_registry.created_at)` (date-only normalized to millisecond form).
- `status` matches `hypothesis_registry.status`.
- `change_reason IS NULL` (seed).
- `recorded_at` is a valid millisecond-precision ISO datetime.
- Discriminating test: insert a NEW hypothesis_registry row post-migration; assert it does NOT auto-get a history row (seed runs ONCE; service helper handles post-migration insertions).

- [ ] **Step 1: Write seed-verification tests**
- [ ] **Step 2: Verify pass**
- [ ] **Step 3: Commit**

```bash
git add tests/data/test_phase9_hypothesis_seed_verification.py
git commit -m "test(data): Task C.1 — verify hypothesis_status_history seed rows from T-A.1 migration"
```

### Task C.2: account_equity_snapshots repo + service + CLI

**Files:**
- Modify: `swing/data/models.py` (add `AccountEquitySnapshot` dataclass)
- Create: `swing/data/repos/account_equity_snapshots.py`
- Create: `swing/trades/account_equity_snapshots.py`
- Modify: `swing/cli.py` (add `swing account snapshot`)
- Test: `tests/data/test_account_equity_snapshots_repo.py`
- Test: `tests/trades/test_account_equity_snapshots_service.py`
- Test: `tests/cli/test_account_snapshot_cli.py`

**Depends on:** T-C.0.

**Acceptance criteria per spec §3.5 + §4.4 + §A.9 + §A.10:**
- `upsert_snapshot` uses SELECT-then-UPDATE-or-INSERT (NOT REPLACE per CLAUDE.md gotcha); PK preserved across re-record for same `(snapshot_date, source)`.
- `get_latest_snapshot_on_or_before` implements source-ladder precedence (`schwab_api` > `tos_csv` > `manual`).
- `with_provenance=True` returns (winner, suppressed_rows) per spec §3.5 R4 Minor #3.
- Service `record_snapshot`: snapshot_date defaults to `last_completed_session(now())` per §A.9.
- Service rejects caller-held transaction.
- CLI `swing account snapshot --equity 1300` records row.
- CLI `swing account snapshot --equity 1400 --date 2026-04-01` upserts past-date row + flags back-recorded if gap > 7 days.
- Server-stamping for recorded_at + recorded_by per §A.10.

(Step-by-step abbreviated.)

- [ ] **Step 1-15: TDD cycles for repo + service + CLI**
- [ ] **Step 16: Discriminating Saturday-night test (date defaults to Friday's session)**
- [ ] **Step 17: Commit**

```bash
git add swing/data/models.py swing/data/repos/account_equity_snapshots.py swing/trades/account_equity_snapshots.py swing/cli.py tests/
git commit -m "feat(trades): Task C.2 — account_equity_snapshots repo + service + CLI"
```

### Task C.3: hypothesis_status_history repo

**Files:**
- Modify: `swing/data/models.py` (add `HypothesisStatusHistory` dataclass)
- Create: `swing/data/repos/hypothesis_status_history.py`
- Test: `tests/data/test_hypothesis_status_history_repo.py`

**Depends on:** T-C.1.

**Acceptance criteria:**
- `insert_history`, `update_close_open_interval`, `get_current_status`, `list_history_for_hypothesis`, `list_all_history` per file map.
- Repo functions do NOT commit (Finviz I1 lesson).
- Dataclass validator rejects invalid enum values; rejects effective_to < effective_from when both non-NULL.

(Step-by-step abbreviated.)

- [ ] **Step 1-7: TDD cycle**
- [ ] **Step 8: Commit**

```bash
git add swing/data/models.py swing/data/repos/hypothesis_status_history.py tests/data/test_hypothesis_status_history_repo.py
git commit -m "feat(data): Task C.3 — hypothesis_status_history dataclass + repo"
```

### Task C.4: hypothesis status audit service + CLI rewire + DELETE legacy repo function

**Files:**
- Create: `swing/trades/hypothesis.py` (new service module)
- Modify: `swing/data/repos/hypothesis.py` (DELETE `update_hypothesis_status` function)
- Modify: `swing/cli.py` (rewire `swing hypothesis update` to call new service)
- Test: `tests/trades/test_hypothesis_service.py`

**Depends on:** T-C.3.

**Acceptance criteria per §A.1 + spec §3.4.1:**
- New service: `update_hypothesis_status_with_audit(conn, *, hypothesis_id, new_status, change_reason)` returns `Literal["transition", "noop_identity"]`.
- Rejects caller-held transaction.
- 8-step transactional sequence per §A.1 (BEGIN IMMEDIATE → read current status under lock → if same, ROLLBACK + return "noop_identity" → close prior interval → INSERT new history row → UPDATE hypothesis_registry → COMMIT).
- Discriminating regression test T-C.4.1: synthetic exception between history INSERT and registry UPDATE → assert BOTH rolled back.
- T-C.4.2: legacy `swing.data.repos.hypothesis.update_hypothesis_status` raises `ImportError` (function deleted).
- T-C.4.3: CLI `swing hypothesis update` invokes new service; identity transition prints INFO "already <status>" (not ERROR).
- T-C.4.4: stale-status race: two CLI invocations attempting active → paused; second sees current status as `paused` under the lock + correctly handles (NoOpIdentityTransition or different transition path).

(Step-by-step abbreviated.)

- [ ] **Step 1-12: TDD cycles**
- [ ] **Step 13: Verify deleted repo function raises ImportError**
- [ ] **Step 14: Commit**

```bash
git add swing/trades/hypothesis.py swing/data/repos/hypothesis.py swing/cli.py tests/trades/test_hypothesis_service.py
git commit -m "feat(trades): Task C.4 — hypothesis status audit service + DELETE legacy repo function + CLI rewire"
```

### Task C.5: E2E integration test for sub-bundle C

**Files:**
- Test: extend `tests/integration/test_phase9_end_to_end.py` (C scope)

**Depends on:** T-C.4.

**Acceptance criteria:**
- Record account snapshot via CLI; verify row + back-recorded flag for >7-day gap.
- Update hypothesis status via CLI; verify history row + closed prior interval.
- Issue identity transition; verify NoOpIdentityTransition + no new history row.

(Step-by-step abbreviated.)

- [ ] **Step 1-5: E2E TDD cycle**
- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_phase9_end_to_end.py
git commit -m "test(integration): Task C.5 — E2E for sub-bundle C"
```

---

## §G — Sub-bundle D: sector/industry tamper hardening

**Goal:** Route-layer rejection at `/trades/entry` POST mirroring chart_pattern hardening; emit `sector_tamper` discrepancy in ad-hoc reconciliation_run on rejection.

**Sub-bundle D surfaces 3 operator-witnessed gates:**
- S1: Form sector matches cached → entry proceeds normally (regression-clean).
- S2: Form sector mismatches cached → reject + HTMX error fragment; ad-hoc reconciliation_run row created (`source='system_audit'`, `state='completed'`); `sector_tamper` discrepancy row persisted.
- S3: Form industry mismatches → same behavior.

### Task D.0: Existing chart_pattern hardening recon

**Files:**
- None (recon-only).

**Depends on:** T-B.6 (reconciliation_runs available for emission).

**Acceptance criteria:**
- Implementer reads + summarizes chart_pattern hardening at `swing/web/routes/trades.py` (commits `117dc97` + `2b9d6f3`) before writing tamper extension.

- [ ] **Step 1: Grep + read existing implementation**

```bash
git log --oneline -- swing/web/routes/trades.py | head -20
git show 117dc97 -- swing/web/routes/trades.py
git show 2b9d6f3 -- swing/web/routes/trades.py
```

- [ ] **Step 2: Document chart_pattern pattern in plan note**

### Task D.1: Route-layer sector/industry rejection + tamper test fixtures

**Files:**
- Modify: `swing/web/routes/trades.py` (extend entry POST handler with sector + industry checks mirroring chart_pattern hardening)
- Test: `tests/web/test_trade_entry_sector_industry_tamper.py`

**Depends on:** T-D.0.

**Acceptance criteria per §A.4 + spec §7:**
- After form parse + cached candidate lookup: compare form-submitted sector + industry against cached.
- Match → proceed.
- Mismatch on either field → reject POST with HTMX-friendly error fragment (mirror chart_pattern hardening response shape).
- TWO discrete tests: sector mismatch + industry mismatch (separate code paths).

(Step-by-step abbreviated; tests pin the chart_pattern test pattern as the template.)

- [ ] **Step 1-10: TDD cycle**
- [ ] **Step 11: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_trade_entry_sector_industry_tamper.py
git commit -m "feat(web): Task D.1 — sector/industry tamper rejection at /trades/entry POST"
```

### Task D.2: Ad-hoc reconciliation_run emission on rejection

**Files:**
- Modify: `swing/web/routes/trades.py` (on tamper rejection, emit `sector_tamper` discrepancy in ad-hoc reconciliation_run with `source='system_audit'`)
- Test: extend `tests/web/test_trade_entry_sector_industry_tamper.py`

**Depends on:** T-D.1.

**Acceptance criteria per §A.4.1:**
- On tamper rejection: open a SEPARATE transaction (NOT the rejected entry's transaction); INSERT reconciliation_run row (`source='system_audit'`, `state='completed'`, `period_start=period_end=action_session_for_run(now())`); INSERT `sector_tamper` discrepancy (expected/actual JSON per spec §3.3.1, material_to_review=0 V1).
- Audit row persists even though entry POST is rejected.
- Discriminating test T-D.2.5: assert that after rejection, reconciliation_runs has +1 row AND reconciliation_discrepancies has +1 row of type `sector_tamper`.

(Step-by-step abbreviated.)

- [ ] **Step 1-8: TDD cycle**
- [ ] **Step 9: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_trade_entry_sector_industry_tamper.py
git commit -m "feat(web): Task D.2 — emit sector_tamper discrepancy in ad-hoc system_audit reconciliation_run on rejection"
```

### Task D.3: E2E integration test for sub-bundle D

**Files:**
- Test: extend `tests/integration/test_phase9_end_to_end.py` (D scope)

**Depends on:** T-D.2.

**Acceptance criteria:**
- Operator submits tamper-attempt entry; verify HTMX rejection + audit row persists.
- Subsequent `swing journal discrepancy list` shows the sector_tamper row.

- [ ] **Step 1-3: TDD cycle**
- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_phase9_end_to_end.py
git commit -m "test(integration): Task D.3 — E2E for tamper hardening"
```

---

## §H — Sub-bundle E: final polish + Phase 10 hand-off prep

**Goal:** Combined E2E happy path; CLAUDE.md gotcha promotion candidates; orchestrator-context lesson capture; Phase 10 hand-off notes in return report.

### Task E.0: Combined E2E happy path

**Files:**
- Test: `tests/integration/test_phase9_full_happy_path.py`

**Depends on:** T-A.7, T-B.8, T-C.5, T-D.3.

**Acceptance criteria:**
- Single test runs the operator's natural workflow: (1) edit policy via CLI → (2) reconcile TOS CSV → (3) resolve a discrepancy → (4) record account snapshot → (5) update hypothesis status → (6) issue tamper-attempt → audit row appears → (7) `list_unresolved_material_for_active_trades` returns expected count.
- All 7 surfaces work in one connection across one test.

- [ ] **Step 1-3: TDD cycle**
- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_phase9_full_happy_path.py
git commit -m "test(integration): Task E.0 — Phase 9 combined E2E happy path"
```

### Task E.1: CLAUDE.md gotcha promotion candidates

**Files:**
- Modify: `CLAUDE.md` (add candidate gotchas — implementer-side proposals; orchestrator triage at integration merge)

**Depends on:** T-E.0.

**Candidate gotchas:**
- **risk_policy supersession 6-step sequence — predecessor's is_active=0 BEFORE successor INSERT** to free the `ux_risk_policy_active` partial unique index slot. Failure mode anticipated; landed correctly per spec §4.1.
- **TOML divergence detection at startup**: cfg.account.risk_equity_floor diverging from risk_policy.is_active=1's value logs WARNING + overrides in-memory cfg; TOML file NEVER auto-written (audit-trail integrity).
- **Account equity snapshot source-ladder precedence**: `schwab_api > tos_csv > manual` for same `snapshot_date`. UI rendering must show suppressed-row provenance per spec §3.5 R4 Minor #3.

- [ ] **Step 1: Draft candidates inline as plan comments**
- [ ] **Step 2: Orchestrator triages at integration merge (NOT inline)**
- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): Task E.1 — Phase 9 candidate gotcha promotions (orchestrator-triage at merge)"
```

### Task E.2: Phase 10 hand-off + final ruff sweep

**Files:**
- Modify: `docs/phase3e-todo.md` (add Phase 9 lessons-banked + Phase 10 hand-off note per spec §11)
- Run: `ruff check swing/ --statistics` (baseline 18; verify Phase 9 introduces NO new violations)

**Depends on:** T-E.1.

**Acceptance criteria:**
- Baseline ruff count unchanged at 18 (E501 only).
- Phase 10 hand-off note enumerates: risk_policy read-precedence (at-trade-time vs live-time per spec §11.1); reconciliation discrepancy badge surfaces (Phase 10 territory per spec §11.2); hypothesis status history queries for Phase 10 (spec §11.3); account_equity_snapshots resolution for `live_capital_denominator_dollars` (spec §11.4).

- [ ] **Step 1: Update phase3e-todo.md**
- [ ] **Step 2: Run ruff sweep + verify no new violations**
- [ ] **Step 3: Commit**

```bash
git add docs/phase3e-todo.md
git commit -m "docs(phase9): Task E.2 — Phase 9 lessons-banked + Phase 10 hand-off note + ruff sweep clean"
```

---

## §I — Watch items for executing-plans dispatch

Cross-bundle invariants the executing-plans dispatcher (and Codex review chain) must verify:

1. **Migration filename = `0017_*`**, NOT `0016_*` (per §A.0). Grep test: `ls swing/data/migrations/0017_*.sql | wc -l` == 1.
2. **EXPECTED_SCHEMA_VERSION = 17** after T-A.1; `cat swing/data/db.py | grep "EXPECTED_SCHEMA_VERSION = 17"` returns 1 match.
3. **Zero `INSERT OR REPLACE` introduced anywhere in Phase 9 paths.** Grep: `grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/` should remain at zero matches post-Phase-9.
4. **Single-write-path discipline for hypothesis status:** `swing/data/repos/hypothesis.py` DOES NOT contain `update_hypothesis_status` after T-C.4. Discriminating ImportError test.
5. **No `conn.commit()` calls in new repo files.** Grep: `grep -rn "conn.commit()" swing/data/repos/` returns zero matches (per Finviz I1 lesson; existing repos confirmed clean pre-Phase-9).
6. **Service-layer transaction-ownership contract:** new services in `swing/trades/{risk_policy.py, reconciliation.py, account_equity_snapshots.py, hypothesis.py}` ALL reject caller-held transactions at entry (Phase 8 R4 M1 lesson). Discriminating tests verify `CallerHeldTransactionError`.
7. **`__post_init__` validators present on all new dataclasses** in `swing/data/models.py` (per dispatch brief §0.3 #4). Discriminating tests verify NaN/inf rejection + enum validation.
8. **Session-anchor read/write predicate alignment** (per dispatch brief §0.3 #8 + CLAUDE.md gotcha): `swing account snapshot` writer uses `last_completed_session(now())`; Phase 10 dispatcher must inherit. Discriminating test T-A.9-mirror (Saturday-night invocation defaults to Friday's date).
9. **HTMX form lessons preserved** at Phase 5 config route extension (T-A.5): HX-Request propagation + HX-Redirect success-path response (operator-witnessed browser verification gate is BINDING).
10. **Server-stamping discipline** for all audit timestamps per §A.10. No hidden inputs added to forms (per dispatch brief §0.3 #9).
11. **Composition-surface enumeration via `^def` grep, not memory-enumerate** (per dispatch brief §0.3 #1 + Bundle 2 V2 lesson + Bundle 3 V2 lesson). Each new service has its call sites enumerated via:

```bash
grep -rn "^def supersede_active_policy\|^def run_tos_reconciliation\|^def update_hypothesis_status_with_audit\|^def record_snapshot" swing/
```

The function-definition grep MUST return exactly one match per function (the definition itself). Brief reviewer cross-references against any call sites mentioned in plan text.

12. **Migration-runner discipline (backup gate + foreign_keys=OFF + executescript wrapper)** verified by T-A.2 regression tests.
13. **Cross-bundle FK ordering**: reconciliation_discrepancies CREATE TABLE comes AFTER reconciliation_runs in the 0017 file. hypothesis_status_history CREATE TABLE comes AFTER hypothesis_registry exists (migration 0008 — guaranteed since 0008 < 0017).

---

## §J — Cross-references + grep verifications + test count summary

### §J.1 Spec coverage matrix

| Spec section | Plan task(s) |
|---|---|
| §3.1 risk_policy (28 cols + indexes + seed) | T-A.1, T-A.3 |
| §3.1.1 per-row policy stamping | T-A.7 (trades + review_log) |
| §3.1.3 cfg-mirror cascade + TOML divergence | T-A.5 |
| §3.1.4 versioning model rationale | T-A.3 (dataclass + repo design) |
| §3.2 reconciliation_runs (17 cols + indexes) | T-B.0, T-B.1 |
| §3.3 reconciliation_discrepancies (18 cols + indexes) | T-B.0, T-B.1 |
| §3.3.1 expected_value/actual_value JSON shapes per type | T-B.3, T-B.4, T-B.5, T-B.6 |
| §3.3.2 material_to_review classification + override | T-B.6 (MATERIAL_BY_TYPE), T-B.7 (CLI override) |
| §3.3.3 single-transaction emit | T-B.6 (service contract) |
| §3.4 hypothesis_status_history (7 cols + indexes) | T-C.0, T-C.3 |
| §3.4.1 append-on-status-update service | T-C.4 |
| §3.5 account_equity_snapshots (8 cols + indexes) | T-C.0, T-C.2 |
| §3.6 ALTER TABLE additions | T-A.1 |
| §3.7 capture-need cross-check 15/15 | implicit via spec coverage |
| §4.1 risk_policy supersession 6-step | T-A.4 |
| §4.2 reconciliation cadence + CLI | T-B.6, T-B.7 |
| §4.3 hypothesis_status_history append cadence | T-C.4 |
| §4.4 account_equity_snapshots manual cadence | T-C.2 |
| §5.1 Phase 7 state-machine query-side reopen | T-B.1 (canonical queries) |
| §5.2 Phase 6 review_log frozen aggregates (no change) | (no-op confirmed) |
| §5.3 Phase 8 daily_management read-only | (no-op confirmed) |
| §6.1 close_price_mismatch | T-B.3 |
| §6.2 stop_mismatch | T-B.4 |
| §6.3 position_qty_mismatch | T-B.5 |
| §6.4 cash_movement_mismatch | T-B.6 |
| §6.5 tos_import.py refactor | T-B.2 |
| §7 sector/industry tamper hardening | T-D.0, T-D.1, T-D.2 |
| §8 Schwab API boundary (V2; source enum reserved) | T-A.1 (CHECK enum includes 'schwab_api'), T-C.2 (same) |
| §9.1 migration filename + version bump | §A.0 + T-A.1 |
| §9.2 mechanic per table | T-A.1 (no rebuilds) |
| §9.3 migration runner discipline | T-A.2 |
| §9.4 in-flight production data | §A.7 |
| §9.5 cfg seed transition | T-A.4 (seed_initial_policy) + T-A.5 |
| §10.1 reconciliation period_end resolution (defer Schwab) | accepted; V1 ships TOS-CSV path only |
| §10.2 sector_tamper hard-gate trigger (defer V2) | accepted; V1 advisory; flag in return report |
| §10.3 retention (retain forever) | accepted |
| §10.4 hypothesis seed effective_from = created_at | accepted; T-C.1 |
| §10.5 CLI surface per-field | accepted; T-A.6 |
| §10.6 reconciliation period_end CLI flag default | accepted; T-B.7 |
| §11 Phase 10 hand-off | T-E.2 |

**Coverage:** 39/39 spec sections + open-questions disposition complete.

### §J.2 Grep-verification commands (executing-plans dispatch acceptance gate)

```bash
# 1. Migration filename correct
test -f swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql
test ! -f swing/data/migrations/0016_phase9_risk_policy_and_reconciliation.sql

# 2. Schema version bumped
grep -E "^EXPECTED_SCHEMA_VERSION = 17$" swing/data/db.py

# 3. No INSERT OR REPLACE introduced
test $(grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/ | wc -l) -eq 0

# 4. Legacy hypothesis repo function deleted
! grep -n "^def update_hypothesis_status" swing/data/repos/hypothesis.py

# 5. No conn.commit() in new repos
test $(grep -rn "conn.commit()" swing/data/repos/risk_policy.py swing/data/repos/reconciliation.py swing/data/repos/account_equity_snapshots.py swing/data/repos/hypothesis_status_history.py | wc -l) -eq 0

# 6. Service modules reject caller-held tx
grep -rn "CallerHeldTransactionError\|in_transaction" swing/trades/risk_policy.py swing/trades/reconciliation.py swing/trades/account_equity_snapshots.py swing/trades/hypothesis.py | wc -l  # > 4

# 7. __post_init__ validators present
grep -rn "__post_init__" swing/data/models.py | wc -l  # >= 5 (RiskPolicy, ReconciliationRun, ReconciliationDiscrepancy, HypothesisStatusHistory, AccountEquitySnapshot)

# 8. Function definition enumeration (composition-surface lesson)
grep -rn "^def supersede_active_policy" swing/  # 1 match in swing/trades/risk_policy.py
grep -rn "^def run_tos_reconciliation" swing/   # 1 match in swing/trades/reconciliation.py
grep -rn "^def update_hypothesis_status_with_audit" swing/  # 1 match in swing/trades/hypothesis.py
grep -rn "^def record_snapshot" swing/  # 1 match in swing/trades/account_equity_snapshots.py

# 9. Ruff baseline unchanged
ruff check swing/ --statistics | grep "Found 18"
```

### §J.3 Test count projection

Per §A.6, biased high; ranges per sub-bundle:

| Sub-bundle | New tests (low) | New tests (high) |
|---|---|---|
| A — risk_policy foundation | 40 | 65 |
| B — reconciliation depth | 80 | 120 |
| C — hypothesis + account_equity | 50 | 75 |
| D — tamper hardening | 15 | 25 |
| E — polish + E2E | 15 | 35 |
| **Total** | **200** | **320** |

Baseline 2328 → expected end-state 2528–2648 fast tests post-Phase-9-ship.

### §J.4 References

- Spec: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`.
- Brief: `docs/phase9-writing-plans-dispatch-brief.md`.
- Phase 8 plan precedent: `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`.
- Phase 7 migration runner hotfix: commit `283d4fa` (executescript discipline + foreign_keys=OFF wrapper).
- Phase 8 SQLite REPLACE gotcha: CLAUDE.md (2026-05-06).
- Phase 8 `record_event_log` service-layer transaction discipline: CLAUDE.md (2026-05-07).
- Phase 8 R3→R4 `in_transaction` anti-pattern: CLAUDE.md (2026-05-07).
- Phase 5 HTMX failure surfaces (HX-Request + HX-Redirect): CLAUDE.md (2026-05-02).
- Bundle 2+3 V2 watch items: `docs/phase3e-todo.md` (2026-05-11).
- Existing chart_pattern hardening for §7 mirror pattern: commits `117dc97` + `2b9d6f3`.

---

*End of plan. Adversarial Codex review pending.*
