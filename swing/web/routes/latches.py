"""Phase 21 Arc A: the read-only latch panel.

A4 -- THE WRITE SEAM IS DELIBERATE AND IT IS NOT THIS GET. `GET /latches`
writes NOTHING AT ALL: not the view record (that is `POST /latches/view`) and
not a Schwab audit row (the broker join is the lazy `POST /latches/orders`).
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.latch_view_events import record_view
from swing.evaluation.dates import (
    action_session_for_run,
    is_trading_session,
    sessions_behind,
)
from swing.latches.constants import (
    LATCH_ACTUAL_ORDER_TYPES,
    LATCH_ATTESTED_DISPOSITIONS,
    LATCH_BROKER_SNAPSHOT_KEYS,
    LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS,
    LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES,
    LATCH_INTENT_KINDS,
    LATCH_VALIDITY_OUTCOMES,
)
from swing.latches.reader import build_latch_derivation
from swing.web.view_models.latches import build_latch_orders_vm, build_latch_panel_vm

router = APIRouter()
log = logging.getLogger(__name__)

# A trivial flood guard: the panel renders at most a handful of live latches.
_MAX_BEACON_IDS = 200
# A generous bound on a SQLite rowid's decimal length. It exists to keep the
# conversion away from Python's integer-conversion limit on an adversarial
# payload, not to constrain any real id.
_MAX_ROW_ID_DIGITS = 19


def _now() -> datetime:
    """Indirection so tests can freeze the handler clock at ONE place."""
    return datetime.now()


class _BeaconRejectedError(Exception):
    """A validated-input rejection carrying the offending FIELD, so a silently
    broken beacon is diagnosable from the response body."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def _parse_id_list(form, field: str) -> list[int]:
    """One comma-separated positive-integer id list, or a named rejection."""
    raw_ids = form.get(field)
    if raw_ids is None:
        raise _BeaconRejectedError(field, "missing")
    if not isinstance(raw_ids, str):
        raise _BeaconRejectedError(field, "must be a comma-separated string")
    ids: list[int] = []
    for part in (p.strip() for p in raw_ids.split(",") if p.strip()):
        # `str.isdigit()` rejects '-3', '1.5', 'true' and 'abc' outright; the
        # explicit > 0 check then rejects '0'.
        if not part.isdigit():
            raise _BeaconRejectedError(
                field, f"{part!r} is not a positive decimal integer")
        value = int(part)
        if value <= 0:
            raise _BeaconRejectedError(field, f"{part!r} is not positive")
        ids.append(value)
    return ids


def _parse_beacon_anchor(form) -> tuple[date, list[int], list[int]]:
    """The rejection ladder (plan section D). Every branch names its field.

    ARC 21-B REWRITES THE PAYLOAD CONTRACT (Codex R13 MAJOR 3). The single
    `candidate_ids` field is REPLACED by `actionable_candidate_ids` +
    `withheld_candidate_ids`, and this is a rewrite rather than a new kwarg for
    a concrete reason: left on the old contract EVERY WITHHELD RENDER IS STILL
    INGESTED AS A PLAIN VIEW and the whole actionability fix never reaches the
    DB. On today's substrate every card is withheld, so that is not a corner
    case -- it is the entire corpus.

    The two lists are DISJOINT BY CONSTRUCTION: one card was either offered a
    decision or it was not, and an id in BOTH would be the render asserting two
    incompatible facts about one moment. That is a 400, not a silent precedence
    rule -- picking a winner would decide, invisibly, which way the away/lapse
    split is biased.
    """
    raw_session = form.get("view_session_date")
    if raw_session is None:
        raise _BeaconRejectedError("view_session_date", "missing")
    if not isinstance(raw_session, str) or len(raw_session) != 10:
        raise _BeaconRejectedError(
            "view_session_date", "must be exactly a 10-char ISO YYYY-MM-DD date")
    try:
        anchor = date.fromisoformat(raw_session)
    except ValueError as exc:
        raise _BeaconRejectedError(
            "view_session_date", "is not a valid ISO date") from exc
    if anchor.isoformat() != raw_session:
        # THE SAME ROUND-TRIP GUARD AS THE INTENT ROUTE (Codex exec R4 MAJOR 1),
        # applied here because the defect is a CLASS and not an instance: this
        # is the OTHER door into the same session keyspace, and `2026-W31-1`
        # parses AND measures ten characters. Fixing one door and leaving the
        # other is how the next reader concludes the guard exists.
        raise _BeaconRejectedError(
            "view_session_date",
            "must be the CANONICAL YYYY-MM-DD spelling of that date")

    actionable = _parse_id_list(form, "actionable_candidate_ids")
    withheld = _parse_id_list(form, "withheld_candidate_ids")
    # THE CAP APPLIES TO THE UNION, not per list -- otherwise splitting the
    # field would have doubled the flood ceiling as a side effect.
    if len(actionable) + len(withheld) > _MAX_BEACON_IDS:
        raise _BeaconRejectedError(
            "actionable_candidate_ids",
            f"more than {_MAX_BEACON_IDS} ids across both lists")
    overlap = sorted(set(actionable) & set(withheld))
    if overlap:
        raise _BeaconRejectedError(
            "withheld_candidate_ids",
            f"ids {overlap} appear in BOTH lists; a card was either offered a "
            "decision or it was not")
    return anchor, actionable, withheld


def _classify_anchor(anchor: date, current: date) -> str:
    """`ok` | `future` | `not_a_session` | `stale`.

    The session check is load-bearing and is NOT implied by the proximity
    check: `sessions_behind(2026-07-27, 2026-07-26)` is 1 even though
    2026-07-26 is a SUNDAY, so a weekend/holiday date would otherwise pass and
    be written as a `view_session_date` -- corrupting the session keyspace that
    21-B's ledger joins on.
    """
    if anchor > current:
        return "future"
    if not is_trading_session(anchor):
        return "not_a_session"
    if sessions_behind(current, anchor) > 1:
        return "stale"
    return "ok"


def _stale_notice(anchor: date, current: date) -> HTMLResponse:
    return HTMLResponse(
        status_code=409,
        content=(
            "<p class='latch-beacon-stale'>This page is stale (rendered "
            f"for {anchor.isoformat()}; current session is "
            f"{current.isoformat()}). Reload to record your view.</p>"),
    )


def _reject(field: str, reason: str) -> HTMLResponse:
    return HTMLResponse(
        status_code=400,
        content=(
            f"<p class='latch-beacon-error'>beacon rejected: "
            f"{field}: {reason}</p>"),
    )


@router.get("/latches", response_class=HTMLResponse)
def latches_panel(request: Request):
    """The read-only latch panel. Writes NOTHING (A4)."""
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "latches.html.j2", {"vm": vm},
    )


@router.post("/latches/orders", response_class=HTMLResponse)
async def latches_orders_fragment(request: Request):
    """The lazy broker-order-awareness fragment.

    THIS ENDPOINT IS NOT A SAFE METHOD. It performs an AUDITED external Schwab
    call that inserts a `schwab_api_calls` row -- that is a write. It writes NO
    domain row (no `latch_view_events`, no `trades`, no `fills`). It is a POST
    for exactly that reason: calling it GET would be a lie about the method's
    safety, would contradict A4 inside the arc that asserts A4, and would
    expose a real broker call to browser prefetch / preconnect / refresh.

    It carries the SAME render-time session anchor as the beacon, and for the
    same reason: without it the fragment would derive at its own clock and
    could render alarms for a DIFFERENT session than the latch cards the
    operator is looking at.
    """
    anchor: date | None = None
    try:
        form = await request.form()
        raw = form.get("view_session_date")
        if isinstance(raw, str) and len(raw) == 10:
            parsed = date.fromisoformat(raw)
            # STRICTER THAN THE BEACON, deliberately. The beacon's
            # one-session tolerance is sound for TELEMETRY (it records that a
            # view happened, as of the session it happened in). It is NOT sound
            # here: this fragment joins the anchor's latch set to the LIVE
            # broker book, so a stale anchor would judge orders placed or
            # cancelled AFTER that session against the older mandates --
            # manufacturing or silencing an alarm. Alarms must describe one
            # coherent moment.
            if parsed == action_session_for_run(_now()):
                anchor = parsed
    except (ValueError, TypeError):
        anchor = None
    except Exception:  # noqa: BLE001 -- an unparseable body degrades, never 500s
        anchor = None

    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_orders_vm(
            conn, cfg, request.app.state, horizon_session_override=anchor)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "partials/latch_orders.html.j2", {"vm": vm},
    )


@router.post("/latches/view")
async def latches_view_beacon(request: Request) -> Response:
    """Record that the latch panel was viewed while these latches were live.

    A4 seam: the PANEL GET writes nothing; this dedicated POST is the ONLY
    write path.

    The payload is an ANCHOR of what the GET rendered -- the session it was
    rendered FOR and the latch ids it showed as live -- never a source of
    truth. Both fields are VALIDATED, then the handler RE-DERIVES the latches
    AS OF THE ANCHOR SESSION and records the INTERSECTION. It does NOT
    recompute "the latest session" at POST time: that is the GET/POST TOCTOU
    recompute the project's hazard-2 gotcha forbids, and it would either
    misdate or silently DROP a view whose latch changed state between render
    and beacon. Wall-clock timestamps are still SERVER-STAMPED.
    """
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001 -- an unparseable body is a 400, not a 500
        return _reject("body", "could not be parsed as a form")
    try:
        anchor, actionable_ids, withheld_ids = _parse_beacon_anchor(form)
    except _BeaconRejectedError as exc:
        return _reject(exc.field, exc.reason)

    now = _now()
    current = action_session_for_run(now)
    verdict = _classify_anchor(anchor, current)
    if verdict == "future":
        return _reject("view_session_date", "is in the future")
    if verdict == "not_a_session":
        return _reject("view_session_date", "is not an NYSE trading session")
    if verdict == "stale":
        # NOT a silent drop and NOT an acceptance (plan section D). Accepting
        # would WRITE A VIEW RECORD FOR A SESSION THE OPERATOR DID NOT VIEW --
        # manufacturing evidence in the flattering direction. Dropping silently
        # would bias the record toward a false `away`. So the rejection is made
        # VISIBLE and the operator is told to reload.
        log.warning(
            "latch view beacon rejected as stale: anchor=%s current=%s",
            anchor.isoformat(), current.isoformat())
        return _stale_notice(anchor, current)

    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        # The override rebuilds the ENTIRE render-time context from the anchor,
        # so `now` influences NOTHING that can change a recorded latch state.
        derivation = build_latch_derivation(
            conn, cfg, horizon_session_override=anchor)
        live = {
            latch.identity.candidate_id: latch
            for latch in derivation.latches if latch.is_live
        }
        # EACH LIST IS INTERSECTED WITH THE LIVE SET INDEPENDENTLY. The
        # intersection is the EXISTENCE gate 21-A already ships -- a forged id
        # writes nothing.
        #
        # THE RENDER-TIME CLAIM IS THE DATUM AND THE RE-DERIVATION DOES NOT
        # OVERRIDE IT (Codex R11 MAJOR 3). `actionable` is a fact about WHAT THE
        # OPERATOR WAS SHOWN, and a card that WAS offered when he looked does not
        # stop having been offered because the latch moved a moment later.
        # Recording "the weaker claim" on disagreement sounds conservative and is
        # actually a corruption: it would manufacture a `never_actionable` for a
        # mandate he was genuinely presented with. So actionability comes from
        # WHICH LIST the id arrived in. This is not a retreat from
        # validate-do-not-trust -- the intent handler still refuses a mutated
        # framework anchor outright, because THERE the payload asserts a
        # computation the server owns. Here the payload reports a RENDER, which
        # only the render can know, so the server's job is BOUNDING it.
        matched = [
            (live[cid], actionable)
            for actionable, ids in ((1, actionable_ids), (0, withheld_ids))
            for cid in ids if cid in live
        ]
        if matched:
            viewed_ts = now.isoformat(timespec="seconds")
            try:
                with conn:
                    for latch, actionable in matched:
                        record_view(
                            conn, identity=latch.identity,
                            view_session_date=anchor.isoformat(),
                            viewed_ts=viewed_ts, latch_state=latch.state,
                            surface="latch_panel", actionable=actionable)
            except sqlite3.Error as exc:
                # A6: the telemetry beacon is an OBSERVER. A schema rejection
                # (e.g. the identity-coherence trigger) must be logged loudly
                # and degrade, never 500 the operator's page.
                log.warning("latch view beacon write rejected: %s", exc)
                return HTMLResponse(
                    status_code=409,
                    content=("<p class='latch-beacon-error'>view telemetry "
                             "could not be recorded; see the log.</p>"))
    finally:
        conn.close()
    return Response(status_code=204)


# =====================================================================
# Arc 21-B Task 7 -- POST /latches/intent. LOG-ONLY: NOTHING is sent to the
# broker on any branch. The write path is 21-C, behind an operator-signed L2
# endpoint diff.
# =====================================================================
_INTENT_SURFACE = "latch_panel"

# The kinds that submit a FRAMEWORK BLOCK and therefore get the field-by-field
# re-derivation comparison. `validity` / `cancel` / `attest` submit none (the
# schema makes one unwritable on them), so the handler MUST NOT invent a
# comparison -- it would 409 every attestation the moment the derivation moved,
# which for an aged prompt is always.
_DECISION_KINDS = frozenset({"place", "decline"})

# The SEMANTIC answer fields PER KIND -- exactly the ones that kind PERSISTS.
#
# THE ROSTER MIRRORS THE MIGRATION'S PER-KIND SHAPE EXCLUSIONS, and it is one
# object rather than an inline list at each site. A key that digested a field
# the row DISCARDS would change on input the ledger throws away, so one decision
# could occupy two append-only rows; a key that OMITTED a field the row keeps
# would collapse two different answers onto one row and lose the second.
_ANSWER_FIELDS_BY_KIND: dict[str, tuple[str, ...]] = {
    "place": (),
    "decline": ("decline_reason",),
    "cancel": ("actual_broker_order_id",),
    "attest": ("attested_disposition", "actual_broker_order_id"),
    "validity": (
        "actual_order_type", "actual_duration", "actual_stop_price",
        "actual_limit_price", "actual_quantity", "actual_broker_order_id",
        "validity_outcome",
    ),
}


class _GovernanceUnknownError(Exception):
    """The latch's governing row could not be established.

    A DISTINCT signal rather than `None`, because `None` legitimately means
    "this latch has no rows yet" -- and collapsing the two is exactly how the
    superseded-key safeguard failed open.
    """


class _IntentRejectedError(Exception):
    """A 400 carrying the offending FIELD, so a rejected submit is diagnosable
    from the response body rather than from the log."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


def _reject_intent(field: str, reason: str) -> HTMLResponse:
    return HTMLResponse(
        status_code=400,
        content=(f"<section class='latch-intent-error'>intent rejected: "
                 f"{field}: {reason}</section>"))


def _conflict(detail: str) -> HTMLResponse:
    """A 409 fragment. The root is a `section`, NEVER a `tr` (the
    `makeFragment` synthetic-table-wrap gotcha), and it is only VISIBLE at all
    because `base.html.j2` keeps the `htmx.config.responseHandling` 4xx-swap
    override."""
    return HTMLResponse(
        status_code=409,
        content=f"<section class='latch-intent-stale'>{detail}</section>")


def _required_str(form, field: str) -> str:
    raw = form.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise _IntentRejectedError(field, "missing or blank")
    return raw.strip()


def _parse_positive_int(field: str, text: str) -> int:
    """The ONE guarded decimal-integer parse. Every integer field routes here.

    `str.isdigit()` IS NOT A SAFE GUARD FOR `int()` (Codex exec R7 + R8 MAJOR).
    It is TRUE for Unicode digit characters such as `²` and `١`, on which `int()`
    RAISES; a sufficiently long ASCII digit string trips Python's own
    integer-conversion limit and raises for the same reason. Either way a
    reachable client-controlled payload 500s instead of being named and refused.

    THE CLASS, NOT THE INSTANCE. R7 fixed this on `prior_intent_id` ALONE and R8
    found `candidate_id`, `validated_place_intent_id` and `actual_quantity`
    still holding it -- so the parse lives in ONE function every integer field
    calls, and a new integer field cannot reintroduce it by being written the
    obvious way.
    """
    if (not text.isascii() or not text.isdigit()
            or len(text) > _MAX_ROW_ID_DIGITS):
        raise _IntentRejectedError(
            field, f"{text!r} is not a positive decimal integer")
    try:
        value = int(text)
    except ValueError as exc:  # pragma: no cover -- belt behind the guard above
        raise _IntentRejectedError(
            field, f"{text!r} is not a decimal integer") from exc
    if value <= 0:
        raise _IntentRejectedError(field, f"{text!r} is not positive")
    return value


def _positive_int(form, field: str) -> int:
    return _parse_positive_int(field, _required_str(form, field))


def _optional_price(form, field: str) -> float | None:
    raw = form.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise _IntentRejectedError(field, f"{raw!r} is not a number") from exc
    if not math.isfinite(value):
        # `> 0` IS NOT A FINITENESS TEST (Codex exec R4 MAJOR 4). `float("inf")`
        # parses, satisfies `> 0`, survives `round(_, 2)`, and satisfies the
        # model's and the schema's `> 0` CHECKs too -- so an infinite OBSERVED
        # price would persist as authoritative broker evidence and the agreement
        # report would then compute a fabricated divergence off it. The one
        # place a measurement must refuse a number is where the number is not
        # one.
        raise _IntentRejectedError(field, "must be a finite number")
    if not (value > 0):
        raise _IntentRejectedError(field, "must be greater than zero")
    return round(value, 2)


def _optional_qty(form, field: str) -> int | None:
    raw = form.get(field)
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None
    return _parse_positive_int(field, str(raw).strip())


def _canonical_optional_id(form, field: str) -> str:
    """An optional row id as its CANONICAL decimal spelling, or `""`.

    IT IS KEY MATERIAL, so it is REFUSED rather than normalised when it does not
    round-trip: `007` and `7` name one row, and silently accepting both would
    key ONE decision as TWO on an append-only ledger -- the same hazard the
    canonical-session guard closes one field over, arriving through a different
    field. A shape rejection that NAMES the field is diagnosable; a silent
    normalisation is a second spelling nobody knows exists.
    """
    raw = form.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return ""
    text = str(raw).strip()
    # `str.isdigit()` IS NOT A SAFE GUARD FOR `int()` (Codex exec R7 MAJOR).
    # It is TRUE for Unicode digit characters such as `²`, on which `int()`
    # then RAISES -- outside the rejection path, so a reachable client-controlled
    # payload 500s the endpoint instead of being named and refused. And a
    # sufficiently long ASCII digit string trips Python's own integer-conversion
    # limit, which raises for the same reason. So: ASCII-only, length-bounded,
    # and the conversion itself inside the guard. Same class as the
    # `[] in frozenset(...)` unhashable finding two rounds back -- never assume a
    # client-controlled string is the shape a predicate implies.
    value = _parse_positive_int(field, text)
    if str(value) != text:
        # CANONICAL SPELLING, on top of the parse: this field is KEY MATERIAL,
        # so `007` and `7` would key ONE decision as TWO on an append-only
        # ledger. A shape rejection that NAMES the field is diagnosable; a
        # silent normalisation is a second spelling nobody knows exists.
        raise _IntentRejectedError(
            field, f"{text!r} is not the canonical spelling of a positive "
                   "row id")
    return text


def _enum(form, field: str, allowed, *, required: bool) -> str | None:
    raw = form.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise _IntentRejectedError(field, "missing")
        return None
    value = str(raw).strip()
    if value not in allowed:
        raise _IntentRejectedError(
            field, f"{value!r} is not one of {sorted(allowed)}")
    return value


def _normalise_submitted(form) -> dict:
    """The submitted OPERATOR-ANSWER fields, canonicalised. PURE.

    Normalisation runs BEFORE the key is derived and touches NO server state, so
    the load-bearing property holds exactly: EVERY key input is a function of
    the submitted payload alone, which is what lets the shape check precede the
    replay SELECT.

    DURATIONS ARE CANONICALISED, and that is not cosmetic: brokers render `GTC`
    where the framework stores `GOOD_TILL_CANCEL`, so two semantically identical
    answers would otherwise produce different keys AND report a duration
    MISMATCH on an identical order -- a false divergence in the one metric this
    ledger exists to compute, and a duplicate ledger row on a plain reload.
    """
    from swing.latches.order_intent import canonical_duration
    raw_duration = form.get("actual_duration")
    duration = (
        None if raw_duration is None or not str(raw_duration).strip()
        else canonical_duration(raw_duration))
    return {
        "actual_order_type": _enum(
            form, "actual_order_type", LATCH_ACTUAL_ORDER_TYPES, required=False),
        "actual_duration": duration,
        "actual_stop_price": _optional_price(form, "actual_stop_price"),
        "actual_limit_price": _optional_price(form, "actual_limit_price"),
        "actual_quantity": _optional_qty(form, "actual_quantity"),
        "actual_broker_order_id": (
            str(form.get("actual_broker_order_id")).strip()
            if form.get("actual_broker_order_id") else None),
        "decline_reason": (
            str(form.get("decline_reason")).strip()
            if form.get("decline_reason") else None),
        "attested_disposition": _enum(
            form, "attested_disposition", LATCH_ATTESTED_DISPOSITIONS,
            required=False),
        "validity_outcome": _enum(
            form, "validity_outcome", LATCH_VALIDITY_OUTCOMES, required=False),
    }


def _actual_digest(kind: str, answer: dict, *, parent_id: int | None,
                   snapshot_digest: str | None) -> str:
    """Every operator-SUBMITTED semantic field for the kind.

    The ANSWER fields are named explicitly because omitting them lets two
    DIFFERENT answers about the same parent and snapshot (`rejected_by_broker`
    vs `not_submitted`) collide -- so the replay SELECT would return the FIRST
    as a 200 and the second answer would be silently lost.

    It deliberately does NOT cover `broker_snapshot_ts`: that is render-time
    data changing on every reload, so keying on it would give a plain refresh a
    new key and duplicate the row -- falsifying the collapse-on-refresh property
    for the one form that most needs it. The timestamp still drives the
    staleness GATE. A gate is not a key input.

    EVERY numeric answer field goes through the SAME `encode_derivation_value`
    encoding the framework anchor uses (Codex exec R1 MAJOR 3). Stringifying a
    float directly makes the key depend on Python's float `repr` rather than on
    the DECLARED display-precision contract -- `str(18.9)` is `'18.9'` while the
    stored and compared value is the 2dp `18.90`, so the digest and the ledger
    would be reasoning at two different precisions. That is the
    price-precision-parity gotcha arriving through the key instead of through a
    comparison, and it is exactly the class that produces either a duplicate row
    or a silent collapse.

    THE FIELD SET IS SCOPED BY KIND, AND IT MATCHES WHAT THE KIND PERSISTS
    (Codex exec R2 MAJOR 2). Digesting every optional field on every kind lets a
    field the row will DISCARD change the key: a `place` POST carrying a stray
    `actual_duration=DAY` -- which `place` does not store, and which the schema
    makes unstorable on it -- would key differently from the same decision
    without it, so an append-only ledger would gain a SECOND row for one
    decision. The key must partition the SEMANTIC answers, and a field the row
    does not carry is not part of its answer. `_ANSWER_FIELDS_BY_KIND` is the
    single roster; every other site refers to it and states no count, and it
    mirrors the per-kind shape exclusions the migration enforces.
    """
    from swing.latches.order_intent import _digest, encode_derivation_value
    encodings = {
        "actual_stop_price": "price2",
        "actual_limit_price": "price2",
        "actual_quantity": "int",
    }
    parts = ["v1", kind]
    for name in _ANSWER_FIELDS_BY_KIND[kind]:
        value = answer.get(name)
        parts.append(name)
        parts.append(encode_derivation_value(
            encodings.get(name, "text"), value))
    parts.append("validated_place_intent_id")
    parts.append(encode_derivation_value("int", parent_id))
    parts.append("broker_snapshot_digest")
    parts.append(snapshot_digest or "")
    return _digest(*parts)


def _parse_snapshot(form) -> dict:
    """The broker-snapshot envelope, VALIDATED and persisted VERBATIM.

    ONE hidden field carrying every key in `LATCH_BROKER_SNAPSHOT_KEYS` -- not
    separate inputs, which cannot satisfy the envelope contract. The handler
    synthesises NO key: a row whose snapshot the report cannot hydrate would
    make the staleness basis unknowable forever after, on an append-only ledger.
    """
    raw = form.get("broker_snapshot_json")
    if not isinstance(raw, str) or not raw.strip():
        raise _IntentRejectedError("broker_snapshot_json", "missing")
    try:
        envelope = json.loads(raw)
    except ValueError as exc:
        raise _IntentRejectedError(
            "broker_snapshot_json", "is not valid JSON") from exc
    if not isinstance(envelope, dict):
        raise _IntentRejectedError("broker_snapshot_json", "must be an object")
    if set(envelope) != set(LATCH_BROKER_SNAPSHOT_KEYS):
        raise _IntentRejectedError(
            "broker_snapshot_json",
            "must carry EXACTLY the broker-snapshot roster keys; got "
            f"{sorted(envelope)}")
    branch = envelope.get("broker_snapshot_branch")
    if not isinstance(branch, str):
        # MEMBERSHIP-TESTING A CLIENT-CONTROLLED VALUE REQUIRES KNOWING IT IS
        # HASHABLE (Codex exec R5). The roster check passes only KEYS, so a
        # roster-conformant envelope carrying `"broker_snapshot_branch": []`
        # reaches this line and `[] in frozenset(...)` raises
        # `TypeError: unhashable type` -- OUTSIDE the guard, so a reachable
        # payload 500s instead of being named and refused.
        raise _IntentRejectedError(
            "broker_snapshot_branch", "must be a string")
    if branch not in LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES:
        # An `unavailable` book renders NO validity prompt in EITHER direction,
        # so a persisted row asserting an execution outcome against an unknown
        # book would assert it forever with no evidence. The render vocabulary
        # is three-valued; the ANSWER vocabulary is two.
        raise _IntentRejectedError(
            "broker_snapshot_json",
            f"branch {branch!r} may not answer a validity prompt")
    return envelope


def _snapshot_is_fresh(envelope: dict, *, now: datetime, anchor: date) -> bool:
    """The staleness GATE (a validation, never a key input).

    Bounds the realistic failure -- an HONEST answer about a stale view. It does
    NOT defend against a forged local POST, and V1 does not pretend to: on a
    127.0.0.1 single-operator app that threat implies an attacker who can
    already write the DB directly, where a token protects nothing.

    THE WHOLE COMPUTATION IS INSIDE THE GUARD, NOT JUST THE PARSE (Codex exec
    R2 MAJOR 3). `datetime.fromisoformat` happily accepts an OFFSET-AWARE
    timestamp, and subtracting an aware datetime from the naive server clock
    raises `TypeError` -- OUTSIDE a guard that wrapped only the two parses. So a
    payload carrying `...T12:00:00+00:00` would 500 the endpoint instead of
    being refused. Any failure to establish freshness is NOT-FRESH: the gate
    fails CLOSED, because an unverifiable snapshot is exactly the thing it
    exists to refuse.
    """
    try:
        taken = datetime.fromisoformat(str(envelope["broker_snapshot_ts"]))
        session = date.fromisoformat(str(envelope["broker_snapshot_session"]))
        if taken.tzinfo is not None:
            # The render emits a NAIVE server-clock stamp; an aware one did not
            # come from our own fragment, and comparing the two would be a
            # timezone guess dressed as a measurement.
            return False
        if session != anchor:
            return False
        age = (now - taken).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return 0 <= age <= LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS


def _anchor_field_names():
    """`(name, encoding)` for every hidden anchor field the form emits.

    ONE enumeration, GENERATED from the manifest -- the handler does not re-list
    the derivation columns any more than the form does.
    """
    from swing.latches.order_intent import (
        FRAMEWORK_ANCHOR_FIELDS,
        derivation_anchor_fields,
    )
    return tuple(FRAMEWORK_ANCHOR_FIELDS) + derivation_anchor_fields()


def _compare_anchor(form, block) -> list[str]:
    """Field-by-field, at the manifest's own encoding. Returns the DIFFERENCES.

    The comparison walks the SAME manifest the form emitted from, so a
    derivation column added to the DDL cannot be silently omitted here -- and
    the encodings are what make render and POST agree on a float (the
    price-precision-parity gotcha: never a raw float compare).
    """
    diffs: list[str] = []
    for name, current in block.anchor_fields:
        if name in ("view_session_date", "candidate_id"):
            continue
        raw = form.get(name)
        submitted = "" if raw is None else str(raw).strip()
        if submitted != current:
            diffs.append(
                f"{name} was {submitted or '(none)'}, is now "
                f"{current or '(none)'}")
    return diffs


def _stored_anchor_values(form, block) -> tuple[dict, dict]:
    """The framework + derivation columns, taken from what the FORM SUBMITTED.

    Deliberately NOT from the fresh re-derivation. The re-derivation's job was
    to VALIDATE (step 5 already 409'd on any difference); the row records what
    the operator was LOOKING AT, and substituting a freshly computed value would
    quietly store an order he never saw -- the exact claim this ledger exists to
    make true.
    """
    from swing.latches.constants import DERIVATION_FIELD_MANIFEST
    from swing.latches.order_intent import FRAMEWORK_ANCHOR_FIELDS
    numeric = {"price2": float, "pct6": float, "int": int}

    def _decode(encoding: str, raw):
        text = "" if raw is None else str(raw).strip()
        if not text:
            return None
        caster = numeric.get(encoding)
        return caster(text) if caster else text

    framework = {
        name: _decode(enc, form.get(name))
        for name, enc in FRAMEWORK_ANCHOR_FIELDS
    }
    derivation = {
        f.column: _decode(f.encode, form.get(f.column))
        for f in DERIVATION_FIELD_MANIFEST
    }
    return framework, derivation


def _latch_for_identity(conn, cfg, candidate_id: int, anchor: date):
    """The latch for `candidate_id`, LIVE OR TERMINAL, as of `anchor`.

    An attestation is normally given AFTER the latch went terminal -- that is
    the whole point of the prompt -- so a live-set lookup would refuse exactly
    the case the prompt exists to serve.
    """
    derivation = build_latch_derivation(
        conn, cfg, horizon_session_override=anchor)
    return next(
        (lat for lat in derivation.latches
         if lat.identity.candidate_id == candidate_id), None)


def _semantic_replay(conn, *, candidate_id: int, kind: str, anchor_digest: str,
                     actual_digest: str, parent_id: int | None):
    """The GOVERNING row when this submission says EXACTLY what it already says.

    RESTORES THE REFRESH-COLLAPSE PROPERTY THAT `prior_intent_id` BROKE (Codex
    exec R9 MAJOR). The key is content-derived precisely so a REFRESH followed by
    an identical resubmit collapses -- but the ruling-3 context anchor made the
    key depend on the render, so after recording A a reload renders `prior=A` and
    resubmitting the SAME answer produced a NEW key and a duplicate row. Two
    claims in one docstring, only one of them true.

    BOTH PROPERTIES NOW HOLD, because they are about different things:
      * A -> A (no intervening different answer) is a REPLAY -- it says what the
        governing row already says, so it collapses onto it.
      * A -> B -> A IS a correction -- it differs from the governing row B -- so
        it writes, and the operator's LAST answer governs.
    The test is SEMANTIC IDENTITY WITH THE CURRENT GOVERNOR, not the render, so
    no reload can turn a repeat into a second event and no correction can be
    mistaken for a repeat.

    Compared through the SAME digest functions the key is built from, so
    "identical" cannot drift from what the key means by it.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    from swing.latches.constants import DERIVATION_FIELD_MANIFEST
    from swing.latches.order_intent import (
        FRAMEWORK_ANCHOR_FIELDS,
        build_anchor_digest,
    )
    try:
        rows = [r for r in list_intents_for_latch(conn, candidate_id=candidate_id)
                if r.intent_id is not None]
    except sqlite3.Error as exc:
        raise _GovernanceUnknownError from exc
    if not rows:
        return None
    governor = max(rows, key=lambda r: (r.recorded_ts, r.intent_id))
    if governor.intent_kind != kind:
        return None
    if (governor.validated_place_intent_id or None) != (parent_id or None):
        return None
    stored = {
        name: getattr(governor, name, None)
        for name, _ in FRAMEWORK_ANCHOR_FIELDS
    }
    stored.update({
        f.column: getattr(governor, f.column, None)
        for f in DERIVATION_FIELD_MANIFEST
    })
    if build_anchor_digest(
            intent_kind=kind, candidate_id=candidate_id,
            view_session_date=governor.action_session_date,
            values=stored) != anchor_digest:
        return None
    if _stored_actual_digest(governor, kind) != actual_digest:
        return None
    return governor


def _stored_actual_digest(intent, kind: str) -> str:
    """`_actual_digest` over a STORED row -- the same function, same encodings."""
    answer = {
        name: getattr(intent, name, None)
        for name in _ANSWER_FIELDS_BY_KIND[kind]
    }
    detail = getattr(intent, "validity_detail", None)
    snapshot_digest = None
    if detail:
        try:
            snapshot_digest = str(json.loads(detail)["broker_snapshot_digest"])
        except (ValueError, KeyError, TypeError):
            snapshot_digest = None
    return _actual_digest(
        kind, answer, parent_id=intent.validated_place_intent_id,
        snapshot_digest=snapshot_digest)


def _governing_intent_id(conn, candidate_id: int) -> int | None:
    """The latch's GOVERNING ledger row id right now, or `None`.

    The SAME total order the render-time anchor is built from
    (`swing/web/view_models/latches.py:_prior_intent_id`) and the same one every
    "latest by what?" ruling in this arc uses -- `(recorded_ts, intent_id)`,
    with the id tiebreak load-bearing because `recorded_ts` is whole seconds.
    Read here rather than passed, because the question is about NOW rather than
    about the render.
    """
    from swing.data.repos.latch_order_intents import list_intents_for_latch
    try:
        rows = [r for r in list_intents_for_latch(conn, candidate_id=candidate_id)
                if r.intent_id is not None]
    except sqlite3.Error as exc:
        # IT FAILS CLOSED (Codex exec R8 MAJOR). Degrading to "cannot tell" and
        # replaying anyway restores the exact defect this safeguard exists to
        # close: the OLD row comes back, the newer one keeps governing, and the
        # operator's later correction is lost -- the flattering direction. A
        # guard that cannot establish its fact must REFUSE, not wave through.
        log.warning("latch governing-intent read degraded: %s", exc)
        raise _GovernanceUnknownError from exc
    if not rows:
        return None
    return max(rows, key=lambda r: (r.recorded_ts, r.intent_id)).intent_id


def _intent_fragment(request: Request, intent, *, replayed: bool) -> HTMLResponse:
    """The success / replay fragment. Root is a section element, never a tr."""
    return request.app.state.templates.TemplateResponse(
        request, "partials/latch_intent_result.html.j2",
        {"intent": intent, "replayed": replayed},
    )


@router.post("/latches/intent", response_class=HTMLResponse)
async def latches_intent(request: Request):
    """Record ONE operator decision about a prepared order. LOG ONLY.

    THE SEVEN-STEP ORDER IS THE POINT, and each step buys a property with its
    own test:

      1. parse the form                        -> 400 on an unparseable body
      2. SHAPE-validate every field            -> 400 NAMING the offending field
      3. NORMALISE, then derive idempotency_key from the payload ALONE
      4. SELECT by key -> FOUND: REPLAY. 200 + the same intent_id. RETURN HERE:
         NEITHER the anchor staleness check NOR the snapshot freshness check
         runs. Recording the intent is the TERMINAL STATE; once it exists,
         neither a stale anchor nor an aged snapshot is relevant to it. The
         freshness gates exist to stop a stale view producing a NEW row, not to
         punish a resubmit of a row already written.
      5. FIRST-WRITE VALIDATION ONLY: the anchor ladder, the snapshot freshness
         gate (validity only), and the re-derive-and-compare (decision kinds
         only) -> 409
      6. INSERT ... ON CONFLICT(idempotency_key) DO NOTHING -- an INSERT-time
         no-op, NOT INSERT OR REPLACE: no DELETE, no new PK, no cascade, so the
         append-only property holds
      7. re-SELECT by key and return THAT row -- the loser of a concurrent race
         returns the winner's row rather than surfacing an IntegrityError

    This ordering satisfies the SELECT-first idempotency discipline LITERALLY:
    the terminal-state read precedes the expensive/fragile validation.

    IT RETURNS MARKUP, NOT A REDIRECT, AND THAT DEPARTURE IS ARGUED. The
    project's HTMX form contract (204 + HX-Redirect) exists because htmx
    swallows a 303 -- its subject is NAVIGATION. This endpoint must NOT
    navigate: the task is per-latch, there is usually more than one latch on the
    page, and bouncing him after each decision would re-render, re-fire the
    beacon and the broker fragment, and lose his place. So the success response
    swaps the card's own block in place -- the shipped POST /latches/orders and
    POST /prices/refresh shape, both browser-verified.

    NO SCHWAB CALL IS MADE ON ANY BRANCH. The client is never borrowed, no
    schwab_api_calls row is written, and Task 10 pins that BEHAVIOURALLY at the
    HTTP transport rather than by grepping method names.
    """
    from swing.data.models import LatchOrderIntent
    from swing.data.repos.latch_order_intents import (
        get_intent,
        get_intent_by_key,
        record_intent,
    )
    from swing.latches.order_intent import (
        build_anchor_digest,
        build_idempotency_key,
    )
    from swing.web.view_models.latches import rederive_prepared_order

    # --- step 1 ---------------------------------------------------------
    try:
        form = await request.form()
    except Exception:  # noqa: BLE001 -- an unparseable body is a 400, not a 500
        return _reject_intent("body", "could not be parsed as a form")

    # --- step 2 ---------------------------------------------------------
    envelope = None
    parent_id = None
    prior_intent_id = ""
    try:
        kind = _enum(form, "intent_kind", LATCH_INTENT_KINDS, required=True)
        # THE RULING-3 CONTEXT ANCHOR: the row that governed this latch when the
        # form was RENDERED. Validated for SHAPE only -- see
        # `build_idempotency_key` for why the forgery half is scoped out and why
        # a stale one writes an extra row rather than losing one.
        prior_intent_id = _canonical_optional_id(form, "prior_intent_id")
        candidate_id = _positive_int(form, "candidate_id")
        raw_session = _required_str(form, "view_session_date")
        if len(raw_session) != 10:
            raise _IntentRejectedError(
                "view_session_date",
                "must be exactly a 10-char ISO YYYY-MM-DD date")
        try:
            anchor = date.fromisoformat(raw_session)
        except ValueError as exc:
            raise _IntentRejectedError(
                "view_session_date", "is not a valid ISO date") from exc
        if anchor.isoformat() != raw_session:
            # THE SPELLING MUST ROUND-TRIP, NOT MERELY PARSE (Codex exec R4
            # MAJOR 1). `date.fromisoformat` accepts the ISO WEEK form, and
            # `2026-W31-1` is both a valid parse AND exactly ten characters --
            # so the length check does not catch it. The RAW spelling feeds the
            # idempotency key while the STORED session is canonicalised, so the
            # canonical form and its week-date equivalent are ONE decision that
            # keys as TWO: hazard (a) defeated by a spelling. The anchor
            # comparison cannot catch it either, because this field is
            # deliberately exempt from it.
            raise _IntentRejectedError(
                "view_session_date",
                "must be the CANONICAL YYYY-MM-DD spelling of that date")
        answer = _normalise_submitted(form)
        if kind == "validity":
            parent_id = _positive_int(form, "validated_place_intent_id")
            _enum(form, "validity_outcome", LATCH_VALIDITY_OUTCOMES,
                  required=True)
            envelope = _parse_snapshot(form)
        if kind == "decline" and not answer["decline_reason"]:
            raise _IntentRejectedError(
                "decline_reason", "a decline REQUIRES a reason")
        if kind == "attest" and not answer["attested_disposition"]:
            raise _IntentRejectedError(
                "attested_disposition", "an attestation REQUIRES a disposition")
        if kind == "cancel" and not answer["actual_broker_order_id"]:
            # HAZARD (c), at the FIRST of its three layers: a cancel targets a
            # SPECIFIC broker order id, never a ticker. The form does not emit a
            # blank one, this rejects it, and the schema CHECK makes the row
            # unwritable.
            raise _IntentRejectedError(
                "actual_broker_order_id",
                "a cancel REQUIRES the broker order id it targets; a cancel "
                "may never be aimed at a ticker")
    except _IntentRejectedError as exc:
        return _reject_intent(exc.field, exc.reason)

    # --- step 3: the key, from the SUBMITTED PAYLOAD ALONE ----------------
    submitted = {
        name: ("" if form.get(name) is None else str(form.get(name)).strip())
        for name, _ in _anchor_field_names()
    }
    submitted["view_session_date"] = raw_session
    submitted["candidate_id"] = str(candidate_id)
    anchor_digest = build_anchor_digest(
        intent_kind=kind, candidate_id=candidate_id,
        view_session_date=raw_session, values=submitted)
    snapshot_digest = (
        None if envelope is None else str(envelope["broker_snapshot_digest"]))
    key = build_idempotency_key(
        candidate_id=candidate_id, action_session_date=raw_session,
        surface=_INTENT_SURFACE, intent_kind=kind, anchor_digest=anchor_digest,
        actual_digest=_actual_digest(
            kind, answer, parent_id=parent_id,
            snapshot_digest=snapshot_digest),
        validated_place_intent_id=parent_id,
        prior_intent_id=prior_intent_id)

    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        # --- step 4: REPLAY. Returns BEFORE every freshness gate. ---------
        #
        # A KEY MATCH IS A REPLAY ONLY WHILE THAT ROW STILL GOVERNS (Codex exec
        # R6 MAJOR). Two tabs render the same prior; tab one records A then
        # corrects to B; the stale tab later submits A. Its key equals the FIRST
        # A, so an unconditional replay returned that old row and left the
        # flattering B authoritative -- a genuine later correction silently
        # discarded, which is the one direction RD's ruling 3 forbids.
        #
        # REFUSED, NOT SILENTLY RE-KEYED. Re-deriving the key against the
        # CURRENT governor would make the second click of a double-click on THAT
        # submission key differently again and write a duplicate, trading the
        # collapse property for the correction property. A 409 loses NO
        # testimony -- he reloads, sees what actually governs, and answers again
        # against it -- and it is the same refuse-and-say-so posture every other
        # stale anchor on this endpoint takes. A double-click is unaffected: the
        # row the first click wrote IS the current governor.
        existing = get_intent_by_key(conn, idempotency_key=key)
        if existing is not None:
            try:
                governing = _governing_intent_id(conn, candidate_id)
            except _GovernanceUnknownError:
                return _conflict(
                    "This latch's ledger could not be read, so it cannot be "
                    "shown that the row your form matches still governs. "
                    "NOTHING was recorded. Reload and answer again; see the "
                    "log.")
            if governing is not None and governing != existing.intent_id:
                return _conflict(
                    "This form was rendered before a later decision was "
                    "recorded on this latch, so replaying it would return the "
                    "OLDER row and leave the newer one governing. NOTHING was "
                    "recorded. Reload to see what governs now, then answer "
                    "again - your latest answer wins and nothing is "
                    "overwritten.")
            return _intent_fragment(request, existing, replayed=True)

        # --- step 4b: THE SEMANTIC REPLAY --------------------------------
        # The key MISSED, which under the ruling-3 context anchor includes the
        # plain case of a RELOAD followed by the same answer. If this submission
        # says exactly what the governing row already says, it is a repeat and
        # not an event.
        try:
            same = _semantic_replay(
                conn, candidate_id=candidate_id, kind=kind,
                anchor_digest=anchor_digest,
                actual_digest=_actual_digest(
                    kind, answer, parent_id=parent_id,
                    snapshot_digest=snapshot_digest),
                parent_id=parent_id)
        except _GovernanceUnknownError:
            return _conflict(
                "This latch's ledger could not be read, so it cannot be shown "
                "whether this answer is a repeat or a correction. NOTHING was "
                "recorded. Reload and answer again; see the log.")
        if same is not None:
            return _intent_fragment(request, same, replayed=True)

        # --- step 5: FIRST-WRITE VALIDATION ONLY --------------------------
        now = _now()
        current = action_session_for_run(now)
        verdict = _classify_anchor(anchor, current)
        if verdict == "future":
            return _reject_intent("view_session_date", "is in the future")
        if verdict == "not_a_session":
            return _reject_intent(
                "view_session_date", "is not an NYSE trading session")
        if verdict == "stale":
            return _conflict(
                f"This page is stale (rendered for {anchor.isoformat()}; "
                f"current session is {current.isoformat()}). Reload before "
                "recording a decision.")

        action_session_date = anchor.isoformat()
        if kind == "validity":
            if not _snapshot_is_fresh(envelope, now=now, anchor=anchor):
                return _conflict(
                    "The broker order book you answered about is no longer "
                    "current. Reload the order fragment and answer again.")
            parent = get_intent(conn, intent_id=parent_id)
            if parent is None or parent.intent_kind != "place":
                return _reject_intent(
                    "validated_place_intent_id",
                    "does not identify a recorded place intent")
            if parent.candidate_id != candidate_id:
                return _reject_intent(
                    "validated_place_intent_id", "belongs to a different latch")
            # SERVER-COPIED from the parent, NEVER the submitted anchor: a
            # validity row answers for THAT order, and the aged prompt is the
            # NORMAL case, so an anchor-derived value would file a July mandate
            # under August.
            action_session_date = parent.action_session_date

        block = None
        if kind in _DECISION_KINDS:
            latch, block = rederive_prepared_order(
                conn, cfg, candidate_id=candidate_id, anchor=anchor)
            if latch is None:
                return _reject_intent(
                    "candidate_id", "was not a live latch on that session")
            if block is None or not block.offered:
                return _conflict(
                    "The prepared order for this latch is now WITHHELD, so the "
                    "order you were shown can no longer be recorded. Reload.")
            diffs = _compare_anchor(form, block)
            if diffs:
                return _conflict(
                    "The framework order changed since this form was rendered, "
                    "so NOTHING was recorded. Reload and re-read it. Changed: "
                    + "; ".join(diffs))
        else:
            latch = _latch_for_identity(conn, cfg, candidate_id, anchor)
            if latch is None:
                return _reject_intent(
                    "candidate_id", "does not identify a derivable latch")

        # --- steps 6 + 7 --------------------------------------------------
        framework: dict = {}
        derivation: dict = {}
        if block is not None:
            framework, derivation = _stored_anchor_values(form, block)
        # THE MODEL CONSTRUCTION IS INSIDE THE GUARD (Codex exec R2 MAJOR 3).
        # `LatchOrderIntent.__post_init__` mirrors every cross-column shape rule
        # the migration enforces and raises `ValueError` on a violation -- so
        # building the row OUTSIDE the try turned a refusable payload (an
        # `accepted_by_broker` validity answer with an incomplete actual side)
        # into a 500 instead of a visible 400. The dataclass validator and the
        # schema CHECK are the SAME contract; both must degrade the same way.
        try:
            intent = LatchOrderIntent(
                intent_id=None,
                candidate_id=latch.identity.candidate_id,
                evaluation_run_id=latch.identity.evaluation_run_id,
                ticker=latch.identity.ticker,
                detection_date=latch.identity.detection_date,
                pipeline_run_id=latch.identity.pipeline_run_id,
                idempotency_key=key,
                action_session_date=action_session_date,
                # SERVER-STAMPED wall clock. NO timestamp is ever read from the
                # payload (the V1 server-stamp gotcha).
                recorded_ts=now.isoformat(timespec="seconds"),
                surface=_INTENT_SURFACE,
                intent_kind=kind,
                decline_reason=(
                    answer["decline_reason"] if kind == "decline" else None),
                attested_disposition=(
                    answer["attested_disposition"] if kind == "attest" else None),
                validated_place_intent_id=parent_id,
                **framework, **derivation,
                actual_order_type=(
                    answer["actual_order_type"] if kind == "validity" else None),
                actual_duration=(
                    answer["actual_duration"] if kind == "validity" else None),
                actual_stop_price=(
                    answer["actual_stop_price"] if kind == "validity" else None),
                actual_limit_price=(
                    answer["actual_limit_price"] if kind == "validity" else None),
                actual_quantity=(
                    answer["actual_quantity"] if kind == "validity" else None),
                actual_broker_order_id=(
                    answer["actual_broker_order_id"]
                    if kind in ("cancel", "attest", "validity") else None),
                validity_outcome=(
                    answer["validity_outcome"] if kind == "validity" else None),
                validity_detail=(
                    None if envelope is None
                    else json.dumps(envelope, sort_keys=True)),
            )
            with conn:
                stored = record_intent(conn, intent=intent)
        except (sqlite3.IntegrityError, ValueError) as exc:
            log.warning("latch intent rejected by the ledger: %s", exc)
            return _reject_intent(
                "intent", f"was rejected by the ledger contract: {exc}")
    finally:
        conn.close()
    return _intent_fragment(request, stored, replayed=False)
