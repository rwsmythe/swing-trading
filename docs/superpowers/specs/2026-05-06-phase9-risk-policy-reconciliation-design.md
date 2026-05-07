# Phase 9 Risk_Policy + Reconciliation Depth — Design Spec (Brainstorm Output)

**Baseline:** `main` at HEAD `d89b74b` (post-Phase-8/Phase-10 brainstorm shipping); ~1940 fast tests green; production schema_version = 15. Phase 8 brainstorm SHIPPED 2026-05-06 at `c954eef`; Phase 10 brainstorm SHIPPED 2026-05-06 at `fe6cb45`. Phase 9 brainstorm is the third in the 10 → 8 → 9 design chain; execution order is locked at 8 → 9 → 10. Phase 8 will bump schema to v16 in writing-plans-time; Phase 9 bumps v16 → v17.

**Goal:** Lock SCHEMA SHAPES + COLUMNS + CHECK constraints + FK relationships + capture cadence + lifecycle integration with Phase 6 / Phase 7 / Phase 8 for: versioned `risk_policy`, structured `reconciliation_runs` + `reconciliation_discrepancies`, append-only `hypothesis_status_history`, `account_equity_snapshots`, sector/industry tamper hardening, and TOS reconciliation depth bundle subsumption. Schwab API is a V2-pluggable `source` enum slot (no library / auth design here). RESEARCH-AND-LOCK posture: schema sketches + cadence + lifecycle, NOT migration SQL, NOT code.

**Brief:** `docs/phase9-risk-policy-reconciliation-brainstorm-brief.md` (commit `d89b74b`).

**Scope inputs (binding, not re-derived):**
- Phase 10 §6.2 capture-needs (versioning needs for `risk_policy`; `hypothesis_status_history` audit; `account_equity_snapshot_table` source enum; `capital_floor_versioning`).
- Phase 8 §11 capture-needs (`mfe_mae_default_precision_level` versioning; `trail_MA_period_days` + V2 `trail_MA_post_2R_period_days`; snapshot reconciliation flag).
- Phase 7 + Phase 8 lessons (17+ in `docs/orchestrator-context.md` "Lessons captured" + 1 NEW CLAUDE.md gotcha for SQLite REPLACE).
- v1.2 §7.8 / §7.9 / §10.5 source-spec; framework-fit DROP rules per `docs/phase3e-todo.md` "Cross-cutting framing."
- Existing `swing.config.toml` values (Account, Risk, PositionLimits, Web, Pipeline, Review, Archive, etc.) → seed `risk_policy` row at `policy_id=1`.

---

## §1 Background, framing, and binding constraints

### §1.1 What this spec produces

A locked schema set (§3) for five new tables plus enumerated modifications to two shipped tables (`trades`, `review_log`); a locked capture-cadence policy (§4); a locked lifecycle-integration design with Phase 6 review_log + Phase 7 state machine + Phase 8 daily_management_records (§5); a locked TOS-reconciliation-depth bundle subsumption mapping (§6); a locked sector/industry tamper hardening scope (§7); a locked Schwab API Phase A coordination boundary (§8); a locked migration strategy (§9); enumerated open questions for orchestrator triage (§10); a Phase 10 hand-off section that surfaces what Phase 10 writing-plans needs to know (§11).

### §1.2 What this spec does NOT produce (out of scope per brief §3)

Migration SQL drafts; code drafts (services, repos, view-models, Jinja, route handlers, CLI bodies); Phase 9 task decomposition into dispatches (writing-plans output); Schwab API library evaluation (Schwabdev vs schwab-py vs build-from-scratch — that is the eventual Schwab Phase A brainstorm); Schwab API authentication design; fractional-shares schema; `trade.entry_date` datetime promotion; Phase 10 dashboard layer. Re-litigation of brief §1 strategic context is also out of scope — accepted as binding.

### §1.3 Binding constraints (orchestrator-distilled, not re-derived)

Per brief §1, the following are accepted as design inputs without re-justification:

1. **Framework-research-loop posture, not discretionary trading.** Pipeline asserts thesis; per-trade hypothesis_label drives cohort attribution. risk_policy fields seed from `swing.config.toml`, not from operator-discretionary inputs.
2. **Capital tie-up = primary constraint.** $7,500 capital floor for sizing; ~50-trade/year ceiling. `account_equity_snapshots` is the source-of-truth for `live_capital_denominator_dollars` (per Phase 10 §2 split-policy).
3. **Single operator at $7,500.** Drawdown circuit breaker DEFAULT opt-in disabled per v1.2 framing rule. Concentration limits are advisory, NOT blocking, in V1.
4. **Sample size: n=2 closed, n=3 open as of 2026-05-06.** Reconciliation framework ships from-day-one; analytical surfaces are years away from statistical power. Schema MUST NOT prematurely optimize for high-cardinality discrepancy aggregation.
5. **Operator already on Schwab.** Dev Portal app + production-access approval RESOLVED 2026-05-06 (see `docs/phase3e-todo.md` Schwab API Q4). Phase 9 ships TOS-CSV V1 only; Schwab is a V2-pluggable enum value reserved on `reconciliation_runs.source` and `account_equity_snapshots.source`.
6. **No ship-velocity pressure.** Metric stability is the binding constraint; convergent multi-round Codex chains (4–6 rounds) are budgeted per Phase 7/8 lesson family.

### §1.4 v1.2 DROP rules applied

Per `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation" cross-cutting framing — drop from v1.2 §7.8 / §7.9:

- **Self-rated `pre_trade_quality_score`-style fields on risk_policy:** DROP. Pipeline asserts thesis; no self-rating component.
- **Setup_Playbook references in v1.2 §7.8:** DROP. Setups encoded in `swing/evaluation/`.
- **Pyramiding R-views (`R_initial` / `R_effective` / `R_campaign`):** DROP. Single denominator `planned_risk_budget_dollars` per Phase 10 §1.3.
- **Drawdown circuit breaker:** DEFAULT opt-in disabled (matches v1.2 default + project posture). Schema includes the 4 conditional fields but `drawdown_circuit_breaker_enabled` defaults FALSE.
- **`current_consecutive_loss_count` runtime-state field:** NOT a `risk_policy` column. v1.2 §7.8 lists it as runtime-state-derived (formula in v1.2 lines 962–974). Compute on read; do not persist.

### §1.5 Sector/industry tamper hardening — IN-PHASE-9 SCOPE

Per `docs/phase3e-todo.md` "2026-05-05 Sector/industry tamper vector hardening" — operator-decided to bundle into Phase 9. Once `risk_policy.max_sector_concentration_positions` becomes a gating dimension (V2; advisory in V1), the tamper vector becomes correctness-critical. Phase 9 schema supports the audit (see §3.3 `discrepancy_type='sector_tamper'`); route-layer rejection at trade entry POST is writing-plans territory mirroring chart_pattern hardening (`swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`). See §7.

### §1.6 Schwab API Phase A coordination (NOT a Phase 9 dependency)

Per `docs/phase3e-todo.md` Schwab API Phase A entry — Phase 9 reconciliation depth + Schwab Phase A have logical merger ("Phase 9 ships using Schwab API as the data layer"). **HOWEVER, Phase 9 must NOT be hard-dependent on Schwab API.** TOS-CSV path remains the V1 reconciliation source; `reconciliation_runs.source ∈ {tos_csv, schwab_api, manual}` enum supports both. Schwab Phase A is a separate sequencing decision; Phase 9 ships V1 with TOS-CSV alone. See §8 for the boundary.

---

## §2 Vocabulary anchored against shipped surfaces

| Term | Definition (Phase 9) | Anchor / shipped surface |
|---|---|---|
| **Risk_Policy** | A versioned snapshot of operator-tunable risk constants (max risk per trade, max concurrent, heat cap, sector concentration, consecutive-loss thresholds, drawdown gate fields, statistics-methodology knobs) PLUS metric-config knobs (scratch_epsilon, review_lag_threshold_days, low-sample-size thresholds, global confidence floor, bootstrap resample count, process_grade_weights, capital_floor_constant_dollars, mfe_mae_default_precision_level, trail_MA_period_days). One row per active version; supersession tracked via `is_active` flag + `superseded_by_policy_id` FK (Phase 8 R2 dual-column lesson). |
| **Reconciliation_Run** | A single invocation of a reconciliation pass (TOS CSV import, future Schwab API sync, future manual entry). Owns metadata + lifecycle state (`running` / `completed` / `failed`); one-to-many to discrepancies. |
| **Reconciliation_Discrepancy** | A single field-level disagreement detected within a run. Carries discrepancy_type + linked entity (trade / fill / cash_movement / daily_management_record) + expected/actual JSON shapes + resolution. |
| **material_to_review** | Per-discrepancy boolean — TRUE iff the discrepancy SHOULD trigger Phase 6 review reopen. Computed at INSERT time per discrepancy_type lookup (see §3.3 + §5.1). |
| **Hypothesis_Status_History** | Append-only audit of every `hypothesis_registry.status` UPDATE. One row per transition; `effective_from` = transition-in-time; `effective_to` = NULL for current row. Mirrors v1.1-alternate F-022. |
| **Account_Equity_Snapshot** | Single-day account-balance capture. V1 cadence: manual entry via CLI / web; V2 source enum slot reserved for `schwab_api`. One row per `snapshot_date`. Backs Phase 8's `position_capital_utilization_pct` and Phase 10's `live_capital_denominator_dollars`. |
| **review_log.reopened_at** | Phase 6 review_log gains a nullable column to mark a completed review as flagged for re-examination after a material reconciliation discrepancy. Frozen aggregates remain frozen (audit snapshot of what was reviewed); new aggregates are computed on demand at the dashboard read layer; Phase 7 state stays at `reviewed`. See §5. |
| **trades.risk_policy_id_at_lock** | Phase 9 adds a per-trade FK stamp to `risk_policy` recording which policy version was effective at `pre_trade_locked_at`. Preserves correct retroactive interpretation when policy changes (capital floor change; tripwire change; scratch_epsilon change). |
| **policy_id** | INTEGER PK on `risk_policy`; surrogate; assigned at INSERT. NOT a string-encoded version (per §3.1 rationale). Discrete monotone series; v1.2 §7.8's `policy_id: string` form is rejected as overhead at our scale. |

---

## §3 Schema sketches (LOCKED)

### §3.1 New table: `risk_policy`

**Versioning model (LOCKED — Decision §3.1.4):** ONE row per policy snapshot, NOT per-field versioning. Rationale in §3.1.4. Supersession via `is_active` flag + `superseded_by_policy_id` FK (decoupled from `effective_to` per Phase 8 R2 lesson).

**Column sketch** (column-name + type + nullability + CHECK / FK; NOT full DDL):

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `policy_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `effective_from` | TEXT | NOT NULL | **ISO datetime** (YYYY-MM-DDTHH:MM:SS); naive-UTC per §9 datetime discipline; chosen over date-only so same-day policy changes have monotone ordering AND so consumers comparing against `trades.pre_trade_locked_at` (datetime) can use a uniform string format. (R1 Major #2 fix.) |
| `effective_to` | TEXT | nullable | ISO datetime OR NULL; NULL while is_active=1; set in same transaction as supersession per §4.1 6-step sequence; lexicographic ordering preserved by naive-UTC validator policy. |
| `is_active` | INTEGER | NOT NULL | CHECK IN (0,1) DEFAULT 1; predecessor flag set BEFORE successor row INSERT to free the active-policy uniqueness slot (Phase 8 R2 lesson — decoupled from FK pointer) |
| `superseded_by_policy_id` | INTEGER | nullable | FK → `risk_policy(policy_id)` (self-reference); set AFTER successor row INSERT to record the audit-chain pointer per §4.1 6-step sequence |
| `created_at` | TEXT | NOT NULL | ISO datetime; system wall-clock; naive-UTC per §9 datetime policy |
| `policy_notes` | TEXT | nullable | free-text rationale |
| **Trading-risk fields (v1.2 §7.8 — DROP rules per §1.4 applied)** | | | |
| `max_account_risk_per_trade_pct` | REAL | NOT NULL | CHECK > 0; default seed 0.50 |
| `max_concurrent_positions` | INTEGER | NOT NULL | CHECK > 0; default seed 6 |
| `max_portfolio_heat_pct` | REAL | NOT NULL | CHECK > 0; default seed 3.0 |
| `max_sector_concentration_positions` | INTEGER | NOT NULL | CHECK > 0; default seed 3; ADVISORY in V1 (NOT a gate); see §7 for tamper hardening dependency |
| `consecutive_losses_pause_threshold` | INTEGER | NOT NULL | CHECK > 0; default seed 3 |
| `consecutive_losses_pause_action` | TEXT | NOT NULL | CHECK IN ('review_required'); seed 'review_required' (V1 single-value enum; V2 may extend) |
| `consecutive_losses_streak_reset` | TEXT | NOT NULL | CHECK IN ('review_completed'); seed 'review_completed' |
| **Drawdown circuit breaker (DEFAULT opt-in disabled per §1.4; sign convention: thresholds are negative R per Phase 10 §2 lock — drawdowns are always ≤ 0)** | | | |
| `drawdown_circuit_breaker_enabled` | INTEGER | NOT NULL | CHECK IN (0,1) DEFAULT 0 |
| `drawdown_pause_threshold_R` | REAL | nullable | CHECK < 0 OR NULL (R1 Major #7 fix — Phase 10 sign convention); required at app-layer when `drawdown_circuit_breaker_enabled=1`; runtime predicate per v1.2 §7.8: `current_drawdown_R <= drawdown_pause_threshold_R` (both signed-negative). Enforce-when-enabled via app-layer validator (cross-field CHECK with sentinel NULL is feasible but the validator path stays the binding contract per §3.1.1). |
| `drawdown_pause_action` | TEXT | nullable | CHECK IN ('halt_new_entries','reduce_size') OR NULL; required at app-layer when enabled |
| `drawdown_size_reduction_pct` | REAL | nullable | CHECK > 0 AND ≤ 1 OR NULL; required at app-layer when `drawdown_pause_action='reduce_size'`; expressed as fraction (0.50 = halve sizing) |
| `drawdown_recovery_threshold_R` | REAL | nullable | CHECK < 0 OR NULL (Phase 10 sign convention); required at app-layer when enabled; runtime: drawdown recovers when `current_drawdown_R >= recovery_threshold_R` (closer to zero than pause_threshold) |
| **Capital + sizing (Phase 10 §6.2 split-policy capture-need)** | | | |
| `capital_floor_constant_dollars` | REAL | NOT NULL | CHECK > 0; default seed 7500.0 (governance-anchor; Phase 10 §2 split-policy) |
| **Statistics-methodology knobs (Phase 10 §6.2 capture-needs)** | | | |
| `scratch_epsilon_R` | REAL | NOT NULL | CHECK > 0; default seed 0.10 (per v1.1-alternate F-014) |
| `review_lag_threshold_days` | INTEGER | NOT NULL | CHECK > 0; default seed 7 (matches Phase 6 `cfg.review.review_window_days`) |
| `low_sample_size_threshold_class_a_n` | INTEGER | NOT NULL | CHECK > 0; default seed 3 (Phase 10 §5 Class A — rate metrics suppress threshold) |
| `low_sample_size_threshold_class_b_n` | INTEGER | NOT NULL | CHECK > 0; default seed 5 (Phase 10 §5 Class B mean / sum-over-fixed-denominator) |
| `low_sample_size_threshold_class_c_n` | INTEGER | NOT NULL | CHECK > 0; default seed 5 (Phase 10 §5 Class C — ratio metrics requiring win-loss diversity) |
| `low_sample_size_threshold_class_d_n` | INTEGER | NOT NULL | CHECK > 0; default seed 10 (Phase 10 §5 Class D — trend / rolling-window) |
| `global_confidence_floor_n` | INTEGER | NOT NULL | CHECK > 0; default seed 20 (Phase 10 R3 M2 lock) |
| `bootstrap_resample_count` | INTEGER | NOT NULL | CHECK > 0; default seed 1000 (Phase 10 §3.3 cohort_expectancy_with_CI) |
| `process_grade_weight_entry` | REAL | NOT NULL | CHECK > 0 AND < 1; default seed 0.40 (Phase 6 hardcode externalized) |
| `process_grade_weight_management` | REAL | NOT NULL | CHECK > 0 AND < 1; default seed 0.35 |
| `process_grade_weight_exit` | REAL | NOT NULL | CHECK > 0 AND < 1; default seed 0.25 |
| **MFE/MAE precision (Phase 8 §11.1 capture-need)** | | | |
| `mfe_mae_default_precision_level` | TEXT | NOT NULL | CHECK IN ('daily_approximate','intraday_estimated','intraday_exact'); default seed 'daily_approximate' |
| `trail_MA_period_days` | INTEGER | NOT NULL | CHECK > 0; default seed 21 (Phase 8 §6.6 lock externalized) |
| `trail_MA_post_2R_period_days` | INTEGER | nullable | CHECK > 0 OR NULL; default seed NULL (V1 = no upgrade); V2 may set 10 (Tier-3 #6 doctrine) |
| **Sum-to-1.0 cross-field constraint** | | | |
| The three `process_grade_weight_*` fields MUST sum to 1.0 within tolerance ±1e-9. (R1 Minor #4 correction — earlier wording over-claimed that SQLite cannot CHECK cross-column arithmetic. SQLite CAN: `CHECK (ABS((entry+management+exit) - 1.0) < 1e-9)` is valid.) Spec keeps app-layer validator as the binding contract for clearer error messaging + UI form integration; schema-level CHECK is added as defense-in-depth at writing-plans-time (operator-actionable: writing-plans verifies CHECK syntax executes correctly under SQLite-runner). |

**Field count:** 28 columns (7 metadata + supersession + 13 trading-risk + 5 statistics-methodology grade weights, etc.).

#### §3.1.1 Per-row policy stamping (Phase 8 R1 M5 lesson — BINDING)

Per Phase 8 brainstorm lesson "Per-row stamp of policy-versioned values prevents historical-row reinterpretation under risk_policy changes" — Phase 9 must enumerate per-row stamps where historical reinterpretation matters. Locked stamps:

| Consumer table | Stamp column added | Rationale |
|---|---|---|
| `trades` (Phase 7 shipped) | `risk_policy_id_at_lock` (INTEGER FK → `risk_policy(policy_id)`, nullable for legacy) | Trades pre-Phase-9 have NULL; new trades stamp at `pre_trade_locked_at`; preserves capital floor + scratch_epsilon + tripwire interpretation for the trade's lifetime. |
| `review_log` (Phase 6 shipped) | `risk_policy_id_at_review_completion` (INTEGER FK → `risk_policy(policy_id)`, nullable until completion) | Set at completion-time (alongside frozen aggregates). Preserves which `scratch_epsilon` + `process_grade_weights` produced the frozen aggregates. |
| `daily_management_records` (Phase 8 will ship in v15→v16) | NO new column for V1 (R1 Major #3 ACCEPTED with rationale + V2 trigger); resolves via `trade_id → trades.risk_policy_id_at_lock` for trade-grain interpretation | **Phase 8 already stamps `trail_MA_period_days` per-row** (Phase 8 §3.1 column; R1 M5 satisfied for SMA period at snapshot grain). **Phase 8 already stamps `mfe_mae_precision_level` per-row** (Phase 8 §3.1 column). **Phase 8 already stamps `position_capital_denominator_dollars` per-row** (Phase 8 §3.1 column; R1 Major #4 self-stamp at snapshot time). Every Phase 8 column whose value derives from a Phase 9 risk_policy field is ALREADY self-stamped at snapshot-emit-time. **R1 Major #3 trigger condition for V2:** if a future Phase 9 policy field is added that Phase 8 daily_management consumes at snapshot-emit-time WITHOUT Phase 8 self-stamping it, V2 must add a `risk_policy_id_at_snapshot` FK column on daily_management_records. V1 audit at writing-plans-time MUST verify no such field exists pre-ship. |
| `account_equity_snapshots` (Phase 9 §3.5) | NO stamp; capital floor is static per-policy and snapshots are capital-state, not capital-doctrine. | Snapshot date + source already capture the meaningful provenance. |
| `hypothesis_status_history` (Phase 9 §3.4) | NO stamp; status transitions are operator-decision-anchored, not policy-anchored. | |

**Migration mechanic for `trades.risk_policy_id_at_lock`:** `ALTER TABLE trades ADD COLUMN risk_policy_id_at_lock INTEGER REFERENCES risk_policy(policy_id)` — no rebuild needed (nullable column add). Legacy rows (pre-Phase-9) stay NULL; new entries set at `pre_trade_locked_at` (Phase 7's `entry_create` service path stamps; writing-plans extends).

**Migration mechanic for `review_log.risk_policy_id_at_review_completion`:** `ALTER TABLE review_log ADD COLUMN risk_policy_id_at_review_completion INTEGER REFERENCES risk_policy(policy_id)` — no rebuild. Legacy completed rows stay NULL; new completions stamp at completion path.

#### §3.1.2 Indexes

```
-- Active-policy uniqueness: ONE non-superseded row at a time.
CREATE UNIQUE INDEX ux_risk_policy_active
    ON risk_policy (is_active)
    WHERE is_active = 1;

-- Effective-from timeline reads.
CREATE INDEX ix_risk_policy_effective_from
    ON risk_policy (effective_from);
```

The `ux_risk_policy_active` partial unique index forbids two non-superseded rows simultaneously. Successor INSERT must follow the §4.1 6-step transactional sequence (`is_active=0` predecessor BEFORE `is_active=1` successor INSERT) to avoid violating the index mid-transaction.

#### §3.1.3 Seed migration content (LOCKED — writing-plans drafts SQL)

The migration that creates `risk_policy` MUST seed `policy_id=1` from current `swing.config.toml` values:

| risk_policy column | Seed source |
|---|---|
| `effective_from` | DATE of migration apply (writing-plans bakes the date in or uses `date('now')`) |
| `is_active` | 1 |
| `max_account_risk_per_trade_pct` | `cfg.risk.max_risk_pct × 100` (toml stores as fraction; v1.2 §7.8 form is percent — verify at writing-plans-time and pick one canonical unit) |
| `max_concurrent_positions` | `cfg.position_limits.hard_cap_open` |
| `max_portfolio_heat_pct` | constant 3.0 (NOT in current toml; v1.2 default; operator can edit post-seed) |
| `max_sector_concentration_positions` | constant 3 (NOT in current toml; v1.2 default) |
| `consecutive_losses_pause_threshold` | constant 3 (v1.2 default) |
| `drawdown_circuit_breaker_enabled` | 0 (default opt-in disabled per §1.4) |
| `drawdown_pause_threshold_R` / `pause_action` / `size_reduction_pct` / `recovery_threshold_R` | NULL (gated on enabled=1) |
| `capital_floor_constant_dollars` | `cfg.account.risk_equity_floor` (currently 7500.0) |
| `scratch_epsilon_R` | constant 0.10 |
| `review_lag_threshold_days` | `cfg.review.review_window_days` (currently 7) |
| `low_sample_size_threshold_class_*_n` | constants 3 / 5 / 5 / 10 |
| `global_confidence_floor_n` | constant 20 |
| `bootstrap_resample_count` | constant 1000 |
| `process_grade_weight_entry / management / exit` | constants 0.40 / 0.35 / 0.25 |
| `mfe_mae_default_precision_level` | constant 'daily_approximate' |
| `trail_MA_period_days` | constant 21 |
| `trail_MA_post_2R_period_days` | NULL |

**Operational consequence (LOCKED — R1 Major #8 fix; previously deferred to §10.1):** post-Phase-9 ship, `risk_policy` IS the source-of-truth for every field that has a corresponding column. The transition contract:

1. **At Phase 9 ship-time:** the v16→v17 migration seeds `policy_id=1` from current TOML values per the table above.
2. **Post-Phase-9, for the 3 currently-Phase-5-surfaced fields** (`cfg.web.chase_factor`, `cfg.pipeline.chart_top_n_watch`, `cfg.account.risk_equity_floor`):
   - `cfg.account.risk_equity_floor` corresponds to `risk_policy.capital_floor_constant_dollars` — Phase 5 config page edit MUST cascade to a new `risk_policy` row (writing-plans wires this); the cfg field becomes a startup-mirror (read-only, refreshed at process start from `risk_policy.is_active=1` row). If operator hand-edits `swing.config.toml` directly, startup detects divergence + logs a warning + writes a new `risk_policy` row matching the TOML edit (operator-paced reconciliation; no auto-write under operator's hands).
   - `cfg.web.chase_factor` and `cfg.pipeline.chart_top_n_watch` are NOT risk_policy fields (operational-tunable, not policy). They stay cfg-managed.
3. **Post-Phase-9, for non-Phase-5-surfaced fields** (the 21 statistics-methodology + drawdown + sector-concentration + MFE/MAE precision fields newly introduced by §3.1): edited via `swing config policy ...` CLI (V1) or future Phase 10+ web form. Each edit creates a new policy_id row.
4. **Read path discipline:** all policy-value reads (Phase 8 snapshot emit; Phase 6 review computation; Phase 10 metric layer; Phase 9 reconciliation discrepancy classifier) resolve via either `trades.risk_policy_id_at_lock` (at-trade-time semantics — capital_floor, scratch_epsilon, tripwire, MA periods) OR `risk_policy.is_active=1` (live-time semantics — statistics-methodology knobs at dashboard render). NEVER from cfg.
5. **Backwards-compatibility:** the existing `cfg.account.starting_equity` + `cfg.account.starting_date` + `cfg.account.risk_equity_floor` persist; only `risk_equity_floor` becomes mirrored. `starting_equity` + `starting_date` are static (account-open snapshots), not policy. Phase 5 config-page existing field set is preserved.

#### §3.1.4 Versioning-model decision rationale (LOCKED — per-policy-snapshot)

**Decision:** ONE row per policy snapshot. Each operator change to ANY field creates a new `policy_id` row.

**Counter-considered:** PER-FIELD versioning (each field has its own effective_from / effective_to history table). Rejected because:

1. **Read complexity explodes.** Resolving "policy-effective-at-trade-lock" becomes 24 separate queries (one per field) per trade read. For our scale (~50 trades/year), the cardinality ratio is wrong; per-policy-snapshot resolves in ONE row read.
2. **Audit-chain integrity is harder to enforce.** Per-field versioning fragments history across N tables; ensuring ALL fields have consistent effective_from for a given trade-time becomes an integrity discipline rather than a schema invariant.
3. **Operator workflow.** Operator edits policy values in batches (config-page form). Per-policy-snapshot matches that workflow naturally; per-field would explode every form-save into N audit rows.
4. **n=2 closed sample size.** We are years away from policy-version cardinality being a database-design concern. The simpler model wins.

**Trade-off accepted:** changing one field forces a full row copy. This is acceptable; operator changes are rare (V1 expects <10 risk_policy versions over the life of the account).

---

### §3.2 New table: `reconciliation_runs`

**Lifecycle:** `running` → `completed` (success path) | `failed` (error path). Mirrors `pipeline_runs` lifecycle convention (per `swing/data/migrations/0001*` pipeline_runs schema).

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `run_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `source` | TEXT | NOT NULL | CHECK IN ('tos_csv','schwab_api','manual','system_audit'); V1 ships with 'tos_csv' + 'system_audit' active + 'schwab_api' + 'manual' reserved (R1 Minor #2 fix — `system_audit` distinguishes route-layer-emitted ad-hoc runs (e.g., the §7 sector_tamper rejection) from operator-initiated reconciliation; prevents `manual` from being overloaded with two semantics) |
| `source_artifact_path` | TEXT | nullable | absolute path to TOS CSV (V1) or null for `schwab_api` runs (no artifact) |
| `source_artifact_sha256` | TEXT | nullable | content-hash of source artifact at run-start (TOS CSV); NULL for `schwab_api`; supports re-run idempotency check |
| `period_start` | TEXT | nullable | ISO date; reconciliation period inclusive lower bound; NULL for full-account snapshot mode |
| `period_end` | TEXT | nullable | ISO date; reconciliation period inclusive upper bound; NULL for full-account snapshot mode |
| `started_ts` | TEXT | NOT NULL | ISO datetime; naive-UTC per §9 |
| `finished_ts` | TEXT | nullable | ISO datetime; naive-UTC; NULL while `state='running'` |
| `state` | TEXT | NOT NULL | CHECK IN ('running','completed','failed') DEFAULT 'running' |
| `account_equity_journal_dollars` | REAL | nullable | journal-side equity at period_end; resolves from `account_equity_snapshots` if a snapshot exists for `period_end`, else NULL |
| `account_equity_source_dollars` | REAL | nullable | source-side equity (TOS Account Summary net-liq; Schwab API balances); NULL when source doesn't surface |
| `equity_delta_dollars` | REAL | nullable | computed `account_equity_journal_dollars - account_equity_source_dollars`; NULL when either side is NULL |
| `trades_reconciled_count` | INTEGER | nullable | count of trades touched in this run |
| `fills_reconciled_count` | INTEGER | nullable | count of fills examined |
| `discrepancies_count` | INTEGER | nullable | count of discrepancies emitted (joined to `reconciliation_discrepancies` for detail) |
| `unresolved_discrepancies_count` | INTEGER | nullable | count where `resolution='unresolved'` at run-end |
| `summary_json` | TEXT | nullable | JSON; source-specific aggregates (e.g., `unmatched_open_fills_count`, `already_reconciled_count`, etc.); free-form for V1 |
| `error_message` | TEXT | nullable | populated when state='failed' |
| `notes` | TEXT | nullable | operator free-text |

**Field count:** 17 columns.

**Indexes:**

```
CREATE INDEX ix_reconciliation_runs_started_ts
    ON reconciliation_runs (started_ts);

CREATE INDEX ix_reconciliation_runs_state
    ON reconciliation_runs (state)
    WHERE state IN ('running','failed');

CREATE INDEX ix_reconciliation_runs_source
    ON reconciliation_runs (source, started_ts);
```

The partial-index on `state` accelerates "show me current+failed runs" dashboard reads (Phase 10+ surface). The composite `(source, started_ts)` index supports the "most-recent run per source" query.

**Pipeline_runs convention inheritance:** the `started_ts DESC ORDER BY` query that masks last-completed runs (CLAUDE.md gotcha "Queries ordered by `started_ts DESC` on `pipeline_runs` mask prior completes mid-run") applies HERE too. Writing-plans MUST adopt the two-read pattern: most-recent COMPLETED for "when did we last reconcile?" + most-recent-started for "what's running now?"

---

### §3.3 New table: `reconciliation_discrepancies`

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `discrepancy_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `run_id` | INTEGER | NOT NULL | FK → `reconciliation_runs(run_id)` ON DELETE CASCADE |
| `discrepancy_type` | TEXT | NOT NULL | CHECK IN ('close_price_mismatch','stop_mismatch','position_qty_mismatch','cash_movement_mismatch','sector_tamper','snapshot_mismatch','unmatched_open_fill','unmatched_close_fill','entry_price_mismatch','equity_delta') |
| `trade_id` | INTEGER | nullable | FK → `trades(id)` ON DELETE SET NULL; populated when discrepancy attributes to a known trade |
| `fill_id` | INTEGER | nullable | FK → `fills(fill_id)` ON DELETE SET NULL; populated when discrepancy attributes to a specific fill (close_price_mismatch typically) |
| `cash_movement_id` | INTEGER | nullable | FK → `cash_movements(id)` ON DELETE SET NULL; populated for cash_movement_mismatch |
| `linked_daily_management_record_id` | INTEGER | nullable | FK → `daily_management_records(management_record_id)` ON DELETE SET NULL; populated for snapshot_mismatch type |
| `ticker` | TEXT | nullable | denormalized from trade for ticker-keyed types (sector_tamper, position_qty_mismatch); NULL for run-grain types like equity_delta |
| `field_name` | TEXT | NOT NULL | which field disagreed (e.g., 'price', 'current_stop', 'qty', 'sector', 'industry', 'amount') |
| `expected_value_json` | TEXT | nullable | JSON; journal-side value(s); shape per §3.3.1 type table |
| `actual_value_json` | TEXT | nullable | JSON; source-side value(s); shape per §3.3.1 type table |
| `delta_text` | TEXT | nullable | human-readable summary (e.g., "$0.20 difference"; "5 vs 3 shares"); display-aid only — not a programmatic field |
| `material_to_review` | INTEGER | NOT NULL | CHECK IN (0,1); computed at INSERT-time per discrepancy_type lookup (see §3.3.2 + §5.1) |
| `resolution` | TEXT | NOT NULL | CHECK IN ('journal_corrected','source_treated_canonical','manual_override','unresolved','acknowledged_immaterial') DEFAULT 'unresolved' |
| `resolution_reason` | TEXT | nullable | required at app-layer when resolution != 'unresolved' AND != 'acknowledged_immaterial' |
| `resolved_at` | TEXT | nullable | ISO datetime; naive-UTC; populated when resolution moves off 'unresolved' |
| `resolved_by` | TEXT | nullable | session/user identifier; V1 hardcoded 'operator' |
| `mistake_tag_assigned` | TEXT | nullable | optional tag from `swing/trades/review.py` mistake_tags vocabulary; populated when reconciliation surfaces a discipline failure (e.g., MOVED_STOP_AWAY surfaced via stop_mismatch) |
| `created_at` | TEXT | NOT NULL | ISO datetime; system wall-clock at row INSERT |

**Field count:** 18 columns.

**Indexes:**

```
CREATE INDEX ix_reconciliation_discrepancies_run
    ON reconciliation_discrepancies (run_id);

CREATE INDEX ix_reconciliation_discrepancies_trade
    ON reconciliation_discrepancies (trade_id)
    WHERE trade_id IS NOT NULL;

CREATE INDEX ix_reconciliation_discrepancies_unresolved
    ON reconciliation_discrepancies (resolution)
    WHERE resolution = 'unresolved';

CREATE INDEX ix_reconciliation_discrepancies_material
    ON reconciliation_discrepancies (trade_id, material_to_review)
    WHERE material_to_review = 1 AND resolution = 'unresolved';
```

The two partial indexes accelerate "open discrepancy review" dashboard queries; the composite index on `(trade_id, material_to_review)` supports the Phase 6 dashboard "needs re-review" badge query (§5.1).

#### §3.3.1 expected_value_json / actual_value_json shape per discrepancy_type (LOCKED)

JSON shapes are per-type contracts; writing-plans bakes a JSON-shape validator (mirrors Phase 7 `trade_events.payload_json` discipline). All values are scalars or short objects; no nested arrays beyond the documented types.

| discrepancy_type | expected_value_json shape (journal) | actual_value_json shape (source) | trade_id-linked? | material_to_review default |
|---|---|---|---|---|
| `close_price_mismatch` | `{"price": <journal exit price (REAL)>, "exit_date": <ISO date>}` | `{"price": <tos price (REAL)>, "fill_date": <ISO date>}` | YES (+ fill_id) | 1 (TRUE) |
| `stop_mismatch` | `{"current_stop": <journal stop (REAL)>}` | `{"working_stop_price": <tos working stop (REAL)>, "order_id": <tos ref or null>}` | YES | 1 (TRUE) |
| `position_qty_mismatch` | `{"qty": <journal current_size (REAL)>}` | `{"qty": <source qty (REAL)>}` | YES (when ticker matches a trade) | 1 (TRUE) |
| `cash_movement_mismatch` | `{"amount": <journal amount (REAL)>, "kind": <"deposit"|"withdraw">, "ref": <ref or null>}` | `{"amount": <source amount (REAL)>, "kind": <"deposit"|"withdraw">, "ref": <ref or null>}` | NO (cash_movement_id) | 0 (FALSE — cash flow doesn't bear on trade review) |
| `sector_tamper` | `{"sector": <cached sector>, "industry": <cached industry>, "session": <ISO date>}` | `{"sector": <form-submitted sector>, "industry": <form-submitted industry>}` | YES | 0 (FALSE in V1; ELEVATES to TRUE when sector concentration becomes a gating dimension — see §7) |
| `snapshot_mismatch` | `{"current_size": <daily_management_records.current_size>, "asof_session": <ISO date>}` | `{"position_qty": <broker qty>, "asof_session": <ISO date>}` | YES (+ linked_daily_management_record_id) | 0 (FALSE — broker authoritative; daily snapshot is run-time view) |
| `unmatched_open_fill` | `{}` (no journal counterpart) | `{"price": <REAL>, "qty": <INT>, "ticker": <str>, "fill_date": <ISO date>}` | NO (no trade ever created) | 1 (TRUE — a TOS open fill with no journal entry is operationally severe) |
| `unmatched_close_fill` | `{}` | `{"price": <REAL>, "qty": <INT>, "ticker": <str>, "fill_date": <ISO date>}` | NO (no trade matched) | 1 (TRUE — could indicate missed exit recording) |
| `entry_price_mismatch` | `{"price": <journal entry_price (REAL)>, "entry_date": <ISO date>}` | `{"price": <tos entry price (REAL)>, "fill_date": <ISO date>}` | YES (+ fill_id) | 1 (TRUE) |
| `equity_delta` | `{"equity_dollars": <journal equity (REAL)>}` | `{"equity_dollars": <source equity (REAL)>}` | NO (run-grain only) | 0 (FALSE — surfaces as a run-summary metric, not a per-trade reopen trigger) |

#### §3.3.2 material_to_review default lookup + override semantics (R1 Major #6 fix — non-trade-linked behavior locked)

The `material_to_review` boolean is COMPUTED at INSERT-time by the discrepancy emitter (writing-plans codifies the lookup as `MATERIAL_BY_TYPE: dict[str,int]`). Operator may override per-row at app-layer post-INSERT. Schema CHECK does NOT bind type → material mapping; the binding lives in the validator. Rationale: type-to-material mapping changes when sector concentration becomes a gate (V2 elevates `sector_tamper` from immaterial → material); putting it in CHECK requires a schema migration to flip; putting it in the validator requires a code commit only.

**Operator-override semantics (LOCKED):** `material_to_review` is a CLASSIFICATION flag, NOT a workflow trigger. The §5.1 "trades flagged for re-review attention" query joins on `trade_id IS NOT NULL AND material_to_review=1 AND resolution='unresolved'` — discrepancies WITHOUT `trade_id` (run-grain `equity_delta`; cash_movement-grain `cash_movement_mismatch`; orphan `unmatched_open_fill` / `unmatched_close_fill` with no journal trade to attribute to) NEVER appear in the trade-attention query, regardless of `material_to_review` value.

For non-trade-linked discrepancies, operator dispositioning happens via the resolution lifecycle (§4.2):

| discrepancy_type (non-trade-linked) | Operator action when material=1 (overridden) | Rendering surface |
|---|---|---|
| `equity_delta` | Resolve via journal correction (e.g., add missing cash_movement) → `resolution='journal_corrected'` | Run-summary surface (Phase 10+ dashboard "reconciliation status" badge) |
| `cash_movement_mismatch` | Resolve via journal correction → resolution=journal_corrected; OR acknowledge → `acknowledged_immaterial` | Discrepancy list page (Phase 10+ writing-plans) |
| `unmatched_open_fill` (no trade_id, ticker only) | Operator creates the missed trade journal entry → resolution=journal_corrected; OR acknowledges (e.g., the trade was a previously-closed trade not in our DB scope) → `acknowledged_immaterial` | Run-summary surface; discrepancy list |
| `unmatched_close_fill` (no trade_id) | Same as above; or operator records the matching exit fill on an existing open trade | Same |
| `sector_tamper` (V1 immaterial; V2 material when gate elevates) | Acknowledge in V1; in V2 when gate elevates, audit-investigate the cache-vs-form drift before re-attempting entry | Sector-concentration audit surface (V2 only) |
| `snapshot_mismatch` (V2 only when Schwab Phase A wires emitter) | Resolve when broker / journal alignment is verified | Phase 8 daily_management UI extension (Phase 10+) |

**Why operator override is allowed but does NOT trigger trade-attention:** The classification flag default is BEST GUESS at type-to-material mapping; operator may know context that elevates an otherwise-immaterial discrepancy (e.g., a cash_movement_mismatch reveals the operator made an account-fund-transfer error that affects sizing for the next several trades — material to operator's broader practice but NOT to a specific trade's review). The override flips the badge surface; it does NOT manufacture a phantom trade-attention row. This avoids the failure mode where a non-trade discrepancy with operator-override `material=1` generates phantom trade-list entries via `trade_id IS NULL` joins.

**Strict-validator note:** writing-plans CHECK constraint should NOT enforce `(material_to_review=1 → trade_id IS NOT NULL)` — operator-discretion is the binding; otherwise legitimate "this is material to my workflow even though no specific trade ties to it" overrides become impossible.

#### §3.3.3 Reconciliation_Run + Discrepancies single-transaction emit (LOCKED)

A reconciliation run that produces N discrepancies MUST emit them in a single transaction with the run row's state transition `running → completed`:

```
1. BEGIN IMMEDIATE TRANSACTION
2. INSERT INTO reconciliation_runs (..., state='running', started_ts=now) RETURNING run_id
3. (Run reconciliation logic; collect discrepancies in memory)
4. For each discrepancy: INSERT INTO reconciliation_discrepancies (run_id, ...)
5. UPDATE reconciliation_runs SET state='completed', finished_ts=now, discrepancies_count=N, ... WHERE run_id=?
6. COMMIT
```

Failure path (step 3 throws): catch + UPDATE state='failed', finished_ts=now, error_message=str(e); COMMIT. This preserves the run row so the operator sees "what failed" (mirrors `pipeline_runs` failure semantics).

**Why BEGIN IMMEDIATE:** prevents writer-conflict if a second reconcile is launched concurrently (V1 single-operator, but defensive). Codex R3 Major #5 in Phase 8 spec set this precedent.

---

### §3.4 New table: `hypothesis_status_history`

Append-only audit. One row per `hypothesis_registry.status` UPDATE. Mirrors v1.1-alternate F-022 pattern.

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `history_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `hypothesis_id` | INTEGER | NOT NULL | FK → `hypothesis_registry(id)` ON DELETE CASCADE |
| `status` | TEXT | NOT NULL | CHECK IN ('active','paused','closed-escaped','closed-target-met'); same enum as `hypothesis_registry.status` |
| `effective_from` | TEXT | NOT NULL | ISO datetime; transition timestamp (when the status was set); naive-UTC per §9 |
| `effective_to` | TEXT | nullable | ISO datetime; transition-out timestamp; NULL for the current row; set when this status is superseded by next transition |
| `change_reason` | TEXT | nullable | operator free-text from `swing hypothesis update --status --reason "..."`; NULL for seed row only |
| `recorded_at` | TEXT | NOT NULL | ISO datetime; system wall-clock at INSERT; may differ from `effective_from` if back-recording (validator rejects when back-record gap exceeds policy — writing-plans codifies) |

**Field count:** 7 columns.

**Indexes:**

```
CREATE INDEX ix_hypothesis_status_history_hyp
    ON hypothesis_status_history (hypothesis_id, effective_from);

-- Current-row partial unique: ONE row per hypothesis with effective_to IS NULL.
CREATE UNIQUE INDEX ux_hypothesis_status_history_current
    ON hypothesis_status_history (hypothesis_id)
    WHERE effective_to IS NULL;
```

The partial-unique index enforces "exactly one current row per hypothesis" at schema level (defense-in-depth against application-layer bug introducing two open intervals).

#### §3.4.0 Why no `is_superseded` + `superseded_by_history_id` dual-column pattern (R1 Major #1 — ACCEPTED with rationale)

The Phase 8 R2 dual-column lesson applies when the supersession SEQUENCE is `INSERT successor → UPDATE predecessor's FK pointer`, because between those two steps the active-row uniqueness slot is occupied by BOTH rows (predecessor's `is_superseded=0` flag must be UPDATEd FIRST to free the slot; the FK pointer is set LATER once successor's PK is known). On `risk_policy`, that's exactly the §4.1 6-step sequence.

`hypothesis_status_history` does NOT need the dual-column pattern because the supersession sequence is REVERSED: predecessor is closed (`UPDATE prior SET effective_to=NOW`) BEFORE successor is INSERTed. There is no intermediate state where two rows have `effective_to IS NULL` for the same `hypothesis_id`. The FK chain is implicit via `effective_from` chronology — readers query "what came after row X?" by `WHERE effective_from = (SELECT effective_to FROM hsh WHERE history_id=X)`. No FK pointer needed.

If a future workflow demands "what immediately replaced this row?" as an O(1) lookup (e.g., audit-trail visualization with predecessor/successor links), writing-plans can ADD `superseded_by_history_id INTEGER` column at-need without breaking V1 readers. V1 ships without it.

#### §3.4.1 Append-on-status-update mechanism (LOCKED — application-layer, not SQL trigger)

Decision: **application-layer enforcement, NOT SQL trigger.** Rationale:

1. **Validation at write-time.** Validator can check `effective_from >= prior row's effective_from` + `change_reason` non-empty + status enum.
2. **Audit-trail integrity.** SQL triggers fire on EVERY UPDATE; backfill operations (data migration, repair) need to bypass — application-layer gives explicit control.
3. **Phase 7 lesson alignment.** "State-bearing entity validation must distinguish operation enforcement from data invariant" (Phase 7 R1 Critical 1 lesson). Status transition is an OPERATION, not a passive invariant.

**Service-layer contract (binding for writing-plans):** every code path that UPDATEs `hypothesis_registry.status` MUST flow through a single `hypothesis_repo.update_status_with_audit(...)` helper that:

1. Reads the current `hypothesis_registry.status` row.
2. If status unchanged: no-op (defensive; status transition is identity → reject at app-layer).
3. BEGIN IMMEDIATE TRANSACTION.
4. UPDATE hypothesis_status_history SET effective_to=now WHERE hypothesis_id=? AND effective_to IS NULL.
5. INSERT INTO hypothesis_status_history (hypothesis_id, status, effective_from=now, effective_to=NULL, change_reason, recorded_at=now).
6. UPDATE hypothesis_registry SET status=new_status, status_changed_at=now, status_change_reason=reason WHERE id=?.
7. COMMIT.

**Single-write-path discipline:** Phase 8 §5.3 introduces this discipline for stop-change cross-table coupling; Phase 9 inherits the pattern. Writing-plans gate enumerates ALL existing status-UPDATE call sites and re-routes them through the helper.

**Seed-row migration content:** the v16→v17 migration MUST insert a seed row per existing hypothesis_registry row, with:

- `effective_from` = `hypothesis_registry.created_at` (preserves chronology — the seed row represents "initial active status" effective from creation).
- `effective_to` = NULL (current row).
- `status` = current `hypothesis_registry.status`.
- `change_reason` = NULL (no prior change).
- `recorded_at` = migration apply time.

For hypotheses whose `status_changed_at` is NOT NULL (any of the seeded 4 might have been mutated post-Phase-9-deploy if some operator action sneaks in — defensive), writing-plans handles the two-row backfill (one row from `created_at` → `status_changed_at`, one row from `status_changed_at` → NULL with status=current). Production DB at v15 has all 4 hypotheses at default `status='active'` with `status_changed_at=NULL`, so single-row seed suffices for current state.

---

### §3.5 New table: `account_equity_snapshots`

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `snapshot_id` | INTEGER PRIMARY KEY | NOT NULL | autoincrement |
| `snapshot_date` | TEXT | NOT NULL | ISO date (YYYY-MM-DD); chronology field; one row per (snapshot_date, source) |
| `equity_dollars` | REAL | NOT NULL | CHECK > 0; account net liquidation value at snapshot_date close-of-business |
| `source` | TEXT | NOT NULL | CHECK IN ('manual','schwab_api','tos_csv'); V1 ships 'manual' active + 'schwab_api' + 'tos_csv' reserved (R1 Minor #3 fix — vocabulary harmonized with `reconciliation_runs.source`; was `csv_import`, renamed to `tos_csv` for consistency. Future broker CSV imports — e.g., a hypothetical Schwab-CSV-export — would extend the enum then; do not over-anticipate) |
| `source_artifact_path` | TEXT | nullable | path to underlying CSV / API response cache; NULL for 'manual' |
| `recorded_at` | TEXT | NOT NULL | ISO datetime; system wall-clock at INSERT |
| `recorded_by` | TEXT | NOT NULL | session/user identifier; V1 hardcoded 'operator' |
| `notes` | TEXT | nullable | free-text |

**Field count:** 8 columns.

**Indexes:**

```
-- One row per (snapshot_date, source).
CREATE UNIQUE INDEX ux_account_equity_snapshots_date_source
    ON account_equity_snapshots (snapshot_date, source);

-- Most-recent-equity reads (Phase 8 position_capital_utilization_pct resolution).
CREATE INDEX ix_account_equity_snapshots_date
    ON account_equity_snapshots (snapshot_date);
```

The unique index `(snapshot_date, source)` allows BOTH a manual-entry row AND a future Schwab-API row to coexist for the same date (operator-recorded vs broker-authoritative). Read-time precedence in Phase 8 + Phase 10 follows the source ladder: `schwab_api` > `tos_csv` > `manual`.

**Cadence:** V1 manual entry (CLI `swing account snapshot --equity 1234.56` + web form); V2 Schwab Phase A may emit `schwab_api` rows automatically. **Daily target; gaps allowed (Phase 8 §4.3 GAP-FLAGGED-no-auto-back-fill precedent).** Read-time consumers (Phase 8 `position_capital_utilization_pct`; Phase 10 `live_capital_denominator_dollars`) resolve to most-recent-snapshot-on-or-before-asof_date via `MAX(snapshot_date)` query; on absence, fall back to `risk_policy.capital_floor_constant_dollars` (Phase 10 §2 split-policy PROVISIONAL).

**Idempotency:** UPSERT pattern is SELECT-then-UPDATE-or-INSERT (per CLAUDE.md SQLite REPLACE gotcha + Phase 8 R4 lesson). Re-recording for the same `(snapshot_date, source)` UPDATEs the existing row's `equity_dollars` + `recorded_at`; never DELETE+INSERT.

**Back-fill policy:** GAP-FLAGGED (no auto back-fill). Operator may insert a row for a past `snapshot_date` manually if recall + verifiable; back-recorded rows have `recorded_at > snapshot_date` and are flagged at read-time as "back-recorded" if the gap exceeds 7 days (writing-plans codifies the threshold; Phase 8 precedent).

---

### §3.6 Modifications to existing tables

**`trades` (Phase 7 shipped) — ADD ONE COLUMN:**

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `risk_policy_id_at_lock` | INTEGER | nullable | FK → `risk_policy(policy_id)` ON DELETE SET NULL; populated at `pre_trade_locked_at` for new trades; NULL for legacy pre-Phase-9 trades + Phase 7-era trades that lack the stamp |

**Migration mechanic:** `ALTER TABLE trades ADD COLUMN risk_policy_id_at_lock INTEGER REFERENCES risk_policy(policy_id)` — no rebuild (nullable column add). Phase 7's locked-table-rebuild migration 0014 is NOT re-run.

**`review_log` (Phase 6 shipped) — ADD ONE COLUMN (R1 Major #4 + #5 fix):**

| Column | Type | Nullability | CHECK / FK |
|---|---|---|---|
| `risk_policy_id_at_review_completion` | INTEGER | nullable | FK → `risk_policy(policy_id)` ON DELETE SET NULL; populated at completion-time per §3.1.1 stamp discipline |

**Migration mechanic:** one `ALTER TABLE review_log ADD COLUMN ...` — no rebuild.

**Why `reopened_at` + `reopened_due_to_reconciliation_run_id` + `reopen_resolution_completed_at` are NOT added (R1 Major #4 fix — review_log is cadence-period-grain, NOT trade-grain):** Phase 6's `review_log` table tracks daily/weekly/monthly/quarterly/circuit_breaker cadence reviews; rows are keyed on `(review_type, period_start, period_end)`. There is NO `trade_id` column and NO bridge table mapping reviews to trades — a "weekly review" reviews ALL trades that closed in the period as a batch. Setting a reopen flag on review_log when ONE trade in the period has a material discrepancy would (a) reopen the entire period's review for one trade's discrepancy, (b) require a "most-recent review whose period overlaps trade close date" lookup that lacks a precise mapping when multiple reviews of different cadences cover the same trade. The reopen workflow is reframed as a query-side join (§5.1) instead of a row-side flag — the dashboard surfaces "reviews containing trades with unresolved material discrepancies" by JOINing review_log to trades-by-period-overlap to discrepancies. No schema additions to review_log beyond the policy-id stamp.

**`hypothesis_registry` (Phase 1 shipped via migration 0008) — NO MODIFICATIONS.** The audit history lives in the new `hypothesis_status_history` child table. The shipped `hypothesis_registry.status` + `status_changed_at` + `status_change_reason` columns retain their meaning as "current-row denorm" of the most-recent transition (writing-plans keeps them in sync via the §3.4.1 service helper).

**No other modifications.** `fills`, `trade_events`, `cash_movements`, `daily_management_records` (Phase 8 shipped in v16) are read-only consumers from Phase 9.

---

### §3.7 Phase 10 §6.2 + Phase 8 §11 capture-need cross-check

| Capture-need | §3 column / table | Status |
|---|---|---|
| Phase 10 §6.2 `scratch_epsilon` | `risk_policy.scratch_epsilon_R` | ✅ |
| Phase 10 §6.2 `review_lag_threshold_days` | `risk_policy.review_lag_threshold_days` | ✅ |
| Phase 10 §6.2 low_sample_size_thresholds_class_a/b/c/d | `risk_policy.low_sample_size_threshold_class_a/b/c/d_n` | ✅ |
| Phase 10 §6.2 `global_confidence_floor_n` | `risk_policy.global_confidence_floor_n` | ✅ |
| Phase 10 §6.2 `bootstrap_resample_count` | `risk_policy.bootstrap_resample_count` | ✅ |
| Phase 10 §6.2 `process_grade_weights_entry / management / exit` | `risk_policy.process_grade_weight_entry/management/exit` | ✅ |
| Phase 10 §6.2 `hypothesis_status_history` audit | `hypothesis_status_history` table | ✅ |
| Phase 10 §6.2 `account_equity_snapshot_table` source enum | `account_equity_snapshots.source` | ✅ |
| Phase 10 §6.2 `capital_floor_versioning` | `risk_policy.capital_floor_constant_dollars` (per-policy versioning) | ✅ |
| Phase 10 §6.2 `reconciliation_runs` discrepancy surface | `reconciliation_runs` + `reconciliation_discrepancies` | ✅ |
| Phase 8 §11.1 `mfe_mae_default_precision_level` | `risk_policy.mfe_mae_default_precision_level` | ✅ |
| Phase 8 §11.1 `trail_MA_period_days` | `risk_policy.trail_MA_period_days` | ✅ |
| Phase 8 §11.1 `trail_MA_post_2R_period_days` | `risk_policy.trail_MA_post_2R_period_days` | ✅ |
| Phase 8 §11.1 `account_equity_snapshot_table` source enum | `account_equity_snapshots.source` (overlap with Phase 10 §6.2 same field) | ✅ |
| Phase 8 §11.2 snapshot reconciliation flag | `reconciliation_discrepancies.linked_daily_management_record_id` + `discrepancy_type='snapshot_mismatch'` | ✅ (Phase 9-side only; Phase 8 schema UNTOUCHED) |

**Coverage:** 15/15.

---

## §4 Capture cadence (LOCKED)

### §4.1 risk_policy: explicit-operator-action only

**Cadence:** NO periodic refresh. Triggered exclusively by:

1. **CLI:** `swing config policy set --field <name> --value <val>` (writing-plans designs the surface) OR `swing config policy update <bulk-form>`.
2. **Web:** Phase 5 config-page extension to edit risk_policy fields (writing-plans territory).

Each change INSERTs a new policy_id row + supersedes the prior row. **6-step transactional sequence (Phase 8 R3 Major 3 lesson — capture predecessor by exact PK):**

1. `BEGIN IMMEDIATE`.
2. `SELECT policy_id FROM risk_policy WHERE is_active=1` → `predecessor_id` (exactly one row by `ux_risk_policy_active`).
3. `UPDATE risk_policy SET is_active=0, effective_to=NOW WHERE policy_id=predecessor_id`.
4. `INSERT INTO risk_policy (..., is_active=1, effective_from=NOW, ...)` → `successor_id = last_insert_rowid()`.
5. `UPDATE risk_policy SET superseded_by_policy_id=successor_id WHERE policy_id=predecessor_id`.
6. `COMMIT`.

**Idempotency:** writing-plans MAY add an "input matches active policy" no-op short-circuit (compare all fields; if identical, skip insert). V1 default: no short-circuit (every save creates a row); operator's saves are infrequent (~10/year expected); audit trail of "operator saved with no change" is harmless.

**Back-fill:** NO auto back-fill. Seed migration creates `policy_id=1` with `effective_from=migration_apply_date`. If operator wants to back-record an effective_from earlier than migration date (e.g., "this policy was effective from account-open 2026-04-01"), writing-plans surfaces a one-shot `swing config policy backfill` CLI; not part of normal cadence.

**Schwab API coordination:** none. risk_policy is internal-doctrine; no external system writes to it.

### §4.2 reconciliation_runs + reconciliation_discrepancies: operator-paced CLI/web triggered

**Cadence:** triggered by:

1. **CLI:** `swing journal reconcile-tos --csv-path <path>` (refactored existing `swing journal import-tos` flow); future `swing journal reconcile-schwab` (V2 — Schwab Phase A); future `swing journal reconcile-manual --equity <val> --period-end <date>` (V2 — manual run for ad-hoc spot-checks).
2. **NOT a pipeline step.** Reconciliation is post-export / post-trade-close, not nightly. Operator-paced (per v1.2 §10.5: "Weekly reconciliation is required, but post-trade review can occur provisionally before reconciliation"). Pipeline already has its own gating discipline; bundling reconciliation in would invert the post-trade-review-can-precede-reconciliation flow.

**Single-transaction emit per §3.3.3.** The existing `swing/journal/tos_import.py:reconcile_tos` returns a `ReconciliationReport` dataclass; writing-plans refactors it to ALSO write `reconciliation_runs` + `reconciliation_discrepancies` rows. Backwards compatibility: the dataclass return-shape is preserved (CLI display layer still reads it); the persistence is new behavior. Existing callers (CLI, future web) are unchanged.

**Idempotency:** reruns over the same TOS CSV produce a NEW `reconciliation_runs` row each time (new `run_id`). The `source_artifact_sha256` column lets writing-plans surface "you already reconciled this CSV at run_id=X" warning at CLI-level (advisory, not blocking — operator may want to re-run after editing the CSV).

**Back-fill:** NO auto back-fill. Each run is a one-shot capture. Historical TOS CSVs that weren't reconciled at the time can be back-run (operator points the CLI at an old CSV; produces a run with appropriate `period_start` / `period_end`); back-runs flagged in `notes` field by operator.

**Resolution lifecycle:** discrepancies start at `resolution='unresolved'`. Operator dispositions via:

1. **CLI:** `swing journal discrepancy resolve <discrepancy_id> --resolution <enum> --reason "..."` (writing-plans).
2. **Web:** discrepancy detail page (writing-plans / Phase 10 dashboard extension).

UPDATE pattern is SELECT-then-UPDATE-or-INSERT (the row exists; just UPDATE) — NO `INSERT OR REPLACE`. The CLAUDE.md SQLite REPLACE gotcha applies because `reconciliation_discrepancies` has FK references (children ON DELETE CASCADE from `reconciliation_runs`, but also self-attribution to trade/fill/cash_movement/daily_management_record).

### §4.3 hypothesis_status_history: append-on-status-UPDATE

**Cadence:** append-only on every `hypothesis_registry.status` UPDATE — see §3.4.1 service-layer contract.

**Triggered by:**

1. **CLI:** `swing hypothesis update --hypothesis <name> --status <enum> --reason "..."` (existing CLI surface).
2. **Future web:** if writing-plans adds a hypothesis-management web surface (currently CLI-only); same service helper.

**Idempotency:** the service helper rejects identity transitions (current_status == new_status). No history row written; no `hypothesis_registry` UPDATE.

**Back-fill:** seed migration creates one row per existing hypothesis (with `effective_from = hypothesis_registry.created_at`). Post-Phase-9 ship, no automated back-fill of historical pre-Phase-9 status changes (none on production at writing-plans time per current state n=0 status changes; defensive — if a status changed between Phase 9 ship and writing-plans-time, the history captures from Phase 9 ship onward only).

### §4.4 account_equity_snapshots: V1 manual; V2 schwab_api

**V1 cadence:** manual entry. Operator-driven via:

1. **CLI:** `swing account snapshot --equity <REAL> [--date <ISO>] [--notes "..."]`. `--date` defaults to today's last-completed-NYSE-session per `last_completed_session(now)` (Phase 6 §A.8 lesson). Same backward-vs-forward distinction.
2. **Web:** an "account equity" form on the dashboard / config page (writing-plans Phase 10+ territory).

**V2 cadence (Schwab Phase A):** `swing journal reconcile-schwab` co-emits `account_equity_snapshots` row with `source='schwab_api'` for the period_end snapshot date. Source ladder ensures Schwab takes precedence over manual at read-time.

**Daily target; gaps allowed.** No automatic prompt. Operator catches gaps at end-of-week reconciliation (Phase 10 dashboard surface flags "no equity snapshot in last N days" — Phase 10 writing-plans).

**Idempotency:** SELECT-then-UPDATE-or-INSERT keyed on `(snapshot_date, source)`.

**Back-fill:** GAP-FLAGGED. Operator may back-record any past date manually; back-record threshold (`recorded_at - snapshot_date > N`) flags at read-time as "back-recorded" advisory; writing-plans codifies threshold.

---

## §5 Lifecycle integration with Phase 6 + Phase 7 + Phase 8 (LOCKED)

### §5.1 Phase 7 state-machine integration: query-side reopen, NOT state transition + NOT review_log flag

**Decision (LOCKED — R1 Major #4 redesign):** When a material reconciliation discrepancy is detected on a trade with `state='reviewed'`, Phase 9 does NOT introduce a new state, does NOT extend Phase 7's state machine, AND does NOT add reopen-flag columns to `review_log`. Phase 7 state stays at `reviewed`. The "reopen review" semantic is a QUERY-SIDE JOIN against `reconciliation_discrepancies`; the discrepancy row IS the source-of-truth for "this trade has audit-trail-pending material disagreement."

**Rationale:**

1. **Phase 7 state machine is operationally settled.** 11 operator-witnessed gate surfaces PASS post-hotfix (Phase 7 ship 2026-05-05); production DB has 4 trades at known states. Touching the state CHECK enum forces a Phase 7-style table-rebuild — backup gate, foreign_keys=OFF runner discipline, full constraint enumeration (Phase 7 R1 Major 1 lesson). Massive blast radius for a flag-shaped need.
2. **Reopen is a property of the discrepancy, not the trade or the review_log row.** The operator-actionable surface is: "show me discrepancies that are unresolved AND material AND attribute to a reviewed trade." That's a SELECT, not a flag.
3. **review_log is cadence-period-grain, NOT trade-grain (R1 Major #4 fix).** Phase 6 `review_log` rows track daily / weekly / monthly / quarterly / circuit_breaker cadence; one row covers MANY trades in its period. Setting a reopen flag on a weekly review_log row when ONE trade in the period has a discrepancy reopens the WHOLE period's review semantically, which doesn't match operator intent. There is also NO trade-to-review-log mapping in current Phase 6 schema (no `review_log_id` column on trades; no bridge table); inferring "the most recent review whose period overlaps trade close date" is a heuristic that breaks down when multiple cadences cover the same trade. Query-side JOIN by period-overlap remains correct AND has no ambiguity-amplifying flag to maintain.
4. **Frozen aggregates remain frozen.** `review_log.net_R_effective` etc. are an audit snapshot of "what was reviewed." Phase 9 does NOT touch them. New aggregates, if needed, are computed at the dashboard read layer from current trade+fill data; the dashboard distinguishes "frozen-at-time-of-review" vs "current" naturally without a schema-level un-freeze.

**Operational sequence when material discrepancy hits a `state='reviewed'` trade (LOCKED — single transaction):**

1. (Inside the §3.3.3 reconciliation_runs transaction.) Discrepancy is INSERTed with `material_to_review=1` + `trade_id=T`.
2. NO `review_log` UPDATE.
3. NO Phase 7 state column UPDATE.
4. (Transaction COMMITs at §3.3.3 step 6.)

That's it. Operator-actionable surface is the discrepancy resolution lifecycle (§4.2): operator dispositions the discrepancy via CLI / web, optionally adds an addendum to the trade via Phase 7's `trade_events.event_type='note'` mechanism. If the operator's review judgment changes after the discrepancy resolves, they may add a `mistake_tag` to the trade row (`swing trade review` already supports re-running review on a closed trade per Phase 6 design) — that path EXISTS independently of Phase 9.

**Predicate rewrite per call-site (Phase 7 R1 Major 1 lesson, applied):** Phase 9 introduces ONE new query predicate — "trade has unresolved material discrepancies on a reviewed trade" — but this predicate is built from EXISTING tables (no new `state` value, no new flag column):

```sql
-- Reviews containing trades with unresolved material discrepancies (Phase 10+ dashboard surface):
SELECT r.review_id, r.review_type, r.period_start, r.period_end,
       COUNT(d.discrepancy_id) AS pending_material_count
FROM review_log r
JOIN trades t ON
  -- trade close date overlaps review period (Phase 6 review_log periods are inclusive bounds)
  (SELECT MAX(f.fill_datetime) FROM fills f
   WHERE f.trade_id = t.id AND f.action IN ('exit','stop','trim'))
  BETWEEN (r.period_start || 'T00:00:00') AND (r.period_end || 'T23:59:59')
JOIN reconciliation_discrepancies d ON
  d.trade_id = t.id
  AND d.material_to_review = 1
  AND d.resolution = 'unresolved'
WHERE r.completed_date IS NOT NULL
  AND t.state = 'reviewed'
GROUP BY r.review_id;

-- Trades flagged for re-review attention (Phase 6 dashboard "needs re-attention" extension):
SELECT t.id, t.ticker, COUNT(d.discrepancy_id) AS pending_material_count
FROM trades t
JOIN reconciliation_discrepancies d ON
  d.trade_id = t.id
  AND d.material_to_review = 1
  AND d.resolution = 'unresolved'
WHERE t.state = 'reviewed'
GROUP BY t.id;
```

These predicates are DISTINCT from existing Phase 7 state predicates (closed-or-reviewed-aggregator: `state IN ('closed','reviewed')`; active-trade-filter: `state IN ('entered','managing','partial_exited')`; review-precondition: `state='closed'`; entry-uniqueness: `state IN ('entered','managing','partial_exited')`). Writing-plans MUST enumerate every Phase 9 query call site and specify per-purpose which predicate applies — see Phase 7 R1 Major 1 lesson on per-call-site predicate-rewrite discipline.

**Idempotency at discrepancy grain:** the `(run_id, trade_id, discrepancy_type, fill_id, ticker, field_name)` combination is what defines a "duplicate" — writing-plans codifies a uniqueness check at INSERT-time so a second reconciliation rerun for the same source artifact doesn't generate exponential discrepancy counts on the same trade. (This complements §3.2's `source_artifact_sha256` advisory at the run level.)

### §5.2 Phase 6 review_log integration: frozen aggregates NEVER unfreeze

**Decision (LOCKED):** review_log frozen aggregates (`net_R_effective`, `expectancy_R_effective`, `win_rate`, `avg_win_R`, `avg_loss_R`, `profit_factor`, `max_drawdown_R`) are frozen-at-completion-time per Phase 6 lock; Phase 9 does NOT introduce an unfreeze path.

**Rationale:**

- Frozen aggregates are an audit snapshot of WHAT WAS REVIEWED with the data available at completion-time. Reconciliation may correct underlying fills (data corrections); recomputing the aggregate would silently rewrite history of "what the operator reviewed." Audit integrity is the priority.
- If the operator's process is to re-review with corrected data, the workflow is: (a) the data correction lands as a separate journal edit (e.g., fill_price corrected via `swing trade fix-fill`); (b) the operator opens a NEW review_log row (or reuses the existing pending row in the new period) and the NEW frozen aggregates capture the corrected data. The OLD frozen aggregates remain as the audit of the PRIOR review.
- Phase 6 dashboard query for "needs review" trades + "review history" surfaces consume frozen aggregates AS-IS; Phase 9 does not change these consumers.

**Counter-considered:** versioned review_log rows (`is_superseded` + `superseded_by_review_id`). Rejected because:

1. Existing `review_log` unique-index `(review_type, period_start, period_end)` would need to become partial (`WHERE is_superseded=0`) — a schema rebuild on the `review_log` table.
2. The reopen flag pattern (§5.1) doesn't actually need versioning — the operator's intent is "look again," not "redo." If "redo" becomes a workflow, V2 can add the versioning surface.
3. Phase 6 's `n_trades_reviewed=1` review for VIR (production) would gain a "superseded" semantic that doesn't match operational reality. Maintain the simpler shape until V2 demand surfaces.

### §5.3 Phase 8 daily_management_records integration: discrepancy lives in Phase 9, NOT in Phase 8 schema

**Decision (LOCKED):** The "snapshot reconciliation flag" mentioned in Phase 8 §11.2 lives in Phase 9's `reconciliation_discrepancies` table as `discrepancy_type='snapshot_mismatch'` with FK `linked_daily_management_record_id`. **NO new column is added to Phase 8's `daily_management_records` schema.**

**Rationale:**

1. **Phase 8 schema is locked at v15→v16.** Touching it now requires re-opening Phase 8 brainstorm; the spec is set.
2. **Reconciliation is a Phase-9-grain concept.** Daily snapshots are the operator's runtime view; reconciliation against broker state is a separate audit pass; the locus of audit data SHOULD be in the audit table, not on the source-of-truth-for-runtime row.
3. **Read-time join is cheap.** Phase 10 dashboard query "show me snapshots flagged for reconciliation":
   ```
   SELECT d.*, rd.discrepancy_id, rd.run_id, rd.expected_value_json, rd.actual_value_json
   FROM daily_management_records d
   LEFT JOIN reconciliation_discrepancies rd
     ON rd.linked_daily_management_record_id = d.management_record_id
     AND rd.discrepancy_type = 'snapshot_mismatch'
     AND rd.resolution = 'unresolved'
   WHERE d.trade_id = ?
   ```
   At our cardinality (~5 trades × ~250 sessions/year × 1 snapshot/day = ~1250 snapshot rows / year; <100 reconciliation runs / year; <50 discrepancies / year of which a handful are snapshot_mismatch), the LEFT JOIN cost is negligible.

**Phase 8 daily_management_records is consumed read-only by Phase 9.** Phase 9 may FK-reference daily_management_records.management_record_id (already in §3.3 column list as `linked_daily_management_record_id`) but writes nothing back into Phase 8's columns.

---

## §6 TOS reconciliation depth bundle subsumption (LOCKED)

Per `docs/phase3e-todo.md` "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" — Phase 9 SUBSUMES this bundle. The three queued gaps map to `discrepancy_type` enum values; the existing one-shot `ReconciliationReport` flow REFACTORS to write `reconciliation_runs` + per-discrepancy rows (writing-plans implements; brainstorm locks the mapping).

### §6.1 Gap 1 — CLOSE-fill price-mismatch detection → `discrepancy_type='close_price_mismatch'`

**v1.2 §10.5 step 5 ("compute field deltas") materialization for the CLOSE branch.**

Today (`swing/journal/tos_import.py:208-244`): CLOSE-fill matched against any open trade for ticker; cumulative qty bound; **no price comparison.**

Phase 9 refactor: after a successful match, compare `f.price` (TOS) to the matching exit fill's `fills.price` (journal). If `abs(diff) > price_tolerance`, emit a discrepancy:

- **discrepancy_type:** `close_price_mismatch`
- **trade_id, fill_id:** populated (writing-plans wires the fill-id lookup via `fills.action != 'entry'` matching the match-batch position)
- **expected_value_json:** `{"price": <journal exit price>, "exit_date": <ISO date>}`
- **actual_value_json:** `{"price": <tos price>, "fill_date": <ISO date>}`
- **delta_text:** `"$N.NN price difference"` (display-aid)
- **material_to_review:** 1 (TRUE — close price drives realized R; review reopen warranted)

### §6.2 Gap 2 — Stop-order reconciliation against Account Order History → `discrepancy_type='stop_mismatch'`

Today (`swing/journal/tos_import.py:_SECTION_LABELS`): `Account Order History` parsed but never consumed.

Phase 9 refactor:

1. Add `stop_order_extractor` parsing the WORKING SELL TO CLOSE STP rows (TOS Order History section variable-column parser). Output: `list[(ticker, working_stop_price, order_id_or_none)]`.
2. For each open trade in journal: look up corresponding TOS working stop. Compare `trades.current_stop` to TOS stop within `price_tolerance`. Mismatch → emit:
   - **discrepancy_type:** `stop_mismatch`
   - **trade_id:** populated; **fill_id:** NULL (stop is on a separate working order, not a fill)
   - **expected_value_json:** `{"current_stop": <journal>}`
   - **actual_value_json:** `{"working_stop_price": <tos>, "order_id": <ref or null>}`
   - **material_to_review:** 1 (TRUE — operator may have miscoded stop OR forgot to update broker after stop-adjust event)
3. **Open trade with NO TOS working stop:** emit `stop_mismatch` with `actual_value_json={"working_stop_price": null}` — operator forgot to place the stop at broker. Material.
4. **TOS working stop with NO matching journal trade:** emit `stop_mismatch` with `expected_value_json={}` — orphaned broker order. Material.

### §6.3 Gap 3 — Position-level holdings reconciliation against Equities section → `discrepancy_type='position_qty_mismatch'`

Today: `Equities` section not parsed.

Phase 9 refactor:

1. Add `Equities` to `_SECTION_LABELS` + `equities_extractor`. Output: `dict[ticker, qty]`.
2. For each open trade: compare `trades.current_size` to TOS qty for that ticker. Mismatch → emit:
   - **discrepancy_type:** `position_qty_mismatch`
   - **trade_id:** populated; **ticker:** denorm
   - **expected_value_json:** `{"qty": <journal current_size>}`
   - **actual_value_json:** `{"qty": <tos qty>}`
   - **material_to_review:** 1 (TRUE — likely an unrecorded partial exit OR missed entry)
3. **TOS ticker with no journal open trade:** emit with `trade_id=NULL` + `ticker` populated — orphaned broker holding (could indicate the entry was never journaled). Material.
4. **Journal open trade with no TOS qty for ticker:** emit with `trade_id` populated + `actual_value_json={"qty": 0}` — broker shows zero, journal shows position. Material (possible silent close at broker).

### §6.4 Gap 4 — cash_movement_mismatch (NEW; not in original TOS bundle)

Existing `extract_cash_movements` (`swing/journal/tos_import.py:104-143`) detects deposit/withdraw rows by REF #; if REF# already exists (`find_by_ref`), the candidate is `duplicate_cash_movements`. Phase 9 refactor: in addition to dropping duplicates, COMPARE amount + kind to the existing journal record. If they disagree (e.g., journal has deposit $500 with ref X; TOS reports deposit $5000 with same ref — operator typo), emit:

- **discrepancy_type:** `cash_movement_mismatch`
- **cash_movement_id:** populated
- **expected_value_json:** `{"amount": <journal>, "kind": <journal kind>, "ref": <ref>}`
- **actual_value_json:** `{"amount": <tos>, "kind": <tos kind>, "ref": <ref>}`
- **material_to_review:** 0 (FALSE — cash flow doesn't bear on review of trade outcomes; surfaces as data-quality flag only)

Operator-actionable: review + correct the journal cash row OR mark `acknowledged_immaterial`.

### §6.5 Existing `swing/journal/tos_import.py:reconcile_tos` refactor scope (writing-plans territory)

The brainstorm-locked refactor shape is: `reconcile_tos(...)` returns the existing `ReconciliationReport` dataclass UNCHANGED + writes `reconciliation_runs` + child discrepancy rows as a side-effect within a single transaction. Caller code (CLI `swing journal import-tos`) sees the same dataclass; new behavior is durable persistence.

**Existing report-fields → discrepancy_type mapping (writing-plans codifies):**

| ReconciliationReport field | Maps to discrepancy_type |
|---|---|
| `matched_fills` | (NO discrepancy emitted; clean match — counted in `trades_reconciled_count` / `fills_reconciled_count` summary) |
| `unmatched_open_fills` | `unmatched_open_fill` |
| `unmatched_close_fills` | `unmatched_close_fill` |
| `price_mismatch_fills` (current — only OPEN-fills) | `entry_price_mismatch` |
| `already_reconciled_fills` | (NO discrepancy emitted; informational — `summary_json.already_reconciled_count`) |
| `new_cash_movements` | (NO discrepancy emitted; persisted to `cash_movements`) |
| `duplicate_cash_movements` (when amount+kind agree) | (NO discrepancy emitted; informational — `summary_json.duplicate_cash_movements_count`) |
| `duplicate_cash_movements` (when amount+kind DIFFER per §6.4) | `cash_movement_mismatch` |
| (NEW close-price compare per §6.1) | `close_price_mismatch` |
| (NEW stop reconciliation per §6.2) | `stop_mismatch` |
| (NEW equities qty compare per §6.3) | `position_qty_mismatch` |

**Sector tamper:** NOT detected at TOS reconciliation time (TOS exports don't carry the operator's form-submitted sector); detected at trade-entry POST in real-time. See §7.

**Snapshot mismatch:** NOT detected at TOS reconciliation time (TOS isn't a Phase 8 daily_snapshot source); detected at future Schwab API reconciliation OR manual cross-check workflow. V1 `snapshot_mismatch` is a reserved enum value with no V1 emitter; V2 Schwab Phase A wires it.

**Equity_delta:** detected at `account_equity_journal_dollars - account_equity_source_dollars` computation (§3.2). When non-zero beyond a threshold (writing-plans codifies threshold), emit `discrepancy_type='equity_delta'` with `material_to_review=0`.

---

## §7 Sector/industry tamper hardening scope (LOCKED)

**Decision (LOCKED):** BOTH schema-side and route-layer.

- **Schema-side (Phase 9 in scope):** `discrepancy_type='sector_tamper'` enum value already in §3.3. `expected_value_json` / `actual_value_json` shape per §3.3.1 (cached vs form-submitted sector + industry).
- **Route-layer (writing-plans territory):** mirrors `chart_pattern` hardening at `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`. At trade entry POST: lookup cached candidate row by `(ticker, action_session)`; reject if form-submitted sector or industry doesn't match. On rejection path: ALSO emit a `sector_tamper` discrepancy row inside an ad-hoc `reconciliation_runs` row (`source='system_audit'` per R1 Minor #2 distinction, `state='completed'`, period_start=period_end=action_session) for audit trail.

**material_to_review default for sector_tamper:** 0 (FALSE) in V1. **Elevate to 1 (TRUE) when** `risk_policy.max_sector_concentration_positions` becomes a HARD GATE (V2). The elevation requires:

1. New `risk_policy` row introducing the gating semantic (writing-plans for V2 introduces a `sector_concentration_gating_mode` enum field — currently advisory; elevation to 'hard_gate' triggers the `material_to_review=1` lookup).
2. Update `MATERIAL_BY_TYPE` lookup in the discrepancy emitter (code change, not schema change).

**Why "both" rather than schema-side-only or route-layer-only:**

- Schema-side-only: discrepancy logged but no rejection at entry; tamper succeeds. Wrong.
- Route-layer-only: rejection prevents tamper but no audit trail; operator can't review historical attempts. Wrong.
- Both: route-layer rejects in real-time AND emits an audit row for forensic review. Defense in depth. Same pattern as v1.2 §10.5 reconciliation step "create discrepancy records ... reopen reviewed trades if material."

**Operational sequence at trade entry POST (writing-plans territory; brainstorm locks the contract):**

1. Form POSTs trade entry with sector + industry hidden inputs (form-submitted values).
2. Route handler: lookup cached candidate by `(ticker, action_session_for_run(now))`.
3. If cached.sector == form.sector AND cached.industry == form.industry: proceed to entry_create.
4. If MISMATCH: 
   a. Reject the POST with HTMX-friendly error (mirror chart_pattern hardening response shape).
   b. Emit `sector_tamper` discrepancy in an ad-hoc reconciliation_run.
   c. Operator sees the rejection + can fix the form OR investigate the cache.

**Test pattern:** identical to chart_pattern hardening tests (`tests/web/test_trade_entry_chart_pattern_*`). Writing-plans clones the pattern with sector/industry payloads.

---

## §8 Schwab API Phase A coordination (LOCKED)

### §8.1 What Phase 9 ships V1

- `reconciliation_runs.source` enum value `'schwab_api'` reserved (CHECK constraint allows it; no V1 code emits it).
- `account_equity_snapshots.source` enum value `'schwab_api'` reserved.
- TOS-CSV path is the V1 LIVE reconciliation source. `swing journal reconcile-tos` (refactored) is operator's only V1 reconciliation entry.

### §8.2 What Phase 9 explicitly does NOT ship

- Any Schwab API library evaluation (Schwabdev / schwab-py / build-from-scratch).
- Any Schwab OAuth flow, refresh-token storage, or auth design.
- Any Schwab API integration namespace beyond reservation of the source enum value.
- Any `schwab_api`-specific column on `reconciliation_runs` or `account_equity_snapshots` (e.g., `schwab_account_id`, `schwab_api_request_id`). If V2 needs these, they ADD COLUMN at v17→vXX.

### §8.3 Schwab Phase A boundary contract (informational; writing-plans for Schwab Phase A consumes)

When Schwab Phase A brainstorm + writing-plans + executing-plans dispatch, the integration must:

1. NOT modify Phase 9 schema (no ALTER on `reconciliation_runs` / `reconciliation_discrepancies` / `account_equity_snapshots`).
2. Emit `reconciliation_runs` rows with `source='schwab_api'` + `source_artifact_path=NULL` + `source_artifact_sha256=NULL` (no CSV artifact).
3. Emit `account_equity_snapshots` rows with `source='schwab_api'` co-emitted within the reconcile-schwab transaction.
4. Reuse the `MATERIAL_BY_TYPE` lookup in the discrepancy emitter; no Schwab-specific overrides.
5. (Optional) Wire `snapshot_mismatch` discrepancy emission (Phase 9 reserved enum; no V1 emitter) by comparing Phase 8 daily_management_records against Schwab API position state.

### §8.4 Writing-plans + Phase 8 §11.2 cross-reference

Phase 8 §11.2 captures-needs-feedback line: "Phase 9 reconciliation_runs may flag snapshot rows whose underlying state diverges. NOT a Phase 8 concern; Phase 9 to scope." Phase 9 scopes: `discrepancy_type='snapshot_mismatch'` per §3.3.1 + §5.3. V1 emitter: NONE (TOS doesn't surface intraday position state). V2 Schwab Phase A: emitter wires snapshot_mismatch when broker position diverges from journal daily_management_record.

---

## §9 Migration strategy (LOCKED — Phase 7 + Phase 8 lesson inheritance)

### §9.1 Schema bump: v16 → v17

Phase 8 lands v15 → v16 in writing-plans-time. Phase 9 lands v16 → v17. Migration file: `swing/data/migrations/0016_phase9_risk_policy_and_reconciliation.sql` (numeric prefix matches version-bump-target convention; check writing-plans for actual numbering against shipped migrations).

### §9.2 Mechanic per table

| Table / change | Mechanic | Risk |
|---|---|---|
| CREATE TABLE `risk_policy` + 2 indexes | CREATE TABLE + CREATE INDEX | none |
| CREATE TABLE `reconciliation_runs` + 3 indexes | CREATE TABLE + CREATE INDEX | none |
| CREATE TABLE `reconciliation_discrepancies` + 4 indexes | CREATE TABLE + CREATE INDEX | none |
| CREATE TABLE `hypothesis_status_history` + 2 indexes | CREATE TABLE + CREATE INDEX | none |
| CREATE TABLE `account_equity_snapshots` + 2 indexes | CREATE TABLE + CREATE INDEX | none |
| ALTER `trades` ADD `risk_policy_id_at_lock` | `ALTER TABLE trades ADD COLUMN ...` (NULL allowed) | none — no rebuild |
| ALTER `review_log` ADD 1 column | 1× `ALTER TABLE review_log ADD COLUMN risk_policy_id_at_review_completion ...` (NULL) | none — no rebuild (R1 Major #4 + #5 fix — was 4 columns; reduced to 1) |
| INSERT seed `risk_policy` row 1 | `INSERT INTO risk_policy (...)` | none |
| INSERT seed `hypothesis_status_history` rows (one per existing hypothesis_registry row) | INSERT in idempotent form | none — uses existing `hypothesis_registry.created_at` |

**No table rebuilds.** All Phase 9 schema changes are CREATE TABLE / CREATE INDEX / ALTER ADD COLUMN. The Phase 7 lesson "Schema migration table-rebuilds must enumerate + preserve EXISTING CHECK + FK constraints" does NOT apply (no rebuild). Future column-tightening (e.g., ALTER `risk_policy_id_at_lock` to NOT NULL after backfill) WOULD trigger a rebuild and the lesson applies; brainstorm flags as writing-plans-phase verification gate.

### §9.3 Migration runner discipline (Phase 7 lessons binding)

- **`executescript()` partial-failure rollback wrapper:** Phase 7 hotfix `283d4fa` enabled the runner to ROLLBACK on mid-script failures. Phase 9 inherits via runner; no Phase-9-specific change.
- **`foreign_keys=OFF` discipline at runner level for table-rebuilds:** Phase 7 hotfix `283d4fa` disabled FK at runner level around `executescript`. Phase 9 has no rebuilds; the discipline still wraps the migration apply (defensive). No Phase-9-specific change.
- **Backup gate fires only on `current_version == 16 AND target >= 17`:** Phase 7 Sub-A code-review I1 lesson. Writing-plans codifies the gate condition. NEVER fires on fresh DBs (current=0 walks past) NOR mid-walk (current<16 walks through to 16 first).
- **Test fixture PRAGMA discipline:** every Phase 9 migration test fixture sets `PRAGMA foreign_keys=ON` to mirror production (Phase 7 hotfix `283d4fa` lesson). Writing-plans enumerates 5+ binding test fixtures.
- **NEW Phase 8 lesson — SQLite REPLACE prohibition:** Phase 9 UPSERT patterns MUST use SELECT-then-UPDATE-or-INSERT, NOT `INSERT OR REPLACE`. Applies to:
  - `account_equity_snapshots` per `(snapshot_date, source)` (§4.4).
  - `reconciliation_discrepancies` resolution UPDATE (§4.2).
  - `risk_policy` supersession 6-step sequence (§4.1).
  - `hypothesis_status_history` append (§3.4.1) — no UPSERT (pure append) but the closing UPDATE on `effective_to` is a UPDATE, not REPLACE; defensive lesson reminder.
  - `review_log` reopen-flag UPDATE (§5.1) — UPDATE on existing row.
- **Datetime-column impedance discipline (Phase 7 Sub-B R1 M1 lesson):** TEXT datetime columns (`effective_from` / `effective_to` on risk_policy + hypothesis_status_history; `started_ts` / `finished_ts` on reconciliation_runs; `created_at` / `resolved_at` on discrepancies; `recorded_at` on equity snapshots) require validator policy. Decision (LOCKED): **naive-only inputs**, validator rejects tz-aware datetimes. Mirrors Phase 7 Sub-B `_normalize_trade_event_date_to_iso` validator. Lexicographic ordering on text-stored datetimes is preserved when inputs are naive-only.
- **Per-row stamp of policy-versioned values (Phase 8 R1 M5 lesson):** §3.1.1 enumerates the stamps. Writing-plans verifies no risk_policy-versioned value is consumed without a corresponding per-row stamp.

### §9.4 In-flight production data

Production DB at HEAD `c954eef` (post-Phase-8-brainstorm) has:

- 4 trades (VIR / DHC / CC / YOU) — all pre-Phase-9; all stamp `risk_policy_id_at_lock=NULL`.
- 5 fills + 11 trade_events.
- 1+ review_log rows (VIR review). All pre-Phase-9; all stamp `risk_policy_id_at_review_completion=NULL`.
- 4 hypothesis_registry rows (seeded by migration 0008); none mutated. Phase 9 seeds one history row per hypothesis with `effective_from=hypothesis_registry.created_at`.

**Backwards-compatibility:** writing-plans verifies no Phase 9 read path treats `risk_policy_id_at_lock IS NULL` as an error condition. Default-resolution policy on legacy rows: resolve to current `risk_policy.is_active=1` row. Discriminating regression test (binding writing-plans deliverable): backfill no rows → query "policy effective at trade lock" returns the current policy for legacy trades.

### §9.5 Existing swing.config.toml seed transition

Per §3.1.3 LOCKED contract: post-Phase-9 ship, `risk_policy` is canonical source-of-truth; cfg is startup-mirror for the 1 currently-Phase-5-surfaced field that has a `risk_policy` corresponding column (`cfg.account.risk_equity_floor` ↔ `risk_policy.capital_floor_constant_dollars`); other risk_policy fields have no cfg counterpart. Writing-plans wires the cascade.

---

## §10 Open questions for orchestrator triage

### §10.1 reconciliation_run period_end resolution when source is account-state-only

**Question:** When Schwab API Phase A ships and `swing journal reconcile-schwab` does an account-state pull (not a CSV import covering a date range), what is `period_end`? Today's date? Last completed NYSE session? Operator-passed?

**Brainstorm recommendation:** `period_end=last_completed_session(now)` (same convention as Phase 6 §A.8 cadence pre-create lesson). Operator can override with `--period-end <ISO>`. NULL period_start for snapshot-mode runs.

**Defer:** Schwab Phase A brainstorm decides at writing-plans time.

### §10.2 sector_tamper hard-gate elevation trigger

**Question:** When does `risk_policy.max_sector_concentration_positions` become a HARD GATE rather than ADVISORY?

- **V1 (this Phase 9):** Advisory. `material_to_review=0` for sector_tamper.
- **V2:** Hard gate. `material_to_review=1` for sector_tamper.

**Trigger options:**

- **Operator-decision:** orchestrator surfaces when Phase 9 ships + operator confirms gate-mode at any time post-Phase-9.
- **Sample-size threshold:** automated elevation when n>=20 closed trades (per `risk_policy.global_confidence_floor_n`).
- **Phase 10 dashboard surface:** dashboard shows current gate-mode + has a toggle.

**Brainstorm recommendation:** Operator-decision. Operator + orchestrator decide at any time post-Phase-9. The elevation IS a `risk_policy` UPDATE (introducing `sector_concentration_gating_mode` enum field — currently NOT in the §3.1 column list; would be a new ALTER ADD COLUMN OR a future Phase migration). For Phase 9 scope, flag as future work; do NOT add the field to V1 schema. **Defer:** orchestrator triage at first orchestrator-context update post-Phase-9 ship.

### §10.3 reconciliation_runs vs reconciliation_discrepancies retention

**Question:** Long-horizon, do we retain ALL runs + discrepancies forever? Or roll up to summary after N years?

**Brainstorm recommendation:** Retain all forever. At our cardinality (<100 runs/year × <50 discrepancies/year ≈ <5000 rows over 10 years), storage is trivial. Audit-trail integrity > storage optimization.

**Defer:** revisit at year 5+ if cardinality changes.

### §10.4 hypothesis_status_history seed effective_from policy

**Question:** Should the seed migration use `hypothesis_registry.created_at` as `effective_from` (preserves chronology) or migration-apply-time (declares "Phase 9 is when audit started")?

**Brainstorm recommendation:** Use `hypothesis_registry.created_at`. Preserves chronology. Set `recorded_at` to migration-apply-time (the row WAS recorded at migration time, but its `effective_from` reflects the historical truth that the hypothesis became active when registered). The recorded_at vs effective_from divergence is meaningful and useful (signals back-recorded seed rows).

**Locked in §3.4.1.** Surfaced here for orchestrator review; if orchestrator prefers migration-apply-time, writing-plans changes the seed.

### §10.5 V1 CLI surface for risk_policy editing

**Question:** What CLI surface does writing-plans add for non-Phase-5-mirror risk_policy fields?

- Single CLI: `swing config policy update --field <name> --value <val>` (per-field UPDATE).
- Bulk CLI: `swing config policy save --json '{...}'` (full row replace).
- Read-only CLI for V1 (operator edits via DB direct SQL until V2): cheap escape hatch.

**Brainstorm recommendation:** Per-field CLI for V1 (matches operator's spot-edit workflow); bulk CLI deferred to V2. Out-of-V1: web form (deferred to Phase 10+ writing-plans for dashboard integration).

**Defer:** writing-plans decides at task-decomposition time.

### §10.6 Reconciliation_run period_end vs source artifact date alignment

**Question:** If operator imports a TOS CSV labeled `2026-04-30-AccountStatement.csv` but the CSV's last fill date is 2026-04-28, what is `period_end`?

- Source artifact filename date (2026-04-30)?
- Last fill date in the CSV (2026-04-28)?
- Operator-passed via CLI flag?

**Brainstorm recommendation:** Operator-passed via CLI flag (`--period-end <ISO>`); default to last fill date in the parsed CSV. Filename date is unreliable (operator could rename the file). Last-fill-date is data-derived and meaningful.

**Defer:** writing-plans codifies CLI default.

(R1 Major #4 fix — former §10.8 "Reopen-resolution UI surface" REMOVED. Reopen flag dropped from review_log; query-side JOIN over `reconciliation_discrepancies.resolution` IS the operator-actionable surface — see §5.1.)

---

## §11 Phase 10 hand-off (capture-needs feedback)

Phase 10 writing-plans dispatch follows Phase 9 execution. Phase 9 design choices that Phase 10 needs to know about:

### §11.1 Risk_Policy as the source for metric defaults at dashboard read-time

Phase 10 §6.2 capture-needs are SATISFIED by Phase 9 §3.1 risk_policy schema. Phase 10 dashboard READS LIVE policy (per `risk_policy.is_active=1` row), NOT seeded-at-trade-time, for:

- `low_sample_size_threshold_class_*_n` (suppression policy at dashboard render).
- `global_confidence_floor_n` (n=20 floor).
- `bootstrap_resample_count` (CI computation).
- `process_grade_weight_*` (weight reconstitution if stamp absent on legacy review_log rows).

Phase 10 dashboard reads at-trade-time policy (per `trades.risk_policy_id_at_lock`) for:

- `capital_floor_constant_dollars` (preserves historical-trade interpretation under capital-floor change).
- `scratch_epsilon_R` (preserves win/loss/scratch classification under threshold change).
- Trade-grain metrics that need policy-as-of-trade-time semantics.

**Locked decision per §3.1.1:** the per-row stamp on trades + review_log enables this at-trade-time vs live-time distinction.

### §11.2 Reconciliation discrepancy surface for metrics-data-quality reporting

Phase 9 ships `reconciliation_runs` + `reconciliation_discrepancies`. Phase 10+ writing-plans may add a "reconciliation status" badge on dashboard / journal review surfaces. **Phase 9 brainstorm scopes the schema to support this (LEFT JOIN as in §5.3); Phase 10+ writing-plans implements.**

Recommended Phase 10+ surfaces:

- Dashboard top: "N unresolved material discrepancies" badge (links to discrepancy list).
- Per-trade detail: "Trade X has unresolved reconciliation discrepancies" indicator + link to detail.
- Per-cohort metrics view: optional filter "exclude trades with unresolved discrepancies" for sample-purity.

### §11.3 Hypothesis status history surfaces

Phase 10 §3.2 surfaces "single most-recent transition only" in V1; full history requires Phase 9 audit table. Phase 10 writing-plans uses `hypothesis_status_history` to render:

- Per-hypothesis transition timeline (active → paused → active → closed-target-met).
- Cohort-level "active period" calculations (excludes paused intervals from rate-metric numerators if operator opts in).

Phase 9 schema is sufficient; Phase 10 writing-plans wires the queries.

### §11.4 account_equity_snapshots resolution at Phase 10 metric layer

Phase 10 §6.2 + §3.4 capital-friction metrics depend on `live_capital_denominator_dollars`. Phase 9 ships the table. Phase 10 metric layer resolves:

```
live_capital_denominator_dollars(asof_date) :=
  COALESCE(
    (SELECT equity_dollars FROM account_equity_snapshots
       WHERE snapshot_date <= asof_date
       ORDER BY snapshot_date DESC,
                CASE source WHEN 'schwab_api' THEN 1
                            WHEN 'tos_csv' THEN 2
                            WHEN 'manual' THEN 3 END ASC
       LIMIT 1),
    (SELECT capital_floor_constant_dollars FROM risk_policy WHERE is_active = 1)
  )
```

Source ladder enforces broker-authoritative > csv > manual when same date has multiple rows. Fallback to risk_policy capital floor when no snapshot exists at-or-before asof_date — Phase 10 §2 split-policy PROVISIONAL.

### §11.5 Phase 9 capture-needs already accommodated for Phase 10

Phase 10 §6.3 enumerated capture-needs beyond Phase 8/9 plans:

- **Per-pipeline-run capital-utilization aggregate:** Phase 10+ writing-plans territory; uses Phase 9's `account_equity_snapshots` for live denominator. NOT a Phase 9 column.
- **Benchmark series capture (Phase 10 §8.3 open question):** OUT of Phase 9 scope; orchestrator triages separately.
- **Corporate_Actions MVP (Phase 10 §8.4 open question):** OUT of Phase 9 scope; orchestrator triages separately.
- **Daily account equity capture (Phase 10 §8.2 open question):** SATISFIED by Phase 9 §3.5 `account_equity_snapshots` table.

---

## §12 Self-review checklist (pre-commit)

- **Placeholders:** No "TBD" / "TODO" markers in normative sections.
- **Internal consistency** (R1 Major #5 fix — review_log additions = 1 column verified; risk_policy column count = 28 verified; §3.7 capture-need cross-check = 15/15).
- **Scope check:** SCHEMA-LOCKING but no migration SQL; no code drafting; no task decomposition; no Schwab library / auth design.
- **Brief watch-item coverage:** all 18 brief §5 watch items addressed (key dispositions: §5.1 Phase 7 state untouched, query-side reopen via discrepancy JOIN; §3.1 risk_policy uses `is_active` + `superseded_by_policy_id` dual-column; §3.4.0 hypothesis_status_history justified as no-dual-col case; §9.3 SQLite REPLACE prohibition enumerated for 5 UPSERT sites; §3.1.1 per-row policy stamping locked; §3.7 15/15; §8 Schwab source-enum cleanly reserved; §6 TOS bundle 3 gaps + gap 4 mapped; §7 sector tamper BOTH; §3.3.2 material_to_review override semantics for non-trade-linked discrepancies; §9.3 backup gate fires only at `current_version==16 AND target>=17`; §9.3 PRAGMA + naive-only datetime validator; §11 operator-actionability + Phase 10 hand-off; §13 brief premises empirically verified against shipped migrations + tos_import.py + config.py).
- **R1 Codex round disposition** (8 majors + 5 minors):
  - Major #1 (hypothesis_status_history dual-column) — ACCEPTED with rationale at §3.4.0.
  - Major #2 (effective_from/to date vs datetime) — FIXED at §3.1 (locked ISO datetime).
  - Major #3 (Phase 8 stamp completeness) — FIXED at §3.1.1 (clarified Phase 8 self-stamps; V2 trigger documented).
  - Major #4 (review_log reopen keyed-to-trade) — FIXED at §5.1 (redesigned to query-side JOIN; review_log additions reduced 4→1).
  - Major #5 (review_log additions count drift) — FIXED (consistent 1-column count post-#4 redesign).
  - Major #6 (material_to_review for non-trade discrepancies) — FIXED at §3.3.2 (override semantics + non-trade rendering surfaces locked).
  - Major #7 (drawdown sign convention) — FIXED at §3.1 (CHECK < 0; aligned with Phase 10 §2 lock).
  - Major #8 (config source-of-truth direction) — FIXED at §3.1.3 (locked: `risk_policy` canonical post-Phase-9; cfg startup-mirror).
  - Minor #1 (line-count overage) — partial trim of §12 + open-question consolidation; final post-fix line count ~1100 lines (still slightly over 900 target — accepted as locked-content-density vs Phase 8's 875 lines proportional to Phase 9 having 5 new tables + Phase 6/7/8 integration vs Phase 8's 1 new table).
  - Minor #2 (source enum overload) — FIXED at §3.2 (added `system_audit` enum value).
  - Minor #3 (csv_import vs tos_csv vocabulary) — FIXED at §3.5 (harmonized to `tos_csv`).
  - Minor #4 (SQLite cross-column CHECK over-claim) — FIXED at §3.1 (correction documented; defense-in-depth CHECK noted as writing-plans verifiable).
  - Minor #5 ("corrected here" inline drift) — FIXED via §3.6 + §5.1 redesign (drift collapsed; canonical sections updated).

---

## §13 References

- Brief: `docs/phase9-risk-policy-reconciliation-brainstorm-brief.md` (HEAD `d89b74b`).
- Phase 10 metrics-design (binding §6.2 capture-needs): `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`.
- Phase 8 daily-management-design (binding §11 capture-needs + spec format reference): `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`.
- Phase 7 trade-state-machine + Fills (binding integration): `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`.
- Phase 7 migration shipped: `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`.
- Phase 6 post-trade review (review_log shipped): `swing/data/migrations/0013_phase6_post_trade_review.sql`; `swing/trades/review.py`.
- Hypothesis registry (Phase 1 shipped): `swing/data/migrations/0008_hypothesis_registry.sql`.
- Journal v1.2 source spec: `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` (§7.8 Risk_Policy + §7.9 Reconciliation_Log + §10.5 Reconciliation Workflow).
- Existing TOS reconciliation (refactor target): `swing/journal/tos_import.py`.
- Existing config (seed source): `swing/config.py` + `swing.config.toml`.
- Cross-phase backlog: `docs/phase3e-todo.md` (TOS bundle + Schwab API + sector tamper + journal v1.2 framing).
- Orchestrator-context (binding lessons): `docs/orchestrator-context.md` §"Lessons captured" (Phase 7 + Phase 8 lessons binding).
- CLAUDE.md gotchas (SQLite REPLACE; foreign_keys=OFF; lexicographic datetime ordering; HTMX failure surfaces; `... or None` for nullable enum CHECK columns).

---

*End of design spec. Adversarial Codex review pending.*
