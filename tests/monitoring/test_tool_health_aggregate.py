"""Task 5 -- compute_tool_health aggregator (worst-of + envelope + LOCKs)."""
from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta

from swing.config import Config
from swing.data.db import connect, ensure_schema
from swing.data.models import WeatherRun
from swing.data.repos.pipeline import (
    finalize_run,
    insert_pipeline_run,
)
from swing.data.repos.weather import upsert_weather_run
from swing.evaluation.dates import (
    action_session_for_run,
    last_completed_session,
)
from swing.monitoring.tool_health import ToolHealthStatus, compute_tool_health


def _build_db(tmp_path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    return db_path


def _seed_complete_run(conn, *, action_session_date):
    rid, tok = insert_pipeline_run(
        conn, started_ts="2026-06-14T00:00:00", trigger="manual",
        data_asof_date=action_session_date, action_session_date=action_session_date,
        lease_heartbeat_ts="2026-06-14T00:00:00",
    )
    finalize_run(conn, run_id=rid, lease_token=tok, state="complete",
                 finished_ts="2026-06-14T00:00:00")


def _seed_running_wedged(conn, now):
    rid, tok = insert_pipeline_run(
        conn, started_ts="2026-06-14T00:00:00", trigger="manual",
        data_asof_date="2026-06-15", action_session_date="2026-06-15",
        lease_heartbeat_ts="2026-06-14T00:00:00",
    )
    hb = (now - timedelta(seconds=400)).isoformat()
    step = (now - timedelta(seconds=1000)).isoformat()
    conn.execute(
        "UPDATE pipeline_runs SET lease_heartbeat_ts=?, last_step_progress_ts=? "
        "WHERE id=?", (hb, step, rid))


def _seed_weather(conn, *, asof_date):
    upsert_weather_run(conn, WeatherRun(
        id=None, run_ts="2026-06-17T05:00:00", asof_date=asof_date, ticker="QQQ",
        status="Bullish", close=400.0, sma10=None, sma20=None, sma50=None,
        slope20_5bar=None, slope10_5bar=None, rationale=None))


def _fresh_parquet(tmp_path, now, *, days=1):
    from zoneinfo import ZoneInfo
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    p = cache / "AAPL.parquet"
    p.write_bytes(b"x")
    target = now.replace(tzinfo=ZoneInfo("Pacific/Honolulu")) - timedelta(days=days)
    ts = target.timestamp()
    os.utime(p, (ts, ts))
    return cache


def test_all_green_overall_green(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    with conn:
        _seed_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        _seed_weather(conn, asof_date=last_completed_session(now).isoformat())
    cache = _fresh_parquet(tmp_path, now, days=1)
    status = compute_tool_health(conn, cfg=None, prices_cache_dir=cache, now=now)
    assert status.overall == "green"
    assert len(status.checks) >= 5


def test_one_red_makes_overall_red(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    cfg = Config.from_defaults()
    with conn:
        _seed_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        _seed_weather(conn, asof_date=last_completed_session(now).isoformat())
        _seed_running_wedged(conn, now)  # red
    cache = _fresh_parquet(tmp_path, now, days=1)
    status = compute_tool_health(conn, cfg=cfg, prices_cache_dir=cache, now=now)
    assert status.overall == "red"


def test_one_yellow_no_red_overall_yellow(tmp_path):
    now = datetime(2026, 6, 17, 21, 0)
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    with conn:
        _seed_complete_run(conn, action_session_date=action_session_for_run(now).isoformat())
        _seed_weather(conn, asof_date=last_completed_session(now).isoformat())
    cache = _fresh_parquet(tmp_path, now, days=5)  # 5d stale -> yellow
    status = compute_tool_health(conn, cfg=None, prices_cache_dir=cache, now=now)
    assert status.overall == "yellow"


def test_compute_tool_health_bare_conn_call_shape(tmp_path):
    # The sec-3 locked shape compute_tool_health(conn) against a SCHEMA-PRESENT
    # but EMPTY DB: cfg/cache-dependent checks -> green/"n/a"; operational-DATA
    # checks -> red. Distinguishes "missing config = green n/a" from
    # "missing data = red".
    now = datetime(2026, 6, 17, 21, 0)
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    status = compute_tool_health(conn)
    assert isinstance(status, ToolHealthStatus)
    by_key = {c.key: c for c in status.checks}
    assert by_key["schwab_token_ttl"].status == "green"
    assert "n/a" in by_key["schwab_token_ttl"].summary.lower()
    assert by_key["ohlcv_freshness"].status == "green"
    assert "n/a" in by_key["ohlcv_freshness"].summary.lower()
    assert by_key["pipeline_freshness"].status == "red"
    assert by_key["weather_freshness"].status == "red"


def test_compute_tool_health_pre_schema_conn_degrades_not_crash():
    # bare :memory: (no ensure_schema -> no tables) does NOT raise; schema-
    # dependent checks degrade to yellow "schema unavailable".
    conn = sqlite3.connect(":memory:")
    status = compute_tool_health(conn)
    assert isinstance(status, ToolHealthStatus)
    by_key = {c.key: c for c in status.checks}
    assert any("schema unavailable" in c.summary.lower() for c in status.checks)
    assert by_key["pipeline_schema"].status == "yellow"
    assert by_key["weather_freshness"].status == "yellow"


def test_compute_tool_health_is_read_only(tmp_path):
    # The read-only LOCK proof: a write attempt on a mode=ro conn raises
    # OperationalError. compute_tool_health must return normally.
    now = datetime(2026, 6, 17, 21, 0)
    db_path = _build_db(tmp_path)
    rw = connect(db_path)
    with rw:
        _seed_complete_run(rw, action_session_date=action_session_for_run(now).isoformat())
        _seed_weather(rw, asof_date=last_completed_session(now).isoformat())
    rw.close()
    ro = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        status = compute_tool_health(ro, cfg=None, prices_cache_dir=None, now=now)
        assert isinstance(status, ToolHealthStatus)
    finally:
        ro.close()


def test_generated_ts_uses_injected_now(tmp_path):
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    now = datetime(2026, 6, 14, 20, 31, 0)
    status = compute_tool_health(conn, now=now)
    assert status.generated_ts == "2026-06-14T20:31:00"
    assert status.to_dict()["generated_ts"] == "2026-06-14T20:31:00"


def test_compute_tool_health_normalizes_aware_now(tmp_path):
    # Codex R3 MAJOR #1. aware-UTC 2026-06-15T19:00Z == 2026-06-15 09:00 HST.
    # Correct (convert): action_session=Mon 06-15, last_completed=Fri 06-12.
    # Bug (relabel 19:00 as HST): anchors shift forward -> different colors.
    # Seed so the anchors are color-sensitive; assert aware == equiv-naive result.
    aware = datetime(2026, 6, 15, 19, 0, 0, tzinfo=UTC)
    naive = datetime(2026, 6, 15, 9, 0, 0)
    db_path = _build_db(tmp_path)
    conn = connect(db_path)
    with conn:
        # cover the correct action_session (Mon 06-15) so freshness is green
        _seed_complete_run(conn, action_session_date="2026-06-15")
        # cover the correct last_completed_session (Fri 06-12) so weather is green
        _seed_weather(conn, asof_date="2026-06-12")
    s_aware = compute_tool_health(conn, now=aware)
    s_naive = compute_tool_health(conn, now=naive)
    aware_map = {c.key: c.status for c in s_aware.checks}
    naive_map = {c.key: c.status for c in s_naive.checks}
    assert aware_map == naive_map
    # the seed is genuinely color-sensitive: pipeline + weather are green under
    # the correct conversion (would be RED if relabeled forward).
    assert aware_map["pipeline_freshness"] == "green"
    assert aware_map["weather_freshness"] == "green"
