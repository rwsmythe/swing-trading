"""Phase 9 Sub-bundle C T-C.4 — hypothesis status audit service tests.

Per plan §F T-C.4 + spec §3.4.1 + plan §A.1 + §A.1.1 + dispatch brief
§0.5 #2 + #3 + #4.

Coverage:
  - 8-step transactional sequence: BEGIN IMMEDIATE → read status under lock
    → close prior interval → INSERT new row → UPDATE registry → COMMIT.
  - noop_identity sentinel (NOT exception) when current == new.
  - Rejects caller-held transaction (Phase 8 R4 lesson).
  - Transition rules preserved from legacy repo (closed-target-met is
    terminal; active → closed-target-met allowed; etc.).
  - Reason required; invalid status rejected; unknown hypothesis_id ValueError.
  - Discriminating ImportError test (T-C.4.2): legacy
    swing.data.repos.hypothesis.update_hypothesis_status is GONE.
  - Rollback on synthetic failure (T-C.4.1): history INSERT happens but
    registry UPDATE forced-to-fail → both reverted (no orphan history row).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.hypothesis_status_history import (
    get_current_status,
    list_history_for_hypothesis,
)
from swing.trades.hypothesis import (
    CallerHeldTransactionError,
    HYPOTHESIS_STATUSES,
    HypothesisStatusTransitionError,
    update_hypothesis_status_with_audit,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "hyp_service.db"
    return ensure_schema(db_path)


def _first_hypothesis_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE status = 'active' "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    assert row is not None
    return int(row[0])


# ============================================================================
# §1 — Happy path: active → paused transition
# ============================================================================


def test_active_to_paused_returns_transition_sentinel(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    result = update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="operator paused",
    )
    assert result == "transition"


def test_transition_closes_prior_interval_and_inserts_new(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="operator paused",
    )
    # Prior seed row now has effective_to set.
    rows = list_history_for_hypothesis(conn, hyp_id)
    assert len(rows) == 2
    seed = rows[0]
    new = rows[1]
    assert seed.effective_to is not None
    assert seed.status == "active"  # original seed status
    assert new.effective_to is None
    assert new.status == "paused"
    assert new.change_reason == "operator paused"


def test_transition_updates_hypothesis_registry_denorm(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="operator paused",
    )
    row = conn.execute(
        "SELECT status, status_changed_at, status_change_reason "
        "FROM hypothesis_registry WHERE id = ?", (hyp_id,),
    ).fetchone()
    assert row[0] == "paused"
    assert row[1] is not None
    assert row[2] == "operator paused"


def test_history_recorded_at_equals_effective_from_same_call(
    conn: sqlite3.Connection,
) -> None:
    """Phase 9 spec §3.1 R4 Minor #1 bind-once: same-instant fields agree."""
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="r",
    )
    current = get_current_status(conn, hyp_id)
    assert current is not None
    assert current.effective_from == current.recorded_at


def test_seed_close_timestamp_equals_new_effective_from(
    conn: sqlite3.Connection,
) -> None:
    """The closed seed's effective_to matches the new row's effective_from
    (continuous timeline; same ms-precision instant)."""
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="r",
    )
    rows = list_history_for_hypothesis(conn, hyp_id)
    assert rows[0].effective_to == rows[1].effective_from


# ============================================================================
# §2 — NoOpIdentityTransition sentinel (spec §3.4.1 R3 Minor #1)
# ============================================================================


def test_identity_transition_returns_noop_sentinel(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    # Seeded as active. Identity transition active → active.
    result = update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="active",
        change_reason="redundant",
    )
    assert result == "noop_identity"


def test_identity_transition_does_not_insert_history_row(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    pre_count = len(list_history_for_hypothesis(conn, hyp_id))
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="active",
        change_reason="redundant",
    )
    post_count = len(list_history_for_hypothesis(conn, hyp_id))
    assert pre_count == post_count


def test_identity_transition_does_not_mutate_registry(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    pre = conn.execute(
        "SELECT status_changed_at, status_change_reason "
        "FROM hypothesis_registry WHERE id = ?", (hyp_id,),
    ).fetchone()
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="active",
        change_reason="redundant",
    )
    post = conn.execute(
        "SELECT status_changed_at, status_change_reason "
        "FROM hypothesis_registry WHERE id = ?", (hyp_id,),
    ).fetchone()
    assert pre == post


def test_identity_transition_leaves_no_open_transaction(
    conn: sqlite3.Connection,
) -> None:
    """ROLLBACK on identity path; conn.in_transaction must be False after."""
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="active",
        change_reason="redundant",
    )
    assert conn.in_transaction is False


# ============================================================================
# §3 — Reject caller-held transaction
# ============================================================================


def test_rejects_caller_held_transaction(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    conn.execute("BEGIN IMMEDIATE")
    assert conn.in_transaction is True
    with pytest.raises(CallerHeldTransactionError):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason="r",
        )


# ============================================================================
# §4 — Transition rules (preserved from legacy repo + brief §4.6)
# ============================================================================


def test_active_to_closed_target_met_allowed(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    result = update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="closed-target-met",
        change_reason="hit target",
    )
    assert result == "transition"


def test_closed_target_met_is_terminal(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="closed-target-met",
        change_reason="hit",
    )
    with pytest.raises(HypothesisStatusTransitionError, match="not allowed"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="active",
            change_reason="reopen",
        )


def test_closed_escaped_to_active_allowed(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="closed-escaped",
        change_reason="escape",
    )
    result = update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="active",
        change_reason="reopen",
    )
    assert result == "transition"


def test_paused_to_closed_target_met_rejected(conn: sqlite3.Connection) -> None:
    """Brief §4.6: paused → only active | closed-escaped."""
    hyp_id = _first_hypothesis_id(conn)
    update_hypothesis_status_with_audit(
        conn,
        hypothesis_id=hyp_id,
        new_status="paused",
        change_reason="pause",
    )
    with pytest.raises(HypothesisStatusTransitionError):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="closed-target-met",
            change_reason="hit",
        )


# ============================================================================
# §5 — Input validation
# ============================================================================


def test_rejects_invalid_status(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    with pytest.raises(ValueError, match="invalid status"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="bogus",
            change_reason="r",
        )


def test_rejects_empty_reason(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    with pytest.raises(ValueError, match="change_reason is required"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason="",
        )


def test_rejects_whitespace_only_reason(conn: sqlite3.Connection) -> None:
    hyp_id = _first_hypothesis_id(conn)
    with pytest.raises(ValueError, match="change_reason is required"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason="   ",
        )


def test_rejects_unknown_hypothesis(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="not found"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=99999,
            new_status="paused",
            change_reason="r",
        )


def test_rejects_none_reason(conn: sqlite3.Connection) -> None:
    """``change_reason=None`` is also rejected (operator-supplied required)."""
    hyp_id = _first_hypothesis_id(conn)
    with pytest.raises(ValueError, match="change_reason is required"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason=None,
        )


def test_validation_does_not_leave_open_transaction(
    conn: sqlite3.Connection,
) -> None:
    hyp_id = _first_hypothesis_id(conn)
    with pytest.raises(ValueError):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason="",
        )
    assert conn.in_transaction is False


# ============================================================================
# §6 — Rollback on failure (T-C.4.1 discriminating regression)
# ============================================================================


def test_rollback_on_synthetic_failure_after_history_insert(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject failure between history INSERT and registry UPDATE.

    Both must roll back: NO history row added, NO registry mutation.

    Injection point: monkeypatch the service module's reference to
    ``insert_history`` so it executes the original repo INSERT (writing
    the audit row inside the BEGIN IMMEDIATE) and THEN raises before
    control returns to the service. That places the raise BETWEEN
    step 6 (audit INSERT committed-to-the-transaction) and step 7
    (registry UPDATE). The ROLLBACK in the service's except: handler
    must undo BOTH halves.
    """
    import swing.trades.hypothesis as service_mod
    from swing.data.repos.hypothesis_status_history import (
        insert_history as real_insert_history,
    )

    hyp_id = _first_hypothesis_id(conn)
    seed_count = len(list_history_for_hypothesis(conn, hyp_id))

    def faulty_insert_history(*args, **kwargs):
        # Run the real INSERT first so the row truly lands inside the
        # transaction; THEN raise to simulate a downstream failure.
        real_insert_history(*args, **kwargs)
        raise RuntimeError("synthetic failure between history + registry")

    monkeypatch.setattr(service_mod, "insert_history", faulty_insert_history)

    with pytest.raises(RuntimeError, match="synthetic failure"):
        update_hypothesis_status_with_audit(
            conn,
            hypothesis_id=hyp_id,
            new_status="paused",
            change_reason="r",
        )

    monkeypatch.undo()

    # Both halves rolled back.
    assert conn.in_transaction is False
    post_count = len(list_history_for_hypothesis(conn, hyp_id))
    assert post_count == seed_count, (
        "history INSERT should have been rolled back with the registry"
    )
    reg_status = conn.execute(
        "SELECT status FROM hypothesis_registry WHERE id = ?", (hyp_id,),
    ).fetchone()[0]
    assert reg_status == "active", "registry status unchanged after rollback"
    # The seed open interval is still open (effective_to IS NULL).
    seed = get_current_status(conn, hyp_id)
    assert seed is not None
    assert seed.status == "active"


# ============================================================================
# §7 — ImportError discriminating test (T-C.4.2)
# ============================================================================


def test_legacy_repo_function_is_deleted() -> None:
    """Per plan §A.1.1 + brief §0.5 #2: single-write-path discipline.

    The legacy ``swing.data.repos.hypothesis.update_hypothesis_status``
    function is DELETED in T-C.4. Re-import attempts must fail.
    """
    with pytest.raises(ImportError):
        from swing.data.repos.hypothesis import (  # noqa: F401
            update_hypothesis_status,
        )


# ============================================================================
# §8 — Constants exported correctly
# ============================================================================


def test_hypothesis_statuses_matches_dataclass_enum() -> None:
    assert HYPOTHESIS_STATUSES == (
        "active", "paused", "closed-escaped", "closed-target-met",
    )
