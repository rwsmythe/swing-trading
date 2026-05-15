"""T-D.7 — operator-facing manual-backup warning when 0018 will land.

Per Schwab API plan §C.5 + §I.1 + dispatch brief §0.9 T-D.7: NO
version-specific backup gate fires for 17→18 (the Phase-9 gate is
keyed on current==16 AND target>=17), so the migration runner does
not raise ``MigrationBackupRequiredException`` to interrupt the
operator. The auto-backup logic in ``swing db-migrate`` STILL writes a
defensive snapshot to ``backups_dir``, but plan §I.1 also wants a
visible operator-facing recommendation to take a manual backup at a
known location BEFORE allowing 0018 to land — defense-in-depth for
the FIRST schema-change in the Schwab arc.

Discriminating-test pattern (anti-no-op) per Phase 9 Sub-bundle A
``test_<emitter>_no_op_value_does_not_supersede`` precedent: plant a
v17 DB → invoke db-migrate → assert warning emitted + exit 0 + schema
advances to v18; THEN re-invoke db-migrate against the now-v18 DB →
assert warning ABSENT + exit 0 + schema unchanged. This pins the
gate predicate to ``pre_version < 18``.

USERPROFILE+HOME monkeypatch per CLAUDE.md gotcha — db-migrate
doesn't itself write to user-config.toml but other CLI subcommands
running through the same click main group can; defensive isolation.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import run_migrations


def _minimal_config(project_dir: Path, home_dir: Path) -> Path:
    """Same shape as tests/cli/test_cli_eval.py:_minimal_config."""
    cfg_path = project_dir / "swing.config.toml"
    universe_path = project_dir / "reference" / "rs-universe.csv"
    universe_path.parent.mkdir(parents=True, exist_ok=True)
    universe_path.write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\nAAPL\nMSFT\n",
        encoding="utf-8",
    )

    cfg_path.write_text(
        f"""[paths]
db_path = "{(home_dir / 'swing-data' / 'swing.db').as_posix()}"
data_dir = "{(home_dir / 'swing-data').as_posix()}"
logs_dir = "{(home_dir / 'swing-data' / 'logs').as_posix()}"
charts_dir = "{(home_dir / 'swing-data' / 'charts').as_posix()}"
backups_dir = "{(home_dir / 'swing-data' / 'backups').as_posix()}"
prices_cache_dir = "{(home_dir / 'swing-data' / 'prices-cache').as_posix()}"
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
    return cfg_path


def _bootstrap_v17(db_path: Path) -> None:
    """Bring a fresh DB to schema_version 17 (Phase-9 ladder), no further."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=17)
    conn.commit()
    version = conn.execute(
        "SELECT version FROM schema_version"
    ).fetchone()[0]
    conn.close()
    assert version == 17, f"bootstrap_v17 produced version {version}"


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """USERPROFILE+HOME monkeypatch per CLAUDE.md gotcha (defensive)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_warns_to_manual_backup_pre_17_18(isolated_home: Path) -> None:
    """Discriminating round-trip: pre-v18 → warn + advance; v18 → no warn + no-op.

    Phase 1 (pre-v18): plant v17 DB → invoke db-migrate → assert
        (a) stderr contains case-insensitive substring "manual backup",
        (b) exit code 0,
        (c) schema_version advances to EXPECTED (>=18).

    Phase 2 (already-v18, idempotence): re-invoke db-migrate → assert
        (a) stderr does NOT contain "manual backup" substring,
        (b) exit code 0,
        (c) schema_version unchanged.
    """
    project_dir = isolated_home / "project"
    home_dir = isolated_home / "home"
    project_dir.mkdir()
    home_dir.mkdir()
    cfg_path = _minimal_config(project_dir, home_dir)

    db_path = home_dir / "swing-data" / "swing.db"
    _bootstrap_v17(db_path)

    runner = CliRunner()

    # Phase 1: pre-v18 invocation MUST emit the manual-backup recommendation.
    result1 = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result1.exit_code == 0, (
        f"db-migrate failed: stdout={result1.output!r} stderr={result1.stderr!r}"
    )
    combined1 = (result1.stderr or "") + (result1.output or "")
    assert "manual backup" in combined1.lower(), (
        f"expected manual-backup recommendation when pre_version < 18; "
        f"stdout={result1.output!r} stderr={result1.stderr!r}"
    )

    # Schema advanced.
    conn = sqlite3.connect(db_path)
    try:
        v_after_phase1 = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
    finally:
        conn.close()
    assert v_after_phase1 >= 18, (
        f"phase 1 left schema at v{v_after_phase1}; expected >=18"
    )

    # Phase 2: already-v18 invocation MUST NOT emit the recommendation.
    result2 = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert result2.exit_code == 0, (
        f"db-migrate failed on idempotent rerun: "
        f"stdout={result2.output!r} stderr={result2.stderr!r}"
    )
    combined2 = (result2.stderr or "") + (result2.output or "")
    assert "manual backup" not in combined2.lower(), (
        f"warning fired when pre_version >= 18 (idempotence violation); "
        f"stdout={result2.output!r} stderr={result2.stderr!r}"
    )

    # Schema unchanged.
    conn = sqlite3.connect(db_path)
    try:
        v_after_phase2 = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
    finally:
        conn.close()
    assert v_after_phase2 == v_after_phase1, (
        f"phase 2 changed schema from v{v_after_phase1} to v{v_after_phase2}"
    )
