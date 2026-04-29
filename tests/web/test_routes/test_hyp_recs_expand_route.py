"""GET /hyp-recs/refresh + /hyp-recs/{ticker}/expand route tests.

Tasks 4 + 5 + 6 + 7 + 8 + 9 contribute. Task 4 seeds refresh-route
tests; subsequent tasks extend.

Spec §3.5.4 + §4.6 (R2-Major-2 scoped refresh builder).
Spec §3.5.3 + §3.5.4 + §4.3 (expand route).
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _patch_price_cache(monkeypatch):
    """Stub PriceCache.get_many so the route doesn't try to fetch prices."""

    def get_many(self, tickers, *, deadline_seconds, executor):
        return {
            t: PriceSnapshot(
                ticker=t, price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        }
    monkeypatch.setattr(PriceCache, "get_many", get_many)
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _make_watchlist_entry(
    *,
    ticker: str,
    entry_target: float | None = None,
    initial_stop_target: float | None = None,
    last_close: float | None = None,
    last_adr_pct: float = 2.0,
) -> WatchlistEntry:
    """Factory matching the actual WatchlistEntry dataclass shape."""
    return WatchlistEntry(
        ticker=ticker,
        added_date="2026-04-29",
        last_qualified_date="2026-04-29",
        status="watch",
        qualification_count=1,
        not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=entry_target,
        initial_stop_target=initial_stop_target,
        last_close=last_close,
        last_pivot=None,
        last_stop=None,
        last_adr_pct=last_adr_pct,
        missing_criteria=None,
        notes=None,
    )


def _seed_hyp_recs_fixture(
    cfg: Config,
    *,
    tickers: list[str] | None = None,
) -> None:
    """Seed enough state for hyp-recs to render at least 1 active
    recommendation. Each ticker gets an A+ candidate row + a watchlist row.

    Pattern ported from tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py
    — relies on the bundled `A+ baseline` hypothesis registered by the
    schema migration; no manual hypothesis_registry INSERT needed.
    """
    tickers = tickers or ["NVDA", "AMD"]
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, ?, ?, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T09:00:00", "2026-04-28", "2026-04-29",
                 len(tickers), len(tickers)),
            )
            eval_id = cur.lastrowid
            for tk in tickers:
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=tk, entry_target=100.0,
                        initial_stop_target=95.0, last_close=99.0,
                    ),
                )
                conn.execute(
                    """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                       close, pivot, initial_stop, rs_method)
                       VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 'universe')""",
                    (eval_id, tk),
                )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-29T08:00:00', '2026-04-29T09:00:00',
                           'scheduled', '2026-04-28', '2026-04-29',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_refresh_route_returns_section_partial(seeded_db, monkeypatch):
    """Spec §3.5.4 R2-Major-2 — refresh route returns the rendered
    hypothesis_recommendations.html.j2 section."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    # The section root element is <section id="hypothesis-recommendations">.
    assert 'id="hypothesis-recommendations"' in body, (
        "refresh route must render the section partial (root element"
        " '<section id=\"hypothesis-recommendations\">')"
    )
    # The section MUST include the rendered table head.
    assert "<thead>" in body
    assert ">Pivot<" in body, (
        "refresh route's rendered section must include the existing Pivot column"
    )


def test_refresh_route_does_not_invoke_full_dashboard_build(
    seeded_db, monkeypatch: pytest.MonkeyPatch,
):
    """R2-Major-2 regression: GET /hyp-recs/refresh must NOT call
    build_dashboard. Discriminating sentinel — a regression where the
    refresh handler reverts to build_dashboard would trip the sentinel.
    """
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)

    # Replace build_dashboard with a sentinel that records calls. The
    # refresh route must NOT call it.
    sentinel_calls: list[str] = []
    from swing.web.view_models import dashboard as dashboard_mod
    original = dashboard_mod.build_dashboard

    def _sentinel(*args, **kwargs):
        sentinel_calls.append("build_dashboard")
        # Defensive: still return a value so a regression-path doesn't
        # crash mid-test — sentinel_calls capture is the assertion.
        return original(*args, **kwargs)

    monkeypatch.setattr(dashboard_mod, "build_dashboard", _sentinel)
    # Also patch the route module's already-bound import (FastAPI may
    # have imported the symbol into the route module's namespace).
    from swing.web.routes import dashboard as dashboard_route
    if hasattr(dashboard_route, "build_dashboard"):
        monkeypatch.setattr(dashboard_route, "build_dashboard", _sentinel)
    from swing.web.routes import trades as trades_route
    if hasattr(trades_route, "build_dashboard"):
        monkeypatch.setattr(trades_route, "build_dashboard", _sentinel)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    assert sentinel_calls == [], (
        "refresh route must use scoped build_hyp_recs_section, not"
        f" build_dashboard. Sentinel was called: {sentinel_calls}"
    )


def test_refresh_route_renders_drift_equivalent_html_to_full_page(
    seeded_db, monkeypatch,
):
    """HTMX OOB-swap drift discriminating test (writing-plans brief §5
    watch item 3). The refresh route's hyp-recs section HTML must match
    the full-page render's hyp-recs section HTML — both go through the
    SAME `{% include %}` chain (`partials/hypothesis_recommendations.html.j2`).

    Discriminating: compares the section's structural shape (table head
    column count + each <th> text) between the two renders. A drift
    bug (e.g. refresh adds an extra <th>) would diverge.
    """
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        full_resp = client.get("/")
        refresh_resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert full_resp.status_code == 200, full_resp.text
    assert refresh_resp.status_code == 200, refresh_resp.text
    # Extract the <thead> region from each. (Simple shape-match —
    # full-page also renders other thead's so we anchor on the
    # hypothesis-recommendations section.)
    import re
    pattern = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>.*?</thead>',
        flags=re.DOTALL,
    )
    full_thead = pattern.search(full_resp.text)
    refresh_thead = pattern.search(refresh_resp.text)
    assert full_thead is not None and refresh_thead is not None, (
        "both renders must contain the hypothesis-recommendations section's"
        " thead — a regression that drops the section entirely fails here"
    )
    # Compare column-header text sequences. Both renders must produce the
    # same ordered list of <th> contents.
    th_pattern = re.compile(r"<th[^>]*>(.*?)</th>", flags=re.DOTALL)
    full_cols = [t.strip() for t in th_pattern.findall(full_thead.group(0))]
    refresh_cols = [t.strip() for t in th_pattern.findall(refresh_thead.group(0))]
    assert full_cols == refresh_cols, (
        "Hyp-recs section's thead column sequence drifts between full-page"
        f" and refresh-route renders. full={full_cols} refresh={refresh_cols}"
    )
