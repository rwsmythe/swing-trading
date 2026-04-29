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
    charts_status: str = "ok",
    seed_chart_targets: bool = True,
) -> int:
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
            cur2 = conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id, charts_status)
                   VALUES ('2026-04-29T08:00:00', '2026-04-29T09:00:00',
                           'scheduled', '2026-04-28', '2026-04-29',
                           'complete', 'tok', ?, ?)""",
                (eval_id, charts_status),
            )
            pipeline_run_id = int(cur2.lastrowid)
            if seed_chart_targets and charts_status == "ok":
                for tk in tickers:
                    conn.execute(
                        """INSERT INTO pipeline_chart_targets
                           (pipeline_run_id, ticker, source, chart_status)
                           VALUES (?, ?, 'aplus', 'ok')""",
                        (pipeline_run_id, tk),
                    )
                # Materialize the chart PNG files so resolve_chart_scope
                # does not downgrade an in-scope ok-target to insufficient-data.
                from pathlib import Path as _Path
                charts_dir = _Path(cfg.paths.charts_dir) / "2026-04-28"
                charts_dir.mkdir(parents=True, exist_ok=True)
                for tk in tickers:
                    (charts_dir / f"{tk}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return pipeline_run_id
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


# ---------------------------------------------------------------------------
# Task 5.3 — GET /hyp-recs/{ticker}/expand route tests.
# ---------------------------------------------------------------------------


def test_expand_route_happy_path_returns_partial(seeded_db, monkeypatch):
    """Spec §3.5.4 happy path — the expand route renders the
    `hypothesis_recommendations_expanded.html.j2` partial with all
    sections (Order parameters, Sizing, Context, Freshness)."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert 'id="hyp-rec-row-NVDA"' in body
    assert "close-expanded" in body, "close (✕) button must be present"
    assert "Order parameters" in body
    assert "Buy stop:" in body
    assert "Sizing" in body


def test_expand_route_unknown_ticker_returns_404_unavailable_partial(
    seeded_db, monkeypatch,
):
    """Ticker NOT in the latest run's candidates → 404 + the
    `hyp_recs_expand_unavailable.html.j2` body."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/UNKN/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 404, resp.text
    body = resp.text
    assert "expand-unavailable" in body
    assert "Not a current candidate" in body, (
        "operator-facing message must be rendered"
    )


def test_expand_route_404_swaps_as_tr_via_row_target_prefix(
    seeded_db, monkeypatch,
):
    """R1-Major-2 — when HX-Target matches `hyp-rec-row-*`, the 404 path
    must produce a <tr> fragment (NOT the generic <div> error fragment)
    so the HTML parser does not hoist a bare <div> out of <tbody>."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/UNKN/expand",
            headers={
                "HX-Request": "true",
                "HX-Target": "hyp-rec-row-UNKN",
            },
        )
    assert resp.status_code == 404, resp.text
    body = resp.text
    assert "<tr " in body, (
        "404 unavailable partial must be a <tr> fragment, got:\n" + body[:400]
    )
    # Discriminating: the generic full-page error template is NOT what we want.
    assert "<div " not in body or body.find("<tr ") < body.find("<div "), (
        "row-target prefix must produce a <tr>-rooted fragment"
    )


def test_expand_route_500_swaps_as_tr_via_row_target_prefix(
    seeded_db, monkeypatch,
):
    """R1-Major-2 defense-in-depth — a forced 500 inside the route must
    swap as <tr> when the request's HX-Target matches a row-target
    prefix. Requires `_ROW_TARGET_PREFIXES` to include `hyp-rec-row-`."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)

    # Force build_hyp_recs_expanded to raise; the global exception
    # handler should detect the row-target prefix and render the
    # trade_form_error.html.j2 fragment (a <tr>).
    from swing.web.routes import recommendations as rec_route
    from swing.web.view_models import dashboard as dashboard_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("forced 500 for row-target swap test")

    monkeypatch.setattr(dashboard_mod, "build_hyp_recs_expanded", _boom)
    if hasattr(rec_route, "build_hyp_recs_expanded"):
        monkeypatch.setattr(rec_route, "build_hyp_recs_expanded", _boom)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={
                "HX-Request": "true",
                "HX-Target": "hyp-rec-row-NVDA",
            },
        )
    assert resp.status_code == 500, resp.text
    body = resp.text
    assert "<tr " in body, (
        "500 + row-target prefix must produce a <tr> fragment, got:\n"
        + body[:400]
    )


def test_expand_route_chart_unavailable_renders_message(
    seeded_db, monkeypatch,
):
    """When `resolve_chart_scope` returns a non-None reason, the
    `chart-unavailable` div must render with the reason message text."""
    cfg, cfg_path = seeded_db
    # No chart targets seeded → chart_status='ok' but ticker is not in
    # pipeline_chart_targets → reason 'out-of-scope'.
    _seed_hyp_recs_fixture(cfg, seed_chart_targets=False)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "chart-unavailable" in body, (
        "out-of-scope ticker must render the chart-unavailable div"
    )
    # `out-of-scope` reason message uses "isn't in today's charting scope".
    assert "charting scope" in body or "Chart unavailable" in body


def test_expand_route_anchor_consistency_uses_completed_run_pivot(
    seeded_db, monkeypatch,
):
    """Spec §3.5.4 anchor consistency — an in-flight pipeline_run with
    `finished_ts IS NULL` MUST NOT win the binding lookup. The COMPLETED
    run's candidates (pivot=100.0) must be used, even if a more-recently-
    started in-flight run with a different pivot exists.
    """
    cfg, cfg_path = seeded_db
    # First seed: completed run with pivot=100.0 for NVDA.
    _seed_hyp_recs_fixture(cfg)

    # Now seed an in-flight run with a DIFFERENT pivot for the same ticker.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-29T10:00:00", "2026-04-29", "2026-04-30"),
            )
            inflight_eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, 'NVDA', 'aplus', 199.0, 200.0, 195.0, 'universe')""",
                (inflight_eval_id,),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-29T10:00:00', NULL,
                           'scheduled', '2026-04-29', '2026-04-30',
                           'running', 'tok2', ?)""",
                (inflight_eval_id,),
            )
    finally:
        conn.close()

    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    # COMPLETED run pivot is 100.00; in-flight pivot is 200.00. Body must
    # show the COMPLETED run's pivot.
    assert "$100.00" in body, (
        "expansion must use COMPLETED run's pivot (100.00), not in-flight"
        " run's pivot (200.00)"
    )
    assert "$200.00" not in body, (
        "in-flight run with NULL finished_ts must NOT win the binding"
    )


def test_expand_route_freshness_footer_includes_finished_ts(
    seeded_db, monkeypatch,
):
    """Spec §3.5.6 freshness — the rendered partial must include the
    binding's `finished_ts` substring as the freshness footer signal."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "2026-04-29T09:00:00" in body, (
        "freshness footer must render the binding pipeline_run.finished_ts"
    )


# ---------------------------------------------------------------------------
# Task 5.6 — Take-this-trade button (Q8) on expansion.
# Spec §3.5.6 (layout) + §3.7 D.2 D.3 D.5 (binding contracts).
# ---------------------------------------------------------------------------


def test_expand_route_take_this_trade_button_present(seeded_db, monkeypatch):
    """Task 5.6 — Take-this-trade button must be present in the expansion
    render. Discriminating: regression that drops the action-row would fail
    here."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "take-this-trade" in body, (
        "Take-this-trade button (class 'take-this-trade') must be present"
        " in expansion render"
    )
    assert "Take this trade" in body, (
        "Take-this-trade button must use the canonical label 'Take this trade'"
    )


def test_expand_route_take_this_trade_url_matches_per_row_enter(
    seeded_db, monkeypatch,
):
    """Task 5.6 D.2 (a) — Take-this-trade button's URL MUST match the
    per-row Enter button's URL. Both fire `/trades/entry/form?ticker=X
    &origin=hyp-recs`. Discriminating: a regression that diverged the URLs
    (e.g. different `&origin=` value, different path) fails here."""
    import re
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Render expansion (Take-this-trade button lives here).
        expand_resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
        # Render dashboard (per-row Enter button lives in the row partial).
        dash_resp = client.get("/")
    assert expand_resp.status_code == 200, expand_resp.text
    assert dash_resp.status_code == 200, dash_resp.text

    # Extract the Take-this-trade button block from the expansion response,
    # then extract its hx-get URL.
    take_button_match = re.search(
        r'<button[^>]*class="[^"]*take-this-trade[^"]*"[^>]*>',
        expand_resp.text,
        flags=re.DOTALL,
    )
    assert take_button_match is not None, (
        "Take-this-trade button tag not found in expansion response"
    )
    take_url_match = re.search(
        r'hx-get="([^"]+)"', take_button_match.group(0)
    )
    assert take_url_match is not None, (
        "Take-this-trade button must have hx-get attribute"
    )
    take_url = take_url_match.group(1)

    # Extract the per-row Enter button URL for NVDA from the dashboard.
    # Per-row Enter button has hx-get="/trades/entry/form?ticker=NVDA&origin=hyp-recs"
    # (Task 5.5). Find ANY hx-get pointing at /trades/entry/form for NVDA in
    # the hyp-recs section.
    section_match = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>'
        r'(.*?)</section>',
        dash_resp.text,
        flags=re.DOTALL,
    )
    assert section_match is not None, (
        "hypothesis-recommendations section not found in dashboard"
    )
    section_body = section_match.group(1)
    enter_url_match = re.search(
        r'hx-get="(/trades/entry/form\?[^"]*ticker=NVDA[^"]*)"',
        section_body,
    )
    assert enter_url_match is not None, (
        "per-row Enter button URL for NVDA not found in dashboard hyp-recs"
        " section"
    )
    enter_url = enter_url_match.group(1)

    assert take_url == enter_url, (
        f"Take-this-trade URL must match per-row Enter URL (D.2 (a)).\n"
        f"  Take-this-trade: {take_url}\n"
        f"  Per-row Enter:   {enter_url}"
    )


def test_expand_route_take_this_trade_button_has_primary_class(
    seeded_db, monkeypatch,
):
    """Task 5.6 D.3 — Take-this-trade button differentiates from per-row
    Enter via CSS class `primary`. The button's class attribute must
    contain both `take-this-trade` and `primary`."""
    import re
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    # Tolerant of class-attribute ordering: extract the class attr's value
    # from the take-this-trade button tag.
    button_match = re.search(
        r'<button[^>]*class="([^"]*take-this-trade[^"]*)"[^>]*>',
        resp.text,
        flags=re.DOTALL,
    )
    assert button_match is not None, (
        "Take-this-trade button tag with class attr not found"
    )
    class_value = button_match.group(1)
    classes = class_value.split()
    assert "take-this-trade" in classes, (
        f"button class attr must include 'take-this-trade'; got: {class_value}"
    )
    assert "primary" in classes, (
        f"button class attr must include 'primary' (D.3); got: {class_value}"
    )


def test_expand_route_take_this_trade_button_no_stop_propagation(
    seeded_db, monkeypatch,
):
    """Task 5.6 D.5 — Take-this-trade button MUST NOT include
    `event.stopPropagation` (the row is not a trigger; click bubbling is
    unnecessary). Discriminating: regression that copies the close-button
    pattern with stopPropagation onto Take-this-trade fails here."""
    import re
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    # Isolate the take-this-trade <button>...</button> region and assert
    # `stopPropagation` does NOT appear inside it.
    button_block_match = re.search(
        r'<button[^>]*class="[^"]*take-this-trade[^"]*"[^>]*>'
        r'.*?</button>',
        resp.text,
        flags=re.DOTALL,
    )
    assert button_block_match is not None, (
        "Take-this-trade button block not found"
    )
    button_block = button_block_match.group(0)
    assert "stopPropagation" not in button_block, (
        f"Take-this-trade button must not include stopPropagation (D.5);"
        f" found in:\n{button_block}"
    )


def test_expand_route_take_this_trade_layout_between_order_and_sizing(
    seeded_db, monkeypatch,
):
    """Task 5.6 spec §3.5.6 layout — the Take-this-trade button must appear
    BETWEEN the Order parameters group and the Sizing group. Discriminating:
    if inserted in the wrong section (e.g. AFTER Sizing or BEFORE Order
    parameters), this ordered-position assertion fails."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/NVDA/expand",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.text

    order_idx = body.find("Order parameters")
    take_idx = body.find("take-this-trade")
    sizing_idx = body.find("Sizing")

    assert order_idx >= 0, "'Order parameters' heading not found"
    assert take_idx >= 0, "'take-this-trade' button not found"
    assert sizing_idx >= 0, "'Sizing' heading not found"

    assert order_idx < take_idx, (
        f"Take-this-trade button must appear AFTER 'Order parameters'"
        f" heading. order_idx={order_idx} take_idx={take_idx}"
    )
    assert take_idx < sizing_idx, (
        f"Take-this-trade button must appear BEFORE 'Sizing' heading."
        f" take_idx={take_idx} sizing_idx={sizing_idx}"
    )
