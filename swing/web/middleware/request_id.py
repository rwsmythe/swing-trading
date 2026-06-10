"""Request-id middleware and rotating web.log setup."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from swing.logging_config import DEFAULT_LOG_FORMAT, configure_logging
from swing.logging_setup import install_logging

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


def configure_web_logging(logs_dir: Path, cfg=None) -> None:
    """Back-compat shim over the redacted/bounded web logging path (Arc-1 lock:
    RETAINED, not removed). With ``cfg`` it forwards to the composition root;
    without it (legacy logs_dir-only callers) it constructs a minimal default
    LoggingConfig and routes through the SAME redaction + rotation wiring.
    Either way web.log behavior is preserved AND redaction is now added
    (strictly additive)."""
    if cfg is not None:
        install_logging(cfg, surface="web")   # module-level symbol -> monkeypatchable
        return
    # Legacy path: default knobs + the same belts.
    from swing.config import LoggingConfig
    from swing.integrations.schwab.client import (
        RedactingFormatter,
        ensure_schwab_log_redaction_factory_installed,
    )

    default = LoggingConfig()
    configure_logging(
        logs_dir,
        surface="web",
        level=default.level,
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT),
        max_bytes=default.max_bytes,
        backup_count=default.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,
    )
