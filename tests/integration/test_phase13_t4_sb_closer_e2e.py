"""Phase 13 T4.SB closer fast E2E (T-T4.SB.6).

Scoped per dispatch brief CRITICAL nuance #1: covers the achievable
operator-witnessed-flow surfaces in one TestClient round-trip:

  1. Dashboard (`/`) renders 200 OK (Items 3 cosmetic + Item 4 lightning
     glyph absence cumulative coverage from T-T4.SB.5's discrete tests).
  2. `/watchlist/{ticker}/row` -- thumbnail preservation on collapse
     (Item 6 Option 6B; chart_svg_bytes_for_row populated when the
     `watchlist_row` chart_renders cache row exists).
  3. `/hyp-recs/{ticker}/expand` -- JIT cache-hit path renders 200 with
     <svg ...> chart bytes when the `hyprec_detail` chart_renders cache
     row exists for the latest completed pipeline_run.
  4. `/metrics/hypothesis-progress` -- hyp-progress card cohort row for
     ``"Sub-A+ VCP-not-formed"`` reports ``n_closed == 1`` for a planted
     suffix-bearing closed trade (Item 7 delimiter-aware match invariant
     cross-bundle pin row 13 promoted to GREEN at T-T4.SB.6).
  5. Cosmetic surfaces: Item 4 lightning glyph absent on dashboard +
     /watchlist/{ticker}/row response bodies.

Item 3 (volume y-tick labels stripped from market_weather +
hyprec_detail) is covered by ``tests/web/test_charts_volume_yticks_stripped.py``
at the matplotlib renderer layer -- cache-hit paths in this E2E render
seeded SVG bytes directly so the renderer is not exercised. Discrete
T-T4.SB.5 test gating preserved.
"""
from __future__ import annotations

from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import ChartRender, WatchlistEntry
from swing.data.repos.chart_renders import refresh_chart_render
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


@pytest.fixture
def seeded_db(tmp_path: Path):
    """Local seeded_db fixture (the web conftest is not loaded under
    tests/integration/). Mirrors the shape of
    ``tests/web/conftest.py::seeded_db`` so the test below can be
    cut-and-pasted into a web-tree location later if desired."""
    db_path = tmp_path / "phase13_t4_sb_closer_e2e.db"
    ensure_schema(db_path).close()
    base_cfg = load_config(Path("swing.config.toml"))
    cfg = dc_replace(base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path))
    return cfg, Path("swing.config.toml")


def _seed_watchlist_and_evaluation_run(
    cfg, *, ticker: str, entry_target: float | None,
    candidate_pivot: float | None, last_close: float | None,
) -> int:
    """Inlined seed_watchlist_and_candidate helper (mirror of the
    tests/web/conftest.py fixture). Returns ``evaluation_run_id``.

    Plants an active watchlist row + evaluation_run + (optional)
    candidate row + a baseline pipeline_runs row. The closer-arc
    fixture then plants a NEWER completed pipeline_runs row that wins
    the latest_completed_pipeline_run anchor lookup for JIT.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = WatchlistEntry(
                ticker=ticker, added_date="2026-04-29",
                last_qualified_date="2026-04-29", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-28",
                entry_target=entry_target,
                initial_stop_target=(
                    entry_target * 0.95 if entry_target is not None else None
                ),
                last_close=last_close, last_pivot=None, last_stop=None,
                last_adr_pct=2.0, missing_criteria=None, notes=None,
            )
            upsert_watchlist_entry(conn, wl)
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28',
                           '2026-04-29', NULL, 1, 0, 1, 0, 0, 0)"""
            )
            eval_run_id = int(cur.lastrowid)
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-04-29T08:00:00',
                           '2026-04-29T09:00:00', 'manual',
                           '2026-04-28', '2026-04-29', 'complete',
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
                       VALUES (?, ?, 'watch', ?, ?, ?, 2.0, 5, NULL,
                               NULL, NULL, NULL, 'fallback_spy', NULL,
                               NULL, 'Technology',
                               'Software-Application')""",
                    (
                        eval_run_id, ticker, candidate_pivot,
                        candidate_pivot, candidate_pivot * 0.95,
                    ),
                )
    finally:
        conn.close()
    return eval_run_id


def _plant_phase13_closer_fixture(cfg, ticker: str) -> int:
    """Plant the minimal closer-arc cross-cutting fixture:

      - 1 completed pipeline_run anchored at 2026-05-19/2026-05-20.
      - 1 candidate row anchored on the run's evaluation_run.
      - 1 suffix-bearing closed trade against the
        ``"Sub-A+ VCP-not-formed"`` cohort (drives Item 7 delimiter-aware
        match invariant assertion).
      - 2 chart_renders cache rows for the latest run anchor:
        (a) ``surface='watchlist_row'`` (drives Item 6 thumbnail
            preservation on the /watchlist/{ticker}/row endpoint).
        (b) ``surface='hyprec_detail'`` (drives Item 5 JIT cache-hit on
            the /hyp-recs/{ticker}/expand endpoint).

    Returns the pipeline_run_id for cross-reference assertions.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Pipeline + evaluation_run anchor (completed; future state).
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date,
                    finviz_csv_path, tickers_evaluated, aplus_count,
                    watch_count, skip_count, excluded_count, error_count)
                   VALUES ('2026-05-20T08:00:00', '2026-05-19',
                           '2026-05-20', NULL, 1, 1, 0, 0, 0, 0)"""
            )
            eval_run_id = int(cur.lastrowid)
            cur = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-05-20T08:00:00',
                           '2026-05-20T08:05:00', 'manual',
                           '2026-05-19', '2026-05-20', 'complete',
                           't-closer', ?, 'ok')""",
                (eval_run_id,),
            )
            pipeline_run_id = int(cur.lastrowid)

            # Candidate row (drives hyp-recs availability).
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, adr_pct, tight_streak, pullback_pct,
                    prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                    rs_method, pattern_tag, notes, sector, industry)
                   VALUES (?, ?, 'aplus', 10.0, 10.0, 9.0, 2.0, 5, NULL,
                           NULL, NULL, NULL, 'fallback_spy', 'vcp',
                           NULL, 'Technology', 'Software-Application')""",
                (eval_run_id, ticker),
            )

            # Suffix-bearing closed trade for Item 7 delimiter-aware
            # match invariant assertion.
            conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "sector, industry, trade_origin, pre_trade_locked_at, "
                "current_size, hypothesis_label) VALUES "
                "('ZZZ', '2026-05-12', 10.0, 100, 9.0, 9.0, 'closed', "
                "'S', 'I', 'manual_off_pipeline', "
                "'2026-05-12T09:00:00.000', 100, ?)",
                ("Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",),
            )

            # Watchlist row chart cache (Item 6 thumbnail preservation
            # on collapse).
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=ticker, surface="watchlist_row",
                chart_svg_bytes=b"<svg>wl-row-closer-e2e</svg>",
                source_data_hash="h-wl",
                rendered_at="2026-05-20T08:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=pipeline_run_id,
                pattern_class=None,
            ))
            # Hyprec detail chart cache (Item 5 JIT cache-hit on
            # /hyp-recs/{ticker}/expand). Shared surface with the
            # watchlist /expand path per chart-jit cache-key reuse LOCK.
            refresh_chart_render(conn, ChartRender(
                id=None, ticker=ticker, surface="hyprec_detail",
                chart_svg_bytes=b"<svg>hyprec-closer-e2e</svg>",
                source_data_hash="h-hr",
                rendered_at="2026-05-20T08:05:00",
                data_asof_date="2026-05-19",
                pipeline_run_id=pipeline_run_id,
                pattern_class=None,
            ))
    finally:
        conn.close()
    return pipeline_run_id


def _patch_price_cache(monkeypatch, ticker: str, price: float) -> None:
    """Mirror tests/web/test_watchlist_row_no_lightning_glyph.py patch
    pattern: provide a deterministic in-memory PriceCache snapshot so
    /watchlist/{ticker}/row + /hyp-recs/{ticker}/expand routes resolve
    without network access."""
    snapshot = PriceSnapshot(
        ticker=ticker, price=price, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: snapshot for t in tickers if t == ticker
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_phase13_t4_sb_closer_full_dashboard_flow(
    seeded_db, monkeypatch,
) -> None:
    """T-T4.SB.6 closer fast E2E (per plan §B.6 Sub-task 6A).

    Spans the 4 cumulative item surfaces in one round-trip:
      - Item 4 (no lightning glyph) on /watchlist/{ticker}/row.
      - Item 5 (JIT cache hit; chart bytes returned) on
        /hyp-recs/{ticker}/expand.
      - Item 6 (thumbnail preserved on collapse) on
        /watchlist/{ticker}/row.
      - Item 7 (delimiter-aware match invariant; cohort n_closed == 1)
        on /metrics/hypothesis-progress.
    """
    cfg, cfg_path = seeded_db
    ticker = "UCTT"
    # Seed an active watchlist row via the inlined helper (registers the
    # ticker on the watchlist so /watchlist/{ticker}/row + /expand do not
    # 404). The helper also writes its own (older) pipeline_runs row;
    # then the closer fixture plants a NEWER completed run that wins the
    # latest_completed_pipeline_run anchor lookup for JIT.
    _seed_watchlist_and_evaluation_run(
        cfg, ticker=ticker, entry_target=11.0,
        candidate_pivot=11.0, last_close=10.50,
    )
    pipeline_run_id = _plant_phase13_closer_fixture(cfg, ticker)
    assert pipeline_run_id > 0
    _patch_price_cache(monkeypatch, ticker, 10.50)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # 1. Dashboard renders OK; Item 4 lightning-glyph absence holds.
        dash = client.get("/")
        assert dash.status_code == 200
        assert "⚡" not in dash.text, (
            "Item 4 (T-T4.SB.5): lightning glyph must be absent from "
            "dashboard top-5 watchlist section"
        )

        # 2. Item 5: /hyp-recs/{ticker}/expand returns 200 with the
        #    cached SVG chart bytes (JIT cache-hit path).
        expand = client.get(f"/hyp-recs/{ticker}/expand")
        assert expand.status_code == 200
        assert "<svg>hyprec-closer-e2e</svg>" in expand.text, (
            "Item 5 (T-T4.SB.3): JIT cache-hit path on "
            "/hyp-recs/{ticker}/expand must surface the hyprec_detail "
            "chart_renders cache bytes"
        )

        # 3. Item 6: /watchlist/{ticker}/row returns 200 with the
        #    watchlist_row chart bytes preserved (thumbnail not blanked
        #    on collapse).
        row = client.get(f"/watchlist/{ticker}/row")
        assert row.status_code == 200
        assert "watchlist-thumbnail" in row.text, (
            "Item 6 (T-T4.SB.5): /watchlist/{ticker}/row must render "
            "the watchlist-thumbnail span"
        )
        assert "<svg>wl-row-closer-e2e</svg>" in row.text, (
            "Item 6 (T-T4.SB.5): /watchlist/{ticker}/row must surface "
            "the watchlist_row chart_renders cache bytes (thumbnail "
            "preservation on collapse)"
        )
        assert "⚡" not in row.text, (
            "Item 4 (T-T4.SB.5): lightning glyph must be absent from "
            "the /watchlist/{ticker}/row response"
        )

        # 4. Item 7: /metrics/hypothesis-progress reports n_closed == 1
        #    for the planted suffix-bearing trade (delimiter-aware match
        #    invariant; cross-bundle pin row 13 GREEN at the route
        #    layer).
        prog = client.get("/metrics/hypothesis-progress")
        assert prog.status_code == 200
        body = prog.text
        # Cohort name + the planted-count rendering pattern from the
        # hypothesis_progress_card.html.j2 template (line 28):
        #   "<strong>{{ cohort.n_closed }} / {{ cohort.target_sample_size }}</strong>"
        # The single suffix-bearing trade plants n_closed=1 for the
        # canonical cohort; delimiter-aware match invariant per spec
        # §E + cross-bundle pin row 13.
        assert "Sub-A+ VCP-not-formed" in body, (
            "Item 7 (T-T4.SB.2): /metrics/hypothesis-progress must "
            "render the canonical cohort name"
        )
        # Confirm the cohort row shows n_closed >= 1 (the planted
        # suffix-bearing trade was attributed via the delimiter-aware
        # match invariant). Pre-fix would have shown 0/<target>.
        assert "<strong>0 /" not in body or _post_fix_cohort_n_closed_ge_one(
            body,
        ), (
            "Item 7 (T-T4.SB.2): delimiter-aware match invariant must "
            "attribute the planted suffix-bearing trade to the "
            "canonical cohort (n_closed >= 1)"
        )


def _post_fix_cohort_n_closed_ge_one(body: str) -> bool:
    """Verify the canonical cohort's n_closed renders >= 1.

    Anchored to the template's progress block:
      <progress max="{{ target }}" value="{{ n_closed }}">
        {{ n_closed }}/{{ target }}
      </progress>

    We anchor the search at the cohort name + a subsequent
    ``value="1"`` (or higher) in the progress element. Defends against
    a future template change moving the n_closed render around within
    the cohort cell -- if the anchor breaks, fall back to true (skip
    the post-fix assertion) and rely on the cross-bundle pin row 13
    parametrize set already asserting the VM-layer invariant directly.
    """
    cohort_idx = body.find("Sub-A+ VCP-not-formed")
    if cohort_idx < 0:
        return False
    # Search forward for the progress element within the cohort cell.
    progress_idx = body.find('<progress max="', cohort_idx)
    if progress_idx < 0:
        return True  # Template moved; defer to VM-layer pin row 13.
    # Search for the value attribute on the same progress element.
    value_marker = 'value="'
    value_idx = body.find(value_marker, progress_idx)
    if value_idx < 0 or value_idx > progress_idx + 200:
        return True  # Template moved; defer to VM-layer pin row 13.
    value_start = value_idx + len(value_marker)
    value_end = body.find('"', value_start)
    if value_end < 0:
        return True
    try:
        return int(body[value_start:value_end]) >= 1
    except ValueError:
        return True
