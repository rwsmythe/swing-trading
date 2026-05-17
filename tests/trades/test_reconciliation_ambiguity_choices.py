"""Phase 12 C.D T-D.2 — `swing/trades/reconciliation_ambiguity_choices.py`.

Helper module pure unit tests. Encodes the spec §6.2.1 LOCKED table verbatim
as a Python constant + asserts dict-vs-dict equality (tuple-of-tuples for
``ChoiceMenuItem`` shape) against the helper's ``get_choice_menu`` output
per `ambiguity_kind`.

Per plan §E.2 acceptance criteria:
  1. ``ChoiceMenuItem`` dataclass: ``code`` + ``description`` +
     ``requires_custom_value`` + ``recommended`` + (forward-prep for
     T-D.3) ``expected_payload_shape_description`` Optional[str] = None.
  2. ``get_choice_menu(ambiguity_kind)`` returns the binding menu per
     spec §6.2.1.
  3. Per OQ-4: ``keep_journal_as_is`` is ``recommended=True`` under
     ``multi_partial_vs_consolidated``.
  4. ``multi_match_within_window``: static menu has ``mark_unmatched``
     + ``custom`` only; parametric ``pick_schwab_record_<N>`` entries
     are constructed at CLI show-time (NOT in this helper).
  5. Unknown ``ambiguity_kind`` → empty list (graceful degradation).

The helper module is PURE (no DB, no I/O, no transaction management) per
CLAUDE.md "Classifier is a PURE function" precedent (Phase 12 C.B).
"""
from __future__ import annotations

from swing.trades.reconciliation_ambiguity_choices import (
    ChoiceMenuItem,
    get_choice_menu,
)


# ===========================================================================
# §1 — ChoiceMenuItem dataclass shape (forward-prep for T-D.3).
# ===========================================================================


def test_choice_menu_item_carries_expected_payload_shape_description_field() -> None:
    """T-D.3 needs ``expected_payload_shape_description`` for the
    ``--custom-value`` rejection error messages; landing the field NOW so
    T-D.3 has clean inheritance."""
    item = ChoiceMenuItem(
        code="x",
        description="y",
        requires_custom_value=True,
        recommended=False,
        expected_payload_shape_description="{'price': X.XX}",
    )
    assert item.expected_payload_shape_description == "{'price': X.XX}"


def test_choice_menu_item_expected_payload_defaults_to_none() -> None:
    """``expected_payload_shape_description`` is Optional[str] = None so
    existing call sites (T-D.2 helper construction) don't need to supply
    it; T-D.3 fills it in where applicable."""
    item = ChoiceMenuItem(
        code="x", description="y", requires_custom_value=False,
    )
    assert item.expected_payload_shape_description is None
    assert item.recommended is False


# ===========================================================================
# §2 — Per-ambiguity_kind menus encode the spec §6.2.1 table verbatim.
# ===========================================================================


def _shape(items: list[ChoiceMenuItem]) -> list[tuple]:
    """Project ChoiceMenuItem list to (code, requires_custom_value,
    recommended) tuples for dict-vs-dict equality assertions. Description
    text is asserted separately via substring matches to keep this test
    robust against minor wording reflows."""
    return [
        (it.code, it.requires_custom_value, it.recommended)
        for it in items
    ]


def test_multi_partial_vs_consolidated_menu_matches_spec() -> None:
    """Spec §6.2.1 rows: split_into_partials / consolidate_using_operator_vwap
    / keep_journal_as_is / custom. Per OQ-4: keep_journal_as_is is
    ``recommended=True``."""
    items = get_choice_menu("multi_partial_vs_consolidated")
    assert _shape(items) == [
        ("keep_journal_as_is", False, True),  # RECOMMENDED per OQ-4
        ("consolidate_using_operator_vwap", True, False),
        ("split_into_partials", True, False),
        ("custom", True, False),
    ]
    codes = {it.code for it in items}
    # All 4 spec rows present.
    assert codes == {
        "keep_journal_as_is",
        "consolidate_using_operator_vwap",
        "split_into_partials",
        "custom",
    }


def test_multi_match_within_window_menu_static_only() -> None:
    """Static menu = mark_unmatched + custom (NO ``pick_schwab_record_<N>``
    entries — those are parametric at CLI show-time from the discrepancy's
    candidate list)."""
    items = get_choice_menu("multi_match_within_window")
    assert _shape(items) == [
        ("mark_unmatched", False, False),
        ("custom", True, False),
    ]


def test_unknown_schwab_subtype_menu_matches_spec() -> None:
    """Spec §6.2.1: acknowledge / operator_truth / custom (3 choices;
    Codex R5 M#4 fix added operator_truth)."""
    items = get_choice_menu("unknown_schwab_subtype")
    assert _shape(items) == [
        ("acknowledge", False, False),
        ("operator_truth", True, False),
        ("custom", True, False),
    ]


def test_field_shape_incompatible_menu_matches_spec() -> None:
    """Spec §6.2.1: acknowledge + custom (2 choices)."""
    items = get_choice_menu("field_shape_incompatible")
    assert _shape(items) == [
        ("acknowledge", False, False),
        ("custom", True, False),
    ]


def test_schwab_returned_no_match_menu_matches_spec() -> None:
    """Spec §6.2.1: mark_unmatched + operator_truth (2 choices)."""
    items = get_choice_menu("schwab_returned_no_match")
    assert _shape(items) == [
        ("mark_unmatched", False, False),
        ("operator_truth", True, False),
    ]


def test_validator_rejected_menu_matches_spec() -> None:
    """Spec §6.2.1: acknowledge + operator_alternative (2 choices)."""
    items = get_choice_menu("validator_rejected")
    assert _shape(items) == [
        ("acknowledge", False, False),
        ("operator_alternative", True, False),
    ]


def test_unsupported_menu_matches_spec() -> None:
    """Spec §6.2.1: operator_truth + acknowledge (2 choices)."""
    items = get_choice_menu("unsupported")
    assert _shape(items) == [
        ("operator_truth", True, False),
        ("acknowledge", False, False),
    ]


# ===========================================================================
# §3 — Unknown ambiguity_kind → empty list (graceful degradation).
# ===========================================================================


def test_unknown_ambiguity_kind_returns_empty_list() -> None:
    """Caller-side defense: unknown ambiguity_kind returns empty list
    (NOT raises) so a future schema-widening that introduces a new
    ambiguity_kind value doesn't crash the show-ambiguity CLI surface
    until the helper is updated."""
    assert get_choice_menu("__nonexistent_kind__") == []
    assert get_choice_menu("") == []


# ===========================================================================
# §4 — All 7 ambiguity_kinds are covered (regression guard).
# ===========================================================================


def test_all_seven_ambiguity_kinds_have_menus() -> None:
    """Spec §6.2.1 LOCKS 7 ambiguity_kind values. Helper MUST cover all 7
    with non-empty menus."""
    expected_kinds = {
        "multi_partial_vs_consolidated",
        "multi_match_within_window",
        "unknown_schwab_subtype",
        "field_shape_incompatible",
        "schwab_returned_no_match",
        "validator_rejected",
        "unsupported",
    }
    for kind in expected_kinds:
        menu = get_choice_menu(kind)
        assert len(menu) > 0, f"empty menu for {kind!r}"


# ===========================================================================
# §5 — get_choice_menu returns a fresh list (mutation safety).
# ===========================================================================


def test_get_choice_menu_returns_fresh_list_each_call() -> None:
    """Caller mutation of the returned list MUST NOT affect subsequent
    calls. Pattern from C.B classifier helpers."""
    a = get_choice_menu("unsupported")
    a.clear()
    b = get_choice_menu("unsupported")
    assert len(b) == 2  # unaffected by caller's clear()


# ===========================================================================
# §6 — keep_journal_as_is description references partial-fill aggregation
# (OQ-4 binding).
# ===========================================================================


def test_keep_journal_as_is_description_references_partial_aggregation() -> None:
    """Description text MUST mention partial-fill aggregation or
    consolidated framing per OQ-4 RECOMMENDED rationale (operator's V1
    default is to acknowledge Schwab's partial-fill aggregation rather
    than mutate journal)."""
    items = get_choice_menu("multi_partial_vs_consolidated")
    keep = next(it for it in items if it.code == "keep_journal_as_is")
    assert keep.recommended is True
    # Substring guard — must reference partial-fill semantics.
    desc_lower = keep.description.lower()
    assert "partial" in desc_lower or "aggregat" in desc_lower
