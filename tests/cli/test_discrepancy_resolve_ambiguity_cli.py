"""Phase 12 C.D T-D.3 — CLI: ``swing journal discrepancy resolve-ambiguity``.

Per plan §E.3 acceptance criteria — operator-driven CLI surface that
resolves a ``pending_ambiguity_resolution`` discrepancy via a per-
``ambiguity_kind`` ``--choice <code>`` selection (and an optional
``--custom-value '<json>'`` payload). Delegates to
``apply_tier2_resolution`` in ``swing.trades.reconciliation_auto_correct``.

Discriminating tests (per dispatch brief self-review checklist + plan
§E.3 acceptance criterion #11):

* §A — happy paths: one per ``ambiguity_kind`` × 1 valid choice each
  (7 tests via parametrize).
* §B — missing ``--reason`` → non-zero exit.
* §C — missing ``--custom-value`` on payload-required choice → exit 2 +
  shape-description in error message.
* §D — malformed ``--custom-value`` JSON → exit 2.
* §E — incompatible ``--choice`` for ambiguity_kind → exit 2.
* §F — service-owned-state ``--choice`` (4 tests, one per
  ``auto_corrected_from_schwab`` / ``pending_ambiguity_resolution`` /
  ``operator_resolved_ambiguity`` / ``operator_overridden``) → exit 2 +
  routing-hint substring.
* §G — ``--schwab-api-call-id`` back-link wires through to
  ``schwab_api_calls.linked_correction_id``.
"""
from __future__ import annotations

import json
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
        (
            "schwab_api", "2026-05-16T12:00:00", "running",
            "2026-05-10", "2026-05-16",
        ),
    )
    return int(cur.lastrowid)


def _seed_trade_with_entry_fill(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    qty: float = 39.0,
    price: float = 7.50,
) -> tuple[int, int]:
    """Insert a managing trade + its single entry fill; return (trade_id, fill_id)."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker, "2026-04-27", price, int(qty), price - 1.0,
            price - 1.0, "managing", "manual_off_pipeline",
            "2026-04-27T16:00:00",
        ),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id, "2026-04-27T14:23:00", "entry", qty, price,
            "unreconciled",
        ),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    return trade_id, fill_id


def _plant_pending_ambiguity(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    ticker: str,
    ambiguity_kind: str,
    trade_id: int | None = None,
    fill_id: int | None = None,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    resolution_reason: str | None = None,
    expected_json: str | None = None,
    actual_json: str | None = None,
    created_at: str = "2026-05-16T12:05:00",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker,
            field_name, expected_value_json, actual_value_json,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, discrepancy_type, trade_id, fill_id, ticker,
            field_name, expected_json, actual_json,
            1, "pending_ambiguity_resolution", ambiguity_kind,
            resolution_reason, created_at,
        ),
    )
    return int(cur.lastrowid)


# ===========================================================================
# §A — Happy paths: one valid (ambiguity_kind, choice) tuple each.
# ===========================================================================


_HAPPY_PATH_CASES: list[tuple[str, str, str | None]] = [
    # (ambiguity_kind, choice_code, custom_value_json_or_None)
    # Pick one no-payload choice per kind where possible; for kinds whose
    # only no-payload entry is acknowledge/mark_unmatched, use that.
    (
        "multi_partial_vs_consolidated",
        "keep_journal_as_is",
        None,
    ),
    (
        "multi_match_within_window",
        "mark_unmatched",
        None,
    ),
    (
        "unknown_schwab_subtype",
        "acknowledge",
        None,
    ),
    (
        "field_shape_incompatible",
        "acknowledge",
        None,
    ),
    (
        "schwab_returned_no_match",
        "mark_unmatched",
        None,
    ),
    (
        "validator_rejected",
        "acknowledge",
        None,
    ),
    (
        "unsupported",
        "acknowledge",
        None,
    ),
]


@pytest.mark.parametrize("ambiguity_kind,choice_code,custom_value", _HAPPY_PATH_CASES)
def test_resolve_ambiguity_happy_path(
    cli_workspace, ambiguity_kind, choice_code, custom_value,
) -> None:
    """One valid (kind, choice) per ambiguity_kind — assert exit 0 + the
    discrepancy moves to ``operator_resolved_ambiguity`` and a
    ``reconciliation_corrections`` row is created."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(
            conn, ticker="DHC",
        )
        # For acknowledge-style choices that route to a fill-attribution
        # handler, we MUST anchor the discrepancy to that fill.
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind=ambiguity_kind,
            trade_id=trade_id, fill_id=fill_id,
            resolution_reason=(
                "Schwab returned 2 orders within the match window"
                if ambiguity_kind == "multi_match_within_window"
                else "Pass-2 surfaced an ambiguity"
            ),
            expected_json=json.dumps({"price": 7.50}),
            actual_json=json.dumps({"_pass2": True}),
        )
        conn.commit()
    finally:
        conn.close()

    args = [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", choice_code,
        "--reason", "operator gate test",
    ]
    if custom_value is not None:
        args.extend(["--custom-value", custom_value])

    r = runner.invoke(main, args)
    assert r.exit_code == 0, r.output
    assert f"resolved discrepancy {did}" in r.output
    assert f"choice '{choice_code}'" in r.output
    assert "correction_id=" in r.output

    # Verify state.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
        assert row is not None
        assert row[0] == "operator_resolved_ambiguity", row
        assert row[1] == "operator", row
        n = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()[0]
        assert n == 1, n
    finally:
        conn.close()


# ===========================================================================
# §B — Missing --reason → non-zero exit.
# ===========================================================================


def test_resolve_ambiguity_missing_reason_errors(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "keep_journal_as_is",
        # NOTE: no --reason
    ])
    assert r.exit_code != 0
    # click 'Missing option' style message references --reason.
    assert "--reason" in r.output


# ===========================================================================
# §C — Missing --custom-value on a payload-required choice → exit 2 +
# shape description appears in the error message.
# ===========================================================================


def test_resolve_ambiguity_missing_custom_value_on_required_choice(
    cli_workspace,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "consolidate_using_operator_vwap",
        "--reason", "operator gate test",
        # NOTE: no --custom-value
    ])
    assert r.exit_code == 2, r.output
    assert "--custom-value" in r.output
    assert "consolidate_using_operator_vwap" in r.output
    # The expected_payload_shape_description for this choice is
    # '{"price": X.XX}' — assert the shape blurb is surfaced.
    assert '"price"' in r.output or "price" in r.output


# ===========================================================================
# §D — Malformed --custom-value JSON → exit 2.
# ===========================================================================


def test_resolve_ambiguity_malformed_custom_value_json(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "consolidate_using_operator_vwap",
        "--reason", "operator gate test",
        "--custom-value", "{not: valid json",
    ])
    assert r.exit_code == 2, r.output
    assert "--custom-value" in r.output.lower() or "json" in r.output.lower()


# ===========================================================================
# §E — Incompatible --choice for ambiguity_kind → exit 2.
# ===========================================================================


def test_resolve_ambiguity_incompatible_choice_for_kind(cli_workspace) -> None:
    """Plant a ``multi_partial_vs_consolidated`` row; pass a choice that
    only exists in a DIFFERENT kind's menu (``operator_truth`` lives in
    ``unknown_schwab_subtype`` / ``schwab_returned_no_match`` / etc., NOT
    ``multi_partial_vs_consolidated``)."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "operator_truth",
        "--reason", "operator gate test",
        "--custom-value", json.dumps({"price": 7.42}),
    ])
    assert r.exit_code == 2, r.output
    # CLI surfaces the per-kind menu in the error message.
    assert "multi_partial_vs_consolidated" in r.output
    assert "operator_truth" in r.output


# ===========================================================================
# §F — Service-owned-state values as --choice → exit 2 + routing hint.
# Manual-resolver-allowlist-tightness LOCK (NEW C.C lesson #1 carry-forward).
# ===========================================================================


@pytest.mark.parametrize("service_owned", [
    "auto_corrected_from_schwab",
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
])
def test_resolve_ambiguity_rejects_service_owned_state_as_choice(
    cli_workspace, service_owned,
) -> None:
    """The 4 service-owned ``resolution`` values must NOT be accepted as
    ``--choice`` values — those route through C.C canonical service
    entries (``apply_tier1_correction`` / ``apply_tier2_resolution`` /
    ``apply_tier3_override`` / pivot stamp), NOT operator-input.

    Discriminating signal: exit 2 + the error message must mention a
    routing hint so the operator knows where to go next.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", service_owned,
        "--reason", "operator gate test",
    ])
    assert r.exit_code == 2, r.output
    assert service_owned in r.output
    # Routing-hint substring: at least one of the canonical-entry markers
    # must appear (apply_tier* / override-correction / service-owned).
    assert (
        "service-owned" in r.output.lower()
        or "service owned" in r.output.lower()
        or "override-correction" in r.output
        or "apply_tier" in r.output
    )


# ===========================================================================
# §G — --schwab-api-call-id back-link wires through to
# schwab_api_calls.linked_correction_id.
# ===========================================================================


def test_resolve_ambiguity_schwab_api_call_id_backlinks(
    cli_workspace,
) -> None:
    """Plant a pending ambiguity + a schwab_api_calls row. Invoke with
    ``--schwab-api-call-id``. Assert:
      (a) new correction row's ``schwab_api_call_id`` populates;
      (b) the schwab_api_calls row's ``linked_correction_id`` back-links
          to the new correction row.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(conn, ticker="DHC")
        did = _plant_pending_ambiguity(
            conn, run_id=run_id, ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            trade_id=trade_id, fill_id=fill_id,
        )
        cur = conn.execute(
            "INSERT INTO schwab_api_calls ("
            "ts, endpoint, status, surface, environment, http_status"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2026-05-16T12:04:00", "accounts.orders.list",
                "success", "cli", "production", 200,
            ),
        )
        call_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", "keep_journal_as_is",
        "--reason", "operator gate test",
        "--schwab-api-call-id", str(call_id),
    ])
    assert r.exit_code == 0, r.output

    conn = sqlite3.connect(db_path)
    try:
        crow = conn.execute(
            "SELECT correction_id, schwab_api_call_id "
            "FROM reconciliation_corrections WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
        assert crow is not None
        correction_id, stamped_call_id = crow
        assert stamped_call_id == call_id, crow
        back_link = conn.execute(
            "SELECT linked_correction_id FROM schwab_api_calls "
            "WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        assert back_link is not None
        assert back_link[0] == correction_id, back_link
    finally:
        conn.close()


# ===========================================================================
# §H — Unknown discrepancy_id → friendly click error (non-zero).
# ===========================================================================


def test_resolve_ambiguity_unknown_discrepancy_errors(cli_workspace) -> None:
    runner, cfg, _db = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", "9999",
        "--choice", "keep_journal_as_is",
        "--reason", "operator gate test",
    ])
    assert r.exit_code != 0
    assert "9999" in r.output
