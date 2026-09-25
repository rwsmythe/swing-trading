"""22-F T-G0 -- unit tests for the web close-after-commit helper,
`swing/web/routes/__init__.py::close_after_commit(conn, log, *, what)`.

It closes the connection; on a close failure (an `Exception`) it logs ONE
contained ERROR record and returns the one-line notice
`"<what> IS recorded; the database connection could not be closed cleanly
(see the log)."`.  An INTERRUPT at the close (a BaseException that is not an
Exception) is logged with the same record, the interrupt named, and
re-raised BARE (STOP-6, CHARC: the operator's stop signal is never
contained).  A working close returns None and logs nothing.  Driven with the closing proxy
(`FailingVerbsConn`); every case asserts exactly one `close()` recorded.
"""
from __future__ import annotations

import logging
import sqlite3

import pytest

from tests._22f_proxies import FailingVerbsConn

_LOG = logging.getLogger("tests.22f.close_after_commit")


def _helper():
    from swing.web.routes import close_after_commit
    return close_after_commit


def test_working_close_returns_none_and_logs_nothing(caplog):
    proxy = FailingVerbsConn(sqlite3.connect(":memory:"))
    with caplog.at_level(logging.ERROR):
        assert _helper()(proxy, _LOG, what="The stop change") is None
    assert proxy.calls["close"] == 1
    assert caplog.records == []


def test_close_failure_returns_the_notice_and_logs_once(caplog):
    proxy = FailingVerbsConn(sqlite3.connect(":memory:"), fail_close=True)
    with caplog.at_level(logging.ERROR):
        notice = _helper()(proxy, _LOG, what="The stop change")
    assert proxy.calls["close"] == 1
    assert notice == ("The stop change IS recorded; the database connection "
                      "could not be closed cleanly (see the log).")
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "planted on close" in errors[0].getMessage()


def test_an_interrupt_at_the_close_is_logged_and_re_raised_bare(caplog):
    """STOP-6 (CHARC): `except Exception` keeps the containment above; an
    INTERRUPT at the close is logged with the same record (the interrupt
    named) and re-raised BARE -- never swallowed into the notice."""
    class _InterruptOnClose(FailingVerbsConn):
        def close(self) -> None:
            self.calls["close"] += 1
            self._real.close()
            raise KeyboardInterrupt("planted interrupt on close")

    proxy = _InterruptOnClose(sqlite3.connect(":memory:"))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KeyboardInterrupt,
                           match="planted interrupt on close") as info:
            _helper()(proxy, _LOG, what="The snapshot")
    assert proxy.calls["close"] == 1
    assert info.value.__cause__ is None
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert "The snapshot IS recorded and CLOSING the database connection" in msg
    assert "KeyboardInterrupt" in msg


def test_a_raising_log_sink_does_not_make_the_helper_raise():
    class _Boom(logging.Handler):
        def emit(self, record):
            raise RuntimeError("sink down")

    log = logging.getLogger("tests.22f.close_after_commit.boom")
    log.propagate = False
    handler = _Boom()
    log.addHandler(handler)
    try:
        proxy = FailingVerbsConn(sqlite3.connect(":memory:"), fail_close=True)
        notice = _helper()(proxy, log, what="The pin")
    finally:
        log.removeHandler(handler)
    assert proxy.calls["close"] == 1
    assert notice is not None and notice.startswith("The pin IS recorded")
