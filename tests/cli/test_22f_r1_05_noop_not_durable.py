"""22-F R1-05 (Reviewer A round 1; CHARC-ruled at the round 1 gate) -- a
root's `durable` flag is bound from what the WRITER REPORTS, never from
reaching the line after the call.  Three CLI roots returned from a NO-OP
with `durable = True`, so a close failure after a no-op printed "WARN: the
write IS recorded" over a write that never happened:

* `trade stop-adjust` -- `adjust_stop`'s equal-stop return (it now returns
  `bool`, the GRANTED amendment to `swing/trades/stop_adjust.py`);
* `journal correct-cohort-provenance` -- the service's `already_applied`
  result;
* `journal discrepancy resolve-ambiguity` -- `apply_tier2_resolution`'s
  step-2 terminal-state idempotent return (`reconciliation_auto_correct.py`
  step 2, `if disc.resolution in _TERMINAL_RESOLUTIONS`), bound from the
  CLI's own pre-read of the same predicate taken before the call (its
  `CorrectionResult` carries no structured idempotent fact -- only prose
  `notes`).

Each case drives the NO-OP with every connection's close failing.  PRE-FIX:
exit 0 and the false WARN.  POST-FIX: nothing durable and no refusal -> the
S-B02 bare close, byte-unchanged: the close error propagates exactly as it
did before the arc, and NO "IS recorded" text.  The WRITE input with a
failing close keeps its WARN and a fresh read of the write: that is G1-a of
`tests/cli/test_22f_close_after_durable.py`, run over the same three roots.
Did-it-fire: every case asserts the failing proxies recorded >= 1 close.
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.cli import main
from tests.cli.test_22f_close_after_durable import (
    _PLANTED,
    _WARN,
    ROOTS,
    _closes,
    _failing_close,
)

_BY_ID = {r.id: r for r in ROOTS}


def _stop_noop_argv(w) -> list:
    return ["--config", str(w.cfg), "trade", "stop-adjust", "--trade-id", "1",
            "--new-stop", "170.0", "--rationale", "manual-trail"]


# root id -> (the no-op argv, whether the no-op needs a first clean run)
_NOOPS = {
    "trade-stop-adjust": (_stop_noop_argv, False),
    "journal-correct-cohort-provenance": (None, True),
    "discrepancy-resolve-ambiguity": (None, True),
}


@pytest.mark.parametrize("root_id", sorted(_NOOPS))
def test_r1_05_noop_with_close_failure_reports_no_write(root_id, tmp_path,
                                                         monkeypatch):
    root = _BY_ID[root_id]
    noop_argv, first_run = _NOOPS[root_id]
    w = root.world(tmp_path, monkeypatch)
    argv = (noop_argv or root.argv)(w)
    if first_run:
        first = w.runner.invoke(main, argv, input=root.input)
        assert first.exit_code == 0, first.output
    before = root.probe(w)
    built = _failing_close(monkeypatch, root.target, root.nth)
    result = w.runner.invoke(main, argv, input=root.input)
    assert _closes(built, root.nth) >= 1
    assert _WARN not in result.output
    assert "IS recorded" not in result.output
    assert isinstance(result.exception, sqlite3.OperationalError), (
        result.output, repr(result.exception))
    assert _PLANTED in str(result.exception)
    assert root.probe(w) == before  # a no-op: nothing changed


def test_r1_05_stop_noop_without_close_failure_is_unchanged(tmp_path,
                                                            monkeypatch):
    """PIN (both trees): the equal-stop no-op with a clean close exits 0 with
    the command's normal echo."""
    root = _BY_ID["trade-stop-adjust"]
    w = root.world(tmp_path, monkeypatch)
    result = w.runner.invoke(main, _stop_noop_argv(w))
    assert result.exit_code == 0, result.output
    assert "Trade 1 stop -> $170.00" in result.output
