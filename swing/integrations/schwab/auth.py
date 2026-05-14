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
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
    _suppress_transport_debug_logs,
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

    Strip any token-shaped substrings. Keep the exception class name as the
    primary identifier — the message itself is best-effort context only.
    Bounded length so an upstream library cannot blow out the audit table.
    """
    raw = f"{type(exc).__name__}: {exc!s}"
    truncated = raw[:max_chars]
    # Defense-in-depth: scrub any long alphanumeric runs that could be
    # token-shaped (32+ chars). schwabdev tokens are typically 30+ chars
    # base64-shaped; the regex in `_redact_message` covers `/`, `=`, `:`
    # delimiters but a free-text exception message may include them bare.
    import re

    return re.sub(r"[A-Za-z0-9_+/=\-]{24,}", "<REDACTED>", truncated)


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

    # D2 hotfix (operator-paired phase-2 verification 2026-05-14):
    # schwabdev's `client.account_linked()` returns a DICT (Schwab error
    # envelope) when the Client has no valid tokens — NOT a list. The
    # subsequent `accounts[0]` would raise `KeyError: 0`. Validate shape
    # explicitly + close the audit row as auth_failed when malformed.
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

    # Step 9 — pick primary account.
    if not accounts:
        raise SchwabAuthError(
            500,
            "<account_linked returned empty list; expected at least 1 account>",
        )
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


def force_refresh(*args: Any, **kwargs: Any) -> Any:
    """Force-rotate access + refresh tokens — implementation lands in T-A.5."""
    raise NotImplementedError("force_refresh lands in T-A.5")


def revoke_and_delete(*args: Any, **kwargs: Any) -> Any:
    """Revoke refresh_token + delete per-env tokens DB — implementation lands
    in T-A.5."""
    raise NotImplementedError("revoke_and_delete lands in T-A.5")
