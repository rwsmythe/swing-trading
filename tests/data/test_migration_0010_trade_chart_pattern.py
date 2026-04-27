import sqlite3
from pathlib import Path
import pytest
from swing.data.db import ensure_schema


def test_migration_0010_adds_four_trade_columns(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        cur = conn.execute("PRAGMA table_info(trades)")
        cols = {row[1] for row in cur.fetchall()}
        assert "chart_pattern_algo" in cols
        assert "chart_pattern_algo_confidence" in cols
        assert "chart_pattern_operator" in cols
        assert "chart_pattern_classification_pipeline_run_id" in cols
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] == 10
    finally:
        conn.close()


def test_migration_0010_chart_pattern_algo_check_rejects_invalid_value(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, status, "
                "chart_pattern_algo) VALUES "
                "('T', '2026-04-26', 10.0, 1, 9.0, 9.0, 'open', 'pennant')"
            )
    finally:
        conn.close()
