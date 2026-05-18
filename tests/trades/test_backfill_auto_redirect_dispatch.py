"""Phase 12.5 #1 T-1.5.B — backfill multi-leg auto-redirect dispatch
in ``swing.trades.reconciliation_backfill._handle_pass_2`` +
``run_backfill`` + ``format_summary_block``.

OPERATIONAL FIRING SITE per F20 — Pass-2 ``_orders_to_classifier_payload``
builds the rich list-shape source_payload from freshly-fetched Schwab
orders WITH execution-grain data; the C.B classifier emits
``auto_redirect_recipe`` on this path; backfill consumes the recipe
through ``apply_tier2_resolution`` with override kwargs.

Pins (9 acceptance criteria from plan §A T-1.5.B):
  1. dry_run=True → outcome='projection_auto_redirect'; no mutation.
  2. dry_run=False, environment='production' → outcome=
     'tier1_multi_leg_auto_redirected'; N+1 correction rows + parent
     disc in operator_resolved_ambiguity with resolved_by=
     'auto_tier1_multi_leg'.
  3. dry_run=False, environment='sandbox' → outcome=
     'auto_redirect_skipped_sandbox'; no mutation.
  4. InvalidOverrideComboError propagates out (F21).
  5. ValidatorRejectedError / ValueError post-stamp → outcome=
     'tier2_stamped' with §7.5 fallback reason; disc stays in
     pending_ambiguity_resolution.
  6. Stamp failure → outcome='errored' (not 'tier2_stamped').
  7. schwab_api_call_id threaded to all N+1 correction rows.
  8. Mid-sequence pipeline-running race → BackfillPipelineActiveError
     on the second _check_pipeline_not_running call.
  9. BackfillSummary counter wiring — 3 new fields populated per
     outcome via run_backfill.

+ format_summary_block tests (renderer extension).
+ Slow E2E test (full classify → dispatch → state-cascade).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.models import (
    SchwabExecutionLeg,
    SchwabOrderResponse,
)
from swing.trades.reconciliation_auto_correct import InvalidOverrideComboError
from swing.trades.reconciliation_backfill import (
    BackfillPipelineActiveError,
    BackfillSummary,
    _handle_pass_2,
    format_summary_block,
    run_backfill,
)
from swing.trades.reconciliation_classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def v19_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "swing.db"
    ensure_schema(db_path).close()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("schwab_api", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_dhc_trade_and_fill(
    conn: sqlite3.Connection,
    *,
    journal_qty: float = 39.0,
    journal_price: float = 7.5797,
    ticker: str = "DHC",
) -> dict[str, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ticker, "2026-04-15", journal_price, int(journal_qty), 7.0, 7.0,
         "managing", "manual_off_pipeline", "2026-04-15T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-15T13:00:00", "entry", journal_qty,
         journal_price, "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return {"trade_id": trade_id, "fill_id": fill_id}


def _seed_unmatched_open_fill_disc(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    fill_id: int,
    ticker: str = "DHC",
    created_at: str = "2026-04-15T13:30:00",
) -> int:
    cur = conn.execute(
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
            json.dumps({"price": 7.50}),
            json.dumps({"matched": None}), "no Schwab match",
            1, "unresolved", None, None, created_at,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _make_multi_leg_order(
    *,
    order_id: str = "100",
    legs: list[tuple[float, float, str]] | None = None,
    instrument_symbol: str = "DHC",
) -> SchwabOrderResponse:
    """Build a SchwabOrderResponse with multiple execution legs.

    Default legs use uniform price=7.58 so the predicate's
    sub-condition 6 (per-leg price vs VWAP within tolerance) passes.
    Journal-price 7.5797 (set in _seed_dhc_trade_and_fill) is within
    the default $0.01 tolerance of leg-VWAP 7.58.
    """
    if legs is None:
        legs = [
            (20.0, 7.58, "2026-04-15T13:00:00.000Z"),
            (19.0, 7.58, "2026-04-15T13:00:42.000Z"),
        ]
    schwab_legs = [
        SchwabExecutionLeg(
            leg_id=i + 1,
            price=p,
            quantity=q,
            mismarked_quantity=0.0,
            instrument_id=None,
            time=t,
        )
        for i, (q, p, t) in enumerate(legs)
    ]
    total_qty = sum(q for q, _, _ in legs)
    return SchwabOrderResponse(
        order_id=order_id,
        status="FILLED",
        enter_time="2026-04-15T13:00:00",
        instrument_symbol=instrument_symbol,
        instruction="BUY",
        quantity=total_qty,
        order_type="LIMIT",
        price=7.50,
        executions=schwab_legs,
    )


class _FakeSchwabClient:
    pass


def _seed_schwab_api_call(
    conn: sqlite3.Connection,
    *,
    call_id: int,
    endpoint: str = "accounts.orders.list",
) -> None:
    """Plant a schwab_api_calls audit row so FK references
    (reconciliation_corrections.schwab_api_call_id) resolve. The
    backfill mocks return a call_id but the real audited wrapper would
    have already INSERTed the row; tests must seed it explicitly.
    """
    conn.execute(
        """
        INSERT INTO schwab_api_calls (
            call_id, ts, endpoint, status, surface, environment
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (call_id, "2026-05-16T10:00:00", endpoint, "success",
         "cli", "production"),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Acceptance #1 — Dry-run projection
# ---------------------------------------------------------------------------


def test_backfill_dry_run_emits_projection_auto_redirect_outcome(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    orders = [_make_multi_leg_order()]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=True,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.outcome == "projection_auto_redirect"
    assert out.tier == 1
    assert out.pass_2_call_id == 99
    assert summary.projection_auto_redirect == 1
    assert summary.tier1_multi_leg_auto_redirected == 0
    assert summary.tier2_stamped == 0
    # NO correction rows in dry-run mode.
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert n == 0
    # Discrepancy stays unresolved.
    res = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert res == "unresolved"


# ---------------------------------------------------------------------------
# Acceptance #2 — Production --apply tier1_multi_leg_auto_redirected
# ---------------------------------------------------------------------------


def test_backfill_production_apply_emits_tier1_multi_leg_auto_redirected_outcome(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    _seed_schwab_api_call(v19_db, call_id=99)
    orders = [_make_multi_leg_order()]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "tier1_multi_leg_auto_redirected"
    assert out.tier == 1
    assert out.correction_id is not None
    assert summary.tier1_multi_leg_auto_redirected == 1
    # N+1 correction rows (1 anchor + 2 partials).
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert n == 3
    # Parent disc in operator_resolved_ambiguity with auto resolved_by.
    row = v19_db.execute(
        "SELECT resolution, resolved_by FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()
    assert row[0] == "operator_resolved_ambiguity"
    assert row[1] == "auto_tier1_multi_leg"


# ---------------------------------------------------------------------------
# Acceptance #3 — Sandbox no-mutation
# ---------------------------------------------------------------------------


def test_backfill_sandbox_emits_auto_redirect_skipped_sandbox_outcome(
    v19_db: sqlite3.Connection,
) -> None:
    """Sandbox `_pass_2_dispatch` returns (None, None, sandbox_reason)
    BEFORE any Schwab API call, so the auto_redirect_recipe path does
    NOT fire — the reclassification is None. Mock `_pass_2_dispatch`
    to return the recipe-bearing classification so the auto-redirect
    branch reaches its sandbox short-circuit.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    # Build a recipe-bearing classification directly.
    recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-15T13:00:00"},
            {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-15T13:00:42"},
        ],
    }
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="multi-leg detected",
        candidate_choices=None,
        auto_redirect_recipe=recipe,
    )

    # Mock _pass_2_dispatch to bypass the sandbox short-circuit at that
    # layer and route the recipe-bearing classification through
    # _handle_pass_2's auto-redirect branch (where the §7.6.1 sandbox
    # short-circuit fires).
    with patch(
        "swing.trades.reconciliation_backfill._pass_2_dispatch",
        return_value=(fake_classification, 99, None),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="sandbox",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "auto_redirect_skipped_sandbox"
    assert summary.auto_redirect_skipped_sandbox == 1
    assert summary.tier1_multi_leg_auto_redirected == 0
    # ZERO correction rows.
    n = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert n == 0
    # Discrepancy STAYS in unresolved (NOT pending_ambiguity_resolution).
    res = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert res == "unresolved"


# ---------------------------------------------------------------------------
# Acceptance #4 — InvalidOverrideComboError propagates
# ---------------------------------------------------------------------------


def test_backfill_invalid_override_combo_propagates_out_of_handle_pass_2(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    bad_recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "operator",  # mismatched
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-15T13:00:00"},
            {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-15T13:00:42"},
        ],
    }
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="malformed test recipe",
        candidate_choices=None,
        auto_redirect_recipe=bad_recipe,
    )
    with patch(
        "swing.trades.reconciliation_backfill._pass_2_dispatch",
        return_value=(fake_classification, 99, None),
    ):
        with pytest.raises(InvalidOverrideComboError):
            run_backfill(
                v19_db,
                dry_run=False,
                schwab_client=_FakeSchwabClient(),
                environment="production",
                account_hash="acct-hash",
            )


# ---------------------------------------------------------------------------
# Acceptance #5 — ValidatorRejectedError / ValueError post-stamp fallback
# ---------------------------------------------------------------------------


def test_backfill_validator_rejected_post_stamp_falls_back_to_tier2_stamped(
    v19_db: sqlite3.Connection,
) -> None:
    """Plant a recipe whose payload sum != journal qty so the inner
    split_into_partials handler raises ValueError (qty_tolerance trip).
    Step 1 (stamp) succeeds; step 2 (apply) raises → fallback returns
    outcome='tier2_stamped' with reason citing 'declined post-stamp'.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    # Bad payload: legs sum to 38 not 39
    recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-15T13:00:00"},
            {"qty": 18.0, "price": 7.59, "fill_datetime": "2026-04-15T13:00:42"},
        ],
    }
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="bad payload sum",
        candidate_choices=None,
        auto_redirect_recipe=recipe,
    )
    with patch(
        "swing.trades.reconciliation_backfill._pass_2_dispatch",
        return_value=(fake_classification, 99, None),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "tier2_stamped"
    assert out.reason is not None
    assert "declined post-stamp" in out.reason
    # Discrepancy in pending_ambiguity_resolution (step 1 succeeded).
    res = v19_db.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()
    assert res[0] == "pending_ambiguity_resolution"
    assert res[1] == "multi_partial_vs_consolidated"


# ---------------------------------------------------------------------------
# Acceptance #6 — Stamp failure → errored
# ---------------------------------------------------------------------------


def test_backfill_stamp_failure_routes_to_errored_outcome(
    v19_db: sqlite3.Connection,
) -> None:
    """Monkeypatch stamp_pending_ambiguity to raise ValueError BEFORE any
    DB write → outcome='errored'; discrepancy stays unresolved.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-15T13:00:00"},
            {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-15T13:00:42"},
        ],
    }
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="stamp will fail",
        candidate_choices=None,
        auto_redirect_recipe=recipe,
    )
    with patch(
        "swing.trades.reconciliation_backfill._pass_2_dispatch",
        return_value=(fake_classification, 99, None),
    ), patch(
        "swing.trades.reconciliation_auto_correct.stamp_pending_ambiguity",
        side_effect=ValueError("stamp failed for arbitrary reason"),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "errored"
    assert out.reason is not None
    assert "auto-redirect stamp failed" in out.reason
    # Disc stays in unresolved.
    res = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()[0]
    assert res == "unresolved"


# ---------------------------------------------------------------------------
# Acceptance #7 — schwab_api_call_id threaded to all N+1 correction rows
# ---------------------------------------------------------------------------


def test_backfill_apply_threads_schwab_api_call_id_to_all_correction_rows(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    orders = [_make_multi_leg_order()]

    # Mock get_account_orders_audited to return call_id=42 so we can
    # verify the same call_id threads through to all correction rows.
    # Also write the audit row so the FK is satisfied (real call_id=42).
    _seed_schwab_api_call(v19_db, call_id=42)

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(42, orders),
    ):
        run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    # All N+1 correction rows have schwab_api_call_id=42.
    call_ids = [
        r[0] for r in v19_db.execute(
            "SELECT schwab_api_call_id FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? ORDER BY correction_id ASC",
            (disc_id,),
        ).fetchall()
    ]
    assert len(call_ids) == 3
    for cid in call_ids:
        assert cid == 42


# ---------------------------------------------------------------------------
# Acceptance #8 — Mid-sequence pipeline-running raises on second check
# ---------------------------------------------------------------------------


def test_backfill_mid_sequence_pipeline_running_raises_on_second_check(
    v19_db: sqlite3.Connection,
) -> None:
    """Inject a pipeline_runs row mid-iteration via test-fixture seam:
    use a stateful side_effect on _check_pipeline_not_running that
    raises on the Nth call.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db)
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    _seed_schwab_api_call(v19_db, call_id=99)
    orders = [_make_multi_leg_order()]

    # The check is called several times: at run_backfill entry; per-
    # discrepancy iteration; and TWICE inside _handle_pass_2 (before
    # stamp + before apply). We let the first 3 pass; the 4th raises
    # (simulating a pipeline starting between stamp and apply).
    call_count = {"n": 0}

    def fake_check(conn, *, partial_summary=None):
        call_count["n"] += 1
        if call_count["n"] >= 4:
            raise BackfillPipelineActiveError(
                "pipeline started mid-iteration",
                partial_summary=partial_summary,
            )

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ), patch(
        "swing.trades.reconciliation_backfill._check_pipeline_not_running",
        side_effect=fake_check,
    ):
        with pytest.raises(BackfillPipelineActiveError):
            run_backfill(
                v19_db,
                dry_run=False,
                schwab_client=_FakeSchwabClient(),
                environment="production",
                account_hash="acct-hash",
            )


# ---------------------------------------------------------------------------
# Acceptance #9 — BackfillSummary counter wiring per outcome
# ---------------------------------------------------------------------------


def test_backfill_summary_counter_increments_per_outcome(
    v19_db: sqlite3.Connection,
) -> None:
    """Mix 3 discrepancies — 1 production-apply, 1 dry-run-projection,
    1 sandbox-skip — and assert each summary counter increments
    independently. We run 3 separate invocations because mixing dry_run /
    environment per-row is not the natural API; the test asserts that
    run_backfill's elif ladder correctly routes per outcome.
    """
    # Test 1: production-apply path
    run_id1 = _seed_reconciliation_run(v19_db)
    seed1 = _seed_dhc_trade_and_fill(v19_db, ticker="DHC")
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id1, ticker="DHC", **seed1,
    )
    _seed_schwab_api_call(v19_db, call_id=99)
    orders = [_make_multi_leg_order()]
    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ):
        summary_apply = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )
    assert summary_apply.tier1_multi_leg_auto_redirected == 1
    assert summary_apply.projection_auto_redirect == 0
    assert summary_apply.auto_redirect_skipped_sandbox == 0

    # Test 2: dry-run-projection path on a fresh discrepancy
    seed2 = _seed_dhc_trade_and_fill(v19_db, ticker="LION")
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id1, ticker="LION", **seed2,
    )
    lion_orders = [_make_multi_leg_order(instrument_symbol="LION")]
    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(100, lion_orders),
    ):
        summary_dry = run_backfill(
            v19_db,
            dry_run=True,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
            ticker="LION",
        )
    assert summary_dry.projection_auto_redirect == 1

    # Test 3: sandbox path on a fresh discrepancy
    seed3 = _seed_dhc_trade_and_fill(v19_db, ticker="VIR")
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id1, ticker="VIR", **seed3,
    )
    recipe = {
        "choice_code": "split_into_partials",
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
        "payload": [
            {"qty": 20.0, "price": 7.57, "fill_datetime": "2026-04-15T13:00:00"},
            {"qty": 19.0, "price": 7.59, "fill_datetime": "2026-04-15T13:00:42"},
        ],
    }
    fake_classification = ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="multi-leg detected",
        candidate_choices=None,
        auto_redirect_recipe=recipe,
    )
    with patch(
        "swing.trades.reconciliation_backfill._pass_2_dispatch",
        return_value=(fake_classification, 101, None),
    ):
        summary_sandbox = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="sandbox",
            account_hash="acct-hash",
            ticker="VIR",
        )
    assert summary_sandbox.auto_redirect_skipped_sandbox == 1


# ---------------------------------------------------------------------------
# format_summary_block renderer extensions
# ---------------------------------------------------------------------------


def test_format_summary_block_renders_multi_leg_counters_when_nonzero() -> None:
    summary = BackfillSummary(
        tier1_multi_leg_auto_redirected=3,
        projection_auto_redirect=2,
        auto_redirect_skipped_sandbox=1,
    )
    block = format_summary_block(summary)
    assert "Multi-leg auto-redirects applied: 3" in block
    assert "Multi-leg auto-redirects (dry-run projection): 2" in block
    assert "Multi-leg auto-redirects skipped (sandbox): 1" in block
    # ASCII-only (F12 / CLAUDE.md cp1252 gotcha). No non-ASCII bytes.
    block.encode("ascii")  # raises UnicodeEncodeError on non-ASCII


def test_format_summary_block_omits_multi_leg_counter_when_zero() -> None:
    summary = BackfillSummary()  # all defaults (0)
    block = format_summary_block(summary)
    # None of the three new lines render when counters are 0.
    assert "Multi-leg auto-redirects applied:" not in block
    assert "Multi-leg auto-redirects (dry-run projection):" not in block
    assert "Multi-leg auto-redirects skipped (sandbox):" not in block


# ---------------------------------------------------------------------------
# Slow E2E test — full classify → dispatch → state-cascade
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count(
    v19_db: sqlite3.Connection,
) -> None:
    """End-to-end: plant reconciliation_run + multi-leg discrepancy +
    mocked schwab_client returning multi-leg SchwabOrderResponse +
    invoke run_backfill(dry_run=False, environment='production', ...)
    + assert FULL state cascade:
      - 3 correction rows written (1 anchor + 2 partials);
      - parent discrepancy in operator_resolved_ambiguity with
        resolved_by='auto_tier1_multi_leg';
      - direct SQL count of distinct discrepancy_ids that auto-redirected
        in the most recent run == 1 (T-1.7 helper not yet shipped; use
        direct SQL).
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )
    _seed_schwab_api_call(v19_db, call_id=99)
    orders = [_make_multi_leg_order()]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    # (a) 4 correction rows? Actually 3: 1 anchor (delete) + 2 inserts.
    # (resolved_by lives on the parent discrepancy, not the correction
    # rows — corrections carry applied_by + correction_action per the
    # F15 hybrid-row invariant.)
    rcs = v19_db.execute(
        "SELECT applied_by, correction_action "
        "FROM reconciliation_corrections WHERE discrepancy_id = ? "
        "ORDER BY correction_id ASC",
        (disc_id,),
    ).fetchall()
    assert len(rcs) == 3
    for applied_by, correction_action in rcs:
        assert applied_by == "auto"
        assert correction_action == "auto_applied"

    # (b) parent disc state cascade
    parent = v19_db.execute(
        "SELECT resolution, resolved_by, ambiguity_kind "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert parent[0] == "operator_resolved_ambiguity"
    assert parent[1] == "auto_tier1_multi_leg"
    assert parent[2] == "multi_partial_vs_consolidated"

    # (c) T-1.7 helper not yet shipped — use direct SQL to count distinct
    # discrepancy_ids that auto-redirected. `resolved_by` lives on the
    # parent discrepancy; JOIN on discrepancy_id.
    n_redirects = v19_db.execute(
        "SELECT COUNT(DISTINCT rc.discrepancy_id) "
        "FROM reconciliation_corrections rc "
        "JOIN reconciliation_discrepancies rd "
        "  ON rc.discrepancy_id = rd.discrepancy_id "
        "WHERE rd.resolved_by = ?",
        ("auto_tier1_multi_leg",),
    ).fetchone()[0]
    assert n_redirects == 1

    # (d) summary counter
    assert summary.tier1_multi_leg_auto_redirected == 1

    # (e) per_discrepancy_outcomes shape
    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "tier1_multi_leg_auto_redirected"
    assert out.correction_id is not None
    assert out.pass_2_call_id == 99
