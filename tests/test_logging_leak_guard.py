from __future__ import annotations

import os
from pathlib import Path

# Captured at MODULE IMPORT, before any monkeypatch fixture applies -> the REAL
# operator home. (conftest fixtures are function-scoped and apply per-test.)
_REAL_HOME = Path(
    os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
)


def test_suite_does_not_resolve_logs_to_real_home():
    from swing.config import _resolve_path, _user_home

    # The autouse redirect fixture must be active: _user_home() is NOT the real
    # operator home. Discriminator: WITHOUT the fixture, _user_home() == _REAL_HOME
    # and this assertion FAILS.
    redirected = _user_home()
    assert redirected != _REAL_HOME

    # And a relative logs_dir resolves UNDER the redirected (tmp) home, never the
    # real ~/swing-data/logs.
    resolved = _resolve_path("swing-data/logs", redirected, Path("/proj"))
    real_logs = _REAL_HOME / "swing-data" / "logs"
    assert resolved != real_logs
    assert str(real_logs) not in str(resolved)


def test_create_app_writes_weblog_under_tmp_not_real_home(tmp_path, monkeypatch):
    # A cfg with a RELATIVE logs_dir (the leak shape) + create_app must write
    # web.log under the redirected home, never the operator's real logs dir.
    import logging
    from logging.handlers import RotatingFileHandler

    import swing.integrations.schwab.client as schwab_client
    from swing.config import _user_home
    from swing.web.app import create_app

    # Build a sample_config-style cfg with a relative logs_dir.
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_RELATIVE_LOGS_TOML, encoding="utf-8")
    from swing.config import load
    cfg = load(cfg_path)

    root = logging.getLogger()
    saved = list(root.handlers)
    # create_app routes through install_logging (sets root level + installs the
    # Schwab LogRecord factory) -> snapshot/restore ALL global logging state.
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        create_app(cfg, cfg_path)
        real_weblog = _REAL_HOME / "swing-data" / "logs" / "web.log"
        # The handler target must be under the redirected home, not the real one.
        targets = [
            h.baseFilename for h in root.handlers if isinstance(h, RotatingFileHandler)
        ]
        assert targets, "create_app attached no web.log handler"
        for t in targets:
            assert str(real_weblog) != t
            assert str(_user_home()) in t
    finally:
        for h in list(root.handlers):
            if isinstance(h, RotatingFileHandler):
                h.close()
            root.removeHandler(h)
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)
        logging.setLogRecordFactory(saved_factory)
        schwab_client._GLOBAL_KNOWN_SECRETS.clear()
        schwab_client._GLOBAL_KNOWN_SECRETS.update(saved_secrets)


_RELATIVE_LOGS_TOML = '''[paths]
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
'''
