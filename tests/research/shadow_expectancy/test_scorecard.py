from __future__ import annotations

import math

from research.harness.shadow_expectancy.scorecard import (
    ShadowTrade, build_hypothesis_scorecard,
)


def _arms(v):
    return {"realistic": v, "favorable_reprice": v}


def _t(hyp, realistic_r, favorable_r, *, triggered=True, open_h=False,
       ambiguous=False, sessions=5, scenarios=None):
    return ShadowTrade(hypothesis=hyp, triggered=triggered, open_at_horizon=open_h,
                       realized_r={"realistic": realistic_r,
                                   "favorable_reprice": favorable_r},
                       entry_bar_ambiguous=ambiguous, holding_sessions=sessions,
                       censoring_scenarios=scenarios)


def test_four_scenario_means_over_all_triggered_trades():
    # Codex C3: each scenario mean is over ALL triggered trades. A closed trade contributes
    # its realized R in ALL FOUR scenarios; an open trade is EXCLUDED in closed_only but
    # contributes its scenario-specific value elsewhere.
    closed = [_t("A+ baseline", 2.0, 2.0), _t("A+ baseline", -1.0, -1.0)]
    open_t = _t("A+ baseline", 0.5, 0.5, open_h=True, scenarios={
        "closed_only": _arms(0.0), "mtm_at_horizon": _arms(0.6),
        "forced_exit_at_horizon_open": _arms(0.4), "stop_level_adverse": _arms(-0.2)})
    sc = build_hypothesis_scorecard([*closed, open_t], sample_floor_mean=2,
                                    sample_floor_rate=2, profit_factor_floor=2)
    card = sc["A+ baseline"]
    s = card["scenarios"]
    # closed_only: the open trade is EXCLUDED -> mean over the 2 closed only = (2.0-1.0)/2 = 0.5
    assert math.isclose(s["closed_only"]["realistic"], 0.5)
    assert s["closed_only"]["n"] == 2          # open trade dropped
    # mtm: closed contribute realized R; open contributes its mtm value 0.6 -> (2-1+0.6)/3
    assert math.isclose(s["mtm_at_horizon"]["realistic"], (2.0 - 1.0 + 0.6) / 3)
    assert math.isclose(s["forced_exit_at_horizon_open"]["realistic"], (2.0 - 1.0 + 0.4) / 3)
    assert math.isclose(s["stop_level_adverse"]["realistic"], (2.0 - 1.0 - 0.2) / 3)
    # headline = realistic-arm closed-only, explicitly labeled (no MTM leak).
    assert math.isclose(card["headline_realistic_closed_only"], 0.5)
    # both arms reported for every scenario.
    for name in ("closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
                 "stop_level_adverse"):
        assert set(s[name]) >= {"realistic", "favorable_reprice", "n", "suppressed"}


def test_closed_only_winrate_wilson_no_mtm_leak():
    # win rate + Wilson computed on the CLOSED-only realized R (no open-trade MTM leak).
    closed = [_t("A+ baseline", 2.0, 2.0), _t("A+ baseline", -1.0, -1.0),
              _t("A+ baseline", 1.5, 1.5), _t("A+ baseline", -1.0, -1.0)]
    open_t = _t("A+ baseline", 9.9, 9.9, open_h=True, scenarios={
        "closed_only": _arms(0.0), "mtm_at_horizon": _arms(9.9),
        "forced_exit_at_horizon_open": _arms(9.9), "stop_level_adverse": _arms(0.0)})
    sc = build_hypothesis_scorecard([*closed, open_t], sample_floor_mean=2,
                                    sample_floor_rate=2, profit_factor_floor=2)
    card = sc["A+ baseline"]
    assert card["win_rate"]["k"] == 2 and card["win_rate"]["n"] == 4   # open NOT counted
    assert "wilson" in card["win_rate"]
    assert card["trigger_rate"]["triggered"] == 5     # trigger rate IS over all triggered


def test_profit_factor_suppressed_below_floor():
    trades = [_t("H3", 1.0, 1.0), _t("H3", -1.0, -1.0)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=10, sample_floor_rate=10,
                                    profit_factor_floor=10)
    assert sc["H3"]["profit_factor"]["suppressed"] is True
    assert sc["H3"]["scenarios"]["closed_only"]["suppressed"] is True


def test_per_signal_vs_triggered_distinct():
    trades = [_t("H4", 2.0, 2.0, triggered=True),
              _t("H4", 0.0, 0.0, triggered=False)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=1, sample_floor_rate=1,
                                    profit_factor_floor=1)
    # headline (closed-only) over 1 closed triggered trade = 2.0; per-signal over 2 signals = 1.0
    assert math.isclose(sc["H4"]["headline_realistic_closed_only"], 2.0)
    assert math.isclose(sc["H4"]["per_signal_expectancy"]["realistic"], 1.0)


def test_same_bar_adverse_sensitivity_only_over_ambiguous():
    trades = [_t("A+ baseline", 2.0, 2.0, ambiguous=True),
              _t("A+ baseline", 1.0, 1.0, ambiguous=False)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=1, sample_floor_rate=1,
                                    profit_factor_floor=1)
    card = sc["A+ baseline"]
    # base closed-only mean = 1.5; adverse forces the ambiguous trade to -1R -> (-1 + 1)/2 = 0.0
    assert math.isclose(card["headline_realistic_closed_only"], 1.5)
    assert math.isclose(card["same_bar_adverse_mean_r"]["realistic"], 0.0)
    assert card["ambiguous_count"] == 1
