"""20-A Task A-5 — the fills<->trades consistency invariant (the watchdog).

A recon check that the entry-fill VWAP agrees with ``trades.entry_price``
(tolerance = display precision). Divergence emits a MATERIAL diagnostic that
is NEVER auto-corrected (a shared classify-SKIP at BOTH firing sites -- pivot
+ backfill). Covers ALL trades (open + closed/reviewed) -- the corrector's own
six-week divergence lived on CLOSED trades.

Fixtures = the real PTEN geometry (entry_price 13.00 but the entry FILL carries
the corrupt 12.305) pre-B1, and the corrected fill 13.00 post-B1 (quiet).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import (
    _INTERNAL_CONSISTENCY_FILLS_VS_TRADES,
    _INTERNAL_CONSISTENCY_KEY,
    _is_internal_consistency_diagnostic,
    run_schwab_reconciliation,
)


@dataclass
class _Account:
    net_liquidating_value: float | None = 2000.0
    positions: list | None = None


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "test.db")


def _seed_reviewed_trade(
    conn, *, ticker: str, entry_price: float, fill_price: float, qty: float,
) -> tuple[int, int]:
    """A CLOSED/REVIEWED trade whose entry FILL price may diverge from the
    trades.entry_price (the PTEN/DFTX corruption geometry)."""
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "2026-05-19", entry_price, int(qty), entry_price - 1.0,
         entry_price - 1.0, "reviewed", "manual_off_pipeline",
         "2026-05-19T16:00:00"),
    )
    trade_id = int(cur.lastrowid)
    fcur = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-19T14:00:00", "entry", qty, fill_price,
         "unreconciled"),
    )
    fill_id = int(fcur.lastrowid)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-25T14:00:00", "exit", qty, entry_price + 2.0,
         "unreconciled"),
    )
    conn.commit()
    return trade_id, fill_id


def _run(conn):
    return run_schwab_reconciliation(
        conn, account_hash="<acct>",
        period_start="2026-05-19", period_end="2026-05-25",
        schwab_orders=[], schwab_transactions=[], schwab_account=_Account(),
    )


def _a5_rows(conn, run_id):
    rows = conn.execute(
        "SELECT trade_id, actual_value_json, resolution, material_to_review "
        "FROM reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchall()
    return rows


def test_a5_fires_on_closed_trade_with_divergent_entry_fill(conn) -> None:
    """PTEN pre-B1: entry_price 13.00 but the entry fill carries 12.305 ->
    a MATERIAL fills<->trades diagnostic on a REVIEWED trade."""
    trade_id, _ = _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][0] == trade_id
    payload = json.loads(rows[0][1])
    assert payload[_INTERNAL_CONSISTENCY_KEY] == \
        _INTERNAL_CONSISTENCY_FILLS_VS_TRADES
    assert payload["trades_entry_price"] == 13.00
    assert abs(payload["entry_fill_vwap"] - 12.305) < 1e-9
    # Material.
    assert rows[0][3] == 1


def test_a5_quiet_when_fill_matches_entry_price(conn) -> None:
    """Post-B1: entry fill corrected to 13.00 == entry_price -> no emit."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=13.00, qty=15.0,
    )
    run = _run(conn)
    assert _a5_rows(conn, run.run_id) == []


def test_a5_row_is_never_auto_corrected(conn) -> None:
    """The diagnostic stays `unresolved` after the pivot (classify-skip) — it
    is NEVER routed into the tier-1 path."""
    _seed_reviewed_trade(
        conn, ticker="DFTX", entry_price=24.53, fill_price=22.16, qty=7.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    assert rows[0][2] == "unresolved"  # not auto_corrected / stamped


def test_a5_backfill_skips_the_diagnostic(conn) -> None:
    """The backfill firing site ALSO skips the diagnostic (shared predicate):
    it stays unresolved after run_backfill."""
    _seed_reviewed_trade(
        conn, ticker="DFTX", entry_price=24.53, fill_price=22.16, qty=7.0,
    )
    run = _run(conn)
    rows = _a5_rows(conn, run.run_id)
    assert len(rows) == 1
    from swing.trades.reconciliation_backfill import run_backfill
    run_backfill(
        conn, dry_run=False, schwab_client=None, environment="production",
        account_hash=None,
    )
    resolution = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE field_name = ?", (_INTERNAL_CONSISTENCY_KEY,),
    ).fetchone()[0]
    assert resolution == "unresolved"


def test_a5_render_consumers_are_sane_on_the_variant(conn) -> None:
    """Consumer audit (D-A4 condition 2): the EXISTING entry_price_mismatch
    render consumers (reconciliation_render + the reconcile pre-resolution VM)
    do NOT crash on the internal-consistency variant and show the divergence."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    rows = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM "
        "reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()
    expected = json.loads(rows[0])
    actual = json.loads(rows[1])
    from swing.trades.reconciliation_render import _pairs_entry_price_mismatch
    pairs = _pairs_entry_price_mismatch(expected, actual)
    # Renders the divergence (trades 13.00 vs fill VWAP 12.305) — no crash.
    assert ("entry price", 13.00, 12.305) in pairs


def test_skip_predicate_discriminates() -> None:
    """The shared predicate matches the marker and rejects a plain payload."""
    @dataclass
    class _D:
        actual_value_json: str | None

    assert _is_internal_consistency_diagnostic(
        _D(json.dumps({_INTERNAL_CONSISTENCY_KEY:
                       _INTERNAL_CONSISTENCY_FILLS_VS_TRADES}))
    )
    assert not _is_internal_consistency_diagnostic(_D(json.dumps({"price": 5.0})))
    assert not _is_internal_consistency_diagnostic(_D(None))


# ===========================================================================
# Item-5 A-4 -- the dedicated `fills_trades_price_divergence` type.
#
# Every test above this line stayed GREEN when the emit changed type, because
# they call the pair BUILDER directly and never assert the emitted
# `discrepancy_type`. So these are DISPATCH-level: a graceful default is
# exactly what makes a broken dispatch invisible.
# ===========================================================================

A4_TYPE = "fills_trades_price_divergence"


def test_a4_the_emitter_writes_the_dedicated_type(conn) -> None:
    """D1's own regression -- nothing asserted the emitted type before."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    row = conn.execute(
        "SELECT discrepancy_type, field_name, material_to_review FROM "
        "reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()
    assert row[0] == A4_TYPE
    assert row[1] == _INTERNAL_CONSISTENCY_KEY
    # RD 2026-08-09: a change of CATEGORY must never smuggle a change of
    # SEVERITY. The row was material as an `entry_price_mismatch`; it stays
    # material as its own type.
    assert row[2] == 1


def test_a4_the_emitter_still_writes_the_discriminator(conn) -> None:
    """The type is NEW; the discriminator is KEPT. One predicate has to cover
    both the historical `entry_price_mismatch` rows and the new-typed ones."""
    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    actual = json.loads(conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()[0])
    assert actual[_INTERNAL_CONSISTENCY_KEY] == (
        _INTERNAL_CONSISTENCY_FILLS_VS_TRADES
    )


def test_a4_the_cli_render_dispatch_resolves_to_its_own_builder(conn) -> None:
    """D4 dispatch. `build_compared_pairs` returns None for an unknown type
    (graceful degradation), so a missing _PAIRS_BUILDERS key would look like a
    quiet display regression rather than a failure."""
    from swing.trades.reconciliation_render import build_compared_pairs

    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    row = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM "
        "reconciliation_discrepancies WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()
    pairs = build_compared_pairs(
        A4_TYPE, json.loads(row[0]), json.loads(row[1]),
    )
    assert pairs is not None, "dispatch fell through to the None default"
    labels = [p[0] for p in pairs]
    assert "entry price (trades vs entry-fill VWAP)" in labels
    assert (
        "entry price (trades vs entry-fill VWAP)", 13.00, 12.305,
    ) in pairs


def test_a4_the_web_vm_dispatch_is_not_the_generic_fallback(conn) -> None:
    """D5 dispatch. `_render_generic_fallback` renders SOMETHING for any
    unknown type, so the failure mode here is a vaguer page, not an error."""
    from swing.data.repos.reconciliation import get_discrepancy
    from swing.web.view_models.reconcile import (
        _RENDER_HELPERS_BY_DISCREPANCY_TYPE,
        _render_generic_fallback,
        _render_pre_resolution_context,
    )

    helper = _RENDER_HELPERS_BY_DISCREPANCY_TYPE.get(A4_TYPE)
    assert helper is not None
    assert helper is not _render_generic_fallback

    _seed_reviewed_trade(
        conn, ticker="PTEN", entry_price=13.00, fill_price=12.305, qty=15.0,
    )
    run = _run(conn)
    disc_id = conn.execute(
        "SELECT discrepancy_id FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND field_name = ?",
        (run.run_id, _INTERNAL_CONSISTENCY_KEY),
    ).fetchone()[0]
    ctx = _render_pre_resolution_context(get_discrepancy(conn, disc_id))
    assert ctx.journal_side_label == "trades.entry_price"
    assert ctx.schwab_side_label == "Entry-fill VWAP (journal fills)"
    assert "13.00" in ctx.journal_side_value
    assert "12.30" in ctx.schwab_side_value


def test_a4_a_legacy_typed_row_is_STILL_skipped_at_the_pivot(conn) -> None:
    """The predicate keys on the DISCRIMINATOR, not the type, and this is the
    test that proves it must.

    A row planted with the PRE-0035 shape -- `entry_price_mismatch` plus the
    discriminator -- via RAW conn.execute (the historical-data technique; the
    production emitter can no longer produce this shape). Re-keying the
    predicate on the OLD TYPE would pass this test while letting every
    NEW-typed row into classification, so the sibling test below is what makes
    the pair discriminating.
    """
    _plant_raw_diagnostic(conn, discrepancy_type="entry_price_mismatch")
    _run(conn)
    _assert_untouched_diagnostic(conn, "entry_price_mismatch")


def test_a4_a_new_typed_row_is_skipped_at_the_pivot(conn) -> None:
    _plant_raw_diagnostic(conn, discrepancy_type=A4_TYPE)
    _run(conn)
    _assert_untouched_diagnostic(conn, A4_TYPE)


def _plant_raw_diagnostic(conn, *, discrepancy_type: str) -> int:
    """Plant a fills<->trades diagnostic with a chosen TYPE and the
    discriminator, by RAW insert. Returns the discrepancy_id."""
    trade_id, fill_id = _seed_reviewed_trade(
        conn, ticker="DFTX", entry_price=9.00, fill_price=8.25, qty=10.0,
    )
    rcur = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('schwab_api', '2026-08-08T00:00:00', 'completed')",
    )
    run_id = int(rcur.lastrowid)
    dcur = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, created_at) "
        "VALUES (?, ?, ?, 'DFTX', ?, ?, ?, 1, 'unresolved', "
        "'2026-08-08T00:00:00')",
        (
            run_id, discrepancy_type, trade_id, _INTERNAL_CONSISTENCY_KEY,
            json.dumps({"price": 9.0, "trades_entry_price": 9.0}),
            json.dumps({
                _INTERNAL_CONSISTENCY_KEY: (
                    _INTERNAL_CONSISTENCY_FILLS_VS_TRADES
                ),
                "price": 8.25,
                "entry_fill_vwap": 8.25,
                "trades_entry_price": 9.0,
                "entry_fill_ids": [fill_id],
            }, sort_keys=True),
        ),
    )
    conn.commit()
    return int(dcur.lastrowid)


def _assert_untouched_diagnostic(conn, discrepancy_type: str) -> None:
    rows = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_type = ? AND field_name = ?",
        (discrepancy_type, _INTERNAL_CONSISTENCY_KEY),
    ).fetchall()
    assert rows, f"no {discrepancy_type} diagnostic row survived"
    for (resolution,) in rows:
        assert resolution == "unresolved", (
            f"{discrepancy_type} diagnostic was classified/dispositioned "
            f"(resolution={resolution!r}) -- the classify-SKIP did not fire"
        )
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_a4_both_representations_are_skipped_at_the_BACKFILL(conn) -> None:
    """The backfill is the SECOND firing site and imports the same predicate.
    A legacy-only test here is satisfiable by the wrong implementation."""
    from swing.trades.reconciliation_backfill import run_backfill

    legacy_id = _plant_raw_diagnostic(
        conn, discrepancy_type="entry_price_mismatch",
    )
    new_id = _plant_raw_diagnostic(conn, discrepancy_type=A4_TYPE)
    summary = run_backfill(
        conn, dry_run=True, schwab_client=None, environment='production',
        account_hash=None,
    )
    outcomes = {
        o.discrepancy_id: o.outcome
        for o in summary.per_discrepancy_outcomes
    }
    assert outcomes.get(legacy_id) == "skipped_internal_consistency"
    assert outcomes.get(new_id) == "skipped_internal_consistency"
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
