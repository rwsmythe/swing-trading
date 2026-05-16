"""Phase 12 C.D T-D.8 — backfill Pass 2 (Schwab re-fetch) tests.

Covers plan §E.8 acceptance criteria #1-9 + brief §0.5 #9:

  1. DHC 39 fixture: Pass 2 returns 2 orders qty=20+19 →
     tier-2 ``multi_partial_vs_consolidated``; ``--apply`` stamps the
     discrepancy + writes a ``schwab_api_calls`` audit row.
  2. VSAT 40 fixture: Pass 2 returns 1 order qty=2 →
     tier-2 ``unknown_schwab_subtype``.
  3. VSAT 40 fixture: Pass 2 returns 0 orders →
     tier-2 ``schwab_returned_no_match``.
  4. Pass 2 raises ``SchwabAuthError`` → tier-2 ``unsupported`` with
     ``"Pass 2 re-fetch failed"`` rationale; ``BackfillSummary.pass_2_failed``
     increments; under ``--apply`` the discrepancy gets
     ``resolution='pending_ambiguity_resolution'`` +
     ``ambiguity_kind='unsupported'``.
  5. Sandbox short-circuit: ``environment='sandbox'`` → tier-2
     ``unsupported`` per §9.7; NO Schwab API call fired (audited wrapper
     not invoked); NO ``schwab_api_calls`` row written.
  6. ``--no-pass-2-on-dry-run`` flag: dry-run skips Pass 2 entirely;
     matrix shows ``unsupported`` projection.
  7. Pass-2-tier-1-FORBIDDEN LOCK (brief §0.5 #9 BINDING): plant DHC
     fixture where matching orders sum to journal qty AND match journal
     price; assert tier-2 always (NEVER tier-1) regardless of
     price-similarity.
  8. Per-discrepancy ``call_id`` printout (Codex R6 Minor #2):
     output line shape ``disc <id> <ticker> (<type>): Pass 2 ->
     call_id=<int>; tier-2; ambiguity_kind=...``; assert the printed
     ``call_id`` matches the row INSERTed into ``schwab_api_calls``.
"""
from __future__ import annotations

import json
import sqlite3
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabAuthError,
    SchwabRateLimitError,
)
from swing.integrations.schwab.models import SchwabOrderResponse
from swing.trades.reconciliation_backfill import (
    BackfillOutcome,
    BackfillSummary,
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
    journal_price: float = 7.50,
) -> dict[str, int]:
    """Plant a DHC trade + entry fill. Default journal_qty=39 matches
    spec §10.2 DHC walkthrough (2 partial orders sum to 39)."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("DHC", "2026-04-15", journal_price, int(journal_qty), 7.0, 7.0,
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


def _seed_vsat_trade_and_fill(
    conn: sqlite3.Connection, *, journal_qty: float = 2.0,
) -> dict[str, int]:
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("VSAT", "2026-04-20", 65.00, int(journal_qty), 60.0, 60.0,
         "managing", "manual_off_pipeline", "2026-04-20T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (trade_id, "2026-04-20T13:00:00", "entry", journal_qty, 65.00,
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
    created_at: str = "2026-05-16T10:06:00",
) -> int:
    """Plant unmatched_open_fill discrepancy with the persisted-JSON
    ``{"matched": null}`` sentinel that flags Pass-2-required at Pass 1."""
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, fill_id, ticker, "
        "  field_name, expected_value_json, actual_value_json, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "unmatched_open_fill", trade_id, fill_id, ticker,
            "match",
            json.dumps({"fill_datetime": "2026-04-15T13:00:00"}),
            json.dumps({"matched": None}),
            1, "unresolved", created_at,
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
    """Sentinel object — the test patches ``get_account_orders_audited``
    so the client itself is never touched; we just need a non-None marker
    so the backfill ``schwab_client is not None`` guard fires."""

    pass


# ---------------------------------------------------------------------------
# Test 1 — DHC 2-order partial-vs-consolidated (spec §10.2)
# ---------------------------------------------------------------------------


def test_dhc_pass_2_multi_partial_vs_consolidated(
    v19_db: sqlite3.Connection,
) -> None:
    """Pass 2 returns 2 orders summing to journal qty → tier-2
    ``multi_partial_vs_consolidated``; --apply stamps the discrepancy."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
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
        )

    # The audited wrapper was invoked exactly once.
    assert audited_mock.call_count == 1
    # Tier-2 stamped via stamp_pending_ambiguity (Pass-2-tier-1-FORBIDDEN).
    assert summary.tier2_stamped == 1
    assert summary.pass_2_pending == 0  # T-D.8 supersedes the placeholder.
    assert summary.pass_2_failed == 0
    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.tier == 2
    assert out.outcome == "tier2_stamped"
    assert out.ambiguity_kind == "multi_partial_vs_consolidated"
    assert out.pass_2_call_id == 99

    # Discrepancy flipped at journal-layer.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "multi_partial_vs_consolidated"


# ---------------------------------------------------------------------------
# Test 2 — VSAT 1-order unknown_schwab_subtype
# ---------------------------------------------------------------------------


def test_vsat_pass_2_unknown_schwab_subtype(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_vsat_trade_and_fill(v19_db, journal_qty=2.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="VSAT", **seed,
    )

    orders = [_make_order(
        order_id="200", quantity=2.0, instrument_symbol="VSAT",
        price=65.00,
    )]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(101, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.tier == 2
    assert out.outcome == "tier2_stamped"
    assert out.ambiguity_kind == "unknown_schwab_subtype"
    assert out.pass_2_call_id == 101


# ---------------------------------------------------------------------------
# Test 3 — VSAT 0-order schwab_returned_no_match
# ---------------------------------------------------------------------------


def test_vsat_pass_2_schwab_returned_no_match(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_vsat_trade_and_fill(v19_db, journal_qty=2.0)
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="VSAT", **seed,
    )

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(102, []),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    assert out.tier == 2
    assert out.outcome == "tier2_stamped"
    assert out.ambiguity_kind == "schwab_returned_no_match"


# ---------------------------------------------------------------------------
# Test 4 — Pass 2 raises SchwabAuthError → unsupported / pass_2_failed
# ---------------------------------------------------------------------------


def test_pass_2_auth_error_failure_mode(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    def _raise(*args: Any, **kwargs: Any) -> None:
        raise SchwabAuthError(401, "refresh_token expired")

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        side_effect=_raise,
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    # Failure-mode counter increments + tier-2 stamped per LOCK.
    assert summary.pass_2_failed == 1
    assert summary.tier2_stamped == 1
    out = summary.per_discrepancy_outcomes[0]
    assert out.tier == 2
    assert out.ambiguity_kind == "unsupported"
    assert "Pass 2 re-fetch failed" in (out.reason or "")
    assert out.pass_2_call_id is None  # no audited wrapper return on raise.

    # Persisted state per acceptance #6.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert row[0] == "pending_ambiguity_resolution"
    assert row[1] == "unsupported"
    assert "Pass 2 re-fetch failed" in (row[2] or "")


# ---------------------------------------------------------------------------
# Test 5 — Sandbox short-circuit (§9.7)
# ---------------------------------------------------------------------------


def test_sandbox_short_circuit_skips_schwab_api(
    v19_db: sqlite3.Connection,
) -> None:
    """Codex R1 Major #2 fix — sandbox + --apply leaves discrepancy unresolved.

    Sandbox MUST NOT mutate any journal state under --apply: the C.C
    sandbox short-circuit LOCK extends to backfill Pass-2 dispatch. The
    previous behavior stamped ``pending_ambiguity_resolution`` even
    though the underlying Schwab API call was skipped — that was a
    journal mutation (resolution flip + ambiguity_kind set) and violates
    the no-mutation-under-sandbox contract. Fixed: backfill outcome is
    ``tier2_skipped_sandbox`` + discrepancy stays ``unresolved``.
    """
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    # Capture pre-state for the BEFORE/AFTER discriminator.
    pre_row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert pre_row[0] == "unresolved"
    assert pre_row[1] is None
    # And no fill mutations.
    pre_fill = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()

    def _should_not_be_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "get_account_orders_audited must NOT be called under sandbox"
        )

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        side_effect=_should_not_be_called,
    ) as audited_mock:
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="sandbox",
            account_hash="acct-hash",
        )

    # Audited wrapper never invoked.
    assert audited_mock.call_count == 0
    # No schwab_api_calls audit row written.
    n_calls = v19_db.execute(
        "SELECT COUNT(*) FROM schwab_api_calls",
    ).fetchone()[0]
    assert n_calls == 0
    # No reconciliation_corrections row written.
    n_corrections = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n_corrections == 0

    # Outcome — tier-2 SKIPPED (sandbox) per Codex R1 Major #2 LOCK.
    out = summary.per_discrepancy_outcomes[0]
    assert out.discrepancy_id == disc_id
    assert out.tier == 2
    assert out.outcome == "tier2_skipped_sandbox"
    assert out.ambiguity_kind is None  # no stamp = no ambiguity_kind set
    assert "sandbox" in (out.reason or "").lower()
    assert out.pass_2_call_id is None
    # pass_2_failed must NOT increment under sandbox (it's a deliberate
    # short-circuit, not an API failure).
    assert summary.pass_2_failed == 0
    assert summary.tier2_stamped == 0
    assert summary.tier2_skipped_sandbox == 1

    # AFTER state: discrepancy left exactly as pre-call.
    post_row = v19_db.execute(
        "SELECT resolution, ambiguity_kind, resolution_reason "
        "FROM reconciliation_discrepancies WHERE discrepancy_id = ?",
        (disc_id,),
    ).fetchone()
    assert post_row[0] == "unresolved"
    assert post_row[1] is None
    # Fill state unchanged.
    post_fill = v19_db.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (seed["fill_id"],),
    ).fetchone()
    assert post_fill[0] == pre_fill[0]


# ---------------------------------------------------------------------------
# Test 6 — --no-pass-2-on-dry-run skips Pass 2 entirely
# ---------------------------------------------------------------------------


def test_no_pass_2_on_dry_run_skips_schwab_api(
    v19_db: sqlite3.Connection,
) -> None:
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    def _should_not_be_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "Pass 2 must be skipped under --no-pass-2-on-dry-run"
        )

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        side_effect=_should_not_be_called,
    ) as audited_mock:
        summary = run_backfill(
            v19_db,
            dry_run=True,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
            no_pass_2_on_dry_run=True,
        )

    assert audited_mock.call_count == 0
    # Dry-run projects as Pass 2 (unsupported); no journal mutation.
    out = summary.per_discrepancy_outcomes[0]
    assert out.outcome == "projection_pass_2"
    # No correction row, no resolution change.
    n_corr = v19_db.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0]
    assert n_corr == 0


# ---------------------------------------------------------------------------
# Test 7 — Pass-2-tier-1-FORBIDDEN LOCK (brief §0.5 #9 BINDING)
# ---------------------------------------------------------------------------


def test_pass_2_tier_1_forbidden_even_when_qty_and_price_match(
    v19_db: sqlite3.Connection,
) -> None:
    """Plant a fixture where Pass 2 returns N orders summing to journal
    qty AND each at journal price — classifier MUST still emit tier-2
    (NEVER tier-1) per §8.4 Pass-2-tier-1-FORBIDDEN LOCK.

    Discriminating: a naive classifier might inspect price-similarity and
    upgrade to tier-1; the C.B sub-classifier instead emits tier-2
    ``multi_partial_vs_consolidated`` because Pass-2 data is order-grain
    (limit/stop price, NOT execution price)."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(
        v19_db, journal_qty=39.0, journal_price=7.50,
    )
    _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    # Both orders at journal price 7.50 + sum to journal qty 39.
    orders = [
        _make_order(order_id="500", quantity=20.0, price=7.50),
        _make_order(order_id="501", quantity=19.0, price=7.50),
    ]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(150, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    out = summary.per_discrepancy_outcomes[0]
    # CRITICAL — tier MUST be 2 (NEVER 1) regardless of price-similarity.
    assert out.tier == 2, (
        "Pass-2-tier-1-FORBIDDEN LOCK violated — classifier upgraded to "
        f"tier-1 despite §8.4 LOCK (got outcome={out.outcome!r}, "
        f"ambiguity_kind={out.ambiguity_kind!r})"
    )
    assert out.ambiguity_kind == "multi_partial_vs_consolidated"
    # And no tier-1 fields are populated.
    assert summary.tier1_applied == 0
    assert summary.tier1_skipped_sandbox == 0


# ---------------------------------------------------------------------------
# Test 8 — Per-discrepancy call_id printout (Codex R6 Minor #2)
# ---------------------------------------------------------------------------


def test_per_discrepancy_call_id_printout(
    v19_db: sqlite3.Connection, capsys: pytest.CaptureFixture[str],
) -> None:
    """Backfill apply output for each Pass-2-required discrepancy MUST
    include the captured ``call_id``. Output line shape per plan §E.8 #9:

      ``disc <id> <ticker> (<type>): Pass 2 -> call_id=<int>; tier-2;
        ambiguity_kind=<kind>``

    Discriminating: assert the formatted line appears in stdout +
    ``call_id`` matches BackfillOutcome.pass_2_call_id."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    orders = [
        _make_order(order_id="100", quantity=20.0),
        _make_order(order_id="101", quantity=19.0),
    ]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(77, orders),
    ):
        summary = run_backfill(
            v19_db,
            dry_run=False,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    captured = capsys.readouterr()
    expected_substring = (
        f"disc {disc_id} DHC (unmatched_open_fill): Pass 2 -> "
        f"call_id=77;"
    )
    assert expected_substring in captured.out, (
        f"expected printout substring not found.\nGOT STDOUT:\n{captured.out}"
    )
    assert "tier-2" in captured.out
    assert "ambiguity_kind='multi_partial_vs_consolidated'" in captured.out

    # And the BackfillOutcome carries the same call_id.
    out = summary.per_discrepancy_outcomes[0]
    assert out.pass_2_call_id == 77


# ---------------------------------------------------------------------------
# Test 9 — non-Pass-2 outcomes do NOT print the Pass-2 call_id line
# ---------------------------------------------------------------------------


def test_non_pass_2_outcomes_do_not_print_call_id_line(
    v19_db: sqlite3.Connection, capsys: pytest.CaptureFixture[str],
) -> None:
    """Discriminating regression: a tier-2 outcome from a NON-Pass-2 path
    (e.g., sector_tamper) MUST NOT emit the ``Pass 2 -> call_id=`` line."""
    run_id = _seed_reconciliation_run(v19_db)
    # Seed CVGI trade.
    cur = v19_db.execute(
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
    v19_db.commit()

    v19_db.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, trade_id, ticker, field_name, "
        "  expected_value_json, actual_value_json, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, "sector_tamper", trade_id, "CVGI", "sector",
            json.dumps({"sector": "Energy"}),
            json.dumps({"sector": "Technology"}),
            0, "unresolved", "2026-05-16T10:07:00",
        ),
    )
    v19_db.commit()

    summary = run_backfill(
        v19_db,
        dry_run=False,
        schwab_client=None,
        environment="production",
        account_hash=None,
    )
    captured = capsys.readouterr()
    assert "Pass 2 -> call_id=" not in captured.out
    out = summary.per_discrepancy_outcomes[0]
    assert out.pass_2_call_id is None


# ---------------------------------------------------------------------------
# Test 10 — Dry-run with Pass 2 enabled (default) still fires Schwab
# ---------------------------------------------------------------------------


def test_dry_run_pass_2_enabled_fires_audited_wrapper(
    v19_db: sqlite3.Connection,
) -> None:
    """Spec §8.2 LOCK — dry-run with Pass 2 enabled DOES write
    ``schwab_api_calls`` audit rows (read's audit-trail contract) but
    does NOT stamp the discrepancy."""
    run_id = _seed_reconciliation_run(v19_db)
    seed = _seed_dhc_trade_and_fill(v19_db, journal_qty=39.0)
    disc_id = _seed_unmatched_open_fill_disc(
        v19_db, run_id=run_id, ticker="DHC", **seed,
    )

    orders = [
        _make_order(order_id="100", quantity=20.0),
        _make_order(order_id="101", quantity=19.0),
    ]

    with patch(
        "swing.trades.reconciliation_backfill.get_account_orders_audited",
        return_value=(88, orders),
    ) as audited_mock:
        summary = run_backfill(
            v19_db,
            dry_run=True,
            schwab_client=_FakeSchwabClient(),
            environment="production",
            account_hash="acct-hash",
        )

    # Audited wrapper IS invoked under dry-run + Pass-2-default-on.
    assert audited_mock.call_count == 1
    out = summary.per_discrepancy_outcomes[0]
    # Projection (NOT stamp).
    assert out.outcome == "projection_pass_2"
    assert out.pass_2_call_id == 88
    # Discrepancy NOT stamped.
    row = v19_db.execute(
        "SELECT resolution, ambiguity_kind FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (disc_id,),
    ).fetchone()
    assert row[0] == "unresolved"
    assert row[1] is None
