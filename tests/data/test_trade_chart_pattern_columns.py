from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event


def _base_trade(**kwargs) -> Trade:
    defaults = dict(
        id=None,
        ticker="AAPL",
        entry_date="2026-04-26",
        entry_price=100.0,
        initial_shares=10,
        initial_stop=95.0,
        current_stop=95.0,
        status="open",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
    )
    defaults.update(kwargs)
    return Trade(**defaults)


def _seed_pipeline_run(conn) -> int:
    """Seed a pipeline_runs row and return its id."""
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES ('2026-04-26T00:00:00','manual','2026-04-25','2026-04-26','complete','tok')"
    )
    return conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]


def test_insert_trade_with_flag_pattern_returns_id(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        t = _base_trade(
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence=0.82,
            chart_pattern_operator=None,
            chart_pattern_classification_pipeline_run_id=run_id,
        )
        trade_id = insert_trade_with_event(
            conn, t, event_ts="2026-04-26T09:30:00", rationale="test"
        )
        assert trade_id > 0
    finally:
        conn.close()


def test_insert_trade_with_none_pattern_returns_id(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        t = _base_trade(
            chart_pattern_algo="none",
            chart_pattern_algo_confidence=None,
            chart_pattern_operator=None,
            chart_pattern_classification_pipeline_run_id=None,
        )
        trade_id = insert_trade_with_event(
            conn, t, event_ts="2026-04-26T09:30:00", rationale="test"
        )
        assert trade_id > 0
    finally:
        conn.close()


def test_insert_flag_without_confidence_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        t = _base_trade(
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence=None,
            chart_pattern_classification_pipeline_run_id=7,
        )
        with pytest.raises(ValueError, match="confidence"):
            insert_trade_with_event(
                conn, t, event_ts="2026-04-26T09:30:00", rationale="test"
            )
    finally:
        conn.close()


def test_insert_flag_without_pipeline_run_id_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        t = _base_trade(
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence=0.75,
            chart_pattern_classification_pipeline_run_id=None,
        )
        with pytest.raises(ValueError, match="pipeline_run_id"):
            insert_trade_with_event(
                conn, t, event_ts="2026-04-26T09:30:00", rationale="test"
            )
    finally:
        conn.close()


def test_insert_non_flag_with_confidence_raises(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        t = _base_trade(
            chart_pattern_algo="none",
            chart_pattern_algo_confidence=0.5,
        )
        with pytest.raises(ValueError, match="confidence"):
            insert_trade_with_event(
                conn, t, event_ts="2026-04-26T09:30:00", rationale="test"
            )
    finally:
        conn.close()
