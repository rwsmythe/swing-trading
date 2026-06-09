"""Request-id middleware and rotating web.log setup."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from swing.logging_config import configure_logging

_access_log = logging.getLogger("swing.web.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - t0) * 1000)
        response.headers["X-Request-ID"] = rid
        _access_log.info(
            "%s %s %d %dms %s",
            request.method, request.url.path, response.status_code,
            duration_ms, rid,
        )
        return response


def configure_web_logging(logs_dir: Path) -> None:
    """Thin shim over the shared seam (no formatter override -> default formatter)."""
    configure_logging(logs_dir, surface="web")
