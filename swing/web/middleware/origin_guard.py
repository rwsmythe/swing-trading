"""Origin/HX-Request/Referer guard for state-changing requests.

Two modes:
- Non-strict (default): accepts HX-Request OR same-Origin OR same-Referer on unsafe methods.
- Strict (spec §3.3): requires HX-Request on unsafe methods; Origin/Referer fallbacks
  are removed. Narrows the accepted-header matrix for defense-in-depth; does NOT add
  cryptographic CSRF (see spec §1.1 threat model).

GET/HEAD/OPTIONS are always passed through in both modes.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class OriginGuardMiddleware(BaseHTTPMiddleware):
    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app, *, bound_host: str, bound_port: int, strict: bool = False):
        super().__init__(app)
        self._expected_origin = f"http://{bound_host}:{bound_port}"
        self._strict = strict

    async def dispatch(self, request: Request, call_next):
        if request.method in self._SAFE_METHODS:
            return await call_next(request)

        headers = request.headers
        if headers.get("HX-Request", "").lower() == "true":
            return await call_next(request)

        if self._strict:
            return Response(
                status_code=403,
                content="Missing HX-Request header (strict mode)",
                media_type="text/plain",
            )

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
