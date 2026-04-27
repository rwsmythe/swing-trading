"""Sort-neutrality regression: behavioral parity vector for `_sort_watchlist`.

Spec §4.4 architectural guarantee (R1 M2 fix): `_pattern_tags` is a
SIBLING to `_flag_tags`; the flag tag never enters the `tags` tuple
consumed by `_sort_watchlist`. This test asserts the contract by replaying
a fixed input/output vector through `_sort_watchlist` after Phase 4
changes — Phase 4 adds NO new sort cases, so the vector freezes the
pre-Phase-4 sort behavior verbatim.

The parity vector covers:
- All-untagged → proximity-then-ticker.
- Tag count beats precedence (2 tags > 1 tag).
- Precedence beats proximity at equal tag count.
- Stable ticker tiebreak with full equality.
- Unknown tag scores 0 (defensive against future tag-vocabulary changes).
- Missing pivot / last_close → +inf proximity, sorts last among no-tag
  group.

Companion to the source-byte check in Task 4.8: the parity vector
catches behavioral drift; the byte check catches structural drift.
"""
from __future__ import annotations

import pytest

from swing.data.models import WatchlistEntry
from swing.web.view_models.dashboard import _sort_watchlist


def _entry(
    ticker: str, last_close: float | None, entry_target: float | None,
) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-01",
        last_qualified_date="2026-04-26", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-25",
        entry_target=entry_target, initial_stop_target=None,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=None, missing_criteria=None, notes=None,
    )


# Each tuple: (label, list-of-(ticker, last_close, entry_target),
#             {ticker: tag-tuple}, expected order of tickers)
PARITY_VECTOR: list[tuple] = [
    (
        "all-untagged-sort-by-proximity-then-ticker",
        [
            ("AAA", 100.0, 110.0),  # 9.09% off
            ("BBB", 105.0, 110.0),  # 4.55% off
            ("CCC", 90.0, 110.0),   # 18.18% off
        ],
        {},
        # Closest to pivot first, ticker as final tiebreak.
        ["BBB", "AAA", "CCC"],
    ),
    (
        "tag-count-beats-precedence",
        [("AAA", 100.0, 110.0), ("BBB", 100.0, 110.0)],
        {"AAA": ("TT✓",), "BBB": ("TT✓", "VCP✓")},
        ["BBB", "AAA"],  # 2 tags > 1 tag
    ),
    (
        "precedence-beats-proximity-on-equal-tag-count",
        [("AAA", 100.0, 110.0), ("BBB", 105.0, 110.0)],
        {"AAA": ("A+",), "BBB": ("TT✓",)},
        # AAA's precedence 4 (A+) beats BBB's precedence 1 (TT✓) even
        # though BBB has BETTER proximity.
        ["AAA", "BBB"],
    ),
    (
        "ticker-tiebreak-on-full-equality",
        [("BBB", 105.0, 110.0), ("AAA", 105.0, 110.0)],
        {},
        # Same proximity, no tags — stable ticker ASC.
        ["AAA", "BBB"],
    ),
    (
        "unknown-tag-scores-zero-still-sorts-by-proximity",
        [("AAA", 100.0, 110.0), ("BBB", 105.0, 110.0)],
        {"AAA": ("UNKNOWN",), "BBB": ("UNKNOWN",)},
        # Tag count is 1 for both; precedence 0 for both → proximity wins.
        ["BBB", "AAA"],
    ),
    (
        "missing-pivot-sorts-last-among-untagged",
        [
            ("AAA", 105.0, 110.0),  # 4.55% off
            ("BBB", None, 110.0),   # +inf proximity
            ("CCC", 100.0, 110.0),  # 9.09% off
        ],
        {},
        # Untagged-with-pivot first by proximity; missing-pivot last.
        ["AAA", "CCC", "BBB"],
    ),
    (
        "tagged-row-with-worse-proximity-still-outranks-untagged-better",
        [
            # Real production case (Session 2 watchlist sort).
            ("TGT", 108.0, 100.0),  # 8% off, A+
            ("UNT", 101.0, 100.0),  # 1% off, no tag
        ],
        {"TGT": ("A+",)},
        # Tag count (1 vs 0) wins regardless of proximity.
        ["TGT", "UNT"],
    ),
    (
        "three-tag-A+-VCP-TT-beats-two-tag-VCP-TT",
        [("AAA", 100.0, 110.0), ("BBB", 100.0, 110.0)],
        {
            "AAA": ("TT✓", "VCP✓"),
            "BBB": ("TT✓", "VCP✓", "A+"),
        },
        # Tag count 3 > 2; ticker doesn't enter primary key.
        ["BBB", "AAA"],
    ),
]


@pytest.mark.parametrize(
    "label,rows_data,flag_tags,expected_order", PARITY_VECTOR,
)
def test_sort_watchlist_byte_for_byte_parity(
    label: str, rows_data: list[tuple], flag_tags: dict, expected_order: list[str],
):
    """Replay the frozen vector through `_sort_watchlist`. Failing here
    means Phase 4 (or anything after) accidentally touched the sort —
    by definition a regression because the vector covers the existing
    pre-Phase-4 behavior verbatim."""
    rows = [_entry(*r) for r in rows_data]
    sorted_rows = _sort_watchlist(rows, flag_tags)
    assert [r.ticker for r in sorted_rows] == expected_order, (
        f"Sort regression on case '{label}'."
    )
