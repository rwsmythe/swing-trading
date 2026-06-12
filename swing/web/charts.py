"""Phase 13 T2.SB6 T-A.6.1 — Theme 1 SVG-inline chart renderers (spec §4.3 + §C.1).

Pure-function matplotlib renderers returning raw SVG bytes for inlining into
HTMX partial responses. NO PNG output. Per spec §A.9 + §C.1 LOCK + CLAUDE.md
matplotlib mathtext gotcha:

  - ASCII-only text in titles/labels/annotations.
  - ``parse_math=False`` on ``fig.suptitle`` defense-in-depth.
  - NO ``$`` / ``^`` / ``_`` / unbalanced ``\\`` in any rendered text.

Per §C.1 public surface contract (5 functions; consumed by T-A.6.2 cache
write-through + T-A.6.6 chart surface integration + T-A.6.6b exemplars
enhancement):

  - ``render_watchlist_thumbnail_svg``  (200x100; eager per-run)
  - ``render_ticker_detail_svg``        (800x500; eager per-run)
  - ``render_position_detail_svg``      (800x500; eager; fill markers)
  - ``render_market_weather_svg``       (400x150; per-pipeline-run)
  - ``render_theme2_annotated_svg``     (800x600; pattern-class-specific
                                         annotations from
                                         structural_evidence_json)

Per L8 LOCK (plan §B.7 + T3.SB2 hotfix ``cf3c489`` discipline): the
``_CHART_SURFACE_VALUES`` 5-tuple is imported from ``swing/data/models.py``
(canonical site); this module MUST NOT redefine the enum.
"""
from __future__ import annotations

import functools
import io
import json
import logging
import math
import threading
import zlib
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

# L8 LOCK: import canonical surface enum from swing/data/models.py — DO NOT
# redefine. Forward-binding from T3.SB2 hotfix at cf3c489 (4-surface-guard
# audit) + plan §B.7.
from swing.data.models import (  # noqa: F401  (re-export for downstream)
    _CHART_SURFACE_VALUES,
    Fill,
    PatternEvaluation,
    Trade,
)

# Matplotlib import is deferred + uses Agg backend so test/server processes
# avoid spawning a GUI toolkit. Mirror swing/rendering/charts.py pattern.
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
except ImportError as exc:  # pragma: no cover - install gate
    raise RuntimeError(
        "matplotlib is required for swing/web/charts.py; install via "
        "pip install -e \".[web]\""
    ) from exc

# Phase 14 SB3 T-3.2: mplfinance is a declared runtime dependency for the
# candlestick detail renderers. HARD-fail at import (mirror the matplotlib
# guard) — silent line-chart degradation would mask the very regression this
# sub-bundle fixes (close-line detail charts -> candlesticks).
try:
    import mplfinance as mpf  # noqa: E402
except ImportError as exc:  # pragma: no cover - install gate
    raise RuntimeError(
        "mplfinance is required for swing/web/charts.py candlestick "
        "rendering; install via pip install -e \".[web]\""
    ) from exc

logger = logging.getLogger(__name__)


def compute_chart_source_hash(bars: Any) -> str:
    """Content-derived value for ``chart_renders.source_data_hash``.

    Phase 16 Arc 3 (3c): the pipeline + JIT write sites previously stamped a
    STATIC literal (``"step_charts_v1"`` / ``"chart_jit_v1"``) which does not
    encode the underlying data, so the field never changed when a chart's bar
    history grew (e.g. a sparse 16-bar XMAX thumbnail vs a rich 207-bar render)
    or its window shifted. Keying on (bar count + first/last asof_date) makes
    the value honest: data growth → a different hash. VALUE-only change (no
    schema). The field remains a provenance/audit tag today; an honest value is
    the substrate for any future read-time hash-compare invalidation.

    ``bars`` is the legacy yfinance-shape frame (DatetimeIndex + capitalized
    OHLCV) the renderers consume. None / empty → a stable sentinel.

    The value combines bar count + first/last asof_date with a CRC32 over the
    Close column so two frames with the same count + endpoints but different
    bar VALUES (e.g. a yfinance re-fetch that drifts historical bars per the
    archive temporal-mutation gotcha) do NOT collide — making the field a
    genuine content token, not just a count/window token.
    """
    if bars is None or len(bars) == 0:
        return "bars=0"
    n = len(bars)
    first = bars.index[0]
    last = bars.index[-1]
    first_iso = first.date().isoformat() if hasattr(first, "date") else str(first)
    last_iso = last.date().isoformat() if hasattr(last, "date") else str(last)
    close_crc = 0
    if "Close" in getattr(bars, "columns", []):
        try:
            close_bytes = bars["Close"].to_numpy(dtype="float64").tobytes()
            close_crc = zlib.crc32(close_bytes) & 0xFFFFFFFF
        except Exception:  # noqa: BLE001 — provenance is best-effort; degrade to count/window
            close_crc = 0
    return f"bars={n};first={first_iso};last={last_iso};crc={close_crc:08x}"


# Process-wide matplotlib render lock. charts.py renders through pyplot GLOBAL
# state (matplotlib.pyplot as plt, mpf.plot, plt.subplots, plt.close) which is
# NOT thread-safe and has no other serialization. Every top-level web render
# path acquires this ONCE at its boundary (Codex R3 M#2 / R4 M#1: process-wide,
# not SB4-only). RLock (reentrant) so a helper that delegates to another
# serialized renderer on the same thread cannot self-deadlock (Codex R5 M#1).
_RENDER_LOCK = threading.RLock()


def _serialized_render(fn):
    """Serialize a top-level SVG renderer under the process-wide render lock."""
    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        with _RENDER_LOCK:
            return fn(*args, **kwargs)
    _wrapped._is_serialized_render = True  # marker for the coverage test
    return _wrapped


# Chart dimensions per spec §C.5 chart surface inventory.
_WATCHLIST_THUMBNAIL_SIZE_PX = (200, 100)
_TICKER_DETAIL_SIZE_PX = (800, 500)
_POSITION_DETAIL_SIZE_PX = (800, 500)
_MARKET_WEATHER_SIZE_PX = (400, 150)
_THEME2_ANNOTATED_SIZE_PX = (800, 600)

# matplotlib renders at 100 DPI by default; figsize is inches not pixels.
_DPI = 100


def _figsize_inches(px: tuple[int, int]) -> tuple[float, float]:
    return (px[0] / _DPI, px[1] / _DPI)


def _svg_bytes_from_fig(fig: Any) -> bytes:
    """Serialize a matplotlib Figure to raw SVG bytes (UTF-8)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _assert_ascii_only(text: str, *, field: str) -> str:
    """Defense-in-depth: ASCII-only text per L7 LOCK + spec §A.9.

    All chart text (titles, labels, annotations) flows through this helper
    at construction time. Non-ASCII glyphs raise immediately so a
    programming error surfaces in dev/test rather than mathtext-italicizing
    silently in a rendered SVG that ships to operator.

    NOTE: the ``$`` / ``^`` / ``_`` / ``\\`` mathtext-metacharacter gate is
    applied ONLY at suptitle/title text (via :func:`_assert_title_no_math`)
    because matplotlib mathtext interpretation fires inside ``$..$`` blocks
    at the title-render layer. In body-text rendered via ``ax.text(...)``
    with the default rcParams, ``_`` and ``^`` are literal characters
    (verified empirically) — so pattern-class slugs like ``flat_base`` are
    safe to emit via ``ax.text(...)``. The suptitle wrapper gates them
    defensively because future ``ax.set_title`` changes / rcParam shifts
    could re-enable math-mode in title text.
    """
    if not text.isascii():
        raise ValueError(
            f"chart text field {field!r} must be ASCII-only per spec "
            f"§A.9 mathtext LOCK; got {text!r}"
        )
    return text


def _assert_ticker_safe(ticker: str) -> str:
    """Ticker validator: ASCII + no mathtext metacharacters.

    Tickers flow into the suptitle on multiple renderers (hyp-rec /
    position-detail / theme2-annotated); reject ``$`` / ``^`` / ``_`` /
    ``\\`` at the renderer boundary so a malformed ticker can never reach
    the title layer.
    """
    _assert_ascii_only(ticker, field="ticker")
    for forbidden in ("$", "^", "_", "\\"):
        if forbidden in ticker:
            raise ValueError(
                f"ticker {ticker!r} contains matplotlib mathtext "
                f"metacharacter {forbidden!r}; tickers must be free of "
                "mathtext-active characters per L7 LOCK"
            )
    return ticker


def _assert_title_no_math(text: str, *, field: str) -> str:
    """Title-text gate: forbids ``$`` / ``^`` / ``_`` / ``\\`` per L7 LOCK.

    Applied at suptitle/title-render layer only. Pattern-class slugs that
    contain ``_`` (``flat_base`` / ``cup_with_handle`` / ``high_tight_flag``
    / ``double_bottom_w``) MUST NOT flow through this gate — emit them via
    :func:`ax.text` as body annotations instead.
    """
    _assert_ascii_only(text, field=field)
    for forbidden in ("$", "^", "_", "\\"):
        if forbidden in text:
            raise ValueError(
                f"chart title field {field!r} must not contain "
                f"matplotlib mathtext metacharacter {forbidden!r}; got "
                f"{text!r}"
            )
    return text


def _set_suptitle_no_math(fig: Any, title: str) -> None:
    """Apply suptitle with ``parse_math=False`` defense-in-depth per L7 LOCK."""
    _assert_title_no_math(title, field="suptitle")
    fig.suptitle(title, parse_math=False)


def _close_series(bars: pd.DataFrame) -> pd.Series:
    """Extract a 1-D Close series regardless of MultiIndex shape.

    Handles the yfinance ``group_by='column'`` MultiIndex DataFrame footgun
    (CLAUDE.md gotcha "yfinance group_by='column' now returns a MultiIndex
    column even for single-ticker calls"). Defense-in-depth even though
    chart renderers consume pre-normalized OhlcvCache output.
    """
    close = bars["Close"]
    if hasattr(close, "ndim") and close.ndim == 2:
        close = close.iloc[:, 0]
    return close


def _volume_series(bars: pd.DataFrame) -> pd.Series:
    if "Volume" not in bars.columns:
        return pd.Series([], dtype=float)
    vol = bars["Volume"]
    if hasattr(vol, "ndim") and vol.ndim == 2:
        vol = vol.iloc[:, 0]
    return vol


# ---------------------------------------------------------------------------
# Phase 14 SB3 T-3.2 — shared mplfinance candlestick infrastructure.
#
# The detail renderers (ticker_detail volume=True; theme2_annotated
# volume=False) route ALL OHLC bars through _normalize_ohlc_for_mpf
# (pre-plot barrier) -> _render_candles_fig (shared figure builder). Overlay
# coordinate mapping goes through _x_for_date so mpf's positional integer
# x-axis convention is coupled in exactly ONE place. MA overlay colors come
# ONLY from _MA_COLORS so the palette is identical across every surface
# (Expansion #10c uniformity).
# ---------------------------------------------------------------------------


class OhlcNormalizationError(ValueError):
    """OHLC frame failed the pre-plot normalization barrier.

    Raised with an ASCII-only message so a malformed frame surfaces as a
    typed error at the renderer boundary rather than a deep mplfinance
    KeyError mid-plot.
    """


# Okabe-Ito colorblind-safe palette, keyed by MA window. ASCII hex.
# Deliberately avoids #d62728/#2ca02c (reserved for risk/reward fills).
_MA_COLORS: dict[int, str] = {
    10:  "#0072B2",  # blue
    20:  "#E69F00",  # orange
    50:  "#009E73",  # bluish green
    150: "#CC79A7",  # reddish purple
    200: "#D55E00",  # vermillion
}

# mplfinance's lower volume panel ylabel — used to resolve the volume axis
# by ROLE (never a fixed index) on the returnfig axes list.
_MPF_VOLUME_YLABEL = "Volume"

_REQUIRED_OHLC_COLS = ("Open", "High", "Low", "Close")
_OHLC_TITLECASE_MAP = {
    "open": "Open", "high": "High", "low": "Low",
    "close": "Close", "volume": "Volume",
}


def _normalize_ohlc_for_mpf(bars: pd.DataFrame) -> pd.DataFrame:
    """Pre-plot barrier: coerce raw bars into the exact shape mplfinance needs.

    Output columns are Title-cased Open/High/Low/Close[/Volume] on an
    ascending, tz-naive, duplicate-deduped DatetimeIndex. Raises
    :class:`OhlcNormalizationError` (typed, ASCII messages) rather than
    letting a deep mplfinance ``KeyError`` surface mid-plot.

    Steps (spec C.1b):
      (a) flatten a SINGLE-ticker yfinance ``group_by='column'`` MultiIndex
          (Price x Ticker) by taking level 0; RAISE on >1 ticker.
      (b) Title-case columns to Open/High/Low/Close/Volume; RAISE on a
          Title-casing collision (e.g. both ``close`` and ``Close``).
      (c) sort index ascending.
      (d) drop duplicate timestamps keep='last'.
      (e) make index tz-naive.
      (f) RAISE if any required OHLC column is absent.

    The thumbnail/line renderer does NOT route through this barrier.
    """
    df = bars.copy()

    # (a) Single-ticker MultiIndex flatten.
    if isinstance(df.columns, pd.MultiIndex):
        if df.columns.nlevels < 2:
            raise OhlcNormalizationError(
                "MultiIndex columns must have a (Price, Ticker) shape"
            )
        tickers = df.columns.get_level_values(-1).unique()
        if len(tickers) > 1:
            raise OhlcNormalizationError(
                "cannot normalize a multi-ticker frame; got tickers "
                f"{[str(t) for t in tickers]} -- pass a single-ticker frame"
            )
        df.columns = df.columns.get_level_values(0)

    # (b) Title-case columns; reject collisions.
    rename: dict[Any, str] = {}
    target_sources: dict[str, list[str]] = {}
    for col in df.columns:
        key = str(col).lower()
        target = _OHLC_TITLECASE_MAP.get(key)
        if target is None:
            continue
        rename[col] = target
        target_sources.setdefault(target, []).append(str(col))
    for target, sources in target_sources.items():
        if len(sources) > 1:
            raise OhlcNormalizationError(
                f"Title-casing OHLC columns collides on {target!r}: "
                f"sources {sorted(sources)}"
            )
    df = df.rename(columns=rename)

    # (b2) coerce a non-DatetimeIndex to datetime BEFORE the sort/dedup/tz
    # steps. mplfinance assumes a DatetimeIndex; an object/string index would
    # otherwise fail in a deep mpf / get_loc error. Surface it here as a typed
    # ASCII error instead.
    if not isinstance(df.index, pd.DatetimeIndex):
        # A numeric (integer/float/RangeIndex) index is "datetime-coercible"
        # by pandas -- it becomes nanosecond timestamps near 1970-01-01,
        # producing a plausible-but-semantically-WRONG chart (and breaking
        # fill/window overlays that compare against real trade dates). Reject
        # it loudly rather than coercing numerics to epoch timestamps.
        if pd.api.types.is_numeric_dtype(df.index):
            raise OhlcNormalizationError(
                "OHLC index is numeric, not a date index"
            )
        try:
            df.index = pd.to_datetime(df.index)
        except (ValueError, TypeError) as exc:
            raise OhlcNormalizationError(
                "OHLC index is not datetime-coercible"
            ) from exc

    # NaT can survive coercion (None/blank/partial-invalid datetime-like
    # input) -- and a DatetimeIndex passed in directly may already carry NaT.
    # Downstream _x_for_fill_date assumes every index value has a comparable
    # .date(), so reject any NaT here.
    if df.index.isna().any():
        raise OhlcNormalizationError(
            "OHLC index contains unparseable/NaT dates"
        )

    # (c) sort ascending.
    df = df.sort_index()

    # (d) drop duplicate timestamps, keep last.
    df = df[~df.index.duplicated(keep="last")]

    # (e) make index tz-naive.
    idx = df.index
    if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
        df.index = idx.tz_localize(None)

    # (f) require OHLC columns.
    missing = [c for c in _REQUIRED_OHLC_COLS if c not in df.columns]
    if missing:
        raise OhlcNormalizationError(
            f"OHLC frame is missing required columns {missing}; "
            f"present columns are {list(df.columns)}"
        )

    return df


def _x_for_date(price_ax: Any, df: pd.DataFrame, target_date: Any) -> int:
    """Integer bar position for ``target_date`` on mpf's positional x-axis.

    ``df`` MUST be the SAME normalized frame passed to
    :func:`_render_candles_fig` (NOT raw bars). mplfinance candle plots
    render along a positional integer x-axis (bar 0..N-1), so overlay
    coordinates are bar indices, not date-locator coordinates. This is the
    single place coupled to mpf's coordinate convention.
    """
    return int(df.index.get_loc(pd.Timestamp(target_date)))


def _x_for_fill_date(df: pd.DataFrame, fill_date: date) -> int:
    """Nearest-forward-bar position for a FILL date on mpf's positional x-axis.

    Preserves the pre-candlestick behavior: fills on a non-trading-day /
    holiday / tz-shifted date (no exact daily bar) land on the NEXT trading
    bar, not dropped. Returns the first position ``i`` in ``df.index`` whose
    date is ``>= fill_date``; clamps to the last bar (``len - 1``) when the
    fill date is past the window. ``df`` MUST be the SAME normalized frame
    passed to :func:`_render_candles_fig`.

    NOTE: this is the FILL-marker placement rule ONLY. Exact-date overlays
    (the pattern_evaluation window band) keep using :func:`_x_for_date`.
    """
    return next(
        (i for i, ts in enumerate(df.index) if ts.date() >= fill_date),
        len(df.index) - 1,
    )


def _resolve_volume_ax(fig: Any, price_ax: Any) -> Any:
    """Resolve mpf's volume panel by ROLE, never a fixed axes index.

    mplfinance's axes count/order shifts with style/panels (and each panel
    has a twin sibling for the secondary y-axis). The volume panel
    advertises its role through its lower y-label, but mpf appends an
    auto-computed scale-factor suffix (e.g. ``"Volume  $10^{6}$"``), so an
    exact-equality check never fires on the real panel. We therefore match
    on a NORMALIZED y-label prefix: an axis whose configured y-label,
    stripped of surrounding whitespace and compared case-insensitively,
    starts with ``"Volume"``. This is the primary role mechanism.

    Only when no axis advertises a Volume label do we fall back to GEOMETRY:
    the lowest panel (smallest ``y0``) below the price axis. We do NOT
    explicitly skip twin axes — a twin shares its host's exact ``y0``, and
    the volume twin carries an empty y-label, so the role match selects the
    labelled (non-twin) volume panel directly; the geometry fallback relies
    on ``fig.axes`` insertion order placing the labelled panel ahead of its
    twin when ``y0`` values tie. Callers never touch ``axes[i]`` by position.
    """
    candidates = []
    for ax in fig.axes:
        if ax is price_ax:
            continue
        ylabel = ax.get_ylabel()
        candidates.append((ax, ylabel, ax.get_position().y0))
    # Primary: an axis whose y-label advertises the volume role. mpf appends
    # a scale-factor suffix, so match on a normalized prefix, not equality.
    for ax, ylabel, _y0 in candidates:
        if ylabel.strip().lower().startswith(_MPF_VOLUME_YLABEL.lower()):
            return ax
    # Secondary fallback: no axis advertises a Volume label — pick the lowest
    # panel (smallest y0) that sits below the price axis by geometry.
    price_y0 = price_ax.get_position().y0
    below = [c for c in candidates if c[2] < price_y0]
    if below:
        below.sort(key=lambda c: c[2])
        return below[0][0]
    return None


def _render_candles_fig(
    df: pd.DataFrame,
    *,
    ma_windows: tuple[int, ...],
    figsize: tuple[float, float],
    volume: bool = True,
    style: str = "yahoo",
) -> tuple[Any, Any, Any]:
    """Shared candlestick figure builder for the detail renderers.

    ``df`` MUST be :func:`_normalize_ohlc_for_mpf` output. Returns
    ``(fig, price_ax, vol_ax)`` where ``vol_ax is None`` when
    ``volume=False``. MA overlays draw close rolling means in
    ``_MA_COLORS`` (skip windows longer than the series; skip all-NaN).

    The volume axis is resolved by ROLE (see :func:`_resolve_volume_ax`);
    callers never index ``axes[i]``. Volume y-tick labels are stripped on
    the volume axis only; the price axis keeps its price ticks. A uniform
    grid (P14.N8) is enabled on the price axis.
    """
    close = df["Close"]
    if hasattr(close, "ndim") and close.ndim == 2:
        close = close.iloc[:, 0]

    addplots = []
    for window in ma_windows:
        if window not in _MA_COLORS:
            raise ValueError(
                f"no _MA_COLORS entry for MA window {window}; add it to "
                "the palette"
            )
        if window > len(close):
            continue
        sma = close.rolling(window).mean()
        if sma.isna().all():
            continue
        addplots.append(
            mpf.make_addplot(sma, color=_MA_COLORS[window], width=1.0)
        )

    plot_kwargs: dict[str, Any] = dict(
        type="candle",
        style=style,
        volume=volume,
        returnfig=True,
        figsize=figsize,
    )
    if addplots:
        plot_kwargs["addplot"] = addplots

    fig, axes = mpf.plot(df, **plot_kwargs)
    price_ax = axes[0]

    # mplfinance pads the positional x-axis with a wide date-tick-driven
    # margin (~7 bars each side on a 120-bar daily chart), leaving large
    # empty gutters and breaking the integer-extent contract (bars sit at
    # integer positions 0..N-1). Collapse the x-margin so the axis spans the
    # data tightly; bars remain at integer positions, overlays via
    # _x_for_date stay correct.
    price_ax.margins(x=0)

    vol_ax = None
    if volume:
        vol_ax = _resolve_volume_ax(fig, price_ax)
        if vol_ax is not None:
            # Strip volume y-tick labels (price ticks preserved on price_ax).
            vol_ax.set_yticklabels([])
            vol_ax.margins(x=0)

    # Uniform gridlines per P14.N8.
    price_ax.grid(True, alpha=0.3)

    return fig, price_ax, vol_ax


# ---------------------------------------------------------------------------
# 1. Watchlist row thumbnail (200x100; MA lines; volume)
# ---------------------------------------------------------------------------


@_serialized_render
def render_watchlist_thumbnail_svg(
    *, ticker: str, bars: pd.DataFrame, ma_lines: list[int]
) -> bytes:
    """Per spec §C.5 line 449 + plan §G.9 T-A.6.1: 200x100 thumbnail with
    MA lines + volume bars.

    No title text on a 200x100 thumbnail (too small to read); we omit the
    title entirely rather than risk mathtext leakage. Volume bars render
    in a slim lower sub-axes per the spec inventory volume requirement.
    """
    _assert_ticker_safe(ticker)
    close = _close_series(bars)
    volume = _volume_series(bars)
    fig, (ax_price, ax_vol) = plt.subplots(
        nrows=2, ncols=1,
        figsize=_figsize_inches(_WATCHLIST_THUMBNAIL_SIZE_PX),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    ax_price.plot(range(len(close)), close.values,
                  color="#1f77b4", linewidth=0.8)
    for window in ma_lines:
        if window <= 0 or window > len(close):
            continue
        sma = close.rolling(window).mean()
        ax_price.plot(range(len(sma)), sma.values, linewidth=0.6, alpha=0.7)
    ax_price.set_xticks([])
    ax_price.set_yticks([])
    ax_price.text(
        0.02, 0.92, ticker, transform=ax_price.transAxes,
        fontsize=8, color="#333", fontweight="bold",
    )
    # Volume bars per plan §C.5 line 449.
    if len(volume) > 0:
        ax_vol.bar(range(len(volume)), volume.values,
                   color="#888", width=1.0)
    ax_vol.set_xticks([])
    ax_vol.set_yticks([])
    # F-4 (Phase 14 close-out follow-on): hide the axes spines on BOTH sub-axes
    # so the hyp-rec / watchlist thumbnails have no black box border.
    for _spine in ax_price.spines.values():
        _spine.set_visible(False)
    for _spine in ax_vol.spines.values():
        _spine.set_visible(False)
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 2. Ticker detail chart (800x500; MA + volume + optional pattern boundaries)
#    Shared by BOTH the hyp-rec-expand caller AND the watchlist-expand caller
#    (single cached ticker_detail row); the suptitle is caller-agnostic.
# ---------------------------------------------------------------------------


@_serialized_render
def render_ticker_detail_svg(
    *, ticker: str, bars: pd.DataFrame,
    pattern_evaluation: PatternEvaluation | None = None,
) -> bytes:
    """Phase 14 SB3 T-3.2 (§C.2): 800x500 candlestick detail chart.

    Candlesticks (volume=True) with the uniform MA palette (10/20/50/150/200)
    via the shared :func:`_render_candles_fig` builder. Optional
    ``pattern_evaluation`` paints a window band using NORMALIZED positions
    via :func:`_x_for_date`. The suptitle stays neutral + caller-agnostic
    (the single cached ticker_detail row is read by both the hyp-rec-expand
    and watchlist-expand callers).
    """
    _assert_ticker_safe(ticker)
    # Normalize ONCE; pass the SAME df to the figure builder AND every
    # _x_for_date call (mpf positional-x coupling discipline).
    df = _normalize_ohlc_for_mpf(bars)
    close = _close_series(df)

    fig, price_ax, vol_ax = _render_candles_fig(
        df,
        ma_windows=(10, 20, 50, 150, 200),
        figsize=_figsize_inches(_TICKER_DETAIL_SIZE_PX),
        volume=True,
    )

    if pattern_evaluation is not None:
        # Pattern window boundaries as a vertical band (positions via the
        # normalized df, NOT raw bars).
        try:
            window_start = _x_for_date(
                price_ax, df, pattern_evaluation.window_start_date,
            )
        except (KeyError, TypeError):
            window_start = None
        try:
            window_end = _x_for_date(
                price_ax, df, pattern_evaluation.window_end_date,
            )
        except (KeyError, TypeError):
            window_end = None
        if window_start is not None and window_end is not None:
            price_ax.axvspan(window_start, window_end,
                             color="#ffeb3b", alpha=0.2,
                             label="pattern window")

    # Legend only when there are labeled artists (the candles + MA addplots
    # are unlabeled; the optional pattern-window band carries a label).
    handles, _labels = price_ax.get_legend_handles_labels()
    if handles:
        price_ax.legend(loc="upper left", fontsize=8)
    price_ax.set_ylabel("Price (USD)")
    _assert_ascii_only("Price (USD)", field="ylabel_price")
    if vol_ax is not None:
        vol_ax.set_ylabel("Volume")
        _assert_ascii_only("Volume", field="ylabel_vol")
    # KEEP the neutral, caller-agnostic suptitle. mpf renders `title=` as
    # fig.suptitle; we suppress mpf's title (none passed) and set our own
    # via _set_suptitle_no_math to avoid a duplicate suptitle.
    _set_suptitle_no_math(fig, f"{ticker} | last {len(close)} bars")
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 3. Position detail chart (800x500; fill markers + stop line + trail-MA)
#    Phase 14 SB3 T-3.3 (§C.3 / §C.3a): candlesticks + risk/reward zones.
# ---------------------------------------------------------------------------


def _rr_target_price(trade: Trade) -> float | None:
    """Absolute risk/reward target price, the inverse of the canonical r_mult formula.

    ``target = entry_price + planned_target_R * (entry_price - initial_stop)``

    This is a FIXED price locked at trade open (single-entry basis =
    ``trade.entry_price``; NO avg-fill in V1). Returns ``None`` when
    ``planned_target_R`` is unset (legacy / non-target trades) or the locked
    risk-unit ``(entry_price - initial_stop)`` is non-positive (invalid long
    shape — never invents an inverted target).
    """
    if trade.planned_target_R is None:
        return None
    r_unit = trade.entry_price - trade.initial_stop
    if r_unit <= 0:
        return None
    return trade.entry_price + trade.planned_target_R * r_unit


@_serialized_render
def render_position_detail_svg(
    *, ticker: str, bars: pd.DataFrame, trade: Trade,
    fills: list[Fill], current_stop: float | None,
) -> bytes:
    """Phase 14 SB3 T-3.3 (§C.3 / §C.3a): 800x500 candlestick position chart.

    Candlesticks (volume=True) with the uniform MA palette (10/20/50) via the
    shared :func:`_render_candles_fig` builder. Fill markers re-attach via the
    NORMALIZED df + :func:`_x_for_date` (mpf positional-x coupling). The
    ``current_stop`` axhline is preserved. risk/reward shaded zones
    (P14.N4) are drawn long-only (``stop < entry < target``); invalid shapes
    skip + WARN-log per-ticker, never raise.
    """
    _assert_ticker_safe(ticker)
    # Normalize ONCE; pass the SAME df to the figure builder AND every
    # _x_for_date call (mpf positional-x coupling discipline).
    df = _normalize_ohlc_for_mpf(bars)
    close = _close_series(df)

    fig, price_ax, vol_ax = _render_candles_fig(
        df,
        ma_windows=(10, 20, 50),
        figsize=_figsize_inches(_POSITION_DETAIL_SIZE_PX),
        volume=True,
    )

    # Fill markers (one per Fill row); positioned via NEAREST-FORWARD-bar
    # placement on the NORMALIZED df (:func:`_x_for_fill_date`). A fill on a
    # non-trading-day / holiday / tz-shifted date lands on the next trading
    # bar (clamped to the last bar if past the window), NOT dropped. Only a
    # fill whose fill_datetime can't be parsed at all is skipped.
    for fill in fills:
        try:
            fill_date = date.fromisoformat(fill.fill_datetime[:10])
        except (ValueError, TypeError, AttributeError):
            continue
        x = _x_for_fill_date(df, fill_date)
        marker = {"entry": "^", "exit": "v", "trim": "v", "stop": "x"}.get(
            fill.action, "o",
        )
        color = {"entry": "#2ca02c", "exit": "#d62728",
                 "trim": "#ff7f0e", "stop": "#d62728"}.get(
                     fill.action, "#888",
        )
        price_ax.scatter([x], [fill.price], marker=marker, color=color,
                         s=100, zorder=5, label=f"fill {fill.action}")

    # Current stop horizontal line.
    if current_stop is not None and current_stop > 0:
        price_ax.axhline(current_stop, color="#d62728", linestyle="--",
                         linewidth=0.8, alpha=0.7, label="current stop")

    # risk/reward shaded zones (P14.N4). Long-only V1: zones assume
    # stop < entry < target. Invalid/unsupported shapes skip + WARN; NEVER
    # raise; NEVER draw an inverted band. Off-range valid zones are DRAWN
    # (axhspan autoscales the y-axis), not silently hidden.
    _draw_risk_reward_zones(price_ax, ticker=ticker, trade=trade,
                     current_stop=current_stop)

    price_ax.set_ylabel("Price (USD)")
    _assert_ascii_only("Price (USD)", field="ylabel_price")
    if vol_ax is not None:
        vol_ax.set_ylabel("Volume")
        _assert_ascii_only("Volume", field="ylabel_vol")
    handles, _labels = price_ax.get_legend_handles_labels()
    if handles:
        price_ax.legend(loc="upper left", fontsize=7)
    _set_suptitle_no_math(
        fig, f"{trade.ticker} | position detail | last {len(close)} bars",
    )
    return _svg_bytes_from_fig(fig)


def _draw_risk_reward_zones(
    price_ax: Any, *, ticker: str, trade: Trade, current_stop: float | None,
) -> None:
    """Draw risk (entry->stop) + reward (entry->target) shaded zones.

    Per §C.3a. Risk zone drawn only when ``stop`` and ``entry`` are both
    present and ``stop < entry`` (valid long). Reward zone drawn only when a
    target is derivable and ``target > entry``. Invalid/unsupported shapes
    (short, ``stop >= entry``, ``target <= entry``, missing/zero entry/stop)
    skip + WARN-log per-ticker; never raise; never draw an inverted band.
    ASCII-only labels (the ``->`` arrow is ASCII).
    """
    entry = trade.entry_price
    stop = current_stop

    # Risk zone: entry -> stop (valid long requires stop < entry, both > 0).
    if (entry is not None and stop is not None and entry > 0 and stop > 0
            and stop < entry):
        label = _assert_ascii_only(
            "risk zone (entry->stop)", field="risk_zone_label",
        )
        price_ax.axhspan(stop, entry, color="#d62728", alpha=0.10,
                         label=label)
    else:
        logger.warning(
            "skipping risk zone for %s: invalid long shape "
            "(entry=%s, stop=%s); long-only V1 requires stop < entry",
            ticker, entry, stop,
        )

    # Reward zone: entry -> target (valid requires target > entry).
    target = _rr_target_price(trade)
    if target is not None and entry is not None and entry > 0 and target > entry:
        label = _assert_ascii_only(
            "reward zone (entry->target)", field="reward_zone_label",
        )
        price_ax.axhspan(entry, target, color="#2ca02c", alpha=0.10,
                         label=label)
    elif target is not None:
        logger.warning(
            "skipping reward zone for %s: invalid long shape "
            "(entry=%s, target=%s); long-only V1 requires target > entry",
            ticker, entry, target,
        )


# ---------------------------------------------------------------------------
# 4. Market weather mini-chart (400x150; S&P 500 + MA + trend badge)
# ---------------------------------------------------------------------------


@_serialized_render
def render_market_weather_svg(
    *, bars: pd.DataFrame, trend_template_state: str,
) -> bytes:
    """Phase 14 SB3 T-3.4 (§C.4): 400x150 candlestick market-weather chart.

    Candlesticks (volume=True) with MA50 + MA200 from the uniform palette
    via the shared :func:`_render_candles_fig` builder (gridlines per
    P14.N8 come from the helper). The trend-template state renders as an
    ASCII body-text badge via ``ax.text`` (underscore is LITERAL outside
    mathtext, so ``trend: stage_2`` is SAFE in body text — it would NOT be
    safe in a title). The real ``trend_template_state`` is computed at the
    call sites (pipeline + interactive refresh) via
    :func:`swing.patterns.foundation.current_stage` (§C.4a); this renderer
    is state-agnostic.
    """
    _assert_ascii_only(trend_template_state, field="trend_template_state")
    df = _normalize_ohlc_for_mpf(bars)
    fig, price_ax, _vol_ax = _render_candles_fig(
        df,
        ma_windows=(50, 200),
        figsize=_figsize_inches(_MARKET_WEATHER_SIZE_PX),
        volume=True,
    )
    price_ax.text(
        0.02, 0.88, f"trend: {trend_template_state}",
        transform=price_ax.transAxes,
        fontsize=9, color="#222", fontweight="bold",
    )
    _set_suptitle_no_math(fig, "Market weather (SP500 daily)")
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 5. Theme 2 annotated chart (800x600; per-pattern annotations from
#    structural_evidence_json) — per spec §4.6 + §C.4 LOCK.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AnnotationContext:
    """Pure-function evidence holder for per-pattern annotation drawing."""
    pattern_class: str
    evidence: dict[str, Any]


def _annotate_vcp(ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame) -> None:
    """VCP: contraction sequence markers + pivot horizontal line."""
    pivot = ctx.evidence.get("pivot_price")
    if isinstance(pivot, (int, float)) and not math.isnan(float(pivot)):
        ax.axhline(float(pivot), color="#9467bd", linestyle="-",
                   linewidth=1.0, alpha=0.8, label="pivot")
    contractions = ctx.evidence.get("contractions") or []
    if isinstance(contractions, list):
        for i, ctr in enumerate(contractions):
            if not isinstance(ctr, dict):
                continue
            depth = ctr.get("depth_pct")
            if not isinstance(depth, (int, float)):
                continue
            # Phase 14 close-out (A-2): anchor INWARD at x=0.74 (was 0.98) so
            # the stacked contraction labels clear the right price-tick column.
            # Stays ha="right"; mathtext-free ("pct", no $/^/_).
            ax.text(
                0.74, 0.92 - i * 0.05,
                f"contraction {i + 1}: {depth:.1f}pct",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right",
            )


def _annotate_flat_base(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """Flat base: top/bottom horizontal lines + duration label."""
    top = ctx.evidence.get("range_top_price")
    bottom = ctx.evidence.get("range_bottom_price")
    if isinstance(top, (int, float)):
        ax.axhline(float(top), color="#2ca02c", linestyle="--",
                   linewidth=0.8, alpha=0.7, label="top of range")
    if isinstance(bottom, (int, float)):
        ax.axhline(float(bottom), color="#d62728", linestyle="--",
                   linewidth=0.8, alpha=0.7, label="bottom of range")
    duration = ctx.evidence.get("base_duration_days")
    if isinstance(duration, int):
        ax.text(0.98, 0.92, f"duration: {duration} days",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right")


def _annotate_cup_with_handle(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """CWH: cup edges + handle markers + depth ratio."""
    depth = ctx.evidence.get("cup_depth_pct")
    if isinstance(depth, (int, float)):
        ax.text(0.98, 0.92, f"depth ratio: {depth:.2f}",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right")
    cup_bottom = ctx.evidence.get("cup_bottom_price")
    if isinstance(cup_bottom, (int, float)):
        ax.axhline(float(cup_bottom), color="#9467bd", linestyle=":",
                   linewidth=0.8, alpha=0.7, label="cup bottom")


def _annotate_high_tight_flag(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """HTF: pole markers + consolidation box + days-tight."""
    days_tight = ctx.evidence.get("consolidation_duration_days")
    if isinstance(days_tight, int):
        ax.text(0.98, 0.92, f"days tight: {days_tight}",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right")
    pole_pct = ctx.evidence.get("pole_pct")
    if isinstance(pole_pct, (int, float)):
        ax.text(0.98, 0.87, f"pole advance: {pole_pct:.1f}pct",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right")


def _annotate_double_bottom_w(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """DBW: trough_1 + center_peak + trough_2 markers + optional undercut."""
    for key, label, color in (
        ("trough_1_price", "trough 1", "#d62728"),
        ("center_peak_price", "center peak", "#9467bd"),
        ("trough_2_price", "trough 2", "#d62728"),
    ):
        val = ctx.evidence.get(key)
        if isinstance(val, (int, float)):
            ax.axhline(float(val), color=color, linestyle=":",
                       linewidth=0.8, alpha=0.7, label=label)
    undercut = ctx.evidence.get("undercut")
    if isinstance(undercut, bool) and undercut:
        ax.text(0.98, 0.92, "undercut: yes",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right")


_ANNOTATORS = {
    "vcp": _annotate_vcp,
    "flat_base": _annotate_flat_base,
    "cup_with_handle": _annotate_cup_with_handle,
    "high_tight_flag": _annotate_high_tight_flag,
    "double_bottom_w": _annotate_double_bottom_w,
}


@_serialized_render
def render_theme2_annotated_svg(
    *, ticker: str, bars: pd.DataFrame,
    pattern_evaluation: PatternEvaluation,
    exemplar_thumbnails: list[bytes] | None = None,
) -> bytes:
    """Per spec §4.6 + §C.4 LOCK: full annotated chart with per-pattern
    structural evidence overlays from ``structural_evidence_json``.

    Reused at T-A.6.3 review form + T-A.6.6b exemplars enhancement.

    ``exemplar_thumbnails`` is accepted (per §C.4 top-3 historical-base
    overlay contract) but V1 renders them as a noted summary rather than
    embedding inline SVG-in-SVG (deferred to V2 per spec §C.6).
    """
    _assert_ticker_safe(ticker)
    # Phase 14 SB3 T-3.2 (§C.5): candlesticks with volume=False so the
    # single-axis _annotate_* layout is preserved. Normalize ONCE; pass the
    # SAME df to the figure builder AND every _x_for_date call.
    df = _normalize_ohlc_for_mpf(bars)
    fig, ax, _vol_ax = _render_candles_fig(
        df,
        ma_windows=(10, 20, 50, 150, 200),
        figsize=_figsize_inches(_THEME2_ANNOTATED_SIZE_PX),
        volume=False,
    )  # _vol_ax is None

    pattern_class = pattern_evaluation.pattern_class
    try:
        evidence = json.loads(pattern_evaluation.structural_evidence_json)
    except (ValueError, TypeError):
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    annotator = _ANNOTATORS.get(pattern_class)
    if annotator is not None:
        ctx = _AnnotationContext(pattern_class=pattern_class, evidence=evidence)
        annotator(ax, ctx, bars)

    # Pattern window vertical band (positions via the normalized df).
    try:
        window_start = _x_for_date(
            ax, df, pattern_evaluation.window_start_date,
        )
    except (KeyError, TypeError):
        window_start = None
    try:
        window_end = _x_for_date(
            ax, df, pattern_evaluation.window_end_date,
        )
    except (KeyError, TypeError):
        window_end = None
    if window_start is not None and window_end is not None:
        ax.axvspan(window_start, window_end,
                   color="#ffeb3b", alpha=0.15)

    # Top-3 exemplar thumbnails — V1 footnote only.
    if exemplar_thumbnails:
        ax.text(0.98, 0.02,
                f"top-{len(exemplar_thumbnails)} historical bases",
                transform=ax.transAxes, fontsize=7, color="#555",
                ha="right")

    # Legend only when an annotator added labeled artists (some annotators
    # emit only ax.text overlays with no legend handle).
    handles, _labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper left", fontsize=7)
    ax.set_ylabel("Price (USD)")
    # Per L7 LOCK: pattern-class slugs like flat_base / cup_with_handle /
    # high_tight_flag / double_bottom_w contain ``_`` and MUST NOT flow
    # through the suptitle (which gates mathtext metacharacters). Render
    # the slug via ax.text() body annotation instead — matplotlib treats
    # ``_`` as literal in body text outside math mode.
    ax.text(
        0.98, 0.95, pattern_class,
        transform=ax.transAxes, fontsize=10, color="#222",
        ha="right", fontweight="bold",
    )
    title = (
        f"{ticker} | pattern overlay | composite "
        f"{pattern_evaluation.composite_score:.2f}"
    )
    _set_suptitle_no_math(fig, title)
    return _svg_bytes_from_fig(fig)
