"""T-C.4 — `_apply_tier3_override_inner` body tests.

Per plan §D.4 — spec §5.7 10-step flow + Codex R1 Minor #1 reorder
(validator chain re-run BEFORE any mutation). Pins:
  - AlreadySupersededError raised when target row's
    superseded_by_correction_id IS NOT NULL.
  - Happy path: new correction row written; prior row's
    superseded_by_correction_id chain pointer updated; journal column
    UPDATEd to operator-truth value; discrepancy resolution flipped to
    operator_overridden; trade_events row emitted.
  - Validator rejection raises ValidatorRejectedError BEFORE any
    mutation (defense-in-depth; operator-truth might violate invariants).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import (
    AlreadySupersededError,
    CorrectionResult,
    ValidatorRejectedError,
    apply_tier1_correction,
    apply_tier3_override,
)
from swing.trades.reconciliation_classifier import ClassificationResult


def _seed_cvgi_world(conn: sqlite3.Connection) -> dict[str, Any]:
    """Plant CVGI fixture + run apply_tier1_correction so we have a
    correction row to override."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("CVGI", "2026-04-27", 5.23, 100, 4.0, 4.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO fills (
            fill_id, trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (9, ?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.23, "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES (?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running"),
    )
    run_id = int(run_cur.lastrowid)
    conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
            ticker, field_name, expected_value_json, actual_value_json,
            delta_text, material_to_review, resolution, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            41, run_id, "entry_price_mismatch", trade_id, 9,
            "CVGI", "price", '{"price": 5.23}', '{"price": 5.30}',
            "+$0.07", 1, "unresolved", "2026-05-15T12:00:00",
        ),
    )
    conn.commit()
    # Apply tier-1 to get a correction row.
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="initial tier-1 apply",
        candidate_choices=None,
    )
    tier1 = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="production",
    )
    return {
        "trade_id": trade_id,
        "fill_id": 9,
        "run_id": run_id,
        "discrepancy_id": 41,
        "tier1_correction_id": tier1.correction_id,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


@pytest.fixture
def cvgi_world(conn: sqlite3.Connection) -> dict[str, Any]:
    return _seed_cvgi_world(conn)


# ---------------------------------------------------------------------------
# Happy path — chain a tier-3 override onto a tier-1 correction
# ---------------------------------------------------------------------------


def test_apply_tier3_override_chains_correctly(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    tier1_id = cvgi_world["tier1_correction_id"]
    result = apply_tier3_override(
        conn,
        correction_id=tier1_id,
        operator_truth_value={"price": 5.25},
        operator_reason="Verified broker statement; actual was $5.25",
    )
    # New correction row created with operator_overridden action:
    new = conn.execute(
        "SELECT correction_action, applied_by, "
        "pre_correction_value_json, applied_value_json, "
        "operator_truth_value_json "
        "FROM reconciliation_corrections WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert new[0] == "operator_overridden"
    assert new[1] == "operator"
    assert json.loads(new[2]) == {"price": 5.30}
    assert json.loads(new[3]) == {"price": 5.25}
    assert json.loads(new[4]) == {"price": 5.25}
    # Prior row's superseded_by_correction_id points to new row:
    prior = conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (tier1_id,),
    ).fetchone()
    assert prior[0] == result.correction_id
    # Journal column UPDATEd to operator-truth:
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 9"
    ).fetchone()
    assert fp[0] == 5.25
    # Discrepancy resolution:
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (cvgi_world["discrepancy_id"],),
    ).fetchone()
    assert d[0] == "operator_overridden"
    # trade_events row emitted:
    te = conn.execute(
        "SELECT event_type FROM trade_events "
        "WHERE trade_id = ? ORDER BY id DESC LIMIT 1",
        (cvgi_world["trade_id"],),
    ).fetchone()
    assert te[0] == "reconciliation_auto_correct"


# ---------------------------------------------------------------------------
# AlreadySupersededError
# ---------------------------------------------------------------------------


def test_apply_tier3_override_rejects_already_superseded(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    tier1_id = cvgi_world["tier1_correction_id"]
    # First override succeeds.
    apply_tier3_override(
        conn,
        correction_id=tier1_id,
        operator_truth_value={"price": 5.25},
        operator_reason="first override",
    )
    # Second override against the SAME (now-superseded) correction_id raises.
    with pytest.raises(AlreadySupersededError):
        apply_tier3_override(
            conn,
            correction_id=tier1_id,
            operator_truth_value={"price": 5.20},
            operator_reason="second override against stale row",
        )


# ---------------------------------------------------------------------------
# Validator rejection BEFORE any mutation
# ---------------------------------------------------------------------------


def test_apply_tier3_override_validator_rejection_before_mutation(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    tier1_id = cvgi_world["tier1_correction_id"]
    pre_fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 9"
    ).fetchone()[0]
    pre_n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections"
    ).fetchone()[0]
    with pytest.raises(ValidatorRejectedError):
        apply_tier3_override(
            conn,
            correction_id=tier1_id,
            operator_truth_value={"price": -1.0},  # invalid
            operator_reason="negative price probe",
        )
    # No mutation: fills.price unchanged + no new correction row + prior
    # row's superseded_by_correction_id still NULL.
    post_fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 9"
    ).fetchone()[0]
    assert post_fp == pre_fp
    post_n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections"
    ).fetchone()[0]
    assert post_n == pre_n
    prior = conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (tier1_id,),
    ).fetchone()
    assert prior[0] is None


# ---------------------------------------------------------------------------
# Unknown correction_id raises
# ---------------------------------------------------------------------------


def test_apply_tier3_override_raises_on_unknown_correction_id(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="correction_id"):
        apply_tier3_override(
            conn,
            correction_id=999_999,
            operator_truth_value={"price": 5.25},
            operator_reason="x",
        )


# ---------------------------------------------------------------------------
# Risk-policy stamp on the new tier-3 correction row
# ---------------------------------------------------------------------------


def test_apply_tier3_override_stamps_risk_policy(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    tier1_id = cvgi_world["tier1_correction_id"]
    result = apply_tier3_override(
        conn,
        correction_id=tier1_id,
        operator_truth_value={"price": 5.25},
        operator_reason="x",
    )
    rp = conn.execute(
        "SELECT risk_policy_id_at_correction FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rp[0] is not None
