"""The two alarms (plan A.9)."""
from __future__ import annotations

from datetime import date

from swing.latches.models import DailyBar, FireRow, RestingOrder
from swing.latches.orders import join_orders_to_latches, to_resting_orders
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
