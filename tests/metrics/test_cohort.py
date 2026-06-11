"""Phase 10 Sub-bundle A T-A.4 — cohort filter tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.cohort import (
    count_per_cohort,
    list_closed_trades_for_cohort,
    list_trades_for_cohort,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase10_cohort.db")


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str,
    state: str,
    hypothesis_label: str | None,
    entry_date: str = "2026-05-12",
    entry_intent: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label, entry_intent) VALUES (?, ?, ?, 10.0, 100, 9.0, 9.0, ?, "
        "'S', 'I', 'manual_off_pipeline', ?, 100, ?, ?)",
        (trade_id, ticker, entry_date, state,
         entry_date + "T09:00:00.000", hypothesis_label, entry_intent),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# list_trades_for_cohort
# ---------------------------------------------------------------------------

def test_list_trades_filters_by_hypothesis_label(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="AAA", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=2, ticker="BBB", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=3, ticker="CCC", state="closed",
                hypothesis_label="Sub-A+ VCP-not-formed")
    result = list_trades_for_cohort(conn, hypothesis_label="A+ baseline")
    assert len(result) == 2
    assert {t.ticker for t in result} == {"AAA", "BBB"}


def test_list_trades_state_filter_narrows(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="OPEN", state="entered",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=2, ticker="CLOSED", state="closed",
                hypothesis_label="A+ baseline")
    open_only = list_trades_for_cohort(
        conn, hypothesis_label="A+ baseline",
        state_filter=("entered",),
    )
    assert [t.ticker for t in open_only] == ["OPEN"]
    closed_only = list_trades_for_cohort(
        conn, hypothesis_label="A+ baseline",
        state_filter=("closed",),
    )
    assert [t.ticker for t in closed_only] == ["CLOSED"]


def test_list_trades_label_none_returns_all(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="A", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=2, ticker="B", state="closed",
                hypothesis_label="Sub-A+ VCP-not-formed")
    _seed_trade(conn, trade_id=3, ticker="C", state="closed",
                hypothesis_label=None)  # unlabeled trade
    result = list_trades_for_cohort(conn, hypothesis_label=None)
    assert len(result) == 3


def test_list_trades_canonicalizes_label(conn: sqlite3.Connection):
    """Whitespace + control-byte canonicalization at query time matches
    the persistence-boundary canonicalization. ``canonicalize_hypothesis_label``
    does NOT lowercase — case is preserved by design."""
    _seed_trade(conn, trade_id=1, ticker="AAA", state="closed",
                hypothesis_label="A+ baseline")
    # Query with embedded zero-width space + extra whitespace + control byte.
    raw_label = "  A+​ baseline\t"
    result = list_trades_for_cohort(conn, hypothesis_label=raw_label)
    assert len(result) == 1
    assert result[0].ticker == "AAA"


def test_list_trades_case_difference_matches_under_three_rule_contract(
    conn: sqlite3.Connection,
):
    """Phase 13 T-T4.SB.2 (Item 7 Option 7C LOCK) widens the cohort match
    contract from bytewise equality to 3-rule delimiter-aware case-insensitive
    matching. Per the shared helper at
    :func:`swing.metrics.label_match.label_matches_hypothesis`, ``"a+ baseline"``
    and ``"A+ baseline"`` now belong to the SAME cohort (Rule 1 case-fold
    exact equality). Operator-facing implication: hypothesis labels are
    case-insensitive for cohort attribution.
    """
    _seed_trade(conn, trade_id=1, ticker="UPPER", state="closed",
                hypothesis_label="A+ baseline")
    result_lower = list_trades_for_cohort(
        conn, hypothesis_label="a+ baseline",
    )
    assert [t.ticker for t in result_lower] == ["UPPER"]


def test_list_trades_ordered_by_entry_date_then_ticker(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="ZZZ", state="closed",
                hypothesis_label="A+ baseline", entry_date="2026-05-10")
    _seed_trade(conn, trade_id=2, ticker="AAA", state="closed",
                hypothesis_label="A+ baseline", entry_date="2026-05-11")
    _seed_trade(conn, trade_id=3, ticker="BBB", state="closed",
                hypothesis_label="A+ baseline", entry_date="2026-05-10")
    result = list_trades_for_cohort(conn, hypothesis_label="A+ baseline")
    assert [t.ticker for t in result] == ["BBB", "ZZZ", "AAA"]


# ---------------------------------------------------------------------------
# list_closed_trades_for_cohort
# ---------------------------------------------------------------------------

def test_list_closed_trades_returns_closed_and_reviewed(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="OPEN", state="entered",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=2, ticker="CLOSED", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=3, ticker="REVIEWED", state="reviewed",
                hypothesis_label="A+ baseline")
    result = list_closed_trades_for_cohort(conn, hypothesis_label="A+ baseline")
    assert {t.ticker for t in result} == {"CLOSED", "REVIEWED"}


# ---------------------------------------------------------------------------
# count_per_cohort
# ---------------------------------------------------------------------------

def test_count_per_cohort_returns_all_4_cohorts_even_when_zero(
    conn: sqlite3.Connection,
):
    """Empty trades table + 4 seeded cohorts → {name: 0} for all 4."""
    result = count_per_cohort(conn)
    assert set(result.keys()) == {
        "A+ baseline",
        "Near-A+ defensible: extension test",
        "Sub-A+ VCP-not-formed",
        "Capital-blocked: smaller-position test",
        "Broad-watch baseline",
    }
    for name, count in result.items():
        assert count == 0, f"{name}: expected 0 got {count}"


def test_count_per_cohort_reflects_closed_trade_counts(conn: sqlite3.Connection):
    _seed_trade(conn, trade_id=1, ticker="A", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=2, ticker="B", state="closed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=3, ticker="C", state="reviewed",
                hypothesis_label="A+ baseline")
    _seed_trade(conn, trade_id=4, ticker="D", state="entered",
                hypothesis_label="A+ baseline")  # NOT closed; excluded.
    _seed_trade(conn, trade_id=5, ticker="E", state="closed",
                hypothesis_label="Sub-A+ VCP-not-formed")
    result = count_per_cohort(conn)
    assert result["A+ baseline"] == 3  # 2 closed + 1 reviewed
    assert result["Sub-A+ VCP-not-formed"] == 1
    assert result["Near-A+ defensible: extension test"] == 0
    assert result["Capital-blocked: smaller-position test"] == 0


def test_count_per_cohort_includes_orphan_labels(conn: sqlite3.Connection):
    """A trade labeled with a name NOT in hypothesis_registry surfaces in
    the returned dict (operator-visibility for orphan labels)."""
    _seed_trade(conn, trade_id=1, ticker="X", state="closed",
                hypothesis_label="orphan-cohort")
    result = count_per_cohort(conn)
    assert result["orphan-cohort"] == 1
    # The 4 registry cohorts still present (with 0):
    assert result["A+ baseline"] == 0


# ---------------------------------------------------------------------------
# Task 6 — entry_intent predicate (sentinel convention)
# ---------------------------------------------------------------------------

def test_list_closed_trades_for_cohort_intent_predicate(
    conn: sqlite3.Connection,
) -> None:
    """Sentinel convention: None=no filter; '__unclassified__'=IS NULL;
    member value = equality. Verified across closed trades carrying
    entry_intent in {standard, hypothesis_test_by_design, NULL}."""
    _seed_trade(conn, trade_id=1, ticker="STD1", state="closed",
                hypothesis_label=None, entry_intent="standard")
    _seed_trade(conn, trade_id=2, ticker="STD2", state="closed",
                hypothesis_label=None, entry_intent="standard")
    _seed_trade(conn, trade_id=3, ticker="BD1", state="closed",
                hypothesis_label=None,
                entry_intent="hypothesis_test_by_design")
    _seed_trade(conn, trade_id=4, ticker="NULL1", state="closed",
                hypothesis_label=None, entry_intent=None)

    std = list_closed_trades_for_cohort(
        conn, hypothesis_label=None, entry_intent="standard")
    assert {t.entry_intent for t in std} == {"standard"}
    assert {t.ticker for t in std} == {"STD1", "STD2"}

    bd = list_closed_trades_for_cohort(
        conn, hypothesis_label=None,
        entry_intent="hypothesis_test_by_design")
    assert {t.entry_intent for t in bd} == {"hypothesis_test_by_design"}

    unc = list_closed_trades_for_cohort(
        conn, hypothesis_label=None, entry_intent="__unclassified__")
    assert all(t.entry_intent is None for t in unc)
    assert {t.ticker for t in unc} == {"NULL1"}

    nofilter = list_closed_trades_for_cohort(conn, hypothesis_label=None)
    # no-filter == today's behavior (all four closed trades).
    assert len(nofilter) == 4
    assert len(nofilter) >= len(std)


def test_list_trades_for_cohort_intent_predicate_with_state(
    conn: sqlite3.Connection,
) -> None:
    """entry_intent predicate composes with the state_filter clause."""
    _seed_trade(conn, trade_id=1, ticker="OPEN_STD", state="entered",
                hypothesis_label=None, entry_intent="standard")
    _seed_trade(conn, trade_id=2, ticker="CLOSED_STD", state="closed",
                hypothesis_label=None, entry_intent="standard")
    closed_std = list_trades_for_cohort(
        conn, hypothesis_label=None, state_filter=("closed",),
        entry_intent="standard")
    assert [t.ticker for t in closed_std] == ["CLOSED_STD"]
