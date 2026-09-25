"""22-F T-F5 -- D39 (S-D39) on `run_schwab_reconciliation` (census C2-08;
`schwab fetch` is its operator root): the run transaction (`:1843`, its two
suppressed rollbacks) and the SEVEN `ROLLBACK TO SAVEPOINT` sites of the
per-discrepancy pivot (`_pivot_classify_and_dispatch_for_run`).

Instrument (the T-F1 pattern): the proxy is the `conn` argument.  A
`FailingVerbsConn` subclass adds ONE verb the shared proxy does not fail --
`ROLLBACK TO SAVEPOINT <name-prefix>` (the shared proxy deliberately treats
`ROLLBACK TO` as a statement, not a rollback).  Each savepoint case plants the
pivot's own callees at the names the pivot resolves at call time (module
globals of `swing.trades.schwab_reconciliation`); the planted body issues a
REAL partial write (`UPDATE trades SET current_stop`) and then a REAL write the
proxy fails with the branch's trigger exception.  Did-it-fire: every planted
callee is counted, and the proxy's `failed_sql` / `failed_rollback_to` are
asserted.

THE SAVEPOINT FACET: a suppressed failed `ROLLBACK TO` leaves the
discrepancy's partial write inside the run's transaction, so the run COMMITS
it.  Post-fix the savepoint failure is raised chained from the per-discrepancy
error and the run's WHOLE transaction is rolled back.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from tests._22f_proxies import CountingWrapper, FailingVerbsConn

_MOD = "swing.trades.schwab_reconciliation"
_PARTIAL = "UPDATE trades SET current_stop = 4.5 WHERE ticker = 'CVGI'"
_FAILWRITE_PREFIX = "UPDATE reconciliation_discrepancies SET resolution_reason"
_FAILWRITE = (_FAILWRITE_PREFIX + " = 'planted' WHERE discrepancy_id = ?")


class _SpFailConn(FailingVerbsConn):
    """Adds: fail `ROLLBACK TO SAVEPOINT <prefix>...` (every match)."""

    def __init__(self, real: sqlite3.Connection, *,
                 fail_rollback_to: str | None = None, **kw: Any) -> None:
        super().__init__(real, **kw)
        object.__setattr__(self, "_fail_rollback_to", fail_rollback_to)

    def _check_sql(self, sql: str) -> None:
        norm = sql.strip().upper()
        frt = self._fail_rollback_to
        if frt is not None and norm.startswith(
                "ROLLBACK TO SAVEPOINT " + frt.upper()):
            self.calls["failed_rollback_to"] += 1
            self.sql_log.append(sql)
            raise sqlite3.OperationalError(
                "cannot rollback to savepoint (planted on ROLLBACK TO)")
        super()._check_sql(sql)


@dataclass
class _Order:
    status: str
    price: float
    quantity: float
    instrument_symbol: str
    order_type: str = "MARKET"
    instruction: str = "BUY"
    order_id: str = "ORD-22f"
    executions: object = None
    enter_time: str = "2026-04-27T14:23:00.000Z"


@dataclass
class _Account:
    net_liquidating_value: float | None = None
    positions: list[Any] | None = None


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """The CVGI entry-price-mismatch world (one tier-1 discrepancy; read)."""
    path = tmp_path / "t.db"
    conn = ensure_schema(path)
    try:
        cur = conn.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at) VALUES ('CVGI', '2026-04-27', 5.23, 100, "
            "4.0, 4.0, 'managing', 'manual_off_pipeline', "
            "'2026-04-27T16:00:00')")
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price, reconciliation_status) VALUES (?, '2026-04-27T14:23:00', "
            "'entry', 100.0, 5.23, 'unreconciled')", (tid,))
        from swing.data.repos.fills import _recompute_aggregates
        _recompute_aggregates(conn, tid)
        conn.commit()
    finally:
        conn.close()
    return path


def _run(conn):
    from swing.integrations.schwab.models import SchwabExecutionLeg
    from swing.trades.schwab_reconciliation import run_schwab_reconciliation
    leg = SchwabExecutionLeg(
        leg_id=1, price=5.30, quantity=100.0, mismarked_quantity=0.0,
        instrument_id=None, time="2026-04-27T14:23:00.000Z")
    return run_schwab_reconciliation(
        conn, account_hash="<acct>", period_start="2026-04-27",
        period_end="2026-04-27",
        schwab_orders=[_Order(status="FILLED", price=5.30, quantity=100.0,
                              instrument_symbol="CVGI", executions=[leg])],
        schwab_transactions=[],
        schwab_account=_Account(net_liquidating_value=2000.0, positions=[]))


def _fresh(db: Path) -> dict:
    c = sqlite3.connect(str(db))
    try:
        return {
            "runs": c.execute(
                "SELECT state FROM reconciliation_runs ORDER BY run_id"
            ).fetchall(),
            "discs": c.execute(
                "SELECT COUNT(*) FROM reconciliation_discrepancies"
            ).fetchone()[0],
            "stop": c.execute(
                "SELECT current_stop FROM trades WHERE ticker = 'CVGI'"
            ).fetchone()[0],
        }
    finally:
        c.close()


def _records(caplog, needle: str):
    return [r for r in caplog.records
            if r.levelno >= logging.ERROR and needle in r.getMessage()]


def _recipe_result():
    from swing.trades.reconciliation_classifier import ClassificationResult
    return ClassificationResult(
        tier=2,
        ambiguity_kind="multi_partial_vs_consolidated",
        correction_target=None,
        correction_reason="22-F planted recipe",
        candidate_choices=None,
        auto_redirect_recipe={
            "choice_code": "split_into_partials",
            "resolved_by": "auto_tier1_multi_leg",
            "applied_by_override": "auto",
            "correction_action_override": "auto_applied",
            "payload": [
                {"qty": 50.0, "price": 5.29, "fill_datetime":
                 "2026-04-27T14:23:00"},
                {"qty": 50.0, "price": 5.31, "fill_datetime":
                 "2026-04-27T14:23:42"},
            ],
        },
    )


def _body(*, partial: bool, fail: bool):
    """A planted callee: optional real partial write, optional real write the
    proxy fails (with the case's trigger exception)."""
    def body(conn, **kw):
        if partial:
            conn.execute(_PARTIAL)
        if fail:
            conn.execute(_FAILWRITE, (kw.get("discrepancy_id"),))
        return None
    return body


def _seq(*bodies):
    """Call-order dispatch: the n-th call runs the n-th body (last repeats)."""
    state = {"n": 0}

    def body(conn, **kw):
        i = min(state["n"], len(bodies) - 1)
        state["n"] += 1
        return bodies[i](conn, **kw)
    return body


def _trigger(name: str) -> BaseException:
    from swing.trades import reconciliation_auto_correct as rac
    return {
        "validator_rejected": rac.ValidatorRejectedError("planted reject"),
        "sandbox": rac._SandboxAutoRedirectShortCircuit("planted sandbox"),
        "invalid_combo": rac.InvalidOverrideComboError("planted combo"),
        "value_error": ValueError("planted decline"),
        "sqlite": sqlite3.OperationalError("planted on the discrepancy write"),
    }[name]


# Per site (READ from `_pivot_classify_and_dispatch_for_run`, recorded in the
# exec ledger): the branch that reaches it, the plants, the trigger raised by
# the proxy on the failing write, the savepoint whose ROLLBACK TO fails, and
# whether the pre-fix run RAISES (the preserve-and-commit path) or RETURNS.
_SITES = {
    # :1175 -- tier-1 ValidatorRejectedError -> the fresh fallback savepoint's
    # stamp fails -> ROLLBACK TO the FALLBACK savepoint.
    "S1-1175-tier1-fallback-sp": dict(
        recipe=False,
        tier1=("raise_first", "validator_rejected"),
        stamp=[dict(partial=True, fail=True)],
        trigger="sqlite", sp="correction_fallback_sp_", pre_raises=False),
    # :1247 -- auto-redirect, `_SandboxAutoRedirectShortCircuit`.
    "S2-1247-sandbox": dict(
        recipe=True, stamp=[dict(partial=True, fail=False)],
        tier2=dict(partial=False, fail=True),
        trigger="sandbox", sp="correction_sp_", pre_raises=False),
    # :1263 -- auto-redirect, InvalidOverrideComboError (then :1325 again).
    "S3-1263-invalid-combo": dict(
        recipe=True, stamp=[dict(partial=True, fail=False)],
        tier2=dict(partial=False, fail=True),
        trigger="invalid_combo", sp="correction_sp_", pre_raises=True),
    # :1275 -- auto-redirect, ValueError decline -> ROLLBACK TO sp_name.
    "S4-1275-decline-sp": dict(
        recipe=True,
        stamp=[dict(partial=True, fail=False), dict(partial=False, fail=False)],
        tier2=dict(partial=False, fail=True),
        trigger="value_error", sp="correction_sp_", pre_raises=False),
    # :1295 -- auto-redirect decline -> fallback stamp fails -> ROLLBACK TO
    # the FALLBACK savepoint.
    "S5-1295-decline-fallback-sp": dict(
        recipe=True,
        stamp=[dict(partial=False, fail=False), dict(partial=True, fail=True)],
        tier2=dict(partial=False, fail=True, second_trigger="value_error"),
        trigger="sqlite", sp="correction_fallback_sp_", pre_raises=False),
    # :1325 -- the per-discrepancy InvalidOverrideComboError handler, reached
    # from the tier-1 branch (the tier-1 handler does not catch it).
    "S6-1325-outer-invalid-combo": dict(
        recipe=False, tier1=("partial_then_fail", None),
        trigger="invalid_combo", sp="correction_sp_", pre_raises=True),
    # :1330 -- the per-discrepancy graceful-degradation handler.
    "S7-1330-outer-generic": dict(
        recipe=False, tier1=("partial_then_fail", None),
        trigger="sqlite", sp="correction_sp_", pre_raises=False),
}


def _plant_site(monkeypatch, spec) -> dict:
    counters: dict[str, CountingWrapper] = {}
    if spec["recipe"]:
        cw = CountingWrapper(lambda disc, **k: _recipe_result())
        monkeypatch.setattr(f"{_MOD}.classify_discrepancy", cw)
        counters["classify"] = cw
    t1 = spec.get("tier1")
    if t1 is not None:
        kind, exc_name = t1
        if kind == "raise_first":
            exc = _trigger(exc_name)

            def tier1(conn, **k):
                raise exc
        else:
            tier1 = _body(partial=True, fail=True)
        cw = CountingWrapper(tier1)
        monkeypatch.setattr(f"{_MOD}._apply_tier1_correction_inner", cw)
        counters["tier1"] = cw
    if "stamp" in spec:
        cw = CountingWrapper(_seq(*[_body(**b) for b in spec["stamp"]]))
        monkeypatch.setattr(f"{_MOD}._stamp_pending_ambiguity_inner", cw)
        counters["stamp"] = cw
    if "tier2" in spec:
        t2 = dict(spec["tier2"])
        second = t2.pop("second_trigger", None)
        if second is None:
            fn = _body(**t2)
        else:
            exc = _trigger(second)

            def fn(conn, **k):
                raise exc
        cw = CountingWrapper(fn)
        monkeypatch.setattr(f"{_MOD}._apply_tier2_resolution_inner", cw)
        counters["tier2"] = cw
    return counters


@pytest.mark.parametrize("site", sorted(_SITES))
def test_failed_rollback_to_savepoint_rolls_the_whole_run_back(
        site, db, monkeypatch, caplog):
    """PRE-FIX: the `ROLLBACK TO` failure is SUPPRESSED, so the partial write
    (current_stop 4.0 -> 4.5) COMMITS with the run (or with its preserved
    'failed' row).  POST-FIX: the savepoint failure is raised chained from
    the per-discrepancy error, and a fresh read shows none of the run's rows
    and the partial write gone."""
    spec = _SITES[site]
    counters = _plant_site(monkeypatch, spec)
    proxy = _SpFailConn(sqlite3.connect(str(db)),
                        fail_sql_prefix=_FAILWRITE_PREFIX, fail_sql_times=1,
                        raise_on_sql=_trigger(spec["trigger"]),
                        fail_rollback_to=spec["sp"])
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    for name, cw in counters.items():
        assert cw.calls >= 1, f"planted {name} never called"
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["failed_rollback_to"] >= 1
    assert "ROLLBACK TO SAVEPOINT" in str(info.value)
    assert spec["sp"] in str(info.value)
    cause = info.value.__cause__
    assert cause is not None
    assert type(cause) is type(_trigger(spec["trigger"]))
    after = _fresh(db)
    assert after == {"runs": [], "discs": 0, "stop": 4.0}
    assert len(_records(caplog, "ROLLBACK TO SAVEPOINT")) == 1


def test_invalid_combo_with_working_savepoints_still_preserves_failed_run(
        db, monkeypatch):
    """PIN (both trees): the auto-redirect InvalidOverrideComboError path with
    a WORKING `ROLLBACK TO` -- the savepoint undoes the stamp, the handler at
    :1325 meets an already-released savepoint, and the run's preserve path
    (spec 3.3.3) commits the 'failed' run row.  Guards the post-fix
    released-savepoint tracking: it must not turn this into a whole-run
    rollback."""
    counters = _plant_site(monkeypatch, _SITES["S3-1263-invalid-combo"])
    proxy = _SpFailConn(sqlite3.connect(str(db)),
                        fail_sql_prefix=_FAILWRITE_PREFIX, fail_sql_times=1,
                        raise_on_sql=_trigger("invalid_combo"))
    try:
        from swing.trades.reconciliation_auto_correct import (
            InvalidOverrideComboError,
        )
        with pytest.raises(InvalidOverrideComboError):
            _run(proxy)
    finally:
        proxy._real.close()
    assert counters["tier2"].calls == 1 and proxy.calls["failed_sql"] == 1
    after = _fresh(db)
    assert after["runs"] == [("failed",)]
    assert after["stop"] == 4.0


# --- the run transaction's own sites (the common Part-F table) ------------

_RUN_INSERT = "INSERT INTO reconciliation_runs"
_DISC_INSERT = "INSERT INTO reconciliation_discrepancies"


@pytest.mark.parametrize("prefix", [_RUN_INSERT, "UPDATE reconciliation_runs"])
def test_run_tx_both_verbs_fail_raises_cleanup_chained(
        prefix, db, caplog):
    """`:2773` (the run-row INSERT fails, run_id None) and `:2794` (the
    preserve path's `update_run_failed` fails too).  PRE-FIX: the rollback
    failure is suppressed and the WRITE error raised, no record.  POST-FIX:
    the CLEANUP error, `__cause__` the run's original error, one record."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix=prefix, fail_rollback=True)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    assert proxy.calls["failed_sql"] >= 1
    assert proxy.calls["rollback"] >= 1
    assert "cannot rollback" in str(info.value)
    assert "planted on" in str(info.value.__cause__)
    assert len(_records(caplog, "MUST BE DISCARDED")) == 1


@pytest.mark.parametrize("prefix", [_RUN_INSERT, _DISC_INSERT])
def test_run_tx_f2_twin_interrupt_rolls_back(prefix, db):
    """PRE-FIX: `except Exception` does not run, so the transaction stays
    OPEN after the interrupt.  POST-FIX: rolled back, interrupt re-raised."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix=prefix,
                             raise_on_sql=KeyboardInterrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            _run(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _fresh(db)["runs"] == []


def test_run_tx_single_failure_before_run_row_pin(db, caplog):
    """PIN (both trees): the run-row INSERT fails, the rollback works -> the
    write error, no rows, no record."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix=_RUN_INSERT)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _run(proxy)
        assert proxy.calls["failed_sql"] == 1
        assert proxy.in_transaction is False
    finally:
        proxy._real.close()
    assert _records(caplog, "MUST BE DISCARDED") == []
    assert _fresh(db)["runs"] == []


def test_run_tx_single_failure_after_run_row_preserves_failed_pin(db, caplog):
    """PIN (both trees): a discrepancy INSERT fails with a working rollback
    -> the spec 3.3.3 preserve path commits the 'failed' run row; the
    behaviour change is bounded to the double failure."""
    proxy = FailingVerbsConn(sqlite3.connect(str(db)),
                             fail_sql_prefix=_DISC_INSERT)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(sqlite3.OperationalError, match="planted on"):
                _run(proxy)
        assert proxy.calls["failed_sql"] == 1
    finally:
        proxy._real.close()
    assert _records(caplog, "MUST BE DISCARDED") == []
    assert _fresh(db)["runs"] == [("failed",)]


def test_run_tx_control_commits(db):
    proxy = FailingVerbsConn(sqlite3.connect(str(db)))
    try:
        run = _run(proxy)
        assert proxy.calls["commit"] >= 1
    finally:
        proxy._real.close()
    assert run.state == "completed"
    after = _fresh(db)
    assert after["runs"] == [("completed",)] and after["discs"] == 1


# -- R1-09 (Reviewer A round 1; D-16, as narrowed by the orchestrator) ------
# An INTERRUPT raised by `ROLLBACK TO SAVEPOINT` itself.  PRE-FIX the helper
# caught `sqlite3.Error` only, so the interrupt escaped with no ERROR record
# and no `__cause__` (the per-discrepancy error survived only as implicit
# context).  POST-FIX the interrupt is logged with a MUST-BE-DISCARDED record
# and re-raised CHAINED from the per-discrepancy error -- NOT retyped as
# `_SavepointRollbackError` (an interrupt stays an interrupt).  On both trees
# the run's BaseException handler rolls the whole run back.


class _SpInterruptConn(_SpFailConn):
    """`ROLLBACK TO SAVEPOINT <prefix>...` raises KeyboardInterrupt."""

    def _check_sql(self, sql: str) -> None:
        norm = sql.strip().upper()
        frt = self._fail_rollback_to
        if frt is not None and norm.startswith(
                "ROLLBACK TO SAVEPOINT " + frt.upper()):
            self.calls["failed_rollback_to"] += 1
            self.sql_log.append(sql)
            raise KeyboardInterrupt
        FailingVerbsConn._check_sql(self, sql)


@pytest.mark.parametrize("site", sorted(_SITES))
def test_r1_09_interrupted_rollback_to_stays_an_interrupt_chained(
        site, db, monkeypatch, caplog):
    spec = _SITES[site]
    counters = _plant_site(monkeypatch, spec)
    proxy = _SpInterruptConn(sqlite3.connect(str(db)),
                             fail_sql_prefix=_FAILWRITE_PREFIX,
                             fail_sql_times=1,
                             raise_on_sql=_trigger(spec["trigger"]),
                             fail_rollback_to=spec["sp"])
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    for name, cw in counters.items():
        assert cw.calls >= 1, f"planted {name} never called"
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["failed_rollback_to"] == 1
    assert type(info.value) is KeyboardInterrupt
    cause = info.value.__cause__
    assert cause is not None
    assert type(cause) is type(_trigger(spec["trigger"]))
    recs = _records(caplog, "MUST BE DISCARDED")
    assert len(recs) == 1
    assert spec["sp"] in recs[0].getMessage()
    assert _fresh(db) == {"runs": [], "discs": 0, "stop": 4.0}


# -- R2-05 (Reviewer A round 2; CHARC's class ruling, MINOR) -----------------
# The tier-1 REJECTION branch's own direct `ROLLBACK TO SAVEPOINT` (never a
# census C2-08 site: it was never suppressed).  An interrupt there PRE-FIX
# escaped with no record and no `__cause__` (the rejection survived only as
# implicit context).  POST-FIX it is recorded and re-raised CHAINED from the
# rejection AT that statement -- not routed through the helper (a single
# `sqlite3.Error` there keeps propagating to the per-discrepancy handler,
# which retries the ROLLBACK TO; unchanged).  On both trees the run's
# BaseException handler rolls the whole run back.
def test_r2_05_interrupted_rejection_rollback_to_is_chained(
        db, monkeypatch, caplog):
    from swing.trades import reconciliation_auto_correct as rac
    counters = _plant_site(monkeypatch, dict(
        recipe=False, tier1=("raise_first", "validator_rejected")))
    proxy = _SpInterruptConn(sqlite3.connect(str(db)),
                             fail_rollback_to="correction_sp_")
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    assert counters["tier1"].calls >= 1  # did-it-fire (the rejection)
    assert proxy.calls["failed_rollback_to"] == 1  # did-it-fire
    assert type(info.value) is KeyboardInterrupt
    assert isinstance(info.value.__cause__, rac.ValidatorRejectedError)
    recs = _records(caplog, "MUST BE DISCARDED")
    assert len(recs) == 1
    assert "correction_sp_" in recs[0].getMessage()
    assert _fresh(db) == {"runs": [], "discs": 0, "stop": 4.0}


def test_r2_05_sqlite_error_at_rejection_rollback_to_unchanged_pin(
        db, monkeypatch, caplog):
    """PIN (both trees): a `sqlite3.Error` at that ROLLBACK TO still reaches
    the per-discrepancy handler, whose helper retries the ROLLBACK TO (which
    fails again here) -> `_SavepointRollbackError` -> the whole run rolls
    back."""
    counters = _plant_site(monkeypatch, dict(
        recipe=False, tier1=("raise_first", "validator_rejected")))
    proxy = _SpFailConn(sqlite3.connect(str(db)),
                        fail_rollback_to="correction_sp_")
    try:
        with pytest.raises(Exception) as info:
            _run(proxy)
    finally:
        proxy._real.close()
    assert counters["tier1"].calls >= 1
    assert proxy.calls["failed_rollback_to"] == 2
    assert type(info.value).__name__ == "_SavepointRollbackError"
    assert _fresh(db) == {"runs": [], "discs": 0, "stop": 4.0}


# -- SS-3 / SS-4 (the uncounted self-sweep, CHARC's Round 2 class rule) -----
# The RELEASE that completes a savepoint cleanup after a SUCCESSFUL
# `ROLLBACK TO`: in the R1-09 helper (`RELEASE` under
# `contextlib.suppress(sqlite3.Error)`) and in the R2-05 rejection branch.
# PRE-FIX an interrupt there escaped with no record and no `__cause__`.
# POST-FIX it is recorded and re-raised CHAINED from the in-flight error; a
# `sqlite3.Error` there is unchanged (suppressed in the helper; propagated in
# the rejection branch).  On both trees the run rolls back WHOLE.


class _ReleaseInterruptConn(_SpFailConn):
    """`RELEASE SAVEPOINT <prefix>...` raises KeyboardInterrupt."""

    def __init__(self, real: sqlite3.Connection, *, release_prefix: str,
                 **kw: Any) -> None:
        super().__init__(real, **kw)
        object.__setattr__(self, "_release_prefix", release_prefix)

    def _check_sql(self, sql: str) -> None:
        norm = sql.strip().upper()
        if norm.startswith("RELEASE SAVEPOINT "
                           + self._release_prefix.upper()):
            self.calls["interrupted_release"] += 1
            self.sql_log.append(sql)
            raise KeyboardInterrupt
        super()._check_sql(sql)


def test_ss_helper_release_interrupt_is_chained(db, monkeypatch, caplog):
    spec = _SITES["S7-1330-outer-generic"]
    counters = _plant_site(monkeypatch, spec)
    proxy = _ReleaseInterruptConn(sqlite3.connect(str(db)),
                                  release_prefix="correction_sp_",
                                  fail_sql_prefix=_FAILWRITE_PREFIX,
                                  fail_sql_times=1,
                                  raise_on_sql=_trigger(spec["trigger"]))
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    for name, cw in counters.items():
        assert cw.calls >= 1, f"planted {name} never called"
    assert proxy.calls["failed_sql"] == 1
    assert proxy.calls["interrupted_release"] == 1  # did-it-fire
    assert type(info.value) is KeyboardInterrupt
    assert isinstance(info.value.__cause__, sqlite3.OperationalError)
    recs = _records(caplog, "MUST BE DISCARDED")
    assert len(recs) == 1 and "RELEASE" in recs[0].getMessage()
    assert _fresh(db) == {"runs": [], "discs": 0, "stop": 4.0}


def test_ss_rejection_release_interrupt_is_chained(db, monkeypatch, caplog):
    from swing.trades import reconciliation_auto_correct as rac
    counters = _plant_site(monkeypatch, dict(
        recipe=False, tier1=("raise_first", "validator_rejected")))
    proxy = _ReleaseInterruptConn(sqlite3.connect(str(db)),
                                  release_prefix="correction_sp_")
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyboardInterrupt) as info:
                _run(proxy)
    finally:
        proxy._real.close()
    assert counters["tier1"].calls >= 1
    assert proxy.calls["interrupted_release"] == 1  # did-it-fire
    assert type(info.value) is KeyboardInterrupt
    assert isinstance(info.value.__cause__, rac.ValidatorRejectedError)
    recs = _records(caplog, "MUST BE DISCARDED")
    assert len(recs) == 1 and "RELEASE" in recs[0].getMessage()
    assert _fresh(db) == {"runs": [], "discs": 0, "stop": 4.0}
