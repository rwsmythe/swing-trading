"""MaxBodySizeMiddleware — Content-Length pre-read guard.

Rejects requests to a configured path whose declared Content-Length exceeds a
byte limit, BEFORE FastAPI's multipart parameter binding reads the body.
Spec §3.1 (Phase 3c CSV-upload layer 1 defense).

For chunked-transfer requests (no Content-Length header), the middleware lets
the request through — a route-level `file.size` safety net catches those.

Renders the same `csv_upload_error.html.j2` fragment the route uses for
schema-invalid rejections, so the HTMX swap target (#csv-upload-section) sees
a consistent UI whether rejection came from the middleware or the route.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject POSTs to `path_prefix` whose Content-Length > `max_bytes`.

    Arguments (keyword-only):
        path_prefix: exact path match, e.g. "/pipeline/csv-upload". Only POSTs
            to paths EQUAL to this value are inspected. Other requests (including
            sub-paths like `/pipeline/csv-upload/foo` if such routes are added
            later) pass through unchanged.
        max_bytes: inclusive upper bound. Content-Length > max_bytes → 413
            rendering `csv_upload_error.html.j2`.
    """

    def __init__(self, app, *, path_prefix: str, max_bytes: int):
        super().__init__(app)
        # Name kept as `path_prefix` for backward-compat of the kwarg; actual
        # comparison is exact equality. Rename if the comparison ever needs
        # to be prefix-based.
        self._path_prefix = path_prefix
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        # Exact-path match (not startswith) — a future `/pipeline/csv-upload/foo`
        # route would be unrelated and shouldn't silently inherit this guard.
        if (
            request.method == "POST"
            and request.url.path == self._path_prefix
        ):
            cl_header = request.headers.get("content-length")
            if cl_header is not None:
                try:
                    declared = int(cl_header)
                except ValueError:
                    declared = -1
                if declared > self._max_bytes:
                    tpls = request.app.state.templates
                    return tpls.TemplateResponse(
                        request, "partials/csv_upload_error.html.j2",
                        {"reasons": [
                            f"file too large "
                            f"(Content-Length: {declared} > {self._max_bytes} bytes)"
                        ]},
                        status_code=413,
                    )
        return await call_next(request)
