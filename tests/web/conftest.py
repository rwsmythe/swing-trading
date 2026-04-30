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


@pytest.fixture
def seed_watchlist_and_candidate(seeded_db):
    """Seed an active watchlist row + a completed pipeline_run + (optionally) a
    candidate row with `pivot=candidate_pivot`. When `candidate_pivot is
    None`, no candidate row exists for the ticker (fallback path).

    Lifted from `tests/web/test_watchlist_pivot_column.py:53` (Phase 4 Task 11).
    """
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry

    cfg, _ = seeded_db

    def _make_watchlist_entry(
        *, ticker, entry_target=None, initial_stop_target=None,
        last_close=None, last_adr_pct=2.0,
    ):
        return WatchlistEntry(
            ticker=ticker, added_date="2026-04-29",
            last_qualified_date="2026-04-29", status="watch",
            qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-04-28",
            entry_target=entry_target,
            initial_stop_target=initial_stop_target,
            last_close=last_close, last_pivot=None, last_stop=None,
            last_adr_pct=last_adr_pct, missing_criteria=None, notes=None,
        )

    def _seed(*, ticker, entry_target, candidate_pivot, last_close):
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                if entry_target is not None:
                    upsert_watchlist_entry(
                        conn,
                        _make_watchlist_entry(
                            ticker=ticker, entry_target=entry_target,
                            initial_stop_target=entry_target * 0.95,
                            last_close=last_close,
                        ),
                    )
                else:
                    upsert_watchlist_entry(
                        conn,
                        _make_watchlist_entry(
                            ticker=ticker, entry_target=None,
                            initial_stop_target=None, last_close=last_close,
                        ),
                    )
                cur = conn.execute(
                    """INSERT INTO evaluation_runs
                       (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                        tickers_evaluated, aplus_count, watch_count, skip_count,
                        excluded_count, error_count)
                       VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                               NULL, 1, 0, 1, 0, 0, 0)"""
                )
                eval_run_id = cur.lastrowid
                conn.execute(
                    """INSERT INTO pipeline_runs
                       (started_ts, finished_ts, trigger, data_asof_date,
                        action_session_date, state, lease_token,
                        evaluation_run_id, charts_status)
                       VALUES ('2026-04-29T08:00:00','2026-04-29T09:00:00',
                               'manual','2026-04-28','2026-04-29','complete',
                               't-test', ?, 'ok')""",
                    (eval_run_id,),
                )
                if candidate_pivot is not None:
                    conn.execute(
                        """INSERT INTO candidates
                           (evaluation_run_id, ticker, bucket, close, pivot,
                            initial_stop, adr_pct, tight_streak, pullback_pct,
                            prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                            rs_method, pattern_tag, notes, sector, industry)
                           VALUES (?, ?, 'watch', ?, ?, ?, 2.0, 5, NULL, NULL,
                                   NULL, NULL, 'fallback_spy', NULL, NULL,
                                   'Technology', 'Software-Application')""",
                        (
                            eval_run_id, ticker, candidate_pivot,
                            candidate_pivot, candidate_pivot * 0.95,
                        ),
                    )
        finally:
            conn.close()

    return _seed
