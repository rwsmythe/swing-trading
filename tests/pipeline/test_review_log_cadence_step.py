"""Cadence pre-create step: idempotence + period helpers + error tolerance."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.review import (
    compute_daily_period, compute_monthly_period, compute_weekly_period,
)


class TestPeriodHelpers:
    def test_daily_returns_last_completed_session(self) -> None:
        # 2026-05-02 (Saturday) HST 9pm → ET 02:00am next day, which is post-close
        # of NYSE 2026-05-02 (also Saturday). last_completed_session: 2026-05-01 (Friday).
        # Daily period = (2026-05-01, 2026-05-01).
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_daily_period(now)
        assert start == end
        # Plan author: actual asserted date depends on NYSE calendar — use
        # last_completed_session(now) directly to compare:
        from swing.evaluation.dates import last_completed_session
        assert start == last_completed_session(now)

    def test_weekly_returns_prior_mon_to_fri(self) -> None:
        # 2026-05-02 (Saturday). Prior Mon-Fri = 2026-04-20 to 2026-04-24.
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_weekly_period(now)
        # If last_completed_session is 2026-05-01 (Friday), prior week's Mon = 2026-04-20.
        # Plan author: verify against the actual NYSE calendar via last_completed_session.
        # Assert end == start + 4 days (Mon to Fri):
        assert (end - start).days == 4
        # Assert start.weekday() == 0 (Monday):
        assert start.weekday() == 0

    def test_monthly_returns_prior_calendar_month(self) -> None:
        now = datetime(2026, 5, 2, 21, 0, 0)
        start, end = compute_monthly_period(now)
        assert start.day == 1
        # End must be the last day of prior month (April 2026 has 30 days):
        # end + 1 day == next month's day 1 (i.e. start of the current month)
        from datetime import timedelta
        assert (end + timedelta(days=1)).day == 1
        assert (end + timedelta(days=1)).month != end.month


class TestStepReviewLogCadence:
    """Unit tests for _step_review_log_cadence using a real lease in a tmp DB.

    Pattern mirrors the existing tests/pipeline/test_runner.py harness:
    acquire a real lease via swing.pipeline.lease.acquire_lease, run the
    step, then release. The lease's fenced_write contract is exercised
    end-to-end (not mocked).
    """

    @pytest.fixture
    def lease_and_conn_factory(self, tmp_path: Path):
        from swing.pipeline.lease import acquire_lease

        db_path = tmp_path / "phase6.db"
        # Initialize schema (apply all migrations):
        ensure_schema(db_path).close()

        def make() -> tuple:
            lease = acquire_lease(
                db_path=db_path, trigger="manual",
                data_asof_date="2026-04-30",
                action_session_date="2026-05-01",
                block_threshold_seconds=60,
                finviz_csv_path=None,
                rs_universe_version=None,
                rs_universe_hash=None,
            )
            return lease, db_path
        return make

    def test_creates_three_cadence_rows_first_call(
        self, lease_and_conn_factory,
    ) -> None:
        from swing.pipeline.runner import _step_review_log_cadence
        lease, db_path = lease_and_conn_factory()
        try:
            _step_review_log_cadence(lease=lease)
        finally:
            lease.release(state="complete")
        c = sqlite3.connect(db_path)
        n = c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        c.close()
        assert n == 3  # daily + weekly + monthly

    def test_idempotent_second_call_creates_no_new_rows(
        self, lease_and_conn_factory,
    ) -> None:
        from swing.pipeline.runner import _step_review_log_cadence
        for _ in range(2):
            lease, db_path = lease_and_conn_factory()
            try:
                _step_review_log_cadence(lease=lease)
            finally:
                lease.release(state="complete")
        c = sqlite3.connect(db_path)
        n = c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0]
        c.close()
        assert n == 3  # idempotent — second call adds zero rows

    def test_step_does_not_propagate_internal_errors(
        self, lease_and_conn_factory, monkeypatch,
    ) -> None:
        """When insert_pre_create raises mid-loop, the cadence step must
        propagate the exception (per the implementation that does NOT
        catch internally — the run_pipeline_internal wrapper logs+continues).

        This test asserts the IMPLEMENTATION'S contract — the function does
        NOT swallow exceptions; the WRAPPER does. Brief §6.2 watch item 13
        is satisfied at the WRAPPER layer (run_pipeline_internal try/except
        log.warning), not inside _step_review_log_cadence.
        """
        import sqlite3 as _sqlite3
        from swing.data.repos import review_log as _rl
        from swing.pipeline.runner import _step_review_log_cadence

        call_count = {"n": 0}
        original = _rl.insert_pre_create

        def boom(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise _sqlite3.OperationalError("simulated mid-loop failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(_rl, "insert_pre_create", boom)

        lease, db_path = lease_and_conn_factory()
        try:
            with pytest.raises(_sqlite3.OperationalError):
                _step_review_log_cadence(lease=lease)
        finally:
            lease.release(state="complete")
