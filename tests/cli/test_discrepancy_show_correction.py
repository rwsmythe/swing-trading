"""Tests for `swing journal discrepancy show-correction <id>` CLI subcommand
(Sub-bundle 1 T-1.12).

Per plan §A.1.12 + spec §8.3 OQ-G + plan §A.0.1 D1. 8 discriminating cases
covering subcommand existence, help-text content + generic ID-free addendum,
spec path citation, override-correction help epilog breadth, smoke render
of an existing correction, not-found error, and single-source-of-truth
constant verification.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


# ---------------------------------------------------------------------------
# Workspace + seed helpers (mirrors override-correction test pattern).
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_workspace(tmp_path: Path):
    """Create a project + home dir + run db-migrate to land schema v19."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _seed_correction_row(db_path: Path) -> int:
    """Plant a minimal reconciliation_corrections row + return correction_id."""
    conn = sqlite3.connect(db_path)
    try:
        # Plant a run + discrepancy + correction in one transaction.
        rcur = conn.execute(
            """
            INSERT INTO reconciliation_runs (
                source, state, started_ts, period_start, period_end,
                source_artifact_path, finished_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("schwab_api", "completed", "2026-05-15T12:00:00",
             "2026-05-15", "2026-05-15", "schwab_api:run",
             "2026-05-15T12:01:00"),
        )
        run_id = int(rcur.lastrowid)
        dcur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, field_name, material_to_review,
                created_at, expected_value_json, actual_value_json,
                resolution
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, "entry_price_mismatch", "price", 1,
             "2026-05-15T12:00:01",
             '{"price": 5.23}',
             '{"price": 5.30}',
             "auto_corrected_from_schwab"),
        )
        disc_id = int(dcur.lastrowid)
        ccur = conn.execute(
            """
            INSERT INTO reconciliation_corrections (
                discrepancy_id, correction_action, affected_table,
                affected_row_id, field_name, pre_correction_value_json,
                source_canonical_value_json, applied_value_json,
                applied_at, applied_by, reconciliation_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (disc_id, "auto_applied", "fills", 1, "price",
             '{"price": 5.23}', '{"price": 5.30}', '{"price": 5.30}',
             "2026-05-15T12:00:02", "auto", run_id),
        )
        correction_id = int(ccur.lastrowid)
        conn.commit()
        return correction_id
    finally:
        conn.close()


# Test 1 — show-correction --help exits 0 + carries subcommand name.
def test_show_correction_help_exits_zero(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", "--help"],
    )
    assert r.exit_code == 0, r.output
    assert "show-correction" in r.output or "CORRECTION_ID" in r.output


# Test 2 — show-correction --help includes the addendum text.
def test_show_correction_help_includes_addendum_text(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", "--help"],
    )
    assert r.exit_code == 0
    # Per spec §8.3 verbatim addendum text excerpts.
    assert "V2 mapper widening" in r.output
    assert "execution-grain" in r.output
    assert "operator_truth_value_json" in r.output


# Test 3 — show-correction --help is GENERIC + ID-FREE (no
# operator-local correction IDs cited).
def test_show_correction_help_is_generic_no_operator_ids(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", "--help"],
    )
    assert r.exit_code == 0
    # Must NOT cite any specific operator-DB correction id (per OQ-G + plan
    # §A.1.12 R1 M#8 lock).
    for bad in (
        "correction_id=1", "correction_id=2", "correction_id=3",
        "correction_id=4", "correction_id=5", "correction_id=6",
        "correction_id=7",
        "rows 1-6", "rows 1-7",
        "correction_ids 1-6", "correction_ids 1-7",
        "correction_ids 3+4", "correction_ids 3+4+6",
    ):
        assert bad not in r.output, f"forbidden ID-reference {bad!r} in --help"


# Test 4 — show-correction --help cites the spec path verbatim.
def test_show_correction_help_cites_spec_path(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", "--help"],
    )
    assert r.exit_code == 0
    # Per spec §8.3 verbatim addendum path. Click's epilog renderer
    # word-wraps long path strings at terminal-width-80 boundaries —
    # specifically at hyphens — even when the subcommand sets
    # `context_settings={'max_content_width': 200}`. The rendered path
    # comes out as `2026-05-17-schwab-mapper-execution-grain-widening-\n
    # design.md` (the trailing hyphen + soft-wrap newline split the
    # filename). Strip the wrap by removing all whitespace runs and the
    # soft-wrap dangling hyphen so we can assert the path substring.
    flat = "".join(r.output.split())  # remove ALL whitespace
    # Collapse soft-wrap hyphenation: a sequence like `widening-design.md`
    # is what we end up with after whitespace removal.
    assert "docs/superpowers/specs" in flat
    assert "2026-05-17-schwab-mapper-execution-grain-widening-design.md" in flat


# Test 5 — override-correction --help ALSO includes the addendum (breadth).
def test_override_correction_help_includes_addendum(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "override-correction", "--help"],
    )
    assert r.exit_code == 0
    assert "V2 mapper widening" in r.output
    assert "execution-grain" in r.output


# Test 6 — show-correction <existing_id> smoke renders correction detail.
def test_show_correction_existing_id_renders(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    correction_id = _seed_correction_row(db_path)
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", str(correction_id)],
    )
    assert r.exit_code == 0, r.output
    assert "correction_id" in r.output
    assert str(correction_id) in r.output
    # Renders the correction_action + affected_table.
    assert "auto_applied" in r.output
    assert "fills" in r.output


# Test 7 — show-correction <nonexistent> → exit non-zero + 'not found'.
def test_show_correction_not_found_errors(cli_workspace) -> None:
    runner, cfg, _db_path = cli_workspace
    r = runner.invoke(
        main,
        ["--config", str(cfg), "journal", "discrepancy",
         "show-correction", "99999"],
    )
    assert r.exit_code != 0, r.output
    assert "not found" in (r.output + (r.stderr_bytes.decode() if r.stderr_bytes else "")).lower()


# Test 8 — _HISTORICAL_CORRECTION_NOTE single-source-of-truth constant.
def test_historical_correction_note_constant_single_source() -> None:
    """Verify the module-level _HISTORICAL_CORRECTION_NOTE constant exists
    + carries the canonical addendum substring."""
    from swing import cli as cli_mod
    assert hasattr(cli_mod, "_HISTORICAL_CORRECTION_NOTE")
    note = cli_mod._HISTORICAL_CORRECTION_NOTE
    assert isinstance(note, str)
    assert "V2 mapper widening" in note
    assert "execution-grain" in note
    assert "operator_truth_value_json" in note
