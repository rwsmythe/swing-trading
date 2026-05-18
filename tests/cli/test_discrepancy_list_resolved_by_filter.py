"""Phase 12.5 #1 T-1.10 — CLI: ``swing journal discrepancy list --resolved-by``.

Per plan §A T-1.10 acceptance criteria — adds a ``--resolved-by`` Click
option to the existing ``swing journal discrepancy list`` command. The
filter is composable with the pre-existing ``--unresolved`` / ``--material``
/ ``--trade-id`` / ``--limit`` options.

Spec §8.6 + §13.2 LOCKs honored:
  * F7 (free TEXT): NO CLI-layer enum validation; NO new
    ``_RESOLVED_BY_VALUES`` Python constant.
  * Composability: combinable with existing filters per spec §8.6.

Discriminating tests (4 — names from plan §A T-1.10):
  1. ``--resolved-by auto_tier1_multi_leg`` returns 2 planted multi-leg
     rows + the 1 operator-resolved row is absent.
  2. ``--resolved-by nonexistent_value`` returns the ``(no discrepancies)``
     friendly empty-message.
  3. ``--unresolved --resolved-by auto_tier1_multi_leg`` composes without
     raising (AND-composition typically yields 0 rows since auto-redirect
     pairs with ``operator_resolved_ambiguity``, not ``unresolved``).
  4. ``--material --resolved-by auto_tier1_multi_leg`` returns the
     material+resolved-by row only.
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
        ("tos_csv", "2026-05-17T10:00:00", "completed",
         "2026-05-10", "2026-05-17"),
    )
    return int(cur.lastrowid)


def _plant_discrepancy(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str,
    resolution: str,
    resolved_by: str | None,
    material: int = 0,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    created_at: str = "2026-05-17T10:05:00",
    ambiguity_kind: str | None = None,
) -> int:
    """Insert one discrepancy row + return discrepancy_id.

    Honors C.A cross-column CHECK invariant: ``ambiguity_kind`` is
    NOT NULL iff ``resolution`` IN (``pending_ambiguity_resolution``,
    ``operator_resolved_ambiguity``). Auto-defaults when caller omits.
    """
    if ambiguity_kind is None and resolution in (
        "pending_ambiguity_resolution",
        "operator_resolved_ambiguity",
    ):
        ambiguity_kind = "multi_partial_vs_consolidated"
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, resolved_by, ambiguity_kind, "
        "  created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            material, resolution, resolved_by, ambiguity_kind, created_at,
        ),
    )
    return int(cur.lastrowid)


# ===========================================================================
# §1 — --resolved-by auto_tier1_multi_leg returns matching rows.
# ===========================================================================


def test_discrepancy_list_resolved_by_auto_tier1_multi_leg_returns_matching_rows(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        d1 = _plant_discrepancy(
            conn, run_id,
            ticker="DHC",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
            created_at="2026-05-17T10:05:00",
        )
        d2 = _plant_discrepancy(
            conn, run_id,
            ticker="VSAT",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
            created_at="2026-05-17T10:06:00",
        )
        d3 = _plant_discrepancy(
            conn, run_id,
            ticker="CVGI",
            resolution="operator_resolved_ambiguity",
            resolved_by="operator",
            created_at="2026-05-17T10:07:00",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list",
        "--resolved-by", "auto_tier1_multi_leg",
    ])
    assert r.exit_code == 0, r.output
    # Both matching IDs surface in stdout (ID column).
    assert f" {d1} " in r.output or f"{d1:>5}" in r.output
    assert f" {d2} " in r.output or f"{d2:>5}" in r.output
    # Tickers as ground truth — DHC + VSAT present; CVGI absent.
    assert "DHC" in r.output
    assert "VSAT" in r.output
    assert "CVGI" not in r.output
    # Empty-message must NOT appear.
    assert "(no discrepancies)" not in r.output
    # The operator-resolved discrepancy id MUST be absent.
    assert f"{d3:>5}" not in r.output


# ===========================================================================
# §2 — --resolved-by with no match returns empty-message.
# ===========================================================================


def test_discrepancy_list_resolved_by_no_match_returns_empty_with_friendly_message(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_discrepancy(
            conn, run_id,
            ticker="DHC",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
        )
        _plant_discrepancy(
            conn, run_id,
            ticker="VSAT",
            resolution="unresolved",
            resolved_by=None,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list",
        "--resolved-by", "nonexistent_value",
    ])
    assert r.exit_code == 0, r.output
    assert "(no discrepancies)" in r.output
    # Neither planted ticker surfaces.
    assert "DHC" not in r.output
    assert "VSAT" not in r.output


# ===========================================================================
# §3 — composable with --unresolved (AND-composition).
# ===========================================================================


def test_discrepancy_list_resolved_by_composable_with_unresolved_filter(
    cli_workspace,
) -> None:
    """``--unresolved`` AND ``--resolved-by auto_tier1_multi_leg`` composes.

    Auto-redirect resolutions are ``operator_resolved_ambiguity``, NOT
    ``unresolved`` (per spec §7.4), so this composition typically yields
    0 rows. The test asserts the CLI does not raise + returns the empty
    message. It also plants an ``unresolved`` row without ``resolved_by``
    that MUST be excluded (filter is applied), and an
    ``operator_resolved_ambiguity`` row with the auto-redirect
    ``resolved_by`` that MUST be excluded (the ``--unresolved`` filter
    rules it out).
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        # Unresolved without resolved_by — filter excludes (resolved_by NULL).
        _plant_discrepancy(
            conn, run_id,
            ticker="DHC",
            resolution="unresolved",
            resolved_by=None,
        )
        # Auto-redirect (operator_resolved_ambiguity) — excluded by --unresolved.
        _plant_discrepancy(
            conn, run_id,
            ticker="VSAT",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list",
        "--unresolved", "--resolved-by", "auto_tier1_multi_leg",
    ])
    assert r.exit_code == 0, r.output
    # AND-composition yields 0 rows. Empty-message surfaces.
    assert "(no discrepancies)" in r.output
    # Neither planted ticker surfaces.
    assert "DHC" not in r.output
    assert "VSAT" not in r.output


# ===========================================================================
# §4 — composable with --material.
# ===========================================================================


def test_discrepancy_list_resolved_by_composable_with_material_filter(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        # Material=1 + resolved_by=auto_tier1_multi_leg — SHOULD match.
        d_match = _plant_discrepancy(
            conn, run_id,
            ticker="DHC",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
            material=1,
        )
        # Material=0 + resolved_by=auto_tier1_multi_leg — excluded by --material.
        _plant_discrepancy(
            conn, run_id,
            ticker="VSAT",
            resolution="operator_resolved_ambiguity",
            resolved_by="auto_tier1_multi_leg",
            material=0,
        )
        # Material=1 + resolved_by='operator' — excluded by --resolved-by.
        _plant_discrepancy(
            conn, run_id,
            ticker="CVGI",
            resolution="operator_resolved_ambiguity",
            resolved_by="operator",
            material=1,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "list",
        "--material", "--resolved-by", "auto_tier1_multi_leg",
    ])
    assert r.exit_code == 0, r.output
    # Exactly the d_match row surfaces.
    assert "DHC" in r.output
    assert f"{d_match:>5}" in r.output
    # Other tickers must be absent.
    assert "VSAT" not in r.output
    assert "CVGI" not in r.output
    # Empty-message must NOT appear.
    assert "(no discrepancies)" not in r.output
