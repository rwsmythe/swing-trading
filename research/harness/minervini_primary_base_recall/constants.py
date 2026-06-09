from __future__ import annotations

# Reuse the FROZEN harness's control-sampling constants (do NOT redefine).
from research.harness.minervini_exemplar_recall.constants import (  # noqa: F401
    CONTROL_GAP_BARS,
    DEFAULT_CONTROL_SEED,
)

# --- Minervini primary base, TWoSMW Ch.11 (quantified per spec section 2/5) ---
# "at least a couple of months of trading activity" -> ~2 months ~= 40 trading days.
MIN_HISTORY_BARS = 40
# "a base of at least three to five weeks" -> >= 3 weeks ~= 15 trading days.
MIN_BASE_BARS = 15
# Zigzag swing threshold for base identification (spec section 5 crit 2; matches the
# foundation generate_candidate_windows zigzag_pivot default).
ZIGZAG_THRESHOLD_PCT = 3.0

# Graduated correction-depth caps keyed on base duration in BARS (spec section 5 crit 4):
#   <=25 bars (~5wk): 0.25 ; 26-200 bars: 0.35 ; >200 bars (~1yr): 0.50.
# (max_inclusive_bars, cap) ordered ascending; a deliberately literal mapping of the Ch.11 prose.
DEPTH_LADDER: tuple[tuple[int, float], ...] = ((25, 0.25), (200, 0.35))
DEPTH_LADDER_TOP_CAP = 0.50


def depth_cap(duration_bars: int) -> float:
    """The graduated max correction depth (fraction) for a base of duration_bars bars."""
    for max_bars, cap in DEPTH_LADDER:
        if duration_bars <= max_bars:
            return cap
    return DEPTH_LADDER_TOP_CAP


# --- Precision control (spec section 4/6) ---
# Young-window control pool ceiling: ~first 2 years post-IPO (504 trading days). The pre-filter
# range is [MIN_HISTORY_BARS-1, MAX_CONTROL_AGE_BARS-1] = [39, 503].
MAX_CONTROL_AGE_BARS = 504
# The ORIGINAL Minervini-recall study's screenable floor (200 + rising_ma_period_days = 221):
# names with fewer bars-through-anchor were un-screenable there (the sub-floor cohort); >= this
# is a "sufficient-history" positive control.
YOUNG_NAME_CEILING_BARS = 221
CONTROL_K = 5

# --- Timing sweep window (positional, spec section 6) ---
WINDOW_BACK = 60
WINDOW_FWD = 5
