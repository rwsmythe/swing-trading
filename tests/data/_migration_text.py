"""Read a schema object's HEAD definition out of the migration files.

P34 / F12 condition 6 / encoding 9: a test that reads a trigger's text out of
the migration that FIRST created it keeps passing -- green -- against a
SUPERSEDED definition once a later migration re-creates the object (gotcha
#31's shape: a check that still reads true about the wrong artefact). A test
about a re-created object reads its HEAD definition: the LAST migration, in
ascending order, that CREATEs it.
"""
from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[2] / "swing" / "data" / "migrations")

_KINDS = r"(?:TABLE|TRIGGER|(?:UNIQUE\s+)?INDEX|VIEW)"


def _create_re(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"^CREATE\s+{_KINDS}\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?{re.escape(name)}\"?"
        r"(?=[\s(])",
        re.MULTILINE,
    )


def _statement_at(text: str, start: int) -> str:
    """The CREATE statement beginning at ``start``, without its ``;``.

    A trigger body ends at the first line that is exactly ``END;`` or ends
    with ``END;`` (the repo's trigger idioms: a multi-line body closing on its
    own line, or a one-line ``BEGIN SELECT RAISE(...); END;``); any other
    statement ends at the first ``;`` at a line end.
    """
    head = text[start:start + 40].upper()
    if "TRIGGER" in head:
        m = re.compile(r"(?:^|\s)END;[ \t]*$", re.MULTILINE).search(text, start)
        assert m is not None, "unterminated trigger"
        return text[start:m.end()].rstrip()[:-1]
    m = re.compile(r";[ \t]*$", re.MULTILINE).search(text, start)
    assert m is not None, "unterminated statement"
    return text[start:m.start()]


def head_create_statement(name: str) -> tuple[Path, str]:
    """``(path, statement)`` of the LAST migration that CREATEs ``name``."""
    found: tuple[Path, str] | None = None
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        text = path.read_text(encoding="utf-8")
        hits = list(_create_re(name).finditer(text))
        if hits:
            found = (path, _statement_at(text, hits[-1].start()))
    assert found is not None, f"no migration creates {name}"
    return found


def create_statement_in(path: Path, name: str) -> str:
    """The (single) CREATE statement for ``name`` in ONE migration file."""
    text = path.read_text(encoding="utf-8")
    hits = list(_create_re(name).finditer(text))
    assert len(hits) == 1, (path.name, name, len(hits))
    return _statement_at(text, hits[0].start())
