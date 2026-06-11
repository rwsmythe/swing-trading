"""Process-global run/request correlation ids for log records (Arc-2 Slice-2).

NEUTRAL by construction: imports nothing from swing.integrations.schwab and
nothing from swing.config -- so the composition root (swing/logging_setup.py)
can import it without re-introducing a cycle, and the seam stays untouched.

WHY process-globals, not contextvars (spec R2-major-3): the ids are
process/run-scoped, not task-local. The pipeline subprocess emits records from
worker threads (the price-fetch executor, threaded steps) that would NOT inherit
a ``ContextVar`` set on the main thread -- a contextvar would silently drop the
id on those records. A lock-guarded module global is single-writer (env at
install; lease once) / many-reader and correct across all threads.
"""
from __future__ import annotations

import logging
import os
import re
import threading

ENV_VAR = "SWING_WEB_REQUEST_ID"
PLACEHOLDER = "-"
# Strict token shape: the uuid4 the web emits is [0-9a-f-]; we allow the broader
# alnum+hyphen set, length 1..64. Anything with whitespace/newlines/punctuation
# or over-length is REJECTED to a placeholder (defends against an inherited or
# forged env var injecting newlines / misleading content into log lines).
# NB: matched with re.fullmatch (NOT re.match), because re.match anchored with `$`
# still accepts a SINGLE trailing newline ("abc\n") -- `$` matches before a final
# "\n" -- which would inject a newline into a log line. fullmatch has no such gap.
_VALID_TOKEN = re.compile(r"[A-Za-z0-9-]{1,64}")

_lock = threading.Lock()
_web_request_id: str = PLACEHOLDER          # validated env value or "-"
_pipeline_run_id: str | None = None         # None until the lease is held


def _validate_token(raw: str | None) -> str:
    if raw is not None and _VALID_TOKEN.fullmatch(raw):
        return raw
    return PLACEHOLDER


def reset_correlation_from_env() -> None:
    """Reset BOTH globals at install (spec R3-minor-3): pipeline_run_id -> None
    (no run yet), web_request_id -> validated SWING_WEB_REQUEST_ID or "-". Called
    at the START of install_logging, before seeding, so a stale pipeline_run_id
    from an earlier run in the same process cannot bleed into later records."""
    global _web_request_id, _pipeline_run_id
    with _lock:
        _web_request_id = _validate_token(os.environ.get(ENV_VAR))
        _pipeline_run_id = None


def set_pipeline_run_id(run_id: int | str | None) -> None:
    """Set the run id after the pipeline lease row is inserted. None -> placeholder."""
    global _pipeline_run_id
    with _lock:
        _pipeline_run_id = None if run_id is None else str(run_id)


def get_web_request_id() -> str:
    with _lock:
        return _web_request_id


def get_pipeline_run_id() -> str:
    with _lock:
        return _pipeline_run_id if _pipeline_run_id is not None else PLACEHOLDER


def _set_for_test(*, web_request_id: str, pipeline_run_id: str | None) -> None:
    """Test-only direct seam (no env round-trip). Not used in production paths."""
    global _web_request_id, _pipeline_run_id
    with _lock:
        _web_request_id = web_request_id
        _pipeline_run_id = pipeline_run_id


class CorrelationFilter(logging.Filter):
    """Stamps record.web_request_id / record.pipeline_run_id from the process
    globals at filter() time (per record, any thread). Always returns True.

    Reading at filter() time -- not at construction -- means a value set AFTER
    the handler is installed (e.g. set_pipeline_run_id at lease acquisition) is
    picked up on the next record from any thread."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.web_request_id = get_web_request_id()
        record.pipeline_run_id = get_pipeline_run_id()
        return True
