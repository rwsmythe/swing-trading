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


def test_cited_artifacts_are_git_tracked():
    """Option C (Phase-19 close, RD FINAL 2026-07-06; CHARC co-sign): the engine's dated
    output dirs are the EPHEMERAL instrument path (default-ignored; the keep-90 pruner
    rmtree's them). The reproducibility contract binds on CITED artifacts -- a
    decision-read that cites an engine artifact COPIES its ledger files into the study's
    TRACKED location and commits them with the read (cited = committed = prune-proof).
    This asserts the T4-decision-read's cited artifacts are actually git-tracked -- a
    REAL contract, replacing the earlier aspirational gitignore allowlist (git ls-files
    showed zero shadow-expectancy files were ever tracked under it)."""
    import subprocess

    art = "research/studies/2026-07-03-broad-watch-baseline-t4-decision-read/artifacts"
    cited = (
        "20260630T010654Z",  # the VSTS risk-unit +27R flag (T4-cited)
        "20260703T020948Z",  # T4 decision-read #1
        "20260704T223859Z",  # T4 decision-read #2 (post-19-D-merge, FINAL)
        "20260611T041306Z",  # T3 golden-gate first-priced evidence (watch-standard 2.2)
    )
    tracked = set(subprocess.run(
        ["git", "ls-files", art], capture_output=True, text=True, check=True,
    ).stdout.splitlines())
    for ts in cited:
        for name in ("summary.md", "manifest.json", "results.csv", "per_session.csv"):
            rel = f"{art}/{ts}/{name}"
            assert rel in tracked, f"cited artifact not git-tracked: {rel}"
