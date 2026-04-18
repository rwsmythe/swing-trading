from __future__ import annotations

from swing.data.models import Candidate
from swing.recommendations.focus_ranking import rank_focus, FocusWeights


def _c(t: str, *, close: float, pivot: float, adr: float, trend: float) -> Candidate:
    return Candidate(
        ticker=t, bucket="aplus", close=close, pivot=pivot,
        initial_stop=close * 0.95, adr_pct=adr, tight_streak=3,
        pullback_pct=10.0, prior_trend_pct=trend, rs_rank=80,
        rs_return_12w_vs_spy=0.15, rs_method="universe",
        pattern_tag=None, notes=None, criteria=(),
    )


def test_ranking_orders_by_composite():
    cands = [
        _c("BEST", close=100.5, pivot=101.0, adr=6.0, trend=50.0),
        _c("MID",  close=100.0, pivot=102.0, adr=5.0, trend=40.0),
        _c("LOW",  close=98.0,  pivot=104.0, adr=4.0, trend=30.0),
    ]
    ranked = rank_focus(cands, weights=FocusWeights(
        closeness_to_pivot=0.5, adr=0.25, prior_trend=0.25,
    ))
    assert [c.ticker for c in ranked] == ["BEST", "MID", "LOW"]


def test_ranking_breaks_ties_by_ticker():
    cands = [
        _c("MSFT", close=100.0, pivot=101.0, adr=5.0, trend=40.0),
        _c("AAPL", close=100.0, pivot=101.0, adr=5.0, trend=40.0),
    ]
    ranked = rank_focus(cands, weights=FocusWeights(0.5, 0.25, 0.25))
    assert [c.ticker for c in ranked] == ["AAPL", "MSFT"]


def test_empty_input_returns_empty():
    assert rank_focus([], weights=FocusWeights(0.5, 0.25, 0.25)) == []


def test_single_input_unchanged():
    c = _c("AAPL", close=100.0, pivot=101.0, adr=5.0, trend=40.0)
    assert rank_focus([c], weights=FocusWeights(0.5, 0.25, 0.25)) == [c]
