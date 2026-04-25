"""Tests for swing.recommendations.hypothesis.match_candidate_to_hypotheses.

Per brief §4.2 + §5 watch items:
- na counts as non-pass (matches `bucket_for` semantics)
- Closed hypotheses are not matched
- Multi-match is allowed when multiple ACTIVE hypotheses fit
"""
from __future__ import annotations

from swing.data.models import Candidate, CriterionResult, HypothesisRegistryEntry
from swing.recommendations.hypothesis import (
    DOCTRINE_DEFENSIBLE_MISS_SET,
    HypothesisMatch,
    match_candidate_to_hypotheses,
)


def _candidate(bucket: str, results: list[tuple[str, str, str]] | None = None) -> Candidate:
    """Build a minimal Candidate. results is [(name, layer, result), ...]."""
    crit = tuple(
        CriterionResult(criterion_name=n, layer=l, result=r) for (n, l, r) in (results or [])
    )
    return Candidate(
        ticker="TEST", bucket=bucket,
        close=10.0, pivot=11.0, initial_stop=9.0, adr_pct=4.0,
        tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="universe",
        pattern_tag=None, notes=None, criteria=crit,
    )


def _registry() -> list[HypothesisRegistryEntry]:
    """Mirror the v0.1 seed (matcher should query by name not id)."""
    return [
        HypothesisRegistryEntry(
            id=1, name="A+ baseline",
            statement="x", target_sample_size=20,
            decision_criteria="x", status="active",
            consecutive_loss_tripwire=5, absolute_loss_tripwire_pct=5.0,
            created_at="2026-04-25",
        ),
        HypothesisRegistryEntry(
            id=2, name="Near-A+ defensible: extension test",
            statement="x", target_sample_size=10,
            decision_criteria="x", status="active",
            consecutive_loss_tripwire=4, absolute_loss_tripwire_pct=5.0,
            created_at="2026-04-25",
        ),
        HypothesisRegistryEntry(
            id=3, name="Sub-A+ VCP-not-formed",
            statement="x", target_sample_size=5,
            decision_criteria="x", status="active",
            consecutive_loss_tripwire=3, absolute_loss_tripwire_pct=5.0,
            created_at="2026-04-25",
        ),
        HypothesisRegistryEntry(
            id=4, name="Capital-blocked: smaller-position test",
            statement="x", target_sample_size=10,
            decision_criteria="x", status="active",
            consecutive_loss_tripwire=4, absolute_loss_tripwire_pct=5.0,
            created_at="2026-04-25",
        ),
    ]


def test_doctrine_defensible_set_frozen():
    """Brief §0 + Finviz study D1: frozen at TT8_rs_rank, risk_feasibility,
    proximity_20ma."""
    assert DOCTRINE_DEFENSIBLE_MISS_SET == frozenset(
        {"TT8_rs_rank", "risk_feasibility", "proximity_20ma"}
    )


def test_aplus_candidate_matches_aplus_baseline():
    cand = _candidate("aplus")
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    assert len(matches) == 1
    assert matches[0].hypothesis_name == "A+ baseline"
    assert matches[0].hypothesis_id == 1
    assert "aplus" in matches[0].suggested_label_descriptive.lower()


def test_aplus_candidate_only_matches_aplus_when_other_hypotheses_active():
    """A+ candidate should not also match watch-bucket hypotheses."""
    cand = _candidate("aplus")
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    assert {m.hypothesis_name for m in matches} == {"A+ baseline"}


def test_near_aplus_extension_candidate_matches_extension_test():
    """Watch bucket; ONLY proximity_20ma fails — defensible extension miss."""
    cand = _candidate("watch", results=[
        ("TT1_above_150_200", "trend_template", "pass"),
        ("proximity_20ma", "vcp", "fail"),
        ("tightness", "vcp", "pass"),
        ("vcp_volume_contraction", "vcp", "pass"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Near-A+ defensible: extension test" in names
    # Should NOT also match Sub-A+ VCP-not-formed (proximity is not in the
    # tightness/vcp set)
    assert "Sub-A+ VCP-not-formed" not in names


def test_near_aplus_extension_rejects_when_additional_failures():
    """Watch + proximity + something else fails → not pure extension test."""
    cand = _candidate("watch", results=[
        ("proximity_20ma", "vcp", "fail"),
        ("adr", "vcp", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Near-A+ defensible: extension test" not in names


def test_sub_aplus_vcp_not_formed_matches_tightness_failure():
    """Watch + tightness in non-pass; everything else either pass or in
    (tightness, vcp_volume_contraction, defensible_set)."""
    cand = _candidate("watch", results=[
        ("proximity_20ma", "vcp", "fail"),  # in defensible set
        ("tightness", "vcp", "fail"),       # the trigger
        ("vcp_volume_contraction", "vcp", "pass"),
        ("adr", "vcp", "pass"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Sub-A+ VCP-not-formed" in names


def test_sub_aplus_vcp_not_formed_matches_vcp_volume_contraction():
    cand = _candidate("watch", results=[
        ("vcp_volume_contraction", "vcp", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Sub-A+ VCP-not-formed" in names


def test_sub_aplus_vcp_not_formed_rejects_when_outside_failures():
    """Watch + tightness + something OUTSIDE allowed set → not VCP-not-formed."""
    cand = _candidate("watch", results=[
        ("tightness", "vcp", "fail"),
        ("adr", "vcp", "fail"),  # outside allowed set
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Sub-A+ VCP-not-formed" not in names


def test_capital_blocked_test_matches_only_risk_feasibility_failure():
    cand = _candidate("watch", results=[
        ("risk_feasibility", "risk", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Capital-blocked: smaller-position test" in names


def test_capital_blocked_test_rejects_when_additional_failures():
    cand = _candidate("watch", results=[
        ("risk_feasibility", "risk", "fail"),
        ("proximity_20ma", "vcp", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Capital-blocked: smaller-position test" not in names


def test_na_counts_as_non_pass_per_bucket_for_semantics():
    """Brief §5 explicit decision: na counts as non-pass (matches
    `bucket_for` semantics that treat na as fail for VCP gating). A
    candidate with proximity=fail + tightness=na should NOT match the
    'extension test' (which requires non-pass == {proximity_20ma} alone)."""
    cand = _candidate("watch", results=[
        ("proximity_20ma", "vcp", "fail"),
        ("tightness", "vcp", "na"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Near-A+ defensible: extension test" not in names
    # tightness=na also triggers Sub-A+ VCP-not-formed (na counts as
    # non-pass; both other failures are in allowed set)
    assert "Sub-A+ VCP-not-formed" in names


def test_skip_bucket_no_match():
    cand = _candidate("skip", results=[("risk_feasibility", "risk", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    # No active hypothesis matches `skip` bucket
    assert matches == []


def test_excluded_bucket_no_match():
    cand = _candidate("excluded")
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    assert matches == []


def test_closed_hypothesis_is_not_matched():
    """closed-escaped, closed-target-met, paused → not in active set."""
    registry = _registry()
    # close out the A+ baseline hypothesis
    registry[0] = HypothesisRegistryEntry(
        id=1, name="A+ baseline", statement="x", target_sample_size=20,
        decision_criteria="x", status="closed-target-met",
        consecutive_loss_tripwire=5, absolute_loss_tripwire_pct=5.0,
        created_at="2026-04-25",
    )
    cand = _candidate("aplus")
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=registry,
    )
    assert matches == []


def test_paused_hypothesis_is_not_matched():
    registry = _registry()
    registry[2] = HypothesisRegistryEntry(
        id=3, name="Sub-A+ VCP-not-formed", statement="x",
        target_sample_size=5, decision_criteria="x", status="paused",
        consecutive_loss_tripwire=3, absolute_loss_tripwire_pct=5.0,
        created_at="2026-04-25",
    )
    cand = _candidate("watch", results=[("tightness", "vcp", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=registry,
    )
    assert all(m.hypothesis_name != "Sub-A+ VCP-not-formed" for m in matches)


def test_match_descriptive_label_includes_failure_summary():
    """The descriptive label is what the operator sees as the hypothesis-tag
    pre-fill suggestion. It must encode bucket + which criteria failed so
    later matching by `startswith` (tripwire) works."""
    cand = _candidate("watch", results=[
        ("tightness", "vcp", "fail"),
        ("proximity_20ma", "vcp", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    sub = next(m for m in matches if m.hypothesis_name == "Sub-A+ VCP-not-formed")
    assert sub.suggested_label_descriptive.startswith(sub.hypothesis_name)
    assert "tightness" in sub.suggested_label_descriptive
    assert "proximity_20ma" in sub.suggested_label_descriptive


def test_match_returns_priority_hint():
    """Prioritizer downstream sorts by hypothesis distance-to-target then
    breaks ties on this hint. Stable hint = (closer to pivot wins among
    same-hypothesis candidates), surfaced as a small numeric for now."""
    cand = _candidate("aplus")
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    assert len(matches) == 1
    assert isinstance(matches[0].priority_hint, (int, float))
