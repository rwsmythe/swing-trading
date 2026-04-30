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
    def empty(cls, fetched_at: float) -> OhlcvBundle:
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

        Degraded short-circuit (R2 Major 2 resolution, scoped by R4 Major 1):
        when the breaker is tripped, skip executor submission for MISSES only —
        warm cache hits are still served normally. This preserves the 1-hour
        TTL value: a transient yfinance outage does not blank already-cached
        SMA advisories during cooldown. `is_degraded()` auto-clears the window
        after the cooldown expires so recovery can proceed.
        """
        # Normalize + deduplicate (spec §4.1).
        normalized = list(dict.fromkeys(t.upper() for t in tickers))

        now = time.monotonic()
        out: dict[str, OhlcvBundle] = {}
        to_fetch: list[str] = []
        hits_with_data = 0
        hits_empty_sentinel = 0

        # Cache scan — serve warm hits regardless of breaker state (R4 Major 1
        # resolution: valid cached bundles stay valid during cooldown).
        with self._lock:
            for t in normalized:
                hit = self._store.get(t)
                if hit is not None and (now - hit[1]) <= self._ttl:
                    out[t] = hit[0]
                    bundle = hit[0]
                    has_data = any(
                        v is not None for v in (
                            bundle.sma10, bundle.sma20, bundle.sma50, bundle.previous_close,
                        )
                    )
                    if has_data:
                        hits_with_data += 1
                    else:
                        hits_empty_sentinel += 1
                else:
                    to_fetch.append(t)

        # Ternary breaker accounting for cache hits:
        # - Data-hit: success (counts in window).
        # - Empty-sentinel hit: neutral (skips window) — R3 Major 1 fix.
        for _ in range(hits_with_data):
            self._record_outcome(success=True)
        for _ in range(hits_empty_sentinel):
            self._record_neutral()

        if not to_fetch:
            self._maybe_trip_breaker()
            return out

        # Degraded short-circuit — applies ONLY to misses (R4 Major 1 fix):
        # warm cache already served above, so during cooldown we just skip
        # fresh fetches for the remaining misses. These skips are NEUTRAL —
        # they don't pad the breaker window, same as sentinel hits.
        if self.is_degraded():
            for t in to_fetch:
                out[t] = OhlcvBundle.empty(fetched_at=time.monotonic())
                self._record_neutral()
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
                bundle, healthy = fut.result(timeout=0)
            except Exception as exc:
                # Should be rare — worker catches internally. This catches
                # worker framework issues (e.g. semaphore, MemoryError).
                log.warning("ohlcv worker raised for %s: %s", t, exc)
                bundle = OhlcvBundle.empty(fetched_at=time.monotonic())
                out[t] = bundle
                self._record_outcome(success=False)
                continue
            out[t] = bundle
            bundle_has_data = any(
                v is not None for v in (
                    bundle.sma10, bundle.sma20, bundle.sma50, bundle.previous_close,
                )
            )
            # Ternary breaker accounting:
            # - Unhealthy (fetch raised): failure. Counts in window.
            # - Healthy + has data: success. Counts in window.
            # - Healthy + empty (per-ticker data absence): NEUTRAL. Skip window.
            #   Prevents empty-result ticker from padding window with successes
            #   that would mask real source degradation (R2 Major 1).
            if not healthy:
                self._record_outcome(success=False)
            elif bundle_has_data:
                self._record_outcome(success=True)
            else:
                self._record_neutral()
            # Cache bundles with data (still from request thread — R1 Critical 1).
            # Also cache empty healthy bundles as a SENTINEL to avoid refetching
            # permanently bad tickers every render (R2 Major 2). Unhealthy
            # (raised) bundles are NOT cached — we want the next request to retry.
            if healthy:
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

    def _fetch_bundle_worker(self, ticker: str) -> tuple[OhlcvBundle, bool]:
        """Worker: acquire semaphore, fetch bars, build bundle. Returns
        (bundle, is_source_healthy).

        `is_source_healthy=False` ONLY when the fetch raised (source-level
        failure, e.g. yfinance down, network error). `True` means the fetch
        completed successfully — an empty result is per-ticker data absence
        (delisted symbol, bad ticker, no history) which is an operator issue,
        not a source issue, and MUST NOT trip the global breaker.

        Pure return — does NOT touch self._store (R1 Critical 1)."""
        with self._sema:
            try:
                bars = ohlcv_mod.fetch_daily_bars(
                    ticker,
                    n_bars=60,
                    cache_dir=self._cfg.paths.prices_cache_dir,
                    archive_history_days=self._cfg.archive.archive_history_days,
                )
            except Exception as exc:
                log.warning("ohlcv fetch raised for %s: %s", ticker, exc)
                return OhlcvBundle.empty(fetched_at=time.monotonic()), False
            now = time.monotonic()
            if bars is None:
                # Empty result (ticker has no data) — healthy from cache's view.
                return OhlcvBundle.empty(fetched_at=now), True
            smas = ohlcv_mod.compute_smas(bars, [10, 20, 50])
            prev = ohlcv_mod.previous_close(bars)
            return OhlcvBundle(
                sma10=smas.get(10),
                sma20=smas.get(20),
                sma50=smas.get(50),
                previous_close=prev,
                fetched_at=now,
            ), True

    def _record_outcome(self, *, success: bool) -> None:
        """Record one sliding-window outcome. True-failure appends True;
        success appends False. To skip the window (neutral outcome, e.g.
        per-ticker empty result that is not source-relevant) call
        `_record_neutral()` instead — never call this with a synthetic bool."""
        with self._lock:
            self._failure_window.append(not success)

    def _record_neutral(self) -> None:
        """Neutral outcome — per-ticker data absence after a healthy fetch.
        Does NOT touch the breaker window. Kept as an explicit method so
        callers document their intent vs. just omitting the call."""
        # Intentionally empty — the window is updated elsewhere. This method
        # exists for call-site clarity.
        pass

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
