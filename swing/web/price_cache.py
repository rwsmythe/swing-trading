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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

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
        if not self.market_hours_now():
            last = self._last_close(ticker)
            if last is None:
                return None
            return PriceSnapshot(
                ticker=ticker, price=last, asof=datetime.now(),
                is_stale=True, source="last_close_market_closed",
            )
        try:
            price = self._fetch_live_price(ticker)
            self._record_outcome(success=True)
            return PriceSnapshot(
                ticker=ticker, price=price, asof=datetime.now(),
                is_stale=False, source="live",
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
        close_series = df["Close"].dropna()
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

    # ---------- circuit breaker (wired in Task 6) ----------

    def _record_outcome(self, *, success: bool) -> None:
        """Update the failure window + degraded flag atomically. Called
        after every real fetch attempt. Live-only: last-close fallbacks
        don't count as either success or failure."""
        with self._lock:
            self._failure_window.append(not success)  # True = failure

    # ---------- market hours ----------

    def market_hours_now(self) -> bool:
        """True during NYSE regular session (incl. holidays-aware).

        Uses `exchange_calendars` (already a Phase 1 base dep via
        `swing.evaluation.dates`).
        """
        import exchange_calendars as xcals
        nyse = xcals.get_calendar("XNYS")
        utc_now = datetime.now(timezone.utc)
        try:
            return bool(nyse.is_open_at_time(utc_now, ignore_breaks=True))
        except Exception:
            return False
