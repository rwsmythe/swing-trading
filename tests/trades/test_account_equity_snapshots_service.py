"""Phase 9 Sub-bundle C T-C.2 — account_equity_snapshots service tests.

Per plan §F T-C.2 acceptance + spec §3.5 + §4.4 + §A.9 + §A.10 + plan §I.

Coverage:
  - record_snapshot defaults snapshot_date to last_completed_session(now())
    per §A.9 (Saturday-night → Friday's date discriminating test).
  - record_snapshot rejects caller-held transaction (Phase 8 R4 lesson).
  - is_back_recorded threshold semantics (default 7 days).
  - Dataclass __post_init__ validators (NaN/inf rejection; enum source;
    snapshot_date format).
  - Server-stamping of recorded_at (operator does NOT supply).
"""
from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import AccountEquitySnapshot
from swing.trades.account_equity_snapshots import (
    BACK_RECORD_THRESHOLD_DAYS,
    CallerHeldTransactionError,
    is_back_recorded,
    record_snapshot,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aes_service.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — Happy path
# ============================================================================


def test_record_snapshot_returns_dataclass_with_pk(conn: sqlite3.Connection) -> None:
    snap = record_snapshot(
        conn,
        equity_dollars=1300.0,
        snapshot_date=date(2026, 5, 12),
        notes="happy path",
    )
    assert isinstance(snap, AccountEquitySnapshot)
    assert snap.snapshot_id is not None
    assert snap.equity_dollars == 1300.0
    assert snap.snapshot_date == "2026-05-12"
    assert snap.source == "manual"
    assert snap.recorded_by == "operator"
    assert snap.notes == "happy path"


def test_record_snapshot_server_stamps_recorded_at(
    conn: sqlite3.Connection,
) -> None:
    """recorded_at must be server-stamped (operator does NOT supply)."""
    snap = record_snapshot(
        conn,
        equity_dollars=1300.0,
        snapshot_date=date(2026, 5, 12),
    )
    # recorded_at must be valid ms-ISO; format YYYY-MM-DDTHH:MM:SS.SSS.
    assert snap.recorded_at[10] == "T"
    assert len(snap.recorded_at) == len("2026-05-12T00:00:00.000")


def test_record_snapshot_persists_to_db(conn: sqlite3.Connection) -> None:
    snap = record_snapshot(
        conn,
        equity_dollars=1300.0,
        snapshot_date=date(2026, 5, 12),
    )
    row = conn.execute(
        "SELECT equity_dollars, source, snapshot_date FROM "
        "account_equity_snapshots WHERE snapshot_id = ?",
        (snap.snapshot_id,),
    ).fetchone()
    assert row == (1300.0, "manual", "2026-05-12")


def test_record_snapshot_upserts_existing_pk(conn: sqlite3.Connection) -> None:
    first = record_snapshot(
        conn,
        equity_dollars=1300.0,
        snapshot_date=date(2026, 5, 12),
    )
    second = record_snapshot(
        conn,
        equity_dollars=1400.0,
        snapshot_date=date(2026, 5, 12),
        notes="re-record",
    )
    assert first.snapshot_id == second.snapshot_id
    # DB reflects the second call's values.
    row = conn.execute(
        "SELECT equity_dollars, notes FROM account_equity_snapshots "
        "WHERE snapshot_id = ?", (first.snapshot_id,),
    ).fetchone()
    assert row == (1400.0, "re-record")


def test_record_snapshot_accepts_string_date(conn: sqlite3.Connection) -> None:
    snap = record_snapshot(
        conn,
        equity_dollars=1300.0,
        snapshot_date="2026-05-12",
    )
    assert snap.snapshot_date == "2026-05-12"


# ============================================================================
# §2 — Defaulting snapshot_date to last_completed_session (§A.9)
# ============================================================================


def test_record_snapshot_defaults_to_last_completed_session(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per §A.9 + spec §4.4 V1 cadence: default to backward-looking session.

    Discriminating Saturday-night test (plan T-C.2 step 16): invoke with
    no --date on a Saturday evening; assert snapshot_date resolved to
    Friday's date. The pre-§A.9 footgun would resolve to today (Saturday)
    or action_session_for_run (Monday).
    """
    import swing.trades.account_equity_snapshots as service_mod

    class FrozenDateTime:
        @staticmethod
        def now(tz=None):
            # Saturday 2026-05-09, 22:00 HST (the operator's locale).
            return datetime(2026, 5, 9, 22, 0, 0)

    monkeypatch.setattr(service_mod, "datetime", FrozenDateTime)
    snap = record_snapshot(conn, equity_dollars=1300.0)
    # Friday's date — last_completed_session for Saturday evening HST.
    assert snap.snapshot_date == "2026-05-08", (
        f"expected Friday's date 2026-05-08; got {snap.snapshot_date!r}"
    )


def test_record_snapshot_default_uses_friday_on_sunday(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sunday-evening Monday-prep workflow: still resolves to Friday."""
    import swing.trades.account_equity_snapshots as service_mod

    class FrozenDateTime:
        @staticmethod
        def now(tz=None):
            # Sunday 2026-05-10, 18:00 HST.
            return datetime(2026, 5, 10, 18, 0, 0)

    monkeypatch.setattr(service_mod, "datetime", FrozenDateTime)
    snap = record_snapshot(conn, equity_dollars=1300.0)
    assert snap.snapshot_date == "2026-05-08"


# ============================================================================
# §3 — Caller-held transaction rejection (Phase 8 R4 lesson)
# ============================================================================


def test_record_snapshot_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    """Plan §I item #6 + dispatch brief §0.5 #6: reject; don't auto-detect."""
    conn.execute("BEGIN IMMEDIATE")
    assert conn.in_transaction is True
    with pytest.raises(CallerHeldTransactionError):
        record_snapshot(
            conn,
            equity_dollars=1300.0,
            snapshot_date=date(2026, 5, 12),
        )


# ============================================================================
# §4 — is_back_recorded threshold semantics
# ============================================================================


def test_is_back_recorded_default_threshold_seven_days() -> None:
    assert BACK_RECORD_THRESHOLD_DAYS == 7


def test_is_back_recorded_false_within_threshold() -> None:
    """7-day gap is NOT back-recorded (strict >, not >=)."""
    assert is_back_recorded(
        snapshot_date="2026-05-01",
        recorded_at="2026-05-08T00:00:00.000",
    ) is False


def test_is_back_recorded_true_past_threshold() -> None:
    """8-day gap IS back-recorded."""
    assert is_back_recorded(
        snapshot_date="2026-05-01",
        recorded_at="2026-05-09T00:00:00.000",
    ) is True


def test_is_back_recorded_false_same_day() -> None:
    assert is_back_recorded(
        snapshot_date="2026-05-12",
        recorded_at="2026-05-12T00:00:00.000",
    ) is False


def test_is_back_recorded_negative_gap_when_future_snapshot() -> None:
    """Snapshot_date after recorded_at: not back-recorded (negative gap)."""
    assert is_back_recorded(
        snapshot_date="2026-05-12",
        recorded_at="2026-05-10T00:00:00.000",
    ) is False


def test_is_back_recorded_custom_threshold() -> None:
    """3-day threshold: 4-day gap is back-recorded."""
    assert is_back_recorded(
        snapshot_date="2026-05-01",
        recorded_at="2026-05-05T00:00:00.000",
        threshold_days=3,
    ) is True


# ============================================================================
# §5 — Dataclass __post_init__ validators (plan §I item #7)
# ============================================================================


def test_dataclass_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="source must be one of"):
        AccountEquitySnapshot(
            snapshot_id=None,
            snapshot_date="2026-05-12",
            equity_dollars=1300.0,
            source="csv_import",
            source_artifact_path=None,
            recorded_at="2026-05-12T00:00:00.000",
            recorded_by="operator",
            notes=None,
        )


def test_dataclass_rejects_nan_equity() -> None:
    with pytest.raises(ValueError, match="equity_dollars must be finite"):
        AccountEquitySnapshot(
            snapshot_id=None,
            snapshot_date="2026-05-12",
            equity_dollars=math.nan,
            source="manual",
            source_artifact_path=None,
            recorded_at="2026-05-12T00:00:00.000",
            recorded_by="operator",
            notes=None,
        )


def test_dataclass_rejects_inf_equity() -> None:
    with pytest.raises(ValueError, match="equity_dollars must be finite"):
        AccountEquitySnapshot(
            snapshot_id=None,
            snapshot_date="2026-05-12",
            equity_dollars=math.inf,
            source="manual",
            source_artifact_path=None,
            recorded_at="2026-05-12T00:00:00.000",
            recorded_by="operator",
            notes=None,
        )


def test_dataclass_rejects_zero_or_negative_equity() -> None:
    for v in (0.0, -1.0):
        with pytest.raises(ValueError, match="equity_dollars must be > 0"):
            AccountEquitySnapshot(
                snapshot_id=None,
                snapshot_date="2026-05-12",
                equity_dollars=v,
                source="manual",
                source_artifact_path=None,
                recorded_at="2026-05-12T00:00:00.000",
                recorded_by="operator",
                notes=None,
            )


def test_dataclass_rejects_empty_recorded_by() -> None:
    for v in ("", "   "):
        with pytest.raises(ValueError, match="recorded_by must be"):
            AccountEquitySnapshot(
                snapshot_id=None,
                snapshot_date="2026-05-12",
                equity_dollars=1300.0,
                source="manual",
                source_artifact_path=None,
                recorded_at="2026-05-12T00:00:00.000",
                recorded_by=v,
                notes=None,
            )


def test_dataclass_rejects_malformed_snapshot_date() -> None:
    for v in ("2026/05/12", "20260512", "May 12 2026"):
        with pytest.raises(ValueError, match="snapshot_date must be"):
            AccountEquitySnapshot(
                snapshot_id=None,
                snapshot_date=v,
                equity_dollars=1300.0,
                source="manual",
                source_artifact_path=None,
                recorded_at="2026-05-12T00:00:00.000",
                recorded_by="operator",
                notes=None,
            )
