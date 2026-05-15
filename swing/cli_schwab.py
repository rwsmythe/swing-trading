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
    resolve_credentials_env_or_prompt,
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

# T-D.1 — refresh-token severity-escalation thresholds (per dispatch brief
# §0.5 + §5.2): 24h ⇒ WARN; 2h ⇒ ERROR. Boundary semantics are inclusive at
# the upper bound (remaining <= 24*3600 ⇒ WARN; remaining <= 2*3600 ⇒ ERROR).
_REFRESH_TOKEN_WARN_THRESHOLD_SECONDS = 24 * 3600
_REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS = 2 * 3600

# T-D.1 — tokens-DB-staleness threshold for the multi-signal degraded
# predicate (per dispatch brief §3 prevention column + §5.2 T-D.1 row).
# Refresh-token TTL is 7 days, so a tokens DB whose mtime is older than
# 7 days cannot possibly hold a valid refresh token.
_TOKENS_DB_STALE_AGE_SECONDS = 7 * 24 * 3600

# T-D.1 — per-environment count windows (per spec §3.5 mock).
_RECENT_ERROR_WINDOW_24H_SECONDS = 24 * 3600
_RECENT_ERROR_WINDOW_7D_SECONDS = 7 * 24 * 3600
_RECENT_30D_WINDOW_SECONDS = 30 * 24 * 3600


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


def _resolve_credentials_for_cli(cfg: Any, environment: str) -> tuple[str, str]:
    """CLI-side credential resolver: env vars first, prompt fallback.

    Wraps `resolve_credentials_env_or_prompt` with `click.ClickException`
    translation so callers get clean CLI error rendering instead of stack
    traces. Collapses the 5× repeated try/except blocks that every CLI
    subcommand needing credentials previously open-coded (T-A.1 code-review
    cleanup).
    """
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=True,
        )
    except SchwabConfigMissingError as exc:
        raise click.ClickException(str(exc)) from exc
    if client_id is None or client_secret is None:
        # `resolve_credentials_env_or_prompt` only returns (None, None) when
        # `allow_prompt=False`; CLI path passes `allow_prompt=True` so this
        # is defensive only.
        raise click.ClickException("Failed to resolve Schwab credentials.")
    return client_id, client_secret


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
    # Codex R1 Critical #1 fix — apply_overrides() at CLI entry point so
    # the cfg-cascade (user-config.toml) tier of
    # `integrations.schwab.{client_id,client_secret}` is actually consumed.
    # Mirrors swing/cli_schwab.py:982-985, 1266-1269, 1430-1431.
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(ctx.obj["config"])
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
        # T-A.1 — env-var supersession: `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`
        # env vars set together → skip prompt; partial set → SchwabConfigMissingError.
        client_id, client_secret = _resolve_credentials_for_cli(cfg, env)

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
    # Codex R1 Major #3 — `swing config set integrations.schwab.environment`
    # is NOT a working V1 surface (FIELD_REGISTRY does not include the env
    # field). Operator activation path is hand-edit OR `--environment` flag
    # per-invocation (T-D.2 cycle-checklist guidance).
    click.echo(
        "To activate this environment for pipeline + CLI defaults: "
        "hand-edit `%USERPROFILE%/swing-data/user-config.toml` and set "
        f"`integrations.schwab.environment = \"{env}\"`. "
        f"Or pass `--environment {env}` per-invocation to override.",
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
    # Codex R1 Critical #1 fix — apply_overrides() at CLI entry point.
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(ctx.obj["config"])
    env = environment or cfg.integrations.schwab.environment

    # D3 pattern from T-A.4 hotfix: connect() validates schema BEFORE
    # operator credential prompt — fail fast on schema mismatch.
    conn = connect(cfg.paths.db_path)
    try:
        # T-A.1 — env-var supersession (see schwab_setup for full notes).
        client_id, client_secret = _resolve_credentials_for_cli(cfg, env)

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
    # Codex R1 Critical #1 fix — apply_overrides() at CLI entry point.
    from swing.config_overrides import apply_overrides
    cfg = apply_overrides(ctx.obj["config"])
    env = environment or cfg.integrations.schwab.environment

    conn = connect(cfg.paths.db_path)
    try:
        # T-A.1 — env-var supersession (see schwab_setup for full notes).
        client_id, client_secret = _resolve_credentials_for_cli(cfg, env)

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


def _count_recent_errors(
    conn: sqlite3.Connection,
    *,
    env: str,
    now: datetime,
    window_seconds: int,
) -> int:
    """Count `schwab_api_calls` rows in [now - window, now] with status != 'success'.

    Mirrors `count_calls_by_status` but: (a) filters by environment, (b)
    counts the COMPLEMENT of 'success' so all error variants
    (`error`, `auth_failed`, `rate_limited`, `concurrent_refresh`,
    `in_flight`) roll up under "recent errors". Per dispatch brief §0.5 #2:
    the predicate is the COMPLEMENT of success, not equality with 'error'.
    """
    since_ts = (now - timedelta(seconds=window_seconds)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls "
        "WHERE environment = ? AND status != 'success' AND ts >= ?",
        (env, since_ts),
    ).fetchone()
    return int(row[0])


def _count_snapshots_30d(
    conn: sqlite3.Connection,
    *,
    now: datetime,
) -> int:
    """Count `account_equity_snapshots` rows with snapshot_date in last 30 days.

    Snapshots have NO environment column V1 (the per-env qualifier is
    provided by the active env header in the rendered output).
    """
    since_date = (now - timedelta(seconds=_RECENT_30D_WINDOW_SECONDS)).date().isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots "
        "WHERE source = 'schwab_api' AND snapshot_date >= ?",
        (since_date,),
    ).fetchone()
    return int(row[0])


def _count_recon_runs_30d(
    conn: sqlite3.Connection,
    *,
    now: datetime,
) -> int:
    """Count `reconciliation_runs` with source='schwab_api' in last 30 days."""
    since_ts = (now - timedelta(seconds=_RECENT_30D_WINDOW_SECONDS)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs "
        "WHERE source = 'schwab_api' AND started_ts >= ?",
        (since_ts,),
    ).fetchone()
    return int(row[0])


def _count_unresolved_material_discrepancies(
    conn: sqlite3.Connection,
) -> int:
    """Count `reconciliation_discrepancies` with material=1 AND resolution='unresolved'.

    NOT joined to trades — counts ALL unresolved material discrepancies
    regardless of attribution (active vs closed vs orphan-emit). The Phase
    10 banner queries `list_unresolved_material_for_active_trades` (joined
    to trades for the dashboard banner); status surface gives the broader
    operator-visible count.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE material_to_review = 1 AND resolution = 'unresolved'",
    ).fetchone()
    return int(row[0])


def _compute_degraded_state(
    conn: sqlite3.Connection,
    *,
    env: str,
    tokens_path: Path,
    now: datetime,
) -> tuple[str, str | None]:
    """Multi-signal integration-state predicate per dispatch brief §5.2 T-D.1
    + Codex R1 Major #1+#2 + R2 Major #1+#2 hardening (extends to consult
    token_dictionary presence + refresh_token bytes presence AND narrows
    PROVISIONAL to ONLY tokens-DB-missing-on-disk).

    Returns ``(state, reason_text)`` where ``state`` is one of:
      - "LIVE" — all signals OK; integration is configured + healthy.
      - "PROVISIONAL" — never configured yet (tokens DB missing on disk
        ONLY per R2 M#2 narrowing). Operator runs `swing schwab setup` to
        advance; this is NOT a failure state.
      - "DEGRADED" — configured but failing. Operator runs `swing schwab
        status` for diagnostic detail + likely `swing schwab logout` +
        `swing schwab setup` to recover.

    ``reason_text`` is ``None`` only when state == "LIVE"; otherwise carries
    a short operator-facing phrase suitable for inline display next to the
    state label.

    Signal order (matches dispatch brief §5.2 + Codex R1 + R2 directives):
      1. tokens DB missing on disk            → PROVISIONAL
      2. tokens DB unparseable / corrupt JSON → DEGRADED
      3. `token_dictionary` missing or non-dict
                                              → DEGRADED   (R2 M#1)
      4. `token_dictionary.refresh_token` bytes missing or empty
                                              → DEGRADED   (R2 M#1)
      5. `refresh_token_issued` field missing → DEGRADED   (R2 M#2)
      6. `refresh_token_issued` unparseable   → DEGRADED   (R2 M#2)
      7. `refresh_token_issued` already expired (issued + 7d <= now)
                                              → DEGRADED   (R2 m#1: <=)
      8. tokens DB mtime > 7 days old         → DEGRADED
      9. most-recent `schwab_api_calls` for env has status != 'success'
                                              → DEGRADED

    R2 narrows PROVISIONAL to Signal 1 only: a tokens DB that exists on
    disk implies the operator has previously completed `swing schwab
    setup`, so any anomaly inside it is configured-but-malformed →
    DEGRADED (cleanest semantic for operator triage). R2 M#1 closes the
    bypass where a tokens DB with valid `refresh_token_issued` metadata
    but missing actual refresh_token bytes would have fallen through to
    LIVE; presence + non-emptiness is now an explicit signal (SECURITY:
    only presence is checked; the token VALUE is never read into a return
    string).
    """
    # Signal 1: tokens DB missing → PROVISIONAL (not configured yet).
    if not tokens_path.exists():
        return "PROVISIONAL", "tokens DB missing — not configured yet"

    # Signals 2-7 consult tokens-file metadata.
    payload, parse_err = _read_tokens_metadata(tokens_path)
    # Signal 2: parse_err set → DEGRADED (corrupt JSON or OS error).
    if parse_err is not None:
        return "DEGRADED", f"tokens DB unparseable: {parse_err}"

    if payload is not None:
        # Signal 3 (R2 M#1): token_dictionary missing or non-dict → DEGRADED.
        token_dict = payload.get("token_dictionary")
        if not isinstance(token_dict, dict):
            return (
                "DEGRADED",
                "token_dictionary missing or non-dict — "
                "run `swing schwab logout` then `swing schwab setup`",
            )
        # Signal 4 (R2 M#1): refresh_token bytes missing or empty → DEGRADED.
        # SECURITY: ONLY presence/non-emptiness is checked; the token
        # VALUE is never echoed into the return string (sentinel-leak
        # tests assert this).
        refresh_token_bytes = token_dict.get("refresh_token")
        if (
            not isinstance(refresh_token_bytes, str)
            or not refresh_token_bytes.strip()
        ):
            return (
                "DEGRADED",
                "token_dictionary missing refresh_token bytes — "
                "run `swing schwab logout` then `swing schwab setup`",
            )

        refresh_issued_iso = payload.get("refresh_token_issued")
        # Signal 5 (R2 M#2): refresh_token_issued field missing → DEGRADED.
        if not refresh_issued_iso:
            return (
                "DEGRADED",
                "tokens DB missing refresh_token_issued field — "
                "run `swing schwab logout` then `swing schwab setup`",
            )
        # Signal 6 (R2 M#2): refresh_token_issued unparseable → DEGRADED.
        issued_dt = _parse_iso_datetime(refresh_issued_iso)
        if issued_dt is None:
            return (
                "DEGRADED",
                "tokens DB has unparseable refresh_token_issued — "
                "run `swing schwab logout` then `swing schwab setup`",
            )
        if issued_dt.tzinfo is None:
            issued_dt = issued_dt.replace(tzinfo=UTC)
        expires_dt = issued_dt + timedelta(
            seconds=_REFRESH_TOKEN_TTL_SECONDS,
        )
        # Signal 7 (R2 m#1): boundary semantics align with renderer's
        # `delta_seconds <= 0` — at exactly now == expires_dt, predicate
        # AND renderer both report expired.
        if expires_dt <= now:
            return (
                "DEGRADED",
                "refresh_token expired (run `swing schwab setup` to re-auth)",
            )

    # Signal 8: tokens DB stale (mtime > 7 days).
    try:
        mtime = tokens_path.stat().st_mtime
        age_seconds = now.timestamp() - mtime
        if age_seconds > _TOKENS_DB_STALE_AGE_SECONDS:
            days_old = int(age_seconds // 86400)
            return (
                "DEGRADED",
                f"tokens DB age {days_old} days old (>7 days; refresh-token "
                "TTL exceeded by file mtime)",
            )
    except OSError:
        # Defensive — if we can't stat, treat as degraded (filesystem issue).
        return "DEGRADED", "tokens DB stat failed (filesystem issue)"

    # Signal 9: most-recent call for this env has status != 'success'.
    # Pull only the single most-recent row to avoid scanning history.
    row = conn.execute(
        "SELECT status FROM schwab_api_calls WHERE environment = ? "
        "ORDER BY ts DESC, call_id DESC LIMIT 1",
        (env,),
    ).fetchone()
    if row is not None and row[0] != "success":
        return "DEGRADED", f"most-recent call status='{row[0]}'"

    return "LIVE", None


def _render_refresh_token_with_severity(
    *,
    issued_iso: str | None,
    now: datetime,
) -> str:
    """Render the refresh_token validity line with severity escalation.

    Per dispatch brief §0.5 + spec §3.5:
      - remaining <= 2hr ⇒ ERROR + bold red ASCII marker `[!! ERROR !!]`.
      - 2hr < remaining <= 24hr ⇒ WARN (`[WARN]` prefix).
      - remaining > 24hr ⇒ neither marker.

    Boundary semantics: <= is INCLUSIVE at the upper bound (per acceptance
    criteria: at exactly 24hr → WARN; at exactly 2hr → ERROR). ERROR
    SUPPRESSES WARN (escalates rather than stacking).

    NEVER touches sensitive token bytes — only the `*_issued` ISO timestamp.
    """
    base = _render_token_validity(
        issued_label="Refresh token",
        issued_iso=issued_iso,
        ttl_seconds=_REFRESH_TOKEN_TTL_SECONDS,
        now=now,
        expired_advice="run `swing schwab setup` to re-auth",
    )
    if not issued_iso:
        return base
    issued_dt = _parse_iso_datetime(issued_iso)
    if issued_dt is None:
        return base
    if issued_dt.tzinfo is None:
        issued_dt = issued_dt.replace(tzinfo=UTC)
    expires_dt = issued_dt + timedelta(seconds=_REFRESH_TOKEN_TTL_SECONDS)
    delta_seconds = (expires_dt - now).total_seconds()
    # Already-expired path is handled by the base "_render_token_validity"
    # output ("expired N ago"); no severity prefix needed (the "expired"
    # text is itself the loudest signal and operator advice already cited).
    if delta_seconds <= 0:
        return base
    if delta_seconds <= _REFRESH_TOKEN_ERROR_THRESHOLD_SECONDS:
        return f"[!! ERROR !!] {base}"
    if delta_seconds <= _REFRESH_TOKEN_WARN_THRESHOLD_SECONDS:
        return f"[WARN] {base}"
    return base


def render_status(
    *,
    cfg: Any,
    env: str,
    tokens_path: Path,
    now: datetime,
    conn: sqlite3.Connection,
) -> str:
    """Pure rendering helper for `swing schwab status` output.

    Sections per dispatch brief §0.9 T-D.1 + spec §3.5 mock:
      0. Environment header.
      1. LIVE / PROVISIONAL / DEGRADED indicator (multi-signal predicate
         per §5.2 T-D.1 + Codex R1 M#1+M#2 + R2 M#1+M#2 hardening).
      2. cfg + tokens-file metadata (account_hash masked; tokens DB path).
      3. Token validity (access + refresh, with severity escalation on refresh).
      4. Per-environment counts: recent errors (24h, 7d) + snapshots-30d
         + reconciliation_runs(schwab_api)-30d + unresolved-material-
         discrepancies count.
      5. Recent API calls (last N, filtered by env).

    NEVER echoes access_token / refresh_token / id_token bytes.

    Caller controls connection; this function does NOT close conn.
    """
    out: list[str] = []
    header = f"Schwab integration status (environment: {env})"
    out.append(header)
    out.append("=" * len(header))
    out.append("")

    # Section 1 — LIVE/PROVISIONAL/DEGRADED indicator (T-D.1 + Codex R1
    # Major #1+#2; multi-signal predicate with 3-state distinction).
    state, reason = _compute_degraded_state(
        conn, env=env, tokens_path=tokens_path, now=now,
    )
    if state == "LIVE":
        out.append(f"Schwab integration: LIVE ({env})")
    elif state == "PROVISIONAL":
        out.append(f"Schwab integration: PROVISIONAL ({env}) — {reason}")
    else:  # DEGRADED
        out.append(f"Schwab integration: DEGRADED ({env}) — {reason}")
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
            # Refresh token gets severity escalation (T-D.1).
            out.append(_render_refresh_token_with_severity(
                issued_iso=refresh_issued,
                now=now,
            ))
    out.append("")

    # Section 4 — per-environment counts (T-D.1; spec §3.5 mock).
    err_24h = _count_recent_errors(
        conn, env=env, now=now,
        window_seconds=_RECENT_ERROR_WINDOW_24H_SECONDS,
    )
    err_7d = _count_recent_errors(
        conn, env=env, now=now,
        window_seconds=_RECENT_ERROR_WINDOW_7D_SECONDS,
    )
    out.append(
        f"recent errors:    {err_24h} in last 24h, {err_7d} in last 7d "
        "(see `swing schwab fetch --verbose`)",
    )
    n_snap_30d = _count_snapshots_30d(conn, now=now)
    out.append(f"snapshots written: {n_snap_30d} in last 30 days")
    n_recon_30d = _count_recon_runs_30d(conn, now=now)
    n_unresolved = _count_unresolved_material_discrepancies(conn)
    out.append(
        f"reconciliation_runs (schwab_api): {n_recon_30d} in last 30 days; "
        f"{n_unresolved} unresolved material discrepancies",
    )
    out.append("")

    # Section 5 — recent API calls.
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


def _verify_marketdata_path(
    *,
    ctx: click.Context,
    symbols: list[str],
    environment: str | None,
) -> None:
    """T-C.5 `--verify-marketdata` execution path.

    Per dispatch brief §3 surface S3 disposition (b): verification-only
    subcommand exercising the schwabdev market-data API endpoints
    (`/quotes` + `/price_history`). Audit rows ARE written; cache writes
    are SKIPPED regardless of env (no ladder fetcher installed; CLI
    directly invokes the T-C.1 wrappers).

    Per plan §H.10: `--verify-marketdata` is in the 3-SAFE-subcommands
    list; NO pipeline-active exclusion check fires.

    Reuses ``construct_authenticated_client`` per pre-emption #5 — does
    NOT instantiate `schwabdev.Client(...)` directly.

    Exit codes:
      - 0 on success (incl. partial-response: at least one symbol mapped).
      - Non-zero on auth failure (401), rate-limit (429), shape error,
        or total failure (all symbols failed at quotes layer).
    """
    # Apply user-config.toml overrides best-effort (production path).
    try:
        from swing.config_overrides import apply_overrides
        cfg = apply_overrides(ctx.obj["config"])
    except (AttributeError, TypeError):
        cfg = ctx.obj["config"]
    env = (environment or cfg.integrations.schwab.environment).lower()

    conn = connect(cfg.paths.db_path)
    try:
        # Pipeline-active check intentionally SKIPPED per plan §H.10 + brief
        # pre-emption #2 — verify-marketdata is in the 3-safe-subcommands list.

        # T-A.1 — env-var supersession (see schwab_setup for full notes).
        client_id, client_secret = _resolve_credentials_for_cli(cfg, env)

        # Apply --environment override to cfg so downstream env-aware
        # consumers see the right value (mirrors schwab_fetch).
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
                cfg.integrations.schwab.environment = env

        # Construct client via the single-Client-instance discipline helper.
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

        # Invoke T-C.1 wrappers DIRECTLY — NOT via the ladder.
        # Per pre-emption #3: no cache fill, no ladder fetcher installed.
        from swing.integrations.schwab import marketdata as schwab_md
        from swing.integrations.schwab.client import (
            SchwabRateLimitError,
            SchwabSchemaParityError,
        )

        click.echo(f"Schwab market-data verification (env={env}):")

        # /quotes call.
        quotes_failed_total = False
        try:
            quotes_result = schwab_md.get_quotes_batch(
                sd_client,
                conn,
                symbols,
                surface="cli",
                environment=env,
                pipeline_run_id=None,
            )
        except SchwabAuthError as exc:
            raise click.ClickException(
                f"quotes: authentication failed (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc
        except SchwabRateLimitError as exc:
            raise click.ClickException(
                f"quotes: rate limited (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc
        except SchwabSchemaParityError as exc:
            raise click.ClickException(
                f"quotes: response shape error: {exc}",
            ) from exc
        except SchwabApiError as exc:
            raise click.ClickException(
                f"quotes: API error (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc

        # Build operator-visible summary for quotes.
        ok_syms = set(quotes_result.keys())
        failed = [s for s in symbols if s not in ok_syms]
        n_ok = len(ok_syms)
        n_total = len(symbols)
        if n_ok == n_total:
            click.echo(
                f"  [quotes] success  {n_ok}/{n_total} OK  "
                f"symbols={','.join(symbols)}"
            )
        else:
            failed_excerpt = ",".join(failed[:5])
            if len(failed) > 5:
                failed_excerpt += f",+{len(failed) - 5} more"
            click.echo(
                f"  [quotes] partial  {n_ok}/{n_total} OK; "
                f"failed: {failed_excerpt}"
            )
            if n_ok == 0:
                quotes_failed_total = True

        # /price_history call — use first symbol (default AAPL when omitted).
        # Schwab's price_history accepts ONE symbol per call (per T-C.1
        # docstring; api-calls.md L432). Verification scope is the endpoint
        # surface; running it on the first symbol suffices.
        primary_symbol = symbols[0]
        try:
            ph_window = schwab_md.get_price_history(
                sd_client,
                conn,
                primary_symbol,
                period_type="month",
                period=1,
                frequency_type="daily",
                frequency=1,
                surface="cli",
                environment=env,
                pipeline_run_id=None,
            )
        except SchwabAuthError as exc:
            raise click.ClickException(
                f"price_history: authentication failed (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc
        except SchwabRateLimitError as exc:
            raise click.ClickException(
                f"price_history: rate limited (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc
        except SchwabSchemaParityError as exc:
            raise click.ClickException(
                f"price_history: response shape error: {exc}",
            ) from exc
        except SchwabApiError as exc:
            # Includes empty-bars transient (status_code=204).
            raise click.ClickException(
                f"price_history: API error (HTTP "
                f"{getattr(exc, 'status_code', '?')}): {exc}",
            ) from exc

        n_bars = len(ph_window.bars)
        click.echo(
            f"  [price_history] success  symbol={primary_symbol}  "
            f"bars={n_bars}  provider={ph_window.provider}"
        )

        # Exit code disposition per pre-emption #7:
        # - All OK → exit 0.
        # - Partial (quotes_failed_total is False, n_ok>0) → exit 0 with
        #   stdout note already emitted above.
        # - Total quotes failure (n_ok==0) → non-zero.
        if quotes_failed_total:
            raise click.ClickException(
                f"quotes: ALL {n_total} symbols failed; see audit row for details.",
            )
    finally:
        conn.close()


def _parse_symbols_csv(raw: str | None, *, default: list[str]) -> list[str]:
    """Parse `--symbols` CSV string per pre-emption #4.

    Rules:
      - None / empty string → ``default``.
      - Comma-separated; per-element whitespace stripped.
      - Empty tokens (e.g. trailing comma or `","`) dropped.
      - Final list must be non-empty; otherwise raise ``click.ClickException``.

    Operator typo defense — `swing schwab fetch --verify-marketdata --symbols ","`
    rejected at parse time BEFORE any schwabdev call.
    """
    if raw is None or not raw.strip():
        return list(default)
    parts = [tok.strip() for tok in raw.split(",")]
    cleaned = [p for p in parts if p]
    if not cleaned:
        raise click.ClickException(
            "--symbols parsed to empty list; supply at least one ticker "
            "(e.g. --symbols AAPL or --symbols AAPL,AMD).",
        )
    return cleaned


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
    "--verify-marketdata", "verify_marketdata", is_flag=True, default=False,
    help=(
        "Verification-only: issue /quotes + /price_history calls against "
        "active env; audit rows written; cache writes SKIPPED. Does NOT "
        "enforce pipeline-active exclusion (T-C.5)."
    ),
)
@click.option(
    "--symbols", "symbols_csv", default=None,
    help=(
        "Comma-separated ticker list for --verify-marketdata (e.g. "
        "'AAPL,AMD'). Default: AAPL. Ignored for other fetch modes."
    ),
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
    verify_marketdata: bool,
    symbols_csv: str | None,
    environment: str | None,
) -> None:
    """Run a CLI-driven Schwab data fetch (snapshot, orders, both, or
    market-data verification).

    Each subcommand prompts for client_id + client_secret (mirroring setup/
    refresh CLI). On success, the pipeline-step algorithm runs verbatim
    (production env: writes account_equity_snapshots + reconciliation_runs;
    sandbox env: audit rows only). Refuses execution if a pipeline is
    in flight (plan §H.10).

    `--verify-marketdata` is a SAFE subcommand (T-C.5; plan §H.10): does
    NOT enforce the pipeline-active exclusion + does NOT write to caches
    or the OHLCV archive regardless of env. Audit rows ARE written for
    each /quotes + /price_history call.
    """
    # Dispatch to --verify-marketdata path BEFORE the snapshot/orders/all
    # validation: --verify-marketdata is mutually exclusive with the 3
    # domain-write flags. The verification path has its own simpler
    # codepath (no pipeline-active check, no account_hash preflight, no
    # domain writes).
    if verify_marketdata:
        if fetch_snapshot or fetch_orders or fetch_all:
            raise click.ClickException(
                "--verify-marketdata is mutually exclusive with "
                "--snapshot / --orders / --all.",
            )
        symbols = _parse_symbols_csv(symbols_csv, default=["AAPL"])
        _verify_marketdata_path(
            ctx=ctx,
            symbols=symbols,
            environment=environment,
        )
        return

    if symbols_csv is not None:
        raise click.ClickException(
            "--symbols is only valid with --verify-marketdata.",
        )

    # Validate one of --snapshot/--orders/--all chosen.
    chosen_count = sum([fetch_snapshot, fetch_orders, fetch_all])
    if chosen_count == 0:
        raise click.ClickException(
            "Choose one of --snapshot, --orders, --all, or --verify-marketdata.",
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

        # T-A.1 — env-var supersession (see schwab_setup for full notes).
        client_id, client_secret = _resolve_credentials_for_cli(cfg, env)

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
