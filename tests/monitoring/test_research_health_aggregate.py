"""Task 7 -- compute_research_health aggregator (worst-of + envelope + aware-UTC
clock normalization). End-to-end against a seeded DB + tmp manifest/exports
dirs; the read-only LOCK proof.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from swing.data.db import ensure_schema
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import insert_observation
from swing.evaluation.dates import last_completed_session
from swing.monitoring.research_health import (
    ResearchHealthStatus,
    compute_research_health,
)

# Codex R6 MINOR: anchor the frozen clock to the REAL wall clock so the
# ResearchHealthStatus freshness gate (generated_ts must be <= 7d) never goes
# stale as the calendar advances. _NOW is "yesterday noon" Hawaii-local; the
# seeded observation dates are computed from last_completed_session(_NOW), so the
# coverage scenario stays valid on any run date.
_NOW = (datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
        - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
_LAST_COMPLETED = last_completed_session(_NOW)
_XNYS = xcals.get_calendar("XNYS")
# the most-recent 6 NYSE sessions ending at _LAST_COMPLETED (a contiguous,
# weekend-aware window) + the cutoff = the session just before the first.
_SESSION_WINDOW = [
    ts.date() for ts in _XNYS.sessions_in_range(
        pd.Timestamp(_LAST_COMPLETED) - pd.Timedelta(days=12),
        pd.Timestamp(_LAST_COMPLETED))
][-6:]
_SESSIONS = tuple(d.isoformat() for d in _SESSION_WINDOW)
# the detector cutoff = the session BEFORE the first observed session (so the
# first observed session is the first-expected -> a contiguous full window).
_ASOF = _XNYS.previous_session(pd.Timestamp(_SESSION_WINDOW[0])).date().isoformat()
_FINITE_OHLC = '{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, ' \
    '"volume": 100.0, "provider": "yfinance"}'


def _seed_green_db(conn: sqlite3.Connection) -> None:
    det = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="AAA", detection_date=_SESSIONS[0],
        data_asof_date=_ASOF, pattern_class="vcp",
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
        ("2026-06-12T00:00:00", _LAST_COMPLETED.isoformat(),
         _SESSIONS[-1], 1, 1, 0, 0, 0, 0))
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
    # plant a NaN-Close observation on the EXISTING green detection's last
    # session via a second (terminal) detection so coverage stays clean and only
    # finiteness goes red. Use a clock-relative cutoff + the last session.
    det2 = insert_detection_event(conn, PatternDetectionEvent(
        detection_id=None, ticker="ZZZ", detection_date=_SESSIONS[-1],
        data_asof_date=_SESSIONS[-2], pattern_class="vcp",
        structural_anchors_json="{}", composite_score=1.0, detector_version="t",
        source="synthetic", per_pattern_metadata_json="{}",
        created_at="2026-06-12T00:00:00"))
    conn.execute(
        "INSERT INTO pattern_forward_observations "
        "(detection_id, observation_date, ohlc_today_json, status, "
        "sessions_since_detection, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (det2, _SESSIONS[-1],
         '{"open": 1.0, "high": 2.0, "low": 0.5, "close": NaN, '
         '"volume": 100.0, "provider": "yfinance"}',
         "invalidated", 1, "2026-06-12T00:00:00"))
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
    # A naive-Hawaii-local now (HST = UTC-10) -> aware-UTC stamp 10h later. Anchor
    # on a RECENT naive-HST instant (clock-relative -- Codex R6 MINOR -- so the
    # freshness gate never rejects it) and compute the expected UTC arithmetic.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    now = (datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
           - timedelta(hours=2)).replace(microsecond=0)
    expected = (now.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
                .astimezone(ZoneInfo("UTC")).isoformat(timespec="seconds"))
    status = compute_research_health(
        conn, exports_root=_fresh_exports_root_for(tmp_path, now), now=now)
    assert status.generated_ts == expected
    assert status.to_dict()["generated_ts"] == expected
    # the conversion is a +10h offset (HST -> UTC), tz-aware UTC suffix.
    assert expected.endswith("+00:00")


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


def test_manifest_dir_overrides_exports_root_for_manifest_checks(tmp_path: Path) -> None:
    # Codex R5 MINOR: manifest_dir is NOT a silent no-op -- it overrides the
    # engine-artifact root the manifest checks scan. Point exports_root at an
    # EMPTY dir (manifest absent -> drumbeat red) but manifest_dir at a fresh
    # root -> drumbeat green.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    fresh_root = _fresh_exports_root(tmp_path)
    status = compute_research_health(
        conn, exports_root=empty_root, manifest_dir=fresh_root, now=_NOW)
    by_key = {c.key: c.status for c in status.checks}
    assert by_key["drumbeat_liveness"] == "green"  # read from manifest_dir
    assert by_key["excluded_reason_breakdown"] == "green"


def test_aggregate_normalizes_aware_now(tmp_path: Path) -> None:
    # an AWARE-UTC now and its equivalent naive-Hawaii-local -> same statuses AND
    # the same generated_ts (both normalize to the same instant). Clock-relative
    # (Codex R6 MINOR) so the freshness gate never rejects the stamp.
    db = tmp_path / "swing.db"
    conn = ensure_schema(db)
    _seed_green_db(conn)
    naive_hst = (datetime.now(ZoneInfo("Pacific/Honolulu")).replace(tzinfo=None)
                 - timedelta(hours=2)).replace(microsecond=0)
    aware_utc = naive_hst.replace(tzinfo=ZoneInfo("Pacific/Honolulu")).astimezone(
        ZoneInfo("UTC"))
    expected = aware_utc.isoformat(timespec="seconds")
    root = _fresh_exports_root_for(tmp_path, naive_hst)
    a = compute_research_health(conn, exports_root=root, now=naive_hst)
    b = compute_research_health(conn, exports_root=root, now=aware_utc)
    assert a.generated_ts == b.generated_ts == expected
    assert [c.status for c in a.checks] == [c.status for c in b.checks]
