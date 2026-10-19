"""D79 T2 -- the identity lookup and the typed refusals inside the lock.

CHARC K1 (2)(3); RD K2 + FORK 1; RD K7.1 (global); CHARC FORK 2's
submitted-envelope half. Plan T2. Envelopes are built with
``json.dumps(..., sort_keys=True)`` unless a test needs hand-written JSON.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from swing.data.db import connect
from swing.data.repos.fills import _recompute_aggregates
from swing.trades import exit as exit_mod
from tests.trades.test_d79_record_exit_txn import (
    ConnProxy,
    count_exit_fills,
    exit_req,
    make_db,
    run_race,
    seed_trade,
)


def env(order_id: str | None = "o2", **extra) -> str:
    payload = {"exit_date": "2026-05-21", "exit_price": 131.0,
               "closed_shares": 3, "schwab_instrument_symbol": "TST"}
    if order_id is not None:
        payload["schwab_order_id"] = order_id
    payload.update(extra)
    return json.dumps(payload, sort_keys=True)


def plant_exit_fill(db, trade_id: int, *, envelope: str | None,
                    day: str = "2026-05-21", price: float = 131.0,
                    qty: float = 3.0, action: str = "trim") -> int:
    """RAW insert (the 18-B.1 technique): a pre-existing row the fixed
    writer could not produce, planted without the service."""
    c = connect(db)
    try:
        with c:
            cur = c.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, fill_origin, schwab_source_value_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trade_id, f"{day}T16:00:00", action, qty, price,
                 "schwab_auto" if envelope else "operator_typed", envelope))
            _recompute_aggregates(c, trade_id)
        return int(cur.lastrowid)
    finally:
        c.close()


def record(db, req):
    c = connect(db)
    try:
        return exit_mod.record_exit(c, req)
    finally:
        c.close()


# ----------------------------------------------------------------- T2-a
def test_t2a_same_id_two_connections_one_fill_typed_refusal(
        tmp_path, monkeypatch):
    """CHARC K1 (i). ``partial_exited`` with 10 shares, two 3-share exits of
    order o2: the size check passes for both and no transition fires, so
    ONLY the identity guard can refuse. PRE-FIX: 2 fills, events ``["read",
    "commit1"]``. NULL killed: the identity lookup before BEGIN."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited", current_size=10.0)
    req = exit_req(tid, shares=3, envelope=env("o2"),
                   fill_origin="schwab_auto")
    events, result1, out2 = run_race(db, monkeypatch, req, req)
    assert count_exit_fills(db) == 1
    exc = out2.get("exc")
    assert isinstance(exc, exit_mod.ExitOrderAlreadyRecordedError), out2
    assert f"#{result1.exit_id}" in str(exc)
    assert events == ["commit1", "read"]


# ----------------------------------------------------------------- T2-b
def test_t2b_split_partial_trade_refused_naming_all_three(tmp_path):
    """CHARC K1 (ii); RD K2 multiplicity. Three partial rows carry order o9
    (the split shape). PRE-FIX: recorded (4 rows). NULL killed: a
    ``fetchone`` lookup naming one of the three."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited", current_size=12.0)
    fids = [plant_exit_fill(db, tid, envelope=env("o9"), qty=2.0)
            for _ in range(3)]
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
        record(db, exit_req(tid, shares=2, envelope=env("o9"),
                            fill_origin="schwab_auto"))
    for fid in fids:
        assert f"#{fid}" in str(info.value)
    assert count_exit_fills(db) == 3


# ----------------------------------------------------------------- T2-c
def test_t2c_cross_trade_refusal_names_the_other_trade(tmp_path):
    """RD K7.1 global; cell list 12. PRE-FIX: recorded. NULL killed: a
    per-trade ``WHERE trade_id = ?``."""
    db = make_db(tmp_path)
    trade_a = seed_trade(db, state="partial_exited", ticker="AAA")
    trade_b = seed_trade(db, state="partial_exited", ticker="BBB")
    record(db, exit_req(trade_a, shares=3, envelope=env("o2"),
                        fill_origin="schwab_auto"))
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
        record(db, exit_req(trade_b, shares=3, envelope=env("o2"),
                            fill_origin="schwab_auto"))
    assert f"trade #{trade_a}" in str(info.value)
    assert count_exit_fills(db) == 1


# ----------------------------------------------------------------- T2-d
def test_t2d_same_id_different_values_refused_with_the_anomaly_text(tmp_path):
    """RD K2 instrument anomaly; cell list 4. PRE-FIX: both recorded. NULL
    killed: a refusal that ignores values (no "differ")."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    first = record(db, exit_req(tid, shares=3, exit_price=131.0,
                                envelope=env("o2"), fill_origin="schwab_auto"))
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
        record(db, exit_req(tid, shares=3, exit_price=131.50,
                            envelope=env("o2"), fill_origin="schwab_auto"))
    assert "differ" in str(info.value)
    assert f"correct fill #{first.exit_id}" in str(info.value)
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as same:
        record(db, exit_req(tid, shares=3, exit_price=131.0,
                            envelope=env("o2"), fill_origin="schwab_auto"))
    assert "differ" not in str(same.value)
    assert count_exit_fills(db) == 1


# ----------------------------------------------------------------- T2-e
@pytest.mark.parametrize("bad", [
    "{bad",
    '{"schwab_order_id": " 123"}',
    '{"schwab_order_id":"a","schwab_order_id":"b"}',
])
def test_t2e_submitted_envelope_refused_before_begin(tmp_path, bad):
    """CHARC F2-(iii). PRE-FIX: recorded. NULL killed: the check placed
    after BEGIN (the statement spy would see it)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    statements: list[str] = []
    real = connect(db)
    proxy = ConnProxy(real, statements=statements)
    try:
        with pytest.raises(exit_mod.ExitEnvelopeUnreadableError) as info:
            exit_mod.record_exit(proxy, exit_req(
                tid, shares=3, envelope=bad, fill_origin="schwab_auto"))
    finally:
        real.close()
    assert "re-open the exit form" in str(info.value)
    assert not any("BEGIN" in s.upper() for s in statements), statements
    assert count_exit_fills(db) == 0


# ----------------------------------------------------------------- T2-f
def test_t2f_selected_only_row_does_not_match_by_id(tmp_path):
    """RD FORK 1 / AL-5: the service reads the authority's TOP-LEVEL id only;
    a row whose only id is ``selected_candidate_order_id`` is anonymous.
    NULL killed: a fourth reader (branch B would refuse)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    plant_exit_fill(db, tid, envelope=json.dumps(
        {"selected_candidate_order_id": "o2", "exit_date": "2026-05-21"},
        sort_keys=True))
    record(db, exit_req(tid, shares=3, envelope=env("o2"),
                        fill_origin="schwab_auto"))
    assert count_exit_fills(db) == 2


# ----------------------------------------------------------------- T2-g
def test_t2g_split_handler_still_succeeds_on_a_linked_exit(tmp_path):
    """CHARC "settled by grep" pin; cell list 11. A linked exit recorded
    through ``record_exit`` is split by the tier-2 handler (it writes
    through ``insert_fill_with_event`` directly, never ``record_exit``): the
    split SUCCEEDS, both partials carry o9, and a later ``record_exit`` o9
    is refused. The split half is green pre-fix; the refusal half is RED."""
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution

    db = make_db(tmp_path)
    tid = seed_trade(db, state="managing", current_size=10.0)
    exit_fill = record(db, exit_req(tid, shares=4, envelope=env("o9"),
                                    fill_origin="schwab_auto")).exit_id
    c = connect(db)
    try:
        with c:
            run_id = c.execute(
                "INSERT INTO reconciliation_runs (source, started_ts, state, "
                "period_start, period_end) VALUES (?, ?, ?, ?, ?)",
                ("schwab_api", "2026-05-22T12:00:00", "running",
                 "2026-05-21", "2026-05-21")).lastrowid
            disc_id = c.execute(
                "INSERT INTO reconciliation_discrepancies (run_id, "
                "discrepancy_type, trade_id, fill_id, ticker, field_name, "
                "expected_value_json, actual_value_json, delta_text, "
                "material_to_review, resolution, ambiguity_kind, "
                "resolution_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "close_price_mismatch", tid, exit_fill, "TST",
                 "price", json.dumps({"price": 131.0}),
                 json.dumps({"_multi_match": True, "count": 2}), "+$0.01",
                 1, "pending_ambiguity_resolution",
                 "multi_partial_vs_consolidated",
                 "Schwab returned 2 partial orders", "2026-05-22T12:00:00"),
            ).lastrowid
        apply_tier2_resolution(
            c, discrepancy_id=int(disc_id), choice_code="split_into_partials",
            operator_custom_payload=[
                {"qty": 2, "price": 131.0, "fill_datetime": "2026-05-21T15:00:00"},
                {"qty": 2, "price": 131.0, "fill_datetime": "2026-05-21T15:01:00"},
            ],
            operator_reason="two partial executions")
        rows = c.execute(
            "SELECT fill_id, schwab_source_value_json FROM fills "
            "WHERE trade_id = ? AND action != 'entry' ORDER BY fill_id",
            (tid,)).fetchall()
    finally:
        c.close()
    assert len(rows) == 2
    assert all(json.loads(e)["schwab_order_id"] == "o9" for _f, e in rows)
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
        record(db, exit_req(tid, shares=2, envelope=env("o9"),
                            fill_origin="schwab_auto"))
    for fid, _e in rows:
        assert f"#{fid}" in str(info.value)


# ----------------------------------------------------------------- T2-h
def test_t2h_canonical_envelope_naming_no_order_records(tmp_path):
    """Scope control: the guard is scoped to an ID. NULL killed: "refuse
    when the envelope is non-null"."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    plant_exit_fill(db, tid, envelope=env(None))
    record(db, exit_req(tid, shares=3, envelope=env(None),
                        fill_origin="schwab_auto"))
    assert count_exit_fills(db) == 2


def test_recorded_exit_identities_reader_shape(tmp_path):
    """The ONE reader: global (no trade predicate), a canonical id groups by
    id, ``refused`` goes to ``unreadable``, a canonical no-id row and a
    NULL-envelope row go to neither."""
    db = make_db(tmp_path)
    a = seed_trade(db, state="partial_exited", ticker="AAA")
    b = seed_trade(db, state="partial_exited", ticker="BBB")
    f1 = plant_exit_fill(db, a, envelope=env("o2"))
    f2 = plant_exit_fill(db, b, envelope=env("o2"), price=131.5)
    f3 = plant_exit_fill(db, a, envelope='{"schwab_order_id": " 123"}')
    plant_exit_fill(db, a, envelope=env(None))
    plant_exit_fill(db, b, envelope=None)
    c = sqlite3.connect(str(db))
    try:
        ident = exit_mod.recorded_exit_identities(c)
    finally:
        c.close()
    assert set(ident.by_order_id) == {"o2"}
    assert [h.fill_id for h in ident.by_order_id["o2"]] == [f1, f2]
    assert {h.trade_id for h in ident.by_order_id["o2"]} == {a, b}
    assert ident.by_order_id["o2"][1].price == 131.5
    assert ident.by_order_id["o2"][0].date == "2026-05-21"
    assert [u.fill_id for u in ident.unreadable] == [f3]


# ------------------------------------------------- RA-01 (Reviewer A R2)
def _plant_text_valued(db, trade_id: int, *, envelope: str | None,
                       price, qty) -> int:
    """A RAW non-entry fill whose price / quantity are TEXT. The 0014
    ``REAL NOT NULL CHECK (> 0)`` admits them (a TEXT value compares greater
    than any number), so the reader must not assume a float. No aggregate
    recompute: the row exists only to be READ."""
    c = sqlite3.connect(str(db))
    try:
        with c:
            cur = c.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, fill_origin, schwab_source_value_json) "
                "VALUES (?, '2026-05-21T16:00:00', 'trim', ?, ?, ?, ?)",
                (trade_id, qty, price,
                 "schwab_auto" if envelope else "operator_typed", envelope))
        assert c.execute("SELECT typeof(price), typeof(quantity) FROM fills "
                         "WHERE fill_id = ?", (cur.lastrowid,)).fetchone() != (
            "real", "real")
        return int(cur.lastrowid)
    finally:
        c.close()


def test_ra01_text_valued_rows_do_not_break_the_global_reader(tmp_path):
    """RA-01: the reader reads the IDENTITY before any value, and a value
    that will not convert is carried as ``None``. A text-valued LINKED row
    still groups under its id; a text-valued REFUSED row is still
    unreadable. PRE-FIX: ``float('abc')`` raises ``ValueError`` out of the
    reader."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited", current_size=10.0)
    linked = _plant_text_valued(db, tid, envelope=env("o2"), price="abc",
                                qty="3")
    refused = _plant_text_valued(db, tid, envelope=env(" 123"), price=131.0,
                                 qty="xyz")
    c = connect(db)
    try:
        got = exit_mod.recorded_exit_identities(c)
    finally:
        c.close()
    [hit] = got.by_order_id["o2"]
    assert (hit.fill_id, hit.price, hit.quantity) == (linked, None, 3.0)
    [bad] = got.unreadable
    assert (bad.fill_id, bad.price, bad.quantity) == (refused, 131.0, None)


def test_ra01_a_text_valued_linked_row_still_refuses_its_order(tmp_path):
    """RA-01: the (a) refusal still fires on a linked row whose stored
    values are malformed, and the anomaly sentence treats them as not
    deriving. PRE-FIX: ``ValueError`` from the reader rolls the exit back
    instead of refusing it as already recorded."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited", current_size=10.0)
    linked = _plant_text_valued(db, tid, envelope=env("o2"), price="abc",
                                qty="abc")
    with pytest.raises(exit_mod.ExitOrderAlreadyRecordedError) as info:
        record(db, exit_req(tid, shares=3, envelope=env("o2"),
                            fill_origin="schwab_auto"))
    assert f"#{linked}" in str(info.value)
    assert count_exit_fills(db) == 1
