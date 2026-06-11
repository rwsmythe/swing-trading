"""Phase 10 Sub-bundle E Task T-E.2 — process-grade-trend route smoke tests.

Per plan §H T-E.2 acceptance:
- Endpoint returns 200.
- Template renders inline SVG with polyline (when window full) + circles
  (always when trades exist).
- Per spec §4.9 + lesson #20 + #23: confidence-floor warning + window-not-
  full warning rendered as TEXT inline (separate elements, exact rendered
  substring).
"""
from __future__ import annotations

import re
import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _panel(html: str, name: str) -> str:
    """Inner markup of the <svg data-panel="<name>"> ... </svg> block.

    Panel-scoped slicing (Codex R2-M2): a global ``in r.text`` would falsely
    pass even if every series stayed in the grades SVG with empty rate/cost
    panels bolted on.
    """
    m = re.search(rf'<svg[^>]*data-panel="{name}"[^>]*>(.*?)</svg>', html, re.S)
    assert m is not None, f"panel {name} svg missing"
    return m.group(1)


def _legend(html: str) -> str:
    m = re.search(
        r'<g[^>]*data-marker="grades-legend"[^>]*>(.*?)</g>', html, re.S,
    )
    assert m is not None, "grades-legend group missing"
    return m.group(1)


def _seed_n_reviewed_trades(
    db_path,
    *,
    n: int,
    process_grade: str = "B",
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for i in range(n):
            day = (i % 27) + 1
            trade_id = i + 1
            ts = f"2026-04-{day:02d}T16:00:00"
            fill_ts = f"2026-04-{day:02d}T15:30:00"
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, sector, "
                "industry, trade_origin, pre_trade_locked_at, current_size, "
                "process_grade, entry_grade, management_grade, exit_grade, "
                "disqualifying_process_violation, realized_R_if_plan_followed, "
                "reviewed_at, last_fill_at) VALUES "
                "(?, ?, '2026-03-15', 10.0, 100, 9.0, 9.0, 'reviewed', 'S', 'I', "
                "'manual_off_pipeline', '2026-03-15T09:30:00', 0, ?, ?, ?, ?, 0, "
                "1.0, ?, ?)",
                (
                    trade_id, f"T{i:03d}",
                    process_grade, process_grade, process_grade, process_grade,
                    ts, fill_ts,
                ),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, '2026-03-15T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
                (trade_id,),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, ?, 'exit', 100, 11.0, 'unreconciled')",
                (trade_id, fill_ts),
            )
        conn.commit()
    finally:
        conn.close()


def _seed_intent_reviewed_trades(db_path) -> None:
    """Seed reviewed trades carrying entry_intent for the marker-annotation
    route tests (one standard, one by-design, one unclassified)."""
    conn = sqlite3.connect(db_path)
    try:
        rows = (
            (1, "STD", "standard", "2026-04-01"),
            (2, "BYD", "hypothesis_test_by_design", "2026-04-02"),
            (3, "UNC", None, "2026-04-03"),
        )
        for trade_id, ticker, intent, day in rows:
            ts = f"{day}T16:00:00"
            fill_ts = f"{day}T15:30:00"
            conn.execute(
                "INSERT INTO trades (id, ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, sector, "
                "industry, trade_origin, pre_trade_locked_at, current_size, "
                "process_grade, entry_grade, management_grade, exit_grade, "
                "disqualifying_process_violation, realized_R_if_plan_followed, "
                "reviewed_at, last_fill_at, entry_intent) VALUES "
                "(?, ?, '2026-03-15', 10.0, 100, 9.0, 9.0, 'reviewed', 'S', "
                "'I', 'manual_off_pipeline', '2026-03-15T09:30:00', 0, 'B', "
                "'B', 'B', 'B', 0, 1.0, ?, ?, ?)",
                (trade_id, ticker, ts, fill_ts, intent),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, '2026-03-15T09:30:00', 'entry', 100, 10.0, 'unreconciled')",
                (trade_id,),
            )
            conn.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, reconciliation_status) VALUES "
                "(?, ?, 'exit', 100, 11.0, 'unreconciled')",
                (trade_id, fill_ts),
            )
        conn.commit()
    finally:
        conn.close()


def test_pgt_template_emits_intent_css_hook(seeded_db):
    """Marker circles carry the normalized data-entry-intent hook (spec §7.2);
    the by-design marker uses the `by-design` token, NOT the raw enum value
    (Codex R1-Major-2)."""
    cfg, cfg_path = seeded_db
    _seed_intent_reviewed_trades(cfg.paths.db_path)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert "data-entry-intent=" in r.text
    grades = _panel(r.text, "grades")
    assert 'data-entry-intent="standard"' in grades
    assert 'data-entry-intent="by-design"' in grades
    assert 'data-entry-intent="unclassified"' in grades
    # The raw token must NOT leak as a CSS class / attribute.
    assert "hypothesis_test_by_design" not in grades


def test_pgt_rolling_series_byte_stable_and_hooks_preserved(seeded_db):
    """L5 LOCK: every #22 rolling-series + panel hook stays present after the
    additive marker-intent annotation. Seed n=5 so the rolling line is
    drawable (polyline floor) AND mark the cohort with entry_intent."""
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    for hook in (
        'data-panel="grades"', 'data-panel="rate"', 'data-panel="cost"',
        'data-series=', '<polyline', '<circle', 'A=4', 'F=0',
        'data-marker="grades-legend"',
    ):
        assert hook in r.text, f"missing #22 hook: {hook}"


def test_process_grade_trend_endpoint_returns_200(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert "Process-grade trend" in r.text


def test_process_grade_trend_endpoint_registered_in_app_routes(seeded_db):
    """Pre-empts the HX-Redirect target gotcha family — verify route is
    actually registered in the FastAPI router."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/metrics/process-grade-trend" in paths


def test_process_grade_trend_extends_base_layout(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert 'class="topbar"' in r.text


def test_process_grade_trend_renders_empty_state_when_no_trades(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert 'data-empty-state="process-grade-trend"' in r.text


def test_process_grade_trend_renders_svg_polyline_when_window_drawable(seeded_db):
    """Per §A.10 LOCK + §5.4 5≤effective_n<N — line drawable + polyline emitted."""
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    # SVG element with viewBox attribute.
    assert "<svg viewBox" in r.text
    # Polyline emitted for the process_grade_rolling_N series.
    assert 'data-series="process_grade_rolling_N"' in r.text
    assert "<polyline points=" in r.text
    # F-3: the template loops over svg_polyline_segments; the per-segment CSS
    # class hooks are preserved so gaps render as separate <polyline>s.
    assert (
        'class="process-grade-rolling-line metric-process_grade_rolling_N"'
        in r.text
    )


def test_process_grade_trend_renders_per_trade_circles_always(seeded_db):
    """Per spec §5.4 + §4.8: per-trade markers always render even at low n."""
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=2)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert "<circle " in r.text
    # NO polyline at n=2 (line floor is 5).
    assert "<polyline" not in r.text


def test_process_grade_trend_renders_separate_decoupled_badge_text_elements(
    seeded_db,
):
    """Per spec §5.4 + lesson #23: confidence-floor warning + window-not-full
    warning + drawability text render as SEPARATE text elements with
    dedicated ``data-marker=`` attributes — NOT title= hover-only.
    """
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    # Exact rendered substrings (lesson #20 exact-substring discrimination).
    assert 'data-marker="drawability-process_grade_rolling_N"' in r.text
    assert "rolling line drawable" in r.text
    assert 'data-marker="window-warning-process_grade_rolling_N"' in r.text
    assert "rolling window not yet at N" in r.text
    assert 'data-marker="floor-warning-process_grade_rolling_N"' in r.text
    # Jinja auto-escapes "<" → "&lt;" in HTML output.
    assert "below confidence floor (n&lt;20)" in r.text


def test_process_grade_trend_grade_axis_encoding_labels_visible(seeded_db):
    """Lesson #19 — grade axis labels include numeric encoding."""
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=3)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert "A=4" in r.text
    assert "F=0" in r.text


def test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib(
    seeded_db,
):
    """Plan §A.10 LOCK: NO matplotlib PNG; NO client-side chart library
    (Chart.js / D3) — pure inline SVG.
    """
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    assert "matplotlib" not in r.text.lower()
    assert "chart.js" not in r.text.lower()
    assert "d3.min.js" not in r.text.lower()


# ---------------------------------------------------------------------------
# Slice B (B3) — small-multiples: three scale-separated SVG panels
# ---------------------------------------------------------------------------

_GRADE_NAMES = (
    "process_grade_rolling_N",
    "entry_grade_rolling_N",
    "management_grade_rolling_N",
    "exit_grade_rolling_N",
)


def _get(cfg, cfg_path):
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        return client.get("/metrics/process-grade-trend")


def test_three_scale_separated_panels_present_when_drawable(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    assert r.status_code == 200
    for name in ("grades", "rate", "cost"):
        assert f'data-panel="{name}"' in r.text


def test_each_series_renders_in_its_own_panel(seeded_db):
    """Anti-regression guard against 'leave everything in grades + add empty
    panels' (Codex R2-M2 / R3-m1): each series renders ONLY in its panel."""
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    grades = _panel(r.text, "grades")
    rate = _panel(r.text, "rate")
    cost = _panel(r.text, "cost")
    for n in _GRADE_NAMES:
        assert f'data-series="{n}"' in grades
        assert f'data-series="{n}"' not in rate + cost
    assert 'data-series="disqualifying_violation_rate_rolling_N"' in rate
    assert 'data-series="disqualifying_violation_rate_rolling_N"' not in grades + cost
    assert 'data-series="mistake_cost_R_rolling_N_per_trade"' in cost
    assert 'data-series="mistake_cost_R_rolling_N_per_trade"' not in grades + rate
    # _total charts in NO svg panel (table-only).
    for p in (grades, rate, cost):
        assert 'data-series="mistake_cost_R_rolling_N_total"' not in p


def test_grades_legend_names_all_four_series(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    leg = _legend(r.text)
    for label in ("process", "entry", "management", "exit"):
        assert f'>{label}<' in leg or f'>{label} ' in leg
    # ASCII discipline (#16/#32): NO middle-dot anywhere in the response.
    assert "·" not in r.text
    for name in _GRADE_NAMES:
        assert f'process-grade-legend-swatch metric-{name}' in leg


def test_rate_panel_axis_and_line(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    rate = _panel(r.text, "rate")
    assert 'data-marker="rate-axis"' in rate
    assert "0.0" in rate and "1.0" in rate


def test_cost_panel_axis_line_and_caption(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    cost = _panel(r.text, "cost")
    assert 'data-marker="cost-axis"' in cost
    assert 'data-marker="cost-axis-caption"' in cost
    assert "running total in table below" in cost


def test_total_cost_in_table_row(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    assert 'data-metric="mistake_cost_R_rolling_N_total"' in r.text


def test_under_floor_captions_render_for_partial_window(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_n_reviewed_trades(cfg.paths.db_path, n=3)
    r = _get(cfg, cfg_path)
    rate = _panel(r.text, "rate")
    cost = _panel(r.text, "cost")
    assert 'data-marker="rate-under-floor"' in rate
    assert 'data-marker="cost-under-floor"' in cost
    # Literal ASCII '>=' in static template text (Codex R1-M1), NOT &gt;.
    assert ">=5 effective samples" in rate
    # Under-floor: no line in ANY panel (route test 6 family).
    assert "<polyline" not in r.text


# ---------------------------------------------------------------------------
# Slice B (B4) — structural sweep residuals
# ---------------------------------------------------------------------------

def test_empty_state_still_wraps_all_panels_when_no_trades(seeded_db):
    """The empty-state guard short-circuits all three panels (not just one)."""
    cfg, cfg_path = seeded_db
    r = _get(cfg, cfg_path)
    assert r.status_code == 200
    assert 'data-empty-state="process-grade-trend"' in r.text
    for name in ("grades", "rate", "cost"):
        assert f'data-panel="{name}"' not in r.text


def test_cost_axis_all_zero_renders_nondegenerate_labels_route(seeded_db):
    """Route companion to the B2 VM test — exercises the production VM->template
    path (not stubs). All-zero cost -> [0,1] fallback -> non-degenerate labels
    0.00/0.50/1.00 scoped to the cost panel (Codex R2-m1), NOT three '0.00'."""
    cfg, cfg_path = seeded_db
    # The default seed (grade B, realized_R_if_plan_followed=1.0, no
    # disqualifying) yields all-zero per-trade mistake cost.
    _seed_n_reviewed_trades(cfg.paths.db_path, n=5)
    r = _get(cfg, cfg_path)
    cost = _panel(r.text, "cost")
    assert "0.00" in cost
    assert "0.50" in cost
    assert "1.00" in cost
