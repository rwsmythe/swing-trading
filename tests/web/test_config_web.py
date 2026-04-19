"""Web config section parses with defaults + partial overrides."""
from __future__ import annotations

from pathlib import Path

from swing.config import Web, load


def _write_cfg(project_dir: Path, home_dir: Path, *, extra: str = "") -> Path:
    cfg = project_dir / "swing.config.toml"
    cfg.write_text(
        f"""[paths]
db_path = "{(home_dir / 'swing.db').as_posix()}"
data_dir = "{home_dir.as_posix()}"
logs_dir = "{(home_dir / 'logs').as_posix()}"
charts_dir = "{(home_dir / 'charts').as_posix()}"
backups_dir = "{(home_dir / 'backups').as_posix()}"
prices_cache_dir = "{(home_dir / 'prices').as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1000.0
starting_date = "2026-01-01"
risk_equity_floor = 5000.0

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
{extra}
""",
        encoding="utf-8",
    )
    (project_dir / "reference").mkdir(exist_ok=True)
    (project_dir / "reference" / "rs-universe.csv").write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\nAAPL\n",
        encoding="utf-8",
    )
    return cfg


def test_web_defaults_when_section_absent(tmp_path: Path):
    (tmp_path / "project").mkdir(exist_ok=True)
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    assert isinstance(cfg.web, Web)
    assert cfg.web.host == "127.0.0.1"
    assert cfg.web.port == 8080
    assert cfg.web.reload is False
    assert cfg.web.price_cache_ttl_seconds == 120
    assert cfg.web.price_fetch_timeout_seconds == 3
    assert cfg.web.price_fetch_deadline_seconds == 6
    assert cfg.web.max_concurrent_price_fetches == 8
    assert cfg.web.circuit_breaker_cooldown_seconds == 60
    assert cfg.web.polling_interval_seconds == 2


def test_web_partial_override(tmp_path: Path):
    (tmp_path / "project").mkdir(exist_ok=True)
    cfg_path = _write_cfg(
        tmp_path / "project", tmp_path / "home",
        extra='[web]\nport = 9090\nreload = true\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.port == 9090
    assert cfg.web.reload is True
    # Unspecified fields still at default
    assert cfg.web.host == "127.0.0.1"
    assert cfg.web.price_cache_ttl_seconds == 120
