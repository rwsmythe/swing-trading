"""POST /latches/orders -- the lazy broker-order-awareness fragment.

It is a POST, NOT a GET (plan D.1): it performs an AUDITED external Schwab call
that inserts a `schwab_api_calls` row. Calling it GET would be a lie about the
method's safety and would contradict A4 inside the arc that asserts A4.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)
ANCHOR = "2026-07-27"     # action_session_for_run(NOW)
_HX = {"HX-Request": "true"}


def _post_orders(client, anchor=ANCHOR):
    """The fragment carries the RENDER-TIME session anchor, exactly as the
    panel template emits it via hx-vals."""
    data = {} if anchor is None else {"view_session_date": anchor}
    return client.post("/latches/orders", headers=_HX, data=data)

# Every DOMAIN table the fragment must NOT touch. `schwab_api_calls` is the
# only row it may write.
_DOMAIN_TABLES = (
    "trades", "fills", "latch_view_events", "candidates", "evaluation_runs",
    "reconciliation_runs", "reconciliation_discrepancies",
    "reconciliation_corrections", "account_equity_snapshots", "trade_events",
)


def _seed_ftre(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, 0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
    conn.close()


@pytest.fixture
def frozen_panel_clock(monkeypatch):
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)


def _counts(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in _DOMAIN_TABLES
        }
    finally:
        conn.close()


class _Holder:
    """Stands in for the app's SchwabClientHolder (the 18-H.4 borrow seam)."""

    def __init__(self, client, *, record=None):
        self._client = client
        self._record = record if record is not None else []

    def borrow(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            self._record.append("borrowed")
            yield self._client

        return _cm()


def _order(**over):
    base = dict(order_id="1", status="WORKING", enter_time="2026-07-20T13:30:00Z",
                instrument_symbol="FTRE", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", price=18.89, stop_price=18.34)
    base.update(over)
    return SchwabOrderResponse(**base)


def _app(cfg, cfg_path, monkeypatch, *, environment="production", orders=None,
         raises=None, holder_client=object(), install_holder=True, record=None):
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(
        vm_mod, "_resolve_schwab_environment", lambda _cfg: environment)
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _cfg: "HASH")

    def _fetch(client, conn, account_hash, from_dt, to_dt, **kwargs):
        if raises is not None:
            raise raises
        return list(orders or [])

    monkeypatch.setattr(vm_mod, "_fetch_account_orders", _fetch)
    app = create_app(cfg, cfg_path)
    if install_holder:
        app.state.schwab_client_holder = _Holder(holder_client, record=record)
    elif hasattr(app.state, "schwab_client_holder"):
        delattr(app.state, "schwab_client_holder")
    return app


def test_a_get_on_the_orders_path_is_405(seeded_db):
    """Codex R4-1: the fragment makes an AUDITED Schwab call, so it is NOT a
    safe method. A GET route would expose a real broker call to browser
    prefetch and would contradict A4 inside the arc that asserts it."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.get("/latches/orders").status_code == 405


def test_the_fragment_requires_the_hx_request_header(seeded_db):
    """OriginGuard strict mode (swing/web/app.py) applies to this POST as it
    does to the beacon."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.post("/latches/orders").status_code == 403


def test_fragment_reports_sandbox_short_circuit_without_constructing_a_client(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The sandbox short-circuit fires FIRST, mirroring
    swing/trades/entry_auto_fill.py -- so the sandbox path is provably
    side-effect-free."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    record: list = []
    app = _app(cfg, cfg_path, monkeypatch, environment="sandbox", record=record)
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "sandbox" in r.text.lower()
    assert record == [], "the sandbox path must not borrow a client"


def test_fragment_degrades_when_no_schwab_client_holder_is_installed(
        seeded_db, monkeypatch, frozen_panel_clock):
    """A test config has no credentials, so the holder is absent."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, install_holder=False)
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "unavailable" in r.text.lower()


def test_fragment_suppresses_alarms_when_the_order_book_is_unknown(
        seeded_db, monkeypatch, frozen_panel_clock):
    """An unknown order book must NOT fire a false LATCH_ARMED_NO_RESTING_ORDER
    -- a false all-clear and a false alarm are both worse than an honest
    'unknown'."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, install_holder=False)
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_fragment_fires_the_ftre_alarm_when_the_order_book_is_known_and_empty(
        seeded_db, monkeypatch, frozen_panel_clock):
    """THE FTRE failure mode: armed latch, zero resting orders."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" in r.text
    assert "FTRE" in r.text


def test_fragment_is_quiet_when_a_matching_order_is_resting(
        seeded_db, monkeypatch, frozen_panel_clock):
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text
    assert "ORDER_RESTING_LATCH_CLEARED" not in r.text


def test_fragment_borrows_the_client_through_the_holder(
        seeded_db, monkeypatch, frozen_panel_clock):
    """18-H.4: the client must be taken via holder.borrow() so a concurrent
    /schwab/setup drain can finish before the tokens-DB rename."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    record: list = []
    app = _app(cfg, cfg_path, monkeypatch, orders=[], record=record)
    with TestClient(app) as client:
        _post_orders(client)
    assert record == ["borrowed"]


def test_fragment_returns_200_with_a_degraded_block_on_a_schwab_api_error(
        seeded_db, monkeypatch, frozen_panel_clock):
    """And the message names the exception TYPE only -- never the message
    (the redaction discipline)."""
    from swing.integrations.schwab.client import SchwabApiError
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               raises=SchwabApiError(500, "SECRETTOKEN leaked"))
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "SchwabApiError" in r.text
    assert "SECRETTOKEN" not in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_fragment_root_is_not_a_table_row(seeded_db, monkeypatch,
                                          frozen_panel_clock):
    """The HTMX makeFragment synthetic-table-wrap gotcha: a fragment whose
    root is `<tr>` gets its content DROPPED inside an OOB section."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert not r.text.strip().lower().startswith("<tr")


def test_the_fragment_writes_only_schwab_audit_and_no_domain_row(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Snapshot the row count of EVERY domain table before and after; only
    schwab_api_calls may change."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    before = _counts(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        _post_orders(client)
    assert _counts(cfg) == before


def test_the_panel_get_writes_nothing_at_all(seeded_db, frozen_panel_clock):
    """The companion assertion: GET /latches touches neither
    latch_view_events NOR schwab_api_calls (it makes no Schwab call -- the
    order join is lazy)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert client.get("/latches").status_code == 200
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 0
    finally:
        conn.close()


def test_fragment_renders_the_stale_order_alarm_for_an_invalidated_latch(
        seeded_db, monkeypatch, frozen_panel_clock, tmp_path):
    """The inverse alarm: a resting order matching a latch cleared by
    INVALIDATION is the operator's one manual duty."""
    import pandas as pd
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    # A close below the frozen 14.88 stop invalidates the latch.
    cfg.paths.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": "2026-07-21", "open": 15.0, "high": 15.2, "low": 14.0,
         "close": 14.00, "volume": 100.0},
    ]).to_parquet(cfg.paths.prices_cache_dir / "FTRE.yfinance.parquet")
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "ORDER_RESTING_LATCH_CLEARED" in r.text
    assert "invalidation" in r.text


def test_the_fragment_suppresses_alarms_when_the_render_anchor_is_missing(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R1: without the render-time anchor the fragment would
    derive at its OWN clock, so after a session rollover (or on a restored
    page) it could render alarms for session S+1 while the visible latch cards
    still describe S -- the panel contradicting itself about which mandates are
    live. Suppression is the safe direction."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=None)
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text
    assert "reload" in r.text.lower()


def test_the_fragment_suppresses_alarms_on_a_stale_render_anchor(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Same defence for a RESTORED page: an anchor more than one session behind
    the current action session cannot describe the live order picture."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client, anchor="2026-07-01")
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_the_panel_emits_the_orders_anchor_so_the_fragment_agrees_with_the_cards(
        seeded_db, frozen_panel_clock):
    """The two halves of the page must describe the SAME session."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        body = client.get("/latches").text
    assert 'hx-post="/latches/orders"' in body
    # Jinja autoescapes the JSON's double quotes inside the single-quoted
    # hx-vals attribute; the browser un-escapes them before HTMX parses it.
    import html
    assert f'"view_session_date": "{ANCHOR}"' in html.unescape(body)


def test_a_mispriced_order_does_not_render_a_false_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R2 CRITICAL. `LATCH_ARMED_NO_RESTING_ORDER` is keyed on
    TICKER-LEVEL absence (plan A.9) so a mispriced order does not produce a
    factually false "no order" alarm -- but that means a wrong-price order
    SILENCES the alarm. If the disagreement is then discarded, the fragment
    renders "orders agree" over a mandate that is NOT covered: a false
    all-clear, the exact failure this arc exists to prevent.

    FTRE is armed at pivot 18.34 / cap 18.89; the broker order is 18.59 / 19.15."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(price=19.15, stop_price=18.59)])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "Broker orders agree" not in r.text
    assert "ORDER PRICE MISMATCH" in r.text
    assert "18.34" in r.text and "18.89" in r.text


def test_a_correctly_priced_order_still_reads_as_agreeing(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator: the all-clear must still be reachable, or the
    mismatch banner is just noise."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "Broker orders agree" in r.text
    assert "ORDER PRICE MISMATCH" not in r.text


def test_the_order_query_window_reaches_back_to_the_oldest_latch_anchor(
        seeded_db, monkeypatch):
    """Codex executing R2 CRITICAL. `get_account_orders` filters on ENTERED
    TIME and a GTC entry order is entered on the FIRE date, so a fixed
    30-CALENDAR-day window is too short for a 30-SESSION mandate (30 sessions
    is ~42 calendar days). Late in a mandate's life the very order that
    satisfies it would drop out of the query -- firing a FALSE
    LATCH_ARMED_NO_RESTING_ORDER and silencing a genuine stale-order alarm.

    FTRE fires 2026-07-20; at a 2026-08-28 clock the window must still reach
    back past the fire date."""
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    seen: dict = {}

    monkeypatch.setattr(vm_mod, "_resolve_schwab_environment", lambda _c: "production")
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _c: "HASH")
    # Freeze BOTH clocks well past the fire so the anchor is CURRENT (a future
    # anchor would be rejected before the fetch is ever reached).
    import swing.web.routes.latches as route_mod
    later = datetime(2026, 8, 28, 9, 0)
    monkeypatch.setattr(vm_mod, "_now", lambda: later)
    monkeypatch.setattr(route_mod, "_now", lambda: later)

    def _fetch(client, conn, account_hash, from_dt, to_dt, **kwargs):
        seen["from_dt"] = from_dt
        return []

    monkeypatch.setattr(vm_mod, "_fetch_account_orders", _fetch)
    app = create_app(cfg, cfg_path)
    app.state.schwab_client_holder = _Holder(object())
    with TestClient(app) as client:
        _post_orders(client, anchor="2026-08-28")

    assert seen["from_dt"].date() < date(2026, 7, 20), (
        "the entered-time window must reach back past the fire date; "
        f"got {seen['from_dt']}")


def test_the_order_query_window_is_bounded():
    """The ceiling: a pathological anchor must not ask Schwab for years."""
    from swing.latches.models import FireRow
    from swing.latches.service import derive_latches
    from swing.web.view_models.latches import (
        _ORDER_LOOKBACK_MAX_DAYS,
        _order_lookback_days,
    )

    ancient = FireRow(
        candidate_id=1, evaluation_run_id=1, ticker="OLD", pivot=10.0,
        initial_stop=8.0, action_session_date="2019-01-02",
        run_ts="2019-01-01T21:00:00", pipeline_run_id=None)
    latches = derive_latches(
        fires=[ancient], bars_by_ticker={"OLD": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches
    assert _order_lookback_days(
        latches, now=datetime(2026, 7, 27, 9, 0)) == _ORDER_LOOKBACK_MAX_DAYS
    assert _order_lookback_days((), now=datetime(2026, 7, 27, 9, 0)) == 30
