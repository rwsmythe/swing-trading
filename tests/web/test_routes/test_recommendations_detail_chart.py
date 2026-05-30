"""Phase 13 T2.SB6c task T-A.6c.2 — Gap A.1 ticker detail chart wiring.

Per plan §G.2 step 1a (3 tests covering Gap A.1):
  - VM field populated from chart_renders cache (surface='ticker_detail').
  - Template renders the inline SVG bytes when present.
  - Cache-miss leaves the field None + template renders nothing.

The hyp-rec "detail" page in V1 is the expanded inline row at
`partials/hypothesis_recommendations_expanded.html.j2` rendered by
`GET /hyp-recs/{ticker}/expand`. The expansion is bound to the latest
completed pipeline run; the cache key is keyed on that run_id.

Per L7 LOCK (T2.SB6a substrate API FROZEN): tests reuse
`refresh_chart_render` + the ChartRender semantic validator verbatim; no
substrate modification.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.app import create_app


def _seed_complete_run_with_eval(conn) -> tuple[int, int]:
    """Insert an evaluation_run + completed pipeline_run + candidate row.

    Returns (pipeline_run_id, evaluation_run_id). The candidate row carries
    a non-NULL pivot + initial_stop so `build_hyp_recs_expanded` returns a
    populated VM rather than the 404 unavailable path.
    """
    cur = conn.execute(
        """
        INSERT INTO evaluation_runs
            (run_ts, data_asof_date, action_session_date, finviz_csv_path,
             tickers_evaluated, aplus_count, watch_count, skip_count,
             excluded_count, error_count)
        VALUES ('2026-05-22T09:00:00', '2026-05-21', '2026-05-22', NULL,
                1, 1, 0, 0, 0, 0)
        """
    )
    eval_run_id = int(cur.lastrowid)
    cur = conn.execute(
        """
        INSERT INTO pipeline_runs
            (started_ts, finished_ts, trigger, data_asof_date,
             action_session_date, state, lease_token, evaluation_run_id,
             charts_status)
        VALUES ('2026-05-22T08:00:00', '2026-05-22T09:00:00', 'manual',
                '2026-05-21', '2026-05-22', 'complete', 't-hyp', ?, 'ok')
        """,
        (eval_run_id,),
    )
    pipeline_run_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO candidates
            (evaluation_run_id, ticker, bucket, close, pivot, initial_stop,
             adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank,
             rs_return_12w_vs_spy, rs_method, pattern_tag, notes,
             sector, industry)
        VALUES (?, 'HYP', 'aplus', 100.0, 100.0, 95.0, 2.0, 5,
                NULL, NULL, NULL, NULL, 'fallback_spy', NULL, NULL,
                'Technology', 'Software-Application')
        """,
        (eval_run_id,),
    )
    return pipeline_run_id, eval_run_id


def test_ticker_detail_template_renders_inline_chart_svg_when_cache_hit(
    seeded_db,
):
    """Gap A.1 — operator-facing expansion partial renders inline SVG bytes
    pulled from chart_renders (surface='ticker_detail', run-bound key)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id, _ = _seed_complete_run_with_eval(conn)
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="HYP", surface="ticker_detail",
                chart_svg_bytes=b"<svg>hyprec-cached</svg>",
                source_data_hash="h",
                rendered_at="2026-05-22T09:00:00",
                data_asof_date="2026-05-21",
                pipeline_run_id=run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/hyp-recs/HYP/expand")
    assert r.status_code == 200
    assert "<svg>hyprec-cached</svg>" in r.text


def test_ticker_detail_template_omits_chart_when_cache_miss(seeded_db):
    """Gap A.1 — cache-miss leaves the chart field None; template emits no
    raw bytes (operator-facing page still renders 200 + the order params)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            _seed_complete_run_with_eval(conn)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/hyp-recs/HYP/expand")
    assert r.status_code == 200
    # Order-parameters block still rendered (non-chart content unchanged).
    assert "Order parameters" in r.text
    # No leaked SVG marker from the cache row (none exists).
    assert "<svg>hyprec-cached</svg>" not in r.text


def test_ticker_detail_vm_populates_chart_svg_bytes_from_cache(seeded_db):
    """Gap A.1 — `HypRecsExpandedVM` carries the cached bytes via a new
    `ticker_detail_chart_svg_bytes` field; the route handler threads the
    `conn` + `pipeline_run_id` so the builder can consult the substrate.
    """
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            run_id, _ = _seed_complete_run_with_eval(conn)
            refresh_chart_render(conn, ChartRender(
                id=None, ticker="HYP", surface="ticker_detail",
                chart_svg_bytes=b"<svg>hyprec-vm</svg>",
                source_data_hash="h",
                rendered_at="2026-05-22T09:00:00",
                data_asof_date="2026-05-21",
                pipeline_run_id=run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()
    # Build the VM directly so we can assert the new field's wiring.
    from swing.web.view_models.dashboard import build_hyp_recs_expanded
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            vm = build_hyp_recs_expanded(
                conn, cfg, ticker="HYP", current_balance=10_000.0,
            )
    finally:
        conn.close()
    assert vm is not None
    assert getattr(vm, "ticker_detail_chart_svg_bytes", None) == (
        b"<svg>hyprec-vm</svg>"
    )
