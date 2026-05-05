"""Phase 5 Task 5.1 — EntryRequest carries chart_pattern snapshot;
record_entry persists what is passed in AS-IS (no re-resolve).

ToCToU fix per spec §3.6 (R2 M3 + R3 M1): cache resolution happens once
at entry-surface (form/CLI); the resolved values flow through the
request and are persisted unchanged. A pipeline run completing between
form render and submit cannot change the persisted values vs the
operator's view at submit time.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.trades import get_trade
from swing.trades.entry import EntryRequest, record_entry


def _seed_pipeline_run(conn: sqlite3.Connection) -> int:
    """Seed a minimal pipeline_runs row so the FK from
    trades.chart_pattern_classification_pipeline_run_id resolves.

    Returns the new pipeline_run id."""
    cur = conn.execute(
        "INSERT INTO pipeline_runs (started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token) "
        "VALUES ('2026-04-26T00:00:00','2026-04-26T00:30:00','manual',"
        "'2026-04-25','2026-04-26','complete','t')"
    )
    conn.commit()
    return int(cur.lastrowid)


# Phase 7 Sub-A: 13 EntryRequest fields populated to satisfy the pre-trade
# required-field gate in record_entry. Tests in this module focus on
# chart-pattern persistence behavior, NOT pre-trade-gate behavior, so they
# splat these placeholder values to clear the gate.
_PRE_TRADE_FIELDS = dict(
    thesis="t", why_now="w", invalidation_condition="i",
    expected_scenario="e", premortem_technical="pt",
    premortem_market_sector="pm", premortem_execution="pe",
    event_risk_present=0, gap_risk_present=0,
    emotional_state_pre_trade="calm", market_regime="Bullish",
    catalyst="technical_only", manual_entry_confidence="normal",
)


def test_record_entry_persists_chart_pattern_snapshot_as_is(tmp_path: Path):
    """ToCToU fix: record_entry persists what's passed in, NOT a fresh
    cache lookup. A pipeline run completing between render and submit
    cannot change the persisted values."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26",
            entry_price=10.0, shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-26T00:00:00",
            hypothesis_label=None,
            chart_pattern_operator=None,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence=0.78,
            chart_pattern_classification_pipeline_run_id=run_id,
            **_PRE_TRADE_FIELDS,
        )
        result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
        t = get_trade(conn, result.trade_id)
        assert t is not None
        assert t.chart_pattern_algo == "flag"
        assert t.chart_pattern_algo_confidence == 0.78
        assert t.chart_pattern_classification_pipeline_run_id == run_id
        assert t.chart_pattern_operator is None
    finally:
        conn.close()


def test_record_entry_canonicalizes_operator_label(tmp_path: Path):
    """Operator override goes through canonicalize_hypothesis_label
    (NFC + control-byte stripping). Spec §3.6.

    The submitted value embeds a leading space, a zero-width space
    (Cf category — dropped), and a trailing tab (Cc category — replaced
    with space, then collapsed). Canonical form: ``flag``.
    """
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        # Embed a zero-width-space + tab to verify they're stripped.
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26", entry_price=10.0,
            shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-26T00:00:00", hypothesis_label=None,
            chart_pattern_operator="  flag​\t",
            chart_pattern_algo="flag", chart_pattern_algo_confidence=0.78,
            chart_pattern_classification_pipeline_run_id=run_id,
            **_PRE_TRADE_FIELDS,
        )
        result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
        t = get_trade(conn, result.trade_id)
        assert t is not None
        assert t.chart_pattern_operator == "flag"  # canonicalized
    finally:
        conn.close()


def test_record_entry_refuses_invariant_violation_at_record_entry_layer(tmp_path: Path):
    """Form-tampering defense: if EntryRequest arrives with algo='flag'
    but confidence=None, the repo-layer ValueError fires from
    insert_trade_with_event (V1 enforcement, spec §3.2.2 R2 M2).

    Compounding-confound: keep the FK target valid (run_id from a real
    pipeline_runs row) so the FK constraint cannot be the cause of the
    raise. Only the cross-column invariant should fire here.
    """
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26", entry_price=10.0,
            shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-26T00:00:00", hypothesis_label=None,
            chart_pattern_operator=None, chart_pattern_algo="flag",
            chart_pattern_algo_confidence=None,
            chart_pattern_classification_pipeline_run_id=run_id,
            # Phase 7 Sub-A: pre-trade gate fires BEFORE the
            # chart_pattern_algo invariant check; populate so the
            # chart-pattern raise is the discriminating signal.
            **_PRE_TRADE_FIELDS,
        )
        with pytest.raises(ValueError, match="chart_pattern"):
            record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    finally:
        conn.close()
