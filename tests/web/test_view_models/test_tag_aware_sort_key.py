"""Pin _tag_aware_sort_key as the single source of truth for the
tag-aware composite sort key. Spec §A.

Byte-identity invariant: `_sort_watchlist` and `_step_charts` (Task 5) both
import this helper. Tests here pin the key shape; Task 5 tests pin the
identity-of-output between callers.
"""
from __future__ import annotations

from swing.data.models import WatchlistEntry
from swing.web.view_models.dashboard import _tag_aware_sort_key


def _wl(ticker: str, *, entry_target: float | None = 100.0,
        last_close: float | None = 99.0) -> WatchlistEntry:
    """Helper to build minimal WatchlistEntry for sort tests.

    All fields populated explicitly per swing/data/models.py.
    Adjust if the model gains fields.
    """
    return WatchlistEntry(
        ticker=ticker,
        added_date="2026-04-15",
        last_qualified_date="2026-04-17",
        status="watch",
        qualification_count=1,
        not_qualified_streak=0,
        last_data_asof_date="2026-04-17",
        entry_target=entry_target,
        initial_stop_target=None,
        last_close=last_close,
        last_pivot=None,
        last_stop=None,
        last_adr_pct=None,
        missing_criteria=None,
        notes=None,
    )


def test_tag_aware_sort_key_returns_4_tuple():
    """Helper returns the documented 4-tuple shape:
    (-tag_count, -tag_precedence_score, abs_proximity, ticker).

    Discriminating verification: assert tuple length AND each element's
    sign/type. A regression that drops the ticker tiebreaker would fail
    the length check.
    """
    flag_tags = {"AAPL": ("A+",)}
    key = _tag_aware_sort_key(_wl("AAPL"), flag_tags)
    assert isinstance(key, tuple)
    assert len(key) == 4, f"expected 4-tuple, got {len(key)}: {key}"
    tag_count_neg, tag_score_neg, proximity, ticker = key
    assert tag_count_neg == -1
    assert tag_score_neg < 0  # A+ score is positive, so negated is negative
    assert proximity == 0.01  # |99.0 - 100.0| / 100.0 = 0.01
    assert ticker == "AAPL"


def test_tag_aware_sort_key_no_tags_returns_zeroed_first_two():
    """When the ticker has no tags, the first two slots are 0 (ties up
    at the bottom of the no-tag group).

    Discriminating verification: pre-fix code gave ticker tags from a
    transitively-imported map; post-fix code uses the explicit `flag_tags`
    arg. Catches a regression where the helper accidentally re-uses a
    module-level map.
    """
    key = _tag_aware_sort_key(_wl("ZZZ"), {})
    tag_count_neg, tag_score_neg, _proximity, _ticker = key
    assert tag_count_neg == 0
    assert tag_score_neg == 0


def test_sort_watchlist_uses_tag_aware_sort_key_helper():
    """Reference-enumeration discipline: build a 4-row watchlist with
    diverse tag profiles and assert the sorted order matches what
    `_tag_aware_sort_key` produces directly (verified-empirically pin).

    Discriminating verification: invariant is "_sort_watchlist's output
    order is identical to the order obtained by sorting with
    _tag_aware_sort_key directly." If the two diverge, this test fails;
    Task 5's identity claim depends on this.
    """
    from swing.web.view_models.dashboard import _sort_watchlist
    rows = [
        _wl("ZZZ", entry_target=100.0, last_close=99.0),  # no tags
        _wl("BBB", entry_target=100.0, last_close=99.5),  # no tags, closer
        _wl("AAA", entry_target=100.0, last_close=98.0),  # 1 tag (TT✓)
        _wl("CCC", entry_target=100.0, last_close=99.0),  # 2 tags (TT✓+VCP✓)
    ]
    flag_tags = {
        "AAA": ("TT✓",),
        "CCC": ("TT✓", "VCP✓"),
    }
    expected = sorted(rows, key=lambda w: _tag_aware_sort_key(w, flag_tags))
    actual = _sort_watchlist(list(rows), flag_tags)
    assert [w.ticker for w in actual] == [w.ticker for w in expected]
