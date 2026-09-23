"""Arc 22-B Task 1 -- pin the training-epoch intent contract (F1).

The contract doc is the live home of clauses (1)-(3) (verbatim from the
archive) and the ratified clause (4).  These tests pin its bytes; migration
0040's header carries the same hash (b22_29), derived independently here.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess

import pytest

from tests.docs._contract_reader import (
    CONTRACT_DOC,
    REPO_ROOT,
    clause4_body,
    clause4_lines,
    split_lines,
)

CLAUSE4_SHA256 = "5a78e547f64df25e0f891bd271c8d5e51bbd884866ca6d04c6c85b7803ef3886"
RATIFIED_AT = "e5feec2a"
RULINGS_DOC = "docs/phase22-arc-b-rd-rulings-f1-f3.md"


def test_clause4_line_occurs_exactly_once_b22_01() -> None:
    assert len(clause4_lines(CONTRACT_DOC.read_bytes())) == 1


def test_clause4_is_byte_identical_to_the_ratified_text_b22_02() -> None:
    if shutil.which("git") is None:
        pytest.skip("git unavailable: the ratified blob cannot be read")
    proc = subprocess.run(
        ["git", "show", f"{RATIFIED_AT}:{RULINGS_DOC}"],
        capture_output=True, cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        pytest.skip(f"git show failed: {proc.stderr[:200]!r}")
    ratified = clause4_lines(proc.stdout)
    assert len(ratified) == 1
    assert clause4_lines(CONTRACT_DOC.read_bytes()) == ratified


def test_clause4_sha256_is_the_pinned_value_b22_03(tmp_path) -> None:
    raw = CONTRACT_DOC.read_bytes()
    body = clause4_body(raw)
    assert len(body) == 1024
    assert hashlib.sha256(body).hexdigest() == CLAUSE4_SHA256
    # A CRLF twin of the doc hashes identically (autocrlf checkouts).
    lf = b"\n".join(split_lines(raw))
    crlf = lf.replace(b"\n", b"\r\n")
    twin = tmp_path / "crlf.md"
    twin.write_bytes(crlf)
    assert hashlib.sha256(clause4_body(twin.read_bytes())).hexdigest() == CLAUSE4_SHA256


def test_clauses_1_to_3_are_verbatim_from_the_archive_b22_04() -> None:
    archive = (REPO_ROOT / "docs" / "research-director-context-archive.md").read_text(
        encoding="utf-8").split("\n")
    line84 = archive[83].rstrip("\r")
    start = line84.index("(1) A+ fires")
    end = line84.index("**Epoch-integrity")
    expected = line84[start:end].rstrip()
    doc = CONTRACT_DOC.read_text(encoding="utf-8").split("\n")
    quoted = [ln.rstrip("\r") for ln in doc if ln.startswith("> (1) A+ fires")]
    assert len(quoted) == 1
    assert quoted[0][2:].rstrip() == expected


def test_ratification_is_quoted_b22_05() -> None:
    assert "clause (4) is ratified." in CONTRACT_DOC.read_text(encoding="utf-8")
