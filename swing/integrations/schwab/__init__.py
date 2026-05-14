"""Schwab API integration (V1: paste-only OAuth, plaintext tokens, audit lifecycle).

Public surface re-exports the SchwabClient wrapper + the 8-class exception
hierarchy. Module-internal callers (auth.py; future setup/refresh/logout
helpers) import from `swing.integrations.schwab.client` directly to also
reach `_suppress_transport_debug_logs` and `_TRANSPORT_DEBUG_LOGGERS`.

See `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §A.2.
"""
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabClient,
    SchwabConcurrentRefreshError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
    SchwabRateLimitError,
    SchwabRefreshTokenExpiredError,
    SchwabSchemaParityError,
    ensure_schwab_log_redaction_factory_installed,
    register_schwab_secrets,
)

__all__ = (
    "SchwabClient",
    "SchwabConfigMissingError",
    "SchwabApiError",
    "SchwabRateLimitError",
    "SchwabAuthError",
    "SchwabRefreshTokenExpiredError",
    "SchwabSchemaParityError",
    "SchwabConcurrentRefreshError",
    "SchwabPipelineActiveError",
    "register_schwab_secrets",
    "ensure_schwab_log_redaction_factory_installed",
)
