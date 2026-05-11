"""Chart rendering — mplfinance, optional. Pipeline degrades gracefully."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

CHART_LOOKBACK_DAYS = 120
CONSOLIDATION_DAYS = 10
MIN_BARS = CONSOLIDATION_DAYS + 1


class ChartingUnavailableError(RuntimeError):
    """mplfinance not installed — pipeline should set charts_status='skipped'."""


@dataclass(frozen=True)
class PatternOverlay:
    """Algo-derived pole/flag region + algo-pivot for chart annotation.

    Distinct from the candidate-pivot hline already drawn by render_chart.
    Spec §3.4. Phase 6 paints (was Phase 3 no-op stub).

    Coordinate contract (V1): the date fields are mapped to integer bar
    positions (0..N-1) at render time via render_chart's `_bar_idx` helper.
    mpf candle plots render along a positional x-axis, not a true date axis.
    Out-of-window dates clamp to the chart's left/right edge (see _bar_idx).
    """
    pattern: str
    confidence: float
    pole_start_date: date
    pole_end_date: date
    flag_start_date: date
    flag_end_date: date
    pivot: float

    @classmethod
    def from_classification(cls, r) -> PatternOverlay | None:
        """Build from a FlagClassificationResult; returns None when not detected."""
        if not r.detected or r.pattern != "flag":
            return None
        return cls(
            pattern="flag", confidence=r.confidence,
            pole_start_date=r.pole_start_date, pole_end_date=r.pole_end_date,
            flag_start_date=r.flag_start_date, flag_end_date=r.flag_end_date,
            pivot=r.pivot,
        )


def _build_chart_title(*, ticker: str, pivot: float, stop: float | None) -> str:
    """Build the ticker + pivot/stop segment of the chart title.

    Spec §A: when stop is None or <= 0, the `stop X.XX` segment is omitted
    entirely (avoids matplotlib auto-scaling y-axis to include zero).
    Per CLAUDE.md mathtext gotcha, NO `$`, `^`, `_`, or unbalanced `\\` in
    the format — those metacharacters trigger mathtext interpretation and
    silently italicize / consume glyphs.

    The caller (render_chart) appends the `| last N bars` suffix and any
    pattern-overlay segment.
    """
    parts = [ticker, f"pivot {pivot:.2f}"]
    if stop is not None and stop > 0.0:
        parts.append(f"stop {stop:.2f}")
    return " | ".join(parts)


def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float | None,
    output_path: Path,
    pattern_overlay: PatternOverlay | None = None,
) -> Path | None:
    """Render a daily chart with SMAs 10/20/50 + pivot/stop hlines + consolidation marker.

    Returns the output path on success, None if data is too short.
    Raises ChartingUnavailableError if mplfinance isn't installed (caller handles).

    When `pattern_overlay` is non-None, paints pole + flag fill_betweenx
    bands plus an algo-pivot horizontal segment spanning only the flag
    region, and appends `| flag (<conf>)` to the title (spec §3.4).
    The candidate-pivot/stop hline pair (legacy) is preserved in both cases.
    """
    try:
        import matplotlib.pyplot as plt
        import mplfinance as mpf
    except ImportError as exc:
        raise ChartingUnavailableError("mplfinance not installed") from exc

    df = ohlcv.tail(CHART_LOOKBACK_DAYS).copy()
    if len(df) < MIN_BARS:
        return None

    addplots = []
    closes = df["Close"]
    for window, color in ((10, "blue"), (20, "orange"), (50, "red")):
        sma = closes.rolling(window).mean()
        if not sma.isna().all():
            addplots.append(mpf.make_addplot(sma, color=color, width=1.0))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Omit `$` from the title because matplotlib's mathtext interpreter
    # treats paired `$..$` as math mode, italicizing intervening text and
    # consuming the `$` glyphs. The `\$` escape (commit `2fd0ecc`) does
    # NOT prevent math-mode entry — matplotlib resolves `\$` to a literal
    # `$` BEFORE the math-mode parse pass. Trading context implies the
    # values are dollars; the labels "pivot" / "stop" carry the meaning.
    # Spec §A: stop segment omitted when stop is None or <= 0 (_build_chart_title).
    title = _build_chart_title(
        ticker=ticker, pivot=pivot, stop=stop,
    ) + f" | last {len(df)} bars"
    if pattern_overlay is not None:
        title += f" | flag ({pattern_overlay.confidence:.2f})"

    # hlines + colors must stay length-aligned (spec §A: omit stop when None/0).
    _hlines_list = [pivot]
    _hlines_colors = ["green"]
    if stop is not None and stop > 0.0:
        _hlines_list.append(stop)
        _hlines_colors.append("red")

    plot_kwargs = dict(
        type="candle", volume=True, style="yahoo",
        figsize=(11, 6),
        title=title,
        ylabel_lower="Volume",
        addplot=addplots,
        hlines=dict(hlines=_hlines_list, colors=_hlines_colors, linestyle="--"),
        vlines=dict(vlines=[df.index[-CONSOLIDATION_DAYS]],
                    colors=["purple"], linestyle=":", alpha=0.5),
    )

    if pattern_overlay is None:
        mpf.plot(
            df,
            savefig=dict(fname=str(output_path), dpi=100, bbox_inches="tight"),
            **plot_kwargs,
        )
        return output_path

    fig, axes = mpf.plot(df, returnfig=True, **plot_kwargs)
    price_ax = axes[0]
    # Note: mpf renders `title=` as fig.suptitle (NOT axes[0].title); do not
    # set_title here — it would create a duplicate visible title. Read via
    # fig._suptitle (or fig.texts) instead. (Internal review fix, commit 803607e.)
    # V1 design contract (approved Phase 6): overlay placement uses integer
    # bar positions, NOT date-axis coordinates. mpf candle plots render
    # along a positional integer x-axis (bar 0, bar 1, ..., bar N-1), even
    # though `df.index` is a DatetimeIndex. The brief's hint about
    # "matplotlib auto-converts via the date locator" applies to line/area
    # plots, not candles — empirically verified during Phase 6 implementation.
    # Consequence: if mpf changes its candle x-axis to true datetime
    # coordinates in a future version, this code AND the tests asserting
    # specific integer extents (e.g., (80, 100), (101, 119)) MUST be
    # updated together. The integer-extent assertions are intentional
    # — they pin the contract — and are NOT a hidden coupling to
    # implementation details.
    bar_dates = [d.date() if hasattr(d, "date") else d for d in df.index]

    def _bar_idx(d: date) -> int:
        # Map an overlay date to the index of the first bar whose date >= d.
        # Two clamp behaviors, both intentional:
        # - LEFT-truncation: if d falls BEFORE the first bar in the window
        #   (every bar.date >= d → returns 0), the band starts at the chart's
        #   left edge. Visually represents the visible portion of an overlay
        #   whose start date precedes the lookback window.
        # - RIGHT-truncation: if d falls AFTER the last bar (no bar.date >= d
        #   → returns len(bar_dates)-1), the band collapses to zero width at
        #   the chart's right edge. Visually represents an overlay whose end
        #   date extends past the lookback window.
        # Both behaviors render partially-out-of-window classifications as
        # "snapped to edge" rather than dropped entirely; operator can see
        # the visible portion of the pattern in either case.
        for i, bd in enumerate(bar_dates):
            if bd >= d:
                return i
        return len(bar_dates) - 1

    pole_start_i = _bar_idx(pattern_overlay.pole_start_date)
    pole_end_i = _bar_idx(pattern_overlay.pole_end_date)
    flag_start_i = _bar_idx(pattern_overlay.flag_start_date)
    flag_end_i = _bar_idx(pattern_overlay.flag_end_date)
    # Algo-pivot horizontal segment drawn first so matplotlib autoscales
    # around it before we capture the y-range for fill_betweenx — avoids
    # bands being frozen to pre-hlines limits if pivot is near the axis edge.
    price_ax.hlines(
        y=pattern_overlay.pivot, xmin=flag_start_i, xmax=flag_end_i,
        colors="darkblue", linestyles="-", linewidth=1.5,
    )
    # Pole + flag bands via fill_betweenx (spec §3.4) — vertical stripes
    # spanning the full autoscaled y-range across the band's bar positions.
    # y-range captured AFTER hlines so bands span the post-autoscale axis.
    y_lo, y_hi = price_ax.get_ylim()
    price_ax.fill_betweenx(
        [y_lo, y_hi], pole_start_i, pole_end_i, alpha=0.15, color="green",
    )
    price_ax.fill_betweenx(
        [y_lo, y_hi], flag_start_i, flag_end_i, alpha=0.15, color="yellow",
    )
    fig.savefig(str(output_path), dpi=100, bbox_inches="tight")
    plt.close(fig)
    return output_path
