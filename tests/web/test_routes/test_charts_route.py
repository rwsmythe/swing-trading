"""GET /charts/{ticker}.png — date-less chart redirect (Tier-2 #2).

Looks up the latest completed pipeline run's data_asof_date, calls the
existing chart_scope.resolve_chart_scope, and either:
  - 303 redirects to /charts/<date>/<TICKER>.png (StaticFiles serves the PNG), or
  - returns 404 with the operator-facing chart-unavailable reason in the body.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from swing.web.chart_scope import CHART_REASON_MESSAGES


def _insert_pipeline_run(
    conn, *, started_ts, finished_ts, data_asof_date,
    state="complete", charts_status="ok", action_session_date=None,
    lease_token="t-x", evaluation_run_id=None,
) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, charts_status,
            evaluation_run_id)
           VALUES (?, ?, 'manual', ?, ?, ?, ?, ?, ?)""",
        (started_ts, finished_ts, data_asof_date,
         action_session_date or data_asof_date,
         state, lease_token, charts_status, evaluation_run_id),
    )
    return int(cur.lastrowid)


def _insert_eval_run(conn, *, run_ts, data_asof_date) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts, data_asof_date, data_asof_date),
    )
    return int(cur.lastrowid)


def _insert_chart_target(conn, *, pipeline_run_id, ticker,
                         source="aplus", chart_status="ok"):
    conn.execute(
        """INSERT INTO pipeline_chart_targets
           (pipeline_run_id, ticker, source, chart_status)
           VALUES (?, ?, ?, ?)""",
        (pipeline_run_id, ticker, source, chart_status),
    )


def _write_chart(charts_dir: Path, *, date: str, ticker: str) -> Path:
    target = charts_dir / date / f"{ticker}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stub")
    return target


def test_charts_redirect_in_scope_303_to_dated_url(seeded_db):
    """In-scope ticker with PNG on disk → 303 redirect to /charts/<date>/<ticker>.png."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_id = _insert_eval_run(
                conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
            )
            run_id = _insert_pipeline_run(
                conn, started_ts="2026-04-17T21:00:00",
                finished_ts="2026-04-17T21:55:00",
                data_asof_date="2026-04-17", evaluation_run_id=eval_id,
            )
            _insert_chart_target(
                conn, pipeline_run_id=run_id, ticker="AAPL",
                source="aplus", chart_status="ok",
            )
    finally:
        conn.close()
    _write_chart(cfg.paths.charts_dir, date="2026-04-17", ticker="AAPL")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/charts/AAPL.png", follow_redirects=False)
    assert r.status_code == 303, (
        f"expected 303 redirect to dated URL; got {r.status_code} body={r.text[:120]!r}"
    )
    assert r.headers["location"] == "/charts/2026-04-17/AAPL.png", (
        f"redirect Location wrong: {r.headers.get('location')!r}"
    )


def test_charts_redirect_no_run_404_with_reason(seeded_db):
    """No completed pipeline run → 404 with no-run reason message in body."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/charts/AAPL.png", follow_redirects=False)
    assert r.status_code == 404
    assert CHART_REASON_MESSAGES["no-run"] in r.text


def test_charts_redirect_out_of_scope_404_with_reason(seeded_db):
    """Pipeline ran, ticker not in chart-scope → 404 with out-of-scope message."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_id = _insert_eval_run(
                conn, run_ts="2026-04-17T21:30:00", data_asof_date="2026-04-17",
            )
            run_id = _insert_pipeline_run(
                conn, started_ts="2026-04-17T21:00:00",
                finished_ts="2026-04-17T21:55:00",
                data_asof_date="2026-04-17", evaluation_run_id=eval_id,
            )
            _insert_chart_target(
                conn, pipeline_run_id=run_id, ticker="MSFT",
                source="aplus", chart_status="ok",
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/charts/XYZNOTINSCOPE.png", follow_redirects=False)
    assert r.status_code == 404
    # Substring check: avoids coupling to html.escape behavior (apostrophes
    # in the message become &#x27;) while still discriminating between the
    # right reason (out-of-scope) and the wrong reason (no-run, etc).
    assert "today" in r.text and "charting scope" in r.text
    assert CHART_REASON_MESSAGES["no-run"] not in r.text


def test_charts_redirect_does_not_intercept_dated_url(seeded_db):
    """The new dynamic /charts/{ticker}.png route MUST NOT match the
    date-prefixed URL /charts/<date>/<TICKER>.png — that has two path
    segments and falls through to the StaticFiles mount.

    Pre-fix discriminator: if the dynamic route accidentally claimed the
    dated path (e.g. caught everything under /charts/), this test would
    return 303/404 instead of the StaticFiles 200/404 path.

    Post-fix: PNG exists under <charts_dir>/<date>/<ticker>.png → 200
    (StaticFiles serves it directly, no redirect involved).
    """
    cfg, cfg_path = seeded_db
    _write_chart(cfg.paths.charts_dir, date="2026-04-17", ticker="AAPL")

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/charts/2026-04-17/AAPL.png", follow_redirects=False)
    assert r.status_code == 200, (
        f"dated /charts/<date>/<ticker>.png must hit StaticFiles, not the "
        f"dynamic redirect route; got {r.status_code} body={r.text[:120]!r}"
    )
    assert r.content == b"stub"
