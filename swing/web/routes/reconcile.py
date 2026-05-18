"""Phase 12.5 #2 Tasks T-2.5 + T-2.6 — web Tier-2 discrepancy-resolution
surface.

T-2.5 added the read-only GET handler for the dedicated form page at
``/reconcile/discrepancy/{discrepancy_id}/resolve``. T-2.6 adds the POST
companion handler + extends the error-template with 3 additional branches
(``anchor_mismatch`` / ``service_error`` / ``db_unavailable``).

Per plan §A T-2.5 + T-2.6 acceptance + spec §4.1 / §4.2:

- ``apply_overrides(request.app.state.cfg)`` at route entry (F14 LOCK;
  Phase 12 Sub-bundle B Codex R1 Critical #1 inheritance).
- ``sqlite3.connect(cfg.paths.db_path)`` + ``try/finally: conn.close()``
  (F13 LOCK; Codex R3 M#3 — connection closure guaranteed on ALL paths
  including early-return 404 / 409).
- 404 branch: ``get_discrepancy(conn, discrepancy_id) is None``.
- 409 branch: ``disc.resolution != 'pending_ambiguity_resolution'`` OR
  ``disc.ambiguity_kind is None`` (defensive — schema CHECK in migration
  0019 normally forbids the second case, but covered for hardening).
- POST happy path: ``apply_tier2_resolution(conn, ...,
  resolved_by_override='operator_web')`` (F2 LOCK — surface attribution
  distinguishability vs CLI's default ``'operator'``).
- POST does NOT open a transaction (F7 LOCK — service layer owns
  BEGIN IMMEDIATE / COMMIT / ROLLBACK; CLAUDE.md "Service-layer ``with
  conn:``" gotcha).
- POST ``ValueError`` catch (Codex R1 M#2 fix; plan §J J2 amendment +
  L-W2 LOCK): re-read the discrepancy on a FRESH connection — if the
  re-read shows terminal state, respond 409 + ``already_resolved``;
  otherwise respond 400 + re-render. Closes the concurrent-resolve race.
- ZERO Schwab API calls in the route (service layer composes them).
- ZERO DB writes outside the service call.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from swing.config_overrides import apply_overrides
from swing.data.repos.reconciliation import get_discrepancy
from swing.evaluation.dates import action_session_for_run
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
)
from swing.trades.reconciliation_ambiguity_choices import get_choice_menu
from swing.trades.reconciliation_auto_correct import (
    AlreadySupersededError,
    CallerHeldTransactionError,
    InvalidOverrideComboError,
    ValidatorRejectedError,
    apply_tier2_resolution,
)
from swing.web.view_models.reconcile import (
    ReconcileDiscrepancyErrorVM,
    _parse_parametric_pick_count,
    build_reconcile_discrepancy_resolve_vm,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _render_error(
    request: Request,
    *,
    status_code: int,
    error_kind: str,
    error_message: str,
    discrepancy_id: int | None,
    unresolved_count: int,
    recent_multi_leg_count: int,
    disc_resolution: str | None = None,
    disc_resolved_by: str | None = None,
    disc_created_at: str | None = None,
) -> Response:
    """Render ``reconcile_discrepancy_resolve_error.html.j2`` with the
    appropriate ``ReconcileDiscrepancyErrorVM``. Used by 404 + 409 paths
    (and T-2.6 will extend with anchor_mismatch + service_error +
    db_unavailable branches)."""
    try:
        session_date = action_session_for_run(datetime.now()).isoformat()
    except Exception:  # pragma: no cover - defensive
        session_date = "n/a"
    vm = ReconcileDiscrepancyErrorVM(
        session_date=session_date,
        error_kind=error_kind,
        error_message=error_message,
        discrepancy_id=discrepancy_id,
        disc_resolution=disc_resolution,
        disc_resolved_by=disc_resolved_by,
        disc_created_at=disc_created_at,
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "reconcile_discrepancy_resolve_error.html.j2",
        {"vm": vm},
        status_code=status_code,
    )


@router.get(
    "/reconcile/discrepancy/{discrepancy_id}/resolve",
    response_class=HTMLResponse,
)
def reconcile_discrepancy_resolve_form(
    request: Request, discrepancy_id: int,
) -> Response:
    """GET — render the operator Tier-2 resolution form page.

    Flow per spec §4.1 + plan §A T-2.5 acceptance:

    1. ``apply_overrides`` on the raw cfg (F14 LOCK).
    2. Open a short-lived ``sqlite3.Connection``; wrap remaining steps in
       try/finally to guarantee closure (F13 LOCK).
    3. ``get_discrepancy(conn, discrepancy_id)`` -> None: 404 + error
       template with ``error_kind='not_found'``.
    4. Resolution not ``pending_ambiguity_resolution`` OR ambiguity_kind
       is NULL: 409 + error template with ``error_kind='already_resolved'``
       (echoes ``disc.resolution`` + ``disc.resolved_by`` +
       ``disc.created_at``).
    5. Happy path: hand off to ``build_reconcile_discrepancy_resolve_vm``
       (T-2.3 builder; read-only on conn) + render
       ``reconcile_discrepancy_resolve.html.j2``.
    """
    # F14 LOCK — apply_overrides at every web route entry. Phase 12 Sub-
    # bundle B Codex R1 Critical #1 inheritance + Sub-bundle 2 T-2.1
    # SchwabStatus route precedent.
    cfg = apply_overrides(request.app.state.cfg)
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        unresolved_count = count_unresolved_material(conn)
        recent_multi_leg_count = count_recent_multi_leg_auto_corrections(conn)
        disc = get_discrepancy(conn, discrepancy_id)
        if disc is None:
            return _render_error(
                request,
                status_code=404,
                error_kind="not_found",
                error_message=(
                    f"No reconciliation discrepancy exists with id "
                    f"{discrepancy_id}."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        if (
            disc.resolution != "pending_ambiguity_resolution"
            or disc.ambiguity_kind is None
        ):
            return _render_error(
                request,
                status_code=409,
                error_kind="already_resolved",
                error_message=(
                    f"Discrepancy {discrepancy_id} is no longer in "
                    f"pending_ambiguity_resolution state."
                ),
                discrepancy_id=discrepancy_id,
                disc_resolution=disc.resolution,
                disc_resolved_by=disc.resolved_by,
                disc_created_at=disc.created_at,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        vm = build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request,
        "reconcile_discrepancy_resolve.html.j2",
        {"vm": vm},
    )


# ---------------------------------------------------------------------------
# Phase 12.5 #2 T-2.6 — POST handler + helpers
# ---------------------------------------------------------------------------


_PARAMETRIC_PICK_PREFIX = "pick_schwab_record_"
_PARAMETRIC_PICK_PAYLOAD_SHAPE = (
    '{"price": X.XX, "quantity": Q, "fill_datetime": "..."}'
)


def _render_form_with_error(
    request: Request,
    conn: sqlite3.Connection,
    discrepancy_id: int,
    *,
    error_band_message: str,
    error_band_field_hint: str | None = None,
    prior_choice_code: str = "",
    prior_custom_value_raw: str = "",
    prior_resolution_reason: str = "",
    prior_ambiguity_kind_at_render: str = "",
) -> Response:
    """Re-render ``reconcile_discrepancy_resolve.html.j2`` at status 400
    with the operator's prior submission preserved + an error band
    explaining the rejection."""
    vm = build_reconcile_discrepancy_resolve_vm(
        conn,
        discrepancy_id,
        prior_choice_code=prior_choice_code,
        prior_custom_value_raw=prior_custom_value_raw,
        prior_resolution_reason=prior_resolution_reason,
        prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
        error_band_message=error_band_message,
        error_band_field_hint=error_band_field_hint,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "reconcile_discrepancy_resolve.html.j2",
        {"vm": vm},
        status_code=400,
    )


def _reread_discrepancy_resolution(
    db_path: str, discrepancy_id: int,
) -> str | None:
    """Fresh-connection re-read of the discrepancy's ``resolution`` column.

    Plan §J J2 amendment + L-W2 LOCK: when ``apply_tier2_resolution``
    raises a ``ValueError``, the route MUST re-read on a FRESH
    ``sqlite3.connect`` so any concurrent writer's COMMIT is visible.
    The original handler conn may carry a snapshot that doesn't reflect
    the concurrent commit. Returns the post-race resolution string, or
    None if the row vanished (defensive).
    """
    fresh = sqlite3.connect(db_path)
    try:
        row = fresh.execute(
            "SELECT resolution FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?",
            (discrepancy_id,),
        ).fetchone()
    finally:
        fresh.close()
    if row is None:
        return None
    return row[0]


@router.post("/reconcile/discrepancy/{discrepancy_id}/resolve")
async def reconcile_discrepancy_resolve_post(  # noqa: PLR0911, PLR0912, PLR0915
    request: Request, discrepancy_id: int,
) -> Response:
    """POST — apply a Tier-2 operator resolution. Spec §4.2 verbatim.

    The handler:

    1. ``apply_overrides`` on raw cfg (F14 LOCK).
    2. Parse form fields with the ``... or None``/``... or ""`` distinctions
       per F6 (CLAUDE.md nullable-vs-CHECK-enum gotcha).
    3. Open a short-lived ``sqlite3.Connection`` (F13 LOCK; try/finally).
    4. Pre-flight read-only checks (404 / 409 / 400 paths).
    5. Service call via ``apply_tier2_resolution`` with
       ``resolved_by_override='operator_web'`` (F2 LOCK).
    6. Catch-ladder for service exceptions per spec §4.2 step 5 — including
       the ``ValueError`` re-read disambiguation per plan §J J2 / L-W2 LOCK.
    7. HTMX success: 204 + ``HX-Redirect: /dashboard?reconcile_resolved=
       {correction_id}`` (F5 LOCK).
    8. Non-HTMX (OriginGuard non-strict): 303 ``RedirectResponse`` byte-for-
       byte mirror of ``swing/web/routes/schwab.py:451``.
    """
    # F14 LOCK
    cfg = apply_overrides(request.app.state.cfg)

    # Step 2 — parse form values.
    form = await request.form()
    choice_code = (form.get("choice_code") or "").strip()
    # F6 LOCK — custom_value is a nullable text column on the audit side;
    # empty string would coerce to "" and miss the NULL semantics. Treat
    # empty/whitespace-only as None.
    raw_custom_value = form.get("custom_value")
    if raw_custom_value is None:
        custom_value_raw: str | None = None
    else:
        custom_value_raw = str(raw_custom_value)
        if custom_value_raw.strip() == "":
            custom_value_raw = None
    resolution_reason = (form.get("resolution_reason") or "").strip()
    ambiguity_kind_at_render = (
        form.get("ambiguity_kind_at_render") or ""
    ).strip()

    # For re-render preservation, keep the operator's ORIGINAL strings
    # (do NOT substitute the trimmed/normalized values — preserve byte-for-
    # byte; matches T-2.4 prior_* preservation discipline).
    prior_choice_code = str(form.get("choice_code") or "")
    prior_custom_value_raw = (
        "" if raw_custom_value is None else str(raw_custom_value)
    )
    prior_resolution_reason = str(form.get("resolution_reason") or "")
    prior_ambiguity_kind_at_render = str(
        form.get("ambiguity_kind_at_render") or ""
    )

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        unresolved_count = count_unresolved_material(conn)
        recent_multi_leg_count = count_recent_multi_leg_auto_corrections(conn)

        # Step 4a — discrepancy existence
        disc = get_discrepancy(conn, discrepancy_id)
        if disc is None:
            return _render_error(
                request,
                status_code=404,
                error_kind="not_found",
                error_message=(
                    f"No reconciliation discrepancy exists with id "
                    f"{discrepancy_id}."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )

        # Step 4b — state guard (terminal or NULL ambiguity_kind)
        if (
            disc.resolution != "pending_ambiguity_resolution"
            or disc.ambiguity_kind is None
        ):
            return _render_error(
                request,
                status_code=409,
                error_kind="already_resolved",
                error_message=(
                    f"Discrepancy {discrepancy_id} is no longer in "
                    f"pending_ambiguity_resolution state."
                ),
                discrepancy_id=discrepancy_id,
                disc_resolution=disc.resolution,
                disc_resolved_by=disc.resolved_by,
                disc_created_at=disc.created_at,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )

        # Step 4c — hidden-anchor (F8 LOCK)
        if ambiguity_kind_at_render == "":
            return _render_error(
                request,
                status_code=400,
                error_kind="anchor_mismatch",
                error_message=(
                    "Form is stale or tampered; please re-open the resolve "
                    "form."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        if disc.ambiguity_kind != ambiguity_kind_at_render:
            return _render_error(
                request,
                status_code=409,
                error_kind="anchor_mismatch",
                error_message=(
                    "Discrepancy state changed since form was rendered; "
                    "please re-open."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )

        # Step 4d — required choice_code
        if choice_code == "":
            return _render_form_with_error(
                request,
                conn,
                discrepancy_id,
                error_band_message="Please select a resolution choice.",
                error_band_field_hint="choice_code",
                prior_choice_code=prior_choice_code,
                prior_custom_value_raw=prior_custom_value_raw,
                prior_resolution_reason=prior_resolution_reason,
                prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
            )

        # Step 4e — required resolution_reason
        if resolution_reason == "":
            return _render_form_with_error(
                request,
                conn,
                discrepancy_id,
                error_band_message="Resolution reason is required.",
                error_band_field_hint="resolution_reason",
                prior_choice_code=prior_choice_code,
                prior_custom_value_raw=prior_custom_value_raw,
                prior_resolution_reason=prior_resolution_reason,
                prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
            )

        # Step 4f — static-menu validation
        menu = get_choice_menu(disc.ambiguity_kind)
        static_codes = {item.code for item in menu}
        is_parametric_pick = (
            disc.ambiguity_kind == "multi_match_within_window"
            and choice_code.startswith(_PARAMETRIC_PICK_PREFIX)
        )

        if choice_code in static_codes:
            menu_item = next(item for item in menu if item.code == choice_code)
            if menu_item.requires_custom_value and custom_value_raw is None:
                shape = (
                    menu_item.expected_payload_shape_description or "(any)"
                )
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message=(
                        f"Choice '{choice_code}' requires --custom-value; "
                        f"expected shape: {shape}"
                    ),
                    error_band_field_hint="custom_value",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )
        elif is_parametric_pick:
            # Step 4g — parametric pick validation
            suffix = choice_code[len(_PARAMETRIC_PICK_PREFIX):]
            try:
                n = int(suffix)
            except ValueError:
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message=(
                        f"Choice '{choice_code}' has non-integer suffix."
                    ),
                    error_band_field_hint="choice_code",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )
            if n < 1:
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message="Pick index must be >= 1.",
                    error_band_field_hint="choice_code",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )
            parsed_count = _parse_parametric_pick_count(disc.resolution_reason)
            if n > parsed_count:
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message=(
                        f"Choice 'pick_schwab_record_{n}' is out of range; "
                        f"Schwab returned {parsed_count} candidates within "
                        f"the match window. Valid range: "
                        f"pick_schwab_record_1 .. "
                        f"pick_schwab_record_{parsed_count}."
                    ),
                    error_band_field_hint="choice_code",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )
            # F10 LOCK — parametric picks ALWAYS require custom_value.
            if custom_value_raw is None:
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message=(
                        f"Choice '{choice_code}' requires --custom-value; "
                        f"expected shape: {_PARAMETRIC_PICK_PAYLOAD_SHAPE}"
                    ),
                    error_band_field_hint="custom_value",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )
        else:
            # Step 4h — no-match branch
            if disc.ambiguity_kind == "multi_match_within_window":
                parsed_count = _parse_parametric_pick_count(
                    disc.resolution_reason,
                )
                valid_choices = sorted(static_codes) + [
                    f"pick_schwab_record_{i + 1}"
                    for i in range(parsed_count)
                ]
            else:
                valid_choices = sorted(static_codes)
            return _render_form_with_error(
                request,
                conn,
                discrepancy_id,
                error_band_message=(
                    f"Unknown choice_code '{choice_code}'. "
                    f"Valid choices: {', '.join(valid_choices)}"
                ),
                error_band_field_hint="choice_code",
                prior_choice_code=prior_choice_code,
                prior_custom_value_raw=prior_custom_value_raw,
                prior_resolution_reason=prior_resolution_reason,
                prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
            )

        # Step 4i — parse custom_value JSON if present.
        custom_payload = None
        if custom_value_raw is not None and len(custom_value_raw.strip()) > 0:
            try:
                custom_payload = json.loads(custom_value_raw)
            except json.JSONDecodeError as exc:
                return _render_form_with_error(
                    request,
                    conn,
                    discrepancy_id,
                    error_band_message=(
                        f"custom_value is not valid JSON: {exc.msg}"
                    ),
                    error_band_field_hint="custom_value",
                    prior_choice_code=prior_choice_code,
                    prior_custom_value_raw=prior_custom_value_raw,
                    prior_resolution_reason=prior_resolution_reason,
                    prior_ambiguity_kind_at_render=(
                        prior_ambiguity_kind_at_render
                    ),
                )

        # Step 5 — service call
        environment = getattr(
            getattr(getattr(cfg, "integrations", None), "schwab", None),
            "environment",
            "production",
        )
        try:
            result = apply_tier2_resolution(
                conn,
                discrepancy_id=discrepancy_id,
                choice_code=choice_code,
                operator_custom_payload=custom_payload,
                operator_reason=resolution_reason,
                resolved_by_override="operator_web",  # F2 LOCK
                environment=environment,
            )
        except CallerHeldTransactionError as exc:
            log.warning("CallerHeldTransactionError")
            return _render_error(
                request,
                status_code=500,
                error_kind="service_error",
                error_message=(
                    "Internal error: caller-held transaction. "
                    f"({type(exc).__name__})"
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        except InvalidOverrideComboError as exc:
            log.warning("InvalidOverrideComboError")
            return _render_error(
                request,
                status_code=500,
                error_kind="service_error",
                error_message=(
                    "Internal error: invalid override combo. "
                    f"({type(exc).__name__})"
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        except ValidatorRejectedError as exc:
            return _render_form_with_error(
                request,
                conn,
                discrepancy_id,
                error_band_message=str(exc),
                error_band_field_hint="custom_value",
                prior_choice_code=prior_choice_code,
                prior_custom_value_raw=prior_custom_value_raw,
                prior_resolution_reason=prior_resolution_reason,
                prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
            )
        except AlreadySupersededError:
            return _render_error(
                request,
                status_code=409,
                error_kind="already_resolved",
                error_message=(
                    "Discrepancy has already been superseded by a prior "
                    "correction; no further action possible."
                ),
                discrepancy_id=discrepancy_id,
                disc_resolution=disc.resolution,
                disc_resolved_by=disc.resolved_by,
                disc_created_at=disc.created_at,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        except ValueError as exc:
            # Plan §J J2 + L-W2 LOCK — re-read on a FRESH connection so a
            # concurrent writer's COMMIT is visible. Same conn would carry
            # a snapshot that misses the race-winner's mutation.
            post_race = _reread_discrepancy_resolution(
                str(cfg.paths.db_path), discrepancy_id,
            )
            if (
                post_race is not None
                and post_race != "pending_ambiguity_resolution"
            ):
                return _render_error(
                    request,
                    status_code=409,
                    error_kind="already_resolved",
                    error_message=(
                        "Another writer resolved this discrepancy "
                        "concurrently."
                    ),
                    discrepancy_id=discrepancy_id,
                    disc_resolution=post_race,
                    disc_resolved_by=None,
                    disc_created_at=disc.created_at,
                    unresolved_count=unresolved_count,
                    recent_multi_leg_count=recent_multi_leg_count,
                )
            return _render_form_with_error(
                request,
                conn,
                discrepancy_id,
                error_band_message=str(exc),
                error_band_field_hint="custom_value",
                prior_choice_code=prior_choice_code,
                prior_custom_value_raw=prior_custom_value_raw,
                prior_resolution_reason=prior_resolution_reason,
                prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
            )
        except sqlite3.OperationalError as exc:
            log.warning("sqlite3.OperationalError: %s", exc)
            return _render_error(
                request,
                status_code=503,
                error_kind="db_unavailable",
                error_message=(
                    "Database is busy; please retry in a moment."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
        except Exception as exc:  # noqa: BLE001 — defense-in-depth
            log.warning(type(exc).__name__)
            return _render_error(
                request,
                status_code=500,
                error_kind="service_error",
                error_message=(
                    "Unexpected internal error while applying resolution."
                ),
                discrepancy_id=discrepancy_id,
                unresolved_count=unresolved_count,
                recent_multi_leg_count=recent_multi_leg_count,
            )
    finally:
        conn.close()

    # Step 7 — success path. F5 LOCK on HTMX.
    correction_id = result.correction_id
    redirect_target = (
        f"/dashboard?reconcile_resolved={correction_id}"
    )
    if request.headers.get("HX-Request") == "true":
        return Response(
            status_code=204,
            headers={"HX-Redirect": redirect_target},
        )
    # Non-HTMX fallback (OriginGuard non-strict / direct form submit).
    return RedirectResponse(url=redirect_target, status_code=303)
