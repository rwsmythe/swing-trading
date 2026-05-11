"""3e.8 Bundle 1 Task A.1 — briefing-side advisory composition helper.

Verifies the pure-logic helper that mirrors the dashboard's
``compute_all_suggestions(trade, AdvisoryContext(...))`` composition for the
briefing renderer's ``open_trade_advisories`` mapping.

Pipeline-side divergence from web side (locked design §0.3 #2):
  - No live PriceCache → ``current_price`` sourced from
    ``candidates_by_ticker[ticker].last_close`` (the open-position
    synthetic candidate row written by ``_step_evaluate``); falls back to
    OHLCV last-bar close when the candidate's close is missing.
  - SMA + previous_close from the same pipeline-loaded OHLCV path
    ``_step_charts`` already populated (``swing.data.ohlcv_archive``).
    NO new yfinance calls — only re-reads the per-ticker archive.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from swing.config import StopAdvisoryConfig
from swing.data.models import Candidate, Trade


def _trade(*, ticker: str = "ABCD", entry: float = 100.0,
           initial_stop: float = 95.0, current_stop: float | None = None,
           entry_date: str = "2026-04-01",
           trade_id: int = 7) -> Trade:
    return Trade(
        id=trade_id, ticker=ticker, entry_date=entry_date,
        entry_price=entry, initial_shares=10, initial_stop=initial_stop,
        current_stop=current_stop if current_stop is not None else initial_stop,
        state="managing",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )


def _candidate(*, ticker: str = "ABCD", close: float | None = None) -> Candidate:
    return Candidate(
        ticker=ticker, bucket="excluded", close=close,
        pivot=None, initial_stop=None, adr_pct=None,
        tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes="open position", criteria=(),
    )


def _stop_advisory_default() -> StopAdvisoryConfig:
    # Use the production default surface (single source of truth).
    return StopAdvisoryConfig()


def _bars_with_trail_setup() -> pd.DataFrame:
    """OHLCV bars where SMA-10 ≈ 99 + last_close above 10MA → trail_10ma fires."""
    # 30 bars rising from 80 to 100. SMA-10 over last 10 closes ~= 95.5.
    closes = [80.0 + (i * 0.7) for i in range(30)]
    dates = pd.date_range("2026-03-01", periods=30, freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=dates,
    )


def _bars_no_trigger() -> pd.DataFrame:
    """OHLCV bars chosen so NO advisory fires under the default config.

    All closes = 95.0. With trade.entry=100, trade.current_stop=96.0:
      * trail_10ma proposed stop = ceil(95.0 * (1 - 0.3/100) * 100)/100 = $94.72
        ≤ current_stop $96 → no trail_10ma.
      * trail_20ma + trail_50ma: same MA value, same predicate result.
      * exit_close_below_*: previous_close 95.0 >= 95.0 (== sma10) → no exit.
      * breakeven: price 95.0 < entry 100 → R = -1.0R < breakeven_r_trigger 1.0
        → no breakeven.
      * weather Bullish → no weather advisory.
      * time_stop: with entry_date < 10 days before as_of, no time_stop.
    """
    closes = [95.0] * 30
    dates = pd.date_range("2026-03-01", periods=30, freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": closes, "Low": closes, "Close": closes,
         "Volume": [1_000_000] * 30},
        index=dates,
    )


class _StubFetcher:
    """Fetcher protocol stub. Records calls; returns prepared DataFrames."""

    def __init__(self, per_ticker_bars: dict[str, pd.DataFrame] | None = None,
                 raise_for: set[str] | None = None):
        self._per_ticker_bars = per_ticker_bars or {}
        self._raise_for = raise_for or set()
        self.calls: list[tuple[str, int]] = []

    def get(self, ticker: str, lookback_days: int, *, as_of_date=None):
        self.calls.append((ticker, lookback_days))
        if ticker in self._raise_for:
            raise ValueError(f"No data for {ticker}")
        return self._per_ticker_bars[ticker]


def test_compose_open_trade_advisories_fires_trail_10ma_when_price_above_sma10():
    """Trade at entry $100, stop $95; price $100 above SMA-10 → trail_10ma advisory."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade()
    bars = _bars_with_trail_setup()
    # Sanity: last close should be a clean trail-setup price.
    last_close = float(bars["Close"].iloc[-1])
    assert last_close > 95.0, "fixture sanity"
    cfg_stop = _stop_advisory_default()
    candidates = {"ABCD": _candidate(close=last_close)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=cfg_stop,
        action_session_date="2026-04-15",
    )

    assert trade.id in result
    rules = {s.rule for s in result[trade.id]}
    assert "trail_10ma" in rules, (
        f"Expected trail_10ma to fire; got rules={rules!r}"
    )


def test_compose_open_trade_advisories_empty_list_when_no_triggers():
    """Trade with current_stop above trail-proposed, price below entry,
    bullish weather, recent entry → no advisories fire under default config."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    # entry_date 2026-04-14 → 1 day open at as_of=2026-04-15 (< 10 day default
    # → no time_stop). current_stop $96 already above trail-proposed $94.72.
    trade = _trade(current_stop=96.0, entry_date="2026-04-14")
    bars = _bars_no_trigger()
    candidates = {"ABCD": _candidate(close=95.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    assert trade.id in result, (
        "helper must return key for every open trade — even when list is empty "
        "(briefing renderer differentiates absent-vs-empty per §3.1 A.AC.6)"
    )
    assert result[trade.id] == [], (
        f"Expected empty list (no triggers); got {result[trade.id]!r}"
    )


def test_compose_open_trade_advisories_no_extra_fetcher_calls_per_trade():
    """One fetcher.get per open trade — proves no spurious refetching.

    Closes A.AC.5 / pre-empt-list "no extra yfinance calls": the helper must
    issue exactly one fetcher.get call per open trade (the chart-step's
    fetch is already in the archive; one read re-uses that archive entry).
    """
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trades = [
        _trade(ticker="AAAA", trade_id=1),
        _trade(ticker="BBBB", trade_id=2),
        _trade(ticker="CCCC", trade_id=3),
    ]
    bars = _bars_no_trigger()
    candidates = {t.ticker: _candidate(ticker=t.ticker, close=96.0) for t in trades}
    fetcher = _StubFetcher({t.ticker: bars for t in trades})

    compose_open_trade_advisories_for_briefing(
        trades=trades, fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    # Exactly one fetcher.get call per ticker.
    tickers_called = [t for t, _lookback in fetcher.calls]
    assert sorted(tickers_called) == sorted([t.ticker for t in trades]), (
        f"Expected one fetcher.get per trade ticker; got {fetcher.calls!r}"
    )


def test_compose_open_trade_advisories_graceful_on_fetcher_error():
    """If fetcher raises for a ticker, helper logs + emits empty list for that
    trade — does NOT propagate the exception (briefing must continue).
    """
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade_ok = _trade(ticker="OKEE", trade_id=11)
    trade_bad = _trade(ticker="FAIL", trade_id=22)
    bars = _bars_with_trail_setup()
    candidates = {
        "OKEE": _candidate(ticker="OKEE", close=float(bars["Close"].iloc[-1])),
        "FAIL": _candidate(ticker="FAIL", close=100.0),
    }
    fetcher = _StubFetcher({"OKEE": bars}, raise_for={"FAIL"})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade_ok, trade_bad], fetcher=fetcher,
        candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    assert trade_bad.id in result
    assert result[trade_bad.id] == []
    assert trade_ok.id in result


def test_compose_open_trade_advisories_returns_view_model_dataclasses():
    """Returned items must be ``AdvisorySuggestionVM`` (rendering layer type),
    not raw ``AdvisorySuggestion`` — matches the briefing-renderer template's
    ``s.rule`` + ``s.message`` consumption contract.
    """
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing
    from swing.rendering.view_models import AdvisorySuggestionVM

    trade = _trade()
    bars = _bars_with_trail_setup()
    candidates = {"ABCD": _candidate(close=float(bars["Close"].iloc[-1]))}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    suggestions = result[trade.id]
    assert suggestions, "fixture should produce at least one suggestion"
    for s in suggestions:
        assert isinstance(s, AdvisorySuggestionVM), (
            f"Expected AdvisorySuggestionVM; got {type(s).__name__}"
        )
