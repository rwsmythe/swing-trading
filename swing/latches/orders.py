"""The broker-order join + the two tier-1 alarms (plan A.9). PURE.

No DB, no network, no transaction management. The impure part (borrowing the
Schwab client, making the audited call) lives in the web layer's
`resolve_open_orders`.

ATTRIBUTION IS PER-ORDER AGAINST LATCH PRICES, NOT PER-TICKER LIVENESS
(Codex R1-2). A ticker-level rule ("alarm only when the ticker has no live
latch") goes SILENT the moment a newer latch fires on that ticker -- which is
exactly the live VSTS geometry (fired 2026-06-25, cleared, fired again
2026-07-27) and exactly the post-supersede geometry. The operator's one manual
duty -- cancelling a resting order whose setup invalidated -- would then never
be announced.
"""
from __future__ import annotations

import math

from swing.latches.constants import (
    BUY_INSTRUCTIONS,
    MANDATE_ORDER_DURATIONS,
    MANDATE_ORDER_TYPE_BREAKOUT,
    MANDATE_ORDER_TYPE_PULLBACK,
    MANDATE_ORDER_TYPES,
)
from swing.latches.models import Latch, LatchOrderJoin, OrderAlarm, RestingOrder

# Display precision on BOTH sides of every price comparison (the
# price-precision-parity gotcha): an execution-grain sub-cent difference must
# not read as "the operator edited the order".
_PRICE_DP = 2

# A resting order's `price` is only a genuine LIMIT for these order types; for
# a plain STOP the mapper's documented fallback collapses `price` onto the stop
# trigger, and reading that as a limit would invent a limit that does not exist
# and then compare it against the zone cap.
_LIMIT_BEARING_ORDER_TYPES = frozenset({
    "LIMIT", "STOP_LIMIT", "TRAILING_STOP_LIMIT", "LIMIT_ON_CLOSE",
    "NET_DEBIT", "NET_CREDIT", "NET_ZERO",
})

# The clear reasons that leave the operator with an OUTSTANDING MANUAL DUTY --
# a resting order sitting against a mandate that no longer exists at that
# level. `superseded` is here on RD's gate ruling: "the panel must LOUDLY show
# that any resting order placed against the old level no longer matches the new
# mandate."
_CRITICAL_STALE_CLEAR_REASONS = frozenset({"invalidation", "superseded"})


def to_resting_orders(schwab_orders) -> tuple[RestingOrder, ...]:
    """Map `SchwabOrderResponse` -> `RestingOrder`, keeping BUY-side orders
    whose status is RESTING or INDETERMINATE. Terminal statuses are dropped."""
    out: list[RestingOrder] = []
    for o in schwab_orders or ():
        instruction = (getattr(o, "instruction", "") or "").upper()
        if instruction not in BUY_INSTRUCTIONS:
            continue
        order_type = (getattr(o, "order_type", "") or "").upper()
        stop_price = getattr(o, "stop_price", None)
        price = getattr(o, "price", None)
        if order_type in _LIMIT_BEARING_ORDER_TYPES:
            limit_price = price
        elif stop_price is not None and price is not None and price == stop_price:
            # The mapper's plain-STOP fallback collapsed `price` onto the stop.
            limit_price = None
        else:
            limit_price = price
        candidate = RestingOrder(
            order_id=str(o.order_id),
            ticker=(getattr(o, "instrument_symbol", "") or "").upper(),
            instruction=instruction,
            quantity=float(getattr(o, "quantity", 0.0) or 0.0),
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status=getattr(o, "status", "") or "",
            duration=getattr(o, "duration", None),
        )
        if candidate.is_resting or candidate.is_indeterminate:
            out.append(candidate)
    return tuple(out)


def indeterminate_order_tickers(orders) -> tuple[str, ...]:
    """Tickers carrying a BUY order whose broker status is INDETERMINATE.

    THE SINGLE SOURCE for both halves of the indeterminate rule: the SUPPRESSION
    (here in `join_orders_to_latches`) and the RENDER (in the fragment VM). They
    must be computed from the SAME predicate over the SAME order set -- deriving
    the render half from anything else (e.g. only LIVE latches) lets the
    suppression fire on a ticker the banner never mentions, which turns an
    honest "unknown" into a silent all-clear.
    """
    return tuple(sorted({
        o.ticker for o in orders or ()
        if (o.instruction or "").upper() in BUY_INSTRUCTIONS and o.is_indeterminate
    }))


def expected_mandate_order_type(*, latched_pivot, last_close) -> str | None:
    """Which of the two mandate forms applies at this price, or ``None``.

    The regime boundary is the LATCHED PIVOT (RD, 2026-07-27): below it the
    mandate is a GTC STOP_LIMIT (the breakout entry); at or above it a buy stop
    would sit BELOW the market and be rejected by the broker, so the mandate is
    a GTC LIMIT at the zone cap (the pullback entry).

    Returns ``None`` -- regime UNDETERMINABLE -- when either side is absent or
    unusable. The caller must then accept EITHER form rather than assert a
    mismatch it cannot support (an absent price is not evidence of a wrong
    order shape).

    Both sides are rounded to display precision before the comparison (the
    price-precision-parity gotcha): a sub-cent float artifact must never flip
    the regime and invert which instrument the panel calls correct.
    """
    values: list[float] = []
    for raw in (latched_pivot, last_close):
        if raw is None or isinstance(raw, bool):
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value):
            return None
        values.append(value)
    pivot, close = values
    if round(close, _PRICE_DP) < round(pivot, _PRICE_DP):
        return MANDATE_ORDER_TYPE_BREAKOUT
    return MANDATE_ORDER_TYPE_PULLBACK


def mandate_shape_mismatch(
    order: RestingOrder, *, latched_pivot=None, last_close=None,
) -> str | None:
    """Why this order is not the MANDATED order shape, or None.

    Price agreement alone is not coverage: an order at the right prices but the
    wrong SHAPE does not implement the mandate. The mandate has TWO forms and
    the price regime selects between them (see `expected_mandate_order_type`),
    so this reports against whichever form was expected in THAT regime -- a
    hard-coded "not STOP_LIMIT" would be wrong half the time, and on this arc's
    own live subject (FTRE) it produced a FALSE mismatch against the operator's
    situationally-CORRECT order.

    GTC-ness is required of BOTH forms and is checked independently of the
    regime: a DAY order expires tonight and leaves the operator uncovered
    tomorrow (the FTRE failure mode).

    ABSENT values are NOT asserted against: an older payload that simply does
    not carry a duration is reported as unknown-but-not-wrong, so the panel does
    not become permanently noisy on shapes it cannot see (real Schwab payloads
    DO carry `duration`), and an absent/unusable price leaves the regime unknown
    so BOTH forms are accepted.
    """
    order_type = (order.order_type or "").upper()
    expected = expected_mandate_order_type(
        latched_pivot=latched_pivot, last_close=last_close)
    if order_type:
        if expected is None:
            if order_type not in MANDATE_ORDER_TYPES:
                return (
                    f"order type is {order_type}, not "
                    f"{MANDATE_ORDER_TYPE_BREAKOUT} (below the latched pivot) "
                    f"or {MANDATE_ORDER_TYPE_PULLBACK} (at or above it)")
        elif order_type != expected:
            regime = (
                "BELOW" if expected == MANDATE_ORDER_TYPE_BREAKOUT
                else "AT OR ABOVE")
            return (
                f"order type is {order_type}, but the last close is {regime} "
                f"the latched pivot, so the mandate is a {expected}")
    duration = (order.duration or "").upper()
    if duration and duration not in MANDATE_ORDER_DURATIONS:
        return f"duration is {duration}, not GOOD_TILL_CANCEL"
    return None


def _agrees(order_price, latch_price) -> bool | None:
    """`None` (UNKNOWN) when either side is absent -- never `False`."""
    if order_price is None or latch_price is None:
        return None
    return round(float(order_price), _PRICE_DP) == round(float(latch_price), _PRICE_DP)


def _match_latch(order: RestingOrder, ticker_latches: list[Latch]) -> Latch | None:
    """The latch whose FROZEN prices this order matches, or ``None``.

    STOP-family orders match on the trigger vs the latched pivot; a LIMIT-only
    order (no stop) matches on the limit vs the zone cap. Ties break to the most
    recent anchor.
    """
    if order.stop_price is not None:
        hits = [
            x for x in ticker_latches
            if _agrees(order.stop_price, x.latched_pivot) is True
        ]
    elif order.limit_price is not None:
        hits = [
            x for x in ticker_latches
            if _agrees(order.limit_price, x.zone_cap) is True
        ]
    else:
        return None
    if not hits:
        return None
    return max(hits, key=lambda x: (x.anchor, x.identity.candidate_id))


def _pick_reference_order(orders: list[RestingOrder], latch: Latch) -> RestingOrder | None:
    """The order the agreement flags are reported from.

    Multi-order agreement is ANY-ORDER-AGREES (plan H.6): prefer an order that
    agrees on BOTH legs, else fall back to the first, so a mispriced order is
    still reported rather than hidden.

    NOTE this deliberately answers only "is the mandate COVERED". It cannot
    also answer "is there a stray order" -- a fully-agreeing order would mask
    one. Stray orders travel separately as `LatchOrderJoin.unmatched_orders`.
    """
    if not orders:
        return None
    for o in orders:
        if (_agrees(o.stop_price, latch.latched_pivot) is True
                and _agrees(o.limit_price, latch.zone_cap) is True):
            return o
    return orders[0]


def join_orders_to_latches(*, latches, orders):
    """PURE. Returns ``({latch_candidate_id: LatchOrderJoin}, alarms)``."""
    latches = list(latches)
    by_ticker: dict[str, list[Latch]] = {}
    for latch in latches:
        by_ticker.setdefault(latch.identity.ticker, []).append(latch)

    resting_by_ticker: dict[str, list[RestingOrder]] = {}
    indeterminate_tickers = set(indeterminate_order_tickers(orders))
    for order in orders or ():
        if (order.instruction or "").upper() not in BUY_INSTRUCTIONS:
            continue
        if order.is_indeterminate:
            continue
        if not order.is_resting:
            continue
        resting_by_ticker.setdefault(order.ticker, []).append(order)

    # Per-order attribution, computed ONCE so the joins and the alarms cannot
    # disagree about which latch an order belongs to.
    matched: dict[str, Latch | None] = {}
    for ticker, ticker_orders in resting_by_ticker.items():
        for order in ticker_orders:
            matched[order.order_id] = _match_latch(order, by_ticker.get(ticker, []))

    joins: dict[int, LatchOrderJoin] = {}
    for latch in latches:
        ticker = latch.identity.ticker
        cid = latch.identity.candidate_id
        ticker_orders = resting_by_ticker.get(ticker, [])
        mine = [o for o in ticker_orders if matched.get(o.order_id) is latch]
        unmatched: list[RestingOrder] = []
        if latch.is_live:
            # An order at NEITHER latch's price is still reported against the
            # live mandate, so it surfaces as a DISAGREEMENT rather than as a
            # factually false "no resting order" alarm. It is kept SEPARATE
            # from the matched set so a correctly-priced order cannot mask it.
            unmatched = [
                o for o in ticker_orders if matched.get(o.order_id) is None]
        reference = _pick_reference_order(mine or unmatched, latch)
        joins[cid] = LatchOrderJoin(
            latch_candidate_id=cid,
            orders=tuple(mine + unmatched),
            unmatched_orders=tuple(unmatched),
            order_stop_agrees=(
                None if reference is None
                else _agrees(reference.stop_price, latch.latched_pivot)),
            order_limit_agrees=(
                None if reference is None
                else _agrees(reference.limit_price, latch.zone_cap)),
            indeterminate=ticker in indeterminate_tickers,
            # The size of the MATCHED set only (never the strays, which travel
            # separately and are already reported one by one). It is what lets
            # the panel notice that the agreement flags above describe one of
            # several orders and withhold the affirmative all-clear.
            matched_order_count=len(mine),
        )

    alarms: list[OrderAlarm] = []

    # (a) LATCH_ARMED_NO_RESTING_ORDER -- the FTRE failure mode.
    #
    # COVERAGE IS PER-LATCH, NOT PER-TICKER. An order is treated as covering
    # THIS mandate when it either matches this latch's frozen prices OR matches
    # NO latch at all (a plausibly-mispriced attempt at it, which plan A.9 says
    # must surface through the agreement flags rather than a factually false
    # "no order" alarm). An order matched to a DIFFERENT, CLEARED latch is NOT
    # coverage: that is the post-supersede geometry RD called out -- old latch
    # superseded at 18.34 with its GTC order still resting, new latch armed at
    # 20.19 with nothing behind it. A ticker-level rule goes silent there and
    # the operator is never told the LIVE mandate is naked.
    for latch in latches:
        ticker = latch.identity.ticker
        if not latch.is_live:
            continue
        if ticker in indeterminate_tickers:
            continue
        covering = [
            o for o in resting_by_ticker.get(ticker, [])
            if matched.get(o.order_id) is latch or matched.get(o.order_id) is None
        ]
        if covering:
            continue
        alarms.append(OrderAlarm(
            kind="LATCH_ARMED_NO_RESTING_ORDER",
            ticker=ticker,
            latch_candidate_id=latch.identity.candidate_id,
            detail=(
                f"latch armed at pivot {latch.latched_pivot:.2f} "
                f"(zone cap {latch.zone_cap:.2f}) with NO resting BUY order at "
                f"the broker; expires {latch.horizon_expiry.isoformat()}"),
            severity="critical",
        ))

    # (b)/(c) ORDER_RESTING_LATCH_CLEARED -- the stale-order hazard.
    for ticker, ticker_orders in sorted(resting_by_ticker.items()):
        if ticker in indeterminate_tickers:
            continue                      # an unknown order book fires nothing
        ticker_latches = by_ticker.get(ticker, [])
        live_present = any(x.is_live for x in ticker_latches)
        for order in ticker_orders:
            target = matched.get(order.order_id)
            if target is not None and target.is_live:
                continue                  # the order matches a LIVE mandate
            if target is None:
                if live_present:
                    continue              # a mispriced order for a live mandate
                # DELIBERATELY NOT attributed to the most recently cleared latch
                # (a deviation from plan A.9, recorded). Its prices match NO
                # latch, so claiming it "matches a latch that CLEARED by
                # invalidation" is a FALSE statement about a real broker order,
                # and it would inherit `critical` severity from an unrelated
                # latch's clear reason. The alarm still fires -- an unexplained
                # resting order with no live mandate is worth surfacing -- but
                # it says only what is true.
                target = None
            reason = None if target is None else target.clear_reason
            session = (
                None if target is None or target.clear_session is None
                else target.clear_session.isoformat())
            if target is None:
                detail = (
                    f"resting BUY order {order.order_id} on {ticker} matches NO "
                    "latch's frozen prices, and no latch on this ticker is "
                    "live; verify it at the broker")
            else:
                detail = (
                    f"resting BUY order {order.order_id} matches a latch that "
                    f"CLEARED by {reason} on {session}; cancel it at the broker")
            alarms.append(OrderAlarm(
                kind="ORDER_RESTING_LATCH_CLEARED",
                ticker=ticker,
                latch_candidate_id=(
                    None if target is None else target.identity.candidate_id),
                detail=detail,
                severity=(
                    "critical" if reason in _CRITICAL_STALE_CLEAR_REASONS
                    else "warning"),
            ))

    return joins, tuple(alarms)
