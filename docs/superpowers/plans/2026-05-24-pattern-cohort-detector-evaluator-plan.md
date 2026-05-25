# Pattern Cohort Detector Evaluator Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship pattern cohort detector evaluator research harness as a NEW research-branch module under `research/harness/pattern_cohort_evaluator/` that invokes the 5 Phase 13 chart-shape detectors (`vcp`, `flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`) against an operator-supplied cohort of `(ticker, asof_date)` tuples (CSV or inline list) and emits per-(cohort_entry, pattern_class, window) verdict CSV + analyst-readable markdown summary + manifest JSON. Designed to answer: *do Phase 13 detectors filter loosened-A+ candidates productively?* — the architectural answer to gotcha #27's silent-skip-without-audit motivation.

**Architecture:** NEW module per spec §B.1 architecture-location LOCK + Expansion #10 discipline; 5-sub-bundle decomposition (T-PC.1..T-PC.5); read-only Shape A parquet read via RE-EXPORT of V2 OHLCV evaluator's existing `ohlcv_reader.py` (per OQ-3 LOCK; zero-drift between two read-only Shape-A readers); production detector registry re-imported from `swing.pipeline.runner._pattern_detect_registry()` (per OQ-1 LOCK; cascade-call-graph audit per gotcha #19); production `swing/` code is READ-ONLY except for one explicit minimal CLI subcommand registration carve-out at `swing/cli.py` per OQ-13 LOCK (35-60 lines, mirroring V2 OHLCV evaluator's OQ-17 V1 precedent at `swing/cli.py:4791-4859`); schema v21 UNCHANGED; harness output emits to `exports/research/pattern-cohort-detection-<ISO>/` only.

**Tech Stack:** Python 3.11+ (3.14 on operator's box), pandas (parquet I/O re-exported via V2 OHLCV reader), sqlite3 (read-only via URI `mode=ro` per V2 OHLCV evaluator's Codex R2.M2 precedent; consumed by `current_stage` for Stage-2 gate + `list_exemplars` for template-match Pass 2 corpus), Click (CLI subcommand registration), pytest (TDD per task; **~55-71 NEW fast tests** projected per §H; parametrize-consolidated bound ~50-65; ZERO slow tests). NO yfinance / NO schwabdev / NO swing.data.ohlcv_archive / NO swing.integrations.schwab imports in the harness module set (defense-in-depth per L2 LOCK + 5 BINDING discriminating tests at §F + §K).

---

## §A Status + scope (binding context)

### §A.1 Lineage

Pattern cohort detector evaluator harness is the SECOND Applied Research arc post-Phase-13-FULLY-CLOSED per operator Option D LOCK 2026-05-24 PM at `docs/applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md` commit `8ba87cd`. Brainstorming spec at [`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`](../specs/2026-05-24-pattern-cohort-detector-evaluator-design.md) (996 lines; 14 sections §A-§N) is BINDING substrate; brainstorming-phase Codex MCP review was OPTIONAL per dispatch brief and NOT fired per operator-paired discretion. Brainstorming return report at [`docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md`](../../applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md) (188 lines) documents 8 V2/V3-dependency-cited candidates banked + pre-Codex 7-expansion + 5 NEW candidate refinements applied at spec-write time. Writing-plans dispatch brief at [`docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-dispatch-brief.md`](../../applied-research-pattern-cohort-detector-evaluator-writing-plans-dispatch-brief.md) (~178 lines; 6 sections) specifies plan deliverables per V2 OHLCV writing-plans precedent.

### §A.2 Research question addressed

Per spec §B + dispatch brief §7:

> Do Phase 13 chart-shape detectors confirm candidates that V1 sensitivity analysis identifies as binding at the watch→A+ boundary? IF YES (detector-pass + backtest-triggered cells diverge from detector-pass + backtest-untriggered cells): chart-shape detection adds orthogonal signal at the loosened threshold. IF NO (detector-pass and detector-fail cohorts have indistinguishable backtest outcomes): detection-vs-classification are independently calibrated; no orthogonal signal at this threshold.

The harness is the architecturally-correct answer to the question gotcha #27 surfaced (Phase 13 `_step_pattern_detect` gates on `bucket == 'aplus'` BY DESIGN per runner.py:1485-1490; cannot answer the loosened-cohort detector-confirmation research question via production pipeline). Per predecessor investigation Option D LOCKED at merge `54bd9c6`.

### §A.3 Production read-only invariant (with OQ-13 CLI carve-out)

Production `swing/` is READ-ONLY for the duration of this dispatch arc EXCEPT for the ONE explicit minimal CLI subcommand-registration carve-out in `swing/cli.py` per spec §A.1 + OQ-13 LOCK. The carve-out covers (a) `@click.command`-decorated handler + (b) `@diagnose_group.command` group attachment + (c) `@click.option` definitions + (d) `ClickException` wrapping per cumulative T-A.1.5b lesson + (e) delegation to `research.harness.pattern_cohort_evaluator.run.run_harness`. Realistic line count: 35-60 lines per V1 precedent at `swing/cli.py:4791-4859` (the V2 OHLCV evaluator's `aplus-sensitivity-v2` subcommand; 69 lines including blank-line separators — the V2 OHLCV plan §G.0 deviation log noted that as 71 vs 35-60 target). NO schema changes. NO migrations. NO writes to `swing-data/swing.db` (URI mode=ro). NO writes to OHLCV archive parquet files.

Discriminating gate at T-PC.4 ship: `git diff swing/ --stat` after executing-plans phase shows ONLY `swing/cli.py` modified.

### §A.4 13 OQ dispositions LOCKED (verbatim from spec §J + brief §1)

| OQ | Disposition LOCKED |
|---|---|
| OQ-1 Detector invocation interface | Direct production detector function invocation (re-import `_pattern_detect_registry` from `swing.pipeline.runner` per §D.2). NO cfg substitution V1. |
| OQ-2 Cohort input mode | V1 = Mode (b) CSV primary + Mode (a) inline fallback; Mode (c) SQL deferred V2.5+. |
| OQ-3 OHLCV reader source | Re-export V2 OHLCV evaluator's `ohlcv_reader.py` VERBATIM (single source of L2 LOCK truth). |
| OQ-4 Anchor mode (window generation) | Mirror production `zigzag_pivot` only; multi-mode deferred V2.5+. |
| OQ-5 Pattern-class filter scope | Per-entry CSV column + CLI global; per-entry takes precedence. |
| OQ-6 Template-match Pass 2 mode | Default `--template-match=on` (production-parity). |
| OQ-7 Window-mode (last-only vs per-window) | Default `--window-mode=per-window` (NON-production-default; deliberate per analytical purpose); operator can force `last-only` for parity testing. |
| OQ-8 `current_stage` Stage-2-gate override | Default production `current_stage`; per-entry `stage_override` deferred V2.5+. |
| OQ-9 First-cohort target | +67 watch→aplus flips at `vcp.tightness_range_factor=1.005` (15 unique tickers; per V2 OHLCV sensitivity backtest brief §1 drill-down at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`). |
| OQ-10 V1 harness CLI subcommand name | `swing diagnose pattern-cohort-detect`. |
| OQ-11 Both-exist diagnostic surface | Inherit V2 OHLCV evaluator's `BothExistDiagnostic`. |
| OQ-12 Empty-state representation | Uniform per T3.SB3 LOCK: `(none)` markdown / `null` CSV / `None` JSON. |
| OQ-13 CLI subcommand registration as production carve-out | Sole production-`swing/`-write carve-out per OQ-17 V2 OHLCV precedent (35-60 lines). |

### §A.5 Schema discipline (LOCK)

Schema v21 LOCKED. Harness does NOT touch migrations. Verified via brief §3.3 + spec §A.2: harness reads ONLY existing columns at `swing/data/migrations/0001_phase1_initial.sql:9-56` (via `current_stage` cascade through `candidates` + `evaluation_runs` + `candidate_criteria`) + `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` (via `list_exemplars` for template-match Pass 2 corpus). Discriminating gate at T-PC.5 closer: `git diff swing/data/migrations/ --stat` after ship shows ZERO files modified.

### §A.6 V1 persisted state read-only (BINDING)

Harness output lives in `exports/research/pattern-cohort-detection-<ISO>/` ONLY per spec §A.5 + §I.2. ZERO modification of `pattern_evaluations` / `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / V1 persisted state. DB connection opened via URI `mode=ro` per V2 OHLCV evaluator Codex R2.M2 precedent (defense-in-depth: any accidental INSERT/UPDATE/CREATE from harness module set raises `sqlite3.OperationalError: attempt to write a readonly database`).

### §A.7 Streaks preserved through this plan write

- ~519+ ZERO `Co-Authored-By` footer trailer cumulative (commit chain through brief commit `16f9efc`).
- Baseline ~5893 fast tests UNCHANGED through writing-plans phase (writing-plans is docs-only).
- ZERO new Schwab API calls (harness design preserves L2 LOCK; reinforced via 5 BINDING discriminating tests at §F + §K).
- Schema v21 UNCHANGED through writing-plans phase.

---

## §B Per-sub-bundle file map + dependency graph

### §B.1 File map (NEW + MODIFIED surfaces)

| Sub-bundle | Path | New / Modified | Responsibility |
|------------|------|----------------|----------------|
| T-PC.1.1 | `research/harness/pattern_cohort_evaluator/__init__.py` | NEW | Package marker (empty + version constant `__version__ = "0.1.0"` matching method-record §K.1). |
| T-PC.1.1 | `research/harness/pattern_cohort_evaluator/exceptions.py` | NEW | Typed exceptions: `PatternCohortEvaluatorError`, `CohortInputSchemaError`, `MalformedAsofDateError`, `OhlcvCoverageError` (re-exported), `BothCohortModesSuppliedError`, `NeitherCohortModeSuppliedError`. |
| T-PC.1.1 | `research/harness/pattern_cohort_evaluator/ohlcv_reader.py` | NEW | Re-export of V2 OHLCV evaluator's `read_yfinance_shape_a` + `read_yfinance_shape_a_sliced` + `BothExistDiagnostic` per OQ-3 LOCK. NO duplicate implementation; pure `from ... import ...` statements + `__all__` declaration. |
| T-PC.1.2 | `research/harness/pattern_cohort_evaluator/cohort_reader.py` | NEW | Cohort CSV reader (Mode (b)) + inline tuple-list parser (Mode (a)); `CohortEntry` frozen dataclass; required-column validation with typed `CohortInputSchemaError`; ISO-date parsing with typed `MalformedAsofDateError`; ASCII-only enforcement at parse time. |
| T-PC.2 | `research/harness/pattern_cohort_evaluator/detector_invoker.py` | NEW | Per-(cohort_entry, pattern_class, window) detector orchestration; production detector registry re-import; CandidateWindow generation via `generate_candidate_windows(bars, "zigzag_pivot", ticker=..., timeframe="daily")`; template-match Pass 2 (loads `pattern_exemplars` corpus via `list_exemplars(conn)` + filters to `final_decision IN ('confirmed', 'watch')`); composite_score via `compute_composite_score(geometric=..., template_match=...)`; per-entry try/except per cumulative T2.SB5 lesson with 5 enumerated skip reasons; `current_stage(conn, ticker, asof_date)` surface for stage_observed audit column. |
| T-PC.3 | `research/harness/pattern_cohort_evaluator/output.py` | NEW | 24-column CSV writer; markdown writer (Header + Headline per-pattern-class summary table + per-pattern-class drill-down + Skip-reason summary + Both-exist warning banner + Notes + Manifest); manifest JSON writer per spec §I.3; ASCII-only enforcement (cp1252 round-trip per cumulative Windows stdout safety gotcha); empty-state uniform representation per OQ-12 LOCK. |
| T-PC.4 | `research/harness/pattern_cohort_evaluator/run.py` | NEW | `run_harness(...)` orchestrator + argparse `main()` for direct invocation; output path conventions (`exports/research/pattern-cohort-detection-<ISO>/`); DB URI `mode=ro` connection per V2 OHLCV precedent. |
| T-PC.4 | `swing/cli.py` | MODIFIED (SOLE production write) | NEW `swing diagnose pattern-cohort-detect` subcommand registration per OQ-13 carve-out (35-60 lines; mirror V2 OHLCV's `aplus-sensitivity-v2` at `swing/cli.py:4791-4859`). |
| T-PC.5 | `research/method-records/pattern-cohort-detection.md` | NEW | First method-record version `0.1.0`; status `research`; promotion criteria per spec §K.3; validation notes per spec §K.4; notes section per spec §K.5. |
| T-PC.5 | `research/studies/<harness-ship-date>-pattern-cohort-detection.md` | NEW | First study writeup per spec §L.1 template; methodology + cross-tabulation against backtest output at merge `e0a9edd` + Limitations section template per spec §L.2. |
| T-PC.5 | `research/phase-0-tasks.md` | MODIFIED | "Next" section reflects harness SHIPPED status (second method-record COMPLETED). |
| T-PC.5 | `exports/research/cohorts/tightness_1.005_flips_67.csv` | NEW (operator-supplied) | First-cohort substrate CSV; 67 rows / 15 unique tickers extracted from V2 OHLCV sensitivity drill-down per spec §C.3. |
| T-PC.5 | `exports/research/pattern-cohort-detection-<ISO>/{results.csv,summary.md,manifest.json}` | NEW (operator smoke artifact) | Captured operator smoke run output committed for ledger. |

Test paths (per §H ~55-71 tests; parametrize-consolidated bound ~50-65):

| Test file | Sub-bundle | Test count |
|-----------|------------|------------|
| `tests/research/test_pattern_cohort_evaluator_reader.py` | T-PC.1.1 | ~7 |
| `tests/research/test_pattern_cohort_evaluator_cohort_reader.py` | T-PC.1.2 | ~10 |
| `tests/research/test_pattern_cohort_evaluator_detector_invoker.py` | T-PC.2 | ~18 |
| `tests/research/test_pattern_cohort_evaluator_output.py` | T-PC.3 | ~10 |
| `tests/research/test_pattern_cohort_evaluator_run.py` | T-PC.4 | ~8 |
| `tests/cli/test_diagnose_subcommands.py` (extension) | T-PC.4 | ~3 |
| `tests/research/test_pattern_cohort_evaluator_integration.py` | T-PC.5 | ~5 |

Baseline ~5893 fast tests → ~5954 post-harness-ship at parametrize-consolidated count. ZERO slow-marked tests in harness scope.

### §B.2 Dependency graph (sequential dispatch per spec §M.2)

```
T-PC.1.1 (exceptions + ohlcv_reader re-export + 5 BINDING L2 LOCK tests)
   ↓
T-PC.1.2 (cohort_reader — CohortEntry + Mode (a) inline + Mode (b) CSV parsers)
   ↓
T-PC.2 (detector_invoker — consumes ohlcv_reader + cohort_reader;
        per-(cohort_entry, pattern_class, window) verdict orchestration;
        template-match Pass 2 + composite_score parity with production)
   ↓
T-PC.3 (output — consumes verdict dataclass from detector_invoker)
   ↓
T-PC.4 (run + CLI registration — consumes detector_invoker + output)
   ↓
T-PC.5 (method-record + first study writeup + operator smoke + closer)
```

NO concurrent dispatch per spec §M.2 RECOMMEND. Single-implementer sequential via `superpowers:subagent-driven-development` per project workflow precedent.

---

## §C Module function signatures + class shapes (BINDING)

Per spec §M.3 OQ #1 (refine spec §B.1 + §C.1 + §C.4 + §D.3 proposed shapes to BINDING signatures during writing-plans phase).

### §C.1 `exceptions.py`

```python
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
    Exactly one is required per §C.5.
    """


class NeitherCohortModeSuppliedError(PatternCohortEvaluatorError):
    """Raised when CLI receives NEITHER --cohort-csv NOR --cohort-inline.
    Exactly one is required per §C.5.
    """


__all__ = (
    "OhlcvCoverageError",
    "PatternCohortEvaluatorError",
    "CohortInputSchemaError",
    "MalformedAsofDateError",
    "BothCohortModesSuppliedError",
    "NeitherCohortModeSuppliedError",
)
```

### §C.2 `ohlcv_reader.py` (RE-EXPORT per OQ-3 LOCK)

```python
"""Read-only Shape A parquet wrapper for the pattern cohort harness.

RE-EXPORT of V2 OHLCV evaluator's existing reader per OQ-3 LOCK.

L2 LOCK preservation: this module DELEGATES to
research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader which has its own
5 BINDING discriminating tests at tests/research/test_aplus_v2_ohlcv_reader.py
(file-open mock + import-graph mock + byte-checksum + read_or_fetch_archive
signature lock + V2 module-set source-grep). This harness adds 5 ADDITIONAL
BINDING discriminating tests at tests/research/test_pattern_cohort_evaluator_reader.py
verifying the RE-EXPORT INTEGRITY per spec §E.3 + §F.1.

NEVER opens {ticker}.schwab_api.parquet under any code path.
NO fetch path. NO writes. NO archive mutation.
"""
from __future__ import annotations

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
    read_yfinance_shape_a_sliced,
)

# Identity-preserving re-export: the symbols below are the SAME objects as
# the V2 OHLCV reader's exports (verified via `is` identity in §F.4 test).
__all__ = (
    "BothExistDiagnostic",
    "read_yfinance_shape_a",
    "read_yfinance_shape_a_sliced",
)
```

### §C.3 `cohort_reader.py`

```python
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
    """Parse ISO YYYY-MM-DD string → datetime.date.

    Raises:
      MalformedAsofDateError: per cumulative gotcha #12 — must be typed
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
```

### §C.4 `detector_invoker.py`

```python
"""Per-(cohort_entry, pattern_class, window) detector orchestration.

Re-imports production detector registry via
`swing.pipeline.runner._pattern_detect_registry()` per OQ-1 LOCK + cumulative
gotcha #19 (cascade-call-graph verification): the function is module-level
+ side-effect-free + returns a 5-tuple; safe to import; zero-drift discipline.

Per-entry try/except per cumulative T2.SB5 lesson: 5 enumerated skip reasons
surfaced via per-skip-reason counters + per-entry skip rows (NEVER silent;
this harness IS gotcha #27's architectural answer + models its discipline).
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
)
from research.harness.pattern_cohort_evaluator.cohort_reader import CohortEntry
from research.harness.pattern_cohort_evaluator.exceptions import (
    OhlcvCoverageError,
)
from research.harness.pattern_cohort_evaluator.ohlcv_reader import (
    read_yfinance_shape_a_sliced,
)
from swing.data.repos.pattern_exemplars import list_exemplars
from swing.patterns.composite import compute_composite_score
from swing.patterns.foundation import (
    CandidateWindow,
    current_stage,
    generate_candidate_windows,
)
from swing.patterns.template_matching import (
    GEOMETRIC_SCORE_PREGATE_THRESHOLD,
    TemplateMatchExemplar,
    match_forward,
)

log = logging.getLogger(__name__)

_WindowMode = Literal["last-only", "per-window"]
_TemplateMatchMode = Literal["on", "off"]

# Per spec §I.2 + cumulative gotcha #15 (Expansion #11 taxonomy propagation):
# skip_reason enum values are enumerated explicitly + propagated to
# CohortVerdict.skip_reason + output.py rendering + test fixtures.
_SKIP_REASONS: frozenset[str] = frozenset(
    {
        "coverage_skip",
        "archive_missing_skip",
        "window_generation_error",
        "no_windows",
        "detector_error_all",
    }
)


@dataclass(frozen=True)
class CohortVerdict:
    """One row in the harness output CSV per spec §I.2 (24 columns).

    For non-skip entries: per-(cohort_entry, pattern_class, window) verdict
    populated with detector evidence + template-match + composite_score.

    For skip entries: skip_reason populated; pattern_class + detector verdict
    columns NULL.
    """
    # Cohort-entry identifiers
    cohort_entry_id: int
    cohort_label: str | None
    ticker: str
    asof_date: date

    # Cohort-entry persisted metadata (from V1)
    candidate_id: int | None
    eval_run_id: int | None
    persisted_bucket: str | None
    persisted_pivot: float | None
    persisted_initial_stop: float | None

    # Window identification (None for skip rows)
    window_index: int | None
    window_start_date: date | None
    window_end_date: date | None
    anchor_date: date | None
    anchor_reason: str | None

    # Detector verdict (None for skip rows)
    pattern_class: str | None
    detector_version: str | None
    stage_observed: str | None  # 'stage_2' | 'undefined' | None (skip)

    geometric_score: float | None
    template_match_score: float | None
    composite_score: float | None

    # Audit envelope
    template_match_nearest_exemplar_ids_json: str | None
    criteria_pass_json: str | None
    structural_evidence_json: str | None

    # Skip-bearing audit (None for non-skip rows)
    skip_reason: str | None

    def __post_init__(self) -> None:
        if self.skip_reason is not None and self.skip_reason not in _SKIP_REASONS:
            raise ValueError(
                f"CohortVerdict.skip_reason must be one of "
                f"{sorted(_SKIP_REASONS)}, got {self.skip_reason!r}"
            )


@dataclass(frozen=True)
class CohortRunResult:
    """Top-level harness result emitted to output.py.

    Per cumulative gotcha #22 (Expansion #8 promotion: per-counter accumulation
    audit): each counter unit is per-cohort-entry (NOT per-(entry, pattern_class,
    window)) — the harness skips at the entry level for OHLCV / window failures.
    The detector_error_all counter fires only when ALL detectors raise for a
    given entry; partial detector failures are tallied separately at per-row
    level (skip_reason='detector_error_all' fires only at entry-level total
    detector failure).
    """
    cohort_entries_count: int
    cohort_unique_tickers_count: int
    cohort_unique_asof_dates_count: int
    verdicts: tuple[CohortVerdict, ...]
    entries_processed: int
    verdicts_emitted: int  # non-skip rows
    skipped_entries: dict[str, int]  # per-skip-reason counter; keys ⊂ _SKIP_REASONS
    both_exist_diagnostic: BothExistDiagnostic
    pattern_exemplars_corpus_size_at_invocation: int
    pattern_exemplars_filtered_size: int
    detectors_invoked: tuple[str, ...]
    window_mode: _WindowMode
    template_match_mode: _TemplateMatchMode
    runtime_seconds: float


def get_detector_registry() -> tuple[tuple[object, str, str], ...]:
    """Return the production detector registry per OQ-1 LOCK.

    Re-imports `swing.pipeline.runner._pattern_detect_registry` which is a
    module-level, side-effect-free function returning a 5-tuple of
    (detector_callable, pattern_class, version_str). Verified via
    cascade-call-graph audit per cumulative gotcha #19 — the function body
    invokes 5 detector module imports + returns a 5-tuple verbatim.

    Discriminating test in §F.5 asserts tuple equality with production.
    """
    from swing.pipeline.runner import _pattern_detect_registry
    return _pattern_detect_registry()


def load_exemplar_corpus(
    conn: sqlite3.Connection,
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic,
) -> tuple[dict[str, list[TemplateMatchExemplar]], int, int]:
    """Load pattern_exemplars corpus + slice close-price series per exemplar.

    Mirrors production at swing/pipeline/runner.py:1844-1895 (Pass 2 corpus
    load) except corpus reads from ohlcv_reader.read_yfinance_shape_a_sliced
    instead of OhlcvCache.get_or_fetch.

    Returns: (exemplar_bundles_by_class, corpus_size_at_invocation,
              filtered_corpus_size).

    Per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval
    functions": per-exemplar try/except inside the load loop — one bad
    exemplar does NOT poison the cohort's template-match Pass 2.
    """
    exemplar_rows = list_exemplars(conn)
    corpus_size = len(exemplar_rows)
    bundles_by_class: dict[str, list[TemplateMatchExemplar]] = {}
    valid_decisions = ("confirmed", "watch")
    filtered_count = 0
    for ex_row in exemplar_rows:
        if ex_row.final_decision not in valid_decisions:
            continue
        filtered_count += 1
        try:
            ex_bars = read_yfinance_shape_a_sliced(
                ex_row.ticker,
                cache_dir,
                asof_date=ex_row.end_date,
                min_bars=1,  # exemplar slice may be short; corpus-load
                             # min_bars is exemplar-specific NOT 200
                diagnostic=diagnostic,
            )
            ts_start = pd.Timestamp(ex_row.start_date)
            ts_end = pd.Timestamp(ex_row.end_date)
            mask = (ex_bars.index >= ts_start) & (ex_bars.index <= ts_end)
            close_series = ex_bars.loc[mask, "Close"]
            if hasattr(close_series, "ndim") and close_series.ndim == 2:
                close_series = close_series.iloc[:, 0]
            close_arr = np.asarray(close_series.values, dtype=float)
            if close_arr.size == 0:
                continue
            bundle = TemplateMatchExemplar(
                exemplar=ex_row, close_prices=close_arr
            )
        except Exception as exc:
            log.info(
                "pattern_cohort: exemplar bars fetch failed for "
                "exemplar_id=%s ticker=%s (continuing): %s",
                ex_row.id,
                ex_row.ticker,
                exc,
            )
            continue
        bundles_by_class.setdefault(
            ex_row.proposed_pattern_class, []
        ).append(bundle)
    return bundles_by_class, corpus_size, filtered_count


def invoke_cohort(
    cohort: tuple[CohortEntry, ...],
    *,
    conn: sqlite3.Connection,
    cache_dir: Path,
    window_mode: _WindowMode,
    template_match_mode: _TemplateMatchMode,
    cli_pattern_class_filter: tuple[str, ...] | None = None,
) -> CohortRunResult:
    """Invoke 5 detectors per cohort entry + emit per-row verdicts.

    Args:
      cohort: parsed cohort entries from cohort_reader.
      conn: READ-ONLY sqlite3 connection (URI mode=ro per V2 OHLCV precedent).
      cache_dir: cfg.paths.prices_cache_dir.
      window_mode: 'last-only' (mirror production) or 'per-window' (analytical).
      template_match_mode: 'on' (mirror production Pass 2) or 'off' (skip).
      cli_pattern_class_filter: global filter; per-entry CohortEntry.pattern_class_filter
        takes precedence when set (per OQ-5 LOCK).

    Per-entry try/except per cumulative T2.SB5 gotcha:
      OhlcvCoverageError on read → coverage_skip
      FileNotFoundError on read → archive_missing_skip
      generate_candidate_windows Exception → window_generation_error
      empty windows → no_windows
      ALL 5 detectors raise → detector_error_all (only entries where every
        detector raises; partial detector failures emit individual skip-flag
        flag on the row's structural_evidence_json + log WARNING but still
        contribute non-skip rows for the surviving detectors)
    """
    import time
    started = time.time()
    both_exist = BothExistDiagnostic()

    # Template-match Pass 2 corpus load (once per harness invocation;
    # mirrors production single-load pattern at runner.py:1844-1895)
    if template_match_mode == "on":
        exemplar_bundles_by_class, corpus_size, filtered_size = (
            load_exemplar_corpus(conn, cache_dir, diagnostic=both_exist)
        )
    else:
        exemplar_bundles_by_class = {}
        corpus_size = 0
        filtered_size = 0

    detectors = get_detector_registry()
    detector_names = tuple(p for _, p, _ in detectors)

    skipped: dict[str, int] = {r: 0 for r in _SKIP_REASONS}
    verdicts: list[CohortVerdict] = []
    entries_processed = 0
    verdicts_emitted = 0

    for entry_idx, entry in enumerate(cohort):
        entries_processed += 1

        # Step 1: read OHLCV + slice to <= asof_date
        try:
            sliced = read_yfinance_shape_a_sliced(
                entry.ticker,
                cache_dir,
                asof_date=entry.asof_date,
                min_bars=200,
                diagnostic=both_exist,
            )
        except OhlcvCoverageError:
            skipped["coverage_skip"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "coverage_skip"))
            continue
        except (FileNotFoundError, OSError) as exc:
            log.warning(
                "pattern_cohort: archive missing for %s at %s: %s",
                entry.ticker,
                entry.asof_date,
                exc,
            )
            skipped["archive_missing_skip"] += 1
            verdicts.append(
                _skip_verdict(entry_idx, entry, "archive_missing_skip")
            )
            continue

        # Step 2: generate candidate windows
        try:
            windows = generate_candidate_windows(
                sliced,
                "zigzag_pivot",
                ticker=entry.ticker,
                timeframe="daily",
            )
        except Exception as exc:
            log.warning(
                "pattern_cohort: generate_candidate_windows failed for %s: %s",
                entry.ticker,
                exc,
            )
            skipped["window_generation_error"] += 1
            verdicts.append(
                _skip_verdict(entry_idx, entry, "window_generation_error")
            )
            continue

        if not windows:
            skipped["no_windows"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "no_windows"))
            continue

        # Step 3: select windows per window_mode
        if window_mode == "last-only":
            target_windows: tuple[tuple[int, CandidateWindow], ...] = (
                (len(windows) - 1, windows[-1]),
            )
        else:
            target_windows = tuple(enumerate(windows))

        # Step 4: stage_observed lookup once per entry
        stage_obs = current_stage(conn, entry.ticker, entry.asof_date)

        # Step 5: per-(window, detector) invocation
        entry_verdict_emitted = False
        entry_detector_attempts = 0
        entry_detector_failures = 0
        per_entry_rows: list[CohortVerdict] = []
        for w_idx, window in target_windows:
            for detector_fn, pattern_class, version_str in detectors:
                # Per-entry pattern_class_filter takes precedence over CLI
                # global filter (OQ-5 LOCK)
                if entry.pattern_class_filter is not None:
                    if entry.pattern_class_filter != pattern_class:
                        continue
                elif cli_pattern_class_filter is not None:
                    if pattern_class not in cli_pattern_class_filter:
                        continue
                entry_detector_attempts += 1
                try:
                    evidence = detector_fn(
                        sliced,
                        window,
                        conn=conn,
                        ticker=entry.ticker,
                        asof_date=entry.asof_date,
                    )
                except Exception as exc:
                    entry_detector_failures += 1
                    log.warning(
                        "pattern_cohort: %s detector failed for %s window=%d: %s",
                        pattern_class,
                        entry.ticker,
                        w_idx,
                        exc,
                    )
                    continue

                geometric_score = float(
                    getattr(evidence, "geometric_score", 0.0)
                )

                # Template-match Pass 2 per OQ-6 LOCK
                template_match_score: float | None = None
                nearest_exemplar_ids: list[int] = []
                if template_match_mode == "on":
                    bundles = exemplar_bundles_by_class.get(pattern_class, [])
                    candidate_close = _slice_window_close(sliced, window)
                    if (
                        bundles
                        and candidate_close.size > 0
                        and geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD
                    ):
                        try:
                            hits = match_forward(
                                candidate_close_prices=candidate_close,
                                candidate_pattern_class=pattern_class,
                                candidate_ticker=entry.ticker,
                                exemplar_corpus=bundles,
                                top_k=3,
                                geometric_score=geometric_score,
                            )
                        except Exception as exc:
                            log.warning(
                                "pattern_cohort: match_forward failed for "
                                "(%s, %s): %s",
                                entry.ticker,
                                pattern_class,
                                exc,
                            )
                            hits = []
                        if hits:
                            template_match_score = max(
                                h.similarity_score for h in hits
                            )
                            nearest_exemplar_ids = [
                                h.exemplar_id for h in hits
                            ]

                composite_score = compute_composite_score(
                    geometric=geometric_score,
                    template_match=template_match_score,
                )

                per_entry_rows.append(
                    _build_verdict(
                        entry_idx=entry_idx,
                        entry=entry,
                        window_idx=w_idx,
                        window=window,
                        pattern_class=pattern_class,
                        version_str=version_str,
                        stage_obs=stage_obs,
                        evidence=evidence,
                        geometric_score=geometric_score,
                        template_match_score=template_match_score,
                        composite_score=composite_score,
                        nearest_exemplar_ids=nearest_exemplar_ids,
                    )
                )
                entry_verdict_emitted = True

        # Step 6: per-entry detector_error_all skip check
        # Only fires when EVERY attempted detector raised (no surviving rows)
        if (
            entry_detector_attempts > 0
            and entry_detector_failures == entry_detector_attempts
            and not entry_verdict_emitted
        ):
            skipped["detector_error_all"] += 1
            verdicts.append(_skip_verdict(entry_idx, entry, "detector_error_all"))
            continue

        verdicts.extend(per_entry_rows)
        verdicts_emitted += len(per_entry_rows)

    runtime = time.time() - started
    return CohortRunResult(
        cohort_entries_count=len(cohort),
        cohort_unique_tickers_count=len({e.ticker for e in cohort}),
        cohort_unique_asof_dates_count=len({e.asof_date for e in cohort}),
        verdicts=tuple(verdicts),
        entries_processed=entries_processed,
        verdicts_emitted=verdicts_emitted,
        skipped_entries=skipped,
        both_exist_diagnostic=both_exist,
        pattern_exemplars_corpus_size_at_invocation=corpus_size,
        pattern_exemplars_filtered_size=filtered_size,
        detectors_invoked=detector_names,
        window_mode=window_mode,
        template_match_mode=template_match_mode,
        runtime_seconds=runtime,
    )


def _slice_window_close(
    bars: pd.DataFrame, window: CandidateWindow
) -> np.ndarray:
    """Slice candidate's close-price series; mirrors production at
    swing/pipeline/runner.py:1707-1718.
    """
    ts_start = pd.Timestamp(window.start_date)
    ts_end = pd.Timestamp(window.end_date)
    mask = (bars.index >= ts_start) & (bars.index <= ts_end)
    close_series = bars.loc[mask, "Close"]
    if hasattr(close_series, "ndim") and close_series.ndim == 2:
        close_series = close_series.iloc[:, 0]
    return np.asarray(close_series.values, dtype=float)


def _build_verdict(
    *,
    entry_idx: int,
    entry: CohortEntry,
    window_idx: int,
    window: CandidateWindow,
    pattern_class: str,
    version_str: str,
    stage_obs: str,
    evidence: object,
    geometric_score: float,
    template_match_score: float | None,
    composite_score: float,
    nearest_exemplar_ids: list[int],
) -> CohortVerdict:
    """Build a non-skip CohortVerdict row.

    Per cumulative T3.SB3 lesson "Audit envelope empty-state representation
    must be uniform across emit + persist paths": empty
    nearest_exemplar_ids → JSON null (the string "null"); NOT "[]" and NOT
    "" — per OQ-12 uniform-empty-state LOCK.
    """
    import dataclasses
    import json

    if dataclasses.is_dataclass(evidence):
        ev_dict = dataclasses.asdict(evidence)
    else:
        ev_dict = {"raw_repr": repr(evidence)}

    # Extract criteria_pass flags from evidence dataclass if present
    criteria_pass = ev_dict.get("criteria_pass")
    if criteria_pass is not None:
        criteria_pass_json: str | None = json.dumps(criteria_pass, sort_keys=True)
    else:
        criteria_pass_json = None

    structural_json: str | None = json.dumps(ev_dict, sort_keys=True, default=str)

    nearest_json: str | None
    if nearest_exemplar_ids:
        nearest_json = json.dumps(nearest_exemplar_ids)
    else:
        nearest_json = None  # uniform empty-state (NOT "[]")

    return CohortVerdict(
        cohort_entry_id=entry_idx,
        cohort_label=entry.cohort_label,
        ticker=entry.ticker,
        asof_date=entry.asof_date,
        candidate_id=entry.candidate_id,
        eval_run_id=entry.eval_run_id,
        persisted_bucket=entry.bucket,
        persisted_pivot=entry.pivot,
        persisted_initial_stop=entry.initial_stop,
        window_index=window_idx,
        window_start_date=window.start_date,
        window_end_date=window.end_date,
        anchor_date=window.anchor_date,
        anchor_reason=window.anchor_reason,
        pattern_class=pattern_class,
        detector_version=version_str,
        stage_observed=stage_obs,
        geometric_score=geometric_score,
        template_match_score=template_match_score,
        composite_score=composite_score,
        template_match_nearest_exemplar_ids_json=nearest_json,
        criteria_pass_json=criteria_pass_json,
        structural_evidence_json=structural_json,
        skip_reason=None,
    )


def _skip_verdict(
    entry_idx: int, entry: CohortEntry, skip_reason: str
) -> CohortVerdict:
    """Build a skip-bearing CohortVerdict row per spec §I.2."""
    return CohortVerdict(
        cohort_entry_id=entry_idx,
        cohort_label=entry.cohort_label,
        ticker=entry.ticker,
        asof_date=entry.asof_date,
        candidate_id=entry.candidate_id,
        eval_run_id=entry.eval_run_id,
        persisted_bucket=entry.bucket,
        persisted_pivot=entry.pivot,
        persisted_initial_stop=entry.initial_stop,
        window_index=None,
        window_start_date=None,
        window_end_date=None,
        anchor_date=None,
        anchor_reason=None,
        pattern_class=None,
        detector_version=None,
        stage_observed=None,
        geometric_score=None,
        template_match_score=None,
        composite_score=None,
        template_match_nearest_exemplar_ids_json=None,
        criteria_pass_json=None,
        structural_evidence_json=None,
        skip_reason=skip_reason,
    )
```

### §C.5 `output.py`

```python
"""Pattern cohort harness output formatters: CSV + markdown + manifest JSON.

ASCII-only output per Windows cp1252 stdout safety lesson (cumulative
CLAUDE.md gotcha). All emitted text — CSV cells AND markdown body AND
JSON values — must be cp1252-encodable. Tests verify via text.encode("cp1252").

Empty-state representation per OQ-12 LOCK + cumulative T3.SB3 lesson:
'(none)' literal in markdown drill-down; 'null' (the JSON null literal)
in CSV cells via empty string emit; None in JSON-serialized fields.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from research.harness.pattern_cohort_evaluator.detector_invoker import (
    CohortRunResult,
    CohortVerdict,
)

_CSV_HEADERS = (
    "cohort_entry_id",
    "cohort_label",
    "ticker",
    "asof_date",
    "candidate_id",
    "eval_run_id",
    "persisted_bucket",
    "persisted_pivot",
    "persisted_initial_stop",
    "window_index",
    "window_start_date",
    "window_end_date",
    "anchor_date",
    "anchor_reason",
    "pattern_class",
    "detector_version",
    "stage_observed",
    "geometric_score",
    "template_match_score",
    "composite_score",
    "template_match_nearest_exemplar_ids_json",
    "criteria_pass_json",
    "structural_evidence_json",
    "skip_reason",
)

assert len(_CSV_HEADERS) == 24, "CSV header column count drift; spec §I.2 LOCK"


def write_results_csv(result: CohortRunResult, path: Path) -> None:
    """Write 24-column CSV per spec §I.2.

    Empty fields emit empty string (CSV null convention) per OQ-12 LOCK.
    """
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADERS)
        for v in result.verdicts:
            writer.writerow(_verdict_to_row(v))


def _verdict_to_row(v: CohortVerdict) -> tuple[str, ...]:
    """Render a CohortVerdict to a 24-tuple of strings. Empty -> ''.

    Per cumulative gotcha "Windows PowerShell stdout defaults to cp1252":
    NO non-ASCII glyphs. Floats formatted with explicit fixed precision
    (4 decimals for scores) to keep test fixtures deterministic.
    """

    def _s(x: object) -> str:
        if x is None:
            return ""
        return str(x)

    def _f(x: float | None) -> str:
        if x is None:
            return ""
        return f"{x:.6f}"

    return (
        _s(v.cohort_entry_id),
        _s(v.cohort_label),
        _s(v.ticker),
        v.asof_date.isoformat() if v.asof_date else "",
        _s(v.candidate_id),
        _s(v.eval_run_id),
        _s(v.persisted_bucket),
        _f(v.persisted_pivot),
        _f(v.persisted_initial_stop),
        _s(v.window_index),
        v.window_start_date.isoformat() if v.window_start_date else "",
        v.window_end_date.isoformat() if v.window_end_date else "",
        v.anchor_date.isoformat() if v.anchor_date else "",
        _s(v.anchor_reason),
        _s(v.pattern_class),
        _s(v.detector_version),
        _s(v.stage_observed),
        _f(v.geometric_score),
        _f(v.template_match_score),
        _f(v.composite_score),
        _s(v.template_match_nearest_exemplar_ids_json),
        _s(v.criteria_pass_json),
        _s(v.structural_evidence_json),
        _s(v.skip_reason),
    )


def write_summary_markdown(
    result: CohortRunResult,
    path: Path,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    harness_version: str,
) -> None:
    """Write analyst-readable markdown summary per spec §I.4.

    Sections (in order):
      1. Header (generated time + cohort mode + size + harness version + L2 LOCK)
      2. Headline (per-pattern-class summary table; composite thresholds)
      3. Per-pattern-class drill-down (one subsection per pattern_class)
      4. Skip-reason summary
      5. Both-exist warning banner (conditional)
      6. Notes (corpus drift + archive temporal mutation caveats)
      7. Manifest summary
    """
    lines: list[str] = []
    lines.append(_render_header(
        result,
        cohort_input_mode=cohort_input_mode,
        cohort_input_path=cohort_input_path,
        harness_version=harness_version,
    ))
    lines.append(_render_headline(result))
    lines.append(_render_per_class_drilldown(result))
    lines.append(_render_skip_summary(result))
    if result.both_exist_diagnostic.count > 0:
        lines.append(_render_both_exist_banner(result))
    lines.append(_render_notes())
    lines.append(_render_manifest_summary(result))
    body = "\n\n".join(lines) + "\n"
    # Sanity check: body MUST be cp1252-encodable per Windows stdout safety
    body.encode("cp1252")  # raises UnicodeEncodeError on drift
    path.write_text(body, encoding="utf-8")


def write_manifest_json(
    result: CohortRunResult,
    path: Path,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    cache_dir: Path,
    db_path: Path,
    harness_version: str,
) -> None:
    """Write manifest JSON per spec §I.3 schema.

    Includes (per spec §I.3): harness_version + cohort_input metadata +
    cohort SHA-256 + corpus sizes + detectors_invoked + window_mode +
    template_match_mode + runtime + counters + both_exist_diagnostic
    (count + first-50 affected_tickers) + l2_lock_preserved=true.
    """
    import inspect
    from research.harness.pattern_cohort_evaluator import ohlcv_reader as _reader

    if cohort_input_path is not None and cohort_input_path.exists():
        cohort_bytes = cohort_input_path.read_bytes()
        cohort_sha = hashlib.sha256(cohort_bytes).hexdigest()
        cohort_path_str: str | None = str(cohort_input_path.resolve())
    else:
        cohort_sha = None
        cohort_path_str = None

    # ohlcv_reader signature hash for provenance (Codex R3 V2 OHLCV precedent)
    sig = inspect.signature(_reader.read_yfinance_shape_a)
    sig_str = f"{sig.return_annotation}|{','.join(sig.parameters.keys())}"
    sig_hash = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

    manifest = {
        "harness_version": harness_version,
        "cohort_input_mode": cohort_input_mode,
        "cohort_input_path": cohort_path_str,
        "cohort_input_sha256": cohort_sha,
        "cohort_entries_count": result.cohort_entries_count,
        "cohort_unique_tickers_count": result.cohort_unique_tickers_count,
        "cohort_unique_asof_dates_count": result.cohort_unique_asof_dates_count,
        "db_path": str(db_path.resolve()),
        "cache_dir": str(cache_dir.resolve()),
        "ohlcv_reader_module": (
            "research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader"
        ),
        "ohlcv_reader_signature_hash": sig_hash,
        "pattern_exemplars_corpus_size_at_invocation": (
            result.pattern_exemplars_corpus_size_at_invocation
        ),
        "pattern_exemplars_corpus_filter": (
            "final_decision IN ('confirmed','watch')"
        ),
        "pattern_exemplars_filtered_size": result.pattern_exemplars_filtered_size,
        "detectors_invoked": list(result.detectors_invoked),
        "window_mode": result.window_mode,
        "template_match_mode": result.template_match_mode,
        "started_at_utc": datetime.now(UTC).isoformat(),  # set by run.py if needed
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "runtime_seconds": result.runtime_seconds,
        "entries_processed": result.entries_processed,
        "verdicts_emitted": result.verdicts_emitted,
        "skipped_entries": dict(result.skipped_entries),
        "both_exist_diagnostic": {
            "count": result.both_exist_diagnostic.count,
            "affected_tickers": list(
                result.both_exist_diagnostic.affected_tickers
            ),
        },
        "l2_lock_preserved": True,
    }
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_header(
    result: CohortRunResult,
    *,
    cohort_input_mode: str,
    cohort_input_path: Path | None,
    harness_version: str,
) -> str:
    """Header section per spec §I.4 step 1."""
    iso = datetime.now(UTC).isoformat()
    path_repr = str(cohort_input_path) if cohort_input_path else "(inline)"
    return (
        f"# Pattern Cohort Detector Evaluator Summary\n\n"
        f"- generated_at_utc: {iso}\n"
        f"- harness_version: {harness_version}\n"
        f"- cohort_input_mode: {cohort_input_mode}\n"
        f"- cohort_input_path: {path_repr}\n"
        f"- cohort_entries_count: {result.cohort_entries_count}\n"
        f"- cohort_unique_tickers_count: {result.cohort_unique_tickers_count}\n"
        f"- cohort_unique_asof_dates_count: "
        f"{result.cohort_unique_asof_dates_count}\n"
        f"- window_mode: {result.window_mode}\n"
        f"- template_match_mode: {result.template_match_mode}\n"
        f"- runtime_seconds: {result.runtime_seconds:.2f}\n"
        f"- l2_lock_preserved: true"
    )


def _render_headline(result: CohortRunResult) -> str:
    """Headline per-pattern-class summary table per spec §I.4 step 2."""
    rows: list[str] = []
    rows.append("## Headline: per-pattern-class summary")
    rows.append("")
    rows.append(
        "| pattern_class | entries_evaluated | composite>=0.5 | "
        "composite>=0.7 | composite>=0.9 | max_composite |"
    )
    rows.append("|---|---|---|---|---|---|")
    by_class = _group_by_class(result.verdicts)
    if not by_class:
        rows.append("| (none) | 0 | 0 | 0 | 0 | (none) |")
        return "\n".join(rows)
    for cls in sorted(by_class.keys()):
        entries = by_class[cls]
        scores = [
            v.composite_score for v in entries
            if v.composite_score is not None
        ]
        cnt = len(entries)
        ge05 = sum(1 for s in scores if s >= 0.5)
        ge07 = sum(1 for s in scores if s >= 0.7)
        ge09 = sum(1 for s in scores if s >= 0.9)
        mx = f"{max(scores):.4f}" if scores else "(none)"
        rows.append(f"| {cls} | {cnt} | {ge05} | {ge07} | {ge09} | {mx} |")
    return "\n".join(rows)


def _render_per_class_drilldown(result: CohortRunResult) -> str:
    """Per-pattern-class drill-down per spec §I.4 step 3."""
    rows: list[str] = []
    rows.append("## Per-pattern-class drill-down")
    by_class = _group_by_class(result.verdicts)
    if not by_class:
        rows.append("")
        rows.append("(none) -- no non-skip verdicts emitted")
        return "\n".join(rows)
    for cls in sorted(by_class.keys()):
        rows.append("")
        rows.append(f"### {cls}")
        rows.append("")
        rows.append(
            "| cohort_entry_id | ticker | asof_date | window_index | "
            "stage_observed | geometric_score | template_match_score | "
            "composite_score |"
        )
        rows.append("|---|---|---|---|---|---|---|---|")
        # cap at first 50 per spec §I.4 step 3 "top-N if cohort large"
        ranked = sorted(
            by_class[cls],
            key=lambda v: -(v.composite_score or 0.0),
        )[:50]
        for v in ranked:
            tm = (
                f"{v.template_match_score:.4f}"
                if v.template_match_score is not None else "(none)"
            )
            rows.append(
                f"| {v.cohort_entry_id} | {v.ticker} | "
                f"{v.asof_date.isoformat()} | {v.window_index} | "
                f"{v.stage_observed or '(none)'} | "
                f"{(v.geometric_score or 0.0):.4f} | {tm} | "
                f"{(v.composite_score or 0.0):.4f} |"
            )
    return "\n".join(rows)


def _render_skip_summary(result: CohortRunResult) -> str:
    """Skip-reason summary table per spec §I.4 step 4."""
    rows: list[str] = []
    rows.append("## Skip-reason summary")
    rows.append("")
    rows.append("| skip_reason | count |")
    rows.append("|---|---|")
    for r in sorted(result.skipped_entries.keys()):
        rows.append(f"| {r} | {result.skipped_entries[r]} |")
    return "\n".join(rows)


def _render_both_exist_banner(result: CohortRunResult) -> str:
    """Both-exist warning banner per spec §I.4 step 5 (conditional)."""
    rows: list[str] = []
    rows.append("## Both-exist diagnostic (Shape A wins per OQ-18 V2 LOCK)")
    rows.append("")
    rows.append(
        f"- count: {result.both_exist_diagnostic.count}"
    )
    rows.append("- affected_tickers (capped at 50):")
    for t in result.both_exist_diagnostic.affected_tickers[:50]:
        rows.append(f"  - {t}")
    return "\n".join(rows)


def _render_notes() -> str:
    """Notes section per spec §I.4 step 6 + §L.2 limitation templates."""
    return (
        "## Notes\n\n"
        "- pattern_exemplars corpus is read at harness invocation time; "
        "corpus drift between cohort-input-time and invocation-time may "
        "shift template-match Pass 2 verdicts. See method-record "
        "L1 limitation.\n"
        "- OHLCV archive bar-content TEMPORAL mutation per cumulative "
        "gotcha #26 family: intervening pipeline runs may overwrite "
        "historical bars between cohort-input-time and harness-invocation-"
        "time. See method-record L2 limitation.\n"
        "- current_stage lookup uses CURRENT operator DB state; if eval_runs "
        "have been pruned between cohort-input-time and harness-invocation-"
        "time, stage_observed may shift. See method-record L3 limitation."
    )


def _render_manifest_summary(result: CohortRunResult) -> str:
    """Manifest summary footer per spec §I.4 step 7."""
    return (
        "## Manifest summary\n\n"
        f"- entries_processed: {result.entries_processed}\n"
        f"- verdicts_emitted: {result.verdicts_emitted}\n"
        f"- detectors_invoked: "
        f"{', '.join(result.detectors_invoked)}\n"
        f"- pattern_exemplars_corpus_size_at_invocation: "
        f"{result.pattern_exemplars_corpus_size_at_invocation}\n"
        f"- pattern_exemplars_filtered_size: "
        f"{result.pattern_exemplars_filtered_size}\n"
        f"- runtime_seconds: {result.runtime_seconds:.2f}\n"
        f"- both_exist_diagnostic.count: "
        f"{result.both_exist_diagnostic.count}"
    )


def _group_by_class(
    verdicts: tuple[CohortVerdict, ...],
) -> dict[str, list[CohortVerdict]]:
    """Group non-skip verdicts by pattern_class. Skip rows excluded."""
    out: dict[str, list[CohortVerdict]] = {}
    for v in verdicts:
        if v.skip_reason is not None or v.pattern_class is None:
            continue
        out.setdefault(v.pattern_class, []).append(v)
    return out
```

### §C.6 `run.py`

```python
"""Pattern cohort detector evaluator harness CLI entry point.

Invoke via `python -m research.harness.pattern_cohort_evaluator.run
--cohort-csv PATH --db PATH --output-dir DIR` OR via
`swing diagnose pattern-cohort-detect` which delegates here.

L2 LOCK preserved: NO imports of forbidden modules (yfinance, schwabdev,
swing.integrations.schwab, swing.data.ohlcv_archive). DB opened via URI
mode=ro per V2 OHLCV Codex R2.M2 RESOLVED.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.harness.pattern_cohort_evaluator import __version__
from research.harness.pattern_cohort_evaluator.cohort_reader import (
    CohortEntry,
    parse_inline_cohort,
    read_cohort_csv,
)
from research.harness.pattern_cohort_evaluator.detector_invoker import (
    CohortRunResult,
    invoke_cohort,
)
from research.harness.pattern_cohort_evaluator.exceptions import (
    BothCohortModesSuppliedError,
    NeitherCohortModeSuppliedError,
)
from research.harness.pattern_cohort_evaluator.output import (
    write_manifest_json,
    write_results_csv,
    write_summary_markdown,
)
from swing.config import Config


def _get_cfg() -> Config:
    """Load production cfg via Config.from_defaults().

    Isolated to a module-level helper so tests can monkeypatch it without
    importing run.py's internals directly. Mirrors V2 OHLCV evaluator
    precedent at research/harness/aplus_v2_ohlcv_evaluator/run.py:28-34.
    """
    return Config.from_defaults()


def _resolve_cohort(
    cohort_csv: Path | None,
    cohort_inline: str | None,
) -> tuple[tuple[CohortEntry, ...], str, Path | None]:
    """Resolve cohort entries from Mode (a) or Mode (b) inputs.

    Returns: (entries, cohort_input_mode, cohort_input_path).

    Raises:
      BothCohortModesSuppliedError: both flags supplied.
      NeitherCohortModeSuppliedError: neither flag supplied.
    """
    if cohort_csv is not None and cohort_inline is not None:
        raise BothCohortModesSuppliedError(
            "Exactly one of --cohort-csv or --cohort-inline required; "
            "both supplied"
        )
    if cohort_csv is None and cohort_inline is None:
        raise NeitherCohortModeSuppliedError(
            "Exactly one of --cohort-csv or --cohort-inline required; "
            "neither supplied"
        )
    if cohort_csv is not None:
        return read_cohort_csv(cohort_csv), "csv", cohort_csv
    return parse_inline_cohort(cohort_inline), "inline", None  # type: ignore[arg-type]


def run_harness(
    *,
    cohort_csv: Path | None,
    cohort_inline: str | None,
    db_path: Path,
    output_dir: Path,
    window_mode: str = "per-window",
    template_match_mode: str = "on",
    cli_pattern_class_filter: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path]:
    """Run the cohort harness + emit results CSV + summary markdown +
    manifest JSON into a fresh timestamped subdirectory under output_dir.

    Returns: (results_csv_path, summary_md_path, manifest_json_path).

    Validates:
      Exactly one cohort mode supplied.
      window_mode ∈ {'last-only', 'per-window'} -> ValueError.
      template_match_mode ∈ {'on', 'off'} -> ValueError.
      cli_pattern_class_filter: each value in known pattern_class set
        -> ValueError on unknown names with names enumerated.

    DB connection: opens via URI mode=ro per V2 OHLCV Codex R2.M2 precedent;
    path-escape safe via db_path.resolve().as_uri() per Codex R3.m2.
    """
    if window_mode not in ("last-only", "per-window"):
        raise ValueError(
            f"window_mode must be 'last-only' or 'per-window'; got {window_mode!r}"
        )
    if template_match_mode not in ("on", "off"):
        raise ValueError(
            f"template_match_mode must be 'on' or 'off'; got "
            f"{template_match_mode!r}"
        )
    if cli_pattern_class_filter is not None:
        from research.harness.pattern_cohort_evaluator.cohort_reader import (
            _ALLOWED_PATTERN_CLASSES,
        )
        unknown = [
            n for n in cli_pattern_class_filter
            if n not in _ALLOWED_PATTERN_CLASSES
        ]
        if unknown:
            raise ValueError(
                f"cli_pattern_class_filter contains unknown pattern_class names: "
                f"{unknown}; allowed: {sorted(_ALLOWED_PATTERN_CLASSES)}"
            )

    cohort, mode, cohort_path = _resolve_cohort(cohort_csv, cohort_inline)

    cfg = _get_cfg()
    cache_dir = cfg.paths.prices_cache_dir

    db_uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    try:
        result = invoke_cohort(
            cohort,
            conn=conn,
            cache_dir=cache_dir,
            window_mode=window_mode,  # type: ignore[arg-type]
            template_match_mode=template_match_mode,  # type: ignore[arg-type]
            cli_pattern_class_filter=cli_pattern_class_filter,
        )
    finally:
        conn.close()

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"pattern-cohort-detection-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)
    results_csv_path = run_dir / "results.csv"
    summary_md_path = run_dir / "summary.md"
    manifest_json_path = run_dir / "manifest.json"

    write_results_csv(result, results_csv_path)
    write_summary_markdown(
        result,
        summary_md_path,
        cohort_input_mode=mode,
        cohort_input_path=cohort_path,
        harness_version=__version__,
    )
    write_manifest_json(
        result,
        manifest_json_path,
        cohort_input_mode=mode,
        cohort_input_path=cohort_path,
        cache_dir=cache_dir,
        db_path=db_path,
        harness_version=__version__,
    )
    return results_csv_path, summary_md_path, manifest_json_path


def main(argv: list[str] | None = None) -> int:
    """argparse main for direct `python -m` invocation."""
    parser = argparse.ArgumentParser(
        description="Pattern cohort detector evaluator harness."
    )
    cohort_group = parser.add_mutually_exclusive_group(required=False)
    cohort_group.add_argument(
        "--cohort-csv", type=Path, default=None, dest="cohort_csv",
    )
    cohort_group.add_argument(
        "--cohort-inline", type=str, default=None, dest="cohort_inline",
    )
    parser.add_argument("--db", required=True, type=Path, dest="db_path")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("exports/research"),
    )
    parser.add_argument(
        "--window-mode", choices=("last-only", "per-window"),
        default="per-window",
    )
    parser.add_argument(
        "--template-match", choices=("on", "off"), default="on",
        dest="template_match_mode",
    )
    parser.add_argument(
        "--pattern-class-filter", type=str, default=None,
        help="Comma-separated pattern_class filter.",
    )
    args = parser.parse_args(argv)

    filter_tuple: tuple[str, ...] | None = None
    if args.pattern_class_filter:
        filter_tuple = tuple(
            s.strip() for s in args.pattern_class_filter.split(",") if s.strip()
        )

    try:
        results_path, md_path, manifest_path = run_harness(
            cohort_csv=args.cohort_csv,
            cohort_inline=args.cohort_inline,
            db_path=args.db_path,
            output_dir=args.output_dir,
            window_mode=args.window_mode,
            template_match_mode=args.template_match_mode,
            cli_pattern_class_filter=filter_tuple,
        )
    except (
        ValueError,
        BothCohortModesSuppliedError,
        NeitherCohortModeSuppliedError,
    ) as exc:
        parser.error(str(exc))
        return 1  # unreachable; parser.error raises SystemExit

    print(f"Results CSV: {results_path}")
    print(f"Summary MD:  {md_path}")
    print(f"Manifest:    {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---


## §D SQL skeleton verification (Expansion #4 refinement)

Per cumulative gotcha #18 — for every SQL skeleton, enumerate (a) consumer's row-set scope; (b) JOIN-cardinality; (c) downstream sufficiency; (d) post-mutation re-check semantics. Per cumulative gotcha #20 (Expansion #4 sub-refinement: runtime-binding-shape + empty-result-set audit) — enumerate runtime binding shape per parameter + empty-input handling.

### §D.1 Mode (c) SQL is V2.5+ DEFERRED (NOT this dispatch)

Per OQ-2 LOCK + spec §A.5: V1 ships Mode (a) inline + Mode (b) CSV cohort input only; Mode (c) SQL query against operator DB is V2.5+ candidate. THIS dispatch produces NO parameterized SQL inside the harness module set.

### §D.2 Production helper SQL consumed transitively

The harness consumes production SQL transitively via `current_stage(conn, ticker, asof_date)` per `swing/patterns/foundation.py:745-790` (queries `candidates` JOIN `evaluation_runs` + `candidate_criteria`) and `list_exemplars(conn)` per `swing/data/repos/pattern_exemplars.py:134-180` (queries `pattern_exemplars` with optional pattern_class / label_source filters; defaults to all). Both production functions have their own test surface; harness does NOT re-author their SQL.

**(a) Row-set scope (consumer side):**
- `current_stage`: per-(ticker, asof_date) → single int (TT-pass count) → string label.
- `list_exemplars(conn)` (no filter args): all rows → list[PatternExemplar].

**(b) JOIN-cardinality (production):**
- `current_stage` JOIN of `candidates` ⨝ `evaluation_runs`: 1:1 (each candidate has exactly 1 evaluation_run per `0001_phase1_initial.sql:26` `evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id)`).
- `list_exemplars` no JOINs.

**(c) Downstream sufficiency:**
- `current_stage`'s 'stage_2' return populates `CohortVerdict.stage_observed` for operator audit (per spec §C.4 step 5 + §I.2 column #17). When `current_stage` returns `'undefined'`, detectors' criterion #1 (Stage-2-gate) fails internally → zero-evidence verdict; harness STILL emits the row with `stage_observed='undefined'` for visibility (NOT a skip).
- `list_exemplars` result filtered to `final_decision IN ('confirmed', 'watch')` per production runner.py:1860 — harness mirrors verbatim at `load_exemplar_corpus`.

**(d) Post-mutation re-check:** harness is READ-ONLY; no mutations. N/A.

### §D.3 Empty-input handling (cumulative gotcha #20)

Per cumulative gotcha #20 Expansion #4 sub-refinement: empty-input cases enumerated:

- Empty cohort input → harness emits CSV header-only + markdown headline `(none)` + manifest `entries_processed=0` + ALL skip counters zero (per spec §E.4 + OQ-12 LOCK uniform empty-state).
- Empty `pattern_exemplars` corpus (or all rows filter out) → `exemplar_bundles_by_class = {}`; template-match Pass 2 returns `template_match_score = None` for every verdict; `compute_composite_score(geometric=g, template_match=None)` falls through to `min(1.0, geometric)` per L5 LOCK precedent at `swing/patterns/composite.py:55`.
- Empty `current_stage` lookup result → returns `'undefined'`; detector criterion #1 fails internally; verdict emitted with `stage_observed='undefined'` + zero-evidence.

Discriminating tests for each empty case at §F.2 + §H.

---

## §E Production function signature verification (Expansion #2 refinement BINDING)

Per cumulative gotcha #17 — grep every production-function reference in the plan + verify (a) signature; (b) side-effect contract; (c) error semantics; (d) L2 LOCK preservation. Per cumulative gotcha #19 (Expansion #2 sub-refinement: cascade-call-graph verification) — verify CASCADE behavior (whether documented sibling helpers are invoked from the production function body).

### §E.1 `swing.pipeline.runner._pattern_detect_registry`

Verified at `swing/pipeline/runner.py:1272-1303`:

```python
def _pattern_detect_registry():
    """Return [(detector_callable, pattern_class, version_str), ...]."""
    from swing.patterns.cup_with_handle import DETECTOR_VERSION as CUP_VERSION
    from swing.patterns.cup_with_handle import detect_cup_with_handle
    from swing.patterns.double_bottom_w import DETECTOR_VERSION as DBW_VERSION
    from swing.patterns.double_bottom_w import detect_double_bottom_w
    from swing.patterns.flat_base import DETECTOR_VERSION as FLAT_VERSION
    from swing.patterns.flat_base import detect_flat_base
    from swing.patterns.high_tight_flag import DETECTOR_VERSION as HTF_VERSION
    from swing.patterns.high_tight_flag import detect_high_tight_flag
    from swing.patterns.vcp import DETECTOR_VERSION as VCP_VERSION
    from swing.patterns.vcp import detect_vcp

    return (
        (detect_vcp, "vcp", VCP_VERSION),
        (detect_flat_base, "flat_base", FLAT_VERSION),
        (detect_cup_with_handle, "cup_with_handle", CUP_VERSION),
        (detect_high_tight_flag, "high_tight_flag", HTF_VERSION),
        (detect_double_bottom_w, "double_bottom_w", DBW_VERSION),
    )
```

- (a) Signature: `() -> tuple[tuple[Callable, str, str], ...]`. NO arguments.
- (b) Side-effect contract: PURE. 5 lazy module imports (cheap when re-invoked since Python caches in `sys.modules`). No DB writes, no I/O, no fetch. Returns a 5-tuple.
- (c) Error semantics: Raises `ImportError` if any detector module is broken (unlikely; defensive). Harness propagates.
- (d) L2 LOCK: SAFE. The 5 detector modules (`swing/patterns/{vcp,flat_base,cup_with_handle,high_tight_flag,double_bottom_w}.py`) do NOT import yfinance / schwabdev / swing.integrations.schwab / swing.data.ohlcv_archive at module level (verified via grep at plan-write time). Cascade-call-graph audit per gotcha #19 BINDING: no transitive forbidden imports.
- **Cascade-call-graph verification (gotcha #19)**: the function body invokes 5 detector module imports + returns a 5-tuple verbatim. NO sibling helper invocation. Re-import contract preserved zero-drift.

Discriminating test in §F.5 (`test_harness_detector_registry_matches_production`): asserts `get_detector_registry() == _pattern_detect_registry()` tuple equality. Defensive signature lock at §F.5 (`test_pattern_detect_registry_signature_unchanged`): asserts `inspect.signature(_pattern_detect_registry).parameters == {}`.

### §E.2 `swing.patterns.foundation.generate_candidate_windows`

Verified at `swing/patterns/foundation.py:426-434`:

```python
def generate_candidate_windows(
    bars: pd.DataFrame,
    anchor_search_method: Literal[
        "zigzag_pivot", "ma_crossover", "high_low_breakout"
    ],
    *,
    ticker: str,
    timeframe: Literal["daily", "weekly"] = "daily",
) -> list[CandidateWindow]:
```

- (a) Signature: 2 positional (bars + anchor_search_method) + 2 keyword-only (ticker + timeframe). Per OQ-4 LOCK the harness invokes ONLY with `"zigzag_pivot"`.
- (b) Side-effect contract: PURE. No DB, no I/O. Returns a list of `CandidateWindow` frozen dataclasses (may be empty).
- (c) Error semantics: May raise on bars sanitizer failures (`swing/patterns/_sanitize.py`). Harness wraps in try/except → `window_generation_error` skip per §C.4 step 2.
- (d) L2 LOCK: SAFE. PURE function.
- **Cascade-call-graph (gotcha #19)**: zigzag_pivot mode invokes `extract_zigzag_swings(bars, initial_threshold_pct=3.0)` per spec section 5.1.3 LOCK; the swing extractor is pure pandas/numpy. NO forbidden cascade.

Discriminating test at §F.5: `test_generate_candidate_windows_signature_unchanged_via_inspect_signature`.

### §E.3 `swing.patterns.foundation.current_stage`

Verified at `swing/patterns/foundation.py:745-790`:

```python
def current_stage(
    conn: sqlite3.Connection,
    ticker: str,
    asof_date: date,
) -> _StageLabel:  # Literal["stage_1","stage_2","stage_3","stage_4","undefined"]
```

- (a) Signature: 3 positional. `asof_date` is `datetime.date` (NOT str). Per cumulative gotcha #12 BINDING: caller converts TEXT data_asof_date via `date.fromisoformat()` BEFORE invoking (cohort_reader does this in `parse_asof_date`).
- (b) Side-effect contract: PURE READ. 2 SELECTs (candidate lookup + TT pass count). NO writes.
- (c) Error semantics: Returns `'undefined'` for missing candidate row. Returns `'stage_2'` for TT-pass-count == 8. Returns `'undefined'` for any other count.
- (d) L2 LOCK: SAFE. Uses sqlite3 SELECTs only.
- **Cascade-call-graph (gotcha #19)**: function body executes 2 SQL queries directly; NO sibling helper invocation; no transitive imports. Safe to invoke from harness.

Discriminating test at §F.5: `test_current_stage_signature_unchanged_via_inspect_signature`.

### §E.4 `swing.patterns.composite.compute_composite_score`

Verified at `swing/patterns/composite.py:40-110`:

```python
def compute_composite_score(
    *,
    geometric: float,
    template_match: float | None,
) -> float:
```

- (a) Signature: 2 keyword-only args. RETURNS clamped float in [0.0, 1.0].
- (b) Side-effect contract: PURE math. No I/O.
- (c) Error semantics: `ValueError` on non-finite inputs OR geometric < 0 OR template_match outside [0.0, 1.0].
- (d) L2 LOCK: SAFE.
- **Cascade-call-graph (gotcha #19)**: pure arithmetic; no sibling invocation.

Discriminating test at §F.5: `test_compute_composite_score_signature_unchanged_via_inspect_signature`.

### §E.5 `swing.patterns.template_matching.match_forward`

Verified at `swing/patterns/template_matching.py:319-327`:

```python
def match_forward(
    *,
    candidate_close_prices: np.ndarray,
    candidate_pattern_class: str,
    candidate_ticker: str,
    exemplar_corpus: Sequence[TemplateMatchExemplar],
    top_k: int = 3,
    geometric_score: float | None = None,
) -> list[TemplateMatchHit]:
```

- (a) Signature: 4 required + 2 optional keyword-only. ALL keyword-only per `*` marker.
- (b) Side-effect contract: PURE. No DB I/O. Caller pre-fetches close-price arrays per spec section 5.7 BINDING.
- (c) Error semantics: `ValueError` on unknown pattern_class OR top_k < 1. Empty list when corpus empty OR pre-gate fails OR no exemplars match. Per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval functions": match_forward has internal per-exemplar try/except (already RESOLVED at `swing/patterns/template_matching.py`).
- (d) L2 LOCK: SAFE.
- **Cascade-call-graph (gotcha #19)**: invokes `_min_max_normalize` + `subsample_exemplar_corpus` siblings — both pure numpy/dict helpers. NO forbidden cascade.

Discriminating test at §F.5: `test_match_forward_signature_unchanged_via_inspect_signature`. Defensive test asserts harness's invocation kwargs match production exactly (`candidate_close_prices`, `candidate_pattern_class`, `candidate_ticker`, `exemplar_corpus`, `top_k`, `geometric_score`) per cumulative gotcha "Sub-bundle B `34be84e` defect family — schwabdev camelCase kwarg discipline" generalized to ANY kwarg-bound production callsite.

### §E.6 `swing.data.repos.pattern_exemplars.list_exemplars`

Verified at `swing/data/repos/pattern_exemplars.py:134-180`:

```python
def list_exemplars(
    conn: sqlite3.Connection,
    *,
    pattern_class: str | None = None,
    label_source: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[PatternExemplar]:
```

- (a) Signature: 1 positional (conn) + 4 keyword-only (all optional). Harness invokes with NO filters (`list_exemplars(conn)`) to get full corpus.
- (b) Side-effect contract: PURE READ. Single SELECT. No writes.
- (c) Error semantics: Propagates `sqlite3.OperationalError` if `pattern_exemplars` table absent (migration v20+ guarantees existence; pre-v20 DB fails-fast).
- (d) L2 LOCK: SAFE. SQLite SELECT only.
- **Cascade-call-graph (gotcha #19)**: invokes `_row_to_exemplar` mapper helper; pure dataclass construction.

Discriminating test at §F.5: `test_list_exemplars_signature_unchanged_via_inspect_signature`.

### §E.7 `swing.data.ohlcv_archive.read_or_fetch_archive` — NEGATIVE verification (harness does NOT call)

Per spec §A.1 + brief §3.4 + cumulative gotcha #17: the harness does NOT import `read_or_fetch_archive`. The V2 OHLCV evaluator's `ohlcv_reader.py` (re-exported here per OQ-3 LOCK) bypasses `read_or_fetch_archive` because:

- `read_or_fetch_archive` ACTIVELY FETCHES yfinance on cache-miss (verified at `swing/data/ohlcv_archive.py:172-251`).
- `read_or_fetch_archive` does NOT have a `prefer_source` kwarg (also verified at the same lines).
- Harness must be reproducible per-invocation (no implicit fetch).

Discriminating tests at §F (inherited from V2 OHLCV evaluator's L2 LOCK suite):
- `test_pattern_cohort_module_set_does_NOT_import_swing_data_ohlcv_archive` — grep harness source files for forbidden import substrings.

### §E.8 `swing.config.Config.from_defaults`

Verified per V2 OHLCV evaluator plan §E.7 + `swing/config.py`:

- (a) Signature: classmethod; no args.
- (b) Side-effect contract: reads tracked-repo `swing.config.toml` ONLY. Does NOT cascade through user-config.toml (Codex R3.M2 RESOLVED at V2 OHLCV plan). Per cumulative gotcha #19 (cascade-call-graph) — verified at V2 OHLCV plan §E.7 that `from_defaults` does NOT invoke `swing/config_overrides.py`.
- (c) Error semantics: may raise `FileNotFoundError` / `tomllib.TOMLDecodeError` / `KeyError`. Harness propagates to CLI ClickException wrapping per cumulative T-A.1.5b lesson.
- (d) L2 LOCK: reads ONLY tracked-repo `swing.config.toml`; NO external API. SAFE.

NO ADDITIONAL discriminating test required — V2 OHLCV evaluator plan §E.7 already locks the signature.

---

## §F L2 LOCK reinforcement (5 BINDING discriminating tests per spec §E.3 + brief §3.4)

The L2 LOCK invariant (ZERO new Schwab API calls; ZERO reads of `{ticker}.schwab_api.parquet`; ZERO imports of forbidden modules) MUST be preserved + REINFORCED. Since OHLCV reader is RE-EXPORTED per OQ-3 LOCK, the harness's L2 LOCK tests verify RE-EXPORT INTEGRITY (NOT duplicate the V2 reader's own tests which independently validate read behavior).

### §F.1 Test 1: Identity-preserving re-export (`is` identity assertion)

**File:** `tests/research/test_pattern_cohort_evaluator_reader.py`

```python
def test_ohlcv_reader_re_export_identity():
    """L2 LOCK reinforcement test #1: harness's ohlcv_reader symbols are
    IDENTICALLY the V2 OHLCV evaluator's symbols (same object, not a
    re-implementation). Catches accidental shadow re-implementation that
    would bypass V2's existing 5 BINDING discriminating tests.
    """
    from research.harness.aplus_v2_ohlcv_evaluator import (
        ohlcv_reader as v2_reader,
    )
    from research.harness.pattern_cohort_evaluator import (
        ohlcv_reader as pc_reader,
    )
    assert pc_reader.read_yfinance_shape_a is v2_reader.read_yfinance_shape_a
    assert (
        pc_reader.read_yfinance_shape_a_sliced
        is v2_reader.read_yfinance_shape_a_sliced
    )
    assert pc_reader.BothExistDiagnostic is v2_reader.BothExistDiagnostic
```

### §F.2 Test 2: File-open boundary check (4 file-open surfaces spied)

**File:** `tests/research/test_pattern_cohort_evaluator_reader.py`

Per V2 OHLCV evaluator's §F.1 surface (4-boundary spy: `pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table`); invoke harness reader against synthetic ticker with BOTH `{T}.yfinance.parquet` AND `{T}.schwab_api.parquet` planted; assert no `schwab_api` path appears in `opened_paths`. Full implementation copied verbatim from V2 OHLCV §F.1 with module path substituted to `research.harness.pattern_cohort_evaluator.ohlcv_reader`.

### §F.3 Test 3: Import-graph mock asserts NO schwab / yfinance / archive imports

**File:** `tests/research/test_pattern_cohort_evaluator_reader.py`

Per V2 OHLCV evaluator's §F.2 surface (4-forbidden-module sentinel + 8-banned-substring source-grep); invoke harness module-set import; assert sentinels intact post-import + source-grep returns ZERO matches across all 6 harness `.py` files. Banned-substring list extended with `read_or_fetch_archive` to enforce NEGATIVE-verification per §E.7. Full implementation copied verbatim from V2 OHLCV §F.2 with module path substituted to `research.harness.pattern_cohort_evaluator.*`.

### §F.4 Test 4: Byte-checksum discriminating fixture

**File:** `tests/research/test_pattern_cohort_evaluator_reader.py`

Per V2 OHLCV evaluator's §F.3 surface; plant both Shape A parquet (yfinance + schwab_api) with distinct sentinel close values; invoke harness reader; assert returned `Close[-1]` == yfinance sentinel (NOT schwab sentinel). Full implementation copied verbatim from V2 OHLCV §F.3 with import path substituted.

### §F.5 Test 5: Defensive signature locks for production callsites

**File:** `tests/research/test_pattern_cohort_evaluator_detector_invoker.py`

```python
def test_production_function_signatures_unchanged():
    """L2 LOCK reinforcement test #5: lock all 6 production callsites the
    harness invokes via inspect.signature.

    Per cumulative gotcha #17 (Expansion #2 refinement) BINDING + #19
    (Expansion #2 sub-refinement cascade-call-graph): brief-vs-actual-
    production-function-signature verification at test time guards against
    future production refactor.
    """
    import inspect
    import typing as _typing

    from swing.data.repos.pattern_exemplars import list_exemplars
    from swing.patterns.composite import compute_composite_score
    from swing.patterns.foundation import (
        current_stage, generate_candidate_windows,
    )
    from swing.patterns.template_matching import match_forward
    from swing.pipeline.runner import _pattern_detect_registry

    # Registry function: zero args, returns 5-tuple
    sig = inspect.signature(_pattern_detect_registry)
    assert list(sig.parameters.keys()) == []
    registry = _pattern_detect_registry()
    assert len(registry) == 5, f"detector registry length drift: {len(registry)}"
    assert {p for _, p, _ in registry} == {
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    }

    sig = inspect.signature(generate_candidate_windows)
    assert list(sig.parameters.keys()) == [
        "bars", "anchor_search_method", "ticker", "timeframe",
    ]

    sig = inspect.signature(current_stage)
    assert list(sig.parameters.keys()) == ["conn", "ticker", "asof_date"]
    from datetime import date as _date_cls
    hints = _typing.get_type_hints(current_stage)
    assert hints["asof_date"] is _date_cls

    sig = inspect.signature(compute_composite_score)
    assert list(sig.parameters.keys()) == ["geometric", "template_match"]

    sig = inspect.signature(match_forward)
    assert list(sig.parameters.keys()) == [
        "candidate_close_prices",
        "candidate_pattern_class",
        "candidate_ticker",
        "exemplar_corpus",
        "top_k",
        "geometric_score",
    ]

    sig = inspect.signature(list_exemplars)
    assert list(sig.parameters.keys()) == [
        "conn", "pattern_class", "label_source", "limit", "offset",
    ]
```

These 5 BINDING discriminating tests are blocking — failure of any one blocks the executing-plans merge per operator-witnessed gate (per V2 OHLCV evaluator L2 LOCK precedent).

---

## §G Per-task acceptance criteria + bite-sized step structure

### §G.0 Commit cadence preface (per V2 OHLCV plan §G.0 + brief §3.2)

Per spec §G.0 + V2 OHLCV executing-plans return report §3 deviations BANKED: per-task commits target the 35-60 line range; mega-consolidation deviations MUST be enumerated explicitly in executing-plans return report with "why".

Projected commit budget per sub-bundle (from spec §M.1):

| Sub-bundle | Tasks | Tests (§H) | Per-test slices | Task-wrap commits | Total commits |
|------------|-------|-----------|----------------|-------------------|---------------|
| T-PC.1 | T-PC.1.1 + T-PC.1.2 | ~7 + ~10 = ~17 | ~7+7 = 14 (parametrize-consolidation; per-mode CSV variants in 1 commit) | 2 task-wraps | ~16 commits |
| T-PC.2 | T-PC.2 (1 mono-task; 18 sub-steps) | ~18 | ~14 (parametrize-consolidation for failure-isolation × 3 + signature-lock × 6) | 1 task-wrap | ~15 commits |
| T-PC.3 | T-PC.3 (1 mono-task; 10 sub-steps) | ~10 | ~8 | 1 task-wrap | ~9 commits |
| T-PC.4 | T-PC.4 (1 mono-task; 11 sub-steps) | ~11 | ~9 | 1 task-wrap | ~10 commits |
| T-PC.5 | T-PC.5 (1 mono-task; 5 sub-steps) | ~5 | ~5 | 1 task-wrap | ~6 commits |
| **Total** | | **~61 tests** | **~50 per-test commits** (parametrize-consolidated) | **6 task-wraps** | **~56 commits** with parametrize-consolidation; **~67 commits** at raw 1-commit-per-test ceiling |

Lands within spec §G.0 brief's projected ~30-52 commit range at the parametrize-consolidated end OR slightly above at the raw end. Implementer guidance: tight parametrize-consolidation lands at ~50-56 commits; raw 1-commit-per-test lands at ~67. Final cadence is implementer's call per V2 OHLCV plan §G.0 precedent.

**Each logical TDD slice (test + minimal implementation expansion + passing test) is ONE commit.** Per cumulative TDD discipline + V2 OHLCV plan §G.0 BINDING. Implementer guidance: every "Step N: Run test to verify pass" followed by another "Step M: Write failing test" implies an IMPLICIT commit between Step N and Step M. The `### Task` blocks below explicitly enumerate task-wrap commits but elide per-test commits for readability.

---

### Task T-PC.1.1: NEW `__init__.py` + `exceptions.py` + `ohlcv_reader.py` re-export + 5 BINDING L2 LOCK tests

**Files:**
- Create: `research/harness/pattern_cohort_evaluator/__init__.py`
- Create: `research/harness/pattern_cohort_evaluator/exceptions.py`
- Create: `research/harness/pattern_cohort_evaluator/ohlcv_reader.py`
- Test: `tests/research/test_pattern_cohort_evaluator_reader.py`

- [ ] **Step 1: Write failing test for re-export identity** (per §F.1 verbatim).

- [ ] **Step 2: Run test → verify fail.** Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `__init__.py` + `exceptions.py` + `ohlcv_reader.py` per §C.1 + §C.2.**

`__init__.py`:
```python
"""Pattern cohort detector evaluator research harness.

Cohort-input-driven invocation surface for Phase 13 chart-shape detectors.
Designed to answer the question gotcha #27 surfaced: production
_step_pattern_detect gates on bucket == 'aplus' BY DESIGN; the harness
runs detectors against loosened-A+ cohorts to test orthogonal-signal hypothesis.
"""
from __future__ import annotations

__version__ = "0.1.0"
```

`exceptions.py` + `ohlcv_reader.py`: full implementations per §C.1 + §C.2.

- [ ] **Step 4: Run test → verify pass.**

- [ ] **Step 5: Add file-open boundary test (L2 LOCK #2)** per §F.2 verbatim with helper:

```python
def _make_shape_a_parquet(path, n_bars=250, sentinel_close=100.0):
    """Write a Shape A parquet (lowercase OHLCV + asof_date column)."""
    dates = pd.date_range(end="2026-04-30", periods=n_bars, freq="B")
    df = pd.DataFrame({
        "asof_date": [d.date().isoformat() for d in dates],
        "open": [sentinel_close] * n_bars,
        "high": [sentinel_close + 1.0] * n_bars,
        "low": [sentinel_close - 1.0] * n_bars,
        "close": [sentinel_close] * n_bars,
        "volume": [1_000_000] * n_bars,
    })
    df.to_parquet(path, index=False)
```

- [ ] **Step 6: Run + verify pass.**

- [ ] **Step 7: Add import-graph mock + source-grep test (L2 LOCK #3)** per §F.3 verbatim.

- [ ] **Step 8: Run + verify pass.**

- [ ] **Step 9: Add byte-checksum test (L2 LOCK #4)** per §F.4 verbatim.

- [ ] **Step 10: Run + verify pass.**

- [ ] **Step 11: Add defensive `read_or_fetch_archive` signature lock test** per §E.7:

```python
def test_read_or_fetch_archive_has_no_prefer_source_kwarg():
    """Defensive test per NEW gotcha #17 (Expansion #2 refinement BINDING)."""
    import inspect
    from swing.data.ohlcv_archive import read_or_fetch_archive
    params = inspect.signature(read_or_fetch_archive).parameters
    assert "prefer_source" not in params
```

- [ ] **Step 12: Run + verify pass.**

- [ ] **Step 13: Add exceptions hierarchy test:**

```python
def test_exception_hierarchy():
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
        OhlcvCoverageError as V2OhlcvCoverageError,
    )
    from research.harness.pattern_cohort_evaluator.exceptions import (
        BothCohortModesSuppliedError, CohortInputSchemaError,
        MalformedAsofDateError, NeitherCohortModeSuppliedError,
        OhlcvCoverageError, PatternCohortEvaluatorError,
    )
    assert OhlcvCoverageError is V2OhlcvCoverageError
    assert issubclass(CohortInputSchemaError, PatternCohortEvaluatorError)
    assert issubclass(MalformedAsofDateError, PatternCohortEvaluatorError)
    assert issubclass(BothCohortModesSuppliedError, PatternCohortEvaluatorError)
    assert issubclass(NeitherCohortModeSuppliedError, PatternCohortEvaluatorError)
```

- [ ] **Step 14: Run + verify pass.**

- [ ] **Step 15: ruff + task-wrap commit.**

Run: `ruff check research/harness/pattern_cohort_evaluator/ tests/research/test_pattern_cohort_evaluator_reader.py`

```bash
git add research/harness/pattern_cohort_evaluator/__init__.py \
        research/harness/pattern_cohort_evaluator/exceptions.py \
        research/harness/pattern_cohort_evaluator/ohlcv_reader.py \
        tests/research/test_pattern_cohort_evaluator_reader.py
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.1.1 -- exceptions + ohlcv_reader re-export + L2 LOCK tests

Adds NEW research/harness/pattern_cohort_evaluator/ package per spec §B.1
+ §C.1 + §C.2. Identity-preserving re-export of V2 OHLCV evaluator's
ohlcv_reader per OQ-3 LOCK. Typed exception hierarchy with OhlcvCoverageError
re-exported from V2.

Tests: ~7 covering re-export identity + 5 BINDING L2 LOCK tests per
§F.1-§F.4 + defensive read_or_fetch_archive signature lock + exception
hierarchy.

L2 LOCK reinforced via 5 BINDING tests; ZERO production swing/ writes;
ZERO Schwab API calls; schema v21 unchanged.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

### Task T-PC.1.2: NEW `cohort_reader.py`

**Files:**
- Create: `research/harness/pattern_cohort_evaluator/cohort_reader.py`
- Test: `tests/research/test_pattern_cohort_evaluator_cohort_reader.py`

- [ ] **Step 1: Write failing test for `parse_inline_cohort`:**

```python
def test_parse_inline_cohort_returns_entries():
    from datetime import date
    from research.harness.pattern_cohort_evaluator.cohort_reader import (
        parse_inline_cohort,
    )
    entries = parse_inline_cohort("RLMD:2026-04-15,DNTH:2026-04-15")
    assert len(entries) == 2
    assert entries[0].ticker == "RLMD"
    assert entries[0].asof_date == date(2026, 4, 15)
```

- [ ] **Step 2: Run → verify fail.**

- [ ] **Step 3: Implement `cohort_reader.py` per §C.3 verbatim.**

- [ ] **Step 4: Run → verify pass.**

- [ ] **Step 5: Add malformed-asof-date + edge tests (cumulative gotcha #12):**

5 parametrize-consolidatable tests: `parse_asof_date_raises_MalformedAsofDateError` + `parse_asof_date_returns_date` + `parse_inline_cohort_raises_on_malformed` + `parse_inline_cohort_raises_on_missing_separator` + `parse_inline_cohort_raises_on_empty_spec`.

- [ ] **Step 6: Run + verify pass.**

- [ ] **Step 7: Add CSV read tests (5+1 parametrize-consolidatable):**

`test_read_cohort_csv_required_columns_only` + `test_read_cohort_csv_full_optional_columns` + `test_read_cohort_csv_missing_required_column` + `test_read_cohort_csv_unrecognized_column` + `test_read_cohort_csv_empty_returns_empty_tuple` (per cumulative gotcha #20) + `test_cohort_entry_post_init_validates_pattern_class_filter` (per cumulative gotcha #15 Literal validation).

CSV test fixture pattern:
```python
csv_path = tmp_path / "cohort.csv"
csv_path.write_text(
    "ticker,asof_date,candidate_id,eval_run_id,bucket,pivot,"
    "initial_stop,pattern_class_filter,cohort_label\n"
    "RLMD,2026-04-15,1234,42,watch,12.50,11.25,vcp,tightness_1.005_flip\n",
    encoding="utf-8",
)
entries = read_cohort_csv(csv_path)
assert entries[0].candidate_id == 1234
assert entries[0].cohort_label == "tightness_1.005_flip"
```

- [ ] **Step 8: Run + verify pass (~10 tests total).**

- [ ] **Step 9: ruff + task-wrap commit.**

```bash
git add research/harness/pattern_cohort_evaluator/cohort_reader.py \
        tests/research/test_pattern_cohort_evaluator_cohort_reader.py
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.1.2 -- cohort_reader (inline + CSV parsers)

Adds NEW research/harness/pattern_cohort_evaluator/cohort_reader.py per spec
§C.1 + §C.2 + §C.3. CohortEntry frozen dataclass + parse_inline_cohort
(Mode (a)) + read_cohort_csv (Mode (b)). Mode (c) SQL deferred V2.5+.

Per cumulative gotcha #12 typed MalformedAsofDateError + #15 Literal validation
for pattern_class_filter + T-A.1.5b synthetic-fixture-vs-production-emitter
typed CohortInputSchemaError + #20 Expansion #4 sub-refinement empty-input
returns empty tuple (not raises) + "Python ... or '' idiom" None coercion
for empty CSV cells.

Tests: ~10 covering inline parse + 5 CSV variants + CohortEntry __post_init__.

ZERO production swing/ writes; ZERO Schwab API calls.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

### Task T-PC.2: NEW `detector_invoker.py`

**Files:**
- Create: `research/harness/pattern_cohort_evaluator/detector_invoker.py`
- Test: `tests/research/test_pattern_cohort_evaluator_detector_invoker.py`

This is the LARGEST sub-bundle per spec §M.1 + §G.0 estimate (~15 commits). 18 sub-steps + 18 tests.

- [ ] **Step 1: Write failing test for `get_detector_registry()` parity:**

```python
def test_get_detector_registry_matches_production():
    from research.harness.pattern_cohort_evaluator.detector_invoker import (
        get_detector_registry,
    )
    from swing.pipeline.runner import _pattern_detect_registry
    assert get_detector_registry() == _pattern_detect_registry()
```

- [ ] **Step 2: Run + verify fail.**

- [ ] **Step 3: Implement `detector_invoker.py` skeleton with `get_detector_registry` per §C.4.**

- [ ] **Step 4: Run + verify pass.**

- [ ] **Step 5: Add 6-production-signature consolidated lock test per §F.5 verbatim.**

- [ ] **Step 6: Run + verify pass.**

- [ ] **Step 7: Add `CohortVerdict.__post_init__` Literal validation test:**

```python
def test_cohort_verdict_post_init_validates_skip_reason():
    """Per cumulative gotcha "Literal[...] not runtime-enforced"."""
    from datetime import date
    from research.harness.pattern_cohort_evaluator.detector_invoker import (
        CohortVerdict,
    )
    import pytest
    # Valid skip reason constructs successfully
    CohortVerdict(
        cohort_entry_id=0, cohort_label=None, ticker="RLMD",
        asof_date=date(2026, 4, 15),
        candidate_id=None, eval_run_id=None, persisted_bucket=None,
        persisted_pivot=None, persisted_initial_stop=None,
        window_index=None, window_start_date=None, window_end_date=None,
        anchor_date=None, anchor_reason=None,
        pattern_class=None, detector_version=None, stage_observed=None,
        geometric_score=None, template_match_score=None, composite_score=None,
        template_match_nearest_exemplar_ids_json=None,
        criteria_pass_json=None, structural_evidence_json=None,
        skip_reason="coverage_skip",
    )
    # Invalid skip reason raises
    with pytest.raises(ValueError, match="skip_reason must be one of"):
        CohortVerdict(
            cohort_entry_id=0, cohort_label=None, ticker="RLMD",
            asof_date=date(2026, 4, 15),
            candidate_id=None, eval_run_id=None, persisted_bucket=None,
            persisted_pivot=None, persisted_initial_stop=None,
            window_index=None, window_start_date=None, window_end_date=None,
            anchor_date=None, anchor_reason=None,
            pattern_class=None, detector_version=None, stage_observed=None,
            geometric_score=None, template_match_score=None,
            composite_score=None,
            template_match_nearest_exemplar_ids_json=None,
            criteria_pass_json=None, structural_evidence_json=None,
            skip_reason="bogus_reason",
        )
```

- [ ] **Step 8: Implement `CohortVerdict` + `CohortRunResult` + `_skip_verdict` + `_build_verdict` + `invoke_cohort` per §C.4 verbatim.**

- [ ] **Step 9: Run + verify pass.**

- [ ] **Step 10: Add `_seed_minimal_schema` test helper** that creates `evaluation_runs` + `candidates` + `candidate_criteria` + `pattern_exemplars` tables matching the column-list of `_SELECT_COLUMNS_SQL` at `swing/data/repos/pattern_exemplars.py`. Implementer reads that constant + matches; if schema drift surfaces, extends helper.

- [ ] **Step 11: Add 3 per-entry try/except discriminating tests** (parametrize-consolidatable):
- `test_per_entry_coverage_skip_does_not_poison_others` (3-ticker cohort with 1 missing archive)
- `test_per_entry_no_windows_does_not_poison_others` (monkeypatch `generate_candidate_windows` to return [] for one ticker)
- `test_per_detector_exception_does_not_poison_other_detectors` (monkeypatch ONE detector to raise; assert OTHER 4 emit verdicts; `detector_error_all == 0`)

- [ ] **Step 12: Run + verify pass.**

- [ ] **Step 13: Add filter precedence tests** (per OQ-5):
- `test_per_entry_pattern_class_filter_takes_precedence_over_cli`
- `test_cli_pattern_class_filter_applies_when_per_entry_unset`

- [ ] **Step 14: Add window-mode tests** (per OQ-7):
- `test_window_mode_last_only_emits_one_window_per_entry_per_class`
- `test_window_mode_per_window_emits_multiple_window_indices`

- [ ] **Step 15: Add template-match Pass 2 ON/OFF tests** (per OQ-6):
- `test_template_match_off_skips_corpus_load` (asserts `corpus_size_at_invocation == 0` + `template_match_score is None`)
- `test_template_match_on_loads_corpus_once_per_invocation`

- [ ] **Step 16: Add `stage_observed` lookup tests:**
- `test_stage_observed_surfaces_undefined_for_empty_db`
- `test_stage_observed_surfaces_stage_2_for_seeded_8_TT_pass_candidate` (seeds candidates row with 8 candidate_criteria rows for trend_template layer all 'pass'; assert stage_observed == 'stage_2')

- [ ] **Step 17: Add `composite_score` formula parity test** (per spec §C.4 step 6 + §D.4):

```python
def test_composite_score_uses_production_formula(tmp_path):
    """Asserts harness's composite_score equals compute_composite_score
    output exactly (NOT a re-implementation)."""
    from swing.patterns.composite import compute_composite_score
    # ... after invoke_cohort, iterate verdicts + assert:
    for v in result.verdicts:
        if v.skip_reason is not None or v.composite_score is None:
            continue
        expected = compute_composite_score(
            geometric=v.geometric_score,
            template_match=v.template_match_score,
        )
        assert abs(v.composite_score - expected) < 1e-9
```

- [ ] **Step 18: Add empty-cohort short-circuit test** (per cumulative gotcha #20):

```python
def test_invoke_cohort_empty_cohort_returns_empty_result(tmp_path):
    from research.harness.pattern_cohort_evaluator.detector_invoker import (
        invoke_cohort,
    )
    import sqlite3
    conn = sqlite3.connect(":memory:")
    _seed_minimal_schema(conn)
    result = invoke_cohort(
        (), conn=conn, cache_dir=tmp_path,
        window_mode="last-only", template_match_mode="off",
    )
    assert result.cohort_entries_count == 0
    assert result.entries_processed == 0
    assert result.verdicts_emitted == 0
    assert result.verdicts == ()
    assert all(c == 0 for c in result.skipped_entries.values())
```

- [ ] **Step 19: Run all detector_invoker tests + ruff + task-wrap commit.**

```bash
git add research/harness/pattern_cohort_evaluator/detector_invoker.py \
        tests/research/test_pattern_cohort_evaluator_detector_invoker.py
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.2 -- detector_invoker (per-entry orchestration + template-match Pass 2)

Adds NEW research/harness/pattern_cohort_evaluator/detector_invoker.py per
spec §C.4 + §D + §E. Per-(cohort_entry, pattern_class, window) orchestration;
production detector registry re-import per OQ-1 LOCK + cumulative gotcha #19
(cascade-call-graph) BINDING; window generation via generate_candidate_windows
with zigzag_pivot only per OQ-4 LOCK; per-entry try/except with 5 enumerated
skip reasons per cumulative T2.SB5 lesson + gotcha #27; template-match Pass 2
mirrors production at runner.py:1844-1969 (corpus load + filter to confirmed
+ watch; per-exemplar try/except per T2.SB5 isolation; geometric_score
pre-gate 0.4); composite_score via compute_composite_score per L5 LOCK
formula parity; stage_observed surface from current_stage lookup.

Tests: ~18 covering registry parity + 6 production signature locks +
CohortVerdict __post_init__ + 3 per-entry failure isolation + filter
precedence + window-mode + template-match on/off + stage_observed surface
+ composite_score formula parity + empty-cohort short-circuit.

Per cumulative gotcha #17 + #19 + #22 + #23 BINDING (all pre-applied).

ZERO production swing/ writes; ZERO Schwab API calls.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

### Task T-PC.3: NEW `output.py`

**Files:**
- Create: `research/harness/pattern_cohort_evaluator/output.py`
- Test: `tests/research/test_pattern_cohort_evaluator_output.py`

- [ ] **Step 1: Write failing test for CSV header column count:**

```python
def test_results_csv_header_matches_spec_24_columns():
    from research.harness.pattern_cohort_evaluator.output import _CSV_HEADERS
    assert len(_CSV_HEADERS) == 24
    assert _CSV_HEADERS[0] == "cohort_entry_id"
    assert _CSV_HEADERS[-1] == "skip_reason"
```

- [ ] **Step 2: Run + verify fail.**

- [ ] **Step 3: Implement `output.py` skeleton with `_CSV_HEADERS` + `write_results_csv` + `_verdict_to_row` per §C.5.**

- [ ] **Step 4: Run + verify pass.**

- [ ] **Step 5: Add CSV row round-trip test for non-skip verdict.**

- [ ] **Step 6: Add CSV skip-row empty-state test** (per OQ-12 LOCK + cumulative T3.SB3): all skip-row optional fields render as empty string (NOT 'None' literal, NOT 'null' string).

- [ ] **Step 7: Implement markdown writers per §C.5.** Add tests for:
- `test_summary_markdown_renders_all_sections` (Header + Headline + Per-class drill-down + Skip-summary + Both-exist banner + Notes + Manifest summary)
- `test_summary_markdown_empty_cohort_renders_none_placeholders` (per OQ-12 `(none)` literal)
- `test_summary_markdown_both_exist_banner_suppressed_when_count_zero`
- `test_summary_markdown_ascii_only` (body.encode('cp1252') no raise)

- [ ] **Step 8: Implement `write_manifest_json` per §C.5.** Add test:
- `test_manifest_json_round_trip_all_required_keys` (asserts all 23+ keys from spec §I.3 + `l2_lock_preserved is True`)

- [ ] **Step 9: Add skip-reason summary coverage test** (per cumulative gotcha #22): all 5 skip_reasons appear in markdown summary table even when count is 0.

- [ ] **Step 10: Run all output tests + ruff + task-wrap commit.**

```bash
git add research/harness/pattern_cohort_evaluator/output.py \
        tests/research/test_pattern_cohort_evaluator_output.py
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.3 -- output (CSV + markdown + manifest)

Adds NEW research/harness/pattern_cohort_evaluator/output.py per spec §C.5
+ §I.2-§I.4. 24-column CSV writer; markdown summary writer (Header +
Headline + Per-pattern-class drill-down + Skip-reason summary + Both-exist
warning banner + Notes + Manifest summary); manifest JSON writer per spec
§I.3 schema.

Per cumulative Windows cp1252 stdout safety gotcha: ASCII-only enforcement
at write_summary_markdown via body.encode('cp1252') sanity check. Per
cumulative T3.SB3 lesson + OQ-12 LOCK: uniform empty-state ('(none)'
markdown / '' CSV / None JSON). Per cumulative gotcha #22 + #15 enum
propagation: all 5 skip reasons render in summary table.

Tests: ~10.

ZERO production swing/ writes; ZERO Schwab API calls.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

### Task T-PC.4: NEW `run.py` + CLI subcommand registration

**Files:**
- Create: `research/harness/pattern_cohort_evaluator/run.py`
- Modify: `swing/cli.py` (SOLE production write per OQ-13)
- Test: `tests/research/test_pattern_cohort_evaluator_run.py`
- Test: `tests/cli/test_diagnose_subcommands.py` (extension)

- [ ] **Step 1: Write failing test for `run_harness` happy path** (synthetic 1-ticker cohort + planted Shape A + monkeypatch `_get_cfg` to point cache_dir at tmp_path).

- [ ] **Step 2: Run + verify fail.**

- [ ] **Step 3: Implement `run.py` per §C.6 verbatim.**

- [ ] **Step 4: Run + verify pass.**

- [ ] **Step 5: Add 5 CLI validation tests** (parametrize-consolidatable):
- `test_run_harness_both_cohort_modes_raises` → `BothCohortModesSuppliedError`
- `test_run_harness_neither_cohort_mode_raises` → `NeitherCohortModeSuppliedError`
- `test_run_harness_invalid_window_mode_raises` → `ValueError`
- `test_run_harness_invalid_template_match_mode_raises` → `ValueError`
- `test_run_harness_unknown_pattern_class_filter_raises` → `ValueError` with name enumerated

- [ ] **Step 6: Add DB URI `mode=ro` test** (sqlite3.connect spy; assert URI contains `mode=ro` per V2 OHLCV Codex R2.M2 precedent).

- [ ] **Step 7: Add output path convention test** (timestamped subdir + 3 files).

- [ ] **Step 8: Modify `swing/cli.py`** — register `pattern-cohort-detect` subcommand mirroring `aplus-sensitivity-v2` precedent at `swing/cli.py:4791-4859` (LOCK: 35-60 lines target per OQ-13; banked deviation if exceeds per V2 OHLCV plan §G.0). Full registration code:

```python
@diagnose_group.command("pattern-cohort-detect")
@click.option("--cohort-csv", "cohort_csv", type=click.Path(path_type=Path), default=None)
@click.option("--cohort-inline", "cohort_inline", type=str, default=None,
              help="Mode (a) comma-separated 'ticker:asof_date' pairs.")
@click.option("--db", "db_path", required=True, type=click.Path(path_type=Path))
@click.option("--output-dir", type=click.Path(path_type=Path),
              default=Path("exports/research"), show_default=True)
@click.option("--window-mode", type=click.Choice(("last-only", "per-window")),
              default="per-window", show_default=True)
@click.option("--template-match", "template_match_mode",
              type=click.Choice(("on", "off")),
              default="on", show_default=True)
@click.option("--pattern-class-filter", "pattern_class_filter", type=str,
              default=None, help="Comma-separated pattern_class filter.")
def diagnose_pattern_cohort_detect(
    cohort_csv: Path | None,
    cohort_inline: str | None,
    db_path: Path,
    output_dir: Path,
    window_mode: str,
    template_match_mode: str,
    pattern_class_filter: str | None,
) -> None:
    """Pattern cohort detector evaluator harness.

    Invokes Phase 13 chart-shape detectors against an operator-supplied
    cohort of (ticker, asof_date) tuples. See
    research/method-records/pattern-cohort-detection.md (v0.1.0+).
    """
    _validate_diagnose_db_path(db_path)
    from research.harness.pattern_cohort_evaluator.exceptions import (
        BothCohortModesSuppliedError, NeitherCohortModeSuppliedError,
    )
    from research.harness.pattern_cohort_evaluator.run import run_harness

    filter_tuple: tuple[str, ...] | None = None
    if pattern_class_filter:
        filter_tuple = tuple(
            s.strip() for s in pattern_class_filter.split(",") if s.strip()
        )

    try:
        results_path, md_path, manifest_path = run_harness(
            cohort_csv=cohort_csv,
            cohort_inline=cohort_inline,
            db_path=db_path,
            output_dir=output_dir,
            window_mode=window_mode,
            template_match_mode=template_match_mode,
            cli_pattern_class_filter=filter_tuple,
        )
    except (
        ValueError,
        BothCohortModesSuppliedError,
        NeitherCohortModeSuppliedError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    click.echo(f"Results CSV: {results_path}")
    click.echo(f"Summary MD:  {md_path}")
    click.echo(f"Manifest:    {manifest_path}")
```

- [ ] **Step 9: Add CLI smoke tests** in `tests/cli/test_diagnose_subcommands.py`:
- `test_diagnose_pattern_cohort_detect_help_smoke` (asserts `--help` shows `--cohort-csv`, `--cohort-inline`, `--db`)
- `test_diagnose_pattern_cohort_detect_neither_mode_raises_clean` (CLI exit_code != 0; output mentions "Exactly one of")
- `test_diagnose_pattern_cohort_detect_db_not_found_raises_clean` (CLI exit_code != 0; output mentions "DB not found")

- [ ] **Step 10: Add subprocess stdout cp1252 safety test** (per cumulative Windows gotcha): invokes `python -m swing.cli diagnose pattern-cohort-detect --help` via subprocess + decodes stdout/stderr as cp1252 without raising.

- [ ] **Step 11: Run all T-PC.4 tests + ruff + verify `git diff swing/ --stat` shows ONLY `swing/cli.py` modified + task-wrap commit.**

```bash
git add research/harness/pattern_cohort_evaluator/run.py \
        swing/cli.py \
        tests/research/test_pattern_cohort_evaluator_run.py \
        tests/cli/test_diagnose_subcommands.py
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.4 -- run.py + CLI subcommand registration

Adds NEW research/harness/pattern_cohort_evaluator/run.py per spec §C.6 +
NEW 'swing diagnose pattern-cohort-detect' subcommand in swing/cli.py per
OQ-13 carve-out LOCK (SOLE production-swing/ write this arc; mirrors V2
OHLCV aplus-sensitivity-v2 precedent at swing/cli.py:4791-4859).

DB connection opens via URI mode=ro per V2 OHLCV Codex R2.M2 + R3.m2
precedent. Mutual-exclusion validation between cohort modes; window_mode +
template_match_mode + cli_pattern_class_filter validated at run_harness
boundary with ValueError → ClickException wrapping per cumulative T-A.1.5b
lesson. Subprocess stdout cp1252 safety per cumulative Windows gotcha.

Tests: ~11.

OQ-13 SOLE production carve-out verified: 'git diff swing/ --stat' shows
only swing/cli.py modified.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

### Task T-PC.5: NEW method-record + first study writeup + integration tests + operator smoke + closer

**Files:**
- Create: `research/method-records/pattern-cohort-detection.md`
- Create: `research/studies/<harness-ship-date>-pattern-cohort-detection.md`
- Modify: `research/phase-0-tasks.md`
- Test: `tests/research/test_pattern_cohort_evaluator_integration.py`
- Operator-supplied: `exports/research/cohorts/tightness_1.005_flips_67.csv`
- Operator smoke artifact: `exports/research/pattern-cohort-detection-<ISO>/{results.csv,summary.md,manifest.json}`

- [ ] **Step 1: Author method-record per spec §K.1-§K.5 verbatim** with frontmatter `key: pattern-cohort-detection`, `version: 0.1.0`, `status: research`, `last_updated: <YYYY-MM-DD harness ship date>` + 5 sections (Definition + Promotion criteria + Validation notes + Limitations L1-L4 + Notes).

- [ ] **Step 2: Author first study writeup per spec §L.1 template** (8 sections; Results section populated POST operator smoke run in step 5).

- [ ] **Step 3: Author 5 integration tests** in `tests/research/test_pattern_cohort_evaluator_integration.py`:
- `test_e2e_synthetic_3_ticker_cohort` (E2E happy-path; assert 3 output files exist; manifest.json `l2_lock_preserved=true`)
- `test_e2e_idempotent_against_static_fixture` (two invocations against same fixture; byte-equal results.csv per spec §D.6 + §F.4)
- `test_e2e_pattern_class_filter_via_cli` (assert only filtered classes emit non-skip)
- `test_e2e_window_mode_per_window_emits_multiple_window_indices`
- `test_e2e_brief_framing_first_cohort_target_size` (per spec §F.7; assert row count == 67 + unique ticker count == 15 IF CSV committed; SKIPS otherwise)

- [ ] **Step 4: Run integration tests + verify pass** (or 1 SKIPPED for brief-framing if CSV not yet committed).

- [ ] **Step 5: Operator smoke run against 67-entry first-cohort target.** Operator provides `exports/research/cohorts/tightness_1.005_flips_67.csv`. Implementer captures:

```bash
python -m swing.cli diagnose pattern-cohort-detect \
    --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv \
    --db ~/swing-data/swing.db \
    --output-dir exports/research/ \
    --window-mode per-window \
    --template-match on
```

Smoke artifact lands at `exports/research/pattern-cohort-detection-<ISO>/{results.csv,summary.md,manifest.json}`.

- [ ] **Step 6: Update study writeup `Results` section** per smoke artifact (per-pattern-class detector-pass counts + per-entry composite_score distribution + cross-tabulation against backtest output per spec §I.5 + §L.1 step 5).

- [ ] **Step 7: Update `research/phase-0-tasks.md` "Next" section** — reflect harness SHIPPED status (second method-record COMPLETED following V2 OHLCV evaluator first; precedent inherited).

- [ ] **Step 8: Final closer commit.**

```bash
git add research/method-records/pattern-cohort-detection.md \
        research/studies/<date>-pattern-cohort-detection.md \
        research/phase-0-tasks.md \
        tests/research/test_pattern_cohort_evaluator_integration.py \
        exports/research/cohorts/tightness_1.005_flips_67.csv \
        exports/research/pattern-cohort-detection-<ISO>/results.csv \
        exports/research/pattern-cohort-detection-<ISO>/summary.md \
        exports/research/pattern-cohort-detection-<ISO>/manifest.json
git commit -m "$(cat <<'EOF'
feat(research): pattern cohort harness T-PC.5 -- method-record + first study writeup + operator smoke + closer

Adds NEW research/method-records/pattern-cohort-detection.md per spec §K
(key=pattern-cohort-detection; status=research; version=0.1.0; promotion
ladder + validation notes + limitations enumerated per spec §K.3 + §K.4
+ §L.2). NEW first study writeup per spec §L.1 template.

Integration tests: 5 (E2E synthetic + idempotency + filter + window-mode
per-window + brief-framing first-cohort target size).

Operator smoke artifact captured at
exports/research/pattern-cohort-detection-<ISO>/.

Pattern cohort detector evaluator harness SHIPPED end-to-end.
SECOND Applied Research arc post-Phase-13-FULLY-CLOSED COMPLETE.

ZERO new Schwab API calls (L2 LOCK preserved + reinforced via 5 BINDING
discriminating tests per §K). Schema v21 UNCHANGED through entire arc.
OQ-13 SOLE production carve-out respected.

NO Co-Authored-By footer per cumulative discipline.
EOF
)"
```

---

## §H Test scope per-task budget

Per spec §H.1 + brief §3 baseline; recalibrated for parametrize-consolidated commit cadence per §G.0.

| Sub-bundle | Test file(s) | Test count | Per-test enumeration |
|------------|--------------|------------|----------------------|
| T-PC.1.1 | `test_pattern_cohort_evaluator_reader.py` | **~7** | (1) re-export identity; (2) file-open boundary mock (L2 LOCK #2); (3) import-graph mock + source-grep (L2 LOCK #3); (4) byte-checksum discriminating (L2 LOCK #4); (5) defensive read_or_fetch_archive signature lock; (6) exception hierarchy (OhlcvCoverageError identity + 4 harness exceptions); (7) consolidated edge cases (parametrized). |
| T-PC.1.2 | `test_pattern_cohort_evaluator_cohort_reader.py` | **~10** | (1) inline parse 2 entries; (2) parse_asof_date raises typed exc on garbage; (3) valid asof_date returns date; (4) inline raises on missing separator; (5) inline raises on empty spec; (6) CSV required columns only; (7) CSV full optional columns round-trip; (8) CSV missing required column raises; (9) CSV unrecognized column raises; (10) CSV empty returns empty tuple + CohortEntry __post_init__ pattern_class_filter validation (consolidatable). |
| T-PC.2 | `test_pattern_cohort_evaluator_detector_invoker.py` | **~18** | (1) get_detector_registry matches production; (2) 6 production signature locks (parametrize); (3) CohortVerdict __post_init__ Literal validation; (4) per-entry coverage_skip isolation; (5) per-entry no_windows isolation; (6) per-entry archive_missing_skip isolation; (7) per-detector exception does NOT poison others; (8) per-entry filter takes precedence over CLI; (9) CLI filter applies when per-entry unset; (10) window-mode last-only one window; (11) window-mode per-window multiple; (12) template-match off skips corpus load; (13) template-match on loads corpus once; (14) stage_observed 'undefined' for empty DB; (15) stage_observed 'stage_2' for seeded TT-pass-count==8 candidate; (16) composite_score formula parity; (17) empty-cohort short-circuit; (18) detector_error_all only when ALL detectors raise. |
| T-PC.3 | `test_pattern_cohort_evaluator_output.py` | **~10** | (1) CSV header column count == 24; (2) CSV row round-trip non-skip; (3) CSV skip-row empty-state uniform; (4) markdown renders all 7 sections; (5) markdown empty-cohort renders (none); (6) markdown both-exist banner suppressed when count==0; (7) markdown ASCII-only cp1252 round-trip; (8) manifest JSON round-trip all required keys; (9) manifest l2_lock_preserved=true; (10) markdown skip-reason summary lists all 5 reasons. |
| T-PC.4 | `test_pattern_cohort_evaluator_run.py` + `test_diagnose_subcommands.py` extension | **~11** | (1) run_harness returns 3 paths happy-path; (2) both modes raises BothCohortModesSuppliedError; (3) neither mode raises NeitherCohortModeSuppliedError; (4) invalid window_mode raises; (5) invalid template_match_mode raises; (6) unknown pattern_class filter raises; (7) DB URI mode=ro verified via sqlite3.connect spy; (8) output path convention; (9) CLI --help smoke; (10) CLI neither-mode raises clean; (11) CLI db-not-found raises clean + subprocess stdout cp1252 safety (consolidatable). |
| T-PC.5 | `test_pattern_cohort_evaluator_integration.py` | **~5** | (1) E2E synthetic 3-ticker cohort; (2) E2E idempotent against static fixture; (3) E2E pattern-class filter via CLI; (4) E2E window-mode per-window; (5) brief-framing first-cohort target size lock (per spec §F.7; SKIPS if CSV not committed). |
| **Total** | | **~61 NEW fast tests** | Parametrize-consolidated bound: ~50-55. Baseline ~5893 → ~5944-5954 post-harness-ship. ZERO slow-marked tests. |

---

## §I Plan-phase OQ work-items resolved

### §I.1 Per-sub-bundle Codex MCP round-budget (§M.3 spec OQ #5)

Resolved at §N below.

### §I.2 Actual function signatures + class shapes (§M.3 spec OQ #1)

Resolved at §C verbatim BINDING.

### §I.3 Exact CLI flag naming + default value tuning (§M.3 spec OQ #2)

Resolved at §C.5 (spec) + §C.6 (this plan) BINDING:
- `--cohort-csv PATH` / `--cohort-inline LIST` (mutually exclusive; required).
- `--db PATH` (required).
- `--output-dir DIR` default `exports/research/`.
- `--window-mode {last-only,per-window}` default `per-window` per OQ-7 LOCK.
- `--template-match {on,off}` default `on` per OQ-6 LOCK.
- `--pattern-class-filter NAME[,NAME...]` default None (all 5 detectors).

`--max-runtime-seconds N` proposed in spec §C.5 but DEFERRED V1: harness has simpler runtime profile than V2 OHLCV evaluator (no per-(variable, sweep_point) loop multiplying work); first-cohort target is small (67 entries); runtime budget < 5 min projected. V2.5 candidate BANKED.

### §I.4 Per-task test-budget refinement (§M.3 spec OQ #3)

Resolved at §H verbatim.

---

## §J Forward-binding lessons inherited

### §J.1 27 cumulative gotchas (BINDING for writing-plans-phase pre-Codex review)

| # | Gotcha | Plan application |
|---|--------|------------------|
| 1-8 | Original cumulative discipline through Phase 11 | Schema-CHECK + Python-constant + dataclass-validator paired discipline N/A (no schema change); other process disciplines applied at orchestrator level. |
| 9 | SQL aggregation UNIT audit (Expansion #8) | N/A (no COUNT/SUM/GROUP BY in harness SQL skeletons; Mode (c) deferred V2.5+). |
| 10 | Existing-field reuse audit before claiming new dataclass fields | APPLIED at §C.4 `CohortVerdict` — every field justified per spec §I.2 24-column schema; no field duplication. |
| 11 | Template-rendering surface audit before claiming "no template edit needed" | N/A (no Jinja templates; markdown via Python string concat). |
| 12 | `date.fromisoformat()` discipline | APPLIED at §C.3 `parse_asof_date` + discriminating test §G T-PC.1.2 step 5. |
| 13 | Form-render anchor lifecycle audit (Expansion #9) | N/A (no web routes / forms). |
| 14 | Architecture-location audit + 5 sub-disciplines (Expansion #10) | APPLIED at §B.1 NEW module placement + dependency-surface table per spec §B.1. Sub-discipline (e) orphan-label preservation mapped to per-skip-reason counters at §C.4. |
| 15 | Taxonomy propagation audit (Expansion #11) | APPLIED at §C.4 `_SKIP_REASONS` frozenset + §C.3 `_ALLOWED_PATTERN_CLASSES` frozenset + §C.5 `_CSV_HEADERS` 24-tuple — each enum value propagated through dataclass __post_init__ + CSV header + markdown rendering + test fixtures. |
| 16 | Sibling-route audit (Expansion #12) | N/A (no route handlers; single-CLI-entry-point). |
| 17 | Expansion #2 refinement — brief-vs-actual-production-function-signature verification | APPLIED at §E (6 production functions verified via inspect.signature + typing.get_type_hints; 1 NEGATIVE verification at §E.7); consolidated discriminating test at §F.5 covers all 6 callsites. |
| 18 | Expansion #4 refinement — SQL skeleton JOIN-cardinality + downstream-sufficiency audit | APPLIED at §D for production-helper SQL consumed transitively. |
| 19 | Expansion #2 sub-refinement — cascade-call-graph verification | APPLIED at §E.1-§E.6 — for each production function, cascade behavior verified (e.g., `_pattern_detect_registry` body invokes 5 lazy module imports + returns 5-tuple verbatim; `generate_candidate_windows` zigzag_pivot invokes `extract_zigzag_swings` pure helper). Discriminating test at §F.5 asserts registry length + tuple equality. |
| 20 | Expansion #4 sub-refinement — runtime-binding-shape + empty-result-set audit | APPLIED at §D.3 — empty-cohort + empty-corpus + empty-current_stage cases enumerated; discriminating tests at §G T-PC.1.2 step 7 + §G T-PC.2 step 18. |
| 21 | Expansion #13 candidate — cumulative regression cascade audit | Banked for executing-plans phase post-Codex-fix discipline. |
| 22 | Expansion #8 promotion — per-counter-accumulation audit | APPLIED at §C.4 `CohortRunResult` + §G T-PC.2 step 11 + step 18 — every counter unit enumerated: `entries_processed` per-cohort-entry; `verdicts_emitted` per-non-skip-row; `skipped_entries[r]` per-cohort-entry; `detector_error_all` fires only when ALL attempted detectors raise (verified in test). |
| 23 | Expansion #11 promotion — dataclass attribution metadata audit | APPLIED at §C.4 `CohortVerdict` 24 fields — each attribution field (cohort_entry_id + cohort_label + window_index + anchor_reason + detector_version + stage_observed + skip_reason) explicitly enumerated with required/optional semantics. |
| 24 | Parallel-archive freshness desync | APPLIED via OQ-3 re-export — harness inherits V2 OHLCV evaluator's both-exist Shape A wins LOCK + diagnostic surface. Limitation L4 in method-record §K.4. |
| 25 | Sentinel-bucket parity-comparison discipline | N/A this dispatch — harness emits per-(cohort_entry, pattern_class, window) verdicts directly; no V1↔V2 baseline parity at the bucket level. Production-parity invariant per spec §E.1 operates at per-(geometric_score, composite_score, structural_evidence_json) verdict level. |
| 26 | OHLCV archive bar-content TEMPORAL mutation | APPLIED at spec §D.6 idempotency caveat + method-record §K.4 Limitation L2 (template per spec §L.2 verbatim). |
| 27 | Silent-skip-without-audit pattern in pipeline steps | APPLIED at §C.4 + §G T-PC.2 + §C.5 markdown skip-reason summary — the harness is gotcha #27's architectural answer AND models its discipline via per-skip-reason counters + per-entry skip-row CSV emission. |

### §J.2 NEW candidate refinements banked from this plan

No NEW candidate refinements surfaced during this writing-plans phase pre-Codex review (operator may commission Codex chain at Turn D; if NEW gotchas surface, append per V2 OHLCV writing-plans precedent).

### §J.3 Per cumulative discipline (process)

- **NO Co-Authored-By footer** — ~519+ cumulative streak through brief commit `16f9efc`. Every commit message in §G cites the discipline per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety per cumulative gotcha).
- **TDD per task** via `superpowers:test-driven-development`.
- **Edit tool for per-file edits**; Write tool reserved for new file creation.

---

## §K L2 LOCK reinforcement (5 BINDING discriminating tests; cross-reference §F)

5 BINDING discriminating tests at `tests/research/test_pattern_cohort_evaluator_reader.py` + `tests/research/test_pattern_cohort_evaluator_detector_invoker.py`:

- **§K.1 Test 1**: Identity-preserving re-export. See §F.1.
- **§K.2 Test 2**: File-open boundary mock (4 file-open surfaces). See §F.2.
- **§K.3 Test 3**: Import-graph mock + source-grep (9-banned-substring list including `read_or_fetch_archive`). See §F.3.
- **§K.4 Test 4**: Byte-checksum discriminating fixture. See §F.4.
- **§K.5 Test 5**: Production function signature locks (6 production callsites). See §F.5.

These 5 BINDING tests are operator-witnessed-gate blocking per V2 OHLCV evaluator L2 LOCK precedent — failure of any one blocks executing-plans merge.

---

## §L Research-branch coordination

### §L.1 NEW method-record at `research/method-records/pattern-cohort-detection.md`

Per spec §K.1: NEW method-record (NOT extension; sibling to `aplus-criteria-calibration.md`). Frontmatter:

```yaml
---
key: pattern-cohort-detection
name: Chart-shape pattern cohort detector-confirmation harness
layer: detection
status: research
baseline_or_predecessor: production swing.pipeline.runner._step_pattern_detect (aplus-only)
version: 0.1.0
last_updated: <harness ship date>
---
```

Required sections per spec §K.2-§K.5: Definition + Promotion criteria (research → shadow → production) with 4 research→shadow conditions + 3 shadow→production conditions + 3 anti-promotion guards + Validation notes + Limitations L1-L4 + Notes.

### §L.2 First study writeup at `research/studies/<harness-ship-date>-pattern-cohort-detection.md`

Per spec §L.1 template + `research/studies/earnings-proximity-exclusion.md` format precedent. 8 required sections: Question + Null hypothesis + Baseline + Methodology + Results + Interpretation + Limitations (L1-L4 verbatim per spec §L.2) + Conclusion.

### §L.3 `research/phase-0-tasks.md` "Next" section refresh

Per spec §M.4: reflects harness SHIPPED status (second method-record COMPLETED). V2.5+ candidates from spec §K.5 enumerated.

### §L.4 First-cohort substrate CSV at `exports/research/cohorts/tightness_1.005_flips_67.csv`

Per spec §C.3: 67 entries / 15 unique tickers from V2 OHLCV sensitivity drill-down at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md` lines 9725-10866 filtered to `sweep_point=1.005` AND `to_bucket=aplus`. Operator-side cohort-CSV generator MAY be a one-off `tmp/` artifact; the CSV itself committed to `exports/research/cohorts/`.

### §L.5 Operator smoke run output capture

Per spec §M.1 row 5: operator runs harness against the 67-entry first-cohort target; captures `exports/research/pattern-cohort-detection-<ISO>/{results.csv,summary.md,manifest.json}`; commits with closer.

---

## §M Closure procedure

T-PC.5 closer (per spec §M.1 row 5) MUST include:

1. **CLAUDE.md line 3 refresh** — pattern cohort detector evaluator harness SHIPPED status; SECOND Applied Research arc COMPLETE post-Phase-13-FULLY-CLOSED.
2. **`docs/orchestrator-context.md` "Currently in-flight work"** — second arc closed; pivot to next applied-research arc OR Phase 14 commissioning consideration per spec §M.4.
3. **First study writeup** committed at `research/studies/<date>-pattern-cohort-detection.md`.
4. **Method-record `pattern-cohort-detection.md` version 0.1.0** committed at `research/method-records/`.
5. **Operator smoke run output** captured + committed to `exports/research/pattern-cohort-detection-<ISO>/`.
6. **First-cohort substrate CSV** committed to `exports/research/cohorts/tightness_1.005_flips_67.csv`.
7. **`research/phase-0-tasks.md` "Next"** refreshed per §L.3.
8. **Final closer commit message** cites: pattern cohort harness SHIPPED; method-record 0.1.0; first study writeup; baseline ~5893 → ~5944-5954 fast tests (+55-61 NEW per §H); ZERO new Schwab API calls (L2 LOCK preserved + reinforced via 5 BINDING discriminating tests per §K); schema v21 UNCHANGED; OQ-13 carve-out boundary respected (only `swing/cli.py` modified, verified via `git diff swing/` gate); ZERO Co-Authored-By footer; ALL 27 cumulative gotchas honored.

Post-closer orchestrator-side housekeeping:
- QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING.
- Merge branches `--no-ff` to `main`; push.
- Post-merge housekeeping bundle.
- Decide next arc per spec §M.4.

---

## §N Per-sub-bundle Codex MCP round-budget expectation

Per spec §M.3 OQ #5 (deferred to writing-plans phase): writing-plans estimates per-sub-bundle Codex MCP round budgets informed by complexity:

| Sub-bundle | Estimated Codex rounds | Justification |
|------------|------------------------|---------------|
| T-PC.1.1 | 1-2 | Tight surface (3 small modules; ~7 tests); RE-EXPORT pattern minimizes surprise surface — V2 OHLCV reader's existing L2 LOCK tests are the canonical authority + this harness's tests verify re-export integrity. Cumulative gotcha #17 + #19 + #20 BINDING but already pre-applied at plan-write time. |
| T-PC.1.2 | 1-2 | Bounded surface (1 module + 10 tests); pure-Python CSV/inline parser; cumulative gotcha #12 + #15 + #20 BINDING; LOW Codex surface area. |
| T-PC.2 | 2-3 | **HIGHEST** — detector_invoker is the largest sub-bundle (~15 commits per §G.0; ~18 tests per §H); production registry cascade-call-graph (gotcha #19); template-match Pass 2 production parity at runner.py:1844-1969; 5 enumerated skip reasons + per-counter-accumulation discipline (gotcha #22); 6 production signature locks (gotcha #17). Moderate Codex surface area. |
| T-PC.3 | 1-2 | output.py is pure formatter; ~10 tests; well-bounded; cumulative ASCII cp1252 + OQ-12 uniform empty-state + gotcha #15 enum propagation already pre-applied. LOW Codex surface area. |
| T-PC.4 | 2-3 | run.py + CLI carve-out; ClickException wrapping; subprocess stdout cp1252 safety; OQ-13 production-`swing/` boundary verified via `git diff swing/` gate. Modest Codex surface area but CLI registration touches production code so review scrutiny elevated. |
| T-PC.5 | 1-2 | **LOWEST** — method-record + study writeup + integration tests + closer; docs-mostly; small test surface (~5 integration tests). Codex surface area minimal. |
| **Total cumulative across 5 sub-bundles** | **8-14 Codex rounds** | Comparable-but-smaller than V2 OHLCV evaluator executing-plans cumulative round budget (10-14). The structural simplicity of this harness (no cfg substitution; no per-(variable, sweep_point) sweep loop; OHLCV reader re-exported NOT re-implemented) reduces the Codex surface area. |

Writing-plans phase's OWN Codex MCP chain expected 2-5 rounds IF operator commissions one (per dispatch brief §2.3 OPTIONAL; 38th cumulative C.C lesson #6 validation slot available).

---

## §O Self-review (BINDING per superpowers:writing-plans final step)

### §O.1 Spec coverage check

Skim spec §A-§N + verify each requirement has a corresponding task in this plan:

- §A (status + scope + research-branch positioning + schema discipline + V2.1 lifecycle + production retention + non-scope) → §A this plan
- §B (NEW research module layout + 7 files + dependency surface table + repository cross-references) → §B file map + §B.2 dep graph + §C module signatures
- §C (cohort entry shape + 3 cohort input modes + first-cohort target + harness data flow + CLI surface + output paths) → §C.3 + §C.4 + §C.6 + §G T-PC.1.2 + T-PC.2 + T-PC.4
- §D (detector invocation interface + detector registry adoption + per-entry try/except + template-match Pass 2 + Stage-2 gate semantic + idempotency) → §C.4 + §E + §G T-PC.2 + integration test in §G T-PC.5
- §E (production-parity invariant + Stage-2 gate parity + L2 LOCK preservation + empty-cohort handling) → §E.1 + §F + §K + §G T-PC.5 integration tests
- §F (5 BINDING L2 LOCK tests + 3 per-detector-failure isolation + production-parity tests + idempotency test + cohort-input shape tests + output schema tests + brief-framing accuracy test + total count budget) → §F + §K + §H + §G per-task tests
- §G (commit cadence preface + Codex round-budget expectation + NO Co-Authored-By discipline) → §G.0 + §N + §J.3
- §H (per-module test budget + cumulative gotcha catalog application + test count baseline + cross-bundle pin disposition) → §H + §J.1
- §I (inputs + output CSV schema 24 cols + output manifest JSON + output markdown structure + downstream consumption pathway) → §C.5 + §G T-PC.3 + §L.2 study writeup
- §J (13 OQs surfaced + RECOMMEND dispositions) → §A.4 dispositions LOCKED + §I.1-§I.4
- §K (NEW method-record + definition + promotion criteria + validation notes + notes section) → §L.1 + §G T-PC.5
- §L (first-cohort study writeup template + limitations section template) → §L.2 + §G T-PC.5
- §M (5 sub-bundle decomposition + concurrent dispatch + open questions deferred to writing-plans + post executing-plans handback) → §B.2 + §A.4 + §I + §M
- §N (self-review) → §O this section

ZERO gaps.

### §O.2 Placeholder scan

Search this plan for placeholder red flags per superpowers:writing-plans BINDING "No Placeholders" rule:
- "TBD" → ZERO matches.
- "TODO" → ZERO matches.
- "implement later" → ZERO matches.
- "fill in details" → ZERO matches.
- "appropriate error handling" / "add validation" / "handle edge cases" → ZERO matches.
- "Write tests for the above" without code → ZERO matches.
- "Similar to Task N" → ZERO matches (each task self-contained; references to spec sections are BINDING substrate citations).
- `<harness ship date>` / `<date>` / `<ISO>` / `<YYYY-MM-DD>` — these are INTENTIONAL placeholders to be stamped at ship time per spec §K.1 + V2 OHLCV evaluator §K precedent; NOT plan failures.

### §O.3 Type consistency

Cross-checked function signatures + dataclass shapes across §C.1-§C.6 + task code blocks:
- `OhlcvCoverageError` referenced consistently in §C.1 (re-export) + §C.4 (try/except) + §G T-PC.2 step 11.
- `BothExistDiagnostic` referenced consistently in §C.2 (re-export) + §C.4 (parameter) + §C.5 (manifest) + §G T-PC.1.1 step 9.
- `CohortEntry` field list (9 fields: ticker + asof_date required + 7 optional) consistent across §C.3 + §C.4 + §G T-PC.1.2.
- `CohortVerdict` field list (24 fields) consistent across §C.4 + §C.5 `_CSV_HEADERS` (24 column count assertion) + spec §I.2 + §G T-PC.3.
- `CohortRunResult` field list consistent between §C.4 + §C.5 (consumed by output writers) + §G T-PC.3.
- `_SKIP_REASONS` frozenset (5 values) consistent across §C.4 module-level + `CohortVerdict.__post_init__` + §G T-PC.2 step 7 + §G T-PC.3 step 9.
- `_ALLOWED_PATTERN_CLASSES` frozenset (5 values) consistent across §C.3 module-level + `CohortEntry.__post_init__` + §C.6 `run_harness` validation + §G T-PC.1.2 step 7 + §G T-PC.4 step 5.
- `run_harness(...)` signature consistent between §C.6 + §G T-PC.4.1 + §G T-PC.4.8 (CLI subcommand delegation kwargs).
- `get_detector_registry()` return shape (5-tuple of `(callable, str, str)`) consistent across §C.4 + §E.1 + §G T-PC.2.1 + §F.5.

ZERO type-consistency issues.

### §O.4 Per-cumulative-gotcha disposition check

Spot-checked §J.1 against actual plan body:
- Gotcha #15 (Expansion #11 taxonomy propagation) — `_SKIP_REASONS` + `_ALLOWED_PATTERN_CLASSES` enumerated at §C.3 + §C.4; propagated through dataclass `__post_init__` validators + CSV header + test fixtures.
- Gotcha #17 (Expansion #2 refinement signature) — 6 production functions verified at §E; consolidated discriminating test at §F.5 + §G T-PC.2 step 5.
- Gotcha #19 (Expansion #2 sub-refinement cascade-call-graph) — registry cascade verified at §E.1 + assertion `len(registry) == 5` + tuple equality at §F.5.
- Gotcha #20 (Expansion #4 sub-refinement empty-result-set) — empty-cohort + empty-CSV + empty-corpus enumerated at §D.3 + discriminating tests at §G T-PC.1.2 step 7 + §G T-PC.2 step 18.
- Gotcha #22 (Expansion #8 promotion per-counter-accumulation) — `entries_processed` + `verdicts_emitted` + `skipped_entries[r]` + `detector_error_all` unit semantics enumerated at §C.4 + discriminating test at §G T-PC.2 step 11 (detector_error_all fires ONLY when ALL attempted detectors raise).
- Gotcha #23 (Expansion #11 promotion dataclass attribution) — `CohortVerdict` 24 attribution fields enumerated at §C.4 with required/optional semantics.
- Gotcha #27 (silent-skip-without-audit) — per-skip-reason counters + per-entry skip-row CSV emission + markdown skip-reason summary table; harness is gotcha #27's architectural answer.

ZERO disposition gaps.

---

*End of pattern cohort detector evaluator harness implementation plan. SECOND Applied Research arc post-Phase-13-FULLY-CLOSED writing-plans phase. Consumes 996-line brainstorming-phase spec as BINDING substrate. ALL 13 OQ dispositions LOCKED per operator triage 2026-05-24 PM with ZERO amendments (mirrors V2 OHLCV 18-OQ-LOCKED precedent). 5 BINDING L2 LOCK discriminating tests enumerated; production read-only invariant preserved (OQ-13 sole carve-out at swing/cli.py); schema v21 UNCHANGED; 27 cumulative gotchas honored. ~519+ ZERO Co-Authored-By footer streak preserved through this plan commit.*
