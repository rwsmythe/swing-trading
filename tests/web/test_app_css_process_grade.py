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


def _block(css: str, selector_line: str) -> str:
    """Return the text from `selector_line` up to its first closing '}'.

    app.css uses one-declaration-per-line within a flat selector block, so the
    first '}' after the selector start is that block's close. read_text() runs in
    universal-newline mode, so the CRLF file presents as '\\n' here.
    """
    start = css.index(selector_line)
    end = css.index("}", start)
    return css[start:end]


def test_series_tokens_defined_in_both_theme_blocks():
    # Codex R1-M4 / R1-m2: scope each token assertion to its actual selector
    # block (a global count would falsely pass on two declarations in one block,
    # and the dark theme is the COMBINED `html.dark, body.dark {…}` FOUC block).
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    root = _block(css, ":root {")
    dark = _block(css, "html.dark,\nbody.dark {")
    for token in ("--series-process", "--series-entry", "--series-management", "--series-exit"):
        assert (token + ":") in root, f"{token} missing from :root"
        assert (token + ":") in dark, f"{token} missing from html.dark,body.dark"


def test_per_series_two_class_stroke_rules_present():
    # Codex R1-M1: the two-class selector (specificity 0,2,0) beats the
    # single-class base rule (0,1,0) regardless of source order.
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".process-grade-rolling-line.metric-entry_grade_rolling_N { stroke: var(--series-entry); }" in css
    assert ".process-grade-rolling-line.metric-management_grade_rolling_N { stroke: var(--series-management); }" in css
    assert ".process-grade-rolling-line.metric-exit_grade_rolling_N { stroke: var(--series-exit); }" in css
    assert ".process-grade-rolling-line { stroke: var(--accent); }" in css   # base rule + A-6 STAYS


def test_legend_swatch_fill_rules_present():
    # Codex R1-M3: SVG presentation attrs cannot take var(); the swatch <rect>
    # must resolve its fill via a CSS rule keyed by the same metric-<name> class.
    css = Path("swing/web/static/app.css").read_text(encoding="utf-8")
    assert ".process-grade-legend-swatch { fill: var(--accent); }" in css
    assert ".process-grade-legend-swatch.metric-entry_grade_rolling_N { fill: var(--series-entry); }" in css
    assert ".process-grade-legend-swatch.metric-management_grade_rolling_N { fill: var(--series-management); }" in css
    assert ".process-grade-legend-swatch.metric-exit_grade_rolling_N { fill: var(--series-exit); }" in css
