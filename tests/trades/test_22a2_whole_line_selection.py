"""22-A2 OBS-1 -- a tier-2 selection is EXACTLY ONE WHOLE artifact line.

RD's ruling A-R1 item 2 (option b) with CHARC's shape review (A-R1-SHAPE):
``quoted_text`` must equal one element of the artifact split on ``\\n``, with
one trailing ``\\r`` removed from that element; the quote carries neither.
F13's whole-token rule was written about the RECORD's tokens, but
``find_token`` applies it to the QUOTE's tokens, and a sub-line quote's edges
are operator-chosen -- so ``41.42 OII 2026-08-10 53.98`` cut from the record
line ``141.42 OII 2026-08-10 53.981`` manufactured two whole tokens the record
does not carry.  A line boundary is ``\\n``, outside every token class, so a
whole-line quote's edge tokens are whole in the record by construction.

TWO named refusals (CHARC point 2, E-10's reason): a quote absent from the
artifact is still ``quoted_text_not_in_artifact`` and is checked FIRST; every
present-but-not-a-whole-line quote (sub-line, two lines, a quote carrying its
own ``\\r``) is ``quoted_text_not_a_whole_line``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import T25_AUTHOR_INSTANT
from tests.trades._git_world import GitWorld
from tests.trades.test_22a2_correction_service import (  # noqa: F401 -- fixture
    RD_STATE,
    _apply,
    _count,
    _evidence,
    _t25,
    ticking_clock,
)

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC)
# RD's OBS-1 record line and the sub-line quote cut from it.
OBS1_LINE = b"141.42 OII 2026-08-10 53.981"
OBS1_QUOTE = "41.42 OII 2026-08-10 53.98"


def _artifact(line57: bytes, *, eol: bytes = b"\n") -> bytes:
    lines = [f"line {i}".encode("ascii") for i in range(1, 57)]
    return eol.join([*lines, line57, b"line 58", b""])


def _preflight(tmp_path: Path, artifact: bytes, quoted: str) -> fve.PreflightResult:
    world = GitWorld(tmp_path / "git")
    world.commit("README.md", b"base\n")
    sha = world.commit(RD_STATE, artifact, author_date=T25_AUTHOR_INSTANT)
    world.push()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "artifact_path": RD_STATE, "artifact_commit_sha": sha,
        "quoted_text": quoted}), encoding="utf-8")
    return fve.run_preflight(evidence, repo_dir=world.work, now_utc=NOW)


def test_obs1_a_sub_line_quote_refuses_not_a_whole_line(tmp_path: Path) -> None:
    """The OBS-1 case, pinned.  Pre-fix arithmetic: the quote IS a
    byte-substring of the artifact and carries no line break, so the pre-fix
    preflight returns FACTS (and criterion 3 then finds 41.42 and 53.98 as
    whole tokens of the QUOTE)."""
    artifact = _artifact(OBS1_LINE)
    assert OBS1_QUOTE.encode("utf-8") in artifact
    result = _preflight(tmp_path, artifact, OBS1_QUOTE)
    assert result.failure == "quoted_text_not_a_whole_line"
    assert result.facts is None


@pytest.mark.usefixtures("ticking_clock")
def test_obs1_the_same_line_quoted_whole_reaches_criterion_3_naming_pivot(
    tmp_path: Path,
) -> None:
    """The whole line passes the selection check and reaches the conjunction,
    where criterion 3 REFUSES naming ``pivot``: 53.98 is not a whole token of
    ``53.981`` -- the F13 rule now reaching the record."""
    assert _preflight(tmp_path / "p", _artifact(OBS1_LINE),
                      OBS1_LINE.decode("utf-8")).failure is None
    repo, evidence = _evidence(tmp_path, line57=OBS1_LINE)
    conn, cfg = _t25(tmp_path)
    try:
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            _apply(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert "criterion 3: pivot" in str(exc.value)
        assert _count(conn) == 0
    finally:
        conn.close()


def test_obs1_a_crlf_artifact_line_quoted_without_its_cr_admits(tmp_path: Path) -> None:
    artifact = _artifact(OBS1_LINE, eol=b"\r\n")
    result = _preflight(tmp_path, artifact, OBS1_LINE.decode("utf-8"))
    assert result.failure is None
    assert result.facts is not None


def test_obs1_a_crlf_artifact_line_quoted_with_its_cr_refuses(tmp_path: Path) -> None:
    """The terminator rule: the quote carries neither ``\\n`` nor ``\\r``."""
    artifact = _artifact(OBS1_LINE, eol=b"\r\n")
    quoted = OBS1_LINE.decode("utf-8") + "\r"
    assert quoted.encode("utf-8") in artifact
    result = _preflight(tmp_path, artifact, quoted)
    assert result.failure == "quoted_text_not_a_whole_line"


def test_obs1_a_quote_spanning_two_lines_refuses_not_a_whole_line(tmp_path: Path) -> None:
    artifact = _artifact(OBS1_LINE)
    quoted = OBS1_LINE.decode("utf-8") + "\nline 58"
    assert quoted.encode("utf-8") in artifact
    result = _preflight(tmp_path, artifact, quoted)
    assert result.failure == "quoted_text_not_a_whole_line"


def test_obs1_a_quote_absent_from_the_artifact_still_names_not_in_artifact(
    tmp_path: Path,
) -> None:
    """CHARC point 5: the two refusals stay distinct, and presence is checked
    FIRST.  An impl that folds the two names into one FAILS this."""
    artifact = _artifact(OBS1_LINE)
    absent = "141.42 OII 2026-08-10 53.982"
    assert absent.encode("utf-8") not in artifact
    result = _preflight(tmp_path, artifact, absent)
    assert result.failure == "quoted_text_not_in_artifact"


def test_obs1_the_refusal_constant_is_renamed_not_added() -> None:
    assert fve.FAILURE_QUOTED_TEXT_NOT_A_WHOLE_LINE == "quoted_text_not_a_whole_line"
    assert fve.FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT == "quoted_text_not_in_artifact"
    assert not hasattr(fve, "FAILURE_QUOTED_TEXT_NOT_ONE_LINE")
