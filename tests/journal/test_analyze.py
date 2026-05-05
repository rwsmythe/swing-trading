"""Tests for `swing.journal.analyze.analyze_trade` — per-trade retrospective compute.

Brief: `docs/trade-analyze-cli-brief.md` §4.1. Branching cases:
  - manually-sourced (no candidate row before/on entry_date)
  - single pre-entry recommendation
  - multiple pre-entry recommendations (latest used for deviations)
  - excluded-only post-entry rows are filtered out
  - partial exits → shares-weighted R-multiple
  - no exits yet (open trade)
  - hypothesis_label NULL renders as None
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import ensure_schema
# B.9: Exit dataclass + insert_exit_with_event removed (Phase 7). Tests now
# go through the fills repo. analyze_trade still consumes the `_ExitLikeRow`
# shim from list_exits_for_trade — Sub-C T1 deletes the shim.
from swing.data.models import Candidate, CriterionResult, EvaluationRun, Fill, Trade
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.journal.analyze import (
    CriterionResultDisplay,
    RecommendationContext,
    TradeAnalysis,
    analyze_trade,
)


def _conn(tmp_path) -> sqlite3.Connection:
    db_path = tmp_path / "swing.db"
    return ensure_schema(db_path)


def _insert_run(
    conn: sqlite3.Connection, *, run_ts: str, action_session_date: str,
    data_asof_date: str, candidates: list[Candidate],
) -> int:
    """Insert one evaluation_run + its candidates inside a single txn."""
    run = EvaluationRun(
        id=None,
        run_ts=run_ts,
        data_asof_date=data_asof_date,
        action_session_date=action_session_date,
        finviz_csv_path=None,
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=sum(1 for c in candidates if c.bucket == "excluded"),
        error_count=sum(1 for c in candidates if c.bucket == "error"),
    )
    with conn:
        run_id = insert_evaluation_run(conn, run)
        insert_candidates(conn, run_id, candidates)
    return run_id


def _watch_candidate(
    ticker: str, *, pivot: float, close: float, initial_stop: float = 8.0,
    rs_rank: int | None = None, rs_excess: float | None = 0.5,
    extra_criteria: tuple[CriterionResult, ...] = (),
) -> Candidate:
    """Build a Candidate in the 'watch' bucket with a baseline TT/VCP layer set."""
    base = (
        CriterionResult("TT1_above_150_200", "trend_template", "pass", "ok", "rule"),
        CriterionResult("TT8_rs_rank", "trend_template", "pass", "fallback", "rule"),
        CriterionResult("proximity_20ma", "vcp", "fail", "+15.38%", "<= 5.0%"),
        CriterionResult("tightness", "vcp", "fail", "0 day streak", ">= 2 days"),
        CriterionResult("risk_feasibility", "risk", "pass", "2 sh, $6.08 risk", ">= 1 share"),
    )
    return Candidate(
        ticker=ticker, bucket="watch", close=close, pivot=pivot,
        initial_stop=initial_stop, adr_pct=5.0, tight_streak=0,
        pullback_pct=0.0, prior_trend_pct=96.0, rs_rank=rs_rank,
        rs_return_12w_vs_spy=rs_excess, rs_method="fallback_spy",
        pattern_tag=None, notes=None, criteria=base + extra_criteria,
    )


def _excluded_candidate(ticker: str, close: float) -> Candidate:
    """Open-position row written by `_step_evaluate` to keep last-close fresh."""
    return Candidate(
        ticker=ticker, bucket="excluded", close=close, pivot=None,
        initial_stop=None, adr_pct=None, tight_streak=None, pullback_pct=None,
        prior_trend_pct=None, rs_rank=None, rs_return_12w_vs_spy=None,
        rs_method="unavailable", pattern_tag=None, notes="open position",
        criteria=(),
    )


def _trade(
    conn: sqlite3.Connection, *, ticker: str, entry_date: str,
    entry_price: float, shares: int, initial_stop: float,
    hypothesis_label: str | None = None,
    watchlist_target: float | None = None,
    notes: str | None = None,
) -> int:
    """Seed a trade row + entry-fill so current_size denorm is correct.

    Goes through ``insert_trade_with_event`` + entry-fill INSERT directly
    (bypassing the entry service's pre-trade-required-fields gate, which
    these analyze-CLI tests don't exercise). Mirrors the
    ``tests/trades/test_exit.py::_seed_active_trade`` pattern.
    """
    event_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date, entry_price=entry_price,
        initial_shares=shares, initial_stop=initial_stop,
        current_stop=initial_stop, state="entered",
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=initial_stop, notes=notes,
        hypothesis_label=hypothesis_label,
        trade_origin="manual_off_pipeline",
        pre_trade_locked_at=event_ts,
    )
    with conn:
        trade_id = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale=None,
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=trade_id,
                fill_datetime=event_ts, action="entry",
                quantity=float(shares), price=entry_price,
            ),
            event_ts=event_ts,
        )
    return trade_id


def _exit(
    conn: sqlite3.Connection, *, trade_id: int, exit_date: str,
    exit_price: float, shares: int, reason: str,
    realized_pnl: float, r_multiple: float,
) -> None:
    """Insert a non-entry fill + transition state when fully exited.

    B.9: the exit service (``swing.trades.exit.record_exit``) is the
    canonical path, but it requires a typed ExitReason; for the small
    fixed reason strings these tests use, we go through the fills repo
    directly + UPDATE state once cumulative non-entry fills cover the
    initial shares (analogous to the state-machine's full-close branch).
    Keeps the test surface minimal — analyze_trade reads the resulting
    rows the same way regardless of which service wrote them.
    """
    event_ts = f"{exit_date}T16:00:00"
    with conn:
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=trade_id,
                fill_datetime=event_ts, action="exit",
                quantity=float(shares), price=exit_price, reason=reason,
            ),
            event_ts=event_ts,
        )
        # Mirror the state machine: when cumulative non-entry quantity
        # equals or exceeds initial_shares, the trade is closed.
        row = conn.execute(
            "SELECT initial_shares, "
            "  COALESCE((SELECT SUM(quantity) FROM fills "
            "            WHERE trade_id = ? AND action != 'entry'), 0) "
            "FROM trades WHERE id = ?",
            (trade_id, trade_id),
        ).fetchone()
        if row is not None and row[1] >= row[0]:
            conn.execute(
                "UPDATE trades SET state='closed' WHERE id=?", (trade_id,),
            )


# --- core happy path: VIR-like single-rec / closed / loss --------------------


def test_analyze_returns_dataclass_for_known_trade(tmp_path):
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-19T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75, initial_stop=8.26)],
    )
    tid = _trade(
        conn, ticker="VIR", entry_date="2026-04-20", entry_price=11.30,
        shares=2, initial_stop=8.26,
        hypothesis_label="sub-A+ VCP-not-formed test",
        watchlist_target=10.76, notes="trade test",
    )
    _exit(
        conn, trade_id=tid, exit_date="2026-04-24", exit_price=10.30,
        shares=2, reason="stop-hit", realized_pnl=-2.0, r_multiple=-0.32894737,
    )

    a = analyze_trade(conn, tid)
    assert isinstance(a, TradeAnalysis)
    assert a.trade_id == tid
    assert a.ticker == "VIR"
    assert a.entry_price == pytest.approx(11.30)
    assert a.initial_shares == 2
    assert a.status == "closed"
    assert a.hypothesis_label == "sub-A+ VCP-not-formed test"
    assert a.notes == "trade test"
    # Exactly one usable recommendation, all wired through
    assert len(a.recommendations) == 1
    rec = a.recommendations[0]
    assert isinstance(rec, RecommendationContext)
    assert rec.bucket == "watch"
    assert rec.pivot == pytest.approx(10.76)
    assert rec.initial_stop == pytest.approx(8.26)
    # Criteria preserved layer/result/value
    crit_by_name = {c.criterion_name: c for c in rec.criteria}
    assert crit_by_name["proximity_20ma"].result == "fail"
    assert crit_by_name["proximity_20ma"].layer == "vcp"
    # Deviations against the latest pre-entry rec
    assert a.days_rec_to_entry == 0          # action_session 2026-04-20 vs entry 2026-04-20
    assert a.pct_above_pivot == pytest.approx(0.05018587, abs=1e-5)  # (11.30-10.76)/10.76
    assert a.stop_dev_pct == pytest.approx(0.0, abs=1e-9)  # 8.26 vs 8.26
    # Outcomes: single full exit
    assert len(a.exits) == 1
    assert a.realized_pnl_total == pytest.approx(-2.0)
    assert a.r_multiple_avg == pytest.approx(-0.32894737, abs=1e-5)


def test_criterion_display_carries_value_and_rule(tmp_path):
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-19T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("AAA", pivot=100.0, close=99.0)],
    )
    tid = _trade(conn, ticker="AAA", entry_date="2026-04-20",
                 entry_price=101.0, shares=1, initial_stop=95.0)
    a = analyze_trade(conn, tid)
    crit = {c.criterion_name: c for c in a.recommendations[0].criteria}
    assert isinstance(crit["proximity_20ma"], CriterionResultDisplay)
    assert crit["proximity_20ma"].value == "+15.38%"
    assert crit["proximity_20ma"].rule == "<= 5.0%"


# --- multi-recommendation: latest pre-entry wins for deviations --------------


def test_multiple_pre_entry_recs_use_latest_for_deviations(tmp_path):
    conn = _conn(tmp_path)
    # Earlier rec (lower pivot)
    _insert_run(
        conn, run_ts="2026-04-17T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-16",
        candidates=[_watch_candidate("VIR", pivot=10.60, close=10.33, initial_stop=8.26)],
    )
    # Later rec (higher pivot) — should be the deviation reference
    _insert_run(
        conn, run_ts="2026-04-19T18:47:34",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75, initial_stop=8.26)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)

    a = analyze_trade(conn, tid)
    # Both recs surfaced
    assert len(a.recommendations) == 2
    # Chronological order
    assert a.recommendations[0].pivot == pytest.approx(10.60)
    assert a.recommendations[1].pivot == pytest.approx(10.76)
    # Deviation uses the later (10.76) pivot
    assert a.pct_above_pivot == pytest.approx(0.05018587, abs=1e-5)


def test_excluded_post_entry_rows_are_filtered(tmp_path):
    """`excluded` rows with notes='open position' are bookkeeping, not recs."""
    conn = _conn(tmp_path)
    # One real rec pre-entry
    _insert_run(
        conn, run_ts="2026-04-19T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75)],
    )
    # Then post-entry excluded rows (open-position bookkeeping)
    _insert_run(
        conn, run_ts="2026-04-20T17:00:00",
        action_session_date="2026-04-21", data_asof_date="2026-04-20",
        candidates=[_excluded_candidate("VIR", close=11.09)],
    )
    _insert_run(
        conn, run_ts="2026-04-21T17:00:00",
        action_session_date="2026-04-22", data_asof_date="2026-04-21",
        candidates=[_excluded_candidate("VIR", close=10.83)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)

    a = analyze_trade(conn, tid)
    # Only the pre-entry watch rec surfaces; excluded post-entry rows filtered
    assert len(a.recommendations) == 1
    assert a.recommendations[0].bucket == "watch"


def test_pre_entry_excluded_also_filtered(tmp_path):
    """Filter by bucket regardless of timing — excluded is never useful."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-15T18:00:00",
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        candidates=[_excluded_candidate("VIR", close=10.0)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)

    a = analyze_trade(conn, tid)
    # No usable recommendations; treated as manually-sourced
    assert a.recommendations == ()
    assert a.days_rec_to_entry is None
    assert a.pct_above_pivot is None
    assert a.stop_dev_pct is None


# --- manually-sourced trade ---------------------------------------------------


def test_manually_sourced_trade_returns_empty_recs_and_none_deviations(tmp_path):
    conn = _conn(tmp_path)
    tid = _trade(
        conn, ticker="ZZZ", entry_date="2026-04-20", entry_price=50.0,
        shares=10, initial_stop=45.0, hypothesis_label="manual entry",
    )
    a = analyze_trade(conn, tid)
    assert a.recommendations == ()
    assert a.days_rec_to_entry is None
    assert a.pct_above_pivot is None
    assert a.stop_dev_pct is None
    # Output-bearing fields still populated
    assert a.ticker == "ZZZ"
    assert a.hypothesis_label == "manual entry"
    assert a.exits == ()
    assert a.realized_pnl_total == 0.0
    assert a.r_multiple_avg is None  # no exits → undefined


def test_manually_sourced_trade_with_only_post_entry_candidate_is_manual(tmp_path):
    """Per brief §8: if ticker only appears in candidates AFTER entry, it's
    still manually-sourced from the analysis perspective."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-22T18:00:00",
        action_session_date="2026-04-23", data_asof_date="2026-04-22",
        candidates=[_watch_candidate("ZZZ", pivot=55.0, close=54.0)],
    )
    tid = _trade(conn, ticker="ZZZ", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    a = analyze_trade(conn, tid)
    assert a.recommendations == ()
    assert a.pct_above_pivot is None


# --- partial exits ------------------------------------------------------------


def test_partial_exits_share_weighted_r_multiple(tmp_path):
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="AAA", entry_date="2026-04-15",
                 entry_price=100.0, shares=10, initial_stop=95.0)
    # 6 shares exit at +2R; 4 shares at -1R
    _exit(conn, trade_id=tid, exit_date="2026-04-18", exit_price=110.0,
          shares=6, reason="target", realized_pnl=60.0, r_multiple=2.0)
    _exit(conn, trade_id=tid, exit_date="2026-04-22", exit_price=95.0,
          shares=4, reason="stop-hit", realized_pnl=-20.0, r_multiple=-1.0)

    a = analyze_trade(conn, tid)
    assert len(a.exits) == 2
    # Shares-weighted: (6*2.0 + 4*-1.0) / (6 + 4) = 8/10 = 0.8
    assert a.r_multiple_avg == pytest.approx(0.8)
    assert a.realized_pnl_total == pytest.approx(40.0)


# --- hypothesis_label NULL ----------------------------------------------------


def test_null_hypothesis_label_renders_as_none(tmp_path):
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="AAA", entry_date="2026-04-15",
                 entry_price=100.0, shares=1, initial_stop=95.0,
                 hypothesis_label=None)
    a = analyze_trade(conn, tid)
    assert a.hypothesis_label is None


# --- error path ---------------------------------------------------------------


def test_missing_trade_raises(tmp_path):
    conn = _conn(tmp_path)
    with pytest.raises(ValueError):
        analyze_trade(conn, 999)


# --- Phase 7 C.11: state surfaced raw + status derived for CLI compat --------


def test_c11_trade_analysis_state_carries_raw_phase7_vocab(tmp_path):
    """C.11: TradeAnalysis.state carries the raw lifecycle string from
    trade.state (Phase 7 5-state vocab: entered|managing|partial_exited|
    closed|reviewed). This preserves the operator-facing detail B.9
    surfaced in the CLI ``Status:`` line.

    Discriminating: a closed-only field would lose 'entered' vs 'managing'
    distinction. The state field MUST surface the raw string unchanged.
    """
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="ZZZ", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    a = analyze_trade(conn, tid)
    assert a.state == "entered", (
        f"expected state='entered' (mirrors trade.state); got {a.state!r}"
    )


def test_c11_trade_analysis_status_derived_open_for_active_states(tmp_path):
    """C.11: TradeAnalysis.status derives legacy 'open'/'closed' from
    trade.state for CLI-comparison compatibility. The active states
    {entered, managing, partial_exited} → 'open'.

    Discriminating: under raw-state assignment status='entered'/'managing'
    /'partial_exited', the CLI's ``a.status == 'open'`` comparisons would
    NEVER match → the hold-duration block falls through to the data-anomaly
    branch even on healthy live trades.
    """
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="AAA", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    # No exits; trade is in 'entered'.
    a = analyze_trade(conn, tid)
    assert a.state == "entered"
    assert a.status == "open", (
        f"expected derived status='open' for state='entered'; got "
        f"{a.status!r}. CLI's a.status=='open' comparison depends on this."
    )


def test_c11_trade_analysis_status_partial_exited_is_open(tmp_path):
    """C.11: state='partial_exited' is active → derived status='open'."""
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="BBB", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    # Partial exit — half the shares — leaves the trade in 'managing' or
    # 'partial_exited' depending on the entry/exit fixture; force the row.
    with conn:
        conn.execute(
            "UPDATE trades SET state='partial_exited' WHERE id=?", (tid,),
        )
    a = analyze_trade(conn, tid)
    assert a.state == "partial_exited"
    assert a.status == "open"


def test_c11_trade_analysis_status_managing_is_open(tmp_path):
    """C.11: state='managing' is active → derived status='open'."""
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="CCC", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    with conn:
        conn.execute(
            "UPDATE trades SET state='managing' WHERE id=?", (tid,),
        )
    a = analyze_trade(conn, tid)
    assert a.state == "managing"
    assert a.status == "open"


def test_c11_trade_analysis_status_closed_is_closed(tmp_path):
    """C.11: state='closed' → derived status='closed'."""
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="DDD", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    with conn:
        conn.execute(
            "UPDATE trades SET state='closed' WHERE id=?", (tid,),
        )
    a = analyze_trade(conn, tid)
    assert a.state == "closed"
    assert a.status == "closed"


def test_c11_trade_analysis_status_reviewed_is_closed(tmp_path):
    """C.11: state='reviewed' is closed-or-reviewed → derived status='closed'.

    Discriminating: under raw-state assignment status='reviewed', the CLI's
    hold-duration ``a.status == 'closed'`` branch would not fire even after
    the operator completed a post-trade review.
    """
    conn = _conn(tmp_path)
    tid = _trade(conn, ticker="EEE", entry_date="2026-04-20",
                 entry_price=50.0, shares=10, initial_stop=45.0)
    with conn:
        conn.execute(
            "UPDATE trades SET state='reviewed' WHERE id=?", (tid,),
        )
    a = analyze_trade(conn, tid)
    assert a.state == "reviewed"
    assert a.status == "closed", (
        f"expected derived status='closed' for state='reviewed'; got "
        f"{a.status!r}. CLI's hold-duration branch depends on this."
    )


# --- DB read-only safety ------------------------------------------------------


def test_recommendations_with_fractional_second_run_ts_on_entry_date_included(tmp_path):
    """Adversarial R2 M1: the upper bound must accept run_ts strings with
    sub-second precision stamped anywhere within entry_date. Inclusive
    string compare against 'entry_dateT23:59:59' would silently drop them."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-20T23:59:59.500",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75,
                                     initial_stop=8.26)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)
    a = analyze_trade(conn, tid)
    assert len(a.recommendations) == 1
    assert a.pct_above_pivot is not None  # deviation math available


def test_recommendations_with_z_suffix_run_ts_on_entry_date_included(tmp_path):
    """R2 M1: also handle the `Z` UTC suffix variant."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-20T23:59:59Z",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)
    a = analyze_trade(conn, tid)
    assert len(a.recommendations) == 1


def test_recommendations_with_next_day_run_ts_excluded(tmp_path):
    """R2 M1: ensure the new exclusive bound does NOT silently sweep in the
    following day's runs."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-21T00:00:00",
        action_session_date="2026-04-21", data_asof_date="2026-04-20",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)
    a = analyze_trade(conn, tid)
    assert a.recommendations == ()


def test_malformed_entry_date_raises(tmp_path):
    """R3 M1: surface a malformed `trades.entry_date` as a clear
    `ValueError` rather than silently degrading to 'manually-sourced'.
    Silent fallback would hide data corruption from the operator."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-19T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75)],
    )
    # Manually insert a trade with a malformed entry_date via raw SQL — the
    # repo would refuse, but production data could in principle have it.
    # B.9: 'status' column dropped (migration 0014); use 'state' + the
    # NOT-NULL Phase 7 lifecycle columns.
    with conn:
        conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, notes, "
            "trade_origin, pre_trade_locked_at, current_size) "
            "VALUES ('VIR', 'not-a-date', 11.30, 2, 8.26, 8.26, 'entered', "
            "NULL, 'manual_off_pipeline', '2026-04-20T09:30:00', 2)"
        )
        tid = conn.execute(
            "SELECT id FROM trades WHERE entry_date='not-a-date'"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
            "VALUES (?, '2026-04-20T09:30:00', 'entry', '{}')",
            (tid,),
        )
    with pytest.raises(ValueError, match="entry_date"):
        analyze_trade(conn, tid)


def test_analyze_does_not_mutate_db(tmp_path):
    """Brief §5 watch item: function must be read-only."""
    conn = _conn(tmp_path)
    _insert_run(
        conn, run_ts="2026-04-19T18:00:00",
        action_session_date="2026-04-20", data_asof_date="2026-04-17",
        candidates=[_watch_candidate("VIR", pivot=10.76, close=10.75)],
    )
    tid = _trade(conn, ticker="VIR", entry_date="2026-04-20",
                 entry_price=11.30, shares=2, initial_stop=8.26)
    _exit(conn, trade_id=tid, exit_date="2026-04-24", exit_price=10.30,
          shares=2, reason="stop-hit", realized_pnl=-2.0,
          r_multiple=-0.32894737)

    # B.9: 'exits' table dropped in migration 0014; replaced by 'fills'.
    tables = ("trades", "fills", "candidates", "candidate_criteria",
              "evaluation_runs", "trade_events")
    before_counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in tables
    }
    analyze_trade(conn, tid)
    after_counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in tables
    }
    assert before_counts == after_counts
