"""Task 7 -- compute_research_health aggregator (worst-of + envelope + aware-UTC
clock normalization). End-to-end against a seeded DB + tmp manifest/exports
dirs; the read-only LOCK proof.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.monitoring.research_health import (
    ResearchHealthStatus,
    compute_research_health,
)

_NOW = datetime(2026, 6, 14, 12, 0, 0)  # Sunday -> last_completed = Fri 2026-06-12
_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'
# NYSE sessions 2026-06-05..2026-06-12.
_SESSIONS = ("2026-06-05", "2026-06-08", "2026-06-09", "2026-06-10",
             "2026-06-11", "2026-06-12")


def _seed_green_db(conn: sqlite3.Connection) -> None:
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="AAA", detection_date="2026-06-05",
        data_asof_date="2026-06-04", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-05T00:00:00"))
    for d in _SESSIONS:
        insert_observation(conn, PatternForwardObservation(
            observation_id=None, detection_id=det, observation_date=d,
            ohlc_today_json=_FINITE_OHLC, status="pending",
            sessions_since_detection=1, created_at="2026-06-05T00:00:00"))
    # a complete candidate run
    cur = conn.execute(
        "INSERT INTO evaluation_runs (run_ts, data_asof_date, action_session_date,"
        " tickers_evaluated, aplus_count, watch_count, skip_count, excluded_count,"
        " error_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2026-06-12T00:00:00", "2026-06-12", "2026-06-15", 1, 1, 0, 0, 0, 0))
    run = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, pivot, rs_method)"
        " VALUES (?, ?, ?, ?, ?)", (run, "AAA", "aplus", 10.0, "universe"))
    conn.commit()


def _fresh_exports_root(tmp_path: Path) -> Path:
    """A fresh shadow-expectancy-* dir 1 day before _NOW with an attributed,
    zero-unattributed manifest -> drumbeat green, excluded green."""
    import json

    ts = (_NOW.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
          .astimezone(ZoneInfo("UTC")) - timedelta(days=1))
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    root = tmp_path / "research"
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_all_green_overall_green(tmp_path: Path) -> None:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    exports_root = _fresh_exports_root(tmp_path)
    status = compute_research_health(conn, exports_root=exports_root, now=_NOW)
    assert status.overall == "green"
    assert len(status.checks) == 7
    keys = {c.key for c in status.checks}
    assert keys == {
        "temporal_log_finiteness", "excluded_reason_breakdown", "coverage_gaps",
        "structural_integrity", "drumbeat_liveness", "candidate_completeness",
        "fetch_transport_health",
    }


def test_one_red_makes_overall_red(tmp_path: Path) -> None:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    # plant a NaN-Close observation on a SEPARATE detection (finiteness red).
    det2 = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="ZZZ", detection_date="2026-06-12",
        data_asof_date="2026-06-11", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-12T00:00:00"))
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det2, "2026-06-12",
         '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, '
         '"volume": 100.0, "provider": "yfinance"}',
         "pending", 1, "2026-06-12T00:00:00"))
    conn.commit()
    exports_root = _fresh_exports_root(tmp_path)
    status = compute_research_health(conn, exports_root=exports_root, now=_NOW)
    assert status.overall == "red"


def test_one_yellow_no_red_overall_yellow(tmp_path: Path) -> None:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    # a STALE drumbeat (5 days) -> yellow, nothing red.
    import json

    ts = (_NOW.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
          .astimezone(ZoneInfo("UTC")) - timedelta(days=5))
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    root = tmp_path / "research"
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}), encoding="utf-8")
    status = compute_research_health(conn, exports_root=root, now=_NOW)
    assert status.overall == "yellow"


def test_compute_research_health_bare_conn_call_shape(tmp_path: Path) -> None:
    # schema-present-but-EMPTY DB: no check false-reds on absent optional inputs.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    status = compute_research_health(conn, exports_root=tmp_path / "none", now=_NOW)
    assert isinstance(status, ResearchHealthStatus)
    # finiteness/structural/candidate green on empty; manifest checks: absent
    # -> excluded green, drumbeat RED (never ran). The bare-call must not crash.
    by_key = {c.key: c.status for c in status.checks}
    assert by_key["temporal_log_finiteness"] == "green"
    assert by_key["structural_integrity"] == "green"
    assert by_key["candidate_completeness"] == "green"
    assert by_key["excluded_reason_breakdown"] == "green"


def test_compute_research_health_pre_schema_conn_degrades_not_crash(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")  # NO ensure_schema
    status = compute_research_health(conn, exports_root=tmp_path / "none", now=_NOW)
    assert isinstance(status, ResearchHealthStatus)
    by_key = {c.key: c.status for c in status.checks}
    # schema-dependent checks degrade to yellow "schema unavailable"
    assert by_key["temporal_log_finiteness"] == "yellow"
    assert by_key["structural_integrity"] == "yellow"
    assert by_key["candidate_completeness"] == "yellow"


def test_compute_research_health_is_read_only(tmp_path: Path) -> None:
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    conn.close()
    ro_uri = db.resolve().as_uri() + "?mode=ro"
    ro_conn = sqlite3.connect(ro_uri, uri=True)
    try:
        status = compute_research_health(
            ro_conn, exports_root=_fresh_exports_root(tmp_path), now=_NOW)
    finally:
        ro_conn.close()
    assert isinstance(status, ResearchHealthStatus)  # no readonly-write error


def test_generated_ts_uses_injected_now_as_aware_utc(tmp_path: Path) -> None:
    # now=2026-06-14T20:31:00 naive (Hawaii HST = UTC-10) -> 06:31 next-day UTC.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    now = datetime(2026, 6, 14, 20, 31, 0)
    status = compute_research_health(
        conn, exports_root=_fresh_exports_root_for(tmp_path, now), now=now)
    assert status.generated_ts == "2026-06-15T06:31:00+00:00"
    assert status.to_dict()["generated_ts"] == "2026-06-15T06:31:00+00:00"


def _fresh_exports_root_for(tmp_path: Path, now: datetime) -> Path:
    import json

    ts = (now.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
          .astimezone(ZoneInfo("UTC")) - timedelta(days=1))
    name = "shadow-expectancy-" + ts.strftime("%Y%m%dT%H%M%S") + "Z"
    root = tmp_path / "research2"
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps({"funnel": {
        "detection_level": {"unique_signals": 100},
        "per_hypothesis": {"H": {"excluded": {"invalid_ohlc": 1}}},
        "unattributed": {},
    }}), encoding="utf-8")
    return root


def test_aggregate_normalizes_aware_now(tmp_path: Path) -> None:
    # an AWARE-UTC now and its equivalent naive-Hawaii-local -> same statuses AND
    # the same generated_ts (both normalize to the same instant).
    # 2026-06-14T20:31:00 HST == 2026-06-15T06:31:00+00:00 UTC.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    naive_hst = datetime(2026, 6, 14, 20, 31, 0)
    aware_utc = datetime(2026, 6, 15, 6, 31, 0, tzinfo=ZoneInfo("UTC"))
    root = _fresh_exports_root_for(tmp_path, naive_hst)
    a = compute_research_health(conn, exports_root=root, now=naive_hst)
    b = compute_research_health(conn, exports_root=root, now=aware_utc)
    assert a.generated_ts == b.generated_ts == "2026-06-15T06:31:00+00:00"
    assert [c.status for c in a.checks] == [c.status for c in b.checks]
