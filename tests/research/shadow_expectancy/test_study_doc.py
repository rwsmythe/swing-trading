from __future__ import annotations

from pathlib import Path

_STUDY = Path("research/studies/2026-06-09-shadow-expectancy-engine.md")
_METHOD = Path("research/method-records/shadow-expectancy-engine.md")


def test_study_doc_exists_with_required_sections():
    assert _STUDY.exists()
    text = _STUDY.read_text(encoding="utf-8")
    for heading in ("## Question", "## Null hypothesis", "## Methodology",
                    "## Results", "## Limitations", "## Conclusion"):
        assert heading in text, f"study missing {heading!r}"
    assert "../method-records/shadow-expectancy-engine.md" in text
    assert "mechanical-ruleset shadow evidence" in text.lower()
    text.encode("ascii")  # ASCII-only (spec section 8)


def test_method_record_exists():
    assert _METHOD.exists()
    _METHOD.read_text(encoding="utf-8").encode("ascii")


def test_gitignore_allowlists_artifact_dir():
    gi = Path(".gitignore").read_text(encoding="utf-8")
    assert "!exports/research/shadow-expectancy-*" in gi
    assert "!exports/research/shadow-expectancy-*/summary.md" in gi
    assert "!exports/research/shadow-expectancy-*/manifest.json" in gi
    assert "!exports/research/shadow-expectancy-*/results.csv" in gi
    assert "!exports/research/shadow-expectancy-*/per_session.csv" in gi
