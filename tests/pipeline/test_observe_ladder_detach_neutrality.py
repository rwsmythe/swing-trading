"""D90 N-V: the detach is neutral on an ordinary night and differs ONLY in the
provider LABEL of observe-only tickers on a carry night (RD ruling (c), two
world pairs; plan L-1, L-2).

Two worlds run the REAL `_step_pattern_observe` -> the REAL `OhlcvCache` with
the production bars hook's composition installed (`runner.py`
`_install_pipeline_marketdata_caches`): the REAL `fetch_window_via_ladder` and
the REAL `resolve_full_archive_bars`, with ONLY the Schwab leg
(`get_price_history`) replaced by a fixture (plan L-4). Carry is a fixture
parameter, `schwab_end`: the Schwab window ends at the observation date on a
carry night and at the prior session otherwise. There is no clock predicate.

  OOT: observe-only; its Schwab leg succeeds.
  DPT: the detect pool; stored by a detect-shaped call before observe.
  FBK: observe-only; its Schwab leg raises, so the ladder's yfinance fallback
       runs (ledger K-5).

The today-world wraps `OhlcvCache.get_or_fetch` to force `use_ladder=True`
(the pre-D90 populate, which reached the ladder on every miss); the detach
world is production as merged. The Schwab bars equal the yfinance bars, so the
carry pair pins a LABEL only.

`run_world` applies its own patches inside `pytest.MonkeyPatch.context()` so a
scratch script can call it for the merge report (D89's N-V precedent).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

_DATES = [date(2026, 6, 4), date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9),
          date(2026, 6, 10)]
_SESSION = date(2026, 6, 10)
_DET_DATES = ("2026-06-05", "2026-06-08")
_TICKERS = ("OOT", "DPT", "FBK")


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

    class _Schwab:
        # The two attributes `_is_ladder_active` reads.
        environment = "production"
        marketdata_ladder_enabled = True

    class _Integrations:
        pass

    def __init__(self, db_path, cache_dir):
        self.paths = self._Paths(db_path, cache_dir)
        self.web = self._Web()
        self.archive = self._Archive()
        self.rs = self._RS()
        self.pipeline = self._Pipeline()
        self.integrations = self._Integrations()
        self.integrations.schwab = self._Schwab()


def run_world(tmp_path: Path, *, detach: bool, carry: bool) -> dict:
    """Build one world under `tmp_path`, run a detect-shaped call then observe.

    Returns {"rows", "warnings", "schwab_calls", "downloads",
    "store_before_observe", "det_ids", "schwab_files"}.
    """
    import swing.data.ohlcv_archive as arch
    import swing.integrations.schwab.marketdata_ladder as ladder
    import swing.pipeline.runner as rmod
    from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
    from swing.integrations.schwab.client import SchwabApiError
    from swing.integrations.schwab.models import OhlcvBar, SchwabPriceHistoryWindow
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
    det_ids: dict[str, list[int]] = {}
    for t in _TICKERS:
        det_ids[t] = [_plant_detection(conn, ticker=t, data_asof_date="2026-06-05",
                                       detection_date=d) for d in _DET_DATES]

    cache = tmp_path / "ohlcv"
    cache.mkdir(exist_ok=True)
    phase = {"name": "setup"}
    downloads: list[str] = []
    schwab_calls: list[tuple[str, str]] = []
    warnings: list[dict] = []
    schwab_end = date(2026, 6, 10) if carry else date(2026, 6, 9)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(arch, "_last_completed_session_today", lambda: _SESSION)
        mp.setattr("swing.web.ohlcv_cache.last_completed_session",
                   lambda *_a, **_k: _SESSION)
        mp.setattr(rmod, "last_completed_session", lambda *_a, **_k: _SESSION)
        mp.setattr(arch, "_load_archive_config_for_stagger", lambda: False)
        arch._full_refresh_stagger_enabled.cache_clear()
        try:
            for t in _TICKERS:
                arch._write_archive_atomic(
                    cache / f"{t}.parquet",
                    _table_frame([date(2026, 6, 4), date(2026, 6, 5),
                                  date(2026, 6, 8)]))
                arch._write_meta_atomic(cache / f"{t}.meta.json",
                                        {"last_full_refresh_date": "2026-06-08"})

            def _fake_download(tickers, *, start, end, **_kw):
                if phase["name"] == "observe":
                    downloads.append(tickers)
                return _table_frame(_window_dates(start, end, _DATES))

            mp.setattr(arch.yf, "download", _fake_download)

            def _fake_get_price_history(client, conn_, ticker, **_kw):
                schwab_calls.append((phase["name"], ticker))
                if ticker == "FBK":
                    raise SchwabApiError(503, "")
                return SchwabPriceHistoryWindow(ticker=ticker, bars=[
                    OhlcvBar(asof_date=d.isoformat(), open=10.0 + i,
                             high=11.0 + i, low=9.0 + i, close=10.5 + i,
                             volume=1000 + i)
                    for i, d in enumerate(_DATES) if d <= schwab_end])

            mp.setattr(ladder, "get_price_history", _fake_get_price_history)
            cfg = _Cfg(db_path, cache)

            def _yf_window(t, start, end):
                return arch.read_or_fetch_archive(
                    t, end_date=_SESSION, cache_dir=cache,
                    archive_history_days=1260)

            def _hook(t):
                window, tag = ladder.fetch_window_via_ladder(
                    t, start=None, end=None, cfg=cfg, schwab_client=object(),
                    yfinance_fallback_fn=_yf_window, conn=None, surface="pipeline",
                    pipeline_run_id=1, period_type="year", period=5,
                    frequency_type="daily", frequency=1)
                return ladder.resolve_full_archive_bars(
                    t, window, tag, yfinance_window_fn=_yf_window)

            if not detach:
                # Today's world: the pre-D90 populate reached the ladder.
                real = OhlcvCache.get_or_fetch
                mp.setattr(OhlcvCache, "get_or_fetch",
                           lambda self, *, use_ladder=True, **k:
                           real(self, use_ladder=True, **k))
            oc = OhlcvCache(cfg)
            oc.set_ladder_bars_fetcher(_hook)
            phase["name"] = "detect"
            oc.get_or_fetch(ticker="DPT", window_days=rmod.DETECT_OBSERVE_WINDOW_DAYS)
            store_before_observe = set(oc._bars_store)
            phase["name"] = "observe"
            rmod._step_pattern_observe(
                cfg=cfg, lease=_FakeLease(db_path, 1, "2026-06-10"),
                ohlcv_cache=oc, run_warnings=warnings)
        finally:
            arch._full_refresh_stagger_enabled.cache_clear()

    rows = conn.execute(
        "SELECT detection_id, observation_date, ohlc_today_json, status, "
        "status_change_event, sessions_since_detection "
        "FROM pattern_forward_observations "
        "ORDER BY detection_id, observation_date").fetchall()
    conn.close()
    schwab_files = {t for t in _TICKERS
                    if (cache / f"{t}.schwab_api.parquet").exists()}
    return {"rows": rows, "warnings": warnings, "schwab_calls": schwab_calls,
            "downloads": downloads, "store_before_observe": store_before_observe,
            "det_ids": det_ids, "schwab_files": schwab_files}


def _load(warnings: list[dict]) -> dict:
    return next(e for e in warnings if e.get("metric") == "observe_load")


def _shared_assertions(today: dict, detach: dict) -> None:
    """The ordinary test's (2)-(6), which hold on a carry night as well."""
    # (2) warnings equal; observe_load's counts.
    assert today["warnings"] == detach["warnings"]
    for world in (today, detach):
        entry = _load(world["warnings"])
        assert entry["observed"] == 6
        assert entry["fetch_window"] == 2  # the OOT and FBK misses
        assert entry["in_memory_hit"] == 4
        assert entry["resolve_reads"] == 3
    # (3) the Schwab calls: the in-fixture witness is the detach world's [].
    for world in (today, detach):
        assert [c for c in world["schwab_calls"] if c[0] == "detect"] == [
            ("detect", "DPT")]
    assert [c for c in today["schwab_calls"] if c[0] == "observe"] == [
        ("observe", "OOT"), ("observe", "FBK")]
    assert [c for c in detach["schwab_calls"] if c[0] == "observe"] == []
    # (4) CHARC's anti-vacuity: OOT and FBK miss the store.
    for world in (today, detach):
        assert world["store_before_observe"] == {("DPT", 400)}
    # (5) admissibility (2)'s residual, in-fixture.
    assert today["schwab_files"] == {"OOT", "DPT"}
    assert detach["schwab_files"] == {"DPT"}
    # (6) the archive refresh is the same: D90 removes only the Schwab leg.
    assert today["downloads"] == detach["downloads"]


def test_ordinary_night_rows_equal_with_and_without_the_detach(tmp_path) -> None:
    today = run_world(tmp_path / "today", detach=False, carry=False)
    detach = run_world(tmp_path / "detach", detach=True, carry=False)
    # (1) the rows, value for value, all yfinance.
    assert len(today["rows"]) == 6
    assert len(detach["rows"]) == 6
    assert today["rows"] == detach["rows"]
    for r in detach["rows"]:
        assert json.loads(r[2])["provider"] == "yfinance"
    _shared_assertions(today, detach)


def test_carry_night_rows_differ_only_on_the_observe_only_provider_label(
        tmp_path) -> None:
    today = run_world(tmp_path / "today", detach=False, carry=True)
    detach = run_world(tmp_path / "detach", detach=True, carry=True)
    # (1) six rows each, same order; every non-provider field equal.
    assert len(today["rows"]) == 6
    assert len(detach["rows"]) == 6
    differing: set[int] = set()
    providers: dict[int, tuple[str, str]] = {}
    for rt, rd in zip(today["rows"], detach["rows"]):
        assert rt[0] == rd[0] and rt[1] == rd[1]  # detection_id, observation_date
        assert rt[3:] == rd[3:]  # status, status_change_event, sessions_since
        jt, jd = json.loads(rt[2]), json.loads(rd[2])
        pt, pd_ = jt.pop("provider"), jd.pop("provider")
        assert jt == jd  # OHLC and volume equal: a label only
        providers[rt[0]] = (pt, pd_)
        if pt != pd_:
            differing.add(rt[0])
    # (2) the differing rows are EXACTLY OOT's.
    ids = detach["det_ids"]
    assert differing == set(ids["OOT"])
    for d in ids["OOT"]:
        assert providers[d] == ("schwab_api", "yfinance")
    for d in ids["DPT"]:
        assert providers[d] == ("schwab_api", "schwab_api")  # L-2
    for d in ids["FBK"]:
        assert providers[d] == ("yfinance", "yfinance")
    # (3) the ordinary test's (2)-(6).
    _shared_assertions(today, detach)
