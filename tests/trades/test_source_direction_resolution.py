"""Arc 4b Task 10 — the no-FK-safe source-direction resolve branch + menu."""
import json

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_ambiguity_choices import choice_menu_for_discrepancy
from swing.trades.reconciliation_auto_correct import (
    SourceResolutionRejected,
    apply_source_direction_resolution,
)


def _make_pending(conn, *, flag_reason="unrecognized_income_description",
                  tx_id="T9001", net_amount=5.0, iso_date="2026-06-01",
                  candidate_ids=None):
    cur = conn.execute(
        "INSERT INTO reconciliation_runs (source, state, started_ts, "
        "period_start, period_end) VALUES ('schwab_api', 'completed', '1', "
        "'2026-05-01', '2026-05-31')")
    run_id = int(cur.lastrowid)
    envelope = {
        "transactionId": tx_id, "date": iso_date, "type": "DIVIDEND_OR_INTEREST",
        "net_amount": net_amount, "description": None, "flag_reason": flag_reason,
    }
    if candidate_ids is not None:
        envelope["candidate_cash_movement_ids"] = candidate_ids
    dcur = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "field_name, material_to_review, created_at, resolution, ambiguity_kind, "
        "expected_value_json, actual_value_json) VALUES (?, "
        "'cash_movement_mismatch', 'missing_journal_row', 1, '1', "
        "'pending_ambiguity_resolution', 'schwab_returned_no_match', ?, "
        "'{\"matched\": null}')",
        (run_id, json.dumps(envelope, sort_keys=True)))
    return int(dcur.lastrowid)


@pytest.fixture
def source_dir_pending(tmp_path):
    conn = ensure_schema(tmp_path / "sdr.db")

    def _make(**kw):
        did = _make_pending(conn, **kw)
        conn.commit()
        return conn, did
    return _make


def test_menu_routes_missing_journal_row_to_source_menu(source_dir_pending):
    conn, disc_id = source_dir_pending()
    from swing.data.repos.reconciliation import get_discrepancy
    disc = get_discrepancy(conn, discrepancy_id=disc_id)
    menu = choice_menu_for_discrepancy(disc)
    codes = {m.code for m in menu}
    assert codes == {
        "acknowledge_not_journal_event", "record_journal_row", "matched_existing_row"}


def test_acknowledge_not_journal_event_terminal(source_dir_pending):
    conn, disc_id = source_dir_pending(flag_reason="unrecognized_income_description")
    apply_source_direction_resolution(
        conn, discrepancy_id=disc_id,
        choice_code="acknowledge_not_journal_event",
        operator_reason="not a ledger event")
    res = conn.execute("SELECT resolution, ambiguity_kind FROM "
                       "reconciliation_discrepancies WHERE discrepancy_id=?",
                       (disc_id,)).fetchone()
    assert res[0] == "acknowledged_immaterial"
    assert res[1] is None  # nulled to satisfy the CHECK


def test_record_journal_row_rejects_when_no_matching_ref(source_dir_pending):
    conn, disc_id = source_dir_pending()
    with pytest.raises(SourceResolutionRejected, match="swing journal cash"):
        apply_source_direction_resolution(
            conn, discrepancy_id=disc_id, choice_code="record_journal_row",
            operator_reason="x")


def test_record_journal_row_succeeds_when_verified(source_dir_pending):
    conn, disc_id = source_dir_pending(
        flag_reason="unrecognized_income_description", tx_id="T777",
        net_amount=3.0, iso_date="2026-06-01")
    # Operator records the matching journal row (ref==transactionId, kind in
    # the admitted income set, amount + date match).
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-06-01','interest',3.0,'T777',NULL)")
    apply_source_direction_resolution(
        conn, discrepancy_id=disc_id, choice_code="record_journal_row",
        operator_reason="recorded as interest")
    res = conn.execute("SELECT resolution FROM reconciliation_discrepancies "
                       "WHERE discrepancy_id=?", (disc_id,)).fetchone()[0]
    assert res == "operator_resolved_ambiguity"


def test_matched_existing_rejects_id_outside_candidate_list(source_dir_pending):
    conn, disc_id = source_dir_pending(
        flag_reason="fallback_multi_match", candidate_ids=[10, 11])
    with pytest.raises(SourceResolutionRejected, match="candidate"):
        apply_source_direction_resolution(
            conn, discrepancy_id=disc_id, choice_code="matched_existing_row",
            operator_custom_payload={"cash_movement_id": 999},
            operator_reason="x")


def test_terminal_row_cannot_be_re_resolved(source_dir_pending):
    # Codex R2 MAJOR — once a source-direction row is terminal, the service
    # itself rejects re-resolution (rewriting the terminal audit state).
    conn, disc_id = source_dir_pending(flag_reason="unrecognized_income_description")
    apply_source_direction_resolution(
        conn, discrepancy_id=disc_id,
        choice_code="acknowledge_not_journal_event", operator_reason="first")
    # Second attempt (e.g. flipping to a different terminal state) is rejected.
    with pytest.raises(SourceResolutionRejected, match="not pending"):
        apply_source_direction_resolution(
            conn, discrepancy_id=disc_id,
            choice_code="acknowledge_not_journal_event", operator_reason="again")


def test_matched_existing_rejects_wrong_kind_candidate(tmp_path):
    # Codex R1 MAJOR — a candidate id in the envelope list whose amount matches
    # but whose KIND is direction-incompatible must be REJECTED at resolve time
    # (spec §4.3(c): the row must still exist with matching kind/amount).
    conn = ensure_schema(tmp_path / "wk.db")
    # WRONG-direction candidate row: a 'withdraw' with a matching amount. The
    # transaction is a positive DIVIDEND_OR_INTEREST (net_amount=5.0) so the
    # admitted kinds are {deposit,interest,dividend}; 'withdraw' is invalid.
    bad_id = int(conn.execute(
        "INSERT INTO cash_movements (date, kind, amount, ref, note) "
        "VALUES ('2026-06-01','withdraw',5.0,NULL,'wrong-dir')").lastrowid)
    disc_id = _make_pending(
        conn, flag_reason="fallback_multi_match", net_amount=5.0,
        candidate_ids=[bad_id])
    conn.commit()
    with pytest.raises(SourceResolutionRejected, match="direction-compatible"):
        apply_source_direction_resolution(
            conn, discrepancy_id=disc_id, choice_code="matched_existing_row",
            operator_custom_payload={"cash_movement_id": bad_id},
            operator_reason="x")
