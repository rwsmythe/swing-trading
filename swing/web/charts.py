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
  - ``render_hyprec_detail_svg``        (800x500; eager per-run)
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

import io
import json
import math
from dataclasses import dataclass
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

# Chart dimensions per spec §C.5 chart surface inventory.
_WATCHLIST_THUMBNAIL_SIZE_PX = (200, 100)
_HYPREC_DETAIL_SIZE_PX = (800, 500)
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
# 1. Watchlist row thumbnail (200x100; MA lines; volume)
# ---------------------------------------------------------------------------


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
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 2. Hyp-rec detail chart (800x500; MA + volume + optional pattern boundaries)
# ---------------------------------------------------------------------------


def render_hyprec_detail_svg(
    *, ticker: str, bars: pd.DataFrame,
    pattern_evaluation: PatternEvaluation | None = None,
) -> bytes:
    _assert_ticker_safe(ticker)
    close = _close_series(bars)
    volume = _volume_series(bars)

    fig, (ax_price, ax_vol) = plt.subplots(
        nrows=2, ncols=1,
        figsize=_figsize_inches(_HYPREC_DETAIL_SIZE_PX),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    ax_price.plot(range(len(close)), close.values, color="#1f77b4",
                  linewidth=1.0, label="Close")
    for window, color in ((50, "#ff7f0e"), (150, "#2ca02c"), (200, "#d62728")):
        if window <= len(close):
            sma = close.rolling(window).mean()
            ax_price.plot(range(len(sma)), sma.values, color=color,
                          linewidth=0.8, alpha=0.8,
                          label=f"MA{window}")
    if pattern_evaluation is not None:
        # Pattern window boundaries as vertical band.
        try:
            window_start = bars.index.get_loc(
                pd.Timestamp(pattern_evaluation.window_start_date)
            )
        except (KeyError, TypeError):
            window_start = None
        try:
            window_end = bars.index.get_loc(
                pd.Timestamp(pattern_evaluation.window_end_date)
            )
        except (KeyError, TypeError):
            window_end = None
        if window_start is not None and window_end is not None:
            ax_price.axvspan(window_start, window_end,
                             color="#ffeb3b", alpha=0.2,
                             label="pattern window")
    if len(volume) > 0:
        ax_vol.bar(range(len(volume)), volume.values, color="#888")
    # Phase 13 T-T4.SB.5 Item 3: strip volume y-tick labels (ylabel preserved).
    ax_vol.set_yticks([])
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.set_ylabel("Price (USD)")
    ax_vol.set_ylabel("Volume")
    _assert_ascii_only("Price (USD)", field="ylabel_price")
    _assert_ascii_only("Volume", field="ylabel_vol")
    _set_suptitle_no_math(fig, f"{ticker} | hyp-rec detail | last {len(close)} bars")
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 3. Position detail chart (800x500; fill markers + stop line + trail-MA)
# ---------------------------------------------------------------------------


def render_position_detail_svg(
    *, ticker: str, bars: pd.DataFrame, trade: Trade,
    fills: list[Fill], current_stop: float | None,
) -> bytes:
    _assert_ticker_safe(ticker)
    close = _close_series(bars)
    fig, ax = plt.subplots(figsize=_figsize_inches(_POSITION_DETAIL_SIZE_PX))
    ax.plot(range(len(close)), close.values, color="#1f77b4",
            linewidth=1.0, label="Close")
    # MA50 for trail context.
    if len(close) >= 50:
        sma = close.rolling(50).mean()
        ax.plot(range(len(sma)), sma.values, color="#ff7f0e",
                linewidth=0.8, alpha=0.8, label="MA50")
    # Fill markers (one per Fill row); positioned at the fill date if present
    # in the bar window, else clamped to right edge.
    bar_dates = [d.date() if hasattr(d, "date") else d for d in bars.index]
    for fill in fills:
        try:
            fill_date = pd.Timestamp(fill.fill_datetime).date()
        except (ValueError, AttributeError):
            continue
        x = next((i for i, bd in enumerate(bar_dates) if bd >= fill_date),
                 len(bar_dates) - 1)
        marker = {"entry": "^", "exit": "v", "trim": "v", "stop": "x"}.get(
            fill.action, "o",
        )
        color = {"entry": "#2ca02c", "exit": "#d62728",
                 "trim": "#ff7f0e", "stop": "#d62728"}.get(
                     fill.action, "#888",
        )
        ax.scatter([x], [fill.price], marker=marker, color=color,
                   s=100, zorder=5, label=f"fill {fill.action}")
    # Current stop horizontal line.
    if current_stop is not None and current_stop > 0:
        ax.axhline(current_stop, color="#d62728", linestyle="--",
                   linewidth=0.8, alpha=0.7, label="current stop")
    ax.set_ylabel("Price (USD)")
    ax.legend(loc="upper left", fontsize=7)
    _set_suptitle_no_math(
        fig, f"{trade.ticker} | position detail | last {len(close)} bars",
    )
    return _svg_bytes_from_fig(fig)


# ---------------------------------------------------------------------------
# 4. Market weather mini-chart (400x150; S&P 500 + MA + trend badge)
# ---------------------------------------------------------------------------


def render_market_weather_svg(
    *, bars: pd.DataFrame, trend_template_state: str,
) -> bytes:
    """Per spec §C.5 line 452: market weather mini-chart with MA50 + MA200
    + volume bars + trend-template state badge.
    """
    _assert_ascii_only(trend_template_state, field="trend_template_state")
    close = _close_series(bars)
    volume = _volume_series(bars)
    fig, (ax_price, ax_vol) = plt.subplots(
        nrows=2, ncols=1,
        figsize=_figsize_inches(_MARKET_WEATHER_SIZE_PX),
        gridspec_kw={"height_ratios": [3, 1]},
        sharex=True,
    )
    ax_price.plot(range(len(close)), close.values,
                  color="#1f77b4", linewidth=0.8)
    for window, color in ((50, "#ff7f0e"), (200, "#d62728")):
        if window <= len(close):
            sma = close.rolling(window).mean()
            ax_price.plot(range(len(sma)), sma.values, color=color,
                          linewidth=0.6, alpha=0.8)
    ax_price.set_xticks([])
    ax_price.text(
        0.02, 0.88, f"trend: {trend_template_state}",
        transform=ax_price.transAxes,
        fontsize=9, color="#222", fontweight="bold",
    )
    # Volume bars per plan §C.5 line 452.
    if len(volume) > 0:
        ax_vol.bar(range(len(volume)), volume.values,
                   color="#888", width=1.0)
    ax_vol.set_xticks([])
    # Phase 13 T-T4.SB.5 Item 3: strip volume y-tick labels.
    ax_vol.set_yticks([])
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
            ax.text(
                0.02, 0.92 - i * 0.05,
                f"contraction {i + 1}: {depth:.1f}pct",
                transform=ax.transAxes, fontsize=8, color="#222",
            )


def _annotate_flat_base(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """Flat base: top/bottom horizontal lines + duration label."""
    top = ctx.evidence.get("top_of_range")
    bottom = ctx.evidence.get("bottom_of_range")
    if isinstance(top, (int, float)):
        ax.axhline(float(top), color="#2ca02c", linestyle="--",
                   linewidth=0.8, alpha=0.7, label="top of range")
    if isinstance(bottom, (int, float)):
        ax.axhline(float(bottom), color="#d62728", linestyle="--",
                   linewidth=0.8, alpha=0.7, label="bottom of range")
    duration = ctx.evidence.get("duration_days")
    if isinstance(duration, int):
        ax.text(0.02, 0.92, f"duration: {duration} days",
                transform=ax.transAxes, fontsize=8, color="#222")


def _annotate_cup_with_handle(
    ax: Any, ctx: _AnnotationContext, bars: pd.DataFrame
) -> None:
    """CWH: cup edges + handle markers + depth ratio."""
    depth = ctx.evidence.get("depth_ratio")
    if isinstance(depth, (int, float)):
        ax.text(0.02, 0.92, f"depth ratio: {depth:.2f}",
                transform=ax.transAxes, fontsize=8, color="#222")
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
        ax.text(0.02, 0.92, f"days tight: {days_tight}",
                transform=ax.transAxes, fontsize=8, color="#222")
    pole_pct = ctx.evidence.get("pole_advance_pct")
    if isinstance(pole_pct, (int, float)):
        ax.text(0.02, 0.86, f"pole advance: {pole_pct:.1f}pct",
                transform=ax.transAxes, fontsize=8, color="#222")


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
        ax.text(0.02, 0.92, "undercut: yes",
                transform=ax.transAxes, fontsize=8, color="#222")


_ANNOTATORS = {
    "vcp": _annotate_vcp,
    "flat_base": _annotate_flat_base,
    "cup_with_handle": _annotate_cup_with_handle,
    "high_tight_flag": _annotate_high_tight_flag,
    "double_bottom_w": _annotate_double_bottom_w,
}


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
    close = _close_series(bars)
    fig, ax = plt.subplots(figsize=_figsize_inches(_THEME2_ANNOTATED_SIZE_PX))
    ax.plot(range(len(close)), close.values, color="#1f77b4",
            linewidth=1.0, label="Close")
    for window, color in ((50, "#ff7f0e"), (150, "#2ca02c"), (200, "#d62728")):
        if window <= len(close):
            sma = close.rolling(window).mean()
            ax.plot(range(len(sma)), sma.values, color=color,
                    linewidth=0.6, alpha=0.7, label=f"MA{window}")

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

    # Pattern window vertical band.
    try:
        window_start = bars.index.get_loc(
            pd.Timestamp(pattern_evaluation.window_start_date)
        )
    except (KeyError, TypeError):
        window_start = None
    try:
        window_end = bars.index.get_loc(
            pd.Timestamp(pattern_evaluation.window_end_date)
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
