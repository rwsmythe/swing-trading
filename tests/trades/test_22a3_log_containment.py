"""22-A3 -- the log-containment idiom and the six cleanup sites it covers.

**A FAILING LOGGING HANDLER MUST NEVER CHANGE A FUNCTION'S RESULT OR WHICH
EXCEPTION PROPAGATES** (Codex 22A-R11-03).  A logging sink is caller-installed
infrastructure this package does not control, and every site covered here is a
CLEANUP handler -- the place where an exception is already in flight and its
IDENTITY is the caller's only evidence about what happened.

MEASURED PRE-FIX (plan S1.4, re-measured at execution time): a sink whose
``emit()`` raises replaces the cleanup error with its own ``RuntimeError`` and
the ``raise ... from ...`` chaining is lost with it.

Every (d) test therefore asserts the IDENTITY of what escapes, not merely that
something did.  "No crash" is asserted NOWHERE, deliberately: an implementation
wrapping the cleanup in ``try/except: pass`` would satisfy a no-crash assertion
and destroy the site.
"""
from __future__ import annotations

import logging
import sqlite3

import pytest


class _BrokenSink(logging.Handler):
    def emit(self, record):
        raise RuntimeError("22-A3 PROBE: logging sink failed")


@pytest.fixture
def broken_sink():
    sink = _BrokenSink(level=logging.ERROR)
    root = logging.getLogger()
    root.addHandler(sink)
    try:
        yield sink
    finally:
        root.removeHandler(sink)


# ===========================================================================
# (i) -- the idiom's unit properties
# ===========================================================================


def test_log_contained_returns_None_when_the_sink_works(caplog):
    from swing.trades.entry import log_contained
    log = logging.getLogger("t22a3.ok")
    with caplog.at_level(logging.ERROR):
        assert log_contained(log, "hello %s", "world") is None
    assert "hello world" in caplog.text


def test_log_contained_RETURNS_the_sink_failure_instead_of_raising(broken_sink):
    from swing.trades.entry import log_contained
    out = log_contained(logging.getLogger("t22a3.broken"), "boom")
    assert isinstance(out, RuntimeError)
    assert "logging sink failed" in str(out)


def test_log_contained_note_leaves_the_escaping_exception_UNCHANGED(broken_sink):
    from swing.trades.entry import log_contained_note
    cause = ValueError("the original cause")
    escaping = KeyError("the cleanup failure")
    escaping.__cause__ = cause

    log_contained_note(logging.getLogger("t22a3.note"), escaping, "boom")

    assert type(escaping) is KeyError
    assert escaping.args == ("the cleanup failure",)
    assert escaping.__cause__ is cause
    assert escaping.__context__ is None
    notes = getattr(escaping, "__notes__", ())
    assert any("could not be emitted" in n for n in notes), notes
    assert any("logging sink failed" in n for n in notes), notes


def test_an_OVERRIDDEN_add_note_cannot_swallow_the_sink_failure(broken_sink):
    """``add_note`` is overridable and CAN raise; going through
    ``escaping.add_note`` would then lose the logging failure entirely -- the
    invisible failure this helper exists to prevent.  The base implementation
    cannot be overridden away."""
    from swing.trades.entry import log_contained_note

    class _RefusesNotes(RuntimeError):
        def add_note(self, note):
            raise TypeError("refuses notes")

    escaping = _RefusesNotes("x")
    log_contained_note(logging.getLogger("t22a3.nonote"), escaping, "boom")

    notes = getattr(escaping, "__notes__", ())
    assert any("could not be emitted" in n for n in notes), (
        "the sink failure was swallowed because add_note was overridden")


def test_a_MALFORMED_existing_notes_attribute_is_repaired(broken_sink):
    """MEASURED: assigning a TUPLE to ``__notes__`` makes even
    ``BaseException.add_note`` raise ``TypeError: Cannot add note: __notes__
    is not a list``.  Without the repair branch the sink failure is lost, which
    is the same information loss the override case exists to prevent."""
    from swing.trades.entry import log_contained_note

    escaping = RuntimeError("cleanup")
    escaping.__notes__ = ("already", "a", "tuple")
    log_contained_note(logging.getLogger("t22a3.badnotes"), escaping, "boom")

    assert isinstance(escaping.__notes__, list)
    assert escaping.__notes__[:3] == ["already", "a", "tuple"]
    assert any("could not be emitted" in n for n in escaping.__notes__)


def test_an_overriding_getattribute_cannot_swallow_the_sink_failure(broken_sink):
    """S3(i) property 9.  A subclass overriding ``add_note``, ``__setattr__``
    AND ``__getattribute__`` defeats BOTH the base ``add_note`` (which reads
    the attribute through the override) and a plain ``getattr(..., None)``
    fallback -- whose default swallows only ``AttributeError`` while the
    override raises ``TypeError``.

    MEASURED on this runtime: ``BaseException.__getattribute__`` raises a
    plain ``AttributeError`` on such an object (i.e. reads as "absent") and
    ``BaseException.__setattr__`` then installs the list.  Read and write both
    go through the base slots, symmetrically.
    """
    from swing.trades.entry import log_contained_note

    class _Hostile(RuntimeError):
        def add_note(self, note):
            raise TypeError("refuses notes")

        def __setattr__(self, name, value):
            raise TypeError("refuses setattr")

        def __getattribute__(self, name):
            if name == "__notes__":
                raise TypeError("refuses __notes__ reads")
            return object.__getattribute__(self, name)

    escaping = _Hostile("x")
    log_contained_note(logging.getLogger("t22a3.hostile"), escaping, "boom")

    notes = BaseException.__getattribute__(escaping, "__notes__")
    assert any("could not be emitted" in n for n in notes), notes


def test_ascii_safe_survives_a_lone_surrogate():
    from swing.trades.entry import ascii_safe
    out = ascii_safe("bad \ud800 repr")
    assert out.isascii()
    assert "ud800" in out


def test_safe_text_of_a_surrogate_repr_is_ascii():
    """The property that keeps ``HTMLResponse`` from raising: ``html.escape``
    PRESERVES a lone surrogate and UTF-8 encoding of the body then fails, one
    frame outside every guard in the degraded path."""
    from swing.trades.entry import safe_text

    class _Surrogate(RuntimeError):
        def __repr__(self):
            return "bad \ud800 repr"

    assert safe_text(_Surrogate()).isascii()


def test_safe_text_never_raises():
    from swing.trades.entry import safe_text

    class _NoRepr(RuntimeError):
        def __repr__(self):
            raise ValueError("repr boom")

    class _NoReprNoStr(RuntimeError):
        def __repr__(self):
            raise ValueError("repr boom")

        def __str__(self):
            raise ValueError("str boom")

    assert safe_text(ValueError("plain")) == repr(ValueError("plain"))
    assert safe_text(ValueError("plain")).isascii()
    assert "repr boom" not in safe_text(_NoRepr("y"))       # fell through to str
    out = safe_text(_NoReprNoStr("z"))
    assert "raised" in out


def test_a_sink_error_with_a_RAISING_repr_still_produces_a_note():
    from swing.trades.entry import log_contained_note

    class _NoRepr(RuntimeError):
        def __repr__(self):
            raise ValueError("repr boom")

    class _WeirdSink(logging.Handler):
        def emit(self, record):
            raise _NoRepr("sink")

    sink = _WeirdSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    escaping = KeyError("cleanup")
    try:
        log_contained_note(logging.getLogger("t22a3.weird"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)
    assert any("could not be emitted" in n
               for n in getattr(escaping, "__notes__", ()))


# ===========================================================================
# (d1) -- `entry.py`'s OWN cleanup handler, BOTH branches.
#
# Fixing one branch and leaving the other is this arc's named repeat failure,
# so the test is parametrized over both.
# ===========================================================================


class _RollbackRaises:
    """Proxies ONLY the four members `_entry_transaction` touches, so a
    stand-in cannot silently diverge from the real connection surface
    (the `_CommitRaises` pattern, tests/trades/test_22a_task9_entry_wiring.py).

    `in_transaction` is SCRIPTED: the first read is the handler's entry gate
    (always True here); the second selects the message branch -- True is the
    "STILL OPEN" branch, False the "rollback took effect then raised" branch.
    """

    def __init__(self, *, in_transaction_after_rollback):
        self._reads = 0
        self._after = in_transaction_after_rollback
        self.rolled_back = False
        self.rollback_error = sqlite3.OperationalError(
            "22-A3 PROBE: rollback failed")

    def execute(self, sql, *a, **k):
        return None

    def commit(self):
        raise AssertionError("the body raises before any commit")

    def rollback(self):
        self.rolled_back = True
        raise self.rollback_error

    @property
    def in_transaction(self):
        self._reads += 1
        return True if self._reads == 1 else self._after


@pytest.mark.parametrize("still_open", [True, False],
                         ids=["still-open-branch", "took-effect-branch"])
def test_d1_a_broken_sink_cannot_change_what_escapes_the_entry_cleanup(
        broken_sink, still_open):
    from swing.trades.entry import _CommitOutcome, _entry_transaction

    proxy = _RollbackRaises(in_transaction_after_rollback=still_open)
    body_error = ValueError("22-A3 PROBE: the write failed")

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        with _entry_transaction(proxy, immediate=True,
                                outcome=_CommitOutcome()):
            raise body_error

    assert excinfo.value is proxy.rollback_error, (
        "the LOG SINK's exception escaped instead of the cleanup error -- "
        "the identity of what propagates was changed by a logging handler")
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is body_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ())), (
        "the log failure was swallowed silently")
    assert proxy.rolled_back


# ===========================================================================
# (d2)-(d6) -- the SIX cleanup sites in `cohort_provenance_correction.py`.
#
# None of them needs a seeded database world: each is driven through a narrow
# connection proxy plus one targeted monkeypatch, in the `_CommitRaises` style
# already used by tests/trades/test_22a_task9_entry_wiring.py -- proxying ONLY
# the members the code under test touches, so a stand-in cannot silently
# diverge from the real connection surface.
# ===========================================================================


class _Proxy:
    """`execute()` raises for SQL whose prefix appears in `fail_on`, returns
    None otherwise; `rollback()` raises `rollback_error` when given;
    `in_transaction` is a SCRIPTED SEQUENCE consumed one value per read, with
    the last value repeating.

    The sequence is required by the sites that read `in_transaction` MORE THAN
    ONCE, where the reads mean DIFFERENT things (does this call own the
    transaction / did the failed cleanup leave it open); a single boolean
    cannot express those postures.  d3 and d6 consume only the FIRST value --
    they enter caller-held, so `owns_read_tx` is False and the later ownership
    checks short-circuit.
    """

    def __init__(self, *, fail_on=None, rollback_error=None,
                 in_transaction=(False, True)):
        self._fail_on = dict(fail_on or {})
        self.rollback_error = rollback_error
        self._script = tuple(in_transaction)
        self._reads = 0
        self.executed: list[str] = []
        self.rolled_back = False

    def execute(self, sql, *a, **k):
        self.executed.append(sql)
        for prefix, exc in self._fail_on.items():
            if sql.startswith(prefix):
                raise exc
        return None

    def rollback(self):
        self.rolled_back = True
        if self.rollback_error is not None:
            raise self.rollback_error

    def commit(self):
        return None

    @property
    def in_transaction(self):
        idx = min(self._reads, len(self._script) - 1)
        self._reads += 1
        return self._script[idx]


def test_d2_a_broken_sink_cannot_change_what_escapes_the_owned_preview(
        broken_sink):
    """cohort site 2 -- the preview savepoint handler, OWNED-tx branch.

    Chaining matrix: `raise cleanup_error from savepoint_error`.
    """
    import swing.trades.cohort_provenance_correction as mod

    savepoint_error = sqlite3.OperationalError("22-A3 PROBE: savepoint failed")
    rollback_error = sqlite3.OperationalError("22-A3 PROBE: rollback failed")
    proxy = _Proxy(fail_on={"SAVEPOINT": savepoint_error},
                   rollback_error=rollback_error,
                   in_transaction=(False, True))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.preview_cohort_provenance_correction(
            proxy, trade_id=1, cited_candidate_id=2,
            cited_recommendation_id=3)

    assert excinfo.value is rollback_error, (
        "the LOG SINK's exception escaped instead of the cleanup error")
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is savepoint_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ())), (
        "the log failure was swallowed silently")


def test_d3_a_broken_sink_cannot_change_what_escapes_the_caller_held_preview(
        broken_sink):
    """cohort site 3 -- the preview savepoint handler, CALLER-HELD branch.

    The escaping object is `anomaly`, NOT `savepoint_error`: the escaping
    exception is the one the `raise` statement names.  Chaining matrix:
    `raise anomaly from savepoint_error`.
    """
    import swing.trades.cohort_provenance_correction as mod

    savepoint_error = sqlite3.OperationalError("22-A3 PROBE: savepoint failed")
    # NOT a "no such savepoint" message -- that one alone is treated as
    # silence, and this test needs the LOUD path.
    anomaly = sqlite3.OperationalError("22-A3 PROBE: database is locked")
    proxy = _Proxy(fail_on={"SAVEPOINT": savepoint_error,
                            "ROLLBACK TO": anomaly},
                   in_transaction=(True,))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.preview_cohort_provenance_correction(
            proxy, trade_id=1, cited_candidate_id=2,
            cited_recommendation_id=3)

    assert excinfo.value is anomaly, (
        "the LOG SINK's exception escaped instead of the cleanup anomaly")
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is savepoint_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ())), (
        "the log failure was swallowed silently")


def test_d4_a_broken_sink_cannot_change_what_escapes_the_apply_rollback(
        broken_sink, monkeypatch):
    """cohort site 4 -- the apply-path rollback handler.

    Parametrized over BOTH message branches at the call below; the two share
    one raise statement (`raise cleanup_error from write_error`), so the
    chaining assertion is the same for both.
    """
    import swing.trades.cohort_provenance_correction as mod

    write_error = ValueError("22-A3 PROBE: the correction failed")
    rollback_error = sqlite3.OperationalError("22-A3 PROBE: rollback failed")

    def _raiser(conn, **kwargs):
        raise write_error

    monkeypatch.setattr(mod, "_correct_cohort_provenance_inner", _raiser)
    proxy = _Proxy(rollback_error=rollback_error,
                   in_transaction=(False, True, True))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.correct_cohort_provenance(
            proxy, trade_id=1, cited_candidate_id=2,
            cited_recommendation_id=3)

    assert excinfo.value is rollback_error
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is write_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ()))


def test_d4b_the_TOOK_EFFECT_branch_is_contained_too(broken_sink, monkeypatch):
    """cohort site 4's SECOND branch -- fixing one twin and leaving the other
    is this arc's named repeat failure, so both branches get a red."""
    import swing.trades.cohort_provenance_correction as mod

    write_error = ValueError("22-A3 PROBE: the correction failed")
    rollback_error = sqlite3.OperationalError("22-A3 PROBE: rollback failed")

    def _raiser(conn, **kwargs):
        raise write_error

    monkeypatch.setattr(mod, "_correct_cohort_provenance_inner", _raiser)
    proxy = _Proxy(rollback_error=rollback_error,
                   in_transaction=(False, True, False))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.correct_cohort_provenance(
            proxy, trade_id=1, cited_candidate_id=2,
            cited_recommendation_id=3)

    assert excinfo.value is rollback_error
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is write_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ()))


def test_d5_a_broken_sink_cannot_change_what_escapes_the_reader_unwind(
        broken_sink, monkeypatch):
    """cohort site 5 -- the reader's `finally` unwind, ON THE SUCCESS PATH.

    The clearest statement of what the class costs: the read SUCCEEDED and
    only the unwind failed.  Chaining matrix: a BARE `raise`, so there is no
    `from` and no other exception is in flight -- `__cause__ is None`.
    """
    import swing.trades.cohort_provenance_correction as mod

    rollback_error = sqlite3.OperationalError("22-A3 PROBE: rollback failed")
    monkeypatch.setattr(mod, "_read_provenance_corrections_inner",
                        lambda conn, **kw: [])
    proxy = _Proxy(rollback_error=rollback_error,
                   in_transaction=(False, True))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.read_provenance_corrections(proxy, trade_id=1)

    assert excinfo.value is rollback_error
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is None
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ()))


@pytest.mark.parametrize("posture", ["failure", "success"])
def test_d6_a_broken_sink_cannot_change_what_escapes_the_preview_finally(
        broken_sink, monkeypatch, posture):
    """cohort site 6 -- the preview `finally` unwind. **NOT IN THE 22-A3
    BRIEF'S ROSTER OF FIVE**, ratified 2026-09-02: a roster in a brief is a
    FLOOR.

    PARAMETRIZED OVER BOTH POSTURES because the argument for including this
    site is that its `finally` runs on the function's SUCCESS path too -- a
    test that only ever drove the failure posture would leave that specific
    claim untested.

    Chaining matrix: `raise cleanup_error` -- `__cause__ is None`; on the
    FAILURE posture `__context__ is` the authorization error (the declared
    R14-08 composition, which this arc must NOT change).
    """
    from types import SimpleNamespace

    import swing.trades.cohort_provenance_correction as mod

    auth_error = mod.CohortProvenanceCorrectionError("22-A3 PROBE: refused")

    def _authorize_failure(conn, **kwargs):
        raise auth_error

    def _authorize_success(conn, **kwargs):
        return SimpleNamespace(
            already_applied=None, anchored=object(), derived=object(),
            latch=object(), admission_tier="probe")

    monkeypatch.setattr(
        mod, "_authorize",
        _authorize_failure if posture == "failure" else _authorize_success)

    rollback_error = sqlite3.OperationalError(
        "22-A3 PROBE: ROLLBACK TO failed")
    proxy = _Proxy(fail_on={"ROLLBACK TO": rollback_error},
                   in_transaction=(True,))

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        mod.preview_cohort_provenance_correction(
            proxy, trade_id=1, cited_candidate_id=2,
            cited_recommendation_id=3)

    assert excinfo.value is rollback_error
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is None
    if posture == "failure":
        assert excinfo.value.__context__ is auth_error
    else:
        assert excinfo.value.__context__ is None
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ()))


# ===========================================================================
# (p) and (q) -- THE TWO `entry.py` `!r` FORMATTING SITES ON THE POST-COMMIT
# PATH, authorised by the 2026-09-02 ruling:
#
#   "The envelope covers outcome-corrupting exception-formatting on the
#    post-commit path of `record_entry`, wherever it occurs in the function."
#
# They get TWO SEPARATE TESTS because the two sites fail on DIFFERENT
# injections and neither test reaches the other's line -- one test for both
# would watch one of them pass for the wrong reason.
# ===========================================================================


class _HostileText(RuntimeError):
    """Both `__repr__` and `__str__` raise.  Constructible, and the values
    these two sites format are exceptions raised by arbitrary code."""

    def __repr__(self):
        raise ValueError("22-A3 PROBE: repr boom")

    def __str__(self):
        raise ValueError("22-A3 PROBE: str boom")


def test_p_a_hostile_SINK_error_cannot_break_the_degraded_result(
        tmp_path, monkeypatch):
    """The `({log_error!r})` site inside the degraded handler's own `except`.

    TWO INJECTIONS ARE REQUIRED and an earlier draft specified one: the site
    runs ONLY after a post-commit error has already entered the degraded
    handler, so a broken sink alone never reaches it on an ordinary
    successful entry.

    PRE-FIX the `{log_error!r}` formatting raises INSIDE the `except` clause,
    over a durable row, and `record_entry` reports a failure.  POST-FIX
    `safe_text` yields its fixed literal and the degraded result returns.
    """
    from tests.trades.test_22a_task9_entry_wiring import (
        ACCEPT_SESSION,
        _inject_after_the_commit,
        _trade_rows,
        accept_and_link,
        build_world,
        enter,
        req,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "a3p")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    fired = _inject_after_the_commit(
        monkeypatch, KeyboardInterrupt("on the transaction's own return"))

    class _HostileSink(logging.Handler):
        def emit(self, record):
            raise _HostileText("22-A3 PROBE: hostile sink")

    sink = _HostileSink(level=logging.ERROR)
    root = logging.getLogger()
    root.addHandler(sink)
    try:
        result = enter(conn, cfg, req())
    finally:
        root.removeHandler(sink)

    assert fired, "the planted exception never landed"
    assert result.trade_id is not None and result.trade_id > 0
    assert len(result.post_commit_warnings) == 2, result.post_commit_warnings
    assert any("DURABLE" in w for w in result.post_commit_warnings)
    assert any("could not be emitted" in w
               for w in result.post_commit_warnings)
    assert any("both raised" in w for w in result.post_commit_warnings), (
        result.post_commit_warnings)
    assert _trade_rows(conn) == 1


def test_q_a_hostile_POST_COMMIT_error_cannot_break_the_degraded_result(
        tmp_path, monkeypatch):
    """The `({post_commit_error!r})` site that BUILDS the degraded warning.

    NO broken sink is installed: this site raises BEFORE any `EntryResult`
    exists, so the pre-fix failure is NOT the same as (p)'s.

    PRE-FIX the warning-text construction raises over a committed row and
    `record_entry` reports a failure.  POST-FIX `safe_text` yields its fixed
    literal, the degraded result returns, and exactly one durable row exists.
    """
    from tests.trades.test_22a_task9_entry_wiring import (
        ACCEPT_SESSION,
        _inject_after_the_commit,
        _trade_rows,
        accept_and_link,
        build_world,
        enter,
        req,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "a3q")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    fired = _inject_after_the_commit(
        monkeypatch, _HostileText("22-A3 PROBE: hostile post-commit error"))

    result = enter(conn, cfg, req())

    assert fired, "the planted exception never landed"
    assert result.trade_id is not None and result.trade_id > 0
    durable = [w for w in result.post_commit_warnings if "DURABLE" in w]
    assert len(durable) == 1, result.post_commit_warnings
    assert "both raised" in durable[0], durable[0]
    assert _trade_rows(conn) == 1
