"""WatchlistVM shape + expand helper."""
from __future__ import annotations

from unittest.mock import MagicMock

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_watchlist_shape(seeded_db, monkeypatch):
    from swing.web.view_models.watchlist import WatchlistVM, build_watchlist
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.5, asof=datetime.now(),
                                   is_stale=False, source="live")
        })
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_watchlist(cfg=cfg, cache=cache, executor=None)
    assert isinstance(vm, WatchlistVM)
    assert len(vm.rows) == 1
    assert vm.rows[0].ticker == "AAPL"


# -----------------------------------------------------------------------------
# Chart-unavailable reason plumbing — Tranche B-ops spec §4 (Bug 4).
# -----------------------------------------------------------------------------

def _seed_completed_pipeline_run(cfg, *, data_asof: str, charts_status: str):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status)
                   VALUES ('2026-04-17T21:00:00', '2026-04-17T21:55:00',
                           'manual', ?, ?, 'complete', 't', ?)""",
                (data_asof, data_asof, charts_status),
            )
    finally:
        conn.close()


def test_build_watchlist_expanded_carries_chart_reason_no_run(seeded_db, monkeypatch):
    """No pipeline run yet → chart_reason='no-run' with friendly message."""
    from swing.web.view_models.watchlist import build_watchlist_expanded
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})

    expanded = build_watchlist_expanded(
        cfg=cfg, cache=cache, ticker="AAPL", executor=None,
    )
    assert expanded is not None
    assert expanded.chart_reason == "no-run"
    assert "no pipeline run" in expanded.chart_reason_message
    # No completed pipeline run → no chart-URL date.
    assert expanded.data_asof_date is None


def test_build_watchlist_expanded_reports_insufficient_data(seeded_db, monkeypatch):
    """Pipeline ran ok, ticker is in A+, but PNG is missing."""
    from swing.web.view_models.watchlist import build_watchlist_expanded
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:30:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'hash')""",
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id,),
            )
    finally:
        conn.close()
    _seed_completed_pipeline_run(cfg, data_asof="2026-04-17", charts_status="ok")

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})

    expanded = build_watchlist_expanded(
        cfg=cfg, cache=cache, ticker="AAPL", executor=None,
    )
    assert expanded is not None
    assert expanded.chart_reason == "insufficient-data"
    assert expanded.data_asof_date == "2026-04-17"   # from pipeline run, not eval


def test_watchlist_expanded_template_renders_reason_message(seeded_db, monkeypatch):
    """GET /watchlist/AAPL/expand renders the chart-unavailable reason in place
    of the chart image when chart_reason is set."""
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand")
    assert r.status_code == 200
    body = r.text
    # No pipeline run exists → no-run state.
    assert 'class="chart-unavailable"' in body
    assert 'data-chart-reason="no-run"' in body
    assert "no pipeline run yet" in body
    # The old onerror-based fallback is gone.
    assert "onerror=" not in body
    # Since chart is unavailable, there must be NO <img src="/charts/ tag.
    assert '<img src="/charts/' not in body


def test_build_watchlist_expanded_criteria_not_bound_to_unrelated_eval(
    seeded_db, monkeypatch,
):
    """Adversarial-review Round 4: when a pipeline exists but the
    eval-linkage heuristic (data_asof_date + run_ts <= finished_ts) misses,
    the criteria panel must NOT silently fall back to the latest eval — that
    would recreate the mixed-anchor bug where a post-pipeline standalone
    `swing eval` seeds the criteria with data the pipeline did not chart.

    Setup: pipeline ran for data_asof=2026-04-16 with no eval matching that
    date + finish time. A later standalone eval for 2026-04-17 exists.
    Expected: `candidate` is None (NOT populated from the 04-17 eval).
    """
    from swing.web.view_models.watchlist import build_watchlist_expanded
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            # Completed pipeline with data_asof=2026-04-16, finished 16:00.
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token, charts_status)
                   VALUES ('2026-04-16T15:00:00', '2026-04-16T16:00:00',
                           'manual', '2026-04-16', '2026-04-17',
                           'complete', 'tok1', 'ok')""",
            )
            # A later standalone eval for a DIFFERENT data_asof_date — the
            # linkage heuristic should NOT match (data_asof != pipeline's).
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T10:00:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'hash')""",
            )
            standalone_eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (standalone_eval_id,),
            )
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})

    expanded = build_watchlist_expanded(
        cfg=cfg, cache=cache, ticker="AAPL", executor=None,
    )
    assert expanded is not None
    assert expanded.candidate is None, (
        "criteria panel must NOT bind to the standalone 04-17 eval when the "
        "pipeline ran for 04-16 — that's the mixed-anchor regression"
    )
    # Chart binds to the pipeline's own data_asof_date.
    assert expanded.data_asof_date == "2026-04-16"


def test_watchlist_expanded_template_renders_pipeline_failed_reason(
    seeded_db, monkeypatch,
):
    """Adversarial-review Round 1 Minor 2: template-level coverage was only
    exercising no-run + available. This verifies a distinct non-no-run
    unavailable state (`pipeline-failed`) survives VM plumbing and renders
    the correct placeholder branch with the right message + data attribute.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    # Completed pipeline run with charts_status='failed'.
    _seed_completed_pipeline_run(cfg, data_asof="2026-04-17", charts_status="failed")

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand")
    assert r.status_code == 200
    body = r.text
    assert 'data-chart-reason="pipeline-failed"' in body
    assert "chart step failed" in body.lower()
    assert '<img src="/charts/' not in body
    assert "onerror=" not in body


def test_build_watchlist_expanded_uses_binding_not_re_read(seeded_db, monkeypatch):
    """build_watchlist_expanded uses binding's data_asof_date AND the resolver
    answer that goes with it, NOT a re-read of pipeline_runs.

    Setup: same pattern as the open-positions caller test. Two completed
    runs; AAPL is in runN's chart_targets but NOT runN+1's. Watchlist has
    AAPL active. Monkeypatch
    `swing.web.view_models.watchlist.latest_completed_pipeline_run` to
    return runN's binding.

    Discriminating verification: pre-fix watchlist.py:243-260 did its own
    SELECT for `data_asof_date` AND the resolver re-read. Pre-fix
    data_asof would be runN+1's '2026-04-02' AND chart_reason would be
    'out-of-scope' (AAPL not in runN+1's targets). Post-fix: data_asof
    pinned to runN's '2026-04-01' AND chart_reason is None.
    """
    from concurrent.futures import ThreadPoolExecutor

    from swing.web.chart_scope import PipelineRunBinding
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.watchlist import build_watchlist_expanded

    cfg, _cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Eval runs first (FK-backed path).
            conn.execute(
                """INSERT INTO evaluation_runs (id, run_ts, data_asof_date,
                                                 action_session_date, finviz_csv_path,
                                                 tickers_evaluated, aplus_count,
                                                 watch_count, skip_count, excluded_count,
                                                 error_count, rs_universe_version,
                                                 rs_universe_hash)
                   VALUES (450, '2026-04-01T09:00:00', '2026-04-01', '2026-04-02', NULL,
                           1, 1, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO evaluation_runs (id, run_ts, data_asof_date,
                                                 action_session_date, finviz_csv_path,
                                                 tickers_evaluated, aplus_count,
                                                 watch_count, skip_count, excluded_count,
                                                 error_count, rs_universe_version,
                                                 rs_universe_hash)
                   VALUES (451, '2026-04-02T09:00:00', '2026-04-02', '2026-04-03', NULL,
                           1, 1, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            # Two runs, different dates; AAPL chart_target only in runN — eval id 450.
            conn.execute(
                """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                               data_asof_date, action_session_date,
                                               charts_status, evaluation_run_id,
                                               trigger, lease_token)
                   VALUES (400, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                           'complete', '2026-04-01', '2026-04-02', 'ok', 450,
                           'manual', 'tok-400')""",
            )
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (400, 'AAPL', 'tag_aware_top_n', 'ok')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                               data_asof_date, action_session_date,
                                               charts_status, evaluation_run_id,
                                               trigger, lease_token)
                   VALUES (401, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                           'complete', '2026-04-02', '2026-04-03', 'ok', 451,
                           'manual', 'tok-401')""",
            )
            # Active watchlist row for AAPL.
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-01",
                last_qualified_date="2026-04-01", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-01",
                entry_target=100.0, initial_stop_target=95.0,
                last_close=99.0, last_pivot=100.0, last_stop=95.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
        # PNG on disk for runN's date.
        (cfg.paths.charts_dir / "2026-04-01").mkdir(parents=True, exist_ok=True)
        (cfg.paths.charts_dir / "2026-04-01" / "AAPL.png").write_bytes(b"png-stub")
    finally:
        conn.close()

    runN_binding = PipelineRunBinding(
        run_id=400, finished_ts="2026-04-01T09:30:00",
        data_asof_date="2026-04-01", charts_status="ok",
        evaluation_run_id=450,
    )
    monkeypatch.setattr(
        "swing.web.view_models.watchlist.latest_completed_pipeline_run",
        lambda _conn: runN_binding,
    )

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {})

    with ThreadPoolExecutor(max_workers=1) as executor:
        vm = build_watchlist_expanded(
            cfg=cfg, cache=cache, ticker="AAPL", executor=executor,
        )

    assert vm is not None
    assert vm.data_asof_date == "2026-04-01", (
        f"expected runN's data_asof; got {vm.data_asof_date!r}; "
        "regression: builder did its own SELECT on pipeline_runs"
    )
    assert vm.chart_reason is None, (
        f"expected chart-available (binding=runN, AAPL in runN's targets); "
        f"got reason={vm.chart_reason!r}; "
        "regression: resolver re-read pipeline_runs and bound to runN+1"
    )


def test_watchlist_expanded_template_shows_img_when_chart_available(
    seeded_db, monkeypatch, tmp_path,
):
    """When resolver returns None (chart available), template renders <img>
    and no chart-unavailable div."""
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:30:00', '2026-04-17', '2026-04-20',
                           NULL, 1, 1, 0, 0, 0, 0, 'v1', 'hash')""",
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
                    rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id,),
            )
    finally:
        conn.close()
    _seed_completed_pipeline_run(cfg, data_asof="2026-04-17", charts_status="ok")
    # Write the PNG to the configured charts_dir.
    chart_path = cfg.paths.charts_dir / "2026-04-17" / "AAPL.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fake-png")

    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist/AAPL/expand")
    assert r.status_code == 200
    body = r.text
    assert '<img src="/charts/2026-04-17/AAPL.png"' in body
    assert 'class="chart-unavailable"' not in body
    assert "onerror=" not in body
