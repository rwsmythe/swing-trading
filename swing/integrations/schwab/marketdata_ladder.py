"""Schwab market-data ladder fetcher (Phase 11 Sub-bundle C T-C.3).

Two ladder functions, one per call-shape:

  - `fetch_quote_via_ladder(ticker, *, cfg, schwab_client,
    yfinance_fallback_fn, conn, surface, pipeline_run_id=None)`
    → `tuple[PriceSnapshot, str]`
  - `fetch_window_via_ladder(ticker, *, start, end, cfg, schwab_client,
    yfinance_fallback_fn, conn, surface, pipeline_run_id=None)`
    → `tuple[SchwabPriceHistoryWindow, str]`

The second tuple element is the provenance tag: 'schwab_api' on a Schwab
success path, 'yfinance' on a yfinance fallback path.

Per plan §H.6.1 + §H.6.2 + dispatch brief T-C.3:

  1. **Sandbox / disabled short-circuit:** if
     ``cfg.integrations.schwab.environment != 'production'`` OR
     ``not cfg.integrations.schwab.marketdata_ladder_enabled`` →
     invoke ``yfinance_fallback_fn`` directly; return with provider tag
     ``'yfinance'``. NO schwabdev call attempted. NO audit row written
     (pipeline-internal silent-skip per spec §3.6.3 + Sub-bundle B
     forward-binding lesson #2 surface-aware advisory audit).
  2. **Production + ladder enabled + schwab_client is None:** treated as
     fall-through to yfinance with WARNING log (per dispatch brief §0.5
     pre-emption #7 — caller couldn't construct a client).
  3. **Production + ladder enabled + schwab_client provided:** invoke the
     T-C.1 wrapper (which owns audit-lifecycle + transport-debug suppression
     + signature-hash + mapper). On success → wrap or pass-through with
     provider='schwab_api'.
  4. **On T-C.1 wrapper raising SchwabAuthError / SchwabRateLimitError /
     SchwabApiError:** log warning; invoke ``yfinance_fallback_fn``; return
     with provider tag ``'yfinance'``. Audit row already written by the
     T-C.1 wrapper (status='error'/'auth_failed'/'rate_limited').
  5. **Empty-bars handling:** mapper at T-C.1 raises synthetic
     ``SchwabApiError(204, "empty bars")`` per plan §H.6.4. Ladder catches
     via the ``SchwabApiError`` except clause; falls back to yfinance.
     parquet UNCHANGED (T-C.2 empty-write guard provides defense-in-depth).
  6. **Partial-response on quotes:** mapper at T-C.1 returns
     dict-of-successful-symbols. Ladder receives this dict; if requested
     ticker absent → treats as failure → falls back to yfinance.

**`PriceSnapshot.provider` field addition (Option A)** — per dispatch brief
§0.5 pre-emption #4, the `provider: str | None = None` field was added to
`swing.web.price_cache.PriceSnapshot` IN THIS TASK so the ladder can stamp
provenance at construction time; T-C.4 cache-integration consumes the field
naturally without dataclass extension. Banked as plan deviation.

**Reads but does NOT write `schwab_api_calls`:** all audit rows for the
ladder's Schwab-attempted path are written by the T-C.1 wrappers
(`get_quotes_batch` / `get_price_history`). The ladder itself writes
nothing — sandbox/disabled short-circuits and yfinance-fallback paths are
silent per spec §3.6.3.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
)
from swing.integrations.schwab.marketdata import (
    get_price_history,
    get_quotes_batch,
)
from swing.integrations.schwab.models import (
    SchwabPriceHistoryWindow,
    SchwabQuoteResponse,
)
from swing.web.price_cache import PriceSnapshot

log = logging.getLogger(__name__)


def _resolve_cache_dir(cfg: Any) -> Path | None:
    """Best-effort lookup of ``cfg.paths.prices_cache_dir``.

    Codex R1 Major #3: persisting Schwab/yfinance window data to the Shape A
    archive requires a cache directory. Production cfg has
    ``cfg.paths.prices_cache_dir`` available; minimal test cfgs (SimpleNamespace)
    may not. Return None when unavailable so the ladder gracefully skips
    persistence in test scenarios that don't exercise the archive layer.
    """
    paths = getattr(cfg, "paths", None)
    if paths is None:
        return None
    cache_dir = getattr(paths, "prices_cache_dir", None)
    if cache_dir is None:
        return None
    return Path(cache_dir)


def _schwab_window_to_shape_a_df(window: SchwabPriceHistoryWindow):
    """Convert a ``SchwabPriceHistoryWindow`` to a Shape A DataFrame
    (``asof_date`` ISO string column + lowercase OHLCV columns) suitable for
    ``swing.data.ohlcv_archive.write_window``.

    Distinct from ``SchwabPriceHistoryWindow.to_dataframe()`` (M#4) which
    returns the IN-MEMORY legacy yfinance shape (DatetimeIndex + capitalized
    OHLCV) consumed by ``compute_smas`` + chart-step downstream code.
    """
    import pandas as pd

    return pd.DataFrame(
        {
            "asof_date": [bar.asof_date for bar in window.bars],
            "open": [bar.open for bar in window.bars],
            "high": [bar.high for bar in window.bars],
            "low": [bar.low for bar in window.bars],
            "close": [bar.close for bar in window.bars],
            "volume": [bar.volume for bar in window.bars],
        }
    )


def _yfinance_window_to_shape_a_df(window: Any):
    """Best-effort conversion of an arbitrary yfinance-fallback return value
    to a Shape A DataFrame.

    The yfinance fallback for the window ladder may return any of:
      - DatetimeIndex DataFrame with capitalized OHLCV columns (from
        ``_yf_download_window`` → ``read_or_fetch_archive`` legacy path);
      - already-Shape-A DataFrame (some test fixtures);
      - ``SchwabPriceHistoryWindow`` (some test fixtures use a Schwab dataclass
        as the fallback return — see ``test_04_window_production_path_empty_bars``);
      - None or empty.

    Returns None when conversion is infeasible (e.g., empty window, can't
    detect date column, non-DataFrame). Callers MUST guard the
    ``write_window`` call against ``None`` (which ``write_window``'s
    empty-window guard already handles).
    """
    if window is None:
        return None
    # SchwabPriceHistoryWindow path — use the same converter as Schwab success.
    if isinstance(window, SchwabPriceHistoryWindow):
        if not window.bars:
            return None
        return _schwab_window_to_shape_a_df(window)
    # DataFrame path — normalize via the archive's legacy helper.
    try:
        import pandas as pd

        from swing.data.ohlcv_archive import _normalize_legacy_dataframe
    except ImportError:  # pragma: no cover — defensive
        return None
    if not isinstance(window, pd.DataFrame):
        return None
    if window.empty:
        return None
    try:
        return _normalize_legacy_dataframe(window)
    except (ValueError, KeyError, AttributeError):
        return None


def _persist_window_to_archive(
    ticker: str,
    window: Any,
    provider: str,
    cache_dir: Path | None,
) -> None:
    """Best-effort persistence of a window to the Shape A archive.

    Codex R1 Major #3 — the ladder previously dropped Schwab-fetched bars on
    the floor; subsequent reads via ``resolve_ohlcv_window`` saw no
    schwab_api archive content. Persisting here ensures Schwab-sourced bars
    survive cross-call/cross-process via the archive layer.

    Failures are LOGGED but never propagated — write failures must not abort
    the ladder's primary contract (return the window to the caller).
    """
    if cache_dir is None or window is None:
        return
    if provider == "schwab_api" and isinstance(window, SchwabPriceHistoryWindow):
        df = _schwab_window_to_shape_a_df(window)
    elif provider == "yfinance":
        df = _yfinance_window_to_shape_a_df(window)
    else:  # pragma: no cover — defensive
        return
    if df is None:
        return
    try:
        from swing.data.ohlcv_archive import write_window
        write_window(ticker, df, provider, cache_dir=cache_dir)
    except Exception as exc:
        log.warning(
            "fetch_window_via_ladder: archive persistence failed for "
            "%s/%s: %s (continuing)",
            ticker, provider, type(exc).__name__,
        )


# ============================================================================
# Helpers
# ============================================================================


def _validate_ticker(ticker: Any) -> str:
    """Defense-in-depth (dispatch brief T-C.3 test #10): reject empty,
    None, non-string tickers BEFORE branching into env/ladder logic."""
    if ticker is None:
        raise TypeError("ticker must be non-empty str; got None")
    if not isinstance(ticker, str):
        raise TypeError(
            f"ticker must be non-empty str; got {type(ticker).__name__}"
        )
    if not ticker:
        raise ValueError("ticker must be non-empty str; got ''")
    return ticker


def _is_ladder_active(cfg: Any) -> bool:
    """Per plan §H.6.1 + §H.6.2 short-circuit predicate.

    Returns True iff env == 'production' AND
    marketdata_ladder_enabled == True. Any other case (sandbox, disabled
    flag, missing attrs) returns False → yfinance-only path.
    """
    integrations = getattr(cfg, "integrations", None)
    if integrations is None:
        return False
    schwab_cfg = getattr(integrations, "schwab", None)
    if schwab_cfg is None:
        return False
    env = getattr(schwab_cfg, "environment", None)
    enabled = getattr(schwab_cfg, "marketdata_ladder_enabled", None)
    return env == "production" and bool(enabled)


def _build_price_snapshot_from_quote(
    ticker: str, quote: SchwabQuoteResponse,
) -> PriceSnapshot:
    """Construct a PriceSnapshot stamped with provider='schwab_api'.

    asof = now() (the quote's `quote_time` is informational; ladder consumers
    treat asof as fetch-time for TTL bookkeeping); is_stale=False;
    source='live' (preserves existing TTL-state field semantics per plan
    pseudocode); provider='schwab_api'.
    """
    return PriceSnapshot(
        ticker=ticker,
        price=float(quote.last_price),
        asof=datetime.now(),
        is_stale=False,
        source="live",
        provider="schwab_api",
    )


# ============================================================================
# Quote ladder
# ============================================================================


def fetch_quote_via_ladder(
    ticker: str,
    *,
    cfg: Any,
    schwab_client: Any | None,
    yfinance_fallback_fn: Callable[[str], PriceSnapshot],
    conn: sqlite3.Connection,
    surface: str,
    pipeline_run_id: int | None = None,
) -> tuple[PriceSnapshot, str]:
    """Quote-fetch ladder: Schwab → yfinance fallback.

    Returns ``(entry, provider_tag)`` where:
      - ``entry`` is a ``PriceSnapshot`` instance.
      - ``provider_tag`` is ``'schwab_api'`` on Schwab success or
        ``'yfinance'`` on fallback.

    The ``yfinance_fallback_fn`` callable receives the ticker only and MUST
    return a ``PriceSnapshot`` (provider field optional — ladder does NOT
    re-stamp on the yfinance return path; caller-supplied provider is
    preserved).

    Raises:
        TypeError / ValueError on invalid ticker input (defense-in-depth).
    """
    ticker = _validate_ticker(ticker)

    # Sandbox / disabled short-circuit (plan §H.6.1 LOCK; ZERO audit row).
    if not _is_ladder_active(cfg):
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")

    # Production + ladder enabled but client wasn't constructed → fallback.
    if schwab_client is None:
        log.warning(
            "fetch_quote_via_ladder: schwab_client is None in production; "
            "falling back to yfinance for %s",
            ticker,
        )
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")

    # Attempt Schwab. The T-C.1 wrapper owns _suppress_transport_debug_logs +
    # audit-lifecycle + signature-hash + mapper.
    try:
        mapped = get_quotes_batch(
            schwab_client,
            conn,
            [ticker],
            surface=surface,
            environment="production",
            pipeline_run_id=pipeline_run_id,
        )
    except (SchwabAuthError, SchwabRateLimitError, SchwabApiError) as exc:
        log.warning(
            "Schwab market-data quote fetch failed for %s "
            "(%s); falling back to yfinance",
            ticker, type(exc).__name__,
        )
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")
    except Exception:  # pragma: no cover — defensive
        # Any unexpected exception from the wrapper is treated as a failure
        # → yfinance fallback. The wrapper has already logged + written its
        # audit row.
        log.warning(
            "fetch_quote_via_ladder: unexpected error from T-C.1 wrapper for "
            "%s; falling back to yfinance", ticker,
        )
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")

    # Partial-response (plan §E.4): if requested ticker absent from mapper
    # output → fall back to yfinance. T-C.1 wrapper already wrote audit row
    # reflecting partial-success / all-failed disposition.
    quote = mapped.get(ticker)
    if quote is None:
        log.warning(
            "fetch_quote_via_ladder: ticker %s absent from Schwab response "
            "(partial-response per §E.4); falling back to yfinance",
            ticker,
        )
        entry = yfinance_fallback_fn(ticker)
        return (entry, "yfinance")

    entry = _build_price_snapshot_from_quote(ticker, quote)
    return (entry, "schwab_api")


# ============================================================================
# Window ladder
# ============================================================================


def fetch_window_via_ladder(
    ticker: str,
    *,
    start: datetime | int | None,
    end: datetime | int | None,
    cfg: Any,
    schwab_client: Any | None,
    yfinance_fallback_fn: Callable[
        [str, datetime | int | None, datetime | int | None],
        SchwabPriceHistoryWindow,
    ],
    conn: sqlite3.Connection,
    surface: str,
    pipeline_run_id: int | None = None,
) -> tuple[SchwabPriceHistoryWindow, str]:
    """Window-fetch ladder: Schwab → yfinance fallback.

    Returns ``(window, provider_tag)`` where:
      - ``window`` is a ``SchwabPriceHistoryWindow`` instance (or whatever
        the yfinance fallback emits; callers should treat it as a window-
        shaped object).
      - ``provider_tag`` is ``'schwab_api'`` on Schwab success or
        ``'yfinance'`` on fallback.

    The ``yfinance_fallback_fn`` callable receives ``(ticker, start, end)``
    and MUST return a window-shaped object.

    Empty-bars handling (plan §E.5 + §H.6.4): the T-C.1 mapper raises
    ``SchwabApiError(204, "empty bars")`` when Schwab returns
    ``{"empty": true, "candles": []}``. The ladder catches via the
    ``SchwabApiError`` except clause; falls back to yfinance; the T-C.1
    wrapper's audit row carries ``error_message='empty bars (transient)'``.
    Parquet write at T-C.2 is unchanged (empty-write guard provides
    defense-in-depth).

    Raises:
        TypeError / ValueError on invalid ticker input.
    """
    ticker = _validate_ticker(ticker)
    cache_dir = _resolve_cache_dir(cfg)

    if not _is_ladder_active(cfg):
        window = yfinance_fallback_fn(ticker, start, end)
        # Codex R1 Major #3 — persist yfinance window to Shape A archive
        # so subsequent resolve_ohlcv_window calls see the rows.
        _persist_window_to_archive(ticker, window, "yfinance", cache_dir)
        return (window, "yfinance")

    if schwab_client is None:
        log.warning(
            "fetch_window_via_ladder: schwab_client is None in production; "
            "falling back to yfinance for %s",
            ticker,
        )
        window = yfinance_fallback_fn(ticker, start, end)
        _persist_window_to_archive(ticker, window, "yfinance", cache_dir)
        return (window, "yfinance")

    try:
        schwab_window = get_price_history(
            schwab_client,
            conn,
            ticker,
            start_dt=start,
            end_dt=end,
            surface=surface,
            environment="production",
            pipeline_run_id=pipeline_run_id,
        )
    except (SchwabAuthError, SchwabRateLimitError, SchwabApiError) as exc:
        log.warning(
            "Schwab price_history failed for %s (%s); falling back to "
            "yfinance",
            ticker, type(exc).__name__,
        )
        window = yfinance_fallback_fn(ticker, start, end)
        _persist_window_to_archive(ticker, window, "yfinance", cache_dir)
        return (window, "yfinance")
    except Exception:  # pragma: no cover — defensive
        log.warning(
            "fetch_window_via_ladder: unexpected error from T-C.1 wrapper "
            "for %s; falling back to yfinance", ticker,
        )
        window = yfinance_fallback_fn(ticker, start, end)
        _persist_window_to_archive(ticker, window, "yfinance", cache_dir)
        return (window, "yfinance")

    # Codex R1 Major #3 — persist Schwab window to Shape A archive on
    # success so the merge layer in resolve_ohlcv_window can attribute
    # subsequent reads to schwab_api provenance.
    _persist_window_to_archive(ticker, schwab_window, "schwab_api", cache_dir)
    return (schwab_window, "schwab_api")


__all__ = [
    "fetch_quote_via_ladder",
    "fetch_window_via_ladder",
]
