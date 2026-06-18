"""equity_delta limbo-routing fix — the 18-H.6.1 pivot-skip pattern.

A fired ``equity_delta`` (an account-level ledger-vs-NLV coherence
discrepancy) used to flow the reconciliation classify/dispatch pivot,
get classified tier-2 (``_classify_equity_delta`` -> ``field_shape_incompatible``),
and the pivot's else-branch stamped it ``pending_ambiguity_resolution`` (the
tier-2 fill-matching limbo — the WRONG state: an ``equity_delta`` is not a
broker-vs-journal fill RECORD to disposition, and that limbo is uncleanable
via the legitimate operator surfaces). The live witness is run-59 id 71.

The fix (CHARC settled, the 18-H.6.1 twin): widen the pivot's existing
``untracked_broker_position`` skip-set to also skip ``equity_delta`` so a
fired ``equity_delta`` stays ``unresolved`` — a real unaddressed coherence
finding that is run-level-counted + CLI-clearable via the existing manual
resolver (``resolve_discrepancy`` -> ``acknowledged_immaterial``).

CHARC Sec-0 RULING = (A): cleanability. ``equity_delta`` has been
``MATERIAL_BY_TYPE=0`` since Phase 9 -> the material-banner EXCLUSION is
correct-by-design (test (b)(iii) is a SCOPE LOCK, not the distinguisher).
NO ``MATERIAL_BY_TYPE`` change; the arc stays the single-line pivot skip.

Fixtures are built from the REAL emitter path (``run_schwab_reconciliation``
for the firing fixtures; a focused direct ``_pivot_classify_and_dispatch_for_run``
call for the C1 lock; a raw-insert for the C3 legacy-limbo seed).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.reconciliation import (
    get_discrepancy,
    list_discrepancies_for_run,
)
from swing.metrics.discrepancies import count_unresolved_material
from swing.trades.reconciliation import resolve_discrepancy
from swing.trades.schwab_reconciliation import (
    _pivot_classify_and_dispatch_for_run,
    run_schwab_reconciliation,
)

_SWING_BASIS = "net_liq_minus_declared_oof"


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


def _position(
    symbol: str,
    *,
    long_qty: float = 0.0,
    market_value: float | None = None,
) -> dict:
    """The REAL Schwab position dict (sibling top-level ``marketValue``)."""
    return {
        "shortQuantity": 0.0,
        "longQuantity": long_qty,
        "instrument": {"symbol": symbol, "type": "EQUITY"},
        "marketValue": market_value,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "equity_delta_limbo.db")


def _run(
    conn: sqlite3.Connection,
    positions: list[dict],
    *,
    nlv: float | None,
    starting_equity: float = 1000.0,
    out_of_framework: tuple[str, ...] = (),
):
    acct = _SchwabAccount(net_liquidating_value=nlv, positions=positions)
    return run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-15",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=acct,
        out_of_framework_tickers=out_of_framework,
        starting_equity=starting_equity,
    )


def _equity_delta_rows(conn: sqlite3.Connection, run_id: int):
    return [
        d
        for d in list_discrepancies_for_run(conn, run_id)
        if d.discrepancy_type == "equity_delta"
    ]


# --------------------------------------------------------------------------- #
# Test (a) — the LOAD-BEARING distinguisher: a fired SWING-SCOPED equity_delta
# (the id-71 path) stays `unresolved`, not `pending_ambiguity_resolution`.
# --------------------------------------------------------------------------- #


def test_fired_swing_scoped_equity_delta_stays_unresolved_not_pending_ambiguity(
    conn: sqlite3.Connection,
):
    """Test (a) — REQUIRED swing-scoped fixture (the live id-71 path).

    nlv = 392.51 (declared SPCX mv) + 1500.00; swing_nlv = 1500.00;
    ledger = starting 1000.00; |1000 - 1500| = 500.00;
    tol = max(5, 0.5%*1500) = 7.50; 500 > 7.50 -> FIRES on the swing basis.

    Pre-fix arithmetic: the pivot calls classify_discrepancy(equity_delta) ->
    _classify_equity_delta -> tier=2, field_shape_incompatible -> the
    else-branch stamps `pending_ambiguity_resolution`. Assertion (2) would
    FAIL (resolution == 'pending_ambiguity_resolution').
    Post-fix arithmetic: the widened skip-set `continue`s past the
    equity_delta -> it stays `unresolved`. Assertion (2) PASSES. Distinguishes.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=392.51)],
        nlv=1892.51,
        starting_equity=1000.00,
        out_of_framework=("SPCX",),
    )
    rows = _equity_delta_rows(conn, run.run_id)
    # (1) exactly one equity_delta fired AND it is the SWING-SCOPED basis
    # (proves the §2.4 path, not the legacy both-flat basis / a C2-degrade).
    assert len(rows) == 1
    import json

    actual = json.loads(rows[0].actual_value_json)
    assert actual["basis"] == _SWING_BASIS
    # (2) post-fix: it stays unresolved (NOT pending_ambiguity_resolution).
    assert rows[0].resolution == "unresolved"


def test_fired_legacy_both_flat_equity_delta_stays_unresolved(
    conn: sqlite3.Connection,
):
    """Test (1b) — the legacy both-flat firing basis also routes to unresolved.

    nlv = 1100.00; ledger = 1000.00; |1000 - 1100| = 100;
    tol = max(5, 0.5%*1100=5.5) = 5.5; 100 > 5.5 -> FIRES on basis 'net_liq'.

    Same pre/post distinguisher as test (a): pre-fix stamped
    `pending_ambiguity_resolution`; post-fix stays `unresolved`. Proves BOTH
    firing bases route to `unresolved` post-fix (the pivot dispatches on
    discrepancy_type, not basis — but this pins both rather than assuming).
    """
    run = _run(conn, [], nlv=1100.00, starting_equity=1000.00)
    rows = _equity_delta_rows(conn, run.run_id)
    assert len(rows) == 1
    import json

    actual = json.loads(rows[0].actual_value_json)
    assert actual["basis"] == "net_liq"
    assert rows[0].resolution == "unresolved"


# --------------------------------------------------------------------------- #
# Test (b) — the unresolved equity_delta is run-level-counted + CLI-clearable;
# (iii) the material-banner exclusion is correct-by-design (a SCOPE LOCK).
# --------------------------------------------------------------------------- #


def test_fired_equity_delta_counts_in_run_unresolved_count_and_clearable(
    conn: sqlite3.Connection,
):
    """Test (b) — C2 satisfied by the run-level count + the clearable path.

    Reuses the swing-scoped fixture (test (a)).
    (i)   run.unresolved_discrepancies_count includes the equity_delta.
          Pre-fix: stamped pending_ambiguity_resolution -> the post-pivot
          recompute (COUNT WHERE resolution='unresolved') excludes it -> 0.
          Post-fix: stays unresolved -> the recompute counts it -> 1.
          Distinguishes.
    (ii)  resolve_discrepancy(... acknowledged_immaterial) clears it.
    (iii) SCOPE LOCK (CHARC Sec-0 = A): the fired equity_delta is ABSENT from
          count_unresolved_material because material_to_review=0 since Phase 9.
          This is correct-by-design — NOT a missing feature, NOT the pre/post
          distinguisher (it does not change pre-vs-post; it locks scope).
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=392.51)],
        nlv=1892.51,
        starting_equity=1000.00,
        out_of_framework=("SPCX",),
    )
    rows = _equity_delta_rows(conn, run.run_id)
    assert len(rows) == 1
    disc = rows[0]

    # (i) run-level unresolved count includes the equity_delta.
    assert run.unresolved_discrepancies_count == 1

    # (iii) SCOPE LOCK — material-banner exclusion correct-by-design (material=0).
    assert disc.material_to_review == 0
    assert count_unresolved_material(conn) == 0

    # (ii) CLI-clearable via the existing manual resolver.
    resolve_discrepancy(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution="acknowledged_immaterial",
        resolution_reason="acknowledged coherence drift",
    )
    assert (
        get_discrepancy(conn, disc.discrepancy_id).resolution
        == "acknowledged_immaterial"
    )


# --------------------------------------------------------------------------- #
# Test (c) — C1 LOCK: an unrelated sub-classified type still flows the FULL
# savepoint+classify+dispatch path + reaches its REAL non-vacuous disposition.
# --------------------------------------------------------------------------- #


def _seed_trade(conn: sqlite3.Connection, *, ticker: str) -> int:
    cur = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES (?, '2026-04-27', 10.0, 100, 9.0, 9.0, 'managing', "
        "'manual_off_pipeline', '2026-04-27T16:00:00')",
        (ticker,),
    )
    return int(cur.lastrowid)


def _raw_insert_stop_mismatch(
    conn: sqlite3.Connection, *, run_id: int, trade_id: int, ticker: str
) -> int:
    """Raw-insert an unresolved stop_mismatch (actual_value_json NULL) so the
    pivot's _extract_source_payload yields None -> _classify_stop_mismatch
    returns tier-2 schwab_returned_no_match (a REAL, deterministic, non-vacuous,
    NON-`unsupported` disposition)."""
    return int(
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, trade_id, ticker, field_name, "
            "material_to_review, resolution, created_at"
            ") VALUES (?, 'stop_mismatch', ?, ?, 'current_stop', 1, "
            "'unresolved', '2026-06-15T09:00:00')",
            (run_id, trade_id, ticker),
        ).lastrowid
    )


def test_unrelated_sub_classified_type_still_dispatches_post_skip(
    conn: sqlite3.Connection,
):
    """Test (c) — the C1 lock (NO vacuous-pass escape hatch).

    A stop_mismatch (sub-classified by _classify_stop_mismatch) with no
    matching Schwab order (schwab_orders=[]) flows the FULL pivot path and
    reaches its REAL tier-2 disposition: resolution ==
    'pending_ambiguity_resolution' with ambiguity_kind == 'schwab_returned_no_match'
    (NOT 'unsupported', NOT skipped — proving the sub-classifier actually ran).

    Pre==post (the LOCK): the skip-set never matched stop_mismatch; widening it
    to add equity_delta cannot touch the stop_mismatch dispatch path. The
    asserted disposition is identical under both the pre-edit and post-edit
    pivot — that identity, with the non-vacuity assertion, IS the C1 lock.
    """
    from swing.data.repos.reconciliation import insert_run

    trade_id = _seed_trade(conn, ticker="ABC")
    run_id = insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-06-15T09:00:00.000",
        state="running",
    )
    did = _raw_insert_stop_mismatch(
        conn, run_id=run_id, trade_id=trade_id, ticker="ABC"
    )
    conn.commit()

    counters: dict[str, int] = {}
    with conn:
        _pivot_classify_and_dispatch_for_run(
            conn,
            run_id=run_id,
            schwab_orders=[],
            schwab_api_call_id=None,
            environment="production",
            counters=counters,
        )

    disc = get_discrepancy(conn, did)
    # Non-vacuity: it reached the sub-classifier's REAL tier-2 outcome.
    assert disc.resolution == "pending_ambiguity_resolution"
    assert disc.ambiguity_kind == "schwab_returned_no_match"
    assert counters.get("tier2_pending_count", 0) == 1


# --------------------------------------------------------------------------- #
# Test (d) — C3 (test-only, NO resolver code): a raw-inserted legacy-limbo
# equity_delta (id-71 shape) is clearable by the EXISTING resolver.
# --------------------------------------------------------------------------- #


def _raw_insert_pending_ambiguity_equity_delta(
    conn: sqlite3.Connection, *, run_id: int
) -> int:
    """Plant an equity_delta in the LEGACY pending_ambiguity_resolution state
    (the id-71 shape: ambiguity_kind='field_shape_incompatible'). RAW insert is
    mandatory — the cross-column CHECK requires ambiguity_kind IS NOT NULL for
    this resolution, AND the manual resolver REJECTS setting
    pending_ambiguity_resolution, so it cannot be planted via any write-path
    (the cross-arc write-barrier lesson)."""
    return int(
        conn.execute(
            "INSERT INTO reconciliation_discrepancies ("
            "run_id, discrepancy_type, trade_id, fill_id, cash_movement_id, "
            "ticker, field_name, expected_value_json, actual_value_json, "
            "delta_text, material_to_review, resolution, ambiguity_kind, "
            "resolution_reason, created_at"
            ") VALUES (?, 'equity_delta', NULL, NULL, NULL, NULL, "
            "'net_liquidating_value', "
            "'{\"equity_dollars\": 1000.0, \"basis\": \"ledger\"}', "
            "'{\"equity_dollars\": 1500.0, \"swing_nlv\": 1500.0, "
            "\"basis\": \"net_liq_minus_declared_oof\"}', "
            "'$+500.00 (ledger minus swing_nlv)', 0, "
            "'pending_ambiguity_resolution', 'field_shape_incompatible', "
            "'classifier: field_shape_incompatible', '2026-06-15T09:00:00')",
            (run_id,),
        ).lastrowid
    )


def test_legacy_pending_ambiguity_equity_delta_clearable_to_acknowledged_immaterial(
    conn: sqlite3.Connection,
):
    """Test (d) — C3: the EXISTING resolver clears a legacy-limbo equity_delta.

    Mirrors test_resolve_orphan_discrepancy.py's
    test_resolve_legacy_pending_ambiguity_orphan_clears_ambiguity_kind (the
    exact twin precedent). The resolver clears ambiguity_kind in the same
    UPDATE so the migration-0031 cross-column CHECK permits the transition.
    No resolver CODE change — this pins that the equity_delta variant is
    already covered by the existing path.

    Distinguishing: an impl that left ambiguity_kind non-NULL ->
    acknowledged_immaterial + non-NULL ambiguity_kind violates the CHECK ->
    IntegrityError. On `main` it resolves cleanly + ambiguity_kind is NULL.
    """
    from swing.data.repos.reconciliation import insert_run

    run_id = insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-06-15T09:00:00.000",
        state="completed",
        finished_ts="2026-06-15T09:00:01.000",
        unresolved_discrepancies_count=0,
    )
    did = _raw_insert_pending_ambiguity_equity_delta(conn, run_id=run_id)
    conn.commit()

    resolve_discrepancy(
        conn,
        discrepancy_id=did,
        resolution="acknowledged_immaterial",
        resolution_reason="Clearing the legacy pending equity_delta (id-71 shape).",
    )

    disc = get_discrepancy(conn, did)
    assert disc.resolution == "acknowledged_immaterial"
    assert disc.ambiguity_kind is None
