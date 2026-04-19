# Phase 3d — SMA-aware advisories (design)

**Baseline:** Phase 3c shipped at commit `3e934ef` on `main`; 444 fast tests green. Phase 3c explicitly deferred SMA advisories to this phase (see 3c spec §1.3 provenance note).

**Goal:** Compute daily SMA10, SMA20, SMA50 on demand for open-trade tickers and plumb them — plus each ticker's previous daily close — into the existing `AdvisoryContext`, so the already-implemented `suggest_trail_ma` and `suggest_exit_close_below_ma` rules can actually fire. Add the Minervini 50-SMA exit rule. Do it without blocking page load on slow or failed OHLCV fetches.

**Scope variant:** plumbing + add SMA50 (Minervini exit). The rule logic already exists — this phase wires data to it.

---

## 1. Background & scope

### 1.1 What already exists

The advisory engine is implemented and tested in [swing/trades/advisory.py](../../../swing/trades/advisory.py):

- `AdvisoryContext` dataclass with `sma10: float | None`, `sma20: float | None`.
- `suggest_trail_ma(trade, ctx, *, ma_value, ma_label, buffer_pct)`: pure function that suggests raising the trailing stop to `ma_value * (1 - buffer_pct/100)` when `ctx.current_price >= ma_value`.
- `suggest_exit_close_below_ma(trade, ctx, *, ma_value, ma_label)`: pure function that currently flags EXIT when `ctx.current_price < ma_value`.
- `compute_all_suggestions` calls both rules for 10MA and 20MA.

The dashboard view-model ([swing/web/view_models/dashboard.py:159-167](../../../swing/web/view_models/dashboard.py)) and the single-row wrapper ([swing/web/view_models/open_positions_row.py:100-107](../../../swing/web/view_models/open_positions_row.py)) already construct `AdvisoryContext` and call `compute_all_suggestions` — but pass `sma10=None, sma20=None`, so the SMA-dependent rules silently no-op. An inline comment explicitly acknowledges this: "SMA-dependent rules return None until Phase 3c" (stale annotation; actually Phase 3d).

### 1.2 What Phase 3d ships

1. Compute daily SMA10 / SMA20 / SMA50 **on demand** per open-trade ticker, via a new `OhlcvCache` with a longer TTL than the live-quote `PriceCache`.
2. Plumb `sma10`, `sma20`, `sma50`, and `previous_close` into `AdvisoryContext` at both call sites.
3. Change `suggest_exit_close_below_ma` to use `ctx.previous_close` (Minervini canonical form: fires on yesterday's *daily close* below the MA, not on a live-tick dip).
4. Add a 50-SMA exit call in `compute_all_suggestions`.
5. Graceful degradation: missing OHLCV → SMA rules silently no-op per ticker; other advisories unaffected.
6. Update CLI `swing trade advisory` for parity with the new context fields.

### 1.3 Provenance — why this is a separate phase

Phase 3a explicitly deferred SMA-aware advisories because they required a new data-fetch subsystem (OHLCV bars, not live quotes) with different TTL semantics than the live-quote `PriceCache`. Phase 3c reconfirmed the deferral (3c spec §1.3 lists SMA advisories as the single item carried over into 3d). This spec picks up that thread.

---

## 2. Architecture

### 2.1 File layout

```
swing/
├── trades/
│   └── advisory.py                 # Phase 2 carve-out: +sma50, +previous_close fields;
│                                   #   swap ctx input for suggest_exit_close_below_ma;
│                                   #   add 50MA exit call in compute_all_suggestions.
├── pipeline/
│   └── ohlcv.py                    # NEW: pure helpers — fetch_daily_bars, compute_smas,
│                                   #   previous_close. IO isolated to fetch_daily_bars.
├── web/
│   ├── ohlcv_cache.py              # NEW: OhlcvCache; mirrors PriceCache's shape +
│   │                               #   sliding-window circuit-breaker; TTL ~1h;
│   │                               #   shares price_fetch_executor.
│   ├── app.py                      # MODIFIED: app.state.ohlcv_cache built at startup;
│   │                               #   existing price_fetch_executor reused.
│   ├── routes/
│   │   ├── dashboard.py            # MODIFIED: thread ohlcv_cache through to build_dashboard.
│   │   └── trades.py               # MODIFIED: every call site of build_open_positions_row
│   │                               #   now passes ohlcv_cache (~6 POST-success handlers).
│   └── view_models/
│       ├── dashboard.py            # MODIFIED: fetch OHLCV bundles via ohlcv_cache;
│       │                           #   plumb sma10/20/50 + previous_close into
│       │                           #   AdvisoryContext.
│       └── open_positions_row.py   # MODIFIED: same plumbing for the single-row wrapper;
│                                   #   accepts ohlcv_cache as a new positional/kwarg.
├── cli.py                          # MODIFIED: `swing trade advisory` gains --sma50 and
│                                   #   --previous-close flags (consequential parity).
└── config.py                       # MODIFIED: Web.ohlcv_cache_ttl_seconds = 3600 default;
                                    #   Web.max_concurrent_ohlcv_fetches = 4 (see §3.2).
```

Files touched (full list):

- **Phase 2 carve-out (1):** `swing/trades/advisory.py`.
- **New modules (2):** `swing/pipeline/ohlcv.py`, `swing/web/ohlcv_cache.py`.
- **Phase 3 route updates (2):** `swing/web/routes/dashboard.py`, `swing/web/routes/trades.py`.
- **Phase 3 view-model updates (5):** `swing/web/view_models/dashboard.py` (OHLCV plumb + DashboardVM.ohlcv_source_degraded), `open_positions_row.py` (accepts ohlcv_cache), `pipeline.py` (PipelineVM.ohlcv_source_degraded), `journal.py` (JournalVM.ohlcv_source_degraded=False default), `watchlist.py` (WatchlistVM.ohlcv_source_degraded=False default), plus `error.py` (PageErrorVM.ohlcv_source_degraded=False default).
- **Phase 3 template update (1):** `swing/web/templates/base.html.j2` gains the conditional OHLCV-degraded banner.
- **Wiring (3):** `swing/web/app.py` (app.state.ohlcv_cache), `swing/cli.py` (--sma50, --previous-close), `swing/config.py` (two new Web fields).

Total: **15 files** (1 carve-out + 2 new modules + 12 modifications). The earlier "ten files" count under-reported by omitting the shared-base-template VM surface — R3 review correctly flagged this. Existing dashboard and trade-action integration tests will need fixtures updated to pass a test double for `ohlcv_cache`.

### 2.2 Design invariants

- **Purity at the boundary.** `swing/pipeline/ohlcv.py::compute_smas` and `::previous_close` are pure: DataFrame in, primitives out. Tests inject canned DataFrames; no yfinance round-trip in the fast suite.
- **Cache shape mirrors `PriceCache`.** `OhlcvCache.get_many_bundles(tickers, deadline=..., executor=...)` has the same method shape as `PriceCache.get_many(tickers, deadline=..., executor=...)`. Callers handle missing results identically.
- **Bounded-deadline rendering.** The dashboard's existing deadline pattern (default `cfg.web.price_fetch_deadline_seconds = 6`) applies to the OHLCV fetch too. The two caches are called **sequentially** on the request thread — `cache.get_many(...)` first, then `ohlcv_cache.get_many_bundles(...)` — each bounded by its own deadline. Each method internally parallelizes per-ticker fetches across `price_fetch_executor`. Worst-case total latency is `2 × deadline_seconds` on a cold cache; steady-state is near-instant (both caches warm). Sequential top-level calls deliberately avoid a nested-futures topology that could deadlock on a small executor pool (see §3.2).
- **Circuit breaker isolation.** `OhlcvCache` has its own circuit breaker; a failing yfinance OHLCV endpoint does not trip the live-quote breaker or vice versa.
- **Graceful degradation throughout.** Missing `OhlcvBundle`, or a bundle with any None field, must not raise. SMA rules silently return None.

### 2.3 Data flow (dashboard render)

```
GET /  ──►  build_dashboard(cfg, price_cache, ohlcv_cache, executor)
              │
              ├─► price_cache.get_many([tickers], deadline=...)         # Phase 3a — unchanged
              ├─► ohlcv_cache.get_many_bundles([tickers], deadline=...) # NEW
              │     │
              │     └─► per ticker (cache-miss): executor.submit →
              │           fetch_daily_bars(ticker, n_bars=60) →   # drops in-progress bar
              │           compute_smas(bars, [10, 20, 50]) →      # over completed bars only
              │           previous_close(bars) →                   # most recent COMPLETED close
              │           OhlcvBundle(sma10, sma20, sma50, previous_close, fetched_at)
              │
              └─► per open trade:
                    snap = price_cache result
                    bundle = ohlcv_cache result  (may be all-None on deadline / failure)
                    ctx = AdvisoryContext(
                        as_of_date=..., current_price=snap.price,
                        sma10=bundle.sma10, sma20=bundle.sma20, sma50=bundle.sma50,
                        previous_close=bundle.previous_close,
                        weather_status=..., config=cfg.stop_advisory,
                    )
                    compute_all_suggestions(trade, ctx)
```

If `ohlcv_cache.get_many_bundles` deadline fires before a ticker's OHLCV arrives, that ticker receives a `None`-filled bundle; SMA rules for that row no-op; the existing breakeven / weather / time_stop advisories still render.

---

## 3. Components

### 3.1 `swing/pipeline/ohlcv.py` (new)

```python
from collections.abc import Sequence
import pandas as pd
import yfinance as yf


def fetch_daily_bars(ticker: str, *, n_bars: int = 60, as_of_date: date | None = None) -> pd.DataFrame | None:
    """Fetch completed daily bars for `ticker`.

    Returns at most `n_bars` rows of FULLY-COMPLETED daily bars, ending with
    the most recent completed session. Returns None on empty result or
    exception.

    Critical session-boundary semantics: yfinance's `history(interval='1d')`
    includes the IN-PROGRESS bar for the current trading day during US market
    hours, and continues to return that bar under "today"'s exchange date
    until the next session rolls over. We must exclude that in-progress bar —
    otherwise `previous_close` and the last rolling-mean row would reflect
    the partial close of the current session, turning a "close below MA" exit
    rule back into a live-intraday rule (what we explicitly chose NOT to do
    per spec §1.2).

    Timezone correctness: "today" MUST be resolved against the exchange
    session, NOT the app-local timezone. On a Hawaii-local dev box, local
    midnight lags ET by 5 hours; naive `date.today()` would treat an
    ET-complete bar as in-progress for hours. Use the existing
    `swing.evaluation.dates.action_session_for_run(datetime.now())` helper —
    it's already the project's single source of truth for session-date
    resolution (used by the weather classifier and Phase 3c's PageErrorVM).

    Strip rule: drop the last row iff `last_bar.date() >= action_session` —
    i.e., the last bar is either today's in-progress session OR (defensively)
    dated in the future relative to the current session.

    Implementation:
      - Request `period='6mo'` (≈126 trading bars — ample for SMA50 plus
        holiday/DST buffer, unambiguously ≥ 60 trading bars).
      - Resolve `session = as_of_date or action_session_for_run(datetime.now())`.
      - Drop the last row if `df.index[-1].date() >= session`.
      - Return `df.tail(n_bars)`.

    Uses `threads=False` per the yfinance rate-limit gotcha documented in
    CLAUDE.md.
    """
```

The concrete implementation:

```python
from datetime import date, datetime
import pandas as pd
import yfinance as yf

from swing.evaluation.dates import action_session_for_run


def fetch_daily_bars(
    ticker: str, *, n_bars: int = 60, as_of_date: date | None = None,
) -> pd.DataFrame | None:
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
    # Exchange-session-anchored "today" (NOT app-local date — HST lags ET by 5h).
    session = as_of_date or action_session_for_run(datetime.now())
    # yfinance index is timezone-aware Timestamps; compare by .date().
    last_idx = df.index[-1]
    last_date = last_idx.date() if hasattr(last_idx, "date") else last_idx
    if last_date >= session:
        df = df.iloc[:-1]                 # drop in-progress bar
    if df.empty:
        return None
    return df.tail(n_bars)


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
    """Last daily bar's Close, or None."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return None
    closes = bars["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])
```

All three functions are unit-testable with canned DataFrames. Only `fetch_daily_bars` does IO.

`as_of_date` is injectable for deterministic testing (same pattern as `is_stale_eligible`'s `now=` seam from Phase 3c). Production callers pass nothing; tests pin a fixed date so the in-progress-bar strip is deterministic.

### 3.2 `swing/web/ohlcv_cache.py` (new)

```python
import time
from collections.abc import Sequence
from concurrent.futures import Executor
from dataclasses import dataclass

from swing.config import Config
from swing.pipeline.ohlcv import fetch_daily_bars, compute_smas, previous_close


@dataclass(frozen=True)
class OhlcvBundle:
    sma10: float | None
    sma20: float | None
    sma50: float | None
    previous_close: float | None
    fetched_at: float

    @classmethod
    def empty(cls, fetched_at: float) -> "OhlcvBundle":
        return cls(None, None, None, None, fetched_at)


class OhlcvCache:
    """TTL-cached daily-bar bundles keyed by uppercase ticker. Shares the
    existing price_fetch_executor (bounded by its own semaphore; see §3.2
    starvation guard). Circuit breaker mirrors PriceCache's sliding-window
    mechanism (see [swing/web/price_cache.py:207-219](../../../swing/web/price_cache.py#L207-L219))."""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._ttl = cfg.web.ohlcv_cache_ttl_seconds
        self._store: dict[str, tuple[OhlcvBundle, float]] = {}
        self._sema = threading.Semaphore(cfg.web.max_concurrent_ohlcv_fetches)
        self._failure_window: collections.deque[bool] = collections.deque(maxlen=...)  # True=failure
        self._degraded_until: float | None = None
        self._lock = threading.Lock()
        # ... implementation details ...

    def get_many_bundles(
        self, tickers: Sequence[str], *,
        deadline_seconds: float, executor: Executor,
    ) -> dict[str, OhlcvBundle]:
        """Return {ticker: OhlcvBundle} for every ticker. Cache-hits served
        immediately; cache-misses fetched in parallel via `executor`; any
        ticker not completed before `deadline_seconds` gets OhlcvBundle.empty()
        and its miss is logged, not raised."""

    def is_degraded(self) -> bool: ...
    def reset_circuit_breaker(self) -> None: ...
```

Storage is in-memory per app instance. TTL from `cfg.web.ohlcv_cache_ttl_seconds` (default 3600s). No persistence across restarts (intentional — yfinance fetch is cheap enough, and memory cache avoids stale-on-disk issues).

**Executor-starvation guard:** `OhlcvCache` bounds its own concurrent submissions via an internal `threading.Semaphore(cfg.web.max_concurrent_ohlcv_fetches)`. The default is `8` — the full executor size — on the theory that the **sequential top-level call pattern** (§2.2) already separates OHLCV and price fetches in time, so there is no live-quote starvation to guard against: by the time `ohlcv_cache.get_many_bundles(...)` runs, `cache.get_many(...)` has already returned and released every slot it held. The semaphore remains in the design as a configurable defensive cap for operators who want a tighter bound (e.g., running a second unrelated workload on the same executor), but the default `8` eliminates the artificial queue backlog that would otherwise inflate deadline misses.

**Queue-multiplier math.** With 8 slots and 20 open positions on a cold cache, per-ticker fetches queue roughly `ceil(20/8) = 3` deep. A healthy-but-slow yfinance taking 2s/fetch completes the last ticker in ~6s — inside the default 6s deadline. For portfolios beyond ~30 open positions, operators should raise `price_fetch_deadline_seconds` or accept that some row's SMA advisories will land on the next render (once the TTL-populated cache is warm). The design does NOT attempt to distinguish "queue-wait deadline miss" from "execution-time deadline miss" in the breaker window — YAGNI; with the cap raised, the queue-wait pathology flagged in R3 review is not reachable in realistic operation.

**Circuit breaker:** mirrors `PriceCache`'s sliding-window mechanism (see [swing/web/price_cache.py:207-219](../../../swing/web/price_cache.py#L207-L219)) — trips when the failure fraction over the recent-calls window exceeds 50%. Cooldown uses `cfg.web.circuit_breaker_cooldown_seconds` (reuses the existing knob — no separate `ohlcv_circuit_breaker_cooldown_seconds` is YAGNI). `reset_circuit_breaker()` exists so a future `/ohlcv/refresh` can force-reset; Phase 3d's `/prices/refresh` is NOT extended to touch the OHLCV breaker (see §4.5).

### 3.3 `swing/trades/advisory.py` (Phase 2 carve-out)

```python
@dataclass(frozen=True)
class AdvisoryContext:
    as_of_date: str
    current_price: float
    sma10: float | None
    sma20: float | None
    sma50: float | None               # NEW
    previous_close: float | None      # NEW — drives exit_close_below_ma
    weather_status: str
    config: StopAdvisoryConfig


def suggest_exit_close_below_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str,
) -> AdvisorySuggestion | None:
    # Minervini: "Sell on a close below the N-day MA." Fires when YESTERDAY'S
    # DAILY CLOSE is below the MA — not on a live intraday tick.
    if ma_value is None or ctx.previous_close is None:
        return None
    if ctx.previous_close >= ma_value:
        return None
    return AdvisorySuggestion(
        rule=f"exit_below_{ma_label.lower()}",
        message=f"EXIT — yesterday's close ${ctx.previous_close:.2f} "
                f"is below {ma_label} (${ma_value:.2f})",
    )


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

`suggest_trail_ma` is unchanged — it still uses `ctx.current_price`, which is the right input for "where is the price relative to MA" when suggesting a stop-raise. There is no `trail_50ma` because a 50-SMA trailing stop is too loose for swing trades (50-SMA can be 10%+ below a price running to highs; the 20-SMA is the typical outer-bound trailer).

### 3.4 `swing/web/view_models/dashboard.py` + `open_positions_row.py`

Both change in the same way: after `price_cache.get_many`, add a sequential `ohlcv_cache.get_many_bundles` call (each internally parallelizes per-ticker fetches across the executor; the two top-level calls themselves run back-to-back on the request thread — see §2.2 rationale). Plumb the per-ticker bundle into the existing `AdvisoryContext` construction. Open-positions-row template is unchanged; the new degraded-OHLCV banner lives in the shared base layout — see the "Template / view-model surface changes" subsection below.

Concretely in `dashboard.py` — sequential call on the request thread, each cache's `get_many(...)` internally parallelizes across `price_fetch_executor`:

```python
    tickers = [t.ticker for t in open_trades]
    deadline = cfg.web.price_fetch_deadline_seconds

    # Sequential top-level calls. Each method internally parallelizes per-ticker
    # fetches across `price_fetch_executor`. Sequential (not nested futures) so
    # a small executor pool cannot deadlock parents-waiting-on-children.
    prices = cache.get_many(
        tickers, deadline_seconds=deadline, executor=executor,
    )
    bundles = app.state.ohlcv_cache.get_many_bundles(
        tickers, deadline_seconds=deadline, executor=executor,
    )

    for t in open_trades:
        snap = prices.get(t.ticker)
        bundle = bundles.get(t.ticker)           # may be None or all-None
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=bundle.sma10 if bundle else None,
            sma20=bundle.sma20 if bundle else None,
            sma50=bundle.sma50 if bundle else None,
            previous_close=bundle.previous_close if bundle else None,
            weather_status=weather_status,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv) if snap else []
```

Worst-case cold-cache latency is `2 × deadline_seconds` (default 12s). On any warm cache (≥1 prior render within the TTL) the OHLCV call is a dict lookup and effectively free. The 1h OHLCV TTL means steady-state dashboard loads are dominated by the price-cache latency alone.

`build_open_positions_row` receives `ohlcv_cache` the same way it receives `cache` today, mirrored call.

**Template / view-model surface changes in §3.4 scope:**

- `base.html.j2` gains a conditional render for the OHLCV-degraded banner (§6) — driven by a new `vm.ohlcv_source_degraded: bool` field. Because the base template is shared across **every** page that extends it, EVERY base-layout VM must gain the field (defaulted to `False`) or Jinja will 500 the page with `UndefinedError` on an unrelated route. Per Phase 3c's `PageErrorVM` precedent, we enumerate the full base-layout VM set:
  - `swing/web/view_models/dashboard.py::DashboardVM` — populates `ohlcv_source_degraded` from `ohlcv_cache.is_degraded()`.
  - `swing/web/view_models/pipeline.py::PipelineVM` — populates `ohlcv_source_degraded` from `ohlcv_cache.is_degraded()`.
  - `swing/web/view_models/journal.py::JournalVM` — defaults to `False` (journal route doesn't consult OHLCV).
  - `swing/web/view_models/watchlist.py::WatchlistVM` — defaults to `False`.
  - `swing/web/view_models/error.py::PageErrorVM` — defaults to `False` (error pages never show OHLCV banner).
  Adding a `bool = False` field to each frozen dataclass is mechanically trivial; `build_*` functions stay simple (default is correct for non-dashboard/non-pipeline pages).
- Open-positions row template unchanged — extra advisories just render into the existing `advisories` list.
- `_build_templates` autoescape guarantee (Phase 3c) still applies to the new banner markup.

### 3.5 `swing/web/app.py` startup

```python
    # ... existing app.state assignments ...
    app.state.ohlcv_cache = OhlcvCache(cfg)
```

One new line. The existing `price_fetch_executor` is reused; no new executor or lifespan surface.

### 3.6 `swing/cli.py::trade_advisory_cmd` (consequential)

```python
@click.option("--sma10", type=float, default=None)
@click.option("--sma20", type=float, default=None)
@click.option("--sma50", type=float, default=None)           # NEW
@click.option("--previous-close", type=float, default=None)  # NEW
# ... rest unchanged ...
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, sma50,
                        previous_close, weather, as_of_date):
    ctx_a = AdvisoryContext(
        # ... existing ...
        sma50=sma50,
        previous_close=previous_close,
        # ... existing ...
    )
```

Pure additive CLI change. Operators invoking the CLI without the new flags see SMA50 and exit_close_below_ma silently skip — same semantic as before.

### 3.7 `swing/config.py::Web`

```python
@dataclass(frozen=True)
class Web:
    # ... existing fields ...
    ohlcv_cache_ttl_seconds: int = 3600          # NEW: 1h default
    max_concurrent_ohlcv_fetches: int = 8        # NEW: defensive cap = full executor (§3.2)
```

Two new fields. No changes to `StopAdvisoryConfig`.

---

## 4. Data flow details

### 4.1 Cache keying

`OhlcvCache` is keyed by the uppercased ticker. Normalization happens at the cache boundary — `get_many_bundles(["aapl","AAPL"])` coalesces to a single `"AAPL"` lookup. Callers in `dashboard.py` and `open_positions_row.py` pass `trade.ticker` through directly; the DB schema already stores tickers uppercase (see [swing/data/models.py](../../../swing/data/models.py)), so normalization is defense-in-depth.

We don't key by `n_bars` because `fetch_daily_bars` always requests a 6-month period — enough for any SMA ≤ 50 with buffer for holidays. If a future advisory needs SMA200, bump the fetch window and the `n_bars` tail; we'd introduce a `(ticker, n_bars)` key only if multiple callers with different window needs emerge. YAGNI for now.

### 4.2 Cache TTL

Default 1 hour (`cfg.web.ohlcv_cache_ttl_seconds = 3600`). Rationale: daily bars don't change during a session. The close of yesterday's bar is fixed; the "bar in progress" doesn't enter SMA until tomorrow's fetch. A 1h TTL means at most one yfinance fetch per ticker per hour per app instance. Short enough that a long-running web session picks up overnight bar closes within an hour of session resume; long enough to avoid thrashing.

### 4.3 Deadline semantics

`OhlcvCache.get_many_bundles(tickers, deadline_seconds=..., executor=...)` returns `{ticker: OhlcvBundle}` for every requested ticker. A ticker that didn't complete before the deadline receives `OhlcvBundle.empty(fetched_at=now)` (all None fields). This bundle is **not cached** — it represents a deadline miss, not a confirmed-empty result. The next request re-attempts the fetch.

**Deadline misses count toward the breaker.** A yfinance outage that manifests as *slow* rather than *exception* would never record a failure in a raw try/except model, so the breaker would never trip and the degraded banner (§6) would never appear — operators would see advisories silently disappear without explanation. To close this gap, `OhlcvCache.get_many_bundles` records one sliding-window outcome per requested ticker: `success` if a bundle was produced (cache hit or fresh fetch), `failure` if the ticker hit the deadline OR the underlying `fetch_daily_bars` raised. The breaker's >50% trip condition therefore fires on slow-fetch regimes as well as on error regimes.

### 4.4 Circuit breaker

Mirrors `PriceCache`'s sliding-window mechanism (see [swing/web/price_cache.py:207-219](../../../swing/web/price_cache.py#L207-L219)): every fetch records success/failure into a bounded sliding window via `_record_outcome(...)`; `_maybe_trip_breaker(...)` enters degraded mode once the failure fraction in the window exceeds 50%. Cooldown uses `cfg.web.circuit_breaker_cooldown_seconds` (shared knob). `reset_circuit_breaker()` clears the window and the degraded flag.

The OHLCV breaker is INDEPENDENT of the price breaker — a yfinance OHLCV outage does not stop live quotes from rendering, and vice versa. `is_degraded()` reports the breaker state; Phase 3d adds a dedicated page-level banner when it returns True (see §6, decision 8).

### 4.5 Interaction with `POST /prices/refresh`

The existing `POST /prices/refresh` route resets the live-quote circuit breaker and triggers a re-fetch of all tickers. Phase 3d does NOT extend this route to also reset OHLCV — out of scope. The OHLCV cache will heal on its own after the cooldown, or on the next TTL refresh. If the operator wants to force an OHLCV refresh, a restart works; a dedicated `POST /ohlcv/refresh` can come later.

---

## 5. Testing

### 5.1 `tests/pipeline/test_ohlcv.py` (new, ~8 tests)

- `compute_smas` with exactly 50 bars returns SMA50 value; fewer returns None for that period.
- `compute_smas` with 10 bars returns SMA10 float, SMA20/50 None.
- `compute_smas` with empty DataFrame returns all None.
- `compute_smas` with all-NaN Close column returns all None.
- `previous_close` returns last Close; empty frame returns None.
- `fetch_daily_bars` with a monkeypatched `yf.Ticker` returning synthetic bars whose LAST index date == `as_of_date` (injected) — verifies the in-progress bar is dropped before `.tail()`. Reverse case: when the last bar's date is strictly before `as_of_date`, it is retained.
- `fetch_daily_bars` exception-path returns None.
- `fetch_daily_bars` truncation: synthetic fetch of 126 bars + `n_bars=60` → returned DataFrame has exactly 60 rows AFTER the in-progress-bar strip.

### 5.2 `tests/web/test_ohlcv_cache.py` (new, ~6 tests)

Monkeypatch `swing.pipeline.ohlcv.fetch_daily_bars` to return synthetic DataFrames. Cover:

- Cache hit returns cached bundle without refetch.
- Cache miss triggers fetch and stores bundle.
- TTL expiry triggers refetch.
- Ticker deadline miss returns `OhlcvBundle.empty()` and is NOT cached.
- Circuit breaker trips once the failure fraction in the sliding window exceeds 50%.
- `is_degraded()` returns True during cooldown, False after.

### 5.3 `tests/trades/test_advisory.py` (amended, ~4 new tests + regression updates)

- `suggest_exit_close_below_ma` now fires on `previous_close < ma_value`, not `current_price`.
- New: `test_exit_below_50ma_fires_on_previous_close_below`.
- New: `test_exit_below_50ma_noops_when_previous_close_is_none`.
- New: `test_exit_below_50ma_noops_when_sma50_is_none`.
- Existing exit-rule tests receive `previous_close=...` in their `AdvisoryContext` construction.

### 5.4 `tests/web/test_dashboard_integration.py` (amended, ~2-3 tests)

Monkeypatch `OhlcvCache.get_many_bundles` to return canned bundles; assert the SMA advisories render in the open-positions row. Cover: bundle with all three SMAs → EXIT advisories appear; bundle with all None (deadline miss) → advisories absent; partial bundle (SMA10 only) → only 10MA advisories visible.

### 5.5 `tests/web/test_base_layout_compat.py` (new, ~3 tests)

Regression-guard the shared base-template surface (R3 Major 2). For each non-dashboard page that extends `base.html.j2`, render the page against a test `create_app(...)` and assert status 200 + `<html>` body. Pages to cover explicitly:

- `GET /journal` — `JournalVM.ohlcv_source_degraded` must default to `False`; page renders without `UndefinedError`.
- `GET /watchlist` — `WatchlistVM` same.
- Error-page branch: force a `RequestValidationError` that triggers the Phase 3c full-page 400 path — `PageErrorVM.ohlcv_source_degraded` must default to `False`; page renders.

This closes the class of bug where a base-template addition breaks unrelated routes because a VM didn't gain the new field.

### 5.6 Target test count

Phase 3c baseline: 444 fast tests. Phase 3d adds ~20-24 new tests (including the §5.5 base-layout compat suite) → target ~465 fast tests. The existing Phase 3a/3b/3c tests must remain green.

### 5.7 No live yfinance in the fast suite

All OHLCV-dependent tests either (a) use canned pandas DataFrames or (b) monkeypatch `fetch_daily_bars` / `OhlcvCache.get_many_bundles`. The `slow` marker exists for any end-to-end yfinance smoke tests; they are not Phase 3d scope.

---

## 6. Error handling & degraded UI

| Failure | Behavior |
|---|---|
| yfinance network timeout (per ticker) | `fetch_daily_bars` returns None → `OhlcvBundle.empty()` → SMA rules no-op for that ticker; other rows unaffected. |
| yfinance rate-limit / repeated failures | OhlcvCache circuit-breaker trips. `is_degraded() == True`. Page still renders; SMA advisories silently absent until cooldown. |
| Executor deadline expires before fetch returns | Bundle defaults to `OhlcvBundle.empty()`; rule no-op. Same pattern as missing `PriceSnapshot`. Not cached (§4.3). |
| Ticker has fewer than N bars of history (IPO, delisted) | `compute_smas` returns None for periods that can't be computed; partial advisories render (e.g., SMA10 only on a new IPO). |
| Weekend / market-closed | Previous-close stays "Friday's close" throughout; rule fires once and stays consistent. No special handling. |
| Corporate action reshaping bars | `yf.Ticker.history(auto_adjust=False)` returns raw bars; SMA drifts briefly after a split until the cache TTL refreshes (up to 1h of stale SMA across the split boundary). **Accepted limitation.** Operator awareness: the message strings on exit/trail advisories always print the literal MA value in dollars, so a split-driven drop in a stock's price against an unadjusted SMA (which becomes nonsensically high post-split) is visually flagged as a suspiciously large gap — operator should sanity-check before acting on a same-day post-split advisory. If this becomes a noise source in practice, a future phase can add post-split signal suppression. |
| Jinja render error from bad SMA value | Cannot happen: SMA fields are float / None; templates render `{{ …}}` through autoescape. |

**Degraded UI:** when `OhlcvCache.is_degraded()` is True (circuit breaker tripped), the dashboard renders a dedicated banner near the top:

> ⚠ SMA advisories unavailable — daily-bar fetch is in a cool-down period. Trail-MA and close-below-MA rules will not fire until service recovers.

Rationale for surfacing this (reversing the earlier decision to keep it silent): an ABSENT exit advisory must be distinguishable from a signal that was suppressed by an outage. For stop-discipline and exit rules in particular, "no advisory" and "advisory would have fired but we couldn't tell" are operationally different outcomes. A one-line banner below the existing price-source-degraded banner is a cheap disambiguation.

Per-ticker TRANSIENT deadline misses (a single ticker's fetch didn't complete by the deadline but the breaker has not tripped) still silently skip — those are noise, not systemic, and flicker in/out; banner-izing every transient miss would train the operator to ignore the banner. The systemic signal (breaker tripped) is the load-bearing one.

---

## 7. Decisions locked

1. **Scope variant B**: plumbing + add SMA50 (Minervini exit rule).
2. **Exit-rule semantic**: previous daily close. `suggest_exit_close_below_ma` uses `ctx.previous_close`. `suggest_trail_ma` keeps `ctx.current_price`.
3. **Separate `OhlcvCache`**, TTL 3600s, keyed by raw uppercase ticker. Shares `price_fetch_executor`; has its own circuit-breaker.
4. **Inline fetch on page load, bounded by `price_fetch_deadline_seconds`.** No HTMX lazy-load. Missing bundle → silent no-op per row.
5. **SMA set: 10, 20, 50.** Keep existing 10/20; add 50. No SMA21. No SMA200.
6. **Trail-ma stays 10/20 only.** No trail_50ma (too loose for swing).
7. **Exactly one Phase 2 carve-out**: `swing/trades/advisory.py` gains `sma50` + `previous_close` fields, swaps exit-rule input, and adds one 50MA exit call. No other Phase 2 file touched.
8. **Dedicated degraded-OHLCV banner** shown when `OhlcvCache.is_degraded()` (breaker tripped). Per-ticker transient deadline misses remain silent (see §6).
9. **CLI parity**: `swing trade advisory` gains `--sma50` and `--previous-close`.
10. **No network in fast suite**: all OHLCV tests use canned data or monkeypatching.

---

## 8. Out of scope

- Historical backtest or past-signal audit of SMA advisories.
- Trailing-stop automation (advisories remain advisory; operator still clicks Adjust stop).
- Additional indicators: EMAs, VWAP, MACD, RSI, volume-weighted MAs, intraday crossovers.
- Per-ticker SMA period overrides.
- Auto-refresh / polling of SMA advisories during the trading day (1h TTL is the cadence; manual page refresh forces a refetch after expiry).
- Alerting / notification channels (push, email) for SMA triggers.
- Extending `POST /prices/refresh` to also reset the OHLCV cache (`POST /ohlcv/refresh` is deferred).
- Changes to `suggest_breakeven`, `suggest_weather_action`, `suggest_time_stop`.
- UI rearrangement / renaming / reordering of existing advisories.

---

## 9. Architectural invariants preserved

- **Phase 2 isolation** holds modulo the one sanctioned `advisory.py` carve-out.
- **Starlette LIFO middleware order** unchanged — Phase 3d adds no middleware.
- **Jinja autoescape** unchanged — uses the existing `_build_templates` helper.
- **Phase 3a deadline-bounded fetch pattern** reused verbatim.
- **Phase 3b row-swap conventions** unchanged — no new HTMX targets or fragments.
- **Phase 3c force-clear / stale-run machinery** untouched.
- **DB schema** unchanged — OhlcvCache is in-memory, no migration needed.

---

## 10. Expected test count

- Phase 3c baseline: 444 fast tests.
- Phase 3d target: ~460 fast tests (+16 new; +/- a few as tests are added or adjusted).
- Phase 2 regression: all existing `tests/trades/test_advisory.py` tests continue to pass after the minor context-construction updates.
