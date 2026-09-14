"""Tests for the CLAUDE.md-weight section of scripts/harness_probe.py.

Phase 22 harness-riders D54/§4.2 reconciliation (docs/tool-director-context.md
section 4.2, amended 2026-09-14): the probe previously measured CLAUDE.md
total chars (100,000) and line-3 chars (9,000, now 2,000) and did not look at
the Gotchas section at all -- a cap the instrument does not measure is a cap
nobody sees. This adds two NEW checks over the Gotchas section (from the
"## Gotchas" line to the next top-level "## " header or EOF): the section's
total chars (max 55,000) and the count of top-level bullets ("- " lines)
whose own length exceeds 700 chars (reporting the five largest as INFO).

Exercises the pure _claude_md_checks() helper over a synthetic CLAUDE.md
under tmp_path (never the real repo CLAUDE.md).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "harness_probe.py"
_spec = importlib.util.spec_from_file_location("harness_probe", _MODULE_PATH)
harness_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness_probe)


def _claude_md_text(*, line3: str = "state line", gotchas_lines=None,
                     has_gotchas: bool = True, close_section: bool = True) -> str:
    """Build a synthetic CLAUDE.md whose THIRD line is `line3` and whose
    Gotchas section (if `has_gotchas`) carries `gotchas_lines` verbatim,
    optionally closed by a following top-level header (`close_section`)."""
    lines = ["# Swing Trading -- Claude Code Context", "", line3]
    if has_gotchas:
        lines.append("## Gotchas")
        lines.extend(gotchas_lines or [])
        if close_section:
            lines.append("## Next Section")
            lines.append("content after the Gotchas section")
    else:
        lines.append("## Some Other Section")
        lines.extend(gotchas_lines or [])
    return "\n".join(lines) + "\n"


@pytest.fixture
def root(tmp_path):
    return tmp_path


def _write_claude_md(root: Path, text: str) -> None:
    (root / "CLAUDE.md").write_text(text, encoding="utf-8")


# ============================================================================
# (a) Gotchas section under all caps -> the three lines read OK.
# ============================================================================


def test_gotchas_section_under_caps_is_ok(root):
    _write_claude_md(root, _claude_md_text(
        line3="a short state line",
        gotchas_lines=["### sub-heading", "- a short bullet", "> a blockquote"],
    ))
    rows = harness_probe._claude_md_checks(root)
    line3_rows = [r for r in rows if r[1].startswith("CLAUDE.md line-3 chars")]
    section_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas section chars")]
    bullet_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas bullets")]
    assert len(line3_rows) == 1 and line3_rows[0][0] == "OK"
    assert len(section_rows) == 1 and section_rows[0][0] == "OK"
    assert len(bullet_rows) == 1 and bullet_rows[0][0] == "OK"
    assert "bullets: 1, over 700: 0" in bullet_rows[0][1]


# ============================================================================
# (b) one bullet of 701 chars -> ATTENTION, named in the top five;
#     a 700-char bullet -> OK (the boundary twin).
# ============================================================================


def test_bullet_over_700_chars_fires_attention_and_is_named(root):
    bullet = "- " + ("x" * 699)  # "- " (2 chars) + 699 = 701 total.
    assert len(bullet) == 701
    _write_claude_md(root, _claude_md_text(gotchas_lines=[bullet]))
    rows = harness_probe._claude_md_checks(root)
    bullet_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas bullets")]
    assert bullet_rows[0][0] == "ATTENTION"
    assert "over 700: 1" in bullet_rows[0][1]
    info_rows = [line for level, line in rows if level == "INFO"]
    assert any(line.startswith("701 ") for line in info_rows)
    assert any(bullet[:60] in line for line in info_rows)


def test_bullet_at_exactly_700_chars_is_ok(root):
    bullet = "- " + ("x" * 698)  # exactly 700 total.
    assert len(bullet) == 700
    _write_claude_md(root, _claude_md_text(gotchas_lines=[bullet]))
    rows = harness_probe._claude_md_checks(root)
    bullet_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas bullets")]
    assert bullet_rows[0][0] == "OK"
    assert "over 700: 0" in bullet_rows[0][1]


def test_five_largest_over_cap_bullets_are_listed(root):
    bullets = [f"- {'x' * (800 + i)}" for i in range(7)]  # 7 over-cap bullets.
    _write_claude_md(root, _claude_md_text(gotchas_lines=bullets))
    rows = harness_probe._claude_md_checks(root)
    bullet_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas bullets")]
    assert "over 700: 7" in bullet_rows[0][1]
    info_rows = [line for level, line in rows if level == "INFO"
                 and line[0].isdigit()]
    assert len(info_rows) == 5
    # The five LARGEST (802..808 chars) are the ones named, largest first.
    sizes = [int(line.split(" ", 1)[0]) for line in info_rows]
    assert sizes == sorted(sizes, reverse=True)
    assert sizes[0] == 808  # 800 + 6 + "- " len 2 = 808


# ============================================================================
# (c) a Gotchas section of 55,001 chars -> ATTENTION; 55,000 -> OK.
# ============================================================================


def test_gotchas_section_over_55000_fires_attention(root):
    # A single non-bullet narrative line so it never trips the bullet check.
    padding = "narrative text " * 4000  # comfortably over 55,000 with the header.
    _write_claude_md(root, _claude_md_text(gotchas_lines=[padding]))
    rows = harness_probe._claude_md_checks(root)
    section_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas section chars")]
    assert section_rows[0][0] == "ATTENTION"


def test_gotchas_section_at_exactly_55000_is_ok(root):
    # "## Gotchas\n" is 11 chars; pad the body to land the section at exactly
    # 55,000 chars total (header + newline + body, no trailing newline counted
    # inside the section slice since join uses "\n".join).
    header = "## Gotchas"
    body_len = 55_000 - len(header) - 1  # -1 for the join separator
    body = "y" * body_len
    _write_claude_md(root, _claude_md_text(gotchas_lines=[body]))
    rows = harness_probe._claude_md_checks(root)
    section_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas section chars")]
    assert "55,000" in section_rows[0][1]
    assert section_rows[0][0] == "OK"


# ============================================================================
# (d) line-3 of 2,001 chars -> ATTENTION; 2,000 -> OK.
# ============================================================================


def test_line3_over_2000_fires_attention(root):
    _write_claude_md(root, _claude_md_text(line3="z" * 2001))
    rows = harness_probe._claude_md_checks(root)
    line3_rows = [r for r in rows if r[1].startswith("CLAUDE.md line-3 chars")]
    assert line3_rows[0][0] == "ATTENTION"


def test_line3_at_exactly_2000_is_ok(root):
    _write_claude_md(root, _claude_md_text(line3="z" * 2000))
    rows = harness_probe._claude_md_checks(root)
    line3_rows = [r for r in rows if r[1].startswith("CLAUDE.md line-3 chars")]
    assert line3_rows[0][0] == "OK"


# ============================================================================
# (e) no "## Gotchas" header -> INFO "section not found", never a crash.
# ============================================================================


def test_no_gotchas_header_is_info_not_found(root):
    _write_claude_md(root, _claude_md_text(has_gotchas=False))
    rows = harness_probe._claude_md_checks(root)
    info_rows = [line for level, line in rows if level == "INFO"]
    assert any("section not found" in line.lower() for line in info_rows)
    # No section/bullet rows are emitted when there is no section to measure.
    assert not any(r[1].startswith("CLAUDE.md Gotchas section chars") for r in rows)
    assert not any(r[1].startswith("CLAUDE.md Gotchas bullets") for r in rows)


def test_gotchas_section_runs_to_eof_when_no_closing_header(root):
    """No top-level "## " header follows the Gotchas section -> the section
    runs to EOF (close_section=False exercises that branch directly, rather
    than only exercising the has-a-closing-header path every other test
    uses)."""
    bullet = "- " + ("x" * 699)  # 701 chars, over the per-bullet cap.
    _write_claude_md(root, _claude_md_text(gotchas_lines=[bullet], close_section=False))
    rows = harness_probe._claude_md_checks(root)
    section_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas section chars")]
    bullet_rows = [r for r in rows if r[1].startswith("CLAUDE.md Gotchas bullets")]
    assert len(section_rows) == 1
    assert bullet_rows[0][0] == "ATTENTION"
    assert "over 700: 1" in bullet_rows[0][1]


def test_indented_gotchas_text_is_not_mistaken_for_the_header(root):
    """A line reading exactly "## Gotchas" starts the section; indented or
    otherwise-decorated text that merely CONTAINS that text (e.g. inside a
    code fence) must not be mistaken for the real header."""
    _write_claude_md(root, _claude_md_text(
        has_gotchas=False,
        gotchas_lines=["    ## Gotchas", "- a bullet under the fake header"],
    ))
    rows = harness_probe._claude_md_checks(root)
    info_rows = [line for level, line in rows if level == "INFO"]
    assert any("section not found" in line.lower() for line in info_rows)


def test_missing_claude_md_is_attention_never_crash(root):
    rows = harness_probe._claude_md_checks(root)
    assert rows == [("ATTENTION", "CLAUDE.md missing")]


def test_output_is_ascii(root):
    bullet = "- " + ("x" * 699)
    _write_claude_md(root, _claude_md_text(line3="z" * 2001, gotchas_lines=[bullet]))
    for _level, line in harness_probe._claude_md_checks(root):
        line.encode("cp1252")  # must not raise
