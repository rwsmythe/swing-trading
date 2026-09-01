"""22-A task 1 -- the FIVE envelope guards, as PURE functions.

Cases 15a-15e, 15d-i, 15d-ii and 30a-30d.  Every fixture is a hand-built
``AcceptedLatchOrder``: the guards take no connection, which is what makes
them testable without a database and keeps all five in one place.

FREE-DIMENSION DECLARATION (plan S3.8).  These cases PIN: ``fill_origin``,
the ticker, the quantity relation (1 vs 2; 3 vs 2), and the price relative to
BOTH bounds.  They deliberately leave FREE: the freeze tier (no case here
reaches rung 9 -- see the twin-roster repair in ``case_registry_22a``), the
fill session, and the link/intent ids, none of which any guard reads.
"""
from __future__ import annotations

import logging

import pytest

from swing.latches.constants import (
    PRICE_DP,
    mandate_limit_price,
    zone_cap_for_pivot,
)
from swing.trades.latched_origin import (
    AcceptedLatchOrder,
    assert_fill_consistent_with_order,
    broker_order_id_from_envelope,
    instrument_symbol_from_envelope,
)

# THE 17.407 GEOMETRY, from the live VSTS cap the mandate-limit ruling was made
# on.  pivot 16.90 -> cap 16.9 * 1.03 = 17.407, whose THIRD decimal is non-zero.
#   mandate_limit_price(17.407) = 17.40   (FLOOR -- the orderable price)
#   round(17.407, 2)            = 17.41   (the forbidden second rounding)
# 17.41 EXCEEDS the cap, so an implementation using ``round`` blesses a price
# OUTSIDE the buy zone.  That gap of one cent is the whole of case 30a.
THIRD_DECIMAL_PIVOT = 16.90
FLOORED_CENT = 17.40
ROUND_UP_CENT = 17.41


def _order(**overrides) -> AcceptedLatchOrder:
    base = dict(
        link_id=1,
        validity_intent_id=2,
        place_intent_id=1,
        candidate_id=12284,
        evaluation_run_id=136,
        ticker="OII",
        detection_date="2026-08-07",
        broker_order_id="1007523377009",
        frozen_pivot=53.97999954223633,
        frozen_invalidation=41.41999816894531,
        actual_quantity=2,
        freeze_tier="live_at_acceptance",
        actual_limit_price=55.59,
    )
    base.update(overrides)
    return AcceptedLatchOrder(**base)


def _judge(order: AcceptedLatchOrder, **overrides) -> str | None:
    kwargs = dict(
        ticker=order.ticker,
        price=53.98,
        shares=2,
        fill_origin="schwab_auto",
        envelope_symbol=order.ticker,
    )
    kwargs.update(overrides)
    return assert_fill_consistent_with_order(order, **kwargs)


# ---------------------------------------------------------------------------
# The 17.407 geometry is a PREMISE of cases 30a-30c, so it is CHECKED here
# rather than trusted.  If the shared helpers ever agree, 30a stops
# discriminating and this fails first, naming why.
# ---------------------------------------------------------------------------
def test_the_third_decimal_geometry_still_separates_floor_from_round() -> None:
    cap = zone_cap_for_pivot(THIRD_DECIMAL_PIVOT)
    assert round(cap, 4) == 17.407
    assert mandate_limit_price(cap) == FLOORED_CENT
    assert round(cap, PRICE_DP) == ROUND_UP_CENT
    assert ROUND_UP_CENT > cap, (
        "the round-up cent must EXCEED the cap, or case 30a is not a case"
    )


# ---------------------------------------------------------------------------
# 15a-15e
# ---------------------------------------------------------------------------
def test_untrusted_fill_origin_refuses_case_15a() -> None:
    """PRE-FIX (guard absent): None -> the order authorizes an operator-typed
    fill on nothing but a typed-in id.  POST-FIX: ``untrusted_fill_origin``."""
    assert _judge(_order(), fill_origin="operator_typed") == "untrusted_fill_origin"
    for trusted in ("schwab_auto", "schwab_auto_then_operator_corrected"):
        assert _judge(_order(), fill_origin=trusted) is None


def test_out_of_zone_price_refuses_case_15b() -> None:
    """A fill BELOW the frozen pivot did not come through this buy-stop."""
    assert _judge(_order(), price=52.00) == "fill_outside_frozen_zone"
    assert _judge(_order(), price=53.98) is None


def test_ticker_mismatch_refuses_case_15c() -> None:
    assert _judge(_order(), ticker="AMN") == "ticker_mismatch"


def test_envelope_symbol_mismatch_refuses_case_15c_second_shape() -> None:
    """The ENVELOPE's symbol is a separate input from the request's ticker.

    A guard checking only ``req.ticker`` passes this while the envelope names
    a different instrument entirely.
    """
    assert _judge(_order(), envelope_symbol="AMN") == "ticker_mismatch"


def test_partial_fill_admits_case_15d_i() -> None:
    """shares=1 against actual_quantity=2 -> ADMIT.

    An accepted validity row records the ORDER quantity; the fill records the
    EXECUTED quantity.  A partial-then-cancelled order gives shares=1 against
    actual_quantity=2 -- a genuine order and a genuine fill.  **An EQUALITY
    implementation fails this case**, and would mint the empty-cohort-key row
    the arc exists to stop.
    """
    assert _judge(_order(), shares=1) is None


def test_over_quantity_refuses_case_15d_ii() -> None:
    assert _judge(_order(), shares=3) == "quantity_exceeds_order"
    assert _judge(_order(), shares=0) == "quantity_exceeds_order"


ABSENT_ENVELOPE_SHAPES = [
    None,
    "",
    "   ",
    "not json at all",
    "[1, 2, 3]",
    '"a bare string"',
    "{}",
    '{"schwab_order_id": null}',
    '{"schwab_order_id": 1007523377009}',
    '{"schwab_order_id": ""}',
    '{"schwab_order_id": "   "}',
]


@pytest.mark.parametrize("raw", ABSENT_ENVELOPE_SHAPES)
def test_malformed_or_absent_envelope_yields_no_order_id_case_15e(raw) -> None:
    """Case 15e -- every unusable envelope shape degrades to ``None``, never raises.

    PRE-FIX a naive ``json.loads(raw)["schwab_order_id"]`` raises on eight of
    these eleven shapes, and a raising read-only consumer takes down a
    money-bearing entry over cohort bookkeeping.
    """
    assert broker_order_id_from_envelope(raw) is None


def test_well_formed_envelope_yields_the_order_id_case_15e_positive() -> None:
    raw = (
        '{"entry_date": "2026-08-17", "entry_price": 53.98, '
        '"schwab_instrument_symbol": "OII", '
        '"schwab_order_id": "1007523377009", "shares": 2}'
    )
    assert broker_order_id_from_envelope(raw) == "1007523377009"
    assert instrument_symbol_from_envelope(raw) == "OII"


def test_unusable_json_logs_a_warning_but_absence_does_not(caplog) -> None:
    """An ABSENT envelope is the ordinary non-Schwab case and is not noteworthy.

    Without this split every ordinary operator-typed entry would emit a
    WARNING, and a log line that fires on the common path stops being read.
    """
    with caplog.at_level(logging.WARNING):
        assert broker_order_id_from_envelope(None) is None
    assert not caplog.records
    with caplog.at_level(logging.WARNING):
        assert broker_order_id_from_envelope("not json") is None
    assert any("could not be decoded" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# 30a-30d -- the price rung
# ---------------------------------------------------------------------------
def test_round_up_cent_is_refused_case_30a() -> None:
    """The bound is ``mandate_limit_price``, not a second ``round``.

    PRE-FIX (``round(zone_cap, 2)`` as the cap): 17.41 <= 17.41 -> ADMITS a
    price ONE CENT ABOVE the framework's own cap.
    POST-FIX (``mandate_limit_price`` floors to 17.40): REFUSES.
    """
    order = _order(frozen_pivot=THIRD_DECIMAL_PIVOT, actual_limit_price=None)
    assert _judge(order, price=ROUND_UP_CENT) == "fill_outside_frozen_zone"


def test_floored_cent_is_admitted_case_30b() -> None:
    """...and the floored cent is still INSIDE.

    Without this, "refuse everything at the top of the zone" would pass 30a.
    """
    order = _order(frozen_pivot=THIRD_DECIMAL_PIVOT, actual_limit_price=None)
    assert _judge(order, price=FLOORED_CENT) is None


def test_broker_limit_below_the_framework_cap_refuses_case_30c(caplog) -> None:
    """The validity row's own ``actual_limit_price`` is CONSULTED.

    An implementation that ignores the accepted order's actuals ADMITS a fill
    priced between the broker limit and the framework cap -- a price the order
    the broker actually accepted could not have produced.  The DIVERGENCE
    itself is a WARNING, not a refusal: 0033 permits the two to differ.
    """
    order = _order(frozen_pivot=THIRD_DECIMAL_PIVOT, actual_limit_price=17.20)
    with caplog.at_level(logging.WARNING):
        assert _judge(order, price=17.30) == "fill_outside_frozen_zone"
    assert any("diverges from the framework cap" in r.getMessage()
               for r in caplog.records)
    # ...and a price inside BOTH bounds still admits, with the same warning.
    assert _judge(order, price=17.10) is None


def test_null_broker_limit_admits_on_the_framework_bound_case_30d() -> None:
    """Case 30d -- DEFENSIVE-HANDLING ONLY.  This shape is SCHEMA-IMPOSSIBLE.

    **22A-R9-04, verified on disk and CONFIRMED.**  The plan justified this
    case with "of the five live latch_order_intents rows exactly one carries
    ``actual_limit_price``; the four place rows carry NULL by construction" --
    a correct measurement with a WRONG INFERENCE.  Those four are ``place``
    intents and can never back an accepted link, and
    ``0033_latch_order_intents.sql`` CHECKs
    ``validity_outcome <> 'accepted_by_broker' OR (... actual_limit_price IS
    NOT NULL ...)``.  So a production ``AcceptedLatchOrder`` ALWAYS carries a
    limit.

    The CLAUSE is kept and the FIXTURE is relabelled: this pins that the pure
    function treats NULL as "no broker bound" rather than coercing it to 0.0
    (which would refuse every fill) or raising.  **Its green is NOT evidence
    that production NULLs occur** -- ``test_accepted_validity_rows_cannot_carry
    _a_null_limit_price`` below is what establishes they cannot.
    """
    order = _order(frozen_pivot=THIRD_DECIMAL_PIVOT, actual_limit_price=None)
    assert _judge(order, price=FLOORED_CENT) is None
    assert _judge(order, price=ROUND_UP_CENT) == "fill_outside_frozen_zone"


def test_accepted_validity_rows_cannot_carry_a_null_limit_price(tmp_path) -> None:
    """The CHECK that makes case 30d's shape schema-impossible, asserted.

    22A-R9-04's evidence, pinned rather than quoted: without this the "30d is
    defensive-only" claim is a sentence in a docstring with a shelf life.
    """
    from swing.data.db import ensure_schema

    conn = ensure_schema(tmp_path / "check.db")
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'latch_order_intents'"
    ).fetchone()[0]
    normalized = " ".join(sql.split())
    assert "validity_outcome <> 'accepted_by_broker'" in normalized
    assert "actual_limit_price IS NOT NULL" in normalized


def test_a_MISSING_envelope_symbol_fails_the_guard(tmp_path) -> None:
    """22A-R6-05: unknown is not pass.

    ``envelope_symbol is not None and envelope_symbol != ticker`` collapsed a
    three-valued question to two, so an envelope with no
    ``schwab_instrument_symbol`` PASSED and the evidence recorded a passing
    guard whose input was ``null``.  It is also an authorize-then-abort: the
    citation trigger requires that entry's input to be TEXT, so a correction
    the service admitted aborted at the INSERT.

    PRE-FIX: ``None`` (the guard passed).  POST-FIX: ``'ticker_mismatch'``.
    Its control is one line down -- a symbol that AGREES still passes, so the
    change refuses absence and not everything.
    """
    assert _judge(_order(), envelope_symbol=None) == "ticker_mismatch"
    assert _judge(_order(), envelope_symbol=_order().ticker) is None


# ---------------------------------------------------------------------------
# 22A-R15-02 (NARROW) -- A NON-FINITE BROKER LIMIT IS AN AUTHORIZE-THEN-ABORT
#
# `0033:414` is `CHECK (actual_limit_price IS NULL OR actual_limit_price > 0)`
# and `+inf > 0` is TRUE in SQLite, so an infinite broker limit is SCHEMA-LEGAL.
# The guard then rounded it to infinity and accepted any finite fill price
# below it; the citation evidence writer serialised the bare token `Infinity`,
# `json_valid()` read FALSE, and the citation INSERT ABORTED -- AFTER the
# service had authorized.  The operator got a raw `sqlite3` error where a typed
# refusal belonged: the authorize-then-abort shape this arc met five times.
#
# LIVE INCIDENCE IS MEASURED ZERO.  The mechanism is what is fixed; the CLASS
# fix is the trigger-predicate closure check, not a sixth patch at one site.
#
# It is the SAME shape as `frozen_pivot`'s guard four lines above, and it
# carries the SAME reason: `actual_limit_price` is a value FROZEN on the
# accepted validity row, and what is true of it is that it cannot be used.
# ---------------------------------------------------------------------------
def test_a_non_finite_broker_limit_refuses_before_any_arithmetic() -> None:
    """PRE-FIX: `None` -- the guard ACCEPTED, and the abort landed at the
    citation INSERT with an engine error.  POST-FIX: a typed refusal.

    Both infinities, because `-inf` passes `> 0` in neither direction but is
    equally unusable, and a value-set sweep that checked only `+inf` would
    leave the mirror case live.
    """
    for limit in (float("inf"), float("-inf")):
        assert _judge(_order(actual_limit_price=limit)) == (
            "frozen_value_unavailable"), limit


def test_a_FINITE_broker_limit_is_still_accepted() -> None:
    """THE CONTROL.  A refusal-only pair cannot establish that the guard can
    still accept the ordinary order, which is every real one."""
    assert _judge(_order(actual_limit_price=55.59)) is None
    assert _judge(_order(actual_limit_price=None)) is None
