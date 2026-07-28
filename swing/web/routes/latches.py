"""Phase 21 Arc A: the read-only latch panel.

A4 -- THE WRITE SEAM IS DELIBERATE AND IT IS NOT THIS GET. `GET /latches`
writes NOTHING AT ALL: not the view record (that is `POST /latches/view`) and
not a Schwab audit row (the broker join is the lazy `POST /latches/orders`).
"""
from __future__ import annotations

import logging
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
from swing.latches.reader import build_latch_derivation
from swing.web.view_models.latches import build_latch_orders_vm, build_latch_panel_vm

router = APIRouter()
log = logging.getLogger(__name__)

# A trivial flood guard: the panel renders at most a handful of live latches.
_MAX_BEACON_IDS = 200


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


def _parse_beacon_anchor(form) -> tuple[date, list[int]]:
    """The rejection ladder (plan section D). Every branch names its field."""
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

    raw_ids = form.get("candidate_ids")
    if raw_ids is None:
        raise _BeaconRejectedError("candidate_ids", "missing")
    if not isinstance(raw_ids, str):
        raise _BeaconRejectedError("candidate_ids", "must be a comma-separated string")
    parts = [p.strip() for p in raw_ids.split(",") if p.strip()]
    if len(parts) > _MAX_BEACON_IDS:
        raise _BeaconRejectedError(
            "candidate_ids", f"more than {_MAX_BEACON_IDS} ids")
    ids: list[int] = []
    for part in parts:
        # `str.isdigit()` rejects '-3', '1.5', 'true' and 'abc' outright; the
        # explicit > 0 check then rejects '0'.
        if not part.isdigit():
            raise _BeaconRejectedError(
                "candidate_ids", f"{part!r} is not a positive decimal integer")
        value = int(part)
        if value <= 0:
            raise _BeaconRejectedError("candidate_ids", f"{part!r} is not positive")
        ids.append(value)
    return anchor, ids


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
            if _classify_anchor(parsed, action_session_for_run(_now())) == "ok":
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
        anchor, posted_ids = _parse_beacon_anchor(form)
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
        matched = [live[cid] for cid in posted_ids if cid in live]
        if matched:
            viewed_ts = now.isoformat(timespec="seconds")
            with conn:
                for latch in matched:
                    record_view(
                        conn, identity=latch.identity,
                        view_session_date=anchor.isoformat(),
                        viewed_ts=viewed_ts, latch_state=latch.state)
    finally:
        conn.close()
    return Response(status_code=204)
