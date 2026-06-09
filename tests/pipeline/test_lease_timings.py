# tests/pipeline/test_lease_timings.py
from __future__ import annotations

import logging
from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from swing.data.db import ensure_schema
from swing.pipeline import lease as lease_mod
from swing.pipeline.lease import STEP_SOFT_BUDGET_MS, acquire_lease


@pytest.fixture
def fresh_lease(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    lz = acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )
    yield lz


@pytest.fixture
def fake_clock(monkeypatch):
    ticks = iter([])

    def install(values):
        nonlocal ticks
        ticks = iter(values)
        monkeypatch.setattr(lease_mod, "_monotonic", lambda: next(ticks))

    return install


def test_durations_distinguish_fast_and_slow(fresh_lease, fake_clock):
    # One _monotonic() call per step(). t0=1000.0, t1=1000.5, t2=1003.5.
    fake_clock([1000.0, 1000.5, 1003.5])
    fresh_lease.step("fast")   # opens fast @ t0
    fresh_lease.step("slow")   # closes fast (dur=(t1-t0)*1000=500), opens slow @ t1
    fresh_lease.step("end")    # closes slow (dur=(t2-t1)*1000=3000), opens end @ t2
    closed = fresh_lease._timings
    assert [t.step_name for t in closed] == ["fast", "slow"]
    assert closed[0].duration_ms == 500
    assert closed[1].duration_ms == 3000
    # Discriminator: a naive last-wins/overwrite impl records no closed list ->
    # closed == [] -> the slice assertion fails. CORRECT keeps both intervals.
    assert closed[1].duration_ms > closed[0].duration_ms


def test_inbox_empty_sequence_ordinals_and_aggregation(fresh_lease, fake_clock):
    # The REAL inbox-empty order from runner.py: finviz_fetch(634) -> weather(723)
    # -> finviz_fetch(758, skip) -> evaluate(817). weather sits BETWEEN the two
    # finviz_fetch calls -- NOT a synthetic two-in-a-row.
    fake_clock([0.0, 0.5, 0.7, 0.73])  # 4 step() calls
    for name in ["finviz_fetch", "weather", "finviz_fetch", "evaluate"]:
        fresh_lease.step(name)
    closed = fresh_lease._timings  # evaluate still pending -> 3 closed
    assert [(t.ordinal, t.step_name) for t in closed] == [
        (0, "finviz_fetch"), (1, "weather"), (2, "finviz_fetch"),
    ]
    totals = lease_mod._aggregate_by_name(closed)
    # finviz_fetch = (500) + (30) = 530; weather = 200.
    assert totals["finviz_fetch"] == closed[0].duration_ms + closed[2].duration_ms
    assert set(totals) == {"finviz_fetch", "weather"}


def test_inbox_nonempty_sequence_single_finviz(fresh_lease, fake_clock):
    # Non-empty path: site-1 never fires -> weather(723, ord 0) -> finviz_fetch(758,
    # ord 1) -> evaluate. Proves ordinals are path-dependent.
    fake_clock([0.0, 0.5, 0.7])
    for name in ["weather", "finviz_fetch", "evaluate"]:
        fresh_lease.step(name)
    closed = fresh_lease._timings
    assert [(t.ordinal, t.step_name) for t in closed] == [
        (0, "weather"), (1, "finviz_fetch"),
    ]
    assert sum(1 for t in closed if t.step_name == "finviz_fetch") == 1


def test_soft_budget_warns_only_over_threshold(fresh_lease, fake_clock, caplog):
    over = STEP_SOFT_BUDGET_MS / 1000.0 + 1.0  # seconds; > budget
    fake_clock([0.0, over, over + 0.001])
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.lease"):
        fresh_lease.step("charts")   # opens
        fresh_lease.step("export")   # closes charts (over budget) -> WARN
        fresh_lease.step("complete")  # closes export (~1ms) -> no WARN
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("name=charts" in r.getMessage() for r in warns)
    assert not any("name=export" in r.getMessage() for r in warns)
