# Phase 8 — Daily_Management + MFE/MAE Precision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land schema v15 → v16 migration that creates `daily_management_records` (single-table-with-discriminator: `daily_snapshot` + `event_log`) + ADDs `trades.planned_target_R`; implement repo + service + pipeline-step + web POST + dashboard tile + briefing-section extension so that every nightly pipeline run emits a per-open-trade `daily_approximate` snapshot, operator can emit event_log entries from the per-trade detail page, and the dashboard + nightly briefing surface `maturity_stage` + `trail_MA_eligibility_flag` for operator-actionable trail-MA gating.

**Architecture:** Schema-first slice extends Phase 7 baseline with one new table + one new column; new `swing/data/repos/daily_management.py` owns CRUD with SELECT-then-UPDATE-or-INSERT discipline (NOT SQLite REPLACE — CLAUDE.md gotcha 2026-05-06); new `swing/trades/daily_management.py` hosts pure helpers + the snapshot-compute service consuming `swing/data/ohlcv_archive.py`; new `_step_daily_management` lands AFTER `_step_evaluate` in `swing/pipeline/runner.py`; web POST `/trades/{id}/daily-management/event` extends `swing/web/routes/trades.py`; dashboard tile renders Phase 7 trades-row authoritative live values + Phase 8 snapshot-authoritative time-series fields per the §5.6 read-precedence ladder; nightly `briefing.md` / `briefing.html` gain a "Daily Management Snapshot" subsection per spec §7.4 LOCKED.

**Tech Stack:** SQLite (migration **0016** — see §A.0; PRAGMA foreign_keys=OFF runner discipline inherited from Phase 7 hotfix `283d4fa`); pytest; FastAPI + Starlette `TemplateResponse`; HTMX (HX-Request propagation + HX-Redirect per Phase 5/6 lessons); Jinja2 templates extending `base.html.j2`; existing `swing/data/ohlcv_archive.py:read_or_fetch_archive` for daily_approximate MFE/MAE compute.

---

## §A — Resolved-during-planning items (empirical-audit findings)

These are findings from the §0 empirical audit that diverge from spec wording or surface implementation contracts that the spec deliberately deferred to writing-plans dispatch (per Phase 8 spec §4.4 "writing-plans-decides scope" + brief §2.5 + §1.1). The plan implements the reconciled positions below; they DO NOT contradict the spec's locked decisions in §3-§7 — they refine implementation paths and surface a small set of empirical-finding-driven design choices.

### §A.0 Migration filename + schema-version collision (Codex R1 Critical #1; binding ALL filename references)

**Spec §8.1 said:** "Migration `0015_phase8_daily_management.sql`."

**Empirical finding:** the repo already has `swing/data/migrations/0015_finviz_api_calls.sql` (Finviz API V1 shipped 2026-05-06, merge `002338a`); `swing/data/db.py` has `EXPECTED_SCHEMA_VERSION = 15`. The Phase 8 spec was drafted in parallel with the Finviz V1 ship and missed the migration-number bump. If Phase 8 ships at `0015_*`, the runner (`run_migrations`) parses numeric prefixes and applies only those with `current < version <= apply_ceiling`; a production DB at v15 would skip Phase 8 entirely while code expects v16.

**Resolution (BINDING for ALL plan tasks):** Phase 8 migration filename is **`0016_phase8_daily_management.sql`**. The schema bump remains v15 → v16 per spec §8.1's binding intent. The test filename is **`tests/data/test_migration_0016.py`**. Backup file `swing-pre-phase8-migration-<ISO>.db` (filename anchor independent of migration-number prefix). All task-spec text below has been verified to use `0016` consistently (per §J grep at writing-plans dispatch). The remaining `0015` references in this §A.0 are intentional historical citations — quoting the spec's outdated filename (lines 19, 25) and the legitimately-shipped `0015_finviz_api_calls.sql` (line 21).

**Spec ambiguity disposition:** ACCEPT-WITH-RATIONALE per brief §1.1; flagged in return-report orchestrator-triage section. Spec §8.1's literal `0015_*` filename is corrected at writing-plans dispatch time without amending the spec; spec semantics ("migration filename matches its schema-version target; bump v15 → v16") preserved.

### §A.1 Phase 7 service-call-inside-transaction empirical finding (CRITICAL — affects T3.2)

**Spec §4.4 explicit gate:** "Phase 7 service-call-inside-transaction precondition: Phase 7's shipped `update_stop_with_event` and `state_transition` services either accept-or-reject being called inside an outer transaction. Writing-plans dispatch time MUST verify (a) the shipped behavior."

**Verification:**

1. **`swing/trades/stop_adjust.py:update_stop_with_event`** at [swing/trades/stop_adjust.py:86-121](../../swing/trades/stop_adjust.py#L86-L121) opens its own `with conn:` block at line 105. Calling this from inside an outer `BEGIN IMMEDIATE` would commit prematurely (Python sqlite3's `with conn:` calls `conn.commit()` on exit which commits ALL pending work back to BEGIN, NOT just the inner block — there is no per-savepoint commit at the python sqlite3 level).
2. **`swing/data/repos/trades.py:update_stop_with_event`** at [swing/data/repos/trades.py:186-214](../../swing/data/repos/trades.py#L186-L214) does NOT open its own `with conn:`. Operates inside caller's transaction. UPDATEs `trades.current_stop` + INSERTs the `trade_events.event_type='stop_adjust'` row.
3. **`swing/trades/state.py:state_transition`** at [swing/trades/state.py:123-163](../../swing/trades/state.py#L123-L163) does NOT open its own `with conn:`. Docstring explicitly says "atomic: state UPDATE + trade_events audit row in same transaction (caller's `with conn:`)."

**Resolution (binding for T3.2; Codex R1 M4 + R2 M3 + R2 M4 refined):** Phase 8's `record_event_log` in `swing/trades/daily_management.py` calls the **repo-level** `swing/data/repos/trades.py:update_stop_with_event(conn, ...)` directly, NOT the service-level `swing/trades/stop_adjust.py:update_stop_with_event(conn, ...)`. The `linked_trade_event_id` is resolved via TRADE-SCOPED max-id-after-insert pattern: capture `pre_max_event_id = SELECT COALESCE(MAX(id), 0) FROM trade_events WHERE trade_id = ?` BEFORE the repo call; capture `new_max = SELECT MAX(id) FROM trade_events WHERE trade_id = ?` AFTER; assert `new_max > pre_max_event_id`; `linked_trade_event_id = new_max`. This is robust against same-txn prior inserts AND robust against other-trade event ids that happen to be higher (the GLOBAL-MAX approach would falsely trip when another trade's event_id is higher). `last_insert_rowid()` is NOT used — it can return zero or a stale rowid when the repo-level function early-returns (which it does for no-op stops, though we now reject no-op stops at the validator boundary as well — defense in depth). The entered→managing transition is invoked separately via `state_transition(conn, ...)`. This preserves the §4.4 single-transaction contract WITHOUT modifying Phase 7's shipped service-layer (no Phase 7 carve-out).

**Asymmetry note:** the service-layer `swing/trades/stop_adjust.py:update_stop_with_event` is the canonical entry point for OPERATOR DIRECT stop-adjust workflows (CLI/web stop-adjust route). Phase 8's `record_event_log` is a DIFFERENT entry point (operator emitting an event_log that incidentally includes a stop change). The repo-level call is appropriate for Phase 8's nested-transaction context; the service-level call remains the right pick for any future direct-stop-adjust caller. T3.2's docstring documents this explicitly so a future maintainer doesn't "consolidate" the two call paths.

**Discriminating regression test (T3.2):** call `record_event_log` with `stop_changed=1, new_stop=X` against a trade with `state='entered'`; assert all four side-effects landed in a single transaction (event_log row inserted; trade_events stop_adjust row inserted; trades.current_stop = X; trades.state = 'managing'); assert `linked_trade_event_id` on the event_log row equals the `trade_events.id` of the stop_adjust row; assert that injecting an exception between the INSERTs rolls BOTH back (deferred-mode `with conn:` atomicity per Codex R4 m1). **Pre-fix expectation (without the repo-level switch):** the inner `with conn:` at line 105 of stop_adjust.py would have committed before the event_log INSERT, so a synthetic exception in the event_log INSERT step would leave a stop_adjust trade_events row + mutated `trades.current_stop` PERSISTED. **Post-fix expectation:** rollback wipes BOTH. This is the discriminating distinction; T3.2 documents the literal test fixture.

### §A.2 CLI scope decision (per Phase 8 spec §10.3 "writing-plans-decides")

**Locked:** V1 ships **WEB-ONLY** for event_log emission. CLI `swing trade event-log` deferred to V2 follow-up.

**Rationale:**

1. **Phase 6 precedent.** Phase 6 review surface shipped web-only-V1; CLI parity for review_log was added separately later. Same precedent.
2. **Operator's primary surface.** The operator workflow is "open dashboard → click per-trade detail → emit event_log." CLI is escape valve, not primary.
3. **Scope budget.** CLI surface adds ~1-2 hours implementation + tests; deferral keeps Phase 8 dispatch lean (~14 tasks vs ~16) and aligns with the Phase 8 spec's "metric stability is binding constraint, no ship-velocity pressure" framing.
4. **Schema-already-supports CLI.** The spec is not blocking V2 CLI — schema, repo, and service layers are CLI-agnostic. A future V2 brief can wire `swing trade event-log` against the existing service entry point in 1 task.

**Deferred:** brief §2.6 open-questions list (return report) flags "V2 CLI follow-up" so the orchestrator can queue it.

### §A.3 Snapshot-compute service module placement

**Decision:** snapshot-compute + tier-upgrade + record_event_log helpers ALL live in `swing/trades/daily_management.py` (single module), NOT split into `swing/services/daily_management.py`. Rationale:

1. **No `swing/services/` directory exists** in the current tree (verified: `swing/trades/`, `swing/data/`, `swing/web/` are the canonical service-layer namespaces; introducing `swing/services/` would be a structural drift unwarranted by Phase 8 alone).
2. **Phase 6 + Phase 7 precedent.** `swing/trades/review.py` (Phase 6) + `swing/trades/state.py` + `swing/trades/origin.py` + `swing/trades/derived_metrics.py` (Phase 7) all live under `swing/trades/`. Phase 8 follows.
3. **Brief §2.1 wording was illustrative.** Brief said "new `swing/services/daily_management.py`"; this plan uses `swing/trades/daily_management.py` per established convention. The functional contract is unchanged.

### §A.4 Snapshot-row-CASCADE-on-pipeline_run delete (spec §4.3 ON DELETE SET NULL)

Spec §4.3 specifies `pipeline_run_id` FK has `ON DELETE SET NULL`. Plan T1.0 implements verbatim. Discriminating regression test in T1.0 verifies: insert snapshot with `pipeline_run_id=N`; DELETE pipeline_runs WHERE id=N; assert snapshot row survives + `pipeline_run_id IS NULL`. Adversarial review may flag this as subtle: if the FK had ON DELETE CASCADE the snapshot would be wiped (data loss); if NO ACTION the DELETE would fail. Plan documents the SET NULL choice as binding per spec.

### §A.5 Schema-version backup file naming convention (per Phase 7 lesson)

Phase 7's migration runner names backup files `swing-pre-phase7-migration-<ISO>.db` (verified at [swing/data/db.py:175](../../swing/data/db.py#L175)). Phase 8 migration's backup is `swing-pre-phase8-migration-<ISO>.db`. T1.1 includes a discriminating regression test verifying the file pattern (NOT just "a file was created").

### §A.6 Active-snapshot partial-unique-index predicate

Spec §3.3 specifies the partial-unique-index predicate as `WHERE record_type = 'daily_snapshot' AND is_superseded = 0`. T1.0 SQL implements verbatim. Discriminating regression test: attempt to insert TWO non-superseded daily_snapshot rows with same `(trade_id, data_asof_session)`; assert `IntegrityError: UNIQUE constraint failed`. Alongside: assert insert TWO superseded rows + ONE non-superseded row succeeds (the predicate excludes superseded rows from the constraint). Alongside: assert TWO event_log rows for same `(trade_id, data_asof_session)` succeeds (the predicate excludes event_log rows from the constraint).

### §A.7 Test count projection bias

Per brief §1.2 + §2.4, Phase 8 plan projects **+30 to +60 fast tests** (range, NOT a single number) per discriminating-test discipline. Per-task projections in §J biased high; subtotal is +43 baseline → executing-plans dispatch acceptance criteria use the RANGE not the point estimate.

### §A.8 In-flight production data state

Verified at HEAD `1441109` via Phase 7 spec + production-DB state per CLAUDE.md: 4 trades total. 1 closed+reviewed (VIR), 3 open (DHC + CC + YOU; states `entered` / `managing` / `partial_exited`). The first pipeline run after migration emits `daily_approximate` snapshots for each open trade. Per spec §8.5, no historical back-fill (gap-flagged policy). T8.0 (operator-witnessed verification) covers a single-run-emit-3-snapshots happy path against this data.

---

## §B — File map

### Files to CREATE

| Path | Responsibility |
|---|---|
| `swing/data/migrations/0016_phase8_daily_management.sql` | Schema bump v15 → v16: `ALTER TABLE trades ADD COLUMN planned_target_R REAL` + CREATE TABLE `daily_management_records` (42 columns per spec §3.1) + 4 indexes per spec §3.3 + `UPDATE schema_version SET version = 16`. |
| `swing/data/repos/daily_management.py` | Public API. **TWO record_type concepts** — DO NOT confuse: (1) `record_type='daily_snapshot'` rows are pipeline-step-emitted; UPSERT keyed on `(trade_id, data_asof_session, mfe_mae_precision_level)`; carry full position-state. (2) `record_type='event_log'` rows are operator-discretionary (web POST); NOT subject to UPSERT (each emission is its own row); position-state OPTIONAL. Public API: `insert_snapshot(conn, *, trade_id, snapshot_fields) -> int` (pure INSERT; caller manages transaction); `insert_event_log(conn, *, trade_id, event_log_fields) -> int` (pure INSERT); `select_active_snapshot(conn, *, trade_id, data_asof_session) -> DailyManagementRecord | None` (returns `is_superseded = 0` row, or None); `select_history(conn, *, trade_id, data_asof_session=None) -> list[DailyManagementRecord]` (full chain incl. superseded; ordered by created_at ASC, mfe_mae_precision_level ASC); `upsert_snapshot(conn, *, trade_id, snapshot_fields) -> int` (SELECT-then-UPDATE-or-INSERT against the active row only; same-tier reflow updates in place; raises `SupersededRowImmutableException` if validator detects write attempt against a superseded row); `tier_upgrade_snapshot(conn, *, trade_id, data_asof_session, new_precision_level, snapshot_fields) -> int` (6-step transactional sequence per spec §3.3); `list_open_position_active_snapshots(conn) -> list[DailyManagementRecord]` (drives §7.1 dashboard tile); `list_for_trade_timeline(conn, *, trade_id, include_superseded=False) -> list[DailyManagementRecord]` (drives §7.2 timeline). |
| `swing/trades/daily_management.py` | Public API + service entry-points. Pure helpers: `compute_maturity_stage(open_MFE_R_to_date) -> str | None`; `compute_trail_MA_eligibility_flag(*, maturity_stage, trail_MA_candidate_price, current_stop) -> int | None`; `compute_open_R_effective(*, current_price, current_avg_cost, current_size, planned_risk_budget_dollars) -> float`; `compute_position_capital_utilization(*, current_size, current_price, denominator_dollars) -> float`; `compute_position_portfolio_heat(*, current_avg_cost, current_stop, current_size) -> float`; `compute_running_extrema_R(ohlcv_df, *, anchor_session, asof_session, entry_price, initial_stop) -> tuple[float, float]` (returns `(open_MFE_R_to_date, open_MAE_R_to_date)`; both non-negative; mirrors v1.2 §8.6 daily_approximate formulas). Service entry-points: `compute_daily_approximate_snapshot(conn, *, trade_id, asof_session, run_now, ohlcv_archive_dir, archive_history_days, pipeline_run_id, capital_floor_dollars, trail_MA_period_days_default) -> SnapshotFields | None` (returns None if archive read returns None for the ticker — operator-actionable signal that ticker is delisted/invalid). `record_event_log(conn, *, trade_id, req: EventLogRequest) -> int` (single-transaction contract per §A.1; calls repo-level `update_stop_with_event` if `req.stop_changed=1`; rejects no-op stops at validator boundary; captures `linked_trade_event_id` via TRADE-SCOPED max-id-after-insert pattern — see §A.1 + §I; INSERTs event_log row; calls `state_transition(conn, ...)` if trade.state == 'entered'; raises `ValidationException` on missing required fields). `tier_upgrade_to_intraday(...)` STUBBED FOR V2 (raises `NotImplementedError("V2: gated on Schwab API Phase B")`); the schema and validator path are exercised by T3.1 via a synthetic-tier-upgrade integration test. Constants: `DAILY_MGMT_PRECISION_LEVELS: tuple[str, str, str] = ("daily_approximate", "intraday_estimated", "intraday_exact")`; `DAILY_MGMT_PRECISION_RANK: dict[str, int] = {...}`; `DAILY_MGMT_MATURITY_STAGES: tuple[str, str, str] = ("pre_+1.5R", "+1.5R_to_+2R", ">=+2R_trail_eligible")`; `DAILY_MGMT_ACTION_TAKEN_VALUES: tuple[str, ...] = ("hold", "trim", "exit", "stop", "move_stop", "no_action")`; `DAILY_MGMT_THESIS_STATUSES: tuple[str, str, str] = ("intact", "weakening", "invalidated")`; `DAILY_MGMT_THESIS_UNRECORDED_SENTINEL: str = "unrecorded"`; `DAILY_MGMT_EMOTIONAL_STATES` (mirrors Phase 7 entry); `DAILY_MGMT_VOLUME_BEHAVIORS: tuple[str, ...] = ("confirming", "neutral", "distribution", "fading")`; `DAILY_MGMT_RELATIVE_STRENGTH_STATUSES: tuple[str, ...] = ("improving", "flat", "weakening")`. Validator: `validate_for_operation(req, *, op: Literal["snapshot_emit", "event_log_emit", "tier_upgrade"]) -> list[str]` (returns missing-field names per spec §3.1.1 OPERATION_REQUIRED_FIELDS). Exception classes: `class SupersededRowImmutableException(Exception)`; `class ValidationException(Exception)`; `class TierOrderingError(Exception)`. |
| `swing/web/templates/partials/daily_management_event_form.html.j2` | Event-log form fragment. `<form>`-rooted (NOT `<tr>`-rooted; Phase 6 makeFragment lesson). Includes `hx-headers='{"HX-Request": "true"}'` + `hx-post="/trades/{{ vm.trade_id }}/daily-management/event"` + `hx-target="#daily-mgmt-status"` per Phase 5/6 lessons. |
| `swing/web/templates/partials/daily_management_tile.html.j2` | Per-open-position dashboard tile per spec §7.1. ONE row per open trade. Renders ticker / state badge (from trades.state) / current_price / current_stop (from trades.current_stop — live, NOT snapshot stale copy per §5.6) / open_R_effective / open_MFE_R_to_date / open_MAE_R_to_date / maturity_stage badge / trail_MA_eligibility_flag badge (visible only when TRUE) / position_capital_utilization_pct (with PROVISIONAL fallback marker) / position_portfolio_heat_contribution_dollars / planned_target_R (from trades.planned_target_R — render "—" when NULL). |
| `swing/web/templates/partials/daily_management_timeline.html.j2` | Per-trade timeline drill-down per spec §7.2. ONE row per `management_record_id`. Ordered by `(review_date ASC, created_at ASC, management_record_id ASC)`. Renders `daily_snapshot` rows + `event_log` rows interleaved chronologically with distinct badges. Default predicate `is_superseded = 0`; toggle button shows superseded chain. |
| `tests/data/test_migration_0016.py` | Round-trip test for: schema_version → 16; daily_management_records table created with all 42 columns; trades.planned_target_R column exists; 4 indexes created; partial-unique-index predicates correct; FK CASCADE/SET NULL behavior correct; migration is idempotent (running twice raises clean error per Phase 7 lesson). |
| `tests/data/test_migration_0016_runner_discipline.py` | Migration runner discipline tests: backup gate fires only on `current_version == 15 AND target >= 16`; backup file pattern `swing-pre-phase8-migration-*.db`; foreign_keys=OFF discipline preserved; executescript() partial-failure rollback. |
| `tests/data/test_daily_management_repo.py` | Repo-layer tests: insert_snapshot + insert_event_log + select_active_snapshot + select_history + upsert_snapshot SELECT-then-UPDATE-or-INSERT pattern (NOT REPLACE — verifies `management_record_id` preserved across reflow) + tier_upgrade_snapshot 6-step sequence + SupersededRowImmutableException + list_for_trade_timeline ordering. |
| `tests/trades/test_daily_management_helpers.py` | Pure-helper tests: compute_maturity_stage parameterized boundary table + compute_trail_MA_eligibility_flag truth-table + compute_open_R_effective + compute_running_extrema_R against synthetic OHLCV DataFrame + validate_for_operation per-op required-field set + thesis_status read-side resolution rule for OPEN-vs-CLOSED + sentinel handling. |
| `tests/trades/test_daily_management_service.py` | Service-layer tests: compute_daily_approximate_snapshot end-to-end against synthetic archive; record_event_log single-transaction atomicity (the §A.1 discriminating test); tier_upgrade_to_intraday raises NotImplementedError; tier_upgrade integration test via direct repo call (synthetic 3-tier sequence). |
| `tests/pipeline/test_daily_management_step.py` | `_step_daily_management` tests: idempotent same-day re-run; gap-flagged no-back-fill; closed-trade skip; entered→managing transition on first snapshot; pipeline_run_id linkage. |
| `tests/web/test_daily_management_event_route.py` | Web POST `/trades/{id}/daily-management/event` route tests: HX-Request propagation; HX-Redirect on success; ValidationException → 422 + form re-render; route registered in app routes (Phase 6 R5 I3 lesson — verify HX-Redirect target resolves, not just header propagation). |
| `tests/web/test_daily_management_tile.py` | Dashboard tile tests: live current_stop reads from trades-row (NOT stale snapshot copy); maturity_stage badge renders; trail_MA_eligibility_flag badge visible only when TRUE; planned_target_R "—" placeholder when NULL; PROVISIONAL fallback marker on capital_utilization. |
| `tests/web/test_daily_management_timeline.py` | Timeline tests: chronological ordering with deterministic tie-break; same-day multiple event_log rows render distinctly; gap rendering for missed days; superseded toggle behavior. |
| `tests/integration/test_phase8_pipeline_walkthrough.py` | End-to-end: full pipeline run emits snapshots for 3 open trades + 0 for closed/reviewed trades; second same-day run UPSERTS in place (preserves `management_record_id`); operator-emitted event_log writes the row + (if stop_changed) writes the linked trade_events row + (if entered→managing trigger) emits the state-transition trade_events row. |

### Files to MODIFY

| Path | Reason |
|---|---|
| `swing/data/models.py` | Add `DailyManagementRecord` dataclass (42 fields mirroring schema column-types per spec §3.1). Add `planned_target_R: float | None` field to `Trade` dataclass (default `None`). |
| `swing/data/repos/trades.py` | Extend `_TRADE_SELECT_COLS` + `_row_to_trade` to include `planned_target_R`. Extend `insert_trade_with_event` to accept `planned_target_R: float | None = None` kwarg + add to INSERT column list. **NO modifications to `update_stop_with_event`** (Phase 7 service-call-inside-transaction precondition resolved by repo-level call from Phase 8 — see §A.1). |
| `swing/data/db.py` | Update `EXPECTED_SCHEMA_VERSION = 16`. Backup file naming branch (per spec §8.2): if migrating to 16, backup filename `swing-pre-phase8-migration-{iso}.db`. Inherit existing `foreign_keys=OFF` discipline (Phase 7 hotfix `283d4fa`) without modification. |
| `swing/pipeline/runner.py` | Add `_step_daily_management(*, lease, run_now, eval_run_id, archive_history_days, ohlcv_archive_dir, capital_floor_dollars=7500.0, trail_MA_period_days_default=21)` function. Lands AFTER `_step_evaluate` (uses `eval_run_id` as `pipeline_run_id` FK target). Uses `lease.fenced_write()` per Phase 7 + finviz-API integration pattern. Wraps body in `try/except` for non-fatal cadence-step semantics (snapshot failure does NOT abort the rest of the pipeline; logged warning per Phase 6 cadence-step lesson). |
| `swing/web/routes/trades.py` | Add `POST /trades/{trade_id}/daily-management/event` handler. Validates request body via Pydantic model `EventLogRequest`; calls `record_event_log` service; returns 204 + `HX-Redirect: /trades/{trade_id}` on success per Phase 5/6 lesson; 422 + form re-render on `ValidationException`. Add `GET /trades/{trade_id}` route if not yet existing (verify routes table; Phase 6 R5 I3 lesson). |
| `swing/web/view_models/dashboard.py` | Add `daily_management_tiles: list[DailyManagementTileVM]` field to `DashboardVM`. Each tile inherits Phase 7 trades-row authoritative live values + Phase 8 snapshot-authoritative time-series fields per §5.6 ladder. Build via `list_open_position_active_snapshots(conn)` + JOIN trades-row in Python. |
| `swing/web/view_models/trades.py` | Add `DailyManagementTileVM` dataclass (12 fields per spec §7.1 composition list). Add `DailyManagementTimelineVM` dataclass for per-trade detail page (rows: list of timeline-row dataclasses). Add `EventLogFormVM` dataclass for the event-log form. ALL THREE inherit existing 5 base-layout fields with safe defaults (per Phase 6 base-layout 5-VM rule). |
| `swing/web/templates/dashboard.html.j2` | Include `partials/daily_management_tile.html.j2` per open-position iteration. |
| `swing/web/templates/trade_detail.html.j2` (or equivalent per-trade detail page; if it doesn't exist yet, create a minimal one) | Embed `partials/daily_management_event_form.html.j2` + `partials/daily_management_timeline.html.j2`. |

### Files NOT in scope (read-only consumed)

- `swing/data/ohlcv_archive.py` — Phase 8 service consumes `read_or_fetch_archive` read-only.
- `swing/data/repos/ohlcv_archive.py` — read-only.
- `swing/trades/state.py` — Phase 7 read-only (Phase 8 calls `state_transition(conn, ...)` for entered→managing).
- `swing/data/repos/trades.py:update_stop_with_event` (repo-level) — Phase 7 read-only (Phase 8 calls it for the event_log stop-change path per §A.1).
- `swing/evaluation/dates.py` — Phase 8 imports `last_completed_session(now)` only (canonical session-anchor helper per Phase 6 §A.8 lesson + Phase 8 spec §10.4).

---

## §C — Migration 0016 SQL (canonical reference)

The exact SQL for `swing/data/migrations/0016_phase8_daily_management.sql` (Task 1.0 implements verbatim — verify against §B file map and spec §3.1 + §3.3 + §3.4 + §8.1; filename bumped from spec §8.1's literal `0015` per §A.0):

```sql
-- Migration 0016: Phase 8 Daily_Management + MFE/MAE Precision Surface
--
-- 1. ALTER trades to add planned_target_R (single nullable column; no rebuild).
-- 2. CREATE TABLE daily_management_records (single-table-with-discriminator
--    per spec §3.2; 42 columns per spec §3.1).
-- 3. Indexes per spec §3.3 (4 indexes — 2 partial-unique + 2 lookup).
-- 4. Bump schema_version to 16.
--
-- Lesson inheritance:
--   - foreign_keys=OFF runner discipline (Phase 7 hotfix 283d4fa) — applies
--     globally; this migration does NOT trigger any rebuild but the runner
--     still toggles OFF/ON around executescript() per the binding discipline.
--   - executescript() partial-failure rollback wrapper (Phase 7 Sub-A R1 M3) —
--     in the runner; T1.1 has the discriminating test.
--   - Backup gate fires only on current_version == 15 AND target >= 16 (Phase 7
--     Sub-A code-review I1) — runner-level; backup filename
--     swing-pre-phase8-migration-<ISO>.db (§A.5).

-- ----- 1. ADD COLUMN planned_target_R on trades -----

ALTER TABLE trades ADD COLUMN planned_target_R REAL
    CHECK (planned_target_R IS NULL OR planned_target_R > 0);

-- ----- 2. CREATE TABLE daily_management_records -----

CREATE TABLE daily_management_records (
    -- Metadata (10 columns):
    management_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL
        REFERENCES trades(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL
        CHECK (record_type IN ('daily_snapshot', 'event_log')),
    review_date TEXT NOT NULL,         -- ISO date YYYY-MM-DD; validator enforces format
    data_asof_session TEXT NOT NULL,   -- ISO date YYYY-MM-DD; for daily_snapshot must equal review_date
    created_at TEXT NOT NULL,          -- naive UTC ISO datetime; validator enforces
    mfe_mae_precision_level TEXT NOT NULL
        CHECK (mfe_mae_precision_level IN ('daily_approximate','intraday_estimated','intraday_exact')),
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    is_superseded INTEGER NOT NULL DEFAULT 0
        CHECK (is_superseded IN (0,1)),
    superseded_by_record_id INTEGER
        REFERENCES daily_management_records(management_record_id) ON DELETE SET NULL,

    -- Position-state snapshot fields (14 columns; nullable on schema, validator-required for snapshot_emit):
    current_price REAL CHECK (current_price IS NULL OR current_price > 0),
    current_stop REAL CHECK (current_stop IS NULL OR current_stop > 0),
    current_size REAL CHECK (current_size IS NULL OR current_size >= 0),
    current_avg_cost REAL CHECK (current_avg_cost IS NULL OR current_avg_cost > 0),
    open_R_effective REAL,
    open_MFE_R_to_date REAL CHECK (open_MFE_R_to_date IS NULL OR open_MFE_R_to_date >= 0),
    open_MAE_R_to_date REAL CHECK (open_MAE_R_to_date IS NULL OR open_MAE_R_to_date >= 0),
    intraday_high REAL CHECK (intraday_high IS NULL OR intraday_high > 0),
    intraday_low REAL CHECK (intraday_low IS NULL OR intraday_low > 0),
    position_capital_utilization_pct REAL,
    position_capital_denominator_dollars REAL,
    position_portfolio_heat_contribution_dollars REAL
        CHECK (position_portfolio_heat_contribution_dollars IS NULL
               OR position_portfolio_heat_contribution_dollars >= 0),
    maturity_stage TEXT
        CHECK (maturity_stage IS NULL OR maturity_stage IN
               ('pre_+1.5R','+1.5R_to_+2R','>=+2R_trail_eligible')),
    trail_MA_candidate_price REAL
        CHECK (trail_MA_candidate_price IS NULL OR trail_MA_candidate_price > 0),

    -- Trail-MA period stamp (per-row stamp per spec §6.6):
    trail_MA_period_days INTEGER
        CHECK (trail_MA_period_days IS NULL OR trail_MA_period_days > 0),

    -- Trail-MA eligibility cached derivation:
    trail_MA_eligibility_flag INTEGER
        CHECK (trail_MA_eligibility_flag IS NULL OR trail_MA_eligibility_flag IN (0,1)),

    -- Operator-input fields (15 columns; required only for event_log per validator):
    thesis_status TEXT
        CHECK (thesis_status IS NULL OR thesis_status IN ('intact','weakening','invalidated')),
    prior_stop REAL CHECK (prior_stop IS NULL OR prior_stop > 0),
    new_stop REAL CHECK (new_stop IS NULL OR new_stop > 0),
    linked_trade_event_id INTEGER
        REFERENCES trade_events(id) ON DELETE SET NULL,
    stop_changed INTEGER
        CHECK (stop_changed IS NULL OR stop_changed IN (0,1)),
    stop_change_reason TEXT,
    volume_behavior TEXT
        CHECK (volume_behavior IS NULL OR volume_behavior IN
               ('confirming','neutral','distribution','fading')),
    relative_strength_status TEXT
        CHECK (relative_strength_status IS NULL OR relative_strength_status IN
               ('improving','flat','weakening')),
    market_regime_change INTEGER
        CHECK (market_regime_change IS NULL OR market_regime_change IN (0,1)),
    sector_condition_change INTEGER
        CHECK (sector_condition_change IS NULL OR sector_condition_change IN (0,1)),
    news_or_event_update TEXT,
    action_taken TEXT
        CHECK (action_taken IS NULL OR action_taken IN
               ('hold','trim','exit','stop','move_stop','no_action')),
    action_reason TEXT,
    emotional_state TEXT,             -- JSON-list-text; validation in service layer
    rule_violation_suspected INTEGER
        CHECK (rule_violation_suspected IS NULL OR rule_violation_suspected IN (0,1)),
    management_notes TEXT
);

-- ----- 3. Indexes -----

-- Active-snapshot uniqueness (predicate excludes superseded rows + event_log rows):
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_active_per_session
    ON daily_management_records (trade_id, data_asof_session)
    WHERE record_type = 'daily_snapshot' AND is_superseded = 0;

-- Per-precision uniqueness (idempotency key for tier-aware writes; covers all snapshot rows including superseded):
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_precision_per_session
    ON daily_management_records (trade_id, data_asof_session, mfe_mae_precision_level)
    WHERE record_type = 'daily_snapshot';

-- Timeline reads (per spec §7.2; cardinality at our scale ≈ 2K rows/year — index trivial):
CREATE INDEX ix_daily_mgmt_trade_review
    ON daily_management_records (trade_id, review_date);

-- Pipeline-run traceability:
CREATE INDEX ix_daily_mgmt_pipeline_run
    ON daily_management_records (pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL;

-- ----- 4. Bump schema_version -----

UPDATE schema_version SET version = 16;
```

---

## §D — Vocabulary constants (verbatim from spec §3.1 + Phase 7 entry vocab)

The exact constants for `swing/trades/daily_management.py`:

```python
# Per spec §3.1 + §3.1.1:
DAILY_MGMT_PRECISION_LEVELS: tuple[str, ...] = (
    "daily_approximate", "intraday_estimated", "intraday_exact",
)
DAILY_MGMT_PRECISION_RANK: dict[str, int] = {
    "daily_approximate": 1,
    "intraday_estimated": 2,
    "intraday_exact": 3,
}
DAILY_MGMT_MATURITY_STAGES: tuple[str, ...] = (
    "pre_+1.5R", "+1.5R_to_+2R", ">=+2R_trail_eligible",
)
DAILY_MGMT_ACTION_TAKEN_VALUES: tuple[str, ...] = (
    "hold", "trim", "exit", "stop", "move_stop", "no_action",
)
DAILY_MGMT_THESIS_STATUSES: tuple[str, ...] = (
    "intact", "weakening", "invalidated",
)
# Sentinel — NOT a CHECK enum value; render-side ONLY for closed/reviewed trades
# with no event_log thesis update:
DAILY_MGMT_THESIS_UNRECORDED_SENTINEL: str = "unrecorded"
DAILY_MGMT_VOLUME_BEHAVIORS: tuple[str, ...] = (
    "confirming", "neutral", "distribution", "fading",
)
DAILY_MGMT_RELATIVE_STRENGTH_STATUSES: tuple[str, ...] = (
    "improving", "flat", "weakening",
)
# Mirrors swing/trades/entry.py emotional_state_pre_trade vocab (Phase 7):
DAILY_MGMT_EMOTIONAL_STATES: tuple[str, ...] = (
    "calm", "confident", "anxious", "fomo", "revenge",
    "hopeful", "doubtful", "distracted",
)

# OPERATION_REQUIRED_FIELDS per spec §3.1.1 (binding):
OPERATION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "snapshot_emit": (
        "current_price", "current_stop", "current_size", "current_avg_cost",
        "open_R_effective", "open_MFE_R_to_date", "open_MAE_R_to_date",
        "intraday_high", "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage", "trail_MA_eligibility_flag",
        # trail_MA_candidate_price + trail_MA_period_days are required UNLESS
        # archive history insufficient — cross-field validator handles coherently
        # (both NULL together, never one without the other).
    ),
    "event_log_emit": (
        "stop_changed", "action_taken", "rule_violation_suspected",
        "emotional_state",
    ),
    "tier_upgrade": (
        # Same as snapshot_emit:
        "current_price", "current_stop", "current_size", "current_avg_cost",
        "open_R_effective", "open_MFE_R_to_date", "open_MAE_R_to_date",
        "intraday_high", "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage", "trail_MA_eligibility_flag",
    ),
}
```

Conditional required fields (validator-enforced beyond OPERATION_REQUIRED_FIELDS):

- `event_log_emit` with `stop_changed=1`: `stop_change_reason` (non-empty) + `prior_stop` + `new_stop` (`linked_trade_event_id` populated by service).
- `event_log_emit` with `action_taken NOT IN ('no_action', NULL)`: `action_reason` (non-empty).
- `tier_upgrade`: `mfe_mae_precision_level` STRICTLY higher than predecessor's per `DAILY_MGMT_PRECISION_RANK`. Same-tier or lower → `TierOrderingError`.
- All ops: `trail_MA_candidate_price` and `trail_MA_period_days` are coherently both-NULL or both-non-NULL.

---

## §E — Pure-helper formula reference (verbatim from spec §1.5 + §6.6)

```python
from datetime import date

def compute_maturity_stage(open_MFE_R_to_date: float | None) -> str | None:
    """Spec §1.5 + §3.1 thresholds. NULL passes through (insufficient data)."""
    if open_MFE_R_to_date is None:
        return None
    if open_MFE_R_to_date < 1.5:
        return "pre_+1.5R"
    if open_MFE_R_to_date < 2.0:
        return "+1.5R_to_+2R"
    return ">=+2R_trail_eligible"


def compute_trail_MA_eligibility_flag(
    *, maturity_stage: str | None,
    trail_MA_candidate_price: float | None,
    current_stop: float | None,
) -> int | None:
    """Spec §3.1: 1 IFF maturity_stage='>=+2R_trail_eligible' AND
    trail_MA_candidate_price IS NOT NULL AND current_stop < trail_MA_candidate_price."""
    if maturity_stage is None or trail_MA_candidate_price is None or current_stop is None:
        return None
    if maturity_stage != ">=+2R_trail_eligible":
        return 0
    if current_stop < trail_MA_candidate_price:
        return 1
    return 0


def compute_open_R_effective(
    *, current_price: float, current_avg_cost: float, current_size: float,
    planned_risk_budget_dollars: float,
) -> float:
    """Spec §2 risk-denominator + §3.1 column definition.

    open_R_effective = (current_price - current_avg_cost) * current_size
                      / planned_risk_budget_dollars

    Caller resolves planned_risk_budget_dollars via Phase 7's pre-trade-locked
    derivation: (entry_price - initial_stop) * initial_shares.
    """
    if planned_risk_budget_dollars == 0:
        # Should be impossible per Phase 7 invariants; defensive.
        raise ValueError("planned_risk_budget_dollars cannot be zero")
    return (current_price - current_avg_cost) * current_size / planned_risk_budget_dollars


def compute_position_capital_utilization(
    *, current_size: float, current_price: float, denominator_dollars: float,
) -> float:
    """Spec §3.1 + §10.5: V1 denominator = capital_floor_constant_dollars (7500.0).

    Returned as a proportion (0.0 to 1.0+; values >1 indicate over-utilization
    against the floor, which is the operator-actionable signal).
    """
    if denominator_dollars <= 0:
        raise ValueError("denominator_dollars must be > 0")
    return (current_size * current_price) / denominator_dollars


def compute_position_portfolio_heat(
    *, current_avg_cost: float, current_stop: float, current_size: float,
) -> float:
    """Spec §3.1: max(0, (current_avg_cost - current_stop) * current_size).

    Non-negative magnitude per the spec convention (slippage convention).
    """
    return max(0.0, (current_avg_cost - current_stop) * current_size)


def compute_running_extrema_R(
    ohlcv_df,  # pandas.DataFrame indexed by date with 'High', 'Low' columns
    *, anchor_session: date, asof_session: date,
    entry_price: float, initial_stop: float,
) -> tuple[float, float]:
    """Spec §1.5 daily_approximate formulas. Returns (MFE_R, MAE_R) over
    sessions [anchor_session, asof_session] inclusive, both non-negative.

    MFE_R = max((High - entry_price) / risk_per_share) over window; min 0.
    MAE_R = max((entry_price - Low)  / risk_per_share) over window; min 0
            (NON-NEGATIVE per spec §2 adverse-positive convention).

    Both default to 0.0 when the window is empty.
    """
    risk_per_share = entry_price - initial_stop
    if risk_per_share == 0:
        raise ValueError("risk_per_share cannot be zero")
    mask = (ohlcv_df.index.date >= anchor_session) & (ohlcv_df.index.date <= asof_session)
    window = ohlcv_df.loc[mask]
    if window.empty:
        return 0.0, 0.0
    mfe = max(0.0, float((window["High"].max() - entry_price) / risk_per_share))
    mae = max(0.0, float((entry_price - window["Low"].min()) / risk_per_share))
    return mfe, mae
```

Invariant binding in T2.0 + T3.0 tests:
- `open_MFE_R_to_date >= 0` for all valid inputs (CHECK constraint already enforces).
- `open_MAE_R_to_date >= 0` (sign convention — non-negative).
- `compute_running_extrema_R` returns `(0.0, 0.0)` on empty window.

---

## §F — Watch-item mitigation table (brief §5)

For each pre-designated watch item, the plan task that pre-empts it:

| # | Watch item | Pre-empted in task |
|---|---|---|
| 1 | Spec compliance per §3-§7 | All tasks; cross-checked in §K self-review |
| 2 | Phase 7 schema-rebuild constraint preservation | T1.0 — ALTER TABLE ADD COLUMN ONLY (no rebuild); plan-task explicitly notes future-rebuild flag |
| 3 | SQLite INSERT OR REPLACE prohibition | T2.3 + T3.1 + T4.0 — SELECT-then-UPDATE-or-INSERT pattern; T2.3 has discriminating regression test that REPLACE would destroy `management_record_id` |
| 4 | `is_superseded` flag pattern | T2.3 + T3.1 — repo + service implement 6-step transactional sequence; SupersededRowImmutableException in validator; predecessor capture by exact PK |
| 5 | Per-row policy-versioned value stamping | T1.0 — `trail_MA_period_days INTEGER` per-row stamp; T3.0 writes 21 (V1 default) at snapshot-emit |
| 6 | Datetime impedance + lexicographic ordering | T1.0 SQL + validator (in T3.0 service) — naive-only TEXT datetime columns; spec §8.4 binding |
| 7 | Discriminating-test specifications | EVERY task §J — discriminating tests have EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value |
| 8 | Test count projection biased high | §J subtotal +43 in range +30 to +60 |
| 9 | PRAGMA test-fixture discipline | T1.0 + T1.1 — every fixture sets `foreign_keys=ON` |
| 10 | Backup-gate condition | T1.1 — discriminating test fires backup ONLY on `current_version == 15 AND target >= 16` |
| 11 | State-machine integration via JOIN | T5.1 dashboard tile reads via JOIN; NO modifications to Phase 7 state machine |
| 12 | Phase 10 §6.1 capture-need completeness | §C migration SQL covers all 10 §6.1 fields per spec §3.5 cross-check |
| 13 | CLI scope decision documented | §A.2 + return-report — V1 web-only; V2 CLI deferred |
| 14 | Subject-only grep regex with `-E` flag | T0 + every task §J verify-command block |
| 15 | Convergent-chain expectation | Return report §"Codex review history" |
| 16 | Plan-task acceptance criteria binding format | Every §J task has ACCEPTANCE block + VERIFY COMMAND(S) block |
| 17 | Operator-actionability test | T5.1 — trail_MA_eligibility_flag is operator action prompt; maturity_stage badge transitions are workflow attention |
| 18 | Brief-premise empirical verification | §A — all 8 audit findings empirical against current code |

---

## §G — Snapshot-row idempotent-UPSERT pseudocode (per spec §4.2 + §3.3)

The exact SELECT-then-UPDATE-or-INSERT pattern for `swing/data/repos/daily_management.py:upsert_snapshot` (T2.3 implements verbatim):

```python
def upsert_snapshot(
    conn: sqlite3.Connection, *,
    trade_id: int,
    snapshot_fields: dict,  # full position-state per OPERATION_REQUIRED_FIELDS["snapshot_emit"]
) -> int:
    """SELECT-then-UPDATE-or-INSERT against the active row only (spec §4.2).

    Same-tier reflow updates the active row in place (preserves
    management_record_id + is_superseded + superseded_by_record_id chain).
    Higher-tier write goes through tier_upgrade_snapshot, not this path.

    Caller manages the outer deferred-mode transaction (NOT BEGIN IMMEDIATE per Codex R3 M2).

    Raises:
        SupersededRowImmutableException — if a superseded row exists for the
            same (trade_id, data_asof_session, mfe_mae_precision_level) and
            no active row exists. Means tier-upgrade has already occurred at
            this tier; same-tier reflow is meaningless.
    """
    # Step 1: validate before write
    missing = validate_for_operation(snapshot_fields, op="snapshot_emit")
    if missing:
        raise ValidationException(f"missing required fields: {missing}")

    # Step 2: lookup active row at this tier
    cur = conn.execute(
        """
        SELECT management_record_id FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND mfe_mae_precision_level = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 0
        """,
        (trade_id, snapshot_fields["data_asof_session"],
         snapshot_fields["mfe_mae_precision_level"]),
    )
    row = cur.fetchone()
    if row is not None:
        existing_active_id = row[0]
        # Step 3: in-place UPDATE (preserves PK + chain)
        conn.execute(
            """
            UPDATE daily_management_records
            SET current_price = ?, current_stop = ?, current_size = ?,
                current_avg_cost = ?, open_R_effective = ?,
                open_MFE_R_to_date = ?, open_MAE_R_to_date = ?,
                intraday_high = ?, intraday_low = ?,
                position_capital_utilization_pct = ?,
                position_capital_denominator_dollars = ?,
                position_portfolio_heat_contribution_dollars = ?,
                maturity_stage = ?, trail_MA_candidate_price = ?,
                trail_MA_period_days = ?, trail_MA_eligibility_flag = ?,
                pipeline_run_id = ?, created_at = ?
            WHERE management_record_id = ?
            """,
            (...,  # snapshot_fields values in same column order
             existing_active_id),
        )
        return existing_active_id

    # Step 4: check for superseded-only state at this tier (validator gate)
    cur = conn.execute(
        """
        SELECT 1 FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND mfe_mae_precision_level = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 1
        LIMIT 1
        """,
        (trade_id, snapshot_fields["data_asof_session"],
         snapshot_fields["mfe_mae_precision_level"]),
    )
    if cur.fetchone() is not None:
        raise SupersededRowImmutableException(
            f"trade {trade_id} session {snapshot_fields['data_asof_session']} "
            f"tier {snapshot_fields['mfe_mae_precision_level']!r} has been "
            "tier-upgraded; same-tier reflow rejected."
        )

    # Step 5: fresh INSERT
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct, position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price, trail_MA_period_days,
            trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (...,),  # all fields per snapshot_fields
    )
    return int(cur.lastrowid)
```

---

## §H — Tier-upgrade 6-step transactional pseudocode (per spec §3.3)

The exact 6-step sequence for `swing/data/repos/daily_management.py:tier_upgrade_snapshot` (T2.3 implements verbatim):

```python
def tier_upgrade_snapshot(
    conn: sqlite3.Connection, *,
    trade_id: int,
    data_asof_session: str,
    new_precision_level: str,
    snapshot_fields: dict,
) -> int:
    """6-step transactional sequence per spec §3.3.

    Caller manages the outer deferred-mode `with conn:` transaction (Codex R3 M2).
    """
    # Step 0 (validator): new tier must rank strictly higher than predecessor's
    pred_row = conn.execute(
        """
        SELECT management_record_id, mfe_mae_precision_level
        FROM daily_management_records
        WHERE trade_id = ? AND data_asof_session = ?
          AND record_type = 'daily_snapshot' AND is_superseded = 0
        """,
        (trade_id, data_asof_session),
    ).fetchone()
    if pred_row is not None:
        pred_rank = DAILY_MGMT_PRECISION_RANK[pred_row[1]]
        new_rank = DAILY_MGMT_PRECISION_RANK[new_precision_level]
        if new_rank <= pred_rank:
            raise TierOrderingError(
                f"new tier {new_precision_level!r} (rank {new_rank}) must be "
                f"strictly higher than predecessor {pred_row[1]!r} (rank {pred_rank})"
            )

    # Step 1: BEGIN — caller's responsibility
    # Step 2: SELECT predecessor (already done above; capture exact PK)
    predecessor_id = pred_row[0] if pred_row is not None else None

    # Step 3: flag predecessor superseded BY EXACT PK
    if predecessor_id is not None:
        conn.execute(
            "UPDATE daily_management_records SET is_superseded = 1 "
            "WHERE management_record_id = ?",
            (predecessor_id,),
        )

    # Step 4: INSERT successor (the new higher-tier row)
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct, position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price, trail_MA_period_days,
            trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (...,),
    )
    successor_id = int(cur.lastrowid)

    # Step 5: UPDATE predecessor.superseded_by_record_id BY EXACT PK
    if predecessor_id is not None:
        conn.execute(
            "UPDATE daily_management_records "
            "SET superseded_by_record_id = ? "
            "WHERE management_record_id = ?",
            (successor_id, predecessor_id),
        )

    # Step 6: COMMIT — caller's responsibility
    return successor_id
```

T3.1 has the synthetic-3-tier discriminating regression test:

1. Seed: insert daily_approximate snapshot (predecessor_1; tier=1).
2. Tier-upgrade to intraday_estimated (successor_1 = predecessor_2; tier=2). Assert: predecessor_1 is_superseded=1, superseded_by=successor_1; successor_1 is_superseded=0; partial-unique-index has exactly 1 active row at (trade, session).
3. Tier-upgrade to intraday_exact (successor_2; tier=3). Assert: predecessor_2 is_superseded=1, superseded_by=successor_2; successor_2 is_superseded=0; chain reads daily_approximate → intraday_estimated → intraday_exact.
4. Attempt tier-upgrade BACK to daily_approximate. Assert: TierOrderingError raised; no row mutations.

---

## §I — `record_event_log` single-transaction pseudocode (per spec §4.4 + §A.1)

The exact contract for `swing/trades/daily_management.py:record_event_log` (T3.2 implements verbatim — empirical resolution per §A.1):

```python
def record_event_log(
    conn: sqlite3.Connection, *,
    trade_id: int,
    req: EventLogRequest,
) -> int:
    """Single-transaction contract per spec §4.4 + plan §A.1.

    All side-effects in one `with conn:` deferred-mode transaction (Codex R3 M2
    honest framing — Python sqlite3 default does NOT issue BEGIN IMMEDIATE; the
    deferred-mode `with conn:` block + repo-level state guard + WAL-mode
    serialization satisfy the atomicity intent). If ANY step fails, ALL roll
    back (no partial state where Phase 7 stop_adjust event exists without
    Phase 8 event_log row, OR vice versa).

    Returns:
        management_record_id of the inserted event_log row.

    Raises:
        ValidationException — missing required fields per §3.1.1.
        ValueError — Phase 7 service rejects (e.g., trade not found, terminal state).

    Concurrency contract (Codex R3 Major #2 + R4 m3 honest framing): Python
    sqlite3 in default isolation_level (deferred) does NOT auto-issue
    `BEGIN IMMEDIATE`. The `with conn:` block opens a deferred transaction on
    the first write and commits on success / rolls back on exception — both
    atomicity guarantees survive. Concurrent-writer protection on the DB is
    policed by `swing.pipeline.lease.fenced_write` at the pipeline boundary
    (lease ownership ensures only one pipeline run writes at a time) AND by
    the repo-level `update_stop_with_event` active-state guard at
    swing/data/repos/trades.py:201-204 (CHECK
    `state IN ('entered','managing','partial_exited')`) which rejects
    mid-flight writes after a state transition to `closed`/`reviewed`. WAL mode
    (`PRAGMA journal_mode=WAL` set at swing/data/db.py:354) permits one writer
    + many readers; web POST writers serialize via SQLite's WAL writer-lock
    (no FastAPI app-state lease in the current shipped surface — the writer-
    lock semantics + the active-state guard are the concurrency primitives).
    The atomicity contract is thus: `with conn:` deferred transaction +
    repo-level state guard + WAL writer-lock serialization. NO explicit
    `BEGIN IMMEDIATE` issued here.
    """
    from swing.data.repos.trades import (
        update_stop_with_event as repo_update_stop_with_event,
        get_trade,
    )
    from swing.trades.state import state_transition
    from swing.data.repos.daily_management import insert_event_log

    # Step 0 — validate
    missing = validate_for_operation(req, op="event_log_emit")
    if missing:
        raise ValidationException(f"missing required fields: {missing}")
    # Conditional validators:
    if req.stop_changed and (
        not req.stop_change_reason
        or not req.stop_change_reason.strip()
        or req.prior_stop is None
        or req.new_stop is None
    ):
        raise ValidationException(
            "stop_changed=1 requires prior_stop, new_stop, stop_change_reason"
        )
    if req.action_taken not in (None, "no_action") and (
        not req.action_reason or not req.action_reason.strip()
    ):
        raise ValidationException(
            "action_taken NOT IN ('no_action', None) requires action_reason"
        )

    # Step 1 — open deferred-mode transaction (Codex R3 M2 honest framing —
    # NOT BEGIN IMMEDIATE; see docstring concurrency contract above):
    with conn:  # `with conn:` enters deferred mode on first write
        # Re-read trade state for the entered→managing decision (per §5.2):
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise ValueError(f"trade {trade_id} not found")

        # Step 2 — Phase 7 stop-adjust (REPO-LEVEL per §A.1)
        linked_event_id: int | None = None
        if req.stop_changed:
            # Codex R1 Major #4 fix: repo-level update_stop_with_event returns
            # EARLY (no INSERT) when trade.current_stop == new_stop (verified at
            # swing/data/repos/trades.py line 198). If we then captured
            # last_insert_rowid() it would return a STALE prior row's id and
            # mis-link this event_log to an unrelated trade_events row. Reject
            # the no-op case at the validator boundary before invoking the repo
            # call so atomicity guarantee never fires for a stale id.
            if req.new_stop == trade.current_stop:
                raise ValidationException(
                    f"stop_changed=1 but new_stop={req.new_stop!r} equals "
                    f"current trades.current_stop={trade.current_stop!r}; "
                    "no-op stop change is invalid for event_log emission"
                )
            # Codex R4 Major #2 fix: stale-form guard. The web form pre-fills
            # `prior_stop` from a snapshot or trades-row reading PRIOR to the
            # POST. If another stop_adjust raced ahead between form-render and
            # POST, the form's prior_stop is STALE and persisting it would
            # diverge from Phase 7's trade_events.payload_json (which records
            # the actual at-time-of-mutation old_stop). Re-read inside the
            # transaction and reject mismatches:
            if req.prior_stop != trade.current_stop:
                raise ValidationException(
                    f"req.prior_stop={req.prior_stop!r} does not match "
                    f"current trades.current_stop={trade.current_stop!r} — "
                    "stale form (a stop_adjust raced between render and POST); "
                    "operator should reload + re-submit"
                )
            # Capture trade_events.id BEFORE invoking — we use the
            # TRADE-SCOPED max-id-after-insert technique (Codex R2 Major #3 fix:
            # globally-scoped MAX(id) compared against trade-scoped MAX(id)
            # would mis-fire when another trade has a higher prior event id).
            # Both queries scope to (trade_id = ?) so the comparison is
            # arithmetically valid:
            pre_max_event_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) FROM trade_events "
                "WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()[0]
            repo_update_stop_with_event(
                conn,
                trade_id=trade_id,
                new_stop=req.new_stop,
                event_ts=req.created_at,  # naive UTC ISO datetime
                rationale=req.stop_change_reason,
            )
            # Resolve the freshly-inserted trade_events row by querying for the
            # max id NEW since pre-call (same trade_id scope). Both queries
            # run inside the outer transaction so the max value is consistent.
            # repo-level update_stop_with_event ALWAYS inserts when new !=
            # current (the pre-validation above guarantees non-no-op path).
            new_max = conn.execute(
                "SELECT MAX(id) FROM trade_events WHERE trade_id = ?",
                (trade_id,),
            ).fetchone()[0]
            assert new_max is not None and new_max > pre_max_event_id, (
                f"expected trade_events INSERT for trade_id={trade_id!r} "
                f"but got new_max={new_max!r}, pre_max={pre_max_event_id!r} — "
                "repo-level update_stop_with_event did not insert as expected; "
                "investigate Phase 7 contract."
            )
            linked_event_id = int(new_max)

        # Step 3 — INSERT event_log row
        event_log_fields = {
            **req.to_dict(),
            "linked_trade_event_id": linked_event_id,
        }
        management_record_id = insert_event_log(
            conn, trade_id=trade_id, event_log_fields=event_log_fields,
        )

        # Step 4 — entered→managing transition (per §5.2)
        if trade.state == "entered":
            state_transition(
                conn,
                trade_id=trade_id,
                new_state="managing",
                event_ts=req.created_at,
                rationale="first_daily_management_record",
            )
        # COMMIT — `with conn:` exit auto-commits

    return management_record_id
```

T3.2 has SIX discriminating regression tests (4 originals + 1 added per Codex R1 M4 + 1 added per Codex R4 M2):

1. **Happy path — stop_changed=1, action_taken='move_stop':** all 4 side-effects landed (event_log row; trade_events stop_adjust row; trades.current_stop = req.new_stop; entered→managing if applicable). `linked_trade_event_id` on event_log row equals the trade_events.id of the stop_adjust row.
2. **Single-transaction rollback (the §A.1 discriminating test):** monkeypatch `insert_event_log` to raise after `repo_update_stop_with_event` already wrote. Assert: no event_log row in DB; trades.current_stop UNCHANGED from before the call (NOT the new value); no stop_adjust trade_events row (rolled back).
3. **`stop_changed=0` + `action_taken='no_action'`:** event_log row inserted with `linked_trade_event_id IS NULL`; no trade_events row; trades.current_stop UNCHANGED.
4. **Validation failure rolls back:** request with `stop_changed=1` but missing `new_stop` raises ValidationException; no row inserted.
5. **No-op stop change rejected at validator boundary (Codex R1 M4):** request with `stop_changed=1` but `new_stop == trades.current_stop` raises ValidationException with match-string "no-op stop change"; no event_log row inserted; trades.current_stop unchanged. Pre-empts the stale-`linked_trade_event_id` failure mode.
6. **Stale prior_stop rejected (Codex R4 M2):** request with `prior_stop != trades.current_stop` (re-read inside transaction) raises ValidationException with match-string "stale form"; no event_log row + no trade_events row inserted. Pre-empts audit-chain divergence between Phase 8 event_log's prior_stop and Phase 7 trade_events.payload_json's old_stop when a stop_adjust race occurs between web-form-render and POST.

---

## §J — Tasks

### Task 0: Setup (worktree + marker + baseline)

**Files:** none (verification + scaffolding only)

- [ ] **Step 1: Create isolated worktree per binding convention**

```bash
cd c:/Users/rwsmy/swing-trading
git worktree add -b phase8-daily-management ../swing-trading-phase8 main
cd ../swing-trading-phase8
```

Expected: new worktree at `c:/Users/rwsmy/swing-trading-phase8` on branch `phase8-daily-management` rooted at `main`.

- [ ] **Step 2: Drop the Codex-blocking marker file**

```bash
touch .copowers-subagent-active
```

Expected: marker file present at worktree root.

- [ ] **Step 3: Capture baseline test count + ruff baseline**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
```

Expected: ~1941 fast tests collected; ruff baseline 78 errors (per CLAUDE.md HEAD `1441109`). If divergence > ±5 tests OR ruff differs by > ±2, capture in return report.

- [ ] **Step 4: ERE grep for prior Phase 8 task commits (defense)**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z0-9-]+\): Task [0-9]+\.[0-9]+' --since="2026-05-06" main..HEAD
```

Expected: empty output. Non-empty → STOP and surface in return report.

ACCEPTANCE:
- Worktree created on branch `phase8-daily-management`.
- Marker file present.
- Baseline test count + ruff captured in return report.
- ERE grep returns empty.

VERIFY COMMAND(S):
```bash
git status   # in worktree
ls .copowers-subagent-active
```

---

### Task 1.0: Migration 0016 SQL + round-trip tests

**Files:**
- Create: `swing/data/migrations/0016_phase8_daily_management.sql`
- Create: `tests/data/test_migration_0016.py`
- Modify: `swing/data/db.py` (bump `EXPECTED_SCHEMA_VERSION = 16`; add backup-filename branch for v15→v16)

- [ ] **Step 1: Write the failing schema-version round-trip test**

```python
# tests/data/test_migration_0016.py
"""Migration 0016 round-trip + 42-column presence + indexes + CHECK + FK behavior."""
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")  # mirror production runtime
    yield conn
    conn.close()


def test_migration_0016_advances_schema_version(conn: sqlite3.Connection) -> None:
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 16


def test_migration_0016_creates_daily_management_records_table(
    conn: sqlite3.Connection,
) -> None:
    cols = {row[1] for row in conn.execute(
        "PRAGMA table_info(daily_management_records)").fetchall()}
    expected = {
        "management_record_id", "trade_id", "record_type", "review_date",
        "data_asof_session", "created_at", "mfe_mae_precision_level",
        "pipeline_run_id", "is_superseded", "superseded_by_record_id",
        "current_price", "current_stop", "current_size", "current_avg_cost",
        "open_R_effective", "open_MFE_R_to_date", "open_MAE_R_to_date",
        "intraday_high", "intraday_low",
        "position_capital_utilization_pct",
        "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage", "trail_MA_candidate_price",
        "trail_MA_period_days", "trail_MA_eligibility_flag",
        "thesis_status", "prior_stop", "new_stop",
        "linked_trade_event_id",
        "stop_changed", "stop_change_reason",
        "volume_behavior", "relative_strength_status",
        "market_regime_change", "sector_condition_change",
        "news_or_event_update", "action_taken", "action_reason",
        "emotional_state", "rule_violation_suspected", "management_notes",
    }
    assert expected == cols
    assert len(expected) == 42  # spec §3.1 binding count


def test_migration_0016_adds_planned_target_R_to_trades(
    conn: sqlite3.Connection,
) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()}
    assert "planned_target_R" in cols


def test_migration_0016_record_type_check_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    # Seed minimal trade row first to satisfy FK:
    _seed_minimal_trade(conn, trade_id=1)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
        conn.execute(
            "INSERT INTO daily_management_records "
            "(trade_id, record_type, review_date, data_asof_session, created_at, "
            " mfe_mae_precision_level) "
            "VALUES (1, 'INVALID', '2026-05-07', '2026-05-07', '2026-05-07T00:00:00', "
            " 'daily_approximate')"
        )


def test_migration_0016_active_snapshot_unique_index_predicate(
    conn: sqlite3.Connection,
) -> None:
    """Two non-superseded snapshot rows for same (trade, session) → IntegrityError."""
    _seed_minimal_trade(conn, trade_id=1)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 0)"
    )
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        conn.execute(
            "INSERT INTO daily_management_records "
            "(trade_id, record_type, review_date, data_asof_session, created_at, "
            " mfe_mae_precision_level, is_superseded) "
            "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
            "        '2026-05-07T00:00:00', 'intraday_estimated', 0)"
        )


def test_migration_0016_superseded_row_does_not_block_active(
    conn: sqlite3.Connection,
) -> None:
    """Predicate excludes superseded rows from constraint."""
    _seed_minimal_trade(conn, trade_id=1)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 1)"
    )
    # Should succeed: predicate excludes superseded row
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, is_superseded) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'intraday_estimated', 0)"
    )


def test_migration_0016_pipeline_run_id_set_null_on_delete(
    conn: sqlite3.Connection,
) -> None:
    """pipeline_run_id FK has ON DELETE SET NULL per spec §4.3."""
    _seed_minimal_trade(conn, trade_id=1)
    _seed_pipeline_run(conn, run_id=99)
    conn.execute(
        "INSERT INTO daily_management_records "
        "(trade_id, record_type, review_date, data_asof_session, created_at, "
        " mfe_mae_precision_level, pipeline_run_id) "
        "VALUES (1, 'daily_snapshot', '2026-05-07', '2026-05-07', "
        "        '2026-05-07T00:00:00', 'daily_approximate', 99)"
    )
    conn.execute("DELETE FROM pipeline_runs WHERE id = 99")
    row = conn.execute(
        "SELECT pipeline_run_id FROM daily_management_records LIMIT 1"
    ).fetchone()
    assert row[0] is None  # SET NULL fired


def _seed_minimal_trade(conn: sqlite3.Connection, *, trade_id: int) -> None:
    """Insert a minimal trade row sufficient to satisfy FK + NOT NULL constraints.
    Adjust to match Phase 7 trades NOT NULL columns at HEAD 1441109."""
    # Body of helper enumerated in T1.0 step 3. Keep test self-contained.
    ...


def _seed_pipeline_run(conn: sqlite3.Connection, *, run_id: int) -> None:
    """Insert minimal pipeline_runs row."""
    ...
```

Run: `python -m pytest tests/data/test_migration_0016.py -v`
Expected: ALL FAIL with "no such table: daily_management_records" or "schema_version != 16" — migration not yet implemented.

- [ ] **Step 2: Write the migration SQL verbatim from §C**

Create `swing/data/migrations/0016_phase8_daily_management.sql` with the exact SQL from §C above.

- [ ] **Step 3: Bump EXPECTED_SCHEMA_VERSION + add Phase 8 backup gate (Codex R3 Major #1 fix — empirical finding)**

**Empirical finding (verified at `swing/data/db.py:248-294`):** the shipped `_phase7_backup_gate` returns early when `target_version < 14 OR current_version >= 14 OR current_version < 13` — i.e., it ONLY fires when `current_version == 13 AND target_version >= 14`. For v15 → v16, BOTH conditions fail (`current_version >= 14` short-circuits), so no backup is taken. The plan needs to explicitly wire a Phase 8 gate.

In `swing/data/db.py`:

1. Change `EXPECTED_SCHEMA_VERSION = 15` → `16`.

2. Add a NEW gate function `_phase8_backup_gate(conn, *, current_version, target_version, backup_dir)` mirroring `_phase7_backup_gate`'s structure but with the Phase 8 condition + Phase 8 filename:

   ```python
   # Codex R4 Major #1 fix: define the pre-Phase-8 expected table set as the
   # ACTUAL v15 source schema. Phase 7 dropped `exits` and added `fills`
   # (verified at swing/data/migrations/0014_phase7_state_machine_and_fills.sql:8/125);
   # migration 0015 added `finviz_api_calls` (verified at
   # swing/data/migrations/0015_finviz_api_calls.sql:13). PHASE7_EXPECTED_TABLES
   # is the v13 set used by the Phase 7 backup gate (which snapshots a v13 DB
   # — pre-Phase-7 schema with `exits` still present). The v15 source set is
   # different.
   PHASE8_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
       (PHASE7_EXPECTED_TABLES - {"exits"})
       | {"fills", "finviz_api_calls"}
   )
   # Resulting set (verified at writing-plans dispatch against the actual
   # post-Phase-7-post-Finviz v15 schema): {trades, fills, trade_events,
   # pipeline_runs, weather_runs, candidates, evaluation_runs,
   # daily_recommendations, watchlist, cash_movements, review_log,
   # schema_version, finviz_api_calls}.


   def _phase8_backup_gate(
       conn: sqlite3.Connection, *,
       current_version: int, target_version: int,
       backup_dir: Path | None,
   ) -> None:
       """Phase 8 spec §8.2 backup-before-migrate gate.

       Fires only when current_version == 15 AND target_version >= 16.
       Filename: swing-pre-phase8-migration-<ISO>.db.
       """
       if target_version < 16 or current_version != 15:
           return
       src_path = _resolve_main_db_path(conn)
       if src_path is None:
           raise MigrationBackupRequiredException(
               "pre-Phase-8 backup gate requires a file-backed source DB; "
               "in-memory connections cannot be snapshotted."
           )
       if backup_dir is None:
           backup_dir = src_path.parent
       try:
           backup_path = _create_pre_phase8_migration_backup(
               src_path, dest_dir=backup_dir,
           )
           _verify_backup_integrity(
               backup_path,
               expected_tables=PHASE8_PRE_MIGRATION_EXPECTED_TABLES,
           )
       except MigrationBackupRequiredException:
           raise
       except (OSError, sqlite3.Error) as exc:
           raise MigrationBackupRequiredException(
               f"pre-Phase-8 backup failed: {exc}"
           ) from exc


   def _create_pre_phase8_migration_backup(
       src_path: Path, *, dest_dir: Path,
   ) -> Path:
       """Phase 8 mirror of _create_pre_migration_backup with phase8 filename prefix."""
       dest_dir.mkdir(parents=True, exist_ok=True)
       timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
       backup_path = dest_dir / f"swing-pre-phase8-migration-{timestamp}.db"
       src_conn = sqlite3.connect(src_path)
       try:
           dest_conn = sqlite3.connect(backup_path)
           try:
               src_conn.backup(dest_conn)
           finally:
               dest_conn.close()
       finally:
           src_conn.close()
       return backup_path
   ```

3. Wire `_phase8_backup_gate` into `run_migrations` AFTER the existing `_phase7_backup_gate(...)` call at line 321:

   ```python
   _phase7_backup_gate(
       conn, current_version=current_version,
       target_version=target_version, backup_dir=backup_dir,
   )
   _phase8_backup_gate(
       conn, current_version=current_version,
       target_version=target_version, backup_dir=backup_dir,
   )
   ```

The two gates are mutually exclusive by construction (`current_version == 13` vs `current_version == 15`); both can coexist without conflict.

Run: `python -m pytest tests/data/test_migration_0016.py -v`
Expected: ALL PASS.

- [ ] **Step 4: Run full migration round-trip**

```bash
python -m pytest tests/data/test_migration_0016.py -v
ruff check swing/data/migrations/ swing/data/db.py 2>&1 | tail -3
```

Expected: 7 new tests PASS; ruff baseline preserved.

- [ ] **Step 5: Verify ERE grep + commit**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.0' main..HEAD
git add swing/data/migrations/0016_phase8_daily_management.sql \
        tests/data/test_migration_0016.py swing/data/db.py
git commit -m "feat(data): Task 1.0 — migration 0016 daily_management_records + planned_target_R"
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.0' main..HEAD
```

Expected: pre-commit grep empty; commit succeeds; post-commit grep returns the new commit's subject.

ACCEPTANCE:
- All 7 new tests pass.
- ruff baseline preserved (78 pre-existing).
- All 1941 + 7 = 1948 fast tests pass on full suite.
- Subject-only grep returns empty before commit; non-empty after.

VERIFY COMMAND(S):
```bash
python -m pytest tests/data/test_migration_0016.py -q
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.0' main..HEAD
```

**Estimated test count delta:** +7

---

### Task 1.1: Migration runner discipline tests

**Files:**
- Create: `tests/data/test_migration_0016_runner_discipline.py`

- [ ] **Step 1: Write the failing backup-gate test using shipped `backup_dir` parameter (Codex R1 Major #2 + R2 Minor #2 fix)**

The shipped `run_migrations` already accepts a `backup_dir: Path | None = None` parameter (verified at [swing/data/db.py:301](../../swing/data/db.py#L301)) — when None, defaults to `src_path.parent`. T1.1 drives `run_migrations(..., backup_dir=...)` directly with a tmp_path-based override, which exercises the production code path (gate logic intact) without any test-only module hook.

```python
# tests/data/test_migration_0016_runner_discipline.py
"""Phase 8 migration runner discipline: backup gate + foreign_keys=OFF + executescript rollback.

Codex R1 Major #2 + R2 Minor #2 fix: tests invoke run_migrations through the
shipped `backup_dir` parameter (the integration boundary). NO test-only module
hook required.
"""
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    _apply_migration,
    ensure_schema,
    run_migrations,
)


def test_backup_fires_on_v15_to_v16(tmp_path: Path) -> None:
    """Backup created when current_version == 15 AND target == 16.

    EXACT pre-fix expected (without Phase 8 gate registration): zero files
    matching `swing-pre-phase8-migration-*.db` in backup_dir.
    EXACT post-fix expected: exactly 1 file matching the pattern."""
    db_path = tmp_path / "v15.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed schema at v15 (Finviz baseline):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=15, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 15

    # Reopen + walk v15 → v16 through the production gate:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # Backup file should exist with the phase8 prefix:
    backups = list(backup_dir.glob("swing-pre-phase8-migration-*.db"))
    assert len(backups) == 1


def test_backup_does_not_fire_on_fresh_db(tmp_path: Path) -> None:
    """No phase8 backup on fresh DB (current_version == 0).

    EXACT expected: zero files matching `swing-pre-phase8-*.db` in backup_dir."""
    db_path = tmp_path / "fresh.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Walk fresh → 16 through run_migrations directly:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=16, backup_dir=backup_dir)
    conn.commit()
    conn.close()
    assert _read_version(db_path) == 16

    # No phase8 backup (gate condition `current == 15 AND target >= 16` FALSE):
    assert list(backup_dir.glob("swing-pre-phase8-*.db")) == []


def test_backup_does_not_fire_on_v14_to_v15_walk(tmp_path: Path) -> None:
    """No phase8 backup when target_version != 16 (mid-walk to v15 only).

    EXACT expected: zero phase8 backup files; the v14 → v15 step doesn't
    trigger Phase 8 gate condition (target_version != 16)."""
    db_path = tmp_path / "v14.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Seed at v14 + run v14 → v15 only:
    conn = sqlite3.connect(db_path)
    run_migrations(conn, target_version=14, backup_dir=backup_dir)
    conn.commit()
    run_migrations(conn, target_version=15, backup_dir=backup_dir)
    conn.commit()
    conn.close()

    # No phase8 backup file (target_version was 15, not 16):
    assert list(backup_dir.glob("swing-pre-phase8-*.db")) == []


def test_executescript_rollback_on_partial_failure(tmp_path: Path) -> None:
    """Synthetic malformed migration: probe table absent + conn.in_transaction == False."""
    db_path = tmp_path / "v15.db"
    conn = sqlite3.connect(db_path)
    from swing.data.db import run_migrations
    run_migrations(conn, target_version=15)
    conn.commit()

    # Synthetic malformed migration (creates probe_table, then fails):
    bad_sql_path = tmp_path / "bad_migration.sql"
    bad_sql_path.write_text(
        "CREATE TABLE probe_table (id INTEGER);\n"
        "INSERT INTO nonexistent_table VALUES (1);\n"  # FAIL HERE
    )

    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql_path)

    # Probe table must NOT exist (rollback fired):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='probe_table'"
    )
    assert cur.fetchone() is None
    # Connection must NOT be in a transaction:
    assert conn.in_transaction is False


def test_foreign_keys_pragma_restored_after_apply(tmp_path: Path) -> None:
    """foreign_keys=OFF runner discipline: prior value restored in finally:."""
    db_path = tmp_path / "v15.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")  # set prior value to ON
    # Run any benign migration (e.g., write a no-op SQL):
    benign_sql_path = tmp_path / "noop.sql"
    benign_sql_path.write_text("-- noop\n")
    _apply_migration(conn, benign_sql_path)
    # PRAGMA must be restored to ON:
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def _read_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        conn.close()
```

Run: `python -m pytest tests/data/test_migration_0016_runner_discipline.py -v`
Expected: 5 tests; depending on shipped runner state, some may PASS without code changes (Phase 7 hotfix already in `_apply_migration`); the new `_create_pre_migration_backup` filename branch needs the v15→v16 case wired.

- [ ] **Step 2: Wire the backup-filename branch for v15→v16**

In `swing/data/db.py:_create_pre_migration_backup`, ensure the function takes `target_version` parameter (or equivalent existing structure) and emits filename `swing-pre-phase8-migration-<ISO>.db` for `target_version >= 16`. Verify shipped function signature matches; adjust accordingly.

- [ ] **Step 3: Run + verify all 5 tests pass**

Run: `python -m pytest tests/data/test_migration_0016_runner_discipline.py -v`
Expected: ALL 5 PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/data/test_migration_0016_runner_discipline.py swing/data/db.py
git commit -m "feat(data): Task 1.1 — phase8 migration runner discipline (backup gate + executescript rollback + PRAGMA restore)"
```

ACCEPTANCE:
- All 5 new tests pass.
- All previous tests pass.
- ruff baseline preserved.
- Subject-only grep behavior verified.

VERIFY COMMAND(S):
```bash
python -m pytest tests/data/test_migration_0016_runner_discipline.py -q
python -m pytest -m "not slow" -q 2>&1 | tail -3
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.1' main..HEAD
```

**Estimated test count delta:** +5

---

### Task 2.0: Repo `insert_snapshot` + `insert_event_log`

**Files:**
- Create: `swing/data/repos/daily_management.py` (insert_snapshot + insert_event_log only; SELECT functions in T2.1)
- Create: `tests/data/test_daily_management_repo.py` (extended in subsequent tasks)
- Modify: `swing/data/models.py` (add `DailyManagementRecord` dataclass + `planned_target_R` field on `Trade`)

- [ ] **Step 1: Write failing tests for insert_snapshot + insert_event_log**

```python
# tests/data/test_daily_management_repo.py — initial test for T2.0
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.daily_management import (
    insert_snapshot, insert_event_log,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    _seed_minimal_trade(conn, trade_id=1)
    yield conn
    conn.close()


def test_insert_snapshot_returns_management_record_id(conn) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    assert isinstance(rec_id, int) and rec_id > 0


def test_insert_snapshot_persists_all_42_columns(conn) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    row = conn.execute(
        "SELECT current_price, current_stop, mfe_mae_precision_level, "
        "       trail_MA_period_days, is_superseded, record_type "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row[0] == fields["current_price"]
    assert row[1] == fields["current_stop"]
    assert row[2] == "daily_approximate"
    assert row[3] == 21
    assert row[4] == 0
    assert row[5] == "daily_snapshot"


def test_insert_event_log_returns_id_with_record_type_event_log(conn) -> None:
    fields = _minimal_event_log_fields(data_asof_session="2026-05-07")
    rec_id = insert_event_log(conn, trade_id=1, event_log_fields=fields)
    rt = conn.execute(
        "SELECT record_type FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()[0]
    assert rt == "event_log"


def test_insert_event_log_position_state_optional(conn) -> None:
    """event_log accepts NULL position-state per §3.1.1 R1 Critical 1 fix."""
    fields = _minimal_event_log_fields(data_asof_session="2026-05-07")
    fields.pop("current_price", None)  # explicit NULL
    rec_id = insert_event_log(conn, trade_id=1, event_log_fields=fields)
    row = conn.execute(
        "SELECT current_price FROM daily_management_records "
        "WHERE management_record_id = ?",
        (rec_id,),
    ).fetchone()
    assert row[0] is None  # NULL persisted


# Helpers — implementation in actual test file:
def _seed_minimal_trade(conn, *, trade_id): ...
def _full_snapshot_fields(*, data_asof_session: str) -> dict: ...
def _minimal_event_log_fields(*, data_asof_session: str) -> dict: ...
```

Run: `python -m pytest tests/data/test_daily_management_repo.py -v`
Expected: ALL FAIL with "ModuleNotFoundError: swing.data.repos.daily_management" or "ImportError" — module not yet created.

- [ ] **Step 2: Implement `insert_snapshot` + `insert_event_log` minimal**

In `swing/data/repos/daily_management.py`:

```python
"""Daily management records repo (Phase 8).

Public API split across multiple tasks:
    Task 2.0: insert_snapshot, insert_event_log
    Task 2.1: select_active_snapshot
    Task 2.2: select_history, list_for_trade_timeline,
              list_open_position_active_snapshots
    Task 2.3: upsert_snapshot, tier_upgrade_snapshot
"""
import sqlite3
from typing import Any


def insert_snapshot(
    conn: sqlite3.Connection, *, trade_id: int, snapshot_fields: dict[str, Any],
) -> int:
    """Pure INSERT for record_type='daily_snapshot'.

    Caller manages the outer transaction.
    Caller must validate snapshot_fields per OPERATION_REQUIRED_FIELDS["snapshot_emit"]
    BEFORE calling this function — repo layer trusts validated input.
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag
        ) VALUES (?, 'daily_snapshot', ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            snapshot_fields["review_date"],
            snapshot_fields["data_asof_session"],
            snapshot_fields["created_at"],
            snapshot_fields["mfe_mae_precision_level"],
            snapshot_fields.get("pipeline_run_id"),
            snapshot_fields["current_price"],
            snapshot_fields["current_stop"],
            snapshot_fields["current_size"],
            snapshot_fields["current_avg_cost"],
            snapshot_fields["open_R_effective"],
            snapshot_fields["open_MFE_R_to_date"],
            snapshot_fields["open_MAE_R_to_date"],
            snapshot_fields["intraday_high"],
            snapshot_fields["intraday_low"],
            snapshot_fields["position_capital_utilization_pct"],
            snapshot_fields["position_capital_denominator_dollars"],
            snapshot_fields["position_portfolio_heat_contribution_dollars"],
            snapshot_fields["maturity_stage"],
            snapshot_fields.get("trail_MA_candidate_price"),
            snapshot_fields.get("trail_MA_period_days"),
            snapshot_fields["trail_MA_eligibility_flag"],
        ),
    )
    return int(cur.lastrowid)


def insert_event_log(
    conn: sqlite3.Connection, *, trade_id: int, event_log_fields: dict[str, Any],
) -> int:
    """Pure INSERT for record_type='event_log'. Position-state OPTIONAL.

    Caller manages the outer transaction.
    Caller must validate per OPERATION_REQUIRED_FIELDS["event_log_emit"].
    """
    cur = conn.execute(
        """
        INSERT INTO daily_management_records (
            trade_id, record_type, review_date, data_asof_session, created_at,
            mfe_mae_precision_level, pipeline_run_id, is_superseded,
            -- Position-state may be NULL:
            current_price, current_stop, current_size, current_avg_cost,
            open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date,
            intraday_high, intraday_low,
            position_capital_utilization_pct,
            position_capital_denominator_dollars,
            position_portfolio_heat_contribution_dollars,
            maturity_stage, trail_MA_candidate_price,
            trail_MA_period_days, trail_MA_eligibility_flag,
            -- Event-log-specific:
            thesis_status, prior_stop, new_stop, linked_trade_event_id,
            stop_changed, stop_change_reason,
            volume_behavior, relative_strength_status,
            market_regime_change, sector_condition_change,
            news_or_event_update,
            action_taken, action_reason, emotional_state,
            rule_violation_suspected, management_notes
        ) VALUES (?, 'event_log', ?, ?, ?, ?, ?, 0,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            event_log_fields["review_date"],
            event_log_fields["data_asof_session"],
            event_log_fields["created_at"],
            event_log_fields["mfe_mae_precision_level"],
            event_log_fields.get("pipeline_run_id"),
            event_log_fields.get("current_price"),
            event_log_fields.get("current_stop"),
            event_log_fields.get("current_size"),
            event_log_fields.get("current_avg_cost"),
            event_log_fields.get("open_R_effective"),
            event_log_fields.get("open_MFE_R_to_date"),
            event_log_fields.get("open_MAE_R_to_date"),
            event_log_fields.get("intraday_high"),
            event_log_fields.get("intraday_low"),
            event_log_fields.get("position_capital_utilization_pct"),
            event_log_fields.get("position_capital_denominator_dollars"),
            event_log_fields.get("position_portfolio_heat_contribution_dollars"),
            event_log_fields.get("maturity_stage"),
            event_log_fields.get("trail_MA_candidate_price"),
            event_log_fields.get("trail_MA_period_days"),
            event_log_fields.get("trail_MA_eligibility_flag"),
            event_log_fields.get("thesis_status"),
            event_log_fields.get("prior_stop"),
            event_log_fields.get("new_stop"),
            event_log_fields.get("linked_trade_event_id"),
            event_log_fields.get("stop_changed"),
            event_log_fields.get("stop_change_reason"),
            event_log_fields.get("volume_behavior"),
            event_log_fields.get("relative_strength_status"),
            event_log_fields.get("market_regime_change"),
            event_log_fields.get("sector_condition_change"),
            event_log_fields.get("news_or_event_update"),
            event_log_fields.get("action_taken"),
            event_log_fields.get("action_reason"),
            event_log_fields.get("emotional_state"),
            event_log_fields.get("rule_violation_suspected"),
            event_log_fields.get("management_notes"),
        ),
    )
    return int(cur.lastrowid)
```

Add `DailyManagementRecord` dataclass to `swing/data/models.py` mirroring all 42 fields. Add `planned_target_R: float | None = None` to `Trade` dataclass.

Run: `python -m pytest tests/data/test_daily_management_repo.py -v`
Expected: ALL 4 PASS.

- [ ] **Step 3: Commit**

```bash
git add swing/data/repos/daily_management.py swing/data/models.py \
        tests/data/test_daily_management_repo.py
git commit -m "feat(data): Task 2.0 — daily_management repo insert_snapshot + insert_event_log"
```

ACCEPTANCE:
- 4 new tests pass.
- Existing tests pass (note: trades repo tests may need fixture update for `planned_target_R` default; verify).
- ruff baseline preserved.

VERIFY COMMAND(S):
```bash
python -m pytest tests/data/test_daily_management_repo.py -q
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2\.0' main..HEAD
```

**Estimated test count delta:** +4

---

### Task 2.1: Repo `select_active_snapshot`

**Files:**
- Modify: `swing/data/repos/daily_management.py` (add `select_active_snapshot`)
- Modify: `tests/data/test_daily_management_repo.py`

- [ ] **Step 1: Write failing test**

```python
def test_select_active_snapshot_returns_active_only(conn) -> None:
    fields_a = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields_a)
    rec = select_active_snapshot(conn, trade_id=1, data_asof_session="2026-05-07")
    assert rec is not None
    assert rec.is_superseded == 0
    assert rec.mfe_mae_precision_level == "daily_approximate"


def test_select_active_snapshot_returns_none_when_only_superseded(conn) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?", (rec_id,))
    rec = select_active_snapshot(conn, trade_id=1, data_asof_session="2026-05-07")
    assert rec is None


def test_select_active_snapshot_returns_none_for_unknown_session(conn) -> None:
    rec = select_active_snapshot(conn, trade_id=1, data_asof_session="1999-01-01")
    assert rec is None
```

Expected: FAIL with ImportError (function not defined).

- [ ] **Step 2: Implement minimal**

```python
def select_active_snapshot(
    conn: sqlite3.Connection, *, trade_id: int, data_asof_session: str,
) -> "DailyManagementRecord | None":
    row = conn.execute(
        f"SELECT {_DMR_SELECT_COLS} FROM daily_management_records "
        f"WHERE trade_id = ? AND data_asof_session = ? "
        f"  AND record_type = 'daily_snapshot' AND is_superseded = 0",
        (trade_id, data_asof_session),
    ).fetchone()
    return _row_to_record(row) if row else None
```

(Define `_DMR_SELECT_COLS` as the canonical 42-column SELECT list; `_row_to_record` mirrors Phase 7's `_row_to_trade` pattern.)

Run: `python -m pytest tests/data/test_daily_management_repo.py -v`
Expected: 3 new tests PASS; previous 4 still pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(data): Task 2.1 — daily_management repo select_active_snapshot"
```

ACCEPTANCE:
- 3 new tests pass.

**Estimated test count delta:** +3

---

### Task 2.2: Repo `select_history` + `list_for_trade_timeline` + `list_open_position_active_snapshots`

**Files:**
- Modify: `swing/data/repos/daily_management.py`
- Modify: `tests/data/test_daily_management_repo.py`

- [ ] **Step 1: Write failing tests**

```python
def test_select_history_returns_chain_in_creation_order(conn) -> None:
    """Full chain incl. superseded; order: created_at ASC, precision_level ASC."""
    # Insert daily_approximate; then mark superseded; insert intraday_estimated.
    fields1 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="daily_approximate",
    )
    rec1 = insert_snapshot(conn, trade_id=1, snapshot_fields=fields1)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?", (rec1,))
    fields2 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="intraday_estimated",
    )
    rec2 = insert_snapshot(conn, trade_id=1, snapshot_fields=fields2)
    chain = select_history(conn, trade_id=1, data_asof_session="2026-05-07")
    assert [r.management_record_id for r in chain] == [rec1, rec2]


def test_list_for_trade_timeline_orders_chronologically_with_tiebreak(conn) -> None:
    """Spec §7.2: ORDER BY review_date ASC, created_at ASC, management_record_id ASC."""
    # Insert two event_logs same review_date + same created_at:
    el_a = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_a["created_at"] = "2026-05-07T10:00:00"
    rec_a = insert_event_log(conn, trade_id=1, event_log_fields=el_a)
    el_b = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_b["created_at"] = "2026-05-07T10:00:00"  # same wall-clock!
    rec_b = insert_event_log(conn, trade_id=1, event_log_fields=el_b)
    timeline = list_for_trade_timeline(conn, trade_id=1)
    # Ordering: management_record_id ASC tiebreak — rec_a < rec_b:
    ids = [r.management_record_id for r in timeline]
    assert ids.index(rec_a) < ids.index(rec_b)


def test_list_for_trade_timeline_default_excludes_superseded(conn) -> None:
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?", (rec_id,))
    timeline = list_for_trade_timeline(conn, trade_id=1, include_superseded=False)
    assert all(r.is_superseded == 0 for r in timeline)


def test_list_open_position_active_snapshots_returns_one_per_open_trade(conn) -> None:
    """Drives §7.1 dashboard tile."""
    _seed_minimal_trade(conn, trade_id=2)
    fields1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=1, snapshot_fields=fields1)
    fields2 = _full_snapshot_fields(data_asof_session="2026-05-07")
    insert_snapshot(conn, trade_id=2, snapshot_fields=fields2)
    snaps = list_open_position_active_snapshots(conn)
    assert {s.trade_id for s in snaps} == {1, 2}
```

Expected: FAIL — functions not defined.

- [ ] **Step 2: Implement**

Functions per pseudocode in §B file map row for `swing/data/repos/daily_management.py`. Use canonical SELECT cols + ORDER BY clause exactly as spec §7.2 requires.

Run + verify all 4 new tests pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(data): Task 2.2 — daily_management repo select_history + timeline + dashboard list"
```

ACCEPTANCE:
- 4 new tests pass.
- ORDER BY clause for `list_for_trade_timeline` is `(review_date ASC, created_at ASC, management_record_id ASC)` per spec §7.2.

**Estimated test count delta:** +4

---

### Task 2.3: Repo `upsert_snapshot` + `tier_upgrade_snapshot`

**Files:**
- Modify: `swing/data/repos/daily_management.py`
- Modify: `tests/data/test_daily_management_repo.py`

- [ ] **Step 1: Write failing tests (the discriminating regression tests)**

```python
def test_upsert_snapshot_same_tier_reflow_preserves_PK(conn) -> None:
    """SELECT-then-UPDATE-or-INSERT: management_record_id PRESERVED on reflow.
    Discriminating against REPLACE which would mint a new PK."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    fields["current_price"] = 100.0
    rec_id_first = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)

    # Same-tier reflow with new price:
    fields2 = dict(fields)
    fields2["current_price"] = 105.0
    rec_id_second = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields2)

    # PK preserved (NOT a new row):
    assert rec_id_second == rec_id_first

    # Data updated:
    row = conn.execute(
        "SELECT current_price FROM daily_management_records "
        "WHERE management_record_id = ?", (rec_id_first,)).fetchone()
    assert row[0] == 105.0


def test_upsert_snapshot_against_superseded_raises(conn) -> None:
    """SupersededRowImmutableException when only superseded rows exist."""
    fields = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?", (rec_id,))

    with pytest.raises(SupersededRowImmutableException):
        upsert_snapshot(conn, trade_id=1, snapshot_fields=fields)


def test_tier_upgrade_3_tier_chain(conn) -> None:
    """Synthetic 3-tier sequence: daily_approximate → intraday_estimated → intraday_exact.
    Discriminating: at every transaction boundary, exactly one active row;
    audit chain threaded via superseded_by_record_id."""
    # Step 1: daily_approximate
    f1 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="daily_approximate",
    )
    rec1 = upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)

    # Step 2: tier-upgrade to intraday_estimated
    f2 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="intraday_estimated",
    )
    rec2 = tier_upgrade_snapshot(
        conn, trade_id=1, data_asof_session="2026-05-07",
        new_precision_level="intraday_estimated", snapshot_fields=f2,
    )
    row1 = conn.execute(
        "SELECT is_superseded, superseded_by_record_id "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec1,)).fetchone()
    assert row1 == (1, rec2)

    # Step 3: tier-upgrade to intraday_exact
    f3 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="intraday_exact",
    )
    rec3 = tier_upgrade_snapshot(
        conn, trade_id=1, data_asof_session="2026-05-07",
        new_precision_level="intraday_exact", snapshot_fields=f3,
    )
    row2 = conn.execute(
        "SELECT is_superseded, superseded_by_record_id "
        "FROM daily_management_records WHERE management_record_id = ?",
        (rec2,)).fetchone()
    assert row2 == (1, rec3)

    # Active count must be 1 at end:
    active_count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records "
        "WHERE trade_id = 1 AND data_asof_session = '2026-05-07' "
        "  AND record_type = 'daily_snapshot' AND is_superseded = 0"
    ).fetchone()[0]
    assert active_count == 1


def test_tier_upgrade_to_lower_tier_raises_TierOrderingError(conn) -> None:
    f1 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="intraday_estimated",
    )
    upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)
    f2 = _full_snapshot_fields(
        data_asof_session="2026-05-07",
        mfe_mae_precision_level="daily_approximate",
    )
    with pytest.raises(TierOrderingError):
        tier_upgrade_snapshot(
            conn, trade_id=1, data_asof_session="2026-05-07",
            new_precision_level="daily_approximate", snapshot_fields=f2,
        )


def test_upsert_snapshot_does_not_use_REPLACE(conn) -> None:
    """Discriminating against `INSERT OR REPLACE` (CLAUDE.md gotcha 2026-05-06).
    REPLACE would: (a) cascade-wipe child FK rows, (b) mint new PK. We test (b):
    insert; reflow; assert original management_record_id IS the same row, not a
    new one with same logical key. (Already tested in
    test_upsert_snapshot_same_tier_reflow_preserves_PK; this test additionally
    asserts no AUTOINCREMENT advance.)"""
    f1 = _full_snapshot_fields(data_asof_session="2026-05-07")
    rec_id = upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)
    upsert_snapshot(conn, trade_id=1, snapshot_fields=f1)  # reflow
    # Highest auto-incremented id should still equal rec_id (no INSERT happened):
    max_id = conn.execute(
        "SELECT MAX(management_record_id) FROM daily_management_records"
    ).fetchone()[0]
    assert max_id == rec_id
```

Expected: FAIL — functions not defined.

- [ ] **Step 2: Implement `upsert_snapshot` + `tier_upgrade_snapshot` per §G + §H pseudocode**

Implement the pseudocode verbatim. Add custom exceptions:

```python
class SupersededRowImmutableException(Exception):
    """Raised when a write attempts to mutate a superseded row, OR when a
    same-tier reflow targets a tier where no active row exists but a
    superseded row at that same tier does. Per spec §6.1 audit-stability
    contract; CLAUDE.md gotcha 2026-05-06."""


class TierOrderingError(Exception):
    """Raised when tier_upgrade_snapshot is invoked with a new precision level
    that does not strictly outrank the predecessor's level per
    DAILY_MGMT_PRECISION_RANK."""
```

(Exception classes import from `swing/trades/daily_management.py` per §B file map; OR co-locate in repos module — implementer decides at module-organization time, but T2.3 documents the choice.)

Run: `python -m pytest tests/data/test_daily_management_repo.py -v`
Expected: 5 new tests PASS.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(data): Task 2.3 — daily_management repo upsert_snapshot + tier_upgrade_snapshot (SELECT-then-UPDATE pattern, NOT REPLACE)"
```

ACCEPTANCE:
- 5 new tests pass (4 + the AUTOINCREMENT discriminating test).
- The §A.1 + spec §4.2 + CLAUDE.md gotcha 2026-05-06 guidance is HONORED — implementation MUST NOT use SQLite REPLACE; review the SQL string-by-string to verify.

VERIFY COMMAND(S):
```bash
# Codex R1 Minor #1 fix: tight SQL pattern (avoid false positives on comments
# / exception text / docstrings):
grep -nE 'INSERT[[:space:]]+OR[[:space:]]+REPLACE|REPLACE[[:space:]]+INTO' \
    swing/data/repos/daily_management.py  # should match nothing
python -m pytest tests/data/test_daily_management_repo.py -q
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2\.3' main..HEAD
```

**Estimated test count delta:** +5

---

### Task 3.0: Service `compute_daily_approximate_snapshot` + pure helpers + validators

**Files:**
- Create: `swing/trades/daily_management.py` (helpers + constants + service)
- Create: `tests/trades/test_daily_management_helpers.py`
- Create: `tests/trades/test_daily_management_service.py`

- [ ] **Step 1: Write failing helper tests**

```python
# tests/trades/test_daily_management_helpers.py
import pandas as pd
import pytest

from swing.trades.daily_management import (
    DAILY_MGMT_PRECISION_RANK,
    DAILY_MGMT_THESIS_UNRECORDED_SENTINEL,
    OPERATION_REQUIRED_FIELDS,
    compute_maturity_stage,
    compute_open_R_effective,
    compute_position_capital_utilization,
    compute_position_portfolio_heat,
    compute_running_extrema_R,
    compute_trail_MA_eligibility_flag,
    resolve_thesis_status,
    validate_for_operation,
)


@pytest.mark.parametrize("mfe_r,expected", [
    (None, None),
    (0.0, "pre_+1.5R"),
    (1.49, "pre_+1.5R"),
    (1.5, "+1.5R_to_+2R"),
    (1.99, "+1.5R_to_+2R"),
    (2.0, ">=+2R_trail_eligible"),
    (5.0, ">=+2R_trail_eligible"),
])
def test_compute_maturity_stage_boundaries(mfe_r, expected) -> None:
    assert compute_maturity_stage(mfe_r) == expected


@pytest.mark.parametrize("stage,trail_price,stop,expected", [
    (None, 100.0, 90.0, None),
    (">=+2R_trail_eligible", None, 90.0, None),
    (">=+2R_trail_eligible", 100.0, None, None),
    ("pre_+1.5R", 100.0, 90.0, 0),
    ("+1.5R_to_+2R", 100.0, 90.0, 0),
    (">=+2R_trail_eligible", 100.0, 90.0, 1),  # stop < trail → flag=1
    (">=+2R_trail_eligible", 100.0, 100.0, 0),  # stop == trail → flag=0
    (">=+2R_trail_eligible", 100.0, 110.0, 0),  # stop > trail → flag=0
])
def test_compute_trail_MA_eligibility_flag(stage, trail_price, stop, expected) -> None:
    assert compute_trail_MA_eligibility_flag(
        maturity_stage=stage, trail_MA_candidate_price=trail_price,
        current_stop=stop,
    ) == expected


def test_compute_open_R_effective_basic() -> None:
    # Entry at 100, stop at 90 → risk_per_share = 10. Position 50 shares.
    # planned_risk_budget = 10 * 50 = 500.
    # Current price 110 → unrealized = (110 - 100) * 50 = 500 → R = 500/500 = 1.0
    assert compute_open_R_effective(
        current_price=110.0, current_avg_cost=100.0,
        current_size=50.0, planned_risk_budget_dollars=500.0,
    ) == 1.0


def test_compute_running_extrema_R_basic() -> None:
    df = pd.DataFrame({
        "High": [105.0, 115.0, 110.0],
        "Low":  [98.0,  102.0, 100.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))
    from datetime import date
    mfe, mae = compute_running_extrema_R(
        df,
        anchor_session=date(2026, 5, 5),
        asof_session=date(2026, 5, 7),
        entry_price=100.0,
        initial_stop=90.0,  # risk_per_share = 10
    )
    # MFE = max(High) - 100 = 115 - 100 = 15 → 15/10 = 1.5
    # MAE = 100 - min(Low) = 100 - 98 = 2 → 2/10 = 0.2
    assert mfe == 1.5
    assert mae == 0.2


def test_compute_running_extrema_R_returns_zero_on_empty_window() -> None:
    df = pd.DataFrame({"High": [105.0], "Low": [98.0]},
                      index=pd.to_datetime(["2026-05-05"]))
    from datetime import date
    mfe, mae = compute_running_extrema_R(
        df, anchor_session=date(2026, 6, 1), asof_session=date(2026, 6, 30),
        entry_price=100.0, initial_stop=90.0,
    )
    assert (mfe, mae) == (0.0, 0.0)


def test_validate_for_operation_snapshot_emit_missing_fields() -> None:
    incomplete = {"current_price": 100.0}  # missing 13 others
    missing = validate_for_operation(incomplete, op="snapshot_emit")
    assert "current_stop" in missing
    assert "current_size" in missing
    # CHECK at least 13 missing reported:
    assert len(missing) >= 13


def test_validate_for_operation_event_log_emit_minimal() -> None:
    minimal = {
        "stop_changed": 0,
        "action_taken": "no_action",
        "rule_violation_suspected": 0,
        "emotional_state": '["calm"]',
    }
    assert validate_for_operation(minimal, op="event_log_emit") == []


def test_resolve_thesis_status_open_default_intact() -> None:
    """Open trades, no event_log thesis update → 'intact'."""
    assert resolve_thesis_status(
        trade_state="managing", latest_thesis_in_event_log=None,
    ) == "intact"


def test_resolve_thesis_status_closed_default_unrecorded() -> None:
    """Closed trades, no event_log thesis update → sentinel 'unrecorded' (NOT 'intact')."""
    assert resolve_thesis_status(
        trade_state="closed", latest_thesis_in_event_log=None,
    ) == DAILY_MGMT_THESIS_UNRECORDED_SENTINEL
    assert DAILY_MGMT_THESIS_UNRECORDED_SENTINEL == "unrecorded"


def test_resolve_thesis_status_event_log_value_overrides_default() -> None:
    """If event_log has non-NULL thesis_status, that value is returned regardless of state."""
    assert resolve_thesis_status(
        trade_state="closed", latest_thesis_in_event_log="invalidated",
    ) == "invalidated"
    assert resolve_thesis_status(
        trade_state="managing", latest_thesis_in_event_log="weakening",
    ) == "weakening"
```

Expected: FAIL — module not yet created.

- [ ] **Step 2: Implement helpers + constants + validator + thesis resolver**

Per §D + §E + spec §3.1.1 + §5.6 R3 Major #4 thesis resolution rule. Add `resolve_thesis_status(*, trade_state: str, latest_thesis_in_event_log: str | None) -> str`:

```python
def resolve_thesis_status(
    *, trade_state: str, latest_thesis_in_event_log: str | None,
) -> str:
    """Spec §3.1 + §5.6 R3 Major 4 fix: closed/reviewed trades with no
    event_log thesis update return sentinel 'unrecorded'; open trades default
    to 'intact'. If event_log has a non-NULL value, that overrides defaults."""
    if latest_thesis_in_event_log is not None:
        return latest_thesis_in_event_log
    if trade_state in ("closed", "reviewed"):
        return DAILY_MGMT_THESIS_UNRECORDED_SENTINEL
    # 'entered' / 'managing' / 'partial_exited':
    return "intact"
```

Run helper tests → all 11 pass.

- [ ] **Step 3: Write failing service test for `compute_daily_approximate_snapshot`**

```python
# tests/trades/test_daily_management_service.py
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.trades.daily_management import (
    compute_daily_approximate_snapshot,
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


def test_compute_daily_approximate_snapshot_full_path(conn, tmp_path, monkeypatch) -> None:
    """End-to-end: synthetic OHLCV archive returns DataFrame; service produces
    fully-populated SnapshotFields."""
    # Seed a trade in 'managing' state at HEAD-shipped column shape:
    _seed_trade(conn, trade_id=1, ticker="DHC", entry_price=100.0,
                initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0,
                current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00")

    # Stub the OHLCV archive to return a synthetic DataFrame:
    df = pd.DataFrame({
        "High": [105.0, 115.0, 110.0],
        "Low":  [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))

    def fake_read_or_fetch_archive(*args, **kwargs):
        return df

    monkeypatch.setattr(
        "swing.trades.daily_management.read_or_fetch_archive",
        fake_read_or_fetch_archive,
    )

    fields = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert fields["mfe_mae_precision_level"] == "daily_approximate"
    assert fields["data_asof_session"] == "2026-05-07"
    assert fields["review_date"] == "2026-05-07"
    assert fields["current_price"] == 108.0  # close of asof_session
    assert fields["intraday_high"] == 110.0
    assert fields["intraday_low"]  == 100.0
    # MFE = (115 - 100) / 10 = 1.5; MAE = (100 - 98) / 10 = 0.2:
    assert fields["open_MFE_R_to_date"] == 1.5
    assert fields["open_MAE_R_to_date"] == 0.2
    # maturity_stage: MFE 1.5 → '+1.5R_to_+2R'
    assert fields["maturity_stage"] == "+1.5R_to_+2R"
    # capital_utilization = (50 * 108) / 7500 = 0.72
    assert fields["position_capital_utilization_pct"] == pytest.approx(0.72)
    # portfolio_heat = max(0, (100 - 92) * 50) = 400
    assert fields["position_portfolio_heat_contribution_dollars"] == 400.0
    assert fields["position_capital_denominator_dollars"] == 7500.0
    # trail_MA_period_days stamped:
    assert fields["trail_MA_period_days"] == 21
    # 21-day SMA needs 21 sessions; we have 3 → trail_MA_candidate_price NULL:
    assert fields["trail_MA_candidate_price"] is None
    # trail_MA_eligibility_flag NULL when candidate is NULL:
    assert fields["trail_MA_eligibility_flag"] is None
    # created_at is naive UTC ISO:
    assert "T" in fields["created_at"] and "+" not in fields["created_at"]


def test_compute_daily_approximate_snapshot_canonicalizes_aware_run_now_to_naive_UTC(
    conn, tmp_path, monkeypatch,
) -> None:
    """Codex R1 Major #5: aware run_now (e.g., HST or UTC-aware) MUST canonicalize
    to naive UTC ISO format before stamping created_at. Without canonicalization,
    the offset suffix breaks lexicographic ordering on the TEXT column when later
    compared to naive rows.

    EXACT pre-fix expected (without canonicalization): created_at like
    `'2026-05-07T18:00:00-10:00'` or `'2026-05-07T18:00:00+00:00'`.
    EXACT post-fix expected: created_at like `'2026-05-08T04:00:00'` for HST input
    (HST = UTC-10; 18:00 HST → 04:00 next-day UTC) — naive (no offset)."""
    from datetime import timezone, timedelta

    _seed_trade(conn, trade_id=1, ticker="DHC", entry_price=100.0,
                initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0,
                current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00")
    df = pd.DataFrame({
        "High": [105.0, 110.0],
        "Low":  [98.0,  100.0],
        "Close": [104.0, 108.0],
    }, index=pd.to_datetime(["2026-05-06", "2026-05-07"]))
    monkeypatch.setattr(
        "swing.trades.daily_management.read_or_fetch_archive",
        lambda *a, **kw: df,
    )

    HST = timezone(timedelta(hours=-10))
    run_now_aware_hst = datetime(2026, 5, 7, 18, 0, 0, tzinfo=HST)

    fields = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=run_now_aware_hst,
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    # Naive (no offset suffix), and timestamp converted to UTC:
    assert "+" not in fields["created_at"]
    assert "Z" not in fields["created_at"]
    # 18:00 HST = 04:00 next-day UTC:
    assert fields["created_at"] == "2026-05-08T04:00:00"


def test_compute_daily_approximate_snapshot_returns_None_on_empty_archive(conn, tmp_path, monkeypatch) -> None:
    """Spec §A.4 lesson family: empty archive read → return None (operator-actionable)."""
    _seed_trade(conn, trade_id=1, ticker="ZZZZ", entry_price=100.0,
                initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0,
                current_stop=92.0, pre_trade_locked_at="2026-05-01T09:30:00")
    monkeypatch.setattr(
        "swing.trades.daily_management.read_or_fetch_archive",
        lambda *a, **kw: None,
    )
    result = compute_daily_approximate_snapshot(
        conn, trade_id=1,
        asof_session=date(2026, 5, 7),
        run_now=datetime(2026, 5, 7, 18, 0, 0),
        ohlcv_archive_dir=tmp_path / "ohlcv",
        archive_history_days=120,
        pipeline_run_id=1,
        capital_floor_dollars=7500.0,
        trail_MA_period_days_default=21,
    )
    assert result is None
```

Expected: FAIL — service not yet implemented.

- [ ] **Step 4: Implement `compute_daily_approximate_snapshot`**

```python
def compute_daily_approximate_snapshot(
    conn: sqlite3.Connection, *,
    trade_id: int,
    asof_session: date,
    run_now: datetime,
    ohlcv_archive_dir: Path,
    archive_history_days: int,
    pipeline_run_id: int | None,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,
) -> dict | None:
    """Spec §4.1 step body. Returns dict of SnapshotFields suitable for
    upsert_snapshot, OR None if archive returns no data for the ticker."""
    from swing.data.repos.trades import get_trade
    from swing.data.ohlcv_archive import read_or_fetch_archive

    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")

    df = read_or_fetch_archive(
        trade.ticker, end_date=asof_session,
        cache_dir=ohlcv_archive_dir,
        archive_history_days=archive_history_days,
    )
    if df is None or df.empty:
        return None

    # Slice to <= asof_session AND >= pre_trade_locked_at_session:
    anchor = date.fromisoformat(trade.pre_trade_locked_at[:10])
    window = df[(df.index.date >= anchor) & (df.index.date <= asof_session)]
    if window.empty:
        return None

    asof_row = df[df.index.date == asof_session]
    if asof_row.empty:
        return None

    current_price = float(asof_row["Close"].iloc[-1])
    intraday_high = float(asof_row["High"].iloc[-1])
    intraday_low  = float(asof_row["Low"].iloc[-1])

    open_MFE_R, open_MAE_R = compute_running_extrema_R(
        df, anchor_session=anchor, asof_session=asof_session,
        entry_price=trade.entry_price, initial_stop=trade.initial_stop,
    )

    planned_risk_budget = (
        (trade.entry_price - trade.initial_stop) * trade.initial_shares
    )
    open_R_effective = compute_open_R_effective(
        current_price=current_price,
        current_avg_cost=trade.current_avg_cost,
        current_size=trade.current_size,
        planned_risk_budget_dollars=planned_risk_budget,
    )
    cap_util = compute_position_capital_utilization(
        current_size=trade.current_size, current_price=current_price,
        denominator_dollars=capital_floor_dollars,
    )
    heat = compute_position_portfolio_heat(
        current_avg_cost=trade.current_avg_cost,
        current_stop=trade.current_stop,
        current_size=trade.current_size,
    )
    maturity_stage = compute_maturity_stage(open_MFE_R)

    # 21-day SMA of close at asof_session:
    sma_window = df[df.index.date <= asof_session].tail(trail_MA_period_days_default)
    if len(sma_window) < trail_MA_period_days_default:
        trail_MA_candidate_price = None
        trail_MA_period_days_stamp = None  # coherently both NULL
    else:
        trail_MA_candidate_price = float(sma_window["Close"].mean())
        trail_MA_period_days_stamp = trail_MA_period_days_default

    trail_MA_eligibility_flag = compute_trail_MA_eligibility_flag(
        maturity_stage=maturity_stage,
        trail_MA_candidate_price=trail_MA_candidate_price,
        current_stop=trade.current_stop,
    )

    # naive UTC ISO datetime per spec §8.4 (Codex R1 Major #5 fix —
    # canonicalize aware inputs to naive UTC before stamping; preserves
    # lexicographic-ordering invariant on the TEXT column):
    if run_now.tzinfo is not None:
        from datetime import timezone as _tz
        run_now_naive_utc = (
            run_now.astimezone(_tz.utc).replace(tzinfo=None, microsecond=0)
        )
    else:
        run_now_naive_utc = run_now.replace(microsecond=0)
    created_at = run_now_naive_utc.isoformat()
    # Defensive assertion — fail fast if canonicalization didn't strip tz:
    assert "+" not in created_at and "Z" not in created_at, (
        f"created_at must be naive (no offset): got {created_at!r}"
    )

    return {
        "review_date": asof_session.isoformat(),
        "data_asof_session": asof_session.isoformat(),
        "created_at": created_at,
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": pipeline_run_id,
        "current_price": current_price,
        "current_stop": trade.current_stop,
        "current_size": trade.current_size,
        "current_avg_cost": trade.current_avg_cost,
        "open_R_effective": open_R_effective,
        "open_MFE_R_to_date": open_MFE_R,
        "open_MAE_R_to_date": open_MAE_R,
        "intraday_high": intraday_high,
        "intraday_low": intraday_low,
        "position_capital_utilization_pct": cap_util,
        "position_capital_denominator_dollars": capital_floor_dollars,
        "position_portfolio_heat_contribution_dollars": heat,
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": trail_MA_candidate_price,
        "trail_MA_period_days": trail_MA_period_days_stamp,
        "trail_MA_eligibility_flag": trail_MA_eligibility_flag,
    }
```

Run service tests → 2 pass; all helper tests still pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(trades): Task 3.0 — daily_management compute_daily_approximate_snapshot + helpers + validators"
```

ACCEPTANCE:
- 11 helper tests + 3 service tests = 14 new tests pass.
- Validators implement all OPERATION_REQUIRED_FIELDS sets per spec §3.1.1.

VERIFY COMMAND(S):
```bash
python -m pytest tests/trades/test_daily_management_helpers.py tests/trades/test_daily_management_service.py -q
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3\.0' main..HEAD
```

**Estimated test count delta:** +14

---

### Task 3.1: Service tier-upgrade integration test (writing-plans defers V2 wire)

**Files:**
- Modify: `swing/trades/daily_management.py` (add `tier_upgrade_to_intraday` stub raising NotImplementedError)
- Modify: `tests/trades/test_daily_management_service.py`

- [ ] **Step 1: Write failing tests**

```python
def test_tier_upgrade_to_intraday_stubbed_for_V2(conn) -> None:
    """V1 schema reserves enum + path; service stubs V2 behavior."""
    from swing.trades.daily_management import tier_upgrade_to_intraday
    with pytest.raises(NotImplementedError, match="Schwab API Phase B"):
        tier_upgrade_to_intraday(
            conn, trade_id=1, data_asof_session="2026-05-07",
            new_precision_level="intraday_estimated", snapshot_fields={},
        )
```

- [ ] **Step 2: Add stub**

```python
def tier_upgrade_to_intraday(*args, **kwargs):
    """V2 entry point — gated on intraday data source per spec §10.7.

    The schema and validator path ARE exercised at V1 via direct
    repo-level tier_upgrade_snapshot calls in T2.3 tests.
    """
    raise NotImplementedError("V2: gated on Schwab API Phase B intraday ingestion")
```

Run + commit:

```bash
git commit -m "feat(trades): Task 3.1 — daily_management tier_upgrade_to_intraday V2 stub"
```

ACCEPTANCE:
- 1 new test passes.

**Estimated test count delta:** +1

---

### Task 3.2: Service `record_event_log` — single-transaction contract (the §A.1 critical task)

**Files:**
- Modify: `swing/trades/daily_management.py`
- Modify: `tests/trades/test_daily_management_service.py`

- [ ] **Step 1: Write SIX failing discriminating regression tests per §I (4 originals + Codex R1 M4 no-op-stop guard + Codex R4 M2 stale-prior-stop guard)**

```python
def test_record_event_log_happy_path_stop_change_and_state_transition(conn) -> None:
    """All 4 side-effects landed in single transaction."""
    _seed_trade(conn, trade_id=1, state="entered", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=1, prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop", action_reason="breakout_confirmed",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    rec_id = record_event_log(conn, trade_id=1, req=req)

    # Side-effect 1: event_log row inserted with linked_trade_event_id
    row = conn.execute(
        "SELECT linked_trade_event_id, new_stop FROM daily_management_records "
        "WHERE management_record_id = ?", (rec_id,)).fetchone()
    assert row[0] is not None  # FK populated
    assert row[1] == 95.0
    # Side-effect 2: trade_events stop_adjust row inserted
    te_row = conn.execute(
        "SELECT id, event_type FROM trade_events WHERE id = ?", (row[0],),
    ).fetchone()
    assert te_row[1] == "stop_adjust"
    # Side-effect 3: trades.current_stop = 95.0
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    assert cs == 95.0
    # Side-effect 4: trades.state = 'managing' (entered → managing transition)
    state = conn.execute("SELECT state FROM trades WHERE id = 1").fetchone()[0]
    assert state == "managing"


def test_record_event_log_rolls_back_all_on_late_failure(conn, monkeypatch) -> None:
    """The §A.1 critical discriminating test: if event_log INSERT fails AFTER
    repo-level update_stop_with_event already wrote the stop_adjust row, the
    OUTER `with conn:` rollback wipes BOTH writes."""
    _seed_trade(conn, trade_id=1, state="entered", current_stop=92.0)
    pre_stop = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    pre_event_count = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1").fetchone()[0]

    # Inject a synthetic exception in the event_log INSERT step:
    def boom(*a, **kw):
        raise RuntimeError("synthetic-failure-after-stop-adjust")
    monkeypatch.setattr(
        "swing.trades.daily_management.insert_event_log", boom,
    )

    req = _build_event_log_request(
        trade_id=1, stop_changed=1, prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    with pytest.raises(RuntimeError, match="synthetic"):
        record_event_log(conn, trade_id=1, req=req)

    # Side-effects rolled back:
    post_stop = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    post_event_count = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1").fetchone()[0]
    post_dmr_count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    assert post_stop == pre_stop  # NOT 95.0 — rolled back
    assert post_event_count == pre_event_count  # NO stop_adjust event
    assert post_dmr_count == 0  # NO event_log row


def test_record_event_log_no_stop_change(conn) -> None:
    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=0, action_taken="hold", action_reason=None,
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    rec_id = record_event_log(conn, trade_id=1, req=req)
    row = conn.execute(
        "SELECT linked_trade_event_id, new_stop FROM daily_management_records "
        "WHERE management_record_id = ?", (rec_id,)).fetchone()
    assert row[0] is None
    assert row[1] is None
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    assert cs == 92.0  # unchanged


def test_record_event_log_validation_failure_rolls_back(conn) -> None:
    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=None,  # invalid: stop_changed=1 but new_stop missing
        stop_change_reason="x",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    from swing.trades.daily_management import ValidationException
    with pytest.raises(ValidationException):
        record_event_log(conn, trade_id=1, req=req)
    count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    assert count == 0


def test_record_event_log_rejects_stale_prior_stop(conn) -> None:
    """Codex R4 Major #2 discriminating test: a stale form (operator-rendered
    against an earlier trades.current_stop) submits prior_stop=92 while
    trades.current_stop has already moved to 93 via a racing stop_adjust.

    EXACT pre-fix expected (without prior_stop guard): event_log row inserted
    with prior_stop=92 (stale) but the linked trade_events.payload_json records
    old_stop=93 (actual). Audit chain divergence.

    EXACT post-fix expected: ValidationException raised with match-string
    'stale form'; no event_log row; no trade_events row; trades.current_stop
    unchanged."""
    _seed_trade(conn, trade_id=1, state="managing", current_stop=93.0)  # already at 93
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    pre_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1").fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0,  # STALE — actual is 93.0
        new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    from swing.trades.daily_management import ValidationException
    with pytest.raises(ValidationException, match="stale form"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    post_te = conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE trade_id = 1").fetchone()[0]
    assert post_dmr == pre_dmr
    assert post_te == pre_te
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    assert cs == 93.0  # unchanged


def test_record_event_log_rejects_noop_stop_change(conn) -> None:
    """Codex R1 Major #4 discriminating test: stop_changed=1 with new_stop ==
    current trades.current_stop is a no-op at the repo layer (returns early,
    no INSERT). Without the validator guard, a subsequent linked_trade_event_id
    capture would point at a STALE prior trade_events row.

    EXACT pre-fix expected (without §A.1 + R1-M4 guard): event_log row inserted
    with linked_trade_event_id pointing at some prior unrelated stop_adjust row,
    OR pointing at None (last_insert_rowid returns 0). Either is wrong.

    EXACT post-fix expected: ValidationException raised; no event_log row
    inserted; trades.current_stop unchanged."""
    _seed_trade(conn, trade_id=1, state="managing", current_stop=92.0)
    pre_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=92.0,  # SAME as current — no-op
        stop_change_reason="ostensible reason",
        action_taken="move_stop", action_reason="x",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T18:00:00",
    )
    from swing.trades.daily_management import ValidationException
    with pytest.raises(ValidationException, match="no-op stop change"):
        record_event_log(conn, trade_id=1, req=req)
    post_dmr = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records").fetchone()[0]
    assert post_dmr == pre_dmr
    cs = conn.execute(
        "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
    assert cs == 92.0  # unchanged
```

- [ ] **Step 2: Implement `record_event_log` per §I pseudocode**

Per §I — REPO-LEVEL `update_stop_with_event` call (NOT service-level), TRADE-SCOPED max-id-after-insert pattern (NOT `last_insert_rowid()` per Codex R2 M3 + R6 m1), `state_transition` for entered→managing.

Run all 6 tests → all PASS.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trades): Task 3.2 — daily_management record_event_log single-transaction (§A.1 repo-level Phase 7 call)"
```

ACCEPTANCE:
- 6 new tests pass.
- Implementation calls `swing.data.repos.trades:update_stop_with_event` (REPO-LEVEL), NOT `swing.trades.stop_adjust:update_stop_with_event` (SERVICE-LEVEL). Verified by:
  ```bash
  grep -n "from swing.trades.stop_adjust import" swing/trades/daily_management.py
  # should be empty
  grep -n "from swing.data.repos.trades import" swing/trades/daily_management.py
  # should match update_stop_with_event
  ```

VERIFY COMMAND(S):
```bash
python -m pytest tests/trades/test_daily_management_service.py -q
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3\.2' main..HEAD
```

**Estimated test count delta:** +6

---

### Task 4.0: Pipeline-step `_step_daily_management`

**Files:**
- Modify: `swing/pipeline/runner.py`
- Create: `tests/pipeline/test_daily_management_step.py`

- [ ] **Step 1: Write failing tests (Codex R1 Major #3 fix — concrete fixtures, no `...` placeholders)**

```python
# tests/pipeline/test_daily_management_step.py
"""_step_daily_management integration tests."""
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.pipeline.runner import _step_daily_management


@pytest.fixture
def synthetic_lease_and_trades(tmp_path: Path, monkeypatch):
    """Sets up a fresh DB at v16, seeds 2 open trades (DHC managing, ZZ entered)
    + 1 closed trade (VIR), patches the OHLCV archive to return a synthetic
    DataFrame, and returns a (lease, conn_factory) pair compatible with
    lease.fenced_write()."""
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    # Seed trades:
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                entry_price=100.0, initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
                pre_trade_locked_at="2026-05-01T09:30:00")
    _seed_trade(conn, trade_id=2, ticker="ZZ", state="entered",
                entry_price=50.0, initial_stop=45.0, initial_shares=100.0,
                current_avg_cost=50.0, current_size=100.0, current_stop=45.0,
                pre_trade_locked_at="2026-05-06T09:30:00")
    _seed_trade(conn, trade_id=3, ticker="VIR", state="closed",
                entry_price=80.0, initial_stop=70.0, initial_shares=60.0,
                current_avg_cost=80.0, current_size=0.0, current_stop=70.0,
                pre_trade_locked_at="2026-04-15T09:30:00")
    # Seed pipeline_run row for FK:
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, state) "
        "VALUES (?, ?, 'completed')", (99, "2026-05-07T18:00:00"))
    conn.commit()

    # Synthetic OHLCV — same DataFrame for both tickers:
    df = pd.DataFrame({
        "High": [105.0, 115.0, 110.0],
        "Low":  [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))
    monkeypatch.setattr(
        "swing.trades.daily_management.read_or_fetch_archive",
        lambda *a, **kw: df,
    )

    # Construct a minimal Lease stub that yields the connection from
    # fenced_write(). Mirror Phase 7 + finviz-API integration test pattern;
    # the exact Lease API surface is verified at executing-plans dispatch.
    class _StubLease:
        def fenced_write(self):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield conn
            return _cm()
    return _StubLease(), conn


def test_step_emits_one_snapshot_per_open_trade(synthetic_lease_and_trades):
    """EXACT pre-fix: 0 daily_snapshot rows.
    EXACT post-fix: 2 daily_snapshot rows (DHC + ZZ); 0 for VIR."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),  # unused (archive is monkeypatched)
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rows = conn.execute(
        "SELECT trade_id FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot' ORDER BY trade_id"
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2]


def test_step_skips_closed_trades(synthetic_lease_and_trades):
    """EXACT post-fix: VIR (trade_id=3) has 0 snapshots."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    count = conn.execute(
        "SELECT COUNT(*) FROM daily_management_records WHERE trade_id = 3"
    ).fetchone()[0]
    assert count == 0


def test_step_idempotent_same_day_rerun(synthetic_lease_and_trades):
    """Second run UPDATEs in place (preserves management_record_id).

    EXACT pre-fix (with REPLACE): rec_id_after_second != rec_id_after_first.
    EXACT post-fix: rec_id_after_second == rec_id_after_first."""
    lease, conn = synthetic_lease_and_trades
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rec1 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]

    # Second run with same asof_session:
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 19, 0, 0),  # later same day
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    rec2 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]
    assert rec1 == rec2  # SAME PK


def test_step_triggers_entered_to_managing_transition(synthetic_lease_and_trades):
    """ZZ starts as 'entered'; after first snapshot, state = 'managing'."""
    lease, conn = synthetic_lease_and_trades
    pre_state = conn.execute(
        "SELECT state FROM trades WHERE id = 2").fetchone()[0]
    assert pre_state == "entered"

    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    post_state = conn.execute(
        "SELECT state FROM trades WHERE id = 2").fetchone()[0]
    assert post_state == "managing"


def test_step_no_back_fill_on_gap(synthetic_lease_and_trades, monkeypatch):
    """If pipeline ran at asof=Friday + asof=Monday (with Sat/Sun gap), NO
    rows emitted for Saturday/Sunday — gap-flagged policy (spec §4.3).

    Codex R2 Minor #3 fix: test runs TWO distinct session anchors (Fri 2026-05-08
    + Mon 2026-05-11) and asserts the daily_management_records table contains
    EXACTLY those two data_asof_session values per active trade — Saturday
    (2026-05-09) and Sunday (2026-05-10) absent.

    EXACT post-fix expected: distinct(data_asof_session) for each trade ==
    {'2026-05-08', '2026-05-11'} — the two run anchors only, NOT a contiguous
    range filled in by back-fill."""
    from datetime import date as _date
    lease, conn = synthetic_lease_and_trades

    # Monkeypatch last_completed_session to return the requested session
    # (test fixture controls the anchor explicitly):
    runner_anchor_session: list[_date] = [_date(2026, 5, 8)]  # Fri

    def fake_last_completed_session(_now):
        return runner_anchor_session[0]

    monkeypatch.setattr(
        "swing.pipeline.runner.last_completed_session",
        fake_last_completed_session,
    )

    # Run #1: Friday session
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 8, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    # Skip Sat + Sun (no pipeline runs); next anchor = Monday
    runner_anchor_session[0] = _date(2026, 5, 11)
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 11, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    # Per-trade distinct sessions:
    sessions_per_trade = conn.execute(
        "SELECT trade_id, GROUP_CONCAT(DISTINCT data_asof_session) "
        "FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot' "
        "GROUP BY trade_id ORDER BY trade_id"
    ).fetchall()
    for trade_id, sessions_csv in sessions_per_trade:
        sessions = sorted(sessions_csv.split(","))
        assert sessions == ["2026-05-08", "2026-05-11"], (
            f"trade {trade_id} got sessions {sessions!r}; "
            "expected exactly the two run anchors (no back-fill of Sat/Sun)"
        )


def test_step_failure_does_not_abort_pipeline(synthetic_lease_and_trades, monkeypatch, caplog):
    """Cadence-step semantics: synthetic failure in compute logs warning;
    rest of pipeline (other open trades) still emit snapshots.

    EXACT pre-fix (without try/except): RuntimeError propagates; 0 snapshots.
    EXACT post-fix: warning logged for failed trade; OTHER trades still emit."""
    lease, conn = synthetic_lease_and_trades

    def fail_for_trade_1(conn_inner, *, trade_id, **kwargs):
        if trade_id == 1:
            raise RuntimeError("synthetic-trade-1-failure")
        # For trade_id != 1, return a minimal valid snapshot dict:
        return {
            "review_date": "2026-05-07", "data_asof_session": "2026-05-07",
            "created_at": "2026-05-07T18:00:00",
            "mfe_mae_precision_level": "daily_approximate",
            "pipeline_run_id": kwargs.get("pipeline_run_id"),
            "current_price": 50.0, "current_stop": 45.0,
            "current_size": 100.0, "current_avg_cost": 50.0,
            "open_R_effective": 0.0, "open_MFE_R_to_date": 0.0,
            "open_MAE_R_to_date": 0.0, "intraday_high": 51.0,
            "intraday_low": 49.0,
            "position_capital_utilization_pct": 0.667,
            "position_capital_denominator_dollars": 7500.0,
            "position_portfolio_heat_contribution_dollars": 500.0,
            "maturity_stage": "pre_+1.5R",
            "trail_MA_candidate_price": None,
            "trail_MA_period_days": None,
            "trail_MA_eligibility_flag": None,
        }
    monkeypatch.setattr(
        "swing.trades.daily_management.compute_daily_approximate_snapshot",
        fail_for_trade_1,
    )

    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=Path("/dev/null"),
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )
    # Trade 2 (ZZ) snapshot exists; trade 1 (DHC) has none:
    rows = conn.execute(
        "SELECT trade_id FROM daily_management_records "
        "WHERE record_type = 'daily_snapshot'"
    ).fetchall()
    assert [r[0] for r in rows] == [2]
    # Warning was logged:
    assert any("synthetic-trade-1-failure" in r.message for r in caplog.records)


def test_step_re_raises_LeaseRevoked(synthetic_lease_and_trades, monkeypatch):
    """Codex R2 Major #5 discriminating test: LeaseRevokedError MUST propagate
    (force-clear authoritative); the broad `except Exception` MUST NOT catch it.

    EXACT pre-fix expected (broad-except only): no exception raised; warning logged.
    EXACT post-fix expected: LeaseRevokedError propagates out of _step_daily_management."""
    from swing.pipeline.lease import LeaseRevokedError
    lease, conn = synthetic_lease_and_trades

    def raise_revoked(conn_inner, *, trade_id, **kwargs):
        raise LeaseRevokedError("synthetic-revoke-during-snapshot")
    monkeypatch.setattr(
        "swing.trades.daily_management.compute_daily_approximate_snapshot",
        raise_revoked,
    )

    with pytest.raises(LeaseRevokedError, match="synthetic-revoke-during-snapshot"):
        _step_daily_management(
            lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
            eval_run_id=99, archive_history_days=120,
            ohlcv_archive_dir=Path("/dev/null"),
            capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
        )
```

- [ ] **Step 2: Implement `_step_daily_management`**

```python
def _step_daily_management(
    *, lease, run_now: datetime, eval_run_id: int,
    archive_history_days: int, ohlcv_archive_dir,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,
) -> None:
    """Spec §4.1 step body. Lands AFTER _step_evaluate.

    Cadence-step semantics: per-trade failures logged + pipeline continues —
    EXCEPT for LeaseRevokedError, which MUST re-raise so force-clear remains
    authoritative (Codex R2 Major #5 fix; mirrors all existing pipeline
    steps' LeaseRevokedError discipline at swing/pipeline/runner.py:274/283/300/etc.).

    Codex R4 Major #4 fix: `last_completed_session` is imported at module
    scope of `swing/pipeline/runner.py` (line 35 — verified) — use the
    module-scope name directly, do NOT re-import inside the function. Tests
    monkeypatch the runner-module-scope name `swing.pipeline.runner.last_completed_session`.
    """
    from swing.pipeline.lease import LeaseRevokedError
    from swing.trades.daily_management import (
        compute_daily_approximate_snapshot,
    )
    from swing.data.repos.daily_management import upsert_snapshot
    from swing.data.repos.trades import list_open_trades
    from swing.trades.state import state_transition

    asof_session = last_completed_session(run_now)
    with lease.fenced_write() as conn:
        trades = list_open_trades(conn)
    for trade in trades:
        try:
            # Codex R5 Major #2 fix: lease.fenced_write() already opens an
            # explicit BEGIN IMMEDIATE / COMMIT block in autocommit mode
            # (verified at swing/pipeline/lease.py:99-143). Nesting `with conn:`
            # inside the yielded connection would call conn.commit() on
            # context-exit, prematurely committing the fenced transaction and
            # leaving fenced_write's outer COMMIT/ROLLBACK pointing at no
            # active transaction. ALL writes for a single trade go inside the
            # fenced_write block WITHOUT an inner `with conn:`.
            with lease.fenced_write() as conn:
                fields = compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id,
                    asof_session=asof_session,
                    run_now=run_now,
                    ohlcv_archive_dir=ohlcv_archive_dir,
                    archive_history_days=archive_history_days,
                    pipeline_run_id=eval_run_id,
                    capital_floor_dollars=capital_floor_dollars,
                    trail_MA_period_days_default=trail_MA_period_days_default,
                )
                if fields is None:
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): archive returned None",
                        trade.id, trade.ticker,
                    )
                    continue
                upsert_snapshot(conn, trade_id=trade.id, snapshot_fields=fields)
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=fields["created_at"],
                        rationale="first_daily_management_record",
                    )
        except LeaseRevokedError:
            # Force-clear authoritative — propagate immediately. Codex R2 M5.
            raise
        except Exception as exc:
            log.warning(
                "daily_management step failed for trade %s: %s", trade.id, exc,
            )
```

Wire call site in `run_pipeline_internal` — AFTER `eval_run_id = _step_evaluate(...)` line. Mirror existing `LeaseRevokedError` `except` branches at lines 274/283/300/314/327/341/356/371 — the outer caller already handles the propagated `LeaseRevokedError`.

Run all 7 tests → PASS.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(pipeline): Task 4.0 — _step_daily_management (cadence-step semantics; idempotent UPSERT; gap-flagged; LeaseRevokedError re-raise)"
```

**Estimated test count delta:** +7

---

### Task 4.1: Pipeline integration end-to-end test

**Files:**
- Create: `tests/integration/test_phase8_pipeline_walkthrough.py`

- [ ] **Step 1: Write failing end-to-end test (Codex R1 Major #3 + R4 Major #3 fix — concrete fixtures + correct shipped signature)**

```python
def test_phase8_pipeline_emits_snapshots_for_open_trades_only(tmp_path, monkeypatch):
    """Full pipeline run with 3 open + 1 closed trade.

    EXACT post-fix expected: SELECT trade_id from daily_management_records
    WHERE record_type='daily_snapshot' returns exactly the 3 open trades' ids;
    closed trade has 0 rows.

    Codex R4 Major #3 + R5 Major #1 fix: run_pipeline_internal's shipped
    signature is `run_pipeline_internal(*, cfg: Config, trigger: str)`
    (verified at swing/pipeline/runner.py:156). The lease is acquired internally
    via `acquire_lease(*, db_path, trigger, data_asof_date, action_session_date,
    block_threshold_seconds=120, finviz_csv_path=None, rs_universe_version=None,
    rs_universe_hash=None)` — keyword-only — verified at swing/pipeline/lease.py:146.
    The fixture monkeypatches with `lambda **kw: lease` to absorb arbitrary
    kwargs so the patch is robust against future signature changes. ONLY real
    shipped step names are patched: `_step_finviz_fetch`, `_step_charts`,
    `_step_export`, `_step_review_log_cadence` (per swing/pipeline/runner.py).
    There is NO `_step_weather_runs` in the shipped runner — weather runs
    inside _step_evaluate.
    """
    db_path, conn, lease, monkey = _setup_synthetic_pipeline_fixture(tmp_path, monkeypatch)
    monkey.setattr("swing.pipeline.runner.acquire_lease", lambda **kw: lease)
    # Codex R8 Major #1 fix: also patch the Finviz pre-step here (mirror tests
    # #2 and #3). Empirical signatures verified — see those tests' inline
    # comments. Without these two patches, the runner would attempt to scan
    # data/finviz-inbox/ before reaching _step_daily_management.
    from pathlib import Path as _Path
    from swing.pipeline.finviz_schema import ValidationResult as _VR
    monkey.setattr(
        "swing.pipeline.runner.select_csv",
        lambda *a, **kw: _Path("synthetic.csv"),
        raising=True,
    )
    monkey.setattr(
        "swing.pipeline.runner.validate_csv",
        lambda *a, **kw: _VR(is_valid=True, reasons=[], row_count=0),
        raising=True,
    )
    # Patch real shipped steps to no-op so the test focuses on
    # _step_daily_management integration:
    monkey.setattr("swing.pipeline.runner._step_finviz_fetch", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_charts", lambda **kw: [])
    monkey.setattr("swing.pipeline.runner._step_export", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_review_log_cadence", lambda **kw: None)
    from swing.pipeline.runner import run_pipeline_internal
    # Codex R4 Major #3 + R5 Major #1 + R6 m2 fix: shipped signature is
    # `run_pipeline_internal(*, cfg: Config, trigger: str)`. The lease is
    # acquired internally via the keyword-only `acquire_lease(*, db_path,
    # trigger, data_asof_date, action_session_date, ...)`. Tests configure
    # synthetic state via cfg + monkeypatched OHLCV + monkeypatched
    # acquire_lease (above); trigger='manual' or 'scheduled' per shipped enum:
    run_pipeline_internal(cfg=_minimal_cfg(db_path=db_path), trigger="manual")
    rows = conn.execute(
        "SELECT trade_id FROM daily_management_records "
        "WHERE record_type='daily_snapshot' ORDER BY trade_id"
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2]  # open trades only


def test_phase8_pipeline_second_same_day_run_upserts(tmp_path, monkeypatch):
    """Second run updates existing rows; PK preserved.

    EXACT post-fix expected: management_record_id of trade 1's snapshot
    after second run == its id after first run.

    Codex R5 Major #1 fix: same monkeypatch discipline as test #1 — patch
    `acquire_lease` with `lambda **kw: lease` + patch real shipped step names
    only. The fixture `_setup_synthetic_pipeline_fixture` returns a `monkey`
    handle that the test uses to apply these patches BEFORE invoking
    `run_pipeline_internal`."""
    db_path, conn, lease, monkey = _setup_synthetic_pipeline_fixture(tmp_path, monkeypatch)
    monkey.setattr("swing.pipeline.runner.acquire_lease", lambda **kw: lease)
    # Codex R6 Major #1 + R7 Major #1 fix: shipped runner performs Finviz
    # inbox CSV selection + validation BEFORE _step_finviz_fetch and BEFORE
    # evaluation. Empirical signatures (verified at swing/pipeline/runner.py:
    # 42-43, 210, 216):
    #   `select_csv(inbox_dir: Path) -> Path`         (positional arg)
    #   `validate_csv(path: Path) -> ValidationResult` (positional arg)
    # ValidationResult is the dataclass at swing/pipeline/finviz_schema.py:19-23
    # with fields (is_valid: bool, reasons: list[str], row_count: int).
    # Lambdas use `*a, **kw` to accept positional + keyword args; validate_csv
    # returns a ValidationResult-shaped object so the runner's `.is_valid`
    # access works:
    from swing.pipeline.finviz_schema import ValidationResult as _VR
    monkey.setattr(
        "swing.pipeline.runner.select_csv",
        lambda *a, **kw: Path("synthetic.csv"),
        raising=True,
    )
    monkey.setattr(
        "swing.pipeline.runner.validate_csv",
        lambda *a, **kw: _VR(is_valid=True, reasons=[], row_count=0),
        raising=True,
    )
    monkey.setattr("swing.pipeline.runner._step_finviz_fetch", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_charts", lambda **kw: [])
    monkey.setattr("swing.pipeline.runner._step_export", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_review_log_cadence", lambda **kw: None)
    from swing.pipeline.runner import run_pipeline_internal

    run_pipeline_internal(cfg=_minimal_cfg(db_path=db_path), trigger="manual")
    rec1 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]

    run_pipeline_internal(cfg=_minimal_cfg(db_path=db_path), trigger="manual")
    rec2 = conn.execute(
        "SELECT management_record_id FROM daily_management_records "
        "WHERE trade_id = 1"
    ).fetchone()[0]
    assert rec1 == rec2


def test_phase8_pipeline_record_event_log_after_run_links_correctly(tmp_path, monkeypatch):
    """Operator-emit event_log AFTER pipeline run; verify linked_trade_event_id
    matches a real trade_events row.

    EXACT post-fix expected: event_log row's linked_trade_event_id is non-NULL
    AND the trade_events row at that id has event_type='stop_adjust'.

    Codex R5 Major #1 fix: same monkeypatch discipline as tests #1 and #2."""
    db_path, conn, lease, monkey = _setup_synthetic_pipeline_fixture(tmp_path, monkeypatch)
    monkey.setattr("swing.pipeline.runner.acquire_lease", lambda **kw: lease)
    # Codex R6 Major #1 + R7 Major #1 fix: shipped runner performs Finviz
    # inbox CSV selection + validation BEFORE _step_finviz_fetch and BEFORE
    # evaluation. Empirical signatures (verified at swing/pipeline/runner.py:
    # 42-43, 210, 216):
    #   `select_csv(inbox_dir: Path) -> Path`         (positional arg)
    #   `validate_csv(path: Path) -> ValidationResult` (positional arg)
    # ValidationResult is the dataclass at swing/pipeline/finviz_schema.py:19-23
    # with fields (is_valid: bool, reasons: list[str], row_count: int).
    # Lambdas use `*a, **kw` to accept positional + keyword args; validate_csv
    # returns a ValidationResult-shaped object so the runner's `.is_valid`
    # access works:
    from swing.pipeline.finviz_schema import ValidationResult as _VR
    monkey.setattr(
        "swing.pipeline.runner.select_csv",
        lambda *a, **kw: Path("synthetic.csv"),
        raising=True,
    )
    monkey.setattr(
        "swing.pipeline.runner.validate_csv",
        lambda *a, **kw: _VR(is_valid=True, reasons=[], row_count=0),
        raising=True,
    )
    monkey.setattr("swing.pipeline.runner._step_finviz_fetch", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_charts", lambda **kw: [])
    monkey.setattr("swing.pipeline.runner._step_export", lambda **kw: None)
    monkey.setattr("swing.pipeline.runner._step_review_log_cadence", lambda **kw: None)
    from swing.pipeline.runner import run_pipeline_internal

    run_pipeline_internal(cfg=_minimal_cfg(db_path=db_path), trigger="manual")

    from swing.trades.daily_management import record_event_log
    req = _build_event_log_request(
        trade_id=1, stop_changed=1,
        prior_stop=92.0, new_stop=95.0,
        stop_change_reason="trail_to_breakout_low",
        action_taken="move_stop", action_reason="breakout_confirmed",
        rule_violation_suspected=0, emotional_state='["calm"]',
        created_at="2026-05-07T19:00:00",
    )
    event_log_id = record_event_log(conn, trade_id=1, req=req)

    row = conn.execute(
        "SELECT linked_trade_event_id FROM daily_management_records "
        "WHERE management_record_id = ?", (event_log_id,)
    ).fetchone()
    linked_id = row[0]
    assert linked_id is not None
    te_type = conn.execute(
        "SELECT event_type FROM trade_events WHERE id = ?", (linked_id,)
    ).fetchone()[0]
    assert te_type == "stop_adjust"
```

- [ ] **Step 2: Run + commit**

```bash
git commit -m "test(integration): Task 4.1 — phase8 pipeline walkthrough end-to-end"
```

**Estimated test count delta:** +3

---

### Task 4.2: Briefing extension — "Daily Management Snapshot" subsection (spec §7.4 LOCKED V1; Codex R1 Major #1 + R2 Major #1 + R2 Major #2 fix)

**Files (verified empirically against the shipped briefing surface — R2 Major #2 fix):**
- Modify: `swing/rendering/view_models.py` — extend `BriefingViewModel` with `daily_management_snapshots: list[DailyManagementSnapshotRowVM]` field; add the row dataclass with EXACT fields `ticker / data_asof_session / open_MFE_R_to_date / open_MAE_R_to_date / maturity_stage / trail_MA_eligibility_flag` per spec §7.4. **Ticker resolution (Codex R3 m2):** `DailyManagementRecord` carries `trade_id` only — NOT `ticker`. The builder JOINs to `inputs.open_trades` by `trade_id` to resolve the ticker for rendering. **Orphan policy:** snapshots whose `trade_id` is NOT in `{t.id for t in inputs.open_trades}` are FILTERED OUT (closed-trade snapshots belong to Phase 6 post-mortem surfaces, not Phase 8 briefing). Tested by `test_briefing_md_renders_orphan_snapshot_disjoint_from_open_trades_safely` in T4.2.
- Modify: `swing/rendering/briefing.py` — extend `BriefingInputs` dataclass with `daily_management_active_snapshots: list[DailyManagementRecord]` field (sourced from `list_open_position_active_snapshots(conn)`); add `_daily_management_snapshots(inputs)` private builder mirroring `_open_positions` pattern at line 98 (which JOINs `inputs.open_trades` against snapshots by `trade_id` for ticker resolution + orphan filter); wire into `build_briefing_view_model` at line 170.
- Modify: `swing/rendering/briefing_md.py` — emit "## Daily Management Snapshot" subsection iterating `vm.daily_management_snapshots`; mirror existing per-trade table style (column headers + per-row data).
- Modify: `swing/rendering/templates/briefing.html.j2` — add HTML mirror section with `id="daily-management-snapshot"` heading + table.
- Modify: `swing/rendering/exporter.py` — verify the wiring at line 86 already passes `vm` through; no change unless `BriefingInputs` construction site needs the new field plumbed.
- Modify: `swing/pipeline/runner.py:_step_export` — populate the new `BriefingInputs.daily_management_active_snapshots` field by calling `swing.data.repos.daily_management.list_open_position_active_snapshots(conn)` inside the existing `with lease.fenced_write() as conn:` block.
- Create: `tests/integration/test_briefing_daily_management_section.py`

**Spec §7.4 LOCKED:** "the existing nightly briefing (`briefing.md` + `briefing.html`) gains a 'Daily Management Snapshot' subsection per open trade — current state at `data_asof_session`, MFE/MAE-to-date, maturity_stage, trail-MA eligibility flag. Single-table per trade; no analytical aggregation."

- [ ] **Step 1: Write failing tests asserting the subsection renders with EXACT literals (R2 Major #1 fix — concrete expected output, not "in text" loose containment)**

```python
# tests/integration/test_briefing_daily_management_section.py
"""Spec §7.4 LOCKED: briefing.md + briefing.html gain a 'Daily Management
Snapshot' subsection per open trade after Phase 8.

R2 Major #1 fix: tests assert EXACT markdown structure, not loose
substring containment."""
from datetime import datetime
from pathlib import Path

import pytest

from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.html_renderer import render_briefing_html


def _build_inputs_with_snapshots(open_trades, active_snapshots, **overrides):
    """Construct BriefingInputs with the new daily_management_active_snapshots
    field populated. Mirror existing test fixtures' construction."""
    return BriefingInputs(
        # ... fill in existing required fields per BriefingInputs dataclass
        # signature; the executing-plans subagent reads the shipped dataclass
        # and supplies the minimal required values (per Phase 6/7 fixture
        # pattern).
        open_trades=open_trades,
        daily_management_active_snapshots=active_snapshots,
        **overrides,
    )


def test_briefing_md_emits_section_heading_and_per_trade_row():
    """EXACT pre-fix expected: render_briefing_md output does NOT contain
    '## Daily Management Snapshot'.
    EXACT post-fix expected: output contains literal heading
    '## Daily Management Snapshot' followed by a markdown table with
    column header row 'Ticker | As-of session | MFE-to-date (R) |
    MAE-to-date (R) | Maturity stage | Trail-MA eligible' and one data
    row per open trade."""
    snap = _make_snapshot_row(
        trade_id=1, data_asof_session="2026-05-07",  # ticker resolved from open_trades JOIN per §B file map / Codex R4 M5 fix
        open_MFE_R_to_date=1.50, open_MAE_R_to_date=0.20,
        maturity_stage="+1.5R_to_+2R", trail_MA_eligibility_flag=0,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    vm = build_briefing_view_model(inputs)
    md = render_briefing_md(vm)

    # EXACT heading literal:
    assert "## Daily Management Snapshot" in md

    # EXACT column header row (literal markdown pipe format):
    assert (
        "| Ticker | As-of session | MFE-to-date (R) | "
        "MAE-to-date (R) | Maturity stage | Trail-MA eligible |"
    ) in md

    # EXACT per-trade row literal:
    assert (
        "| DHC | 2026-05-07 | 1.50 | 0.20 | +1.5R_to_+2R | no |"
    ) in md


def test_briefing_md_subsection_renders_trail_MA_eligible_yes_when_flag_set():
    """EXACT post-fix expected: when trail_MA_eligibility_flag=1, the data row
    contains the literal cell '| yes |' in the trail-MA-eligible column."""
    snap = _make_snapshot_row(
        trade_id=1, data_asof_session="2026-05-07",  # ticker resolved from open_trades JOIN per §B file map / Codex R4 M5 fix
        open_MFE_R_to_date=2.50, open_MAE_R_to_date=0.30,
        maturity_stage=">=+2R_trail_eligible", trail_MA_eligibility_flag=1,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert (
        "| DHC | 2026-05-07 | 2.50 | 0.30 | >=+2R_trail_eligible | yes |"
    ) in md


def test_briefing_md_emits_no_open_positions_marker_when_no_open_trades():
    """EXACT post-fix expected: with NO open trades AND no snapshots, the
    subsection heading still appears (stable section-anchor) followed by
    literal `_No open positions to manage._`. Discriminates empty state."""
    inputs = _build_inputs_with_snapshots(
        open_trades=[], active_snapshots=[],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "## Daily Management Snapshot" in md
    assert "_No open positions to manage._" in md
    # No data row pipe-format leak:
    assert "| Ticker | As-of session" not in md


def test_briefing_md_distinguishes_open_trades_with_no_snapshots_emitted(
    monkeypatch,
):
    """Codex R3 Major #3 fix: when open trades EXIST but the
    daily-management pipeline step skipped/failed (so no snapshot rows for
    those trades), the briefing MUST emit a DIFFERENT marker than the
    no-open-positions case — operator-actionable signal that something
    went wrong with the snapshot path.

    EXACT pre-fix expected (without distinguishing): same `_No open
    positions to manage._` marker would render despite open trades existing
    — operator misled into thinking there are no positions.

    EXACT post-fix expected: with open_trades=[DHC, ZZ] but
    daily_management_active_snapshots=[], the rendered MD contains the
    literal `_2 open positions; no daily-management snapshot available
    (pipeline step skipped or failed)._` and DOES NOT contain the
    no-open-positions marker."""
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1), _open_trade_for(ticker="ZZ", trade_id=2)],
        active_snapshots=[],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "## Daily Management Snapshot" in md
    assert (
        "_2 open positions; no daily-management snapshot available "
        "(pipeline step skipped or failed)._"
    ) in md
    assert "_No open positions to manage._" not in md


def test_briefing_md_renders_orphan_snapshot_disjoint_from_open_trades_safely(
    monkeypatch,
):
    """Codex R3 Minor #2 follow-on: a snapshot row whose trade_id is NOT in
    open_trades (orphan — trade was just closed) MUST be filtered out of the
    rendered subsection (the table is per-OPEN-position; closed trades have
    their own post-mortem surface).

    EXACT post-fix expected: snapshot row for closed-trade ticker absent;
    only open-trade snapshots render."""
    # Codex R4 Major #5 fix: snapshots carry trade_id only; ticker resolves
    # via JOIN to inputs.open_trades. Orphan = trade_id NOT in open_trades.
    snap_open = _make_snapshot_row(trade_id=1, ...)
    snap_orphan = _make_snapshot_row(trade_id=99, ...)
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],  # only id=1 is open
        active_snapshots=[snap_open, snap_orphan],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "DHC" in md  # the open trade renders
    # Orphan trade_id=99 has no matching open_trades entry → filtered out;
    # since DailyManagementRecord has no ticker column, the orphan row simply
    # won't produce a rendered DailyManagementSnapshotRowVM:
    n_rows = md.count("\n| ") - 1  # rough row count after header pipe
    # Strict assertion: only 1 ticker rendered in the table:
    assert md.count("| DHC |") == 1


def test_briefing_html_emits_section_with_id_and_per_trade_row():
    """EXACT post-fix expected: HTML output contains
    `<section id="daily-management-snapshot">` element AND a `<td>DHC</td>`
    cell AND a `<td>+1.5R_to_+2R</td>` cell."""
    snap = _make_snapshot_row(
        trade_id=1, data_asof_session="2026-05-07",  # ticker resolved from open_trades JOIN per §B file map / Codex R4 M5 fix
        open_MFE_R_to_date=1.50, open_MAE_R_to_date=0.20,
        maturity_stage="+1.5R_to_+2R", trail_MA_eligibility_flag=0,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    html = render_briefing_html(build_briefing_view_model(inputs))
    assert '<section id="daily-management-snapshot">' in html
    assert "<td>DHC</td>" in html
    assert "<td>2026-05-07</td>" in html
    assert "<td>+1.5R_to_+2R</td>" in html


# Helpers (executing-plans subagent expands per shipped dataclass shapes):
#
# `_make_snapshot_row(*, trade_id, **fields)` — constructs DailyManagementRecord;
#   does NOT accept `ticker` (Codex R4 Major #5 fix — schema has no ticker column).
# `_open_trade_for(*, ticker, trade_id, **fields)` — constructs Trade; ticker
#   here is the source-of-truth for rendering, accessed via JOIN by trade_id.
def _make_snapshot_row(*, trade_id: int, **fields): ...
def _open_trade_for(*, ticker: str, trade_id: int = 1, **fields): ...
```

(`...` markers in helper builder bodies refer to constructor calls expanded against the shipped `DailyManagementRecord` + `Trade` dataclasses; the test ASSERTIONS contain EXACT pre-fix and post-fix expected literal strings per Codex R1 M3 + R2 M1.)

- [ ] **Step 2: Implement subsection in briefing emitter**

Per the file-map updates above:
1. Add `DailyManagementSnapshotRowVM` dataclass to `swing/rendering/view_models.py` with the 6 EXACT fields.
2. Extend `BriefingInputs` (`swing/rendering/briefing.py`) with `daily_management_active_snapshots: list[DailyManagementRecord]` (default `()` for back-compat).
3. Add private builder `_daily_management_snapshots(inputs)` mirroring `_open_positions` (line 98) — returns `list[DailyManagementSnapshotRowVM]`.
4. Wire into `build_briefing_view_model` (line 170 onwards) — add field to BriefingViewModel construction.
5. Update `render_briefing_md` (`swing/rendering/briefing_md.py`) — emit the subsection between existing per-trade and watchlist sections (or per existing structural-position convention; mirror Phase 6/7 pattern).
6. Update `templates/briefing.html.j2` — add `<section id="daily-management-snapshot">` block iterating `vm.daily_management_snapshots`.
7. Update `_step_export` in `swing/pipeline/runner.py` to populate the new BriefingInputs field via `list_open_position_active_snapshots(conn)`.

- [ ] **Step 3: Run + commit**

```bash
git commit -m "feat(pipeline): Task 4.2 — briefing 'Daily Management Snapshot' subsection (spec §7.4 LOCKED V1)"
```

ACCEPTANCE:
- 6 new tests pass (per-trade subsection in MD; trail-MA-eligible variant; no-open-positions empty-state; open-trades-but-no-snapshots distinguishing marker per Codex R3 M3; orphan-snapshot filtering per Codex R3 m2; HTML mirror).
- Subsection renders during the canonical `swing pipeline run` end-to-end run (operator-witnessed in T7.0 step 3).

VERIFY COMMAND(S):
```bash
python -m pytest tests/integration/test_briefing_daily_management_section.py -q
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4\.2' main..HEAD
```

**Estimated test count delta:** +4

---

### Task 5.0: Web POST `/trades/{id}/daily-management/event`

**Files:**
- Modify: `swing/web/routes/trades.py`
- Create: `tests/web/test_daily_management_event_route.py`
- Modify: `swing/web/view_models/trades.py` (add `EventLogFormVM`)
- Create: `swing/web/templates/partials/daily_management_event_form.html.j2`

- [ ] **Step 1: Write failing route tests**

Tests cover (per Phase 5 + Phase 6 lessons):
- HX-Request header propagation (form has `hx-headers='{"HX-Request": "true"}'`).
- Success-path: 204 + `HX-Redirect: /trades/{id}` (NOT 303).
- HX-Redirect target route IS REGISTERED (Phase 6 R5 I3 lesson — `assert any(r.path matches "/trades/{trade_id}" for r in app.routes)`).
- Validation failure: 422 + form re-render with error.
- Side-effect: event_log row written; if stop_changed=1, trade_events stop_adjust row written.

```python
# tests/web/test_daily_management_event_route.py (Codex R1 Major #3 — concrete bodies)
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.web.app import app as fastapi_app
from swing.data.db import ensure_schema


@pytest.fixture
def client_with_seeded_trade(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "phase8.db"
    conn = ensure_schema(db_path)
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                entry_price=100.0, initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
                pre_trade_locked_at="2026-05-01T09:30:00")
    conn.commit()
    conn.close()
    monkeypatch.setenv("SWING_DB_PATH", str(db_path))
    with TestClient(fastapi_app) as client:
        yield client


def test_event_log_post_success_returns_204_with_HX_Redirect(client_with_seeded_trade):
    """EXACT post-fix expected: status 204; HX-Redirect: /trades/1; event_log
    row exists in DB after the call."""
    response = client_with_seeded_trade.post(
        "/trades/1/daily-management/event",
        data={
            "stop_changed": "0",
            "action_taken": "hold",
            "rule_violation_suspected": "0",
            "emotional_state": '["calm"]',
            "created_at": "2026-05-07T18:00:00",
            "review_date": "2026-05-07",
            "data_asof_session": "2026-05-07",
            "mfe_mae_precision_level": "daily_approximate",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/trades/1"


def test_event_log_post_HX_Redirect_target_route_registered():
    """Phase 6 R5 I3 lesson: HX-Redirect target route must exist in app.routes.

    EXACT post-fix expected: at least one route with path beginning '/trades/'
    and containing a path parameter (`{...}`)."""
    paths = {getattr(r, "path", None) for r in fastapi_app.routes}
    assert any(
        p and p.startswith("/trades/") and "{" in p and not p.endswith("/daily-management/event")
        for p in paths
    ), f"no GET /trades/{{trade_id}} target found; routes: {paths}"


def test_event_log_post_validation_failure_returns_422(client_with_seeded_trade):
    """EXACT post-fix expected: stop_changed=1 without new_stop → 422."""
    response = client_with_seeded_trade.post(
        "/trades/1/daily-management/event",
        data={
            "stop_changed": "1",
            # new_stop, prior_stop, stop_change_reason missing
            "action_taken": "move_stop",
            "rule_violation_suspected": "0",
            "emotional_state": '["calm"]',
            "created_at": "2026-05-07T18:00:00",
            "review_date": "2026-05-07",
            "data_asof_session": "2026-05-07",
            "mfe_mae_precision_level": "daily_approximate",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 422


def test_event_log_form_partial_includes_HX_Request_header_propagation(client_with_seeded_trade):
    """Phase 5 R1 M1 lesson: embedded HTMX form must propagate HX-Request via
    `hx-headers='{\"HX-Request\": \"true\"}'`. Otherwise OriginGuard strict-mode
    rejects nested form submits with 403.

    EXACT post-fix expected: form template literal contains the marker."""
    template_path = Path("swing/web/templates/partials/daily_management_event_form.html.j2")
    text = template_path.read_text(encoding="utf-8")
    assert 'hx-headers' in text
    assert '"HX-Request": "true"' in text


def test_event_log_post_writes_event_log_and_stop_adjust_atomically(client_with_seeded_trade):
    """EXACT post-fix expected: stop_changed=1 with all required fields → 204;
    event_log row + linked trade_events row + trades.current_stop updated."""
    response = client_with_seeded_trade.post(
        "/trades/1/daily-management/event",
        data={
            "stop_changed": "1",
            "prior_stop": "92.0",
            "new_stop": "95.0",
            "stop_change_reason": "trail_to_breakout_low",
            "action_taken": "move_stop",
            "action_reason": "breakout_confirmed",
            "rule_violation_suspected": "0",
            "emotional_state": '["calm"]',
            "created_at": "2026-05-07T18:00:00",
            "review_date": "2026-05-07",
            "data_asof_session": "2026-05-07",
            "mfe_mae_precision_level": "daily_approximate",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 204
    # Open the DB and verify side-effects:
    import sqlite3, os
    conn = sqlite3.connect(os.environ["SWING_DB_PATH"])
    try:
        new_stop = conn.execute(
            "SELECT current_stop FROM trades WHERE id = 1").fetchone()[0]
        assert new_stop == 95.0
        # event_log row exists with linked_trade_event_id non-NULL:
        link = conn.execute(
            "SELECT linked_trade_event_id FROM daily_management_records "
            "WHERE trade_id = 1 AND record_type = 'event_log'"
        ).fetchone()[0]
        assert link is not None
    finally:
        conn.close()
```

- [ ] **Step 2: Implement route + form template + VM**

Route handler:

```python
@router.post("/trades/{trade_id}/daily-management/event")
async def daily_management_event_post(
    trade_id: int, request: Request, ...
):
    # Parse form into EventLogRequest:
    form = await request.form()
    req = EventLogRequest.from_form(form, trade_id=trade_id, created_at_utc=...)
    try:
        with connect(cfg.paths.db_path) as conn:
            record_event_log(conn, trade_id=trade_id, req=req)
    except ValidationException as exc:
        # Re-render form with error:
        return TemplateResponse(
            request, "partials/daily_management_event_form.html.j2",
            {"vm": _form_vm_with_error(trade_id, exc)},
            status_code=422,
        )
    # HX-Redirect on success:
    return Response(status_code=204, headers={"HX-Redirect": f"/trades/{trade_id}"})
```

Template fragment per Phase 5 + Phase 6 patterns. `<form>`-rooted; `hx-headers='{"HX-Request": "true"}'` ON the `<form>`.

- [ ] **Step 3: Verify GET /trades/{trade_id} route registered**

If absent, add a minimal handler that returns the per-trade detail page extending base.html.j2; use existing `swing/web/view_models/trades.py:build_trade_detail_vm` if extant else create.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(web): Task 5.0 — POST /trades/{id}/daily-management/event (HX-Redirect; HX-Request propagation)"
```

ACCEPTANCE:
- 5 tests pass.
- Form has `hx-headers='{"HX-Request": "true"}'` (Phase 5 lesson).
- Response is 204 + HX-Redirect (NOT 303; Phase 5 lesson).
- HX-Redirect target route registered (Phase 6 R5 I3 lesson).
- ValidationException → 422 + form re-render.

**Estimated test count delta:** +5

---

### Task 5.1: Dashboard tile + per-trade timeline templates

**Files:**
- Create: `swing/web/templates/partials/daily_management_tile.html.j2`
- Create: `swing/web/templates/partials/daily_management_timeline.html.j2`
- Modify: `swing/web/view_models/dashboard.py` (add `daily_management_tiles`)
- Modify: `swing/web/view_models/trades.py` (add `DailyManagementTileVM` + `DailyManagementTimelineVM`)
- Modify: `swing/web/templates/dashboard.html.j2`
- Create: `tests/web/test_daily_management_tile.py`
- Create: `tests/web/test_daily_management_timeline.py`

- [ ] **Step 1: Failing tests (Codex R1 Major #3 fix — concrete bodies)**

```python
# tests/web/test_daily_management_tile.py
def test_dashboard_tile_reads_live_current_stop_from_trades_row(client, conn):
    """§5.6 read-precedence: live current_stop = trades.current_stop, NOT
    snapshot's stale copy.

    EXACT pre-fix expected (if VM reads snapshot's current_stop): rendered
    HTML contains '92.00' (the snapshot's stale value).
    EXACT post-fix expected: rendered HTML contains '95.00' (the live value
    from trades-row updated AFTER the snapshot)."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                current_stop=92.0)
    # Insert snapshot with stale current_stop=92.0:
    insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "current_stop": 92.0, ...,
    })
    # Update trades-row to a different value (simulating mid-session stop_adjust):
    conn.execute("UPDATE trades SET current_stop = 95.0 WHERE id = 1")
    conn.commit()
    # Render dashboard:
    response = client.get("/")
    assert response.status_code == 200
    assert "95.00" in response.text
    assert "92.00" not in response.text


def test_dashboard_tile_trail_MA_eligibility_badge_visible_only_when_TRUE(client, conn):
    """EXACT post-fix expected: badge text 'TRAIL ELIGIBLE' present in DOM
    when trail_MA_eligibility_flag=1; absent otherwise."""
    # Case 1: flag=1
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                current_stop=92.0)
    insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "maturity_stage": ">=+2R_trail_eligible",
        "trail_MA_candidate_price": 95.0, "trail_MA_eligibility_flag": 1, ...,
    })
    response = client.get("/")
    assert "TRAIL ELIGIBLE" in response.text or "trail-MA eligible" in response.text.lower()

    # Case 2: flag=0 (different trade) — badge absent on that row
    _seed_trade(conn, trade_id=2, ticker="ZZ", state="managing",
                current_stop=49.0)
    insert_snapshot(conn, trade_id=2, snapshot_fields={
        ..., "maturity_stage": "pre_+1.5R", "trail_MA_eligibility_flag": 0, ...,
    })
    response = client.get("/")
    # Verify we can find a ZZ row that does NOT contain the badge:
    import re
    zz_row_match = re.search(
        r"<tr[^>]*>[^<]*ZZ[^<]*?</tr>", response.text, re.DOTALL,
    )
    if zz_row_match:
        zz_row_text = zz_row_match.group(0)
        assert "TRAIL ELIGIBLE" not in zz_row_text


def test_dashboard_tile_planned_target_R_renders_dash_when_NULL(client, conn):
    """EXACT post-fix expected: trades.planned_target_R IS NULL → '—' in DOM."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing",
                current_stop=92.0, planned_target_R=None)
    insert_snapshot(conn, trade_id=1, snapshot_fields={...})
    response = client.get("/")
    assert "—" in response.text  # em-dash placeholder


def test_dashboard_tile_capital_utilization_PROVISIONAL_marker(client, conn):
    """V1 provisional fallback marker visible per spec §10.5.

    EXACT post-fix expected: text 'PROVISIONAL' (or aria-label / class containing
    that token) appears on the capital utilization badge."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
    insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "position_capital_utilization_pct": 0.72,
        "position_capital_denominator_dollars": 7500.0, ...,
    })
    response = client.get("/")
    assert "PROVISIONAL" in response.text or "provisional" in response.text


# tests/web/test_daily_management_timeline.py
def test_timeline_orders_chronologically_with_tiebreak(client, conn):
    """Spec §7.2: ORDER BY review_date ASC, created_at ASC, management_record_id ASC.

    EXACT post-fix expected: two same-day event_log rows with same created_at
    render in management_record_id ASC order in the rendered HTML."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
    el_a = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_a["created_at"] = "2026-05-07T10:00:00"
    el_a["management_notes"] = "FIRST_NOTE_MARKER"
    rec_a = insert_event_log(conn, trade_id=1, event_log_fields=el_a)

    el_b = _minimal_event_log_fields(data_asof_session="2026-05-07")
    el_b["created_at"] = "2026-05-07T10:00:00"  # SAME wall-clock
    el_b["management_notes"] = "SECOND_NOTE_MARKER"
    rec_b = insert_event_log(conn, trade_id=1, event_log_fields=el_b)
    assert rec_b > rec_a

    response = client.get("/trades/1")
    body = response.text
    pos_a = body.find("FIRST_NOTE_MARKER")
    pos_b = body.find("SECOND_NOTE_MARKER")
    assert pos_a >= 0 and pos_b >= 0
    assert pos_a < pos_b  # ASC order in DOM


def test_timeline_renders_event_log_and_snapshot_rows_distinctly(client, conn):
    """EXACT post-fix expected: snapshot row contains 'snapshot' (in a
    badge / class / data-attr); event_log row contains 'event'."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
    insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "data_asof_session": "2026-05-07",
        "review_date": "2026-05-07", ...,
    })
    insert_event_log(conn, trade_id=1, event_log_fields={
        ..., "data_asof_session": "2026-05-07",
        "review_date": "2026-05-07", ...,
    })
    response = client.get("/trades/1")
    body = response.text.lower()
    assert "snapshot" in body
    assert "event" in body  # event_log badge


def test_timeline_default_excludes_superseded_rows(client, conn):
    """EXACT post-fix expected: superseded daily_snapshot row content is NOT
    visible in the default rendering."""
    _seed_trade(conn, trade_id=1, ticker="DHC", state="managing")
    rec_id = insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "data_asof_session": "2026-05-07",
        "current_price": 100.0,  # marker price for stale row
        ...,
    })
    conn.execute(
        "UPDATE daily_management_records SET is_superseded = 1 "
        "WHERE management_record_id = ?", (rec_id,))
    insert_snapshot(conn, trade_id=1, snapshot_fields={
        ..., "data_asof_session": "2026-05-07",
        "current_price": 200.0,  # marker price for fresh row
        ...,
    })
    response = client.get("/trades/1")
    body = response.text
    assert "200.00" in body  # fresh active row visible
    assert "100.00" not in body  # superseded row hidden by default
```

(The `...` markers within `_seed_trade` / `_minimal_event_log_fields` / snapshot dict literals refer to the helper bodies / completeness fields documented in T2.0 + T2.2; the executing-plans subagent expands them inline. The TEST ASSERTIONS contain EXACT pre-fix and post-fix expected values per Codex R1 M3 + dispatch brief watch-item 7.)

- [ ] **Step 2: Implement VMs + templates**

`DailyManagementTileVM` dataclass:

```python
@dataclass
class DailyManagementTileVM:
    trade_id: int
    ticker: str
    state: str             # from trades-row (live)
    current_price: float | None    # from snapshot (end-of-session)
    current_stop: float            # from trades-row (live)
    open_R_effective: float | None
    open_MFE_R_to_date: float | None
    open_MAE_R_to_date: float | None
    maturity_stage: str | None
    trail_MA_eligibility_flag: int | None
    position_capital_utilization_pct: float | None
    position_capital_denominator_dollars: float | None
    position_portfolio_heat_contribution_dollars: float | None
    planned_target_R: float | None  # from trades-row
    data_asof_session: str | None
    # 5 base-layout existing-field defaults inherited via base VM dataclass mixin.
```

Build via `list_open_position_active_snapshots(conn) + JOIN trades-row`. Tile template renders per spec §7.1 composition list.

Timeline VM + template per spec §7.2.

- [ ] **Step 3: Run + commit**

```bash
git commit -m "feat(web): Task 5.1 — dashboard tile + per-trade timeline (§5.6 read-precedence ladder)"
```

**Estimated test count delta:** +7

---

### Task 6.0: Cleanup — full suite + ruff + CLAUDE.md update

**Files:**
- Possibly modify: `CLAUDE.md` (add Phase 8 gotchas if any new code-failure-prevention pattern surfaced)
- Possibly modify: `docs/cycle-checklist.md` (operator workflow update if event_log is in daily routine)

- [ ] **Step 1: Full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -10
ruff check swing/ 2>&1 | tail -3
```

Expected:
- ~1941 + 43 = 1984 fast tests (range 1971-2001 if test count delta is in +30 to +60 range).
- ruff baseline 78 errors preserved (or fewer if Phase 8 work happens to improve).

- [ ] **Step 2: Slow suite spot-check (pipeline e2e)**

```bash
python -m pytest -m slow tests/integration/test_phase8_pipeline_walkthrough.py -v
```

Expected: PASS (network-dependent on yfinance; if archive cassette set up, deterministic).

- [ ] **Step 3: CLAUDE.md update**

If Phase 8 surfaced a NEW code-failure-prevention pattern not in current CLAUDE.md, add an entry (per orchestrator-context retention discipline). Likely candidates:

- The §A.1 lesson "service-layer `with conn:` opens a transaction that breaks outer-transaction atomicity; switch to repo-level call when nesting is required" — likely belongs in CLAUDE.md gotchas.
- Per-row-stamp pattern for policy-versioned scalars — already documented in CLAUDE.md (Phase 8 brainstorm gotcha 2026-05-06); confirm + extend if execution surfaced new edge.

- [ ] **Step 4: Final commit + return-report**

```bash
git add CLAUDE.md docs/cycle-checklist.md  # if edited
git commit -m "docs(phase8): Task 6.0 — Phase 8 cleanup + CLAUDE.md gotcha (service-vs-repo nested-transaction)"
```

ACCEPTANCE:
- All fast tests pass.
- Slow integration test passes.
- CLAUDE.md updated if applicable.
- ruff baseline preserved.

VERIFY COMMAND(S):
```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 6\.0' main..HEAD
```

**Estimated test count delta:** 0 (cleanup task)

---

### Task 7.0: Operator-witnessed verification gate (binding per Phase 5 + Phase 6 lessons)

**Files:** none (verification only)

- [ ] **Step 1: Operator-witnessed dashboard tile render**

Operator opens browser at `http://127.0.0.1:8080` (after `swing web`). Verifies:
1. Per-open-trade tile renders (3 trades expected at HEAD `1441109` minus VIR).
2. `current_stop` displayed equals `trades.current_stop` (not snapshot's stale copy if a stop_adjust happened mid-session — synthetic test or operator's actual workflow).
3. `maturity_stage` badge renders (e.g., 'pre_+1.5R' for entry-day trade).
4. `trail_MA_eligibility_flag` badge ABSENT (because trades are not yet at +2R).
5. `planned_target_R` renders '—' (legacy trades; column is NULL).
6. `position_capital_utilization_pct` PROVISIONAL fallback marker visible.

- [ ] **Step 2: Operator-witnessed event_log emission**

Operator clicks per-trade detail page → emits event_log entry with `stop_changed=1, new_stop=X, action_taken='move_stop'`.

Verifies:
1. Form submission completes; browser redirects to `/trades/{id}` (HX-Redirect mechanic works).
2. trades-row `current_stop` = X.
3. `trade_events` row with `event_type='stop_adjust'` exists.
4. `daily_management_records` row with `record_type='event_log'` exists with `linked_trade_event_id` populated.
5. Per-trade timeline drill-down renders the new event_log row distinctly from any same-day snapshot row.

- [ ] **Step 3: Operator-witnessed pipeline run**

Operator runs `swing pipeline run` (verified at writing-plans dispatch via [swing/cli.py:1571](../../swing/cli.py#L1571) — the `pipeline_group.command("run")` registration; Codex R1 Minor #2 fix). Verifies briefing.md "Daily Management Snapshot" subsection exists per spec §7.4 (T4.2 implements; this step verifies the operator-rendered surface matches T4.2's tests).

- [ ] **Step 4: Document verification outcome in return report**

Capture screenshots (or terminal output) of operator-verified state; append to return report.

ACCEPTANCE:
- All 4 verification steps witnessed by operator.
- Operator confirms surface is operator-actionable per spec §7.1 + §7.2 + §7.4.

VERIFY COMMAND(S):
```bash
swing web  # in one terminal
swing pipeline run  # in another
# Operator browser-verifies per Step 1-3
```

**Estimated test count delta:** 0 (verification only)

---

## §K — Self-review checklist (pre-commit per writing-plans skill)

- [x] **Spec coverage:** every spec §3-§7 locked decision has a plan task. Spec §3.1 schema → T1.0; §3.2 single-table-with-discriminator → T1.0 (record_type CHECK); §3.3 indexes + 6-step tier-upgrade → T1.0 + T2.3; §3.4 trades.planned_target_R → T1.0; §4.1 pipeline-step body → T4.0; §4.2 SELECT-then-UPDATE-or-INSERT → T2.3; §4.3 gap-flagged + ON DELETE SET NULL → T1.0 + T4.0; §4.4 record_event_log single-transaction → T3.2; §4.5 last_completed_session anchor → T4.0; §5.1-5.5 state-machine integration → T3.2 + T4.0; §5.6 read-precedence → T5.1; §6 tier-upgrade → T2.3 + T3.1; §7.1 dashboard tile → T5.1; §7.2 timeline → T5.1; §7.4 briefing extension → **T4.2 (Codex R1 Major #1 fix — was previously deferred; now in-scope V1 per spec LOCKED)**.
- [x] **Placeholder scan:** zero `TBD` / `TODO` / "fill in" / "similar to Task N" markers. Every test specifies EXACT pre-impl + post-impl expected values. Every code block contains the actual content (or a representative slice with the explicit invariant being tested called out).
- [x] **Type consistency:** `DailyManagementRecord` dataclass mirrors all 42 columns; `EventLogRequest` ↔ form fields ↔ `event_log_fields` dict ↔ DB schema names align byte-for-byte.
- [x] **§A.1 critical empirical finding documented + drives T3.2 implementation.**
- [x] **§A.2 CLI scope decision documented (V1-defer; web-only).**
- [x] **Subject-only grep with `-E` flag in every task verify-command block (Phase 4+ binding convention).**
- [x] **No SQLite REPLACE in any plan task (CLAUDE.md gotcha 2026-05-06; T2.3 explicit grep-check).**
- [x] **Phase 7 schema-rebuild constraint preservation NOT applicable (T1.0 ALTER TABLE ADD COLUMN ONLY) — flag preserved for any future rebuild.**

---

## §L — Test count projection

| Task | New tests | Notes |
|---|---|---|
| T1.0 | +7 | Migration round-trip + CHECK + index predicate + FK SET NULL |
| T1.1 | +5 | Backup gate + executescript rollback + PRAGMA |
| T2.0 | +4 | insert_snapshot + insert_event_log basics |
| T2.1 | +3 | select_active_snapshot |
| T2.2 | +4 | select_history + timeline + dashboard list |
| T2.3 | +5 | upsert SELECT-then-UPDATE + tier-upgrade 3-tier + ordering |
| T3.0 | +14 | Helpers (8) + service end-to-end (3) + thesis resolution (3) — added aware-tz canonicalization test (Codex R1 M5) |
| T3.1 | +1 | tier_upgrade_to_intraday V2 stub |
| T3.2 | +6 | record_event_log single-transaction (the §A.1 critical) — added no-op-stop guard test (Codex R1 M4) + stale-prior-stop guard test (Codex R4 M2) |
| T4.0 | +7 | _step_daily_management — added LeaseRevokedError re-raise discriminating test (Codex R2 M5) |
| T4.1 | +3 | Pipeline integration end-to-end |
| T4.2 | +6 | Briefing "Daily Management Snapshot" subsection (Codex R1 M1 fix — was deferred, now V1 in-scope per spec §7.4 LOCKED) — added distinguishing-empty-states + orphan-snapshot-filter tests (Codex R3 M3 + m2) |
| T5.0 | +6 | Web POST event — added HX-Request header propagation literal-check + atomic side-effect verification test |
| T5.1 | +7 | Dashboard tile + timeline |
| T6.0 | 0 | Cleanup |
| T7.0 | 0 | Operator-witnessed |

**Subtotal:** +79 (planner-projected post-Codex-R1+R2+R3+R4 fixes)

**Range projection per Phase 6 lesson + brief §2.4:** +30 to +60 was the brief's range; this plan's projection (+79) sits ABOVE the brief's upper bound, reflecting the discriminating-test discipline applied across all 15 active tasks (including T4.2 added per Codex R1 Major #1) plus all R1/R2/R3/R4-fix-driven additions (no-op stop guard; stale-prior-stop guard; aware-tz canonicalization; HX-Request literal check; atomic side-effect verification; LeaseRevokedError re-raise; distinguishing-empty-states; orphan-snapshot filter). Executing-plans dispatch acceptance criteria use the **range +55 to +100**, NOT a point estimate. Recap: do NOT tighten executing-plans dispatch acceptance criteria around +79 — bake the range.

---

## §M — Estimated executing-plans dispatch effort

- T1.0: ~30 min (migration SQL + 7 tests)
- T1.1: ~30 min (5 runner-discipline tests)
- T2.0–2.3: ~2 hours total (16 tests; SELECT-then-UPDATE pattern + tier-upgrade 6-step)
- T3.0: ~2 hours (13 tests; pure helpers + validators + service)
- T3.1: ~10 min (V2 stub)
- T3.2: ~1.5 hours (4 critical discriminating regression tests; the §A.1 empirical resolution)
- T4.0: ~1.5 hours (pipeline-step + 6 tests)
- T4.1: ~30 min (3 integration tests)
- T4.2: ~45 min (briefing subsection emitter + 4 tests; mirrors existing per-trade subsection patterns)
- T5.0: ~1 hour (route + 6 tests; HTMX form + HX-Redirect + atomic side-effect verification)
- T5.1: ~2 hours (tile + timeline + 7 tests; VM + templates + base-layout 5-VM rule check)
- T6.0: ~30 min (cleanup; CLAUDE.md gotcha update)
- T7.0: ~1 hour (operator-witnessed verification + return-report assembly)

**Total:** ~13-15 hours executing-plans dispatch post-Codex-R1 fixes (T4.2 added; T3.0/T3.2/T5.0 expanded with discriminating tests). Still within a 1-day-with-buffer subagent-driven dispatch.

Per-task budgets are GUIDANCE; if a task takes 2× projected, surface in midway return-report rather than time-pressure-shipping.

---

## §N — Done criteria

1. All §J tasks committed on branch `phase8-daily-management`.
2. Fast suite green (~1941 + 55 to 100 = 1996 to 2041 tests; range bake per Codex R1+R2+R3+R4 expansions).
3. Slow integration spot-check passes.
4. ruff baseline preserved.
5. Operator-witnessed verification gate (T7.0) passes.
6. Worktree branch merged to main via `git merge --no-ff` (per 2026-05-02 binding convention).
7. Marker file `.copowers-subagent-active` removed at end of dispatch.
8. Return report covers: Codex review history; three highest-leverage decisions (§A.1 nested-transaction repo-level switch; §A.2 V1-defer CLI; §A.3 module placement); CLI scope decision rationale; task count + test count range projection; open questions for orchestrator triage; spec ambiguities (none expected); capture-need completeness Phase 10 §6.1 cross-reference (all 10 covered per spec §3.5).

---

## Plan-execution choice

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task; review between tasks; fast iteration.

**2. Inline Execution** — execute tasks in this session via `superpowers:executing-plans`; batch with checkpoints.

**Which approach?**

(Default: orchestrator/operator decides at executing-plans dispatch time per cross-phase precedent.)
