"""ConfigPageVM + build_config_vm."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from swing.config import Config
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_validation import (
    FIELD_REGISTRY,
    FieldSpec,
    mask_sensitive_value,
)


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
    # Phase 10 Sub-bundle E T-E.3 — unresolved-material discrepancy banner.
    unresolved_material_discrepancies_count: int = 0
    # Phase 12.5 #1 T-1.8 — multi-leg auto-redirect advisory banner counter.
    recent_multi_leg_auto_correction_count: int = 0
    # Phase 12.5 #2 T-2.7 — banner link to FIRST pending-ambiguity discrepancy
    # resolve form. None when no pending-ambiguity row exists.
    banner_resolve_link: str | None = None
    schwab_checker_badge: object | None = None  # P14.N7 badge (SB5.5)

    def __post_init__(self) -> None:
        if self.banner_resolve_link is not None:
            if not isinstance(self.banner_resolve_link, str):
                raise TypeError(
                    "ConfigPageVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "ConfigPageVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


def _current_value(cfg: Config, spec: FieldSpec) -> Any:
    # Sub-bundle A T-A.2 — walk N-part dotted path for nested sub-dataclass
    # entries (e.g., 'integrations.schwab.account_hash').
    cursor: Any = cfg
    for part in spec.path.split("."):
        cursor = getattr(cursor, part)
    return cursor


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
        raw_value = _current_value(eff, spec)
        # Sub-bundle A T-A.2 — apply masking discipline at render time for
        # `masked=True` entries (e.g., integrations.schwab.account_hash).
        if spec.masked:
            current_value: Any = mask_sensitive_value(raw_value)
        else:
            current_value = raw_value
        # input_kind drives <input type="number" step="...">; str-typed
        # masked-display entries fall back to "text" (display-only / no edit).
        if spec.type is int:
            input_kind = "int"
        elif spec.type is float:
            input_kind = "float"
        else:
            input_kind = "text"
        rows.append(ConfigFieldRow(
            path=spec.path,
            label=spec.label,
            description=spec.description,
            current_value=current_value,
            default_value=spec.default,
            source=get_field_source(base_cfg, spec.path),
            input_kind=input_kind,
            soft_warn_min=spec.soft_warn_min,
            soft_warn_max=spec.soft_warn_max,
            hard_refuse_min=spec.hard_refuse_min,
            hard_refuse_max=spec.hard_refuse_max,
        ))
    divergence: dict | None = None
    unresolved_count = 0
    recent_multi_leg_count = 0
    banner_resolve_link: str | None = None
    if conn is not None:
        from swing.metrics.discrepancies import (
            count_recent_multi_leg_auto_corrections,
            count_unresolved_material,
            fetch_first_pending_ambiguity_resolve_link_path,
        )
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
        try:
            unresolved_count = count_unresolved_material(conn)
        except Exception:
            unresolved_count = 0
        try:
            recent_multi_leg_count = count_recent_multi_leg_auto_corrections(
                conn,
            )
        except Exception:
            recent_multi_leg_count = 0
        try:
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
        except Exception:
            banner_resolve_link = None
    from swing.web.view_models.schwab_checker_badge import build_schwab_checker_badge
    return ConfigPageVM(
        schwab_checker_badge=build_schwab_checker_badge(base_cfg),
        rows=rows,
        saved=saved,
        session_date=date.today().isoformat(),
        risk_policy_divergence=divergence,
        unresolved_material_discrepancies_count=unresolved_count,
        recent_multi_leg_auto_correction_count=recent_multi_leg_count,
        banner_resolve_link=banner_resolve_link,
    )
