# tests/pipeline/test_lease_flush.py
from __future__ import annotations

import contextlib
import logging
from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from swing.data.db import connect, ensure_schema
from swing.data.repos.pipeline import force_clear
from swing.data.repos.pipeline_step_timings import (
    list_step_timings, step_durations_by_name,
)
from swing.pipeline import lease as lease_mod
from swing.pipeline.lease import acquire_lease


@pytest.fixture
def fake_clock(monkeypatch):
    def install(values):
        it = iter(values)
        monkeypatch.setattr(lease_mod, "_monotonic", lambda: next(it))
    return install


def _lease(tmp_path):
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db, acquire_lease(
        db_path=db, trigger="manual",
        data_asof_date="2026-06-08", action_session_date="2026-06-09",
        block_threshold_seconds=120,
    )


def test_flush_persists_all_rows_and_closes_final_pending(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 0.7, 0.73, 1.0])  # 4 step()s + 1 flush close
    for name in ["finviz_fetch", "weather", "finviz_fetch", "evaluate"]:
        lz.step(name)
    lz.flush_step_timings()  # closes evaluate (ordinal 3), persists all 4
    with contextlib.closing(connect(db)) as conn:
        rows = list_step_timings(conn, lz.run_id)
        assert [r.ordinal for r in rows] == [0, 1, 2, 3]
        assert step_durations_by_name(conn, lz.run_id)["finviz_fetch"] == (
            rows[0].duration_ms + rows[2].duration_ms
        )


def test_persisted_durations_distinguish_fast_and_slow(tmp_path, fake_clock):
    # spec §6.2: the PERSISTED duration_ms must distinguish fast vs slow -- not just
    # the in-memory ledger (Task 5). Monotonic stub: fast=500ms, slow=3000ms.
    db, lz = _lease(tmp_path)
    fake_clock([1000.0, 1000.5, 1003.5, 1003.6])  # 3 step()s + 1 flush close
    lz.step("fast")   # opens fast @1000.0
    lz.step("slow")   # closes fast (500ms), opens slow @1000.5
    lz.step("end")    # closes slow (3000ms), opens end @1003.5
    lz.flush_step_timings()  # closes end (100ms), persists all 3
    with contextlib.closing(connect(db)) as conn:
        rows = {r.step_name: r.duration_ms for r in list_step_timings(conn, lz.run_id)}
    # CORRECT: fast=500, slow=3000 persisted distinctly. NAIVE (last-wins/overwrite
    # at persist): would collapse to one row -> KeyError or equal values. 3000 > 500.
    assert rows["fast"] == 500
    assert rows["slow"] == 3000
    assert rows["slow"] > rows["fast"]


def test_flush_emits_summary_and_per_step_lines(tmp_path, fake_clock, caplog):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    # caplog MUST wrap the step() calls too: the `evaluate` per-step line is
    # emitted DURING step("charts") (which closes evaluate), before flush. Only
    # the final `charts` line + the summary are emitted inside flush.
    with caplog.at_level(logging.INFO, logger="swing.pipeline.lease"):
        for name in ["evaluate", "charts"]:
            lz.step(name)
        lz.flush_step_timings()
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("step totals:") for m in msgs)  # summary present
    assert any("name=evaluate" in m for m in msgs)          # per-step line (during step)
    assert any("name=charts" in m for m in msgs)            # per-step line (during flush)


def test_flush_failure_degrades_cleanly(tmp_path, fake_clock, caplog, monkeypatch):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])

    def boom(*a, **k):
        raise RuntimeError("db locked")

    monkeypatch.setattr(lease_mod, "insert_step_timings", boom)
    runner_log = logging.getLogger("swing.pipeline.runner")
    # caplog MUST wrap the step() calls: the `evaluate` per-step line is emitted
    # during step("charts"); the `charts` line + summary are emitted inside flush
    # BEFORE the failing insert. All must survive (spec §6.4b: per-step lines AND
    # the aggregate summary are the durable fallback when the DB write fails).
    with caplog.at_level(logging.INFO):
        for name in ["evaluate", "charts"]:
            lz.step(name)
        try:
            lz.flush_step_timings()
        except Exception as exc:  # mirror the runner finally's swallow + log
            runner_log.error("step-timing flush failed: %s", exc)
    msgs = [r.getMessage() for r in caplog.records]
    # (b) error logged
    assert any("flush failed" in m for m in msgs)
    # (d) per-step lines survive (already-closed `evaluate` + final-pending `charts`)
    assert any("name=evaluate" in m for m in msgs)
    assert any("name=charts" in m for m in msgs)
    # (e) the aggregate summary survives (emitted before the fallible DB write)
    assert any(m.startswith("step totals:") for m in msgs)
    # (a) outcome unaffected; _timings_flushed stays False (set only AFTER commit) ->
    # a later retry is still possible (the in-memory ledger still holds the rows).
    assert lz._timings_flushed is False


def test_flush_idempotent_after_success(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    for name in ["evaluate", "charts"]:
        lz.step(name)
    lz.flush_step_timings()
    assert lz._timings_flushed is True
    lz.flush_step_timings()  # second call: guard short-circuits, no dup rows
    with contextlib.closing(connect(db)) as conn:
        assert len(list_step_timings(conn, lz.run_id)) == 2


def test_flush_after_force_clear_uses_fresh_connection(tmp_path, fake_clock):
    db, lz = _lease(tmp_path)
    fake_clock([0.0, 0.5, 1.0])
    lz.step("evaluate")
    lz.step("charts")
    # Revoke the lease (sets state='force_cleared'; row survives). force_clear does
    # NOT self-commit -> wrap in `with conn:` (transaction); closing() ensures the
    # connection is also closed (sqlite3's CM commits but does not close).
    with contextlib.closing(connect(db)) as conn:
        with conn:
            force_clear(conn, run_id=lz.run_id, error_message="operator force-clear")
    lz.flush_step_timings()  # fresh connect(), no token needed
    with contextlib.closing(connect(db)) as conn:
        assert len(list_step_timings(conn, lz.run_id)) >= 1
