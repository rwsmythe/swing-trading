"""Arc 22-B Task 5 -- the assignment service `swing/trades/entry_intent_assignment.py`.

F4 shape: ``preflight`` reads only; ``assign`` rejects a caller-held
transaction, re-runs the preflight inside ONE ``BEGIN IMMEDIATE``, INSERTs the
attestation THEN updates ``trades`` -- both rows or neither. Every case runs on
a ``target_version=40`` image carrying the REAL triggers (the two unattested
twins, N4, the admission triggers), so a row the service admits is proven to
pass SQL and never merely assumed to.

Fixtures are the live row shapes of ``tests/_22b_fixtures.py`` (trade 20, fill
41's envelope, fill 44, AMN telemetry row 5). The structural cases drive the
REAL ``mandate_alive_at`` over a seeded AMN derivation (the 22-A probe-world
builders); the probe is never stubbed.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest

import swing.trades.entry_intent_assignment as svc
from swing.data.db import open_connection, run_migrations
from tests._22b_fixtures import (
    AMN_ORDER_ID,
    LVE_ROW5,
    TRADE20,
    envelope,
    insert_row,
    record_envelope_readings,
    seed_amn_row5,
    seed_trade20,
)
from tests._latch_probe_world_22a import (
    accept_and_link,
    probe_cfg,
    record_decision,
    seed_run,
    seed_trade,
    write_closes,
)

UNINT = "unintended_execution"
CITE = ["why_now", "notes"]  # deliberately NOT sorted: storage order is the service's
REASON = "Stale A+ latch order fired after the mandate died"
TWIN_MSG = "entry_intent unintended_execution requires its attestation row"
_KEEP = object()


def _db(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    try:
        run_migrations(c, target_version=40, backup_dir=root / "bak")
    finally:
        c.close()
    return root / "swing.db"


def _world(tmp_path: Path, name: str = "w", *, row5: bool = True,
           env: Any = _KEEP, with_outcome: bool = True,
           outcome_dt: str | None = None, **trade: Any):
    """Trade 20 (+ fill 41/44, + AMN row 5) on a v40 image. Committed."""
    path = _db(tmp_path, name)
    c = open_connection(path)
    if row5:
        seed_amn_row5(c)
    seed_trade20(c, with_outcome=with_outcome, **trade)
    if env is not _KEEP:
        c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = 41",
                  (env,))
    if outcome_dt is not None:
        c.execute("UPDATE fills SET fill_datetime = ? WHERE fill_id = 44",
                  (outcome_dt,))
    c.commit()
    return c, probe_cfg(path.parent), path


def _fresh(path: Path, sql: str, params: tuple = ()) -> list[tuple]:
    c = sqlite3.connect(path)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


def _nothing_written(path: Path, trade_id: int = 20) -> None:
    assert _fresh(path, "SELECT COUNT(*) FROM entry_intent_attestations") == [(0,)]
    assert _fresh(path, "SELECT entry_intent FROM trades WHERE id = ?",
                  (trade_id,)) == [(None,)]


def _assign(c, cfg, *, trade_id: int = 20, cite=CITE, reason: str = REASON,
            dry_run: bool = False):
    return svc.assign(c, cfg, trade_id=trade_id, cite=list(cite), reason=reason,
                      applied_by="operator", dry_run=dry_run)


def _row(path: Path, trade_id: int = 20) -> dict[str, Any]:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    try:
        r = c.execute("SELECT * FROM entry_intent_attestations WHERE trade_id = ?",
                      (trade_id,)).fetchone()
        return dict(r)
    finally:
        c.close()


def _speaking(c, *, first: str, ever: int, view_id: int = 6,
              session: str = "2026-08-05", last: str | None = None) -> dict:
    row = {**LVE_ROW5, "view_event_id": view_id, "view_session_date": session,
           "first_viewed_ts": first, "last_viewed_ts": last or first,
           "actionable_at_first_view": ever, "actionable_at_last_view": ever,
           "actionable_ever_viewed": ever, "view_count": 1}
    insert_row(c, "latch_view_events", row)
    c.commit()
    return row


# ---------------------------------------------------------------------------
# Trade 20 -- the acceptance shape, and the order of the two writes
# ---------------------------------------------------------------------------
def test_trade20_shape_admits_contemporaneous_record_b22_80(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        assert {"trg_trades_entry_intent_unattested_update",
                "trg_trades_entry_intent_unattested_insert",
                "trg_trades_entry_intent_attested_terminal"} <= names
        r = _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    assert r.admitted, r.message
    assert (r.tier, r.admitted_leg, r.placement_session, r.outcome_known_at) == (
        "contemporaneous_record", "deployment", "2026-08-01", "2026-08-11T16:00:00")
    assert r.attestation_id is not None
    row = _row(path)
    assert row["attestation_id"] == r.attestation_id
    assert row["cited_fields_json"] == '["notes", "why_now"]'
    expected_snap = json.dumps({"notes": TRADE20["notes"], "why_now": TRADE20["why_now"]},
                               ensure_ascii=False, sort_keys=True)
    assert row["cited_text_snapshot_json"] == expected_snap
    assert "disappeared.  This happened" in json.loads(expected_snap)["notes"]
    assert row["entry_broker_order_id"] == AMN_ORDER_ID
    assert row["placement_session_source"] == "schwab_envelope"
    assert json.loads(row["leg_evidence_json"]) == {
        "deployment_session": "2026-08-03", "placement_session": "2026-08-01"}
    assert (row["entry_fill_id"], row["entry_fill_id_at_assignment"]) == (41, 41)
    assert row["corrections_touching_cited_fields"] == 0
    assert row["trade_entry_date"] == "2026-08-07"
    assert (row["reason"], row["applied_by"]) == (REASON, "operator")
    assert _fresh(path, "SELECT entry_intent FROM trades WHERE id = 20") == [(UNINT,)]


def test_the_reversed_service_order_aborts_b22_205(tmp_path: Path, monkeypatch) -> None:
    """The trades UPDATE before the attestation INSERT: the update twin ABORTS
    with its own message, and a fresh connection sees neither row. The order is
    pinned by EXECUTION."""
    def reversed_write(conn, attestation):
        svc._set_trades_value(conn, attestation.trade_id)
        return svc.insert_attestation(conn, attestation)

    monkeypatch.setattr(svc, "_write", reversed_write)
    c, cfg, path = _world(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as exc:
            _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    assert TWIN_MSG in str(exc.value)
    _nothing_written(path)


def test_both_rows_or_neither_b22_81(tmp_path: Path, monkeypatch) -> None:
    seen: list[int] = []

    def boom(conn, trade_id):
        # AFTER the INSERT: the attestation is visible inside the transaction.
        seen.append(conn.execute(
            "SELECT COUNT(*) FROM entry_intent_attestations").fetchone()[0])
        raise RuntimeError("forced failure between the two statements")

    monkeypatch.setattr(svc, "_set_trades_value", boom)
    c, cfg, path = _world(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="forced failure"):
            _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    assert seen == [1]
    _nothing_written(path)


def test_caller_held_transaction_is_rejected_b22_82(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        c.execute("BEGIN")
        with pytest.raises(RuntimeError, match="transaction"):
            _assign(c, cfg)
        c.rollback()
    finally:
        c.close()
    _nothing_written(path)


def test_dry_run_writes_nothing_and_returns_the_predicates_b22_83(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, dry_run=True)
        assert not c.in_transaction
    finally:
        c.close()
    assert r.admitted is True and r.refusal_code is None and r.message is None
    assert (r.tier, r.admitted_leg, r.placement_session) == (
        "contemporaneous_record", "deployment", "2026-08-01")
    assert r.leg_evidence == {"deployment_session": "2026-08-03",
                              "placement_session": "2026-08-01"}
    assert r.corrections_by_table == {"reconciliation_corrections": 0,
                                      "provenance_corrections": 0}
    assert r.outcome_known_at == "2026-08-11T16:00:00"
    assert r.attestation_id is None
    _nothing_written(path)
    # RULING G1b: the dry run takes assign's own path (ensure inside BEGIN
    # IMMEDIATE) and ROLLBACKs it, the stored readings ensure appended included.
    assert _fresh(path, "SELECT COUNT(*) FROM fill_envelope_identity") == [(0,)]


# ---------------------------------------------------------------------------
# N1 -- the legs (R0.H window), one mutation each
# ---------------------------------------------------------------------------
def test_a_speaking_row_flipped_to_actionable_refuses_naming_the_offer_b22_84(
        tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, env=envelope(entry_date="2026-08-06"))
    try:
        _speaking(c, first="2026-08-05T09:00:00", ever=0)
        control = _assign(c, cfg, dry_run=True)
        c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 1, "
                  "actionable_at_last_view = 1 WHERE view_event_id = 6")
        c.commit()
        r = _assign(c, cfg)
    finally:
        c.close()
    assert control.admitted and control.admitted_leg == "telemetry"
    assert (r.admitted, r.refusal_code) == (False, "instrument_offered")
    assert "offered the order and did not fire" in r.message
    _nothing_written(path)


def test_no_telemetry_placement_0801_admits_on_deployment_b22_85(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, row5=False)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted and (r.admitted_leg, r.placement_session) == (
        "deployment", "2026-08-01")


def test_no_telemetry_placement_0803_refuses_b22_86(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, row5=False, env=envelope(entry_date="2026-08-03"))
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "instrument_existed")
    assert "2026-08-03" in r.message
    _nothing_written(path)


def test_no_telemetry_placement_0802_admits_boundary_twin_b22_87(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, row5=False, env=envelope(entry_date="2026-08-02"))
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted and (r.admitted_leg, r.placement_session) == (
        "deployment", "2026-08-02")


@pytest.mark.parametrize("entry_date,admits", [("2026-08-03", False),
                                               ("2026-08-02", True)])
def test_no_envelope_entry_date_0803_refuses_b22_88(
        tmp_path: Path, entry_date: str, admits: bool) -> None:
    c, cfg, path = _world(tmp_path, row5=False, env=None, entry_date=entry_date)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted is admits, r.message
    if admits:
        row = _row(path)
        assert (row["placement_session"], row["placement_session_source"],
                row["entry_broker_order_id"]) == (entry_date, "entry_date_fallback", None)
    else:
        assert r.refusal_code == "instrument_existed"


def test_oii_shape_routes_structural_not_tier2_b22_89(tmp_path: Path) -> None:
    """Actionable 1 in the PRE window + a validity row naming the order + its
    link: the structural path decides; tier 2 is never consulted."""
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c, cfg, path = _world(tmp_path, env=envelope(entry_date="2026-08-06"))
    try:
        _speaking(c, first="2026-08-05T09:00:00", ever=1)
        accept_order(c, seed_link_fire(c), actual_broker_order_id=AMN_ORDER_ID)
        c.commit()
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted is False
    assert r.refusal_code == "structural_unprovable", r.message
    assert r.tier is None
    _nothing_written(path)


def test_a_speaking_zero_row_before_placement_admits_on_telemetry_b22_90(
        tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, env=envelope(entry_date="2026-08-06"))
    try:
        _speaking(c, first="2026-08-05T09:00:00", ever=0)
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted, r.message
    evidence = {"telemetry_rows": [{
        "view_event_id": 6, "actionable_ever_viewed": 0,
        "first_viewed_ts": "2026-08-05T09:00:00", "view_session_date": "2026-08-05"}]}
    assert (r.admitted_leg, r.leg_evidence) == ("telemetry", evidence)
    row = _row(path)
    assert json.loads(row["leg_evidence_json"]) == evidence
    assert (row["placement_session"], row["admitted_leg"]) == ("2026-08-06", "telemetry")


def test_a_speaking_row_first_viewed_after_placement_is_silent_b22_105(
        tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, env=envelope(entry_date="2026-08-06"))
    try:
        _speaking(c, first="2026-08-07T09:00:00", ever=1, session="2026-08-07")
        r = _assign(c, cfg)
    finally:
        c.close()
    # silent (not an offer): leg 2 decides, and 08-06 >= 08-03 refuses
    assert (r.admitted, r.refusal_code) == (False, "instrument_existed")


def test_row5_flipped_to_1_is_still_silent_b22_106(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 1, "
                  "actionable_at_last_view = 1 WHERE view_event_id = 5")
        c.commit()
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted and r.admitted_leg == "deployment", r.message


# ---------------------------------------------------------------------------
# F3 -- the structural tier, AMN geometry, the REAL probe
# ---------------------------------------------------------------------------
AMN_FIRE = date(2026, 8, 3)
AMN_PIVOT, AMN_STOP = 36.43, 30.85
HEALTHY = {date(2026, 8, 3): 35.10, date(2026, 8, 4): 35.40,
           date(2026, 8, 5): 34.90, date(2026, 8, 6): 35.20}
BREACH_0806 = {**HEALTHY, date(2026, 8, 6): 30.80}
BREACH_0807 = {**HEALTHY, date(2026, 8, 7): 30.80}


def _structural(tmp_path: Path, name: str, *, horizon: int = 30,
                closes: dict | None = None, setup=None):
    """The AMN fire (08-03, pivot 36.43, invalidation 30.85), a MINTED link for
    fill 41's order, trade 20 filling 08-07, and an OHLCV archive."""
    path = _db(tmp_path, name)
    cfg = probe_cfg(path.parent, horizon_sessions=horizon)
    c = open_connection(path)
    seed_run(c, 131, AMN_FIRE)
    cand = int(c.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot, "
        "initial_stop, rs_method) VALUES (131, 'AMN', 'aplus', 35.10, ?, ?, "
        "'universe')", (AMN_PIVOT, AMN_STOP)).lastrowid)
    order = accept_and_link(c, cand, session=AMN_FIRE,
                            broker_order_id=AMN_ORDER_ID, key="amn")
    seed_trade20(c)
    if setup is not None:
        setup(c, cand)
    c.commit()
    write_closes(cfg, HEALTHY if closes is None else closes, ticker="AMN")
    return c, cfg, path, order


def _decline(session: date, recorded: str):
    def setup(c, cand):
        record_decision(c, candidate_id=cand, run_id=131, ticker="AMN",
                        detection=AMN_FIRE, session=session, recorded_ts=recorded)
    return setup


_DIES_0806 = {
    "invalidation": {"closes": BREACH_0806},
    "horizon": {"horizon": 3},
    "declined": {"setup": _decline(date(2026, 8, 6), "2026-08-05T18:00:00")},
}
_DIES_0807 = {
    # the fill-session bar is never seen by the probe (bars run through the
    # PRIOR session), so an 08-07 breach leaves the mandate ALIVE at the fill
    "invalidation": ({"closes": BREACH_0807}, "mandate_fill"),
    "horizon": ({"horizon": 4}, "death_not_before_fill"),
    "declined": ({"setup": _decline(date(2026, 8, 7), "2026-08-06T18:00:00")},
                 "death_not_before_fill"),
}


@pytest.mark.parametrize("rung", sorted(_DIES_0806))
def test_invalidation_terminal_0806_fill_0807_admits_structural_b22_91(
        tmp_path: Path, rung: str) -> None:
    c, cfg, path, order = _structural(tmp_path, rung, **_DIES_0806[rung])
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted, r.message
    assert r.tier == "structural" and r.admitted_leg is None
    row = _row(path)
    assert (row["cited_latch_link_id"], row["cited_latch_terminal_rung"],
            row["cited_latch_terminal_session"]) == (order.link_id, rung, "2026-08-06")
    probe = json.loads(row["cited_latch_probe_json"])
    assert set(probe) == {"decline_reason", "clear_reason", "clear_session",
                          "horizon_session", "bars_through", "freeze_tier",
                          "link_id", "fire_candidate_id"}
    assert (probe["decline_reason"], probe["fire_candidate_id"]) == (
        "mandate_not_alive", order.candidate_id)
    assert row["placement_session"] is None and row["leg_evidence_json"] is None
    assert _fresh(path, "SELECT entry_intent FROM trades WHERE id = 20") == [(UNINT,)]


def test_criteria_lapsed_is_unreachable_through_the_probe_b22_91(
        tmp_path: Path, monkeypatch) -> None:
    """`criteria_lapsed` stays a CHECK member (as ruled) but the probe forces
    the lapse rule OFF, so no structural admission can cite it."""
    import swing.trades.latched_origin as lo

    seen: list[Any] = []
    real = lo.build_latch_derivation

    def spy(*a, **k):
        seen.append(k.get("criteria_lapse_armed_override"))
        return real(*a, **k)

    monkeypatch.setattr(lo, "build_latch_derivation", spy)
    assert "criteria_lapsed" in svc.DEATH_RUNGS
    c, cfg, path, _ = _structural(tmp_path, "lapse", closes=BREACH_0806)
    try:
        r = _assign(c, cfg, dry_run=True)
    finally:
        c.close()
    assert r.admitted and seen and all(v is False for v in seen)


@pytest.mark.parametrize("rung", sorted(_DIES_0807))
def test_terminal_0807_same_session_refuses_b22_92(tmp_path: Path, rung: str) -> None:
    kwargs, code = _DIES_0807[rung]
    c, cfg, path, _ = _structural(tmp_path, rung, **kwargs)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, code), r.message
    if code == "death_not_before_fill":
        assert rung in r.message and "2026-08-07" in r.message
    _nothing_written(path)


def test_live_latch_refuses_as_mandate_fill_b22_93(tmp_path: Path) -> None:
    c, cfg, path, _ = _structural(tmp_path, "live")
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "mandate_fill")
    assert "standard" in r.message
    _nothing_written(path)


def _other_fill(c, cand):
    seed_trade(c, trade_id=21, entry_date=date(2026, 8, 5), price=36.50, ticker="AMN")


def _refire(c, cand):
    seed_run(c, 133, date(2026, 8, 5))
    c.execute("INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
              "pivot, initial_stop, rs_method) VALUES (133, 'AMN', 'aplus', 35.5, "
              "38.00, 33.00, 'universe')")


@pytest.mark.parametrize("rung,setup", [("fill", _other_fill), ("superseded", _refire)])
def test_terminal_fill_or_superseded_refuses_b22_94(tmp_path: Path, rung: str,
                                                   setup) -> None:
    c, cfg, path, _ = _structural(tmp_path, rung, setup=setup)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "not_a_death_rung"), r.message
    assert rung in r.message and "2026-08-05" in r.message and "2026-08-07" in r.message
    _nothing_written(path)


def test_unlinked_intent_naming_the_order_refuses_typed_b22_95(tmp_path: Path) -> None:
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c, cfg, path = _world(tmp_path)
    try:
        for (name,) in c.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND "
                "tbl_name='latch_order_intents' AND sql LIKE "
                "'%INSERT INTO latch_order_mandate_links%'").fetchall():
            c.execute(f"DROP TRIGGER {name}")
        accept_order(c, seed_link_fire(c), actual_broker_order_id=AMN_ORDER_ID)
        c.commit()
        assert c.execute("SELECT COUNT(*) FROM latch_order_mandate_links"
                         ).fetchone()[0] == 0
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "unlinked_intent")
    assert "link backfilled under 22-A" in r.message
    _nothing_written(path)


# ---------------------------------------------------------------------------
# F2 -- citation, audit trail (both tables), outcome, relabel, drift
# ---------------------------------------------------------------------------
def test_open_trade_admits_with_outcome_null_b22_96(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, with_outcome=False)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted and r.outcome_known_at is None
    assert _row(path)["outcome_known_at"] is None


@pytest.mark.parametrize("action", ["trim", "exit"])
def test_a_later_trim_or_exit_does_not_backfill_b22_97(tmp_path: Path, action: str) -> None:
    c, cfg, path = _world(tmp_path, with_outcome=False)
    try:
        assert _assign(c, cfg).admitted
        before = _row(path)
        insert_row(c, "fills", {"trade_id": 20, "fill_datetime": "2026-08-12T16:00:00",
                                "action": action, "quantity": 5.0 if action == "exit"
                                else 2.0, "price": 37.0})
        c.commit()
    finally:
        c.close()
    assert _row(path) == before
    assert before["outcome_known_at"] is None


def test_pre_trade_locked_at_not_citable_b22_98(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, cite=["notes", "pre_trade_locked_at"])
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "not_citable")
    assert "pre_trade_locked_at" in r.message
    _nothing_written(path)


def test_emotional_state_alone_refuses_b22_99(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, cite=["emotional_state_pre_trade"])
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "no_descriptive_field")
    _nothing_written(path)


def test_planted_reconciliation_correction_on_notes_refuses_b22_100(
        tmp_path: Path) -> None:
    from tests.data.test_migration_0040_attestations import _plant_rc

    c, cfg, path = _world(tmp_path)
    try:
        _plant_rc(c, field_name="notes", pre='{"notes": "a"}', applied='{"notes": "b"}')
        c.commit()
        cid = c.execute("SELECT MAX(correction_id) FROM reconciliation_corrections"
                        ).fetchone()[0]
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "cited_field_corrected")
    assert "notes" in r.message and f"reconciliation_corrections row {cid}" in r.message
    assert r.corrections_by_table["reconciliation_corrections"] == 1
    _nothing_written(path)


def test_planted_provenance_correction_on_notes_refuses_b22_101(tmp_path: Path) -> None:
    from tests._tier2_world_22a2 import base_last_word_payload

    payload = base_last_word_payload(tmp_path)
    c, cfg, path = _world(tmp_path)
    try:
        # schema-unreachable row (P2-a): planted with FK + CHECK enforcement off
        # and the citation-graph trigger dropped, exactly as b22_62 plants it
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("DROP TRIGGER trg_provenance_corrections_citation_graph")
        c.execute("PRAGMA ignore_check_constraints=ON")
        prov = copy.deepcopy(payload)
        prov.update(provenance_correction_id=None, trade_id=20, entry_fill_id=41,
                    entry_fill_id_at_correction=41,
                    corrected_fields_json=json.dumps(
                        ["trades.hypothesis_label", "trades.notes"]))
        pid = insert_row(c, "provenance_corrections", prov)
        c.execute("PRAGMA ignore_check_constraints=OFF")
        c.commit()
        c.execute("PRAGMA foreign_keys=ON")
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "cited_field_corrected")
    assert f"provenance_corrections row {pid}" in r.message and "notes" in r.message
    assert r.corrections_by_table["provenance_corrections"] == 1
    _nothing_written(path)


def test_entry_intent_already_set_refuses_b22_102(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, entry_intent="standard")
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "already_set")
    assert "no relabel path" in r.message
    assert _fresh(path, "SELECT COUNT(*) FROM entry_intent_attestations") == [(0,)]


def _assigned(tmp_path: Path, **kw):
    c, cfg, path = _world(tmp_path, **kw)
    r = _assign(c, cfg)
    assert r.admitted, r.message
    return c, cfg, path


def test_drift_reader_names_a_changed_cited_field_b22_103(tmp_path: Path) -> None:
    c, _, _ = _assigned(tmp_path)
    try:
        assert svc.drift_report(c, 20) == []
        c.execute("UPDATE trades SET notes = 'rewritten' WHERE id = 20")
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any("(i)" in line and "notes" in line for line in report), report


def test_drift_reader_names_a_value_without_attestation_b22_104(tmp_path: Path) -> None:
    c, _, _ = _world(tmp_path)
    try:
        assert svc.drift_report(c, 20) == []
        c.execute("DROP TRIGGER trg_trades_entry_intent_unattested_update")
        c.execute("UPDATE trades SET entry_intent = 'unintended_execution' WHERE id = 20")
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any("(iii)" in line for line in report), report


def test_drift_reader_names_a_changed_entry_date_b22_117(tmp_path: Path) -> None:
    c, _, _ = _assigned(tmp_path)
    try:
        c.execute("UPDATE trades SET entry_date = '2026-08-06' WHERE id = 20")
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any("(ii)" in line and "2026-08-06" in line for line in report), report


def _telemetry_assigned(tmp_path: Path):
    c, cfg, path = _world(tmp_path, env=envelope(entry_date="2026-08-06"))
    _speaking(c, first="2026-08-05T09:00:00", ever=0,
              last="2026-08-05T09:30:00")
    r = _assign(c, cfg)
    assert r.admitted and r.admitted_leg == "telemetry", r.message
    assert svc.drift_report(c, 20) == []
    return c


def test_drift_reader_names_changed_leg1_actionability_b22_118(tmp_path: Path) -> None:
    """0 -> 1 is the only reachable change (the monotonic belt refuses 1 -> 0)."""
    c = _telemetry_assigned(tmp_path)
    try:
        c.execute("UPDATE latch_view_events SET actionable_ever_viewed = 1, "
                  "actionable_at_last_view = 1 WHERE view_event_id = 6")
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any("(iv)" in line and "actionable_ever_viewed" in line
               for line in report), report


_LEG1_MOVES = {
    "view_session_date": (None, "UPDATE latch_view_events SET view_session_date = "
                                "'2026-08-06' WHERE view_event_id = 6"),
    "first_viewed_past_placement": (
        "trg_lve_view_window_immutable",
        "UPDATE latch_view_events SET first_viewed_ts = '2026-08-07T09:00:00', "
        "last_viewed_ts = '2026-08-07T09:30:00' WHERE view_event_id = 6"),
    "second_row_into_window": (
        "trg_lve_view_window_immutable",
        "UPDATE latch_view_events SET first_viewed_ts = '2026-08-04T09:00:00' "
        "WHERE view_event_id = 7"),
}


@pytest.mark.parametrize("move", sorted(_LEG1_MOVES))
def test_drift_reader_names_moved_leg1_view_fields_b22_195(tmp_path: Path,
                                                           move: str) -> None:
    drop, sql = _LEG1_MOVES[move]
    c = _telemetry_assigned(tmp_path)
    try:
        _speaking(c, first="2026-08-07T09:00:00", ever=0, view_id=7,
                  session="2026-08-07", last="2026-08-07T09:30:00")
        assert svc.drift_report(c, 20) == []  # row 7 is silent (after placement)
        if drop:
            c.execute(f"DROP TRIGGER {drop}")
        c.execute(sql)
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any("(iv)" in line for line in report), report


@pytest.mark.parametrize("move", ["earlier_entry_fill", "envelope_rewritten",
                                  "envelope_rewritten_unread", "entry_fill_deleted"])
def test_drift_reader_names_a_moved_authoritative_fill_and_a_changed_envelope_b22_116(
        tmp_path: Path, move: str) -> None:
    c, _, _ = _assigned(tmp_path)
    try:
        if move == "earlier_entry_fill":
            insert_row(c, "fills", {"trade_id": 20, "action": "entry",
                                    "fill_datetime": "2026-08-06T16:00:00",
                                    "quantity": 1.0, "price": 36.0})
            tag = "(v)"
        elif move == "envelope_rewritten":
            # RULING G1b: (vi) compares the STORED reading of the CURRENT
            # document; the production writer reads a new document first.
            c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = 41",
                      (envelope(schwab_order_id="999"),))
            record_envelope_readings(c)
            tag = "(vi) the entry fill's order id changed"
        elif move == "envelope_rewritten_unread":
            c.execute("UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = 41",
                      (envelope(schwab_order_id="999"),))
            tag = "(vi) the entry fill's current envelope has no stored reading"
        else:
            c.execute("DELETE FROM fills WHERE fill_id = 41")
            assert c.execute("SELECT entry_fill_id FROM entry_intent_attestations"
                             ).fetchone() == (None,)
            tag = "(v)"
        c.commit()
        report = svc.drift_report(c, 20)
    finally:
        c.close()
    assert any(tag in line for line in report), report


def test_no_entry_fill_refuses_typed_b22_119(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        c.execute("DELETE FROM fills WHERE fill_id = 41")
        c.commit()
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "no_entry_fill")
    _nothing_written(path)


def test_blank_envelope_reads_as_absent_in_both_domains_b22_193(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, row5=False, env="   ", entry_date="2026-08-02")
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted, r.message
    row = _row(path)
    assert (row["entry_broker_order_id"], row["placement_session"],
            row["placement_session_source"]) == (None, "2026-08-02", "entry_date_fallback")


@pytest.mark.parametrize("dry_run", [True, False])
def test_blank_reason_refuses_typed_b22_194(tmp_path: Path, dry_run: bool) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, reason="  ", dry_run=dry_run)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "blank_reason")
    _nothing_written(path)


@pytest.mark.parametrize("outcome,admits", [("2026-08-07T16:00:00", False),
                                            ("2026-08-08T16:00:00", True)])
def test_same_session_outcome_refuses_typed_b22_196(tmp_path: Path, outcome: str,
                                                    admits: bool) -> None:
    c, cfg, path = _world(tmp_path, outcome_dt=outcome)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert r.admitted is admits, r.message
    if not admits:
        assert r.refusal_code == "outcome_not_after_record"
        _nothing_written(path)


def test_thesis_and_emotional_state_are_citable_beside_a_descriptive_field_b22_109(
        tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, cite=["notes", "thesis", "emotional_state_pre_trade"])
    finally:
        c.close()
    assert r.admitted, r.message
    row = _row(path)
    assert json.loads(row["cited_fields_json"]) == [
        "emotional_state_pre_trade", "notes", "thesis"]
    assert set(json.loads(row["cited_text_snapshot_json"])) == {
        "emotional_state_pre_trade", "notes", "thesis"}


def test_envelope_order_id_survives_the_helper_b22_107(tmp_path: Path) -> None:
    from swing.data.repos.fills import get_authoritative_entry_fill

    c, cfg, path = _world(tmp_path)
    try:
        fill = get_authoritative_entry_fill(c, 20)
        assert fill.fill_id == 41 and fill.schwab_source_value_json is None
        assert _assign(c, cfg).admitted
    finally:
        c.close()
    assert _row(path)["entry_broker_order_id"] == "1007427919619"


_NON_CANONICAL = {
    "duplicate_order_key": (
        '{"entry_date": "2026-08-01", "schwab_order_id": "1", '
        '"schwab_instrument_symbol": "AMN", "schwab_order_id": "1007427919619"}'),
    "padded_order_value": envelope(schwab_order_id=" 1007427919619 "),
}


@pytest.mark.parametrize("shape", sorted(_NON_CANONICAL))
def test_padded_or_duplicate_key_envelope_refuses_b22_108(tmp_path: Path,
                                                         shape: str) -> None:
    c, cfg, path = _world(tmp_path, env=_NON_CANONICAL[shape])
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "envelope_refused")
    _nothing_written(path)


_DUPLICATE_ENTRY_DATES = {
    # (first, last): the fixture's own dates, and the discriminating twin where
    # both precede 08-03 so a bare json.loads read (last key) would ADMIT.
    "first_0801_last_0805": ("2026-08-01", "2026-08-05"),
    "first_0801_last_0802": ("2026-08-01", "2026-08-02"),
}


@pytest.mark.parametrize("shape", sorted(_DUPLICATE_ENTRY_DATES))
def test_duplicate_entry_date_key_refuses_b22_78(tmp_path: Path, shape: str) -> None:
    """REWRITTEN by RULING G1b as a refusal case; its code RULED at G1d (a).
    MEASURED: the stored reading of this document is `canonical` (the
    canonicaliser checks duplicates only for schwab_order_id /
    schwab_instrument_symbol), so the refusal is the service's Python read
    counting the ROOT entry_date keys before json.loads' last-key rule can
    choose one. Its code is its OWN, `entry_date_ambiguous`: `envelope_refused`
    means only that the stored reading's state is refused, which it is not."""
    from swing.trades.latched_origin import canonical_envelope_identity

    first, last = _DUPLICATE_ENTRY_DATES[shape]
    env = (f'{{"entry_date": "{first}", "entry_price": 36.43, '
           '"schwab_instrument_symbol": "AMN", '
           f'"schwab_order_id": "1007427919619", "shares": 5, '
           f'"entry_date": "{last}"}}')
    assert json.loads(env)["entry_date"] == last
    assert canonical_envelope_identity(env).state == "canonical"
    c, cfg, path = _world(tmp_path, env=env)
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "entry_date_ambiguous"), r.message
    assert "entered date cannot be read" in r.message
    assert "carries entry_date 2 times" in r.message
    assert r.message.isascii()
    _nothing_written(path)


# ---------------------------------------------------------------------------
# RULING G1b -- the stored reading is the refuse-first; drift is contained
# ---------------------------------------------------------------------------
def test_a_refused_reading_on_the_entry_fill_refuses_b22_208(tmp_path: Path) -> None:
    """An undecodable envelope: the authority stores `refused` (the production
    writer reads it at entry), and the assignment refuses envelope_refused --
    never admits, nothing written."""
    c, cfg, path = _world(tmp_path, env='{"schwab_order_id": "1007427919619"')
    try:
        record_envelope_readings(c)
        c.commit()
        assert c.execute("SELECT envelope_state FROM fill_envelope_identity "
                         "WHERE fill_id = 41").fetchall() == [("refused",)]
        r = _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "envelope_refused"), r.message
    _nothing_written(path)
    assert _fresh(path, "SELECT COUNT(*) FROM fill_envelope_identity") == [(1,)]


def test_a_drifted_reading_refuses_identity_drift_b22_209(tmp_path: Path) -> None:
    """A stored reading of the entry fill's CURRENT document that disagrees with
    what the canonicaliser reads today (a forged or older-grammar row, planted
    raw): ensure's record_identity raises, contained into identity_drift,
    fail-closed, nothing written. MEASURED: rewriting the envelope AFTER a
    reading does NOT drift -- the new document is a new (fill_id,
    envelope_raw) key and ensure appends a fresh reading."""
    c, cfg, path = _world(tmp_path)
    try:
        doc = c.execute("SELECT schwab_source_value_json FROM fills "
                        "WHERE fill_id = 41").fetchone()[0]
        insert_row(c, "fill_envelope_identity", {
            "fill_id": 41, "envelope_raw": doc, "envelope_state": "canonical",
            "broker_order_id": "999", "instrument_symbol": "AMN",
            "canonicalizer_version": "planted",
            "recorded_ts": "2026-09-23T00:00:00Z"})
        c.commit()
        r = _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "identity_drift"), r.message
    _nothing_written(path)
    assert _fresh(path, "SELECT COUNT(*) FROM fill_envelope_identity") == [(1,)]


def test_an_envelope_with_no_reading_after_ensure_raises_the_invariant_b22_212(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An envelope present with NO stored reading after ensure is an invariant
    breach: it RAISES and rolls back, it is never a refusal."""
    c, cfg, path = _world(tmp_path)
    try:
        monkeypatch.setattr(svc, "ensure_entry_fill_identities", lambda conn: 0)
        with pytest.raises(svc.EnvelopeReadingMissingError):
            _assign(c, cfg)
        assert not c.in_transaction
    finally:
        c.close()
    _nothing_written(path)


# ---------------------------------------------------------------------------
# RULING G4 (CHARC 2026-09-24): a copied source date of the wrong shape
# refuses as `source_date_malformed` at preflight step 1 -- before any lexical
# comparison and before EntryIntentAttestation.__post_init__. Planted RAW
# (the fixtures' own INSERT/UPDATE): trades.entry_date and fills.fill_datetime
# are bare TEXT NOT NULL at v40, so no CHECK and no trigger refuses them.
# ---------------------------------------------------------------------------
def _refuses_source_date(tmp_path: Path, name: str, dry_run: bool,
                         column: str, value: str, **world: Any) -> None:
    c, cfg, path = _world(tmp_path, f"{name}-{dry_run}", **world)
    try:
        r = _assign(c, cfg, dry_run=dry_run)
        assert not c.in_transaction
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "source_date_malformed"), (
        r.refusal_code, r.message)
    assert column in r.message and repr(value) in r.message, r.message
    assert r.message.isascii()
    assert r.attestation is None and r.attestation_id is None
    _nothing_written(path)


@pytest.mark.parametrize("dry_run", [True, False])
def test_unpadded_entry_date_on_a_closed_trade_refuses_as_malformed_b22_218(
        tmp_path: Path, dry_run: bool) -> None:
    """Pre-fix: `outcome_not_after_record` -- '2026-8-07' < '2026-08-11' is
    FALSE bytewise ('8' > '0'), a mislabeled refusal (the D38 class)."""
    _refuses_source_date(tmp_path, "b218", dry_run, "trades.entry_date",
                         "2026-8-07", entry_date="2026-8-07")


@pytest.mark.parametrize("dry_run", [True, False])
def test_unpadded_entry_date_with_no_envelope_refuses_as_malformed_b22_219(
        tmp_path: Path, dry_run: bool) -> None:
    """Pre-fix: `instrument_existed` -- the fallback placement '2026-8-07' is
    NOT < '2026-08-03' bytewise, so leg 2 reads as post-deployment."""
    _refuses_source_date(tmp_path, "b219", dry_run, "trades.entry_date",
                         "2026-8-07", entry_date="2026-8-07", env=None,
                         with_outcome=False)


@pytest.mark.parametrize("dry_run", [True, False])
def test_outcome_fill_datetime_with_a_space_refuses_as_malformed_b22_220(
        tmp_path: Path, dry_run: bool) -> None:
    """Pre-fix: an untyped ValueError from EntryIntentAttestation.__post_init__
    (outcome_known_at shape)."""
    _refuses_source_date(tmp_path, "b220", dry_run, "fills.fill_datetime",
                         "2026-08-11 16:00:00", outcome_dt="2026-08-11 16:00:00")


def _entry_fill_dt(value: str):
    def plant(c) -> None:
        c.execute("UPDATE fills SET fill_datetime = ? WHERE fill_id = 41", (value,))
        c.commit()
    return plant


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("case,column,value,world,plant", [
    # the pattern-alone hole: YYYY-MM-DD shaped, not a calendar date
    ("entry_date_not_a_date", "trades.entry_date", "2026-02-31",
     {"entry_date": "2026-02-31"}, None),
    ("outcome_hour_25", "fills.fill_datetime", "2026-08-11T25:00:00",
     {"outcome_dt": "2026-08-11T25:00:00"}, None),
    # the ENTRY fill's datetime is compared too: get_authoritative_entry_fill
    # picks the authoritative entry fill by ORDER BY fill_datetime
    ("entry_fill_datetime_unpadded", "fills.fill_datetime", "2026-8-07T16:00:00",
     {}, _entry_fill_dt("2026-8-07T16:00:00")),
])
def test_every_copied_or_compared_source_date_is_shape_checked_b22_221(
        tmp_path: Path, dry_run: bool, case: str, column: str, value: str,
        world: dict, plant) -> None:
    c, cfg, path = _world(tmp_path, f"{case}-{dry_run}", **world)
    if plant is not None:
        plant(c)
    try:
        r = _assign(c, cfg, dry_run=dry_run)
        assert not c.in_transaction
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "source_date_malformed"), (
        case, r.refusal_code, r.message)
    assert column in r.message and repr(value) in r.message, r.message
    _nothing_written(path)


# ---------------------------------------------------------------------------
# Codex R1 Minor 1: every refusal message is ASCII, including the ones that
# echo an operator- or envelope-supplied value (the CLI prints them on a
# cp1252 console). Pre-fix each message carried the raw non-ASCII value.
# ---------------------------------------------------------------------------
_SNOWMAN = "\u2603"


def test_not_citable_echo_is_ascii_b22_227(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path)
    try:
        r = _assign(c, cfg, cite=["notes", _SNOWMAN])
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "not_citable"), r.message
    assert r.message.isascii(), r.message
    assert ascii(_SNOWMAN) in r.message
    _nothing_written(path)


def test_unprovable_envelope_date_echo_is_ascii_b22_227(tmp_path: Path) -> None:
    c, cfg, path = _world(tmp_path, env=envelope(entry_date=_SNOWMAN))
    try:
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "unprovable"), r.message
    assert r.message.isascii(), r.message
    assert ascii(_SNOWMAN) in r.message
    _nothing_written(path)


def test_entry_intent_param_echo_is_ascii_b22_227() -> None:
    import click

    from swing.cli import EntryIntentParam

    with pytest.raises(click.BadParameter) as exc:
        EntryIntentParam().convert(_SNOWMAN, None, None)
    assert exc.value.message.isascii(), exc.value.message
    assert ascii(_SNOWMAN) in exc.value.message


# ---------------------------------------------------------------------------
# RULING R6-1 (RD 1a + CHARC 1b; Codex R6 Critical 1): a placement session
# STRICTLY AFTER the trade's entry date is the typed refusal
# `placement_after_entry`, decided at the ISO-shape step BEFORE either leg.
# Equality passes. Trade 20 enters 2026-08-07 (a Friday); one session later
# is 2026-08-10 (a Monday).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dry_run", [True, False])
def test_an_envelope_placement_one_session_after_the_entry_refuses_b22_242(
        tmp_path: Path, dry_run: bool) -> None:
    """(a) One mutation of trade 20's world: the envelope's entry_date moves to
    the next session. Pre-fix: `instrument_existed` (leg 2 read 08-10 as a
    post-deployment placement). Post-fix: `placement_after_entry`, nothing
    written, both dates named, the recovery named, ASCII."""
    c, cfg, path = _world(tmp_path, f"b242-{dry_run}",
                          env=envelope(entry_date="2026-08-10"))
    try:
        r = _assign(c, cfg, dry_run=dry_run)
        assert not c.in_transaction
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, "placement_after_entry"), (
        r.refusal_code, r.message)
    assert r.message.isascii(), r.message
    assert ascii("2026-08-10") in r.message and ascii("2026-08-07") in r.message
    assert "fill 41" in r.message
    assert "swing journal correct-entry-date" in r.message
    assert "22-A" in r.message
    assert r.attestation is None and r.attestation_id is None
    assert r.tier is None and r.admitted_leg is None and r.placement_session is None
    _nothing_written(path)


@pytest.mark.parametrize("speaks", [False, True])
def test_an_envelope_placement_equal_to_the_entry_passes_the_bound_b22_244(
        tmp_path: Path, speaks: bool) -> None:
    """(c) The boundary twin: envelope entry_date == trade entry_date passes
    this bound and the LEGS decide -- silent telemetry refuses on leg 2
    (08-07 is after the deployment session); a speaking row before the
    placement admits on leg 1."""
    c, cfg, path = _world(tmp_path, f"b244-{speaks}",
                          env=envelope(entry_date="2026-08-07"))
    try:
        if speaks:
            _speaking(c, first="2026-08-05T09:00:00", ever=0)
        r = _assign(c, cfg)
    finally:
        c.close()
    if speaks:
        assert r.admitted, r.message
        assert (r.admitted_leg, r.placement_session) == ("telemetry", "2026-08-07")
        row = _row(path)
        assert (row["placement_session"], row["trade_entry_date"],
                row["placement_session_source"]) == (
            "2026-08-07", "2026-08-07", "schwab_envelope")
    else:
        assert (r.admitted, r.refusal_code) == (False, "instrument_existed"), r.message
        _nothing_written(path)


# The three LIVE earlier shapes (RD's census at RULING R6-1a: trade 19 FTRE
# envelope 07-23 / entry 07-31; trade 20 AMN 08-01 / 08-07; trade 22 ORKA
# 08-09 / 08-10), transplanted onto trade 20's fixture world as dates only --
# the live DB is never read. Their verdicts are the PRE-fix verdicts.
_EARLIER_SHAPES = {
    "trade19_ftre": ("2026-07-31", "2026-07-23", (True, None, "deployment")),
    "trade20_amn": ("2026-08-07", "2026-08-01", (True, None, "deployment")),
    "trade22_orka": ("2026-08-10", "2026-08-09",
                     (False, "instrument_existed", None)),
}


@pytest.mark.parametrize("shape", sorted(_EARLIER_SHAPES))
def test_the_live_earlier_placement_shapes_keep_their_verdicts_b22_245(
        tmp_path: Path, shape: str) -> None:
    """(d) An envelope placement EARLIER than the entry is untouched by the
    bound; trade 20 admits on leg 2 exactly as before."""
    entry, placement, expected = _EARLIER_SHAPES[shape]
    c, cfg, path = _world(tmp_path, shape, env=envelope(entry_date=placement),
                          entry_date=entry)
    try:
        c.execute("UPDATE fills SET fill_datetime = ? WHERE fill_id = 41",
                  (f"{entry}T16:00:00",))
        c.commit()
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code, r.admitted_leg) == expected, r.message
    if r.admitted:
        row = _row(path)
        assert (row["placement_session"], row["trade_entry_date"]) == (
            placement, entry)


def test_cell16_probe_flips_from_admit_to_placement_after_entry_b22_247(
        tmp_path: Path) -> None:
    """(f) Codex R6's reproduction, verbatim in shape (cell 16's probe):
    entry 08-07, envelope 08-09, a silent view first seen 08-08 -- AFTER the
    entry. Pre-fix it was ADMITTED on leg 1 with placement_session 08-09.
    The control (envelope 08-06) still refuses `instrument_existed`."""
    results = {}
    for label, env_date in (("control", "2026-08-06"), ("probe", "2026-08-09")):
        c, cfg, path = _world(tmp_path, label, env=envelope(entry_date=env_date))
        try:
            _speaking(c, first="2026-08-08T09:00:00", ever=0, session="2026-08-08",
                      last="2026-08-08T09:30:00")
            results[label] = _assign(c, cfg)
        finally:
            c.close()
        _nothing_written(path)
    control, probe = results["control"], results["probe"]
    assert (control.admitted, control.refusal_code) == (False, "instrument_existed")
    assert (probe.admitted, probe.refusal_code) == (False, "placement_after_entry"), (
        probe.admitted_leg, probe.message)
    assert ascii("2026-08-09") in probe.message and ascii("2026-08-07") in probe.message


# ---------------------------------------------------------------------------
# Codex R6 Minor 2: the two refusals that echo the order id pass it through
# ascii() (the module's ASCII promise). The id is the canonicaliser's reading,
# which accepts a non-ASCII string (measured).
# ---------------------------------------------------------------------------
_NON_ASCII_ORDER_ID = "1007\u00e9427919619"


@pytest.mark.parametrize("site", ["unlinked_intent", "ambiguous_links"])
def test_order_id_echo_is_ascii_b22_248(tmp_path: Path, monkeypatch, site: str) -> None:
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    c, cfg, path = _world(tmp_path, site,
                          env=envelope(schwab_order_id=_NON_ASCII_ORDER_ID))
    try:
        if site == "unlinked_intent":
            for (name,) in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND "
                    "tbl_name='latch_order_intents' AND sql LIKE "
                    "'%INSERT INTO latch_order_mandate_links%'").fetchall():
                c.execute(f"DROP TRIGGER {name}")
            accept_order(c, seed_link_fire(c),
                         actual_broker_order_id=_NON_ASCII_ORDER_ID)
            c.commit()
        else:
            import swing.trades.latched_origin as lo

            monkeypatch.setattr(lo, "find_accepted_latch_order",
                                lambda conn, *, broker_order_id: [object(), object()])
        r = _assign(c, cfg)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, site), r.message
    assert r.message.isascii(), r.message
    assert ascii(_NON_ASCII_ORDER_ID) in r.message
    _nothing_written(path)
