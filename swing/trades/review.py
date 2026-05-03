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

import unicodedata
from datetime import date, datetime, timedelta

from swing.data.models import Exit, Trade
from swing.evaluation.dates import last_completed_session

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
    trade: Trade, exits: list[Exit],
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
    closed_trades: list[Trade], exits: list[Exit],
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
    closed_trades: list[Trade], exits: list[Exit],
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


def _trade_closed_date_for_review(trade: Trade, exits: list[Exit]) -> date | None:
    """Mirror of swing.journal.stats._trade_closed_date — same formula.
    Re-implemented per journal/-read-only carve-out (plan §A.1).
    """
    if trade.status != "closed":
        return None
    relevant = [e.exit_date for e in exits if e.trade_id == trade.id]
    return max(date.fromisoformat(d) for d in relevant) if relevant else None


# ---- Cadence-period boundary helpers (locked decision §2.7) ----

# ---- Soft-warn message constant (shared between web + CLI close paths) ----

SOFT_WARN_REVIEW_DUE_MESSAGE: str = (
    "Review due within 7 days. Run `swing trade review --trade-id <id>` "
    "or visit /trades/<id>/review."
)


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
