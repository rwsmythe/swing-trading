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
import threading
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from swing.config import _user_home

if TYPE_CHECKING:
    import schwabdev

    from swing.config import Config


log = logging.getLogger(__name__)


# ============================================================================
# Token redaction (T-A.10 — three-layer discipline per plan §H.8)
# ============================================================================
#
# Layer 0 — known-value exact-replace from runtime context (5 long-lived
#   slots: client_id, client_secret, access_token, refresh_token, account_hash).
#   `authorization_code` is OMITTED — paste-back-only inside schwabdev's
#   manual_flow; never observable as a Python string in the wrapper (R4 M#1).
# Layer 1 — heuristic regex (hex 32+, base64 24+); folded into Layer 0.
# Layer 2 — `logging.setLogRecordFactory` at record-creation time. Earlier
#   R5/R6 designs that attached a `logging.Filter` to the root logger are
#   WRONG per Python's `Logger.callHandlers()` semantics (filters on ancestor
#   loggers do NOT fire during propagation). R7 Critical #1 redesign moved
#   to the factory approach which mutates the LogRecord before any handler
#   reads it.
#
# Plan §H.8 binding contract; T-A.10 test file is the discriminating audit.

# Logger-name prefix gating the factory's redaction pass. Plan §H.8 specifies
# `'schwabdev'`, but live schwabdev 2.5.1 uses `logging.getLogger("Schwabdev")`
# (capital S; single logger, no hierarchy). Using "Schwabdev" matches the
# actual library; sub-loggers of the form `Schwabdev.<module>` also match via
# `startswith`. Banked as plan-text deviation (mirrors the T-A.3 banked
# `_TRANSPORT_DEBUG_LOGGERS` deviation).
_SCHWABDEV_LOGGER_PREFIX = "Schwabdev"

# Process-global registry: a single set of all sensitive values seen this
# process. Lifecycle = process lifetime; never narrowed. Multiple SchwabClient
# instances (sandbox + production, or sequential setup/refresh/status invocations)
# all CONTRIBUTE secrets to this set; the LogRecord factory consults the full
# set at record-creation time. Narrowing the registry per-client would erase
# earlier clients' secrets — Codex R3 Major #2.
_GLOBAL_KNOWN_SECRETS: set[str] = set()
_GLOBAL_FILTER_LOCK = threading.Lock()

# Layer 2 state — process-global factory install.
_ORIGINAL_RECORD_FACTORY: Callable | None = None
_FACTORY_INSTALLED = False
_FACTORY_LOCK = threading.Lock()
_FACTORY_DEPTH = threading.local()  # thread-local recursion guard (R9 M#1)


def register_schwab_secrets(secrets: Iterable[str]) -> None:
    """Add operator-supplied sensitive values to the global redaction set.

    Called at SchwabClient construction, OAuth setup, refresh — anywhere a
    new secret enters the runtime. Idempotent under repeat registration.
    Never removes secrets.

    Values shorter than 4 chars + empty/None values are skipped to avoid
    polluting the registry with substrings that would over-redact noise.
    """
    with _GLOBAL_FILTER_LOCK:
        for s in secrets:
            if s and isinstance(s, str) and len(s) >= 4:
                _GLOBAL_KNOWN_SECRETS.add(s)


def _make_redactor_from_global() -> Callable[[str], str]:
    """Build a redactor closure that reads `_GLOBAL_KNOWN_SECRETS` at each call.

    Snapshots the set at message-redaction time so secrets registered AFTER
    redactor construction are picked up on the next log record. Three-piece
    redaction:
      Layer 0 (in-set) — exact-replace every registered secret.
      Layer 1a (heuristic) — 32+ contiguous hex characters.
      Layer 1b (heuristic) — 24+ contiguous base64-shaped characters.
    """
    def redact(message: str) -> str:
        if not message:
            return message
        excerpt = message[:500]
        with _GLOBAL_FILTER_LOCK:
            secrets = list(_GLOBAL_KNOWN_SECRETS)
        # Sort longest-first so a longer secret that *contains* a shorter
        # secret as substring is redacted before the shorter one consumes
        # part of its bytes.
        secrets.sort(key=len, reverse=True)
        for s in secrets:
            excerpt = excerpt.replace(s, "<REDACTED>")
        excerpt = re.sub(r"[a-fA-F0-9]{32,}", "<REDACTED>", excerpt)
        excerpt = re.sub(r"[A-Za-z0-9+/=]{24,}", "<REDACTED>", excerpt)
        return excerpt
    return redact


def _redact_error_message_for_audit(message: str) -> str:
    """Layer-1-only redactor for code paths without runtime-context registry.

    Pass-through to the global-set redactor; included as a stable public name
    so audit-row writers + future test fixtures can pin redaction to the same
    discipline.
    """
    return _make_redactor_from_global()(message)


def _schwab_record_factory(*args, **kwargs):
    """LogRecord factory wrapping the original. Redacts msg+args at
    creation time for any record whose name starts with the schwabdev
    prefix. Non-schwabdev records pass through with a single startswith
    check (microsecond cost).

    R9 Major #1 recursion guard: if a third-party LogRecord factory
    captures our factory as their `orig` and our `ensure_*` later wraps
    them again, the chain `ours -> theirs -> ours -> theirs ...` would
    infinite-recurse. Thread-local `_FACTORY_DEPTH.in_call` short-circuits
    re-entry.

    R10 Major #1: on re-entry detection, call `logging.LogRecord(*args,
    **kwargs)` DIRECTLY (NOT `_ORIGINAL_RECORD_FACTORY`) — under the
    adversarial third-party-wraps-our-factory scenario, `_ORIGINAL` is
    the third party which would call back into us → loop.
    """
    if getattr(_FACTORY_DEPTH, "in_call", False):
        # Re-entry detected (adversarial chain). Direct stdlib construct;
        # outer redaction has already mutated the outermost record.
        return logging.LogRecord(*args, **kwargs)
    _FACTORY_DEPTH.in_call = True
    try:
        record = _ORIGINAL_RECORD_FACTORY(*args, **kwargs)
        if not record.name.startswith(_SCHWABDEV_LOGGER_PREFIX):
            return record
        redactor = _make_redactor_from_global()
        # Force message interpolation now (so record.msg substitution is final).
        msg = record.getMessage()
        record.msg = redactor(msg)
        record.args = ()  # message already interpolated
        return record
    finally:
        _FACTORY_DEPTH.in_call = False


# Tag for chain detection (R9 Major #1 defense-in-depth).
_schwab_record_factory._is_schwab_factory = True  # type: ignore[attr-defined]


def _install_schwab_log_redaction_factory_once() -> None:
    """Install the LogRecord factory wrapper EXACTLY ONCE per process.

    Idempotent. Stores original factory in `_ORIGINAL_RECORD_FACTORY` for
    pass-through. Replaces the prior root-logger-filter design (R5/R6) which
    was incorrect per Python's `Logger.callHandlers()` semantics — filters on
    ancestor loggers are NOT applied during propagation.
    """
    global _ORIGINAL_RECORD_FACTORY, _FACTORY_INSTALLED
    with _FACTORY_LOCK:
        if _FACTORY_INSTALLED:
            return
        _ORIGINAL_RECORD_FACTORY = logging.getLogRecordFactory()
        logging.setLogRecordFactory(_schwab_record_factory)
        _FACTORY_INSTALLED = True


def ensure_schwab_log_redaction_factory_installed() -> None:
    """Re-install Schwab's redaction factory if another library replaced it.

    Codex R8 Major #2 fix: `logging.setLogRecordFactory()` is process-global;
    any other library calling it AFTER our install silently disables our
    redaction. SchwabClient should call this BEFORE every schwabdev API
    invocation; it checks the current factory and re-wraps if needed.

    Idempotent under repeat calls when factory IS already ours. When factory
    has been replaced, captures the current factory as the new "original" +
    reinstalls our wrapper around it so we redact + still pass through to
    whatever the other library wanted.
    """
    global _ORIGINAL_RECORD_FACTORY, _FACTORY_INSTALLED
    with _FACTORY_LOCK:
        current = logging.getLogRecordFactory()
        if current is _schwab_record_factory:
            return  # ours; intact
        _ORIGINAL_RECORD_FACTORY = current
        logging.setLogRecordFactory(_schwab_record_factory)
        _FACTORY_INSTALLED = True  # R11 Minor #2 invariant cleanup


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

        # T-A.10 — contribute cfg-known sensitive bytes to the process-global
        # redaction registry + install the LogRecord factory once. Tokens
        # (access_token / refresh_token) are NOT yet known here (they land
        # after schwabdev.Client construction via auth.py:setup_paste_flow /
        # force_refresh, which calls `register_schwab_secrets(...)` again).
        # The factory install is idempotent + process-singleton.
        cfg_secrets: list[str] = []
        for attr in ("client_id", "client_secret", "account_hash"):
            val = getattr(self._cfg, attr, None)
            if val:
                cfg_secrets.append(str(val))
        register_schwab_secrets(cfg_secrets)
        _install_schwab_log_redaction_factory_once()

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
