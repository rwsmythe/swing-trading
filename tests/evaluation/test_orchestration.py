"""Unit tests for the shared evaluation orchestrator (Arc 17-A)."""
# ruff: noqa: F811 -- pytest fixtures imported from the Phase-0 harness module are
# re-bound as test-function parameters; that is the intended pytest pattern.
from __future__ import annotations

import inspect
import sqlite3
from dataclasses import MISSING, fields
from datetime import date

import pytest

from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.prices import PriceFetcher

# Reuse the Phase-0 offline-archive fixtures + helpers (real derivation chain).
from tests.evaluation.test_orchestration_parity_golden import (  # noqa: F401
    HELD_TICKER,
    PINNED_TICKER,
    RUN_NOW,
    SCREEN_TICKERS,
    _build_inputs,
    _make_config,
    _migrate,
    frozen_clock,
    pin_network,
)


def test_orchestration_public_surface():
    from swing.evaluation.orchestration import (
        EvaluationBehaviorPolicy,
        OrchestrationOutput,
        OrchestrationResult,
        UniverseAugmentation,
        orchestrate_evaluation,
    )

    assert UniverseAugmentation().held_tickers == ()
    assert UniverseAugmentation().pinned_inject == ()

    # C1 (CHARC 2026-06-12): EvaluationBehaviorPolicy has NO field defaults -- every
    # field is required, so a zero-arg construction is impossible.
    assert all(
        f.default is MISSING and f.default_factory is MISSING
        for f in fields(EvaluationBehaviorPolicy)
    )
    with pytest.raises(TypeError):
        EvaluationBehaviorPolicy()  # cannot construct without stating every field

    # Task-C rulings: only spy_failure_mode survives as an intentional policy field
    # (dedup_error_rows + preserve_held_close were ruled unify -> deleted).
    assert {f.name for f in fields(EvaluationBehaviorPolicy)} == {"spy_failure_mode"}

    # `behavior` is a REQUIRED keyword arg of orchestrate_evaluation (no default).
    sig = inspect.signature(orchestrate_evaluation)
    assert sig.parameters["behavior"].default is inspect.Parameter.empty
    assert set(sig.parameters) == {
        "cfg", "csv_path", "universe", "universe_hash", "run_now", "fetcher",
        "current_equity", "persist", "as_of_date", "action_session",
        "augmentation", "pre_fetch_hook", "output", "behavior",
    }

    # OrchestrationOutput defaults are no-op callables.
    assert callable(OrchestrationOutput().info)
    assert callable(OrchestrationOutput().warn)
    assert callable(OrchestrationOutput().note_pin_injection)

    # OrchestrationResult carries run_id / run / candidates.
    assert {f.name for f in fields(OrchestrationResult)} == {"run_id", "run", "candidates"}


# --------------------------------------------------------------------------- #
# Task 1.2: orchestrator body driven directly through the offline derivation chain.
# --------------------------------------------------------------------------- #
def _orch_kwargs(inputs, cfg, *, augmentation=None, output=None, pre_fetch_hook=None,
                 persist=None, spy_failure_mode="warn_and_zero"):
    from swing.evaluation.orchestration import (
        EvaluationBehaviorPolicy,
        OrchestrationOutput,
        UniverseAugmentation,
    )
    universe = load_universe(cfg.paths.rs_universe_path)
    uhash = universe_version_hash(cfg.paths.rs_universe_path)
    fetcher = PriceFetcher(
        cache_dir=inputs.cache_dir, archive_history_days=cfg.archive.archive_history_days
    )
    return dict(
        cfg=cfg, csv_path=inputs.csv_path, universe=universe, universe_hash=uhash,
        run_now=RUN_NOW, fetcher=fetcher,
        current_equity=cfg.account.starting_equity,
        persist=persist if persist is not None else _plain_persist(inputs.db_path),
        as_of_date=None,
        augmentation=augmentation if augmentation is not None else UniverseAugmentation(),
        pre_fetch_hook=pre_fetch_hook,
        output=output if output is not None else OrchestrationOutput(),
        behavior=EvaluationBehaviorPolicy(spy_failure_mode=spy_failure_mode),
    )


def _plain_persist(db_path):
    def persist(run, candidates):
        conn = sqlite3.connect(db_path)
        try:
            with conn:
                run_id = insert_evaluation_run(conn, run)
                insert_candidates(conn, run_id, candidates)
        finally:
            conn.close()
        return run_id
    return persist


def test_orchestrator_empty_augmentation_screen_only(tmp_path, frozen_clock, pin_network):
    from swing.evaluation.orchestration import OrchestrationOutput, orchestrate_evaluation
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    notes: list[list[str]] = []
    result = orchestrate_evaluation(**_orch_kwargs(
        inputs, cfg,
        output=OrchestrationOutput(note_pin_injection=lambda t: notes.append(t)),
    ))
    tickers = {c.ticker for c in result.candidates}
    assert tickers == set(SCREEN_TICKERS)
    assert HELD_TICKER not in tickers and PINNED_TICKER not in tickers
    assert notes == []  # no pin injection fired


def test_orchestrator_held_excluded_close_preserved(tmp_path, frozen_clock, pin_network):
    from swing.evaluation.orchestration import (
        OrchestrationOutput,
        UniverseAugmentation,
        orchestrate_evaluation,
    )
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    notes: list[list[str]] = []
    result = orchestrate_evaluation(**_orch_kwargs(
        inputs, cfg,
        augmentation=UniverseAugmentation(held_tickers=(HELD_TICKER,)),
        output=OrchestrationOutput(note_pin_injection=lambda t: notes.append(t)),
    ))
    held = [c for c in result.candidates if c.ticker == HELD_TICKER]
    assert len(held) == 1
    assert held[0].bucket == "excluded"
    assert held[0].close == pytest.approx(35.14)  # EXCLUDED-CLOSE unified: preserved
    assert held[0].notes == "open position"
    assert notes == []  # held is NOT pin-injected


def test_orchestrator_pin_injected_fully_evaluated(tmp_path, frozen_clock, pin_network):
    from swing.evaluation.orchestration import (
        OrchestrationOutput,
        UniverseAugmentation,
        orchestrate_evaluation,
    )
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    notes: list[list[str]] = []
    result = orchestrate_evaluation(**_orch_kwargs(
        inputs, cfg,
        augmentation=UniverseAugmentation(pinned_inject=(PINNED_TICKER,)),
        output=OrchestrationOutput(note_pin_injection=lambda t: notes.append(t)),
    ))
    pinned = [c for c in result.candidates if c.ticker == PINNED_TICKER]
    assert len(pinned) == 1
    assert pinned[0].bucket in {"aplus", "watch", "skip"}
    assert notes == [[PINNED_TICKER]]  # fired once with the injected list


def test_orchestrator_persist_invoked_once(tmp_path, frozen_clock, pin_network):
    from swing.evaluation.orchestration import orchestrate_evaluation
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    calls: list[tuple] = []

    def persist(run, candidates):
        calls.append((run, candidates))
        return 4242

    result = orchestrate_evaluation(**_orch_kwargs(inputs, cfg, persist=persist))
    assert len(calls) == 1
    assert result.run_id == 4242
    assert calls[0][1] is result.candidates


def test_orchestrator_pre_fetch_hook_called_once_with_merged(tmp_path, frozen_clock, pin_network):
    from swing.evaluation.orchestration import UniverseAugmentation, orchestrate_evaluation
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    seen_args: list[list[str]] = []
    orchestrate_evaluation(**_orch_kwargs(
        inputs, cfg,
        augmentation=UniverseAugmentation(
            held_tickers=(HELD_TICKER,), pinned_inject=(PINNED_TICKER,)
        ),
        pre_fetch_hook=lambda merged: seen_args.append(list(merged)),
    ))
    assert len(seen_args) == 1
    # screen ∪ held ∪ pins, in insertion order.
    assert seen_args[0] == [*SCREEN_TICKERS, HELD_TICKER, PINNED_TICKER]


def test_orchestrator_honors_passed_action_session(tmp_path, frozen_clock, pin_network):
    """Codex R1 Major #1: the orchestrator persists the EXPLICITLY-passed
    action_session (the pipeline adapter forwards the run-level value it captured),
    not a recomputed one -- byte-faithful to the pre-refactor _step_evaluate."""
    from swing.evaluation.orchestration import orchestrate_evaluation
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    distinct = date(2026, 7, 1)  # NOT action_session_for_run(RUN_NOW) (= 2026-06-12)
    result = orchestrate_evaluation(
        **_orch_kwargs(inputs, cfg), action_session=distinct
    )
    assert result.run.action_session_date == distinct.isoformat()


def test_orchestrator_derives_action_session_when_none(tmp_path, frozen_clock, pin_network):
    """When no action_session is supplied (the CLI adapter), the orchestrator
    derives it from run_now via action_session_for_run -- the CLI's prior
    self-computation."""
    from swing.evaluation.orchestration import orchestrate_evaluation
    inputs = _build_inputs(tmp_path)
    cfg = _make_config(tmp_path, inputs)
    _migrate(inputs.db_path).close()
    result = orchestrate_evaluation(**_orch_kwargs(inputs, cfg))  # action_session defaults None
    assert result.run.action_session_date == date(2026, 6, 12).isoformat()
