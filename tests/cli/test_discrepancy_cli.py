"""Phase 9 Task B.7 — CLI: swing journal discrepancy {list,show,resolve}.

Per plan §E T-B.7 + spec §4.2 acceptance criteria.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


SYNTHETIC_TOS_TEXT = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 10:00:00,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT
"""


@pytest.fixture
def cli_workspace(tmp_path: Path):
    """Create a project + home dir + run db-migrate."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path, project


def _seed_open_trade(db_path: Path) -> int:
    """Seed an open trade so reconciliation produces a stop_mismatch row."""
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    conn = sqlite3.connect(db_path)
    try:
        trade = Trade(
            id=None, ticker="ABC", entry_date="2026-05-12",
            entry_price=10.05, initial_shares=10,
            initial_stop=9.00, current_stop=9.00,
            state="entered",
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, trade_origin="manual_off_pipeline",
            pre_trade_locked_at="2026-05-12T09:30:00",
        )
        with conn:
            tid = insert_trade_with_event(
                conn, trade, event_ts="2026-05-12T09:30:00", rationale="seed",
            )
            insert_fill_with_event(
                conn,
                Fill(
                    fill_id=None, trade_id=tid,
                    fill_datetime="2026-05-12T09:30:00",
                    action="entry", quantity=10.0, price=10.05,
                ),
                event_ts="2026-05-12T09:30:00",
            )
        return tid
    finally:
        conn.close()


def _run_reconcile(runner, cfg, csv_text: str, tmp_path: Path) -> None:
    csv = tmp_path / "tos.csv"
    csv.write_text(csv_text, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "reconcile-tos",
        "--csv-path", str(csv),
    ])
    assert r.exit_code == 0, r.output


# ===========================================================================
# §1 — reconcile-tos happy path.
# ===========================================================================


def test_reconcile_tos_runs_and_summary_prints(cli_workspace, tmp_path: Path) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(SYNTHETIC_TOS_TEXT, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "reconcile-tos",
        "--csv-path", str(csv),
        "--period-end", "2026-05-12",
        "--notes", "cli test",
    ])
    assert r.exit_code == 0, r.output
    assert "Reconciliation run #" in r.output
    assert "state=completed" in r.output
    # Confirm a row landed.
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_runs WHERE state='completed'"
        ).fetchone()[0]
        assert n == 1
    finally:
        conn.close()


# ===========================================================================
# §2 — import-tos deprecation alias prints stderr warning.
# ===========================================================================


def test_import_tos_alias_prints_deprecation_warning(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(SYNTHETIC_TOS_TEXT, encoding="utf-8")
    # mix_stderr=False keeps stderr distinguishable; runner default merges.
    r = runner.invoke(
        main,
        [
            "--config", str(cfg), "journal", "import-tos",
            "--csv-path", str(csv),
        ],
        catch_exceptions=False,
    )
    assert r.exit_code == 0
    # Output (merged stdout+stderr) must contain the deprecation message.
    assert "deprecated" in r.output.lower()
    assert "reconcile-tos" in r.output


def test_import_tos_alias_dispatches_to_same_service(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    csv = tmp_path / "tos.csv"
    csv.write_text(SYNTHETIC_TOS_TEXT, encoding="utf-8")
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "import-tos",
        "--csv-path", str(csv),
    ])
    assert r.exit_code == 0
    # The alias should produce a reconciliation_runs row equivalent to
    # the canonical command.
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute("SELECT COUNT(*) FROM reconciliation_runs").fetchone()[0]
        assert n == 1
    finally:
        conn.close()


# ===========================================================================
# §3 — discrepancy list / show / resolve.
# ===========================================================================


def test_discrepancy_list_empty(cli_workspace) -> None:
    runner, cfg, db_path, project = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "list",
    ])
    assert r.exit_code == 0
    assert "no discrepancies" in r.output


def test_discrepancy_list_after_reconcile_shows_rows(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "list",
    ])
    assert r.exit_code == 0
    # The stop_mismatch row should appear (no broker working stop in the
    # CSV — Account Order History section absent).
    assert "stop_mismatch" in r.output


def test_discrepancy_list_unresolved_filter(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "list",
        "--unresolved",
    ])
    assert r.exit_code == 0
    assert "stop_mismatch" in r.output


def test_discrepancy_show_renders_full_detail(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    # Fetch the first discrepancy id.
    conn = sqlite3.connect(db_path)
    try:
        did = conn.execute(
            "SELECT discrepancy_id FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "show", str(did),
    ])
    assert r.exit_code == 0
    assert f"discrepancy_id: {did}" in r.output
    assert "type:" in r.output
    assert "resolution:" in r.output


def test_discrepancy_show_unknown_id_errors(cli_workspace) -> None:
    runner, cfg, db_path, project = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "show", "99999",
    ])
    assert r.exit_code != 0
    assert "not found" in r.output.lower()


def test_discrepancy_resolve_happy_path(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        did = conn.execute(
            "SELECT discrepancy_id FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve", str(did),
        "--resolution", "journal_corrected",
        "--reason", "placed broker stop after reconcile review",
    ])
    assert r.exit_code == 0, r.output
    assert f"Discrepancy {did} resolved" in r.output

    # Verify the row was updated.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT resolution, resolution_reason, resolved_at, resolved_by "
            "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "journal_corrected"
    assert row[1] == "placed broker stop after reconcile review"
    assert row[2] is not None
    assert row[3] == "operator"


def test_discrepancy_resolve_acknowledged_immaterial_without_reason(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        did = conn.execute(
            "SELECT discrepancy_id FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
    ])
    assert r.exit_code == 0, r.output


def test_discrepancy_resolve_journal_corrected_requires_reason(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        did = conn.execute(
            "SELECT discrepancy_id FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve", str(did),
        "--resolution", "journal_corrected",
    ])
    assert r.exit_code != 0
    assert "resolution_reason" in r.output


def test_discrepancy_resolve_material_override(
    cli_workspace, tmp_path: Path,
) -> None:
    runner, cfg, db_path, project = cli_workspace
    _seed_open_trade(db_path)
    _run_reconcile(runner, cfg, SYNTHETIC_TOS_TEXT, tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        did = conn.execute(
            "SELECT discrepancy_id FROM reconciliation_discrepancies "
            "ORDER BY discrepancy_id ASC LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--material", "0",
    ])
    assert r.exit_code == 0, r.output
    conn = sqlite3.connect(db_path)
    try:
        mat = conn.execute(
            "SELECT material_to_review FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert mat == 0
