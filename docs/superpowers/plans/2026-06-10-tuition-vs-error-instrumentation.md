# Tuition-vs-Error Instrumentation (`entry_intent`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an orthogonal, operator-set `entry_intent` attribute (`standard` | `hypothesis_test_by_design` | NULL) to every trade and facet the process-quality surfaces by it — resolving the tuition-vs-error conflation — without touching the measurement chain, grade/tag semantics, or the #22 PGT redesign.

**Architecture:** One additive nullable, CHECK-constrained column via migration `0027` (v26→v27, strict backup gate) + the `ENTRY_INTENTS` constant/`Trade` validator/repo plumbing landed atomically (#11); a pure `swing/trades/intent.py` presentation+prefill module (advisory-only `suggest_entry_intent`); set-at-entry / correctable-at-review / CLI-backfillable surfaces (server-stamped, never label-derived); a faceted trade-process card + an **always-on cross-intent execution-discipline panel** that keeps risk/reconciliation slips visible regardless of the facet; annotated PGT markers. The measurement chain (registry/matcher/tripwires/shadow engine/temporal log) and `process_grade`/`mistake_tags` semantics are UNTOUCHED.

**Tech Stack:** Python 3.14, SQLite (migration runner in `swing/data/db.py`), FastAPI + HTMX + Jinja2, click CLI, pytest (`-m "not slow"` fast suite), ruff. Windows cp1252 stdout (ASCII-only CLI/form strings, gotcha #16).

**Binding spec:** `docs/superpowers/specs/2026-06-10-tuition-vs-error-instrumentation-design.md` (commit `0c1efe71`; Codex-converged R4). Operator decisions **D1–D6** and locks **L1–L7** in spec §2 are CLOSED — implement them, do not re-open. The measurement chain is L1-isolated; grade/tag semantics are L2-frozen; faceting is NOT regrading; the §7.1 execution-discipline panel contract is fully specified in the spec — implement it, do not reinvent it; the #22 PGT L5 locks are preserved; spec §7.5/§7.6 surfaces appear in NO task.

---

## Verified-against-disk signatures + live-DB data shapes (2026-06-10, this plan-write)

Every signature below was read from `main` HEAD at plan-write time. The spec's `file:line` anchors had drifted (main moved since the spec was written); the **re-anchored** values below are authoritative for this plan. **Codex must independently re-verify these against the shipped code, and the §1 live-record claims against the supplied read-only query output — fixtures must NOT force them true (`feedback_adversarial_review_verify_data_shapes`).**

**Schema / migration state:**
- `swing/data/db.py:51` — `EXPECTED_SCHEMA_VERSION = 26` (the SOLE production schema pin).
- Migrations on disk: `0024_phase15_b7_failure_mode.sql`, `0025_phase16_pipeline_step_timings.sql`, `0026_broad_watch_baseline.sql`. **`0027` is FREE** (see the migration-number preflight below).
- `_broad_watch_baseline_backup_gate` (`db.py:1163`) registered in `run_migrations` at `db.py:1285` (last gate). `BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES` (`db.py:233`) = `PHASE16_PRE_MIGRATION_EXPECTED_TABLES | {"pipeline_step_timings"}` (the true-v25 set; 0026 added **no** table → the v26 table set EQUALS the v25 set).
- 0024 ALTER template (`0024_phase15_b7_failure_mode.sql`): `BEGIN; ALTER TABLE trades ADD COLUMN failure_mode TEXT CHECK (... IS NULL OR ... IN (...)); UPDATE schema_version SET version = 24; COMMIT;` — copy this shape verbatim.

**Model / repo (`swing/data/models.py`, `swing/data/repos/trades.py`):**
- `FAILURE_MODES` frozenset at `models.py:186`; `Trade` dataclass `models.py:197`; `failure_mode: str | None = None` is the LAST field (`models.py:289`); `Trade.__post_init__` validates `failure_mode` (`models.py:291-298`).
- Repo SELECT projections: `_TRADE_SELECT_COLS` (v24+, `trades.py:57`, ends `... candidate_id, pattern_evaluation_id, failure_mode`), `_TRADE_SELECT_COLS_V21_TO_V23` (`:82`, ends `... NULL AS failure_mode`), `_TRADE_SELECT_COLS_PRE_V21` (`:107`, ends `NULL AS candidate_id, NULL AS pattern_evaluation_id, NULL AS failure_mode`). `_trade_select_cols(conn)` (`:130`) detects columns via `PRAGMA table_info` and composes (three eras).
- `insert_trade_with_event` (`trades.py:185`): TWO branches (v21+ INSERT incl. `candidate_id, pattern_evaluation_id`; legacy pre-v21). **`failure_mode` is NEVER in the INSERT** (review-only). `entry_intent` IS set at entry → a NEW v27+ branch is required.
- `_row_to_trade` (`trades.py:508`): positional map; `failure_mode=row[54]` is the last (`:581`). `entry_intent` → index **55**.
- `update_trade_review_fields` (`trades.py:585`): the PRAGMA-aware-write precedent for the dedicated `update_entry_intent`. (Do NOT widen this writer — the spec mandates a separate `update_entry_intent`.)

**Prefill / presentation precedent (`swing/trades/review.py`):**
- `MISTAKE_TAGS` (`review.py:37`): `risk` = `OVERSIZED, NO_STOP, STOP_TOO_WIDE, STOP_TOO_TIGHT, CORRELATION_IGNORED, GAP_RISK_IGNORED, HEAT_OVERAGE, CIRCUIT_BREAKER_OVERRIDDEN`; `reconciliation` = `SIZE_MISCOUNTED, WRONG_TICKER_ENTERED, FILL_NOT_LOGGED, PARTIAL_NOT_LOGGED, STOP_NOT_PLACED`. `CHASED`/`NO_SETUP`/`EARLY_ENTRY` are in `entry` → correctly ABSENT from the discipline panel.
- `FAILURE_MODE_DISPLAY` tuple + `failure_mode_display_choices()` + `failure_mode_label()` + the `{v for v,_ in DISPLAY} == FAILURE_MODES` no-drift test (`review.py:74-96`) — the verbatim template for `intent.py`.

**Faceting surfaces (verified):**
- `compute_trade_process_metrics(conn, *, hypothesis_label)` at `process.py:546`; the mistake-tag loop at `process.py:747-768`; `_render_class_a_cell(*, name, k, n, policy)` at `process.py:501`; `MetricCellA` at `process.py:322`; `TradeProcessMetricsResult` at `process.py:403` with `n_reviewed` at `:415`, `mistake_tag_frequency` at `:455`, `__post_init__` int-loop at `:459-469`. The result is built once-per-cohort AND once for All.
- `cohort.py:32` `list_trades_for_cohort(conn, *, hypothesis_label, state_filter=None)`; `cohort.py:84` `list_closed_trades_for_cohort(conn, *, hypothesis_label)` (thin wrapper). Both build WHERE via `label_matches_hypothesis_sql` + optional `state IN (...)`, SELECT via `_trade_select_cols(conn)` → `entry_intent` flows through automatically once the projection includes it.
- Card VM `build_trade_process_card_vm(*, cfg, conn=None, active_cohort_key=None)` at `trade_process_card.py:123`; per-cohort `compute_trade_process_metrics(conn, hypothesis_label=name)` at `:163`; All-aggregate `compute_trade_process_metrics(conn, hypothesis_label=None)` at `:176`; `CohortTabVM` at `:49`; `TradeProcessCardVM(BaseLayoutVM)` at `:91`; `ALL_COHORTS_KEY` toggle. Template `trade_process_card.html.j2`: cohort tabs partial at `:13`, active selection `:15-19`, `process_grade_distribution.items()` at `:95`, `mistake_tag_frequency.items()` at `:106`. Route `GET /metrics/trade-process` at `routes/metrics.py:63` `metrics_trade_process(request, cohort: str | None = Query(default=None))` → `build_trade_process_card_vm(cfg=cfg, active_cohort_key=cohort)`; plain server-rendered (no HTMX OOB/redirect).

**PGT surfaces (verified):**
- `ProcessGradeTrendPoint` (frozen) at `process_grade_trend.py:79`; last field `mistake_cost_R: float` (`:99`); `__post_init__` validators `:101-130`. `_build_per_trade_point(trade, ordinal, mistake_cost_R)` at `:298` (has the `Trade` object → can read `trade.entry_intent`); construction `:314-326`; called from the loop at `:564-572`. `ProcessGradeTrendResult` at `:213` with the `rolling_series` keyset invariant `__post_init__` `:226-234` (UNTOUCHED).
- VM `PerTradeMarkerDisplay` (frozen) at `view_models/metrics/process_grade_trend.py:113`; `_build_marker_display(...)` at `:506`, constructor call `:541-546`.
- Template `process_grade_trend.html.j2`: GRADES `<circle>` marker loop `:57-70` (hooks `data-trade-id`, `data-grade`, `data-disqualifying`, `r="4"`, `class="process-grade-marker"`); grade polylines `:71-84`, rate `:99-113`, cost `:128-142` (hook `data-series`); SVG panels `data-panel="grades|rate|cost"` (`:36,:93,:122`); `data-marker="grade-axis-encoding"` `:38`; `data-marker="grades-legend"` `:49`; numeric encoding `A=4, B=3, C=2, D=1, F=0`. **No matplotlib/external-lib guard exists in the template; the no-matplotlib test lives in the route/template test suite — preserve every hook above.**

**Set/correct surfaces (re-anchored — spec lines drifted):**
- Web entry: GET `entry_form` at `routes/trades.py:~400`; POST `entry_post` at `:~448` with the `EntryRequest` construction at `:~1251-1318` and the `MissingPreTradeFieldsException` soft-warn re-render (rebuilds `build_entry_form_vm`, draft_* preservation) at `:~1334-1373`. (Spec said 330/565 — drifted.)
- Web review: GET `review_form_page` at `:~2591`; POST `review_post` at `:2669` (`failure_mode: str | None = Form(None)` at `:2680`; validates against `FAILURE_MODES` `:2754-2766`; routes through `complete_trade_review` `:2799-2812`; success = `204` + `HX-Redirect: /reviews/pending` `:2815`). (Spec said 2620/2669.)
- `EntryRequest` at `entry.py:97` (last fields `pattern_evaluation_id`/`candidate_id` `:173-174`); `record_entry` at `entry.py:224`; the `Trade(...)` construction at `entry.py:352-407` (ends `candidate_id=resolved_candidate_id, pattern_evaluation_id=req.pattern_evaluation_id`).
- CLI: `trade` group at `cli.py:584`; `trade_entry_cmd` at `:589` (options `:589-697`; `EntryRequest` build `:811-848`; `--hypothesis` precedent `:~690`); `trade_review_cmd` at `:1328` (`--failure-mode` precedent `:~1360`; `FAILURE_MODES` validation + `complete_trade_review` + `ClickException` wrap `:1455-1497`); `_render_trade_analysis` at `:1141` (`Hypothesis:` print `:~1161`). (Spec said 699/1364/1098 — drifted.)
- Entry-form VM `EntryFormVM` in `view_models/trades.py` (`hypothesis_label` `:287`; draft_* block `:296-320`); `build_entry_form_vm` at `:383`. Review VM `ReviewVM` at `:1140` (`failure_mode_choices: tuple[tuple[str,str],...] = ()` `:1158`); `build_review_vm` at `:1232` (uses `failure_mode_display_choices()` `:1398`).
- Display-only: `TradeAnalysis` (frozen) at `journal/analyze.py:86` (last field `r_multiple_avg` `:104`; `hypothesis_label` `:96`); `analyze_trade` at `:208` sets `hypothesis_label=trade.hypothesis_label` `:319`.
- Entry-form template: `templates/partials/trade_entry_form.html.j2` (the `<select>` insertion point near the hypothesis_label control — verify the exact line at execution). Review template: `templates/partials/review_form.html.j2`.

**Live-record (§1) ground truth (read-only, 2026-06-10):** schema v26; `entry_intent` column ABSENT; **16 trades**. Proposed-intent split: **YOU** (`A+ baseline (aplus)`) → `standard`; **VSAT/PTEN** (NULL label) → `standard` (operator); **VIR** (`inaugural trade test`) → `by_design` BUT `suggest_entry_intent` emits **`None`** (no keyword match) — its `NO_STOP`/`STOP_NOT_PLACED` slips stay visible via the discipline panel; all other H3-family `Sub-A+ VCP-not-formed`/BULZ `Near-A+ ... extension test` → `hypothesis_test_by_design`. SKYT (id 15) is **closed-not-reviewed** (`pg=NULL`) yet carries a deliberate entry intent (proves intent ≠ review attribute).

---

## Migration-number preflight (BINDING — executing agent runs this FIRST)

Phase 16 has arcs in flight/queued (perf; Arc 7 watchlist-pin, which will itself take a migration). Before branching, the executing agent MUST verify `0027` is still free:

```bash
ls swing/data/migrations/ | sort        # confirm 0027_*.sql does NOT exist
grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py   # confirm it reads 26
```

- If `0027` is free and `EXPECTED_SCHEMA_VERSION == 26`: proceed with `0027`/`v27` exactly as written.
- If another arc has landed `0027` (or bumped EXPECTED past 26): **renumber** this migration to the next free integer `N`, set `EXPECTED_SCHEMA_VERSION` to `N`, set the gate's strict equality to `current_version == (N-1) AND target_version >= N`, set `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES` to the true `(N-1)` table set (= the prior gate's expected-tables set plus any table the intervening migration added), and re-run the version-pin sweep (Task 1 Step 9) against the NEW head value. Note the renumber in the commit body. Every `27`/`v27`/`26`/`v26` literal in this plan is then read as `N`/`N-1`.

The plan below assumes the free-`0027` case.

---

## File Map

**Production (the L6 §2 carve-out — exactly these + tests):**
- `swing/data/migrations/0027_entry_intent.sql` — **CREATE.** 0024-shaped `ALTER TABLE trades ADD COLUMN entry_intent TEXT CHECK (...)` + `UPDATE schema_version SET version = 27;`.
- `swing/data/models.py` — **MODIFY.** `ENTRY_INTENTS` frozenset (alongside `FAILURE_MODES`); `Trade.entry_intent` field + `__post_init__` validator.
- `swing/data/repos/trades.py` — **MODIFY.** 4th projection era + `_trade_select_cols` branch; `_row_to_trade` index 55; `insert_trade_with_event` v27+ branch; new `update_entry_intent`.
- `swing/data/db.py` — **MODIFY.** `EXPECTED_SCHEMA_VERSION` 26→27; `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_entry_intent_migration_backup`; `_entry_intent_backup_gate`; gate registration after `_broad_watch_baseline_backup_gate`.
- `swing/trades/intent.py` — **CREATE.** Pure presentation + prefill (`ENTRY_INTENT_DISPLAY`, `entry_intent_label`, `entry_intent_display_choices`, `suggest_entry_intent`).
- `swing/trades/entry.py` — **MODIFY.** `EntryRequest.entry_intent` + validation + thread to `Trade(...)`.
- `swing/trades/review.py` — **UNCHANGED** (no widening; the dedicated `update_entry_intent` is the writer). Listed only to assert it is NOT modified.
- `swing/metrics/process.py` — **MODIFY.** `entry_intent` filter param + the two new result fields + the discipline panel.
- `swing/metrics/cohort.py` — **MODIFY.** `entry_intent` predicate on both list functions.
- `swing/metrics/process_grade_trend.py` — **MODIFY.** `ProcessGradeTrendPoint.entry_intent` (marker field only).
- `swing/web/view_models/metrics/trade_process_card.py` — **MODIFY.** Intent facet on the "All" aggregate.
- `swing/web/view_models/metrics/process_grade_trend.py` — **MODIFY.** Marker CSS-class hook.
- `swing/web/view_models/trades.py` — **MODIFY.** `EntryFormVM` + `ReviewVM` intent fields; `build_entry_form_vm` + `build_review_vm`.
- `swing/web/routes/trades.py` — **MODIFY.** Entry/review GET render + POST persist (server-stamp; soft-warn round-trip; 4-tier ladder).
- `swing/web/routes/metrics.py` — **MODIFY.** Intent facet query param.
- `swing/web/templates/metrics/trade_process_card.html.j2` — **MODIFY.** Facet selector + discipline panel.
- `swing/web/templates/metrics/process_grade_trend.html.j2` — **MODIFY.** Marker intent attribute + legend.
- `swing/web/templates/partials/trade_entry_form.html.j2` — **MODIFY.** Intent `<select>`.
- `swing/web/templates/partials/review_form.html.j2` — **MODIFY.** Intent `<select>`.
- `swing/journal/analyze.py` — **MODIFY.** `TradeAnalysis.entry_intent` + `analyze_trade`.
- `swing/cli.py` — **MODIFY.** `--entry-intent` on entry + review; `_render_trade_analysis` print; new `swing trade backfill-intent`.

**Tests (new):**
- `tests/data/test_migration_0027_entry_intent.py`
- `tests/trades/test_intent.py`
- `tests/trades/test_backfill_intent_cli.py` (subprocess-encoding test lives here)
- `tests/metrics/test_execution_discipline_panel.py` (the orthogonality test)

**Tests (modify):** the existing model/repo/entry/review/faceting/PGT/route/CLI suites + the schema-version-pin sweep (Task 1 Step 9).

**NOT touched (locks):** `swing/recommendations/hypothesis.py`, `swing/metrics/tier.py`/`deviation_outcome.py`, `research/harness/**`, the v22 temporal log, `swing/data/repos/hypothesis.py`, `hypothesis_progress_card.py`, `journal/stats.py`, `get_priors_for_ticker`/`get_period_mistake_tag_aggregate` (spec §7.6 LEAVE-UNCHANGED), the 7 PGT rolling series, `compute_process_grade`/`validate_mistake_tags`/`canonicalize_mistake_tags`/`MISTAKE_TAGS`/`disqualifying_process_violation`. **No intent×hypothesis matrix.**

---

## Task 1: Migration 0027 + `ENTRY_INTENTS` + `Trade` validator + repo plumbing + db.py gate + version-pin sweep

The atomic schema unit (spec §4.1–§4.4, §9; #11 atomicity + #11 sweep). The migration cannot be tested without bumping `EXPECTED_SCHEMA_VERSION` (`apply_ceiling = min(target, EXPECTED)`), the bump turns the version-pin family red, and the #11 sweep lock binds the schema CHECK + constant + validator + repo projections together — so all of it lands in this one task and ends green.

**Files:**
- Create: `swing/data/migrations/0027_entry_intent.sql`, `tests/data/test_migration_0027_entry_intent.py`
- Modify: `swing/data/models.py`, `swing/data/repos/trades.py`, `swing/data/db.py`
- Modify (sweep): the test files in Step 9.

- [ ] **Step 1: Write the failing migration + gate + model + repo test**

Create `tests/data/test_migration_0027_entry_intent.py` (mirrors `tests/data/test_migration_0026_broad_watch_baseline.py`):

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _current_version,
    _entry_intent_backup_gate,
    run_migrations,
)
from swing.data.models import ENTRY_INTENTS, Trade
from swing.data.repos.trades import (
    _row_to_trade,
    _trade_select_cols,
    insert_trade_with_event,
    update_entry_intent,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version, backup_dir=backup_dir or tmp_path)
    return conn


def _make_trade(**over) -> Trade:
    base = dict(
        id=None, ticker="AAA", entry_date="2026-05-01", entry_price=10.0,
        initial_shares=10, initial_stop=9.0, current_stop=9.0, state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline", pre_trade_locked_at="2026-05-01T00:00:00",
        current_size=10.0,
    )
    base.update(over)
    return Trade(**base)


def test_expected_schema_version_is_27():
    assert EXPECTED_SCHEMA_VERSION == 27


def test_entry_intents_constant():
    assert ENTRY_INTENTS == frozenset({"standard", "hypothesis_test_by_design"})


def test_migrate_to_27_adds_nullable_checked_column(tmp_path):
    conn = _migrate(tmp_path, 27)
    assert _current_version(conn) == 27
    cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
    assert "entry_intent" in cols
    # CHECK accepts NULL + the two enum members; rejects anything else.
    conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                 "initial_shares, initial_stop, current_stop, state, "
                 "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                 "VALUES ('A','2026-05-01',10,1,9,9,'entered',"
                 "'manual_off_pipeline','2026-05-01T00:00:00',1,'standard')")
    conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                 "initial_shares, initial_stop, current_stop, state, "
                 "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                 "VALUES ('B','2026-05-01',10,1,9,9,'entered',"
                 "'manual_off_pipeline','2026-05-01T00:00:00',1',NULL)".replace("1'", "1"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO trades (ticker, entry_date, entry_price, "
                     "initial_shares, initial_stop, current_stop, state, "
                     "trade_origin, pre_trade_locked_at, current_size, entry_intent) "
                     "VALUES ('C','2026-05-01',10,1,9,9,'entered',"
                     "'manual_off_pipeline','2026-05-01T00:00:00',1,'foo')")
    conn.close()


def test_trade_model_rejects_bad_entry_intent():
    with pytest.raises(ValueError, match="entry_intent"):
        _make_trade(entry_intent="foo")
    # valid values + None accepted.
    assert _make_trade(entry_intent="standard").entry_intent == "standard"
    assert _make_trade(entry_intent=None).entry_intent is None


def test_insert_and_read_round_trip_preserves_entry_intent(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(entry_intent="hypothesis_test_by_design"),
            event_ts="2026-05-01T00:00:00", rationale="t")
    cols = _trade_select_cols(conn)
    row = conn.execute(f"SELECT {cols} FROM trades WHERE id = ?", (tid,)).fetchone()
    assert _row_to_trade(row).entry_intent == "hypothesis_test_by_design"
    conn.close()


def test_pre_v27_projection_yields_null_entry_intent(tmp_path):
    # A v26 DB: the projection must emit `NULL AS entry_intent` (merge-safe pin).
    conn = _migrate(tmp_path, 26)
    cols = _trade_select_cols(conn)
    assert "entry_intent" in cols  # as a NULL alias
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(), event_ts="2026-05-01T00:00:00", rationale="t")
    row = conn.execute(f"SELECT {cols} FROM trades WHERE id = ?", (tid,)).fetchone()
    assert _row_to_trade(row).entry_intent is None
    conn.close()


def test_update_entry_intent_writes_only_the_column(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(state="reviewed", reviewed_at="2026-05-10",
                              process_grade="A", entry_grade="A",
                              management_grade="A", exit_grade="A"),
            event_ts="2026-05-01T00:00:00", rationale="t")
    with conn:
        update_entry_intent(conn, trade_id=tid, entry_intent="standard")
    row = conn.execute(
        "SELECT entry_intent, state, process_grade, reviewed_at "
        "FROM trades WHERE id = ?", (tid,)).fetchone()
    assert row[0] == "standard"
    assert row[1] == "reviewed"      # state untouched
    assert row[2] == "A"             # review fields untouched
    assert row[3] == "2026-05-10"
    # NULL round-trips (the skip path).
    with conn:
        update_entry_intent(conn, trade_id=tid, entry_intent=None)
    assert conn.execute("SELECT entry_intent FROM trades WHERE id=?",
                        (tid,)).fetchone()[0] is None
    conn.close()


def test_update_entry_intent_rejects_bad_value(tmp_path):
    conn = _migrate(tmp_path, 27)
    with conn:
        tid = insert_trade_with_event(
            conn, _make_trade(), event_ts="2026-05-01T00:00:00", rationale="t")
    with pytest.raises(ValueError, match="entry_intent"):
        with conn:
            update_entry_intent(conn, trade_id=tid, entry_intent="foo")
    conn.close()


def test_update_entry_intent_missing_trade_raises(tmp_path):
    conn = _migrate(tmp_path, 27)
    with pytest.raises(ValueError, match="not found"):
        with conn:
            update_entry_intent(conn, trade_id=9999, entry_intent="standard")
    conn.close()


def test_backup_gate_fires_strict_on_v26(tmp_path):
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    # current==27 -> already past, inert.
    _entry_intent_backup_gate(conn, current_version=27, target_version=27, backup_dir=inert)
    # current==25, target==27 -> multi-version jump bypasses the v26-strict gate.
    _entry_intent_backup_gate(conn, current_version=25, target_version=27, backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    # current==26, target>=27 -> fires; in-memory source -> raises.
    with pytest.raises(MigrationBackupRequiredException):
        _entry_intent_backup_gate(conn, current_version=26, target_version=27, backup_dir=fire)


def test_run_migrations_wires_entry_intent_gate(tmp_path):
    backups = tmp_path / "v26_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 26); conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=27, backup_dir=backups)
    assert _current_version(conn) == 27
    snaps = list(backups.glob("swing-pre-entry-intent-migration-*.db"))
    assert len(snaps) == 1
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 27)
    run_migrations(conn, target_version=27)  # current >= target -> early return
    assert _current_version(conn) == 27
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()]
    assert cols.count("entry_intent") == 1  # not double-added
    conn.close()
```

> NOTE to implementer: the `'B'` NULL-insert line above is written awkwardly to dodge a quoting artifact — replace it with a clean `entry_intent` NULL insert (or `DEFAULT`); the assertion that matters is "NULL is accepted by the CHECK." Keep the malformed-`'foo'` `IntegrityError` assertion exact.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/data/test_migration_0027_entry_intent.py -q`
Expected: FAIL — `ImportError: cannot import name 'ENTRY_INTENTS'` / `'_entry_intent_backup_gate'` / `'update_entry_intent'`, and `EXPECTED_SCHEMA_VERSION == 27` would read `26`. Pre-fix: none of these exist; the migration never applies (`apply_ceiling = min(27, 26) = 26`).

- [ ] **Step 3: Create the migration SQL (0024-shaped)**

Create `swing/data/migrations/0027_entry_intent.sql`:

```sql
-- Migration 0027 / v27: add the nullable, CHECK-constrained entry_intent TEXT
-- column to trades (tuition-vs-error instrument; design spec 2026-06-10).
-- A nullable ADD COLUMN whose CHECK references only the new column is a cheap,
-- NON-rebuild migration (same shape as 0024's failure_mode). Existing rows
-- backfill implicitly to NULL (operator-driven backfill is a separate CLI pass,
-- spec §6). NULL = "unclassified" (a distinct third facet; NEVER coerced to
-- 'standard' -- spec L4 / §3 corollary 3).
--
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript implicit-COMMIT
-- discipline). The runner's _apply_migration wraps this with rollback-on-error.
BEGIN;
ALTER TABLE trades ADD COLUMN entry_intent TEXT
    CHECK (entry_intent IS NULL OR entry_intent IN ('standard','hypothesis_test_by_design'));
UPDATE schema_version SET version = 27;
COMMIT;
```

- [ ] **Step 4: Add `ENTRY_INTENTS` + `Trade.entry_intent` + validator (`swing/data/models.py`)**

After the `FAILURE_MODES` frozenset (`models.py:194`), add:

```python
# Tuition-vs-error instrument (migration 0027 / v27) -- the schema-CHECK enum
# for trades.entry_intent. Co-located with FAILURE_MODES (the schema-enum home)
# so the Trade dataclass __post_init__ can validate without an upward import
# from swing/trades/ (the same import-cycle reason FAILURE_MODES lives here).
# NULL = unclassified (a distinct third facet; never coerced to 'standard').
# Asserted identical to the migration 0027 CHECK by the 0027 schema test.
ENTRY_INTENTS: frozenset[str] = frozenset({"standard", "hypothesis_test_by_design"})
```

Add the field to `Trade` immediately after `failure_mode` (`models.py:289`):

```python
    # Tuition-vs-error instrument (migration 0027 / v27). Operator's stated
    # design intent for the entry, ORTHOGONAL to execution quality. Set at entry,
    # correctable at review, backfillable by CLI. NULL = unclassified. Validated
    # against ENTRY_INTENTS in __post_init__ (Literal[...] is NOT runtime-enforced).
    entry_intent: str | None = None
```

Extend `Trade.__post_init__` (after the `failure_mode` check at `models.py:298`):

```python
        if self.entry_intent is not None and self.entry_intent not in ENTRY_INTENTS:
            raise ValueError(
                f"entry_intent must be one of {sorted(ENTRY_INTENTS)} or None, "
                f"got {self.entry_intent!r}")
```

- [ ] **Step 5: Bump `EXPECTED_SCHEMA_VERSION` + add the expected-tables alias (`swing/data/db.py`)**

- `db.py:51`: `EXPECTED_SCHEMA_VERSION = 26` → `EXPECTED_SCHEMA_VERSION = 27`.
- After the `BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES` block (`db.py:233-235`), add:

```python
# entry_intent (migration 0027) backup gate: migrating v26 -> v27 snapshots the
# live v26 DB. 0027 is an ALTER ADD COLUMN -- it adds NO table -- and 0026 added
# no table either, so the v26 table set EQUALS the v25 set. Alias the broad-watch
# (true-v25) set for auditable provenance.
ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES
)
```

- [ ] **Step 6: Add the backup helper + the strict gate + register it (`swing/data/db.py`)**

After `_create_pre_broad_watch_migration_backup` (`db.py:692`), add (mirroring it verbatim with the new filename stem):

```python
def _create_pre_entry_intent_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """entry_intent (0027) mirror. SQLite-native Connection.backup() before the
    0027 migration. Backup file ``swing-pre-entry-intent-migration-<ISO>.db``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-entry-intent-migration-{timestamp}.db"
    src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
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

After `_broad_watch_baseline_backup_gate` (`db.py:1199`), add:

```python
def _entry_intent_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """entry_intent (0027) backup-before-migrate gate.

    Fires ONLY when ``current_version == 26 AND target_version >= 27`` -- a real
    production v26 DB about to cross v27. STRICT EQUALITY on pre_version per the
    ``pre_version == (target - 1)`` gotcha (NOT ``<=``); multi-version jumps from
    pre-v26 baselines bypass this gate by design.
    """
    if target_version < 27 or current_version != 26:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-entry-intent backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_entry_intent_migration_backup(
            src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-entry-intent backup failed: {exc}"
        ) from exc
```

Register it in `run_migrations` immediately after the `_broad_watch_baseline_backup_gate(...)` call (`db.py:1285-1290`):

```python
    _entry_intent_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
```

- [ ] **Step 7: Repo plumbing — 4th projection era + `_trade_select_cols` + `_row_to_trade` index 55 (`swing/data/repos/trades.py`)**

Append `entry_intent` to the v27+ projection `_TRADE_SELECT_COLS` (`trades.py:76`, change the trailing line):

```python
    candidate_id, pattern_evaluation_id, failure_mode, entry_intent
```

Rename the existing v24+ list to a v24–v26 era projection and add `NULL AS entry_intent`. Add a NEW module constant after `_TRADE_SELECT_COLS` (keep all three pre-existing constants; append `NULL AS entry_intent` to EACH so `_row_to_trade[55]` is always present):

```python
# v24-v26 era (failure_mode present, entry_intent absent): real failure_mode +
# NULL AS entry_intent. MUST NOT null failure_mode (the four-era trap).
_TRADE_SELECT_COLS_V24_TO_V26 = """
    id, ticker, entry_date, entry_price, initial_shares, initial_stop,
    current_stop, state, watchlist_entry_target,
    watchlist_initial_stop, notes, hypothesis_label,
    chart_pattern_algo, chart_pattern_algo_confidence,
    chart_pattern_operator, chart_pattern_classification_pipeline_run_id,
    sector, industry,
    reviewed_at, mistake_tags, entry_grade, management_grade,
    exit_grade, process_grade, disqualifying_process_violation,
    realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned,
    trade_origin, pre_trade_locked_at, current_size, current_avg_cost,
    last_fill_at,
    thesis, why_now, invalidation_condition, expected_scenario,
    premortem_technical, premortem_market_sector, premortem_execution,
    premortem_additional,
    event_risk_present, event_handling, event_type, event_date,
    gap_risk_present, gap_risk_handling, emotional_state_pre_trade,
    market_regime, catalyst, catalyst_other_description,
    planned_target_R,
    candidate_id, pattern_evaluation_id, failure_mode, NULL AS entry_intent
"""
```

Append `, NULL AS entry_intent` to the trailing line of BOTH `_TRADE_SELECT_COLS_V21_TO_V23` (`:101`) and `_TRADE_SELECT_COLS_PRE_V21` (`:126`):

```python
    candidate_id, pattern_evaluation_id, NULL AS failure_mode, NULL AS entry_intent
```
```python
    NULL AS candidate_id, NULL AS pattern_evaluation_id, NULL AS failure_mode, NULL AS entry_intent
```

Rewrite `_trade_select_cols` (`trades.py:130-149`) to detect `entry_intent` independently (FOUR eras now), composing as the existing comment discipline prescribes:

```python
def _trade_select_cols(conn: sqlite3.Connection) -> str:
    """Return the schema-era-appropriate SELECT-cols projection.

    FOUR eras (migration 0027 added a fourth):
      * v27+ (entry_intent present)  -> full projection incl. entry_intent.
      * v24-v26 (failure_mode present, entry_intent absent) -> real failure_mode
        + NULL AS entry_intent.
      * v21-v23 (candidate_id present, failure_mode absent) -> real backlinks +
        NULL AS failure_mode + NULL AS entry_intent.
      * pre-v21 (none present) -> NULL backlinks + NULL failure_mode + NULL intent.
    Detect entry_intent / failure_mode / the v21 columns INDEPENDENTLY, then
    compose. Keeps _row_to_trade positional + agnostic across all eras.
    """
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    has_v21 = "candidate_id" in cols and "pattern_evaluation_id" in cols
    if "entry_intent" in cols:   # v27 implies failure_mode + v21 columns exist
        return _TRADE_SELECT_COLS
    if "failure_mode" in cols:
        return _TRADE_SELECT_COLS_V24_TO_V26
    if has_v21:
        return _TRADE_SELECT_COLS_V21_TO_V23
    return _TRADE_SELECT_COLS_PRE_V21
```

Update `_row_to_trade` (`trades.py:508`): extend the index-map docstring with `55:entry_intent (migration 0027)` and add the kwarg after `failure_mode=row[54]` (`:581`):

```python
        failure_mode=row[54],
        entry_intent=row[55],
    )
```

- [ ] **Step 8: Repo plumbing — `insert_trade_with_event` v27+ branch + `update_entry_intent` (`swing/data/repos/trades.py`)**

`entry_intent` is set AT ENTRY (unlike `failure_mode`), so `insert_trade_with_event` needs a NEW v27+ INSERT branch. Restructure the column-presence check at `trades.py:210-213` to detect `entry_intent` and branch FIRST (the v27 branch = the v21 branch + `entry_intent`), preserving the existing v21 and legacy branches verbatim for pre-v27 DBs:

```python
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    if "entry_intent" in cols:
        # v27+ : v21 backlinks + entry_intent set-at-entry.
        cur = conn.execute(
            """
            INSERT INTO trades
                (ticker, entry_date, entry_price, initial_shares, initial_stop,
                 current_stop, state, watchlist_entry_target,
                 watchlist_initial_stop, notes, hypothesis_label,
                 chart_pattern_algo, chart_pattern_algo_confidence,
                 chart_pattern_operator,
                 chart_pattern_classification_pipeline_run_id,
                 sector, industry,
                 trade_origin, pre_trade_locked_at, current_size,
                 current_avg_cost, last_fill_at,
                 thesis, why_now, invalidation_condition, expected_scenario,
                 premortem_technical, premortem_market_sector,
                 premortem_execution, premortem_additional,
                 event_risk_present, event_handling, event_type, event_date,
                 gap_risk_present, gap_risk_handling,
                 emotional_state_pre_trade, market_regime, catalyst,
                 catalyst_other_description,
                 planned_target_R,
                 candidate_id, pattern_evaluation_id, entry_intent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?,
                    ?, ?, ?)
            """,
            (
                trade.ticker, trade.entry_date, trade.entry_price,
                trade.initial_shares, trade.initial_stop, trade.current_stop,
                trade.state,
                trade.watchlist_entry_target, trade.watchlist_initial_stop,
                trade.notes, trade.hypothesis_label,
                trade.chart_pattern_algo, trade.chart_pattern_algo_confidence,
                trade.chart_pattern_operator,
                trade.chart_pattern_classification_pipeline_run_id,
                trade.sector, trade.industry,
                trade.trade_origin, trade.pre_trade_locked_at,
                trade.current_size,
                trade.current_avg_cost, trade.last_fill_at,
                trade.thesis, trade.why_now, trade.invalidation_condition,
                trade.expected_scenario,
                trade.premortem_technical, trade.premortem_market_sector,
                trade.premortem_execution, trade.premortem_additional,
                trade.event_risk_present, trade.event_handling,
                trade.event_type, trade.event_date,
                trade.gap_risk_present, trade.gap_risk_handling,
                trade.emotional_state_pre_trade, trade.market_regime,
                trade.catalyst, trade.catalyst_other_description,
                trade.planned_target_R,
                trade.candidate_id, trade.pattern_evaluation_id,
                trade.entry_intent,
            ),
        )
    elif "candidate_id" in cols and "pattern_evaluation_id" in cols:
        # ... existing v21-v26 branch UNCHANGED ...
```

(Leave the existing `if "candidate_id" in cols and "pattern_evaluation_id" in cols:` and `else:` branches exactly as-is, just demoted to `elif`/`else` under the new `if`.)

Add the dedicated writer after `update_trade_review_fields` (`trades.py:647`), mirroring its PRAGMA-aware shape but single-column:

```python
def update_entry_intent(
    conn: sqlite3.Connection, *, trade_id: int, entry_intent: str | None,
) -> None:
    """UPDATE trades.entry_intent ONLY. Caller wraps in `with conn:`.

    The dedicated review-time-correction + backfill writer (spec §4.4). Touches
    NO review field and does NOT transition state -- entry_intent is an entry
    attribute, independent of review state (SKYT id 15 is closed-not-reviewed
    yet carries a deliberate intent). Kept separate from the 11-field
    update_trade_review_fields to preserve that writer's focus.

    PRAGMA-aware: a non-None entry_intent against a pre-v27 schema raises a clean
    ValueError (NOT a leaked OperationalError). Validates against ENTRY_INTENTS
    (Literal is not runtime-enforced). `... or None` nullability respected by the
    caller; NULL is a legal value (the backfill `skip` path). Missing trade_id
    raises ValueError.
    """
    from swing.data.models import ENTRY_INTENTS

    if entry_intent is not None and entry_intent not in ENTRY_INTENTS:
        raise ValueError(
            f"entry_intent must be one of {sorted(ENTRY_INTENTS)} or None, "
            f"got {entry_intent!r}")
    has_col = "entry_intent" in {
        r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
    }
    if entry_intent is not None and not has_col:
        raise ValueError(
            "entry_intent requires schema v27+ (the trades.entry_intent column "
            "is absent on this DB)")
    if not has_col:
        # pre-v27 + entry_intent is None -> no-op write target; still verify the
        # row exists so the contract (missing -> ValueError) holds.
        cur = conn.execute("SELECT 1 FROM trades WHERE id = ?", (trade_id,))
        if cur.fetchone() is None:
            raise ValueError(f"trade {trade_id} not found")
        return
    cur = conn.execute(
        "UPDATE trades SET entry_intent = ? WHERE id = ?", (entry_intent, trade_id))
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} not found")
```

- [ ] **Step 9: Schema-version-pin sweep (26 → 27)**

`feedback_regression_test_arithmetic`: every literal that tracks HEAD (`EXPECTED_SCHEMA_VERSION`, or an `ensure_schema`/HEAD-walk-derived `version`/`row[0]`) asserts `26` today and must become `27`; every literal pinned via an explicit `run_migrations(target_version=N<27)` STAYS. **Unlike the 0026 arc, there is NO hypothesis-count (4→5) sweep — 0027 adds a trades COLUMN, not a registry row; cohort counts and tab counts are UNCHANGED.** Stale test/comment/function names are preserved per repo convention (`stale-name-but-current-assertion`); only the asserted value changes.

`EXPECTED_SCHEMA_VERSION == 26` → `== 27`:
- `tests/data/test_b7_failure_mode_schema.py:45`
- `tests/data/test_db_v8.py:113`
- `tests/data/test_migration_0012.py:38`
- `tests/data/test_migration_0015_finviz_api_calls.py:59`
- `tests/data/test_migration_0017.py:44`
- `tests/data/test_migration_0018.py:65`
- `tests/data/test_migration_0019_atomic_apply.py:65`
- `tests/data/test_migration_0025_phase16.py:29`
- `tests/data/test_migration_0026_broad_watch_baseline.py:26` (and rename the function `test_expected_schema_version_is_26` → `_is_27` for clarity; this is the 0026 migration's OWN head-pin — its other assertions stay, see STAY list)
- `tests/data/test_no_schema_change_v3.py:15`
- `tests/data/test_phase13_t3_sb1_prerequisite.py:54`
- `tests/data/test_temporal_log_migration.py:30`
- `tests/data/test_v20_migration.py:236`
- `tests/data/test_v21_migration_trade_backlinks.py:722`
- `tests/data/test_v23_migration.py:115`

Head-tracking `version`/`row[0]`/`post`/`ver[0]`/`cur.fetchone()[0]` reached via `ensure_schema` (→ HEAD): `26` → `27`:
- `tests/data/test_migration_0010_trade_chart_pattern.py:18`
- `tests/data/test_migration_0013.py:27`
- `tests/data/test_migration_0015_finviz_api_calls.py:18` (stale "v24" message — preserve, bump value)
- `tests/data/test_migration_0016.py:38`
- `tests/data/test_migration_0017.py:49`
- `tests/data/test_migration_0018.py:70`
- `tests/data/test_migration_0019_atomic_apply.py:70` and `:86`
- `tests/data/test_phase13_t3_sb1_prerequisite.py:199` (`version == EXPECTED_SCHEMA_VERSION == 26` → `== 27`)
- `tests/data/test_v20_migration.py:233` and `:833`
- `tests/data/test_v21_migration_trade_backlinks.py:787` (stale "!= 24" message — preserve, bump value)

Engine testkit (builds fixtures at HEAD; the trades.entry_intent column rides along): `tests/research/shadow_expectancy/testkit.py:13` `target_version=26` → `27`.

**STAY (migration-pinned via explicit `run_migrations(target_version=N<27)`, or testing a specific lower migration — do NOT touch):**
- `tests/data/test_migration_0018.py:451,482,529,538`; `tests/data/test_migration_0019_atomic_apply.py:216,249`.
- `tests/data/test_temporal_log_migration.py` (all `target_version=21/22`); `tests/data/test_v23_migration.py` (all `target_version=21/22/23`).
- `tests/data/test_migration_0026_broad_watch_baseline.py`: ALL except `:26` — `test_migrate_to_26_*` / `test_backup_gate_fires_strict_on_v25` / `test_run_migrations_wires_broad_watch_gate` are `target=26`-pinned (`apply_ceiling = min(26, 27) = 26`, still stops at 26) and STAY.
- `tests/data/test_migration_0025_phase16.py`: `:66-113` (the phase16-gate tests use `target_version=26` crossing v25; `apply_ceiling = min(26, 27) = 26` — unchanged behavior; `:111 == 26` STAYS, its comment "ceiling now equals the target (v26)" is still TRUE since `min(26,27)=26=target`). Only `:29` bumps.
- `tests/research/minervini_exemplar_recall/test_timing.py:40` (`len(sessions) == 26` — coincidental, NOT a schema pin).

- [ ] **Step 10: Run the migration test (PASS), then the predicted-RED sweep run to confirm exhaustiveness**

Run: `python -m pytest tests/data/test_migration_0027_entry_intent.py -q` → Expected: PASS.

Run (BEFORE editing the Step-9 files, to capture the predicted red): `python -m pytest tests/data tests/research/shadow_expectancy -q`
Expected: the version-pin assertions fail. **Any failure NOT in the Step-9 lists must be triaged with the head-tracking-vs-pinned rule and added.** Then apply Step 9 and re-run:

Run: `python -m pytest tests/data tests/research/shadow_expectancy -q` → Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add swing/data/migrations/0027_entry_intent.sql swing/data/models.py \
  swing/data/repos/trades.py swing/data/db.py \
  tests/data/test_migration_0027_entry_intent.py tests/data tests/research/shadow_expectancy/testkit.py
git commit -m "feat(data): migration 0027 entry_intent column + model/repo plumbing + v27 gate"
```

---

## Task 2: `swing/trades/intent.py` — pure presentation + prefill module

Spec §4.1 + §5. Pure, no I/O; imports `ENTRY_INTENTS` from `swing.data.models` (downward, no cycle). Fully testable standalone — green immediately after Task 1.

**Files:**
- Create: `swing/trades/intent.py`, `tests/trades/test_intent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/trades/test_intent.py`:

```python
from __future__ import annotations

import pytest

from swing.data.models import ENTRY_INTENTS
from swing.trades.intent import (
    ENTRY_INTENT_DISPLAY,
    entry_intent_display_choices,
    entry_intent_label,
    suggest_entry_intent,
)


def test_display_matches_constant_no_drift():
    assert {v for v, _ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS


def test_display_choices_is_the_ordered_tuple():
    assert entry_intent_display_choices() == ENTRY_INTENT_DISPLAY
    assert ENTRY_INTENT_DISPLAY[0][0] == "standard"


def test_label_maps_and_passes_through():
    assert entry_intent_label("standard") == "Standard entry"
    assert entry_intent_label("hypothesis_test_by_design") == "Hypothesis test (by design)"
    assert entry_intent_label(None) is None
    assert entry_intent_label("weird") == "weird"   # unknown -> itself


@pytest.mark.parametrize("label,expected", [
    # standard family (spec §5.1)
    ("A+ baseline (aplus)", "standard"),
    ("aplus", "standard"),
    ("Capital-blocked: smaller-position test", "standard"),
    ("Broad-watch baseline (watch); failed: adr", "standard"),
    # by-design family
    ("Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness",
     "hypothesis_test_by_design"),
    ("Near-A+ defensible: extension test (watch); failed: proximity_20ma",
     "hypothesis_test_by_design"),
    ("DHC sub-A+ VCP-not-formed test", "hypothesis_test_by_design"),
    # no confident suggestion (spec §1 note + §5.1 last row)
    ("inaugural trade test", None),     # VIR id 1
    (None, None),                       # VSAT / PTEN NULL labels
    ("", None),
    ("   ", None),
    ("totally unknown manual label", None),
])
def test_suggest_entry_intent_table(label, expected):
    assert suggest_entry_intent(label) == expected


def test_suggest_is_case_insensitive():
    assert suggest_entry_intent("APLUS BASELINE") == "standard"
    assert suggest_entry_intent("SUB-A+ vcp-not-formed") == "hypothesis_test_by_design"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/trades/test_intent.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.trades.intent'`.

- [ ] **Step 3: Create the module**

Create `swing/trades/intent.py`:

```python
"""Tuition-vs-error instrument: entry_intent presentation + advisory prefill.

PURE (no I/O). The schema-CHECK enum ENTRY_INTENTS lives in swing.data.models
(the schema-enum home, to avoid an upward import); this module imports it
downward and owns the display/advisory helpers. NEVER consulted by the
service/persist layer for the stored value -- suggest_entry_intent only seeds
the visible form control's default (spec §5: THE SINGLE PREFILL RULE).
"""
from __future__ import annotations

from swing.data.models import ENTRY_INTENTS

# Ordered (value, label) for the form <select> + display (mirrors
# review.FAILURE_MODE_DISPLAY). ASCII-only labels (#16 cp1252 stdout + parity).
# A frozenset has NO iteration-order guarantee -- forms/labels iterate THIS
# tuple, never ENTRY_INTENTS directly. The no-drift test asserts
# {v for v,_ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS.
ENTRY_INTENT_DISPLAY: tuple[tuple[str, str], ...] = (
    ("standard", "Standard entry"),
    ("hypothesis_test_by_design", "Hypothesis test (by design)"),
)

_ENTRY_INTENT_LABELS: dict[str, str] = dict(ENTRY_INTENT_DISPLAY)


def entry_intent_display_choices() -> tuple[tuple[str, str], ...]:
    """Ordered (value, label) pairs for the form <select> + VM."""
    return ENTRY_INTENT_DISPLAY


def entry_intent_label(value: str | None) -> str | None:
    """Map a stored token to its display label; None -> None; unknown -> itself."""
    if value is None:
        return None
    return _ENTRY_INTENT_LABELS.get(value, value)


def suggest_entry_intent(hypothesis_label: str | None) -> str | None:
    """Advisory default ONLY (spec §5) -- seeds the visible form control; never
    read by the service/persist layer and never consults the matcher/registry.

    Keyword match on the lowercased label (spec §5.1). Order matters: the
    'standard' families are tested before the by-design families so an explicit
    A+/capital-blocked/broad-watch label never falls through to a by-design
    keyword. No keyword match (manual / 'inaugural trade test' / NULL) -> None.
    """
    if hypothesis_label is None:
        return None
    text = hypothesis_label.strip().lower()
    if not text:
        return None
    standard_keywords = ("a+ baseline", "aplus", "capital-blocked", "broad-watch baseline")
    if any(kw in text for kw in standard_keywords):
        return "standard"
    by_design_keywords = ("sub-a+", "vcp-not-formed", "near-a+", "extension test")
    if any(kw in text for kw in by_design_keywords):
        return "hypothesis_test_by_design"
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/trades/test_intent.py -q` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/intent.py tests/trades/test_intent.py
git commit -m "feat(trades): entry_intent presentation + advisory prefill module"
```

---

## Task 3: Set-at-entry surfaces (EntryRequest/record_entry + web entry form + CLI entry)

Spec §5.2 + §7.3 + §8. The persisted value is ALWAYS the explicit submitted control (web) or flag (CLI) — the service NEVER derives it from the label (spec §5 SINGLE PREFILL RULE).

**Files:**
- Modify: `swing/trades/entry.py`, `swing/web/routes/trades.py`, `swing/web/view_models/trades.py`, `swing/web/templates/partials/trade_entry_form.html.j2`, `swing/cli.py`
- Test: `tests/trades/test_entry.py` (or the existing entry test module), `tests/web/test_routes/test_trades_entry.py`, `tests/cli/test_cli_trade.py` (match existing filenames)

- [ ] **Step 1: Write failing service + web + CLI tests**

Add to the entry service test module:

```python
def test_entry_request_validates_entry_intent():
    import pytest
    from swing.trades.entry import EntryRequest
    with pytest.raises(ValueError, match="entry_intent"):
        EntryRequest(
            ticker="AAA", entry_date="2026-05-01", entry_price=10.0, shares=1,
            initial_stop=9.0, watchlist_entry_target=None,
            watchlist_initial_stop=None, notes=None, rationale="r",
            event_ts="2026-05-01T00:00:00", entry_intent="foo")


def test_record_entry_persists_entry_intent(tmp_path):
    # Build a v27 DB, record an entry with entry_intent='standard', read back.
    conn = _v27_conn(tmp_path)   # helper migrates to 27 (mirror existing fixtures)
    req = _minimal_entry_request(entry_intent="standard")  # existing builder + new kwarg
    result = record_entry(conn, req, soft_warn=99, hard_cap=99, force=False)
    trade = get_trade(conn, result.trade_id)
    assert trade.entry_intent == "standard"


def test_record_entry_omitted_intent_persists_null(tmp_path):
    conn = _v27_conn(tmp_path)
    req = _minimal_entry_request()   # no entry_intent -> default None
    result = record_entry(conn, req, soft_warn=99, hard_cap=99, force=False)
    assert get_trade(conn, result.trade_id).entry_intent is None
```

Web entry POST test (server-stamp + empty→NULL + soft-warn round-trip):

```python
def test_entry_post_persists_selected_intent(client_v27):
    resp = client_v27.post("/trades/entry", data={**_valid_entry_form(),
                                                  "entry_intent": "hypothesis_test_by_design"})
    assert resp.status_code in (204, 200)
    # assert the persisted trade carries the value (read via repo/get_trade)


def test_entry_post_empty_intent_persists_null(client_v27):
    resp = client_v27.post("/trades/entry", data={**_valid_entry_form(),
                                                  "entry_intent": ""})
    # persisted entry_intent IS NULL, not "" (the ... or None gotcha)


def test_entry_softwarn_roundtrips_intent(client_v27):
    # A submission that trips the soft-warn / missing-fields re-render must
    # re-render the <select> pre-selected to the SUBMITTED intent (draft_entry_intent),
    # not the suggestion -- so a force=true resubmit keeps it.
    resp = client_v27.post("/trades/entry", data={**_entry_form_missing_required(),
                                                  "entry_intent": "standard"})
    assert 'value="standard"' in resp.text and "selected" in resp.text
```

CLI entry test:

```python
def test_cli_entry_intent_flag_persists(...):
    # `swing trade entry ... --entry-intent standard` -> persisted standard.

def test_cli_entry_omitted_intent_is_null(...):
    # no --entry-intent -> NULL (advisory suggestion NOT auto-applied).

def test_cli_entry_bad_intent_raises_clickexception(...):
    # --entry-intent foo -> click.Choice rejects (exit code 2) OR ClickException.
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/trades/test_entry.py tests/web/test_routes/test_trades_entry.py tests/cli/test_cli_trade.py -k entry_intent -q`
Expected: FAIL — `EntryRequest` has no `entry_intent`; the form/CLI ignore it.

- [ ] **Step 3: Add `entry_intent` to `EntryRequest` + thread through `record_entry`**

In `swing/trades/entry.py`, add the field to `EntryRequest` (after `candidate_id` at `:174`):

```python
    # Tuition-vs-error instrument (spec §7.3). Operator's explicit design-intent
    # selection at entry; default None -> NULL (omitted CLI flag / unselected form).
    # Validated against ENTRY_INTENTS; NEVER derived from hypothesis_label.
    entry_intent: str | None = None
```

Add a `__post_init__` validation to `EntryRequest` (it currently has none — add one), OR validate inside `record_entry` before constructing `Trade`. Prefer the dataclass validator for symmetry with `Trade`:

```python
    def __post_init__(self) -> None:
        from swing.data.models import ENTRY_INTENTS
        if self.entry_intent is not None and self.entry_intent not in ENTRY_INTENTS:
            raise ValueError(
                f"EntryRequest.entry_intent must be None or one of "
                f"{sorted(ENTRY_INTENTS)}; got {self.entry_intent!r}")
```

In the `Trade(...)` construction (`entry.py:352-407`), add the kwarg (after `pattern_evaluation_id=req.pattern_evaluation_id,`):

```python
        # Tuition-vs-error: persisted AS-IS from the operator's explicit choice
        # (server-stamp); NEVER suggested from the label here (spec §5).
        entry_intent=req.entry_intent,
```

- [ ] **Step 4: Web entry form — VM choices/suggestion, GET render, POST server-stamp + soft-warn round-trip**

In `swing/web/view_models/trades.py`, add to `EntryFormVM` (after `hypothesis_label` `:287` and alongside the `draft_*` block):

```python
    entry_intent_choices: tuple[tuple[str, str], ...] = ()
    suggested_entry_intent: str | None = None   # seed for the <select> default (fresh GET)
    # Soft-warn round-trip. None = "no draft (fresh GET)" -> use the suggestion;
    # "" = "operator explicitly chose Unclassified on a submit" -> KEEP "" (do NOT
    # fall back to the suggestion). A bare str default of "" would conflate the two
    # and silently re-suggest on a force resubmit (Codex R1-Major-1: NULL != standard).
    draft_entry_intent: str | None = None
```

In `build_entry_form_vm` (`:383`), populate `entry_intent_choices=entry_intent_display_choices()` and `suggested_entry_intent=suggest_entry_intent(resolved_hypothesis_label)` (import both from `swing.trades.intent`; `resolved_hypothesis_label` is computed at `:542/:793`). Leave `draft_entry_intent` at its `None` default on the fresh-GET path.

In `swing/web/templates/partials/trade_entry_form.html.j2`, add an intent `<select>` near the hypothesis-label control. The selection is the draft when a draft exists (incl. explicit `""`), else the suggestion — `is not none` is the discriminator, NOT truthiness:

```jinja2
{% set selected_intent = vm.draft_entry_intent if vm.draft_entry_intent is not none else vm.suggested_entry_intent %}
<label for="entry_intent">Design intent
  <select id="entry_intent" name="entry_intent">
    <option value=""{% if not selected_intent %} selected{% endif %}>(unclassified)</option>
    {% for value, label in vm.entry_intent_choices %}
    <option value="{{ value }}"{% if selected_intent == value %} selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
</label>
```

In `swing/web/routes/trades.py` `entry_post` (`:~448`): add `entry_intent: str = Form("")` to the signature; in the `EntryRequest(...)` construction (`:~1251`) add `entry_intent=entry_intent or None` (the `... or None` nullability gotcha — server-stamp, never a trusted hidden input). In the `MissingPreTradeFieldsException` soft-warn re-render (`:~1334-1373`), pass `draft_entry_intent=entry_intent` (the submitted string verbatim, possibly `""`) into the `build_entry_form_vm`/`dc_replace` so an explicit Unclassified survives the force resubmit and a suggested-but-changed value is not re-suggested (mirror the existing `draft_*` preservation for the 18 pre-trade fields). Add a test asserting an explicit `entry_intent=""` submission that trips the soft-warn re-renders the `(unclassified)` option `selected` (NOT the suggestion) for a trade whose label HAS a suggestion.

- [ ] **Step 5: CLI entry — `--entry-intent` option (advisory NOT auto-applied)**

In `swing/cli.py` `trade_entry_cmd` (`:589`), add after the `--hypothesis` option:

```python
@click.option("--entry-intent", "entry_intent",
              type=click.Choice(["standard", "hypothesis_test_by_design"]),
              default=None,
              help="Design intent for this entry (advisory suggestion shown in "
                   "the web form is NOT auto-applied here). Omit -> unclassified "
                   "(NULL); pass a value to set it.")
```

Add `entry_intent` to the `def trade_entry_cmd(...)` parameter list and to the `EntryRequest(...)` construction (`:811-848`): `entry_intent=entry_intent` (already None when omitted). The `click.Choice` rejects bad values with exit 2; the `EntryRequest`/`Trade` validators are the belt.

- [ ] **Step 6: Run to verify PASS + no regression**

Run: `python -m pytest tests/trades/test_entry.py tests/web/test_routes/test_trades_entry.py tests/cli/test_cli_trade.py -q` → Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/trades/entry.py swing/web/routes/trades.py swing/web/view_models/trades.py \
  swing/web/templates/partials/trade_entry_form.html.j2 swing/cli.py \
  tests/trades/test_entry.py tests/web/test_routes/test_trades_entry.py tests/cli/test_cli_trade.py
git commit -m "feat(trades): set entry_intent at entry (web form + CLI, server-stamped)"
```

---

## Task 4: Correct-at-review surfaces (web review form + VM + CLI review correction)

Spec §5.2 + §7.3 (D5) + §8. The review form pre-populates the PERSISTED value (NULL → suggestion default); the POST persists via the dedicated `update_entry_intent` (separate from `complete_trade_review`'s field write; same request), server-stamped, with the 4-tier rejection ladder.

**Files:**
- Modify: `swing/web/routes/trades.py`, `swing/web/view_models/trades.py`, `swing/web/templates/partials/review_form.html.j2`, `swing/cli.py`
- Test: `tests/web/test_routes/test_trades_review.py`, `tests/cli/test_cli_trade.py`

- [ ] **Step 1: Write failing tests**

```python
def test_review_form_prepopulates_persisted_intent(client_v27):
    # A trade with persisted entry_intent='standard' -> <select> pre-selected standard.

def test_review_form_null_intent_falls_back_to_suggestion(client_v27):
    # A reviewed-eligible trade with NULL entry_intent + a by-design label ->
    # <select> default = suggestion (hypothesis_test_by_design).

def test_review_post_persists_intent_via_update_entry_intent(client_v27):
    # POST review with entry_intent='standard' -> persisted; review fields/state
    # also transition (closed->reviewed) via complete_trade_review, intent via the
    # dedicated writer. Assert entry_intent persisted AND grades persisted.

def test_review_post_empty_intent_persists_null(client_v27):
    # entry_intent="" -> NULL (... or None), NOT "".

def test_review_post_bad_intent_rejected_400_and_clears(client_v27):
    # entry_intent="foo" -> 400 + re-rendered review form; bad anchor cleared.

def test_cli_review_intent_corrects(...):
    # `swing trade review --trade-id N --entry-intent standard ...` -> persisted.

def test_cli_review_omitted_intent_leaves_persisted(...):
    # No --entry-intent -> the previously-persisted value is unchanged.
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/web/test_routes/test_trades_review.py tests/cli/test_cli_trade.py -k intent -q` → Expected: FAIL.

- [ ] **Step 3: Review VM — choices + pre-populated selection**

In `swing/web/view_models/trades.py` `ReviewVM` (`:1140`, alongside `failure_mode_choices` `:1158`):

```python
    entry_intent_choices: tuple[tuple[str, str], ...] = ()
    entry_intent_selected: str | None = None   # persisted value, else suggestion
```

In `build_review_vm` (`:1232`): set `entry_intent_choices=entry_intent_display_choices()` and `entry_intent_selected=(trade.entry_intent if trade.entry_intent is not None else suggest_entry_intent(trade.hypothesis_label))` (import from `swing.trades.intent`).

- [ ] **Step 4: Review template — intent `<select>`**

In `swing/web/templates/partials/review_form.html.j2`, mirror the `failure_mode` `<select>` block with an `entry_intent` control pre-selected to `vm.entry_intent_selected` (and an `(unclassified)` empty option).

- [ ] **Step 5: Review POST — server-stamp + 4-tier ladder + dedicated writer**

In `swing/web/routes/trades.py` `review_post` (`:2669`): add `entry_intent: str | None = Form(None)` to the signature. After the existing `failure_mode` validation (`:2754-2766`), add the intent ladder (malformed/non-member → 400 + re-render with the bad anchor CLEARED; empty → NULL):

```python
    from swing.data.models import ENTRY_INTENTS
    ei = entry_intent or None   # ... or None: empty -> NULL (nullable CHECK)
    if ei is not None and ei not in ENTRY_INTENTS:
        from swing.web.view_models.trades import build_review_vm
        vm = build_review_vm(trade_id=trade_id, cfg=cfg)
        msg = f"Invalid entry_intent {ei!r}"
        if vm is None:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": msg}, status_code=400)
        return templates.TemplateResponse(
            request, "partials/review_form.html.j2",
            {"vm": vm, "error_message": msg}, status_code=400)
```

After the `complete_trade_review(...)` call (`:2799-2812`), persist the intent via the dedicated writer in its OWN transaction (intent is independent of review state; do NOT widen `complete_trade_review`):

```python
        from swing.data.repos.trades import update_entry_intent
        with conn:
            update_entry_intent(conn, trade_id=trade_id, entry_intent=ei)
```

(The success response stays `204` + `HX-Redirect: /reviews/pending`.)

- [ ] **Step 6: CLI review — `--entry-intent` correction (omitted leaves persisted)**

In `swing/cli.py` `trade_review_cmd` (`:1328`), add after `--failure-mode`:

```python
@click.option("--entry-intent", "entry_intent",
              type=click.Choice(["standard", "hypothesis_test_by_design"]),
              default=None,
              help="Optional correction of the trade's design intent. Omit to "
                   "leave the persisted value unchanged; pass a value to set it.")
```

Add `entry_intent` to the param list. After the `complete_trade_review(...)` block (`:1455-1497`), when `entry_intent is not None`, call the dedicated writer with a `ClickException` wrap (spec §8):

```python
        if entry_intent is not None:
            try:
                with conn:
                    update_entry_intent(conn, trade_id=trade_id, entry_intent=entry_intent)
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc
```

(Omitted `--entry-intent` → no call → persisted value untouched. ASCII-only echo.)

- [ ] **Step 7: Run PASS + commit**

Run: `python -m pytest tests/web/test_routes/test_trades_review.py tests/cli/test_cli_trade.py -q` → Expected: PASS.

```bash
git add swing/web/routes/trades.py swing/web/view_models/trades.py \
  swing/web/templates/partials/review_form.html.j2 swing/cli.py \
  tests/web/test_routes/test_trades_review.py tests/cli/test_cli_trade.py
git commit -m "feat(trades): correct entry_intent at review (web + CLI, dedicated writer)"
```

---

## Task 5: Backfill CLI — `swing trade backfill-intent`

Spec §6 (D3). Walks ALL trades with `entry_intent IS NULL` (every state, incl. closed-not-reviewed like SKYT id 15); idempotent; `--trade-id`/`--force` re-target; per-trade prompt with the suggestion as default; `skip` → leaves NULL; writes via `update_entry_intent`; summary-as-audit; ASCII; `ClickException` wrapping.

**Files:**
- Modify: `swing/cli.py`
- Test: `tests/cli/test_backfill_intent_cli.py` (incl. the subprocess-through-PowerShell encoding test)

- [ ] **Step 1: Write failing tests**

```python
def test_backfill_sets_null_rows_idempotently(v27_db_with_unclassified_trades):
    # First run: prompts each NULL-intent trade; operator answers -> set.
    # Second run: no NULL rows remain -> "0 set" (idempotent).

def test_backfill_skip_leaves_null(...):
    # Answering 'skip' leaves entry_intent NULL; row re-appears on a later run.

def test_backfill_trade_id_retargets_single(...):
    # --trade-id N re-prompts ONLY trade N even if already set.

def test_backfill_force_reprompts_set_rows(...):
    # --force re-prompts already-set rows (the correction path).

def test_backfill_summary_counts(...):
    # Final line: "N set, N skipped-already-set, N skipped-by-operator".

def test_backfill_bad_input_raises_clickexception(...):
    # An invalid typed choice (not standard/hypothesis_test_by_design/skip) ->
    # ClickException (or re-prompt), never a traceback.

def test_backfill_subprocess_ascii_stdout():
    # Run `swing trade backfill-intent` through PowerShell with non-ASCII-free
    # output asserted (cp1252-safe; the capsys-bypass discipline, gotcha #16).
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/cli/test_backfill_intent_cli.py -q` → Expected: FAIL — `No such command 'backfill-intent'`.

- [ ] **Step 3: Implement the command**

In `swing/cli.py`, add to the `trade` group (`:584`):

```python
@trade_group.command("backfill-intent")
@click.option("--trade-id", type=int, default=None,
              help="Re-target a single trade (re-prompts even if already set).")
@click.option("--force", is_flag=True,
              help="Re-prompt trades whose entry_intent is already set (correction).")
@click.pass_context
def trade_backfill_intent_cmd(ctx, trade_id, force):
    """Classify each trade's design intent (entry_intent). Idempotent: already-set
    rows are skipped unless --trade-id or --force. 'skip' leaves a row NULL
    (renders 'Unclassified'). The re-runnable command + its summary ARE the audit
    (no provenance table for V1)."""
    from swing.trades.intent import entry_intent_label, suggest_entry_intent
    from swing.data.repos.trades import update_entry_intent
    cfg = apply_overrides(ctx.obj["cfg"])
    conn = connect(cfg.paths.db_path)
    n_set = n_skipped_set = n_skipped_op = 0
    try:
        # Select target trades: by id, or all rows; the IS-NULL/--force gate is
        # applied per-row so the summary counts are exact.
        if trade_id is not None:
            rows = conn.execute(
                "SELECT id, ticker, entry_date, hypothesis_label, process_grade, "
                "mistake_tags, entry_intent FROM trades WHERE id = ?",
                (trade_id,)).fetchall()
            if not rows:
                raise click.ClickException(f"trade {trade_id} not found")
        else:
            rows = conn.execute(
                "SELECT id, ticker, entry_date, hypothesis_label, process_grade, "
                "mistake_tags, entry_intent FROM trades "
                "ORDER BY entry_date, ticker, id").fetchall()
        for tid, ticker, edate, hyp, pg, tags, current in rows:
            already_set = current is not None
            if already_set and trade_id is None and not force:
                n_skipped_set += 1
                continue
            suggestion = suggest_entry_intent(hyp)
            sug_label = entry_intent_label(suggestion) or "(no suggestion)"
            click.echo(f"#{tid} {ticker} {edate} | label={hyp or '(none)'} | "
                       f"grade={pg or '-'} | tags={tags or '-'} | "
                       f"current={current or 'NULL'} | suggested={sug_label}")
            choice = click.prompt(
                "  intent [standard / hypothesis_test_by_design / skip]",
                default=(suggestion or "skip"), show_default=True).strip()
            if choice in ("skip", ""):
                n_skipped_op += 1
                continue
            try:
                with conn:
                    update_entry_intent(conn, trade_id=tid, entry_intent=choice)
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc
            n_set += 1
        click.echo(f"{n_set} set, {n_skipped_set} skipped-already-set, "
                   f"{n_skipped_op} skipped-by-operator")
    finally:
        conn.close()
```

(The `update_entry_intent` ValueError-on-bad-choice is wrapped as `ClickException`; ASCII-only output; the `default=` shows the suggestion so the operator can accept with Enter.)

- [ ] **Step 4: Run PASS + commit**

Run: `python -m pytest tests/cli/test_backfill_intent_cli.py -q` → Expected: PASS.

```bash
git add swing/cli.py tests/cli/test_backfill_intent_cli.py
git commit -m "feat(cli): swing trade backfill-intent walk (idempotent, auditable)"
```

---

## Task 6: Faceted trade-process surfaces + the always-on execution-discipline panel

Spec §7.1 (the core fix) + §3 corollary 1 + §10. `cohort.py` gains an `entry_intent` predicate; `compute_trade_process_metrics` gains an intent filter param + two new result fields for the **always-on cross-intent execution-discipline panel** (the orthogonality guarantee); the card VM/template/route surface the facet on the "All" aggregate (D6).

**Files:**
- Modify: `swing/metrics/cohort.py`, `swing/metrics/process.py`, `swing/web/view_models/metrics/trade_process_card.py`, `swing/web/templates/metrics/trade_process_card.html.j2`, `swing/web/routes/metrics.py`
- Test: `tests/metrics/test_cohort.py`, `tests/metrics/test_process.py` (or the existing process-metrics test module), `tests/metrics/test_execution_discipline_panel.py` (NEW — orthogonality), `tests/web/test_view_models/test_trade_process_card_vm.py`, `tests/web/test_routes/test_metrics_routes.py`

- [ ] **Step 1: Write the failing cohort + faceting + panel tests**

`tests/metrics/test_cohort.py` (predicate):

```python
def test_list_closed_trades_for_cohort_intent_predicate(v27_conn_mixed_intents):
    # fixture: closed trades with entry_intent in {standard, by_design, NULL}.
    std = list_closed_trades_for_cohort(conn, hypothesis_label=None, entry_intent="standard")
    assert {t.entry_intent for t in std} == {"standard"}
    unc = list_closed_trades_for_cohort(conn, hypothesis_label=None, entry_intent="__unclassified__")
    assert all(t.entry_intent is None for t in unc)
    nofilter = list_closed_trades_for_cohort(conn, hypothesis_label=None)
    assert len(nofilter) >= len(std)   # no-filter == today's behavior
```

`tests/metrics/test_process.py` (faceting; regression-arithmetic — distinguish filtered vs unfiltered):

```python
def test_compute_trade_process_metrics_intent_filter(v27_conn_mixed_intents):
    # fixture: 2 standard closed-reviewed + 3 by_design closed-reviewed + 1 NULL.
    all_m = compute_trade_process_metrics(conn, hypothesis_label=None)
    std_m = compute_trade_process_metrics(conn, hypothesis_label=None, entry_intent="standard")
    bd_m  = compute_trade_process_metrics(conn, hypothesis_label=None,
                                          entry_intent="hypothesis_test_by_design")
    unc_m = compute_trade_process_metrics(conn, hypothesis_label=None, entry_intent="__unclassified__")
    # Pre/post arithmetic: all_m.n_reviewed == 5; std_m.n_reviewed == 2;
    # bd_m.n_reviewed == 3; unc_m.n_reviewed == 0 (NULL row not reviewed in fixture).
    assert all_m.n_reviewed == 5
    assert std_m.n_reviewed == 2
    assert bd_m.n_reviewed == 3
    # mistake_tag_frequency reflects only the filtered cohort's tags.
    assert set(std_m.mistake_tag_frequency).isdisjoint(_only_in_by_design_tags)
    # no-filter equals today's behavior (same as omitting the param).
    assert all_m.n_reviewed == compute_trade_process_metrics(conn, hypothesis_label=None).n_reviewed
```

`tests/metrics/test_execution_discipline_panel.py` (NEW — the orthogonality guarantee):

```python
def test_execution_discipline_panel_is_intent_independent(v27_conn_vir_like):
    # fixture: a by_design VIR-like trade carrying NO_STOP + STOP_NOT_PLACED,
    # plus standard trades carrying CHASED (an entry-category tuition tag).
    base = compute_trade_process_metrics(conn, hypothesis_label=None)
    std  = compute_trade_process_metrics(conn, hypothesis_label=None, entry_intent="standard")
    bd   = compute_trade_process_metrics(conn, hypothesis_label=None,
                                         entry_intent="hypothesis_test_by_design")
    # The panel + its denominator are IDENTICAL across every filter state.
    for m in (std, bd):
        assert m.execution_discipline_n_reviewed == base.execution_discipline_n_reviewed
        assert set(m.execution_discipline_tag_frequency) == set(base.execution_discipline_tag_frequency)
        for tag, cell in base.execution_discipline_tag_frequency.items():
            assert m.execution_discipline_tag_frequency[tag].sample_n == cell.sample_n
            assert m.execution_discipline_tag_frequency[tag].events_k == cell.events_k
    # the slip is present...
    assert "NO_STOP" in base.execution_discipline_tag_frequency
    assert "STOP_NOT_PLACED" in base.execution_discipline_tag_frequency
    # ...and the tuition entry-tag is NOT (panel lists only risk/reconciliation).
    assert "CHASED" not in base.execution_discipline_tag_frequency
    # the panel denominator is the intent-UNFILTERED reviewed count, NOT n_reviewed.
    assert base.execution_discipline_n_reviewed == base.n_reviewed   # no filter -> equal
    assert std.execution_discipline_n_reviewed >= std.n_reviewed     # filter shrinks n_reviewed only
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/metrics/test_cohort.py tests/metrics/test_process.py tests/metrics/test_execution_discipline_panel.py -k "intent or discipline" -q`
Expected: FAIL — no `entry_intent` param; no `execution_discipline_*` fields.

- [ ] **Step 3: `cohort.py` predicate**

In `swing/metrics/cohort.py`, add an `entry_intent` param to `list_trades_for_cohort` (`:32`) and `list_closed_trades_for_cohort` (`:84`). Convention: `None` = no predicate (today's behavior); `'__unclassified__'` = `entry_intent IS NULL`; a member value = `entry_intent = ?`. Add to the WHERE composition (after the `state_filter` block):

```python
def list_trades_for_cohort(
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
    state_filter: tuple[str, ...] | None = None,
    entry_intent: str | None = None,
) -> list[Trade]:
    ...
    if entry_intent is not None:
        if entry_intent == "__unclassified__":
            where_clauses.append("entry_intent IS NULL")
        else:
            where_clauses.append("entry_intent = ?")
            params.append(entry_intent)
```

```python
def list_closed_trades_for_cohort(
    conn: sqlite3.Connection, *, hypothesis_label: str | None,
    entry_intent: str | None = None,
) -> list[Trade]:
    return list_trades_for_cohort(
        conn, hypothesis_label=hypothesis_label,
        state_filter=("closed", "reviewed"), entry_intent=entry_intent,
    )
```

- [ ] **Step 4: `process.py` — filter param + the discipline panel + result fields**

In `swing/metrics/process.py`, add the execution-discipline tag-set constant near the top (derived from `MISTAKE_TAGS` to avoid drift):

```python
from swing.trades.review import MISTAKE_TAGS

# Execution-discipline panel tag set (spec §7.1): risk + reconciliation
# categories ONLY (genuine slips). Derived from MISTAKE_TAGS so it never drifts
# from the vocabulary; entry-category tuition tags (CHASED/NO_SETUP) are excluded.
_EXECUTION_DISCIPLINE_TAGS: frozenset[str] = (
    frozenset(MISTAKE_TAGS["risk"]) | frozenset(MISTAKE_TAGS["reconciliation"])
)
```

Add the two fields to `TradeProcessMetricsResult` (after `mistake_tag_frequency` `:455`), with defaults so positional/keyword construction stays valid:

```python
    # Always-on cross-intent execution-discipline panel (spec §7.1). Computed
    # over the cohort's reviewed trades WITHOUT the intent filter applied, so a
    # genuine risk/reconciliation slip can never be hidden by an intent facet.
    execution_discipline_tag_frequency: dict[str, MetricCellA] = field(
        default_factory=dict,
    )
    execution_discipline_n_reviewed: int = 0   # intent-UNFILTERED reviewed count
```

Add `execution_discipline_n_reviewed` to the `__post_init__` int-validation loop (`:460-462`).

Change the function signature + body (`process.py:546`):

```python
def compute_trade_process_metrics(  # noqa: PLR0915
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
    entry_intent: str | None = None,   # None = no filter (today's behavior)
) -> TradeProcessMetricsResult:
    live_policy = read_live_policy(conn)
    # Panel source: the cohort's trades WITHOUT the intent filter (spec §7.1).
    cohort_trades = list_closed_trades_for_cohort(conn, hypothesis_label=hypothesis_label)
    # Metrics cohort: the intent-filtered slice (spec §7.1 row 1).
    if entry_intent is None:
        trades = cohort_trades
    else:
        trades = list_closed_trades_for_cohort(
            conn, hypothesis_label=hypothesis_label, entry_intent=entry_intent)
    ...
```

(All existing metric computation below continues to use `trades`/`inputs` unchanged.) After the existing `mistake_tag_frequency` block (`:762-768`), compute the panel from the INTENT-UNFILTERED reviewed set, reusing the same per-row JSON-isolation loop restricted to `_EXECUTION_DISCIPLINE_TAGS`:

```python
    # Execution-discipline panel (spec §7.1): intent-UNFILTERED reviewed set,
    # restricted to risk/reconciliation tags, SEPARATE denominator.
    panel_inputs = [_prepare_trade_inputs(conn, t) for t in cohort_trades]
    panel_reviewed = [x for x in panel_inputs if x.trade.reviewed_at is not None]
    execution_discipline_n_reviewed = len(panel_reviewed)
    disc_tag_counts: dict[str, int] = {}
    for x in panel_reviewed:
        if not x.trade.mistake_tags:
            continue
        try:
            tags = json.loads(x.trade.mistake_tags)
        except (ValueError, TypeError):
            continue
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if not isinstance(tag, str) or tag not in _EXECUTION_DISCIPLINE_TAGS:
                continue
            disc_tag_counts[tag] = disc_tag_counts.get(tag, 0) + 1
    execution_discipline_tag_frequency = {
        tag: _render_class_a_cell(
            name=f"execution_discipline_{tag}",
            k=count, n=execution_discipline_n_reviewed, policy=live_policy,
        )
        for tag, count in sorted(disc_tag_counts.items())
    }
```

> Performance note: when `entry_intent is None`, `cohort_trades is trades` and `panel_inputs` recomputes `_prepare_trade_inputs` over the same rows already in `inputs`. The executing agent MAY reuse `inputs`/`reviewed_trades` for the panel in the `entry_intent is None` branch to avoid the double prepare; the discriminating behavior is unchanged (the panel is computed over the UNFILTERED reviewed set in both branches). Keep the recompute if it is simpler — the cohort is tiny.

Add both fields to the `return TradeProcessMetricsResult(...)` (`:835-871`):

```python
        execution_discipline_tag_frequency=execution_discipline_tag_frequency,
        execution_discipline_n_reviewed=execution_discipline_n_reviewed,
```

- [ ] **Step 5: Card VM — intent facet on the "All" aggregate (D6)**

In `swing/web/view_models/metrics/trade_process_card.py`: the All-aggregate call (`:176`) passes the selected facet; the per-cohort calls (`:163`) stay unfiltered (D6 — facet only on All). Add an `active_entry_intent: str | None = None` param to `build_trade_process_card_vm` (`:123`), thread it to the All call:

```python
    all_metrics = compute_trade_process_metrics(
        conn, hypothesis_label=None, entry_intent=active_entry_intent)
```

Add a facet selector to the VM (the four states `All / Standard / Hypothesis-test-by-design / Unclassified`) — e.g. an `intent_facets: tuple[tuple[str, str], ...]` of `(value, label)` plus `active_entry_intent: str | None`, where `value` is `""` (All), `"standard"`, `"hypothesis_test_by_design"`, `"__unclassified__"`. Surface on `TradeProcessCardVM`.

- [ ] **Step 6: Template — facet selector + the always-on panel**

In `swing/web/templates/metrics/trade_process_card.html.j2`: when the active tab is the "All" cohort, render the intent-facet selector (links carrying `?cohort=__all__&intent=<value>`, server-rendered — no HTMX). Render the always-on **Execution-discipline** panel (after the mistake-tag-frequency block `:101-113`) iterating `active.metrics.execution_discipline_tag_frequency.items()` through the same `metric_row_a.html.j2` partial; show `execution_discipline_n_reviewed` as the denominator label. Make the panel render for the All tab (and naturally per-cohort, since the field is always computed). Keep the existing cohort tabs + card body unchanged.

- [ ] **Step 7: Route — intent facet query param**

In `swing/web/routes/metrics.py` `metrics_trade_process` (`:63`): add `intent: str | None = Query(default=None)`; normalize `""`/absent → `None` (All); pass `active_entry_intent=intent` to `build_trade_process_card_vm`. Plain server-rendered (no HTMX concerns).

- [ ] **Step 8: Update existing VM/route tests for the new fields**

`tests/web/test_view_models/test_trade_process_card_vm.py` + `tests/web/test_routes/test_metrics_routes.py`: the cohort-tab COUNT is UNCHANGED (no new cohort). Add assertions that the All tab renders the facet selector + the discipline panel; that selecting `?intent=standard` filters the card body but the panel is byte-identical. Adjust any test that snapshots `TradeProcessMetricsResult` fields to include the two new fields.

- [ ] **Step 9: Run PASS + commit**

Run: `python -m pytest tests/metrics tests/web/test_view_models/test_trade_process_card_vm.py tests/web/test_routes/test_metrics_routes.py -q` → Expected: PASS.

```bash
git add swing/metrics/cohort.py swing/metrics/process.py \
  swing/web/view_models/metrics/trade_process_card.py \
  swing/web/templates/metrics/trade_process_card.html.j2 swing/web/routes/metrics.py \
  tests/metrics tests/web/test_view_models/test_trade_process_card_vm.py \
  tests/web/test_routes/test_metrics_routes.py
git commit -m "feat(metrics): facet trade-process card by entry_intent + always-on execution-discipline panel"
```

---

## Task 7: PGT markers — annotate by intent (#22 L5 preserved)

Spec §7.2 (D4) + §10. Additive marker annotation only; the 7 rolling series + every #22 hook stay byte-stable.

**Files:**
- Modify: `swing/metrics/process_grade_trend.py`, `swing/web/view_models/metrics/process_grade_trend.py`, `swing/web/templates/metrics/process_grade_trend.html.j2`
- Test: `tests/metrics/test_process_grade_trend.py`, `tests/web/test_view_models/test_process_grade_trend_vm.py`, `tests/web/test_routes/test_metrics_routes.py` (PGT route test + the no-matplotlib guard)

- [ ] **Step 1: Write failing tests**

```python
def test_marker_carries_entry_intent(v27_conn):
    res = compute_process_grade_trend(conn)
    # a reviewed trade with entry_intent='standard' -> its marker.entry_intent == 'standard'
    assert any(m.entry_intent == "standard" for m in res.per_trade_markers)

def test_pgt_template_emits_intent_css_hook(client_v27):
    html = client_v27.get("/metrics/process-grade-trend").text
    assert 'data-entry-intent=' in html   # marker carries the intent hook

def test_pgt_rolling_series_byte_stable_and_hooks_preserved(client_v27):
    html = client_v27.get("/metrics/process-grade-trend").text
    for hook in ('data-panel="grades"', 'data-panel="rate"', 'data-panel="cost"',
                 'data-series=', '<polyline', '<circle', 'A=4', 'F=0',
                 'data-marker="grades-legend"'):
        assert hook in html
    # the 7 rolling series keyset invariant is unchanged (ProcessGradeTrendResult).
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/metrics/test_process_grade_trend.py tests/web/test_view_models/test_process_grade_trend_vm.py -k intent -q` → Expected: FAIL.

- [ ] **Step 3: Marker field + computation**

In `swing/metrics/process_grade_trend.py`, add to `ProcessGradeTrendPoint` (after `mistake_cost_R` `:99`):

```python
    entry_intent: str | None = None   # tuition-vs-error marker annotation (spec §7.2)
```

In `_build_per_trade_point` (`:314-326`), add `entry_intent=trade.entry_intent,` to the constructor. (`ProcessGradeTrendResult` + the 7 rolling series are UNTOUCHED.)

- [ ] **Step 4: VM hook**

In `swing/web/view_models/metrics/process_grade_trend.py`, add TWO fields to `PerTradeMarkerDisplay` (`:113`): `entry_intent: str | None = None` (the raw stored value, for the `data-entry-intent` attribute) AND `entry_intent_css_class: str = "unclassified"` (the NORMALIZED hook the spec §7.2 requires: `standard` / `by-design` / `unclassified`). The raw `hypothesis_test_by_design` token must NOT be used as a CSS class (it would produce `intent-hypothesis_test_by_design`, missing the spec's `by-design` hook — Codex R1-Major-2). Populate both in `_build_marker_display` (`:541-546`):

```python
        entry_intent=marker.entry_intent,
        entry_intent_css_class=_INTENT_CSS_CLASS.get(marker.entry_intent, "unclassified"),
```

with a module-level map near the top of the VM file:

```python
# Normalized CSS-class hooks for PGT marker intent annotation (spec §7.2).
_INTENT_CSS_CLASS: dict[str | None, str] = {
    "standard": "standard",
    "hypothesis_test_by_design": "by-design",
    None: "unclassified",
}
```

- [ ] **Step 5: Template — marker intent attribute + legend**

In `swing/web/templates/metrics/process_grade_trend.html.j2`, in the GRADES `<circle>` marker loop (`:57-70`), add the intent hook + an intent-distinct class WITHOUT removing any existing hook:

```jinja2
  <circle cx="{{ "%.2f"|format(marker.svg_x) }}"
          cy="{{ "%.2f"|format(marker.svg_y) }}"
          r="4"
          data-trade-id="{{ marker.trade_id }}"
          data-grade="{{ marker.process_grade_letter }}"
          data-disqualifying="{{ marker.disqualifying }}"
          data-entry-intent="{{ marker.entry_intent_css_class }}"
          class="process-grade-marker intent-{{ marker.entry_intent_css_class }}">
```

(`entry_intent_css_class` is the normalized `standard`/`by-design`/`unclassified` token; the `data-entry-intent` attribute carries the same normalized value so route-tests can match the spec's three hooks.) Add a small ASCII legend entry (`standard / by-design / unclassified`) to the existing `data-marker="grades-legend"` group — ASCII only, no `$`/`^`/`_` mathtext metacharacters (these markers are SVG/HTML, not matplotlib, but keep ASCII for parity). Rolling lines + the RATE/COST panels untouched. The Task-7 Step-1 test asserts `data-entry-intent="by-design"` (the normalized hook) appears for a by-design marker — NOT the raw token.

- [ ] **Step 6: Run PASS (incl. no-matplotlib guard green) + commit**

Run: `python -m pytest tests/metrics/test_process_grade_trend.py tests/web/test_view_models/test_process_grade_trend_vm.py tests/web/test_routes/test_metrics_routes.py -q` → Expected: PASS.

```bash
git add swing/metrics/process_grade_trend.py swing/web/view_models/metrics/process_grade_trend.py \
  swing/web/templates/metrics/process_grade_trend.html.j2 \
  tests/metrics/test_process_grade_trend.py tests/web/test_view_models/test_process_grade_trend_vm.py \
  tests/web/test_routes/test_metrics_routes.py
git commit -m "feat(metrics): annotate PGT per-trade markers by entry_intent (#22 hooks preserved)"
```

---

## Task 8: Display-only — CLI single-trade analysis

Spec §7.4. `_render_trade_analysis` prints the trade's `entry_intent` (label; `Unclassified` for NULL). Requires `TradeAnalysis` to carry the field.

**Files:**
- Modify: `swing/journal/analyze.py`, `swing/cli.py`
- Test: `tests/journal/test_analyze.py`, `tests/cli/test_cli_trade.py`

- [ ] **Step 1: Write failing tests**

```python
def test_trade_analysis_carries_entry_intent(v27_conn):
    a = analyze_trade(conn, trade_id=<a standard trade>)
    assert a.entry_intent == "standard"

def test_render_trade_analysis_prints_intent():
    a = _stub_analysis(entry_intent="hypothesis_test_by_design")
    lines = _render_trade_analysis(a)
    assert any("Hypothesis test (by design)" in ln for ln in lines)

def test_render_trade_analysis_null_intent_unclassified():
    a = _stub_analysis(entry_intent=None)
    lines = _render_trade_analysis(a)
    assert any("Intent: Unclassified" in ln for ln in lines)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/journal/test_analyze.py tests/cli/test_cli_trade.py -k intent -q` → Expected: FAIL.

- [ ] **Step 3: Add the field + builder + print**

In `swing/journal/analyze.py`, add to `TradeAnalysis` (after `r_multiple_avg` `:104`):

```python
    entry_intent: str | None = None
```

In `analyze_trade` (`:319`), add `entry_intent=trade.entry_intent,` to the `TradeAnalysis(...)` construction.

In `swing/cli.py` `_render_trade_analysis` (`:1141`), after the `Hypothesis:` line (`:~1161`), add:

```python
    from swing.trades.intent import entry_intent_label
    lines.append(f"Intent: {entry_intent_label(a.entry_intent) or 'Unclassified'}")
```

(ASCII-only.)

- [ ] **Step 4: Run PASS + commit**

Run: `python -m pytest tests/journal/test_analyze.py tests/cli/test_cli_trade.py -q` → Expected: PASS.

```bash
git add swing/journal/analyze.py swing/cli.py tests/journal/test_analyze.py tests/cli/test_cli_trade.py
git commit -m "feat(cli): show entry_intent on single-trade analysis"
```

---

## Task 9: Verification tail

**Files:** none (verification only).

- [ ] **Step 1: Full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS (baseline ~7600+ tests + the new tests; ZERO failures). Per `feedback_no_false_green_claim`, READ the actual summary line — do not infer green.

- [ ] **Step 2: ruff**

Run: `ruff check swing/ tests/` → Expected: clean.

- [ ] **Step 3: Migrate-twice no-op (explicit gate)**

Run: `python -m pytest tests/data/test_migration_0027_entry_intent.py::test_migrate_twice_is_noop -q` → Expected: PASS.

- [ ] **Step 4: Orthogonality gate (explicit)**

Run: `python -m pytest tests/metrics/test_execution_discipline_panel.py -q` → Expected: PASS — the discipline panel is identical across every intent-filter value; `NO_STOP`/`STOP_NOT_PLACED` present; `CHASED` absent.

- [ ] **Step 5: Confirm the locks held (grep)**

Run: `git diff --name-only main` and confirm the touched set is exactly the File Map's production + test files. **MUST NOT appear:** `swing/recommendations/hypothesis.py`, `swing/metrics/tier.py`, `swing/metrics/deviation_outcome.py`, `research/harness/**`, `swing/data/repos/hypothesis.py`, `swing/web/view_models/metrics/hypothesis_progress_card.py`, `swing/journal/stats.py`, and (no widening) `swing/trades/review.py`'s `update_trade_review_fields`/`get_priors_for_ticker`/`get_period_mistake_tag_aggregate`. Confirm `compute_process_grade`/`validate_mistake_tags`/`canonicalize_mistake_tags`/`MISTAKE_TAGS` are unmodified.

- [ ] **Step 6: Operator browser/CLI gate (BINDING, spec §10.1 — post-merge, NOT in this plan's automated scope)**

Document for the post-merge operator gate (TestClient asserts structure only): (1) the trade-process card intent facet renders + the standard-only view isolates real execution quality AND the under-populated states render honestly (the seeded-gate-masks lesson) AND the always-on execution-discipline panel keeps risk/reconciliation slips visible unchanged as the facet toggles; (2) the PGT GRADES panel shows intent-distinct markers + legend in light AND dark mode; (3) the entry + review forms set/correct intent and persist; (4) the backfill walk classifies all 16 + the NULL→Unclassified rendering is honest. Merge blocked until the operator confirms.

---

## Self-Review (run against the spec)

**Spec coverage:**
- §4.1 `ENTRY_INTENTS` in models.py + intent.py presentation → Task 1 Step 4 + Task 2. ✓
- §4.2 migration 0027 (0024-shaped, nullable CHECK, no row rewrites) → Task 1 Step 3. ✓
- §4.3 `Trade.entry_intent` + `__post_init__` validator (#11 atomic with CHECK + constant) → Task 1 Steps 3–4 (same task). ✓
- §4.4 four-point repo plumbing (4th projection era + `_trade_select_cols` + `_row_to_trade[55]` + version-aware INSERT v27 branch + dedicated `update_entry_intent`) → Task 1 Steps 7–8. ✓
- §4.4 #11 sweep (version pins → 27) → Task 1 Step 9. ✓
- §5 single prefill rule (web seeded + submit=confirm; CLI omitted→NULL; service never label-derives) → Tasks 2/3/4. ✓
- §6 backfill walk (all states, idempotent, --trade-id/--force, skip→NULL, summary audit, ASCII, ClickException) → Task 5. ✓
- §7.1 faceting (process.py filter + `__unclassified__`, cohort.py predicate, card facet on All (D6), template + route param) AND the execution-discipline panel exact contract (intent-UNFILTERED source, SEPARATE `execution_discipline_n_reviewed` denominator, risk∪reconciliation tags, reuse the tag loop) → Task 6. ✓
- §7.2 PGT marker field + VM hook + template circles/legend under L5 (#22 hooks preserved, 7 rolling series byte-stable) → Task 7. ✓
- §7.3 set/correct surfaces (entry web/CLI; review web/CLI; dedicated writer) → Tasks 3/4. ✓
- §7.4 display-only single-trade CLI → Task 8. ✓
- §7.5/§7.6 leave-unchanged → in NO task; asserted in Task 9 Step 5 locks grep. ✓
- §8 form-safety (server-stamp; `... or None`; 4-tier ladder; soft-warn `form_values` round-trip; HTMX 204/HX-Redirect preserved; CLI ClickException + ASCII) → Tasks 3/4/5. ✓
- §9 migration + backup-gate (EXPECTED 26→27; `_entry_intent_backup_gate` strict `current==26 AND target>=27`; `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES`; gate registered after broad-watch; migrate-twice) → Task 1 Steps 5–6 + Step 1 tests. ✓
- §10 test strategy (migration, model/repo, prefill table, faceting w/ regression-arithmetic, orthogonality panel, PGT marker + byte-stable, form-safety, backfill subprocess-encoding, live-record fixture) → Tasks 1–8 tests. ✓

**Placeholder scan:** code/SQL steps show complete content; test steps that reference fixture builders (`_v27_conn`, `_minimal_entry_request`, `client_v27`, `v27_conn_mixed_intents`) point at existing harness patterns the executing agent wires from the established conftest fixtures (the migration/model code is fully spelled out). No TBD/TODO. ✓

**Type consistency:** `ENTRY_INTENTS`, `entry_intent`, `ENTRY_INTENT_DISPLAY`, `suggest_entry_intent`, `entry_intent_label`, `entry_intent_display_choices`, `update_entry_intent`, `_entry_intent_backup_gate`, `_create_pre_entry_intent_migration_backup`, `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES`, `_TRADE_SELECT_COLS_V24_TO_V26`, `execution_discipline_tag_frequency`, `execution_discipline_n_reviewed`, `_EXECUTION_DISCIPLINE_TAGS` used consistently across tasks. ✓

## Spec ambiguities resolved (spec-faithful readings)

1. **`insert_trade_with_event` needs a NEW branch, unlike `failure_mode`.** `failure_mode` is review-only and is NEVER in the INSERT; the existing insert has only v21+/legacy branches. `entry_intent` is set AT ENTRY (spec §4.4 point 3), so a third (v27+) INSERT branch is required (Task 1 Step 8). The v27 branch = the v21 branch + `entry_intent`.

2. **Four projection eras, not three.** The repo had three eras (v24+/v21-23/pre-v21). `entry_intent` adds a fourth; the v24+ list is split into a v27+ full projection and a new `_TRADE_SELECT_COLS_V24_TO_V26` (`NULL AS entry_intent`). All three lower projections gain a trailing `NULL AS entry_intent` so `_row_to_trade[55]` is always present (Task 1 Step 7).

3. **No hypothesis-count sweep (contrast 0026).** 0027 adds a trades COLUMN, not a registry row, so cohort/tab counts are UNCHANGED; only the schema-version-pin family flips 26→27. The cleaner-than-0026 rule: every HEAD-tracking literal bumps; every explicit `target_version=N` (including the 0026 test's `target=26` assertions, since `min(26,27)=26`) STAYS (Task 1 Step 9). This is a genuine simplification over the 0026 plan's dual sweep — flagged so Codex confirms no count sweep is silently missing.

4. **Review-form intent persists via a SEPARATE transaction.** `complete_trade_review` is a service that opens its own `with conn:` and does the state transition; the spec mandates a dedicated `update_entry_intent` (not widening the review writer). Intent is independent of review state, so the review POST/CLI call `update_entry_intent` in its own `with conn:` block in the same request (Task 4 Steps 5–6). This honors L2 (review-field writer unchanged) and the gotcha that a service's `with conn:` must not be nested in an outer tx.

5. **Spec `file:line` anchors drifted; re-anchored.** Entry GET 330→~400, POST 565→~448 (EntryRequest at ~1251); review GET 2620→~2591; CLI entry 699→589, review 1364→1328, `_render_trade_analysis` 1098→1141; PGT `ProcessGradeTrendPoint` 79 and `compute_process_grade_trend` 524 confirmed exact. All re-anchored values verified against disk at plan-write; the executing agent re-verifies (main moves).

6. **`__unclassified__` is the NULL filter sentinel; `None` is the no-filter default.** This lets `compute_trade_process_metrics(entry_intent=None)` reproduce today's behavior exactly while `'__unclassified__'` isolates NULL rows — matching spec §7.1's "sentinel default = no filter; ... `'__unclassified__'` filter the cohort."

7. **CLI bad-`--entry-intent` is caught by `click.Choice` (exit 2), with the validator as belt.** The spec §8 ClickException-wrapping applies to the backfill prompt path (free-typed input → `update_entry_intent` ValueError → ClickException) and the review correction path; the `--entry-intent` option on entry/review uses `click.Choice` which rejects pre-dispatch.

## Codex review note (for the executing/review phase)

Per the dispatch brief §3 + `feedback_adversarial_review_verify_data_shapes`, the adversarial Codex review (WSL CLI transport; run to `NO_NEW_CRITICAL_MAJOR`, cap suspended; persist EVERY round's full response incl. Round 1) must:
(a) verify every edit against the SHIPPED signatures cited in "Verified-against-disk signatures" (the `insert_trade_with_event`/`_trade_select_cols`/`_row_to_trade` repo plumbing; the `db.py` gate-registration pattern at ~`:1285`; the `process.py` mistake-tag loop at `:747`; `MetricCellA`/`TradeProcessMetricsResult.__post_init__`; the `cohort.py` WHERE composition; the PGT marker construction; the entry/review route + CLI anchors; the form VMs);
(b) re-verify the §1 live-record data claims (the proposed-intent split, VIR→`None`, SKYT closed-not-reviewed, NULL-label standard rows) against the supplied read-only query output — challenging any the fixtures would otherwise force true;
(c) confirm the orthogonality guarantee is structurally real: the `execution_discipline_*` fields are computed over the intent-UNFILTERED set and the panel denominator is `execution_discipline_n_reviewed` (NOT `n_reviewed`), so toggling the facet cannot change the panel;
(d) confirm the version-pin sweep (Step 9) is exhaustive against the predicted-RED run AND that no hypothesis-count sweep is actually required (the contrast-with-0026 claim).
