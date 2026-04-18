"""Watchlist service: partition today's evaluation against prior watchlist."""
from __future__ import annotations

from swing.data.models import Candidate, CriterionResult, WatchlistEntry
from swing.watchlist.service import (
    compute_watchlist_changes, WatchlistDelta,
    STABLE_CRITERION_NAMES, DYNAMIC_CRITERION_NAMES,
    AGING_STREAK_THRESHOLD,
)


def _candidate(
    ticker: str, *, all_stable_pass: bool = True, missing_dynamic: tuple[str, ...] = (),
    bucket: str = "watch",
) -> Candidate:
    crits = []
    for name in STABLE_CRITERION_NAMES:
        crits.append(CriterionResult(
            criterion_name=name, layer="vcp",
            result="pass" if all_stable_pass else "fail",
            value=None, rule=None,
        ))
    for name in DYNAMIC_CRITERION_NAMES:
        crits.append(CriterionResult(
            criterion_name=name, layer="vcp",
            result="fail" if name in missing_dynamic else "pass",
            value=None, rule=None,
        ))
    return Candidate(
        ticker=ticker, bucket=bucket, close=100.0, pivot=102.0,
        initial_stop=98.0, adr_pct=4.5, tight_streak=3, pullback_pct=10.0,
        prior_trend_pct=30.0, rs_rank=80, rs_return_12w_vs_spy=0.15,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tuple(crits),
    )


def test_new_qualifier_is_added():
    delta = compute_watchlist_changes(
        prior=[], today_candidates=[_candidate("AAPL")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.adds) == 1
    add = delta.adds[0]
    assert add.ticker == "AAPL"
    assert add.added_date == "2026-04-15"
    assert add.qualification_count == 1
    assert add.entry_target == 102.0
    assert add.initial_stop_target == 98.0


def test_existing_requalifier_increments_count_keeps_targets():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[_candidate("AAPL")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.requalifies) == 1
    rq = delta.requalifies[0]
    assert rq.qualification_count == 3
    assert rq.entry_target == 99.0
    assert rq.initial_stop_target == 95.0


def test_failing_stable_increments_streak():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    assert len(delta.streak_increments) == 1
    inc = delta.streak_increments[0]
    assert inc.not_qualified_streak == 1
    assert inc.last_data_asof_date == "2026-04-15"


def test_streak_at_threshold_archives():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2,
        not_qualified_streak=AGING_STREAK_THRESHOLD - 1,
        last_data_asof_date="2026-04-14",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    assert delta.streak_increments == []
    assert len(delta.removes) == 1
    arch = delta.removes[0]
    assert arch.ticker == "AAPL"
    assert arch.removed_date == "2026-04-15"
    assert "stable" in arch.reason.lower() or "aged" in arch.reason.lower()


def test_absence_from_batch_does_not_count():
    prior = [WatchlistEntry(
        ticker="OBSCURE", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=2,
        last_data_asof_date="2026-04-14",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[],
        data_asof_date="2026-04-15",
    )
    assert delta.streak_increments == []
    assert delta.removes == []
    assert delta.adds == []
    assert delta.requalifies == []


def test_duplicate_data_asof_does_not_double_increment_streak():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=1,
        last_data_asof_date="2026-04-15",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", all_stable_pass=False)],
        data_asof_date="2026-04-15",
    )
    assert delta.streak_increments == []
    assert delta.removes == []


def test_corrected_rerun_can_requalify_previously_failing_ticker():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=1,
        last_data_asof_date="2026-04-15",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    delta = compute_watchlist_changes(
        prior=prior,
        today_candidates=[_candidate("AAPL", bucket="watch")],
        data_asof_date="2026-04-15",
    )
    assert len(delta.requalifies) == 1
    assert delta.requalifies[0].not_qualified_streak == 0
    assert delta.requalifies[0].qualification_count == 3


def test_dynamic_misses_recorded_in_missing_criteria():
    delta = compute_watchlist_changes(
        prior=[],
        today_candidates=[_candidate("AAPL", missing_dynamic=("tightness", "vcp_volume_contraction"))],
        data_asof_date="2026-04-15",
    )
    assert len(delta.adds) == 1
    add = delta.adds[0]
    assert add.missing_criteria is not None
    assert "tightness" in add.missing_criteria
    assert "vcp" in add.missing_criteria


def test_skip_bucket_does_not_qualify():
    cand = _candidate("SKIP1", missing_dynamic=("proximity_20ma", "tightness", "vcp_volume_contraction"),
                      bucket="skip")
    delta = compute_watchlist_changes(
        prior=[], today_candidates=[cand], data_asof_date="2026-04-15",
    )
    assert delta.adds == []
    assert delta.requalifies == []


def test_skip_bucket_for_existing_counts_as_fail():
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-12",
        status="watch", qualification_count=2, not_qualified_streak=0,
        last_data_asof_date="2026-04-12",
        entry_target=99.0, initial_stop_target=95.0,
        last_close=98.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    cand = _candidate("AAPL", missing_dynamic=("proximity_20ma", "tightness", "vcp_volume_contraction"),
                      bucket="skip")
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[cand], data_asof_date="2026-04-15",
    )
    assert len(delta.streak_increments) == 1
    assert delta.streak_increments[0].not_qualified_streak == 1


def test_duplicate_data_asof_qualify_is_idempotent():
    """Adversarial review Round 1 Major: same-day rerun where both runs qualify
    must not double-increment qualification_count (was a bug where streak guard
    only covered the fail path)."""
    prior = [WatchlistEntry(
        ticker="AAPL", added_date="2026-04-10", last_qualified_date="2026-04-15",
        status="watch", qualification_count=3, not_qualified_streak=0,
        last_data_asof_date="2026-04-15",  # already processed today
        entry_target=99.0, initial_stop_target=95.0,
        last_close=99.0, last_pivot=99.0, last_stop=95.0, last_adr_pct=3.0,
        missing_criteria=None, notes=None,
    )]
    # Re-run: AAPL still qualifies → must be no-op (no requalify, no add)
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=[_candidate("AAPL", bucket="watch")],
        data_asof_date="2026-04-15",
    )
    assert delta.requalifies == []
    assert delta.adds == []
    assert delta.streak_increments == []
    assert delta.removes == []
