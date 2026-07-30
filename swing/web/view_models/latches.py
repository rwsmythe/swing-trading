"""Phase 21 Arc A: the read-only latch panel view models.

A5: the panel gets its OWN VM and route -- no new field on `base.html.j2` or on
any existing base-layout VM (the every-base-VM-or-500 gotcha).

A6: EVERY builder path degrades visibly. `build_latch_panel_vm` never raises,
and that explicitly includes `_base_banner_fields`, which issues three DB reads
BEFORE the derivation guard would be reached (Codex R5-1).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, timedelta

from swing.evaluation.dates import PageKind, sessions_behind, topbar_session_date
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    CLOSE_PROVENANCE_FUTURE_STAMP,
    CLOSE_PROVENANCE_UNCORROBORATED,
    LATCH_PANEL_LOOKBACK_SESSIONS,
)
from swing.latches.models import Latch
from swing.latches.reader import (
    build_latch_derivation,
    count_session_recorded_closes,
    latest_recorded_close_stamp,
    load_last_closes,
)
from swing.web.view_models.journal import _base_banner_fields

_log = logging.getLogger(__name__)

_ZONE_POSITIONS = ("below_pivot", "in_zone", "above_zone", "unknown")

# Display precision on BOTH sides of the zone comparison, so a boundary price
# cannot flip the verdict on a sub-cent difference (the price-precision-parity
# gotcha).
_PRICE_DP = 2

# RD gate ruling G.5: V1 implements the close-below-the-fire-time-stop half of
# invalidation ONLY. The panel must NOT present itself as implementing full
# invalidation, so the qualifier travels WITH the number everywhere it is shown.
INVALIDATION_LABEL = "invalidation (stop level only)"
BASE_BREAK_FOOTNOTE = (
    "Invalidation is evaluated on closes below the fire-time stop level ONLY. "
    "Structural base-break is not implemented in V1."
)

# The all-fields-present fallback. Every key here is a base.html.j2 field: a
# MISSING key is a Jinja UndefinedError 500 on an unrelated banner, which is
# the very failure mode this is guarding against.
_SAFE_BANNER: dict = {
    "session_date": "", "stale_banner": None,
    "price_source_degraded": False, "price_source_degraded_until": None,
    "ohlcv_source_degraded": False,
    "unresolved_material_discrepancies_count": 0,
    "recent_multi_leg_auto_correction_count": 0,
    "banner_resolve_link": None,
}

_ZONE_LABELS = {
    "below_pivot": "below pivot - not triggered",
    "in_zone": "IN ZONE",
    "above_zone": "ABOVE ZONE - do not chase",
    "unknown": "price unavailable",
}

_TERMINAL_STATE_LABELS = {
    "filled": "FILLED",
    "invalidated": "INVALIDATED",
    "horizon_expired": "HORIZON EXPIRED",
}

_DEGRADED_REASON_LABELS = {
    "pivot_missing": "pivot missing on the fire's candidates row",
    "stop_missing": "initial stop missing on the fire's candidates row",
    "stop_not_below_pivot": "initial stop is not below the pivot",
    "bad_session_date": "the fire's action session date is malformed",
}


@dataclass(frozen=True)
class LatchRowVM:
    """One latch, rendered. Display-ready strings only -- NO logic in the
    template."""

    # identity + the FROZEN mandate (brief section 1.1)
    ticker: str
    fire_date: str
    latched_pivot: str
    zone_cap: str
    invalidation_level: str
    invalidation_label: str
    # LIVE price vs the buy zone (brief section 1.1 "current price vs zone")
    current_price: str
    zone_position: str
    zone_position_label: str
    price_source: str
    # THE DATE THE PANEL CAN PROVE, or "-" (Arc 21-G Task 6, RD OQ-3). It is
    # deliberately NOT the run stamp any more: a stamp is an UPPER BOUND on the
    # close's date, and handing a consumer an upper bound shaped like a per-row
    # date is exactly gotcha #30. A future consumer reading this field now gets
    # either a PROVEN date or nothing.
    price_asof: str
    # The display-ready claim rendered beside the price. NEW display-only field
    # on LatchRowVM ONLY -- LatchRowVM is not a base-layout VM, so the
    # every-base-VM-or-500 gotcha does not apply.
    price_asof_basis: str
    price_is_stale: bool
    # horizon + state
    sessions_to_horizon: int
    horizon_expiry: str
    state: str
    state_label: str
    clear_reason: str | None
    clear_session: str | None
    clear_trade_id: int | None
    fill_link_basis: str | None
    fill_link_anomaly: bool
    # provenance + honesty
    evaluation_run_id: int
    candidate_id: int
    detection_date: str
    pipeline_run_id: int | None
    reconfirmation_count: int
    bars_available: bool
    bars_through: str
    telemetry_label: str
    is_live: bool


@dataclass(frozen=True)
class DegradedRowVM:
    """Display shape for a DegradedFire (plan A.10): a fire whose own
    candidates row is unusable. Rendered as a visibly-degraded row so the
    operator sees that a fire EXISTED and why it produced no latch -- never
    silently dropped."""

    ticker: str
    fire_date: str
    evaluation_run_id: int
    candidate_id: int
    reason: str
    reason_label: str


@dataclass(frozen=True)
class LatchAlarmVM:
    kind: str
    ticker: str
    latch_candidate_id: int | None
    detail: str
    severity: str


@dataclass(frozen=True)
class LatchPanelVM:
    rows: tuple[LatchRowVM, ...]
    degraded_rows: tuple[DegradedRowVM, ...]
    available: bool
    unavailable_reason: str | None
    live_candidate_ids: tuple[int, ...]
    derivation_session: str
    horizon_session: str
    beacon_payload_json: str
    orders_payload_json: str
    base_break_footnote: str = BASE_BREAK_FOOTNOTE
    PAGE_KIND = PageKind.FORWARD_PLANNING

    # base-banner fields (populated via **_base_banner_fields):
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None


def _safe_base_banner_fields(conn, cfg) -> dict:
    """A6: `_base_banner_fields` issues THREE DB reads; any one of them raising
    would 500 `GET /latches` BEFORE the derivation guard is even reached."""
    try:
        return _base_banner_fields(conn, cfg)
    except Exception as exc:      # noqa: BLE001 -- A6: never 500 the panel
        _log.warning("latch panel base-banner degraded: %s", exc)
        return dict(_SAFE_BANNER)


def _fmt_price(value) -> str:
    return "-" if value is None else f"{float(value):.2f}"


def _zone_position(price, latch: Latch) -> str:
    """The buy zone is the CLOSED interval [latched_pivot, zone_cap], compared
    at display precision."""
    if price is None:
        return "unknown"
    p = round(float(price), _PRICE_DP)
    if p < round(latch.latched_pivot, _PRICE_DP):
        return "below_pivot"
    if p > round(latch.zone_cap, _PRICE_DP):
        return "above_zone"
    return "in_zone"


def _state_label(latch: Latch, zone_position: str) -> str:
    """Composes the state with the zone position (RD gate ruling, plan A.7.1).

    ZONE ESCAPE IS AN ATTRIBUTE OF `armed`, NEVER A TERMINAL STATE. The
    operator's resting order at the cap remains valid and fills on a pullback,
    "price will not come back" is unknowable, and the horizon already bounds
    the zombie case -- so the panel says "out of zone" WITHOUT the derivation
    having cleared anything.
    """
    if latch.state == "superseded":
        session = latch.clear_session.isoformat() if latch.clear_session else "-"
        return f"SUPERSEDED - re-fired at a new pivot {session}"
    if latch.state in _TERMINAL_STATE_LABELS:
        return _TERMINAL_STATE_LABELS[latch.state]
    base = "ORDER RESTING" if latch.state == "order_resting" else "ARMED"
    if zone_position == "above_zone":
        return (
            f"{base} - OUT OF ZONE (current price above the cap; fills only on "
            f"a pullback; expires {latch.horizon_expiry.isoformat()})")
    if zone_position == "in_zone":
        return f"{base} - IN ZONE"
    return base


def _telemetry_label(views) -> str:
    """The self-revealing echo (plan section D): a silently-broken beacon shows
    up as 'NOT YET RECORDED' on every visit."""
    if not views:
        return "view telemetry: NOT YET RECORDED THIS SESSION"
    first = views[0]
    total = sum(v.view_count for v in views)
    return f"first viewed {first.first_viewed_ts} ({total} views)"


def _price_asof_claim(quote, provenance) -> tuple[str, str]:
    """`(price_asof, price_asof_basis)` -- the DATE the card may claim.

    Arc 21-G Task 6 (RD's OQ-3 fold-in). `_build_row` used to render
    `quote[1]`, the RUN STAMP, as the price's own as-of date. The card already
    said `last_close` and `[STALE]` unconditionally, so it never claimed
    FRESHNESS -- what it claimed wrongly is the DATE:

        `a live instance of gotcha #30 sitting inside the fix for gotcha #30`

    It reuses the SAME classifier the fragment uses and the SAME archive map
    the derivation already surfaced, so it adds no read, no query and no DB
    field: `GET /latches` still writes nothing at all (A4).

    NO APOSTROPHES (Jinja autoescaping renders one as `&#39;`).
    """
    if quote is None or provenance is None:
        return "-", "as of -"
    session_iso = provenance.derivation_session.isoformat()
    stamp = provenance.stamp_session or "an unrecorded session"
    if provenance.may_assert:
        # PROVEN: the archive holds a bar dated exactly this session whose
        # close IS the recorded close.
        return session_iso, f"close dated {session_iso}"
    if provenance.provenance == CLOSE_PROVENANCE_FUTURE_STAMP:
        # TWO distinct rung-F shapes, keyed on the PARSED stamp rather than on
        # the raw string being non-empty (Codex R9 MINOR): 'not-a-date' is
        # non-empty but UNPLACEABLE, and calling it "later than" would state a
        # false reason for a correct degradation.
        if provenance.stamp_date is None:
            # THREE rung-F shapes, and the card must state the one it actually
            # holds (Codex R11 MINOR). `evaluation_runs.data_asof_date` is only
            # `TEXT NOT NULL` (migration 0001), so an EMPTY stamp is reachable
            # and is a different fact from an unparseable one -- rendering
            # "the unusable session stamp an unrecorded session" would name a
            # stamp that does not exist. The fragment already split these; the
            # card now matches it.
            if not provenance.stamp_session:
                return "-", ("close carries no session stamp, so it cannot be "
                             "placed in time")
            return "-", (f"close carries the unusable session stamp {stamp}, so "
                         f"it cannot be placed in time")
        return "-", (f"close stamped {stamp}, later than the session this page "
                     f"describes ({session_iso})")
    # Rung B: the stamp stated as the UPPER BOUND it actually is.
    return "-", f"close dated on or before {stamp}"


def _build_row(latch: Latch, *, quote, views, provenance=None) -> LatchRowVM:
    """`quote` is `(price, asof_iso)` from the READ-ONLY last-close source, or
    `None`. `provenance` is the `CloseProvenance` for that quote, or `None`.

    SCOPE BOUNDARY (RD, OQ-3): the provenance fixes the DATE the card claims.
    It does NOT re-gate `_zone_position` or the IN ZONE / OUT OF ZONE label --
    once the date is honest, "at the close dated X, this latch is in zone" is a
    TRUE statement. The zone label describes the price the card shows rather
    than asserting order coverage, so it is not a #30 instance once the date
    beside it stops overstating.
    """
    price = None if quote is None else quote[0]
    zone_position = _zone_position(price, latch)
    price_asof, price_asof_basis = _price_asof_claim(quote, provenance)
    return LatchRowVM(
        ticker=latch.identity.ticker,
        fire_date=latch.anchor.isoformat(),
        latched_pivot=_fmt_price(latch.latched_pivot),
        zone_cap=_fmt_price(latch.zone_cap),
        invalidation_level=_fmt_price(latch.latched_initial_stop),
        invalidation_label=INVALIDATION_LABEL,
        current_price=_fmt_price(price),
        zone_position=zone_position,
        zone_position_label=_ZONE_LABELS[zone_position],
        # ALWAYS `last_close` + stale on the GET: the panel deliberately does
        # NOT take a live quote, because fetching one would write an audit row
        # from a GET (A4). Rendering the provenance keeps that honest rather
        # than passing a possibly-days-old close off as a live quote.
        price_source="-" if quote is None else "last_close",
        price_asof=price_asof,
        price_asof_basis=price_asof_basis,
        price_is_stale=quote is not None,
        sessions_to_horizon=latch.sessions_to_horizon,
        horizon_expiry=latch.horizon_expiry.isoformat(),
        state=latch.state,
        state_label=_state_label(latch, zone_position),
        clear_reason=latch.clear_reason,
        clear_session=(
            None if latch.clear_session is None else latch.clear_session.isoformat()),
        clear_trade_id=latch.clear_trade_id,
        fill_link_basis=latch.fill_link_basis,
        fill_link_anomaly=latch.fill_link_anomaly,
        evaluation_run_id=latch.identity.evaluation_run_id,
        candidate_id=latch.identity.candidate_id,
        detection_date=latch.identity.detection_date,
        pipeline_run_id=latch.identity.pipeline_run_id,
        reconfirmation_count=latch.reconfirmation_count,
        bars_available=latch.bars_available,
        bars_through=(
            "-" if latch.bars_through is None else latch.bars_through.isoformat()),
        telemetry_label=_telemetry_label(views),
        is_live=latch.is_live,
    )


def _within_display_lookback(latch: Latch, horizon_session: date) -> bool:
    """The DISPLAY filter only. The derivation always folds EVERY fire, so the
    re-confirmation chain is never truncated -- only the render is bounded."""
    if latch.is_live:
        return True
    reference = latch.clear_session or latch.anchor
    return sessions_behind(horizon_session, reference) <= LATCH_PANEL_LOOKBACK_SESSIONS


def _now() -> datetime:
    """Indirection so tests can freeze the panel clock at ONE place."""
    return datetime.now()


def _empty_panel(banner: dict, *, reason: str | None, session_date: str) -> LatchPanelVM:
    payload = json.dumps({"view_session_date": "", "candidate_ids": ""})
    banner = dict(banner)
    banner["session_date"] = session_date
    return LatchPanelVM(
        rows=(), degraded_rows=(), available=reason is None,
        unavailable_reason=reason, live_candidate_ids=(),
        derivation_session="-", horizon_session="-",
        beacon_payload_json=payload,
        orders_payload_json=json.dumps({"view_session_date": ""}),
        **banner)


def build_latch_panel_vm(conn, cfg, *, now=None) -> LatchPanelVM:
    """Build the panel VM. NEVER raises, NEVER writes (A4 + A6).

    THE NO-WRITE PROPERTY IS STRUCTURAL: this builder takes NO price cache and
    NO executor, so there is nothing here that could dispatch a live fetch.
    `PriceCache.get_many` looks read-only but a cache MISS submits
    `_fetch_with_fallback` to the executor, which routes the Schwab ->
    yfinance ladder and writes `schwab_api_calls` / `yfinance_calls` audit
    rows -- i.e. a GET that writes. The current price is instead the most
    recent persisted `candidates.close` (a pure SELECT), rendered with its
    provenance so it can never be mistaken for a live quote.
    """
    banner = _safe_base_banner_fields(conn, cfg)
    clock = now or _now()
    # PAGE_KIND is FORWARD_PLANNING but `_base_banner_fields` hardcodes the
    # HISTORY_ANALYSIS anchor, so the spread value is OVERRIDDEN here to keep
    # the rendered topbar honest.
    session_date = topbar_session_date(PageKind.FORWARD_PLANNING, clock).isoformat()
    try:
        derivation = build_latch_derivation(conn, cfg, now=clock)
        displayed = [
            latch for latch in derivation.latches
            if _within_display_lookback(latch, derivation.horizon_session)
        ]
        live = [latch for latch in displayed if latch.is_live]

        quotes: dict = {}
        if live:
            try:
                quotes = load_last_closes(
                    conn, sorted({latch.identity.ticker for latch in live}))
            except Exception as exc:  # noqa: BLE001 -- A6: a price miss never blocks
                _log.warning("latch panel last-close read degraded: %s", exc)
                quotes = {}

        views_by_latch = _load_views(conn, displayed, derivation.horizon_session)

        # The SAME pure classifier the fragment uses, over the SAME archive map
        # the derivation already surfaced -- no new read, no new query, no new
        # DB field, so the panel GET stays a pure reader (A4).
        from swing.latches.orders import classify_close_provenance

        def _prov(latch: Latch, quote):
            return classify_close_provenance(
                quote=quote,
                derivation_session=derivation.derivation_session,
                bars_through=latch.bars_through,
                archive_closes=derivation.archive_closes.get(
                    latch.identity.ticker, {}),
                archive_status=derivation.archive_status.get(
                    latch.identity.ticker, ARCHIVE_STATUS_OK),
            )

        def _row(latch: Latch) -> LatchRowVM:
            quote = quotes.get(latch.identity.ticker) if latch.is_live else None
            return _build_row(
                latch, quote=quote,
                views=views_by_latch.get(latch.identity.candidate_id, ()),
                provenance=None if quote is None else _prov(latch, quote),
            )

        rows = [
            _row(latch)
            for latch in sorted(
                displayed,
                key=lambda x: (not x.is_live, -x.anchor.toordinal(),
                               x.identity.ticker),
            )
        ]
        degraded_rows = tuple(
            DegradedRowVM(
                ticker=d.ticker,
                fire_date=d.action_session_date or "-",
                evaluation_run_id=d.evaluation_run_id,
                candidate_id=d.candidate_id,
                reason=d.reason,
                reason_label=_DEGRADED_REASON_LABELS.get(d.reason, d.reason),
            )
            for d in derivation.degraded
        )
        live_ids = tuple(latch.identity.candidate_id for latch in live)
        payload = json.dumps({
            "view_session_date": derivation.horizon_session.isoformat(),
            "candidate_ids": ",".join(str(i) for i in live_ids),
        })
        banner = dict(banner)
        banner["session_date"] = session_date
        return LatchPanelVM(
            rows=tuple(rows),
            degraded_rows=degraded_rows,
            available=True,
            unavailable_reason=None,
            live_candidate_ids=live_ids,
            derivation_session=derivation.derivation_session.isoformat(),
            horizon_session=derivation.horizon_session.isoformat(),
            beacon_payload_json=payload,
            orders_payload_json=json.dumps({
                "view_session_date": derivation.horizon_session.isoformat()}),
            **banner,
        )
    except Exception as exc:  # noqa: BLE001 -- A6: the panel degrades, never 500s
        _log.warning("latch panel degraded: %s", exc)
        return _empty_panel(
            banner, reason="latch derivation unavailable", session_date=session_date)


def _load_views(
    conn, latches, horizon_session: date, *,
    counted_surfaces: frozenset[str] | None = None,
) -> dict[int, tuple]:
    """The persisted view telemetry for THIS session, per latch. Read-only.

    `counted_surfaces` is EXPLICIT (21-B, plan section E.3 conjunct 2): the
    moment 21-F adds a second surface, a non-panel row must not silently satisfy
    the panel's "viewed" predicate and move a disposition. `None` here means
    "the measurement default", which is `ACTIONABLE_VIEW_SURFACES` -- callers
    that want a raw read say so.
    """
    from swing.latches.constants import ACTIONABLE_VIEW_SURFACES
    if counted_surfaces is None:
        counted_surfaces = ACTIONABLE_VIEW_SURFACES
    out: dict[int, tuple] = {}
    try:
        from swing.data.repos.latch_view_events import list_views_for_latch
    except Exception as exc:  # noqa: BLE001 -- pre-0032 DB: no telemetry, no 500
        _log.warning("latch panel telemetry read unavailable: %s", exc)
        return out
    session_iso = horizon_session.isoformat()
    for latch in latches:
        try:
            rows = list_views_for_latch(
                conn, candidate_id=latch.identity.candidate_id,
                surfaces=counted_surfaces)
        except Exception as exc:  # noqa: BLE001 -- A6
            _log.warning("latch panel telemetry read degraded: %s", exc)
            continue
        out[latch.identity.candidate_id] = tuple(
            r for r in rows if r.view_session_date == session_iso)
    return out


# ---------------------------------------------------------------------------
# The lazy broker-order-awareness fragment (plan D.1 / Task 7).
#
# The ladder below REPRODUCES the shipped `swing/trades/entry_auto_fill.py`
# sequence BY CONSTRUCTION, not by import -- this arc takes NO `swing/trades`
# dependency and makes NO `swing/trades` edit.
# ---------------------------------------------------------------------------

# The FLOOR for the Schwab order-read lookback, in CALENDAR days.
#
# The real lower bound is DERIVED from the oldest latch anchor on the page --
# NOT a constant. `get_account_orders` filters on ENTERED TIME, and a GTC entry
# order is entered on the FIRE date, so the window must reach back to the oldest
# latch this page can display. A fixed 30 CALENDAR days is shorter than a
# 30-SESSION horizon (30 sessions is ~42 calendar days: FTRE fires 2026-07-20
# and expires 2026-08-31), so late in a mandate's life the order that satisfies
# it would drop out of the query -- firing a FALSE
# LATCH_ARMED_NO_RESTING_ORDER, and silencing a genuine stale-order alarm.
_ORDER_LOOKBACK_FLOOR_DAYS = 30
# A hard ceiling so a pathological anchor cannot ask Schwab for years of orders.
_ORDER_LOOKBACK_MAX_DAYS = 400
# Slack beyond the oldest anchor for an order entered just before the fire.
_ORDER_LOOKBACK_BUFFER_DAYS = 7


@dataclass(frozen=True)
class OrdersResolutionVM:
    kind: str
    detail: str


@dataclass(frozen=True)
class MandateFormCheckVM:
    """One latch whose mandate-FORM check could not run, with the TONE its
    reason earns (RD ruling 2026-07-28).

    ONE rendering path, three severities -- the reduction stays visible in every
    branch (the CHARC ruling-4 concurrence), but the operator's correct response
    differs per branch and so must the wording:

      `pending`   -- NO closes at all have been recorded for the derivation
                     session yet, so nobody has a regime price.
                     The response is to WAIT, and the label says when it clears.
                     THIS IS THE DEFAULT STATE, not an exception: the action
                     session rolls over AT the market close (10:00-10:30 HST)
                     and the nightly pipeline writes the new session at 17:30
                     HST, so for ~7 hours of every trading day -- the operator's
                     whole post-close review window -- NO latch has a
                     derivation-session close. A warning-shaped label on a
                     state that occurs daily on every latch trains the dismissal
                     reflex, which is exactly how the Phase-19 drumbeat false-RED
                     became expensive, and this is the one surface whose alarms
                     have to survive being believed. So: neutral status, no alarm
                     prefix, no alarm styling.
      `permanent` -- closes DATED that session have been recorded and this
                     ticker's most recent usable close is still older, so it is
                     a question about the TICKER, not about the clock. (DATED,
                     not proven-from: `data_asof_date` is a run-level stamp --
                     see `count_session_recorded_closes`.)
                     The label keeps the warning tone
                     and states the count it is reasoning from, so an unusual
                     number (an ad-hoc same-date `swing eval` rather than the
                     nightly) is VISIBLE rather than silently deciding the
                     branch -- the Codex y1 MAJOR-2 residue.
      `unknown`   -- the close read failed, or the recorded-close count could
                     not be read. The panel promises neither direction.
    """

    ticker: str
    severity: str
    headline: str
    detail: str


_FORM_CHECK_HEADLINES = {
    # Sentence case + no box for `pending`: the prefix itself must not be
    # alarm-shaped on the state that renders every evening.
    "pending": "Mandate form check pending",
    "permanent": "MANDATE FORM CHECK INERT FOR THIS LATCH",
    "unknown": "MANDATE FORM CHECK NOT RUN",
    # --- Arc 21-G ----------------------------------------------------------
    # NEUTRAL, and for the same reason `pending` is: this renders on every live
    # latch for ~7 hours of every trading day, and a warning-shaped label on a
    # daily state trains the dismissal reflex.
    "stale_regime": "Mandate form check ran from an uncorroborated close",
    # WARNING tone: both report a real, actionable inconsistency in the
    # operator's own data rather than a routine wait.
    "value_conflict": "RECORDED CLOSE CONTRADICTED BY THE ARCHIVE",
    # TWO headlines for the ONE rung, because the rung holds two DIFFERENT
    # facts and the headline is the bold text the operator reads first (Codex
    # R10 MINOR). A detail that says "cannot be placed in time" under a
    # headline that says "stamped after this page session" is a false reason
    # rendered more prominently than the true one.
    "future_stamp": "RECORDED CLOSE IS STAMPED AFTER THIS PAGE SESSION",
    "unplaceable_stamp": "RECORDED CLOSE CANNOT BE PLACED IN TIME",
}

# The severities that render as neutral STATUS rather than as a warning. Kept
# beside the headlines so the tone and the wording cannot drift apart; the
# template mirrors this set (no new CSS token, so the theme no-raw-hex /
# token-contract test is untouched).
NEUTRAL_FORM_CHECK_SEVERITIES = frozenset({"pending", "stale_regime"})

# The PAGE-LEVEL claim each form-check severity contributes (Arc 21-B B6 x Arc
# 21-G), kept beside the headlines for the same reason the neutral set is: the
# per-latch label and the page-level claim must not drift apart.
#
# B6 SEPARATES the claims -- the alarm all-clear is COMPLETE and unscoped, and
# each form-check reduction states its OWN severity rather than being lumped
# into one undifferentiated "not form-checked" count. 21-G's severities join
# that list as FURTHER CLAIMS rather than as a competing sentence: "the check
# ran from a close whose date could not be proved" is a DIFFERENT fact from
# "the check did not run" (there, the check DID run -- its input could not be
# dated), so under the separated construction it is simply another claim.
#
# ORDERED, and `stale_regime` LEADS THE REDUCTIONS: it is the claim that says
# no all-clear is asserted, and Codex R7 (21-G) ruled the reduction must not
# sit behind the reassurance. "No alarms." still leads the whole line, because
# under the SEPARATED construction it is COMPLETE -- skimming it yields a TRUE
# belief, which is exactly what the superseded SCOPED sentence could not offer
# and is why RD ruled the separated form its REPLACEMENT.
#
# EVERY severity in `_FORM_CHECK_HEADLINES` MUST appear here: an unlabelled
# reduction is a quiet all-clear by omission, and a severity that silently
# fails to reach the page-level line is precisely that. A test pins the two
# key sets equal (the #11 mirror discipline), so a new severity cannot ship
# green while being dropped from the line.
_FORM_CHECK_CLAIM_PHRASINGS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("stale_regime",),
     "{n} {noun} checked from an uncorroborated close - no all-clear is "
     "asserted for those."),
    (("value_conflict",),
     "Mandate-form check inert for {n} {noun} - the recorded close is "
     "contradicted by the archive; see the labels below."),
    # ONE claim for the ONE rung: `future_stamp` and `unplaceable_stamp` are
    # two HEADLINES over the same rung F (a stamp AFTER this session, or a
    # stamp that cannot be parsed at all -- two different reasons, and the
    # per-latch label states which). The page-level fact they share is the one
    # that matters here: the close cannot be placed at or before this page's
    # session, so no form was picked from it.
    (("future_stamp", "unplaceable_stamp"),
     "Mandate-form check inert for {n} {noun} - the recorded close cannot be "
     "placed in time; see the labels below."),
    (("pending",), "Mandate-form check pending for {n} {noun}."),
    (("permanent",),
     "Mandate-form check inert for {n} {noun} - see the labels below."),
    (("unknown",), "Mandate-form check status unknown for {n} {noun}."),
)


def _as_sentence(text: str) -> str:
    """Upper-case the FIRST character only.

    NOT `str.capitalize()`, which lower-cases everything after it -- it would
    turn `GOOD_TILL_CANCEL` into `good_till_cancel` and `STOP_LIMIT` into
    `stop_limit` inside a label whose whole job is to name broker enum values
    exactly as the broker does.
    """
    return text[:1].upper() + text[1:]


def _uncorroborated_suffix(prov) -> str:
    """The provenance clause carried by EVERY B-continuity disagreement line.

    ONE helper, so the wording cannot drift between the leg lines and the
    shape lines. It names the close's PROVEN date (the archive corroborated the
    recorded close at that date) and the derivation session the archive holds
    nothing for, which is exactly the claim the alarm rests on -- and exactly
    the qualification that keeps it from over-claiming in the other direction.

    NO APOSTROPHES: Jinja autoescaping renders one as `&#39;`, which is correct
    HTML but silently breaks text assertions and operator search.
    """
    stamp = prov.stamp_session or "an unrecorded session"
    return (f" [read from a close dated {stamp}, corroborated by the archive "
            f"bar dated {stamp}; the archive holds no bar for the derivation "
            f"session {prov.derivation_session.isoformat()}, so this is a "
            f"labelled finding and not an all-clear]")


def _close_provenance(quote) -> str:
    """What the operator's data actually says about this ticker's last close.

    `load_last_closes` skips a non-numeric / non-finite close, so "no close is
    recorded" would be a false statement about his data when a malformed one
    exists -- hence "no USABLE close" (Codex R3 MINOR).
    """
    if quote is None:
        return "no usable close is recorded for this ticker"
    return ("the most recent usable close for this ticker is from "
            f"{quote[1] or 'an unrecorded session'}")


@dataclass(frozen=True)
class LatchOrdersFragmentVM:
    """The order-awareness fragment. `available` False means the order book is
    UNKNOWN, and an unknown order book fires NO alarm (a false all-clear and a
    false alarm are both worse than an honest 'unknown')."""

    available: bool
    resolution_kind: str
    resolution_detail: str
    alarms: tuple[LatchAlarmVM, ...]
    order_lines: tuple[str, ...]
    # A live latch whose only resting order is MISPRICED. Not one of the two
    # named alarms (plan A.9 routes it through the agreement flags), but it MUST
    # be rendered: silence here reads as "covered" when it is not.
    disagreements: tuple[str, ...] = ()
    # Tickers with a live latch whose broker order state is INDETERMINATE
    # (PENDING_CANCEL / UNKNOWN / ...). Alarms are correctly suppressed for
    # these -- a false all-clear and a false alarm are both worse than an
    # honest "unknown" -- but the UNKNOWN must be RENDERED, or the suppression
    # itself reads as an all-clear.
    indeterminate_tickers: tuple[str, ...] = ()
    # Latches carrying MORE THAN ONE matched resting order (RD ruling
    # 2026-07-27). The agreement flags describe a SINGLE reference order, so
    # over a matched set the affirmative agree is WITHHELD and the multiplicity
    # is stated instead. Deliberately a COUNT plus a directive: 21-A does NOT
    # report per-order legs, per-order agreement, or per-order alarms.
    multiplicity_notes: tuple[str, ...] = ()
    # Live latches whose mandate REGIME could not be determined, so the two-form
    # order-shape check did not run (RD ruling 2026-07-27). Accepting either
    # form is the right conservative behaviour, but it is a real reduction in
    # what the panel is asserting, and an UNLABELLED reduction is a quiet
    # all-clear by omission. It is also where a latched ticker that has dropped
    # off the screen lands (RD ruling 3): permanently inert, and therefore
    # required to be VISIBLY inert rather than silently inert. That is the
    # MOTIVATING case, NOT a fact the code can establish -- nothing here can see
    # finviz-screen membership (Codex y1 MAJOR 1), so the label names it as the
    # usual cause and never asserts it.
    #
    # Carries a per-branch SEVERITY (RD ruling 2026-07-28): see
    # `MandateFormCheckVM`. Still ONE rendering path -- only the tone differs.
    mandate_form_check_skipped: tuple[MandateFormCheckVM, ...] = ()
    # How many live latches the mandate-FORM check DID run on. Pairs with
    # `len(mandate_form_check_skipped)` to state the page-level all-clear WITH
    # its scope instead of withholding it outright (RD ruling 2026-07-28): the
    # not-run label is the default state for ~7 hours of every trading day, so
    # blanket withholding means the operator essentially never sees an
    # all-clear, and a sentence that is usually absent stops being informative
    # by its absence. The display-ready sentence is `all_clear_note`.
    form_check_ran_count: int = 0
    # Arc 21-G: how many live latches were checked from an UNCORROBORATED close
    # (B-continuity). Deliberately NARROW -- only the sub-rung that was actually
    # alarm-authorized is counted. B-persistent / B-unknown / B-undated are
    # indistinguishable from rung C in what the page can claim, and counting
    # them here would imply a check ran that did not.
    form_check_stale_count: int = 0

    @property
    def all_clear_claims(self) -> tuple[str, ...]:
        """THE SEPARATED-CLAIMS CONSTRUCTION (B6, Arc 21-B).

        The superseded single SCOPED sentence -- *"No alarms among the {N}
        {latch|latches} form-checked. {M} not form-checked - see the labels
        below."* -- was wrong for TWO reasons, and RD named both:

        1. IT RESTED ON A MISUNDERSTANDING. Only the two-form SELECTION is
           skipped: alarms, the cap leg, GTC duration and the stray-order sweep
           all RUN on every latch. So the ALARM all-clear is not scoped at all --
           it is COMPLETE. Re-verified on disk before adopting the change: on the
           no-findings branch (the ONLY branch that reaches this property) there
           are no alarms, no disagreements, no indeterminate tickers and no
           multiplicity notes, and `join_orders_to_latches` ran over
           `derivation.latches` UNCONDITIONALLY. Every latch WAS alarm-checked.
        2. IT PRODUCES A VACUOUS ZERO-CASE. In the ~7-hour window when
           `form_check_ran_count == 0` it reads *"No alarms among the 0 latches
           form-checked."* -- a claim about an empty set, dressed as a result.

        So the claims are SEPARATED, each independently true and none vacuous.
        THE PENDING-VS-PERMANENT DISTINCTION IS CARRIED INTO THE PAGE-LEVEL LINE,
        which is the actual B6 refinement: today it is visible only in the
        per-latch labels, so the page-level sentence LUMPS a self-resolving wait
        together with a permanently-inert latch.

        `form_check_ran_count` stays on the VM (the CLI report and the tests read
        it) but no longer appears in the prose -- the operator does not need a
        DENOMINATOR for a claim that is not SCOPED.

        ARC 21-G COMPOSES INTO THIS, IT IS NOT REPLACED BY IT. 21-G's scoped
        sentence led with `"{M} latches checked from an uncorroborated close -
        no all-clear is asserted for those."` The STRUCTURE it was written into
        is what RD retired; the FACT it carries is real provenance work and
        survives as a claim of its own, because "the check ran from a close
        whose date could not be proved" is a DIFFERENT statement from "the
        check did not run". Under the separated construction the two simply
        coexist. See `_FORM_CHECK_CLAIM_PHRASINGS` for the full roster and the
        ordering rationale.
        """
        by_severity: dict[str, int] = {}
        for note in self.mandate_form_check_skipped:
            by_severity[note.severity] = by_severity.get(note.severity, 0) + 1
        claims = ["No alarms."]        # ALWAYS, on this branch: unscoped
        for severities, phrasing in _FORM_CHECK_CLAIM_PHRASINGS:
            n = sum(by_severity.get(s, 0) for s in severities)
            if n:
                claims.append(phrasing.format(
                    n=n, noun="latch" if n == 1 else "latches"))
        return tuple(claims)

    @property
    def all_clear_note(self) -> str:
        """The separated claims, joined for display. The template holds no logic.

        Reachable ONLY from the template's no-findings branch: a disagreement /
        indeterminate status / multiplicity is a FINDING, not an absent check, and
        still withholds every form of all-clear.
        """
        return " ".join(self.all_clear_claims)


def _resolve_schwab_environment(cfg) -> str | None:
    schwab_cfg = getattr(getattr(cfg, "integrations", None), "schwab", None)
    return getattr(schwab_cfg, "environment", None)


def _resolve_account_hash(cfg) -> str | None:
    schwab_cfg = getattr(getattr(cfg, "integrations", None), "schwab", None)
    value = getattr(schwab_cfg, "account_hash", None)
    return value if isinstance(value, str) and value else None


def _fetch_account_orders(client, conn, account_hash, from_dt, to_dt, **kwargs):
    """The single audited seam, isolated so tests can stub it without stubbing
    the whole Schwab package."""
    from swing.integrations.schwab import trader
    return trader.get_account_orders(
        client, conn, account_hash, from_dt, to_dt, **kwargs)


def _order_lookback_days(latches, *, now: datetime) -> int:
    """Calendar days back to query, derived from the OLDEST latch anchor."""
    anchors = [lat.anchor for lat in latches or ()]
    if not anchors:
        return _ORDER_LOOKBACK_FLOOR_DAYS
    span = (now.date() - min(anchors)).days + _ORDER_LOOKBACK_BUFFER_DAYS
    return max(_ORDER_LOOKBACK_FLOOR_DAYS, min(span, _ORDER_LOOKBACK_MAX_DAYS))


def resolve_open_orders(conn, cfg, app_state, *, latches=()):
    """Resolve the LIVE broker order book, or say honestly why we cannot.

    Returns `(OrdersResolutionVM, orders)`. The sandbox short-circuit fires
    FIRST -- BEFORE any client borrow -- so the sandbox path is provably
    side-effect-free (the Schwab sandbox-gating gotcha).

    `latches` only sizes the entered-time query window (see
    `_order_lookback_days`); it is not otherwise consulted here.
    """
    from swing.latches.orders import to_resting_orders

    environment = _resolve_schwab_environment(cfg)
    if environment == "sandbox":
        return OrdersResolutionVM(
            kind="sandbox",
            detail=("Schwab integration is in sandbox mode; the live order "
                    "book was NOT read. Order alarms are suppressed."),
        ), ()
    if environment != "production":
        return OrdersResolutionVM(
            kind="not_configured",
            detail=("Schwab integration is not configured "
                    "(cfg.integrations.schwab.environment missing or invalid); "
                    "the order book is unavailable. Alarms are suppressed."),
        ), ()

    holder = getattr(app_state, "schwab_client_holder", None)
    if holder is None:
        return OrdersResolutionVM(
            kind="unavailable",
            detail=("No Schwab client is installed on this web process; the "
                    "order book is unavailable. Alarms are suppressed."),
        ), ()

    account_hash = _resolve_account_hash(cfg)
    if account_hash is None:
        return OrdersResolutionVM(
            kind="unavailable",
            detail=("Schwab account_hash is not set (run `swing schwab setup`); "
                    "the order book is unavailable. Alarms are suppressed."),
        ), ()

    # UTC-AWARE, deliberately. `trader._schwab_iso` converts an AWARE datetime
    # to UTC but passes a NAIVE one through UNCHANGED and stamps 'Z' on it -- so
    # a naive local `datetime.now()` is transmitted as if it were UTC. On this
    # HST deployment that is a TEN-HOUR skew: `to_entered_time` lands ten hours
    # in the past and the query silently omits orders entered earlier the same
    # day, firing a FALSE LATCH_ARMED_NO_RESTING_ORDER for an order the operator
    # actually placed that morning. Matches the convention every other Schwab
    # caller already uses (entry_auto_fill / exit_auto_fill both use
    # `datetime.now(UTC)`).
    now = datetime.now(UTC)
    try:
        with holder.borrow() as client:
            if client is None:
                return OrdersResolutionVM(
                    kind="unavailable",
                    detail=("The Schwab client is being re-constructed; the "
                            "order book is unavailable. Alarms are suppressed."),
                ), ()
            raw = _fetch_account_orders(
                client, conn, account_hash,
                now - timedelta(days=_order_lookback_days(latches, now=now)), now,
                surface="trade_entry",
                environment=environment,
                pipeline_run_id=None,
                status=None,
                max_results=None,
            )
    except Exception as exc:  # noqa: BLE001 -- A6: the panel never 500s
        # The exception TYPE only, NEVER the message (redaction discipline).
        return OrdersResolutionVM(
            kind="error",
            detail=(f"The Schwab order read failed ({type(exc).__name__}); the "
                    "order book is unavailable. Alarms are suppressed."),
        ), ()
    return OrdersResolutionVM(
        kind="ok", detail="Live broker order book read."), to_resting_orders(raw)


def build_latch_orders_vm(
    conn, cfg, app_state, *, horizon_session_override=None,
) -> LatchOrdersFragmentVM:
    """Build the order-awareness fragment VM. NEVER raises (A6).

    `horizon_session_override` is the RENDER-TIME anchor the panel posted. It
    is REQUIRED: without it the fragment would derive at its own `now`, so
    after a session rollover (or a restored page) it could render alarms for
    session S+1 while the visible latch cards still describe S -- the panel
    contradicting itself about which mandates are live. When the anchor is
    absent or unusable the fragment degrades and SUPPRESSES alarms, which is
    the safe direction: a false all-clear is the failure mode this arc exists
    to prevent.
    """
    from swing.latches.constants import (
        MANDATE_ORDER_TYPE_BREAKOUT,
        MANDATE_ORDER_TYPE_PULLBACK,
    )
    from swing.latches.orders import (
        classify_close_provenance,
        expected_mandate_order_type,
        indeterminate_order_tickers,
        join_orders_to_latches,
        mandate_shape_mismatch,
    )

    if horizon_session_override is None:
        return LatchOrdersFragmentVM(
            available=False, resolution_kind="stale_anchor",
            resolution_detail=(
                "This page's session anchor is missing or stale, so broker "
                "orders were not joined to it. Reload to check your orders."),
            alarms=(), order_lines=())

    # DERIVE FIRST. The latches size the broker query window: `get_account_orders`
    # filters on ENTERED TIME, so the window must reach back to the OLDEST latch
    # on the page or the very order that satisfies a long-running mandate falls
    # out of the result and fires a FALSE "no resting order" alarm.
    try:
        derivation = build_latch_derivation(
            conn, cfg, horizon_session_override=horizon_session_override)
    except Exception as exc:  # noqa: BLE001 -- A6
        _log.warning("latch order derivation degraded: %s", exc)
        return LatchOrdersFragmentVM(
            available=False, resolution_kind="error",
            resolution_detail=(
                f"The latch derivation failed ({type(exc).__name__}); alarms "
                "are suppressed."),
            alarms=(), order_lines=())

    try:
        resolution, orders = resolve_open_orders(
            conn, cfg, app_state, latches=derivation.latches)
    except Exception as exc:  # noqa: BLE001 -- A6
        _log.warning("latch order resolution degraded: %s", exc)
        resolution, orders = OrdersResolutionVM(
            kind="error",
            detail=(f"The Schwab order read failed ({type(exc).__name__}); "
                    "alarms are suppressed."),
        ), ()

    if resolution.kind != "ok":
        # An UNKNOWN order book fires NOTHING.
        return LatchOrdersFragmentVM(
            available=False, resolution_kind=resolution.kind,
            resolution_detail=resolution.detail, alarms=(), order_lines=())

    try:
        joins, alarms = join_orders_to_latches(
            latches=derivation.latches, orders=orders)
    except Exception as exc:  # noqa: BLE001 -- A6
        _log.warning("latch order join degraded: %s", exc)
        return LatchOrdersFragmentVM(
            available=False, resolution_kind="error",
            resolution_detail=(
                f"The latch/order join failed ({type(exc).__name__}); alarms "
                "are suppressed."),
            alarms=(), order_lines=())

    # PRICE DISAGREEMENTS ARE RENDERED, NOT SWALLOWED (Codex executing R2).
    # `LATCH_ARMED_NO_RESTING_ORDER` is deliberately keyed on TICKER-LEVEL
    # absence (plan A.9) so a mispriced order does not produce a factually
    # false "no order" alarm -- but that means a wrong-price order SILENCES the
    # alarm. If the disagreement is then discarded, the fragment renders "orders
    # agree" over a mandate that is NOT actually covered: a false all-clear,
    # which is the exact failure mode this arc exists to prevent.
    def _agreement_word(flag) -> str:
        # `None` is UNKNOWN, and unknown is NOT agreement. A plain BUY STOP at
        # the pivot carries no limit leg, so `order_limit_agrees` is None -- but
        # the mandate is a stop trigger AND a cap, and it is the cap that stops
        # the operator chasing. Reading that silence as agreement is a false
        # all-clear.
        if flag is True:
            return "agrees"
        return "DISAGREES" if flag is False else "UNKNOWN (leg absent)"

    # THE MANDATE-SHAPE REGIME PRICE. Which of the two mandated instruments is
    # correct depends on where price sits relative to the latched pivot, so the
    # shape check needs a price. It is the SAME price the panel cards render --
    # the most recent persisted `candidates.close` via `load_last_closes`, a
    # PURE SELECT -- so the operator never sees the fragment judging his order
    # against a number the page does not show. A read failure leaves the regime
    # UNKNOWN, which accepts either form (A6: degrade, never false-alarm).
    #
    # IT IS PROVENANCE-SCOPED (Arc 21-G; 21-A's session gate COMPLETED, not
    # reversed). `load_last_closes` returns the GLOBALLY latest close per ticker
    # no matter how old it is, and the session it returns is only the RUN STAMP
    # -- an UPPER BOUND on the close's own date, because the evaluator stamps
    # the COHORT MAX bar date while each `candidates.close` comes from that
    # ticker's OWN last bar (gotcha #30). 21-A gated both directions on that
    # stamp because nothing could date a close per row; `classify_close_provenance`
    # now can, using the on-disk archive the derivation already loads, so the
    # single knob SPLITS along RD's rule:
    #
    #   ASSERT a match  -- rung A only: a bar dated EXACTLY the derivation
    #                      session whose close IS the recorded close.
    #   ALARM a mismatch-- permitted from a STALE close, but only when the
    #                      staleness is CHARACTERISABLE (its date is PROVEN at
    #                      its own stamp, never inferred from the stamp) and
    #                      SELF-LIMITING (the whole system is no fresher than
    #                      this ticker, so the gap ends at the next nightly).
    #
    # The archive DATES the persisted close; it never REPLACES it. The number
    # judged is still the number the cards render (21-A shown-equals-judged).
    regime_session_iso = derivation.derivation_session.isoformat()
    regime_closes: dict = {}
    # A FAILED read is NOT an absent close (Codex R1 MINOR). Both collapse to an
    # empty `regime_closes`, so without this flag the skipped-shape label would
    # tell the operator "no close is recorded for this ticker" -- a claim about
    # his DATA that is false when the read simply blew up.
    regime_price_read_failed = False
    regime_tickers = sorted({
        lat.identity.ticker for lat in derivation.latches if lat.is_live})
    if regime_tickers:
        try:
            regime_closes = load_last_closes(conn, regime_tickers)
        except Exception as exc:  # noqa: BLE001 -- A6: a price miss never blocks
            _log.warning("latch order regime price read degraded: %s", exc)
            regime_closes = {}
            regime_price_read_failed = True

    # The SELF-LIMITING half of the alarm gate (plan B.2.1 condition 2), read
    # LAZILY and at most ONCE per fragment build -- never per latch, and never
    # at all when every live latch reached rung A. Wrapped in the A6 ladder: an
    # unreadable `L` WITHDRAWS alarm authority (permission is not obligation)
    # rather than granting it by default, and it does NOT change the label --
    # that is `count_session_recorded_closes`'s job, and the two reads answer
    # different questions (Codex R7 MINOR).
    _stamp_read: dict = {}

    def _latest_stamp() -> str | None:
        if "value" not in _stamp_read:
            _stamp_read["failed"] = False
            try:
                _stamp_read["value"] = latest_recorded_close_stamp(conn)
            except Exception as exc:  # noqa: BLE001 -- A6: the panel never 500s
                _log.warning("latch order latest-close-stamp read degraded: %s", exc)
                _stamp_read["value"] = None
                # A FAILED read is NOT "the system has no usable close" -- the
                # same distinction the archive status makes, for the same
                # reason. Carried so the withheld alarm can say WHY it was
                # withheld (codex-auto-review MAJOR); without it the operator
                # sees the routine waiting label over a real suppressed finding.
                _stamp_read["failed"] = True
        return _stamp_read["value"]

    disagreement_lines: list[str] = []
    multiplicity_lines: list[str] = []
    # (ticker, quote, tail, provenance, note_reason) per latch whose FORM check
    # was not ASSERTIVE. EXACTLY ONE list, so the counts and the labels cannot
    # fork (Codex R3 MINOR): a latch is appended here whenever `assertive` is
    # False, B-continuity included. The pending-vs-permanent classification
    # needs ONE more read, so it is deferred until after the loop and skipped
    # entirely when nothing was withheld.
    form_check_skipped: list[tuple[str, tuple | None, str, object, str | None]] = []
    form_check_ran_count = 0
    form_check_stale_count = 0
    for lat in derivation.latches:
        join = joins.get(lat.identity.candidate_id)
        if not lat.is_live or join is None or join.indeterminate:
            continue
        # THE MULTIPLICITY GUARD (RD ruling 2026-07-27). The agreement flags
        # below describe ONE reference order. Two GTC stop-limits sharing the
        # correct stop trigger but carrying DIFFERENT caps both match the latch,
        # so neither is a stray, the reference is the good one, and the page
        # would print the affirmative all-clear over a real wrong-cap order
        # resting at the broker. The panel may say only what the data supports:
        # "one order agrees" is supportable, "orders agree" over an uninspected
        # set is not. So the all-clear is WITHHELD and the multiplicity stated.
        #
        # WITHHOLDING ONLY. No per-order legs, no per-order agreement, no
        # per-order alarms -- that is the single-reference -> per-order
        # reporting-model change, and it is banked as V2, not 21-A.
        if join.matched_order_count > 1:
            multiplicity_lines.append(
                f"{lat.identity.ticker}: {join.matched_order_count} resting BUY "
                f"orders match this mandate (pivot {lat.latched_pivot:.2f} / cap "
                f"{lat.zone_cap:.2f}); only 1 is reported here - verify the "
                f"others at the broker")
        ticker = lat.identity.ticker
        quote = regime_closes.get(ticker)
        # quote is (close, RUN STAMP). The stamp is an upper bound, so the
        # ladder DATES the close against the archive instead of trusting it.
        prov = classify_close_provenance(
            quote=quote,
            derivation_session=derivation.derivation_session,
            bars_through=lat.bars_through,
            archive_closes=derivation.archive_closes.get(ticker, {}),
            archive_status=derivation.archive_status.get(
                ticker, ARCHIVE_STATUS_OK),
        )
        # MAY ASSERT: rung A only.
        assertive = prov.may_assert and expected_mandate_order_type(
            latched_pivot=lat.latched_pivot, last_close=prov.price) is not None
        # MAY ALARM: the two RD conditions. Everything EXCEPT the self-limiting
        # check is computed first so the DB read is issued only when it can
        # still change the outcome -- and so a FAILURE of that read can be
        # distinguished from a genuine `D != L` (codex-auto-review MAJOR).
        alarm_prerequisites = (
            prov.provenance == CLOSE_PROVENANCE_UNCORROBORATED
            # B-conflict: dated evidence CONTRADICTS this close. Alarming from
            # the contradicted number would be a false alarm made by our own
            # inconsistency, repeatable daily (Codex R4 MAJOR 2).
            and not prov.has_dated_conflict
            # B-unavailable: the archive read RAISED, so the missing witness is
            # our ignorance (Codex R5 MAJOR 2). BELT, not braces: an unreadable
            # archive yields an EMPTY close map, so `dated_at_stamp` below is
            # already False and this term cannot currently change the outcome
            # on its own. It is kept because it states the REASON independently
            # of that coincidence -- if a future edit ever weakened condition
            # (1), this is what would still refuse to alarm from a price whose
            # settling evidence was unreadable. (The status ALSO drives the
            # LABEL, which IS independently observable -- see T9.)
            and not prov.archive_unavailable
            # (1) CHARACTERISABLE -- the date is PROVEN at the close's own
            # stamp, not inferred from it (Codex R6 MAJOR).
            and prov.dated_at_stamp
            and prov.stamp_date is not None
            and prov.stamp_date < derivation.derivation_session
        )
        # (2) SELF-LIMITING -- the gap is the CLOCK's, not the TICKER's (Codex
        # R5 MAJOR 1). `_latest_stamp()` may be None, in which case the
        # comparison is False and authority is WITHDRAWN (permission is not
        # obligation).
        latest_stamp = _latest_stamp() if alarm_prerequisites else None
        alarm_authorized = (
            alarm_prerequisites
            and latest_stamp is not None
            and prov.stamp_session == latest_stamp
        )
        # ...but a WITHDRAWAL caused by an unreadable read is not the same fact
        # as `D != L`, and the operator must be able to tell them apart
        # (codex-auto-review MAJOR). This is the state in which a genuine,
        # dated, would-have-been-labelled mismatch was suppressed because the
        # self-limiting check could not be evaluated at all. Left unstated it
        # renders as the routine "waiting on the nightly" label over a real
        # suppressed finding -- an unlabelled under-alarm, which is the exact
        # shape the arc's coupling condition forbids.
        alarm_withheld_unreadable = bool(
            alarm_prerequisites and _stamp_read.get("failed"))
        # Every non-authorized state feeds `None` downstream, exactly as an
        # ABSENT close does today -- so `mandate_shape_mismatch` still runs in
        # its shipped unknown-regime mode (it catches a TRAILING_STOP_LIMIT or
        # a DAY duration, wrong in EVERY regime) and nothing regime-derived is
        # asserted or alarmed.
        last_close = prov.price if (assertive or alarm_authorized) else None
        expected_type = expected_mandate_order_type(
            latched_pivot=lat.latched_pivot, last_close=last_close)
        # THE UNDETERMINABLE-REGIME LABEL (RD ruling 2026-07-27). With no usable
        # close the FORM SELECTION cannot run, so BOTH forms are accepted
        # -- the right conservative behaviour, but a real reduction in what the
        # panel is asserting, and an unlabelled reduction is a quiet all-clear by
        # omission. The label states the reduction and names the checks that DID
        # run, so it reads as a narrowed claim rather than a blanket failure.
        #
        # THIS IS ALSO WHERE A LATCHED TICKER THAT LEFT THE SCREEN LANDS (ruling
        # 3): it gets no new `candidates` row, so it never gets a
        # derivation-session close and the shape check is PERMANENTLY inert for
        # that latch. Both are "the check did not run, here is why", so they
        # share ONE rendering path -- but NOT one string (RD ruling 2026-07-28):
        # waiting fixes the first and never fixes the second, so the reason and
        # the TONE both differ. `_build_form_check_notes` classifies them; the V2
        # live-quote fix is what actually restores the check.
        #
        # `latched_pivot` is validated finite at construction, so an
        # undeterminable regime is ALWAYS the close side -- either absent or off
        # the derivation session.
        #
        # THE LABEL ITSELF MUST NOT OVER-CLAIM (Codex R1 MINORs + the
        # codex-auto-review MINOR). It is scoped to the FORM SELECTION, not to
        # "the shape check": `mandate_shape_mismatch` still runs in an unknown
        # regime and can still report a TRAILING_STOP_LIMIT or a DAY order, so a
        # label claiming the whole shape check was skipped would contradict a
        # mismatch rendered three lines below it. Its tail describes only checks
        # that actually ran: with no resting order there is no form to accept and
        # no leg or duration was judged.
        if assertive:
            form_check_ran_count += 1
        else:
            if alarm_authorized:
                form_check_stale_count += 1
                # The form WAS selected here, from a dated-but-older close, so
                # the shipped "either form is accepted" tail would be false.
                tail = (
                    "the order type, the zone cap and GOOD_TILL_CANCEL were "
                    "judged against that close." if join.orders
                    else "no resting order was evaluated for this mandate.")
            else:
                tail = (
                    # GOOD_TILL_CANCEL is judged only when the payload CARRIES a
                    # duration -- `mandate_shape_mismatch` deliberately does not
                    # assert against an absent one, so an unconditional "GTC
                    # still applies" overclaims (Codex R3 MINOR).
                    "either form is accepted. The zone cap is still judged, and "
                    "GOOD_TILL_CANCEL whenever the broker payload carries a "
                    "duration." if join.orders
                    else "no resting order was evaluated for this mandate.")
            # THE NOTE REASON IS DECIDED HERE, ONCE, AND PASSED (Codex R6
            # MINOR). `_build_form_check_notes` then only FORMATS -- it makes
            # no classification decision of its own for the new branches, so
            # the counts and the labels cannot drift apart and there is no
            # second hidden classifier. `None` defers to the shipped four.
            if prov.provenance == CLOSE_PROVENANCE_FUTURE_STAMP:
                note_reason = "future_stamp"
            elif prov.has_dated_conflict:
                note_reason = "value_conflict"
            elif (prov.provenance == CLOSE_PROVENANCE_UNCORROBORATED
                    and prov.archive_unavailable):
                note_reason = "unavailable"
            elif alarm_authorized:
                note_reason = "stale_regime"
            else:
                note_reason = None
            form_check_skipped.append(
                (ticker, quote, tail, prov, note_reason,
                 alarm_withheld_unreadable))
        # EVERY line derived from a B-continuity regime carries its provenance,
        # so the operator can weigh it. An unlabelled stale-derived alarm would
        # be a claim the data does not support in the other direction.
        suffix = _uncorroborated_suffix(prov) if alarm_authorized else ""
        # (a) an order matched to this mandate but priced wrong.
        #
        # WHICH LEGS THE MANDATE HAS IS REGIME-SELECTED:
        #   PULLBACK (last close at or above the latched pivot) -- the mandate
        #     is a plain GTC LIMIT at the zone cap and has NO stop leg, so an
        #     absent stop is the CORRECT shape, not a disagreement. Demanding it
        #     produced a false "stop UNKNOWN (leg absent)" price mismatch
        #     against the operator's situationally-correct FTRE order.
        #   BREAKOUT (last close below the pivot) -- both legs, as before.
        #   UNKNOWN regime -- the SHAPE check accepts EITHER form here, so the
        #     LEG check must too, or the fragment contradicts itself and the
        #     same false alarm returns whenever the close read degrades (Codex
        #     y1 MAJOR). The stop is then judged only when the order actually
        #     CARRIES one: `order_stop_agrees` is None ONLY when the ORDER has
        #     no `stop_price`, because the latch side of the comparison
        #     (`latched_pivot`) is validated finite at construction -- so
        #     `is not None` reads exactly as "this order claims a stop trigger",
        #     and a claimed trigger is still judged against the frozen pivot.
        #
        # The CAP leg is required in EVERY regime: it is what stops the operator
        # chasing (the Codex R7 stop-only-order CRITICAL).
        #
        # THE RELAXATION IS RUNG-A ONLY (Arc 21-G, plan B.3.2 + B.4). Setting
        # `stop_leg_expected = False` EXCUSES an absent stop leg -- an
        # ASSERTION that the order's shape is right -- and RD's rule says a
        # non-corroborated close may never assert a match. Under B-continuity
        # the code therefore falls back to the shipped unknown-regime rule:
        # judge a stop the order actually carries, demand none it does not.
        # That is also the COMMISSION-NOT-OMISSION line: under a stale-derived
        # BREAKOUT regime, demanding the missing stop leg would flag the
        # operator's situationally-correct stopless pullback LIMIT every day,
        # for seven hours -- a false positive by FREQUENCY, which destroys a
        # channel exactly as reliably as a false positive by logic.
        if assertive and expected_type == MANDATE_ORDER_TYPE_PULLBACK:
            stop_leg_expected = False
        elif assertive and expected_type == MANDATE_ORDER_TYPE_BREAKOUT:
            stop_leg_expected = True
        else:
            stop_leg_expected = join.order_stop_agrees is not None
        legs_disagree = join.order_limit_agrees is not True or (
            stop_leg_expected and join.order_stop_agrees is not True)
        if join.orders and legs_disagree:
            if stop_leg_expected:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (pivot {lat.latched_pivot:.2f}, zone cap "
                    f"{lat.zone_cap:.2f}); stop "
                    f"{_agreement_word(join.order_stop_agrees)}, limit "
                    f"{_agreement_word(join.order_limit_agrees)}{suffix}")
            elif expected_type == MANDATE_ORDER_TYPE_PULLBACK:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (the last close is at or above the "
                    f"latched pivot {lat.latched_pivot:.2f}, so the mandate is "
                    f"a GTC LIMIT at the zone cap {lat.zone_cap:.2f}); limit "
                    f"{_agreement_word(join.order_limit_agrees)}{suffix}")
            else:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (zone cap {lat.zone_cap:.2f}); this order "
                    f"carries no stop leg and the last close is unavailable, so "
                    f"only the cap is judged -- limit "
                    f"{_agreement_word(join.order_limit_agrees)}")
        # (a2) an order at the RIGHT PRICES but the WRONG SHAPE. Price
        # agreement alone is not coverage: a DAY order expires tonight and
        # leaves the operator uncovered tomorrow -- the FTRE failure mode.
        # The mandated shape is REGIME-SELECTED, so the prose must name the
        # form expected at THIS price, not a hard-coded stop-limit.
        if expected_type == MANDATE_ORDER_TYPE_PULLBACK:
            mandate_prose = (
                "a GTC LIMIT at the zone cap (the last close is at or above "
                "the latched pivot, so a buy stop-limit would sit below the "
                "market and be rejected)")
        elif expected_type == MANDATE_ORDER_TYPE_BREAKOUT:
            mandate_prose = (
                "a GTC STOP_LIMIT at the latched pivot with the zone cap as "
                "its limit")
        else:
            mandate_prose = (
                "a GTC STOP_LIMIT at the latched pivot with the zone cap as "
                "its limit while price is below the pivot, or a GTC LIMIT at "
                "the cap once price is at or above it")
        for o in join.orders:
            shape = mandate_shape_mismatch(
                o, latched_pivot=lat.latched_pivot, last_close=last_close)
            if shape is not None:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting BUY order {o.order_id} "
                    f"is not the mandated order shape ({shape}); the mandate is "
                    f"{mandate_prose}{suffix}")
        # (b) a STRAY order on this ticker matching NO latch. Reported per
        # order, because a correctly-priced order would otherwise mask it and
        # the page would read as all-clear with an unexplained live order at
        # the broker.
        for stray in join.unmatched_orders:
            disagreement_lines.append(
                f"{lat.identity.ticker}: resting BUY order {stray.order_id} "
                f"(stop {_fmt_price(stray.stop_price)}, limit "
                f"{_fmt_price(stray.limit_price)}) matches NO latch on this "
                f"ticker; the mandate is pivot {lat.latched_pivot:.2f} / cap "
                f"{lat.zone_cap:.2f}")
    disagreements = tuple(dict.fromkeys(disagreement_lines))
    # Computed from the ORDER SET via the SAME predicate the suppression uses,
    # NOT from the latches. Deriving it from LIVE latches only left a hole: the
    # suppression is ticker-wide, so a ticker with only a CLEARED latch plus a
    # stale order plus an indeterminate order had its critical stale-order alarm
    # suppressed with NO banner -- the page then printed the all-clear.
    indeterminate_tickers = indeterminate_order_tickers(orders)

    form_check_notes = _build_form_check_notes(
        conn, form_check_skipped,
        derivation_session=derivation.derivation_session,
        regime_session_iso=regime_session_iso,
        close_read_failed=regime_price_read_failed,
    )

    order_lines = tuple(
        f"{o.ticker} {o.instruction} {o.quantity:g} {o.order_type} "
        f"stop {_fmt_price(o.stop_price)} limit {_fmt_price(o.limit_price)} "
        f"[{o.status}]"
        for o in orders
    )
    return LatchOrdersFragmentVM(
        available=True,
        resolution_kind="ok",
        resolution_detail=resolution.detail,
        alarms=tuple(
            LatchAlarmVM(kind=a.kind, ticker=a.ticker,
                         latch_candidate_id=a.latch_candidate_id,
                         detail=a.detail, severity=a.severity)
            for a in sorted(alarms, key=lambda a: (a.severity != "critical", a.kind))
        ),
        order_lines=order_lines,
        disagreements=disagreements,
        indeterminate_tickers=indeterminate_tickers,
        multiplicity_notes=tuple(dict.fromkeys(multiplicity_lines)),
        mandate_form_check_skipped=form_check_notes,
        form_check_ran_count=form_check_ran_count,
        form_check_stale_count=form_check_stale_count,
    )


def _build_form_check_notes(
    conn, skipped, *, derivation_session: date, regime_session_iso: str,
    close_read_failed: bool,
) -> tuple[MandateFormCheckVM, ...]:
    """Render each non-ASSERTIVE form check as a labelled note.

    `skipped` is `(ticker, quote, tail, provenance, note_reason)` per affected
    latch, and `note_reason` was DECIDED IN THE LOOP (Codex R6 MINOR) -- this
    function only FORMATS. There is no second classifier here, so the counts
    and the labels cannot drift apart. A `None` reason defers to the four
    shipped branches below.

    THE COUPLING (RD's binding condition, 2026-07-28). Under-alarming is
    acceptable ONLY BECAUSE IT IS LABELLED; an unlabelled under-alarm is a
    silent all-clear. So EVERY state in which the check declines to alarm
    reaches this function and renders a note saying what was not judged and
    why. Deleting a branch here does not merely lose wording -- it converts a
    defensible reduction into the exact defect the arc exists to eliminate.

    The shipped four still need ONE fact nothing else on this page knows --
    whether ANY usable close has been recorded for the derivation session -- so
    that read happens here, once, and ONLY when something was withheld.

    That fact is deliberately about CLOSES, never about screen MEMBERSHIP (the
    Codex y1 MAJOR 1): an `evaluation_runs` row carries held open positions and
    pins alongside the finviz screen, so no read over it can prove a ticker was
    or was not screened. Do not re-derive this from a ticker set.
    """
    if not skipped:
        return ()
    # A FAILED close read short-circuits: with no closes read at all, the
    # recorded-close count says nothing useful about WHY this latch has none.
    recorded: int | None = None
    if not close_read_failed:
        try:
            recorded = count_session_recorded_closes(conn, derivation_session)
        except Exception as exc:  # noqa: BLE001 -- A6: the panel never 500s
            _log.warning("latch order recorded-close count degraded: %s", exc)
            recorded = None

    notes: list[MandateFormCheckVM] = []
    for ticker, quote, tail, prov, note_reason, alarm_read_failed in skipped:
        provenance = _close_provenance(quote)
        session_iso = regime_session_iso
        stamp = (prov.stamp_session or "") if prov is not None else ""
        if note_reason == "stale_regime":
            # B-CONTINUITY. The form check DID run -- from a close whose date
            # the archive PROVED, one session or more before this page's own.
            # NEUTRAL, not a warning: this is the state of every live latch for
            # ~7 hours of every trading day, and a warning-shaped label on a
            # daily state trains the dismissal reflex on the one surface whose
            # alarms have to survive being believed. It REPLACES the shipped
            # `pending` note for this latch -- the two describe the same moment.
            severity = "stale_regime"
            detail = (
                f"{ticker}: the mandate FORM check ran from an uncorroborated "
                f"close dated {stamp} - the archive corroborates that close at "
                f"{stamp} but holds no bar for the derivation session "
                f"{session_iso}, so a mismatch found from it is reported and "
                f"LABELLED while no all-clear is asserted for this latch. The "
                f"whole system is no fresher than this ticker, so the next "
                f"nightly run normally ends the gap. {_as_sentence(tail)}")
        elif note_reason == "value_conflict":
            # B-CONFLICT. Not merely un-dated: CONTRADICTED by dated evidence
            # the panel is holding. Naming both numbers is strictly more useful
            # than either an alarm or generic inert wording, because it reports
            # a real data inconsistency in the operator's own system.
            severity = "value_conflict"
            recorded_value = "-" if prov.price is None else f"{prov.price:.2f}"
            archive_value = (
                "-" if prov.session_close is None else f"{prov.session_close:.2f}")
            same_session = stamp == session_iso
            disagreement = (
                (f"two dated sources disagree about the same session: the "
                 f"recorded close is {recorded_value} while the archive bar "
                 f"dated {session_iso} closed at {archive_value}")
                if same_session else
                (f"the archive holds a newer close for {session_iso} "
                 f"({archive_value}) than the recorded one ({recorded_value}, "
                 f"stamped {stamp or 'an unrecorded session'})"))
            detail = (
                f"{ticker}: the mandate FORM check is INERT for this latch - "
                f"{disagreement}. No mandate form will be picked while the two "
                f"disagree, and no alarm is raised from the contradicted "
                f"number. Verify the archive and the recorded close. {tail}")
        elif note_reason == "future_stamp":
            # RUNG F. A price that cannot be placed at-or-before this page's
            # own moment may neither decide nor contest the regime -- the same
            # coherent-moment discipline that makes a stale render anchor
            # suppress the alarms.
            # THE REASON MUST BE TRUE, NOT MERELY SAFE (Codex R9 + R10 MINOR).
            # Rung F holds TWO distinct shapes, keyed on the PARSED stamp and
            # never on the raw string being non-empty: a stamp of 'not-a-date'
            # is non-empty but UNPLACEABLE, and calling it "later than" would
            # state a false reason for a correct degradation. The HEADLINE
            # moves with the detail -- it is the bold text read first, so a
            # true detail under a false headline is worse than neither.
            severity = (
                "future_stamp" if prov is not None and prov.stamp_date is not None
                else "unplaceable_stamp")
            if severity == "future_stamp":
                placed = (
                    f"is stamped {stamp}, LATER than the derivation session "
                    f"{session_iso} this page describes, so it belongs to a "
                    f"moment after this page")
            elif stamp:
                placed = (
                    f"carries the session stamp {stamp}, which is not a usable "
                    f"date, so it cannot be placed in time at all")
            else:
                placed = (
                    f"carries no session stamp at all, so it cannot be placed "
                    f"at or before the derivation session {session_iso}")
            detail = (
                f"{ticker}: the mandate FORM check is INERT for this latch - "
                f"the most recent recorded close {placed}. A price that cannot "
                f"be placed at or before the session this page describes cannot "
                f"say WHICH of the two mandate forms is correct at this price, "
                f"so neither a match nor a mismatch is claimed from it. Reload "
                f"to move this page forward. {tail}")
        elif note_reason == "unavailable":
            # B-UNAVAILABLE. The archive read RAISED, so the missing witness is
            # OUR IGNORANCE. Alarming here would be asserting from a stale
            # price at exactly the moment the settling evidence was unreadable.
            severity = "unknown"
            detail = (
                f"{ticker}: the mandate FORM check did not run - the OHLCV "
                f"archive read for this ticker failed, so the recorded close "
                f"could not be dated and the panel cannot say WHICH of the two "
                f"mandate forms is correct at this price, nor raise a mismatch "
                f"from a price it could not place in time; {tail}")
        elif close_read_failed:
            severity = "unknown"
            detail = (
                f"{ticker}: the mandate FORM check did not run - the close read "
                f"failed, so no regime price is available for the derivation "
                f"session {regime_session_iso} and the panel cannot say WHICH "
                f"of the two mandate forms is correct at this price; {tail}")
        elif recorded is None:
            # The count read itself failed. Guessing "pending" would tell the
            # operator to wait for something that may never arrive, so the panel
            # promises nothing in either direction.
            severity = "unknown"
            detail = (
                f"{ticker}: the mandate FORM check did not run - {provenance}, "
                f"and whether any closes dated {regime_session_iso} have been "
                f"recorded could not be determined, so the "
                f"panel cannot say WHICH of the two mandate forms is correct at "
                f"this price, nor whether waiting will clear it; {tail}")
        elif recorded == 0:
            # NOBODY has a close for this session yet -- the default state for
            # ~7 hours of every trading day. Status, not a warning.
            severity = "pending"
            detail = (
                # "no USABLE closes are RECORDED" -- the count mirrors
                # `load_last_closes`'s usability filter, so a run that recorded
                # only NULL / non-finite closes also reads as zero, and "no
                # closes have been recorded" would then overstate what the
                # helper knows (Codex y3 MINOR 1).
                f"{ticker}: waiting on the nightly data for the derivation "
                f"session {regime_session_iso} - no usable closes dated "
                f"{regime_session_iso} are recorded yet ({provenance}), "
                f"so there is no regime price and "
                f"the panel cannot yet say WHICH of the two mandate forms is "
                # WHAT the nightly settles, not what it guarantees (Codex y2
                # MINOR 1). The run ends the WAITING; it does not promise the
                # check will then run, because a ticker that is still not
                # evaluated lands in the permanent branch instead. Promising the
                # check would be the same over-claim in the opposite direction.
                # "NORMALLY settles" (Codex y5 MINOR 2): the count mirrors the
                # usable-close filter, so a run that again records only
                # unusable closes leaves this state exactly as it was. The
                # ruling requires a stated clear time, not a guarantee.
                f"correct at this price. This is the normal state between the "
                f"market close and the nightly pipeline run; the next run "
                f"normally settles it - either the form check runs, or this "
                f"becomes a warning. {_as_sentence(tail)}")
        else:
            # That session already has closes and this ticker's newest usable
            # close is still older -- so this is a question about the TICKER,
            # not about the clock. The COUNT is rendered so the operator can see
            # the evidence rather than take the diagnosis on trust (Codex y1
            # MAJOR 2), and the cause is stated as the usual one, not asserted.
            severity = "permanent"
            noun = "ticker" if recorded == 1 else "tickers"
            detail = (
                # "DATED", not "for" (codex-auto-review MAJOR). The evaluator
                # stamps `evaluation_runs.data_asof_date` as the MAX bar date
                # across the whole cohort while each `candidates.close` comes
                # from that ticker's own last bar, so the date is a STAMP, not a
                # proof that the bar is from that session. "Dated" is exactly
                # what the read can support.
                f"{ticker}: closes dated {regime_session_iso} HAVE been "
                f"recorded (for {recorded} "
                f"{noun}), but {provenance}, so there is no regime price for this "
                # The cause is stated as the USUAL one and the look-alike is
                # named (Codex y2 MINOR 2). "not held, not pinned" was dropped:
                # this read cannot see WHY a ticker is absent, and a parenthetical
                # that reads as a diagnosis is the same over-claim in miniature.
                f"mandate and the panel cannot say WHICH of the two mandate "
                f"forms is correct at this price. The usual cause is the ticker "
                f"no longer being evaluated at all; a partial evaluation of that "
                f"session looks the same from here. "
                # The response cue is stated WITHOUT any claim about the
                # nightly. "Waiting will never clear this" was false under the
                # partial-evaluation shape (Codex y4 MINOR 1) and so was "this
                # is NOT simply waiting on the nightly" (y5 MINOR 1) -- both
                # asserted something the count cannot prove. What the count DOES
                # prove is that the session already has closes and this ticker
                # has none of them, which makes it a question about the TICKER
                # rather than the clock. The clearing condition is a usable
                # close, not being evaluated (y3 MINOR 2): a row may carry none.
                #
                # NO APOSTROPHE anywhere in these details: Jinja autoescaping
                # renders one as `&#39;`, which is correct HTML but silently
                # breaks any assertion (or operator search) on the plain text.
                f"So this is a question about the TICKER rather than the clock: "
                f"it clears when this ticker again has a usable close on the "
                f"derivation session. {_as_sentence(tail)}")
        if alarm_read_failed:
            # THE WITHHELD ALARM STATES ITS OWN REASON (codex-auto-review
            # MAJOR). This latch held a close whose date the archive PROVED and
            # which is genuinely older than this page's session -- i.e. every
            # condition for a labelled stale-derived mismatch EXCEPT the one
            # read that failed. The shipped branch above stays exactly as ruled
            # (an unreadable `L` withdraws alarm authority ONLY; it does not
            # change the label, because the count-driven statement remains TRUE
            # and telling him less than we know would be its own defect). This
            # clause is purely ADDITIVE: it names the suppression so the
            # routine wording cannot stand in for it.
            detail = (
                f"{detail} Separately: a stale-derived mismatch could not even "
                f"be CONSIDERED for this latch, because the newest-recorded-"
                f"close-stamp read failed and the panel could not tell whether "
                f"this staleness is system-wide. Any such finding was withheld "
                f"rather than risk one that repeats every day.")
        notes.append(MandateFormCheckVM(
            ticker=ticker, severity=severity,
            headline=_FORM_CHECK_HEADLINES[severity], detail=detail))
    return tuple(dict.fromkeys(notes))


# Drift pin support: the base-banner field names declared on LatchPanelVM.
PANEL_SPECIFIC_FIELDS = frozenset({
    "rows", "degraded_rows", "available", "unavailable_reason",
    "live_candidate_ids", "derivation_session", "horizon_session",
    "beacon_payload_json", "orders_payload_json", "base_break_footnote",
})


def declared_banner_fields() -> frozenset[str]:
    return frozenset(
        f.name for f in fields(LatchPanelVM) if f.name not in PANEL_SPECIFIC_FIELDS)
