"""3e.10 dark theme — Task A CSS-content contracts.

Pins three contracts on swing/web/static/app.css:

  A.1 — `:root` block defines all locked semantic theme tokens with
        light-theme defaults (per dispatch brief §0.3 #5).
  A.2 — `body.dark` block redefines `--bg` and `--fg` (at minimum) so
        the toggle just flips a class on body and the variables cascade.
  A.3 — outside the `:root` and `body.dark` blocks, no raw hex color or
        rgb()/rgba() values appear in CSS rule declarations — color rules
        MUST reference theme tokens via `var(--...)`.

Visual rendering + interactive behavior remain operator-witnessed (§5);
these tests pin the structural contract that survives a refactor regression.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


APP_CSS = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "web"
    / "static"
    / "app.css"
)


# Locked token list per dispatch brief §0.3 #5. All MUST be defined under
# `:root { ... }`. Implementer may add MORE tokens; this list is the minimum.
LOCKED_ROOT_TOKENS = (
    "--bg",
    "--bg-elevated",
    "--bg-muted",
    "--fg",
    "--fg-muted",
    "--border",
    "--accent",
    "--accent-hover",
    "--badge-bullish-bg",
    "--badge-bullish-fg",
    "--badge-caution-bg",
    "--badge-caution-fg",
    "--badge-bearish-bg",
    "--badge-bearish-fg",
    "--state-entered-bg",
    "--state-entered-fg",
    "--state-managing-bg",
    "--state-managing-fg",
    "--state-partial_exited-bg",
    "--state-partial_exited-fg",
    "--state-closed-bg",
    "--state-closed-fg",
    "--state-reviewed-bg",
    "--state-reviewed-fg",
    "--badge-update-today-bg",
    "--badge-update-today-fg",
    "--badge-update-needed-bg",
    "--badge-update-needed-fg",
    "--field-error-bg",
    "--field-error-fg",
    "--banner-degraded-bg",
    "--banner-degraded-fg",
    "--stale-fg",
)


def _read_css() -> str:
    return APP_CSS.read_text(encoding="utf-8")


def _extract_block(css: str, selector_pattern: str) -> str:
    """Return the concatenation of all block bodies (text inside braces) of
    blocks whose selector matches the given regex pattern. Empty string if
    none found. Concatenating across multiple matches handles classes
    declared in both a combined-selector block (shared layout properties)
    and a dedicated block (per-class color rules) — both contribute to the
    effective style for the class.
    """
    matches = re.findall(
        selector_pattern + r"\s*\{([^}]*)\}", css, flags=re.DOTALL,
    )
    return "\n".join(matches)


def test_a1_root_block_defines_all_locked_tokens():
    """A.1 — `:root` block must define every locked semantic token."""
    css = _read_css()
    root_body = _extract_block(css, r":root")
    assert root_body, "No `:root { ... }` block found in app.css"
    missing = [t for t in LOCKED_ROOT_TOKENS if t + ":" not in root_body]
    assert not missing, (
        f"Missing locked tokens under :root: {missing}\n"
        f"All locked tokens must be declared under :root with light-theme values."
    )


def test_a2_dark_block_overrides_at_least_bg_and_fg():
    """A.2 — `body.dark` block must redefine at least `--bg` and `--fg`."""
    css = _read_css()
    dark_body = _extract_block(css, r"body\.dark")
    assert dark_body, "No `body.dark { ... }` block found in app.css"
    for token in ("--bg", "--fg"):
        assert token + ":" in dark_body, (
            f"body.dark does not redefine {token}; the toggle relies on dark "
            f"overrides of at least --bg and --fg."
        )


def test_a3_no_raw_hex_outside_root_and_dark_blocks():
    """A.3 — outside `:root` and `body.dark`, no hex/rgb color literals
    appear in CSS declarations. Color rules MUST reference `var(--...)`.

    This is a hard-anti-regression contract: if a future PR sneaks a
    hardcoded `#abcdef` back into a rule, the dark theme silently fails
    for that selector. Comments are allowed to contain hex (we strip them
    before scanning).
    """
    css = _read_css()
    # Strip CSS block comments to avoid false positives from documentation.
    css_no_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Strip the two theme-token-defining blocks; the hex literals there are
    # the AUTHORITATIVE token values.
    for selector in (r":root", r"body\.dark"):
        css_no_comments = re.sub(
            selector + r"\s*\{[^}]*\}", "", css_no_comments, flags=re.DOTALL,
        )

    hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    rgb_pattern = re.compile(r"\brgba?\(")
    hex_hits = hex_pattern.findall(css_no_comments)
    rgb_hits = rgb_pattern.findall(css_no_comments)
    assert not hex_hits, (
        f"Hex color literal(s) found outside :root/body.dark: {hex_hits}\n"
        f"All color rules must use var(--token) references so the dark "
        f"override cascades."
    )
    assert not rgb_hits, (
        f"rgb()/rgba() literal(s) found outside :root/body.dark: {rgb_hits}\n"
        f"Use var(--token) instead."
    )


@pytest.mark.parametrize(
    "selector_class, expected_bg_var, expected_fg_var",
    [
        ("state-entered", "--state-entered-bg", "--state-entered-fg"),
        ("state-managing", "--state-managing-bg", "--state-managing-fg"),
        (
            "state-partial_exited",
            "--state-partial_exited-bg",
            "--state-partial_exited-fg",
        ),
        ("state-closed", "--state-closed-bg", "--state-closed-fg"),
        ("state-reviewed", "--state-reviewed-bg", "--state-reviewed-fg"),
        (
            "badge-update-today",
            "--badge-update-today-bg",
            "--badge-update-today-fg",
        ),
        (
            "badge-update-needed",
            "--badge-update-needed-bg",
            "--badge-update-needed-fg",
        ),
    ],
)
def test_a4_state_and_badge_classes_reference_their_tokens(
    selector_class, expected_bg_var, expected_fg_var
):
    """A.4 — each state/badge class block must reference its paired tokens
    via `var(--...)` for both background and foreground (not arbitrary
    raw values, not unrelated tokens).
    """
    css = _read_css()
    block = _extract_block(css, r"\." + re.escape(selector_class))
    assert block, f"No `.{selector_class} {{ ... }}` block found"
    assert f"var({expected_bg_var})" in block, (
        f".{selector_class} does not reference var({expected_bg_var})"
    )
    assert f"var({expected_fg_var})" in block, (
        f".{selector_class} does not reference var({expected_fg_var})"
    )
