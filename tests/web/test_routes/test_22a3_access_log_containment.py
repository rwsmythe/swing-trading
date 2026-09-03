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


# ===========================================================================
# CODEX ROUND 1 -- A3-AR-04, the DOUBLE-FAULT path.
# ===========================================================================


def test_A3_AR_04_a_failing_header_stamp_cannot_destroy_the_response():
    """Codex A3-AR-04 (MINOR).

    The containment's own observability write was UNGUARDED, so a header
    mutation that raises while a logging failure is already being handled
    would destroy the completed response the guard exists to protect --
    falsifying the containment claim one statement after making it.

    Driven against `dispatch` directly, because the failure needs a response
    whose header mutation raises and no route produces one.

    PRE-fix the `RuntimeError` from the header stamp escapes `dispatch`;
    POST-fix the response is returned unchanged. Observability is best-effort;
    the RESPONSE is not.
    """
    import asyncio
    import logging
    from types import SimpleNamespace

    from swing.web.middleware.request_id import RequestIdMiddleware

    class _Headers(dict):
        def __setitem__(self, key, value):
            if key == "X-Access-Log-Failed":
                raise RuntimeError("22-A3 PROBE: header mutation failed")
            dict.__setitem__(self, key, value)

    class _Response:
        status_code = 200

        def __init__(self):
            self.headers = _Headers()

    response = _Response()

    async def _call_next(request):
        return response

    request = SimpleNamespace(
        method="POST", url=SimpleNamespace(path="/trades/entry"),
        state=SimpleNamespace())

    class _BrokenAccess(logging.Handler):
        def emit(self, record):
            raise RuntimeError("22-A3 PROBE: access log sink failed")

    sink = _BrokenAccess(level=logging.INFO)
    access_log = logging.getLogger("swing.web.access")
    # **THE LEVEL IS SET EXPLICITLY, AND THAT IS NOT INCIDENTAL.** The
    # logger's default EFFECTIVE level is WARNING (measured: 30), so
    # `_access_log.info(...)` is a no-op that never reaches a handler -- and
    # the first draft of this test therefore PASSED under its own mutation,
    # i.e. it was vacuous. Caught by running the mutation; kept as a comment
    # so it cannot silently return.
    prior_level = access_log.level
    access_log.setLevel(logging.INFO)
    access_log.addHandler(sink)
    try:
        middleware = RequestIdMiddleware(app=lambda *a, **k: None)
        out = asyncio.run(middleware.dispatch(request, _call_next))
    finally:
        access_log.removeHandler(sink)
        access_log.setLevel(prior_level)

    assert out is response, "the completed response was destroyed"
    assert out.headers.get("X-Request-ID") is not None
    assert "X-Access-Log-Failed" not in out.headers, (
        "the stamp itself failed, which is exactly the case under test")
