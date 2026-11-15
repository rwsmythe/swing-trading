"""Phase 22 entry-form rider -- the THREE entry recovery paths share one
re-render (`_with_entry_submission`, C2):

  (a) `_rerender_entry_form_with_error` -- here its rationale refusal;
  (b) the missing-field 400 (`MissingPreTradeFieldsException`);
  (c) the duplicate-position 400 (`DuplicateOpenPositionError`).

The world is a plain watchlist row (FEZ: live 20.00, stop target 19.00) with
the test config's $1,200 real equity under its $7,500 floor.
"""
from __future__ import annotations

import html
import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from tests.web.test_routes.test_fx2_claimed_undecodable_round_trip import (
    _serialize_first_form,
)
from tests.web.test_routes.test_phase13_t2_sb6c_t_a_6c_4 import (
    _pretrade_form_kwargs,
)

_TICKER = "FEZ"
_ANSWERS = {
    **_pretrade_form_kwargs(),
    "premortem_additional": "earnings in three weeks",
    "catalyst": "other",
    "catalyst_other_description": "index inclusion",
    "entry_intent": "hypothesis_test_by_design",
}


def _seed(cfg, monkeypatch) -> None:
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
                entry_target=20.0, initial_stop_target=19.0,
                last_close=19.9, last_pivot=20.0, last_stop=19.0,
                last_adr_pct=3.0, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=20.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers})


def _open_trade(cfg) -> None:
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker=_TICKER, entry_date="2026-11-02",
                entry_price=19.0, initial_shares=3, initial_stop=18.0,
                current_stop=18.0, state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-11-02T09:30:00")
    finally:
        conn.close()


def _post(cfg, cfg_path, monkeypatch, path: str, *, entry: str, stop: str,
          shares: str = "5") -> str:
    """Drive one recovery path; return the 400's unescaped body."""
    data = {
        "ticker": _TICKER, "entry_date": "2026-11-13",
        "entry_price": entry, "shares": shares, "initial_stop": stop,
        "rationale": "vcp-breakout", "origin": "watchlist", **_ANSWERS,
    }
    said = {
        "rerender": "Invalid rationale",
        "missing-field": "Missing required pre-trade fields: thesis",
        "duplicate": f"Already an open position in {_TICKER}",
    }[path]
    if path == "rerender":
        data["rationale"] = "not-a-rationale"
    elif path == "missing-field":
        data.pop("thesis")
    else:
        _open_trade(cfg)
    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.post("/trades/entry", data=data,
                        headers={"HX-Request": "true"})
    assert r.status_code == 400, r.text
    body = html.unescape(r.text)
    assert said in body, body
    return r.text


_PATHS = ["rerender", "missing-field", "duplicate"]


def _shares_input(body: str) -> int:
    m = re.search(r'name="shares"\s+value="(\d+)"', body)
    assert m is not None
    return int(m.group(1))


@pytest.mark.parametrize("path", _PATHS)
def test_d47_each_recovery_path_keeps_the_pre_trade_answers(
        seeded_db, monkeypatch, path):
    """(b) always kept the answers; (a) and (c) dropped them before C2."""
    cfg, cfg_path = seeded_db
    _seed(cfg, monkeypatch)
    body = _post(cfg, cfg_path, monkeypatch, path, entry="20.00", stop="19.00")
    recovery = _serialize_first_form(body)
    expected = {k: v for k, v in _ANSWERS.items()
                if not (path == "missing-field" and k == "thesis")}
    assert {k: recovery.get(k) for k in expected} == expected
    assert recovery["shares"] == "5"


# ---------------------------------------------------------------------------
# D98 -- a refused submit re-renders the sizing ON THE SUBMITTED PRICES.
#
# Server-resolved geometry (what the rebuilt VM sizes): live 20.00 / stop
# 19.00 on the floored $7,500 (budget $37.50): 37 by risk, cap 56 -> 37 sh.
#
# Risk-bound zero submitted: 104.00 / 29.81 -> one share risks $74.19 against
# the $37.50 budget, 74.19 / 37.50 = 1.98 -> "2.0x budget": zero shares, the
# stated line below. Before D98 every path rendered "Suggested max: 37 sh"
# beside those prices (the server's sizing, a different geometry).
#
# Feasible submitted: 20.00 / 18.00 -> $2.00 a share: 18 by risk (37.50 / 2 =
# 18.75), cap 7500 * 0.15 / 20 = 56 -> 18 sh, $36.00 risk = 36 / 7500 = 0.48%.
# 18 differs from the server's 37 AND from the submitted count, 5.
# ---------------------------------------------------------------------------
_ZERO_LINE = ("0 shares at the $37.50 budget; 1 share risks $74.19 (2.0x "
              "budget) at entry 104.00; above budget if you proceed")


@pytest.mark.parametrize("path", _PATHS)
def test_d98_a_risk_bound_zero_submit_states_its_zero(
        seeded_db, monkeypatch, path):
    cfg, cfg_path = seeded_db
    _seed(cfg, monkeypatch)
    body = html.unescape(_post(cfg, cfg_path, monkeypatch, path,
                               entry="104.00", stop="29.81"))
    assert _ZERO_LINE in body
    assert "Suggested max" not in body
    # The prices shown are the submitted ones the line is computed on.
    recovery = _serialize_first_form(body)
    assert (recovery["entry_price"], recovery["initial_stop"]) == (
        "104.00", "29.81")


@pytest.mark.parametrize("path", _PATHS)
def test_d98_a_feasible_submit_is_sized_on_its_own_prices(
        seeded_db, monkeypatch, path):
    cfg, cfg_path = seeded_db
    _seed(cfg, monkeypatch)
    body = _post(cfg, cfg_path, monkeypatch, path,
                 entry="20.00", stop="18.00", shares="5")
    assert 18 not in (37, 5)
    assert "Suggested max: <strong>18 sh</strong>" in body
    assert "~$36.00 risk" in body
    assert "0.48%" in body
    assert "Suggested max: <strong>37 sh</strong>" not in body
    # `input_shares` stays the submitted count; the sizing never reads it.
    assert _shares_input(body) == 5


def test_d98_an_invalid_submitted_geometry_asks_for_valid_prices(
        seeded_db, monkeypatch):
    """The stop >= entry refusal re-renders NO sizing for its prices (before
    D98 it showed the server geometry's "37 sh" beside a stop above entry)."""
    cfg, cfg_path = seeded_db
    _seed(cfg, monkeypatch)
    data = {
        "ticker": _TICKER, "entry_date": "2026-11-13", "entry_price": "20.00",
        "shares": "5", "initial_stop": "21.00", "rationale": "vcp-breakout",
        "origin": "watchlist", **_ANSWERS,
    }
    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.post("/trades/entry", data=data,
                        headers={"HX-Request": "true"})
    assert r.status_code == 400, r.text
    assert "stop must be &lt; entry" in r.text or "stop must be < entry" in r.text
    assert "Suggested max" not in r.text
    assert "Enter a valid entry price and stop to see sizing" in r.text


def test_d98_an_unsizable_submitted_geometry_keeps_the_recovery_form(
        seeded_db, monkeypatch):
    """Codex R1 minor 1: finite, positive, ordered prices can still overflow
    the sizing arithmetic (1e-308 / 5e-309: the $37.50 budget over a
    5e-309 one-share risk is inf, and `math.floor(inf)` raises). Sizing is
    advisory, so the recovery form comes back (400, not 500) with no sizing
    and the hint endpoint keeps its "Sizing unavailable" guidance."""
    from swing.web.view_models.trades import entry_form_sizing

    cfg, cfg_path = seeded_db
    _seed(cfg, monkeypatch)
    unsized = entry_form_sizing(cfg=cfg, entry=1e-308, stop=5e-309,
                                real_equity=1200.0)
    assert (unsized.suggested_shares, unsized.sizing) == (0, None)
    data = {
        "ticker": _TICKER, "entry_date": "2026-11-13", "entry_price": "1e-308",
        "shares": "5", "initial_stop": "5e-309", "rationale": "not-a-rationale",
        "origin": "watchlist", **_ANSWERS,
    }
    with TestClient(create_app(cfg, cfg_path)) as client:
        r = client.post("/trades/entry", data=data,
                        headers={"HX-Request": "true"})
        hint = client.get("/trades/entry/sizing-hint",
                          params={"entry_price": "1e-308",
                                  "initial_stop": "5e-309"})
    assert r.status_code == 400, r.text
    assert "Invalid rationale" in r.text
    assert "Enter a valid entry price and stop to see sizing" in r.text
    assert _serialize_first_form(r.text)["thesis"] == _ANSWERS["thesis"]
    assert hint.status_code == 200
    assert "Sizing unavailable" in hint.text
