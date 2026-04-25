"""Tranche C adversarial-review Round 1 Major 1: _step_export must scope
recommendations to the pipeline's own eval.

Without scoping, a re-run pipeline (or a manual `swing eval` that triggers
recommendation writes) could leave recs from an older eval in
daily_recommendations for tickers the new eval doesn't cover (the upsert
UNIQUE constraint is on (action_session_date, ticker, recommendation), so
older rows for tickers the new eval doesn't see are not overwritten).
The briefing exporter would then emit recs alongside `candidates` from the
current pipeline that don't match those rec rows — internally inconsistent.

This test exercises `_step_export` directly with a synthetic two-eval
fixture and asserts only the bound eval's recs appear in the briefing's
`recommendations` field.
"""
from __future__ import annotations

import sqlite3
from datetime import date as _date
from pathlib import Path

from swing.data.db import ensure_schema


def _seed_eval_with_rec(conn, *, run_ts: str, ticker: str, action_session: str = "2026-04-20"):
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, '2026-04-17', ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts, action_session),
    )
    eval_id = int(cur.lastrowid)
    conn.execute(
        """INSERT INTO candidates
           (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
            rs_method)
           VALUES (?, ?, 'aplus', 100.0, 101.0, 95.0, 'universe')""",
        (eval_id, ticker),
    )
    conn.execute(
        """INSERT INTO daily_recommendations
           (evaluation_run_id, data_asof_date, action_session_date,
            ticker, recommendation, action_text)
           VALUES (?, '2026-04-17', ?, ?, 'today_decision',
                   'Buy-stop $101 · 5 sh · $25 risk')""",
        (eval_id, action_session, ticker),
    )
    return eval_id


def _seed_pipeline_run_running(conn) -> tuple[int, str]:
    """A 'running' pipeline_runs row that satisfies _step_export's
    lease.verify_held()."""
    import uuid
    token = str(uuid.uuid4())
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, trigger, data_asof_date, action_session_date,
            state, lease_token, lease_heartbeat_ts)
           VALUES ('2026-04-17T20:55:00', 'manual', '2026-04-17',
                   '2026-04-20', 'running', ?, '2026-04-17T20:55:00')""",
        (token,),
    )
    return int(cur.lastrowid), token


def _make_cfg(tmp_path: Path):
    from swing.config import load
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


def test_step_export_scopes_recs_to_pipeline_eval(tmp_path: Path, monkeypatch):
    """E1 wrote AAPL today_decision; later E2 wrote NVDA today_decision (a
    re-run pipeline). When _step_export runs bound to E1, the briefing's
    recs must only contain AAPL — NVDA's row from E2 must not leak in."""
    from swing.pipeline.lease import Lease
    from swing.pipeline.runner import _step_export

    cfg = _make_cfg(tmp_path)
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with conn:
            e1 = _seed_eval_with_rec(conn, run_ts="2026-04-17T21:00:00", ticker="AAPL")
            # E2 is a later eval (e.g., a re-run pipeline) that wrote NVDA's rec.
            _seed_eval_with_rec(conn, run_ts="2026-04-17T22:00:00", ticker="NVDA")
            run_id, token = _seed_pipeline_run_running(conn)
    finally:
        conn.close()

    # Capture what BriefingInputs receives; assert only AAPL is in `recommendations`.
    captured = {}
    real_build_view_model = None

    def fake_build_view_model(inputs):
        captured["recs"] = list(inputs.recommendations)
        # Return a minimal view-model-like sentinel; the real one's contract
        # is opaque to this test.
        class _VM:
            briefing_html = ""
            briefing_md = ""
        return _VM()

    monkeypatch.setattr(
        "swing.pipeline.runner.build_briefing_view_model", fake_build_view_model,
    )

    # Stub the heavy export side-effects: we only care about which recs land
    # in BriefingInputs.recommendations.
    monkeypatch.setattr(
        "swing.pipeline.runner.export_briefing",
        lambda **kw: None,
    )
    monkeypatch.setattr(
        "swing.pipeline.runner.promote_staging",
        lambda **kw: type("PR", (), {"target_path": tmp_path})(),
    )
    monkeypatch.setattr(
        "swing.rendering.retention.archive_old_exports",
        lambda **kw: None,
    )

    lease = Lease(db_path=cfg.paths.db_path, run_id=run_id, token=token)
    _step_export(
        cfg=cfg, lease=lease, eval_run_id=e1,
        action_session=_date(2026, 4, 20),
        data_asof="2026-04-17",
        chart_paths={},
    )

    rec_tickers = {r.ticker for r in captured["recs"]}
    assert rec_tickers == {"AAPL"}, (
        f"_step_export must scope recs to its own eval (E1=AAPL); "
        f"E2's NVDA rec must not leak into the briefing. Got {rec_tickers}."
    )
