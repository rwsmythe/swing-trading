from __future__ import annotations

# --- Simulator unit-of-analysis defaults (spec D1-D12) ---
INITIAL_SHARES = 100.0          # nominal fractional entry unit (D2/5.1)
PARTIAL_SESSION_N = 3           # Day-3 partial (D4/5.3); session-N configurable
PARTIAL_PCT = 0.5               # sell 50% of initial_shares (D4)
BREAKEVEN_R_TRIGGER = 1.0       # mirrors swing.config.StopAdvisoryConfig.breakeven_r_trigger (5.4)
MATURITY_FAST_MA_R = 2.0        # >=+2R -> 10MA per advisory._MATURITY_STAGE_TRAIL_MA (D12/5.5)
MA_FAST_PERIOD = 10             # maturity-staged 10/20 proxy (D12)
MA_SLOW_PERIOD = 20
HORIZON_SESSIONS = 126          # ~6 months (D5); bounded by available bars
SOURCE = "pipeline"            # temporal-log detection source filter (6: A+ isolation)
PRICE_TICK_DECIMALS = 4         # normalized pivot-match precision (6, Codex R5-m1)

# --- Honesty / suppression sample floors (7.2) ---
SAMPLE_FLOOR_MEAN = 5           # mean-R suppression floor
SAMPLE_FLOOR_RATE = 5           # win-rate Wilson floor (still reported, annotated)
PROFIT_FACTOR_FLOOR = 5         # profit-factor suppressed below this n

# --- Funnel reason vocabulary (7.1; entry/join correction 3.1-3.5) ---
FUNNEL_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_candidate_pivot", "invalid_ohlc", "inconsistent_detection_series",
    "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle", "never_triggered",
)
# Reasons reported WITHIN the unattributed bucket (PRE-/NON-attribution states only; spec 3.4).
# The retired no_canonical_detection / inconsistent_trigger_state are GONE (the geometric
# detection.pivot is no longer consulted for entry or collapse). matched_no_hypothesis and
# multi_match are reasons WITHIN this single bucket, not separate top-level buckets. A
# post-attribution data-quality fault (no_candidate_pivot / invalid_ohlc / degenerate_risk) is
# reported PER-HYPOTHESIS in ATTRIBUTED_EXCLUDED_REASONS, never here.
UNATTRIBUTED_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "inconsistent_detection_series",
)
# The ONLY reasons a POST-attribution (per-hypothesis) `excluded` terminal may carry. DISJOINT
# from UNATTRIBUTED_REASONS by construction. no_candidate_pivot (spec 3.2) joins + attributes,
# then is excluded at validate -> per-hypothesis, exactly like invalid_ohlc / degenerate_risk.
ATTRIBUTED_EXCLUDED_REASONS = (
    "no_candidate_pivot", "invalid_ohlc", "degenerate_risk",
    "insufficient_forward_depth", "missing_observations", "lifecycle",
)

EXIT_REASONS = (
    "initial_stop", "breakeven_stop", "ma_close_below",
    "horizon_mtm", "never_triggered", "degenerate_risk",
)
BRACKET_ARMS = ("realistic", "favorable_reprice")
CENSORING_SCENARIOS = (
    "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
    "stop_level_adverse",
)
HARNESS_VERSION = "0.1.0"
