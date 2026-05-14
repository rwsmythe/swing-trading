"""Click CLI for Schwab API integration (Sub-bundle A T-A.4 setup +
T-A.5 refresh/logout/status — future).

V1 (T-A.4): `swing schwab setup` runs the OAuth paste-back flow against the
operator's per-env tokens DB. T-A.5 adds `refresh`, `logout`, `status`
subcommands to this same group.

Algorithm + error handling per plan §H.1 + recon doc §4 (T-A.4 impact).
Token sentinel + audit-row redaction discipline per CLAUDE.md gotchas +
plan §H.5.

Sister-module to `swing/cli_config.py` — mirrors the click.Group + per-
subcommand decorator style.
"""
from __future__ import annotations

import click

from swing.data.db import connect
from swing.integrations.schwab.auth import setup_paste_flow
from swing.integrations.schwab.client import (
    SchwabAuthError,
    SchwabConfigMissingError,
    SchwabPipelineActiveError,
)


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

    client_id = click.prompt("Schwab app client_id", type=str).strip()
    client_secret = click.prompt(
        "Schwab app client_secret", type=str, hide_input=True,
    ).strip()
    if not client_id:
        raise click.ClickException("client_id is required (non-empty).")
    if not client_secret:
        raise click.ClickException("client_secret is required (non-empty).")

    conn = connect(cfg.paths.db_path)
    try:
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
