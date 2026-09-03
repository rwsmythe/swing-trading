"""22-A3 (o) -- the OUTERMOST middleware cannot destroy the response this arc
builds.

FOLDED INTO THE ENVELOPE BY RULING 2026-09-02, ON ONE GROUND AND BOUNDED BY
IT: 22-A3's acceptance criterion is that **the operator SEES the degraded
success**, and that response transits `RequestIdMiddleware`, which is
OUTERMOST (`swing/web/app.py`, and the comment there says so) and access-logs
AFTER `call_next` returns while holding the route's FINISHED response.  A
raising `swing.web.access` handler there converts a correct 200 -- including
this arc's degraded-success 200 -- into the refusal-shaped 500, one frame
outside every guard a route can install.

**EVERY OTHER TEST IN THIS ARC CAN PASS WHILE THIS ONE FAILS.**

THE BOUND IS EXACT: this ONE call and this test. **NO MIDDLEWARE SWEEP** --
other instances of the class in other middleware are banked follow-ons.
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests.web.test_routes.test_22a3_entry_degraded_success import (
    _patch_price_cache,
    _post_entry,
    _seed_minimal_dashboard_state,
    _trade_count,
)


class _BrokenAccessSink(logging.Handler):
    def emit(self, record):
        raise RuntimeError("22-A3 PROBE: access log sink failed")


def test_o_a_failing_access_log_cannot_destroy_a_completed_response(
        seeded_db, monkeypatch):
    """PRE-fix 500 over one durable row, with `X-Request-ID` ABSENT; POST-fix
    200 carrying `X-Request-ID` and `X-Access-Log-Failed`.

    THE HEADER IS THE POINT, NOT AN EXTRA: without asserting it a
    `try/except: pass` would pass this test, which is the same shape the (d)
    tests refuse. The containment is SWALLOWED-AND-NOTED, not swallowed.

    `X-Request-ID` is ABSENT pre-fix and it is worth saying why, because the
    stamp PRECEDES the log call: it is stamped on the INNER response, which
    is DISCARDED when `_access_log.info` raises, and `ServerErrorMiddleware`
    then builds a DIFFERENT 500 response OUTSIDE `RequestIdMiddleware` --
    one that never had the header.
    """
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    sink = _BrokenAccessSink(level=logging.INFO)
    access_log = logging.getLogger("swing.web.access")
    access_log.addHandler(sink)
    try:
        app = create_app(cfg, cfg_path)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = _post_entry(client)
    finally:
        access_log.removeHandler(sink)

    assert _trade_count(cfg) == 1, (
        "the premise: the entry was durable in the pre-fix run too, which is "
        "exactly why the 500 was a wrong report")
    assert resp.status_code == 200, resp.text[:400]
    assert resp.headers.get("X-Request-ID") is not None
    assert resp.headers.get("X-Access-Log-Failed") == "1", (
        "the containment must be swallowed-AND-NOTED; a bare pass would "
        "leave the failure invisible")


def test_o_control_an_intact_access_log_stamps_no_failure_header(
        seeded_db, monkeypatch):
    """Without this control the header assertion above could pass against an
    implementation that stamps it unconditionally."""
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)
    _patch_price_cache(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = _post_entry(client)

    assert resp.status_code == 200, resp.text[:400]
    assert resp.headers.get("X-Request-ID") is not None
    assert "X-Access-Log-Failed" not in resp.headers
