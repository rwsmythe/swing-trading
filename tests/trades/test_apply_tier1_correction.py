"""T-C.2 — `_apply_tier1_correction_inner` body tests.

Per plan §D.2 — spec §5.4 11-step atomic flow. Pins:
  - CVGI 41 happy path end-to-end (fills price update + aggregates +
    discrepancy resolution + correction row + trade_events emission).
  - Validator chain re-invocation; rejection raises ValidatorRejectedError.
  - Idempotency: terminal resolution returns existing correction_id
    without writing a new audit row.
  - Sandbox short-circuit at outer (see also
    test_reconciliation_auto_correct_transactional_discipline.py).
  - Review_log supersede-pointer wired via cadence-period anchoring
    when applicable.
  - Schwab API call back-link via update_call_linked_correction.
  - Lifecycle invariants enforced at INSERT time.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.trades.reconciliation_auto_correct import (
    CorrectionResult,
    ValidatorRejectedError,
    _apply_tier1_correction_inner,
    apply_tier1_correction,
)
from swing.trades.reconciliation_classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Fixtures — plant CVGI 41 shape: 1 trade, 1 entry fill at price=5.23,
# 1 reconciliation_run, 1 discrepancy of entry_price_mismatch type at
# discrepancy_id=41 referencing fill_id=9.
# ---------------------------------------------------------------------------


def _seed_cvgi_world(
    conn: sqlite3.Connection,
    *,
    fill_price: float = 5.23,
    review_log_period: tuple[str, str] | None = None,
    trade_state: str = "managing",
    closed_date: str | None = None,
) -> dict[str, Any]:
    """Plant CVGI 41 fixture. Returns dict with key ids."""
    # 1. trade
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CVGI", "2026-04-27", fill_price, 100, 4.0,
            4.0, trade_state, "manual_off_pipeline", "2026-04-27T16:00:00",
        ),
    )
    trade_id = int(cur.lastrowid)

    # 2. entry fill — explicitly use fill_id=9 to match plan walkthrough
    conn.execute(
        """
        INSERT INTO fills (
            fill_id, trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (9, ?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, fill_price, "unreconciled"),
    )

    # 2b. optional exit fill to close the trade
    if closed_date is not None:
        conn.execute(
            """
            INSERT INTO fills (
                trade_id, fill_datetime, action, quantity, price,
                reconciliation_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (trade_id, f"{closed_date}T16:00:00", "exit", 100.0, 6.0, "unreconciled"),
        )

    # 3. recompute trades aggregates
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)

    # 4. reconciliation_run
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running", "2026-04-27", "2026-04-27"),
    )
    run_id = int(run_cur.lastrowid)

    # 5. discrepancy at id=41
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
            "CVGI", "price", json.dumps({"price": fill_price}),
            json.dumps({"price": 5.30}), "+$0.07", 1, "unresolved",
            "2026-05-15T12:00:00",
        ),
    )

    # 6. risk_policy seeded by migrations; verify there's an active one
    active = conn.execute(
        "SELECT policy_id FROM risk_policy WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    assert active is not None
    active_policy_id = int(active[0])

    # 7. optional review_log row
    review_id = None
    if review_log_period is not None:
        ps, pe = review_log_period
        rcur = conn.execute(
            """
            INSERT INTO review_log (
                review_type, period_start, period_end, scheduled_date,
                completed_date, duration_minutes, n_trades_reviewed,
                primary_lesson, next_period_focus
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("weekly", ps, pe, pe, pe, 30, 1, "lesson", "focus"),
        )
        review_id = int(rcur.lastrowid)

    # Commit the seeded state so the service-layer outer fn's
    # ``conn.in_transaction`` precondition passes (Python sqlite3 opens
    # an implicit tx on the first DML statement).
    conn.commit()

    return {
        "trade_id": trade_id,
        "fill_id": 9,
        "run_id": run_id,
        "discrepancy_id": 41,
        "active_policy_id": active_policy_id,
        "review_id": review_id,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


@pytest.fixture
def cvgi_world(conn: sqlite3.Connection) -> dict[str, Any]:
    return _seed_cvgi_world(conn)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_cvgi_41_happy_path(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason=(
            "entry_price_mismatch on (CVGI, fill_id=9): "
            "journal $5.23 vs Schwab $5.30"
        ),
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn,
        discrepancy_id=41,
        classification=classification,
        risk_policy_id=cvgi_world["active_policy_id"],
        environment="production",
    )
    # 1. fills.price updated.
    fill_price = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 9"
    ).fetchone()
    assert fill_price[0] == 5.30
    # 2. trades.current_avg_cost recomputed.
    avg = conn.execute(
        "SELECT current_avg_cost FROM trades WHERE id = ?",
        (cvgi_world["trade_id"],),
    ).fetchone()
    assert avg[0] == 5.30
    # 3. reconciliation_corrections row written.
    rc = conn.execute(
        "SELECT correction_action, applied_value_json, applied_by, "
        "affected_table, affected_row_id, field_name, "
        "pre_correction_value_json, source_canonical_value_json "
        "FROM reconciliation_corrections WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rc[0] == "auto_applied"
    assert json.loads(rc[1]) == {"price": 5.30}
    assert rc[2] == "auto"
    assert rc[3] == "fills"
    assert rc[4] == 9
    assert rc[5] == "price"
    assert json.loads(rc[6]) == {"price": 5.23}
    assert json.loads(rc[7]) == {"price": 5.30}
    # 4. Discrepancy resolution updated.
    d = conn.execute(
        "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "auto_corrected_from_schwab"
    assert d[1] == "auto"
    # 5. trade_events row emitted.
    te = conn.execute(
        "SELECT event_type, payload_json FROM trade_events "
        "WHERE trade_id = ? ORDER BY id DESC LIMIT 1",
        (cvgi_world["trade_id"],),
    ).fetchone()
    assert te[0] == "reconciliation_auto_correct"
    payload = json.loads(te[1])
    assert payload["correction_id"] == result.correction_id
    assert payload["affected_table"] == "fills"
    assert payload["affected_row_id"] == 9
    assert payload["field_name"] == "price"
    # 6. fills.reconciliation_status flipped.
    rs = conn.execute(
        "SELECT reconciliation_status FROM fills WHERE fill_id = 9"
    ).fetchone()
    assert rs[0] == "reconciled_discrepancy_resolved"
    # 7. CorrectionResult shape.
    assert isinstance(result, CorrectionResult)
    assert result.correction_action == "auto_applied"
    assert result.affected_table == "fills"
    assert result.affected_row_id == 9
    assert result.field_name == "price"
    assert json.loads(result.applied_value_json) == {"price": 5.30}


# ---------------------------------------------------------------------------
# Validator rejection
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_raises_validator_rejected_on_negative_price(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": -1.0},  # validate_fill_correction rejects
        correction_reason="negative-price probe",
        candidate_choices=None,
    )
    with pytest.raises(ValidatorRejectedError) as excinfo:
        apply_tier1_correction(
            conn,
            discrepancy_id=41,
            classification=classification,
            environment="production",
        )
    assert "price" in str(excinfo.value).lower()
    # Discrepancy stays unresolved + no correction row written.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "unresolved"
    rc_count = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections WHERE discrepancy_id = 41"
    ).fetchone()[0]
    assert rc_count == 0
    # fills.price unchanged.
    fp = conn.execute(
        "SELECT price FROM fills WHERE fill_id = 9"
    ).fetchone()
    assert fp[0] == 5.23


# ---------------------------------------------------------------------------
# Sandbox short-circuit (happens at outer; covered minimally here +
# extensively in test_reconciliation_auto_correct_transactional_discipline)
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_sandbox_short_circuit_writes_nothing(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="...",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="sandbox",
    )
    assert result.correction_id is None
    assert "sandbox" in (result.notes or "").lower()
    # No domain writes.
    fp = conn.execute("SELECT price FROM fills WHERE fill_id = 9").fetchone()
    assert fp[0] == 5.23
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "unresolved"
    rc_count = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections"
    ).fetchone()[0]
    assert rc_count == 0


def test_apply_tier1_correction_inner_sandbox_short_circuit_writes_nothing(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    """SC-1: plan §D.5 step 3 LOCK requires `_apply_tier1_correction_inner`
    to accept ``environment`` kwarg and short-circuit on ``'sandbox'``
    without journal mutation or correction INSERT. This pins the inner-fn
    contract (not the outer wrapper) so the pivot dispatcher at
    `_pivot_classify_and_dispatch_for_run` can always iterate + classify +
    call the inner with ``environment='sandbox'`` and get a no-op result
    that increments classifier counters but leaves tier1_applied_count=0.
    """
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="...",
        candidate_choices=None,
    )
    # Caller owns transaction per inner-fn contract.
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_tier1_correction_inner(
            conn,
            discrepancy_id=41,
            classification=classification,
            environment="sandbox",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # Returns no-op result.
    assert result.correction_id is None
    assert "sandbox" in (result.notes or "").lower()
    # No journal mutation.
    fp = conn.execute("SELECT price FROM fills WHERE fill_id = 9").fetchone()
    assert fp[0] == 5.23
    # No discrepancy resolution change.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "unresolved"
    # No correction audit row.
    rc_count = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections"
    ).fetchone()[0]
    assert rc_count == 0


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_is_idempotent_on_terminal_state(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="...",
        candidate_choices=None,
    )
    first = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        risk_policy_id=cvgi_world["active_policy_id"],
        environment="production",
    )
    assert first.correction_id is not None
    second = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        risk_policy_id=cvgi_world["active_policy_id"],
        environment="production",
    )
    # Same correction_id returned; no second row.
    assert second.correction_id == first.correction_id
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections WHERE discrepancy_id = 41"
    ).fetchone()[0]
    assert n == 1


# ---------------------------------------------------------------------------
# Review_log supersede pointer (cadence-period anchored on close date)
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_supersedes_review_log_when_trade_closed_in_period(
    conn: sqlite3.Connection,
) -> None:
    """Closed trade + review_log row covering the close date → review_log
    row gets superseded_by_correction_id set."""
    world = _seed_cvgi_world(
        conn,
        review_log_period=("2026-04-27", "2026-04-30"),
        trade_state="closed",
        closed_date="2026-04-28",
    )
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="closed-trade review supersede probe",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="production",
    )
    rl_row = conn.execute(
        "SELECT superseded_by_correction_id FROM review_log "
        "WHERE review_id = ?",
        (world["review_id"],),
    ).fetchone()
    assert rl_row[0] == result.correction_id


def test_apply_tier1_correction_does_not_supersede_review_log_for_open_trade(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    """Open trade (CVGI 41 default) → no review_log row to supersede."""
    # Plant a review_log row that covers the discrepancy creation date but
    # whose trade is still open → should NOT be superseded.
    rcur = conn.execute(
        """
        INSERT INTO review_log (
            review_type, period_start, period_end, scheduled_date,
            completed_date, duration_minutes, n_trades_reviewed,
            primary_lesson, next_period_focus
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "weekly", "2026-04-27", "2026-04-30", "2026-04-30",
            "2026-04-30", 30, 0, "lesson", "focus",
        ),
    )
    review_id = int(rcur.lastrowid)
    conn.commit()
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="open-trade probe",
        candidate_choices=None,
    )
    apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="production",
    )
    rl_row = conn.execute(
        "SELECT superseded_by_correction_id FROM review_log "
        "WHERE review_id = ?",
        (review_id,),
    ).fetchone()
    assert rl_row[0] is None


# ---------------------------------------------------------------------------
# Schwab API call back-link
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_back_links_schwab_api_call(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    """When `schwab_api_call_id` is supplied, the audit row carries it +
    schwab_api_calls.linked_correction_id is back-linked."""
    # Plant a schwab_api_calls row to back-link to.
    call_cur = conn.execute(
        """
        INSERT INTO schwab_api_calls (
            endpoint, ts, status, surface, environment
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            "accounts.orders.list", "2026-05-15T12:00:00", "success",
            "pipeline", "production",
        ),
    )
    call_id = int(call_cur.lastrowid)
    conn.commit()
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="back-link probe",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        schwab_api_call_id=call_id,
        environment="production",
    )
    # Forward: reconciliation_corrections.schwab_api_call_id = call_id.
    rc_call = conn.execute(
        "SELECT schwab_api_call_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rc_call[0] == call_id
    # Reverse: schwab_api_calls.linked_correction_id = result.correction_id.
    api_back = conn.execute(
        "SELECT linked_correction_id FROM schwab_api_calls WHERE call_id = ?",
        (call_id,),
    ).fetchone()
    assert api_back[0] == result.correction_id


# ---------------------------------------------------------------------------
# Reconciliation_run_id stamped from discrepancy.run_id
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_stamps_reconciliation_run_id(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="run-id-stamp probe",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="production",
    )
    run_id_row = conn.execute(
        "SELECT reconciliation_run_id FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert run_id_row[0] == cvgi_world["run_id"]


# ---------------------------------------------------------------------------
# Risk-policy stamp from caller-supplied OR active fallback
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_stamps_caller_supplied_risk_policy_id(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="x",
        candidate_choices=None,
    )
    caller_policy_id = cvgi_world["active_policy_id"]
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        risk_policy_id=caller_policy_id,
        environment="production",
    )
    rp_row = conn.execute(
        "SELECT risk_policy_id_at_correction FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rp_row[0] == caller_policy_id


def test_apply_tier1_correction_falls_back_to_active_risk_policy_when_omitted(
    conn: sqlite3.Connection, cvgi_world: dict[str, Any],
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="x",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="production",
    )
    rp_row = conn.execute(
        "SELECT risk_policy_id_at_correction FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rp_row[0] == cvgi_world["active_policy_id"]


# ---------------------------------------------------------------------------
# Unknown discrepancy_id raises
# ---------------------------------------------------------------------------


def test_apply_tier1_correction_raises_on_unknown_discrepancy_id(
    conn: sqlite3.Connection,
) -> None:
    classification = ClassificationResult(
        tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="x",
        candidate_choices=None,
    )
    with pytest.raises(ValueError, match="discrepancy_id"):
        apply_tier1_correction(
            conn, discrepancy_id=999_999, classification=classification,
            environment="production",
        )
