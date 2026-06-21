"""cash-void command (Phase-18 register D19) -- recon-path + ref-helper tests.

Tests (per docs/plans/cash-void-command-plan.md §4):
  - C2-V   the VOID sentinel ref collision + canonical-shape discriminator
           (Task 1 unit + matcher boundary)
  - S-V    the step-7 self-reconcile `void:` branch distinguisher -- BOTH a
           void-deposit AND a void-withdraw (the kind-agnostic gate, O1) (Task 2)
  - C3-V   the additive/guard-only proof (every non-void row byte-unchanged) (Task 2)
  - COMP-V the BINDING composition test (RD, MERGE-BLOCKING): void a withdraw of
           X -> current_equity RESTORED; AND the symmetric deposit case (Tasks 2+4)

Fixtures are built from the REAL emitter path (run_schwab_reconciliation +
insert_cash + the real current_equity), never values hand-built to satisfy the
premise (feedback_verify_premise_arithmetic_vs_live). The _SchwabAccount /
_position shapes mirror tests/trades/test_oof_buy_cash_coherence.py.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.data.models import CashMovement
from swing.data.repos.cash import insert_cash, list_cash
from swing.trades.equity import current_equity
from swing.trades.schwab_reconciliation import (
    _build_void_ref,
    _cash_coherence_tolerance,
    _is_oof_sentinel_ref,
    _is_void_sentinel_ref,
    run_schwab_reconciliation,
)


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
    return ensure_schema(tmp_path / "cash_void.db")


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
# C2-V — the VOID sentinel ref collision + canonical-shape discriminator (unit)
# --------------------------------------------------------------------------- #

def test_void_ref_helper_round_trip_and_collision():
    """C2-V unit: the predicate + constructor are mutually-exclusive with numeric
    Schwab transaction_ids (the §3 collision proof) AND with the `oof:` prefix.

    A real Schwab transaction_id is a NUMERIC string ([0-9]+); the void sentinel
    always carries the literal 'void:' prefix. A buggy predicate (bare-prefix
    startswith, substring/`in`, numeric-catch) flips an assertion below.
    """
    # Constructor builds the canonical shape.
    assert _build_void_ref(5) == "void:5"
    assert _build_void_ref(42) == "void:42"
    # Round-trip: a built ref is always recognized.
    assert _is_void_sentinel_ref(_build_void_ref(42)) is True
    assert _is_void_sentinel_ref("void:5") is True
    # Canonical-shape ONLY (NOT a bare `void:` prefix -- the OOF R1 lesson).
    assert _is_void_sentinel_ref("void:") is False        # no digits
    assert _is_void_sentinel_ref("void:abc") is False     # non-digit tail
    assert _is_void_sentinel_ref("void:5x") is False      # trailing non-digit
    assert _is_void_sentinel_ref("void: 5") is False      # space
    assert _is_void_sentinel_ref("void:5:6") is False     # extra segment
    # Codex R2-MINOR: the predicate accepts EXACTLY the constructor's domain --
    # _build_void_ref rejects id<1 and int() never emits a leading zero, so a
    # zero / leading-zero ref must NOT be recognized as self-sourced.
    assert _is_void_sentinel_ref("void:0") is False       # zero (id<1 rejected)
    assert _is_void_sentinel_ref("void:0005") is False    # leading zero
    # Collision: a numeric Schwab transaction_id is NEVER a void sentinel.
    assert _is_void_sentinel_ref("115520131470") is False
    assert _is_void_sentinel_ref("5") is False
    # Cross-prefix disjointness: void and oof predicates are mutually exclusive.
    assert _is_void_sentinel_ref("oof:SPCX:2026-06-18") is False
    assert _is_oof_sentinel_ref("void:5") is False
    # Edge: None / empty are False (the matcher guards `cm.ref and _is_...`).
    assert _is_void_sentinel_ref(None) is False
    assert _is_void_sentinel_ref("") is False


def test_build_void_ref_rejects_non_positive_id():
    """C2-V unit: _build_void_ref rejects a non-positive id (raise ValueError),
    surfaced as a clean ClickException at the CLI boundary. A well-defined
    cash_movements id is >= 1."""
    with pytest.raises(ValueError):
        _build_void_ref(0)
    with pytest.raises(ValueError):
        _build_void_ref(-5)
    # The normal case still works.
    assert _build_void_ref(7) == "void:7"


def test_void_ref_matcher_boundary_numeric_txn_not_caught(conn):
    """C2-V matcher boundary: a void row is skipped-as-self-sourced AND a numeric
    transaction_id tx is NOT consumed by the void row (PASS 1 never ref-matches
    'void:5' to a number); conversely a NON-void numeric ref-backed row
    ref-matches in PASS 1 as today and is NOT caught by the void branch.
    """
    d = "2026-06-18"
    _seed_cash(
        conn,
        # (i) a void DEPOSIT reffed 'void:5'.
        CashMovement(
            id=None, date=d, kind="deposit", amount=500.0,
            ref=_build_void_ref(5), note="VOID #5: test",
        ),
        # (ii) a NON-void withdraw ref-backed to a numeric txn that value-matches.
        CashMovement(
            id=None, date=d, kind="withdraw", amount=80.0,
            ref="115520131470", note="manual",
        ),
    )
    txns = [
        # The numeric-ref withdraw's real counterpart (a WITHDRAW-typed tx).
        _Txn("115520131470", d, "ACH_DISBURSEMENT", -80.0),
    ]
    void_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?", (_build_void_ref(5),)
    ).fetchone()[0]
    run = _run(
        conn, [], nlv=1450.0, starting_equity=1450.0, schwab_transactions=txns,
    )
    mismatch_ids = _cash_mismatch_ids(conn, run.run_id)
    # The void row is NOT emitted (skipped self-sourced).
    assert void_id not in mismatch_ids
    # The numeric-ref withdraw cleanly ref-matched its ACH_DISBURSEMENT -> no emit.
    numeric_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref='115520131470'"
    ).fetchone()[0]
    assert numeric_id not in mismatch_ids


# --------------------------------------------------------------------------- #
# S-V — the step-7 self-reconcile `void:` branch distinguisher (BOTH directions)
# --------------------------------------------------------------------------- #

def _sv_fixture(conn) -> tuple[int, int, list[Any]]:
    """The S-V isolation fixture: TWO void rows -- a void DEPOSIT (reversing a
    withdraw) and a void WITHDRAW (reversing a deposit) -- each with NO
    same-sign Schwab counterpart in-window (so neither can heuristic-match).
    Returns (void_deposit_id, void_withdraw_id, schwab_transactions).

    out_of_framework is EMPTY in the caller to PROVE the void skip does NOT
    depend on a ticker registry (the kind-agnostic gate, O1).
    """
    d = "2026-06-18"
    _seed_cash(
        conn,
        # A void DEPOSIT (reversing an erroneous withdraw id 11).
        CashMovement(
            id=None, date=d, kind="deposit", amount=500.0,
            ref=_build_void_ref(11), note="VOID #11: bad withdraw",
        ),
        # A void WITHDRAW (reversing an erroneous deposit id 12).
        CashMovement(
            id=None, date=d, kind="withdraw", amount=250.0,
            ref=_build_void_ref(12), note="VOID #12: bad deposit",
        ),
    )
    void_dep_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?", (_build_void_ref(11),)
    ).fetchone()[0]
    void_wd_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?", (_build_void_ref(12),)
    ).fetchone()[0]
    # No same-sign counterpart for EITHER void row. An unrelated matched tx is
    # not needed; the empty list keeps the fixture minimal (the void rows still
    # run the PASS-2 heuristic with no candidate).
    txns: list[Any] = []
    return void_dep_id, void_wd_id, txns


def test_self_reconcile_void_rows_not_emitted(conn):
    """S-V (post-fix): NEITHER void row fires cash_movement_mismatch -- scoped to
    the void cm.ids. Covers BOTH a void-deposit AND a void-withdraw with an
    EMPTY out_of_framework registry (the kind-agnostic, registry-independent
    gate, O1)."""
    void_dep_id, void_wd_id, txns = _sv_fixture(conn)
    run = _run(
        conn, [], nlv=1450.0, starting_equity=1450.0,
        out_of_framework=(),  # EMPTY -- the void skip must not depend on it
        schwab_transactions=txns,
    )
    emitted = _cash_mismatch_ids(conn, run.run_id)
    assert void_dep_id not in emitted   # void DEPOSIT skipped (kind-agnostic)
    assert void_wd_id not in emitted    # void WITHDRAW skipped


def test_self_reconcile_branch_disabled_belt_fires(conn, monkeypatch):
    """S-V branch-disabled belt (the cleanest distinguisher): with the void
    branch FORCED INERT (the predicate monkeypatched to return False -- mirrors
    the branch absent), the SAME fixture emits cash_movement_mismatch for BOTH
    void cm.ids. The emit FLIPPING on the single boolean proves the branch is
    load-bearing AND kind-agnostic (eliminates the both-paths-pass risk).

    Pre-fix arithmetic: without the branch, each void row is not ref-matched
    (PASS 1: 'void:...' != numeric txn_id), not ref-mismatch, runs the PASS-2
    heuristic, and -- because the fixture provably has NO same-sign counterpart
    in window -- finds match_idx is None -> emits cash_movement_mismatch for the
    void cm.id. So pre-fix BOTH void rows emit; post-fix NEITHER does.

    The void-DEPOSIT-emitted assertion is the discriminator a kind=='withdraw'
    copy-paste of the OOF branch would FAIL: such a gate would skip the void
    WITHDRAW even with the branch inert here is moot -- the point is the ACTIVE
    branch (the companion test) must skip the void DEPOSIT, which a
    kind=='withdraw' gate cannot.
    """
    import swing.trades.schwab_reconciliation as sr

    monkeypatch.setattr(sr, "_is_void_sentinel_ref", lambda _ref: False)
    void_dep_id, void_wd_id, txns = _sv_fixture(conn)
    run = _run(
        conn, [], nlv=1450.0, starting_equity=1450.0,
        out_of_framework=(), schwab_transactions=txns,
    )
    emitted = _cash_mismatch_ids(conn, run.run_id)
    # Branch disabled -> BOTH void rows DO emit (the both-paths-pass hole closed).
    assert void_dep_id in emitted
    assert void_wd_id in emitted


# --------------------------------------------------------------------------- #
# C3-V — the additive/guard-only proof (every non-void row byte-unchanged)
# --------------------------------------------------------------------------- #

def _c3_fixture(conn) -> dict[str, int]:
    """A mix of NON-void cash_movements exercising each step-7 outcome class.
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


def test_c3_non_void_rows_byte_unchanged(conn):
    """C3-V LOCK: every NON-void row's match/emit disposition is byte-unchanged
    by the new branch (the branch is inert for non-void refs). Non-vacuity guard:
    (b) and (d) MUST emit (the emit path still works); (a) and (c) MUST NOT emit
    (matches preserved). No void row is planted -> the new branch is provably
    inert.
    """
    ids = _c3_fixture(conn)
    run = _run(
        conn, [], nlv=1000.0, starting_equity=1000.0,
        schwab_transactions=_c3_txns(),
    )
    emitted = set(_cash_mismatch_ids(conn, run.run_id))
    # Non-vacuity: the emit path works (b drift, d no-counterpart).
    assert ids["b_drift"] in emitted
    assert ids["d_no_match"] in emitted
    # Matches preserved (a clean ref-match, c heuristic).
    assert ids["a_clean"] not in emitted
    assert ids["c_heuristic"] not in emitted
    # The exact emit set is the two emitters (no void row planted -> branch inert).
    assert emitted == {ids["b_drift"], ids["d_no_match"]}


# --------------------------------------------------------------------------- #
# COMP-V — the BINDING composition test (RD, MERGE-BLOCKING measurement artifact)
# --------------------------------------------------------------------------- #
#
# §2.1 + §2.4 arithmetic (worktree base):
#   current_equity = starting + realized + net_cash_movements  (equity.py:39)
#     -- a 'withdraw'/'fee' SUBTRACTS; a 'deposit'/'interest'/'dividend' ADDS.
#   With no positions: swing_nlv == finite_source_nlv == N == L0.
#   eval_delta = finite_ledger_equity - swing_nlv  (the §2.4 path).
#   fire iff journal_flat and broker_flat_swing and |eval_delta| > tol.
#   tol = max(5.00, 0.005*|NLV|)  (_cash_coherence_tolerance).
#
# Fixture (no positions, flat): L0 = starting = 1450; broker NLV N = L0 = 1450.
#   The error: a withdraw of X=372.48 -> ledger = L0 - X; eval_delta = -X; FIRES.
#   The void: a reversing deposit of X -> ledger = L0; eval_delta = 0; no fire.

_L0 = 1450.0
_X = 372.48   # the live SPCX double-debit amount


def test_comp_v_void_withdraw_restores_current_equity(conn):
    """COMP-V (the binding measurement artifact -- the withdraw-error direction):
    void an erroneous withdraw of X -> current_equity RESTORED to L0; PRE-void
    it is L0 - X. Asserted on BOTH the direct current_equity surface AND the
    recon equity_delta surface (PRE fires -X, POST 0).

    Real-derived: the void reversing row is inserted via the production
    insert_cash path with the canonical void ref; the tolerance is COMPUTED from
    the resolved swing_nlv (not assumed).
    """
    d = "2026-06-18"
    # Baseline (no error row): current_equity == L0.
    assert current_equity(
        starting_equity=_L0, exits=[], cash_movements=list_cash(conn)
    ) == pytest.approx(_L0)

    # The error: an erroneous withdraw of X.
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="withdraw", amount=_X, ref=None, note="bad debit",
    ))
    err_id = conn.execute(
        "SELECT id FROM cash_movements WHERE note='bad debit'"
    ).fetchone()[0]
    ce_pre = current_equity(
        starting_equity=_L0, exits=[], cash_movements=list_cash(conn)
    )
    assert ce_pre == pytest.approx(_L0 - _X)   # PRE-void: off by X

    # PRE-void recon: eval_delta = (L0 - X) - L0 = -X; tol << X -> FIRES once.
    run_pre = _run(conn, [], nlv=_L0, starting_equity=_L0)
    rows_pre = _equity_deltas(conn, run_pre.run_id)
    tol = _cash_coherence_tolerance(_L0)
    assert abs(-_X) > tol           # 372.48 > 7.25 -> fires
    assert len(rows_pre) == 1

    # The void: a reversing DEPOSIT of X with ref=void:<err_id> (production path).
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="deposit", amount=_X,
        ref=_build_void_ref(err_id), note=f"VOID #{err_id}: double-debit",
    ))
    ce_post = current_equity(
        starting_equity=_L0, exits=[], cash_movements=list_cash(conn)
    )
    # POST-void: RESTORED to baseline; the restoration delta is EXACTLY X.
    assert ce_post == pytest.approx(_L0)
    assert ce_post - ce_pre == pytest.approx(_X)

    # POST-void recon: eval_delta = L0 - L0 = 0 -> NO equity_delta fires.
    run_post = _run(conn, [], nlv=_L0, starting_equity=_L0)
    assert _equity_deltas(conn, run_post.run_id) == []
    # The void row is self-sourced -> no cash_movement_mismatch for it either.
    void_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?", (_build_void_ref(err_id),)
    ).fetchone()[0]
    assert void_id not in _cash_mismatch_ids(conn, run_post.run_id)


def test_comp_v_void_deposit_restores_current_equity(conn):
    """COMP-V symmetric arm (the deposit-error direction): void an erroneous
    deposit of X -> a reversing WITHDRAW restores current_equity to L0; PRE-void
    it is L0 + X. The recon eval_delta flips from +X (fires) to 0 (no fire)."""
    d = "2026-06-18"
    # The error: an erroneous deposit of X.
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="deposit", amount=_X, ref=None, note="bad credit",
    ))
    err_id = conn.execute(
        "SELECT id FROM cash_movements WHERE note='bad credit'"
    ).fetchone()[0]
    ce_pre = current_equity(
        starting_equity=_L0, exits=[], cash_movements=list_cash(conn)
    )
    assert ce_pre == pytest.approx(_L0 + _X)   # PRE-void: over by X

    # PRE-void recon: eval_delta = (L0 + X) - L0 = +X -> FIRES once.
    run_pre = _run(conn, [], nlv=_L0, starting_equity=_L0)
    assert len(_equity_deltas(conn, run_pre.run_id)) == 1

    # The void: a reversing WITHDRAW of X with ref=void:<err_id>.
    _seed_cash(conn, CashMovement(
        id=None, date=d, kind="withdraw", amount=_X,
        ref=_build_void_ref(err_id), note=f"VOID #{err_id}: bad credit",
    ))
    ce_post = current_equity(
        starting_equity=_L0, exits=[], cash_movements=list_cash(conn)
    )
    assert ce_post == pytest.approx(_L0)
    assert ce_pre - ce_post == pytest.approx(_X)

    # POST-void recon: eval_delta = 0 -> NO fire.
    run_post = _run(conn, [], nlv=_L0, starting_equity=_L0)
    assert _equity_deltas(conn, run_post.run_id) == []
    void_id = conn.execute(
        "SELECT id FROM cash_movements WHERE ref=?", (_build_void_ref(err_id),)
    ).fetchone()[0]
    assert void_id not in _cash_mismatch_ids(conn, run_post.run_id)
