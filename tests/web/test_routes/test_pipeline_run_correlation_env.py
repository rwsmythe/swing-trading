from __future__ import annotations

import subprocess
from datetime import datetime

from fastapi.testclient import TestClient

import swing.web.routes.pipeline as pipeline_route
from swing.data.db import connect
from swing.web.app import create_app


def test_route_popen_receives_request_id_env(seeded_db, monkeypatch):
    # ROUTE-LEVEL discriminator (R1-major-2): POST /pipeline/run and assert the
    # kwargs the route hands to subprocess.Popen carry env["SWING_WEB_REQUEST_ID"]
    # AND preserve DEVNULL/close_fds/start_new_session. Modeled on the existing
    # test_post_pipeline_run_spawns_subprocess. Discriminator: if the production
    # spawn omits env=_build_subprocess_env(request_id), "env" is absent and this
    # FAILS -- a helper-only test would not catch that.
    cfg, cfg_path = seeded_db
    captured = {}

    class FakeProc:
        pid = 4242
        def poll(self):
            return None  # still running -> route polls for the lease row

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        # Simulate the child acquiring the lease so the route returns 200.
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                conn.execute(
                    """INSERT INTO pipeline_runs
                       (started_ts, trigger, data_asof_date, action_session_date,
                        state, lease_token, lease_heartbeat_ts)
                       VALUES (?, 'manual', '2026-04-17', '2026-04-20',
                               'running', 'subprocess-tok', ?)""",
                    (datetime.now().isoformat(timespec="seconds"),
                     datetime.now().isoformat(timespec="seconds")),
                )
        finally:
            conn.close()
        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    kw = captured["kwargs"]
    rid = kw["env"]["SWING_WEB_REQUEST_ID"]
    # STRONG discriminator (R2-major-2): the child env id must equal the ACTUAL web
    # request id for this request -- the web.log <-> pipeline.log join chain. The
    # RequestIdMiddleware echoes that id in the X-Request-ID response header, so
    # equality here proves the route passed the real per-request id (not a hardcoded
    # or stale token that would still match the regex shape).
    assert rid == r.headers["X-Request-ID"]
    import re
    assert re.match(r"^[A-Za-z0-9-]{1,64}$", rid)  # also conforms to the token shape
    # The spawn contract is otherwise preserved.
    assert kw["stdout"] is subprocess.DEVNULL
    assert kw["stderr"] is subprocess.DEVNULL
    assert kw["close_fds"] is True
    assert kw["start_new_session"] is True


def test_build_subprocess_env_is_copy(monkeypatch):
    # Unit: the helper returns a COPY (mutating it must not touch os.environ) and
    # stamps the request id.
    import os
    monkeypatch.setenv("SOME_EXISTING", "1")
    env = pipeline_route._build_subprocess_env("rid-x")
    assert env["SWING_WEB_REQUEST_ID"] == "rid-x"
    assert env["SOME_EXISTING"] == "1"
    env["SOME_EXISTING"] = "2"
    assert os.environ["SOME_EXISTING"] == "1"
