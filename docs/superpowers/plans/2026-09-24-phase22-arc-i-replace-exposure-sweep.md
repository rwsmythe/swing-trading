# Phase 22 arc 22-I — the REPLACE-exposure sweep: implementation plan (migration 0041)

**Brief:** `docs/phase22-arc-i-f-sweeps-commissioning-brief.md` (text of record on main @ `732c5c21`, 22-I only). **Census:** `2026-09-24-phase22-arc-i-replace-exposure-sweep.census.md`. **Ledger (every argument, ruling and measurement this plan encodes):** `2026-09-24-phase22-arc-i-replace-exposure-sweep.ledger.md` (sections "Rulings received", "STEP 3", "STEP-3 RULINGS"). **Probe scripts:** `scripts/probe_22i_guard_census.py`, `scripts/probe_22i_plan_measurements.py`. This plan is a task ladder and a test roster; it carries no argument. Where a line says "(ruling X)", the ledger holds X verbatim.

**Executing cell:** `implementer-opus-high` (a schema migration; brief §0). **Review:** Reviewer A (`strong`) to convergence per the recipe; Reviewer B at the orchestrator's gate; CHARC merge gate (brief §5 witness sitting).

---

## 0. Invariants every task holds

1. `0041` is `CREATE TRIGGER` only, plus exactly ONE `DROP TRIGGER` + `CREATE TRIGGER` (`trg_provenance_corrections_append_only_update`). No table, index, view, column, or row is created, altered, rebuilt or written, apart from `schema_version` 40 → 41.
2. Every `WHEN` clause `0041` writes is wrapped in `COALESCE(<predicate>, 0)`: `WHEN NOT COALESCE(<admitted>, 0)` for update twins, and `WHEN COALESCE(EXISTS (...), 0)` for conflict barriers. A barrier with no `WHEN` (the plain `no_delete`, the blanket `no_update`, the `UPDATE OF` twin) has no NULL hazard.
3. Every PK clause in a `no_replace` reads `(NEW.<pk> != -1 AND <pk> = NEW.<pk>)` (the 0037 idiom). `candidate_criteria` has a composite PK and gets no `-1` clause. No `CHECK (pk > 0)` is added, because no table is new (AL-1).
4. Every update comparison is `IS` / `IS NOT` (never `=`); every parent-existence test is `NOT EXISTS` (never NULL).
5. No barrier is narrowed to admit a writer. A writer a barrier would abort is adjusted under F-I3 (ruled), or its row returns to the ruler. Ruled writer changes in 22-I: ONE F-I3 adjustment (`review_log.insert_pre_create`) and ONE service-twin refusal (`complete_review_atomic`, the CLI boundary). There are no others; brief §2.6 was amended by CHARC @ `a83df9d3` (ledger "STEP-3 RULINGS").
6. `EXPECTED_SCHEMA_VERSION = 41`; one gate row `BackupGateSpec(40, "22i", PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES, "_phase22_arc_i_backup_gate", "pre-22-I")`.
7. D51: every commit that touches `0041` runs `python scripts/schema_manifest.py --write` and commits `tests/data/schema_manifest_head.tsv` in the same commit. The final diff reads: ADDED = the 59 triggers in §1.4, CHANGED = the header + `trg_provenance_corrections_append_only_update`, DELETED = 0.
8. The live DB is never opened writable. Probes run on a backup-API copy; nothing reaches `ensure_schema` except a migration run on a copy.

## 1. The guard set (what `0041` creates)

### 1.1 Column-class vocabulary (used by the spec module and every twin)

| Class | Meaning | Predicate term inside `WHEN NOT COALESCE(... , 0)` |
|---|---|---|
| **I** immutable | never changes after INSERT | `NEW.c IS OLD.c` |
| **W** write-once | NULL → value admitted; value → anything refused | `(NEW.c IS OLD.c OR OLD.c IS NULL)` |
| **F** a17 FK | ON DELETE SET NULL FK: value → NULL admitted only with the parent gone | `(NEW.c IS OLD.c OR (OLD.c IS NOT NULL AND NEW.c IS NULL AND NOT EXISTS (SELECT 1 FROM <parent> WHERE <ppk> = OLD.c)))` |
| **D** directional | `risk_policy.is_active` 1 → 0 only | `(NEW.is_active IS OLD.is_active OR (OLD.is_active = 1 AND NEW.is_active = 0))` |
| **M** mutable | in the writer's measured UPDATE set | absent from the predicate |
| **S** state-frozen | mutable while a row-state holds, frozen after (dmr, review_log) | per-table clause, §1.3 |

Every F column is listed in §1.5 in one of three states (CHARC @ `732c5c21`): **REACHABLE** (a production parent delete exists), **DELETABLE-NO-PRODUCTION-DELETER** (the parent is unguarded but nothing in `swing/`/`scripts/`/`research/` deletes it), or **DEAD-BY-PARENT-GUARD** (the parent table itself gets `no_delete` in `0041` or earlier). The exemption is uniform across all three (CHARC a17 uniformity, @ `7e0463ed`).

### 1.2 The (a) triples — seven tables, 21 triggers

Abbreviations are used in trigger names: `trg_<abbr>_no_update`, `trg_<abbr>_no_delete`, `trg_<abbr>_no_replace`.

| Table (abbr) | PK | `no_replace` conflict clause (besides the PK clause) | `no_update` shape |
|---|---|---|---|
| `pattern_forward_observations` (`pfo`) | `observation_id` | `detection_id = NEW.detection_id AND observation_date = NEW.observation_date` | blanket (no `WHEN`) |
| `pattern_detection_events` (`pde`) | `detection_id` | `source = NEW.source AND ticker = NEW.ticker AND detection_date = NEW.detection_date AND pattern_class = NEW.pattern_class` | **a17 twin-shaped** (below) |
| `candidate_criteria` (`cc`) | composite `(candidate_id, criterion_name)` | the PK equality only (no `-1` clause) | blanket |
| `trade_events` (`te`) | `id` | none | blanket |
| `finviz_api_calls` (`fac`) | `call_id` | none | blanket |
| `pattern_evaluations` (`pev`) | `id` | `pipeline_run_id = NEW.pipeline_run_id AND ticker = NEW.ticker AND pattern_class = NEW.pattern_class` | blanket |
| `evaluation_runs` (`er`) | `id` | none | blanket |

`trg_pde_no_update`: `BEFORE UPDATE ... WHEN NOT COALESCE(<F chart_render_id→chart_renders.id> AND <F pipeline_run_id→pipeline_runs.id> AND (NEW.chart_render_id IS NOT OLD.chart_render_id OR NEW.pipeline_run_id IS NOT OLD.pipeline_run_id) AND <I: the other 12 columns>, 0)`. The third conjunct makes a no-op UPDATE abort (the v40 `trg_eia_no_update` shape).

### 1.3 The (c) tables — thirteen tables, 37 triggers

Each twin-bearing table gets `trg_<abbr>_no_delete` + `trg_<abbr>_no_replace` + `trg_<abbr>_immutable`. `pattern_exemplars` and `watchlist_archive` get the first two only. Column sets are by EXCLUSION of the writer's measured UPDATE set (RD binding (i); ledger STEP 3). A column list here is the spec; the comparator test (§4.2 C8) asserts it against `PRAGMA table_info`.

**`reconciliation_corrections` (`rc`)**, 20 columns. Conflict clause: PK only.
- W: `correction_set_id` (S3-F1), `superseded_by_correction_id` (S3-F1 amended: write-once, **no** SET-NULL exemption).
- F: `risk_policy_id_at_correction` → `risk_policy.policy_id`; `schwab_api_call_id` → `schwab_api_calls.call_id`.
- I (16): `correction_id, discrepancy_id, correction_action, correction_choice, affected_table, affected_row_id, field_name, pre_correction_value_json, source_canonical_value_json, applied_value_json, operator_truth_value_json, applied_at, applied_by, reconciliation_run_id, correction_reason, notes`.
- M: none.

**`risk_policy` (`rp`)**, 34 columns. Conflict clause: `(NEW.is_active = 1 AND is_active = 1)` (the partial `ux_risk_policy_active`).
- D: `is_active`.
- W: `effective_to`, `superseded_by_policy_id`.
- I: the other 31 (every policy-value column + `policy_id, effective_from, created_at, policy_notes`).
- M: none.

**`hypothesis_registry` (`hr`)**, 13 columns. Conflict clause: `name = NEW.name`.
- M: `status, status_changed_at, status_change_reason` (`trades/hypothesis.py:269-273`).
- I: the other 10. This is defined by exclusion, so `preregistered_decision_criteria` (0034) is covered without being named.

**`hypothesis_status_history` (`hsh`)**, 7 columns. Conflict clause: `(NEW.effective_to IS NULL AND effective_to IS NULL AND hypothesis_id = NEW.hypothesis_id)` (the partial `ux_hypothesis_status_history_current`).
- W: `effective_to`.
- I: the other 6.

**`reconciliation_runs` (`rr`)**, 20 columns. Conflict clause: PK only.
- M (12): `state, finished_ts, account_equity_journal_dollars, account_equity_source_dollars, equity_delta_dollars, trades_reconciled_count, fills_reconciled_count, discrepancies_count, unresolved_discrepancies_count, summary_json, notes, error_message`.
- F: `schwab_api_call_id` → `schwab_api_calls.call_id`.
- I (7): `run_id, source, source_artifact_path, source_artifact_sha256, period_start, period_end, started_ts`.

**`reconciliation_discrepancies` (`rd`)**, 20 columns. Conflict clause: PK only.
- M (7): `resolution, resolution_reason, resolved_at, resolved_by, ambiguity_kind, mistake_tag_assigned, material_to_review`.
- F (4): `trade_id` → `trades.id`; `fill_id` → `fills.fill_id`; `cash_movement_id` → `cash_movements.id`; `linked_daily_management_record_id` → `daily_management_records.management_record_id`.
- I (9): `discrepancy_id, run_id, discrepancy_type, ticker, field_name, expected_value_json, actual_value_json, delta_text, created_at`.

**`schwab_api_calls` (`sac`)**, 15 columns. Conflict clause: PK only.
- M (9): `http_status, response_time_ms, rate_limit_remaining, signature_hash, status, error_message, linked_snapshot_id, linked_reconciliation_run_id, linked_correction_id`.
- F: `pipeline_run_id` → `pipeline_runs.id`.
- I (5): `call_id, ts, endpoint, surface, environment`.

**`yfinance_calls` (`yfc`)**, 11 columns. Conflict clause: PK only.
- M (4): `response_time_ms, status, rows_returned, error_message`.
- F: `pipeline_run_id`.
- I (6): `call_id, ts, call_type, ticker, ticker_count, surface`.

**`account_equity_snapshots` (`aes`)**, 10 columns. Conflict clause: `snapshot_date = NEW.snapshot_date AND source = NEW.source AND basis = NEW.basis`.
- M (6): `equity_dollars, source_artifact_path, recorded_at, recorded_by, notes, schwab_account_hash`.
- I (4): `snapshot_id, snapshot_date, source, basis`.

**`daily_management_records` (`dmr`)**, 42 columns. Conflict clause: `(record_type = 'daily_snapshot' AND NEW.record_type = 'daily_snapshot' AND trade_id = NEW.trade_id AND data_asof_session = NEW.data_asof_session AND ((is_superseded = 0 AND NEW.is_superseded = 0) OR mfe_mae_precision_level = NEW.mfe_mae_precision_level))`. This mirrors the two partial UNIQUE indexes.
- **DATA** (18, the reflow SET list `daily_management.py:621-640`): `current_price, current_stop, current_size, current_avg_cost, open_R_effective, open_MFE_R_to_date, open_MAE_R_to_date, intraday_high, intraday_low, position_capital_utilization_pct, position_capital_denominator_dollars, position_portfolio_heat_contribution_dollars, maturity_stage, trail_MA_candidate_price, trail_MA_period_days, trail_MA_eligibility_flag, pipeline_run_id, created_at`.
- I (21, always): `management_record_id, trade_id, record_type, review_date, data_asof_session, mfe_mae_precision_level, thesis_status, prior_stop, new_stop, stop_changed, stop_change_reason, volume_behavior, relative_strength_status, market_regime_change, sector_condition_change, news_or_event_update, action_taken, action_reason, emotional_state, rule_violation_suspected, management_notes`.
- F (always): `linked_trade_event_id` → `trade_events.id`.
- State columns: `is_superseded`, `superseded_by_record_id` (value → NULL refused on every row; S3-F2 and RD's (ii); no SET-NULL exemption on the self-FK).
- Admitted iff `<I all> AND <F linked_trade_event_id> AND (ACTIVE OR WINDOW OR FROZEN_FK)`, where:
  - **ACTIVE** = `OLD.is_superseded = 0 AND OLD.superseded_by_record_id IS NULL AND NEW.superseded_by_record_id IS NULL AND NEW.is_superseded IN (0, 1)`. DATA is free (reflow `:621`; step 3 `:822`).
  - **WINDOW** = `OLD.is_superseded = 1 AND OLD.superseded_by_record_id IS NULL AND NEW.superseded_by_record_id IS NOT NULL AND NEW.is_superseded = 1 AND <DATA all IS OLD>` (step 5 `:875`; S3-F2).
  - **FROZEN_FK** = `OLD.is_superseded = 1 AND NEW.is_superseded = 1 AND NEW.superseded_by_record_id IS OLD.superseded_by_record_id AND <DATA minus pipeline_run_id, IS OLD> AND <F pipeline_run_id>` (only the FK-driven nulling on a superseded row).
- The whole disjunction sits inside the one `COALESCE`.

**`review_log` (`rl`)**, 24 columns. Conflict clause: `review_type = NEW.review_type AND period_start = NEW.period_start AND period_end = NEW.period_end`.
- I (7, always): `review_id, review_type, period_start, period_end, scheduled_date, skipped, created_at`.
- S (16, frozen once `OLD.completed_date IS NOT NULL`): `completed_date, duration_minutes, n_trades_reviewed, primary_lesson, next_period_focus, total_mistake_cost_R, total_lucky_violation_R, net_R_effective, expectancy_R_effective, win_rate, avg_win_R, avg_loss_R, profit_factor, max_drawdown_R, auto_populated_field_keys_json`, plus `risk_policy_id_at_review_completion`, which is F-shaped while frozen.
- M (always): `superseded_by_correction_id` (`reconciliation_auto_correct.py:2404` overwrites it unconditionally).
- Admitted iff `<I all> AND (OLD.completed_date IS NULL OR (<S minus rp, IS OLD> AND <F risk_policy_id_at_review_completion → risk_policy.policy_id>))` (S3-F3 (A)).

**`pattern_exemplars` (`pex`)**: `no_delete` + `no_replace` (PK only). No twin; labels are edited in place (ruled).

**`watchlist_archive` (`wla`)**: `no_delete` + `no_replace` (PK only). No twin (ruled).

### 1.4 F-I5 + F-I2 + the ADDED/CHANGED manifest

- **F-I5** (CHARC shape, binding): `trg_lve_first_view_immutable BEFORE UPDATE OF candidate_id, evaluation_run_id, detection_date, surface, view_session_date, latch_state_at_first_view, actionable_at_first_view ON latch_view_events FOR EACH ROW BEGIN SELECT RAISE(ABORT, ...); END`. No `WHEN`. Its comment quotes `0032:31`, `0033:62` and 22-B R0.K.
- **F-I2** (CHARC, binding): `DROP TRIGGER trg_provenance_corrections_append_only_update;` then `CREATE` it again with text = the stored v40 `sqlite_master.sql` with exactly two substitutions: `FOR EACH ROW WHEN NOT (` → `FOR EACH ROW WHEN NOT COALESCE((`, and the closing `\n)\nBEGIN` → `\n), 0)\nBEGIN`. The measured result is 4,140 → 4,153 chars, and the inverse transform is byte-identical (ledger S3-4). The migration text is written out literally, never generated at run time.
- **ADDED (59):** `trg_{pfo,pde,cc,te,fac,pev,er}_{no_update,no_delete,no_replace}` (21) · `trg_{rc,rp,hr,hsh,rr,rd,sac,yfc,aes,dmr,rl}_{no_delete,no_replace,immutable}` (33) · `trg_{pex,wla}_{no_delete,no_replace}` (4) · `trg_lve_first_view_immutable` (1).
- **CHANGED:** the `schema_version` header row + `trg_provenance_corrections_append_only_update`.
- **DELETED:** 0.

### 1.5 The a17 sites — three states (CHARC @ `7e0463ed`, corrected @ `732c5c21`)

The method is a grep of `DELETE FROM <parent>` over `swing/ scripts/ research/`, every hit read (ledger STEP 3; re-run at round 3). Two parents are REACHABLE, not one: `chart_renders` and `fills` (`split_into_partials`); the brief's "the only one" is corrected in the ledger.

| Child.column | Parent | Class | Production delete evidence |
|---|---|---|---|
| `pde.chart_render_id` | `chart_renders` | **REACHABLE** | `diagnostics/prune_chart_cache.py:36`, `repos/chart_renders.py:223/:234/:241` |
| `pde.pipeline_run_id` | `pipeline_runs` | **DELETABLE-NO-PRODUCTION-DELETER** | none (`DELETE FROM pipeline_runs`: zero hits) |
| `sac.pipeline_run_id`, `yfc.pipeline_run_id`, `dmr` FROZEN_FK `pipeline_run_id` | `pipeline_runs` | **DELETABLE-NO-PRODUCTION-DELETER** | none |
| `rd.fill_id` | `fills` | **REACHABLE** | `reconciliation_auto_correct.py:3226` (`split_into_partials`) |
| `rd.trade_id` | `trades` | **DELETABLE-NO-PRODUCTION-DELETER** | none (`DELETE FROM trades`: zero hits) |
| `rd.cash_movement_id` | `cash_movements` | **DELETABLE-NO-PRODUCTION-DELETER** | none (`DELETE FROM cash_movements`: zero hits) |
| `rd.linked_daily_management_record_id` | `daily_management_records` | **DEAD-BY-PARENT-GUARD** (`trg_dmr_no_delete`) | — |
| `rr.schwab_api_call_id`, `rc.schwab_api_call_id` | `schwab_api_calls` | **DEAD-BY-PARENT-GUARD** (`trg_sac_no_delete`) | — |
| `rc.risk_policy_id_at_correction`, `rl.risk_policy_id_at_review_completion` | `risk_policy` | **DEAD-BY-PARENT-GUARD** (`trg_rp_no_delete`) | — |
| `dmr.linked_trade_event_id` | `trade_events` | **DEAD-BY-PARENT-GUARD** (`trg_te_no_delete`) | — |

The self-FKs `rc.superseded_by_correction_id` and `dmr.superseded_by_record_id` carry **no** exemption (RD S3-F1 amendment; S3-F2 (ii)).

## 2. File map

| File | Change |
|---|---|
| `swing/data/migrations/0041_replace_exposure_sweep.sql` | NEW. Header (§3 T1) + §1 triggers + the F-I2 rebuild |
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION = 41`; `PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES` (= the v40 table set; copy the 22-B constant's shape at `:439`); the one `BackupGateSpec` row after `:767`. The gate creator is the parameterised one (no `creator_alias`) |
| `swing/data/repos/review_log.py` | `insert_pre_create`: the `WHERE NOT EXISTS` pre-filter (F-I3, S3-F4 (i)); `complete_review_atomic`: the SELECT-first completed-row refusal (S3-F3 (A)) + a new `ReviewAlreadyCompletedError(ValueError)` in this module |
| `swing/cli.py` | `review complete` (`:2196`): wrap `ReviewAlreadyCompletedError` → `click.ClickException("Review already completed")` |
| `swing/trades/cohort_provenance_correction.py` | `:3168-3174` docstring ONLY (COMMENT-ONLY; CHARC pre-authorized, zero behaviour): cite the triggers, not the grep |
| `tests/data/schema_manifest_head.tsv` | regenerated per migration commit |
| `tests/data/_22i_guard_spec.py` | NEW. The declarative spec: per table its class, PK, conflict clause columns, and the I/W/F/D/M/S/DATA sets of §1 (the ONE source the tests read) |
| `tests/data/_22i_seed.py` | NEW. Raw-SQL seed helpers: one minimal valid row per guarded table plus its parents, on a DB migrated to 40 or 41 |
| `tests/_22i_guard_seam.py` | NEW. `guards_dropped(conn, *names)` context manager: drop the named triggers on a TEST DB and re-create them from their stored `sqlite_master.sql` on exit; a name absent from the DB is skipped (so one test runs at 40 and 41). Two uses only: tests that plant historical corruption to test DETECTION, and a17 clause pins whose parent delete `0041` refuses (AL-10) |
| `tests/data/test_migration_0041_*.py` | NEW, the roster in §4 |
| the 28 tests asserting `EXPECTED_SCHEMA_VERSION == 40` | body → 41 (no rename in this commit; CLAUDE.md naming rule) |
| tests that raw-write a newly guarded table | re-planted (T16) |
| `scripts/probe_22i_guard_census.py` | `--post-migrate` mode, built in T18 step 1: section `G-0041` + the corrected expectations |

No new `swing/` module. No new dependency. No change to any other writer.

## 3. Task ladder (TDD; one red → green → commit per task; each migration commit regenerates the manifest)

Conventions for every task:
- "RED on v40" means the discriminator's ABORT assertion fails on a DB migrated with `run_migrations(c, target_version=40, ...)`.
- "GREEN" means it passes at 41. Both are kept in the suite as a `(version, verdict)` parametrization (§4.0), so v40 exposure and v41 protection are each pinned permanently.
- Seeding uses `tests/data/_22i_seed.py`.
- Run the task's tests plus the named writer test modules; the full suite runs at T18.

**T0 — worktree.** `git worktree add -b 22-i-exec .worktrees/22-i-exec <plan-commit>`. Record the base SHA in the exec ledger.

**T1 — version, gate, empty 0041, spec module.**
- Tests first: `test_expected_schema_version_is_head` bodies → 41 (28 files, bodies only); `test_backup_gate_table` gains the 40/"22i" row assertion; the gate fires at `pre_version == 40 AND target_version >= 41` and not at 39 → 41 beyond its own row (the D50 predicate is untouched).
- `test_0041_header_declarations`: the header carries (i) the D60 sentence verbatim, "pre-existing rows replay unchanged: a trigger does not touch stored rows"; (ii) a DROP line for every created trigger (the 0040 reversibility shape) plus the restoring text reference for the rebuilt one (`0039_provenance_corrections_tier2.sql:704`); (iii) the gate row; (iv) "adds triggers only, rebuilds nothing".
- Implement: `0041` with header + `UPDATE schema_version` per the runner's convention (read 0040's last lines and mirror them); db.py changes.
- Manifest `--write`. Commit.

**T2 — F-I2: rebuild `trg_provenance_corrections_append_only_update`.**
- Tests first, `test_migration_0041_pc_update.py`:
  - `test_rebuilt_text_is_the_v40_text_plus_the_wrap`: at 41, stored sql == transform(stored sql at 40), and the inverse transform == the v40 text.
  - `test_fk_null_branch_plus_column_null_fires[col]`: over the 30 `=`-compared columns, parametrized (40 → `NOT NULL`-refused, trigger SILENT; 41 → the trigger fires by its RAISE text).
  - `test_risk_policy_branch_plus_null_fires` (same pair).
  - Both risk-policy tests delete the `risk_policy` parent (FK OFF) inside `with guards_dropped(conn, "trg_rp_no_delete")`: from T10 on, `0041` refuses that delete, so without the seam the setup aborts before the `pc` trigger is reached. The delete is labelled "clause pin, parent delete refused in production" (AL-9); at 40 the name is absent and the seam skips it.
  - `test_split_into_partials_fill_delete_admitted` (41; FKs on; `entry_fill_id` → NULL).
  - `test_risk_policy_delete_null_admitted` (41).
  - `test_plain_update_still_fires[col]` (41).
- `tests/_22i_guard_seam.py` is created in this task (its first user).
- Seeds are a fully-cited `provenance_corrections` row via the existing 22-A2/22-B fixture helpers (`tests/_22b_fixtures.py` or the 0039 test module's world builder — reuse, do not re-author).
- Implement the DROP + CREATE in `0041` §F-I2. Manifest. Commit.

**T3 — the six blanket (a) triples** (`pfo, cc, te, fac, pev, er`).
- Tests first: `test_migration_0041_triples.py` parametrized over the spec's (a) rows with §4.1's A1-A8.
- Implement. Run the writer modules: `tests/data/test_pattern_forward_observations*.py`, `tests/data/test_pattern_evaluations*.py`, `tests/data/test_candidates*.py`, `tests/**/test_*trade_events*`/`test_state*.py`, `tests/**/test_finviz_api_calls*.py`, `tests/pipeline/` (the nightly writers). Fix fixture fallout per T16's rule inside this task.
- Manifest. Commit.

**T4 — `pde` triple with the a17 `no_update`.**
- Tests first: §4.1 A1-A6 + §4.3 P1-P6 (P1 = the production chart prune via `swing.diagnostics.prune_chart_cache.prune_chart_renders_older_than` on a seeded pde → admitted, `chart_render_id` NULL; P1b = `refresh_chart_render` DELETE path admitted).
- Implement. Manifest. Commit.

**T5 — F-I5 `trg_lve_first_view_immutable`.**
- Tests first: `test_first_view_column_update[col]` over the seven columns (40 admitted / 41 aborts); `test_record_view_merge_unchanged` (the existing `record_view` tests green, plus one merge call at 41 asserting the five writer columns move and the seven do not); `test_lve_column_closure` (the seven + the five writer columns + `view_event_id, pipeline_run_id, first_viewed_ts, ticker` == `PRAGMA table_info`, disjoint).
- Implement. Manifest. Commit.

**T6 — `rr` + `rd`.**
- Tests first: §4.2 C1-C8 for both tables. The a17 set for `rd` covers all four F columns, including P3-class "FK → NULL with parent present aborts" on each; the REACHABLE production control is `_handle_split_into_partials`'s fill `DELETE` (`reconciliation_auto_correct.py:3226`) admitted on a seeded discrepancy carrying the fill.
- Writer suites: `tests/data/test_reconciliation*.py`, `tests/trades/test_reconciliation*.py`, `tests/trades/test_reconciliation_auto_correct*.py` — all green.
- Manifest. Commit.

**T7 — `rc`.**
- Tests first: §4.2 with the W pair for `correction_set_id` (NULL → self admitted — the literal `:3251` statement; value → other aborts; value → NULL aborts) and for `superseded_by_correction_id` (NULL → value admitted — `repo:208` and `entry_date_correction.py:1543`; value → NULL aborts; value → other aborts); F pair on the two DEAD-BY-PARENT-GUARD FKs (P3 parent-present abort; the parent-gone admit is shown with FK OFF + parent deleted with its `no_delete` dropped via the seam, labelled as the clause's own pin, never as a production path).
- End-to-end: `_handle_split_into_partials` on a seeded world completes at 41 (anchor + N rows; `correction_set_id` set).
- Manifest. Commit.

**T8 — `sac` + `yfc`.**
- Tests first: §4.2. The production writers `schwab_api_calls.insert_in_flight`/`update_call_outcome`/`update_call_linked_{snapshot,reconciliation_run,correction}`/`reconciliation_auto_correct.py:2370`, and `yfinance_calls.insert_in_flight`/`update_call_outcome`, all green at 41.
- `scripts/fix_phase2_misleading_audit_rows.py`'s statement (status, error_message) is admitted at 41 (one test running its literal SQL).
- Manifest. Commit.

**T9 — `aes`.**
- Tests first: §4.2, plus the upsert writer (`account_equity_snapshots.py:77/:121`) and `audit_service.py:339` green at 41.
- `test_corrector_snapshot_branch_unreachable` pins the service-prevention AL-7 rests on. It is table-driven over `_resolve_affected_target`'s THREE returning branches (fill_id → `fills`, cash_movement_id → `cash_movements`, trade_id → `trades`) plus the FOURTH case: an `equity_delta`/`snapshot_mismatch`-typed discrepancy carrying none of those FKs raises `ValueError` and issues no UPDATE (a `sqlite3` trace callback records none). The function's docstring (`:2188-2193`) names a snapshot branch that its code (`:2194-2205`) does not implement, so the `SET {field_name}` snapshot branch (`:2325-2328`) has no caller path.
- Manifest. Commit.

**T10 — `rp`, `hr`, `hsh`.**
- Tests first: §4.2 with the D pair on `rp.is_active` (1 → 0 admitted; 0 → 1 aborts), and the W pairs.
- `supersede_active_policy` end-to-end at 41 (predecessor flag twice, successor insert passes the partial-unique `no_replace`).
- `ratify_seed_from_cfg_on_v17_landing` on a fresh 0 → 41 migrate (the post-migrate path runs AFTER 0041's triggers exist).
- `update_hypothesis_status_with_audit` (`trades/hypothesis.py:145`) end-to-end at 41.
- The four risk-policy emitters' no-op tests green.
- Manifest. Commit.

**T11 — `dmr`.**
- Tests first: §4.2 over the ACTIVE/WINDOW/FROZEN_FK clauses:
  - ACTIVE reflow (`upsert_snapshot` twice on one session) admitted.
  - `tier_upgrade_snapshot` end-to-end admitted (steps 3 → 4 → 5).
  - The three S3-F2 discriminators: WINDOW step 5 admitted; a DATA column on a superseded row aborts; the step-5 shape + a DATA column aborts.
  - `is_superseded` 1 → 0 aborts.
  - `superseded_by_record_id` value → NULL aborts and value → other aborts.
  - Each I column aborts on an ACTIVE row.
  - FROZEN_FK: a probe `pipeline_runs` delete (a run with no `pattern_evaluations`; C4a) nulls `pipeline_run_id` on a superseded row, admitted; the parent-present P3 aborts.
  - `no_replace` on both partial keys (active-per-session; precision-per-session) aborts at 41, while an INSERT at a different precision on a superseded session passes (the tier-upgrade successor).
- Writer suite `tests/data/test_daily_management*.py` + `tests/pipeline/*daily_management*` green.
- Manifest. Commit.

**T12 — `review_log`: the service twin FIRST, then the F-I3 writer, then the triggers.** Three commits, in this order (authorize-then-abort: a trigger never ships ahead of its service check):
- **T12a (no schema).** Test: `test_complete_review_atomic_refuses_completed_row` — a completed row → `ReviewAlreadyCompletedError`, and all 24 columns are byte-unchanged. Test: `test_cli_review_complete_refuses_completed_row` — CliRunner exit 1, output contains `Review already completed`, no traceback, row unchanged. Both are RED on current code (it re-derives). Implement:
  - Step 1's SELECT reads `completed_date`; raise `ReviewAlreadyCompletedError("Review already completed")` before any compute (inside the existing `BEGIN IMMEDIATE`; the existing `except` rolls back).
  - The CLI catches that type only → `click.ClickException("Review already completed")`.
  - Existing web 409 test green (`routes/trades.py:3766-3770` unchanged).
- **T12b (0041 `trg_rl_no_replace` + the F-I3 writer).** Test first, `test_insert_pre_create_contract` (CHARC S3-F4 wording): at 41 with the row present → returns `None`, raises nothing, and `SELECT count(*)` is unchanged; absent → returns the new id; at 40, same contract. RED at 41 before the writer change (the trigger message lacks `UNIQUE`). Implement:
  - `INSERT INTO review_log (...) SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM review_log WHERE review_type = ? AND period_start = ? AND period_end = ?)`.
  - `cur.rowcount == 0` → `None`.
  - The existing `except sqlite3.IntegrityError` matcher RETAINED VERBATIM as the belt (no trigger-name matching; (ii) refused).
  - Plus `trg_rl_no_replace` and `trg_rl_no_delete`.
  - The nightly caller `runner.py:4207` pipeline test green.
  - Manifest. Commit.
- **T12c (`trg_rl_immutable`).** Tests: §4.2 with S (every S column on a completed row aborts; each S column on an uncompleted row admitted) and I always. `superseded_by_correction_id` on a completed row admitted — the literal `:2404` statement, via `_supersede_review_log_for_trade_close`. `complete_review_atomic` on an uncompleted row admitted. The closure test `test_rl_trigger_refusal_unreachable_through_service` (§4.4). Manifest. Commit.

**T13 — `pex` + `wla`.** Tests: §4.1 A2-A6 minus A7 (no twin), the writer suites (`tests/**/test_pattern_exemplars*`, `tests/web/*patterns*`, `tests/**/test_watchlist*`) green, and `record_entry`'s archive step green. Manifest. Commit.

**T14 — F-I6 pins (CHARC (a); six backstops).** `test_migration_0041_fi6_pins.py`, one test per backstop (§4.5). No schema. Commit.

**T15 — meta tests over the whole of 0041.**
- `test_every_0041_when_is_coalesce_wrapped`: parse every `CREATE TRIGGER` in the file; each `WHEN` begins `NOT COALESCE(` or `COALESCE(`.
- `test_0041_pk_clause_idiom`: each `no_replace` over an INTEGER PK contains `NEW.<pk> != -1 AND <pk> = NEW.<pk>`.
- `test_0041_manifest_composition`: migrate fresh DBs to 40 and 41; diff `sqlite_master` by (type, name). ADDED == the 59 names of §1.4 exactly; CHANGED == {`trg_provenance_corrections_append_only_update`} (plus `schema_version`'s row); DELETED == ∅; no table/index sql changed.
- `test_0041_is_triggers_only`: the file has no `CREATE TABLE|INDEX|VIEW`, `ALTER`, `DROP TABLE`, `INSERT`, `DELETE`; exactly one `DROP TRIGGER`.
- Commit.

**T16 — fixture fallout sweep (the 55 files, ledger STEP 3).**
- Run the fast suite. Classify each red test; re-plant by the rule:
  - (a) the test needs a pre-existing state → plant it with a raw INSERT carrying the final values;
  - (b) the test exercises DETECTION of a moved/deleted/rewritten row (e.g. the drift reader's moved `evaluation_runs` row) → `with guards_dropped(conn, "<name>")`, a one-line reason comment, TEST DB only;
  - (c) the test asserted `match="UNIQUE"` on a now-barriered key → assert the barrier's trigger name instead (AL-8);
  - (d) a cascade-parent delete in a test (`trades`, `pipeline_runs`, `reconciliation_runs`, `hypothesis_registry`) that now hits a child's `no_delete` → seed without the guarded child, or (b) with reason.
- A red test whose writer is PRODUCTION code (not a test's raw SQL) is a FINDING: STOP, report up, never narrow a barrier.
- Commit per module group.

**T17 — row-3 docstring (COMMENT-ONLY).** Replace `cohort_provenance_correction.py:3168-3174`'s "checked rather than assumed: grep ... returns ZERO sites" reason with: the candidate row is held by 0037's `trg_candidates_no_update`/`_no_delete`/`_no_replace`, and its criteria by 0041's `trg_cc_no_update`/`_no_delete`/`_no_replace`, so there is no path for either to drift through. `git diff` shows docstring lines only. Commit `docs(trades): ... comment-only`.

**T18 — probe `--post-migrate`, live-copy rehearsal, full suite.**
- **Step 1, build `--post-migrate` (tests first; the script has only `--make-copy`/`--copy`/`--live-ro` today, `probe_22i_guard_census.py:765-770`).**
  - The flag requires `--copy` and keeps the live-path refusal. It adds ONE section, `G-0041`, after the existing sections, and changes exactly three existing expectations: the `pc_append_only_update` (ii) set and the risk-policy branch expect FIRES; the five PK → NULL probes (4 `pc` + 1 `eia`) expect `CONSTRAINT:datatype mismatch` (CHARC F-I2: engine-refused, expectation corrected); `lve_update_guards` expects `view_session_date` / `latch_state_at_first_view` to ABORT by `trg_lve_first_view_immutable`. One setup change: the two `pc` risk-policy-branch probes (`:520-532`) delete a `risk_policy` row, which `trg_rp_no_delete` now refuses, so under the flag their in-txn setup first drops `trg_rp_no_delete` (rolled back with the probe; the row is labelled "clause pin, parent delete refused in production", AL-9).
  - `G-0041` iterates `SPEC` from `tests/data/_22i_guard_spec.py`, loaded by file path (the spec module imports nothing from `swing`, so the probe still never imports `swing`). Per guarded table, on its first and last row by PK, each probe inside `BEGIN ... ROLLBACK`: A2 on each conflict key; A4 explicit conflicting PK; A6 `DELETE`; one UPDATE per I/W/D column with the class's refused transition; one UPDATE per M column (expect OK); per F column the C4b parent-present `fk → NULL` (expect abort). The expected trigger is named per probe. A table with no rows emits `INFO no-row`.
  - Test `tests/scripts/test_probe_22i_post_migrate.py`: on seeded temp DBs (`_22i_seed.migrated`), `G-0041` reports FAIL = 0 at 41, and at 40 every abort-expected `G-0041` probe reports FAIL (the RED control). The existing sections need live rows (trade-23/25) and are not unit-tested.
  - Commit `feat(scripts): ...`.
- **Step 2, run it:** `scripts/probe_22i_guard_census.py --post-migrate --copy <migrated copy>`. Acceptance: `G-0041` FAIL = 0; total FAIL = 34 (r0's 101 − 62 F-I2 flips − 5 corrected PK → NULL), and every one of the 34 is in a declared class: 16 snapshot CHECK + 1 `applied_at` NOT NULL (F-I6, pinned T14), 5 citation declared-open (AL-2), 12 `eia` schema/sibling-backstopped (F-I6). Output path + sha256 go in the exec ledger.
- Rehearsal, the 22-B G6 shape:
  - Take a backup-API copy of live (`mode=ro` source) and run `PYTHONPATH=. python -m swing.cli --config <scratch cfg, all [paths] in scratch> db-migrate`. Assert `swing.__file__` resolves inside the worktree and the version constant reads 41.
  - Expect ONE gate image `swing-pre-22i-migration-<UTC>Z.db` in `backups_dir`.
  - Copy → 41; `quick_check` ok; `foreign_key_check` []; `schema_manifest.py --db <copy>` clean; the 59 names present; the rebuilt text byte-matches §1.4.
- Record in the exec ledger.
- `python -m pytest -m "not slow" -q` full; `ruff check swing/`; trailer audit. Then Reviewer A.

## 4. Test roster

### 4.0 Harness
`tests/data/_22i_guard_spec.py` (pure data: no `swing` import, because T18's probe loads it by path):
- `SPEC: dict[str, GuardSpec]` — class, pk, conflict-key columns, I/W/F(parent, ppk)/D/M/DATA/S sets, abbreviation, reachability of each F.
- `GUARDS_22I_ADDED: tuple[str, ...]` (the 59 names).

`tests/data/_22i_seed.py`:
- `migrated(tmp_path, version) -> sqlite3.Connection` (plain sqlite3, FK ON, `run_migrations(..., target_version=version)`).
- `seed_<table>(conn) -> pk`.
- `outcome(conn, sql, params) -> "OK" | "TRIGGER:<name>" | "CONSTRAINT:<kind>"`: the census `Probe.classify` mapping from RAISE text to trigger name, rebuilt from `sqlite_master` at call time.

The verdict pair: `@pytest.mark.parametrize("version,expect", [(40, "exposed"), (41, "guarded")])`. "exposed" asserts the statement SUCCEEDS or aborts only by an engine constraint; "guarded" asserts `TRIGGER:<the named trigger>`.

### 4.1 (a) triple discriminators — `test_migration_0041_triples.py` (parametrized over (a) spec rows; pde, pex, wla reuse A2-A6)

| Id | Probe | v40 | v41 |
|---|---|---|---|
| A1 | ordinary append, pk omitted | OK | OK |
| A2 | `INSERT OR REPLACE` / bare `REPLACE` on each conflict key with a new payload | OK (row replaced, id moved where the key is not the PK) | `trg_<abbr>_no_replace` |
| A3 | `INSERT OR IGNORE` and `... ON CONFLICT DO NOTHING` on the conflict key | OK (no-op) | `trg_<abbr>_no_replace` (the priced cost, pinned) |
| A4 | plain `INSERT` with an explicit conflicting PK | CONSTRAINT:UNIQUE/PK | `trg_<abbr>_no_replace` |
| A5 | `INSERT OR REPLACE` with an explicit conflicting PK | OK | `trg_<abbr>_no_replace` |
| A6 | `DELETE` | OK | `trg_<abbr>_no_delete` |
| A7 | `UPDATE <col>` for EVERY column (value → different value) | OK | `trg_<abbr>_no_update` |
| A8 | explicit `-1` PK insert (INTEGER-PK tables) | OK | OK — the declared residual AL-1, pinned so a later `CHECK` is a visible change |

For `cc`, A4/A5 use the composite PK and A8 is skipped. For tables with no UNIQUE beyond the PK, A2/A3 run on the PK.

### 4.2 (c) twin discriminators — `test_migration_0041_twins.py` (parametrized over the (c) spec rows)

| Id | Probe | v40 | v41 |
|---|---|---|---|
| C1 | UPDATE each I column | OK | `trg_<abbr>_immutable` |
| C2 | UPDATE each M column | OK | OK |
| C3a / C3b / C3c | W: NULL → value · value → other · value → NULL | OK / OK / OK | OK / immutable / immutable |
| C4a | F, REACHABLE: the production parent delete (FK ON). DELETABLE-NO-PRODUCTION-DELETER: a probe `DELETE` of a parent seeded without guarded CASCADE children (a `pipeline_runs` row with no `pattern_evaluations`; a `trades` row with no `trade_events`/`daily_management_records`), labelled "probe delete, no production deleter" | OK | OK (child FK NULL) |
| C4b | F: `UPDATE child SET fk = NULL` with the parent PRESENT (CHARC @ `7e0463ed`, EVERY a17 site) | OK | immutable |
| C4c | F: fk → NULL together with one I column | OK | immutable |
| C4d | F: NULL → value (a row seeded with NULL) | OK | immutable |
| C4e | F, DEAD-BY-PARENT-GUARD: the clause's own pin — parent deleted with FK OFF under `guards_dropped(<parent>_no_delete)`, then fk → NULL | OK | OK (labelled "clause pin, no production path") |
| C5 | D (`rp.is_active`): 1 → 0 · 0 → 1 | OK · OK | OK · immutable |
| C6 | `no_delete` | OK | `trg_<abbr>_no_delete` |
| C7 | A2-A5 of §4.1 against `trg_<abbr>_no_replace` | as §4.1 | as §4.1 |
| C8 | **COMPARATOR** (RD binding (ii); CLAUDE.md #11): (1) the spec's classes partition `PRAGMA table_info` exactly (disjoint, no unknown, no missing); (2) the stored `trg_<abbr>_immutable` sql references `NEW.<c>` for every non-M column and for NO M column; (3) each I column appears in the form `NEW.<c> IS OLD.<c>`; (4) each F column's clause names its spec parent and parent PK | — | PASS |

Per-table extras (named tests):
- `rc`: `test_rc_split_into_partials_end_to_end`, `test_rc_supersede_repo_208`, `test_rc_entry_date_correction_1543`.
- `dmr`: T11's list.
- `rl`: T12's list.
- `rp`: `test_rp_supersede_end_to_end`, `test_rp_ratification_after_0041`.
- `hr`: `test_hr_transition_end_to_end`; `test_hr_preregistered_criteria_frozen`.
- `hsh`: `test_hsh_update_close_open_interval`.
- `sac`/`yfc`: `test_audit_row_lifecycle_at_41`, `test_fix_phase2_script_statement_admitted`.
- `aes`: `test_aes_upsert_at_41`, `test_aes_account_hash_stamp_at_41`, `test_corrector_snapshot_branch_unreachable`.
- `rr`/`rd`: one test per writer site of the twelve (ledger S3-2), each at 41.

### 4.3 `pde` a17 (`test_migration_0041_pde.py`)
- P1: prune → admitted, `chart_render_id` NULL.
- P1b: `refresh_chart_render` → admitted.
- P2: `pipeline_runs` delete (a run with no evaluations) → admitted, `pipeline_run_id` NULL.
- P3: `chart_render_id` → NULL with the parent present → aborts.
- P3b: `pipeline_run_id` → NULL with the parent present → aborts.
- P4: FK → NULL + `composite_score` → aborts.
- P5: NULL → value → aborts.
- P6: a payload column alone → aborts.
- P7: a no-op `UPDATE ... SET ticker = ticker` → aborts.

v40 column: all OK.

### 4.4 Service-twin closure (authorize-then-abort; harness §5.1)
`test_rl_trigger_refusal_unreachable_through_service` — for each `trg_rl_immutable` refusal reachable by a production path (a re-completion), the service raises the typed error first and the trigger is never reached. Two assertions: the error type is `ReviewAlreadyCompletedError` (not `sqlite3.IntegrityError`), and a `sqlite3` trace callback records no UPDATE statement against `review_log`.

### 4.5 F-I6 pins (`test_migration_0041_fi6_pins.py`; CHARC (a)). Each test raw-inserts the input on a v41 DB with the FULL trigger set present.

| Pin | Open trigger(s) (census) | Backstop — DDL quoted in the test's docstring from `sqlite_master` | Assertion |
|---|---|---|---|
| FI6-1 | `trg_eia_structural`, `trg_eia_tier2` on `admission_tier` NULL | `admission_tier ... NOT NULL` + its `CHECK (admission_tier IN (...))` | error == `NOT NULL constraint failed: entry_intent_attestations.admission_tier` |
| FI6-2 | `trg_eia_audit_trail`, `_cited_fields`, `_tier2` on `trade_id` NULL | sibling `trg_eia_outcome` | outcome == `TRIGGER:trg_eia_outcome` |
| FI6-3 | `trg_eia_audit_trail` on `cited_fields_json` NULL / `$[0]` / `$[1]` absent | sibling `trg_eia_cited_fields` | `TRIGGER:trg_eia_cited_fields` (3 params) |
| FI6-4 | `trg_eia_structural`, `trg_eia_tier2` on `entry_broker_order_id` NULL | sibling `trg_eia_trade_binding` | `TRIGGER:trg_eia_trade_binding` |
| FI6-5 | `trg_provenance_corrections_citation_graph` on `entry_fill_snapshot_json` keys `action, fill_datetime, fill_id, trade_id` absent / JSON-null | the `pc` CHECK on `entry_fill_snapshot_json` | `CONSTRAINT:CHECK` naming `entry_fill_snapshot_json` (8 params) |
| FI6-6 | `citation_graph` `last_word` branch on `applied_at` NULL | `applied_at NOT NULL` | `NOT NULL constraint failed: provenance_corrections.applied_at` |

Each pin's docstring states the precondition (backstop on the SAME statement) and that removing it needs a table rebuild, which D51 reports as CHANGED.

### 4.6 Non-regression (kept green, not new)
- The citation-trigger replay set (D60 evidence, F-I2 ruling): trade-25 stored row admits; trade-23 operand-completed admits; trade-23 STORED row stays refused. Add `test_0041_citation_replay_set` if no existing test pins all three at 41.
- Every existing 0036-0040 trigger test.
- `record_view` tests.
- The web review 409 test.
- The census probe's confirmed guards (T18 `--post-migrate`).

## 5. Accepted limitations (each with its reason; reviewers are invited to challenge any reason)

- **AL-1 — explicit `-1` PK on existing tables.** A row inserted with an explicit PK of `-1` passes every `no_replace` PK clause, and no `CHECK (pk > 0)` is added. *Reason:* the CHECK needs a table rebuild, which brief §2.6 excludes; live has 0 non-positive PKs on all 43 tables (census a16); no writer supplies an explicit PK (ledger STEP 3 INSERT read); A8 pins it.
- **AL-2 — five citation-trigger inputs admitted by declared design** (`rung7_consumption_scan_fill_ids.input[0]` and `decision_ordering.input[0]` absent; `remote_ref_updated_at`/`remote_ref_age_seconds` JSON null). *Reason:* the trigger's own comments (live dump `:1415-1431`, `:1767-1773`, `:1981-1982`) declare them — completeness limits and nullable-by-contract fields, not NULL-`WHEN` holes; CHARC F-I6 ruling.
- **AL-3 — the (b) tables stay unguarded:**
  - `daily_recommendations`: row mutable in place by 0036's design (`0036:121-126`); evidence frozen at citation into `cited_recommendation_snapshot_json`; drift reported by the read command. The `0003:98` "immutable session snapshot" comment is stale and left unedited (applied migration). The cited rows 169/172 are held by `ON DELETE RESTRICT`, measured: REPLACE/DELETE abort under FK ON; **the RESTRICT holds only on FK-ON connections — the migration runner runs FK OFF and writes no `daily_recommendations` rows** (RD, verbatim reason).
  - `watchlist_close_track_flags` / `_flag_events`: dormant, zero callers.
  - `chart_renders`: a cache.
  - `pipeline_step_timings`: T1 telemetry.
  - Each re-opens if its stated condition changes (RD F-I1).
- **AL-4 — a trigger binds SQL, not people.** `DROP TRIGGER` or a future migration can remove any guard. *Reason:* that is D51's job: the manifest reports the removal as DELETED at the merge gate.
- **AL-5 — D58 (the pre-migration snapshot fence) is not in 22-I.** *Reason:* brief §2.6; its own item.
- **AL-6 — under `foreign_keys=OFF` a parent can be deleted without the cascade, after which a raw `UPDATE child SET fk = NULL` satisfies the a17 parent-gone clause.** *Reason:* this is the v40 `trg_eia_no_update`/pc shape CHARC ruled to copy; production connections run FK ON (`db.py:149`); for DEAD-BY-PARENT-GUARD FKs the parent delete itself is refused by `no_delete` regardless of the FK pragma.
- **AL-7 — the corrector's `account_equity_snapshots` branch** (`reconciliation_auto_correct.py:2325-2328`, `SET {field_name}`) could name an I column. *Reason:* SERVICE-prevented, not schema-prevented: `_resolve_affected_target` (`:2182-2205`) never returns that table (its code returns `fills`/`cash_movements`/`trades` or raises `ValueError`, whatever its docstring says) (pinned by `test_corrector_snapshot_branch_unreachable`); live incidence 0 of 44 corrections. If it ever did, the trigger would refuse (a loud authorize-then-abort, never a silent write).
- **AL-8 — a duplicate INSERT on a newly-guarded UNIQUE key now raises the barrier's RAISE text instead of `UNIQUE constraint failed`.** *Reason:* a `BEFORE INSERT` trigger fires before conflict resolution (CLAUDE.md, third facet); the only production code matching on the text, `review_log.insert_pre_create`, is adjusted under F-I3 (T12b). Every other `except sqlite3.IntegrityError` in `swing/` was READ: none guards an (a)/(c) table's conflict (the ledger's plan-stage sweep row).
- **AL-9 — DEAD-BY-PARENT-GUARD a17 exemptions are kept.** *Reason:* CHARC ruled uniformity @ `7e0463ed` (three states @ `732c5c21`); the C4e pin keeps each clause executable. DELETABLE-NO-PRODUCTION-DELETER exemptions are pinned by C4a's probe delete.
- **AL-10 — two kinds of test drop a named guard on their own temp DB** (`tests/_22i_guard_seam.py`): tests that plant historical corruption, and a17 clause pins whose parent delete a `0041` `no_delete` refuses (T2's risk-policy pair, C4e, T18's probe setup). *Reason:* a trigger cannot be bypassed by a raw INSERT the way a Python write-barrier can (the 18-B.1 technique); the first kind exercises DETECTION of states the schema now forbids, the second keeps an unreachable exemption clause executable (AL-9); each use carries its reason. The helper never touches a non-test path.
- **AL-11 — (c) columns named M stay mutable, and `pattern_exemplars` / `watchlist_archive` carry no twin.** *Reason:* ruled (RD F-I1); each M set is the writer's measured UPDATE set (ledger STEP 3), defended by the C8 comparator.
- **AL-12 — `review_log` re-completion is now REFUSED on the CLI**, where it used to overwrite. *Reason:* S3-F3 (A) — the freeze contract at `review_log.py:177` and the web's existing 409; the refusal is the trigger's service twin (CHARC scope ruling).

## 6. Merge packet (for the orchestrator's gate; brief §4/§5)

- The exec ledger rows (Reviewer A per round).
- B's transcript on the tree being merged.
- The merged-head suite with SHA.
- The D51 diff read as §1.4.
- `schema_manifest.py --check` clean.
- T18's rehearsal record: ONE gate image; `foreign_key_check` []; `quick_check` ok.
- The `--post-migrate` probe output with sha256.
- The witness sitting W0-W5 per brief §5. W5 re-runs the census probe `--live-ro` catalogue only; write probes on the copy only.
