"""Schwab API integration — SchwabClient wrapper + exception hierarchy +
transport-debug-log suppression context manager.

V1 scope (T-A.3): exception definitions + LAZY `SchwabClient` skeleton (does
NOT construct `schwabdev.Client` at __init__ — that would trigger OAuth flow
on first call when no tokens DB is present). Full setup/refresh/logout flow
lands in T-A.4 / T-A.5 / T-A.6.

Design references:
  * `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §A.2 +
    §H.3 (SchwabClient.__init__ algorithm; tokens-DB path resolution).
  * `docs/schwab-bundle-A-task-A0b-recon.md` §2.2 (paste-back embedded in
    `schwabdev.Client.__init__` — wrapping discipline is composition + lazy
    instantiation so test fixtures don't block on stdin).
  * `swing/integrations/finviz_api.py` — precedent for both the exception
    `__str__` redaction discipline and the `_suppress_transport_debug_logs`
    context-manager shape.

Token-redaction contract:
  * NO exception's `__str__` includes URL bytes (URLs contain `account_hash`
    segments) OR response body verbatim. Only HTTP status + body length.
  * Logger suppression covers urllib3 transport (request URL appears in
    DEBUG records) + schwabdev's `Schwabdev` logger (per recon §2.10 +
    tokens.py:~338 caveat — auth-failure path may log `response.text`).
"""
from __future__ import annotations

import contextlib
import logging
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from swing.config import _user_home

if TYPE_CHECKING:
    import schwabdev

    from swing.config import Config


log = logging.getLogger(__name__)


# Logger names that may emit URL / response-body content at DEBUG (or higher)
# level. Muted to WARNING during any wrapped API call. Spectrum chosen per
# T-A.0.b recon §2 inspection of installed schwabdev (version 2.5.1):
#   * `urllib3.connectionpool` + `requests.packages.urllib3.connectionpool` —
#     urllib3 transport (DEBUG line per HTTP request prints the request URL).
#   * `urllib3.util.retry` — emits the retry URL on backoff.
#   * `Schwabdev` — the ONLY logger schwabdev itself constructs (client.py
#     L44: `logging.getLogger("Schwabdev")`); shared across Client/Tokens/
#     Stream. Per recon doc §2.10 the auth-failure path under
#     `schwabdev/tokens.py` logs `response.text` which may carry token-related
#     error detail.
# NOTE: plan §Tasks-A T-A.3 targeted '5 logger names' synthesized from the
# Finviz precedent (2) + an expected schwabdev breakdown (3). Live inspection
# of schwabdev 2.5.1 shows schwabdev itself ships ONE logger only ("Schwabdev"),
# so the project ships 4 muted loggers total. Banked as plan-text deviation.
_TRANSPORT_DEBUG_LOGGERS = (
    "urllib3.connectionpool",
    "requests.packages.urllib3.connectionpool",
    "urllib3.util.retry",
    "Schwabdev",
)


@contextlib.contextmanager
def _suppress_transport_debug_logs() -> Iterator[None]:
    """Force every logger in `_TRANSPORT_DEBUG_LOGGERS` to WARNING for the
    duration of the context; restore each logger's prior level on exit.

    Defense-in-depth complement to the per-exception `__str__` redaction
    contracts. Mirrors `swing/integrations/finviz_api.py:_suppress_transport_debug_logs`."""
    prior = {n: logging.getLogger(n).level for n in _TRANSPORT_DEBUG_LOGGERS}
    try:
        for n in _TRANSPORT_DEBUG_LOGGERS:
            logging.getLogger(n).setLevel(logging.WARNING)
        yield
    finally:
        for n, lvl in prior.items():
            logging.getLogger(n).setLevel(lvl)


# ---------- Exception hierarchy ----------
#
# Inheritance:
#
#   SchwabConfigMissingError(_RedactedMessageError)
#   SchwabSchemaParityError(_RedactedMessageError)
#   SchwabPipelineActiveError(_RedactedMessageError)
#   SchwabApiError(RuntimeError)
#       ├── SchwabRateLimitError
#       └── SchwabAuthError
#               ├── SchwabRefreshTokenExpiredError
#               └── SchwabConcurrentRefreshError
#
# All eight classes' `__str__` MUST redact account_hash-shaped substrings.
# `SchwabApiError` enforces by NEVER echoing the body (only its length).
# `_RedactedMessageError` enforces by stripping URL path segments + likely
# hash tokens from the caller-supplied message via regex substitution.

# A "hash-looking" token: 8+ alphanumeric/underscore chars in a URL-path
# segment (`/<hash>` or `/<hash>/`) OR after `=` (`accountHash=<hash>`,
# `hash:<hash>`). Defense-in-depth — callers SHOULD NOT include such values
# in messages, but redaction here closes the foot-gun.
_HASH_SHAPED = re.compile(
    r"(?P<lead>[/=:])(?P<token>[A-Za-z0-9_]{8,})"
)


def _redact_message(msg: str) -> str:
    """Mask hash-shaped substrings appearing after `/`, `=`, or `:`.

    Used by the non-`SchwabApiError` exception classes whose `__str__` would
    otherwise echo a caller-supplied message verbatim — protects against the
    foot-gun where a higher-level handler interpolates `account_hash` or
    response-URL bytes into a diagnostic string."""
    return _HASH_SHAPED.sub(lambda m: f"{m.group('lead')}<redacted>", msg)


class _RedactedMessageError(RuntimeError):
    """Base for the message-accepting Schwab exception classes. Stores the
    raw caller-supplied message AS-IS on `.message` for callers that need it,
    but `__str__` returns the redacted form."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return _redact_message(self.message)


class SchwabConfigMissingError(_RedactedMessageError):
    """Raised when required cfg / credential is missing.

    Typical causes: `cfg.integrations.schwab.environment` set to a value
    outside {'sandbox', 'production'}; `account_hash` missing when an
    account-keyed call is attempted; client_id/client_secret missing at
    setup-flow entry. Caller-supplied message; `__str__` redacts
    hash-shaped substrings as defense-in-depth.
    """


class SchwabApiError(RuntimeError):
    """Generic Schwab API error (HTTP non-200 or network failure).

    `__str__` is engineered to NEVER include the request URL (URLs contain
    `account_hash` segments) or the response body verbatim — only the HTTP
    status code + a byte-count of the body excerpt. Mirrors
    `swing.integrations.finviz_api.FinvizApiError`.

    Subclasses preserve the same `__str__` shape via the shared __init__.
    """

    def __init__(self, status_code: int, body_excerpt: str) -> None:
        self.status_code = status_code
        self.body_excerpt = body_excerpt
        super().__init__(
            f"{type(self).__name__}(status={status_code}, "
            f"body=<{len(body_excerpt)} bytes>)"
        )


class SchwabRateLimitError(SchwabApiError):
    """Raised on HTTP 429 after a Retry-After-respecting retry has also failed
    (or when Retry-After is absent / unparseable). Schwab rate limits per
    `client.md` L255-265: 120/min all endpoints + 4000/day orders."""


class SchwabAuthError(SchwabApiError):
    """Raised on HTTP 401 auth failures that the wrapper could not transparently
    recover from (e.g. schwabdev's own refresh path failed). Distinguished from
    `SchwabRefreshTokenExpiredError` for the operator-advisory path."""


class SchwabRefreshTokenExpiredError(SchwabAuthError):
    """Raised when the refresh_token has crossed its 7-day Schwab-side expiry
    (the `unsupported_token_type` error documented in `troubleshooting.md`
    L45-58). Operator-actionable: re-run `swing schwab setup --environment <env>`.

    Distinct from generic `SchwabAuthError` because the CLI advisory differs
    (full re-auth vs implicit refresh)."""


class SchwabSchemaParityError(_RedactedMessageError):
    """Raised when a Schwab API response cannot be normalized to the expected
    dataclass shape — missing field, unexpected nesting, type mismatch.

    Bundle B + C consumers (mapper.py) raise this; T-A.3 ships the class to
    keep the exception hierarchy complete + importable. `__str__` redacts
    hash-shaped substrings."""


class SchwabConcurrentRefreshError(SchwabAuthError):
    """Raised when two SchwabClient instances attempt to refresh tokens
    simultaneously and the file-locking semantics signal contention.

    Per recon doc §2.8: schwabdev claims multi-Client safety but does not
    document explicit lock semantics. Project handles cross-surface
    coordination via `SchwabPipelineActiveError` (CLI vs pipeline) + this
    class for in-process concurrent refresh contention."""


class SchwabPipelineActiveError(_RedactedMessageError):
    """Raised by CLI surfaces (`swing schwab setup`, `logout`, `refresh`) when
    a pipeline run is currently in flight without operator `--force` override.

    Mirrors `swing.integrations.finviz_api.FinvizPipelineActiveError`. Cross-
    surface concurrency exclusion per plan §A.14 / §H.10. NOT raised by
    pipeline-internal Schwab call sites — those run inside the lease by
    definition. `__str__` redacts hash-shaped substrings."""


# ---------- SchwabClient wrapper ----------

_VALID_ENVIRONMENTS = ("sandbox", "production")


class SchwabClient:
    """Thin composition wrapper around `schwabdev.Client`.

    Per plan §A.2 + §H.3: COMPOSITION, not subclassing. Every endpoint method
    invocation wraps the underlying schwabdev call in an audit-row
    INSERT/UPDATE pair (Bundle B+ scope) + `_suppress_transport_debug_logs()`.

    LAZY CONSTRUCTION (T-A.3 binding contract): the underlying
    `schwabdev.Client(...)` is NOT constructed at `__init__` — that would
    trigger OAuth paste-back flow (blocks on stdin) the very first time the
    integration is used. Callers in T-A.4+ supply `app_key`/`app_secret` and
    invoke `_ensure_schwabdev_client(...)` on first use; subsequent calls
    return the cached instance.

    Per-env tokens DB path resolved at __init__ via `_user_home()` so test
    fixtures (USERPROFILE+HOME monkeypatched) and the operator's real
    `~/swing-data/` are properly isolated.
    """

    def __init__(
        self,
        cfg: Config,
        environment: str,
        conn: sqlite3.Connection,
    ) -> None:
        if environment not in _VALID_ENVIRONMENTS:
            raise SchwabConfigMissingError(
                f"environment must be one of {_VALID_ENVIRONMENTS!r}; "
                f"got {environment!r}"
            )
        self._cfg = cfg.integrations.schwab
        self._environment = environment
        self._conn = conn
        self._tokens_db_path: Path = (
            _user_home() / "swing-data" / f"schwab-tokens.{environment}.db"
        )
        # Lazy hook — T-A.4/T-A.5 populate via `_ensure_schwabdev_client`.
        self._schwabdev_client: schwabdev.Client | None = None
        # Best-effort headroom telemetry (Bundle B+ populates from response
        # headers when Schwab emits any rate-limit metadata).
        self.last_rate_limit_remaining: int | None = None

    def _ensure_schwabdev_client(
        self, app_key: str, app_secret: str,
    ) -> schwabdev.Client:
        """Construct `schwabdev.Client(...)` on first call; cache + return on
        subsequent calls.

        Caller (T-A.4 `setup_paste_flow` initial construction; T-A.5
        `force_refresh` re-use post-setup) supplies the app credentials.

        Implementation deferred to T-A.4 — T-A.3 ships the binding hook so
        downstream tasks have a stable construction site. Calling this in
        T-A.3 would import schwabdev at module-load time + block tests."""
        raise NotImplementedError(
            "schwabdev.Client construction lands in T-A.4 / T-A.5; "
            "T-A.3 only ships the lazy hook signature."
        )
