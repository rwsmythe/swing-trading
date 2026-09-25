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


# ---------------------------------------------------------------------------
# T-A7 -- C1-26 D68 + the exit route's F4 close (S-CONTAIN, the 22-A3 outer
# guard).  After `record_exit` RETURNS the exit is durable; a failure in the
# close or in the page refresh must not be reported as a failure (the
# double-exit direction).  Before the bind, an error is still the honest
# answer and is re-raised unchanged (A7-d).
# ---------------------------------------------------------------------------

def _post(cfg, cfg_path, tid: int, **over: str):
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        return tc.post(f"/trades/{tid}/exit", headers=_HX,
                       data=_exit_data(**over))


def test_A7a_refresh_failure_after_a_durable_exit_is_a_degraded_success(
        seeded_db: tuple[Config, Path], monkeypatch):
    """A7-a. `build_dashboard` (module-level import in
    `swing.web.routes.trades`, resolved per call) planted to raise.
    PRE-FIX: 500, while the exit IS durable.  POST-FIX: 200 naming the
    trade and that the exit IS recorded; a FRESH read shows the fill."""
    from tests._22f_proxies import raising
    cfg, cfg_path = seeded_db
    tid = _open_trade(cfg)
    before = _fresh(cfg.paths.db_path, tid)
    planted = raising(RuntimeError("planted non-race"))
    monkeypatch.setattr("swing.web.routes.trades.build_dashboard", planted)
    resp = _post(cfg, cfg_path, tid)
    assert planted.calls == 1  # did-it-fire
    assert resp.status_code == 200, resp.text[:500]
    assert f"#{tid}" in resp.text and "IS recorded" in resp.text
    assert "planted non-race" in resp.text
    after = _fresh(cfg.paths.db_path, tid)
    assert after[0] == before[0] + 1 and after[1] == before[1] - 10


def test_A7b_close_failure_after_a_durable_exit_is_logged_not_a_500(
        seeded_db: tuple[Config, Path], monkeypatch, caplog):
    """A7-b. `exit_post` resolves the module global
    `swing.web.routes.trades.connect`; every connection it opens there fails
    `close()`.  A FULL close (100 of 100) so the route opens exactly one.
    PRE-FIX: the close raise escapes the `finally` -> 500.  POST-FIX: the
    ordinary 200 success response, and one ERROR record naming the close
    failure."""
    import logging

    from tests._22f_proxies import FailingVerbsConn, patch_conn_opener
    cfg, cfg_path = seeded_db
    tid = _open_trade(cfg)
    built = patch_conn_opener(
        monkeypatch, "swing.web.routes.trades.connect",
        lambda real: FailingVerbsConn(real, fail_close=True))
    with caplog.at_level(logging.ERROR, logger="swing.web.routes.trades"):
        resp = _post(cfg, cfg_path, tid, shares="100")
    assert built and all(p.calls["close"] >= 1 for p in built)  # did-it-fire
    assert resp.status_code == 200, resp.text[:500]
    assert f'id="open-position-{tid}"' in resp.text  # the success fragment
    errors = [r for r in caplog.records
              if r.name == "swing.web.routes.trades"
              and r.levelno == logging.ERROR
              and "cannot close (planted on close)" in r.getMessage()]
    assert len(errors) == 1, [r.getMessage() for r in caplog.records]
    assert _fresh(cfg.paths.db_path, tid)[1] == 0


def test_A7c_control_value_error_is_still_the_400_rerender(
        seeded_db: tuple[Config, Path]):
    """A7-c CONTROL: `record_exit` refuses (`ValueError`, shares > remaining)
    -> the 400 re-render, unchanged on both trees."""
    cfg, cfg_path = seeded_db
    tid = _open_trade(cfg)
    resp = _post(cfg, cfg_path, tid, shares="500")
    assert resp.status_code == 400, resp.text[:500]
    assert "exceeds remaining" in resp.text


def test_A7d_control_error_before_the_bind_is_still_a_500(
        seeded_db: tuple[Config, Path], monkeypatch):
    """A7-d CONTROL: `record_exit` (module-level import in the route) raises
    a `RuntimeError` BEFORE anything is durable -- `result` is never bound,
    so the error is the honest answer: 500 on both trees, nothing written."""
    from tests._22f_proxies import raising
    cfg, cfg_path = seeded_db
    tid = _open_trade(cfg)
    before = _fresh(cfg.paths.db_path, tid)
    planted = raising(RuntimeError("planted before commit"))
    monkeypatch.setattr("swing.web.routes.trades.record_exit", planted)
    resp = _post(cfg, cfg_path, tid)
    assert planted.calls == 1  # did-it-fire
    assert resp.status_code == 500
    assert _fresh(cfg.paths.db_path, tid) == before
