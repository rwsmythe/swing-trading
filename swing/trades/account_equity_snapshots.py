"""account_equity_snapshots service layer (Phase 9 Sub-bundle C T-C.2).

Spec §3.5 + §4.4 + plan §A.9 + §A.10 + §0.5 #6 + #8.

Transactional discipline mirrors Sub-bundle A's
``swing/trades/risk_policy.py:supersede_active_policy`` + Sub-bundle B's
``swing/trades/reconciliation.py:run_tos_reconciliation``:

  - REJECT caller-held transactions at entry (raise
    ``CallerHeldTransactionError``); do NOT auto-detect (Phase 8 R3→R4
    lesson + CLAUDE.md gotcha "in_transaction auto-detect re-introduces
    the very race the explicit lock was meant to close").
  - Own ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``.
  - Server-stamp ``recorded_at`` (audit timestamp; operator must not
    supply per plan §A.10).
  - Default ``snapshot_date`` to ``last_completed_session(now())`` per
    plan §A.9 (backward-looking session anchor; mirrors weather lookup
    writer-side discipline).

Back-recorded flag (spec §3.5 + plan §B file map):
  ``is_back_recorded(*, snapshot_date, recorded_at, threshold_days=7)``
  returns True when the gap between recorded_at's date and snapshot_date
  exceeds the threshold. V1 threshold = 7 days (defaults to
  ``BACK_RECORD_THRESHOLD_DAYS``).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from swing.data.datetime_helpers import now_ms
from swing.data.models import AccountEquitySnapshot
from swing.data.repos import account_equity_snapshots as repo
from swing.evaluation.dates import last_completed_session


BACK_RECORD_THRESHOLD_DAYS: int = 7


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes ``record_snapshot`` while holding an
    open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha. Single-transaction services
    own BEGIN IMMEDIATE / COMMIT / ROLLBACK; they REJECT caller-held
    transactions rather than silently auto-detecting.
    """


def is_back_recorded(
    *,
    snapshot_date: str,
    recorded_at: str,
    threshold_days: int = BACK_RECORD_THRESHOLD_DAYS,
) -> bool:
    """Return True if recorded_at's date is more than ``threshold_days``
    after snapshot_date.

    ``snapshot_date`` is YYYY-MM-DD. ``recorded_at`` is the full ms-ISO
    datetime (we compare only the date part).
    """
    sd = date.fromisoformat(snapshot_date)
    rd = date.fromisoformat(recorded_at[:10])
    return (rd - sd).days > threshold_days


def record_snapshot(
    conn: sqlite3.Connection,
    *,
    equity_dollars: float,
    snapshot_date: date | str | None = None,
    source: str = "manual",
    source_artifact_path: str | None = None,
    recorded_by: str = "operator",
    notes: str | None = None,
) -> AccountEquitySnapshot:
    """Record (insert or upsert) an account equity snapshot.

    Defaults:
      - ``snapshot_date``: ``last_completed_session(datetime.now())`` per
        plan §A.9. Backward-looking; mirrors weather-writer discipline.
      - ``source``: ``"manual"`` (V1 CLI cadence per spec §4.4).
      - ``recorded_by``: ``"operator"`` (V1 hardcoded per spec §3.5).

    Server-stamps ``recorded_at`` (now_ms).

    Raises:
      ``CallerHeldTransactionError`` if caller holds an open transaction.
      ``ValueError`` (via dataclass ``__post_init__``) on invalid input.

    Returns the persisted ``AccountEquitySnapshot`` dataclass (with PK
    populated). Re-record for an existing ``(snapshot_date, source)`` UPSERTS
    in place via SELECT-then-UPDATE-or-INSERT (PK preserved).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "record_snapshot owns its own transaction; caller MUST NOT "
            "hold an open transaction. See CLAUDE.md gotcha 'Service-layer "
            "with conn:' + 'in_transaction auto-detect outer transaction "
            "guards re-introduce the very race the explicit lock was meant "
            "to close'."
        )

    # Resolve snapshot_date.
    if snapshot_date is None:
        # last_completed_session signature takes a naive datetime — match
        # the Phase 8 + polish-bundle pattern + R3 of CLAUDE.md gotcha.
        resolved_date = last_completed_session(datetime.now())
    elif isinstance(snapshot_date, date):
        resolved_date = snapshot_date
    else:
        resolved_date = date.fromisoformat(snapshot_date)
    snapshot_date_str = resolved_date.isoformat()

    recorded_at = now_ms()

    # Construct the dataclass FIRST (so __post_init__ validation fires
    # before we touch the DB; surfacing ValueError without leaving a half-
    # acquired write lock).
    candidate = AccountEquitySnapshot(
        snapshot_id=None,
        snapshot_date=snapshot_date_str,
        equity_dollars=float(equity_dollars),
        source=source,
        source_artifact_path=source_artifact_path,
        recorded_at=recorded_at,
        recorded_by=recorded_by,
        notes=notes,
    )

    # Single transaction: BEGIN IMMEDIATE / upsert / COMMIT.
    conn.execute("BEGIN IMMEDIATE")
    try:
        sid = repo.upsert_snapshot(
            conn,
            snapshot_date=candidate.snapshot_date,
            equity_dollars=candidate.equity_dollars,
            source=candidate.source,
            source_artifact_path=candidate.source_artifact_path,
            recorded_at=candidate.recorded_at,
            recorded_by=candidate.recorded_by,
            notes=candidate.notes,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # Return the persisted dataclass with PK populated.
    return AccountEquitySnapshot(
        snapshot_id=sid,
        snapshot_date=candidate.snapshot_date,
        equity_dollars=candidate.equity_dollars,
        source=candidate.source,
        source_artifact_path=candidate.source_artifact_path,
        recorded_at=candidate.recorded_at,
        recorded_by=candidate.recorded_by,
        notes=candidate.notes,
    )


__all__ = [
    "BACK_RECORD_THRESHOLD_DAYS",
    "CallerHeldTransactionError",
    "is_back_recorded",
    "record_snapshot",
]
