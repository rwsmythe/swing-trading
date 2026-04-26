"""Tests for `_sort_watchlist` — the four-key composite sort that replaces
the prior pure-proximity sort on the dashboard top-5 and /watchlist surface.

Sort key (descending priority):
  1. tag count (DESC)
  2. tag precedence score (DESC) — A+=4, VCP✓=2, TT✓=1
  3. abs(% to pivot) (ASC) — None entry_target/last_close → +inf (sorts last)
  4. ticker (ASC) — determinism tiebreaker (part of the contract)
"""
from __future__ import annotations

from swing.data.models import WatchlistEntry


def _w(ticker: str, *, entry_target: float | None, last_close: float | None) -> WatchlistEntry:
    """Minimal WatchlistEntry factory; non-sort fields filled with safe defaults."""
    return WatchlistEntry(
        ticker=ticker,
        added_date="2026-04-10",
        last_qualified_date="2026-04-17",
        status="watch",
        qualification_count=1,
        not_qualified_streak=0,
        last_data_asof_date="2026-04-17",
        entry_target=entry_target,
        initial_stop_target=None,
        last_close=last_close,
        last_pivot=entry_target,
        last_stop=None,
        last_adr_pct=None,
        missing_criteria=None,
        notes=None,
    )


def test_sort_primary_tag_count_beats_proximity():
    """A: better proximity (1% from pivot), 1 tag. B: worse proximity (8%), 3 tags.
    Pure-proximity sort would put A first; tag-count-primary sort puts B first.
    This is the canonical pre-fix vs post-fix discriminator from the brief.
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    a = _w("AAA", entry_target=100.0, last_close=101.0)  # 1% prox, 1 tag
    b = _w("BBB", entry_target=100.0, last_close=108.0)  # 8% prox, 3 tags
    flag_tags = {
        "AAA": ("TT✓",),
        "BBB": ("A+", "VCP✓", "TT✓"),
    }

    out = _sort_watchlist([a, b], flag_tags)

    assert [w.ticker for w in out] == ["BBB", "AAA"]


def test_sort_secondary_precedence_breaks_count_tie():
    """Both have 2 tags and identical proximity. A=(A+, TT✓) score 5,
    B=(VCP✓, TT✓) score 3. A+ wins.

    Note: (A+, TT✓) is degenerate per real `_flag_tags` (A+ bucket emits all
    three tags) — bypassing _flag_tags here exercises the precedence encoding
    directly so a future framework loosening that drops VCP✓ from an A+
    candidate still sorts correctly.
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    a = _w("AAA", entry_target=100.0, last_close=105.0)  # 5% prox, 2 tags
    b = _w("BBB", entry_target=100.0, last_close=105.0)  # 5% prox, 2 tags
    flag_tags = {
        "AAA": ("A+", "TT✓"),         # score 5
        "BBB": ("VCP✓", "TT✓"),  # score 3
    }

    out = _sort_watchlist([a, b], flag_tags)

    assert [w.ticker for w in out] == ["AAA", "BBB"]


def test_sort_tertiary_proximity_breaks_tag_tie():
    """Identical tags (both `(TT✓,)`), so primary + secondary tied.
    Tertiary key (proximity ASC) wins: 1% prox before 8%.
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    a = _w("AAA", entry_target=100.0, last_close=101.0)  # 1% prox
    b = _w("BBB", entry_target=100.0, last_close=108.0)  # 8% prox
    flag_tags = {
        "AAA": ("TT✓",),
        "BBB": ("TT✓",),
    }

    out = _sort_watchlist([a, b], flag_tags)

    assert [w.ticker for w in out] == ["AAA", "BBB"]


def test_sort_quaternary_ticker_alphabetical_for_determinism():
    """All three keys tied → ticker ASC for determinism.

    Insertion order is deliberately reverse-alphabetical (MSFT, AAPL) so the
    quaternary key actually fires; if the implementation falls back to
    Python's stable sort with no ticker key, the order would stay (MSFT, AAPL).
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    msft = _w("MSFT", entry_target=100.0, last_close=105.0)
    aapl = _w("AAPL", entry_target=100.0, last_close=105.0)
    flag_tags = {
        "MSFT": ("TT✓",),
        "AAPL": ("TT✓",),
    }

    out = _sort_watchlist([msft, aapl], flag_tags)

    assert [w.ticker for w in out] == ["AAPL", "MSFT"]


def test_sort_no_tags_fallback_to_proximity_after_tagged():
    """No-tag tickers sort by proximity ASC AMONG THEMSELVES, AFTER any tagged
    ticker (even a tagged ticker with worse proximity).
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    tagged_far = _w("TAG", entry_target=100.0, last_close=110.0)  # 10% prox, tagged
    untag_close = _w("CLO", entry_target=100.0, last_close=101.0)  # 1% prox, no tags
    untag_far = _w("FAR", entry_target=100.0, last_close=105.0)   # 5% prox, no tags
    flag_tags = {"TAG": ("TT✓",)}

    out = _sort_watchlist([untag_close, tagged_far, untag_far], flag_tags)

    assert [w.ticker for w in out] == ["TAG", "CLO", "FAR"]


def test_sort_missing_proximity_data_sorts_last_among_no_tag_group():
    """`entry_target=None` or `last_close=None` → proximity = +inf, so sorts
    AFTER no-tag entries with valid proximity. Combined with the no-tag rule,
    a None-proximity untagged row sorts last overall.
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    no_data = _w("NONE", entry_target=None, last_close=None)
    valid_no_tag = _w("VLD", entry_target=100.0, last_close=105.0)
    tagged = _w("TAG", entry_target=100.0, last_close=110.0)
    flag_tags = {"TAG": ("TT✓",)}

    out = _sort_watchlist([no_data, valid_no_tag, tagged], flag_tags)

    assert [w.ticker for w in out] == ["TAG", "VLD", "NONE"]


def test_sort_empty_flag_tags_mapping_falls_back_to_proximity():
    """Defensive: when no candidates exist (empty `flag_tags`), the sort
    degrades gracefully to pure-proximity ordering. Asserts the
    `flag_tags.get(ticker, ())` fallback survives an empty mapping.
    """
    from swing.web.view_models.dashboard import _sort_watchlist

    a = _w("AAA", entry_target=100.0, last_close=101.0)  # 1%
    b = _w("BBB", entry_target=100.0, last_close=108.0)  # 8%
    c = _w("CCC", entry_target=100.0, last_close=104.0)  # 4%

    out = _sort_watchlist([b, c, a], flag_tags={})

    assert [w.ticker for w in out] == ["AAA", "CCC", "BBB"]


def test_tag_precedence_score_known_combinations():
    """Encoding contract: A+=4, VCP✓=2, TT✓=1; unknown tags score 0.

    Pinned so future tag additions can't silently regress the secondary key.
    """
    from swing.web.view_models.dashboard import _tag_precedence_score

    assert _tag_precedence_score(("A+", "VCP✓", "TT✓")) == 7
    assert _tag_precedence_score(("VCP✓", "TT✓")) == 3
    assert _tag_precedence_score(("A+", "TT✓")) == 5
    assert _tag_precedence_score(("TT✓",)) == 1
    assert _tag_precedence_score(()) == 0
    # Unknown tag must score 0 — not crash and not borrow another tag's weight.
    assert _tag_precedence_score(("UNKNOWN",)) == 0
    assert _tag_precedence_score(("A+", "UNKNOWN")) == 4
