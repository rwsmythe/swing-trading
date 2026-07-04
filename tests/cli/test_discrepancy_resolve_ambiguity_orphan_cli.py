"""Arc 19-F — CLI ``resolve-ambiguity`` FK-orphan awareness (Task D).

An operator who reaches for the tier-2 ``resolve-ambiguity`` command on an
FK-orphan (a discrepancy whose referenced fill/cash_movement/trade row was
RAW-DELETED, e.g. disc 73's cash_movement_id=5) previously hit
``"cash_movements row id=5 not found while reading pre-correction value"``
(exit 2). This arc short-circuits the orphan to a terminal
``acknowledged_immaterial`` resolution -- symmetric with the web + the existing
``discrepancy resolve`` command -- while keeping the NON-orphan tier-2 contract
(``--choice`` required, menu dispatch, correction row) byte-identical.

Seeding discipline (18-B.1): the dangling-FK orphan is planted via a RAW INSERT
with ``PRAGMA foreign_keys = OFF``.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config
from tests.cli.test_discrepancy_resolve_ambiguity_cli import (
    _seed_reconciliation_run,
    _seed_trade_with_entry_fill,
)


@pytest.fixture
def cli_workspace(tmp_path: Path):
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


def _plant_fk_orphan(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    cash_movement_id: int | None = None,
    fill_id: int | None = None,
    trade_id: int | None = None,
    resolution: str = "pending_ambiguity_resolution",
    ambiguity_kind: str | None = "schwab_returned_no_match",
    discrepancy_type: str = "cash_movement_mismatch",
    field_name: str = "net_amount",
) -> int:
    """Raw-INSERT a discrepancy referencing a (possibly nonexistent) FK subject
    row, with FK enforcement OFF (so a dangling reference can exist)."""
    conn.execute("PRAGMA foreign_keys = OFF")
    resolution_reason = None
    resolved_by = None
    resolved_at = None
    if resolution == "pending_ambiguity_resolution":
        resolution_reason = "classifier: schwab_returned_no_match"
    elif resolution != "unresolved":
        resolved_by = "operator"
        resolved_at = "2026-06-19T13:00:00"
        ambiguity_kind = None
        resolution_reason = "operator resolved out of pending"
    cur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
            ticker, field_name, expected_value_json, actual_value_json,
            material_to_review, resolution, ambiguity_kind, resolution_reason,
            resolved_at, resolved_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
            "CASH", field_name,
            json.dumps({"amount": 372.48, "date": "2026-06-15",
                        "kind": "withdraw"}),
            json.dumps({"matched": None}),
            1, resolution, ambiguity_kind, resolution_reason,
            resolved_at, resolved_by, "2026-06-19T21:07:27.837",
        ),
    )
    return int(cur.lastrowid)


def _read(db_path: Path, did: int) -> tuple:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT resolution, resolved_by, ambiguity_kind, resolution_reason "
            "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Orphan short-circuit — resolves to acknowledged_immaterial with --reason only
# ---------------------------------------------------------------------------


def test_cash_fk_orphan_resolves_acknowledged_immaterial(cli_workspace) -> None:
    """The disc-73 shape (pending cash_movement_mismatch, ambiguity_kind set,
    cash_movement_id gone) resolves via the orphan short-circuit. PRE-fix: the
    tier-2 path raises 'cash_movements row id=5 not found' (exit 2)."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_fk_orphan(conn, run_id=run_id, cash_movement_id=5)
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--reason", "subject row deleted in D19",
    ])
    assert r.exit_code == 0, r.output
    assert f"resolved orphan discrepancy {did}" in r.output
    assert "cash_movements id=5 no longer exists" in r.output
    resolution, resolved_by, ambiguity_kind, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert resolved_by == "operator"
    assert ambiguity_kind is None
    assert reason.startswith(
        "orphan-resolved (subject row gone): cash_movements id=5"
    )
    assert reason.endswith("subject row deleted in D19")


def test_unresolved_fill_orphan_not_rejected_by_ambiguity_guard(
    cli_workspace,
) -> None:
    """PLACEMENT LOCK: an UNRESOLVED FK-orphan (ambiguity_kind NULL, e.g. a
    raw-deleted fill) is resolved by the orphan short-circuit -- it is NOT
    rejected by the `d.ambiguity_kind is None` guard (which runs AFTER)."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_fk_orphan(
            conn, run_id=run_id, fill_id=4242,
            resolution="unresolved", ambiguity_kind=None,
            discrepancy_type="unmatched_open_fill", field_name="price",
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--reason", "fill raw-deleted",
    ])
    assert r.exit_code == 0, r.output
    assert "fills id=4242 no longer exists" in r.output
    resolution, _, _, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert "fills id=4242" in reason


def test_already_resolved_orphan_is_idempotent_error(cli_workspace) -> None:
    """An already-resolved FK-orphan (row still missing) -> the
    require_current_resolution precondition raises -> ClickException, no
    re-mutation."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_fk_orphan(
            conn, run_id=run_id, cash_movement_id=5,
            resolution="acknowledged_immaterial",
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--reason", "retry",
    ])
    assert r.exit_code != 0, r.output
    # The pre-existing terminal reason is unchanged (no re-mutation).
    _, _, _, reason = _read(db_path, did)
    assert reason == "operator resolved out of pending"


# ---------------------------------------------------------------------------
# NO-REGRESSION — the NON-orphan tier-2 contract is byte-identical
# ---------------------------------------------------------------------------


def test_non_orphan_missing_choice_still_exit_2(cli_workspace) -> None:
    """Omitting --choice on a NON-orphan tier-2 row stays exit 2 (contract
    preserved; the orphan is the only case that may omit --choice)."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_fk_orphan(
            conn, run_id=run_id, fill_id=fill_id, trade_id=trade_id,
            discrepancy_type="entry_price_mismatch", field_name="price",
            ambiguity_kind="schwab_returned_no_match",
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--reason", "no choice supplied",
    ])
    assert r.exit_code == 2, r.output
    assert "--choice is required" in r.output


def test_non_orphan_live_fill_tier2_path_unchanged(cli_workspace) -> None:
    """A live tier-2 row (fill EXISTS) still routes through
    apply_tier2_resolution: --choice mark_unmatched -> exit 0, resolution
    operator_resolved_ambiguity, one correction row."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_fk_orphan(
            conn, run_id=run_id, fill_id=fill_id, trade_id=trade_id,
            discrepancy_type="entry_price_mismatch", field_name="price",
            ambiguity_kind="schwab_returned_no_match",
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "mark_unmatched",
        "--reason", "operator gate test",
    ])
    assert r.exit_code == 0, r.output
    assert f"resolved discrepancy {did}" in r.output
    resolution, resolved_by, _, _ = _read(db_path, did)
    assert resolution == "operator_resolved_ambiguity"
    assert resolved_by == "operator"
    conn = sqlite3.connect(db_path)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1, n
