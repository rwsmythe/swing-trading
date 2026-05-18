"""Phase 12.5 #2 Task T-2.4 — reconcile_discrepancy_resolve.html.j2 template tests.

Direct template rendering through the same `_build_templates` path the
production app uses (autoescape=True, FileSystemLoader rooted at
swing/web/templates). T-2.5 (the GET route) has not shipped yet so we
cannot use TestClient; instead the test constructs a
ReconcileDiscrepancyResolveVM directly and renders the template.

F# invariants pinned:
- F4: hx-headers='{"HX-Request": "true"}' on the form (Phase 5 R1 M1 LOCK).
- F8: hidden anchor `ambiguity_kind_at_render` (TOCTOU defense).
- F9: custom-value fieldset ALWAYS rendered (JS-disabled fallback).
- F12: ASCII-only NEW text (base layout has pre-existing `WARN` glyph;
       theme-toggle moon/sun glyphs — these are allowlisted; ALL NEW
       substrings in this template MUST be ASCII-only).
"""
from __future__ import annotations

import json
from html.parser import HTMLParser

from swing.web.app import _build_templates, _templates_dir
from swing.web.view_models.reconcile import (
    ReconcileChoiceFormItem,
    ReconcileDiscrepancyResolveVM,
    ReconcilePreResolutionContext,
)

# Base-layout pre-existing non-ASCII glyphs we carve out for the ASCII-only
# audit (F12). Includes the banner WARN glyph + the dark-theme toggle's
# moon/sun emoji glyphs (each a multi-codepoint cluster including ZWJ/VS-16).
_BASE_LAYOUT_GLYPH_ALLOWLIST = frozenset(
    [
        "⚠",   # WARNING SIGN (banner glyph in base.html.j2)
        "\U0001f319",  # MOON
        "☀",   # SUN (in "☀️" cluster)
        "️",   # VARIATION SELECTOR-16
    ]
)


def _make_pre_resolution_context(
    *,
    discrepancy_type: str = "entry_price_mismatch",
    ambiguity_kind: str = "multi_partial_vs_consolidated",
    journal_side_label: str = "Journal entry price",
    journal_side_value: str = "5.30",
    schwab_side_label: str = "Schwab entry price",
    schwab_side_value: str = "5.22",
    delta_label: str = "Price delta",
    delta_value: str = "-0.08",
    parse_warning: str | None = None,
) -> ReconcilePreResolutionContext:
    return ReconcilePreResolutionContext(
        discrepancy_type=discrepancy_type,
        ambiguity_kind=ambiguity_kind,
        ticker="CVGI",
        field_name="price",
        journal_side_label=journal_side_label,
        journal_side_value=journal_side_value,
        schwab_side_label=schwab_side_label,
        schwab_side_value=schwab_side_value,
        delta_label=delta_label,
        delta_value=delta_value,
        classifier_resolution_reason=(
            "Schwab returned 2 orders within the match window"
        ),
        material=True,
        created_at="2026-05-18T10:00:00",
        run_id=42,
        parse_warning=parse_warning,
    )


def _make_vm(
    *,
    discrepancy_id: int = 41,
    pre_context: ReconcilePreResolutionContext | None = None,
    choices: tuple[ReconcileChoiceFormItem, ...] = (),
    prior_choice_code: str = "",
    prior_custom_value_raw: str = "",
    prior_resolution_reason: str = "",
    prior_ambiguity_kind_at_render: str = "",
    error_band_message: str | None = None,
    error_band_field_hint: str | None = None,
) -> ReconcileDiscrepancyResolveVM:
    if pre_context is None:
        pre_context = _make_pre_resolution_context()
    if not choices:
        choices = (
            ReconcileChoiceFormItem(
                code="consolidate_using_operator_vwap",
                description="Consolidate via operator-supplied VWAP",
                requires_custom_value=True,
                recommended=True,
                expected_payload_shape_description='{"price": X.XX}',
                is_parametric_pick=False,
            ),
            ReconcileChoiceFormItem(
                code="keep_journal_as_is",
                description="Keep journal value as-is; acknowledge divergence",
                requires_custom_value=False,
                recommended=False,
                expected_payload_shape_description=None,
                is_parametric_pick=False,
            ),
        )
    return ReconcileDiscrepancyResolveVM(
        session_date="2026-05-18",
        unresolved_material_discrepancies_count=1,
        recent_multi_leg_auto_correction_count=0,
        banner_resolve_link=None,
        discrepancy_id=discrepancy_id,
        form_action=f"/reconcile/discrepancy/{discrepancy_id}/resolve",
        pre_resolution_context=pre_context,
        choices=choices,
        prior_choice_code=prior_choice_code,
        prior_custom_value_raw=prior_custom_value_raw,
        prior_resolution_reason=prior_resolution_reason,
        prior_ambiguity_kind_at_render=prior_ambiguity_kind_at_render,
        error_band_message=error_band_message,
        error_band_field_hint=error_band_field_hint,
    )


def _render(vm: ReconcileDiscrepancyResolveVM) -> str:
    templates = _build_templates(_templates_dir())
    template = templates.env.get_template(
        "reconcile_discrepancy_resolve.html.j2"
    )
    return template.render(vm=vm)


# ---------------------------------------------------------------------------
# Test 1 — extends base layout (banner DOM discriminator from base.html.j2).
# ---------------------------------------------------------------------------


def test_resolve_template_extends_base_layout():
    """Banner discriminator from base.html.j2 should appear when the VM
    carries unresolved_material_discrepancies_count > 0."""
    vm = _make_vm()
    html = _render(vm)
    # base.html.j2 emits ``data-banner="unresolved-material-discrepancies"``
    # when the count is > 0. The fixture sets the count to 1.
    assert 'data-banner="unresolved-material-discrepancies"' in html
    # Nav bar from base layout MUST also be present.
    assert 'class="topbar"' in html


# ---------------------------------------------------------------------------
# Test 2 — entry_price_mismatch pre-resolution context rendering.
# ---------------------------------------------------------------------------


def test_resolve_template_renders_pre_resolution_context_for_entry_price_mismatch():
    """The pre-resolution context section uses the right discriminator +
    journal/Schwab labels + :.2f-formatted numeric values."""
    vm = _make_vm()
    html = _render(vm)
    assert 'data-pre-context="true"' in html
    assert "Journal entry price" in html
    assert "Schwab entry price" in html
    assert ">5.30<" in html
    assert ">5.22<" in html


# ---------------------------------------------------------------------------
# Test 3 — hx-headers attribute semantic parse (Codex R1 m#4 LOCK).
# ---------------------------------------------------------------------------


class _FormAttrCollector(HTMLParser):
    """Collect attributes of the first <form ...> tag."""

    def __init__(self) -> None:
        super().__init__()
        self.form_attrs: dict[str, str | None] | None = None

    def handle_starttag(self, tag, attrs):  # type: ignore[override]
        if tag == "form" and self.form_attrs is None:
            self.form_attrs = dict(attrs)


def test_resolve_template_renders_hx_headers_attribute_semantically():
    """Semantic equality check on the form's hx-headers attribute (robust
    to harmless quote-style normalization). Plus a complementary substring
    check that the attribute is present at all (would catch silent drops)."""
    vm = _make_vm()
    html = _render(vm)
    parser = _FormAttrCollector()
    parser.feed(html)
    assert parser.form_attrs is not None, "no <form> tag found"
    raw_value = parser.form_attrs.get("hx-headers")
    assert raw_value is not None, "form has no hx-headers attribute"
    assert json.loads(raw_value) == {"HX-Request": "true"}
    # Complementary substring check (presence-only, no quote-style coupling).
    assert "hx-headers=" in html


# ---------------------------------------------------------------------------
# Test 4 — hidden TOCTOU anchor input (F8).
# ---------------------------------------------------------------------------


def test_resolve_template_renders_ambiguity_kind_at_render_hidden_input():
    """The hidden ``ambiguity_kind_at_render`` input must render the
    discrepancy's ambiguity_kind verbatim."""
    vm = _make_vm()
    html = _render(vm)
    assert (
        '<input type="hidden" name="ambiguity_kind_at_render"\n'
        '      value="multi_partial_vs_consolidated">'
    ) in html or (
        # Allow whitespace variation between attr name and value (defensive).
        'name="ambiguity_kind_at_render"' in html
        and 'value="multi_partial_vs_consolidated"' in html
    )


# ---------------------------------------------------------------------------
# Test 5 — custom-value textarea ALWAYS rendered (F9, JS-disabled fallback).
# ---------------------------------------------------------------------------


def test_resolve_template_renders_custom_value_textarea_always():
    """The custom-value textarea must be in the DOM even when no choice is
    currently selected (no `prior_choice_code`)."""
    vm = _make_vm(prior_choice_code="")
    html = _render(vm)
    assert 'name="custom_value"' in html
    assert 'data-custom-value-input="true"' in html
    assert 'class="custom-value-fieldset"' in html


# ---------------------------------------------------------------------------
# Test 6 — ASCII-only codepoints in NEW template text (F12).
# ---------------------------------------------------------------------------


def test_resolve_template_ascii_only_codepoints():
    """The rendered ``{% block content %}`` body (everything THIS template
    adds beyond what base.html.j2 contributes) must be ASCII-only.

    base.html.j2 itself contains non-ASCII characters in comments + the
    theme-toggle emoji literals + the banner WARN glyph; those are
    pre-existing and out of scope for the F12 gate. We scope the audit
    to bytes this template emits by reading the raw template file and
    iterating its codepoints. The base layout's pre-existing glyphs do
    not appear in this template file at all so the audit is exact."""
    template_path = (
        _templates_dir() / "reconcile_discrepancy_resolve.html.j2"
    )
    source = template_path.read_text(encoding="utf-8")
    offenders: list[tuple[int, str]] = []
    for idx, c in enumerate(source):
        if ord(c) >= 128 and c not in _BASE_LAYOUT_GLYPH_ALLOWLIST:
            offenders.append((idx, c))
    assert not offenders, (
        f"Non-ASCII codepoints in reconcile_discrepancy_resolve.html.j2 "
        f"outside the allowlist: {offenders[:8]}..."
    )
