"""D89: the observe step's per-step read memo (plan T1).

`_bar_for_date` memoizes the `(df, provenance)` pair `resolve_ohlcv_window`
returned, keyed by `_observe_memo_key(ticker, observation_date)`, ONLY when
THIS call's populate (`ohlcv_cache.get_or_fetch`) returned without raising
(RD's C3 literal). A present key is selected from first (E1). The populate
runs on every call (D1). `resolve_reads` on the `observe_load` entry counts
the resolve calls the step made.

Every test drives a REAL `OhlcvCache` (its `_fetch_bars_window` scripted per
ticker) over a REAL Shape-A archive in tmp, and counts the REAL
`resolve_ohlcv_window` with an independent counter.

T-E is a DECLARED DIFFERENCE inside H3 (plan L-3), not a neutrality test.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from swing.data.repos.pattern_forward_observations import (
    get_observations_for_detection,
)
from tests.pipeline.conftest_temporal import (  # noqa: F401
    _StubOhlcvCache,
    _build_bars,
    _cfg,
    _FakeLease,
    _plant_detection,
    tmp_db_at_head,
)

_OBS = "2026-05-29"
_DET_DATES = ("2026-05-26", "2026-05-27", "2026-05-28")
_COLS = ["asof_date", "open", "high", "low", "close", "volume"]


def _test_cfg(tmp_path, db_path, *, ttl=3600):
    # cfg.web / cfg.archive are attached BEFORE OhlcvCache(cfg) is built:
    # OhlcvCache.__init__ copies the TTL.
    cfg = _cfg(tmp_path, db_path)
    cfg.web = SimpleNamespace(ohlcv_cache_ttl_seconds=ttl,
                              max_concurrent_ohlcv_fetches=4)
    cfg.archive = SimpleNamespace(archive_history_days=1260)
    return cfg


def _plant(conn, ticker, n):
    return [_plant_detection(conn, ticker=ticker, data_asof_date="2026-05-25",
                             detection_date=_DET_DATES[i]) for i in range(n)]


def _put(cache_dir, ticker, provider, rows):
    from swing.data.ohlcv_archive import write_window
    write_window(ticker, pd.DataFrame(
        [(d, c, c, c, c, 1e6) for d, c in rows], columns=_COLS),
        provider, cache_dir=cache_dir)


def _real_cache(cfg, monkeypatch, script):
    """A REAL OhlcvCache whose `_fetch_bars_window` pops the next scripted
    action for the ticker. A script overrun is recorded (the populate's
    `except Exception` would swallow a raise) and asserted by the caller."""
    from swing.web.ohlcv_cache import OhlcvCache
    cache = OhlcvCache(cfg)
    cache.overruns = []

    def _fetch(*, ticker, window_days):
        actions = script.get(ticker)
        if not actions:
            cache.overruns.append(ticker)
            return None
        action = actions.pop(0)
        if action == "frame":
            return _build_bars()
        if action is None:
            return None
        _kind, provider, rows, then = action
        _put(cfg.paths.prices_cache_dir, ticker, provider, rows)
        return _build_bars() if then == "frame" else None

    monkeypatch.setattr(cache, "_fetch_bars_window", _fetch)
    return cache


def _count_resolve(monkeypatch):
    import swing.data.ohlcv_archive as arch
    real = arch.resolve_ohlcv_window
    counter = {"n": 0}

    def _counting(*a, **k):
        counter["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(arch, "resolve_ohlcv_window", _counting)
    return counter


def _drive(cfg, db_path, cache, run_id=1):
    from swing.pipeline.runner import _step_pattern_observe
    w: list[dict] = []
    with patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS):
        _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, run_id, _OBS),
                              ohlcv_cache=cache, run_warnings=w)
    assert not getattr(cache, "overruns", []), cache.overruns
    return w


def load(w):
    return next(e for e in w if e.get("metric") == "observe_load")


def _no_bar(w):
    return [e for e in w if e.get("reason") == "no bar for observation_date"]


def _rows(conn, det_id):
    return [json.loads(o.ohlc_today_json)
            for o in get_observations_for_detection(conn, det_id)]


def test_raise_then_heal_later_detections_observe(
        tmp_db_at_head, tmp_path, monkeypatch):
    conn, db_path = tmp_db_at_head
    d1, d2, d3 = _plant(conn, "AAA", 3)
    cfg = _test_cfg(tmp_path, db_path)
    cache = _real_cache(cfg, monkeypatch, {"AAA": [
        None,
        ("write", "yfinance", [("2026-05-28", 8.8), ("2026-05-29", 9.0)], "frame"),
    ]})
    reads = _count_resolve(monkeypatch)
    w = _drive(cfg, db_path, cache)
    assert _rows(conn, d1) == []
    for d in (d2, d3):
        (row,) = _rows(conn, d)
        assert row["close"] == 9.0 and row["provider"] == "yfinance"
    nb = _no_bar(w)
    assert len(nb) == 1 and nb[0]["ticker"] == "AAA"
    assert load(w)["fetch_window"] == 2
    assert load(w)["in_memory_hit"] == 1
    assert reads["n"] == 2
    assert load(w)["resolve_reads"] == 2


def test_raise_over_archived_yfinance_then_schwab_write_outranks(
        tmp_db_at_head, tmp_path, monkeypatch):
    conn, db_path = tmp_db_at_head
    d1, d2, d3 = _plant(conn, "AAA", 3)
    cfg = _test_cfg(tmp_path, db_path)
    _put(cfg.paths.prices_cache_dir, "AAA", "yfinance",
         [("2026-05-28", 8.8), ("2026-05-29", 9.0)])
    cache = _real_cache(cfg, monkeypatch, {"AAA": [
        None,
        ("write", "schwab_api", [("2026-05-29", 9.5)], "frame"),
    ]})
    reads = _count_resolve(monkeypatch)
    w = _drive(cfg, db_path, cache)
    (r1,) = _rows(conn, d1)
    assert r1["close"] == 9.0 and r1["provider"] == "yfinance"
    for d in (d2, d3):
        (row,) = _rows(conn, d)
        assert row["close"] == 9.5 and row["provider"] == "schwab_api"
    assert reads["n"] == 2
    assert load(w)["resolve_reads"] == 2


def test_no_bar_ticker_is_read_once_after_a_non_raising_populate(
        tmp_db_at_head, tmp_path, monkeypatch):
    conn, db_path = tmp_db_at_head
    dets = _plant(conn, "NOB", 3)
    cfg = _test_cfg(tmp_path, db_path)
    _put(cfg.paths.prices_cache_dir, "NOB", "yfinance",
         [("2026-05-27", 8.7), ("2026-05-28", 8.8)])
    cache = _real_cache(cfg, monkeypatch, {"NOB": ["frame"]})
    reads = _count_resolve(monkeypatch)
    w = _drive(cfg, db_path, cache)
    for d in dets:
        assert _rows(conn, d) == []
    nb = _no_bar(w)
    assert len(nb) == 3
    assert all(e["ticker"] == "NOB" and e["observation_date"] == _OBS
               for e in nb)
    assert load(w)["fetch_window"] == 1
    assert load(w)["in_memory_hit"] == 2
    assert reads["n"] == 1
    assert load(w)["resolve_reads"] == 1


def test_memo_first_when_a_later_populate_raises_declared_h3_difference(
        tmp_db_at_head, tmp_path, monkeypatch):
    """A DECLARED DIFFERENCE inside H3 (plan L-3; orchestrator ruling E1), NOT
    a neutrality test. A TTL of -1 makes every lookup a miss (models a
    mid-step expiry). d2's populate writes 9.9 and then raises; under E1 the
    memoized key is selected first, so d2 carries 9.0 with ONE read. Today's
    code re-reads and gives 9.9."""
    conn, db_path = tmp_db_at_head
    d1, d2 = _plant(conn, "AAA", 2)
    cfg = _test_cfg(tmp_path, db_path, ttl=-1)
    _put(cfg.paths.prices_cache_dir, "AAA", "yfinance", [("2026-05-29", 9.0)])
    cache = _real_cache(cfg, monkeypatch, {"AAA": [
        "frame",
        ("write", "yfinance", [("2026-05-29", 9.9)], None),
    ]})
    reads = _count_resolve(monkeypatch)
    w = _drive(cfg, db_path, cache)
    (r1,) = _rows(conn, d1)
    (r2,) = _rows(conn, d2)
    assert r1["close"] == 9.0
    assert r2["close"] == 9.0  # the memo, though the archive now holds 9.9
    assert load(w)["fetch_window"] == 2
    assert load(w)["in_memory_hit"] == 0
    assert reads["n"] == 1
    assert load(w)["resolve_reads"] == 1


def test_memo_key_carries_the_observation_date(tmp_path, monkeypatch):
    from swing.pipeline.runner import _bar_for_date
    cfg = _test_cfg(tmp_path, tmp_path / "unused.db")
    _put(cfg.paths.prices_cache_dir, "AAA", "yfinance",
         [("2026-05-28", 8.0), ("2026-05-29", 9.0)])
    cache = _StubOhlcvCache({"AAA": _build_bars()})
    memo: dict = {}
    b1 = _bar_for_date(cfg, cache, "AAA", "2026-05-28", memo=memo)
    b2 = _bar_for_date(cfg, cache, "AAA", "2026-05-29", memo=memo)
    assert b1 is not None and b1["close"] == 8.0
    assert b2 is not None and b2["close"] == 9.0
    assert set(memo) == {("AAA", "2026-05-28"), ("AAA", "2026-05-29")}


def test_memo_does_not_outlive_the_step_call(
        tmp_db_at_head, tmp_path, monkeypatch):
    conn, db_path = tmp_db_at_head
    d1, d2 = _plant(conn, "AAA", 2)
    cfg = _test_cfg(tmp_path, db_path)
    _put(cfg.paths.prices_cache_dir, "AAA", "yfinance",
         [("2026-05-27", 8.7), ("2026-05-28", 8.8)])
    # ONE real cache: later lookups are TTL hits (no further script pops).
    cache = _real_cache(cfg, monkeypatch, {"AAA": ["frame"]})
    reads = _count_resolve(monkeypatch)
    w1 = _drive(cfg, db_path, cache, run_id=1)
    assert _rows(conn, d1) == [] and _rows(conn, d2) == []
    assert len(_no_bar(w1)) == 2
    assert load(w1)["resolve_reads"] == 1
    _put(cfg.paths.prices_cache_dir, "AAA", "yfinance", [("2026-05-29", 9.0)])
    w2 = _drive(cfg, db_path, cache, run_id=2)
    for d in (d1, d2):
        (row,) = _rows(conn, d)
        assert row["close"] == 9.0
    assert load(w2)["resolve_reads"] == 1
    assert reads["n"] == 2


def test_observe_load_gains_resolve_reads_and_loses_nothing(
        tmp_db_at_head, tmp_path, monkeypatch):
    conn, db_path = tmp_db_at_head
    _plant(conn, "AAA", 2)
    _plant(conn, "BBB", 1)
    cfg = _test_cfg(tmp_path, db_path)
    for t in ("AAA", "BBB"):
        _put(cfg.paths.prices_cache_dir, t, "yfinance", [("2026-05-29", 9.0)])
    cache = _real_cache(cfg, monkeypatch, {"AAA": ["frame"], "BBB": ["frame"]})
    _count_resolve(monkeypatch)
    w = _drive(cfg, db_path, cache)
    entry = load(w)
    assert set(entry) == {"step", "metric", "observed", "fetch_window",
                          "in_memory_hit", "resolve_reads"}
    assert entry["observed"] == 3
    assert entry["fetch_window"] == 2
    assert entry["in_memory_hit"] == 1
    assert entry["resolve_reads"] == 2
    assert list(entry)[-1] == "resolve_reads"
