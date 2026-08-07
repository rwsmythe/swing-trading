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

from swing.data.repos.latch_order_intents import list_intents_for_latch
from swing.data.repos.risk_policy import get_active_policy
from swing.evaluation.dates import (
    PageKind,
    sessions_behind,
    topbar_session_date,
)
from swing.latches.classification import (
    assess_telemetry_health,
    classify_latch,
    decision_bounds_for,
    telemetry_window_sessions,
)
from swing.latches.constants import (
    ARCHIVE_STATUS_OK,
    CLOSE_PROVENANCE_FUTURE_STAMP,
    CLOSE_PROVENANCE_UNCORROBORATED,
    DEFAULT_CRITERIA_LAPSE_SESSIONS,
    LATCH_ATTESTED_DISPOSITIONS,
    LATCH_PANEL_LOOKBACK_SESSIONS,
    build_beacon_payload,
    mandate_limit_price,
)
from swing.latches.models import Latch
from swing.latches.order_intent import (
    FRAMEWORK_ANCHOR_FIELDS,
    SizingInputs,
    build_anchor_digest,
    compute_prepared_order,
    derivation_anchor_fields,
    derivation_column_values,
    encode_derivation_value,
    framework_column_values,
)
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


LOG_ONLY_NOTICE = "PREPARED ORDER (LOG ONLY - nothing is sent to the broker)"

# The DECISION-axis labels. Every one states its REASON, because an unlabelled
# reduction is a quiet all-clear by omission -- and two of these dispositions
# exist precisely to say the instrument, not the operator, was silent.
_DISPOSITION_LABELS = {
    "pre_telemetry": (
        "PRE-TELEMETRY - the view instrument did not exist over this latch's "
        "window, so nothing about the operator is claimed"),
    "telemetry_unhealthy": (
        "TELEMETRY UNHEALTHY - the beacon was dark across this window, so no "
        "away/lapse verdict is asserted"),
    "never_actionable": (
        "NEVER ACTIONABLE - the panel rendered but its prepared order was "
        "withheld throughout; that is our silence, not his"),
    "away_unseen": "AWAY - the instrument looked and saw nothing",
    "accepted": "ACCEPTED - a prepared-order placement was logged",
    "declined": "DECLINED",
    "attested_acted_manually": "ATTESTED - acted manually",
    "attested_chose_not_to_act": "ATTESTED - chose not to act",
    "attested_was_away": "ATTESTED - was away",
    "discipline_lapse": (
        "DISCIPLINE LAPSE - an actionable mandate was presented and no action "
        "was recorded"),
    "pending_live": "PENDING - still live; reported, never scored",
    # THE #11 MIRROR THIS MAP TURNED OUT TO BE (Codex R1 + auto-review, item
    # 3b). `_build_row` subscripts this map BARE, and the panel's outer
    # `except Exception` degrades the WHOLE panel -- so a disposition ruled
    # into `LATCH_DISPOSITIONS` without a label here does not lose one row, it
    # loses every latch behind "latch derivation unavailable". A set-equality
    # test now pins the two together.
    "framework_withdrawn": (
        "WITHDRAWN BY THE FRAMEWORK - the A+ structural gate failed over the "
        "calibrated window and the price decayed with it; never scored "
        "against him"),
}

_ATTEST_OPTION_LABELS = {
    "acted_manually": "I acted on this manually",
    "chose_not_to_act": "I saw it and chose not to act",
    "was_away": "I was away",
}


@dataclass(frozen=True)
class PreparedOrderVM:
    """The framework's computed entry order, WITH its derivation, or WITHHELD.

    THE DERIVATION TRAVELS WITH THE NUMBERS, and that is structural rather than
    stylistic (the D25 lesson): a human gate only helps if the human can SEE
    that a computation is wrong, and four bare numbers invite click-through.

    THE WITHHELD BRANCH IS THE EXPRESSIVE ONE, not the afterthought. It is the
    CURRENT live state -- the regime is undeterminable whenever no close is
    dated the derivation session -- so it carries a display-ready reason and,
    deliberately, NO order numbers at all: rendering a quantity or a limit under
    a withheld heading would present as a mandate something the framework
    refused to assert.
    """

    offered: bool
    headline: str
    derivation_lines: tuple[str, ...]
    # SECTION A.4's closure, made checkable: which manifest columns this block
    # actually PRESENTS. Declared by the line builders, so a line added without
    # anchoring its inputs fails the manifest assertion.
    rendered_derivation_columns: frozenset[str]
    # The HIDDEN ANCHOR the form emits, `(name, encoded_value)`, GENERATED by
    # walking the manifest so the form, the digest and the POST-time comparison
    # cannot drift.
    anchor_fields: tuple[tuple[str, str], ...]
    anchor_digest: str
    withheld_reason: str | None
    withheld_detail: str
    log_only_notice: str = LOG_ONLY_NOTICE


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
    # ===== Arc 21-B: the prepared order, the disposition and the prompt =====
    # Defaulted so 21-A's construction shape is preserved and a degraded build
    # can omit the whole block rather than 500 the page (A6).
    prepared_order: PreparedOrderVM | None = None
    disposition: str = ""
    disposition_label: str = ""
    execution_outcome: str = ""
    # True on EXACTLY ONE disposition (`discipline_lapse`). A prompt on an
    # objectively-resolved cell trains dismissal, and dismissal is what
    # eventually kills the honest answer on the cell that matters.
    prompt_required: bool = False
    attest_options: tuple[tuple[str, str], ...] = ()
    # The RULING-3 context anchor (see `_prior_intent_id`): the ledger row that
    # governed this latch AS THIS PAGE RENDERED IT, `""` when it had none. Every
    # intent form on the card emits it, and it is deliberately OUTSIDE the
    # manifest-generated hidden anchor -- it is not part of the framework
    # DERIVATION and must not enter `anchor_digest`.
    prior_intent_id: str = ""
    # THE ATTESTATION CORRECTION AFFORDANCE (Codex exec R6 MAJOR). The prompt
    # rides on `discipline_lapse` and vanishes the instant an attestation is
    # recorded -- so `was_away` could never be corrected to `chose_not_to_act`
    # through the browser, and the two dispositions land in DIFFERENT R buckets.
    # RD's ruling 3 requires that a correction be possible; a control the
    # operator cannot reach makes the append-only correction path a handler
    # capability he can never use.
    #
    # DELIBERATELY NOT `prompt_required`: that flag is a PROMPT, and the plan is
    # explicit that prompting anywhere other than a scored lapse trains the
    # dismissal reflex. This is not a question -- it is an affordance to amend an
    # answer he already gave, worded and styled as one.
    attest_correction_available: bool = False
    attested_disposition: str = ""
    # ===== Item 3b: the criteria-lapse countdown and the UNVERIFIABLE render =
    # READ from the `Latch`, NEVER recomputed here. Recomputing the streak in
    # the view would be a SECOND implementation of the resolver -- the drift
    # class this arc single-sources the A+ gate to avoid -- and the VM cannot
    # see the PASSED sessions at all, so it could not compute the tail
    # correctly even if it tried.
    lapse_countdown: str = ""
    lapse_detail: str = ""
    unverifiable_label: str = ""


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
    # The per-order CANCEL control's anchors (plan file manifest: "the per-order
    # Cancel control on stale-order rows"). Present together or not at all: a
    # `cancel` row needs BOTH the broker order it targets and the latch identity
    # block, so an alarm about an order attributable to NO latch cannot offer the
    # control -- see `cancel_unavailable_note`.
    broker_order_id: str | None = None
    prior_intent_id: str = ""
    cancel_unavailable_note: str = ""


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
    # ===== Arc 21-B =====
    # The PANEL-LEVEL half of the intent anchor: the render-time session every
    # per-latch form posts alongside its own hidden framework block. Separate
    # from `beacon_payload_json` because the beacon reports a RENDER and the
    # intent form submits a DECISION -- different claims, different payloads.
    intent_payload_json: str = ""
    # The telemetry verdict, rendered rather than merely consumed: the away rate
    # it gates is the number that would justify automating the operator's
    # entries, so its reliability is not allowed to be invisible.
    telemetry_health_verdict: str = "ok"
    telemetry_health_label: str = ""
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


def _fmt_cap(zone_cap) -> str:
    """THE ONLY WAY THIS MODULE RENDERS A ZONE CAP.

    IT RENDERS THE PRICE THE FRAMEWORK WOULD ACTUALLY ORDER, not the raw cap
    (operator witness, 2026-08-03). `mandate_limit_price` FLOORS to whole cents
    -- RD's ruling that a cap which can drift up is not a cap -- while `:.2f`
    rounds HALF-UP, so on any cap whose third decimal is >= 5 the two disagree
    by exactly one cent and the DISPLAY states a price ABOVE the cap.

    That is not cosmetic. The panel showed `Zone cap 37.36` for AMN beside its
    own prepared order at `limit 37.35`; the operator placed 37.36 because it
    was the number in front of him, and 21-B's parity ledger records the
    difference between the framework's price and his as HIS deviation. So the
    surface may never show a price the framework would refuse to order.

    SAME FUNCTION AS THE MANDATE, NOT A SECOND FLOORING EXPRESSION (CHARC,
    2026-07-30): a parallel copy that agrees today is the D6 drift class, which
    is exactly how the comparator and the emitter diverged on VSTS.

    `None` degrades to `_fmt_price`'s dash. `Latch.zone_cap` is validated finite
    at construction, so this is a belt for a caller holding something else.
    """
    return "-" if zone_cap is None else _fmt_price(mandate_limit_price(zone_cap))


def _fmt_money(value) -> str:
    return f"${float(value):,.2f}"


# ---------------------------------------------------------------------------
# Arc 21-B Task 6 -- the prepared-order block.
# ---------------------------------------------------------------------------
def _prior_intent_id(intents) -> str:
    """The latch's GOVERNING ledger row as this render saw it, or `""`.

    THE RULING-3 CONTEXT ANCHOR (RD, 2026-07-30). The ledger's unit is the
    EVENT, not the VALUE: a content-derived idempotency key that collapses on
    value cannot tell a REPLAY from a CORRECTION, because the two are identical
    in value and differ only in context. A -> B -> A therefore reused A's key and
    the third answer -- his actual final answer -- was discarded as a replay,
    leaving the flattering intermediate governing. That is the instrument
    editing its subject's testimony in his favour, which this ledger may never
    do.

    So the key is scoped to the SUBMISSION IN CONTEXT: the form carries the row
    that governed the latch WHEN IT WAS RENDERED. A -> B -> A carries `prior=B`
    on the third submission, so its key differs from the first (`prior=none`)
    and it writes; a double-click on that third submission carries the SAME
    prior and still collapses.

    LATCH-SCOPED, NOT KIND-SCOPED, and that is one rule rather than five: the
    ledger is per-latch and append-only, "the context" is the state of that
    latch's ledger as he saw it, and the place/decline form is ONE form whose
    kind is chosen at the submit button -- so a kind-scoped anchor could not be
    rendered by it at all.

    `(recorded_ts, intent_id)` is the same total order every other "latest by
    what?" ruling in this arc uses; the `intent_id` tiebreak is load-bearing
    because `recorded_ts` is whole seconds.
    """
    rows = [i for i in intents or () if getattr(i, "intent_id", None) is not None]
    if not rows:
        return ""
    latest = max(rows, key=lambda i: (i.recorded_ts, i.intent_id))
    return str(latest.intent_id)


def _withheld_block(reason: str | None, detail: str) -> PreparedOrderVM:
    """A withheld block carries the REASON and NOTHING that reads as a mandate.

    No headline, no derivation lines, no hidden anchor: a quantity or a limit
    rendered under a withheld heading would present as an order to place
    something the framework explicitly refused to assert -- and the ledger's
    whole claim is that a recorded framework order is byte-identically what the
    operator was looking at.
    """
    return PreparedOrderVM(
        offered=False, headline="", derivation_lines=(),
        rendered_derivation_columns=frozenset(), anchor_fields=(),
        anchor_digest="", withheld_reason=reason, withheld_detail=detail)


def _derivation_block(latch: Latch, order) -> tuple[tuple[str, ...], frozenset[str]]:
    """The card's derivation lines, each DECLARING the manifest columns it
    presents.

    The declaration is what makes section A.4's rule executable instead of
    aspirational: EVERY value presented inside this block is hidden-anchored,
    compared at POST and stored, and anything not anchored MUST NOT be rendered
    here. The two are ONE decision, and a line added without anchoring its
    inputs fails the manifest assertion rather than silently shipping an
    un-audited number.
    """
    d = order.derivation
    lines: list[tuple[frozenset[str], str]] = []
    lines.append((
        frozenset({"derivation_zone_cap_pct"}),
        f"Limit  {order.limit_price:.2f}  = latched pivot "
        f"{d.latched_pivot:.2f} x {1 + d.zone_cap_pct / 100:.2f} (zone cap), "
        f"floored to whole cents (a cap that can drift up is not a cap)"))
    if order.stop_price is None:
        stop_line = (
            f"Stop   none   = the last close {d.regime_close:.2f} (dated "
            f"{d.regime_close_session}) is at or above the latched pivot "
            f"{d.latched_pivot:.2f}, so the mandate is a resting BUY LIMIT; a "
            f"buy stop-limit at {d.latched_pivot:.2f} would sit below the "
            f"market and be rejected by the broker.")
    else:
        stop_line = (
            f"Stop   {order.stop_price:.2f}  = the latched pivot; the last "
            f"close {d.regime_close:.2f} (dated {d.regime_close_session}) is "
            f"BELOW it, so the mandate is the breakout GTC STOP_LIMIT.")
    lines.append((
        frozenset({"derivation_regime_close", "derivation_regime_close_session"}),
        stop_line))
    lines.append((
        frozenset(),
        f"Pivot  {d.latched_pivot:.2f}  frozen at the fire: evaluation run "
        f"{d.fire_evaluation_run_id}, session {d.fire_session}, candidate "
        f"{d.fire_candidate_id} - this mandate does NOT follow a later "
        f"candidates row."))
    lines.append((
        frozenset({"derivation_sizing_basis"}),
        f"Qty    {order.quantity}      = floor("
        f"{_fmt_money(d.max_risk_dollars)} / {_fmt_money(d.risk_per_share)}); "
        f"the sizing basis is the {d.sizing_basis} - the worst price this "
        f"order can fill at."))
    lines.append((
        frozenset(),
        f"                  risk per share {d.risk_per_share:.2f} = limit "
        f"{order.limit_price:.2f} - fire-time stop "
        f"{d.latched_initial_stop:.2f}"))
    lines.append((
        frozenset({"derivation_max_risk_pct"}),
        f"                  max risk {_fmt_money(d.max_risk_dollars)} = sizing "
        f"equity {_fmt_money(d.sizing_equity)} x {d.max_risk_pct * 100:.3f}%"))
    lines.append((
        frozenset({"derivation_sizing_equity", "derivation_real_equity",
                   "derivation_equity_floor"}),
        f"                  sizing equity {_fmt_money(d.sizing_equity)} = "
        f"max(real equity {_fmt_money(d.real_equity)}, risk_equity_floor "
        f"{_fmt_money(d.equity_floor)})"))
    lines.append((
        frozenset({"derivation_risk_policy_id"}),
        f"                  risk_policy id {d.risk_policy_id}"
        if d.risk_policy_id is not None
        else "                  no active risk_policy row - the sizing RATE "
             "comes from config, and the policy id is provenance only"))
    lines.append((
        frozenset({"derivation_position_pct_cap"}),
        f"                  position cap would allow {d.shares_by_position_cap} "
        f"sh ({_fmt_money(d.sizing_equity * d.position_pct_cap)} / "
        f"{order.limit_price:.2f}) - "
        f"{'RISK BINDS' if d.binding_constraint == 'risk' else 'POSITION CAP BINDS'}"))
    # THE SECTION-D.3 DIVERGENCE NOTE IS GONE (RD 2026-08-04) -- a guard that
    # outlived its condition. It existed because the nightly briefing sized off
    # the PIVOT while this form sized off the LIMIT, so the operator needed both
    # numbers and the reason in front of him at the point of action. The nightly
    # now sizes off the limit too (`swing/recommendations/build.py:_sizing_entry`
    # and `swing/web/view_models/dashboard.py`), the surfaces agree, and prose
    # explaining a divergence that no longer exists reads as an active warning.
    #
    # `derivation_nightly_recommendation_shares` ITSELF STAYS, AND THE REASON IS
    # PROVENANCE (RD, 2026-08-04). The column is PER-ROW PROVENANCE -- what the
    # nightly surface said AT INTENT TIME -- so it is still gathered,
    # hidden-anchored, digested and written to the append-only
    # `latch_order_intents` ledger. The two counts will now typically AGREE and
    # the column keeps recording that agreement; what was retired is the RENDER
    # that explained a by-design divergence which no longer exists. An
    # append-only ledger losing a provenance field to a display cleanup is the
    # anti-provenance move, not a tidy-up. The manifest row is declared
    # `rendered=False` so the section-A.4 closure assertion stays honest rather
    # than merely satisfied. Full rationale + RD's generalization
    # ("the machinery comes out" = the CLAIMS and their RENDERS, never a
    # persisted column): `swing/latches/constants.py`, the manifest row.
    lines.append((
        frozenset(),
        f"Invalidation {d.latched_initial_stop:.2f} ({INVALIDATION_LABEL})"))
    columns: set[str] = set()
    for used, _ in lines:
        columns |= used
    return tuple(text for _, text in lines), frozenset(columns)


def _build_prepared_order_vm(
    latch: Latch, result, *, view_session_date: str,
) -> PreparedOrderVM:
    """Turn a `PreparedOrderResult` into the card block plus its hidden anchor."""
    if result.order is None:
        return _withheld_block(result.withheld_reason, result.withheld_detail)
    order = result.order
    lines, columns = _derivation_block(latch, order)
    # ONE enumeration, GENERATED from the manifest. No site re-lists the
    # derivation columns, so the form's hidden inputs, `anchor_digest` and the
    # POST-time comparison read the SAME mapping and cannot drift.
    raw: dict = {}
    raw.update(framework_column_values(order))
    raw.update(derivation_column_values(order.derivation))
    encoded: list[tuple[str, str]] = [
        ("view_session_date", view_session_date),
        ("candidate_id", str(latch.identity.candidate_id)),
    ]
    for name, enc in FRAMEWORK_ANCHOR_FIELDS:
        encoded.append((name, encode_derivation_value(enc, raw.get(name))))
    for column, enc in derivation_anchor_fields():
        encoded.append((column, encode_derivation_value(enc, raw.get(column))))
    digest = build_anchor_digest(
        intent_kind="place", candidate_id=latch.identity.candidate_id,
        view_session_date=view_session_date, values=dict(encoded))
    # The instrument, rendered as the operator would enter it. The PULLBACK form
    # has no stop leg at all -- a buy stop below the market is the FTRE
    # rejection -- so it renders as a plain `LIMIT <cap>` rather than as a
    # stop-limit with an empty trigger.
    instrument = (
        f"{order.order_type} {order.limit_price:.2f}"
        if order.stop_price is None
        else (f"{order.order_type} stop {order.stop_price:.2f} "
              f"limit {order.limit_price:.2f}"))
    return PreparedOrderVM(
        offered=True,
        headline=(
            f"BUY {order.quantity} {latch.identity.ticker}   {instrument}   "
            f"{order.duration}"),
        derivation_lines=lines,
        rendered_derivation_columns=columns,
        anchor_fields=tuple(encoded),
        anchor_digest=digest,
        withheld_reason=None, withheld_detail="")


def _zone_position(price, latch: Latch) -> str:
    """The buy zone is the CLOSED interval [latched_pivot, THE ORDERABLE CAP],
    compared at display precision.

    THE UPPER BOUND IS `mandate_limit_price`, NOT `round(zone_cap, 2)` (Codex
    R1 MAJOR on the 2026-08-03 display fix). Fixing the DISPLAYED cap while
    leaving this comparison on the rounded raw cap put a contradiction in two
    adjacent fields of the same card: for AMN both 37.36 and the cap 37.3581
    round to 37.36, so a 37.36 print read as IN ZONE beside a rendered
    `Zone cap 37.35`.

    And the classifier's own claim is the reason the mandate limit is the right
    bound rather than the tidy one: the latch's resting order caps at 37.35, so
    a 37.36 print CANNOT fill it. "In the buy zone" means "a price this mandate
    could still transact at", and that is bounded by the price the framework can
    actually order -- the same asymmetry as the cap itself (a bound that can
    drift up is not a bound).
    """
    if price is None:
        return "unknown"
    p = round(float(price), _PRICE_DP)
    if p < round(latch.latched_pivot, _PRICE_DP):
        return "below_pivot"
    if p > mandate_limit_price(latch.zone_cap):
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
    # THE REASON BRANCH COMES BEFORE THE STATE MAP, and it has to (OQ-2's
    # Option B): `declined` shares `horizon_expired` with `horizon`, so falling
    # through to `_TERMINAL_STATE_LABELS` would tell the operator that his OWN
    # recorded decision was a deadline running out.
    if latch.clear_reason == "declined":
        session = latch.clear_session.isoformat() if latch.clear_session else "-"
        return f"DECLINED - operator declined on {session}"
    # THE SECOND Option-B REASON. THREE reasons now share `horizon_expired`, so
    # this branch is the surface that tells them apart -- and a WITHDRAWAL is
    # emphatically not a deadline: the framework retracted the mandate on its
    # own structural + directional evidence, which is a claim it owes the
    # operator plainly.
    if latch.clear_reason == "criteria_lapsed":
        session = latch.clear_session.isoformat() if latch.clear_session else "-"
        return f"WITHDRAWN - criteria lapsed on {session}"
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


def _lapse_countdown(latch: Latch, *, sessions: int) -> str:
    """The criteria-lapse countdown, on EVERY live latch.

    IT DISCLOSES THE UNCHECKED SESSIONS RATHER THAN IMPLYING ADJACENCY. The bare
    form "failed 3 of 5" reads as three CONSECUTIVE sessions, when the algorithm
    skips arbitrarily many UNVERIFIABLE ones in between -- three failures
    separated by twenty unchecked runs would render identically to three in a
    row. Making the gaps visible is what stops the countdown itself being a
    false statement, and it is also the condition under which OQ-17's PAUSE is
    sound.

    ONCE `k >= N` THERE ARE **TWO** REASONS A LATCH IS STILL LIVE AND THE CARD
    MUST DISTINGUISH THEM OR IT STATES A FALSEHOOD:

    * the conjuncts REFUSED -> "directional condition NOT MET";
    * the conjuncts MET and the feature is UNARMED -> "WOULD WITHDRAW on <s>".

    Printing "directional condition NOT MET" in the second case would be a FLAT
    FALSEHOOD about a condition that DID meet, on the one surface whose entire
    purpose is to show the operator what the unarmed rule is doing.
    `directional_evaluable` does NOT disambiguate them -- it says the test COULD
    run, not that it passed.
    """
    if not latch.is_live:
        return ""
    k = latch.lapse_failed_count
    unchecked = latch.lapse_unchecked_count
    base = f"failed {k} of {sessions} checked sessions ({unchecked} unchecked)"
    # RUNG 1 -- THE HYPOTHETICAL, WHEREVER THE CURRENT STREAK NOW STANDS (Codex
    # R1 MAJOR). The two diagnostic scopes differ on purpose:
    # `lapse_failed_count` is CURRENT-STREAK evidence, `lapse_would_clear_session`
    # is ANALYSIS-WINDOW evidence. So a PASS after a qualifying window resets the
    # count to zero while the would-clear stands. Testing `k >= sessions` first
    # rendered that latch as "failed 0 of 5" and said nothing about the
    # withdrawal the armed rule would already have made -- while `swing latches
    # parity` COUNTS the same latch. The panel and the calibration read must not
    # disagree about one fact.
    if latch.lapse_would_clear_session is not None:
        would = latch.lapse_would_clear_session.isoformat()
        if k >= sessions:
            return (f"{k} failures; threshold {sessions}; WOULD WITHDRAW on "
                    f"{would} - REPORT ONLY (not armed)")
        # The reset streak is stated too: the card must not imply the failures
        # are CURRENT when a later session passed the gate.
        return (f"WOULD WITHDRAW on {would} - REPORT ONLY (not armed); the "
                f"structural streak has since reset to {k} of {sessions}")
    # RUNG 2 -- "NEVER EVALUABLE" OUTRANKS ANY CLAIM ABOUT THE CONJUNCT'S ANSWER,
    # at every k. WITHOUT IT the card shows a failed streak beside a plain live
    # status while the directional predicate had NO DATA -- implying a withdrawal
    # is one session away when it is in fact unreachable -- and, over threshold,
    # it said "directional condition NOT MET" about a condition that was never
    # evaluated at all. `directional_evaluable is False` is precisely the
    # statement that it could not be.
    if not latch.directional_evaluable:
        head = (f"{k} failures; threshold {sessions}"
                if k >= sessions else base)
        return (f"{head}; directional test NOT EVALUABLE "
                f"({latch.directional_block_reason})")
    # RUNG 3 -- the conjuncts ran and REFUSED. Only reachable once the two
    # statements above are false, which is what makes this one true.
    if k >= sessions:
        return (f"{k} failures; threshold {sessions}; directional condition "
                "NOT MET")
    return base


def _lapse_detail(latch: Latch) -> str:
    """The sessions NAMED, and the UNVERIFIABLE causes -- straight off the
    `Latch`.

    A card that carried only COUNTS could satisfy neither the gap disclosure the
    PAUSE rule depends on nor the conflict signal OQ-15 requires, without either
    inventing fields or recomputing the streak in the view."""
    parts: list[str] = []
    if latch.lapse_failed_sessions:
        parts.append("failed: " + ", ".join(
            d.isoformat() for d in latch.lapse_failed_sessions))
    if latch.lapse_unverifiable_sessions:
        parts.append("unchecked: " + ", ".join(
            f"{d.isoformat()} ({cause})"
            for d, cause in zip(latch.lapse_unverifiable_sessions,
                                latch.lapse_unverifiable_causes, strict=False)))
    if latch.lapse_conflicted_sessions:
        # OQ-15: a same-session verified-PASS/verified-FAIL conflict is a
        # DATA-QUALITY signal about the pipeline. Resolved generously, never
        # silently.
        parts.append("conflicting verdicts: " + ", ".join(
            d.isoformat() for d in latch.lapse_conflicted_sessions))
    return "; ".join(parts)


def _unverifiable_label(latch: Latch) -> str:
    """The off-screen UNVERIFIABLE render (RD's inverted default).

    ONE unchecked session at the TAIL is enough. The claim being withheld is
    "the framework checked this mandate for the session you are about to
    trade", and one unchecked session falsifies it.

    It is a RENDER attribute of a LIVE latch, never a terminal state -- the
    mandate is still live and still fillable, so a terminal would be a false
    statement. The in-tree precedent is exact: zone escape is an attribute of
    `armed`, never a clear reason.
    """
    if not latch.is_live or latch.lapse_unverifiable_tail <= 0:
        return ""
    n = latch.lapse_unverifiable_tail
    plural = "" if n == 1 else "s"
    return (f"UNVERIFIABLE - OFF SCREEN: the framework has not checked this "
            f"mandate for the last {n} evaluated session{plural}")


def _build_row(latch: Latch, *, quote, views, provenance=None,
               prepared_order=None, disposition=None,
               prior_intent_id: str = "",
               lapse_sessions: int = DEFAULT_CRITERIA_LAPSE_SESSIONS) -> LatchRowVM:
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
    prompt = bool(disposition is not None and disposition.prompt_required)
    return LatchRowVM(
        ticker=latch.identity.ticker,
        fire_date=latch.anchor.isoformat(),
        latched_pivot=_fmt_price(latch.latched_pivot),
        zone_cap=_fmt_cap(latch.zone_cap),
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
        prepared_order=prepared_order,
        disposition="" if disposition is None else disposition.disposition,
        disposition_label=(
            "" if disposition is None
            else _DISPOSITION_LABELS[disposition.disposition]),
        execution_outcome=(
            "" if disposition is None else disposition.execution_outcome),
        prompt_required=prompt,
        # THE PROMPT RIDES ON THE DISPOSITION, never on a separate render flag.
        # It is offered BECAUSE the cell has already been scored as a lapse, and
        # attesting is the operator's opportunity to CORRECT it -- so the option
        # set is exactly the attestation vocabulary and nothing more.
        attest_options=(
            tuple(sorted(
                (value, _ATTEST_OPTION_LABELS[value])
                for value in LATCH_ATTESTED_DISPOSITIONS))
            if prompt or _attested(disposition) else ()),
        prior_intent_id=prior_intent_id,
        attest_correction_available=_attested(disposition),
        attested_disposition=(
            "" if not _attested(disposition)
            else disposition.disposition.removeprefix("attested_")),
        lapse_countdown=_lapse_countdown(latch, sessions=lapse_sessions),
        lapse_detail=_lapse_detail(latch),
        unverifiable_label=_unverifiable_label(latch),
    )


def _attested(disposition) -> bool:
    """Has an attestation already been recorded for this latch?

    Read off the DISPOSITION rather than by re-reading the ledger: the
    `attested_*` dispositions exist precisely because an attestation governs, so
    the two can never disagree about it.
    """
    return bool(disposition is not None
                and disposition.disposition.startswith("attested_"))


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


def _sizing_inputs(conn, cfg, *, nightly_shares: int | None) -> SizingInputs:
    """The config- and policy-derived sizing context, gathered ONCE per render.

    This is the SAME pair the nightly briefing and the dashboard use
    (`current_equity` then `sizing_equity`), and deliberately NOT what
    `POST /trades/sizing-hint` uses -- that surface passes RAW `current_equity`,
    unfloored. That existing divergence is FLAGGED, not fixed: it is a
    `swing/web/routes/trades.py` behaviour change outside this arc's scope, and
    the form states which figure it used so the operator is never guessing.

    The RATE stays `cfg.risk.max_risk_pct` -- the same source every other sizing
    caller uses. The policy id is recorded ALONGSIDE it purely as provenance, so
    a future cfg-vs-policy divergence is visible in the ledger rather than
    invisible; a missing active policy row therefore does NOT withhold the form.
    """
    from swing.data.repos.cash import list_cash
    from swing.trades.equity import (
        current_equity,
        list_all_exitshape_via_fills,
        sizing_equity,
    )
    real_equity = current_equity(
        starting_equity=cfg.account.starting_equity,
        exits=list_all_exitshape_via_fills(conn),
        cash_movements=list_cash(conn))
    floor = cfg.account.risk_equity_floor
    try:
        policy_id = get_active_policy(conn).policy_id
    except Exception as exc:  # noqa: BLE001 -- A6 + the id is PROVENANCE ONLY
        _log.warning("latch panel active risk_policy read degraded: %s", exc)
        policy_id = None
    return SizingInputs(
        real_equity=real_equity, equity_floor=floor,
        sizing_equity=sizing_equity(real_equity=real_equity, floor=floor),
        max_risk_pct=cfg.risk.max_risk_pct,
        position_pct_cap=cfg.sizing.position_pct_cap,
        risk_policy_id=policy_id,
        nightly_recommendation_shares=nightly_shares)


def _nightly_shares(conn, latch: Latch) -> int | None:
    """The nightly briefing's share count FOR THIS FIRE, or None.

    Scoped to the fire's OWN evaluation run and session -- not "the latest
    recommendation for this ticker", which would attach a different night's
    sizing to this mandate.
    """
    row = conn.execute(
        "SELECT shares FROM daily_recommendations WHERE ticker = ? "
        "AND evaluation_run_id = ? AND action_session_date = ? "
        "ORDER BY id DESC LIMIT 1",
        (latch.identity.ticker, latch.identity.evaluation_run_id,
         latch.anchor.isoformat()),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])


_TELEMETRY_HEALTH_LABELS = {
    "ok": "view telemetry: OK",
    "indeterminate": (
        "view telemetry: INDETERMINATE - no beacon witness in this window, so "
        "no away/lapse verdict is asserted"),
    "broken": (
        "view telemetry: BROKEN - the beacon was dark across this window; the "
        "away rate is WITHHELD rather than computed from it"),
}


def _empty_panel(banner: dict, *, reason: str | None, session_date: str) -> LatchPanelVM:
    payload = json.dumps(build_beacon_payload(
        view_session_date="", actionable_ids=(), withheld_ids=()))
    banner = dict(banner)
    banner["session_date"] = session_date
    return LatchPanelVM(
        rows=(), degraded_rows=(), available=reason is None,
        unavailable_reason=reason, live_candidate_ids=(),
        derivation_session="-", horizon_session="-",
        beacon_payload_json=payload,
        orders_payload_json=json.dumps({"view_session_date": ""}),
        intent_payload_json=json.dumps({"view_session_date": ""}),
        telemetry_health_label=_TELEMETRY_HEALTH_LABELS["ok"],
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

        # ===== Arc 21-B: the prepared order, the disposition and the prompt ==
        # The REGIME PRICE is PROVENANCE-gated, exactly as the order fragment
        # gates its all-clear: only a close the archive dates to the derivation
        # session may pick the mandate form. On any other rung the regime is
        # undeterminable and the form is WITHHELD -- from an undated close you
        # may raise a mismatch alarm, but you may not assert a match, and a
        # prepared order IS an assertion (#30).
        health = _panel_telemetry_health(
            conn, displayed, derivation.horizon_session)
        blocks = _panel_prepared_orders(
            conn, cfg, live, quotes=quotes, derivation=derivation,
            view_session_date=derivation.horizon_session.isoformat())
        # THE CLASSIFIER TAKES THE UNFILTERED VIEW SET (Codex exec R2 MAJOR 1).
        # `views_by_latch` is narrowed to THIS session for the card's telemetry
        # echo; the classifier reads the latch's whole covered window, and
        # handing it the narrowed set would discard yesterday's actionable view.
        dispositions, priors = _panel_dispositions(
            conn, displayed,
            views_by_latch=_load_all_views(conn, displayed), health=health,
            # The resolver's as-of bound on the production path (`service.py`
            # `_close` passes `fill_bound=horizon_session`), so the classifier's
            # decision window is the resolver's own rather than a second
            # derivation of it.
            fill_bound=derivation.horizon_session)

        def _row(latch: Latch) -> LatchRowVM:
            quote = quotes.get(latch.identity.ticker) if latch.is_live else None
            return _build_row(
                latch, quote=quote,
                views=views_by_latch.get(latch.identity.candidate_id, ()),
                provenance=(
                    None if quote is None
                    else _close_provenance_for(derivation, latch, quote)),
                prepared_order=blocks.get(latch.identity.candidate_id),
                disposition=dispositions.get(latch.identity.candidate_id),
                prior_intent_id=priors.get(latch.identity.candidate_id, ""),
                # THE N IN FORCE, from the config the derivation actually ran
                # under -- the panel states it so a retroactive change to N is
                # visible rather than silent (section 3.2.1 ruling 7).
                lapse_sessions=getattr(
                    getattr(cfg, "latches", None), "criteria_lapse_sessions",
                    DEFAULT_CRITERIA_LAPSE_SESSIONS),
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
        # THE BEACON PAYLOAD IS SPLIT BY ACTIONABILITY (the R7 CRITICAL). A
        # single `candidate_ids` field records every withheld render as a full
        # "he saw the mandate" view -- and on today's substrate EVERY card is
        # withheld, so the away/lapse split would be computed from renders that
        # never presented a decision. Both silences are wrong, and they are
        # wrong in OPPOSITE directions, which is the tell that the fact has to
        # be RECORDED rather than inferred.
        actionable_ids = [
            cid for cid in live_ids
            if (blocks.get(cid) is not None and blocks[cid].offered)
        ]
        withheld_ids = [cid for cid in live_ids if cid not in set(actionable_ids)]
        # BUILT THROUGH THE NAMED CONTRACT, never hand-spelled (CHARC ruling,
        # 2026-07-30): the reader parses the same names and measures coverage
        # against the same field set, so the two ends cannot drift apart.
        payload = json.dumps(build_beacon_payload(
            view_session_date=derivation.horizon_session.isoformat(),
            actionable_ids=actionable_ids, withheld_ids=withheld_ids))
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
            intent_payload_json=json.dumps({
                "view_session_date": derivation.horizon_session.isoformat()}),
            telemetry_health_verdict=health.verdict,
            telemetry_health_label=_TELEMETRY_HEALTH_LABELS[health.verdict],
            **banner,
        )
    except Exception as exc:  # noqa: BLE001 -- A6: the panel degrades, never 500s
        _log.warning("latch panel degraded: %s", exc)
        return _empty_panel(
            banner, reason="latch derivation unavailable", session_date=session_date)


def _close_provenance_for(derivation, latch: Latch, quote):
    """This latch's `CloseProvenance` for `quote`. ONE quantity, ONE rule.

    Every panel-side consumer of "what may this card claim about its close"
    comes through here: the card's as-of date AND the prepared order. They read
    the same classifier over the same archive map the derivation already
    surfaced, so no new read, no new query and no new DB field -- the panel GET
    stays a pure reader (A4).

    THE SHARING IS THE POINT, not a tidy-up. While the prepared order kept its
    own stamp-equality gate, one card could render `close dated on or before X`
    on its price line and assert `dated X` two lines below it, in one render.
    """
    from swing.latches.orders import classify_close_provenance
    return classify_close_provenance(
        quote=quote,
        derivation_session=derivation.derivation_session,
        bars_through=latch.bars_through,
        archive_closes=derivation.archive_closes.get(latch.identity.ticker, {}),
        archive_status=derivation.archive_status.get(
            latch.identity.ticker, ARCHIVE_STATUS_OK),
    )


def _panel_telemetry_health(conn, latches, horizon_session: date):
    """The beacon's reliability over the displayed window. A6 at every seam.

    The away rate this gates is the number that would justify automating the
    operator's entries, so a silently broken beacon is not a wrong statistic --
    it is a wrong statistic pointed at the biggest pending decision. A read
    failure therefore degrades to `indeterminate`, never to `ok`.
    """
    from swing.latches.classification import TelemetryHealth
    try:
        from swing.data.repos.latch_view_events import list_views_for_latch
        from swing.latches.constants import ACTIONABLE_VIEW_SURFACES
        views: list = []
        for latch in latches:
            views.extend(list_views_for_latch(
                conn, candidate_id=latch.identity.candidate_id,
                surfaces=ACTIONABLE_VIEW_SURFACES))
        return assess_telemetry_health(
            sessions=telemetry_window_sessions(latches, horizon_session),
            latches=latches, views=views)
    except Exception as exc:  # noqa: BLE001 -- A6, and NEVER degrade to `ok`
        _log.warning("latch panel telemetry health degraded: %s", exc)
        return TelemetryHealth(verdict="indeterminate")


def _panel_prepared_orders(
    conn, cfg, live, *, quotes: dict, derivation, view_session_date: str,
) -> dict[int, PreparedOrderVM]:
    """The prepared-order block per LIVE latch. A6: any failure WITHHELDS."""
    out: dict[int, PreparedOrderVM] = {}
    if not live:
        return out
    # TWO DECISIONS, AND ONLY ONE OF THEM IS A SEAM.
    #
    # `expected_mandate_order_type` owns the pivot-vs-close COMPARISON and is
    # never re-implemented here (a test pins that `swing/latches/order_intent.py`
    # carries no independent comparison of its own). It does NOT own the
    # question of whether a price may be handed to it at all -- that is the
    # CALLER's decision, it is made right here, and it is made on the 21-G
    # provenance ladder rather than on a run stamp.
    #
    # A run stamp is only an UPPER BOUND on a close's date (#30), so stamp
    # equality proved nothing and offered a placeable order asserting a date the
    # panel could not stand behind. `may_assert` is rung A: the archive holds a
    # bar dated EXACTLY this session whose close IS the recorded close. Off that
    # rung the price is withheld from the seam, the seam returns no regime, and
    # `compute_prepared_order` withholds the form with its labelled reason --
    # so nothing unproven reaches the operator OR the parity ledger.
    from swing.latches.orders import expected_mandate_order_type
    regime_session_iso = derivation.derivation_session.isoformat()
    for latch in live:
        cid = latch.identity.candidate_id
        try:
            quote = quotes.get(latch.identity.ticker)
            prov = (
                None if quote is None
                else _close_provenance_for(derivation, latch, quote))
            regime_close = (
                prov.price if prov is not None and prov.may_assert else None)
            regime_type = expected_mandate_order_type(
                latched_pivot=latch.latched_pivot, last_close=regime_close)
            sizing = _sizing_inputs(
                conn, cfg, nightly_shares=_nightly_shares(conn, latch))
            result = compute_prepared_order(
                latch=latch, regime_order_type=regime_type,
                regime_close=regime_close,
                # THE COLUMN THAT MADE THIS MERGE-BLOCKING. It is written as
                # FACT into an append-only ledger, and it is now only ever
                # written from a rung-A close -- one the archive dates to
                # EXACTLY this session. A display defect is recoverable; a
                # ledger write is not.
                regime_close_session=(
                    regime_session_iso if regime_close is not None else None),
                sizing_inputs=sizing)
            out[cid] = _build_prepared_order_vm(
                latch, result, view_session_date=view_session_date)
        except Exception as exc:  # noqa: BLE001 -- A6: degrade VISIBLY
            _log.warning(
                "latch prepared order degraded for candidate %s: %s", cid, exc)
            out[cid] = _withheld_block(
                None,
                "No prepared order: the derivation could not be computed for "
                "this latch. The mandate facts are shown; no order is offered.")
    return out


def rederive_prepared_order(conn, cfg, *, candidate_id: int, anchor: date):
    """`(latch, PreparedOrderVM)` for ONE latch, AS OF `anchor`. `(None, None)`
    when the anchor session had no such live latch.

    THE POST-TIME VALIDATION SEAM. `POST /latches/intent` re-derives through
    THIS function -- the SAME code path the GET rendered through -- and then
    COMPARES field by field against the submitted anchor. Re-deriving to
    VALIDATE is not substituting: the handler never swaps the fresh computation
    in for the anchored one, because the ledger's entire value is that the
    recorded framework order is byte-identically what the operator was looking
    at, and a handler that quietly re-sized would record an order he never saw.
    """
    derivation = build_latch_derivation(
        conn, cfg, horizon_session_override=anchor)
    # LIVENESS ONLY -- and a decline now TERMINATES, so a declined latch is NOT
    # re-openable here. THE COST IS REAL AND IS FLAGGED RATHER THAN PAPERED OVER:
    # the operator can end a mandate and cannot take it back, which sits awkwardly
    # beside `build_idempotency_key`'s `prior_intent_id` (there so a CORRECTION
    # keys differently from a REPLAY) and beside `governing_decision` resolving
    # the place/decline family by RECENCY. The RESOLVER honours `decline -> place`
    # correctly; only the recording surface cannot currently produce it.
    #
    # AN EARLIER CUT OF THIS ARC WIDENED THIS FILTER AND IT WAS WRONG-SHAPED, so
    # the reason is recorded here rather than rediscovered. `build_latch_panel_vm`
    # builds prepared-order blocks from `live` alone, so a declined card renders
    # NO decision form -- widening only this POST-time re-derivation therefore
    # created a path reachable ONLY by replaying a form rendered BEFORE the
    # decline. That stale-form path is worse than the missing affordance: a
    # decline can MASK a later fill or invalidation (earliest-date-wins), so
    # erasing it with a late `place` lets the masked terminal become
    # authoritative and persists a placement against a mandate that was already
    # filled or dead.
    #
    # The correction affordance is a RENDER-plus-ROUTE change and belongs with the
    # wave item that already owns its ruled principle -- recording an operator
    # action and alarming on a detected problem are different functions, and the
    # affordance to record must not be gated on the alarm that detects. Building
    # half of it here bought a hole instead of a path.
    live = [lat for lat in derivation.latches if lat.is_live]
    latch = next(
        (lat for lat in live if lat.identity.candidate_id == candidate_id), None)
    if latch is None:
        return None, None
    try:
        quotes = load_last_closes(conn, [latch.identity.ticker])
    except Exception as exc:  # noqa: BLE001 -- A6: a price miss never blocks
        _log.warning("intent re-derivation last-close read degraded: %s", exc)
        quotes = {}
    blocks = _panel_prepared_orders(
        conn, cfg, [latch], quotes=quotes, derivation=derivation,
        view_session_date=derivation.horizon_session.isoformat())
    return latch, blocks.get(candidate_id)


def _family_intents(conn, latch) -> list:
    """Every intent on a latch's WHOLE candidate family, in the canonical order.

    `list_intents_for_latch` is keyed on ONE candidate id; a latch's identity is
    its opening fire PLUS its re-confirmations. Re-sorted by `(recorded_ts,
    intent_id)` after the union because per-candidate reads arrive already sorted
    only WITHIN each candidate, and every "latest by what?" resolution in this arc
    depends on that exact total order.
    """
    rows: list = []
    for cid in sorted(latch.candidate_set):
        rows.extend(list_intents_for_latch(conn, candidate_id=cid))
    rows.sort(key=lambda r: (r.recorded_ts, r.intent_id or 0))
    return rows


def _panel_dispositions(
    conn, latches, *, views_by_latch: dict, health, fill_bound=None,
):
    """`(dispositions, prior_intent_ids)` per displayed latch. A6 at the seam.

    BOTH come off the SAME per-latch intent read. The RULING-3 context anchor is
    a fact about the ledger rows this function has already loaded, so re-reading
    them would be a second read that could disagree with the first about which
    row governs -- the classification and the anchor the form emits must describe
    ONE moment.
    """
    out: dict = {}
    priors: dict = {}
    for latch in latches:
        cid = latch.identity.candidate_id
        try:
            # THE WHOLE CANDIDATE FAMILY, NOT THE FIRE ID ALONE (item 3a). The
            # resolver decides a latch's terminal over `candidate_set` -- the
            # opening fire PLUS its re-confirmations -- so reading only the fire
            # id here lets a decision recorded against a re-confirmation
            # TERMINATE the latch while this classifier never sees it, and the
            # disposition then contradicts the terminal on the same card. Both
            # halves must read the same population or they cannot agree.
            intents = _family_intents(conn, latch)
        except Exception as exc:  # noqa: BLE001 -- A6: a missing 0033 is not a 500
            _log.warning("latch intent read degraded for candidate %s: %s", cid, exc)
            intents = []
        priors[cid] = _prior_intent_id(intents)
        try:
            out[cid] = classify_latch(
                latch=latch, views=views_by_latch.get(cid, ()),
                intents=intents, telemetry_health=health,
                # THE SAME WINDOW THE RESOLVER USED. Without it the disposition
                # and the lifecycle can disagree about one latch -- a mandate
                # cleared by `fill` scored in `decision_r` as a decline.
                decision_bounds=(
                    None if fill_bound is None
                    else decision_bounds_for(latch, fill_bound=fill_bound)))
        except Exception as exc:  # noqa: BLE001 -- A6
            _log.warning(
                "latch classification degraded for candidate %s: %s", cid, exc)
    return out, priors


def _load_all_views(
    conn, latches, *, counted_surfaces: frozenset[str] | None = None,
) -> dict[int, tuple]:
    """EVERY persisted view row per latch, UNFILTERED BY SESSION. Read-only.

    THIS IS THE CLASSIFIER'S INPUT AND `_load_views` IS NOT (Codex exec R2
    MAJOR 1). `_load_views` narrows to the CURRENT session because the card's
    telemetry ECHO is a claim about this visit -- but `classify_latch` reads the
    latch's WHOLE covered window, so feeding it the narrowed set silently
    discards yesterday's actionable view. A terminal latch he demonstrably acted
    under would then fall out of `discipline_lapse` into `away_unseen` or
    `never_actionable`: the instrument losing its own evidence and scoring the
    loss against its subject, which is the one direction RD's rules forbid
    absolutely.
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
    for latch in latches:
        try:
            out[latch.identity.candidate_id] = tuple(list_views_for_latch(
                conn, candidate_id=latch.identity.candidate_id,
                surfaces=counted_surfaces))
        except Exception as exc:  # noqa: BLE001 -- A6
            _log.warning("latch panel telemetry read degraded: %s", exc)
    return out


def _load_views(
    conn, latches, horizon_session: date, *,
    counted_surfaces: frozenset[str] | None = None,
) -> dict[int, tuple]:
    """The persisted view telemetry for THIS session, per latch. Read-only.

    THE SESSION FILTER IS FOR THE ECHO, NOT FOR THE CLASSIFIER. The card's
    telemetry label answers "was this panel opened THIS session", which is a
    claim about this visit; `classify_latch` asks a different question over the
    latch's WHOLE covered window and takes `_load_all_views` instead.

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
class LatchValidityPromptVM:
    """ONE latch's validity prompt -- display-ready, no logic in the template.

    THIS FRAGMENT IS THE ONLY SURFACE THAT CAN ASK THE QUESTION (plan section
    F.3, Codex R8 MAJOR 1). The presence/absence branch needs the LIVE broker
    book; `GET /latches` has no broker knowledge and must not acquire any (A4),
    and `POST /latches/intent` is forbidden from borrowing the Schwab client at
    all -- so the prompt is rendered HERE, by the fragment that already owns the
    borrow and already holds the resting-order set the presence test needs, and
    the intent route merely RECORDS the answer this fragment offered.

    THE PROMPT FIRES IN BOTH DIRECTIONS, and that is not symmetry for its own
    sake (Codex R5 CRITICAL). An absence-only prompt leaves the POSITIVE case --
    an order the broker plainly accepted -- permanently `unknown`, so the
    agreement NUMERATOR (which requires `accepted_by_broker`) could never be
    populated by anything and the report would measure only failures.

    The ASYMMETRY that survives: PRESENCE is direct positive evidence, so the
    framework may PRE-SELECT the answer; ABSENCE is equally consistent with a
    rejection, a cancel and a never-submitted order, so the framework may raise
    the QUESTION and may NOT pre-select an ANSWER. That is *you may raise a
    mismatch alarm but you may not assert a match*, applied to an execution
    outcome instead of to an order shape.
    """

    ticker: str
    candidate_id: int
    branch: str                       # presence | absence
    headline: str
    # NAMES THE DIFFERENCE (Codex R17 CRITICAL, the arc's own worked example).
    # Attribution is to the LATCH, never to the framework order's exact params:
    # FTRE's real resting order is LIMIT 18.89 / 10 sh against a framework
    # LIMIT 18.89 / 9 sh, so an exact-match gate would fire NO prompt on the one
    # case the ledger exists to measure and the +1 quantity delta could never
    # reach it. So the prompt fires on 21-A's latch attribution, pre-fills the
    # OBSERVED params whether or not they match, and SAYS SO when they diverge.
    divergence_note: str
    # Rendered when the observed order cannot be read completely enough to
    # support an `accepted_by_broker` row (the schema requires a COMPLETE
    # observed side). Empty otherwise.
    incomplete_note: str
    parent_place_intent_id: int
    # The RULING-3 context anchor: the latch's governing ledger row AS RENDERED.
    # Empty string when the latch has none.
    prior_intent_id: str
    # The NON-ACCEPTED answers. ALWAYS exactly the enum minus
    # `accepted_by_broker`, on BOTH branches, with nothing pre-selected.
    options: tuple[tuple[str, str], ...]
    # TWO FORMS, NOT ONE RADIO GROUP (Codex exec R6 MAJOR). The model and the
    # migration both require that a NON-accepted validity row carry NO observed
    # order at all -- "an outcome and its evidence must not be able to disagree"
    # -- so a single form that emitted the observed side alongside all four
    # options was UNWRITABLE for three of them, and the incomplete-observation
    # branch was unwritable for all of them: every click 400d against the ledger
    # contract. That is the arc's own signature defect (a control that renders
    # and cannot be submitted) reappearing inside the fix for it.
    #
    # So the observed side rides on its OWN confirm form, and the three
    # non-accepted answers ride on a second form that carries no observed side.
    # This also states the asymmetry better than a pre-selected radio did:
    # PRESENCE is direct positive evidence, so the framework offers a
    # one-click CONFIRM; it still asserts nothing, because nothing is written
    # without his click.
    confirm_available: bool
    confirm_label: str
    actual_fields: tuple[tuple[str, str], ...]
    snapshot_json: str
    view_session_date: str
    # A CORRECTION rather than a QUESTION (Codex exec R6 MAJOR). An answer
    # already exists and this is the affordance to amend it -- RD's ruling 3
    # requires that a correction be possible, and a control the operator cannot
    # reach makes the ledger's append-only correction path a handler capability
    # he can never use.
    is_correction: bool = False
    superseded_outcome: str = ""


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
    #
    # NOT the source of the page-level uncorroborated CLAIM: that is counted off
    # the `stale_regime` notes, so the counts and the labels come from ONE list
    # and cannot fork. This field is what the CLI report and the 21-G tests read.
    form_check_stale_count: int = 0
    # The RENDER-TIME session anchor, carried so the embedded cancel form posts
    # the same anchor the fragment derived against rather than the browser's idea
    # of "now" (the GET/POST TOCTOU the hazard-2 gotcha forbids).
    view_session_date: str = ""
    # How many LIVE latch mandates this render had to check at all. Carried for
    # RD ruling 4: with none, "No alarms." is a claim about an EMPTY SET dressed
    # as a result -- the zero-data state wearing the good state's words.
    live_latch_count: int = 0
    # The validity prompts this render is offering (plan section F.3). EMPTY is
    # the norm: a prompt fires only where a logged `place` intent still has an
    # UNRESOLVED execution outcome.
    validity_prompts: tuple[LatchValidityPromptVM, ...] = ()
    # A FAILED COLLECTOR MUST NOT LOOK LIKE AN ABSENT QUESTION (Codex exec R7
    # MAJOR). Every seam that builds a prompt degrades rather than 500s (A6) --
    # but a silent degrade makes "the prompt could not be built" visually
    # IDENTICAL to "there is no validity question here", and the consequence of
    # the first is that the agreement denominator stays empty for reasons nobody
    # can see. Degrading silently on THIS surface is the arc's own failure mode.
    # Display-ready, empty when nothing failed.
    validity_prompt_degraded: str = ""

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
        if not self.live_latch_count:
            # RD RULING 4 (2026-07-30), the same rule the ledger report now
            # applies to every rate: the ZERO-DATA state must be
            # DISTINGUISHABLE from the GOOD state. With no live mandate there
            # was nothing to alarm ON, so "No alarms." is true, vacuous, and
            # indistinguishable from a clean check of a real order book. This
            # does NOT re-scope the B6 claim -- when there IS a mandate the
            # alarm all-clear stays COMPLETE and unscoped, because every latch
            # really was alarm-checked. It answers the prior question of whether
            # anything was checked at all.
            return ("No live latch mandates to check.",)
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
                f"{_fmt_cap(lat.zone_cap)}); only 1 is reported here - verify "
                f"the others at the broker")
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
                    f"{_fmt_cap(lat.zone_cap)}); stop "
                    f"{_agreement_word(join.order_stop_agrees)}, limit "
                    f"{_agreement_word(join.order_limit_agrees)}{suffix}")
            elif expected_type == MANDATE_ORDER_TYPE_PULLBACK:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (the last close is at or above the "
                    f"latched pivot {lat.latched_pivot:.2f}, so the mandate is "
                    f"a GTC LIMIT at the zone cap {_fmt_cap(lat.zone_cap)}); "
                    f"limit "
                    f"{_agreement_word(join.order_limit_agrees)}{suffix}")
            else:
                disagreement_lines.append(
                    f"{lat.identity.ticker}: resting order does not match the "
                    f"latched mandate (zone cap {_fmt_cap(lat.zone_cap)}); this "
                    f"order "
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
                o, latched_pivot=lat.latched_pivot, last_close=last_close,
                # The mandate's OWN geometry, so the collapsed-zone case (a
                # sub-dollar pivot where cent-flooring leaves cap == pivot) is
                # not reported as a malformed order -- it is what the framework
                # itself emits there.
                zone_cap=lat.zone_cap)
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
                f"{_fmt_cap(lat.zone_cap)}")
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
    # THE VALIDITY PROMPTS. Reached ONLY on the `ok` resolution -- every other
    # branch returned above -- which IS the R8 MAJOR 1 rule: an unknown order
    # book renders no prompt in either direction, because a prompt built on it
    # invites an answer the operator would infer from the panel's own silence.
    intents_by_latch = _intents_by_latch(conn, derivation.latches)
    try:
        validity_prompts, validity_prompt_degraded = _validity_prompts(
            derivation.latches, joins=joins, orders=orders,
            anchor=horizon_session_override, now=_now(),
            intents_by_latch=intents_by_latch)
    except Exception as exc:  # noqa: BLE001 -- A6: the fragment never 500s
        _log.warning("latch validity prompts degraded: %s", exc)
        validity_prompts = ()
        validity_prompt_degraded = (
            f"THE VALIDITY QUESTION COULD NOT BE BUILT AT ALL "
            f"({type(exc).__name__}). Until it renders, no execution outcome "
            "can be recorded and the agreement rate stays unmeasurable. See "
            "the log.")
    return LatchOrdersFragmentVM(
        available=True,
        resolution_kind="ok",
        resolution_detail=resolution.detail,
        alarms=tuple(
            LatchAlarmVM(
                kind=a.kind, ticker=a.ticker,
                latch_candidate_id=a.latch_candidate_id,
                detail=a.detail, severity=a.severity,
                broker_order_id=a.broker_order_id,
                prior_intent_id=_prior_intent_id(
                    intents_by_latch.get(a.latch_candidate_id, ())),
                # A `cancel` row carries the FULL latch identity block, so an
                # order attributable to NO latch cannot be logged against one.
                # The gap is LABELLED rather than left as a silently missing
                # button: the operator still has to cancel it at the broker, and
                # a control that is simply absent reads as "nothing to do here".
                cancel_unavailable_note=(
                    "" if a.broker_order_id is None
                    or a.latch_candidate_id is not None else
                    "This order matches no latch, so there is no mandate to log "
                    "a cancel against. Cancel it at the broker; the ledger "
                    "cannot record a decision about an order it cannot "
                    "attribute."),
            )
            for a in sorted(alarms, key=lambda a: (a.severity != "critical", a.kind))
        ),
        view_session_date=horizon_session_override.isoformat(),
        order_lines=order_lines,
        disagreements=disagreements,
        indeterminate_tickers=indeterminate_tickers,
        multiplicity_notes=tuple(dict.fromkeys(multiplicity_lines)),
        mandate_form_check_skipped=form_check_notes,
        form_check_ran_count=form_check_ran_count,
        form_check_stale_count=form_check_stale_count,
        live_latch_count=sum(1 for lat in derivation.latches if lat.is_live),
        validity_prompts=validity_prompts,
        validity_prompt_degraded=validity_prompt_degraded,
    )


_VALIDITY_OPTION_LABELS = {
    "accepted_by_broker": "Yes - the broker accepted this order",
    "rejected_by_broker": "It was REJECTED by the broker",
    "not_submitted": "I never submitted it",
    "unknown": "I do not know",
}


def _broker_book_digest(orders) -> str:
    """A digest over the BROKER-BOOK STATE, not over the envelope's other keys.

    The two are separate facts and conflating them is how the key roster drifted
    once already. The property this must have (plan Task 7): it CHANGES when a
    non-matching resting order appears while `attributable_order_count` stays 0
    -- a counts-only digest is identical across those two books and cannot tell
    the operator's answer apart from an answer about a different book -- and it
    is UNCHANGED across a reload showing the same book, so a plain refresh does
    not duplicate the ledger row.

    It therefore digests the ORDER SET ITSELF, ordered by `order_id` so the
    broker's response ordering cannot change it, and carries NO timestamp.
    """
    from swing.latches.order_intent import _digest, encode_derivation_value
    parts = ["latch_broker_book_v1"]
    for o in sorted(orders or (), key=lambda x: str(x.order_id)):
        parts.extend([
            str(o.order_id), str(o.ticker), str(o.instruction),
            str(o.order_type), str(o.status), str(o.duration or ""),
            encode_derivation_value("price2", o.limit_price),
            encode_derivation_value("price2", o.stop_price),
            encode_derivation_value("price2", o.quantity),
        ])
    return _digest(*parts)


def _observed_side_is_complete(side: dict) -> bool:
    """Can this observed order support an `accepted_by_broker` row AT ALL?

    The migration requires a COMPLETE observed side on an accepted row -- known
    type, known duration, a limit, a quantity and the broker order id -- because
    the agreement DENOMINATOR requires a known actual side and section G.4's
    exact-linkage claim rests on the captured id. Offering `accepted_by_broker`
    over an order we could not fully read would hand the operator a click that
    the ledger then REFUSES, which is a dead end rather than a measurement. So
    the option is withheld and the reduction is LABELLED on the prompt.

    IT MIRRORS THE ACCEPTED-ROW CONTRACT IN FULL, INCLUDING THE STOP-LEG SHAPE
    (Codex exec R7 MAJOR). A partial mirror is worse than none: a `STOP_LIMIT`
    with no stop trigger, or a `LIMIT` carrying one, passed the earlier predicate
    and rendered the CONFIRM button, and `LatchOrderIntent.__post_init__` then
    refused the POST -- a control that renders and cannot be submitted, which is
    the exact class this whole dispatch exists to close. The prices and the
    quantity are checked positive here for the same reason: the schema's `> 0`
    CHECKs would otherwise reject the click rather than the render.
    """
    from swing.latches.constants import (
        MANDATE_ORDER_TYPE_BREAKOUT,
        MANDATE_ORDER_TYPE_PULLBACK,
        MANDATE_ORDER_TYPES,
    )
    order_type = side.get("order_type")
    stop = side.get("stop_price")
    limit = side.get("limit_price")
    quantity = side.get("quantity")
    if order_type not in MANDATE_ORDER_TYPES:
        return False
    if side.get("duration") in (None, "UNKNOWN"):
        return False
    if limit is None or not (float(limit) > 0):
        return False
    if quantity is None or int(quantity) <= 0:
        return False
    if order_type == MANDATE_ORDER_TYPE_BREAKOUT:
        # A STOP_LIMIT without its trigger is not the order the broker holds.
        if stop is None or not (float(stop) > 0):
            return False
    elif order_type == MANDATE_ORDER_TYPE_PULLBACK and stop is not None:
        # A LIMIT carrying a stop leg is the rejected FTRE shape, and the
        # accepted-row contract forbids it outright.
        return False
    return True


def _divergence_note(delta, framework: dict, observed: dict) -> str:
    """The prompt's own statement of HOW the observed order differs.

    Named field by field rather than as a bare "differs": confirming an order
    the operator can see is not the same as confirming one described to him
    only as non-matching.
    """
    parts: list[str] = []
    if delta.order_type_differs:
        parts.append(f"order type {observed['order_type']} vs "
                     f"{framework['order_type']}")
    if delta.duration_differs:
        parts.append(f"duration {observed['duration']} vs "
                     f"{framework['duration']}")
    if delta.stop_leg == "compared" and delta.stop_price_delta:
        parts.append(f"stop {_fmt_price(observed['stop_price'])} vs "
                     f"{_fmt_price(framework['stop_price'])}")
    elif delta.stop_leg == "one_sided":
        # BOTH SIDES OBSERVED AND THEY DISAGREE ABOUT THE LEG ITSELF (RD ruling,
        # 2026-07-30). It is a difference the operator is being asked to
        # confirm, so it is NAMED -- an order carrying a stop trigger the
        # mandate does not have, or missing one it does, is exactly the FTRE
        # shape divergence.
        parts.append(
            f"stop leg {_fmt_price(observed['stop_price'])} vs "
            f"{_fmt_price(framework['stop_price'])} (present on one side only)")
    elif delta.stop_leg == "unknown":
        parts.append("the stop leg cannot be compared")
    if delta.limit_price_delta:
        parts.append(f"limit {_fmt_price(observed['limit_price'])} vs "
                     f"{_fmt_price(framework['limit_price'])}")
    if delta.quantity_delta:
        parts.append(f"quantity {observed['quantity']} vs "
                     f"{framework['quantity']}")
    if not parts:
        return ""
    return ("This order DIFFERS from the one you logged (" + "; ".join(parts)
            + "). Confirming records BOTH sides, which is how the divergence "
              "reaches the parity measurement.")


def _attributable_orders(join) -> tuple:
    """The resting orders 21-A attributed to THIS latch.

    Derived from the documented invariant -- `orders` is the attributed set plus
    the strays, and `unmatched_orders` IS the stray subset -- rather than by
    slicing `orders` positionally, which would silently mis-partition the moment
    21-A changed its concatenation order.
    """
    stray_ids = {o.order_id for o in join.unmatched_orders}
    return tuple(o for o in join.orders if o.order_id not in stray_ids)


def _prompt_candidates(join, *, ticker_strays=()) -> tuple[tuple, str]:
    """`(candidate resting orders, ambiguity_reason)` for the presence branch.

    A MISPRICED ORDER IS STILL AN OBSERVATION (Codex exec R8 MAJOR). 21-A
    attributes an order to a latch by its FROZEN PRICES, so a real resting
    `LIMIT 18.88` against an `18.89` mandate matches NO latch and travelled only
    as a STRAY -- which routed the prompt down the ABSENCE branch, where no
    `accepted_by_broker` row can be written and no `actual_limit_price` is ever
    captured. The consequence is precise and bad: the ledger could record a
    QUANTITY divergence (21-A does not match on quantity, so the arc's worked
    example survives) and could NEVER record a PRICE divergence -- the one the
    instrument most exists to catch. `limit_price_differs` was unreachable.

    So a UNIQUE stray on this latch's ticker is offered as the candidate, and
    the prompt says plainly that it matches no mandate's frozen prices. Anything
    AMBIGUOUS -- attributable orders alongside strays, or several of either --
    yields no candidate and a REASON, because picking one arbitrarily would put
    an arbitrary `order_id` into an audit row.
    """
    attributable = _attributable_orders(join)
    # `LatchOrderJoin.unmatched_orders` is populated for LIVE latches ONLY
    # (Codex exec R9 MAJOR), so a CLEARED opportunity's unique mispriced order
    # was invisible here and `limit_price_differs` stayed unreachable for
    # exactly the latches whose measurement is FINAL. `ticker_strays` supplies
    # the same set for those, computed once by the caller from the orders that
    # no latch claims.
    strays = tuple(join.unmatched_orders) or tuple(ticker_strays)
    if len(attributable) == 1 and not strays:
        return attributable, ""
    if len(attributable) > 1:
        return (), (
            f"{len(attributable)} resting orders are attributable to this "
            "mandate, so no single broker order id could be recorded against "
            "it. Resolve the duplicates at the broker.")
    if not attributable and len(strays) == 1:
        return strays, ""
    if strays:
        return (), (
            f"{len(attributable) + len(strays)} resting BUY orders on this "
            "ticker could be the one you logged and none is unambiguously it, "
            "so the framework will not guess which order id to record.")
    return (), ""


def _validity_prompt_for(latch, *, join, framework, place, digest,
                         snapshot_ts: str, anchor_iso: str, prior_intent_id: str,
                         is_correction: bool = False,
                         superseded_outcome: str = "", ticker_strays=()):
    """`(prompt, withheld_reason)`. PURE -- every input is passed in.

    EVERY WITHHELD COLLECTOR CARRIES A REASON (Codex exec R8 MAJOR). Returning a
    bare `None` made "the question was withheld" indistinguishable from "there
    was no question", and the multiplicity note that would have explained it is
    generated only for LIVE latches -- so a CLEARED latch with two matched stale
    orders lost its collector in total silence. On this instrument an unexplained
    absence reads as nothing-to-see, which is the failure mode the whole arc is
    built against.
    """
    from swing.latches.constants import (
        LATCH_BROKER_SNAPSHOT_KEYS,
        LATCH_VALIDITY_OUTCOMES,
    )
    from swing.latches.order_intent import compute_order_delta, observed_side_of

    attributable = _attributable_orders(join)
    if len(attributable) != join.matched_order_count:
        # The two ways of counting the attributed set disagree, so the branch
        # gate cannot be trusted -- and the branch decides WHICH question the
        # operator is asked. An unexplainable disagreement withholds.
        _log.warning(
            "latch validity prompt withheld for candidate %s: attributed set "
            "size %s disagrees with the join count %s",
            latch.identity.candidate_id, len(attributable),
            join.matched_order_count)
        return None, (
            "the framework's two counts of the orders attributable to this "
            "mandate disagree, so it will not choose a branch")
    candidates, ambiguity = _prompt_candidates(
        join, ticker_strays=ticker_strays)
    if ambiguity:
        return None, ambiguity
    exact_matches = 0
    for o in attributable:
        delta = compute_order_delta(framework, observed_side_of(o))
        if delta.any_difference is False:
            exact_matches += 1

    branch = "presence" if candidates else "absence"
    envelope = {
        "broker_snapshot_ts": snapshot_ts,
        "broker_snapshot_branch": branch,
        "broker_snapshot_digest": digest,
        "broker_snapshot_session": anchor_iso,
        "attributable_order_count": len(attributable),
        "exact_framework_match_count": exact_matches,
        "indeterminate": bool(join.indeterminate),
    }
    if set(envelope) != set(LATCH_BROKER_SNAPSHOT_KEYS):
        # The emitted set and the set `validity_detail` REQUIRES are ONE object;
        # a drift makes the audit row unwritable, so it fails here rather than
        # at the operator's click.
        _log.warning("latch broker-snapshot roster drift: %s vs %s",
                     sorted(envelope), sorted(LATCH_BROKER_SNAPSHOT_KEYS))
        return None, (
            "the broker-snapshot envelope this answer would carry does not "
            "match what the ledger requires, so the audit row would be "
            "unwritable")

    def _opt(names):
        return tuple((n, _VALIDITY_OPTION_LABELS[n]) for n in sorted(names))

    if branch == "presence":
        order = candidates[0]
        off_mandate = order.order_id in (
            {o.order_id for o in join.unmatched_orders}
            | {o.order_id for o in ticker_strays})
        observed = observed_side_of(order)
        delta = compute_order_delta(framework, observed)
        complete = _observed_side_is_complete(observed)
        actual_fields = (
            ("actual_order_type", str(observed["order_type"] or "UNKNOWN")),
            ("actual_duration", str(observed["duration"])),
            ("actual_stop_price", _fmt_price_or_blank(observed["stop_price"])),
            ("actual_limit_price", _fmt_price_or_blank(observed["limit_price"])),
            ("actual_quantity", (
                "" if observed["quantity"] is None else str(observed["quantity"]))),
            ("actual_broker_order_id", str(order.order_id)),
        )
        headline = (
            f"Your logged {framework['order_type']} "
            f"{_fmt_price(framework['limit_price'])} / "
            f"{framework['quantity']} sh order for {latch.identity.ticker} has a "
            f"resting order at the broker (order {order.order_id}: "
            f"{observed['order_type']} {_fmt_price(observed['limit_price'])} / "
            f"{'' if observed['quantity'] is None else observed['quantity']} sh). "
            "Confirm what happened to it.")
        return LatchValidityPromptVM(
            ticker=latch.identity.ticker,
            candidate_id=latch.identity.candidate_id,
            branch=branch, headline=headline,
            divergence_note=_divergence_note(delta, framework, observed),
            incomplete_note=" ".join(x for x in (
                "" if complete else
                "The broker's copy of this order could not be read completely "
                "(its type, duration or share count is not one the framework "
                "can record), so it cannot be logged as ACCEPTED. Answer only "
                "what you know.",
                "This order matches NO mandate's frozen prices, so the "
                "framework is offering it as the only candidate rather than "
                "recognising it. Confirm only if it IS the order you logged."
                if off_mandate else "",
            ) if x),
            parent_place_intent_id=place.intent_id,
            prior_intent_id=prior_intent_id,
            options=_opt(LATCH_VALIDITY_OUTCOMES - {"accepted_by_broker"}),
            confirm_available=complete,
            confirm_label=(
                f"YES - the broker accepted order {order.order_id}"
                if complete else ""),
            actual_fields=actual_fields if complete else (),
            snapshot_json=json.dumps(envelope, sort_keys=True),
            view_session_date=anchor_iso,
            is_correction=is_correction,
            superseded_outcome=superseded_outcome), ""

    # ABSENCE. "Filled" is deliberately NOT an option: it is not in
    # LATCH_VALIDITY_OUTCOMES, so offering it would force the handler to
    # mislabel or discard the answer -- and it does not need to be offered,
    # because the fill short-circuit already covers that case from data the
    # framework owns.
    headline = (
        f"You logged a {framework['order_type']} "
        f"{_fmt_price(framework['limit_price'])} / {framework['quantity']} sh "
        f"order for {latch.identity.ticker} on {place.action_session_date}. NO "
        "matching resting order is visible at the broker. Was it rejected, "
        "never submitted, or do you not know?")
    return LatchValidityPromptVM(
        ticker=latch.identity.ticker,
        candidate_id=latch.identity.candidate_id,
        branch=branch, headline=headline, divergence_note="", incomplete_note="",
        parent_place_intent_id=place.intent_id,
        prior_intent_id=prior_intent_id,
        options=_opt(LATCH_VALIDITY_OUTCOMES - {"accepted_by_broker"}),
        confirm_available=False, confirm_label="",
        actual_fields=(),
        snapshot_json=json.dumps(envelope, sort_keys=True),
        view_session_date=anchor_iso,
        is_correction=is_correction,
        superseded_outcome=superseded_outcome), ""


def _displaced_cycle_prompts(latch, *, intents, current, digest,
                             snapshot_ts, anchor_iso, prior_intent_id):
    """One control per DISPLACED place cycle -- ANSWERED OR NOT.

    A CHILDLESS DISPLACED CYCLE MAY NOT VANISH (RD ruling, 2026-07-30). It used
    to be skipped outright, so a FAILED FIRST ATTEMPT stayed permanently
    unmeasured while its ACCEPTED RETRY supplied the scored agreement. That is
    not a null -- it is a SUBSTITUTION OF A SUCCESS FOR A FAILURE, which is
    worse than silence, and it fails in the flattering direction.

    So the same absence-branch control is offered with NO recorded answer to
    correct: `is_correction` is False, the heading asks the question rather than
    offering a correction, and the row it writes is that cycle's FIRST answer.
    The intent route already accepts it -- it validates that the parent is a
    `place` on THIS latch, never that the parent is the CURRENT cycle -- and the
    idempotency key is scoped to the submission in context, so a first answer
    for an earlier parent cannot collide with the current cycle's.

    THE REPORT-SIDE HALF IS NOT REDUNDANT WITH THIS. An affordance nobody uses
    is exactly the silence the ruling forbids, so every still-unanswered cycle
    is ALSO counted as `displaced_unanswerable` and disclosed beside the
    agreement rate (`swing/cli_latches.py`).
    """
    import json as _json

    from swing.latches.classification import _order_key
    from swing.latches.constants import (
        LATCH_BROKER_SNAPSHOT_KEYS,
        LATCH_VALIDITY_OUTCOMES,
    )
    out: list[LatchValidityPromptVM] = []
    for place in sorted(
            (i for i in intents if i.intent_kind == "place"), key=_order_key):
        if current is not None and place.intent_id == current.intent_id:
            continue
        children = [
            i for i in intents
            if i.intent_kind == "validity"
            and i.validated_place_intent_id == place.intent_id
        ]
        answered = max(children, key=_order_key) if children else None
        if answered is None and current is None:
            # THE FIRST-ANSWER FORM IS SCOPED TO THE SUBSTITUTION CASE, and the
            # boundary is a RULING boundary, not a convenience. RD's item-2 harm
            # is a failed first attempt going unmeasured WHILE ITS ACCEPTED
            # RETRY SUPPLIES THE SCORED AGREEMENT -- a success standing in for a
            # failure. When the decision family resolved to a DECLINE there is
            # no current place and so nothing is standing in for it, and the
            # earlier R7 ruling is explicit that `place` and `decline` are ONE
            # question: the panel must stop asking about the order he has since
            # declined. Representation for that cycle is therefore the report's
            # NAMED `displaced_unanswerable` category, which still counts it and
            # still discloses it beside the agreement rate.
            continue
        envelope = {
            "broker_snapshot_ts": snapshot_ts,
            # The ABSENCE shape: this correction offers no observed order for a
            # cycle whose order book cannot be reconstructed.
            "broker_snapshot_branch": "absence",
            "broker_snapshot_digest": digest,
            "broker_snapshot_session": anchor_iso,
            "attributable_order_count": 0,
            "exact_framework_match_count": 0,
            "indeterminate": False,
        }
        if set(envelope) != set(LATCH_BROKER_SNAPSHOT_KEYS):  # pragma: no cover
            continue
        out.append(LatchValidityPromptVM(
            ticker=latch.identity.ticker,
            candidate_id=latch.identity.candidate_id,
            branch="absence",
            headline=(
                f"An EARLIER order cycle for {latch.identity.ticker} (place "
                f"intent {place.intent_id}, logged "
                f"{place.action_session_date}) is recorded as "
                f"{answered.validity_outcome}. It is no longer the current "
                "cycle, so its order book cannot be re-read -- but the answer "
                "is still correctable DOWNWARD."
                if answered is not None else
                f"An EARLIER order cycle for {latch.identity.ticker} (place "
                f"intent {place.intent_id}, logged "
                f"{place.action_session_date}) was NEVER ANSWERED, and it is "
                "no longer the current cycle. Until you answer it, it stays "
                "OUT of the agreement rate while the later cycle supplies the "
                "measured one. What happened to that order?"),
            divergence_note="",
            incomplete_note=(
                "Re-asserting ACCEPTANCE for a displaced cycle would require an "
                "observed order side nothing can reconstruct, so only the other "
                "outcomes are offered."),
            parent_place_intent_id=place.intent_id,
            prior_intent_id=prior_intent_id,
            options=tuple(
                (n, _VALIDITY_OPTION_LABELS[n])
                for n in sorted(LATCH_VALIDITY_OUTCOMES
                                - {"accepted_by_broker"})),
            confirm_available=False, confirm_label="",
            actual_fields=(),
            snapshot_json=_json.dumps(envelope, sort_keys=True),
            view_session_date=anchor_iso,
            is_correction=answered is not None,
            superseded_outcome=(
                "" if answered is None else answered.validity_outcome)))
    return tuple(out)


def _fmt_price_or_blank(value) -> str:
    return "" if value is None else f"{float(value):.2f}"


def _intents_by_latch(conn, latches) -> dict[int, list]:
    """Every ledger row per latch, read ONCE per fragment render. A6 at the seam.

    ONE read because two consumers need it -- the validity prompts and the
    per-order cancel control's context anchor -- and two reads could disagree
    about which row governs, so one render would emit two different answers to
    the same question.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    out: dict[int, list] = {}
    for latch in latches:
        cid = latch.identity.candidate_id
        try:
            out[cid] = list(list_intents_for_latch(conn, candidate_id=cid))
        except Exception as exc:  # noqa: BLE001 -- A6: a pre-0033 DB is not a 500
            _log.warning("latch intent read degraded for candidate %s: %s", cid, exc)
    return out


def _validity_prompts(latches, *, joins, orders, anchor: date, now,
                      intents_by_latch: dict):
    """Every validity prompt this render offers. A6 at every seam.

    A PROMPT IS OFFERED ONLY WHERE THE QUESTION IS BOTH OPEN AND ANSWERABLE:

      * a governing `place` intent EXISTS (nothing to validate otherwise), and
      * the outcome is not settled by a FILL -- which is what makes the fill
        SHORT-CIRCUIT structural rather than a second rule: a latch cleared by
        fill resolves `accepted_by_broker` from the trades ledger, so it never
        reaches a prompt. That is the one place the framework may answer for
        itself, because the evidence is a real position rather than an absence,
        and it is also the one outcome NO testimony may overturn, and
      * the ticker's broker status is not INDETERMINATE (the broker's own answer
        is unknown, so the fragment renders its indeterminate note and no
        prompt), and
      * for the ABSENCE branch, the place intent is from an EARLIER session --
        prompting the same evening he logged the order would be asking him about
        something he has not had a session to do yet.

    `resolution.kind != "ok"` never reaches here at all: the caller returns the
    degraded VM before any join exists, which is the R8 MAJOR 1 rule -- a prompt
    built on an unknown order book invites an answer the operator would infer
    from the panel's own silence.
    """
    from swing.latches.classification import (
        current_cycle_place,
        resolve_execution_outcome_for,
    )
    from swing.latches.order_intent import framework_side_of

    digest = _broker_book_digest(orders)
    snapshot_ts = now.isoformat(timespec="seconds")
    anchor_iso = anchor.isoformat()
    # Resting BUY orders NO latch claims, per ticker. 21-A carries this set on
    # the join for LIVE latches only, so it is recomputed here for the cleared
    # ones -- whose measurement is FINAL and therefore the one that most needs
    # its divergence captured.
    claimed = {
        o.order_id for j in joins.values() for o in _attributable_orders(j)}
    strays_by_ticker: dict[str, list] = {}
    for o in orders or ():
        if o.order_id in claimed:
            continue
        strays_by_ticker.setdefault(o.ticker, []).append(o)
    # A STRAY MAY BE OFFERED TO AT MOST ONE LATCH (Codex exec R10 MAJOR). With
    # an old cleared latch and a newer live latch on the same ticker, one
    # unclaimed broker order was supplied to BOTH prompts and could be persisted
    # as the exact `actual_broker_order_id` of two DISTINCT latch observations --
    # a fabricated agreement on whichever of them it did not belong to, and no
    # schema uniqueness prevents it. Where more than one latch on a ticker could
    # take it, NONE does, and the ambiguity is what the prompt reports.
    eligible: dict[str, int] = {}
    for latch in latches:
        if joins.get(latch.identity.candidate_id) is None:
            continue
        ticker = latch.identity.ticker
        eligible[ticker] = eligible.get(ticker, 0) + 1
    contested = {t for t, n in eligible.items() if n > 1}
    out: list[LatchValidityPromptVM] = []
    degraded: list[str] = []
    withheld_notes: list[str] = []
    for latch in latches:
        cid = latch.identity.candidate_id
        join = joins.get(cid)
        if join is None or join.indeterminate:
            continue
        intents = intents_by_latch.get(cid)
        if intents is None:
            degraded.append(latch.identity.ticker)
            continue
        # THE CURRENT-CYCLE PLACE, NOT MERELY THE LATEST PLACE (Codex exec R7
        # MAJOR). `place` and `decline` are one question, so after
        # `place -> decline` there is no current order to validate and the panel
        # must stop asking about the superseded one; the report discloses it as
        # a displaced cycle instead.
        place = current_cycle_place(intents)
        # A DISPLACED CYCLE'S ANSWER MUST STAY CORRECTABLE, AND THAT IS
        # INDEPENDENT OF WHETHER THE CURRENT CYCLE PRODUCES A PROMPT (Codex exec
        # R9 + R10 MAJOR). Gating it behind the current prompt meant a LATER
        # DECLINE (which makes `current_cycle_place` None), an ambiguous
        # attribution, a same-session deferral, a fill settlement or a degraded
        # current prompt all silently removed it -- so on several branches an
        # erroneous, FLATTERING `accepted_by_broker` stayed browser-uncorrectable
        # after all. It is generated FIRST, from the ledger alone.
        #
        # AND A CHILDLESS DISPLACED CYCLE GETS A FIRST-ANSWER FORM (RD ruling,
        # 2026-07-30): skipping it left a failed first attempt permanently
        # unmeasured while its accepted retry supplied the scored agreement.
        out.extend(_displaced_cycle_prompts(
            latch, intents=intents, current=place, digest=digest,
            snapshot_ts=snapshot_ts, anchor_iso=anchor_iso,
            prior_intent_id=_prior_intent_id(intents)))
        if place is None:
            continue
        framework = framework_side_of(place)
        if framework is None:
            continue
        try:
            outcome = resolve_execution_outcome_for(latch, place, intents)
        except Exception as exc:  # noqa: BLE001 -- A6
            _log.warning(
                "latch execution-outcome read degraded for candidate %s: %s",
                cid, exc)
            degraded.append(latch.identity.ticker)
            continue
        # AN ANSWERED PROMPT BECOMES A CORRECTION CONTROL; IT DOES NOT VANISH
        # (Codex exec R6 MAJOR). Suppressing the form the moment ANY outcome was
        # recorded left an erroneous `accepted_by_broker` uncorrectable through
        # the browser, so the flattering answer stayed governing -- and the
        # append-only correction path the resolver explicitly supports was a
        # handler capability the operator could never use. That is precisely the
        # defect class this dispatch exists to close, and RD's ruling 3 says the
        # governing answer must be his LAST.
        #
        # THE ONE OUTCOME NO TESTIMONY MAY OVERTURN IS A FILL: it is a real
        # position in the trades ledger rather than a recollection, so a
        # fill-settled latch still renders NOTHING. That is the fill
        # short-circuit, unchanged.
        is_correction = outcome != "unknown"
        if is_correction and not any(
                i.intent_kind == "validity"
                and i.validated_place_intent_id == place.intent_id
                for i in intents):
            # Settled by the FILL rather than by an answer -- nothing to correct.
            continue
        strays = (
            () if latch.identity.ticker in contested
            else tuple(strays_by_ticker.get(latch.identity.ticker, ())))
        if (latch.identity.ticker in contested
                and strays_by_ticker.get(latch.identity.ticker)):
            withheld_notes.append(
                f"{latch.identity.ticker}: an unattributed resting BUY order "
                "could belong to more than one mandate on this ticker, so the "
                "framework will not offer it to any of them")
        if (not is_correction
                and not _prompt_candidates(join, ticker_strays=strays)[0]
                and place.action_session_date >= anchor_iso):
            continue
        try:
            prompt, withheld = _validity_prompt_for(
                latch, join=join, framework=framework,
                place=place, digest=digest, snapshot_ts=snapshot_ts,
                anchor_iso=anchor_iso,
                prior_intent_id=_prior_intent_id(intents),
                is_correction=is_correction,
                superseded_outcome=outcome if is_correction else "",
                ticker_strays=strays)
        except Exception as exc:  # noqa: BLE001 -- A6: the fragment never 500s
            _log.warning(
                "latch validity prompt degraded for candidate %s: %s", cid, exc)
            degraded.append(latch.identity.ticker)
            continue
        if prompt is not None:
            out.append(prompt)
        elif withheld:
            # A WITHHELD COLLECTOR IS LABELLED WITH ITS REASON. Silence here
            # reads as "there is no question about this latch", and the
            # multiplicity note that would otherwise explain it is generated for
            # LIVE latches only -- so a CLEARED latch with two stale matched
            # orders lost its collector in total silence.
            withheld_notes.append(f"{latch.identity.ticker}: {withheld}")
    parts: list[str] = []
    if degraded:
        parts.append(
            "THE VALIDITY QUESTION COULD NOT BE BUILT for "
            + ", ".join(sorted(set(degraded)))
            + ". That is NOT the same as there being no question to ask: until "
              "it renders, no execution outcome can be recorded for those "
              "latches and the agreement rate stays unmeasurable. See the log.")
    if withheld_notes:
        parts.append(
            "THE VALIDITY QUESTION IS WITHHELD -- "
            + "; ".join(sorted(set(withheld_notes)))
            + ". No execution outcome can be recorded for these until it is "
              "resolved.")
    return tuple(out), " ".join(parts)


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
    # Arc 21-B. A5: every new LatchPanelVM field MUST be listed here or
    # `declared_banner_fields()` mis-reports it as a base-banner field and the
    # cross-VM banner drift pin breaks.
    "intent_payload_json", "telemetry_health_verdict", "telemetry_health_label",
})


def declared_banner_fields() -> frozenset[str]:
    return frozenset(
        f.name for f in fields(LatchPanelVM) if f.name not in PANEL_SPECIFIC_FIELDS)
