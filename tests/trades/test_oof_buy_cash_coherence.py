"""OOF-buy cash-coherence command (Phase-18 deferred follow-up #1) — recon-path
+ ref-helper tests.

Tests (per docs/plans/oof-buy-command-plan.md §4):
  - C2  the OOF sentinel ref collision discriminator (Task 1 unit + matcher boundary)
  - S1  the step-7 self-reconcile branch distinguisher (Task 2)
  - C3  the additive/guard-only proof (every non-OOF row byte-unchanged) (Task 2)
  - C1  the BINDING composition test (RD, MERGE-BLOCKING): the both-sides-exclude
        property -- eval_delta == 0 at cost==MV AND after a later OOF price move
        (Tasks 2 + 3)

Fixtures are built from the REAL emitter path (run_schwab_reconciliation +
insert_cash), never values hand-built to satisfy the premise
(feedback_verify_premise_arithmetic_vs_live). The _SchwabAccount / _position
shapes mirror tests/trades/test_swing_nlv_coherence.py (the real Schwab account +
positions payload shape).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.data.models import CashMovement
from swing.data.repos.cash import insert_cash
from swing.trades.schwab_reconciliation import (
    _build_oof_ref,
    _cash_coherence_tolerance,
    _is_oof_sentinel_ref,
    run_schwab_reconciliation,
)

_SWING_BASIS = "net_liq_minus_declared_oof"


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


@dataclass
class _Txn:
    """Mirror SchwabTransactionResponse's matcher-relevant fields."""
    transaction_id: str
    transaction_date: str
    type: str
    net_amount: float
    description: str | None = None


def _position(
    symbol: str,
    *,
    long_qty: float = 0.0,
    market_value: float | None = None,
) -> dict:
    """The REAL Schwab position dict (sibling top-level marketValue)."""
    return {
        "shortQuantity": 0.0,
        "longQuantity": long_qty,
        "instrument": {"symbol": symbol, "type": "EQUITY"},
        "marketValue": market_value,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "oof_buy.db")


def _seed_cash(conn: sqlite3.Connection, *movements: CashMovement) -> None:
    """Insert cash_movements + COMMIT.

    run_schwab_reconciliation owns its own BEGIN IMMEDIATE and REJECTS a
    caller-held transaction, so a bare insert_cash (which does not commit) would
    leave the connection mid-transaction. Commit so the run sees a clean conn --
    this seeds PRE-EXISTING ledger rows, exactly as production (the CLI commits
    its insert before any later recon run).
    """
    with conn:
        for m in movements:
            insert_cash(conn, m)


def _run(
    conn: sqlite3.Connection,
    positions: list[dict],
    *,
    nlv: float | None,
    starting_equity: float,
    out_of_framework: tuple[str, ...] = (),
    schwab_transactions: list[Any] | None = None,
):
    acct = _SchwabAccount(net_liquidating_value=nlv, positions=positions)
    return run_schwab_reconciliation(
        conn,
        account_hash="<acct>",
        period_start="2026-06-15",
        period_end="2026-06-20",
        schwab_orders=[],
        schwab_transactions=schwab_transactions or [],
        schwab_account=acct,
        out_of_framework_tickers=out_of_framework,
        starting_equity=starting_equity,
    )


def _equity_deltas(conn: sqlite3.Connection, run_id: int) -> list[tuple]:
    return conn.execute(
        "SELECT expected_value_json, actual_value_json, delta_text "
        "FROM reconciliation_discrepancies "
        "WHERE run_id=? AND discrepancy_type='equity_delta'",
        (run_id,),
    ).fetchall()


def _cash_mismatch_ids(conn: sqlite3.Connection, run_id: int) -> list[int]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT cash_movement_id FROM reconciliation_discrepancies "
            "WHERE run_id=? AND discrepancy_type='cash_movement_mismatch'",
            (run_id,),
        ).fetchall()
    ]


# --------------------------------------------------------------------------- #
# C2 — the OOF sentinel ref collision discriminator (Task 1 unit)
# --------------------------------------------------------------------------- #

def test_oof_ref_helper_round_trip_and_collision():
    """C2 unit: the predicate + constructor are mutually-exclusive with numeric
    Schwab transaction_ids (the §3 collision proof).

    A real Schwab transaction_id is a NUMERIC string ([0-9]+); the OOF sentinel
    always carries the literal 'oof:' prefix. The two are mutually exclusive by
    construction. A buggy predicate (substring/`in`/numeric-catch) flips an
    assertion below.
    """
    # Constructor builds the canonical shape.
    assert _build_oof_ref("SPCX", "2026-06-18") == "oof:SPCX:2026-06-18"
    # Round-trip: a built ref is always recognized.
    assert _is_oof_sentinel_ref(_build_oof_ref("SPCX", "2026-06-18")) is True
    # The constructor UPPER-CASES the ticker (canonical regardless of caller case).
    assert _build_oof_ref("spcx", "2026-06-18") == "oof:SPCX:2026-06-18"
    assert _build_oof_ref(" spcx ", "2026-06-18") == "oof:SPCX:2026-06-18"
    # A numeric Schwab transaction_id is NEVER an OOF sentinel.
    assert _is_oof_sentinel_ref("115520131470") is False
    assert _is_oof_sentinel_ref(str(900088)) is False
    # Even a numeric string equal to the date digits is NOT an OOF sentinel.
    assert _is_oof_sentinel_ref("20260618") is False
    # Edge: None / empty are False (the matcher guards `cm.ref and _is_...`).
    assert _is_oof_sentinel_ref(None) is False
    assert _is_oof_sentinel_ref("") is False


def test_oof_ref_predicate_canonical_shape_only(conn):
    """Codex R1-MAJOR-1: the predicate matches the CANONICAL shape only, NOT a
    bare `oof:` prefix -- so a manual `journal cash --ref "oof:..."` row that is
    NOT a real OOF transfer-out is still emitted (Lock 1 byte-unchanged).

    A free-form `ref` can already be written via `journal cash --ref`. A
    prefix-only predicate would skip ANY `oof:`-prefixed ref as self-sourced,
    altering a NON-OOF row's emit -> a Lock-1 violation.

    Distinguishes: a non-canonical `oof:manual` ref (no TICKER:DATE shape) MUST
    still emit cash_movement_mismatch when it has no counterpart; only the
    canonical oof:<TICKER>:<YYYY-MM-DD> is skipped.
    """
    # Unit: canonical recognized; non-canonical oof:-prefixed NOT recognized.
    assert _is_oof_sentinel_ref("oof:SPCX:2026-06-18") is True
    assert _is_oof_sentinel_ref("oof:manual") is False
    assert _is_oof_sentinel_ref("oof:") is False
    assert _is_oof_sentinel_ref("oof:SPCX") is False          # missing date
    assert _is_oof_sentinel_ref("oof:SPCX:2026-6-1") is False  # non-ISO date
    assert _is_oof_sentinel_ref("oof:spcx:2026-06-18") is False  # lower ticker

    # Integration: a manual `oof:manual` withdraw with NO counterpart STILL
    # emits (it is NOT canonical-OOF-shaped -> not skipped as self-sourced).
    d = "2026-06-18"
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="withdraw", amount=42.0,
        ref="oof:manual", note="not a real oof-buy",
    ))
    manual_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref='oof:manual'"
    ).fetchone()[0]
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=500.0)],
        nlv=1450.0, starting_equity=1450.0, out_of_framework=("SPCX",),
        schwab_transactions=[],
    )
    # Lock 1: the non-canonical row is NOT skipped -> it emits as before.
    assert manual_id in _cash_mismatch_ids(conn, run.run_id)


def test_canonical_ref_non_withdraw_row_still_emits(conn):
    """Codex R2-MAJOR-1: the branch guards on kind=='withdraw' too -- a NON-
    withdraw row with a CANONICAL-shaped oof: ref is NOT skipped as self-sourced.

    The OOF command ALWAYS writes kind='withdraw', so a genuine OOF row is always
    a withdraw. A manual `journal cash --deposit ... --ref oof:SPCX:<d>` (a
    canonical-LOOKING ref on a deposit) must run the normal PASS-2 heuristic and
    emit if unmatched -- it is NOT an OOF transfer-out.

    Distinguishes: WITHOUT the kind=='withdraw' guard the deposit would be
    skipped (no emit) -> the assertion FAILS; WITH it the deposit emits. The
    companion canonical-WITHDRAW arm proves the genuine OOF row is still skipped.
    """
    d = "2026-06-18"
    canonical_ref = _build_oof_ref("SPCX", d)  # oof:SPCX:2026-06-18
    _seed_cash(
        conn,
        # A DEPOSIT carrying a canonical-looking oof: ref (NOT an OOF buy).
        CashMovement(id=None, date=d, kind="deposit", amount=123.0,
                     ref=canonical_ref, note="not-a-real-oof-buy deposit"),
    )
    deposit_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=? AND kind='deposit'",
        (canonical_ref,),
    ).fetchone()[0]
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=500.0)],
        nlv=1450.0, starting_equity=1450.0, out_of_framework=("SPCX",),
        schwab_transactions=[],   # no counterpart -> a non-skipped row emits
    )
    # The canonical-ref DEPOSIT is NOT skipped (kind != withdraw) -> it emits.
    assert deposit_id in _cash_mismatch_ids(conn, run.run_id)


def test_oof_ref_matcher_boundary_numeric_txn_not_caught(conn):
    """C2 matcher boundary: an OOF row is skipped-as-self-sourced AND a numeric
    transaction_id tx is NOT consumed by the OOF row (PASS 1 never ref-matches
    'oof:...' to a number); conversely a NON-OOF numeric ref-backed row
    ref-matches in PASS 1 as today and is NOT caught by the OOF branch.
    """
    d = "2026-06-18"
    _seed_cash(
        conn,
        # (i) OOF row reffed 'oof:SPCX:<d>'.
        CashMovement(
            id=None, date=d, kind="withdraw", amount=500.0,
            ref=_build_oof_ref("SPCX", d), note="oof",
        ),
        # (ii) a NON-OOF withdraw ref-backed to a numeric txn that value-matches.
        CashMovement(
            id=None, date=d, kind="withdraw", amount=80.0,
            ref="115520131470", note="manual",
        ),
    )
    txns = [
        # The OOF buy's TRADE counterpart (numeric id resembling date digits);
        # skipped at ingest, never a step-7 candidate.
        _Txn("20260618", d, "TRADE", -500.0),
        # The numeric-ref withdraw's real counterpart (a WITHDRAW-typed tx).
        _Txn("115520131470", d, "ACH_DISBURSEMENT", -80.0),
    ]
    oof_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?",
        (_build_oof_ref("SPCX", d),),
    ).fetchone()[0]
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=500.0)],
        nlv=1450.0, starting_equity=1450.0, out_of_framework=("SPCX",),
        schwab_transactions=txns,
    )
    mismatch_ids = _cash_mismatch_ids(conn, run.run_id)
    # The OOF row is NOT emitted (skipped self-sourced).
    assert oof_id not in mismatch_ids
    # The numeric-ref withdraw cleanly ref-matched its ACH_DISBURSEMENT -> no emit.
    numeric_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref='115520131470'"
    ).fetchone()[0]
    assert numeric_id not in mismatch_ids


# --------------------------------------------------------------------------- #
# S1 — the step-7 self-reconcile branch distinguisher (Task 2)
# --------------------------------------------------------------------------- #

def _s1_fixture(conn) -> tuple[int, list[Any]]:
    """The S1 isolation fixture: an OOF withdraw row with NO withdraw-typed
    Schwab counterpart in-window (so it CANNOT heuristic-match), plus an
    ingest-skipped TRADE + an unrelated matched deposit (so the run isn't empty).
    Returns (oof_cm_id, schwab_transactions).
    """
    d = "2026-06-18"
    _seed_cash(
        conn,
        CashMovement(
            id=None, date=d, kind="withdraw", amount=500.0,
            ref=_build_oof_ref("SPCX", d), note="oof",
        ),
        # An UNRELATED deposit that DOES have a counterpart (positive sign cannot
        # match a withdraw -> proves the run is not empty + matching still works).
        CashMovement(
            id=None, date=d, kind="deposit", amount=100.0,
            ref="900088", note="dep",
        ),
    )
    oof_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?",
        (_build_oof_ref("SPCX", d),),
    ).fetchone()[0]
    txns = [
        # The OOF buy's TRADE counterpart -- skipped at ingest, NOT a step-7
        # candidate (in _CASH_SKIP_TX_TYPES AND TRADE not in withdraw types).
        _Txn("115520131470", d, "TRADE", -500.0),
        # The unrelated deposit's matched counterpart (positive).
        _Txn("900088", d, "ACH_RECEIPT", 100.0),
    ]
    return oof_id, txns


def test_self_reconcile_oof_row_not_emitted(conn):
    """S1 (post-fix): the OOF-marked cash_movement does NOT fire
    cash_movement_mismatch (scoped to the OOF cm.id; an unrelated mismatch may
    legitimately exist elsewhere, so the assertion is scoped, not generic)."""
    oof_id, txns = _s1_fixture(conn)
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=500.0)],
        nlv=1450.0, starting_equity=950.0, out_of_framework=("SPCX",),
        schwab_transactions=txns,
    )
    assert oof_id not in _cash_mismatch_ids(conn, run.run_id)


def test_self_reconcile_branch_disabled_belt_fires(conn, monkeypatch):
    """S1 branch-disabled belt (the cleanest distinguisher): with the OOF branch
    FORCED INERT (the predicate monkeypatched to return False -- mirrors the
    branch absent), the SAME fixture emits cash_movement_mismatch for the OOF
    cm.id. The emit FLIPPING on the single boolean proves the branch is
    load-bearing (eliminates the both-paths-pass risk).

    Pre-fix arithmetic: without the branch, the OOF row is not ref-matched
    (PASS 1: 'oof:...' != numeric txn_id), not ref-mismatch, runs the PASS-2
    heuristic, and -- because the fixture provably has NO withdraw-typed
    counterpart in window -- finds match_idx is None -> emits
    cash_movement_mismatch for the OOF cm.id.
    """
    import swing.trades.schwab_reconciliation as sr

    monkeypatch.setattr(sr, "_is_oof_sentinel_ref", lambda _ref: False)
    oof_id, txns = _s1_fixture(conn)
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=500.0)],
        nlv=1450.0, starting_equity=950.0, out_of_framework=("SPCX",),
        schwab_transactions=txns,
    )
    # Branch disabled -> the OOF row DOES emit (the both-paths-pass hole closed).
    assert oof_id in _cash_mismatch_ids(conn, run.run_id)


# --------------------------------------------------------------------------- #
# C3 — the additive/guard-only proof (every non-OOF row byte-unchanged) (Task 2)
# --------------------------------------------------------------------------- #

def _c3_fixture(conn) -> dict[str, int]:
    """A mix of NON-OOF cash_movements exercising each step-7 outcome class.
    Returns a dict of cm.id keyed by outcome label.
    """
    d = "2026-06-18"
    ids: dict[str, int] = {}
    _seed_cash(
        conn,
        # (a) ref-backed clean match (ref == numeric txn_id, value-valid) -> no emit.
        CashMovement(id=None, date=d, kind="deposit", amount=100.0,
                     ref="111", note=None),
        # (b) ref-backed value-drift (ref == numeric txn_id, WRONG amount) -> emit.
        CashMovement(id=None, date=d, kind="deposit", amount=999.0,
                     ref="222", note=None),
        # (c) ref-less heuristic match (matching date/amount/kind/sign) -> no emit.
        CashMovement(id=None, date=d, kind="deposit", amount=300.0,
                     ref=None, note="c"),
        # (d) ref-less no-counterpart row -> emit.
        CashMovement(id=None, date=d, kind="withdraw", amount=77.0,
                     ref=None, note="d"),
    )
    ids["a_clean"] = conn.execute(
        "SELECT id FROM cash_movements WHERE ref='111'").fetchone()[0]
    ids["b_drift"] = conn.execute(
        "SELECT id FROM cash_movements WHERE ref='222'").fetchone()[0]
    ids["c_heuristic"] = conn.execute(
        "SELECT id FROM cash_movements WHERE note='c'").fetchone()[0]
    ids["d_no_match"] = conn.execute(
        "SELECT id FROM cash_movements WHERE note='d'").fetchone()[0]
    return ids


def _c3_txns() -> list[Any]:
    d = "2026-06-18"
    return [
        _Txn("111", d, "ACH_RECEIPT", 100.0),   # (a) clean ref-match
        _Txn("222", d, "ACH_RECEIPT", 100.0),   # (b) ref-match but WRONG amount
        _Txn("333", d, "ACH_RECEIPT", 300.0),   # (c) heuristic match for ref-less
        # (d) has NO counterpart.
    ]


def test_c3_non_oof_rows_byte_unchanged(conn):
    """C3 LOCK: every NON-OOF row's match/emit disposition is byte-unchanged by
    the new branch (the branch is inert for non-OOF refs). Non-vacuity guard:
    (b) and (d) MUST emit (the emit path still works); (a) and (c) MUST NOT emit
    (matches preserved).
    """
    ids = _c3_fixture(conn)
    run = _run(
        conn, [], nlv=1000.0, starting_equity=1000.0,
        out_of_framework=("SPCX",), schwab_transactions=_c3_txns(),
    )
    emitted = set(_cash_mismatch_ids(conn, run.run_id))
    # Non-vacuity: the emit path works (b drift, d no-counterpart).
    assert ids["b_drift"] in emitted
    assert ids["d_no_match"] in emitted
    # Matches preserved (a clean ref-match, c heuristic).
    assert ids["a_clean"] not in emitted
    assert ids["c_heuristic"] not in emitted
    # The exact emit set is the two emitters (no OOF row planted -> branch inert).
    assert emitted == {ids["b_drift"], ids["d_no_match"]}


# --------------------------------------------------------------------------- #
# C1 — the BINDING composition test (RD, MERGE-BLOCKING measurement artifact)
# --------------------------------------------------------------------------- #
#
# §2.4 arithmetic (worktree base schwab_reconciliation.py):
#   ledger_equity = current_equity(starting, exits, cash_movements)  (:1854)
#     -- a 'withdraw' SUBTRACTS from net_cash_movements (equity.py).
#   declared_oof_mv summed from POSITIONS (:1911-1926), NOT cash_movements.
#   swing_nlv = finite_source_nlv - declared_oof_mv  (:1939)
#   eval_delta = finite_ledger_equity - swing_nlv  (:1957)
#   fire iff journal_flat and broker_flat_swing and |eval_delta| > tol  (:1971)
#   tol = max(5.00, 0.005*|NLV|)  (_cash_coherence_tolerance, :208)
#
# Fixture (the at-purchase identity): L0 = starting_equity = 1450; ONE declared
# SPCX position market_value = M = C = 500; broker NLV N = L0 = 1450 (cash C
# became the OOF position worth M==C; total assets unchanged).
#   PRE  (no OOF withdraw): ledger=1450, swing_nlv=1450-500=950,
#        eval_delta = 1450-950 = 500 = C; tol = max(5, 0.005*950)=5.0; 500>5 FIRES.
#   POST (OOF withdraw 500): ledger=950, swing_nlv=950, eval_delta=0 -> no fire.
#   LATER price move M'=750: N'=1450-500+750=1700, swing_nlv'=1700-750=950,
#        ledger=950, eval_delta=0 -> STILL no fire (the both-sides-exclude property).

_L0 = 1450.0
_C = 500.0
_N = 1450.0   # at-purchase identity N == L0
_MPRIME = 750.0


def test_c1_composition_pre_fix_fires(conn):
    """C1 PRE: no OOF withdraw row -> the ledger is overstated by C -> drift
    fires. The fired row carries the swing-scoped basis (proves the §2.4 path,
    not a degraded net_liq fixture). The tolerance is COMPUTED from the resolved
    swing_nlv (not assumed)."""
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=_C)],
        nlv=_N, starting_equity=_L0, out_of_framework=("SPCX",),
    )
    rows = _equity_deltas(conn, run.run_id)
    # Arithmetic: swing_nlv = N - M = 1450 - 500 = 950; eval_delta = 1450 - 950 = 500.
    swing_nlv = _N - _C
    eval_delta_pre = _L0 - swing_nlv
    tol = _cash_coherence_tolerance(swing_nlv)
    assert eval_delta_pre == pytest.approx(_C)
    assert abs(eval_delta_pre) > tol  # 500 > 5.0 -> the PRE state fires
    assert len(rows) == 1
    import json
    act = json.loads(rows[0][1])
    assert act["basis"] == _SWING_BASIS          # the swing-scoped §2.4 path
    assert act["swing_nlv"] == pytest.approx(swing_nlv)
    assert "+500.00" in rows[0][2]                # delta_text reflects C


def test_c1_composition_post_fix_zero_at_cost_and_after_price_move(conn):
    """C1 POST + the later-price-move arm (the binding both-sides-exclude
    property): after the OOF withdraw, eval_delta == 0 at cost==MV; AND after a
    later OOF price move, eval_delta STILL == 0 (both sides exclude the OOF).

    The OOF withdraw is inserted via the production repo path (insert_cash with
    the canonical ref). It is recognized + skipped by the step-7 self-reconcile
    branch (so it never fires cash_movement_mismatch either)."""
    d = "2026-06-18"
    # POST-fix: insert the OOF withdraw (the production cash path).
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="withdraw", amount=_C,
        ref=_build_oof_ref("SPCX", d), note="oof transfer-out",
    ))
    run = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=_C)],
        nlv=_N, starting_equity=_L0, out_of_framework=("SPCX",),
        schwab_transactions=[_Txn("115520131470", d, "TRADE", -_C)],
    )
    # Arithmetic: ledger = L0 - C = 950; swing_nlv = N - M = 950; eval_delta = 0.
    assert _equity_deltas(conn, run.run_id) == []   # POST: no fire at cost==MV
    # The OOF row is self-sourced -> no cash_movement_mismatch for it either.
    oof_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?",
        (_build_oof_ref("SPCX", d),),
    ).fetchone()[0]
    assert oof_id not in _cash_mismatch_ids(conn, run.run_id)

    # The later-price-move arm: keep the OOF withdraw; re-price SPCX to M'=750.
    # N' = L0 - C + M' = 1700; swing_nlv' = N' - M' = 950; ledger = 950; delta=0.
    run2 = _run(
        conn, [_position("SPCX", long_qty=2.0, market_value=_MPRIME)],
        nlv=_L0 - _C + _MPRIME, starting_equity=_L0, out_of_framework=("SPCX",),
        schwab_transactions=[_Txn("115520131470", d, "TRADE", -_C)],
    )
    assert _equity_deltas(conn, run2.run_id) == []   # STILL no fire after move
