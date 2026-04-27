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


# ---------------------------------------------------------------------------
# Task 4.6 — Compounding-confound test (per 2026-04-26 lesson).
#
# Spec §3.5 + §4.4: pattern_tag must NOT influence row order. The direct
# `_sort_watchlist(rows, flag_tags)` test would be vacuous (the function
# signature doesn't even accept pattern_tags). Instead test E2E through
# `build_watchlist` and verify that toggling classifications ON / OFF
# leaves the row order unchanged. If sort logic ever picks up the flag
# tag, this test FAILS first — well before the operator notices reorder.
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock  # noqa: E402  — keep test-internal import grouping

from ._pattern_classification_seed import (  # noqa: E402
    add_active_watchlist_row,
    delete_all_classifications,
    seed_pipeline_with_classification,
)


def test_pattern_tags_do_not_influence_watchlist_row_order(seeded_db):
    """Sort-neutrality (architectural separation, Codex R1 Major 1 split):
    a row carrying a pattern_tag must NOT outrank a row without one.
    With identical flag_tags + proximity, the sort must be byte-equivalent
    whether classifications exist or not.

    **This test contains ONLY the sort-neutrality assertion.** It is the
    structural proof that `_pattern_tags` does not leak into
    `_sort_watchlist`'s primary key — by construction, removing the
    `_pattern_tags` call from `build_watchlist` MUST leave this test
    green (the test would still observe identical order_with vs
    order_without, because both VMs would have empty pattern_tags but
    the sort itself is unchanged).

    The companion test `test_pattern_tags_wiring_active_in_build_watchlist`
    asserts the wiring leg separately so the two architectural concerns
    don't conflate.

    Setup: two watchlist rows (AAA, BBB), identical entry_target +
    last_close (so proximity is equal); only **BBB** has a classification.
    Why BBB and not AAA: ticker-ASC tiebreak already places AAA first
    under the correct sort. Classifying AAA would be vacuous — a
    hypothetical bug where pattern-tag presence illegally sorted FIRST
    would still place AAA first (it has both the alphabetical advantage
    AND the bogus pattern-tag advantage), so the discriminator would
    fail to distinguish. Classifying BBB inverts the test: the correct
    sort places AAA first (alphabetical); a bug giving pattern-tag
    presence priority would flip BBB to first. order_with vs
    order_without then disagrees only when sort-neutrality is broken.
    Codex Round 2 Major 1 fix.
    """
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="BBB",
        pattern="flag", confidence=0.99,
    )
    add_active_watchlist_row(cfg.paths.db_path, ticker="AAA")
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False

    vm_with = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    order_with = [r.ticker for r in vm_with.rows]

    delete_all_classifications(cfg.paths.db_path)

    vm_without = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    order_without = [r.ticker for r in vm_without.rows]

    # Exact-order assertions (Codex R2 Major 1 strengthening): asserting
    # only `order_with == order_without` was vacuous if both runs
    # produced the same coincidentally-wrong order. The deterministic
    # ticker-ASC tiebreak puts AAA before BBB regardless of pattern_tag
    # state; if `_pattern_tags` ever leaks into the sort primary key,
    # the classified BBB would jump first in `vm_with` and these
    # exact-order assertions would fire. Removing `_pattern_tags` from
    # `build_watchlist` leaves both assertions green by construction —
    # that's the structural proof. The wiring leg lives in the separate
    # test below.
    assert order_with == ["AAA", "BBB"], (
        f"Sort with classification present produced {order_with} — "
        f"expected deterministic [AAA, BBB] (alphabetical). "
        "pattern_tag is influencing _sort_watchlist; "
        "architectural separation regressed."
    )
    assert order_without == ["AAA", "BBB"], (
        f"Sort with classifications wiped produced {order_without} — "
        f"expected deterministic [AAA, BBB]. Sort logic itself regressed."
    )


def test_pattern_tags_wiring_active_in_build_watchlist(seeded_db):
    """Wiring leg (Codex R1 Major 1 split): `build_watchlist` populates
    `WatchlistVM.pattern_tags` from the classification cache, and the
    field empties when classifications are deleted.

    **This test isolates the wiring assertion** so the sort-neutrality
    test above can serve as the architectural proof without conflating
    two concerns. Catches the failure mode where the order check would
    pass tautologically because both runs produce empty pattern_tags
    (e.g., a threshold-filter regression that always returns {}).
    """
    from swing.web.view_models.watchlist import build_watchlist
    cfg, _ = seeded_db
    # Ticker assignment mirrors the sort-neutrality test (Codex R2 fix):
    # classify BBB, leave AAA unclassified. Setup parity keeps both
    # tests on the same fixture shape so a future refactor can lift
    # them into a shared @pytest.fixture if needed.
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="BBB",
        pattern="flag", confidence=0.99,
    )
    add_active_watchlist_row(cfg.paths.db_path, ticker="AAA")
    cache = MagicMock()
    cache.get_many.return_value = {}
    cache.degraded_until.return_value = None
    cache.is_degraded.return_value = False

    vm_with = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm_with.pattern_tags == {"BBB": "flag (0.99)"}

    delete_all_classifications(cfg.paths.db_path)

    vm_without = build_watchlist(cfg=cfg, cache=cache, executor=MagicMock())
    assert vm_without.pattern_tags == {}
