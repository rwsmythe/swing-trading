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
