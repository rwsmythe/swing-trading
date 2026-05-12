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


# Phase 9 T-A.5 / Codex R1 Major #4 fix: when `swing config set` writes a
# field that has a risk_policy mirror counterpart (per spec §3.1.3), the
# CLI MUST also supersede the active risk_policy with the new value.
# Otherwise the legacy CLI surface bypasses the cfg-cascade that the web
# config page wires (T-A.5), creating a divergence the operator cannot
# easily detect. Map mirrors `swing/web/routes/config.py:_RISK_POLICY_CASCADE_MAP`.
_CONFIG_SET_RISK_POLICY_CASCADE_MAP: dict[str, str] = {
    "account.risk_equity_floor": "capital_floor_constant_dollars",
}


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

    # Phase 9 cfg-cascade: when this CLI writes a field with a risk_policy
    # mirror, supersede the active policy too (Codex R1 Major #4 fix).
    # Mirrors the web config_save cascade in swing/web/routes/config.py.
    # Cascade fires AFTER the override write so a cascade failure leaves
    # the cfg-side change committed; the next-startup divergence advisory
    # surfaces the gap.
    if field_path in _CONFIG_SET_RISK_POLICY_CASCADE_MAP:
        from swing.data.db import connect
        from swing.trades.risk_policy import supersede_active_policy

        cfg = ctx.obj["config"]
        policy_field = _CONFIG_SET_RISK_POLICY_CASCADE_MAP[field_path]
        try:
            cascade_conn = connect(cfg.paths.db_path)
        except Exception as exc:
            click.echo(
                f"WARNING: could not open DB for risk_policy cascade ({exc}); "
                f"override written but risk_policy NOT updated. Run "
                f"`swing config policy import-from-toml --field {policy_field}` "
                f"to reconcile.",
                err=True,
            )
            return
        try:
            new_id = supersede_active_policy(
                cascade_conn,
                field_updates={policy_field: coerced},
                source="cfg_cascade",
            )
            click.echo(
                f"Cascaded to risk_policy: new policy_id={new_id} with "
                f"{policy_field}={coerced}"
            )
        except Exception as exc:
            click.echo(
                f"WARNING: risk_policy cascade failed ({exc}); override "
                f"written but risk_policy NOT updated. Run "
                f"`swing config policy import-from-toml --field {policy_field}` "
                f"to reconcile.",
                err=True,
            )
        finally:
            cascade_conn.close()


@config_group.command("reset")
@click.argument("field_path", type=click.Choice(_FIELD_PATHS))
@click.pass_context
def config_reset(ctx: click.Context, field_path: str) -> None:
    """Remove a field from user-config.toml (subsequent reads fall through)."""
    delete_user_override(field_path)
    click.echo(f"Reset {field_path} (now reads from default/tracked).")

    # Phase 9 Codex R2 Major #1 fix: when the reset field has a risk_policy
    # mirror, cascade the post-reset effective value to the active policy.
    # Otherwise reset recreates the very divergence the cfg-cascade closed.
    if field_path in _CONFIG_SET_RISK_POLICY_CASCADE_MAP:
        from swing.config import load as load_cfg_raw
        from swing.config_overrides import apply_overrides
        from swing.data.db import connect
        from swing.trades.risk_policy import supersede_active_policy

        # Re-load + apply remaining overrides to get the post-reset value
        # (the override we just deleted is gone; the rest still apply).
        post_reset_cfg = apply_overrides(load_cfg_raw(ctx.obj["config_path"]))
        section, attr = field_path.split(".")
        post_reset_value = getattr(getattr(post_reset_cfg, section), attr)
        policy_field = _CONFIG_SET_RISK_POLICY_CASCADE_MAP[field_path]
        try:
            cascade_conn = connect(post_reset_cfg.paths.db_path)
        except Exception as exc:
            click.echo(
                f"WARNING: could not open DB for risk_policy reset cascade "
                f"({exc}); user-config override deleted but risk_policy NOT "
                f"updated. Run `swing config policy import-from-toml --field "
                f"{policy_field}` to reconcile.",
                err=True,
            )
            return
        try:
            new_id = supersede_active_policy(
                cascade_conn,
                field_updates={policy_field: post_reset_value},
                source="cfg_cascade",
                notes=(
                    f"reset {field_path} to {post_reset_value} via "
                    f"`swing config reset`"
                ),
            )
            click.echo(
                f"Cascaded reset to risk_policy: new policy_id={new_id} "
                f"with {policy_field}={post_reset_value}"
            )
        except Exception as exc:
            click.echo(
                f"WARNING: risk_policy reset cascade failed ({exc}); "
                f"override deleted but risk_policy NOT updated. Run "
                f"`swing config policy import-from-toml --field "
                f"{policy_field}` to reconcile.",
                err=True,
            )
        finally:
            cascade_conn.close()


# ============================================================================
# Phase 9 T-A.6 — `swing config policy {show,set,import-from-toml,history}`.
# ============================================================================
# Per plan §A.3 + spec §10.5: V1 ships per-field CLI surface; bulk CLI + web
# form deferred to V2. Per dispatch brief §0.3 #9 + spec §A.10:
# all timestamps are server-stamped at service entry (no operator-supplied
# created_at / effective_from / effective_to).

# Coercion map for `policy set --field <name> --value <raw>`. INTEGER fields
# parse as int; REAL fields parse as float; TEXT enum fields stay as str.
_POLICY_FIELD_COERCERS: dict[str, type] = {
    "max_account_risk_per_trade_pct": float,
    "max_concurrent_positions": int,
    "max_portfolio_heat_pct": float,
    "max_sector_concentration_positions": int,
    "consecutive_losses_pause_threshold": int,
    "consecutive_losses_pause_action": str,
    "consecutive_losses_streak_reset": str,
    "drawdown_circuit_breaker_enabled": int,
    "drawdown_pause_threshold_R": float,
    "drawdown_pause_action": str,
    "drawdown_size_reduction_pct": float,
    "drawdown_recovery_threshold_R": float,
    "capital_floor_constant_dollars": float,
    "scratch_epsilon_R": float,
    "review_lag_threshold_days": int,
    "low_sample_size_threshold_class_a_n": int,
    "low_sample_size_threshold_class_b_n": int,
    "low_sample_size_threshold_class_c_n": int,
    "low_sample_size_threshold_class_d_n": int,
    "global_confidence_floor_n": int,
    "bootstrap_resample_count": int,
    "process_grade_weight_entry": float,
    "process_grade_weight_management": float,
    "process_grade_weight_exit": float,
    "mfe_mae_default_precision_level": str,
    "trail_MA_period_days": int,
    "trail_MA_post_2R_period_days": int,
    "policy_notes": str,
}
_POLICY_FIELD_NAMES: tuple[str, ...] = tuple(_POLICY_FIELD_COERCERS.keys())

# Fields that have a Phase-5-surfaced cfg counterpart (eligible for
# `import-from-toml`). Per spec §3.1.3: only ONE field in V1 (the operator
# can extend post-V1 by mapping additional cfg paths to risk_policy
# columns; we keep the map minimal to avoid silent drift).
_TOML_MIRROR_MAP: dict[str, tuple[str, str]] = {
    # risk_policy column → (cfg section, cfg attribute)
    "capital_floor_constant_dollars": ("account", "risk_equity_floor"),
}


def _coerce_policy_value(field: str, raw: str):
    """Coerce a `policy set --value` raw string per the field's type."""
    coercer = _POLICY_FIELD_COERCERS[field]
    try:
        if coercer is int:
            # Reject raw floats that would silently round (e.g. "8.5" → 8).
            if "." in raw:
                raise ValueError(
                    f"{field} requires an integer; got {raw!r}"
                )
            return int(raw)
        if coercer is float:
            return float(raw)
        return raw
    except (TypeError, ValueError) as exc:
        raise click.ClickException(
            f"cannot coerce --value {raw!r} for field {field}: {exc}"
        ) from exc


@config_group.group("policy")
def policy_group() -> None:
    """Phase 9 risk_policy CRUD — view + supersede the active policy.

    Per spec §3.1 + plan §A.3: V1 surfaces per-field CLI editing.
    Bulk + web form deferred to V2.
    """


@policy_group.command("show")
@click.pass_context
def policy_show(ctx: click.Context) -> None:
    """Print the active risk_policy row."""
    from swing.data.db import connect
    from swing.trades.risk_policy import read_active_policy

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        active = read_active_policy(conn)
    finally:
        conn.close()

    click.echo(f"policy_id          = {active.policy_id}")
    click.echo(f"is_active          = {active.is_active}")
    click.echo(f"effective_from     = {active.effective_from}")
    click.echo(f"created_at         = {active.created_at}")
    if active.policy_notes:
        click.echo(f"policy_notes       = {active.policy_notes}")
    click.echo("")
    click.echo("--- Trading risk ---")
    click.echo(f"max_account_risk_per_trade_pct       = {active.max_account_risk_per_trade_pct}")
    click.echo(f"max_concurrent_positions             = {active.max_concurrent_positions}")
    click.echo(f"max_portfolio_heat_pct               = {active.max_portfolio_heat_pct}")
    click.echo(
        "max_sector_concentration_positions   = "
        f"{active.max_sector_concentration_positions}"
    )
    click.echo(
        "consecutive_losses_pause_threshold   = "
        f"{active.consecutive_losses_pause_threshold}"
    )
    click.echo(f"consecutive_losses_pause_action      = {active.consecutive_losses_pause_action}")
    click.echo(f"consecutive_losses_streak_reset      = {active.consecutive_losses_streak_reset}")
    click.echo("")
    click.echo("--- Drawdown circuit breaker (default opt-in disabled) ---")
    click.echo(f"drawdown_circuit_breaker_enabled     = {active.drawdown_circuit_breaker_enabled}")
    click.echo(f"drawdown_pause_threshold_R           = {active.drawdown_pause_threshold_R}")
    click.echo(f"drawdown_pause_action                = {active.drawdown_pause_action}")
    click.echo(f"drawdown_size_reduction_pct          = {active.drawdown_size_reduction_pct}")
    click.echo(f"drawdown_recovery_threshold_R        = {active.drawdown_recovery_threshold_R}")
    click.echo("")
    click.echo("--- Capital + sizing ---")
    click.echo(f"capital_floor_constant_dollars       = {active.capital_floor_constant_dollars}")
    click.echo("")
    click.echo("--- Statistics methodology ---")
    click.echo(f"scratch_epsilon_R                    = {active.scratch_epsilon_R}")
    click.echo(f"review_lag_threshold_days            = {active.review_lag_threshold_days}")
    click.echo(
        "low_sample_size_threshold_class_a_n  = "
        f"{active.low_sample_size_threshold_class_a_n}"
    )
    click.echo(
        "low_sample_size_threshold_class_b_n  = "
        f"{active.low_sample_size_threshold_class_b_n}"
    )
    click.echo(
        "low_sample_size_threshold_class_c_n  = "
        f"{active.low_sample_size_threshold_class_c_n}"
    )
    click.echo(
        "low_sample_size_threshold_class_d_n  = "
        f"{active.low_sample_size_threshold_class_d_n}"
    )
    click.echo(f"global_confidence_floor_n            = {active.global_confidence_floor_n}")
    click.echo(f"bootstrap_resample_count             = {active.bootstrap_resample_count}")
    click.echo(f"process_grade_weight_entry           = {active.process_grade_weight_entry}")
    click.echo(f"process_grade_weight_management      = {active.process_grade_weight_management}")
    click.echo(f"process_grade_weight_exit            = {active.process_grade_weight_exit}")
    click.echo("")
    click.echo("--- MFE/MAE + trail-MA ---")
    click.echo(f"mfe_mae_default_precision_level      = {active.mfe_mae_default_precision_level}")
    click.echo(f"trail_MA_period_days                 = {active.trail_MA_period_days}")
    click.echo(f"trail_MA_post_2R_period_days         = {active.trail_MA_post_2R_period_days}")


@policy_group.command("set")
@click.option("--field", "field", required=True,
              type=click.Choice(_POLICY_FIELD_NAMES))
@click.option("--value", "raw_value", required=True, type=str)
@click.option("--notes", "notes", default=None, type=str,
              help="Optional operator rationale stored in policy_notes.")
@click.pass_context
def policy_set(
    ctx: click.Context, field: str, raw_value: str, notes: str | None,
) -> None:
    """Supersede the active policy with a one-field change.

    Per spec §4.1: each set creates a new policy_id row (6-step
    transactional sequence in swing/trades/risk_policy.py:supersede_active_policy).
    Idempotency: V1 has no short-circuit; every set creates a row.
    """
    from swing.data.db import connect
    from swing.trades.risk_policy import (
        CallerHeldTransactionError,
        supersede_active_policy,
    )

    cfg = ctx.obj["config"]
    coerced = _coerce_policy_value(field, raw_value)

    conn = connect(cfg.paths.db_path)
    try:
        new_id = supersede_active_policy(
            conn,
            field_updates={field: coerced},
            notes=notes,
            source="cli",
        )
    except CallerHeldTransactionError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    click.echo(f"new policy_id={new_id}; field {field} = {coerced}")


@policy_group.command("import-from-toml")
@click.option("--field", "field", required=True,
              type=click.Choice(tuple(_TOML_MIRROR_MAP.keys())))
@click.option("--notes", "notes", default=None, type=str)
@click.pass_context
def policy_import_from_toml(
    ctx: click.Context, field: str, notes: str | None,
) -> None:
    """Read the current cfg value + supersede the active policy.

    The reverse of the Phase 5 cfg-cascade (T-A.5): when the operator has
    hand-edited the TOML AND the divergence-warning surfaced, this command
    is the explicit ratification that promotes the TOML edit to a new
    risk_policy row.

    V1 only supports `capital_floor_constant_dollars` (per spec §3.1.3
    only one Phase-5-surfaced field has a cfg counterpart).
    """
    from swing.data.db import connect
    from swing.trades.risk_policy import (
        CallerHeldTransactionError,
        supersede_active_policy,
    )

    if field not in _TOML_MIRROR_MAP:
        raise click.ClickException(
            f"field {field!r} has no TOML counterpart (not mirrored to cfg "
            "in V1; spec §3.1.3 lists only capital_floor_constant_dollars)"
        )
    # Re-load the raw TOML — ctx.obj['config'] may have been corrected by
    # the divergence hook, which would then make `import-from-toml` a no-op.
    # The operator's intent for import-from-toml is "promote the TOML value
    # to canonical", so we MUST read from the raw TOML before the hook
    # rewrites it.
    from swing.config import load as load_cfg_raw
    raw_cfg = load_cfg_raw(ctx.obj["config_path"])
    section, attr = _TOML_MIRROR_MAP[field]
    cfg_value = getattr(getattr(raw_cfg, section), attr)

    conn = connect(raw_cfg.paths.db_path)
    try:
        new_id = supersede_active_policy(
            conn,
            field_updates={field: cfg_value},
            notes=notes or (
                f"import-from-toml: cfg.{section}.{attr}={cfg_value} → "
                f"risk_policy.{field}"
            ),
            source="import_from_toml",
        )
    except CallerHeldTransactionError as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    click.echo(f"new policy_id={new_id}; imported {field} = {cfg_value}")


@policy_group.command("history")
@click.option("--limit", "limit", default=20, type=int,
              help="Maximum rows to display (default 20).")
@click.pass_context
def policy_history(ctx: click.Context, limit: int) -> None:
    """Print recent policy versions ordered by effective_from DESC, policy_id DESC."""
    from swing.data.db import connect
    from swing.data.repos.risk_policy import list_policy_history

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        rows = list_policy_history(conn, limit=limit)
    finally:
        conn.close()
    if not rows:
        click.echo("(no policy rows)")
        return
    for r in rows:
        flag = "ACTIVE  " if r.is_active else "inactive"
        notes = r.policy_notes or ""
        click.echo(
            f"policy_id={r.policy_id:<4} {flag} "
            f"effective_from={r.effective_from}  "
            f"effective_to={r.effective_to or '(none)'}  "
            f"capital_floor={r.capital_floor_constant_dollars}  "
            f"max_risk_pct={r.max_account_risk_per_trade_pct}  "
            f"superseded_by={r.superseded_by_policy_id or '(none)'}  "
            f"{notes}"
        )
