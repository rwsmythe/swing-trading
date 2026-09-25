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
