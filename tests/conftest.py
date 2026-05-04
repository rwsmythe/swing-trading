"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from swing.data.models import Trade


def make_trade(
    *,
    id: int | None = None,
    ticker: str = "AAA",
    entry_date: str = "2026-01-01",
    entry_price: float = 10.0,
    initial_shares: int = 100,
    initial_stop: float = 9.0,
    current_stop: float = 9.0,
    status: str = "open",
    state: str = "entered",
    watchlist_entry_target: float | None = None,
    watchlist_initial_stop: float | None = None,
    notes: str | None = None,
    **overrides,
) -> Trade:
    """Canonical Trade fixture builder for the test corpus.

    Phase 7 Sub-A T0 introduced this builder. Both `status` and `state` are
    accepted as kwargs during the A.0–A.3 dual-field transition window; T3
    drops `status` from the Trade dataclass and the canonical signature
    will be updated to remove it.
    """
    return Trade(
        id=id,
        ticker=ticker,
        entry_date=entry_date,
        entry_price=entry_price,
        initial_shares=initial_shares,
        initial_stop=initial_stop,
        current_stop=current_stop,
        status=status,
        state=state,
        watchlist_entry_target=watchlist_entry_target,
        watchlist_initial_stop=watchlist_initial_stop,
        notes=notes,
        **overrides,
    )


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


@pytest.fixture
def sample_config(tmp_path):
    """Minimal valid Config for criterion tests."""
    from swing.config import load

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(
        """[paths]
db_path = "swing-data/swing.db"
data_dir = "swing-data"
logs_dir = "swing-data/logs"
charts_dir = "swing-data/charts"
backups_dir = "swing-data/backups"
prices_cache_dir = "swing-data/prices-cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8_rs_rank"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
""",
        encoding="utf-8",
    )
    return load(cfg_path)
