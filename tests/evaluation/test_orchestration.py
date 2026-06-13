"""Unit tests for the shared evaluation orchestrator (Arc 17-A)."""
from __future__ import annotations

import inspect
from dataclasses import MISSING, fields

import pytest


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
        "current_equity", "persist", "as_of_date", "augmentation",
        "pre_fetch_hook", "output", "behavior",
    }

    # OrchestrationOutput defaults are no-op callables.
    assert callable(OrchestrationOutput().info)
    assert callable(OrchestrationOutput().warn)
    assert callable(OrchestrationOutput().note_pin_injection)

    # OrchestrationResult carries run_id / run / candidates.
    assert {f.name for f in fields(OrchestrationResult)} == {"run_id", "run", "candidates"}
