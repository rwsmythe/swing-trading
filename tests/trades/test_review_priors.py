"""Phase 13 T3.SB3 T-B.3.1 — Priors helpers per spec §E.4.

Covers:
  * ``ReviewPriors`` frozen dataclass shape + runtime validation guard.
  * ``get_priors_for_ticker(conn, ticker, n=5)`` returns ``ReviewPriors`` with
    mistake_tag_candidates + process_grade_baseline + lesson_learned_candidates.
  * Graceful at n=0 (no prior reviews → empty priors).
  * Numeric grade encoding A=4..F=0 for process_grade_baseline.
  * lesson_learned_candidates ordered most-recent-first.
  * ``n=5`` default (§E.4 LOCK).
  * Runtime range validation on process_grade_baseline (Literal-not-runtime-
    enforced gotcha; T-A.1.5b R3 M#1).
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import connect, ensure_schema


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    reviewed_at: str | None,
    mistake_tags: list[str] | None = None,
    process_grade: str | None = None,
    lesson_learned: str | None = None,
    state: str = "reviewed",
) -> int:
    """Insert a trade row + return its id. Bypasses the trade-entry service so
    we can plant ``state='reviewed'`` directly with the review-field set.
    """
    cursor = conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
        "current_size, reviewed_at, mistake_tags, process_grade, lesson_learned) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ticker, "2026-04-01", 10.0, 100, 9.0, 9.0, state,
            "manual_off_pipeline", "2026-04-01T09:30:00", 100.0,
            reviewed_at,
            json.dumps(mistake_tags) if mistake_tags is not None else None,
            process_grade,
            lesson_learned,
        ),
    )
    return cursor.lastrowid


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "priors.db"
    ensure_schema(db_path).close()
    conn = connect(db_path)
    yield conn
    conn.close()


# --- (a) Shape: returns ReviewPriors with 3 fields ---


def test_get_priors_for_ticker_returns_review_priors_with_three_fields(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import ReviewPriors, get_priors_for_ticker

    _seed_trade(
        db, ticker="ABC", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["CHASED", "FOMO"], process_grade="B",
        lesson_learned="Wait for proper base completion.",
    )
    db.commit()

    priors = get_priors_for_ticker(db, "ABC", n=5)
    assert isinstance(priors, ReviewPriors)
    assert isinstance(priors.mistake_tag_candidates, tuple)
    assert isinstance(priors.lesson_learned_candidates, tuple)
    assert priors.process_grade_baseline is not None
    # Union of all tags from the one row.
    assert set(priors.mistake_tag_candidates) == {"CHASED", "FOMO"}
    # B = 3.0 numeric.
    assert priors.process_grade_baseline == pytest.approx(3.0)
    assert priors.lesson_learned_candidates == (
        "Wait for proper base completion.",
    )


# --- (b) Edge case: zero priors → empty priors, no raise ---


def test_get_priors_for_ticker_zero_priors_returns_empty_priors(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import ReviewPriors, get_priors_for_ticker

    # No trades seeded for ticker XYZ.
    priors = get_priors_for_ticker(db, "XYZ", n=5)
    assert priors == ReviewPriors(
        mistake_tag_candidates=(),
        process_grade_baseline=None,
        lesson_learned_candidates=(),
    )


def test_get_priors_for_ticker_only_unreviewed_trades_returns_empty(
    db: sqlite3.Connection,
) -> None:
    """A trade in state='closed' (not 'reviewed') must NOT contribute priors."""
    from swing.trades.review import get_priors_for_ticker

    _seed_trade(
        db, ticker="ABC", reviewed_at=None,
        mistake_tags=None, process_grade=None, lesson_learned=None,
        state="closed",
    )
    db.commit()
    priors = get_priors_for_ticker(db, "ABC", n=5)
    assert priors.mistake_tag_candidates == ()
    assert priors.process_grade_baseline is None
    assert priors.lesson_learned_candidates == ()


# --- (c) Numeric grade encoding A=4..F=0 ---


@pytest.mark.parametrize(
    "grades, expected_mean",
    [
        (["A"], 4.0),
        (["B"], 3.0),
        (["C"], 2.0),
        (["D"], 1.0),
        (["F"], 0.0),
        (["A", "B"], 3.5),  # (4+3)/2
        (["A", "B", "C"], 3.0),  # (4+3+2)/3
        (["A", "F"], 2.0),  # (4+0)/2
    ],
)
def test_get_priors_for_ticker_process_grade_baseline_a_to_4_f_to_0_encoding(
    db: sqlite3.Connection, grades: list[str], expected_mean: float,
) -> None:
    from swing.trades.review import get_priors_for_ticker

    for i, g in enumerate(grades):
        _seed_trade(
            db, ticker="ABC", reviewed_at=f"2026-05-{i + 1:02d}T10:00:00",
            mistake_tags=["CHASED"], process_grade=g,
            lesson_learned=f"Lesson {i}.",
        )
    db.commit()

    priors = get_priors_for_ticker(db, "ABC", n=5)
    assert priors.process_grade_baseline == pytest.approx(expected_mean)


# --- (d) lesson_learned_candidates ordered most-recent-first ---


def test_get_priors_for_ticker_lesson_learned_ordered_most_recent_first(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_priors_for_ticker

    _seed_trade(
        db, ticker="ABC", reviewed_at="2026-04-15T10:00:00",
        mistake_tags=["CHASED"], process_grade="C",
        lesson_learned="Lesson OLD",
    )
    _seed_trade(
        db, ticker="ABC", reviewed_at="2026-05-15T10:00:00",
        mistake_tags=["FOMO"], process_grade="B",
        lesson_learned="Lesson NEW",
    )
    _seed_trade(
        db, ticker="ABC", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["NO_STOP"], process_grade="D",
        lesson_learned="Lesson MID",
    )
    db.commit()

    priors = get_priors_for_ticker(db, "ABC", n=5)
    assert priors.lesson_learned_candidates == (
        "Lesson NEW", "Lesson MID", "Lesson OLD",
    )


# --- (e) n=5 default per §E.4 LOCK ---


def test_get_priors_for_ticker_default_n_is_5_per_spec_e4_lock() -> None:
    from swing.trades.review import get_priors_for_ticker

    sig = inspect.signature(get_priors_for_ticker)
    n_param = sig.parameters["n"]
    assert n_param.default == 5, (
        f"§E.4 LOCK requires n=5 default; got {n_param.default!r}"
    )


# --- (f) n caps row count ---


def test_get_priors_for_ticker_n_caps_row_count(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_priors_for_ticker

    for i in range(7):
        _seed_trade(
            db, ticker="ABC",
            reviewed_at=f"2026-05-{i + 10:02d}T10:00:00",
            mistake_tags=[f"TAG_{i}"], process_grade="A",
            lesson_learned=f"Lesson {i}.",
        )
    db.commit()

    priors = get_priors_for_ticker(db, "ABC", n=3)
    # Only 3 lessons (n=3 cap); ordered most-recent-first.
    assert priors.lesson_learned_candidates == (
        "Lesson 6.", "Lesson 5.", "Lesson 4.",
    )


# --- (g) Runtime range validation (Literal-not-runtime-enforced gotcha) ---


def test_review_priors_post_init_rejects_process_grade_baseline_out_of_range() -> None:
    """``Literal[...]`` is NOT runtime-enforced (T-A.1.5b R3 M#1); a frozen
    dataclass with a numeric field on the data-integrity path MUST guard the
    range in ``__post_init__`` so an out-of-range value doesn't silently
    persist downstream."""
    from swing.trades.review import ReviewPriors

    with pytest.raises(ValueError, match="process_grade_baseline"):
        ReviewPriors(
            mistake_tag_candidates=(),
            process_grade_baseline=4.5,  # > 4.0 upper bound
            lesson_learned_candidates=(),
        )
    with pytest.raises(ValueError, match="process_grade_baseline"):
        ReviewPriors(
            mistake_tag_candidates=(),
            process_grade_baseline=-0.1,  # < 0.0 lower bound
            lesson_learned_candidates=(),
        )


def test_review_priors_post_init_rejects_non_tuple_candidates() -> None:
    """Frozen-dataclass immutability demands tuple-not-list for candidate
    fields (§E.4 LOCK)."""
    from swing.trades.review import ReviewPriors

    with pytest.raises(TypeError, match="mistake_tag_candidates"):
        ReviewPriors(
            mistake_tag_candidates=["CHASED"],  # type: ignore[arg-type]
            process_grade_baseline=None,
            lesson_learned_candidates=(),
        )
    with pytest.raises(TypeError, match="lesson_learned_candidates"):
        ReviewPriors(
            mistake_tag_candidates=(),
            process_grade_baseline=None,
            lesson_learned_candidates=["lesson"],  # type: ignore[arg-type]
        )


# --- (h) Different ticker isolation ---


def test_get_priors_for_ticker_isolates_by_ticker(
    db: sqlite3.Connection,
) -> None:
    from swing.trades.review import get_priors_for_ticker

    _seed_trade(
        db, ticker="AAA", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["CHASED"], process_grade="A",
        lesson_learned="Lesson AAA",
    )
    _seed_trade(
        db, ticker="BBB", reviewed_at="2026-05-01T10:00:00",
        mistake_tags=["FOMO"], process_grade="F",
        lesson_learned="Lesson BBB",
    )
    db.commit()

    priors_aaa = get_priors_for_ticker(db, "AAA", n=5)
    priors_bbb = get_priors_for_ticker(db, "BBB", n=5)
    assert priors_aaa.mistake_tag_candidates == ("CHASED",)
    assert priors_bbb.mistake_tag_candidates == ("FOMO",)
    assert priors_aaa.process_grade_baseline == pytest.approx(4.0)
    assert priors_bbb.process_grade_baseline == pytest.approx(0.0)
