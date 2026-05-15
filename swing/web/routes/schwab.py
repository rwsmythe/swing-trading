"""Phase 12 Sub-bundle B Task T-B.4 — Schwab OAuth setup web route.

Web counterpart to the existing ``swing schwab setup`` CLI. Single page
+ form lets the operator complete the weekly OAuth re-auth from the
browser instead of dropping to a PowerShell session.

Per dispatch brief §3 T-B.4 acceptance criteria + CLAUDE.md HTMX-form-
driven gotcha family:
- GET /schwab/setup renders the form (authorize URL link + paste-back
  text input). Form sets ``hx-headers='{"HX-Request": "true"}'`` so
  OriginGuard strict-mode accepts the POST (Phase 5 R1 M1 lesson).
- POST /schwab/setup resolves credentials via the cfg cascade
  (``resolve_credentials_env_or_prompt(..., allow_prompt=False)``);
  refusal → 400 + error template + remediation hint.
- POST invokes ``setup_paste_flow_with_callback_url`` (Outcome B from
  dispatch brief §0 STEP 0 LOCK). schwabdev.Client cannot consume a
  callback URL programmatically — its OAuth paste-back blocks on
  ``input(...)``. The service helper manually POSTs to
  /v1/oauth/token + writes a schwabdev-compatible tokens.json so
  subsequent Client construction loads cleanly.
- Success → 204 + ``HX-Redirect: /config`` (T-B.7 deferred; web
  ``/schwab/status`` lives in a follow-up dispatch). Non-HTMX clients
  get a 303 to /config. The /config route is verified to exist via
  route-table assertion in tests (Phase 6 I3 lesson).
- Multi-account web flow is REJECTED in V1 (singleton-only); operator
  must use the CLI for multi-account setup (banked V2 candidate).

T-B.7 disposition: DEFERRED (per dispatch brief §3 T-B.7 decision rule).
Outcome B's material implementation surface drives the defer call.

Architectural reference: ``docs/phase12-bundle-B-schwab-web-ui-
friendliness-executing-plans-dispatch-brief.md`` §3 T-B.4 + §0 STEP 0.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from swing.evaluation.dates import action_session_for_run
from swing.integrations.schwab.auth import (
    _redacted_excerpt,
    _resolve_tokens_db_path,
    resolve_credentials_env_or_prompt,
    setup_paste_flow_with_callback_url,
)
from swing.integrations.schwab.client import (
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
)
from swing.web.view_models.schwab import (
    SchwabSetupErrorVM,
    SchwabSetupVM,
)

log = logging.getLogger(__name__)

router = APIRouter()


# HX-Redirect target after successful setup. T-B.7 deferred → /config
# is the V1 landing page (verified to exist via route-table assertion
# in tests).
_SUCCESS_REDIRECT_TARGET = "/config?schwab_setup=ok"


def _build_authorize_url(client_id: str, callback_url: str) -> str:
    """Construct Schwab's OAuth consent URL — mirrors
    schwabdev/tokens.py:347 ``Tokens.update_refresh_token`` URL shape:
        https://api.schwabapi.com/v1/oauth/authorize?client_id=<...>&redirect_uri=<...>
    """
    return (
        "https://api.schwabapi.com/v1/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={callback_url}"
    )


def _render_form(
    request: Request,
    *,
    vm: SchwabSetupVM,
    status_code: int = 200,
) -> Response:
    return request.app.state.templates.TemplateResponse(
        request,
        "schwab_setup.html.j2",
        {"vm": vm},
        status_code=status_code,
    )


def _render_error(
    request: Request,
    *,
    status_code: int,
    error_message: str,
    remediation_hint: str,
) -> Response:
    try:
        session_date = action_session_for_run(datetime.now()).isoformat()
    except Exception:  # pragma: no cover - defensive
        session_date = "n/a"
    vm = SchwabSetupErrorVM(
        session_date=session_date,
        status_code=status_code,
        error_message=error_message,
        remediation_hint=remediation_hint,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "schwab_setup_error.html.j2",
        {"vm": vm},
        status_code=status_code,
    )


def _build_form_vm(
    *,
    cfg,
    client_id: str | None,
    error_message: str | None = None,
    callback_url_value: str = "",
) -> SchwabSetupVM:
    """Build the SchwabSetupVM for form render.

    When ``client_id`` is None, the authorize URL renders the literal
    placeholder ``<set client_id>`` — the form would 400 on submit (no
    credentials in cascade), but we still want to surface a sensible
    GET render so operators see the page + remediation banner instead
    of a hard 400 on first visit.
    """
    environment = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "environment",
        "production",
    )
    callback_url_cfg = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "callback_url",
        "https://127.0.0.1",
    )
    authorize_url = _build_authorize_url(
        client_id or "<set client_id>",
        callback_url_cfg,
    )
    existing_db = False
    try:
        tokens_path = _resolve_tokens_db_path(environment)
        existing_db = tokens_path.exists()
    except Exception:  # pragma: no cover - defensive
        existing_db = False
    try:
        session_date = action_session_for_run(datetime.now()).isoformat()
    except Exception:  # pragma: no cover
        session_date = "n/a"
    return SchwabSetupVM(
        session_date=session_date,
        environment=environment,
        authorize_url=authorize_url,
        existing_tokens_db_warning=existing_db,
        error_message=error_message,
        callback_url_value=callback_url_value,
    )


@router.get("/schwab/setup", response_class=HTMLResponse)
def schwab_setup_form(request: Request) -> Response:
    """GET — render the OAuth setup form."""
    cfg = request.app.state.cfg
    environment = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "environment",
        "production",
    )
    # Resolve credentials WITHOUT prompting (web context has no stdin).
    # If creds are absent at every tier the form still renders, but
    # surfaces an inline banner pointing the operator at /config.
    try:
        client_id, _client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError as exc:
        # Partial env-tier raises — surface as inline banner.
        vm = _build_form_vm(
            cfg=cfg,
            client_id=None,
            error_message=_redacted_excerpt(exc),
        )
        return _render_form(request, vm=vm)

    error_msg = None
    if client_id is None:
        error_msg = (
            "Schwab credentials not configured. Set "
            "SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars OR run "
            "`swing config set integrations.schwab.client_id <value>` "
            "and `swing config set integrations.schwab.client_secret "
            "<value>` before completing the OAuth flow."
        )
    vm = _build_form_vm(cfg=cfg, client_id=client_id, error_message=error_msg)
    return _render_form(request, vm=vm)


@router.post("/schwab/setup")
async def schwab_setup_post(request: Request) -> Response:
    """POST — exchange operator's pasted callback URL for tokens."""
    cfg = request.app.state.cfg
    environment = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "environment",
        "production",
    )
    form = await request.form()
    callback_url_with_code = (form.get("callback_url") or "").strip()

    # Tier-1: resolve credentials (no prompt in web context).
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError as exc:
        return _render_error(
            request,
            status_code=400,
            error_message=_redacted_excerpt(exc),
            remediation_hint=(
                "Unset partial SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET "
                "env vars OR set both, then retry."
            ),
        )

    if client_id is None or client_secret is None:
        return _render_error(
            request,
            status_code=400,
            error_message=(
                "Schwab credentials are not configured at any tier "
                "(env vars, ~/swing-data/user-config.toml, prompt-N/A)."
            ),
            remediation_hint=(
                "Set credentials via /config or run "
                "`swing config set integrations.schwab.client_id` + "
                "`swing config set integrations.schwab.client_secret` "
                "in a PowerShell session, then retry."
            ),
        )

    if not callback_url_with_code:
        # Re-render form with inline banner (preserves the authorize-URL
        # link + tokens-db warning) rather than the full error template.
        vm = _build_form_vm(
            cfg=cfg,
            client_id=client_id,
            error_message=(
                "Pasted callback URL is required. After authorizing at "
                "Schwab, copy the full address-bar URL and paste here."
            ),
            callback_url_value="",
        )
        return _render_form(request, vm=vm, status_code=400)

    db_path = cfg.paths.db_path
    conn = sqlite3.connect(db_path)
    try:
        summary = setup_paste_flow_with_callback_url(
            cfg,
            environment,
            client_id,
            client_secret,
            callback_url_with_code,
            conn,
            # V1 web LOCK: singleton-only. Multi-account → operator must
            # use the CLI. account_picker stays None so the service helper
            # raises SchwabConfigMissingError on multi-account — caught
            # below for a clean error template.
            account_picker=None,
        )
    except SchwabConfigMissingError as exc:
        return _render_error(
            request,
            status_code=400,
            error_message=_redacted_excerpt(exc),
            remediation_hint=(
                "Multi-account setup is not supported on the web V1; "
                "use `swing schwab setup` CLI which prompts for the "
                "primary account. (Banked V2 candidate: web multi-"
                "account picker.)"
            ),
        )
    except SchwabPipelineActiveError as exc:
        return _render_error(
            request,
            status_code=409,
            error_message=_redacted_excerpt(exc),
            remediation_hint=(
                "Wait for the in-flight pipeline run to finish, then "
                "retry. Check status at /pipeline."
            ),
        )
    except SchwabAuthError as exc:
        return _render_error(
            request,
            status_code=502,
            error_message=_redacted_excerpt(exc),
            remediation_hint=(
                "OAuth exchange failed at Schwab. Verify your client "
                "credentials are correct + retry the authorize flow "
                "(the code expires ~30 seconds after issuance)."
            ),
        )
    except Exception as exc:
        # Broad except-clause — pipeline-boundary discipline (Sub-bundle
        # A lesson #9). Anything unexpected becomes a generic 500 +
        # redacted excerpt; log warning for ops triage.
        log.warning(
            "POST /schwab/setup unexpected error: %s",
            type(exc).__name__,
        )
        return _render_error(
            request,
            status_code=500,
            error_message=_redacted_excerpt(exc),
            remediation_hint=(
                "Unexpected error during setup. Retry; if persistent, "
                "check `swing schwab status` CLI for audit-row state."
            ),
        )
    finally:
        conn.close()

    # Success path. summary is the service helper's return dict (used
    # by tests to assert the call shape; web route only cares about
    # success-vs-failure).
    _ = summary  # silence unused-variable linters; tests inspect via mocks
    if request.headers.get("HX-Request", "").lower() == "true":
        return Response(
            status_code=204,
            headers={"HX-Redirect": _SUCCESS_REDIRECT_TARGET},
        )
    return RedirectResponse(url=_SUCCESS_REDIRECT_TARGET, status_code=303)
