from __future__ import annotations

import statistics
from dataclasses import dataclass

from research.harness.shadow_expectancy.constants import BRACKET_ARMS
from swing.metrics.honesty import wilson_ci


@dataclass(frozen=True)
class ShadowTrade:
    hypothesis: str
    triggered: bool
    open_at_horizon: bool
    realized_r: dict | None   # {"realistic":R,"favorable_reprice":R}; None if degenerate
    entry_bar_ambiguous: bool
    holding_sessions: int
    censoring_scenarios: dict | None = None


_SCENARIO_NAMES = ("closed_only", "mtm_at_horizon",
                   "forced_exit_at_horizon_open", "stop_level_adverse")


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _scenario_value(trade: ShadowTrade, scenario: str, arm: str):
    """Codex C3: the per-trade contribution to a scenario mean.

    A CLOSED trade contributes its realized R in ALL FOUR scenarios (identical).
    An OPEN-at-horizon trade is EXCLUDED from closed_only (return None) and
    contributes its scenario-specific value in the other three.

    GRAIN NOTE (m3): this aggregate `closed_only` SCENARIO drops a still-open trade
    ENTIRELY (return None) -- it is the population of fully-closed trades. It is a
    DIFFERENT grain from the simulator's PER-TRADE `censoring_scenarios["closed_only"]`
    (Task 9), which reports a single open trade's already-realized partial-leg R. We
    intentionally do NOT fold an open trade's realized partial into the headline
    closed-only mean here; the per-trade value is available in the ledger/manifest for
    inspection. Same label, two grains -- documented in both tasks.
    """
    if not trade.open_at_horizon:
        return trade.realized_r[arm]
    if scenario == "closed_only":
        return None          # open trade excluded from the aggregate closed-only population
    return trade.censoring_scenarios[scenario][arm]


def build_hypothesis_scorecard(trades, *, sample_floor_mean, sample_floor_rate,
                               profit_factor_floor) -> dict:
    by_hyp: dict[str, list[ShadowTrade]] = {}
    for t in trades:
        by_hyp.setdefault(t.hypothesis, []).append(t)

    out: dict[str, dict] = {}
    for hyp, group in by_hyp.items():
        triggered = [t for t in group if t.triggered and t.realized_r is not None]
        closed = [t for t in triggered if not t.open_at_horizon]
        n_trig = len(triggered)
        n_closed = len(closed)
        card: dict = {}

        # FOUR censoring-scenario means, EACH over ALL triggered trades (D10 / C3).
        # closed contributes realized R in all four; open contributes scenario value
        # (excluded only in closed_only). n is the count actually contributing.
        scenarios: dict = {}
        for sc_name in _SCENARIO_NAMES:
            sc_entry: dict = {}
            n_contrib = None
            for arm in BRACKET_ARMS:
                vals = [v for t in triggered
                        if (v := _scenario_value(t, sc_name, arm)) is not None]
                sc_entry[arm] = _mean(vals)
                n_contrib = len(vals)
            sc_entry["n"] = n_contrib
            sc_entry["suppressed"] = n_contrib < sample_floor_mean
            scenarios[sc_name] = sc_entry
        card["scenarios"] = scenarios

        # Headline = realistic-arm closed-only (no MTM leak), explicitly labeled.
        card["headline_realistic_closed_only"] = scenarios["closed_only"]["realistic"]

        # per-signal expectancy (non-triggers count as 0R; D11). Realized R for closed,
        # MTM (realized_r) for open -- this is the "what did the signal do" per-signal view.
        n_signals = len(group)
        per_signal = {}
        for arm in BRACKET_ARMS:
            vals = [(t.realized_r[arm] if (t.triggered and t.realized_r is not None) else 0.0)
                    for t in group]
            per_signal[arm] = _mean(vals)
        card["per_signal_expectancy"] = per_signal

        # trigger rate (over ALL signals).
        card["trigger_rate"] = {"triggered": n_trig, "signals": n_signals,
                                "rate": (n_trig / n_signals if n_signals else 0.0)}

        # win rate + Wilson + avg win/loss + payoff + profit factor: CLOSED-only realized R
        # (no open-trade MTM leak; matches the headline basis).
        wins = sum(1 for t in closed if t.realized_r["realistic"] > 0)
        wci = wilson_ci(k=wins, n=n_closed) if n_closed else None
        card["win_rate"] = {
            "k": wins, "n": n_closed,
            "wilson": ({"point": wci.point, "lower": wci.lower, "upper": wci.upper}
                       if wci else None),
            "suppressed": n_closed < sample_floor_rate,
        }
        win_rs = [t.realized_r["realistic"] for t in closed if t.realized_r["realistic"] > 0]
        loss_rs = [t.realized_r["realistic"] for t in closed if t.realized_r["realistic"] <= 0]
        avg_win = _mean(win_rs)
        avg_loss = _mean(loss_rs)
        gross_win = sum(win_rs)
        gross_loss = -sum(loss_rs)
        card["avg_win_r"] = avg_win
        card["avg_loss_r"] = avg_loss
        card["payoff_ratio"] = (avg_win / abs(avg_loss)) if avg_loss < 0 else None
        card["profit_factor"] = {
            "value": (gross_win / gross_loss) if gross_loss > 0 else None,
            "suppressed": n_closed < profit_factor_floor,
        }
        card["median_holding_sessions"] = (
            statistics.median([t.holding_sessions for t in triggered]) if triggered else None)

        # same-bar-adverse sensitivity (D9): on the CLOSED-only basis, ambiguous trades -> -1R.
        ambiguous = [t for t in closed if t.entry_bar_ambiguous]
        card["ambiguous_count"] = len(ambiguous)
        adverse_mean = {}
        for arm in BRACKET_ARMS:
            vals = [(-1.0 if t.entry_bar_ambiguous else t.realized_r[arm]) for t in closed]
            adverse_mean[arm] = _mean(vals)
        card["same_bar_adverse_mean_r"] = adverse_mean

        out[hyp] = card
    return out
