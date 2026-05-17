"""Phase 12 Sub-bundle C.D T-D.2 — per-(ambiguity_kind) choice-menu helper.

PURE module (no DB, no I/O, no transaction management) per CLAUDE.md
"Classifier is a PURE function" precedent (Phase 12 C.B). Returns the
spec §6.2.1 LOCKED choice menus consumed by:

* ``swing journal discrepancy show-ambiguity`` (T-D.2): renders the menu
  + per-row REQUIRES/RECOMMENDED markers.
* ``swing journal discrepancy resolve-ambiguity`` (T-D.3 — follow-up):
  validates the operator's ``--choice <code>`` against this menu +
  enforces the per-choice ``--custom-value`` requirement; the
  ``expected_payload_shape_description`` field will be threaded into
  T-D.3's rejection error messages.

For ``multi_match_within_window``, the menu surfaced here is STATIC
(``mark_unmatched`` + ``custom``); the parametric
``pick_schwab_record_<N>`` entries are constructed at CLI show-time from
the discrepancy's candidate list (V1 LOCK: source = best-effort parse
of ``resolution_reason`` text; no dedicated ``candidate_choices_json``
column — banked V2 candidate §I.13).

Per OQ-4: ``keep_journal_as_is`` is ``recommended=True`` for
``multi_partial_vs_consolidated`` (operator's V1 default — acknowledge
Schwab's partial-fill aggregation rather than mutate journal).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChoiceMenuItem:
    """One row in the per-ambiguity_kind menu surfaced to the operator.

    Attributes
    ----------
    code:
        The ``--choice <code>`` token the operator passes to
        ``resolve-ambiguity``. Matches the spec §6.2.1 Choice code column
        verbatim.
    description:
        Operator-facing one-line description rendered next to the code.
    requires_custom_value:
        When ``True``, the choice cannot be applied without an operator-
        supplied ``--custom-value '<json>'`` payload (per the spec §6.2.1
        Description column's "REQUIRES `--custom-value`" markers; Codex
        R5 Major #2 LOCK).
    recommended:
        When ``True``, the CLI prefixes the row with ``[RECOMMENDED]``
        and surfaces the choice first in the printed menu. Per spec
        OQ-4: only ``keep_journal_as_is`` under
        ``multi_partial_vs_consolidated`` carries this V1.
    expected_payload_shape_description:
        Forward-prep for T-D.3 (``resolve-ambiguity`` CLI rejection
        error messages on ``--custom-value`` mismatch). Optional; T-D.2
        does not consume it. Example values: ``'{"price": X.XX}'`` for
        ``consolidate_using_operator_vwap``; the partial-fill payload
        shape for ``split_into_partials``.
    """

    code: str
    description: str
    requires_custom_value: bool
    recommended: bool = False
    expected_payload_shape_description: str | None = None


_PARTIAL_PAYLOAD_SHAPE = (
    '[{"qty": Q1, "price": P1, "fill_datetime": "..."}, ...]'
)
_PRICE_SCALAR_SHAPE = '{"price": X.XX}'
_OPERATOR_TRUTH_SHAPE = (
    '{"price": X.XX, "quantity": Q, "trade_date": "YYYY-MM-DD", ...}'
)
_CUSTOM_AUDIT_SHAPE = (
    '{"audit_only": true, "operator_intent": "<free-text>"}'
)


_AMBIGUITY_CHOICE_MENUS: dict[str, list[ChoiceMenuItem]] = {
    # Spec §6.2.1: 4 choices. keep_journal_as_is RECOMMENDED per OQ-4.
    "multi_partial_vs_consolidated": [
        ChoiceMenuItem(
            code="keep_journal_as_is",
            description=(
                "Acknowledge Schwab partial-fill aggregation; no "
                "journal mutation."
            ),
            requires_custom_value=False,
            recommended=True,
        ),
        ChoiceMenuItem(
            code="consolidate_using_operator_vwap",
            description=(
                "Keep journal consolidated; update price to operator-"
                "supplied VWAP (computed from broker execution "
                "statement)."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_PRICE_SCALAR_SHAPE,
        ),
        ChoiceMenuItem(
            code="split_into_partials",
            description=(
                "Replace journal consolidated fill with N partial "
                "fills from operator-supplied execution payload."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_PARTIAL_PAYLOAD_SHAPE,
        ),
        ChoiceMenuItem(
            code="custom",
            description=(
                "Operator-supplied arbitrary structured payload; "
                "service applies as multi-column correction."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_CUSTOM_AUDIT_SHAPE,
        ),
    ],
    # Spec §6.2.1: static menu = mark_unmatched + custom. Parametric
    # pick_schwab_record_<N> entries are constructed at CLI show-time
    # from the discrepancy's candidate list (NOT here).
    "multi_match_within_window": [
        ChoiceMenuItem(
            code="mark_unmatched",
            description=(
                "Journal entry has no corresponding broker record; no "
                "journal mutation."
            ),
            requires_custom_value=False,
        ),
        ChoiceMenuItem(
            code="custom",
            description=(
                "Operator-supplied arbitrary payload via --custom-value."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_CUSTOM_AUDIT_SHAPE,
        ),
    ],
    # Spec §6.2.1: 3 choices (Codex R5 M#4 fix added operator_truth).
    "unknown_schwab_subtype": [
        ChoiceMenuItem(
            code="acknowledge",
            description=(
                "Acknowledge + log the unrecognized Schwab subtype for "
                "V2 code update; no journal mutation."
            ),
            requires_custom_value=False,
        ),
        ChoiceMenuItem(
            code="operator_truth",
            description=(
                "Operator supplies the real journal field values "
                "(e.g., single-order-multi-execution V1-mapper case)."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_OPERATOR_TRUTH_SHAPE,
        ),
        ChoiceMenuItem(
            code="custom",
            description=(
                "Operator-supplied arbitrary structured payload."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_CUSTOM_AUDIT_SHAPE,
        ),
    ],
    # Spec §6.2.1: 2 choices.
    "field_shape_incompatible": [
        ChoiceMenuItem(
            code="acknowledge",
            description=(
                "Acknowledge the field-shape mismatch; no journal "
                "mutation."
            ),
            requires_custom_value=False,
        ),
        ChoiceMenuItem(
            code="custom",
            description=(
                "Operator-supplied arbitrary structured payload."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_CUSTOM_AUDIT_SHAPE,
        ),
    ],
    # Spec §6.2.1: 2 choices. Per Codex R9 Minor #1 cleanup:
    # acknowledged_immaterial is NOT reachable from this kind.
    "schwab_returned_no_match": [
        ChoiceMenuItem(
            code="mark_unmatched",
            description=(
                "Schwab has no record; journal stays as-is (e.g., "
                "non-Schwab-routed broker fill); no journal mutation."
            ),
            requires_custom_value=False,
        ),
        ChoiceMenuItem(
            code="operator_truth",
            description=(
                "Operator supplies the real values from off-Schwab "
                "broker source."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_OPERATOR_TRUTH_SHAPE,
        ),
    ],
    # Spec §6.2.1: 2 choices.
    "validator_rejected": [
        ChoiceMenuItem(
            code="acknowledge",
            description=(
                "Correction would violate invariants; leave divergence "
                "as-is; no journal mutation."
            ),
            requires_custom_value=False,
        ),
        ChoiceMenuItem(
            code="operator_alternative",
            description=(
                "Operator supplies alternative value that passes the "
                "validator chain; service re-runs validators on "
                "operator-supplied value."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_OPERATOR_TRUTH_SHAPE,
        ),
    ],
    # Spec §6.2.1: 2 choices. Classifier emitted this when shape was
    # not recognized (graceful degradation per §4.5).
    "unsupported": [
        ChoiceMenuItem(
            code="operator_truth",
            description=(
                "Operator-custom resolution; supplies the real values."
            ),
            requires_custom_value=True,
            expected_payload_shape_description=_OPERATOR_TRUTH_SHAPE,
        ),
        ChoiceMenuItem(
            code="acknowledge",
            description=(
                "Leave journal as-is; classifier did not recognize "
                "the shape; no journal mutation."
            ),
            requires_custom_value=False,
        ),
    ],
}


def get_choice_menu(ambiguity_kind: str) -> list[ChoiceMenuItem]:
    """Return the per-``ambiguity_kind`` choice menu per spec §6.2.1.

    Each call returns a FRESH list (mutation safety for callers).
    Unknown ``ambiguity_kind`` → empty list (graceful degradation; a
    future schema-widening that introduces a new ambiguity_kind value
    will not crash the ``show-ambiguity`` CLI surface).

    For ``multi_match_within_window`` the returned menu is STATIC
    (``mark_unmatched`` + ``custom``); CLI show-time constructs the
    parametric ``pick_schwab_record_<N>`` entries dynamically from the
    discrepancy's candidate list (V1 source: ``resolution_reason`` text;
    no dedicated ``candidate_choices_json`` column per §I.13 V2).
    """
    return list(_AMBIGUITY_CHOICE_MENUS.get(ambiguity_kind, []))
