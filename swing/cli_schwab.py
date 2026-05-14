"""Click CLI for Schwab API integration (Sub-bundle A T-A.4 setup +
T-A.5 refresh/logout + T-A.6 status).

V1 (T-A.4): `swing schwab setup` runs the OAuth paste-back flow against the
operator's per-env tokens DB. T-A.5 adds `refresh`, `logout` subcommands.
T-A.6 adds `status` — READ-ONLY metadata surface (no schwabdev.Client
construction, no operator prompts, no `--force` flag).

Algorithm + error handling per plan §H.1 + recon doc §4 (T-A.4 impact)
+ §6.bis (T-A.5/T-A.6 phase-2 live-library findings on tokens-file JSON
shape). Token sentinel + audit-row redaction discipline per CLAUDE.md
gotchas + plan §H.5.

Sister-module to `swing/cli_config.py` — mirrors the click.Group + per-
subcommand decorator style.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import click

from swing.config_user import _user_home
from swing.config_validation import mask_sensitive_value
from swing.data.db import connect
from swing.data.repos import schwab_api_calls as schwab_repo
from swing.integrations.schwab.auth import (
    force_refresh,
    revoke_and_delete,
    setup_paste_flow,
)
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
    SchwabRefreshTokenExpiredError,
)

# Refresh-token validity is 7 days per recon §2.11 + troubleshooting.md L64-68.
_REFRESH_TOKEN_TTL_SECONDS = 7 * 24 * 3600

# Limit on schwab_api_calls rows surfaced in `swing schwab status` output.
_RECENT_CALLS_LIMIT = 5


@click.group("schwab", help="Schwab API integration (V1 OAuth paste-back + status).")
def schwab_group() -> None:
    """Schwab API setup / status / token-management subcommands."""


def _mask_account_hash(account_hash: str) -> str:
    """Show first 3 + last 4 chars; ellipsis middle. Defense-in-depth — the
    full hash is not strictly secret (it's a stable account identifier and
    will be written to user-config.toml in plaintext) but operators don't
    need to see it in full at CLI output. Mirrors the
    `swing/config_validation.py:mask_sensitive_value` style.
    """
    if len(account_hash) <= 7:
        return account_hash
    return f"{account_hash[:3]}...{account_hash[-4:]}"


def _build_account_picker():
    """Return an account-picker callable suitable for `setup_paste_flow`.

    The callable prints a numbered list + prompts via `click.prompt` for a
    1-based index, then returns the 0-based index. Tests inject a stub that
    returns a fixed index without the prompt.
    """

    def _picker(accounts: list[dict]) -> int:
        click.echo("Multiple linked accounts detected:")
        for i, acct in enumerate(accounts, start=1):
            num = acct.get("accountNumber", "<missing>")
            hash_str = acct.get("hashValue", "<missing>")
            click.echo(
                f"  {i}) accountNumber={num}  hashValue={_mask_account_hash(hash_str)}",
            )
        while True:
            choice = click.prompt(
                f"Pick primary account (1-{len(accounts)})", type=int,
            )
            if 1 <= choice <= len(accounts):
                return choice - 1
            click.echo(f"  Invalid choice {choice}; please pick 1-{len(accounts)}.")

    return _picker


@schwab_group.command("setup")
@click.option(
    "--environment",
    "environment",
    type=click.Choice(["sandbox", "production"], case_sensitive=False),
    default=None,
    help="Tier: sandbox or production. Defaults to cfg.integrations.schwab.environment.",
)
@click.option(
    "--force",
    "force",
    is_flag=True,
    default=False,
    help="Bypass the pipeline-active concurrency exclusion (use only when sure).",
)
@click.pass_context
def schwab_setup(
    ctx: click.Context, environment: str | None, force: bool,
) -> None:
    """Run the OAuth paste-back flow + persist account_hash to user-config.toml.

    Prompts for client_id + client_secret (hidden input for secret). Invokes
    `schwabdev.Client(...)` which prints the consent URL + blocks on stdin
    for the operator to paste the redirected URL.

    On success: writes the per-env tokens DB / file under `~/swing-data/`,
    auto-picks (single account) or prompts (multi-account), persists the
    chosen `account_hash` to `user-config.toml`, prints success + advisory.

    Two audit rows are written (one for the setup OAuth call; a second for
    the `accounts.linked` call). Both are observable via `swing config show`
    + `account.snapshot` consumers.
    """
    cfg = ctx.obj["config"]
    env = environment or cfg.integrations.schwab.environment

    # D3 hotfix (operator-paired phase-2 verification 2026-05-14):
    # `connect()` raises `SchemaVersionMismatchError` when the DB version
    # doesn't match `EXPECTED_SCHEMA_VERSION`. Previously the connect()
    # happened AFTER the click.prompt calls, so an operator on a stale
    # schema (e.g. v17 when code expects v18) wasted typing credentials
    # before the migration-required error surfaced. Fail fast: open the
    # connection (which validates schema) BEFORE prompting. The same
    # reordering also surfaces `SchwabPipelineActiveError` to the operator
    # before they type credentials.
    conn = connect(cfg.paths.db_path)
    try:
        client_id = click.prompt("Schwab app client_id", type=str).strip()
        client_secret = click.prompt(
            "Schwab app client_secret", type=str, hide_input=True,
        ).strip()
        if not client_id:
            raise click.ClickException("client_id is required (non-empty).")
        if not client_secret:
            raise click.ClickException("client_secret is required (non-empty).")

        try:
            result = setup_paste_flow(
                cfg=cfg,
                environment=env,
                client_id=client_id,
                client_secret=client_secret,
                conn=conn,
                force=force,
                account_picker=_build_account_picker(),
            )
        except SchwabPipelineActiveError as exc:
            raise click.ClickException(str(exc)) from exc
        except SchwabAuthError as exc:
            raise click.ClickException(
                f"Authentication failed: {exc}",
            ) from exc
        except SchwabConfigMissingError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    masked = _mask_account_hash(result["account_hash"])
    if result["num_accounts"] == 1:
        click.echo(
            f"Auto-selected single linked account: hashValue={masked}",
        )
    else:
        click.echo(
            f"Selected account: hashValue={masked} "
            f"(from {result['num_accounts']} linked accounts).",
        )
    click.echo(
        f"Setup complete. Tokens DB written at {result['tokens_path']}.",
    )
    click.echo(
        f"To activate this env: `swing config set integrations.schwab.environment {env}`.",
    )
    click.echo(
        "Then verify with `swing schwab status`.",
    )
    click.echo(
        f"WARNING: schwab-tokens.{env}.db contains plaintext OAuth state. "
        "Do not back this file up to cloud storage / shared filesystems. "
        "To revoke: `swing schwab logout`.",
    )


@schwab_group.command("refresh")
@click.option(
    "--environment",
    "environment",
    type=click.Choice(["sandbox", "production"], case_sensitive=False),
    default=None,
    help="Tier: sandbox or production. Defaults to cfg.integrations.schwab.environment.",
)
# CONCURRENT-SAFE per Codex R1 Minor #3: refresh has NO `--force` flag.
# schwabdev's RLock + SQLite file lock on the tokens_file handle the inner
# race naturally; gating on pipeline-active would block a legitimate refresh
# during a long-running pipeline. The discriminating test
# `test_refresh_does_not_accept_force_flag` pins this contract.
@click.pass_context
def schwab_refresh(
    ctx: click.Context, environment: str | None,
) -> None:
    """Force-rotate the access_token using the existing refresh_token.

    Prompts for client_id + client_secret (the tokens DB does NOT carry
    these — schwabdev requires them at every Client construction).

    Concurrent-safe — no `--force` flag. schwabdev's RLock + SQLite file
    lock handle the inner race naturally.

    Audit row at endpoint='oauth.refresh' is observable via the standard
    `schwab_api_calls` query surface.
    """
    cfg = ctx.obj["config"]
    env = environment or cfg.integrations.schwab.environment

    # D3 pattern from T-A.4 hotfix: connect() validates schema BEFORE
    # operator credential prompt — fail fast on schema mismatch.
    conn = connect(cfg.paths.db_path)
    try:
        client_id = click.prompt("Schwab app client_id", type=str).strip()
        client_secret = click.prompt(
            "Schwab app client_secret", type=str, hide_input=True,
        ).strip()
        if not client_id:
            raise click.ClickException("client_id is required (non-empty).")
        if not client_secret:
            raise click.ClickException("client_secret is required (non-empty).")

        try:
            result = force_refresh(
                cfg=cfg,
                environment=env,
                client_id=client_id,
                client_secret=client_secret,
                conn=conn,
            )
        except SchwabRefreshTokenExpiredError as exc:
            raise click.ClickException(
                f"Refresh token has expired or been revoked. Run "
                f"`swing schwab setup --environment {env}` to re-auth.\n"
                f"Detail: {exc}",
            ) from exc
        except SchwabAuthError as exc:
            raise click.ClickException(
                f"Authentication failed during refresh: {exc}",
            ) from exc
        except SchwabApiError as exc:
            raise click.ClickException(
                f"Refresh failed (transient/network): {exc}",
            ) from exc
        except SchwabConfigMissingError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    click.echo(
        f"Refresh complete. Tokens DB at {result['tokens_path']}.",
    )


@schwab_group.command("logout")
@click.option(
    "--environment",
    "environment",
    type=click.Choice(["sandbox", "production"], case_sensitive=False),
    default=None,
    help="Tier: sandbox or production. Defaults to cfg.integrations.schwab.environment.",
)
@click.option(
    "--force",
    "force",
    is_flag=True,
    default=False,
    help="Bypass the pipeline-active concurrency exclusion (use only when sure).",
)
@click.pass_context
def schwab_logout(
    ctx: click.Context, environment: str | None, force: bool,
) -> None:
    """Revoke the refresh_token at Schwab + atomically rename the per-env
    tokens DB to `<path>.deleted-<ts>` for a 24h recovery window.

    Prompts for client_id + client_secret (needed for the
    POST /v1/oauth/revoke Basic-auth header).

    The local rename happens REGARDLESS of revoke success/failure — the
    operator's intent on `logout` is "deactivate this device's tokens
    locally" and revocation-at-Schwab is best-effort per plan §E.6.
    """
    cfg = ctx.obj["config"]
    env = environment or cfg.integrations.schwab.environment

    conn = connect(cfg.paths.db_path)
    try:
        client_id = click.prompt("Schwab app client_id", type=str).strip()
        client_secret = click.prompt(
            "Schwab app client_secret", type=str, hide_input=True,
        ).strip()
        if not client_id:
            raise click.ClickException("client_id is required (non-empty).")
        if not client_secret:
            raise click.ClickException("client_secret is required (non-empty).")

        try:
            result = revoke_and_delete(
                cfg=cfg,
                environment=env,
                client_id=client_id,
                client_secret=client_secret,
                conn=conn,
                force=force,
            )
        except SchwabPipelineActiveError as exc:
            raise click.ClickException(str(exc)) from exc
        except SchwabApiError as exc:
            raise click.ClickException(str(exc)) from exc
        except SchwabConfigMissingError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    if result["revoke_status"] == "success":
        click.echo(
            f"Logout complete. Refresh token revoked at Schwab. "
            f"Tokens DB renamed to {result['deleted_path']} "
            f"(24h recovery window).",
        )
    else:
        click.echo(
            f"Logout complete (revoke best-effort failed; "
            f"local tokens still rotated). "
            f"Tokens DB renamed to {result['deleted_path']} "
            f"(24h recovery window).",
        )


def _parse_iso_datetime(s: str) -> datetime | None:
    """Best-effort ISO 8601 parse. Returns None if unparseable.

    Tokens file uses ``datetime.now(timezone.utc).isoformat()`` style
    timestamps (with tzinfo). Use `fromisoformat` which handles
    `2026-05-14T11:28:13.234697+00:00` on Python 3.11+.
    """
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _format_duration(seconds: float) -> str:
    """Render a positive duration as `Xd Yh` / `Xh Ym` / `Xm Ys` / `Xs`.

    Used for both "valid for N remaining" and "expired N ago" — the caller
    determines positivity and prefixes accordingly.
    """
    total = int(seconds)
    if total < 0:
        total = -total
    if total >= 86400:
        days = total // 86400
        hours = (total % 86400) // 3600
        return f"{days}d {hours}h"
    if total >= 3600:
        hours = total // 3600
        minutes = (total % 3600) // 60
        return f"{hours}h {minutes}m"
    if total >= 60:
        minutes = total // 60
        secs = total % 60
        return f"{minutes}m {secs}s"
    return f"{total}s"


def _render_token_validity(
    *,
    issued_label: str,
    issued_iso: str | None,
    ttl_seconds: int,
    now: datetime,
    expired_advice: str,
) -> str:
    """Render one token-validity line.

    `issued_label` is the operator-facing prefix ("Access token" or
    "Refresh token"). `expired_advice` is the operator-actionable message
    appended when the token is past its TTL — for access_token, "run
    `swing schwab refresh`"; for refresh_token, "run `swing schwab setup`".

    Sensitive token bytes are NEVER touched here — this function consumes
    only the `*_issued` ISO timestamps and computes derived metadata.
    """
    if not issued_iso:
        return f"{issued_label}:    (no issued timestamp; tokens file may be malformed)"
    issued_dt = _parse_iso_datetime(issued_iso)
    if issued_dt is None:
        return f"{issued_label}:    (cannot parse issued timestamp)"
    # Normalize to UTC for comparison.
    if issued_dt.tzinfo is None:
        issued_dt = issued_dt.replace(tzinfo=UTC)
    expires_dt = issued_dt + timedelta(seconds=ttl_seconds)
    delta_seconds = (expires_dt - now).total_seconds()
    expires_iso = expires_dt.isoformat(timespec="seconds")
    if delta_seconds > 0:
        remaining = _format_duration(delta_seconds)
        return (
            f"{issued_label}:    issued {issued_dt.isoformat(timespec='seconds')}, "
            f"valid for {remaining} remaining (expires {expires_iso})"
        )
    expired_for = _format_duration(-delta_seconds)
    return (
        f"{issued_label}:    expired {expired_for} ago "
        f"(expired at {expires_iso}); {expired_advice}"
    )


def _read_tokens_metadata(tokens_path: Path) -> tuple[dict | None, str | None]:
    """Read + parse the tokens JSON file.

    Returns ``(payload, error_message)``. On success: ``(payload, None)``.
    On missing file: ``(None, None)`` (caller distinguishes via Path.exists).
    On parse failure: ``(None, "<error description>")``.

    SECURITY: this function returns the FULL payload including token
    bytes. The caller MUST consume only ``access_token_issued`` +
    ``refresh_token_issued`` + ``token_dictionary.expires_in`` and MUST
    NOT echo other keys (access_token / refresh_token / id_token).
    """
    try:
        with open(tokens_path) as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        return None, f"<tokens file unreadable: invalid JSON: {exc.msg}>"
    except OSError as exc:
        return None, f"<tokens file unreadable: {type(exc).__name__}>"
    if not isinstance(payload, dict):
        return None, "<tokens file unparseable: top-level not a JSON object>"
    return payload, None


def _render_recent_calls(
    conn: sqlite3.Connection,
    *,
    env: str,
    limit: int,
) -> str:
    """Render the Recent API calls section.

    Queries ``schwab_api_calls`` filtered by environment, newest-first,
    capped at `limit`. Renders as a small fixed-width table.
    """
    # Use a wide-open since_ts (epoch beginning) — we want the LIMIT to
    # constrain the result, not a time window.
    rows = schwab_repo.list_recent_calls(
        conn,
        since_ts="1970-01-01T00:00:00",
        surface_filter=None,
        environment_filter=env,
        limit=limit,
    )
    lines = [f"Recent API calls (last {limit}):"]
    if not rows:
        lines.append("  (no API calls yet)")
        return "\n".join(lines)
    for r in rows:
        http = r.http_status if r.http_status is not None else "—"
        lines.append(
            f"  call_id={r.call_id}  {r.ts}  {r.endpoint}  "
            f"{r.status}  http={http}",
        )
    return "\n".join(lines)


def render_status(
    *,
    cfg: Any,
    env: str,
    tokens_path: Path,
    now: datetime,
    conn: sqlite3.Connection,
) -> str:
    """Pure rendering helper for `swing schwab status` output.

    Sections per dispatch brief + spec §3.5:
      1. Environment header.
      2. cfg + tokens-file metadata (account_hash masked; tokens DB path
         + size if present).
      3. Token validity (access + refresh remaining or expired-ago).
      4. Recent API calls (last N, filtered by env).

    NEVER echoes access_token / refresh_token / id_token bytes.

    Caller controls connection; this function does NOT close conn.
    """
    out: list[str] = []
    header = f"Schwab integration status (environment: {env})"
    out.append(header)
    out.append("=" * len(header))
    out.append("")

    # Section 2 — cfg + tokens-file metadata.
    schwab_cfg = getattr(cfg.integrations, "schwab", None)
    account_hash = getattr(schwab_cfg, "account_hash", None) if schwab_cfg else None
    if account_hash:
        out.append(
            f"account_hash:    {mask_sensitive_value(account_hash)} (masked)",
        )
    else:
        out.append(
            "account_hash:    (not set; run `swing schwab setup`)",
        )

    if tokens_path.exists():
        try:
            size = tokens_path.stat().st_size
        except OSError:
            size = -1
        size_str = f"{size} bytes" if size >= 0 else "(unknown size)"
        out.append(f"Tokens DB:       {tokens_path} ({size_str})")
    else:
        out.append(
            f"Tokens DB:       {tokens_path} "
            "(not present; run `swing schwab setup`)",
        )
    out.append("")

    # Section 3 — token validity.
    if tokens_path.exists():
        payload, parse_err = _read_tokens_metadata(tokens_path)
        if parse_err is not None:
            out.append(f"Token validity:  {parse_err}")
            out.append(
                "                 Re-run `swing schwab setup` to recover.",
            )
        elif payload is not None:
            access_issued = payload.get("access_token_issued")
            refresh_issued = payload.get("refresh_token_issued")
            token_dict = payload.get("token_dictionary") or {}
            expires_in = token_dict.get("expires_in")
            try:
                access_ttl = int(expires_in) if expires_in is not None else 1800
            except (TypeError, ValueError):
                access_ttl = 1800
            out.append(_render_token_validity(
                issued_label="Access token",
                issued_iso=access_issued,
                ttl_seconds=access_ttl,
                now=now,
                expired_advice="run `swing schwab refresh` to rotate",
            ))
            out.append(_render_token_validity(
                issued_label="Refresh token",
                issued_iso=refresh_issued,
                ttl_seconds=_REFRESH_TOKEN_TTL_SECONDS,
                now=now,
                expired_advice="run `swing schwab setup` to re-auth",
            ))
    out.append("")

    # Section 4 — recent API calls.
    out.append(_render_recent_calls(conn, env=env, limit=_RECENT_CALLS_LIMIT))

    return "\n".join(out)


def _build_schwabdev_client_for_fetch(
    cfg: Any, environment: str, client_id: str, client_secret: str,
) -> Any:
    """Construct a fresh schwabdev.Client(...) for the fetch subcommands.

    Codex R1 M#7 fix — single-Client-instance discipline: delegates to
    `swing.integrations.schwab.auth.construct_authenticated_client` so the
    only sites instantiating `schwabdev.Client(...)` are inside
    `swing/integrations/schwab/auth.py`. The CLI surface no longer
    constructs the client directly.

    The fetch subcommands prompt for client_id + client_secret at handler
    entry (mirror setup/refresh CLI pattern). On second + subsequent
    invocations within the same operator session, schwabdev's Client(...)
    re-loads the persisted tokens DB without re-prompting.
    """
    from swing.integrations.schwab.auth import construct_authenticated_client
    return construct_authenticated_client(
        cfg=cfg,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
    )


def _check_pipeline_not_running(conn: sqlite3.Connection) -> None:
    """Per plan §H.10 — raise SchwabPipelineActiveError if pipeline is in flight.

    Used by `swing schwab fetch {--snapshot|--orders|--all}` per the protected
    surface table (5 protected + 3 safe). The 3 fetch subcommands are
    protected (NO --force override) because they write to domain tables
    that are unsafe under concurrent pipeline-internal writes.
    """
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE state = 'running' LIMIT 1",
    ).fetchone()
    if row is not None:
        raise SchwabPipelineActiveError(
            f"Pipeline run {row[0]} is currently in flight. Refusing to "
            f"run `swing schwab fetch`. Wait for pipeline to complete or "
            f"kill it.",
        )


@schwab_group.command("fetch")
@click.option(
    "--snapshot", "fetch_snapshot", is_flag=True, default=False,
    help="Run _step_schwab_snapshot (accounts.details + record_snapshot).",
)
@click.option(
    "--orders", "fetch_orders", is_flag=True, default=False,
    help="Run _step_schwab_orders (orders + transactions + details + reconcile).",
)
@click.option(
    "--all", "fetch_all", is_flag=True, default=False,
    help="Run both --snapshot and --orders sequentially.",
)
@click.option(
    "--environment",
    "environment",
    type=click.Choice(["sandbox", "production"], case_sensitive=False),
    default=None,
    help="Tier override. Defaults to cfg.integrations.schwab.environment.",
)
@click.pass_context
def schwab_fetch(
    ctx: click.Context,
    fetch_snapshot: bool,
    fetch_orders: bool,
    fetch_all: bool,
    environment: str | None,
) -> None:
    """Run a CLI-driven Schwab data fetch (snapshot, orders, or both).

    Each subcommand prompts for client_id + client_secret (mirroring setup/
    refresh CLI). On success, the pipeline-step algorithm runs verbatim
    (production env: writes account_equity_snapshots + reconciliation_runs;
    sandbox env: audit rows only). Refuses execution if a pipeline is
    in flight (plan §H.10).
    """
    # Validate one of --snapshot/--orders/--all chosen.
    chosen_count = sum([fetch_snapshot, fetch_orders, fetch_all])
    if chosen_count == 0:
        raise click.ClickException(
            "Choose one of --snapshot, --orders, or --all.",
        )
    if chosen_count > 1 and not fetch_all:
        raise click.ClickException(
            "Choose only one of --snapshot, --orders, or --all. "
            "Use --all to run both snapshot + orders.",
        )

    # Apply user-config.toml overrides best-effort (production path); fall back
    # to the raw cfg if the helper can't operate on it (test fixtures supply
    # SimpleNamespace cfgs that bypass the Config dataclass round-trip).
    try:
        from swing.config_overrides import apply_overrides
        cfg = apply_overrides(ctx.obj["config"])
    except (AttributeError, TypeError):
        cfg = ctx.obj["config"]
    env = (environment or cfg.integrations.schwab.environment).lower()

    conn = connect(cfg.paths.db_path)
    try:
        # Pipeline-active hard exclusion per plan §H.10 (NO --force override).
        try:
            _check_pipeline_not_running(conn)
        except SchwabPipelineActiveError as exc:
            raise click.ClickException(str(exc)) from exc

        # Codex R4 M#1 fix — preflight account_hash BEFORE prompting for
        # credentials. If account_hash is missing, exit with the
        # operator-actionable advisory immediately; do NOT waste operator
        # typing on a flow that can't complete. The pipeline-step layer
        # will emit a CLI-surface advisory audit row when invoked, but
        # we short-circuit BEFORE the client construction so the audit
        # row is the only side-effect of a no-account-hash CLI invocation.
        if not cfg.integrations.schwab.account_hash:
            # Emit the advisory audit row directly (mirror what
            # _step_schwab_snapshot/_step_schwab_orders would do under
            # surface='cli'); operator gets a uniform observability
            # surface across both pipeline + CLI paths.
            from swing.integrations.schwab import audit_service
            from swing.integrations.schwab.auth import _now_ms_iso
            call_id = audit_service.record_call_start(
                conn,
                ts=_now_ms_iso(),
                endpoint="accounts.details",
                pipeline_run_id=None,
                surface="cli",
                environment=env,
            )
            audit_service.record_call_finish(
                conn,
                call_id=call_id,
                http_status=None,
                response_time_ms=0,
                rate_limit_remaining=None,
                signature_hash=None,
                status="error",
                error_message=(
                    "<account_hash not configured; run `swing schwab setup` first>"
                ),
            )
            raise click.ClickException(
                f"Schwab account_hash not configured. "
                f"Run `swing schwab setup --environment {env}` first.",
            )

        # Prompt for credentials.
        client_id = click.prompt("Schwab app client_id", type=str).strip()
        client_secret = click.prompt(
            "Schwab app client_secret", type=str, hide_input=True,
        ).strip()
        if not client_id:
            raise click.ClickException("client_id is required (non-empty).")
        if not client_secret:
            raise click.ClickException("client_secret is required (non-empty).")

        # Construct schwabdev client.
        try:
            sd_client = _build_schwabdev_client_for_fetch(
                cfg, env, client_id, client_secret,
            )
        except SchwabAuthError as exc:
            raise click.ClickException(
                f"Authentication failed: {exc}",
            ) from exc
        except SchwabConfigMissingError as exc:
            raise click.ClickException(str(exc)) from exc

        # Override cfg.integrations.schwab.environment when the operator
        # passed an explicit --environment flag — the pipeline steps read
        # `cfg.integrations.schwab.environment` for the sandbox-vs-production
        # gate, so the flag MUST propagate (not just env-string string).
        if environment and env != cfg.integrations.schwab.environment:
            from dataclasses import replace as _dc_replace
            try:
                new_schwab = _dc_replace(
                    cfg.integrations.schwab, environment=env,
                )
                new_integrations = _dc_replace(
                    cfg.integrations, schwab=new_schwab,
                )
                cfg = _dc_replace(cfg, integrations=new_integrations)
            except TypeError:
                # SimpleNamespace test fixture — mutate in place.
                cfg.integrations.schwab.environment = env

        # Run requested step(s).
        from swing.integrations.schwab.pipeline_steps import (
            _step_schwab_orders,
            _step_schwab_snapshot,
        )

        results: list[dict] = []
        do_snapshot = fetch_snapshot or fetch_all
        do_orders = fetch_orders or fetch_all
        if do_snapshot:
            try:
                r = _step_schwab_snapshot(
                    conn, cfg, pipeline_run_id=None,
                    client=sd_client, surface="cli",
                )
                results.append({"step": "snapshot", **r})
            except SchwabApiError as exc:
                raise click.ClickException(
                    f"Snapshot step failed: {exc}",
                ) from exc

        if do_orders:
            try:
                r = _step_schwab_orders(
                    conn, cfg, pipeline_run_id=None,
                    client=sd_client, surface="cli",
                )
                results.append({"step": "orders", **r})
            except SchwabApiError as exc:
                raise click.ClickException(
                    f"Orders step failed: {exc}",
                ) from exc

        # Echo summary.
        click.echo(f"Schwab fetch complete (env={env}):")
        for r in results:
            step = r.get("step")
            status = r.get("status")
            extras = []
            if r.get("call_id") is not None:
                extras.append(f"call_id={r['call_id']}")
            if r.get("call_ids"):
                extras.append(f"call_ids={r['call_ids']}")
            if r.get("snapshot_id") is not None:
                extras.append(f"snapshot_id={r['snapshot_id']}")
            if r.get("reconciliation_run_id") is not None:
                extras.append(f"reconciliation_run_id={r['reconciliation_run_id']}")
            extras_str = "  ".join(extras) if extras else ""
            click.echo(f"  [{step}] {status}  {extras_str}")
    finally:
        conn.close()


@schwab_group.command("status")
@click.option(
    "--environment",
    "environment",
    type=click.Choice(["sandbox", "production"], case_sensitive=False),
    default=None,
    help=(
        "Override cfg.integrations.schwab.environment for this status call. "
        "Defaults to the cfg-active env."
    ),
)
@click.pass_context
def schwab_status(
    ctx: click.Context, environment: str | None,
) -> None:
    """Show Schwab integration status: env, account_hash, tokens DB metadata,
    token validity, recent API calls.

    READ-ONLY surface — no schwabdev.Client construction, no operator prompts,
    no `--force` flag. Plan §H.5 sentinel-leak discipline preserved: access /
    refresh / id token bytes NEVER appear in stdout — only derived metadata
    (issued timestamps + expiry deltas).
    """
    # Apply user-config.toml overrides so account_hash + environment +
    # callback_url come through; mirrors web routes + cli_config pattern.
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(ctx.obj["config"])
    env = (environment or cfg.integrations.schwab.environment).lower()

    # D3 pattern from T-A.4 hotfix: connect() validates schema BEFORE any
    # output — fail fast on schema mismatch.
    conn = connect(cfg.paths.db_path)
    try:
        tokens_path = _user_home() / "swing-data" / f"schwab-tokens.{env}.db"
        now = datetime.now(UTC)
        output = render_status(
            cfg=cfg,
            env=env,
            tokens_path=tokens_path,
            now=now,
            conn=conn,
        )
        click.echo(output)
    finally:
        conn.close()
