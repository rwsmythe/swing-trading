"""swing config show/set/reset — CLI parity with /config web page.

Shares the validation registry from swing.config_validation; same
hard/soft semantics.
"""
from __future__ import annotations

import click

from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import (
    delete_user_override,
    load_user_overrides,
    write_user_overrides,
)
from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_field,
)

_FIELD_PATHS = tuple(s.path for s in FIELD_REGISTRY)


@click.group("config")
def config_group() -> None:
    """View / edit operator-tunable settings (user-config.toml)."""


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Print all V1 fields with current value, default, source."""
    base_cfg = ctx.obj["config"]
    eff = apply_overrides(base_cfg)
    click.echo(f"{'Field':<32} {'Current':<12} {'Default':<12} Source")
    click.echo("-" * 72)
    for spec in FIELD_REGISTRY:
        section, key = spec.path.split(".")
        current = getattr(getattr(eff, section), key)
        source = get_field_source(base_cfg, spec.path)
        click.echo(
            f"{spec.label + ' (' + spec.path + ')':<32} "
            f"{current!s:<12} {spec.default!s:<12} {source}"
        )


@config_group.command("set")
@click.argument("field_path", type=click.Choice(_FIELD_PATHS))
@click.argument("raw_value", type=str)
@click.option("--force", is_flag=True, help="Bypass soft-warn confirmation prompts")
@click.pass_context
def config_set(ctx: click.Context, field_path: str, raw_value: str, force: bool) -> None:
    """Set a field. Hard-refuse exits non-zero. Soft-warn prompts y/n unless --force."""
    result = validate_field(field_path, raw_value)
    if result.hard_errors:
        for err in result.hard_errors:
            click.echo(f"ERROR: {err.message}", err=True)
        ctx.exit(1)
    if result.soft_warnings and not force:
        click.echo("Confirm: values exceed the typical range.")
        for w in result.soft_warnings:
            click.echo(f"  - {w.message}")
        if not click.confirm("Proceed?", default=False):
            click.echo("Aborted.")
            ctx.exit(2)
    coerced = coerce_value(field_path, raw_value)
    overrides = load_user_overrides()
    section, key = field_path.split(".")
    overrides.setdefault(section, {})[key] = coerced
    write_user_overrides(overrides)
    click.echo(f"Set {field_path} = {coerced}")


@config_group.command("reset")
@click.argument("field_path", type=click.Choice(_FIELD_PATHS))
@click.pass_context
def config_reset(ctx: click.Context, field_path: str) -> None:
    """Remove a field from user-config.toml (subsequent reads fall through)."""
    delete_user_override(field_path)
    click.echo(f"Reset {field_path} (now reads from default/tracked).")
