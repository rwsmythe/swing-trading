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
