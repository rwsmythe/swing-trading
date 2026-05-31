"""T-5.3 — /metrics overview template render (P14.N5)."""
from __future__ import annotations

import html

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.view_models.metrics.index import (
    _SURFACES,
    MetricsIndexSurface,
    MetricsIndexVM,
)

# `seeded_db` is the existing global fixture (tests/web/conftest.py) yielding
# (cfg, cfg_path) for an empty schema-only DB - enough to build the app.

_TREND_PATHS = {
    "/metrics/capital-friction",
    "/metrics/identification-funnel",
    "/metrics/process-grade-trend",
}


def _overview_section(body: str) -> str:
    """Slice out the SB5 overview ``<section>`` from the full page. The shared
    base.html.j2 carries a pre-existing U+2014 em-dash in its inline FOUC
    <style> comment (out of SB5/L7 scope), so a full-page body.isascii() is
    infeasible; scoping to the overview section faithfully tests the SB5 ASCII
    guarantee (reused suppression text + the static registry) per plan sec F."""
    start = body.index('<section class="metrics-index"')
    end = body.index("</section>", start) + len("</section>")
    return body[start:end]


def _vm_from(trend_points: str | None, suppressed: str | None) -> MetricsIndexVM:
    """Hand-build a 9-card VM: the 3 trend surfaces carry inline_svg, the rest
    are headline-only. ``trend_points`` None + ``suppressed`` set => suppressed."""
    surfaces = tuple(
        MetricsIndexSurface(
            path=s.path, label=s.label, description=s.description,
            headline_stat_text="1.23", headline_caption="x",
            sparkline_points=(trend_points if s.path in _TREND_PATHS else None),
            sparkline_suppressed_text=(suppressed if s.path in _TREND_PATHS else None),
            sparkline_kind=("inline_svg" if s.path in _TREND_PATHS else "none"),
        )
        for s in _SURFACES
    )
    return MetricsIndexVM(session_date="2026-05-30", surfaces=surfaces)


def test_overview_renders_nine_cards_with_three_polylines(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(
        "swing.web.routes.metrics.build_metrics_index_vm",
        lambda cfg, conn: _vm_from("2.00,28.00 98.00,2.00", None),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    for s in _SURFACES:
        assert f'href="{s.path}"' in body
    assert body.count("<polyline") == 3  # exactly the 3 trend surfaces
    assert _overview_section(body).isascii()


def test_overview_below_threshold_shows_suppressed_caption_no_polyline(
    seeded_db, monkeypatch,
):
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(
        "swing.web.routes.metrics.build_metrics_index_vm",
        lambda cfg, conn: _vm_from(None, "trend needs >=5 runs (have 3)"),
    )
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "<polyline" not in body
    # Jinja autoescapes '>' to '&gt;'; unescape before the substring check.
    assert "needs >=5 runs" in html.unescape(body)
    assert _overview_section(body).isascii()


def test_overview_real_builder_coerces_reused_suppression_text_to_ascii(seeded_db):
    """The BINDING #16/#32 gate: render through the REAL builder (no monkeypatch)
    on a low-sample DB so honesty.py's U+2265-carrying placeholder text actually
    flows through the central ``_ascii`` chokepoint. The monkeypatched tests
    above inject pre-built ASCII VMs and so cannot catch a real-glyph leak."""
    cfg, cfg_path = seeded_db  # empty schema => every metric suppresses (n=0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    overview = _overview_section(resp.text)
    assert overview.isascii()  # real honesty.py ">=" placeholder, coerced
    # Jinja autoescapes '>' to '&gt;'; unescape before the substring check.
    assert ">=" in html.unescape(overview)  # glyph mapped to ">=", not dropped
    assert "?" not in overview              # no replace-masking of an unmapped glyph
