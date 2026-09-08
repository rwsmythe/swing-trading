"""22-A4 -- the THREE observations, and clause 2's settlement rows.

**TASK 3 SHIPPED (k), (k2), (k3a), (k5), (k6a)-(k6b) and (k7a)-(k7b).**  Every
row there asserts something an assertion IN THAT TASK can distinguish from the
naive substitute the plan names for it -- the scheduling rule Task 3 was
written against.

**TASK 4 ADDS THE ROWS THAT ASSERT WHAT ``record_entry`` DOES WITH THOSE
OBSERVATIONS** -- (k3b), (k4a), (k4b), (RD-a1), (RD-a2), (RD-a3), (RD-a4),
(RD-a5), (RD-b), (RD-b2), (c2) and (pr1)-(pr5) -- **and the assertions
deferred out of Task 3 into rows it already shipped**: (k3a)'s ordering half
and the probe-call-count-of-ZERO on (k2), (k7a) and (k7b).  Every one of them
was excluded from Task 3 for a SINGLE reason: it names ``_durability_probe``
or ``_settle_by_attempt_identity``, which did not exist there.

**THE PROXY SHAPE IS PART OF THE ROW, NOT A NOTE ABOUT IT.**  The commit-fail
arm of ``sqlite3.Connection.__exit__`` cannot be driven natively, so the
deferred-path rows use a connection PROXY whose ``__exit__`` stands in for
CPython's -- and a proxy that does not reproduce the chaining tests the proxy
rather than the code.  ``_ExitRollbackAlsoFails`` therefore raises the rollback
error from INSIDE the ``except`` handling the commit error, so ``__context__``
is set by the interpreter exactly as ``_PyErr_ChainExceptions1`` sets it; every
row using it asserts that chaining on the fixture itself before asserting
anything about the production code.
"""
from __future__ import annotations

import ast
import json
import logging
import sqlite3
import sys
from pathlib import Path

import pytest

from swing.data.db import (
    DEFAULT_BUSY_TIMEOUT_MS,
    EXPECTED_SCHEMA_VERSION,
    _resolve_main_db_path,
    ensure_schema,
    open_connection,
    run_migrations,
)
from swing.trades import entry as entry_mod
from swing.trades.entry import (
    EntryRequest,
    _CommitOutcome,
    _entry_transaction,
    record_entry,
)
from swing.trades.origin import EntryPath

SOFT, HARD = 8, 12
EVENT_TS = "2026-09-07T09:30:00"
TICKER = "AAA"


def _req(**over) -> EntryRequest:
    fields = dict(
        ticker=TICKER, entry_date="2026-09-07", entry_price=18.50, shares=2,
        initial_stop=14.00, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None, rationale="vcp_breakout",
        event_ts=EVENT_TS, entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="the mandate fired", why_now="through the pivot",
        invalidation_condition="break of the stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small",
        event_risk_present=0, event_handling="not_applicable",
        gap_risk_present=0, gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm"]', market_regime="Bullish",
        catalyst="technical_only", manual_entry_confidence="normal",
        fill_origin="operator_typed", schwab_source_value_json=None,
    )
    fields.update(over)
    return EntryRequest(**fields)


def _capture_outcomes(monkeypatch) -> list:
    """Hand back every ``_CommitOutcome`` ``record_entry`` builds.

    The observations are written onto an object the function creates for
    itself, so a row asserting them has to reach it.  A FACTORY is patched in
    rather than the class, because the real class is what must be
    constructed -- a stand-in would assert the harness's fields, not the
    shipped ones.
    """
    made: list = []

    def _factory():
        outcome = _CommitOutcome()
        made.append(outcome)
        return outcome

    monkeypatch.setattr(entry_mod, "_CommitOutcome", _factory)
    return made


def _probe_calls(monkeypatch, result=None) -> list:
    """Replace ``_durability_probe`` with a call-RECORDING sentinel.

    **THE CALL COUNT IS THE INSTRUMENT, NOT THE OUTCOME.**  Rule (i) --
    *a connection whose rollback RAISED is discarded and NO read is attempted
    on it* -- is a statement about whether the read HAPPENS, and on most of
    these fixtures the refused read would have answered ABSENT anyway.  So an
    implementation with no refusal at all produces the SAME caller-facing
    outcome and is visible only here.

    ``*args`` rather than named parameters on purpose: these rows are about
    WHETHER the probe ran and WITH WHICH TOKEN, and pinning the whole
    signature in nine fixtures would make one production change red in nine
    places for no added discrimination.
    """
    calls: list = []

    def _sentinel(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(entry_mod, "_durability_probe", _sentinel)
    return calls


# ===========================================================================
# THE DEFERRED-PATH PROXIES.  Both stand in for
# `pysqlite_connection_exit_impl`'s commit-fail branch; they differ in whether
# the rollback CPython runs there succeeds or fails.
# ===========================================================================
class _ExitCommitFailsRollbackOK:
    """``__exit__``'s commit fails; its rollback SUCCEEDS.

    CPython restores the COMMIT's exception through ``PyErr_SetRaisedException``
    -- so its ``__context__`` is whatever the THREAD was already handling, and
    the raise here is deliberately NOT inside an ``except`` block, because a
    Python re-raise from inside one would set ``__context__`` to the exception
    being handled and reproduce the WRONG arm.
    """

    def __init__(self, conn: sqlite3.Connection,
                 commit_error: BaseException) -> None:
        self._conn = conn
        self._commit_error = commit_error
        self.rollback_calls = 0
        self.rollback_calls_at_exit_return = -1

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._conn.rollback()

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            return self._conn.__exit__(exc_type, exc, tb)
        self.rollback()
        self.rollback_calls_at_exit_return = self.rollback_calls
        raise self._commit_error


class _ExitRollbackAlsoFails:
    """``__exit__``'s commit fails AND its rollback fails.

    The rollback error is raised from INSIDE the ``except`` handling the commit
    error, so the interpreter sets ``__context__`` exactly as
    ``_PyErr_ChainExceptions1`` does in the branch this fixture is derived
    from.  ``perform_rollback`` chooses between the took-effect-then-raised
    sequence and the raised-before-taking-effect one.
    """

    def __init__(self, conn: sqlite3.Connection,
                 rollback_error: BaseException, *,
                 perform_rollback: bool = True) -> None:
        self._conn = conn
        self._rollback_error = rollback_error
        self._perform_rollback = perform_rollback
        self.commit_error: BaseException | None = None
        self.rollback_calls = 0
        self.rollback_calls_at_exit_return = -1

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._conn.rollback()

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            return self._conn.__exit__(exc_type, exc, tb)
        try:
            raise sqlite3.OperationalError("commit failed (planted)")
        except sqlite3.OperationalError as commit_error:
            self.commit_error = commit_error
            if self._perform_rollback:
                self.rollback()
            self.rollback_calls_at_exit_return = self.rollback_calls
            raise self._rollback_error


def _fresh_rows(db_path: Path, ticker: str = TICKER) -> int:
    fresh = sqlite3.connect(db_path)
    try:
        return fresh.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker = ?",
            (ticker,)).fetchone()[0]
    finally:
        fresh.close()


# ===========================================================================
# (k3a) STATIC -- the `A4-R1-3` window is closed on BOTH branches, in the
# places the two branches close it, and the pre-arc gate IS SPLIT.
# ===========================================================================
def _entry_tree() -> ast.Module:
    src = Path(entry_mod.__file__).read_text(encoding="utf-8")
    return ast.parse(src)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is not in the module")


def _assigns_attr(node: ast.AST, owner: str, attr: str) -> bool:
    return any(
        isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Attribute) and t.attr == attr
            and isinstance(t.value, ast.Name) and t.value.id == owner
            for t in n.targets)
        for n in ast.walk(node))


def _is_assign_to(node: ast.AST, owner: str, attr: str) -> bool:
    return (isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr == attr
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == owner)


def _body_guards(root: ast.AST, target: ast.AST) -> list[str]:
    """The tests of every ``If`` whose BODY (never its ``orelse``) contains
    ``target``, outermost first."""
    found: list[str] = []

    def walk(node: ast.AST, stack: list[str]) -> bool:
        if node is target:
            found.extend(stack)
            return True
        for field, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for child in children:
                if not isinstance(child, ast.AST):
                    continue
                deeper = stack
                if isinstance(node, ast.If) and field == "body":
                    deeper = [*stack, ast.unparse(node.test)]
                if walk(child, deeper):
                    return True
        return False

    walk(root, [])
    return found


def test_k3a_the_window_is_closed_on_both_branches_and_the_gate_is_split(
) -> None:
    """**THE BYTE-LOCK, ASSERTED RATHER THAN PROMISED.**

    Three separate sections of this arc's plan claimed ``_entry_transaction``'s
    ``if not immediate:`` branch is untouched while its own pseudocode
    contradicted them.  This row is that claim as a test, and it has three
    parts because the window is closed in three different places:

      * the IMMEDIATE branch closes it with a ``try`` whose handler both
        writes ``outcome.resolution`` and re-raises -- so an assignment
        OUTSIDE that ``try``, or inside a nested decoy whose handler records
        no resolution, fails;
      * the DEFERRED branch closes it ONE FRAME OUT, so the branch itself
        must contain NO ``Try`` at all and its ``with conn:`` suite must be
        exactly ``yield``;
      * ``record_entry`` takes the deferred observation under a branch
        guarded by ``not outcome.committed`` and ``not _reserve``, AFTER the
        ``result is None`` raise -- which is reachable only because this task
        SPLITS the shipped ``if result is None or not outcome.committed``
        gate into two branches that both re-raise.
    """
    tree = _entry_tree()
    fn = _function(tree, "_entry_transaction")

    deferred = [
        s for s in fn.body
        if isinstance(s, ast.If) and isinstance(s.test, ast.UnaryOp)
        and isinstance(s.test.op, ast.Not)
        and isinstance(s.test.operand, ast.Name)
        and s.test.operand.id == "immediate"]
    assert len(deferred) == 1, "the `if not immediate:` arm moved or split"
    arm = deferred[0]

    # ---- THE DEFERRED BRANCH IS NOT EDITED AT ALL ----
    assert not [n for n in ast.walk(arm) if isinstance(n, ast.Try)], (
        "the deferred branch grew a `try` -- the one suite this arc promises "
        "is byte-identical")
    withs = [n for n in ast.walk(arm) if isinstance(n, ast.With)]
    assert len(withs) == 1
    assert all(item.optional_vars is None for item in withs[0].items), (
        "an `as` binding was added to `with conn:`")
    suite = withs[0].body
    assert len(suite) == 1 and isinstance(suite[0], ast.Expr), (
        f"`with conn:`'s suite is no longer one statement: "
        f"{[ast.unparse(s) for s in suite]}")
    assert isinstance(suite[0].value, ast.Yield), (
        "`with conn:`'s suite is no longer a bare `yield`")
    assert suite[0].value.value is None, "the `yield` gained a value"

    # ---- THE IMMEDIATE BRANCH: the assignment sits in a RESOLVING try ----
    immediate_arm = fn.body[fn.body.index(arm) + 1:]
    committed_assigns = [
        n for stmt in immediate_arm for n in ast.walk(stmt)
        if _is_assign_to(n, "outcome", "committed")]
    assert committed_assigns, "no `outcome.committed` assignment on the " \
                              "immediate branch"
    for assign in committed_assigns:
        holders = [
            n for stmt in immediate_arm for n in ast.walk(stmt)
            if isinstance(n, ast.Try) and any(s is assign for s in n.body)]
        assert len(holders) == 1, (
            "`outcome.committed = True` is not directly inside exactly one "
            "`try` body -- the `A4-R1-3` window is open on the immediate path")
        handlers = [
            h for h in holders[0].handlers
            if _assigns_attr(h, "outcome", "resolution")
            and any(isinstance(s, ast.Raise) and s.exc is None
                    for s in h.body)]
        assert handlers, (
            "the `try` holding `outcome.committed = True` has no handler that "
            "BOTH records a resolution and re-raises")

    # ---- RECORD_ENTRY'S HALF: the gate is split, and the observation is
    #      under `not outcome.committed` and `not _reserve` ----
    re_fn = _function(tree, "record_entry")
    tries = [s for s in re_fn.body if isinstance(s, ast.Try)]
    assert len(tries) == 1, "the guarded region is no longer one `try`"
    handler = tries[0].handlers[0]

    first = handler.body[0]
    assert isinstance(first, ast.If), "the handler no longer opens with a gate"
    assert not isinstance(first.test, ast.BoolOp), (
        "the pre-arc gate still carries its `or` -- there is no "
        "`not outcome.committed` branch for the observation to sit under")
    assert ast.unparse(first.test) == "result is None"
    assert (len(first.body) == 1 and isinstance(first.body[0], ast.Raise)
            and first.body[0].exc is None), (
        "the `result is None` branch no longer re-raises bare")
    assert not first.orelse

    reads = [
        n for n in ast.walk(handler)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_read_resolution"]
    assert len(reads) == 1, (
        "the deferred observation is missing, or is taken more than once")
    assert _body_guards(handler, reads[0]) == [
        "not outcome.committed", "not _reserve"], (
        "the deferred observation is not guarded by BOTH the "
        "commit-not-observed branch and the deferred-path branch")

    # ---- TASK 4'S HALF: THE OBSERVATION IS LEXICALLY BEFORE THE SETTLE ----
    # This could not be written in Task 3 and would have PASSED VACUOUSLY
    # there: an AST walk that finds no `_settle_by_attempt_identity` node
    # finds no ordering to violate and reports success.  The `== 1` below is
    # what makes the ordering assertion non-vacuous -- the failure mode of
    # scheduling-by-artifact is not always a red test.
    settles = [
        n for n in ast.walk(handler)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_settle_by_attempt_identity"]
    assert len(settles) == 1, (
        "the settle is missing from the handler, or is consulted more than "
        "once -- and a missing call makes the ordering assertion below "
        "VACUOUS rather than red")
    assert reads[0].lineno < settles[0].lineno, (
        "the gate is consulted BEFORE the resolution is observed: "
        "`resolution` would still read \"unattempted\", the gate would "
        "refuse, and a DURABLE entry would be reported as a failure -- the "
        "`A4-R1-3` defect relocated rather than fixed")


# ===========================================================================
# (k) THE DEFERRED PATH OBSERVES ITS OWN RESOLUTION -- it does not perform it
# ===========================================================================
def test_k_the_deferred_path_observes_its_own_resolution(
        tmp_path: Path, monkeypatch) -> None:
    """A ``_CommitNeverLands``-shaped failure on the PRE-ARC path.

    ``sqlite3.Connection.__exit__`` already rolls back when its own commit
    fails, so ``in_transaction`` reads False on both trees and **the
    discriminator is the OBSERVATION, not the connection state** -- the
    connection state was never this arc's to fix on that path.

    ``resolution == "not_needed"`` is also the proof that ``result is not
    None``: the observation lives AFTER the ``result is None`` raise, so a
    body that never finished leaves the field at ``"unattempted"``.
    """
    db_path = tmp_path / "k.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        lost = sqlite3.OperationalError("database is locked (planted)")
        proxy = _ExitCommitFailsRollbackOK(conn, lost)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        assert caught.value is lost, "the ORIGINAL exception did not propagate"
        assert proxy.rollback_calls == 1, (
            "the fixture's own premise: `__exit__` rolled back")
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.committed is False
        assert outcome.resolution == "not_needed"
        assert outcome.cleanup_raised is False
        assert conn.in_transaction is False
        assert _fresh_rows(db_path) == 0, "something partial is durable"
    finally:
        conn.close()


# ===========================================================================
# (k2) THE DEFERRED PATH'S EXCEPTION IDENTITY IS UNCHANGED -- a LOCK
# ===========================================================================
def test_k2_the_deferred_paths_exception_identity_is_unchanged(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """**THE DISCRIMINATING ASSERTION IS ``cleanup_raised is True``**; the
    other three are LOCKS -- they pass pre-fix, and they fail an
    implementation that copies the immediate path's ``raise cleanup_error
    from write_error`` onto the deferred path, or that keeps a retry rollback
    arm there.

    Task 4 ADDS the probe-call-count-of-ZERO assertion to this row, where the
    sentinel it patches exists.
    """
    db_path = tmp_path / "k2.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        rollback_error = sqlite3.OperationalError("rollback failed (planted)")
        proxy = _ExitRollbackAlsoFails(conn, rollback_error)

        with caplog.at_level(logging.DEBUG, logger="swing.trades.entry"):
            with pytest.raises(sqlite3.OperationalError) as caught:
                record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                             force=False, cfg=None)

        escaping = caught.value
        # THE FIXTURE'S OWN CHAINING, ASSERTED BEFORE ANYTHING ELSE.
        assert type(escaping.__context__) is sqlite3.OperationalError, (
            "the proxy stopped chaining, so every assertion below would be "
            "measuring the fixture rather than the code")

        assert escaping is rollback_error
        assert type(escaping) is sqlite3.OperationalError
        assert escaping.args == ("rollback failed (planted)",)
        assert escaping.__cause__ is None, (
            "the deferred path added a `raise ... from ...` of its own")
        assert escaping.__context__ is proxy.commit_error

        assert outcomes[0].cleanup_raised is True

        assert proxy.rollback_calls == proxy.rollback_calls_at_exit_return, (
            "the deferred path issued a rollback of its own AFTER `__exit__` "
            "returned -- `__exit__` owns this path's rollback")
        assert [r for r in caplog.records
                if r.name == "swing.trades.entry"] == [], (
            "the deferred observation emitted a log record; the rollback's "
            "failure is already what escaped")

        # TASK 4'S ADDED ASSERTION.  The rollback RAISED, so rule (i) refuses
        # the read outright -- and because the refused read would have
        # answered ABSENT here anyway, the count is the ONLY place an
        # implementation without the refusal differs.
        assert probed == [], (
            f"the probe ran on a connection whose rollback raised: {probed}")
    finally:
        conn.close()


# ===========================================================================
# (k5) THE CHAINED SIGNAL IS DETECTED -- Task 3's discriminator for
# `_exit_rollback_failed`, with NO probe
# ===========================================================================
def test_k5_the_chained_signal_is_detected(
        tmp_path: Path, monkeypatch) -> None:
    """``_exit_rollback_failed`` ships in Task 3 and every OTHER row touching
    it also asserts a probe call count, so without this row Task 3 would go
    green against ``def _exit_rollback_failed(...): return False``.

    **Against ``return False``:** ``cleanup_raised`` is False with
    ``resolution == "not_needed"`` -- the ``A4-R9-3`` admitting state, which
    in Task 4 becomes a live false-confirm window.  Since the deferred path
    has no rollback arm at all, the flag can only have come from the chained
    exception, which makes this a property of the CODE and not of the fixture.
    """
    db_path = tmp_path / "k5.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        proxy = _ExitRollbackAlsoFails(
            conn, sqlite3.OperationalError("rollback failed (planted)"))

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        assert type(caught.value.__context__) is sqlite3.OperationalError, (
            "the fixture's own chaining")
        outcome = outcomes[0]
        assert outcome.cleanup_raised is True, (
            "the chained rollback failure was not detected")
        assert outcome.resolution == "not_needed", (
            "the rollback took effect, so the physical state is resolved")
        assert conn.in_transaction is False
        assert _fresh_rows(db_path) == 0
    finally:
        conn.close()


# ===========================================================================
# (k6a)-(k6b) THE IMMEDIATE PATH'S OBSERVATIONS, WITH NO PROBE AND NO
# `record_entry` -- driven through `_entry_transaction`'s own contract.
# ===========================================================================
class _RollbackReturnsWithoutEffect:
    """``commit()`` raises without landing; ``rollback()`` RETURNS NORMALLY
    while leaving the transaction open.

    **``__getattr__`` was added in Task 4 so (RD-a1) can drive this SAME
    proxy through ``record_entry``** rather than through
    ``_entry_transaction`` alone.  Every attribute (k6a) uses is still
    defined explicitly above it, so (k6a) is unchanged by the addition.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rollback_calls = 0

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
        self.rollback_calls += 1

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


class _RollbackTakesEffectThenRaises:
    """``commit()`` raises without landing; ``rollback()`` performs the REAL
    rollback and THEN raises.

    This is (RD-a1) shape **(b)** -- ``_CommitNeverLands``'s commit half with
    ``_RollbackAfterEffect``'s rollback half.  The existing
    ``_RollbackAfterEffect`` cannot serve: its ``commit()`` commits normally
    and returns, so ``record_entry`` succeeds and the raising ``rollback()``
    is never reached.  ``__getattr__`` was added in Task 4 for the reason
    given on the proxy above.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rolled = False
        self.rollback_calls = 0

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._conn.rollback()
        self.rolled = True
        raise sqlite3.OperationalError("rollback raised AFTER taking effect")

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


_PLANT = (
    "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
    "action_session_date, tickers_evaluated, aplus_count, watch_count, "
    "skip_count, excluded_count, error_count) VALUES "
    "(9301, '2026-09-07T17:30:05', '2026-09-07', '2026-09-08', 1, 0, 0, 1, "
    "0, 0)")


def test_k6a_a_rollback_that_returns_without_taking_effect(
        tmp_path: Path) -> None:
    """**Against the naive substitute** -- assigning ``"rolled_back"``
    whenever ``rollback()`` returns -- ``resolution`` reads ``"rolled_back"``,
    which in Task 4 ADMITS the probe under a falsely clean label.  The field
    contract says *re-read from ``conn.in_transaction`` after ANY rollback
    attempt*, and the returning arm is the one where a naive implementation
    infers it instead.
    """
    conn = ensure_schema(tmp_path / "k6a.db")
    try:
        proxy = _RollbackReturnsWithoutEffect(conn)
        outcome = _CommitOutcome()

        with pytest.raises(sqlite3.OperationalError) as caught:
            with _entry_transaction(proxy, immediate=True, outcome=outcome):
                proxy.execute(_PLANT)

        assert str(caught.value) == "commit failed (planted)", (
            "the write error did not propagate unchanged")
        assert caught.value.__cause__ is None
        assert proxy.rollback_calls == 1, "the rollback was never attempted"
        assert conn.in_transaction is True, (
            "the fixture's own premise: the rollback did NOT take effect")
        assert outcome.resolution == "still_open"
        assert outcome.cleanup_raised is False
        assert outcome.committed is False
    finally:
        conn.rollback()
        conn.close()


def test_k6b_a_rollback_that_took_effect_and_then_raised(
        tmp_path: Path, caplog) -> None:
    """``cleanup_raised`` and ``resolution`` are TWO FACTS and this row
    asserts both: the CALL raised, and the TRANSACTION is resolved.

    **Against a naive substitute that infers the state from the raise**
    (``"still_open"``, or the first draft's ``"unresolved"``) the resolution
    assertion fails on a transaction that is resolved.  **AND against routing
    the immediate path through a shared helper that CONTAINS its rollback
    failure**, the escaping exception would be the WRITE error with no
    ``__cause__`` -- which is the assertion that makes *"the shared thing is
    the non-mutating read, never the rollback"* a test rather than a
    paragraph.  That chained-escape half passes pre-fix and is a LOCK.
    """
    conn = ensure_schema(tmp_path / "k6b.db")
    try:
        proxy = _RollbackTakesEffectThenRaises(conn)
        outcome = _CommitOutcome()

        with caplog.at_level(logging.ERROR, logger="swing.trades.entry"):
            with pytest.raises(sqlite3.OperationalError) as caught:
                with _entry_transaction(
                        proxy, immediate=True, outcome=outcome):
                    proxy.execute(_PLANT)

        assert proxy.rolled, "the planted rollback never took effect"
        assert conn.in_transaction is False, (
            "the fixture's own premise: the rollback DID take effect")
        assert str(caught.value) == "rollback raised AFTER taking effect"
        assert isinstance(caught.value.__cause__, sqlite3.OperationalError)
        assert str(caught.value.__cause__) == "commit failed (planted)", (
            "`raise cleanup_error from write_error` was lost")
        assert outcome.cleanup_raised is True
        assert outcome.resolution == "rolled_back"
        assert any("TOOK EFFECT" in r.getMessage() for r in caplog.records), (
            "the existing took-effect cleanup message is gone")
    finally:
        conn.close()


# ===========================================================================
# (k7a)-(k7b) THE SUBCLASS-DESCRIPTOR ROWS -- the base-slot read's Task-3
# discriminator, in the task that SHIPS `_CONTEXT_SLOT`.
# ===========================================================================
class _LyingContext(sqlite3.OperationalError):
    """``__context__`` is a data descriptor that returns ``None``."""

    @property
    def __context__(self):  # type: ignore[override]
        return None


class _RaisingContext(sqlite3.OperationalError):
    """``__context__`` is a data descriptor that RAISES."""

    @property
    def __context__(self):  # type: ignore[override]
        raise RuntimeError("22-A4 PROBE: the __context__ getter raised")


def test_k7a_a_context_descriptor_that_lies_is_still_detected(
        tmp_path: Path, monkeypatch) -> None:
    """**Against the bare attribute read:** ``cleanup_raised`` is False -- a
    FALSE NEGATIVE, and in Task 4 that state ADMITS the probe and rebuilds the
    ``A4-R9-3`` window.  ``escaping.__context__`` is an ORDINARY attribute
    lookup and a subclass data descriptor reads whatever it likes; the base
    getset descriptor runs no user code, which is the whole reason it is the
    read.
    """
    db_path = tmp_path / "k7a.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        hostile = _LyingContext("rollback failed (planted)")
        proxy = _ExitRollbackAlsoFails(conn, hostile)

        with pytest.raises(_LyingContext) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        escaping = caught.value
        # THE FIXTURE ASSERTS THE DIVERGENCE IT EXISTS TO EXERCISE, so a
        # future CPython that closed the hole turns this row RED instead of
        # vacuously green.
        assert escaping.__context__ is None, "the hostile getter did not fire"
        assert BaseException.__dict__["__context__"].__get__(
            escaping, type(escaping)) is proxy.commit_error, (
            "the real commit error is not in the base slot, so this row is "
            "not exercising the divergence")

        assert outcomes[0].cleanup_raised is True
        assert outcomes[0].resolution == "not_needed"
        # TASK 4'S ADDED ASSERTION: under the bare attribute read the lying
        # getter makes `cleanup_raised` False, which ADMITS the probe and
        # rebuilds the `A4-R9-3` window.  The count is where that is visible.
        assert probed == [], (
            f"a FALSE-NEGATIVE detection admitted the probe: {probed}")
    finally:
        conn.close()


def test_k7b_a_context_descriptor_that_raises_does_not_replace_the_evidence(
        tmp_path: Path, monkeypatch) -> None:
    """**The discriminating assertion is the SECOND one.**  Against the bare
    attribute read the getter fires, its ``RuntimeError`` propagates, and the
    operator's evidence about what actually failed has been replaced by the
    hostile exception; ``cleanup_raised`` alone cannot distinguish the two
    implementations here, because the bare read never returns at all.

    *What this row does NOT prove: the base descriptor runs no user code, so
    the getter never fires under the shipped read and the ALARM-direction
    ``except`` arm in ``_exit_rollback_failed`` is NOT exercised by it.*
    """
    db_path = tmp_path / "k7b.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        hostile = _RaisingContext("rollback failed (planted)")
        proxy = _ExitRollbackAlsoFails(conn, hostile)

        # **`BaseException` ON PURPOSE, and the type is asserted BELOW
        # instead.**  Under the bare attribute read the getter's
        # ``RuntimeError`` is what escapes, carrying the hostile object in its
        # own ``__context__`` -- and pytest's traceback formatter walks
        # ``__context__``, so an un-caught escape turns this row's failure
        # into a session-aborting INTERNALERROR instead of a readable red.
        # Catching broadly and asserting identity keeps the discrimination
        # and makes the naive substitute fail as an ordinary assertion.
        with pytest.raises(BaseException) as caught:  # noqa: B017
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        escaping = caught.value
        assert escaping is hostile, (
            "what escaped is not the exception `__exit__` produced -- the "
            "hostile getter replaced the operator's evidence")
        assert type(escaping) is _RaisingContext
        assert escaping.args == ("rollback failed (planted)",)
        with pytest.raises(RuntimeError, match="the __context__ getter"):
            escaping.__context__  # noqa: B018 -- the fixture's own premise
        assert BaseException.__dict__["__context__"].__get__(
            escaping, type(escaping)) is proxy.commit_error

        assert outcomes[0].cleanup_raised is True
        # TASK 4'S ADDED ASSERTION, for (k7a)'s reason.
        assert probed == [], (
            f"the probe ran despite a rollback failure: {probed}")
    finally:
        conn.close()


# ===========================================================================
# ================== TASK 4 -- CLAUSE 2 RETURNS =============================
#
# Everything below this line ships in Task 4.  Every row names
# `_durability_probe` or `_settle_by_attempt_identity`, which is the SINGLE
# reason each was excluded from Task 3.
# ===========================================================================
TOK = "00000000-0000-4000-8000-0000000004a4"
OTHER_TICKER = "ZZZ"

# THE IMMEDIATE PATH IS SELECTED BY THE ENVELOPE, NOT BY A KEYWORD.
# `record_entry` takes `immediate=True` when the request's envelope NAMES a
# usable order id -- and that is the only path on which `_entry_transaction`
# calls `conn.commit()` / `conn.rollback()` ITSELF, so a connection proxy
# overriding those two methods is reached ONLY there.  On the deferred path
# `sqlite3.Connection.__exit__` owns both, which is why the deferred rows use
# an `__exit__`-shaped proxy instead.
_ORDER_ENVELOPE = json.dumps({
    "schwab_order_id": "22a4-order-1",
    "schwab_instrument_symbol": TICKER,
    "entry_date": "2026-09-07", "entry_price": 18.50, "shares": 2})


def _immediate_req(**over) -> EntryRequest:
    return _req(schwab_source_value_json=_ORDER_ENVELOPE,
                fill_origin="schwab_auto", **over)


def _pin_token(monkeypatch, token: str = TOK) -> str:
    """Plant a KNOWN token so a row can assert what the probe was handed."""
    monkeypatch.setattr(entry_mod, "_mint_attempt_token", lambda: token)
    return token


def _probe_spy(monkeypatch) -> list:
    """Record every ``_durability_probe`` call while still running the REAL
    probe -- for the rows that assert the COUNT and the settled OUTCOME
    together.  ``_probe_calls`` replaces the probe; this one watches it."""
    calls: list = []
    real = entry_mod._durability_probe

    def _spy(*args):
        calls.append(args)
        return real(*args)

    monkeypatch.setattr(entry_mod, "_durability_probe", _spy)
    return calls


class _ExitCommitsThenRaises:
    """THE (c) SHAPE ON THE DEFERRED PATH: ``__exit__`` performs the REAL
    commit and only then raises, so the commit's own RETURN is lost while the
    row is DURABLE.

    A proxy that raised INSTEAD of committing would be a different case
    entirely (that is ``_ExitCommitFailsRollbackOK``).  The real ``__exit__``
    is delegated to first, so ``outcome.committed`` is never reached and
    ``record_entry`` sees exactly what an interrupt landing on the commit's
    own return looks like.
    """

    def __init__(self, conn: sqlite3.Connection, exc: BaseException) -> None:
        self._conn = conn
        self._exc = exc
        self.committed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._conn.__exit__(exc_type, exc, tb)
        if exc_type is None:
            self.committed = True
            raise self._exc
        return False


class _RollbackRaisesWithoutEffect:
    """(RD-a1) SHAPE (a) / (RD-a3): ``commit()`` raises without landing and
    ``rollback()`` raises BEFORE taking effect, so the writer's transaction
    stays OPEN with the entry row PENDING."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rollback_calls = 0

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
        self.rollback_calls += 1
        raise sqlite3.OperationalError("rollback failed before taking effect")

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


_PLANT_TRADE = (
    "INSERT INTO trades (id, ticker, entry_date, entry_price, initial_shares, "
    "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at, "
    "attempt_id) VALUES (?, ?, '2026-09-07', 10.0, 1, 9.0, 9.0, 'entered', "
    "'manual_off_pipeline', '2026-09-07T16:00:00', ?)")


def _plant_committed_trade(db_path: Path, ticker: str,
                           attempt_id: str | None,
                           at_id: int | None = None) -> int:
    """Commit a trade row from a SECOND connection.

    A raw INSERT rather than the repo writer: these rows exist to reproduce a
    CONSEQUENCE (a rowid reissued to somebody else, an RNG token collision),
    and routing them through the production writer would make the fixture
    depend on the very thing under test.
    """
    second = sqlite3.connect(db_path)
    try:
        with second:
            cur = second.execute(_PLANT_TRADE, (at_id, ticker, attempt_id))
        return int(cur.lastrowid)
    finally:
        second.close()


# ===========================================================================
# (RD-a1) THE PROBE IS NOT CALLED WHEN THE ROLLBACK RAISED -- three fixtures,
# because a rollback can fail in TWO ways and RETURN-WITHOUT-EFFECT in a third
# ===========================================================================
def test_RD_a1_shape_a_a_rollback_that_RAISED_before_taking_effect(
        tmp_path: Path, monkeypatch) -> None:
    """RD's rule (i) -- *if the rollback itself raises, the connection is
    DISCARDED and NO read is attempted on it* -- closed by an ASSERTION rather
    than by the comment R10-02's own site carried while the next line walked
    past it.

    **Pre-fix (the naive implementation this excludes -- one that probes
    whenever the commit is lost):** the count is 1.
    """
    conn = ensure_schema(tmp_path / "rda1a.db")
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        proxy = _RollbackRaisesWithoutEffect(conn)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value) == "rollback failed before taking effect"
        assert str(caught.value.__cause__) == "commit failed (planted)", (
            "`raise cleanup_error from write_error` was lost")
        assert proxy.rollback_calls == 1, "the rollback was never attempted"
        assert conn.in_transaction is True, (
            "the fixture's own premise: the rollback did NOT take effect")

        outcome = outcomes[0]
        assert outcome.committed is False
        assert outcome.cleanup_raised is True
        assert outcome.resolution == "still_open"
        assert probed == [], (
            f"a read was attempted on a connection whose rollback raised: "
            f"{probed}")
    finally:
        conn.rollback()
        conn.close()


def test_RD_a1_shape_b_a_rollback_that_took_effect_and_THEN_raised(
        tmp_path: Path, monkeypatch) -> None:
    """**THE ROW THAT PROVES THE GATE READS BOTH FIELDS** rather than
    inferring one from the other: the transaction is RESOLVED
    (``resolution == "rolled_back"``) and the read is refused anyway, because
    the CALL raised.  That is rule (i) taken literally.

    **Against the first draft's single-field gate:** this shape would be
    labelled ``"unresolved"`` on a resolved transaction, so the state model
    would be wrong even where the outcome happened to be right.
    """
    db_path = tmp_path / "rda1b.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        proxy = _RollbackTakesEffectThenRaises(conn)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value) == "rollback raised AFTER taking effect"
        assert str(caught.value.__cause__) == "commit failed (planted)"
        assert proxy.rolled, "the planted rollback never took effect"
        assert conn.in_transaction is False, (
            "the fixture's own premise: the transaction IS resolved")

        outcome = outcomes[0]
        assert outcome.cleanup_raised is True
        assert outcome.resolution == "rolled_back"
        assert probed == [], (
            f"the read was admitted on a resolved transaction whose rollback "
            f"call RAISED: {probed}")
        assert _fresh_rows(db_path) == 0
    finally:
        conn.close()


def test_RD_a1_shape_c_a_rollback_that_RETURNED_without_taking_effect(
        tmp_path: Path, monkeypatch) -> None:
    """The arm no earlier fixture covered.

    **Against the pseudocode this replaces**, which assigned ``"rolled_back"``
    whenever the call RETURNED: the resolution is misclassified and **the
    probe is ADMITTED** -- a read let in under a falsely clean label, on a
    transaction that is still open and whose row is still pending.
    """
    conn = ensure_schema(tmp_path / "rda1c.db")
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        proxy = _RollbackReturnsWithoutEffect(conn)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value) == "commit failed (planted)"
        assert caught.value.__cause__ is None
        assert proxy.rollback_calls == 1
        assert conn.in_transaction is True, (
            "the fixture's own premise: the rollback returned without effect")

        outcome = outcomes[0]
        assert outcome.cleanup_raised is False, (
            "the rollback RETURNED -- nothing raised")
        assert outcome.resolution == "still_open", (
            "the state was inferred from the call returning instead of being "
            "re-read from the connection")
        assert probed == [], (
            f"the probe was admitted under a falsely clean label: {probed}")
    finally:
        conn.rollback()
        conn.close()


# ===========================================================================
# (RD-a2) THE PROBE NEVER RECEIVES THE WRITER'S CONNECTION
# ===========================================================================
def test_RD_a2_the_probe_never_receives_the_writers_connection(
        tmp_path: Path, monkeypatch) -> None:
    """**``swing.trades.entry.find_trade_id_by_attempt_id`` is patched -- the
    name AS BOUND IN THE CONSUMING MODULE.**  ``entry.py`` imports its repo
    functions directly, so patching ``swing.data.repos.trades.<name>`` would
    rebind a name the service no longer consults and the capture would
    silently record nothing.

    **Pre-fix (the R10-02 shape -- reading on the writer's own handle):** the
    captured object IS the writer's connection.  This is the half of
    VISIBILITY closed by CONSTRUCTION, pinned so a later refactor cannot
    quietly re-introduce the convenience of *we already have a connection
    right here*.
    """
    db_path = tmp_path / "rda2.db"
    conn = ensure_schema(db_path)
    try:
        real = entry_mod.find_trade_id_by_attempt_id
        seen: list = []

        def _capture(probe_conn, attempt_id):
            # The path is read HERE, while the probe still owns the LIVE
            # connection -- `_durability_probe` closes it in its `finally`.
            seen.append((probe_conn, _resolve_main_db_path(probe_conn)))
            return real(probe_conn, attempt_id)

        monkeypatch.setattr(
            entry_mod, "find_trade_id_by_attempt_id", _capture)
        proxy = _ExitCommitsThenRaises(
            conn, sqlite3.OperationalError("commit lost (planted)"))

        result = record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                              force=False, cfg=None)

        assert result.trade_id > 0
        assert len(seen) == 1, f"the probe read {len(seen)} times"
        captured, captured_path = seen[0]
        assert captured is not conn, (
            "the probe read on the WRITER's own connection -- the writer "
            "quoting itself")
        assert captured is not proxy
        assert isinstance(captured, sqlite3.Connection)
        assert captured_path == db_path.resolve(), (
            "the probe opened a connection to a DIFFERENT database")
    finally:
        conn.close()


# ===========================================================================
# (RD-a3) R10-02 REPRODUCED -- a pending row is never reported durable
# ===========================================================================
def test_RD_a3_a_pending_row_is_never_reported_durable(
        tmp_path: Path, monkeypatch) -> None:
    """**The sharpest part of this row is the PAIR of reads**: the WRITER's
    own connection sees its pending row while a FRESH connection sees none.
    That is what shows the false SUCCESS in R10-02 came specifically from
    reading the writer's own handle and not from any property of the ledger.

    **Pre-fix (the reverted clause-2 helper, and any implementation that
    reads on ``conn``):** the read observes the writer's own uncommitted row
    and returns SUCCESS carrying a "DURABLE" warning over a merely-pending
    one.

    The fixture names its own journal mode because it makes a
    fresh-connection claim while the writer still holds the lock.
    """
    db_path = tmp_path / "rda3.db"
    conn = ensure_schema(db_path)
    try:
        assert conn.execute(
            "PRAGMA journal_mode").fetchone()[0] == "wal", (
            "in `delete` mode the fresh read below would block to the busy "
            "timeout and fail for a reason unrelated to this row's subject")
        outcomes = _capture_outcomes(monkeypatch)
        proxy = _RollbackRaisesWithoutEffect(conn)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value.__cause__) == "commit failed (planted)"
        assert conn.in_transaction is True, "the transaction stayed OPEN"
        assert conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker = ?",
            (TICKER,)).fetchone()[0] == 1, (
            "the fixture's own premise: the WRITER sees its pending row")
        assert _fresh_rows(db_path) == 0, (
            "a fresh connection sees a row that was never committed")
        assert outcomes[0].resolution == "still_open"
    finally:
        conn.rollback()
        conn.close()


# ===========================================================================
# (RD-a4) THE PREDICATE'S FOUR-ROW MATRIX, EACH CELL COMPUTED UNDER BOTH
# PREDICATES.  Rows 1, 2 and 4 are IDENTICAL under both, so ROW 3 IS THE
# ENTIRE DELTA -- and a matrix in which only one cell moves is the honest
# statement that the amendment is narrow.
# ===========================================================================
_A4_MATRIX = [(False, False), (False, True), (True, False), (True, True)]


@pytest.mark.parametrize("inside_except,chained", _A4_MATRIX, ids=[
    "row1-no-ambient-rollback-ok", "row2-no-ambient-rollback-failed",
    "row3-ambient-rollback-ok", "row4-ambient-rollback-failed"])
def test_RD_a4_the_predicates_four_row_matrix(
        tmp_path: Path, monkeypatch, inside_except: bool,
        chained: bool) -> None:
    """MEASURED BY EXECUTION, CPython 3.14.2 / sqlite3 3.50.4 -- these are the
    values the test asserts, not values derived from the source.

    ==  =============  =======  =========================  ===========  =============================  ==============
    #   inside_except  chained  ``escaping.__context__``   is ambient?  PRE-FIX (bare ``is not None``) POST-FIX
    ==  =============  =======  =========================  ===========  =============================  ==============
    1   False          False    ``None``                   --           False                          False
    2   False          True     the COMMIT error           no           True                           True
    3   True           False    the ambient ``ValueError`` YES          True -- THE FALSE POSITIVE     False
    4   True           True     the COMMIT error           no           True                           True
    ==  =============  =======  =========================  ===========  =============================  ==============

    **Row 3 is the entire delta**, and it is the row that would RE-RAISE under
    the pre-fix predicate -- over a DURABLE entry.  **Row 4 proves the nested
    case composes without a branch:** the ambient is live AND the rollback
    failed, and the predicate still answers True, because ``__exit__`` chains
    the COMMIT error at the FIRST link and the first link is the only one the
    predicate reads.

    The previous version of this row pinned ONE case and asserted it as a
    declared COST; the validity pin for it was then executed on the
    ``inside_except=False`` leg only and reported as confirming a scope
    argument entirely about the other leg.  RD: *"the repaired test is the
    apology that compiles."*
    """
    db_path = tmp_path / f"rda4_{int(inside_except)}{int(chained)}.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_spy(monkeypatch)
        lost = sqlite3.OperationalError("commit lost (planted)")
        proxy = (
            _ExitRollbackAlsoFails(
                conn, sqlite3.OperationalError("rollback failed (planted)"))
            if chained else _ExitCommitsThenRaises(conn, lost))
        ambient_seen: list = []
        escaped: list = []

        def _drive():
            # THE AXIS IS ASSERTED ON THE FIXTURE ITSELF, so a fixture that
            # stops establishing the ambient context fails loudly instead of
            # turning cells green.
            ambient_seen.append(sys.exc_info()[1])
            assert (ambient_seen[-1] is not None) is inside_except, (
                "the fixture is not on the axis this cell claims")
            if not chained:
                return record_entry(proxy, _req(), soft_warn=SOFT,
                                    hard_cap=HARD, force=False, cfg=None)
            with pytest.raises(sqlite3.OperationalError) as caught:
                record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                             force=False, cfg=None)
            escaped.append(caught.value)
            return None

        if inside_except:
            try:
                raise ValueError("22-A4 PROBE: the ambient handled exception")
            except ValueError:
                returned = _drive()
        else:
            returned = _drive()

        outcome = outcomes[0]
        if chained:
            # ROWS 2 and 4 -- the rollback FAILED.
            assert type(escaped[0].__context__) is sqlite3.OperationalError
            assert escaped[0].__context__ is proxy.commit_error, (
                "the fixture's own chaining: `__exit__` links the COMMIT "
                "error at the FIRST link")
            assert outcome.cleanup_raised is True
            assert probed == [], f"the probe ran anyway: {probed}"
            assert returned is None
            assert _fresh_rows(db_path) == 0
        else:
            # ROWS 1 and 3 -- no rollback failure; the row LANDED.
            assert lost.__context__ is ambient_seen[0], (
                "row 3's premise: `__exit__`'s re-raise carries the AMBIENT "
                "object, which is the false positive the base-slot read "
                "excludes by IDENTITY")
            assert outcome.cleanup_raised is False, (
                "the ambient exception was mistaken for a rollback failure -- "
                "under the pre-fix `__context__ is not None` predicate row 3 "
                "RE-RAISES over a durable entry")
            assert len(probed) == 1, f"the probe ran {len(probed)} times"
            assert returned is not None and returned.trade_id > 0
            assert any("do NOT retry" in w
                       for w in returned.post_commit_warnings), (
                returned.post_commit_warnings)
            assert _fresh_rows(db_path) == 1, (
                "the cost of getting this wrong is measured against the "
                "LEDGER, never against the warning text")
    finally:
        conn.close()


# ===========================================================================
# (RD-a5) THE CALLER-SIDE OBLIGATION THE `body_completed` REMOVAL RESTS ON
# -- a REGRESSION CONTROL, identical pre-fix and post-fix, and NOT evidence
# that clause 2 works: the guard it pins is PRE-ARC.
# ===========================================================================
@pytest.mark.parametrize("immediate", [True, False],
                         ids=["latched-path", "pre-arc-path"])
def test_RD_a5_a_body_that_raises_never_reaches_the_probe(
        tmp_path: Path, monkeypatch, immediate: bool) -> None:
    """Removing ``outcome.body_completed`` is sound *only because*
    ``record_entry``'s ``if result is None: raise`` runs first.  **That is a
    claim about the CALLER, and gotcha #31 is explicit that a caller-side
    obligation is pinned by a test rather than described in a comment** -- the
    callee's absence is the wrong half.

    **Against an implementation that moved the settle above the
    ``result is None`` branch:** the probe is called, and on the immediate
    path -- where ``resolution`` reads ``rolled_back`` -- the gate would reach
    the probe on a transaction whose body never finished.
    """
    db_path = tmp_path / f"rda5_{int(immediate)}.db"
    conn = ensure_schema(db_path)
    try:
        probed = _probe_calls(monkeypatch)
        settles: list = []
        real_settle = entry_mod._settle_by_attempt_identity

        def _watch_settle(*args):
            settles.append(args)
            return real_settle(*args)

        monkeypatch.setattr(
            entry_mod, "_settle_by_attempt_identity", _watch_settle)

        real_inner = entry_mod._record_entry_inner
        planted = RuntimeError("22-A4 PROBE: the body failed after its INSERT")

        def _inner(*a, **kw):
            real_inner(*a, **kw)
            raise planted

        monkeypatch.setattr(entry_mod, "_record_entry_inner", _inner)

        with pytest.raises(RuntimeError) as caught:
            record_entry(conn, _immediate_req() if immediate else _req(),
                         soft_warn=SOFT, hard_cap=HARD, force=False, cfg=None)

        assert caught.value is planted
        assert type(caught.value) is RuntimeError
        assert caught.value.args == (
            "22-A4 PROBE: the body failed after its INSERT",)
        assert caught.value.__cause__ is None
        assert probed == [], f"the probe ran on a body that raised: {probed}"
        assert settles == [], f"the settle was consulted: {settles}"
        assert _fresh_rows(db_path) == 0
        assert conn.in_transaction is False
    finally:
        conn.close()


# ===========================================================================
# (RD-b) A CONCURRENT INSERT TAKING OUR ROWID IS NOT CONFIRMED AS OURS
# ===========================================================================
class _RollbackThenConcurrentInsert:
    """``commit()`` raises without landing; ``rollback()`` performs the REAL
    rollback and THEN, on a SECOND connection, inserts a DIFFERENT trade --
    which is issued the rowid our rolled-back attempt had just used."""

    def __init__(self, conn: sqlite3.Connection, db_path: Path) -> None:
        self._conn = conn
        self._db_path = db_path
        self.planted_id: int | None = None

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
        self._conn.rollback()
        self.planted_id = _plant_committed_trade(
            self._db_path, OTHER_TICKER, None)

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


def test_RD_b_a_concurrent_insert_taking_our_rowid_is_not_ours(
        tmp_path: Path, monkeypatch) -> None:
    """``22A-FIX-R10-03``, reproduced on THIS tree rather than quoted, and
    killed.

    **Pre-fix (a rowid-keyed probe -- the reverted helper):** the read finds
    the OTHER row and returns SUCCESS naming a trade the operator never
    entered.  **Post-fix:** the probe is keyed ``WHERE attempt_id = ?``, finds
    nothing, and the ORIGINAL ``OperationalError`` propagates.
    """
    db_path = tmp_path / "rdb.db"
    conn = ensure_schema(db_path)
    try:
        token = _pin_token(monkeypatch)
        probed = _probe_spy(monkeypatch)
        our_id: list = []
        real_insert = entry_mod.insert_trade_with_event

        def _capture_insert(*a, **kw):
            tid = real_insert(*a, **kw)
            our_id.append(tid)
            return tid

        monkeypatch.setattr(
            entry_mod, "insert_trade_with_event", _capture_insert)

        # THE PROBE'S OWN ANSWER IS CAPTURED, and it is the assertion that
        # discriminates the KEYING rather than the outcome: against a
        # rowid-keyed read the answer is the OTHER row, and the outcome would
        # still be a re-raise because (pr3)'s ticker corroboration catches it
        # one step later.  A row that asserts only the outcome therefore
        # cannot see R10-03 at all.
        answers: list = []
        real_find = entry_mod.find_trade_id_by_attempt_id

        def _spy_find(probe_conn, attempt_id):
            answer = real_find(probe_conn, attempt_id)
            answers.append(answer)
            return answer

        monkeypatch.setattr(
            entry_mod, "find_trade_id_by_attempt_id", _spy_find)
        proxy = _RollbackThenConcurrentInsert(conn, db_path)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value) == "commit failed (planted)"
        # THE PREMISE, ASSERTED FIRST, so the row cannot pass for the wrong
        # reason: the rowid our INSERT was issued now belongs to somebody
        # else, and that row does not carry our token.
        assert proxy.planted_id == our_id[0], (
            "the concurrent insert did NOT take our rolled-back rowid, so "
            "this row is not reproducing R10-03 at all")
        stolen = conn.execute(
            "SELECT ticker, attempt_id FROM trades WHERE id = ?",
            (our_id[0],)).fetchone()
        assert stolen[0] == OTHER_TICKER
        assert stolen[1] is None and stolen[1] != token

        assert len(probed) == 1, "the probe did not run"
        assert probed[0][1] == token, "the probe was keyed on the wrong value"
        assert answers == [None], (
            f"the probe CONFIRMED a row that is not ours -- a rowid-keyed "
            f"read finds the concurrent insert and answers {answers}")
        assert _fresh_rows(db_path, TICKER) == 0, (
            "a trade the operator never entered was confirmed as ours")
    finally:
        conn.close()


# ===========================================================================
# (RD-b2) THE DECLARED RESIDUAL, VERIFIED BY EXECUTION
# ===========================================================================
class _RollbackThenPlantOurToken:
    """``commit()`` raises without landing; ``rollback()`` rolls back for real
    and THEN a SECOND connection commits a row carrying the SAME token.

    ``ticker`` is the one dimension between (RD-b2) -- the SAME ticker, S7.7's
    declared residual -- and (pr3) -- a DIFFERENT one, the alarm.

    **THE ROW CANNOT BE PLANTED BEFORE THE ATTEMPT**, which is a property of
    the schema rather than a fixture preference: our own INSERT carries the
    same token, so ``ux_trades_attempt_id`` refuses it AT THE INSERT and the
    attempt never reaches the lost-commit window.  Planting after the rollback
    is also the only sequence a real collision could take.
    """

    def __init__(self, conn: sqlite3.Connection, db_path: Path,
                 token: str, ticker: str = TICKER,
                 at_id: int | None = None) -> None:
        self._conn = conn
        self._db_path = db_path
        self._token = token
        self._ticker = ticker
        self._at_id = at_id
        self.planted_id: int | None = None

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
        self._conn.rollback()
        self.planted_id = _plant_committed_trade(
            self._db_path, self._ticker, self._token, at_id=self._at_id)

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


def test_RD_b2_a_rolled_back_token_re_minted_IS_confirmed(
        tmp_path: Path, monkeypatch) -> None:
    """**S7.7's DECLARED RESIDUAL, EXECUTED RATHER THAN DESCRIBED.**  The
    UNIQUE index keeps NO memory of a rolled-back token, so a later committed
    row may legitimately carry it -- and the probe would then confirm that row
    as ours.  **This test must be READ AS A DECLARATION, not as an
    aspiration:** if a future arc makes uniqueness structural, this row is the
    one that must be INVERTED, and its failure is the notification.

    The arithmetic, so the declaration carries its own bound: a ``uuid4``
    draws 122 random bits, so ``n`` attempts collide with probability about
    ``n^2 / 2^123`` -- roughly 1e-27 at ``n = 10^5``.  A real occurrence needs
    TWO independent conditions: an RNG collision AND the same ticker.  The
    collision is PLANTED here by raw INSERT because a genuine ``uuid4``
    collision is not reproducible, and this row's subject is the CONSEQUENCE
    of one rather than its likelihood.
    """
    db_path = tmp_path / "rdb2.db"
    conn = ensure_schema(db_path)
    try:
        token = _pin_token(monkeypatch)
        probed = _probe_spy(monkeypatch)
        our_id: list = []
        real_insert = entry_mod.insert_trade_with_event

        def _capture_insert(*a, **kw):
            tid = real_insert(*a, **kw)
            our_id.append(tid)
            return tid

        monkeypatch.setattr(
            entry_mod, "insert_trade_with_event", _capture_insert)
        # THE COLLIDING ROW IS PLANTED AT AN EXPLICIT, DIFFERENT ROWID, which
        # is what makes the id assertion below discriminate at all: a
        # collision on a row inserted LATER carries a higher rowid than our
        # rolled-back attempt did, so `result.trade_id` can only be right if
        # it came from the PROBE and not from the INSERT's `lastrowid`.
        proxy = _RollbackThenPlantOurToken(conn, db_path, token, at_id=4004)

        result = record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                              hard_cap=HARD, force=False, cfg=None)

        assert proxy.planted_id == 4004, "nothing was planted"
        assert our_id and our_id[0] != proxy.planted_id, (
            f"the fixture's own premise: our INSERT's rowid {our_id} must "
            f"DIFFER from the colliding row's {proxy.planted_id}")
        assert len(probed) == 1
        assert result.trade_id == proxy.planted_id, (
            "the settle did NOT confirm the colliding row -- the residual is "
            "no longer what S7.7 declares, and the declaration must be "
            "rewritten rather than this assertion relaxed -- and because "
            "the ids differ, this also pins that the returned id comes from "
            "the PROBE and never from the INSERT's `lastrowid`")
        assert any("do NOT retry" in w for w in result.post_commit_warnings)
        assert _fresh_rows(db_path) == 1
    finally:
        conn.close()


# ===========================================================================
# (c2) A REAL COMMIT FAILURE, NO PROXY
# ===========================================================================
@pytest.mark.parametrize("immediate", [True, False],
                         ids=["latched-path", "pre-arc-path"])
def test_c2_a_REAL_commit_failure_with_no_proxy(
        tmp_path: Path, monkeypatch, immediate: bool) -> None:
    """Every other lost-commit row uses a proxy, and a proxy tests the HANDLER
    rather than the CONDITION.  This one produces the real condition, on the
    real context manager, and it is the row that would have caught the first
    draft's ``A4-R1-2`` premise error.

    **The fixture NAMES ITS OWN JOURNAL MODE** -- a ROLLBACK-JOURNAL database,
    built through ``open_connection`` + ``run_migrations`` and never through
    ``ensure_schema``, because MEASURED (3) is a rollback-journal measurement
    and WAL admits the commit this row needs to fail.

    **Pre-fix, both paths:** the same ``OperationalError`` propagates -- so
    the ESCAPING EXCEPTION does not discriminate, and **the discriminating
    assertions are ``resolution`` plus the fact that the probe RAN and
    returned ABSENT.**
    """
    db_path = tmp_path / f"c2_{int(immediate)}.db"
    conn = open_connection(db_path, busy_timeout_ms=100)
    reader = sqlite3.connect(db_path)
    try:
        run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION)
        assert conn.execute(
            "PRAGMA journal_mode").fetchone()[0] == "delete", (
            "the fixture must be ROLLBACK-JOURNAL: MEASURED (3) is a "
            "rollback-journal measurement")
        conn.commit()
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM trades").fetchall()

        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_spy(monkeypatch)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(conn, _immediate_req() if immediate else _req(),
                         soft_warn=SOFT, hard_cap=HARD, force=False, cfg=None)

        assert "locked" in str(caught.value), (
            f"the planted condition did not fire: {caught.value}")
        outcome = outcomes[0]
        assert outcome.committed is False
        assert outcome.cleanup_raised is False
        assert outcome.resolution == (
            "rolled_back" if immediate else "not_needed"), (
            "the two paths resolve the transaction in different frames and "
            "the field must say which")
        assert len(probed) == 1, (
            f"the probe did not run after a PROVEN resolution: {probed}")
        assert conn.in_transaction is False
        assert _fresh_rows(db_path) == 0
    finally:
        reader.rollback()
        reader.close()
        conn.close()


# ===========================================================================
# (k3b) RUNTIME -- the `A4-R1-3` window at the ONE line, demonstrated
# ===========================================================================
def _deferred_committed_lineno() -> int:
    """The line of the DEFERRED branch's ``outcome.committed = True``.

    Located by AST rather than hard-coded: plan line anchors into
    ``entry.py`` have drifted through four commits of this ladder, and a
    stale number here would install the trace hook on an unrelated line and
    turn this row vacuously green.
    """
    fn = _function(_entry_tree(), "_entry_transaction")
    arm = next(
        s for s in fn.body
        if isinstance(s, ast.If) and isinstance(s.test, ast.UnaryOp)
        and isinstance(s.test.op, ast.Not)
        and isinstance(s.test.operand, ast.Name)
        and s.test.operand.id == "immediate")
    assigns = [n for n in ast.walk(arm)
               if _is_assign_to(n, "outcome", "committed")]
    assert len(assigns) == 1, (
        "the deferred branch no longer has exactly one `outcome.committed` "
        "assignment")
    return assigns[0].lineno


def test_k3b_an_exception_AT_the_committed_assignment_still_settles(
        tmp_path: Path, monkeypatch) -> None:
    """The ``A4-R1-3`` window at the one line, PROVEN rather than argued.

    A ``sys.settrace`` local hook raises a sentinel exactly at the deferred
    path's ``outcome.committed = True``, AFTER ``with conn:`` has committed.

    **Against the first draft's shape:** the sentinel escapes
    ``_entry_transaction`` uncaught, ``resolution`` stays ``"unattempted"``,
    the settle gate REFUSES, and ``record_entry`` re-raises **over a durable
    entry** -- the exact defect, demonstrated rather than argued.

    *Kept alongside (k3a): the trace hook proves the behaviour at ONE line,
    the AST walk proves the property for every assignment including ones
    added later.*
    """
    db_path = tmp_path / "k3b.db"
    conn = ensure_schema(db_path)
    target = _deferred_committed_lineno()
    entry_file = entry_mod.__file__
    fired: list = []
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_spy(monkeypatch)

        def _local(frame, event, arg):
            if event == "line" and frame.f_lineno == target and not fired:
                fired.append(True)
                raise KeyboardInterrupt(
                    "22-A4 PROBE: at `outcome.committed = True`")
            return _local

        def _global(frame, event, arg):
            if (frame.f_code.co_filename == entry_file
                    and frame.f_code.co_name == "_entry_transaction"):
                return _local
            return None

        # **THE ESCAPE IS CAUGHT AND ASSERTED, NOT LEFT TO PROPAGATE.**  The
        # sentinel is a `KeyboardInterrupt`, and an uncaught one ABORTS THE
        # PYTEST SESSION rather than producing a readable red -- strictly
        # worse than a failure, because it masks every other result.
        # MEASURED: against the reverted-clause-2 implementation this row is
        # written to exclude, that is exactly what happened.  Same shape, and
        # the same reason, as (k7b)'s broad catch.
        escaped: list = []
        result = None
        sys.settrace(_global)
        try:
            result = record_entry(conn, _req(), soft_warn=SOFT, hard_cap=HARD,
                                  force=False, cfg=None)
        except BaseException as exc:  # noqa: BLE001 -- see above
            escaped.append(exc)
        finally:
            sys.settrace(None)

        assert not escaped, (
            f"the sentinel ESCAPED `record_entry`: the settle refused over a "
            f"durable entry -- {type(escaped[0]).__name__}: {escaped[0]}")
        assert fired, (
            "the trace hook never reached the target line, so this row "
            "measures nothing about the window")
        outcome = outcomes[0]
        assert outcome.committed is False, (
            "the sentinel was planted AT the assignment; if this is True the "
            "hook fired somewhere else")
        assert outcome.resolution == "not_needed", (
            "`record_entry` never observed the resolution, so the settle "
            "gate would refuse over a durable row")
        assert len(probed) == 1
        assert result.trade_id > 0
        assert any("do NOT retry" in w for w in result.post_commit_warnings)
        assert _fresh_rows(db_path) == 1
    finally:
        sys.settrace(None)
        conn.close()


# ===========================================================================
# (k4a)-(k4b) THE DEFERRED PATH'S TWO ROLLBACK-FAILURE SEQUENCES -- the
# SIGNAL and the OUTCOME, BOTH pinned.  Keeping only the outcome assertions
# would leave two rows that pass against an implementation with NO detection
# at all, which is precisely the shape they were written under.
# ===========================================================================
def test_k4a_the_internal_rollback_takes_effect_and_then_raises(
        tmp_path: Path, monkeypatch) -> None:
    """**Against the pre-ruling shape in this same plan**
    (``resolution="not_needed"``, ``cleanup_raised=False``): the flag is
    False, the probe call count is **1**, and the probe reads ABSENT -- so the
    OUTCOME is the same and **only the two new assertions discriminate.**
    That is the whole reason they are here: the outcome-only version of this
    row certified the admitting implementation.

    And it is the row that closes ``A4-R9-3``: with the probe not run, there
    is no window in which a concurrently-committed colliding token can be read
    and confirmed.
    """
    db_path = tmp_path / "k4a.db"
    conn = ensure_schema(db_path)
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        rollback_error = sqlite3.OperationalError("rollback failed (planted)")
        proxy = _ExitRollbackAlsoFails(conn, rollback_error)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        escaping = caught.value
        assert type(escaping.__context__) is sqlite3.OperationalError, (
            "the proxy stopped chaining, so every assertion below would be "
            "measuring the fixture rather than the code")
        assert escaping is rollback_error
        assert escaping.__context__ is proxy.commit_error

        outcome = outcomes[0]
        assert outcome.resolution == "not_needed", (
            "the rollback took effect, so `in_transaction` reads False")
        assert outcome.cleanup_raised is True, "the failure was not DETECTED"
        assert probed == [], f"S2.4 condition 2 did not refuse: {probed}"
        assert conn.in_transaction is False
        assert _fresh_rows(db_path) == 0
    finally:
        conn.close()


def test_k4b_the_internal_rollback_raises_before_taking_effect(
        tmp_path: Path, monkeypatch) -> None:
    """THE WOUNDED CONNECTION.  ``_read_resolution`` sees ``in_transaction``
    True and records ``"still_open"``, **issuing no rollback and no
    statement**; ``cleanup_raised`` is True **from the ONE remaining route,
    ``_exit_rollback_failed`` on the chained exception** -- and the row
    asserts that route by ALSO asserting the proxy's ``rollback`` call count
    is unchanged after ``__exit__`` returned.

    **Against this sweep's retired retry arm:** the proxy's ``rollback`` count
    is 1 rather than 0, and the row goes red.

    The fixture NAMES ITS OWN JOURNAL MODE because it makes a
    fresh-connection claim while the writer still holds its lock.
    """
    db_path = tmp_path / "k4b.db"
    conn = ensure_schema(db_path)
    try:
        assert conn.execute(
            "PRAGMA journal_mode").fetchone()[0] == "wal", (
            "on a `delete`-mode database the COUNT below would block to the "
            "busy timeout and raise for a reason unrelated to this row")
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_calls(monkeypatch)
        rollback_error = sqlite3.OperationalError(
            "rollback failed before taking effect (planted)")
        proxy = _ExitRollbackAlsoFails(
            conn, rollback_error, perform_rollback=False)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        escaping = caught.value
        assert type(escaping.__context__) is sqlite3.OperationalError, (
            "the fixture's own chaining")
        assert escaping is rollback_error

        outcome = outcomes[0]
        assert outcome.resolution == "still_open"
        assert outcome.cleanup_raised is True
        assert proxy.rollback_calls == 0, (
            "the fixture's own premise: `__exit__` did NOT roll back")
        assert proxy.rollback_calls == proxy.rollback_calls_at_exit_return, (
            "a retry rollback was issued on a WOUNDED connection after "
            "`__exit__` returned")
        assert probed == [], f"the probe ran on a still-open write: {probed}"
        assert conn.in_transaction is True
        assert _fresh_rows(db_path) == 0
    finally:
        conn.rollback()
        conn.close()


# ===========================================================================
# (pr1)-(pr5) THE PROBE'S FIVE DESIGN REQUIREMENTS, EACH WITH AN ASSERTION
# THAT GOES RED IF THE REQUIREMENT IS DROPPED.  A design decision with no
# discriminating assertion is a paragraph, and this plan's own standard for a
# paragraph is that it does not ship.
# ===========================================================================
def _open_spy(monkeypatch, wrap=None) -> list:
    """Record every ``entry.open_connection`` call -- the name AS BOUND IN THE
    CONSUMING MODULE, (RD-a2)'s rule."""
    seen: list = []
    real = entry_mod.open_connection

    def _spy(*a, **kw):
        seen.append((a, kw))
        opened = real(*a, **kw)
        return opened if wrap is None else wrap(opened)

    monkeypatch.setattr(entry_mod, "open_connection", _spy)
    return seen


def test_pr1_the_probe_busy_timeout_is_bounded_and_the_bound_is_captured(
        tmp_path: Path, monkeypatch) -> None:
    """**Against an implementation that simply omits the kwarg:** the call
    carries ``DEFAULT_BUSY_TIMEOUT_MS``, **30000** -- a lost-commit probe that
    hangs a money-bearing web submit for thirty seconds, on a path whose
    fallback is the alarm anyway.

    The row asserts the NUMBER and not merely that some timeout was passed,
    because a silent restoration of the project default is exactly the shape a
    value-free assertion cannot see.
    """
    db_path = tmp_path / "pr1.db"
    conn = ensure_schema(db_path)
    try:
        seen = _open_spy(monkeypatch)
        proxy = _ExitCommitsThenRaises(
            conn, sqlite3.OperationalError("commit lost (planted)"))

        result = record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                              force=False, cfg=None)

        assert result.trade_id > 0
        assert len(seen) == 1, f"the probe opened {len(seen)} connections"
        _args, kwargs = seen[0]
        assert entry_mod._PROBE_BUSY_TIMEOUT_MS == 2000
        assert kwargs["busy_timeout_ms"] == entry_mod._PROBE_BUSY_TIMEOUT_MS
        assert kwargs["busy_timeout_ms"] != DEFAULT_BUSY_TIMEOUT_MS
        assert DEFAULT_BUSY_TIMEOUT_MS == 30000, (
            "the project default moved; the bound above is stated RELATIVE "
            "to it and this row's argument needs re-reading")
        assert kwargs["uri"] is True
    finally:
        conn.close()


class _CloseRaises:
    """A connection whose ``close()`` RAISES after a perfectly good read."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.close_calls = 0

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self) -> None:
        self.close_calls += 1
        raise RuntimeError("22-A4 PROBE: the probe connection close failed")


def test_pr2_a_close_that_raises_after_a_good_read_does_not_discard_it(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """**Against a naive ``finally: probe.close()`` with no containment:** the
    close's exception propagates out of the ``finally``, the valid result is
    thrown away, and ``record_entry`` re-raises **over a durable entry** --
    which is clause 1's own subject arriving inside the machinery built to
    serve it.

    *(g) is the neighbouring row and is NOT the same one: (g) drives a probe
    that fails to READ; this one drives a probe that read SUCCESSFULLY and
    then failed to tidy up, and only this ordering distinguishes "contained
    close" from "contained probe".*
    """
    db_path = tmp_path / "pr2.db"
    conn = ensure_schema(db_path)
    leaked: list = []

    def _wrap(probe_conn):
        leaked.append(probe_conn)
        return _CloseRaises(probe_conn)

    try:
        _open_spy(monkeypatch, wrap=_wrap)
        proxy = _ExitCommitsThenRaises(
            conn, sqlite3.OperationalError("commit lost (planted)"))

        with caplog.at_level(logging.WARNING, logger="swing.trades.entry"):
            result = record_entry(proxy, _req(), soft_warn=SOFT,
                                  hard_cap=HARD, force=False, cfg=None)

        assert result.trade_id > 0, "the valid read was thrown away"
        assert any("do NOT retry" in w for w in result.post_commit_warnings)
        assert _fresh_rows(db_path) == 1
        assert any("close" in r.getMessage() for r in caplog.records), (
            "the close failure was swallowed silently -- a silent `pass` "
            "trades one invisible failure for another")
    finally:
        for c in leaked:
            c.close()
        conn.close()


def test_pr3_the_right_token_on_the_WRONG_ticker_is_the_alarm(
        tmp_path: Path, monkeypatch) -> None:
    """**S7.7's SAME-TICKER BOUND RESTS ON THIS ROW.**  The accepted
    limitation bounds the false-confirm probability by requiring an RNG
    collision **AND** the same ticker, and without this row nothing in the
    suite holds up the second conjunct.

    **Against an implementation that omits the corroboration** (S2.4
    condition 4's second half): the settle SUCCEEDS and returns a trade id for
    a ticker the operator did not enter -- and **every other row in this
    roster would pass that implementation.**
    """
    db_path = tmp_path / "pr3.db"
    conn = ensure_schema(db_path)
    try:
        assert OTHER_TICKER != TICKER
        token = _pin_token(monkeypatch)
        probed = _probe_spy(monkeypatch)

        # THE PREMISE IS TAKEN FROM THE PROBE'S OWN ANSWER, not from a read
        # beside it: what must be true is that the tuple the corroboration
        # examines carries a ticker that is not the request's.
        seen: list = []
        real_find = entry_mod.find_trade_id_by_attempt_id

        def _spy_find(probe_conn, attempt_id):
            answer = real_find(probe_conn, attempt_id)
            seen.append(answer)
            return answer

        monkeypatch.setattr(
            entry_mod, "find_trade_id_by_attempt_id", _spy_find)
        proxy = _RollbackThenPlantOurToken(
            conn, db_path, token, ticker=OTHER_TICKER)

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _immediate_req(), soft_warn=SOFT,
                         hard_cap=HARD, force=False, cfg=None)

        assert str(caught.value) == "commit failed (planted)", (
            "the ORIGINAL exception must survive the alarm")
        assert len(probed) == 1, "the probe never ran"
        assert seen == [(proxy.planted_id, OTHER_TICKER)], (
            f"the premise: the probe FOUND a row carrying our token under "
            f"somebody else's ticker -- got {seen}")
        assert _fresh_rows(db_path, TICKER) == 0, (
            "a trade id was returned for a ticker the operator did not enter")
    finally:
        conn.close()


def test_pr4_no_token_means_no_probe(
        tmp_path: Path, monkeypatch) -> None:
    """**Against an implementation whose condition 3 checks only the database
    path:** the probe runs with ``attempt_id = None``, and
    ``WHERE attempt_id = ?`` bound to NULL matches nothing in SQL -- **so the
    defect is INVISIBLE in its outcome and visible only in the call count**,
    which is why this row asserts the count rather than the result.

    **THE PLAN'S FIXTURE FOR THIS ROW WAS FALSE AND IS CORRECTED HERE
    (executing intake, 2026-09-07).**  It said to *"drive the (c) shape with
    the mint contained-failed, so ``attempt.token is None`` while the database
    path resolved (the ``e2`` apparatus-cannot-fail-an-entry path produces
    exactly this)."*  **It does not.**  MEASURED against the shipped
    ``_begin_attempt_identity``: the mint's ``except`` arm returns a bare
    ``_AttemptIdentity()`` **before** ``_resolve_main_db_path`` is ever
    reached, so a contained mint failure yields ``token=None`` AND
    ``db_path=None`` -- and under that state the db-path-only mutant refuses
    the probe for the WRONG reason and this row goes green against the very
    implementation it excludes (measured: it did).

    So the state is CONSTRUCTED directly, which also states the honest
    consequence: **``token is None`` with a resolved path is not producible by
    today's ``_begin_attempt_identity``, so condition 3's token half is a
    PRECONDITION of the gate rather than a reachable branch.**  It is kept and
    pinned because the gate's safety must not depend on the internal ordering
    of a different function -- exactly the argument S2.4 gives for rejecting
    ``"unattempted"`` rather than arguing it unreachable.
    """
    db_path = tmp_path / "pr4.db"
    conn = ensure_schema(db_path)
    try:
        real_begin = entry_mod._begin_attempt_identity

        def _tokenless(c):
            resolved = real_begin(c)
            assert resolved.db_path is not None, (
                "the fixture's own premise: the PATH resolved")
            return entry_mod._AttemptIdentity(
                token=None, db_path=resolved.db_path)

        monkeypatch.setattr(
            entry_mod, "_begin_attempt_identity", _tokenless)
        probed = _probe_calls(monkeypatch)
        proxy = _ExitCommitsThenRaises(
            conn, sqlite3.OperationalError("commit lost (planted)"))

        with pytest.raises(sqlite3.OperationalError) as caught:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)

        assert str(caught.value) == "commit lost (planted)"
        # The apparatus degraded and did NOT fail the entry: the row is
        # durable, tokenless, and only the settle is unavailable.
        assert _fresh_rows(db_path) == 1
        assert conn.execute(
            "SELECT attempt_id FROM trades WHERE ticker = ?",
            (TICKER,)).fetchone()[0] is None
        assert probed == [], f"the probe ran with no token: {probed}"
    finally:
        conn.close()


def test_pr5_the_probe_cannot_CREATE_a_database(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """**Pre-fix (a bare path handed to ``open_connection``):**
    ``sqlite3.connect`` CREATES the file, the probe answers ABSENT, and the
    arc has written a zero-table database onto an already-failing money path
    **by the mechanism whose entire purpose is to observe without acting.**

    **The no-file assertion is the discriminating one**; the exception type
    alone is not, because a created-then-empty database also produces no row.
    """
    db_path = tmp_path / "pr5.db"
    conn = ensure_schema(db_path)
    missing = tmp_path / "moved-away" / "gone.db"
    missing.parent.mkdir()
    try:
        monkeypatch.setattr(
            entry_mod, "_resolve_main_db_path", lambda _c: missing)
        probed = _probe_spy(monkeypatch)
        proxy = _ExitCommitsThenRaises(
            conn, sqlite3.OperationalError("commit lost (planted)"))

        with caplog.at_level(logging.WARNING, logger="swing.trades.entry"):
            with pytest.raises(sqlite3.OperationalError) as caught:
                record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                             force=False, cfg=None)

        assert str(caught.value) == "commit lost (planted)", (
            "the probe's own failure replaced the operator's evidence")
        assert len(probed) == 1, "the probe never ran"
        assert not missing.exists(), (
            "the probe CREATED a database on an already-failing money path")
        assert caplog.records, "the contained failure was not reported"
    finally:
        conn.close()


# ===========================================================================
# (A4X-R2-02a)-(A4X-R2-02c) THE PROOF-TO-RETURN TAIL -- the two windows
# `A4X-R2-01` named, RULED BY RD 2026-09-08.  Window 1 is FIXED and (a) pins
# the fix; window 2 is DECLARED and (b) pins THE DECLARED DIRECTION rather
# than a fix -- a row written deliberately to fail against the swallow.
# (c) is the probe-count pin carried by BOTH rows: it is the discriminator
# against the re-probe branch RD rejected, and it is what keeps
# `tests/trades/test_22a4_attempt_identity.py`'s one-probe-per-attempt
# assertion true rather than merely unedited.
# ===========================================================================
def _proof_return_lineno() -> int:
    """The line of the corroborated proof's ``return`` inside
    ``_settle_by_attempt_identity``'s own ``try``.

    **Located by SHAPE, not by name and not by number.**  The plan's line
    anchors into ``entry.py`` have drifted through six commits of this
    ladder, and the LOCAL'S NAME is exactly what RD's capture-then-return
    changes (``found`` before, ``proven`` after) -- so a locator keyed on
    either would measure the rename instead of the window.  The shape is
    stable across both: the ``try`` body's every other ``return`` is the
    literal ``None`` alarm, so **the one ``return <name>`` in that body is
    the statement this row injects at**, before the fix and after it.
    """
    fn = _function(_entry_tree(), "_settle_by_attempt_identity")
    tries = [n for n in fn.body if isinstance(n, ast.Try)]
    assert len(tries) == 1, (
        "`_settle_by_attempt_identity` no longer has exactly one top-level "
        "`try`, so this row cannot say where the proof is returned")
    returns = [n for stmt in tries[0].body for n in ast.walk(stmt)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)]
    assert len(returns) == 1, (
        f"expected exactly one `return <name>` in the try body, found "
        f"{len(returns)} -- the injection target is no longer identifiable")
    return returns[0].lineno


def _post_settle_unpack_lineno() -> int:
    """The line of ``record_entry``'s ``settled_trade_id, _ = settled``.

    The FIRST statement of the post-settle tail -- window 2's NEAR end.
    Located by shape for the same reason as above: it is the one
    tuple-unpacking assignment in ``record_entry`` whose value is the name
    ``settled``.  **The tail does not end two statements later** -- see
    ``_degraded_return_lineno`` for its FAR end, and Codex ``22A4-R3-02`` for
    the measurement that corrected the width this row's first draft claimed.
    """
    fn = _function(_entry_tree(), "record_entry")
    found = [n for n in ast.walk(fn)
             if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Tuple)
             and isinstance(n.value, ast.Name) and n.value.id == "settled"]
    assert len(found) == 1, (
        f"expected exactly one `<a>, <b> = settled` in `record_entry`, found "
        f"{len(found)} -- window 2's injection target moved")
    return found[0].lineno


def _fault_at(entry_file: str, func_name: str, target: int,
              exc: BaseException, fired: list):
    """A ``sys.settrace`` global hook that raises ``exc`` ONCE, at ``target``,
    and only inside ``func_name``'s frames in ``entry.py``."""
    def _local(frame, event, arg):
        if event == "line" and frame.f_lineno == target and not fired:
            fired.append(True)
            raise exc
        return _local

    def _global(frame, event, arg):
        if (frame.f_code.co_filename == entry_file
                and frame.f_code.co_name == func_name):
            return _local
        return None

    return _global


def test_A4X_R2_02a_a_fault_AT_the_proof_return_reports_the_durable_entry(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """WINDOW 1, RULED: capture-then-return, with the ``except`` UNCHANGED.

    **THE NAIVE SUBSTITUTE IS TODAY'S SHIPPED CODE**, and what it does is the
    whole finding: the probe has ALREADY returned a row and the ticker has
    ALREADY matched -- durability is PROVEN -- but the ``return`` sits inside
    the helper's own ``except BaseException``, so an interrupt delivered at
    that statement is converted to ``None``, and ``record_entry`` re-raises
    **the original commit error over a durable entry.**  MEASURED against
    ``b3b518f9``'s shape: ``sqlite3.OperationalError('commit lost (planted)')``
    escaped this row.

    RD's ruling (2026-09-08): a post-proof fault is clause 1's own event one
    rung down -- a fault after ``commit()`` returned is already reported as a
    degraded SUCCESS -- so the proof is CAPTURED before the ``return`` and
    handed back from the containment arm.  **The ``except`` scope is NOT
    narrowed**: narrowing changes WHICH exception escapes on a post-proof
    fault (the fault instead of the original), and that identity is the
    R11-03 property this module pins.

    **THE FAULT'S TEXT REACHES THE OPERATOR THROUGH THE LOG, NOT THROUGH THE
    WARNING** -- asserted here on the channel that exists.  ``warning_text``
    interpolates ``safe_text(post_commit_error)``, which is ``repr``; MEASURED
    on this box, ``repr`` renders no ``__notes__``, and ``log_contained_note``
    attaches a note ONLY when the SINK fails.  So no contained note can reach
    the degraded warning today.  That gap is reported as a finding rather than
    closed here: RD pre-ruled that discovering it is NOT a licence to add a
    channel.
    """
    db_path = tmp_path / "r2_02a.db"
    conn = ensure_schema(db_path)
    entry_file = entry_mod.__file__
    target = _proof_return_lineno()
    fired: list = []
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probe_calls: list = []
        probe_returns: list = []
        real_probe = entry_mod._durability_probe

        def _spy(*args):
            probe_calls.append(args)
            probe_returns.append(real_probe(*args))
            return probe_returns[-1]

        monkeypatch.setattr(entry_mod, "_durability_probe", _spy)
        lost = sqlite3.OperationalError("commit lost (planted)")
        proxy = _ExitCommitsThenRaises(conn, lost)
        fault = KeyboardInterrupt(
            "22-A4 PROBE: AT the settle's own return of the proof")

        # **THE ESCAPE IS COLLECTED, NOT LEFT TO PROPAGATE** -- same reason as
        # (k3b): an uncaught `KeyboardInterrupt` ABORTS THE PYTEST SESSION
        # rather than producing a readable red, which is strictly worse than a
        # failure because it masks every other result.  Against the naive
        # substitute this row catches `sqlite3.OperationalError` here.
        escaped: list = []
        result = None
        with caplog.at_level(logging.ERROR, logger="swing.trades.entry"):
            sys.settrace(_fault_at(entry_file, "_settle_by_attempt_identity",
                                   target, fault, fired))
            try:
                result = record_entry(proxy, _req(), soft_warn=SOFT,
                                      hard_cap=HARD, force=False, cfg=None)
            except BaseException as exc:  # noqa: BLE001 -- see above
                escaped.append(exc)
            finally:
                sys.settrace(None)

        assert fired, (
            "the trace hook never reached the proof's return, so this row "
            "measures nothing about the window")
        assert not escaped, (
            f"a PROVEN-durable entry was reported as a failure: "
            f"{type(escaped[0]).__name__}: {escaped[0]}")
        assert result is not None
        # (A4X-R2-02c) THE PROBE-COUNT PIN -- one probe per attempt, which is
        # the discriminator against the re-probe branch.
        assert len(probe_calls) == 1, (
            f"the probe ran {len(probe_calls)} times -- a second read is the "
            f"branch RD rejected")
        assert probe_returns[0] is not None, (
            "the fixture's own premise: the probe corroborated a durable row")
        assert result.trade_id == probe_returns[0][0], (
            f"the reported id is not the PROBE's: {result.trade_id} vs "
            f"{probe_returns[0]}")
        assert _fresh_rows(db_path) == 1
        assert outcomes[0].committed is False, (
            "a successful settle must not claim the commit's own return")
        lost_commit = [w for w in result.post_commit_warnings
                       if "own RETURN was LOST" in w]
        assert len(lost_commit) == 1, result.post_commit_warnings
        assert f"trade {result.trade_id}" in lost_commit[0]
        assert "do NOT retry" in lost_commit[0]
        # The post-proof fault's text, on the channel that carries it.
        post_proof = [r.getMessage() for r in caplog.records
                      if "AFTER the proof" in r.getMessage()]
        assert len(post_proof) == 1, (
            f"the post-proof fault was not reported: "
            f"{[r.getMessage() for r in caplog.records]}")
        assert "22-A4 PROBE: AT the settle's own return" in post_proof[0]
        # THE COUNTERFACTUAL, which is what carries the meaning here: the
        # NO-PROOF arm must NOT fire when a proof exists.  Asserting the
        # absence of the SUPERSEDED wording ("the read FAILED") stopped
        # discriminating the moment that sentence left the module -- a belt
        # that goes vacuously green is the shape this arc keeps catching -- so
        # this names the arm that is actually reachable.  The superseded
        # wording is still asserted against, discriminatingly, by (A4X-R2-02d),
        # which is the row that measured it red.
        assert not any("NO CORROBORATED PROOF" in r.getMessage()
                       for r in caplog.records), (
            "the no-proof alarm fired while the probe HAD corroborated a "
            "durable row -- a false sentence in an alarm teaches the next "
            "reader to distrust the check")
    finally:
        sys.settrace(None)
        conn.close()


def test_A4X_R2_02b_a_fault_in_the_post_settle_window_escapes_as_itself(
        tmp_path: Path, monkeypatch) -> None:
    """WINDOW 2, **DECLARED, NOT FIXED** -- and this row pins the DECLARED
    DIRECTION rather than a fix.  It is written that way deliberately.

    ``record_entry``'s POST-SETTLE TAIL -- the unpack, the
    ``dataclasses.replace``, ``post_commit_error_text``, the ``warning_text``
    branch, the degraded result's construction and ``return degraded`` -- sits
    in the ``except BaseException as post_commit_error:`` suite with no
    enclosing handler, because an exception raised inside an ``except`` suite
    is not caught by the ``try`` whose handler is running.  A fault delivered
    anywhere in it escapes over a row that is DURABLE.  **This row drives the
    NEAR end; its sibling below drives the FAR end**, and the pair is what the
    declaration's boundary-named bound rests on.  RD ruled (2026-09-08) that
    the tail cannot be made zero-width and that this window is **one
    more member of the alarm family the declaration already prices** -- durable
    row, reported failure, retry refused by ``ux_trades_one_open_per_ticker``
    except for a ticker closed between the attempts -- with the same cost and
    the same belt, not a new uncovered direction.  Branch C's residual is
    accepted here because nothing cheaper exists; it was refused for window 1
    because capture-then-return is cheaper and strictly truer.

    **THE NAIVE SUBSTITUTE IS A ``try``/``except`` THAT SWALLOWS IT** -- the
    obvious symmetry with window 1's fix, applied where it does not belong.
    Against that shape this row goes RED at ``len(escaped) == 1``: nothing
    escapes, and the operator is handed a success whose warning was built by
    a frame that never finished.  MEASURED, not argued: the substitute was
    applied to ``record_entry`` and this row failed against it before it was
    reverted.

    So what is asserted is the HONEST CHAIN: the escaping exception **is** the
    injected fault, with the ORIGINAL commit error as its ``__context__``.
    The row is a control on the declaration -- if a later arc closes this
    window, this row is the one that must be re-ruled and rewritten, which is
    the point of pinning a declared direction rather than leaving it unpinned.
    """
    db_path = tmp_path / "r2_02b.db"
    conn = ensure_schema(db_path)
    entry_file = entry_mod.__file__
    target = _post_settle_unpack_lineno()
    fired: list = []
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_spy(monkeypatch)
        lost = sqlite3.OperationalError("commit lost (planted)")
        proxy = _ExitCommitsThenRaises(conn, lost)
        fault = KeyboardInterrupt(
            "22-A4 PROBE: at the post-settle tail's NEAR end")

        # The broad collector, for (k3b)'s reason: an uncaught
        # `KeyboardInterrupt` ABORTS THE PYTEST SESSION, which is strictly
        # worse than a red because it masks every other result.  Here the
        # escape is EXPECTED, so the collector is also the assertion's subject.
        escaped: list = []
        result = None
        sys.settrace(_fault_at(entry_file, "record_entry", target, fault,
                               fired))
        try:
            result = record_entry(proxy, _req(), soft_warn=SOFT,
                                  hard_cap=HARD, force=False, cfg=None)
        except BaseException as exc:  # noqa: BLE001 -- see above
            escaped.append(exc)
        finally:
            sys.settrace(None)

        assert fired, (
            "the trace hook never reached the post-settle window, so this row "
            "measures nothing about it")
        assert len(escaped) == 1, (
            f"nothing escaped the post-settle window -- the declared "
            f"direction was replaced by a swallow, and the caller was handed "
            f"{result}")
        assert type(escaped[0]) is KeyboardInterrupt, (
            f"the escaping exception is not the injected fault: "
            f"{type(escaped[0]).__name__}")
        assert escaped[0] is fault
        assert escaped[0].__context__ is lost, (
            "the chain is not honest: the ORIGINAL commit error must be the "
            "context of what escapes")
        # (A4X-R2-02c) THE PROBE-COUNT PIN, on this row too.
        assert len(probed) == 1, (
            f"the probe ran {len(probed)} times -- a second read is the "
            f"branch RD rejected")
        assert outcomes[0].committed is False
        # THE DECLARATION'S OWN SUBJECT, MEASURED: the row IS durable while
        # the caller is told the entry failed.  That is the cost the
        # declaration prices, and pricing it requires asserting it.
        assert _fresh_rows(db_path) == 1, (
            "this row's entire premise is a DURABLE entry reported as a "
            "failure; without it the assertion above prices nothing")
    finally:
        sys.settrace(None)
        conn.close()


# ===========================================================================
# THE TWO ROWS CODEX ROUND 3 SHOWED WERE MISSING (`22A4-R3-01`, `22A4-R3-02`).
# Both findings were REPRODUCED before either was acted on, and both landed on
# the fix leg's OWN artifacts: a declaration that claimed a window was gone
# when the fix had only MOVED it, and a bound stated as "two statements" when
# the exposure ran to the function's return.  The rows below measure the two
# boundaries the declaration now names, so that the corrected text is pinned
# by execution rather than by a second confident sentence.
# ===========================================================================
def _proof_capture_lineno() -> int:
    """The line of ``proven = found`` -- the settle's CAPTURE boundary.

    The one statement the capture-then-return fix could not cover: a fault
    landing HERE arrives with the probe's corroborated row already in hand and
    ``proven`` still ``None``.  Located by shape (the single assignment of a
    bare Name to ``proven``) for the same reason as the other locators.
    """
    fn = _function(_entry_tree(), "_settle_by_attempt_identity")
    hits = [n for n in ast.walk(fn)
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and n.targets[0].id == "proven"
            and isinstance(n.value, ast.Name)]
    assert len(hits) == 1, (
        f"expected exactly one `proven = <name>` capture, found {len(hits)}")
    return hits[0].lineno


def _degraded_return_lineno() -> int:
    """The line of ``return degraded`` -- the post-settle tail's FAR end."""
    fn = _function(_entry_tree(), "record_entry")
    hits = [n for n in ast.walk(fn)
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
            and n.value.id == "degraded"]
    assert len(hits) == 1, (
        f"expected exactly one `return degraded`, found {len(hits)}")
    return hits[0].lineno


def test_A4X_R2_02d_a_fault_AT_the_capture_alarms_and_says_only_what_it_saw(
        tmp_path: Path, monkeypatch, caplog) -> None:
    """`22A4-R3-01`: THE CAPTURE BOUNDARY -- declared, and its wording made true.

    The capture-then-return fix MOVED the settle's proof-to-return window; it
    did not remove it, because the class is irreducible and a capture is
    itself a statement.  A fault delivered AT ``proven = found`` lands after
    the probe returned a corroborated row and before the proof is bound, so
    the helper ALARMS over a durable entry.

    **THE NAIVE SUBSTITUTE IS THE FIX LEG'S OWN FIRST SHAPE**, whose no-proof
    arm said *"the settle-by-attempt-identity read FAILED"*.  MEASURED against
    it: this exact injection emitted that sentence with one durable row on
    disk -- **the same false sentence the ruling required be removed, one
    statement further along.**  So this row asserts the direction AND the
    wording: the alarm fires, and it claims only what the branch can observe.

    It also pins the declaration.  Naming this boundary as a member of the
    alarm family is only worth the words if something measures it; without
    this row the declaration would be a second confident sentence about a
    window nobody had driven.
    """
    db_path = tmp_path / "r3_capture.db"
    conn = ensure_schema(db_path)
    entry_file = entry_mod.__file__
    target = _proof_capture_lineno()
    fired: list = []
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probe_calls: list = []
        probe_returns: list = []
        real_probe = entry_mod._durability_probe

        def _spy(*args):
            probe_calls.append(args)
            probe_returns.append(real_probe(*args))
            return probe_returns[-1]

        monkeypatch.setattr(entry_mod, "_durability_probe", _spy)
        lost = sqlite3.OperationalError("commit lost (planted)")
        proxy = _ExitCommitsThenRaises(conn, lost)
        fault = KeyboardInterrupt("22-A4 PROBE: AT the settle's capture")

        escaped: list = []
        with caplog.at_level(logging.ERROR, logger="swing.trades.entry"):
            sys.settrace(_fault_at(entry_file, "_settle_by_attempt_identity",
                                   target, fault, fired))
            try:
                record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                             force=False, cfg=None)
            except BaseException as exc:  # noqa: BLE001 -- session-abort guard
                escaped.append(exc)
            finally:
                sys.settrace(None)

        assert fired, (
            "the trace hook never reached the capture, so this row measures "
            "nothing about the boundary it exists to declare")
        # THE DECLARED DIRECTION: the alarm, carrying the ORIGINAL failure.
        assert len(escaped) == 1, "nothing escaped the capture boundary"
        assert escaped[0] is lost, (
            f"the containment arm changed which exception escapes: "
            f"{type(escaped[0]).__name__}: {escaped[0]}")
        # THE PREMISE, MEASURED: the probe HAD corroborated a durable row.
        assert len(probe_calls) == 1
        assert probe_returns[0] is not None, (
            "without a corroborated probe this row is not about the capture "
            "boundary at all")
        assert _fresh_rows(db_path) == 1, (
            "the declaration's cost is a DURABLE row reported as a failure; "
            "without the row there is nothing declared")
        assert outcomes[0].committed is False
        # THE WORDING: only what the branch can observe.
        arm = [r.getMessage() for r in caplog.records
               if "NO CORROBORATED PROOF" in r.getMessage()]
        assert len(arm) == 1, (
            f"the no-proof arm did not report: "
            f"{[r.getMessage() for r in caplog.records]}")
        assert "22-A4 PROBE: AT the settle's capture" in arm[0]
        assert not any("read FAILED" in r.getMessage()
                       for r in caplog.records), (
            "the alarm says the READ failed while the read SUCCEEDED and was "
            "corroborated -- the false sentence the ruling required removed, "
            "surviving one statement further along")
    finally:
        sys.settrace(None)
        conn.close()


def test_A4X_R2_02e_a_fault_at_the_tail_s_FAR_end_escapes_the_same_way(
        tmp_path: Path, monkeypatch) -> None:
    """`22A4-R3-02`: THE POST-SETTLE TAIL'S FAR END -- the bound's other endpoint.

    The declaration's first draft bounded window 2 at TWO STATEMENTS.  It is
    not two: an exception raised inside an ``except`` suite is not caught by
    the ``try`` whose handler is running, and the only nested handler in that
    tail protects the ``log.error`` call alone -- so the exposure runs from the
    settle's return THROUGH ``return degraded``.  MEASURED at two interior
    points before the text was corrected; this row drives the FAR END, which
    is the endpoint that falsifies the two-statement claim outright.

    **THE NAIVE SUBSTITUTE IS THE SUPERSEDED DECLARATION ITSELF**: under a
    two-statement bound this injection point is outside the declared window,
    so an escape here would be an UNDECLARED loss of a durable entry.  The row
    exists so the corrected bound is measured at both ends rather than
    asserted at one.  A `try`/`except` swallow over the tail would also fail
    it, at ``len(escaped) == 1``.
    """
    db_path = tmp_path / "r3_tailfar.db"
    conn = ensure_schema(db_path)
    entry_file = entry_mod.__file__
    target = _degraded_return_lineno()
    fired: list = []
    try:
        outcomes = _capture_outcomes(monkeypatch)
        probed = _probe_spy(monkeypatch)
        lost = sqlite3.OperationalError("commit lost (planted)")
        proxy = _ExitCommitsThenRaises(conn, lost)
        fault = KeyboardInterrupt("22-A4 PROBE: at `return degraded`")

        escaped: list = []
        sys.settrace(_fault_at(entry_file, "record_entry", target, fault,
                               fired))
        try:
            record_entry(proxy, _req(), soft_warn=SOFT, hard_cap=HARD,
                         force=False, cfg=None)
        except BaseException as exc:  # noqa: BLE001 -- session-abort guard
            escaped.append(exc)
        finally:
            sys.settrace(None)

        assert fired, (
            "the trace hook never reached `return degraded`, so this row "
            "measures nothing about the tail's far end")
        assert len(escaped) == 1, (
            "nothing escaped the tail's far end -- the declared direction was "
            "replaced by a swallow")
        assert type(escaped[0]) is KeyboardInterrupt
        assert escaped[0] is fault
        assert escaped[0].__context__ is lost, (
            "the chain is not honest: the ORIGINAL commit error must be the "
            "context of what escapes")
        assert len(probed) == 1
        assert outcomes[0].committed is False
        assert _fresh_rows(db_path) == 1, (
            "the row must be DURABLE here, or this measures nothing the "
            "declaration prices")
    finally:
        sys.settrace(None)
        conn.close()
