"""22-A Task 4 -- the lookup and TEN of the eleven authorization rungs.

RUNG 8 IS NOT HERE.  It is task 6a's, because it must evaluate each competitor
through ``mandate_alive_at`` and therefore could not run at this point in the
ladder (review 22A-R7-09).  This module passes ``competitor_rung=None``, which
is the honest statement that the rung does not run rather than a stub that
looks like it does.

THE SEVEN RELOCATED ``-pre`` TWINS LIVE HERE (registry finding N10).  A twin
asserts ``pre_barrier_unproven``, which RUNG 9 emits, and rung 9 ships in THIS
task -- ``mandate_alive_at`` never reads a freeze tier at all, so at task 6 the
twin could only have been written against a reason its own task cannot produce.
Their BASE cases stay at task 6, where they belong.

FROZEN CLOCK.  Every session is an explicit date; nothing reads the wall clock.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.models import (
    FREEZE_TIER_LIVE_AT_ACCEPTANCE,
    FREEZE_TIER_PRE_BARRIER,
)
from swing.trades.latched_origin import (
    AUTHORIZATION_KEYS,
    AcceptedLatchOrder,
    authorize_accepted_order,
    find_accepted_latch_order,
)
from tests._latch_link_fixtures_22a import insert_intent, place_row, validity_row
from tests._latch_probe_world_22a import (
    ANCHOR,
    BASE_CLOSES,
    BROKER_ORDER_ID,
    FILL_SESSION,
    PIVOT,
    TICKER,
    accept_and_link,
    order_for_candidate,
    probe_cfg,
    seed_fire,
    seed_run,
    seed_trade,
    write_closes,
)

NO_EXCLUSIONS: frozenset[int] = frozenset()

# The fill the ladder is asked about, in the frozen zone and inside the
# accepted order's own quantity.  PINNED for every case that does not name a
# price or a quantity; those dimensions are exercised by task 1's pure-function
# cases (15a-15e, 30a-30d) and are deliberately FREE here.
GOOD_PRICE = 18.50
GOOD_SHARES = 2
GOOD_ORIGIN = "schwab_auto"

# The place/validity pair is recorded the session BEFORE the fill: a `place` is
# a DECISION row and the probe's as-of rule refuses one recorded on or after the
# fill session, so a fixture leaving it at a default would refuse for a reason
# unrelated to the case under test.
ACCEPT_SESSION = date(2026, 7, 24)


def build_world(tmp_path: Path, name: str, *, closes=None, pre_barrier=False):
    """A fire, an archive and a config.  Returns ``(conn, cfg, candidate_id)``.

    ``pre_barrier=True`` builds the world THE PRODUCTION WAY -- the fire is
    created on a v36 schema and the migration runs afterwards, so the epoch's
    boundary lands ABOVE it and BOTH halves of rung 9 (the minted column and
    the read-time recomputation) say ``pre_barrier_reconstructed``.  This is
    RHI's real shape, and it is why the twin fixtures do not edit the epoch:
    the epoch is IMMUTABLE by its own three triggers, so a fixture that tried
    to move the boundary would be asking the barrier to be less than it is.
    """
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root)
    if pre_barrier:
        conn = open_connection(root / "swing.db")
        run_migrations(conn, target_version=36)
        candidate_id = seed_fire(conn)
        conn.commit()
        run_migrations(conn, target_version=37, backup_dir=root / "bak")
    else:
        conn = ensure_schema(root / "swing.db")
        candidate_id = seed_fire(conn)
        conn.commit()
    write_closes(cfg, BASE_CLOSES if closes is None else closes)
    return conn, cfg, candidate_id


def _accept(conn, candidate_id, **over) -> AcceptedLatchOrder:
    """Place, accept, and read back the TRIGGER-MINTED link through the lookup.

    The lookup is used rather than the fixture's own read so every case
    exercises ``find_accepted_latch_order`` -- including its validity JOIN,
    which is the only source of ``actual_limit_price``.
    """
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION, **over)
    orders = find_accepted_latch_order(
        conn, broker_order_id=over.get("broker_order_id", BROKER_ORDER_ID))
    assert len(orders) == 1, orders
    return orders[0]


def _accept_no_assert(conn, candidate_id, *, key: str,
                      broker_order_id: str = BROKER_ORDER_ID) -> None:
    """Place + accept WITHOUT asserting single-link cardinality.

    ``accept_and_link`` asserts exactly one link for the order id, which is
    precisely the property case 14 exists to violate.
    """
    run_id, ticker, detection = conn.execute(
        "SELECT c.evaluation_run_id, c.ticker, e.action_session_date "
        "FROM candidates c JOIN evaluation_runs e "
        "ON e.id = c.evaluation_run_id WHERE c.id = ?",
        (candidate_id,)).fetchone()
    common = {
        "evaluation_run_id": int(run_id), "ticker": str(ticker),
        "detection_date": str(detection),
        "action_session_date": ACCEPT_SESSION.isoformat(),
        "recorded_ts": f"{ACCEPT_SESSION.isoformat()}T10:00:00",
    }
    place_id = insert_intent(conn, place_row(
        candidate_id, idempotency_key=f"{key}-place", **common))
    insert_intent(conn, validity_row(
        candidate_id, place_id, key=f"{key}-validity",
        actual_broker_order_id=broker_order_id, **common))
    conn.commit()


def _authorize(conn, cfg, order, *, ticker=TICKER, fill_session=FILL_SESSION,
               price=GOOD_PRICE, shares=GOOD_SHARES, fill_origin=GOOD_ORIGIN,
               envelope_symbol=TICKER, exclude=NO_EXCLUSIONS, trade_id=None):
    return authorize_accepted_order(
        conn, cfg, order=order, ticker=ticker, fill_session=fill_session,
        price=price, shares=shares, fill_origin=fill_origin,
        envelope_symbol=envelope_symbol, exclude_trade_ids=exclude,
        trade_id=trade_id, competitor_rung=None)


def _cancel(conn, candidate_id, *, session, recorded_ts,
            broker_order_id=BROKER_ORDER_ID) -> int:
    """A ``cancel`` intent, through the PRODUCTION dataclass and repo.

    A cancel NAMES ONE BROKER ORDER (``actual_broker_order_id`` is required by
    the model -- *"there is no by-ticker cancel path"*), which is why the
    generic decision helper cannot build one.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import record_intent

    intent = LatchOrderIntent(
        intent_id=None, candidate_id=candidate_id, evaluation_run_id=121,
        ticker=TICKER, detection_date=ANCHOR.isoformat(), pipeline_run_id=None,
        idempotency_key=f"cancel-{candidate_id}-{recorded_ts}",
        action_session_date=session.isoformat(), recorded_ts=recorded_ts,
        surface="latch_panel", intent_kind="cancel",
        # A CANCEL CARRIES NO ORDER BLOCK.  The model excludes the framework
        # and derivation columns for every kind outside place/decline/validity
        # -- keyed on the order-BEARING kinds so a future kind is excluded by
        # default -- and it REQUIRES the broker order id, because *"there is no
        # by-ticker cancel path"*.  Both halves are the emitter's shape, not
        # this fixture's opinion.
        actual_broker_order_id=broker_order_id)
    with conn:
        return record_intent(conn, intent=intent)


def _forged_link(conn, candidate_id, *, key: str, validity_over=None,
                 **over) -> AcceptedLatchOrder:
    """A raw link citing a GENUINE validity row, with fields SUBSTITUTED.

    The mint trigger is SUPPRESSED around the acceptance and restored
    immediately, then the link row is written by hand.  Three reasons the shape
    has to be built this way rather than by raw-inserting a second link beside
    a minted one, each measured rather than assumed:
      * ``latch_order_mandate_links.validity_intent_id`` is UNIQUE, so a raw
        copy of a minted link cannot exist at all;
      * the link table is APPEND-ONLY, so a minted link cannot be edited into
        the forged shape afterwards;
      * a forged link must cite a REAL validity row, or rung 3 refuses it and
        the case proves nothing about the rung it was written for.

    ``over`` may be a plain value or a CALLABLE ``(place_id, validity_id) ->
    value``, because the two ids only exist once the intents are inserted --
    which is exactly the shape case 41a needs (a parent pointing at the
    VALIDITY row).

    THE MINT TRIGGER'S BODY IS REPLAYED VERBATIM out of ``sqlite_master``,
    never re-spelled here: the same discipline the candidates-barrier helper
    uses, and for the same reason -- a helper that spells its own copy drifts
    from the migration silently.
    """
    saved = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'trg_latch_link_mint_on_acceptance'").fetchone()[0]
    conn.execute("DROP TRIGGER trg_latch_link_mint_on_acceptance")
    try:
        common = {
            "action_session_date": ACCEPT_SESSION.isoformat(),
            "recorded_ts": f"{ACCEPT_SESSION.isoformat()}T10:00:00",
            "detection_date": ANCHOR.isoformat(),
        }
        place_id = insert_intent(conn, place_row(
            candidate_id, idempotency_key=f"{key}-place", **common))
        validity = validity_row(
            candidate_id, place_id, key=f"{key}-validity",
            actual_broker_order_id=f"{key}-real", **common)
        validity.update(validity_over or {})
        validity_id = insert_intent(conn, validity)
        conn.commit()
    finally:
        conn.execute(saved)
        conn.commit()

    run_id, ticker, detection, pivot, stop = conn.execute(
        "SELECT c.evaluation_run_id, c.ticker, e.action_session_date, c.pivot, "
        "c.initial_stop FROM candidates c JOIN evaluation_runs e "
        "ON e.id = c.evaluation_run_id WHERE c.id = ?", (candidate_id,),
    ).fetchone()
    row = {
        "validity_intent_id": validity_id, "place_intent_id": place_id,
        "candidate_id": candidate_id, "evaluation_run_id": int(run_id),
        "ticker": str(ticker), "detection_date": str(detection),
        "broker_order_id": f"{key}-real", "frozen_pivot": pivot,
        "frozen_invalidation": stop, "actual_quantity": 10,
        "freeze_tier": FREEZE_TIER_LIVE_AT_ACCEPTANCE,
        "linked_at": "2026-07-24T12:00:00Z",
    }
    for name, value in over.items():
        row[name] = value(place_id, validity_id) if callable(value) else value
    conn.execute(
        f"INSERT INTO latch_order_mandate_links ({', '.join(row)}) "
        f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    conn.commit()
    # READ IT BACK THROUGH THE PRODUCTION LOOKUP.  Building the dataclass by
    # hand here would test the fixture's idea of the row rather than the row.
    found = [
        o for o in find_accepted_latch_order(
            conn, broker_order_id=str(row["broker_order_id"]))
        if o.validity_intent_id == validity_id
    ]
    assert len(found) == 1, found
    return found[0]


# ===========================================================================
# THE LOOKUP -- CARDINALITY BY COUNT
# ===========================================================================
def test_an_armed_latch_admits_through_the_whole_ladder_case_4() -> None:
    """CASE 4 -- RHI's shape: a broker-accepted order on a mandate that is
    ARMED at its fill session ADMITS, and the admission is reached through the
    ORDER's identity rather than through "any armed latch".

    Lens clause 3b.  An implementation matching on "the ticker has an armed
    latch" passes this and fails case 4b, which is why both exist.
    """
    import tempfile
    conn, cfg, candidate_id = build_world(
        Path(tempfile.mkdtemp()), "case4")
    try:
        order = _accept(conn, candidate_id)
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.order.link_id == order.link_id
        assert verdict.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE
        assert set(verdict.probe_evidence["authorization"]) == set(
            AUTHORIZATION_KEYS)
        assert all(
            entry["verdict"] == "pass"
            for entry in verdict.probe_evidence["authorization"].values())
    finally:
        conn.close()


def test_an_in_zone_fill_with_no_accepted_order_finds_nothing_case_4b(
        tmp_path) -> None:
    """CASE 4b -- the PRICE-HEURISTIC discriminator (lens clause 3).

    A NULL-candidate, same-ticker, IN-ZONE entry with NO validity row anywhere.
    The shipped ``derive_latches`` windowed rung would MATCH it on price; this
    arc's lookup is keyed on the BROKER ORDER ID and finds nothing at all.
    ``find_accepted_latch_order`` returning an EMPTY list is the whole assertion
    -- there is no accepted link for the ladder to authorize.
    """
    conn, _cfg, candidate_id = build_world(tmp_path, "case4b")
    try:
        # A place intent WITHOUT a validity child: the operator prepared an
        # order and no broker acceptance was ever recorded.
        insert_intent(conn, place_row(
            candidate_id, idempotency_key="case4b-place",
            action_session_date=ACCEPT_SESSION.isoformat(),
            recorded_ts=f"{ACCEPT_SESSION.isoformat()}T10:00:00",
            detection_date=ANCHOR.isoformat()))
        seed_trade(conn, trade_id=91, entry_date=FILL_SESSION, price=GOOD_PRICE,
                   candidate_id=None)
        conn.commit()
        assert find_accepted_latch_order(
            conn, broker_order_id=BROKER_ORDER_ID) == []
    finally:
        conn.close()


def test_two_links_on_one_order_id_are_ambiguous_case_14(tmp_path) -> None:
    """CASE 14 -- CARDINALITY BY COUNT, not ``fetchone()`` (lens clause 16).

    There is deliberately no UNIQUE on ``broker_order_id``, so the reader
    counts.  A ``fetchone()`` lookup silently picks one and looks correct.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case14")
    try:
        order = _accept(conn, candidate_id)
        # A SECOND acceptance naming the SAME broker order id.  It is minted
        # by the trigger rather than raw-inserted, because
        # `latch_order_mandate_links.validity_intent_id` is UNIQUE and a raw
        # copy of the first link could not exist -- the duplicate this rung
        # guards against is a duplicate BROKER ORDER, not a duplicate row.
        second = seed_fire(conn, run_id=132, action_session=ANCHOR,
                           ticker=TICKER)
        conn.commit()
        _accept_no_assert(conn, second, key="dup")
        found = find_accepted_latch_order(conn, broker_order_id=BROKER_ORDER_ID)
        assert len(found) == 2
        assert [o.link_id for o in found] == sorted(o.link_id for o in found)

        # AND THE REFUSAL ITSELF, at the RESOLVER (Codex 22A-R6-09). Asserting
        # only that the lookup returns two proves the READER counts; it says
        # nothing about what the ladder DOES with two. Deleting the resolver's
        # `len(orders) > 1` branch and taking `orders[0]` left this case green,
        # and the roster tests do not close it either -- one finds the literal
        # statically and the other constructs a verdict directly, so neither
        # exercises the rung.
        from types import SimpleNamespace

        from swing.trades.latched_origin import resolve_latched_provenance

        request = SimpleNamespace(
            ticker=TICKER, entry_date=FILL_SESSION.isoformat(),
            entry_price=GOOD_PRICE, shares=GOOD_SHARES,
            fill_origin=GOOD_ORIGIN, hypothesis_label=None,
            schwab_source_value_json=json.dumps({
                "schwab_order_id": BROKER_ORDER_ID,
                "schwab_instrument_symbol": TICKER}))
        verdict = resolve_latched_provenance(conn, cfg, request)
        assert verdict.admitted is False
        assert verdict.recognised_but_underivable is True, (
            "two links is RECOGNISED-and-refused; falling through to the "
            "ordinary chain would write TODAY's candidate for a fill that "
            "demonstrably came from an accepted order")
        assert verdict.decline_reason == "ambiguous_accepted_orders"
        assert (verdict.trade_origin, verdict.candidate_id,
                verdict.hypothesis_label) == (None, None, None)
    finally:
        conn.close()


# ===========================================================================
# RUNG 2 -- THE LINK'S PARENT RELATION
# ===========================================================================
def test_a_link_whose_parent_is_not_a_place_row_is_incoherent_case_41a(
        tmp_path) -> None:
    """CASE 41a -- lens clause 46.  ``link_parent_incoherent`` HAD NO CASE AT
    ALL until SELF-SWEEP SS-10 found it.

    Two shapes, both refused: a ``place_intent_id`` naming a row that is not a
    ``place``, and one naming a place on a DIFFERENT candidate.  Rungs 1 and 3
    pass on both.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case41a")
    try:
        # (a) the parent names the VALIDITY row, which is not a place.
        not_a_place = _forged_link(
            conn, candidate_id, key="41aA",
            place_intent_id=lambda _p, validity_id: validity_id)
        assert _authorize(conn, cfg, not_a_place).decline_reason == (
            "link_parent_incoherent")

        # (b) the parent is a genuine place row on ANOTHER candidate.
        other = seed_fire(conn, run_id=131, action_session=ANCHOR,
                          ticker="OTHR")
        other_place = insert_intent(conn, place_row(
            other, run_id=131, ticker="OTHR",
            idempotency_key="41a-other-place",
            action_session_date=ACCEPT_SESSION.isoformat(),
            recorded_ts=f"{ACCEPT_SESSION.isoformat()}T10:00:00",
            detection_date=ANCHOR.isoformat()))
        conn.commit()
        wrong_parent = _forged_link(conn, candidate_id, key="41aB",
                                    place_intent_id=other_place)
        assert _authorize(conn, cfg, wrong_parent).decline_reason == (
            "link_parent_incoherent")
    finally:
        conn.close()


# ===========================================================================
# RUNG 3 / 3b -- THE LINKED VALIDITY ROW
# ===========================================================================
def test_a_link_citing_a_rejected_validity_row_refuses_case_4d_i(
        tmp_path) -> None:
    """CASE 4d(i) -- lens clause 2.  The ``accepted_by_broker`` GATE, which was
    described in prose two sections from the ladder and was NEVER IN IT
    (review 22A-R5-07).

    ``0033`` forbids a non-accepted validity row from carrying an
    ``actual_broker_order_id``, so against the SERVICE this never bites -- but a
    RAW link may CITE a rejected row, which is exactly this shape, so
    schema-prevention does not cover it.  The refusal is asserted BY NAME:
    an implementer following the ladder literally would have admitted the
    planted row or invented a reason.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case4d1")
    try:
        # The CITED validity row is genuinely REJECTED.  0033 forbids a
        # rejected row from carrying an actual_broker_order_id at all, so the
        # link's copy is unbound too -- but rung 3 fires BEFORE rung 3c, and
        # the assertion is on the reason NAME, which is what makes it
        # discriminating rather than merely a decline.
        planted = _forged_link(
            conn, candidate_id, key="4di", broker_order_id="4di-order",
            validity_over={
                "validity_outcome": "rejected_by_broker",
                "actual_order_type": None, "actual_duration": None,
                "actual_stop_price": None, "actual_limit_price": None,
                "actual_quantity": None, "actual_broker_order_id": None,
            })
        assert _authorize(conn, cfg, planted).decline_reason == (
            "linked_validity_not_accepted")
    finally:
        conn.close()


def test_a_superseded_validity_child_refuses_case_4d_ii(tmp_path) -> None:
    """CASE 4d(ii) -- lens clause 2b.  ACCEPTED, then SUPERSEDED.

    A later validity child of the SAME place intent makes the earlier one
    stale.  The comparison is the classifier's own ``(recorded_ts, intent_id)``
    total order, IMPORTED -- ``max(intent_id)`` is a DIFFERENT order whenever a
    later-inserted row carries an earlier stamp.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case4d2")
    try:
        order = _accept(conn, candidate_id)
        insert_intent(conn, validity_row(
            candidate_id, order.place_intent_id, key="4dii-later",
            action_session_date=ACCEPT_SESSION.isoformat(),
            recorded_ts=f"{ACCEPT_SESSION.isoformat()}T15:00:00",
            detection_date=ANCHOR.isoformat(),
            validity_outcome="rejected_by_broker",
            actual_order_type=None, actual_duration=None,
            actual_stop_price=None, actual_limit_price=None,
            actual_quantity=None, actual_broker_order_id=None))
        conn.commit()
        assert _authorize(conn, cfg, order).decline_reason == (
            "validity_superseded")
    finally:
        conn.close()


# ===========================================================================
# RUNG 3c -- THE DUPLICATED FIELDS ARE BOUND BACK
# ===========================================================================
def test_a_substituted_broker_order_id_is_unbound_case_47a(tmp_path) -> None:
    """CASE 47a -- lens clause 62.  A raw link citing a GENUINE accepted
    validity row while SUBSTITUTING the broker order id.

    Rungs 1-3b check ticker, parent and outcome and would admit it, and the
    submitted envelope would then match the FORGERY rather than the acceptance.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case47a")
    try:
        forged = _forged_link(conn, candidate_id, key="47a",
                              broker_order_id="9999999999")
        assert forged.broker_order_id == "9999999999"
        assert _authorize(conn, cfg, forged).decline_reason == (
            "link_field_unbound")
    finally:
        conn.close()


def test_an_inflated_quantity_is_unbound_case_47b(tmp_path) -> None:
    """CASE 47b -- the same clause, on the QUANTITY.

    The envelope guard compares ``shares`` to the LINK's ``actual_quantity``,
    so an inflated copy would silently widen the permitted fill.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case47b")
    try:
        inflated = _forged_link(conn, candidate_id, key="47b",
                                actual_quantity=999)
        assert inflated.actual_quantity == 999
        assert _authorize(conn, cfg, inflated).decline_reason == (
            "link_field_unbound")
    finally:
        conn.close()


def test_a_mismatched_ticker_copy_is_unbound_case_47c(tmp_path) -> None:
    """CASE 47c -- the same clause, on the fields copied from the CANDIDATE.

    The link's ``ticker`` / ``evaluation_run_id`` / ``detection_date`` are
    copies of the fire's own, and rung 1 compares the link to the REQUEST --
    so a link whose ticker matches the request but NOT the candidate passes
    rung 1 and is caught only here.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case47c")
    try:
        # A plausible-looking but WRONG detection date: one session off the
        # fire's own.  Rung 1 compares the link to the REQUEST and passes.
        drifted = _forged_link(conn, candidate_id, key="47c",
                               detection_date="2026-07-21")
        assert drifted.detection_date == "2026-07-21"
        assert _authorize(conn, cfg, drifted).decline_reason == (
            "link_field_unbound")
    finally:
        conn.close()


# ===========================================================================
# RUNG 4 / 5 -- THE GOVERNING PLACE CYCLE AND THE CANCELLATION HISTORY
# ===========================================================================
def test_a_newer_place_cycle_retires_the_accepted_order_case_29a(
        tmp_path) -> None:
    """CASE 29a -- lens clause 33.  A later ``place`` opens a NEW cycle and
    retires the earlier order REGARDLESS of what the earlier order's own
    validity children say.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case29a")
    try:
        order = _accept(conn, candidate_id)
        insert_intent(conn, place_row(
            candidate_id, idempotency_key="29a-newer-place",
            action_session_date=ACCEPT_SESSION.isoformat(),
            recorded_ts=f"{ACCEPT_SESSION.isoformat()}T16:00:00",
            detection_date=ANCHOR.isoformat()))
        conn.commit()
        assert _authorize(conn, cfg, order).decline_reason == (
            "place_cycle_superseded")
    finally:
        conn.close()


def test_a_cancel_before_the_fill_refuses_case_29b(tmp_path) -> None:
    """CASE 29b -- lens clause 34.  A cancel recorded STRICTLY BEFORE the fill
    session kills the order."""
    conn, cfg, candidate_id = build_world(tmp_path, "case29b")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=ACCEPT_SESSION,
                recorded_ts=f"{ACCEPT_SESSION.isoformat()}T17:00:00")
        assert _authorize(conn, cfg, order).decline_reason == "order_cancelled"
    finally:
        conn.close()


def test_a_cancel_on_the_fill_session_is_unorderable_case_29c(
        tmp_path) -> None:
    """CASE 29c -- the SAME-DATE branch, and it refuses with its OWN reason.

    The entry carries a DATE, so a cancel stamped on the fill session cannot be
    ordered against it -- and inventing a third clock domain to try is exactly
    what this arc declines to do (D37).  Refusing with a DISTINCT reason is
    what makes the ambiguity actionable rather than indistinguishable from a
    kill.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case29c")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=FILL_SESSION,
                recorded_ts=f"{FILL_SESSION.isoformat()}T09:00:00")
        assert _authorize(conn, cfg, order).decline_reason == (
            "cancel_ordering_ambiguous")
    finally:
        conn.close()


def test_a_cancel_after_the_fill_is_not_consulted_case_29d(tmp_path) -> None:
    """CASE 29d -- lens clause 34b.  ADMIT.

    THIS IS THE CASE THAT FAILS AN IMPLEMENTATION REFUSING ON ANY CANCEL AT
    ALL.  An order cancelled the day AFTER it filled was live when it filled;
    reading its later cancellation backwards would refuse a genuine entry.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case29d")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=FILL_SESSION,
                recorded_ts="2026-07-28T09:00:00")
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is True, verdict.decline_reason
    finally:
        conn.close()


# ===========================================================================
# RUNG 6 / 7 -- CONSUMPTION, AND THE DESTRUCTIBILITY OF ITS EVIDENCE
# ===========================================================================
def _entry_fill(conn, *, fill_id, trade_id, envelope, session=FILL_SESSION,
                reconciliation_status="unreconciled"):
    conn.execute(
        "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, "
        "quantity, price, rule_based, reconciliation_status, fill_origin, "
        "schwab_source_value_json) VALUES (?, ?, ?, 'entry', 2, 18.50, 0, "
        "?, 'schwab_auto', ?)",
        (fill_id, trade_id, f"{session.isoformat()}T14:30:00",
         reconciliation_status, envelope))
    conn.commit()


def test_a_second_trade_on_the_same_order_is_already_consumed_case_13(
        tmp_path) -> None:
    """CASE 13 -- lens clause 15.  ONE TRADE PER MANDATE.

    The scan is ORDER-LINKED: another trade whose entry fill carries THIS
    broker order id has consumed the mandate.
    """
    import json
    conn, cfg, candidate_id = build_world(tmp_path, "case13")
    try:
        order = _accept(conn, candidate_id)
        seed_trade(conn, trade_id=41, entry_date=FILL_SESSION, price=18.40)
        _entry_fill(conn, fill_id=41, trade_id=41, envelope=json.dumps(
            {"schwab_order_id": BROKER_ORDER_ID,
             "schwab_instrument_symbol": TICKER}))
        assert _authorize(conn, cfg, order).decline_reason == (
            "mandate_already_consumed")
    finally:
        conn.close()


def test_an_ordinary_trade_on_the_fire_does_not_block_admission_case_22(
        tmp_path) -> None:
    """CASE 22 -- lens clause 25.  CONSUMPTION IS ORDER-LINKED.

    An ordinary trade carrying the fire's ``candidate_id`` but NOT this broker
    order must NOT block admission.  A ``COUNT(*) FROM trades WHERE
    candidate_id = ?`` implementation FALSELY REFUSES -- and the ordinary entry
    path assigns ``candidate_id`` from pipeline provenance with no accepted
    order anywhere near it, so that count is reachable in production.

    THE OTHER TRADE'S SESSION IS **NOT** A FREE DIMENSION HERE, and the
    plan's S3.8 audit says it is (*"free, and verified HARMLESS: consumption
    is order-linked and session-independent by construction"*).  That is true
    of RUNG 6 and FALSE of the FIXTURE: the shipped fold's own windowed fill
    rung matches a same-candidate entry AT OR BEFORE the bar bound, so an
    ordinary trade dated INSIDE the probe window makes ``mandate_alive_at``
    return ``mandate_not_alive`` and the case never reaches the clause it
    exists to test.  MEASURED, not reasoned: with the other trade dated
    2026-07-22 the verdict is ``mandate_not_alive`` carrying
    ``fill_link_basis='candidate_id'``.  The session is therefore PINNED
    AFTER the fill, where the probe cannot see it and rung 6 still can.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case22")
    try:
        order = _accept(conn, candidate_id)
        seed_trade(conn, trade_id=42, entry_date=date(2026, 7, 28),
                   price=18.10, candidate_id=candidate_id)
        _entry_fill(conn, fill_id=42, trade_id=42, envelope=None,
                    session=date(2026, 7, 28))
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is True, verdict.decline_reason
    finally:
        conn.close()


def test_a_stripped_envelope_makes_consumption_unprovable_case_22b(
        tmp_path) -> None:
    """CASE 22b -- lens clause 36.  THE EVIDENCE CAN BE DESTROYED.

    A prior trade on the ticker whose entry fill went through the supported
    split-into-partials handler: ``reconciliation_status =
    'reconciled_discrepancy_resolved'`` with the envelope STRIPPED.  The scan
    cannot prove non-consumption, so it refuses rather than silently admitting.

    Task 11a fixes the handler FORWARD; rows already rebuilt are already blind,
    which is why this rung survives that fix.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "case22b")
    try:
        order = _accept(conn, candidate_id)
        seed_trade(conn, trade_id=43, entry_date=date(2026, 7, 28), price=18.10)
        _entry_fill(
            conn, fill_id=43, trade_id=43, envelope=None,
            session=date(2026, 7, 28),
            reconciliation_status="reconciled_discrepancy_resolved")
        assert _authorize(conn, cfg, order).decline_reason == (
            "consumption_evidence_unavailable")
    finally:
        conn.close()


# ===========================================================================
# RUNG 9 -- RD'S REFUSE-BY-DEFAULT, AND THE SEVEN RELOCATED TWINS
# ===========================================================================
def test_a_pre_barrier_link_refuses_outright_case_22_pre(tmp_path) -> None:
    """``22-pre`` -- rung 9 refuses BEFORE the ordinary-trade question is even
    asked.  Under Option C there is NO tier-2 escape."""
    conn, cfg, candidate_id = build_world(tmp_path, "22pre", pre_barrier=True)
    try:
        order = _accept(conn, candidate_id)
        assert order.freeze_tier == FREEZE_TIER_PRE_BARRIER
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "pre_barrier_unproven"
        assert verdict.recognised_but_underivable is True
    finally:
        conn.close()


def test_a_pre_barrier_link_refuses_despite_a_late_cancel_case_29d_pre(
        tmp_path) -> None:
    """``29d-pre`` -- case 29d's twin.  The base ADMITS; the twin refuses at
    rung 9 regardless."""
    conn, cfg, candidate_id = build_world(
        tmp_path, "29dpre", pre_barrier=True)
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=FILL_SESSION,
                recorded_ts="2026-07-28T09:00:00")
        assert _authorize(conn, cfg, order).decline_reason \
            == "pre_barrier_unproven"
    finally:
        conn.close()


# The SEVEN twins relocated from task 6 by registry finding N10.  Their BASE
# cases live in the task-6 module and assert what the PROBE answers; the twins
# assert that rung 9 refuses FIRST, so the probe's answer never matters.  They
# are parametrized because the assertion is identical and only the world that
# would otherwise have admitted differs -- and the world is what each base case
# already pins.
RELOCATED_TWIN_CASE_IDS = [
    "8-pre", "10-pre", "24-pre", "27-pre", "28a-pre", "28b-pre", "28c-pre",
]


@pytest.mark.parametrize("twin", RELOCATED_TWIN_CASE_IDS)
def test_every_relocated_twin_refuses_at_rung_nine(tmp_path, twin) -> None:
    """The seven ``-pre`` twins whose BASE cases are task 6's.

    N10's repair, and it is caught by the registry's OWN ownership rule: *the
    EARLIEST task at which its FULL required outcome is assertable.*  A twin
    asserts ``pre_barrier_unproven``, which RUNG 9 emits, and
    ``mandate_alive_at`` never reads a freeze tier at all -- so at task 6 the
    twin could only have been written against a reason its own task cannot
    produce.  That is 22A-R7-09's class recurring INSIDE the registry written
    to close it.

    WHAT MAKES THIS DISCRIMINATING rather than seven copies of one assertion:
    each twin's world is the one its base case proved ADMITS, so an
    implementation that omitted rung 9 would ADMIT all seven.  The pre-barrier
    state is planted on BOTH halves (stored tier AND epoch boundary), so the
    refusal is rung 9's ruling rather than one of its operands.
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, twin.replace("-", "_"), pre_barrier=True)
    try:
        order = _accept(conn, candidate_id)
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is False, twin
        assert verdict.decline_reason == "pre_barrier_unproven", twin
        assert verdict.freeze_tier == FREEZE_TIER_PRE_BARRIER, twin
    finally:
        conn.close()


def test_rung_nine_refuses_a_post_barrier_link_with_the_barrier_dropped(
        tmp_path) -> None:
    """THE EXISTENCE CHECK OUTRANKS THE STORED TIER, for EVERY candidate.

    NO CASE ID -- 50a-50c are task 3's, at the READER's grain.  This is the
    same property one layer up: rung 9 must consume the reader's
    ``barrier_installed`` verdict rather than reading only the stored column,
    and an implementation reading only the tier ADMITS here.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "barrier-gone")
    try:
        order = _accept(conn, candidate_id)
        conn.execute("DROP TRIGGER trg_candidates_no_update")
        conn.commit()
        verdict = _authorize(conn, cfg, order)
        assert verdict.decline_reason == "barrier_not_installed"
        assert verdict.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE
    finally:
        conn.close()


def test_rung_eight_does_not_run_at_task_four(tmp_path) -> None:
    """THE SEAM IS A PARAMETER, NOT A COMMENT PROMISING INHERITANCE (#31).

    ``competitor_rung=None`` means the rung does NOT run, and the
    ``$.authorization`` entry records an EMPTY competitor list -- which is
    truthful about what was scanned.  Task 6a supplies the callable; a test
    there asserts it is consulted.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "no-rung8")
    try:
        order = _accept(conn, candidate_id)
        seen = {}

        def _rung(conn_, cfg_, *, order, fill_session, exclude_trade_ids):
            seen["called"] = True
            return None, [order.link_id]

        verdict = authorize_accepted_order(
            conn, cfg, order=order, ticker=TICKER, fill_session=FILL_SESSION,
            price=GOOD_PRICE, shares=GOOD_SHARES, fill_origin=GOOD_ORIGIN,
            envelope_symbol=TICKER, exclude_trade_ids=NO_EXCLUSIONS,
            competitor_rung=_rung)
        assert seen == {"called": True}
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.probe_evidence["authorization"][
            "rung8_competitor_link_ids"]["input"] == [order.link_id]

        plain = _authorize(conn, cfg, order)
        assert plain.probe_evidence["authorization"][
            "rung8_competitor_link_ids"]["input"] == []
    finally:
        conn.close()


def test_the_lookup_carries_the_accepted_orders_own_limit(tmp_path) -> None:
    """``actual_limit_price`` comes from the validity JOIN, not from a second
    query at the guard -- which is what keeps the envelope guards a PURE
    function over the dataclass.

    NO CASE ID: this is the property review 22A-R8-07 added the field for, and
    cases 30a-30d (task 1) exercise the guard it feeds.
    """
    conn, _cfg, candidate_id = build_world(tmp_path, "limit")
    try:
        order = _accept(conn, candidate_id)
        assert order.actual_limit_price == 18.89
        assert order.frozen_pivot == PIVOT
    finally:
        conn.close()


def test_an_unknown_order_id_returns_an_empty_list(tmp_path) -> None:
    """The lookup NEVER raises on an absent order -- ``no_accepted_latch_order``
    is the RESOLVER's reason (case 2/4), reached from an empty list."""
    conn, _cfg, candidate_id = build_world(tmp_path, "absent")
    try:
        _accept(conn, candidate_id)
        assert find_accepted_latch_order(conn, broker_order_id="nope") == []
    finally:
        conn.close()


def test_a_ticker_mismatch_refuses_at_rung_one(tmp_path) -> None:
    """RUNG 1, reached through the LADDER rather than through the pure guard.

    NO CASE ID: case 15c is task 1's, over ``assert_fill_consistent_with_order``
    directly.  This asserts the ladder's own first rung fires -- and it fires
    BEFORE rung 2, which matters because a wrong-ticker link is usually also
    parent-incoherent and a reader could not otherwise tell which rung ran.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "rung1")
    try:
        order = _accept(conn, candidate_id)
        verdict = _authorize(conn, cfg, order, ticker="ZZZZ")
        assert verdict.decline_reason == "ticker_mismatch"
    finally:
        conn.close()


def test_seed_run_and_helpers_are_importable() -> None:
    """A guard on this module's own imports, so an unused-import cleanup that
    silently drops a fixture helper fails here rather than in a later task."""
    assert callable(seed_run)
    assert callable(order_for_candidate)


# ===========================================================================
# 22A-R4-04 -- RUNG 5 IS ORDER-SCOPED. BOTH HALVES MOVED TOGETHER.
# ===========================================================================
def test_a_cancel_of_a_DIFFERENT_order_does_not_refuse(tmp_path) -> None:
    """A cancel names ONE broker order (`swing/data/models.py`, 0033 CHECK).

    A fire can legitimately be placed, cancelled and RE-PLACED, so the ledger
    holds a cancel naming the OLD order beside a live acceptance of the new
    one.  PRE-FIX rung 5 scanned by ``candidate_id`` alone and refused
    ``order_cancelled``; POST-FIX it binds the cancel's own
    ``actual_broker_order_id`` and ADMITS.  Both values are stated so the
    assertion distinguishes.

    The cancel is dated STRICTLY BEFORE the fill -- the position that kills --
    so nothing but the order-id binding can be what admits it.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r404")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=ACCEPT_SESSION,
                recorded_ts=f"{ACCEPT_SESSION.isoformat()}T09:00:00",
                broker_order_id="an-older-order")
        verdict = _authorize(conn, cfg, order)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.probe_evidence["authorization"][
            "rung5_cancel_intent_id"]["input"] is None
    finally:
        conn.close()


def test_a_cancel_of_THIS_order_still_refuses_after_the_narrowing(
        tmp_path) -> None:
    """THE CONTROL, in its own test so a failure names it.

    ONE dimension differs from the case above -- the cancel names THIS order --
    and the refusal returns.  Without this half a narrowing that dropped rung 5
    entirely would pass.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r404ctl")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=ACCEPT_SESSION,
                recorded_ts=f"{ACCEPT_SESSION.isoformat()}T09:00:00",
                broker_order_id=BROKER_ORDER_ID)
        assert _authorize(conn, cfg, order).decline_reason == "order_cancelled"
    finally:
        conn.close()


def test_a_same_session_cancel_of_a_DIFFERENT_order_does_not_refuse(
        tmp_path) -> None:
    """The unorderable branch is narrowed by the SAME binding.

    A cancel stamped ON the fill session for a DIFFERENT order is not this
    order's ambiguity.  PRE-FIX ``cancel_ordering_ambiguous``; POST-FIX admits.
    Its control is case 29c, which is unchanged and still refuses.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r404b")
    try:
        order = _accept(conn, candidate_id)
        _cancel(conn, candidate_id, session=FILL_SESSION,
                recorded_ts=f"{FILL_SESSION.isoformat()}T09:00:00",
                broker_order_id="an-older-order")
        assert _authorize(conn, cfg, order).admitted is True
    finally:
        conn.close()


# ===========================================================================
# 22A-R3-14 -- RUNG 3b'S LEDGER READ IS GUARDED LIKE EVERY OTHER ONE
# ===========================================================================
def test_an_unreadable_intent_ledger_refuses_rather_than_escaping(
        tmp_path) -> None:
    """PRE-FIX the exception ESCAPED and blocked a money-bearing entry.

    The competitor loop and the probe both catch a failed
    ``list_intents_for_latch``; rung 3b did not, so an unreadable ledger
    propagated out of the whole ladder -- the `0036:26-38` inversion, in the
    one rung that had not been swept.

    PRE-FIX: ``RuntimeError`` out of ``authorize_accepted_order``.
    POST-FIX: a fail-closed ``validity_evidence_unavailable`` refusal.
    """
    import swing.data.repos.latch_order_intents as repo

    conn, cfg, candidate_id = build_world(tmp_path, "r314")
    try:
        order = _accept(conn, candidate_id)
        real = repo.list_intents_for_latch

        def boom(*a, **kw):
            raise RuntimeError("the ledger is unreadable")

        repo.list_intents_for_latch = boom
        try:
            verdict = _authorize(conn, cfg, order)
        finally:
            repo.list_intents_for_latch = real
        assert verdict.admitted is False
        assert verdict.decline_reason == "validity_evidence_unavailable"
        assert verdict.recognised_but_underivable is True
    finally:
        conn.close()
