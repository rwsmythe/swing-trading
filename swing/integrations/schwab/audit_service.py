"""Schwab API audit service-layer wrappers (Phase 11 Sub-bundle A T-A.9).

Plan §B.1 service signatures. Four functions wrap the repo at
``swing/data/repos/schwab_api_calls.py`` with single-transaction ownership +
caller-held-tx rejection per the project's three-piece transactional
discipline family:

  - caller-controlled at repo layer (Finviz I1 lesson; T-A.8 repo);
  - transaction-owning at service layer (this module);
  - reject-caller-held-tx contract (Phase 8 R3→R4 + CLAUDE.md gotcha
    "in_transaction auto-detect outer transaction guards re-introduce the
    very race the explicit lock was meant to close").

The fourth function, ``link_snapshot_and_stamp_account_hash``, performs
BOTH updates (audit row's ``linked_snapshot_id`` AND snapshot row's
``schwab_account_hash``) inside ONE ``BEGIN IMMEDIATE / COMMIT`` per
plan §H.4.1 + R2 Major #3 fix — reduces blast radius of a process kill
between the two side-effects to zero (either both land or neither does).

Server-stamping discipline (Phase 8 lesson): the ``ts`` for
``record_call_start`` is caller-supplied — the handler entry server-
stamps before any I/O, so the recorded ``ts`` reflects request boundary,
not deferred service-layer entry. Matches the Finviz audit pattern.

Distinct namespace note: ``CallerHeldTransactionError`` is defined locally
here (NOT imported from ``swing.trades.*``) because the integrations
layer must not depend on ``swing.trades``. Phase 9 services define their
own copies for the same reason — module-local classes per single-
transaction service is the project convention.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time

from swing.data.repos import schwab_api_calls as repo

log = logging.getLogger(__name__)

# SQLite lock-contention arc (OQ-C): serialize ALL audit-row transactions within
# a process. With the shared pipeline audit connection this guarantees at most
# ONE BEGIN IMMEDIATE is active at a time (a single sqlite3 connection cannot run
# two concurrent transactions); it also removes audit-vs-audit write-lock
# contention even for distinct connections. Held only for the sub-ms INSERT/UPDATE
# -- NEVER across the HTTP call (start releases it before the HTTP; finish
# re-acquires).
_AUDIT_WRITE_LOCK = threading.Lock()

_SLOW_ACQUIRE_WARN_THRESHOLD_S = 1.0


def _maybe_log_audit_lock_wait(op, waited_s, busy_failed, configured_ms):
    """G2' lock-wait visibility. Called AFTER the lock is released (never inside
    the critical section -- logging I/O would extend the contention window). The
    ``configured_ms`` busy_timeout value is captured by the CALLER while still
    holding the lock and passed in as a plain int -- this function NEVER touches
    the connection (Codex R1 major #1: a PRAGMA read on the shared
    check_same_thread=False conn after lock release would race a concurrent
    writer). Emits a WARNING for failed acquisitions (busy_timeout exhausted) and
    for slow successful ones (>= threshold). Durations + ints only -> redaction-
    irrelevant.
    """
    if not busy_failed and (waited_s is None or waited_s < _SLOW_ACQUIRE_WARN_THRESHOLD_S):
        return
    if busy_failed:
        log.warning(
            "audit %s: BEGIN IMMEDIATE FAILED (database is locked) after %.3fs "
            "(busy_timeout=%sms)", op, waited_s or 0.0, configured_ms,
        )
    else:
        log.warning(
            "audit %s: slow BEGIN IMMEDIATE acquisition %.3fs (busy_timeout=%sms)",
            op, waited_s, configured_ms,
        )

# Phase 13 T2.SB1 (migration 0020) — surface CHECK widening per spec §3.4 +
# §6.4 + plan §A.14 paired-atomic-landing LOCK. Schema CHECK on
# ``schwab_api_calls.surface`` in migration 0020 mirrors these 4 values
# (per CLAUDE.md gotcha "Schema-CHECK + Python-constant + dataclass-
# validator MUST land in the same task for atomic consistency").
#
# Pre-Phase-13 callsites at ``swing/pipeline/runner.py:_step_schwab_*`` +
# ``swing/cli_schwab.py`` + ``swing/web/routes/trades.py`` +
# ``swing/web/routes/schwab.py`` are unaffected (continue passing 'pipeline'
# / 'cli'). Phase 13 T3.SB1 entry auto-fill + T3.SB2 exit auto-fill paths
# emit audit rows with 'trade_entry' / 'trade_exit'.
_SCHWAB_API_SURFACE_VALUES: tuple[str, ...] = (
    "pipeline",
    "cli",
    "trade_entry",
    "trade_exit",
)


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes a Schwab audit service function while
    holding an open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha. Single-transaction services
    own BEGIN IMMEDIATE / COMMIT / ROLLBACK; they REJECT caller-held
    transactions rather than silently auto-detecting.
    """


def record_call_start(
    conn: sqlite3.Connection,
    *,
    ts: str,
    endpoint: str,
    pipeline_run_id: int | None,
    surface: str,
    environment: str,
) -> int:
    """Insert an in-flight schwab_api_calls audit row. Returns the call_id.

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects caller-held tx.

    ``ts`` is caller-supplied (server-stamped at handler entry per Phase 8
    server-stamping discipline — the recorded timestamp reflects the
    request boundary, not deferred service entry).

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
    """
    # Phase 13 T2.SB1 (migration 0020) — Python-side surface enum validation
    # mirroring schema CHECK widening per plan §A.14 paired-atomic-landing
    # LOCK. Mirrors the migration 0020 CHECK on ``schwab_api_calls.surface``.
    # Pure input validation -> stays OUTSIDE the audit write lock.
    if surface not in _SCHWAB_API_SURFACE_VALUES:
        raise ValueError(
            "surface must be one of "
            f"{_SCHWAB_API_SURFACE_VALUES}, got {surface!r}"
        )

    waited_s = None
    busy_failed = False
    configured_ms = None
    try:
        with _AUDIT_WRITE_LOCK:
            # configured_ms is read INSIDE the lock (conn idle, owned by this
            # thread) so the after-lock logger never touches the connection.
            try:
                configured_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            except Exception:  # noqa: BLE001 -- diagnostic only
                configured_ms = None
            # in_transaction is checked INSIDE the lock: a shared audit connection
            # is transiently in-tx while another serialized writer holds it;
            # checking outside would false-positive. Inside the lock the prior
            # holder has committed/rolled back, so a genuine caller-held tx is
            # still rejected.
            if conn.in_transaction:
                raise CallerHeldTransactionError(
                    "record_call_start owns its own transaction; caller MUST NOT "
                    "hold an open transaction. See CLAUDE.md gotcha 'Service-layer "
                    "with conn:' + 'in_transaction auto-detect outer transaction "
                    "guards re-introduce the very race the explicit lock was meant "
                    "to close'."
                )
            _t0 = time.monotonic()
            begun = False
            try:
                conn.execute("BEGIN IMMEDIATE")
                begun = True
                waited_s = time.monotonic() - _t0
                call_id = repo.insert_in_flight(
                    conn,
                    ts=ts,
                    endpoint=endpoint,
                    pipeline_run_id=pipeline_run_id,
                    surface=surface,
                    environment=environment,
                )
                conn.commit()
            except sqlite3.OperationalError:
                # busy_failed is the BEGIN IMMEDIATE lock-acquisition failure
                # ONLY (Codex R1 minor): a later OperationalError (insert/commit)
                # would mislabel the lock-wait telemetry, so only record it when
                # the transaction never began.
                if not begun:
                    waited_s = time.monotonic() - _t0
                    busy_failed = True
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                raise
    finally:
        _maybe_log_audit_lock_wait(
            "record_call_start", waited_s, busy_failed, configured_ms
        )
    return call_id


def record_call_finish(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    http_status: int | None,
    response_time_ms: int | None,
    rate_limit_remaining: int | None,
    signature_hash: str | None,
    status: str,
    error_message: str | None,
) -> None:
    """Update the existing call row in place with terminal outcome fields.

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects caller-held tx.

    Delegates to ``repo.update_call_outcome`` which uses plain ``UPDATE``
    (NEVER ``INSERT OR REPLACE`` per CLAUDE.md gotcha; PK preserved).

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
    """
    waited_s = None
    busy_failed = False
    configured_ms = None
    try:
        with _AUDIT_WRITE_LOCK:
            try:
                configured_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            except Exception:  # noqa: BLE001 -- diagnostic only
                configured_ms = None
            if conn.in_transaction:
                raise CallerHeldTransactionError(
                    "record_call_finish owns its own transaction; caller MUST NOT "
                    "hold an open transaction. See CLAUDE.md gotcha 'Service-layer "
                    "with conn:' + 'in_transaction auto-detect outer transaction "
                    "guards re-introduce the very race the explicit lock was meant "
                    "to close'."
                )
            _t0 = time.monotonic()
            begun = False
            try:
                conn.execute("BEGIN IMMEDIATE")
                begun = True
                waited_s = time.monotonic() - _t0
                repo.update_call_outcome(
                    conn,
                    call_id=call_id,
                    http_status=http_status,
                    response_time_ms=response_time_ms,
                    rate_limit_remaining=rate_limit_remaining,
                    signature_hash=signature_hash,
                    status=status,
                    error_message=error_message,
                )
                conn.commit()
            except sqlite3.OperationalError:
                # busy_failed is the BEGIN IMMEDIATE lock-acquisition failure
                # ONLY (Codex R1 minor): a later OperationalError (update/commit)
                # would mislabel the lock-wait telemetry, so only record it when
                # the transaction never began.
                if not begun:
                    waited_s = time.monotonic() - _t0
                    busy_failed = True
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                raise
    finally:
        _maybe_log_audit_lock_wait(
            "record_call_finish", waited_s, busy_failed, configured_ms
        )


def link_snapshot_and_stamp_account_hash(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    snapshot_id: int,
    account_hash: str,
) -> None:
    """Atomically (1) set ``linked_snapshot_id`` on the schwab_api_calls
    audit row AND (2) stamp ``schwab_account_hash`` on the
    account_equity_snapshots row — ONE ``BEGIN IMMEDIATE / COMMIT``
    covers both UPDATEs (plan §H.4.1 + R2 Major #3 fix).

    The combined-tx design reduces the blast radius of a process kill to
    zero: either both side-effects land or neither does. The crash-window
    invariant is "never see `linked_snapshot_id` set with
    `schwab_account_hash` unset, or vice-versa".

    The first UPDATE is delegated to ``repo.update_call_linked_snapshot``
    (single-row UPDATE; preserves all other audit columns). The second
    UPDATE on ``account_equity_snapshots`` is raw SQL inside the service
    by deliberate boundary choice (the integrations layer should not
    cross-depend on ``swing.data.repos.account_equity_snapshots``).

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects caller-held tx.

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
    """
    with _AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "link_snapshot_and_stamp_account_hash owns its own transaction; "
                "caller MUST NOT hold an open transaction. See CLAUDE.md gotcha "
                "'Service-layer with conn:' + 'in_transaction auto-detect outer "
                "transaction guards re-introduce the very race the explicit "
                "lock was meant to close'."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            repo.update_call_linked_snapshot(
                conn,
                call_id=call_id,
                snapshot_id=snapshot_id,
            )
            _stamp_account_hash_on_snapshot(
                conn, snapshot_id=snapshot_id, account_hash=account_hash,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _stamp_account_hash_on_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_id: int,
    account_hash: str,
) -> None:
    """Inline raw-SQL helper for the second leg of
    ``link_snapshot_and_stamp_account_hash``.

    Extracted as a module-level function (NOT inlined) so tests can patch
    it via ``monkeypatch.setattr`` to simulate a mid-tx2 process kill on
    the second UPDATE. The Schwab integration layer must NOT cross-depend
    on ``swing.data.repos.account_equity_snapshots`` (Phase 9 owns that
    repo); raw SQL is the deliberate boundary.
    """
    conn.execute(
        "UPDATE account_equity_snapshots SET schwab_account_hash = ? "
        "WHERE snapshot_id = ?",
        (account_hash, snapshot_id),
    )


def link_reconciliation_run(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    reconciliation_run_id: int,
) -> None:
    """Set ``linked_reconciliation_run_id`` on the audit row.

    Owns BEGIN IMMEDIATE / COMMIT / ROLLBACK. Rejects caller-held tx.

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
    """
    with _AUDIT_WRITE_LOCK:
        if conn.in_transaction:
            raise CallerHeldTransactionError(
                "link_reconciliation_run owns its own transaction; caller MUST "
                "NOT hold an open transaction. See CLAUDE.md gotcha 'Service-"
                "layer with conn:' + 'in_transaction auto-detect outer "
                "transaction guards re-introduce the very race the explicit "
                "lock was meant to close'."
            )
        conn.execute("BEGIN IMMEDIATE")
        try:
            repo.update_call_linked_reconciliation_run(
                conn,
                call_id=call_id,
                reconciliation_run_id=reconciliation_run_id,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


__all__ = [
    "CallerHeldTransactionError",
    "link_reconciliation_run",
    "link_snapshot_and_stamp_account_hash",
    "record_call_finish",
    "record_call_start",
]
