"""Phase 13 T4.SB Codex R1 MAJOR #1 regression — /watchlist/{ticker}/expand
must thread a SINGLE pipeline_run anchor through both the VM build (chart
URL, candidate criteria, chart-scope reason) and the JIT chart bytes
lookup. Option A "one pipeline_run anchor" discipline (per §1.5.3 LOCK).

Pre-fix defect: ``build_watchlist_expanded`` resolved its OWN
``latest_completed_pipeline_run`` and the route's
``_resolve_jit_chart_bytes`` resolved its own anchor a moment later. A
new pipeline completing between the two reads would surface old-run
candidate / URL / chart-scope reason data alongside new-run JIT SVG
bytes — mixed anchors across one response.

Post-fix: the VM exposes its bound ``pipeline_run_id`` + ``data_asof_date``;
the route passes them explicitly into the JIT helper instead of letting
the helper re-resolve. A pipeline_run landing between VM-build and
JIT-call is IGNORED for JIT chart lookup (anchor stays pinned).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect, ensure_schema
from swing.data.models import ChartRender, WatchlistEntry
from swing.data.repos.chart_renders import refresh_chart_render
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


@pytest.fixture
def isolated_cfg(tmp_path: Path):
    from dataclasses import replace as dc_replace

    from swing.config import load as load_config

    db_path = tmp_path / "phase13_t4_sb_jit_anchor.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return cfg, Path("swing.config.toml")


def _patch_price_cache(monkeypatch, ticker: str) -> None:
    snap = PriceSnapshot(
        ticker=ticker, price=10.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snap for t in tickers if t == ticker
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _seed_watchlist(cfg, ticker: str) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = WatchlistEntry(
                ticker=ticker, added_date="2026-04-29",
                last_qualified_date="2026-04-29", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-28",
                entry_target=11.0,
                initial_stop_target=10.45,
                last_close=10.50, last_pivot=None, last_stop=None,
                last_adr_pct=2.0, missing_criteria=None, notes=None,
            )
            upsert_watchlist_entry(conn, wl)
    finally:
        conn.close()


def _insert_completed_pipeline_run(
    cfg, *, finished_ts: str, data_asof_date: str,
    action_session_date: str, lease_token: str,
) -> int:
    """Insert a complete pipeline_run + linked evaluation_run; return run_id."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count)
                   VALUES (?, ?, ?, NULL, 1, 0, 1, 0, 0, 0)""",
                (finished_ts, data_asof_date, action_session_date),
            )
            eval_run_id = int(cur.lastrowid)
            cur = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES (?, ?, 'manual', ?, ?, 'complete', ?, ?, 'ok')""",
                (
                    finished_ts, finished_ts, data_asof_date,
                    action_session_date, lease_token, eval_run_id,
                ),
            )
            run_id = int(cur.lastrowid)
    finally:
        conn.close()
    return run_id


def _plant_chart_render(
    cfg, *, ticker: str, surface: str,
    pipeline_run_id: int, data_asof_date: str, body: bytes,
) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=ticker, surface=surface,
                chart_svg_bytes=body,
                source_data_hash="t-anchor",
                rendered_at="2026-05-20T08:05:00Z",
                data_asof_date=data_asof_date,
                pipeline_run_id=pipeline_run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()


def test_watchlist_expand_threads_single_pipeline_anchor(
    isolated_cfg, monkeypatch,
):
    """Discriminating test: pipeline_run 100 + 101 exist at VM-build
    time (101 latest). Plant pipeline_run 102 between VM-build and the
    route's JIT call (simulated by mutating the helper). Assert the
    JIT chart bytes returned are from run_id 101 (the anchor the VM
    bound to), NOT run_id 102 (the now-latest).

    Pre-fix: the route would have used the JIT helper's internal
    ``latest_completed_pipeline_run`` re-resolve at request time —
    returning run_id 102's cache bytes. Post-fix: route threads the
    VM's anchor explicitly.
    """
    cfg, cfg_path = isolated_cfg
    ticker = "UCTT"
    _seed_watchlist(cfg, ticker)
    _patch_price_cache(monkeypatch, ticker)

    # Plant runs 100 + 101 BEFORE request begins.
    run100 = _insert_completed_pipeline_run(
        cfg, finished_ts="2026-05-19T08:00:00Z",
        data_asof_date="2026-05-18", action_session_date="2026-05-19",
        lease_token="t-run100",
    )
    run101 = _insert_completed_pipeline_run(
        cfg, finished_ts="2026-05-20T08:00:00Z",
        data_asof_date="2026-05-19", action_session_date="2026-05-20",
        lease_token="t-run101",
    )
    assert run100 < run101

    # Plant chart_renders rows for runs 101 + 102 (run 102 planted via
    # the in-test injection below). Each run gets its OWN identifying
    # body so the post-response assertion can prove the correct anchor
    # was honored.
    _plant_chart_render(
        cfg, ticker=ticker, surface="ticker_detail",
        pipeline_run_id=run101, data_asof_date="2026-05-19",
        body=b"<svg>RUN_101_BYTES</svg>",
    )

    # Build the app + monkeypatch the routes module so that, AFTER
    # ``build_watchlist_expanded`` returns, but BEFORE the route's
    # ``_resolve_jit_chart_bytes`` call, a NEW pipeline_run lands +
    # gets its own ``ticker_detail`` chart row planted. This is the
    # GET/POST TOCTOU window simulation.
    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    original_build = routes_mod.build_watchlist_expanded

    def _build_then_plant_run102(*args, **kwargs):
        vm = original_build(*args, **kwargs)
        # Between VM-build and JIT-call: plant run 102 + its chart row.
        run102 = _insert_completed_pipeline_run(
            cfg, finished_ts="2026-05-20T09:00:00Z",
            data_asof_date="2026-05-19",
            action_session_date="2026-05-20", lease_token="t-run102",
        )
        _plant_chart_render(
            cfg, ticker=ticker, surface="ticker_detail",
            pipeline_run_id=run102, data_asof_date="2026-05-19",
            body=b"<svg>RUN_102_BYTES</svg>",
        )
        return vm

    monkeypatch.setattr(
        routes_mod, "build_watchlist_expanded", _build_then_plant_run102,
    )

    with TestClient(app) as client:
        resp = client.get(f"/watchlist/{ticker}/expand")

    assert resp.status_code == 200
    # Post-fix discriminating assertion: the response carries the
    # run 101 SVG (the anchor the VM bound to), NOT run 102's SVG.
    assert b"RUN_101_BYTES" in resp.content, (
        "Codex R1 Major #1: /watchlist/{ticker}/expand must thread the "
        "VM's resolved pipeline_run anchor through to the JIT chart "
        "lookup, NOT re-resolve the latest_completed_pipeline_run at "
        "JIT-call time (mixed-anchor risk)"
    )
    assert b"RUN_102_BYTES" not in resp.content, (
        "Codex R1 Major #1: JIT chart bytes returned MUST NOT come from "
        "a newer pipeline_run that landed between VM-build and JIT-call"
    )
