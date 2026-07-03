"""19-B Task 4 -- the explicit config-derived project_root + the comms-root source.

load() stamps cfg.project_root = config_path.parent.resolve(); config_project_root
prefers that explicit field (never exports_dir.parent) and RAISES when it is unset
(Codex R5 -- no silent divergence). _comms_root_for derives comms from it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import config_project_root, load
from swing.monitoring.research_health import (
    _comms_root_for,
    _default_comms_root,
)

_CFG_TEXT = """[paths]
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
"""


def _write_cfg(tmp_path) -> Path:
    p = tmp_path / "swing.config.toml"
    p.write_text(_CFG_TEXT, encoding="utf-8")
    return p


class _StubCfg:
    def __init__(self, project_root, exports_dir):
        self.project_root = project_root

        class _P:
            pass

        self.paths = _P()
        self.paths.exports_dir = exports_dir


def test_load_sets_project_root(tmp_path):
    cfg = load(_write_cfg(tmp_path))
    assert cfg.project_root == tmp_path.resolve()


def test_config_project_root_prefers_explicit(tmp_path):
    # exports_dir.parent (/other) != project_root (/p) -> the accessor MUST return
    # the explicit /p, proving it never infers from exports_dir (Codex R1 MAJOR).
    cfg = _StubCfg(Path("/p"), Path("/other/exports"))
    assert config_project_root(cfg) == Path("/p")


def test_config_project_root_raises_without_project_root():
    cfg = _StubCfg(None, Path("/x/exports"))
    with pytest.raises(ValueError):
        config_project_root(cfg)


def test_comms_root_for_derives_from_project_root(tmp_path):
    cfg = _StubCfg(tmp_path / "p", tmp_path / "p" / "exports")
    assert _comms_root_for(cfg) == tmp_path / "p" / "comms"


def test_default_comms_root_unchanged_fallback():
    # The __file__ fallback (cfg-less callers) is intact: <repo>/comms.
    import swing.monitoring.research_health as rh
    assert _default_comms_root() == Path(rh.__file__).resolve().parents[2] / "comms"


def test_apply_overrides_preserves_project_root(tmp_path):
    # apply_overrides returns dataclasses.replace(cfg, ...) which copies unlisted
    # fields -> project_root survives (Codex R3 MAJOR verified-not-a-vector); the
    # comms root cannot split from the artifact path under overrides.
    from swing.config_overrides import apply_overrides
    cfg = load(_write_cfg(tmp_path))
    overridden = apply_overrides(cfg)
    assert config_project_root(overridden) == tmp_path.resolve()
