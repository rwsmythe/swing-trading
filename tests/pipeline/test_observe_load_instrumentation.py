from __future__ import annotations
import pytest
from unittest.mock import patch

from tests.pipeline.conftest_temporal import (  # noqa: F401
    tmp_db_v22, _build_bars, _cfg, _FakeLease, _plant_detection, _stub_window)
from swing.data.repos.pattern_forward_observations import (
    get_observations_for_detection)

_OBS = "2026-05-29"


class _TeleStub:
    """A telemetry-bearing observe cache stub: each get_or_fetch is a
    fetch_window (the observe step's fresh-process cold-cache model)."""
    def __init__(self, bars):
        self._b = bars
        self._fw = 0

    def get_or_fetch(self, *, ticker, window_days=180):
        self._fw += 1
        return self._b.get(ticker)

    def drain_telemetry(self):
        fw, self._fw = self._fw, 0
        return {"fetch_window": fw, "in_memory_hit": 0}


def _drive_observe(cfg, lease, cache, warnings):
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_=_OBS)):
        with patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS):
            from swing.pipeline.runner import _step_pattern_observe
            _step_pattern_observe(cfg=cfg, lease=lease, ohlcv_cache=cache,
                                  run_warnings=warnings)


def test_ohlcv_cache_telemetry_counts_hit_vs_fetch(tmp_path, monkeypatch):
    # Unit-test the truthful counter at its source. First get_or_fetch for a
    # ticker is a fetch_window; an immediate second call (within TTL) is an
    # in_memory_hit. Stub _fetch_bars_window so no real network/slice is hit.
    import pandas as pd
    from tests.pipeline.test_ohlcv_cache_shape_parity import _make_cfg
    from swing.web.ohlcv_cache import OhlcvCache
    cfg = _make_cfg(tmp_path)
    cache = OhlcvCache(cfg=cfg)
    frame = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0],
         "Volume": [1]}, index=pd.to_datetime(["2026-05-28"]))
    monkeypatch.setattr(cache, "_fetch_bars_window",
                        lambda *, ticker, window_days: frame)
    cache.get_or_fetch(ticker="AAA", window_days=180)   # fetch_window
    cache.get_or_fetch(ticker="AAA", window_days=180)   # in_memory_hit (TTL)
    t = cache.drain_telemetry()
    assert t["fetch_window"] == 1 and t["in_memory_hit"] == 1
    # Drain zeroes the counters.
    assert cache.drain_telemetry() == {"in_memory_hit": 0, "fetch_window": 0}


def test_observe_emits_fetch_telemetry_metrics_entry(tmp_db_v22, tmp_path):
    # Plant 2 open detections; drive observe with a telemetry-bearing stub;
    # assert one observe_load metrics entry where observed == fetch_window == 2.
    conn, db_path = tmp_db_v22
    _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    _plant_detection(conn, ticker="BBB", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    cache = _TeleStub({"AAA": _build_bars(), "BBB": _build_bars()})
    warnings: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), cache, warnings)
    entry = next(w for w in warnings
                 if w.get("metric") == "observe_load")
    assert entry["step"] == "pattern_observe"
    assert entry["observed"] == 2
    assert entry["fetch_window"] == 2          # one populate per open detection
    assert entry["in_memory_hit"] == 0
    assert entry["fetch_window"] + entry["in_memory_hit"] == 2  # == get_or_fetch


def test_observe_load_excludes_prior_step_fetches(tmp_db_v22, tmp_path):
    # Codex R1 MAJOR: the runner shares one OhlcvCache across detect/charts/
    # observe. Simulate prior-step fetches on the SAME cache before observe;
    # the observe_load audit must reflect observe-ONLY fetches (entry reset).
    conn, db_path = tmp_db_v22
    _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    cache = _TeleStub({"AAA": _build_bars()})
    # Prior steps already fetched 5 windows on this cache instance.
    for _ in range(5):
        cache.get_or_fetch(ticker="AAA")
    warnings: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), cache, warnings)
    entry = next(w for w in warnings if w.get("metric") == "observe_load")
    # Observe touched 1 open detection -> fetch_window == 1, NOT 6.
    assert entry["fetch_window"] == 1
    assert entry["observed"] == 1


def test_observe_scaling_one_obs_per_open_detection(tmp_db_v22, tmp_path):
    # Plant 5 open detections; drive observe; assert 5 observation rows (one per
    # open detection) and the idempotent already-observed-today guard holds on a
    # second drive (still 5).
    conn, db_path = tmp_db_v22
    det_ids = [
        _plant_detection(conn, ticker=t, data_asof_date="2026-05-28")
        for t in ("AAA", "BBB", "CCC", "DDD", "EEE")]
    cfg = _cfg(tmp_path, db_path)
    bars = {t: _build_bars() for t in ("AAA", "BBB", "CCC", "DDD", "EEE")}

    class _Stub:
        def get_or_fetch(self, *, ticker, window_days=180):
            return bars[ticker]
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), _Stub(), [])
    assert sum(len(get_observations_for_detection(conn, d)) for d in det_ids) == 5
    # Idempotent re-drive: still 5 (no duplicate rows).
    _drive_observe(cfg, _FakeLease(db_path, 2, _OBS), _Stub(), [])
    assert sum(len(get_observations_for_detection(conn, d)) for d in det_ids) == 5
