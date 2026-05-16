"""Phase 12 C.D T-D.9 — backfill idempotency + ``--retry-pass-2-failures``.

Per plan §E.9 acceptance criteria #1-5 + spec §8.3 + §8.4 #3:

  1. Re-run on fully-resolved DB: ``resolution != 'unresolved'`` rows
     SKIPPED at orchestrator level BEFORE service-layer payload
     validation fires (NEW C.C lesson #3 — SELECT-first idempotency
     precedes payload validation). Counter
     ``skipped_already_resolved`` increments.
  2. Pass-2-failed discrepancies (persisted state per §8.4 #3 —
     ``resolution='pending_ambiguity_resolution'`` +
     ``ambiguity_kind='unsupported'`` +
     ``resolution_reason`` contains ``"Pass 2 re-fetch failed"``) on
     default ``--apply`` are SKIPPED with
     ``skipped_pass_2_failed`` counter increment.
  3. ``--retry-pass-2-failures`` flag (opt-in) scopes iteration to
     Pass-2-failed rows ONLY + re-fetches Schwab + re-classifies. On
     SUCCESS with new ``ambiguity_kind``, ``stamp_pending_ambiguity(...,
     allow_pending_update=True)`` OVERWRITES the prior failure stamp.
     On REPEATED FAILURE, refreshes ``resolution_reason`` via the same
     mechanism (advisory).
  4. CLI summary printout (T-D.9 verbatim layout) printed on both
     ``--apply`` AND ``--dry-run``.
  5. Mixed state: per-counter discrimination across unresolved +
     pass-2-failed + already-resolved + tier-1-eligible buckets.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.client import SchwabAuthError
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.trades.reconciliation_backfill import (
    BackfillSummary,
    format_summary_block,
    run_backfill,
)


# ---------------------------------------------------------------------------
# Test scaffold — minimal v19 schema + fixture seeds
# ---------------------------------------------------------------------------


@pytest.fixture
def v19_db(tmp_path: Path) -> sqlite3.Connection:
    """Create + return a sqlite3 connection to a fresh v19 schema."""
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
    conn: sqlite3.Connection, *, journal_qty: float = 39.0,
    journal_price: float = 7.50, ticker: str = "DHC",
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
        (trade_id, "2026-04-15T13:00:00", "entry", journal_qty, journal_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    from swing.data.repos.fills import _recompute_aggregates
    _recompute_aggregates(conn, trade_id)
    conn.commit()
    return {"trade_id": trade_id, "fill_id": fill_id}


def _seed_cvgi_trade_and_fill(
    conn: sqlite3.Connection, *, journal_price: float = 5.23,
) -> dict[str, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("CVGI", "2026-04-15", journal_price, 100, 4.5, 4.5,
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
        (trade_id, "2026-04-15T13:00:00", "entry", 100, journal_price,
         "unreconciled"),
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
    ticker: str,
    resolution: str = "unresolved",
    ambiguity_kind: str | None = None,
    resolution_reason: str | None = None,
) -> int:
    # Terminal-state resolutions require resolved_at + resolved_by stamps;
    # 'unresolved' + 'pending_ambiguity_resolution' do NOT.
    is_terminal = resolution not in (
        "unresolved", "pending_ambiguity_resolution",
    )
    resolved_at = "2026-05-16T11:00:00" if is_terminal else None
    resolved_by = "operator" if is_terminal else None
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, fill_id, ticker, "
        "  field_name, expected_value_json, actual_value_json, "
        "  material_to_review, resolution, ambiguity_kind, "
        "  resolution_reason, resolved_at, resolved_by, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "unmatched_open_fill", trade_id, fill_id, ticker,
            "match",
            json.dumps({"fill_datetime": "2026-04-15T13:00:00"}),
            json.dumps({"matched": None}),
            1, resolution, ambiguity_kind, resolution_reason,
            resolved_at, resolved_by,
            "2026-05-16T10:06:00",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _seed_entry_price_mismatch_disc(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    trade_id: int,
    fill_id: int,
    ticker: str,
    schwab_price: float,
    resolution: str = "unresolved",
) -> int:
    """Plant a tier-1-eligible Shape-A entry_price_mismatch discrepancy."""
    is_terminal = resolution not in (
        "unresolved", "pending_ambiguity_resolution",
    )
    resolved_at = "2026-05-16T11:00:00" if is_terminal else None
    resolved_by = "operator" if is_terminal else None
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, fill_id, ticker, "
        "  field_name, expected_value_json, actual_value_json, "
        "  material_to_review, resolution, resolved_at, resolved_by, "
        "  created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "entry_price_mismatch", trade_id, fill_id, ticker,
            "price",
            json.dumps({"price": 5.23}),
            json.dumps({"price": schwab_price}),
            1, resolution, resolved_at, resolved_by,
            "2026-05-16T10:06:00",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def _make_order(
    *,
    order_id: str = "1",
    quantity: float = 20.0,
    price: float | None = 7.50,
    instrument_symbol: str = "DHC",
    instruction: str = "BUY",
    order_type: str = "LIMIT",
) -> SchwabOrderResponse:
    return SchwabOrderResponse(
        order_id=order_id,
        status="FILLED",
        enter_time="2026-04-15T13:00:00",
        instrument_symbol=instrument_symbol,
        instruction=instruction,
        quantity=quantity,
        order_type=order_type,
        price=price,
    )


class _FakeSchwabClient:
    pass


# ---------------------------------------------------------------------------
# Test 1 — Re-run on fully-resolved DB: 0 mutations + skipped counter
# ---------------------------------------------------------------------------


def test_fully_resolved_db_yields_zero_mutations_skipped_counter(
    v19_db: sqlite3.Connection,
) -> None:
    """Per plan §E.9 acceptance #1: re-running --apply on already-resolved
    discrepancies is a no-op + ``skipped_already_resolved`` increments.

    DISCRIMINATING: the existing default filter at
    ``_iter_unresolved_discrepancies`` excludes ``resolution !=
    'unresolved'`` rows from iteration. To exercise the orchestrator-level
    SELECT-first idempotency check (NEW C.C lesson #3 — race-condition
    defense between iteration-list SELECT and apply-time), we plant
    discrepancies with ``resolution='unresolved'`` then MUTATE them to a
    terminal state mid-iteration via a patched
    ``_classify_and_apply`` that flips state between iteration-list SELECT
    and apply-time.

    Simpler discriminating path: plant N already-resolved discrepancies +
    invoke without --retry-pass-2-failures. The default filter excludes
    them. Test asserts run yields empty summary (no mutations). This pins
    the negative case (filter works) but not the SELECT-first idempotency
    path. We exercise BOTH below.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db)
    # Plant 3 already-resolved discrepancies (one per terminal state).
    for resolution in (
        "auto_corrected_from_schwab",
        "acknowledged_immaterial",
        "journal_corrected",
    ):
        _seed_entry_price_mismatch_disc(
            v19_db,
            run_id=run_id,
            ticker="CVGI",
            schwab_price=5.30,
            resolution=resolution,
            **seed,
        )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash="acct-hash",
    )

    # The default ``resolution = 'unresolved'`` filter excludes all 3 rows
    # from iteration — backfill is a no-op.
    assert summary.tier1_applied == 0
    assert summary.tier2_stamped == 0
    assert summary.pass_2_failed == 0
    assert len(summary.per_discrepancy_outcomes) == 0
    # The summary printout format should be valid even with zero counters.
    block = format_summary_block(summary)
    assert "Skipped (already resolved): 0" in block


# ---------------------------------------------------------------------------
# Test 1.bis — SELECT-first idempotency: race-condition defense
# ---------------------------------------------------------------------------


def test_select_first_idempotency_when_discrepancy_resolved_between_select_and_apply(
    v19_db: sqlite3.Connection,
) -> None:
    """SELECT-first idempotency check at apply-time per NEW C.C lesson #3.

    Plant an unresolved discrepancy. Between ``_iter_unresolved_discrepancies``
    listing it and the per-row apply step firing, race-condition mutation
    flips the row to a terminal state. The orchestrator MUST detect this
    via SELECT-first idempotency at apply-time + SKIP with
    ``skipped_already_resolved`` counter increment + ZERO service-layer
    payload validation fired.

    DISCRIMINATING: if SELECT-first is absent, the apply-time path would
    proceed into the classifier + ``apply_tier1_correction`` and either
    (a) raise on validation against an already-mutated journal row, or
    (b) idempotent-return at the service layer (after wasted compute).
    The counter ``skipped_already_resolved`` would NOT increment in either
    case.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_cvgi_trade_and_fill(v19_db)
    disc_id = _seed_entry_price_mismatch_disc(
        v19_db, run_id=run_id, ticker="CVGI", schwab_price=5.30, **seed,
    )

    # Simulate race: another writer flips the row to terminal state
    # BETWEEN iteration-list SELECT and apply-time. We patch
    # ``_classify_and_apply`` indirectly by mutating the row before the
    # loop fires its per-row check. Simpler: invoke run_backfill but
    # mutate the row HERE first via a side-effect injected via a patch on
    # the classifier — that flow needs the orchestrator's SELECT-first
    # check at apply-time.
    #
    # Simplest discriminating approach: pre-resolve the row in the SAME
    # connection that backfill uses. The default filter would normally
    # exclude it, BUT we patch _iter_unresolved_discrepancies to return
    # it anyway (simulating the race-condition list-SELECT-stale-data).
    from swing.trades import reconciliation_backfill as bf

    # Capture the original iter; will return the row even though it's
    # already resolved. We do this BEFORE mutating the row.
    original_iter = bf._iter_unresolved_discrepancies

    def _stale_iter(conn: sqlite3.Connection, **kwargs: Any) -> list:
        # Read row regardless of resolution state.
        from swing.data.repos.reconciliation import (
            _DISCREPANCY_SELECT_COLUMNS,
            _row_to_discrepancy,
        )
        row = conn.execute(
            f"SELECT {_DISCREPANCY_SELECT_COLUMNS} "
            "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
            (disc_id,),
        ).fetchone()
        return [_row_to_discrepancy(row)]

    # First: read the discrepancy to simulate iteration-list step.
    stale_disc_list = _stale_iter(v19_db)
    assert len(stale_disc_list) == 1
    assert stale_disc_list[0].resolution == "unresolved"

    # Now: mutate the row to a terminal state (race-condition).
    # Terminal states require resolved_at + resolved_by stamps.
    v19_db.execute(
        "UPDATE reconciliation_discrepancies "
        "SET resolution = 'acknowledged_immaterial', "
        "    resolved_at = '2026-05-16T11:30:00', "
        "    resolved_by = 'race-condition-test' "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    )
    v19_db.commit()

    # Invoke run_backfill with the stale iterator. The orchestrator MUST
    # detect the race via SELECT-first at apply-time + skip.
    with patch.object(bf, "_iter_unresolved_discrepancies", _stale_iter):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=None,
            environment="production",
            account_hash="acct-hash",
        )

    # SELECT-first detects terminal state + increments skip counter.
    assert summary.skipped_already_resolved == 1
    assert summary.tier1_applied == 0
    assert summary.tier2_stamped == 0
    assert len(summary.per_discrepancy_outcomes) == 1
    outcome = summary.per_discrepancy_outcomes[0]
    assert outcome.outcome == "skipped_already_resolved"
    # State is unchanged from the mid-race mutation.
    row = v19_db.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "acknowledged_immaterial"


# ---------------------------------------------------------------------------
# Test 2 — Default skip Pass-2-failed
# ---------------------------------------------------------------------------


def test_default_skip_pass_2_failed_discrepancies(
    v19_db: sqlite3.Connection,
) -> None:
    """Per plan §E.9 acceptance #2 + spec §8.3: Pass-2-failed
    discrepancies persisted as ``('pending_ambiguity_resolution',
    'unsupported')`` with ``"Pass 2 re-fetch failed"`` substring are
    SKIPPED on default ``--apply`` (no ``--retry-pass-2-failures``);
    ``skipped_pass_2_failed`` counter increments.

    DISCRIMINATING: without the explicit skip, the default
    ``resolution = 'unresolved'`` filter would already exclude these rows
    (since their resolution is ``'pending_ambiguity_resolution'``), so
    they would NOT appear in the iteration list at all + the
    ``skipped_pass_2_failed`` counter would stay 0. This test asserts the
    counter is >0 ON DEFAULT --apply, which requires the orchestrator to
    EXPLICITLY enumerate pass-2-failed rows + increment the skip counter
    WITHOUT touching them. The retry path test below covers the inverse
    (retry-flag scopes iteration to these rows).
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="DHC",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason=(
            "Pass 2 re-fetch failed: SchwabAuthError: 401 refresh_token expired"
        ),
        **seed,
    )

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash="acct-hash",
        retry_pass_2_failures=False,
    )

    assert summary.skipped_pass_2_failed == 1
    assert summary.tier1_applied == 0
    assert summary.tier2_stamped == 0
    assert summary.pass_2_failed == 0
    # The row is UNTOUCHED — no audit row, no state flip.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "unsupported"
    assert "Pass 2 re-fetch failed" in (row[2] or "")
    # Per-outcome record reflects the skip.
    outcome = summary.per_discrepancy_outcomes[0]
    assert outcome.outcome == "skipped_pass_2_failed"
    assert outcome.discrepancy_id == disc_id

    # Summary printout — assert format includes the skip-pass-2 line.
    block = format_summary_block(summary)
    assert "Skipped (Pass-2-failed" in block
    assert "use --retry-pass-2-failures to retry" in block


# ---------------------------------------------------------------------------
# Test 3 — --retry-pass-2-failures re-attempts + overwrites on success
# ---------------------------------------------------------------------------


def test_retry_pass_2_failures_reattempts_and_overwrites_on_success(
    v19_db: sqlite3.Connection,
) -> None:
    """Per plan §E.9 acceptance #3: ``--retry-pass-2-failures`` scopes
    iteration to Pass-2-failed rows + re-fetches Schwab + writes new
    ``schwab_api_calls`` audit row + re-classifies + overwrites the prior
    failure-state stamp with the new classification via
    ``stamp_pending_ambiguity(..., allow_pending_update=True)``.

    DISCRIMINATING: assert (a) ``get_account_orders_audited`` IS called
    exactly once; (b) the discrepancy's ``ambiguity_kind`` is OVERWRITTEN
    from ``'unsupported'`` to the new classification (e.g.,
    ``'multi_partial_vs_consolidated'``); (c) ``resolution_reason`` no
    longer contains ``"Pass 2 re-fetch failed"``. Without
    ``allow_pending_update=True``, the inner would no-op-idempotent-return
    + the stamp would NOT overwrite + (b) and (c) would fail.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="DHC",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason=(
            "Pass 2 re-fetch failed: SchwabAuthError: 401 refresh_token expired"
        ),
        **seed,
    )

    orders = [
        _make_order(order_id="100", quantity=20.0),
        _make_order(order_id="101", quantity=19.0),
    ]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(99, orders),
    ) as audited_mock:
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
            retry_pass_2_failures=True,
        )

    # Audited wrapper invoked exactly once.
    assert audited_mock.call_count == 1
    # Tier-2 stamped + new classification overwrote prior failure.
    assert summary.tier2_stamped == 1
    assert summary.pass_2_failed == 0
    assert summary.skipped_pass_2_failed == 0
    # Discrepancy's persisted state reflects the new classification.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "multi_partial_vs_consolidated"
    # Old failure reason replaced.
    assert "Pass 2 re-fetch failed" not in (row[2] or "")


# ---------------------------------------------------------------------------
# Test 4 — --retry-pass-2-failures re-fails (still raises)
# ---------------------------------------------------------------------------


def test_retry_pass_2_failures_re_fails_refreshes_reason(
    v19_db: sqlite3.Connection,
) -> None:
    """Per plan §E.9 acceptance #3 (failure branch): retry re-fails →
    ``stamp_pending_ambiguity(..., allow_pending_update=True)`` refreshes
    ``resolution_reason`` with the latest failure timestamp/exception text
    (advisory; non-binding); state stays in
    ``('pending_ambiguity_resolution', 'unsupported')``.

    DISCRIMINATING: plant a Pass-2-failed row with the OLD failure reason
    text; re-fetch raises a DIFFERENT exception class (so the new reason
    text differs); assert the row's ``resolution_reason`` reflects the
    new exception text + ``pass_2_failed`` counter increments.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    old_reason = (
        "Pass 2 re-fetch failed: SchwabAuthError: 401 refresh_token expired"
    )
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="DHC",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason=old_reason,
        **seed,
    )

    def _raise_new_error(*args: Any, **kwargs: Any) -> None:
        # Different exception class than the planted-old-reason text.
        raise SchwabAuthError(403, "token revoked by user")

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        side_effect=_raise_new_error,
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
            retry_pass_2_failures=True,
        )

    # Per-LOCK: even on repeated failure, summary reflects pass_2_failed.
    assert summary.pass_2_failed == 1
    # Row's resolution_reason refreshed with the NEW error text.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "unsupported"
    assert "Pass 2 re-fetch failed" in (row[2] or "")
    # New error substring present; old error substring should NOT remain
    # (the resolution_reason was overwritten with the latest exception).
    # ``SchwabAuthError.__str__`` produces a status-keyed prefix; the
    # discriminating signal is that the NEW status (403) replaces the
    # OLD status (401).
    assert "status=403" in (row[2] or "")
    assert "status=401" not in (row[2] or "")
    assert "refresh_token expired" not in (row[2] or "")


# ---------------------------------------------------------------------------
# Test 5 — Mixed state: per-counter discrimination across all buckets
# ---------------------------------------------------------------------------


def test_mixed_state_yields_per_bucket_counters(
    v19_db: sqlite3.Connection,
) -> None:
    """Per plan §E.9 acceptance #5 + #4: mixed state must yield correct
    per-bucket counters AND CLI summary printout per the §E.9 #4 layout.

    Plant:
      - 1 tier-1-eligible unresolved CVGI ``entry_price_mismatch`` (Shape A).
      - 2 unresolved DHC ``unmatched_open_fill`` (will go Pass-2 tier-2).
      - 2 already-pass-2-failed DHC rows (planted in terminal state).
      - 1 already-resolved DHC row (resolved=acknowledged_immaterial).

    Invoke ``--apply`` default (no retry flag) + assert counters per
    plan §E.9 acceptance #5:
      - ``tier1_applied == 1`` (CVGI tier-1 ran).
      - ``tier2_stamped == 2`` (2 unresolved DHC pass-2 tier-2).
      - ``skipped_pass_2_failed == 2`` (2 pass-2-failed rows skipped).
      - ``skipped_already_resolved == 0`` (already-resolved excluded by
        default filter; not counted as skipped UNLESS race-condition path
        fires — not exercised here).
      - Summary printout includes all required lines.
    """
    run_id = _seed_reconciliation_run(v19_db)

    # CVGI tier-1-eligible (entry_price_mismatch Shape A).
    cvgi_seed = _seed_cvgi_trade_and_fill(v19_db)
    _seed_entry_price_mismatch_disc(
        v19_db, run_id=run_id, ticker="CVGI", schwab_price=5.30, **cvgi_seed,
    )

    # 2 unresolved pass-2-required (different tickers per UNIQUE constraint).
    seed_1 = _seed_dhc_trade_and_fill(
        v19_db, ticker="DHC", journal_qty=39.0,
    )
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed_1,
    )
    seed_2 = _seed_dhc_trade_and_fill(
        v19_db, ticker="YOU", journal_qty=39.0,
    )
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="YOU", **seed_2,
    )

    # 2 already-pass-2-failed (different tickers).
    seed_3 = _seed_dhc_trade_and_fill(
        v19_db, ticker="VSAT", journal_qty=39.0,
    )
    _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="VSAT",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason="Pass 2 re-fetch failed: SchwabAuthError: 401",
        **seed_3,
    )
    seed_4 = _seed_dhc_trade_and_fill(
        v19_db, ticker="LAR", journal_qty=39.0,
    )
    _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="LAR",
        resolution="pending_ambiguity_resolution",
        ambiguity_kind="unsupported",
        resolution_reason="Pass 2 re-fetch failed: SchwabRateLimitError: 429",
        **seed_4,
    )

    # 1 already-resolved (different ticker).
    seed_5 = _seed_dhc_trade_and_fill(
        v19_db, ticker="NAT", journal_qty=39.0,
    )
    _seed_unmatched_open_fill_disc(
        v19_db,
        run_id=run_id,
        ticker="NAT",
        resolution="acknowledged_immaterial",
        **seed_5,
    )

    # Pass-2 returns orders summing to journal qty=39 PER ticker
    # (multi_partial). The Pass 2 helper filters by ticker, so we need
    # orders for each of the 2 unresolved tickers (DHC + YOU).
    def _orders_for_ticker(ticker: str) -> list:
        return [
            _make_order(
                order_id=f"100-{ticker}", quantity=20.0,
                instrument_symbol=ticker,
            ),
            _make_order(
                order_id=f"101-{ticker}", quantity=19.0,
                instrument_symbol=ticker,
            ),
        ]

    # The audited wrapper is invoked once per unresolved Pass-2-required
    # row; we return ALL orders + the Pass-2 helper filters by ticker.
    # Build a combined list spanning both DHC + YOU.
    orders = _orders_for_ticker("DHC") + _orders_for_ticker("YOU")

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
            retry_pass_2_failures=False,
        )

    # Per-bucket assertions per plan §E.9 #5.
    assert summary.tier1_applied == 1, (
        f"expected 1 tier-1; got tier1={summary.tier1_applied} "
        f"tier2={summary.tier2_stamped} "
        f"skipped_pass2={summary.skipped_pass_2_failed} "
        f"skipped_resolved={summary.skipped_already_resolved}"
    )
    assert summary.tier2_stamped == 2
    assert summary.skipped_pass_2_failed == 2
    # Already-resolved rows excluded by default filter — not iterated +
    # not counted as "skipped" (the skip counter is for the dynamic
    # SELECT-first race-condition path AND the explicit pass-2-failed
    # enumeration; already-resolved goes through the default filter).
    assert summary.skipped_already_resolved == 0
    assert summary.tier_errored == 0

    # Summary printout — verify all canonical lines present per plan §E.9 #4.
    block = format_summary_block(summary)
    assert "Tier 1 applied: 1" in block
    assert "Tier 2 stamped: 2" in block
    assert "Errored: 0" in block
    assert "Pass 2 failed (persisted as tier-2 unsupported):" in block
    assert "Skipped (already resolved): 0" in block
    assert (
        "Skipped (Pass-2-failed; use --retry-pass-2-failures to retry): 2"
    ) in block
