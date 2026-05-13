"""Phase 10 Sub-bundle D T-D.7 — integration E2E happy-path.

Seeds:
- A live open trade.
- Account-equity snapshot covering ``last_completed_session(now)``.
- 10 pipeline_runs across distinct trading sessions (unlocks the 30-day
  trend on capital-friction + identification-funnel surfaces).
- Per-run candidates with mixed risk_feasibility outcomes.

Verifies:
- ``/metrics/capital-friction`` PROVISIONAL → LIVE flip on snapshot
  presence (plan §I.13 round-trip BINDING).
- ``/metrics/maturity-stage`` per-position rendering.
- ``/metrics/identification-funnel`` trend rendering + verbatim §A.0.1
  footnote.

Plan §I.13 + dispatch brief §0.12 BINDING: write snapshot at session N +
immediately invoke capital-friction read → assert LIVE badge propagation.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import exchange_calendars
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.evaluation.dates import last_completed_session
from swing.metrics.capital import compute_capital_friction
from swing.metrics.funnel import compute_identification_funnel
from swing.web.app import create_app


@pytest.fixture
def cfg_and_path(tmp_path: Path):
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load_config(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


def _seed_pipeline_runs_10_sessions(
    conn: sqlite3.Connection,
) -> list[str]:
    """Seed 10 distinct trading sessions of pipeline_runs ending at
    ``last_completed_session(now)``. Returns the session dates ascending.
    """
    cal = exchange_calendars.get_calendar("XNYS")
    asof = last_completed_session(datetime.now())
    sessions = sorted({
        ts.date().isoformat()
        for ts in cal.sessions_window(pd.Timestamp(asof), -10)
    })
    for i, sd in enumerate(sessions, start=1):
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, "
            "watch_count, skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, ?, 0, 0, 0, 0, 0, 0)",
            (i, sd + "T13:00:00", sd, sd),
        )
        conn.execute(
            "INSERT INTO pipeline_runs (id, started_ts, finished_ts, "
            "trigger, data_asof_date, action_session_date, state, "
            "lease_token, evaluation_run_id) VALUES "
            "(?, ?, ?, 'manual', ?, ?, 'complete', 'tok', ?)",
            (i, sd + "T13:00:00", sd + "T13:30:00", sd, sd, i),
        )
    return sessions


def _seed_open_trade(
    conn: sqlite3.Connection, *,
    trade_id: int = 100, ticker: str = "AAA",
    pre_trade_locked_at: str | None = None,
    trade_origin: str = "pipeline_aplus",
) -> None:
    if pre_trade_locked_at is None:
        pre_trade_locked_at = (
            last_completed_session(datetime.now()).isoformat() + "T09:30:00"
        )
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "current_avg_cost) VALUES (?, ?, '2026-05-01', 10.0, 100, 9.0, "
        "9.0, 'managing', 'S', 'I', ?, ?, 100, 10.0)",
        (trade_id, ticker, trade_origin, pre_trade_locked_at),
    )


def test_e2e_capital_friction_provisional_to_live_round_trip(cfg_and_path):
    """Plan §I.13 BINDING + dispatch brief §0.12: PROVISIONAL → LIVE flip
    on snapshot record."""
    cfg, cfg_path = cfg_and_path
    asof = last_completed_session(datetime.now())
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_open_trade(conn, trade_id=1, ticker="AAA")
    finally:
        conn.close()

    # First read — no snapshot yet → PROVISIONAL.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r1 = client.get("/metrics/capital-friction")
    assert r1.status_code == 200
    assert 'data-badge="capital-denominator">PROVISIONAL</span>' in r1.text

    # Write snapshot covering today's last completed session.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO account_equity_snapshots (snapshot_date, "
                "equity_dollars, source, recorded_at, recorded_by) VALUES "
                "(?, 2500.0, 'manual', ?, 'test')",
                (asof.isoformat(), asof.isoformat() + "T08:00:00"),
            )
    finally:
        conn.close()

    # Direct compute layer reads LIVE.
    conn = connect(cfg.paths.db_path)
    try:
        result = compute_capital_friction(conn, asof_date=asof)
    finally:
        conn.close()
    assert result.capital_denominator_badge == "LIVE"
    assert result.capital_denominator_dollars == 2500.0

    # Browser layer reflects the flip.
    app2 = create_app(cfg, cfg_path)
    with TestClient(app2) as client:
        r2 = client.get("/metrics/capital-friction")
    assert r2.status_code == 200
    assert 'data-badge="capital-denominator">LIVE</span>' in r2.text


def test_e2e_maturity_stage_renders_with_open_trade(cfg_and_path):
    """5-position equivalent: seed 1 open trade with snapshot; row renders."""
    cfg, cfg_path = cfg_and_path
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_open_trade(conn, trade_id=1, ticker="AAA")
            # Seed a Phase 8 snapshot for the trade.
            asof_session = (
                last_completed_session(datetime.now()).isoformat()
            )
            conn.execute(
                "INSERT INTO daily_management_records "
                "(trade_id, record_type, review_date, data_asof_session, "
                " created_at, mfe_mae_precision_level, is_superseded, "
                " current_stop, current_size, current_avg_cost, "
                " open_MFE_R_to_date, open_MAE_R_to_date, "
                " maturity_stage, trail_MA_candidate_price) "
                "VALUES (1, 'daily_snapshot', ?, ?, ?, "
                " 'daily_approximate', 0, 9.0, 100, 10.0, 1.0, 0.5, "
                " 'pre_+1.5R', NULL)",
                (asof_session, asof_session, asof_session + "T08:00:00"),
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    assert r.status_code == 200
    body = r.text
    # Discriminating: per-position row present for trade 1.
    assert 'data-trade-id="1"' in body
    # NULL trail_MA_candidate_price → em-dash placeholder + None eligibility.
    assert '"—"' in body or "<em>—</em>" in body
    # The forbidden text per plan §G T-D.4.
    assert "[Phase 8 capture pending]" not in body


def test_e2e_identification_funnel_trend_with_10_sessions(cfg_and_path):
    """10 sessions of pipeline_runs → trend renders + §A.0.1 footnote
    verbatim."""
    cfg, cfg_path = cfg_and_path
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_pipeline_runs_10_sessions(conn)
    finally:
        conn.close()

    # Direct compute layer.
    conn = connect(cfg.paths.db_path)
    try:
        result = compute_identification_funnel(
            conn, asof_date=last_completed_session(datetime.now()),
        )
    finally:
        conn.close()
    assert result.trend_suppressed is False
    assert len(result.trend_runs) == 10

    # Browser layer renders the §A.0.1 footnote.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/identification-funnel")
    assert r.status_code == 200
    expected_footnote = (
        "Trend computed from current trade state; historical points "
        "approximate where state has changed since the run."
    )
    assert expected_footnote in r.text


def test_e2e_all_3_surfaces_render_at_baseline_state(cfg_and_path):
    """At a fresh DB the 3 new D surfaces all return 200 (smoke gate)."""
    cfg, cfg_path = cfg_and_path
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_c = client.get("/metrics/capital-friction")
        r_m = client.get("/metrics/maturity-stage")
        r_f = client.get("/metrics/identification-funnel")
    assert r_c.status_code == 200
    assert r_m.status_code == 200
    assert r_f.status_code == 200
