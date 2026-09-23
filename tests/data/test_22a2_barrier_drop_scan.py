"""22-A2 Task 1 -- F2.T (t1): the barrier-drop scan.

RD ruled F2 = (b) (defer the era model to 22-A2i) on the ground that every gap
class that exists TODAY is visible to the system.  The one that is not -- a
post-barrier retire -> re-arm (R6-02) -- is visible in its FILE-BORNE form
only if something reads the migration files.  This is that something (CHARC
F2.T (t1)): a migration numbered above 0037 that drops a barrier trigger, or
drops one of the two tables the barrier lives on (the implicit drop of a
rebuild, encoding 7), FAILS the suite unless the same file carries an era
record -- an ``INSERT INTO candidates_immutability_epoch_events`` statement
(encoding E-5), a table that only 22-A2i creates.

RD's F2 re-open condition, stated at his ruling: *"if any migration numbered
above 0038 drops a barrier trigger before 22-A2i lands, F2 re-opens and (a)
becomes mandatory BEFORE that migration merges."*  A red here IS that
condition firing.

The scan is keyed on the TWO named tables ONLY -- never on "any DROP TABLE"
(CHARC's note on encoding 7): 0039 itself drops ``provenance_corrections``.

AL2-4: a hand-run DROP followed by a byte-identical CREATE is undetectable by
construction; this scan sees file-borne drops only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import swing.data.repos.candidates_immutability_epoch as _epoch_mod
from swing.data.repos.candidates_immutability_epoch import BARRIER_TRIGGER_NAMES

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "swing" / "data" / "migrations"

# Migrations numbered ABOVE this are scanned (0037 creates the barrier).
_SCAN_ABOVE = 37

# The two tables the barrier's six triggers live on.  Dropping either removes
# its triggers WITHOUT a ``DROP TRIGGER`` statement.
BARRIER_TABLES: tuple[str, ...] = ("candidates", "candidates_immutability_epoch")

_ERA_RECORD = re.compile(
    r"\binsert\s+into\s+[\"`\[]?candidates_immutability_epoch_events[\"`\]]?",
    re.IGNORECASE,
)

_RE_OPEN_CONDITION = (
    "RD F2 re-open condition (22-A2 ledger R0.8): a migration numbered above "
    "0038 drops a barrier trigger (or a barrier table) before 22-A2i lands -> "
    "F2 re-opens and the era model (a) becomes MANDATORY before that migration "
    "merges."
)


@dataclass(frozen=True)
class Violation:
    path: str
    statement: str
    target: str


def _strip_sql_comments(text: str) -> str:
    """Remove ``--`` line comments and ``/* */`` block comments.

    String literals are respected so a ``--`` inside quotes is not a comment.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'" or ch == '"':
            j = i + 1
            while j < n:
                if text[j] == ch:
                    if j + 1 < n and text[j + 1] == ch:
                        j += 2
                        continue
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
            continue
        if text.startswith("--", i):
            j = text.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _ident(name: str) -> str:
    """Regex for an identifier, bare or quoted with "", ``, or []."""
    e = re.escape(name)
    return rf"(?:\"{e}\"|`{e}`|\[{e}\]|\b{e}\b)"


def _drop_patterns() -> list[tuple[str, re.Pattern[str]]]:
    pats: list[tuple[str, re.Pattern[str]]] = []
    for name in BARRIER_TRIGGER_NAMES:
        pats.append((
            f"trigger {name}",
            re.compile(
                rf"\bdrop\s+trigger\s+(?:if\s+exists\s+)?(?:\w+\.)?{_ident(name)}",
                re.IGNORECASE,
            ),
        ))
    for table in BARRIER_TABLES:
        pats.append((
            f"table {table}",
            re.compile(
                rf"\bdrop\s+table\s+(?:if\s+exists\s+)?(?:\w+\.)?{_ident(table)}"
                r"(?![A-Za-z0-9_])",
                re.IGNORECASE,
            ),
        ))
    return pats


def scan_migrations(dirpath: Path) -> list[Violation]:
    """Every file-borne barrier drop above 0037 lacking a same-file era record."""
    violations: list[Violation] = []
    patterns = _drop_patterns()
    for path in sorted(Path(dirpath).glob("*.sql")):
        m = re.match(r"^(\d{4})_", path.name)
        if m is None or int(m.group(1)) <= _SCAN_ABOVE:
            continue
        stripped = _strip_sql_comments(path.read_text(encoding="utf-8"))
        if _ERA_RECORD.search(stripped):
            continue
        for target, pat in patterns:
            for hit in pat.finditer(stripped):
                violations.append(Violation(
                    path=path.name, statement=hit.group(0), target=target))
    return violations


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_a2_01_drop_barrier_trigger_is_violation(tmp_path):
    _write(tmp_path, "0040_x.sql", "BEGIN;\nDROP TRIGGER trg_candidates_no_update;\nCOMMIT;\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_update"], _RE_OPEN_CONDITION


def test_a2_02_drop_table_candidates_is_violation(tmp_path):
    _write(tmp_path, "0040_x.sql", "DROP TABLE candidates;\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["table candidates"], _RE_OPEN_CONDITION


def test_a2_03_drop_table_if_exists_quoted_epoch_is_violation(tmp_path):
    _write(tmp_path, "0041_y.sql",
           'DROP TABLE IF EXISTS "candidates_immutability_epoch";\n')
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["table candidates_immutability_epoch"]


def test_a2_04_drop_other_table_is_not_violation(tmp_path):
    # 0039's own shape: the rebuild drops provenance_corrections.  An "any
    # DROP TABLE" scan would read 1 here.
    _write(tmp_path, "0039_z.sql",
           "DROP TABLE provenance_corrections;\nDROP TABLE candidates_archive;\n")
    assert scan_migrations(tmp_path) == []


def test_a2_05_drop_with_era_record_is_not_violation(tmp_path):
    _write(tmp_path, "0040_x.sql",
           "DROP TRIGGER trg_candidates_epoch_no_insert;\n"
           "INSERT INTO candidates_immutability_epoch_events (kind) VALUES ('retire');\n")
    assert scan_migrations(tmp_path) == []


def test_a2_06_drop_and_era_record_only_in_comments_is_violation(tmp_path):
    # The era record appears only in a comment; the drop is live.
    _write(tmp_path, "0040_x.sql",
           "-- INSERT INTO candidates_immutability_epoch_events (kind) VALUES ('x');\n"
           "/* INSERT INTO candidates_immutability_epoch_events */\n"
           "DROP TRIGGER IF EXISTS trg_candidates_no_delete;\n"
           "-- DROP TRIGGER trg_candidates_no_replace;\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_delete"]


def test_a2_07_real_migrations_scan_clean_and_names_imported():
    # The names are the module's OWN tuple, not a re-typed roster (D21).
    assert BARRIER_TRIGGER_NAMES is _epoch_mod.BARRIER_TRIGGER_NAMES
    assert len(BARRIER_TRIGGER_NAMES) == 6
    # Files at and below 0037 are out of the scan; 0037 itself creates the
    # barrier and 0038+ must not drop it.
    assert scan_migrations(MIGRATIONS_DIR) == [], _RE_OPEN_CONDITION
