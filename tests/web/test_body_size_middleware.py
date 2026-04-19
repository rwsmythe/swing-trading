"""MaxBodySizeMiddleware — Content-Length pre-read guard for /pipeline/csv-upload.
Spec §3.1 layer 1."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_middleware_rejects_oversized_content_length(test_cfg, seeded_db):
    """Content-Length header exceeds limit → 413 rendering csv_upload_error.html.j2.
    The middleware uses the same template the route uses for other rejections,
    so HTMX can swap it into #csv-upload-section without visual regression."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        oversize = cfg.web.csv_upload_max_bytes + 1
        r = client.post(
            "/pipeline/csv-upload",
            headers={
                "HX-Request": "true",
                "Content-Length": str(oversize),
                "Content-Type": "multipart/form-data; boundary=---x",
            },
            content=b"irrelevant",
        )
    assert r.status_code == 413
    assert 'id="csv-upload-section"' in r.text
    assert "too large" in r.text.lower()


def test_middleware_passes_through_within_limit(test_cfg, seeded_db):
    """Content-Length within limit → middleware lets the request through to the route
    (route is Task 16; before then, the request 404s or 405s, not 413)."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={
                "HX-Request": "true",
                "Content-Length": "100",
                "Content-Type": "multipart/form-data; boundary=---x",
            },
            content=b"x" * 100,
        )
    # Before Task 16 this route doesn't exist, so expect 404 or 405 (or 400).
    # Key assertion: NOT 413.
    assert r.status_code != 413


def test_middleware_ignores_non_csv_upload_paths(test_cfg, seeded_db):
    """Middleware only applies to /pipeline/csv-upload POSTs. Other routes
    with a large Content-Length aren't rejected by this middleware."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/",
            headers={"Content-Length": str(cfg.web.csv_upload_max_bytes + 1)},
        )
    # GET / is unaffected — the dashboard renders fine.
    assert r.status_code == 200
