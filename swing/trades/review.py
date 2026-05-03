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
