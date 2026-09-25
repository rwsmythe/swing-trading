"""22-F T-G0 -- unit tests for the CLI close-after-durable helper,
`swing/cli.py::_close_after_writes(conn, *, durable, pending_refusal)`
(S-B02 exactly; RULING B item 2, the `trade review` shape).

Branches, each driven with the closing proxy (`FailingVerbsConn`; its
`close()` releases the real handle and then raises when `fail_close=True`):

* nothing durable, no refusal -> a bare `conn.close()`: a close failure
  propagates UNCHANGED (byte-unchanged branch);
* a refusal in flight -> S-R8: the refusal text survives with the close
  failure named, CHAINED from the close error;
* durable, no refusal -> contained: one ERROR record, a
  `WARN: the write IS recorded; the connection close failed: ...` line on
  the error sink, and a normal return (exit 0 at the root).

Each branch also runs with a WORKING close (the helper then returns quietly).
Every case asserts the proxy recorded exactly one `close()`.
"""
from __future__ import annotations

import logging
import sqlite3

import click
import pytest

from tests._22f_proxies import FailingVerbsConn


def _proxy(fail: bool) -> FailingVerbsConn:
    return FailingVerbsConn(sqlite3.connect(":memory:"), fail_close=fail)


def _helper():
    from swing.cli import _close_after_writes
    return _close_after_writes


def test_nothing_durable_no_refusal_close_failure_propagates_unchanged(caplog):
    proxy = _proxy(True)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.OperationalError,
                           match="planted on close") as info:
            _helper()(proxy, durable=False, pending_refusal=None)
    assert proxy.calls["close"] == 1
    assert info.value.__cause__ is None
    assert caplog.records == []


def test_refusal_in_flight_keeps_its_text_and_chains_the_close_error():
    proxy = _proxy(True)
    refusal = click.ClickException("Trade 7 REFUSED: already closed")
    with pytest.raises(click.ClickException) as info:
        _helper()(proxy, durable=False, pending_refusal=refusal)
    assert proxy.calls["close"] == 1
    msg = info.value.format_message()
    assert msg.startswith("Trade 7 REFUSED: already closed; ")
    assert "the connection close also failed" in msg
    assert "planted on close" in msg
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)


def test_refusal_wins_even_when_something_was_durable():
    """S-B02 (i) precedes (ii): a named refusal is raised even if an earlier
    write committed (the `trade review` intent-refused shape)."""
    proxy = _proxy(True)
    refusal = click.ClickException("Intent change REFUSED: x")
    with pytest.raises(click.ClickException, match="also failed"):
        _helper()(proxy, durable=True, pending_refusal=refusal)
    assert proxy.calls["close"] == 1


def test_durable_close_failure_is_contained_warned_and_returns(capsys, caplog):
    proxy = _proxy(True)
    with caplog.at_level(logging.ERROR):
        assert _helper()(proxy, durable=True, pending_refusal=None) is None
    assert proxy.calls["close"] == 1
    err = capsys.readouterr().err
    assert ("WARN: the write IS recorded; the connection close failed: "
            in err)
    assert "planted on close" in err
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "IS recorded" in errors[0].getMessage()


@pytest.mark.parametrize("durable,refusal", [
    (False, None), (True, None),
    (False, click.ClickException("r")), (True, click.ClickException("r")),
])
def test_working_close_is_quiet_on_every_branch(durable, refusal, capsys,
                                                caplog):
    proxy = _proxy(False)
    with caplog.at_level(logging.ERROR):
        assert _helper()(proxy, durable=durable,
                         pending_refusal=refusal) is None
    assert proxy.calls["close"] == 1
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    assert caplog.records == []


def test_durable_close_failure_names_the_recorded_write_when_given(capsys,
                                                                   caplog):
    """STOP-5 (CHARC, `swing eval`): `recorded=` names the durable write in
    the WARN line and the ERROR record; the WARN prefix is unchanged."""
    proxy = _proxy(True)
    with caplog.at_level(logging.ERROR):
        assert _helper()(proxy, durable=True, pending_refusal=None,
                         recorded="evaluation run 42") is None
    assert proxy.calls["close"] == 1
    err = capsys.readouterr().err
    assert ("WARN: the write IS recorded; the connection close failed: "
            in err)
    assert "the recorded write: evaluation run 42" in err
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "evaluation run 42" in errors[0].getMessage()


# ---- STOP-6 (CHARC, 2026-09-25): an INTERRUPT at the close -----------------
# A BaseException that is not an Exception (KeyboardInterrupt, SystemExit,
# GeneratorExit) is the operator's STOP SIGNAL: never swallowed, never
# retyped.  `except Exception` keeps the three branches above exactly.

class _InterruptOnClose(FailingVerbsConn):
    """The real close runs (the handle is released), then the interrupt."""

    def close(self) -> None:
        self.calls["close"] += 1
        self._real.close()
        raise KeyboardInterrupt("planted interrupt on close")


def _interrupt_proxy() -> _InterruptOnClose:
    return _InterruptOnClose(sqlite3.connect(":memory:"))


@pytest.mark.parametrize("durable", [False, True])
def test_interrupt_at_close_with_refusal_pending_is_re_raised_from_the_refusal(
        durable, capsys, caplog):
    """Refusal pending -> ONE record naming the refusal and the interrupt,
    then the INTERRUPT itself re-raised `from` the refusal (not a
    ClickException carrying it as text)."""
    proxy = _interrupt_proxy()
    refusal = click.ClickException("Trade 7 REFUSED: already closed")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KeyboardInterrupt,
                           match="planted interrupt on close") as info:
            _helper()(proxy, durable=durable, pending_refusal=refusal)
    assert proxy.calls["close"] == 1
    assert info.value.__cause__ is refusal
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert "Trade 7 REFUSED: already closed" in msg
    assert "KeyboardInterrupt" in msg
    assert "WARN" not in capsys.readouterr().err


def test_interrupt_at_close_after_durable_write_warns_then_re_raises_bare(
        capsys, caplog):
    """Durable, no refusal -> the ERROR record and the WARN line (the durable
    fact IS still stated), then the interrupt re-raised BARE."""
    proxy = _interrupt_proxy()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KeyboardInterrupt,
                           match="planted interrupt on close") as info:
            _helper()(proxy, durable=True, pending_refusal=None,
                      recorded="evaluation run 42")
    assert proxy.calls["close"] == 1
    assert info.value.__cause__ is None
    err = capsys.readouterr().err
    assert "WARN: the write IS recorded; " in err
    assert "KeyboardInterrupt" in err
    assert "the recorded write: evaluation run 42" in err
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "IS recorded" in errors[0].getMessage()
    assert "KeyboardInterrupt" in errors[0].getMessage()
    assert "evaluation run 42" in errors[0].getMessage()


def test_interrupt_at_close_nothing_durable_no_refusal_propagates_bare(
        capsys, caplog):
    """The third state -- the byte-unchanged bare close: the interrupt
    propagates as it always has, no record, no WARN (a PIN on both trees)."""
    proxy = _interrupt_proxy()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KeyboardInterrupt) as info:
            _helper()(proxy, durable=False, pending_refusal=None)
    assert proxy.calls["close"] == 1
    assert info.value.__cause__ is None
    assert caplog.records == []
    assert capsys.readouterr().err == ""
