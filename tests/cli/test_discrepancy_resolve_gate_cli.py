"""Arc 20-B — the D22 gate on the general ``discrepancy resolve`` command.

``swing journal discrepancy resolve <id>`` previously called
``resolve_discrepancy`` on ANY ``pending_ambiguity_resolution`` row, silently
bypassing the tier-2 choice menu + the correction row (the D22 register bug).
This arc gates the general command:

  - a pending row whose FK subject row(s) EXIST refuses (exit non-zero, naming
    BOTH ``resolve-ambiguity`` and ``--force``);
  - an FK-orphan (subject row raw-deleted) passes UNGATED, exactly as today
    (REUSING the 19-F ``orphaned_affected_target`` predicate, not a fork);
  - ``--force`` overrides the gate AND RECORDS the conscious bypass in the
    resolution reason (never a silent identical outcome);
  - a non-pending row is byte-identical to pre-20-B behavior.

Seeding discipline (18-B.1): pending / orphan / non-pending discrepancy rows
are planted via RAW production-shape INSERT (FK enforcement OFF for the
dangling orphan) -- never through a barriered writer. Each assertion is
computed under BOTH the pre-fix path (bypass/exit-0 or no --force option) and
the post-fix path (refuse/record) so it distinguishes.
"""
from __future__ import annotations

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
from tests.cli.test_discrepancy_resolve_ambiguity_orphan_cli import (
    _plant_fk_orphan,
    _read,
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


def _seed_live_pending(db_path: Path) -> int:
    """Plant a LIVE tier-2 pending row (fill + trade EXIST) -> subject rows
    present -> the gated case."""
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
    return did


# ---------------------------------------------------------------------------
# Orphan passes UNGATED (no-regression: pre-fix and post-fix both exit 0)
# ---------------------------------------------------------------------------


def test_orphan_pending_resolve_passes_ungated(cli_workspace) -> None:
    """An FK-orphan pending row (cash_movement_id gone) resolves directly via
    `discrepancy resolve` -- ungated, exactly as today. The gate must NOT fire
    (orphaned_affected_target is non-None -> orphan -> pass). The operator
    reason is passed through verbatim (no forced-bypass marker)."""
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
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "subject row deleted in D19",
    ])
    assert r.exit_code == 0, r.output
    resolution, _, ambiguity_kind, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert ambiguity_kind is None
    # Ungated path: verbatim operator reason, no forced-bypass marker.
    assert reason == "subject row deleted in D19"
    assert "bypass" not in reason.lower()


# ---------------------------------------------------------------------------
# Live subject-exists pending REFUSES (the NEW discriminating case)
# ---------------------------------------------------------------------------


def test_pending_subject_exists_refuses(cli_workspace) -> None:
    """A LIVE tier-2 pending row (fill + trade EXIST) is REFUSED by the general
    resolve command. PRE-fix: exit 0, resolution silently flips to
    acknowledged_immaterial (the D22 bypass). POST-fix: exit non-zero, the row
    stays pending_ambiguity_resolution (unmutated)."""
    runner, cfg, db_path = cli_workspace
    did = _seed_live_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "trying to bypass the menu",
    ])
    assert r.exit_code != 0, r.output
    assert str(did) in r.output
    # Row unchanged -- still pending, ambiguity_kind intact.
    resolution, resolved_by, ambiguity_kind, _ = _read(db_path, did)
    assert resolution == "pending_ambiguity_resolution"
    assert ambiguity_kind == "schwab_returned_no_match"
    assert resolved_by is None


def test_refusal_message_names_both_escape_hatches(cli_workspace) -> None:
    """The refusal message names BOTH the choice-menu flow (`resolve-ambiguity`)
    AND the escape hatch (`--force`). PRE-fix: exit 0 with no such message."""
    runner, cfg, db_path = cli_workspace
    did = _seed_live_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "trying to bypass the menu",
    ])
    assert r.exit_code != 0, r.output
    out = r.output.lower()
    assert "resolve-ambiguity" in out
    assert "--force" in out


# ---------------------------------------------------------------------------
# --force proceeds AND records the bypass on the audit surface
# ---------------------------------------------------------------------------


def test_pending_subject_exists_force_records_bypass(cli_workspace) -> None:
    """`--force` on a LIVE pending row proceeds to resolution AND records the
    conscious bypass in resolution_reason (never a silent identical outcome).
    PRE-fix: --force is an unknown option (exit 2). POST-fix: exit 0, resolved,
    the bypass marker + the operator reason both persisted."""
    runner, cfg, db_path = cli_workspace
    did = _seed_live_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "deliberate override for audit",
        "--force",
    ])
    assert r.exit_code == 0, r.output
    resolution, resolved_by, ambiguity_kind, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert resolved_by == "operator"
    assert ambiguity_kind is None
    # The forced bypass is recorded -- distinct from a silent identical outcome.
    assert "bypass" in reason.lower()
    assert str(did) in reason
    # The bypassed ambiguity_kind is preserved in the marker even though
    # resolve_discrepancy clears it from the row on the transition.
    assert "schwab_returned_no_match" in reason
    # Operator rationale preserved alongside the marker.
    assert "deliberate override for audit" in reason


def test_force_on_ungated_row_adds_no_marker(cli_workspace) -> None:
    """`--force` is IGNORED for a non-gated (orphan) row -- the reason is passed
    through verbatim, no bypass marker. Confirms the marker rides ONLY the
    pending+subject-exists override path (not a blanket --force behavior)."""
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
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "orphan with force flag",
        "--force",
    ])
    assert r.exit_code == 0, r.output
    _, _, _, reason = _read(db_path, did)
    assert reason == "orphan with force flag"
    assert "bypass" not in reason.lower()


def _plant_no_fk_pending(db_path: Path) -> int:
    """Plant a pending_ambiguity_resolution row with ALL FK columns NULL. The
    schema cross-CHECK ties ambiguity_kind to the pending resolution but does
    NOT require an FK, so this state is reachable. Such a row has no subject
    rows and no resolve-ambiguity path (_resolve_affected_target has nothing to
    read), so the gate must NOT refuse it -- it passes ungated like an orphan.
    """
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        cur = conn.execute(
            """
            INSERT INTO reconciliation_discrepancies (
                run_id, discrepancy_type, trade_id, fill_id, cash_movement_id,
                ticker, field_name, expected_value_json, actual_value_json,
                material_to_review, resolution, ambiguity_kind,
                resolution_reason, created_at
            ) VALUES (?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, "snapshot_mismatch", "SPY", "net_amount",
                None, None, 1, "pending_ambiguity_resolution",
                "unknown_schwab_subtype",
                "classifier: unknown_schwab_subtype", "2026-05-16T12:05:00",
            ),
        )
        did = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return did


def test_no_fk_pending_passes_ungated(cli_workspace) -> None:
    """A NO-FK pending row (all subject FKs NULL -> no subject rows, no
    resolve-ambiguity path) is NOT refused -- it passes ungated exactly as
    today (verbatim reason, no marker). PRE-this-fix the gate refused any
    non-orphan pending row (including no-FK); POST-fix it fires only when a
    subject FK is set AND the subject exists."""
    runner, cfg, db_path = cli_workspace
    did = _plant_no_fk_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "no-FK pending; direct ack",
    ])
    assert r.exit_code == 0, r.output
    resolution, _, ambiguity_kind, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert ambiguity_kind is None  # cleared on the transition
    assert reason == "no-FK pending; direct ack"
    assert "bypass" not in reason.lower()


def _plant_source_direction_pending(db_path: Path) -> int:
    """Plant a SOURCE-DIRECTION pending row (field_name='missing_journal_row',
    all FK NULL BY DESIGN -- the journal row is what is MISSING). Despite having
    no FK it HAS a supported resolve-ambiguity path (the source_without_journal
    menu / apply_source_direction_resolution), so the gate MUST refuse it. Real
    emitter shape per swing/trades/schwab_reconciliation.py:_emit_source_
    direction_cash + tests/trades/test_source_direction_resolution.py."""
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        cur = conn.execute(
            "INSERT INTO reconciliation_discrepancies (run_id, "
            "discrepancy_type, field_name, material_to_review, created_at, "
            "resolution, ambiguity_kind, expected_value_json, "
            "actual_value_json) VALUES (?, 'cash_movement_mismatch', "
            "'missing_journal_row', 1, '2026-05-16T12:05:00', "
            "'pending_ambiguity_resolution', 'schwab_returned_no_match', "
            "'{\"transactionId\": \"TX9\"}', '{\"matched\": null}')",
            (run_id,),
        )
        did = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    return did


def test_source_direction_pending_refuses(cli_workspace) -> None:
    """A SOURCE-DIRECTION pending row (all-FK-null but resolvable via the
    source_without_journal menu) is REFUSED, naming both escape hatches.
    PRE this fix the has_subject_fk-only gate let it silently bypass (exit 0);
    POST fix the field_name=='missing_journal_row' path gates it."""
    runner, cfg, db_path = cli_workspace
    did = _plant_source_direction_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "trying to bypass source-direction menu",
    ])
    assert r.exit_code != 0, r.output
    out = r.output.lower()
    assert "resolve-ambiguity" in out
    assert "--force" in out
    resolution, _, ambiguity_kind, _ = _read(db_path, did)
    assert resolution == "pending_ambiguity_resolution"
    assert ambiguity_kind == "schwab_returned_no_match"


def test_source_direction_pending_force_records_bypass(cli_workspace) -> None:
    """`--force` on a source-direction pending row proceeds AND records the
    bypass. PRE this fix --force was moot (the row was never gated)."""
    runner, cfg, db_path = cli_workspace
    did = _plant_source_direction_pending(db_path)

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "confirmed not a ledger event",
        "--force",
    ])
    assert r.exit_code == 0, r.output
    resolution, _, ambiguity_kind, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert ambiguity_kind is None
    assert "bypass" in reason.lower()
    assert "confirmed not a ledger event" in reason


# ---------------------------------------------------------------------------
# Non-pending row is byte-identical to today (the gate touches ONLY pending)
# ---------------------------------------------------------------------------


def test_non_pending_row_unchanged(cli_workspace) -> None:
    """A NON-pending (unresolved) row with a LIVE subject resolves exactly as
    today -- verbatim reason, no gate, no marker. Pre-fix and post-fix are
    byte-identical."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_fk_orphan(
            conn, run_id=run_id, fill_id=fill_id, trade_id=trade_id,
            resolution="unresolved", ambiguity_kind=None,
            discrepancy_type="entry_price_mismatch", field_name="price",
        )
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve", str(did),
        "--resolution", "acknowledged_immaterial",
        "--reason", "immaterial delta",
    ])
    assert r.exit_code == 0, r.output
    resolution, _, _, reason = _read(db_path, did)
    assert resolution == "acknowledged_immaterial"
    assert reason == "immaterial delta"
    assert "bypass" not in reason.lower()
