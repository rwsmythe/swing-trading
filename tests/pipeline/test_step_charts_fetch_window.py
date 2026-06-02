"""Phase 14 close-out (A-1) — the chart/market-weather OHLCV fetch window is
widened to >=200 trading bars (~300 calendar days) so the 200-MA on any
MA200-bearing surface has enough bars. Binding assertion (Codex M#5): >=200
bars actually REACH render_market_weather_svg, not just the window_days value.
"""
from __future__ import annotations

from dataclasses import replace

import swing.pipeline.runner as runner_mod
from swing.pipeline.lease import acquire_lease
from swing.pipeline.runner import _step_charts
from swing.web.ohlcv_cache import (
    MIN_CALENDAR_DAYS_FOR_MA200,
    MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
)
from tests.pipeline.test_step_charts_ohlcv_cache_wiring import (
    _make_cfg,
    _ohlcv,
    _seed_eval_with_aplus_candidates,
    _stub_render,
)


def test_min_calendar_days_constant_is_at_least_290():
    # 200 trading bars * 365/252 ~= 290 calendar days; the constant must clear it.
    assert MIN_CALENDAR_DAYS_FOR_MA200 >= 290


def test_step_charts_market_weather_window_and_bars(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    cfg = replace(cfg, pipeline=replace(cfg.pipeline, chart_top_n_watch=5))
    lease = acquire_lease(
        db_path=cfg.paths.db_path, trigger="manual",
        data_asof_date="2026-04-15", action_session_date="2026-04-16",
    )
    eval_run_id, data_asof = _seed_eval_with_aplus_candidates(
        cfg, lease, [("APLA", 110.0)],
    )

    captured_windows: list[int] = []

    class _FakeCache:
        def get_or_fetch(self, *, ticker, window_days):
            captured_windows.append(window_days)
            return _ohlcv(260)  # >=200 rows so the SMA200 has enough bars

    seen: dict[str, int] = {}
    real = runner_mod.render_market_weather_svg

    def spy(*, bars, **kw):
        seen["bars_len"] = len(bars)
        return real(bars=bars, **kw)

    monkeypatch.setattr(runner_mod, "render_market_weather_svg", spy)
    _stub_render(monkeypatch)

    _step_charts(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id, data_asof=data_asof,
        ohlcv_cache=_FakeCache(),
    )

    # F-2: the market_weather fetch uses the WIDE compute window (structural_stage
    # needs TT3's 200MA-rising history); the chart-target fetches still use MA200.
    assert MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE in captured_windows
    assert MIN_CALENDAR_DAYS_FOR_MA200 in captured_windows
    # Binding (Codex M#5): >=200 bars REACH the renderer (the sliced display
    # window still carries a full 200-MA line).
    assert seen["bars_len"] >= 200
