"""THE AUTHORIZE-THEN-ABORT CLASS, CLOSURE-CHECKED (CHARC, ruled 2026-09-01).

**THE RULE: the TRIGGER's predicate set MUST BE A SUBSET of the SERVICE's
admission predicates.**  The trigger is a BACKSTOP against writes that BYPASS
the service -- never the discovery point for an input the service ADMITS.
Anything the trigger will refuse, the service refuses FIRST, with a typed
message.

**FIVE INSTANCES IN ONE ARC, read in the preserved ledger rather than reasoned
from the label**, and all five have one shape: the SERVICE ADMITS and a
downstream trigger or CHECK then ABORTS, so the operator gets a raw ``sqlite3``
error where the service would have given a legible refusal.

  * ``R6-05`` -- three values collapsed to two; an absent envelope symbol read
    as PASS while the trigger required TEXT.
  * ``SS-4``  -- the service STRIPPED a key the trigger BINDS, which this
    arc's own ledger already called an authorize-then-abort delivering an
    ILLEGIBLE refusal.
  * ``R15-02`` -- ``+inf`` passes ``0033:414``'s ``CHECK (p > 0)``, gets
    authorized, and then fails ``json_valid`` at the citation INSERT.

**ENFORCEMENT IS A CLOSURE CHECK, NOT A ROSTER, and it deliberately reuses the
``AL-3`` / ``SS-12`` instrument rather than authoring a fourth**: every
SQL-bound trigger clause maps to a NAMED service-side refusal, asserted
mechanically in BOTH directions, so a clause added to either side without its
twin fails loudly.

**CANON PLACEMENT: this is the persist-canonical family's OTHER HALF.**
Persist-canonical governs where SQL RE-DERIVES a judgment the service owns;
this governs where SQL holds a STRICTER predicate than the service checks.
Both are the service and the schema disagreeing about the same input, and both
resolve by making the SERVICE the single authority that speaks to the operator.

WHAT THIS MODULE PROVES, AND WHAT IT DOES NOT -- stated rather than left to
look complete, because *"do not claim exact when you are not"* is the standing
rule:

  * PROVED MECHANICALLY, both directions: every SQL-bound clause names a
    service-side decline reason; every named reason is a live member of
    ``DECLINE_REASONS``; and every named reason is one the service module can
    actually CONSTRUCT (the static walk, reused from task 8 rather than
    re-spelled).
  * PROVED BY EXECUTION: the three MEASURED instances above -- the service
    refuses each with a typed refusal, so the trigger's own refusal is
    unreachable through the service.
  * **NOT PROVED:** that the service's predicate is at least as strict as the
    trigger's for the remaining eleven clauses.  Establishing that in general
    needs a solver over two languages, not a test; what is enforced here is
    that every clause HAS a named counterpart and that the counterpart is
    live, which is what makes a missing twin loud instead of silent.

FROZEN CLOCK: nothing here reads a clock.
"""
from __future__ import annotations

import math

import pytest

from swing.trades.latched_origin import (
    AUTHORIZATION_CLAUSES,
    DECLINE_REASONS,
    PROBE_GUARD_CLAUSES,
    SQL_BOUND,
    assert_fill_consistent_with_order,
)
from tests.trades.test_22a_task8_resolver import _constructed_reason_strings

ALL_CLAUSES = AUTHORIZATION_CLAUSES + PROBE_GUARD_CLAUSES
SQL_BOUND_KEYS = tuple(c.key for c in ALL_CLAUSES if c.binding == SQL_BOUND)

# ---------------------------------------------------------------------------
# THE ONE HAND-WRITTEN ROSTER: clause key -> the SERVICE-side decline reason
# that refuses the SAME input before the trigger can see it.
#
# It is hand-written for the same reason AL-3's is: the mapping is a JUDGMENT
# about which service predicate covers which SQL clause, and no walk can derive
# a judgment.  What is mechanical is everything AROUND it -- both directions of
# membership, the reason's liveness, and the reason's emittability.
# ---------------------------------------------------------------------------
SERVICE_SIDE_REFUSAL: dict[str, str] = {
    "rung1_link_ticker": "ticker_mismatch",
    "rung2_link_parent": "link_parent_incoherent",
    "rung3_validity_outcome": "linked_validity_not_accepted",
    "rung3b_latest_validity_child": "validity_superseded",
    "rung3c_link_broker_order_id": "link_field_unbound",
    "rung4_governing_place_intent": "place_cycle_superseded",
    "rung5_cancel_intent_id": "order_cancelled",
    "rung6_consuming_trade_id": "mandate_already_consumed",
    "rung9_stored_freeze_tier": "pre_barrier_unproven",
    # THE THREE MEASURED INSTANCES.
    "guard_fill_origin": "untrusted_fill_origin",
    # R6-05: an ABSENT symbol read as PASS while the trigger required TEXT.
    "guard_envelope_symbol": "ticker_mismatch",
    "guard_quantity": "quantity_exceeds_order",
    "guard_framework_price_bound": "fill_outside_frozen_zone",
    # R15-02: `+inf` is SCHEMA-LEGAL under `0033:414` and aborts at the
    # citation INSERT; the service now refuses it at the authorization
    # boundary under the reason that says what is true of a frozen value it
    # cannot use.
    "guard_broker_limit_bound": "frozen_value_unavailable",
}


def _order(**over):
    """The task-1 order shape, imported rather than re-spelled."""
    from tests.trades.test_22a_task1_envelope_guards import _order as build

    return build(**over)


def _judge(order, **over):
    kwargs = dict(
        ticker=order.ticker, price=53.98, shares=2,
        fill_origin="schwab_auto", envelope_symbol=order.ticker)
    kwargs.update(over)
    return assert_fill_consistent_with_order(order, **kwargs)


# ---------------------------------------------------------------------------
# THE CLOSURE, IN BOTH DIRECTIONS
# ---------------------------------------------------------------------------
def test_every_sql_bound_clause_names_a_service_side_refusal() -> None:
    """DIRECTION A.  A clause the trigger will refuse and the service will not
    is an authorize-then-abort waiting to be met by an operator."""
    missing = sorted(set(SQL_BOUND_KEYS) - set(SERVICE_SIDE_REFUSAL))
    assert not missing, (
        f"{len(missing)} SQL-bound trigger clause(s) name no service-side "
        f"refusal: {missing}. Under CHARC's rule the trigger's predicate set "
        f"is a SUBSET of the service's, so each of these is either an "
        f"authorize-then-abort or a missing roster entry -- and the two are "
        f"indistinguishable from here, which is why the entry is required.")


def test_every_named_service_refusal_belongs_to_a_live_clause() -> None:
    """DIRECTION B.  A stale entry is a claim about a clause that no longer
    exists, and it reads exactly like a covered one."""
    stray = sorted(set(SERVICE_SIDE_REFUSAL) - set(SQL_BOUND_KEYS))
    assert not stray, (
        f"the roster names clauses that are not SQL-bound (or not clauses at "
        f"all): {stray}")


def test_every_named_reason_is_a_live_roster_member() -> None:
    unknown = sorted(set(SERVICE_SIDE_REFUSAL.values()) - DECLINE_REASONS)
    assert not unknown, (
        f"named service refusals outside the {len(DECLINE_REASONS)}-member "
        f"DECLINE_REASONS roster: {unknown}")


def test_every_named_reason_is_one_the_service_can_actually_construct() -> None:
    """AND THE ROSTER IS NOT THE FIX -- the static walk is.

    A reason named here that no site in ``latched_origin`` constructs would
    make the mapping a sentence rather than a contract: the clause would still
    be an authorize-then-abort and the entry would read as its remedy.  The
    walk is task 8's, IMPORTED, so the two cannot drift.
    """
    constructed = _constructed_reason_strings()
    unemittable = sorted(set(SERVICE_SIDE_REFUSAL.values()) - constructed)
    assert not unemittable, (
        f"the roster names reasons `latched_origin` never constructs: "
        f"{unemittable}")


def test_the_sql_bound_count_is_stated_and_read_from_the_clauses() -> None:
    """The count comes from READING the clause roster, never from a grep."""
    assert len(SQL_BOUND_KEYS) == len(set(SQL_BOUND_KEYS)), "duplicate keys"
    assert len(SQL_BOUND_KEYS) == 14, (
        f"{len(SQL_BOUND_KEYS)} SQL-bound clauses; the roster above and this "
        f"stated count move together or one of them is stale")


# ---------------------------------------------------------------------------
# THE NEGATIVE SATISFIABILITY PROOF, for the three MEASURED instances
#
# Note the SYMMETRY with the proof this arc already built: that one shows a
# guard CAN accept a truthful row; this one shows a guard CANNOT be the first
# to refuse a service-admitted one.
# ---------------------------------------------------------------------------
def test_R6M5_an_absent_envelope_symbol_is_refused_by_the_SERVICE() -> None:
    """PRE-FIX the guard returned ``None`` (PASS) for an absent symbol, the
    evidence blob recorded a passing guard whose input was ``null``, and the
    citation trigger -- which requires that entry to be TEXT -- then ABORTED a
    correction the service had authorized."""
    assert _judge(_order(), envelope_symbol=None) == (
        SERVICE_SIDE_REFUSAL["guard_envelope_symbol"])
    assert _judge(_order()) is None, (
        "the control: an AGREEING symbol still passes, so the guard refuses "
        "absence and not everything")


def test_R15M2_a_non_finite_broker_limit_is_refused_by_the_SERVICE() -> None:
    """PRE-FIX ``+inf`` passed ``0033:414``'s ``CHECK (p > 0)``, was
    AUTHORIZED, and then failed ``json_valid`` at the citation INSERT --
    ``json.dumps(inf)`` writes the bare token ``Infinity``.

    The premise is measured here rather than asserted in prose: the value is
    schema-legal, so the refusal has to come from the service."""
    assert math.isinf(float("inf")) and float("inf") > 0, (
        "the premise: `inf > 0` is TRUE, which is why the CHECK admits it")
    for limit in (float("inf"), float("-inf")):
        assert _judge(_order(actual_limit_price=limit)) == (
            SERVICE_SIDE_REFUSAL["guard_broker_limit_bound"]), limit
    assert _judge(_order(actual_limit_price=55.59)) is None, (
        "the control: a FINITE limit is still accepted")


def test_SS4_a_padded_envelope_is_REFUSED_BY_THE_RESOLVER(tmp_path) -> None:
    """SS-4's shape, proved THROUGH THE SERVICE (Codex 22A-FIX-R1-07).

    The service STRIPPED whitespace on a key the citation trigger BINDS by
    ``json_extract``, which strips nothing -- so the service ADMITTED and the
    trigger then ABORTED the correction with the generic citation-graph
    message: an authorize-then-abort delivering an ILLEGIBLE refusal, named as
    such in this arc's own ledger.

    **THE FIRST VERSION OF THIS ROW ASSERTED ONLY THAT TWO HELPER PREDICATES
    ANSWER ``False`` AND ``True``** -- a resolver that recognised the envelope
    and then omitted or bypassed the canonicality refusal passed a case
    claiming to be a negative-satisfiability proof.  It runs the RESOLVER now,
    on a world whose link the padded document names, and asserts the typed
    refusal the service must produce BEFORE the trigger can see the row.
    """
    import json
    from datetime import date
    from types import SimpleNamespace

    from swing.trades.latched_origin import (
        envelope_is_canonical,
        envelope_recognises_an_order,
        resolve_latched_provenance,
    )
    from tests._latch_probe_world_22a import (
        BROKER_ORDER_ID,
        FILL_SESSION,
        TICKER,
        accept_and_link,
    )
    from tests.trades.test_22a_task8_resolver import build_world

    padded = json.dumps({"schwab_order_id": f" {BROKER_ORDER_ID} ",
                         "schwab_instrument_symbol": TICKER})
    assert envelope_is_canonical(padded) is False, (
        "the two domains must READ this document differently, or the case is "
        "about a shape the divergence does not reach")
    assert envelope_recognises_an_order(padded) is True, (
        "a document the domains read differently must be RECOGNISED, so the "
        "ladder refuses it rather than letting the ordinary chain run")

    conn, cfg, candidate_id = build_world(tmp_path, "ss4")
    try:
        accept_and_link(conn, candidate_id, session=date(2026, 7, 24))
        conn.commit()

        def _req(envelope):
            return SimpleNamespace(
                ticker=TICKER, entry_date=FILL_SESSION.isoformat(),
                entry_price=18.50, shares=2, fill_origin="schwab_auto",
                hypothesis_label=None, candidate_id=None,
                schwab_source_value_json=envelope)

        verdict = resolve_latched_provenance(conn, cfg, _req(padded))
        assert verdict.admitted is False
        assert verdict.decline_reason == "envelope_not_canonical", (
            "the SERVICE must refuse this document; if it admits, the "
            "citation trigger is the first thing to refuse it and the "
            "operator gets a raw sqlite error")
        assert verdict.recognised_but_underivable is True, (
            "a recognised-and-refused envelope must land honest-unset rather "
            "than falling through to the ordinary chain")

        # THE CONTROL: the SAME world with the UNPADDED document ADMITS, so
        # the refusal is the padding's doing and not the fixture's.
        clean = json.dumps({"schwab_order_id": BROKER_ORDER_ID,
                            "schwab_instrument_symbol": TICKER})
        assert envelope_is_canonical(clean) is True
        assert resolve_latched_provenance(
            conn, cfg, _req(clean)).admitted is True
    finally:
        conn.close()


@pytest.mark.parametrize("key", sorted(SERVICE_SIDE_REFUSAL))
def test_the_roster_entry_is_not_blank(key: str) -> None:
    """A blank entry would satisfy both membership directions while naming
    nothing -- the roster failing the way rosters fail."""
    assert SERVICE_SIDE_REFUSAL[key].strip(), key
