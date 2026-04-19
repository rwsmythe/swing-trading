"""Origin/HX-Request/Referer guard for state-changing requests.

Accepts a request when ANY of:
  - HX-Request: true header is present
  - Origin header equals http://<bound_host>:<bound_port>
  - Referer header starts with http://<bound_host>:<bound_port>/

GET/HEAD/OPTIONS are always passed through.
Everything else failing the matrix returns 403.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class OriginGuardMiddleware(BaseHTTPMiddleware):
    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app, *, bound_host: str, bound_port: int):
        super().__init__(app)
        self._expected_origin = f"http://{bound_host}:{bound_port}"

    async def dispatch(self, request: Request, call_next):
        if request.method in self._SAFE_METHODS:
            return await call_next(request)

        headers = request.headers
        if headers.get("HX-Request", "").lower() == "true":
            return await call_next(request)

        origin = headers.get("Origin")
        if origin is not None:
            if origin == self._expected_origin:
                return await call_next(request)
            return Response(
                status_code=403,
                content=f"Cross-origin request blocked (origin={origin})",
                media_type="text/plain",
            )

        referer = headers.get("Referer", "")
        if referer.startswith(self._expected_origin + "/"):
            return await call_next(request)

        return Response(
            status_code=403,
            content="Missing HX-Request / Origin / Referer same-origin signal",
            media_type="text/plain",
        )
