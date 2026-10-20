"""F12 (maintenance rider, CHARC-ruled 2026-10-20): ONE named window constant for
detect Pass-1, the exemplar fetch and observe's archive populate, plus the depth
relation (condition (ii)) against the LIVE tracked config.

The exemplar site is held by the closure grep (zero `window_days=400` under
`swing/`) plus the value pin below; a runtime pin there would need a seeded
exemplar corpus (plan AL-15).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

import swing.config
import swing.pipeline.runner as runner
from tests.pipeline.conftest_temporal import _cfg


def test_warm_depth_covers_observe_window_against_live_config() -> None:
    """The config counts TRADING rows (`ohlcv_archive.py:607` keeps the last N),
    the constant is CALENDAR days; N rows span at least N-1 calendar days, so
    N > C.

    The left side is read through `Config` from the tracked `swing.config.toml`
    (the CLI's loader), never a literal, so this pins the deployed value rather
    than today's default. Today: 1260 trading rows (~1,857 calendar days)
    against 400.
    """
    cfg = swing.config.load(
        Path(__file__).resolve().parents[2] / "swing.config.toml")
    assert cfg.archive.archive_history_days > runner.DETECT_OBSERVE_WINDOW_DAYS


def test_observe_populate_uses_the_window_constant(tmp_path, monkeypatch) -> None:
    """Observe's best-effort archive populate in `_bar_for_date` passes the
    constant, read at call time (a sentinel value proves the site uses it)."""
    cfg = _cfg(tmp_path, tmp_path / "swing.db")
    monkeypatch.setattr(runner, "DETECT_OBSERVE_WINDOW_DAYS", 401)
    monkeypatch.setattr(runner, "last_completed_session",
                        lambda *_a, **_k: date(2026, 6, 4))
    recorded: list[int] = []

    class _RecCache:
        def get_or_fetch(self, *, ticker, window_days):
            recorded.append(window_days)
            return pd.DataFrame()

    runner._bar_for_date(cfg, _RecCache(), "AAPL", "2026-06-04")
    assert recorded == [401]


def test_window_constant_value_is_400() -> None:
    """The behaviour-neutral guard: the named constant carries today's literal."""
    assert runner.DETECT_OBSERVE_WINDOW_DAYS == 400
