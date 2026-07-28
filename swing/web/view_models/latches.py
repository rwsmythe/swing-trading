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
from swing.latches.constants import LATCH_PANEL_LOOKBACK_SESSIONS
from swing.latches.models import Latch
from swing.latches.reader import build_latch_derivation, load_last_closes
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
    price_asof: str
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


def _build_row(latch: Latch, *, quote, views) -> LatchRowVM:
    """`quote` is `(price, asof_iso)` from the READ-ONLY last-close source, or
    `None`."""
    price = None if quote is None else quote[0]
    zone_position = _zone_position(price, latch)
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
        price_asof="-" if quote is None or not quote[1] else quote[1],
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

        rows = [
            _build_row(
                latch,
                quote=(
                    quotes.get(latch.identity.ticker) if latch.is_live else None),
                views=views_by_latch.get(latch.identity.candidate_id, ()),
            )
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


def _load_views(conn, latches, horizon_session: date) -> dict[int, tuple]:
    """The persisted view telemetry for THIS session, per latch. Read-only."""
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
                conn, evaluation_run_id=latch.identity.evaluation_run_id,
                ticker=latch.identity.ticker)
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
    # required to be VISIBLY inert rather than silently inert.
    shape_check_skipped: tuple[str, ...] = ()


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
    # IT IS SESSION-SCOPED (codex-auto-review MAJOR). `load_last_closes` returns
    # the GLOBALLY latest close per ticker no matter how old it is, so without
    # this gate a price from several sessions ago would decide which instrument
    # the panel calls correct -- and on a stock that has since round-tripped
    # through the pivot that blesses the wrong order or flags the right one. The
    # fragment already insists every part of its picture describe ONE coherent
    # moment (it is why a one-session-stale ANCHOR suppresses the alarms); the
    # regime price is held to the same standard. Only a close stamped on the
    # DERIVATION SESSION may pick a form; anything else leaves the regime
    # unknown, where both forms are accepted and the cap leg and GTC still bind.
    regime_session_iso = derivation.derivation_session.isoformat()
    regime_closes: dict = {}
    regime_tickers = sorted({
        lat.identity.ticker for lat in derivation.latches if lat.is_live})
    if regime_tickers:
        try:
            regime_closes = load_last_closes(conn, regime_tickers)
        except Exception as exc:  # noqa: BLE001 -- A6: a price miss never blocks
            _log.warning("latch order regime price read degraded: %s", exc)
            regime_closes = {}

    disagreement_lines: list[str] = []
    multiplicity_lines: list[str] = []
    shape_check_skipped_lines: list[str] = []
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
        quote = regime_closes.get(lat.identity.ticker)
        # quote is (close, data_asof_date); a close from any other session is
        # not evidence about THIS moment, so it does not get to pick the form.
        last_close = (
            quote[0] if quote is not None and quote[1] == regime_session_iso
            else None)
        expected_type = expected_mandate_order_type(
            latched_pivot=lat.latched_pivot, last_close=last_close)
        # THE UNDETERMINABLE-REGIME LABEL (RD ruling 2026-07-27). With no usable
        # close the two-form shape check cannot run, so BOTH forms are accepted
        # -- the right conservative behaviour, but a real reduction in what the
        # panel is asserting, and an unlabelled reduction is a quiet all-clear by
        # omission. The label states the reduction and names the checks that DID
        # run, so it reads as a narrowed claim rather than a blanket failure.
        #
        # THIS IS ALSO WHERE A LATCHED TICKER THAT LEFT THE SCREEN LANDS (ruling
        # 3): it gets no new `candidates` row, so it never gets a
        # derivation-session close and the shape check is PERMANENTLY inert for
        # that latch. Both are "the check did not run, here is why", so they
        # share one rendering path; only the reason clause differs. The V2
        # live-quote fix is what actually restores the check.
        #
        # `latched_pivot` is validated finite at construction, so an
        # undeterminable regime is ALWAYS the close side -- either absent or off
        # the derivation session.
        if expected_type is None:
            if quote is None:
                why = ("no close is recorded for this ticker on the derivation "
                       f"session {regime_session_iso}")
            else:
                why = (f"the most recent close for this ticker is from "
                       f"{quote[1] or 'an unrecorded session'}, not the "
                       f"derivation session {regime_session_iso}")
            shape_check_skipped_lines.append(
                f"{lat.identity.ticker}: order-shape check did NOT run - {why}, "
                f"so the panel cannot say which mandate form is correct at this "
                f"price; either form is accepted. The zone cap and "
                f"GOOD_TILL_CANCEL checks still apply.")
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
        if expected_type == MANDATE_ORDER_TYPE_PULLBACK:
            stop_leg_expected = False
        elif expected_type == MANDATE_ORDER_TYPE_BREAKOUT:
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
                    f"{_agreement_word(join.order_limit_agrees)}")
            elif expected_type == MANDATE_ORDER_TYPE_PULLBACK:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (the last close is at or above the "
                    f"latched pivot {lat.latched_pivot:.2f}, so the mandate is "
                    f"a GTC LIMIT at the zone cap {lat.zone_cap:.2f}); limit "
                    f"{_agreement_word(join.order_limit_agrees)}")
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
                    f"{mandate_prose}")
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
        shape_check_skipped=tuple(dict.fromkeys(shape_check_skipped_lines)),
    )


# Drift pin support: the base-banner field names declared on LatchPanelVM.
PANEL_SPECIFIC_FIELDS = frozenset({
    "rows", "degraded_rows", "available", "unavailable_reason",
    "live_candidate_ids", "derivation_session", "horizon_session",
    "beacon_payload_json", "orders_payload_json", "base_break_footnote",
})


def declared_banner_fields() -> frozenset[str]:
    return frozenset(
        f.name for f in fields(LatchPanelVM) if f.name not in PANEL_SPECIFIC_FIELDS)
