from swing.data.models import Candidate, CriterionResult, WatchlistEntry
from swing.watchlist.service import AGING_STREAK_THRESHOLD, compute_watchlist_changes


def _failing_candidate(ticker: str, *, bucket="skip", close=12.0) -> Candidate:
    crits = tuple(
        CriterionResult(criterion_name=n, layer="vcp", result="fail", value=None, rule=None)
        for n in
        ("prior_trend", "ma_stack_10_20_50", "ma_short_rising", "adr",
         "pullback", "orderliness", "risk_feasibility")
    )
    return Candidate(
        ticker=ticker, bucket=bucket, close=close, pivot=None, initial_stop=None,
        adr_pct=2.0, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes="", criteria=crits,
    )


def _prior(ticker: str, *, streak: int, pinned: bool, **kw) -> WatchlistEntry:
    base = dict(
        ticker=ticker, added_date="2026-06-01", last_qualified_date="2026-06-05",
        status="watch", qualification_count=2, not_qualified_streak=streak,
        last_data_asof_date="2026-06-09", entry_target=10.0, initial_stop_target=9.0,
        last_close=10.5, last_pivot=10.0, last_stop=9.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None, pinned=pinned, pin_note=("n" if pinned else None),
        pinned_at=("2026-06-10T00:00:00" if pinned else None),
    )
    base.update(kw)
    return WatchlistEntry(**base)


def test_pinned_ticker_vetoes_age_off_and_keeps_streak_honest():
    """DISCRIMINATING: prior streak=2, threshold=3, candidate fails → new_streak=3.
    PINNED: zero removes; ONE streak_increment carrying not_qualified_streak==3
    (NOT frozen at 2); ONE suppressed_removes entry."""
    assert AGING_STREAK_THRESHOLD == 3
    prior = _prior("PINP", streak=2, pinned=True)
    cand = _failing_candidate("PINP")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"PINP"}),
    )
    assert delta.removes == []
    assert len(delta.streak_increments) == 1
    assert delta.streak_increments[0].not_qualified_streak == 3
    assert delta.streak_increments[0].pinned is True
    assert len(delta.suppressed_removes) == 1
    assert delta.suppressed_removes[0].ticker == "PINP"


def test_unpinned_same_setup_ages_off():
    prior = _prior("UNPN", streak=2, pinned=False)
    cand = _failing_candidate("UNPN")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset(),
    )
    assert len(delta.removes) == 1
    assert delta.removes[0].ticker == "UNPN"
    assert delta.streak_increments == []
    assert delta.suppressed_removes == []


def test_pinned_below_threshold_is_ordinary_streak_increment():
    prior = _prior("LOWP", streak=0, pinned=True)
    cand = _failing_candidate("LOWP")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"LOWP"}),
    )
    assert delta.suppressed_removes == []
    assert delta.removes == []
    assert delta.streak_increments[0].not_qualified_streak == 1
    assert delta.streak_increments[0].pinned is True


def test_error_candidate_preserves_last_values_and_missing_criteria():
    """Codex R1-Critical / F6: a pinned ticker whose candidate is bucket='error'
    (close=None, empty criteria) must NOT blank last_*/missing_criteria."""
    prior = _prior("DEAD", streak=1, pinned=True, last_close=22.2, last_pivot=21.0,
                   last_stop=19.5, last_adr_pct=4.1, missing_criteria="tightness")
    err_cand = Candidate(
        ticker="DEAD", bucket="error", close=None, pivot=None, initial_stop=None,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
    )
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[err_cand], data_asof_date="2026-06-10",
        pinned_tickers=frozenset({"DEAD"}),
    )
    inc = delta.streak_increments[0]
    assert inc.not_qualified_streak == 2
    assert inc.last_close == 22.2
    assert inc.last_pivot == 21.0
    assert inc.last_stop == 19.5
    assert inc.last_adr_pct == 4.1
    assert inc.missing_criteria == "tightness"


def test_default_empty_pinned_tickers_keeps_legacy_behavior():
    prior = _prior("LEGC", streak=2, pinned=False)
    cand = _failing_candidate("LEGC")
    delta = compute_watchlist_changes(
        prior=[prior], today_candidates=[cand], data_asof_date="2026-06-10",
    )
    assert len(delta.removes) == 1
