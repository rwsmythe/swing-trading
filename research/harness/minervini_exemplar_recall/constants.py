# research/harness/minervini_exemplar_recall/constants.py
from __future__ import annotations

from swing.config import Config

H2_MIN_BARS = 60  # detector floor: enough bars for zigzag to emit >=1 down-swing.
CONTROL_GAP_BARS = 120  # min |session_pos - entry_pos| for a negative-control anchor.
DEFAULT_CONTROL_SEED = 20260608  # deterministic control-sampling base seed.
EQUITY_FLOOR_SURROGATE = 7500.0  # flagged surrogate; H1 risk gate uses this, not a real account.


def screenable_floor(config: Config) -> int:
    """200 + rising_ma_period_days. Below this TT3 (200MA rising) is an UNALLOWED
    na -> bucket_for forces skip regardless of merit, so we classify such names
    skip_insufficient_history (not a gate rejection)."""
    return 200 + config.trend_template.rising_ma_period_days
