"""Arc 4b Task 8 — ledger-vs-NLV equity coherence (flat-only, max($5,0.5%) tol)."""
import json

import pytest

from swing.trades.schwab_reconciliation import _cash_coherence_tolerance


def test_tolerance_is_max_of_5_and_half_pct():
    assert _cash_coherence_tolerance(100.0) == 5.0          # 0.5% = 0.50 < 5
    assert _cash_coherence_tolerance(2000.0) == 10.0        # 0.5% = 10 > 5


def test_coherence_silent_within_tolerance(cash_recon_full):
    # FLOOR-binding boundary: ledger 1000.00 vs NLV 995.01 -> Δ=$4.99.
    # tolerance = max($5, 0.5%×995.01=$4.975) = $5.00; 4.99 < 5.00 -> silent.
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=995.01, open_trades=0, broker_positions=[])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0


def test_coherence_warns_past_tolerance(cash_recon_full):
    # FLOOR-binding boundary: ledger 1000.00 vs NLV 994.99 -> Δ=$5.01.
    # tolerance = max($5, 0.5%×994.99=$4.975) = $5.00; 5.01 > 5.00 -> emits.
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=994.99, open_trades=0, broker_positions=[])
    row = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='equity_delta'").fetchone()
    assert row is not None
    exp, act = json.loads(row[0]), json.loads(row[1])
    assert exp["basis"] == "ledger" and act["basis"] == "net_liq"


def test_coherence_suppressed_with_open_trade(cash_recon_full):
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=5000.0, open_trades=1, broker_positions=[("AAPL", 10)])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0  # not flat -> no check


def test_coherence_orphan_position_suppresses_and_warns(cash_recon_full):
    # journal-flat but broker has a position -> suppress check, warn.
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=5000.0, open_trades=0, broker_positions=[("AAPL", 10)])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0
    summary = json.loads(run.summary_json)
    assert any("orphan" in w.get("reason", "") for w in summary.get("cash_warnings", []))


def test_equity_delta_render_tolerates_basis_keys():
    from swing.trades.reconciliation_render import build_compared_pairs
    pairs = build_compared_pairs(
        "equity_delta",
        {"equity_dollars": 1000.0, "basis": "ledger"},
        {"equity_dollars": 1005.0, "basis": "net_liq"})
    assert pairs == [("equity dollars", 1000.0, 1005.0)]


def test_completed_run_stores_ledger_equity_not_stale_snapshot(cash_recon_full):
    # After auto-ingesting a $100 deposit at flat, the completed run row's
    # account_equity_journal_dollars must equal the LEDGER equity (starting +
    # realized + net cash), NOT a pre-run snapshot-derived value.
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[],
        schwab_txs=[("ACH_RECEIPT", "2026-05-29", 100.0, "900099")],
        nlv=1100.0, open_trades=0, broker_positions=[])
    row = conn.execute(
        "SELECT account_equity_journal_dollars, equity_delta_dollars "
        "FROM reconciliation_runs WHERE run_id=?", (run.run_id,)).fetchone()
    # ledger = 1000 starting + 0 realized + 100 ingested deposit = 1100.
    assert row[0] == pytest.approx(1100.0)
    assert row[1] == pytest.approx(0.0)  # ledger 1100 - NLV 1100
