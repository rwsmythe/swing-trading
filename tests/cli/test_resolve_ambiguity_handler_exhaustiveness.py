"""T-D.5 — Exhaustive handler-registry vs menu vs spec §6.2.1 regression test.

Canonical "no silent kind/choice drift" regression: pins the binding contract
that every spec §6.2.1 (ambiguity_kind, choice_code) entry has BOTH a menu
entry in ``swing.trades.reconciliation_ambiguity_choices._AMBIGUITY_CHOICE_MENUS``
AND a handler entry in ``swing.trades.reconciliation_auto_correct._TIER2_HANDLERS``.

Spec §6.2.1 totals: **17 exact-key + 1 parametric prefix = 18 binding contract entries**.
Parametric prefix ``pick_schwab_record_<N>`` lives under the
``multi_match_within_window`` kind and is registered as a single key
``(ambiguity_kind, _PICK_SCHWAB_RECORD_PREFIX)`` in the handler registry.
"""

from __future__ import annotations

from swing.trades.reconciliation_ambiguity_choices import (
    _AMBIGUITY_CHOICE_MENUS,
)
from swing.trades.reconciliation_auto_correct import (
    _PICK_SCHWAB_RECORD_PREFIX,
    _TIER2_HANDLERS,
)

# Spec §6.2.1 binding-contract: 17 exact-key (ambiguity_kind, choice_code) pairs.
EXPECTED_EXACT_KEY_PAIRS: set[tuple[str, str]] = {
    # multi_partial_vs_consolidated — 4 choices
    ("multi_partial_vs_consolidated", "keep_journal_as_is"),
    ("multi_partial_vs_consolidated", "consolidate_using_operator_vwap"),
    ("multi_partial_vs_consolidated", "split_into_partials"),
    ("multi_partial_vs_consolidated", "custom"),
    # multi_match_within_window — 2 static choices (parametric prefix tracked separately)
    ("multi_match_within_window", "mark_unmatched"),
    ("multi_match_within_window", "custom"),
    # unknown_schwab_subtype — 3 choices
    ("unknown_schwab_subtype", "acknowledge"),
    ("unknown_schwab_subtype", "operator_truth"),
    ("unknown_schwab_subtype", "custom"),
    # field_shape_incompatible — 2 choices
    ("field_shape_incompatible", "acknowledge"),
    ("field_shape_incompatible", "custom"),
    # schwab_returned_no_match — 2 choices
    ("schwab_returned_no_match", "mark_unmatched"),
    ("schwab_returned_no_match", "operator_truth"),
    # validator_rejected — 2 choices
    ("validator_rejected", "acknowledge"),
    ("validator_rejected", "operator_alternative"),
    # unsupported — 2 choices
    ("unsupported", "operator_truth"),
    ("unsupported", "acknowledge"),
}

# Spec §6.2.1 binding-contract: 1 parametric-prefix entry.
EXPECTED_PARAMETRIC_PAIRS: set[tuple[str, str]] = {
    ("multi_match_within_window", _PICK_SCHWAB_RECORD_PREFIX),
}


def test_menu_matches_spec_6_2_1_exact_keys() -> None:
    """Every spec §6.2.1 exact-key entry appears in the static menu helper."""
    actual = {
        (kind, item.code)
        for kind, items in _AMBIGUITY_CHOICE_MENUS.items()
        for item in items
    }
    assert actual == EXPECTED_EXACT_KEY_PAIRS, (
        "drift between spec §6.2.1 EXPECTED_EXACT_KEY_PAIRS and "
        "_AMBIGUITY_CHOICE_MENUS contents: "
        f"missing-from-menu={EXPECTED_EXACT_KEY_PAIRS - actual}; "
        f"orphan-in-menu={actual - EXPECTED_EXACT_KEY_PAIRS}"
    )


def test_handler_registry_matches_spec_6_2_1() -> None:
    """Every spec §6.2.1 entry (exact + parametric prefix) is registered in _TIER2_HANDLERS."""
    expected = EXPECTED_EXACT_KEY_PAIRS | EXPECTED_PARAMETRIC_PAIRS
    actual = set(_TIER2_HANDLERS.keys())
    assert actual == expected, (
        "drift between spec §6.2.1 binding contract and _TIER2_HANDLERS keys: "
        f"missing-from-registry={expected - actual}; "
        f"orphan-in-registry={actual - expected}"
    )


def test_total_binding_contract_entries_is_18() -> None:
    """17 exact-key + 1 parametric prefix = 18 binding contract entries."""
    assert len(EXPECTED_EXACT_KEY_PAIRS) == 17
    assert len(EXPECTED_PARAMETRIC_PAIRS) == 1
    assert len(_TIER2_HANDLERS) == 18


def test_no_orphan_menu_entries() -> None:
    """Every static menu entry has a corresponding (kind, code) handler."""
    for kind, items in _AMBIGUITY_CHOICE_MENUS.items():
        for item in items:
            assert (kind, item.code) in _TIER2_HANDLERS, (
                f"menu entry ({kind!r}, {item.code!r}) has no handler "
                "in _TIER2_HANDLERS"
            )


def test_no_orphan_handler_entries() -> None:
    """Every handler entry has a corresponding menu kind (parametric prefix special-cased)."""
    for (kind, code) in _TIER2_HANDLERS:
        if code == _PICK_SCHWAB_RECORD_PREFIX:
            # Parametric — verify the kind exists in the static menu mapping.
            assert kind in _AMBIGUITY_CHOICE_MENUS, (
                f"parametric handler ({kind!r}, {code!r}) has no menu kind "
                "in _AMBIGUITY_CHOICE_MENUS"
            )
        else:
            # Exact-key — verify (kind, code) appears in the static menu items.
            assert kind in _AMBIGUITY_CHOICE_MENUS, (
                f"handler ({kind!r}, {code!r}) has no menu kind "
                "in _AMBIGUITY_CHOICE_MENUS"
            )
            menu_codes = {item.code for item in _AMBIGUITY_CHOICE_MENUS[kind]}
            assert code in menu_codes, (
                f"handler ({kind!r}, {code!r}) has no menu entry "
                f"(menu codes for {kind!r}: {sorted(menu_codes)})"
            )
