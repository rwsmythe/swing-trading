"""D90: the cache surface of `OhlcvCache.get_or_fetch(..., use_ladder=...)`.

`use_ladder` is keyword-only with default True (CHARC FORM, plan AL-1). True
(the default) reaches an installed ladder bars hook on a store miss; False takes
the `read_or_fetch_archive` branch even when a hook is installed (AL-2). The
`_bars_store` key does not include the flag, so a TTL hit serves either setting
(AL-3). The bundle worker reads the hook directly and is untouched (AL-6).

Two distinguishable sources: the hook returns `frame_l`, the patched
`read_or_fetch_archive` returns `frame_a = frame_l + 1.0`.
"""
from __future__ import annotations

import inspect
from datetime import date

import pandas as pd
import pytest

from swing.web.ohlcv_cache import OhlcvCache
from tests.pipeline.test_ohlcv_cache_shape_parity import (
    _fixture_daily_bars,
    _make_cfg,
)

_SESSION = date(2026, 6, 10)


@pytest.fixture
def world(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr("swing.web.ohlcv_cache.last_completed_session",
                        lambda *_a, **_k: _SESSION)
    # 240 business days span fewer than 400 calendar days: a 400-day slice
    # keeps every row.
    frame_l = _fixture_daily_bars(end=pd.Timestamp("2026-06-10"), n_rows=240)
    frame_a = frame_l + 1.0
    hook_calls: list[str] = []
    archive_calls: list[tuple] = []

    def hook(t):
        hook_calls.append(t)
        return (frame_l, "yfinance")

    def _archive(ticker, *, end_date, cache_dir, archive_history_days):
        archive_calls.append((ticker, end_date, cache_dir, archive_history_days))
        return frame_a

    monkeypatch.setattr("swing.web.ohlcv_cache.read_or_fetch_archive", _archive)

    def fresh():
        cache = OhlcvCache(cfg)
        cache.set_ladder_bars_fetcher(hook)
        return cache

    return {"cfg": cfg, "frame_l": frame_l, "frame_a": frame_a,
            "hook_calls": hook_calls, "archive_calls": archive_calls,
            "fresh": fresh}


def _eq(a, b):
    # A boolean-mask slice drops the `B` freq.
    pd.testing.assert_frame_equal(a, b, check_freq=False)


def test_default_and_true_reach_the_ladder_hook(world):
    cache1 = world["fresh"]()
    out1 = cache1.get_or_fetch(ticker="aaa", window_days=400)
    assert world["hook_calls"] == ["AAA"]
    assert world["archive_calls"] == []
    _eq(out1, world["frame_l"])

    world["hook_calls"].clear()
    cache2 = world["fresh"]()
    out2 = cache2.get_or_fetch(ticker="aaa", window_days=400, use_ladder=True)
    assert world["hook_calls"] == ["AAA"]
    assert world["archive_calls"] == []
    _eq(out2, world["frame_l"])

    param = inspect.signature(OhlcvCache.get_or_fetch).parameters["use_ladder"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is True


def test_false_skips_the_hook_and_shares_the_store(world):
    cfg = world["cfg"]
    cache = world["fresh"]()
    out = cache.get_or_fetch(ticker="AAA", window_days=400, use_ladder=False)
    assert world["hook_calls"] == []
    assert world["archive_calls"] == [
        ("AAA", _SESSION, cfg.paths.prices_cache_dir,
         cfg.archive.archive_history_days)]
    _eq(out, world["frame_a"])
    # A default call on the same cache is a TTL hit (the key omits the flag).
    hit = cache.get_or_fetch(ticker="AAA", window_days=400)
    assert world["hook_calls"] == []
    _eq(hit, world["frame_a"])
    assert cache.drain_telemetry() == {"in_memory_hit": 1, "fetch_window": 1}

    # Reverse order on a fresh cache: default first (hook once), then
    # use_ladder=False is a hit and never reaches the archive.
    world["archive_calls"].clear()
    cache2 = world["fresh"]()
    first = cache2.get_or_fetch(ticker="AAA", window_days=400)
    assert world["hook_calls"] == ["AAA"]
    _eq(first, world["frame_l"])
    second = cache2.get_or_fetch(ticker="AAA", window_days=400, use_ladder=False)
    assert world["hook_calls"] == ["AAA"]
    assert world["archive_calls"] == []
    _eq(second, world["frame_l"])
    assert cache2.drain_telemetry() == {"in_memory_hit": 1, "fetch_window": 1}


def test_bundle_worker_still_calls_the_hook(world):
    # An invariant pin (AL-6): GREEN before and after D90.
    cache = world["fresh"]()
    bundle, healthy = cache._fetch_bundle_worker("AAA")
    assert world["hook_calls"] == ["AAA"]
    assert bundle.provider == "yfinance"
    assert healthy is True
