from __future__ import annotations

from pathlib import Path

_STUDY = Path("research/studies/2026-06-09-minervini-primary-base-recall.md")


def test_study_doc_exists_with_required_sections():
    assert _STUDY.exists()
    text = _STUDY.read_text(encoding="utf-8")
    for heading in (
        "## Question",
        "## Null hypothesis",
        "## Methodology",
        "## Results",
        "## Limitations",
        "## Conclusion",
    ):
        assert heading in text, f"study missing {heading!r}"
    assert "../method-records/minervini-primary-base-recall.md" in text
    # n~3 proof-of-concept framing + corpus-expansion-advised must be explicit.
    assert "proof-of-concept" in text
    text.encode("ascii")  # ASCII-only (spec section 8; stricter than cp1252 -- Codex WP-R2 minor 2)
