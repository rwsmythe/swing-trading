"""Task 6 -- the scripts/tool_health.py operator probe surface."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from swing.config import Config
from swing.data.db import connect, ensure_schema
from swing.data.models import WeatherRun
from swing.data.repos.pipeline import finalize_run, insert_pipeline_run
from swing.data.repos.weather import upsert_weather_run
from swing.evaluation.dates import action_session_for_run, last_completed_session

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "tool_health.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("tool_health_script", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_green_db(tmp_path):
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    from datetime import datetime
    now = datetime(2026, 6, 17, 21, 0)
    conn = connect(db_path)
    with conn:
        rid, tok = insert_pipeline_run(
            conn, started_ts="2026-06-14T00:00:00", trigger="manual",
            data_asof_date=action_session_for_run(now).isoformat(),
            action_session_date=action_session_for_run(now).isoformat(),
            lease_heartbeat_ts="2026-06-14T00:00:00")
        finalize_run(conn, run_id=rid, lease_token=tok, state="complete",
                     finished_ts="2026-06-14T00:00:00")
        upsert_weather_run(conn, WeatherRun(
            id=None, run_ts="2026-06-17T05:00:00",
            asof_date=last_completed_session(now).isoformat(), ticker="QQQ",
            status="Bullish", close=400.0, sma10=None, sma20=None, sma50=None,
            slope20_5bar=None, slope10_5bar=None, rationale=None))
    conn.close()
    return db_path, now


def _fresh_cache(tmp_path, now, *, days=1):
    from zoneinfo import ZoneInfo
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    p = cache / "AAPL.parquet"
    p.write_bytes(b"x")
    ts = (now.replace(tzinfo=ZoneInfo("Pacific/Honolulu")) - timedelta(days=days)).timestamp()
    os.utime(p, (ts, ts))
    return cache


def _seed_wedged(db_path, now):
    conn = connect(db_path)
    with conn:
        rid, _ = insert_pipeline_run(
            conn, started_ts="2026-06-14T00:00:00", trigger="manual",
            data_asof_date="2026-06-15", action_session_date="2026-06-15",
            lease_heartbeat_ts="2026-06-14T00:00:00")
        hb = (now - timedelta(seconds=400)).isoformat()
        step = (now - timedelta(seconds=1000)).isoformat()
        conn.execute(
            "UPDATE pipeline_runs SET lease_heartbeat_ts=?, last_step_progress_ts=? "
            "WHERE id=?", (hb, step, rid))
    conn.close()


def _patch_cfg(monkeypatch, cache_dir):
    """Make Config.from_defaults return a cfg with empty schwab client_id (n/a)
    and the tmp cache dir, so the script resolves controlled paths."""
    real = Config.from_defaults()
    import dataclasses
    paths = dataclasses.replace(real.paths, prices_cache_dir=cache_dir)
    cfg = dataclasses.replace(real, paths=paths)
    monkeypatch.setattr(Config, "from_defaults", classmethod(lambda cls: cfg))
    return cfg


def test_script_all_clear_exit_zero(tmp_path, monkeypatch):
    db_path, now = _build_green_db(tmp_path)
    cache = _fresh_cache(tmp_path, now, days=1)
    _patch_cfg(monkeypatch, cache)
    mod = _load_script_module()
    monkeypatch.setattr(mod, "_resolve_now", lambda: now, raising=False)
    rc = mod.main(["--db", str(db_path)])
    assert rc == 0


def test_script_attention_exit_one(tmp_path, monkeypatch, capsys):
    db_path, now = _build_green_db(tmp_path)
    cache = _fresh_cache(tmp_path, now, days=1)
    _seed_wedged(db_path, now)  # red
    _patch_cfg(monkeypatch, cache)
    mod = _load_script_module()
    monkeypatch.setattr(mod, "_resolve_now", lambda: now, raising=False)
    rc = mod.main(["--db", str(db_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ATTENTION (1)" in out
    assert "pipeline_wedged" in out


def test_script_json_flag(tmp_path, monkeypatch, capsys):
    db_path, now = _build_green_db(tmp_path)
    cache = _fresh_cache(tmp_path, now, days=1)
    _seed_wedged(db_path, now)  # red -> overall red, but --json exits 0
    _patch_cfg(monkeypatch, cache)
    mod = _load_script_module()
    monkeypatch.setattr(mod, "_resolve_now", lambda: now, raising=False)
    rc = mod.main(["--db", str(db_path), "--json"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["monitor"] == "tool_health"
    assert parsed["overall"] in {"green", "yellow", "red"}
    assert isinstance(parsed["checks"], list)
    assert rc == 0  # --json always exits 0 (machine surface)


def test_script_output_is_ascii(tmp_path, monkeypatch):
    # platform-agnostic: the subprocess stdout BYTES must decode as pure ASCII
    # (guarantees ANY cp1252 encoder is safe). capsys is INSUFFICIENT (bypasses
    # the OS encoder). Seed a RED state so the string-heavy ATTENTION path runs.
    db_path, now = _build_green_db(tmp_path)
    cache = _fresh_cache(tmp_path, now, days=9)  # red ohlcv -> ATTENTION
    _seed_wedged(db_path, now)
    _patch_cfg(monkeypatch, cache)  # only affects in-process; subprocess uses real
    # The subprocess can't see the monkeypatched Config; rely on the real config's
    # empty client_id (schwab n/a) + the --db override. The ASCII guarantee holds
    # regardless of which checks fire.
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db", str(db_path)],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    # must not raise -- every byte ASCII:
    result.stdout.decode("ascii")
    result.stderr.decode("ascii")


@pytest.mark.skipif(sys.platform != "win32", reason="cp1252 encoder is Windows-specific")
def test_script_output_survives_cp1252(tmp_path):
    db_path, _ = _build_green_db(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--db", str(db_path)],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONIOENCODING": "cp1252"},
    )
    # a non-ASCII glyph would crash the cp1252 encoder -> nonzero + traceback.
    assert b"UnicodeEncodeError" not in result.stderr
