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

# --- Funnel reason vocabulary (7.1) ---
FUNNEL_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_canonical_detection", "invalid_ohlc", "inconsistent_detection_series",
    "inconsistent_trigger_state", "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle", "never_triggered",
)
# Reasons reported WITHIN the unattributed bucket (PRE-/NON-attribution states only;
# Codex R4-m1 + C-review M1/M2/M4 + R3-M1, spec 7.1). Under the join -> attribute ->
# validate -> simulate order, the unattributed states are the JOIN/COLLAPSE-stage ones
# below PLUS matched_no_hypothesis (candidate joined + valid but matched ZERO hypotheses)
# PLUS multi_match (candidate matched >1 hypothesis). All six are REASONS within the
# single `unattributed` bucket -- each reported with its own counter in the reason
# breakdown; there is NO separate top-level matched_no_hypothesis / multi_match bucket
# (C-review M1). matched_no_hypothesis is DISTINCT from no_candidate_join (candidate row
# missing) and from no_canonical_detection (candidate present but no detection pivot
# matches it -- a collapse/substrate-integrity fault; C-review M4). multi_match (R3-M1)
# is a DEFENSIVE reason: the 4 seeded hypotheses are mutually exclusive by their
# exact-miss-set definitions, so it should be ~0 today, but excluding a >1-match signal
# here (rather than emitting one outcome PER matched hypothesis) keeps the reconciliation
# invariant -- Sum(unattributed reason counts) + Sum(per-hypothesis terminal-status
# counts) == unique_signals -- exact for a future non-exclusive hypothesis.
# Validation/simulation failures on an ATTRIBUTED (exactly-one-match) signal (invalid_ohlc
# / degenerate_risk) are caught AFTER attribution and reported PER-HYPOTHESIS in that
# hypothesis's excluded[...], NOT unattributed (spec 7.1).
UNATTRIBUTED_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_canonical_detection", "inconsistent_detection_series",
    "inconsistent_trigger_state",
)
# writing-plans R5: the ONLY reasons a POST-attribution (per-hypothesis) `excluded` terminal may
# carry. DISJOINT from UNATTRIBUTED_REASONS by construction, so an unattributed-only reason can
# never be silently miscounted under a hypothesis (build_funnel rejects it).
ATTRIBUTED_EXCLUDED_REASONS = (
    "invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle",
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
