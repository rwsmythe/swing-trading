"""Arc 4b Task 6 — auto-ingest classifier + dedup ladder + source-direction emit.

SYNTHETIC fixtures mirror the REAL SchwabTransactionResponse emitter shape (ISO
transaction_date, str transaction_id, float net_amount, optional description).
"""
import json

import pytest

from swing.integrations.schwab.models import SchwabTransactionResponse
from swing.trades.schwab_reconciliation import (
    _classify_cash_transaction,
    _ingest_cash_transactions,
)


def _tx(tid, date, ttype, amt, desc=None):
    return SchwabTransactionResponse(
        transaction_id=str(tid), transaction_date=date, type=ttype,
        net_amount=amt, description=desc)


# --- classifier (pure function) -------------------------------------------


def test_classifier_trade_skips_by_design():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "TRADE", 500.0))
    assert d.action == "skip"


def test_classifier_zero_amount_electronic_fund_skips():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "ELECTRONIC_FUND", 0.0))
    assert d.action == "skip"


def test_classifier_ach_receipt_is_deposit_candidate():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "ACH_RECEIPT", 100.0))
    assert d.action == "candidate" and d.kind == "deposit"


def test_classifier_ach_disbursement_is_withdraw_candidate():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "ACH_DISBURSEMENT", -50.0))
    assert d.action == "candidate" and d.kind == "withdraw"


def test_classifier_electronic_fund_sign_routes():
    pos = _classify_cash_transaction(_tx(1, "2026-06-01", "ELECTRONIC_FUND", 10.0))
    neg = _classify_cash_transaction(_tx(1, "2026-06-01", "ELECTRONIC_FUND", -10.0))
    assert pos.kind == "deposit"
    assert neg.kind == "withdraw"


def test_classifier_unrecognized_dividend_flags_tier2():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "DIVIDEND_OR_INTEREST", 5.0, "MYSTERY"))
    assert d.action == "flag" and d.flag_reason == "unrecognized_income_description"


def test_classifier_negative_income_flags_tier2():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "DIVIDEND_OR_INTEREST", -5.0, "FEE-SHAPED"))
    assert d.action == "flag" and d.flag_reason == "negative_income_amount"


def test_classifier_memorandum_nonzero_skip_warns():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "MEMORANDUM", 3.0))
    assert d.action == "skip_warn"


def test_classifier_trade_correction_nonzero_skip_warns_not_silent():
    # Codex R5 — TRADE_CORRECTION is NOT granted silent trade-skip (the spec §4.1
    # table covers only TRADE + RECEIVE_AND_DELIVER); a nonzero one surfaces.
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "TRADE_CORRECTION", -12.0))
    assert d.action == "skip_warn"


def test_ingest_trade_correction_nonzero_warns_no_trade_count(cash_recon_run):
    conn, run_id = cash_recon_run
    warnings = []
    c = _ingest_cash_transactions(
        conn, run_id=run_id,
        schwab_transactions=[_tx(900042, "2026-06-01", "TRADE_CORRECTION", -12.0)],
        price_tolerance=0.01, cash_warnings=warnings)
    assert c["cash_skipped_trade_count"] == 0  # NOT counted as a trade skip
    assert c["cash_ingested_count"] == 0
    assert any(w.get("reason") == "skipped_nonzero_noncash" for w in warnings)


# --- dedup ladder ----------------------------------------------------------


def test_ingest_inserts_unmatched_then_is_idempotent(cash_recon_run):
    conn, run_id = cash_recon_run
    txs = [_tx(900001, "2026-06-01", "ACH_RECEIPT", 100.0)]
    c1 = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                   price_tolerance=0.01, cash_warnings=[])
    assert c1["cash_ingested_count"] == 1
    c2 = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                   price_tolerance=0.01, cash_warnings=[])
    assert c2["cash_ingested_count"] == 0 and c2["cash_matched_by_ref_count"] == 1
    n = conn.execute("SELECT COUNT(*) FROM cash_movements WHERE ref='900001'").fetchone()[0]
    assert n == 1  # ZERO duplicates


def test_fallback_matches_refless_row_within_4_days_no_write(cash_recon_run):
    conn, run_id = cash_recon_run
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'manual 4a')")
    txs = [_tx(900002, "2026-05-29", "ACH_RECEIPT", 100.0)]
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_matched_by_fallback_count"] == 1 and c["cash_ingested_count"] == 0
    assert conn.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 1


def test_fallback_5_days_off_does_not_match_ingests_new(cash_recon_run):
    conn, run_id = cash_recon_run
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'manual')")
    txs = [_tx(900003, "2026-06-02", "ACH_RECEIPT", 100.0)]  # 5 days off
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_matched_by_fallback_count"] == 0 and c["cash_ingested_count"] == 1


def test_multi_candidate_fallback_flags_tier2_no_write(cash_recon_run):
    conn, run_id = cash_recon_run
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'a')")
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-29','deposit',100.0,NULL,'b')")
    txs = [_tx(900004, "2026-05-28", "ACH_RECEIPT", 100.0)]
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_flagged_count"] == 1 and c["cash_ingested_count"] == 0
    row = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM reconciliation_discrepancies "
        "WHERE field_name='missing_journal_row'").fetchone()
    exp, act = json.loads(row[0]), json.loads(row[1])
    assert act == {"matched": None}  # sole-key shape (load-bearing)
    assert exp["flag_reason"] == "fallback_multi_match"
    assert sorted(exp["candidate_cash_movement_ids"])  # candidate ids carried
    # Codex R3 — the classified kind is persisted for the exact-kind resolver check.
    assert exp["expected_kind"] == "deposit"


def test_two_unmatched_in_one_run_emit_two_rows(cash_recon_run):
    conn, run_id = cash_recon_run
    txs = [_tx(900005, "2026-06-01", "DIVIDEND_OR_INTEREST", 5.0, "MYSTERY-A"),
           _tx(900006, "2026-06-01", "DIVIDEND_OR_INTEREST", 6.0, "MYSTERY-B")]
    _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                              price_tolerance=0.01, cash_warnings=[])
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE field_name='missing_journal_row'").fetchone()[0]
    assert n == 2  # dedup_key_override prevents the {"matched":null} collision


def test_trade_with_nonzero_amount_creates_no_row(cash_recon_run):
    conn, run_id = cash_recon_run
    txs = [_tx(900007, "2026-06-01", "TRADE", -134.85)]
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_ingested_count"] == 0 and c["cash_skipped_trade_count"] == 1
    assert conn.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 0


# --- coverage-gap (end-to-end) ---------------------------------------------


def test_coverage_gap_warns_on_uncovered_span(cash_recon_full):
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=1000.0, open_trades=0, broker_positions=[],
        prior_completed_period_end="2026-05-01", period_start="2026-05-20")
    summary = json.loads(run.summary_json)
    assert any(w.get("reason") == "coverage_gap" for w in summary.get("cash_warnings", []))


def test_no_coverage_gap_when_contiguous(cash_recon_full):
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=1000.0, open_trades=0, broker_positions=[],
        prior_completed_period_end="2026-05-25", period_start="2026-05-20")
    summary = json.loads(run.summary_json)
    assert not any(w.get("reason") == "coverage_gap" for w in summary.get("cash_warnings", []))


# --- marker deferral visibility (operator decision 2026-06-11) -------------


@pytest.mark.skip(reason="pending real DIVIDEND_OR_INTEREST payload capture — plan Task 6 §item-2")
def test_dividend_marker_set_is_real_payload_sourced():
    # Operator shipped EMPTY marker frozensets (no live dividend/interest history
    # at the 2026-06-11 epoch). When a real payload is captured (Task 11 runbook
    # step 2), seed the frozensets + unskip + assert the real markers classify.
    from swing.trades.schwab_reconciliation import _DIVIDEND_MARKERS, _INTEREST_MARKERS
    assert _DIVIDEND_MARKERS or _INTEREST_MARKERS
