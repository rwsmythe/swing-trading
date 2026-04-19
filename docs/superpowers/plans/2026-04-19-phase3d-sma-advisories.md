# Phase 3d SMA-Aware Advisories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute daily SMA10 / SMA20 / SMA50 + previous-daily-close on demand per open-trade ticker, plumb them into the existing `AdvisoryContext`, add the Minervini 50-SMA exit rule, and surface a degraded-OHLCV banner when the new cache is tripped — without blocking page load on slow / failed fetches.

**Architecture:** A new pure `swing/pipeline/ohlcv.py` (fetch + SMA math) is wrapped by a new `swing/web/ohlcv_cache.py` (TTL-cached bundles + sliding-window breaker) attached to `app.state`. Dashboard and the single-row wrapper receive the cache, call it sequentially after the live-price cache, and plumb per-ticker bundles into `AdvisoryContext`. One scoped Phase 2 change in `swing/trades/advisory.py` adds `sma50` + `previous_close` fields and swaps the exit-rule input. A new `ohlcv_source_degraded: bool = False` field lands on every base-layout VM so the shared `base.html.j2` banner renders without breaking unrelated routes.

**Tech Stack:** FastAPI + HTMX 2.x (existing), Jinja2 (autoescape via `_build_templates` Phase 3c helper), yfinance for OHLCV, pandas for SMA math (already in dependency tree via weather classifier). Python 3.14, Windows 11, gitbash. All commits go to `main`. Conventional commits (`feat(web):`, `fix(data):`, `refactor(...)`, etc.), NO Claude co-author footer, NO `--no-verify`.

**Baseline:** Phase 3c shipped at commit `3e934ef`. Spec committed + Codex-approved at `c3d65df` (5 rounds, NO_NEW_CRITICAL_MAJOR). 444 fast tests green. Target: **~484** fast tests after Phase 3d (spec §10 projected ~465; this plan lands ~20 above because breaker coverage, in-progress-bar strip, and pipeline pass-through got more granular).

---

## File Structure

### Production code

```
swing/
├── pipeline/
│   └── ohlcv.py                      # NEW: fetch_daily_bars, compute_smas, previous_close.
│                                     #   IO isolated to fetch_daily_bars; rest is pure.
├── trades/
│   └── advisory.py                   # MODIFIED (Phase 2 carve-out): +sma50 + previous_close
│                                     #   fields on AdvisoryContext; swap exit-rule input;
│                                     #   add 50MA exit call in compute_all_suggestions.
├── web/
│   ├── app.py                        # MODIFIED: app.state.ohlcv_cache = OhlcvCache(cfg).
│   ├── ohlcv_cache.py                # NEW: OhlcvBundle + OhlcvCache class.
│   ├── routes/
│   │   ├── dashboard.py              # MODIFIED: thread ohlcv_cache into build_dashboard.
│   │   ├── pipeline.py               # MODIFIED: compute ohlcv_degraded; pass to build_pipeline.
│   │   └── trades.py                 # MODIFIED: 4 call sites of build_open_positions_row.
│   ├── view_models/
│   │   ├── dashboard.py              # MODIFIED: fetch bundle; plumb into AdvisoryContext;
│   │   │                             #   populate DashboardVM.ohlcv_source_degraded.
│   │   ├── open_positions_row.py     # MODIFIED: accepts ohlcv_cache kwarg; single-ticker plumb.
│   │   ├── pipeline.py               # MODIFIED: PipelineVM.ohlcv_source_degraded field + kwarg.
│   │   ├── journal.py                # MODIFIED: JournalVM.ohlcv_source_degraded=False default.
│   │   ├── watchlist.py              # MODIFIED: WatchlistVM.ohlcv_source_degraded=False default.
│   │   └── error.py                  # MODIFIED: PageErrorVM.ohlcv_source_degraded=False default.
│   └── templates/
│       ├── base.html.j2              # MODIFIED: conditional include of the banner partial.
│       └── partials/
│           └── ohlcv_degraded_banner.html.j2  # NEW.
├── cli.py                            # MODIFIED: `swing trade advisory` gains --sma50 and
│                                     #   --previous-close flags; AdvisoryContext construction
│                                     #   updated.
└── config.py                         # MODIFIED: Web.ohlcv_cache_ttl_seconds = 3600 default;
                                      #   Web.max_concurrent_ohlcv_fetches = 8 default.
```

### Test files

```
tests/
├── pipeline/
│   └── test_ohlcv.py                 # NEW: ~8 tests — compute_smas, previous_close,
│                                     #   fetch_daily_bars in-progress-bar strip, truncation.
├── trades/
│   └── test_advisory.py              # MODIFIED: +4 new tests (SMA50 exit rule + previous_close
│                                     #   semantic); existing tests updated to pass sma50= /
│                                     #   previous_close= in the _ctx() factory.
├── cli/
│   └── test_cli_advisory.py          # MODIFIED (or NEW test per file shape): +1 smoke test
│                                     #   exercising --sma50 and --previous-close flags.
├── web/
│   ├── test_app_smoke.py             # MODIFIED: +1 test — app.state.ohlcv_cache is OhlcvCache.
│   ├── test_ohlcv_cache.py           # NEW: ~7 tests — cache hit/miss/TTL/deadline/breaker.
│   ├── test_base_layout_compat.py    # NEW: ~4 tests — /journal, /watchlist, page-error, and
│   │                                 #   /pipeline with is_degraded() True + False.
│   ├── test_dashboard_integration.py # MODIFIED: +3 tests — SMA advisories render for full
│   │                                 #   bundle; absent for all-None bundle; partial bundle.
│   └── test_view_models/
│       └── test_*.py (various)       # MODIFIED: existing fixtures updated to pass a test
│                                     #   double for ohlcv_cache.
```

**Target test count:** 444 (end of 3c) + ~40 = **~484 fast tests** (spec §10 projected ~465; per-task math cascades to 484 — see §Task 18 summary).

---

## Task Ordering Rationale

1. **Pure helpers (T1-T2):** `swing/pipeline/ohlcv.py` has no dependencies on the rest of the codebase. Land first; downstream tasks import from it.
2. **Phase 2 carve-out (T3):** `swing/trades/advisory.py` gains `sma50` + `previous_close`. All existing `AdvisoryContext(...)` callers in tests must be updated to pass the new kwargs (Python frozen dataclass — order of kwargs matters only for positional calls; existing call sites use kwargs, so adding fields is compatible for callers that default-fill them, but `_ctx()` fixture and the two `build_*` call sites need updating). Land this EARLY so downstream wiring in T12-T13 can construct the new shape.
3. **CLI parity (T4):** orthogonal; lands alongside T3 so the CLI and the service share the new context shape.
4. **Config (T5):** two new `Web` fields. Smallest possible commit.
5. **`OhlcvCache` class (T6):** depends on T1 (pure helpers) and T5 (config fields).
6. **App wiring (T7):** adds `app.state.ohlcv_cache`. Depends on T6.
7. **Base-layout VM compat (T8):** add `ohlcv_source_degraded: bool = False` to the 5 VMs. MUST land before T9 (template banner) or unrelated routes 500 on `UndefinedError`.
8. **Template banner (T9):** add the conditional to `base.html.j2` + new partial.
9. **Pipeline route flag pass-through (T10-T11):** `build_pipeline` kwarg + route computes and passes.
10. **Dashboard wiring (T12-T15):** `build_dashboard` + `build_open_positions_row` receive the cache; dashboard + trades routes pass it.
11. **Regression + integration tests (T16-T17):** base-layout compat suite + dashboard integration tests.
12. **Full-suite acceptance sweep (T18).**

Each task ends with a clean commit. No task leaves the codebase in a broken state.

---

## Task 1: Pure SMA helpers (`compute_smas` + `previous_close`)

**Files:**
- Create: `swing/pipeline/ohlcv.py`
- Test: `tests/pipeline/test_ohlcv.py`

Spec §3.1 first half: the two PURE functions. Fetching comes in T2. These functions must be testable with canned DataFrames — no yfinance round-trip.

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/test_ohlcv.py`:

```python
"""Pure SMA helpers — canned DataFrame tests. No yfinance round-trip."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _bars(closes: list[float]) -> pd.DataFrame:
    """Build a synthetic DataFrame matching yfinance's shape (Close column)."""
    idx = pd.date_range("2026-01-02", periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_compute_smas_returns_float_when_enough_bars():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([100.0] * 50)
    out = compute_smas(bars, [10, 20, 50])
    assert out[10] == pytest.approx(100.0)
    assert out[20] == pytest.approx(100.0)
    assert out[50] == pytest.approx(100.0)


def test_compute_smas_returns_none_for_period_exceeding_bars():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([100.0] * 10)
    out = compute_smas(bars, [10, 20, 50])
    assert out[10] is not None
    assert out[20] is None
    assert out[50] is None


def test_compute_smas_returns_all_none_on_empty_dataframe():
    from swing.pipeline.ohlcv import compute_smas
    bars = pd.DataFrame({"Close": []})
    out = compute_smas(bars, [10, 20, 50])
    assert out == {10: None, 20: None, 50: None}


def test_compute_smas_handles_all_nan_close_column():
    from swing.pipeline.ohlcv import compute_smas
    bars = _bars([np.nan] * 50)
    out = compute_smas(bars, [10, 20, 50])
    assert out == {10: None, 20: None, 50: None}


def test_compute_smas_returns_none_when_close_column_missing():
    from swing.pipeline.ohlcv import compute_smas
    bars = pd.DataFrame({"Open": [100.0] * 50})
    out = compute_smas(bars, [10])
    assert out == {10: None}


def test_previous_close_returns_last_close():
    from swing.pipeline.ohlcv import previous_close
    bars = _bars([100.0, 101.0, 102.5])
    assert previous_close(bars) == pytest.approx(102.5)


def test_previous_close_returns_none_on_empty_or_all_nan():
    from swing.pipeline.ohlcv import previous_close
    assert previous_close(pd.DataFrame({"Close": []})) is None
    assert previous_close(_bars([np.nan, np.nan])) is None


def test_previous_close_returns_none_when_close_column_missing():
    from swing.pipeline.ohlcv import previous_close
    bars = pd.DataFrame({"Open": [100.0, 101.0]})
    assert previous_close(bars) is None
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/pipeline/test_ohlcv.py -v`
Expected: all FAIL with `ModuleNotFoundError: swing.pipeline.ohlcv`.

- [ ] **Step 3: Create the module with pure helpers**

Create `swing/pipeline/ohlcv.py`:

```python
"""Daily-bar fetch + pure SMA math for Phase 3d advisories.

Spec §3.1. `fetch_daily_bars` does the network IO; `compute_smas` and
`previous_close` are pure transformations over pandas DataFrames and are
unit-testable without yfinance.
"""
from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def compute_smas(
    bars: pd.DataFrame, periods: Sequence[int],
) -> dict[int, float | None]:
    """Return {period: float|None} from the last row of a rolling-mean over
    the 'Close' column. None if fewer bars than `period` (or 'Close' missing)."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return {p: None for p in periods}
    closes = bars["Close"].dropna()
    out: dict[int, float | None] = {}
    for p in periods:
        if len(closes) < p:
            out[p] = None
        else:
            sma = closes.rolling(p, min_periods=p).mean()
            last = sma.iloc[-1]
            out[p] = float(last) if pd.notna(last) else None
    return out


def previous_close(bars: pd.DataFrame) -> float | None:
    """Last daily bar's Close, or None if unavailable."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return None
    closes = bars["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/pipeline/test_ohlcv.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 452 passed (444 baseline + 8 new). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/ohlcv.py tests/pipeline/test_ohlcv.py
git commit -m "feat(pipeline): ohlcv.compute_smas + previous_close pure helpers"
```

---

## Task 2: `fetch_daily_bars` with in-progress-bar strip

**Files:**
- Modify: `swing/pipeline/ohlcv.py`
- Modify: `tests/pipeline/test_ohlcv.py`

Spec §3.1 second half. The IO function, with the critical session-boundary semantic: strip the in-progress daily bar using exchange-session date (not local date).

- [ ] **Step 1: Write failing tests**

Append to `tests/pipeline/test_ohlcv.py`:

```python
def test_fetch_daily_bars_strips_in_progress_bar_via_as_of_date(monkeypatch):
    """Spec §3.1: the last bar whose date == current exchange session is
    treated as in-progress and dropped before .tail(n_bars)."""
    from datetime import date
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    idx = pd.date_range("2026-04-15", periods=10, freq="B")  # Wed Apr 15 → Tue Apr 28
    closes = [100.0 + i for i in range(10)]
    df = pd.DataFrame({"Close": closes}, index=idx)

    class FakeTicker:
        def history(self, **kwargs):
            return df

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    # Treat the last bar's date as the in-progress session.
    as_of = idx[-1].date()
    result = mod.fetch_daily_bars("AAPL", n_bars=5, as_of_date=as_of)
    assert result is not None
    # Last bar stripped → max 9 remaining, tail(5) → 5 rows.
    assert len(result) == 5
    # Last retained bar is idx[-2], not idx[-1].
    assert result.index[-1].date() == idx[-2].date()


def test_fetch_daily_bars_retains_last_bar_when_complete(monkeypatch):
    """Reverse case: if the last bar's date is strictly BEFORE the session,
    it is retained (the session has rolled over; the bar is complete)."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    idx = pd.date_range("2026-04-15", periods=10, freq="B")
    closes = [100.0 + i for i in range(10)]
    df = pd.DataFrame({"Close": closes}, index=idx)

    class FakeTicker:
        def history(self, **kwargs):
            return df

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    # Session is AFTER the last bar — nothing to strip.
    as_of = idx[-1].date() + timedelta(days=5)
    result = mod.fetch_daily_bars("AAPL", n_bars=5, as_of_date=as_of)
    assert result is not None
    assert len(result) == 5
    # Last bar retained.
    assert result.index[-1].date() == idx[-1].date()


def test_fetch_daily_bars_returns_none_on_exception(monkeypatch):
    """yfinance raising → None (graceful degradation)."""
    from swing.pipeline import ohlcv as mod

    class FakeTicker:
        def history(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    assert mod.fetch_daily_bars("AAPL") is None


def test_fetch_daily_bars_returns_none_on_empty_result(monkeypatch):
    """yfinance returning empty DataFrame → None."""
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    class FakeTicker:
        def history(self, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr(mod, "yf", type("Y", (), {"Ticker": lambda self=None, t=None: FakeTicker()}))
    assert mod.fetch_daily_bars("AAPL") is None
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/pipeline/test_ohlcv.py -k "fetch_daily_bars" -v`
Expected: all 4 FAIL — `fetch_daily_bars` doesn't exist yet.

- [ ] **Step 3: Add `fetch_daily_bars` to `swing/pipeline/ohlcv.py`**

Add to the top of `swing/pipeline/ohlcv.py`:

```python
from datetime import date, datetime

import yfinance as yf

from swing.evaluation.dates import action_session_for_run
```

Then add the function (before `compute_smas`):

```python
def fetch_daily_bars(
    ticker: str, *, n_bars: int = 60, as_of_date: date | None = None,
) -> pd.DataFrame | None:
    """Fetch completed daily bars for `ticker` (spec §3.1).

    Returns up to `n_bars` rows of FULLY-COMPLETED daily bars, ending with
    the most recent completed session. Returns None on empty result or
    exception.

    Session-boundary semantics: yfinance's `history(interval='1d')` includes
    the IN-PROGRESS bar during market hours. We strip it — otherwise
    `previous_close` would reflect the partial close, turning the
    "close below MA" rule back into an intraday rule.

    `as_of_date` resolves against the EXCHANGE SESSION, not the app-local
    timezone (HST lags ET by 5h). Defaults to
    `action_session_for_run(datetime.now())` — the project's single source
    of truth for session-date resolution. Injectable for deterministic tests.

    Strip rule: drop the last row iff `last_bar.date() >= session`.

    Implementation notes:
      - `period='6mo'` (~126 trading bars) is ample for SMA50 with holiday buffer.
      - `auto_adjust=False` returns raw bars (see spec §6 for split handling).
      - `threads=False` per the yfinance rate-limit gotcha (CLAUDE.md).
    """
    try:
        df = yf.Ticker(ticker).history(
            period="6mo",
            interval="1d",
            auto_adjust=False,
            threads=False,
        )
    except Exception:
        return None
    if df is None or df.empty:
        return None
    session = as_of_date or action_session_for_run(datetime.now())
    # yfinance index is timezone-aware Timestamps; compare by .date().
    last_idx = df.index[-1]
    last_date = last_idx.date() if hasattr(last_idx, "date") else last_idx
    if last_date >= session:
        df = df.iloc[:-1]
    if df.empty:
        return None
    return df.tail(n_bars)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/pipeline/test_ohlcv.py -v`
Expected: 12 PASS (8 from T1 + 4 new).

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 456 passed (452 + 4 new).

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/ohlcv.py tests/pipeline/test_ohlcv.py
git commit -m "feat(pipeline): ohlcv.fetch_daily_bars with session-anchored in-progress-bar strip"
```

---

## Task 3: Phase 2 carve-out — `AdvisoryContext` + exit-rule swap

**Files:**
- Modify: `swing/trades/advisory.py`
- Modify: `tests/trades/test_advisory.py`

Spec §3.3 / §4.4. The ONE sanctioned Phase 2 change in Phase 3d. Adds `sma50` and `previous_close` fields to `AdvisoryContext`; changes `suggest_exit_close_below_ma` to use `ctx.previous_close`; adds a 50MA exit call in `compute_all_suggestions`.

- [ ] **Step 1: Write failing tests**

Append to `tests/trades/test_advisory.py` (after the existing `test_exit_close_below_ma`):

```python
def test_exit_close_below_ma_uses_previous_close_not_current():
    """Spec §3.3: exit rule now fires on yesterday's DAILY close vs MA,
    not on intraday current_price. If previous_close is above MA but
    current_price is below, the rule must NOT fire."""
    # current_price 185 (below 190 MA) but previous_close 195 (above) → no exit.
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=195.0),
        ma_value=190.0, ma_label="10MA",
    )
    assert s is None


def test_exit_close_below_ma_noops_when_previous_close_is_none():
    """Graceful degradation: missing previous_close → rule no-ops."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=None),
        ma_value=190.0, ma_label="10MA",
    )
    assert s is None


def test_exit_below_50ma_fires_on_previous_close_below():
    """SMA50 exit rule (Minervini) fires when yesterday's close < SMA50."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=200.0, ma50=195.0, prev_close=190.0),
        ma_value=195.0, ma_label="50MA",
    )
    assert s is not None
    assert "EXIT" in s.message
    assert "50MA" in s.message
    assert "190.00" in s.message  # previous_close echoed in message


def test_exit_below_50ma_noops_when_sma50_is_none():
    """Missing SMA50 → rule no-ops."""
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=200.0, ma50=None, prev_close=190.0),
        ma_value=None, ma_label="50MA",
    )
    assert s is None


def test_compute_all_suggestions_includes_50ma_exit():
    """compute_all_suggestions now calls suggest_exit_close_below_ma for 50MA."""
    ctx = _ctx(close=200.0, ma10=198.0, ma20=196.0, ma50=195.0, prev_close=190.0)
    sugs = compute_all_suggestions(_trade(), ctx)
    rules = {s.rule for s in sugs}
    assert "exit_below_50ma" in rules
```

Update the `_ctx(...)` factory near the top of the file to accept `ma50=` and `prev_close=` kwargs (default both None):

```python
def _ctx(close: float = 195.0, ma10: float = 190.0, ma20: float = 185.0,
         ma50: float | None = None, prev_close: float | None = None,
         weather: str = "Bullish") -> AdvisoryContext:
    return AdvisoryContext(
        as_of_date="2026-04-15", current_price=close,
        sma10=ma10, sma20=ma20, sma50=ma50,
        previous_close=prev_close,
        weather_status=weather,
        config=StopAdvisoryConfig(),
    )
```

Also update the existing `test_exit_close_below_ma` — the old test was silently passing because `current_price` was below `ma_value`. After the semantic change, it needs a `prev_close` below the MA:

```python
def test_exit_close_below_ma():
    s = suggest_exit_close_below_ma(
        _trade(),
        _ctx(close=185.0, ma10=190.0, prev_close=187.0),   # was: no prev_close arg
        ma_value=190.0, ma_label="10MA",
    )
    assert s is not None
    assert "EXIT" in s.message
    assert "10MA" in s.message
    assert "187.00" in s.message  # previous_close echoed
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/trades/test_advisory.py -v`
Expected: all 5 new-or-updated tests FAIL because `AdvisoryContext` doesn't have `sma50` / `previous_close` fields yet, and `suggest_exit_close_below_ma` still uses `current_price`.

- [ ] **Step 3: Modify `AdvisoryContext` dataclass**

In `swing/trades/advisory.py`, update the dataclass:

```python
@dataclass(frozen=True)
class AdvisoryContext:
    as_of_date: str
    current_price: float
    sma10: float | None
    sma20: float | None
    sma50: float | None                  # NEW (spec §3.3)
    previous_close: float | None         # NEW (drives exit_close_below_ma)
    weather_status: str
    config: StopAdvisoryConfig
```

- [ ] **Step 4: Rewrite `suggest_exit_close_below_ma`**

Replace the existing `suggest_exit_close_below_ma` function:

```python
def suggest_exit_close_below_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str,
) -> AdvisorySuggestion | None:
    """Minervini: "Sell on a close below the N-day MA." Fires when
    YESTERDAY'S DAILY CLOSE is below the MA — not on a live intraday tick.
    Spec §3.3."""
    if ma_value is None or ctx.previous_close is None:
        return None
    if ctx.previous_close >= ma_value:
        return None
    return AdvisorySuggestion(
        rule=f"exit_below_{ma_label.lower()}",
        message=f"EXIT \u2014 yesterday's close ${ctx.previous_close:.2f} "
                f"is below {ma_label} (${ma_value:.2f})",
    )
```

- [ ] **Step 5: Add the 50MA call in `compute_all_suggestions`**

Replace the existing `compute_all_suggestions`:

```python
def compute_all_suggestions(trade: Trade, ctx: AdvisoryContext) -> list[AdvisorySuggestion]:
    sugs: list[AdvisorySuggestion | None] = []
    sugs.append(suggest_breakeven(trade, ctx))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA",
                                  buffer_pct=ctx.config.trail_10ma_buffer_pct))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA",
                                  buffer_pct=ctx.config.trail_20ma_buffer_pct))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma50, ma_label="50MA"))  # NEW
    sugs.append(suggest_weather_action(trade, ctx))
    sugs.append(suggest_time_stop(trade, ctx))
    return [s for s in sugs if s is not None]
```

- [ ] **Step 6: Update downstream callers that construct `AdvisoryContext`**

Two production call sites currently pass positional-or-kwarg args without `sma50` / `previous_close`:

In `swing/web/view_models/dashboard.py` (around line 159), add the two new fields with None defaults:

```python
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=None,
            sma20=None,
            sma50=None,                     # NEW — wired in T12
            previous_close=None,            # NEW — wired in T12
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
```

In `swing/web/view_models/open_positions_row.py` (around line 100), add the same two fields:

```python
        ctx = AdvisoryContext(
            as_of_date=action_session,
            current_price=snapshot.price,
            sma10=None, sma20=None,
            sma50=None,                     # NEW — wired in T13
            previous_close=None,            # NEW — wired in T13
            weather_status=weather_status,
            config=cfg.stop_advisory,
        )
```

In `swing/cli.py::trade_advisory_cmd` (around line 426), add the two new fields with `None` — T4 wires them to new CLI flags:

```python
    ctx_a = AdvisoryContext(
        as_of_date=as_of_date or date.today().isoformat(),
        current_price=current_price,
        sma10=sma10, sma20=sma20,
        sma50=None,                         # NEW — CLI flag added in T4
        previous_close=None,                # NEW — CLI flag added in T4
        weather_status=weather,
        config=cfg.stop_advisory,
    )
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/trades/test_advisory.py -v`
Expected: all tests PASS (existing + 5 new).

Run the CLI tests too since we touched `cli.py`:

Run: `python -m pytest tests/cli/ -v`
Expected: all PASS.

- [ ] **Step 8: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 461 passed (456 + 5 new). No regressions.

- [ ] **Step 9: Commit**

```bash
git add swing/trades/advisory.py swing/web/view_models/dashboard.py swing/web/view_models/open_positions_row.py swing/cli.py tests/trades/test_advisory.py
git commit -m "fix(trades): AdvisoryContext +sma50 +previous_close; exit rule uses previous_close (Phase 3d carve-out)"
```

---

## Task 4: CLI `--sma50` and `--previous-close` flags

**Files:**
- Modify: `swing/cli.py::trade_advisory_cmd`
- Test: `tests/cli/` (ensure the existing CLI test file is updated or add one)

Spec §3.6. Pure additive CLI change: the command accepts the new values and plumbs them into `AdvisoryContext`. Operators invoking without the flags get the same silent-skip behavior as today.

- [ ] **Step 1: Locate the existing CLI test file for `trade advisory`**

Run: `grep -rn "trade_advisory\|trade advisory" tests/cli/ | head`
Expected: identifies `tests/cli/test_cli_advisory.py` (or equivalent) if it exists; otherwise the test lives in a catch-all CLI test file.

If the test file does not exist, create `tests/cli/test_cli_advisory.py`. Otherwise amend the existing file.

- [ ] **Step 2: Write failing test**

Append (or create) in `tests/cli/test_cli_advisory.py`:

```python
"""`swing trade advisory` CLI — SMA50 and previous-close flags (Phase 3d §3.6)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main


def test_trade_advisory_accepts_sma50_and_previous_close(tmp_path: Path, monkeypatch):
    """The command accepts --sma50 and --previous-close and plumbs them
    into AdvisoryContext. Exit code 0; output references 50MA EXIT rule."""
    from tests.cli.test_cli_eval import _minimal_config
    from swing.data.db import connect
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.models import Trade

    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    # Seed an open trade by direct repo call — avoids coupling this test
    # to the `swing trade entry` CLI (the real command name; the previous
    # plan draft used `trade enter` which does not exist).
    from swing.config import load as load_cfg
    loaded_cfg = load_cfg(cfg)
    conn = connect(loaded_cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10,
                initial_stop=170.0, current_stop=170.0,
                status="open", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            tid = insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()

    # Run advisory with SMA50 + previous-close.
    r = runner.invoke(main, [
        "--config", str(cfg), "trade", "advisory",
        "--trade-id", str(tid),
        "--current-price", "200.0",
        "--sma10", "198.0",
        "--sma20", "196.0",
        "--sma50", "195.0",
        "--previous-close", "190.0",
        "--weather", "Bullish",
    ])
    assert r.exit_code == 0, r.output
    # The 50MA exit rule should fire (previous_close 190 < sma50 195).
    assert "50MA" in r.output
    assert "190.00" in r.output
```

- [ ] **Step 3: Verify the test fails**

Run: `python -m pytest tests/cli/test_cli_advisory.py::test_trade_advisory_accepts_sma50_and_previous_close -v`
Expected: FAIL with `Error: No such option: --sma50`.

- [ ] **Step 4: Add the CLI flags**

In `swing/cli.py`, locate `trade_advisory_cmd` (around line 410) — do NOT rewrite the whole function; apply these three targeted edits:

**Edit 1 — add two `@click.option` decorators** after the existing `--sma20` option (around line 406):

```python
@click.option("--sma10", type=float, default=None)
@click.option("--sma20", type=float, default=None)
@click.option("--sma50", type=float, default=None)               # NEW
@click.option("--previous-close", type=float, default=None)      # NEW
@click.option("--weather", default="Bullish")
```

**Edit 2 — add the two parameters to the function signature** (around line 410):

```python
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, sma50,
                        previous_close, weather, as_of_date):
```

**Edit 3 — replace the `sma50=None` + `previous_close=None` literals** added in T3 with the parameter names. Find the `AdvisoryContext(...)` construction inside the function (around line 426) and change:

```python
    ctx_a = AdvisoryContext(
        ...
        sma10=sma10, sma20=sma20,
        sma50=None,                 # ← was set to None literal in T3
        previous_close=None,        # ← was set to None literal in T3
        weather_status=weather,
        ...
    )
```

To:

```python
    ctx_a = AdvisoryContext(
        ...
        sma10=sma10, sma20=sma20,
        sma50=sma50,                         # NEW — flag value from --sma50
        previous_close=previous_close,       # NEW — flag value from --previous-close
        weather_status=weather,
        ...
    )
```

Preserve the rest of the function body (the existing `connect / get_trade / compute_all_suggestions / click.echo` flow) verbatim.

- [ ] **Step 5: Run the test**

Run: `python -m pytest tests/cli/test_cli_advisory.py::test_trade_advisory_accepts_sma50_and_previous_close -v`
Expected: PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 462 passed (461 + 1 new). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/cli.py tests/cli/test_cli_advisory.py
git commit -m "feat(cli): trade advisory gains --sma50 and --previous-close flags"
```

---

## Task 5: Config fields (`ohlcv_cache_ttl_seconds`, `max_concurrent_ohlcv_fetches`)

**Files:**
- Modify: `swing/config.py::Web`
- Test: `tests/web/test_config_web.py`

Spec §3.7. Two new knobs on `Web`. Defaults: TTL 3600s, max concurrent 8. The TOML parser is generic field-name match (Phase 3c noted this), so no parser change is needed.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_config_web.py`:

```python
def test_web_config_has_ohlcv_cache_ttl_seconds_default():
    """Phase 3d §3.7: Web.ohlcv_cache_ttl_seconds defaults to 3600."""
    from swing.config import Web
    w = Web()
    assert w.ohlcv_cache_ttl_seconds == 3600


def test_web_config_has_max_concurrent_ohlcv_fetches_default():
    """Phase 3d §3.7: Web.max_concurrent_ohlcv_fetches defaults to 8."""
    from swing.config import Web
    w = Web()
    assert w.max_concurrent_ohlcv_fetches == 8


def test_web_config_ohlcv_fields_parsed_from_toml(tmp_path: Path):
    """Phase 3d §3.7: TOML overrides land on the cfg."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _write_cfg(
        project, home,
        extra='[web]\nohlcv_cache_ttl_seconds = 1800\nmax_concurrent_ohlcv_fetches = 4\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.ohlcv_cache_ttl_seconds == 1800
    assert cfg.web.max_concurrent_ohlcv_fetches == 4
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/web/test_config_web.py -k "ohlcv" -v`
Expected: all 3 FAIL with `AttributeError` — fields don't exist yet.

- [ ] **Step 3: Add the fields to `swing/config.py::Web`**

In `swing/config.py`, extend the `Web` dataclass (around line 140, after `csv_upload_max_bytes`):

```python
@dataclass(frozen=True)
class Web:
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    price_cache_ttl_seconds: int = 120
    price_fetch_timeout_seconds: int = 3
    price_fetch_deadline_seconds: int = 6
    max_concurrent_price_fetches: int = 8
    circuit_breaker_cooldown_seconds: int = 60
    polling_interval_seconds: int = 2
    csv_upload_max_bytes: int = 10 * 1024 * 1024
    ohlcv_cache_ttl_seconds: int = 3600              # NEW: 1h default (§3.7)
    max_concurrent_ohlcv_fetches: int = 8            # NEW: full executor (§3.2)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_config_web.py -k "ohlcv" -v`
Expected: 3 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 465 passed (462 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add swing/config.py tests/web/test_config_web.py
git commit -m "feat(config): Web gains ohlcv_cache_ttl_seconds + max_concurrent_ohlcv_fetches"
```

---

## Task 6: `OhlcvCache` class with sliding-window breaker

**Files:**
- Create: `swing/web/ohlcv_cache.py`
- Test: `tests/web/test_ohlcv_cache.py`

Spec §3.2 + §4.3 + §4.4. TTL-cached bundles, sliding-window breaker that counts deadline misses as failures, semaphore-bounded executor use.

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_ohlcv_cache.py`:

```python
"""OhlcvCache — TTL cache + sliding-window breaker + deadline-as-failure.
Spec §3.2, §4.3, §4.4."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from swing.config import Config


@pytest.fixture
def cfg(test_cfg):
    c, _ = test_cfg
    return c


def _bars(closes, start="2026-01-02") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(closes), freq="B")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_cache_hit_returns_bundle_without_refetch(cfg, monkeypatch):
    """A hit within TTL returns the cached bundle and does NOT re-invoke fetch."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    calls = {"n": 0}

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
        calls["n"] += 1
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r1["AAPL"].sma10 is not None
    assert r2["AAPL"].sma10 is not None
    assert calls["n"] == 1, "second call should be a cache hit"


def test_cache_miss_triggers_fetch_and_stores_bundle(cfg, monkeypatch):
    """A first-time request fetches and caches."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
        return _bars([100.0 + i for i in range(50)])

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r["AAPL"].sma10 is not None
    assert r["AAPL"].sma20 is not None
    assert r["AAPL"].sma50 is not None
    assert r["AAPL"].previous_close is not None


def test_ttl_expiry_triggers_refetch(cfg, monkeypatch):
    """Past TTL → cache entry is evicted and refetched."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    # Override TTL to 0.1s for test speed.
    from dataclasses import replace as _replace
    tiny_web = _replace(cfg.web, ohlcv_cache_ttl_seconds=0)
    tiny_cfg = _replace(cfg, web=tiny_web)

    calls = {"n": 0}
    def fake_fetch(ticker, *, n_bars=60, as_of_date=None):
        calls["n"] += 1
        return _bars([100.0] * 50)

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)
    cache = OhlcvCache(tiny_cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
        time.sleep(0.05)
        cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert calls["n"] == 2, "TTL expired → refetch"


def test_deadline_miss_returns_empty_bundle_and_is_not_cached(cfg, monkeypatch):
    """A fetch that misses the deadline returns OhlcvBundle.empty() and does
    NOT pollute the cache. Next request re-attempts."""
    from swing.web.ohlcv_cache import OhlcvCache, OhlcvBundle
    from swing.pipeline import ohlcv as ohlcv_mod

    call_count = {"n": 0}

    def slow_fetch(ticker, *, n_bars=60, as_of_date=None):
        call_count["n"] += 1
        # First call sleeps past the deadline; second call returns immediately.
        if call_count["n"] == 1:
            time.sleep(0.3)
            return _bars([100.0] * 50)
        return _bars([100.0] * 50)

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", slow_fetch)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        r1 = cache.get_many_bundles(["AAPL"], deadline_seconds=0.05, executor=ex)
        r2 = cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert r1["AAPL"].sma10 is None, "deadline miss → empty bundle"
    assert r2["AAPL"].sma10 is not None, "next request re-fetches (no cached empty)"


def test_circuit_breaker_trips_when_failure_fraction_exceeds_half(cfg, monkeypatch):
    """Mirrors PriceCache sliding-window: >50% failures in window → breaker
    trips. Deadline misses count as failures (spec §4.3)."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=4) as ex:
        # Force enough requests to fill the window and exceed 50%.
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert cache.is_degraded() is True


def test_is_degraded_clears_after_cooldown(cfg, monkeypatch):
    """After the breaker cools down, is_degraded() returns False."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    # Override breaker cooldown to 0.1s.
    from dataclasses import replace as _replace
    fast_web = _replace(cfg.web, circuit_breaker_cooldown_seconds=0)
    fast_cfg = _replace(cfg, web=fast_web)

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(fast_cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    # With cooldown=0 the breaker should already have cleared.
    time.sleep(0.01)
    assert cache.is_degraded() is False


def test_reset_circuit_breaker_clears_degraded(cfg, monkeypatch):
    """Explicit reset clears the window + the degraded flag."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    def always_fail(ticker, *, n_bars=60, as_of_date=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", always_fail)
    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for _ in range(20):
            cache.get_many_bundles(["AAPL"], deadline_seconds=5.0, executor=ex)
    assert cache.is_degraded() is True
    cache.reset_circuit_breaker()
    assert cache.is_degraded() is False
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/web/test_ohlcv_cache.py -v`
Expected: all FAIL with `ModuleNotFoundError: swing.web.ohlcv_cache`.

- [ ] **Step 3: Create `swing/web/ohlcv_cache.py`**

```python
"""OhlcvCache — TTL-cached daily-bar bundles with sliding-window circuit breaker.

Spec §3.2, §4.3, §4.4. Mirrors PriceCache's shape for callers; internals follow
PriceCache's sliding-window breaker (see swing/web/price_cache.py:207-219).

Key semantics:
- Keyed by uppercase ticker (normalization at cache boundary; DB stores upper).
- TTL from cfg.web.ohlcv_cache_ttl_seconds (default 3600s).
- Bundle fields default None → SMA rules silently no-op per spec §6.
- get_many_bundles records one sliding-window outcome per requested ticker
  (success if bundle produced, failure if deadline miss OR fetch raised).
- Semaphore-bounded executor submissions (cfg.web.max_concurrent_ohlcv_fetches).
"""
from __future__ import annotations

import collections
import logging
import threading
import time
from collections.abc import Sequence
from concurrent.futures import Executor, Future, wait
from dataclasses import dataclass

from swing.config import Config
from swing.pipeline import ohlcv as ohlcv_mod

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OhlcvBundle:
    """SMA10/20/50 + previous close from a single daily-bar fetch. All fields
    are None if the fetch failed or the bar history was insufficient for the
    given period. `fetched_at` is a monotonic timestamp (time.monotonic()).
    """
    sma10: float | None
    sma20: float | None
    sma50: float | None
    previous_close: float | None
    fetched_at: float

    @classmethod
    def empty(cls, fetched_at: float) -> "OhlcvBundle":
        return cls(None, None, None, None, fetched_at)


class OhlcvCache:
    """TTL-cached OhlcvBundle store + circuit breaker. Thread-safe. Spec §3.2."""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._ttl = cfg.web.ohlcv_cache_ttl_seconds
        self._sema = threading.Semaphore(cfg.web.max_concurrent_ohlcv_fetches)
        self._lock = threading.Lock()
        self._store: dict[str, tuple[OhlcvBundle, float]] = {}
        # Sliding window of recent outcomes (True = failure). Matches PriceCache.
        self._failure_window: collections.deque[bool] = collections.deque(maxlen=20)
        self._degraded_until: float | None = None

    # ---------- public API ----------

    def get_many_bundles(
        self, tickers: Sequence[str], *,
        deadline_seconds: float, executor: Executor,
    ) -> dict[str, OhlcvBundle]:
        """Return {ticker: OhlcvBundle} for every requested ticker.

        Cache-hits served from memory. Misses dispatched to `executor` under
        the semaphore. Any ticker that doesn't complete before
        `deadline_seconds` receives `OhlcvBundle.empty()` (not cached).

        Spec §4.3: each ticker's outcome (success if bundle produced, failure
        if deadline miss OR fetch raised) is recorded in the sliding window.

        Degraded short-circuit (R2 Major 2 resolution): when the breaker is
        tripped, skip executor submission entirely — every ticker gets
        `OhlcvBundle.empty()` without a fetch, reducing load on the failing
        yfinance endpoint. `is_degraded()` auto-clears the window after the
        cooldown expires so recovery can proceed.
        """
        normalized = [t.upper() for t in tickers]

        # R2 Major 2: degraded short-circuit BEFORE any executor submission.
        # Reduces load on yfinance during outages. Cooldown auto-clears the
        # window via is_degraded(), so recovery happens naturally once the
        # cooldown expires and fresh fetches start flowing.
        if self.is_degraded():
            return {t: OhlcvBundle.empty(fetched_at=time.monotonic()) for t in normalized}

        now = time.monotonic()
        out: dict[str, OhlcvBundle] = {}
        to_fetch: list[str] = []

        # Cache scan.
        with self._lock:
            for t in normalized:
                hit = self._store.get(t)
                if hit is not None and (now - hit[1]) <= self._ttl:
                    out[t] = hit[0]
                else:
                    to_fetch.append(t)

        # Record one "success" outcome per cache hit (cache hits count as
        # successful data acquisition for breaker accounting).
        for _ in range(len(normalized) - len(to_fetch)):
            self._record_outcome(success=True)

        if not to_fetch:
            self._maybe_trip_breaker()
            return out

        # Dispatch misses.
        futures: dict[Future, str] = {}
        for t in to_fetch:
            fut = executor.submit(self._fetch_bundle_worker, t)
            futures[fut] = t

        deadline = time.monotonic() + deadline_seconds
        remaining = max(0.0, deadline - time.monotonic())
        done, pending = wait(list(futures.keys()), timeout=remaining)

        # Completed-in-deadline fetches — request thread owns the cache write
        # (R1 Critical 1 resolution: worker MUST NOT mutate _store, because
        # `fut.cancel()` on a running worker is a no-op and a late-completing
        # worker would otherwise overwrite the empty bundle we just reported).
        for fut in done:
            t = futures[fut]
            try:
                bundle = fut.result(timeout=0)
            except Exception as exc:
                log.warning("ohlcv fetch raised for %s: %s", t, exc)
                bundle = OhlcvBundle.empty(fetched_at=time.monotonic())
                out[t] = bundle
                self._record_outcome(success=False)
                continue
            out[t] = bundle
            success = any(
                v is not None for v in (
                    bundle.sma10, bundle.sma20, bundle.sma50, bundle.previous_close,
                )
            )
            self._record_outcome(success=success)
            # Cache only successful bundles, and ONLY from the request thread
            # (for futures that completed in time). Late workers' results are
            # discarded — their bundle is never visible to the caller OR the
            # cache.
            if success:
                fetched = bundle.fetched_at
                with self._lock:
                    self._store[t] = (bundle, fetched)

        # Deadline misses — worker may still be running but its result will
        # be discarded (we do not read its future again).
        for fut in pending:
            t = futures[fut]
            fut.cancel()   # may or may not stop it; worker's result is ignored either way
            out[t] = OhlcvBundle.empty(fetched_at=time.monotonic())
            self._record_outcome(success=False)

        self._maybe_trip_breaker()
        return out

    def is_degraded(self) -> bool:
        """Return True if the breaker is currently tripped. Auto-clears the
        failure window when the cooldown expires so the next fetch attempt
        starts with a clean slate (recovery path — R2 Major 2)."""
        with self._lock:
            if self._degraded_until is not None and time.monotonic() >= self._degraded_until:
                # Cooldown expired — reset state for recovery.
                self._failure_window.clear()
                self._degraded_until = None
            return self._degraded_until is not None

    def reset_circuit_breaker(self) -> None:
        """Clear degraded state + failure window. Phase 3d doesn't call this
        from any route; reserved for a future /ohlcv/refresh endpoint."""
        with self._lock:
            self._failure_window.clear()
            self._degraded_until = None

    # ---------- internals ----------

    def _fetch_bundle_worker(self, ticker: str) -> OhlcvBundle:
        """Worker: acquire semaphore, fetch bars, build bundle. Pure return —
        does NOT touch self._store (cache writes happen on the request thread
        in get_many_bundles; see R1 Critical 1)."""
        with self._sema:
            bars = ohlcv_mod.fetch_daily_bars(ticker, n_bars=60)
            now = time.monotonic()
            if bars is None:
                return OhlcvBundle.empty(fetched_at=now)
            smas = ohlcv_mod.compute_smas(bars, [10, 20, 50])
            prev = ohlcv_mod.previous_close(bars)
            return OhlcvBundle(
                sma10=smas.get(10),
                sma20=smas.get(20),
                sma50=smas.get(50),
                previous_close=prev,
                fetched_at=now,
            )

    def _record_outcome(self, *, success: bool) -> None:
        with self._lock:
            self._failure_window.append(not success)

    def _maybe_trip_breaker(self) -> None:
        """Trip the breaker when failure fraction in the sliding window
        exceeds 50%. Cooldown uses cfg.web.circuit_breaker_cooldown_seconds."""
        with self._lock:
            if not self._failure_window:
                return
            failures = sum(1 for x in self._failure_window if x)
            if failures / len(self._failure_window) > 0.5:
                cooldown = self._cfg.web.circuit_breaker_cooldown_seconds
                self._degraded_until = time.monotonic() + cooldown
                log.warning(
                    "ohlcv cache entered degraded mode for %ss (failures=%d/%d)",
                    cooldown, failures, len(self._failure_window),
                )
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_ohlcv_cache.py -v`
Expected: all 7 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 472 passed (465 + 7 new). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/ohlcv_cache.py tests/web/test_ohlcv_cache.py
git commit -m "feat(web): OhlcvCache with TTL + sliding-window breaker (deadline-as-failure)"
```

---

## Task 7: App startup wiring — `app.state.ohlcv_cache`

**Files:**
- Modify: `swing/web/app.py`
- Test: `tests/web/test_app_smoke.py`

Spec §3.5. One-liner: build the cache at app startup and attach to `app.state`.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_app_smoke.py`:

```python
def test_app_state_ohlcv_cache_is_ohlcv_cache(test_cfg):
    """Spec §3.5: OhlcvCache is built at startup and attached to app.state."""
    from swing.web.app import create_app
    from swing.web.ohlcv_cache import OhlcvCache

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert isinstance(app.state.ohlcv_cache, OhlcvCache)
```

- [ ] **Step 2: Verify the test fails**

Run: `python -m pytest tests/web/test_app_smoke.py::test_app_state_ohlcv_cache_is_ohlcv_cache -v`
Expected: FAIL with `AttributeError: 'State' object has no attribute 'ohlcv_cache'`.

- [ ] **Step 3: Wire the cache in `create_app`**

In `swing/web/app.py`, add the import near the top (alongside `PriceCache`):

```python
from swing.web.ohlcv_cache import OhlcvCache
```

In `create_app`, after the existing `app.state.price_cache = PriceCache(cfg)` (around line 114), add:

```python
    app.state.price_cache = PriceCache(cfg)
    app.state.ohlcv_cache = OhlcvCache(cfg)     # NEW — Phase 3d §3.5
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/web/test_app_smoke.py::test_app_state_ohlcv_cache_is_ohlcv_cache -v`
Expected: PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 473 passed (472 + 1 new).

- [ ] **Step 6: Commit**

```bash
git add swing/web/app.py tests/web/test_app_smoke.py
git commit -m "feat(web): app.state.ohlcv_cache built at startup"
```

---

## Task 8: Add `ohlcv_source_degraded: bool = False` to every base-layout VM

**Files:**
- Modify: `swing/web/view_models/dashboard.py` (DashboardVM)
- Modify: `swing/web/view_models/pipeline.py` (PipelineVM)
- Modify: `swing/web/view_models/journal.py` (JournalVM)
- Modify: `swing/web/view_models/watchlist.py` (WatchlistVM)
- Modify: `swing/web/view_models/error.py` (PageErrorVM)

Spec §3.4 "Template / view-model surface changes". **This MUST land before Task 9** (base.html.j2 conditional) — otherwise unrelated routes would 500 with `UndefinedError` on `vm.ohlcv_source_degraded`.

No test is added here — the base-layout compat test in Task 16 validates that all five VMs carry the field correctly.

- [ ] **Step 1: Add the field to DashboardVM**

In `swing/web/view_models/dashboard.py`, locate the `DashboardVM` dataclass (around line 49-69). Add the new field before `open_trade_rows` (keep `open_trade_rows` last since it has a default):

```python
@dataclass(frozen=True)
class DashboardVM:
    generated_at: str
    session_date: str
    stale_banner: str | None
    status_strip: StatusStripVM
    today_decisions: list[DecisionVM]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]]
    open_trade_last_prices: Mapping[str, PriceSnapshot]
    watchlist_top5: list[WatchlistEntry]
    watchlist_remaining_count: int
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
    open_trade_rows: Mapping[int, object] = field(default_factory=dict)
```

Note: `ohlcv_source_degraded` has a default so existing `DashboardVM(...)` construction in `build_dashboard` still compiles until Task 12 populates it. The default is `False`, which means the banner does NOT render until `build_dashboard` sets it to `True` based on `ohlcv_cache.is_degraded()`.

- [ ] **Step 2: Add the field to PipelineVM**

In `swing/web/view_models/pipeline.py`:

```python
@dataclass(frozen=True)
class PipelineVM:
    session_date: str
    recent_runs: list[PipelineRun]
    stale_run: PipelineRun | None = None
    # Base-template banner fields
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
```

- [ ] **Step 3: Add the field to JournalVM**

In `swing/web/view_models/journal.py`:

```python
@dataclass(frozen=True)
class JournalVM:
    period: str
    stats: JournalStats
    flags: list[BehavioralFlag]
    trades: list[Trade]
    # Fields required by base.html.j2 (uniform banner guards)
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
```

- [ ] **Step 4: Add the field to WatchlistVM**

In `swing/web/view_models/watchlist.py`:

```python
@dataclass(frozen=True)
class WatchlistVM:
    session_date: str
    rows: list[WatchlistEntry]
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    stale_banner: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
```

- [ ] **Step 5: Add the field to PageErrorVM**

In `swing/web/view_models/error.py`:

```python
@dataclass(frozen=True)
class PageErrorVM:
    """Context for page_error.html.j2. ..."""
    session_date: str
    stale_banner: None = None
    price_source_degraded: bool = False
    status_code: int = 400
    detail: str = "Invalid request"
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
```

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 473 passed. All existing tests still pass — the defaults mean existing construction sites don't break.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/
git commit -m "feat(web): every base-layout VM gains ohlcv_source_degraded=False default (Phase 3d §3.4)"
```

---

## Task 9: Base-layout banner (conditional include in `base.html.j2`)

**Files:**
- Create: `swing/web/templates/partials/ohlcv_degraded_banner.html.j2`
- Modify: `swing/web/templates/base.html.j2`

Spec §6. Page-level banner when `vm.ohlcv_source_degraded` is True. The partial pattern mirrors the existing `stale_banner` and `price_degraded_banner` includes.

- [ ] **Step 1: Create the partial**

Create `swing/web/templates/partials/ohlcv_degraded_banner.html.j2`:

```jinja
{#- swing/web/templates/partials/ohlcv_degraded_banner.html.j2
    Phase 3d §6. Rendered when vm.ohlcv_source_degraded is True (OhlcvCache
    circuit breaker tripped). Signals to the operator that trail-MA and
    close-below-MA rules will not fire until service recovers — critical
    for distinguishing "no exit condition" from "data unavailable". -#}
<div class="banner banner-degraded" role="status">
  ⚠ SMA advisories unavailable — daily-bar fetch is in a cool-down period.
  Trail-MA and close-below-MA rules will not fire until service recovers.
</div>
```

- [ ] **Step 2: Add the conditional to base.html.j2**

In `swing/web/templates/base.html.j2`, add the include alongside the existing banners:

```jinja
  {% if vm.stale_banner %}
    {% include "partials/stale_banner.html.j2" %}
  {% endif %}
  {% if vm.price_source_degraded %}
    {% include "partials/price_degraded_banner.html.j2" %}
  {% endif %}
  {% if vm.ohlcv_source_degraded %}                                   {# NEW (Phase 3d §6) #}
    {% include "partials/ohlcv_degraded_banner.html.j2" %}
  {% endif %}
```

- [ ] **Step 3: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 473 passed. The banner is gated on `vm.ohlcv_source_degraded` which defaults to `False` on every VM (Task 8), so existing tests render unchanged pages.

- [ ] **Step 4: Commit**

```bash
git add swing/web/templates/partials/ohlcv_degraded_banner.html.j2 swing/web/templates/base.html.j2
git commit -m "feat(web): conditional OHLCV-degraded banner in base.html.j2"
```

---

## Task 10: `build_pipeline` gains `ohlcv_degraded` kwarg

**Files:**
- Modify: `swing/web/view_models/pipeline.py::build_pipeline`

Spec §3.4 R4 pass-through. `build_pipeline` accepts an optional `ohlcv_degraded` flag (default `False`) and forwards it into `PipelineVM.ohlcv_source_degraded`. The VM builder stays decoupled from `app.state`; the ROUTE (Task 11) computes and passes the flag.

No new test is added here — Task 16's `/pipeline` test with the toggled flag exercises this seam.

- [ ] **Step 1: Extend the signature + constructor call**

In `swing/web/view_models/pipeline.py`:

```python
def build_pipeline(
    *, cfg: Config, limit: int = 10, ohlcv_degraded: bool = False,
) -> PipelineVM:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            runs = list_recent_runs(conn, limit=limit)
            active = find_active_run(conn)
            stale = active if (active is not None and is_stale_eligible(active, cfg)) else None
    finally:
        conn.close()
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
        stale_run=stale,
        ohlcv_source_degraded=ohlcv_degraded,            # NEW (Phase 3d §3.4)
    )
```

- [ ] **Step 2: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 473 passed. No regressions — all existing callers of `build_pipeline` pass no new arg; the default (`False`) preserves current behavior.

- [ ] **Step 3: Commit**

```bash
git add swing/web/view_models/pipeline.py
git commit -m "feat(web): build_pipeline gains ohlcv_degraded kwarg (default False)"
```

---

## Task 11: Pipeline route passes `ohlcv_degraded` flag

**Files:**
- Modify: `swing/web/routes/pipeline.py::pipeline_page`

Spec §3.4 R4 pass-through continued. Route computes `request.app.state.ohlcv_cache.is_degraded()` and passes to `build_pipeline`.

- [ ] **Step 1: Update the route**

In `swing/web/routes/pipeline.py`:

```python
@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    cfg = request.app.state.cfg
    ohlcv_degraded = request.app.state.ohlcv_cache.is_degraded()      # NEW
    vm = build_pipeline(cfg=cfg, ohlcv_degraded=ohlcv_degraded)       # NEW kwarg
    return request.app.state.templates.TemplateResponse(
        request, "pipeline.html.j2", {"vm": vm},
    )
```

- [ ] **Step 2: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 473 passed. No regressions.

- [ ] **Step 3: Commit**

```bash
git add swing/web/routes/pipeline.py
git commit -m "feat(web): /pipeline route computes and passes ohlcv_degraded flag"
```

---

## Task 12: `build_dashboard` plumbs OHLCV + populates degraded flag

**Files:**
- Modify: `swing/web/view_models/dashboard.py::build_dashboard`
- Test: `tests/web/test_view_models/test_dashboard.py`

Spec §3.4 + §2.3. The dashboard's VM builder receives `ohlcv_cache`, calls it sequentially after `cache.get_many`, and plumbs per-ticker bundle values into `AdvisoryContext`. Populates `DashboardVM.ohlcv_source_degraded` from `ohlcv_cache.is_degraded()`.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_view_models/test_dashboard.py`:

```python
def _seed_open_trade_direct(cfg, *, ticker: str, entry_price: float, shares: int) -> int:
    """Helper: insert an open trade via the repo, returning its id. Avoids
    coupling this test to any specific CLI command name."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=entry_price, initial_shares=shares,
                initial_stop=entry_price * 0.95, current_stop=entry_price * 0.95,
                status="open", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            return insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()


def test_build_dashboard_plumbs_ohlcv_bundle_into_advisory_context(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4: when ohlcv_cache returns a bundle with SMAs + previous_close,
    those values must appear in the AdvisoryContext inputs for each open trade."""
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.view_models import dashboard as dm
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    # Patch the ohlcv_cache to return a canned bundle.
    # NB: monkeypatching a CLASS METHOD — the first arg is `self`, so the
    # fake MUST accept it (Codex R1 Major 4 correction).
    def fake_bundles(self, tickers, *, deadline_seconds, executor):
        return {t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                                previous_close=190.0, fetched_at=0.0)
                for t in tickers}

    monkeypatch.setattr(OhlcvCache, "get_many_bundles", fake_bundles)
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    # Patch PriceCache.get_many to return a canned live price.
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = dm.build_dashboard(
            cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache, executor=ex,
        )

    # The open-positions row for AAPL should show SMA50 exit advisory
    # (previous_close 190 < sma50 195).
    assert len(vm.open_trades) == 1
    advisories = vm.open_trade_advisories[vm.open_trades[0].id]
    rules = {a.rule for a in advisories}
    assert "exit_below_50ma" in rules
    assert vm.ohlcv_source_degraded is False


def test_build_dashboard_reflects_ohlcv_degraded_flag(test_cfg, seeded_db, monkeypatch):
    """Spec §3.4: DashboardVM.ohlcv_source_degraded is True when the cache is."""
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.view_models import dashboard as dm
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache

    cfg, _ = test_cfg

    monkeypatch.setattr(OhlcvCache, "get_many_bundles",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: True)
    monkeypatch.setattr(PriceCache, "get_many",
                        lambda self, tickers, *, deadline_seconds, executor: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = dm.build_dashboard(
            cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache, executor=ex,
        )
    assert vm.ohlcv_source_degraded is True
```

Use `_seed_open_trade_direct` (defined above in this test file) — it's the local helper that inserts an open trade via the repo. `test_cfg` + `seeded_db` are existing conftest fixtures that give you a config and a migrated DB respectively.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/web/test_view_models/test_dashboard.py -k "plumbs_ohlcv_bundle or reflects_ohlcv_degraded" -v`
Expected: FAIL — `build_dashboard` doesn't accept `ohlcv_cache` kwarg yet.

- [ ] **Step 3: Update `build_dashboard` signature + body**

In `swing/web/view_models/dashboard.py`, change the signature. **The `ohlcv_cache` kwarg is OPTIONAL with a `None` default** so existing production call sites (dashboard route, 2× trades route, pipeline route) remain callable until Tasks 14-15 wire them — the codebase stays green between T12 and T14/15 (R2 Major 1 resolution):

```python
def build_dashboard(
    *, cfg: Config, cache: PriceCache, executor, ohlcv_cache=None,
) -> DashboardVM:
    """Read state + prices + OHLCV bundles, return a frozen VM.

    When `ohlcv_cache=None` (transitional — wired in T14/15), the OHLCV fetch
    is skipped and all SMA fields fall through to None, so the dashboard
    renders without SMA advisories. `executor` may be None in tests.
    """
```

Inside the body, **after** the existing `prices = cache.get_many(...)` call (around line 137-141), add the conditional OHLCV fetch:

```python
    prices = cache.get_many(
        sorted(active_tickers),
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    # Sequential top-level call (spec §2.2) — each cache internally parallelizes
    # per-ticker fetches across the executor. Sequential ordering prevents a
    # nested-futures deadlock and starvation under small executor pools.
    # When ohlcv_cache is None (transitional — pre-T14/15 callers), skip the
    # fetch entirely; bundles stays empty so SMA rules no-op gracefully.
    bundles: dict = {}
    if ohlcv_cache is not None:
        bundles = ohlcv_cache.get_many_bundles(
            sorted(active_tickers),
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )
```

Change the per-trade `AdvisoryContext` construction (around line 159-166) to pull from the bundle:

```python
        snap = prices.get(t.ticker)
        remaining = t.initial_shares - sum(e.shares for e in exits_by_trade.get(t.id, []))
        bundle = bundles.get(t.ticker)        # may be None or all-None
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv) if snap else []
```

At the end, populate `DashboardVM.ohlcv_source_degraded` — guarded so `None` callers don't crash:

```python
    degraded_until = cache.degraded_until()
    return DashboardVM(
        generated_at=now.isoformat(timespec="seconds"),
        session_date=action_session,
        stale_banner=stale_banner,
        status_strip=status_strip,
        today_decisions=today_decisions,
        open_trades=list(open_trades),
        open_trade_advisories=open_trade_advisories,
        open_trade_last_prices=open_trade_last_prices,
        watchlist_top5=list(top5),
        watchlist_remaining_count=max(0, len(watchlist) - 5),
        watchlist_last_prices=watchlist_last_prices,
        flag_tags=flag_tags,
        candidates_by_ticker=candidates_by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
        ohlcv_source_degraded=(
            ohlcv_cache.is_degraded() if ohlcv_cache is not None else False
        ),                                                       # NEW
        open_trade_rows=open_trade_rows,
    )
```

Remove the stale inline comment `"SMA-dependent rules return None until Phase 3c"` if it appears in the body comments (the spec §1.1 notes it).

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_view_models/test_dashboard.py -k "plumbs_ohlcv_bundle or reflects_ohlcv_degraded" -v`
Expected: 2 PASS.

- [ ] **Step 5: Run full fast suite (some existing tests may break)**

Run: `python -m pytest -m "not slow" -q`

**Expected regressions:** existing integration tests that call `build_dashboard(cfg=..., cache=..., executor=...)` (no `ohlcv_cache`) will fail with `TypeError`. Those call sites must be updated in the same task — find them and pass a test double (a cache-like object or a `MagicMock` with `get_many_bundles`/`is_degraded`/`degraded_until` stubs).

Run: `grep -rn "build_dashboard(" tests/ | head`

For each hit, update the call to:

```python
    vm = build_dashboard(cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache, executor=executor)
```

If the existing test didn't need an ohlcv_cache, inject a `MagicMock` with the following minimal shape:

```python
from unittest.mock import MagicMock
ohlcv_cache = MagicMock()
ohlcv_cache.get_many_bundles.return_value = {}
ohlcv_cache.is_degraded.return_value = False
```

Re-run the full fast suite after updating all fixtures:

Expected: 475 passed (473 + 2 new). No remaining failures.

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/test_view_models/test_dashboard.py tests/
git commit -m "feat(web): build_dashboard plumbs OHLCV bundles + populates ohlcv_source_degraded"
```

---

## Task 13: `build_open_positions_row` accepts `ohlcv_cache` + plumbs bundle

**Files:**
- Modify: `swing/web/view_models/open_positions_row.py::build_open_positions_row`
- Test: `tests/web/test_view_models/test_open_positions_row.py`

Spec §3.4. Single-ticker wrapper mirrors the dashboard's plumbing. Consumed by `swing/web/routes/trades.py` POST-success handlers (~4 call sites).

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_view_models/test_open_positions_row.py`:

```python
def test_build_open_positions_row_plumbs_ohlcv_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4: build_open_positions_row receives ohlcv_cache and plumbs
    sma10/20/50 + previous_close into AdvisoryContext."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    from swing.web.view_models.open_positions_row import build_open_positions_row
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.data.models import Trade

    cfg, _ = test_cfg
    trade = Trade(
        id=1, ticker="AAPL", entry_date="2026-04-15", entry_price=180.0,
        initial_shares=10, initial_stop=170.0, current_stop=170.0,
        status="open", watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )

    cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        vm = build_open_positions_row(
            trade=trade, cfg=cfg, cache=cache, ohlcv_cache=ohlcv_cache,
            executor=ex,
        )

    rules = {a.rule for a in vm.advisories}
    assert "exit_below_50ma" in rules
```

- [ ] **Step 2: Verify the test fails**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -k "plumbs_ohlcv_bundle" -v`
Expected: FAIL — `build_open_positions_row` doesn't accept `ohlcv_cache`.

- [ ] **Step 3: Update `build_open_positions_row`**

In `swing/web/view_models/open_positions_row.py`, change the signature. **`ohlcv_cache` is OPTIONAL with a `None` default** so existing call sites in `swing/web/routes/trades.py` (4 sites) remain callable until Task 15 wires them (R2 Major 1 resolution):

```python
def build_open_positions_row(
    *, trade: Trade, cfg: Config, cache: PriceCache, executor,
    ohlcv_cache=None,
    conn: sqlite3.Connection | None = None,
) -> OpenPositionsRowVM:
```

Update the body (around line 73-110). After `snapshot = prices.get(trade.ticker)` (line 78), add the conditional OHLCV fetch:

```python
    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snapshot = prices.get(trade.ticker)
    # Sequential OHLCV fetch (spec §2.2). When ohlcv_cache is None (pre-T15
    # callers), skip the fetch; bundle stays None so SMA rules no-op.
    bundle = None
    if ohlcv_cache is not None:
        bundles = ohlcv_cache.get_many_bundles(
            [trade.ticker],
            deadline_seconds=cfg.web.price_fetch_deadline_seconds,
            executor=executor,
        )
        bundle = bundles.get(trade.ticker)
```

Update the `AdvisoryContext` construction (around line 98-106):

```python
    advisories: tuple[AdvisorySuggestionVM, ...] = ()
    if snapshot is not None:
        ctx = AdvisoryContext(
            as_of_date=action_session,
            current_price=snapshot.price,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(trade, ctx)
        advisories = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )
```

Remove or update the stale docstring line `"compute_all_suggestions(trade, AdvisoryContext(sma10=None, sma20=None, ...))"`.

- [ ] **Step 4: Run the new test**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -k "plumbs_ohlcv_bundle" -v`
Expected: PASS.

- [ ] **Step 5: Run full fast suite (more existing tests may break)**

Run: `python -m pytest -m "not slow" -q`

**Expected regressions:** existing tests that call `build_open_positions_row(...)` without `ohlcv_cache` will fail. Find them:

Run: `grep -rn "build_open_positions_row(" tests/ | head`

Update each call site to pass `ohlcv_cache=MagicMock(...)` (same pattern as Task 12). Re-run:

Expected: 476 passed (475 + 1 new). No remaining failures.

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/open_positions_row.py tests/
git commit -m "feat(web): build_open_positions_row accepts ohlcv_cache + plumbs bundle"
```

---

## Task 14: All `build_dashboard` production call sites thread `ohlcv_cache`

**Files:**
- Modify: `swing/web/routes/dashboard.py` (1 call site)
- Modify: `swing/web/routes/trades.py` (2 `build_dashboard` call sites around lines 242 + 338)
- Modify: `swing/web/routes/pipeline.py` (1 `build_dashboard` call site around line 309, inside `prices_refresh`)

Spec §2.1. All four production call sites of `build_dashboard` must pass `ohlcv_cache` (R2 Major 1 resolution — Codex flagged that the earlier plan missed trades ×2 and pipeline's `prices_refresh` handler).

- [ ] **Step 1: Grep call sites to confirm**

Run: `grep -n "build_dashboard(" swing/web/routes/ -r`

Expected output lists 4 call sites: `dashboard.py:17`, `trades.py:242`, `trades.py:338`, `pipeline.py:309`.

- [ ] **Step 2: Update the `/` route (dashboard.py)**

```python
@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    ohlcv_cache = request.app.state.ohlcv_cache                   # NEW
    executor = request.app.state.price_fetch_executor
    vm = build_dashboard(
        cfg=cfg, cache=cache, executor=executor,
        ohlcv_cache=ohlcv_cache,                                  # NEW kwarg
    )
    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html.j2", {"vm": vm},
    )
```

- [ ] **Step 3: Update the two `build_dashboard` call sites in trades.py**

At each of the two lines (around 242 and 338), change:

```python
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
```

To:

```python
    dashboard_vm = build_dashboard(
        cfg=cfg, cache=cache, executor=executor,
        ohlcv_cache=request.app.state.ohlcv_cache,                # NEW
    )
```

- [ ] **Step 4: Update the `prices_refresh` call site in pipeline.py**

At line ~309 in `swing/web/routes/pipeline.py`, change:

```python
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
```

To:

```python
    vm = build_dashboard(
        cfg=cfg, cache=cache, executor=executor,
        ohlcv_cache=request.app.state.ohlcv_cache,                # NEW
    )
```

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 476 passed. Dashboard + trades + prices-refresh integration tests now exercise the full OHLCV plumbing on the real app.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/dashboard.py swing/web/routes/trades.py swing/web/routes/pipeline.py
git commit -m "feat(web): all build_dashboard call sites thread ohlcv_cache"
```

---

## Task 15: Trades route POST handlers pass `ohlcv_cache`

**Files:**
- Modify: `swing/web/routes/trades.py`

Spec §2.1. Four call sites of `build_open_positions_row` in `swing/web/routes/trades.py` (previously grepped at lines 237, 356, 396, 462). Each needs `ohlcv_cache=request.app.state.ohlcv_cache`.

- [ ] **Step 1: Locate the four call sites**

Run: `grep -n "build_open_positions_row(" swing/web/routes/trades.py`

Each site currently looks like:

```python
    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=executor, conn=conn,
    )
```

- [ ] **Step 2: Update each call site**

For each of the 4 sites, add `ohlcv_cache=request.app.state.ohlcv_cache`:

```python
    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache,
        ohlcv_cache=request.app.state.ohlcv_cache,               # NEW
        executor=executor, conn=conn,
    )
```

If the local variable `executor` was derived from `request.app.state.price_fetch_executor`, the `ohlcv_cache` lookup uses the same `request` object — no new state needed.

- [ ] **Step 3: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 476 passed. Trade-action integration tests now exercise the full plumbing.

- [ ] **Step 4: Commit**

```bash
git add swing/web/routes/trades.py
git commit -m "feat(web): /trades/* POST handlers thread ohlcv_cache into build_open_positions_row"
```

---

## Task 16: Base-layout compat test suite

**Files:**
- Create: `tests/web/test_base_layout_compat.py`

Spec §5.5. Regression-guard that the new `vm.ohlcv_source_degraded` field on every base-layout VM doesn't break unrelated routes. Also pins the pipeline-route `is_degraded` pass-through.

- [ ] **Step 1: Write the tests**

Create `tests/web/test_base_layout_compat.py`:

```python
"""Phase 3d §5.5: base-layout VM compatibility.

Every VM that extends base.html.j2 now carries ohlcv_source_degraded: bool.
Unrelated routes must still render — if any VM defaults to True or omits the
field, Jinja would 500 with UndefinedError. These tests close that class of
regression.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_journal_renders_with_ohlcv_source_degraded_default_false(test_cfg, seeded_db):
    """GET /journal must render 200 HTML. JournalVM's ohlcv_source_degraded
    defaults to False; the banner must NOT appear."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=month")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_watchlist_renders_with_ohlcv_source_degraded_default_false(
    test_cfg, seeded_db, monkeypatch,
):
    """GET /watchlist must render 200 HTML. WatchlistVM's ohlcv_source_degraded
    defaults to False; the banner must NOT appear."""
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_page_error_renders_with_ohlcv_source_degraded_default_false(test_cfg, seeded_db):
    """Force a validation error on /journal to trigger the full-page 400 path.
    PageErrorVM.ohlcv_source_degraded defaults to False; banner absent."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_pipeline_banner_shown_when_ohlcv_cache_is_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4 R4 pass-through: when OhlcvCache.is_degraded() is True, the
    /pipeline page renders the SMA-advisories-unavailable banner."""
    from swing.web.ohlcv_cache import OhlcvCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: True)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert "SMA advisories unavailable" in r.text


def test_pipeline_banner_absent_when_ohlcv_cache_is_not_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4 R4 pass-through: when OhlcvCache.is_degraded() is False, the
    /pipeline page renders WITHOUT the banner."""
    from swing.web.ohlcv_cache import OhlcvCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert "SMA advisories unavailable" not in r.text
```

- [ ] **Step 2: Run the new tests**

Run: `python -m pytest tests/web/test_base_layout_compat.py -v`
Expected: 5 PASS.

- [ ] **Step 3: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 481 passed (476 + 5 new).

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_base_layout_compat.py
git commit -m "test(web): base-layout compat + pipeline banner pass-through (Phase 3d §5.5)"
```

---

## Task 17: Dashboard integration — SMA advisories render end-to-end

**Files:**
- Modify: `tests/web/test_dashboard_integration.py`

Spec §5.4. Integration tests that exercise the full `GET /` path with a monkeypatched `OhlcvCache.get_many_bundles`.

- [ ] **Step 1: Write tests**

Append to `tests/web/test_dashboard_integration.py`. Each test uses the same direct-seed helper pattern as Task 12's `_seed_open_trade_direct`. Define a local copy at the top of the appended block (or import from `tests.web.test_view_models.test_dashboard` if already available there):

```python
def _seed_open_trade_direct(cfg, *, ticker: str, entry_price: float, shares: int) -> int:
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = Trade(
                id=None, ticker=ticker, entry_date="2026-04-15",
                entry_price=entry_price, initial_shares=shares,
                initial_stop=entry_price * 0.95, current_stop=entry_price * 0.95,
                status="open", watchlist_entry_target=None,
                watchlist_initial_stop=None, notes=None,
            )
            return insert_trade_with_event(conn, trade, event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()


def test_get_dashboard_renders_sma_advisories_from_full_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: when OhlcvCache returns a full bundle, SMA50 EXIT rule
    fires and the advisory message appears in the rendered page."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=196.0, sma50=195.0,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # SMA50 exit advisory appears (previous_close 190 < sma50 195).
    assert "50MA" in r.text
    assert "$190.00" in r.text


def test_get_dashboard_absent_advisories_on_all_none_bundle(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: all-None bundle (deadline miss) → SMA advisories absent,
    but page still renders."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle.empty(fetched_at=0.0) for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # No SMA50 exit advisory.
    assert "50MA" not in r.text


def test_get_dashboard_partial_bundle_sma10_only_renders_only_10ma_rules(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §5.4: a partial bundle (SMA10 only, rest None) → only 10MA rules
    fire. SMA20 and SMA50 rules silently no-op."""
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = test_cfg
    _seed_open_trade_direct(cfg, ticker="AAPL", entry_price=180.0, shares=10)

    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: OhlcvBundle(sma10=198.0, sma20=None, sma50=None,
                            previous_close=190.0, fetched_at=0.0)
            for t in tickers
        },
    )
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=200.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    # 10MA exit rule fires (previous_close 190 < sma10 198).
    assert "10MA" in r.text
    # SMA50 exit rule silently no-ops.
    assert "50MA" not in r.text
```

(The `_seed_open_trade_direct` helper defined above at the top of the appended block is module-local. If another test-file already provides an equivalent helper you prefer to reuse, import it; otherwise keep the local copy.)

- [ ] **Step 2: Run the new tests**

Run: `python -m pytest tests/web/test_dashboard_integration.py -k "renders_sma_advisories or absent_advisories or partial_bundle" -v`
Expected: 3 PASS.

- [ ] **Step 3: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 484 passed (481 + 3 new).

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_dashboard_integration.py
git commit -m "test(web): dashboard integration exercises SMA advisory render (Phase 3d §5.4)"
```

---

## Task 18: Full-suite acceptance sweep

**Files:** none (verification only).

Final regression gate before the adversarial Codex pass.

- [ ] **Step 1: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: **484 passed** (444 baseline + ~40 Phase 3d new; spec projected ~465, so we land ~20 above the projection — fine). No regressions in any Phase 2, 3a, 3b, or 3c test.

If any pre-existing test now fails, investigate. The only legitimate regression candidates are:
- Tests that constructed `AdvisoryContext(...)` positionally and didn't receive the new `sma50` / `previous_close` kwargs — fix by adding the missing fields.
- Tests that called `build_dashboard(...)` or `build_open_positions_row(...)` without `ohlcv_cache` — fix per Task 12/13 instructions.

- [ ] **Step 2: Phase 2 isolation spot-check**

Run: `python -m pytest tests/data/ tests/trades/ tests/pipeline/ -q`
Expected: all green. Task 3's Phase 2 carve-out (the atomic `suggest_exit_close_below_ma` semantic swap) is the ONLY approved Phase 2 change. Any other Phase 2 test regression is a bug.

- [ ] **Step 3: Phase 3a/3b/3c regression sweep**

Run: `python -m pytest tests/web/test_origin_guard.py tests/web/test_error_handling.py tests/web/test_routes/ tests/web/test_dashboard_integration.py tests/web/test_trades_integration.py tests/web/test_body_size_middleware.py -v`
Expected: all green. Phase 3b's HX-Target contract, Phase 3c's force-clear chain, middleware ordering (MaxBodySize → OriginGuard → RequestId), and autoescape defense are untouched.

- [ ] **Step 4: Optional lint**

Run: `python -m ruff check swing/pipeline/ohlcv.py swing/web/ohlcv_cache.py swing/trades/advisory.py swing/web/view_models/`
Expected: clean on newly-added/modified files.

- [ ] **Step 5: Final commit (only if lint fixes were needed)**

If lint produced fixes:

```bash
git add swing/
git commit -m "chore(web): lint sweep after Phase 3d"
```

Otherwise skip this step.

---

## Plan summary

- **18 tasks**, each ending in a clean commit.
- **~40 new tests** distributed across pipeline helpers, OHLCV cache, advisory rule tests, base-layout compat, and dashboard integration. (Spec projected ~20-24; actual distribution weighted higher to match the 5 compat tests in §5.5 and the 3 integration tests in §5.4.)
- **Target test count:** 444 (end of 3c) → **~484 fast tests** (3d). Spec baseline: 413+ at Phase 3c; ~465 at Phase 3d. We land ~20 above the projection due to more granular coverage of the breaker, in-progress bar strip, and the pipeline pass-through.
- **Phase 2 change scope:** exactly one function module — `swing/trades/advisory.py` gains `sma50` + `previous_close` fields on `AdvisoryContext`, swaps `suggest_exit_close_below_ma`'s input to `ctx.previous_close`, and adds a 50MA exit call in `compute_all_suggestions` (spec §3.3 / decision #7).
- **Spec coverage:**
  - §3.1 pure helpers + fetch_daily_bars with session-anchored strip → Tasks 1-2
  - §3.2 OhlcvCache + semaphore + sliding-window breaker + deadline-as-failure → Task 6
  - §3.3 AdvisoryContext + exit-rule swap + 50MA call → Task 3
  - §3.4 template/VM compat + pipeline pass-through → Tasks 8-11
  - §3.5 app.state.ohlcv_cache → Task 7
  - §3.6 CLI parity → Task 4
  - §3.7 config fields → Task 5
  - §4.1-4.5 data-flow details → Tasks 6, 10-13
  - §5.1 ohlcv test suite → Tasks 1-2
  - §5.2 ohlcv_cache test suite → Task 6
  - §5.3 advisory test updates → Task 3
  - §5.4 dashboard integration tests → Task 17
  - §5.5 base-layout compat tests → Task 16
  - §6 degraded banner → Tasks 8-9
- **Architectural invariants preserved:**
  - Phase 2 isolation (1 carve-out only).
  - Starlette LIFO middleware order (no new middleware).
  - Jinja autoescape (via `_build_templates`).
  - No DB schema changes (OhlcvCache is in-memory).
  - No HTMX swap pattern changes.
