"""Shared evaluation-run orchestration (Arc 17-A).

ONE orchestration path consumed by both entry points -- standalone `swing eval`
(`swing/cli.py:eval_cmd`) and the nightly pipeline (`swing/pipeline/runner.py:
_step_evaluate`) -- so they persist classification identically, modulo the
operator-ruled intentional differences carried on explicit injection seams.

The genuinely-different concerns are injected:
  - `augmentation`     -- the held/pin universe union (DIVERGENCE-1/2, intentional:
                          pipeline supplies sets; CLI supplies an empty one).
  - `current_equity`   -- the per-ticker sizing equity (DIVERGENCE-EQUITY, unified:
                          both adapters pass `sizing_equity(...)`).
  - `behavior`         -- the SPY-failure policy (DIVERGENCE-SPY-GUARD, intentional).
  - `pre_fetch_hook`   -- LOCK #16: the pipeline's warm+prewarm at the held-tickers
                          boundary; CLI passes None.
  - `output`           -- click.echo vs run-warnings channel.
  - `persist`          -- LOCK #1: plain `with conn:` (CLI) vs `lease.fenced_write()`
                          + `set_evaluation_run_id` (pipeline). The orchestrator
                          NEVER imports Lease.
  - `as_of_date`       -- the CLI's parity flag; pipeline passes None.

DIVERGENCE-ERROR-DEDUP and DIVERGENCE-EXCLUDED-CLOSE were ruled UNIFY, so their
behaviors are unconditional shared code here (the corresponding policy fields were
deleted). See docs/phase17-arc-a-task-c-divergence-rulings.md.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from swing.data.models import Candidate, EvaluationRun


@dataclass(frozen=True)
class UniverseAugmentation:
    """Extra tickers folded into one evaluation run beyond the finviz screen.

    held_tickers:  open-position tickers -- close-ONLY (added to `excluded`, no
                   buy/watch decision, fresh close preserved for the dashboard
                   price fallback). Supplied by the pipeline adapter.
    pinned_inject: Arc-7 pinned off-screen tickers -- FULL evaluate_batch pass.
                   Supplied by the pipeline adapter.

    Empty default == the standalone-eval universe (finviz screen only).
    """
    held_tickers: tuple[str, ...] = ()
    pinned_inject: tuple[str, ...] = ()


# Module-level singleton for the empty-augmentation default (frozen -> safe to
# share; avoids a call-in-argument-default, ruff B008).
_EMPTY_AUGMENTATION = UniverseAugmentation()


@dataclass
class OrchestrationOutput:
    """Output channel seam. CLI wires click.echo; pipeline wires run-warnings."""
    info: Callable[[str], None] = lambda _msg: None
    warn: Callable[[str], None] = lambda _msg: None
    note_pin_injection: Callable[[list[str]], None] = lambda _tickers: None


@dataclass
class OrchestrationResult:
    run_id: int
    run: EvaluationRun
    candidates: list[Candidate]


@dataclass(frozen=True)
class EvaluationBehaviorPolicy:
    """Error-path behavior that the Task-C operator rulings keep as an intentional
    injected-seam difference.

    C1 -- EXPLICIT CONSTRUCTION, NO DEFAULTS (CHARC ratification 2026-06-12,
    docs/phase17-arc-a-charc-ratification.md): every field is REQUIRED with NO
    default; BOTH adapters construct the policy explicitly, stating every field at
    the call site (never `EvaluationBehaviorPolicy()`). A defaulted field is a
    silent-inheritance channel -- exactly the disease this arc cures.

    C2 -- the field set equals EXACTLY the operator-ruled-INTENTIONAL policy-field
    divergences. After the Task-C rulings (docs/phase17-arc-a-task-c-divergence-
    rulings.md) only `spy_failure_mode` survives; `dedup_error_rows` and
    `preserve_held_close` were ruled UNIFY and deleted (their behaviors are now
    unconditional shared code in `orchestrate_evaluation`).

    spy_failure_mode:  "raise" (pipeline: a SPY fetch exception fails the step) |
                       "warn_and_zero" (CLI: warn + spy_return=0.0, continue).
    """
    spy_failure_mode: str


def orchestrate_evaluation(
    *,
    cfg,
    csv_path: Path,
    universe,
    universe_hash: str,
    run_now: datetime,
    fetcher,
    current_equity: float,
    persist: Callable[[EvaluationRun, list[Candidate]], int],
    as_of_date: date | None = None,
    augmentation: UniverseAugmentation = _EMPTY_AUGMENTATION,
    pre_fetch_hook: Callable[[list[str]], None] | None = None,
    output: OrchestrationOutput | None = None,
    behavior: EvaluationBehaviorPolicy,  # C1: REQUIRED keyword arg, no default instance
) -> OrchestrationResult:
    raise NotImplementedError
