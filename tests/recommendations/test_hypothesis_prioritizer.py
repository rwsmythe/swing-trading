"""Tests for swing.recommendations.hypothesis.prioritize_recommendations.

Per brief §4.3:
- Active hypotheses far from target sample size get higher priority
- Hypotheses with `tripwire_fired` status fall to bottom
- Closed hypotheses produce no recommendations
- Within same hypothesis, candidates ordered by priority_hint, then ticker
"""
from __future__ import annotations

from swing.data.models import HypothesisRegistryEntry
from swing.recommendations.hypothesis import (
    CandidateRecommendation,
    HypothesisMatch,
    HypothesisProgressSummary,
    prioritize_recommendations,
)


def _h(name: str, status: str = "active", target: int = 10) -> HypothesisRegistryEntry:
    return HypothesisRegistryEntry(
        id=hash(name) & 0xffff,
        name=name, statement="x", target_sample_size=target,
        decision_criteria="x", status=status,
        consecutive_loss_tripwire=3, absolute_loss_tripwire_pct=5.0,
        created_at="2026-04-25",
    )


def _registry() -> list[HypothesisRegistryEntry]:
    return [
        _h("A+ baseline", target=20),
        _h("Near-A+ defensible: extension test", target=10),
        _h("Sub-A+ VCP-not-formed", target=5),
        _h("Capital-blocked: smaller-position test", target=10),
    ]


def _match(name: str, ticker: str, hint: float = 0.05,
           registry: list[HypothesisRegistryEntry] | None = None) -> HypothesisMatch:
    reg = registry or _registry()
    h = next(r for r in reg if r.name == name)
    return HypothesisMatch(
        hypothesis_id=h.id, hypothesis_name=name,
        suggested_label_descriptive=f"{name} (test)",
        priority_hint=hint, candidate_ticker=ticker,
    )


def _progress(name: str, current: int, *, tripwire: bool = False,
              registry: list[HypothesisRegistryEntry] | None = None) -> HypothesisProgressSummary:
    reg = registry or _registry()
    h = next(r for r in reg if r.name == name)
    return HypothesisProgressSummary(
        hypothesis_id=h.id, hypothesis_name=name,
        current_sample=current, target_sample=h.target_sample_size,
        any_tripwire_fired=tripwire,
    )


def test_empty_matches_returns_empty():
    assert prioritize_recommendations([], registry=_registry(),
                                      progress=[]) == []


def test_single_match_returns_single_recommendation():
    reg = _registry()
    matches = [_match("A+ baseline", "ABCD", registry=reg)]
    progress = [_progress(name=h.name, current=0, registry=reg) for h in reg]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert len(out) == 1
    assert isinstance(out[0], CandidateRecommendation)
    assert out[0].candidate_ticker == "ABCD"
    assert out[0].hypothesis_name == "A+ baseline"


def test_far_from_target_outranks_close_to_target():
    """Two hypotheses, both active, no tripwires; the one further from
    its target wins. Distance metric: target - current (raw integer);
    tie-break documented in next test."""
    reg = _registry()
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "BBBB", registry=reg),
    ]
    progress = [
        # A+ baseline: 0/20 → distance 20
        _progress("A+ baseline", 0, registry=reg),
        # Sub-A+: 4/5 → distance 1
        _progress("Sub-A+ VCP-not-formed", 4, registry=reg),
        # other two not relevant but include for completeness
        _progress("Near-A+ defensible: extension test", 0, registry=reg),
        _progress("Capital-blocked: smaller-position test", 0, registry=reg),
    ]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert [r.candidate_ticker for r in out] == ["AAAA", "BBBB"]


def test_tripwire_fired_falls_to_bottom():
    reg = _registry()
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "BBBB", registry=reg),
    ]
    progress = [
        # A+ baseline: tripwire fired despite being far from target
        _progress("A+ baseline", 5, tripwire=True, registry=reg),
        # Sub-A+: clean, near target
        _progress("Sub-A+ VCP-not-formed", 4, registry=reg),
        _progress("Near-A+ defensible: extension test", 0, registry=reg),
        _progress("Capital-blocked: smaller-position test", 0, registry=reg),
    ]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    # A+ tripwire-fired → bottom
    assert [r.candidate_ticker for r in out] == ["BBBB", "AAAA"]


def test_within_same_hypothesis_priority_hint_then_ticker_alpha():
    reg = _registry()
    matches = [
        _match("A+ baseline", "ZZZZ", hint=0.10, registry=reg),
        _match("A+ baseline", "AAAA", hint=0.05, registry=reg),
        _match("A+ baseline", "BBBB", hint=0.05, registry=reg),  # same hint as AAAA
    ]
    progress = [_progress(h.name, 0, registry=reg) for h in reg]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    # Lower hint first; tied hint → alpha → AAAA before BBBB; ZZZZ last
    assert [r.candidate_ticker for r in out] == ["AAAA", "BBBB", "ZZZZ"]


def test_closed_hypothesis_drops_matches():
    """A match attached to a closed hypothesis should NOT survive
    prioritization. (Defense in depth — matcher already filters by
    status, but the prioritizer's contract should not assume that.)"""
    reg = [
        _h("A+ baseline", status="closed-target-met", target=20),
        _h("Sub-A+ VCP-not-formed", target=5),
    ]
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "BBBB", registry=reg),
    ]
    progress = [
        _progress("A+ baseline", 20, registry=reg),
        _progress("Sub-A+ VCP-not-formed", 0, registry=reg),
    ]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert [r.candidate_ticker for r in out] == ["BBBB"]


def test_paused_hypothesis_drops_matches():
    reg = [
        _h("A+ baseline", status="paused", target=20),
        _h("Sub-A+ VCP-not-formed", target=5),
    ]
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "BBBB", registry=reg),
    ]
    progress = [
        _progress("A+ baseline", 0, registry=reg),
        _progress("Sub-A+ VCP-not-formed", 0, registry=reg),
    ]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert [r.candidate_ticker for r in out] == ["BBBB"]


def test_recommendation_includes_label_and_hypothesis_id():
    reg = _registry()
    h = next(r for r in reg if r.name == "A+ baseline")
    matches = [HypothesisMatch(
        hypothesis_id=h.id, hypothesis_name=h.name,
        suggested_label_descriptive="A+ baseline (aplus); failed: ",
        priority_hint=0.01, candidate_ticker="AAAA",
    )]
    progress = [_progress(name=r.name, current=0, registry=reg) for r in reg]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert out[0].hypothesis_id == h.id
    assert "A+ baseline" in out[0].suggested_label_descriptive


def test_multi_match_candidate_dedupes_to_highest_priority_hypothesis():
    """Adversarial review R1 Major 3: brief §8 says when a candidate
    fits multiple hypotheses, the prioritizer "picks the most-
    investigation-valuable one." A+ baseline (target 20, current 0,
    distance 20) outranks Sub-A+ VCP-not-formed (target 5, current 0,
    distance 5), so the single surviving recommendation for ticker AAAA
    should be the A+ baseline match."""
    reg = _registry()
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "AAAA", registry=reg),
    ]
    progress = [_progress(name=r.name, current=0, registry=reg) for r in reg]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert len(out) == 1
    assert out[0].candidate_ticker == "AAAA"
    assert out[0].hypothesis_name == "A+ baseline"


def test_multi_match_dedup_preserves_other_tickers():
    """Per-ticker dedup keeps first (highest-priority) entry per ticker;
    other tickers are unaffected."""
    reg = _registry()
    matches = [
        _match("A+ baseline", "AAAA", registry=reg),
        _match("Sub-A+ VCP-not-formed", "AAAA", registry=reg),
        _match("A+ baseline", "BBBB", registry=reg),
    ]
    progress = [_progress(name=r.name, current=0, registry=reg) for r in reg]
    out = prioritize_recommendations(matches, registry=reg, progress=progress)
    assert len(out) == 2
    assert {r.candidate_ticker for r in out} == {"AAAA", "BBBB"}
