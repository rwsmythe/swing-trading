"""PipelineVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import PipelineRun
from swing.data.repos.pipeline import list_recent_runs


@dataclass(frozen=True)
class PipelineVM:
    session_date: str
    recent_runs: list[PipelineRun]
    # Base-template banner fields
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None


def build_pipeline(*, cfg: Config, limit: int = 10) -> PipelineVM:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            runs = list_recent_runs(conn, limit=limit)
    finally:
        conn.close()
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
    )
