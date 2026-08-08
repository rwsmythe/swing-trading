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
from dataclasses import dataclass
from datetime import date

from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    ARCHIVE_STATUS_UNAVAILABLE,
    BUY_INSTRUCTIONS,
    CLOSE_PROVENANCE_ABSENT,
    CLOSE_PROVENANCE_CORROBORATED,
    CLOSE_PROVENANCE_FUTURE_STAMP,
    CLOSE_PROVENANCE_UNCORROBORATED,
    MANDATE_ORDER_DURATIONS,
    MANDATE_ORDER_TYPE_BREAKOUT,
    MANDATE_ORDER_TYPE_PULLBACK,
    MANDATE_ORDER_TYPES,
    PRICE_DP,
    mandate_limit_price,
)
from swing.latches.models import Latch, LatchOrderJoin, OrderAlarm, RestingOrder

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
#
# `declined` joins on RD's OQ-1 reasoning (2026-08-06), which he ruled for
# `criteria_lapsed` and which reaches here identically: THE ALARM CHANNEL
# ENCODES DUTY, NOT FAULT -- blame lives in the DISPOSITION. The duty behind a
# declined mandate (cancel the resting order) and the consequence of ignoring it
# (an unmandated fill on a rally through a pivot nobody is standing behind) are
# the same as the invalidation case, so the severity is the same.
#
# `criteria_lapsed` joins on the SAME OQ-1 ruling, which RD made FOR it and
# against CHARC's prior. The prior distinguished a mandate that was WRONG
# (invalidation / superseded) from one the framework WITHDREW -- but that is a
# BLAME distinction, and blame already lives in the DISPOSITION
# (`framework_withdrawn`, excluded from the discipline signal AND the away
# rate). Severity follows DUTY; fault follows disposition.
#
# `horizon` is deliberately ABSENT and stays absent: a mandate that simply ran
# out its window carries no act the operator left undone.
_CRITICAL_STALE_CLEAR_REASONS = frozenset({
    "invalidation", "superseded", "declined", "criteria_lapsed"})


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
    if round(close, PRICE_DP) < round(pivot, PRICE_DP):
        return MANDATE_ORDER_TYPE_BREAKOUT
    return MANDATE_ORDER_TYPE_PULLBACK


def _usable_price(raw) -> float | None:
    """A price the panel may reason from, or ``None``.

    Rejects ``bool`` explicitly (``True`` is not a price), non-numeric values,
    and the non-finite shapes -- the same predicate
    ``expected_mandate_order_type`` already applies, single-sourced here so the
    ladder and the regime selector cannot disagree about what "usable" means.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


@dataclass(frozen=True)
class CloseProvenance:
    """What the panel may CLAIM about the regime close (gotcha #30).

    THE WHOLE DESIGN IN ONE SENTENCE: **never act on an undated price, in
    either direction.** Assert a match only from a close DATED the derivation
    session; raise a mismatch alarm only from a close dated `D < S` that is
    PROVEN to be dated `D`.

    The archive is used ONLY to DATE the persisted close -- it never REPLACES
    it. The number the check judges stays the number the cards render
    (`load_last_closes` -> `candidates.close`), so 21-A's shown-equals-judged
    invariant is preserved exactly. What changes is what the panel is willing
    to claim about that number.

    WHAT CORROBORATION PROVES, AND WHAT IT DOES NOT. The archive is an
    independently DATED record, not an independently SOURCED one:
    `candidates.close` was itself derived from an archive read at evaluation
    time, so a match proves *the persisted close is the archive bar dated X*.
    It does NOT prove the archive bar is a faithful record of the market. That
    residual is out of this ladder's model and is not newly introduced by it --
    the panel's whole price picture already rests on the archive being honest,
    and the archive's own integrity is guarded upstream (the F6 / #24 / #26 /
    18-A / 18-B finiteness + trailing-ragged + write-through defenses).
    """

    price: float | None
    provenance: str                    # one of CLOSE_PROVENANCES
    stamp_session: str | None          # the run stamp: an UPPER BOUND on the date
    stamp_date: date | None            # the parsed stamp, or None when unplaceable
    session_close: float | None        # W(S): the archive close dated exactly S
    stamp_session_close: float | None  # W(D): the archive close dated exactly D
    archive_status: str                # one of ARCHIVE_STATUSES
    bars_through: date | None          # display/label context ONLY, never the witness
    derivation_session: date

    @property
    def may_assert(self) -> bool:
        """Rung A ONLY. No other rung may ever contribute to an all-clear."""
        return self.provenance == CLOSE_PROVENANCE_CORROBORATED

    @property
    def has_dated_conflict(self) -> bool:
        """B-conflict: a bar DATED S exists and DISAGREES with the recorded
        close.

        Inert for the regime, deliberately (Codex R4 MAJOR 2). Here the
        persisted close is not merely un-dated -- it is CONTRADICTED by dated
        evidence the panel is holding. Alarming from the older, contradicted
        number against an order that is correct for the dated bar would be a
        false alarm manufactured by our own inconsistency, and it could repeat
        daily whenever the archive refreshes ahead of the candidate rows.
        """
        return (self.provenance == CLOSE_PROVENANCE_UNCORROBORATED
                and self.session_close is not None)

    @property
    def archive_unavailable(self) -> bool:
        """B-unavailable: the archive read RAISED, so the absence of a witness
        is OUR IGNORANCE rather than a fact about the data."""
        return self.archive_status == ARCHIVE_STATUS_UNAVAILABLE

    @property
    def dated_at_stamp(self) -> bool:
        """Condition (1), CHARACTERISABLE: the close is corroborated AT ITS OWN
        STAMP, so its date is KNOWN rather than assumed.

        This is the rung-A test applied at `D` instead of `S`, and it is
        NON-NEGOTIABLE (RD). A stamp comparison alone (`D == L`) compares two
        RUN-LEVEL values, so a ticker that lagged INSIDE the latest cohort
        satisfies it while its true close is a session older than `D` claims --
        which would be gotcha #30 committed inside the fix for gotcha #30,
        merely relocated from the assert direction to the alarm direction.
        Requiring corroboration at `D` removes the stamp from the reasoning
        entirely.
        """
        return (self.price is not None
                and self.stamp_session_close is not None
                and round(self.stamp_session_close, PRICE_DP)
                == round(self.price, PRICE_DP))


def classify_close_provenance(
    *, quote, derivation_session: date, bars_through, archive_closes,
    archive_status: str = ARCHIVE_STATUS_OK,
) -> CloseProvenance:
    """Place the recorded close on the provenance ladder. PURE.

    `quote` is the shipped `(close, stamp_iso)` tuple from `load_last_closes`,
    or `None`. `archive_closes` is that ticker's `{session -> close}` map
    (possibly empty). No I/O, no exception swallowing beyond the numeric
    coercion `expected_mandate_order_type` already does.

    The rungs, in the order they are decided:

      C `absent`        -- no usable price. Neither direction.
      F `future_stamp`  -- the close is stamped AFTER the derivation session,
                           or cannot be placed in time at all. Neither
                           direction. This rung PRE-EMPTS rung A: the fragment
                           insists every part of its picture describe ONE
                           coherent moment (it is why a one-session-stale
                           render anchor suppresses the alarms), and a
                           future-stamped close is held to the same standard.
                           Reachable: `load_last_closes` returns the GLOBALLY
                           latest close per ticker while the fragment POST
                           deliberately rebuilds an OLDER render-time anchor.
      A `corroborated`  -- a bar dated EXACTLY S whose close IS the recorded
                           close, to the cent. May assert.
      B `uncorroborated`-- everything else. May alarm only under the caller's
                           two conditions (plan B.2.1).

    RUNG A IS DELIBERATELY TIGHT. Bar EXISTENCE alone is not enough: the
    evaluation may have run before that bar landed, in which case the persisted
    close is older than a bar that now exists. It is the VALUE agreement WITH
    the exact date that ties the two together. Coincidental agreement (two
    sessions closing at the identical cent) cannot fabricate a rung-A claim,
    because the compared bar is pinned to S.
    """
    price = None if quote is None else _usable_price(quote[0])
    raw_stamp = None if quote is None else quote[1]
    stamp_session = None if raw_stamp is None else str(raw_stamp)
    try:
        stamp_date = (
            None if not stamp_session else date.fromisoformat(stamp_session))
    except (TypeError, ValueError):
        stamp_date = None

    closes = archive_closes or {}
    session_close = _usable_price(closes.get(derivation_session))
    stamp_session_close = (
        None if stamp_date is None else _usable_price(closes.get(stamp_date)))

    if price is None:
        provenance = CLOSE_PROVENANCE_ABSENT
    elif stamp_date is None or stamp_date > derivation_session:
        provenance = CLOSE_PROVENANCE_FUTURE_STAMP
    elif (session_close is not None
            and round(session_close, PRICE_DP) == round(price, PRICE_DP)):
        provenance = CLOSE_PROVENANCE_CORROBORATED
    else:
        provenance = CLOSE_PROVENANCE_UNCORROBORATED

    return CloseProvenance(
        price=price,
        provenance=provenance,
        stamp_session=stamp_session,
        stamp_date=stamp_date,
        session_close=session_close,
        stamp_session_close=stamp_session_close,
        archive_status=(
            archive_status if archive_status in
            (ARCHIVE_STATUS_OK, ARCHIVE_STATUS_UNAVAILABLE)
            else ARCHIVE_STATUS_OK),
        bars_through=bars_through,
        derivation_session=derivation_session,
    )


def mandate_shape_mismatch(
    order: RestingOrder, *, latched_pivot=None, last_close=None,
    zone_cap=None,
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

    STOP-LEG COHERENCE IS REPORTED HERE TOO, so this and
    `_implements_mandate_shape` cannot say different things about the same order
    (Codex R3 MINOR). Without it a `LIMIT` carrying a stop trigger produced a
    critical "wrong shape" presence alarm while the operator-facing shape line
    said nothing at all about it -- an alarm with no explanation beside it, which
    is how an alarm stops being believed. It is REGIME-INDEPENDENT: the leg is
    required by the breakout form and forbidden by the pullback form, so an
    order that disagrees with ITS OWN declared type is wrong in either regime.
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
    if order_type in MANDATE_ORDER_TYPES and order.limit_price is None:
        return ("it carries NO limit price, so nothing caps the fill at the "
                "zone; the cap is what stops the operator chasing")
    if order_type == MANDATE_ORDER_TYPE_BREAKOUT and order.stop_price is None:
        return (f"order type is {MANDATE_ORDER_TYPE_BREAKOUT} but it carries NO "
                "stop trigger, so it cannot fire at the latched pivot")
    # GATED ON THE MANDATE'S OWN GEOMETRY, exactly as `_covers_mandate` is
    # (Codex R6 MAJOR): cent-flooring collapses the zone on a sub-dollar pivot,
    # where the framework itself emits stop == limit. An ungated rule would
    # declare the framework's OWN order malformed. `zone_cap` ABSENT means the
    # caller cannot say, and an absent value is never asserted against here.
    if (order_type == MANDATE_ORDER_TYPE_BREAKOUT
            and order.stop_price is not None
            and order.limit_price is not None
            and zone_cap is not None
            and latched_pivot is not None
            and mandate_limit_price(zone_cap) > latched_pivot
            and order.limit_price <= order.stop_price):
        return (f"its limit {order.limit_price:.2f} is not ABOVE its stop "
                f"trigger {order.stop_price:.2f}, so no zone cap was observed "
                "(the broker payload may have carried no limit at all)")
    if order_type == MANDATE_ORDER_TYPE_PULLBACK and order.stop_price is not None:
        return (f"order type is {MANDATE_ORDER_TYPE_PULLBACK} but it CARRIES a "
                f"stop trigger ({order.stop_price:.2f}); a pullback mandate has "
                "no stop leg")
    return None


def _agrees(order_price, latch_price) -> bool | None:
    """`None` (UNKNOWN) when either side is absent -- never `False`.

    IT COMPARES TWO PRICES; IT DOES NOT DERIVE ONE. The mandate's limit price
    comes from `mandate_limit_price` at every call site below -- see
    `_mandate_limit_of`. This function must never grow a rounding RULE of its
    own: that is precisely the second definition CHARC's ruling deleted.
    """
    if order_price is None or latch_price is None:
        return None
    return round(float(order_price), PRICE_DP) == round(float(latch_price), PRICE_DP)


def _mandate_limit_of(latch: Latch) -> float:
    """The limit price THIS latch's mandate carries -- the single-sourced one.

    THE ONLY WAY THE COMPARATOR MAY OBTAIN A MANDATE LIMIT (CHARC ruling,
    2026-07-30). Reading `latch.zone_cap` straight into `_agrees` re-derives the
    mandate limit by a SECOND rule (`round`), and two independently-plausible
    roundings of one quantity is the D6 class. On the live VSTS cap of 17.407
    the two rules disagreed -- 17.40 emitted, 17.41 expected -- and the panel
    called the operator's correct order a stray.
    """
    return mandate_limit_price(latch.zone_cap)


def _match_latch(order: RestingOrder, ticker_latches: list[Latch]) -> Latch | None:
    """The latch whose FROZEN prices this order matches, or ``None``.

    STOP-family orders match on the trigger vs the latched pivot; a LIMIT-only
    order (no stop) matches on the limit vs THE MANDATE'S LIMIT PRICE -- the
    value the framework actually emits, not a second rounding of the cap. Ties
    break to the most recent anchor.
    """
    if order.stop_price is not None:
        hits = [
            x for x in ticker_latches
            if _agrees(order.stop_price, x.latched_pivot) is True
        ]
    elif order.limit_price is not None:
        hits = [
            x for x in ticker_latches
            if _agrees(order.limit_price, _mandate_limit_of(x)) is True
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
                and _agrees(o.limit_price, _mandate_limit_of(latch)) is True):
            return o
    return orders[0]


def _implements_mandate_shape(
    order: RestingOrder, *, mandate_has_room: bool,
) -> bool:
    """Could this order be a mandate order AT ALL, ignoring price and regime?

    THE REGIME-INDEPENDENT HALF ONLY. The pure join holds no last close, so it
    cannot select between the two mandate forms; what it CAN say is that an
    order is neither of them, or is internally incoherent.

    COVERAGE IS AN ASSERTION OF A MATCH, so it needs POSITIVE evidence. An
    ABSENT order type therefore does NOT support coverage: `order_type` is
    explicitly allowed to be empty by `SchwabOrderResponse` and the mapper
    defaults a missing `orderType` to `""` (Codex R2 MAJOR), and without it
    there is no evidence the resting order is a mandate form at all -- letting
    it stand as coverage prints an affirmative all-clear over an instrument
    nobody read.

    AN ABSENT DURATION IS TREATED DIFFERENTLY, ON PURPOSE, AND THE ASYMMETRY IS
    STATED RATHER THAN LEFT TO BE INFERRED: the type IS the instrument, while a
    duration is a MODIFIER on an already-identified mandate form, and 21-A
    explicitly ruled an absent duration unknown-but-not-wrong so the panel does
    not become permanently noisy on shapes it cannot see. `mandate_shape_
    mismatch` carries the same posture for the same reason.

    STOP-LEG COHERENCE WITH THE DECLARED TYPE (Codex R2 MAJOR): a `LIMIT`
    carrying a stop trigger, or a `STOP_LIMIT` missing one, is not a mandate
    order in either regime. This is the exact rule migration 0033 already
    enforces on the FRAMEWORK side (`framework_order_type <> 'LIMIT' OR
    framework_stop_price IS NULL`), applied to the OBSERVED order. Without it a
    `LIMIT` carrying a stop at the frozen pivot attributes to the latch on its
    stop leg, covers the mandate, and -- in the pullback regime, where the
    fragment expects no stop leg at all -- reads as an affirmative all-clear.
    """
    order_type = (order.order_type or "").upper()
    if order_type not in MANDATE_ORDER_TYPES:
        return False
    duration = (order.duration or "").upper()
    if duration and duration not in MANDATE_ORDER_DURATIONS:
        return False
    # THE LIMIT LEG IS REQUIRED BY *BOTH* FORMS (codex-auto-review MAJOR). The
    # cap is what stops the operator chasing -- it is the whole reason the
    # breakout mandate is a STOP_LIMIT rather than a plain STOP -- and
    # `SchwabOrderResponse` permits `price=None`, which `to_resting_orders`
    # propagates as `limit_price=None`. Without this, a WORKING GTC `LIMIT` with
    # no limit at all, or a `STOP_LIMIT` with a trigger and no cap, covered the
    # mandate and suppressed the critical alarm: an order incapable of enforcing
    # the zone would have read as implementing it. Same class as the stop-only
    # order the R7 CRITICAL named, on the other leg.
    if order.limit_price is None:
        return False
    # ...AND AN INVENTED CAP IS NOT A CAP (Codex R5 MAJOR). When Schwab omits
    # `price` but supplies `stopPrice`, `map_orders_to_fill_candidates`
    # SUBSTITUTES the trigger into `price` (mappers.py:317-320), and
    # `to_resting_orders` then reads that back as `limit_price` because
    # STOP_LIMIT is limit-bearing -- so the `is None` guard above never sees the
    # missing cap.
    #
    # IT IS GATED ON `mandate_has_room`, AND THAT GATE IS THE WHOLE POINT
    # (Codex R6 MAJOR). "The cap is above the trigger" is true of the mandate
    # only while cent-flooring leaves room: at pivot 0.25 the cap is 0.2575 and
    # the framework ITSELF emits stop 0.25 / limit 0.25, and neither
    # `candidates.pivot` nor `Latch` imposes a price floor that prevents it. An
    # ungated rule therefore fires `LATCH_ARMED_NO_RESTING_ORDER` against THE
    # EXACT ORDER THE FRAMEWORK INSTRUCTED -- the self-flagging class this whole
    # pass exists to eliminate, re-created inside the fix for it. So the caller
    # supplies whether THIS mandate's own cap clears its own trigger, and the
    # check runs only then. It is a REQUIRED argument: a default would silently
    # re-create the bug at the next call site.
    if (mandate_has_room and order_type == MANDATE_ORDER_TYPE_BREAKOUT
            and order.stop_price is not None
            and order.limit_price <= order.stop_price):
        return False
    # The stop leg is REQUIRED by the breakout form and FORBIDDEN by the
    # pullback form, so coherence is exactly "carries a trigger iff STOP_LIMIT".
    return (order.stop_price is not None) == (
        order_type == MANDATE_ORDER_TYPE_BREAKOUT)


def _mandate_has_room(latch: Latch) -> bool:
    """Does THIS mandate's own cap clear its own trigger?

    Cent-flooring can collapse the 3% zone to nothing on a sub-dollar
    pivot -- at 0.25 the cap is 0.2575 and the framework emits stop 0.25 /
    limit 0.25 -- so 'the cap is above the trigger' is a property of the
    GEOMETRY, not a universal truth about the mandate form. Read through
    the single-sourced `mandate_limit_price`, so the comparison is against
    the value the framework ACTUALLY EMITS rather than the raw cap.
    """
    return _mandate_limit_of(latch) > latch.latched_pivot


def _covers_mandate(order: RestingOrder, latch: Latch, *, attributed) -> bool:
    """Is there an order IMPLEMENTING this mandate? PRESENCE + SHAPE ONLY.

    RD's ruling, 2026-07-30: **`LATCH_ARMED_NO_RESTING_ORDER` keys on PRESENCE
    and SHAPE -- order type, duration, stop leg, side -- NEVER on exact limit
    equality.** An order one cent from the cap DOES implement the mandate: it is
    a GTC buy limit at the zone edge. Calling that "no resting order" is not a
    threshold problem, it is a FALSE STATEMENT, and it is the loudest alarm on
    the panel firing against the operator's own correct behaviour. A limit-price
    difference is a per-field DELTA, which is what the execution-parity ledger
    exists to record; routing it into a presence alarm destroys an alarm channel
    to report something the ledger already reports better.

    `attributed` is the latch this order was price-attributed to (or `None`),
    computed ONCE by the caller so the joins and the alarms cannot disagree.

      * attributed to THIS latch                 -> coverage.
      * attributed to NO latch                   -> coverage (plan A.9,
        unchanged: a plausibly-mispriced attempt surfaces through the agreement
        flags rather than a factually false "no order" alarm).
      * attributed to ANOTHER latch              -> coverage IFF this order
        carries NO STOP LEG. A limit-only order can only ever have been
        attributed by LIMIT EQUALITY, and the limit may never key this alarm.
        An order that DOES carry a stop trigger was attributed by that trigger
        -- the stop leg is one of RD's named SHAPE keys -- so it genuinely
        belongs to the other mandate and is not coverage of this one. That is
        what preserves the post-supersede geometry: the old 18.34 stop-limit
        does not cover the new 20.19 latch, and the naked live mandate is still
        announced.

    ORDER TYPE, DURATION AND STOP-LEG COHERENCE ARE KEYS TOO, and they are
    enforced (Codex R1 + R2 MAJORs on the ruling pass). They are named in the
    ruling, and the harm is the FTRE failure mode itself: a DAY stop-limit
    expires tonight and leaves the operator uncovered tomorrow, and a plain BUY
    `STOP` carries no cap at all -- neither implements the mandate, yet either
    used to SUPPRESS the critical presence alarm merely by existing. Only the
    REGIME-INDEPENDENT half is judged here, because the pure join holds no price
    and so cannot know which of the two mandate forms applies; see
    `_implements_mandate_shape`.

    THE ALARM'S DETAIL IS WRITTEN BY THE CALLER FROM `covering` VS THE ORDER
    COUNT, so it never claims "NO resting BUY order" about a ticker that has
    one. An alarm that fires on a true condition with a false explanation is
    the same defect this ruling exists to remove.
    """
    if not _implements_mandate_shape(
            order, mandate_has_room=_mandate_has_room(latch)):
        return False
    if attributed is latch or attributed is None:
        return True
    return order.stop_price is None


@dataclass(frozen=True)
class OrderAttribution:
    """ONE broker order, and the latch (if any) its frozen prices match.

    THE SUBJECT OF THE RECORDING AFFORDANCE, and deliberately not the subject
    of any alarm. RD's principle (2026-08-03): recording an operator action and
    alarming on a detected problem are DIFFERENT FUNCTIONS, and the affordance
    to record must not be gated on the alarm that detects. So this surface
    carries what the operator holds -- a broker order attributable to a
    mandate -- with no reference to whether anything is wrong with it.
    """

    order_id: str
    ticker: str
    status: str
    is_indeterminate: bool
    latch_candidate_id: int | None


def attribute_orders_to_latches(*, latches, orders) -> tuple[OrderAttribution, ...]:
    """PURE. One row per BUY order that is RESTING **or** INDETERMINATE.

    INDETERMINATE ORDERS ARE INCLUDED, WHICH IS THE WHOLE POINT. The join drops
    them (`if order.is_indeterminate: continue`) and both alarm loops skip
    their entire ticker, and that is CORRECT FOR THE ALARM -- an unknown order
    book must fire nothing, because a false all-clear and a false alarm are
    both worse than an honest unknown. It is BACKWARDS for the recording
    affordance: `PENDING_CANCEL` is the state produced BY the operator doing
    exactly what the framework asked, so the framework would offer him no way
    to record the act it requested.

    SORTED BY `order_id` IN THE RETURNED TUPLE ONLY, for a stable render. The
    caller may share the resulting MAP with `join_orders_to_latches` but must
    never feed it this ORDERING: `_pick_reference_order` falls back to
    `orders[0]` and `LatchOrderJoin.orders` is built from the per-ticker list,
    so re-ordering the input can change which order the agreement flags
    describe -- a behaviour change wearing a refactor's clothes.
    """
    latches = list(latches)
    by_ticker: dict[str, list[Latch]] = {}
    for latch in latches:
        by_ticker.setdefault(latch.identity.ticker, []).append(latch)

    rows: list[OrderAttribution] = []
    for order in orders or ():
        if (order.instruction or "").upper() not in BUY_INSTRUCTIONS:
            continue
        if not (order.is_resting or order.is_indeterminate):
            continue
        matched = _match_latch(order, by_ticker.get(order.ticker, []))
        rows.append(OrderAttribution(
            order_id=order.order_id,
            ticker=order.ticker,
            status=order.status,
            is_indeterminate=order.is_indeterminate,
            latch_candidate_id=(
                None if matched is None else matched.identity.candidate_id),
        ))
    return tuple(sorted(rows, key=lambda r: r.order_id))


def join_orders_to_latches(*, latches, orders, attribution=None):
    """PURE. Returns ``({latch_candidate_id: LatchOrderJoin}, alarms)``.

    `attribution` is the tuple `attribute_orders_to_latches` returned for this
    SAME `(latches, orders)` pair. `None` means "compute it internally", which
    is what every existing caller does and what keeps this signature change
    additive. When it IS supplied, only the `{order_id: latch}` MAP is taken
    from it -- never its ordering (see `attribute_orders_to_latches`).

    Passing it is how the fragment VM gets ONE `_match_latch` pass reaching
    both the alarms and the cancel-control render: a VM that re-derived the
    attribution would be a second pass that can disagree with this one, which
    is the property `indeterminate_order_tickers` already forbids for the
    sibling predicate.
    """
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
    if attribution is not None:
        # THE SUPPLIED ATTRIBUTION MUST BE *THIS* CALL'S, ON BOTH AXES, AND
        # NEITHER CHECK SUBSUMES THE OTHER (Codex R1 MAJOR). Validating only the
        # candidate ids accepts an attribution computed over a DIFFERENT ORDER
        # SET against the same latches, and the map is then wrong for orders it
        # never saw -- reproduced as the shared path emitting two alarms where
        # the internal path emitted none. Duplicate order ids are the same
        # failure one level down: two rows for one id silently collapse, and an
        # indeterminate row can overwrite a resting one's attribution.
        #
        # RAISE, NEVER DEGRADE. `None` in this map means "attributed to NO
        # latch", which is a LOAD-BEARING alarm input (it suppresses the
        # stale-order alarm while a live latch exists), so a wrong map MOVES AN
        # ALARM rather than merely losing information. The caller's A6 ladder
        # degrades a raise visibly; a silent divergence is invisible, and the
        # entire reason this parameter exists is that the two paths agree.
        expected_ids = [
            o.order_id for o in orders or ()
            if (o.instruction or "").upper() in BUY_INSTRUCTIONS
            and (o.is_resting or o.is_indeterminate)
        ]
        supplied_ids = [row.order_id for row in attribution]
        if len(set(supplied_ids)) != len(supplied_ids):
            raise ValueError(
                "attribution carries duplicate order ids, so one order's latch "
                "would silently overwrite another's")
        if set(supplied_ids) != set(expected_ids):
            raise ValueError(
                "attribution does not cover exactly this call's attributable "
                "BUY orders -- it was computed against a different order set")
        by_cid = {x.identity.candidate_id: x for x in latches}
        for row in attribution:
            if row.latch_candidate_id is None:
                matched[row.order_id] = None
                continue
            if row.latch_candidate_id not in by_cid:
                raise ValueError(
                    "attribution references candidate_id "
                    f"{row.latch_candidate_id}, which is not in this call's "
                    "latches -- it was computed against a different latch set")
            matched[row.order_id] = by_cid[row.latch_candidate_id]
    else:
        for ticker, ticker_orders in resting_by_ticker.items():
            for order in ticker_orders:
                matched[order.order_id] = _match_latch(
                    order, by_ticker.get(ticker, []))

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
                else _agrees(reference.limit_price, _mandate_limit_of(latch))),
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
        ticker_orders = resting_by_ticker.get(ticker, [])
        covering = [
            o for o in ticker_orders
            if _covers_mandate(o, latch, attributed=matched.get(o.order_id))
        ]
        if covering:
            continue
        # THE DETAIL MUST STAY TRUE IN BOTH CASES. "NO resting BUY order at the
        # broker" is a FACT about the order book and it is FALSE when orders
        # exist but none implements the mandate -- and an alarm that fires on a
        # true condition with a false explanation is the same defect the
        # presence/price ruling exists to remove. So the absence case keeps the
        # original wording (which the operator has been reading since 21-A) and
        # the shape case gets its own, naming what IS resting.
        #
        # AND THE CAP IS RENDERED THROUGH `_mandate_limit_of`, NOT `:.2f` ON THE
        # RAW CAP (operator witness, 2026-08-03). Round-half-up states a price
        # ABOVE the cap whenever the cap's third decimal is >= 5 -- this alarm
        # is the loudest thing on the panel and the number beside it is the one
        # the operator types at the broker, so it must be the number the
        # framework would order.
        if ticker_orders:
            detail = (
                f"latch armed at pivot {latch.latched_pivot:.2f} "
                f"(zone cap {_mandate_limit_of(latch):.2f}) with NO resting BUY "
                f"order IMPLEMENTING it; {len(ticker_orders)} resting BUY "
                f"order(s) on "
                f"{ticker} are the wrong shape (mandate: a GTC "
                f"{MANDATE_ORDER_TYPE_BREAKOUT} or {MANDATE_ORDER_TYPE_PULLBACK}"
                f"); expires {latch.horizon_expiry.isoformat()}")
        else:
            detail = (
                f"latch armed at pivot {latch.latched_pivot:.2f} "
                f"(zone cap {_mandate_limit_of(latch):.2f}) with NO resting BUY "
                f"order at the broker; expires "
                f"{latch.horizon_expiry.isoformat()}")
        alarms.append(OrderAlarm(
            kind="LATCH_ARMED_NO_RESTING_ORDER",
            ticker=ticker,
            latch_candidate_id=latch.identity.candidate_id,
            detail=detail,
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
                broker_order_id=order.order_id,
            ))

    return joins, tuple(alarms)
