"""The prepared order + the per-field delta - PURE (Arc 21-B Task 2).

Built from the REAL FTRE geometry, verified on the live DB 2026-07-28:
`candidates.id=11261`, evaluation run 121, action session 2026-07-20,
pivot 18.34, initial_stop 14.88, zone cap = pivot x 1.03 = 18.8902,
sizing equity 7500 (the floor binds; real equity ~1.2k),
`max_risk_pct` 0.005 -> $37.50, `position_pct_cap` 0.15.
"""
from __future__ import annotations

import math as _math
from datetime import date

import pytest

from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch
from swing.latches.order_intent import (
    OrderDelta,
    PreparedOrderResult,
    SizingInputs,
    canonical_duration,
    compute_order_delta,
    compute_prepared_order,
    derivation_column_values,
    quantize_limit_down,
    recompute_derived_display_values,
)

FTRE_PIVOT = 18.34
FTRE_STOP = 14.88
FTRE_ZONE_CAP = round(FTRE_PIVOT * 1.03, 4)      # 18.8902
FTRE_LIMIT = 18.89                                # cent-quantized DOWN


def _ftre_latch(**over) -> Latch:
    kw = dict(
        identity=LatchIdentity(
            candidate_id=11261, evaluation_run_id=121, ticker="FTRE",
            detection_date="2026-07-20", pipeline_run_id=None),
        latched_pivot=FTRE_PIVOT, latched_initial_stop=FTRE_STOP,
        zone_cap=FTRE_ZONE_CAP, anchor=date(2026, 7, 20),
        horizon_expiry=date(2026, 8, 31), sessions_elapsed=6,
        sessions_to_horizon=24, state="armed",
    )
    kw.update(over)
    return Latch(**kw)


def _sizing(**over) -> SizingInputs:
    kw = dict(real_equity=1234.56, equity_floor=7500.0, sizing_equity=7500.0,
              max_risk_pct=0.005, position_pct_cap=0.15, risk_policy_id=5,
              nightly_recommendation_shares=10)
    kw.update(over)
    return SizingInputs(**kw)


def _prepared(**over):
    return compute_prepared_order(
        latch=_ftre_latch(), regime_order_type=over.pop("regime", "LIMIT"),
        regime_close=over.pop("close", 19.20),
        regime_close_session=over.pop("close_session", "2026-07-29"),
        sizing_inputs=over.pop("sizing", _sizing()))


# --------------------------------------------------------------------------
# The limit price -- WHOLE CENTS, by FLOOR
# --------------------------------------------------------------------------
def test_the_limit_is_the_zone_cap_quantized_DOWN_to_whole_cents():
    """ONE value, used in PreparedOrder.limit_price, the card, the hidden
    anchor, the anchor digest, the stored framework_limit_price,
    compute_shares's entry, compute_order_delta and every fixture."""
    assert quantize_limit_down(FTRE_ZONE_CAP) == FTRE_LIMIT
    res = _prepared()
    assert res.order.limit_price == FTRE_LIMIT


def test_a_cap_whose_third_decimal_rounds_UP_still_quantizes_DOWN():
    """THE ROUND-HALF-UP DISCRIMINATOR. **NOT DROPPABLE AS REDUNDANT** -- it is
    HALF of a pair and the other half CANNOT catch what it catches.

    FTRE alone cannot discriminate here (its cap 18.8902 rounds down either
    way), which is the vacuous-acceptance-test trap. The zone cap is a MAXIMUM,
    so a quantization that can move the price UP can push the order ABOVE the
    zone. A round-half-up implementation returns 18.90 and FAILS this test; a
    NAIVE binary floor PASSES it, which is precisely why its sibling below
    (`..._not_undercut_by_binary_representation`) exists and why neither may be
    deleted as covering the other.
    """
    assert quantize_limit_down(18.8952) == 18.89
    assert round(18.8952, 2) == 18.90, (
        "the premise, asserted inline so it cannot rot: round-half-up DOES move "
        "this cap up, which is why FLOOR is required rather than preferred")
    assert _math.floor(18.8952 * 100) / 100 == 18.89, (
        "and the OTHER premise: a naive binary floor passes this case, so this "
        "test alone does not pin the quantizer -- its sibling does")
    res = compute_prepared_order(
        latch=_ftre_latch(zone_cap=18.8952), regime_order_type="LIMIT",
        regime_close=19.20, regime_close_session="2026-07-29",
        sizing_inputs=_sizing())
    assert res.order.limit_price == 18.89


def test_a_whole_dollar_pivot_cap_is_not_undercut_by_binary_representation():
    """THE REPRESENTATION DISCRIMINATOR (RD ruling, 2026-07-30). **NOT
    DROPPABLE AS REDUNDANT** -- the sibling above passes under the defect this
    one catches.

    RULED SEMANTIC: the limit is the largest whole-cent price that does not
    exceed the cap, evaluated against the cap's DECIMAL value rather than its
    BINARY representation.

    THE ARITHMETIC, UNDER BOTH PATHS, so the test provably distinguishes:
      pivot 141.00 -> zone_cap = round(141.00 * 1.03, 4) = 145.23 exactly
      PRE-FIX  `math.floor(145.23 * 100) / 100`:
               145.23 * 100 == 14522.999999999998 -> floor 14522 -> **145.22**
      POST-FIX `Decimal('145.23').quantize('0.01', ROUND_FLOOR)` -> **145.23**
    A round-half-up implementation ALSO returns 145.23, so this case cannot
    catch the rounding defect -- that is the sibling's job.

    RARITY IS NOT THE POINT AND THE HARM IS NOT THE PRICE. A limit one cent
    below the cap is still in zone. The harm is that the FRAMEWORK FLAGS ITS OWN
    OUTPUT AS A MISMATCH -- see
    `test_the_framework_never_flags_its_own_prepared_limit_as_a_mismatch`, a
    false alarm we generate on this arc's primary alarm channel. Incidence
    through the PRODUCTION path (`zone_cap = round(pivot * 1.03, 4)`): 43 of the
    100,000 two-decimal pivots from $0.01 to $1000.00, incl. 35.00, 141.00 and
    257.00.
    """
    cap = round(141.00 * 1.03, 4)
    assert cap == 145.23
    assert _math.floor(cap * 100) / 100 == 145.22, (
        "the pre-fix premise, asserted inline so it cannot rot: the naive "
        "binary floor DOES undercut this cap by a cent")
    assert quantize_limit_down(cap) == 145.23
    res = compute_prepared_order(
        latch=_ftre_latch(latched_pivot=141.00, latched_initial_stop=120.00,
                          zone_cap=cap),
        regime_order_type="LIMIT", regime_close=150.00,
        regime_close_session="2026-07-29", sizing_inputs=_sizing())
    assert res.order.limit_price == 145.23


def test_the_framework_never_flags_its_own_prepared_limit_as_a_mismatch():
    """THE HARM THE FLOOR FIX ACTUALLY PREVENTS, pinned END TO END.

    A resting order carrying EXACTLY the limit the framework prepared must
    ATTRIBUTE to that latch and AGREE with it under 21-A's own comparison. Under
    the pre-fix quantizer the prepared limit is 145.22 against a 145.23 cap, so
    `_match_latch` finds no hit at all: the operator's order becomes a STRAY, the
    mandate reads as NAKED, and the panel raises a mismatch the framework itself
    manufactured. That is drumbeat erosion on the one channel whose alarms have
    to survive being believed.

    Both sides of the comparison are at cent precision, which is what keeps the
    representation defect from simply recurring at the comparison instead of at
    the emission.
    """
    from swing.latches.models import RestingOrder
    from swing.latches.orders import join_orders_to_latches

    cap = round(141.00 * 1.03, 4)
    latch = _ftre_latch(latched_pivot=141.00, latched_initial_stop=120.00,
                        zone_cap=cap)
    prepared = compute_prepared_order(
        latch=latch, regime_order_type="LIMIT", regime_close=150.00,
        regime_close_session="2026-07-29", sizing_inputs=_sizing()).order
    order = RestingOrder(
        order_id="9001", ticker="FTRE", instruction="BUY", quantity=9.0,
        order_type="LIMIT", limit_price=prepared.limit_price, stop_price=None,
        status="WORKING", duration="GOOD_TILL_CANCEL")
    joins, alarms = join_orders_to_latches(latches=[latch], orders=[order])
    join = joins[latch.identity.candidate_id]
    assert join.orders and join.unmatched_orders == (), (
        "the framework's OWN prepared order must attribute to the latch it was "
        "prepared for -- a stray here is a false alarm we generated")
    assert join.order_limit_agrees is True
    assert [a.kind for a in alarms] == []


# --------------------------------------------------------------------------
# The two regimes
# --------------------------------------------------------------------------
def test_the_pullback_regime_yields_a_resting_LIMIT_with_no_stop_leg():
    res = _prepared(regime="LIMIT")
    assert res.withheld_reason is None
    o = res.order
    assert o.order_type == "LIMIT"
    assert o.stop_price is None, (
        "a buy stop below the market is the FTRE rejection")
    assert o.duration == "GOOD_TILL_CANCEL"
    assert o.limit_price == FTRE_LIMIT
    assert o.quantity == 9


def test_the_breakout_regime_yields_a_STOP_LIMIT_triggered_at_the_frozen_pivot():
    res = _prepared(regime="STOP_LIMIT", close=17.50)
    o = res.order
    assert o.order_type == "STOP_LIMIT"
    assert o.stop_price == FTRE_PIVOT
    assert o.limit_price == FTRE_LIMIT
    assert o.quantity == 9, "the sizing basis is the LIMIT in BOTH regimes"


def test_the_quantity_is_sized_off_the_LIMIT_and_computes_NINE():
    """THE RD-RULED SIZING BASIS, and the discriminator for it.

    A PIVOT-basis implementation returns 10 and FAILS. Verified arithmetic under
    both paths:
      pivot 18.34   -> risk/share 3.46 -> floor(37.50/3.46) = 10 shares,
                       whose risk at an ORDINARY CAP FILL is
                       10 x (18.89 - 14.88) = $40.10 = 0.535% -- OVER the 0.5%
                       policy cap, and in the pullback regime the cap is
                       PRECISELY WHERE THE ORDER FILLS.
      limit 18.89   -> risk/share 4.01 -> floor(37.50/4.01) =  9 shares,
                       whose risk is 9 x 4.01 = $36.09 = 0.481% -- inside the
                       cap in every fill outcome.
    """
    import math
    pivot_basis_shares = math.floor(37.50 / (FTRE_PIVOT - FTRE_STOP))
    limit_basis_shares = math.floor(37.50 / (FTRE_LIMIT - FTRE_STOP))
    assert pivot_basis_shares == 10 and limit_basis_shares == 9, (
        "the two paths must actually differ or this test cannot discriminate")
    res = _prepared()
    assert res.order.quantity == 9
    d = res.order.derivation
    assert d.sizing_basis == "limit_price"
    assert d.sizing_basis_price == FTRE_LIMIT
    assert round(d.risk_per_share, 2) == 4.01
    assert round(d.max_risk_dollars, 2) == 37.50
    assert d.shares_by_risk == 9
    assert d.binding_constraint == "risk"
    # ...and the risk at the worst fill this order can get is inside the cap.
    assert round(9 * d.risk_per_share / d.sizing_equity, 5) <= 0.005


def test_the_position_cap_leg_is_recorded_even_when_risk_binds():
    res = _prepared()
    d = res.order.derivation
    assert d.shares_by_position_cap == 59      # floor(1125.00 / 18.89)
    assert d.binding_constraint == "risk"


def test_the_one_share_divergence_from_the_nightly_is_SURFACED(
):
    """A DOCUMENTED LEDGER SEMANTIC, not an unresolved defect. The nightly sizes
    off the PIVOT (10 sh) and the mandate off the LIMIT (9 sh); only the latter
    is inside the risk policy at the fill the order can actually get. The card
    renders the divergence so the operator sees WHY two surfaces disagree rather
    than discovering it at the broker."""
    res = _prepared()
    d = res.order.derivation
    assert d.nightly_recommendation_shares == 10
    assert res.order.quantity == 9


# --------------------------------------------------------------------------
# The WITHHELD branch -- the CURRENT live state, so it is the expressive one
# --------------------------------------------------------------------------
def test_an_undeterminable_regime_WITHHOLDS_the_form_with_a_reason():
    """A form that GUESSED the type would write the WRONG TYPE into the parity
    ledger. From a stale close you may raise a mismatch alarm, but you may not
    assert a match -- and a prepared order IS an assertion."""
    res = compute_prepared_order(
        latch=_ftre_latch(), regime_order_type=None, regime_close=None,
        regime_close_session=None, sizing_inputs=_sizing())
    assert res.order is None
    assert res.withheld_reason == "regime_undeterminable"
    assert res.withheld_detail.strip()


def test_infeasible_sizing_WITHHOLDS_the_form():
    res = _prepared(sizing=_sizing(sizing_equity=1.0, real_equity=1.0,
                                   equity_floor=0.0))
    assert res.order is None
    assert res.withheld_reason == "sizing_infeasible"
    assert res.withheld_detail.strip()


def test_a_degenerate_sizing_geometry_WITHHOLDS_rather_than_raising(monkeypatch):
    """`Latch.__post_init__` already guarantees stop < pivot < cap so this cannot
    fire in production -- but the call is guarded anyway and a raise degrades
    VISIBLY rather than 500ing the panel (A6)."""
    from swing.latches import order_intent as mod

    def _boom(**kw):
        raise ValueError("stop must be < entry")

    monkeypatch.setattr(mod, "compute_shares", _boom)
    res = _prepared()
    assert res.order is None
    assert res.withheld_reason == "sizing_degenerate"
    assert res.withheld_detail.strip()


def test_the_result_type_is_LOSSLESS_and_rejects_both_none_and_both_set():
    """A bare `PreparedOrder | None` return cannot carry the withheld reason the
    panel is REQUIRED to render."""
    with pytest.raises(ValueError, match="EXACTLY ONE"):
        PreparedOrderResult(order=None, withheld_reason=None, withheld_detail="")
    with pytest.raises(ValueError, match="EXACTLY ONE"):
        PreparedOrderResult(
            order=_prepared().order, withheld_reason="sizing_infeasible",
            withheld_detail="x")


def test_a_withheld_result_MUST_label_its_reduction():
    """An UNLABELLED reduction is a quiet all-clear by omission, which is the
    failure mode -- not the under-claim itself."""
    with pytest.raises(ValueError, match="display-ready detail"):
        PreparedOrderResult(
            order=None, withheld_reason="sizing_infeasible", withheld_detail="  ")


def test_an_unknown_withheld_reason_is_rejected():
    with pytest.raises(ValueError, match="withheld_reason must be in"):
        PreparedOrderResult(
            order=None, withheld_reason="because", withheld_detail="x")


# --------------------------------------------------------------------------
# The 21-A regime SEAM is consumed, never re-implemented
# --------------------------------------------------------------------------
def test_order_intent_contains_no_independent_pivot_vs_close_comparison():
    """`swing/latches/orders.py:expected_mandate_order_type` is the ONLY source
    of the mandate form in this arc, so whatever 21-G does to make the close
    sound flows through automatically. A module that re-derived the regime would
    silently keep the pre-21-G behaviour."""
    from pathlib import Path
    src = Path("swing/latches/order_intent.py").read_text(encoding="utf-8")
    body = "\n".join(
        ln for ln in src.splitlines() if not ln.strip().startswith("#"))
    for forbidden in ("last_close", "regime_close <", "regime_close >",
                      "< latched_pivot", "> latched_pivot"):
        assert forbidden not in body, (
            f"{forbidden!r} suggests a re-implemented regime comparison")
    # ...and the regime arrives as a PARAMETER.
    import inspect
    sig = inspect.signature(compute_prepared_order)
    assert "regime_order_type" in sig.parameters


# --------------------------------------------------------------------------
# The section A.4 RECOMPUTE half -- the five DERIVED values are legitimately
# derived, not merely omitted from storage
# --------------------------------------------------------------------------
def test_the_five_derived_values_recompute_EXACTLY_from_a_stored_row():
    """The test that proves they are legitimately DERIVED rather than omitted.

    If any one could NOT be recomputed from the stored columns plus the
    candidate_id-pinned prices, it would belong in the STORED set, and the
    section A.4 rule says so.
    """
    res = _prepared()
    d = res.order.derivation
    stored = derivation_column_values(d)
    stored["framework_limit_price"] = res.order.limit_price
    stored["latched_initial_stop"] = d.latched_initial_stop
    got = recompute_derived_display_values(stored)
    assert got["risk_per_share"] == d.risk_per_share
    assert got["max_risk_dollars"] == d.max_risk_dollars
    assert got["shares_by_risk"] == d.shares_by_risk
    assert got["shares_by_position_cap"] == d.shares_by_position_cap
    assert got["binding_constraint"] == d.binding_constraint


def test_derivation_column_values_covers_every_manifest_row():
    from swing.latches.constants import DERIVATION_FIELD_MANIFEST
    vals = derivation_column_values(_prepared().order.derivation)
    assert set(vals) == {f.column for f in DERIVATION_FIELD_MANIFEST}
    # every non-exempt column is POPULATED on an offered order
    from swing.latches.constants import DERIVATION_NULLABLE_ON_DECISION
    for col, val in vals.items():
        if col in DERIVATION_NULLABLE_ON_DECISION:
            continue
        assert val is not None, col


# --------------------------------------------------------------------------
# The delta
# --------------------------------------------------------------------------
_FW_PULLBACK = {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL",
                "stop_price": None, "limit_price": 18.89, "quantity": 9}


def test_an_exact_match_reports_no_difference_anywhere():
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK))
    assert d.order_type_differs is False
    assert d.duration_differs is False
    assert d.limit_price_delta == 0.0
    assert d.quantity_delta == 0
    assert d.stop_leg == "both_absent"
    assert d.any_difference is False
    assert d.unknown_fields == ()


def test_the_FTRE_divergence_is_a_clean_single_field_quantity_delta():
    """THE ARC'S WORKED EXAMPLE, against the real geometry: framework
    LIMIT 18.89 / GTC / 9 vs the operator's actual resting GTC LIMIT 18.89 / 10.
    """
    actual = dict(_FW_PULLBACK, quantity=10)
    d = compute_order_delta(_FW_PULLBACK, actual)
    assert d.quantity_delta == 1
    assert d.order_type_differs is False
    assert d.duration_differs is False
    assert d.limit_price_delta == 0.0
    assert d.stop_leg == "both_absent"
    assert d.any_difference is True


def test_a_missing_actual_side_is_UNKNOWN_never_False():
    """Unknown is NEVER agreement."""
    d = compute_order_delta(_FW_PULLBACK, None)
    assert d.any_difference is None
    assert d.order_type_differs is None
    assert d.quantity_delta is None
    assert d.stop_leg == "unknown"
    assert set(d.unknown_fields) == {
        "order_type", "duration", "limit_price", "quantity", "stop_price"}


def test_prices_compare_at_DISPLAY_precision():
    """At execution grain a sub-cent artifact would falsely flip an identical
    order to 'operator edited'."""
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK, limit_price=18.885))
    assert d.limit_price_delta == 0.0
    assert d.any_difference is False


def test_GTC_and_GOOD_TILL_CANCEL_compare_EQUAL():
    """Comparing RAW strings reports a duration divergence on a SEMANTICALLY
    IDENTICAL order -- a manufactured mismatch in the exact metric the ledger
    exists to compute. A raw-string implementation FAILS."""
    assert canonical_duration("GTC") == canonical_duration("GOOD_TILL_CANCEL")
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK, duration="GTC"))
    assert d.duration_differs is False
    assert d.any_difference is False


def test_an_unmapped_duration_canonicalises_to_UNKNOWN_and_compares_as_UNKNOWN():
    assert canonical_duration("WHENEVER") == "UNKNOWN"
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK, duration="WHENEVER"))
    assert d.duration_differs is None
    assert d.any_difference is None
    assert "duration" in d.unknown_fields


def test_a_real_duration_divergence_IS_reported():
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK, duration="DAY"))
    assert d.duration_differs is True
    assert d.any_difference is True


def test_the_stop_leg_both_absent_cell_is_a_MATCH_not_an_unknown():
    """THE PULLBACK REGIME'S RIGHT ANSWER. With a bare `float | None` this
    collapses into `unknown`, and unknown is never agreement, so the CORRECT
    order would score as a NON-MATCH. A bare-float implementation FAILS."""
    d = compute_order_delta(_FW_PULLBACK, dict(_FW_PULLBACK))
    assert d.stop_leg == "both_absent"
    assert d.stop_price_delta is None
    assert d.any_difference is False
    assert "stop_price" not in d.unknown_fields


def test_the_stop_leg_compared_cell_carries_the_signed_delta():
    fw = {"order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
          "stop_price": 18.34, "limit_price": 18.89, "quantity": 9}
    d = compute_order_delta(fw, dict(fw, stop_price=18.40))
    assert d.stop_leg == "compared"
    assert d.stop_price_delta == 0.06
    assert d.any_difference is True


def test_the_stop_leg_unknown_cell_fires_when_exactly_one_side_has_a_stop():
    fw = {"order_type": "STOP_LIMIT", "duration": "GOOD_TILL_CANCEL",
          "stop_price": 18.34, "limit_price": 18.89, "quantity": 9}
    d = compute_order_delta(fw, dict(fw, stop_price=None))
    assert d.stop_leg == "unknown"
    assert d.stop_price_delta is None
    assert d.any_difference is None


def test_the_delta_type_pins_stop_price_delta_IFF_compared():
    with pytest.raises(ValueError, match="IFF"):
        OrderDelta(order_type_differs=False, duration_differs=False,
                   stop_leg="both_absent", stop_price_delta=0.0,
                   limit_price_delta=0.0, quantity_delta=0,
                   any_difference=False, unknown_fields=())
    with pytest.raises(ValueError, match="IFF"):
        OrderDelta(order_type_differs=False, duration_differs=False,
                   stop_leg="compared", stop_price_delta=None,
                   limit_price_delta=0.0, quantity_delta=0,
                   any_difference=False, unknown_fields=())


def test_an_unknown_stop_leg_state_is_rejected():
    with pytest.raises(ValueError, match="stop_leg must be in"):
        OrderDelta(order_type_differs=False, duration_differs=False,
                   stop_leg="maybe", stop_price_delta=None,
                   limit_price_delta=0.0, quantity_delta=0,
                   any_difference=False, unknown_fields=())


# --- the anchor encoding must survive the browser round trip (Task 6) -----
@pytest.mark.parametrize("encoding,raw,expected", [
    ("price2", 18.8902, "18.89"),
    ("price2", None, ""),
    ("pct6", 0.005, "0.005000"),
    ("int", 9, "9"),
    ("int", None, ""),
    ("session", "2026-07-24", "2026-07-24"),
    ("text", "limit_price", "limit_price"),
])
def test_the_anchor_encoding_is_idempotent(encoding, raw, expected):
    """LOAD-BEARING, not tidy. The RENDER encodes raw derivation values into
    hidden inputs; the browser posts those STRINGS back; the handler must
    recompute the SAME digest from what it received. If re-encoding an
    already-encoded value did not reproduce it, the two sides could not agree --
    and the EMPTY STRING in particular would RAISE (`float("")`), so a pullback
    mandate, whose framework stop leg is legitimately absent, could not be
    anchored at all."""
    from swing.latches.order_intent import encode_derivation_value
    once = encode_derivation_value(encoding, raw)
    assert once == expected
    assert encode_derivation_value(encoding, once) == once


def test_the_empty_string_encodes_as_NULL_and_not_as_a_zero():
    """The empty string IS the NULL encoding, deliberately distinct from "0",
    which a float field could legitimately produce. Collapsing the two would
    make "no stop leg" and "a stop at zero" share a digest."""
    from swing.latches.order_intent import encode_derivation_value
    assert encode_derivation_value("price2", "") == ""
    assert encode_derivation_value("price2", 0) == "0.00"


def test_the_rate_encoding_is_FINER_than_the_card_renders_the_same_rate():
    """AUTO-REVIEW CRITICAL 3 -- the price-precision-parity gotcha arriving at a
    PERCENTAGE field, and it arrives the wrong way round.

    The rule that family states is that the ANCHOR and the DISPLAY must agree.
    The card renders a policy rate as `{rate * 100:.3f}%` -- THREE decimals of
    percent, i.e. FIVE decimals of fraction -- while the anchor encoded FOUR
    decimals of fraction. The anchor was therefore COARSER than the display, so
    two configs the operator can plainly see apart shared one hidden anchor:

      0.00504 renders 0.504%   and encoded pct4 -> '0.0050'
      0.00505 renders 0.505%   and encoded pct4 -> '0.0050'

    Consequences, both real: the POST-time comparison cannot detect a changed
    VISIBLE derivation (the hidden-anchor defence has a hole exactly the width of
    the display's extra digit), and `_stored_anchor_values` decodes the SUBMITTED
    text, so the ledger persists 0.0050 as the provenance of a card that said
    0.504% -- a stored derivation that is not the one he was shown, on the ledger
    whose entire claim is that those two are identical.

    The fix is directional: the anchor must be at least as fine as the display,
    never the reverse. Six decimals of fraction is four decimals of percent, one
    digit finer than the card renders.
    """
    from swing.latches.order_intent import encode_derivation_value
    assert encode_derivation_value("pct6", 0.00504) != (
        encode_derivation_value("pct6", 0.00505))
    assert f"{0.00504 * 100:.3f}" != f"{0.00505 * 100:.3f}", (
        "the premise, inline so it cannot rot: the CARD does distinguish them")
    assert encode_derivation_value("pct6", 0.005) == "0.005000"
    assert encode_derivation_value("pct6", None) == ""
    assert encode_derivation_value(
        "pct6", encode_derivation_value("pct6", 0.00504)) == "0.005040", (
        "idempotent across the browser round trip, like every other encoding")


def test_the_manifest_carries_NO_encoding_coarser_than_its_rendered_display():
    """The CLASS, pinned rather than the instance: every manifest field the card
    RENDERS must anchor at least as finely as the card shows it. Stated as an
    executable check over the manifest so a field added later cannot quietly
    reintroduce the hole."""
    from swing.latches.constants import DERIVATION_FIELD_MANIFEST
    assert {f.encode for f in DERIVATION_FIELD_MANIFEST} <= {
        "price2", "pct6", "int", "session", "text"}
    assert "pct4" not in {f.encode for f in DERIVATION_FIELD_MANIFEST}, (
        "pct4 is four decimals of FRACTION against a display of three decimals "
        "of PERCENT -- coarser than what the operator can see")
