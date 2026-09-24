"""Arc 22-B Task 10 -- the two precondition pins (F2 S3, F3) and the value's
write-closure (b22_115, moved here from Task 6 because it needs this
inventory, SS-6).

* b22_150 (F2 S3): tier-2 cites ``notes``/``why_now``/``thesis``/
  ``emotional_state_pre_trade`` as a contemporaneous record, which is only
  evidence while nothing but the AUDITED corrector rewrites them. The walk
  (``tests/trades/_22b_sql_walk.py``) visits EVERY ``.execute`` /
  ``.executemany`` / ``.executescript`` call in ``swing/**/*.py``; a site
  whose SQL does not resolve statically must sit on ``DYNAMIC_SQL_SITES``
  (a closure check in BOTH directions: a new unresolved site fails, and so
  does an entry the walk no longer finds). A found writer is a REPORTED
  finding, never a new channel.
* b22_115: every site that writes ``trades.entry_intent`` or INSERTs into
  ``entry_intent_attestations`` is on a named set; a new site fails.
* b22_151 (F3, ledger R0.C C.3): death-then-fill is EXPRESSIBLE -- a fill
  strictly after a death leaves the DEATH terminal; the same-session twin is
  a fill (R6 tie -> fill).

Each walk test first shows the instrument FAILS on a planted violation (a
synthetic module run through the same walk and the same assertion helper),
so a green walk over the real tree is not a blind one.
"""
from __future__ import annotations

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from swing.latches.models import DailyBar, EntryRecord, FireRow
from swing.latches.service import derive_latches
from swing.trades.entry_intent_assignment import CITABLE_FIELDS
from tests.trades._22b_sql_walk import HOLE, Site, classify, walk_source, walk_tree

REPO_ROOT = Path(__file__).resolve().parents[2]
SWING = REPO_ROOT / "swing"
MIGRATIONS = SWING / "data" / "migrations"
CITABLE = frozenset(CITABLE_FIELDS)
TABLES = frozenset({"trades", "entry_intent_attestations"})
ANY = frozenset({"*"})
REWRITE_KINDS = frozenset({"update", "upsert", "replace"})

MIGRATION_RUNNER = ("swing/data/db.py", "_apply_migration")
CORRECTOR = ("swing/trades/reconciliation_auto_correct.py", "_update_journal_field")
REVIEW_BUILDER = ("swing/data/repos/trades.py", "update_trade_review_fields")
ATTESTATION_INSERT = (
    "swing/data/repos/entry_intent_attestations.py", "insert_attestation")
CAPTURE = ("swing/data/repos/trades.py", "insert_trade_with_event")


# --------------------------------------------------------------------------
# helpers shared by the real walk and the planted violations
# --------------------------------------------------------------------------

def _module_tree(module: str) -> ast.Module:
    return ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))


def _function(module: str, qualname: str) -> ast.FunctionDef:
    node: ast.AST = _module_tree(module)
    for part in qualname.split("."):
        node = next(n for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)) and n.name == part)
    assert isinstance(node, ast.FunctionDef)
    return node


def _walk_swing() -> list[Site]:
    return walk_tree(SWING, REPO_ROOT, TABLES)


def _citable_rewrites(sites: list[Site]) -> list[tuple]:
    """Resolved statements that REWRITE a citable field of an existing trade:
    an UPDATE / upsert naming one (or ``*``), and ANY REPLACE on trades --
    REPLACE deletes the row, so every column it does not list is rewritten
    to its default."""
    out = []
    for s in sites:
        for w in s.writes or ():
            if w.table == "trades" and (
                    w.kind == "replace"
                    or (w.kind in REWRITE_KINDS and w.columns & (CITABLE | ANY))):
                out.append((s.module, s.function, s.lineno, w.kind,
                            sorted(w.columns & (CITABLE | ANY))))
    return out


def _citable_inserters(sites: list[Site]) -> set[tuple[str, str]]:
    return {s.key for s in sites for w in (s.writes or ())
            if w.table == "trades" and w.kind == "insert"
            and w.columns & (CITABLE | ANY)}


def _uninventoried(sites: list[Site], inventory: dict) -> set[tuple[str, str]]:
    return {s.key for s in sites if s.writes is None} - set(inventory)


def _value_writers(sites: list[Site], inventory: dict) -> set[tuple[str, str]]:
    """Every site that can write ``trades.entry_intent`` (any kind) or write
    ``entry_intent_attestations`` (any kind), resolved or inventoried."""
    out = set()
    for s in sites:
        for w in s.writes or ():
            if w.table == "trades" and (
                    w.kind == "replace"
                    or w.columns & ({"entry_intent"} | ANY)):
                out.add(s.key)
            if w.table == "entry_intent_attestations":
                out.add(s.key)
    for key, entry in inventory.items():
        if entry.writes.get("trades", frozenset()) & ({"entry_intent"} | ANY):
            out.add(key)
        if entry.writes.get("entry_intent_attestations"):
            out.add(key)
    return out


# --------------------------------------------------------------------------
# the reviewed inventory of UNRESOLVED sites (each READ; verifiers check the
# declared column set against the code where the code states it)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DynamicSite:
    reason: str
    # table -> the columns this site can write on it ({"*"} = any column);
    # only the tables this walk guards are declared.
    writes: dict[str, frozenset[str]] = field(default_factory=dict)
    verify: Callable[[], None] | None = None


def _verify_migration_files() -> None:
    """The runner executes swing/data/migrations/*.sql. Walked by the SAME
    classifier: no migration UPDATEs/REPLACEs a trades citable field or
    entry_intent, none writes entry_intent_attestations, and the only writes
    carrying those columns are the two REBUILD COPIES (0014, 0040), each an
    identity copy -- ``INSERT INTO trades_new (cols) SELECT cols FROM trades``
    with the SAME column list in the SAME order."""
    guarded = TABLES | {"trades_new"}
    carriers, copies = [], []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        writes = classify(text, guarded, script=True)
        assert writes is not None, path.name
        for w in writes:
            assert w.table != "entry_intent_attestations", (path.name, w)
            if w.table in ("trades", "trades_new") and (
                    w.columns & (CITABLE | {"entry_intent"} | ANY)):
                assert (w.kind, w.table) == ("insert", "trades_new"), (path.name, w)
                carriers.append(path.name)
        for m in re.finditer(
                r"INSERT\s+INTO\s+trades_new\s*\(([^()]*)\)\s*SELECT\s+(.*?)"
                r"\s+FROM\s+trades\s*;", text, re.I | re.S):
            cols = [c.strip() for c in m.group(1).split(",")]
            sel = [c.strip() for c in m.group(2).split(",")]
            assert cols == sel, path.name
            copies.append(path.name)
    assert copies == carriers  # every carrier IS a matched identity copy
    assert carriers == ["0014_phase7_state_machine_and_fills.sql",
                        "0040_entry_intent_unintended_execution.sql"], carriers


def _verify_review_builder() -> None:
    """The SET list is built only from string literals on ``set_clauses``."""
    func = _function(*REVIEW_BUILDER)
    cols: set[str] = set()
    for node in ast.walk(func):
        literals: list[ast.expr] = []
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "set_clauses"):
            assert isinstance(node.value, ast.List)
            literals = list(node.value.elts)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == "set_clauses"):
            assert node.func.attr == "append", ast.unparse(node)
            literals = list(node.args)
        for lit in literals:
            assert isinstance(lit, ast.Constant) and isinstance(lit.value, str)
            cols.add(lit.value.split("=")[0].strip().lower())
    assert cols == DYNAMIC_SQL_SITES[REVIEW_BUILDER].writes["trades"], cols


def _verify_attestation_insert() -> None:
    from swing.data.repos import entry_intent_attestations as repo

    declared = DYNAMIC_SQL_SITES[ATTESTATION_INSERT].writes[
        "entry_intent_attestations"]
    assert frozenset(repo._COLUMNS[1:]) == declared


def _verify_try_callers() -> None:
    """Every ``_try(conn, <sql>)`` caller in the module passes text that can
    write nothing (transaction control naming a savepoint)."""
    module = "swing/trades/cohort_provenance_correction.py"
    calls = [n for n in ast.walk(_module_tree(module))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_try"]
    assert calls
    for call in calls:
        arg = call.args[1]
        assert isinstance(arg, ast.JoinedStr), ast.unparse(arg)
        skeleton = "".join(v.value if isinstance(v, ast.Constant) else HOLE
                           for v in arg.values)
        assert classify(skeleton, TABLES) == (), skeleton


def _verify_corrector_reserves_the_value() -> None:
    from swing.trades.reconciliation_auto_correct import _RESERVED_JOURNAL_FIELDS

    assert ("trades", "entry_intent") in _RESERVED_JOURNAL_FIELDS


def _verify_read_only(key: tuple[str, str]) -> Callable[[], None]:
    """A WITH/SELECT-led read whose holes are column lists / placeholder runs
    (by READ): its literal skeleton names no write verb at all."""
    def check() -> None:
        texts = [t for s in walk_source(
            (REPO_ROOT / key[0]).read_text(encoding="utf-8"), key[0], TABLES)
            if s.key == key for t in s.texts]
        assert texts, key
        for t in texts:
            assert not re.search(r"\b(INSERT|UPDATE|REPLACE|DELETE)\b", t, re.I), t
    return check


_REVIEW_COLUMNS = frozenset({
    "reviewed_at", "mistake_tags", "entry_grade", "management_grade",
    "exit_grade", "process_grade", "disqualifying_process_violation",
    "realized_r_if_plan_followed", "mistake_cost_confidence", "lesson_learned",
    "failure_mode"})

DYNAMIC_SQL_SITES: dict[tuple[str, str], DynamicSite] = {
    MIGRATION_RUNNER: DynamicSite(
        "executescript of a migration file's text (swing/data/migrations/"
        "*.sql); the schema itself. Its row writes are walked from the files "
        "by the same classifier: the only writes carrying a citable field or "
        "entry_intent are the 0014 and 0040 REBUILD identity copies.",
        {"trades": ANY}, _verify_migration_files),
    CORRECTOR: DynamicSite(
        "the AUDITED corrector's field-SET builder (UPDATE {table} SET "
        "{field}); every write carries a reconciliation_corrections row, and "
        "('trades','entry_intent') is RESERVED (N4 layer 2).",
        {"trades": ANY}, _verify_corrector_reserves_the_value),
    REVIEW_BUILDER: DynamicSite(
        "the review-fields builder: SET list assembled from string literals "
        "(10 review fields + failure_mode when the column exists).",
        {"trades": _REVIEW_COLUMNS}, _verify_review_builder),
    ATTESTATION_INSERT: DynamicSite(
        "the ONLY INSERT INTO entry_intent_attestations (CHARC-S3 cond. 1); "
        "column list is the module's _COLUMNS minus the PK.",
        {"entry_intent_attestations": frozenset({
            "trade_id", "assigned_value", "admission_tier", "trade_entry_date",
            "entry_fill_id", "entry_fill_id_at_assignment",
            "entry_broker_order_id", "placement_session",
            "placement_session_source", "admitted_leg", "leg_evidence_json",
            "cited_latch_link_id", "cited_latch_terminal_rung",
            "cited_latch_terminal_session", "cited_latch_probe_json",
            "cited_fields_json", "cited_text_snapshot_json",
            "audit_trail_checked_at", "corrections_touching_cited_fields",
            "outcome_known_at", "reason", "applied_at", "applied_by"})},
        _verify_attestation_insert),
    ("swing/trades/cohort_provenance_correction.py", "_try"): DynamicSite(
        "a cleanup runner taking its SQL as a parameter; its callers pass "
        "ROLLBACK TO / RELEASE of a savepoint only.",
        {}, _verify_try_callers),
    ("swing/data/repos/pattern_detection_events.py",
     "list_observable_detections"): DynamicSite(
        "WITH-led read; holes are the _COLS column list and a placeholder run.",
        {}, _verify_read_only(("swing/data/repos/pattern_detection_events.py",
                               "list_observable_detections"))),
    ("swing/data/repos/pattern_forward_observations.py",
     "get_latest_observations_for_detections"): DynamicSite(
        "WITH-led read; holes are the _COLS column list and a placeholder run.",
        {}, _verify_read_only(("swing/data/repos/pattern_forward_observations.py",
                               "get_latest_observations_for_detections"))),
    ("swing/web/view_models/patterns/review_form.py",
     "_build_outcome_distribution"): DynamicSite(
        "WITH-led read over pattern evaluations; holes are filter fragments "
        "and placeholder runs.",
        {}, _verify_read_only(("swing/web/view_models/patterns/review_form.py",
                               "_build_outcome_distribution"))),
    ("swing/data/repos/schwab_api_calls.py", "list_recent_calls"): DynamicSite(
        "' '.join of a list of SELECT fragments (a SELECT ... FROM "
        "schwab_api_calls head plus AND/ORDER BY clauses) -- a read.",
        {}, None),
}


# --------------------------------------------------------------------------
# planted violations: the instrument sees what it forbids
# --------------------------------------------------------------------------

_PLANTED = '''
def plant_update(conn, tid):
    conn.execute("UPDATE trades SET notes = ? WHERE id = ?", ("x", tid))

def plant_builder(conn, tid, sets):
    sql = "UPDATE trades SET "
    sql += "why_now = ?"
    sql += " WHERE id = ?"
    conn.execute(sql, ("x", tid))

def plant_subquery_set(conn, tid):
    conn.execute("""UPDATE trades SET current_size = (SELECT 1 FROM fills
        WHERE fills.trade_id = ?), thesis = ? WHERE id = ?""", (tid, "x", tid))

def plant_replace(conn, row):
    conn.execute("INSERT OR REPLACE INTO trades (id, emotional_state_pre_trade)"
                 " VALUES (?, ?)", row)

def plant_dynamic(conn, col, tid):
    conn.execute(f"UPDATE trades SET {col} = ? WHERE id = ?", ("x", tid))

def plant_param(conn, sql):
    conn.executescript(sql)

def plant_intent(conn, tid):
    conn.execute("UPDATE trades SET entry_intent = ? WHERE id = ?", ("s", tid))

def plant_attest(conn):
    conn.execute("INSERT INTO entry_intent_attestations (trade_id) VALUES (1)")

def benign(conn, tid, cols):
    conn.execute(f"SELECT {cols} FROM trades WHERE id = ?", (tid,))
    conn.execute("UPDATE trades SET state = ? WHERE id = ?", ("closed", tid))
    conn.execute("SELECT 'UPDATE trades SET notes = 1' -- UPDATE trades SET notes")
'''


def _planted_sites() -> list[Site]:
    return walk_source(_PLANTED, "planted.py", TABLES)


# --------------------------------------------------------------------------
# b22_150 -- F2 S3
# --------------------------------------------------------------------------

def test_no_unaudited_writer_of_the_citable_fields_b22_150() -> None:
    # The instrument FAILS on planted violations (same helpers as below).
    planted = _planted_sites()
    assert {(f, k) for _, f, _, k, _ in _citable_rewrites(planted)} == {
        ("plant_update", "update"), ("plant_builder", "update"),
        ("plant_subquery_set", "update"), ("plant_replace", "replace")}
    assert _uninventoried(planted, DYNAMIC_SQL_SITES) == {
        ("planted.py", "plant_dynamic"), ("planted.py", "plant_param")}
    assert not [s for s in planted if s.function == "benign" and s.writes is None]

    # The real tree.
    sites = _walk_swing()
    assert len(sites) > 500  # the walk reaches the tree (623 at authoring)
    unresolved = {s.key for s in sites if s.writes is None}
    assert unresolved == set(DYNAMIC_SQL_SITES), (
        "new unresolved (inventory it, with a reason):",
        sorted(unresolved - set(DYNAMIC_SQL_SITES)),
        "stale inventory:", sorted(set(DYNAMIC_SQL_SITES) - unresolved))
    for entry in DYNAMIC_SQL_SITES.values():
        if entry.verify is not None:
            entry.verify()
    # No resolved statement rewrites a citable field.
    assert _citable_rewrites(sites) == []
    # No inventoried site can, except the audited corrector and the schema.
    can = {k for k, e in DYNAMIC_SQL_SITES.items()
           if e.writes.get("trades", frozenset()) & (CITABLE | ANY)}
    assert can == {CORRECTOR, MIGRATION_RUNNER}
    # The citable text enters a trade ONLY at capture.
    assert _citable_inserters(sites) == {CAPTURE}


# --------------------------------------------------------------------------
# b22_115 -- the value's write-closure
# --------------------------------------------------------------------------

_VALUE_WRITERS = {
    ("swing/trades/entry_intent_assignment.py", "_set_trades_value"),
    ATTESTATION_INSERT,
    ("swing/data/repos/trades.py", "update_entry_intent"),
    CAPTURE,
    CORRECTOR,
    MIGRATION_RUNNER,
}


def _call_owners(name: str) -> set[str]:
    owners = set()
    for path in sorted(SWING.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                f = node.func
                called = f.id if isinstance(f, ast.Name) else (
                    f.attr if isinstance(f, ast.Attribute) else None)
                if called == name:
                    owners.add(path.relative_to(REPO_ROOT).as_posix())
    return owners


def test_no_other_production_writer_of_the_value_b22_115() -> None:
    planted = _planted_sites()
    assert _value_writers(planted, {}) == {
        ("planted.py", "plant_intent"), ("planted.py", "plant_attest"),
        ("planted.py", "plant_replace")}

    sites = _walk_swing()
    assert _uninventoried(sites, DYNAMIC_SQL_SITES) == set()
    assert _value_writers(sites, DYNAMIC_SQL_SITES) == _VALUE_WRITERS
    # The attestation table is written ONLY by an INSERT (append-only).
    kinds = {(s.key, w.kind) for s in sites for w in (s.writes or ())
             if w.table == "entry_intent_attestations"}
    assert kinds == set()  # its one INSERT is the inventoried repo function
    # The service writes trades.entry_intent and holds no attestation SQL.
    service = [s for s in sites
               if s.module == "swing/trades/entry_intent_assignment.py"]
    assert {(s.function, w.table, w.kind, tuple(sorted(w.columns)))
            for s in service for w in (s.writes or ())} == {
        ("_set_trades_value", "trades", "update", ("entry_intent",))}
    # Callers: the capture INSERT only from the entry service, the
    # attestation INSERT only from the assignment service.
    assert _call_owners("insert_trade_with_event") == {"swing/trades/entry.py"}
    assert _call_owners("insert_attestation") == {
        "swing/trades/entry_intent_assignment.py"}


# --------------------------------------------------------------------------
# b22_151 -- F3: death-then-fill is expressible
# --------------------------------------------------------------------------

_FIRE = FireRow(
    candidate_id=9500, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
    initial_stop=14.88, action_session_date="2026-07-20",
    run_ts="2026-07-17T17:30:05", pipeline_run_id=135)
_DEATH = date(2026, 7, 21)


def _derive(fill_session: date, *, candidate_id: int | None):
    """Invalidation close (14.87 < 14.88) on _DEATH; an in-zone same-ticker
    entry (18.40) on ``fill_session``."""
    bars = [DailyBar(session=_DEATH, open=15.0, high=15.2, low=14.1, close=14.87)]
    entry = EntryRecord(trade_id=88, ticker="FTRE", entry_date=fill_session,
                        candidate_id=candidate_id, entry_price=18.40, shares=3)
    d = derive_latches(
        fires=[_FIRE], bars_by_ticker={"FTRE": bars},
        entries_by_ticker={"FTRE": [entry]},
        horizon_session=date(2026, 7, 24), derivation_session=date(2026, 7, 23))
    assert len(d.latches) == 1
    return d.latches[0]


def test_death_then_fill_is_expressible_b22_151() -> None:
    later = date(2026, 7, 22)
    for candidate_id in (None, 9500):  # the windowed rung and the exact rung
        latch = _derive(later, candidate_id=candidate_id)
        assert (latch.clear_reason, latch.clear_session, latch.clear_trade_id) == (
            "invalidation", _DEATH, None), candidate_id
        # The same-session twin: R6 tie -> fill.
        twin = _derive(_DEATH, candidate_id=candidate_id)
        assert (twin.clear_reason, twin.clear_session, twin.clear_trade_id) == (
            "fill", _DEATH, 88), candidate_id
