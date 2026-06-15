"""Phase 18 Arc 18-F: the health drill-down page VMs.

Read-only VMs for `GET /health/tool` + `GET /health/research`, mirroring the
`TradeDrilldownVM` precedent (the `**_base_banner_fields` spread so the base
layout renders without an UndefinedError). DEFENSIVE: a builder failure degrades
to a grey/not-available VM rather than 500 the drill-down (the stoplights on the
page already came through the context processor).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from swing.config import Config
from swing.evaluation.dates import PageKind
from swing.monitoring.stoplights import read_validated_research_envelope
from swing.web.view_models.journal import _base_banner_fields

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResearchCheck:
    """The render shape for a research check (dot-accessible, mirroring 18-E's
    ToolHealthCheck so BOTH templates use uniform `{{ check.key }}` dot access —
    never dicts/item-access)."""

    key: str
    status: str
    summary: str
    detail: str | None = None


@dataclass(frozen=True)
class ToolHealthPageVM:
    overall: str
    checks: tuple  # 18-E's ToolHealthCheck instances (already dot-accessible)
    generated_ts: str
    PAGE_KIND = PageKind.HISTORY_ANALYSIS

    # base-banner fields (populated via **_base_banner_fields):
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None


@dataclass(frozen=True)
class ResearchHealthPageVM:
    available: bool
    overall: str | None
    checks: tuple[ResearchCheck, ...]
    generated_ts: str | None
    PAGE_KIND = PageKind.HISTORY_ANALYSIS

    # base-banner fields (populated via **_base_banner_fields):
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None


def build_tool_health_vm(conn, cfg: Config) -> ToolHealthPageVM:
    """Build the tool-health drill-down VM. REUSES 18-E's compute_tool_health
    (lazy import). DEFENSIVE: a compute failure degrades to a grey VM with no
    checks rather than 500."""
    banner = _base_banner_fields(conn, cfg)
    try:
        from swing.monitoring.tool_health import compute_tool_health
        status = compute_tool_health(
            conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir,
        )
        return ToolHealthPageVM(
            overall=status.overall,
            checks=status.checks,
            generated_ts=status.generated_ts,
            **banner,
        )
    except Exception as exc:  # noqa: BLE001 (defensive — no 500 on the drill-down)
        _log.warning("tool-health drill-down degraded to grey: %s", exc)
        return ToolHealthPageVM(
            overall="grey", checks=(), generated_ts="", **banner,
        )


def build_research_health_vm(conn, cfg: Config) -> ResearchHealthPageVM:
    """Build the research drill-down VM via the SHARED validating reader (same
    identity+staleness gate as the stoplight — validation NOT re-derived). When
    the artifact is absent/malformed/wrong-id/invalid/stale -> the
    not-available VM (the 18-D-pending page). DEFENSIVE: never 500."""
    banner = _base_banner_fields(conn, cfg)
    try:
        validated = read_validated_research_envelope()
        if validated is None:
            return ResearchHealthPageVM(
                available=False, overall=None, checks=(), generated_ts=None,
                **banner,
            )
        overall, env = validated
        checks: list[ResearchCheck] = []
        for c in env.get("checks") or []:
            try:
                checks.append(
                    ResearchCheck(
                        key=c["key"],
                        status=c["status"],
                        summary=c["summary"],
                        detail=c.get("detail"),
                    )
                )
            except Exception as exc:  # noqa: BLE001 (one bad check != 500)
                _log.warning("skipping malformed research check %r: %s", c, exc)
        return ResearchHealthPageVM(
            available=True,
            overall=overall,
            checks=tuple(checks),
            generated_ts=env.get("generated_ts"),
            **banner,
        )
    except Exception as exc:  # noqa: BLE001 (defensive — no 500 on the drill-down)
        _log.warning("research drill-down degraded to not-available: %s", exc)
        return ResearchHealthPageVM(
            available=False, overall=None, checks=(), generated_ts=None,
            **banner,
        )
