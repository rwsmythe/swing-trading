"""22-I T15 -- meta tests over the WHOLE of migration 0041 (plan section 3 T15).

    * every WHEN the file writes is COALESCE-wrapped (brief section 2.4; a NULL
      WHEN fails OPEN);
    * every no_replace over an INTEGER PK carries the 0037 `-1` idiom;
    * the manifest composition, BY EXECUTION: fresh DBs migrated to 40 and 41,
      sqlite_master diffed by (type, name) -- ADDED == the 59 names of plan
      section 1.4 exactly, CHANGED == {the F-I2 rebuild}, DELETED == {}, and no
      table / index / view text moved;
    * the file is triggers only: no CREATE TABLE / INDEX / VIEW, ALTER, DROP
      TABLE, INSERT, DELETE; exactly ONE DROP TRIGGER.

The file text is read with its `--` comments and its '...' string literals
stripped, so prose and RAISE messages (which name INSERT OR REPLACE and
DELETE freely) are never mistaken for statements.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from swing.data import db as db_mod
from tests.data._22i_guard_spec import GUARDS_22I_ADDED, REBUILT_22I, SPEC
from tests.data._22i_seed import migrated

M0041 = (Path(db_mod.__file__).resolve().parent / "migrations"
         / "0041_replace_exposure_sweep.sql")


def _strip(sql: str) -> str:
    """Remove '...' literals ('' escapes included) and -- comments, in one
    left-to-right scan (a -- inside a literal is not a comment)."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2
                    continue
                if sql[i] == "'":
                    i += 1
                    break
                i += 1
            out.append("''")
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _code() -> str:
    return _strip(M0041.read_text(encoding="utf-8"))


def _triggers(code: str) -> dict[str, str]:
    """name -> the CREATE TRIGGER statement text up to its END;."""
    out: dict[str, str] = {}
    for m in re.finditer(r"CREATE TRIGGER (\w+)(.*?)\bEND;", code, re.S):
        assert m.group(1) not in out, m.group(1)
        out[m.group(1)] = m.group(0)
    return out


def test_the_strip_helper_removes_literals_and_comments() -> None:
    assert _strip("SELECT 'a -- b', 'it''s' -- tail\nX") == "SELECT '', '' \nX"


def test_every_0041_when_is_coalesce_wrapped() -> None:
    trig = _triggers(_code())
    with_when = 0
    for name, stmt in trig.items():
        head = stmt.split("BEGIN", 1)[0]
        whens = re.findall(r"\bWHEN\b\s*(.{0,20})", head, re.S)
        assert len(whens) <= 1, name
        if whens:
            with_when += 1
            start = " ".join(whens[0].split())
            assert start.startswith(("NOT COALESCE(", "COALESCE(")), (name, start)
    assert with_when > 0


def test_0041_pk_clause_idiom() -> None:
    trig = _triggers(_code())
    replaces = {n: s for n, s in trig.items() if n.endswith("_no_replace")}
    by_abbr = {s.abbr: s for s in SPEC.values()}
    assert len(replaces) == 20  # 7 (a) + 11 (c) + 2 (c) no-twin
    for name, stmt in replaces.items():
        spec = by_abbr[name[len("trg_"):-len("_no_replace")]]
        flat = " ".join(stmt.split())
        if spec.integer_pk:
            pk = spec.pk[0]
            assert f"NEW.{pk} != -1 AND {pk} = NEW.{pk}" in flat, name
        else:
            # candidate_criteria: the composite PK HIDES the rowid, so the
            # hidden-rowid clause is required too (Reviewer B B-1, CHARC ruling).
            assert "NEW.rowid != -1 AND rowid = NEW.rowid" in flat, name
            key = " AND ".join(f"{k} = NEW.{k}" for k in spec.pk)
            assert key in flat, (name, key)


def _objects(conn: sqlite3.Connection) -> dict[tuple[str, str], str | None]:
    return {(t, n): s for t, n, s in conn.execute(
        "SELECT type, name, sql FROM sqlite_master")}


def test_0041_manifest_composition(tmp_path: Path) -> None:
    c40 = migrated(tmp_path, 40, name="m40.db")
    c41 = migrated(tmp_path, 41, name="m41.db")
    try:
        o40, o41 = _objects(c40), _objects(c41)
        v40 = c40.execute("SELECT version FROM schema_version").fetchone()[0]
        v41 = c41.execute("SELECT version FROM schema_version").fetchone()[0]
    finally:
        c40.close()
        c41.close()
    assert (v40, v41) == (40, 41)
    added = {k for k in o41 if k not in o40}
    deleted = {k for k in o40 if k not in o41}
    changed = {k for k in o40.keys() & o41.keys() if o40[k] != o41[k]}
    assert added == {("trigger", n) for n in GUARDS_22I_ADDED}
    assert len(added) == 59
    assert changed == {("trigger", n) for n in REBUILT_22I}
    assert deleted == set()
    # no table / index / view text moved (a rebuild would show here)
    for (kind, name) in o40.keys() & o41.keys():
        if kind != "trigger":
            assert o40[(kind, name)] == o41[(kind, name)], (kind, name)


def test_0041_is_triggers_only() -> None:
    code = _code()
    forbidden = {
        "CREATE TABLE": r"\bCREATE\s+(TEMP\w*\s+)?TABLE\b",
        "CREATE INDEX": r"\bCREATE\s+(UNIQUE\s+)?INDEX\b",
        "CREATE VIEW": r"\bCREATE\s+(TEMP\w*\s+)?VIEW\b",
        "ALTER": r"\bALTER\s+TABLE\b",
        "DROP TABLE": r"\bDROP\s+(TABLE|INDEX|VIEW)\b",
        "INSERT": r"\bINSERT\s+(OR\s+\w+\s+)?INTO\b",
        "REPLACE INTO": r"\bREPLACE\s+INTO\b",
        "DELETE": r"\bDELETE\s+FROM\b",
    }
    for label, pattern in forbidden.items():
        assert not re.search(pattern, code, re.I), label
    assert len(re.findall(r"\bDROP\s+TRIGGER\b", code, re.I)) == 1
    assert re.findall(r"\bUPDATE\s+(\w+)\s+SET\b", code, re.I) == ["schema_version"]
    assert set(_triggers(code)) == set(GUARDS_22I_ADDED) | set(REBUILT_22I)
