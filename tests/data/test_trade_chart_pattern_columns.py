from pathlib import Path
import pytest
from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event, list_open_trades


def _make_trade(**over) -> Trade:
    base = dict(
        id=None, ticker="AAPL", entry_date="2026-04-26",
        entry_price=10.0, initial_shares=1, initial_stop=9.0,
        current_stop=9.0, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    base.update(over)
    return Trade(**base)


def _seed_pipeline_run(conn) -> int:
    """Seed a pipeline_runs row so the FK on chart_pattern_classification_pipeline_run_id
    resolves. Migration 0010 declares the column REFERENCES pipeline_runs(id) and the
    project's connection setup enables PRAGMA foreign_keys=ON."""
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES ('2026-04-26T00:00:00','manual','2026-04-25','2026-04-26','complete','tok')"
    )
    return conn.execute("SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1").fetchone()[0]


def test_insert_trade_with_chart_pattern_flag_persists_all_four(tmp_path: Path):
    """Round-trip via raw SQL — read paths NOT yet threaded (Task 2.8 follow-up)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            tid = insert_trade_with_event(
                conn,
                _make_trade(
                    chart_pattern_algo="flag",
                    chart_pattern_algo_confidence=0.78,
                    chart_pattern_operator="flag",
                    chart_pattern_classification_pipeline_run_id=run_id,
                ),
                event_ts="2026-04-26T00:00:00", rationale="aplus-setup",
            )
        row = conn.execute(
            "SELECT chart_pattern_algo, chart_pattern_algo_confidence, "
            "chart_pattern_operator, chart_pattern_classification_pipeline_run_id "
            "FROM trades WHERE id = ?",
            (tid,),
        ).fetchone()
        assert row[0] == "flag"
        assert row[1] == 0.78
        assert row[2] == "flag"
        assert row[3] == run_id
    finally:
        conn.close()


def test_insert_trade_with_no_chart_pattern_columns_writes_NULL(tmp_path: Path):
    """Backward-compat: existing call sites pass no chart_pattern_* fields.
    Read via raw SQL until Task 2.8 threads new columns through `_row_to_trade`."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _make_trade(),
                event_ts="2026-04-26T00:00:00", rationale="aplus-setup",
            )
        row = conn.execute(
            "SELECT chart_pattern_algo, chart_pattern_algo_confidence, "
            "chart_pattern_operator, chart_pattern_classification_pipeline_run_id "
            "FROM trades WHERE id = ?",
            (tid,),
        ).fetchone()
        assert row == (None, None, None, None)
    finally:
        conn.close()


def test_insert_trade_flag_without_confidence_raises_valueerror(tmp_path: Path):
    """Repo-layer cross-column invariant per spec §3.2.2 (R2 M2).

    Seeds pipeline_runs so the FK on chart_pattern_classification_pipeline_run_id
    cannot mask the ValueError under test (otherwise an IntegrityError would
    fire first and the test would not discriminate the repo invariant from the
    schema FK)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="flag",
                        chart_pattern_algo_confidence=None,
                        chart_pattern_classification_pipeline_run_id=run_id,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_insert_trade_none_with_confidence_raises_valueerror(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="none",
                        chart_pattern_algo_confidence=0.5,
                        chart_pattern_classification_pipeline_run_id=run_id,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_insert_trade_algo_set_anchor_unset_raises_valueerror(tmp_path: Path):
    """Joint-NULL invariant: algo NOT NULL ⟺ anchor NOT NULL."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="flag",
                        chart_pattern_algo_confidence=0.78,
                        chart_pattern_classification_pipeline_run_id=None,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_insert_trade_anchor_set_algo_unset_raises_valueerror(tmp_path: Path):
    """Joint-NULL invariant in the OTHER direction: anchor NOT NULL with
    algo NULL must also raise. Spec §3.2.2 joint-NULL XOR rule."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo=None,
                        chart_pattern_algo_confidence=None,
                        chart_pattern_classification_pipeline_run_id=run_id,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_list_open_trades_round_trip_chart_pattern(tmp_path: Path):
    """list_open_trades returns Trade with chart_pattern fields populated (Task 2.8)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            insert_trade_with_event(
                conn,
                _make_trade(
                    chart_pattern_algo="flag",
                    chart_pattern_algo_confidence=0.91,
                    chart_pattern_operator=None,
                    chart_pattern_classification_pipeline_run_id=run_id,
                ),
                event_ts="2026-04-26T09:30:00", rationale="task28-test",
            )
        trades = list_open_trades(conn)
        assert len(trades) == 1
        t = trades[0]
        assert t.chart_pattern_algo == "flag"
        assert t.chart_pattern_algo_confidence == 0.91
        assert t.chart_pattern_operator is None
        assert t.chart_pattern_classification_pipeline_run_id == run_id
    finally:
        conn.close()
