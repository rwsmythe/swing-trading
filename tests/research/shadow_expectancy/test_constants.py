from __future__ import annotations

from research.harness.shadow_expectancy import constants as C


def test_simulator_defaults_match_doctrine_constants():
    assert C.INITIAL_SHARES == 100.0
    assert C.PARTIAL_SESSION_N == 3
    assert C.PARTIAL_PCT == 0.5
    assert C.BREAKEVEN_R_TRIGGER == 1.0  # mirrors StopAdvisoryConfig.breakeven_r_trigger
    assert C.MATURITY_FAST_MA_R == 2.0   # >=+2R -> 10MA per _MATURITY_STAGE_TRAIL_MA
    assert (C.MA_FAST_PERIOD, C.MA_SLOW_PERIOD) == (10, 20)
    assert C.HORIZON_SESSIONS == 126
    assert C.SOURCE == "pipeline"


def test_breakeven_trigger_is_NOT_drifted_from_production():
    # Codex M4: a REAL anti-drift binding -- import the production config so a doctrine
    # change to breakeven_r_trigger breaks this harness test (not a hardcoded mirror).
    from swing.config import StopAdvisoryConfig
    assert C.BREAKEVEN_R_TRIGGER == StopAdvisoryConfig().breakeven_r_trigger


def test_maturity_ma_staging_is_NOT_drifted_from_production():
    # Codex M4: bind the harness 10/20 + >=+2R staging to the production
    # advisory._MATURITY_STAGE_TRAIL_MA dict. The pre-maturity stages map to "20MA"
    # (= MA_SLOW_PERIOD), the >=+2R-eligible stage maps to "10MA" (= MA_FAST_PERIOD).
    # A doctrine change to the staging dict breaks this test.
    from swing.trades.advisory import _MATURITY_STAGE_TRAIL_MA
    assert _MATURITY_STAGE_TRAIL_MA[">=+2R_trail_eligible"] == f"{C.MA_FAST_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["pre_+1.5R"] == f"{C.MA_SLOW_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["+1.5R_to_+2R"] == f"{C.MA_SLOW_PERIOD}MA"


def test_reason_vocabularies_are_frozen_tuples():
    assert "no_candidate_join" in C.FUNNEL_REASONS
    assert "invalid_ohlc" in C.FUNNEL_REASONS
    assert "degenerate_risk" in C.FUNNEL_REASONS
    assert "inconsistent_detection_series" in C.FUNNEL_REASONS
    assert "inconsistent_trigger_state" in C.FUNNEL_REASONS
    assert "never_triggered" in C.FUNNEL_REASONS
    assert "matched_no_hypothesis" in C.FUNNEL_REASONS  # C-review M1: a reason WITHIN unattributed
    assert "no_canonical_detection" in C.FUNNEL_REASONS  # C-review M4: candidate present, no pivot match
    assert "multi_match" in C.FUNNEL_REASONS             # R3-M1: defensive >1-hypothesis guard
    # The unattributed bucket's six PRE-/NON-attribution reasons (spec 7.1; C-review M1/M4 +
    # R3-M1 multi_match -- a signal matching >1 hypothesis is excluded here, NOT counted in
    # each, so the reconciliation invariant stays exact).
    assert set(C.UNATTRIBUTED_REASONS) == {
        "no_candidate_join", "matched_no_hypothesis", "no_canonical_detection",
        "multi_match", "inconsistent_detection_series", "inconsistent_trigger_state",
    }
    # writing-plans R5: post-attribution `excluded` reasons, DISJOINT from the unattributed set.
    assert set(C.ATTRIBUTED_EXCLUDED_REASONS) == {
        "invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
        "missing_observations", "lifecycle",
    }
    assert set(C.ATTRIBUTED_EXCLUDED_REASONS).isdisjoint(set(C.UNATTRIBUTED_REASONS))
    assert set(C.EXIT_REASONS) == {
        "initial_stop", "breakeven_stop", "ma_close_below",
        "horizon_mtm", "never_triggered", "degenerate_risk",
    }
    assert set(C.BRACKET_ARMS) == {"realistic", "favorable_reprice"}
    assert set(C.CENSORING_SCENARIOS) == {
        "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
        "stop_level_adverse",
    }
