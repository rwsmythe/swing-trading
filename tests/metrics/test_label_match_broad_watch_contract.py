"""Guard test: label_matches_hypothesis 3-rule contract for Broad-watch baseline.

The broad-watch label produced by _descriptive_label starts with
"Broad-watch baseline" and must match the BROAD hypothesis name only,
never any of the four narrow names.
"""
from __future__ import annotations

import pytest

from swing.metrics.label_match import label_matches_hypothesis

BROAD = "Broad-watch baseline"
NARROW_NAMES = [
    "A+ baseline",
    "Near-A+ defensible: extension test",
    "Sub-A+ VCP-not-formed",
    "Capital-blocked: smaller-position test",
]


def test_descriptive_label_matches_broad_watch():
    assert label_matches_hypothesis("Broad-watch baseline (watch); failed: tightness", BROAD) is True


@pytest.mark.parametrize("name", NARROW_NAMES)
def test_descriptive_label_does_not_match_narrow(name):
    assert label_matches_hypothesis("Broad-watch baseline (watch); failed: tightness", name) is False
    assert label_matches_hypothesis(f"{name} (watch); failed: x", BROAD) is False
