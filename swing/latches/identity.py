"""The latch identity -- BOTH id spaces, stored explicitly (RD finding 4).

`(evaluation_run_id, ticker)` freezes pivot/stop; the shadow artifact keys on
`(ticker, detection_date)` and those are DIFFERENT id spaces (evaluation_runs
vs pipeline_runs -- pipeline_runs.id 126 is action session 2026-07-08 while
evaluation_runs.id 126 is 2026-07-27). Storing only one makes the shadow join
derivable-by-convention rather than exact: cheap now, unrecoverable later.

`candidate_id` (the OPENING fire's candidates.id) is the canonical surrogate
latch key -- exact (candidates has UNIQUE(evaluation_run_id, ticker)),
immutable (no UPDATE/DELETE path exists for candidates), and already an
established FK target (trades.candidate_id, migration 0021).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# The SHARED contract. 21-B's order-intent ledger copies these five column
# names VERBATIM so the two ledgers join exactly on candidate_id. Order is
# load-bearing: tests/data/test_migration_0032.py pins the migration against it.
LATCH_IDENTITY_COLUMNS: tuple[str, ...] = (
    "candidate_id", "evaluation_run_id", "ticker",
    "detection_date", "pipeline_run_id",
)


def _require_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be int (not bool); got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}")


def parse_session_date(name: str, value) -> date:
    """Convert an ISO YYYY-MM-DD TEXT column value to a `date`, or raise.

    The TEXT-column -> Python-date boundary: convert at the callsite with a
    typed error rather than letting a deep TypeError escape (CLAUDE.md).
    """
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{name} must be an ISO YYYY-MM-DD str; got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO date: {value!r}") from exc


@dataclass(frozen=True)
class LatchIdentity:
    candidate_id: int
    evaluation_run_id: int
    ticker: str
    detection_date: str          # == the FIRE's evaluation_runs.action_session_date
    pipeline_run_id: int | None

    def __post_init__(self) -> None:
        _require_positive_int("candidate_id", self.candidate_id)
        _require_positive_int("evaluation_run_id", self.evaluation_run_id)
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError(f"ticker must be a non-blank str; got {self.ticker!r}")
        parse_session_date("detection_date", self.detection_date)
        if self.pipeline_run_id is not None:
            _require_positive_int("pipeline_run_id", self.pipeline_run_id)

    @property
    def detection_session(self) -> date:
        return parse_session_date("detection_date", self.detection_date)
