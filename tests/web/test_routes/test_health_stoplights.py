"""Phase 18 Arc 18-F: the GUI health-stoplight web wiring.

The context-processor injection (Task 5), the every-base-route + strong-form
forced-500 (wired+defensive on `_handle_any`'s fresh `_build_templates`) +
per-provider-raise + positive 400/404-page-stoplights BINDING regression tests
(Task 6, re-scoped — CHARC-approved C-F1/C-F2), and the two drill-down routes
(Task 7). TestClient asserts the BODY, not the rendered DOM — the operator
browser gate is the binding net for DOM/visual regressions (brief §6).

Task-6 RE-SCOPE (CHARC C-F1/C-F2): the bare unhandled-500 page
(`error.html.j2`, via `_handle_any`) is a STANDALONE document that does NOT
extend base and INTENTIONALLY omits the stoplights — by design, it is the
last-resort page that must not depend on base (a base-render failure is a
plausible CAUSE of the 500, so a stoplight there would risk a 500-on-the-500).
"All pages carry stoplights" therefore means all NORMAL pages + the
base-extending full-page error page (`page_error.html.j2`, 400/404). The
forced-500 test below proves the context processor is WIRED + DEFENSIVE on the
fresh-templates 500 render (NOT that stoplights appear in the bare 500 body).
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from swing.monitoring.stoplights import RESEARCH_MONITOR_ID
from swing.web.app import _health_stoplights_context_processor, create_app


def _seed_minimal_dashboard_state(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17', '2026-04-20',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 't')""",
            )
    finally:
        conn.close()


def _stub_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


# ---------------------------------------------------------------- Task 5


def test_health_stoplights_context_processor_returns_key(seeded_db):
    cfg, _ = seeded_db
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=cfg)))
    out = _health_stoplights_context_processor(request)
    assert "health_stoplights" in out
    stoplights = out["health_stoplights"]
    assert isinstance(stoplights, tuple)
    assert len(stoplights) == 2
    assert [s.id for s in stoplights] == ["tool", "research"]


def test_context_processor_returns_empty_when_cfg_none():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=None)))
    out = _health_stoplights_context_processor(request)
    assert out == {"health_stoplights": ()}


def test_context_processor_never_raises_when_aggregator_raises(seeded_db, monkeypatch):
    cfg, _ = seeded_db

    def _boom(conn, cfg):
        raise RuntimeError("aggregator defect")

    monkeypatch.setattr("swing.web.app.health_stoplights", _boom)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cfg=cfg)))
    out = _health_stoplights_context_processor(request)  # must NOT raise
    assert out == {"health_stoplights": ()}


def test_dashboard_renders_with_stoplights_present(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert 'class="stoplights"' in r.text
    assert "/health/tool" in r.text
    assert "/health/research" in r.text


def test_context_processor_injects_color_classes(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert r.text.count("stoplight-") >= 2


# ---------------------------------------------------------------- Task 7


def test_health_tool_route_lists_checks(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/tool")
    assert r.status_code == 200
    assert "pipeline_freshness" in r.text  # a known 18-E check key
    assert 'class="stoplights"' in r.text  # the drill-down is itself a base page


def test_health_research_route_not_deployed_message(seeded_db, monkeypatch, tmp_path):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: tmp_path / "absent.json",
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/research")
    assert r.status_code == 200
    assert "18-D" in r.text
    assert "not yet deployed" in r.text.lower()


def test_health_research_route_lists_checks_when_artifact_present(
    seeded_db, monkeypatch, tmp_path,
):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    p = tmp_path / "latest.json"
    p.write_text(
        json.dumps({
            "monitor": RESEARCH_MONITOR_ID,
            "generated_ts": datetime.now().isoformat(),
            "overall": "yellow",
            "checks": [
                {"key": "expectancy_freshness", "status": "yellow",
                 "summary": "stale shadow run", "detail": "ran 9d ago"},
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path", lambda: p,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/health/research")
    assert r.status_code == 200
    assert "expectancy_freshness" in r.text
    assert "stale shadow run" in r.text


def test_health_routes_read_only(seeded_db, monkeypatch):
    from swing.data.db import connect
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)

    def _count(conn):
        return conn.execute(
            "SELECT COUNT(*) FROM pipeline_runs",
        ).fetchone()[0]

    conn = connect(cfg.paths.db_path)
    try:
        before = _count(conn)
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.get("/health/tool").status_code == 200
        assert client.get("/health/research").status_code == 200
    conn = connect(cfg.paths.db_path)
    try:
        after = _count(conn)
    finally:
        conn.close()
    assert before == after


# ---------------------------------------------------------------- Task 6


def _seed_trade_for_drilldown(cfg) -> int:
    from swing.data.db import connect
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="VIR", entry_date="2026-04-20",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, state="managing",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None, trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-20T09:30:00",
                    thesis="breakout", why_now="volume",
                    invalidation_condition="loses 9"),
                event_ts="2026-04-20T09:30:00")
            insert_fill_with_event(
                conn,
                Fill(fill_id=None, trade_id=tid,
                     fill_datetime="2026-04-20T09:30:00", action="entry",
                     quantity=10.0, price=10.0),
                event_ts="2026-04-20T09:30:00")
    finally:
        conn.close()
    return tid


def test_every_base_route_renders_with_stoplights_and_no_500(seeded_db, monkeypatch):
    """The brief §3 LOCK-2 every-base-route regression test. TestClient asserts
    the BODY, not the rendered DOM — a base-render 500 IS catchable here (500
    status); a browser-only DOM defect is NOT (the operator browser gate is the
    binding net for those)."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    tid = _seed_trade_for_drilldown(cfg)
    _stub_price_cache(monkeypatch)
    # /schwab/status resolves the tokens DB off USERPROFILE/HOME — isolate it.
    monkeypatch.setenv("USERPROFILE", str(cfg.paths.db_path.parent))
    monkeypatch.setenv("HOME", str(cfg.paths.db_path.parent))

    app = create_app(cfg, cfg_path)
    base_get_routes = [
        "/", "/watchlist", "/journal", "/pipeline", "/metrics", "/config",
        f"/journal/trades/{tid}", "/schwab/status",
        "/health/tool", "/health/research",
    ]
    error_route = "/journal/trades/999999"  # 404 -> the error page (base too)
    with TestClient(app) as client:
        for route in base_get_routes:
            r = client.get(route)
            assert r.status_code != 500, f"{route} 500'd"
            if r.status_code == 200:
                assert 'class="stoplights"' in r.text, f"{route} missing stoplights"
        r = client.get(error_route)
        assert r.status_code != 500  # a 404 is acceptable; the contract is NO 500


def test_provider_raise_degrades_to_grey_not_500(seeded_db, monkeypatch, tmp_path):
    """The brief §3 LOCK-2 force-each-provider-to-raise -> grey + no 500 test."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    # Tool provider raises.
    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health",
        lambda conn, **kw: (_ for _ in ()).throw(RuntimeError("tool boom")),
    )
    # Research artifact malformed.
    malformed = tmp_path / "latest.json"
    malformed.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(
        "swing.monitoring.stoplights.research_health_artifact_path",
        lambda: malformed,
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200  # NOT 500
    assert "stoplight-grey" in r.text  # at least one slot degraded to grey


def test_forced_500_wired_and_defensive_on_handle_any_fresh_templates(
    seeded_db, monkeypatch,
):
    """STRONG-FORM forced-500 (CHARC C-F1 re-scope) — prove the context processor
    is WIRED on `_handle_any`'s FRESH `_build_templates` render AND DEFENSIVE.

    The REAL `_handle_any` (swing/web/app.py) builds a FRESH `_build_templates(...)`
    instance for the unhandled-500 page; the context processor must be registered
    INSIDE `_build_templates` to run on THAT render. We patch the stoplight
    PROVIDER (`compute_tool_health`, lazy-imported by `_tool_stoplight`) to (a)
    RAISE and (b) record it was called, then trigger an unhandled exception that
    routes through `_handle_any` -> fresh templates -> `error.html.j2`.

    Both-ways (this is NOT a mere healthy-500 render):
      * WIRED + DEFENSIVE -> clean 500 (error.html.j2, no secondary 500) AND the
        provider spy fired during that render -> PASS.
      * NOT wired on the fresh-templates path -> the processor never runs there ->
        the provider spy is NEVER called -> FAILS the call_count assertion.
      * WIRED but NOT defensive -> the provider's raise propagates out of the
        processor during the 500 render -> a secondary failure / broken response
        -> FAILS the clean-500 assertion.
    So it distinguishes "wired + defensive" from BOTH "not wired" and
    "wired-not-defensive".

    The bare unhandled-500 page (error.html.j2) INTENTIONALLY omits stoplights
    (standalone, does NOT extend base — CHARC C-F1), so we do NOT assert
    `class="stoplights"` here; the positive 400/404 test below guards the real
    stoplight-bearing error page.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)

    calls = {"n": 0}

    def _spy_compute_tool_health(conn, **kw):
        calls["n"] += 1
        raise RuntimeError("tool boom during 500 render")

    # Patch the PROVIDER `_tool_stoplight` lazy-imports during the processor's
    # render. The spy raises (proving defensiveness) AND records the call
    # (proving the processor ran on the fresh-templates path).
    monkeypatch.setattr(
        "swing.monitoring.tool_health.compute_tool_health",
        _spy_compute_tool_health,
    )

    def _raise_boom():
        raise RuntimeError("boom")

    app.add_api_route("/__boom__", _raise_boom)
    # raise_server_exceptions=False -> TestClient returns the rendered 500 page
    # instead of re-raising the exception into the test.
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/__boom__")
    # Clean 500: the real _handle_any rendered error.html.j2 through the fresh
    # templates with NO secondary 500 / unhandled exception in the response.
    assert resp.status_code == 500
    assert "Something went wrong" in resp.text  # error.html.j2 (not a raw stack)
    # The provider spy fired DURING that 500 render -> the processor is wired on
    # the fresh-_build_templates path AND swallowed the raise (defensive).
    assert calls["n"] >= 1, "context processor did not run on _handle_any's render"


def test_full_page_400_error_renders_stoplights(seeded_db, monkeypatch):
    """POSITIVE test (CHARC C-F2 re-scope) — the base-extending full-page error
    page (`page_error.html.j2`) DOES carry the stoplights via the context
    processor. A typo path-param (`/journal/trades/notanint`, an int route)
    raises RequestValidationError; a non-HTMX GET with Accept: text/html renders
    the full-page 400 through base (the path the operator browser gate uses).

    Both-ways: if the processor were not wired (or page_error stopped extending
    base), `class="stoplights"` would be absent from this 400 body.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _stub_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal/trades/notanint", headers={"Accept": "text/html"},
        )
    assert r.status_code == 400
    assert 'class="stoplights"' in r.text
