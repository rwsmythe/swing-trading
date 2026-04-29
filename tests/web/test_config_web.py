"""Web config section parses with defaults + partial overrides."""
from __future__ import annotations

from pathlib import Path

import pytest

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


def test_web_config_has_csv_upload_max_bytes_default():
    """Phase 3c §3.1: Web.csv_upload_max_bytes defaults to 10 MB."""
    from swing.config import Web
    w = Web()
    assert w.csv_upload_max_bytes == 10 * 1024 * 1024


def test_web_config_csv_upload_max_bytes_parsed_from_toml(tmp_path: Path):
    """Phase 3c §3.1: [web] csv_upload_max_bytes = N in TOML → cfg.web.csv_upload_max_bytes == N.
    Follows the same two-dir pattern as existing partial-override tests in this file."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _write_cfg(
        project, home,
        extra='[web]\ncsv_upload_max_bytes = 5242880\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.csv_upload_max_bytes == 5242880


def test_web_config_has_ohlcv_cache_ttl_seconds_default():
    """Phase 3d §3.7: Web.ohlcv_cache_ttl_seconds defaults to 3600."""
    from swing.config import Web
    w = Web()
    assert w.ohlcv_cache_ttl_seconds == 3600


def test_web_config_has_max_concurrent_ohlcv_fetches_default():
    """Phase 3d §3.7: Web.max_concurrent_ohlcv_fetches defaults to 8."""
    from swing.config import Web
    w = Web()
    assert w.max_concurrent_ohlcv_fetches == 8


def test_web_config_ohlcv_fields_parsed_from_toml(tmp_path: Path):
    """Phase 3d §3.7: TOML overrides land on the cfg."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _write_cfg(
        project, home,
        extra='[web]\nohlcv_cache_ttl_seconds = 1800\nmax_concurrent_ohlcv_fetches = 4\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.ohlcv_cache_ttl_seconds == 1800
    assert cfg.web.max_concurrent_ohlcv_fetches == 4


def test_config_web_chase_factor_default_is_one_percent():
    """Spec §3.1 — Config.web.chase_factor default = 0.01 (1%).

    Sourced from the 2026-04-25 entry-discipline framing: 'wait for pivot,
    don't chase >1% above pivot'. The hyp-recs trade-prep expansion's
    buy_limit = pivot × (1 + chase_factor). Phase 5 surfaces an editor;
    this dispatch ships the storage + read path only.

    Discriminating-test: asserts both attribute existence AND the specific
    0.01 value, so a default of 0.0 or 0.02 would fail.
    """
    from swing.config import Web

    web = Web()
    assert hasattr(web, "chase_factor"), (
        "spec §3.1 requires Config.web.chase_factor field"
    )
    assert web.chase_factor == 0.01, (
        f"chase_factor default must be 0.01 (1%); got {web.chase_factor}"
    )


def test_config_web_chase_factor_no_toml_shadow():
    """Spec §3.1 — toml-shadowing audit.

    Per the 2026-04-29 multi-path-ingestion lesson + the prior aeb2084
    lesson, the field MUST NOT have a row in any GIT-TRACKED toml file
    in V1. Phase 5 (configuration page) surfaces all Web overrides
    together; until then, operators write the value into their local
    untracked toml as a deliberate opt-in (NOT scanned by this audit).

    R1-Major-4 + R3-Minor-1 (Codex) — implemented in pure Python rather
    than shelling out to `grep` (portable Win/Unix; no PATH dependency)
    AND scoped strictly to git-tracked files via `git ls-files` (a
    developer's local untracked `swing.config.toml` override is NOT
    a shadowing concern; the audit catches only what's committed to
    the repo).
    """
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    # Use git ls-files to enumerate tracked toml files. Falls back to
    # an empty set if git is unavailable (the assertion is then
    # vacuously true — surface in CI logs that the audit was skipped).
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.toml"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git unavailable; toml-shadowing audit skipped")
        return
    tracked_tomls = [
        repo_root / line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    offenders: list[tuple[Path, int, str]] = []
    for tomlfile in tracked_tomls:
        if not tomlfile.exists():
            continue
        try:
            lines = tomlfile.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(lines, start=1):
            if "chase_factor" in line:
                offenders.append((tomlfile, lineno, line))
    # docs/ matches are in the spec + brief documents; those are NOT
    # toml shadowing. (No tracked toml under docs/ at plan-time, but
    # filter defensively.)
    offenders = [
        (p, ln, line) for (p, ln, line) in offenders
        if "docs" not in p.parts
    ]
    assert offenders == [], (
        "chase_factor must not appear in any GIT-TRACKED toml file"
        " (multi-path-ingestion lesson). Offenders:\n"
        + "\n".join(f"  {p}:{ln}: {line}" for p, ln, line in offenders)
    )
