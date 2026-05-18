"""Phase 12.5 #2 Task T-2.10 — reconcile_discrepancy_resolve_error.html.j2
dedicated per-branch coverage tests + polish assertions.

T-2.5 + T-2.6 shipped the 5 error_kind branches (`not_found`,
`already_resolved`, `anchor_mismatch`, `service_error`, `db_unavailable`)
plus an `else` defense-in-depth catch-all. T-2.10 layers polish ON TOP of
the already-green branches:

- a11y attributes (`role="alert"` + `aria-live="polite"`) on the error band
- shared `<footer class="reconcile-error-footer">` CLI-parity hint
- stable `data-error-kind="{{ vm.error_kind }}"` discriminator attribute
- consistent link-back-to-/dashboard styling across all 5 branches

F# invariants pinned (per plan §F):

- F12: ASCII-only NEW text (base layout has pre-existing glyphs allowlisted
       per T-2.4 precedent; ALL NEW substrings in this template MUST be
       ASCII-only).

Tests below render the template directly through `_build_templates` so we
do not depend on the route at all (already-green at T-2.5 + T-2.6).
"""
from __future__ import annotations

from swing.web.app import _build_templates, _templates_dir
from swing.web.view_models.reconcile import ReconcileDiscrepancyErrorVM


def _render_error_template(vm: ReconcileDiscrepancyErrorVM) -> str:
    """Render the error template against a constructed VM through the same
    `_build_templates` path the production app uses."""
    templates = _build_templates(_templates_dir())
    template = templates.env.get_template(
        "reconcile_discrepancy_resolve_error.html.j2",
    )
    return template.render(vm=vm)


def _base_kwargs() -> dict[str, object]:
    return {
        "session_date": "2026-05-18",
        "unresolved_material_discrepancies_count": 0,
        "recent_multi_leg_auto_correction_count": 0,
    }


# ---------------------------------------------------------------------------
# Per-branch coverage tests (one per error_kind shipped at T-2.5 + T-2.6).
# ---------------------------------------------------------------------------


def test_error_template_not_found_branch() -> None:
    """T-2.5 ``not_found`` branch: shows discrepancy_id + link to dashboard."""
    vm = ReconcileDiscrepancyErrorVM(
        error_kind="not_found",
        error_message="",
        discrepancy_id=9999,
        **_base_kwargs(),
    )
    body = _render_error_template(vm)
    assert 'data-error-kind="not_found"' in body
    assert "9999" in body
    assert 'href="/dashboard"' in body
    # T-2.10 polish: a11y + footer + CLI-parity hint.
    assert 'role="alert"' in body
    assert 'aria-live="polite"' in body
    assert 'class="reconcile-error-footer"' in body
    assert "swing journal discrepancy show" in body


def test_error_template_already_resolved_branch() -> None:
    """T-2.5 ``already_resolved`` branch: echoes resolution + CLI hint."""
    vm = ReconcileDiscrepancyErrorVM(
        error_kind="already_resolved",
        error_message="",
        discrepancy_id=42,
        disc_resolution="operator_resolved_ambiguity",
        disc_resolved_by="operator",
        disc_created_at="2026-05-18T12:00:00Z",
        **_base_kwargs(),
    )
    body = _render_error_template(vm)
    assert 'data-error-kind="already_resolved"' in body
    assert "operator_resolved_ambiguity" in body
    # CLI-parity hint substring (per T-2.10 acceptance).
    assert "swing journal discrepancy show" in body
    assert 'href="/dashboard"' in body


def test_error_template_anchor_mismatch_branch() -> None:
    """T-2.6 ``anchor_mismatch`` branch: link to re-open the resolve form."""
    vm = ReconcileDiscrepancyErrorVM(
        error_kind="anchor_mismatch",
        error_message="ambiguity_kind_at_render does not match current state",
        discrepancy_id=42,
        **_base_kwargs(),
    )
    body = _render_error_template(vm)
    assert 'data-error-kind="anchor_mismatch"' in body
    # Operator can re-open the resolve form.
    assert 'href="/reconcile/discrepancy/42/resolve"' in body
    # error_message rendered verbatim.
    assert "ambiguity_kind_at_render does not match" in body


def test_error_template_service_error_branch() -> None:
    """T-2.6 ``service_error`` branch: echoes error_message."""
    vm = ReconcileDiscrepancyErrorVM(
        error_kind="service_error",
        error_message="ValueError: terminal state",
        discrepancy_id=42,
        **_base_kwargs(),
    )
    body = _render_error_template(vm)
    assert 'data-error-kind="service_error"' in body
    assert "ValueError: terminal state" in body
    # T-2.10 polish: a11y attributes present on every branch.
    assert 'role="alert"' in body
    assert 'aria-live="polite"' in body


def test_error_template_db_unavailable_branch() -> None:
    """T-2.6 ``db_unavailable`` branch: retry hint substring."""
    vm = ReconcileDiscrepancyErrorVM(
        error_kind="db_unavailable",
        error_message="Database is busy; please retry in a moment.",
        discrepancy_id=None,
        **_base_kwargs(),
    )
    body = _render_error_template(vm)
    assert 'data-error-kind="db_unavailable"' in body
    # Retry hint substring (default + custom messages both work).
    assert "retry" in body.lower()
    assert 'href="/dashboard"' in body


# ---------------------------------------------------------------------------
# F12 ASCII-only audit (template-section scope; base-layout glyphs excluded
# per T-2.4 precedent).
# ---------------------------------------------------------------------------


def test_error_template_ascii_only_codepoints() -> None:
    """F12: ALL text added to reconcile_discrepancy_resolve_error.html.j2 in
    T-2.5 + T-2.6 + T-2.10 polish MUST be ASCII-only. Scopes the assertion
    to the template SOURCE file (per T-2.4 template-source-scan pattern) so
    base-layout script-block glyphs are excluded by construction."""
    from pathlib import Path

    source_path = (
        Path(_templates_dir())
        / "reconcile_discrepancy_resolve_error.html.j2"
    )
    source = source_path.read_text(encoding="utf-8")
    non_ascii = sorted({hex(ord(c)) for c in source if ord(c) >= 128})
    assert not non_ascii, (
        f"Found non-ASCII codepoints in template source: {non_ascii}"
    )
