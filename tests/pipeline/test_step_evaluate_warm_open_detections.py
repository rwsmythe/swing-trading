"""D83 (maintenance rider): the OPEN detection set joins the evaluate warm cohort.

The cohort is produced by observe's OWN selector with observe's OWN anchor
(`list_observable_detections(conn, source="pipeline",
observation_date=lease_data_asof(cfg, lease))`, CHARC F9), APPENDED after the
untouched base cohort (CHARC F10 (3)), with `open_det=` / `open_det_added=`
telemetry on the cohort line (F11). A reader failure never sinks the warm: it is
a #27 run-warning and the warm proceeds with the base set (condition (iii)).

The six older warm unit tests stub the reader in their own file
(test_step_evaluate_warm.py); these tests drive the REAL reader.
"""
# ruff: noqa: F811 -- the tmp_db_at_head fixture imported from conftest_temporal is
# re-bound as a test-function parameter; that is the intended pytest pattern.
from __future__ import annotations

import logging
import re
from datetime import datetime

import pytest

import swing.data.repos.pattern_detection_events as pde
from swing.data.ohlcv_archive import WarmReport
from swing.pipeline import runner as rmod
from tests.pipeline.conftest_temporal import (  # noqa: F401
    _FakeLease,
    _plant_detection,
    tmp_db_at_head,
)


class _Cfg:
    """Duck-typed cfg exposing only what the warm and its reader read."""
    class _Paths:
        def __init__(self, db_path, cache_dir):
            self.db_path = db_path
            self.prices_cache_dir = cache_dir

    class _Archive:
        archive_history_days = 1260

    class _RS:
        benchmark_ticker = "SPY"

    def __init__(self, db_path, cache_dir):
        self.paths = self._Paths(db_path, cache_dir)
        self.archive = self._Archive()
        self.rs = self._RS()


def _seed_run(conn) -> None:
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, '2026-06-11T18:00:00', 'manual', '2026-06-10', '2026-06-11', "
        "'tok', 'running')")
    conn.commit()


def _world(tmp_db_at_head, tmp_path):
    conn, db_path = tmp_db_at_head
    _seed_run(conn)
    cache = tmp_path / "ohlcv"
    cache.mkdir(exist_ok=True)
    return conn, _Cfg(db_path, cache), _FakeLease(db_path, 1, "2026-06-10")


def _recording_warm(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def _rec(tickers, **kwargs):
        calls.append(list(tickers))
        return WarmReport(cache_hit=1)

    monkeypatch.setattr(rmod, "warm_archives_batch", _rec)
    return calls


def test_cohort_is_observes_selector_at_the_lease_date(
        tmp_db_at_head, tmp_path, monkeypatch) -> None:
    """Condition (i) / F9: the appended set is observe's selector at the LEASE
    date (06-10), never run_now's last completed session (06-12) and never a
    hand-written SQL. FUT (asof 06-11) is observable at 06-12 but not at 06-10;
    DONE is terminal (expired 06-05); CAND is already in the base cohort."""
    conn, cfg, lease = _world(tmp_db_at_head, tmp_path)
    _plant_detection(conn, ticker="OBS", data_asof_date="2026-06-09")
    _plant_detection(conn, ticker="FUT", data_asof_date="2026-06-11")
    done_id = _plant_detection(conn, ticker="DONE", data_asof_date="2026-06-01")
    _plant_detection(conn, ticker="CAND", data_asof_date="2026-06-09")
    from swing.data.models import PatternForwardObservation
    from swing.data.repos.pattern_forward_observations import insert_observation
    with conn:
        insert_observation(conn, PatternForwardObservation(
            observation_id=None, detection_id=done_id, observation_date="2026-06-05",
            ohlc_today_json='{"open":1,"high":1,"low":1,"close":1,"volume":1,'
                            '"provider":"yfinance"}',
            status="expired", sessions_since_detection=4,
            created_at="2026-06-05T00:00:00Z",
            status_change_event="observation_horizon_reached"))

    real = pde.list_observable_detections
    spy_calls: list[tuple] = []

    def _spy(*args, **kwargs):
        spy_calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(pde, "list_observable_detections", _spy)
    warm_calls = _recording_warm(monkeypatch)
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=cfg, candidate_tickers=["CAND", "AAA"], universe_tickers=["UUU"],
        run_now=datetime(2026, 6, 12, 20, 0), run_warnings=run_warnings,
        lease=lease,
    )
    assert warm_calls == [["SPY", "CAND", "AAA", "UUU", "OBS"]]
    assert len(spy_calls) == 1
    assert spy_calls[0][1] == {"source": "pipeline", "observation_date": "2026-06-10"}
    assert run_warnings == []


def test_cohort_appends_distinct_uppercase_after_the_untouched_base(
        tmp_db_at_head, tmp_path, monkeypatch, caplog) -> None:
    """F10 (3) + F11: the base cohort is byte-identical (its internal case
    duplicate kept) and the open set is appended sorted, uppercase and disjoint
    from it, with the counts on the cohort line.

    The warm sorts and dedupes this list itself (`ohlcv_archive.py:666`); the
    prefix shape pins the composition of the cohort, not an order the warm
    honours."""
    conn, cfg, lease = _world(tmp_db_at_head, tmp_path)
    for t in ("MSFT", "ZZZ", "BBB", "AAPL"):
        _plant_detection(conn, ticker=t, data_asof_date="2026-06-09")
    warm_calls = _recording_warm(monkeypatch)
    with caplog.at_level(logging.INFO, logger=rmod.log.name):
        rmod._prewarm_evaluate_archives(
            cfg=cfg, candidate_tickers=["aapl", "msft"],
            universe_tickers=["AAPL", "NVDA"], run_now=None, run_warnings=[],
            lease=lease,
        )
    assert warm_calls == [["SPY", "aapl", "msft", "AAPL", "NVDA", "BBB", "ZZZ"]]
    lines = [r.getMessage() for r in caplog.records
             if r.getMessage().startswith("evaluate warm:")]
    assert len(lines) == 1
    assert re.search(r"wall=[0-9.]+s open_det=4 open_det_added=2$", lines[0]), lines[0]


@pytest.mark.parametrize("case", ["selector", "anchor"])
def test_reader_failure_warns_and_warms_the_base_set(
        tmp_db_at_head, tmp_path, monkeypatch, caplog, case) -> None:
    """Condition (iii) / F10 (2): ANY reader exception -> log.warning + ONE #27
    run-warning naming the read + `n/a` telemetry, and the warm PROCEEDS with
    the base set (the reader's try is separate from, and before, the wholesale
    try -- a reader inside it would lose the warm)."""
    _conn, cfg, lease = _world(tmp_db_at_head, tmp_path)
    if case == "selector":
        def _raise(*_a, **_k):
            raise RuntimeError("detections table locked")
        monkeypatch.setattr(pde, "list_observable_detections", _raise)
        cause = "RuntimeError: detections table locked"
    else:
        def _raise_anchor(*_a, **_k):
            raise TypeError("no run row")
        monkeypatch.setattr(rmod, "lease_data_asof", _raise_anchor)
        cause = "TypeError: no run row"
    warm_calls = _recording_warm(monkeypatch)
    run_warnings: list[dict] = []
    with caplog.at_level(logging.INFO, logger=rmod.log.name):
        rmod._prewarm_evaluate_archives(
            cfg=cfg, candidate_tickers=["AAA"], universe_tickers=["UUU"],
            run_now=None, run_warnings=run_warnings, lease=lease,
        )
    assert warm_calls == [["SPY", "AAA", "UUU"]]
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert "open-detection cohort read failed" in run_warnings[0]["reason"]
    assert cause in run_warnings[0]["reason"]
    lines = [r.getMessage() for r in caplog.records
             if r.getMessage().startswith("evaluate warm:")]
    assert len(lines) == 1
    assert lines[0].endswith("open_det=n/a open_det_added=n/a"), lines[0]
    warnings = [r for r in caplog.records
                if r.name == rmod.log.name and r.levelno == logging.WARNING]
    assert len(warnings) == 1


def test_reader_closes_its_connection_on_failure(tmp_path, monkeypatch) -> None:
    """F10 (1): the reader's own connection is closed in `finally`, including
    when the selector raises."""
    closed = {"flag": False}

    class _FakeConn:
        def close(self):
            closed["flag"] = True

    monkeypatch.setattr(rmod, "lease_data_asof", lambda cfg, lease: "2026-06-10")
    monkeypatch.setattr(rmod, "connect", lambda *_a, **_k: _FakeConn())

    def _raise(*_a, **_k):
        raise RuntimeError("detections table locked")

    monkeypatch.setattr(pde, "list_observable_detections", _raise)
    _recording_warm(monkeypatch)
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(tmp_path / "unused.db", tmp_path), candidate_tickers=["AAA"],
        universe_tickers=[], run_now=None, run_warnings=run_warnings,
        lease=_FakeLease(tmp_path / "unused.db", 1, "2026-06-10"),
    )
    assert closed["flag"] is True
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert "open-detection cohort read failed" in run_warnings[0]["reason"]
    assert "RuntimeError: detections table locked" in run_warnings[0]["reason"]
