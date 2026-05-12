"""Config page routes."""
from __future__ import annotations

import copy as _copy
import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from swing.config_overrides import apply_overrides
from swing.config_user import (
    delete_user_override,
    load_user_overrides,
    write_user_overrides,
)
from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_all,
)
from swing.web.view_models.config import build_config_vm

log = logging.getLogger(__name__)

router = APIRouter()

_FIELD_PATHS = tuple(s.path for s in FIELD_REGISTRY)

# Phase 9 T-A.5 cfg-mirror cascade map. Keys are FIELD_REGISTRY paths;
# values are the corresponding risk_policy column. Per spec §3.1.3 only
# ONE Phase-5-surfaced field has a risk_policy counterpart in V1
# (risk_equity_floor → capital_floor_constant_dollars); other risk_policy
# fields are edited via the new `swing config policy` CLI surface (T-A.6).
# web.chase_factor + pipeline.chart_top_n_watch are operational tunables,
# NOT policy — they DO NOT cascade.
_RISK_POLICY_CASCADE_MAP: dict[str, str] = {
    "account.risk_equity_floor": "capital_floor_constant_dollars",
}


def _save_redirect_response(request: Request) -> Response:
    """HTMX-aware redirect.

    Codex R1 Major 2 — htmx.js follows 3xx redirects transparently and swaps
    the followed-response body into the hx-target element. A 303 to /config
    on a HTMX-target POST would inject a full <html> page into the small
    #config-form-result <div>, mangling layout. HX-Redirect tells htmx.js
    to do a real browser navigation instead, which renders the saved banner
    on the freshly-loaded /config page.

    Non-HTMX clients (curl, JS-disabled browsers) keep the standard 303.
    """
    if request.headers.get("HX-Request", "").lower() == "true":
        return Response(status_code=204, headers={"HX-Redirect": "/config?saved=1"})
    return RedirectResponse(url="/config?saved=1", status_code=303)


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request, saved: int = 0):
    cfg = apply_overrides(request.app.state.cfg)
    # Phase 9 T-A.5 Codex R1 Major #3 fix: open a short-lived connection
    # so build_config_vm can detect TOML/risk_policy divergence per spec
    # §3.1.3 R3 Minor #2 ("yellow-banner warning until resolved"). The
    # connection is closed before TemplateResponse renders.
    db_path = request.app.state.cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    try:
        vm = build_config_vm(cfg, saved=bool(saved), conn=conn)
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "config.html.j2", {"vm": vm},
    )


@router.post("/config", response_class=HTMLResponse)
async def config_save(request: Request):
    form = await request.form()
    payload: dict[str, str] = {p: form.get(p, "") for p in _FIELD_PATHS}
    force = form.get("force", "").lower() == "true"

    result = validate_all(payload)

    # Hard errors ALWAYS short-circuit, even with force=true.
    if result.hard_errors:
        return request.app.state.templates.TemplateResponse(
            request, "partials/config_hard_refuse.html.j2",
            {"errors": result.hard_errors, "form_values": dict(payload)},
            status_code=400,
        )

    # Soft warnings + not-force → confirm fragment.
    if result.soft_warnings and not force:
        return request.app.state.templates.TemplateResponse(
            request, "partials/config_soft_warn_confirm.html.j2",
            {"warnings": result.soft_warnings, "form_values": dict(payload)},
            status_code=200,
        )

    # Happy path / force=true → MERGE-semantics write per Codex R1 Critical 1.
    base_cfg = request.app.state.cfg
    eff_cfg = apply_overrides(base_cfg)
    new_overrides: dict = _copy.deepcopy(load_user_overrides())
    cascade_updates: dict[str, object] = {}
    for spec in FIELD_REGISTRY:
        section, key = spec.path.split(".")
        submitted = coerce_value(spec.path, payload[spec.path])
        current_eff = getattr(getattr(eff_cfg, section), key)
        if submitted == current_eff:
            continue  # invariant (a) — no-op for unchanged
        new_overrides.setdefault(section, {})[key] = submitted  # invariant (b)
        # Phase 9 T-A.5: collect risk_policy cascades. Computed BEFORE the
        # write so cascade vs override semantics stay independent (a write
        # failure later doesn't leave a half-applied cascade).
        if spec.path in _RISK_POLICY_CASCADE_MAP:
            cascade_updates[_RISK_POLICY_CASCADE_MAP[spec.path]] = submitted
    write_user_overrides(new_overrides)

    # Phase 9 T-A.5: cfg-mirror cascade. After overrides written, supersede
    # the active risk_policy with the new value(s). Per plan §A.5: only
    # account.risk_equity_floor cascades in V1; other risk_policy fields
    # are edited via the new `swing config policy` CLI (T-A.6).
    #
    # Cascade fires AFTER overrides write so a cascade failure leaves the
    # cfg-side change committed (operator can manually run
    # `swing config policy import-from-toml --field
    # capital_floor_constant_dollars` to reconcile). The next startup's
    # divergence check will surface the gap.
    if cascade_updates:
        from swing.trades.risk_policy import supersede_active_policy

        cascade_conn = sqlite3.connect(base_cfg.paths.db_path)
        try:
            supersede_active_policy(
                cascade_conn,
                field_updates=cascade_updates,
                source="cfg_cascade",
            )
        except Exception:
            log.exception(
                "Phase 9 T-A.5: cfg-cascade to risk_policy failed; "
                "overrides written successfully but policy NOT updated. "
                "Operator: run `swing config policy import-from-toml "
                "--field capital_floor_constant_dollars` to reconcile."
            )
            # Don't propagate — overrides are durable; surface via stderr
            # log + next-startup divergence advisory rather than 500.
        finally:
            cascade_conn.close()

    return _save_redirect_response(request)


@router.post("/config/reset/{field_path}", response_class=HTMLResponse)
async def config_reset(request: Request, field_path: str):
    if field_path not in _FIELD_PATHS:
        raise HTTPException(status_code=404, detail=f"unknown field: {field_path}")
    delete_user_override(field_path)

    # Phase 9 Codex R2 Major #1 fix: when the reset field has a risk_policy
    # mirror, cascade the post-reset effective value to the active policy.
    # Otherwise reset recreates the divergence the cfg-cascade closed.
    if field_path in _RISK_POLICY_CASCADE_MAP:
        from swing.trades.risk_policy import supersede_active_policy

        # Re-read the post-reset effective cfg (override is gone).
        post_reset_cfg = apply_overrides(request.app.state.cfg)
        section, attr = field_path.split(".")
        post_reset_value = getattr(getattr(post_reset_cfg, section), attr)
        policy_field = _RISK_POLICY_CASCADE_MAP[field_path]
        cascade_conn = sqlite3.connect(request.app.state.cfg.paths.db_path)
        try:
            supersede_active_policy(
                cascade_conn,
                field_updates={policy_field: post_reset_value},
                source="cfg_cascade",
                notes=(
                    f"reset {field_path} to {post_reset_value} via "
                    f"POST /config/reset/{field_path}"
                ),
            )
        except Exception:
            log.exception(
                "Phase 9 Codex R2 M#1: reset-cascade to risk_policy "
                "failed; user-config override deleted but policy NOT "
                "updated. Operator: run `swing config policy "
                "import-from-toml --field %s` to reconcile.",
                policy_field,
            )
        finally:
            cascade_conn.close()
    return _save_redirect_response(request)
