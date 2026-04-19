"""Request-id middleware and rotating web.log setup."""
from __future__ import annotations

import logging
import time
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = str(logs_dir / "web.log")
    root = logging.getLogger()
    # Idempotent: avoid duplicate handlers if create_app is called multiple
    # times (pytest runs thousands of tests through fixtures that build apps;
    # handler leakage would multiply every log line in later tests).
    for h in root.handlers:
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == target:
            return
    handler = TimedRotatingFileHandler(
        filename=target,
        when="D", interval=1, backupCount=7, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
