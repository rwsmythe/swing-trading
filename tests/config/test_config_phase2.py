"""Phase 2 config sections load with defaults + overrides."""
from __future__ import annotations

from pathlib import Path

from swing.config import load


def test_phase2_defaults_load_when_sections_absent(tmp_path: Path):
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
    cfg = load(cfg_path)

    assert cfg.near_trigger.above_pct == 0.5
    assert cfg.near_trigger.below_pct == 1.0
    assert cfg.stop_advisory.breakeven_r_trigger == 1.0
    assert cfg.stop_advisory.trail_10ma_buffer_pct == 0.3
    assert cfg.stop_advisory.trail_20ma_buffer_pct == 0.3
    assert cfg.stop_advisory.time_stop_days == 10
    assert cfg.sizing.position_pct_cap == 0.15
    assert cfg.pipeline.stale_lease_threshold_seconds == 300
    assert cfg.pipeline.stale_step_threshold_seconds == 900
    assert cfg.pipeline.heartbeat_interval_seconds == 30
    assert cfg.export.size_cap_kb == 500
    assert cfg.export.retain_markdown_sibling is True
    assert cfg.export.retention_days == 90


def test_phase2_overrides_apply(tmp_path: Path):
    base = (tmp_path / "swing.config.toml")
    base.write_text(
        """[paths]
db_path = "x.db"
data_dir = "x"
logs_dir = "x/logs"
charts_dir = "x/charts"
backups_dir = "x/backups"
prices_cache_dir = "x/cache"
finviz_inbox_dir = "x/inbox"
exports_dir = "x/exports"
rs_universe_path = "x/rs.csv"

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

[near_trigger]
above_pct = 0.7
below_pct = 1.5

[pipeline]
heartbeat_interval_seconds = 60
""",
        encoding="utf-8",
    )
    cfg = load(base)
    assert cfg.near_trigger.above_pct == 0.7
    assert cfg.near_trigger.below_pct == 1.5
    assert cfg.pipeline.heartbeat_interval_seconds == 60
    assert cfg.stop_advisory.breakeven_r_trigger == 1.0
