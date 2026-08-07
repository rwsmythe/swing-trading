"""Bucket classification: aplus / watch / skip / excluded / error.

NA results count as fails for bucket determination — insufficient data is a fail.

**THE A+ STRUCTURAL GATE IS SINGLE-SOURCED HERE (item 3b).** `criteria_lapsed`
needs to ask "does this name still pass the A+ structural gate?" of a
`candidate_criteria` ROW SET, while the evaluator asks it of `Result` objects.
Neither can hand the other its own type, so the rule is stated once over the
REDUCTION both can produce (`StructuralInputs`) — one rule, two adapters, never
two rules. A second independently-plausible implementation of one rule is the
drift class that produced `mandate_limit_price`'s round-vs-floor split.

`risk_feasibility` is EXCLUDED from the gate and that exclusion is RD's, not a
convenience: a `skip` produced by the risk pre-filter alone is STRUCTURALLY A+,
so reading the bucket label instead would let the operator's own capital
withdraw his mandate.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from swing.config import Config
from swing.evaluation.criteria._base import Result

# THE EXPECTED ROSTERS, written out explicitly and DRIFT-PINNED by a test that
# runs a real `evaluate_one` and asserts the emitted names equal these sets.
#
# Deriving them at runtime is not implementable: `trend_template.evaluate(ctx)`
# is a RUNTIME call returning a list, there is no static name export, and
# obtaining the names that way would need a constructed `CandidateContext` and
# risk an import cycle. So the codebase's existing shape applies -- write the
# roster out once and pin it against the real emitter (the same discipline
# `DEFAULT_LATCH_HORIZON_SESSIONS` uses against `PipelineConfig`). A criterion
# added, renamed or removed then fails that test rather than silently changing
# what the gate means.
EXPECTED_TT_CRITERIA = frozenset({
    "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
    "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct", "TT8_rs_rank",
})
EXPECTED_VCP_CRITERIA = frozenset({
    "adr", "ma_short_rising", "ma_stack_10_20_50", "orderliness",
    "prior_trend", "proximity_20ma", "pullback", "tightness",
    "vcp_volume_contraction",
})


@dataclass(frozen=True)
class StructuralInputs:
    """The reduced form BOTH callers can supply.

    `tt_pass_count` counts `result == "pass"` ONLY, so every non-pass TT result
    -- `fail` AND `na` -- reduces it; `tt_failed_names` names every non-pass TT
    for the allowed-miss test; `vcp_fail_count` counts `result in ("fail",
    "na")`. That asymmetry is the SHIPPED `bucket_for`'s and is preserved
    deliberately: an adapter that treats a TT `na` as neutral can falsely PASS
    the gate.
    """

    tt_pass_count: int
    tt_failed_names: tuple[str, ...]
    vcp_fail_count: int


def structural_inputs_from_results(
    trend_template_results: Sequence[Result],
    vcp_results: Sequence[Result],
) -> StructuralInputs:
    """The EVALUATOR's adapter: `Result` objects -> the reduced form."""
    return StructuralInputs(
        tt_pass_count=sum(
            1 for r in trend_template_results if r.result == "pass"),
        tt_failed_names=tuple(
            r.name for r in trend_template_results if r.result != "pass"),
        vcp_fail_count=sum(
            1 for r in vcp_results if r.result in ("fail", "na")),
    )


def structural_gate_passes(inputs: StructuralInputs, config: Config) -> bool:
    """Does this name pass the A+ STRUCTURAL gate? RISK IS NOT CONSULTED.

    The gate is `bucket_for` MINUS its risk pre-filter and MINUS the `watch`
    band: the TT gate, then zero vcp failures. `bucket_for` composes this
    function, so the two can never disagree about what "structurally A+" means.
    """
    allowed = set(config.trend_template.allowed_miss_names)
    if inputs.tt_pass_count < config.trend_template.min_passes:
        return False
    if not all(n in allowed for n in inputs.tt_failed_names):
        return False
    return inputs.vcp_fail_count == 0


def bucket_for(
    trend_template_results: Sequence[Result],
    vcp_results: Sequence[Result],
    risk_results: Sequence[Result],
    config: Config,
) -> str:
    # Risk is a hard filter
    if any(r.result != "pass" for r in risk_results):
        return "skip"

    # Trend Template gate: (a) enough passes AND (b) every failing TT is in
    # allowed_miss_names. This matches spec §4.1 — the allowed fail is
    # configurable, TT8 is the default. Composed from `structural_gate_passes`
    # so this function and the latch reader read ONE rule; behaviour-identical,
    # pinned by the T2.1 characterization table.
    inputs = structural_inputs_from_results(trend_template_results, vcp_results)
    allowed = set(config.trend_template.allowed_miss_names)
    if inputs.tt_pass_count < config.trend_template.min_passes:
        return "skip"
    if not all(n in allowed for n in inputs.tt_failed_names):
        return "skip"

    if structural_gate_passes(inputs, config):
        return "aplus"
    if inputs.vcp_fail_count <= 2:
        return "watch"
    return "skip"
