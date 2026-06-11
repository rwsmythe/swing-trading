from __future__ import annotations

import pytest

from swing.data.models import ENTRY_INTENTS
from swing.trades.intent import (
    ENTRY_INTENT_DISPLAY,
    entry_intent_display_choices,
    entry_intent_label,
    suggest_entry_intent,
)


def test_display_matches_constant_no_drift():
    assert {v for v, _ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS


def test_display_choices_is_the_ordered_tuple():
    assert entry_intent_display_choices() == ENTRY_INTENT_DISPLAY
    assert ENTRY_INTENT_DISPLAY[0][0] == "standard"


def test_label_maps_and_passes_through():
    assert entry_intent_label("standard") == "Standard entry"
    assert entry_intent_label("hypothesis_test_by_design") == "Hypothesis test (by design)"
    assert entry_intent_label(None) is None
    assert entry_intent_label("weird") == "weird"   # unknown -> itself


@pytest.mark.parametrize("label,expected", [
    # standard family (spec §5.1)
    ("A+ baseline (aplus)", "standard"),
    ("aplus", "standard"),
    ("Capital-blocked: smaller-position test", "standard"),
    ("Broad-watch baseline (watch); failed: adr", "standard"),
    # by-design family
    ("Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness",
     "hypothesis_test_by_design"),
    ("Near-A+ defensible: extension test (watch); failed: proximity_20ma",
     "hypothesis_test_by_design"),
    # Real live labels (data-shape discipline): the DHC + SKYT by-design rows.
    ("sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)",
     "hypothesis_test_by_design"),
    ("Sub-A+ VCP-not-formed (watch); failed: TT8_rs_rank, proximity_20ma, "
     "tightness", "hypothesis_test_by_design"),
    # no confident suggestion (spec §1 note + §5.1 last row)
    ("inaugural trade test", None),     # VIR id 1
    (None, None),                       # VSAT / PTEN NULL labels
    ("", None),
    ("   ", None),
    ("totally unknown manual label", None),
])
def test_suggest_entry_intent_table(label, expected):
    assert suggest_entry_intent(label) == expected


def test_suggest_is_case_insensitive():
    assert suggest_entry_intent("APLUS BASELINE") == "standard"
    assert suggest_entry_intent("SUB-A+ vcp-not-formed") == "hypothesis_test_by_design"
