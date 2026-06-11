"""Tuition-vs-error instrument: entry_intent presentation + advisory prefill.

PURE (no I/O). The schema-CHECK enum ENTRY_INTENTS lives in swing.data.models
(the schema-enum home, to avoid an upward import); this module owns the
display/advisory helpers. The no-drift test asserts ENTRY_INTENT_DISPLAY's
values equal ENTRY_INTENTS. NEVER consulted by the service/persist layer for
the stored value -- suggest_entry_intent only seeds the visible form control's
default (spec §5: THE SINGLE PREFILL RULE).
"""
from __future__ import annotations

# Ordered (value, label) for the form <select> + display (mirrors
# review.FAILURE_MODE_DISPLAY). ASCII-only labels (#16 cp1252 stdout + parity).
# A frozenset has NO iteration-order guarantee -- forms/labels iterate THIS
# tuple, never ENTRY_INTENTS directly. The no-drift test asserts
# {v for v,_ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS.
ENTRY_INTENT_DISPLAY: tuple[tuple[str, str], ...] = (
    ("standard", "Standard entry"),
    ("hypothesis_test_by_design", "Hypothesis test (by design)"),
)

_ENTRY_INTENT_LABELS: dict[str, str] = dict(ENTRY_INTENT_DISPLAY)


def entry_intent_display_choices() -> tuple[tuple[str, str], ...]:
    """Ordered (value, label) pairs for the form <select> + VM."""
    return ENTRY_INTENT_DISPLAY


def entry_intent_label(value: str | None) -> str | None:
    """Map a stored token to its display label; None -> None; unknown -> itself."""
    if value is None:
        return None
    return _ENTRY_INTENT_LABELS.get(value, value)


def suggest_entry_intent(hypothesis_label: str | None) -> str | None:
    """Advisory default ONLY (spec §5) -- seeds the visible form control; never
    read by the service/persist layer and never consults the matcher/registry.

    Keyword match on the lowercased label (spec §5.1). Order matters: the
    'standard' families are tested before the by-design families so an explicit
    A+/capital-blocked/broad-watch label never falls through to a by-design
    keyword. No keyword match (manual / 'inaugural trade test' / NULL) -> None.
    """
    if hypothesis_label is None:
        return None
    text = hypothesis_label.strip().lower()
    if not text:
        return None
    standard_keywords = ("a+ baseline", "aplus", "capital-blocked", "broad-watch baseline")
    if any(kw in text for kw in standard_keywords):
        return "standard"
    by_design_keywords = ("sub-a+", "vcp-not-formed", "near-a+", "extension test")
    if any(kw in text for kw in by_design_keywords):
        return "hypothesis_test_by_design"
    return None
