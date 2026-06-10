"""Tests for swing.data.repos.hypothesis (registry reads only).

Phase 9 Sub-bundle C T-C.4 (per plan §A.1 + §A.1.1) DELETED the
``update_hypothesis_status`` repo function — status updates now route
through ``swing/trades/hypothesis.py:update_hypothesis_status_with_audit``
which also appends the hypothesis_status_history audit row. The
transition rules, status enum validation, reason-required, frozen-fields
protection, and ImportError discriminating test live in
``tests/trades/test_hypothesis_service.py`` (T-C.4 coverage).

This module retains the legacy registry-READ tests
(``list_hypotheses``, ``get_hypothesis``) since they cover the repo
surface that Sub-bundle C does NOT touch.
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import ensure_schema
from swing.data.models import HypothesisRegistryEntry
from swing.data.repos.hypothesis import (
    get_hypothesis,
    list_hypotheses,
)


def _conn(tmp_db: Path):
    return ensure_schema(tmp_db)


def test_list_hypotheses_returns_all_seeded(tmp_db: Path):
    conn = _conn(tmp_db)
    try:
        rows = list_hypotheses(conn)
        assert len(rows) == 5
        assert all(isinstance(r, HypothesisRegistryEntry) for r in rows)
        assert {r.name for r in rows} == {
            "A+ baseline",
            "Near-A+ defensible: extension test",
            "Sub-A+ VCP-not-formed",
            "Capital-blocked: smaller-position test",
            "Broad-watch baseline",
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
        assert len(active) == 5
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
