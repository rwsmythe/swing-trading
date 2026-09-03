"""Request-id middleware and rotating web.log setup."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from swing.logging_config import (
    CORRELATION_LOG_DEFAULTS,
    DEFAULT_LOG_FORMAT,
    configure_logging,
)
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
        # **A FAILING ACCESS-LOG SINK MUST NOT DESTROY A COMPLETED RESPONSE**
        # (22-A3, folded in by ruling 2026-09-02). This middleware is
        # OUTERMOST (see `swing/web/app.py`'s `add_middleware` ordering
        # comment), so when it logs it is holding the route's FINISHED
        # response -- and a raising handler here turns a correct 200 into a
        # 500 via `ServerErrorMiddleware`, one frame outside every guard a
        # route can install. 22-A3's acceptance criterion is that the
        # operator SEES the degraded-success response; this is the LAST
        # IDENTIFIED IN-PROCESS PRE-SEND site it can be taken from him --
        # response DELIVERY is still beyond reach.
        #
        # THE GUARD IS INLINE RATHER THAN `swing.trades.entry.log_contained`
        # ON PURPOSE: a web middleware must not import the trades service --
        # that would pull the data layer into middleware import time. The
        # four-line duplication is deliberate and declared.
        #
        # AND IT IS NOT SILENT: the failure is stamped on the response as a
        # header, because a swallowed logging failure is the invisible-failure
        # trade the containment idiom exists to refuse.
        #
        # THE BOUND IS EXACT: this ONE call. **NO MIDDLEWARE SWEEP** -- other
        # instances of the class in other middleware are banked follow-ons,
        # not this arc's.
        try:
            _access_log.info(
                "%s %s %d %dms %s",
                request.method, request.url.path, response.status_code,
                duration_ms, rid,
            )
        except BaseException:  # noqa: BLE001 -- the CLASS, not a roster
            # `pass` is deliberately NOT the handler body: ruff's B110
            # (try-except-pass) is in the selected `B` ruleset, and a header
            # stamp is both lint-clean and strictly better -- it makes the
            # swallowed failure observable to the very test that pins it.
            response.headers["X-Access-Log-Failed"] = "1"
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
        formatter=RedactingFormatter(DEFAULT_LOG_FORMAT, defaults=CORRELATION_LOG_DEFAULTS),
        max_bytes=default.max_bytes,
        backup_count=default.backup_count,
        install_record_factory=ensure_schwab_log_redaction_factory_installed,
    )
