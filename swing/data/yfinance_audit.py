"""yfinance audit service + the shared ``_record_yf_download`` chokepoint helper
(Phase 18 Arc 18-C).

Parallels ``swing/integrations/schwab/audit_service.py`` (the three-piece
transactional discipline): a caller-controlled repo
(``swing/data/repos/yfinance_calls.py``), this transaction-owning service
(``record_call_start`` / ``record_call_finish``, each owning BEGIN IMMEDIATE /
COMMIT / ROLLBACK + rejecting a caller-held tx), and the instrumentation that
brackets the RAW ``yf.download`` at the 4 production chokepoints via
``_record_yf_download``.

DELIBERATE divergences from the Schwab audit:

- **Light redaction (no setLogRecordFactory).** yfinance carries NO auth token,
  so the heavy Schwab redaction machinery is unnecessary. ``error_message`` is
  defensively sanitized (collapse whitespace + truncate to 200 chars) -- a
  yfinance exception may embed a URL with query params (benign, no secret);
  truncation is hygiene.
- **Always-on / no ``environment`` gate.** Unlike ``_step_schwab_*``, the audit
  attempts in ALL environments whenever a context is active -- NO ``environment``
  param, NO sandbox short-circuit. "Always-on" = always ATTEMPTED; it is
  BEST-EFFORT on SQLite/audit failures (fast-fail, never blocks/sinks the fetch).
- **``busy_timeout=0`` (Codex R3/R12).** The audit connection opens with a 0ms
  busy timeout, so a contended BEGIN IMMEDIATE fails INSTANTLY (no wait). The
  ``_YF_AUDIT_WRITE_LOCK`` is held ONLY around each SHORT start/finish tx --
  NEVER across ``yf.download`` -- so same-process audits serialize
  deterministically (uncontended sub-ms INSERTs all record), there is NO
  ``N x timeout`` convoy, and cross-process / same-process-non-audit contention
  fails instantly (best-effort drop, the fetch is never delayed).
- **``success`` semantics.** ``status='success'`` means TRANSPORT/frame success
  (the raw ``yf.download`` returned rows) -- NOT data USABILITY. An all-NaN-Close
  intraday frame records ``success`` (raw rows present) even though the caller
  then raises a usability RuntimeError. 18-D's temporal-log non-finite scan is
  the usability authority; 18-C is transport health (COMPLEMENTARY).

Stale ``in_flight`` rows: a rare dropped finish (the contended-finish path)
leaves the row ``in_flight``. Monitors treat a stale ``in_flight`` as
INCOMPLETE/unknown, NOT a hung call. NO new status is added.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
from datetime import datetime
from time import monotonic

from swing.data.db import open_connection
from swing.data.repos import yfinance_calls as repo

log = logging.getLogger(__name__)

# busy_timeout=0 -> a contended BEGIN IMMEDIATE fails INSTANTLY (no wait), so the
# audit lock is never held across a wait and the fetch is never delayed (Codex
# R3/R12). The 30000ms project default would blow the 3s web price-fetch deadline.
YFINANCE_AUDIT_BUSY_TIMEOUT_MS = 0

# Held ONLY around each short start/finish BEGIN IMMEDIATE tx -- NEVER across
# yf.download. With busy_timeout=0 the critical section is always sub-ms, so
# same-process audits serialize deterministically with no fetch-time convoy.
_YF_AUDIT_WRITE_LOCK = threading.Lock()

_FINISH_VALID_STATUSES = frozenset({"success", "empty", "error"})

_ERROR_MESSAGE_MAX = 200


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes a yfinance audit service function while
    holding an open transaction. Single-transaction services own BEGIN
    IMMEDIATE / COMMIT / ROLLBACK; they REJECT caller-held tx rather than
    auto-detecting (CLAUDE.md in_transaction gotcha)."""


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _sanitize_error(exc: BaseException) -> str:
    """Collapse whitespace + truncate to 200 chars (light redaction; no secret
    surface). Matches the runner [:200] precedent.

    TOTAL by construction (Codex executing-R2 MAJOR): a hostile ``exc.__str__``
    must NEVER raise out of here -- the error path re-raises the ORIGINAL fetch
    exception after this, so a sanitize failure cannot be allowed to replace it
    (the no-measurement-change lock). On any failure fall back to the class name."""
    try:
        text = re.sub(r"\s+", " ", str(exc)).strip()
    except Exception:  # noqa: BLE001 -- hostile __str__; never mask the fetch exc
        try:
            return type(exc).__name__[:_ERROR_MESSAGE_MAX]
        except Exception:  # noqa: BLE001 -- truly pathological; last-resort sentinel
            return "unprintable_exception"
    return text[:_ERROR_MESSAGE_MAX]


def record_call_start(
    conn: sqlite3.Connection,
    *,
    ts: str,
    call_type: str,
    ticker: str | None,
    ticker_count: int | None,
    pipeline_run_id: int | None,
    surface: str,
) -> int:
    """Insert an in-flight yfinance_calls audit row. Returns the call_id.

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects a caller-held tx.
    """
    with _YF_AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "record_call_start owns its own transaction; caller MUST NOT "
                "hold an open transaction."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            call_id = repo.insert_in_flight(
                conn, ts=ts, call_type=call_type, ticker=ticker,
                ticker_count=ticker_count, pipeline_run_id=pipeline_run_id,
                surface=surface,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return call_id


def record_call_finish(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    response_time_ms: int | None,
    status: str,
    rows_returned: int | None,
    error_message: str | None,
) -> None:
    """Update the existing call row in place with terminal outcome fields.

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects a caller-held tx. Accepts
    ONLY a TERMINAL status (success/empty/error) -- rejecting 'in_flight' so a
    row never "finishes" into a non-terminal state monitors misread (Codex R16).
    """
    if status not in _FINISH_VALID_STATUSES:
        raise ValueError(
            f"record_call_finish status must be in {sorted(_FINISH_VALID_STATUSES)}, "
            f"got {status!r}"
        )
    with _YF_AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "record_call_finish owns its own transaction; caller MUST NOT "
                "hold an open transaction."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            repo.update_call_outcome(
                conn, call_id=call_id, response_time_ms=response_time_ms,
                status=status, rows_returned=rows_returned,
                error_message=error_message,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _safe_close(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception:  # noqa: BLE001 -- best-effort
        log.warning("yfinance audit: connection close failed", exc_info=True)


def _finish_safe(
    conn: sqlite3.Connection | None,
    call_id: int | None,
    *,
    status: str,
    rows: int | None,
    error: str | None,
    ms: int | None,
) -> None:
    """record_call_finish wrapped so a finish failure (contention/error) logs +
    is SWALLOWED -- it can never break or delay the fetch / the caller."""
    if conn is None or call_id is None:
        return
    try:
        record_call_finish(
            conn, call_id=call_id, response_time_ms=ms, status=status,
            rows_returned=rows, error_message=error,
        )
    except Exception:  # noqa: BLE001 -- best-effort; never sink the fetch
        log.warning("yfinance audit finish failed (best-effort drop)", exc_info=True)


def _rows_of(result) -> int:
    if result is None:
        return 0
    try:
        return int(len(result))
    except TypeError:
        return 0


def _is_empty(result) -> bool:
    if result is None:
        return True
    empty = getattr(result, "empty", None)
    if empty is not None:
        return bool(empty)
    return _rows_of(result) == 0


def _record_yf_download(*, ctx, call_type, ticker, ticker_count, fetch_fn):
    """Bracket a RAW ``yf.download`` (via the zero-arg ``fetch_fn`` closure) with
    a best-effort audit row. Returns the EXACT ``fetch_fn()`` result unchanged.

    The audit can NEVER alter, delay, or replace the fetch:
      - audit START failure / contention -> run ``fetch_fn`` un-audited, no raise;
      - the latency timer wraps ``fetch_fn`` ONLY (Codex R10/R16);
      - a raising fetch closes ``error`` then RE-RAISES (preserves the raise);
      - post-fetch classification is itself wrapped (Codex R8 CRITICAL) so a
        hostile ``.empty`` / ``__len__`` can NEVER replace a successful fetch;
      - the SAME busy_timeout=0 connection is used for start + finish.
    """
    conn = None
    call_id = None
    try:
        t = str(ticker).strip().upper() if ticker is not None else None
        ticker_meta = t or None
        conn = open_connection(
            ctx.db_path, busy_timeout_ms=YFINANCE_AUDIT_BUSY_TIMEOUT_MS,
        )
        call_id = record_call_start(
            conn, ts=_now_iso(), call_type=call_type, ticker=ticker_meta,
            ticker_count=ticker_count, pipeline_run_id=ctx.pipeline_run_id,
            surface=ctx.surface,
        )
    except Exception:  # noqa: BLE001 -- audit start failed/contended
        log.warning("yfinance audit start failed (un-audited fetch)", exc_info=True)
        _safe_close(conn)
        return fetch_fn()
    t0 = monotonic()  # timer AROUND fetch_fn ONLY -> yfinance latency
    try:
        result = fetch_fn()
    except Exception as exc:
        ms = int((monotonic() - t0) * 1000)  # fix the metric BEFORE the finish
        _finish_safe(conn, call_id, status="error", rows=None,
                     error=_sanitize_error(exc), ms=ms)
        _safe_close(conn)
        raise
    ms = int((monotonic() - t0) * 1000)  # response_time_ms fixed BEFORE classify
    try:
        rows = _rows_of(result)
        status = "empty" if _is_empty(result) else "success"
    except Exception:  # noqa: BLE001 -- hostile result; do NOT sink it
        log.warning("yfinance audit classification failed", exc_info=True)
        _finish_safe(conn, call_id, status="success", rows=None, error=None, ms=ms)
        _safe_close(conn)
        return result
    _finish_safe(conn, call_id, status=status, rows=rows, error=None, ms=ms)
    _safe_close(conn)
    return result


__all__ = [
    "CallerHeldTransactionError",
    "record_call_finish",
    "record_call_start",
]
