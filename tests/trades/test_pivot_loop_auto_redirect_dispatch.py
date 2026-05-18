"""Phase 12.5 #1 T-1.5 — pivot-loop multi-leg auto-redirect dispatch
in ``swing.trades.schwab_reconciliation._pivot_classify_and_dispatch_for_run``.

Defensive future-proofing coverage per F20: today's initial pivot CANNOT
emit ``auto_redirect_recipe`` because it reads the persisted
``actual_value_json`` (``{"matched": null}`` sentinel for
``unmatched_*_fill``) and the classifier treats that as the no-payload
sentinel. To exercise this code path, tests monkeypatch
``classify_discrepancy`` at the pivot module's import binding so it
returns a ``ClassificationResult`` with the recipe attached.

Pins:
  - F20: defensive future-proofing branch DOES dispatch
    apply_tier2_resolution_inner when the recipe arrives.
  - F21: InvalidOverrideComboError PROPAGATES out (developer-bug
    fail-fast contract per spec §7.4 R4 M2 LOCK).
  - F16 outer-catch-ladder ordering: InvalidOverrideComboError before
    generic Exception (subclass of ValueError).
  - T-1.6 sandbox short-circuit: dedicated catch rolls back the stamp +
    increments sandbox_auto_redirect_skipped_count; discrepancy stays
    in 'unresolved'.
  - Spec §7.5 fallback: ValidatorRejectedError / ValueError (NOT
    InvalidOverrideComboError) → fresh-savepoint stamp +
    pending_ambiguity_resolution + tier2_pending_count++.
  - F15 hybrid-row invariant: all N+1 correction rows carry the
    auto-applied shape; parent disc carries resolved_by='auto_tier1_multi_leg'.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from swing.data.db import ensure_schema
from swing.trades.reconciliation_auto_correct import InvalidOverrideComboError
from swing.trades.reconciliation_classifier import ClassificationResult
from swing.trades.schwab_reconciliation import (
    _pivot_classify_and_dispatch_for_run,
    run_schwab_reconciliation,
)


# ---------------------------------------------------------------------------
# Synthetic Schwab fixtures
# ---------------------------------------------------------------------------


@dataclass
class _SchwabOrder:
    status: str
    price: float
    quantity: float
    instrument_symbol: str
    order_type: str = "MARKET"
    instruction: str = "BUY"
    order_id: str = "ORD-test"
    executions: object = None
    enter_time: str = "2026-04-27T14:23:00.000Z"


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_open_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    fill_price: float,
    qty: float = 39.0,
) -> tuple[int, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-27", fill_price, int(qty), 6.0, 6.0, "managing",
         "manual_off_pipeline", "2026-04-27T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", qty, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return trade_id, fill_id


def _seed_run_with_pending_multi_partial_disc(
    conn: sqlite3.Connection,
    *,
    ticker: str = "DHC",
    qty: float = 39.0,
    price: float = 7.50,
) -> dict[str, int]:
    """Plant a v19 fixture: open trade + fill + reconciliation_run +
    one unresolved discrepancy of kind multi_partial_vs_consolidated.
    """
    trade_id, fill_id = _seed_open_trade(
        conn, ticker=ticker, fill_price=price, qty=qty,
    )
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running",
         "2026-04-27", "2026-04-27"),
    )
    run_id = int(run_cur.lastrowid)
    # IMPORTANT: emit as 'entry_price_mismatch' with
    # 'pending_ambiguity_resolution' state? NO: the pivot loop only
    # iterates rows in resolution='unresolved'. Plant the row as
    # 'unresolved' (NULL ambiguity_kind) so the loop picks it up; the
    # auto-redirect branch will stamp pending_ambiguity_resolution +
    # then immediately resolve to operator_resolved_ambiguity (T-1.5
    # spec).
    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind,
            resolution_reason, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, "unmatched_open_fill", trade_id, fill_id, ticker,
            "fill_match",
            json.dumps({"price": price}),
            json.dumps({"matched": None}), "no Schwab match",
            1, "unresolved",
            None,
            None,
            "2026-05-15T12:00:00",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    return {
        "trade_id": trade_id,
        "fill_id": fill_id,
        "run_id": run_id,
        "discrepancy_id": discrepancy_id,
    }


def _make_recipe(
    *,
    qty_total: float = 39.0,
    legs: list[tuple[float, float, str]] | None = None,
) -> dict[str, Any]:
    """Build an auto_redirect_recipe dict mirroring classifier output."""
    if legs is None:
        legs = [
            (20.0, 7.57, "2026-04-27T14:23:00"),
            (19.0, 7.59, "2026-04-27T14:23:42"),
        ]
    payload = [
        {"qty": q, "price": p, "fill_datetime": dt}
        for (q, p, dt) in legs
    ]
    return {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": payload,
    }


def _make_recipe_result(recipe: dict[str, Any]) -> ClassificationResult:
    return ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="Schwab returned 2 partials summing to journal qty",
        candidate_choices=None,
        auto_redirect_recipe=recipe,
    )


# ---------------------------------------------------------------------------
# Test #1 — recipe present → dispatches apply_tier2_resolution_inner
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_recipe_present_dispatches_apply_tier2_resolution_inner(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_run_with_pending_multi_partial_disc(conn)
    recipe = _make_recipe()
    counters: dict[str, int] = {}
    fake_classification = _make_recipe_result(recipe)

    # Monkeypatch classify_discrepancy at the pivot module's import binding.
    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # Counter incremented.
    assert counters["tier1_multi_leg_auto_redirected_count"] == 1
    # 3 correction rows (1 delete anchor + 2 partial inserts).
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 3
    # Parent disc carries the auto resolved_by.
    drow = conn.execute(
        "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "operator_resolved_ambiguity"
    assert drow[1] == "auto_tier1_multi_leg"


# ---------------------------------------------------------------------------
# Test #2 — recipe absent → falls through to tier-2 stamp (regression)
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_recipe_absent_falls_through_to_tier2_stamp(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_run_with_pending_multi_partial_disc(conn)
    counters: dict[str, int] = {}
    # tier-2, no recipe — existing tier-2 stamp path.
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_match_within_window",
        correction_target=None,
        correction_reason="multi-match scenario",
        candidate_choices=None,
        auto_redirect_recipe=None,
    )
    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    assert counters["tier2_pending_count"] == 1
    assert counters["tier1_multi_leg_auto_redirected_count"] == 0
    # No correction rows; disc in pending_ambiguity_resolution.
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 0
    res = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert res == "pending_ambiguity_resolution"


# ---------------------------------------------------------------------------
# Test #3 — InvalidOverrideComboError propagates out (F21 + spec §7.4 R4 M2)
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_invalid_override_combo_propagates_out(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_run_with_pending_multi_partial_disc(conn)
    # Malformed recipe — resolved_by mismatch with the auto triple.
    bad_recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "operator",  # mismatched intent
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
            {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
        ],
    }
    fake_classification = _make_recipe_result(bad_recipe)
    counters: dict[str, int] = {}

    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(InvalidOverrideComboError):
                _pivot_classify_and_dispatch_for_run(
                    conn,
                    run_id=seed["run_id"],
                    schwab_orders=[],
                    schwab_api_call_id=None,
                    environment="production",
                    counters=counters,
                )
        finally:
            conn.rollback()
    # Counter NOT incremented (raise propagated; no successful dispatch).
    assert counters.get("tier1_multi_leg_auto_redirected_count", 0) == 0
    # Counter NOT in tier_errored either (developer-bug fail-fast,
    # not graceful-degradation).
    assert counters.get("tier_errored_count", 0) == 0


# ---------------------------------------------------------------------------
# Test #4 — outer catch ladder ordering pin (InvalidOverrideComboError
# first; generic ValueError second)
# ---------------------------------------------------------------------------


def test_pivot_loop_outer_catch_ladder_invalid_override_first_generic_second(
    conn: sqlite3.Connection,
) -> None:
    """Verify the catch-ladder ordering at schwab_reconciliation.py outer:

    - Plant a tier-1 generic Exception → counter['tier_errored_count'] == 1;
      no propagation.
    - Plant an InvalidOverrideComboError → propagates out.

    Two sub-fixtures inside one test to keep the discriminating-test
    pattern tight + pin both arms of the ladder.
    """
    # (a) Generic exception: tier-2 stamp raises some non-InvalidOverride
    # ValueError. Use a recipe-bearing classifier that triggers the
    # auto-redirect branch but the stamp_pending raises.
    seed1 = _seed_run_with_pending_multi_partial_disc(conn, ticker="VSAT")
    recipe = _make_recipe()
    fake_classification = _make_recipe_result(recipe)
    counters: dict[str, int] = {}

    # Force the stamp_pending_ambiguity_inner to raise a non-
    # InvalidOverrideCombo ValueError → §7.5 fallback fires → tier2_pending++.
    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ), patch(
        "swing.trades.schwab_reconciliation._stamp_pending_ambiguity_inner",
        side_effect=ValueError("stamp failed for arbitrary reason"),
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed1["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    # ValueError on stamp → §7.5 fallback → fresh savepoint stamp re-runs
    # (but the fresh stamp ALSO raises since the same mock is active);
    # the fallback's `except Exception` increments tier_errored_count.
    # Discriminating signal: NOT InvalidOverrideComboError propagating out.
    assert counters.get("tier1_multi_leg_auto_redirected_count", 0) == 0
    # Either tier2_pending_count or tier_errored_count incremented;
    # MOST IMPORTANTLY the call did not raise out.
    assert (
        counters.get("tier_errored_count", 0)
        + counters.get("tier2_pending_count", 0)
    ) == 1

    # (b) Bad recipe: propagates.
    seed2 = _seed_run_with_pending_multi_partial_disc(conn, ticker="LION")
    bad_recipe = {
        **recipe,
        "resolved_by": "operator",  # mismatched intent
    }
    fake_bad_class = _make_recipe_result(bad_recipe)
    counters2: dict[str, int] = {}
    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_bad_class,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(InvalidOverrideComboError):
                _pivot_classify_and_dispatch_for_run(
                    conn,
                    run_id=seed2["run_id"],
                    schwab_orders=[],
                    schwab_api_call_id=None,
                    environment="production",
                    counters=counters2,
                )
        finally:
            conn.rollback()


# ---------------------------------------------------------------------------
# Test #5 — sandbox short-circuit rolls back stamp; counter incremented;
# discrepancy stays in 'unresolved'
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_sandbox_short_circuit_rolls_back_stamp(
    conn: sqlite3.Connection,
) -> None:
    seed = _seed_run_with_pending_multi_partial_disc(conn)
    recipe = _make_recipe()
    fake_classification = _make_recipe_result(recipe)
    counters: dict[str, int] = {}

    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="sandbox",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    assert counters["sandbox_auto_redirect_skipped_count"] == 1
    assert counters.get("tier1_multi_leg_auto_redirected_count", 0) == 0
    # Discrepancy stays in 'unresolved' (stamp rolled back).
    res = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert res == "unresolved"
    # No correction rows for this discrepancy.
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 0


# ---------------------------------------------------------------------------
# Test #6 — ValidatorRejectedError-ish → §7.5 fresh-savepoint fallback
# (counter['tier2_pending_count'] ++ ; counter['tier1_multi_leg_auto_redirected_count'] stays 0)
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_validator_rejected_falls_back_to_pending_ambiguity_resolution(
    conn: sqlite3.Connection,
) -> None:
    """Plant a recipe whose synthesized payload trips a downstream guard
    (using a malformed payload that would trip _handle_split_into_partials'
    qty_tolerance=1e-6 — easiest: payload sum != journal qty.). Verify
    the §7.5 fresh-savepoint fallback fires → discrepancy ends in
    pending_ambiguity_resolution; tier1_multi_leg_auto_redirected_count
    stays 0; tier2_pending_count == 1.
    """
    seed = _seed_run_with_pending_multi_partial_disc(conn, qty=39.0)
    # Malformed payload — legs sum to 38 (not 39).
    bad_recipe = _make_recipe(legs=[
        (20.0, 7.57, "2026-04-27T14:23:00"),
        (18.0, 7.59, "2026-04-27T14:23:42"),  # 38 not 39
    ])
    fake_classification = _make_recipe_result(bad_recipe)
    counters: dict[str, int] = {}

    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    assert counters.get("tier1_multi_leg_auto_redirected_count", 0) == 0
    assert counters["tier2_pending_count"] == 1
    # Disc lands in pending_ambiguity_resolution (the fresh-savepoint stamp).
    res = conn.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert res[0] == "pending_ambiguity_resolution"
    assert res[1] == "multi_partial_vs_consolidated"


# ---------------------------------------------------------------------------
# Test #7 — F15 hybrid-row invariant: N+1 correction rows all auto-applied
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_writes_n_plus_1_correction_rows_all_hybrid_shape(
    conn: sqlite3.Connection,
) -> None:
    """Multi-leg fixture with 3 legs → 4 correction rows (1 anchor +
    3 partials); all 4 carry applied_by='auto' + correction_action='auto_applied'.
    Parent disc has resolved_by='auto_tier1_multi_leg'.
    """
    # Use qty=60 = 20+20+20
    seed = _seed_run_with_pending_multi_partial_disc(
        conn, ticker="MULTI3", qty=60.0,
    )
    recipe = _make_recipe(legs=[
        (20.0, 7.57, "2026-04-27T14:23:00"),
        (20.0, 7.58, "2026-04-27T14:23:42"),
        (20.0, 7.59, "2026-04-27T14:24:13"),
    ])
    fake_classification = _make_recipe_result(recipe)
    counters: dict[str, int] = {}

    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    rcs = conn.execute(
        "SELECT applied_by, correction_action FROM reconciliation_corrections "
        "WHERE discrepancy_id = ? ORDER BY correction_id ASC",
        (seed["discrepancy_id"],),
    ).fetchall()
    assert len(rcs) == 4  # 1 anchor (delete) + 3 inserts
    for applied_by, correction_action in rcs:
        assert applied_by == "auto"
        assert correction_action == "auto_applied"
    # Parent disc carries auto resolved_by.
    drow = conn.execute(
        "SELECT resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "auto_tier1_multi_leg"


# ---------------------------------------------------------------------------
# Test #8 — counter setdefault idempotent (no re-zero across invocations)
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_counter_setdefault_idempotent(
    conn: sqlite3.Connection,
) -> None:
    """Invoke pivot loop twice on the same counters dict — counter
    doesn't get re-zeroed; cumulative count is correct.
    """
    seed1 = _seed_run_with_pending_multi_partial_disc(conn, ticker="A")
    seed2 = _seed_run_with_pending_multi_partial_disc(conn, ticker="B")
    recipe = _make_recipe()
    fake_classification = _make_recipe_result(recipe)
    counters: dict[str, int] = {}

    for seed in (seed1, seed2):
        with patch(
            "swing.trades.schwab_reconciliation.classify_discrepancy",
            return_value=fake_classification,
        ):
            conn.execute("BEGIN IMMEDIATE")
            try:
                _pivot_classify_and_dispatch_for_run(
                    conn,
                    run_id=seed["run_id"],
                    schwab_orders=[],
                    schwab_api_call_id=None,
                    environment="production",
                    counters=counters,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    # Cumulative — setdefault did not re-zero.
    assert counters["tier1_multi_leg_auto_redirected_count"] == 2


# ---------------------------------------------------------------------------
# Test #9 — counter keys present on empty run
# ---------------------------------------------------------------------------


def test_pivot_loop_auto_redirect_counter_keys_present_even_on_empty_run(
    conn: sqlite3.Connection,
) -> None:
    # No discrepancies in this fixture; just create a run.
    run_cur = conn.execute(
        """
        INSERT INTO reconciliation_runs (
            source, started_ts, state, period_start, period_end
        ) VALUES (?, ?, ?, ?, ?)
        """,
        ("schwab_api", "2026-05-15T12:00:00", "running",
         "2026-04-27", "2026-04-27"),
    )
    run_id = int(run_cur.lastrowid)
    conn.commit()
    counters: dict[str, int] = {}

    conn.execute("BEGIN IMMEDIATE")
    try:
        _pivot_classify_and_dispatch_for_run(
            conn,
            run_id=run_id,
            schwab_orders=[],
            schwab_api_call_id=None,
            environment="production",
            counters=counters,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    assert counters["tier1_applied_count"] == 0
    assert counters["tier2_pending_count"] == 0
    assert counters["tier_errored_count"] == 0
    assert counters["tier1_multi_leg_auto_redirected_count"] == 0
    assert counters["sandbox_auto_redirect_skipped_count"] == 0


# ---------------------------------------------------------------------------
# Test #10 — Pass-1 tier-1 path unaffected by Phase 12.5 #1 changes
# (regression)
# ---------------------------------------------------------------------------


def test_pivot_loop_tier1_pass_1_path_unaffected_by_phase_12_5_1_changes(
    conn: sqlite3.Connection,
) -> None:
    """Regression: pre-existing Pass-1 tier-1 path still fires; new
    counter stays at 0.
    """
    # Use the real run_schwab_reconciliation end-to-end which exercises
    # the existing CVGI-shape entry_price_mismatch tier-1 path.
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
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-27T14:23:00", "entry", 100.0, 5.23,
         "unreconciled"),
    )
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()

    from swing.integrations.schwab.models import SchwabExecutionLeg
    leg = SchwabExecutionLeg(
        leg_id=1, price=5.30, quantity=100.0,
        mismarked_quantity=0.0, instrument_id=None,
        time="2026-04-27T14:23:00.000Z",
    )
    schwab_orders = [
        _SchwabOrder(
            status="FILLED", price=5.30, quantity=100.0,
            instrument_symbol="CVGI",
            executions=[leg],
        ),
    ]
    schwab_account = _SchwabAccount(net_liquidating_value=2000.0, positions=[])
    run = run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    # Tier-1 auto-correct applied + counter present in summary_json.
    summary = json.loads(run.summary_json)
    assert summary.get("tier1_applied_count", 0) == 1
    assert summary.get("tier1_multi_leg_auto_redirected_count", 0) == 0
    assert summary.get("sandbox_auto_redirect_skipped_count", 0) == 0


# ---------------------------------------------------------------------------
# Test #11 — Case A end-to-end through pivot loop (n=1 multi-leg reroute)
# ---------------------------------------------------------------------------


def test_pivot_loop_n_eq_1_multi_leg_reroute_e2e(
    conn: sqlite3.Connection,
) -> None:
    """Case A: 1 candidate with N>=2 legs summing to journal qty →
    ambiguity_kind reclassified to multi_partial_vs_consolidated AND
    auto-redirect fires + N+1 correction rows.

    Same pattern as test #1 (monkeypatch classifier with a recipe), but
    explicitly pins the "n=1 with multiple legs" scenario per spec §6.5
    + plan §G.2 narrative.
    """
    seed = _seed_run_with_pending_multi_partial_disc(conn, qty=39.0)
    # Recipe shaped as if from a single candidate with 2 legs internally.
    recipe = _make_recipe(legs=[
        (20.0, 7.57, "2026-04-27T14:23:00"),
        (19.0, 7.59, "2026-04-27T14:23:42"),
    ])
    fake_classification = _make_recipe_result(recipe)
    counters: dict[str, int] = {}

    with patch(
        "swing.trades.schwab_reconciliation.classify_discrepancy",
        return_value=fake_classification,
    ):
        conn.execute("BEGIN IMMEDIATE")
        try:
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=seed["run_id"],
                schwab_orders=[],
                schwab_api_call_id=None,
                environment="production",
                counters=counters,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # Multi-leg auto-redirect counter == 1; tier-2 pending stays 0.
    assert counters["tier1_multi_leg_auto_redirected_count"] == 1
    assert counters.get("tier2_pending_count", 0) == 0
    # N+1 correction rows.
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()[0]
    assert n == 3  # 1 anchor (delete) + 2 inserts
    # Parent disc in operator_resolved_ambiguity with auto resolved_by.
    drow = conn.execute(
        "SELECT resolution, resolved_by, ambiguity_kind "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (seed["discrepancy_id"],),
    ).fetchone()
    assert drow[0] == "operator_resolved_ambiguity"
    assert drow[1] == "auto_tier1_multi_leg"
    assert drow[2] == "multi_partial_vs_consolidated"
