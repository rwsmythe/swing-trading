"""22-A4 -- the THREE observations, and clause 2's settlement rows.

**TASK 3 SHIPS (k), (k2), (k3a), (k5), (k6a)-(k6b) and (k7a)-(k7b).**  Every
row here asserts something an assertion IN THIS TASK can distinguish from the
naive substitute the plan names for it -- the scheduling rule Task 3 is
written against.  The rows that assert what ``record_entry`` DOES with these
observations -- (k3b), (k4a), (k4b), (RD-a4), (RD-a5) and (k2)'s
probe-call-count-of-ZERO -- belong to Task 4, for one reason: each names
``_durability_probe`` / ``_settle_by_attempt_identity``, which do not exist yet.

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
import logging
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
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
    while leaving the transaction open."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rollback_calls = 0

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
    rollback and THEN raises."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rolled = False

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        raise sqlite3.OperationalError("commit failed (planted)")

    def rollback(self) -> None:
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
    finally:
        conn.close()
