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
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from swing.config_overrides import apply_overrides
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
from swing.metrics.discrepancies import (
    count_recent_multi_leg_auto_corrections,
    count_unresolved_material,
    fetch_first_pending_ambiguity_resolve_link_path,
)
from swing.web.view_models.schwab import (
    SchwabSetupErrorVM,
    SchwabSetupVM,
    build_schwab_status_vm,
)

log = logging.getLogger(__name__)

router = APIRouter()


# HX-Redirect target after successful setup. Post-Phase-12 Sub-bundle 2
# Task T-2.4 retargets from /config?schwab_setup=ok → /schwab/status
# (T-B.7 deferred is now shipped via Sub-bundle 2). Route verified to
# exist via route-table assertion in tests; the prior /config target
# remains a passive no-op consumer for one release window per Codex R1
# m#2 LOCK (stale browser tabs / bookmarks with the old target still
# render the /config page; /config does not interpret the query param).
_SUCCESS_REDIRECT_TARGET = "/schwab/status"


def _fetch_unresolved_material_count(db_path) -> int:
    """Open a short-lived sqlite connection to count unresolved material
    discrepancies for the global base-layout banner.

    Mirrors the pattern in ``swing/web/routes/account.py`` (Phase 10
    Sub-bundle E T-E.3 cross-bundle pin) — every base-layout page must
    populate ``unresolved_material_discrepancies_count`` so the banner
    fires when discrepancies exist.
    """
    conn = sqlite3.connect(db_path)
    try:
        return count_unresolved_material(conn)
    finally:
        conn.close()


def _fetch_recent_multi_leg_auto_correction_count(db_path) -> int:
    """Phase 12.5 #1 T-1.8 — sibling helper to
    :func:`_fetch_unresolved_material_count`. Counts tier-1 multi-leg
    auto-redirects on the latest completed ``reconciliation_run`` so the
    T-1.9 banner block in ``base.html.j2`` can read
    ``vm.recent_multi_leg_auto_correction_count`` without
    ``UndefinedError``.
    """
    conn = sqlite3.connect(db_path)
    try:
        return count_recent_multi_leg_auto_corrections(conn)
    finally:
        conn.close()


def _fetch_banner_resolve_link(db_path) -> str | None:
    """Phase 12.5 #2 T-2.9 — sibling helper to
    :func:`_fetch_unresolved_material_count`. Returns the resolve-form
    path for the oldest pending-ambiguity discrepancy in the banner set,
    or None when no pending-ambiguity rows exist. Powers the base-layout
    ``vm.banner_resolve_link`` field via the Pattern-B (db_path-shape)
    helper convention used by ``swing/web/routes/schwab.py``.
    """
    conn = sqlite3.connect(db_path)
    try:
        return fetch_first_pending_ambiguity_resolve_link_path(conn)
    finally:
        conn.close()


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
    unresolved_count: int = 0,
    recent_multi_leg_count: int = 0,
    banner_resolve_link: str | None = None,
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
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
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
    unresolved_count: int = 0,
    recent_multi_leg_count: int = 0,
    banner_resolve_link: str | None = None,
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
    from swing.web.view_models.schwab_checker_badge import build_schwab_checker_badge
    return SchwabSetupVM(
        session_date=session_date,
        environment=environment,
        authorize_url=authorize_url,
        existing_tokens_db_warning=existing_db,
        error_message=error_message,
        callback_url_value=callback_url_value,
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
        schwab_checker_badge=build_schwab_checker_badge(cfg),
    )


@router.get("/schwab/setup", response_class=HTMLResponse)
def schwab_setup_form(request: Request) -> Response:
    """GET — render the OAuth setup form."""
    # Codex R1 Critical #1 fix — apply_overrides() at the route entry point.
    # `request.app.state.cfg` is the RAW tracked Config; without
    # apply_overrides() the cfg-cascade tier (user-config.toml) is never
    # consulted for `integrations.schwab.client_id` /
    # `integrations.schwab.client_secret`. Mirrors the existing pattern in
    # swing/cli_schwab.py:982-985, 1266-1269, 1430-1431.
    cfg = apply_overrides(request.app.state.cfg)
    environment = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "environment",
        "production",
    )
    # Phase 10 Sub-bundle E T-E.3 cross-bundle pin — every base-layout
    # page populates ``unresolved_material_discrepancies_count`` so the
    # global banner in base.html.j2 fires when discrepancies exist.
    # Phase 12.5 #1 T-1.8 sibling pin — ``recent_multi_leg_auto_correction_count``
    # for the T-1.9 banner block.
    # Phase 12.5 #2 T-2.9 sibling pin — ``banner_resolve_link`` for the
    # banner-link target.
    unresolved_count = _fetch_unresolved_material_count(cfg.paths.db_path)
    recent_multi_leg_count = _fetch_recent_multi_leg_auto_correction_count(
        cfg.paths.db_path,
    )
    banner_resolve_link = _fetch_banner_resolve_link(cfg.paths.db_path)
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
        )
        return _render_form(request, vm=vm)

    error_msg = None
    if client_id is None:
        # Codex R1 Major #4: do NOT reference /config (masked fields are
        # not editable there per swing/web/routes/config.py:31).
        error_msg = (
            "Schwab credentials not configured. Set "
            "SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars OR run "
            "`swing config set integrations.schwab.client_id <value>` "
            "and `swing config set integrations.schwab.client_secret "
            "<value>` before completing the OAuth flow."
        )
    vm = _build_form_vm(
        cfg=cfg,
        client_id=client_id,
        error_message=error_msg,
        unresolved_count=unresolved_count,
        recent_multi_leg_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
    )
    return _render_form(request, vm=vm)


@router.post("/schwab/setup")
async def schwab_setup_post(request: Request) -> Response:
    """POST — exchange operator's pasted callback URL for tokens."""
    # Codex R1 Critical #1 fix — apply_overrides() at the route entry point.
    # See GET handler for full rationale; same pattern.
    cfg = apply_overrides(request.app.state.cfg)
    environment = getattr(
        getattr(getattr(cfg, "integrations", None), "schwab", None),
        "environment",
        "production",
    )
    form = await request.form()
    callback_url_with_code = (form.get("callback_url") or "").strip()

    # Phase 10 Sub-bundle E T-E.3 cross-bundle pin — every base-layout
    # error/form response carries the unresolved-material count so the
    # global banner fires regardless of the response branch.
    # Phase 12.5 #1 T-1.8 sibling pin — recent_multi_leg_auto_correction_count
    # for the T-1.9 banner block.
    # Phase 12.5 #2 T-2.9 sibling pin — banner_resolve_link target.
    unresolved_count = _fetch_unresolved_material_count(cfg.paths.db_path)
    recent_multi_leg_count = _fetch_recent_multi_leg_auto_correction_count(
        cfg.paths.db_path,
    )
    banner_resolve_link = _fetch_banner_resolve_link(cfg.paths.db_path)

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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
        )

    if client_id is None or client_secret is None:
        # Codex R1 Major #4 fix — drop `/config` mention (masked fields are
        # not editable via the /config POST form per
        # swing/web/routes/config.py:31; pointing operators there would
        # show the masked display but no edit affordance). Reference env
        # vars + CLI only.
        return _render_error(
            request,
            status_code=400,
            error_message=(
                "Schwab credentials are not configured at any tier "
                "(env vars, ~/swing-data/user-config.toml, prompt-N/A)."
            ),
            remediation_hint=(
                "Set credentials via env vars "
                "(SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET) OR via CLI "
                "(`swing config set integrations.schwab.client_id <value>` "
                "and `swing config set integrations.schwab.client_secret "
                "<value>`) in a PowerShell session, then retry."
            ),
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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
            unresolved_count=unresolved_count,
            recent_multi_leg_count=recent_multi_leg_count,
            banner_resolve_link=banner_resolve_link,
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


# ---------------------------------------------------------------------------
# Post-Phase-12 Sub-bundle 2 Task T-2.1 — GET /schwab/status
# ---------------------------------------------------------------------------
#
# Read-only web counterpart to ``swing schwab status`` CLI per dispatch
# brief §0.5 #14 + spec §7.4 OQ-D LOCK. Mirrors CLI 1:1 — no Schwab API
# calls, no auth-flow side-effects, no domain-table writes.
#
# BINDING contracts (from dispatch brief §0.5):
#   #2 — state triplet LIVE/PROVISIONAL/DEGRADED (plan §A.0.1 D3; NOT spec
#        §7.1's misnamed CONFIGURED/...). V2.1 §VII.F amendment banked.
#   #4 — apply_overrides(cfg) at route entry (Codex R1 Critical #1
#        inheritance from Sub-bundle B).
#   #5 — case-insensitive env query-param.
#   #6 — XSS-safe PlainTextResponse for invalid env (Codex R1 Major #7 +
#        R2 Major #1).
#   #7 — sentinel-leak audit per Phase 11 Sub-bundle A T-A.10 D1 redaction.
#   #11 — NO Schwab API calls (read-only consumer of pre-existing audit
#        + tokens DB metadata).
#   #13 — base-layout VM banner pin (5 fields populated via
#        _fetch_unresolved_material_count helper at route entry).


@router.get("/schwab/status", response_class=HTMLResponse)
def schwab_status_get(
    request: Request, environment: str | None = None,
) -> Response:
    """GET — render the read-only Schwab integration status page."""
    # Apply user-config.toml overrides at route entry (BINDING per dispatch
    # brief §0.5 #4 — Codex R1 Critical #1 fix at Sub-bundle B `e418d56`
    # added apply_overrides at all 5 Schwab entry points; preserve here).
    cfg = apply_overrides(request.app.state.cfg)

    # Resolve effective environment: explicit query-param override (case-
    # insensitive per BINDING #5) wins over cfg default.
    if environment is not None:
        env_normalized = environment.strip().lower()
        if env_normalized not in ("production", "sandbox"):
            # XSS-safe error response per BINDING #6 (Codex R1 Major #7 +
            # R2 Major #1). PlainTextResponse content-type 'text/plain'
            # prevents browser interpretation of any echoed value; body
            # MAY contain literal `<script>` substring without effect.
            # Operator-input value is echoed via repr() for debugging.
            return PlainTextResponse(
                content=(
                    f"Invalid environment {environment!r}; "
                    "must be 'production' or 'sandbox'"
                ),
                status_code=400,
            )
        env = env_normalized
    else:
        env = (
            getattr(
                getattr(
                    getattr(cfg, "integrations", None),
                    "schwab",
                    None,
                ),
                "environment",
                "production",
            )
            or "production"
        ).lower()

    # Phase 10 Sub-bundle E T-E.3 cross-bundle pin — every base-layout
    # page populates ``unresolved_material_discrepancies_count`` so the
    # global banner in base.html.j2 fires when discrepancies exist.
    # Phase 12.5 #1 T-1.8 sibling pin — recent_multi_leg_auto_correction_count
    # for the T-1.9 banner block.
    # Phase 12.5 #2 T-2.9 sibling pin — banner_resolve_link target.
    unresolved_count = _fetch_unresolved_material_count(cfg.paths.db_path)
    recent_multi_leg_count = _fetch_recent_multi_leg_auto_correction_count(
        cfg.paths.db_path,
    )
    banner_resolve_link = _fetch_banner_resolve_link(cfg.paths.db_path)

    session_date = action_session_for_run(datetime.now()).isoformat()
    vm = build_schwab_status_vm(
        cfg=cfg,
        env=env,
        db_path=cfg.paths.db_path,
        session_date=session_date,
        unresolved_count=unresolved_count,
        recent_multi_leg_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "schwab_status.html.j2",
        {"vm": vm},
    )
