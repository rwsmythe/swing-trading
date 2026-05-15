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
