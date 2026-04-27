"""Parametrized integration test for chart-pattern flag-v1 (Task 7.2).

Per spec §4.2, runs ``classify_flag`` against operator-labeled fixtures and
asserts label match + optional confidence floor. Empty fixture directory
SKIPS gracefully (Task 7.3 hasn't shipped yet); doesn't fail the suite.
"""
from __future__ import annotations

import pytest

from swing.config import ClassifierConfig
from swing.evaluation.patterns.flag_classifier import classify_flag
from tests.evaluation.patterns._fixtures import (
    LabeledFixture,
    load_labeled_fixtures,
)

_FIXTURES = load_labeled_fixtures()


@pytest.mark.skipif(
    not _FIXTURES,
    reason="No labeled fixtures committed yet (Task 7.3 operator-only)",
)
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
def test_classify_flag_matches_labeled_fixture(fixture: LabeledFixture) -> None:
    """Operator-labeled fixture: classify_flag(bars) should match label."""
    cfg = ClassifierConfig()
    result = classify_flag(fixture.bars, cfg=cfg)

    if fixture.label == "flag":
        assert result.pattern == "flag", (
            f"Fixture {fixture.name} labeled 'flag' but classifier returned "
            f"pattern={result.pattern!r}. Notes: {fixture.notes}"
        )
        if fixture.expected_confidence_min is not None:
            assert result.confidence >= fixture.expected_confidence_min, (
                f"Fixture {fixture.name} labeled 'flag' but classifier "
                f"confidence {result.confidence:.3f} < expected_min "
                f"{fixture.expected_confidence_min:.3f}."
            )
    elif fixture.label == "none":
        assert result.pattern in ("none", None), (
            f"Fixture {fixture.name} labeled 'none' but classifier returned "
            f"pattern={result.pattern!r}. Notes: {fixture.notes}"
        )
    else:
        pytest.fail(f"Unknown label {fixture.label!r} on fixture {fixture.name}")
