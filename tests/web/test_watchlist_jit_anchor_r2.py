"""Phase 13 T4.SB Codex R2 regressions extending R1.M1 pipeline-anchor race fix.

Three findings:

- R2 MAJOR #1: /expand still has the no-run-to-new-run mixed-anchor race.
  When the VM is built with no completed pipeline_run (`pipeline_run_id=None`,
  `data_asof_date=None`), the helper's both-None fallback re-resolves to
  `latest_completed_pipeline_run` — so a pipeline completing between
  VM-build and JIT-call attaches new-run chart bytes to a VM whose
  `chart_reason="no-run"` banner is already in flight. Mixed anchors.

- R2 MAJOR #2: /row has the same race as the pre-R1.M1 /expand race. The
  row's metadata (classification tags, current pivot) IS resolved against a
  bound `latest_completed_pipeline_run` inside `build_watchlist_row`, but
  the route's JIT call resolves its own latest a moment later. A pipeline
  completing in between → row metadata from run N + thumbnail bytes from
  run N+1.

- R2 MINOR #1: Partial anchor (one of `pipeline_run_id` / `data_asof_date`
  supplied, the other None) silently falls back to latest. Should refuse
  + WARN-log (call-site bug masking).
"""
from __future__ import annotations

import logging
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

    db_path = tmp_path / "phase13_t4_sb_r2_anchor.db"
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
                source_data_hash="t-anchor-r2",
                rendered_at="2026-05-20T08:05:00Z",
                data_asof_date=data_asof_date,
                pipeline_run_id=pipeline_run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# R2.M1 — /expand no-run-to-new-run mixed-anchor race
# ---------------------------------------------------------------------------


def test_watchlist_expand_no_run_does_not_pick_up_mid_request_pipeline(
    isolated_cfg, monkeypatch,
):
    """R2 MAJOR #1: when VM is built with NO completed pipeline_run
    (`pipeline_run_id=None`, `data_asof_date=None`, chart_reason='no-run'),
    a pipeline_run completing mid-request MUST NOT attach JIT chart bytes
    to the response. The unavailable banner cascade is the VM's contract;
    the route must NOT silently override it with bytes from a newer
    anchor.

    Pre-fix: `_resolve_jit_chart_bytes` falls back to
    `latest_completed_pipeline_run` when BOTH pipeline_run_id and
    data_asof_date are None, picking up the mid-request run and rendering
    a chart whose VM reports chart_reason='no-run'.

    Post-fix: the route signals "VM has no anchor — do not fall back" and
    the helper skips JIT entirely; response carries the VM's
    chart-unavailable banner verbatim with no chart bytes.
    """
    cfg, cfg_path = isolated_cfg
    ticker = "UCTT"
    _seed_watchlist(cfg, ticker)
    _patch_price_cache(monkeypatch, ticker)

    # NO pipeline_runs at all at VM-build time → VM's pipeline_run_id=None.
    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    original_build = routes_mod.build_watchlist_expanded

    def _build_then_plant_run100(*args, **kwargs):
        vm = original_build(*args, **kwargs)
        # Sanity: pre-fix invariant — VM had NO anchor at build time.
        assert vm.pipeline_run_id is None
        assert vm.data_asof_date is None
        assert vm.chart_reason == "no-run"
        # Between VM-build and JIT-call: a pipeline completes.
        run100 = _insert_completed_pipeline_run(
            cfg, finished_ts="2026-05-20T09:00:00Z",
            data_asof_date="2026-05-19",
            action_session_date="2026-05-20", lease_token="t-run100",
        )
        _plant_chart_render(
            cfg, ticker=ticker, surface="hyprec_detail",
            pipeline_run_id=run100, data_asof_date="2026-05-19",
            body=b"<svg>RUN_100_LATE_BYTES</svg>",
        )
        return vm

    monkeypatch.setattr(
        routes_mod, "build_watchlist_expanded", _build_then_plant_run100,
    )

    with TestClient(app) as client:
        resp = client.get(f"/watchlist/{ticker}/expand")

    assert resp.status_code == 200
    # Post-fix: the late-landing run's chart bytes MUST NOT appear in
    # the response. The VM's chart_reason='no-run' banner is the
    # authoritative content.
    assert b"RUN_100_LATE_BYTES" not in resp.content, (
        "Codex R2 MAJOR #1: /expand MUST NOT fall back to "
        "latest_completed_pipeline_run when VM bound to no-run state. "
        "Mixed-anchor risk: VM banner says no-run, but JIT painted bytes "
        "from a mid-request pipeline_run."
    )


# ---------------------------------------------------------------------------
# R2.M2 — /row race
# ---------------------------------------------------------------------------


def test_watchlist_row_threads_single_pipeline_anchor(
    isolated_cfg, monkeypatch,
):
    """R2 MAJOR #2: /row response must thread VM-pinned anchor through to
    the JIT chart lookup.

    Plant pipeline_run 100 + a planted hyprec_detail-style row chart for
    it. Build the VM (binds to run 100). Plant pipeline_run 101 + a chart
    for it between VM-build and JIT-call. Assert the response carries
    run 100's chart bytes (the VM's anchor), NOT run 101's.
    """
    cfg, cfg_path = isolated_cfg
    ticker = "UCTT"
    _seed_watchlist(cfg, ticker)
    _patch_price_cache(monkeypatch, ticker)

    # Plant run 100 before request begins.
    run100 = _insert_completed_pipeline_run(
        cfg, finished_ts="2026-05-20T08:00:00Z",
        data_asof_date="2026-05-19", action_session_date="2026-05-20",
        lease_token="t-row-run100",
    )
    _plant_chart_render(
        cfg, ticker=ticker, surface="watchlist_row",
        pipeline_run_id=run100, data_asof_date="2026-05-19",
        body=b"<svg>ROW_RUN_100_BYTES</svg>",
    )

    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    original_build = routes_mod.build_watchlist_row

    def _build_row_then_plant_run101(*args, **kwargs):
        vm = original_build(*args, **kwargs)
        # Sanity: VM bound to run 100 (the latest at build time).
        assert vm is not None
        assert vm.pipeline_run_id == run100
        # Between VM-build and JIT-call: run 101 lands + chart row planted.
        run101 = _insert_completed_pipeline_run(
            cfg, finished_ts="2026-05-20T09:00:00Z",
            data_asof_date="2026-05-19",
            action_session_date="2026-05-20", lease_token="t-row-run101",
        )
        _plant_chart_render(
            cfg, ticker=ticker, surface="watchlist_row",
            pipeline_run_id=run101, data_asof_date="2026-05-19",
            body=b"<svg>ROW_RUN_101_BYTES</svg>",
        )
        return vm

    monkeypatch.setattr(
        routes_mod, "build_watchlist_row", _build_row_then_plant_run101,
    )

    with TestClient(app) as client:
        resp = client.get(f"/watchlist/{ticker}/row")

    assert resp.status_code == 200
    assert b"ROW_RUN_100_BYTES" in resp.content, (
        "Codex R2 MAJOR #2: /watchlist/{ticker}/row must thread the "
        "VM-bound pipeline_run anchor through to the JIT chart lookup. "
        "Row metadata + thumbnail must share one anchor."
    )
    assert b"ROW_RUN_101_BYTES" not in resp.content, (
        "Codex R2 MAJOR #2: /row JIT bytes MUST NOT come from a "
        "pipeline_run that landed between VM-build and JIT-call."
    )


def test_watchlist_row_no_run_does_not_pick_up_mid_request_pipeline(
    isolated_cfg, monkeypatch,
):
    """R2 MAJOR #2 (no-run variant): /row VM built with no completed
    pipeline run; mid-request run landing MUST NOT attach JIT bytes.
    Symmetric with the R2.M1 /expand no-run variant.
    """
    cfg, cfg_path = isolated_cfg
    ticker = "UCTT"
    _seed_watchlist(cfg, ticker)
    _patch_price_cache(monkeypatch, ticker)

    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    original_build = routes_mod.build_watchlist_row

    def _build_row_then_plant_run100(*args, **kwargs):
        vm = original_build(*args, **kwargs)
        assert vm is not None
        # No pipeline run existed at VM-build time → no anchor.
        assert vm.pipeline_run_id is None
        run100 = _insert_completed_pipeline_run(
            cfg, finished_ts="2026-05-20T09:00:00Z",
            data_asof_date="2026-05-19",
            action_session_date="2026-05-20", lease_token="t-row-no-run100",
        )
        _plant_chart_render(
            cfg, ticker=ticker, surface="watchlist_row",
            pipeline_run_id=run100, data_asof_date="2026-05-19",
            body=b"<svg>ROW_LATE_RUN_100_BYTES</svg>",
        )
        return vm

    monkeypatch.setattr(
        routes_mod, "build_watchlist_row", _build_row_then_plant_run100,
    )

    with TestClient(app) as client:
        resp = client.get(f"/watchlist/{ticker}/row")

    assert resp.status_code == 200
    assert b"ROW_LATE_RUN_100_BYTES" not in resp.content, (
        "Codex R2 MAJOR #2 (no-run variant): /row MUST NOT fall back to "
        "latest_completed_pipeline_run when VM bound to no-run state."
    )


# ---------------------------------------------------------------------------
# R2.m1 — partial anchor refuses to fall back
# ---------------------------------------------------------------------------


def test_resolve_jit_chart_bytes_partial_anchor_returns_none_and_warns(
    isolated_cfg, monkeypatch, caplog,
):
    """R2 MINOR #1: partial anchor (one of pipeline_run_id /
    data_asof_date supplied, the other None) → return None + WARN log.
    Silent fallback masks call-site bugs; explicit refusal surfaces them.
    """
    cfg, cfg_path = isolated_cfg
    _seed_watchlist(cfg, "UCTT")
    _patch_price_cache(monkeypatch, "UCTT")

    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    class _StubRequest:
        def __init__(self, app):
            self.app = app

    with TestClient(app):
        # Use TestClient context just so app.state is initialized
        # (lifespan-managed price_fetch_executor, ohlcv_cache, etc.).
        req = _StubRequest(app)
        with caplog.at_level(logging.WARNING, logger="swing.web.routes.watchlist"):
            # Case A: pipeline_run_id supplied, data_asof_date None.
            result_a = routes_mod._resolve_jit_chart_bytes(
                req, ticker="UCTT", surface="watchlist_row",
                pipeline_run_id=42, data_asof_date=None,
                ma_lines=[20, 50],
                resolve_latest_if_missing=True,
            )
            assert result_a is None
            # Case B: data_asof_date supplied, pipeline_run_id None.
            result_b = routes_mod._resolve_jit_chart_bytes(
                req, ticker="UCTT", surface="watchlist_row",
                pipeline_run_id=None, data_asof_date="2026-05-19",
                ma_lines=[20, 50],
                resolve_latest_if_missing=True,
            )
            assert result_b is None

    # Both partial-anchor cases logged WARNING.
    partial_warnings = [
        r for r in caplog.records
        if "partial anchor" in r.getMessage().lower()
    ]
    assert len(partial_warnings) >= 2, (
        "R2 MINOR #1: partial-anchor cases must each emit a WARNING. "
        f"Got: {[r.getMessage() for r in caplog.records]}"
    )


def test_resolve_jit_chart_bytes_explicit_no_anchor_skip(
    isolated_cfg, monkeypatch,
):
    """R2 MINOR #1 + MAJOR #1 helper contract: caller signals
    `resolve_latest_if_missing=False` + supplies both None → return None.
    Even if a pipeline_run exists in the DB, the helper does NOT
    re-resolve (preserves the caller's "no anchor" contract).
    """
    cfg, cfg_path = isolated_cfg

    # Plant a completed pipeline run that the helper would otherwise
    # fall back to.
    _insert_completed_pipeline_run(
        cfg, finished_ts="2026-05-20T08:00:00Z",
        data_asof_date="2026-05-19", action_session_date="2026-05-20",
        lease_token="t-explicit-skip",
    )

    app = create_app(cfg, cfg_path)

    import swing.web.routes.watchlist as routes_mod

    class _StubRequest:
        def __init__(self, app):
            self.app = app

    with TestClient(app):
        req = _StubRequest(app)
        result = routes_mod._resolve_jit_chart_bytes(
            req, ticker="UCTT", surface="watchlist_row",
            pipeline_run_id=None, data_asof_date=None,
            ma_lines=[20, 50],
            resolve_latest_if_missing=False,
        )
    assert result is None
