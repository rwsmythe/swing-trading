"""Pipeline-run staleness detection — both-signal check per spec §5.6.

A run is force-clear-eligible only when ALL of:
  - state == 'running'
  - lease_heartbeat_ts is present AND heartbeat age > stale_lease_threshold_seconds
  - last_step_progress_ts is present AND step-progress age > stale_step_threshold_seconds

Missing timestamps mean the evidence for staleness is absent, so the run is
NOT eligible for force-clear. Force-clear is destructive; we require clear
positive evidence rather than treating "unknown" as "safe to revoke lease."
This avoids false positives during fresh-lease windows (heartbeat not yet
emitted) or on rows produced by a migration/pre-Phase-2 artifact.

Shared by CLI (`swing pipeline force-clear`) and the web dashboard's
force-clear route.
"""
from __future__ import annotations

from datetime import datetime

from swing.config import Config
from swing.data.models import PipelineRun


def is_stale_eligible(
    run: PipelineRun,
    cfg: Config,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True iff the run is force-clear-eligible under spec §5.6.

    - Requires state == 'running'.
    - Requires BOTH heartbeat and step-progress timestamps to be present.
    - Requires BOTH ages to exceed their thresholds.
    - Missing timestamps → NOT eligible (conservative; force-clear is destructive).
    - `now` is injectable for deterministic testing; defaults to `datetime.now()`
      at call time.
    """
    if run.state != "running":
        return False
    if not run.lease_heartbeat_ts or not run.last_step_progress_ts:
        return False
    if now is None:
        now = datetime.now()
    hb_age = (now - datetime.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
    step_age = (now - datetime.fromisoformat(run.last_step_progress_ts)).total_seconds()
    hb_stale = hb_age > cfg.pipeline.stale_lease_threshold_seconds
    step_stale = step_age > cfg.pipeline.stale_step_threshold_seconds
    return hb_stale and step_stale
