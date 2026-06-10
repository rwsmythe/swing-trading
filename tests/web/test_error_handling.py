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


def test_handle_any_returns_row_fragment_for_row_target_htmx(seeded_db):
    """Bug 2 follow-up (T7): when an unhandled non-HTTPException fires
    inside an HTMX request whose HX-Target is a row-prefix value (entry-
    form-*, exit-form-*, stop-form-*, watchlist-row-*, open-position-*),
    the response body must be a <tr> fragment from
    partials/trade_form_error.html.j2 — NOT a <div> from
    partials/error_fragment.html.j2.

    Pre-fix: body starts with `<div class="banner banner-degraded">`.
    Post-fix: body starts with `<tr ...>`.

    This is the same row-target awareness `_handle_http_exc` already has;
    `_handle_any` was the gap.
    """
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_row_target_explode")
    def _hx_row():
        raise RuntimeError("simulated row-target explosion")

    r = TestClient(app, raise_server_exceptions=False).post(
        "/_row_target_explode",
        headers={
            "HX-Request": "true",
            # Use one of the _ROW_TARGET_PREFIXES values so the row-target
            # branch is selected. entry-form-* matches the entry-row case
            # the operator hits when submitting the trade entry form.
            "HX-Target": "entry-form-watchlist-row-AAPL",
        },
    )
    assert r.status_code == 500
    body = r.text.lstrip()
    assert body.startswith("<tr"), (
        f"row-target HTMX request must receive a <tr> fragment from "
        f"trade_form_error; pre-fix returns <div> from error_fragment. "
        f"Got: {body[:100]!r}"
    )
    # Discriminator in the negative direction: the pre-fix banner-degraded
    # marker MUST NOT lead the body. (It may appear in the inner banner
    # div inside the <tr>, so we check it does not LEAD the body.)
    assert not body.startswith('<div class="banner banner-degraded"')


def test_handle_any_returns_div_fragment_for_non_row_target_htmx(seeded_db):
    """Symmetric to the row-target test: when HX-Target is NOT a row prefix
    (e.g. sizing-hint, run-panel, plain dashboard fragments), the existing
    error_fragment <div> shape is preserved. Guards against the row-target
    awareness over-triggering."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_non_row_target_explode")
    def _hx_norow():
        raise RuntimeError("simulated non-row-target explosion")

    r = TestClient(app, raise_server_exceptions=False).post(
        "/_non_row_target_explode",
        headers={
            "HX-Request": "true",
            "HX-Target": "sizing-hint",
        },
    )
    assert r.status_code == 500
    body = r.text.lstrip()
    assert not body.startswith("<tr"), (
        f"non-row-target must NOT receive a <tr> fragment; got: {body[:100]!r}"
    )


def test_configure_web_logging_is_idempotent(tmp_path):
    """Calling create_app (or configure_web_logging directly) multiple times
    against the SAME log directory must NOT accumulate duplicate handlers
    on the root logger. pytest runs thousands of tests through pytest's
    fixtures; handler leakage causes every log line in later tests to be
    duplicated N times (R2 Minor 2)."""
    import logging
    from logging.handlers import RotatingFileHandler

    from swing.web.middleware.request_id import configure_web_logging

    logs = tmp_path / "logs"
    # Snapshot baseline handler count.
    root = logging.getLogger()
    baseline = sum(
        1 for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and h.baseFilename == str(logs / "web.log")
    )
    configure_web_logging(logs)
    configure_web_logging(logs)
    configure_web_logging(logs)
    after = sum(
        1 for h in root.handlers
        if isinstance(h, RotatingFileHandler)
        and h.baseFilename == str(logs / "web.log")
    )
    assert after - baseline == 1, (
        f"handler count grew by {after - baseline}; expected idempotent = 1"
    )


def test_configure_web_logging_no_cfg_attaches_redacting_handler(tmp_path):
    # Back-compat shim (Arc-1 lock): legacy logs_dir-only callers still work AND
    # now get redaction (strictly additive). Discriminator: pre-Slice-1 the shim
    # attached a plain default formatter -> this isinstance check would FAIL.
    import logging
    import os
    from logging.handlers import RotatingFileHandler
    import swing.integrations.schwab.client as schwab_client
    from swing.integrations.schwab.client import RedactingFormatter
    from swing.web.middleware.request_id import configure_web_logging

    root = logging.getLogger()
    saved = list(root.handlers)
    # configure_web_logging now ALSO sets root level + installs the global Schwab
    # LogRecord factory + may register secrets -> snapshot/restore ALL of them so a
    # large suite is not contaminated (matches the pipeline_logging fixture).
    saved_level = root.level
    saved_factory = logging.getLogRecordFactory()
    saved_secrets = set(schwab_client._GLOBAL_KNOWN_SECRETS)
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        configure_web_logging(tmp_path)
        target = os.path.abspath(tmp_path / "web.log")
        handlers = [
            h for h in root.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ]
        assert len(handlers) == 1
        assert isinstance(handlers[0].formatter, RedactingFormatter)
        # Idempotent.
        configure_web_logging(tmp_path)
        assert len([
            h for h in root.handlers
            if isinstance(h, RotatingFileHandler) and h.baseFilename == target
        ]) == 1
    finally:
        for h in list(root.handlers):
            if isinstance(h, RotatingFileHandler):
                h.close()
            root.removeHandler(h)
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)
        logging.setLogRecordFactory(saved_factory)
        schwab_client._GLOBAL_KNOWN_SECRETS.clear()
        schwab_client._GLOBAL_KNOWN_SECRETS.update(saved_secrets)


def test_configure_web_logging_with_cfg_delegates_to_install_logging(tmp_path, monkeypatch):
    import swing.web.middleware.request_id as rid
    captured = {}
    monkeypatch.setattr(
        rid, "install_logging",
        lambda cfg, *, surface: captured.update(surface=surface, cfg=cfg),
    )
    sentinel_cfg = object()
    rid.configure_web_logging(tmp_path, cfg=sentinel_cfg)
    assert captured == {"surface": "web", "cfg": sentinel_cfg}


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
    """RequestValidationError on an HTMX POST with a row-prefix HX-Target →
    trade_form_error (a <tr>) at 400. Proves the HX-Target-aware branch of
    the handler renders a row-compatible fragment for HTMX targets using
    `hx-target='closest tr'` whose resolved id starts with a row prefix."""
    from fastapi import Form
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/trades/_typed_probe")
    def _probe(x: float = Form(...)):
        return {"ok": True}

    with TestClient(app) as client:
        r_hx = client.post(
            "/trades/_typed_probe",
            headers={"HX-Request": "true", "HX-Target": "open-position-1"},
            data={},
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


def test_htmx_handler_uses_hx_target_for_row_prefix(test_cfg, seeded_db):
    """Spec §3.3: HX-Target header determines fragment shape, not URL path.
    A /trades/* endpoint with a non-row HX-Target (e.g. sizing-hint) MUST get
    the neutral <div> fragment, not a <tr>.

    Uses /trades/probe/non_row to avoid collision with C.5's
    /trades/{trade_id} route — the bare {trade_id} matcher would coerce a
    non-numeric path segment via int validation and return a 422/400 from
    the validation-error handler before this probe's 404 could fire.
    """
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/trades/probe/non_row")
    def _probe():
        raise HTTPException(status_code=404, detail="probe missing")

    with TestClient(app) as client:
        r = client.get(
            "/trades/probe/non_row",
            headers={"HX-Request": "true", "HX-Target": "sizing-hint"},
        )
    assert r.status_code == 404
    # <div> shape from http_error_fragment.html.j2, NOT <tr>.
    assert "<div" in r.text.lower()
    assert "<tr" not in r.text.lower()
    assert "probe missing" in r.text


def test_htmx_handler_renders_tr_for_row_target(test_cfg, seeded_db):
    """Spec §3.3: row-prefix HX-Target → <tr> fragment from trade_form_error.html.j2."""
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/trades/_row_probe")
    def _probe():
        raise HTTPException(status_code=404, detail="trade #99 not found")

    with TestClient(app) as client:
        r = client.post(
            "/trades/_row_probe",
            headers={"HX-Request": "true", "HX-Target": "open-position-42"},
        )
    assert r.status_code == 404
    assert "<tr" in r.text.lower()
    assert "trade #99 not found" in r.text


def test_htmx_validation_error_on_get_with_row_target_renders_tr(test_cfg, seeded_db):
    """Regression: HX-Target drives fragment shape regardless of method.
    A GET validation error with a row-prefix HX-Target must render a <tr>,
    not a <div> — otherwise HTMX injects <div> into a <table>. Spec §3.3
    (Codex adversarial review Major 1)."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/trades/_row_get_probe")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/trades/_row_get_probe?mode=bad",
            headers={"HX-Request": "true", "HX-Target": "open-position-42"},
        )
    assert r.status_code == 400
    body_lower = r.text.lower()
    tr_pos = body_lower.find("<tr")
    div_pos = body_lower.find("<div")
    assert tr_pos >= 0, "expected <tr> row fragment"
    # Trade form error template has <tr><td><div class='banner'>…</div></td></tr>,
    # so <div> is allowed — but the OUTER element must be <tr>, not the neutral
    # http_error_fragment which starts with <div>.
    assert tr_pos < div_pos, (
        f"outer element should be <tr> (row fragment), not <div> "
        f"(tr_pos={tr_pos}, div_pos={div_pos})"
    )
    assert "Invalid input" in r.text


def test_htmx_validation_error_on_get_with_non_row_target_renders_div(test_cfg, seeded_db):
    """Symmetrical: non-row HX-Target on GET still gets the <div> fragment."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_non_row_get_probe")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/_non_row_get_probe?mode=bad",
            headers={"HX-Request": "true", "HX-Target": "sizing-hint"},
        )
    assert r.status_code == 400
    assert "<div" in r.text.lower()
    assert "<tr" not in r.text.lower()


def test_htmx_handler_uses_app_state_templates(test_cfg, seeded_db):
    """Spec §3.3: handlers use request.app.state.templates (not a per-call
    Jinja2Templates instance). We can't assert this directly from outside,
    but the smoke test here confirms the handler still renders correctly
    after the migration."""
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_smoke_404")
    def _probe():
        raise HTTPException(status_code=404, detail="smoke")

    with TestClient(app) as client:
        r = client.get("/_smoke_404", headers={"HX-Request": "true"})
    assert r.status_code == 404
    assert "smoke" in r.text


def test_non_htmx_get_with_bad_query_renders_full_page(test_cfg, seeded_db):
    """Spec §3.3 / §4.3: address-bar typo on /journal?period=<bad> with
    Accept: text/html → full-page page_error.html.j2, not 422 JSON."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    # Register a synthetic GET endpoint that uses a Literal param (similar to
    # /journal's eventual shape) so RequestValidationError fires on invalid values.
    @app.get("/_typed_query_probe")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/_typed_query_probe?mode=nope",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "text/html" in r.headers.get("content-type", "")
    # Full-page error — contains base layout chrome (nav) + the detail.
    assert "<html" in r.text.lower()
    assert "Return to dashboard" in r.text
    assert "mode" in r.text  # field name appears in detail


def test_non_htmx_get_escapes_html_in_validation_detail(test_cfg, seeded_db):
    """XSS guard: if a future validator raises with HTML in its message, the
    full-page 400 must escape it, not reflect it as markup."""
    from typing import Annotated
    from fastapi import Query as _Query
    import pydantic
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    def _evil_validator(v: str) -> str:
        raise ValueError(f'bad value: <script>alert("xss")</script> {v}')

    @app.get("/_xss_probe")
    def _probe(
        q: Annotated[str, pydantic.AfterValidator(_evil_validator), _Query()] = "ok",
    ):
        return {"q": q}

    with TestClient(app) as client:
        r = client.get(
            "/_xss_probe?q=trigger",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    body = r.text
    # Escaped markers must appear…
    assert "&lt;script&gt;" in body or "&lt;/script&gt;" in body
    # …and raw <script> must NOT be present in the body.
    assert "<script>alert" not in body


def test_non_htmx_get_json_accept_falls_through_to_422(test_cfg, seeded_db):
    """Spec §3.3 precedence rule #3: GET with Accept: application/json (no
    text/html) → FastAPI default 422 JSON, not the HTML page."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_typed_query_probe2")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/_typed_query_probe2?mode=nope",
            headers={"Accept": "application/json"},
        )
    assert r.status_code == 422
    assert "application/json" in r.headers.get("content-type", "")
    body = r.json()
    assert "detail" in body
