"""Phase 13 T4.SB Codex R1 m#2 — ``swing diagnose`` subcommands must
pre-validate the ``--db`` path BEFORE invoking sqlite3.connect().

Pre-fix: raw ``sqlite3.connect(str(db_path))`` would CREATE an empty
SQLite file at the typoed path (sqlite3 default behavior), then the
first SELECT raises ``OperationalError`` deep in the stack, surfacing
as an ugly traceback to the operator. Also bypasses the app's
schema-version validation discipline.

Post-fix: a non-existent ``--db`` path raises a friendly
``click.ClickException`` BEFORE any DB connection is opened; the path
is NOT auto-created on disk. Affected subcommands:

- ``swing diagnose aplus-sensitivity --db <missing>``
- ``swing diagnose metrics-wiring --db <missing>``
- ``swing diagnose prune-chart-cache --db <missing>``
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main as cli


@pytest.fixture
def cfg_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate user-config from the operator's real ~/swing-data (per the
    cumulative gotcha about monkeypatching USERPROFILE + HOME)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return Path("swing.config.toml")


def test_diagnose_metrics_wiring_rejects_missing_db_path(
    cfg_path: Path, tmp_path: Path,
) -> None:
    """A typoed --db path MUST surface as a friendly ClickException +
    MUST NOT auto-create the file on disk."""
    runner = CliRunner()
    missing = tmp_path / "definitely-not-there.db"
    assert not missing.exists()
    out_path = tmp_path / "audit.md"
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "metrics-wiring",
        "--db", str(missing),
        "--output", str(out_path),
    ])
    assert result.exit_code != 0, result.output
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "not found" in combined.lower() or "does not exist" in combined.lower(), (
        f"expected friendly DB-not-found error; got: {combined!r}"
    )
    # The path must NOT have been auto-created by sqlite3.connect.
    assert not missing.exists(), (
        "diagnose metrics-wiring auto-created an empty SQLite file at "
        "the typoed path — pre-validation gate broken"
    )


def test_diagnose_prune_chart_cache_rejects_missing_db_path(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    missing = tmp_path / "no-such.db"
    assert not missing.exists()
    result = runner.invoke(cli, [
        "diagnose", "prune-chart-cache",
        "--db", str(missing), "--older-than", "30",
    ])
    assert result.exit_code != 0, result.output
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "not found" in combined.lower() or "does not exist" in combined.lower(), (
        f"expected friendly DB-not-found error; got: {combined!r}"
    )
    assert not missing.exists(), (
        "diagnose prune-chart-cache auto-created an empty SQLite file"
    )


def test_diagnose_aplus_sensitivity_rejects_missing_db_path(
    cfg_path: Path, tmp_path: Path,
) -> None:
    runner = CliRunner()
    missing = tmp_path / "nope.db"
    assert not missing.exists()
    out_dir = tmp_path / "out"
    result = runner.invoke(cli, [
        "--config", str(cfg_path),
        "diagnose", "aplus-sensitivity",
        "--db", str(missing),
        "--eval-runs", "5",
        "--output-dir", str(out_dir),
    ])
    assert result.exit_code != 0, result.output
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "not found" in combined.lower() or "does not exist" in combined.lower(), (
        f"expected friendly DB-not-found error; got: {combined!r}"
    )
    assert not missing.exists(), (
        "diagnose aplus-sensitivity auto-created an empty SQLite file"
    )
