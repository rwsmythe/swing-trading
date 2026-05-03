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
