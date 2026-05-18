"""Phase 12.5 #2 T-2.8 -- ``base.html.j2`` banner-resolve-link integration
+ Pass A retrofit completeness audit.

Per plan §A T-2.8 + invariants F11/F12/F21:

- When ``vm.banner_resolve_link`` is populated AND
  ``vm.unresolved_material_discrepancies_count > 0``, the banner's count
  text becomes an anchor pointing at the resolve form
  (``data-banner-resolve-link="true"`` marker).
- When ``vm.banner_resolve_link is None`` AND count > 0, the banner
  renders plain (no anchor).
- When count == 0, the banner is suppressed entirely regardless of
  ``banner_resolve_link``.
- Singular vs plural grammar preserved.
- F11/F21 LOCK: retrofit completeness audit runs the Pass A grep at TEST
  TIME and asserts every VM with
  ``unresolved_material_discrepancies_count`` ALSO carries
  ``banner_resolve_link``.
- F12 LOCK: NEW substrings added in T-2.8 are ASCII-only (the
  pre-existing ``<span class="banner-glyph">⚠</span>`` is preserved
  unchanged from Phase 10 T-E.3 and is carve-out-allowlisted).
- F15: HX-Redirect target (the GET resolve route) registered on
  ``app.routes`` (Phase 6 I3 LOCK).
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from swing.web.view_models.dashboard import DashboardVM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _template_env() -> Environment:
    templates_dir = (
        Path(__file__).resolve().parents[2] / "swing" / "web" / "templates"
    )
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def _make_dashboard_vm(
    *,
    count: int,
    banner_resolve_link: str | None,
) -> DashboardVM:
    """Construct a minimal DashboardVM exercising just the banner block."""
    return DashboardVM(
        generated_at="2026-05-18T10:00:00",
        session_date="2026-05-18",
        stale_banner=None,
        status_strip={},
        today_decisions=[],
        open_trades=[],
        open_trade_advisories={},
        open_trade_last_prices={},
        watchlist_top5=[],
        watchlist_remaining_count=0,
        watchlist_last_prices={},
        flag_tags={},
        candidates_by_ticker={},
        prices_generated_at=None,
        price_source_degraded=False,
        price_source_degraded_until=None,
        ohlcv_source_degraded=False,
        open_trade_rows=[],
        active_recommendations=[],
        pattern_tags={},
        needs_review_count=0,
        daily_card=None,
        weekly_card=None,
        monthly_card=None,
        unresolved_material_discrepancies_count=count,
        recent_multi_leg_auto_correction_count=0,
        daily_management_tiles=[],
        banner_resolve_link=banner_resolve_link,
    )


def _render_base(vm: DashboardVM) -> str:
    """Render ``base.html.j2`` via Jinja, providing the minimum context the
    template needs. The template extends nothing and only references
    ``vm`` for the banner block we care about."""
    env = _template_env()
    template = env.get_template("base.html.j2")
    return template.render(vm=vm, request=None, content="")


def _extract_banner(html: str) -> str:
    """Return the substring spanning the unresolved-material-discrepancies
    ``<aside>`` block so banner-scoped assertions don't accidentally
    match the multi-leg banner or other page chrome."""
    marker = 'data-banner="unresolved-material-discrepancies"'
    idx = html.find(marker)
    assert idx != -1, "unresolved-material-discrepancies banner marker not found"
    start = html.rfind("<aside", 0, idx)
    assert start != -1, "could not locate banner <aside> opening tag"
    end = html.find("</aside>", idx)
    assert end != -1, "could not locate banner </aside> closing tag"
    return html[start : end + len("</aside>")]


# ---------------------------------------------------------------------------
# 1. Anchor wrap when banner_resolve_link populated
# ---------------------------------------------------------------------------


def test_banner_template_renders_anchor_when_banner_resolve_link_populated() -> None:
    vm = _make_dashboard_vm(
        count=2,
        banner_resolve_link="/reconcile/discrepancy/99/resolve",
    )
    html = _render_base(vm)
    banner = _extract_banner(html)
    assert (
        '<a href="/reconcile/discrepancy/99/resolve" '
        'data-banner-resolve-link="true">' in banner
    ), banner
    # Count text + plural discrepancy form still present, inside the anchor.
    assert "2 unresolved material reconciliation" in banner
    assert "discrepancies" in banner


# ---------------------------------------------------------------------------
# 2. Plain text (no anchor) when banner_resolve_link is None
# ---------------------------------------------------------------------------


def test_banner_template_renders_plain_text_when_banner_resolve_link_none() -> None:
    vm = _make_dashboard_vm(count=2, banner_resolve_link=None)
    html = _render_base(vm)
    banner = _extract_banner(html)
    # No anchor wrap.
    assert "<a href=" not in banner, banner
    assert 'data-banner-resolve-link="true"' not in banner, banner
    # Count text still intact.
    assert "2 unresolved material reconciliation" in banner
    assert "discrepancies" in banner


# ---------------------------------------------------------------------------
# 3. Banner suppressed entirely when count == 0 (link None)
# ---------------------------------------------------------------------------


def test_banner_template_suppresses_banner_when_count_zero() -> None:
    vm = _make_dashboard_vm(count=0, banner_resolve_link=None)
    html = _render_base(vm)
    assert 'data-banner="unresolved-material-discrepancies"' not in html


# ---------------------------------------------------------------------------
# 4. Banner suppressed even with link populated if count == 0 (defense-in-depth)
# ---------------------------------------------------------------------------


def test_banner_template_suppresses_banner_when_count_zero_and_link_populated() -> None:
    """Anomalous state -- should never occur in production (the resolver
    only populates ``banner_resolve_link`` when there IS a pending
    discrepancy). Count predicate dominates regardless."""
    vm = _make_dashboard_vm(
        count=0,
        banner_resolve_link="/reconcile/discrepancy/99/resolve",
    )
    html = _render_base(vm)
    assert 'data-banner="unresolved-material-discrepancies"' not in html


# ---------------------------------------------------------------------------
# 5. F11/F21 retrofit completeness audit via Pass A grep at TEST TIME
# ---------------------------------------------------------------------------


def test_retrofit_completeness_audit_via_pass_a_grep() -> None:
    """F11/F21 LOCK: every dataclass with
    ``unresolved_material_discrepancies_count`` MUST also have
    ``banner_resolve_link`` field. Runs the Pass A grep (as a regex over
    file contents) + dataclass introspection at test time so future VMs
    that pick up the discrepancy count without the resolve link will
    fail this test.

    Pure-stdlib (no ``rg`` subprocess) so the test runs on any platform
    without depending on the developer's PATH.
    """
    repo_root = Path(__file__).resolve().parents[2]
    target_dir = repo_root / "swing" / "web" / "view_models"

    # Pass A regex -- same shape used at plan-drafting time.
    pass_a_pattern = re.compile(
        r"unresolved_material_discrepancies_count\s*:\s*int\s*="
    )

    matching_files: list[Path] = []
    for path in target_dir.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pass_a_pattern.search(text):
            matching_files.append(path)

    assert matching_files, (
        "Pass A grep returned no files -- sanity check failed; the "
        "discrepancy count field should be on at least BaseLayoutVM + the "
        "13 standalone VMs"
    )

    # Convert file paths to dotted module names robustly across `\` vs `/`.
    offenders: list[str] = []
    for path in matching_files:
        rel = path.resolve().relative_to(repo_root).with_suffix("")
        module_name = ".".join(rel.parts)
        mod = importlib.import_module(module_name)
        for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != module_name:
                continue
            if not dataclasses.is_dataclass(cls):
                continue
            field_names = {f.name for f in dataclasses.fields(cls)}
            if (
                "unresolved_material_discrepancies_count" in field_names
                and "banner_resolve_link" not in field_names
            ):
                offenders.append(f"{module_name}.{cls_name}")

    assert not offenders, (
        f"VMs missing banner_resolve_link: {offenders}; "
        f"add the field per Phase 12.5 #2 T-2.7 retrofit pattern"
    )


# ---------------------------------------------------------------------------
# 6. F12 ASCII-only LOCK on NEW substrings
# ---------------------------------------------------------------------------


def test_banner_new_text_ascii_only() -> None:
    """F12 LOCK: NEW substrings added in T-2.8 (the
    ``data-banner-resolve-link`` attribute + the anchor href markup +
    any wrapper text) are ASCII-only. The pre-existing
    ``<span class="banner-glyph">⚠</span>`` carve-out is
    intentionally PRESERVED and NOT subjected to this check (per plan
    §A T-2.8 explicit carve-out)."""
    new_substrings = [
        'data-banner-resolve-link="true"',
        '<a href=',
        "</a>",
    ]
    for s in new_substrings:
        non_ascii = [c for c in s if ord(c) >= 128]
        assert non_ascii == [], (
            f"NEW substring {s!r} contains non-ASCII codepoints: "
            f"{[hex(ord(c)) for c in non_ascii]}"
        )


# ---------------------------------------------------------------------------
# 7. F15: HX-Redirect target route registered on app.routes
# ---------------------------------------------------------------------------


def test_banner_link_target_route_registered_on_app_routes(seeded_db) -> None:
    """Phase 6 I3 LOCK: the resolve route the banner anchor points at
    MUST be registered on the app. The anchor uses an interpolated id;
    we verify the path TEMPLATE is registered."""
    from swing.web.app import create_app

    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    assert any(
        getattr(r, "path", None)
        == "/reconcile/discrepancy/{discrepancy_id}/resolve"
        for r in app.routes
    ), "GET /reconcile/discrepancy/{discrepancy_id}/resolve not registered"


# ---------------------------------------------------------------------------
# 8. Singular grammar when count == 1, wrapped in anchor
# ---------------------------------------------------------------------------


def test_banner_link_text_singular_when_count_eq_1() -> None:
    vm = _make_dashboard_vm(
        count=1,
        banner_resolve_link="/reconcile/discrepancy/7/resolve",
    )
    html = _render_base(vm)
    banner = _extract_banner(html)
    # Anchor wraps the entire singular phrase ending with period.
    assert (
        '<a href="/reconcile/discrepancy/7/resolve" '
        'data-banner-resolve-link="true">' in banner
    ), banner
    assert "1 unresolved material reconciliation discrepancy." in banner
    # Discriminate against the plural form leaking in the count phrase
    # (the ``data-banner="unresolved-material-discrepancies"`` attribute
    # uses the substring legitimately as a stable DOM marker).
    assert "reconciliation discrepancies" not in banner
    assert " discrepancies." not in banner
