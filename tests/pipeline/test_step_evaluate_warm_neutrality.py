"""D83 condition (v): the warm is MEASUREMENT-NEUTRAL for observe.

Two worlds run the REAL `warm_archives_batch`, the real archive write and the
real observe read (`_step_pattern_observe` -> `OhlcvCache.get_or_fetch` ->
`read_or_fetch_archive`, then `resolve_ohlcv_window`) over ONE deterministic
per-(ticker, date) bar table, with a fake `yf.download` that honours its
`start` / `end` kwargs, so the archive's content is what the paths produce. The
rotated-out ticker ROT has an open detection and an archive two sessions stale.

  (1) observation rows are IDENTICAL with and without the warm (an invariant
      pre and post; its teeth are shown by the merge-report mutation that makes
      the batch path return `close + 0.01`);
  (2) with the warm, observe makes ZERO single-ticker downloads; without it,
      exactly one -- the proof the warm reached observe.

`run_world` applies its own patches inside `pytest.MonkeyPatch.context()` so a
scratch script can call it for the merge report.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

_DATES = [date(2026, 6, 4), date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9),
          date(2026, 6, 10)]
_SESSION = date(2026, 6, 10)


def _bar(i: int) -> dict:
    return {"Open": 10.0 + i, "High": 11.0 + i, "Low": 9.0 + i,
            "Close": 10.5 + i, "Volume": 1000.0 + i}


def _table_frame(dates: list[date]) -> pd.DataFrame:
    rows = [_bar(_DATES.index(d)) for d in dates]
    return pd.DataFrame(rows, index=pd.to_datetime(dates))


def _window_dates(start, end) -> list[date]:
    s = pd.Timestamp(start).date()
    e = pd.Timestamp(end).date()
    return [d for d in _DATES if s <= d < e]


class _Cfg:
    class _Paths:
        def __init__(self, db_path, cache_dir):
            self.db_path = db_path
            self.prices_cache_dir = cache_dir

    class _Web:
        ohlcv_cache_ttl_seconds = 3600
        max_concurrent_ohlcv_fetches = 4

    class _Archive:
        archive_history_days = 1260

    class _RS:
        benchmark_ticker = "SPY"

    class _Pipeline:
        observe_max_pending_window_sessions = 30
        observe_max_post_trigger_window_sessions = 60
        detect_watch_pool_cap = None
        observe_max_pending_window_sessions_watch = None
        observe_max_post_trigger_window_sessions_watch = None

    def __init__(self, db_path, cache_dir):
        self.paths = self._Paths(db_path, cache_dir)
        self.web = self._Web()
        self.archive = self._Archive()
        self.rs = self._RS()
        self.pipeline = self._Pipeline()


def run_world(tmp_path: Path, *, warm: bool) -> dict:
    """Build one world under `tmp_path`, optionally warm, then observe.

    Returns {"rows": [...pattern_forward_observations rows...],
    "observe_single_calls": int, "calls": [(phase, arg_type), ...]}.
    """
    import swing.data.ohlcv_archive as arch
    import swing.pipeline.runner as rmod
    from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
    from swing.web.ohlcv_cache import OhlcvCache
    from tests.pipeline.conftest_temporal import _FakeLease, _plant_detection

    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, '2026-06-10T20:00:00', 'manual', '2026-06-10', '2026-06-11', "
        "'tok', 'running')")
    conn.commit()
    _plant_detection(conn, ticker="ROT", data_asof_date="2026-06-05")

    cache = tmp_path / "ohlcv"
    cache.mkdir(exist_ok=True)
    phase = {"name": "setup"}
    calls: list[tuple[str, str]] = []

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(arch, "_last_completed_session_today", lambda: _SESSION)
        mp.setattr("swing.web.ohlcv_cache.last_completed_session",
                   lambda *_a, **_k: _SESSION)
        mp.setattr(rmod, "last_completed_session", lambda *_a, **_k: _SESSION)
        mp.setattr(arch, "_load_archive_config_for_stagger", lambda: False)
        arch._full_refresh_stagger_enabled.cache_clear()
        try:
            # ROT's legacy archive (06-04, 06-05, 06-08) + meta, two sessions stale.
            arch._write_archive_atomic(
                cache / "ROT.parquet",
                _table_frame([date(2026, 6, 4), date(2026, 6, 5), date(2026, 6, 8)]))
            arch._write_meta_atomic(cache / "ROT.meta.json",
                                    {"last_full_refresh_date": "2026-06-08"})

            def _fake_download(tickers, *, start, end, **_kw):
                calls.append((phase["name"], type(tickers).__name__))
                ds = _window_dates(start, end)
                if isinstance(tickers, str):
                    return _table_frame(ds)
                fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
                cols = pd.MultiIndex.from_product([list(tickers), fields])
                df = pd.DataFrame(index=pd.to_datetime(ds), columns=cols, dtype=float)
                for t in tickers:
                    sub = _table_frame(ds)
                    for f in fields:
                        src = "Close" if f == "Adj Close" else f
                        df[(t, f)] = sub[src].values
                return df

            mp.setattr(arch.yf, "download", _fake_download)
            cfg = _Cfg(db_path, cache)
            lease = _FakeLease(db_path, 1, "2026-06-10")
            if warm:
                phase["name"] = "warm"
                rmod._prewarm_evaluate_archives(
                    cfg=cfg, candidate_tickers=[], universe_tickers=[],
                    run_now=datetime(2026, 6, 10, 20, 0), run_warnings=[],
                    lease=lease,
                )
            phase["name"] = "observe"
            rmod._step_pattern_observe(
                cfg=cfg, lease=lease, ohlcv_cache=OhlcvCache(cfg), run_warnings=[])
        finally:
            arch._full_refresh_stagger_enabled.cache_clear()

    rows = conn.execute(
        "SELECT detection_id, observation_date, ohlc_today_json, status, "
        "status_change_event, sessions_since_detection "
        "FROM pattern_forward_observations "
        "ORDER BY detection_id, observation_date").fetchall()
    conn.close()
    return {
        "rows": rows,
        "observe_single_calls": sum(
            1 for p, kind in calls if p == "observe" and kind == "str"),
        "calls": calls,
    }


def test_observation_rows_identical_with_and_without_the_warm(tmp_path) -> None:
    world_a = run_world(tmp_path / "a", warm=False)
    world_b = run_world(tmp_path / "b", warm=True)
    # (1) measurement neutrality: the same rows, value for value.
    assert len(world_a["rows"]) == 1
    assert len(world_b["rows"]) == 1
    assert world_a["rows"] == world_b["rows"]
    # (2) the warm took effect: observe's archive read was a cache hit.
    assert world_a["observe_single_calls"] == 1
    assert world_b["observe_single_calls"] == 0
