"""D79 T4 -- the flag vocabulary: reason labels, K7.2 possible partials, the
flag model, the ASCII text, and the shared (c) reader.

RD K7.2; orchestrator K7.5; CHARC F2-(v); RD P2 correction 1 (one grain).
Plan T4.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import swing.trades.exit_auto_fill as eaf
from swing.data.db import connect
from swing.trades.exit import RecordedExitFill
from swing.trades.exit_auto_fill import (
    DUP_REASON_POSSIBLE_PARTIAL,
    DUP_REASON_VALUE_TUPLE,
    FLAG_F1_NO_CANDIDATE,
    FLAG_F1_OTHER_ORDER,
    FLAG_POSSIBLE_PARTIAL,
    FLAG_UNREADABLE_ENVELOPE,
    FLAG_VALUE_TUPLE,
    ExitAutoFillCandidate,
    ExitRecordFlag,
    PossibleDuplicateFill,
    anonymous_fill_matches,
    derives_from,
    exit_record_flags,
)
from tests.trades.test_d79_record_exit_identity import env, plant_exit_fill
from tests.trades.test_d79_record_exit_txn import make_db, seed_trade

O1 = {"date": "2026-05-20", "price": 130.0, "quantity": 4, "order_id": "o1",
      "date_source": "execution_leg", "possible_duplicates": []}
O2 = {"date": "2026-05-21", "price": 131.0, "quantity": 3, "order_id": "o2",
      "date_source": "execution_leg", "possible_duplicates": []}
MAP = {"h1": O1, "h2": O2}


def _flags(typed, *, selected=O1, selected_id="o1", cmap=MAP,
           anonymous=(), unreadable=(), linked=True):
    return exit_record_flags(
        typed=typed, selected_entry=selected, selected_order_id=selected_id,
        candidates_map=cmap, anonymous_matches=anonymous,
        unreadable_fills=unreadable, linked=linked)


# ----------------------------------------------------------------- T4-a
def test_t4a_possible_partial_window_and_quantity_bounds():
    """RD K7.2 + the intake window [entered, executed] inclusive, quantity
    <= the candidate's, never a value-tuple match too. PRE-FIX: only r3 is
    returned and it has no ``reason`` (AttributeError)."""
    order = SimpleNamespace(enter_time="2026-05-18T14:30:00.000Z")
    cand = ExitAutoFillCandidate(date="2026-05-21", price=131.10, quantity=6,
                                 signature_hash="h3", order_id="o3")
    rows = {
        "r1": PossibleDuplicateFill(1, "2026-05-19", 131.00, 2.0),
        "r2": PossibleDuplicateFill(2, "2026-05-21", 130.90, 2.0),
        "r3": PossibleDuplicateFill(3, "2026-05-21", 131.10, 6.0),
        "r4": PossibleDuplicateFill(4, "2026-05-17", 131.00, 2.0),
        "r5": PossibleDuplicateFill(5, "2026-05-22", 131.00, 2.0),
        "r6": PossibleDuplicateFill(6, "2026-05-19", 131.00, 6.0),
        "r7": PossibleDuplicateFill(7, "2026-05-20", 131.00, 7.0),
    }
    got = eaf._undecidable_duplicates(order, cand, tuple(rows.values()),
                                      match_quantity=6.0)
    labels = {d.fill_id: d.reason for d in got}
    assert labels == {
        1: DUP_REASON_POSSIBLE_PARTIAL,
        2: DUP_REASON_POSSIBLE_PARTIAL,
        3: DUP_REASON_VALUE_TUPLE,
        6: DUP_REASON_POSSIBLE_PARTIAL,
    }
    assert len(got) == 4  # r3 appears ONCE, with the value-tuple label alone


def test_t4a_empty_entered_date_window_is_the_execution_day():
    order = SimpleNamespace(enter_time="")
    cand = ExitAutoFillCandidate(date="2026-05-21", price=131.10, quantity=6,
                                 signature_hash="h3", order_id="o3")
    got = eaf._undecidable_duplicates(
        order, cand, (PossibleDuplicateFill(1, "2026-05-20", 131.0, 2.0),
                      PossibleDuplicateFill(2, "2026-05-21", 131.0, 2.0)),
        match_quantity=6.0)
    assert [(d.fill_id, d.reason) for d in got] == [
        (2, DUP_REASON_POSSIBLE_PARTIAL)]


def test_possible_duplicate_reason_is_validated():
    with pytest.raises(ValueError):
        PossibleDuplicateFill(1, "2026-05-21", 1.0, 1.0, reason="bogus")
    with pytest.raises(ValueError):
        PossibleDuplicateFill(1, "2026-05-21", 1.0, 1.0, reason=[])
    assert PossibleDuplicateFill(1, "2026-05-21", 1.0, 1.0).reason == (
        DUP_REASON_VALUE_TUPLE)


# ----------------------------------------------------------------- T4-b
def test_t4b_five_distinct_flag_labels():
    """CHARC F2-(v): the refused-envelope, value-tuple and possible-partial
    labels are DISTINCT (a superset: five kinds). NULL killed: a shared
    label for refused-envelope and value-tuple."""
    kinds = [FLAG_F1_OTHER_ORDER, FLAG_F1_NO_CANDIDATE, FLAG_VALUE_TUPLE,
             FLAG_POSSIBLE_PARTIAL, FLAG_UNREADABLE_ENVELOPE]
    flags = [ExitRecordFlag(kind=k, subject="7", text="t") for k in kinds]
    assert len({f.kind for f in flags}) == 5
    assert len({f.identity for f in flags}) == 5
    assert flags[2].identity == f"{FLAG_VALUE_TUPLE}|7"
    with pytest.raises(ValueError):
        ExitRecordFlag(kind="bogus", subject="7", text="t")
    with pytest.raises(ValueError):
        ExitRecordFlag(kind=FLAG_VALUE_TUPLE, subject="7", text="café")


# ----------------------------------------------------------------- T4-c
_REPRESENTATIVE = {
    "typed": "2026-05-21, 131.00 x 3", "other": "o2", "selected": "o1",
    "sel_values": "2026-05-20, 130.00 x 4", "fields": "date / price",
    "fill_id": 7, "date": "2026-05-21", "price": 131.0, "qty": 3.0,
    "order": "o1",
}
# Module-level ``_*_TEXT`` names that are NOT flag templates, each with its
# reason (the closure check walks ``dir()``; this is its exclusion list).
_NOT_FLAG_TEMPLATES = {
    "_OMISSION_REASON_TEXT": "a dict of candidate-omission reasons, rendered "
                             "into the auto-fill advisory, not a flag",
}


def test_t4c_every_flag_text_template_is_ascii_and_the_roster_is_closed():
    """Orchestrator K7.5. The roster ``FLAG_TEXT_TEMPLATES`` is CLOSURE-
    CHECKED by a static walk of the module (not a hand list)."""
    names = {n for n in dir(eaf) if n.startswith("_") and n.endswith("_TEXT")}
    assert names - set(_NOT_FLAG_TEMPLATES) == set(eaf.FLAG_TEXT_TEMPLATES)
    for name in eaf.FLAG_TEXT_TEMPLATES:
        rendered = getattr(eaf, name).format(**_REPRESENTATIVE)
        rendered.encode("ascii")
    for value in eaf._OMISSION_REASON_TEXT.values():
        value.encode("ascii")


# ----------------------------------------------------------------- T4-d
def test_t4d_f1_against_the_selected_entry_other_order():
    """Cell list 6; K4; K7.5. Selected o1, typed = o2's values."""
    [flag] = _flags(("2026-05-21", 131.0, 3))
    assert flag.kind == FLAG_F1_OTHER_ORDER
    assert "match order o2, not the selected order o1" in flag.text
    assert "2026-05-20, 130.00 x 4" in flag.text  # the selected's own values
    assert flag.subject == "o1|2026-05-21|131.00|3"


def test_t4d_f1_no_candidate_names_only_the_differing_field():
    [flag] = _flags(("2026-05-20", 129.50, 4))
    assert flag.kind == FLAG_F1_NO_CANDIDATE
    assert " in price." in flag.text
    assert "date /" not in flag.text and "/ quantity" not in flag.text


def test_t4d_no_flag_when_typed_values_derive_from_the_selected_entry():
    assert _flags(("2026-05-20", 130.0, 4)) == ()


# ----------------------------------------------------------------- T4-e
def test_t4e_vwap_at_two_decimals():
    """Cell list 7. ``round(120.505, 2) == 120.5`` on this interpreter (binary
    representation), and the template renders ``'%.2f' % 120.505`` as
    ``120.50``: the unedited render raises no flag; 120.51 flags price.
    NULL killed: comparing raw floats."""
    assert round(120.505, 2) == 120.5
    assert "%.2f" % 120.505 == "120.50"
    sel = dict(O1, price=120.505)
    cmap = {"h1": sel, "h2": O2}
    assert _flags(("2026-05-20", 120.50, 4), selected=sel, cmap=cmap) == ()
    [flag] = _flags(("2026-05-20", 120.51, 4), selected=sel, cmap=cmap)
    assert flag.kind == FLAG_F1_NO_CANDIDATE
    assert " in price." in flag.text


# ----------------------------------------------------------------- T4-f
def test_t4f_anonymous_fill_matches_through_the_authority_per_trade(tmp_path):
    """RD K5c one grain; RD P2 correction 1. Expected matches are computed
    by ``derives_from`` over a row presented through the module's own
    helper -- never a literal comparison."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited", ticker="AAA")
    other = seed_trade(db, state="partial_exited", ticker="BBB")
    linked = plant_exit_fill(db, tid, envelope=env("o2"))
    none_env = plant_exit_fill(db, tid, envelope=None)
    padded = plant_exit_fill(db, tid, envelope='{"schwab_order_id": " 123"}')
    differs = plant_exit_fill(db, tid, envelope=None, price=131.5)
    plant_exit_fill(db, other, envelope=None)
    typed = dict(exit_date="2026-05-21", exit_price=131.0, shares=3)
    c = connect(db)
    try:
        got = anonymous_fill_matches(c, trade_id=tid, **typed)
        expected = []
        for fid, day, price, qty in c.execute(
                "SELECT fill_id, fill_datetime, price, quantity FROM fills "
                "WHERE trade_id = ? AND fill_id IN (?, ?, ?) ORDER BY fill_id",
                (tid, none_env, padded, differs)).fetchall():
            row = eaf._fill_row_as_entry(day, price, qty)
            if derives_from(row, **typed):
                expected.append(fid)
    finally:
        c.close()
    assert [m.fill_id for m in got] == expected == [none_env, padded]
    assert linked not in expected
    assert all(m.reason == DUP_REASON_VALUE_TUPLE for m in got)


def test_t4f_no_second_spelling_of_the_grain(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    plant_exit_fill(db, tid, envelope=None)
    monkeypatch.setattr(eaf, "derives_from", lambda *a, **k: False)
    c = connect(db)
    try:
        assert anonymous_fill_matches(
            c, trade_id=tid, exit_date="2026-05-21", exit_price=131.0,
            shares=3) == ()
    finally:
        c.close()


# ----------------------------------------------------------------- T4-g
def test_t4g_unreadable_flag_only_on_a_linked_exit():
    """CHARC FORK 2: the unreadable flag fires only when the exit is
    linked."""
    bad = (RecordedExitFill(9, 1, "2026-05-01", 10.0, 1.0),)
    assert _flags(("2026-05-20", 130.0, 4), unreadable=bad,
                  linked=False) == ()
    [flag] = _flags(("2026-05-20", 130.0, 4), unreadable=bad, linked=True)
    assert flag.kind == FLAG_UNREADABLE_ENVELOPE
    assert flag.subject == "o1|9"  # D79-A2: the linked order, then the fill
    assert "correct fill #9" in flag.text


def test_flags_dedupe_by_identity_and_order():
    """(c) from the typed-tuple reader and from the selected entry's map
    item name the same fill ONCE; order is F1, (c), partial, unreadable;
    malformed map items are ignored (AL-6)."""
    sel = dict(O2, possible_duplicates=[
        {"fill_id": 5, "date": "2026-05-21", "price": 131.0, "quantity": 3.0,
         "reason": DUP_REASON_VALUE_TUPLE},
        {"fill_id": 6, "date": "2026-05-19", "price": 131.0, "quantity": 1.0,
         "reason": DUP_REASON_POSSIBLE_PARTIAL},
        {"fill_id": True, "date": "x", "price": 1, "quantity": 1,
         "reason": DUP_REASON_VALUE_TUPLE},
        {"fill_id": 8, "reason": "bogus"},
        "not a dict",
    ])
    flags = _flags(
        ("2026-05-21", 131.0, 3), selected=sel, selected_id="o2",
        cmap={"h1": O1, "h2": sel},
        anonymous=(PossibleDuplicateFill(5, "2026-05-21", 131.0, 3.0),),
        unreadable=(RecordedExitFill(9, 2, "2026-05-01", 1.0, 1.0),))
    assert [f.identity for f in flags] == [
        f"{FLAG_VALUE_TUPLE}|5", f"{FLAG_POSSIBLE_PARTIAL}|o2|6",
        f"{FLAG_UNREADABLE_ENVELOPE}|o2|9"]
    assert json.dumps([f.text for f in flags]).isascii()


# ------------------------------------------------- D79-A1 (Reviewer A R1)
def test_a1_a_fractional_stored_fill_does_not_derive_a_whole_share_exit(
        tmp_path):
    """D79-A1: the quantity is compared as a FLOAT at the resolver's
    ``isclose`` grain, never truncated. A literal stored 5.9-share anonymous
    fill is NOT a value-tuple match of a typed 5-share exit. PRE-FIX:
    ``int(5.9) == 5`` -> the 5.9 row is returned as a match (red)."""
    db = make_db(tmp_path)
    tid = seed_trade(db, state="partial_exited")
    fractional = plant_exit_fill(db, tid, envelope=None, qty=5.9)
    whole = plant_exit_fill(db, tid, envelope=None, qty=5.0)
    c = connect(db)
    try:
        got = anonymous_fill_matches(c, trade_id=tid, exit_date="2026-05-21",
                                     exit_price=131.0, shares=5)
    finally:
        c.close()
    assert [m.fill_id for m in got] == [whole]
    assert fractional not in [m.fill_id for m in got]
    row = {"date": "2026-05-21", "price": 131.0, "quantity": 5.9}
    assert derives_from(row, exit_date="2026-05-21", exit_price=131.0,
                        shares=5) is False
    # The control: a whole-valued float still derives (5.0 == 5).
    assert derives_from(dict(row, quantity=5.0), exit_date="2026-05-21",
                        exit_price=131.0, shares=5) is True


def test_a1_a_fractional_map_entry_is_asked_f1_naming_quantity():
    """D79-A1: a map entry whose quantity is fractional does not derive the
    typed int, so F1 asks and names ``quantity`` (``_differing_fields`` at
    the SAME grain). PRE-FIX: ``int(5.9) == 5`` derives silently -> no
    flag (red)."""
    sel = dict(O1, quantity=5.9)
    [flag] = _flags(("2026-05-20", 130.0, 5), selected=sel,
                    cmap={"h1": sel, "h2": O2})
    assert flag.kind == FLAG_F1_NO_CANDIDATE
    assert " in quantity." in flag.text


# ------------------------------------------------- D79-A2 (Reviewer A R1)
_PARTIAL_F = {"fill_id": 6, "date": "2026-05-19", "price": 129.0,
              "quantity": 1.0, "reason": DUP_REASON_POSSIBLE_PARTIAL}


def test_a2_the_partial_and_unreadable_identities_name_the_order():
    """D79-A2, Fork A2 branch B: the same fill F asked about under two
    selected orders yields two DIFFERENT identities, so one order's
    acknowledgement cannot discharge the other's question; the (c)
    identity is unchanged (the matched fill alone). PRE-FIX: both orders'
    partial and unreadable identities are ``<kind>|<fill_id>`` (equal)."""
    s1 = dict(O1, possible_duplicates=[_PARTIAL_F])
    s2 = dict(O2, possible_duplicates=[_PARTIAL_F])
    cmap = {"h1": s1, "h2": s2}
    bad = (RecordedExitFill(9, 2, "2026-05-01", 1.0, 1.0),)
    anon = (PossibleDuplicateFill(5, "2026-05-21", 131.0, 3.0),)
    f1 = _flags(("2026-05-20", 130.0, 4), selected=s1, selected_id="o1",
                cmap=cmap, unreadable=bad, anonymous=anon)
    f2 = _flags(("2026-05-21", 131.0, 3), selected=s2, selected_id="o2",
                cmap=cmap, unreadable=bad, anonymous=anon)
    assert [f.identity for f in f1] == [
        f"{FLAG_VALUE_TUPLE}|5", f"{FLAG_POSSIBLE_PARTIAL}|o1|6",
        f"{FLAG_UNREADABLE_ENVELOPE}|o1|9"]
    assert [f.identity for f in f2] == [
        f"{FLAG_VALUE_TUPLE}|5", f"{FLAG_POSSIBLE_PARTIAL}|o2|6",
        f"{FLAG_UNREADABLE_ENVELOPE}|o2|9"]


def test_a2_with_no_usable_id_the_partial_names_the_selected_hash():
    """Fork A2: with no usable selected order id the partial's order key is
    the selected entry's signature hash -- the map key whose value IS the
    selected entry -- so two id-less candidates still differ."""
    s1 = dict(O1, order_id=None, possible_duplicates=[_PARTIAL_F])
    s2 = dict(O2, order_id=None, possible_duplicates=[_PARTIAL_F])
    cmap = {"h1": s1, "h2": s2}
    [p1] = _flags(("2026-05-20", 130.0, 4), selected=s1, selected_id=None,
                  cmap=cmap)
    [p2] = _flags(("2026-05-21", 131.0, 3), selected=s2, selected_id=None,
                  cmap=cmap)
    assert p1.identity == f"{FLAG_POSSIBLE_PARTIAL}|h1|6"
    assert p2.identity == f"{FLAG_POSSIBLE_PARTIAL}|h2|6"


# ------------------------------------------------- R5-02 (Reviewer A R5)
_VT_F = {"fill_id": 7, "date": "2026-05-20", "price": 130.0,
         "quantity": 4.0, "reason": DUP_REASON_VALUE_TUPLE}


def test_r502_a_map_derived_value_tuple_identity_names_the_order():
    """Fork R5-02, branch A (orchestrator): a value-tuple item drawn from the
    SELECTED entry's map ``possible_duplicates`` is a question about that
    order's own list, so its identity is
    ``value_tuple_match|<order key>|<fill_id>`` -- the same order key as the
    partials -- and the same fill under two orders yields two identities.
    No DB-derived match is in play. PRE-FIX: both are
    ``value_tuple_match|7`` (equal), so one order's acknowledgement
    discharges the other's."""
    s1 = dict(O1, possible_duplicates=[_VT_F])
    s2 = dict(O2, possible_duplicates=[_VT_F])
    cmap = {"h1": s1, "h2": s2}
    [v1] = _flags(("2026-05-20", 130.0, 4), selected=s1, selected_id="o1",
                  cmap=cmap)
    [v2] = _flags(("2026-05-21", 131.0, 3), selected=s2, selected_id="o2",
                  cmap=cmap)
    assert v1.identity == f"{FLAG_VALUE_TUPLE}|o1|7"
    assert v2.identity == f"{FLAG_VALUE_TUPLE}|o2|7"


def test_r502_a_fill_named_by_both_sources_is_one_flag_under_the_db_identity():
    """Fork R5-02's dedup: when the DB-derived (c) match and the selected
    entry's map item name ONE fill, ONE flag is emitted, under the
    order-independent DB identity ``value_tuple_match|<fill_id>``. A PIN
    against the fix's own null implementation (no dedup), which emits two
    flags for one fill (``value_tuple_match|7`` and
    ``value_tuple_match|o1|7``); pre-fix the two identities were equal, so
    this passes there too."""
    s1 = dict(O1, possible_duplicates=[_VT_F])
    anon = (PossibleDuplicateFill(7, "2026-05-20", 130.0, 4.0),)
    flags = _flags(("2026-05-20", 130.0, 4), selected=s1, selected_id="o1",
                   cmap={"h1": s1, "h2": O2}, anonymous=anon)
    assert [f.identity for f in flags] == [f"{FLAG_VALUE_TUPLE}|7"]



def test_r503_an_entered_date_match_says_so_and_never_these_values_match():
    """R5-03 (RD's Fork R5-01 ruling): a map value-tuple item whose date is
    NOT the selected entry's (execution) date matched on the order's
    ENTERED date. Its text says the price and quantity match and that the
    fill's date is the order's ENTERED date -- never "These values match",
    which is false when the typed date is the execution date. An item on
    the execution date keeps the value-tuple text. PRE-FIX: both rendered
    "These values match recorded fill #N"."""
    entered = {"fill_id": 7, "date": "2026-05-19", "price": 130.0,
               "quantity": 4.0, "reason": DUP_REASON_VALUE_TUPLE}
    executed = dict(entered, fill_id=8, date="2026-05-20")
    s1 = dict(O1, possible_duplicates=[entered, executed])
    flags = _flags(("2026-05-20", 130.0, 4), selected=s1, selected_id="o1",
                   cmap={"h1": s1, "h2": O2})
    by_id = {f.identity: f.text for f in flags}
    assert set(by_id) == {f"{FLAG_VALUE_TUPLE}|o1|7",
                          f"{FLAG_VALUE_TUPLE}|o1|8"}
    text7 = by_id[f"{FLAG_VALUE_TUPLE}|o1|7"]
    assert "These values match" not in text7
    assert "order o1's price and quantity" in text7
    assert "the order's ENTERED date" in text7
    assert "fill #7 (2026-05-19 at 130.00 x 4)" in text7
    assert by_id[f"{FLAG_VALUE_TUPLE}|o1|8"].startswith(
        "These values match recorded fill #8")


def test_ss6_a_map_item_the_typed_values_do_not_derive_from_never_says_these_values_match():
    """Self-sweep SS-6 (uncounted), R5-03's class re-grepped. A map
    value-tuple item on the EXECUTION date that is NOT deduplicated into a
    DB-derived match is one the typed values do NOT derive from (the DB scan
    runs on the typed tuple over the same anonymous rows, at the same grain),
    so "These values match recorded fill #N" states a false equality. Its
    text names the ORDER's values instead; an item the typed values DO
    derive from keeps the value-tuple text (R5-03's control, unchanged).
    PRE-FIX: the edited POST rendered "These values match recorded fill
    #8"."""
    executed = {"fill_id": 8, "date": "2026-05-20", "price": 130.0,
                "quantity": 4.0, "reason": DUP_REASON_VALUE_TUPLE}
    s1 = dict(O1, possible_duplicates=[executed])
    flags = _flags(("2026-05-20", 131.5, 4), selected=s1, selected_id="o1",
                   cmap={"h1": s1, "h2": O2})
    by_id = {f.identity: f.text for f in flags}
    text8 = by_id[f"{FLAG_VALUE_TUPLE}|o1|8"]
    assert "These values match" not in text8
    assert "order o1's date, price and quantity" in text8
    assert "fill #8 (2026-05-20 at 130.00 x 4)" in text8
    unedited = _flags(("2026-05-20", 130.0, 4), selected=s1,
                      selected_id="o1", cmap={"h1": s1, "h2": O2})
    assert {f.identity: f.text for f in unedited}[
        f"{FLAG_VALUE_TUPLE}|o1|8"].startswith(
            "These values match recorded fill #8")
