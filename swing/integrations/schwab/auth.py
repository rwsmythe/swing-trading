"""OAuth paste-back setup, force-refresh, and revocation for Schwab integration.

Per recon doc `docs/schwab-bundle-A-task-A0b-recon.md` §2.2: schwabdev does
NOT expose a separate `auth.manual_flow(...)` callable — OAuth interactive
paste-back is embedded in `schwabdev.Client(...)` construction itself. This
module's functions wrap that construction (`setup_paste_flow`) and surface
the force-refresh (`force_refresh`) + revocation (`revoke_and_delete`) paths.

Full implementations land in:
  * T-A.4 — `setup_paste_flow` (paste-back via `schwabdev.Client(...)`).
  * T-A.5 — `force_refresh` (via `client.update_tokens(force_refresh_token=True)`)
            + `revoke_and_delete` (manual `POST /v1/oauth/revoke` per recon §2.5).

T-A.4 implements `setup_paste_flow`. T-A.5 stubs remain `NotImplementedError`.

LIVE-LIBRARY DEVIATION (T-A.4 banked as V2.1 §VII.F amendment): the recon
doc §2.1 enumerated the constructor signature from `client.md` documentation
as having `tokens_db=` + `open_browser_for_auth=True` kwargs. Live inspection
of the installed `schwabdev==2.5.1` reveals the actual constructor signature
to be: `Client(app_key, app_secret, callback_url='https://127.0.0.1',
tokens_file='tokens.json', timeout=10, capture_callback=False,
use_session=True, call_on_notify=None)`. The implementation MUST use the
actual installed signature — `tokens_file=` (NOT `tokens_db=`) and
`capture_callback=False` (no `open_browser_for_auth=` kwarg exists). Banked
as additional plan-text amendment to recon doc §6 §B.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from swing.config_user import _user_home
from swing.integrations.schwab import audit_service
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
    SchwabRefreshTokenExpiredError,
    _suppress_transport_debug_logs,
    ensure_schwab_log_redaction_factory_installed,
    register_schwab_secrets,
)

log = logging.getLogger(__name__)


def _now_ms_iso() -> str:
    """ISO 8601 server-stamp at handler entry (Phase 8 server-stamping
    discipline). Matches the format used by Finviz audit + Phase 9 services.
    """
    return datetime.now().isoformat(timespec="microseconds")


def _resolve_tokens_db_path(environment: str) -> Path:
    """Per-env tokens DB / file path under `~/swing-data/`.

    The path is constructed for the schwabdev `tokens_file=` kwarg. The
    schwabdev 2.5.1 default filename suggests JSON-format on-disk storage
    (per `client.md` L41 in installed package); we anchor to a per-env
    name so sandbox + production never share the same on-disk state.

    Per CLAUDE.md gotcha: tests MUST monkeypatch `USERPROFILE` AND `HOME`
    before invoking — `_user_home()` reads them unmonkeypatched.
    """
    return _user_home() / "swing-data" / f"schwab-tokens.{environment}.db"


def _is_pipeline_active(conn: sqlite3.Connection) -> bool:
    """Plan §H.10 pipeline-active exclusion check.

    Mirrors `swing.integrations.finviz_api._perform_finviz_fetch_no_lease`
    intent. The CLI surface refuses to run while a pipeline run is in
    flight unless the operator passes `--force`.
    """
    row = conn.execute(
        "SELECT 1 FROM pipeline_runs WHERE state = 'running' LIMIT 1",
    ).fetchone()
    return row is not None


def _stub_call_account_linked(client: Any) -> Any:
    """T-A.4 placeholder for the `client.account_linked()` invocation.

    Full implementation lands at T-B.1 in `swing/integrations/schwab/trader.py`
    (`get_accounts_linked`). T-A.4 calls schwabdev directly; tests patch
    this function (NOT schwabdev) to bypass the real network call.

    Returns the parsed JSON payload (expected: list of
    `{accountNumber, hashValue}` dicts; D2 hotfix — on Schwab auth failure
    schwabdev's wrapper returns a dict-shaped error envelope instead).
    schwabdev's `Client.account_linked()` returns a `requests.Response`;
    we accept either a list/dict (for stub) or a `.json()`-callable object.
    Validation of the shape happens at the call site so the audit row
    can carry an `auth_failed` status with a non-leaky error message.
    """
    result = client.account_linked()
    # Tolerate both raw payloads (test stubs) and Response-like objects
    # (real schwabdev). Real schwabdev returns a Response.
    if hasattr(result, "json") and callable(result.json):
        return result.json()
    return result


def _redacted_excerpt(exc: BaseException, *, max_chars: int = 80) -> str:
    """Sanitise an exception message for audit-row + operator-visible echo.

    Delegates to `swing.integrations.schwab.client._redact_error_message_for_audit`
    so every audit-row `error_message` write benefits from BOTH Layer-0
    exact-replace against `_GLOBAL_KNOWN_SECRETS` (catches SHORT registered
    secrets that the heuristic regex would miss — e.g. a 14-char client_id)
    AND Layer-1 heuristic regex (hex 32+, base64 24+). Codex R2 Major #1 fix.

    Keep the exception class name as the primary identifier — the message
    itself is best-effort context only. Bounded length so an upstream library
    cannot blow out the audit table.

    Codex R3 Major #1 fix: REDACT FIRST, TRUNCATE AFTER. If a registered
    secret straddles the `max_chars` byte boundary in the raw string, a
    pre-redaction truncation would leave only a partial-prefix of the secret
    in the buffer — Layer-0's exact-replace cannot match a partial substring
    and Layer-1's heuristic regex might not catch a short prefix either,
    leaking secret bytes into the audit row. `_redact_error_message_for_audit`
    internally bounds its input to 500 chars (per plan §H.8
    `_make_redactor_from_global`) so passing the full untruncated message is
    safe; the outer 80-char truncation is the audit-row-column-budget cap
    applied to the ALREADY-redacted string.
    """
    raw = f"{type(exc).__name__}: {exc!s}"
    # Layer-0 exact-replace from _GLOBAL_KNOWN_SECRETS + Layer-1 heuristic
    # regex applied to the FULL message BEFORE truncation.
    from swing.integrations.schwab.client import _redact_error_message_for_audit

    redacted = _redact_error_message_for_audit(raw)
    return redacted[:max_chars]


def setup_paste_flow(
    cfg: Any,
    environment: str,
    client_id: str,
    client_secret: str,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
    account_picker: Any = None,
) -> dict:
    """OAuth paste-back setup flow — plan §H.1 (recon-doc amended).

    Algorithm:
      1. Server-stamp start_ts at handler entry.
      2. Validate environment + credentials.
      3. Refuse if pipeline state='running' unless force=True.
      4. Resolve per-env tokens path.
      5. INSERT in-flight audit row (oauth.code_exchange / cli / env).
      6. Wrap `schwabdev.Client(...)` construction in
         `_suppress_transport_debug_logs()`; schwabdev prints consent
         URL + blocks on stdin paste.
      7. On Client-construction success: UPDATE audit row status='success'.
      8. SECOND audit pair around `account_linked()` (endpoint=
         'accounts.linked').
      9. Pick primary account: auto-pick if singleton; prompt via
         `account_picker(accounts)` if multiple (test stub returns the
         desired index; real CLI passes a click.prompt-based callable).
      10. Persist chosen account_hash via `write_user_overrides`.
      11. Return summary dict (tests assert against shape):
          {'tokens_path': <path str>, 'account_hash': <str>,
           'environment': <env>, 'call_id_setup': <int>,
           'call_id_account_linked': <int>}.

    On any schwabdev exception OR `account_linked` failure: UPDATE audit
    row status='auth_failed' + raise `SchwabAuthError`. CLI catches +
    surfaces to operator as redacted non-zero exit.

    The `account_picker` parameter is the test injection seam: when None,
    raises an error for multi-account (tests with click.CliRunner override
    via stdin prompt; the CLI subcommand provides a `click.prompt`-based
    callable). Single-account auto-picks regardless.
    """
    # Step 1 — server-stamp BEFORE any I/O (Phase 8 discipline).
    start_ts = _now_ms_iso()

    # Step 2 — validate inputs.
    if environment not in ("sandbox", "production"):
        raise SchwabConfigMissingError(
            f"environment must be 'sandbox' or 'production'; got {environment!r}",
        )
    if not client_id or not isinstance(client_id, str) or not client_id.strip():
        raise SchwabConfigMissingError(
            "client_id is required (non-empty string)",
        )
    if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
        raise SchwabConfigMissingError(
            "client_secret is required (non-empty string)",
        )

    # Step 3 — pipeline-active exclusion (plan §H.10).
    if not force and _is_pipeline_active(conn):
        raise SchwabPipelineActiveError(
            "Pipeline run in progress; cannot run schwab setup. "
            "Use --force to override.",
        )

    # Step 4 — resolve per-env tokens path. Parent dir created so schwabdev
    # writes succeed first-call.
    tokens_path = _resolve_tokens_db_path(environment)
    tokens_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 5 — INSERT in-flight audit row for the Client construction
    # call (oauth.code_exchange endpoint per migration 0018 CHECK enum).
    call_id_setup = audit_service.record_call_start(
        conn,
        ts=start_ts,
        endpoint="oauth.code_exchange",
        pipeline_run_id=None,
        surface="cli",
        environment=environment,
    )

    # T-A.10 — register cfg-known sensitive bytes BEFORE constructing
    # schwabdev.Client so any log records emitted during construction (incl.
    # the auth-failure paths in schwabdev/tokens.py) flow through the Layer-2
    # redactor with these secrets already in the registry. Use
    # `ensure_schwab_log_redaction_factory_installed()` (R8 M#2 defense)
    # rather than `_install_*_once()`: if another library replaced the
    # process-global LogRecord factory after our initial install, the
    # ensure-helper re-wraps it so redaction stays active for this call.
    register_schwab_secrets([client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()

    # Step 6 — construct schwabdev.Client(...). Implementation deviation
    # from recon doc §2.1: live schwabdev 2.5.1 uses `tokens_file=`
    # (NOT `tokens_db=`) + has NO `open_browser_for_auth=` kwarg.
    construction_start = time.monotonic()
    try:
        # Import here so test fixtures can `monkeypatch.setattr(
        # "schwabdev.Client", ...)` BEFORE the call site references it.
        import schwabdev
        with _suppress_transport_debug_logs():
            client = schwabdev.Client(
                app_key=client_id,
                app_secret=client_secret,
                callback_url=cfg.integrations.schwab.callback_url,
                tokens_file=str(tokens_path),
                timeout=int(cfg.integrations.schwab.timeout_seconds),
            )
        elapsed_ms = int((time.monotonic() - construction_start) * 1000)
    except SchwabPipelineActiveError:
        raise
    except BaseException as exc:
        elapsed_ms = int((time.monotonic() - construction_start) * 1000)
        # Step 10 (failure-path) — UPDATE audit row status='auth_failed'.
        audit_service.record_call_finish(
            conn,
            call_id=call_id_setup,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        log.warning(
            "schwab setup paste-back flow failed: %s",
            type(exc).__name__,
        )
        raise SchwabAuthError(
            500,
            f"<schwabdev construction failed: {type(exc).__name__}>",
        ) from exc

    # D1 hotfix (operator-paired phase-2 verification 2026-05-14):
    # schwabdev.Client(...) does NOT raise on OAuth failure — it prints +
    # retries internally + returns a Client object regardless. If the OAuth
    # exchange ultimately failed, `client.tokens.access_token` is None /
    # empty / non-string. Treat that case as auth_failed (the existing
    # `try/except BaseException` above never fires because schwabdev
    # swallowed the exception internally).
    access_token = getattr(getattr(client, "tokens", None), "access_token", None)
    if not access_token or not isinstance(access_token, str):
        audit_service.record_call_finish(
            conn,
            call_id=call_id_setup,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=(
                "<schwabdev returned Client without access_token; "
                "OAuth exchange likely failed>"
            ),
        )
        log.warning(
            "schwab setup paste-back returned Client with no access_token "
            "(OAuth exchange likely failed silently inside schwabdev)",
        )
        raise SchwabAuthError(
            401,
            "<OAuth exchange failed: schwabdev returned Client without "
            "access_token>",
        )

    # T-A.10 — register the live tokens that schwabdev's Client populated.
    # Subsequent log records (in this CLI process AND any future schwabdev
    # API call within the same process via SchwabClient) flow through the
    # Layer-2 redactor with these tokens in the registry. Best-effort: the
    # tokens may be empty in adversarial test stubs; `register_schwab_secrets`
    # ignores empty/short values.
    refresh_token = getattr(getattr(client, "tokens", None), "refresh_token", None)
    register_schwab_secrets([access_token, refresh_token])

    # Step 7 — happy-path audit close for the setup call.
    audit_service.record_call_finish(
        conn,
        call_id=call_id_setup,
        http_status=200,
        status="success",
        response_time_ms=elapsed_ms,
        signature_hash=None,
        rate_limit_remaining=None,
        error_message=None,
    )

    # Step 8 — SECOND audit-row pair around `client.account_linked()`.
    account_linked_start_ts = _now_ms_iso()
    call_id_account_linked = audit_service.record_call_start(
        conn,
        ts=account_linked_start_ts,
        endpoint="accounts.linked",
        pipeline_run_id=None,
        surface="cli",
        environment=environment,
    )
    account_linked_start = time.monotonic()
    try:
        accounts = _stub_call_account_linked(client)
    except BaseException as exc:
        elapsed_ms = int((time.monotonic() - account_linked_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id_account_linked,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        raise SchwabAuthError(
            500,
            f"<account_linked failed: {type(exc).__name__}>",
        ) from exc

    elapsed_ms = int((time.monotonic() - account_linked_start) * 1000)

    # D2 hotfix (operator-paired phase-2 verification 2026-05-14) +
    # Codex R1 Major #3 — validate ALL shape/empty conditions BEFORE
    # closing the audit row as success. Prior ordering closed the row
    # success FIRST + then raised on empty list, mis-reporting an
    # auth-failure as a successful call in the audit table.
    if not isinstance(accounts, list):
        audit_service.record_call_finish(
            conn,
            call_id=call_id_account_linked,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=(
                f"<account_linked returned {type(accounts).__name__}; "
                f"expected list>"
            ),
        )
        raise SchwabAuthError(
            500,
            f"<account_linked returned unexpected shape: "
            f"{type(accounts).__name__}>",
        )
    # Codex R1 Major #3 — empty-list rejection MUST audit-fail BEFORE
    # the success close, not after.
    if not accounts:
        audit_service.record_call_finish(
            conn,
            call_id=call_id_account_linked,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message="<account_linked returned empty list>",
        )
        raise SchwabAuthError(
            500,
            "<account_linked returned empty list; expected at least 1 account>",
        )
    for _idx, _entry in enumerate(accounts):
        if not isinstance(_entry, dict) or "hashValue" not in _entry:
            audit_service.record_call_finish(
                conn,
                call_id=call_id_account_linked,
                http_status=None,
                status="auth_failed",
                response_time_ms=elapsed_ms,
                signature_hash=None,
                rate_limit_remaining=None,
                error_message=(
                    f"<account_linked entry {_idx} missing hashValue or "
                    f"not dict>"
                ),
            )
            raise SchwabAuthError(
                500,
                f"<account_linked entry {_idx} has unexpected shape>",
            )

    # All shape + non-empty validation passed; safe to record success.
    audit_service.record_call_finish(
        conn,
        call_id=call_id_account_linked,
        http_status=200,
        status="success",
        response_time_ms=elapsed_ms,
        signature_hash=None,
        rate_limit_remaining=None,
        error_message=None,
    )

    # Step 9 — pick primary account. (Empty-list case already handled
    # pre-success above per Codex R1 Major #3.)
    if len(accounts) == 1:
        chosen = accounts[0]
    else:
        if account_picker is None:
            raise SchwabConfigMissingError(
                f"multi-account setup requires an account_picker callable; "
                f"got {len(accounts)} linked accounts and no picker",
            )
        chosen_idx = account_picker(accounts)
        if not isinstance(chosen_idx, int) or not (0 <= chosen_idx < len(accounts)):
            raise SchwabConfigMissingError(
                f"account_picker must return int in [0, {len(accounts)}); "
                f"got {chosen_idx!r}",
            )
        chosen = accounts[chosen_idx]

    account_hash = chosen.get("hashValue")
    if not account_hash or not isinstance(account_hash, str):
        raise SchwabAuthError(
            500,
            "<chosen account missing hashValue>",
        )

    # T-A.10 — register the operator's chosen account_hash. Future log
    # records that interpolate the hash (e.g., request URL contains the
    # account-hash path segment per Schwab API V2 spec; schwabdev may log
    # the URL on retry) flow through Layer-2 redaction with the hash known.
    register_schwab_secrets([account_hash])

    # Step 10 — persist via cfg-cascade write. USERPROFILE+HOME monkeypatch
    # in tests; production reads operator's real ~/swing-data/user-config.toml.
    from swing.config_user import load_user_overrides, write_user_overrides

    overrides = load_user_overrides()
    overrides.setdefault("integrations", {}).setdefault("schwab", {})[
        "account_hash"
    ] = account_hash
    write_user_overrides(overrides)

    return {
        "tokens_path": str(tokens_path),
        "account_hash": account_hash,
        "environment": environment,
        "call_id_setup": call_id_setup,
        "call_id_account_linked": call_id_account_linked,
        "num_accounts": len(accounts),
    }


def force_refresh(
    cfg: Any,
    environment: str,
    client_id: str,
    client_secret: str,
    conn: sqlite3.Connection,
) -> dict:
    """Force-rotate the access_token using the existing refresh_token —
    plan §H.2 (recon §6.bis live-library deviation).

    Algorithm:
      1. Server-stamp start_ts at handler entry.
      2. Validate environment + credentials.
      3. Resolve per-env tokens DB path.
      4. INSERT in-flight audit row (oauth.refresh / cli / env).
      5. Construct schwabdev.Client(...) — Client.__init__ loads existing
         tokens from `tokens_file` without re-prompting when valid; the
         daemon-thread checker schwabdev spawns is `daemon=True` so does
         not block process exit.
      6. Invoke `client.tokens.update_tokens(force_access_token=True)`.

         DEVIATION from plan §H.2 step 6 (banked as V2.1 §VII.F amendment
         candidate): plan text + recon §2.4 said `force_refresh_token=True`,
         but live schwabdev tokens.py L160-198 shows that flag invokes the
         full OAuth dance (`update_refresh_token` triggers `input()` for
         the paste-back URL). The V1 semantic of `swing schwab refresh` is
         "rotate access_token using existing refresh_token without a re-
         auth prompt" — schwabdev's `force_access_token=True` flag does
         exactly that (calls `update_access_token` which POSTs to
         /v1/oauth/token with grant_type=refresh_token).

      7. UPDATE audit row terminal status:
         * 'success' if update succeeded;
         * 'auth_failed' for SchwabRefreshTokenExpiredError / SchwabAuthError;
         * 'error' for SchwabApiError (network / transient);
         * 'auth_failed' for any other BaseException (defensive).
      8. On success: return summary with `call_id` + `tokens_path`.

    Concurrent-safe (Codex R1 Minor #3 LOCK): NO pipeline-active gate.
    schwabdev's RLock + the SQLite file lock on tokens_file handle the
    race naturally. `refresh` has NO `--force` flag at the CLI layer.

    Raises:
      * SchwabConfigMissingError — invalid environment or empty credentials.
      * SchwabRefreshTokenExpiredError — refresh_token expired/revoked.
      * SchwabAuthError — other authentication failure.
      * SchwabApiError — non-auth network/transient failure.
    """
    # Step 1 — server-stamp BEFORE any I/O.
    start_ts = _now_ms_iso()

    # Step 2 — validate inputs.
    if environment not in ("sandbox", "production"):
        raise SchwabConfigMissingError(
            f"environment must be 'sandbox' or 'production'; got {environment!r}",
        )
    if not client_id or not isinstance(client_id, str) or not client_id.strip():
        raise SchwabConfigMissingError(
            "client_id is required (non-empty string)",
        )
    if (
        not client_secret
        or not isinstance(client_secret, str)
        or not client_secret.strip()
    ):
        raise SchwabConfigMissingError(
            "client_secret is required (non-empty string)",
        )

    # Step 3 — resolve per-env tokens path.
    tokens_path = _resolve_tokens_db_path(environment)
    tokens_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 4 — INSERT in-flight audit row.
    call_id = audit_service.record_call_start(
        conn,
        ts=start_ts,
        endpoint="oauth.refresh",
        pipeline_run_id=None,
        surface="cli",
        environment=environment,
    )

    # T-A.10 — register cfg-known sensitive bytes BEFORE constructing
    # schwabdev.Client + invoking update_tokens. Use `ensure_*` (R8 M#2
    # defense) so a third-party library that replaced the process-global
    # LogRecord factory after our initial install gets re-wrapped before
    # this auth-sensitive call fires.
    register_schwab_secrets([client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()

    # Step 5+6 — construct Client + invoke update_tokens.
    call_start = time.monotonic()
    try:
        import schwabdev
        with _suppress_transport_debug_logs():
            client = schwabdev.Client(
                app_key=client_id,
                app_secret=client_secret,
                callback_url=cfg.integrations.schwab.callback_url,
                tokens_file=str(tokens_path),
                timeout=int(cfg.integrations.schwab.timeout_seconds),
            )
            # Codex R1 Major #1 (parity with D1 setup hotfix) — capture
            # the pre-call access_token so we can detect schwabdev
            # returning normally without actually rotating it. schwabdev
            # swallows some refresh failures internally (matching the
            # D1 paste-back failure mode); a silent failure-to-rotate
            # MUST close the audit row as auth_failed, not success.
            pre_call_access_token = getattr(
                getattr(client, "tokens", None), "access_token", None,
            )
            # See docstring DEVIATION block — `force_access_token=True` is
            # the live-library semantic match for "rotate access_token via
            # refresh_token without re-auth prompt".
            client.tokens.update_tokens(force_access_token=True)
        elapsed_ms = int((time.monotonic() - call_start) * 1000)
    except SchwabRefreshTokenExpiredError as exc:
        elapsed_ms = int((time.monotonic() - call_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=401,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        log.warning("schwab refresh: refresh_token expired or revoked")
        raise
    except SchwabAuthError as exc:
        elapsed_ms = int((time.monotonic() - call_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=getattr(exc, "status_code", None),
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        raise
    except SchwabApiError as exc:
        elapsed_ms = int((time.monotonic() - call_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            status="error",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        raise
    except BaseException as exc:
        elapsed_ms = int((time.monotonic() - call_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        log.warning(
            "schwab refresh failed (catch-all): %s",
            type(exc).__name__,
        )
        raise SchwabAuthError(
            500,
            f"<refresh failed: {type(exc).__name__}>",
        ) from exc

    # Codex R1 Major #1 — silent-failure detection mirroring the D1
    # setup hotfix. If schwabdev returns normally from update_tokens but
    # does NOT actually rotate the token (e.g., suppressed-failure path
    # we cannot see), the post-call `client.tokens.access_token` will
    # either be (a) empty / None / non-string, OR (b) byte-identical to
    # the pre-call value. Both cases MUST close the audit row as
    # auth_failed + raise — otherwise an operator's `swing schwab
    # refresh` reports success while the underlying token is stale.
    new_access = getattr(getattr(client, "tokens", None), "access_token", None)
    new_refresh = getattr(getattr(client, "tokens", None), "refresh_token", None)
    if not new_access or not isinstance(new_access, str):
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=(
                "<schwabdev update_tokens returned without populating "
                "access_token; refresh likely failed silently>"
            ),
        )
        log.warning(
            "schwab refresh: update_tokens returned but tokens.access_token "
            "is missing/empty (silent failure)",
        )
        raise SchwabAuthError(
            401,
            "<refresh failed: schwabdev returned without rotating "
            "access_token>",
        )
    if pre_call_access_token and new_access == pre_call_access_token:
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=(
                "<schwabdev update_tokens returned but access_token "
                "unchanged from pre-call value; refresh likely failed "
                "silently>"
            ),
        )
        log.warning(
            "schwab refresh: update_tokens returned but access_token "
            "did not change (silent failure)",
        )
        raise SchwabAuthError(
            401,
            "<refresh failed: schwabdev returned without rotating "
            "access_token (value unchanged)>",
        )

    # T-A.10 — register the freshly-rotated tokens. The registry is
    # additive: the old access_token already there stays registered (per
    # Codex R3 Major #2 process-global UNION discipline), so any log
    # record that interpolates either old OR new token gets redacted.
    register_schwab_secrets([new_access, new_refresh])

    # Step 7 (success) — close audit row.
    audit_service.record_call_finish(
        conn,
        call_id=call_id,
        http_status=200,
        status="success",
        response_time_ms=elapsed_ms,
        signature_hash=None,
        rate_limit_remaining=None,
        error_message=None,
    )

    return {
        "call_id": call_id,
        "tokens_path": str(tokens_path),
        "environment": environment,
    }


def revoke_and_delete(
    cfg: Any,
    environment: str,
    client_id: str,
    client_secret: str,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
) -> dict:
    """Revoke the refresh_token at Schwab + atomically rename the per-env
    tokens DB to `<path>.deleted-<ts>` for 24h recovery — plan §F.3 + §H.2
    revoke surface.

    Algorithm:
      1. Server-stamp start_ts.
      2. Refuse if pipeline state='running' UNLESS force=True (mirrors
         setup; logout DOES have --force).
      3. Resolve env + tokens path.
      4. Read existing tokens file → extract refresh_token for revoke body.
         If file missing/unreadable → audit-row 'error' + raise.
      5. INSERT in-flight audit row (oauth.revoke / cli / env).
      6. POST https://api.schwabapi.com/v1/oauth/revoke
         (form-urlencoded body, Basic auth header).
         Wrap in try/except — non-200 + network failures tolerated per
         plan §E.6 (best-effort revocation).
      7. UPDATE audit row terminal status (success on HTTP 200; error
         otherwise).
      8. os.replace(path, path + f'.deleted-{ts}') — same-volume rename,
         no cross-device-link risk (CLAUDE.md gotcha).
      9. Return summary dict.

    The rename happens REGARDLESS of revoke success/failure — operator's
    intent on `logout` is "deactivate this device's tokens locally" and
    revocation-at-Schwab is best-effort.

    Raises:
      * SchwabConfigMissingError — invalid environment.
      * SchwabPipelineActiveError — pipeline running + force=False.
      * SchwabApiError — tokens file missing (cannot extract refresh_token).
    """
    import base64
    import os
    from datetime import datetime as _dt

    import requests

    # Step 1.
    start_ts = _now_ms_iso()

    # Step 2 — validate inputs + pipeline-active check.
    if environment not in ("sandbox", "production"):
        raise SchwabConfigMissingError(
            f"environment must be 'sandbox' or 'production'; got {environment!r}",
        )
    if not client_id or not isinstance(client_id, str) or not client_id.strip():
        raise SchwabConfigMissingError(
            "client_id is required (non-empty string)",
        )
    if (
        not client_secret
        or not isinstance(client_secret, str)
        or not client_secret.strip()
    ):
        raise SchwabConfigMissingError(
            "client_secret is required (non-empty string)",
        )
    if not force and _is_pipeline_active(conn):
        raise SchwabPipelineActiveError(
            "Pipeline run in progress; cannot run schwab logout. "
            "Use --force to override.",
        )

    # Step 3 — resolve tokens path.
    tokens_path = _resolve_tokens_db_path(environment)

    # Step 4 — read tokens file. If missing/unreadable, surface a clean
    # error + audit row. We INSERT the in-flight audit row first so the
    # failure is observable.
    call_id = audit_service.record_call_start(
        conn,
        ts=start_ts,
        endpoint="oauth.revoke",
        pipeline_run_id=None,
        surface="cli",
        environment=environment,
    )

    refresh_token: str | None = None
    file_missing = not tokens_path.exists()
    if not file_missing:
        try:
            import json as _json
            with open(tokens_path) as f:
                payload = _json.load(f)
            refresh_token = payload.get("token_dictionary", {}).get(
                "refresh_token",
            )
        except Exception as exc:
            log.warning(
                "schwab logout: tokens file unreadable: %s",
                type(exc).__name__,
            )
            refresh_token = None

    if file_missing or not refresh_token:
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            status="error",
            response_time_ms=0,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=(
                "<tokens file missing>" if file_missing
                else "<refresh_token missing from tokens file>"
            ),
        )
        raise SchwabApiError(
            f"<cannot logout: tokens file missing or unreadable at {tokens_path}>",
        )

    # Codex R1 Major #2 — register cfg-known sensitive bytes + ensure
    # the redaction factory is current before the manual POST. The
    # refresh_token extracted above + client_id + client_secret are
    # interpolated into the Authorization header / form body — if
    # `requests`-side debug logging emits them, the LogRecord factory
    # must redact. `ensure_*` (not `_install_*_once`) catches the case
    # where another library replaced the process-global factory after
    # our initial install.
    register_schwab_secrets([client_id, client_secret, refresh_token])
    ensure_schwab_log_redaction_factory_installed()

    # Step 5+6 — POST /v1/oauth/revoke (best-effort).
    auth_header = base64.b64encode(
        f"{client_id}:{client_secret}".encode(),
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "token": refresh_token,
        "token_type_hint": "refresh_token",
    }
    call_start = time.monotonic()
    http_status: int | None = None
    revoke_status = "error"
    revoke_error_message: str | None = None
    try:
        with _suppress_transport_debug_logs():
            response = requests.post(
                "https://api.schwabapi.com/v1/oauth/revoke",
                headers=headers,
                data=data,
                timeout=int(cfg.integrations.schwab.timeout_seconds),
            )
        http_status = getattr(response, "status_code", None)
        if http_status == 200:
            revoke_status = "success"
        else:
            revoke_status = "error"
            revoke_error_message = f"<revoke returned HTTP {http_status}>"
    except BaseException as exc:
        revoke_status = "error"
        revoke_error_message = _redacted_excerpt(exc)
        log.warning(
            "schwab logout: revoke POST failed: %s",
            type(exc).__name__,
        )
    elapsed_ms = int((time.monotonic() - call_start) * 1000)

    # Step 7 — close audit row.
    audit_service.record_call_finish(
        conn,
        call_id=call_id,
        http_status=http_status,
        status=revoke_status,
        response_time_ms=elapsed_ms,
        signature_hash=None,
        rate_limit_remaining=None,
        error_message=revoke_error_message,
    )

    # Step 8 — atomic rename. Same-volume → no cross-device-link risk.
    rename_ts = _dt.now().strftime("%Y%m%dT%H%M%S")
    deleted_path = tokens_path.with_name(
        f"{tokens_path.name}.deleted-{rename_ts}",
    )
    os.replace(str(tokens_path), str(deleted_path))

    return {
        "call_id": call_id,
        "tokens_path": str(tokens_path),
        "deleted_path": str(deleted_path),
        "environment": environment,
        "revoke_status": revoke_status,
    }
