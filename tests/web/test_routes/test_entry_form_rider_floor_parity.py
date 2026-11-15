"""Phase 22 entry-form rider -- D97: the entry form sizes on the FLOORED equity.

The nightly recommendation (`swing/pipeline/runner.py`) and the latch card
(`swing/web/view_models/latches.py`) size on
`sizing_equity(real_equity=..., floor=cfg.account.risk_equity_floor)`. Until
this rider the entry form (`build_entry_form_vm`) and its live hint
(`GET /trades/entry/sizing-hint`) handed `compute_shares` the RAW equity, so
the same account showed two budgets side by side (live, 2026-10-26: 13.96
dollars on the form beside 37.50 on the latch card).

The geometry here is entry 20.00 / stop 19.00 (one share risks $1.00), with
max_risk_pct 0.005 and position_pct_cap 0.15 (the test config).

World 1 -- real equity BELOW the floor (starting 1200, floor 7500, no fills):
  old path: equity 1200 -> budget $6.00 -> 6 by risk; cap 1200*0.15/20 = 9
            -> 6 sh, $6.00 risk = 0.50%.
  new path: equity max(1200, 7500) = 7500 -> budget $37.50 -> 37 by risk;
            cap 7500*0.15/20 = 56 -> 37 sh, $37.00 risk = 37/7500 = 0.49%.
  They differ, so the test discriminates.

World 2 -- real equity ABOVE the floor (a $8,800 deposit: 1200 + 8800 =
10000 > 7500):
  old path = new path: budget $50.00 -> 50 by risk; cap 10000*0.15/20 = 75
            -> 50 sh, $50.00 risk = 0.50%. The floor changes nothing.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.recommendations.sizing import compute_shares
from swing.trades.equity import sizing_equity
from swing.web.app import create_app

_TICKER = "FEZ"
_ENTRY = 20.0
_STOP = 19.0


def _seed_watchlist(cfg, monkeypatch) -> None:
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=_TICKER, added_date="2026-10-20",
                last_qualified_date="2026-10-22", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-10-22",
                entry_target=_ENTRY, initial_stop_target=_STOP,
                last_close=19.9, last_pivot=_ENTRY, last_stop=_STOP,
                last_adr_pct=3.0, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=_ENTRY, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers})


def _deposit(cfg, amount: float) -> None:
    from swing.data.models import CashMovement
    from swing.data.repos.cash import insert_cash

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_cash(conn, CashMovement(
                id=None, date="2026-10-01", kind="deposit", amount=amount,
                ref=None, note="rider floor-parity world 2"))
    finally:
        conn.close()


def _expected(cfg, real_equity: float):
    return compute_shares(
        entry=_ENTRY, stop=_STOP,
        equity=sizing_equity(real_equity=real_equity,
                             floor=cfg.account.risk_equity_floor),
        max_risk_pct=cfg.risk.max_risk_pct,
        position_pct_cap=cfg.sizing.position_pct_cap)


def _render_both(cfg, cfg_path) -> tuple[str, str]:
    with TestClient(create_app(cfg, cfg_path)) as client:
        form = client.get(f"/trades/entry/form?ticker={_TICKER}")
        hint = client.get("/trades/entry/sizing-hint",
                          params={"entry_price": f"{_ENTRY:.2f}",
                                  "initial_stop": f"{_STOP:.2f}"})
    assert form.status_code == 200, form.text
    assert hint.status_code == 200, hint.text
    return form.text, hint.text


def _assert_states(body: str, sizing) -> None:
    assert f"Suggested max: <strong>{sizing.shares} sh</strong>" in body, body
    assert f"~${sizing.risk_dollars:.2f} risk" in body
    assert f"{sizing.risk_pct:.2f}%" in body


def test_d97_below_the_floor_the_form_and_the_hint_size_on_the_floor(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    assert cfg.account.starting_equity < cfg.account.risk_equity_floor
    _seed_watchlist(cfg, monkeypatch)
    expected = _expected(cfg, real_equity=cfg.account.starting_equity)
    # The hand-computed figures of the module docstring (new path).
    assert (expected.shares, round(expected.risk_dollars, 2)) == (37, 37.00)
    assert f"{expected.risk_pct:.2f}" == "0.49"
    # The old path's figures differ, so this test discriminates.
    old = compute_shares(entry=_ENTRY, stop=_STOP,
                         equity=cfg.account.starting_equity,
                         max_risk_pct=cfg.risk.max_risk_pct,
                         position_pct_cap=cfg.sizing.position_pct_cap)
    assert (old.shares, round(old.risk_dollars, 2)) == (6, 6.00)

    form, hint = _render_both(cfg, cfg_path)
    _assert_states(form, expected)
    _assert_states(hint, expected)
    assert "Suggested max: <strong>6 sh</strong>" not in form
    assert "Suggested max: <strong>6 sh</strong>" not in hint


def test_d97_above_the_floor_the_figures_are_unchanged(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _deposit(cfg, 8800.0)
    real = cfg.account.starting_equity + 8800.0
    assert real > cfg.account.risk_equity_floor
    _seed_watchlist(cfg, monkeypatch)
    expected = _expected(cfg, real_equity=real)
    old = compute_shares(entry=_ENTRY, stop=_STOP, equity=real,
                         max_risk_pct=cfg.risk.max_risk_pct,
                         position_pct_cap=cfg.sizing.position_pct_cap)
    assert expected == old
    assert (expected.shares, round(expected.risk_dollars, 2)) == (50, 50.00)

    form, hint = _render_both(cfg, cfg_path)
    _assert_states(form, expected)
    _assert_states(hint, expected)


def test_d97_the_vm_carries_the_real_equity_it_read(seeded_db, monkeypatch):
    """C1: the VM keeps the REAL equity (not the floored one) so a re-render
    resizes without a second DB read and the floor is applied exactly once."""
    from swing.web.view_models.trades import build_entry_form_vm

    cfg, cfg_path = seeded_db
    _seed_watchlist(cfg, monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        app = client.app
        vm = build_entry_form_vm(
            ticker=_TICKER, cfg=cfg, cache=app.state.price_cache,
            executor=app.state.price_fetch_executor)
    assert vm.sizing_real_equity == cfg.account.starting_equity
    assert vm.suggested_shares == 37
