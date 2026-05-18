"""View-model module for the web Tier-2 discrepancy-resolution surface
(Phase 12.5 #2).

This module hosts the helpers, dataclasses, and builder for
`GET /reconcile/discrepancy/{id}/resolve` and the POST companion route.
T-2.1 ships only the `_parse_parametric_pick_count` pure helper; subsequent
tasks (T-2.2..T-2.10) extend this module with the VM dataclasses, error VM,
and the builder function.

Spec references (BINDING):

- spec §5.4 ``Parametric pick_schwab_record_<N> entries derived from
  resolution_reason text — the classifier emits ``Schwab returned <N>
  orders within the match window`` in `reconciliation_discrepancies.
  resolution_reason`; the web VM parses N and synthesizes N parametric
  ChoiceMenuItem entries in the menu (mirrors the CLI behavior at
  `swing/cli.py` near line 2291).

- spec §16.7 LOCK ``_parse_parametric_pick_count helper duplicated
  private in web VM (CLI refactor V2-deferred)`` — accepted at brainstorm
  defaults 2026-05-18 (Phase 12.5 #2 brainstorm return report §16.7).

- spec §15.13 V2 candidate ``DRY consolidation of the
  _parse_parametric_pick_count helper between the CLI surface
  (`swing/cli.py:~2291`) and this module``. V1 ships the duplicate verbatim
  rather than coupling the modules; refactor deferred to a follow-up
  dispatch.

The regex pattern below is BYTE-FOR-BYTE identical to the CLI's compiled
pattern at `swing/cli.py` line 2291-2294 per LOCK §1.2 #11 of the
executing-plans plan; behavioral parity is pinned by the test at
`tests/web/test_reconcile_parametric_pick_count.py:
test_parse_parametric_pick_count_byte_identical_to_cli_parser`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from swing.data.models import ReconciliationDiscrepancy


def _parse_parametric_pick_count(resolution_reason: str | None) -> int:
    """Parse the parametric pick-record count N from a discrepancy
    `resolution_reason`.

    The classifier (`swing/trades/reconciliation_classifier.py`) emits a
    substring of the form ``Schwab returned <N> orders within the match
    window`` inside the resolution_reason for `multi_match_within_window`
    ambiguity-kind discrepancies. This helper extracts N so the web Tier-2
    builder can synthesize N parametric `pick_schwab_record_<i>` choice
    entries (1-indexed) — mirroring the CLI behavior at
    `swing/cli.py:~2291`.

    Returns 0 when:
      - input is None
      - input is the empty string
      - the regex does not match (no "Schwab returned ... within the match
        window" substring)
      - the regex matches with N=0 (no parametric entries to build)

    The function is PURE — no DB access, no I/O, no logging, no
    side-effects. Mirrors the project's "Classifier is a PURE function"
    discipline applied to a parser helper.
    """
    text = resolution_reason or ""
    m = re.search(
        r"Schwab returned\s+(\d+)\s+orders within the match window",
        text,
    )
    if not m:
        return 0
    return int(m.group(1))


# ---------------------------------------------------------------------------
# Phase 12.5 #2 T-2.2 — VM dataclasses + per-discrepancy-type render helpers.
#
# Three frozen dataclasses (ReconcilePreResolutionContext,
# ReconcileChoiceFormItem, ReconcileDiscrepancyResolveVM) per spec §5.1 / §5.2
# / §5.3 + 10 private per-discrepancy-type render helpers per spec §7.1 + a
# dispatch function with graceful-degradation generic fallback.
#
# F1 LOCK: ZERO new schema. F11 LOCK: ReconcileDiscrepancyResolveVM carries
# 8 standalone BaseLayoutVM-shaped fields (does NOT inherit BaseLayoutVM —
# matches SchwabSetupVM precedent at swing/web/view_models/schwab.py).
#
# Plan vs spec field-count drift: plan §A T-2.2 acceptance says
# ``ReconcilePreResolutionContext`` has "14 fields"; the spec §5.2 table
# actually lists 15 fields (the final ``parse_warning`` row is excluded from
# the plan's count). Implementation includes all 15 — every field listed in
# the spec table. Banked at return-report time as a benign drift; no V2.1
# §VII.F amendment required because the implementation matches the spec
# table verbatim.
# ---------------------------------------------------------------------------


_GENERIC_TRUNCATE_LEN = 80


@dataclass(frozen=True)
class ReconcilePreResolutionContext:
    """Per-discrepancy contextual data rendered ABOVE the choice menu on
    ``GET /reconcile/discrepancy/{id}/resolve`` (spec §5.2).

    Fields are pure rendering primitives — labels + already-formatted string
    values. The dispatch function ``_render_pre_resolution_context`` builds
    instances by parsing the discrepancy's persisted JSON envelopes; per-type
    helpers consume the parsed dicts and emit type-specific label/value
    triples per spec §7.1.

    The 15th field ``parse_warning`` is None on the happy path; non-None
    indicates the generic fallback fired (unknown discrepancy_type, malformed
    JSON, or per-type helper raised KeyError).
    """

    discrepancy_type: str
    ambiguity_kind: str
    ticker: str
    field_name: str
    journal_side_label: str
    journal_side_value: str
    schwab_side_label: str
    schwab_side_value: str
    delta_label: str
    delta_value: str
    classifier_resolution_reason: str
    material: bool
    created_at: str
    run_id: int
    parse_warning: str | None = None


@dataclass(frozen=True)
class ReconcileChoiceFormItem:
    """One choice row in the operator-resolution menu (spec §5.3).

    Each choice corresponds to a ``(ambiguity_kind, choice_code)`` entry in
    the auto-correction service's handler registry. ``requires_custom_value``
    is per-choice not suffix-based (CLAUDE.md gotcha); the template uses it
    to gate visibility of the custom-value input row.

    ``is_parametric_pick`` is True for ``pick_schwab_record_<N>`` codes
    (synthesized from ``_parse_parametric_pick_count(resolution_reason)``)
    and False for static codes.
    """

    code: str
    description: str
    requires_custom_value: bool
    recommended: bool
    expected_payload_shape_description: str | None
    is_parametric_pick: bool


@dataclass(frozen=True)
class ReconcileDiscrepancyResolveVM:
    """View-model for ``GET /reconcile/discrepancy/{id}/resolve`` (spec §5.1).

    18 fields total: 8 BaseLayoutVM-shaped (standalone, NOT inherited per
    spec §3 R3 LOCK + plan §F F11) + 10 page-specific. Mirrors
    SchwabSetupVM's pattern at swing/web/view_models/schwab.py.

    ``form_action`` is server-derived and validated by ``__post_init__`` to
    match ``f"/reconcile/discrepancy/{discrepancy_id}/resolve"`` byte-for-
    byte — prevents form-action drift between handler + template.

    ``prior_*`` fields carry the operator's previously-submitted values when
    re-rendering after a 400 validation failure (so the form preserves
    operator input across the round-trip).
    """

    # Base-layout fields (8 standalone, mirror BaseLayoutVM shape).
    session_date: str
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None

    # Page-specific fields (10).
    discrepancy_id: int = 0
    form_action: str = ""
    pre_resolution_context: ReconcilePreResolutionContext | None = None
    choices: tuple[ReconcileChoiceFormItem, ...] = ()
    prior_choice_code: str = ""
    prior_custom_value_raw: str = ""
    prior_resolution_reason: str = ""
    prior_ambiguity_kind_at_render: str = ""
    error_band_message: str | None = None
    error_band_field_hint: str | None = None

    def __post_init__(self) -> None:
        if not self.session_date:
            raise ValueError(
                "ReconcileDiscrepancyResolveVM.session_date must be non-empty",
            )
        if self.unresolved_material_discrepancies_count < 0:
            raise ValueError(
                "ReconcileDiscrepancyResolveVM."
                "unresolved_material_discrepancies_count must >= 0; got "
                f"{self.unresolved_material_discrepancies_count!r}",
            )
        if self.recent_multi_leg_auto_correction_count < 0:
            raise ValueError(
                "ReconcileDiscrepancyResolveVM."
                "recent_multi_leg_auto_correction_count must >= 0; got "
                f"{self.recent_multi_leg_auto_correction_count!r}",
            )
        if self.banner_resolve_link is not None and (
            not self.banner_resolve_link
            or not self.banner_resolve_link.startswith("/")
        ):
            raise ValueError(
                "ReconcileDiscrepancyResolveVM.banner_resolve_link must be "
                f"None or a non-empty string starting with '/'; got "
                f"{self.banner_resolve_link!r}",
            )
        if self.discrepancy_id <= 0:
            raise ValueError(
                "ReconcileDiscrepancyResolveVM.discrepancy_id must be > 0; "
                f"got {self.discrepancy_id!r}",
            )
        expected_form_action = (
            f"/reconcile/discrepancy/{self.discrepancy_id}/resolve"
        )
        if self.form_action != expected_form_action:
            raise ValueError(
                "ReconcileDiscrepancyResolveVM.form_action must match "
                f"{expected_form_action!r} (server-derived from "
                f"discrepancy_id); got {self.form_action!r}",
            )


# ---------------------------------------------------------------------------
# Per-discrepancy-type render helpers (spec §7.1). Each helper is PURE —
# consumes ``disc`` + parsed ``expected`` + parsed ``actual`` dicts and emits
# a ReconcilePreResolutionContext with type-specific label/value triples.
#
# Numeric fields render with ``:.2f`` per spec §7.1 + Phase 12 C.B Codex
# M#3 LOCK precedent. Missing keys raise KeyError which the dispatch
# function catches + downgrades to generic fallback per spec §5 graceful-
# degradation contract (never raise from a pure renderer).
# ---------------------------------------------------------------------------


def _format_price(value: Any) -> str:
    """Format a numeric value with ``:.2f``; return '-' for None."""
    if value is None:
        return "-"
    return f"{float(value):.2f}"


def _signed_delta(schwab: Any, journal: Any) -> str:
    """Format the signed ``(schwab - journal)`` delta with ``:.2f``.

    Returns '-' when either side is None (cannot compute).
    """
    if schwab is None or journal is None:
        return "-"
    delta = float(schwab) - float(journal)
    return f"{delta:.2f}"


def _base_context_kwargs(
    disc: ReconciliationDiscrepancy,
) -> dict[str, Any]:
    """Extract the shared (non-render-specific) ctx kwargs from ``disc``."""
    return {
        "discrepancy_type": disc.discrepancy_type,
        "ambiguity_kind": disc.ambiguity_kind or "",
        "ticker": disc.ticker or "",
        "field_name": disc.field_name or "",
        "classifier_resolution_reason": disc.resolution_reason or "",
        "material": bool(disc.material_to_review),
        "created_at": disc.created_at or "",
        "run_id": disc.run_id,
    }


def _render_pre_resolution_context_entry_price_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_price = expected["price"]
    schwab_price = actual.get("price")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal entry price",
        journal_side_value=_format_price(journal_price),
        schwab_side_label="Schwab entry price",
        schwab_side_value=_format_price(schwab_price),
        delta_label="Price delta",
        delta_value=_signed_delta(schwab_price, journal_price),
    )


def _render_pre_resolution_context_close_price_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_price = expected["price"]
    schwab_price = actual.get("price")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal close price",
        journal_side_value=_format_price(journal_price),
        schwab_side_label="Schwab close price",
        schwab_side_value=_format_price(schwab_price),
        delta_label="Price delta",
        delta_value=_signed_delta(schwab_price, journal_price),
    )


def _render_pre_resolution_context_stop_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_stop = expected["stop_price"]
    schwab_stop = actual.get("stop_price")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal stop",
        journal_side_value=_format_price(journal_stop),
        schwab_side_label="Schwab stop trigger",
        schwab_side_value=_format_price(schwab_stop),
        delta_label="Stop delta",
        delta_value=_signed_delta(schwab_stop, journal_stop),
    )


def _render_pre_resolution_context_position_qty_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_qty = expected["quantity"]
    schwab_qty = actual.get("quantity")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal quantity",
        journal_side_value=str(journal_qty),
        schwab_side_label="Schwab quantity",
        schwab_side_value="-" if schwab_qty is None else str(schwab_qty),
        delta_label="Quantity delta",
        delta_value=_signed_delta(schwab_qty, journal_qty),
    )


def _render_pre_resolution_context_cash_movement_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_amount = expected["amount"]
    schwab_amount = actual.get("amount")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal amount",
        journal_side_value=_format_price(journal_amount),
        schwab_side_label="Schwab amount",
        schwab_side_value=_format_price(schwab_amount),
        delta_label="Amount delta",
        delta_value=_signed_delta(schwab_amount, journal_amount),
    )


def _render_pre_resolution_context_snapshot_mismatch(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    journal_nlv = expected["equity_dollars"]
    schwab_nlv = actual.get("equity_dollars")
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal NLV",
        journal_side_value=_format_price(journal_nlv),
        schwab_side_label="Schwab NLV",
        schwab_side_value=_format_price(schwab_nlv),
        delta_label="NLV delta",
        delta_value=_signed_delta(schwab_nlv, journal_nlv),
    )


def _render_pre_resolution_context_unmatched_open_fill(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    return _render_unmatched_fill_shared(disc, expected, actual)


def _render_pre_resolution_context_unmatched_close_fill(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    return _render_unmatched_fill_shared(disc, expected, actual)


def _render_unmatched_fill_shared(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    """Shared renderer for unmatched_open_fill + unmatched_close_fill.

    Per spec §7.1: journal side renders ``{quantity} @ {price:.2f} on
    {fill_datetime}`` from the expected envelope; Schwab side renders
    ``(none)`` when ``actual['matched'] is None`` AND
    ``_parse_parametric_pick_count(resolution_reason) == 0``, else
    ``{N} candidates within window``. Delta is the record count N.
    """
    quantity = expected["quantity"]
    price = expected["price"]
    fill_datetime = expected["fill_datetime"]
    journal_value = f"{quantity} @ {float(price):.2f} on {fill_datetime}"
    n = _parse_parametric_pick_count(disc.resolution_reason)
    schwab_value = f"{n} candidates within window" if n > 0 else "(none)"
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal fill",
        journal_side_value=journal_value,
        schwab_side_label="Schwab match",
        schwab_side_value=schwab_value,
        delta_label="Schwab record count",
        delta_value=str(n),
    )


def _render_pre_resolution_context_equity_delta(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    """Per spec §7.1: equity_delta carries journal/source/delta in the
    expected envelope only; actual envelope is unused for this type."""
    journal_nlv = expected["journal"]
    schwab_nlv = expected["source"]
    delta = expected["delta"]
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal NLV",
        journal_side_value=_format_price(journal_nlv),
        schwab_side_label="Schwab NLV",
        schwab_side_value=_format_price(schwab_nlv),
        delta_label="Equity delta",
        delta_value=_format_price(delta),
    )


def _render_pre_resolution_context_sector_tamper(
    disc: ReconciliationDiscrepancy,
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> ReconcilePreResolutionContext:
    expected_sector = expected["sector"]
    expected_industry = expected["industry"]
    actual_sector = actual["sector"]
    actual_industry = actual["industry"]
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Form-rendered sector/industry",
        journal_side_value=f"{expected_sector}/{expected_industry}",
        schwab_side_label="Operator-submitted",
        schwab_side_value=f"{actual_sector}/{actual_industry}",
        delta_label="Field",
        delta_value=disc.field_name or "",
    )


_RENDER_HELPERS_BY_DISCREPANCY_TYPE: dict[
    str,
    Callable[
        [ReconciliationDiscrepancy, dict[str, Any], dict[str, Any]],
        ReconcilePreResolutionContext,
    ],
] = {
    "entry_price_mismatch": _render_pre_resolution_context_entry_price_mismatch,
    "close_price_mismatch": _render_pre_resolution_context_close_price_mismatch,
    "stop_mismatch": _render_pre_resolution_context_stop_mismatch,
    "position_qty_mismatch": _render_pre_resolution_context_position_qty_mismatch,
    "cash_movement_mismatch": _render_pre_resolution_context_cash_movement_mismatch,
    "snapshot_mismatch": _render_pre_resolution_context_snapshot_mismatch,
    "unmatched_open_fill": _render_pre_resolution_context_unmatched_open_fill,
    "unmatched_close_fill": _render_pre_resolution_context_unmatched_close_fill,
    "equity_delta": _render_pre_resolution_context_equity_delta,
    "sector_tamper": _render_pre_resolution_context_sector_tamper,
}


def _truncate(text: str | None, n: int = _GENERIC_TRUNCATE_LEN) -> str:
    """Truncate ``text`` to ``n`` chars; return empty string for None."""
    if text is None:
        return ""
    if len(text) <= n:
        return text
    return text[:n]


def _render_generic_fallback(
    disc: ReconciliationDiscrepancy,
    parse_warning: str,
) -> ReconcilePreResolutionContext:
    """Generic fallback renderer (spec §5 graceful-degradation).

    Renders the raw JSON envelopes truncated to 80 chars + records the
    parse-failure reason in ``parse_warning``. NEVER raises.
    """
    return ReconcilePreResolutionContext(
        **_base_context_kwargs(disc),
        journal_side_label="Journal value",
        journal_side_value=_truncate(disc.expected_value_json),
        schwab_side_label="Schwab value",
        schwab_side_value=_truncate(disc.actual_value_json),
        delta_label="Delta",
        delta_value=disc.delta_text or "-",
        parse_warning=parse_warning,
    )


def _render_pre_resolution_context(
    disc: ReconciliationDiscrepancy,
) -> ReconcilePreResolutionContext:
    """Dispatch to the per-type helper based on ``disc.discrepancy_type``.

    Graceful-degradation contract (NEVER raises):

    - Falls back to generic renderer when the type is unknown.
    - Catches ``json.JSONDecodeError`` + ``TypeError`` on JSON parse.
    - Catches ``KeyError`` from per-type helpers (missing-key on the
      expected/actual payload path) and falls back.

    All graceful-degradation paths set ``parse_warning`` to a short
    explanatory reason; the happy path leaves it ``None``.
    """
    helper = _RENDER_HELPERS_BY_DISCREPANCY_TYPE.get(disc.discrepancy_type)
    if helper is None:
        return _render_generic_fallback(
            disc,
            parse_warning=(
                f"unknown discrepancy_type: {disc.discrepancy_type!r}"
            ),
        )
    try:
        expected = (
            json.loads(disc.expected_value_json)
            if disc.expected_value_json
            else {}
        )
        actual = (
            json.loads(disc.actual_value_json)
            if disc.actual_value_json
            else {}
        )
    except (json.JSONDecodeError, TypeError) as exc:
        return _render_generic_fallback(
            disc,
            parse_warning=f"json parse failed: {exc}",
        )
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return _render_generic_fallback(
            disc,
            parse_warning="json envelope is not a JSON object",
        )
    try:
        return helper(disc, expected, actual)
    except KeyError as exc:
        return _render_generic_fallback(
            disc,
            parse_warning=f"missing key in payload: {exc}",
        )
