"""Tests for swing.config."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Web, load


def _write_default_toml(path: Path, *, db_path_override: str | None = None) -> Path:
    """Write a full valid config to path; used by path-resolution tests."""
    db = db_path_override or "swing-data/swing.db"
    path.write_text(
        f"""[paths]
db_path = "{db}"
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
    return path


def test_load_reads_toml_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")
    cfg = load(cfg_file)
    assert cfg.account.starting_equity == 1200.0
    assert cfg.vcp.adr_min_pct == 4.0
    assert cfg.trend_template.min_passes == 7
    assert cfg.rs.benchmark_ticker == "SPY"


def test_paths_resolves_relative_to_user_home(tmp_path: Path, monkeypatch):
    """Relative paths in [paths] are resolved against USERPROFILE (Win) or HOME (Unix)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")
    cfg = load(cfg_file)
    assert cfg.paths.db_path == tmp_path / "swing-data" / "swing.db"
    assert cfg.paths.logs_dir == tmp_path / "swing-data" / "logs"


def test_paths_absolute_not_rewritten(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    abs_db = tmp_path / "absolute" / "swing.db"
    # Use POSIX form so backslashes don't trigger TOML string escapes on Windows
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml", db_path_override=abs_db.as_posix())
    cfg = load(cfg_file)
    assert cfg.paths.db_path == abs_db


def test_project_internal_paths_resolve_against_project_root(tmp_path: Path, monkeypatch):
    """data/, exports/, reference/ paths resolve against project root (config file's dir)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    cfg_file = _write_default_toml(project_dir / "swing.config.toml")
    cfg = load(cfg_file)
    # rs_universe_path is "reference/rs-universe.csv" → project-internal
    assert cfg.paths.rs_universe_path == project_dir / "reference" / "rs-universe.csv"
    # finviz_inbox_dir is "data/finviz-inbox" → project-internal
    assert cfg.paths.finviz_inbox_dir == project_dir / "data" / "finviz-inbox"
    # exports_dir is "exports" → project-internal
    assert cfg.paths.exports_dir == project_dir / "exports"


def test_load_raises_on_missing_section(tmp_path: Path):
    cfg_file = tmp_path / "swing.config.toml"
    cfg_file.write_text("[paths]\ndb_path = \"x\"\n", encoding="utf-8")
    with pytest.raises(KeyError) as exc:
        load(cfg_file)
    assert "account" in str(exc.value).lower() or "section" in str(exc.value).lower()


def test_pipeline_config_chart_top_n_watch_default_is_10():
    """Spec §D — chart_top_n_watch default raised 5 → 10 in chart-scope
    policy v2 (2026-04-27).

    Discriminating verification: pre-fix returns 5; post-fix returns 10.
    Asserting on the exact value catches both directions of regression.
    """
    from swing.config import PipelineConfig
    cfg = PipelineConfig()
    assert cfg.chart_top_n_watch == 10


def test_archive_config_defaults_to_5y_trading_days(tmp_path: Path, monkeypatch):
    """`Config.archive.archive_history_days` defaults to 1260 (5y trading days)
    when no [archive] section is present in swing.config.toml.

    Discriminating: under the pre-fix tree, `cfg.archive` raises
    AttributeError. Under a regressed default (e.g., silently 252 or 504),
    Task 3's helper would truncate the retained history window.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")

    cfg = load(cfg_file)
    assert cfg.archive.archive_history_days == 1260


def test_archive_config_honors_toml_override(tmp_path: Path, monkeypatch):
    """If [archive] archive_history_days is set in the toml, it overrides the
    Python default — matches the dataclass-default-shadowing behavior of all
    other Config sections (lesson `aeb2084` 2026-04-28)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")
    # Append [archive] override to the existing valid toml.
    with cfg_file.open("a", encoding="utf-8") as fh:
        fh.write("\n[archive]\narchive_history_days = 504\n")

    cfg = load(cfg_file)
    assert cfg.archive.archive_history_days == 504


def test_web_db_busy_timeout_default():
    # SQLite lock-contention arc (OQ-A): the runtime-tunable busy_timeout knob.
    assert Web().db_busy_timeout_ms == 30000


def test_web_db_busy_timeout_from_toml(tmp_path: Path, monkeypatch):
    # The template has no [web] table (load uses raw.get("web", {})); append one
    # carrying the knob, mirroring the [archive] append-and-load pattern above.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_file = _write_default_toml(tmp_path / "swing.config.toml")
    with cfg_file.open("a", encoding="utf-8") as fh:
        fh.write("\n[web]\ndb_busy_timeout_ms = 12000\n")

    cfg = load(cfg_file)
    assert cfg.web.db_busy_timeout_ms == 12000
