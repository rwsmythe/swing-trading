"""StopAdvisoryConfig cfg-key extension for 3e.8 Bundle 3 (§M.2).

Mirrors the Bundle 2 validator-discrimination pattern at
``tests/test_config_stop_advisory_bundle2.py``: each pathological input
(zero, negative, NaN, inf) gets a discriminating test.
"""
from __future__ import annotations

from pathlib import Path

from swing.config import StopAdvisoryConfig, load


def test_stop_advisory_config_has_tighten_at_r_multiple_default():
    cfg = StopAdvisoryConfig()
    assert cfg.tighten_at_r_multiple == 2.0


def test_stop_advisory_config_rejects_zero_tighten_at_r_multiple():
    import pytest
    with pytest.raises(ValueError, match="tighten_at_r_multiple"):
        StopAdvisoryConfig(tighten_at_r_multiple=0.0)


def test_stop_advisory_config_rejects_negative_tighten_at_r_multiple():
    import pytest
    with pytest.raises(ValueError, match="tighten_at_r_multiple"):
        StopAdvisoryConfig(tighten_at_r_multiple=-1.0)


def test_stop_advisory_config_rejects_nan_tighten_at_r_multiple():
    """Codex R3 Major #1 pattern — `nan <= 0` is False so a bare comparison
    lets NaN sneak past. Without isfinite, `r >= nan` is False and the
    rule never fires; a discriminating test pins the isfinite guard."""
    import math
    import pytest
    with pytest.raises(ValueError, match="tighten_at_r_multiple"):
        StopAdvisoryConfig(tighten_at_r_multiple=math.nan)


def test_stop_advisory_config_rejects_inf_tighten_at_r_multiple():
    import math
    import pytest
    with pytest.raises(ValueError, match="tighten_at_r_multiple"):
        StopAdvisoryConfig(tighten_at_r_multiple=math.inf)


def test_stop_advisory_config_round_trip_with_tighten_override(tmp_path: Path):
    """Operator-supplied override in swing.config.toml flows into the
    dataclass."""
    cfg_text = """
[paths]
db_path = "swing.db"
data_dir = "data"
logs_dir = "logs"
charts_dir = "charts"
backups_dir = "backups"
prices_cache_dir = "prices_cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "data/rs_universe.csv"

[account]
starting_equity = 10000.0
starting_date = "2026-04-01"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 5
hard_cap_open = 10

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 0.30
adr_min_pct = 0.04
pullback_max_pct = 0.25
proximity_max_pct = 0.05
tightness_days_required = 3
tightness_range_factor = 0.04
orderliness_max_bar_ratio = 1.5
orderliness_max_range_cv = 0.5

[trend_template]
min_passes = 7
allowed_miss_names = []
rising_ma_period_days = 21
high_52w_margin_pct = 0.25
low_52w_min_pct = 0.30

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 0.30

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.5
adr = 0.3
prior_trend = 0.2

[stop_advisory]
tighten_at_r_multiple = 2.5
"""
    p = tmp_path / "swing.config.toml"
    p.write_text(cfg_text)
    cfg = load(p)
    assert cfg.stop_advisory.tighten_at_r_multiple == 2.5


def test_stop_advisory_config_round_trip_uses_default_when_absent(tmp_path: Path):
    """When ``tighten_at_r_multiple`` is omitted from [stop_advisory], the
    dataclass default (2.0) applies."""
    cfg_text = """
[paths]
db_path = "swing.db"
data_dir = "data"
logs_dir = "logs"
charts_dir = "charts"
backups_dir = "backups"
prices_cache_dir = "prices_cache"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "data/rs_universe.csv"

[account]
starting_equity = 10000.0
starting_date = "2026-04-01"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 5
hard_cap_open = 10

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 0.30
adr_min_pct = 0.04
pullback_max_pct = 0.25
proximity_max_pct = 0.05
tightness_days_required = 3
tightness_range_factor = 0.04
orderliness_max_bar_ratio = 1.5
orderliness_max_range_cv = 0.5

[trend_template]
min_passes = 7
allowed_miss_names = []
rising_ma_period_days = 21
high_52w_margin_pct = 0.25
low_52w_min_pct = 0.30

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 0.30

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.5
adr = 0.3
prior_trend = 0.2
"""
    p = tmp_path / "swing.config.toml"
    p.write_text(cfg_text)
    cfg = load(p)
    assert cfg.stop_advisory.tighten_at_r_multiple == 2.0
