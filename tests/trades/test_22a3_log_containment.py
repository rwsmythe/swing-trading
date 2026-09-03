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
