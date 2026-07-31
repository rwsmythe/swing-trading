"""ITEM 6 -- the mandate limit price is SINGLE-SOURCED, and PRESENCE is not
keyed on PRICE (RD + CHARC rulings, 2026-07-30).

(a) ONE function computes the mandate's limit price. 21-B's emitter and 21-A's
    comparator call THE SAME one; the comparator's own re-rounding of the cap
    is DELETED rather than taught to floor.
(b) `LATCH_ARMED_NO_RESTING_ORDER` keys on PRESENCE and SHAPE, never on exact
    limit equality. A limit difference is a per-field DELTA.

THE LIVE SUBJECT IS VSTS, whose cap is 17.407 (pivot 16.90 x 1.03). Under the
pre-fix pair the framework emitted floor -> 17.40 while the comparator expected
round -> 17.41, so the operator's correct order attributed to NO latch. 49.5% of
two-decimal pivots produce a cap whose third decimal is non-zero, so this is the
ordinary case rather than a corner.
"""
from __future__ import annotations

from datetime import date

from swing.latches import constants as _constants
from swing.latches import order_intent as _order_intent
from swing.latches import orders as _orders
from swing.latches.constants import mandate_limit_price
from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch, RestingOrder
from swing.latches.order_intent import compute_order_delta
from swing.latches.orders import join_orders_to_latches

VSTS_PIVOT = 16.90
VSTS_CAP = round(VSTS_PIVOT * 1.03, 4)        # 17.407
VSTS_LIMIT = 17.40                            # floor to whole cents


def _latch(cid: int, *, cap: float, pivot: float = VSTS_PIVOT, state="armed",
           clear_reason=None, anchor=date(2026, 7, 27)) -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=cid, evaluation_run_id=130, ticker="VSTS",
            detection_date=anchor.isoformat(), pipeline_run_id=None),
        latched_pivot=pivot, latched_initial_stop=pivot - 2.0, zone_cap=cap,
        anchor=anchor, horizon_expiry=date(2026, 9, 8), sessions_elapsed=1,
        sessions_to_horizon=29, state=state, clear_reason=clear_reason,
        clear_session=None if clear_reason is None else anchor)


def _limit_order(price: float, *, order_id="7001") -> RestingOrder:
    return RestingOrder(
        order_id=order_id, ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="LIMIT", limit_price=price, stop_price=None,
        status="WORKING", duration="GOOD_TILL_CANCEL")


# --------------------------------------------------------------------------
# (a) ONE definition, and the second one is DELETED
# --------------------------------------------------------------------------
def test_the_premise_the_two_roundings_actually_disagree_on_the_live_cap():
    """Asserted inline so the fix's reason cannot rot.

    `round(17.407, 2)` is 17.41, which EXCEEDS the cap -- 21-A's comparator was
    accepting a price OUTSIDE the zone, which is why the floor basis (RD's) is
    the correct one and 21-A was wrong on its own terms.
    """
    assert round(VSTS_CAP, 2) == 17.41
    assert round(VSTS_CAP, 2) > VSTS_CAP
    assert mandate_limit_price(VSTS_CAP) == VSTS_LIMIT
    assert mandate_limit_price(VSTS_CAP) <= VSTS_CAP


def test_the_emitter_and_the_comparator_call_THE_SAME_function():
    """CHARC's ruling on the fix SHAPE: DELETE the second definition.

    Two independently-correct roundings of one quantity is the D6 class -- a
    comment-enforced parallel copy that drifted in production until one shared
    function killed it. So this is an IDENTITY assertion, not a value one: a
    second implementation that happened to agree today would pass a value test
    and fail this.
    """
    assert _orders.mandate_limit_price is mandate_limit_price
    assert _order_intent.mandate_limit_price is mandate_limit_price
    assert mandate_limit_price is _constants.mandate_limit_price
    assert not hasattr(_order_intent, "quantize_limit_down"), (
        "the second definition must be DELETED, not aliased -- an alias is a "
        "name the next reader can re-implement behind")


def test_the_comparator_agrees_with_the_price_the_framework_ACTUALLY_EMITTED():
    """THE MERGE-BLOCKING DISCRIMINATOR, on the live VSTS geometry.

    PRE-FIX: the comparator asked `round(17.407, 2) == 17.41`, the emitter
    emitted 17.40, so `_match_latch` found no hit -- the operator's correct
    order became a STRAY and `order_limit_agrees` read False.
    POST-FIX: both sides ask `mandate_limit_price(17.407)` -> 17.40 and agree.
    """
    latch = _latch(9101, cap=VSTS_CAP)
    prepared = _order_intent.compute_prepared_order(
        latch=latch, regime_order_type="LIMIT", regime_close=17.20,
        regime_close_session="2026-07-29",
        sizing_inputs=_order_intent.SizingInputs(
            real_equity=1234.56, equity_floor=7500.0, sizing_equity=7500.0,
            max_risk_pct=0.005, position_pct_cap=0.15)).order
    assert prepared.limit_price == VSTS_LIMIT
    joins, alarms = join_orders_to_latches(
        latches=[latch], orders=[_limit_order(prepared.limit_price)])
    join = joins[latch.identity.candidate_id]
    assert join.unmatched_orders == (), "the framework's own order is not a STRAY"
    assert join.order_limit_agrees is True
    assert [a.kind for a in alarms] == []


# --------------------------------------------------------------------------
# (b) PRESENCE is not PRICE
# --------------------------------------------------------------------------
def test_a_one_cent_limit_difference_is_a_DELTA_and_NOT_a_PRESENCE_ALARM():
    """RD's ruling (b), and the geometry where the alarm actually fired.

    An older latch CLEARED at a cap that floors to 17.40 and a LIVE latch armed
    at a cap that floors to 17.41. The operator's resting GTC LIMIT is at 17.40
    -- one cent below the live mandate's limit, and an exact match for the
    cleared one.

    PRE-FIX: `_match_latch` attributed the order to the CLEARED latch, so the
    live latch had no covering order and `LATCH_ARMED_NO_RESTING_ORDER` fired --
    the loudest alarm on the panel, saying "there is NO resting BUY order",
    about a ticker carrying a resting GTC BUY limit at the zone edge. A FALSE
    STATEMENT, not a threshold miss.
    POST-FIX: an order carrying NO stop leg can only ever have been attributed
    by limit equality, and the limit may never key the presence alarm -- so the
    live mandate reads as COVERED and the one-cent difference travels as the
    per-field DELTA the execution-parity ledger exists to record.
    """
    cleared = _latch(9201, cap=17.4049, state="superseded",
                     clear_reason="superseded", anchor=date(2026, 6, 25))
    live = _latch(9202, cap=17.4149, anchor=date(2026, 7, 27))
    assert mandate_limit_price(cleared.zone_cap) == 17.40
    assert mandate_limit_price(live.zone_cap) == 17.41, (
        "the premise: the two mandates' limits differ by exactly one cent")

    order = _limit_order(17.40)
    joins, alarms = join_orders_to_latches(
        latches=[cleared, live], orders=[order])
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in {a.kind for a in alarms}, (
        "an order one cent from the cap DOES implement the mandate; calling it "
        "'no resting order' is a false statement, not a threshold problem")
    assert joins[live.identity.candidate_id] is not None

    # ... and the difference IS reported, through the delta channel.
    delta = compute_order_delta(
        {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
         "stop_price": None, "limit_price": mandate_limit_price(live.zone_cap),
         "quantity": 40},
        {"order_type": order.order_type, "duration": order.duration,
         "stop_price": order.stop_price, "limit_price": order.limit_price,
         "quantity": int(order.quantity)})
    assert delta.limit_price_delta == -0.01
    assert delta.any_difference is True


def test_a_DAY_order_does_NOT_cover_the_mandate_and_the_alarm_stays_TRUTHFUL():
    """CODEX R1 MAJOR on the ruling pass. Duration and order type are NAMED
    shape keys in RD's ruling, and the harm is the FTRE failure mode itself: a
    DAY order expires tonight and leaves the operator uncovered tomorrow, yet it
    used to SUPPRESS the critical presence alarm merely by existing.

    AND THE ALARM MUST NOT LIE WHILE FIXING IT: the detail may not claim "NO
    resting BUY order at the broker" about a ticker that plainly has one. An
    alarm firing on a true condition with a false explanation is the same defect
    the presence/price half of this ruling removes.
    """
    live = _latch(9401, cap=VSTS_CAP)
    day = RestingOrder(
        order_id="7011", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="LIMIT", limit_price=VSTS_LIMIT, stop_price=None,
        status="WORKING", duration="DAY")
    _, alarms = join_orders_to_latches(latches=[live], orders=[day])
    presence = [a for a in alarms if a.kind == "LATCH_ARMED_NO_RESTING_ORDER"]
    assert len(presence) == 1
    assert "NO resting BUY order at the broker" not in presence[0].detail
    assert "wrong shape" in presence[0].detail


def test_a_PLAIN_BUY_STOP_carries_no_cap_and_does_not_cover_the_mandate():
    """The stop-only order the R7 CRITICAL named: it has no limit leg at all, so
    nothing stops the operator chasing. It is not one of the two mandate forms
    and therefore is not coverage."""
    live = _latch(9402, cap=VSTS_CAP)
    stop_only = RestingOrder(
        order_id="7012", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="STOP", limit_price=None, stop_price=VSTS_PIVOT,
        status="WORKING", duration="GOOD_TILL_CANCEL")
    _, alarms = join_orders_to_latches(latches=[live], orders=[stop_only])
    assert "LATCH_ARMED_NO_RESTING_ORDER" in {a.kind for a in alarms}


def test_an_UNREAD_order_type_cannot_ASSERT_coverage():
    """CODEX R2 MAJOR. `SchwabOrderResponse.order_type` is EXPLICITLY allowed to
    be empty ("must be empty or in ...") and the mapper defaults a missing
    `orderType` to `""`, so this is a reachable production payload -- not a
    hypothetical.

    Coverage is an ASSERTION OF A MATCH, and the project's asymmetry rule says
    you may not assert a match from an unknown. With no type there is no
    evidence the resting order is a mandate form at all, so letting it stand as
    coverage prints an affirmative all-clear over an instrument nobody read.
    """
    live = _latch(9404, cap=VSTS_CAP)
    typeless = RestingOrder(
        order_id="7014", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="", limit_price=VSTS_LIMIT, stop_price=None,
        status="WORKING", duration="GOOD_TILL_CANCEL")
    _, alarms = join_orders_to_latches(latches=[live], orders=[typeless])
    assert "LATCH_ARMED_NO_RESTING_ORDER" in {a.kind for a in alarms}


def test_a_LIMIT_CARRYING_A_STOP_LEG_does_not_cover_the_mandate():
    """CODEX R2 MAJOR -- the sharpest of this pass, because it reached an
    AFFIRMATIVE ALL-CLEAR.

    A `LIMIT` carrying a stop trigger at the frozen pivot attributes to the
    latch ON ITS STOP LEG, so it used to be counted as coverage -- and in the
    PULLBACK regime the fragment expects no stop leg at all, so nothing else
    inspected it either: `mandate_shape_mismatch` sees the right type, the leg
    check is disabled, and the panel reads clean over a malformed order.

    The rule applied is the one migration 0033 ALREADY enforces on the FRAMEWORK
    side (`framework_order_type <> 'LIMIT' OR framework_stop_price IS NULL`),
    turned on the OBSERVED order.
    """
    live = _latch(9405, cap=VSTS_CAP)
    malformed = RestingOrder(
        order_id="7015", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="LIMIT", limit_price=VSTS_LIMIT, stop_price=VSTS_PIVOT,
        status="WORKING", duration="GOOD_TILL_CANCEL")
    joins, alarms = join_orders_to_latches(latches=[live], orders=[malformed])
    assert "LATCH_ARMED_NO_RESTING_ORDER" in {a.kind for a in alarms}
    assert joins[live.identity.candidate_id].orders, (
        "the malformed order is still REPORTED against the mandate -- it is "
        "removed from COVERAGE, not from the panel")


def test_a_STOP_LIMIT_MISSING_its_trigger_does_not_cover_the_mandate():
    """The mirror image: a stop-limit with no trigger cannot fire at the pivot,
    so it does not implement the breakout mandate either."""
    live = _latch(9406, cap=VSTS_CAP)
    malformed = RestingOrder(
        order_id="7016", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="STOP_LIMIT", limit_price=VSTS_LIMIT, stop_price=None,
        status="WORKING", duration="GOOD_TILL_CANCEL")
    _, alarms = join_orders_to_latches(latches=[live], orders=[malformed])
    assert "LATCH_ARMED_NO_RESTING_ORDER" in {a.kind for a in alarms}


def test_an_ABSENT_duration_is_NOT_asserted_against():
    """`mandate_shape_mismatch` deliberately does not assert against a payload
    that simply does not carry a duration -- unknown is not wrong -- and the
    coverage rule must not disagree with it, or an older payload shape would
    make the panel permanently noisy."""
    live = _latch(9403, cap=VSTS_CAP)
    no_duration = RestingOrder(
        order_id="7013", ticker="VSTS", instruction="BUY", quantity=40.0,
        order_type="LIMIT", limit_price=VSTS_LIMIT, stop_price=None,
        status="WORKING", duration=None)
    _, alarms = join_orders_to_latches(latches=[live], orders=[no_duration])
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in {a.kind for a in alarms}


def test_a_STOP_LEG_still_keys_the_presence_alarm_the_post_supersede_geometry():
    """THE PROTECTION THAT MAY NOT REGRESS. The stop leg is a NAMED SHAPE key
    in RD's ruling, and it is what 21-A's post-supersede case rests on: an old
    latch superseded at one pivot with its GTC stop-limit still resting, a new
    latch armed at a higher pivot with nothing behind it. A ticker-level rule
    goes silent there and the operator is never told the LIVE mandate is naked.
    """
    cleared = _latch(9301, cap=round(18.34 * 1.03, 4), pivot=18.34,
                     state="superseded", clear_reason="superseded",
                     anchor=date(2026, 6, 25))
    live = _latch(9302, cap=round(20.19 * 1.03, 4), pivot=20.19,
                  anchor=date(2026, 7, 27))
    stale = RestingOrder(
        order_id="7009", ticker="VSTS", instruction="BUY", quantity=10.0,
        order_type="STOP_LIMIT",
        limit_price=mandate_limit_price(cleared.zone_cap),
        stop_price=18.34, status="WORKING", duration="GOOD_TILL_CANCEL")
    _, alarms = join_orders_to_latches(latches=[cleared, live], orders=[stale])
    kinds = {a.kind for a in alarms}
    assert "LATCH_ARMED_NO_RESTING_ORDER" in kinds
    assert "ORDER_RESTING_LATCH_CLEARED" in kinds
