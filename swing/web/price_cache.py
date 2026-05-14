"""In-memory lazy TTL price cache with market-hours gate and circuit breaker.

See spec §3.2. The cache serves both `get(ticker)` and `get_many(tickers, deadline)`
(added in Task 6). Live fetches go through yfinance's fast_info; failures and
market-closed windows fall back to the latest `candidates.close` for the ticker.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from swing.config import Config
from swing.data.db import connect

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceSnapshot:
    ticker: str
    price: float
    asof: datetime
    is_stale: bool
    source: str   # "live" | "last_close" | "last_close_market_closed"
    # Provenance tag for Schwab API ladder (Phase 11 Sub-bundle C T-C.3).
    # Option A: collapsed T-C.4's dataclass extension into T-C.3 per dispatch
    # brief §0.5 pre-emption #4. Legal values: None (legacy / not set),
    # 'schwab_api' (returned by marketdata ladder Schwab-success path),
    # 'yfinance' (returned by marketdata ladder yfinance fallback path).
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.provider is not None:
            if not isinstance(self.provider, str):
                raise TypeError(
                    "PriceSnapshot.provider must be str or None; got "
                    f"{type(self.provider).__name__}"
                )
            if self.provider not in ("schwab_api", "yfinance"):
                raise ValueError(
                    "PriceSnapshot.provider must be one of None | "
                    f"'schwab_api' | 'yfinance'; got {self.provider!r}"
                )


class PriceCache:
    """Thread-safe lazy TTL price cache.

    Thread safety: a single `self._lock` guards `_cache`, `_failure_window`,
    and `_degraded_until`. Executor worker threads record outcomes and request
    threads read the degraded flag under the same lock.
    """

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[PriceSnapshot, float]] = {}
        self._failure_window: deque[bool] = deque(maxlen=20)
        self._degraded_until: float | None = None
        # Schwab Sub-bundle C T-C.4: optional ladder-aware fetcher. When None
        # (default) the cache uses its existing yfinance-only path. When set
        # via `set_ladder_fetcher`, the live-fetch branch in
        # `_fetch_with_fallback` delegates to the callable which returns
        # `(price: float, provider: str)` for production-env routing through
        # the Schwab → yfinance ladder. Sandbox short-circuit lives INSIDE the
        # ladder; cache stays env-agnostic. Caller is responsible for invoking
        # `fetch_quote_via_ladder` and unpacking the PriceSnapshot tuple.
        self._ladder_fetcher: Callable[[str], tuple[float, str]] | None = None

    def set_ladder_fetcher(
        self,
        fetcher: Callable[[str], tuple[float, str]] | None,
    ) -> None:
        """Install (or clear) a ladder-aware live-fetch callable.

        ``fetcher`` must accept the ticker symbol and return
        ``(price: float, provider: str)`` where ``provider`` is
        ``'schwab_api'`` or ``'yfinance'``. The cache will route ALL
        live-fetch attempts through this callable when set; the legacy
        ``_fetch_live_price`` (raw yfinance) path is reserved for the
        ``fetcher is None`` configuration.

        Passing ``None`` reverts to the legacy yfinance-only path (used
        by existing PriceCache tests that don't exercise the ladder).
        """
        self._ladder_fetcher = fetcher

    # ---------- single-ticker API ----------

    def get(self, ticker: str) -> PriceSnapshot | None:
        """Return a snapshot, or None if no last-close is known either.

        Cache hit returns instantly. Cache miss routes through
        `_fetch_with_fallback`, which may hit the network or fall back to
        the most recent `candidates.close` row.
        """
        now = time.monotonic()
        ttl = self._cfg.web.price_cache_ttl_seconds
        with self._lock:
            hit = self._cache.get(ticker)
            if hit is not None:
                snap, fetched_at = hit
                if now - fetched_at <= ttl:
                    return snap
        snap = self._fetch_with_fallback(ticker)
        if snap is None:
            return None
        with self._lock:
            self._cache[ticker] = (snap, now)
        # Evaluate breaker OUTSIDE the lock — _maybe_trip_breaker acquires
        # self._lock itself, so calling it inside would deadlock.
        self._maybe_trip_breaker()
        return snap

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def refresh_all(self, tickers) -> None:
        """Invalidate cache entries so the next `get` re-fetches."""
        with self._lock:
            for t in tickers:
                self._cache.pop(t, None)

    # ---------- internals (single-ticker) ----------

    def _fetch_with_fallback(self, ticker: str) -> PriceSnapshot | None:
        if self.is_degraded():
            return self._fallback_snapshot(ticker)
        if not self.market_hours_now():
            last = self._last_close(ticker)
            if last is None:
                return None
            return PriceSnapshot(
                ticker=ticker, price=last, asof=datetime.now(),
                is_stale=True, source="last_close_market_closed",
            )
        try:
            # Schwab Sub-bundle C T-C.4: when a ladder fetcher is installed,
            # route the live fetch through it. The ladder owns env routing
            # (sandbox short-circuit lives inside the ladder); returned
            # provider tag is stamped onto the snapshot. Legacy yfinance-only
            # path remains the default when no ladder is installed.
            provider_tag: str | None = None
            if self._ladder_fetcher is not None:
                price, provider_tag = self._ladder_fetcher(ticker)
            else:
                price = self._fetch_live_price(ticker)
            self._record_outcome(success=True)
            return PriceSnapshot(
                ticker=ticker, price=price, asof=datetime.now(),
                is_stale=False, source="live",
                provider=provider_tag,
            )
        except Exception as exc:
            log.warning("live fetch failed for %s: %s", ticker, exc)
            self._record_outcome(success=False)
            last = self._last_close(ticker)
            if last is None:
                return None
            return PriceSnapshot(
                ticker=ticker, price=last, asof=datetime.now(),
                is_stale=True, source="last_close",
            )

    def _fetch_live_price(self, ticker: str) -> float:
        """Live yfinance call with an enforced per-ticker timeout.

        **Call context invariant** (R4 Minor 2): `_fetch_live_price` is
        ONLY invoked from `_fetch_with_fallback` during market hours (the
        `if not self.market_hours_now()` branch short-circuits to last-close
        BEFORE this method runs). Out-of-hours bars from `yf.download` are
        therefore never returned to the dashboard; the market-hours gate
        is the authoritative session-boundary check.

        `yfinance.Ticker(t).fast_info` does NOT accept a `timeout` kwarg and
        can hang indefinitely. `yfinance.download(...)` DOES propagate
        `timeout=` through to the underlying requests session.

        Extraction contract (R2 Minor 1):
        - Call: `yf.download(ticker, period="1d", interval="1m",
          progress=False, timeout=<cfg>, auto_adjust=False,
          group_by="column")`. `group_by="column"` keeps a single-level
          column index regardless of ticker count so `df["Close"]` always
          returns a Series.
        - Empty frame -> raise `RuntimeError("no bars")`. Minute-bar data
          can legitimately be empty pre-market-open even during what the
          NYSE calendar calls "market hours" (the calendar treats the
          regular session as 09:30-16:00 but yfinance's 1m data may not
          backfill that precisely at 09:29:59).
        - Walk the `Close` series backwards, returning the first non-NaN
          value - the last bar can carry NaN when yfinance streams a new
          minute whose close hasn't finalized.
        - If every `Close` value is NaN -> raise `RuntimeError("all close NaN")`.

        Timeout default is `self._cfg.web.price_fetch_timeout_seconds` (3s).
        Caller (`_fetch_with_fallback`) catches any exception and falls back
        to last-close with `is_stale=True, source="last_close"`.
        """
        import yfinance as yf
        df = yf.download(
            ticker,
            period="1d",
            interval="1m",
            progress=False,
            timeout=self._cfg.web.price_fetch_timeout_seconds,
            auto_adjust=False,
            group_by="column",
            threads=False,   # CRITICAL (R3 Major 1): yfinance's internal
                             # thread pool would bypass app.state.price_fetch_executor's
                             # max_workers cap. Concurrency must be controlled
                             # solely by the app-level executor.
        )
        if df is None or df.empty:
            raise RuntimeError(f"yfinance returned no bars for {ticker}")
        # yfinance >= ~0.2.4x returns a MultiIndex column (Price × Ticker)
        # even for single-ticker `group_by='column'` calls. `df["Close"]` is
        # then a DataFrame (one column per ticker), not a Series — so the
        # downstream `float(iloc[-1])` explodes with "float() argument must
        # be a string or a real number, not 'Series'". Squeeze to Series.
        close = df["Close"]
        if hasattr(close, "ndim") and close.ndim == 2:
            close = close.iloc[:, 0]
        close_series = close.dropna()
        if close_series.empty:
            raise RuntimeError(f"all Close values are NaN for {ticker}")
        return float(close_series.iloc[-1])

    def _last_close(self, ticker: str) -> float | None:
        conn = connect(self._cfg.paths.db_path)
        try:
            row = conn.execute(
                """SELECT close FROM candidates c
                   JOIN evaluation_runs e ON e.id = c.evaluation_run_id
                   WHERE c.ticker = ? AND c.close IS NOT NULL
                   ORDER BY e.run_ts DESC
                   LIMIT 1""",
                (ticker,),
            ).fetchone()
        finally:
            conn.close()
        return float(row[0]) if row else None

    # ---------- circuit breaker ----------

    def _record_outcome(self, *, success: bool) -> None:
        """Update the failure window atomically. Called after every real
        fetch attempt. Live-only: last-close fallbacks don't count as
        either success or failure."""
        with self._lock:
            self._failure_window.append(not success)  # True = failure

    def is_degraded(self) -> bool:
        with self._lock:
            return self._degraded_until is not None and time.monotonic() < self._degraded_until

    def degraded_until(self) -> datetime | None:
        with self._lock:
            if self._degraded_until is None:
                return None
            if time.monotonic() >= self._degraded_until:
                return None
            remaining = self._degraded_until - time.monotonic()
            return datetime.fromtimestamp(time.time() + remaining)

    def _maybe_trip_breaker(self) -> None:
        """Enter degraded mode if failure fraction in window > 0.5."""
        with self._lock:
            if not self._failure_window:
                return
            failures = sum(1 for x in self._failure_window if x)
            if failures / len(self._failure_window) > 0.5:
                cooldown = self._cfg.web.circuit_breaker_cooldown_seconds
                self._degraded_until = time.monotonic() + cooldown
                log.warning(
                    "price cache entered degraded mode for %ss (failures=%d/%d)",
                    cooldown, failures, len(self._failure_window),
                )

    def reset_circuit_breaker(self) -> None:
        """Clear degraded state + failure window. Called by the user-
        initiated POST /prices/refresh flow so an operator can force-try
        a live fetch even while the breaker is tripped (R2 Major 2). If
        the refetch fails, the breaker will trip again on its own."""
        with self._lock:
            self._failure_window.clear()
            self._degraded_until = None

    # ---------- accepted limitation: executor saturation ----------
    #
    # Python threads cannot be forcibly killed (R4 Major 1). If yfinance's
    # own timeout fails to unwind (e.g., socket stuck in kernel-level
    # SYN-SENT), the corresponding executor worker remains occupied until
    # the OS socket timeout eventually trips (typically 30-60s). Under a
    # sustained stall, all `max_concurrent_price_fetches=8` workers can
    # end up holding stuck tasks simultaneously.
    #
    # Mitigations designed in:
    #   1. Shared executor caps worst-case occupied threads at 8 — prevents
    #      unbounded growth.
    #   2. Circuit breaker trips after ~11/20 failures + 60s cooldown
    #      during which `get_many` short-circuits WITHOUT submitting
    #      anything to the executor -> stuck threads get time to unwind.
    #   3. `executor.shutdown(wait=False, cancel_futures=True)` in the
    #      FastAPI lifespan releases queued tasks at shutdown; in-flight
    #      threads die with the uvicorn process.
    #
    # Practical worst case: 8 fetches go stale simultaneously AND the
    # breaker does not trip (e.g. alternating successes and failures).
    # Each page load then waits up to `price_fetch_deadline_seconds`=6s
    # before falling back to last-close. This is accepted — the
    # alternatives (process-level worker pool, async rewrite) are out
    # of scope for the localhost single-user Phase 3a tool. Operator
    # recovery: restart `swing web` -> executor is recreated.

    # ---------- batch API ----------

    def get_many(
        self, tickers: Sequence[str], deadline_seconds: float,
        *, executor=None,
    ) -> dict[str, PriceSnapshot]:
        """Batch version of get(). Cache hits are served synchronously; misses
        are dispatched to `executor` (required; app.state.price_fetch_executor
        in production) with a total deadline.

        Leaked threads on timeout are tolerated (spec §3.2): each is waiting
        on an HTTP socket with yfinance's own timeout and terminates at most
        one per-ticker-timeout window later.
        """
        # Degraded mode: skip all live fetches.
        if self.is_degraded():
            out: dict[str, PriceSnapshot] = {}
            for t in tickers:
                last = self._last_close(t)
                if last is not None:
                    out[t] = PriceSnapshot(
                        ticker=t, price=last, asof=datetime.now(),
                        is_stale=True, source="last_close",
                    )
            return out

        if executor is None:
            raise ValueError("executor is required — pass app.state.price_fetch_executor")

        results: dict[str, PriceSnapshot] = {}
        misses: list[str] = []
        now = time.monotonic()
        ttl = self._cfg.web.price_cache_ttl_seconds
        with self._lock:
            for t in tickers:
                hit = self._cache.get(t)
                if hit is not None and now - hit[1] <= ttl:
                    results[t] = hit[0]
                else:
                    misses.append(t)

        if not misses:
            return results

        from concurrent.futures import TimeoutError as FuturesTimeout
        from concurrent.futures import as_completed
        futures = {executor.submit(self._fetch_with_fallback, t): t for t in misses}
        try:
            for future in as_completed(futures, timeout=deadline_seconds):
                ticker = futures[future]
                try:
                    snap = future.result(timeout=0)
                except Exception:
                    snap = self._fallback_snapshot(ticker)
                if snap is not None:
                    results[ticker] = snap
                    with self._lock:
                        self._cache[ticker] = (snap, time.monotonic())
        except FuturesTimeout:
            pass

        for ticker in misses:
            if ticker not in results:
                snap = self._fallback_snapshot(ticker)
                if snap is not None:
                    results[ticker] = snap

        self._maybe_trip_breaker()
        return results

    def _fallback_snapshot(self, ticker: str) -> PriceSnapshot | None:
        last = self._last_close(ticker)
        if last is None:
            return None
        return PriceSnapshot(
            ticker=ticker, price=last, asof=datetime.now(),
            is_stale=True, source="last_close",
        )

    # ---------- market hours ----------

    def market_hours_now(self) -> bool:
        """True during NYSE regular session (incl. holidays-aware).

        Uses `exchange_calendars` (already a Phase 1 base dep via
        `swing.evaluation.dates`).

        NOTE: `is_open_at_time` requires a `pd.Timestamp`, not a plain
        `datetime.datetime`, on exchange_calendars >= 4.x — it raises
        `TypeError` otherwise. Wrap accordingly before calling.
        """
        import exchange_calendars as xcals
        import pandas as pd
        nyse = xcals.get_calendar("XNYS")
        utc_now = pd.Timestamp(datetime.now(UTC))
        try:
            return bool(nyse.is_open_at_time(utc_now, ignore_breaks=True))
        except Exception:
            return False
