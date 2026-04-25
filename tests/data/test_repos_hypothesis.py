"""Tests for swing.data.repos.hypothesis."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import HypothesisRegistryEntry
from swing.data.repos.hypothesis import (
    HypothesisStatusTransitionError,
    get_hypothesis,
    list_hypotheses,
    update_hypothesis_status,
)


def _conn(tmp_db: Path):
    return ensure_schema(tmp_db)


def test_list_hypotheses_returns_all_seeded(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        rows = list_hypotheses(conn)
        assert len(rows) == 4
        assert all(isinstance(r, HypothesisRegistryEntry) for r in rows)
        assert {r.name for r in rows} == {
            "A+ baseline",
            "Near-A+ defensible: extension test",
            "Sub-A+ VCP-not-formed",
            "Capital-blocked: smaller-position test",
        }
        # All seeded as active and ordered by id
        ids = [r.id for r in rows]
        assert ids == sorted(ids)
    finally:
        conn.close()


def test_list_hypotheses_filter_by_status(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        active = list_hypotheses(conn, status_filter="active")
        assert len(active) == 4
        paused = list_hypotheses(conn, status_filter="paused")
        assert paused == []
    finally:
        conn.close()


def test_get_hypothesis_by_id(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        rows = list_hypotheses(conn)
        first = rows[0]
        fetched = get_hypothesis(conn, first.id)
        assert fetched == first
        # Missing id
        assert get_hypothesis(conn, 999) is None
    finally:
        conn.close()


def test_update_hypothesis_status_records_reason_and_timestamp(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        rows = list_hypotheses(conn)
        h = rows[2]  # Sub-A+ VCP-not-formed
        assert h.status == "active"
        update_hypothesis_status(
            conn, h.id, new_status="paused",
            reason="Operator pausing pending review",
            now_iso="2026-04-25T12:00:00",
        )
        updated = get_hypothesis(conn, h.id)
        assert updated.status == "paused"
        assert updated.status_change_reason == "Operator pausing pending review"
        assert updated.status_changed_at == "2026-04-25T12:00:00"
    finally:
        conn.close()


def test_update_hypothesis_status_requires_reason(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        with pytest.raises(ValueError, match="reason"):
            update_hypothesis_status(
                conn, h.id, new_status="paused", reason="",
                now_iso="2026-04-25T12:00:00",
            )
    finally:
        conn.close()


def test_update_hypothesis_status_rejects_invalid_status(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        with pytest.raises(ValueError, match="status"):
            update_hypothesis_status(
                conn, h.id, new_status="exploded", reason="x",
                now_iso="2026-04-25T12:00:00",
            )
    finally:
        conn.close()


def test_update_hypothesis_status_rejects_invalid_transition(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        # active → closed-target-met is allowed; from there, no transitions are.
        update_hypothesis_status(
            conn, h.id, new_status="closed-target-met",
            reason="hit 20", now_iso="2026-04-25T12:00:00",
        )
        with pytest.raises(HypothesisStatusTransitionError):
            update_hypothesis_status(
                conn, h.id, new_status="active",
                reason="reopen", now_iso="2026-04-25T13:00:00",
            )
    finally:
        conn.close()


def test_update_hypothesis_status_no_op_same_status_is_rejected(tmp_db: Path):
    """Updating to the current status is a no-op semantic error — caller
    misunderstood state. Reject so audit log doesn't fill with redundant
    rows."""
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        with pytest.raises(HypothesisStatusTransitionError):
            update_hypothesis_status(
                conn, h.id, new_status="active",
                reason="redundant", now_iso="2026-04-25T12:00:00",
            )
    finally:
        conn.close()


def test_update_hypothesis_status_unknown_id(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        with pytest.raises(ValueError, match="not found"):
            update_hypothesis_status(
                conn, 999, new_status="paused", reason="x",
                now_iso="2026-04-25T12:00:00",
            )
    finally:
        conn.close()


def test_update_hypothesis_status_does_not_mutate_frozen_fields(tmp_db: Path):
    """Anti-rationalization watch item from brief §5: only `status`,
    `status_changed_at`, and `status_change_reason` may be modified. The
    repo function exposes no API to change `target_sample_size`,
    `consecutive_loss_tripwire`, etc."""
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        update_hypothesis_status(
            conn, h.id, new_status="paused", reason="check",
            now_iso="2026-04-25T12:00:00",
        )
        after = get_hypothesis(conn, h.id)
        assert after.target_sample_size == h.target_sample_size
        assert after.consecutive_loss_tripwire == h.consecutive_loss_tripwire
        assert after.absolute_loss_tripwire_pct == h.absolute_loss_tripwire_pct
        assert after.decision_criteria == h.decision_criteria
        assert after.statement == h.statement
        assert after.name == h.name
        assert after.created_at == h.created_at
    finally:
        conn.close()


def test_status_transitions_table_per_brief(tmp_db: Path):
    """Per brief §4.6 the allowed transitions are:
    active   → paused | closed-escaped | closed-target-met
    paused   → active | closed-escaped
    closed-escaped → active
    closed-target-met → (none — terminal)
    """
    conn = _conn(tmp_db)
    try:
        h = list_hypotheses(conn)[0]
        # active → paused
        update_hypothesis_status(conn, h.id, new_status="paused",
                                 reason="r1", now_iso="2026-04-25T12:00:00")
        # paused → active
        update_hypothesis_status(conn, h.id, new_status="active",
                                 reason="r2", now_iso="2026-04-25T12:00:01")
        # active → closed-escaped
        update_hypothesis_status(conn, h.id, new_status="closed-escaped",
                                 reason="r3", now_iso="2026-04-25T12:00:02")
        # closed-escaped → active
        update_hypothesis_status(conn, h.id, new_status="active",
                                 reason="r4", now_iso="2026-04-25T12:00:03")
        # active → closed-target-met (terminal)
        update_hypothesis_status(conn, h.id, new_status="closed-target-met",
                                 reason="r5", now_iso="2026-04-25T12:00:04")
        with pytest.raises(HypothesisStatusTransitionError):
            update_hypothesis_status(conn, h.id, new_status="active",
                                     reason="reopen",
                                     now_iso="2026-04-25T12:00:05")
    finally:
        conn.close()
