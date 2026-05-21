"""Phase 6 post-trade review pure helpers.

This module owns:
  * MISTAKE_TAGS vocabulary (verbatim from v1.2 §7.10 — 6 categories, 34 tags).
  * Process Grade computation (added Task 4).
  * Mistake cost / lucky violation derivation (added Task 5).
  * profit_factor + max_drawdown_R aggregation helpers (added Task 5).
  * Cadence-period boundary helpers (added Task 7).
  * Soft-warn-at-close shared message constant (added Task 9).

All functions are pure (no I/O) and side-effect-free; testable with
parameterized inputs.
"""
from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from swing.data.models import Trade
from swing.data.repos.trades import get_trade, update_trade_review_fields
from swing.evaluation.dates import last_completed_session
from swing.trades.state import state_transition

# C.14: ``Exit`` is deleted. Function signatures here use ``ExitLike = Any``
# for exits parameters — consumers pass duck-typed ExitLike-shape objects
# (the per-module ``_ExitShape`` adapters from C.1/C.9/C.10/C.14) which
# expose ``.r_multiple``, ``.shares``, ``.trade_id``, ``.exit_date`` — all
# that the review aggregations require.
ExitLike = Any  # Structural duck-type alias for Exit-shape adapter rows.

# ---- Mistake_Tags vocabulary (v1.2 §7.10 verbatim) ----

MISTAKE_TAGS: dict[str, tuple[str, ...]] = {
    "entry": (
        "CHASED", "EARLY_ENTRY", "LATE_ENTRY", "NO_SETUP",
        "LOW_LIQUIDITY", "EVENT_IGNORED",
    ),
    "risk": (
        "OVERSIZED", "NO_STOP", "STOP_TOO_WIDE", "STOP_TOO_TIGHT",
        "CORRELATION_IGNORED", "GAP_RISK_IGNORED", "HEAT_OVERAGE",
        "CIRCUIT_BREAKER_OVERRIDDEN",
    ),
    "management": (
        "MOVED_STOP_AWAY", "SOLD_TOO_EARLY", "HELD_AFTER_INVALIDATION",
        "FAILED_TO_SCALE", "ADDED_TO_LOSER", "MISSED_TIME_STOP",
    ),
    "psychology": (
        "FOMO", "REVENGE", "BOREDOM", "EGO", "ANCHORING",
        "CONFIRMATION_BIAS", "LOSS_AVERSION", "OVERCONFIDENCE",
    ),
    "reconciliation": (
        "SIZE_MISCOUNTED", "WRONG_TICKER_ENTERED", "FILL_NOT_LOGGED",
        "PARTIAL_NOT_LOGGED", "STOP_NOT_PLACED",
    ),
    "none": (
        "none_observed",
    ),
}

ALL_MISTAKE_TAGS: frozenset[str] = frozenset(
    tag for tags in MISTAKE_TAGS.values() for tag in tags
)


def validate_mistake_tags(tags: list[str]) -> None:
    """Raise ValueError if `tags` contains anything not in ALL_MISTAKE_TAGS,
    or if 'none_observed' co-exists with any other tag."""
    for t in tags:
        if t not in ALL_MISTAKE_TAGS:
            raise ValueError(f"unknown mistake tag: {t!r}")
    if "none_observed" in tags and len(tags) > 1:
        raise ValueError(
            "none_observed cannot co-exist with any other mistake tag"
        )


def canonicalize_mistake_tags(tags: list[str]) -> list[str]:
    """NFC normalize, strip, dedupe, sort. Idempotent."""
    canonical = sorted({
        unicodedata.normalize("NFC", t.strip())
        for t in tags
        if t.strip()
    })
    return canonical


# ---- Process Grade (v1.2 §9.2 verbatim) ----

STAGE_GRADE_NUMERIC: dict[str, int] = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
WEIGHTS: dict[str, float] = {"entry": 0.40, "management": 0.35, "exit": 0.25}
DISQUALIFYING_VIOLATIONS: tuple[str, ...] = (
    "no_stop", "oversized_beyond_policy", "no_valid_setup", "revenge_trade",
    "circuit_breaker_override", "held_after_invalidation_without_rule_basis",
    "moved_stop_away_materially_increasing_risk",
)


def compute_process_grade(
    *, entry: str, management: str, exit_: str, disqualifying: bool,
) -> str:
    """Return overall process grade per v1.2 §9.2.

    Order of evaluation:
      1. Floor rule: any stage = 'F' → 'F'.
      2. Cap rule: disqualifying=True → max D (or F when weighted < 1.00).
      3. Otherwise: weighted avg → grade per numeric_to_grade boundaries.
    """
    if (entry not in STAGE_GRADE_NUMERIC
            or management not in STAGE_GRADE_NUMERIC
            or exit_ not in STAGE_GRADE_NUMERIC):
        raise ValueError(
            f"stage grades must be one of {sorted(STAGE_GRADE_NUMERIC)}; "
            f"got entry={entry!r}, management={management!r}, exit_={exit_!r}"
        )
    if entry == "F" or management == "F" or exit_ == "F":
        return "F"
    weighted = (
        WEIGHTS["entry"] * STAGE_GRADE_NUMERIC[entry]
        + WEIGHTS["management"] * STAGE_GRADE_NUMERIC[management]
        + WEIGHTS["exit"] * STAGE_GRADE_NUMERIC[exit_]
    )
    if disqualifying:
        if weighted < 1.00:
            return "F"
        return "D"
    if weighted >= 3.50:
        return "A"
    if weighted >= 2.75:
        return "B"
    if weighted >= 2.00:
        return "C"
    if weighted >= 1.00:
        return "D"
    return "F"


# ---- Cost / Lucky / R helpers (v1.2 §8.4 + §8.8 + §8.9) ----

def compute_actual_realized_R_effective(  # noqa: N802
    trade: Trade, exits: list[ExitLike],
) -> float:
    """Share-weighted realized R for `trade` per v1.2 §8.4.

    Mirror of swing.journal.stats._trade_r — same formula. Re-implemented
    here per the journal/-read-only carve-out (plan §A.1).
    """
    total = 0.0
    for e in exits:
        if e.trade_id != trade.id:
            continue
        total += e.r_multiple * (e.shares / trade.initial_shares)
    return total


def compute_mistake_cost_R(  # noqa: N802
    *, realized_R_if_plan_followed: float | None,  # noqa: N803
    actual_realized_R_effective: float,  # noqa: N803
) -> float:
    """v1.2 §8.8: max(0, plan - actual). Never netted with lucky."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, realized_R_if_plan_followed - actual_realized_R_effective)


def compute_lucky_violation_R(  # noqa: N802
    *, realized_R_if_plan_followed: float | None,  # noqa: N803
    actual_realized_R_effective: float,  # noqa: N803
) -> float:
    """v1.2 §8.8: max(0, actual - plan). Never netted with cost."""
    if realized_R_if_plan_followed is None:
        return 0.0
    return max(0.0, actual_realized_R_effective - realized_R_if_plan_followed)


def compute_profit_factor(
    closed_trades: list[Trade], exits: list[ExitLike],
) -> float | None:
    """v1.2 §8.9: sum(R where > 0) / abs(sum(R where < 0)).

    Returns None when there are no losses (denominator zero). Returns 0.0 when
    there are no wins but there are losses.
    """
    rs = [compute_actual_realized_R_effective(t, exits) for t in closed_trades]
    gross_wins = sum(r for r in rs if r > 0)
    gross_losses = sum(r for r in rs if r < 0)
    if gross_losses == 0:
        return None
    return gross_wins / abs(gross_losses)


def compute_max_drawdown_R(  # noqa: N802
    closed_trades: list[Trade], exits: list[ExitLike],
) -> float:
    """Maximum peak-to-trough drawdown over the closed-date-ordered cumulative
    R-series. Returned as a non-negative magnitude. Returns 0.0 for empty
    input or no drawdown.
    """
    if not closed_trades:
        return 0.0
    decorated = sorted(
        ((t, compute_actual_realized_R_effective(t, exits),
          _trade_closed_date_for_review(t, exits))
         for t in closed_trades),
        key=lambda x: x[2] or date.min,
    )
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for _t, r, _cd in decorated:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown


def _trade_closed_date_for_review(trade: Trade, exits: list[ExitLike]) -> date | None:
    """Mirror of swing.journal.stats._trade_closed_date — same formula.
    Re-implemented per journal/-read-only carve-out (plan §A.1).

    Phase 7 Sub-B B.6: predicate is closed-or-reviewed because this helper
    answers "has the trade fully exited?" — both terminal states qualify
    (a reviewed trade is, by definition, also closed). Spec §2.1 reserves
    the bare ``state != 'closed'`` form for the per-trade review precondition,
    where 'reviewed' must be REJECTED.

    The body walks an ``exits`` list of duck-typed ExitLike-shape adapter
    rows (per-module ``_ExitShape`` adapters wrap fills via
    ``swing/trades/derived_metrics.py``); the legacy ``Exit`` dataclass is
    deleted (Sub-C C.14).
    """
    if trade.state not in ("closed", "reviewed"):
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None


# ---- Cadence-period boundary helpers (locked decision §2.7) ----

# ---- Soft-warn message (shared between web + CLI close paths) ----


def soft_warn_review_due_message(window_days: int = 7) -> str:
    """Compose the close-path soft-warn message with the cfg-driven window.

    Codex R1 Minor 1: window_days was hardcoded to 7 in the constant, which
    drifts from cfg.review.review_window_days if the operator changes the
    config. Callers should pass cfg.review.review_window_days.
    """
    return (
        f"Review due within {window_days} days. "
        f"Run `swing trade review --trade-id <id>` "
        f"or visit /trades/<id>/review."
    )


# Default-7 alias retained for backwards-compatibility (e.g., test imports).
SOFT_WARN_REVIEW_DUE_MESSAGE: str = soft_warn_review_due_message(7)


def compute_daily_period(now: datetime) -> tuple[date, date]:
    session = last_completed_session(now)
    return session, session


def compute_weekly_period(now: datetime) -> tuple[date, date]:
    today = last_completed_session(now)
    this_monday = today - timedelta(days=today.weekday())
    prior_monday = this_monday - timedelta(days=7)
    prior_friday = prior_monday + timedelta(days=4)
    return prior_monday, prior_friday


def compute_monthly_period(now: datetime) -> tuple[date, date]:
    today = last_completed_session(now)
    first_of_this_month = today.replace(day=1)
    last_of_prior = first_of_this_month - timedelta(days=1)
    first_of_prior = last_of_prior.replace(day=1)
    return first_of_prior, last_of_prior


# ---- Phase 13 T3.SB3 — Review priors (per spec §E.4) ----

# §E.4 LOCK: default N = 5 recent reviews for the same ticker.
REVIEW_PRIORS_DEFAULT_N: int = 5


@dataclass(frozen=True)
class ReviewPriors:
    """Per-ticker prior-review aggregates surfaced to the review form (§E.4).

    Fields:
      * ``mistake_tag_candidates``: union of mistake_tags across recent N
        reviewed trades for the ticker (tuple-of-str for frozen-dataclass
        immutability).
      * ``process_grade_baseline``: mean of recent N process_grade values
        under the numeric encoding A=4..F=0; ``None`` when no prior review
        carries a recognizable grade.
      * ``lesson_learned_candidates``: most-recent-first list of distinct
        non-empty ``lesson_learned`` entries from recent N reviews.

    ``Literal[...]`` is NOT runtime-enforced (T-A.1.5b R3 M#1 gotcha); the
    ``__post_init__`` guard rejects out-of-range ``process_grade_baseline``
    + non-tuple candidate fields to keep data-integrity contracts honest at
    the construction boundary.
    """
    mistake_tag_candidates: tuple[str, ...]
    process_grade_baseline: float | None
    lesson_learned_candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mistake_tag_candidates, tuple):
            raise TypeError(
                "ReviewPriors.mistake_tag_candidates must be tuple[str, ...]; "
                f"got {type(self.mistake_tag_candidates).__name__}"
            )
        if not isinstance(self.lesson_learned_candidates, tuple):
            raise TypeError(
                "ReviewPriors.lesson_learned_candidates must be tuple[str, "
                "...]; got "
                f"{type(self.lesson_learned_candidates).__name__}"
            )
        if self.process_grade_baseline is not None:
            if not isinstance(self.process_grade_baseline, (int, float)):
                raise TypeError(
                    "ReviewPriors.process_grade_baseline must be float | "
                    f"None; got {type(self.process_grade_baseline).__name__}"
                )
            if not (0.0 <= float(self.process_grade_baseline) <= 4.0):
                raise ValueError(
                    "ReviewPriors.process_grade_baseline must lie in "
                    f"[0.0, 4.0]; got {self.process_grade_baseline!r}"
                )


def get_priors_for_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    n: int = REVIEW_PRIORS_DEFAULT_N,
) -> ReviewPriors:
    """Return per-ticker review priors over the most-recent N reviewed
    trades (§E.4 LOCK; default N=5).

    Reads from the ``trades`` table where ``state='reviewed'`` AND
    ``reviewed_at IS NOT NULL`` for the supplied ticker, ordered most-
    recent-first by ``reviewed_at``.

    Graceful at n=0 / no priors per spec §A.16: returns an empty
    ``ReviewPriors`` (empty tuples + ``None`` baseline) without raising.

    Per the spec §6.3 surface contract: each field is operator-editable in
    the review form; this helper supplies only the DEFAULT input values.
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError(
            f"get_priors_for_ticker requires a non-empty ticker; got {ticker!r}"
        )
    if not isinstance(n, int) or n < 0:
        raise ValueError(
            f"get_priors_for_ticker n must be a non-negative int; got {n!r}"
        )
    if n == 0:
        return ReviewPriors(
            mistake_tag_candidates=(),
            process_grade_baseline=None,
            lesson_learned_candidates=(),
        )

    rows = conn.execute(
        "SELECT mistake_tags, process_grade, lesson_learned "
        "FROM trades "
        "WHERE ticker = ? AND state = 'reviewed' AND reviewed_at IS NOT NULL "
        "ORDER BY reviewed_at DESC "
        "LIMIT ?",
        (ticker, n),
    ).fetchall()

    mistake_tag_set: set[str] = set()
    grade_values: list[float] = []
    lessons_ordered: list[str] = []
    seen_lessons: set[str] = set()
    for row in rows:
        mistake_tags_json, process_grade, lesson_learned = row[0], row[1], row[2]
        if mistake_tags_json:
            try:
                parsed = json.loads(mistake_tags_json)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list):
                # Per-row failure isolation (T2.SB5 R1 M#1 forward-binding
                # lesson #2): a single malformed tag must not poison the
                # rest of the cohort.
                for tag in parsed:
                    if isinstance(tag, str) and tag:
                        mistake_tag_set.add(tag)
        if isinstance(process_grade, str):
            grade = STAGE_GRADE_NUMERIC.get(process_grade)
            if grade is not None:
                grade_values.append(float(grade))
        if isinstance(lesson_learned, str):
            lesson = lesson_learned.strip()
            if lesson and lesson not in seen_lessons:
                lessons_ordered.append(lesson)
                seen_lessons.add(lesson)

    if grade_values:
        baseline: float | None = sum(grade_values) / len(grade_values)
    else:
        baseline = None

    return ReviewPriors(
        mistake_tag_candidates=tuple(sorted(mistake_tag_set)),
        process_grade_baseline=baseline,
        lesson_learned_candidates=tuple(lessons_ordered),
    )


def complete_trade_review(
    conn: sqlite3.Connection,
    trade_id: int,
    *,
    reviewed_at: str,
    mistake_tags_json: str,
    entry_grade: str,
    management_grade: str,
    exit_grade: str,
    process_grade: str,
    disqualifying_process_violation: bool | None,
    realized_R_if_plan_followed: float | None,  # noqa: N803
    mistake_cost_confidence: str | None,
    lesson_learned: str,
    event_ts: str,
    rationale: str | None = None,
) -> None:
    """Atomic per-trade review completion.

    Phase 7 Sub-B B.6 service-layer wrapper. Validates the trade is in the
    ``'closed'`` state, then in a single transaction:

      1. Writes the 10 Phase 6 review fields (delegated to
         ``update_trade_review_fields``).
      2. Transitions the trade ``closed → reviewed`` (delegated to
         ``state_transition``).

    Both writes land in the SAME ``with conn:`` block so the row-update and
    the state-machine audit are atomic — if the state transition raises, the
    review-fields UPDATE is rolled back too.

    Spec §2.1 (precondition): the trade MUST be in ``'closed'``. Reviewed is
    REJECTED (single-review-per-trade in V1; an already-reviewed trade is a
    terminal state). Active states (entered/managing/partial_exited) are also
    REJECTED — review is post-exit only.

    Callers (CLI Sub-B B.7, web Sub-C T1) replace their direct
    ``update_trade_review_fields`` invocation with this wrapper to gain the
    state transition for free.
    """
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.state != "closed":
        raise ValueError(
            f"trade {trade_id} is not in closed state (state={trade.state!r})"
        )
    with conn:
        update_trade_review_fields(
            conn,
            trade_id=trade_id,
            reviewed_at=reviewed_at,
            mistake_tags_json=mistake_tags_json,
            entry_grade=entry_grade,
            management_grade=management_grade,
            exit_grade=exit_grade,
            process_grade=process_grade,
            disqualifying_process_violation=disqualifying_process_violation,
            realized_R_if_plan_followed=realized_R_if_plan_followed,
            mistake_cost_confidence=mistake_cost_confidence,
            lesson_learned=lesson_learned,
        )
        state_transition(
            conn,
            trade_id=trade_id,
            new_state="reviewed",
            event_ts=event_ts,
            rationale=rationale,
        )
