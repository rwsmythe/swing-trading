"""22-F R1-05 (Reviewer A round 1; CHARC-ruled) -- the web stop route binds
`durable` from `adjust_stop`'s `bool` return (the GRANTED amendment to
`swing/trades/stop_adjust.py`).  PRE-FIX the route set `durable = True` on
the equal-stop NO-OP too, so a close failure -- on the write connection OR on
the row re-read connection, whose close was contained unconditionally --
rendered "The stop change on trade #N IS recorded" over a write that never
happened.  POST-FIX, for the no-op, both closes are the pre-arc bare close:
a close failure is the app's 500 (nothing durable), with no helper record
and no notice.  The WRITE input with a failing close keeps its notice and a
fresh read of the write: that is `trades-stop` in G2-a of
`tests/web/test_22f_close_after_durable_roots.py`.  Did-it-fire: every case
asserts the failing proxy recorded >= 1 close.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app
from tests.web.test_22f_close_after_durable_roots import (
    _HX,
    _current_stop,
    _fail_nth_close,
    _helper_records,
    _open_trade_world,
)

_TARGET = "swing.web.routes.trades.connect"


@pytest.mark.parametrize("nth", [1, 2], ids=["write-conn", "reread-conn"])
def test_r1_05_stop_noop_close_failure_names_no_write(
        nth, seeded_db: tuple[Config, Path], monkeypatch, caplog):
    cfg, cfg_path = seeded_db
    extra = _open_trade_world(cfg, monkeypatch)
    current = _current_stop(cfg, extra)
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        built = _fail_nth_close(monkeypatch, _TARGET, nth)
        with caplog.at_level(logging.ERROR):
            resp = tc.post(f"/trades/{extra['tid']}/stop", headers=_HX,
                           data={"new_stop": str(current),
                                 "rationale": "trail-10ma"})
    assert len(built) >= nth
    assert built[nth - 1].calls["close"] >= 1  # did-it-fire
    assert "IS recorded" not in resp.text
    assert _helper_records(caplog) == []
    assert resp.status_code == 500, (resp.status_code, resp.text[:600])
    assert _current_stop(cfg, extra) == current


def test_r1_05_stop_noop_clean_close_pin(seeded_db: tuple[Config, Path],
                                         monkeypatch):
    """PIN (both trees): the equal-stop no-op with clean closes renders the
    row, 200."""
    cfg, cfg_path = seeded_db
    extra = _open_trade_world(cfg, monkeypatch)
    current = _current_stop(cfg, extra)
    with TestClient(create_app(cfg, cfg_path)) as tc:
        resp = tc.post(f"/trades/{extra['tid']}/stop", headers=_HX,
                       data={"new_stop": str(current),
                             "rationale": "trail-10ma"})
    assert resp.status_code == 200, resp.text[:600]
    assert "IS recorded" not in resp.text
