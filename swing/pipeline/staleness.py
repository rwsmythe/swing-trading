"""Pipeline-run staleness detection — both-signal check per spec §5.6.

A run is force-clear-eligible only when BOTH:
  - heartbeat age > stale_lease_threshold_seconds
  - step-progress age > stale_step_threshold_seconds
AND state == 'running'.

Shared by CLI (`swing pipeline force-clear`) and the web dashboard's
force-clear route (Phase 3c). Spec §3c/§2.3 notes this module is NEW and
replaces the inline check that lived in cli.py::pipeline_force_clear_cmd.
"""
from __future__ import annotations

from datetime import datetime

from swing.config import Config
from swing.data.models import PipelineRun


def is_stale_eligible(run: PipelineRun, cfg: Config) -> bool:
    """Return True iff the run is force-clear-eligible under spec §5.6.

    - Requires state == 'running'.
    - Requires BOTH heartbeat age AND step-progress age > their thresholds.
    - Missing timestamps are treated as infinitely stale (threshold exceeded).
    """
    if run.state != "running":
        return False
    now = datetime.now()
    hb_age = float("inf")
    step_age = float("inf")
    if run.lease_heartbeat_ts:
        hb_age = (now - datetime.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
    if run.last_step_progress_ts:
        step_age = (now - datetime.fromisoformat(run.last_step_progress_ts)).total_seconds()
    hb_stale = hb_age > cfg.pipeline.stale_lease_threshold_seconds
    step_stale = step_age > cfg.pipeline.stale_step_threshold_seconds
    return hb_stale and step_stale
