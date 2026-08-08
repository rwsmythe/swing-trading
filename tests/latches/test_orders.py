"""The two alarms (plan A.9)."""
from __future__ import annotations

from datetime import date

from swing.latches.constants import (
    MANDATE_ORDER_DURATIONS,
    MANDATE_ORDER_TYPE_BREAKOUT,
    MANDATE_ORDER_TYPE_PULLBACK,
    MANDATE_ORDER_TYPES,
)
from swing.latches.models import DailyBar, FireRow, RestingOrder
from swing.latches.orders import (
    expected_mandate_order_type,
    join_orders_to_latches,
    mandate_shape_mismatch,
    to_resting_orders,
)
from swing.latches.service import derive_latches

FTRE_FIRE = FireRow(
    candidate_id=9500, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
    initial_stop=14.88, action_session_date="2026-07-20",
    run_ts="2026-07-17T17:30:05", pipeline_run_id=135)


def _armed():
    return derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches


def _order(**over):
    base = dict(order_id="1", ticker="FTRE", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", limit_price=18.89, stop_price=18.34,
                status="WORKING")
    base.update(over)
    return RestingOrder(**base)


def test_armed_with_no_resting_order_fires_the_ftre_alarm():
    joins, alarms = join_orders_to_latches(latches=_armed(), orders=())
    assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"]
    assert alarms[0].ticker == "FTRE"
    assert alarms[0].latch_candidate_id == 9500
    assert alarms[0].severity == "critical"
    assert joins[9500].orders == ()


def test_a_matching_resting_order_promotes_the_state_and_silences_the_alarm():
    joins, alarms = join_orders_to_latches(latches=_armed(), orders=(_order(),))
    assert alarms == ()
    j = joins[9500]
    assert j.order_stop_agrees is True
    assert j.order_limit_agrees is True


def test_a_sell_order_never_satisfies_an_entry_latch():
    joins, alarms = join_orders_to_latches(
        latches=_armed(), orders=(_order(instruction="SELL"),))
    assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"]
    assert joins[9500].orders == ()


def test_a_filled_or_canceled_order_is_not_resting():
    for status in ("FILLED", "CANCELED", "REJECTED", "EXPIRED", "REPLACED"):
        _, alarms = join_orders_to_latches(
            latches=_armed(), orders=(_order(status=status),))
        assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"], status


def test_an_indeterminate_order_suppresses_both_alarms():
    joins, alarms = join_orders_to_latches(
        latches=_armed(), orders=(_order(status="PENDING_CANCEL"),))
    assert alarms == ()
    assert joins[9500].indeterminate is True


def test_disagreeing_prices_are_reported_without_silencing_the_join():
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=18.59, limit_price=19.15),))
    j = joins[9500]
    assert j.order_stop_agrees is False
    assert j.order_limit_agrees is False


def test_price_comparison_uses_display_precision():
    """18.340001 must not read as 'operator edited' (the precision-parity
    gotcha)."""
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=18.340001),))
    assert joins[9500].order_stop_agrees is True


def test_unknown_side_of_a_comparison_is_none_not_false():
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=None),))
    assert joins[9500].order_stop_agrees is None


def test_order_resting_on_a_cleared_latch_fires_the_stale_order_alarm():
    bars = [DailyBar(session=date(2026, 7, 21), open=15.0, high=15.2,
                     low=14.1, close=14.0)]
    cleared = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22),
        derivation_session=date(2026, 7, 21)).latches
    _, alarms = join_orders_to_latches(latches=cleared, orders=(_order(),))
    assert [a.kind for a in alarms] == ["ORDER_RESTING_LATCH_CLEARED"]
    assert alarms[0].severity == "critical"    # cleared by INVALIDATION
    assert "invalidation" in alarms[0].detail


def test_order_resting_with_no_latch_at_all_also_fires_the_stale_alarm():
    _, alarms = join_orders_to_latches(
        latches=(), orders=(_order(ticker="ZZZZ"),))
    assert [a.kind for a in alarms] == ["ORDER_RESTING_LATCH_CLEARED"]
    assert alarms[0].latch_candidate_id is None


def test_a_superseded_latch_with_a_resting_order_alarms_critical():
    """RD gate: "the panel must LOUDLY show that any resting order placed
    against the old level no longer matches the new mandate." Post-supersede
    the ticker has a LIVE latch AND a cleared one, so a ticker-level rule would
    have gone silent -- this is the geometry the per-order rule was built for."""
    fires = [
        FireRow(candidate_id=6001, evaluation_run_id=121, ticker="FTRE",
                pivot=18.34, initial_stop=14.88,
                action_session_date="2026-07-20",
                run_ts="2026-07-17T17:30:05", pipeline_run_id=135),
        FireRow(candidate_id=6002, evaluation_run_id=125, ticker="FTRE",
                pivot=20.19, initial_stop=16.515,
                action_session_date="2026-07-24",
                run_ts="2026-07-23T17:30:05", pipeline_run_id=139),
    ]
    latches = derive_latches(
        fires=fires, bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches
    stale = _order(stop_price=18.34, limit_price=18.89)   # the OLD mandate
    _, alarms = join_orders_to_latches(latches=latches, orders=(stale,))
    alarm = next(a for a in alarms if a.kind == "ORDER_RESTING_LATCH_CLEARED")
    assert alarm.latch_candidate_id == 6001
    assert alarm.severity == "critical"
    assert "superseded" in alarm.detail


def test_horizon_cleared_latch_with_a_resting_order_is_warning_not_critical():
    """A horizon expiry carries NO manual-cancel duty the way an invalidation
    or a supersede does, so the stale-order alarm degrades to `warning`.

    NOTE the clock: under the RULED 30-session horizon this fire (2026-07-01)
    expires 2026-08-13, so the derivation must be run AT that session. (The
    plan's draft fixture used 2026-07-30, which was only expired under the
    SUPERSEDED ~20-session horizon -- corrected here.)"""
    old = FireRow(candidate_id=9276, evaluation_run_id=103, ticker="FTRE",
                  pivot=18.34, initial_stop=15.00,
                  action_session_date="2026-07-01",
                  run_ts="2026-07-01T06:30:23", pipeline_run_id=116)
    expired = derive_latches(
        fires=[old], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13),
        derivation_session=date(2026, 8, 13)).latches
    assert expired[0].state == "horizon_expired"
    _, alarms = join_orders_to_latches(latches=expired, orders=(_order(),))
    assert alarms[0].kind == "ORDER_RESTING_LATCH_CLEARED"
    assert alarms[0].severity == "warning"
    assert "horizon" in alarms[0].detail


def test_a_declined_latch_alarms_CRITICAL_although_it_shares_horizons_state():
    """T1.3 + T1.4(b) -- THE CALLER-SIDE OBLIGATION (gotcha #31), and the ONLY
    consumer that can discriminate it.

    Option B (OQ-2) gives `declined` and `horizon` the SAME `state`
    (`horizon_expired`), so the mitigation for the two collapsing cannot be a
    comment -- it has to be a test whose output DIFFERS between them. The two
    latches here are byte-identical apart from `clear_reason`, which is what
    makes the discriminator exact: an implementation that selected severity off
    `latch.state` returns the same answer for both and fails.

    (The execution resolver at `classification.py:401` was the other candidate
    and does NOT qualify -- it keys on `clear_reason == "fill"`, so a
    state-keyed defect gives the same answer for a declined and a horizon latch
    and the assertion would pass under the very bug it claims to catch.)
    """
    from dataclasses import replace

    old = FireRow(candidate_id=9276, evaluation_run_id=103, ticker="FTRE",
                  pivot=18.34, initial_stop=15.00,
                  action_session_date="2026-07-01",
                  run_ts="2026-07-01T06:30:23", pipeline_run_id=116)
    expired = derive_latches(
        fires=[old], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13),
        derivation_session=date(2026, 8, 13)).latches[0]
    declined = replace(expired, clear_reason="declined")
    assert declined.state == expired.state == "horizon_expired"

    _, horizon_alarms = join_orders_to_latches(
        latches=(expired,), orders=(_order(),))
    _, declined_alarms = join_orders_to_latches(
        latches=(declined,), orders=(_order(),))
    assert horizon_alarms[0].severity == "warning"
    assert declined_alarms[0].severity == "critical"
    assert "declined" in declined_alarms[0].detail


def test_a_criteria_lapsed_latch_alarms_CRITICAL_although_it_shares_horizons_state():
    """T1.4(b) for the reason OQ-1 was actually RULED about, and the SECOND
    caller-side obligation Option B creates (gotcha #31).

    THREE reasons now share `state == "horizon_expired"`. The two latches here
    are byte-identical apart from `clear_reason`, so an implementation selecting
    severity off `latch.state` returns the same answer for both and fails --
    while every test that inspects only a lapsed latch, or only the frozenset,
    stays green.

    RD's reasoning is what the assertion encodes: the duty (cancel a resting
    order behind a mandate nobody is standing behind) and the consequence of
    ignoring it (an unmandated fill on a rally through a retracted pivot) are
    identical to the invalidation case. Blame -- which IS different here -- lives
    in the disposition, not in the alarm channel.
    """
    from dataclasses import replace

    old = FireRow(candidate_id=9278, evaluation_run_id=103, ticker="FTRE",
                  pivot=18.34, initial_stop=15.00,
                  action_session_date="2026-07-01",
                  run_ts="2026-07-01T06:30:23", pipeline_run_id=116)
    expired = derive_latches(
        fires=[old], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13),
        derivation_session=date(2026, 8, 13)).latches[0]
    lapsed = replace(expired, clear_reason="criteria_lapsed")
    assert lapsed.state == expired.state == "horizon_expired"

    _, horizon_alarms = join_orders_to_latches(
        latches=(expired,), orders=(_order(),))
    _, lapsed_alarms = join_orders_to_latches(
        latches=(lapsed,), orders=(_order(),))
    assert horizon_alarms[0].severity == "warning"
    assert lapsed_alarms[0].severity == "critical"
    assert "criteria_lapsed" in lapsed_alarms[0].detail


# --- Codex R1-2: PER-ORDER attribution, not per-ticker liveness ------------
def _two_latches_one_cleared_one_live():
    """The live VSTS geometry: an earlier latch INVALIDATED (its GTC order is
    still resting at the OLD pivot 13.56) while a newer latch is LIVE at 16.90."""
    fires = [
        FireRow(candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
                pivot=13.56, initial_stop=11.62,
                action_session_date="2026-06-25",
                run_ts="2026-06-24T20:06:25", pipeline_run_id=112),
        FireRow(candidate_id=9999, evaluation_run_id=126, ticker="VSTS",
                pivot=16.90, initial_stop=13.40,
                action_session_date="2026-07-27",
                run_ts="2026-07-24T17:30:06", pipeline_run_id=140),
    ]
    bars = [DailyBar(session=date(2026, 6, 30), open=12.0, high=12.2,
                     low=11.0, close=11.50)]      # closes below 11.62
    return derive_latches(
        fires=fires, bars_by_ticker={"VSTS": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 27)).latches


def test_a_stale_order_alarms_even_though_a_newer_latch_is_live_on_that_ticker():
    """THE R1-2 discriminator. A ticker-level rule ('alarm only when the ticker
    has no live latch') stays SILENT here -- and the operator never learns his
    invalidation-cancel duty is outstanding."""
    latches = _two_latches_one_cleared_one_live()
    stale = _order(ticker="VSTS", stop_price=13.56, limit_price=13.97)
    _, alarms = join_orders_to_latches(latches=latches, orders=(stale,))
    kinds = [a.kind for a in alarms]
    assert "ORDER_RESTING_LATCH_CLEARED" in kinds
    stale_alarm = next(a for a in alarms if a.kind == "ORDER_RESTING_LATCH_CLEARED")
    assert stale_alarm.latch_candidate_id == 8851      # the CLEARED latch
    assert stale_alarm.severity == "critical"          # cleared by invalidation


def test_an_order_matching_the_live_latch_does_not_fire_the_stale_alarm():
    latches = _two_latches_one_cleared_one_live()
    good = _order(ticker="VSTS", stop_price=16.90, limit_price=17.41)
    _, alarms = join_orders_to_latches(latches=latches, orders=(good,))
    assert [a.kind for a in alarms] == []


def test_a_mispriced_order_on_a_live_latch_reports_disagreement_not_a_false_alarm():
    """An order at neither latch's price must NOT produce a factually false
    LATCH_ARMED_NO_RESTING_ORDER."""
    latches = _two_latches_one_cleared_one_live()
    odd = _order(ticker="VSTS", stop_price=15.00, limit_price=15.45)
    joins, alarms = join_orders_to_latches(latches=latches, orders=(odd,))
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in [a.kind for a in alarms]
    assert joins[9999].order_stop_agrees is False


def test_an_out_of_zone_armed_latch_with_a_matching_order_does_not_alarm():
    """Plan A.7.1 reason 1: the resting order at the cap is VALID and fills on
    a pullback, so an out-of-zone latch must fire NEITHER alarm. (Zone escape
    lives entirely in the render layer -- the derivation cleared nothing.)"""
    bars = [DailyBar(session=date(2026, 7, 24), open=19.77, high=20.09,
                     low=19.25, close=19.52)]     # far above the 18.89 cap
    latches = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches
    assert latches[0].state == "armed" and latches[0].clear_reason is None
    _, alarms = join_orders_to_latches(latches=latches, orders=(_order(),))
    assert alarms == ()


# --- to_resting_orders: the SchwabOrderResponse adapter ---------------------
def _schwab_order(**over):
    from swing.integrations.schwab.models import SchwabOrderResponse
    base = dict(order_id="55", status="WORKING", enter_time="2026-07-20T13:30:00Z",
                instrument_symbol="FTRE", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", price=18.89, stop_price=18.34)
    base.update(over)
    return SchwabOrderResponse(**base)


def test_to_resting_orders_keeps_buy_resting_and_indeterminate_only():
    orders = to_resting_orders([
        _schwab_order(order_id="1", status="WORKING"),
        _schwab_order(order_id="2", status="PENDING_CANCEL"),
        _schwab_order(order_id="3", status="FILLED"),
        _schwab_order(order_id="4", status="CANCELED"),
        _schwab_order(order_id="5", status="WORKING", instruction="SELL"),
    ])
    assert [o.order_id for o in orders] == ["1", "2"]


def test_to_resting_orders_does_not_read_a_plain_stops_collapsed_price_as_a_limit():
    """The mapper's `price` falls back to `stopPrice` for a plain STOP order,
    so a naive `limit_price = price` would invent a limit that does not exist
    and then compare it against the zone cap."""
    (o,) = to_resting_orders([
        _schwab_order(order_type="STOP", price=18.34, stop_price=18.34)])
    assert o.stop_price == 18.34
    assert o.limit_price is None


def test_to_resting_orders_preserves_a_genuine_stop_limit_pair():
    (o,) = to_resting_orders([_schwab_order()])
    assert (o.stop_price, o.limit_price) == (18.34, 18.89)
    assert o.ticker == "FTRE"


def test_an_unmatched_order_is_not_attributed_to_an_unrelated_cleared_latch():
    """Codex executing R8. When a ticker has no LIVE latch, an unmatched resting
    order was attributed to the most recently cleared latch -- so the alarm said
    it "matches a latch that CLEARED by invalidation" (a FALSE statement about a
    real broker order) and inherited `critical` severity from a latch it has
    nothing to do with. The alarm still fires -- an unexplained resting order
    with no live mandate is worth surfacing -- but it now says only what is
    true."""
    from swing.latches.models import DailyBar
    bars = [DailyBar(session=date(2026, 7, 21), open=15.0, high=15.2,
                     low=14.1, close=14.0)]           # invalidates the latch
    cleared = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22),
        derivation_session=date(2026, 7, 21)).latches
    assert cleared[0].state == "invalidated"

    unrelated = _order(stop_price=25.00, limit_price=25.75)
    _, alarms = join_orders_to_latches(latches=cleared, orders=(unrelated,))
    (alarm,) = alarms
    assert alarm.kind == "ORDER_RESTING_LATCH_CLEARED"
    assert alarm.latch_candidate_id is None       # NOT 9500
    assert alarm.severity == "warning"            # NOT inherited `critical`
    assert "matches NO latch" in alarm.detail
    assert "invalidation" not in alarm.detail


def test_an_order_that_does_match_a_cleared_latch_still_names_it():
    """The paired discriminator: correct attribution must survive the fix, or
    the operator loses the invalidation-cancel duty this alarm exists for."""
    from swing.latches.models import DailyBar
    bars = [DailyBar(session=date(2026, 7, 21), open=15.0, high=15.2,
                     low=14.1, close=14.0)]
    cleared = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22),
        derivation_session=date(2026, 7, 21)).latches
    _, alarms = join_orders_to_latches(latches=cleared, orders=(_order(),))
    assert alarms[0].latch_candidate_id == 9500
    assert alarms[0].severity == "critical"
    assert "invalidation" in alarms[0].detail


def test_a_cleared_latchs_order_is_not_coverage_for_the_live_latch():
    """Codex executing R9. THE POST-SUPERSEDE GEOMETRY, and exactly what RD's
    gate ruling demanded the panel show loudly.

    FTRE's old latch is superseded at 18.34 with its GTC order still resting;
    the NEW latch is armed at 20.19 with nothing behind it. A ticker-level
    coverage rule sees "there is an order on FTRE" and goes SILENT -- so the
    operator is never told the LIVE mandate is naked, which is the FTRE failure
    mode this whole arc exists to eliminate. Coverage is per-LATCH: an order
    matched to a DIFFERENT, CLEARED latch is not coverage."""
    from swing.latches.models import FireRow as FR
    fires = [
        FR(candidate_id=6001, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
           initial_stop=14.88, action_session_date="2026-07-20",
           run_ts="2026-07-17T17:30:05", pipeline_run_id=135),
        FR(candidate_id=6002, evaluation_run_id=125, ticker="FTRE", pivot=20.19,
           initial_stop=16.515, action_session_date="2026-07-24",
           run_ts="2026-07-23T17:30:05", pipeline_run_id=139),
    ]
    latches = derive_latches(
        fires=fires, bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches
    assert [x.state for x in latches] == ["superseded", "armed"]

    stale = _order(stop_price=18.34, limit_price=18.89)   # the OLD mandate
    _, alarms = join_orders_to_latches(latches=latches, orders=(stale,))
    kinds = {a.kind for a in alarms}
    assert "ORDER_RESTING_LATCH_CLEARED" in kinds     # the stale order
    assert "LATCH_ARMED_NO_RESTING_ORDER" in kinds    # the NAKED new mandate
    naked = next(a for a in alarms if a.kind == "LATCH_ARMED_NO_RESTING_ORDER")
    assert naked.latch_candidate_id == 6002
    assert "20.19" in naked.detail


def test_the_join_reports_how_many_orders_matched_the_latch():
    """RD ruling 2026-07-27 (the multiplicity guard). TWO GTC stop-limits on one
    latch, same CORRECT stop trigger, DIFFERENT caps: both match on the stop leg,
    so NEITHER is unmatched, and `_pick_reference_order` reports the good one --
    the wrong-cap order then rests at the broker completely uninspected.

    The join already knows the size of the matched set (that is how it concludes
    neither order is unmatched); it must EXPOSE it so the view model can withhold
    the affirmative all-clear."""
    latches = _armed()
    good = _order(order_id="good", stop_price=18.34, limit_price=18.89)
    wrong_cap = _order(order_id="wrong-cap", stop_price=18.34, limit_price=19.75)
    joins, alarms = join_orders_to_latches(
        latches=latches, orders=(good, wrong_cap))
    j = joins[9500]
    assert j.matched_order_count == 2
    # The reference order is still the good one, and the flags still describe
    # only it -- this arc does NOT introduce per-order reporting.
    assert j.order_stop_agrees is True
    assert j.order_limit_agrees is True
    assert j.unmatched_orders == ()
    assert alarms == ()


def test_a_single_matched_order_reports_a_count_of_one():
    """The paired discriminator: the count must distinguish, or the guard would
    withhold the all-clear from every latch."""
    joins, _ = join_orders_to_latches(latches=_armed(), orders=(_order(),))
    assert joins[9500].matched_order_count == 1


def test_a_mispriced_order_still_counts_as_coverage_for_the_live_latch():
    """The paired discriminator, preserving plan A.9's intent: an order matching
    NO latch is a plausibly-mispriced attempt at the live mandate, so it must
    surface through the agreement flags -- NOT through a 'no resting order'
    alarm that would be factually false."""
    latches = _armed()
    mispriced = _order(stop_price=17.00, limit_price=17.51)
    joins, alarms = join_orders_to_latches(latches=latches, orders=(mispriced,))
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in {a.kind for a in alarms}
    assert joins[9500].order_stop_agrees is False


# --- RD ruling 2026-07-27: the mandate shape has TWO regime-selected forms ---
#
# The correct instrument depends on where price sits relative to the LATCHED
# PIVOT, so the accepted set carries two forms:
#   price BELOW the pivot  -> GTC STOP_LIMIT (stop = pivot, limit = zone cap)
#   price AT OR ABOVE it   -> GTC LIMIT at the zone cap
# This is LIVE, not hypothetical: on 2026-07-23 the operator's FTRE
# buy-stop-limit was BROKER-REJECTED because a buy stop must sit ABOVE the
# market and price had already crossed the pivot. The panel must not flag the
# situationally-correct instrument as a shape mismatch.
#
# FTRE's real values: latched pivot 18.34, zone cap 18.89, last close 19.52.
FTRE_PIVOT = 18.34
FTRE_CAP = 18.89
FTRE_CLOSE_ABOVE = 19.52       # the 2026-07-24 close, ABOVE the pivot
FTRE_CLOSE_BELOW = 17.76       # the 2026-07-17 close, BELOW the pivot


def _breakout_order(**over):
    base = dict(order_id="b1", ticker="FTRE", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", limit_price=FTRE_CAP,
                stop_price=FTRE_PIVOT, status="WORKING",
                duration="GOOD_TILL_CANCEL")
    base.update(over)
    return RestingOrder(**base)


def _pullback_order(**over):
    base = dict(order_id="p1", ticker="FTRE", instruction="BUY", quantity=3.0,
                order_type="LIMIT", limit_price=FTRE_CAP, stop_price=None,
                status="WORKING", duration="GOOD_TILL_CANCEL")
    base.update(over)
    return RestingOrder(**base)


def test_below_the_pivot_a_gtc_stop_limit_is_the_mandated_shape():
    assert mandate_shape_mismatch(
        _breakout_order(), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_BELOW) is None


def test_at_or_above_the_pivot_a_gtc_limit_at_the_cap_is_the_mandated_shape():
    """THE LIVE FTRE SUBJECT. CHARC confirmed the live order is a GTC LIMIT at
    18.89, not a stop-limit. Under the one-form set this read as a shape
    mismatch -- a false alarm on the exact channel this arc exists to make
    trustworthy."""
    assert mandate_shape_mismatch(
        _pullback_order(), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_ABOVE) is None


def test_at_the_pivot_exactly_is_the_pullback_regime():
    """The boundary is AT OR ABOVE: a buy stop AT the market is already
    unplaceable, so the cap-limit is the correct instrument."""
    assert mandate_shape_mismatch(
        _pullback_order(), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_PIVOT) is None


def test_a_non_gtc_stop_limit_below_the_pivot_is_still_a_mismatch():
    """GTC-ness is required of BOTH forms. FTRE was lost precisely because the
    order was not GTC."""
    msg = mandate_shape_mismatch(
        _breakout_order(duration="DAY"), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_BELOW)
    assert msg is not None
    assert "GOOD_TILL_CANCEL" in msg


def test_a_non_gtc_limit_above_the_pivot_is_still_a_mismatch():
    """The other half of the GTC requirement -- and the discriminator that
    proves the widening did not swallow the duration check: under the one-form
    set this reported the TYPE, never the duration."""
    msg = mandate_shape_mismatch(
        _pullback_order(duration="DAY"), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_ABOVE)
    assert msg is not None
    assert "GOOD_TILL_CANCEL" in msg


def test_a_stop_limit_above_the_pivot_is_the_wrong_regime():
    """The FTRE 2026-07-23 broker rejection, caught by the panel: a buy stop
    below the market cannot rest."""
    msg = mandate_shape_mismatch(
        _breakout_order(), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_ABOVE)
    assert msg is not None
    assert "STOP_LIMIT" in msg and "LIMIT" in msg
    assert "AT OR ABOVE" in msg


def test_a_plain_limit_below_the_pivot_is_the_wrong_regime():
    """A resting buy-limit at the cap while price is below the pivot fills
    IMMEDIATELY at the market -- it never waits for the breakout."""
    msg = mandate_shape_mismatch(
        _pullback_order(), latched_pivot=FTRE_PIVOT,
        last_close=FTRE_CLOSE_BELOW)
    assert msg is not None
    assert "STOP_LIMIT" in msg
    assert "BELOW" in msg


def test_an_absent_price_degrades_to_accepting_either_form():
    """Degrade gracefully: with no price the regime is UNDETERMINABLE, so the
    check must not assert a mismatch it cannot support."""
    for order in (_breakout_order(), _pullback_order()):
        assert mandate_shape_mismatch(
            order, latched_pivot=FTRE_PIVOT, last_close=None) is None
        assert mandate_shape_mismatch(order) is None


def test_an_unusable_price_degrades_to_accepting_either_form():
    for bad in (float("nan"), float("inf"), "n/a"):
        assert mandate_shape_mismatch(
            _pullback_order(), latched_pivot=FTRE_PIVOT, last_close=bad) is None


def test_a_trailing_stop_is_neither_form_in_either_regime():
    for close in (FTRE_CLOSE_BELOW, FTRE_CLOSE_ABOVE, None):
        msg = mandate_shape_mismatch(
            _breakout_order(order_type="TRAILING_STOP_LIMIT"),
            latched_pivot=FTRE_PIVOT, last_close=close)
        assert msg is not None, close
        assert "TRAILING_STOP_LIMIT" in msg


def test_expected_mandate_order_type_selects_by_regime():
    assert expected_mandate_order_type(
        latched_pivot=FTRE_PIVOT, last_close=FTRE_CLOSE_BELOW) == "STOP_LIMIT"
    assert expected_mandate_order_type(
        latched_pivot=FTRE_PIVOT, last_close=FTRE_CLOSE_ABOVE) == "LIMIT"
    assert expected_mandate_order_type(
        latched_pivot=FTRE_PIVOT, last_close=None) is None
    assert expected_mandate_order_type(
        latched_pivot=None, last_close=FTRE_CLOSE_ABOVE) is None


def test_the_regime_boundary_uses_display_precision():
    """The price-precision-parity gotcha on BOTH sides: a sub-cent float
    artifact must not flip the regime and invert the mandated instrument."""
    assert expected_mandate_order_type(
        latched_pivot=FTRE_PIVOT, last_close=18.339999) == "LIMIT"


def test_close_EXACTLY_AT_the_pivot_is_the_PULLBACK_regime():
    """GUARD -- the boundary's CURRENT disposition, pinned EXACTLY.

    `expected_mandate_order_type` compares `round(close, PRICE_DP) <
    round(pivot, PRICE_DP)`, strict, so `close == pivot` yields PULLBACK: at
    the pivot a buy STOP would sit at the market, and the mandate is a resting
    LIMIT at the zone cap.

    THE EXISTING `18.339999` CASE IS NOT A SUBSTITUTE. That is a NEAR-equality
    and it passes under `<` and under `<=` alike, so it cannot see this
    boundary move. This test fails if the boundary moves in EITHER direction:
    a flip to `<=` makes the equality BREAKOUT, and a flip to `>` or an
    inverted return makes the `P - 0.01` neighbour PULLBACK.

    `18.345` is here because its cent-rounding is non-trivial (it rounds DOWN
    to 18.34), which is exactly the shape a rounding change would disturb.
    """
    for pivot in (FTRE_PIVOT, 36.27, 18.345):
        assert expected_mandate_order_type(
            latched_pivot=pivot, last_close=pivot) == MANDATE_ORDER_TYPE_PULLBACK, pivot
        assert expected_mandate_order_type(
            latched_pivot=pivot,
            last_close=pivot - 0.01) == MANDATE_ORDER_TYPE_BREAKOUT, pivot
        assert expected_mandate_order_type(
            latched_pivot=pivot,
            last_close=pivot + 0.01) == MANDATE_ORDER_TYPE_PULLBACK, pivot


def test_both_forms_are_in_the_mandate_set_and_gtc_is_still_the_only_duration():
    assert MANDATE_ORDER_TYPES == {"STOP_LIMIT", "LIMIT"}
    assert MANDATE_ORDER_DURATIONS == {"GOOD_TILL_CANCEL"}
