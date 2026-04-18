"""Chart rendering — mplfinance, optional. Pipeline degrades gracefully."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CHART_LOOKBACK_DAYS = 120
CONSOLIDATION_DAYS = 10
MIN_BARS = CONSOLIDATION_DAYS + 1


class ChartingUnavailable(RuntimeError):
    """mplfinance not installed — pipeline should set charts_status='skipped'."""


def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float,
    output_path: Path,
) -> Path | None:
    """Render a daily chart with SMAs 10/20/50 + pivot/stop hlines + consolidation marker.

    Returns the output path on success, None if data is too short.
    Raises ChartingUnavailable if mplfinance isn't installed (caller handles).
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
