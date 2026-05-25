"""Typed exceptions for the pattern cohort detector evaluator harness."""
from __future__ import annotations

# Re-export the V2 OHLCV reader's existing OhlcvCoverageError so the harness
# exception surface is single-rooted at this module + matches V2 OHLCV's
# precedent (a re-export, NOT a duplicate class declaration; subclass-identity
# preservation is BINDING for downstream isinstance / except clauses).
from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
    OhlcvCoverageError,
)


class PatternCohortEvaluatorError(Exception):
    """Base class for harness-emitted typed exceptions.

    Discriminates harness-internal errors from production-surfaced errors
    (OhlcvCoverageError from V2 reader; ValueError from CLI parse boundary;
    etc.) per cumulative T-A.1.5b CLI-boundary discipline.
    """


class CohortInputSchemaError(PatternCohortEvaluatorError):
    """Raised when CSV input has missing required columns OR unrecognized
    optional columns. Message enumerates the missing/unrecognized column
    names per cumulative gotcha "Synthetic-fixture-vs-production-emitter
    shape drift" (T-A.1.5b + T-A.1.8 pattern).
    """


class MalformedAsofDateError(PatternCohortEvaluatorError):
    """Raised when cohort entry's asof_date is not a valid ISO YYYY-MM-DD
    string (cumulative gotcha #12 discipline; typed exception NOT TypeError
    deep in stack).
    """


class BothCohortModesSuppliedError(PatternCohortEvaluatorError):
    """Raised when CLI receives BOTH --cohort-csv AND --cohort-inline.
    Exactly one is required.
    """


class NeitherCohortModeSuppliedError(PatternCohortEvaluatorError):
    """Raised when CLI receives NEITHER --cohort-csv NOR --cohort-inline.
    Exactly one is required.
    """


__all__ = (
    "OhlcvCoverageError",
    "PatternCohortEvaluatorError",
    "CohortInputSchemaError",
    "MalformedAsofDateError",
    "BothCohortModesSuppliedError",
    "NeitherCohortModeSuppliedError",
)
