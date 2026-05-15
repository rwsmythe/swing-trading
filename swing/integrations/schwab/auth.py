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
import os
import sqlite3
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import click

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


# T-A.1 — env-var names operator sets to skip the interactive prompt.
# Both must be set together; partial sets raise SchwabConfigMissingError
# rather than silently falling back to prompting only the missing one.
_ENV_VAR_CLIENT_ID = "SCHWAB_CLIENT_ID"
_ENV_VAR_CLIENT_SECRET = "SCHWAB_CLIENT_SECRET"

# T-A.2 collision-disambiguation loop upper bound. The disambiguation branch
# (`<canonical>.deleted-<ts>-1`, `-2`, ...) is unreachable in normal
# operation — same-second double-invocation would require parallel `swing
# schwab setup` invocations against the SAME tokens DB, which the CLI is
# not designed for. The bounded loop exists as a defense-in-depth guard
# against pathological filesystem states (e.g. a directory full of
# `*.deleted-<same-ts>-*` siblings); the `else` clause raises with an
# actionable cleanup message rather than spinning forever.
_MAX_RENAME_DISAMBIG_ATTEMPTS = 10_000


def _mask_credential(value: str | None) -> str:
    """Mask a credential value for inclusion in operator-visible error text.

    Mirrors `swing.config_validation.mask_sensitive_value` shape (first 3 +
    `***` + last 2) but with explicit `<absent>` + `<too_short>` markers
    matching dispatch brief §3 T-A.1 acceptance criterion #2's example
    error message ("CLIENT_ID=<masked> CLIENT_SECRET=<absent>").

    Discipline: NEVER includes the raw value in the masked output for
    strings of length >= 5; shorter strings render `<too_short>` rather
    than the raw bytes so operator misconfiguration (one-char paste) does
    not leak into error text.
    """
    if value is None:
        return "<absent>"
    if not value or not value.strip():
        return "<absent>"
    s = value
    if len(s) < 5:
        return "<too_short>"
    return f"{s[:3]}***{s[-2:]}"


def _safe_cfg_attr(cfg: Any, attr: str) -> Any:
    """T-B.1 — duck-typed safe lookup for `cfg.integrations.schwab.<attr>`.

    Returns the attribute value if the chain resolves, else `None`. Tolerates
    cfg objects that are missing the `integrations` / `schwab` sub-namespaces
    (e.g., legacy test stubs constructed before T-B.2 added the cfg fields).
    Tier-2 cfg-resolution treats `None` return identically to empty-string —
    falls through.
    """
    integrations = getattr(cfg, "integrations", None)
    if integrations is None:
        return None
    schwab = getattr(integrations, "schwab", None)
    if schwab is None:
        return None
    return getattr(schwab, attr, None)


def resolve_credentials_env_or_prompt(
    cfg: Any,
    environment: str,
    *,
    allow_prompt: bool = True,
    prompter: Callable[..., str] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve Schwab `client_id` + `client_secret` via env > cfg > prompt cascade.

    Sub-bundle A T-A.1 helper extended at Phase 12 Sub-bundle B T-B.1 —
    consults three tiers in priority order:
      Tier-1 (highest): `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` env
        vars. Both set + non-empty (after `.strip()`) → returns them;
        SKIPS cfg + prompt. If only ONE is set OR either is empty /
        whitespace-only when the other is PRESENT → raises
        `SchwabConfigMissingError` (env-tier partial signals operator
        typo / shell-session error, not legitimate fallback intent).
      Tier-2 (middle; NEW T-B.1): `cfg.integrations.schwab.client_id` +
        `.client_secret`. Both non-empty + non-whitespace → returns them;
        SKIPS prompt. Partial cfg-tier (one set, the other empty /
        whitespace-only) FALLS THROUGH to next tier (differs from
        env-tier — file-tier is operator-friendly, allowing mix of
        env-var-for-secret + file-for-id without forcing an error).
      Tier-3 (lowest): interactive `click.prompt(...)` fallback.

    All resolution paths register the resolved secrets in the Schwab
    redaction registry BEFORE returning so subsequent schwabdev log
    records that interpolate them flow through Layer-2 redaction.

    Args:
        cfg: Config object with `cfg.integrations.schwab.client_id` +
            `.client_secret` fields (T-B.2 added these). When fields are
            empty / whitespace-only / absent (duck-typed), cfg-tier
            falls through.
        environment: Reserved for future per-env credential resolution
            (env-var names + cfg fields are FLAT across environments in
            V1). Retained in signature so callsites pre-bind their env
            scope for future extension.
        allow_prompt: When True, fall back to `click.prompt(...)` (via
            the optional `prompter` parameter) on the FULLY-ABSENT-AT-
            ALL-TIERS case. When False, returns `(None, None)` —
            pipeline path contract (T-A.3 + T-B.1 AC6 extension).
        prompter: Test-injection seam. When None, defaults to
            `click.prompt`. Receives label + `type=str` / `hide_input=`
            kwargs the legacy callsites used.

    Returns:
        Tuple `(client_id, client_secret)`. Both strings on success
        (env-tier, cfg-tier, or prompt). Both None when
        `allow_prompt=False` AND env + cfg are both absent / partial.

    Raises:
        SchwabConfigMissingError: Partial env-tier set (one of two set,
            or empty / whitespace-only). Message names both env-var
            names + masked-form rendering. NOTE: partial cfg-tier does
            NOT raise — it falls through (locked at T-B.1).

    Notes:
        Sentinel-leak guarantee — every successful tier resolution calls
        `register_schwab_secrets(...)` + invokes
        `ensure_schwab_log_redaction_factory_installed()` BEFORE
        returning (CLAUDE.md gotcha family; lesson #2 mirrored from
        Sub-bundle A — pre-call factory-replacement defense).
    """
    raw_id = os.environ.get(_ENV_VAR_CLIENT_ID)
    raw_secret = os.environ.get(_ENV_VAR_CLIENT_SECRET)

    # Normalise: treat empty / whitespace-only as ABSENT-FOR-RESOLUTION but
    # we DISTINGUISH "env var name present in environment" (operator set it,
    # even if to empty) from "env var name absent entirely" because the
    # partial-vs-fully-absent rule discriminates on that distinction (per
    # Sub-bundle A acceptance criterion #3).
    id_present = _ENV_VAR_CLIENT_ID in os.environ
    secret_present = _ENV_VAR_CLIENT_SECRET in os.environ
    id_clean = (raw_id or "").strip()
    secret_clean = (raw_secret or "").strip()
    id_usable = bool(id_clean)
    secret_usable = bool(secret_clean)

    # Tier-1 happy path: both env vars usable → register + return; skip cfg + prompt.
    if id_usable and secret_usable:
        register_schwab_secrets([id_clean, secret_clean])
        ensure_schwab_log_redaction_factory_installed()
        return id_clean, secret_clean

    # Tier-1 partial: at least one env var is PRESENT (operator set it) but
    # the OTHER is missing OR both are present but at least one is empty /
    # whitespace-only. Reject with masked-form error.
    #
    # T-B.1 LOCK (differs from cfg-tier below): partial env-tier RAISES
    # even when cfg-tier could provide a complete fallback. Rationale:
    # operator's stated intent (env vars) failed; falling through to cfg
    # silently would HIDE the misconfiguration. cfg-tier partial, by
    # contrast, falls through because file-tier may legitimately hold one
    # field while the other comes from env or prompt.
    any_present = id_present or secret_present
    if any_present and not (id_usable and secret_usable):
        raise SchwabConfigMissingError(
            f"Both `{_ENV_VAR_CLIENT_ID}` and `{_ENV_VAR_CLIENT_SECRET}` "
            f"must be set together (non-empty, non-whitespace); got "
            f"{_ENV_VAR_CLIENT_ID}={_mask_credential(raw_id)} "
            f"{_ENV_VAR_CLIENT_SECRET}={_mask_credential(raw_secret)}. "
            f"Either set BOTH env vars or UNSET both to fall back to "
            f"cfg fields (~/swing-data/user-config.toml) / interactive prompt.",
        )

    # Tier-2 (NEW T-B.1): consult cfg.integrations.schwab.{client_id,
    # client_secret}. Both fields non-whitespace → use them; skip prompt.
    #
    # T-B.1 LOCK: partial cfg-tier (one field set, the other empty /
    # whitespace-only) FALLS THROUGH to Tier-3 (NOT raises). Rationale per
    # dispatch brief §3 AC2: file-tier is operator-friendly — an operator
    # who has set client_id in user-config.toml but not client_secret may
    # legitimately want to fall through to env or prompt for the secret,
    # rather than being forced into an error state. The asymmetry with the
    # env-tier-partial-raises rule is INTENTIONAL.
    cfg_id_raw = _safe_cfg_attr(cfg, "client_id")
    cfg_secret_raw = _safe_cfg_attr(cfg, "client_secret")
    cfg_id_clean = (cfg_id_raw or "").strip() if isinstance(cfg_id_raw, str) else ""
    cfg_secret_clean = (
        (cfg_secret_raw or "").strip()
        if isinstance(cfg_secret_raw, str)
        else ""
    )
    if cfg_id_clean and cfg_secret_clean:
        # Sentinel-leak guarantee (mirrors env-tier path): register cfg-
        # sourced secrets in Layer-0 known-secrets registry BEFORE returning.
        # Use `ensure_*` (Sub-bundle A lesson #2: factory-replacement defense)
        # rather than `_install_*_once` so any third-party library that
        # replaced the process-global LogRecord factory after our initial
        # install gets re-wrapped before downstream schwabdev calls fire.
        register_schwab_secrets([cfg_id_clean, cfg_secret_clean])
        ensure_schwab_log_redaction_factory_installed()
        return cfg_id_clean, cfg_secret_clean

    # Tier-3: all preceding tiers fell through (env fully absent + cfg
    # absent / partial). If allow_prompt=False, return (None, None) —
    # pipeline path contract; criterion 6 bullet 3+4 (env+cfg absent OR
    # env absent + partial cfg both produce None pair under this branch).
    if not allow_prompt:
        return None, None

    # Both absent + prompt allowed → fall back to interactive prompt.
    if prompter is None:
        prompter = click.prompt

    client_id = prompter("Schwab app client_id", type=str)
    client_secret = prompter(
        "Schwab app client_secret", type=str, hide_input=True,
    )
    # Apply the same `.strip()` discipline the legacy callsites used.
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not client_id:
        raise SchwabConfigMissingError(
            "client_id is required (non-empty).",
        )
    if not client_secret:
        raise SchwabConfigMissingError(
            "client_secret is required (non-empty).",
        )
    register_schwab_secrets([client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()
    return client_id, client_secret


def _now_ms_iso() -> str:
    """ISO 8601 server-stamp at handler entry (Phase 8 server-stamping
    discipline). Matches the format used by Finviz audit + Phase 9 services.
    """
    return datetime.now().isoformat(timespec="microseconds")


def _utc_now() -> datetime:
    """T-A.2 — module-level wall-clock helper used by the self-heal rename
    path (`_rename_stale_tokens_db`).

    Extracted so tests can `monkeypatch.setattr(auth_mod, "_utc_now", ...)`
    to inject a deterministic timestamp for the collision-disambiguation
    test (Test 3 of `test_schwab_setup_self_healing.py`).
    """
    import datetime as _dt
    return datetime.now(_dt.UTC)


def _rename_stale_tokens_db(
    tokens_db_path: Path,
    *,
    environment: str,
    conn: sqlite3.Connection,
) -> Path | None:
    """T-A.2 — atomically rename an existing tokens DB to a `.deleted-<ts>`
    sibling BEFORE invoking schwabdev's `Client.__init__`.

    Solves operator-pain from 2026-05-14 gate: `Client.__init__` auto-attempts
    a refresh against any existing tokens DB and hard-fails if the refresh
    token has expired (or any other auth-refresh failure), never reaching
    the paste-back code path. Pre-T-A.2 operator recovery was the
    `logout → setup` sequence (per CLAUDE.md gotcha "swing schwab setup
    requires clean tokens DB state").

    Algorithm:
      1. If `tokens_db_path` does NOT exist → return `None` (no-op).
      2. Build candidate `<path>.deleted-<YYYYmmddTHHMMSS>` — same timestamp
         FORMAT as `revoke_and_delete` (logout) uses (`%Y%m%dT%H%M%S`), so
         the renamed-file suffix string convention is consistent across
         setup + logout self-heal paths. SEMANTIC ANCHOR DEVIATION: this
         self-heal path uses UTC-aware `_utc_now()` (intentional; matches
         modern convention) while `revoke_and_delete` currently uses naïve
         `datetime.now()` (local time). Operators scanning `*.deleted-*`
         files by timestamp will see a 4-5 hour gap between adjacent
         self-heal + logout actions during the same wall-clock session.
         Banked as V2.1 §VII.F amendment candidate (unify logout on UTC);
         logout is out-of-scope for T-A.2 per dispatch brief §6.
      3. Atomic CLAIM-then-replace: try `os.open(..., O_CREAT|O_EXCL)` on
         each candidate suffix. `O_EXCL` guarantees that the syscall fails
         atomically if the path already exists (race-free even under
         concurrent same-second double-invocation). On `FileExistsError`,
         disambiguate to `-1`, `-2`, ... and try again. NEVER overwrite a
         prior renamed file (Codex R1 Major fix 2026-05-15: pre-fix used
         `exists()`-then-`os.replace` which had a TOCTOU window where
         another process could create the same `.deleted-<ts>` path
         between the exists-check and the rename — `os.replace` would
         then silently overwrite the prior process's renamed file).
         Bounded by `_MAX_RENAME_DISAMBIG_ATTEMPTS`; pathological
         filesystem states raise `RuntimeError` rather than spinning
         forever.
      4. Audit lifecycle opens BEFORE any claim or rename side effect:
         `record_call_start(endpoint='oauth.code_exchange')` emits the
         in-flight audit row BEFORE the O_EXCL claim loop AND before
         `os.replace` so EVERY failure mode (claim-step OSError such as
         PermissionError / ENOSPC / antivirus interference, replace-step
         OSError such as Windows file-in-use / EACCES, or
         disambiguation-exhaustion RuntimeError) leaves an audit trail.
         Mirrors the canonical setup-flow pattern at `setup_paste_flow`
         :595-602 + the revoke-and-delete pattern at `:1276-1308`.
      5. `os.replace` (same-volume; both source + dest in `~/swing-data/` →
         no cross-device-link risk per CLAUDE.md gotcha). On `OSError`,
         close the audit row with `status='error'`, `error_message` =
         redacted excerpt of the failure (still prefixed with
         "auto-detected" + "renamed" so operators can grep failed
         self-heal attempts), then re-raise.
      6. On success: close the audit row with `status='success'`,
         `error_message` containing the substrings "auto-detected" +
         "renamed before paste-back" so operators can grep the audit log
         to find self-heal events. This row precedes the setup flow's
         own `oauth.code_exchange` audit row for the actual Client
         construction.
      7. `click.echo` an operator-visible advisory line naming the renamed
         path + 24h recovery window (success path only).

    Audit-row disposition LOCK (per dispatch brief §3 T-A.2 AC3): emitted.
    Lock the disposition so operator-pain root-cause is traceable in
    `schwab_api_calls` history. Documented in the implementation docstring
    + Test 7 of `test_schwab_setup_self_healing.py` pins the success-path
    row shape; Test 8 pins the failure-path row shape.

    Returns:
        Path to the renamed file, or `None` if no tokens DB existed.

    Raises:
        OSError: filesystem failure during the O_EXCL claim or the
            subsequent `os.replace` — e.g. PermissionError / EACCES,
            ENOSPC, antivirus-locked tokens DB, Windows file-in-use,
            path-is-directory, or cross-device-link. In ALL OSError
            paths the audit row is closed with `status='error'` and
            the locked operator-greppable substrings ("auto-detected"
            + "renamed") before re-raise.
        RuntimeError: collision-disambiguation loop exceeded
            `_MAX_RENAME_DISAMBIG_ATTEMPTS` (pathological filesystem
            state — operator must clean up the `*.deleted-<ts>-*`
            directory). Audit row closed with `status='error'` before
            re-raise.
    """
    if not tokens_db_path.exists():
        return None

    # Step 2 — build the candidate timestamp suffix. Format matches logout
    # (`%Y%m%dT%H%M%S`); SEMANTIC anchor diverges — self-heal is UTC-aware
    # via `_utc_now()`, logout uses naïve `datetime.now()`. See docstring
    # for V2.1 §VII.F amendment-candidate disposition.
    rename_ts = _utc_now().strftime("%Y%m%dT%H%M%S")

    # Step 3 — audit-row open BEFORE ANY filesystem side effect. Codex R2
    # Major fix (2026-05-15): pre-fix the audit OPEN happened AFTER the
    # O_EXCL claim loop, so any non-collision OSError raised by `os.open`
    # (PermissionError / ENOSPC / path-is-directory / antivirus
    # interference) propagated to the caller before `record_call_start`
    # ran — reintroducing the observability gap the two-phase audit
    # ordering was meant to close. Post-fix: the audit row is opened
    # FIRST so EVERY failure mode below (claim-step OSError, replace-step
    # OSError, disambiguation exhaustion) leaves an audit trail.
    #
    # ENDPOINT NOTE: the schema CHECK enum at v18 does NOT include
    # `oauth.tokens_db_rename` (brief AC3 wording deviated from actual
    # schema). Reuse `oauth.code_exchange` — operators grep on the
    # distinctive error_message substring "auto-detected" + "renamed" to
    # find self-heal events. Banked as V2.1 §VII.F amendment candidate
    # (extend CHECK enum + use dedicated endpoint name in V2).
    audit_start_monotonic = time.monotonic()
    call_id: int | None = None
    try:
        ts = _now_ms_iso()
        call_id = audit_service.record_call_start(
            conn,
            ts=ts,
            endpoint="oauth.code_exchange",
            pipeline_run_id=None,
            surface="cli",
            environment=environment,
        )
    except Exception as exc:
        # Audit-row open failure must not block the self-heal itself —
        # surface a warning + continue with no audit trail.
        log.warning(
            "schwab setup self-heal: audit-row open failed: %s",
            type(exc).__name__,
        )
        call_id = None
        del exc  # silence linter

    def _close_audit_error(failure_exc: BaseException) -> None:
        """Close the audit row with status='error' before re-raising the
        underlying OSError. Preserves the locked grep substrings
        ('auto-detected' + 'renamed') so failed self-heal attempts share
        the same audit namespace as successful ones, and carries the
        underlying failure excerpt for root-cause visibility (Codex R2
        Major coverage extends to claim-step OSError as well as
        os.replace failures).
        """
        elapsed = int((time.monotonic() - audit_start_monotonic) * 1000)
        msg = (
            f"<auto-detected stale tokens DB at {tokens_db_path}; "
            f"renamed FAILED: {_redacted_excerpt(failure_exc)}>"
        )
        if call_id is not None:
            try:
                audit_service.record_call_finish(
                    conn,
                    call_id=call_id,
                    http_status=None,
                    status="error",
                    response_time_ms=elapsed,
                    signature_hash=None,
                    rate_limit_remaining=None,
                    error_message=msg,
                )
            except Exception as audit_exc:
                log.warning(
                    "schwab setup self-heal: audit-row close (failure) "
                    "failed: %s",
                    type(audit_exc).__name__,
                )

    # Step 4 — atomic claim-then-replace (Codex R1 Major fix, 2026-05-15;
    # restructured under audit-row ownership at Codex R2 Major fix,
    # 2026-05-15). Pre-R1 this used an `exists()`-then-`os.replace`
    # pattern that left a TOCTOU window: another process could create the
    # same `.deleted-<ts>` path between our `candidate.exists()` check
    # and `os.replace`. Since `os.replace` overwrites the destination
    # unconditionally on success, the race could silently destroy a
    # prior-process renamed file (violates "NEVER overwrite a prior
    # renamed file" guarantee).
    #
    # Post-R1: each candidate path is atomically CLAIMED via
    # `os.open(..., O_CREAT|O_EXCL|O_WRONLY)` which fails with
    # `FileExistsError` if any process — including ours from a prior
    # invocation — already created that path. On collision we
    # disambiguate to the next suffix and try the claim again. Bounded
    # by `_MAX_RENAME_DISAMBIG_ATTEMPTS`.
    #
    # Once claimed (a 0-byte sentinel file at `candidate`), `os.replace`
    # below atomically REPLACES the claimed sentinel with the stale
    # tokens DB contents. This is safe even if another process tries to
    # claim the same path concurrently — they get `FileExistsError` on
    # their O_EXCL attempt and disambiguate to a different suffix.
    #
    # Codex R2 framing: the ENTIRE claim loop + os.replace lives inside a
    # try/except OSError block. Any non-collision OSError from the claim
    # step (PermissionError on the parent dir, ENOSPC, path-is-directory,
    # antivirus race) closes the audit row with status='error' before
    # re-raise, matching the os.replace failure-path semantics.
    candidate: Path | None = None
    try:
        for counter in range(0, _MAX_RENAME_DISAMBIG_ATTEMPTS):
            if counter == 0:
                attempt = tokens_db_path.with_name(
                    f"{tokens_db_path.name}.deleted-{rename_ts}",
                )
            else:
                attempt = tokens_db_path.with_name(
                    f"{tokens_db_path.name}.deleted-{rename_ts}-{counter}",
                )
            try:
                # Atomic claim: O_CREAT|O_EXCL fails with FileExistsError
                # if path exists (race-free). Other OSError subclasses
                # (PermissionError, OSError(ENOSPC), IsADirectoryError,
                # antivirus interference) escape this inner try and are
                # caught by the OUTER except OSError below — closing the
                # audit row with status='error' before re-raise.
                # Mode 0o600 mirrors the tokens-DB at-rest posture.
                fd = os.open(
                    str(attempt),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                continue  # disambiguate to next suffix
            else:
                os.close(fd)
                candidate = attempt
                break
        if candidate is None:
            # Disambiguation exhaustion — close the audit row with
            # status='error' before raising RuntimeError so the
            # pathological-filesystem state is traceable.
            exhaustion = RuntimeError(
                f"could not claim a non-colliding rename target after "
                f"{_MAX_RENAME_DISAMBIG_ATTEMPTS} attempts; manually "
                f"clean up `{tokens_db_path.parent}/"
                f"{tokens_db_path.name}.deleted-*`",
            )
            _close_audit_error(exhaustion)
            raise exhaustion

        # Step 5 — atomic rename via os.replace. On OSError, close the
        # audit row with status='error' BEFORE re-raise (handled in
        # outer except OSError) so the failed self-heal attempt is
        # traceable in schwab_api_calls history.
        try:
            os.replace(str(tokens_db_path), str(candidate))
        except OSError:
            # Best-effort cleanup of the claimed sentinel so the failure
            # path leaves no orphan `*.deleted-*` files (matches
            # invariant pinned by Test 8). If unlink itself fails
            # (antivirus race on Windows), swallow + log so the
            # underlying OSError still surfaces with the original cause.
            try:
                os.unlink(str(candidate))
            except OSError as unlink_exc:
                log.warning(
                    "schwab setup self-heal: claimed-sentinel cleanup "
                    "failed after os.replace error: %s",
                    type(unlink_exc).__name__,
                )
            raise
    except OSError as rename_exc:
        # Covers BOTH claim-step (Codex R2 Major coverage) and
        # replace-step OSError. Audit row is already OPEN; close with
        # status='error' before re-raising.
        _close_audit_error(rename_exc)
        log.warning(
            "schwab setup self-heal: rename failed: %s",
            type(rename_exc).__name__,
        )
        raise

    # Step 6 — success-path audit close. Preserve disposition-lock substrings
    # "auto-detected" + "renamed before paste-back" (Test 7).
    elapsed_ms = int((time.monotonic() - audit_start_monotonic) * 1000)
    audit_msg = (
        f"<auto-detected stale tokens DB at {tokens_db_path}; "
        f"renamed before paste-back>"
    )
    if call_id is not None:
        try:
            audit_service.record_call_finish(
                conn,
                call_id=call_id,
                http_status=None,
                status="success",
                response_time_ms=elapsed_ms,
                signature_hash=None,
                rate_limit_remaining=None,
                error_message=audit_msg,
            )
        except Exception as exc:
            # Audit-row close failure must not block the self-heal itself
            # — the rename already happened on disk; surface a warning +
            # continue.
            log.warning(
                "schwab setup self-heal: audit-row close (success) "
                "failed: %s",
                type(exc).__name__,
            )

    # Step 7 — operator-visible advisory line. AC5: emit unconditionally
    # via `click.echo` (works regardless of whether a click.Context is
    # bound; click.echo writes to sys.stdout otherwise).
    click.echo(
        f"Auto-detected existing tokens DB at {tokens_db_path}; "
        f"renamed to {candidate} (24h recovery window) before paste-back.",
    )

    return candidate


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


def construct_authenticated_client(
    cfg: Any,
    environment: str,
    client_id: str,
    client_secret: str,
) -> Any:
    """Construct a `schwabdev.Client(...)` for an EXISTING per-env tokens DB.

    Phase 11 Sub-bundle B T-B.5 + Codex R1 M#7 fix — single-Client-instance
    discipline: the only place in the project that calls `schwabdev.Client(...)`
    inside `swing/integrations/schwab/` is HERE + the two pre-existing paths
    (`setup_paste_flow`, `force_refresh` in this same module). CLI fetch
    subcommands (`swing/cli_schwab.py:schwab_fetch`) call THIS helper rather
    than instantiating `schwabdev.Client` directly.

    The helper assumes operator has already run `swing schwab setup` AND
    the tokens DB persists at `~/swing-data/schwab-tokens.{env}.db`. schwabdev
    re-loads existing tokens at construction time + schedules background
    auto-refresh (no consent-URL prompt fires when tokens are present).

    Per Sub-bundle A D1 hotfix lesson: verifies `client.tokens.access_token`
    is populated post-construction; raises `SchwabAuthError` if not (silent-
    failure defense; schwabdev does not raise on internal token-rotation
    failure).

    Caller is expected to pre-register secrets via `register_schwab_secrets`
    + invoke `ensure_schwab_log_redaction_factory_installed` BEFORE this call
    so the Layer-2 redactor catches any auth-failure log records emitted
    during schwabdev's internal construction.

    Returns:
        Live `schwabdev.Client` instance with populated tokens.

    Raises:
        SchwabAuthError: post-construction `client.tokens.access_token` is
            empty / non-string — operator should re-run `swing schwab refresh`
            or `swing schwab setup`.
        SchwabConfigMissingError: missing credentials.
    """
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

    tokens_path = _resolve_tokens_db_path(environment)
    tokens_path.parent.mkdir(parents=True, exist_ok=True)

    register_schwab_secrets([client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()

    import schwabdev
    with _suppress_transport_debug_logs():
        client = schwabdev.Client(
            app_key=client_id,
            app_secret=client_secret,
            callback_url=cfg.integrations.schwab.callback_url,
            tokens_file=str(tokens_path),
            timeout=int(cfg.integrations.schwab.timeout_seconds),
        )

    # Silent-failure defense (D1 hotfix pattern).
    access = getattr(getattr(client, "tokens", None), "access_token", None)
    if not access or not isinstance(access, str):
        raise SchwabAuthError(
            401,
            "<schwabdev returned Client without access_token; "
            "OAuth state may be stale. Run `swing schwab refresh` or "
            "`swing schwab setup`.>",
        )
    refresh = getattr(getattr(client, "tokens", None), "refresh_token", None)
    register_schwab_secrets([access, refresh])

    return client


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

    # Step 4.bis (T-A.2) — self-heal: if a stale tokens DB exists at the
    # canonical path, atomically rename it to a `.deleted-<ts>` sibling
    # BEFORE invoking schwabdev. Solves operator-pain from 2026-05-14
    # gate (CLAUDE.md gotcha "swing schwab setup requires clean tokens
    # DB state" — schwabdev's `Client.__init__` auto-attempts a refresh
    # against any existing tokens DB and hard-fails before paste-back
    # if that refresh dies, e.g. expired refresh_token). The rename's
    # own audit row precedes the setup-flow audit row below.
    _rename_stale_tokens_db(
        tokens_path,
        environment=environment,
        conn=conn,
    )

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

    # Step 8-10 — account_linked() audit pair + picker + persist account_hash.
    # Extracted into a shared private helper at T-B.4 (Phase 12 Sub-bundle B)
    # so the new web-side `setup_paste_flow_with_callback_url` shares the
    # exact audit-row + picker + write_user_overrides logic. The shared
    # helper closes the account_linked audit row + returns the chosen
    # account_hash; the caller assembles the summary dict.
    account_hash, call_id_account_linked, num_accounts = (
        _finalize_setup_account_linked(
            client=client,
            conn=conn,
            environment=environment,
            surface="cli",
            account_picker=account_picker,
        )
    )

    return {
        "tokens_path": str(tokens_path),
        "account_hash": account_hash,
        "environment": environment,
        "call_id_setup": call_id_setup,
        "call_id_account_linked": call_id_account_linked,
        "num_accounts": num_accounts,
    }


def _finalize_setup_account_linked(
    *,
    client: Any,
    conn: sqlite3.Connection,
    environment: str,
    surface: str,
    account_picker: Any,
) -> tuple[str, int, int]:
    """Shared helper extracted at T-B.4 — runs the account_linked() audit
    pair + picker selection + persist account_hash to user-config.toml.

    Called by both ``setup_paste_flow`` AND the new
    ``setup_paste_flow_with_callback_url`` (both use surface='cli' at v18
    per CHECK constraint; V2.1 §VII.F amendment candidate widens to 'web').
    Owns its own
    audit row open + close lifecycle; raises SchwabAuthError on any
    account_linked failure or shape violation, SchwabConfigMissingError
    on multi-account without a picker.

    Returns ``(account_hash, call_id_account_linked, num_accounts)``.

    The ``surface`` parameter is the only behavioural difference between
    the two callers — CLI uses 'cli'; web routes use 'web'. The schema
    CHECK enum at v18 covers both values.
    """
    # SECOND audit-row pair around `client.account_linked()`.
    account_linked_start_ts = _now_ms_iso()
    call_id_account_linked = audit_service.record_call_start(
        conn,
        ts=account_linked_start_ts,
        endpoint="accounts.linked",
        pipeline_run_id=None,
        surface=surface,
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

    # Pick primary account.
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

    # Register the operator's chosen account_hash in the redaction registry.
    register_schwab_secrets([account_hash])

    # Persist via cfg-cascade write. USERPROFILE+HOME monkeypatch in tests;
    # production reads operator's real ~/swing-data/user-config.toml.
    from swing.config_user import load_user_overrides, write_user_overrides

    overrides = load_user_overrides()
    overrides.setdefault("integrations", {}).setdefault("schwab", {})[
        "account_hash"
    ] = account_hash
    write_user_overrides(overrides)

    return account_hash, call_id_account_linked, len(accounts)


def _exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    callback_url: str,
    callback_url_with_code: str,
    timeout_seconds: int,
) -> dict:
    """Manually exchange an OAuth authorization code for access + refresh
    tokens by POSTing to ``https://api.schwabapi.com/v1/oauth/token``.

    T-B.4 (Phase 12 Sub-bundle B) — web-mode counterpart to schwabdev's
    blocking ``Tokens.update_refresh_token`` paste-back flow. In the web
    context the operator has ALREADY pasted the callback URL into the
    form, so we cannot delegate to schwabdev (it would block on
    ``input(...)``). Instead we mirror schwabdev's internal
    ``Tokens._post_oauth_token`` + ``_update_refresh_token_from_code``
    logic: extract the ``code=`` query param from the callback URL and
    POST to /v1/oauth/token with grant_type=authorization_code.

    Mirrors the HTTP pattern at ``revoke_and_delete`` (this module) and
    ``schwabdev/tokens.py:_post_oauth_token`` (Tokens private API).

    Returns the parsed JSON token_dictionary from the OAuth response
    (contains ``access_token``, ``refresh_token``, possibly ``id_token``,
    ``token_type``, ``expires_in``, ``scope``).

    Raises:
        SchwabAuthError: HTTP non-2xx from /v1/oauth/token, or callback URL
            does not contain a parseable ``code=`` substring, or response
            body is not parseable JSON.
    """
    import base64

    import requests

    # Extract code from callback URL. schwabdev's parser:
    #   code = f"{url[url.index('code=') + 5:url.index('%40')]}@"
    # We mirror it byte-for-byte. The trailing '@' is part of Schwab's
    # auth-code format; '%40' is the URL-encoded '@' separator before the
    # session token.
    if "code=" not in callback_url_with_code:
        raise SchwabAuthError(
            400,
            "<callback URL missing 'code=' query param; "
            "ensure the entire address bar URL was pasted>",
        )
    if "%40" not in callback_url_with_code:
        raise SchwabAuthError(
            400,
            "<callback URL missing '%40' marker; the URL appears truncated "
            "or improperly formatted (expected Schwab's code=<...>%40<...> shape)>",
        )
    code_start = callback_url_with_code.index("code=") + 5
    code_end = callback_url_with_code.index("%40")
    if code_end <= code_start:
        raise SchwabAuthError(
            400,
            "<callback URL has 'code=' AFTER '%40' marker; URL malformed>",
        )
    code = f"{callback_url_with_code[code_start:code_end]}@"

    # Register the freshly-extracted code as a redaction target. The code
    # itself is short-lived (single-use, ~30s expiration per schwabdev
    # tokens.py L300) but appearing in audit error_message during a
    # failed exchange would leak its value into the audit row.
    register_schwab_secrets([code, client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()

    auth_header = base64.b64encode(
        f"{client_id}:{client_secret}".encode(),
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url,
    }
    with _suppress_transport_debug_logs():
        response = requests.post(
            "https://api.schwabapi.com/v1/oauth/token",
            headers=headers,
            data=data,
            timeout=timeout_seconds,
        )
    if not getattr(response, "ok", False):
        http_status = getattr(response, "status_code", None)
        raise SchwabAuthError(
            http_status if http_status else 502,
            f"<oauth token-exchange returned HTTP {http_status}>",
        )
    try:
        token_dict = response.json()
    except Exception as exc:
        raise SchwabAuthError(
            502,
            f"<oauth token response body unparseable: {type(exc).__name__}>",
        ) from exc
    if not isinstance(token_dict, dict):
        raise SchwabAuthError(
            502,
            f"<oauth token response JSON not an object: "
            f"{type(token_dict).__name__}>",
        )
    access = token_dict.get("access_token")
    refresh = token_dict.get("refresh_token")
    if not access or not isinstance(access, str):
        raise SchwabAuthError(
            502,
            "<oauth token response missing access_token>",
        )
    if not refresh or not isinstance(refresh, str):
        raise SchwabAuthError(
            502,
            "<oauth token response missing refresh_token>",
        )
    # Register the freshly-issued tokens as redaction targets.
    register_schwab_secrets([access, refresh])
    return token_dict


def _write_schwabdev_tokens_file(
    *,
    tokens_path: Path,
    token_dictionary: dict,
    issued_at: datetime,
) -> None:
    """Write the schwabdev-compatible tokens JSON file at ``tokens_path``.

    schwabdev's ``Tokens._set_tokens`` produces a file with three keys:
    ``access_token_issued`` + ``refresh_token_issued`` (both ISO 8601
    UTC-aware) and ``token_dictionary`` (the raw JSON dict from
    /v1/oauth/token). On subsequent ``schwabdev.Client(...)``
    construction, ``Tokens.__init__`` reads this exact format.

    T-B.4 mirrors that format byte-for-byte so the web-side OAuth
    exchange produces a tokens file indistinguishable from one that
    schwabdev wrote itself. After this call, a subsequent
    ``construct_authenticated_client(...)`` call loads the freshly-
    written tokens cleanly without prompting.

    The mode-0o600 discipline mirrors the at-rest posture of the
    self-heal rename path (auth.py:_rename_stale_tokens_db).
    """
    import json as _json

    payload = {
        "access_token_issued": issued_at.isoformat(),
        "refresh_token_issued": issued_at.isoformat(),
        "token_dictionary": token_dictionary,
    }
    # Write to a tmp sibling + os.replace for atomicity (CLAUDE.md gotcha
    # "os.replace requires same filesystem" — tmp sibling guarantees same
    # volume as final).
    tmp_path = tokens_path.with_name(tokens_path.name + ".tmp")
    fd = os.open(
        str(tmp_path),
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
        0o600,
    )
    import contextlib

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=4)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(str(tmp_path))
        raise
    os.replace(str(tmp_path), str(tokens_path))


def setup_paste_flow_with_callback_url(
    cfg: Any,
    environment: str,
    client_id: str,
    client_secret: str,
    callback_url_with_code: str,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
    account_picker: Any = None,
) -> dict:
    """OAuth setup flow that consumes a pre-pasted callback URL — T-B.4
    (Phase 12 Sub-bundle B) web-mode counterpart to ``setup_paste_flow``.

    The web route handler has ALREADY collected the operator's pasted
    callback URL via a form submission. We cannot use ``setup_paste_flow``
    here because ``schwabdev.Client(...)`` construction with a missing /
    invalid tokens file blocks on stdin (``input(...)``) via
    ``Tokens.update_refresh_token`` → ``Tokens._launch_capture_server`` or
    ``input("After authorizing, paste...")``. In a FastAPI handler that
    blocks the request thread indefinitely.

    Algorithm:
      1. Server-stamp start_ts at handler entry.
      2. Validate environment + credentials + callback_url shape.
      3. Refuse if pipeline state='running' unless force=True.
      4. Resolve per-env tokens path; mkdir parent.
      5. Self-heal stale tokens DB (T-A.2 — atomically rename existing DB
         to `.deleted-<ts>` so the freshly-written tokens file from step 7
         lands cleanly).
      6. INSERT in-flight audit row for the oauth code exchange
         (endpoint='oauth.code_exchange', surface='cli' at v18 per CHECK
         constraint — V2.1 §VII.F amendment candidate widens to 'web').
      7. POST to /v1/oauth/token with grant_type=authorization_code,
         redirect_uri = cfg callback_url, code = extracted from form.
         On HTTP success: parse JSON token_dictionary.
      8. Write schwabdev-compatible tokens JSON file at the per-env path
         (mirror schwabdev's ``Tokens._set_tokens`` format byte-for-byte).
      9. Close audit row #1 status='success'.
      10. Construct ``schwabdev.Client(...)`` — reads our just-written
          tokens file cleanly; no stdin block.
      11. Run the SHARED ``_finalize_setup_account_linked`` helper
          (account_linked() audit pair + picker + persist account_hash;
          surface='cli' at v18 — V2.1 §VII.F amendment to widen CHECK
          enum so web audit rows are distinguishable from CLI).
      12. Return summary dict.

    On exception during steps 7-10: close audit row #1 with
    status='auth_failed' + raise SchwabAuthError. Web route handler
    catches + surfaces a redacted operator-visible 4xx response.

    Args:
        cfg: Config with cfg.integrations.schwab.{callback_url,
            timeout_seconds}.
        environment: 'sandbox' or 'production'.
        client_id / client_secret: Pre-resolved via
            ``resolve_credentials_env_or_prompt(..., allow_prompt=False)``.
        callback_url_with_code: The full URL the operator pasted (must
            contain ``code=<value>%40<session>``).
        conn: SQLite connection (must NOT be inside an open transaction;
            ``record_call_start`` / ``record_call_finish`` REJECT caller-
            held tx per Phase 8 R3→R4 discipline).
        force: Bypass pipeline-active check.
        account_picker: V1 web LOCK = None (singleton-only). Multi-
            account requires CLI per dispatch brief §3 T-B.4 AC2.
            Banked V2 candidate: web multi-account picker.

    Returns:
        Summary dict with same shape as ``setup_paste_flow`` plus
        ``oauth_http_status`` carrying the /v1/oauth/token response code.

    Raises:
        SchwabConfigMissingError: invalid environment, empty credentials,
            empty callback_url, OR multi-account + None picker.
        SchwabPipelineActiveError: pipeline running + force=False.
        SchwabAuthError: any OAuth exchange / shape failure.
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
    if (
        not callback_url_with_code
        or not isinstance(callback_url_with_code, str)
        or not callback_url_with_code.strip()
    ):
        raise SchwabConfigMissingError(
            "callback_url_with_code is required (non-empty string); "
            "paste the entire address-bar URL after authorizing.",
        )

    # Step 3 — pipeline-active exclusion.
    if not force and _is_pipeline_active(conn):
        raise SchwabPipelineActiveError(
            "Pipeline run in progress; cannot run schwab setup. "
            "Use force=True to override.",
        )

    # Step 4 — resolve per-env tokens path; mkdir parent.
    tokens_path = _resolve_tokens_db_path(environment)
    tokens_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 5 — self-heal stale tokens DB (inherits T-A.2 behaviour). Same
    # advisory click.echo fires on success; in a web context the echo
    # lands on the uvicorn stdout but is harmless (operator sees the
    # rename in the audit log + the success-redirect /schwab/status).
    _rename_stale_tokens_db(
        tokens_path,
        environment=environment,
        conn=conn,
    )

    # Step 6 — INSERT in-flight audit row.
    #
    # SURFACE-ENUM DEVIATION (banked as V2.1 §VII.F amendment candidate):
    # the schema CHECK enum at v18 covers only ('pipeline', 'cli'). Web
    # setup audit rows use surface='cli' to stay within the constraint;
    # operators grep on the endpoint='oauth.code_exchange' + the
    # operator-greppable substrings in error_message (NOT surface) to
    # distinguish web from CLI events. Phase 12+ V2 will widen the enum
    # to include 'web' via a 0019 migration.
    call_id_setup = audit_service.record_call_start(
        conn,
        ts=start_ts,
        endpoint="oauth.code_exchange",
        pipeline_run_id=None,
        surface="cli",
        environment=environment,
    )

    # Pre-register cfg-known sensitive bytes before any HTTP call so
    # debug logging emitted by `requests`-side urllib3 flows through the
    # Layer-2 redactor with secrets in the registry. The code is
    # additionally registered inside `_exchange_code_for_tokens`.
    register_schwab_secrets([client_id, client_secret])
    ensure_schwab_log_redaction_factory_installed()

    # Step 7 — manual /v1/oauth/token POST.
    exchange_start = time.monotonic()
    try:
        token_dictionary = _exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            callback_url=cfg.integrations.schwab.callback_url,
            callback_url_with_code=callback_url_with_code,
            timeout_seconds=int(cfg.integrations.schwab.timeout_seconds),
        )
    except SchwabAuthError as exc:
        elapsed_ms = int((time.monotonic() - exchange_start) * 1000)
        audit_service.record_call_finish(
            conn,
            call_id=call_id_setup,
            http_status=getattr(exc, "status_code", None),
            status="auth_failed",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=_redacted_excerpt(exc),
        )
        log.warning(
            "schwab setup (web) oauth code-exchange failed: %s",
            type(exc).__name__,
        )
        raise
    except BaseException as exc:
        elapsed_ms = int((time.monotonic() - exchange_start) * 1000)
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
            "schwab setup (web) oauth code-exchange unexpected error: %s",
            type(exc).__name__,
        )
        raise SchwabAuthError(
            500,
            f"<oauth code-exchange failed: {type(exc).__name__}>",
        ) from exc

    elapsed_ms = int((time.monotonic() - exchange_start) * 1000)

    # Step 8 — write the schwabdev-compatible tokens file. issued_at is
    # `now()` (UTC-aware); matches schwabdev's `Tokens._update_refresh_
    # token_from_code` semantics ("both issued NOW on a fresh exchange").
    import datetime as _dt
    issued_at = datetime.now(_dt.UTC)
    try:
        _write_schwabdev_tokens_file(
            tokens_path=tokens_path,
            token_dictionary=token_dictionary,
            issued_at=issued_at,
        )
    except OSError as exc:
        audit_service.record_call_finish(
            conn,
            call_id=call_id_setup,
            http_status=200,  # oauth succeeded; persist failed locally
            status="error",
            response_time_ms=elapsed_ms,
            signature_hash=None,
            rate_limit_remaining=None,
            error_message=f"<tokens file write failed: {type(exc).__name__}>",
        )
        raise SchwabAuthError(
            500,
            f"<tokens file write failed at {tokens_path}: "
            f"{type(exc).__name__}>",
        ) from exc

    # Step 9 — close audit row #1 success.
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

    # Step 10 — construct schwabdev.Client. Tokens file is fresh from
    # step 8; schwabdev's Tokens.__init__ re-loads it without prompting.
    import schwabdev
    with _suppress_transport_debug_logs():
        client = schwabdev.Client(
            app_key=client_id,
            app_secret=client_secret,
            callback_url=cfg.integrations.schwab.callback_url,
            tokens_file=str(tokens_path),
            timeout=int(cfg.integrations.schwab.timeout_seconds),
        )

    # Silent-failure defense (D1 hotfix parity).
    access_token = getattr(getattr(client, "tokens", None), "access_token", None)
    if not access_token or not isinstance(access_token, str):
        raise SchwabAuthError(
            401,
            "<schwabdev returned Client without access_token after "
            "fresh token-file write; load-back may have failed>",
        )

    # Step 11 — SHARED helper for account_linked + picker + persist.
    # Per the SURFACE-ENUM DEVIATION at step 6, web surface uses 'cli'
    # to stay within the v18 CHECK enum.
    account_hash, call_id_account_linked, num_accounts = (
        _finalize_setup_account_linked(
            client=client,
            conn=conn,
            environment=environment,
            surface="cli",
            account_picker=account_picker,
        )
    )

    # Step 12 — return summary. Mirror `setup_paste_flow` shape plus
    # `oauth_http_status` to surface the exchange-step HTTP status in
    # the web view-model (operator visibility).
    return {
        "tokens_path": str(tokens_path),
        "account_hash": account_hash,
        "environment": environment,
        "call_id_setup": call_id_setup,
        "call_id_account_linked": call_id_account_linked,
        "num_accounts": num_accounts,
        "oauth_http_status": 200,
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
