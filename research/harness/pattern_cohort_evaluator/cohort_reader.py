"""Cohort input parser for the pattern cohort detector evaluator harness.

Per spec §C.1 + §C.2: cohort entry tuple shape; Mode (a) inline parser;
Mode (b) CSV parser. Per cumulative gotcha #12: ISO-date parsing raises
typed MalformedAsofDateError NOT TypeError. Per cumulative T-A.1.5b
synthetic-fixture-vs-production-emitter shape drift: required columns
validated with typed CohortInputSchemaError enumerating missing names.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from research.harness.pattern_cohort_evaluator.exceptions import (
    CohortInputSchemaError,
    MalformedAsofDateError,
)

_REQUIRED_CSV_COLUMNS: frozenset[str] = frozenset({"ticker", "asof_date"})
_OPTIONAL_CSV_COLUMNS: frozenset[str] = frozenset(
    {
        "candidate_id",
        "eval_run_id",
        "bucket",
        "pivot",
        "initial_stop",
        "pattern_class_filter",
        "cohort_label",
    }
)
_ALL_RECOGNIZED_COLUMNS: frozenset[str] = (
    _REQUIRED_CSV_COLUMNS | _OPTIONAL_CSV_COLUMNS
)

# Per spec §I.2 + cumulative gotcha #15 (Expansion #11 taxonomy propagation):
# the 5 V1 pattern_class values are enumerated explicitly + propagated to
# per-entry pattern_class_filter validation + detector_invoker dispatch +
# output rendering.
_ALLOWED_PATTERN_CLASSES: frozenset[str] = frozenset(
    {"vcp", "flat_base", "cup_with_handle", "high_tight_flag", "double_bottom_w"}
)


@dataclass(frozen=True)
class CohortEntry:
    """One operator-supplied cohort entry.

    Required: ticker + asof_date.
    Optional: candidate_id + eval_run_id + bucket + pivot + initial_stop +
              pattern_class_filter + cohort_label.

    Per cumulative gotcha "Literal[...] type hints are NOT runtime-enforced":
    pattern_class_filter (when set) validated against _ALLOWED_PATTERN_CLASSES
    in __post_init__.
    """
    ticker: str
    asof_date: date
    candidate_id: int | None = None
    eval_run_id: int | None = None
    bucket: str | None = None
    pivot: float | None = None
    initial_stop: float | None = None
    pattern_class_filter: str | None = None
    cohort_label: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ticker, str) or not self.ticker:
            raise CohortInputSchemaError(
                f"CohortEntry.ticker must be a non-empty str, got {self.ticker!r}"
            )
        if not isinstance(self.asof_date, date):
            raise CohortInputSchemaError(
                f"CohortEntry.asof_date must be datetime.date, got "
                f"{type(self.asof_date).__name__}"
            )
        if (
            self.pattern_class_filter is not None
            and self.pattern_class_filter not in _ALLOWED_PATTERN_CLASSES
        ):
            raise CohortInputSchemaError(
                f"CohortEntry.pattern_class_filter must be one of "
                f"{sorted(_ALLOWED_PATTERN_CLASSES)}, "
                f"got {self.pattern_class_filter!r}"
            )


def parse_asof_date(raw: str) -> date:
    """Parse ISO YYYY-MM-DD string -> datetime.date.

    Raises:
      MalformedAsofDateError: per cumulative gotcha #12 -- must be typed
        exception, NOT TypeError deep in Python stack.
    """
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise MalformedAsofDateError(
            f"cohort asof_date malformed: {raw!r}; "
            f"expected ISO YYYY-MM-DD string"
        ) from exc


def parse_inline_cohort(spec: str) -> tuple[CohortEntry, ...]:
    """Parse Mode (a) comma-separated `ticker:asof_date` pairs.

    Example: "RLMD:2026-04-15,DNTH:2026-04-15,RNG:2026-04-15" -> 3 entries.

    Mode (a) does NOT support optional metadata fields per §C.2 LOCK; use
    Mode (b) CSV for full-shape cohorts.

    Raises:
      CohortInputSchemaError: when a pair lacks the `:` separator OR contains
        more than one `:` per pair.
      MalformedAsofDateError: per parse_asof_date.
    """
    entries: list[CohortEntry] = []
    for raw_pair in spec.split(","):
        pair = raw_pair.strip()
        if not pair:
            continue
        if pair.count(":") != 1:
            raise CohortInputSchemaError(
                f"inline cohort pair must contain exactly one ':' separator, "
                f"got {pair!r}"
            )
        ticker_raw, date_raw = pair.split(":", 1)
        entries.append(
            CohortEntry(
                ticker=ticker_raw.strip().upper(),
                asof_date=parse_asof_date(date_raw.strip()),
            )
        )
    if not entries:
        raise CohortInputSchemaError(
            f"inline cohort spec parsed to zero entries: {spec!r}"
        )
    return tuple(entries)


def read_cohort_csv(path: Path) -> tuple[CohortEntry, ...]:
    """Parse Mode (b) CSV input per §C.2.

    Required CSV columns: ticker, asof_date.
    Optional CSV columns: candidate_id, eval_run_id, bucket, pivot,
      initial_stop, pattern_class_filter, cohort_label.

    Per cumulative gotcha #18 (Expansion #4 refinement: empty-input handling):
    an empty CSV (header-only) returns an empty tuple. NOT raises.

    Raises:
      CohortInputSchemaError: when required columns missing OR unrecognized
        columns present (enumerated in message).
      MalformedAsofDateError: per parse_asof_date.
      FileNotFoundError: when path does not exist (propagated to CLI boundary).
    """
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = frozenset(reader.fieldnames or ())
        missing = _REQUIRED_CSV_COLUMNS - fieldnames
        if missing:
            raise CohortInputSchemaError(
                f"cohort CSV at {path} missing required columns: "
                f"{sorted(missing)}; found columns: {sorted(fieldnames)}"
            )
        unrecognized = fieldnames - _ALL_RECOGNIZED_COLUMNS
        if unrecognized:
            raise CohortInputSchemaError(
                f"cohort CSV at {path} contains unrecognized columns: "
                f"{sorted(unrecognized)}; allowed: "
                f"{sorted(_ALL_RECOGNIZED_COLUMNS)}"
            )
        entries: list[CohortEntry] = []
        for row in reader:
            entries.append(_row_to_cohort_entry(row))
    return tuple(entries)


def _row_to_cohort_entry(row: dict[str, str]) -> CohortEntry:
    """Convert one CSV dict row to a CohortEntry with optional-field coercion.

    Per cumulative gotcha "Python ... or '' idiom collides with SQL
    CHECK-constraint nullability" + uniform empty-state per OQ-12 LOCK:
    empty-string CSV cells coerce to None NOT empty string.
    """

    def _opt_str(v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return v.strip()

    def _opt_int(v: str | None) -> int | None:
        s = _opt_str(v)
        if s is None:
            return None
        try:
            return int(s)
        except ValueError as exc:
            raise CohortInputSchemaError(
                f"cohort CSV row int field malformed: {v!r}"
            ) from exc

    def _opt_float(v: str | None) -> float | None:
        s = _opt_str(v)
        if s is None:
            return None
        try:
            return float(s)
        except ValueError as exc:
            raise CohortInputSchemaError(
                f"cohort CSV row float field malformed: {v!r}"
            ) from exc

    ticker_raw = _opt_str(row.get("ticker"))
    if ticker_raw is None:
        raise CohortInputSchemaError(
            f"cohort CSV row missing required ticker field: {row!r}"
        )
    asof_raw = _opt_str(row.get("asof_date"))
    if asof_raw is None:
        raise CohortInputSchemaError(
            f"cohort CSV row missing required asof_date field: {row!r}"
        )
    return CohortEntry(
        ticker=ticker_raw.upper(),
        asof_date=parse_asof_date(asof_raw),
        candidate_id=_opt_int(row.get("candidate_id")),
        eval_run_id=_opt_int(row.get("eval_run_id")),
        bucket=_opt_str(row.get("bucket")),
        pivot=_opt_float(row.get("pivot")),
        initial_stop=_opt_float(row.get("initial_stop")),
        pattern_class_filter=_opt_str(row.get("pattern_class_filter")),
        cohort_label=_opt_str(row.get("cohort_label")),
    )
