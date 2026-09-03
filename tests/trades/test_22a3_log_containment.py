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
# (d2)-(d6) -- the FIVE cleanup HANDLERS in
# `cohort_provenance_correction.py`, reached through SIX branch-specific
# call expressions (site 4 branches on `conn.in_transaction`). With the ONE
# handler in `entry.py` that d1 drives, the roster is SIX handlers / EIGHT
# call expressions -- stated precisely because a completeness claim that
# cannot keep its own arithmetic straight is the exact condition under
# which a seventh site is omitted unnoticed (Codex A3R2-06).
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


# ===========================================================================
# CODEX ROUND 1 -- the findings that survived adjudication, each with a test
# that was RED against the shipped code and is GREEN against the fix.
# ===========================================================================


class _Decoded:
    def decode(self, *a, **k):
        return "bad \ud800 surrogate"


class _PoisonStr(str):
    """A `str` SUBCLASS overriding `encode`. Legal: `__repr__` need only
    return `str`, and a subclass IS a `str`."""

    def encode(self, *a, **k):
        return _Decoded()


class _PoisonRepr(RuntimeError):
    def __repr__(self):
        return _PoisonStr("poison-repr")


def test_A3_AR_01_ascii_safe_is_not_defeated_by_a_hostile_str_subclass():
    """Codex A3-AR-01 (MAJOR), REPRODUCED BY EXECUTION before the fix.

    `text.encode(...)` and `.decode(...)` are VIRTUAL. A `str` subclass can
    override `encode` to return an object whose `decode` returns a lone
    surrogate, so the arc's own coercion returned a NON-ASCII string.

    PRE-fix measured: `ascii_safe(_PoisonStr(...))` returned
    `'bad \\ud800 surrogate'` with `.isascii()` False, and `safe_text` of an
    exception whose `__repr__` returns that subclass did the same -- which
    reaches `HTMLResponse` through the route's degraded path and raises
    `UnicodeEncodeError` INSIDE the outer `except`, where nothing catches it.
    POST-fix both are exact ASCII `str`.
    """
    from swing.trades.entry import ascii_safe, safe_text

    out = ascii_safe(_PoisonStr("poison"))
    assert type(out) is str
    assert out.isascii(), out
    assert "ud800" not in out, (
        "the subclass override supplied the payload instead of the base slot")

    out2 = safe_text(_PoisonRepr("x"))
    assert type(out2) is str
    assert out2.isascii(), out2


def test_A3_AR_01b_the_postcondition_is_checked_not_argued():
    """The helper's contract is "the result is safe to interpolate", so it
    ESTABLISHES that at the boundary rather than reasoning about which
    methods the base slots dispatch to."""
    from swing.trades.entry import ascii_safe

    class _NotAStr:
        def encode(self, *a, **k):
            raise AssertionError("must not be reached via the base slot")

    out = ascii_safe(_NotAStr())          # type: ignore[arg-type]
    assert out == "<a value that could not be rendered as text>"


def test_A3_AR_03_a_hostile_container_notes_does_not_lose_the_sink_failure(
        broken_sink):
    """Codex A3-AR-03 (MINOR), REPRODUCED BY EXECUTION before the fix.

    A `tuple` SUBCLASS whose `__iter__` raises made `list(existing)` raise
    inside the repair branch, and the outer guard then discarded the sink
    failure SILENTLY -- the invisible failure this helper exists to refuse.

    POST-fix the note lands: anything that is not one of the four EXACT
    built-in containers is rendered through `safe_text`, which is total.
    """
    from swing.trades.entry import log_contained_note

    class _BadIter(tuple):
        def __iter__(self):
            raise TypeError("iter raises")

    escaping = RuntimeError("cleanup")
    escaping.__notes__ = _BadIter(("a",))
    log_contained_note(logging.getLogger("t22a3.baditer"), escaping, "boom")

    notes = BaseException.__getattribute__(escaping, "__notes__")
    assert isinstance(notes, list)
    assert any("could not be emitted" in n for n in notes), notes


def test_A3_AR_03b_a_notes_DATA_DESCRIPTOR_is_the_declared_residue(
        broken_sink):
    """The narrowed limitation, pinned so it cannot silently widen again.

    An exception defining `__notes__` as a DATA DESCRIPTOR whose getter AND
    setter both raise cannot receive a note at all -- the base slots consult
    the descriptor, so there is no representation left to write into. This is
    the THIRD time this limitation's stated reason has been disproved by
    review, and what the test pins is the property that still holds: the
    helper RETURNS NORMALLY and the escaping exception is untouched.
    """
    from swing.trades.entry import log_contained_note

    class _DescriptorNotes(RuntimeError):
        @property
        def __notes__(self):
            raise TypeError("notes getter raises")

        @__notes__.setter
        def __notes__(self, value):
            raise TypeError("notes setter raises")

    escaping = _DescriptorNotes("x")
    log_contained_note(logging.getLogger("t22a3.desc"), escaping, "boom")

    assert type(escaping) is _DescriptorNotes
    assert escaping.args == ("x",)


def test_A3_AR_06_the_log_failure_wording_is_OBSERVATION_ONLY(broken_sink):
    """Codex A3-AR-06 (MINOR), REPRODUCED BY EXECUTION before the fix.

    `logger.error` raising means A HANDLER raised -- NOT that no sink received
    the record. Measured: an earlier handler emitted the record successfully
    before a later one raised. A flat "could not be emitted" is the same
    after-effect fallacy this project already corrected for rollback messages,
    and a cleanup warning that is WRONG about the state teaches an operator to
    distrust the right ones.

    PRE-fix the note said only "could not be emitted"; POST-fix it names the
    OBSERVATION (a handler raised) and declines to claim the outcome.
    """
    from swing.trades.entry import log_contained_note

    escaping = KeyError("cleanup")
    log_contained_note(logging.getLogger("t22a3.wording"), escaping, "boom")
    note = "\n".join(getattr(escaping, "__notes__", ()))

    assert "a logging handler RAISED" in note, note
    assert "Some sinks may have received the record" in note, note


def test_A3_AR_06b_an_EARLIER_handler_can_emit_before_a_LATER_one_raises():
    """The measurement the wording change rests on, kept as a test so the
    justification cannot rot into an assertion nobody re-checks."""
    emitted: list[str] = []

    class _Good(logging.Handler):
        def emit(self, record):
            emitted.append(record.getMessage())

    good, bad = _Good(level=logging.ERROR), _BrokenSink(level=logging.ERROR)
    root = logging.getLogger()
    root.addHandler(good)
    root.addHandler(bad)
    try:
        with pytest.raises(RuntimeError):
            logging.getLogger("t22a3.order").error("the record")
    finally:
        root.removeHandler(good)
        root.removeHandler(bad)

    assert emitted == ["the record"], (
        "the GOOD handler emitted before the bad one raised, so "
        "'could not be emitted' would be a false statement")


# ===========================================================================
# CODEX ROUND 2.
# ===========================================================================


class _FormattingSink(logging.Handler):
    """A handler that FORMATS the record before failing.

    The round-1 `_BrokenSink` raises before formatting, so it never exercised
    `__str__` on the exception objects passed as `%s` args -- which is exactly
    how the preservation claim went unmeasured for two rounds.
    """

    def emit(self, record):
        record.getMessage()
        raise RuntimeError("22-A3 PROBE: sink failed AFTER formatting")


def test_A3R2_02_a_FORMATTING_sink_cannot_corrupt_the_escaping_evidence():
    """Codex A3R2-02 (MAJOR), REPRODUCED BY EXECUTION before the fix.

    `logger.error(msg, *args)` hands the escaping exception to
    caller-installed handlers, and a handler that FORMATS the record calls
    `__str__` on it -- which an exception may legally override to MUTATE
    ITSELF and then raise.

    PRE-fix measured: `args` went from `('the real args',)` to
    `('CORRUPTED',)` and `__cause__` from a `ValueError` to `None`, while the
    sink's own exception was contained exactly as advertised. **Containing
    the sink's exception is not the same as preserving the evidence** -- and
    at the rollback and savepoint sites the original error and its chaining
    are what say whether a transaction may still be open.
    """
    from swing.trades.entry import log_contained_note

    class _SelfMutating(RuntimeError):
        def __str__(self):
            self.args = ("CORRUPTED",)
            self.__cause__ = None
            self.__context__ = None
            raise RuntimeError("format failed")

    cause = ValueError("the real cause")
    context = KeyError("the real context")
    escaping = _SelfMutating("the real args")
    escaping.__cause__ = cause
    escaping.__context__ = context

    sink = _FormattingSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        log_contained_note(
            logging.getLogger("t22a3.mutating"), escaping, "boom %s", escaping)
    finally:
        logging.getLogger().removeHandler(sink)

    assert escaping.args == ("the real args",), escaping.args
    assert escaping.__cause__ is cause
    assert escaping.__context__ is context


def test_A3R2_03_a_SYNTHESIZING_notes_descriptor_does_not_bless_a_lost_note():
    """Codex A3R2-03 (MINOR), REPRODUCED BY EXECUTION before the fix.

    `BaseException.add_note` can RETURN SUCCESSFULLY and still lose the note:
    a `__notes__` DATA DESCRIPTOR whose getter SYNTHESIZES a fresh list has
    the note appended to a temporary that is then discarded. PRE-fix the
    helper took that success on trust and returned; POST-fix it VERIFIES by
    reading the note back, so the repair branch runs and the note lands
    whenever the setter is willing to store it.
    """
    from swing.trades.entry import log_contained_note

    class _CopyingNotes(RuntimeError):
        """Getter returns a COPY (so `add_note` appends to a temporary);
        setter stores for real (so the verified repair CAN land it)."""

        _stored: list

        def __init__(self, *a):
            super().__init__(*a)
            object.__setattr__(self, "_stored", [])

        @property
        def __notes__(self):
            return list(object.__getattribute__(self, "_stored"))

        @__notes__.setter
        def __notes__(self, value):
            object.__setattr__(self, "_stored", list(value))

    sink = _BrokenSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        escaping = _CopyingNotes("x")
        log_contained_note(
            logging.getLogger("t22a3.copying"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)

    notes = BaseException.__getattribute__(escaping, "__notes__")
    assert any("could not be emitted" in n for n in notes), (
        f"the attach was taken on trust and the note was lost: {notes}")


def test_A3R2_03b_a_DISCARDING_descriptor_is_the_declared_residue():
    """The narrowed residue, pinned. A setter that SILENTLY DISCARDS leaves
    nowhere to write, so the note is genuinely unattachable -- but the
    load-bearing property still holds and the helper still returns."""
    from swing.trades.entry import log_contained_note

    class _Discarding(RuntimeError):
        @property
        def __notes__(self):
            return []

        @__notes__.setter
        def __notes__(self, value):
            pass

    sink = _BrokenSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        escaping = _Discarding("x")
        log_contained_note(
            logging.getLogger("t22a3.discard"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)

    assert type(escaping) is _Discarding
    assert escaping.args == ("x",)


@pytest.mark.parametrize("still_open", [True, False],
                         ids=["still-open-branch", "took-effect-branch"])
def test_A3R2_05_the_entry_cleanup_preserves_ALL_FOUR_evidence_fields(
        still_open):
    """Codex A3R2-05 (MINOR).

    The (d) tests assert identity and SOME chaining; none asserted `args`,
    and several omitted `__context__` -- so the A3R2-02 corruption passed the
    whole suite. This drives the REAL `_entry_transaction` cleanup through a
    FORMATTING sink with a SELF-MUTATING cleanup error, so the corruption is
    actually reachable here and every field the module docstring claims is
    asserted against it.

    A first draft of this test asserted the four fields over an ORDINARY
    exception and therefore passed under its own mutation -- coverage wearing
    a discriminator's costume. Caught by running the mutation.
    """
    from swing.trades.entry import _CommitOutcome, _entry_transaction

    class _MutatingOperationalError(sqlite3.OperationalError):
        def __str__(self):
            self.args = ("CORRUPTED",)
            self.__cause__ = None
            self.__context__ = None
            raise RuntimeError("format failed")

    proxy = _RollbackRaises(in_transaction_after_rollback=still_open)
    proxy.rollback_error = _MutatingOperationalError(
        "22-A3 PROBE: rollback failed")
    body_error = ValueError("22-A3 PROBE: the write failed")

    sink = _FormattingSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        with pytest.raises(sqlite3.OperationalError) as excinfo:
            with _entry_transaction(proxy, immediate=True,
                                    outcome=_CommitOutcome()):
                raise body_error
    finally:
        logging.getLogger().removeHandler(sink)

    escaped = excinfo.value
    assert escaped is proxy.rollback_error
    assert type(escaped) is _MutatingOperationalError
    assert escaped.args == ("22-A3 PROBE: rollback failed",), escaped.args
    assert escaped.__cause__ is body_error
    assert escaped.__context__ is body_error


# ===========================================================================
# CODEX ROUND 3 -- three of these are residuals of ROUND 2's own fixes.
# ===========================================================================


def test_A3R3_02_a_hostile_NOTES_descriptor_cannot_corrupt_evidence_LATER():
    """Codex A3R3-02 (MAJOR).

    Round 2 restored the evidence immediately after the log call, which left
    everything AFTER it outside the boundary: `safe_text(log_error)`,
    `add_note`, the read-back, and the repair's own read and write. A hostile
    `__notes__` descriptor mutates from its GETTER, which runs during
    `add_note` -- i.e. strictly after the sole restoration.

    PRE-fix the corruption survives; POST-fix the restore is a `finally` over
    the whole sequence.
    """
    from swing.trades.entry import log_contained_note

    class _MutatingNotes(RuntimeError):
        @property
        def __notes__(self):
            BaseException.__setattr__(self, "args", ("CORRUPTED",))
            BaseException.__setattr__(self, "__cause__", None)
            BaseException.__setattr__(self, "__context__", None)
            return []

        @__notes__.setter
        def __notes__(self, value):
            pass

    cause = ValueError("the real cause")
    context = KeyError("the real context")
    escaping = _MutatingNotes("the real args")
    escaping.__cause__ = cause
    escaping.__context__ = context

    sink = _BrokenSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        log_contained_note(
            logging.getLogger("t22a3.mutnotes"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)

    assert escaping.args == ("the real args",), escaping.args
    assert escaping.__cause__ is cause
    assert escaping.__context__ is context


def test_A3R3_03_one_unreadable_field_does_not_disable_the_others():
    """Codex A3R3-03 (MAJOR).

    All three fields were read inside ONE `try`, so a single hostile `args`
    data descriptor returned `None` for the whole snapshot and preserved
    NOTHING -- widening the residue from "the note cannot attach" to "the
    chaining can be destroyed".

    Here `args` is unreadable AND a formatting handler drives a self-mutating
    `__str__` that clears the two perfectly writable chaining fields.
    PRE-fix both are lost; POST-fix both are restored, per field.
    """
    from swing.trades.entry import log_contained_note

    class _UnreadableArgs(RuntimeError):
        @property
        def args(self):
            raise TypeError("args getter raises")

        @args.setter
        def args(self, value):
            pass

        def __str__(self):
            BaseException.__setattr__(self, "__cause__", None)
            BaseException.__setattr__(self, "__context__", None)
            raise RuntimeError("format failed")

    cause = ValueError("the real cause")
    context = KeyError("the real context")
    escaping = _UnreadableArgs()
    escaping.__cause__ = cause
    escaping.__context__ = context

    sink = _FormattingSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        log_contained_note(
            logging.getLogger("t22a3.unreadable"), escaping, "boom %s",
            escaping)
    finally:
        logging.getLogger().removeHandler(sink)

    assert escaping.__cause__ is cause, (
        "one unreadable field disabled preservation of the others")
    assert escaping.__context__ is context


def test_A3R3_04_a_STATEFUL_descriptor_that_discards_once_still_gets_the_note():
    """Codex A3R3-04 (MINOR).

    Read-back gated only the FIRST attach, so a descriptor that discards its
    first setter call and stores the second silently lost the note while the
    comments claimed the attachment was verified. ONE bounded retry closes it.
    """
    from swing.trades.entry import log_contained_note

    class _DiscardsFirstWrite(RuntimeError):
        def __init__(self, *a):
            super().__init__(*a)
            object.__setattr__(self, "_stored", [])
            object.__setattr__(self, "_writes", 0)

        @property
        def __notes__(self):
            return list(object.__getattribute__(self, "_stored"))

        @__notes__.setter
        def __notes__(self, value):
            n = object.__getattribute__(self, "_writes") + 1
            object.__setattr__(self, "_writes", n)
            if n >= 2:                      # the FIRST write is discarded
                object.__setattr__(self, "_stored", list(value))

    sink = _BrokenSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        escaping = _DiscardsFirstWrite("x")
        log_contained_note(
            logging.getLogger("t22a3.stateful"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)

    notes = BaseException.__getattribute__(escaping, "__notes__")
    assert any("could not be emitted" in n for n in notes), (
        f"the repair write was not verified and the note was lost: {notes}")


# ===========================================================================
# CODEX ROUND 4 -- three more residuals of the loop's own hardening.
# ===========================================================================


def test_A3R4_01_a_DECOY_evidence_property_cannot_defeat_the_snapshot():
    """Codex A3R4-01 (MAJOR), VERIFIED BY EXECUTION, and it corrects a claim
    this module carried from the day the idiom was written.

    `BaseException.__getattribute__` does NOT bypass a subclass DATA
    DESCRIPTOR -- it performs ordinary lookup on the type. The claim held for
    `__notes__` (no base descriptor; a plain instance attribute) and was
    wrongly generalised to `args` / `__cause__` / `__context__`, which DO have
    base descriptors.

    The discriminator is a DECOY: `__cause__`'s getter returns a fixed
    stand-in while its setter writes the real slot, and a formatting handler
    drives a `__str__` that clears the real slot.

      PRE-fix  the snapshot captures the DECOY, the comparison after the log
               sees the DECOY again, concludes "unchanged", and skips the
               write -- so the real slot stays CLEARED.
      POST-fix both go through `BaseException.__dict__[name].__get__/__set__`,
               which run no user code, so the real cause is seen to have
               changed and is put back.

    A first draft of this test used a property whose SETTER was a no-op, so
    the real slot was never corrupted and the test passed under its own
    mutation. Caught by running the mutation -- the third time in this loop.
    """
    from swing.trades.entry import log_contained_note

    _DECOY = ValueError("a decoy cause")
    _CAUSE_SLOT = BaseException.__dict__["__cause__"]

    class _DecoyCause(RuntimeError):
        @property
        def __cause__(self):
            return _DECOY

        @__cause__.setter
        def __cause__(self, value):
            _CAUSE_SLOT.__set__(self, value)

        def __str__(self):
            _CAUSE_SLOT.__set__(self, None)
            raise RuntimeError("format failed")

    cause = ValueError("the real cause")
    escaping = _DecoyCause("the real args")
    _CAUSE_SLOT.__set__(escaping, cause)

    sink = _FormattingSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        log_contained_note(
            logging.getLogger("t22a3.decoy"), escaping, "boom %s", escaping)
    finally:
        logging.getLogger().removeHandler(sink)

    assert _CAUSE_SLOT.__get__(escaping, type(escaping)) is cause, (
        "the snapshot read a DECOY through the subclass property, so the "
        "restore concluded nothing had changed and the REAL slot stayed "
        "cleared")


def test_A3R4_02_args_cannot_hold_a_mutable_value_MEASURED():
    """Codex A3R4-02's premise, HALF REFUTED by measurement.

    The finding said `BaseException.args` "can legally be assigned a mutable
    value". It cannot: the base setter COERCES to a tuple. This test pins the
    measurement, because the declared residue (an element INSIDE the tuple
    being mutated in place) rests on it -- and a residue whose justification
    is a language fact should fail loudly if that fact ever changes.
    """
    escaping = RuntimeError("x")
    escaping.args = [1, 2]
    assert type(escaping.args) is tuple
    assert escaping.args == (1, 2)


def test_A3R4_03_an_EQ_spoofing_note_cannot_fake_a_landed_note():
    """Codex A3R4-03 (MINOR).

    `any(n is note or n == note ...)` let a `str` subclass whose `__eq__`
    returns True for everything read as "the note landed", so the repair was
    skipped even though its setter WOULD have stored the real note -- a false
    success in the one helper whose job is refusing invisible failures.
    """
    from swing.trades.entry import log_contained_note

    class _EqualEverything(str):
        def __eq__(self, other):
            return True

        def __hash__(self):
            return 0

    class _SpoofingNotes(RuntimeError):
        def __init__(self, *a):
            super().__init__(*a)
            object.__setattr__(self, "_stored", [_EqualEverything("nope")])

        @property
        def __notes__(self):
            return list(object.__getattribute__(self, "_stored"))

        @__notes__.setter
        def __notes__(self, value):
            object.__setattr__(self, "_stored", list(value))

    sink = _BrokenSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        escaping = _SpoofingNotes("x")
        log_contained_note(
            logging.getLogger("t22a3.spoof"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)

    stored = object.__getattribute__(escaping, "_stored")
    assert any(type(n) is str and "could not be emitted" in n for n in stored), (
        f"an equality-spoofing placeholder faked the attach: {stored!r}")


def test_A3R5_03_the_post_commit_error_is_RENDERED_ONCE_not_handed_to_logging(
        tmp_path, monkeypatch):
    """Codex A3R5-03 (MINOR), post-convergence.

    `record_entry`'s degraded handler rendered the post-commit error with
    `safe_text` for the WARNING but still passed the RAW OBJECT to
    `log.error`, so a FORMATTING handler invoked its `__str__` a second time
    -- which a hostile exception can use to mutate itself or raise, obscuring
    what actually failed. The arc's other diagnostic paths were corrected a
    round earlier; this one was missed.

    PRE-fix `__str__` is called once by the formatting handler; POST-fix the
    handler formats a plain `str` and the exception is never asked again.
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

    calls = {"repr": 0, "str": 0}

    class _Counting(RuntimeError):
        def __repr__(self):
            calls["repr"] += 1
            return "<counting error>"

        def __str__(self):
            calls["str"] += 1
            return "<counting error str>"

    conn, cfg, candidate_id = build_world(tmp_path, "a3r503")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    fired = _inject_after_the_commit(monkeypatch, _Counting("probe"))

    sink = _FormattingSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    try:
        result = enter(conn, cfg, req())
    finally:
        logging.getLogger().removeHandler(sink)

    assert fired, "the planted exception never landed"
    assert result.trade_id is not None
    assert _trade_rows(conn) == 1
    assert calls["str"] == 0, (
        f"the RAW exception was handed to a formatting logging handler: "
        f"{calls}")
