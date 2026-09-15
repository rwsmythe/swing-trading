"""D32 + D50 -- `swing db-migrate` takes ONE backup, in backups_dir, and says where.

F1: the gate image lands in ``cfg.paths.backups_dir`` (never beside the DB).
F2 (operator-ruled branch (b)): a gated transition -> the gate's image only, no
CLI copy; an ungated transition -> the CLI copy only; no transition (already at
HEAD) -> no copy at all, echoed with the version read (R0-3). R0-4: the gate's
image is found by the SET-DIFFERENCE of its non-recursive stem glob taken before
and after ensure_schema; exactly one new file is echoed, zero or more than one
RAISES with the count.

Fixture DBs are built through the real runner; the CLI runs through click's
CliRunner against a throwaway config whose every path sits under tmp_path.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data import db as db_mod
from swing.data.db import EXPECTED_SCHEMA_VERSION, open_connection, run_migrations

_CLI_COPY_RE = re.compile(r"^swing-\d{8}T\d{6}\.db$")


def _config(project_dir: Path, home_dir: Path, *, hard_cap_open: int = 6) -> Path:
    cfg_path = project_dir / "swing.config.toml"
    universe = project_dir / "reference" / "rs-universe.csv"
    universe.parent.mkdir(parents=True, exist_ok=True)
    universe.write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\nAAPL\nMSFT\n",
        encoding="utf-8",
    )
    sd = home_dir / "swing-data"
    cfg_path.write_text(
        f"""[paths]
db_path = "{(sd / 'swing.db').as_posix()}"
data_dir = "{sd.as_posix()}"
logs_dir = "{(sd / 'logs').as_posix()}"
charts_dir = "{(sd / 'charts').as_posix()}"
backups_dir = "{(sd / 'backups').as_posix()}"
prices_cache_dir = "{(sd / 'prices-cache').as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = {hard_cap_open}

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


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    home.mkdir()
    cfg = _config(project, home)
    sd = home / "swing-data"
    return {"cfg": cfg, "db": sd / "swing.db", "sd": sd, "backups": sd / "backups"}


def _build(db: Path, version: int) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    c = open_connection(db, reaffirm_wal=True)
    try:
        # a scratch dir: building a fixture must never seed backups_dir
        run_migrations(c, target_version=version, backup_dir=db.parent / "_build_bak")
    finally:
        c.close()


def _version(db: Path) -> int:
    c = sqlite3.connect(db)
    try:
        return int(c.execute("SELECT version FROM schema_version").fetchone()[0])
    finally:
        c.close()


def _migrate(world):
    return CliRunner().invoke(main, ["--config", str(world["cfg"]), "db-migrate"])


def _names(d: Path) -> list[str]:
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_a_gated_transition_writes_one_gate_image_in_backups_dir_and_no_cli_copy(world) -> None:
    _build(world["db"], 37)
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    names = _names(world["backups"])
    assert len(names) == 1, names
    assert re.fullmatch(r"swing-pre-22a4-migration-\d{8}T\d{6}Z\.db", names[0]), names
    assert not [n for n in names if _CLI_COPY_RE.match(n)]
    # nothing beside the live DB (the D32 root-pre-image defect)
    assert not list(world["sd"].glob("swing-pre-*.db"))
    image = world["backups"] / names[0]
    assert f"Backup (pre-migration gate, integrity-verified): {image}" in r.output
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION
    assert _version(image) == 37  # the image is the PRE-migration state


@pytest.mark.parametrize("pre", [14, 17])
def test_an_ungated_transition_takes_the_cli_copy_only(world, pre: int) -> None:
    _build(world["db"], pre)
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    names = _names(world["backups"])
    assert len(names) == 1 and _CLI_COPY_RE.match(names[0]), names
    assert f"Backup: {world['backups'] / names[0]}" in r.output
    assert not list(world["sd"].glob("swing-pre-*.db"))
    assert _version(world["backups"] / names[0]) == pre
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION


def test_already_at_head_takes_no_backup_and_says_so_naming_the_version(world) -> None:
    _build(world["db"], EXPECTED_SCHEMA_VERSION)
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    assert _names(world["backups"]) == []
    assert not list(world["sd"].glob("swing-pre-*.db"))
    assert (
        f"Schema already at version {EXPECTED_SCHEMA_VERSION} (HEAD); nothing to "
        "migrate, no backup taken." in r.output
    )
    assert "Backup" not in r.output


def test_a_fresh_install_takes_no_backup(world) -> None:
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    assert _names(world["backups"]) == []
    assert _version(world["db"]) == EXPECTED_SCHEMA_VERSION


def test_the_echo_names_the_NEW_image_not_an_older_same_stem_file(world) -> None:
    """Set-difference, non-recursive: an older image in backups_dir itself and
    one in backups/pre-images/ (the F4(a) destination) share the stem; neither
    is named, and neither is counted."""
    _build(world["db"], 37)
    older = world["backups"] / "swing-pre-22a4-migration-20260101T000000Z.db"
    moved = world["backups"] / "pre-images" / "swing-pre-22a4-migration-20991231T235959Z.db"
    moved.parent.mkdir(parents=True)
    older.write_bytes(b"older")
    moved.write_bytes(b"moved")
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    new = sorted(set(world["backups"].glob("swing-pre-22a4-migration-*.db")) - {older})
    assert len(new) == 1
    line = [ln for ln in r.output.splitlines() if ln.startswith("Backup (pre-migration gate")]
    assert line == [f"Backup (pre-migration gate, integrity-verified): {new[0]}"]
    assert older.read_bytes() == b"older" and moved.read_bytes() == b"moved"


def test_zero_new_images_after_a_gated_migration_RAISES_with_the_count(
        world, monkeypatch: pytest.MonkeyPatch) -> None:
    _build(world["db"], 37)
    monkeypatch.setattr(db_mod, "_phase22_arc_a4_backup_gate", lambda *a, **k: None)
    r = _migrate(world)
    assert r.exit_code != 0
    assert "0 new 'swing-pre-22a4-migration-*.db' backup image(s)" in r.output
    assert "(expected exactly 1)" in r.output
    assert "Backup (pre-migration gate" not in r.output
    assert _names(world["backups"]) == []  # and no CLI copy was taken instead


def test_more_than_one_new_image_RAISES_with_the_count(
        world, monkeypatch: pytest.MonkeyPatch) -> None:
    _build(world["db"], 37)

    def _two(conn, *, current_version, target_version, backup_dir):
        backup_dir.mkdir(parents=True, exist_ok=True)
        for ts in ("20300101T000000Z", "20300101T000001Z"):
            (backup_dir / f"swing-pre-22a4-migration-{ts}.db").write_bytes(b"x")

    monkeypatch.setattr(db_mod, "_phase22_arc_a4_backup_gate", _two)
    r = _migrate(world)
    assert r.exit_code != 0
    assert "2 new 'swing-pre-22a4-migration-*.db' backup image(s)" in r.output


def test_a_refusing_gate_stops_the_migration_and_takes_no_cli_copy(
        world, monkeypatch: pytest.MonkeyPatch) -> None:
    _build(world["db"], 37)

    def _refuse(*_a, **_k):
        raise db_mod.MigrationBackupRequiredException("planted refusal")

    monkeypatch.setattr(db_mod, "_phase22_arc_a4_backup_gate", _refuse)
    r = _migrate(world)
    assert r.exit_code != 0
    assert isinstance(r.exception, db_mod.MigrationBackupRequiredException)
    assert _version(world["db"]) == 37
    assert _names(world["backups"]) == []


def test_cli_decision_reads_the_same_table_the_runner_iterates() -> None:
    for v in range(0, EXPECTED_SCHEMA_VERSION + 1):
        spec = db_mod.backup_gate_for_pre_version(v)
        rows = [s for s in db_mod._PRE_MIGRATION_BACKUP_GATES if s.pre_version == v]
        assert (spec is None) == (rows == [])
        if spec is not None:
            assert spec is rows[0]


# ---------------------------------------------------------------------------
# Codex R1 fixes: no-clobber (R-1), the deferred alarm (R-3), the F2 boundary
# states (R-5)
# ---------------------------------------------------------------------------
def _real_db(path: Path) -> None:
    """A REAL database at ``path`` (garbage bytes would make backup() fail on its
    own, so an overwrite test would pass without any no-clobber protection)."""
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE an_earlier_recovery_image (x)")
    c.commit()
    c.close()


def _frozen(fixed):
    from datetime import datetime as _dt

    class _Frozen(_dt):
        @classmethod
        def now(cls, tz=None):
            return fixed.replace(tzinfo=tz)

    return _Frozen


def test_an_occupied_cli_copy_name_refuses_BEFORE_migrating_and_keeps_the_file(
        world, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime as _dt

    import swing.cli as cli_mod

    _build(world["db"], 17)
    monkeypatch.setattr(cli_mod, "datetime", _frozen(_dt(2030, 1, 2, 3, 4, 5)))
    world["backups"].mkdir(parents=True)
    occupied = world["backups"] / "swing-20300102T030405.db"
    _real_db(occupied)
    original = occupied.read_bytes()
    r = _migrate(world)
    assert r.exit_code != 0
    assert "refusing to overwrite" in r.output
    assert occupied.read_bytes() == original
    assert _names(world["backups"]) == [occupied.name]
    assert _version(world["db"]) == 17


def test_an_occupied_gate_image_name_refuses_BEFORE_migrating_and_keeps_the_file(
        world, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime as _dt

    _build(world["db"], 37)
    monkeypatch.setattr(db_mod, "datetime", _frozen(_dt(2030, 1, 2, 3, 4, 5)))
    world["backups"].mkdir(parents=True)
    occupied = world["backups"] / "swing-pre-22a4-migration-20300102T030405Z.db"
    _real_db(occupied)
    original = occupied.read_bytes()
    r = _migrate(world)
    assert r.exit_code != 0
    assert isinstance(r.exception, db_mod.MigrationBackupRequiredException)
    assert "pre-22-A4 backup failed" in str(r.exception)
    assert occupied.read_bytes() == original
    assert _names(world["backups"]) == [occupied.name]
    assert _version(world["db"]) == 37


def test_the_image_count_alarm_is_raised_only_AFTER_the_v17_ratification(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From v16 the gated path also owes the once-only v17 seed ratification. A
    wiring alarm must not pre-empt it: a retry starts at HEAD and never ratifies."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "project").mkdir()
    (tmp_path / "home").mkdir()
    cfg = _config(tmp_path / "project", tmp_path / "home", hard_cap_open=11)
    db = tmp_path / "home" / "swing-data" / "swing.db"
    _build(db, 16)
    monkeypatch.setattr(db_mod, "_phase9_backup_gate", lambda *a, **k: None)
    r = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code != 0
    assert "0 new 'swing-pre-phase9-migration-*.db' backup image(s)" in r.output
    assert "Phase 9 ratification" in r.output
    c = sqlite3.connect(db)
    try:
        cap = c.execute(
            "SELECT max_concurrent_positions FROM risk_policy WHERE effective_to IS NULL"
        ).fetchall()
    finally:
        c.close()
    assert cap == [(11,)]
    assert _version(db) == EXPECTED_SCHEMA_VERSION


def test_an_existing_schema_less_db_file_gets_the_cli_copy(world) -> None:
    world["sd"].mkdir(parents=True)
    c = sqlite3.connect(world["db"])
    c.execute("CREATE TABLE operator_marker (m TEXT)")
    c.execute("INSERT INTO operator_marker VALUES ('keep me')")
    c.commit()
    c.close()
    r = _migrate(world)
    assert r.exit_code == 0, r.output
    names = _names(world["backups"])
    assert len(names) == 1 and _CLI_COPY_RE.match(names[0]), names
    c = sqlite3.connect(world["backups"] / names[0])
    try:
        assert c.execute("SELECT m FROM operator_marker").fetchall() == [("keep me",)]
        assert c.execute(
            "SELECT 1 FROM sqlite_master WHERE name='schema_version'").fetchone() is None
    finally:
        c.close()


def test_a_db_newer_than_head_is_refused_with_no_backup(world) -> None:
    _build(world["db"], EXPECTED_SCHEMA_VERSION)
    c = sqlite3.connect(world["db"])
    c.execute("UPDATE schema_version SET version = ?", (EXPECTED_SCHEMA_VERSION + 1,))
    c.commit()
    c.close()
    r = _migrate(world)
    assert r.exit_code != 0
    assert isinstance(r.exception, db_mod.SchemaVersionMismatchError)
    assert _names(world["backups"]) == []
    assert not list(world["sd"].glob("swing-pre-*.db"))
