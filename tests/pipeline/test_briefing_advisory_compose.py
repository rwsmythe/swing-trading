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


def test_compose_open_trade_last_prices_uses_candidate_close_when_present():
    """Codex R2 Major #2 closure — companion helper resolves per-ticker
    prices using candidate.close first, mirroring the advisory helper's
    primary path."""
    from swing.pipeline.runner import compose_open_trade_last_prices_for_briefing

    trade = _trade()
    bars = _bars_with_trail_setup()
    candidates = {"ABCD": _candidate(close=108.42)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_last_prices_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        data_asof_date="2026-04-14",
    )

    assert result == {"ABCD": 108.42}, (
        f"candidate.close path must yield exact value; got {result!r}"
    )
    # Fetcher MUST NOT be called when candidate.close path resolves.
    assert fetcher.calls == [], (
        f"fetcher should not be consulted when candidate.close is present; "
        f"got {fetcher.calls!r}"
    )


def test_compose_open_trade_last_prices_falls_back_to_prev_close():
    """Codex R2 Major #2 closure — when candidate.close is None (or
    candidate row absent), the helper falls back to OHLCV previous_close.
    Discriminating: candidate exists but close=None → helper consults
    fetcher and returns prev_close.
    """
    from swing.pipeline.runner import compose_open_trade_last_prices_for_briefing

    trade = _trade()
    bars = _bars_with_trail_setup()
    expected_prev_close = float(bars["Close"].iloc[-1])
    candidates = {"ABCD": _candidate(close=None)}  # candidate.close missing
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_last_prices_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        data_asof_date="2026-04-14",
    )

    assert result == {"ABCD": expected_prev_close}, (
        f"prev_close fallback must yield bars[Close].iloc[-1]; got {result!r}"
    )


def test_compose_open_trade_last_prices_omits_when_no_data():
    """Codex R2 Major #2 closure — when candidate.close is None AND fetcher
    raises, the ticker is OMITTED from the result. Briefing renderer's
    .get(ticker, t.entry_price) fallback handles this degenerate path.
    """
    from swing.pipeline.runner import compose_open_trade_last_prices_for_briefing

    trade = _trade()
    candidates = {"ABCD": _candidate(close=None)}
    fetcher = _StubFetcher({}, raise_for={"ABCD"})

    result = compose_open_trade_last_prices_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        data_asof_date="2026-04-14",
    )

    assert "ABCD" not in result, (
        f"Ticker with no resolvable price MUST be omitted (briefing renderer "
        f"falls back to t.entry_price); got {result!r}"
    )


def test_compose_open_trade_advisories_pins_as_of_date_when_supplied():
    """Codex R1 Major 3 fix — helper passes ``data_asof_date`` through as
    ``as_of_date=date.fromisoformat(...)`` to the fetcher so cross-session
    or retry runs don't silently fall back to wall-clock
    ``last_completed_session(datetime.now())``.

    Discriminating: stub fetcher records the as_of_date received; assert
    it equals the parsed-from-ISO date object.
    """
    from datetime import date

    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade()
    bars = _bars_with_trail_setup()
    candidates = {"ABCD": _candidate(close=float(bars["Close"].iloc[-1]))}

    class _Recording:
        def __init__(self):
            self.last_as_of_date = "<unset>"
        def get(self, ticker, lookback_days, *, as_of_date=None):
            self.last_as_of_date = as_of_date
            return bars

    fetcher = _Recording()
    compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher,
        candidates_by_ticker=candidates, weather_status="Bullish",
        stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
        data_asof_date="2026-04-14",
    )

    assert fetcher.last_as_of_date == date(2026, 4, 14), (
        f"Expected fetcher to receive as_of_date=date(2026, 4, 14); got "
        f"{fetcher.last_as_of_date!r}"
    )


# ----------------------------------------------------------------------
# 3e.8 Bundle 2 — new advisory rules wired into briefing composer.
# ----------------------------------------------------------------------


def _bars_for_parabolic() -> pd.DataFrame:
    """Bars rigged for §4.D parabolic-trim verification.

    All 50 bars: Close=100, High=102.5, Low=97.5
      → SMA-50 = 100.0
      → ADR% over trailing 20 = (102.5 - 97.5) / 100 * 100 = 5.0
      → §4.D threshold extension = 7.0 × 5.0 = 35%
      → fire iff current_price >= 100 * 1.35 = 135.

    Note: in the briefing composer ``current_price`` is sourced from
    ``candidate.close`` (open-position synthetic candidate row), so the
    test's threshold check is exercised by varying candidate.close, NOT
    the last bar's close.
    """
    closes = [100.0] * 50
    highs = [102.5] * 50
    lows = [97.5] * 50
    dates = pd.date_range("2026-01-01", periods=50, freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes,
         "Volume": [1_000_000] * 50},
        index=dates,
    )


def test_briefing_composer_fires_trim_into_strength_at_plus_1r_no_prior_trim():
    """§4.B — trade at +1R with no fills (has_been_trimmed=False / default)
    fires trim_into_strength via the briefing composer."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    # entry=100, stop=95 → 1R = $5. close=105 → +1R exactly.
    trade = _trade(entry=100.0, initial_stop=95.0)
    bars = _bars_no_trigger()  # SMA neutral; we only test the +1R rule here.
    candidates = {"ABCD": _candidate(close=105.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
        # trimmed_trade_ids omitted → all trades treated as no-prior-trim.
    )

    rules = {s.rule for s in result[trade.id]}
    assert "trim_into_strength" in rules


def test_briefing_composer_suppresses_trim_into_strength_when_trimmed():
    """§4.B — trade at +1R but flagged in trimmed_trade_ids → no advisory.

    Discriminating: same exact bars/candidate/trade as the fire-test;
    only difference is trimmed_trade_ids membership.
    """
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade(entry=100.0, initial_stop=95.0)
    bars = _bars_no_trigger()
    candidates = {"ABCD": _candidate(close=105.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
        trimmed_trade_ids={trade.id},
    )

    rules = {s.rule for s in result[trade.id]}
    assert "trim_into_strength" not in rules


def test_briefing_composer_fires_planned_target_r_hit():
    """§4.K — trade has planned_target_R=2.0 and is at +2R → fires."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = Trade(
        id=42, ticker="ABCD", entry_date="2026-04-01",
        entry_price=100.0, initial_shares=10, initial_stop=95.0,
        current_stop=95.0, state="managing",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None, planned_target_R=2.0,
    )
    bars = _bars_no_trigger()
    # close=110 → +2R exactly.
    candidates = {"ABCD": _candidate(close=110.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    rules = {s.rule for s in result[trade.id]}
    assert "planned_target_r_hit" in rules


def test_briefing_composer_omits_planned_target_r_hit_when_target_null():
    """§4.K — trade without planned_target_R never fires (NULL guard).
    Discriminating: at +5R (clearly past any plausible target), NULL
    must still suppress.
    """
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade(entry=100.0, initial_stop=95.0)  # planned_target_R defaults None
    bars = _bars_no_trigger()
    candidates = {"ABCD": _candidate(close=125.0)}  # +5R
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    rules = {s.rule for s in result[trade.id]}
    assert "planned_target_r_hit" not in rules


def test_briefing_composer_fires_parabolic_trim_at_7x_adr_above_50sma():
    """§4.D — fixture rigged: SMA-50 = 100, ADR% = 5, current_price = 135
    → extension is 35% = 7.0 × 5.0 → fires (>= comparison)."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade(entry=100.0, initial_stop=95.0, current_stop=130.0)
    # current_stop=130 above trail-MA proposed so neighboring trail rules quiet down.
    bars = _bars_for_parabolic()
    candidates = {"ABCD": _candidate(close=135.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    rules = {s.rule for s in result[trade.id]}
    assert "parabolic_trim" in rules, (
        f"Expected parabolic_trim to fire at 7× ADR; got rules={rules!r}"
    )


def test_briefing_composer_omits_parabolic_trim_below_threshold():
    """§4.D — fixture below threshold (price = 134, 34% extension, 6.8× ADR)
    must NOT fire. Discriminating pair with the fire-test above."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trade = _trade(entry=100.0, initial_stop=95.0, current_stop=130.0)
    bars = _bars_for_parabolic()
    # 6.8× ADR → extension 34% → below 7× threshold of 35%.
    candidates = {"ABCD": _candidate(close=134.0)}
    fetcher = _StubFetcher({"ABCD": bars})

    result = compose_open_trade_advisories_for_briefing(
        trades=[trade], fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
    )

    rules = {s.rule for s in result[trade.id]}
    assert "parabolic_trim" not in rules


def test_briefing_composer_no_extra_fetcher_calls_when_bundle2_rules_added():
    """C.AC.8 — ADR reuses existing bars; one fetcher.get per trade total
    even with Bundle 2 rules wired in."""
    from swing.pipeline.runner import compose_open_trade_advisories_for_briefing

    trades = [
        _trade(ticker="AAAA", trade_id=1),
        _trade(ticker="BBBB", trade_id=2),
    ]
    bars = _bars_for_parabolic()
    candidates = {t.ticker: _candidate(ticker=t.ticker, close=135.0) for t in trades}
    fetcher = _StubFetcher({t.ticker: bars for t in trades})

    compose_open_trade_advisories_for_briefing(
        trades=trades, fetcher=fetcher, candidates_by_ticker=candidates,
        weather_status="Bullish", stop_advisory_config=_stop_advisory_default(),
        action_session_date="2026-04-15",
        trimmed_trade_ids=set(),
    )

    # Each ticker fetched once (lookback_days=200 path); no second call
    # for ADR computation.
    call_counts: dict[str, int] = {}
    for ticker, _lb in fetcher.calls:
        call_counts[ticker] = call_counts.get(ticker, 0) + 1
    assert all(c == 1 for c in call_counts.values()), (
        f"Expected exactly one fetcher.get per ticker; got {fetcher.calls!r}"
    )


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
