"""StopAdvisoryConfig cfg-key extensions for 3e.8 Bundle 2 (§4.B + §4.D)."""
from __future__ import annotations

from pathlib import Path

from swing.config import StopAdvisoryConfig, load


def test_stop_advisory_config_rejects_zero_trim_first_r_trigger():
    """Codex R2 Major #1 — defense against pathological TOML override."""
    import pytest
    with pytest.raises(ValueError, match="trim_first_r_trigger"):
        StopAdvisoryConfig(trim_first_r_trigger=0.0)


def test_stop_advisory_config_rejects_negative_trim_first_r_trigger():
    import pytest
    with pytest.raises(ValueError, match="trim_first_r_trigger"):
        StopAdvisoryConfig(trim_first_r_trigger=-1.0)


def test_stop_advisory_config_rejects_zero_trim_first_pct_default():
    import pytest
    with pytest.raises(ValueError, match="trim_first_pct_default"):
        StopAdvisoryConfig(trim_first_pct_default=0.0)


def test_stop_advisory_config_rejects_over_one_trim_first_pct_default():
    """1.5 ≡ 'trim 150% of position', nonsensical."""
    import pytest
    with pytest.raises(ValueError, match="trim_first_pct_default"):
        StopAdvisoryConfig(trim_first_pct_default=1.5)


def test_stop_advisory_config_rejects_zero_parabolic_adr_multiple():
    import pytest
    with pytest.raises(ValueError, match="parabolic_adr_multiple"):
        StopAdvisoryConfig(parabolic_adr_multiple=0.0)


def test_stop_advisory_config_rejects_negative_parabolic_adr_multiple():
    import pytest
    with pytest.raises(ValueError, match="parabolic_adr_multiple"):
        StopAdvisoryConfig(parabolic_adr_multiple=-1.0)


def test_stop_advisory_config_rejects_nan_trim_first_r_trigger():
    """Codex R3 Major #1 — `nan <= 0` is False so a bare comparison lets
    NaN sneak past. Without isfinite, `r < nan` is False and trim_into_strength
    fires on EVERY untrimmed trade."""
    import math
    import pytest
    with pytest.raises(ValueError, match="trim_first_r_trigger"):
        StopAdvisoryConfig(trim_first_r_trigger=math.nan)


def test_stop_advisory_config_rejects_inf_trim_first_r_trigger():
    import math
    import pytest
    with pytest.raises(ValueError, match="trim_first_r_trigger"):
        StopAdvisoryConfig(trim_first_r_trigger=math.inf)


def test_stop_advisory_config_rejects_nan_trim_first_pct_default():
    import math
    import pytest
    with pytest.raises(ValueError, match="trim_first_pct_default"):
        StopAdvisoryConfig(trim_first_pct_default=math.nan)


def test_stop_advisory_config_rejects_nan_parabolic_adr_multiple():
    """NaN parabolic_adr_multiple → threshold = nan → `extension_pct < nan`
    is False → fires for any price above sma50."""
    import math
    import pytest
    with pytest.raises(ValueError, match="parabolic_adr_multiple"):
        StopAdvisoryConfig(parabolic_adr_multiple=math.nan)


def test_stop_advisory_config_rejects_inf_parabolic_adr_multiple():
    import math
    import pytest
    with pytest.raises(ValueError, match="parabolic_adr_multiple"):
        StopAdvisoryConfig(parabolic_adr_multiple=math.inf)


def test_stop_advisory_config_has_trim_first_r_trigger_default():
    cfg = StopAdvisoryConfig()
    assert cfg.trim_first_r_trigger == 1.0


def test_stop_advisory_config_has_trim_first_pct_default():
    cfg = StopAdvisoryConfig()
    assert cfg.trim_first_pct_default == 0.25


def test_stop_advisory_config_has_parabolic_adr_multiple_default():
    cfg = StopAdvisoryConfig()
    assert cfg.parabolic_adr_multiple == 7.0


def test_stop_advisory_config_round_trip_with_overrides(tmp_path: Path):
    """Operator-supplied overrides in swing.config.toml flow into the
    dataclass. Mirrors the existing config-loader pattern (absent ⇒
    defaults; present ⇒ overrides)."""
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
breakeven_r_trigger = 1.0
trail_10ma_buffer_pct = 0.3
trail_20ma_buffer_pct = 0.3
time_stop_days = 10
time_stop_min_r = 0.5
trim_first_r_trigger = 1.5
trim_first_pct_default = 0.33
parabolic_adr_multiple = 8.5
"""
    p = tmp_path / "swing.config.toml"
    p.write_text(cfg_text)
    cfg = load(p)
    assert cfg.stop_advisory.trim_first_r_trigger == 1.5
    assert cfg.stop_advisory.trim_first_pct_default == 0.33
    assert cfg.stop_advisory.parabolic_adr_multiple == 8.5


def test_stop_advisory_config_round_trip_uses_defaults_when_absent(tmp_path: Path):
    """Bundle 2's new cfg keys default when [stop_advisory] omits them."""
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
    assert cfg.stop_advisory.trim_first_r_trigger == 1.0
    assert cfg.stop_advisory.trim_first_pct_default == 0.25
    assert cfg.stop_advisory.parabolic_adr_multiple == 7.0
