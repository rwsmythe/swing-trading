"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Path to a fresh temp SQLite DB (no schema applied)."""
    return tmp_path / "test.db"


@pytest.fixture
def ohlcv_factory():
    """Factory for building synthetic daily OHLCV DataFrames."""
    def _make(
        closes: list[float],
        *,
        start_date: str = "2026-01-02",
        volume: int = 1_000_000,
    ) -> pd.DataFrame:
        idx = pd.bdate_range(start=start_date, periods=len(closes))
        df = pd.DataFrame(
            {
                "Open": closes,
                "High": [c * 1.01 for c in closes],
                "Low": [c * 0.99 for c in closes],
                "Close": closes,
                "Volume": [volume] * len(closes),
            },
            index=idx,
        )
        return df

    return _make
