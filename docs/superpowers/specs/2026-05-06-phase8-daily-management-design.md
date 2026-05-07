# Phase 8 Daily_Management + MFE/MAE Precision — Design Spec (Brainstorm Output)

**Baseline:** `main` at HEAD `1441109` (Finviz API V1 shipped 2026-05-06); ~1940 fast tests green; schema_version = 15.

**Goal:** Lock the schema shape, capture cadence, lifecycle integration, and read-surface contract for Phase 8 — a per-day Daily_Management snapshot/event-log surface that drives Phase 10's maturity-stage view and freezes per-day MFE/MAE history for closed-trade analytics. RESEARCH-POSTURE-ADJACENT: schema sketches are SCHEMA-LOCKING (writing-plans depends on them) but no migration SQL drafting, no code drafting, no task decomposition.

**Brief:** `docs/phase8-daily-management-brainstorm-brief.md`.

**Sequencing:** Phase 10 brainstorm SHIPPED 2026-05-06 (`a46b458` + `fe6cb45`); its §6.1 enumerates Phase 8 capture-needs the dashboard layer requires — this brainstorm consumes those needs. Execution order is 8 → 9 → 10. **No ship-velocity pressure** (operator confirmed n=2 closed / n=3 open trades = 5 total; metric stability is the binding constraint).

---

## §1 Background, framing, and binding constraints

### §1.1 What this spec produces

A locked daily_management_records table sketch (§3) with column-level types + CHECK semantics + FK relationships + indexes; capture cadence + idempotency + back-fill policy (§4); Phase 7 state-machine integration (§5); MFE/MAE precision-tier semantics + tier-upgrade policy (§6); read-surface contracts for the dashboard tile + per-trade timeline drill-down + journal integration (§7); migration strategy with Phase 7 lesson inheritance (§8); Phase 9 hand-off capture-needs (§9); enumerated open-question set for orchestrator triage (§10); writing-plans entry-criteria checklist (§11).

### §1.2 What this spec does NOT produce (out of scope)

- Migration SQL (`CREATE TABLE` / `ALTER TABLE`) drafting.
- Code drafting (view-models, query implementations, repo functions, route handlers, Jinja templates, Click commands).
- Phase 8 task decomposition into writing-plans dispatches.
- Re-litigation of brief §1 binding constraints (capital tie-up = primary; sample size n=5; daily granularity; trail-MA gating operationally urgent; framework-research-loop posture; operator-paced cadence).
- Re-derivation of Phase 10 §6.1 capture-need list — accepted as given.
- Phase 9 / Phase 10 design.
- Intraday data-source decisions (which provider, which API, which depth) — Schwab API Phase B / future-data-source brainstorm territory. Phase 8 designs the precision-tier ENUM + tier-upgrade policy, agnostic of source.
- Ingestion pipelines for `intraday_estimated` + `intraday_exact` tiers — V1 ships `daily_approximate` only; tiers 2+3 are schema-supported (enum value reserved + tier-upgrade column reserved) but not data-fed.

### §1.3 Binding constraints (orchestrator-distilled, not re-derived)

Per brief §1, the following are accepted as design inputs without re-justification:

1. **Daily snapshots are the right granularity.** Operator-paced cadence; no intraday operator engagement; trail-MA decisions are weekly-or-slower decisions. Intraday is V2+ (schema accommodates; V1 doesn't capture).
2. **Capital tie-up = primary constraint.** $7,500 capital floor; ~5 concurrent positions max. Snapshot row count ceiling: 5 open trades × ~365 sessions/year ≈ 1,825 rows/year — table sizing trivial.
3. **Sample size n=5 total.** Schema MUST NOT prematurely optimize for high-n surfaces. No partitioning, no shardable design, no archival splits in V1.
4. **Trail-MA gating is OPERATIONALLY URGENT.** DHC + CC currently approaching trail-MA decision territory (+1.5R / +2R thresholds). Phase 8 surface is the operator-action prompt; design favors operator-actionability over analytical purity where they tension.
5. **Phase 7 state machine is binding.** Snapshots fire ONLY when `trades.state ∈ {entered, managing, partial_exited}`. Closed trades freeze.
6. **Phase 10 §6.1 capture-need list is binding input.** Every field in §6.1 has a target column in §3.1 OR a justified deferral flagged as open question for orchestrator triage.

### §1.4 v1.2 DROP rules applied

Per `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation" cross-cutting framing, the following v1.2 §7.7 fields are DROPPED for Phase 8:

- **`pre_trade_quality_score` extension to daily_management** — DROPPED. Pipeline asserts thesis; daily snapshots don't re-rate setup quality.
- **Pyramiding R-views** — DROPPED. Single denominator (`planned_risk_budget_dollars`); `open_R_effective` uses the trade's pre-trade-locked risk budget.
- **Drawdown circuit breaker fields** — NOT in Daily_Management; lives in Phase 9 Risk_Policy.

KEPT per §1.4 brief:

- **`emotional_state`** (operator-only field; one of the few v1.2 fields that survives the framework adaptation per existing rule).
- **`rule_violation_suspected` flag** (links to Phase 6 mistake-tag taxonomy on review).
- **`thesis_status` enum** (operator-only field; per v1.2 §4.7).

### §1.5 MFE/MAE precision tier semantics (Phase 10 §3.1 binding)

Three precision tiers per v1.2 §8.6 + Phase 10 §3.1 inventory:

- **`daily_approximate`** — uses daily OHLCV close-of-session high/low from `swing/data/ohlcv_archive`. Cheapest; computable today against shipped infrastructure; ships in V1.
- **`intraday_estimated`** — uses estimated intraday high/low (e.g., yfinance 1-hour bars). NOT shipped V1; gated on intraday data source decision. Schema-reserved enum value.
- **`intraday_exact`** — uses exact intraday tick-or-minute data. NOT shipped V1; gated on Schwab API Phase B (or equivalent intraday data source). Schema-reserved enum value.

V1 captures `daily_approximate` ONLY. V2+ tier-upgrade policy locked in §6.

---

## §2 Vocabulary anchored against shipped surfaces

To avoid drift, this spec uses the field names already shipped in production schema (post-Finviz-API merge `1441109`, schema_version 15):

| Concept | Shipped name | Source |
|---|---|---|
| Trade lifecycle stage | `trades.state` (5-value: `entered` / `managing` / `partial_exited` / `closed` / `reviewed`) | shipped (migration 0014) |
| Pre-trade lock anchor | `trades.pre_trade_locked_at` (TEXT ISO datetime) | shipped (0014) |
| Effective entry basis | `fills.action='entry'` first-by-(fill_datetime, fill_id) per Phase 7 §4.3.1 | shipped (0014) |
| Current position state | `trades.current_size` / `current_avg_cost` / `current_stop` | shipped (0014) |
| Pre-trade risk budget | derived: `(entry_price - initial_stop) * initial_shares` (single risk denominator) | shipped (Phase 7 §4.5) |
| Pipeline run anchor | `pipeline_runs.evaluation_run_id` → FK target | shipped |
| NYSE session date helper | `swing.evaluation.dates.action_session_for_run(now)` (forward) / `last_completed_session(now)` (backward) | shipped |
| OHLCV daily history | `swing.data.ohlcv_archive.read_or_fetch_archive(...)` | shipped (Phase 3) |
| Trade-level audit log | `trade_events` (lifecycle transitions: `entry`/`stop_adjust`/`note`/`exit`/`flag`/`pre_trade_edit`) | shipped (0014) |

**Conceptual distinction (binding):** Phase 7's `trade_events` table audits LIFECYCLE state transitions (entry / stop_adjust / pre_trade_edit / etc.). Phase 8's `daily_management_records` table records PER-DAY MANAGEMENT activity (snapshot + operator review actions). They are SEMANTICALLY DIFFERENT and live in DIFFERENT TABLES — see §3.2 single-table-with-discriminator decision.

**Risk denominator (per §1.4 DROP rule):** `planned_risk_budget_dollars = (entry_price - initial_stop) * initial_shares` is the ONE denominator. `open_R_effective` per snapshot = `(current_price - entry_price) * current_size / planned_risk_budget_dollars`.

**Adverse-positive convention (per Phase 10 §2):** `MAE_R_to_date` is a NON-NEGATIVE proportion (abs of min adverse excursion / risk_per_share). Slippage convention preserved across phases.

---

## §3 Schema sketches (LOCKED)

### §3.1 New table: `daily_management_records`

**Discriminating-record-type semantics (LOCKED — Decision §3.2):** ONE table with `record_type` discriminator (`daily_snapshot` / `event_log`). Single-table-with-discriminator chosen over two-table-split. Rationale in §3.2.

**Column sketch** (column-name + type + CHECK descriptor + FK target; NOT full DDL):

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `management_record_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `trade_id` | INTEGER | NOT NULL | FK → `trades(id)` ON DELETE CASCADE |
| `record_type` | TEXT | NOT NULL | CHECK IN (`daily_snapshot`, `event_log`) |
| `review_date` | TEXT | NOT NULL | ISO date (YYYY-MM-DD); chronology field |
| `data_asof_session` | TEXT | NOT NULL | ISO date; NYSE session date the data anchors on; for daily_snapshot, MUST equal `review_date` (same calendar day for daily-tier capture) |
| `created_at` | TEXT | NOT NULL | ISO datetime; system wall-clock at row insert; naive-UTC per §8 datetime policy |
| `mfe_mae_precision_level` | TEXT | NOT NULL | CHECK IN (`daily_approximate`, `intraday_estimated`, `intraday_exact`) |
| `pipeline_run_id` | INTEGER | nullable | FK → `pipeline_runs(id)`; nullable for CLI/web event_log emissions |
| `is_superseded` | INTEGER | NOT NULL | CHECK IN (0,1) DEFAULT 0; predecessor flag set BEFORE successor row INSERT to free the active-snapshot uniqueness slot (R2 Major #2 fix). Decoupled from the FK pointer so the insert-then-update sequence is feasible. |
| `superseded_by_record_id` | INTEGER | nullable | FK → `daily_management_records(management_record_id)` (self-reference); set AFTER successor row INSERT to record the audit-chain pointer (R2 Major #2 fix — order: UPDATE prior is_superseded=1; INSERT successor; UPDATE prior superseded_by_record_id=last_insert_rowid). |
| **Position-state snapshot fields (NULLABLE on schema; validator REQUIRED for daily_snapshot, OPTIONAL for event_log — see §3.1.1)** | | | |
| `current_price` | REAL | nullable | CHECK > 0 OR NULL |
| `current_stop` | REAL | nullable | CHECK > 0 OR NULL |
| `current_size` | REAL | nullable | CHECK ≥ 0 OR NULL (allows 0 for boundary rows) |
| `current_avg_cost` | REAL | nullable | CHECK > 0 OR NULL |
| `open_R_effective` | REAL | nullable | computed at write: `(current_price - current_avg_cost) * current_size / planned_risk_budget_dollars` |
| `open_MFE_R_to_date` | REAL | nullable | running max from `pre_trade_locked_at` through `data_asof_session`; CHECK ≥ 0 OR NULL |
| `open_MAE_R_to_date` | REAL | nullable | running abs(min) from `pre_trade_locked_at` through `data_asof_session`; CHECK ≥ 0 OR NULL |
| `intraday_high` | REAL | nullable | CHECK > 0 OR NULL; daily-session high (used for tomorrow's MFE compute when chained) |
| `intraday_low` | REAL | nullable | CHECK > 0 OR NULL; daily-session low |
| `position_capital_utilization_pct` | REAL | nullable | proportion; uses denominator captured in `position_capital_denominator_dollars` (this row's stamp); PROVISIONAL `$7,500` fallback in V1 until Phase 9 ships live denominator |
| `position_capital_denominator_dollars` | REAL | nullable | per-row stamp of the capital denominator used; V1 = `7500.0` (capital_floor_constant_dollars); V2+ may resolve to live account equity per Phase 9 risk_policy versioning. Snapshot history preserves the denominator at-time-of-capture (per §10.5 lock). |
| `position_portfolio_heat_contribution_dollars` | REAL | nullable | `max(0, (current_avg_cost - current_stop) * current_size)`; CHECK ≥ 0 OR NULL |
| `maturity_stage` | TEXT | nullable | CHECK IN (`pre_+1.5R`, `+1.5R_to_+2R`, `>=+2R_trail_eligible`) OR NULL; derived from `open_MFE_R_to_date` thresholds |
| `trail_MA_candidate_price` | REAL | nullable | SMA at `data_asof_session` close, period from `trail_MA_period_days`; NULL when insufficient archive history (sessions available < `trail_MA_period_days`) OR for event_log rows; CHECK > 0 OR NULL |
| `trail_MA_period_days` | INTEGER | nullable | per-row stamp of the SMA period used (V1 lock = 21; CHECK > 0 OR NULL); preserves interpretability when Phase 9 risk_policy versions the period (e.g., 10-day post-+2R upgrade) |
| `trail_MA_eligibility_flag` | INTEGER | nullable | CHECK IN (0,1) OR NULL; cached derivation: `1 IFF maturity_stage='>=+2R_trail_eligible' AND trail_MA_candidate_price IS NOT NULL AND current_stop < trail_MA_candidate_price`; else `0`; NULL on event_log rows when position-state fields are NULL |
| `thesis_status` | TEXT | nullable | CHECK IN (`intact`, `weakening`, `invalidated`) OR NULL; OPTIONAL on every row including event_log (R2 Major #4 fix — operator only populates when explicitly updating thesis). Snapshot rows ALWAYS leave NULL. Read-side resolution rules (R3 Major #4 fix — terminal-state disambiguation): (a) for OPEN trades (state ∈ {entered, managing, partial_exited}), if ≥1 event_log row has non-NULL thesis_status, return the latest such value; else return `intact` as the no-explicit-update default. (b) For CLOSED/REVIEWED trades, if ≥1 event_log row has non-NULL thesis_status, return the latest such value; ELSE the read-side returns `unrecorded` (a SENTINEL — NOT a CHECK enum value; rendered in UI as "thesis status not recorded during open phase"). The `intact` default DOES NOT propagate to closed-trade post-mortems because that would mislead a reviewer into thinking the operator affirmed thesis intactness when in fact no Phase 8 thesis update was ever emitted. Phase 6 review surfaces should consume the resolution result and display the sentinel verbatim. |
| **Operator-input fields (required ONLY for record_type='event_log'; NULL for daily_snapshot)** | | | |
| `prior_stop` | REAL | nullable | CHECK > 0 OR NULL; required at app-layer when `stop_changed=1` |
| `new_stop` | REAL | nullable | CHECK > 0 OR NULL; required at app-layer when `stop_changed=1` (R2 Major #3 fix — preserves event-time stop value durably on the row) |
| `linked_trade_event_id` | INTEGER | nullable | FK → `trade_events(id)` ON DELETE SET NULL (R3 Minor #3 fix — audit-pointer-only; trade_events row deletion preserves the daily_management_records row but clears the broken pointer); populated when `stop_changed=1` and Phase 7's `update_stop_with_event` co-emits a stop_adjust trade_events row (R2 Major #3 fix — audit-chain pointer) |
| `stop_changed` | INTEGER | nullable | CHECK IN (0,1) OR NULL; required at app-layer when record_type='event_log' |
| `stop_change_reason` | TEXT | nullable | required at app-layer when `stop_changed=1`; non-empty/non-whitespace |
| `volume_behavior` | TEXT | nullable | CHECK IN (`confirming`, `neutral`, `distribution`, `fading`) OR NULL |
| `relative_strength_status` | TEXT | nullable | CHECK IN (`improving`, `flat`, `weakening`) OR NULL |
| `market_regime_change` | INTEGER | nullable | CHECK IN (0,1) OR NULL |
| `sector_condition_change` | INTEGER | nullable | CHECK IN (0,1) OR NULL |
| `news_or_event_update` | TEXT | nullable | free-text |
| `action_taken` | TEXT | nullable | CHECK IN (`hold`, `trim`, `exit`, `stop`, `move_stop`, `no_action`) OR NULL; required at app-layer when record_type='event_log'. NOTE (R1 Minor #2 fix): `add` REMOVED — pyramiding DROP per §1.4; aligns with Phase 7's shipped `fills.action` 4-value enum. `stop` added to mirror `fills.action='stop'` for stop-loss-triggered exits as a distinct event from operator-discretionary `exit`. |
| `action_reason` | TEXT | nullable | required at app-layer when `action_taken IS NOT NULL AND action_taken != 'no_action'` |
| `emotional_state` | TEXT | nullable | JSON-list-text; vocabulary mirrors Phase 7 entry `emotional_state_pre_trade` (`calm`/`confident`/`anxious`/`fomo`/`revenge`/`hopeful`/`doubtful`/`distracted`); validation + canonicalization helpers mirror Phase 6 mistake_tags pattern |
| `rule_violation_suspected` | INTEGER | nullable | CHECK IN (0,1) OR NULL; required at app-layer when record_type='event_log' |
| `management_notes` | TEXT | nullable | free-text |

**Field count:** 42 columns (10 metadata + 17 position-state-or-derived + 15 operator-input/event-log; counted post R1+R2 fixes including `is_superseded` + `position_capital_denominator_dollars` + `trail_MA_period_days` + `new_stop` + `linked_trade_event_id`).

### §3.1.1 Operation-contextual validation (LOCKED — per Phase 7 §3.5.1 lesson)

Schema-level nullability is RELAXED on the position-state fields per Critical R1 #1 fix. App-layer validator enforces required-field set per OPERATION:

```
OPERATION_REQUIRED_FIELDS = {
    "snapshot_emit": (
        # All 14 position-state fields REQUIRED non-null:
        "current_price", "current_stop", "current_size", "current_avg_cost",
        "open_R_effective", "open_MFE_R_to_date", "open_MAE_R_to_date",
        "intraday_high", "intraday_low",
        "position_capital_utilization_pct", "position_capital_denominator_dollars",
        "position_portfolio_heat_contribution_dollars",
        "maturity_stage", "trail_MA_eligibility_flag",
        # trail_MA_candidate_price + trail_MA_period_days REQUIRED non-null UNLESS
        # archive history insufficient (then both NULL coherently — never one without
        # the other; cross-field constraint enforced at validator).
    ),
    "event_log_emit": (
        # Position-state fields are OPTIONAL (NULL allowed) — R1 Critical #1 fix.
        # Operator commentary fields REQUIRED:
        "stop_changed", "action_taken", "rule_violation_suspected", "emotional_state",
        # thesis_status is OPTIONAL even on event_log (R2 Major #4 fix); operator
        # populates only on explicit thesis update; routine events don't restate.
        # Conditional:
        # - "stop_change_reason" + "prior_stop" + "new_stop" + "linked_trade_event_id"
        #   required if stop_changed=1 (linked_trade_event_id populated by service
        #   from Phase 7's update_stop_with_event return value).
        # - "action_reason" required if action_taken NOT IN ('no_action', NULL)
    ),
    "tier_upgrade": (
        # See §6 — replaces an existing daily_snapshot row with a higher-precision row;
        # mfe_mae_precision_level must be > prior row's tier per the ordering
        # daily_approximate < intraday_estimated < intraday_exact.
        # Sets prior row's superseded_by_record_id.
        # All 14 position-state fields REQUIRED non-null (same set as snapshot_emit).
    ),
}
```

The validator API:

```
def validate_for_operation(req, *, op: Literal["snapshot_emit", "event_log_emit", "tier_upgrade"]) -> list[str]:
    """Returns missing-field names for the given operation; empty list if valid."""
```

This contextual-enforcement rule is binding (per Phase 7 §3.5.1 lesson). Drift between write paths is impossible because all paths converge on `validate_for_operation()`.

**Why event_log decouples from position-state (R1 Critical #1 fix):** event_log emission is operator commentary about a moment-in-time decision (stop change, rule violation observation, thesis revision). Coupling event_log writes to a fresh OHLCV-fetch-driven snapshot recompute would (a) couple operator action to network reliability, (b) introduce race conditions where a transient yfinance failure blocks operator from logging a trade decision, (c) force redundant compute when the operator emits multiple event_logs in the same session. The decoupled design lets event_log write atomically with no external data dependency. Read-side (§7.2 timeline) JOINs the same-day daily_snapshot (if it exists) for position-state context; if no snapshot for the day yet, reads the trades-row denorms (Phase 7 shipped).

### §3.2 Single-table-with-discriminator (LOCKED) — rationale

**Decision:** ONE table `daily_management_records` with `record_type ∈ {daily_snapshot, event_log}` discriminator. NOT split into two tables.

**Rationale:**

1. **v1.2 source-spec alignment.** v1.2 §7.7 specifies `record_type_enum: [daily_snapshot, event_log]` on a single `Daily_Management_Record` entity. We honor the source-spec choice where it doesn't conflict with framework-fit.
2. **Per-day cohesive view.** Operator drill-down "show me everything that happened on this trade-day" is a single-table query. Two-table split forces a UNION ALL on every per-day read.
3. **Position-state shared columns.** Both record_types CAN carry the position-state snapshot fields (current_price / current_stop / open_R_effective / MFE/MAE / capital_utilization / portfolio_heat / maturity_stage / trail_MA_*); per R1 Critical #1 fix, schema makes them NULLABLE — required only for daily_snapshot per §3.1.1 OPERATION_REQUIRED_FIELDS, optional for event_log. Two-table split would duplicate 14 columns; single table with optional event-log population keeps the duplication at zero with validator-level requiredness discipline. (R2 Minor #1 fix — earlier wording said "Both REQUIRE"; corrected to "Both CAN carry; daily_snapshot REQUIRES, event_log OPTIONAL".)
4. **Operator-actionability test.** What action does the operator take based on reading per-day timeline? The action is THE SAME REGARDLESS of record_type — review the day's state, decide whether to act. Single-table preserves cohesive read.

**Counter-considerations weighed and rejected:**

- *Two-table split would simplify event-only queries.* Rejected: the dashboard tile (§7.1) is per-position TODAY's state, not historical event-only. Per-trade timeline (§7.2) wants both record types interleaved chronologically. Event-only queries are not in the V1 read surface.
- *Two-table split would force tighter NULL discipline.* Rejected: the validator-level discipline per §3.1 is explicit; CHECK constraints enforce enum validity for non-null values; single-table with discriminator is the established pattern in v1.2 §7.7 source-spec.
- *Conflation with Phase 7's `trade_events` table.* Rejected: `trade_events` is LIFECYCLE audit (state transitions); `daily_management_records` is PER-DAY MANAGEMENT activity. Different semantic domains. See §2 vocabulary table.

**Alternative one-table-but-no-discriminator considered:** every row is a "review record" with optional event-log fields. Rejected because daily_snapshot vs event_log have different idempotency rules (§4) — daily_snapshot UPSERTs on `(trade_id, data_asof_session, mfe_mae_precision_level)` (R3 Minor #1 fix — session-anchored, precision-keyed); event_log allows multiple rows per day with no UPSERT. The discriminator drives the index policy.

### §3.3 Indexes

Snapshot uniqueness keys on `data_asof_session` (the SESSION ANCHOR) NOT `review_date` (R2 Major #1 fix). For V1 daily-tier capture, `review_date == data_asof_session` per §4.5; the divergence emerges in V2+ when a tier-upgrade row is captured on a calendar day after the session it anchors (e.g., Wednesday writes intraday-exact data for Tuesday's session). Keying on `data_asof_session` ensures the V2+ tier-upgrade row correctly supersedes the V1 daily_approximate row for the SAME session.

```
-- Active-snapshot uniqueness: ONE non-superseded daily_snapshot per (trade, session).
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_active_per_session
    ON daily_management_records (trade_id, data_asof_session)
    WHERE record_type = 'daily_snapshot' AND is_superseded = 0;

-- Per-precision uniqueness: idempotent UPSERT key for tier-aware writes (R1 Major #2 fix).
-- Tier-upgrade re-run with same precision_level → REPLACE; different precision_level → new row.
CREATE UNIQUE INDEX ux_daily_mgmt_snapshot_precision_per_session
    ON daily_management_records (trade_id, data_asof_session, mfe_mae_precision_level)
    WHERE record_type = 'daily_snapshot';

-- Timeline reads (§7.2): chronological per-trade ordered by review_date.
CREATE INDEX ix_daily_mgmt_trade_review
    ON daily_management_records (trade_id, review_date);

CREATE INDEX ix_daily_mgmt_pipeline_run
    ON daily_management_records (pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL;
```

**Index rationale:**

1. **`ux_daily_mgmt_snapshot_active_per_session`** (PARTIAL UNIQUE) — enforces ONE active (non-superseded) daily_snapshot per (trade, session). Predicate `WHERE record_type='daily_snapshot' AND is_superseded=0` allows: (a) multiple event_log rows per (trade, day); (b) tier-upgraded rows to coexist with their successor (predecessor has `is_superseded=1`, falls outside the unique constraint). Same partial-unique-index pattern as `ux_trades_one_open_per_ticker`. Keying on `data_asof_session` instead of `review_date` is binding for the V2+ tier-upgrade-across-calendar-days case (R2 Major #1).

2. **`ux_daily_mgmt_snapshot_precision_per_session`** (PARTIAL UNIQUE — R1 Major #2 + R2 Major #1 fix) — enforces ONE row per (trade, session, precision-level) for snapshot rows including superseded ones. Idempotency key for tier-aware writes. Re-running same-tier UPSERTs (REPLACE-on-conflict); higher-tier INSERTs a new row + supersedes prior.

3. **`ix_daily_mgmt_trade_review`** — drives per-trade timeline reads (§7.2). Cardinality at 5 trades × 365 sessions ≈ 1,825 rows/year — index trivial. NOT unique; multiple records (snapshots + event_logs) share the (trade, review_date) tuple.

4. **`ix_daily_mgmt_pipeline_run`** — drives pipeline-run-traceability reads (e.g., "show me all snapshots emitted by this pipeline run"). Partial index since CLI/web event_log rows have no pipeline_run_id.

**Tier-upgrade write sequence (R2 Major #2 + R3 Major #3 fix — binding):** the active-snapshot partial unique index forbids two non-superseded rows for the same `(trade, session)`, so a naive INSERT-then-UPDATE creates a transient violation. Step 4 must target the EXACT predecessor row by primary key (NOT by `is_superseded=1 AND superseded_by_record_id IS NULL`, because an earlier interrupted/manual repair could have left other matching rows). Locked sequence within a single transaction:

1. `BEGIN TRANSACTION`.
2. `SELECT management_record_id FROM daily_management_records WHERE trade_id = ? AND data_asof_session = ? AND record_type = 'daily_snapshot' AND is_superseded = 0` → store as `predecessor_id` (exactly 0 or 1 row by the active-snapshot unique index; NULL means no predecessor — either fresh-write or restart-after-failure case).
3. If `predecessor_id IS NOT NULL`: `UPDATE daily_management_records SET is_superseded = 1 WHERE management_record_id = predecessor_id`. (Frees the active-snapshot uniqueness slot.)
4. `INSERT INTO daily_management_records (...) VALUES (...)` → store as `successor_id = last_insert_rowid()`. (New row; `is_superseded = 0`.)
5. If `predecessor_id IS NOT NULL`: `UPDATE daily_management_records SET superseded_by_record_id = successor_id WHERE management_record_id = predecessor_id`. (Records audit-chain pointer scoped to the EXACT predecessor.)
6. `COMMIT`.

The `is_superseded` column decouples uniqueness-slot management from the FK audit-pointer; capturing `predecessor_id` in step 2 ensures step 5 cannot incorrectly point unrelated repair rows at the new successor (R3 Major #3 fix). Discriminating regression test (binding): synthetic 3-tier sequence (daily_approximate → intraday_estimated → intraday_exact) on the same session; assert at every transaction boundary the active partial unique index has exactly one row AND the audit chain `daily_approximate → intraday_estimated → intraday_exact` is correctly threaded via `superseded_by_record_id` pointers (each row points to its immediate successor only).

### §3.4 Modifications to existing tables

**`trades` table — ADD ONE COLUMN:**

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `planned_target_R` | REAL | nullable | CHECK > 0 OR NULL; pre-trade-locked target in R units (e.g., +2.0R, +3.0R); NULL for legacy trades + trades where operator did not pre-commit a target |

**Decision (§10.2): `planned_target_R` lives on `trades`, NOT on `daily_management_records`.** Per-trade-locked field; pre-trade discipline; one-shot capture at `pre_trade_locked_at`. Replicating per-snapshot creates anti-rationalization risk (operator could later "adjust" target to match outcome). Trades-table residence honors the same frozen-at-lock discipline as Phase 7's premortem fields.

**Migration mechanic:** `ALTER TABLE trades ADD COLUMN planned_target_R REAL` (no rebuild needed — adding NULLABLE column). Phase 7 lesson on table-rebuild constraint preservation does NOT apply here (no rebuild). If a future migration ever needs to make `planned_target_R` NOT NULL, that WOULD be a rebuild and full constraint enumeration discipline applies (§8 binding).

**No other modifications to `trades`, `fills`, or `trade_events`.** Phase 7's shipped schema is consumed read-only by Phase 8 EXCEPT the `planned_target_R` ADD COLUMN.

### §3.5 Phase 10 §6.1 capture-need cross-check

| Phase 10 §6.1 field | §3.1 column | Status |
|---|---|---|
| `maturity_stage` | `maturity_stage` | ✅ |
| `trail_MA_eligibility_flag` | `trail_MA_eligibility_flag` | ✅ |
| `open_MFE_R_to_date` | `open_MFE_R_to_date` | ✅ |
| `open_MAE_R_to_date` | `open_MAE_R_to_date` | ✅ |
| `position_capital_utilization_pct` | `position_capital_utilization_pct` (with PROVISIONAL fallback note per Phase 10 §2) | ✅ |
| `position_portfolio_heat_contribution_dollars` | `position_portfolio_heat_contribution_dollars` | ✅ |
| `intraday_high` / `intraday_low` | `intraday_high` / `intraday_low` | ✅ |
| `data_asof_session` | `data_asof_session` | ✅ |
| `trail_MA_candidate_price` (R1 M5) | `trail_MA_candidate_price` | ✅ |
| `planned_target_R` (R1 M5) | `trades.planned_target_R` (per §3.4 table-of-residence decision) | ✅ |

All 10 Phase 10 §6.1 capture-needs covered. No deviations. (Brief watch-item 6 satisfied.)

---

## §4 Capture cadence (LOCKED)

### §4.1 Snapshot trigger: pipeline-step

**Decision:** New pipeline step `_step_daily_management` extends the nightly orchestrator. Fires AFTER `_step_evaluate` (which produces `pipeline_runs.evaluation_run_id`) so the snapshot row's `pipeline_run_id` FK target exists. Fires BEFORE `_step_charts` if charts depend on snapshot data (none currently; ordering is flexible).

**Step body (descriptive — not code):**

1. Read `list_open_trades(conn)` (state ∈ {`entered`, `managing`, `partial_exited`}).
2. For each open trade:
   a. Compute `data_asof_session = last_completed_session(now)` (per Phase 7 lesson: backward-looking helper, not `action_session_for_run` — same family as the Phase 6 cadence-step lesson).
   b. Read OHLCV via `read_or_fetch_archive(ticker, ...)` for window `[pre_trade_locked_at_session, data_asof_session]`.
   c. Compute `current_price` = close at `data_asof_session`; `intraday_high` / `intraday_low` = high/low at `data_asof_session`; `open_MFE_R_to_date` / `open_MAE_R_to_date` = running extrema over the window per v1.2 §8.6 daily_approximate formulas.
   d. Read `trades.current_stop` / `current_size` / `current_avg_cost` (Phase 7 denorm).
   e. Compute `open_R_effective`, `position_capital_utilization_pct` (PROVISIONAL fallback), `position_portfolio_heat_contribution_dollars`, `maturity_stage`, `trail_MA_candidate_price` (21-day SMA at `data_asof_session`; NULL when archive has <21 sessions of history relative to `data_asof_session`), `trail_MA_eligibility_flag`.
   f. UPSERT row with `record_type='daily_snapshot'`, `mfe_mae_precision_level='daily_approximate'`, `pipeline_run_id=<current run>`, `created_at=now-naive-UTC`.
3. Idempotency policy per §4.2.

**CLI trigger (also supported):** `swing daily-management snapshot --trade-id <id>` for operator-directed re-snapshot (e.g., debugging; replaying a missed day). Same code path as `_step_daily_management` per-trade body. NOT scoped for V1 V1 release; flagged as "implementation-time scope decision" — writing-plans dispatch decides whether to wire CLI or defer.

### §4.2 Idempotency policy: UPSERT on `(trade_id, data_asof_session, mfe_mae_precision_level)` for daily_snapshot (R3 Major #1 fix)

**Decision:** Same-day re-run within the same precision tier = UPSERT (REPLACE-on-conflict against `ux_daily_mgmt_snapshot_precision_per_session` partial unique index). The conflict key is `(trade_id, data_asof_session, mfe_mae_precision_level)` — NOT `(trade_id, review_date)`. The session-anchor key is binding for V2+ tier-upgrade-across-calendar-days correctness (per §3.3). Re-running pipeline twice in same session refreshes `current_price` / `intraday_high` / `intraday_low` / running MFE/MAE based on archive state at the moment-of-fire. This is correct behavior — yfinance archive may receive late-day correction; later run captures more accurate data.

**Tier-upgrade interaction (§6):** UPSERT applies WITHIN the same `mfe_mae_precision_level`. A higher-tier emission (V2+) does NOT UPSERT against the active-snapshot index (`ux_daily_mgmt_snapshot_active_per_session`) — it INSERTs a new row at the new precision following the §3.3 5-step transactional sequence. The active-snapshot partial unique index excludes superseded rows (predicate `is_superseded = 0`), so the new higher-tier row holds the active slot post-step-3.

**event_log idempotency:** NO unique constraint. Operator may emit multiple event_log rows per day (e.g., morning stop_adjust event + afternoon news_or_event_update event). Each row gets its own `management_record_id` via autoincrement.

**Operational discipline (R1 Major #3 — narrative coherence between snapshot and event_log):** the recommended cadence is "pipeline runs first; operator reviews dashboard; emits event_log SECOND." If operator emits event_log BEFORE the day's pipeline run, then a later pipeline run's UPSERT refreshes the snapshot's position-state values to AFTER-event values — the event_log's commentary may then read as describing a state that no longer matches the same-day snapshot. This is a known design tradeoff, not a bug: the event_log row's own captured fields (prior_stop, current_stop-at-event-time per Phase 7's `update_stop_with_event` audit, action_taken) preserve the operator's view at-event-time independently of the snapshot. Read-side surfaces (§7.2 timeline) render event_log row fields as authoritative for "what operator saw"; snapshot row fields as authoritative for "what archive showed at end-of-session." The two views don't conflict because they answer different questions. **Documented as discipline, NOT enforced at schema level** — the schema permits the order; operator workflow guides usage.

### §4.3 Back-fill policy: GAP-FLAGGED, no auto back-fill

**Decision:** If pipeline missed a session (operator skipped the daily run; weekend/holiday gap), `_step_daily_management` does NOT retroactively populate snapshots for missed days. Per-trade timeline (§7.2) renders missing days as `(no snapshot — pipeline did not run)` placeholder.

**Rationale:**

1. **Anti-rationalization discipline.** Back-filling a snapshot creates the illusion of management activity that never happened. Operator's actual management cadence was "didn't review on this day"; data should reflect reality.
2. **Cheap to compute later.** OHLCV archive is the source-of-truth; a future analytical surface CAN derive backward MFE/MAE from archive without persisted snapshot rows. Persisted gap is not data loss — only interaction loss.
3. **Tier-upgrade is the back-fill primitive.** If V2+ ships intraday-exact ingestion, it operates on existing snapshot rows (tier-upgrade per §6) — back-filling a missed day would create a tier-upgrade target that never had a tier-1 baseline, conflating capture failure with capture absence.

**Edge case — pipeline_run row deleted by operator (e.g., to redo):** snapshots tied to the deleted run via `pipeline_run_id` FK have FK target removed. Phase 8 sets `pipeline_runs(id)` FK with `ON DELETE SET NULL` so snapshot rows survive but lose their pipeline traceability. The active-snapshot partial unique index on `(trade_id, data_asof_session)` still holds — re-running pipeline UPSERTs the row with the new pipeline_run_id. (R2 Minor #2 fix — corrected stale FK target reference.)

### §4.4 Operator-event_log trigger: web form + CLI

**Decision:** event_log emission is operator-discretionary (NOT auto-emitted from state transitions). State-transition triggers (entry / stop_adjust / pre_trade_edit) continue to write `trade_events` rows per Phase 7 — those are LIFECYCLE audit, not management review.

**Trigger surfaces:**

1. **Web:** new POST `/trades/{id}/daily-management/event` from per-trade detail page. Form gathers event-log fields per §3.1.
2. **CLI:** `swing trade event-log <trade-id> [--stop-changed --new-stop X --reason "..."] [--action trim --reason "..."] [--rule-violation] [--emotional-state JSON-list]`.

Both surfaces CONVERGE on a single `swing/trades/daily_management.py` `record_event_log(conn, trade_id, req)` function (per Phase 7 §9.2 single-source-of-truth pattern). The function (R2 Critical #1 + R3 Major #5 fix — NO automatic OHLCV fetch; single-transaction atomicity):

**Single-transaction contract (R3 Major #5 fix — binding):** all of the following execute inside ONE `BEGIN IMMEDIATE` / `COMMIT` transaction. If ANY step fails, the entire flow rolls back: no partial state where Phase 7 stop_adjust trade_event row exists without its Phase 8 daily_management_records event_log context, OR vice versa. This is binding because the audit-chain pointer (`linked_trade_event_id`) is meaningless if the two sides can diverge.

1. `BEGIN IMMEDIATE TRANSACTION`.
2. Validates operator-input fields per §3.1.1 OPERATION_REQUIRED_FIELDS["event_log_emit"]. On invalid → ROLLBACK + raise `ValidationException`.
3. (Conditional) If `req.stop_changed=1`: calls Phase 7's `update_stop_with_event(conn, trade_id, req.new_stop, req.stop_change_reason)` WITHIN the existing transaction (the service must accept being called inside a transaction, not open its own — verify Phase 7 shipped behavior at writing-plans dispatch time). Captures the returned `trade_event_id` as `linked_event_id`. ELSE: `linked_event_id = None`.
4. INSERTs the event_log row with:
   - All operator-input fields per §3.1.1 OPERATION_REQUIRED_FIELDS["event_log_emit"].
   - Position-state fields = `req.captured_position_state.<field>` if operator supplies them, ELSE NULL.
   - `linked_trade_event_id = linked_event_id` (NULL if no stop_change occurred).
   - `new_stop = req.new_stop` if `stop_changed=1`, ELSE NULL.
5. If `trades.state == 'entered'`: calls `state_transition(conn, trade_id, 'managing', trigger='first_daily_management_record')` per Phase 7 §3.4 (also accepts being inside a transaction).
6. `COMMIT`.

**Phase 7 service-call-inside-transaction precondition:** Phase 7's shipped `update_stop_with_event` and `state_transition` services either accept-or-reject being called inside an outer transaction. Writing-plans dispatch time MUST verify (a) the shipped behavior; (b) write a discriminating regression test that this single-transaction call pattern works WITHOUT the inner service double-BEGINing OR rolling back the outer's changes. If Phase 7 services internally `BEGIN`, Phase 8's caller-controls-transaction discipline conflicts and either Phase 7 services need to be made transaction-context-aware OR Phase 8 needs a different atomicity strategy (e.g., savepoint nesting).

**No OHLCV fetch in this path.** Operator commentary is decoupled from network reliability per R1 Critical #1. If operator wants the row's position-state fields populated, they pass them explicitly (web form may pre-fill from latest snapshot or trades-row denorms client-side; that's a UI concern, not a write-path requirement). Read-side timeline (§7.2) uses `linked_trade_event_id` + Phase 7's `trade_events.payload_json` for atomic stop-change reconstruction; falls back to the daily_management_records `prior_stop` / `new_stop` if `linked_trade_event_id IS NULL` (which means the event_log row was emitted without a stop_change).

**V1 scope decision:** web form ships V1; CLI flagged as "writing-plans-decides scope" (dispatch may defer if scope inflates).

### §4.5 Snapshot timing (LOCKED): end-of-NYSE-session

Pipeline runs daily, anchored on `last_completed_session(now)` (per Phase 7 lesson "Datetime impedance: chronology vs creation-timestamp"). Pipeline timing depends on operator's actual run cadence — could be 4:30 PM ET (right after close) or Sunday evening (catching up after a weekday gap). The session helper resolves to the most recent COMPLETED NYSE session regardless of wall-clock time.

**`review_date == data_asof_session` for daily_snapshot rows.** They are intentionally identical for daily-tier capture — the snapshot reviews the data anchored on that session. Tier-upgrade (V2+) MAY have `review_date != data_asof_session` (e.g., intraday-exact data captured Wednesday for Tuesday's session), in which case `review_date` = the calendar day of capture, `data_asof_session` = the session being captured.

For event_log rows, `review_date` is the operator-supplied date the event happened (default = `last_completed_session(now)`); `data_asof_session` is the position-state anchor (same default).

---

## §5 Phase 7 state-machine integration (LOCKED)

### §5.1 Snapshot states

**Snapshots fire ONLY when `trades.state ∈ {entered, managing, partial_exited}`.**

| State | Snapshot fires? | Notes |
|---|---|---|
| `entered` | YES | First-day snapshot may be the trigger that transitions to `managing` per Phase 7 §3.3 (binding). |
| `managing` | YES | Default open-state. |
| `partial_exited` | YES | After trim fill; remaining position continues to be tracked. |
| `closed` | NO | Final snapshot was the day-of-final-exit; no new snapshots after. |
| `reviewed` | NO | Phase 6 review has frozen aggregates; no new snapshots. |

### §5.2 Phase 7 transition `entered → managing` is triggered by first daily_management record

Per Phase 7 §3.3 transition table: `entered → managing` is triggered by "first management activity: first stop_adjust event OR first trim/exit/stop-action fill OR (Phase 8 future) first daily_management record." Phase 8 IS that future. **The first `_step_daily_management` snapshot for an `entered` trade triggers the `entered → managing` state transition** (atomic with the snapshot INSERT, in the same fenced_write transaction).

**Cross-table write discipline:** `record_event_log` and `_step_daily_management`'s per-trade body BOTH:

1. Open transaction.
2. Snapshot/event_log INSERT.
3. Read current `trades.state`.
4. If `state == 'entered'`, call `state_transition(conn, trade_id, 'managing', trigger='first_daily_management_record')` per Phase 7 §3.4 single-write-path.
5. Commit.

The `state_transition()` service emits its own `trade_events` row per Phase 7 §3.4. The Phase 8 row + the Phase 7 transition trade_events row co-exist — they describe different things.

### §5.3 Stop-change cross-table coupling

When operator emits an event_log row with `stop_changed=1`, the system MUST also emit a `trade_events` row with `event_type='stop_adjust'` per Phase 7 §6.4. The Phase 7 stop-adjust path is the canonical mutator of `trades.current_stop`. Phase 8's event_log row records the operator's CONTEXT (volume_behavior / emotional_state / rule_violation_suspected); Phase 7's trade_events row records the LIFECYCLE FACT that the stop changed.

**Single-write-path discipline:** `record_event_log` calls into Phase 7's `update_stop_with_event(conn, trade_id, new_stop, reason)` — the existing service that mutates `trades.current_stop` AND emits the `trade_events` row. Phase 8's record_event_log:

```
def record_event_log(conn, trade_id, req):
    # ... validation ...
    if req.stop_changed:
        update_stop_with_event(conn, trade_id, req.new_stop, req.stop_change_reason)
    insert_daily_management_event_log(conn, trade_id, req)
    if trades_state(conn, trade_id) == 'entered':
        state_transition(conn, trade_id, 'managing', trigger='first_daily_management_record')
```

**Predicate-rewrite-per-call-site discipline (Phase 7 lesson):** every Phase 8 query that filters by trade state evaluates per-purpose. Watch-item audit:

- **§7.1 dashboard tile** "show me open positions' latest snapshot" — uses `state IN ('entered','managing','partial_exited')` (active-trade predicate).
- **§7.2 per-trade timeline** "show me snapshot/event_log history" — agnostic of state; query renders all records ordered by `review_date ASC`. NO state filter in the query (timeline must show closed-trade history).
- **`_step_daily_management`** — uses `state IN ('entered','managing','partial_exited')` (active-trade predicate; consistent with Phase 7's `list_open_trades`).
- **§7.3 review-surface drill-down** (Phase 6 review extension; deferred V1) — uses `state IN ('closed','reviewed')` (closed-or-reviewed predicate).

No naive substring substitution; each call-site has its own classification. (Watch-items 1, 2 satisfied.)

### §5.4 Backwards transitions

Phase 7's transition matrix is forward-only EXCEPT the future `reviewed → reopened` extension flagged in Phase 7 spec §3.2. Phase 8 inherits forward-only:

- A `closed` trade's snapshot history is read-only.
- A `reviewed` trade's snapshot history is read-only.
- IF Phase 9 reconciliation reopens a `reviewed` trade (Phase 7 §3.2 future transition), Phase 8 schema accommodates re-opening the snapshot stream (state moves back into open-states; `_step_daily_management` resumes capturing). No schema change required for Phase 9.

### §5.5 Snapshot freeze on `closed`

When `state` transitions to `closed`, the prior open-state snapshot history is preserved verbatim. The next-day's `_step_daily_management` skips the trade. Operator-visible: per-trade timeline (§7.2) shows the snapshot history with the final row bearing `review_date = closing_session_date`.

**Read-only enforcement:** repo-layer convention (no UPDATE paths exposed for closed-trade snapshot rows). Mirrors Phase 7's pre-trade-locked-fields discipline (no DB triggers; lint/test discipline). The exception is tier-upgrade (§6), which intentionally MUTATES the prior row's `superseded_by_record_id` — but the prior row's content fields stay frozen.

### §5.6 Authoritative-source precedence (R1 Major #1 fix)

When the same conceptual value appears across multiple shipped/Phase-8 surfaces, read-side queries follow this PRECEDENCE LADDER. Higher entries on the ladder are AUTHORITATIVE; lower entries are CACHED COPIES with explicit at-time-of-write semantics.

| Field | Authoritative source | Cached copies | At-write semantic |
|---|---|---|---|
| Current stop on a live trade | `trades.current_stop` (Phase 7 single-write-path via `update_stop_with_event`) | `daily_management_records.current_stop` (snapshot row only; NULL on event_log per R2 fix); event_log row's durable stop fields are `prior_stop` + `new_stop` (R3 Minor #2 fix) | Snapshot row's `current_stop` = stop in force at session close; event_log row's `prior_stop` / `new_stop` = stop in force immediately before/after the change at event time. Operator-actionable LIVE read = `trades.current_stop` ALWAYS (per §7.1 dashboard tile read-source precedence). |
| Current size on a live trade | `trades.current_size` (Phase 7 `_recompute_aggregates` after every fill) | `daily_management_records.current_size` (snapshot at end-of-session) | Same pattern — trades-row authoritative; snapshot is timestamped historical record. |
| Trade lifecycle state | `trades.state` (Phase 7 single-write-path via `state_transition`) | none | snapshot rows do NOT cache state. Read-side queries that filter by state JOIN trades. |
| MFE/MAE running max from entry | `daily_management_records.open_MFE_R_to_date` / `open_MAE_R_to_date` (most-recent active snapshot) | none | Snapshot row IS authoritative for in-flight running extrema. Closed-trade post-mortem MFE/MAE = max over all snapshot rows for the trade. |
| Thesis status | most-recent event_log row with non-NULL `thesis_status` | none (snapshot rows ALWAYS leave thesis_status NULL per R1 Critical #4 fix) | Read-side resolves "current thesis_status" via subquery. Defaults to `intact` if no event_log row exists. |
| Pre-trade decision fields | `trades.thesis` / `why_now` / `invalidation_condition` etc. (Phase 7 frozen-at-lock) | none | Snapshots and event_logs do NOT cache pre-trade fields. Read-side reads from trades. |
| Capital denominator at snapshot time | `daily_management_records.position_capital_denominator_dollars` (per-row stamp; R1 Major #4 fix) | none | Each snapshot row IS authoritative for the denominator it used. Phase 9 versioning resolves forward-going writes; historical rows preserve their stamp. |
| Trail-MA period at snapshot time | `daily_management_records.trail_MA_period_days` (per-row stamp; R1 Major #5 fix) | none | Same per-row stamp pattern as the capital denominator. |

**Read-precedence enforcement:** view-models JOIN `trades` for trade-level current state + JOIN `daily_management_records` for time-series snapshot data + subquery for latest event_log thesis_status. NO surface reads stale snapshot copies as if they were live values. Test fixture binding: synthetic case where `trades.current_stop != latest_snapshot.current_stop` (operator did mid-day stop_adjust after morning snapshot) — assert dashboard tile reads `trades.current_stop`, NOT snapshot's stale value.

---

## §6 MFE/MAE precision tier semantics (LOCKED)

### §6.1 Tier-upgrade policy: ADDITIVE with audit trail

**Decision:** When higher-precision data arrives later for a snapshot already populated with `daily_approximate`, the upgrade is ADDITIVE — a NEW row is INSERTED with the higher precision; the prior row's `superseded_by_record_id` is set to the new row's `management_record_id`. Both rows persist forever.

**Rationale:**

1. **Audit trail preserved.** Operator can SEE that on date X the system had daily_approximate data; on date Y it was upgraded to intraday_exact. Neither version is silently overwritten.
2. **Idempotent upgrade.** Re-running tier-upgrade with the same data produces the same row (UPSERT key includes precision_level via the partial unique index excluding superseded rows).
3. **Historical-record stability.** Any analytical surface that ran on date Y can be re-run on date Z and produce the same answer (queries default to "non-superseded rows only" but can opt into the full history).
4. **Brief §1.5 alignment.** Brief recommends "tier-upgrade with audit trail (which tier was authoritative at time-of-use)." This decision implements that recommendation.

### §6.2 Tier ordering

```
daily_approximate < intraday_estimated < intraday_exact
```

**Tier-upgrade rule:** new row's `mfe_mae_precision_level` MUST be strictly higher than the prior row's. Same-tier or lower-tier "upgrades" are rejected at validator level (`tier_upgrade` operation per §3.1 OPERATION_REQUIRED_FIELDS). Same-tier reflows are UPSERTs per §4.2 (replace-on-conflict).

### §6.3 Read-time tier resolution

**Default read predicate (R2 Major #1 + #2 fix):** `WHERE record_type='daily_snapshot' AND is_superseded = 0` — returns the highest-precision snapshot available for each (trade, session). Note: `is_superseded = 0` is the canonical predicate (NOT `superseded_by_record_id IS NULL`); the FK is the audit pointer that may be transiently NULL during the tier-upgrade write sequence per §3.3.

**Audit-trail read predicate:** `WHERE record_type='daily_snapshot' AND trade_id=? AND data_asof_session=?` — returns ALL precision-level rows for a (trade, session), ordered by `mfe_mae_precision_level` ASC (use a CASE expression mapping daily_approximate=1, intraday_estimated=2, intraday_exact=3 for ordering). Used by per-trade detail audit display.

### §6.4 Capture-tier-of-record inscription

Each daily_snapshot row carries its `mfe_mae_precision_level` AT CAPTURE TIME. A row written today as `daily_approximate` STAYS `daily_approximate` forever; a future intraday_exact row is a SEPARATE row pointed to by `superseded_by_record_id` from the daily_approximate predecessor.

This is the v1.2 §8.6 "precision flag" discipline encoded in the schema.

### §6.5 V1 scope

V1 ships `daily_approximate` ONLY. The schema reserves `intraday_estimated` + `intraday_exact` enum values + the `superseded_by_record_id` column + the tier-upgrade validator path — but NO ingestion code. V2+ adds the ingestion pipelines (gated on Schwab API Phase B or equivalent intraday data source per `docs/phase3e-todo.md` 2026-05-04 entry).

(Watch-items 4, 14 satisfied.)

### §6.6 `trail_MA_candidate_price` reference period (LOCKED — decision §10.1)

**LOCKED: 21-day SMA at `data_asof_session` close, with per-row `trail_MA_period_days` stamp (R1 Major #5 fix).**

V1 default value of `trail_MA_period_days = 21`. The per-row stamp is REQUIRED so that:

1. Phase 9 risk_policy versioning of the period (e.g., 10-day upgrade after +2R per Tier-3 #6 doctrine) does NOT silently re-interpret historical rows.
2. A V2 surface that shows mixed-period trail-MA candidates (e.g., a +1.5R trade tagged 21-day; a +2.5R trade tagged 10-day) renders correctly without ambiguity.
3. Future operator-configurability of the period (per §11.1 Phase 9 hand-off) is a clean migration: Phase 9 versioning adjusts forward-going default; per-row stamp preserves history.

Rationale for the V1 = 21-day default:

1. **Canonical TA period.** Minervini's framework uses 10/21/50 SMAs; 21-day is the canonical "intermediate" trail. 20-day is also common but lacks the same TA-chain alignment.
2. **Tier-3 #6 doctrine alignment.** Operator's framing "default 20MA early, upgrade to 10MA after ~+1.5-2R" — V1 ships the EARLIER trail (default 21-day family); 10MA upgrade is V2 (open question per §10).
3. **NULL-on-insufficient-history.** If the OHLCV archive has fewer than `trail_MA_period_days` sessions of history for the ticker at `data_asof_session`, BOTH `trail_MA_candidate_price` AND `trail_MA_period_days` are NULL coherently (cross-field constraint per §3.1.1 OPERATION_REQUIRED_FIELDS validator). The trail_MA_eligibility_flag definition handles NULL: `1 IFF maturity_stage='>=+2R_trail_eligible' AND trail_MA_candidate_price IS NOT NULL AND current_stop < trail_MA_candidate_price`.

**V2 path:** 10-day SMA upgrade after +2R via Phase 9 risk_policy versioning of `trail_MA_post_2R_period_days`. Snapshot writer reads the policy effective at write time; stamps `trail_MA_period_days` accordingly. Historical rows untouched. (R1 Major #5 satisfied: per-row stamp eliminates retroactive interpretation drift.)

(Watch-item 15 satisfied.)

---

## §7 Read-surface contracts (LOCKED — surface sketches only; no HTML/code)

### §7.1 Per-open-position dashboard tile

- **Primary axis:** per-open-position; ALWAYS shown when ≥1 open position exists.
- **Composition:** ticker / state-badge / `current_price` / `current_stop` / `open_R_effective` / `open_MFE_R_to_date` / `open_MAE_R_to_date` / `maturity_stage` (badge) / `trail_MA_eligibility_flag` (badge — visible only when TRUE) / `position_capital_utilization_pct` (PROVISIONAL badge per Phase 10 §2 split-policy) / `position_portfolio_heat_contribution_dollars` / `planned_target_R` (from `trades` table; renders as "—" when NULL).
- **Read-source precedence (R2 Major #5 fix — must align with §5.6 ladder):**
  - **Live values** (current_stop, current_size, state) → read from `trades` table (Phase 7 single-write-path is authoritative). NOT from snapshot row.
  - **Time-series running extrema** (open_MFE_R_to_date, open_MAE_R_to_date) → read from latest active snapshot row (`is_superseded = 0`). Snapshot is authoritative because the running max-from-entry is the snapshot's purpose.
  - **End-of-session anchored values** (current_price = close at last session, intraday_high, intraday_low, maturity_stage, trail_MA_*) → read from latest active snapshot row.
  - **Per-trade frozen** (planned_target_R) → read from `trades` table.
  - **Computed** (open_R_effective for live tile use) → recomputed at render time using `trades.current_size` × (`trades.current_avg_cost`-or-pseudo-current-price); the snapshot row's open_R_effective reflects close-of-session, NOT live.
- **Sample-size threshold:** N/A (per-position, not aggregate). All open positions render.
- **Operator-actionability:** primary daily-management surface. `trail_MA_eligibility_flag=1` is a discrete operator action prompt (consider stop-trail per Tier-3 #6 doctrine). `maturity_stage` transitions trigger workflow attention.
- **HTMX pattern:** matches existing dashboard tile precedent (open-positions row partial; OOB-swap on pipeline refresh). NO per-render OHLCV fetch for live `current_price` — the tile renders the most-recent snapshot's `current_price` (close of last session) as "as-of-{data_asof_session}". Live intraday price is OUT OF SCOPE for V1; future V2 enhancement (per CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY" — when added, applies via PriceCache pattern).
- **JS-test-harness gap:** no client-side compute; all derivations server-side. (Watch-item 13 satisfied.)
- **Operator-witnessed gate (binding):** dashboard tile renders correctly with all fields populated; live current_stop reads from trades-row (not stale snapshot copy); PROVISIONAL badge visible on capital-utilization; trail_MA_eligibility_flag badge visible only when TRUE; planned_target_R "—" placeholder when NULL.

### §7.2 Per-trade detail timeline drill-down

- **Primary axis:** per-trade; chronological with deterministic tie-break (R1 Critical #2 + #3 fix).
- **Row contract:** ONE row per `management_record_id` (NOT per (review_date, record_type) — multiple event_log rows per day are explicitly allowed and EACH renders as its own distinct row).
- **Ordering contract:** `ORDER BY review_date ASC, created_at ASC, management_record_id ASC`. The `created_at ASC` tie-break is binding for same-date event_log rows; `management_record_id ASC` final tie-break ensures determinism even when two rows share the same `created_at` wall-clock second. Per Phase 7 Sub-B R3 M1 lesson "lexicographic ordering on text-stored datetimes is a contract requiring naive-only inputs" — `created_at` validator enforces naive-UTC.
- **Tier-upgrade default visibility:** default rendering filters to `is_superseded = 0` (active snapshots only — canonical predicate per §6.3 R2 Major #1 fix; NOT `superseded_by_record_id IS NULL` which can be transiently NULL during the §3.3 tier-upgrade write sequence). Event_log rows ALWAYS render (never superseded; their `is_superseded` field is `0` by default and never mutated). Toggle "show superseded snapshots" expands to include the audit chain.
- **Composition:** table columns by record_type:
  - **For `record_type='daily_snapshot'`:** `review_date` / "snapshot" badge / `current_price` / `current_stop` / `open_R_effective` / `open_MFE_R_to_date` / `open_MAE_R_to_date` / `mfe_mae_precision_level` (badge) / `maturity_stage`.
  - **For `record_type='event_log'`:** `review_date` / "event" badge / `created_at` (wall-clock; distinguishes multiple same-day events) / `action_taken` / `stop_changed` (with prior→new stop if true) / `thesis_status` / `rule_violation_suspected` (badge if true) / `emotional_state` (chips) / collapsed `action_reason` + `management_notes` (expand on click). Position-state cells render as JOIN-from-same-day-snapshot if available, else "—" (per §3.1.1 R1 Critical #1 fix — event_log rows don't carry position-state by default).
- **Gap rendering:** missing days between snapshots render as a single placeholder row "(no snapshot — pipeline did not run)".
- **Sample-size threshold:** N/A (per-trade, not aggregate).
- **Operator-actionability:** post-trade review consumption. Phase 6 review form may surface this as a drill-down link (deferred V1; operator-paced V2 follow-up).
- **State-of-the-trade footer:** "open since {pre_trade_locked_at}; total snapshot days = N; total event_log entries = M; final snapshot precision = {tier}".
- **JS-test-harness gap:** no client-side compute. (Watch-item 13 satisfied.)

### §7.3 Journal stats integration

**Decision:** Phase 8 daily_management_records is consumed by Phase 10's metrics dashboard ONLY. `swing journal review --period month` does NOT consume Phase 8 data in V1 — that journal command is a Phase 6 review_log surface, semantically distinct.

**Rationale:** journal stats is closed-trade aggregate analytics; Phase 8 is open-position management state + per-day trade history. Conflating loses both surfaces' clarity. If V2+ wants a "journal review with daily-management drill-down," that's a Phase 10+ writing-plans extension (open question §10.6).

### §7.4 Pipeline briefing extension (V1)

**Decision (LOCKED):** the existing nightly briefing (`briefing.md` + `briefing.html`) gains a "Daily Management Snapshot" subsection per open trade — current state at `data_asof_session`, MFE/MAE-to-date, maturity_stage, trail-MA eligibility flag. Single-table per trade; no analytical aggregation.

**Out-of-scope V1:** chart-image overlays of snapshot data; trail-MA candidate-price line on per-trade chart; multi-trade comparative views.

**Operator-actionability:** briefing-driven morning workflow. Operator opens briefing, sees per-trade snapshot, knows whether to act today.

### §7.5 Read-surface inheritance from Phase 7

All Phase 8 read surfaces use Phase 7's denormed fields (`current_size`, `current_avg_cost`, `current_stop`, `last_fill_at`) where available. The daily_snapshot row's columns are the AUTHORITATIVE read source for surface-rendering — Phase 7's denormed fields are the AUTHORITATIVE compute source. Both are recomputed every snapshot emission.

**No drift between trades-row denorms and daily_snapshot denorms** — the snapshot reads the trades-row at emission time, persists the values. If the trades-row mutates between emissions, the next snapshot picks up the new value. Phase 7's `_recompute_aggregates` discipline already polices the trades-row truth-source.

(Watch-item 12 satisfied: every Phase 8 surface answers "what action does the operator take based on reading X vs Y?" §7.1 trail_MA_eligibility_flag; §7.2 post-trade review; §7.4 briefing-driven workflow.)

---

## §8 Migration strategy (LOCKED — Phase 7 lesson inheritance)

### §8.1 Schema bump: v15 → v16

Migration `0015_phase8_daily_management.sql` (single migration; not split). Changes:

1. ADD COLUMN `planned_target_R REAL` to `trades` (NULLABLE; CHECK > 0 OR NULL).
2. CREATE TABLE `daily_management_records` per §3.1.
3. CREATE INDEXES per §3.3.
4. UPDATE `schema_version SET version = 16`.

**No table-rebuild on `trades`.** Adding a NULLABLE column doesn't trigger CREATE-COPY-DROP-RENAME — preserves Phase 7 lesson "any table-rebuild migration MUST enumerate every existing CHECK + FK on the original table + per-constraint disposition" without invoking it.

**If a future migration ever rebuilds `trades`** (e.g., to make `planned_target_R` NOT NULL after operator adoption matures), THAT migration MUST enumerate every CHECK + FK + carry forward — Phase 8 writing-plans dispatch flags this for the future. Phase 7 Sub-C R1 M1 lesson is binding for any future rebuild.

### §8.2 Migration runner discipline (Phase 7 lessons binding)

The shipped migration runner (`swing/data/db.py:_apply_migration` post Phase 7 hotfix `283d4fa`) handles:

1. **Backup gate** — `current_version == 15 AND target >= 16`-tightened condition (per Phase 7 Sub-A code-review I1 lesson). Backup file: `swing-pre-phase8-migration-<ISO>.db` via `Connection.backup()` SQLite-native. 4 binding integrity checks per Phase 7 R2 M1 lesson.
2. **executescript() partial-failure rollback wrapper** — try/except around `conn.executescript(sql) ; conn.commit()`; on exception, `conn.rollback()` then re-raise (per Phase 7 Sub-A R1 M3 lesson). Discriminating regression test: malformed migration with deliberate fail-mid-sequence; assert probe table doesn't exist post-failure AND `conn.in_transaction == False`.
3. **`foreign_keys=OFF` runner discipline** — runner saves current `foreign_keys` value, sets OFF before `executescript`, restores after in `finally:` block (per Phase 7 hotfix `283d4fa` lesson). NOT applicable to Phase 8 since no table-rebuild — but the runner discipline is global and inherited.

(Watch-items 7, 8 satisfied.)

### §8.3 Test fixture PRAGMA discipline

Every Phase 8 migration test fixture sets `PRAGMA foreign_keys=ON` on its connection (per Phase 7 hotfix `283d4fa` lesson "test fixture connection state must mirror production runtime PRAGMA state"). Specific binding test fixtures:

1. **Fresh-DB migration test:** start from no-DB; run all migrations through 0015; assert schema_version=16; assert `daily_management_records` table exists with all 42 columns (per §3.1); assert `trades.planned_target_R` column exists.
2. **Mid-walk migration test:** start from schema_version 14 (pre-Finviz baseline); run migrations 0015 (skipping 0015's own intermediate states); assert no backup taken (gate condition `current_version==15`); assert end state correct.
3. **Backup-fires test:** start from schema_version 15 (Finviz baseline); run migration 0015; assert backup file created at `swing-pre-phase8-migration-<ISO>.db`.
4. **executescript-rollback test:** synthetic malformed 0015 with fail-mid-statement; assert no `daily_management_records` table; assert `conn.in_transaction == False`.
5. **No-CASCADE-loss-on-trades-add-column test:** seed pre-migration with N existing trades + M existing fills + K trade_events; run migration 0015; assert N+M+K row counts identical post-migration. (No rebuild on trades; CASCADE doesn't apply; but the test is cheap insurance against a future rebuild creep.)

(Watch-items 8, 11 satisfied.)

### §8.4 Datetime column policy (Phase 7 Sub-B lessons binding)

`daily_management_records` introduces FOUR datetime-bearing columns:

| Column | Type | Field semantic | Validator policy |
|---|---|---|---|
| `review_date` | TEXT | chronology (operator-meaningful date, e.g., `2026-05-12`) | naive ISO date (YYYY-MM-DD); validator rejects datetimes (must be date-only); rejects non-ISO formats |
| `data_asof_session` | TEXT | chronology (NYSE session anchor, e.g., `2026-05-12`) | same as review_date — naive ISO date |
| `created_at` | TEXT | creation-timestamp (system wall-clock at row insert) | naive UTC ISO datetime; validator rejects tz-aware per Phase 7 Sub-B R3 M1 lesson; canonicalizes to `YYYY-MM-DDTHH:MM:SS` (no offset suffix) |
| (`updated_at` deliberately NOT introduced — see below) | | | |

**`updated_at` deliberately NOT introduced.** A rolled-up "last update wall-clock" field invites datetime impedance ambiguity — does it mean creation? tier-upgrade replacement? content edit? Phase 8 V1 has NO content-edit operations on snapshot rows (read-only); tier-upgrade creates a NEW row (doesn't update); event_log rows are append-only. `created_at` covers all V1 needs; if V2+ ships content-edit, that's a separate column with explicit semantic.

**Lexicographic ordering on TEXT datetime columns:** `ORDER BY review_date ASC` for §7.2 timeline reads; `ORDER BY created_at ASC` for audit-trail reads. Both columns are naive (no tz suffix); lexicographic ordering matches chronological ordering deterministically. Validator-enforced. Per Phase 7 Sub-B R3 M1 lesson.

(Watch-items 9, 10 satisfied.)

### §8.5 In-flight production data

At HEAD `1441109` (schema_version 15): 4 trades (VIR closed+reviewed; DHC + CC + YOU open). Phase 8 migration:

- VIR — `state='reviewed'`; no snapshots fire after migration (final state). `planned_target_R` defaults NULL (legacy trade).
- DHC + CC + YOU — `state='managing'` (or `entered` if no Phase 7 management activity yet); next pipeline run after migration emits the first daily_snapshot for each. `planned_target_R` defaults NULL.
- All `trades` rows have `planned_target_R` NULL post-migration; operator may backfill via direct DB UPDATE if desired (escape valve; not a V1 surface).

**No backfill of historical snapshots for DHC/CC/YOU** — per §4.3 gap-flagged policy. Operator's existing trade history is preserved in trades + fills + trade_events + Phase 7's denorms; Phase 8 starts capturing FORWARD from migration-completion.

---

## §9 Lookback / replay policy for back-recorded trades (LOCKED)

### §9.1 Forward-only from record-time

**Decision:** if operator records a trade on calendar day X with `pre_trade_locked_at = day Y` (Y < X), Phase 8 starts capturing snapshots on the next pipeline run AFTER X. The gap between Y and X is NOT retroactively populated.

**Rationale:** anti-rationalization discipline. Back-recording a trade is a known operator workflow (Phase 7 explicitly accommodates back-recorded trades via NULL pre-trade fields per §3.5.1). But synthesizing snapshot history for the back-recorded period would create the illusion of management activity on days the operator wasn't actually managing the trade. Operator's actual cadence is "I started recording on day X"; data should reflect reality.

**Operator escape valve:** if operator wants to retroactively populate per-day MFE/MAE for analytical purposes, the OHLCV archive supports the computation directly — a future analytical surface CAN derive backward MFE/MAE from `read_or_fetch_archive(...)` without persisted snapshot rows. Persisted gap is interaction loss; analytical surface remains intact.

(Watch-item 16 satisfied.)

### §9.2 Pre-trade-locked-at preservation

`pre_trade_locked_at` is the anchor for `open_MFE_R_to_date` / `open_MAE_R_to_date` window computations. Phase 8 reads it from `trades.pre_trade_locked_at` (Phase 7 shipped). For back-recorded trades, the running MFE/MAE windows starts from pre_trade_locked_at's session — the snapshot on day X+1 already captures running extrema spanning Y → X+1, even though no snapshots existed for Y → X. This is correct: the OHLCV archive has the data; the snapshot row reflects the cumulative state-to-date.

---

## §10 Open questions for orchestrator triage

Each unresolved question that requires operator decision before Phase 8 writing-plans dispatch can scope. Question + tradeoff sketch + recommendation + decision-source.

### §10.1 `trail_MA_candidate_price` reference period (LOCKED in §6.6 — surfaced here for orchestrator review)

**Locked: 21-day SMA at session close, single period in V1.**

Open dimension: should V1 ALSO ship the 10-day SMA upgrade after +2R per Tier-3 #6 doctrine, or is the +2R upgrade V2?

**Recommendation:** V1 ships 21-day only. 10-day upgrade is V2 (gated on operator-configurable `trail_MA_post_2R_period_days` field in Phase 9 risk_policy). Rationale: V1 surface satisfies the operator-actionable trail-MA gating signal; V2 refines the upgrade behavior once operator has lived with the V1 surface.

Decision-source: orchestrator + operator approval at brainstorm-review.

### §10.2 `planned_target_R` table-of-residence (LOCKED in §3.4 — surfaced here for orchestrator review)

**Locked: `trades.planned_target_R` (per-trade pre-trade-locked).**

Open dimension: should Phase 8 also REPLICATE the value per-snapshot for query convenience? E.g., daily_management_records.planned_target_R copy-on-snapshot.

**Recommendation:** NO replication. Phase 10 read surfaces JOIN from `daily_management_records` to `trades` for `planned_target_R`. Replication invites drift. Phase 7 §4.5 frozen-cache pattern is the precedent (entry_date / entry_price etc. live on trades; not duplicated to fills).

Decision-source: orchestrator + operator approval at brainstorm-review.

### §10.3 V1 CLI surface for event_log emission

**Question:** does V1 ship `swing trade event-log <trade-id> [args]` CLI command, or web-only?

**Tradeoff:** CLI ships ~1-2 hours of additional implementation; provides operator escape valve when web UI inconvenient (e.g., quick stop-adjust from terminal). Web-only ships faster; operator's primary surface is the web dashboard anyway.

**Recommendation:** writing-plans dispatch decides at scope-review time (DEFER to plan author). Default scope = web-only V1; CLI as V2 follow-up unless plan dispatch's scope budget accommodates.

Decision-source: writing-plans dispatch scope-review.

### §10.4 `intraday_high` / `intraday_low` semantic at daily_approximate tier

**Question:** for daily_approximate tier, `intraday_high` / `intraday_low` = day's H/L (full session). For yfinance partial-bar discipline (CLAUDE.md gotcha), how is the in-progress session bar handled if the pipeline runs DURING market hours?

**Tradeoff:** `last_completed_session(now)` returns the prior session's date when called during NYSE market hours — so `data_asof_session = prior_session`, NOT today's in-progress session. The in-progress bar is excluded from the snapshot. This is correct per CLAUDE.md gotcha "yfinance interval='1d' includes in-progress bar — strip the partial bar."

**Recommendation:** specify in Phase 8 spec validator: `data_asof_session` MUST be `last_completed_session(now)` per Phase 7 lesson. Reject pipeline runs that attempt to anchor on the in-progress session. Helper `swing.evaluation.dates.last_completed_session(now)` is shipped (per Phase 6 §A.8 lesson). The OHLCV archive's `read_or_fetch_archive` already strips the partial bar (per Phase 3 OHLCV consolidation logic).

**Disposition:** ACCEPT as binding spec contract. No open question; flagged for orchestrator visibility.

Decision-source: orchestrator review of binding contract; writing-plans dispatch verifies the helper choice in plan tasks.

### §10.5 `position_capital_utilization_pct` PROVISIONAL fallback at snapshot time (LOCKED in §3.1 + §5.6 — surfaced for orchestrator review)

**Locked (R1 Major #4 fix): FROZEN-AT-CAPTURE with per-row `position_capital_denominator_dollars` stamp.**

The snapshot's `position_capital_utilization_pct` value reflects what the system knew at capture time. Per-row `position_capital_denominator_dollars` stamps the actual denominator value used (V1 = `7500.0`). This makes per-row interpretability explicit:

- A V1 row reads as "utilization = X% of $7,500 floor" — the denominator is in the row, not just a UI badge.
- A V2 row (post-Phase-9-live-denominator) reads as "utilization = Y% of $A,BCD live equity" — same column carries the actual value used.
- Phase 9 risk_policy versioning resolves the denominator at write time per the policy effective at `created_at`; the stamp records the resolved value.

Open dimension: should the V1 → V2 transition CAVEAT historical rows on read? Recommendation: yes, the dashboard tile (§7.1) renders the row's denominator value alongside the percentage when the historical denominator differs from the current live denominator. UI concern; Phase 10 writing-plans scope.

Decision-source: orchestrator + operator approval; Phase 9 brainstorm inherits the per-row-stamp contract.

### §10.6 V2+ journal-stats integration of Phase 8 data

**Question:** Phase 6 review_log + Phase 8 daily_management_records are conceptually overlapping (per-trade closed-history vs per-trade snapshot-history). Does V2+ surface a unified "trade-detail" view that shows BOTH (review aggregates + snapshot timeline)? Or do they remain on separate routes?

**Recommendation:** SEPARATE in V1; orchestrator decides at Phase 10 writing-plans whether to consolidate. The Phase 6 review form is an event-driven surface (operator clicks "review trade" once); Phase 8 timeline is a per-trade-detail drill-down. Cross-linking via "view daily timeline" link from Phase 6 review form is a 1-line addition that doesn't require schema changes. Defer scope-decision to Phase 10.

Decision-source: Phase 10 writing-plans dispatch.

### §10.7 Schwab API Phase B coordination

**Question:** Phase 8 MFE/MAE precision tiers 2 + 3 (`intraday_estimated`, `intraday_exact`) are gated on intraday data source. The Schwab API integration plan (per `docs/phase3e-todo.md` 2026-05-04 entry) is queued. When Schwab Phase B brainstorm runs, does it inherit Phase 8's precision-tier semantics (additive tier-upgrade) or design its own?

**Recommendation:** Schwab Phase B INHERITS Phase 8's tier-upgrade contract. Phase 8 schema reserves the enum values + the `superseded_by_record_id` column + the validator path; Schwab Phase B writes the ingestion pipeline that emits `intraday_estimated` or `intraday_exact` rows AND sets prior `daily_approximate` rows' `superseded_by_record_id`. No schema rework at Phase B.

**Disposition:** ACCEPT as binding contract; flagged for Schwab Phase B brainstorm awareness when it dispatches.

Decision-source: orchestrator visibility; Schwab Phase B brainstorm references this spec §6.

### §10.8 Snapshot retention policy long-horizon

**Question:** at multi-year scale (5 trades × 365 days × 5 years ≈ 9,125 rows), no retention concerns. At 50-trade/year operational ceiling × 5 years × 365 days = ~91K rows, still trivial. But should Phase 8 spec lock a retention policy (e.g., "snapshots persist forever; never archived") or leave open?

**Recommendation:** LOCK retention = forever. Snapshot rows are analytical-research evidence; archival creates Phase 7-style fragmentation. The data volume is trivial at our scale.

Decision-source: orchestrator approval.

---

## §11 Phase 9 hand-off (capture-needs feedback)

Phase 9 brainstorm follows Phase 8 + builds on Phase 8's schema. Phase 8 design choices that Phase 9 needs to know about:

### §11.1 Risk_Policy versioning of MFE/MAE precision-tier defaults

- `mfe_mae_default_precision_level` (TEXT, default `daily_approximate` in V1) — Phase 9 risk_policy versions this so V2+ can default to `intraday_estimated` when ingestion lands.
- `trail_MA_period_days` (INTEGER, default 21) — externalizes §6.6 lock so V2's 10-day upgrade after +2R becomes a per-policy field.
- `trail_MA_post_2R_period_days` (INTEGER, default NULL — meaning "no upgrade" — V1 default; V2 may set 10) — supports the +2R MA-period upgrade Tier-3 #6 doctrine.

### §11.2 Reconciliation of Daily_Management snapshots against broker-API position state

- `account_equity_snapshot_table` — per Phase 10 §8.2 open question; if operator adopts manual entry OR Schwab Phase A lands, Phase 9 should version-stamp the source (`source ∈ {manual, schwab_api, csv_import}`) so Phase 8's `position_capital_utilization_pct` can resolve to live denominator.
- Snapshot reconciliation flag — for V2+ where broker-API position state may diverge from internal trades-row state, Phase 9 reconciliation_runs may flag snapshot rows whose underlying state diverges. NOT a Phase 8 concern; Phase 9 to scope.

### §11.3 V1 capture-needs already accommodated

Phase 8's `daily_management_records` schema does NOT block:

- `bootstrap_resample_count` / `low_sample_size_thresholds_class_*` (Phase 10 §6.2 already flags for Phase 9; Phase 8 doesn't need them but doesn't block them either).
- `hypothesis_status_history` audit table (Phase 10 §6.2 R1 M1 capture-need; Phase 8 doesn't intersect).
- `capital_floor_constant_dollars` versioning (Phase 10 §6.2 R3 M1 split-policy capture-need; Phase 8 captures as PROVISIONAL fallback per §10.5; Phase 9 externalizes).

(Watch-item 14 satisfied: Schwab API Phase B coordination flagged cleanly in §10.7 + §11.1.)

---

## §12 Self-review checklist (pre-commit)

- [x] **Placeholders:** No "TBD" / "TODO" markers in normative sections.
- [x] **Internal consistency:** §3.1 schema sketches consume Phase 7's shipped fields verbatim; §3.5 cross-checks Phase 10 §6.1 capture-needs (10/10 covered); §5.3 cross-table coupling specifies single-write-path discipline; §8 migration strategy inherits Phase 7 lessons.
- [x] **Scope check:** SCHEMA-LOCKING but no migration SQL (§3 column-level; §8 mechanic-level only); no code drafting (§5.3 single-write-path is described, not implemented); no task decomposition.
- [x] **Ambiguity check:** §3.1 OPERATION_REQUIRED_FIELDS makes per-record_type required-field set explicit; §4.2 idempotency policy explicit; §6.1 tier-upgrade policy explicit (additive with audit trail); §10 open questions enumerated.
- [x] **Codex R3 fix coverage:** all 0 critical + 5 major + 3 minor findings addressed:
  - Major R3 #1 (§4.2 stale UPSERT key + index names) → §4.2 re-keyed to `(trade_id, data_asof_session, mfe_mae_precision_level)` against the new `ux_daily_mgmt_snapshot_precision_per_session` partial-unique index.
  - Major R3 #2 (§7.2 visibility predicate stale) → §7.2 default rendering uses `is_superseded = 0` (canonical predicate), NOT the FK-NULL check.
  - Major R3 #3 (tier-upgrade step 4 too loose; could mis-point unrelated repair rows) → §3.3 5-step sequence revised to capture `predecessor_id` in step 2 (SELECT) and use it as exact-match in step 5 update.
  - Major R3 #4 (terminal-state thesis_status defaults misleadingly to 'intact' for closed trades) → §3.1 thesis_status entry: read-side resolution returns sentinel `unrecorded` (not `intact`) for closed/reviewed trades with no event_log thesis updates.
  - Major R3 #5 (stop-change atomicity under-specified) → §4.4 single-transaction contract — BEGIN IMMEDIATE; validate; Phase 7 update_stop_with_event call; INSERT event_log row; (state transition); COMMIT. Phase 7 service-call-inside-transaction precondition flagged as writing-plans verification gate.
  - Minor R3 #1 (§3.2 stale UPSERT mention) → §3.2 alternative-rationale corrected.
  - Minor R3 #2 (§5.6 cached-copies table mentions event_log copies of position-state) → §5.6 row updated; event_log durable stop fields are `prior_stop` / `new_stop`; position-state copy is snapshot-only.
  - Minor R3 #3 (linked_trade_event_id FK delete behavior) → §3.1 FK clause adds `ON DELETE SET NULL`.
- [x] **Codex R2 fix coverage:** all 1 critical + 5 major + 3 minor findings addressed:
  - Critical R2 #1 (§4.4 reintroduced R1 Critical #1) → §4.4 rewritten — record_event_log() does NO OHLCV fetch; position-state fields populated only if operator supplies them.
  - Major R2 #1 (tier-upgrade keying inconsistent with review_date != data_asof_session) → §3.3 unique indexes re-keyed on `data_asof_session`; §6.3 read predicates updated.
  - Major R2 #2 (active-snapshot index makes successor INSERT impossible without ID-reservation) → New `is_superseded` column decoupled from FK pointer; §3.3 specifies binding 5-step transactional sequence.
  - Major R2 #3 (event_log lacks durable new_stop / FK to Phase 7 trade_events) → §3.1 added `new_stop` + `linked_trade_event_id` columns; §4.4 service signature wires Phase 7's `update_stop_with_event` return.
  - Major R2 #4 (thesis_status drift trap remained because event_log_emit required it) → §3.1 thesis_status OPTIONAL on every row; §3.1.1 makes it not-required for event_log_emit; routine event_logs leave it NULL.
  - Major R2 #5 (§7.1 contradicted §5.6 precedence ladder) → §7.1 read-source precedence section added; live values from trades-row, time-series from snapshot row, frozen from trades.
  - Minor R2 #1 (§3.2 stale wording about both record types requiring position-state) → §3.2 corrected.
  - Minor R2 #2 (§4.3 stale FK target reference) → §4.3 corrected to `pipeline_runs(id)`.
  - Minor R2 #3 (column count drift between §3.1 and §8.3) → §3.1 says "42 columns"; §8.3 test fixture aligned to "all 42 columns".
- [x] **Codex R1 fix coverage:** all 4 critical + 5 major findings addressed:
  - Critical #1 (event_log doesn't need full position-state recompute) → §3.1 nullability relaxed; §3.1.1 OPERATION_REQUIRED_FIELDS makes position-state OPTIONAL for event_log_emit; §3.1.1 explicit rationale paragraph.
  - Critical #2 (timeline contract conflicts with multiple event_log per day) → §7.2 row contract = ONE row per `management_record_id`.
  - Critical #3 (deterministic ordering for same-date rows) → §7.2 ordering contract `(review_date ASC, created_at ASC, management_record_id ASC)`.
  - Critical #4 (thesis_status drift trap) → §3.1 thesis_status NULLABLE; snapshot rows leave NULL; §3.1.1 + §5.6 read-side resolves via latest event_log row.
  - Major #1 (authoritative-source ambiguity) → §5.6 NEW precedence ladder + read-precedence enforcement test fixture binding.
  - Major #2 (tier-upgrade duplicate superseded chains) → §3.3 NEW `ux_daily_mgmt_snapshot_precision_per_day` partial-unique index.
  - Major #3 (UPSERT mutation after event_log narrative inconsistency) → §4.2 NEW Operational discipline paragraph; documented as discipline not enforced.
  - Major #4 (PROVISIONAL capital denominator without per-row stamp) → §3.1 NEW `position_capital_denominator_dollars` column; §10.5 + §5.6 contract.
  - Major #5 (trail_MA scalar without period stamp) → §3.1 NEW `trail_MA_period_days` column; §6.6 + §5.6 contract.
  - Minor #1 (intraday_high/low naming) → ACCEPTED-with-rationale: reader-context note added (V1 daily-tier captures session H/L; V2+ intraday tiers may capture sub-session H/L).
  - Minor #2 (action_taken includes 'add' despite no-pyramiding) → §3.1 enum dropped 'add'; added 'stop' to mirror Phase 7 fills.action.
  - Minor #3 (pipeline_run_id FK target) → §3.1 corrected to `pipeline_runs(id)` (verified against migration 0001 PK).
  - Minor #4 (UTC/local-midnight off-by-one) → §10.4 ACCEPTED-as-binding-contract: `last_completed_session(now)` per Phase 6 §A.8 lesson.
- [x] **Brief watch-item coverage:** all 16 watch items addressed:
  - 1 (Phase 7 state-machine integration completeness): §5.1 + §5.2 + §5.3 + §5.4 + §5.5 cover all 5 states + transitions + cross-table coupling.
  - 2 (predicate rewrite per call-site): §5.3 audit table — 4 distinct predicates per call-site purpose.
  - 3 (capture cadence idempotency): §4.2 UPSERT discipline; §4.3 back-fill = no; §4.4 event_log no idempotency constraint; pipeline-twice-same-day refresh; deletion-of-pipeline_run preserves snapshot via FK SET NULL.
  - 4 (MFE/MAE tier-upgrade policy): §6.1 + §6.2 + §6.3 + §6.4 — additive with audit trail; tier ordering; read-time resolution.
  - 5 (discriminating-record-type): §3.1 OPERATION_REQUIRED_FIELDS + §3.2 single-table rationale.
  - 6 (Phase 10 §6.1 capture-need completeness): §3.5 cross-check table — 10/10.
  - 7 (schema-rebuild constraint preservation): §3.4 ADD COLUMN doesn't trigger rebuild; §8.1 explicit; future rebuild flagged.
  - 8 (foreign_keys=OFF runner discipline): §8.2 inherits via shipped runner.
  - 9 (datetime impedance): §8.4 review_date / data_asof_session / created_at semantics + validator policy.
  - 10 (lexicographic ordering): §8.4 naive-only validator policy.
  - 11 (test fixture PRAGMA): §8.3 enumerates 5 binding test fixtures.
  - 12 (operator-actionability): §7.1 + §7.2 + §7.4 — every surface answers "what action?".
  - 13 (JS-test-harness gap): §7.1 + §7.2 — no client-side compute; HTMX patterns mirror existing precedents.
  - 14 (Schwab API Phase B coordination): §10.7 + §11.1 — flagged cleanly; V1 ships tier 1 only without Schwab dependency.
  - 15 (`trail_MA_candidate_price` reference period): §6.6 + §10.1 — locked 21-day; rationale.
  - 16 (`planned_target_R` table-of-residence): §3.4 + §10.2 — locked trades-table; rationale.
- [x] **Single commit landing:** spec is the only artifact for this brainstorm session; landing + R1-fix follow-up commit per Phase 7 / Phase 10 precedent.
- [x] **Line target:** within brief's 500-800 target after R1 fix integrations.

---

## §13 References

- Brief: `docs/phase8-daily-management-brainstorm-brief.md`.
- Phase 10 metrics-design (binding §6.1 capture-needs): `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`.
- Phase 7 trade-state-machine + Fills (binding integration): `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`.
- Phase 7 migration shipped: `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`.
- Phase 6 post-trade review (review_log freezes-at-review): `swing/data/migrations/0013_phase6_post_trade_review.sql`; `swing/trades/review.py`.
- Phase 3 OHLCV archive (daily_approximate source): `swing/data/ohlcv_archive.py`; `swing/data/repos/ohlcv_archive.py`.
- Journal v1.2 source spec (§7.7 Daily_Management + §8.6 MFE/MAE precision): `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`.
- Cross-phase backlog (Journal v1.2 incorporation; Schwab API Phase B; future schema migration trades.entry_date datetime promotion): `docs/phase3e-todo.md`.
- Orchestrator-context (binding Phase 7 lessons): `docs/orchestrator-context.md` §"Lessons captured" 2026-05-04 + 2026-05-05 entries.
- Format reference: `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`; `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`.
- CLAUDE.md gotchas (yfinance partial-bar; HTMX failure surfaces; `... or None` discipline; Windows ACL).

---

*End of design spec. Adversarial Codex review pending.*
