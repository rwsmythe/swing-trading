"""Input contexts for criteria. Criteria are pure functions of these."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from swing.config import Config


@dataclass(frozen=True)
class BatchContext:
    """Cross-sectional context shared across all tickers in an evaluation run."""

    returns_12w_by_ticker: dict[str, float]
    universe_tickers: tuple[str, ...]
    universe_version: str
    universe_hash: str
    spy_return_12w: float


@dataclass(frozen=True)
class MarketContext:
    """External market state. Phase 1: minimal; Phase 2 adds weather."""

    # Reserved for future expansion
    pass


@dataclass(frozen=True)
class CandidateContext:
    """Everything a criterion needs to evaluate one ticker."""

    ticker: str
    ohlcv: pd.DataFrame
    config: Config
    batch: BatchContext
    market: MarketContext
    current_equity: float
