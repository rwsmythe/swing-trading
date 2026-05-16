"""Phase 12 C.D T-D.2 — CLI: ``swing journal discrepancy show-ambiguity``.

Per plan §E.2 acceptance criteria — prints discrepancy detail (shared
fields with ``discrepancy show``) PLUS the per-``ambiguity_kind``
candidate choice menu from
``swing.trades.reconciliation_ambiguity_choices.get_choice_menu``.

Discriminating tests:

1. Discrepancy not found → exit !=0 with click error.
2. ``multi_partial_vs_consolidated`` → 4 codes present + ``[RECOMMENDED]``
   tag on ``keep_journal_as_is`` first + REQUIRES marker on 3 entries.
3. ``multi_match_within_window`` → static + parametric
   ``pick_schwab_record_<N>`` entries (N derived from
   ``resolution_reason`` text).
4. ``unknown_schwab_subtype`` → 3 codes.
5. ``field_shape_incompatible`` → 2 codes.
6. ``schwab_returned_no_match`` → 2 codes.
7. ``validator_rejected`` → 2 codes.
8. ``unsupported`` → 2 codes.
9. NULL ``ambiguity_kind`` (defense-in-depth — schema allows it on
   non-tier-2 rows) → shared fields render + empty menu message.
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
    ticker: str = "DHC",
    ambiguity_kind: str | None = "multi_partial_vs_consolidated",
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    resolution: str = "pending_ambiguity_resolution",
    resolution_reason: str | None = None,
    created_at: str = "2026-05-16T10:05:00",
) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, resolution_reason, "
        "  ambiguity_kind, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, resolution, resolution_reason, ambiguity_kind, created_at,
        ),
    )
    return int(cur.lastrowid)


# ===========================================================================
# §1 — Discrepancy not found.
# ===========================================================================


def test_show_ambiguity_unknown_id_errors(cli_workspace) -> None:
    runner, cfg, _db = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", "9999",
    ])
    assert r.exit_code != 0
    assert "9999" in r.output


# ===========================================================================
# §2 — multi_partial_vs_consolidated (RECOMMENDED tag + 4 codes).
# ===========================================================================


def test_show_ambiguity_multi_partial_vs_consolidated(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            resolution_reason=(
                "Schwab returned 2 separate orders summing to qty=39; "
                "V1 mapper exposes order-level price only"
            ),
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Shared fields rendered.
    assert f"discrepancy_id: {did}" in r.output
    assert "ticker:" in r.output and "DHC" in r.output
    assert "ambiguity_kind: multi_partial_vs_consolidated" in r.output
    # Menu header.
    assert "Candidate choices" in r.output
    # All 4 codes appear.
    assert "keep_journal_as_is" in r.output
    assert "consolidate_using_operator_vwap" in r.output
    assert "split_into_partials" in r.output
    assert "custom" in r.output
    # [RECOMMENDED] tag appears next to keep_journal_as_is.
    assert "[RECOMMENDED] keep_journal_as_is" in r.output
    # REQUIRES marker appears for the 3 custom-value-required codes
    # (must appear at least 3 times — once per requires_custom_value=True
    # row; using --custom-value substring to be robust).
    require_count = r.output.count("--custom-value")
    assert require_count >= 3, (
        f"expected --custom-value REQUIRES marker on 3+ rows, "
        f"got {require_count} in output:\n{r.output}"
    )
    # RECOMMENDED ordering: keep_journal_as_is renders BEFORE the other
    # 3 codes (operator scan-first ordering per OQ-4).
    idx_keep = r.output.index("keep_journal_as_is")
    idx_vwap = r.output.index("consolidate_using_operator_vwap")
    idx_split = r.output.index("split_into_partials")
    assert idx_keep < idx_vwap < idx_split


# ===========================================================================
# §3 — multi_match_within_window (parametric pick_schwab_record_<N>).
# ===========================================================================


def test_show_ambiguity_multi_match_within_window_parametric(
    cli_workspace,
) -> None:
    """V1 source for N = parse ``resolution_reason`` text per plan §E.2
    acceptance criterion #4. With ``Schwab returned 3 orders`` in the
    reason, CLI must surface pick_schwab_record_1 / _2 / _3 entries +
    the static mark_unmatched / custom."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="VSAT",
            ambiguity_kind="multi_match_within_window",
            resolution_reason=(
                "unmatched_open_fill on (ticker='VSAT', fill_id=2): "
                "Schwab returned 3 orders within the match window with "
                "sum-qty=42 != journal qty=40"
            ),
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert "ambiguity_kind: multi_match_within_window" in r.output
    # Parametric pick_schwab_record_<N> entries (3 of them).
    assert "pick_schwab_record_1" in r.output
    assert "pick_schwab_record_2" in r.output
    assert "pick_schwab_record_3" in r.output
    assert "pick_schwab_record_4" not in r.output  # only 3 candidates
    # Static menu entries.
    assert "mark_unmatched" in r.output
    assert "custom" in r.output


def test_show_ambiguity_multi_match_window_no_count_falls_back_static(
    cli_workspace,
) -> None:
    """When ``resolution_reason`` is NULL OR doesn't contain a parseable
    candidate count, CLI surfaces only the static menu (no parametric
    pick_schwab_record entries). Defense-in-depth — pre-empts a parse
    failure crashing the surface."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="VSAT",
            ambiguity_kind="multi_match_within_window",
            resolution_reason=None,  # no parseable count
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Static menu always present.
    assert "mark_unmatched" in r.output
    assert "custom" in r.output
    # No parametric entries.
    assert "pick_schwab_record_" not in r.output


# ===========================================================================
# §4-8 — Remaining ambiguity_kinds render their menu codes.
# ===========================================================================


@pytest.mark.parametrize(
    ("ambiguity_kind", "expected_codes"),
    [
        (
            "unknown_schwab_subtype",
            ("acknowledge", "operator_truth", "custom"),
        ),
        (
            "field_shape_incompatible",
            ("acknowledge", "custom"),
        ),
        (
            "schwab_returned_no_match",
            ("mark_unmatched", "operator_truth"),
        ),
        (
            "validator_rejected",
            ("acknowledge", "operator_alternative"),
        ),
        (
            "unsupported",
            ("operator_truth", "acknowledge"),
        ),
    ],
)
def test_show_ambiguity_per_kind_codes_appear(
    cli_workspace, ambiguity_kind, expected_codes,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="CVGI",
            ambiguity_kind=ambiguity_kind,
            resolution_reason=f"plant for {ambiguity_kind}",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert f"ambiguity_kind: {ambiguity_kind}" in r.output
    for code in expected_codes:
        assert code in r.output, (
            f"missing code {code!r} for kind {ambiguity_kind!r} in "
            f"output:\n{r.output}"
        )


# ===========================================================================
# §9 — NULL ambiguity_kind (defense-in-depth — schema allows NULL on
# non-tier-2 rows).
# ===========================================================================


def test_show_ambiguity_null_kind_renders_shared_fields(
    cli_workspace,
) -> None:
    """A discrepancy in resolution='unresolved' with NULL ambiguity_kind
    is not a Tier-2 backlog row — but operator may still pass its id to
    show-ambiguity. CLI MUST NOT crash; renders shared fields + empty-
    menu advisory."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind=None,
            resolution="unresolved",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert f"discrepancy_id: {did}" in r.output
    # Empty-menu advisory message; phrasing kept loose.
    assert ("no candidate choices" in r.output.lower()
            or "no ambiguity_kind" in r.output.lower())
