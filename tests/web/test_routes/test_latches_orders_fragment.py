"""POST /latches/orders -- the lazy broker-order-awareness fragment.

It is a POST, NOT a GET (plan D.1): it performs an AUDITED external Schwab call
that inserts a `schwab_api_calls` row. Calling it GET would be a lie about the
method's safety and would contradict A4 inside the arc that asserts A4.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

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

# THE PAGE-LEVEL ALL-CLEAR MARKER, named ONCE (Arc 21-B, B6).
#
# 21-A's marker was the literal "Broker orders agree with the live latches",
# which the SEPARATED-CLAIMS construction removed: the alarm all-clear is not
# SCOPED at all -- it is COMPLETE -- and the scoped sentence also produced a
# VACUOUS zero-case ("No alarms among the 0 latches form-checked") in the
# ~7-hour window when nothing has been form-checked yet.
#
# NAMED rather than inlined at ~26 sites, because those sites include NEGATIVE
# assertions: if the production string changes and the test literal does not,
# every `not in` assertion goes VACUOUSLY TRUE and stops testing anything --
# the silent-decay failure the roster rule exists to stop.
_ALL_CLEAR = "No alarms."


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


def _write_archive_bars(cfg, ticker, rows):
    """Shape-A OHLCV archive bars for `ticker`, as `(iso_session, close)`.

    THE ARCHIVE IS THE ONLY READ-SIDE SOURCE THAT DATES A CLOSE PER ROW, and
    the derivation already loads it. Shape A (`{T}.yfinance.parquet`) is
    deliberate: the panel reads with `migrate=False` (the A4 no-write
    property), so a legacy `{T}.parquet` is invisible here exactly as it is in
    production."""
    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


@pytest.fixture
def frozen_panel_clock(monkeypatch):
    """Freeze BOTH clocks. The order fragment requires the posted anchor to be
    the CURRENT action session, so the ROUTE clock must be pinned too -- leaving
    it on the wall clock makes these tests time-of-day dependent."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


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
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text
    assert "18.34" in r.text and "18.89" in r.text


def test_a_correctly_priced_order_still_reads_as_agreeing(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator: the all-clear must still be reachable, or the
    mismatch banner is just noise.

    The derivation-session close is seeded so the REGIME is determinable: after
    the RD 2026-07-27 undeterminable-regime ruling an unrunnable shape check
    withholds the all-clear, and `_seed_ftre`'s own close is stamped 2026-07-17
    (four sessions before the 2026-07-24 derivation session), which would leave
    this test asserting agreement in the very state the ruling labels."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _ALL_CLEAR in r.text
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


def test_a_correct_order_does_not_mask_an_extra_stray_order(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R3 CRITICAL. With TWO resting BUY orders on the ticker --
    one correct, one at an unrelated price -- the agreement flags describe the
    CORRECT one (that is what 'is the mandate covered' means), so without
    per-order reporting the stray order is invisible and the page renders a
    clean all-clear while a real unexplained order sits at the broker."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    good = _order(order_id="good", price=18.89, stop_price=18.34)
    stray = _order(order_id="stray", price=17.51, stop_price=17.00)
    app = _app(cfg, cfg_path, monkeypatch, orders=[good, stray])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text
    assert "stray" in r.text
    assert "matches NO latch" in r.text
    # ...and it must NOT invent a false "no resting order" alarm: the mandate
    # IS covered by the good order.
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_an_indeterminate_order_is_rendered_not_silently_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R4. An indeterminate broker status correctly SUPPRESSES
    both alarms (a false all-clear and a false alarm are both worse than an
    honest 'unknown') -- but the suppression itself then reads as an all-clear
    unless the UNKNOWN is rendered."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(status="PENDING_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER STATUS INDETERMINATE" in r.text
    assert "verify at the broker" in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_a_one_session_stale_anchor_suppresses_the_order_alarms(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R6. The BEACON tolerates a one-session-stale anchor --
    correctly, because it records that a view HAPPENED, as of the session it
    happened in. The ORDER FRAGMENT must NOT: it joins the anchor's latch set to
    the LIVE broker book, so a stale anchor judges orders placed or cancelled
    AFTER that session against the older mandates, manufacturing or silencing an
    alarm. Alarms must describe ONE coherent moment.

    The anchor here (2026-07-24) is exactly ONE session behind the frozen
    current action session (2026-07-27) -- i.e. inside the beacon's tolerance
    and outside the fragment's."""
    from swing.evaluation.dates import sessions_behind
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    assert sessions_behind(date(2026, 7, 27), date(2026, 7, 24)) == 1
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client, anchor="2026-07-24")
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text
    assert "reload" in r.text.lower()


def test_a_stop_only_order_with_no_cap_is_not_read_as_agreement(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R7 CRITICAL. A plain BUY STOP at the pivot matches the
    latch on the stop leg, but carries NO limit leg -- so `order_limit_agrees`
    is None. `None` is UNKNOWN, and unknown is NOT agreement: the mandate is a
    stop trigger AND a cap at pivot x 1.03, and it is the CAP that stops the
    operator chasing. Reading that silence as agreement renders a false
    all-clear over a mandate with no chase protection."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    stop_only = _order(order_type="STOP", price=18.34, stop_price=18.34)
    app = _app(cfg, cfg_path, monkeypatch, orders=[stop_only])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text
    assert "UNKNOWN (leg absent)" in r.text


def test_the_broker_order_window_is_sent_as_utc_aware_datetimes(
        seeded_db, monkeypatch, frozen_panel_clock):
    """codex-auto-review (repo-access second eye). `trader._schwab_iso`
    converts an AWARE datetime to UTC but passes a NAIVE one through UNCHANGED
    and stamps 'Z' on it. A naive local `datetime.now()` is therefore
    transmitted as if it were UTC -- a TEN-HOUR skew on this HST deployment, so
    `to_entered_time` lands ten hours in the past and the query silently omits
    orders entered earlier the same day. That fires a FALSE
    LATCH_ARMED_NO_RESTING_ORDER for an order the operator actually placed that
    morning: the exact alarm this arc exists to make trustworthy.

    This is a defect the diff-only reviewer could not see -- it depends
    entirely on the behaviour of an UN-CHANGED helper."""
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    seen: dict = {}

    monkeypatch.setattr(vm_mod, "_resolve_schwab_environment", lambda _c: "production")
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _c: "HASH")

    def _fetch(client, conn, account_hash, from_dt, to_dt, **kwargs):
        seen["from_dt"], seen["to_dt"] = from_dt, to_dt
        return []

    monkeypatch.setattr(vm_mod, "_fetch_account_orders", _fetch)
    app = create_app(cfg, cfg_path)
    app.state.schwab_client_holder = _Holder(object())
    with TestClient(app) as client:
        _post_orders(client)

    for key in ("from_dt", "to_dt"):
        assert seen[key].tzinfo is not None, f"{key} must be timezone-AWARE"
        assert seen[key].utcoffset().total_seconds() == 0, f"{key} must be UTC"

    # And the formatter must round-trip it without shifting the instant.
    from swing.integrations.schwab.trader import _schwab_iso
    assert _schwab_iso(seen["to_dt"]).endswith("Z")


def test_an_indeterminate_order_on_a_cleared_only_ticker_is_still_rendered(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R14. The indeterminate SUPPRESSION is ticker-wide, but
    the BANNER was derived from LIVE latches only -- so a ticker carrying ONLY a
    cleared latch, a stale resting order, and an indeterminate order had its
    CRITICAL stale-order alarm suppressed with NO banner, and the page printed
    the all-clear. The suppression and the render now come from the SAME
    predicate over the SAME order set, so they cannot diverge."""
    import pandas as pd
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    # A close below the frozen 14.88 stop clears the ONLY latch on FTRE.
    cfg.paths.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": "2026-07-21", "open": 15.0, "high": 15.2, "low": 14.0,
         "close": 14.00, "volume": 100.0},
    ]).to_parquet(cfg.paths.prices_cache_dir / "FTRE.yfinance.parquet")

    stale = _order(order_id="stale", status="WORKING")
    unknown = _order(order_id="unknown", status="PENDING_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[stale, unknown])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER STATUS INDETERMINATE" in r.text
    assert "FTRE" in r.text


def test_the_suppression_and_the_banner_share_one_predicate(seeded_db):
    """The anti-drift pin: the fragment's banner set must be exactly the set the
    join suppresses on."""
    from swing.latches.models import RestingOrder
    from swing.latches.orders import indeterminate_order_tickers
    orders = (
        RestingOrder(order_id="1", ticker="AAA", instruction="BUY", quantity=1.0,
                     order_type="STOP_LIMIT", limit_price=1.0, stop_price=1.0,
                     status="PENDING_CANCEL"),
        RestingOrder(order_id="2", ticker="BBB", instruction="BUY", quantity=1.0,
                     order_type="STOP_LIMIT", limit_price=1.0, stop_price=1.0,
                     status="WORKING"),
        RestingOrder(order_id="3", ticker="CCC", instruction="SELL", quantity=1.0,
                     order_type="STOP_LIMIT", limit_price=1.0, stop_price=1.0,
                     status="UNKNOWN"),
    )
    # BUY + indeterminate only; a SELL never gates an ENTRY mandate.
    assert indeterminate_order_tickers(orders) == ("AAA",)


def test_a_day_order_at_the_right_prices_is_not_an_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex executing R15. Price agreement alone is NOT coverage. The settled
    semantics mandate a GTC stop-limit; a DAY order at exactly the right prices
    expires tonight and leaves the operator uncovered tomorrow -- which is the
    FTRE failure mode wearing an all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    day_order = _order(duration="DAY")
    app = _app(cfg, cfg_path, monkeypatch, orders=[day_order])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "not the mandated order shape" in r.text
    assert "GOOD_TILL_CANCEL" in r.text


def test_a_trailing_stop_at_the_right_prices_is_not_an_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """A trailing stop does not sit at the frozen pivot at all."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    trailing = _order(order_type="TRAILING_STOP_LIMIT",
                      duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[trailing])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _ALL_CLEAR not in r.text
    assert "not the mandated order shape" in r.text
    assert "TRAILING_STOP_LIMIT" in r.text


def test_a_gtc_stop_limit_at_the_right_prices_IS_an_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator: the mandated shape must still read clean, or
    the check is just noise.

    Seeded with a derivation-session close BELOW the pivot so the shape check
    actually RUNS (see `test_a_correctly_priced_order_still_reads_as_agreeing`):
    an undeterminable regime now withholds the all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    mandated = _order(order_type="STOP_LIMIT", duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mandated])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _ALL_CLEAR in r.text
    assert "not the mandated order shape" not in r.text


def test_an_absent_duration_is_not_asserted_against(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Deliberate conservatism: a payload that simply does not carry a duration
    is unknown-but-not-wrong, so the panel does not become permanently noisy on
    shapes it cannot see. Real Schwab payloads DO carry it.

    Seeded with a derivation-session close so the regime is determinable (see
    `test_a_correctly_priced_order_still_reads_as_agreeing`)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order()])   # duration None
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _ALL_CLEAR in r.text


# --- RD ruling 2026-07-27: the pullback form, end to end -------------------
def _seed_close_above_the_pivot(cfg):
    """FTRE's real geometry after the 2026-07-23 broker rejection: the latch is
    still frozen at pivot 18.34 / zone cap 18.89, but price has run ABOVE the
    pivot (the 2026-07-24 close, 19.52).

    A NON-aplus row, so it supplies the panel's rendered last close WITHOUT
    adding a second fire to the derivation.

    Arc 21-G: it also writes the CORROBORATING archive bar, because the run
    stamp alone is only an UPPER BOUND on the close date. A healthy nightly
    produces exactly this pairing -- the persisted close IS the derivation
    session's bar -- so seeding it is what keeps these tests describing the
    healthy system they were written for."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(126, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 1, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(126, 'FTRE', 'watch', 19.52, 18.34, 14.88, 'universe')")
    conn.close()
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 19.52)])


def _pullback_order(**over):
    """A GTC buy-LIMIT at the zone cap and NO stop leg -- the instrument CHARC
    confirmed is actually resting at the broker for FTRE."""
    base = dict(order_type="LIMIT", price=18.89, stop_price=None,
                duration="GOOD_TILL_CANCEL")
    base.update(over)
    return _order(**base)


def test_the_live_ftre_pullback_order_reads_as_a_match(
        seeded_db, monkeypatch, frozen_panel_clock):
    """THE LIVE SUBJECT, from its real values. Latched pivot 18.34, zone cap
    18.89, last close 19.52 -- price is ABOVE the pivot, so a buy stop-limit at
    the pivot would sit BELOW the market and be REJECTED (it was, on
    2026-07-23). The correct instrument is a GTC LIMIT at the cap, and the panel
    must read it as a MATCH.

    Under the one-form set this rendered TWO false alarms at once: a shape
    mismatch ('order type is LIMIT, not STOP_LIMIT') and a price mismatch (the
    pullback form has NO stop leg, so `order_stop_agrees` is None and the panel
    called that silence a disagreement). A false alarm on the exact channel this
    arc exists to make trustworthy."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_above_the_pivot(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_pullback_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR in r.text
    assert "ORDER PRICE MISMATCH" not in r.text
    assert "not the mandated order shape" not in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_a_non_gtc_pullback_limit_is_still_not_an_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """GTC-ness is required of BOTH forms -- FTRE was lost precisely because the
    order was not GTC. This is also the discriminator proving the pullback
    relaxation did not swallow the duration check: with the price legs now
    satisfied, the duration is the ONLY thing standing between this order and a
    false all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_above_the_pivot(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_pullback_order(duration="DAY")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "not the mandated order shape" in r.text
    assert "GOOD_TILL_CANCEL" in r.text


def test_a_stop_limit_above_the_pivot_is_flagged_as_the_wrong_regime(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The inverse: the operator's REJECTED instrument. A GTC stop-limit at the
    right prices is no longer placeable once price crosses the pivot, so leaving
    it up is not coverage -- the panel must say so."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_above_the_pivot(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "not the mandated order shape" in r.text
    assert "AT OR ABOVE" in r.text


def test_a_mispriced_pullback_limit_still_reports_the_price_disagreement(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The pullback regime drops the STOP leg from the expectation -- it must
    NOT drop the CAP leg. The cap is what stops the operator chasing, so a
    buy-limit above it is exactly the disagreement worth rendering."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_above_the_pivot(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_pullback_order(price=19.75)])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text


def test_the_breakout_regime_still_demands_both_legs(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The regression guard on the other side of the boundary: with a
    derivation-session close BELOW the pivot the mandate IS a stop-limit, so a
    stop-only order with no cap must still read as a disagreement. The pullback
    relaxation must not leak into the breakout regime.

    The close is seeded on the DERIVATION session (2026-07-24) on purpose -- the
    `_seed_ftre` close is stamped 2026-07-17 and is therefore session-scoped OUT
    of the regime selector, which would leave this UNKNOWN rather than
    breakout."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    stop_only = _order(order_type="STOP", price=18.34, stop_price=18.34,
                       duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[stop_only])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text
    assert "UNKNOWN (leg absent)" in r.text


# --- Codex y1 MAJOR: an UNKNOWN regime must not re-create the false alarm ---
def _seed_ftre_without_a_close(cfg):
    """The same A+ fire, but with a NULL `candidates.close`.

    `close REAL` is nullable (migration 0001) and `load_last_closes` explicitly
    filters `c.close IS NOT NULL`, so 'no price at all' is a REACHABLE
    production shape -- and it is exactly what a degraded close read looks like
    to the regime selector."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', NULL, 18.34, 14.88, 'universe')")
    conn.close()


def test_an_unknown_regime_does_not_flag_a_stopless_pullback_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex y1 MAJOR. With no usable close the regime is UNDETERMINABLE, and
    the SHAPE check therefore accepts either form -- but the price-leg check
    still demanded a stop leg unconditionally, so a GTC LIMIT at the cap
    rendered ORDER PRICE MISMATCH ('stop UNKNOWN (leg absent)') anyway. The
    fragment contradicted itself, and the false alarm this arc exists to kill
    came straight back whenever the close read degraded.

    FLIPPED 2026-07-27 (RD ruling 2, MERGE-BLOCKING). The no-false-alarm half of
    this test is UNCHANGED and still binding. What flipped is the all-clear: an
    undeterminable regime means the panel cannot tell the operator whether his
    order SHAPE is correct, which is a real reduction in what the panel is
    asserting -- and an UNLABELLED reduction is a quiet all-clear by omission.
    So the affirmative agree is withheld and the skipped check is labelled on the
    affected latch instead. Accepting either form is still the right conservative
    behaviour; announcing it is what was missing."""
    cfg, cfg_path = seeded_db
    _seed_ftre_without_a_close(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_pullback_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "ORDER PRICE MISMATCH" not in r.text
    assert "not the mandated order shape" not in r.text
    # ...but the reduction is announced, not silent. Every branch of the label
    # carries this clause, so the assertion pins the LABEL, not the branch (the
    # branch itself is pinned by the dedicated tests below).
    assert "WHICH of the two mandate forms is correct at this price" in r.text
    # B6 (Arc 21-B): the ALARM all-clear IS now present and that is CORRECT --
    # it is UNSCOPED because it is COMPLETE. Only the two-form SELECTION was
    # skipped; alarms, the cap leg, GTC duration and the stray-order sweep all
    # RAN on this latch. The reduction is still announced, by its OWN claim.
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check pending for 1 latch." in r.text
    assert "FTRE" in r.text


def test_an_unknown_regime_still_requires_the_cap_leg(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The Codex R7 CRITICAL guarantee, preserved through the y1 relaxation: a
    plain BUY STOP at the pivot carries NO cap, and it is the cap that stops the
    operator chasing. The cap leg is required in EVERY regime."""
    cfg, cfg_path = seeded_db
    _seed_ftre_without_a_close(cfg)
    stop_only = _order(order_type="STOP", price=18.34, stop_price=18.34,
                       duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[stop_only])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text


def test_an_unknown_regime_still_judges_a_stop_leg_the_order_actually_carries(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The relaxation is 'do not demand a leg the order does not have', NOT
    'ignore the stop'. An order that DOES claim a stop trigger is still judged
    against the frozen pivot -- otherwise a stop-limit triggering at the wrong
    level would read as an all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre_without_a_close(cfg)
    wrong_trigger = _order(price=18.89, stop_price=18.59,
                           duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[wrong_trigger])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "ORDER PRICE MISMATCH" in r.text


# --- codex-auto-review MAJOR: the regime price must be SESSION-SCOPED --------
def _seed_close_at_the_derivation_session(cfg, close):
    """A close stamped on the fragment's OWN derivation session (2026-07-24 for
    the frozen ANCHOR), so the regime selector will actually use it.

    Arc 21-G: it now ALSO writes the corroborating Shape-A archive bar dated
    that session at the same close, because a run STAMP is only an upper bound
    on the close's date and rung A demands per-bar proof. That pairing is what
    a healthy nightly actually produces, so every shipped all-clear test keeps
    reaching rung A through this one helper rather than through per-test edits.
    The bar must lie within `[anchor, derivation_session]` and on a trading
    session, or `load_bars` drops it."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(127, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 1, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(127, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')", (close,))
    conn.close()
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", close)])


def _seed_stale_close_above_the_pivot(cfg):
    """A close ABOVE the pivot but stamped on 2026-07-20 -- FOUR sessions before
    the fragment's derivation session (2026-07-24). A missed pipeline night, or
    simply an evening before tonight's run, produces exactly this."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(128, '2026-07-20T17:30:05', '2026-07-20', '2026-07-21', 1, 0, 1, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(128, 'FTRE', 'watch', 19.52, 18.34, 14.88, 'universe')")
    conn.close()


def test_a_stale_close_may_alarm_but_may_not_assert_a_match(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RE-EXPRESSED IN PLACE from
    `test_a_stale_close_does_not_get_to_choose_the_mandate_regime` (21-A) --
    deliberately not deleted and re-added, because a deleted test looks like a
    retreat even when it is an advance (RD, 2026-07-28). Both halves of the
    sharpened claim are visible in ONE diff.

    THE ORIGINAL CLAIM (21-A). `load_last_closes` returns the GLOBALLY latest
    `candidates.close` per ticker regardless of how old it is, and the regime
    selector consumed `quote[0]` while ignoring the `quote[1]` date. So the
    gate became: only a close stamped on the derivation session may pick a
    form; anything older leaves the regime UNKNOWN, in BOTH directions.

    WHY THAT WAS SYMMETRIC, AND WHY IT IS NOT A REVERSAL TO SPLIT IT (RD).
    `21-A shipped SYMMETRIC behaviour because the asymmetry needed the
    provenance ladder, which did not exist yet. 21-G builds the ladder and the
    asymmetry becomes expressible. The ruling never changed; its
    implementability did.` One knob was doing two jobs -- gating the ALARM
    direction and the ASSERT direction together, and gating both on a stamp
    that is only an UPPER BOUND. 21-G splits it:

      may a stale close raise a MISMATCH ALARM?  21-A: no (the staleness could
        not be characterised).  21-G: YES, when the staleness is
        CHARACTERISABLE and SELF-LIMITING, labelled with its proven age.
      may a stamp-dated close assert a MATCH?    21-A: yes (the stamp was
        trusted).  21-G: NO -- corroboration against a dated bar is required.

    So the assert direction is TIGHTENED, not merely preserved.

    THE COST OF CONDITION (1), PAID VISIBLY. This fixture must now ALSO seed
    the 2026-07-20 archive bar at 19.52. Without it the close is B-undated and
    the latch is inert -- which is correct behaviour, but not the behaviour
    this test is for. That extra seed IS the arc refusing to alarm from a price
    whose date it has not proven.

    Condition (2) holds on the shipped seeds unchanged: runs 121 (stamped
    2026-07-17) and 128 (stamped 2026-07-20) both carry usable FTRE closes, so
    `L == 2026-07-20 == D` -- a four-session SYSTEM-WIDE gap (a multi-day
    pipeline outage), whose lifetime the outage itself bounds."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_stale_close_above_the_pivot(cfg)
    _write_archive_bars(cfg, "FTRE", [("2026-07-20", 19.52)])
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # THE INVERTED HALF: the mismatch IS now reported. 19.52 is above the
    # latched pivot, so this GTC STOP_LIMIT would sit below the market and be
    # broker-rejected -- the FTRE rejection class, and a finding the operator
    # can act on rather than one that silently vanishes for seven hours a day.
    assert "not the mandated order shape" in r.text
    assert "AT OR ABOVE" in r.text
    # THE PRESERVED (AND TIGHTENED) HALF: no all-clear is asserted from it.
    # Through the B6 (21-B) marker, NOT the retired literal "Broker orders agree
    # with the live latches": that string no longer exists in production, so a
    # `not in` against it would be VACUOUSLY true and would stop testing
    # anything -- the silent-decay the `_ALL_CLEAR` roster rule exists to stop.
    assert _ALL_CLEAR not in r.text
    # ...and the finding is LABELLED with its exact, PROVEN staleness, naming
    # both dates exactly as the 21-A test already required.
    assert "read from a close dated 2026-07-20" in r.text
    assert "2026-07-24" in r.text


def test_a_close_on_the_derivation_session_does_choose_the_regime(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator: the freshness gate must not disable the regime
    selector outright, or the whole two-form ruling becomes inert."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 19.52)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "not the mandated order shape" in r.text
    assert "AT OR ABOVE" in r.text


# --- RD ruling 2026-07-27: the MULTIPLICITY guard ---------------------------
def test_two_orders_on_one_mandate_withhold_the_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RD ruling 1 / CHARC ruling 1, MERGE-BLOCKING. TWO GTC stop-limits on the
    one FTRE latch: the SAME correct stop trigger (18.34) and DIFFERENT caps
    (18.89 and 19.75). Both match the latch on the stop leg, so NEITHER is
    'unmatched'; `_pick_reference_order` prefers the order agreeing on both legs
    and the fragment reports only that one. The page then prints the affirmative
    all-clear over a real wrong-cap order resting at the broker -- a FALSE
    ALL-CLEAR, this arc's dominant defect class.

    The panel may say only what the data supports. It withholds the affirmative
    agree and states the multiplicity instead. It does NOT begin reporting
    per-order legs / per-order agreement / per-order alarms: that is the
    single-reference -> per-order reporting-model change, banked as V2."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    # A derivation-session close BELOW the pivot, so the regime is determinable
    # and the shape check runs -- this test is about multiplicity ONLY.
    _seed_close_at_the_derivation_session(cfg, 17.76)
    good = _order(order_id="good", price=18.89, stop_price=18.34,
                  duration="GOOD_TILL_CANCEL")
    wrong_cap = _order(order_id="wrong-cap", price=19.75, stop_price=18.34,
                       duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[good, wrong_cap])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR not in r.text
    assert "2 resting BUY orders match this mandate" in r.text
    assert "verify the others at the broker" in r.text
    # ...and NOT a false "no resting order" alarm: the mandate IS covered.
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_a_single_matched_order_still_reaches_the_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator for the multiplicity guard: with ONE matched
    order the affirmative agree must still be reachable, or the guard is just a
    permanent gag."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR in r.text
    assert "match this mandate" not in r.text
    # ...and the shape check RAN, so it is not labelled as skipped in ANY branch.
    assert "WHICH of the two mandate forms" not in r.text


# --- RD ruling 2026-07-27: an UNDETERMINABLE regime must be LABELLED --------
def test_an_undeterminable_regime_is_labelled_on_the_affected_latch(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RD ruling 2, MERGE-BLOCKING. With no usable close the regime is
    undeterminable, so the fragment accepts BOTH mandate forms -- correctly, but
    it said NOTHING about having done so. The panel then cannot tell the operator
    whether his order shape is right, which is a real reduction in what it is
    asserting, and an unlabelled reduction is a quiet all-clear by omission (the
    same family as the multiplicity guard).

    A short INLINE label on the affected latch -- not a banner, not a new page
    element -- so the operator can see the shape check did not run.

    No screen exists for 2026-07-24 here, so this is the PENDING branch (RD
    ruling 2026-07-28) -- the label is present either way, which is the property
    ruling 2 pinned."""
    cfg, cfg_path = seeded_db
    _seed_ftre_without_a_close(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "Mandate form check pending" in r.text
    assert "FTRE: waiting on the nightly data" in r.text
    assert "no usable close is recorded for this ticker" in r.text
    # The checks that DID run are named, so the label reduces the claim rather
    # than reading as a blanket failure.
    assert "GOOD_TILL_CANCEL whenever the broker payload carries" in r.text
    # B6 (Arc 21-B): the ALARM all-clear IS now present and that is CORRECT -- it
    # is UNSCOPED because it is COMPLETE. Only the two-form SELECTION was
    # skipped; alarms, the cap leg, GTC duration and the stray-order sweep all
    # RAN on every latch. The reduction is still labelled, by its OWN claim.
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check pending for 1 latch." in r.text


def test_the_skipped_shape_label_claims_no_check_it_did_not_perform(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex R1 MINOR. With a live latch, an undeterminable regime AND NO resting
    orders, the label said 'either form is accepted' and 'the zone cap and
    GOOD_TILL_CANCEL checks still apply' -- but there was no order to accept and
    no leg or duration check ran on anything. A label written to stop the panel
    over-claiming must not itself over-claim."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)                     # close stamped 2026-07-17 -> unknown
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "LATCH_ARMED_NO_RESTING_ORDER" in r.text
    assert "FTRE: waiting on the nightly data" in r.text
    assert "No resting order was evaluated for this mandate" in r.text
    assert "form is accepted" not in r.text
    assert "GOOD_TILL_CANCEL whenever the broker payload carries" not in r.text


def test_the_label_does_not_contradict_a_shape_mismatch_it_still_reports(
        seeded_db, monkeypatch, frozen_panel_clock):
    """codex-auto-review MINOR (the repo-access second eye). An unknown regime
    stops only the FORM SELECTION between the two mandated instruments -- the
    rest of the shape check still runs, so a TRAILING_STOP_LIMIT (neither form)
    or a DAY order is still reported. A label claiming 'the order-shape check did
    not run' therefore contradicted a mismatch rendered a few lines below it, on
    the one channel this arc exists to make trustworthy.

    Both statements must be able to stand on the page at once."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)                     # close stamped 2026-07-17 -> unknown
    trailing = _order(order_type="TRAILING_STOP_LIMIT",
                      duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[trailing])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # The form selection did not run...
    assert "WHICH of the two mandate forms is correct at this price" in r.text
    # ...and the checks that DID run still reported this order.
    assert "not the mandated order shape" in r.text
    assert "TRAILING_STOP_LIMIT" in r.text
    # The label is scoped to the form, so it never claims the shape check as a
    # whole was skipped.
    assert "shape check did not run" not in r.text.lower()
    assert "shape check is pending" not in r.text.lower()
    # B6 (Arc 21-B): the separated claims do NOT weaken the findings gate. A
    # shape mismatch IS a finding, so the template's no-findings branch is never
    # reached and NO form of all-clear renders -- including the new unscoped one.
    assert _ALL_CLEAR not in r.text


# --- RD ruling 2026-07-28: PENDING is not PERMANENT, and neither is an alarm -
#
# The measured frequency is what forces the split. The action session rolls over
# AT the US market close (10:00-10:30 HST) and the nightly pipeline writes the
# new session at 17:30 HST, so for ~7 hours of EVERY trading day -- the
# operator's whole post-close review window -- no latch has a derivation-session
# close and the form check is inert for ALL of them. That is the DEFAULT state,
# not an edge case, and a warning-shaped label on the default state trains the
# dismissal reflex on the one surface whose alarms have to survive being
# believed (the Phase-19 drumbeat false-RED lesson).
def _seed_recorded_closes_for_the_derivation_session(cfg, *, tickers=("AMN",),
                                                     close=12.0):
    """The nightly HAS recorded 2026-07-24 (the fragment's derivation session),
    carrying a usable close for `tickers`. FTRE's absence from that data is what
    makes its latch PERMANENTLY inert rather than merely waiting."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(129, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 1, "
            "0, 0, 0)")
        for ticker in tickers:
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) VALUES "
                "(129, ?, 'watch', ?, 13.0, 11.0, 'universe')", (ticker, close))
    conn.close()


def test_the_pending_branch_is_neutral_status_with_a_stated_clear_time(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RD ruling 2026-07-28. No screen exists yet for the derivation session, so
    NOBODY has a regime price: the check is waiting on data, and the operator's
    correct response is to wait. The label must therefore read as status, must
    say WHEN it clears, and must NOT carry the alarm prefix or the warning
    styling -- a warning that fires on every latch every evening is how an alarm
    channel stops being believed."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)                     # ...and NO screen for 2026-07-24
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "Mandate form check pending" in r.text
    assert "waiting on the nightly data for the derivation session 2026-07-24" \
        in r.text
    assert "no usable closes dated 2026-07-24 are recorded yet" in r.text
    assert "the next run normally settles it - either the form check runs, " \
        "or this becomes a warning" in r.text
    # Neutral tone, explicitly: no alarm prefix and no alarm/warning styling.
    assert "MANDATE FORM CHECK" not in r.text
    assert "latch-form-check-pending" in r.text
    pending_para = r.text.split("Mandate form check pending")[0].rsplit("<p", 1)[-1]
    assert "latch-alarm" not in pending_para


def test_a_latch_whose_ticker_left_the_screen_is_visibly_inert(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RD ruling 3 (2026-07-27), SPLIT by RD ruling 2026-07-28. A latched ticker
    that has dropped off the finviz screen (not held, not pinned) gets no new
    `candidates` row, so it never gets a derivation-session close and the
    two-form shape check stays PERMANENTLY inert for that latch. RD accepts that
    honest degrade -- the live-quote fix is correctly V2 -- provided it is
    VISIBLY inert rather than SILENTLY inert.

    What the 2026-07-28 ruling adds: this must NOT share a string with the
    pending state. The operator's response differs -- there is nothing to wait
    for -- so the label says so and keeps the warning tone.

    The discriminator against pending is whether that SESSION's closes exist at
    all, not the ticker: 2026-07-24 IS recorded here (carrying AMN), and FTRE's
    newest usable close is still the fire's own 2026-07-17 one.

    The label states the COUNT it reasoned from (Codex y1 MAJOR 2) and states
    the off-screen cause as the USUAL one rather than asserting it (MAJOR 1: an
    `evaluation_runs` row is not the finviz screen -- held and pinned tickers are
    appended to the same run -- so this read cannot prove screen membership)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)                     # ...and NO fresher FTRE candidates row
    _seed_recorded_closes_for_the_derivation_session(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" in r.text
    assert "closes dated 2026-07-24 HAVE been recorded " \
        "(for 1 ticker)" in r.text
    assert "the most recent usable close for this ticker is from 2026-07-17" in r.text
    assert "The usual cause is the ticker no longer being evaluated at all" in r.text
    assert "a partial evaluation of that session looks the same from here" in r.text
    assert "So this is a question about the TICKER rather than the clock: it " \
        "clears when this ticker again has a usable close on the derivation " \
        "session" in r.text
    # ...and NOT a claim about waiting that the count cannot prove: under the
    # partial-evaluation shape a later full run for the SAME session would
    # clear it (Codex y4 MINOR 1 / y5 MINOR 1).
    assert "Waiting will NOT clear" not in r.text
    assert "NOT simply waiting on the nightly" not in r.text
    # No apostrophe anywhere in these details -- Jinja autoescaping renders one
    # as `&#39;`, which is correct HTML but breaks plain-text search.
    assert "&#39;" not in r.text
    # It must NOT assert finviz-screen membership from a read that cannot see it.
    assert "is NOT on it" not in r.text
    assert "WITH this ticker on it" not in r.text
    # It stays a WARNING, and it must not borrow the pending branch's promise.
    assert "latch-alarm-warning" in r.text
    assert "Mandate form check pending" not in r.text
    assert "normally settles it" not in r.text
    # It is a LABEL on the affected latch, NOT an alarm and NOT a suppression:
    # the price legs were still judged and no false alarm was invented.
    assert "ORDER PRICE MISMATCH" not in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


def test_the_pending_and_permanent_branches_cannot_collapse_into_one_string(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The anti-collapse pin. ONE seeding difference -- whether the derivation
    session has any recorded close at all -- must flip the label between the two
    branches. A future edit that folds them back into a single string fails
    here."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        pending = _post_orders(client).text
    _seed_recorded_closes_for_the_derivation_session(cfg)
    with TestClient(app) as client:
        permanent = _post_orders(client).text
    assert "Mandate form check pending" in pending
    assert "Mandate form check pending" not in permanent
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" in permanent
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" not in pending


def test_a_session_whose_rows_carry_no_usable_close_is_still_pending(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex y1 MAJOR 1. An `evaluation_runs` row for the derivation session is
    NOT the same thing as a recorded close: `load_last_closes` drops NULL and
    non-finite closes, so a run whose rows carry none has recorded nothing the
    form check can use. Counting that run as 'recorded' would flip a calmly
    waiting latch to a warning -- the exact dismissal-training failure the split
    exists to prevent. Planted via RAW conn.execute."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(130, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 1, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(130, 'AMN', 'watch', NULL, 13.0, 11.0, 'universe')")
    conn.close()
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "Mandate form check pending" in r.text
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" not in r.text


def test_a_held_position_row_is_never_described_as_finviz_screen_membership(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex y1 MAJOR 1. The evaluator appends HELD open positions
    (`bucket='excluded'`, `notes='open position'`) and pinned tickers to the same
    `evaluation_runs` row as the finviz screen, so a read over that row cannot
    prove screen membership. The permanent label must therefore state the
    off-screen cause as the USUAL one, never assert it."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(131, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 0, 0, "
            "0, 1, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method, notes) VALUES "
            "(131, 'HELD', 'excluded', 9.5, NULL, NULL, 'universe', "
            "'open position')")
    conn.close()
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" in r.text
    assert "The usual cause is the ticker no longer being evaluated at all" in r.text
    assert "a partial evaluation of that session looks the same from here" in r.text
    # ...and NOT a claim about the finviz screen, which this read cannot see.
    assert "the screen for the derivation session" not in r.text
    assert "is NOT on it" not in r.text


def test_an_unreadable_close_count_does_not_promise_that_waiting_will_clear_it(
        seeded_db, monkeypatch, frozen_panel_clock):
    """A6 at the new read's boundary. If the recorded-close count itself fails
    the panel genuinely cannot tell pending from permanent -- and guessing
    'pending' would tell the operator to wait for something that may never
    arrive. It says so instead, and it still does not 500."""
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)

    def _boom(_conn, _session):
        raise sqlite3.OperationalError("no such table: candidates")

    monkeypatch.setattr(vm_mod, "count_session_recorded_closes", _boom)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "MANDATE FORM CHECK NOT RUN" in r.text
    assert "whether any closes dated 2026-07-24 have been recorded could not " \
        "be determined" in r.text
    assert "nor whether waiting will clear it" in r.text
    assert "Mandate form check pending" not in r.text


# --- RD ruling 2026-07-28: SCOPE the page-level all-clear, do not withhold it -
def test_the_all_clear_is_scoped_by_counts_rather_than_withheld(
        seeded_db, monkeypatch, frozen_panel_clock):
    """RD ruling 2026-07-28 (reversing the 2026-07-27 blanket withholding). A
    page-level completeness claim is not supportable when a per-latch check did
    not run -- but blanket withholding overshoots, because the label is the
    DEFAULT state for ~7 hours of every trading day. An all-clear that is almost
    never rendered stops being informative by its absence.

    So the supported claim is stated WITH its scope: the counts, explicitly."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # B6 (Arc 21-B): SEPARATED CLAIMS. The alarm all-clear is UNSCOPED because it
    # is COMPLETE -- only the two-form SELECTION was skipped, and alarms, the cap
    # leg, GTC duration and the stray-order sweep all RAN on every latch.
    assert _ALL_CLEAR in r.text
    # ...and the pending count is its OWN claim, carrying the severity the
    # page-level line previously lumped together.
    assert "Mandate-form check pending for 1 latch." in r.text
    # THE VACUOUS ZERO-CASE IS GONE. This is the whole reason the scoped sentence
    # was replaced: with nothing form-checked yet it read as a claim about an
    # EMPTY SET, dressed as a result.
    assert "among the 0" not in r.text
    assert "form-checked" not in r.text


def test_the_scoped_all_clear_counts_the_latches_that_were_checked(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The paired discriminator: a hard-coded '0 checked' would pass the test
    above. Here FTRE's form check DOES run (a derivation-session close exists)
    and a SECOND latched ticker is off the screen, so the counts must read 1
    and 1."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'AMN', 'aplus', 12.0, 13.0, 11.0, 'universe')")
    conn.close()
    good = _order(duration="GOOD_TILL_CANCEL")
    # pivot 13.00 -> zone cap 13.39 (LATCH_ZONE_CAP_PCT), so this order AGREES
    # and contributes no finding of its own -- the counts are what is under test.
    amn = _order(order_id="2", instrument_symbol="AMN", price=13.39,
                 stop_price=13.0, duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[good, amn])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # B6: the PENDING-VS-PERMANENT distinction is now carried into the
    # page-level line, which is the actual refinement. A derivation-session close
    # exists, so AMN's skip is a question about the TICKER (permanent), not about
    # the clock (pending) -- and the two must not read the same.
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check inert for 1 latch - see the labels below." in r.text
    assert "Mandate-form check pending" not in r.text
    assert "form-checked" not in r.text


def test_a_fully_checked_page_still_prints_the_unscoped_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The scoping must not become a permanent gag on the affirmative claim: with
    every live latch checked and nothing to report, the panel still says so
    plainly."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # B6: the all-checked case renders the unscoped claim AND NOTHING ELSE.
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check" not in r.text
    assert "form-checked" not in r.text


def test_a_real_finding_still_withholds_every_form_of_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The scoped form covers the not-RUN case ONLY. A price disagreement is a
    FINDING, not an absent check, and it must still suppress both the plain and
    the scoped all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    mispriced = _order(price=25.00, duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mispriced])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "ORDER PRICE MISMATCH" in r.text
    assert "No alarms among the" not in r.text
    assert _ALL_CLEAR not in r.text


def test_a_failed_close_read_is_not_reported_as_an_absent_close(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex R1 MINOR. A raising `load_last_closes` collapses the regime prices
    to an empty dict, which is indistinguishable from 'this ticker has no close'
    unless the failure is carried. Reporting a DB read failure as 'no close is
    recorded' tells the operator a fact about his data that is not true."""
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)   # a close DOES exist

    def _boom(_conn, _tickers):
        raise sqlite3.OperationalError("no such table: candidates")

    monkeypatch.setattr(vm_mod, "load_last_closes", _boom)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "MANDATE FORM CHECK NOT RUN" in r.text
    assert "FTRE: the mandate FORM check did not run" in r.text
    assert "the close read failed" in r.text
    assert "no usable close is recorded" not in r.text
    # A failed READ is not a pending SCREEN: it must not borrow the calm
    # branch's promise that waiting clears it.
    assert "Mandate form check pending" not in r.text
    # ...and the failure must not become an alarm or a 500.
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text


# ===========================================================================
# Arc 21-G: the close-provenance asymmetry.
#
# ONE RULE: never act on an undated price, in EITHER direction. Assert a match
# only from a close DATED the derivation session; raise a mismatch alarm only
# from a close dated `D < S` that is PROVEN to be dated `D`, when the whole
# system is no fresher than this ticker.
# ===========================================================================
NOW_WINDOW = datetime(2026, 7, 28, 12, 0)   # post-close, BEFORE the nightly
ANCHOR_WINDOW = "2026-07-29"                # action_session_for_run(NOW_WINDOW)


def _freeze(monkeypatch, when):
    """Freeze BOTH clocks at `when` (the fragment requires the posted anchor to
    equal the CURRENT action session, so the ROUTE clock must move too)."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: when)
    monkeypatch.setattr(route_mod, "_now", lambda: when)


def _seed_watch_close(cfg, rid, *, asof, action, close, ticker="FTRE"):
    """A NON-aplus `candidates` row carrying a close under the run stamp `asof`
    -- exactly how the live corpus carries a newer close for a ticker whose
    latch is still armed (FTRE runs 122-125 are this shape)."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
            (rid, f"{asof}T17:30:05", asof, action))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(?, ?, 'watch', ?, 18.34, 14.88, 'universe')", (rid, ticker, close))
    conn.close()


def _seed_route_b_lag(cfg):
    """THE REAL ROUTE-B GEOMETRY. Run 127 stamps 2026-07-24 over a close that
    is actually FTRE's 2026-07-23 bar, because FTRE's evaluator fetch reached
    only 07-23 while another cohort ticker reached 07-24 and
    `evaluation_runs.data_asof_date` is the COHORT MAX.

    Truth at 07-24 is 17.76, BELOW the latched pivot 18.34 -- so the recorded
    19.52 would pick the WRONG mandate form."""
    _seed_watch_close(cfg, 127, asof="2026-07-24", action="2026-07-27",
                      close=19.52)
    _write_archive_bars(cfg, "FTRE", [
        ("2026-07-23", 19.52),      # the close the run actually carried
        ("2026-07-24", 17.76),      # FTRE's REAL 07-24 close
    ])


def test_a_lagged_close_under_a_fresher_stamp_can_no_longer_assert_a_match(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T2 -- THE FALSE ALL-CLEAR KILLER, and the load-bearing discriminator.

    PRE-FIX: `quote = (19.52, '2026-07-24')` and the shipped gate is
    `quote[1] == regime_session_iso`, which PASSES. 19.52 >= 18.34 -> PULLBACK
    -> the stop leg is EXCUSED, the limit agrees, the shape matches, and the
    page prints `Broker orders agree with the live latches. No alarms.` -- a
    MATCH ASSERTED FROM A PRICE THE MARKET HAD ALREADY LEFT. Truth at 07-24 is
    17.76 < 18.34, so the mandate is a STOP_LIMIT and this stopless LIMIT at
    18.89 would fill IMMEDIATELY at ~17.76: an unintended entry below the pivot.

    POST-FIX: a bar DATED 2026-07-24 exists and closed at 17.76, which
    CONTRADICTS the recorded 19.52 -> B-conflict -> inert. No form is picked,
    no all-clear is asserted, and the operator is told his own two dated
    sources disagree."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_route_b_lag(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_pullback_order()])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # THE discriminating assertion, re-expressed for B6 (Arc 21-B). Pre-fix the
    # form check RAN and MATCHED, so the page carried the alarm all-clear with
    # NO form-check reduction beside it. Under the SEPARATED claims the alarm
    # all-clear correctly stands -- it is COMPLETE, not scoped -- so what
    # discriminates is the reduction that must now sit next to it.
    assert _ALL_CLEAR in r.text
    assert ("Mandate-form check inert for 1 latch - the recorded close is "
            "contradicted by the archive; see the labels below.") in r.text
    # ...and the reduction is labelled with the real inconsistency, naming BOTH
    # numbers -- strictly more information than either the pre-fix all-clear or
    # a generic inert wording would have given him.
    assert "RECORDED CLOSE CONTRADICTED BY THE ARCHIVE" in r.text
    assert "19.52" in r.text and "17.76" in r.text


def test_a_lagged_close_under_a_fresher_stamp_does_not_become_an_alarm_either(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T2b -- the paired half. Route B's fix is, and always was, the REFUSAL TO
    ASSERT; it is not a licence to alarm from the contradicted number.

    PRE-FIX the stamp is trusted -> PULLBACK -> the panel reports the operator's
    GTC STOP_LIMIT as the wrong shape. But that order is CORRECT for the
    2026-07-24 bar the panel is holding (17.76 < 18.34 -> BREAKOUT), so the
    alarm would be a FALSE alarm manufactured by our own inconsistency, and it
    would repeat daily whenever the archive refreshes ahead of the candidate
    rows."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_route_b_lag(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text      # fails pre-fix
    assert "AT OR ABOVE" not in r.text                       # fails pre-fix
    assert "RECORDED CLOSE CONTRADICTED BY THE ARCHIVE" in r.text
    # B6: no FORM-check all-clear is asserted -- and it is withheld by SAYING
    # SO, as its own claim, rather than by suppressing the alarm claim (which
    # does hold: every latch WAS alarm-checked).
    assert ("Mandate-form check inert for 1 latch - the recorded close is "
            "contradicted by the archive; see the labels below.") in r.text


def _seed_the_seven_hour_window(cfg):
    """THE ~7-HOUR WINDOW, which is the state of EVERY trading day between the
    action-session rollover (at the US close) and the nightly run at 17:30 HST.

    S = 2026-07-28 and NOTHING is recorded for it. The newest recorded close
    anywhere is 2026-07-27, and it is FTRE's -- so the staleness is the
    CLOCK's, not the TICKER's, and the archive PROVES the close is from 07-27."""
    _seed_watch_close(cfg, 127, asof="2026-07-27", action="2026-07-28",
                      close=19.52)
    _write_archive_bars(cfg, "FTRE", [
        ("2026-07-24", 18.10),
        ("2026-07-27", 19.52),      # W(D) == P: the date is PROVEN
    ])                              # ...and NO bar for S == 2026-07-28


def test_a_true_finding_survives_the_seven_hour_window(
        seeded_db, monkeypatch):
    """T4a -- THE ARC'S ALARM-SIDE DISCRIMINATOR. There is no other.

    PRE-FIX: the close is stamped 2026-07-27 and the derivation session is
    2026-07-28, so the shipped gate drops it -> regime UNKNOWN -> no shape check
    -> the page prints `No alarms among the 0 latches form-checked` -- a scoped
    all-clear over ZERO checking, with a real wrong-form order resting at the
    broker. That is the whole cost of the current inertness: a mismatch the
    operator saw at 18:00 Monday VANISHES at 10:30 Tuesday and does not return
    until 17:30 Tuesday.

    POST-FIX: both alarm conditions hold -- (1) CHARACTERISABLE, the archive
    holds a 2026-07-27 bar whose close IS 19.52, so the date is PROVEN rather
    than inferred from the stamp; (2) SELF-LIMITING, `L == D == 2026-07-27`, so
    the system is no fresher than this ticker and the gap ENDS at the next
    nightly. The finding is raised, LABELLED with its exact proven age."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert "not the mandated order shape" in r.text          # fails pre-fix
    assert "AT OR ABOVE" in r.text
    assert "No alarms" not in r.text                         # fails pre-fix
    # ...and the finding names the close date the reading came from, so the
    # operator can weigh it. An UNLABELLED stale-derived alarm would be a claim
    # the data does not support in the other direction.
    assert "read from a close dated 2026-07-27" in r.text
    assert "2026-07-28" in r.text


def test_the_seven_hour_window_never_produces_an_all_clear(
        seeded_db, monkeypatch):
    """T4b -- the paired half, and the OQ-2 COUPLING asserted as ONE pair.

    RD: `under-alarming is acceptable ONLY BECAUSE IT IS LABELLED. An
    unlabelled under-alarm is a silent all-clear.` So the suppression and the
    label are ONE requirement with two inseparable halves, and this test
    asserts both TOGETHER -- a future edit that deletes the label while keeping
    the suppression cannot leave a green suite.

    The order here is the operator's situationally-CORRECT stopless pullback
    LIMIT, and the stale close (19.52) is ABOVE the pivot -- so the regime is
    PULLBACK, the LIMIT is the right instrument, and there is nothing to
    report. The BELOW-pivot half of the commission/omission line is a separate
    fixture (see
    `test_a_stale_below_pivot_regime_contradicts_the_type_but_demands_no_leg`);
    saying otherwise here would describe a branch this fixture never reaches
    (Codex R9)."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_pullback_order()])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    # (i) NO FORM-check all-clear -- re-expressed for B6 (Arc 21-B). 21-G wrote
    # this as "no all-clear of ANY form", which was right under the SCOPED
    # sentence, where the single claim covered both. Under the SEPARATED claims
    # the ALARM all-clear stands and is CORRECT (alarms, the cap leg, GTC
    # duration and the stray-order sweep ran on every latch), and what is
    # withheld is the FORM-check all-clear -- withheld by SAYING SO rather than
    # by suppressing a claim that does hold.
    assert _ALL_CLEAR in r.text
    # (ii) ...AND the reduction is LABELLED. These two are ONE requirement.
    assert "Mandate form check ran from an uncorroborated close" in r.text
    assert "no all-clear is asserted for this latch" in r.text
    assert ("1 latch checked from an uncorroborated close - no all-clear is "
            "asserted for those.") in r.text
    # ...and no false alarm was invented from the omitted stop leg.
    assert "ORDER PRICE MISMATCH" not in r.text
    assert "not the mandated order shape" not in r.text
    # The ANTI-DRUMBEAT lock: this state renders on every live latch for ~7
    # hours of every trading day, so it must be NEUTRAL, never alarm-shaped.
    assert "latch-form-check-pending" in r.text
    stale_para = r.text.split(
        "Mandate form check ran from an uncorroborated close")[0].rsplit(
            "<p", 1)[-1]
    assert "latch-alarm" not in stale_para


# --- The alarm-gate CONDITION LOCKS -----------------------------------------
#
# These are DESIGN locks, not pre/post discriminators: they pass under the
# shipped code too, and their adversary is a WRONG POST-FIX implementation.
# They are paired deliberately -- each condition of the alarm gate has a pair
# in which one member MUST alarm and the other MUST NOT, so an implementation
# that drops either condition fails a pair rather than silently passing.
#
#   condition (1) CHARACTERISABLE : T4a (must alarm) x T10 (must not)
#   condition (2) SELF-LIMITING   : T4a (must alarm) x T7a + T7b (must not)
#
# Every discriminator in this arc only asserts that something is ABSENT, which
# is exactly the assertion an over-correcting implementation satisfies
# trivially. These are what defend the direction the discriminators cannot see.
def _seed_the_fallen_out_ticker(cfg):
    """A latched ticker that has dropped OUT of evaluation. Its close is
    permanently stale (2026-07-20, ABOVE the pivot) while the system has moved
    on to 2026-07-24 carrying a different ticker -- so `D < L` and the
    staleness is the TICKER's, not the CLOCK's.

    Condition (1) is DELIBERATELY SATISFIED here: the archive corroborates the
    close at its own stamp. Only condition (2) stands between this latch and a
    daily false alarm, so the pair below cannot pass an implementation that
    dropped it."""
    _seed_stale_close_above_the_pivot(cfg)                  # run 128, 07-20
    _seed_recorded_closes_for_the_derivation_session(cfg)   # run 129, AMN 07-24
    _write_archive_bars(cfg, "FTRE", [("2026-07-20", 19.52)])


def test_a_fallen_out_ticker_does_not_alarm_after_the_nightly(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T7a -- the STICKY-FALSE-RED lock, first half (Codex R3 MAJOR).

    What this forbids: an UNBOUNDED rung-B alarm. From the 2026-07-20 close
    (19.52, above the pivot) the regime reads PULLBACK, so the operator's
    correct-for-market-truth GTC STOP_LIMIT would be reported as the wrong
    shape -- and would be reported again on every review, for as long as the
    ticker stays off the screen. That is the drumbeat this codebase has already
    paid for twice."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_the_fallen_out_ticker(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    # ...and it is VISIBLY inert, not silently inert (the OQ-2 coupling) -- at
    # the per-latch label AND, under B6 (Arc 21-B), as its own page-level claim.
    assert "MANDATE FORM CHECK INERT FOR THIS LATCH" in r.text
    assert "Mandate-form check inert for 1 latch - see the labels below." in r.text


def test_a_fallen_out_ticker_does_not_alarm_inside_the_daily_window_either(
        seeded_db, monkeypatch):
    """T7b -- the second half, and the one that actually kills the drumbeat
    (Codex R5 MAJOR 1).

    The FIRST version of the B-continuity gate keyed on
    `count_session_recorded_closes(S) == 0`. That is TRUE here -- it is true
    during EVERY daily post-close window -- so the fallen-out ticker would have
    been alarm-authorized seven hours a day, forever. T7a alone cannot see it:
    T7a runs at a clock where the count is non-zero. The two together are the
    lock; either alone is defeated by an implementation that passes the other.

    DEVIATION FROM THE PLAN, RECORDED. Plan H.T7b says `assertions identical to
    T7a`, but at this clock NOTHING is recorded for S == 2026-07-28, so the
    shipped classifier renders `pending` rather than `permanent` -- which is
    the honest label (it IS true that no usable close is recorded for that
    session yet) and is what plan B.6 requires, since B-persistent is
    indistinguishable from rung C in what the page can claim. The property
    T7b exists to lock -- NO ALARM, and the reduction LABELLED -- is asserted
    exactly."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_fallen_out_ticker(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    # ...the reduction is LABELLED, and it is NOT the alarm-authorized label:
    # this latch was never checked, so it must not claim to have been.
    assert "Mandate-form check pending for 1 latch." in r.text
    assert "Mandate form check pending" in r.text
    assert "Mandate form check ran from an uncorroborated close" not in r.text
    assert "1 latch checked from an uncorroborated close" not in r.text


def test_a_ticker_lagged_inside_the_latest_cohort_does_not_alarm(
        seeded_db, monkeypatch):
    """T10 -- THE ARC'S OWN DEFECT, IN THE ALARM DIRECTION (Codex R6 MAJOR).

    FTRE lagged INSIDE the latest cohort: the run stamps 2026-07-27 for
    everybody, but FTRE's persisted 19.52 is actually its 2026-07-24 bar. Its
    real 07-27 close is 17.10, which the evaluator never saw.

    What this forbids: the freshness-parity gate ALONE. `D == L == 2026-07-27`
    and `W(S) is None`, so a gate testing only stamp parity authorizes the
    alarm, computes PULLBACK from 19.52, and reports the operator's CORRECT
    stop-limit as the wrong shape -- daily, for as long as the ticker lags.
    That is gotcha #30 committed INSIDE THE FIX FOR GOTCHA #30: a run-level
    stamp standing in for a per-row fact, merely relocated from the assert
    direction to the alarm direction.

    Condition (1) is what closes it: `W(D) = 17.10 != 19.52`, so the close is
    NOT corroborated at its own stamp, its date is not proven, and the latch is
    B-undated and inert. Paired with T4a, which differs ONLY in that its 07-27
    bar AGREES with the persisted close."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_watch_close(cfg, 127, asof="2026-07-27", action="2026-07-28",
                      close=19.52)
    _write_archive_bars(cfg, "FTRE", [
        ("2026-07-24", 19.52),      # what the persisted close ACTUALLY is
        ("2026-07-27", 17.10),      # FTRE's real 07-27 close, never evaluated
    ])
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    # It was NOT checked, and it must not claim to have been.
    assert "Mandate form check ran from an uncorroborated close" not in r.text
    assert "1 latch checked from an uncorroborated close" not in r.text
    # ...and the reduction is labelled (the OQ-2 coupling), per-latch AND at the
    # page level as its own B6 (Arc 21-B) claim.
    assert "Mandate-form check pending for 1 latch." in r.text
    assert "Mandate form check pending" in r.text


def test_a_close_stamped_after_this_page_session_can_neither_assert_nor_alarm(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T8 -- the FUTURE-STAMP lock (Codex R5 MAJOR 3).

    What this forbids: dropping the shipped stamp gate without REPLACING it.
    The archive here holds a 2026-07-24 bar at 17.76 that CORROBORATES the
    recorded close, so a naive ladder would reach rung A, read BREAKOUT, find
    both legs agreeing, and print the affirmative all-clear -- asserted from a
    price belonging to a LATER moment than the page describes, breaking the
    coherent-moment invariant the stale-render-anchor suppression exists to
    protect.

    Reachable, not hypothetical: `load_last_closes` returns the GLOBALLY latest
    close per ticker while the fragment POST deliberately rebuilds an OLDER
    render-time anchor, so a newer evaluation run can exist while the fragment
    describes S."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_watch_close(cfg, 132, asof="2026-07-27", action="2026-07-28",
                      close=17.76)
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 17.76)])
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text
    # B6 (Arc 21-B): the FORM check asserted nothing, and it SAYS so as its own
    # page-level claim. `future_stamp` and `unplaceable_stamp` are two headlines
    # over ONE rung, so they share ONE claim; the per-latch label below is what
    # separates them.
    assert ("Mandate-form check inert for 1 latch - the recorded close cannot "
            "be placed in time; see the labels below.") in r.text
    # ...and the reduction names BOTH dates, so the operator can see why.
    assert "RECORDED CLOSE IS STAMPED AFTER THIS PAGE SESSION" in r.text
    assert "is stamped 2026-07-27, LATER than the derivation session " \
        "2026-07-24" in r.text


def test_an_unreadable_archive_withdraws_the_alarm_rather_than_assuming_it(
        seeded_db, monkeypatch):
    """T9 -- the UNREADABLE-WITNESS lock (Codex R5 MAJOR 2).

    Identical to T4a in EVERY respect except that the archive read RAISES.
    What this forbids: inferring the archive status from an EMPTY close map.
    Under that inference this case is indistinguishable from T4a, the type
    mismatch fires, and the panel asserts a regime from a stale price at
    exactly the moment it could not check the one thing that would have settled
    it."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)

    def _boom(*_a, **_k):
        raise OSError("parquet is unreadable")

    monkeypatch.setattr("swing.data.ohlcv_archive.resolve_ohlcv_window", _boom)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200                             # A6
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    assert "MANDATE FORM CHECK NOT RUN" in r.text
    assert "Mandate-form check status unknown for 1 latch." in r.text
    assert "the OHLCV archive read for this ticker failed" in r.text


def test_a_missing_archive_degrades_visibly_and_never_500s(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T6 -- the A6 regression lock. No parquet at all (the production shape
    for a legacy-only Shape-A ticker, of which 1168 exist on the operator's
    box) plus a usable close: rung B, no raise, no all-clear, and the shipped
    rung-C wording reproduced byte-for-byte."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)                    # a usable close, and NO archive at all
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "Mandate-form check pending for 1 latch." in r.text
    assert "Mandate form check pending" in r.text
    assert "waiting on the nightly data for the derivation session 2026-07-24" \
        in r.text
    # An UNREADABLE archive and an ABSENT one are different facts, and the
    # missing-parquet case is the readable-but-empty one.
    assert "the OHLCV archive read for this ticker failed" not in r.text


def test_the_stale_regime_count_equals_the_rendered_stale_notes(
        seeded_db, monkeypatch):
    """The counts and the labels come from ONE list, so they cannot fork
    (Codex R3 MINOR / R6 MINOR). On a MIXED page -- one alarm-authorized latch,
    one merely-unchecked latch -- the sentence's stale term must equal the
    number of rendered stale_regime notes."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)          # FTRE -> B-continuity
    conn = connect(cfg.paths.db_path)
    with conn:
        # A second latched ticker with NO archive at all -> merely unchecked.
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'AMN', 'aplus', 12.0, 13.0, 11.0, 'universe')")
    conn.close()
    amn = _order(order_id="2", instrument_symbol="AMN", price=13.39,
                 stop_price=13.0, duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_pullback_order(), amn])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert r.text.count("Mandate form check ran from an uncorroborated close") == 1
    # THE COMPOSED LINE, verbatim (21-G's provenance claim inside B6's separated
    # structure). The uncorroborated claim leads the REDUCTIONS -- Codex R7's
    # lead-with-the-reduction ruling, honoured as far as the structure allows --
    # while "No alarms." keeps the whole line, because under the separated
    # construction it is COMPLETE and skimming it yields a TRUE belief, which is
    # exactly what the superseded SCOPED sentence could not offer.
    assert "No alarms. " \
        "1 latch checked from an uncorroborated close - no all-clear is " \
        "asserted for those. " \
        "Mandate-form check pending for 1 latch." in r.text


def test_a_dated_conflict_blocks_the_alarm_even_when_both_conditions_hold(
        seeded_db, monkeypatch):
    """The B-CONFLICT lock, in the one geometry where it is load-bearing
    (Codex R4 MAJOR 2).

    Both alarm conditions hold here -- the close IS corroborated at its own
    stamp 2026-07-27 (condition 1) and the system has nothing newer, `D == L`
    (condition 2) -- so ONLY the B-conflict guard stands between the panel and
    an alarm. And the archive is holding a bar dated the derivation session
    that CONTRADICTS the recorded close: 17.10, which makes the operator GTC
    STOP_LIMIT the CORRECT instrument. Alarming from the older, contradicted
    number would be a false alarm manufactured by our own inconsistency, and it
    would repeat daily for as long as the archive runs ahead of the candidate
    rows.

    It also pins the SECOND value_conflict wording: with `D < S` the honest
    statement is that the archive holds a NEWER close for S than the recorded
    one -- not that two sources disagree about the same session, which is the
    `D == S` case."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_watch_close(cfg, 127, asof="2026-07-27", action="2026-07-28",
                      close=19.52)
    _write_archive_bars(cfg, "FTRE", [
        ("2026-07-27", 19.52),      # W(D) == P: condition (1) IS satisfied
        ("2026-07-28", 17.10),      # ...but a bar DATED S contradicts it
    ])
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    assert ("Mandate-form check inert for 1 latch - the recorded close is "
            "contradicted by the archive; see the labels below.") in r.text
    # ...and it is not counted or labelled as a check that ran.
    assert "Mandate form check ran from an uncorroborated close" not in r.text
    assert "1 latch checked from an uncorroborated close" not in r.text
    # The D < S wording, naming both numbers.
    assert "RECORDED CLOSE CONTRADICTED BY THE ARCHIVE" in r.text
    assert ("the archive holds a newer close for 2026-07-28 (17.10) than the "
            "recorded one (19.52, stamped 2026-07-27)" in r.text)


def test_a_corroborated_close_behaves_byte_identically_to_21A(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T3 -- THE REGRESSION LOCK. Passes pre-fix AND post-fix, by design.

    What it discriminates against is not the shipped code but THIS DESIGN'S OWN
    most likely defect: RUNG A MADE UNREACHABLE. (a) the archive map never
    surfaced on `LatchDerivation`, so `W(S)` is always None; (b) the
    corroboration compared at full float precision, so a `17.759999` parquet
    round-trip fails equality; (c) the ladder wired so `may_assert` is never
    True. Any of those makes EVERY latch rung B forever, permanently kills the
    affirmative all-clear, and would otherwise ship GREEN -- because every
    discriminator in this arc only asserts that an all-clear is ABSENT, which
    is exactly what an over-correcting implementation satisfies trivially.

    Verified by deliberately forcing `session_close = None`: eleven tests fail,
    including every shipped all-clear test, which inherit this protection
    through the shared `_seed_close_at_the_derivation_session` helper."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR in r.text
    # ...and NOTHING else on the page-level line: no reduction claim of any
    # severity (B6, Arc 21-B -- the affirmative case emits exactly one claim).
    assert "Mandate-form check" not in r.text
    assert "uncorroborated" not in r.text
    assert "ORDER PRICE MISMATCH" not in r.text


def test_a_sub_cent_archive_round_trip_still_corroborates(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The (b) half of T3's adversary, isolated. Both sides are compared at
    DISPLAY precision (the price-precision-parity gotcha), so a parquet float
    artifact must not demote a healthy latch to rung B and silently kill the
    affirmative all-clear."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 17.7599999)])
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check" not in r.text


def _seed_a_latch_fired_for_the_current_action_session(cfg):
    """A latch fired on TONIGHT's nightly for TOMORROW: its anchor is the
    current action session 2026-07-27, which is AFTER the derivation session
    2026-07-24. The newest latch in the system, and the one the operator is
    about to act on."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(133, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, 1, 0, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(133, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
    conn.close()
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 17.76)])


def test_the_freshest_latch_in_the_system_can_still_reach_the_all_clear(
        seeded_db, monkeypatch, frozen_panel_clock):
    """T3b -- the FRESH-LATCH reachability lock at the fragment level (Codex R4
    MAJOR 1). The case T3 cannot see, because T3's anchor precedes its
    derivation session.

    The defect this forbids: taking the witness from the invalidation walk's
    ELIGIBLE set. For a latch anchored at 2026-07-27 that set is
    `{bar : 2026-07-27 <= s <= 2026-07-24}` -- EMPTY -- so `W(S)` would be None,
    the latch would be permanently rung B, and the newest mandate in the system
    could never print an affirmative all-clear.

    The paired half -- that the widened LOAD did NOT widen the ELIGIBLE set, so
    `bars_available` stays False and a pre-anchor bar still cannot invalidate a
    mandate that did not yet exist -- is asserted at the reader, where those
    fields live (`tests/latches/test_reader.py`)."""
    cfg, cfg_path = seeded_db
    _seed_a_latch_fired_for_the_current_action_session(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _ALL_CLEAR in r.text
    assert "Mandate-form check" not in r.text


def test_a_stale_below_pivot_regime_contradicts_the_type_but_demands_no_leg(
        seeded_db, monkeypatch):
    """THE COMMISSION/OMISSION LINE, in the branch T4b cannot reach (Codex R9).

    B-continuity with the stale close BELOW the pivot -> BREAKOUT regime, and
    the broker holds a STOPLESS GTC LIMIT at the cap. The two halves of RD's
    calibration must BOTH hold here, and they pull in opposite directions:

      COMMISSION, alarmed. The order TYPE is a positive statement and it
        CONTRADICTS the regime. It is also a real hazard rather than pedantry:
        a resting buy LIMIT at 18.89 while price closed at 17.76 fills
        IMMEDIATELY at ~17.76 -- an unintended entry BELOW the pivot, which is
        the same hazard the Route-B discriminator describes. And it is not a
        daily event: it fires only when a crossing has moved the regime or the
        order was already wrong, and B.2.1 bounds its lifetime to the data gap
        that produced the staleness.

      OMISSION, NOT alarmed. The absent stop LEG is not demanded. Demanding it
        would fire on every stopless order for seven hours of every trading
        day -- a false positive by FREQUENCY. This assertion is what locks the
        rung-A-only leg relaxation: an implementation that let the B-continuity
        BREAKOUT regime set `stop_leg_expected = True` fails here.

    And the alarm carries its provenance, so the operator can weigh a finding
    read from a one-session-old close."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_watch_close(cfg, 127, asof="2026-07-27", action="2026-07-28",
                      close=17.76)                  # BELOW the 18.34 pivot
    _write_archive_bars(cfg, "FTRE", [("2026-07-27", 17.76)])
    app = _app(cfg, cfg_path, monkeypatch, orders=[_pullback_order()])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    # COMMISSION: the type contradiction IS reported...
    assert "not the mandated order shape" in r.text
    assert "BELOW" in r.text
    # ...LABELLED with its proven age, never as a proven-regime finding.
    assert "read from a close dated 2026-07-27" in r.text
    # OMISSION: no leg was demanded of an order that does not carry one.
    # Asserted on the LEG line's own prose, not on the shared
    # `ORDER PRICE MISMATCH` heading -- the template puts that heading on every
    # `disagreements` entry, so the shape line above already carries it.
    assert "resting order does not match the latched mandate" not in r.text
    assert "UNKNOWN (leg absent)" not in r.text
    # ...and a finding still withholds every form of all-clear -- asserted
    # through the B6 marker, never the retired literal, which would go
    # VACUOUSLY true now that the production string is gone.
    assert _ALL_CLEAR not in r.text
    assert "No alarms" not in r.text


def test_an_unplaceable_stamp_is_not_described_as_later_than_this_page(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Codex R9 MINOR -- the degradation REASON must be true, not merely safe.

    `data_asof_date` is a plain TEXT column, so a malformed value is reachable
    and `classify_close_provenance` routes it to rung F for the right reason:
    a price that cannot be placed in time cannot support a claim about a
    moment. But a non-empty malformed stamp is UNPLACEABLE, not LATER, and a
    label keyed on the raw string being non-empty said the wrong thing. Planted
    via RAW conn.execute."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(134, '2026-07-24T17:30:05', 'not-a-date', '2026-07-27', 1, 0, 1, "
            "0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(134, 'FTRE', 'watch', 19.52, 18.34, 14.88, 'universe')")
    conn.close()
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    # The SAFE behaviour is preserved: neither direction is claimed.
    assert "not the mandated order shape" not in r.text
    assert ("Mandate-form check inert for 1 latch - the recorded close cannot "
            "be placed in time; see the labels below.") in r.text
    # ...and the REASON given is the true one, in the HEADLINE as well as in
    # the detail (Codex R10 MINOR): the headline is the bold text the operator
    # reads first, so a true detail under a false headline is worse than
    # neither.
    assert "RECORDED CLOSE CANNOT BE PLACED IN TIME" in r.text
    assert "RECORDED CLOSE IS STAMPED AFTER THIS PAGE SESSION" not in r.text
    assert ("which is not a usable date, so it cannot be placed in time at all"
            in r.text)
    assert "LATER than the derivation session" not in r.text


def test_an_unreadable_latest_stamp_says_the_alarm_was_withheld(
        seeded_db, monkeypatch):
    """codex-auto-review MAJOR -- A6 at the arc's OWN new read boundary.

    The T4a geometry EXACTLY: a close whose date the archive PROVES at
    2026-07-27, genuinely older than the derivation session 2026-07-28, and an
    order whose type mismatches that dated stale regime. T4a alarms. Here the
    self-limiting read RAISES, so alarm authority is correctly WITHDRAWN --
    permission is not obligation.

    But withdrawal without a stated reason is the coupling breach: the operator
    would see the routine `waiting on the nightly data` label standing over a
    real, dated, suppressed finding, with nothing saying an alarm had been
    considered and dropped. The shipped branch is UNCHANGED (an unreadable `L`
    withdraws alarm authority only; the count-driven statement is still TRUE
    and replacing it would tell him less than we know) and the reason is
    APPENDED to it.

    Paired with T4a, which differs ONLY in that this read succeeds."""
    import swing.web.view_models.latches as vm_mod
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)

    def _boom(_conn):
        raise sqlite3.OperationalError("no such table: candidates")

    monkeypatch.setattr(vm_mod, "latest_recorded_close_stamp", _boom)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200                              # A6
    # The alarm is WITHHELD...
    assert "not the mandated order shape" not in r.text
    assert "AT OR ABOVE" not in r.text
    # ...and no FORM-check all-clear is asserted: the reduction is stated as its
    # own B6 (Arc 21-B) claim, beside the alarm all-clear that does hold.
    assert "Mandate-form check pending for 1 latch." in r.text
    # ...and it SAYS SO, rather than hiding behind the routine wording.
    assert "a stale-derived mismatch could not even be CONSIDERED for this "         "latch" in r.text
    assert "the newest-recorded-close-stamp read failed" in r.text
    # The shipped branch is unchanged, exactly as ruled -- the count-driven
    # statement is still true and still rendered.
    assert "Mandate form check pending" in r.text
    # ...and it was NOT counted or labelled as a check that ran.
    assert "Mandate form check ran from an uncorroborated close" not in r.text
    assert "1 latch checked from an uncorroborated close" not in r.text


def test_a_readable_latest_stamp_adds_no_suppression_clause(
        seeded_db, monkeypatch):
    """The paired half: the clause must not leak into the ordinary states, or
    it becomes noise on every latch that was simply never alarm-eligible."""
    cfg, cfg_path = seeded_db
    _freeze(monkeypatch, NOW_WINDOW)
    _seed_ftre(cfg)
    _seed_the_seven_hour_window(cfg)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client, anchor=ANCHOR_WINDOW)
    assert r.status_code == 200
    assert "not the mandated order shape" in r.text          # T4a alarms
    assert "could not even be CONSIDERED" not in r.text


# ---------------------------------------------------------------------------
# The per-order CANCEL control (plan file manifest; auto-review MAJOR)
# ---------------------------------------------------------------------------
def _invalidate(cfg):
    """A close BELOW the frozen 14.88 stop, which clears the latch by
    INVALIDATION and leaves the resting order stale -- the operator's one manual
    duty, and the state that raises the stale-order ALARM.

    IT IS NO LONGER WHAT EARNS A CANCEL CONTROL. Wave item 4 decoupled the
    recording affordance from the alarm: every attributable order gets a
    control, alarmed or not. This helper is retained because these tests are
    about the ALARM's coexistence with the control."""
    import pandas as pd
    cfg.paths.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": "2026-07-21", "open": 15.0, "high": 15.2, "low": 14.0,
         "close": 14.00, "volume": 100.0},
    ]).to_parquet(cfg.paths.prices_cache_dir / "FTRE.yfinance.parquet")


def test_a_stale_order_alarm_offers_a_CANCEL_control_bound_to_THAT_order_id(
        seeded_db, monkeypatch, frozen_panel_clock):
    """AUTO-REVIEW MAJOR, and the SAME CLASS as the missing validity prompt: the
    plan's file manifest requires "the per-order Cancel control on stale-order
    rows", and without it `intent_kind='cancel'` is unreachable in a browser --
    so the row carrying section G.4's EXACT linkage (a captured broker order id)
    never enters the measurement ledger and cancellation decisions are invisible.

    The control targets a SPECIFIC broker order id and never a ticker --
    hazard (c), which the schema CHECK also makes unwritable.

    WHAT BINDS THE CONTROL CHANGED IN WAVE ITEM 4, AND THIS TEST'S ASSERTIONS
    DID NOT. It used to be `OrderAlarm.broker_order_id`, carried structurally so
    a control could ride on the alarm; the control now rides on the ORDER
    (`attribute_orders_to_latches` -> `cancel_controls`) and the alarm field is
    alarm CONTENT. This geometry still produces both, which is exactly why the
    test still passes -- so it is kept as the coexistence case rather than
    rewritten.
    """
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _invalidate(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order(order_id="4242")])
    with TestClient(app) as client:
        r = _post_orders(client)
    import re
    assert "ORDER_RESTING_LATCH_CLEARED" in r.text
    start = r.text.index('<form class="latch-cancel-form"')
    form = r.text[start:r.text.index("</form>", start)]
    fields = dict(re.findall(r'name="([^"]+)" *\n? *value="([^"]*)"', form))
    assert fields["intent_kind"] == "cancel"
    assert fields["actual_broker_order_id"] == "4242"
    assert fields["view_session_date"] == ANCHOR
    assert 'hx-post="/latches/intent"' in form
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in form
    assert 'hx-target="this"' in form


def test_the_cancel_control_actually_writes_the_cancel_row_end_to_end(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Rendered is not the same as REACHABLE. This posts exactly what the form
    emits and asserts the ledger row, which is the property the validity-prompt
    finding proved a rendering test alone does not establish."""
    import re
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _invalidate(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order(order_id="4242")])
    with TestClient(app) as client:
        html = _post_orders(client).text
        start = html.index('<form class="latch-cancel-form"')
        form = html[start:html.index("</form>", start)]
        fields = dict(re.findall(
            r'name="([^"]+)" *\n? *value="([^"]*)"', form))
        r = client.post("/latches/intent", headers=_HX, data=fields)
    assert r.status_code == 200, r.text
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT intent_kind, actual_broker_order_id FROM "
            "latch_order_intents").fetchall()
    finally:
        conn.close()
    assert rows == [("cancel", "4242")]


def test_an_UNATTRIBUTABLE_stale_order_LABELS_the_gap_instead_of_hiding_it(
        seeded_db, monkeypatch, frozen_panel_clock):
    """A `cancel` row carries the FULL latch identity block, so an order matching
    NO latch cannot be logged against one. A control that is simply ABSENT reads
    as "nothing to do here" -- and the operator still has to cancel it at the
    broker. So the gap is LABELLED, which is the same rule the arc applies to
    every other reduction."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _invalidate(cfg)
    stray = _order(order_id="9999", stop_price=99.00, price=99.50)
    app = _app(cfg, cfg_path, monkeypatch, orders=[stray])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "ORDER_RESTING_LATCH_CLEARED" in r.text
    assert "latch-cancel-form" not in r.text, (
        "no cancel control may be bound to an unattributable order")
    assert "no mandate to log a cancel against" in r.text


def test_the_absent_order_alarm_carries_NO_order_id_and_NO_control(
        seeded_db, monkeypatch, frozen_panel_clock):
    """LATCH_ARMED_NO_RESTING_ORDER is an alarm about the ABSENCE of an order.
    There is no id to cancel, and a cancel control there would be nonsense."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "LATCH_ARMED_NO_RESTING_ORDER" in r.text
    assert "latch-cancel-form" not in r.text


# ---------------------------------------------------------------------------
# THE CANCEL-AFFORDANCE DECOUPLING (wave item 4, piece 1).
#
# RD's principle (2026-08-03): recording an operator action and alarming on a
# detected problem are DIFFERENT FUNCTIONS, and the affordance to record must
# not be gated on the alarm that detects. The control's subject is a BROKER
# ORDER THE OPERATOR HOLDS, not a problem the framework noticed.
# ---------------------------------------------------------------------------
_CANCEL_FORM = '<form class="latch-cancel-form"'
_CANCEL_LOG = '<section class="latch-cancel-log">'
_CANCEL_STATUS = 'class="latch-cancel-status"'
_CANCEL_GAP = 'class="latch-cancel-unavailable"'


def _alarms_container(html: str) -> str:
    """The `.latch-alarms` DIV, or '' when absent.

    SCOPED TO THE CONTAINER, NOT TO THE `<p>`. The pre-change form was a
    SIBLING of the alarm paragraph (which closes before it) and a CHILD of
    `.latch-alarms` -- so a `<p>`-scoped assertion is GREEN pre-change and
    would let the inline form survive inside the alarm block while acceptance
    reported success.
    """
    marker = '<div class="latch-alarms">'
    if marker not in html:
        return ""
    start = html.index(marker)
    return html[start:html.index("</div>", start)]


def _cancel_form_fields(html: str) -> dict:
    import re
    start = html.index(_CANCEL_FORM)
    form = html[start:html.index("</form>", start)]
    return dict(re.findall(r'name="([^"]+)" *\n? *value="([^"]*)"', form))


def test_a_PENDING_CANCEL_order_STILL_offers_the_cancel_control(
        seeded_db, monkeypatch, frozen_panel_clock):
    """DISCRIMINATOR. Pre-fix an INDETERMINATE order is dropped before
    attribution and its whole ticker is skipped by both alarm loops, so NO
    control renders at all -- the state produced BY the operator doing what the
    framework asked is exactly the state in which the framework offered him no
    way to record it.

    The paired alarm assertions fail any implementation that bought the control
    by WIDENING THE ALARM SET: the suppression is ruled correct, and alarming
    on PENDING_CANCEL would shout at the operator for complying.

    The status assertion is EXACT and CLASS-SCOPED, because the fragment
    already printed `ORDER STATUS INDETERMINATE` from `vm.indeterminate_tickers`
    before any change -- an assertion on "indeterminate is mentioned" would be
    vacuous.
    """
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(order_id="7001", status="PENDING_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert _CANCEL_LOG in r.text
    assert _cancel_form_fields(r.text)["actual_broker_order_id"] == "7001"
    assert "<p " + _CANCEL_STATUS + ">broker status PENDING_CANCEL</p>" in r.text
    # THE ALARM HALF IS UNTOUCHED.
    assert "ORDER_RESTING_LATCH_CLEARED" not in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text
    assert "ORDER STATUS INDETERMINATE" in r.text


def test_an_ORDINARY_resting_order_carries_NO_status_note(
        seeded_db, monkeypatch, frozen_panel_clock):
    """GUARD -- the other side of the pair. Without it, an implementation that
    emits a status note UNCONDITIONALLY passes the test above."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch,
               orders=[_order(order_id="7002", duration="GOOD_TILL_CANCEL")])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _CANCEL_FORM in r.text
    assert _CANCEL_STATUS not in r.text


def test_a_HEALTHY_covering_order_ALSO_offers_the_cancel_control(
        seeded_db, monkeypatch, frozen_panel_clock):
    """DISCRIMINATOR, and it is Q2: `ORDER_RESTING_LATCH_CLEARED` must not be
    the sole route to a `cancel` row. Pre-fix there is no alarm here, therefore
    no control. It fails any implementation that re-keys the control on a
    rediscovered alarm predicate."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    mandated = _order(order_id="7003", order_type="STOP_LIMIT",
                      duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mandated])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert _ALL_CLEAR in r.text, "the premise: this geometry raises NO alarm"
    assert _CANCEL_LOG in r.text
    assert _cancel_form_fields(r.text)["actual_broker_order_id"] == "7003"


def test_the_cancel_control_on_a_NON_ALARMED_order_writes_the_row_end_to_end(
        seeded_db, monkeypatch, frozen_panel_clock):
    """DISCRIMINATOR. RENDERED IS NOT REACHABLE -- the 21-B lesson, which is
    why the alarm-side control has its own end-to-end test too."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    mandated = _order(order_id="7004", order_type="STOP_LIMIT",
                      duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mandated])
    with TestClient(app) as client:
        html = _post_orders(client).text
        assert _ALL_CLEAR in html, "the premise: NO alarm on this geometry"
        r = client.post(
            "/latches/intent", headers=_HX, data=_cancel_form_fields(html))
    assert r.status_code == 200, r.text
    conn = connect(cfg.paths.db_path)
    try:
        rows = conn.execute(
            "SELECT intent_kind, actual_broker_order_id FROM "
            "latch_order_intents").fetchall()
    finally:
        conn.close()
    assert rows == [("cancel", "7004")]


def test_the_alarm_block_no_longer_carries_a_FORM(
        seeded_db, monkeypatch, frozen_panel_clock):
    """DISCRIMINATOR, scoped to the `.latch-alarms` CONTAINER. Pre-change the
    cancel form is a CHILD of that container, so this is RED; a `<p>`-scoped
    assertion would be green pre-change and would let the inline form survive.

    Paired with a POSITIVE assertion that a control exists elsewhere on the
    same render -- an absence test that would pass on an empty page is not a
    test."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _invalidate(cfg)
    app = _app(cfg, cfg_path, monkeypatch, orders=[_order(order_id="7005")])
    with TestClient(app) as client:
        r = _post_orders(client)
    container = _alarms_container(r.text)
    assert "ORDER_RESTING_LATCH_CLEARED" in container
    assert "<form" not in container
    assert _CANCEL_LOG in r.text
    assert _cancel_form_fields(r.text)["actual_broker_order_id"] == "7005"


def test_an_UNAVAILABLE_broker_book_offers_NO_cancel_control(
        seeded_db, monkeypatch, frozen_panel_clock):
    """GUARD -- green on both trees, because the unavailable branch already
    returns early with no controls. It kills the one wrong implementation:
    building controls outside the `available` branch. A control built on a book
    nobody could read invites a decision the operator would infer from the
    panel's own silence."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = _app(cfg, cfg_path, monkeypatch, install_holder=False)
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "unavailable" in r.text.lower(), "the premise: the book is UNKNOWN"
    assert _CANCEL_FORM not in r.text
    assert _CANCEL_LOG not in r.text


def test_an_order_attributable_to_NO_latch_gets_a_NOTE_and_no_control_with_NO_alarm(
        seeded_db, monkeypatch, frozen_panel_clock):
    """DISCRIMINATOR. A stray order beside a LIVE latch fires NO
    `ORDER_RESTING_LATCH_CLEARED` (a mispriced order for a live mandate is
    deliberately not alarmed), so pre-change the cancel-gap label was
    UNREACHABLE on this geometry -- the note existed only when the order also
    alarmed.

    IT ASSERTS THE CANCEL-GAP CLASS, never merely "a labelled note": the VM
    already appends a DISAGREEMENT line for every unmatched order and the
    template already renders it, so "a note is present" is GREEN pre-change.
    """
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    stray = _order(order_id="9999", stop_price=99.00, price=99.50)
    app = _app(cfg, cfg_path, monkeypatch, orders=[stray])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert "ORDER_RESTING_LATCH_CLEARED" not in r.text, (
        "the premise: a stray beside a LIVE latch does not alarm")
    assert _CANCEL_GAP in r.text
    assert "9999" in r.text
    assert "no mandate to log a cancel against" in r.text
    assert _CANCEL_FORM not in r.text


def test_an_IDENTICAL_paging_DUPLICATE_renders_as_ONE_order_everywhere(
        seeded_db, monkeypatch, frozen_panel_clock):
    """CODEX R4 MAJOR. A broker page can repeat an order, and canonicalising it
    inside the join alone left `order_lines`, the validity prompts and
    `_broker_book_digest` reading the RAW book -- so the duplicate rendered
    twice and MOVED THE SNAPSHOT DIGEST while the join counted one order. A
    digest that moves without the book moving lets a reload append a second
    validity row for the same logical broker state, which is a fabricated
    observation in a measurement ledger.

    Asserted as EQUIVALENCE against the single-order render rather than as a
    count: the property is that one order and the same order twice are the SAME
    BOOK, and any consumer that disagrees shows up as a diff.
    """
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    once = _order(order_id="D1", duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[once])
    with TestClient(app) as client:
        single = _post_orders(client).text
    app2 = _app(cfg, cfg_path, monkeypatch, orders=[once, _order(
        order_id="D1", duration="GOOD_TILL_CANCEL")])
    with TestClient(app2) as client:
        doubled = _post_orders(client).text
    assert doubled == single, (
        "an identical repeat is ONE order, so every consumer -- the order "
        "list, the cancel controls, the alarms and the snapshot digest -- must "
        "render byte-identically")
    assert single.count("<li>FTRE BUY") == 1
    assert single.count(_CANCEL_FORM) == 1


def test_a_CONTRADICTORY_repeated_order_id_degrades_the_whole_fragment(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The other side. A book that says one id is two different orders is not
    something this surface can resolve, and the panel's standing rule is that a
    false all-clear and a false alarm are both worse than an honest unknown --
    so the A6 ladder degrades it VISIBLY and no control is offered on a book
    nobody could read."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    _seed_close_at_the_derivation_session(cfg, 17.76)
    app = _app(cfg, cfg_path, monkeypatch, orders=[
        _order(order_id="C1"), _order(order_id="C1", price=99.0, stop_price=99.0)])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "UNKNOWN" in r.text
    assert _CANCEL_FORM not in r.text
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in r.text
