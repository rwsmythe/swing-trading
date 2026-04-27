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
    Spec §3.4. Phase 3 wires the kwarg as a no-op stub; Phase 6 paints.
    """
    pattern: str
    confidence: float
    pole_start_date: date
    pole_end_date: date
    flag_start_date: date
    flag_end_date: date
    pivot: float

    @classmethod
    def from_classification(cls, r) -> "PatternOverlay | None":
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
    pattern_overlay: "PatternOverlay | None" = None,
) -> Path | None:
    """Render a daily chart with SMAs 10/20/50 + pivot/stop hlines + consolidation marker.

    Returns the output path on success, None if data is too short.
    Raises ChartingUnavailable if mplfinance isn't installed (caller handles).

    `pattern_overlay` is a Phase 3 no-op stub — Phase 6 will paint the
    pole/flag region + algo-pivot when non-None.
    """
    del pattern_overlay  # Phase 3: accept kwarg but do not paint (Phase 6 owns).
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
    mpf.plot(
        df, type="candle", volume=True, style="yahoo",
        figsize=(11, 6),
        title=f"{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars",
        ylabel_lower="Volume",
        addplot=addplots,
        hlines=dict(hlines=[pivot, stop], colors=["green", "red"], linestyle="--"),
        vlines=dict(vlines=[df.index[-CONSOLIDATION_DAYS]], colors=["purple"], linestyle=":", alpha=0.5),
        savefig=dict(fname=str(output_path), dpi=100, bbox_inches="tight"),
    )
    return output_path
