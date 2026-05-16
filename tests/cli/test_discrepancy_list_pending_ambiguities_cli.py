"""Phase 12 C.D T-D.1 — CLI: ``swing journal discrepancy list-pending-ambiguities``.

Per plan §E.1 acceptance criteria — read-only CLI subcommand listing
discrepancies in ``resolution='pending_ambiguity_resolution'`` state for
operator review. Mirrors the existing ``discrepancy list`` shape from
Phase 9 Sub-bundle B; filters by ``--ambiguity-kind`` / ``--ticker`` /
``--limit``.

Discriminating tests:
  1. Plant 3 pending-ambiguity discrepancies (DHC + VSAT + CVGI with
     mixed ``ambiguity_kind``) → CLI surfaces all 3 + ambiguity column
     populated per row.
  2. ``--ticker DHC`` → only DHC row shown.
  3. ``--ambiguity-kind multi_partial_vs_consolidated`` → only matching
     row shown.
  4. Zero pending rows → empty-message ``(no pending ambiguities)``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


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


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    """Insert a minimal reconciliation_runs row + return run_id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("tos_csv", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    return int(cur.lastrowid)


def _plant_pending_ambiguity(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str,
    ambiguity_kind: str,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    created_at: str = "2026-05-16T10:05:00",
) -> int:
    """Insert one ``pending_ambiguity_resolution`` discrepancy + return id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, ambiguity_kind, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, "pending_ambiguity_resolution", ambiguity_kind, created_at,
        ),
    )
    return int(cur.lastrowid)


def _seed_three_pending(db_path: Path) -> None:
    """Plant DHC + VSAT + CVGI pending-ambiguity rows with mixed kinds."""
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            created_at="2026-05-16T10:05:00",
        )
        _plant_pending_ambiguity(
            conn, run_id,
            ticker="VSAT",
            ambiguity_kind="multi_match_within_window",
            created_at="2026-05-16T10:06:00",
        )
        _plant_pending_ambiguity(
            conn, run_id,
            ticker="CVGI",
            ambiguity_kind="unsupported",
            created_at="2026-05-16T10:07:00",
        )
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# §1 — empty result message.
# ===========================================================================


def test_list_pending_ambiguities_empty(cli_workspace) -> None:
    runner, cfg, _db = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list-pending-ambiguities",
    ])
    assert r.exit_code == 0, r.output
    assert "(no pending ambiguities)" in r.output


# ===========================================================================
# §2 — 3 planted rows surface with their ambiguity_kind values.
# ===========================================================================


def test_list_pending_ambiguities_shows_all_three(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    _seed_three_pending(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list-pending-ambiguities",
    ])
    assert r.exit_code == 0, r.output
    # All 3 tickers + all 3 ambiguity_kinds rendered.
    assert "DHC" in r.output
    assert "VSAT" in r.output
    assert "CVGI" in r.output
    assert "multi_partial_vs_consolidated" in r.output
    assert "multi_match_within_window" in r.output
    assert "unsupported" in r.output
    # Empty-message must NOT appear.
    assert "(no pending ambiguities)" not in r.output


# ===========================================================================
# §3 — --ticker filter narrows to one row.
# ===========================================================================


def test_list_pending_ambiguities_filter_by_ticker(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    _seed_three_pending(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list-pending-ambiguities",
        "--ticker", "DHC",
    ])
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "multi_partial_vs_consolidated" in r.output
    # Other tickers + their ambiguity_kinds must NOT appear.
    assert "VSAT" not in r.output
    assert "CVGI" not in r.output
    assert "multi_match_within_window" not in r.output
    # 'unsupported' substring guard — table header doesn't carry it.
    assert "unsupported" not in r.output


# ===========================================================================
# §4 — --ambiguity-kind filter narrows to one row.
# ===========================================================================


def test_list_pending_ambiguities_filter_by_ambiguity_kind(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    _seed_three_pending(db_path)
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list-pending-ambiguities",
        "--ambiguity-kind", "multi_partial_vs_consolidated",
    ])
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "multi_partial_vs_consolidated" in r.output
    # Rows with other ambiguity_kinds must NOT appear.
    assert "VSAT" not in r.output
    assert "CVGI" not in r.output
    assert "multi_match_within_window" not in r.output


# ===========================================================================
# §5 — resolution-state isolation: rows in other resolutions excluded.
# ===========================================================================


def test_list_pending_ambiguities_excludes_other_resolutions(
    cli_workspace,
) -> None:
    """Pre-empt false-positive: rows in unresolved / auto_corrected / etc.
    must NOT appear. The CLI predicate is
    ``resolution='pending_ambiguity_resolution'`` exactly."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        # Plant ONE pending-ambiguity row...
        _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
        )
        # ...and ONE unresolved row that must NOT surface.
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "  run_id, discrepancy_type, ticker, field_name, "
            "  material_to_review, resolution, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, "stop_mismatch", "NOISE", "stop",
                1, "unresolved", "2026-05-16T10:08:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list-pending-ambiguities",
    ])
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    # The unresolved row's ticker must be absent.
    assert "NOISE" not in r.output
