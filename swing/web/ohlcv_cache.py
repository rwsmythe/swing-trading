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
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, Future, wait
from dataclasses import dataclass
from datetime import datetime as _dt
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from swing.config import Config
from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.evaluation.dates import last_completed_session
from swing.pipeline import ohlcv as ohlcv_mod

if TYPE_CHECKING:
    import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OhlcvBundle:
    """SMA10/20/50 + previous close + ADR% from a single daily-bar fetch.
    All fields are None if the fetch failed or the bar history was
    insufficient for the given period. `fetched_at` is a monotonic
    timestamp (time.monotonic()).

    3e.8 Bundle 2 — ``adr_pct`` added for §4.D parabolic-trim advisory.
    Default None so any code that constructs OhlcvBundle without supplying
    it (e.g., older test fixtures, hand-built bundles) continues to work
    with the rule silently no-opping.

    Schwab Sub-bundle C T-C.4 — ``provider`` provenance tag added (mirrors
    ``PriceSnapshot.provider`` shape). None (legacy / not set) | 'schwab_api'
    (ladder returned Schwab-success path) | 'yfinance' (ladder yfinance
    fallback path OR pre-ladder direct yfinance fetch). DISTINCT from any
    TTL-state / freshness field; documents data origin only.
    """
    sma10: float | None
    sma20: float | None
    sma50: float | None
    previous_close: float | None
    fetched_at: float
    adr_pct: float | None = None
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.provider is not None:
            if not isinstance(self.provider, str):
                raise TypeError(
                    "OhlcvBundle.provider must be str or None; got "
                    f"{type(self.provider).__name__}"
                )
            if self.provider not in ("schwab_api", "yfinance"):
                raise ValueError(
                    "OhlcvBundle.provider must be one of None | "
                    f"'schwab_api' | 'yfinance'; got {self.provider!r}"
                )

    @classmethod
    def empty(cls, fetched_at: float) -> OhlcvBundle:
        return cls(None, None, None, None, fetched_at, None, None)


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
        # Schwab Sub-bundle C T-C.4: optional ladder-aware bars fetcher. When
        # None (default), the worker uses the legacy `ohlcv_mod.fetch_daily_bars`
        # path (yfinance via archive). When set, the worker invokes the
        # callable which MUST return `(bars_df_or_none, provider_tag)` where
        # `provider_tag` is 'schwab_api' or 'yfinance'. The provider tag is
        # stamped onto the resulting OhlcvBundle. Sandbox short-circuit + auth
        # fall-through live INSIDE the ladder; cache stays env-agnostic.
        self._ladder_bars_fetcher: (
            Callable[[str], tuple[Any, str]] | None
        ) = None
        # Phase 13 T1.SB0 (plan §G.0): separate store for the DataFrame-returning
        # `get_or_fetch` surface. Keyed by `(ticker_upper, window_days)`; values
        # are `(DataFrame, fetched_at_monotonic)`. Separate lock from `self._lock`
        # so chart-bars traffic does not contend with dashboard bundle traffic
        # (recon §4.B).
        self._bars_lock = threading.Lock()
        self._bars_store: dict[tuple[str, int], tuple[Any, float]] = {}

    def set_ladder_bars_fetcher(
        self,
        fetcher: Callable[[str], tuple[Any, str]] | None,
    ) -> None:
        """Install (or clear) a ladder-aware bars-fetch callable.

        ``fetcher`` must accept the ticker symbol and return
        ``(bars_df_or_none, provider: str)`` where ``provider`` is
        ``'schwab_api'`` or ``'yfinance'``. When set, the cache's worker
        invokes this callable instead of ``ohlcv_mod.fetch_daily_bars``;
        the returned ``bars`` are fed through the same SMA / ADR
        computation pipeline and the provider tag is stamped onto the
        resulting ``OhlcvBundle``.

        Passing ``None`` reverts to the legacy yfinance-only worker path
        (used by existing OhlcvCache tests that don't exercise the ladder).
        """
        self._ladder_bars_fetcher = fetcher

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        """Return daily bars for ``ticker`` over a calendar-day lookback window.

        Phase 13 T1.SB0 (plan §G.0): closes the Phase 11 Sub-bundle C R1 M#5
        ACCEPT-WITH-RATIONALE V1 deferral by exposing a DataFrame-returning
        surface for ``_step_charts`` + downstream Theme 2 detectors (T2.SB2,
        T2.SB3) + T3.SB3 review auto-fill.

        Shape contract: ``pd.DataFrame`` indexed by date (``DatetimeIndex``) with
        capitalized columns ``Open / High / Low / Close / Volume``. Matches
        ``PriceFetcher.get``'s shape (recon §3 parity table).

        Window semantics: ``window_days`` is a calendar-day lookback ending at
        ``last_completed_session(now())`` — backward-looking, NOT forward-looking
        (CLAUDE.md session-anchor read/write mismatch family). Matches the
        legacy ``_step_charts`` line-1323 callsite contract.

        Caching: TTL-keyed by ``(ticker.upper(), window_days)`` in
        ``self._bars_store`` (separate from the bundle ``self._store`` so
        dashboard bundle traffic + chart bars traffic do not contend on lock
        acquisition). TTL inherited from ``cfg.web.ohlcv_cache_ttl_seconds``.

        Routing: when ``set_ladder_bars_fetcher`` is installed, the ladder hook
        is invoked + its DataFrame sliced to the calendar-day window. Otherwise
        ``read_or_fetch_archive`` is consulted directly + sliced. Either path
        inherits the ``read_or_fetch_archive`` shape (capitalized OHLCV +
        DatetimeIndex). Sandbox short-circuit lives inside the ladder; this
        method is env-agnostic.

        Empty-result semantics: raises ``ValueError("No data for {ticker}")`` —
        matches ``PriceFetcher.get``'s raise-on-empty contract so the
        ``_step_charts`` line 1322-1330 ``except Exception`` clause produces
        ``chart_status='fetcher_failed'`` unchanged.

        Concurrency: synchronous + thread-safe under ``self._bars_lock``. The
        lock is NOT held during the fetch call (prevents serialization through
        the lock + I/O). Two threads racing on the same ``(ticker, window_days)``
        each fetch independently + each write; last-writer-wins. Both fetches
        see the same archive-source so values are identical; no data corruption.
        Per-key in-flight dedup is a V2 candidate (recon §4.B).
        """
        ticker_upper = ticker.upper()
        key = (ticker_upper, int(window_days))
        now = time.monotonic()
        with self._bars_lock:
            hit = self._bars_store.get(key)
            if hit is not None and (now - hit[1]) <= self._ttl:
                # Defensive copy on read (Codex R3 Minor #1 fix 2026-05-18):
                # ``get_or_fetch`` is substrate for downstream detector +
                # auto-fill consumers. Returning the stored frame by
                # reference would let one consumer mutating columns/rows
                # corrupt the cache value observed by later consumers
                # within the TTL window. Copy-on-read is the cheapest
                # safety net; copy-on-write at store-time is also defended
                # below for the same reason.
                return hit[0].copy()
        bars = self._fetch_bars_window(
            ticker=ticker_upper, window_days=int(window_days),
        )
        if bars is None or bars.empty:
            raise ValueError(f"No data for {ticker_upper}")
        with self._bars_lock:
            # Store a copy so a caller mutating their returned frame after
            # this call cannot reach back into the cached value.
            self._bars_store[key] = (bars.copy(), time.monotonic())
        return bars

    def _fetch_bars_window(
        self, *, ticker: str, window_days: int,
    ) -> pd.DataFrame | None:
        """Internal: fetch a calendar-day window of daily bars; returns
        ``DataFrame`` or ``None``. Caller maps ``None → ValueError`` so the
        public ``get_or_fetch`` matches ``PriceFetcher.get``'s raise-on-empty
        contract.

        Mirrors ``swing.prices.PriceFetcher.get`` semantics — ``end`` anchors at
        ``last_completed_session(now())`` (backward-looking, matches the
        CLAUDE.md session-anchor gotcha family), and the slice cuts on
        calendar-day cutoff. Belt-and-suspenders in-progress-bar strip mirrors
        ``swing.pipeline.ohlcv.fetch_daily_bars`` (CLAUDE.md yfinance gotcha).
        """
        end = last_completed_session(_dt.now())
        cutoff = end - timedelta(days=window_days)

        if self._ladder_bars_fetcher is not None:
            try:
                result = self._ladder_bars_fetcher(ticker)
            except Exception as exc:  # noqa: BLE001 — safety boundary
                log.warning(
                    "ohlcv ladder bars fetch raised for %s: %s", ticker, exc,
                )
                return None
            if result is None:
                return None
            bars = result[0] if isinstance(result, tuple) else result
            if bars is None or bars.empty:
                return None
        else:
            bars = read_or_fetch_archive(
                ticker,
                end_date=end,
                cache_dir=self._cfg.paths.prices_cache_dir,
                archive_history_days=self._cfg.archive.archive_history_days,
            )
            if bars is None or bars.empty:
                return None

        # Belt-and-suspenders in-progress bar strip (CLAUDE.md yfinance gotcha).
        # Inequality matters: `end` here is `last_completed_session(now())`
        # (backward-looking), so the archive's last legitimate bar can equal
        # `end`. Only strict-greater (a stray partial bar past the last
        # completed session) is partial-data. Using `>=` would over-strip on
        # every read. Distinct from `fetch_daily_bars` which anchors on
        # `action_session_for_run(now())` (forward-looking) and correctly uses
        # `>=`. Preserves shape parity with `PriceFetcher.get` (which performs
        # no strip; archive helper handles partial-bar avoidance).
        if bars.index[-1].date() > end:
            bars = bars.iloc[:-1]
        if bars.empty:
            return None
        sliced = bars.loc[
            (bars.index.date >= cutoff) & (bars.index.date <= end)
        ]
        if sliced.empty:
            return None
        return sliced

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

        Pure return — does NOT touch self._store (R1 Critical 1).

        Schwab Sub-bundle C T-C.4: when a ladder bars fetcher is installed
        via `set_ladder_bars_fetcher`, the worker delegates to it; the
        returned provider tag is stamped onto the resulting OhlcvBundle.
        Otherwise the legacy `ohlcv_mod.fetch_daily_bars` path runs (provider
        tag remains None for backward compatibility).
        """
        with self._sema:
            provider_tag: str | None = None
            try:
                if self._ladder_bars_fetcher is not None:
                    bars, provider_tag = self._ladder_bars_fetcher(ticker)
                else:
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
            adr_pct = ohlcv_mod.compute_adr_pct(bars, lookback=20)
            return OhlcvBundle(
                sma10=smas.get(10),
                sma20=smas.get(20),
                sma50=smas.get(50),
                previous_close=prev,
                fetched_at=now,
                adr_pct=adr_pct,
                provider=provider_tag,
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
