"""Gold-standard regression: the daily-management archive warm must NOT run
inside a held per-trade fenced_write (spec §7.1-§7.2)."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing.data.db import ensure_schema
from swing.pipeline.runner import _step_daily_management
# _seed_trade is a module-level helper in the step-test file (verified
# tests/pipeline/test_daily_management_step.py:15); reuse it directly so this
# file does not duplicate the seeding shape.
from tests.pipeline.test_daily_management_step import _seed_trade


def _make_lease_with_fence_flag(conn_factory):
    """A lease whose fenced_write opens a REAL BEGIN IMMEDIATE write txn on a
    dedicated connection and exposes an in_fenced_write flag (True while held)."""
    state = {"in_fenced_write": False}

    class _RealFenceLease:
        run_id = 99

        def fenced_write(self):
            from contextlib import contextmanager

            @contextmanager
            def _cm():
                conn = conn_factory()
                conn.execute("PRAGMA busy_timeout=200")
                conn.execute("BEGIN IMMEDIATE")
                state["in_fenced_write"] = True
                try:
                    yield conn
                    conn.execute("COMMIT")
                finally:
                    state["in_fenced_write"] = False
                    conn.close()
            return _cm()

    return _RealFenceLease(), state


def test_warm_never_runs_under_a_held_fence(tmp_path: Path, monkeypatch):
    """EXACT pre-fix: read_or_fetch_archive runs inside compute_* under the held
    fence -> a 2nd-connection BEGIN IMMEDIATE on the same DB times out ->
    lock_observed=True -> assert FAILS.
    EXACT post-fix: the warm runs with no held fence -> 2nd-conn BEGIN IMMEDIATE
    succeeds -> lock_observed=False -> assert PASSES.
    Anti-false-pass: the stale/missing archive forces the warm; assert the spy
    fired >= 1 (so 'no lock' can't pass vacuously on a fixture that never fetched)."""
    db_path = tmp_path / "fence.db"
    base = ensure_schema(db_path)
    base.execute("PRAGMA journal_mode=WAL")
    base.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, state, lease_token) "
        "VALUES (99, '2026-05-07T18:00:00', '2026-05-07T18:30:00', 'manual', "
        "'2026-05-07', '2026-05-08', 'complete', 'tok')"
    )
    _seed_trade(base, trade_id=1, ticker="DHC", state="managing",
                entry_price=100.0, initial_stop=90.0, initial_shares=50.0,
                current_avg_cost=100.0, current_size=50.0, current_stop=92.0,
                pre_trade_locked_at="2026-05-01T09:30:00")
    base.commit()
    # Close the seeding connection so no stray file handle survives into tmp
    # cleanup (Windows handle-leak hygiene; Codex R3 MINOR). WAL mode is a
    # persistent DB property -- the lease's own connections still see it.
    base.close()

    df = pd.DataFrame({
        "High":  [105.0, 115.0, 110.0],
        "Low":   [98.0,  102.0, 100.0],
        "Close": [104.0, 113.0, 108.0],
    }, index=pd.to_datetime(["2026-05-05", "2026-05-06", "2026-05-07"]))

    spy = {"calls": 0, "lock_observed": False, "in_fence_at_call": []}

    def spying_warm(*args, **kwargs):
        spy["calls"] += 1
        spy["in_fence_at_call"].append(fence_state["in_fenced_write"])
        probe = sqlite3.connect(db_path, timeout=0.2)
        probe.execute("PRAGMA busy_timeout=200")
        try:
            probe.execute("BEGIN IMMEDIATE")
            probe.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                spy["lock_observed"] = True
            else:
                raise
        finally:
            probe.close()
        return df

    # Patch BOTH namespaces with the SAME spy (Codex R1 MAJOR #3): the pre-fix
    # in-fence fetch resolves via compute_*'s lazy import (the source module);
    # the post-fix warm calls the runner's module-level binding. Patching only
    # one would make the pre-fix test fail because the spy was never reached
    # (a false reproduction).
    monkeypatch.setattr("swing.data.ohlcv_archive.read_or_fetch_archive", spying_warm)
    monkeypatch.setattr("swing.pipeline.runner.read_or_fetch_archive", spying_warm)

    lease, fence_state = _make_lease_with_fence_flag(lambda: sqlite3.connect(db_path, timeout=0.5))

    # NOTE: do NOT pass run_warnings here. run_warnings is an OPTIONAL param
    # added in Task 2; omitting it keeps this test body valid against BOTH the
    # pre-fix interface (to witness red via a temporary hoist-revert) and the
    # post-fix tree, so the ONLY variable that flips lock_observed is the hoist.
    _step_daily_management(
        lease=lease, run_now=datetime(2026, 5, 7, 18, 0, 0),
        eval_run_id=99, archive_history_days=120,
        ohlcv_archive_dir=tmp_path / "ohlcv",
        capital_floor_dollars=7500.0, trail_MA_period_days_default=21,
    )

    assert spy["calls"] >= 1, "warm never fired -- fixture did not exercise the fetch"
    assert spy["lock_observed"] is False, "archive warm ran under a held write lock"
    # Ordering (spec §7.2): every warm observed no held fence.
    assert all(flag is False for flag in spy["in_fence_at_call"])
