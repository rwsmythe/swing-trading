"""GET /trades/open/{trade_id}/expand and /row — open-positions HTMX
click-to-expand (Tier-2 #3).

Mirrors the existing watchlist /expand + /row pattern but uses trade_id as
the route key (more unambiguous than ticker — defends against the future
"could you have two trades for the same ticker?" edge). Reuses
chart_scope.resolve_chart_scope for the chart-unavailable reason messages.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _insert_pipeline_run(conn, *, started_ts, finished_ts, data_asof_date,
                         charts_status="ok", evaluation_run_id=None) -> int:
    cur = conn.execute(
        """INSERT INTO pipeline_runs
           (started_ts, finished_ts, trigger, data_asof_date,
            action_session_date, state, lease_token, charts_status,
            evaluation_run_id)
           VALUES (?, ?, 'manual', ?, ?, 'complete', 't-x', ?, ?)""",
        (started_ts, finished_ts, data_asof_date, data_asof_date,
         charts_status, evaluation_run_id),
    )
    return int(cur.lastrowid)


def _insert_eval_run(conn, *, run_ts, data_asof_date) -> int:
    cur = conn.execute(
        """INSERT INTO evaluation_runs
           (run_ts, data_asof_date, action_session_date, finviz_csv_path,
            tickers_evaluated, aplus_count, watch_count, skip_count,
            excluded_count, error_count, rs_universe_version, rs_universe_hash)
           VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 'v1', 'd')""",
        (run_ts, data_asof_date, data_asof_date),
    )
    return int(cur.lastrowid)


def _insert_chart_target(conn, *, pipeline_run_id, ticker,
                         source="aplus", chart_status="ok"):
    conn.execute(
        """INSERT INTO pipeline_chart_targets
           (pipeline_run_id, ticker, source, chart_status)
           VALUES (?, ?, ?, ?)""",
        (pipeline_run_id, ticker, source, chart_status),
    )


def _write_chart(charts_dir: Path, *, date: str, ticker: str) -> Path:
    target = charts_dir / date / f"{ticker}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stub")
    return target


def _insert_open_trade(conn, *, ticker: str, entry_date: str = "2026-04-20",
                       status: str = "open") -> int:
    cur = conn.execute(
        """INSERT INTO trades
           (ticker, entry_date, entry_price, initial_shares,
            initial_stop, current_stop, status,
            watchlist_entry_target, watchlist_initial_stop, notes)
           VALUES (?, ?, 100.0, 10, 90.0, 90.0, ?, NULL, NULL, NULL)""",
        (ticker, entry_date, status),
    )
    return int(cur.lastrowid)


def _seed_in_scope_trade(cfg, *, ticker: str = "AAPL",
                          data_asof: str = "2026-04-17") -> int:
    """Seed an open trade whose ticker is in chart-scope, plus a chart PNG.
    Returns trade_id.
    """
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_id = _insert_eval_run(
                conn, run_ts=f"{data_asof}T21:30:00", data_asof_date=data_asof,
            )
            run_id = _insert_pipeline_run(
                conn, started_ts=f"{data_asof}T21:00:00",
                finished_ts=f"{data_asof}T21:55:00",
                data_asof_date=data_asof, evaluation_run_id=eval_id,
            )
            _insert_chart_target(
                conn, pipeline_run_id=run_id, ticker=ticker,
                source="aplus", chart_status="ok",
            )
            trade_id = _insert_open_trade(conn, ticker=ticker)
    finally:
        conn.close()
    _write_chart(cfg.paths.charts_dir, date=data_asof, ticker=ticker)
    return trade_id


def _seed_out_of_scope_trade(cfg, *, ticker: str = "DHC",
                              data_asof: str = "2026-04-17") -> int:
    """Seed an open trade whose ticker is NOT in chart-scope. Returns trade_id."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            eval_id = _insert_eval_run(
                conn, run_ts=f"{data_asof}T21:30:00", data_asof_date=data_asof,
            )
            _insert_pipeline_run(
                conn, started_ts=f"{data_asof}T21:00:00",
                finished_ts=f"{data_asof}T21:55:00",
                data_asof_date=data_asof, evaluation_run_id=eval_id,
            )
            # Different ticker in chart_targets — DHC is NOT a target.
            run_id_row = conn.execute(
                "SELECT id FROM pipeline_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            _insert_chart_target(
                conn, pipeline_run_id=run_id_row[0], ticker="MSFT",
                source="aplus", chart_status="ok",
            )
            trade_id = _insert_open_trade(conn, ticker=ticker)
    finally:
        conn.close()
    return trade_id


def _patch_price_cache(monkeypatch):
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)


# ---------------------------------------------------------------------------
# View-model + builder tests
# ---------------------------------------------------------------------------

def test_build_open_positions_expanded_in_scope(seeded_db):
    """In-scope trade returns VM with chart available (chart_reason None)."""
    from swing.web.view_models.open_positions_row import build_open_positions_expanded
    cfg, _ = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()
    assert vm is not None
    assert vm.trade_id == trade_id
    assert vm.ticker == "AAPL"
    assert vm.data_asof_date == "2026-04-17"
    assert vm.chart_reason is None
    assert vm.chart_reason_message is None


def test_build_open_positions_expanded_out_of_scope(seeded_db):
    """Out-of-scope trade returns VM with chart_reason='out-of-scope'."""
    from swing.web.view_models.open_positions_row import build_open_positions_expanded
    cfg, _ = seeded_db
    trade_id = _seed_out_of_scope_trade(cfg, ticker="DHC")
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()
    assert vm is not None
    assert vm.ticker == "DHC"
    assert vm.chart_reason == "out-of-scope"
    assert "charting scope" in (vm.chart_reason_message or "")


def test_build_open_positions_expanded_closed_trade_returns_none(seeded_db):
    """Closed trade → builder returns None (route 404s)."""
    from swing.web.view_models.open_positions_row import build_open_positions_expanded
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _insert_open_trade(conn, ticker="AAPL", status="closed")
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()
    assert vm is None


def test_build_open_positions_expanded_unknown_id_returns_none(seeded_db):
    """Nonexistent trade id → builder returns None."""
    from swing.web.view_models.open_positions_row import build_open_positions_expanded
    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=99999)
    finally:
        conn.close()
    assert vm is None


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_expand_route_in_scope_renders_chart_img(seeded_db, monkeypatch):
    """In-scope trade → expand fragment contains <img src="/charts/<date>/<ticker>.png">"""
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:200]
    body = r.text
    # Chart-display block — img with date-prefixed URL.
    assert '<img src="/charts/2026-04-17/AAPL.png"' in body
    # No chart-unavailable placeholder for the in-scope path.
    assert 'class="chart-unavailable"' not in body


def test_expand_route_out_of_scope_renders_unavailable(seeded_db, monkeypatch):
    """Out-of-scope trade → expand fragment contains chart-unavailable div
    with the resolver's reason message + reason data attribute.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_out_of_scope_trade(cfg, ticker="DHC")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:200]
    body = r.text
    assert 'class="chart-unavailable"' in body
    assert 'data-chart-reason="out-of-scope"' in body
    # No <img src="/charts/ when chart unavailable.
    assert '<img src="/charts/' not in body


def test_expand_route_closed_trade_404(seeded_db, monkeypatch):
    """Closed trade → 404."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade_id = _insert_open_trade(conn, ticker="AAPL", status="closed")
    finally:
        conn.close()
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404


def test_expand_route_unknown_id_404(seeded_db, monkeypatch):
    """Nonexistent trade id → 404."""
    cfg, cfg_path = seeded_db
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/trades/open/99999/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404


def test_row_route_returns_compact_tr(seeded_db, monkeypatch):
    """GET /trades/open/<id>/row returns the compact open-positions row
    partial (the close-button collapse target). Mirrors the watchlist /row
    contract: starts with <tr (HTMX swaps into <tbody>).
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/row",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200, r.text[:200]
    body = r.text.lstrip()
    assert body.startswith("<tr"), (
        f"compact row must be a <tr> (HTMX swaps it into <tbody>); got: "
        f"{body[:80]!r}"
    )
    assert "AAPL" in body
    assert f'id="open-position-{trade_id}"' in body


def test_row_route_unknown_id_404(seeded_db, monkeypatch):
    """Unknown trade id → /row 404."""
    cfg, cfg_path = seeded_db
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/trades/open/99999/row",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Partial / row template assertions
# ---------------------------------------------------------------------------

def test_expanded_partial_has_close_button(seeded_db, monkeypatch):
    """Expanded fragment must include a close button (class=close-expanded)
    whose hx-get points at /trades/open/<id>/row, with stopPropagation so
    the close click does not also re-trigger the row's expand binding.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200
    body = r.text
    assert 'class="close-expanded"' in body
    assert f'hx-get="/trades/open/{trade_id}/row"' in body
    assert "stopPropagation" in body


def test_open_positions_row_has_click_to_expand(seeded_db, monkeypatch):
    """Compact open-positions row must carry HTMX click-to-expand attributes
    on the <tr> so clicking the row fires GET /trades/open/<id>/expand.

    Pre-fix discriminator: row has no hx-get attr → assertion fails.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200, r.text[:200]
    body = r.text
    assert f'hx-get="/trades/open/{trade_id}/expand"' in body, (
        "open-positions <tr> must have hx-get='/trades/open/<id>/expand' "
        "to fire the expand on click. Body excerpt does not contain it."
    )


def test_open_positions_row_action_buttons_stop_propagation(seeded_db, monkeypatch):
    """Bug-1 lesson: the row <tr> has hx-get; the Exit/Adjust buttons inside
    must include event.stopPropagation() so clicking a button does NOT also
    trigger the row's expand binding.
    """
    cfg, cfg_path = seeded_db
    _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # Locate Exit button HTML and verify stopPropagation is present.
    exit_idx = body.find(">Exit</button>")
    assert exit_idx != -1, "Exit button not rendered"
    button_open = body.rfind("<button", 0, exit_idx)
    assert button_open != -1
    button_html = body[button_open:exit_idx]
    assert "stopPropagation" in button_html, (
        "Exit button must stop click propagation so it does not also trigger "
        "the parent <tr>'s hx-get='/trades/open/<id>/expand'. "
        f"Got: {button_html!r}"
    )
    # Same for Adjust stop button.
    adjust_idx = body.find(">Adjust stop</button>")
    assert adjust_idx != -1, "Adjust stop button not rendered"
    button_open2 = body.rfind("<button", 0, adjust_idx)
    button_html2 = body[button_open2:adjust_idx]
    assert "stopPropagation" in button_html2, (
        "Adjust stop button must stop click propagation. "
        f"Got: {button_html2!r}"
    )


def test_build_open_positions_expanded_uses_binding_not_re_read(
    seeded_db, monkeypatch,
):
    """build_open_positions_expanded uses binding.data_asof_date for the VM
    output, NOT a re-read of pipeline_runs. Mirrors the charts-route test
    pattern.

    Setup: seed two completed runs with different data_asof_date values.
    Seed an open trade for a ticker that is in runN's chart_targets but NOT
    in runN+1's. Monkeypatch
    `swing.web.view_models.open_positions_row.latest_completed_pipeline_run`
    to return runN's binding.

    Discriminating verification: pre-fix code did its own SELECT on
    pipeline_runs (returns runN+1's data_asof_date) AND the resolver re-read
    (returns runN+1's chart_targets, where AAPL is NOT present → 'out-of-scope').
    Post-fix the binding pins both reads to runN: data_asof matches runN's
    AND chart_reason is None.
    """
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.chart_scope import PipelineRunBinding
    from swing.web.view_models.open_positions_row import (
        build_open_positions_expanded,
    )

    cfg, _cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Eval runs first (FK-backed path requires evaluation_run_id to be
            # non-NULL on each pipeline_run).
            conn.execute(
                """INSERT INTO evaluation_runs (id, run_ts, data_asof_date,
                                                 action_session_date, finviz_csv_path,
                                                 tickers_evaluated, aplus_count,
                                                 watch_count, skip_count, excluded_count,
                                                 error_count, rs_universe_version,
                                                 rs_universe_hash)
                   VALUES (350, '2026-04-01T09:00:00', '2026-04-01', '2026-04-02', NULL,
                           1, 1, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            conn.execute(
                """INSERT INTO evaluation_runs (id, run_ts, data_asof_date,
                                                 action_session_date, finviz_csv_path,
                                                 tickers_evaluated, aplus_count,
                                                 watch_count, skip_count, excluded_count,
                                                 error_count, rs_universe_version,
                                                 rs_universe_hash)
                   VALUES (351, '2026-04-02T09:00:00', '2026-04-02', '2026-04-03', NULL,
                           1, 1, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            # Two runs, different dates; AAPL in-scope ONLY for runN — eval id 350.
            conn.execute(
                """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                               data_asof_date, action_session_date,
                                               charts_status, evaluation_run_id,
                                               trigger, lease_token)
                   VALUES (300, '2026-04-01T09:00:00', '2026-04-01T09:30:00',
                           'complete', '2026-04-01', '2026-04-02', 'ok', 350,
                           'manual', 'tok-300')""",
            )
            conn.execute(
                """INSERT INTO pipeline_chart_targets
                   (pipeline_run_id, ticker, source, chart_status)
                   VALUES (300, 'AAPL', 'open_position', 'ok')""",
            )
            conn.execute(
                """INSERT INTO pipeline_runs (id, started_ts, finished_ts, state,
                                               data_asof_date, action_session_date,
                                               charts_status, evaluation_run_id,
                                               trigger, lease_token)
                   VALUES (301, '2026-04-02T09:00:00', '2026-04-02T09:30:00',
                           'complete', '2026-04-02', '2026-04-03', 'ok', 351,
                           'manual', 'tok-301')""",
            )
            # Open AAPL trade. Trade dataclass fields per swing/data/models.py;
            # `notes` and `hypothesis_label` default-None acceptable.
            trade = Trade(
                id=None, ticker="AAPL", entry_date="2026-04-01",
                entry_price=100.0, initial_shares=10, initial_stop=95.0,
                current_stop=95.0, status="open",
                watchlist_entry_target=100.0,
                watchlist_initial_stop=95.0,
                notes=None,
                hypothesis_label=None,
            )
            trade_id = insert_trade_with_event(
                conn, trade, event_ts="2026-04-01T09:35:00",
            )
        # Place PNG on disk for runN's date.
        (cfg.paths.charts_dir / "2026-04-01").mkdir(parents=True, exist_ok=True)
        (cfg.paths.charts_dir / "2026-04-01" / "AAPL.png").write_bytes(b"png-stub")

        runN_binding = PipelineRunBinding(
            run_id=300, finished_ts="2026-04-01T09:30:00",
            data_asof_date="2026-04-01", charts_status="ok",
            evaluation_run_id=350,
        )
        monkeypatch.setattr(
            "swing.web.view_models.open_positions_row.latest_completed_pipeline_run",
            lambda _conn: runN_binding,
        )

        vm = build_open_positions_expanded(conn=conn, cfg=cfg, trade_id=trade_id)
    finally:
        conn.close()

    assert vm is not None
    assert vm.data_asof_date == "2026-04-01", (
        f"expected runN's data_asof; got {vm.data_asof_date!r}; "
        "regression: builder did its own SELECT on pipeline_runs"
    )
    assert vm.chart_reason is None, (
        f"expected chart-available (binding=runN, AAPL in runN's targets); "
        f"got reason={vm.chart_reason!r} message={vm.chart_reason_message!r}; "
        "regression: resolver re-read pipeline_runs and bound to runN+1"
    )


def test_expanded_partial_colspan_matches_row(seeded_db, monkeypatch):
    """The expanded <tr>'s <td colspan=N> must match the compact row's
    actual <td> count. A mismatch breaks the table layout (cells overflow
    into adjacent columns or leave gaps).

    Compact row has 10 <td> cells (Ticker, Entry date, Entry price, Shares,
    Current stop, Last, Sector, Industry, Advisory, Actions). Expanded must
    use colspan="10". (Sector + Industry added in Task 9.)
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200
    body = r.text
    assert 'colspan="10"' in body, (
        "expanded row must use colspan='10' to match the 10-cell compact row; "
        f"body excerpt: {body[:200]!r}"
    )


def test_open_position_row_target_500_renders_colspan_10(
    seeded_db, monkeypatch,
):
    """Codex R3 Major-1 — when the global exception handler renders
    `trade_form_error.html.j2` for an `open-position-*` HX-Target, the <td>
    must be `colspan="10"` to match the 10-column open-positions table
    layout (Ticker / Entry date / Entry price / Shares / Current stop /
    Last / Sector / Industry / Advisory / Actions).

    Discriminating: pre-fix `_row_error_colspan` returned 9 for
    `hyp-rec-row-*` and 8 for everything else (including
    `open-position-*`), leaving a 2-cell short row in the 10-col
    open-positions table on every server-error swap.
    """
    cfg, cfg_path = seeded_db
    trade_id = _seed_in_scope_trade(cfg, ticker="AAPL")
    _patch_price_cache(monkeypatch)

    # Force the open-positions expand route to raise so the global
    # exception handler renders trade_form_error.html.j2.
    from swing.web.routes import trades as trades_route

    def _boom(*args, **kwargs):
        raise RuntimeError("forced 500 for open-position row-target test")

    monkeypatch.setattr(trades_route, "build_open_positions_expanded", _boom)

    app = create_app(cfg, cfg_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(
            f"/trades/open/{trade_id}/expand",
            headers={
                "HX-Request": "true",
                "HX-Target": f"open-position-{trade_id}",
            },
        )
    assert resp.status_code == 500, resp.text
    body = resp.text
    assert 'colspan="10"' in body, (
        "open-position-* row-target error fragment must render colspan=10 "
        "(10-col open-positions table); pre-fix renders colspan=8.\nBody:\n"
        + body[:600]
    )


def test_open_positions_row_renders_sector_industry(seeded_db, monkeypatch):
    """Open positions row renders Sector + Industry from trade.sector / .industry.
    Sentinel 'OP-Sector-T9' / 'OP-Industry-T9' guards against default-string
    masks."""
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, sector="OP-Sector-T9", industry="OP-Industry-T9",
            ), event_ts="2026-04-15T09:30:00")
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
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "OP-Sector-T9" in body
    assert "OP-Industry-T9" in body


def test_open_positions_expanded_colspan_matches_new_row_cell_count():
    """colspan in open_positions_expanded.html.j2 must match the cell count
    in open_positions_row.html.j2 — was 8, becomes 10 with sector + industry.
    """
    from pathlib import Path
    expanded = Path("swing/web/templates/partials/open_positions_expanded.html.j2").read_text(encoding="utf-8")
    assert 'colspan="10"' in expanded, (
        "colspan must be 10 to match open_positions_row.html.j2's 10 cells "
        "(Ticker, Entry date, Entry price, Shares, Current stop, Last, "
        "Sector, Industry, Advisory, Actions)."
    )
