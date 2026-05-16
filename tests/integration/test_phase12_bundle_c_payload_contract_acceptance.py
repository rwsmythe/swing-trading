"""Phase 12 C.D T-D.11 — synthetic-fixture payload-contract acceptance test.

Underwrites the C.D gate S6a payload-contract step (per plan §E.11 + spec
§15.5 LOCKED revised mechanic). Table-driven across every payload-required
choice from spec §6.2.1 (11 entries) + every no-payload choice (7 entries).

Each case:
* runs against a fresh isolated tmp ``swing.db`` (no production-DB write);
* exercises both the parse-time payload-required error path (CLI without
  ``--custom-value``) AND the success-path (CLI with ``--custom-value``);
* per-choice-class assertions per plan §E.11 #3:
  - Mutation class (consolidate_using_operator_vwap / pick_schwab_record_<N>
    / operator_truth / operator_alternative):
    ``reconciliation_corrections.applied_value_json`` matches the supplied
    payload AND ``applied_value_json != pre_correction_value_json``.
  - Split class (split_into_partials): N+1 audit rows share one
    ``correction_set_id``; the original fill is DELETEd; N new fills exist
    with the operator-supplied (qty, price, fill_datetime) tuples.
  - Audit-only class (custom for any kind — T-C.3 V1 LOCK):
    ``applied_value_json == pre_correction_value_json`` bytewise (no
    mutation marker); ``correction_reason`` records the operator intent.

Per brief task T-D.11 §1.5 verify command:
``python -m pytest -m slow tests/integration/\
test_phase12_bundle_c_payload_contract_acceptance.py -v``

Brief-vs-impl deviations banked at return report (call out below):
* For ``pick_schwab_record_1`` the brief example uses payload key
  ``"qty"`` — the actual fills schema column is ``quantity`` and the
  multi-field-correction handler UPDATEs that column directly via
  interpolation. The CLI's documented payload-shape help text already
  pins ``quantity``. We use ``quantity`` for pick_schwab_record_1 so the
  end-to-end mutation actually succeeds (banked as brief deviation).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config

pytestmark = pytest.mark.slow


# ===========================================================================
# Fixture seeding helpers (mirrored from
# tests/cli/test_discrepancy_resolve_ambiguity_cli.py — kept self-contained
# so any future drift in that helper file does not silently re-couple us).
# ===========================================================================


def _make_workspace(tmp_path: Path) -> tuple[CliRunner, Path, Path]:
    """Create isolated project + home dir + run db-migrate to land v19."""
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
    """Insert a managing trade + its single entry fill; return ids."""
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
    trade_id: int,
    fill_id: int,
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
# Case tables — spec §6.2.1 menu mirrors.
# ===========================================================================


# (ambiguity_kind, choice_code, payload, choice_class)
# choice_class is one of: "mutation", "split", "audit_only"
PAYLOAD_REQUIRED_CASES: list[tuple[str, str, Any, str]] = [
    (
        "multi_partial_vs_consolidated",
        "consolidate_using_operator_vwap",
        {"price": 1.23},
        "mutation",
    ),
    (
        "multi_partial_vs_consolidated",
        "split_into_partials",
        [
            {"qty": 1, "price": 1.0, "fill_datetime": "2026-01-01T10:00:00"},
            {"qty": 1, "price": 2.0, "fill_datetime": "2026-01-01T10:00:01"},
        ],
        "split",
    ),
    (
        "multi_partial_vs_consolidated",
        "custom",
        {
            "audit_only": True,
            "operator_intent": "investigate broker statement next week",
        },
        "audit_only",
    ),
    (
        "multi_match_within_window",
        "pick_schwab_record_1",
        # Brief-vs-impl deviation: brief example wrote 'qty' but fills
        # schema column is 'quantity'; CLI's own help string also pins
        # 'quantity'. Using 'quantity' so the multi-field UPDATE succeeds.
        {
            "quantity": 5,
            "price": 9.99,
            "fill_datetime": "2026-01-01T10:00:00",
        },
        "mutation",
    ),
    (
        "multi_match_within_window",
        "custom",
        {"audit_only": True, "operator_intent": "investigate"},
        "audit_only",
    ),
    (
        "unknown_schwab_subtype",
        "operator_truth",
        {"price": 1.23},
        "mutation",
    ),
    (
        "unknown_schwab_subtype",
        "custom",
        {"audit_only": True, "operator_intent": "investigate"},
        "audit_only",
    ),
    (
        "field_shape_incompatible",
        "custom",
        {"audit_only": True, "operator_intent": "investigate"},
        "audit_only",
    ),
    (
        "schwab_returned_no_match",
        "operator_truth",
        {"price": 1.23},
        "mutation",
    ),
    (
        "validator_rejected",
        "operator_alternative",
        {"price": 2.0},
        "mutation",
    ),
    (
        "unsupported",
        "operator_truth",
        {"price": 1.23},
        "mutation",
    ),
]


# (ambiguity_kind, choice_code) — no-payload entries from spec §6.2.1.
NO_PAYLOAD_CASES: list[tuple[str, str]] = [
    ("multi_partial_vs_consolidated", "keep_journal_as_is"),
    ("multi_match_within_window", "mark_unmatched"),
    ("unknown_schwab_subtype", "acknowledge"),
    ("field_shape_incompatible", "acknowledge"),
    ("validator_rejected", "acknowledge"),
    ("unsupported", "acknowledge"),
    ("schwab_returned_no_match", "mark_unmatched"),
]


def _resolution_reason_for(ambiguity_kind: str) -> str:
    if ambiguity_kind == "multi_match_within_window":
        return (
            "Schwab returned 2 orders within the match window: "
            "[order_1, order_2]"
        )
    return "Pass-2 surfaced an ambiguity"


# ===========================================================================
# Tests
# ===========================================================================


@pytest.mark.parametrize(
    "ambiguity_kind,choice_code,payload,choice_class",
    PAYLOAD_REQUIRED_CASES,
)
def test_payload_required_choice_end_to_end(
    tmp_path: Path,
    ambiguity_kind: str,
    choice_code: str,
    payload: Any,
    choice_class: str,
) -> None:
    """For each (ambiguity_kind, payload-required choice):

    (a) parse-time rejection without ``--custom-value`` → non-zero exit;
    (b) success-path with ``--custom-value`` → exit 0 +
        ``reconciliation_discrepancies.resolution = 'operator_resolved_ambiguity'``;
    (c) per-choice-class assertions on
        ``reconciliation_corrections.applied_value_json``.
    """
    runner, cfg, db_path = _make_workspace(tmp_path)

    # Split-into-partials needs an original fill quantity equal to the sum
    # of the partial-fill qty entries. The synthetic payload sums to 2.
    seed_qty = 2.0 if choice_code == "split_into_partials" else 5.0

    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(
            conn, ticker="ZZZ", qty=seed_qty, price=7.50,
        )
        did = _plant_pending_ambiguity(
            conn,
            run_id=run_id,
            ticker="ZZZ",
            ambiguity_kind=ambiguity_kind,
            trade_id=trade_id,
            fill_id=fill_id,
            resolution_reason=_resolution_reason_for(ambiguity_kind),
            expected_json=json.dumps({"price": 7.50}),
            actual_json=json.dumps({"_pass2": True}),
        )
        conn.commit()
    finally:
        conn.close()

    # -----------------------------------------------------------------------
    # (a) Parse-time payload-required error WITHOUT --custom-value.
    # -----------------------------------------------------------------------
    args_no_payload = [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", choice_code,
        "--reason", (
            f"synthetic gate fixture; case {ambiguity_kind}/{choice_code}; "
            "isolated DB"
        ),
    ]
    r1 = runner.invoke(main, args_no_payload)
    assert r1.exit_code != 0, (
        f"expected non-zero exit when --custom-value omitted for "
        f"payload-required choice {choice_code!r}; output:\n{r1.output}"
    )
    assert "--custom-value" in r1.output, r1.output
    assert choice_code in r1.output, r1.output

    # Confirm the parse-time rejection did not mutate state.
    conn = sqlite3.connect(db_path)
    try:
        post_row = conn.execute(
            "SELECT resolution FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
        assert post_row is not None
        assert post_row[0] == "pending_ambiguity_resolution", post_row
        n_corrections_after_parse_fail = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()[0]
        assert n_corrections_after_parse_fail == 0
    finally:
        conn.close()

    # -----------------------------------------------------------------------
    # (b) Success path WITH --custom-value.
    # -----------------------------------------------------------------------
    reason = (
        f"synthetic gate fixture; case {ambiguity_kind}/{choice_code}; "
        "isolated DB"
    )
    args_ok = [
        "--config", str(cfg),
        "journal", "discrepancy", "resolve-ambiguity", str(did),
        "--choice", choice_code,
        "--reason", reason,
        "--custom-value", json.dumps(payload),
    ]
    r2 = runner.invoke(main, args_ok)
    assert r2.exit_code == 0, (
        f"success path for {ambiguity_kind}/{choice_code} returned "
        f"exit={r2.exit_code}; output:\n{r2.output}"
    )
    assert f"resolved discrepancy {did}" in r2.output, r2.output

    # -----------------------------------------------------------------------
    # (c) Per-choice-class assertions.
    # -----------------------------------------------------------------------
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT resolution, resolved_by FROM "
            "reconciliation_discrepancies WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
        assert row is not None
        assert row[0] == "operator_resolved_ambiguity", (
            f"case {ambiguity_kind}/{choice_code}: expected resolution="
            f"operator_resolved_ambiguity; got {row[0]!r}"
        )
        assert row[1] == "operator", row

        if choice_class == "split":
            # Split class — N+1 audit rows share one correction_set_id.
            audit_rows = conn.execute(
                "SELECT correction_id, correction_set_id, field_name, "
                "applied_value_json, pre_correction_value_json "
                "FROM reconciliation_corrections "
                "WHERE discrepancy_id = ? "
                "ORDER BY correction_id",
                (did,),
            ).fetchall()
            n_partials = len(payload)
            assert len(audit_rows) == n_partials + 1, (
                f"split: expected {n_partials + 1} audit rows; got "
                f"{len(audit_rows)}"
            )
            set_ids = {a[1] for a in audit_rows}
            assert len(set_ids) == 1, (
                f"split: all rows must share correction_set_id; got "
                f"{set_ids}"
            )
            # Anchor row is __delete__; the N others are __insert__.
            anchor = audit_rows[0]
            assert anchor[2] == "__delete__", anchor
            assert anchor[0] == anchor[1], (
                "anchor row's correction_set_id must self-reference "
                "(spec §3.1.1)"
            )
            insert_field_names = [a[2] for a in audit_rows[1:]]
            assert all(f == "__insert__" for f in insert_field_names), (
                f"non-anchor rows must carry field_name='__insert__'; "
                f"got {insert_field_names}"
            )

            # Original fill DELETEd; N new fills with payload tuples.
            # NOTE: SQLite reuses ROWIDs without AUTOINCREMENT, so we
            # cannot assert fill_id absence; the discriminating signal is
            # (a) the original fill's (price, fill_datetime) tuple is gone
            # from the fills table and (b) the new tuples match the
            # operator-supplied partials.
            orig_tuple_row = conn.execute(
                "SELECT 1 FROM fills WHERE trade_id = ? AND "
                "fill_datetime = ? AND price = ?",
                (trade_id, "2026-04-27T14:23:00", 7.50),
            ).fetchone()
            assert orig_tuple_row is None, (
                "split: original (fill_datetime=2026-04-27T14:23:00, "
                "price=7.50) tuple should be gone from fills after the "
                "consolidated-fill DELETE"
            )

            new_fills = conn.execute(
                "SELECT quantity, price, fill_datetime FROM fills "
                "WHERE trade_id = ? ORDER BY fill_datetime",
                (trade_id,),
            ).fetchall()
            assert len(new_fills) == n_partials, new_fills
            expected_tuples = sorted(
                (float(p["qty"]), float(p["price"]), str(p["fill_datetime"]))
                for p in payload
            )
            actual_tuples = sorted(
                (float(qty), float(price), str(fd))
                for (qty, price, fd) in new_fills
            )
            assert expected_tuples == actual_tuples, (
                f"split: new-fill tuples differ;\n"
                f"expected: {expected_tuples}\n"
                f"actual:   {actual_tuples}"
            )

        elif choice_class == "mutation":
            # Mutation class — single audit row; applied != pre.
            audit_rows = conn.execute(
                "SELECT correction_id, applied_value_json, "
                "pre_correction_value_json "
                "FROM reconciliation_corrections "
                "WHERE discrepancy_id = ?",
                (did,),
            ).fetchall()
            assert len(audit_rows) == 1, audit_rows
            _correction_id, applied_json, pre_json = audit_rows[0]
            assert applied_json != pre_json, (
                f"mutation class: applied_value_json must differ from "
                f"pre_correction_value_json. applied={applied_json!r} "
                f"pre={pre_json!r}"
            )
            applied = json.loads(applied_json)
            # All keys/values in the supplied payload must appear in
            # applied_value_json (the multi-field handler emits the merged
            # correction_target verbatim; the single-field handler emits
            # the single touched field).
            for key, value in payload.items():
                assert key in applied, (
                    f"mutation: expected key {key!r} in applied_value_json "
                    f"= {applied!r}"
                )
                # Numeric tolerance for float JSON round-trip.
                if isinstance(value, (int, float)):
                    assert float(applied[key]) == pytest.approx(
                        float(value)
                    ), (
                        f"mutation: applied[{key!r}]={applied[key]!r}; "
                        f"expected ~{value!r}"
                    )
                else:
                    assert applied[key] == value

        elif choice_class == "audit_only":
            # Audit-only — applied == pre bytewise; operator_intent in
            # correction_reason (via the suffix combiner in the handler).
            audit_rows = conn.execute(
                "SELECT correction_id, applied_value_json, "
                "pre_correction_value_json, correction_reason "
                "FROM reconciliation_corrections "
                "WHERE discrepancy_id = ?",
                (did,),
            ).fetchall()
            assert len(audit_rows) == 1, audit_rows
            _correction_id, applied_json, pre_json, correction_reason = (
                audit_rows[0]
            )
            assert applied_json == pre_json, (
                f"audit_only: applied_value_json must equal "
                f"pre_correction_value_json bytewise (no-mutation marker). "
                f"applied={applied_json!r} pre={pre_json!r}"
            )
            operator_intent = payload.get("operator_intent", "") if (
                isinstance(payload, dict)
            ) else ""
            if operator_intent:
                assert operator_intent in (correction_reason or ""), (
                    f"audit_only: operator_intent {operator_intent!r} "
                    f"must surface in correction_reason "
                    f"{correction_reason!r}"
                )
        else:
            raise AssertionError(f"unknown choice_class {choice_class!r}")
    finally:
        conn.close()


@pytest.mark.parametrize(
    "ambiguity_kind,choice_code", NO_PAYLOAD_CASES,
)
def test_no_payload_choice_end_to_end(
    tmp_path: Path,
    ambiguity_kind: str,
    choice_code: str,
) -> None:
    """For each no-payload (ambiguity_kind, choice_code):

    Invoke CLI WITHOUT ``--custom-value`` → assert exit 0 +
    discrepancy moves to ``operator_resolved_ambiguity`` +
    ``applied_value_json == pre_correction_value_json`` bytewise
    (no-mutation marker per the audit-only audit shape).
    """
    runner, cfg, db_path = _make_workspace(tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        trade_id, fill_id = _seed_trade_with_entry_fill(
            conn, ticker="ZZZ", qty=5.0, price=7.50,
        )
        did = _plant_pending_ambiguity(
            conn,
            run_id=run_id,
            ticker="ZZZ",
            ambiguity_kind=ambiguity_kind,
            trade_id=trade_id,
            fill_id=fill_id,
            resolution_reason=_resolution_reason_for(ambiguity_kind),
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
        "--reason", (
            f"synthetic gate fixture; case {ambiguity_kind}/{choice_code}; "
            "isolated DB"
        ),
    ]
    r = runner.invoke(main, args)
    assert r.exit_code == 0, (
        f"no-payload path for {ambiguity_kind}/{choice_code} returned "
        f"exit={r.exit_code}; output:\n{r.output}"
    )
    assert f"resolved discrepancy {did}" in r.output, r.output

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT resolution FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchone()
        assert row is not None
        assert row[0] == "operator_resolved_ambiguity", row

        audit_rows = conn.execute(
            "SELECT correction_id, applied_value_json, "
            "pre_correction_value_json "
            "FROM reconciliation_corrections "
            "WHERE discrepancy_id = ?",
            (did,),
        ).fetchall()
        assert len(audit_rows) == 1, audit_rows
        _correction_id, applied_json, pre_json = audit_rows[0]
        assert applied_json == pre_json, (
            f"no-payload class: applied_value_json must equal "
            f"pre_correction_value_json bytewise. "
            f"applied={applied_json!r} pre={pre_json!r}"
        )
    finally:
        conn.close()
