"""The 7 per-check helpers (discriminating boundary arithmetic, grounded
fixtures). Seeds the real schema + real repos so the production read path is
exercised (anti-drift); plants legacy NaN rows by writing the ohlc_today_json
text directly (the production write barrier rejects NaN -- the DEFECT rows
predate that barrier).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.monitoring.research_health import (
    ResearchHealthCheck,
    _check_temporal_log_finiteness,
)

_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


def _schema_conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    return conn


def _seed_detection(
    conn: sqlite3.Connection,
    *,
    ticker: str = "AAA",
    detection_date: str = "2026-06-05",
    data_asof_date: str = "2026-06-04",
) -> int:
    det = PatternDetectionEvent(
        detection_id=None,
        ticker=ticker,
        detection_date=detection_date,
        data_asof_date=data_asof_date,
        pattern_class="vcp",
        structural_anchors_json="{}",
        composite_score=1.0,
        detector_version="t",
        source="synthetic",
        per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00",
    )
    det_id = insert_detection_event(conn, det)
    conn.commit()
    return det_id


def _seed_observation(
    conn: sqlite3.Connection,
    det_id: int,
    *,
    observation_date: str,
    ohlc_today_json: str = _FINITE_OHLC,
    status: str = "pending",
    sessions_since_detection: int = 1,
) -> None:
    obs = PatternForwardObservation(
        observation_id=None,
        detection_id=det_id,
        observation_date=observation_date,
        ohlc_today_json=ohlc_today_json,
        status=status,
        sessions_since_detection=sessions_since_detection,
        created_at="2026-06-05T00:00:00",
    )
    insert_observation(conn, obs)
    conn.commit()


def _only(checks: list[ResearchHealthCheck], key: str) -> ResearchHealthCheck:
    matches = [c for c in checks if c.key == key]
    assert len(matches) == 1, f"expected exactly one {key}, got {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# Task 2: _check_temporal_log_finiteness (the data-USABILITY authority)
# ---------------------------------------------------------------------------


def test_finiteness_green_when_all_finite(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    for d in ("2026-06-05", "2026-06-08", "2026-06-09"):
        _seed_observation(conn, det, observation_date=d)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"
    assert "0" in check.summary or "no non-finite" in check.summary.lower()


def test_finiteness_red_on_nan_close(tmp_path: Path) -> None:
    # THE motivating-defect test: O/H/L present, close NaN (the 06-10 shape).
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn, ticker="MSFT")
    _seed_observation(conn, det, observation_date="2026-06-05")
    _seed_observation(conn, det, observation_date="2026-06-08")
    nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    assert json.loads(nan_json)["close"] != json.loads(nan_json)["close"]  # NaN
    _seed_observation(conn, det, observation_date="2026-06-09", ohlc_today_json=nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"
    assert "1" in check.summary  # exactly 1 non-finite of 3
    assert "MSFT" in (check.detail or "")
    assert "2026-06-09" in (check.detail or "")


def test_finiteness_red_on_none_value(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    null_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": null, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05", ohlc_today_json=null_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"  # NOT a TypeError crash


def test_finiteness_red_on_inf(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    inf_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": Infinity, ' \
        '"volume": 100.0, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05", ohlc_today_json=inf_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"


def test_finiteness_red_on_missing_key(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    missing_json = '{"open": 1.0, "high": 2.0, "low": 0.5, ' \
        '"volume": 100.0, "provider": "yfinance"}'  # no close
    _seed_observation(conn, det, observation_date="2026-06-05",
                      ohlc_today_json=missing_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "red"


def test_finiteness_green_when_empty_table(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)  # schema present, 0 observations
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"
    assert "observations yet" in check.summary.lower() or "no " in check.summary.lower()


def test_finiteness_yellow_when_missing_table(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")  # NO pattern_forward_observations table
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "yellow"
    assert "unavailable" in check.summary.lower() or "schema" in check.summary.lower()


def test_finiteness_volume_nan_is_exempt(tmp_path: Path) -> None:
    conn = _schema_conn(tmp_path)
    det = _seed_detection(conn)
    vol_nan_json = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
        '"volume": NaN, "provider": "yfinance"}'
    _seed_observation(conn, det, observation_date="2026-06-05",
                      ohlc_today_json=vol_nan_json)
    check = _only(_check_temporal_log_finiteness(conn), "temporal_log_finiteness")
    assert check.status == "green"  # Volume EXEMPT (Arc-8)
