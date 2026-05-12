"""ConfigPageVM + build_config_vm."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from swing.config import Config
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_validation import FIELD_REGISTRY, FieldSpec


@dataclass(frozen=True)
class ConfigFieldRow:
    path: str
    label: str
    description: str
    current_value: Any
    default_value: Any
    source: str         # "default" | "tracked" | "override"
    input_kind: str     # "float" | "int" — drives <input type="number" step="...">
    soft_warn_min: Any | None
    soft_warn_max: Any | None
    hard_refuse_min: Any | None
    hard_refuse_max: Any | None


@dataclass(frozen=True)
class ConfigPageVM:
    rows: list[ConfigFieldRow]
    saved: bool                                # set by ?saved=1 redirect-back
    # Base-layout banner fields (CLAUDE.md base.html.j2 5-VM rule check —
    # these fields are dereferenced by base.html.j2 even when Task 7 confirmed
    # the nav link is static; the VM still inherits the banner-field schema).
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    # Phase 9 T-A.5 Codex R1 Major #3 fix — visible TOML divergence banner
    # per spec §3.1.3 R3 Minor #2 ("yellow-banner warning until resolved").
    # Populated by build_config_vm via a fresh DB read against the active
    # risk_policy. None means no divergence (banner suppressed).
    risk_policy_divergence: dict | None = None


def _current_value(cfg: Config, spec: FieldSpec) -> Any:
    section, key = spec.path.split(".")
    return getattr(getattr(cfg, section), key)


def build_config_vm(
    base_cfg: Config,
    *,
    saved: bool = False,
    conn: Any = None,
) -> ConfigPageVM:
    """Build the /config page VM.

    The optional ``conn`` parameter lets the route pass a sqlite3.Connection
    so the VM can detect TOML/risk_policy divergence per spec §3.1.3 R3
    Minor #2 (Codex R1 Major #3 fix). When omitted (e.g., legacy callers,
    tests that don't need divergence), the banner is suppressed.
    """
    eff = apply_overrides(base_cfg)
    rows: list[ConfigFieldRow] = []
    for spec in FIELD_REGISTRY:
        rows.append(ConfigFieldRow(
            path=spec.path,
            label=spec.label,
            description=spec.description,
            current_value=_current_value(eff, spec),
            default_value=spec.default,
            source=get_field_source(base_cfg, spec.path),
            input_kind="int" if spec.type is int else "float",
            soft_warn_min=spec.soft_warn_min,
            soft_warn_max=spec.soft_warn_max,
            hard_refuse_min=spec.hard_refuse_min,
            hard_refuse_max=spec.hard_refuse_max,
        ))
    divergence: dict | None = None
    if conn is not None:
        from swing.trades.risk_policy import check_and_reconcile_toml_divergence
        try:
            # silent=True per Codex R2 Minor #1 — per-render probe must NOT
            # spam logs. Startup hooks emit the warning exactly once at
            # process start; the persistent banner here is the operator
            # surface for ongoing divergence.
            _, divergence = check_and_reconcile_toml_divergence(
                conn, eff, silent=True,
            )
        except Exception:
            # Defensive — banner missing on transient DB error is preferable
            # to a 500 on /config.
            divergence = None
    return ConfigPageVM(
        rows=rows,
        saved=saved,
        session_date=date.today().isoformat(),
        risk_policy_divergence=divergence,
    )
