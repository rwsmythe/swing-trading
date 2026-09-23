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

QUOTED CONTENTS AND THE DROP/RENAME SEARCH (CHARC ruling A-R5, R5-03,
correcting ruling A-R4 / Codex R4-02): SQLite's grammar admits a
single-quoted STRING TOKEN as an object name, so
``DROP TRIGGER 'trg_candidates_no_update'`` really drops (measured on SQLite
3.50.4) -- R4-02's premise that "a DROP inside a literal is not a drop
either" was FALSE for the single-quote form.  So the DROP/RENAME search now
runs on the comment-stripped text with NOTHING BLANKED (R4-02's single-quote
blanking for this half is REVERSED): ``_ident`` and ``_SCHEMA_QUALIFIER``
carry the single-quoted form beside the bare, double-quoted, backtick and
bracket forms, and a DROP-shaped or RENAME-shaped text sitting inside ANY
string literal reads as the real thing -- FAIL-CLOSED, the direction a guard
is meant to err in, curable by a human reading the file.

THE ERA-RECORD search is UNCHANGED from R4-02 and keeps blanking BOTH quote
kinds before it runs (a DROP inside a string is not a drop w.r.t. THIS
search either, and an era-record text inside a string is not an era
record): a real era record written as
``INSERT INTO "candidates_immutability_epoch_events"`` OR
``INSERT INTO 'candidates_immutability_epoch_events'`` reads as NO era
record and its file's drop is flagged -- also fail-closed, curable by
unquoting; the bare, backtick and bracket forms still match.

A THIRD violation family (CHARC A-R5, R5-03(c)):
``ALTER TABLE <optional qualifier><barrier table ident> RENAME TO`` -> a
violation with target ``rename table <t>``.  A rename carries the six
triggers off the barrier table (``sqlite_master.tbl_name`` moves with it,
measured) and a later ``DROP TABLE`` of the renamed-away table is the
implicit drop of the barrier wearing another name -- the classic SQLite
rebuild idiom (RENAME the table away, CREATE the new shape under the old
name, copy the rows, DROP the renamed-away table) moves the barrier without
ever naming it in a DROP of the barrier table itself.  RENAME TO ONLY, never
RENAME COLUMN (a column rename leaves the trigger bound to the table it was
already on).

D51 (the HEAD-manifest test) and this (t1) scan COMPOSE; neither substitutes
for the other.  D51 pins that the barrier is PRESENT AT HEAD (it structurally
cannot see a drop-and-recreate inside one file -- the triggers are back by
the time the manifest reads).  (t1) pins that NO post-0037 file RETIRES the
barrier IN TEXT (the textual half D51 cannot see).  A red on either
instrument is the F2 re-open condition firing.
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


def _blank_quoted(text: str, kinds: str) -> str:
    """Blank the CONTENTS of every quoted span whose quote char is in ``kinds``.

    Both quote kinds are always RECOGNISED as spans (so a ``'`` inside a
    double-quoted span never opens a literal), with the doubled-quote escape
    honoured as ``_strip_sql_comments`` honours it; only the kinds named are
    blanked.  The quotes themselves are kept and every blanked character
    becomes a space, so no token can be formed across a blanked span.
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
            inner = text[i + 1:j]
            if ch in kinds:
                inner = " " * len(inner)
            out.append(ch + inner + (ch if j < n else ""))
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _ident(name: str) -> str:
    """Regex for an identifier, bare or quoted with '', "", ``, or [].

    The single-quoted form (R5-03) matters ONLY to the DROP/RENAME search
    (nothing is blanked there any more); the ERA-RECORD search blanks
    single-quoted contents before it runs, so this form never fires there.
    """
    e = re.escape(name)
    return rf"(?:'{e}'|\"{e}\"|`{e}`|\[{e}\]|\b{e}\b)"


# An optional schema qualifier: bare or quoted ('', "", ``, []), with optional
# whitespace around the dot (Codex R3-03 -- ``"main"."x"`` and ``main . x`` are
# valid SQLite and drop the same object as ``main.x``; R5-03 adds the
# single-quoted form, ``'main'.'x'``).
_SCHEMA_QUALIFIER = r"(?:(?:'[^']+'|\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|\w+)\s*\.\s*)?"


def _drop_patterns() -> list[tuple[str, re.Pattern[str]]]:
    pats: list[tuple[str, re.Pattern[str]]] = []
    for name in BARRIER_TRIGGER_NAMES:
        pats.append((
            f"trigger {name}",
            re.compile(
                rf"\bdrop\s+trigger\s+(?:if\s+exists\s+)?{_SCHEMA_QUALIFIER}{_ident(name)}",
                re.IGNORECASE,
            ),
        ))
    for table in BARRIER_TABLES:
        pats.append((
            f"table {table}",
            re.compile(
                rf"\bdrop\s+table\s+(?:if\s+exists\s+)?{_SCHEMA_QUALIFIER}{_ident(table)}"
                r"(?![A-Za-z0-9_])",
                re.IGNORECASE,
            ),
        ))
    # R5-03(c): ALTER TABLE <barrier table> RENAME TO -- RENAME TO only, never
    # RENAME COLUMN (a column rename leaves the trigger on the table).
    for table in BARRIER_TABLES:
        pats.append((
            f"rename table {table}",
            re.compile(
                rf"\balter\s+table\s+{_SCHEMA_QUALIFIER}{_ident(table)}\s+rename\s+to\b",
                re.IGNORECASE,
            ),
        ))
    return pats


def scan_migrations(dirpath: Path) -> list[Violation]:
    """Every file-borne barrier drop/rename above 0037 lacking a same-file
    era record.  R5-03: the DROP/RENAME search runs on the comment-stripped
    text with NOTHING blanked (fail-closed on quoted contents); the
    ERA-RECORD search is unchanged and still blanks both quote kinds before
    it runs.
    """
    violations: list[Violation] = []
    patterns = _drop_patterns()
    for path in sorted(Path(dirpath).glob("*.sql")):
        m = re.match(r"^(\d{4})_", path.name)
        if m is None or int(m.group(1)) <= _SCAN_ABOVE:
            continue
        stripped = _strip_sql_comments(path.read_text(encoding="utf-8"))
        if _ERA_RECORD.search(_blank_quoted(stripped, "'\"")):
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


# --------------------------------------------------------------------------- Codex R3-03
# A schema-qualified DROP whose qualifier is QUOTED, or spaced around the dot,
# is valid SQLite and drops the same object.  Pre-fix the optional qualifier
# was ``(?:\w+\.)?``: every form below except the bare ``main.`` scanned clean.

_QUALIFIED_TRIGGER_FORMS = (
    'DROP TRIGGER "main"."trg_candidates_no_update";\n',
    "DROP TRIGGER main . trg_candidates_no_update;\n",
    "DROP TRIGGER [main].[trg_candidates_no_update];\n",
    "DROP TRIGGER IF EXISTS `main`.`trg_candidates_no_update`;\n",
    'DROP TRIGGER "main" . trg_candidates_no_update;\n',
)
_QUALIFIED_TABLE_FORMS = (
    "DROP TABLE main . candidates;\n",
    'DROP TABLE "main"."candidates";\n',
    "DROP TABLE IF EXISTS [main] . [candidates];\n",
    "DROP TABLE `temp`.`candidates`;\n",
)


def test_codex_r3_03_a_quoted_or_spaced_schema_qualifier_on_a_trigger_is_a_violation(
    tmp_path,
):
    for i, body in enumerate(_QUALIFIED_TRIGGER_FORMS):
        d = tmp_path / str(i)
        d.mkdir()
        _write(d, "0040_x.sql", body)
        found = scan_migrations(d)
        assert [v.target for v in found] == ["trigger trg_candidates_no_update"], body


def test_codex_r3_03_a_quoted_or_spaced_schema_qualifier_on_a_table_is_a_violation(
    tmp_path,
):
    for i, body in enumerate(_QUALIFIED_TABLE_FORMS):
        d = tmp_path / str(i)
        d.mkdir()
        _write(d, "0040_x.sql", body)
        found = scan_migrations(d)
        assert [v.target for v in found] == ["table candidates"], body


def test_codex_r3_03_a_qualified_drop_of_another_table_is_not_a_violation(tmp_path):
    """The widened qualifier does not widen the TARGET: a qualified drop of a
    table that merely starts with a barrier table's name is not a hit."""
    _write(tmp_path, "0040_x.sql",
           'DROP TABLE "main"."candidates_archive";\n'
           "DROP TABLE main . provenance_corrections;\n")
    assert scan_migrations(tmp_path) == []


# --------------------------------------------------------------------------- Codex R4-02
# CHARC ruling A-R4 (R4-02): quoted CONTENTS are not statements.  Single-quoted
# contents are blanked before BOTH searches; double-quoted contents are blanked
# for the ERA-RECORD search only (a double-quoted name in DROP position is an
# identifier -- a2_03 and the R3-03 forms).  Pre-fix the era-record search ran
# over literal contents, so a quoted string carrying the era-record text
# silenced a live drop.

_LIVE_DROP = "DROP TRIGGER trg_candidates_no_update;\n"


def test_codex_r4_02_a_single_quoted_era_record_text_does_not_silence_a_live_drop(
    tmp_path,
):
    _write(tmp_path, "0040_x.sql",
           "SELECT 'INSERT INTO candidates_immutability_epoch_events';\n" + _LIVE_DROP)
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_update"]


def test_codex_r4_02_a_double_quoted_era_record_text_does_not_silence_a_live_drop(
    tmp_path,
):
    _write(tmp_path, "0040_x.sql",
           'SELECT "INSERT INTO candidates_immutability_epoch_events";\n' + _LIVE_DROP)
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_update"]


def test_codex_r4_02_charc_positive_twin_a_drop_inside_an_era_records_literal(tmp_path):
    """CHARC's positive twin, as ruled: a real era record whose VALUE is a
    DROP string, no live drop -> zero violations."""
    _write(tmp_path, "0040_x.sql",
           "INSERT INTO candidates_immutability_epoch_events (kind) "
           "VALUES ('DROP TRIGGER trg_candidates_no_update');\n")
    assert scan_migrations(tmp_path) == []


def test_r5_03_a_drop_shaped_single_quoted_literal_now_flags_fail_closed(tmp_path):
    """R5-03 SUPERSEDES this test's old name and assertion (was
    ``..._is_not_a_drop``, asserted zero violations).  R4-02's premise --
    "a DROP inside a literal is not a drop either" -- rested on the false
    belief that SQLite never treats a single-quoted span as a name; it does
    (``DROP TRIGGER 'x'`` DROPS).  So the DROP search no longer blanks
    single-quoted spans at all: this file's DROP-shaped literal (no era
    record present) now reads as a real drop -- FAIL-CLOSED, curable by a
    human reading the file.  This is the cell's replacement case for CHARC's
    (corrected) R4-02 positive twin (the twin above still passes, but for
    the reason that its file HAS a real era record and is skipped before any
    drop pattern runs -- CHARC's own ownership note)."""
    _write(tmp_path, "0040_x.sql",
           "SELECT 'DROP TRIGGER trg_candidates_no_update';\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_update"]


# --------------------------------------------------------------------------- CHARC A-R5, R5-03
# The drop search's single-quote blanking is REVERSED (nothing is blanked);
# _ident and _SCHEMA_QUALIFIER gain the single-quoted form; a new RENAME TO
# violation family is added.  The three below are the packet's "RED today"
# discriminators -- red against the pre-fix scanner (single-quote blanking,
# no RENAME pattern), green after.


def test_r5_03_single_quoted_trigger_name_in_drop_position_is_a_violation(tmp_path):
    """SQLite grammar: a single-quoted STRING TOKEN in DROP-name position is
    a name, and the drop really fires (measured on SQLite 3.50.4)."""
    _write(tmp_path, "0040_x.sql", "DROP TRIGGER 'trg_candidates_no_update';\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["trigger trg_candidates_no_update"]


def test_r5_03_single_quoted_schema_qualified_table_drop_is_a_violation(tmp_path):
    _write(tmp_path, "0040_x.sql", "DROP TABLE IF EXISTS 'main'.'candidates';\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["table candidates"]


def test_r5_03_alter_table_rename_to_rebuild_is_a_violation_naming_the_rename(tmp_path):
    """The classic SQLite rebuild idiom: RENAME the barrier table away,
    CREATE the new shape under the old name, copy the rows, DROP the
    renamed-away table.  The DROP at the end targets ``candidates_old``, not
    a barrier table name (a2_04's bound-target form), so the ONE violation
    is the RENAME itself."""
    _write(tmp_path, "0040_x.sql",
           "ALTER TABLE candidates RENAME TO candidates_old;\n"
           "CREATE TABLE candidates (id INTEGER PRIMARY KEY);\n"
           "INSERT INTO candidates SELECT * FROM candidates_old;\n"
           "DROP TABLE candidates_old;\n")
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["rename table candidates"]


def test_r5_03_alter_table_rename_to_with_quoted_schema_qualifier_is_a_violation(
    tmp_path,
):
    _write(tmp_path, "0040_x.sql", 'ALTER TABLE "main"."candidates" RENAME TO x;\n')
    found = scan_migrations(tmp_path)
    assert [v.target for v in found] == ["rename table candidates"]


def test_r5_03_alter_table_rename_to_of_a_non_barrier_table_is_not_a_violation(
    tmp_path,
):
    """The target stays bound to the barrier tables, the a2_04 form."""
    _write(tmp_path, "0040_x.sql", "ALTER TABLE candidates_archive RENAME TO y;\n")
    assert scan_migrations(tmp_path) == []


def test_r5_03_alter_table_rename_column_is_not_a_violation(tmp_path):
    """RENAME TO only, never RENAME COLUMN -- a column rename leaves the
    trigger bound to the table it was already on."""
    _write(tmp_path, "0040_x.sql", "ALTER TABLE candidates RENAME COLUMN a TO b;\n")
    assert scan_migrations(tmp_path) == []


def test_r5_03_alter_table_add_column_is_not_a_violation(tmp_path):
    _write(tmp_path, "0040_x.sql", "ALTER TABLE candidates ADD COLUMN z;\n")
    assert scan_migrations(tmp_path) == []


def test_codex_r4_02_fail_closed_a_double_quoted_era_record_table_reads_as_none(
    tmp_path,
):
    """The ruled consequence, pinned: ``INSERT INTO "candidates_immutability_
    epoch_events"`` reads as NO era record, so its file's live drop is flagged
    (FAIL-CLOSED, curable by unquoting); the bare, backtick and bracket forms
    still match."""
    table = "candidates_immutability_epoch_events"
    quoted = f'INSERT INTO "{table}" (kind) VALUES (\'retire\');\n'
    d = tmp_path / "dq"
    d.mkdir()
    _write(d, "0040_x.sql", quoted + _LIVE_DROP)
    assert [v.target for v in scan_migrations(d)] == ["trigger trg_candidates_no_update"]
    for i, name in enumerate((table, f"`{table}`", f"[{table}]")):
        d = tmp_path / str(i)
        d.mkdir()
        _write(d, "0040_x.sql",
               f"INSERT INTO {name} (kind) VALUES ('retire');\n" + _LIVE_DROP)
        assert scan_migrations(d) == [], name
