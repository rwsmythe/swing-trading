from __future__ import annotations

from pathlib import Path

_MR = Path("research/method-records/minervini-primary-base-recall.md")


def test_method_record_exists_with_required_frontmatter():
    assert _MR.exists()
    text = _MR.read_text(encoding="utf-8")
    for token in (
        "key: minervini-primary-base-recall",
        "name:",
        "layer:",
        "status:",
        "version:",
    ):
        assert token in text, f"method record missing {token!r}"
    # Ch.11 grounding + L2 lock anti-promotion guard must be named.
    assert "Ch.11" in text or "Chapter 11" in text
    assert "l2_lock_preserved" in text or "L2 LOCK" in text
    # ASCII-only (spec section 8; stricter than cp1252 -- Codex WP-R2 minor 2).
    text.encode("ascii")
