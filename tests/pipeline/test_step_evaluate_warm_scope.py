"""Arc 17-A LOCK #16 regression: _step_evaluate fires the warm + prewarm at the
held-tickers boundary with the EXACT ticker sets (Codex R2).

The warm gets the captured HELD set; the prewarm gets the merged screen∪held∪pins
set as candidate_tickers + universe.tickers separately. This test must pass
IDENTICALLY on the pre-refactor _step_evaluate and the post-refactor adapter --
written FIRST against current code, then kept green through the orchestrator swap.

Drives the REAL _step_evaluate through the Phase-0 offline-archive fixtures (the
warm/prewarm are monkeypatched to RECORDERS, not no-ops, so their kwargs are
captured; everything else runs for real offline).
"""
# ruff: noqa: F811 -- pytest fixtures imported from the Phase-0 harness module are
# re-bound as test-function parameters; that is the intended pytest pattern.
from __future__ import annotations

import swing.pipeline.runner as runner_mod
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.prices import PriceFetcher
from tests.evaluation.test_orchestration_parity_golden import (  # noqa: F401
    HELD_TICKER,
    PINNED_TICKER,
    RUN_NOW,
    SCREEN_TICKERS,
    SESSION,
    _build_inputs,
    _FakeLease,
    _make_config,
    _seed_open_and_pins,
    _seed_running_run,
    frozen_clock,
    pin_network,
)


def test_warm_and_prewarm_receive_exact_ticker_sets(tmp_path, frozen_clock, pin_network):
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _seed_open_and_pins(inputs.db_path)   # open trade HHH + pinned PPP
    _seed_running_run(inputs.db_path, 1)
    lease = _FakeLease(inputs.db_path, 1)

    warm_calls: list[dict] = []
    prewarm_calls: list[dict] = []

    def _rec_warm(**kwargs):
        warm_calls.append(kwargs)

    def _rec_prewarm(**kwargs):
        prewarm_calls.append(kwargs)

    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_mod, "_warm_pipeline_marketdata", _rec_warm)
    monkeypatch.setattr(runner_mod, "_prewarm_evaluate_archives", _rec_prewarm)
    try:
        universe = load_universe(cfg.paths.rs_universe_path)
        uhash = universe_version_hash(cfg.paths.rs_universe_path)
        fetcher = PriceFetcher(
            cache_dir=inputs.cache_dir, archive_history_days=cfg.archive.archive_history_days
        )
        runner_mod._step_evaluate(
            cfg=cfg, fetcher=fetcher, csv_path=inputs.csv_path, universe=universe,
            universe_hash=uhash, run_now=RUN_NOW, action_session=SESSION,
            lease=lease, price_cache=None, run_warnings=[],
        )
    finally:
        monkeypatch.undo()

    # The warm gets the captured HELD set (NOT the merged set).
    assert len(warm_calls) == 1
    assert warm_calls[0]["held_tickers"] == [HELD_TICKER]

    # The prewarm gets the merged screen∪held∪pins set (same insertion order) as
    # candidate_tickers, plus universe.tickers separately.
    assert len(prewarm_calls) == 1
    assert prewarm_calls[0]["candidate_tickers"] == [*SCREEN_TICKERS, HELD_TICKER, PINNED_TICKER]
    assert prewarm_calls[0]["universe_tickers"] == universe.tickers
    # D83 (gotcha #31, the CALLER-SIDE obligation): the hook hands the prewarm
    # the run's own lease, which the open-detection cohort read is anchored on.
    assert prewarm_calls[0]["lease"] is lease


def test_evaluate_runs_when_the_open_detection_read_raises(
        tmp_path, frozen_clock, pin_network):
    """D83 condition (iii) at evaluate level: the open-detection cohort read
    raising cannot sink the warm, let alone evaluate. The REAL prewarm runs; the
    warm proceeds with the base cohort and the failure is a #27 run-warning."""
    from swing.data.ohlcv_archive import WarmReport

    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _seed_open_and_pins(inputs.db_path)   # open trade HHH + pinned PPP
    _seed_running_run(inputs.db_path, 1)

    warm_batch_calls: list[list[str]] = []

    def _rec_warm_batch(tickers, **kwargs):
        warm_batch_calls.append(list(tickers))
        return WarmReport()

    def _raise(*_a, **_k):
        raise RuntimeError("detections table locked")

    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_mod, "_warm_pipeline_marketdata", lambda **_k: None)
    monkeypatch.setattr(runner_mod, "warm_archives_batch", _rec_warm_batch)
    monkeypatch.setattr(
        "swing.data.repos.pattern_detection_events.list_observable_detections", _raise)
    run_warnings: list[dict] = []
    try:
        universe = load_universe(cfg.paths.rs_universe_path)
        uhash = universe_version_hash(cfg.paths.rs_universe_path)
        fetcher = PriceFetcher(
            cache_dir=inputs.cache_dir, archive_history_days=cfg.archive.archive_history_days
        )
        eval_run_id = runner_mod._step_evaluate(
            cfg=cfg, fetcher=fetcher, csv_path=inputs.csv_path, universe=universe,
            universe_hash=uhash, run_now=RUN_NOW, action_session=SESSION,
            lease=_FakeLease(inputs.db_path, 1), price_cache=None,
            run_warnings=run_warnings,
        )
    finally:
        monkeypatch.undo()

    assert isinstance(eval_run_id, int)
    reader = [w for w in run_warnings
              if "open-detection cohort read failed" in w.get("reason", "")]
    assert len(reader) == 1, run_warnings
    assert reader[0]["step"] == "evaluate_warm"
    assert "RuntimeError: detections table locked" in reader[0]["reason"]
    assert warm_batch_calls == [[
        cfg.rs.benchmark_ticker, *SCREEN_TICKERS, HELD_TICKER, PINNED_TICKER,
        *universe.tickers,
    ]]
