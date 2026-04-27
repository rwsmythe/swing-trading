import json
from pathlib import Path
import pytest
import sqlite3
from swing.data.db import ensure_schema
from swing.data.repos.pattern_classifications import (
    insert_classification, get_classification, list_classifications_for_run,
)
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult
from datetime import date


def _seed_pipeline_run(conn) -> int:
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES ('2026-04-26T00:00:00','manual','2026-04-25','2026-04-26','complete','t')"
    )
    return conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]


def _flag_result() -> FlagClassificationResult:
    return FlagClassificationResult(
        detected=True, confidence=0.78, pattern="flag",
        pole_start_date=date(2026, 4, 1), pole_end_date=date(2026, 4, 10),
        flag_start_date=date(2026, 4, 11), flag_end_date=date(2026, 4, 18),
        pole_high=120.0, flag_low=110.0, pivot=119.5,
        components={"pole_gain": 0.45},
    )


def test_insert_and_get(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            row_id = insert_classification(
                conn, pipeline_run_id=run_id, ticker="AAPL",
                result=_flag_result(),
                computed_at="2026-04-26T00:00:00",
            )
        assert row_id > 0
        row = get_classification(conn, pipeline_run_id=run_id, ticker="AAPL")
        assert row is not None
        assert row.pattern == "flag"
        assert row.confidence == 0.78
        assert json.loads(row.components_json)["pole_gain"] == 0.45
    finally:
        conn.close()


def test_list_for_run_returns_mapping(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                  result=_flag_result(), computed_at="ts")
            insert_classification(conn, pipeline_run_id=run_id, ticker="MSFT",
                                  result=_flag_result(), computed_at="ts")
        m = list_classifications_for_run(conn, pipeline_run_id=run_id)
        assert set(m.keys()) == {"AAPL", "MSFT"}
    finally:
        conn.close()


def test_pattern_none_persists_with_NULL_confidence_and_anchors(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        none_result = FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"pole_gain": 0.10},
        )
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="X",
                                  result=none_result, computed_at="ts")
        row = get_classification(conn, pipeline_run_id=run_id, ticker="X")
        assert row.pattern == "none"
        assert row.confidence is None
        assert row.pivot is None
    finally:
        conn.close()


def test_pattern_None_classifier_error_persists_NULL(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        err_result = FlagClassificationResult(
            detected=False, confidence=0.0, pattern=None,
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"error": "boom"},
        )
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="X",
                                  result=err_result, computed_at="ts")
        row = get_classification(conn, pipeline_run_id=run_id, ticker="X")
        assert row.pattern is None
        assert row.confidence is None
        assert "error" in json.loads(row.components_json)
    finally:
        conn.close()


def test_classifier_components_with_nan_sma_persists_as_strict_json_null(tmp_path: Path):
    """When _enrich_components yields NaN (e.g., SMA50 at flag_start_idx < 49),
    the persisted components_json must be RFC 8259 strict JSON — NaN is not.
    Per spec §3.2.1's 'frozen feature snapshot' contract, the JSON must be
    parseable by strict consumers (SQLite json1, external analyzers)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        # Construct a result with a NaN component (mimics undefined SMA).
        nan_result = FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={
                "pole_gain": 0.10,
                "sma10_at_flag_start": 100.0,
                "sma20_at_flag_start": 99.5,
                "sma50_at_flag_start": float("nan"),
            },
        )
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="X",
                                  result=nan_result, computed_at="ts")
        row = get_classification(conn, pipeline_run_id=run_id, ticker="X")
        # Strict-JSON parse must succeed (default json.loads is RFC-compliant).
        # Python's json.loads accepts NaN by default, so use a strict-mode
        # check: raw text must NOT contain literal "NaN".
        assert "NaN" not in row.components_json, \
            f"components_json contains literal NaN (non-strict JSON): {row.components_json!r}"
        # Round-trip via strict parse: explicit allow_nan=False not exposed in
        # json.loads but we can verify via re.search for any NaN/Infinity literal.
        import re
        assert not re.search(r"\b(NaN|-?Infinity)\b", row.components_json)
        # And the value is None (not NaN, not omitted).
        parsed = json.loads(row.components_json)
        assert parsed["sma50_at_flag_start"] is None
        # Other (finite) values preserved.
        assert parsed["sma10_at_flag_start"] == 100.0
    finally:
        conn.close()


def test_unique_constraint_rejects_duplicate_run_ticker(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                  result=_flag_result(), computed_at="ts")
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                      result=_flag_result(), computed_at="ts")
    finally:
        conn.close()
