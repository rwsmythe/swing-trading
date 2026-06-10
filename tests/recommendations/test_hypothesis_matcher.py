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
    H_BROAD_WATCH_BASELINE,
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


def test_capital_blocked_matches_skip_bucket_when_only_risk_feasibility_fails():
    """Adversarial review R1 Major 1: production gating buckets
    risk_feasibility-only failures as `skip` (hard pre-filter), so the
    matcher must accept `bucket == 'skip'` for the hypothesis to fire on
    real data. Without this, the Capital-blocked hypothesis is dead-on-
    arrival in production."""
    cand = _candidate("skip", results=[
        ("risk_feasibility", "risk", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Capital-blocked: smaller-position test" in names


def test_capital_blocked_skip_bucket_label_annotated_for_clarity():
    """Adversarial review R2 Minor 2: rendering bucket as bare `(skip)`
    in the saved label would read as "rejected" in the operator-facing
    text, contradicting the recommendation to take the trade with
    smaller position. The label annotates as `(skip; capital-blocked)`
    so the deliberate nature is visible in the journal."""
    cand = _candidate("skip", results=[
        ("risk_feasibility", "risk", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    capital = next(
        m for m in matches
        if m.hypothesis_name == "Capital-blocked: smaller-position test"
    )
    assert "skip; capital-blocked" in capital.suggested_label_descriptive
    # Watch-bucket variant (e.g. replay harness) keeps the bare bucket.
    cand_watch = _candidate("watch", results=[
        ("risk_feasibility", "risk", "fail"),
    ])
    matches_watch = match_candidate_to_hypotheses(
        cand_watch, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    capital_watch = next(
        m for m in matches_watch
        if m.hypothesis_name == "Capital-blocked: smaller-position test"
    )
    assert "(watch)" in capital_watch.suggested_label_descriptive


def test_capital_blocked_skip_bucket_rejects_when_other_failures():
    """skip-bucket candidate failing risk_feasibility AND something else
    is NOT capital-blocked — there are multiple blockers, smaller-
    position alone won't unblock the trade."""
    cand = _candidate("skip", results=[
        ("risk_feasibility", "risk", "fail"),
        ("TT1_above_150_200", "trend_template", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
    names = {m.hypothesis_name for m in matches}
    assert "Capital-blocked: smaller-position test" not in names


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


def test_skip_bucket_with_unrelated_failure_no_match():
    """A skip-bucket candidate with failures OUTSIDE the capital-blocked
    rule does not match any hypothesis. (Capital-blocked specifically
    accepts skip + only-risk_feasibility — see
    test_capital_blocked_matches_skip_bucket_when_only_risk_feasibility_fails.)
    """
    cand = _candidate("skip", results=[
        ("TT1_above_150_200", "trend_template", "fail"),
        ("adr", "vcp", "fail"),
    ])
    matches = match_candidate_to_hypotheses(
        cand, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET,
        registry=_registry(),
    )
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


def _registry_with_baseline(*, h3_status: str = "active"):
    """The 4 v0.1 rows + the migration-0026 baseline row (active).
    h3_status lets a test close H3 to exercise the active-set complement."""
    reg = _registry()
    for i, h in enumerate(reg):
        if h.name == "Sub-A+ VCP-not-formed":
            reg[i] = HypothesisRegistryEntry(
                id=h.id, name=h.name, statement=h.statement,
                target_sample_size=h.target_sample_size,
                decision_criteria=h.decision_criteria, status=h3_status,
                consecutive_loss_tripwire=h.consecutive_loss_tripwire,
                absolute_loss_tripwire_pct=h.absolute_loss_tripwire_pct,
                created_at=h.created_at,
            )
    reg.append(HypothesisRegistryEntry(
        id=5, name="Broad-watch baseline",
        statement="x", target_sample_size=30,
        decision_criteria="x", status="active",
        consecutive_loss_tripwire=5, absolute_loss_tripwire_pct=5.0,
        created_at="2026-06-09",
    ))
    return reg


def test_broad_watch_name_constant():
    assert H_BROAD_WATCH_BASELINE == "Broad-watch baseline"


def test_baseline_fires_only_with_opt_in_for_pure_watch():
    # Fixture 5 (spec §9.1.5): a real {adr} watch miss (no H2/H3/H4 fit).
    cand = _candidate("watch", [("adr", "vcp", "fail")])
    reg = _registry_with_baseline()
    # default include_baseline=False -> live path -> ZERO matches (containment).
    assert match_candidate_to_hypotheses(cand, registry=reg) == []
    # opt-in -> exactly the baseline.
    matches = match_candidate_to_hypotheses(cand, registry=reg, include_baseline=True)
    assert [m.hypothesis_name for m in matches] == ["Broad-watch baseline"]


def test_baseline_silent_when_narrow_rule_fires_h2():
    # Fixture 2 (spec §9.1.2): anti-cannibalization. {proximity_20ma} -> H2 ONLY.
    cand = _candidate("watch", [("proximity_20ma", "trend_template", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True)
    names = [m.hypothesis_name for m in matches]
    assert names == ["Near-A+ defensible: extension test"]   # len==1, NO baseline


def test_baseline_silent_when_narrow_rule_fires_h4():
    # Fixture 3 (spec §9.1.3): {risk_feasibility} watch -> H4 ONLY.
    cand = _candidate("watch", [("risk_feasibility", "risk", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True)
    assert [m.hypothesis_name for m in matches] == [
        "Capital-blocked: smaller-position test"]


def test_baseline_membership_flips_on_h3_active_status():
    # Fixture 4 (spec §9.1.4): the dominant real shape {tightness, vcp_volume_contraction}.
    cand = _candidate("watch", [("tightness", "vcp", "fail"),
                                ("vcp_volume_contraction", "vcp", "fail")])
    # H3 ACTIVE -> H3 claims it; baseline silent.
    m_active = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(h3_status="active"),
        include_baseline=True)
    assert [m.hypothesis_name for m in m_active] == ["Sub-A+ VCP-not-formed"]
    # H3 CLOSED (today's live state) -> falls to the baseline.
    m_closed = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(h3_status="closed-target-met"),
        include_baseline=True)
    assert [m.hypothesis_name for m in m_closed] == ["Broad-watch baseline"]


def test_baseline_does_not_fire_for_non_watch_even_opted_in():
    # Baseline requires bucket=='watch'. A skip miss stays unmatched (keeps the
    # matched_no_hypothesis funnel reason reachable). Spec §9.1 / §7.2.
    cand = _candidate("skip", [("tightness", "vcp", "fail")])
    assert match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True) == []


def test_baseline_absent_from_registry_yields_no_match_even_opted_in():
    # If the baseline row is not present+active (e.g. pre-0026), the gate cannot
    # synthesize a match (no id) -> []. Order-robust by construction.
    cand = _candidate("watch", [("adr", "vcp", "fail")])
    assert match_candidate_to_hypotheses(
        cand, registry=_registry(), include_baseline=True) == []


def test_broad_watch_name_no_prefix_collision_both_directions():
    # Spec §6: 3-rule delimiter-aware contract; no prefix collision either way.
    from swing.metrics.label_match import label_matches_hypothesis
    others = ["A+ baseline", "Near-A+ defensible: extension test",
              "Sub-A+ VCP-not-formed", "Capital-blocked: smaller-position test"]
    labelled = "Broad-watch baseline (watch); failed: adr"
    for other in others:
        assert label_matches_hypothesis(labelled, other) is False
        assert label_matches_hypothesis(f"{other} (watch); failed: x",
                                        "Broad-watch baseline") is False
    # exact-name still matches itself.
    assert label_matches_hypothesis("Broad-watch baseline", "Broad-watch baseline")
