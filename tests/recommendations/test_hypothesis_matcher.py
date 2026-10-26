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
    cand = _candidate("aplus", [("risk_feasibility", "risk", "pass")])
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
    cand = _candidate("aplus", [("risk_feasibility", "risk", "pass")])
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


# ===========================================================================
# D84 T4 -- H1 = aplus AND the risk layer passes; H4 = aplus AND the risk layer
# is flagged; an EMPTY risk layer matches neither; the old `watch|skip` H4 form
# is DROPPED (RD). Supersedes, by name:
#   test_capital_blocked_test_matches_only_risk_feasibility_failure -> R-H4-KOD
#   test_capital_blocked_matches_skip_bucket_when_only_risk_feasibility_fails
#       -> R-(iv)'
#   test_capital_blocked_skip_bucket_label_annotated_for_clarity -> R-E4
# and deletes test_capital_blocked_skip_bucket_rejects_when_other_failures and
# test_capital_blocked_test_rejects_when_additional_failures, which went
# VACUOUS (no watch/skip candidate can match H4 by construction); their
# discrimination is carried by R-(iii) and R-(iv)'.
# ===========================================================================

_H1 = "A+ baseline"
_H4 = "Capital-blocked: smaller-position test"

_TT_ROSTER = (
    "TT1_above_150_200", "TT2_150_above_200", "TT3_200_rising",
    "TT4_50_above_150_200", "TT5_above_50", "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct", "TT8_rs_rank",
)
_VCP_ROSTER = (
    "prior_trend", "ma_stack_10_20_50", "ma_short_rising", "proximity_20ma",
    "adr", "pullback", "tightness", "vcp_volume_contraction", "orderliness",
)


def _kod_candidate(bucket: str = "aplus", *, overrides=None, risk="fail",
                   extra_risk=()) -> Candidate:
    """The 18-criterion roster all `pass` except `risk_feasibility`, on the
    real KOD geometry (pivot 104.00, stop 29.81, close 98.46; candidates
    14815-14947, runs 175-178). The real KOD rows carry FIVE non-pass
    criteria, so the roster is constructed, as RD worded it."""
    overrides = overrides or {}
    crit = [CriterionResult(criterion_name=n, layer="trend_template",
                            result=overrides.get(n, "pass"))
            for n in _TT_ROSTER]
    crit += [CriterionResult(criterion_name=n, layer="vcp",
                             result=overrides.get(n, "pass"))
             for n in _VCP_ROSTER]
    crit.append(CriterionResult(
        criterion_name="risk_feasibility", layer="risk", result=risk,
        value="0 sh, $0.00 risk" if risk == "fail" else "1 sh, $37.00 risk",
        rule=">= 1 share fits in 0.5% of equity ($37.50)"))
    for name, result in extra_risk:
        crit.append(CriterionResult(criterion_name=name, layer="risk",
                                    result=result))
    return Candidate(
        ticker="KOD", bucket=bucket,
        close=98.46, pivot=104.00, initial_stop=29.81, adr_pct=6.0,
        tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="universe",
        pattern_tag=None, notes=None, criteria=tuple(crit),
    )


def _names(cand, **kw):
    return [m.hypothesis_name
            for m in match_candidate_to_hypotheses(cand, registry=_registry(), **kw)]


def test_acceptance_ii_the_H1_matcher_returns_False_on_a_risk_fail_aplus():  # noqa: N802
    """R-(ii) -- THE ANTI-VACUITY CHECK. On a risk-fail `aplus` candidate H1 is
    False and the match set is exactly {H4}. It kills a bucket-only amendment:
    before D84, H1 was True and H4 False on this candidate."""
    from swing.recommendations.hypothesis import _aplus_baseline_match

    cand = _kod_candidate()
    assert _aplus_baseline_match(cand) is False
    assert _names(cand) == [_H4]


def test_acceptance_iii_a_risk_pass_aplus_is_H1_and_not_H4():  # noqa: N802
    """R-(iii) -- a GUARD (E-h, ACCEPTED by RD): true before and after D84, so
    it cannot be RED-first. Its discriminating mutation was RUN once at the
    plan stage, in a scratch `git archive` of `b1415630`: with the mutant
    `_capital_blocked_match := return candidate.bucket == "aplus"` (H4 defined
    as aplus-only) this test went red on the multi-match:

        E       AssertionError: assert ['A+ baseline...osition test'] == ['A+ baseline']
        E         Left contains one more item: 'Capital-blocked: smaller-position test'
    """
    assert _names(_kod_candidate(risk="pass")) == [_H1]


def test_acceptance_iv_REPLACED_a_pre_boundary_shaped_skip_row_matches_NO_hypothesis():  # noqa: N802
    """R-(iv)' -- the closed-population pin (RD round-0 ruling): "0 exact-{risk}
    rows and 0 exact-{risk, TT8_rs_rank} rows in all 312 risk non-pass rows
    since 2026-04-16 (runs 1-180), 0 Capital-blocked trades". A `skip`
    candidate whose non-pass set is exactly {risk_feasibility} matches NO
    hypothesis, with every hypothesis active (H5 opted in)."""
    cand = _candidate("skip", [("risk_feasibility", "risk", "fail")])
    assert match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True) == []


def test_the_H4_positive_pin_on_the_real_KOD_geometry():  # noqa: N802
    """R-H4-KOD. Supersedes
    `test_capital_blocked_test_matches_only_risk_feasibility_failure`: H4 no
    longer admits `watch` (RD: the old form is dropped)."""
    assert _names(_kod_candidate()) == [_H4]


def test_the_H4_label_is_aplus_with_the_flag_in_the_failed_list():  # noqa: N802
    """R-E4. Supersedes `test_capital_blocked_skip_bucket_label_annotated_for_
    clarity`: the `(skip; capital-blocked)` annotation branch is deleted."""
    from swing.metrics.label_match import label_matches_hypothesis

    (m,) = match_candidate_to_hypotheses(_kod_candidate(), registry=_registry())
    assert m.suggested_label_descriptive == (
        "Capital-blocked: smaller-position test (aplus); failed: risk_feasibility")
    assert label_matches_hypothesis(m.suggested_label_descriptive, _H4)


def test_H4_admits_the_allowed_TT8_miss():  # noqa: N802
    """R-T4.1 -- RD (iii): A+ allows the allowed miss, so does H4."""
    cand = _kod_candidate(overrides={"TT8_rs_rank": "fail"})
    assert _names(cand) == [_H4]


def test_the_matcher_adapter_is_LAYER_keyed():  # noqa: N802
    """R-T4.2 -- CHARC E2's "second spelling the day the risk layer has two
    criteria". `risk_feasibility` passes but a SECOND risk-layer criterion
    fails: H1 False, H4 True. A name-keyed implementation would pass H1. The
    same holds for `risk_feasibility` = `na` (RD (vi))."""
    from swing.recommendations.hypothesis import (
        _aplus_baseline_match,
        _capital_blocked_match,
    )

    two = _kod_candidate(risk="pass", extra_risk=(("risk_other", "fail"),))
    assert _aplus_baseline_match(two) is False
    assert _capital_blocked_match(two) is True
    assert _names(two) == [_H4]
    na = _kod_candidate(risk="na")
    assert _aplus_baseline_match(na) is False
    assert _names(na) == [_H4]


def test_an_aplus_candidate_with_NO_risk_row_matches_NOTHING():  # noqa: N802
    """R-T4.4 -- E-d REVERSED, the matcher consumer: an `aplus` candidate with
    TT and VCP rows only is neither H1 nor H4, so `_descriptive_label` is never
    reached. The `[]` holds with `include_baseline=True` too: the baseline
    fallback is watch-only (R3-02)."""
    cand = _candidate("aplus", [("TT1_above_150_200", "trend_template", "pass"),
                                ("adr", "vcp", "pass")])
    assert match_candidate_to_hypotheses(cand, registry=_registry()) == []
    assert match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True) == []


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
    """A skip-bucket candidate matches no hypothesis: since D84 no
    hypothesis admits `skip` (Capital-blocked is `aplus` AND a flagged risk
    layer; the pre-boundary `skip` + only-risk_feasibility form was dropped,
    see `test_acceptance_iv_REPLACED_a_pre_boundary_shaped_skip_row_matches_
    NO_hypothesis`)."""
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
    # A risk PASS row, so the CLOSED status is the only reason it does not
    # match: under D84 E-d an A+ with an EMPTY risk layer matches nothing even
    # while H1 is active, which left this test passing for the wrong reason.
    cand = _candidate("aplus", [("risk_feasibility", "risk", "pass")])
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
    cand = _candidate("aplus", [("risk_feasibility", "risk", "pass")])
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


def test_a_risk_fail_watch_falls_to_the_broad_watch_baseline():
    """Supersedes `test_baseline_silent_when_narrow_rule_fires_h4` (D84).
    {risk_feasibility} on a `watch` candidate is no longer H4 (H4 is `aplus`
    only), so with the baseline opted in it falls to H5 by the fallback rule
    (RD (iv))."""
    cand = _candidate("watch", [("risk_feasibility", "risk", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True)
    assert [m.hypothesis_name for m in matches] == ["Broad-watch baseline"]


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
