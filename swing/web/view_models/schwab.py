"""Phase 12 Sub-bundle B Task T-B.4 — Schwab setup form VM.

Web counterpart to the existing ``swing schwab setup`` CLI. Provides the
view-model for ``GET /schwab/setup`` (form-render) + the error template
context (``GET/POST`` failure paths).

Per CLAUDE.md HTMX-form-driven gotcha family (Phase 5 R1 M1 + M2 + Phase 6
I3 lessons):
- Form sets ``hx-headers='{"HX-Request": "true"}'`` so OriginGuard strict-
  mode accepts the submission.
- Success POST returns 204 + HX-Redirect (NOT 303 swap-target). Target
  route MUST exist; tests assert via app.routes table inspection.
- ``authorize_url`` is constructed server-side from cfg
  ``integrations.schwab`` fields; rendered as a clickable link with
  ``target="_blank"``.

T-B.7 disposition (per dispatch brief §3 T-B.7 decision rule): DEFERRED
because T-B.4 lands Outcome B (manual token exchange) which adds material
implementation surface; T-B.7's web `/schwab/status` counterpart routes
to a follow-up dispatch. HX-Redirect target = ``/config`` (verified
present in app.routes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Local minimal base-layout fields. Phase 10 introduced ``BaseLayoutVM`` in
# ``swing.web.view_models.metrics.shared`` for metrics-page VMs; non-metrics
# VMs (DashboardVM, PipelineVM, ConfigVM, AccountSnapshotFormVM, etc.) all
# carry the same fields directly. The Schwab setup VM follows the non-
# metrics convention (no ``unresolved_material_discrepancies_count``
# dependency from the metrics package). We DO add the field name as a
# dataclass attribute so base.html.j2's discrepancy-banner block renders
# without UndefinedError on this page (CLAUDE.md "base.html.j2 is shared"
# gotcha + Phase 10 Sub-bundle E T-E.3 cross-bundle retrofit pattern).


@dataclass(frozen=True)
class SchwabSetupVM:
    """VM for ``GET /schwab/setup`` form-render.

    Base-layout fields (mirrors PageErrorVM / AccountSnapshotFormVM shape):
        session_date: forward-looking action_session_for_run(now).
        stale_banner: never stale on a setup page.
        price_source_degraded / ohlcv_source_degraded: not shown.
        unresolved_material_discrepancies_count: 0 by default; populated
            from ``count_unresolved_material`` at handler entry (matches
            Phase 10 Sub-bundle E T-E.3 base-layout retrofit pattern).

    Setup-specific fields:
        environment: 'sandbox' or 'production' (cfg-driven; display-only
            on the form so operator sees which env they're authorizing).
        authorize_url: full Schwab OAuth consent URL with client_id +
            redirect_uri pre-filled. Operator clicks → opens new tab →
            authorizes → Schwab redirects to the cfg callback_url with
            ``?code=<...>%40<session>`` query params → operator copies
            the URL from address bar → pastes into the form's
            ``callback_url`` text input → submits POST.
        existing_tokens_db_warning: True when an existing tokens DB at
            ``~/swing-data/schwab-tokens.{env}.db`` will be self-healed
            (atomically renamed to ``.deleted-<ts>``) on submit. Purely
            informational — the actual rename happens inside the service
            helper at POST time per T-A.2 inheritance.
        error_message: optional banner text rendered when re-displaying
            the form after a failed POST.
    """

    # Base-layout fields (required-first, default-second per dataclass
    # convention; matches PageErrorVM shape).
    session_date: str
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0

    # Setup-specific fields.
    environment: str = "production"
    authorize_url: str = ""
    existing_tokens_db_warning: bool = False
    error_message: str | None = None
    # Re-displayed callback URL after a failed POST so operator doesn't
    # have to re-extract from the browser address bar. NEVER persisted;
    # exists only in the failure-path re-render.
    callback_url_value: str = ""

    def __post_init__(self) -> None:
        if not self.session_date:
            raise ValueError(
                "SchwabSetupVM.session_date must be non-empty",
            )
        if self.environment not in ("sandbox", "production"):
            raise ValueError(
                "SchwabSetupVM.environment must be 'sandbox' or 'production'; "
                f"got {self.environment!r}",
            )
        if self.unresolved_material_discrepancies_count < 0:
            raise ValueError(
                "SchwabSetupVM.unresolved_material_discrepancies_count must "
                f">= 0; got {self.unresolved_material_discrepancies_count!r}",
            )


# ---------------------------------------------------------------------------
# Post-Phase-12 Sub-bundle 2 Task T-2.0 — SchwabStatusVM + SchwabCallSummary
# (read-only ``/schwab/status`` web counterpart, mirrors ``swing schwab status``
# CLI 1:1 per dispatch brief §0.5 #14 + spec §7.4 OQ-D LOCK).
# ---------------------------------------------------------------------------
#
# State triplet is **LIVE / PROVISIONAL / DEGRADED** (matches shipped CLI
# ``swing schwab status`` per ``swing/cli_schwab.py:790+`` + ``_compute_de
# graded_state`` at L615-741) — NOT spec §7.1's misnamed
# CONFIGURED/PROVISIONAL/NOT_CONFIGURED triplet. Plan §A.0.1 D3 LOCK; V2.1
# §VII.F amendment banked for the spec.
#
# Invariant: ``state_reason is None iff state == 'LIVE'`` (Codex R3 Minor #2 +
# plan §B T-2.0). LIVE = all signals OK so reason is None; non-LIVE REQUIRES
# a non-empty reason for operator-actionability.
#
# Base-layout fields (Phase 10 Sub-bundle E T-E.3 retrofit pattern + Phase 12
# Sub-sub-bundle C.D widening): every page extending base.html.j2 MUST
# populate the 5 banner fields with safe defaults.


# Audit-row status enum per ``schwab_api_calls.status`` CHECK constraint
# (migration 0018). Mirrors the enum exposed via the CLI's
# ``_render_recent_calls`` consumer of ``list_recent_calls``.
_SCHWAB_CALL_STATUSES = frozenset({
    # Terminal outcomes the audit row will surface to the operator-facing
    # status page (in_flight rows are excluded by ``list_recent_calls``'s
    # caller since they represent a request in mid-flight, not history).
    "success",
    "auth_failed",
    "rate_limited",
    "error",
})

_SCHWAB_STATUS_STATES = frozenset({"LIVE", "PROVISIONAL", "DEGRADED"})
_REFRESH_TOKEN_SEVERITIES = frozenset({"ok", "warn", "error"})
_SCHWAB_ENVIRONMENTS = frozenset({"production", "sandbox"})


@dataclass(frozen=True)
class SchwabCallSummary:
    """Operator-facing summary of one ``schwab_api_calls`` audit row.

    Read-only projection — carries ONLY derived metadata that the template
    safely renders. ``error_excerpt`` is the redacted-by-construction text
    that wrapper functions persist via ``record_call_finish`` (per
    CLAUDE.md "Typed SchwabApiError audit-row close discipline" gotcha).

    NEVER carries token bytes — sentinel-leak audit (plan §B T-2.1 test 13)
    plants non-token-shaped sentinels in tokens DB + audit error_message
    rows and asserts ZERO substring matches in the rendered response.
    """

    started_ts: str
    endpoint: str
    status: str
    http_status: int | None
    error_excerpt: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.started_ts, str) or not self.started_ts:
            raise ValueError(
                "SchwabCallSummary.started_ts must be a non-empty string",
            )
        if not isinstance(self.endpoint, str) or not self.endpoint:
            raise ValueError(
                "SchwabCallSummary.endpoint must be a non-empty string",
            )
        if self.status not in _SCHWAB_CALL_STATUSES:
            raise ValueError(
                "SchwabCallSummary.status must be one of "
                f"{sorted(_SCHWAB_CALL_STATUSES)!r}; got {self.status!r}",
            )


@dataclass(frozen=True)
class SchwabStatusVM:
    """VM for ``GET /schwab/status`` (read-only V1 web counterpart to
    ``swing schwab status`` CLI).

    Mirrors the CLI rendering 1:1 per dispatch brief §0.5 #14 + spec §7.4
    OQ-D LOCK. No reconciliation actions; no FIRED-stop-specific handling
    at this layer.

    State triplet + invariant per plan §A.0.1 D3 (shipped CLI triplet) +
    Codex R3 Minor #2 (``state_reason is None iff state == 'LIVE'``).

    Base-layout fields (5) populate via the ``_fetch_unresolved_material_
    count`` helper at the route handler entry per Phase 10 T-E.3 retrofit.
    """

    # CLI-mirror fields.
    session_date: str
    environment: Literal["production", "sandbox"]
    state: Literal["LIVE", "PROVISIONAL", "DEGRADED"]
    state_reason: str | None
    tokens_db_path: str
    refresh_token_expires_at: str | None
    refresh_token_days_remaining: int | None
    refresh_token_severity: Literal["ok", "warn", "error"]
    recent_calls: list[SchwabCallSummary]
    last_success_at: str | None
    last_failure_at: str | None
    degraded_banner_active: bool
    nav_back_to_config_url: str = "/config"

    # Base-layout fields (Phase 10 Sub-bundle E T-E.3 retrofit pattern).
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0

    def __post_init__(self) -> None:
        if not self.session_date:
            raise ValueError(
                "SchwabStatusVM.session_date must be non-empty",
            )
        if self.environment not in _SCHWAB_ENVIRONMENTS:
            raise ValueError(
                "SchwabStatusVM.environment must be one of "
                f"{sorted(_SCHWAB_ENVIRONMENTS)!r}; "
                f"got {self.environment!r}",
            )
        if self.state not in _SCHWAB_STATUS_STATES:
            raise ValueError(
                "SchwabStatusVM.state must be one of "
                f"{sorted(_SCHWAB_STATUS_STATES)!r}; "
                f"got {self.state!r} "
                "(NOTE: plan §A.0.1 D3 locks the shipped CLI triplet "
                "LIVE/PROVISIONAL/DEGRADED — spec §7.1's misnamed "
                "CONFIGURED/... triplet is a V2.1 §VII.F amendment "
                "candidate)",
            )
        if self.refresh_token_severity not in _REFRESH_TOKEN_SEVERITIES:
            raise ValueError(
                "SchwabStatusVM.refresh_token_severity must be one of "
                f"{sorted(_REFRESH_TOKEN_SEVERITIES)!r}; "
                f"got {self.refresh_token_severity!r}",
            )
        if self.unresolved_material_discrepancies_count < 0:
            raise ValueError(
                "SchwabStatusVM.unresolved_material_discrepancies_count "
                "must be >= 0; got "
                f"{self.unresolved_material_discrepancies_count!r}",
            )
        if not isinstance(self.recent_calls, list):
            raise TypeError(
                "SchwabStatusVM.recent_calls must be a list of "
                "SchwabCallSummary; got "
                f"{type(self.recent_calls).__name__}",
            )
        for idx, call in enumerate(self.recent_calls):
            if not isinstance(call, SchwabCallSummary):
                raise TypeError(
                    f"SchwabStatusVM.recent_calls[{idx}] must be a "
                    f"SchwabCallSummary; got {type(call).__name__}",
                )
        # Invariant per Codex R3 Minor #2 (plan §B T-2.0 BINDING):
        #   state_reason is None iff state == 'LIVE'.
        # LIVE = all signals OK so reason is None; non-LIVE REQUIRES a non-
        # empty (post-strip) explanatory string for operator-actionability.
        # The strip-then-empty check rejects whitespace-only reasons that
        # would render as a blank line next to a yellow/red badge.
        if self.state == "LIVE":
            if self.state_reason is not None:
                raise ValueError(
                    "SchwabStatusVM.state_reason must be None when state == "
                    f"'LIVE'; got {self.state_reason!r}",
                )
        else:
            if (
                self.state_reason is None
                or not isinstance(self.state_reason, str)
                or not self.state_reason.strip()
            ):
                raise ValueError(
                    "SchwabStatusVM.state_reason must be a non-empty string "
                    f"when state == {self.state!r}; "
                    f"got {self.state_reason!r}",
                )


@dataclass(frozen=True)
class SchwabSetupErrorVM:
    """VM for the user-visible error template (4xx / 5xx error response).

    Same base-layout shape as SchwabSetupVM. Carries an HTTP status code
    + a redacted operator-actionable error message + a remediation hint.
    """

    session_date: str
    status_code: int
    error_message: str
    remediation_hint: str
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0

    def __post_init__(self) -> None:
        if not self.session_date:
            raise ValueError(
                "SchwabSetupErrorVM.session_date must be non-empty",
            )
        if not self.error_message:
            raise ValueError(
                "SchwabSetupErrorVM.error_message must be non-empty",
            )
