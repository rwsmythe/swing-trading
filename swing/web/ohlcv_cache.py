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
        # Normalize + deduplicate (spec §4.1): "aapl" and "AAPL" coalesce
        # to a single lookup. `dict.fromkeys(...)` preserves insertion order
        # and removes duplicates so breaker accounting isn't double-counted.
        normalized = list(dict.fromkeys(t.upper() for t in tickers))

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
        exceeds 50% AND the window has at least 5 samples. The minimum-sample
        guard prevents a single transient deadline miss from tripping the
        breaker — transient misses are expected noise (spec §6, decision 8).
        Cooldown uses cfg.web.circuit_breaker_cooldown_seconds."""
        with self._lock:
            if len(self._failure_window) < 5:
                return
            failures = sum(1 for x in self._failure_window if x)
            if failures / len(self._failure_window) > 0.5:
                cooldown = self._cfg.web.circuit_breaker_cooldown_seconds
                self._degraded_until = time.monotonic() + cooldown
                log.warning(
                    "ohlcv cache entered degraded mode for %ss (failures=%d/%d)",
                    cooldown, failures, len(self._failure_window),
                )
