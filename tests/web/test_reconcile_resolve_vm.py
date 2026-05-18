"""Tests for ReconcileDiscrepancyResolveVM + sub-VMs + per-discrepancy-type
render helpers in ``swing.web.view_models.reconcile`` (Phase 12.5 #2 T-2.2).

Covers spec §5.1 (ReconcileDiscrepancyResolveVM, 18 fields), §5.2
(ReconcilePreResolutionContext, 15 fields — plan acceptance says 14 but the
spec table lists 15 including ``parse_warning``; we include all 15), §5.3
(ReconcileChoiceFormItem, 6 fields), and §7.1 (per-discrepancy-type render
helper outputs).
"""

from __future__ import annotations

import pytest

from swing.data.models import ReconciliationDiscrepancy
from swing.web.view_models.reconcile import (
    ReconcileChoiceFormItem,
    ReconcileDiscrepancyResolveVM,
    ReconcilePreResolutionContext,
    _render_pre_resolution_context,
)

_UNMATCHED_FILL_EXPECTED = (
    '{"quantity": 100, "price": 5.30,'
    ' "fill_datetime": "2026-05-15T14:30:00Z"}'
)


# ---------------------------------------------------------------------------
# Helpers for constructing test fixtures.
# ---------------------------------------------------------------------------


def _make_discrepancy(
    *,
    discrepancy_id: int = 1,
    run_id: int = 10,
    discrepancy_type: str = "entry_price_mismatch",
    ticker: str = "CVGI",
    field_name: str = "price",
    expected_value_json: str | None = '{"price": 5.30}',
    actual_value_json: str | None = '{"price": 5.23}',
    delta_text: str | None = "-0.07",
    resolution_reason: str | None = None,
    ambiguity_kind: str | None = None,
    material_to_review: int = 1,
    created_at: str = "2026-05-18T12:00:00Z",
    fill_id: int | None = 9,
    trade_id: int | None = 3,
    cash_movement_id: int | None = None,
) -> ReconciliationDiscrepancy:
    return ReconciliationDiscrepancy(
        discrepancy_id=discrepancy_id,
        run_id=run_id,
        discrepancy_type=discrepancy_type,
        trade_id=trade_id,
        fill_id=fill_id,
        cash_movement_id=cash_movement_id,
        linked_daily_management_record_id=None,
        ticker=ticker,
        field_name=field_name,
        expected_value_json=expected_value_json,
        actual_value_json=actual_value_json,
        delta_text=delta_text,
        material_to_review=material_to_review,
        resolution="unresolved",
        resolution_reason=resolution_reason,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at=created_at,
        ambiguity_kind=ambiguity_kind,
    )


def _make_pre_resolution_context(
    *,
    discrepancy_type: str = "entry_price_mismatch",
    ambiguity_kind: str = "",
    ticker: str = "CVGI",
    field_name: str = "price",
    journal_side_label: str = "Journal entry price",
    journal_side_value: str = "5.30",
    schwab_side_label: str = "Schwab entry price",
    schwab_side_value: str = "5.23",
    delta_label: str = "Price delta",
    delta_value: str = "-0.07",
    classifier_resolution_reason: str = "",
    material: bool = True,
    created_at: str = "2026-05-18T12:00:00Z",
    run_id: int = 10,
    parse_warning: str | None = None,
) -> ReconcilePreResolutionContext:
    return ReconcilePreResolutionContext(
        discrepancy_type=discrepancy_type,
        ambiguity_kind=ambiguity_kind,
        ticker=ticker,
        field_name=field_name,
        journal_side_label=journal_side_label,
        journal_side_value=journal_side_value,
        schwab_side_label=schwab_side_label,
        schwab_side_value=schwab_side_value,
        delta_label=delta_label,
        delta_value=delta_value,
        classifier_resolution_reason=classifier_resolution_reason,
        material=material,
        created_at=created_at,
        run_id=run_id,
        parse_warning=parse_warning,
    )


# ---------------------------------------------------------------------------
# ReconcileDiscrepancyResolveVM construction + __post_init__ tests.
# ---------------------------------------------------------------------------


def test_reconcile_discrepancy_resolve_vm_construction() -> None:
    """Happy-path construction with all 18 fields populated."""
    ctx = _make_pre_resolution_context()
    choices = (
        ReconcileChoiceFormItem(
            code="keep_journal_as_is",
            description="Keep journal value as-is.",
            requires_custom_value=False,
            recommended=False,
            expected_payload_shape_description=None,
            is_parametric_pick=False,
        ),
    )
    vm = ReconcileDiscrepancyResolveVM(
        session_date="2026-05-18",
        stale_banner=None,
        price_source_degraded=False,
        price_source_degraded_until=None,
        ohlcv_source_degraded=False,
        unresolved_material_discrepancies_count=2,
        recent_multi_leg_auto_correction_count=0,
        banner_resolve_link="/reconcile/discrepancy/1/resolve",
        discrepancy_id=1,
        form_action="/reconcile/discrepancy/1/resolve",
        pre_resolution_context=ctx,
        choices=choices,
        prior_choice_code="",
        prior_custom_value_raw="",
        prior_resolution_reason="",
        prior_ambiguity_kind_at_render="",
        error_band_message=None,
        error_band_field_hint=None,
    )
    assert vm.discrepancy_id == 1
    assert vm.form_action == "/reconcile/discrepancy/1/resolve"
    assert vm.pre_resolution_context is ctx
    assert vm.choices == choices


def test_reconcile_discrepancy_resolve_vm_post_init_rejects_negative_unresolved_count() -> None:
    ctx = _make_pre_resolution_context()
    with pytest.raises(ValueError, match="unresolved_material_discrepancies_count"):
        ReconcileDiscrepancyResolveVM(
            session_date="2026-05-18",
            unresolved_material_discrepancies_count=-1,
            discrepancy_id=1,
            form_action="/reconcile/discrepancy/1/resolve",
            pre_resolution_context=ctx,
            choices=(),
        )


def test_reconcile_discrepancy_resolve_vm_post_init_rejects_zero_discrepancy_id() -> None:
    ctx = _make_pre_resolution_context()
    with pytest.raises(ValueError, match="discrepancy_id"):
        ReconcileDiscrepancyResolveVM(
            session_date="2026-05-18",
            discrepancy_id=0,
            form_action="/reconcile/discrepancy/0/resolve",
            pre_resolution_context=ctx,
            choices=(),
        )


def test_reconcile_discrepancy_resolve_vm_post_init_rejects_form_action_mismatch() -> None:
    ctx = _make_pre_resolution_context()
    with pytest.raises(ValueError, match="form_action"):
        ReconcileDiscrepancyResolveVM(
            session_date="2026-05-18",
            discrepancy_id=99,
            form_action="/reconcile/discrepancy/100/resolve",
            pre_resolution_context=ctx,
            choices=(),
        )


# ---------------------------------------------------------------------------
# Per-discrepancy-type render helper tests via the dispatch function.
# ---------------------------------------------------------------------------


def test_reconcile_pre_resolution_context_renders_entry_price_mismatch() -> None:
    """Entry price mismatch: journal=5.30, schwab=5.23 -> delta=-0.07."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.discrepancy_type == "entry_price_mismatch"
    assert ctx.journal_side_label == "Journal entry price"
    assert ctx.journal_side_value == "5.30"
    assert ctx.schwab_side_label == "Schwab entry price"
    assert ctx.schwab_side_value == "5.23"
    assert ctx.delta_label == "Price delta"
    assert ctx.delta_value == "-0.07"
    assert ctx.parse_warning is None


def test_reconcile_pre_resolution_context_renders_unmatched_open_fill_n_eq_3() -> None:
    """Unmatched open fill with N=3 candidates in window."""
    disc = _make_discrepancy(
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=_UNMATCHED_FILL_EXPECTED,
        actual_value_json='{"matched": null}',
        resolution_reason="Schwab returned 3 orders within the match window",
        ambiguity_kind="multi_match_within_window",
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.discrepancy_type == "unmatched_open_fill"
    assert ctx.journal_side_label == "Journal fill"
    assert "100" in ctx.journal_side_value
    assert "5.30" in ctx.journal_side_value
    assert "2026-05-15" in ctx.journal_side_value
    assert ctx.schwab_side_label == "Schwab match"
    assert ctx.schwab_side_value == "3 candidates within window"
    assert ctx.delta_label == "Schwab record count"
    assert ctx.delta_value == "3"


def test_reconcile_pre_resolution_context_renders_unmatched_open_fill_zero_count() -> None:
    """Unmatched open fill where resolution_reason doesn't match regex -> N=0."""
    disc = _make_discrepancy(
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=_UNMATCHED_FILL_EXPECTED,
        actual_value_json='{"matched": null}',
        resolution_reason="No Schwab orders in window",
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.schwab_side_value == "(none)"
    assert ctx.delta_value == "0"
    assert ctx.delta_label == "Schwab record count"


def test_reconcile_pre_resolution_context_generic_fallback_on_unknown_discrepancy_type() -> None:
    """Unknown discrepancy_type -> generic fallback with parse_warning.

    Bypasses ReconciliationDiscrepancy.__post_init__ enum validation via
    object.__setattr__ — defends the dispatch helper against future
    discrepancy_type additions that lag the renderer's dispatch table.
    """
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"foo": "bar"}',
        actual_value_json='{"baz": "qux"}',
        field_name="foo",
    )
    object.__setattr__(disc, "discrepancy_type", "some_unknown_type")
    ctx = _render_pre_resolution_context(disc)
    assert ctx.parse_warning is not None
    assert ctx.journal_side_label == "Journal value"
    assert "foo" in ctx.journal_side_value
    assert ctx.schwab_side_label == "Schwab value"


def test_reconcile_pre_resolution_context_generic_fallback_on_malformed_json() -> None:
    """Malformed JSON -> generic fallback, no raise.

    Bypasses ReconciliationDiscrepancy.__post_init__ JSON validation via
    object.__setattr__ — defends the dispatch helper against future
    drift where a stored row's payload becomes unparseable.
    """
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    object.__setattr__(disc, "expected_value_json", "{invalid")
    ctx = _render_pre_resolution_context(disc)
    assert ctx.parse_warning is not None
    assert "parse" in ctx.parse_warning.lower() or "json" in ctx.parse_warning.lower()


def test_reconcile_pre_resolution_context_generic_fallback_on_missing_key() -> None:
    """Per-type helper raises KeyError -> dispatch catches + falls back."""
    # entry_price_mismatch expects 'price' key. Plant 'wrong_key' to trigger
    # KeyError inside the helper.
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"wrong_key": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.parse_warning is not None


def test_dispatch_falls_back_on_value_error_in_helper() -> None:
    """Codex R1 Major #1: type-invalid payload (e.g. ``{"price": "N/A"}``)
    flows into the per-type helper which then raises ``ValueError`` from
    ``float("N/A")``. Dispatch MUST catch ValueError + degrade to the
    generic fallback (set ``parse_warning``) — NOT propagate the
    ValueError up + bubble as 500.
    """
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": "N/A"}',
        actual_value_json='{"price": 5.23}',
    )
    # Must not raise ValueError.
    ctx = _render_pre_resolution_context(disc)
    assert ctx.parse_warning is not None


def test_dispatch_falls_back_on_type_error_in_helper() -> None:
    """Codex R1 Major #1: type-invalid payload where ``expected['price']``
    is a dict (e.g. ``{"price": {}}``). Per-type helper raises ``TypeError``
    from ``float({})``. Dispatch MUST catch TypeError + degrade.
    """
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": {}}',
        actual_value_json='{"price": 5.23}',
    )
    # Must not raise TypeError.
    ctx = _render_pre_resolution_context(disc)
    assert ctx.parse_warning is not None


def test_dispatch_falls_back_on_null_price_value() -> None:
    """Codex R1 Major #1: payload contains an explicit ``null`` price.
    ``expected['price']`` resolves to Python None; the helper's
    ``_format_price(None)`` returns '-' (graceful), BUT ``_signed_delta``
    also handles None gracefully.

    The discriminating shape: pair a null journal price with an actual
    schwab dict that triggers a per-type helper raise via float(None) on
    a path the helper does NOT defensively short-circuit. For
    entry_price_mismatch, ``journal_price = expected["price"]`` is None,
    which short-circuits both _format_price + _signed_delta. So we use a
    different shape: position_qty_mismatch which calls _format_qty on
    None — but that's also defensive.

    Safest discriminating signal: assert that null payload does NOT raise
    AND parse_warning EITHER (a) stays None (the helper handles None) OR
    (b) becomes set (dispatch caught + fell back). Either disposition is
    acceptable — the BINDING behavior under Codex R1 M#1 is that NO
    exception propagates up.
    """
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": null}',
        actual_value_json='{"price": 5.23}',
    )
    # Must not raise.
    ctx = _render_pre_resolution_context(disc)
    # Either graceful None-handling (no warning) or fallback (warning set);
    # the binding contract is "no propagation". A ValueError-on-float-None
    # path would propagate without the (ValueError, TypeError) catch.
    assert ctx is not None


# ---------------------------------------------------------------------------
# ReconcileChoiceFormItem tests.
# ---------------------------------------------------------------------------


def test_reconcile_choice_form_item_is_parametric_pick_true_for_pick_schwab_record_prefix() -> None:
    """Code 'pick_schwab_record_3' -> is_parametric_pick=True."""
    item = ReconcileChoiceFormItem(
        code="pick_schwab_record_3",
        description="Pick Schwab record #3 as canonical.",
        requires_custom_value=False,
        recommended=False,
        expected_payload_shape_description=None,
        is_parametric_pick=True,
    )
    assert item.is_parametric_pick is True
    assert item.code == "pick_schwab_record_3"


def test_reconcile_choice_form_item_is_parametric_pick_false_for_static_codes() -> None:
    """Code 'keep_journal_as_is' -> is_parametric_pick=False."""
    item = ReconcileChoiceFormItem(
        code="keep_journal_as_is",
        description="Keep journal value as-is.",
        requires_custom_value=False,
        recommended=False,
        expected_payload_shape_description=None,
        is_parametric_pick=False,
    )
    assert item.is_parametric_pick is False


# ---------------------------------------------------------------------------
# T-Q2.2 Part B: compared_pairs field on ReconcilePreResolutionContext.
# ---------------------------------------------------------------------------


def test_dataclass_has_compared_pairs_field() -> None:
    """ReconcilePreResolutionContext must expose exactly 16 dataclass fields
    (the 15 original fields plus ``compared_pairs``)."""
    fields = ReconcilePreResolutionContext.__dataclass_fields__
    assert "compared_pairs" in fields, (
        "T-Q2.2 Part B: compared_pairs field is missing from "
        "ReconcilePreResolutionContext"
    )
    assert len(fields) == 16, (
        f"Expected 16 dataclass fields, got {len(fields)}: {list(fields)}"
    )


def test_compared_pairs_defaults_to_none_when_omitted() -> None:
    """The helper ``_make_pre_resolution_context`` (15-arg form) must still
    work after adding the 16th field with a default of None."""
    ctx = _make_pre_resolution_context()
    assert ctx.compared_pairs is None


def test_entry_price_mismatch_populates_compared_pairs() -> None:
    """entry_price_mismatch render helper sets compared_pairs with at least
    one tuple whose label is 'entry price'."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "entry price" in labels


def test_entry_price_mismatch_compared_pairs_values() -> None:
    """entry_price_mismatch: first pair carries journal=5.30, schwab=5.23."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    first = ctx.compared_pairs[0]
    assert first[0] == "entry price"
    assert first[1] == pytest.approx(5.30)
    assert first[2] == pytest.approx(5.23)


def test_entry_price_mismatch_includes_quantity_when_present() -> None:
    """Optional quantity pair is included when both sides carry quantity."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30, "quantity": 100}',
        actual_value_json='{"price": 5.23, "quantity": 100}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "quantity" in labels


def test_entry_price_mismatch_omits_quantity_when_absent() -> None:
    """Optional quantity pair is omitted when neither side carries quantity."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "quantity" not in labels


def test_close_price_mismatch_populates_compared_pairs() -> None:
    """close_price_mismatch render helper sets compared_pairs with 'close price'."""
    disc = _make_discrepancy(
        discrepancy_type="close_price_mismatch",
        expected_value_json='{"price": 12.70}',
        actual_value_json='{"price": 12.75}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "close price" in labels


def test_stop_mismatch_populates_compared_pairs() -> None:
    """stop_mismatch render helper sets compared_pairs with 'stop price'."""
    disc = _make_discrepancy(
        discrepancy_type="stop_mismatch",
        field_name="stop_price",
        expected_value_json='{"stop_price": 4.50}',
        actual_value_json='{"stop_price": 4.55}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "stop price" in labels


def test_position_qty_mismatch_populates_compared_pairs() -> None:
    """position_qty_mismatch render helper sets compared_pairs with 'position quantity'."""
    disc = _make_discrepancy(
        discrepancy_type="position_qty_mismatch",
        field_name="quantity",
        expected_value_json='{"quantity": 100}',
        actual_value_json='{"quantity": 90}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "position quantity" in labels


def test_cash_movement_mismatch_populates_compared_pairs() -> None:
    """cash_movement_mismatch render helper sets compared_pairs with 'amount'."""
    disc = _make_discrepancy(
        discrepancy_type="cash_movement_mismatch",
        field_name="amount",
        expected_value_json='{"amount": 100.0}',
        actual_value_json='{"amount": 99.5}',
        cash_movement_id=1,
        fill_id=None,
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "amount" in labels


def test_snapshot_mismatch_populates_compared_pairs() -> None:
    """snapshot_mismatch render helper sets compared_pairs with 'equity dollars'."""
    disc = _make_discrepancy(
        discrepancy_type="snapshot_mismatch",
        field_name="equity_dollars",
        expected_value_json='{"equity_dollars": 2000.00}',
        actual_value_json='{"equity_dollars": 1980.00}',
        fill_id=None,
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "equity dollars" in labels


def test_equity_delta_compared_pairs_uses_production_emitter_shape() -> None:
    """equity_delta: compared_pairs uses the correct production emitter shape.

    Production emitters (reconciliation.py:453-457 and
    schwab_reconciliation.py:1119-1122) write:
      expected_value_json = {"equity_dollars": journal_equity}
      actual_value_json   = {"equity_dollars": source_nlv}

    Earlier fixture used {"journal": ..., "source": ..., "delta": ...} in the
    expected envelope only; that was synthetic-fixture-vs-production-emitter
    shape drift (CLAUDE.md gotcha).  This test pins the correct emitter shape.
    """
    disc = _make_discrepancy(
        discrepancy_type="equity_delta",
        field_name="equity_dollars",
        expected_value_json='{"equity_dollars": 2000.00}',
        actual_value_json='{"equity_dollars": 2034.78}',
        fill_id=None,
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    assert len(ctx.compared_pairs) == 1
    label, journal_val, source_val = ctx.compared_pairs[0]
    assert label == "equity dollars"
    assert journal_val == pytest.approx(2000.00)
    assert source_val == pytest.approx(2034.78)


def test_sector_tamper_populates_compared_pairs() -> None:
    """sector_tamper render helper sets compared_pairs with 'sector' and 'industry'."""
    disc = _make_discrepancy(
        discrepancy_type="sector_tamper",
        field_name="sector",
        expected_value_json=(
            '{"sector": "Technology", "industry": "Software"}'
        ),
        actual_value_json=(
            '{"sector": "Healthcare", "industry": "Biotech"}'
        ),
        fill_id=None,
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    labels = [t[0] for t in ctx.compared_pairs]
    assert "sector" in labels
    assert "industry" in labels


def test_unmatched_open_fill_compared_pairs_is_none() -> None:
    """unmatched_open_fill: compared_pairs must be None (no tabular comparison)."""
    disc = _make_discrepancy(
        discrepancy_type="unmatched_open_fill",
        field_name="fill_match",
        expected_value_json=_UNMATCHED_FILL_EXPECTED,
        actual_value_json='{"matched": null}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is None


def test_unmatched_close_fill_compared_pairs_is_none() -> None:
    """unmatched_close_fill: compared_pairs must be None (no tabular comparison)."""
    disc = _make_discrepancy(
        discrepancy_type="unmatched_close_fill",
        field_name="fill_match",
        expected_value_json=_UNMATCHED_FILL_EXPECTED,
        actual_value_json='{"matched": null}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is None


def test_generic_fallback_compared_pairs_is_none() -> None:
    """Unknown discrepancy_type falls back to generic helper which sets
    compared_pairs=None (no type-specific comparison available)."""
    disc = _make_discrepancy(
        discrepancy_type="entry_price_mismatch",
        expected_value_json='{"price": 5.30}',
        actual_value_json='{"price": 5.23}',
    )
    object.__setattr__(disc, "discrepancy_type", "completely_unknown_type")
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is None


def test_compared_pairs_is_tuple_not_list() -> None:
    """compared_pairs must be a tuple (frozen-dataclass hashability contract)."""
    disc = _make_discrepancy(
        discrepancy_type="stop_mismatch",
        field_name="stop_price",
        expected_value_json='{"stop_price": 4.50}',
        actual_value_json='{"stop_price": 4.55}',
    )
    ctx = _render_pre_resolution_context(disc)
    assert ctx.compared_pairs is not None
    assert isinstance(ctx.compared_pairs, tuple), (
        f"expected tuple, got {type(ctx.compared_pairs)}"
    )
