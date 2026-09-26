"""22-F R2-04 (Reviewer A round 2; CHARC-ruled, group 3, option (b)) --
`CorrectionResult.wrote`, set INSIDE `apply_tier2_resolution`'s transaction
(True on the handler write path, False at step 2's terminal-state
idempotent return), and BOTH callers (CLI `journal discrepancy
resolve-ambiguity`, web `POST /reconcile/discrepancy/{id}/resolve`) bind
`durable` from it.

PRE-FIX the CLI pre-read the service's step-2 predicate on its own
connection BEFORE the call (a second site of the predicate, outside the
service's `BEGIN IMMEDIATE`), and the web route bound `durable = True`
unconditionally.  A concurrent resolution landing between the caller's
read and the service's lock sends the service down step 2 (it writes
nothing) while the caller still reports durable -- so a failing close
printed / logged "IS recorded" over a no-op.  The race is driven by a
wrapper at the name each caller resolves at call time that commits the
terminal resolution on a SEPARATE connection and then calls the REAL
service.  Did-it-fire: the wrapper's count and the failing proxy's close.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from swing.cli import main
from swing.data.db import ensure_schema
from tests._22f_proxies import CountingWrapper
from tests.cli.test_22f_close_after_durable import (
    _PLANTED,
    _WARN,
    ROOTS,
    _closes,
    _failing_close,
)
from tests.web.test_reconcile_resolve_post_route import _seed_discrepancy

_BY_ID = {r.id: r for r in ROOTS}


def _resolve_on_the_side(db: Path, did: int) -> None:
    side = sqlite3.connect(str(db))
    try:
        side.execute(
            "UPDATE reconciliation_discrepancies SET resolution = "
            "'operator_resolved_ambiguity', resolved_by = 'operator' "
            "WHERE discrepancy_id = ?", (did,))
        side.commit()
    finally:
        side.close()


def _racing(real, db: Path, did: int) -> CountingWrapper:
    def _fn(*args, **kwargs):
        _resolve_on_the_side(db, did)
        return real(*args, **kwargs)
    return CountingWrapper(_fn)


def _resolution(db: Path, did: int) -> str:
    c = sqlite3.connect(str(db))
    try:
        return c.execute("SELECT resolution FROM reconciliation_discrepancies "
                         "WHERE discrepancy_id = ?", (did,)).fetchone()[0]
    finally:
        c.close()


def _corrections(db: Path) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections").fetchone()[0]
    finally:
        c.close()


# -- the service ----------------------------------------------------------

def test_r2_04_service_reports_wrote_true_then_false(tmp_path):
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    did = _seed_discrepancy(db)
    conn = sqlite3.connect(str(db))
    try:
        first = apply_tier2_resolution(
            conn, discrepancy_id=did, choice_code="keep_journal_as_is",
            operator_reason="first")
        again = apply_tier2_resolution(
            conn, discrepancy_id=did, choice_code="keep_journal_as_is",
            operator_reason="again")
    finally:
        conn.close()
    assert first.wrote is True
    assert again.wrote is False
    assert again.correction_id == first.correction_id  # step 2: idempotent
    assert _corrections(db) == 1


# -- the CLI caller -------------------------------------------------------

def test_r2_04_cli_race_to_terminal_is_not_durable(tmp_path, monkeypatch):
    root = _BY_ID["discrepancy-resolve-ambiguity"]
    w = root.world(tmp_path, monkeypatch)
    did = w.extra["did"]
    import swing.trades.reconciliation_auto_correct as rac
    wrapper = _racing(rac.apply_tier2_resolution, w.db, did)
    monkeypatch.setattr(rac, "apply_tier2_resolution", wrapper)
    before = _corrections(w.db)
    built = _failing_close(monkeypatch, root.target, root.nth)
    result = w.runner.invoke(main, root.argv(w), input=root.input)
    assert wrapper.calls == 1  # did-it-fire (the race)
    assert _closes(built, root.nth) >= 1  # did-it-fire (the close)
    assert _WARN not in result.output, result.output
    assert "IS recorded" not in result.output
    assert isinstance(result.exception, sqlite3.OperationalError), (
        result.output, repr(result.exception))
    assert _PLANTED in str(result.exception)
    assert _corrections(w.db) == before  # the service wrote nothing
    assert _resolution(w.db, did) == "operator_resolved_ambiguity"


def test_r2_04_cli_write_path_with_failing_close_warns_control(tmp_path,
                                                               monkeypatch):
    """CONTROL (both trees): the handler writes -> the WARN, exit 0."""
    root = _BY_ID["discrepancy-resolve-ambiguity"]
    w = root.world(tmp_path, monkeypatch)
    before = _corrections(w.db)
    built = _failing_close(monkeypatch, root.target, root.nth)
    result = w.runner.invoke(main, root.argv(w), input=root.input)
    assert _closes(built, root.nth) >= 1
    assert result.exit_code == 0, (result.output, repr(result.exception))
    assert _WARN in result.output
    assert _corrections(w.db) == before + 1
