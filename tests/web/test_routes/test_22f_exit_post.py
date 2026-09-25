"""22-F -- `POST /trades/{id}/exit` (`exit_post`).

T-A6 (C1-24): an `exit_price` the `fills.price` column refuses reached the
INSERT and escaped as `sqlite3.IntegrityError` past the route's
`except ValueError` -> the app-wide 500 page.  After `record_exit`'s typed
`ExitPriceRefusedError(ValueError)`, the existing 400 re-render delivers it.

The world is `seeded_db` (sandbox environment: the re-render's auto-fill
fetch short-circuits) plus an open trade with an entry fill.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from swing.config import Config
from swing.data.db import connect
from swing.web.app import create_app
from tests.trades.test_exit import _seed_active_trade

_HX = {"HX-Request": "true"}


def _open_trade(cfg: Config) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        return int(_seed_active_trade(conn, ticker="AAPL", current_size=100.0))
    finally:
        conn.close()


def _fresh(db_path: Path, tid: int) -> tuple:
    c = sqlite3.connect(str(db_path))
    try:
        return (c.execute("SELECT COUNT(*) FROM fills").fetchone()[0],
                c.execute("SELECT current_size FROM trades WHERE id = ?",
                          (tid,)).fetchone()[0])
    finally:
        c.close()


def _exit_data(**over: str) -> dict:
    data = {"exit_date": "2026-05-10", "exit_price": "130.0", "shares": "10",
            "reason": "manual", "notes": ""}
    data.update(over)
    return data


def test_A6a_A6c_exit_price_zero_is_a_400_refusal_not_a_500(
        seeded_db: tuple[Config, Path]):
    """A6-a / A6-c. PRE-FIX: `record_exit` INSERTs `price=0`, the
    `fills.price` CHECK raises `IntegrityError`, which is not a
    `ValueError` -> 500.  POST-FIX: 400 re-render naming the refusal; a
    FRESH read shows `fills` and `trades.current_size` unchanged."""
    cfg, cfg_path = seeded_db
    tid = _open_trade(cfg)
    before = _fresh(cfg.paths.db_path, tid)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post(f"/trades/{tid}/exit", headers=_HX,
                       data=_exit_data(exit_price="0"))
    assert resp.status_code == 400, resp.text[:500]
    assert "exit price must be &gt; 0" in resp.text or (
        "exit price must be > 0" in resp.text)
    assert _fresh(cfg.paths.db_path, tid) == before
