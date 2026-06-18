"""Swing-NLV coherence refinement (SPCX §2.4 fast-follow) — step-8 generalization.

Generalizes the both-flat equity-coherence gate from ``broker_flat`` to
``broker_flat_swing`` (`schwab_positions − declared out-of-framework set` empty)
and reconciles the swing ledger against a swing-scoped NLV
(`source_nlv − Σ(declared marketValue)`, SAME snapshot) so a real swing drift is
detected even while a declared out-of-framework position (SPCX) is held.

Design = drift-only (CHARC C1-C5; RD L2 §9.4):
  - the run-row columns STAY RAW (`account_equity_source_dollars` = raw broker NLV;
    `equity_delta_dollars` = raw `ledger - source_nlv`);
  - the swing-scoped values ride ADDITIVELY in the fired `equity_delta`'s
    `actual_value_json` ON FIRE only;
  - the swing-flat-and-coherent (no-fire) case persists NOTHING and emits a
    swing-scoped `log.info` line (test (a)'s caplog distinguisher);
  - C2 suppress-NEVER-treat-as-0 on a missing/malformed/non-finite declared MV;
  - a non-finite broker NLV degrades to `None` stamps (run COMPLETES, not crashes).

Fixtures are built from the REAL Schwab account + positions payload shape
(``schwab_account.net_liquidating_value`` + each position's ``marketValue``).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.schwab_reconciliation import run_schwab_reconciliation

_RECON_LOGGER = "swing.trades.schwab_reconciliation"
_SWING_BASIS = "net_liq_minus_declared_oof"


@dataclass
class _SchwabAccount:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


def _position(
    symbol: str,
    *,
    long_qty: float = 0.0,
    short_qty: float = 0.0,
    market_value: float | None = None,
) -> dict:
    """The REAL Schwab position dict (sibling top-level ``marketValue``)."""
    return {
        "shortQuantity": short_qty,
        "longQuantity": long_qty,
        "instrument": {"symbol": symbol, "type": "EQUITY"},
        "marketValue": market_value,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "swing_nlv.db")


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


def _equity_deltas(conn: sqlite3.Connection, run_id: int) -> list[tuple]:
    return conn.execute(
        "SELECT expected_value_json, actual_value_json, delta_text "
        "FROM reconciliation_discrepancies "
        "WHERE run_id=? AND discrepancy_type='equity_delta'",
        (run_id,),
    ).fetchall()


def _run_row(conn: sqlite3.Connection, run_id: int) -> tuple:
    return conn.execute(
        "SELECT account_equity_journal_dollars, account_equity_source_dollars, "
        "equity_delta_dollars, summary_json FROM reconciliation_runs "
        "WHERE run_id=?",
        (run_id,),
    ).fetchone()


def _swing_log_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r for r in caplog.records
        if r.name == _RECON_LOGGER and _SWING_BASIS in r.getMessage()
    ]


# --------------------------------------------------------------------------- #
# Task 1 — broker_flat_swing + the swing-scoped fire condition (tests (b),(e))
# --------------------------------------------------------------------------- #

def test_drift_while_holding_declared_fires(conn):
    """Test (b) — THE core value: a real swing drift FIRES while SPCX is held.

    nlv = 392.51 + 1500.00 = 1892.51; declared SPCX mv=392.51;
    swing_nlv = 1892.51 - 392.51 = 1500.00; ledger = starting 1450.00;
    |1450 - 1500| = 50.00; tol = max(5, 0.5%*1500) = 7.50; 50 > 7.50 -> FIRES.

    Pre-fix: broker not flat -> the whole `if` suppressed -> ZERO equity_delta rows.
    Post-fix: exactly one equity_delta row.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=392.51)],
        nlv=1892.51,
        starting_equity=1450.00,
        out_of_framework=("SPCX",),
    )
    rows = _equity_deltas(conn, run.run_id)
    assert len(rows) == 1


def test_undeclared_position_present_suppresses(conn):
    """Test (e) — the scoping distinguisher (pinned to FALSE-FIRE both bad impls).

    declared SPCX mv=392.51 + UNDECLARED FOO mv=500.00; nlv = 2392.51;
    ledger = 1450.00. A correct impl never computes a swing delta because FOO
    makes swing non-flat (broker_flat_swing = False).
      - "subtract-declared-only": swing_nlv = 2392.51-392.51 = 2000.00, |1450-2000|=550 > tol 10 -> FIRES (wrong).
      - "subtract-all-positions": swing_nlv = 2392.51-892.51 = 1500.00, |1450-1500|=50 > tol 7.50 -> FIRES (wrong).
    """
    run = _run(
        conn,
        [
            _position("SPCX", long_qty=2.0, market_value=392.51),  # declared
            _position("FOO", long_qty=10.0, market_value=500.00),  # undeclared
        ],
        nlv=2392.51,
        starting_equity=1450.00,
        out_of_framework=("SPCX",),
    )
    # (1) no equity_delta — swing is NOT flat (FOO is an unaccounted real position).
    assert _equity_deltas(conn, run.run_id) == []
    # (2) FOO still banners an untracked_broker_position; (3) SPCX carved out.
    orphans = conn.execute(
        "SELECT ticker FROM reconciliation_discrepancies "
        "WHERE run_id=? AND discrepancy_type='untracked_broker_position'",
        (run.run_id,),
    ).fetchall()
    assert [r[0] for r in orphans] == ["FOO"]


# --------------------------------------------------------------------------- #
# Task 2 — swing_nlv computation + the C1/C2 guards (tests (a),(c))
# --------------------------------------------------------------------------- #

def test_coherent_while_holding_logs_swing_scoped_evaluation(conn, caplog):
    """Test (a) — §9.4 caplog distinguisher: coherent-while-holding LOGS, no fire.

    nlv = 392.51 + 1450.00 = 1842.51; declared SPCX mv=392.51;
    swing_nlv = 1842.51 - 392.51 = 1450.00; ledger = 1450.00;
    swing_coherence_delta = 0.00; tol = max(5, 0.5%*1450) = 7.25; 0 <= 7.25 -> NO fire.

    Pre-fix: broker not flat -> swing-scoped path never runs -> NO swing-scoped
    caplog record; run row equity_delta_dollars = ledger-source_nlv = -392.51 (RAW).
    Post-fix: NO fire; a swing-scoped INFO caplog record IS emitted; run row
    equity_delta_dollars STILL -392.51 (RAW, the column cannot distinguish).
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(
            conn,
            [_position("SPCX", long_qty=2.0, market_value=392.51)],
            nlv=1842.51,
            starting_equity=1450.00,
            out_of_framework=("SPCX",),
        )
    # (1) no equity_delta discrepancy.
    assert _equity_deltas(conn, run.run_id) == []
    # (2) a swing-scoped INFO caplog record exists with the swing-scoped fields.
    swing_logs = _swing_log_records(caplog)
    assert len(swing_logs) == 1
    msg = swing_logs[0].getMessage()
    assert _SWING_BASIS in msg
    assert "1450.0" in msg          # swing_nlv
    assert "1842.51" in msg         # source_nlv
    assert "392.51" in msg          # declared_oof_mv
    # (3) run row equity_delta_dollars STAYS RAW = ledger - source_nlv = -392.51.
    journal_d, source_d, delta_d, summary_json = _run_row(conn, run.run_id)
    assert delta_d == pytest.approx(-392.51)
    # (4) account_equity_source_dollars is the RAW broker NLV (unchanged).
    assert source_d == pytest.approx(1842.51)
    # (5) summary_json has NO equity_coherence key (§9.4).
    assert "equity_coherence" not in json.loads(summary_json)


def test_drift_while_holding_records_swing_scoped_actual_value_json(conn):
    """The swing-scoped JSON half of test (b): the fired row carries the swing basis.

    Same setup as the drift test (source_nlv=1892.51, SPCX mv=392.51,
    ledger=1450.00 -> FIRES). The emitted actual_value_json carries the
    swing-scoped basis + swing_nlv + source_nlv + declared_oof_mv.
    """
    run = _run(
        conn,
        [_position("SPCX", long_qty=2.0, market_value=392.51)],
        nlv=1892.51,
        starting_equity=1450.00,
        out_of_framework=("SPCX",),
    )
    rows = _equity_deltas(conn, run.run_id)
    assert len(rows) == 1
    expected, actual, _delta_text = rows[0]
    act = json.loads(actual)
    assert act["basis"] == _SWING_BASIS
    assert act["swing_nlv"] == pytest.approx(1500.0)
    assert act["source_nlv"] == pytest.approx(1892.51)
    assert act["declared_oof_mv"] == pytest.approx(392.51)
    # expected stays the ledger basis.
    assert json.loads(expected)["basis"] == "ledger"


def test_missing_declared_mv_suppresses(conn, caplog):
    """Test (c) — C2 suppress-NEVER-treat-as-0 (pinned to FALSE-FIRE a None->0 impl).

    declared SPCX mv=None; nlv = 1500.00; ledger = 1450.00.
    A None->0 impl: swing_nlv = 1500-0 = 1500.00, |1450-1500|=50 > tol 7.50 -> FALSE-FIRES.
    The correct C2 impl SUPPRESSES (declared MV missing -> swing_nlv uncomputable).

    Pre-fix: suppressed anyway (broker not flat); RAW legacy delta -50.00; no log line.
    Post-fix: still no fire (C2 guard) AND no swing-scoped coherent log line.
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(
            conn,
            [_position("SPCX", long_qty=2.0, market_value=None)],
            nlv=1500.00,
            starting_equity=1450.00,
            out_of_framework=("SPCX",),
        )
    # (1) PRIMARY distinguisher — no spurious equity_delta (a None->0 impl false-fires).
    assert _equity_deltas(conn, run.run_id) == []
    # (2) no swing-scoped coherent log line (the degrade path did NOT run a coherent eval).
    assert _swing_log_records(caplog) == []
    # (3) run row equity_delta_dollars = RAW legacy ledger - source_nlv = -50.00.
    _journal_d, source_d, delta_d, summary_json = _run_row(conn, run.run_id)
    assert delta_d == pytest.approx(-50.00)
    assert source_d == pytest.approx(1500.00)
    # (4) NO equity_coherence key (§9.4).
    assert "equity_coherence" not in json.loads(summary_json)


def test_missing_declared_mv_nonfinite_suppresses(conn, caplog):
    """C2 (R1 MINOR 2) — a NON-finite declared MV (inf/nan) also suppresses.

    A non-finite MV is the reachable malformed case (the upstream orphan pass
    parses MV with float() then drops non-finite to None at :1433; a non-numeric
    STRING MV crashes that orphan-pass float() first, so it never reaches step 8
    — that is a pre-existing step-5.1 defect, out of this step-8-only scope).
    The step-8 guard treats non-finite MV as unavailable -> suppress (NEVER
    treat-as-0). Same arithmetic as test (c): a treat-as-0 impl would false-fire
    (|1450-1500|=50 > 7.50).
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(
            conn,
            [_position("SPCX", long_qty=2.0, market_value=float("inf"))],
            nlv=1500.00,
            starting_equity=1450.00,
            out_of_framework=("SPCX",),
        )
    assert _equity_deltas(conn, run.run_id) == []
    assert _swing_log_records(caplog) == []


def test_active_holding_nonfinite_nlv_degrades(conn, caplog):
    """R3 MINOR — active declared holding + non-finite broker NLV degrades cleanly.

    finite_source_nlv is None -> no fire; the run COMPLETES (not crashes) with
    None stamps so ReconciliationRun.__post_init__'s NaN/inf rejection never trips.

    Pre-fix: the non-finite NLV flows to account_equity_source_dollars and
    get_run -> __post_init__ raises ValueError (the run FAILS to read back).
    Post-fix: the run completes; account_equity_source_dollars / equity_delta_dollars
    are NULL; no swing-scoped log line.
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(
            conn,
            [_position("SPCX", long_qty=2.0, market_value=392.51)],
            nlv=float("nan"),
            starting_equity=1450.00,
            out_of_framework=("SPCX",),
        )
    assert run.state == "completed"
    assert _equity_deltas(conn, run.run_id) == []
    _journal_d, source_d, delta_d, summary_json = _run_row(conn, run.run_id)
    assert source_d is None
    assert delta_d is None
    assert _swing_log_records(caplog) == []
    assert "equity_coherence" not in json.loads(summary_json)


def test_nonfinite_ledger_degrades_no_fire_no_log(conn, caplog):
    """Codex R1 MAJOR 1 — a non-finite ledger (non-finite starting_equity) degrades.

    cfg.account.starting_equity has no finiteness validator, so a non-finite
    starting_equity propagates a non-finite ledger. finite_ledger_equity is None
    -> coherence uncomputable -> no fire, NO coherent log, and the
    account_equity_journal_dollars stamp is NULL so __post_init__'s NaN/inf
    rejection never trips at read-back.

    Pre-fix (before MAJOR-1 fix): the coherent log emits a spurious "coherent"
    line on a NaN comparison AND account_equity_journal_dollars = NaN crashes
    get_run via __post_init__. Post-fix: run COMPLETES, no fire, no log, NULL
    journal stamp.
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(
            conn,
            [_position("SPCX", long_qty=2.0, market_value=392.51)],
            nlv=1842.51,
            starting_equity=float("nan"),
            out_of_framework=("SPCX",),
        )
    assert run.state == "completed"
    assert _equity_deltas(conn, run.run_id) == []
    assert _swing_log_records(caplog) == []
    journal_d, _source_d, delta_d, _summary = _run_row(conn, run.run_id)
    assert journal_d is None
    assert delta_d is None


# --------------------------------------------------------------------------- #
# Task 3 — C3 regression locks (nothing-declared/held byte-identical) (test (d))
# --------------------------------------------------------------------------- #

def test_nothing_declared_both_flat_byte_identical(conn, caplog):
    """Test (d) — C3 LOCK (pre == post): empty declared set, both flat, drifted NLV.

    nlv = 1100.00; ledger = 1000.00; |1000-1100| = 100 > tol max(5,0.5%*1100=5.5)=5.5
    -> legacy both-flat FIRES with basis 'net_liq' (NOT the swing basis), RAW delta,
    NO equity_coherence key, NO swing-scoped log line.
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(conn, [], nlv=1100.00, starting_equity=1000.00, out_of_framework=())
    rows = _equity_deltas(conn, run.run_id)
    assert len(rows) == 1
    _expected, actual, _delta_text = rows[0]
    act = json.loads(actual)
    assert act["basis"] == "net_liq"
    assert "swing_nlv" not in act
    _journal_d, _source_d, delta_d, summary_json = _run_row(conn, run.run_id)
    assert delta_d == pytest.approx(-100.0)  # ledger 1000 - nlv 1100
    assert "equity_coherence" not in json.loads(summary_json)
    assert _swing_log_records(caplog) == []


def test_declared_set_nonempty_but_not_held_byte_identical(conn, caplog):
    """C3 (second half): declared SPCX but NOT held, both flat, drifted NLV.

    swing_scope_active = False (nothing held) -> the swing-scoped path never runs;
    fires legacy both-flat with basis 'net_liq', RAW delta, NO log line.
    """
    with caplog.at_level(logging.INFO, logger=_RECON_LOGGER):
        run = _run(conn, [], nlv=1100.00, starting_equity=1000.00,
                   out_of_framework=("SPCX",))
    rows = _equity_deltas(conn, run.run_id)
    assert len(rows) == 1
    assert json.loads(rows[0][1])["basis"] == "net_liq"
    assert _swing_log_records(caplog) == []


def test_empty_declared_set_with_position_row_suppresses_like_legacy(conn):
    """C3 (R1 MAJOR 3 lock): empty declared set + ONE held position -> suppress like legacy.

    out_of_framework=() leaves EVERY position in undeclared_positions, so
    broker_flat_swing reduces EXACTLY to legacy len(schwab_positions)==0 == False
    -> NO equity_delta. Guards against a nonzero-qty filter falsely flipping
    broker_flat_swing to True on a held position. (AAPL still banners its orphan.)
    """
    run = _run(
        conn,
        [_position("AAPL", long_qty=10.0, market_value=2000.0)],
        nlv=5000.00,
        starting_equity=1000.00,
        out_of_framework=(),
    )
    assert _equity_deltas(conn, run.run_id) == []
    orphans = conn.execute(
        "SELECT ticker FROM reconciliation_discrepancies "
        "WHERE run_id=? AND discrepancy_type='untracked_broker_position'",
        (run.run_id,),
    ).fetchall()
    assert [r[0] for r in orphans] == ["AAPL"]
