"""Shared fixtures for Phase 3a web tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import ensure_schema


@pytest.fixture
def test_cfg(tmp_path: Path) -> tuple[Config, Path]:
    """Return (cfg, cfg_path) for a fresh test project."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    return cfg, cfg_path


@pytest.fixture
def seeded_db(test_cfg) -> tuple[Config, Path]:
    """Ensure schema is applied; return (cfg, cfg_path). Subtests may seed rows."""
    cfg, cfg_path = test_cfg
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path


@pytest.fixture
def seed_stale_run(seeded_db):
    """Seed a PipelineRun with state='running' and configurable heartbeat +
    step-progress ages (in seconds). Returns the new run_id."""
    from datetime import datetime, timedelta

    from swing.data.db import connect

    cfg, _ = seeded_db

    def _seed(*, hb_age: int | None, step_age: int | None, state: str = "running") -> int:
        now = datetime.now()
        hb_ts = (
            (now - timedelta(seconds=hb_age)).isoformat(timespec="seconds")
            if hb_age is not None else None
        )
        step_ts = (
            (now - timedelta(seconds=step_age)).isoformat(timespec="seconds")
            if step_age is not None else None
        )
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO pipeline_runs
                      (started_ts, trigger, data_asof_date, action_session_date,
                       state, lease_token, lease_heartbeat_ts, last_step_progress_ts,
                       current_step)
                    VALUES (?, 'manual', ?, ?, ?, 't-x', ?, ?, 'evaluate')
                    """,
                    (
                        now.isoformat(timespec="seconds"),
                        now.date().isoformat(),
                        now.date().isoformat(),
                        state,
                        hb_ts,
                        step_ts,
                    ),
                )
                return int(cur.lastrowid)
        finally:
            conn.close()

    return _seed
