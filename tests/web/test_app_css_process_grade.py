"""Phase 14 close-out (A-6) — the process-grade-trend SVG marker/line resolve
via the theme-aware accent token so the chart is visible in dark mode (and
actually drawn in both themes). CSS-presence guard; the binding visual check is
the operator S6 dark-mode browser gate."""
from __future__ import annotations

from pathlib import Path


def test_process_grade_css_rules_present():
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".process-grade-rolling-line" in css
    assert ".process-grade-marker" in css
    # Resolves via the theme-aware accent token (not a hardcoded hex), so it
    # tracks light/dark like .metrics-card__sparkline.
    assert "stroke: var(--accent)" in css
    assert "fill: var(--accent)" in css
