from __future__ import annotations
import pytest
from swing.data.repos.pattern_evaluations import get_evaluation_by_id
from swing.data.repos.trades import get_trade
from swing.trades.entry import record_entry
from swing.trades.origin import EntryPath
# Reuse the EXISTING real-callsite watch-backlink harness (avoids re-pinning the
# 25-field EntryRequest + drives the production record_entry path verbatim).
from tests.trades.test_entry_populates_candidate_backlinks import (
    _seed_v21, _seed_pipeline_with_watch_candidate, _req)


def test_watch_ticker_backlink_resolves_via_record_entry(tmp_path):
    """A trade entered on a WATCH ticker must still auto-link to its detection's
    PE row (an IMPROVEMENT; changes no displayed statistic). Drives the REAL
    end-to-end record_entry service on a watch-origin PE, so a future
    blanket-isolation that filtered the entry anchor->candidate resolution to
    aplus-only would FAIL here. Passes both before AND after the aggregate/queue
    isolation (Tasks 2-4) -- axis: intended-exception-vs-blanket-isolation."""
    conn = _seed_v21(tmp_path)
    try:
        _eval_run_id, _pipeline_run_id, watch_pe_id = (
            _seed_pipeline_with_watch_candidate(conn))   # bucket='watch'
        result = record_entry(
            conn, _req(entry_path=EntryPath.HYP_RECS_BUTTON,
                       pattern_evaluation_id=watch_pe_id),
            soft_warn=10, hard_cap=20, force=False)
        trade = get_trade(conn, result.trade_id)
        # The real entry path bound the WATCH candidate + PE (NOT isolated away):
        assert trade is not None
        assert trade.candidate_id is not None
        assert trade.pattern_evaluation_id == watch_pe_id
        # The by-id repo primitive also resolves the watch PE (NOT None).
        got = get_evaluation_by_id(conn, watch_pe_id)
        assert got is not None and got.ticker == "ABC"
    finally:
        conn.close()
