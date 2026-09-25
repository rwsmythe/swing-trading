"""22-I migration 0041 -- the header declarations and the 22i backup gate.

Plan T1 (`docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.md`):
the header carries (i) the D60 sentence verbatim, (ii) a retiring `DROP
TRIGGER` line for every trigger the file creates plus the restoring text
reference for the one rebuilt trigger, (iii) the gate row, (iv) "adds triggers
only, rebuilds nothing". The gate fires at `pre_version == 40 AND
target_version >= 41` (the D50 clause, written once in
`swing/data/db.py::_run_pre_migration_gate`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from swing.data import db as db_mod

M0041 = (Path(db_mod.__file__).resolve().parent / "migrations"
         / "0041_replace_exposure_sweep.sql")
REBUILT = "trg_provenance_corrections_append_only_update"


def _split() -> tuple[str, str]:
    text = M0041.read_text(encoding="utf-8")
    cut = text.index("\nBEGIN;")
    return text[:cut], text[cut:]


def _flat(header: str) -> str:
    """The header's comment prose as one line (a sentence may wrap)."""
    return " ".join(line.lstrip("-").strip() for line in header.splitlines())


def test_0041_header_declarations() -> None:
    header, body = _split()
    flat = _flat(header)
    # (i) D60, verbatim
    assert ("pre-existing rows replay unchanged: a trigger does not touch "
            "stored rows") in flat
    # (iv) the shape
    assert "adds triggers only, rebuilds nothing" in flat.lower()
    # (iii) the gate row and its clause
    assert ('BackupGateSpec(40, "22i", PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES, '
            '"_phase22_arc_i_backup_gate", "pre-22-I")') in flat
    assert "pre_version == 40 AND target_version >= 41" in flat
    # (ii) a retiring line for every created trigger (the 0040 reversibility
    # shape), and the restoring reference for the rebuilt one
    created = re.findall(r"^CREATE TRIGGER (\w+)", body, re.M)
    assert len(created) == len(set(created))
    for name in created:
        assert re.search(rf"^--\s+DROP TRIGGER {name};", header, re.M), name
    if f"DROP TRIGGER {REBUILT};" in body:
        assert "0039_provenance_corrections_tier2.sql:704" in header
    # the body writes no row but the version bump
    assert re.findall(r"^\s*UPDATE\s+(\w+)", body, re.M | re.I) == ["schema_version"]
    assert "UPDATE schema_version SET version = 41;" in body


def test_the_22i_gate_row_is_the_canonical_clause() -> None:
    spec = db_mod.backup_gate_for_pre_version(40)
    assert spec is not None
    assert (spec.pre_version, spec.filename_stem, spec.gate_name, spec.label,
            spec.creator_alias) == (
        40, "22i", "_phase22_arc_i_backup_gate", "pre-22-I", None)
    assert spec.expected_tables is db_mod.PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES
    assert db_mod.EXPECTED_SCHEMA_VERSION == 41


def test_the_22i_expected_tables_are_the_measured_v40_set(tmp_path: Path) -> None:
    import sqlite3

    c = sqlite3.connect(tmp_path / "v40.db")
    try:
        db_mod.run_migrations(c, target_version=40, backup_dir=tmp_path / "bak")
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        c.close()
    assert names == db_mod.PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES


def test_the_22i_gate_fires_once_from_40_and_the_cli_echoes_one_image(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from swing.cli import main
    from tests.cli.test_db_migrate_single_backup import _build, _config

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    cfg = _config(project, home)
    sd = home / "swing-data"
    _build(sd / "swing.db", 40)
    r = CliRunner().invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    images = sorted((sd / "backups").glob("swing-pre-*-migration-*.db"))
    assert len(images) == 1, images
    assert re.fullmatch(r"swing-pre-22i-migration-\d{8}T\d{6}Z\.db", images[0].name)
    assert f"Backup (pre-migration gate, integrity-verified): {images[0]}" in r.output
    assert not list(sd.glob("swing-pre-*.db"))  # none in the DB's parent
