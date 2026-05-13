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

import sqlite3

from fastapi.testclient import TestClient

from swing.web.app import create_app


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
