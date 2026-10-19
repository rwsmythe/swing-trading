"""D79 T3 -- the offer list excludes a GLOBALLY recorded order id, read
through the ONE reader (RD K7.1; orchestrator K7.4; CHARC FORK 2 reader
consistency). Plan T3; the ``world`` fixture of
``test_exit_rerender_anchor.py`` (o1 = 2026-05-20 130.00 x 4, o2 =
2026-05-21 131.00 x 3)."""
from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from swing.data.repos.fills import _recompute_aggregates
from swing.web.app import create_app
from tests.web.test_routes.test_exit_rerender_anchor import (  # noqa: F401
    _hidden,
    world,
)


def _envelope(order_id: str) -> str:
    return json.dumps({"exit_date": "2026-05-20", "exit_price": 130.0,
                       "closed_shares": 4, "schwab_order_id": order_id,
                       "schwab_instrument_symbol": "NVDA"}, sort_keys=True)


def _plant(cfg, trade_id: int, envelope: str | None, *, day="2026-05-20",
           price=130.0, qty=4.0) -> int:
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with c:
            fid = c.execute(
                "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
                "price, fill_origin, schwab_source_value_json) "
                "VALUES (?, ?, 'trim', ?, ?, ?, ?)",
                (trade_id, f"{day}T16:00:00", qty, price,
                 "schwab_auto" if envelope else "operator_typed", envelope),
            ).lastrowid
            _recompute_aggregates(c, trade_id)
        return int(fid)
    finally:
        c.close()


def _closed_trade(cfg) -> int:
    c = sqlite3.connect(str(cfg.paths.db_path))
    try:
        with c:
            tid = c.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) VALUES "
                "('NVDA', '2026-04-01', 100.0, 4, 95.0, 95.0, 'closed', "
                "'manual_off_pipeline', '2026-04-01T09:30:00')").lastrowid
        return int(tid)
    finally:
        c.close()


def _offered_map(body: str) -> dict:
    env = json.loads(_hidden(body, "schwab_source_value_json"))
    return {v["order_id"]: v for v in env["candidates_map"].values()}


def test_t3a_an_id_recorded_on_another_trade_is_excluded(world):
    """RD K7.1, the same-day close-and-re-enter case. PRE-FIX: o1 and o2
    are both offered (the exclusion query is per-trade). NULL killed: the
    per-trade scope."""
    trade_a = _closed_trade(world.cfg)
    _plant(world.cfg, trade_a, _envelope("o1"))
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        body = tc.get(f"/trades/{world.tid}/exit/form").text
    assert set(_offered_map(body)) == {"o2"}


def test_t3b_a_padded_stored_id_is_anonymous_and_flags_never_excludes(world):
    """CHARC FORK 2 consistency. A stored ``" o1"`` is REFUSED by the
    authority, so the row is anonymous: o1 is OFFERED and FLAGGED against it
    with the value-tuple reason. PRE-FIX: the verbatim id enters the
    exclusion set (matching nothing) and the row is not anonymous -> o1 is
    offered with NO flag. NULL killed: a reader that strips (excludes o1)."""
    fid = _plant(world.cfg, world.tid, _envelope(" o1"))
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        body = tc.get(f"/trades/{world.tid}/exit/form").text
    offered = _offered_map(body)
    assert set(offered) == {"o1", "o2"}
    dups = offered["o1"]["possible_duplicates"]
    assert [d["fill_id"] for d in dups] == [fid]
    assert dups[0]["reason"] == "value_tuple_match"


def test_t3c_an_id_recorded_on_the_same_trade_is_excluded_control(world):
    """Regression pin (green pre-fix)."""
    _plant(world.cfg, world.tid, _envelope("o1"))
    with TestClient(create_app(world.cfg, world.cfg_path)) as tc:
        body = tc.get(f"/trades/{world.tid}/exit/form").text
    assert set(_offered_map(body)) == {"o2"}
