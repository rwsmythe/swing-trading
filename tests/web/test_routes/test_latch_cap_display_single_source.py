"""THE CANONICAL ENTRY LIMIT IS SINGLE-SOURCED ON THE DISPLAY SIDE TOO.

Witnessed live 2026-08-03: the panel card showed `Zone cap 37.36` for AMN while
the framework's own prepared order on the SAME card said `limit 37.35`. The
operator placed 37.36 -- the number he was shown -- and 21-B's parity ledger
would have recorded that one cent as HIS deviation.

The mechanism: `swing/latches/constants.py:mandate_limit_price` FLOORS to whole
cents (RD, 2026-07-30: "a cap that can drift up is not a cap"), while every
DISPLAY path formatted the raw cap with `:.2f`, which rounds HALF-UP. Whenever
the cap's third decimal is >= 5 the two disagree by exactly one cent and the
display states a price ABOVE the cap -- a price the framework would refuse to
order.

    AMN   pivot 36.27 -> cap 37.3581 -> `:.2f` 37.36 (UP)   mandate 37.35
    VSTS  pivot 16.90 -> cap 17.4070 -> `:.2f` 17.41 (UP)   mandate 17.40
    FTRE  pivot 18.34 -> cap 18.8902 -> `:.2f` 18.89 (DOWN) mandate 18.89

FTRE IS THE CONTROL AND IT IS NOT DECORATION. Its cap rounds DOWN, so display
and mandate already agreed there and no divergence was visible -- which is why
the defect survived every FTRE-geometry test in the suite. Pinning it here is
what separates "the fix FLOORS" from "the fix subtracts a cent": an over-eager
implementation that shaved FTRE to 18.88 passes every AMN assertion below and
fails the control.

Each assertion is stated as `display == what the framework would ORDER`, never
as a bare literal: the literal is what drifts. The literals appear only as
inline PREMISE assertions, so the geometry's reason cannot rot.
"""
from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.latches.constants import mandate_limit_price
from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch, RestingOrder
from swing.latches.orders import join_orders_to_latches
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)        # Saturday -> action session 2026-07-27
ANCHOR = "2026-07-27"
_HX = {"HX-Request": "true"}

# THE WITNESSED GEOMETRY, kept as pivots so the caps stay derived.
AMN_PIVOT = 36.27
AMN_CAP = round(AMN_PIVOT * 1.03, 4)      # 37.3581 -- third decimal >= 5
AMN_STOP = 33.00
FTRE_PIVOT = 18.34
FTRE_CAP = round(FTRE_PIVOT * 1.03, 4)    # 18.8902 -- third decimal < 5


def _fmt(value: float) -> str:
    return f"{value:.2f}"


def test_the_premise_the_two_quantizations_actually_disagree_on_AMN():
    """Asserted inline so the whole file's reason cannot rot.

    If a future edit changes `LATCH_ZONE_CAP_PCT` or the cap derivation, this
    fails FIRST and tells the next reader that the geometry -- not the fix --
    moved.
    """
    assert AMN_CAP == 37.3581
    assert _fmt(AMN_CAP) == "37.36", "round-half-up overstates the cap"
    assert mandate_limit_price(AMN_CAP) == 37.35
    assert mandate_limit_price(AMN_CAP) < AMN_CAP < float(_fmt(AMN_CAP))

    # ...and the control genuinely does NOT exhibit it.
    assert FTRE_CAP == 18.8902
    assert _fmt(FTRE_CAP) == "18.89"
    assert mandate_limit_price(FTRE_CAP) == 18.89
    assert _fmt(FTRE_CAP) == _fmt(mandate_limit_price(FTRE_CAP))


# ---------------------------------------------------------------------------
# Seeding -- mirrors tests/web/test_routes/test_latches_orders_fragment.py
# ---------------------------------------------------------------------------
def _seed_fire(cfg, *, run_id, ticker, pivot, stop, close, bucket="aplus",
               asof="2026-07-17", action="2026-07-20"):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
            (run_id, f"{asof}T17:30:05", asof, action))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES (?, ?, ?, ?, ?, ?, "
            "'universe')",
            (run_id, ticker, bucket, close, pivot, stop))
    conn.close()


def _seed_amn(cfg):
    _seed_fire(cfg, run_id=141, ticker="AMN", pivot=AMN_PIVOT, stop=AMN_STOP,
               close=35.10)


def _seed_ftre(cfg):
    _seed_fire(cfg, run_id=121, ticker="FTRE", pivot=FTRE_PIVOT, stop=14.88,
               close=17.76)


def _write_archive_bars(cfg, ticker, rows):
    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


def _seed_derivation_session_close(cfg, ticker, close, *, run_id, pivot, stop):
    """A close dated the fragment's OWN derivation session (2026-07-24), with
    the corroborating archive bar -- the pairing a healthy nightly produces, and
    the only one that reaches rung A of the close-provenance ladder."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) "
            "VALUES (?, '2026-07-24T17:30:05', '2026-07-24', '2026-07-27', 1, "
            "0, 1, 0, 0, 0)", (run_id,))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES (?, ?, 'watch', ?, ?, ?, "
            "'universe')", (run_id, ticker, close, pivot, stop))
    conn.close()
    _write_archive_bars(cfg, ticker, [("2026-07-24", close)])


@pytest.fixture
def frozen_panel_clock(monkeypatch):
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


class _Holder:
    def __init__(self, client):
        self._client = client

    def borrow(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield self._client

        return _cm()


def _order(**over):
    base = dict(order_id="1", status="WORKING", enter_time="2026-07-20T13:30:00Z",
                instrument_symbol="AMN", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", price=mandate_limit_price(AMN_CAP),
                stop_price=AMN_PIVOT)
    base.update(over)
    return SchwabOrderResponse(**base)


def _app(cfg, cfg_path, monkeypatch, *, orders=None):
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(
        vm_mod, "_resolve_schwab_environment", lambda _cfg: "production")
    monkeypatch.setattr(vm_mod, "_resolve_account_hash", lambda _cfg: "HASH")
    monkeypatch.setattr(
        vm_mod, "_fetch_account_orders",
        lambda *a, **k: list(orders or []))
    app = create_app(cfg, cfg_path)
    app.state.schwab_client_holder = _Holder(object())
    return app


def _post_orders(client):
    return client.post("/latches/orders", headers=_HX,
                       data={"view_session_date": ANCHOR})


# ---------------------------------------------------------------------------
# SITE 1 -- the panel CARD's `Zone cap` field (the number the operator read)
# ---------------------------------------------------------------------------
def test_the_card_renders_the_cap_the_framework_would_ORDER(
        seeded_db, frozen_panel_clock):
    """`view_models/latches.py` `zone_cap=` on the row VM -> `latches.html.j2`.

    PRE-FIX the row carried "37.36" (`_fmt_price(37.3581)`), one cent ABOVE the
    cap and one cent above the prepared order printed on the same card.
    """
    from swing.web.view_models.latches import build_latch_panel_vm

    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg)
    finally:
        conn.close()
    row = next(r for r in vm.rows if r.ticker == "AMN")
    assert row.zone_cap == _fmt(mandate_limit_price(AMN_CAP))
    assert row.zone_cap == "37.35"          # the PREMISE, not the contract
    assert row.zone_cap != _fmt(AMN_CAP)


def test_the_card_control_a_cap_that_rounds_DOWN_is_unchanged(
        seeded_db, frozen_panel_clock):
    """THE CONTROL. An over-eager "subtract a cent" fix passes every AMN
    assertion in this file and fails here."""
    from swing.web.view_models.latches import build_latch_panel_vm

    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    conn = connect(cfg.paths.db_path)
    try:
        vm = build_latch_panel_vm(conn, cfg)
    finally:
        conn.close()
    row = next(r for r in vm.rows if r.ticker == "FTRE")
    assert row.zone_cap == _fmt(mandate_limit_price(FTRE_CAP))
    assert row.zone_cap == "18.89"
    assert row.zone_cap == _fmt(FTRE_CAP), (
        "the control's display was ALREADY correct; the fix must not move it")


def test_the_rendered_page_never_shows_a_cap_above_the_mandate(
        seeded_db, frozen_panel_clock):
    """End to end through the real template, because the VM assertion above
    cannot see a second cap rendered by the page itself."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert _fmt(mandate_limit_price(AMN_CAP)) in r.text
    assert _fmt(AMN_CAP) not in r.text, (
        "the over-rounded cap must appear NOWHERE on the page")


# ---------------------------------------------------------------------------
# SITES 2-5 -- the order-fragment alarm prose
# ---------------------------------------------------------------------------
def _assert_cap_prose(text, *, expect_present=True):
    over = _fmt(AMN_CAP)
    exact = _fmt(mandate_limit_price(AMN_CAP))
    if expect_present:
        assert exact in text
    assert over not in text, (
        f"an alarm line stated the cap as {over}, which is ABOVE it")


def test_the_ORDER_PRICE_MISMATCH_line_states_the_mandate_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """`view_models/latches.py` breakout-branch disagreement line -- the second
    surface the operator saw on 2026-08-03. The resting order carries the right
    stop trigger and a wrong cap, so the line renders the mandate's cap beside
    the disagreement."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    mispriced = _order(order_id="mispriced", price=37.10, stop_price=AMN_PIVOT)
    app = _app(cfg, cfg_path, monkeypatch, orders=[mispriced])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "ORDER PRICE MISMATCH" in r.text
    _assert_cap_prose(r.text)


def test_the_PULLBACK_disagreement_line_states_the_mandate_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The pullback branch: a corroborated close AT OR ABOVE the latched pivot
    makes the mandate a GTC LIMIT at the cap, and the line names that cap."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    _seed_derivation_session_close(
        cfg, "AMN", 38.50, run_id=142, pivot=AMN_PIVOT, stop=AMN_STOP)
    mispriced = _order(order_id="pullback", order_type="LIMIT", price=37.10,
                       stop_price=None, duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mispriced])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "a GTC LIMIT at the zone cap" in r.text
    _assert_cap_prose(r.text)


def test_the_UNKNOWN_REGIME_disagreement_line_states_the_mandate_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """The third branch: no usable close, a stopless order, so only the cap is
    judged -- and the cap it prints must be the orderable one."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    mispriced = _order(order_id="capless-regime", order_type="LIMIT",
                       price=37.10, stop_price=None,
                       duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[mispriced])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "only the cap is judged" in r.text
    _assert_cap_prose(r.text)


def test_the_MULTIPLICITY_line_states_the_mandate_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """Two orders sharing the correct stop trigger and carrying different caps
    -- the withheld-all-clear line names pivot and cap."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    good = _order(order_id="good", duration="GOOD_TILL_CANCEL")
    wrong_cap = _order(order_id="wrong-cap", price=38.75,
                       stop_price=AMN_PIVOT, duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[good, wrong_cap])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "2 resting BUY orders match this mandate" in r.text
    _assert_cap_prose(r.text)


def test_the_STRAY_ORDER_line_states_the_mandate_limit(
        seeded_db, monkeypatch, frozen_panel_clock):
    """An order matching NO latch is reported with the mandate it failed to
    implement -- pivot and cap."""
    cfg, cfg_path = seeded_db
    _seed_amn(cfg)
    good = _order(order_id="good", duration="GOOD_TILL_CANCEL")
    stray = _order(order_id="stray", price=30.10, stop_price=29.00,
                   duration="GOOD_TILL_CANCEL")
    app = _app(cfg, cfg_path, monkeypatch, orders=[good, stray])
    with TestClient(app) as client:
        r = _post_orders(client)
    assert r.status_code == 200
    assert "matches NO latch" in r.text
    _assert_cap_prose(r.text)


# ---------------------------------------------------------------------------
# SITES 6-7 -- swing/latches/orders.py, the LATCH_ARMED_NO_RESTING_ORDER detail
# ---------------------------------------------------------------------------
def _amn_latch(state="armed") -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=9801, evaluation_run_id=141, ticker="AMN",
            detection_date="2026-07-20", pipeline_run_id=None),
        latched_pivot=AMN_PIVOT, latched_initial_stop=AMN_STOP,
        zone_cap=AMN_CAP, anchor=date(2026, 7, 20),
        horizon_expiry=date(2026, 9, 1), sessions_elapsed=3,
        sessions_to_horizon=27, state=state)


def _ftre_latch() -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=9802, evaluation_run_id=121, ticker="FTRE",
            detection_date="2026-07-20", pipeline_run_id=None),
        latched_pivot=FTRE_PIVOT, latched_initial_stop=14.88,
        zone_cap=FTRE_CAP, anchor=date(2026, 7, 20),
        horizon_expiry=date(2026, 9, 1), sessions_elapsed=3,
        sessions_to_horizon=27, state="armed")


def test_the_NO_RESTING_ORDER_absence_detail_states_the_mandate_limit():
    """`swing/latches/orders.py` -- the empty-book branch. This is the LOUDEST
    alarm on the panel; the number beside it is the one the operator will
    type."""
    _, alarms = join_orders_to_latches(latches=[_amn_latch()], orders=[])
    detail = next(
        a.detail for a in alarms if a.kind == "LATCH_ARMED_NO_RESTING_ORDER")
    assert f"zone cap {_fmt(mandate_limit_price(AMN_CAP))}" in detail
    assert _fmt(AMN_CAP) not in detail


def test_the_NO_RESTING_ORDER_wrong_shape_detail_states_the_mandate_limit():
    """The sibling branch: orders exist but none implements the mandate."""
    day = RestingOrder(
        order_id="7101", ticker="AMN", instruction="BUY", quantity=3.0,
        order_type="LIMIT", limit_price=mandate_limit_price(AMN_CAP),
        stop_price=None, status="WORKING", duration="DAY")
    _, alarms = join_orders_to_latches(latches=[_amn_latch()], orders=[day])
    detail = next(
        a.detail for a in alarms if a.kind == "LATCH_ARMED_NO_RESTING_ORDER")
    assert "wrong shape" in detail
    assert f"zone cap {_fmt(mandate_limit_price(AMN_CAP))}" in detail
    assert _fmt(AMN_CAP) not in detail


def test_the_NO_RESTING_ORDER_control_a_cap_that_rounds_DOWN_is_unchanged():
    """THE CONTROL on the alarm path."""
    _, alarms = join_orders_to_latches(latches=[_ftre_latch()], orders=[])
    detail = next(
        a.detail for a in alarms if a.kind == "LATCH_ARMED_NO_RESTING_ORDER")
    assert f"zone cap {_fmt(FTRE_CAP)}" in detail
    assert f"zone cap {_fmt(mandate_limit_price(FTRE_CAP))}" in detail


# ---------------------------------------------------------------------------
# THE ROSTER BELT -- the "did the fix reach ALL the sites" question, asked of
# the source rather than of the reviewer's memory.
# ---------------------------------------------------------------------------
_RAW_CAP_FORMAT = re.compile(r"\bzone_cap:\.\d+f")


def test_no_module_formats_a_RAW_zone_cap_for_display():
    """A NEW render site is the way this defect comes back, and no behavioural
    test can cover a line nobody has written yet.

    So the belt is structural: `{...zone_cap:.2f}` -- formatting the RAW cap --
    may not appear in any production module. The orderable value comes from
    `mandate_limit_price`, and a site that wants to SHOW a cap has to go
    through it.

    Scoped to a FORMAT SPEC, not to the identifier: `zone_cap` is passed around
    freely (to `mandate_shape_mismatch`, into the derivation), and only the act
    of rendering it at price precision is the defect.
    """
    from swing.latches import orders as orders_mod
    from swing.web.view_models import latches as vm_mod

    for module in (vm_mod, orders_mod):
        source = inspect.getsource(module)
        hits = _RAW_CAP_FORMAT.findall(source)
        assert hits == [], (
            f"{module.__name__} formats a raw zone_cap for display ({hits}); "
            "route it through mandate_limit_price -- round-half-up can state a "
            "price ABOVE the cap, which is the whole defect")
