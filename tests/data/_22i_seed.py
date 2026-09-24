"""22-I seed helpers: raw-SQL worlds on a DB migrated to 40 or 41.

Every row is planted by RAW ``INSERT`` (the 18-B.1 technique) so no repo
write-barrier and no 0041 guard stands between a test and its fixture (a
guard never fires on an ordinary append). The world is the SAME at v40 and
v41, so a ``(version, verdict)`` pair isolates what 0041 changed.

``outcome(conn, sql, params)`` runs ONE statement inside a SAVEPOINT that is
ALWAYS rolled back, and names what refused it: ``"OK"``,
``"TRIGGER:<name>"`` (the RAISE text mapped back to its trigger, read from
``sqlite_master`` at call time -- the census ``Probe.classify`` mapping) or
``"CONSTRAINT:<kind>"``.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from swing.data.db import run_migrations
from tests._22b_fixtures import insert_row, seed_trade20

_RAISE_RE = re.compile(r"RAISE\s*\(\s*ABORT\s*,\s*'((?:[^']|'')*)'\s*\)", re.S)
_TEMPLATES: dict[int, Path] = {}
_TEMPLATE_DIR: Path | None = None

TRADE_ID = 20
ENTRY_FILL = 41
OUTCOME_FILL = 44


def _template(version: int) -> Path:
    global _TEMPLATE_DIR
    if version not in _TEMPLATES:
        if _TEMPLATE_DIR is None:
            _TEMPLATE_DIR = Path(tempfile.mkdtemp(prefix="22i-templates-"))
        path = _TEMPLATE_DIR / f"v{version}.db"
        c = sqlite3.connect(path)
        try:
            run_migrations(c, target_version=version,
                           backup_dir=_TEMPLATE_DIR / f"bak{version}")
        finally:
            c.close()
        _TEMPLATES[version] = path
    return _TEMPLATES[version]


def open_plain(path: Path, *, fk: bool = True) -> sqlite3.Connection:
    """Plain sqlite3 in AUTOCOMMIT (isolation_level=None), FK ON by default."""
    c = sqlite3.connect(path, isolation_level=None)
    c.execute(f"PRAGMA foreign_keys={'ON' if fk else 'OFF'}")
    return c


def migrated(tmp_path: Path, version: int, *, name: str | None = None,
             world: bool = False) -> sqlite3.Connection:
    """A fresh DB at ``version`` (plain sqlite3, FK ON, autocommit), copied
    from a per-process template so a parametrized test does not re-run the
    0 -> N walk. ``world=True`` plants ``seed_world``."""
    path = tmp_path / (name or f"v{version}.db")
    shutil.copyfile(_template(version), path)
    c = open_plain(path)
    if world:
        seed_world(c)
    return c


def version_of(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT version FROM schema_version").fetchone()[0])


# ---------------------------------------------------------------------------
# outcome classification
# ---------------------------------------------------------------------------
def _msg_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"):
        for m in _RAISE_RE.finditer(sql):
            out.setdefault(m.group(1).replace("''", "'"), []).append(name)
    return out


def classify(conn: sqlite3.Connection, exc: BaseException | None) -> str:
    if exc is None:
        return "OK"
    msg = str(exc)
    names = _msg_map(conn).get(msg)
    if names:
        return "TRIGGER:" + "|".join(sorted(names))
    for kind in ("NOT NULL", "CHECK", "UNIQUE", "FOREIGN KEY"):
        if msg.startswith(kind + " constraint failed"):
            return f"CONSTRAINT:{kind}"
    return "ERROR:" + msg


def outcome(conn: sqlite3.Connection,
            sql: str | Sequence[Any] | Callable[[sqlite3.Connection], Any],
            params: Sequence[Any] = (), *,
            post: Callable[[sqlite3.Connection], Any] | None = None,
            setup: Sequence[Any] = ()) -> str | tuple[str, Any]:
    """Run ``setup`` then ONE statement (a list of ``(sql, params)``, or a
    callable taking the connection -- a production function under test) inside
    a SAVEPOINT, always rolled back. Returns the classification, or
    ``(classification, post(conn))`` when ``post`` is given (read inside the
    savepoint, before the rollback; ``None`` on a refusal)."""
    conn.execute("SAVEPOINT p22i")
    exc: BaseException | None = None
    seen: Any = None
    try:
        for s in setup:
            conn.execute(*s) if isinstance(s, tuple) else conn.execute(s)
        try:
            if callable(sql):
                sql(conn)
            elif isinstance(sql, str):
                conn.execute(sql, tuple(params))
            else:
                for s in sql:
                    conn.execute(*s) if isinstance(s, tuple) else conn.execute(s)
        except sqlite3.DatabaseError as e:
            exc = e
        if post is not None and exc is None:
            seen = post(conn)
    finally:
        conn.execute("ROLLBACK TO p22i")
        conn.execute("RELEASE p22i")
    verdict = classify(conn, exc)
    return (verdict, seen) if post is not None else verdict


def is_engine_refusal(verdict: str) -> bool:
    return verdict.startswith("CONSTRAINT:")


# ---------------------------------------------------------------------------
# the world: one or more minimal valid rows per guarded table, plus parents
# ---------------------------------------------------------------------------
TS = "2026-08-10T16:00:00"


def seed_world(c: sqlite3.Connection) -> dict[str, Any]:
    """Plant every guarded table. Returns the ids. Every F column of every
    seeded row points at an EXISTING parent (so a parent-present probe is
    meaningful), every W column is NULL on the first row."""
    ids: dict[str, Any] = {}
    # evaluation run 1 + pipeline run 1 (its twin) + pipeline run 2 (BARE: no
    # pattern_evaluations / chart_renders / step timings -- the probe parent
    # delete for the DELETABLE-NO-PRODUCTION-DELETER class).
    c.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, finviz_csv_path, tickers_evaluated, aplus_count, "
        "watch_count, skip_count, excluded_count, error_count) "
        "VALUES (1, '2026-08-07T18:00:00', '2026-08-07', '2026-08-10', NULL, "
        "60, 1, 10, 46, 3, 0)")
    for pid in (1, 2):
        c.execute(
            "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token, "
            "evaluation_run_id) VALUES (?, '2026-08-07T17:55:00', "
            "'2026-08-07T18:05:00', 'scheduled', '2026-08-07', '2026-08-10', "
            "'complete', ?, ?)", (pid, f"lease-{pid}", 1 if pid == 1 else None))
    c.execute(
        "INSERT INTO candidates (id, evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, adr_pct, tight_streak, pullback_pct, "
        "prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, "
        "pattern_tag, notes, sector, industry) "
        "VALUES (1, 1, 'AMN', 'aplus', 36.0, 36.43, 33.72, 4.1, 5, 8.0, 60.0, "
        "NULL, 20.1, 'universe', 'vcp', NULL, 'Healthcare', 'Care')")
    insert_row(c, "candidate_criteria", dict(
        candidate_id=1, criterion_name="c1", layer="trend_template",
        result="pass", value="1", rule="r"))
    insert_row(c, "candidate_criteria", dict(
        candidate_id=1, criterion_name="c2", layer="vcp", result="fail",
        value="0", rule="r"))
    ids["cc"] = (1, "c1")
    ids["er"] = 1
    ids["pipeline_run"] = 1
    ids["bare_pipeline_run"] = 2
    # trade 20 + fills 41 (entry) / 44 (stop) -- the 22-B real shapes
    seed_trade20(c)
    ids["trade"] = TRADE_ID
    ids["te"] = insert_row(c, "trade_events", dict(
        id=1, trade_id=TRADE_ID, ts=TS, event_type="entry", payload_json="{}",
        rationale="r", notes=None))
    insert_row(c, "trade_events", dict(
        id=2, trade_id=TRADE_ID, ts=TS, event_type="note", payload_json="{}"))
    ids["chart_render"] = insert_row(c, "chart_renders", dict(
        id=1, ticker="AMN", surface="watchlist_row", pipeline_run_id=1,
        pattern_class=None, chart_svg_bytes=b"<svg/>", source_data_hash="h1",
        rendered_at=TS, data_asof_date="2026-08-07"))
    ids["pde"] = insert_row(c, "pattern_detection_events", dict(
        detection_id=1, ticker="AMN", detection_date="2026-08-10",
        data_asof_date="2026-08-07", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.8, detector_version="v1",
        finviz_screen_state=None, source="pipeline",
        per_pattern_metadata_json="{}", pipeline_run_id=1, chart_render_id=1,
        created_at=TS))
    ids["pfo"] = insert_row(c, "pattern_forward_observations", dict(
        observation_id=1, detection_id=1, observation_date="2026-08-11",
        ohlc_today_json="{}", status="pending", status_change_event=None,
        sessions_since_detection=1, created_at=TS))
    ids["fac"] = insert_row(c, "finviz_api_calls", dict(
        call_id=1, ts=TS, screen_query="q", status="ok", row_count=60,
        response_time_ms=10, rate_limit_remaining=5, signature_hash="s",
        error_message=None))
    ids["pev"] = insert_row(c, "pattern_evaluations", dict(
        id=1, pipeline_run_id=1, ticker="AMN", pattern_class="vcp",
        detector_version="v1", geometric_score=0.5, geometric_score_json="{}",
        template_match_score=None, template_match_nearest_exemplar_ids_json=None,
        composite_score=0.6, structural_evidence_json="{}",
        feature_distribution_log_json="{}", window_start_date="2026-07-01",
        window_end_date="2026-08-07", created_at=TS))
    ids["cash_movement"] = insert_row(c, "cash_movements", dict(
        id=1, date="2026-08-01", kind="deposit", amount=100.0, ref=None, note=None))
    ids["sac"] = insert_row(c, "schwab_api_calls", dict(
        call_id=1, ts=TS, endpoint="accounts.details", http_status=200,
        response_time_ms=10, rate_limit_remaining=None, signature_hash=None,
        status="success", error_message=None, pipeline_run_id=1,
        surface="pipeline", environment="production"))
    ids["yfc"] = insert_row(c, "yfinance_calls", dict(
        call_id=1, ts=TS, call_type="download_single", ticker="AMN",
        ticker_count=None, response_time_ms=10, status="success", rows_returned=5,
        error_message=None, pipeline_run_id=1, surface="pipeline"))
    # call 2 of each on the BARE pipeline run 2: the pipeline_run_id probe
    # delete subjects.
    insert_row(c, "schwab_api_calls", dict(
        call_id=2, ts=TS, endpoint="accounts.details", status="success",
        pipeline_run_id=2, surface="pipeline", environment="production"))
    insert_row(c, "yfinance_calls", dict(
        call_id=2, ts=TS, call_type="download_single", ticker="AMN",
        status="success", pipeline_run_id=2, surface="pipeline"))
    ids["rr"] = insert_row(c, "reconciliation_runs", dict(
        run_id=1, source="schwab_api", source_artifact_path="schwab_api:call/1",
        source_artifact_sha256="abc", period_start="2026-08-01",
        period_end="2026-08-10", started_ts=TS, state="running",
        schwab_api_call_id=1))
    ids["aes"] = insert_row(c, "account_equity_snapshots", dict(
        snapshot_id=1, snapshot_date="2026-08-10", equity_dollars=1300.0,
        source="schwab_api", source_artifact_path=None, recorded_at=TS,
        recorded_by="pipeline", notes=None, schwab_account_hash=None,
        basis="net_liq"))
    # daily_management_records: 1 ACTIVE (session 08-10); the superseded pair
    # 2 (-> 3) at session 08-11 with 3 the higher-tier active successor.
    base = dict(trade_id=TRADE_ID, record_type="daily_snapshot",
                created_at=TS, current_price=37.0, current_stop=33.72,
                current_size=5.0, current_avg_cost=36.43, pipeline_run_id=1,
                linked_trade_event_id=1)
    ids["dmr"] = insert_row(c, "daily_management_records", dict(
        base, management_record_id=1, review_date="2026-08-10",
        data_asof_session="2026-08-10", mfe_mae_precision_level="daily_approximate",
        is_superseded=0, superseded_by_record_id=None))
    insert_row(c, "daily_management_records", dict(
        base, management_record_id=3, review_date="2026-08-11",
        data_asof_session="2026-08-11", mfe_mae_precision_level="intraday_estimated",
        is_superseded=0, superseded_by_record_id=None))
    insert_row(c, "daily_management_records", dict(
        base, management_record_id=2, review_date="2026-08-11",
        data_asof_session="2026-08-11", mfe_mae_precision_level="daily_approximate",
        is_superseded=1, superseded_by_record_id=3))
    ids["dmr_superseded"] = 2
    ids["rd"] = insert_row(c, "reconciliation_discrepancies", dict(
        discrepancy_id=1, run_id=1, discrepancy_type="entry_price_mismatch",
        trade_id=TRADE_ID, fill_id=ENTRY_FILL, cash_movement_id=1,
        linked_daily_management_record_id=1, ticker="AMN", field_name="price",
        expected_value_json="36.43", actual_value_json="36.44", delta_text="0.01",
        material_to_review=1, resolution="unresolved", created_at=TS))
    # discrepancy 2 hangs off the BARE trade 21 (no trade_events / dmr
    # children): the rd.trade_id probe-delete subject.
    seed_trade20(c, id=21, ticker="BBB")
    insert_row(c, "reconciliation_discrepancies", dict(
        discrepancy_id=2, run_id=1, discrepancy_type="stop_mismatch",
        trade_id=21, fill_id=None, cash_movement_id=None,
        linked_daily_management_record_id=None, ticker="BBB", field_name="stop",
        expected_value_json="1.0", actual_value_json="1.1", delta_text="0.1",
        material_to_review=0, resolution="unresolved", created_at=TS))
    ids["rc"] = insert_row(c, "reconciliation_corrections", dict(
        correction_id=1, discrepancy_id=1, correction_action="auto_applied",
        correction_choice=None, affected_table="fills", affected_row_id=ENTRY_FILL,
        field_name="price", pre_correction_value_json="36.43",
        source_canonical_value_json="36.44", applied_value_json="36.44",
        operator_truth_value_json=None, applied_at=TS, applied_by="auto",
        correction_set_id=None, superseded_by_correction_id=None,
        risk_policy_id_at_correction=1, schwab_api_call_id=1,
        reconciliation_run_id=1, correction_reason="r", notes=None))
    insert_row(c, "reconciliation_corrections", dict(
        correction_id=2, discrepancy_id=1, correction_action="operator_overridden",
        correction_choice=None, affected_table="fills", affected_row_id=ENTRY_FILL,
        field_name="price", pre_correction_value_json="36.44",
        source_canonical_value_json=None, applied_value_json="36.43",
        operator_truth_value_json="36.43", applied_at=TS, applied_by="operator",
        correction_set_id=None, superseded_by_correction_id=None,
        risk_policy_id_at_correction=1, schwab_api_call_id=1,
        reconciliation_run_id=1, correction_reason="r", notes=None))
    ids["rp"] = 1  # the migration-seeded active policy
    ids["hr"] = 1  # migration-seeded hypothesis rows 1..5
    ids["hsh"] = 1  # migration-seeded current history rows 1..5
    ids["rl"] = insert_row(c, "review_log", dict(
        review_id=1, review_type="weekly", period_start="2026-08-03",
        period_end="2026-08-09", scheduled_date="2026-08-10", created_at=TS))
    ids["rl_completed"] = insert_row(c, "review_log", dict(
        review_id=2, review_type="weekly", period_start="2026-07-27",
        period_end="2026-08-02", scheduled_date="2026-08-03",
        completed_date="2026-08-04", duration_minutes=30, n_trades_reviewed=1,
        total_mistake_cost_R=0.5, total_lucky_violation_R=0.0,
        primary_lesson="l", next_period_focus="f", created_at=TS,
        net_R_effective=1.0, expectancy_R_effective=1.0, win_rate=1.0,
        avg_win_R=1.0, avg_loss_R=None, profit_factor=None, max_drawdown_R=0.0,
        risk_policy_id_at_review_completion=1, superseded_by_correction_id=None,
        auto_populated_field_keys_json=None))
    ids["pex"] = insert_row(c, "pattern_exemplars", dict(
        id=1, ticker="AMN", timeframe="daily", start_date="2026-07-01",
        end_date="2026-08-07", proposed_pattern_class="vcp",
        final_decision="generated", final_pattern_class=None,
        label_source="synthetic", codex_reviewed=0, geometric_score_json="{}",
        labeler_evidence_json=None, structural_evidence_json="{}",
        parent_exemplar_id=None, created_at=TS, created_by="synthetic_generator"))
    ids["wla"] = insert_row(c, "watchlist_archive", dict(
        id=1, ticker="AMN", added_date="2026-07-01", removed_date="2026-08-07",
        reason="entered", qualification_count=3, last_data_asof_date="2026-08-06",
        notes=None))
    return ids


# the PK of the first seeded row per guarded table (a dict of column -> value)
def first_pk(table: str) -> dict[str, Any]:
    from tests.data._22i_guard_spec import SPEC

    spec = SPEC[table]
    if table == "candidate_criteria":
        return {"candidate_id": 1, "criterion_name": "c1"}
    return {spec.pk[0]: 1}


def where_pk(table: str, pk: dict[str, Any] | None = None) -> tuple[str, tuple]:
    pk = pk or first_pk(table)
    return " AND ".join(f"{k} = ?" for k in pk), tuple(pk.values())


def row_of(conn: sqlite3.Connection, table: str,
           pk: dict[str, Any] | None = None) -> dict[str, Any]:
    w, p = where_pk(table, pk)
    cur = conn.execute(f"SELECT * FROM {table} WHERE {w}", p)
    names = [d[0] for d in cur.description]
    row = cur.fetchone()
    assert row is not None, (table, pk)
    return dict(zip(names, row, strict=True))


def insert_copy_sql(conn: sqlite3.Connection, table: str, row: dict[str, Any],
                    verb: str = "INSERT") -> tuple[str, tuple]:
    cols = list(row)
    return (f"{verb} INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})", tuple(row.values()))


def different_value(conn: sqlite3.Connection, table: str, col: str,
                    current: Any) -> Any:
    """A value for ``col`` that differs from ``current`` and (where the schema
    constrains it) is still admissible -- so a refusal is the TRIGGER's, never
    an engine constraint."""
    return _DIFFERENT.get((table, col), _generic_different)(current)


def _generic_different(v: Any) -> Any:
    if v is None:
        return "x"
    if isinstance(v, bytes):
        return v + b"x"
    if isinstance(v, int):
        return v + 1000
    if isinstance(v, float):
        return v + 1.5
    return str(v) + "x"


def _const(x: Any) -> Callable[[Any], Any]:
    return lambda _v: x


# Enum / CHECK-constrained columns: a DIFFERENT admissible value.
_DIFFERENT: dict[tuple[str, str], Callable[[Any], Any]] = {
    ("pattern_forward_observations", "status"): _const("expired"),
    ("pattern_forward_observations", "status_change_event"): _const("time_exit"),
    ("pattern_forward_observations", "sessions_since_detection"): _const(7),
    ("pattern_detection_events", "pattern_class"): _const("flat_base"),
    ("pattern_detection_events", "source"): _const("backfill"),
    ("candidate_criteria", "layer"): _const("risk"),
    ("candidate_criteria", "result"): _const("na"),
    ("trade_events", "event_type"): _const("flag"),
    ("finviz_api_calls", "status"): _const("error"),
    ("pattern_evaluations", "pattern_class"): _const("flat_base"),
    ("reconciliation_corrections", "correction_action"): _const("operator_overridden"),
    ("reconciliation_corrections", "affected_table"): _const("trades"),
    ("reconciliation_corrections", "applied_by"): _const("operator"),
    ("reconciliation_runs", "source"): _const("manual"),
    ("reconciliation_runs", "state"): _const("completed"),
    ("reconciliation_discrepancies", "discrepancy_type"): _const("stop_mismatch"),
    ("reconciliation_discrepancies", "resolution"): _const("journal_corrected"),
    ("reconciliation_discrepancies", "material_to_review"): _const(0),
    ("reconciliation_discrepancies", "ambiguity_kind"): _const(None),
    ("schwab_api_calls", "endpoint"): _const("marketdata.quotes"),
    ("schwab_api_calls", "status"): _const("error"),
    ("schwab_api_calls", "surface"): _const("cli"),
    ("schwab_api_calls", "environment"): _const("sandbox"),
    ("schwab_api_calls", "linked_snapshot_id"): _const(1),
    ("schwab_api_calls", "linked_reconciliation_run_id"): _const(1),
    ("schwab_api_calls", "linked_correction_id"): _const(1),
    ("review_log", "superseded_by_correction_id"): _const(1),
    ("yfinance_calls", "call_type"): _const("download_intraday"),
    ("yfinance_calls", "status"): _const("empty"),
    ("yfinance_calls", "surface"): _const("web"),
    ("yfinance_calls", "ticker_count"): _const(None),
    ("account_equity_snapshots", "source"): _const("manual"),
    ("account_equity_snapshots", "basis"): _const("cash"),
    ("daily_management_records", "record_type"): _const("daily_snapshot"),
    ("daily_management_records", "mfe_mae_precision_level"): _const("intraday_exact"),
    ("daily_management_records", "thesis_status"): _const("weakening"),
    ("daily_management_records", "stop_changed"): _const(1),
    ("daily_management_records", "volume_behavior"): _const("fading"),
    ("daily_management_records", "relative_strength_status"): _const("flat"),
    ("daily_management_records", "market_regime_change"): _const(1),
    ("daily_management_records", "sector_condition_change"): _const(1),
    ("daily_management_records", "action_taken"): _const("hold"),
    ("daily_management_records", "rule_violation_suspected"): _const(1),
    ("daily_management_records", "maturity_stage"): _const("+1.5R_to_+2R"),
    ("daily_management_records", "trail_MA_eligibility_flag"): _const(1),
    ("daily_management_records", "trail_MA_period_days"): _const(21),
    ("review_log", "review_type"): _const("monthly"),
    ("review_log", "skipped"): _const(1),
    ("risk_policy", "consecutive_losses_pause_action"): _const("review_required"),
    ("risk_policy", "consecutive_losses_streak_reset"): _const("review_completed"),
    ("risk_policy", "drawdown_circuit_breaker_enabled"): _const(1),
    ("risk_policy", "drawdown_pause_threshold_R"): _const(-3.0),
    ("risk_policy", "drawdown_pause_action"): _const("reduce_size"),
    ("risk_policy", "drawdown_size_reduction_pct"): _const(0.5),
    ("risk_policy", "drawdown_recovery_threshold_R"): _const(-1.0),
    ("risk_policy", "mfe_mae_default_precision_level"): _const("intraday_exact"),
    ("hypothesis_registry", "status"): _const("paused"),
    ("hypothesis_status_history", "status"): _const("paused"),
}


# ---------------------------------------------------------------------------
# row builders for the A-series probes (plan section 4.1)
# ---------------------------------------------------------------------------
# A FRESH value for the column that makes a row non-conflicting on its key.
_FRESH: dict[tuple[str, str], Any] = {
    ("pattern_forward_observations", "observation_date"): "2026-08-12",
    ("pattern_detection_events", "pattern_class"): "flat_base",
    ("candidate_criteria", "criterion_name"): "c-new",
    ("pattern_evaluations", "pattern_class"): "flat_base",
    ("account_equity_snapshots", "basis"): "cash",
    ("review_log", "period_end"): "2026-08-16",
    ("hypothesis_registry", "name"): "H-22i-new",
}


def _keys(table: str) -> list[tuple[str, ...]]:
    """The conflict targets a probe exercises: the declared UNIQUE keys, the
    composite PK of a non-INTEGER-PK table, or (none declared) the PK."""
    from tests.data._22i_guard_spec import SPEC

    spec = SPEC[table]
    keys = list(spec.conflict_keys)
    if not spec.integer_pk:
        keys.insert(0, spec.pk)
    return keys


def payload_column(table: str, exclude: Sequence[str] = ()) -> str:
    """A non-PK, non-key, non-FK column to carry a 'new payload'."""
    from tests.data._22i_guard_spec import SPEC

    spec = SPEC[table]
    skip = set(spec.pk) | set(exclude) | set(spec.f_cols)
    for key in _keys(table):
        skip |= set(key)
    for col in spec.all_columns():
        if col not in skip:
            return col
    raise AssertionError(table)


def fresh_row(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    """The first seeded row, INTEGER PK omitted, every conflict key made
    fresh: an ordinary append (A1)."""
    from tests.data._22i_guard_spec import SPEC

    spec = SPEC[table]
    row = row_of(conn, table)
    if spec.integer_pk:
        del row[spec.pk[0]]
    for key in _keys(table):
        col = key[-1]
        row[col] = _FRESH[(table, col)]
    return row


def conflict_rows(conn: sqlite3.Connection, table: str) -> list[tuple[str, dict[str, Any]]]:
    """``(label, row)`` per conflict target: the first seeded row with a NEW
    payload, colliding on that key only (INTEGER PK omitted), or -- a table
    with no UNIQUE beyond the PK -- colliding on the explicit PK."""
    from tests.data._22i_guard_spec import SPEC

    spec = SPEC[table]
    out = []
    keys = _keys(table)
    for key in keys:
        row = row_of(conn, table)
        if spec.integer_pk:
            del row[spec.pk[0]]
        col = payload_column(table, exclude=key)
        row[col] = different_value(conn, table, col, row[col])
        out.append(("key:" + ",".join(key), row))
    if not keys:
        row = row_of(conn, table)
        col = payload_column(table)
        row[col] = different_value(conn, table, col, row[col])
        out.append(("pk", row))
    return out
