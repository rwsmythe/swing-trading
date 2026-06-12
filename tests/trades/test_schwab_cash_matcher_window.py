"""Arc 4b Task 7 — the journal→source matcher fix (±4-day shared window)."""
from swing.trades.schwab_reconciliation import _within_cash_match_window


def test_window_inclusive_4_days():
    assert _within_cash_match_window("2026-05-28", "2026-06-01", days=4) is True   # 4 off
    assert _within_cash_match_window("2026-05-28", "2026-06-02", days=4) is False  # 5 off
    assert _within_cash_match_window("2026-05-28", "2026-05-24", days=4) is True   # -4 off


def test_step7_neighbor_date_no_longer_mismatches(cash_recon_full):
    # journal 2026-05-28 $100 deposit; Schwab ACH_RECEIPT $100 on 2026-05-29.
    # Pre-fix: emits cash_movement_mismatch (the live 66/67 class). Post-fix: ZERO.
    conn, result = cash_recon_full(
        journal_cash=[("2026-05-28", "deposit", 100.0, None)],
        schwab_txs=[("ACH_RECEIPT", "2026-05-29", 100.0)],
        nlv=1000.0, open_trades=0)
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies d "
        "JOIN reconciliation_runs r ON d.run_id=r.run_id "
        "WHERE d.discrepancy_type='cash_movement_mismatch' "
        "AND d.field_name='net_amount'").fetchone()[0]
    assert n == 0


def test_step7_genuine_mismatch_still_emits(cash_recon_full):
    # A journal deposit with NO Schwab counterpart in ±4d still emits (the
    # widened predicate must not suppress genuine drift).
    conn, result = cash_recon_full(
        journal_cash=[("2026-05-10", "deposit", 250.0, "MANUALREF")],
        schwab_txs=[],
        nlv=1000.0, open_trades=0)
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='cash_movement_mismatch' "
        "AND field_name='net_amount'").fetchone()[0]
    assert n == 1


def test_step7_income_kind_matches_dividend_or_interest(cash_recon_full):
    # An operator-entered interest row matches a positive DIVIDEND_OR_INTEREST
    # within ±4d (the widened kind->type map) -> no mismatch.
    conn, result = cash_recon_full(
        journal_cash=[("2026-05-12", "interest", 3.0, "TXI1")],
        schwab_txs=[("DIVIDEND_OR_INTEREST", "2026-05-12", 3.0, "TXI1", "INT")],
        nlv=1000.0, open_trades=0)
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='cash_movement_mismatch' "
        "AND field_name='net_amount'").fetchone()[0]
    assert n == 0
