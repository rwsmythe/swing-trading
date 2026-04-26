"""Pipeline routes. POST handlers land in Tasks 17–19."""
from __future__ import annotations

import logging
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from swing.data.db import connect
from swing.data.repos.pipeline import find_active_run, find_run, force_clear
from swing.data.repos.trades import list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.pipeline.finviz_schema import validate_csv
from swing.pipeline.staleness import is_stale_eligible
from swing.web.view_models.dashboard import _sort_by_proximity, build_dashboard
from swing.web.view_models.pipeline import build_pipeline

router = APIRouter()

log = logging.getLogger(__name__)


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    cfg = request.app.state.cfg
    ohlcv_degraded = request.app.state.ohlcv_cache.is_degraded()      # NEW
    vm = build_pipeline(cfg=cfg, ohlcv_degraded=ohlcv_degraded)       # NEW kwarg
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
        # Three cases for an existing active run (spec §3.1, §5.6):
        #   (a) malformed — missing heartbeat or step-progress timestamp →
        #       not stale-eligible AND not showable as normal progress; direct
        #       operator to CLI `--bypass-staleness-check` escape hatch.
        #   (b) truly stale (both signals stale) → direct to the in-page
        #       stale-run card (which GET /pipeline already renders).
        #   (c) fresh or partially-fresh → show existing progress.
        has_incomplete_liveness = (
            not active.lease_heartbeat_ts or not active.last_step_progress_ts
        )
        if has_incomplete_liveness:
            return templates.TemplateResponse(
                request, "partials/pipeline_progress.html.j2",
                {
                    "run": None,
                    "error_text": (
                        f"Active run #{active.id} has incomplete liveness data "
                        f"(missing heartbeat or step-progress timestamp). The "
                        f"dashboard Force-clear button is gated on positive "
                        f"two-signal evidence per spec §5.6. Use CLI: "
                        f"`swing pipeline force-clear {active.id} "
                        f"--bypass-staleness-check`."
                    ),
                    "poll_interval": poll_interval,
                },
            )
        if not is_stale_eligible(active, cfg):
            # Fresh (or partially-fresh by age, both timestamps present) — show
            # existing progress.
            return templates.TemplateResponse(
                request, "partials/pipeline_progress.html.j2",
                {"run": active, "error_text": None, "poll_interval": poll_interval},
            )
        # Truly stale under the two-signal rule — direct the operator to the
        # in-page force-clear card (which is already rendered on GET /pipeline
        # via vm.stale_run).
        return templates.TemplateResponse(
            request, "partials/pipeline_progress.html.j2",
            {
                "run": None,
                "error_text": (
                    f"A previous run is wedged (run #{active.id}, state=running). "
                    f"Reload /pipeline and use the Force clear button on the "
                    f"stale-run card."
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

    # Wait for the child to acquire its lease. Configurable because Python 3.14
    # + heavy imports on Windows regularly exceed a 2s cold-start — 5s default
    # gives headroom without making legitimate failures feel slow.
    deadline = time.monotonic() + cfg.web.pipeline_lease_wait_seconds
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
                    f"Pipeline subprocess did not acquire lease within "
                    f"{cfg.web.pipeline_lease_wait_seconds:g}s. "
                    f"Check `swing-data/logs/pipeline.log` and "
                    f"`swing-data/logs/web.log`."
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


@router.get("/pipeline/stale-run-card/{run_id}", response_class=HTMLResponse)
def stale_run_card(request: Request, run_id: int):
    """Render the fresh stale-run card for an eligible run. Used by the Cancel
    button on the force-clear confirm fragment (reverts the swap)."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None or not is_stale_eligible(run, cfg):
        raise HTTPException(
            status_code=404,
            detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
        )
    return templates.TemplateResponse(
        request, "partials/stale_run_card.html.j2", {"run": run},
    )


@router.get("/pipeline/force-clear/{run_id}/confirm", response_class=HTMLResponse)
def force_clear_confirm(request: Request, run_id: int):
    """Render the 2-step confirm fragment for an eligible stale run (spec §3.1)."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None or not is_stale_eligible(run, cfg):
        raise HTTPException(
            status_code=404,
            detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
        )
    return templates.TemplateResponse(
        request, "partials/force_clear_confirm.html.j2", {"run": run},
    )


@router.post("/pipeline/force-clear/{run_id}", response_class=HTMLResponse)
def force_clear_post(request: Request, run_id: int):
    """Execute force-clear after the 2-step confirm (spec §3.1, §4.2).

    Pre-check: is_stale_eligible (TOCTOU guard against cancel/clear between
    GET confirm and POST). Post-check: re-read the run and verify state
    transitioned to 'force_cleared' (guards against a concurrent writer that
    raced our UPDATE with a different state value — 409 fragment in that case).
    """
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    iso_ts = datetime.now().isoformat(timespec="seconds")

    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
        if run is None or not is_stale_eligible(run, cfg):
            raise HTTPException(
                status_code=404,
                detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
            )
        with conn:
            force_clear(
                conn,
                run_id=run_id,
                error_message=f"dashboard force clear at {iso_ts}",
            )
        # Re-read to confirm the state transition landed.
        updated = find_run(conn, run_id)
    finally:
        conn.close()

    if updated is None or updated.state != "force_cleared":
        # Concurrent writer raced us — state changed before our UPDATE but
        # didn't become 'force_cleared'. Return 409 to signal the conflict.
        return templates.TemplateResponse(
            request, "partials/http_error_fragment.html.j2",
            {
                "status_code": 409,
                "detail": (
                    f"Run #{run_id} state conflict (currently "
                    f"{updated.state if updated else 'missing'}). Refresh the page."
                ),
            },
            status_code=409,
        )

    return templates.TemplateResponse(
        request, "partials/force_clear_success.html.j2",
        {"run_id": run_id},
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
    # 3e.3: also reset the OHLCV breaker so SMA advisories recover on the
    # next dashboard render. Same operator-override rationale; a separately-
    # tripped OHLCV breaker would otherwise leave advisories blank with no
    # UI affordance to retry. Use getattr so the guard is real for both
    # absent attribute AND attribute-set-to-None cases (R1 Minor 1).
    ohlcv_cache = getattr(request.app.state, "ohlcv_cache", None)
    if ohlcv_cache is not None:
        ohlcv_cache.reset_circuit_breaker()
    cache.refresh_all(active)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor,
                         ohlcv_cache=request.app.state.ohlcv_cache)
    return templates.TemplateResponse(
        request, "partials/prices_refresh_container.html.j2",
        {"vm": vm},
    )


_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.csv$")


def _sanitize_filename(raw: str | None) -> str | None:
    """Return a safe inbox filename or None if unacceptable.

    Accepts: A-Z, a-z, 0-9, underscore, dot, hyphen. Must start with alphanumeric
    and end in .csv. Any path separators (`/` or `\\`) or '..' segments in the
    RAW submitted filename → rejected (rather than silently stripped), so an
    operator uploading `../evil.csv` gets a visible error, not a silent rename.
    Spec §4.1 + §9.7.
    """
    if not raw:
        return None
    if "/" in raw or "\\" in raw or ".." in raw:
        return None
    name = raw.strip().lower()
    if not _FILENAME_RE.match(name):
        return None
    return name


@router.post("/pipeline/csv-upload", response_class=HTMLResponse)
async def csv_upload(request: Request, csv: Annotated[UploadFile, File(...)]):
    """Upload a finviz CSV to the inbox. Validate schema + sanitize filename +
    atomically replace any existing same-name file. Spec §3.1 / §4.1."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    max_bytes = cfg.web.csv_upload_max_bytes

    # Route-level size safety-net (middleware also guards via Content-Length).
    # UploadFile.size is populated by Starlette after multipart parsing.
    if csv.size is not None and csv.size > max_bytes:
        return templates.TemplateResponse(
            request, "partials/csv_upload_error.html.j2",
            {"reasons": [f"file too large ({csv.size} bytes > {max_bytes} limit)"]},
            status_code=413,
        )

    sanitized = _sanitize_filename(csv.filename)
    if sanitized is None:
        return templates.TemplateResponse(
            request, "partials/csv_upload_error.html.j2",
            {"reasons": [f"invalid filename: {csv.filename!r}"]},
            status_code=400,
        )

    # Temp file MUST live in the inbox directory so os.replace is a same-volume
    # atomic rename (spec §4.1 — avoids cross-device EXDEV on Windows cloud-sync).
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(suffix=".csv", dir=str(inbox))
    tmp_path = pathlib.Path(tmp_path_str)
    try:
        # Write upload bytes to tmp file, enforcing limit along the way.
        total = 0
        os_write = os.write
        while True:
            chunk = await csv.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                os.close(fd)
                tmp_path.unlink(missing_ok=True)
                return templates.TemplateResponse(
                    request, "partials/csv_upload_error.html.j2",
                    {"reasons": [f"file too large (streamed > {max_bytes} bytes)"]},
                    status_code=413,
                )
            os_write(fd, chunk)
        os.close(fd)

        result = validate_csv(tmp_path)
        if not result.is_valid:
            tmp_path.unlink(missing_ok=True)
            return templates.TemplateResponse(
                request, "partials/csv_upload_error.html.j2",
                {"reasons": result.reasons},
                status_code=400,
            )

        final_path = inbox / sanitized
        os.replace(tmp_path, final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return templates.TemplateResponse(
        request, "partials/csv_upload_form.html.j2",
        {"uploaded_banner": {"name": sanitized, "rows": result.row_count}},
        status_code=200,
    )


def _heartbeat_age_seconds(ts: str | None) -> float | None:
    if ts is None:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
    except ValueError:
        return None
