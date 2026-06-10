from __future__ import annotations

from research.harness.shadow_expectancy import constants as c


def test_simulator_defaults_match_doctrine_constants():
    assert c.INITIAL_SHARES == 100.0
    assert c.PARTIAL_SESSION_N == 3
    assert c.PARTIAL_PCT == 0.5
    assert c.BREAKEVEN_R_TRIGGER == 1.0  # mirrors StopAdvisoryConfig.breakeven_r_trigger
    assert c.MATURITY_FAST_MA_R == 2.0   # >=+2R -> 10MA per _MATURITY_STAGE_TRAIL_MA
    assert (c.MA_FAST_PERIOD, c.MA_SLOW_PERIOD) == (10, 20)
    assert c.HORIZON_SESSIONS == 126
    assert c.SOURCE == "pipeline"


def test_breakeven_trigger_is_not_drifted_from_production():
    # Codex M4: a REAL anti-drift binding -- import the production config so a doctrine
    # change to breakeven_r_trigger breaks this harness test (not a hardcoded mirror).
    from swing.config import StopAdvisoryConfig
    assert StopAdvisoryConfig().breakeven_r_trigger == c.BREAKEVEN_R_TRIGGER


def test_maturity_ma_staging_is_not_drifted_from_production():
    # Codex M4: bind the harness 10/20 + >=+2R staging to the production
    # advisory._MATURITY_STAGE_TRAIL_MA dict. The pre-maturity stages map to "20MA"
    # (= MA_SLOW_PERIOD), the >=+2R-eligible stage maps to "10MA" (= MA_FAST_PERIOD).
    # A doctrine change to the staging dict breaks this test.
    from swing.trades.advisory import _MATURITY_STAGE_TRAIL_MA
    assert _MATURITY_STAGE_TRAIL_MA[">=+2R_trail_eligible"] == f"{c.MA_FAST_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["pre_+1.5R"] == f"{c.MA_SLOW_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["+1.5R_to_+2R"] == f"{c.MA_SLOW_PERIOD}MA"


def test_reason_vocabularies_are_frozen_tuples():
    assert "no_candidate_join" in c.FUNNEL_REASONS
    assert "invalid_ohlc" in c.FUNNEL_REASONS
    assert "degenerate_risk" in c.FUNNEL_REASONS
    assert "inconsistent_detection_series" in c.FUNNEL_REASONS
    assert "never_triggered" in c.FUNNEL_REASONS
    assert "matched_no_hypothesis" in c.FUNNEL_REASONS
    assert "multi_match" in c.FUNNEL_REASONS
    assert "no_candidate_pivot" in c.FUNNEL_REASONS          # correction: split from invalid_ohlc
    # retired by the entry/join correction (spec 3.1): no geometric pivot match remains.
    assert "no_canonical_detection" not in c.FUNNEL_REASONS
    assert "inconsistent_trigger_state" not in c.FUNNEL_REASONS
    # unattributed = pre-/non-attribution states only (spec 3.4): four reasons.
    assert set(c.UNATTRIBUTED_REASONS) == {
        "no_candidate_join", "matched_no_hypothesis", "multi_match",
        "inconsistent_detection_series",
    }
    # post-attribution per-hypothesis excluded reasons (spec 3.5): no_candidate_pivot added.
    assert set(c.ATTRIBUTED_EXCLUDED_REASONS) == {
        "no_candidate_pivot", "invalid_ohlc", "degenerate_risk",
        "insufficient_forward_depth", "missing_observations", "lifecycle",
    }
    assert set(c.ATTRIBUTED_EXCLUDED_REASONS).isdisjoint(set(c.UNATTRIBUTED_REASONS))
    assert set(c.EXIT_REASONS) == {
        "initial_stop", "breakeven_stop", "ma_close_below",
        "horizon_mtm", "never_triggered", "degenerate_risk",
    }
    assert set(c.BRACKET_ARMS) == {"realistic", "favorable_reprice"}
    assert set(c.CENSORING_SCENARIOS) == {
        "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
        "stop_level_adverse",
    }
