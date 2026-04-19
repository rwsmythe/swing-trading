"""Pipeline routes. POST handlers land in Tasks 17–19."""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from swing.data.db import connect
from swing.data.repos.pipeline import find_active_run, find_run
from swing.data.repos.trades import list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.web.view_models.dashboard import _sort_by_proximity, build_dashboard
from swing.web.view_models.pipeline import build_pipeline

router = APIRouter()

log = logging.getLogger(__name__)


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    cfg = request.app.state.cfg
    vm = build_pipeline(cfg=cfg)
    return request.app.state.templates.TemplateResponse(
        request, "pipeline.html.j2", {"vm": vm},
    )


@router.post("/pipeline/run", response_class=HTMLResponse)
def pipeline_run(request: Request):
    cfg = request.app.state.cfg
    cfg_path = request.app.state.cfg_path
    templates = request.app.state.templates

    if cfg_path is None:
        return HTMLResponse(
            "Pipeline subprocess launch requires a config-file-backed app startup. "
            "Configure via `swing --config <path> web`.",
            status_code=503,
        )

    poll_interval = cfg.web.polling_interval_seconds

    # Existing active run?
    conn = connect(cfg.paths.db_path)
    try:
        active = find_active_run(conn)
    finally:
        conn.close()

    if active is not None:
        hb_age = _heartbeat_age_seconds(active.lease_heartbeat_ts)
        stale_threshold = cfg.pipeline.stale_lease_threshold_seconds
        if hb_age is not None and hb_age <= stale_threshold:
            # Fresh heartbeat — show existing progress.
            return templates.TemplateResponse(
                request, "partials/pipeline_progress.html.j2",
                {"run": active, "error_text": None, "poll_interval": poll_interval},
            )
        # Stale heartbeat — explicit manual force-clear required.
        age_min = int((hb_age or 0) // 60)
        return templates.TemplateResponse(
            request, "partials/pipeline_progress.html.j2",
            {
                "run": None,
                "error_text": (
                    f"A previous run is stuck (run #{active.id}, state=running, "
                    f"heartbeat age {age_min}m). A dashboard force-clear button "
                    f"ships in Phase 3b; until then, run `swing pipeline "
                    f"force-clear {active.id} --bypass-staleness-check` in a terminal."
                ),
                "poll_interval": poll_interval,
            },
        )

    # Spawn subprocess.
    cmd = [
        sys.executable, "-m", "swing.cli",
        "--config", str(cfg_path),
        "pipeline", "run", "--manual",
    ]
    log.info("spawning pipeline subprocess: %s", cmd)
    proc = subprocess.Popen(
        cmd, close_fds=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.info("pipeline subprocess started: pid=%d", proc.pid)

    # Wait for the child to acquire its lease (up to 2s).
    deadline = time.monotonic() + 2.0
    run = None
    while time.monotonic() < deadline:
        rc = proc.poll()
        if rc is not None:
            return templates.TemplateResponse(
                request, "partials/pipeline_progress.html.j2",
                {
                    "run": None,
                    "error_text": (
                        f"Pipeline subprocess exited early (code={rc}) before "
                        f"acquiring lease. Check `swing-data/logs/pipeline.log`."
                    ),
                    "poll_interval": poll_interval,
                },
            )
        conn = connect(cfg.paths.db_path)
        try:
            run = find_active_run(conn)
        finally:
            conn.close()
        if run is not None:
            break
        time.sleep(0.05)

    if run is None:
        return templates.TemplateResponse(
            request, "partials/pipeline_progress.html.j2",
            {
                "run": None,
                "error_text": (
                    "Pipeline subprocess did not acquire lease within 2s. "
                    "Check `swing-data/logs/pipeline.log` and "
                    "`swing-data/logs/web.log`."
                ),
                "poll_interval": poll_interval,
            },
        )

    return templates.TemplateResponse(
        request, "partials/pipeline_progress.html.j2",
        {"run": run, "error_text": None, "poll_interval": poll_interval},
    )


@router.get("/pipeline/status/{run_id}", response_class=HTMLResponse)
def pipeline_status(request: Request, run_id: int):
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    poll_interval = cfg.web.polling_interval_seconds
    return templates.TemplateResponse(
        request, "partials/pipeline_progress.html.j2",
        {"run": run, "error_text": None, "poll_interval": poll_interval},
    )


@router.post("/prices/refresh", response_class=HTMLResponse)
def prices_refresh(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates

    # Collect active tickers.
    conn = connect(cfg.paths.db_path)
    try:
        open_trade_tickers = {t.ticker for t in list_open_trades(conn)}
        top5_tickers = {w.ticker for w in _sort_by_proximity(list_active_watchlist(conn))[:5]}
    finally:
        conn.close()
    active = sorted(open_trade_tickers | top5_tickers | {cfg.rs.benchmark_ticker})

    # Manual refresh resets the circuit breaker (R2 Major 2). A user-clicked
    # Refresh button is an INTENTIONAL override of the automatic degraded
    # short-circuit — the breaker exists to protect request-driven fetches
    # from cascading failure, not to block operator intervention. If the
    # refetch attempt fails, the breaker will simply trip again on its own.
    cache.reset_circuit_breaker()
    cache.refresh_all(active)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request, "partials/prices_refresh_container.html.j2",
        {"vm": vm},
    )


def _heartbeat_age_seconds(ts: str | None) -> float | None:
    if ts is None:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
    except ValueError:
        return None
