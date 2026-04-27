"""Chart rendering — mplfinance, optional. Pipeline degrades gracefully."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

CHART_LOOKBACK_DAYS = 120
CONSOLIDATION_DAYS = 10
MIN_BARS = CONSOLIDATION_DAYS + 1


class ChartingUnavailable(RuntimeError):
    """mplfinance not installed — pipeline should set charts_status='skipped'."""


@dataclass(frozen=True)
class PatternOverlay:
    """Algo-derived pole/flag region + algo-pivot for chart annotation.

    Distinct from the candidate-pivot hline already drawn by render_chart.
    Spec §3.4. Phase 6 paints (was Phase 3 no-op stub).
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


def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float,
    output_path: Path,
    pattern_overlay: PatternOverlay | None = None,
) -> Path | None:
    """Render a daily chart with SMAs 10/20/50 + pivot/stop hlines + consolidation marker.

    Returns the output path on success, None if data is too short.
    Raises ChartingUnavailable if mplfinance isn't installed (caller handles).

    When `pattern_overlay` is non-None, paints pole + flag fill_betweenx
    bands plus an algo-pivot horizontal segment spanning only the flag
    region, and appends `| flag (<conf>)` to the title (spec §3.4).
    The candidate-pivot/stop hline pair (legacy) is preserved in both cases.
    """
    try:
        import mplfinance as mpf
    except ImportError as exc:
        raise ChartingUnavailable("mplfinance not installed") from exc

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

    title = f"{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars"
    if pattern_overlay is not None:
        title += f" | flag ({pattern_overlay.confidence:.2f})"

    plot_kwargs = dict(
        type="candle", volume=True, style="yahoo",
        figsize=(11, 6),
        title=title,
        ylabel_lower="Volume",
        addplot=addplots,
        hlines=dict(hlines=[pivot, stop], colors=["green", "red"], linestyle="--"),
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
    # mpf renders `title` as a fig.suptitle, leaving axes[0] title empty.
    # Mirror the title onto the price axes so downstream consumers (and the
    # discriminating overlay test) can read the annotation directly off the
    # axes — keeps the visible suptitle unchanged.
    price_ax.set_title(title)
    # Convert overlay dates to integer x-positions in the bar index — mpf
    # uses positional integers on the x-axis (not timestamps) for candle
    # plots, so we map each overlay date to its bar position.
    bar_dates = [d.date() if hasattr(d, "date") else d for d in df.index]

    def _bar_idx(d: date) -> int:
        # First bar whose date >= d; falls back to last bar if d > last.
        for i, bd in enumerate(bar_dates):
            if bd >= d:
                return i
        return len(bar_dates) - 1

    pole_start_i = _bar_idx(pattern_overlay.pole_start_date)
    pole_end_i = _bar_idx(pattern_overlay.pole_end_date)
    flag_start_i = _bar_idx(pattern_overlay.flag_start_date)
    flag_end_i = _bar_idx(pattern_overlay.flag_end_date)
    # Pole + flag bands via fill_betweenx (spec §3.4) — vertical stripes
    # spanning the price axis y-range across the band's bar positions.
    y_lo, y_hi = price_ax.get_ylim()
    price_ax.fill_betweenx(
        [y_lo, y_hi], pole_start_i, pole_end_i, alpha=0.15, color="green",
    )
    price_ax.fill_betweenx(
        [y_lo, y_hi], flag_start_i, flag_end_i, alpha=0.15, color="yellow",
    )
    # Algo-pivot horizontal segment — only spans flag region (distinct from
    # the existing candidate-pivot hline which spans the full chart).
    price_ax.hlines(
        y=pattern_overlay.pivot, xmin=flag_start_i, xmax=flag_end_i,
        colors="darkblue", linestyles="-", linewidth=1.5,
    )
    fig.savefig(str(output_path), dpi=100, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return output_path
