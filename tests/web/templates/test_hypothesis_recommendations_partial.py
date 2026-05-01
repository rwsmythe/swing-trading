"""Direct render tests for the hypothesis_recommendations.html.j2 partial.

Task 4 of hyp-recs success-path fix: the partial must accept an `oob`
kwarg. With `oob=True`, the partial ALWAYS emits a
`<section id="hypothesis-recommendations">` element (so HTMX has a valid
OOB-swap target even when `vm.active_recommendations` is empty), and the
section carries `hx-swap-oob="true"`. The empty-OOB branch additionally
drops the `class="hypothesis-recommendations"` styling and adds the
`hidden` global attribute so no chrome is visible. With `oob=False`
(default), the legacy behavior is preserved: empty recs render nothing.

Renders go through the same `_build_templates(...)` path the production
app uses (autoescape=True, FileSystemLoader rooted at swing/web/templates)
so the test catches loader-config drift as well as markup drift.
"""
from __future__ import annotations

import re

from swing.web.app import _build_templates, _templates_dir
from swing.web.view_models.dashboard import (
    HypRecsSectionVM,
    HypothesisRecommendation,
)


def _render(vm: HypRecsSectionVM, **ctx) -> str:
    templates = _build_templates(_templates_dir())
    template = templates.env.get_template(
        "partials/hypothesis_recommendations.html.j2"
    )
    return template.render(vm=vm, **ctx)


def _make_rec(
    ticker: str = "AAPL", *, in_flight: int = 0,
) -> HypothesisRecommendation:
    return HypothesisRecommendation(
        ticker=ticker,
        current_price=180.50,
        hypothesis_id=1,
        hypothesis_name="A+ baseline",
        hypothesis_progress_n=0,
        hypothesis_progress_target=20,
        tripwire_fired=False,
        tripwire_reason=None,
        suggested_label="A+ baseline candidate",
        pivot_price=181.00,
        hypothesis_in_flight_n=in_flight,
    )


def test_partial_oob_true_empty_recs_emits_hidden_section():
    """oob=True + empty recs → emit a `<section ... hx-swap-oob="true" hidden>`
    so HTMX has a valid OOB-swap target. No table or heading inside."""
    vm = HypRecsSectionVM(active_recommendations=())
    out = _render(vm, oob=True)
    assert 'id="hypothesis-recommendations"' in out
    assert 'hx-swap-oob="true"' in out
    # The HTML5 `hidden` global attribute (separated by whitespace).
    assert re.search(r"\bhidden\b", out), out
    # No populated chrome.
    assert "<h2>" not in out
    assert "<table" not in out


def test_partial_oob_false_empty_recs_emits_nothing():
    """oob=False (default) + empty recs → preserve legacy: no section."""
    vm = HypRecsSectionVM(active_recommendations=())
    out = _render(vm)  # oob omitted, default False
    assert 'id="hypothesis-recommendations"' not in out


def test_partial_oob_true_populated_recs_emits_section_and_rows():
    """oob=True + populated recs → emit the section with `hx-swap-oob="true"`
    AND render each rec row through the existing row partial."""
    vm = HypRecsSectionVM(active_recommendations=(_make_rec("AAPL"),))
    out = _render(vm, oob=True)
    assert 'id="hypothesis-recommendations"' in out
    assert 'hx-swap-oob="true"' in out
    # Row content reaches the output (ticker rendered by the row partial).
    assert "AAPL" in out


def test_partial_renders_in_flight_decoration_when_nonzero():
    """When `hypothesis_in_flight_n > 0`, the row's progress cell renders
    `N/T (+K in flight)` so the operator sees both closed-evidence count
    and open-position attribution.

    Discriminator: with in_flight=2 the row contains '(+2 in flight)';
    without the template change, only 'N/T' renders and the assertion
    fails. Tests that the new VM field actually flows into the row
    template (not just that the dataclass holds the value)."""
    vm = HypRecsSectionVM(active_recommendations=(_make_rec("AAPL", in_flight=2),))
    out = _render(vm)
    assert "(+2 in flight)" in out, (
        f"row template must render '(+N in flight)' decoration when "
        f"hypothesis_in_flight_n > 0. Body[:1000]={out[:1000]!r}"
    )


def test_partial_omits_in_flight_decoration_when_zero():
    """When `hypothesis_in_flight_n == 0`, the row renders only `N/T`
    (no decoration). Avoids visual noise like '(+0 in flight)'."""
    vm = HypRecsSectionVM(active_recommendations=(_make_rec("AAPL", in_flight=0),))
    out = _render(vm)
    assert "in flight" not in out, (
        "row template must omit the in-flight decoration when count is "
        f"zero. Body[:1000]={out[:1000]!r}"
    )


def test_partial_oob_true_populated_recs_omits_hidden_attr_and_keeps_class():
    """oob=True + populated recs → the section opening tag MUST keep the
    `class="hypothesis-recommendations"` styling AND must NOT carry the
    HTML5 `hidden` global attribute (the populated render replaces the
    earlier `<section hidden>` placeholder on OOB swap and must restore
    full chrome)."""
    vm = HypRecsSectionVM(active_recommendations=(_make_rec("AAPL"),))
    out = _render(vm, oob=True)
    # Extract ONLY the opening <section ...> tag for the hyp-recs section,
    # so an `aria-hidden` or `hidden` attribute that might appear inside row
    # content cannot false-trip the `hidden` assertion.
    m = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>',
        out,
    )
    assert m is not None, "no <section id=hypothesis-recommendations> opening tag"
    opening_tag = m.group(0)
    assert 'class="hypothesis-recommendations"' in opening_tag, opening_tag
    assert not re.search(r"\bhidden\b", opening_tag), opening_tag
