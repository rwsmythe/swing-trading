"""Origin / HX-Request / Referer accepted-header matrix."""
from __future__ import annotations

from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from swing.web.middleware.origin_guard import OriginGuardMiddleware


def _app_with_test_route(bound_host: str = "127.0.0.1", bound_port: int = 8080) -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginGuardMiddleware, bound_host=bound_host, bound_port=bound_port)

    router = APIRouter()

    @router.get("/ping")
    def ping():
        return {"ok": True}

    @router.post("/action")
    def action():
        return {"ok": True}

    app.include_router(router)
    return app


def test_get_always_allowed_no_headers():
    client = TestClient(_app_with_test_route())
    r = client.get("/ping")
    assert r.status_code == 200


def test_post_with_hx_request_header_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"HX-Request": "true"})
    assert r.status_code == 200


def test_post_with_same_origin_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Origin": "http://127.0.0.1:8080"})
    assert r.status_code == 200


def test_post_with_same_origin_referer_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Referer": "http://127.0.0.1:8080/pipeline"})
    assert r.status_code == 200


def test_post_cross_origin_blocked():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_post_no_headers_blocked():
    client = TestClient(_app_with_test_route())
    r = client.post("/action")
    assert r.status_code == 403
