"""Recommendation builder: combines candidates + watchlist + equity → DailyRecommendation list."""
from __future__ import annotations

from swing.data.models import Candidate, DailyRecommendation, WatchlistEntry
from swing.recommendations.build import build_recommendations, BuildContext


def _candidate(ticker: str, bucket: str = "aplus", *, close: float = 100.0,
               pivot: float = 100.5, stop: float = 95.0) -> Candidate:
    return Candidate(
        ticker=ticker, bucket=bucket, close=close, pivot=pivot,
        initial_stop=stop, adr_pct=5.0, tight_streak=3, pullback_pct=10.0,
        prior_trend_pct=30.0, rs_rank=85, rs_return_12w_vs_spy=0.20,
        rs_method="universe", pattern_tag=None, notes=None, criteria=(),
    )


def _wl(ticker: str, target: float = 100.5, last_close: float = 100.0) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-12", last_qualified_date="2026-04-15",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-15", entry_target=target,
        initial_stop_target=95.0, last_close=last_close, last_pivot=target,
        last_stop=95.0, last_adr_pct=5.0, missing_criteria=None, notes=None,
    )


def test_aplus_becomes_today_decision():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("NVDA", "aplus")],
        prior_watchlist=[],
    )
    assert len(recs) == 1
    rec = recs[0]
    assert rec.ticker == "NVDA"
    assert rec.recommendation == "today_decision"
    assert rec.shares is not None and rec.shares > 0
    assert rec.action_text and "Buy-stop" in rec.action_text
    assert rec.entry_target == 100.5


def test_aplus_action_text_does_not_say_limit():
    # The persisted recommendation carries only a stop price; "Buy-stop limit"
    # implied a two-price broker order we never produce. Regression test for
    # Tranche B-ops session 1 spec §1.
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("NVDA", "aplus")],
        prior_watchlist=[],
    )
    assert len(recs) == 1
    text = recs[0].action_text or ""
    assert "Buy-stop" in text
    assert "limit" not in text.lower()


def test_watchlist_near_trigger_recommended():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx, today_aplus=[],
        prior_watchlist=[_wl("MSFT", target=100.0, last_close=99.7)],
    )
    near = [r for r in recs if r.recommendation == "near_trigger"]
    assert len(near) == 1
    assert near[0].ticker == "MSFT"


def test_aplus_already_on_watchlist_yields_only_today_decision_not_double():
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("NVDA", "aplus", close=99.7, pivot=100.0)],
        prior_watchlist=[_wl("NVDA", target=100.0, last_close=99.7)],
    )
    nvda_recs = [r for r in recs if r.ticker == "NVDA"]
    types = {r.recommendation for r in nvda_recs}
    assert types == {"today_decision"}


def test_infeasible_sizing_still_produces_today_decision_with_zero_shares():
    """Spec says today_decision is the immutable snapshot — even infeasible names get listed."""
    ctx = BuildContext(
        evaluation_run_id=1, data_asof_date="2026-04-15",
        action_session_date="2026-04-16", current_equity=1200.0,
        max_risk_pct=0.005, position_pct_cap=0.15,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[_candidate("WIDE", "aplus", close=100.0, pivot=100.0, stop=50.0)],
        prior_watchlist=[],
    )
    assert len(recs) == 1
    assert recs[0].shares == 0
    assert "infeasible" in (recs[0].action_text or "").lower() or recs[0].risk_dollars == 0.0
