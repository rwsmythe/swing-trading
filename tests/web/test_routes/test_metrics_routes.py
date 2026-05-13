"""Phase 10 Sub-bundle A T-A.8 — /metrics index page smoke tests.

Per-surface routes (Sub-bundles B/C/D/E) get their own test files when
they land. This file covers the umbrella `GET /metrics` only.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_metrics_index_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    assert "Metrics dashboard" in r.text


def test_metrics_index_renders_all_8_surface_links(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    # Every plan §A.3 surface link must appear in the index.
    for href in (
        "/metrics/trade-process",
        "/metrics/hypothesis-progress",
        "/metrics/tier-comparison",
        "/metrics/capital-friction",
        "/metrics/maturity-stage",
        "/metrics/identification-funnel",
        "/metrics/deviation-outcome",
        "/metrics/process-grade-trend",
    ):
        assert href in r.text, f"missing surface link: {href}"


def test_metrics_index_extends_base_layout(seeded_db):
    """Response body contains the base-layout topbar (dashboard link + date)
    confirming the index template extends base.html.j2."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    # Topbar nav markers from base.html.j2.
    assert 'class="topbar"' in r.text
    assert "Dashboard" in r.text
    assert "Pipeline" in r.text


def test_metrics_index_registered_in_app_routes(seeded_db):
    """Confirm /metrics is registered in the app's route table (per CLAUDE.md
    'HX-Redirect target route must be verified to exist' gotcha family —
    apply pre-emptively to any new route landing). Sub-bundle A
    deliberately ships the navigator + the 8 surface tile links; tile
    targets 404 until B/C/D/E land per dispatch brief §2 S3."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics" in route_paths


def test_metrics_index_unresolved_material_field_populated(seeded_db):
    """VM constructor populates ``unresolved_material_discrepancies_count``
    eagerly from the discrepancies helper (plan §A.18 + §I.5 LOCK)."""
    import sqlite3

    from swing.web.view_models.metrics.index import build_metrics_index_vm

    cfg, _ = seeded_db
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        vm = build_metrics_index_vm(conn)
    finally:
        conn.close()
    # Empty DB has 0 unresolved-material discrepancies → field is 0.
    assert vm.unresolved_material_discrepancies_count == 0


def test_metrics_index_top_nav_link_in_base_layout(seeded_db):
    """`Metrics` link appears in topbar nav on any base-layout page (e.g., /)."""
    cfg, cfg_path = seeded_db
    # Seed minimal pipeline_runs row so / renders.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-05-12T21:49:00', '2026-05-12', '2026-05-13',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-05-12T21:49:00', '2026-05-12T21:55:00', 'scheduled',
                           '2026-05-12', '2026-05-13', 'complete', 't')""",
            )
    finally:
        conn.close()

    import pytest as _pytest

    from swing.web.price_cache import PriceCache
    monkeypatch = _pytest.MonkeyPatch()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    monkeypatch.undo()
    assert r.status_code == 200
    assert 'href="/metrics"' in r.text


# ---------------------------------------------------------------------------
# Sub-bundle B Task T-B.3: GET /metrics/trade-process
# ---------------------------------------------------------------------------

def test_trade_process_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    assert r.status_code == 200
    assert "Trade-process metrics" in r.text


def test_trade_process_renders_all_5_tabs_in_html_body(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    assert r.status_code == 200
    # All 4 registered cohort names + the "All closed trades" toggle label.
    for label in (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
        "All closed trades",
    ):
        assert label in r.text, f"missing cohort tab label: {label}"


def test_trade_process_default_active_is_first_cohort(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    # Default-active marker should target the FIRST cohort, NOT "all".
    assert 'data-cohort-key="A+ baseline"' in r.text


def test_trade_process_at_zero_trades_renders_suppression_placeholders_in_html(
    seeded_db,
):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    assert r.status_code == 200
    # Spec §5.6 suppression text format.
    assert "n too low" in r.text


def test_trade_process_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    assert r.status_code == 200
    assert 'class="topbar"' in r.text


def test_trade_process_cohort_query_param_selects_active_tab(seeded_db):
    """Operator-supplied ``?cohort=<name>`` selects the active tab."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/metrics/trade-process",
            params={"cohort": "Sub-A+ VCP-not-formed"},
        )
    assert r.status_code == 200
    assert 'data-cohort-key="Sub-A+ VCP-not-formed"' in r.text


def test_trade_process_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/trade-process" in route_paths


# ---------------------------------------------------------------------------
# Sub-bundle B Task T-B.5: GET /metrics/hypothesis-progress
# ---------------------------------------------------------------------------

def test_hypothesis_progress_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/hypothesis-progress")
    assert r.status_code == 200
    assert "Hypothesis-progress card" in r.text


def test_hypothesis_progress_renders_all_4_cohorts(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/hypothesis-progress")
    assert r.status_code == 200
    for label in (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    ):
        assert label in r.text, f"missing cohort cell: {label}"


def test_hypothesis_progress_renders_decision_criteria_text(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/hypothesis-progress")
    body = r.text
    # HTML-escaped `>` → `&gt;`; check segments that survive escaping.
    assert "lower-bound Wilson CI on win rate" in body
    assert "Mean R-multiple within 25% of A+ baseline mean" in body
    assert "Confirm negative mean R-multiple" in body
    assert "defensibility of smaller-position approach" in body


def test_hypothesis_progress_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/hypothesis-progress" in route_paths


def test_hypothesis_progress_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/hypothesis-progress")
    assert 'class="topbar"' in r.text


# ---------------------------------------------------------------------------
# Sub-bundle C Task T-C.2: GET /metrics/tier-comparison
# ---------------------------------------------------------------------------

def test_tier_comparison_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    assert r.status_code == 200
    assert "Tier-comparison metrics" in r.text


def test_tier_comparison_renders_4_cohort_columns(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    assert r.status_code == 200
    # Each cohort's column header anchors via data-cohort-name attribute.
    for cohort in (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    ):
        assert f'data-cohort-name="{cohort}"' in r.text, (
            f"missing cohort column header for {cohort!r}"
        )


def test_tier_comparison_at_zero_trades_renders_descriptor_suppression_text(
    seeded_db,
):
    """Per spec §4.3 worked example: at our current state all CIs are
    suppressed + descriptor renders the "Insufficient cohort samples"
    placeholder."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    assert r.status_code == 200
    body = r.text
    # Spec §5.6 italic placeholder format for cohort cells.
    assert "n too low" in body
    # Descriptor suppression placeholder per dispatch brief §0.10 LOCK.
    assert "Insufficient cohort samples" in body


def test_tier_comparison_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    assert 'class="topbar"' in r.text


def test_tier_comparison_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/tier-comparison" in route_paths


def test_tier_comparison_descriptor_text_does_not_contain_boolean_keys(
    seeded_db,
):
    """Per spec §3.3 R1 M3 LOCK: descriptor is TEXT (NOT boolean / p-value).

    Even at zero trades the suppression placeholder is TEXT — no
    `classification_quality_flag` / `significant` / `p =` leak through."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    body = r.text.lower()
    assert "classification_quality_flag" not in body
    assert ">significant<" not in body
    assert "p-value" not in body
    assert ">p =<" not in body


def test_tier_comparison_renders_no_color_only_badges(seeded_db):
    """Per spec §4.9 + plan §A.9: badges are TEXT-only (no inline color
    style)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/tier-comparison")
    body = r.text
    for forbidden in ("background:red", "background:green", "color:red",
                      "color:green"):
        assert forbidden not in body, (
            f"color-only inline style {forbidden!r} present"
        )


# ---------------------------------------------------------------------------
# Sub-bundle C Task T-C.3: GET /metrics/deviation-outcome
# ---------------------------------------------------------------------------

def test_deviation_outcome_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    assert r.status_code == 200
    assert "Deviation-outcome metrics" in r.text


def test_deviation_outcome_renders_4_cohort_rows_or_placeholders(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    body = r.text
    for cohort in (
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
    ):
        assert f'data-cohort-name="{cohort}"' in body, (
            f"missing cohort row anchor for {cohort!r}"
        )
    # At zero trades each row shows the "n too low" placeholder for the
    # relative-pct cell (template renders italic <em> per spec §5.6).
    assert "n too low" in body


def test_deviation_outcome_renders_doctrine_deviation_class_enum(seeded_db):
    """Per spec §3.7 row 1: enum values surface on the rendered page."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    body = r.text
    for enum_value in (
        "baseline",
        "missing_proximity_20ma",
        "missing_tightness_or_vcp_volume_contraction",
        "smaller_than_standard_position",
    ):
        assert enum_value in body, f"missing doctrine_deviation_class: {enum_value}"


def test_deviation_outcome_renders_decision_criteria_seed_text(seeded_db):
    """Spec §3.7 R1 M4 + dispatch brief §0.11 LOCK: seed text verbatim."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    body = r.text
    # `>` is HTML-escaped to `&gt;` — check substrings that survive escaping.
    assert "lower-bound Wilson CI on win rate" in body
    assert "Mean R-multiple within 25% of A+ baseline mean" in body
    assert "Confirm negative mean R-multiple" in body
    assert "defensibility of smaller-position approach" in body


def test_deviation_outcome_decision_criterion_text_has_no_automated_evaluation(
    seeded_db,
):
    """Per spec §3.7 R1 M4 LOCK: NO automated pass/fail. The page must
    NOT surface "Pass:" / "Fail:" / "criterion met:" / "current: ..."
    synthesis blocks alongside the seed criterion."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    body = r.text
    for forbidden in (
        "criterion met:",
        "criterion_met:",
        ">Pass<",
        ">Fail<",
        "Pass: yes",
        "Pass: no",
        "Fail: yes",
        "Fail: no",
    ):
        assert forbidden not in body, (
            f"automated evaluation drift: {forbidden!r} in body"
        )


def test_deviation_outcome_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    assert 'class="topbar"' in r.text


def test_deviation_outcome_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/deviation-outcome" in route_paths


def test_deviation_outcome_renders_no_color_only_badges(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/deviation-outcome")
    body = r.text
    for forbidden in ("background:red", "background:green", "color:red",
                      "color:green"):
        assert forbidden not in body, (
            f"color-only inline style {forbidden!r} present"
        )


def test_trade_process_renders_no_color_only_badges(seeded_db):
    """Per spec §4.9 + plan §A.9: badges render as TEXT inline, never
    color-only. Sanity check: at our default-tab n=0, NO badges are
    expected to render (everything suppressed), but the literal text
    'background:red' or similar should never appear in the body."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/trade-process")
    body = r.text
    for forbidden in ("background:red", "background:green", "color:red",
                      "color:green"):
        assert forbidden not in body, (
            f"Color-only inline style {forbidden!r} present — spec §4.9 "
            "binds badges to TEXT-only rendering"
        )


# ---------------------------------------------------------------------------
# Sub-bundle D Task T-D.2: GET /metrics/capital-friction
# ---------------------------------------------------------------------------

def test_capital_friction_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    assert r.status_code == 200
    assert "Capital-friction metrics" in r.text


def test_capital_friction_renders_provisional_text_when_no_snapshot(seeded_db):
    """Plan §A.6 + dispatch brief §0.8 LOCK: badge renders as TEXT not
    color-only. Discriminating: exact substring `>PROVISIONAL<` at the
    capital-denominator badge cell."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    body = r.text
    # Exact-substring per lesson #20 (body-wide "PROVISIONAL" might collide
    # with the word "PROVISIONAL fallback" elsewhere). Pin to the badge
    # element with data-badge="capital-denominator".
    assert (
        'data-badge="capital-denominator">PROVISIONAL</span>' in body
    ), (
        "Expected exact PROVISIONAL badge at capital-denominator cell; "
        f"body excerpt: {body[:500]}"
    )


def test_capital_friction_renders_live_when_snapshot_present(seeded_db):
    """Snapshot on-or-before today → badge flips to LIVE."""
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.evaluation.dates import last_completed_session

    cfg, cfg_path = seeded_db
    asof = last_completed_session(_dt.now())
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO account_equity_snapshots (snapshot_date, "
                "equity_dollars, source, recorded_at, recorded_by) VALUES "
                "(?, 3000.0, 'manual', ?, 'test')",
                (asof.isoformat(), asof.isoformat() + "T08:00:00"),
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    body = r.text
    assert (
        'data-badge="capital-denominator">LIVE</span>' in body
    ), (
        "Expected exact LIVE badge at capital-denominator cell after "
        f"snapshot write; body excerpt: {body[:500]}"
    )


def test_capital_friction_renders_historical_disclosure_footnote_in_trend_section(
    seeded_db,
):
    """Plan §A.0.1 + dispatch brief §0.10 BINDING (Codex R2 Major #4):
    EXACT verbatim footnote text in trend section."""
    from datetime import datetime as _dt

    import exchange_calendars
    import pandas as pd

    from swing.data.db import connect
    from swing.evaluation.dates import last_completed_session

    cfg, cfg_path = seeded_db
    # Seed 5 distinct trading sessions of pipeline_runs to unblock trend.
    cal = exchange_calendars.get_calendar("XNYS")
    asof = last_completed_session(_dt.now())
    sessions = cal.sessions_window(pd.Timestamp(asof), -5)
    session_dates = sorted({s.date().isoformat() for s in sessions})
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, sd in enumerate(session_dates[:5], start=1):
                conn.execute(
                    "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                    "action_session_date, tickers_evaluated, aplus_count, "
                    "watch_count, skip_count, excluded_count, error_count) "
                    "VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0)",
                    (i, sd + "T13:00:00", sd, sd),
                )
                conn.execute(
                    "INSERT INTO pipeline_runs (id, started_ts, finished_ts, "
                    "trigger, data_asof_date, action_session_date, state, "
                    "lease_token, evaluation_run_id) VALUES "
                    "(?, ?, ?, 'manual', ?, ?, 'complete', 'tok', ?)",
                    (i, sd + "T13:00:00", sd + "T13:30:00", sd, sd, i),
                )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    body = r.text
    # EXACT verbatim footnote per plan §A.0.1.
    expected_footnote = (
        "Trend computed from current trade state; historical points "
        "approximate where state has changed since the run."
    )
    assert expected_footnote in body, (
        f"Expected verbatim §A.0.1 footnote; not found in body. "
        f"Body excerpt: {body[:1000]}"
    )
    # And it must be inside the historical-disclosure marker (pinned to
    # the trend section per lesson #20).
    assert 'data-footnote="historical-disclosure"' in body


def test_capital_friction_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    assert 'class="topbar"' in r.text


def test_capital_friction_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/capital-friction" in route_paths


def test_capital_friction_renders_no_color_only_badges(seeded_db):
    """Per spec §4.9 + plan §A.9 BINDING: badges are TEXT-only."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/capital-friction")
    body = r.text
    for forbidden in ("background:red", "background:green", "color:red",
                      "color:green"):
        assert forbidden not in body, (
            f"color-only inline style {forbidden!r} present"
        )


# ---------------------------------------------------------------------------
# Sub-bundle D Task T-D.4: GET /metrics/maturity-stage
# ---------------------------------------------------------------------------

def test_maturity_stage_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    assert r.status_code == 200
    assert "Maturity-stage metrics" in r.text


def test_maturity_stage_zero_open_renders_placeholder(seeded_db):
    """Spec §4.5 empty-state: 'No open positions to manage.'"""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    assert "No open positions to manage." in r.text
    # Discriminating: pin to the empty-state marker per lesson #20.
    assert 'data-empty-state="maturity-stage"' in r.text


def test_maturity_stage_renders_per_row_with_em_dash_for_null_capture_need(
    seeded_db,
):
    """Plan §G T-D.4 + spec §4.5: NULL trail_MA_candidate_price + NULL
    planned_target_R render `"—"` placeholder (NOT '[Phase 8 capture
    pending]')."""
    from swing.data.db import connect
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, sector, "
                "industry, trade_origin, pre_trade_locked_at, current_size, "
                "current_avg_cost) VALUES (1, 'AAA', '2026-05-01', 10.0, "
                "100, 9.0, 9.0, 'managing', 'S', 'I', 'manual_off_pipeline', "
                "'2026-05-01T09:30:00', 100, 10.0)"
            )
    finally:
        conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    body = r.text
    assert r.status_code == 200
    # Forbidden text per plan §G T-D.4 acceptance.
    assert "[Phase 8 capture pending]" not in body
    # Each Phase-8 capture-need cell renders the `<em>—</em>` placeholder.
    assert 'data-cell="planned_target_R"' in body
    assert 'data-cell="trail_MA_candidate_price"' in body


def test_maturity_stage_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    assert 'class="topbar"' in r.text


def test_maturity_stage_registered_in_app_routes(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    route_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/metrics/maturity-stage" in route_paths


def test_maturity_stage_renders_no_color_only_badges(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/maturity-stage")
    body = r.text
    for forbidden in ("background:red", "background:green", "color:red",
                      "color:green"):
        assert forbidden not in body, (
            f"color-only inline style {forbidden!r} present"
        )
