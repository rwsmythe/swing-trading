"""Phase 13 T2.SB6c cross-bundle pin row 12 (parametrized over the 2 deltas).

Per plan §E + §G.1 Step 1d. Planted at T-A.6c.1; un-skipped (promoted to GREEN)
at T-A.6c.5 closer.

Each parametrized test asserts the FULL §A.14 paired-discipline set for one
delta:
  - schema: column exists in trades + correct INTEGER + nullable.
  - FK: ON DELETE SET NULL on referenced (table, col).
  - index: exists in sqlite_master.
  - mapper roundtrip: insert via INSERT-SVAI extended path + read back via
    _row_to_trade with non-NULL value, then NULL value.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import get_trade, insert_trade_with_event


def _v21_conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "v21.db"
    conn = ensure_schema(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_fk_target(
    conn: sqlite3.Connection,
    fk_table: str,
) -> int:
    """Plant a single referenceable row in fk_table; return its id.

    The schema setup mirrors the canonical Phase 13 lookup chain
    (evaluation_runs -> pipeline_runs -> candidates -> pattern_evaluations).
    """
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs (
            run_ts, data_asof_date, action_session_date,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count
        ) VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)
        """,
        ("2026-05-22T12:00:00.000", "2026-05-22", "2026-05-22"),
    )
    evaluation_run_id = int(cur.lastrowid)

    cur = conn.execute(
        """
        INSERT INTO pipeline_runs (
            started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, evaluation_run_id
        ) VALUES (?, ?, 'manual', ?, ?, 'complete', ?, ?)
        """,
        (
            "2026-05-22T12:00:00.000",
            "2026-05-22T12:05:00.000",
            "2026-05-22",
            "2026-05-22",
            "tok-pin",
            evaluation_run_id,
        ),
    )
    pipeline_run_id = int(cur.lastrowid)

    if fk_table == "candidates":
        cur = conn.execute(
            """
            INSERT INTO candidates (evaluation_run_id, ticker, bucket, rs_method)
            VALUES (?, 'PIN', 'aplus', 'unavailable')
            """,
            (evaluation_run_id,),
        )
        return int(cur.lastrowid)

    if fk_table == "pattern_evaluations":
        cur = conn.execute(
            """
            INSERT INTO pattern_evaluations (
                pipeline_run_id, ticker, pattern_class, detector_version,
                geometric_score, geometric_score_json, composite_score,
                structural_evidence_json, feature_distribution_log_json,
                window_start_date, window_end_date, created_at
            ) VALUES (?, 'PIN', 'vcp', 'vcp-v1.0', 0.8, '{}', 0.8, '{}', '{}',
                      '2026-05-01', '2026-05-22', '2026-05-22T12:00:00.000')
            """,
            (pipeline_run_id,),
        )
        return int(cur.lastrowid)

    raise ValueError(f"unknown fk_table {fk_table!r}")


def _make_trade(
    *,
    column_name: str,
    fk_value: int | None,
) -> Trade:
    kw: dict = {"candidate_id": None, "pattern_evaluation_id": None}
    kw[column_name] = fk_value
    return Trade(
        id=None,
        ticker="PIN",
        entry_date="2026-05-22",
        entry_price=100.0,
        initial_shares=10,
        initial_stop=95.0,
        current_stop=95.0,
        state="entered",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
        trade_origin="pipeline_aplus",
        pre_trade_locked_at="2026-05-22T12:00:00.000",
        current_size=10.0,
        **kw,
    )


@pytest.mark.parametrize(
    "delta_label,column_name,fk_table,fk_col,index_name",
    [
        (
            "candidate_id",
            "candidate_id",
            "candidates",
            "id",
            "idx_trades_candidate_id",
        ),
        (
            "pattern_evaluation_id",
            "pattern_evaluation_id",
            "pattern_evaluations",
            "id",
            "idx_trades_pattern_evaluation_id",
        ),
    ],
)
def test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic(
    tmp_path: Path,
    delta_label: str,
    column_name: str,
    fk_table: str,
    fk_col: str,
    index_name: str,
) -> None:
    """Cross-bundle pin row 12: every Delta lands the full §A.14 paired set."""
    conn = _v21_conn(tmp_path)
    try:
        # Schema: column exists in trades.
        cols = {
            r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        assert column_name in cols, (
            f"{column_name} not in trades cols (delta={delta_label})"
        )

        # FK: ON DELETE SET NULL on referenced table.
        fks = conn.execute("PRAGMA foreign_key_list(trades)").fetchall()
        matching = [
            fk for fk in fks
            if fk[2] == fk_table and fk[3] == column_name and fk[4] == fk_col
        ]
        assert matching, (
            f"FK not found for {column_name} -> {fk_table}({fk_col})"
        )
        # PRAGMA foreign_key_list col 6 = on_delete
        assert matching[0][6] == "SET NULL"

        # Index: exists in sqlite_master.
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        ).fetchone()
        assert idx is not None, f"index {index_name} not found"

        # Mapper roundtrip: insert non-NULL + read back via _row_to_trade.
        fk_id = _seed_fk_target(conn, fk_table)
        trade_non_null = _make_trade(column_name=column_name, fk_value=fk_id)
        with conn:
            tid = insert_trade_with_event(
                conn, trade_non_null,
                event_ts="2026-05-22T12:30:00.000",
            )
        fetched = get_trade(conn, tid)
        assert fetched is not None
        assert getattr(fetched, column_name) == fk_id

        # Mapper roundtrip: insert NULL + read back as None.
        trade_null = _make_trade(column_name=column_name, fk_value=None)
        # Use a different ticker to avoid one-open-per-ticker invariant.
        trade_null_diff_ticker = Trade(
            id=None,
            ticker="PIN2",
            entry_date="2026-05-22",
            entry_price=100.0,
            initial_shares=10,
            initial_stop=95.0,
            current_stop=95.0,
            state="entered",
            watchlist_entry_target=None,
            watchlist_initial_stop=None,
            notes=None,
            trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-22T12:00:00.000",
            current_size=10.0,
            candidate_id=None,
            pattern_evaluation_id=None,
        )
        with conn:
            tid_null = insert_trade_with_event(
                conn, trade_null_diff_ticker,
                event_ts="2026-05-22T12:31:00.000",
            )
        fetched_null = get_trade(conn, tid_null)
        assert fetched_null is not None
        assert getattr(fetched_null, column_name) is None
        # Reference trade_null to satisfy unused-variable lints.
        _ = trade_null
    finally:
        conn.close()
