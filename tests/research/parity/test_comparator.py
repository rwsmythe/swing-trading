"""Tests for the harness-vs-production comparison primitive.

Covers the disagreement permutations enumerated in
``docs/harness-vs-production-parity-brief.md`` §5.2:
- Identical bucket and criteria → bucket_match True, no disagreements.
- One criterion differs → exactly one disagreement.
- Bucket differs but criteria identical → bucket_match False, no
  per-criterion disagreements.
- Ticker absent on one side → bucket=None on that side.
- Mismatched-presence (criterion present one side, absent the other) →
  counted as disagreement per D1 pre-registration §"Comparison primitive."
"""
from __future__ import annotations

from research.parity.comparator import (
    CriterionDisagreement,
    ParitySummary,
    TickerParity,
    compare,
    summarize,
)
from swing.data.models import Candidate, CriterionResult


def _crit(name: str, result: str, *, layer: str = "trend_template",
          value: str | None = None) -> CriterionResult:
    return CriterionResult(criterion_name=name, layer=layer, result=result, value=value)


def _candidate(ticker: str, *, bucket: str,
               criteria: tuple[CriterionResult, ...]) -> Candidate:
    return Candidate(
        ticker=ticker, bucket=bucket, close=None, pivot=None, initial_stop=None,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
        pattern_tag=None, notes=None, criteria=criteria,
    )


def test_identical_bucket_and_criteria_match():
    crits = (_crit("TT1", "pass"), _crit("risk_feasibility", "pass", layer="risk"))
    prod = _candidate("AAPL", bucket="watch", criteria=crits)
    harness = _candidate("AAPL", bucket="watch", criteria=crits)

    p = compare(prod, harness)

    assert p.ticker == "AAPL"
    assert p.bucket_match is True
    assert p.criterion_disagreements == ()
    assert p.criterion_total_compared == 2
    assert p.criterion_match_count == 2
    assert p.prod_bucket == "watch"
    assert p.harness_bucket == "watch"


def test_one_criterion_differs_records_one_disagreement():
    prod = _candidate("AAPL", bucket="skip", criteria=(
        _crit("TT1", "pass"),
        _crit("TT2", "fail", value="below"),
        _crit("risk_feasibility", "pass", layer="risk"),
    ))
    harness = _candidate("AAPL", bucket="skip", criteria=(
        _crit("TT1", "pass"),
        _crit("TT2", "pass", value="above"),
        _crit("risk_feasibility", "pass", layer="risk"),
    ))

    p = compare(prod, harness)

    assert p.bucket_match is True
    assert len(p.criterion_disagreements) == 1
    d = p.criterion_disagreements[0]
    assert d.criterion_name == "TT2"
    assert d.prod_result == "fail"
    assert d.harness_result == "pass"
    assert d.prod_value == "below"
    assert d.harness_value == "above"
    assert p.criterion_total_compared == 3
    assert p.criterion_match_count == 2


def test_bucket_differs_but_criteria_identical():
    crits = (_crit("TT1", "pass"), _crit("risk_feasibility", "pass", layer="risk"))
    prod = _candidate("AAPL", bucket="watch", criteria=crits)
    harness = _candidate("AAPL", bucket="skip", criteria=crits)

    p = compare(prod, harness)

    assert p.bucket_match is False
    assert p.prod_bucket == "watch"
    assert p.harness_bucket == "skip"
    assert p.criterion_disagreements == ()
    assert p.criterion_match_count == p.criterion_total_compared == 2


def test_ticker_absent_on_harness_side():
    prod = _candidate("AAPL", bucket="watch", criteria=(_crit("TT1", "pass"),))

    p = compare(prod, None)

    assert p.ticker == "AAPL"
    assert p.prod_bucket == "watch"
    assert p.harness_bucket is None
    assert p.bucket_match is False
    assert p.criterion_total_compared == 1
    assert p.criterion_match_count == 0
    assert len(p.criterion_disagreements) == 1
    d = p.criterion_disagreements[0]
    assert d.criterion_name == "TT1"
    assert d.prod_result == "pass"
    assert d.harness_result is None


def test_ticker_absent_on_production_side():
    harness = _candidate("AAPL", bucket="skip", criteria=(_crit("TT1", "pass"),))

    p = compare(None, harness)

    assert p.ticker == "AAPL"
    assert p.prod_bucket is None
    assert p.harness_bucket == "skip"
    assert p.bucket_match is False
    assert p.criterion_total_compared == 1
    assert p.criterion_match_count == 0
    assert len(p.criterion_disagreements) == 1
    d = p.criterion_disagreements[0]
    assert d.prod_result is None
    assert d.harness_result == "pass"


def test_mismatched_criterion_presence_counts_as_disagreement():
    prod = _candidate("AAPL", bucket="watch", criteria=(
        _crit("TT1", "pass"),
        _crit("TT2", "fail"),  # present on prod only
    ))
    harness = _candidate("AAPL", bucket="watch", criteria=(
        _crit("TT1", "pass"),
        _crit("TT3", "pass"),  # present on harness only
    ))

    p = compare(prod, harness)

    # Three criteria in the union: TT1 (matches), TT2 (prod only), TT3 (harness only).
    assert p.criterion_total_compared == 3
    assert p.criterion_match_count == 1
    assert len(p.criterion_disagreements) == 2
    by_name = {d.criterion_name: d for d in p.criterion_disagreements}
    assert by_name["TT2"].prod_result == "fail"
    assert by_name["TT2"].harness_result is None
    assert by_name["TT3"].prod_result is None
    assert by_name["TT3"].harness_result == "pass"


def test_compare_with_both_none_raises():
    import pytest
    with pytest.raises(ValueError):
        compare(None, None)


def test_summarize_tier_1_perfect_agreement():
    crits = (_crit("TT1", "pass"), _crit("TT2", "pass"))
    parities = [
        compare(_candidate(t, bucket="watch", criteria=crits),
                _candidate(t, bucket="watch", criteria=crits))
        for t in ("A", "B", "C")
    ]
    s = summarize(parities)
    assert isinstance(s, ParitySummary)
    assert s.bucket_total == 3
    assert s.bucket_matches == 3
    assert s.criterion_total == 6
    assert s.criterion_matches == 6
    assert s.tier == 1
    assert s.bucket_agreement_rate == 1.0
    assert s.criterion_agreement_rate == 1.0


def test_summarize_tier_2_minor_drift():
    """1 of 100 buckets disagrees → 99% agreement is the boundary; 98% is Tier 2."""
    crits = (_crit("TT1", "pass"),)
    parities = [
        compare(_candidate(f"T{i}", bucket="watch", criteria=crits),
                _candidate(f"T{i}", bucket="skip" if i < 2 else "watch", criteria=crits))
        for i in range(100)
    ]
    s = summarize(parities)
    assert s.bucket_matches == 98
    assert s.bucket_total == 100
    # Per-criterion agreement is 100/100 (criteria all match), so the worse
    # of the two governs: bucket = 98% → 95 ≤ x < 99 → Tier 2.
    assert s.criterion_matches == 100
    assert s.tier == 2


def test_summarize_tier_3_drift_dominant():
    crits_prod = (_crit("TT1", "pass"),)
    crits_harness_diff = (_crit("TT1", "fail"),)
    parities = [
        compare(_candidate(f"T{i}", bucket="watch", criteria=crits_prod),
                _candidate(f"T{i}", bucket="watch",
                           criteria=crits_harness_diff if i < 10 else crits_prod))
        for i in range(100)
    ]
    s = summarize(parities)
    assert s.criterion_matches == 90
    assert s.tier == 3


def test_summarize_anti_rationalization_boundary_at_99_is_tier_1():
    """Bucket+criterion agreement ≥99% qualifies for Tier 1 by D1's frozen
    threshold. A 99/100 ratio is exactly 0.99 — Tier 1, not Tier 2."""
    crits = (_crit("TT1", "pass"),)
    parities = [
        compare(_candidate(f"T{i}", bucket="watch", criteria=crits),
                _candidate(f"T{i}", bucket="skip" if i < 1 else "watch", criteria=crits))
        for i in range(100)
    ]
    s = summarize(parities)
    assert s.bucket_matches == 99
    assert s.bucket_total == 100
    assert s.tier == 1


def test_summarize_anti_rationalization_boundary_at_95_is_tier_2():
    """95/100 is Tier 2 (≥95% but <99%); 94/100 falls to Tier 3."""
    crits = (_crit("TT1", "pass"),)
    parities = [
        compare(_candidate(f"T{i}", bucket="watch", criteria=crits),
                _candidate(f"T{i}", bucket="skip" if i < 5 else "watch", criteria=crits))
        for i in range(100)
    ]
    s = summarize(parities)
    assert s.bucket_matches == 95
    assert s.tier == 2

    parities_94 = [
        compare(_candidate(f"T{i}", bucket="watch", criteria=crits),
                _candidate(f"T{i}", bucket="skip" if i < 6 else "watch", criteria=crits))
        for i in range(100)
    ]
    s_94 = summarize(parities_94)
    assert s_94.bucket_matches == 94
    assert s_94.tier == 3


def test_summarize_empty_input_raises():
    import pytest
    with pytest.raises(ValueError):
        summarize([])


def test_disagreement_dataclass_is_frozen():
    import pytest
    d = CriterionDisagreement(
        criterion_name="TT1", prod_result="pass", harness_result="fail",
        prod_value=None, harness_value=None,
    )
    with pytest.raises((AttributeError, Exception)):
        d.criterion_name = "TT2"  # type: ignore[misc]


def test_ticker_parity_dataclass_is_frozen():
    import pytest
    p = TickerParity(
        ticker="AAPL", prod_bucket="watch", harness_bucket="watch",
        bucket_match=True, criterion_disagreements=(),
        criterion_total_compared=0, criterion_match_count=0,
    )
    with pytest.raises((AttributeError, Exception)):
        p.bucket_match = False  # type: ignore[misc]
