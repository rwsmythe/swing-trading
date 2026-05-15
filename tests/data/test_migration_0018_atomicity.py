"""T-D.7 — line-anchored multiline regex atomicity verification for 0018.

Per Schwab API plan §C.4 + §I.1 + dispatch brief §0.9 T-D.7 + §5.2
T-D.7-row pre-emption: a line-anchored multiline regex MUST find both
``^BEGIN;`` and ``^COMMIT;`` markers in the migration source. Test is
intentionally fragile to whitespace by anchoring to start-of-line in
multiline mode rather than relying on substring containment (which would
spuriously pass if the markers ever drifted into a comment line).

Complement to ``tests/data/test_migration_0018.py`` §7 marker tests
(first-non-comment / last-non-comment) and §8 atomicity counter-example
tests; this is the bare-minimum-discipline regex pin.
"""
from __future__ import annotations

import re
from pathlib import Path

_MIGRATION_0018_PATH = (
    Path(__file__).resolve().parents[2]
    / "swing"
    / "data"
    / "migrations"
    / "0018_schwab_integration.sql"
)


def test_explicit_begin_commit_preserved() -> None:
    """Line-anchored multiline regex finds both ``^BEGIN;`` and ``^COMMIT;``.

    ``executescript()`` runs each statement in autocommit mode and
    ``conn.rollback()`` cannot undo successful intermediate statements
    unless the SQL itself opens an explicit transaction (CLAUDE.md
    gotcha). 0018 ships with explicit ``BEGIN; ... COMMIT;`` framing per
    Codex R1 Critical #1; this test pins the discipline against future
    edits that might re-introduce the implicit-COMMIT footgun.
    """
    sql = _MIGRATION_0018_PATH.read_text(encoding="utf-8")
    assert re.search(r"(?m)^BEGIN;", sql), (
        "missing line-anchored ^BEGIN; marker — 0018 must open with an "
        "explicit transaction so the migration runner can roll back "
        "partial DDL on failure (CLAUDE.md executescript() implicit-"
        "COMMIT gotcha)."
    )
    assert re.search(r"(?m)^COMMIT;", sql), (
        "missing line-anchored ^COMMIT; marker — 0018 must close the "
        "explicit transaction; without it the runner-level "
        "conn.rollback() cannot undo the script's intermediate "
        "statements (CLAUDE.md executescript() implicit-COMMIT gotcha)."
    )
