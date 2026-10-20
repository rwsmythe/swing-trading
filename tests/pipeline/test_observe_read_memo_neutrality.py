"""D89 N-V: the per-step read memo is MEASUREMENT-NEUTRAL for observe (H (ii),
P12).

Two worlds run the REAL `_step_pattern_observe` -> the REAL `OhlcvCache`
(no ladder) -> the REAL `read_or_fetch_archive` gap fetch, then the REAL
`resolve_ohlcv_window` with `migrate=True` over legacy `{T}.parquet` files
(the C-2 `_backward_compat_rename` path), with a fake `yf.download` that
honours its `start` / `end` kwargs. The no-memo world is built by wrapping
`_bar_for_date` to drop its `memo` argument (CHARC's H (ii)); the production
path has one shape.

  AAA x3 (a bar on 06-10), NOB x3 (the populate does not raise; no 06-10 bar),
  RSE x2 (every populate raises).

  (1) observation rows identical (the P12 column set; created_at and
      observation_id excluded BY NAME: wall clock / assigned);
  (2) warnings identical once `resolve_reads` is popped from observe_load;
  (3) resolve reads: 8 without the memo, 4 with it (AAA 1 + NOB 1 + RSE 2);
  (4) the populate's downloads identical (D1);
  (5) the Shape-A frames identical (C-2's content side, plan AL-12 / K-4).

`run_world` applies its own patches inside `pytest.MonkeyPatch.context()` so a
scratch script can call it for the merge report (the precedent is
`test_step_evaluate_warm_neutrality.py`).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

_DATES = [date(2026, 6, 4), date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9),
          date(2026, 6, 10)]
_SESSION = date(2026, 6, 10)
_DET_DATES = ("2026-06-05", "2026-06-08", "2026-06-09")


def _bar(i: int) -> dict:
    return {"Open": 10.0 + i, "High": 11.0 + i, "Low": 9.0 + i,
            "Close": 10.5 + i, "Volume": 1000.0 + i}


def _table_frame(dates: list[date]) -> pd.DataFrame:
    rows = [_bar(_DATES.index(d)) for d in dates]
    return pd.DataFrame(rows, index=pd.to_datetime(dates))


def _window_dates(start, end, served: list[date]) -> list[date]:
    s = pd.Timestamp(start).date()
    e = pd.Timestamp(end).date()
    return [d for d in served if s <= d < e]


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


_SERVED = {
    "AAA": list(_DATES),
    "NOB": [d for d in _DATES if d != date(2026, 6, 10)],
    "RSE": [],
}


def run_world(tmp_path: Path, *, memo: bool) -> dict:
    """Build one world under `tmp_path`, then observe with or without the memo.

    Returns {"rows", "warnings", "reads", "downloads", "shape_a"}.
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
    for ticker, n in (("AAA", 3), ("NOB", 3), ("RSE", 2)):
        for i in range(n):
            _plant_detection(conn, ticker=ticker, data_asof_date="2026-06-05",
                             detection_date=_DET_DATES[i])

    cache = tmp_path / "ohlcv"
    cache.mkdir(exist_ok=True)
    phase = {"name": "setup"}
    downloads: list[str] = []
    reads = {"n": 0}
    warnings: list[dict] = []

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(arch, "_last_completed_session_today", lambda: _SESSION)
        mp.setattr("swing.web.ohlcv_cache.last_completed_session",
                   lambda *_a, **_k: _SESSION)
        mp.setattr(rmod, "last_completed_session", lambda *_a, **_k: _SESSION)
        mp.setattr(arch, "_load_archive_config_for_stagger", lambda: False)
        arch._full_refresh_stagger_enabled.cache_clear()
        try:
            for t in ("AAA", "NOB"):
                arch._write_archive_atomic(
                    cache / f"{t}.parquet",
                    _table_frame([date(2026, 6, 4), date(2026, 6, 5),
                                  date(2026, 6, 8)]))
                arch._write_meta_atomic(cache / f"{t}.meta.json",
                                        {"last_full_refresh_date": "2026-06-08"})

            def _fake_download(tickers, *, start, end, **_kw):
                if phase["name"] == "observe":
                    downloads.append(tickers)
                served = _SERVED[tickers]
                if not served:
                    return pd.DataFrame()
                return _table_frame(_window_dates(start, end, served))

            mp.setattr(arch.yf, "download", _fake_download)

            real_resolve = arch.resolve_ohlcv_window

            def _counting(*a, **k):
                reads["n"] += 1
                return real_resolve(*a, **k)

            mp.setattr(arch, "resolve_ohlcv_window", _counting)
            if not memo:
                real = rmod._bar_for_date
                mp.setattr(rmod, "_bar_for_date",
                           lambda *a, memo=None, **k: real(*a, **k))
            cfg = _Cfg(db_path, cache)
            lease = _FakeLease(db_path, 1, "2026-06-10")
            phase["name"] = "observe"
            rmod._step_pattern_observe(
                cfg=cfg, lease=lease, ohlcv_cache=OhlcvCache(cfg),
                run_warnings=warnings)
        finally:
            arch._full_refresh_stagger_enabled.cache_clear()

    rows = conn.execute(
        "SELECT detection_id, observation_date, ohlc_today_json, status, "
        "status_change_event, sessions_since_detection "
        "FROM pattern_forward_observations "
        "ORDER BY detection_id, observation_date").fetchall()
    conn.close()
    shape_a = {t: pd.read_parquet(cache / f"{t}.yfinance.parquet")
               for t in ("AAA", "NOB")}
    return {"rows": rows, "warnings": warnings, "reads": reads["n"],
            "downloads": downloads, "shape_a": shape_a}


def _popped(warnings: list[dict]) -> list[dict]:
    out = []
    for e in warnings:
        e = dict(e)
        if e.get("metric") == "observe_load":
            e.pop("resolve_reads", None)  # (3) asserts its presence
        out.append(e)
    return out


def _load(warnings: list[dict]) -> dict:
    return next(e for e in warnings if e.get("metric") == "observe_load")


def test_observation_rows_identical_with_and_without_the_memo(tmp_path) -> None:
    nomemo = run_world(tmp_path / "a", memo=False)
    withmemo = run_world(tmp_path / "b", memo=True)
    # (1) measurement neutrality: the same rows, value for value.
    assert len(nomemo["rows"]) == 3
    assert len(withmemo["rows"]) == 3
    assert nomemo["rows"] == withmemo["rows"]
    # (2) the warnings, once resolve_reads is popped: five no-bar entries
    # (NOB x3, RSE x2) in detection order, and the populate telemetry.
    assert _popped(nomemo["warnings"]) == _popped(withmemo["warnings"])
    no_bar = [e["ticker"] for e in withmemo["warnings"]
              if e.get("reason") == "no bar for observation_date"]
    assert no_bar == ["NOB", "NOB", "NOB", "RSE", "RSE"]
    for world in (nomemo, withmemo):
        assert _load(world["warnings"])["fetch_window"] == 4
        assert _load(world["warnings"])["in_memory_hit"] == 4
    # (3) the read count: every iteration without the memo; once per ticker
    # after a non-raising populate, and on every raise, with it.
    assert nomemo["reads"] == 8
    assert _load(nomemo["warnings"])["resolve_reads"] == 8
    assert withmemo["reads"] == 4
    assert _load(withmemo["warnings"])["resolve_reads"] == 4
    # (4) the populate is identical (D1).
    assert nomemo["downloads"] == withmemo["downloads"]
    # (5) the Shape-A content is identical (C-2).
    for t in ("AAA", "NOB"):
        pd.testing.assert_frame_equal(nomemo["shape_a"][t], withmemo["shape_a"][t])
