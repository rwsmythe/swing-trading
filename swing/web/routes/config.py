"""Config page routes."""
from __future__ import annotations

import copy as _copy

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

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

router = APIRouter()

_FIELD_PATHS = tuple(s.path for s in FIELD_REGISTRY)


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request, saved: int = 0):
    cfg = apply_overrides(request.app.state.cfg)
    vm = build_config_vm(cfg, saved=bool(saved))
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
    for spec in FIELD_REGISTRY:
        section, key = spec.path.split(".")
        submitted = coerce_value(spec.path, payload[spec.path])
        current_eff = getattr(getattr(eff_cfg, section), key)
        if submitted == current_eff:
            continue  # invariant (a) — no-op for unchanged
        new_overrides.setdefault(section, {})[key] = submitted  # invariant (b)
    write_user_overrides(new_overrides)
    return RedirectResponse(url="/config?saved=1", status_code=303)


@router.post("/config/reset/{field_path}", response_class=HTMLResponse)
async def config_reset(request: Request, field_path: str):
    if field_path not in _FIELD_PATHS:
        raise HTTPException(status_code=404, detail=f"unknown field: {field_path}")
    delete_user_override(field_path)
    return RedirectResponse(url="/config?saved=1", status_code=303)
