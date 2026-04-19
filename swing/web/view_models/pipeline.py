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


def build_pipeline(*, cfg: Config, limit: int = 10) -> PipelineVM:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            runs = list_recent_runs(conn, limit=limit)
            active = find_active_run(conn)
            stale = active if (active is not None and is_stale_eligible(active, cfg)) else None
    finally:
        conn.close()
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
        stale_run=stale,
    )
