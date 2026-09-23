"""The ONE reader of the training-epoch intent contract's clause-(4) pin line.

Arc 22-B (F1, CHARC's pin shape): the pin input is the single line of
``docs/training-epoch-intent-contract.md`` that begins with ``> **(4)``, read
as BYTES (the clause is non-ASCII; a cp1252 decode would hash mojibake), with
ONE trailing ``\r`` stripped per line (autocrlf checkouts) BEFORE hashing, and
the leading two-byte block-quote marker removed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DOC = REPO_ROOT / "docs" / "training-epoch-intent-contract.md"
CLAUSE4_PREFIX = b"> **(4)"


def split_lines(raw: bytes) -> list[bytes]:
    out = []
    for line in raw.split(b"\n"):
        out.append(line[:-1] if line.endswith(b"\r") else line)
    return out


def clause4_lines(raw: bytes) -> list[bytes]:
    return [line for line in split_lines(raw) if line.startswith(CLAUSE4_PREFIX)]


def clause4_body(raw: bytes) -> bytes:
    """The pin input: the one clause-(4) line, marker removed, no terminator."""
    lines = clause4_lines(raw)
    if len(lines) != 1:
        raise ValueError(f"expected exactly one clause-(4) line, found {len(lines)}")
    return lines[0][2:]


def clause4_sha256(path: Path = CONTRACT_DOC) -> str:
    return hashlib.sha256(clause4_body(path.read_bytes())).hexdigest()
