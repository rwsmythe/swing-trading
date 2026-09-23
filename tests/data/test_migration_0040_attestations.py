"""Arc 22-B Task 4 -- migration 0040 part 2: `entry_intent_attestations`.

Its SCHEMA IS THE EVIDENCE RULE. Each case is ONE mutation of a valid
real-shape row planted RAW on plain ``sqlite3`` -- the trigger/CHECK is tested
ALONE, with no service in the way (the service twin is Task 5's).

FORWARD RULE (R0.I): every migration image pins ``target_version=40``.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import open_connection, run_migrations
from swing.data.models import EntryIntentAttestation
from tests._22b_fixtures import (
    AMN_CANDIDATE_ID,
    AMN_ORDER_ID,
    LVE_ROW5,
    TRADE20,
    envelope,
    insert_row,
    record_envelope_readings,
    seed_amn_row5,
    seed_trade20,
)

TWIN_MSG = ("entry_intent unintended_execution requires its attestation row; "
            "use swing trade assign-intent")
ADMISSION_TRIGGERS = ("trg_eia_trade_binding", "trg_eia_cited_fields",
                      "trg_eia_audit_trail", "trg_eia_outcome", "trg_eia_tier2",
                      "trg_eia_structural")


def _v40(tmp_path: Path, name: str = "v40") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    try:
        run_migrations(c, target_version=40, backup_dir=root / "bak")
    finally:
        c.close()
    return root / "swing.db"


def _plain(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.isolation_level = None
    return c


def _snapshot(fields: list[str], trade: dict[str, Any] = TRADE20) -> str:
    return json.dumps({f: trade[f] for f in fields}, ensure_ascii=False,
                      sort_keys=True)


def tier2_row(**over: Any) -> dict[str, Any]:
    """Trade 20's admission as the service writes it (deployment leg)."""
    row = {
        "trade_id": 20, "assigned_value": "unintended_execution",
        "admission_tier": "contemporaneous_record",
        "trade_entry_date": "2026-08-07",
        "entry_fill_id": 41, "entry_fill_id_at_assignment": 41,
        "entry_broker_order_id": AMN_ORDER_ID,
        "placement_session": "2026-08-01",
        "placement_session_source": "schwab_envelope",
        "admitted_leg": "deployment",
        "leg_evidence_json": json.dumps(
            {"deployment_session": "2026-08-03", "placement_session": "2026-08-01"},
            sort_keys=True),
        "cited_latch_link_id": None, "cited_latch_terminal_rung": None,
        "cited_latch_terminal_session": None, "cited_latch_probe_json": None,
        "cited_fields_json": json.dumps(["notes", "why_now"]),
        "cited_text_snapshot_json": _snapshot(["notes", "why_now"]),
        "audit_trail_checked_at": "2026-09-23T12:00:00",
        "corrections_touching_cited_fields": 0,
        "outcome_known_at": "2026-08-11T16:00:00",
        "reason": "Stale A+ latch order fired after the mandate died",
        "applied_at": "2026-09-23T12:00:00", "applied_by": "operator",
    }
    row.update(over)
    return row


def _world(tmp_path: Path, name: str = "w", *, trade: dict | None = None,
           fill41_env: str | None = None, with_outcome: bool = True,
           outcome_dt: str | None = None) -> sqlite3.Connection:
    c = _plain(_v40(tmp_path, name))
    seed_amn_row5(c)
    seed_trade20(c, with_outcome=with_outcome, **(trade or {}))
    if fill41_env is not None:
        c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = 41",
                  (fill41_env,))
    if outcome_dt is not None:
        c.execute("UPDATE fills SET fill_datetime = ? WHERE fill_id = 44",
                  (outcome_dt,))
    record_envelope_readings(c)
    return c


def _plant(c: sqlite3.Connection, row: dict[str, Any]) -> str | None:
    """INSERT raw; None if it landed, else the refusing message."""
    try:
        insert_row(c, "entry_intent_attestations", row)
    except sqlite3.IntegrityError as exc:
        return str(exc)
    return None


# ---------------------------------------------------------------------------
# The structural baseline (a minted LINK for the fill's order; F3 (a) + N5 (b))
# ---------------------------------------------------------------------------
FTRE_TRADE_ID = 30


def _structural_world(tmp_path: Path, name: str = "s") -> tuple[sqlite3.Connection, dict]:
    from tests._latch_link_fixtures_22a import BROKER_ORDER_ID, accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c = _plain(_v40(tmp_path, name))
    cand = seed_link_fire(c)
    accept_order(c, cand)
    link_id = c.execute("SELECT link_id FROM latch_order_mandate_links "
                        "WHERE broker_order_id = ?", (BROKER_ORDER_ID,)).fetchone()[0]
    seed_trade20(c, id=FTRE_TRADE_ID, ticker="FTRE")
    fill_id = c.execute("SELECT fill_id FROM fills WHERE trade_id = ? AND "
                        "action = 'entry'", (FTRE_TRADE_ID,)).fetchone()[0]
    c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
              (envelope(schwab_order_id=BROKER_ORDER_ID,
                        schwab_instrument_symbol="FTRE"), fill_id))
    record_envelope_readings(c)
    return c, {"link_id": link_id, "candidate_id": cand, "fill_id": fill_id,
               "order_id": BROKER_ORDER_ID}


def structural_row(ids: dict, **over: Any) -> dict[str, Any]:
    probe = {
        "decline_reason": "mandate_not_alive", "clear_reason": "invalidation",
        "clear_session": "2026-08-06", "horizon_session": "2026-08-14",
        "bars_through": "2026-08-06", "freeze_tier": "pre_barrier_reconstructed",
        "link_id": ids["link_id"], "fire_candidate_id": ids["candidate_id"],
    }
    probe.update(over.pop("probe", {}))
    row = tier2_row(
        trade_id=FTRE_TRADE_ID, entry_fill_id=ids["fill_id"],
        entry_fill_id_at_assignment=ids["fill_id"],
        entry_broker_order_id=ids["order_id"], admission_tier="structural",
        placement_session=None, placement_session_source=None,
        admitted_leg=None, leg_evidence_json=None,
        cited_latch_link_id=ids["link_id"],
        cited_latch_terminal_rung=probe["clear_reason"],
        cited_latch_terminal_session=probe["clear_session"],
        cited_latch_probe_json=json.dumps(probe, sort_keys=True),
    )
    row.update(over)
    return row


def test_a_valid_tier2_row_inserts_b22_50(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        assert _plant(c, tier2_row()) is None
        # the variant citing thesis + emotional_state beside a descriptive field
        c2 = _world(tmp_path, "w2")
        fields = ["emotional_state_pre_trade", "notes", "thesis"]
        assert _plant(c2, tier2_row(
            cited_fields_json=json.dumps(fields),
            cited_text_snapshot_json=_snapshot(fields))) is None
        c2.close()
    finally:
        c.close()


def test_a_valid_structural_row_inserts_b22_51(tmp_path: Path) -> None:
    c, ids = _structural_world(tmp_path)
    try:
        assert _plant(c, structural_row(ids)) is None
    finally:
        c.close()


_NULL_CASES = {
    "admission_tier": lambda ids: tier2_row(admission_tier=None),
    "assigned_value": lambda ids: tier2_row(assigned_value=None),
    "trade_entry_date": lambda ids: tier2_row(trade_entry_date=None),
    "entry_fill_id_at_assignment": lambda ids: tier2_row(entry_fill_id_at_assignment=None),
    "tier2_placement_session": lambda ids: tier2_row(placement_session=None),
    "tier2_placement_session_source": lambda ids: tier2_row(placement_session_source=None),
    "tier2_admitted_leg": lambda ids: tier2_row(admitted_leg=None),
    "tier2_leg_evidence_json": lambda ids: tier2_row(leg_evidence_json=None),
    "cited_fields_json": lambda ids: tier2_row(cited_fields_json=None),
    "cited_text_snapshot_json": lambda ids: tier2_row(cited_text_snapshot_json=None),
    "audit_trail_checked_at": lambda ids: tier2_row(audit_trail_checked_at=None),
    "corrections_touching_cited_fields":
        lambda ids: tier2_row(corrections_touching_cited_fields=None),
    "reason": lambda ids: tier2_row(reason=None),
    "applied_at": lambda ids: tier2_row(applied_at=None),
    "applied_by": lambda ids: tier2_row(applied_by=None),
    "structural_link": lambda ids: structural_row(ids, cited_latch_link_id=None),
    "structural_rung": lambda ids: structural_row(ids, cited_latch_terminal_rung=None),
    "structural_terminal_session":
        lambda ids: structural_row(ids, cited_latch_terminal_session=None),
    "structural_probe": lambda ids: structural_row(ids, cited_latch_probe_json=None),
}


@pytest.mark.parametrize("case", list(_NULL_CASES))
def test_each_check_null_mutation_does_not_pass_b22_52(tmp_path: Path, case: str) -> None:
    if case.startswith("structural"):
        c, ids = _structural_world(tmp_path)
    else:
        c, ids = _world(tmp_path), {}
    try:
        assert _plant(c, _NULL_CASES[case](ids)) is not None, case
    finally:
        c.close()


def test_terminal_session_equal_to_entry_refuses_b22_53(tmp_path: Path) -> None:
    c, ids = _structural_world(tmp_path)
    try:
        msg = _plant(c, structural_row(ids, probe={"clear_session": "2026-08-07"}))
        assert msg is not None and "CHECK" in msg
    finally:
        c.close()


def test_terminal_session_day_before_entry_admits_b22_54(tmp_path: Path) -> None:
    c, ids = _structural_world(tmp_path)
    try:
        assert _plant(c, structural_row(ids, probe={"clear_session": "2026-08-06"})) is None
    finally:
        c.close()


_BAD_DATES = ("2026-00-01", "2026-8-1", "2026-02-30")


@pytest.mark.parametrize("column,value", [
    *[("trade_entry_date", d) for d in _BAD_DATES],
    *[("placement_session", d) for d in _BAD_DATES],
    *[("cited_latch_terminal_session", d) for d in _BAD_DATES],
    ("outcome_known_at", "2026-08-11 16:00:00"),
    ("outcome_known_at", "2026-00-11T16:00:00"),
    ("outcome_known_at", "0000-08-11T16:00:00"),
    ("outcome_known_at", "2026-08-11T24:00:00"),
])
def test_malformed_dates_refuse_b22_77(tmp_path: Path, column: str, value: str) -> None:
    if column == "cited_latch_terminal_session":
        c, ids = _structural_world(tmp_path)
        row = structural_row(ids, probe={"clear_session": value})
    else:
        c = _world(tmp_path)
        row = tier2_row(**{column: value})
    try:
        assert _plant(c, row) is not None
    finally:
        c.close()


def _deployment_at(tmp_path: Path, placement: str) -> str | None:
    c = _world(tmp_path, f"d{placement}", fill41_env=envelope(entry_date=placement))
    try:
        return _plant(c, tier2_row(
            placement_session=placement,
            leg_evidence_json=json.dumps({"deployment_session": "2026-08-03",
                                          "placement_session": placement})))
    finally:
        c.close()


def test_deployment_leg_boundary_2026_08_03_refuses_b22_55(tmp_path: Path) -> None:
    assert _deployment_at(tmp_path, "2026-08-03") is not None


def test_deployment_leg_boundary_2026_08_02_admits_b22_56(tmp_path: Path) -> None:
    assert _deployment_at(tmp_path, "2026-08-02") is None


def test_cited_field_outside_allowlist_refuses_b22_57(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        fields = ["notes", "pre_trade_locked_at"]
        msg = _plant(c, tier2_row(cited_fields_json=json.dumps(fields),
                                  cited_text_snapshot_json=_snapshot(fields)))
        assert msg is not None and "citation" in msg
    finally:
        c.close()


def test_tag_only_citation_refuses_b22_58(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        fields = ["emotional_state_pre_trade"]
        msg = _plant(c, tier2_row(cited_fields_json=json.dumps(fields),
                                  cited_text_snapshot_json=_snapshot(fields)))
        assert msg is not None and "citation" in msg
    finally:
        c.close()


def test_snapshot_not_equal_to_live_text_refuses_b22_59(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        one_space = {**TRADE20, "notes": TRADE20["notes"].replace(".  This", ". This")}
        msg = _plant(c, tier2_row(
            cited_text_snapshot_json=_snapshot(["notes", "why_now"], one_space)))
        assert msg is not None and "citation" in msg
    finally:
        c.close()


def _plant_rc(c: sqlite3.Connection, *, field_name: str, pre: str, applied: str) -> None:
    run_id = c.execute("INSERT INTO reconciliation_runs (source, started_ts, state) "
                       "VALUES ('schwab_api', '2026-09-07T12:00:00', 'completed')"
                       ).lastrowid
    disc = c.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, created_at) "
        "VALUES (?, 'stop_mismatch', 20, NULL, 'AMN', ?, '{}', '{}', 1, "
        "'journal_corrected', '2026-09-07T12:00:00')", (run_id, field_name)).lastrowid
    c.execute(
        "INSERT INTO reconciliation_corrections (discrepancy_id, applied_at, "
        "applied_by, correction_action, affected_table, affected_row_id, "
        "field_name, pre_correction_value_json, source_canonical_value_json, "
        "applied_value_json, correction_reason, reconciliation_run_id) "
        "VALUES (?, '2026-09-07T12:00:00', 'operator', 'operator_resolved_ambiguity', "
        "'trades', 20, ?, ?, ?, ?, 'fixture', ?)",
        (disc, field_name, pre, applied, applied, run_id))


def test_a_reconciliation_correction_on_a_cited_field_refuses_b22_60(
        tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        _plant_rc(c, field_name="notes", pre='{"notes": "x"}', applied='{"notes": "y"}')
        msg = _plant(c, tier2_row())
        assert msg is not None and "audit trail" in msg
    finally:
        c.close()


def test_a_multi_field_correction_carrying_notes_as_a_non_first_key_refuses_b22_61(
        tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        _plant_rc(c, field_name="current_stop",
                  pre='{"current_stop": 33.72, "notes": "x"}',
                  applied='{"current_stop": 33.8, "notes": "y"}')
        msg = _plant(c, tier2_row())
        assert msg is not None and "audit trail" in msg
    finally:
        c.close()


def test_a_provenance_correction_naming_trades_notes_refuses_b22_62(
        tmp_path: Path) -> None:
    """P2-a: a provenance row naming a citable text field is SCHEMA-UNREACHABLE
    today (its CHECK pins the three cohort keys), so it is planted under
    ``PRAGMA ignore_check_constraints=ON`` from the 22-A2 fully-cited fixture
    row, with the citation-graph trigger DROPPED in this test DB (the row is
    re-pointed at trade 20, whose citation graph the fixture does not carry)."""
    from tests._tier2_world_22a2 import base_last_word_payload

    payload = base_last_word_payload(tmp_path)
    c = _world(tmp_path)
    try:
        c.execute("DROP TRIGGER trg_provenance_corrections_citation_graph")
        c.execute("PRAGMA ignore_check_constraints=ON")
        prov = copy.deepcopy(payload)
        prov.update(provenance_correction_id=None, trade_id=20, entry_fill_id=41,
                    entry_fill_id_at_correction=41,
                    corrected_fields_json=json.dumps(
                        ["trades.hypothesis_label", "trades.notes"]))
        insert_row(c, "provenance_corrections", prov)
        c.execute("PRAGMA ignore_check_constraints=OFF")
        msg = _plant(c, tier2_row())
        assert msg is not None and "audit trail" in msg
    finally:
        c.close()


@pytest.mark.parametrize("first,second,recorded,admits", [
    ("stop", "exit", "second", False),
    ("trim", "stop", "second", False),
    ("trim", "stop", "first", True),
])
def test_outcome_not_the_earliest_non_entry_fill_refuses_b22_63(
        tmp_path: Path, first: str, second: str, recorded: str, admits: bool) -> None:
    c = _world(tmp_path, with_outcome=False)
    try:
        c.execute("UPDATE trades SET current_size = 0 WHERE id = 20")
        insert_row(c, "fills", {"trade_id": 20, "fill_datetime": "2026-08-10T16:00:00",
                                "action": first, "quantity": 2.0, "price": 34.0})
        insert_row(c, "fills", {"trade_id": 20, "fill_datetime": "2026-08-11T16:00:00",
                                "action": second, "quantity": 3.0, "price": 33.73})
        at = "2026-08-10T16:00:00" if recorded == "first" else "2026-08-11T16:00:00"
        msg = _plant(c, tier2_row(outcome_known_at=at))
        assert (msg is None) is admits, msg
    finally:
        c.close()


def test_tier2_with_a_link_for_the_order_refuses_b22_64(tmp_path: Path) -> None:
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c = _world(tmp_path)
    try:
        accept_order(c, seed_link_fire(c), actual_broker_order_id=AMN_ORDER_ID)
        msg = _plant(c, tier2_row())
        assert msg is not None and "contemporaneous_record" in msg
    finally:
        c.close()


def test_tier2_with_an_intent_naming_the_order_refuses_b22_65(tmp_path: Path) -> None:
    """An order-naming intent with NO link: the minting trigger is DROPPED in
    this test DB so the validity row lands without minting (the N5 (b) shape)."""
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c = _world(tmp_path)
    try:
        minting = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND tbl_name='latch_order_intents' AND sql LIKE "
            "'%INSERT INTO latch_order_mandate_links%'")]
        assert minting, "the link-minting trigger was not found"
        for name in minting:
            c.execute(f"DROP TRIGGER {name}")
        accept_order(c, seed_link_fire(c), actual_broker_order_id=AMN_ORDER_ID)
        assert c.execute("SELECT COUNT(*) FROM latch_order_mandate_links"
                         ).fetchone()[0] == 0
        msg = _plant(c, tier2_row())
        assert msg is not None and "contemporaneous_record" in msg
    finally:
        c.close()


def test_no_order_id_and_a_ticker_link_refuses_b22_66(tmp_path: Path) -> None:
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    no_id = json.dumps({k: v for k, v in json.loads(envelope()).items()
                        if k != "schwab_order_id"})
    c = _world(tmp_path, fill41_env=no_id)
    try:
        row = tier2_row(entry_broker_order_id=None)
        assert _plant(c, row) is None  # control: no link for the ticker yet
    finally:
        c.close()
    c = _world(tmp_path, "w_link", fill41_env=no_id)
    try:
        from tests._latch_link_fixtures_22a import (
            insert_intent,
            place_row,
            validity_row,
        )
        cand = seed_link_fire(c, run_id=500, ticker="AMN",
                              action_session_date="2026-08-03")
        amn = {"run_id": 500, "ticker": "AMN", "detection_date": "2026-08-03"}
        place_id = insert_intent(c, place_row(cand, idempotency_key="amn-place", **amn))
        insert_intent(c, validity_row(cand, place_id, key="amn-validity",
                                      actual_broker_order_id="999", **amn))
        assert c.execute("SELECT COUNT(*) FROM latch_order_mandate_links "
                         "WHERE ticker = 'AMN'").fetchone()[0] == 1
        msg = _plant(c, tier2_row(entry_broker_order_id=None))
        assert msg is not None and "contemporaneous_record" in msg
    finally:
        c.close()


# ---- the leg twins (R0.H), a second AMN telemetry row planted raw ----------
def _speaking_row(c: sqlite3.Connection, *, first: str, ever: int,
                  session: str = "2026-08-05", view_id: int = 6) -> dict:
    row = {**LVE_ROW5, "view_event_id": view_id, "view_session_date": session,
           "first_viewed_ts": first, "last_viewed_ts": first,
           "actionable_at_first_view": ever, "actionable_at_last_view": ever,
           "actionable_ever_viewed": ever, "view_count": 1}
    insert_row(c, "latch_view_events", row)
    return row


def _telemetry_evidence(rows: list[dict]) -> str:
    return json.dumps({"telemetry_rows": [
        {"view_event_id": r["view_event_id"],
         "actionable_ever_viewed": r["actionable_ever_viewed"],
         "first_viewed_ts": r["first_viewed_ts"],
         "view_session_date": r["view_session_date"]} for r in rows]},
        sort_keys=True)


def _at_placement(tmp_path: Path, placement: str, name: str) -> sqlite3.Connection:
    return _world(tmp_path, name, fill41_env=envelope(entry_date=placement))


def test_pre_row_with_actionable_1_refuses_b22_67(tmp_path: Path) -> None:
    c = _at_placement(tmp_path, "2026-08-06", "p67")
    try:
        r = _speaking_row(c, first="2026-08-05T09:00:00", ever=1)
        msg = _plant(c, tier2_row(placement_session="2026-08-06",
                                  admitted_leg="telemetry",
                                  leg_evidence_json=_telemetry_evidence([r])))
        assert msg is not None and "contemporaneous_record" in msg
    finally:
        c.close()


def test_telemetry_leg_without_a_pre_row_refuses_b22_68(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        msg = _plant(c, tier2_row(admitted_leg="telemetry",
                                  leg_evidence_json=_telemetry_evidence([LVE_ROW5])))
        assert msg is not None and "contemporaneous_record" in msg
    finally:
        c.close()


def test_deployment_leg_with_a_pre_row_refuses_b22_69(tmp_path: Path) -> None:
    c = _at_placement(tmp_path, "2026-08-06", "p69")
    try:
        _speaking_row(c, first="2026-08-05T09:00:00", ever=0)
        msg = _plant(c, tier2_row(
            placement_session="2026-08-06",
            leg_evidence_json=json.dumps({"deployment_session": "2026-08-03",
                                          "placement_session": "2026-08-06"})))
        assert msg is not None
    finally:
        c.close()


def test_a_backfilled_row_before_0803_never_speaks_b22_70(tmp_path: Path) -> None:
    c = _at_placement(tmp_path, "2026-08-02", "p70")
    try:
        _speaking_row(c, first="2026-08-02T09:00:00", ever=1, session="2026-08-02")
        assert _plant(c, tier2_row(
            placement_session="2026-08-02",
            leg_evidence_json=json.dumps({"deployment_session": "2026-08-03",
                                          "placement_session": "2026-08-02"}))) is None
    finally:
        c.close()


def test_first_view_on_0803_speaks_b22_76(tmp_path: Path) -> None:
    c = _at_placement(tmp_path, "2026-08-03", "p76")
    try:
        r = _speaking_row(c, first="2026-08-03T00:00:00", ever=0, session="2026-08-04")
        assert _plant(c, tier2_row(placement_session="2026-08-03",
                                   admitted_leg="telemetry",
                                   leg_evidence_json=_telemetry_evidence([r]))) is None
    finally:
        c.close()


def _mut_evidence(kind: str, c: sqlite3.Connection, ids: dict) -> dict:
    if kind.startswith("telemetry"):
        r6 = _speaking_row(c, first="2026-08-05T09:00:00", ever=0)
        r7 = _speaking_row(c, first="2026-08-05T10:00:00", ever=0,
                           session="2026-08-06", view_id=7)
        rows = [r6, r7]
        if kind == "telemetry_extra_id":
            rows = [r6, r7, {**r7, "view_event_id": 99}]
        elif kind == "telemetry_missing_pre_id":
            rows = [r6]
        elif kind == "telemetry_altered_first_viewed":
            rows = [r6, {**r7, "first_viewed_ts": "2026-08-05T10:00:01"}]
        return tier2_row(placement_session="2026-08-06", admitted_leg="telemetry",
                         leg_evidence_json=_telemetry_evidence(rows))
    if kind == "deployment_other_placement":
        return tier2_row(leg_evidence_json=json.dumps(
            {"deployment_session": "2026-08-03", "placement_session": "2026-07-31"}))
    if kind == "deployment_extra_key":
        return tier2_row(leg_evidence_json=json.dumps(
            {"deployment_session": "2026-08-03", "placement_session": "2026-08-01",
             "x": 1}))
    probe = {"link_id": ids.get("link_id", 0) + 1} if kind == "probe_link_id" else (
        {"clear_reason": "horizon"} if kind == "probe_clear_reason" else (
            {"clear_session": "2026-08-05"} if kind == "probe_clear_session"
            else {"decline_reason": "frozen_value_drift"}))
    row = structural_row(ids)
    blob = json.loads(row["cited_latch_probe_json"])
    blob.update(probe)
    row["cited_latch_probe_json"] = json.dumps(blob, sort_keys=True)
    return row


_EVIDENCE_MUTATIONS = (
    "telemetry_extra_id", "telemetry_missing_pre_id", "telemetry_altered_first_viewed",
    "deployment_other_placement", "deployment_extra_key", "probe_link_id",
    "probe_clear_reason", "probe_clear_session", "probe_decline_reason",
)


@pytest.mark.parametrize("kind", _EVIDENCE_MUTATIONS)
def test_valid_json_but_wrong_evidence_refuses_b22_79(tmp_path: Path, kind: str) -> None:
    if kind.startswith("probe"):
        c, ids = _structural_world(tmp_path)
    elif kind.startswith("telemetry"):
        c, ids = _at_placement(tmp_path, "2026-08-06", "e"), {}
    else:
        c, ids = _world(tmp_path), {}
    try:
        assert _plant(c, _mut_evidence(kind, c, ids)) is not None, kind
    finally:
        c.close()


def test_the_telemetry_evidence_control_admits_b22_79(tmp_path: Path) -> None:
    c = _at_placement(tmp_path, "2026-08-06", "e_ok")
    try:
        r6 = _speaking_row(c, first="2026-08-05T09:00:00", ever=0)
        r7 = _speaking_row(c, first="2026-08-05T10:00:00", ever=0,
                           session="2026-08-06", view_id=7)
        assert _plant(c, tier2_row(placement_session="2026-08-06",
                                   admitted_leg="telemetry",
                                   leg_evidence_json=_telemetry_evidence([r7, r6]))) is None
    finally:
        c.close()


@pytest.mark.parametrize("column", ["cited_fields_json", "cited_text_snapshot_json",
                                    "leg_evidence_json", "cited_latch_probe_json"])
def test_malformed_json_is_a_constraint_abort_b22_48(tmp_path: Path, column: str) -> None:
    if column == "cited_latch_probe_json":
        c, ids = _structural_world(tmp_path)
        row = structural_row(ids, cited_latch_probe_json="x")
    else:
        c = _world(tmp_path)
        row = tier2_row(**{column: "x"})
    try:
        with pytest.raises(sqlite3.IntegrityError):
            insert_row(c, "entry_intent_attestations", row)
    finally:
        c.close()


# ---------------------------------------------------------------------------
# RULING G1b -- the binding trigger reads the STORED reading, never the envelope
# ---------------------------------------------------------------------------
BINDING_MSG = "does not bind to its trade"


def _plant_reading(c: sqlite3.Connection, fill_id: int, raw: str, *,
                   state: str = "canonical", order_id: str | None = None,
                   symbol: str | None = None) -> None:
    """A reading planted RAW (a forged or older-grammar row -- the case the
    stored reading is trusted for BY THE TRIGGER, which compares stored values
    only)."""
    insert_row(c, "fill_envelope_identity", {
        "fill_id": fill_id, "envelope_raw": raw, "envelope_state": state,
        "broker_order_id": order_id, "instrument_symbol": symbol,
        "canonicalizer_version": "planted", "recorded_ts": "2026-09-23T00:00:00Z"})


def test_an_order_id_other_than_the_stored_canonical_reading_aborts_b22_210(
        tmp_path: Path) -> None:
    """The twin ALONE on plain sqlite3. (a) the real reading: a row naming an
    order id one byte off ABORTS. (b) a stored reading that DISAGREES with the
    document's own text: the row naming the DOCUMENT's id ABORTS and the row
    naming the STORED id passes -- stored values only. Pre-fix (the retired
    json_extract bind) (b) inverts: the document's id passed, the stored one
    aborted."""
    c = _world(tmp_path)
    try:
        msg = _plant(c, tier2_row(entry_broker_order_id=AMN_ORDER_ID + "0"))
        assert msg is not None and BINDING_MSG in msg, msg
        assert _plant(c, tier2_row()) is None  # the b22_50 control
    finally:
        c.close()
    doc = envelope(shares=6)  # a new document for fill 41, never read
    c = _world(tmp_path, "forged", fill41_env=None)
    try:
        c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = 41",
                  (doc,))
        _plant_reading(c, 41, doc, order_id="999", symbol="AMN")
        msg = _plant(c, tier2_row())  # names the document's own order id
        assert msg is not None and BINDING_MSG in msg, msg
        assert _plant(c, tier2_row(entry_broker_order_id="999")) is None
    finally:
        c.close()


def test_an_order_id_over_a_refused_reading_aborts_b22_211(tmp_path: Path) -> None:
    """A padded order id is a document the authority REFUSES, so its stored
    reading is `refused` and names no order: a raw row naming the id ABORTS.
    Pre-fix the json_extract bind read the padded value, and the row naming it
    PASSED."""
    padded = " " + AMN_ORDER_ID + " "
    c = _world(tmp_path, fill41_env=envelope(schwab_order_id=padded))
    try:
        state = c.execute(
            "SELECT fei.envelope_state FROM fill_envelope_identity fei "
            "JOIN fills f ON f.fill_id = fei.fill_id "
            "AND fei.envelope_raw = f.schwab_source_value_json "
            "WHERE f.fill_id = 41").fetchone()
        assert state == ("refused",)
        for named in (padded, AMN_ORDER_ID):
            msg = _plant(c, tier2_row(entry_broker_order_id=named))
            assert msg is not None and BINDING_MSG in msg, (named, msg)
    finally:
        c.close()


def test_relabel_refused_when_trades_entry_intent_is_set_b22_71(tmp_path: Path) -> None:
    c = _world(tmp_path, trade={"entry_intent": "standard"})
    try:
        msg = _plant(c, tier2_row())
        assert msg is not None and "bind" in msg
    finally:
        c.close()


_UPDATE_MUTATIONS = {
    "trade_id": 21, "assigned_value": "unintended_execution ", "admission_tier":
    "structural", "trade_entry_date": "2026-08-06", "entry_fill_id_at_assignment": 44,
    "entry_broker_order_id": "x", "placement_session": "2026-07-31",
    "placement_session_source": "entry_date_fallback", "admitted_leg": "telemetry",
    "leg_evidence_json": "{}", "cited_fields_json": '["notes"]',
    "cited_text_snapshot_json": "{}", "audit_trail_checked_at": "x",
    "corrections_touching_cited_fields": 0, "outcome_known_at": None,
    "reason": "other", "applied_at": "x", "applied_by": "x",
    "entry_fill_id": None,  # a MANUAL nulling while fill 41 still exists
}


@pytest.mark.parametrize("column", list(_UPDATE_MUTATIONS))
def test_update_aborts_b22_72(tmp_path: Path, column: str) -> None:
    c = _world(tmp_path)
    try:
        assert _plant(c, tier2_row()) is None
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            c.execute(f"UPDATE entry_intent_attestations SET {column} = ?",
                      (_UPDATE_MUTATIONS[column],))
    finally:
        c.close()


def test_delete_aborts_b22_73(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        assert _plant(c, tier2_row()) is None
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            c.execute("DELETE FROM entry_intent_attestations")
    finally:
        c.close()


@pytest.mark.parametrize("form", ["INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE"])
def test_insert_or_replace_aborts_b22_74(tmp_path: Path, form: str) -> None:
    c = _world(tmp_path)
    try:
        assert _plant(c, tier2_row()) is None
        row = tier2_row(reason="a rewrite")
        with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
            c.execute(f"{form} INTO entry_intent_attestations ({', '.join(row)}) "
                      f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
        assert c.execute("SELECT reason FROM entry_intent_attestations"
                         ).fetchone()[0] != "a rewrite"
    finally:
        c.close()


def test_deleting_the_attested_entry_fill_is_not_blocked_b22_191(tmp_path: Path) -> None:
    """The REAL split_into_partials on an attested trade's entry fill, with
    foreign_keys=ON, SUCCEEDS: entry_fill_id goes NULL and every other column
    is byte-unchanged. The attestation is planted raw with the admission
    triggers DROPPED in this test DB (its subject is the FK + the one UPDATE
    permit, not admission)."""
    from swing.data.db import ensure_schema
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution
    from tests.trades.test_apply_tier2_resolution import _seed_dhc_pending

    conn = ensure_schema(tmp_path / "split" / "swing.db") if (
        tmp_path / "split").mkdir() is None else None
    try:
        world = _seed_dhc_pending(conn)
        conn.commit()
        for name in ADMISSION_TRIGGERS:
            conn.execute(f"DROP TRIGGER {name}")
        tid, fid = world["trade_id"], world["fill_id"]
        edate = conn.execute("SELECT entry_date FROM trades WHERE id=?", (tid,)
                             ).fetchone()[0]
        fdt = conn.execute("SELECT fill_datetime FROM fills WHERE fill_id=?", (fid,)
                           ).fetchone()[0]
        row = tier2_row(trade_id=tid, trade_entry_date=edate, entry_fill_id=fid,
                        entry_fill_id_at_assignment=fid, entry_broker_order_id=None,
                        placement_session="2026-04-01",
                        placement_session_source="entry_date_fallback",
                        leg_evidence_json=json.dumps(
                            {"deployment_session": "2026-08-03",
                             "placement_session": "2026-04-01"}),
                        outcome_known_at=None)
        insert_row(conn, "entry_intent_attestations", row)
        conn.commit()
        before = conn.execute("SELECT * FROM entry_intent_attestations").fetchone()
        qty = conn.execute("SELECT quantity FROM fills WHERE fill_id=?", (fid,)
                           ).fetchone()[0]
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        apply_tier2_resolution(
            conn, discrepancy_id=world["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=[
                {"qty": qty - 1, "price": 7.57, "fill_datetime": fdt},
                {"qty": 1, "price": 7.59, "fill_datetime": fdt},
            ],
            operator_reason="two partial executions")
        after = conn.execute("SELECT * FROM entry_intent_attestations").fetchone()
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(entry_intent_attestations)")]
    finally:
        conn.close()
    i = cols.index("entry_fill_id")
    assert before[i] == fid and after[i] is None
    assert [v for j, v in enumerate(after) if j != i] == [
        v for j, v in enumerate(before) if j != i]


def test_outcome_on_the_entry_session_refuses_b22_49(tmp_path: Path) -> None:
    c = _world(tmp_path, outcome_dt="2026-08-07T16:00:00")
    try:
        msg = _plant(c, tier2_row(outcome_known_at="2026-08-07T16:00:00"))
        assert msg is not None and "CHECK" in msg
    finally:
        c.close()
    c = _world(tmp_path, "next", outcome_dt="2026-08-08T16:00:00")
    try:
        assert _plant(c, tier2_row(outcome_known_at="2026-08-08T16:00:00")) is None
    finally:
        c.close()


def _model(row: dict) -> EntryIntentAttestation:
    return EntryIntentAttestation(attestation_id=None, **row)


_MODEL_MUTATIONS = {
    "attestation_id": {"attestation_id": 0},
    "assigned_value": {"assigned_value": "standard"},
    "admission_tier": {"admission_tier": "last_word"},
    "trade_entry_date": {"trade_entry_date": "2026-02-30"},
    "entry_fill_pairing": {"entry_fill_id": 44},
    "placement_session": {"placement_session": "2026-8-1"},
    "placement_session_source": {"placement_session_source": "guess"},
    "admitted_leg": {"admitted_leg": "vibes"},
    "leg_evidence_json": {"leg_evidence_json": "x"},
    "cited_fields_json": {"cited_fields_json": "{}"},
    "cited_fields_empty": {"cited_fields_json": "[]"},
    "cited_text_snapshot_json": {"cited_text_snapshot_json": "[]"},
    "corrections": {"corrections_touching_cited_fields": 1},
    "outcome_known_at": {"outcome_known_at": "2026-08-11 16:00:00"},
    "reason": {"reason": "   "},
    "paired_tier": {"admitted_leg": None},
    "deployment_bound": {"placement_session": "2026-08-03",
                         "leg_evidence_json": "{}"},
    "outcome_after_record": {"outcome_known_at": "2026-08-07T16:00:00"},
}


@pytest.mark.parametrize("case", list(_MODEL_MUTATIONS))
def test_model_post_init_mirrors_every_check_b22_75(case: str) -> None:
    row = tier2_row()
    over = dict(_MODEL_MUTATIONS[case])
    aid = over.pop("attestation_id", None)
    row.update(over)
    with pytest.raises(ValueError, match="EntryIntentAttestation"):
        EntryIntentAttestation(attestation_id=aid, **row)
    _model(tier2_row())  # the control constructs


def test_model_post_init_mirrors_the_structural_checks_b22_75() -> None:
    ids = {"link_id": 1, "candidate_id": 2, "fill_id": 41, "order_id": "1"}
    EntryIntentAttestation(attestation_id=None, **structural_row(ids))
    for over in ({"cited_latch_terminal_rung": "fill"},
                 {"cited_latch_terminal_session": "2026-08-07"},
                 {"cited_latch_probe_json": "x"}):
        with pytest.raises(ValueError, match="EntryIntentAttestation"):
            EntryIntentAttestation(attestation_id=None, **{**structural_row(ids), **over})


# ---------------------------------------------------------------------------
# CHARC-S3 condition 2: the two unattested `trades` twins, raw
# ---------------------------------------------------------------------------
def _twin_world(tmp_path: Path, name: str, *, drop: str | None = None) -> sqlite3.Connection:
    c = _world(tmp_path, name)
    if drop:
        c.execute(f"DROP TRIGGER {drop}")
    return c


def test_raw_update_to_the_value_without_an_attestation_aborts_b22_202(
        tmp_path: Path) -> None:
    sql = "UPDATE trades SET entry_intent = 'unintended_execution' WHERE id = 20"
    c = _twin_world(tmp_path, "t202")
    try:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            c.execute(sql)
        assert TWIN_MSG in str(exc.value)
    finally:
        c.close()
    ctl = _twin_world(tmp_path, "t202c",
                      drop="trg_trades_entry_intent_unattested_update")
    try:
        ctl.execute(sql)  # the twin is the refusing object
    finally:
        ctl.close()


def test_the_same_update_with_a_raw_planted_attestation_passes_b22_203(
        tmp_path: Path) -> None:
    c = _twin_world(tmp_path, "t203")
    try:
        assert _plant(c, tier2_row()) is None
        c.execute("UPDATE trades SET entry_intent = 'unintended_execution' "
                  "WHERE id = 20")
        assert c.execute("SELECT entry_intent FROM trades WHERE id = 20"
                         ).fetchone() == ("unintended_execution",)
        with pytest.raises(sqlite3.IntegrityError, match="entry_intent is attested"):
            c.execute("UPDATE trades SET entry_intent = 'standard' WHERE id = 20")
    finally:
        c.close()


@pytest.mark.parametrize("form", ["INSERT", "INSERT OR REPLACE"])
def test_raw_insert_of_a_trade_carrying_the_value_aborts_b22_204(
        tmp_path: Path, form: str) -> None:
    trade_id = 77 if form == "INSERT" else 20
    sql = (f"{form} INTO trades (id, ticker, entry_date, entry_price, "
           "initial_shares, initial_stop, current_stop, state, trade_origin, "
           "pre_trade_locked_at, entry_intent) VALUES (?, 'ZZZ', '2026-08-07', "
           "10, 1, 9, 9, 'closed', 'manual_off_pipeline', '2026-08-07T16:00:00', "
           "'unintended_execution')")
    c = _twin_world(tmp_path, "t204")
    try:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            c.execute(sql, (trade_id,))
        assert TWIN_MSG in str(exc.value)
    finally:
        c.close()
    ctl = _twin_world(tmp_path, "t204c",
                      drop="trg_trades_entry_intent_unattested_insert")
    try:
        ctl.execute(sql, (trade_id,))  # the INSERT twin is the refusing object
    finally:
        ctl.close()


def test_amn_candidate_constant_is_the_live_one() -> None:
    assert AMN_CANDIDATE_ID == 11926
