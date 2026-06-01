"""PipelineVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import PipelineRun
from swing.data.repos.pipeline import find_active_run, list_recent_runs
from swing.pipeline.staleness import is_stale_eligible


@dataclass(frozen=True)
class PipelineVM:
    session_date: str
    recent_runs: list[PipelineRun]
    stale_run: PipelineRun | None = None
    # Base-template banner fields
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False              # NEW (Phase 3d §3.4)
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
                    "PipelineVM.banner_resolve_link must be str | None; "
                    f"got {type(self.banner_resolve_link).__name__}"
                )
            if (
                not self.banner_resolve_link
                or not self.banner_resolve_link.startswith("/")
            ):
                raise ValueError(
                    "PipelineVM.banner_resolve_link must be None or a "
                    "non-empty path starting with '/'; got "
                    f"{self.banner_resolve_link!r}"
                )


def build_pipeline(*, cfg: Config, limit: int = 10, ohlcv_degraded: bool = False) -> PipelineVM:
    from swing.metrics.discrepancies import (
        count_recent_multi_leg_auto_corrections,
        count_unresolved_material,
        fetch_first_pending_ambiguity_resolve_link_path,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            runs = list_recent_runs(conn, limit=limit)
            active = find_active_run(conn)
            stale = active if (active is not None and is_stale_eligible(active, cfg)) else None
            unresolved = count_unresolved_material(conn)
            recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)
            banner_resolve_link = (
                fetch_first_pending_ambiguity_resolve_link_path(conn)
            )
    finally:
        conn.close()
    from swing.web.view_models.schwab_checker_badge import build_schwab_checker_badge
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
        stale_run=stale,
        ohlcv_source_degraded=ohlcv_degraded,            # NEW (Phase 3d §3.4)
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,
        banner_resolve_link=banner_resolve_link,
        schwab_checker_badge=build_schwab_checker_badge(cfg),
    )
