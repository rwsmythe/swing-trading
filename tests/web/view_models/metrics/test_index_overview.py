"""T-5.2 — metrics overview VM enhancement (P14.N5)."""
from __future__ import annotations

from dataclasses import fields

from swing.web.view_models.metrics.index import (
    MetricsIndexSurface,
    _ascii,
    _SURFACES,
)


def test_surface_has_overview_fields_with_safe_defaults():
    names = {f.name for f in fields(MetricsIndexSurface)}
    assert {
        "headline_stat_text", "headline_caption", "headline_suppressed_text",
        "sparkline_points", "sparkline_suppressed_text", "sparkline_kind",
    } <= names
    s = MetricsIndexSurface(path="/x", label="X", description="d")
    assert s.headline_stat_text is None
    assert s.sparkline_kind == "none"


def test_ascii_sanitizer_coerces_geq_glyph_without_question_mark():
    # honesty.py emits "need: >=N" with a real U+2265; the overview must ASCII it
    # via a MAPPED substitution (no silent "?" masking - Codex R2 MINOR).
    out = _ascii("[grade: n too low (current: 3, need: ≥5)]")
    assert out.isascii()
    assert ">=5" in out
    assert "?" not in out  # the glyph was mapped, not replace-masked
    assert _ascii(None) is None


def test_surfaces_registry_is_ascii():
    # The template renders surface.label + surface.description verbatim; the
    # static registry MUST be ASCII so body.isascii() holds (Codex R2 CRITICAL).
    for s in _SURFACES:
        assert s.label.isascii(), s.label
        assert s.description.isascii(), s.description
