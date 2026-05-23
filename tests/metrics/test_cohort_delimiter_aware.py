"""T-T4.SB.2 Sub-tasks 2B + 2C -- cohort helpers under 3-rule delimiter-aware match.

Discriminating tests: planted suffix-bearing labels MUST match the canonical
registered cohort name; bare-prefix extensions MUST NOT; SQL LIKE wildcards
in registered names MUST escape correctly; orphan labels MUST survive the
``count_per_cohort`` orphan-fallback (Codex R4 M#1 LOCK).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.cohort import count_per_cohort, list_trades_for_cohort


def _plant_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    hypothesis_label: str | None,
    state: str,
    entry_date: str = "2026-05-12",
) -> None:
    """Insert a minimal trade row exercising the same NOT-NULL set as the
    Phase 10 cohort tests (see ``tests/metrics/test_cohort.py``).

    Schema-version-aware: pre-v21 fixtures lack ``candidate_id`` +
    ``pattern_evaluation_id`` columns; the INSERT here omits both columns
    so it works against any v7+ schema.
    """
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "hypothesis_label) VALUES (?, ?, 10.0, 100, 9.0, 9.0, ?, "
        "'S', 'I', 'manual_off_pipeline', ?, 100, ?)",
        (ticker, entry_date, state,
         entry_date + "T09:00:00.000", hypothesis_label),
    )


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "cohort_delim.db")


# ---------------------------------------------------------------------------
# Sub-task 2B -- list_trades_for_cohort
# ---------------------------------------------------------------------------

def test_list_trades_for_cohort_matches_suffix_bearing_labels(
    conn: sqlite3.Connection,
) -> None:
    _plant_trade(conn, ticker="AAA",
                 hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: proximity_20ma",
                 state="closed")
    _plant_trade(conn, ticker="BBB",
                 hypothesis_label="Sub-A+ VCP-not-formed",
                 state="reviewed")
    _plant_trade(conn, ticker="CCC",
                 hypothesis_label="A+ baseline",
                 state="closed")
    _plant_trade(conn, ticker="DDD",
                 hypothesis_label="Sub-A+ VCP-not-formedness extended",
                 state="closed")
    conn.commit()

    rows = list_trades_for_cohort(
        conn, hypothesis_label="Sub-A+ VCP-not-formed",
        state_filter=("closed", "reviewed"),
    )
    tickers = {r.ticker for r in rows}
    # AAA: space-delimited suffix; BBB: exact equality.
    # NOT CCC (different name); NOT DDD (bare-prefix extension).
    assert tickers == {"AAA", "BBB"}


def test_list_trades_for_cohort_handles_wildcard_chars_in_registered_name(
    conn: sqlite3.Connection,
) -> None:
    _plant_trade(conn, ticker="X1", hypothesis_label="cohort_X%", state="closed")
    _plant_trade(conn, ticker="X2",
                 hypothesis_label="cohort_X% (watch); failed: x", state="closed")
    _plant_trade(conn, ticker="X3", hypothesis_label="cohortQX9", state="closed")
    conn.commit()

    rows = list_trades_for_cohort(
        conn, hypothesis_label="cohort_X%",
        state_filter=("closed", "reviewed"),
    )
    tickers = {r.ticker for r in rows}
    # NOT X3 -- would match if ``_`` and ``%`` were unescaped LIKE wildcards.
    assert tickers == {"X1", "X2"}


def test_list_trades_for_cohort_rejects_semicolon_delimited_other_cohort(
    conn: sqlite3.Connection,
) -> None:
    """Semicolon-delimiter rule: ``"A+ baseline;something"`` matches A+ baseline,
    does NOT match ``Sub-A+ VCP-not-formed`` (different name)."""
    _plant_trade(conn, ticker="SEM",
                 hypothesis_label="A+ baseline;follow-up",
                 state="closed")
    conn.commit()
    rows = list_trades_for_cohort(
        conn, hypothesis_label="A+ baseline",
        state_filter=("closed",),
    )
    assert [t.ticker for t in rows] == ["SEM"]
    rows2 = list_trades_for_cohort(
        conn, hypothesis_label="Sub-A+ VCP-not-formed",
        state_filter=("closed",),
    )
    assert rows2 == []


# ---------------------------------------------------------------------------
# Sub-task 2C -- count_per_cohort
# ---------------------------------------------------------------------------

def test_count_per_cohort_delimiter_aware_with_orphan_preservation(
    conn: sqlite3.Connection,
) -> None:
    # ``ensure_schema`` already seeds the 4 canonical hypotheses via
    # migration 0008; we plant trades against them + 1 orphan label.
    _plant_trade(conn, ticker="EX",
                 hypothesis_label="A+ baseline",
                 state="closed")
    _plant_trade(conn, ticker="SF",
                 hypothesis_label="Sub-A+ VCP-not-formed (watch); failed: x",
                 state="closed")
    _plant_trade(conn, ticker="ORP",
                 hypothesis_label="Free-text experimental",
                 state="closed")
    conn.commit()

    counts = count_per_cohort(conn)
    # Registered cohorts get exact-match + suffix-match aggregated.
    assert counts["A+ baseline"] == 1
    assert counts["Sub-A+ VCP-not-formed"] == 1
    # Orphan label preserved as its own entry (Codex R4 M#1 LOCK; orphan-
    # preservation discipline from Expansion #10 sub-discipline (e)).
    assert counts["Free-text experimental"] == 1
    # Other seeded cohorts remain 0 (empty-cohort discipline per plan §A.16).
    assert counts["Near-A+ defensible: extension test"] == 0
    assert counts["Capital-blocked: smaller-position test"] == 0


def test_count_per_cohort_orphan_does_not_double_count_registered(
    conn: sqlite3.Connection,
) -> None:
    """A trade whose label matches a registered cohort via suffix MUST NOT
    appear in the orphan-fallback second query."""
    _plant_trade(conn, ticker="REG",
                 hypothesis_label="A+ baseline (watch); note",
                 state="closed")
    conn.commit()
    counts = count_per_cohort(conn)
    assert counts["A+ baseline"] == 1
    # The suffix-bearing label MUST NOT also appear as an orphan key.
    assert "A+ baseline (watch); note" not in counts


def test_count_per_cohort_three_row_orphan_audit_invariant(
    conn: sqlite3.Connection,
) -> None:
    """Expansion #10 sub-discipline (e) regression -- plant 3 rows:
    registered-suffix + registered-exact + orphan; assert all 3 surface."""
    _plant_trade(conn, ticker="S1",
                 hypothesis_label="A+ baseline (watch); a",
                 state="closed")
    _plant_trade(conn, ticker="E1",
                 hypothesis_label="A+ baseline",
                 state="closed")
    _plant_trade(conn, ticker="O1",
                 hypothesis_label="totally-unregistered-cohort",
                 state="closed")
    conn.commit()
    counts = count_per_cohort(conn)
    assert counts["A+ baseline"] == 2  # suffix + exact aggregated
    assert counts["totally-unregistered-cohort"] == 1  # orphan preserved
