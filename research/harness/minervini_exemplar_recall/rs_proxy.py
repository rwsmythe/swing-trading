# research/harness/minervini_exemplar_recall/rs_proxy.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from swing.config import Config
from swing.evaluation.context import BatchContext

from .ohlcv_reader import slice_to


@dataclass(frozen=True)
class RsProxyOutcome:
    batch: BatchContext
    rs_path: str  # "P0" | "P1"
    excess: float | None  # exemplar trailing-H return minus SPY's; None under P1


def _trailing_return(bars: pd.DataFrame, horizon_bars: int) -> float:
    close = bars["Close"]
    return float(close.iloc[-1]) / float(close.iloc[-(horizon_bars + 1)]) - 1.0


def build_batch(
    *,
    ticker: str,
    exemplar_sliced: pd.DataFrame,
    spy_full: pd.DataFrame,
    session: date,
    config: Config,
) -> RsProxyOutcome:
    horizon = config.rs.horizon_weeks * 5  # 60 for default config
    need = horizon + 1  # 61 bars to compute a trailing-60 return
    spy_sliced = slice_to(spy_full, session) if spy_full is not None else None

    p0_ok = (
        len(exemplar_sliced) >= need
        and spy_sliced is not None
        and len(spy_sliced) >= need
    )

    if p0_ok:
        r_ex = _trailing_return(exemplar_sliced, horizon)
        r_spy = _trailing_return(spy_sliced, horizon)
        batch = BatchContext(
            returns_12w_by_ticker={ticker: r_ex},
            universe_tickers=(),  # empty -> ticker outside universe -> compute_rs uses fallback_spy
            universe_version="minervini-recall-p0",
            universe_hash="",
            spy_return_12w=r_spy,
        )
        return RsProxyOutcome(batch=batch, rs_path="P0", excess=r_ex - r_spy)

    # P1 degenerate: empty returns dict (NO ticker key) -> compute_rs returns 'unavailable'
    # before it ever reads spy_return. A stray SPY value can never promote TT8.
    batch = BatchContext(
        returns_12w_by_ticker={},
        universe_tickers=(),
        universe_version="minervini-recall-p1",
        universe_hash="",
        spy_return_12w=0.0,
    )
    return RsProxyOutcome(batch=batch, rs_path="P1", excess=None)
