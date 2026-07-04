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

# --- 19-D measurement policy (RD-RULED at plan review; values ARE the RD-locked finals) ---
# (a) Risk-unit floor: a mechanical risk-per-share below this fraction of the candidate's screening
# ADR (adr_pct) is degenerate -- a near-zero denominator inflates R without bound. Excluded as
# degenerate_risk. Discriminator: rps / (adr_pct/100 * entry_fill) < RISK_FLOOR_ADR_RATIO.
# Live calibration (2026-07-04): VSTS(catch)=0.0794, TVTX(survive)=0.2564; safe gap (0.0794, 0.2564).
# RD-locked 0.15: catches VSTS + the tight ARMK/PGNY cluster, well clear of TVTX 0.256.
# When adr_pct is null/<=0 the floor is DISABLED (graceful degrade to the old zero-floor) -- NO
# %-of-price fallback (that is the misclassifying form we reject; adr is 100%-populated in prod).
RISK_FLOOR_ADR_RATIO = 0.15
# (b) Epsilon-tolerant OHLC reader: a bar whose low sits above min(o,c) OR high below max(o,c) by
# <= this % of close is clamped (low=min(l,o,c), high=max(h,o,c)); above it stays invalid_ohlc.
# Reader-side ONLY -- the immutable log + archive are untouched. Live cluster 0.037%-0.771% (15
# bars); CALY 1.664% is the lone outlier. RD-locked 1.0 leaves CALY excluded.
OHLC_CLAMP_MAX_PCT = 1.0
# Max per-ticker clamp samples surfaced in the artifact summary/manifest (observability cap).
CLAMP_SAMPLE_LIMIT = 20

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
