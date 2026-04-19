"""is_stale_eligible — two-signal (heartbeat + step-progress) staleness check.
Spec §5.6, §3c/§2.3."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta


def _mk_run(
    *, hb_age_seconds: float | None = None,
    step_age_seconds: float | None = None,
    state: str = "running",
):
    from swing.data.models import PipelineRun
    now = datetime.now()
    hb = (now - timedelta(seconds=hb_age_seconds)).isoformat(timespec="seconds") if hb_age_seconds is not None else None
    step = (now - timedelta(seconds=step_age_seconds)).isoformat(timespec="seconds") if step_age_seconds is not None else None
    return PipelineRun(
        id=1, started_ts=now.isoformat(timespec="seconds"), finished_ts=None,
        trigger="manual", data_asof_date="2026-04-19",
        action_session_date="2026-04-19", state=state,
        lease_token="t-x", lease_heartbeat_ts=hb, last_step_progress_ts=step,
        current_step="evaluate", weather_status=None, evaluation_status=None,
        watchlist_status=None, recommendations_status=None, charts_status=None,
        export_status=None, rs_universe_version=None, rs_universe_hash=None,
        finviz_csv_path=None, error_message=None, warnings_json=None,
    )


def _mk_cfg(lease_threshold=300, step_threshold=900):
    """Minimal cfg stub — only the two pipeline thresholds are read."""
    from types import SimpleNamespace
    return SimpleNamespace(
        pipeline=SimpleNamespace(
            stale_lease_threshold_seconds=lease_threshold,
            stale_step_threshold_seconds=step_threshold,
        ),
    )


def test_is_stale_eligible_both_signals_stale():
    """Spec §5.6: only stale when BOTH heartbeat AND step-progress exceed thresholds."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=1200)
    cfg = _mk_cfg(lease_threshold=300, step_threshold=900)
    assert is_stale_eligible(run, cfg) is True


def test_is_stale_eligible_only_heartbeat_stale_returns_false():
    """Heartbeat stale but step-progress fresh → NOT stale (long-running step)."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=30)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_only_step_stale_returns_false():
    """Step-progress stale but heartbeat fresh → NOT stale (wedged UI-side only)."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=30, step_age_seconds=1200)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_non_running_state_returns_false():
    """Only state='running' is eligible — 'force_cleared', 'complete', etc. are not."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=1200, state="force_cleared")
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_missing_timestamps_treats_as_stale():
    """Either timestamp missing → treated as infinitely stale."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=None, step_age_seconds=None)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is True
