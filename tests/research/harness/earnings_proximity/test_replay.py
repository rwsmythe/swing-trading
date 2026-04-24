"""Replay driver tests.

The replay driver sits on top of `swing.evaluation.evaluator.evaluate_one`.
These tests pin wiring behavior (signal filtering, earnings-lookup, window
bounds, phase-isolation of imports) by monkeypatching `evaluate_one` in the
replay module. The full end-to-end path is exercised by the D7 smoke test.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from swing.data.models import Candidate
from swing.evaluation.context import MarketContext  # noqa: F401 — imported to verify reuse path

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _build_ohlcv(start: str, n_bars: int, base_close: float = 100.0) -> pd.DataFrame:
    """Build a synthetic OHLCV frame with n_bars trading-day-spaced rows."""
    idx = pd.date_range(start, periods=n_bars, freq="B")
    return pd.DataFrame(
        {
            "Open": [base_close + i * 0.1 for i in range(n_bars)],
            "High": [base_close + i * 0.1 + 0.5 for i in range(n_bars)],
            "Low": [base_close + i * 0.1 - 0.5 for i in range(n_bars)],
            "Close": [base_close + i * 0.1 for i in range(n_bars)],
            "Volume": [1_000_000 for _ in range(n_bars)],
        },
        index=idx,
    )


def _make_cfg():
    """Minimal harness Config for replay tests. Only fields read by
    evaluate_one / scoring matter; we stub the rest with safe defaults."""
    from research.harness.earnings_proximity.replay import build_harness_config

    return build_harness_config()


def _aplus_candidate(ticker: str, pivot: float = 110.0, stop: float = 100.0) -> Candidate:
    return Candidate(
        ticker=ticker,
        bucket="aplus",
        close=109.5,
        pivot=pivot,
        initial_stop=stop,
        adr_pct=4.5,
        tight_streak=3,
        pullback_pct=15.0,
        prior_trend_pct=30.0,
        rs_rank=80,
        rs_return_12w_vs_spy=0.15,
        rs_method="universe",
        pattern_tag=None,
        notes=None,
        criteria=(),
    )


def _watch_candidate(ticker: str) -> Candidate:
    return replace(_aplus_candidate(ticker), bucket="watch")


# ----------------------------------------------------------------------------
# Signal emission + filtering
# ----------------------------------------------------------------------------


def test_replay_yields_aplus_signals_per_trading_day(monkeypatch):
    """Two trading days, one ticker, both eval results A+ → two signals."""
    from research.harness.earnings_proximity import replay as mod

    calls: list[tuple[str, str]] = []

    def fake_evaluate_one(ctx):
        calls.append((ctx.ticker, ctx.ohlcv.index[-1].date().isoformat()))
        return _aplus_candidate(ctx.ticker)

    monkeypatch.setattr(mod, "evaluate_one", fake_evaluate_one)

    ohlcv = {"AAPL": _build_ohlcv("2024-01-02", 300)}
    trading_days = [date(2025, 2, 24), date(2025, 2, 25)]
    signals = list(
        mod.replay(
            universe_tickers=("AAPL",),
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings={"AAPL": [date(2025, 3, 15)]},
            cfg=_make_cfg(),
        )
    )

    assert len(signals) == 2
    assert {s.ticker for s in signals} == {"AAPL"}
    assert [s.date for s in signals] == trading_days
    # Pivot / stop plumbed through from Candidate.
    for s in signals:
        assert s.entry_target == pytest.approx(110.0)
        assert s.initial_stop == pytest.approx(100.0)
    assert len(calls) == 2


def test_replay_filters_non_aplus_buckets(monkeypatch):
    """'watch' bucket is skipped; only 'aplus' emits signals."""
    from research.harness.earnings_proximity import replay as mod

    def fake_evaluate_one(ctx):
        if ctx.ticker == "AAPL":
            return _aplus_candidate("AAPL")
        return _watch_candidate(ctx.ticker)

    monkeypatch.setattr(mod, "evaluate_one", fake_evaluate_one)

    ohlcv = {
        "AAPL": _build_ohlcv("2024-01-02", 300),
        "MSFT": _build_ohlcv("2024-01-02", 300),
    }
    signals = list(
        mod.replay(
            universe_tickers=("AAPL", "MSFT"),
            trading_days=[date(2025, 2, 24)],
            ohlcv=ohlcv,
            earnings={"AAPL": [], "MSFT": []},
            cfg=_make_cfg(),
        )
    )
    assert len(signals) == 1
    assert signals[0].ticker == "AAPL"


# ----------------------------------------------------------------------------
# Earnings lookup semantics
# ----------------------------------------------------------------------------


def test_replay_populates_next_earnings_date_strictly_after_signal(monkeypatch):
    """next_earnings_date is the first earnings date > signal.date
    (strictly later, not same-day)."""
    from research.harness.earnings_proximity import replay as mod

    monkeypatch.setattr(mod, "evaluate_one", lambda ctx: _aplus_candidate(ctx.ticker))

    earnings_dates = [
        date(2025, 1, 30),   # before signal
        date(2025, 2, 24),   # SAME as signal — excluded (strictly after rule)
        date(2025, 2, 25),   # first strictly-after
        date(2025, 5, 30),
    ]
    signals = list(
        mod.replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": earnings_dates},
            cfg=_make_cfg(),
        )
    )
    assert len(signals) == 1
    assert signals[0].next_earnings_date == date(2025, 2, 25)
    assert signals[0].absent_earnings_data is False


def test_replay_flags_absent_earnings_data(monkeypatch):
    """Empty earnings list → next_earnings_date=None AND absent_earnings_data=True.
    Per method record: absent data → do NOT exclude downstream, flag for review."""
    from research.harness.earnings_proximity import replay as mod

    monkeypatch.setattr(mod, "evaluate_one", lambda ctx: _aplus_candidate(ctx.ticker))

    signals = list(
        mod.replay(
            universe_tickers=("UNKNOWN",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"UNKNOWN": _build_ohlcv("2024-01-02", 300)},
            earnings={"UNKNOWN": []},
            cfg=_make_cfg(),
        )
    )
    assert len(signals) == 1
    assert signals[0].next_earnings_date is None
    assert signals[0].absent_earnings_data is True


def test_replay_handles_all_earnings_in_past(monkeypatch):
    """Earnings list has entries but none strictly after signal → next=None,
    absent=False (data is present, just no future date)."""
    from research.harness.earnings_proximity import replay as mod

    monkeypatch.setattr(mod, "evaluate_one", lambda ctx: _aplus_candidate(ctx.ticker))

    signals = list(
        mod.replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv={"AAPL": _build_ohlcv("2024-01-02", 300)},
            earnings={"AAPL": [date(2024, 1, 1), date(2024, 5, 1)]},
            cfg=_make_cfg(),
        )
    )
    assert signals[0].next_earnings_date is None
    assert signals[0].absent_earnings_data is False


# ----------------------------------------------------------------------------
# OHLCV slicing + insufficient-history handling
# ----------------------------------------------------------------------------


def test_replay_skips_days_with_insufficient_history(monkeypatch):
    """Trading day with fewer than 200 bars of prior history → skip ticker
    (evaluate_one would return trend-template NA otherwise; we don't call it)."""
    from research.harness.earnings_proximity import replay as mod

    call_log: list[str] = []

    def fake_evaluate_one(ctx):
        call_log.append(ctx.ticker)
        return _aplus_candidate(ctx.ticker)

    monkeypatch.setattr(mod, "evaluate_one", fake_evaluate_one)

    # OHLCV starts 2025-02-03; day 2025-02-24 has only ~15 bars — skip.
    ohlcv = {"AAPL": _build_ohlcv("2025-02-03", 20)}
    signals = list(
        mod.replay(
            universe_tickers=("AAPL",),
            trading_days=[date(2025, 2, 24)],
            ohlcv=ohlcv,
            earnings={"AAPL": []},
            cfg=_make_cfg(),
        )
    )
    assert signals == []
    assert call_log == []  # evaluate_one not called when history < min_bars


def test_replay_slices_ohlcv_up_to_trading_day_inclusive(monkeypatch):
    """CandidateContext.ohlcv must be truncated at the trading day — no
    look-ahead bias from later bars.

    This is the subtle bug the replay MUST avoid: if we pass the whole
    OHLCV frame regardless of trading_day, the simulator/evaluator sees
    the future.
    """
    from research.harness.earnings_proximity import replay as mod

    observed_last_bars: list[date] = []

    def fake_evaluate_one(ctx):
        observed_last_bars.append(ctx.ohlcv.index[-1].date())
        return _aplus_candidate(ctx.ticker)

    monkeypatch.setattr(mod, "evaluate_one", fake_evaluate_one)

    ohlcv = {"AAPL": _build_ohlcv("2024-01-02", 300)}
    trading_days = [date(2025, 2, 24), date(2025, 2, 25), date(2025, 2, 26)]
    list(
        mod.replay(
            universe_tickers=("AAPL",),
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings={"AAPL": []},
            cfg=_make_cfg(),
        )
    )
    # Each call sees an OHLCV whose last bar is at or before that day.
    assert len(observed_last_bars) == 3
    for expected_day, actual_last in zip(trading_days, observed_last_bars, strict=True):
        assert actual_last <= expected_day


# ----------------------------------------------------------------------------
# Phase isolation — no DB-writing imports
# ----------------------------------------------------------------------------


def test_replay_module_imports_no_db_writing_services():
    """Brief §D3 acceptance: replay must not import swing.trades.entry /
    .exit / .stop_adjust (DB-writing services) or swing.data.repos
    (repository layer). AST-level check keeps the invariant from regressing
    without false positives from comments/docstrings."""
    import ast
    from pathlib import Path

    replay_src = (
        Path(__file__).parents[4]
        / "research"
        / "harness"
        / "earnings_proximity"
        / "replay.py"
    )
    tree = ast.parse(replay_src.read_text(encoding="utf-8"))

    forbidden_prefixes = (
        "swing.trades.entry",
        "swing.trades.exit",
        "swing.trades.stop_adjust",
        "swing.data.repos",
    )
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported_names.append(module)

    for name in imported_names:
        for bad in forbidden_prefixes:
            assert not (name == bad or name.startswith(bad + ".")), (
                f"replay.py imports forbidden module {name!r}"
            )
