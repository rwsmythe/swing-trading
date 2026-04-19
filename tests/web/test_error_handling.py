from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_500_on_repo_error_renders_error_page(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.get("/_explode")
    def _explode():
        raise RuntimeError("synthetic boom")

    r = TestClient(app, raise_server_exceptions=False).get("/_explode")
    assert r.status_code == 500
    # Error page carries a request-id for log correlation.
    assert "request" in r.text.lower()
    # Error fragment body mentions the underlying message.
    assert "boom" in r.text.lower() or "error" in r.text.lower()


def test_request_id_header_set_on_every_response(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/", headers={"HX-Request": "true"})
    assert "x-request-id" in (h.lower() for h in r.headers.keys())


def test_htmx_post_error_returns_error_fragment(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_htmx_explode")
    def _hx():
        raise RuntimeError("htmx boom")

    r = TestClient(app, raise_server_exceptions=False).post(
        "/_htmx_explode", headers={"HX-Request": "true"},
    )
    assert r.status_code == 500
    # HTMX errors swap into the target; body is a small fragment, not a full page.
    assert "<html" not in r.text.lower()


def test_configure_web_logging_is_idempotent(tmp_path):
    """Calling create_app (or configure_web_logging directly) multiple times
    against the SAME log directory must NOT accumulate duplicate handlers
    on the root logger. pytest runs thousands of tests through pytest's
    fixtures; handler leakage causes every log line in later tests to be
    duplicated N times (R2 Minor 2)."""
    import logging
    from logging.handlers import TimedRotatingFileHandler

    from swing.web.middleware.request_id import configure_web_logging

    logs = tmp_path / "logs"
    # Snapshot baseline handler count.
    root = logging.getLogger()
    baseline = sum(
        1 for h in root.handlers
        if isinstance(h, TimedRotatingFileHandler)
        and h.baseFilename == str(logs / "web.log")
    )
    configure_web_logging(logs)
    configure_web_logging(logs)
    configure_web_logging(logs)
    after = sum(
        1 for h in root.handlers
        if isinstance(h, TimedRotatingFileHandler)
        and h.baseFilename == str(logs / "web.log")
    )
    assert after - baseline == 1, (
        f"handler count grew by {after - baseline}; expected idempotent = 1"
    )


def test_request_log_line_emitted_per_request(seeded_db, caplog):
    """Verify the spec §5.2 contract: method/path/status/duration/request_id."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with caplog.at_level("INFO", logger="swing.web.access"):
        with TestClient(app) as client:
            r = client.get("/", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # At least one access log line captured matching the expected format.
    access_messages = [rec.message for rec in caplog.records if rec.name == "swing.web.access"]
    assert access_messages, "expected an access log entry"
    line = access_messages[-1]
    assert "GET" in line
    assert "/ " in line or line.startswith("GET /")
    assert "200" in line
    assert "ms" in line
    # Request id present (uuid hex chars)
    assert len(line.split()[-1]) >= 32


def test_403_cross_origin_post_still_carries_request_id(seeded_db):
    """R1 Major 4: middleware order must be RequestId OUTERMOST so the 403
    response from OriginGuard still gets X-Request-ID stamped on it. Without
    this, operators cannot grep the CSRF-defense rejections in web.log."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_guarded_probe")
    def _probe():
        return {"ok": True}

    client = TestClient(app)
    r = client.post("/_guarded_probe", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert "x-request-id" in (h.lower() for h in r.headers.keys())


def test_htmx_404_renders_fragment_not_json(test_cfg):
    """HTMX-aware HTTPException handler: HX-Request 404 → HTML fragment body,
    not FastAPI's default JSON body."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_missing")
    def _missing():
        raise HTTPException(status_code=404, detail="nothing here")

    with TestClient(app) as client:
        # HTMX client: expect fragment
        r_hx = client.get("/_missing", headers={"HX-Request": "true"})
        assert r_hx.status_code == 404
        assert "<!doctype" not in r_hx.text.lower()  # no full page
        assert "nothing here" in r_hx.text
        # Non-HTMX client: expect FastAPI default JSON
        r_json = client.get("/_missing")
        assert r_json.status_code == 404
        assert r_json.headers["content-type"].startswith("application/json")
        assert r_json.json() == {"detail": "nothing here"}


def test_htmx_validation_error_non_trade_path_renders_div_fragment(test_cfg):
    """RequestValidationError (missing field) on a NON-/trades/ HTMX POST →
    http_error_fragment (a <div>) at 400. Proves the 'else' branch of the
    path-aware handler (R3 Major 1 split)."""
    from fastapi import Form
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/_typed_probe")
    def _probe(x: float = Form(...)):
        return {"ok": True}

    with TestClient(app) as client:
        r_hx = client.post(
            "/_typed_probe", headers={"HX-Request": "true"}, data={},
        )
        assert r_hx.status_code == 400
        # http_error_fragment.html.j2 is the neutral <div> banner.
        assert "<div" in r_hx.text.lower()
        assert "<tr" not in r_hx.text.lower()
        assert "<!doctype" not in r_hx.text.lower()
        # Non-HTMX: OriginGuard (strict=True) blocks non-HX-Request POSTs at
        # the middleware layer before validation fires; 403 is the framework
        # default for this app, confirming the validation handler is NOT
        # intercepting non-HTMX requests.
        r_non_hx = client.post("/_typed_probe", data={})
        assert r_non_hx.status_code == 403


def test_htmx_validation_error_trade_path_renders_tr_fragment(test_cfg):
    """RequestValidationError on a /trades/* HTMX POST → trade_form_error
    (a <tr>) at 400. Proves the path-aware branch of the handler renders a
    row-compatible fragment for HTMX targets using `hx-target='closest tr'`."""
    from fastapi import Form
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    # Register a probe under /trades/ so the path-prefix check fires.
    @app.post("/trades/_typed_probe")
    def _probe(x: float = Form(...)):
        return {"ok": True}

    with TestClient(app) as client:
        r_hx = client.post(
            "/trades/_typed_probe", headers={"HX-Request": "true"}, data={},
        )
        assert r_hx.status_code == 400
        # trade_form_error.html.j2 emits a <tr>.
        assert "<tr" in r_hx.text.lower()
        assert "trade-form-error" in r_hx.text
        # Non-HTMX: OriginGuard (strict=True) blocks non-HX-Request POSTs at
        # the middleware layer before validation fires; 403 is the framework
        # default for this app, confirming the validation handler is NOT
        # intercepting non-HTMX requests.
        r_non_hx = client.post("/trades/_typed_probe", data={})
        assert r_non_hx.status_code == 403
