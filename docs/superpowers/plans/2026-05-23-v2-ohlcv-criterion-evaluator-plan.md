# V2 OHLCV Criterion-Evaluator Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship V2 OHLCV criterion-evaluator harness as a NEW research-branch module under `research/harness/aplus_v2_ohlcv_evaluator/` that lifts the V1 LIMITATION (15 threshold variables inert in V1 per `research/harness/aplus_sensitivity/sweep.py:248-250`) by substituting cfg-derived values one-at-a-time and invoking production `swing.evaluation.evaluator.evaluate_one(ctx)` end-to-end against historical OHLCV.

**Architecture:** NEW module per spec §C.1 architecture-location LOCK + Expansion #10 discipline; 5-sub-bundle decomposition (T-V2.1..T-V2.5); read-only direct Shape A parquet read via NEW `ohlcv_reader.py` wrapper (bypasses production `swing.data.ohlcv_archive.read_or_fetch_archive` to preserve reproducibility + L2 LOCK); per-eval_run BatchContext cache + per-ticker OHLCV cache (LOAD-BEARING per spec §F.5); production `swing/` code is READ-ONLY except for one explicit minimal CLI subcommand registration carve-out at `swing/cli.py` per OQ-17 LOCK; schema v21 UNCHANGED.

**Tech Stack:** Python 3.11+ (3.14 on operator's box), pandas (parquet I/O + DataFrame slicing), sqlite3 (read-only via URI `mode=ro` per Codex R2.M2 RESOLVED against operator's `swing-data/swing.db`), Click (CLI subcommand registration), pytest (TDD per task; **~80 NEW fast tests** projected per §H recalibration — parametrize-consolidated bound ~65-70; ZERO slow tests). NO yfinance / NO schwabdev / NO swing.data.ohlcv_archive / NO swing.integrations.schwab imports in the V2 module set (defense-in-depth per L2 LOCK + OQ-12 + OQ-16 + Codex R1.M3 RESOLVED 4-module sentinel).

---

## §A Status + scope (binding context)

### §A.1 Lineage

V2 OHLCV criterion-evaluator harness is the FIRST Applied Research arc post-Phase-13-FULLY-CLOSED per Path B operator LOCK 2026-05-23 PM (`b4d7719` `docs/phase13-closer-next-phase-triage.md`). Brainstorming spec at [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](../specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) (1086 lines; 14 sections §A-§N) is BINDING substrate; Codex chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR (3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place; ZERO accepted-as-rationale). Writing-plans dispatch brief at [`docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md`](../../v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md) (~450 lines; 11 sections; 18 OQ dispositions LOCKED per RECOMMEND with ZERO amendments per operator triage Turn D).

### §A.2 V1 LIMITATION lift target

Per spec §B.1 + operator motivating question:

> Which of the 15 inert threshold variables (V1 LIMITATION at `research/harness/aplus_sensitivity/sweep.py:248-250`) are binding at the watch→A+ promotion boundary, ranked by marginal A+ count per loosening unit?

V2 lifts the V1 LIMITATION by substituting one variable at a time via `dataclasses.replace(cfg.<sub>, <field>=<sweep_value>)` and invoking production `evaluate_one(ctx)` end-to-end against historical OHLCV reconstructed at each candidate's `data_asof_date`. Output answers the motivating question in a headline section atop the markdown deliverable per spec §G.1.

### §A.3 Production read-only invariant (with OQ-17 CLI carve-out)

Production `swing/` is READ-ONLY for the duration of this dispatch arc EXCEPT for the ONE explicit minimal CLI subcommand-registration carve-out in `swing/cli.py` per spec §A.1 + OQ-17 LOCK. The carve-out covers (a) `@click.command`-decorated handler + (b) `@diagnose.command` group attachment + (c) `@click.option` definitions + (d) `ClickException` wrapping per cumulative T-A.1.5b lesson + (e) delegation to `research.harness.aplus_v2_ohlcv_evaluator.run.run_harness`. Realistic line count: 35-60 lines per V1 precedent at `swing/cli.py:4748-4787` (verified via Codex R2.M6). NO schema changes. NO migrations. NO writes to `swing-data/swing.db`. NO writes to OHLCV archive parquet files.

Discriminating gate at T-V2.4 ship: `git diff swing/ --stat` after V2 executing-plans phase shows ONLY `swing/cli.py` modified.

### §A.4 18 OQ dispositions LOCKED (verbatim from brief §1)

| OQ | Disposition LOCKED |
|---|---|
| OQ-1 OHLCV reconstruction scope | Direct Shape A yfinance read via NEW `ohlcv_reader.py` wrapper (bypasses `read_or_fetch_archive`; NEVER opens schwab_api parquet; legacy `{ticker}.parquet` fallback). |
| OQ-2 Per-criterion evaluator interface | cfg-substitution via `dataclasses.replace` + production `evaluate_one(ctx)` end-to-end per §D.1. Single-variable downstream propagation preserved. `vcp.watch_max_fails` special-case mirrors V1 per §E.3. |
| OQ-3 Sweep range strategy | Inherit V1 5-point grid per V2.1 §IV.B parsimony. Adaptive bisection + full-range deferred V3+. |
| OQ-4 Output format | Hybrid: V1 12-col matrix (9 V1 cols + 3 NEW skip cols) + headline section + per-variable drill-down + V1↔V2 parity section + both-exist diagnostic banner per §G. |
| OQ-5 Scope discipline | ALL 15 inert threshold variables in one dispatch (NOT phased). |
| OQ-6 Validation universe | Reuse S3's 5681 candidates / 63 eval_runs for V1↔V2 reproducibility (NOT fresh fetch). |
| OQ-7 Cross-coupling | 1D per V2.1 §IV.B parsimony. Single-variable downstream propagation preserved WITHIN 1D; 2D+ interaction effects deferred V3+. |
| OQ-8 Method-record promotion criteria | 3-tier research→shadow→production ladder per §K.3. research→shadow: V2 shipped + baseline parity green + ≥1 study writeup + ≥1 binding threshold OR all 15 declared non-binding with sign-off. shadow→production: ≥1 cfg-policy proposal evaluated against ≥2 disjoint universes + delta statistically distinguishable (default ≥5 A+ delta on 5681-candidate universe — doubling A+ count) + operator-paired ratification. Anti-promotion guards per §K.3. |
| OQ-9 Performance budget cap | Default UNSET + `--max-runtime-seconds N` CLI flag for partial-run capability. Acceptance target: <60 min on operator hardware for full 5681/63/17/5 universe. |
| OQ-10 V2 CLI surface name | `swing diagnose aplus-sensitivity-v2`. Back-compat preserved (V1 stays at `aplus-sensitivity`). |
| OQ-11 `vcp.watch_max_fails` hardcode handling | Mirror V1's special-case substitution per §E.3 for V2 ship. BANK V2.5 candidate: "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` (1-line production change at `swing/evaluation/scoring.py:37`)". |
| OQ-12 Schwab API L2 LOCK preservation | yfinance-only via direct Shape A `{ticker}.yfinance.parquet` read. Discriminating tests per §K below. |
| OQ-13 OHLCV coverage failure attribution mode | Skip + report. Single `ohlcv_coverage_skip_count` scalar per V2 invocation per Codex R1.M3 (same value across all per-variable rows because `evaluate_one` runs all criteria together — coverage skip is per-candidate-per-V2-run not per-(variable, sweep_point)). |
| OQ-14 RS universe reconstruction at historical asof_date | Current-universe snapshot for V2 ship (V2 reads `cfg.paths.rs_universe_path` at V2 invocation + uses that universe for ALL historical eval_runs). Surface drift caveat in study writeup `Limitations` section. V3+ candidate: persist per-eval_run universe snapshots at write-time. |
| OQ-15 `current_equity` surrogate for risk gate recompute | Per-eval_run-historical from `account_equity_snapshots` rows with snapshot_date ≤ eval_run's `data_asof_date` IF available; fall back to latest snapshot row OTHERWISE; mark tier-2 candidates (per §E.4 risk-gate-dependent buckets) with `bucket_via_surrogate=True` for operator transparency. |
| OQ-16 OHLCV archive read strategy | Direct Shape A parquet read via NEW V2 wrapper `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`. Bypasses production `read_or_fetch_archive` (no `prefer_source` kwarg AND actively fetches yfinance on miss). NO fetch path; reproducible per-V2-invocation; L2 LOCK preserved. |
| OQ-17 CLI subcommand registration as read-only carve-out | Explicit minimal carve-out per spec §A.1 amended language. Realistic line count: 35-60 lines per V1 precedent. This is the SOLE production-`swing/` modification V2 dispatch makes. NO other writes; NO schema change; NO migration. |
| OQ-18 Both-exist legacy/Shape A archive read policy | Shape A wins unconditionally + per-ticker diagnostic surface. V2 reads `{ticker}.yfinance.parquet`; ignores legacy in both-exist case. Per Codex R4.M1: `both_exist_shape_a_wins_count` scalar + per-ticker affected list + warning banner. V2.5 candidate: port production merge logic to V2 reader. |

### §A.5 Schema discipline (LOCK)

Schema v21 LOCKED. V2 does NOT touch migrations. Verified via brief §3.4 + spec §A.2: V2's SQL skeletons reference ONLY existing columns at `swing/data/migrations/0001_phase1_initial.sql:9-56`. Discriminating gate at T-V2.5 closer: `git diff swing/data/migrations/ --stat` after V2 ship shows ZERO files modified.

### §A.6 Streaks preserved through this plan write

- ~439+ ZERO `Co-Authored-By` footer trailer cumulative (commit chain through brief commit `f8cafd9`)
- Baseline 5778 fast tests UNCHANGED through writing-plans phase (writing-plans is docs-only)
- ZERO new Schwab API calls (V2 design preserves L2 LOCK; reinforced via §K)
- Schema v21 UNCHANGED through writing-plans phase

---

## §B Per-sub-bundle file map + dependency graph

### §B.1 File map (NEW + MODIFIED surfaces)

| Sub-bundle | Path | New / Modified | Responsibility |
|------------|------|----------------|----------------|
| T-V2.1 | `research/harness/aplus_v2_ohlcv_evaluator/__init__.py` | NEW | Package marker (empty + version constant `__version__ = "0.2.0"` matching method-record §K.1). |
| T-V2.1 | `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py` | NEW | Typed exceptions: `OhlcvCoverageError`, `MissingRsUniversePathError`, `EmptyRsUniverseError`, `InvalidRsUniverseError`, `PostCleanupUniverseTooSmallError`, `OutOfRangeSubstitutionError`, `MalformedAsofDateError`. |
| T-V2.1 | `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` | NEW | Read-only Shape A parquet wrapper; reads `{ticker}.yfinance.parquet`; legacy `{ticker}.parquet` fallback; both-exist Shape A wins + diagnostic surface; column-case normalization (lowercase→capitalized); NEVER opens schwab_api parquet. Pure I/O; no fetch; no write. |
| T-V2.1 | `research/harness/aplus_v2_ohlcv_evaluator/cfg_substitution.py` | NEW | `substitute_cfg(cfg, variable_name, sweep_value) -> Config` via `dataclasses.replace`; type-preservation invariant; unknown-subsection `ValueError`. |
| T-V2.1 | `research/harness/aplus_v2_ohlcv_evaluator/context_builder.py` | NEW | OHLCV slicing at asof_date via `ohlcv_reader`; BatchContext reconstruction at historical asof_date (full RS universe per Codex C1; `returns_12w_by_ticker` cross-sectional; `spy_return_12w`); `current_equity` surrogate per OQ-15; tier-1/tier-2 risk-gate classifier; universe validation (non-empty + min-size + shape regex + dedup + post-cleanup re-check). |
| T-V2.2 | `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` | NEW | `SweepEntryV2` dataclass + `run_v2_sweep(...)` orchestrator; per-(variable, sweep_point) tally with per-candidate failure isolation (3 modes); per-eval_run BatchContext cache (LOAD-BEARING per Codex M4); per-TICKER OHLCV cache; baseline parity (tier-1 EXACT + tier-2 CONDITIONAL with surrogate); `vcp.watch_max_fails` special-case mirror; out-of-range substitution skip; runtime cap support. |
| T-V2.3 | `research/harness/aplus_v2_ohlcv_evaluator/output.py` | NEW | CSV writer (12 cols); markdown writer (headline + matrix + drill-down + V1↔V2 parity + Notes + both-exist warning banner + manifest); ASCII-only enforcement (cp1252 safety); empty-state uniform representation. |
| T-V2.4 | `research/harness/aplus_v2_ohlcv_evaluator/run.py` | NEW | `run_harness(...)` orchestrator + argparse `main()` for direct invocation; output path conventions (`exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}`). |
| T-V2.4 | `swing/cli.py` | MODIFIED (SOLE production write) | NEW `swing diagnose aplus-sensitivity-v2` subcommand registration per OQ-17 carve-out (35-60 lines; mirror V1 at `swing/cli.py:4748-4787`). |
| T-V2.5 | `research/method-records/aplus-criteria-calibration.md` | MODIFIED | Version bump 0.1.0 → 0.2.0; NEW sections per spec §K.2 + §K.3 + §K.4 + §K.5. |
| T-V2.5 | `research/studies/2026-MM-DD-v2-ohlcv-criterion-evaluator.md` | NEW | First V2 study writeup (date stamped at V2 ship); methodology + baseline parity verification + per-variable findings + Limitations enumerating OQ-14 + OQ-15 + OQ-18 caveats. |
| T-V2.5 | `research/phase-0-tasks.md` | MODIFIED | "Next" section reflects V2 SHIPPED status (first method-record COMPLETED). |
| T-V2.5 | `exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}` | NEW (operator smoke artifact) | Captured operator smoke run output committed for ledger. |

Test paths (per §H recalibrated ~80 tests — see §H per-test enumeration; ~65-70 parametrize-consolidated):

| Test file | Sub-bundle | Test count |
|-----------|------------|------------|
| `tests/research/test_aplus_v2_ohlcv_reader.py` | T-V2.1 | ~12 |
| `tests/research/test_aplus_v2_ohlcv_context_builder.py` | T-V2.1 | ~12 |
| `tests/research/test_aplus_v2_ohlcv_cfg_substitution.py` | T-V2.1 | ~6 |
| `tests/research/test_aplus_v2_ohlcv_sweep.py` | T-V2.2 | ~14 |
| `tests/research/test_aplus_v2_ohlcv_output.py` | T-V2.3 | ~10 |
| `tests/research/test_aplus_v2_ohlcv_run.py` | T-V2.4 | ~8 |
| `tests/research/test_aplus_v2_ohlcv_integration.py` | T-V2.5 | ~6 |

Baseline 5778 fast tests → ~5846 post-V2-ship. ZERO slow-marked tests in V2 scope.

### §B.2 Dependency graph (sequential dispatch per spec §M.2)

```
T-V2.1 (exceptions + ohlcv_reader + cfg_substitution + context_builder)
   ↓
T-V2.2 (sweep.py — consumes ohlcv_reader + context_builder + cfg_substitution)
   ↓
T-V2.3 (output.py — consumes SweepEntryV2 from sweep.py)
   ↓
T-V2.4 (run.py + CLI registration — consumes sweep.run_v2_sweep + output writers)
   ↓
T-V2.5 (method-record extension + study writeup + operator smoke + closer)
```

NO concurrent dispatch per spec §M.2 RECOMMEND. Single-implementer sequential via `copowers:subagent-driven-development` per project workflow precedent.

---

## §C Module function signatures + class shapes (BINDING)

Per spec §M.3 OQ #1 (refine spec §C.1 + §D.3 proposed shapes to BINDING signatures during writing-plans phase).

### §C.1 `exceptions.py`

```python
"""Typed exceptions for the V2 OHLCV criterion-evaluator harness."""
from __future__ import annotations


class OhlcvCoverageError(Exception):
    """Raised when a candidate's OHLCV archive has fewer than 200 bars at
    its data_asof_date (insufficient for trend_template MA200 per
    swing/evaluation/criteria/trend_template.py:24-29).
    """


class MissingRsUniversePathError(Exception):
    """Raised when cfg.paths.rs_universe_path is unset or the file is
    unreadable. V2 fails-fast at universe load.
    """


class EmptyRsUniverseError(Exception):
    """Raised when the loaded RS universe is empty OR has fewer than
    --min-universe-size tickers (default 100).
    """


class InvalidRsUniverseError(Exception):
    """Raised when the loaded RS universe contains more than 5% shape-invalid
    rows (>10 rows whichever is greater). Lists first 20 invalid symbols
    in the message.
    """


class PostCleanupUniverseTooSmallError(Exception):
    """Raised when AFTER dropping invalid + dedup rows the accepted-ticker
    count falls below --min-universe-size. Separate from EmptyRsUniverseError
    because the original universe passed the pre-cleanup threshold.
    """


class OutOfRangeSubstitutionError(Exception):
    """Raised when a sweep_value falls outside the cfg dataclass field's
    documented range (e.g., trend_template.min_passes substituted with 9 when
    only 8 TT criteria exist).
    """


class MalformedAsofDateError(Exception):
    """Raised when evaluation_runs.data_asof_date is not a valid
    ISO YYYY-MM-DD string (cumulative gotcha #12 discipline).
    """
```

### §C.2 `ohlcv_reader.py`

```python
"""Read-only Shape A parquet wrapper for the V2 OHLCV harness.

NEVER opens {ticker}.schwab_api.parquet (L2 LOCK preservation per OQ-12 + OQ-16).
NO fetch path. NO writes. NO archive mutation. Reads only:
  - {cache_dir}/{TICKER}.yfinance.parquet  (Shape A primary)
  - {cache_dir}/{TICKER}.parquet            (legacy fallback)

Both-exist policy: Shape A wins unconditionally (per OQ-18 LOCK; caveat
in study writeup Limitations section).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError


@dataclass
class BothExistDiagnostic:
    """Tracks per-V2-invocation both-exist diagnostic surface (Codex R4.M1).

    Populated by repeated read_yfinance_shape_a invocations during a single
    V2 run. Emitted to manifest + markdown warning banner by output.py.
    """
    count: int = 0
    affected_tickers: list[str] = field(default_factory=list)


def read_yfinance_shape_a(
    ticker: str,
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    """Read the per-ticker yfinance Shape A parquet (with legacy fallback).

    Returns: DataFrame indexed by datetime (ascending; tz-naive) with
    capitalized OHLCV columns (Open/High/Low/Close/Volume) per
    swing/evaluation/criteria expectations.

    Behavior:
      - Primary: read {cache_dir}/{TICKER}.yfinance.parquet (Shape A).
        Columns are lowercase (open/high/low/close/volume) per Shape A
        convention at swing/data/ohlcv_archive.py:449+521-522.
      - Legacy fallback: if primary absent, read {cache_dir}/{TICKER}.parquet
        (capitalized OHLCV; DatetimeIndex).
      - Both-exist case: Shape A wins; if `diagnostic` is provided, increment
        count + append ticker to affected_tickers.
      - Column-case normalization: lowercase OHLCV are renamed to capitalized
        AT THE READ BOUNDARY so downstream evaluate_one(ctx) sees production-
        expected column names (per Codex R2.C1).
      - asof_date handling: Shape A files carry an explicit `asof_date` ISO
        string column; this reader converts to a DatetimeIndex (UTC-naive,
        ascending) and DROPS the asof_date column.
      - NEVER reads {TICKER}.schwab_api.parquet under any branch.

    Raises:
      OhlcvCoverageError: when neither yfinance Shape A nor legacy file exists.
    """
    ...


def read_yfinance_shape_a_sliced(
    ticker: str,
    cache_dir: Path,
    *,
    asof_date,  # datetime.date
    min_bars: int = 200,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    """Read + slice the per-ticker yfinance Shape A parquet to bars
    <= asof_date (inclusive).

    Raises:
      OhlcvCoverageError: when the sliced frame has fewer than `min_bars` rows
        (per spec §F.2 + cumulative gotcha "yfinance history strip" backward-
        looking inequality discipline — `data_asof_date` is BACKWARD-looking,
        so `<=` (inclusive) is correct per the existing weather lookup +
        Phase 13 T1.SB0 R3 gotcha precedent).
    """
    ...
```

### §C.3 `cfg_substitution.py`

```python
"""cfg substitution helper for the V2 OHLCV harness.

Substitutes one cfg field at a time via dataclasses.replace + returns a NEW
Config (immutable; original unchanged). The vcp.watch_max_fails variable is
NOT routed through this helper — see spec §E.3 / OQ-11 special-case at
sweep.py.
"""
from __future__ import annotations

import dataclasses

from swing.config import Config


_KNOWN_SUBSECTIONS: frozenset[str] = frozenset(
    {"trend_template", "vcp", "risk", "rs"}
)


def substitute_cfg(
    cfg: Config,
    variable_name: str,
    sweep_value: float | int,
) -> Config:
    """Return a NEW Config with `variable_name` = `sweep_value`; other
    fields unchanged.

    Args:
      cfg: production cfg from Config.from_defaults() or operator's cfg.
      variable_name: dotted-path form "<sub>.<field>" where <sub> is one of
        {trend_template, vcp, risk, rs}.
      sweep_value: numeric value to substitute. Must match the field's
        expected type (int for additive variables; float for multiplicative).

    Raises:
      ValueError: when <sub> is not in {trend_template, vcp, risk, rs}
        (per Expansion #11 taxonomy discipline + cumulative
        "Literal[...] type hints are NOT runtime-enforced" gotcha).
    """
    sub, field = variable_name.split(".", 1)
    if sub not in _KNOWN_SUBSECTIONS:
        raise ValueError(
            f"substitute_cfg: unknown cfg subsection {sub!r}; "
            f"expected one of {sorted(_KNOWN_SUBSECTIONS)}"
        )
    sub_obj = getattr(cfg, sub)
    new_sub = dataclasses.replace(sub_obj, **{field: sweep_value})
    return dataclasses.replace(cfg, **{sub: new_sub})
```

### §C.4 `context_builder.py`

```python
"""BatchContext + CandidateContext reconstruction at historical asof_date.

Loads RS universe (with non-empty + min-size + shape regex + dedup +
post-cleanup re-check validations per spec §F.4); computes per-eval_run
returns_12w_by_ticker across the FULL RS universe (NOT candidate-only
per Codex R1.C1); resolves `current_equity` per OQ-15 surrogate; classifies
candidates into tier-1 vs tier-2 per spec §E.4 + Codex R2.M3.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
    EmptyRsUniverseError,
    InvalidRsUniverseError,
    MalformedAsofDateError,
    MissingRsUniversePathError,
    OhlcvCoverageError,
    PostCleanupUniverseTooSmallError,
)
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a_sliced,
)
from swing.config import Config
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.rs import load_universe

# Shape regex per Codex R3.M2: starts with capital letter; followed by
# capital letters / digits / dots / hyphens.
_TICKER_SHAPE_RE = re.compile(r"^[A-Z][A-Z0-9.\-]*$")

_BENCHMARK_TICKER = "SPY"
_RETURNS_HORIZON_TRADING_DAYS_DEFAULT = 60  # 12 weeks * 5 days (production cfg.rs.horizon_weeks=12 default)

# Codex R3.M1 RESOLVED: per-ticker min-bars threshold for returns_12w is
# NOT a fixed 60; it must scale with the (possibly-substituted)
# rs.horizon_weeks per production at swing/pipeline/runner.py:1060-1077
# (`bars_needed = cfg.rs.horizon_weeks * 5`; check `len(closes) > bars_needed`).
# Computed dynamically inside build_eval_run_cohort as:
#   bars_needed = horizon_weeks * 5  # candidate skip threshold for THIS run
# Decoupled from candidate OHLCV coverage (200 bars per TT MA200) which
# remains a separate fixed gate (OhlcvCoverageError per spec §E.5).


@dataclass(frozen=True)
class CandidateRow:
    """One row from the candidates SQL skeleton (spec §F.3).

    Mirrors the BINDING SQL columns (Codex R2.M3-amended JOIN) at C.1.
    """
    candidate_id: int
    ticker: str
    persisted_bucket: str  # 'aplus' | 'watch' | 'skip' | 'error' | 'excluded'
    data_asof_date: date  # converted from TEXT per cumulative gotcha #12
    persisted_risk_result: str | None  # 'pass' | 'fail' | 'na' | None (LEFT JOIN miss)


@dataclass(frozen=True)
class EvalRunCohort:
    """One eval_run + its full BatchContext + per-(ticker,date) cache key."""
    eval_run_id: int
    data_asof_date: date
    batch: BatchContext
    current_equity: float
    current_equity_via_surrogate: bool  # True = no historical snapshot found; using current
    universe_skipped_ticker_count: int  # tickers with <60 bars; per Codex C1


def parse_asof_date(raw: str) -> date:
    """Parse TEXT data_asof_date → datetime.date.

    Raises:
      MalformedAsofDateError: when raw is not a valid ISO YYYY-MM-DD string
        (cumulative gotcha #12 — must be typed exception, NOT TypeError deep
        in Python stack).
    """
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise MalformedAsofDateError(
            f"evaluation_runs.data_asof_date malformed: {raw!r}; "
            f"expected ISO YYYY-MM-DD string"
        ) from exc


def load_validated_rs_universe(
    cfg: Config,
    *,
    min_universe_size: int = 100,
) -> tuple[tuple[str, ...], str]:
    """Load RS universe with V2-side validations layered atop production
    swing.evaluation.rs.load_universe per spec §F.4.

    Returns: (validated_universe_tickers_sorted_unique, v2_universe_hash)
      - v2_universe_hash = "v2_universe_hash_" + SHA-256(sorted tuple bytes)
        per Codex R2.m1 (distinct from production's universe_version_hash
        which hashes file bytes).

    Validations:
      (a) Non-empty + min_universe_size (Codex R2.M4) → EmptyRsUniverseError.
      (b) Ticker-shape regex (Codex R3.M2) → InvalidRsUniverseError if
          shape-invalid rows >5% of total (or >10 rows whichever is greater).
          Warning + drop otherwise. Rejected symbols enumerated (first 20).
      (c) Duplicate detection → warning + drop.
      (d) Post-cleanup re-check (Codex R4.M2) →
          PostCleanupUniverseTooSmallError if accepted < min_universe_size.

    Raises:
      MissingRsUniversePathError, EmptyRsUniverseError, InvalidRsUniverseError,
      PostCleanupUniverseTooSmallError.
    """
    ...


def fetch_eval_runs(
    conn: sqlite3.Connection,
    *,
    eval_runs_window: int,
) -> list[tuple[int, date]]:
    """SELECT id, data_asof_date FROM evaluation_runs ORDER BY id DESC
    LIMIT :eval_runs_window. Returns list of (eval_run_id, parsed asof_date).

    Per cumulative gotcha #12: TEXT data_asof_date → date via parse_asof_date.
    """
    ...


def fetch_candidates(
    conn: sqlite3.Connection,
    *,
    eval_run_ids: list[int],
    eval_run_dates: dict[int, date],
) -> list[CandidateRow]:
    """SELECT candidates + LEFT JOIN risk_feasibility per spec §F.3 SQL
    skeleton (Codex R2.M3 amended).

    JOIN-cardinality (NEW gotcha #18 Expansion #4 refinement BINDING):
      - candidates JOIN evaluation_runs ON er.id = c.evaluation_run_id: 1:1
        (candidates.evaluation_run_id is NOT NULL REFERENCES per migration
        0001_phase1_initial.sql:26).
      - candidates LEFT JOIN candidate_criteria cc_risk
        ON cc_risk.candidate_id = c.id
        AND cc_risk.layer = 'risk'
        AND cc_risk.criterion_name = 'risk_feasibility':
        1:0-or-1 (candidate_criteria PK is (candidate_id, criterion_name)
        per migration 0001_phase1_initial.sql:55; AT MOST one
        'risk_feasibility' row per candidate).

    Downstream-sufficiency walk: caller needs (candidate_id, ticker,
    persisted_bucket, data_asof_date) for OHLCV slicing + V1↔V2 parity;
    persisted_risk_result for tier-1/tier-2 classification per spec §E.4.

    The SQL skeleton has NO COUNT/SUM/GROUP BY; no DISTINCT needed
    (UNIQUE(evaluation_run_id, ticker) at migration 0001_phase1_initial.sql:41
    guarantees per-row uniqueness in candidates).
    """
    ...


def build_eval_run_cohort(
    conn: sqlite3.Connection,
    *,
    eval_run_id: int,
    data_asof_date: date,
    cfg: Config,
    universe_tickers: tuple[str, ...],
    candidate_tickers: tuple[str, ...],   # Codex R2.M1 RESOLVED
    universe_hash: str,
    cache_dir: Path,
    horizon_weeks: int,
    diagnostic: BothExistDiagnostic,
) -> EvalRunCohort:
    """Build the BatchContext + resolve current_equity surrogate for one
    (eval_run_id, data_asof_date) cohort.

    Steps:
      1. For each ticker in `universe_tickers ∪ candidate_tickers ∪ {SPY}`
         (Codex R2.M1 RESOLVED): read Shape A; slice to <= data_asof_date;
         compute `horizon_weeks * 5`-bar trailing return (per-ticker skip if
         `len(closes) <= horizon_weeks * 5` per production at
         `swing/pipeline/runner.py:1060-1077` — bars_needed scales with the
         possibly-substituted horizon_weeks; Codex R3.M1 RESOLVED). The
         spec §F.4 step 4 fixed-60-bars text refers to the production
         default horizon_weeks=12 case (12 * 5 = 60); V2 generalizes the
         threshold to the run-time horizon.
         The candidate-not-in-universe inclusion is LOAD-BEARING:
         production `compute_rs` at `swing/evaluation/rs.py:65-85` returns
         `method='fallback_spy'` (NOT `'unavailable'`) when the ticker is
         absent from `universe_tickers` BUT present in `returns_12w_by_ticker`.
         TT8 at `swing/evaluation/criteria/trend_template.py:125-145` consumes
         that fallback_spy result via excess-vs-SPY > `rs.fallback_extreme_pct`
         logic. Without populating returns for candidates outside the universe,
         their RS resolves to `unavailable` → TT8 fails → baseline parity
         breaks for the affected candidates.
      2. SPY return → spy_return_12w (fallback 0.0 if missing).
      3. current_equity per OQ-15: query
         account_equity_snapshots via
         swing.data.repos.account_equity_snapshots.get_latest_snapshot_on_or_before(
             conn, asof_date=data_asof_date.isoformat())
         If None → fallback to most-recent snapshot via
         list_snapshots(conn, limit=1)[0]; if STILL None → use a documented
         floor surrogate per project capital-floor convention auto-memory
         (max($7500, equity)); set current_equity_via_surrogate=True if
         either fallback fires.
      4. Construct BatchContext + return EvalRunCohort.

    rs.horizon_weeks substitution propagates here (writing the lookback bar
    count to horizon_weeks * 5 trading days).
    """
    ...


def classify_candidate_tier(persisted_risk_result: str | None) -> int:
    """Per spec §E.4 Codex R2.M3:
      Tier 1 = bucket is INDEPENDENT of risk gate outcome
        (persisted_risk_result == 'pass' OR bucket was skip-by-TT-gate).
      Tier 2 = bucket DEPENDED on risk gate outcome
        (persisted_risk_result != 'pass' OR None — risk gate was load-bearing).

    Returns: 1 (tier-1 EXACT parity) or 2 (tier-2 CONDITIONAL via surrogate).
    """
    return 1 if persisted_risk_result == "pass" else 2
```

### §C.5 `sweep.py`

```python
"""V2 sweep orchestrator: per-(variable, sweep_point) live evaluate_one
recompute with cfg-substitution.

LOAD-BEARING caches (per Codex M4):
  - Per-eval_run BatchContext: keyed on (eval_run_id, horizon_weeks).
  - Per-TICKER OHLCV: keyed on ticker; full-history frame; in-memory slice
    per (ticker, asof_date) combo as needed.

Per-candidate failure isolation (cumulative T2.SB5 gotcha): 3 modes
  - OhlcvCoverageError → ohlcv_coverage_skip_count++
  - OutOfRangeSubstitutionError → out_of_range_skip_count++
  - any other Exception → evaluation_error_skip_count++ + WARNING log

vcp.watch_max_fails special-case (per OQ-11 + §E.3): mirrors V1's
_bucket_for_substituted watch_max_fails branch end-to-end against V2's
LIVE-recomputed Result tuples (NOT persisted candidate_criteria rows).
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from research.harness.aplus_sensitivity.variables import SweepVariable
from research.harness.aplus_v2_ohlcv_evaluator.context_builder import (
    CandidateRow,
    EvalRunCohort,
)
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import BothExistDiagnostic
from swing.config import Config

_ALLOWED_KINDS_V2: frozenset[str] = frozenset(
    {"gate", "threshold_additive", "threshold_multiplicative"}
)


@dataclass(frozen=True)
class SweepEntryV2:
    """One row in the V2 sensitivity matrix.

    Inherits V1 9-field shape + 3 NEW skip-count fields per spec §D.3
    + Expansion #11 taxonomy-propagation discipline.

    `kind` runtime-validated in __post_init__ per cumulative gotcha
    "Literal[...] type hints are NOT runtime-enforced".
    """
    variable_name: str
    kind: str
    sweep_point: float | int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    delta_aplus: int
    delta_watch: int
    out_of_range_skip_count: int  # NEW vs V1
    ohlcv_coverage_skip_count: int  # NEW vs V1 — SCALAR per V2 invocation (Codex R1.M3)
    evaluation_error_skip_count: int  # NEW vs V1

    def __post_init__(self) -> None:
        if self.kind not in _ALLOWED_KINDS_V2:
            raise ValueError(
                f"SweepEntryV2.kind must be one of {sorted(_ALLOWED_KINDS_V2)}, "
                f"got {self.kind!r}"
            )


@dataclass(frozen=True)
class FlippedCandidate:
    """Per-flipped-candidate provenance for drill-down section (spec §G.2).

    Fields:
      ticker, eval_run_id, data_asof_date: candidate identification.
      old_bucket, new_bucket: 'aplus'/'watch'/'skip'/'excluded' or
        'ohlcv_coverage_skip'/'out_of_range_skip'/'evaluation_error_skip'.
      old_criterion_failure: per-criterion attribution string ('<criterion_name>
        value=<v> rule=<r>') or '(none)' if old_bucket was already aplus.
      bucket_via_surrogate: per OQ-15 — True when current_equity was a
        surrogate (no historical snapshot found at eval_run's asof_date).
    """
    ticker: str
    eval_run_id: int
    data_asof_date: str  # ISO; for output rendering
    sweep_point: float | int
    old_bucket: str
    new_bucket: str
    old_criterion_failure: str
    bucket_via_surrogate: bool


@dataclass(frozen=True)
class BaselineParityReport:
    """V1↔V2 baseline parity (current-value sweep point) per spec §E.4."""
    tier1_match: bool  # EXACT match required; blocking
    tier1_mismatch_candidates: tuple[str, ...]  # (ticker, eval_run_id) on mismatch
    tier2_match_count: int
    tier2_mismatch_count: int
    tier2_via_surrogate_count: int


@dataclass(frozen=True)
class SweepResultV2:
    """Top-level V2 sweep result."""
    eval_runs_window: int
    eval_run_id_range: tuple[int, int]
    total_candidates: int
    universe_size: int
    v2_universe_hash: str
    entries: tuple[SweepEntryV2, ...]
    flipped: tuple[FlippedCandidate, ...]
    baseline_parity: BaselineParityReport
    ohlcv_coverage_skip_count: int  # scalar per V2 invocation
    universe_skipped_ticker_count: int
    both_exist_diagnostic: BothExistDiagnostic
    runtime_seconds: float
    truncated_by_runtime_cap: bool


def run_v2_sweep(
    conn: sqlite3.Connection,
    *,
    variables: tuple[SweepVariable, ...],
    cfg: Config,
    cache_dir: Path,
    eval_runs_window: int = 20,
    min_universe_size: int = 100,
    max_runtime_seconds: float | None = None,
) -> SweepResultV2:
    """Run the V2 1D sensitivity sweep with live OHLCV recompute.

    Args:
      conn: sqlite3 read-only connection against operator's swing-data/swing.db.
      variables: from enumerate_variables(cfg) (V1 module).
      cfg: production cfg from Config.from_defaults().
      cache_dir: cfg.paths.prices_cache_dir (Shape A parquet location; per
        swing/config.py:17 + constructed at swing/config.py:456 — Codex R1.M2
        RESOLVED; `cfg.archive` only holds `archive_history_days`).
      eval_runs_window: last N eval_runs (default 20; max 100; mirror V1).
      min_universe_size: RS universe validation threshold (default 100).
      max_runtime_seconds: optional cap (per OQ-9). When elapsed wallclock
        exceeds cap, sweep aborts mid-loop + sets truncated_by_runtime_cap=True
        on the returned result; partial entries are returned for variables
        completed so far.

    Returns: SweepResultV2 with one SweepEntryV2 per (variable, sweep_point) +
      drill-down + baseline parity + diagnostics.

    Empty-DB / no-eval-runs short-circuit (Codex R3.M3 + R4.M2 RESOLVED —
    mirrors V1 precedent at `research/harness/aplus_sensitivity/sweep.py:81`):
    when `fetch_eval_runs(conn, eval_runs_window=N)` returns an empty list, V2
    returns an empty `SweepResultV2(eval_runs_window=N, eval_run_id_range=(0, 0),
    total_candidates=0, universe_size=0, v2_universe_hash="empty_no_eval_runs",
    entries=(), flipped=(),
    baseline_parity=BaselineParityReport(tier1_match=True, tier1_mismatch_candidates=(),
    tier2_match_count=0, tier2_mismatch_count=0, tier2_via_surrogate_count=0),
    ohlcv_coverage_skip_count=0, universe_skipped_ticker_count=0,
    both_exist_diagnostic=BothExistDiagnostic(), runtime_seconds=<elapsed>,
    truncated_by_runtime_cap=False)` WITHOUT invoking `fetch_candidates`,
    `load_validated_rs_universe`, OR building any `EvalRunCohort`. Codex R4.M2
    RESOLVED: ALL counts are sentinel zeros + empty diagnostics because no
    universe / OHLCV / cohort work happens. The pre-R4 docstring's
    `universe_size=<resolved>` + `universe_skipped_ticker_count=<resolved>`
    framing was inconsistent — both are produced by BatchContext / OHLCV
    reconstruction, neither of which fires in the empty-DB case. Mock-asserted
    in T-V2.2 test #17 (moved from T-V2.1.3 per Codex R4.M1 since
    `run_v2_sweep` is introduced at T-V2.2 not T-V2.1).
    """
    ...
```

### §C.6 `output.py`

```python
"""V2 sensitivity output formatters: CSV + markdown analysis.

ASCII-only output per Windows cp1252 stdout safety lesson (cumulative
CLAUDE.md gotcha). All emitted text — both CSV cells AND markdown body —
must be cp1252-encodable. Tests verify via text.encode("cp1252").

Empty-state representation: '(none)' literal string in drill-down /
flipped-candidate sections; per cumulative T3.SB3 lesson "Audit envelope
empty-state representation must be uniform".
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from research.harness.aplus_v2_ohlcv_evaluator.sweep import SweepResultV2

_CSV_HEADERS_V2 = (
    "variable_name", "kind", "sweep_point",
    "aplus_count", "watch_count", "skip_count", "excluded_count",
    "delta_aplus", "delta_watch",
    "out_of_range_skip_count", "ohlcv_coverage_skip_count",
    "evaluation_error_skip_count",
)


def write_sensitivity_csv_v2(result: SweepResultV2, path: Path) -> None:
    """Write 12-column CSV per spec §G.1.

    Per Expansion #11 taxonomy-propagation discipline, `kind` is the second
    column (immediately after variable_name).
    """
    ...


def write_sensitivity_markdown_v2(result: SweepResultV2, path: Path) -> None:
    """Write markdown analysis report per spec §G.

    Sections (in order):
      1. Header (generated time + eval_runs window + total candidates + V2 universe size + v2_universe_hash + ohlcv_coverage_skip_count + universe_skipped_ticker_count + runtime_seconds + truncated_by_runtime_cap)
      2. Headline (top binding variables by marginal A+ count per loosening unit per §G.1)
      3. V1↔V2 parity section (CRITERION DRIFT alert on tier-1 mismatch per §G.3)
      4. Both-exist warning banner (when both_exist_diagnostic.count > 0 per §G; per OQ-18 + Codex R4.M1)
      5. Sensitivity matrix (12 cols per spec §G.1)
      6. Per-variable drill-down (per §G.2; bucket_via_surrogate flag per OQ-15)
      7. Notes (per-variable scope-reduction + tier-2 surrogate count + OQ-15+OQ-18 caveats)
      8. Manifest (both_exist_shape_a_wins_count + accepted ticker counts + tier-1/tier-2 split + memory peak from tracemalloc per Codex R3.m3)
    """
    ...
```

### §C.7 `run.py`

```python
"""V2 OHLCV harness CLI entry point.

Invoke via `python -m research.harness.aplus_v2_ohlcv_evaluator.run --db PATH
--eval-runs N --output-dir DIR` OR via `swing diagnose aplus-sensitivity-v2`
which delegates here.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.harness.aplus_sensitivity.variables import enumerate_variables
from research.harness.aplus_v2_ohlcv_evaluator.output import (
    write_sensitivity_csv_v2,
    write_sensitivity_markdown_v2,
)
from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
from swing.config import Config


def run_harness(
    *,
    db_path: Path,
    eval_runs: int,
    output_dir: Path,
    variables_filter: tuple[str, ...] | None = None,
    min_universe_size: int = 100,
    max_runtime_seconds: float | None = None,
) -> tuple[Path, Path]:
    """Run the V2 sweep + emit CSV + markdown into output_dir.

    Returns: (md_path, csv_path).

    Validates:
      eval_runs in [1, 100] → ValueError (wrapped to ClickException by CLI).
      min_universe_size >= 1 → ValueError.
      max_runtime_seconds None or > 0 → ValueError.
      variables_filter: subset of enumerate_variables(cfg) names → ValueError
        on unknown names with the unknown names enumerated in the message.

    DB connection (Codex R2.M2 RESOLVED + R3.m2 path-escape-safe RESOLVED):
    opens via URI mode `mode=ro` so any accidental INSERT/UPDATE/CREATE from
    the V2 module set raises `sqlite3.OperationalError: attempt to write a
    readonly database`. Defense-in-depth atop V2-side read-only invariant
    per spec §A.1. V1 precedent at `research/harness/aplus_sensitivity/run.py:41`
    uses the plain non-URI form; V2 deliberately upgrades to URI ro.

    Path-escape safety (R3.m2): use `db_path.resolve().as_uri()` which
    properly URI-encodes filesystem paths containing `?`, `#`, spaces, or
    other URI-sensitive characters. Naive f-string interpolation breaks
    for such paths.

    ```python
    db_uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    ```

    Discriminating test (T-V2.4 #11): plant DB at a path containing a space
    (Windows operator path quirk) + assert connection succeeds + INSERT
    raises sqlite3.OperationalError "readonly".
    """
    ...


def main(argv: list[str] | None = None) -> int:
    """argparse main for direct `python -m` invocation."""
    ...
```

---

## §D SQL skeleton verification (Expansion #4 refinement BINDING)

Per NEW gotcha #18 — for every SQL skeleton, enumerate (a) consumer's row-set scope; (b) JOIN-cardinality; (c) downstream sufficiency; (d) post-mutation re-check.

### §D.1 SQL skeleton #1: last N eval_runs

**Binding NOTE (Codex R1.M1 RESOLVED)**: Python's `sqlite3` cannot bind a list/tuple into a single `IN` placeholder. The skeletons below use `?` (positional) placeholders; the LIMIT param is bound as a single integer. SQL skeleton #2 (below) uses dynamic `?` placeholder expansion mirroring V1 at `research/harness/aplus_sensitivity/sweep.py:89-95`:

```python
placeholders = ",".join("?" for _ in eval_run_ids)
sql = f"... WHERE c.evaluation_run_id IN ({placeholders}) ..."
```

```sql
SELECT id, data_asof_date
  FROM evaluation_runs
  ORDER BY id DESC
  LIMIT ?;
```

Verified: `evaluation_runs.id` + `evaluation_runs.data_asof_date` exist at `swing/data/migrations/0001_phase1_initial.sql:10-12`.

- (a) Row-set scope: per-eval_run (1 row = 1 eval_run; N rows for N eval_runs).
- (b) JOIN-cardinality: N/A (no JOINs).
- (c) Downstream sufficiency: V2's `fetch_eval_runs` returns `[(eval_run_id, parsed_date)]`. The consumer is the eval-run iteration in `build_eval_run_cohort` (per-eval_run BatchContext key) + the candidate fetch's `WHERE evaluation_run_id IN (?, ?, ...)` dynamic-positional-placeholder clause per Codex R1.M1 + R2.m1 RESOLVED. Both consumers need only id + asof_date. SUFFICIENT.
- (d) Post-mutation re-check: V2 is READ-ONLY; no mutation. N/A.

Per cumulative gotcha #12: TEXT `data_asof_date` → `date.fromisoformat()` via `parse_asof_date` helper raises typed `MalformedAsofDateError` on malformed input.

### §D.2 SQL skeleton #2: candidates + persisted risk_feasibility

```sql
-- placeholders = ",".join("?" for _ in eval_run_ids); positional bind via params=eval_run_ids
SELECT c.id, c.ticker, c.bucket, er.data_asof_date,
       cc_risk.result AS persisted_risk_result
  FROM candidates c
  JOIN evaluation_runs er ON er.id = c.evaluation_run_id
  LEFT JOIN candidate_criteria cc_risk
    ON cc_risk.candidate_id = c.id
   AND cc_risk.layer = 'risk'
   AND cc_risk.criterion_name = 'risk_feasibility'
  WHERE c.evaluation_run_id IN (?, ?, ?, ...)   -- placeholder count = len(eval_run_ids)
  ORDER BY er.id DESC, c.ticker ASC;
```

Discriminating test per Codex R1.M1 RESOLVED: `test_fetch_candidates_handles_multi_eval_run_IN_clause` plants 3 eval_runs with 1 candidate each + invokes `fetch_candidates(conn, eval_run_ids=[1, 2, 3], ...)` + asserts all 3 candidates returned (would fail with sqlite3 `ProgrammingError` if the implementation used a single `:eval_run_ids` placeholder bound to a list).

Verified: `candidates.id` + `.ticker` + `.bucket` + `.evaluation_run_id` exist at `0001_phase1_initial.sql:24-42`; `candidate_criteria.candidate_id` + `.criterion_name` + `.layer` + `.result` exist at `0001_phase1_initial.sql:48-56`.

- (a) Row-set scope: per-candidate. For S3's universe: 5681 rows for 63 eval_runs (avg ~90 candidates per eval_run).
- (b) JOIN-cardinality:
  - `candidates JOIN evaluation_runs ON er.id = c.evaluation_run_id`: 1:1 (each candidate has exactly 1 evaluation_run; `evaluation_run_id INTEGER NOT NULL REFERENCES evaluation_runs(id)` per `0001_phase1_initial.sql:26`).
  - `candidates LEFT JOIN candidate_criteria cc_risk ON cc_risk.candidate_id = c.id AND cc_risk.layer = 'risk' AND cc_risk.criterion_name = 'risk_feasibility'`: 1:0-or-1 (PK on candidate_criteria is `(candidate_id, criterion_name)` per `0001_phase1_initial.sql:55`; AT MOST one 'risk_feasibility' row per candidate). LEFT JOIN handles missing row (legacy fixtures; pre-risk-criterion data) → `persisted_risk_result IS NULL` → V2 tier-2 (conservative) per Codex R2.M3 + §E.4.
  - Combined: 1:1 (one row per candidate). NO row inflation. NO DISTINCT needed.
- (c) Downstream sufficiency: walk consumer logic:
  - `candidate_id` + `ticker`: needed for OHLCV slicing + per-candidate failure isolation key.
  - `bucket` (persisted): needed for V1↔V2 baseline parity invariant per §E.4.
  - `data_asof_date`: needed for OHLCV slicing AND for keying into per-eval_run BatchContext cache.
  - `persisted_risk_result`: needed for tier-1/tier-2 classification per §E.4 + Codex R2.M3.
  - SUFFICIENT for all downstream consumers (sweep.py per-(variable, sweep_point) iteration + baseline parity report + drill-down).
- (d) Post-mutation re-check: V2 is READ-ONLY. N/A.

Per cumulative Expansion #8 (SQL aggregation UNIT audit): NO `COUNT/SUM/GROUP BY`. Pure row-fetcher. UNIQUE constraint at `(evaluation_run_id, ticker)` per `0001_phase1_initial.sql:41` guarantees per-row uniqueness; no DISTINCT needed.

### §D.3 No SQL skeleton #3 needed

V2 reads `account_equity_snapshots` via the production repo function `swing.data.repos.account_equity_snapshots.get_latest_snapshot_on_or_before(conn, asof_date=<ISO>)` + `list_snapshots(conn, limit=1)` — NOT raw SQL. The repo function is the source-of-truth for the source-ladder precedence (`schwab_api > tos_csv > manual` per `swing/data/repos/account_equity_snapshots.py:38-42`). V2 imports + invokes the repo function directly; no SQL skeleton refactor required.

---

## §E Production function signature verification (Expansion #2 refinement BINDING)

Per NEW gotcha #17 — grep every production-function reference in the plan + verify (a) signature; (b) side-effect contract; (c) error semantics; (d) L2 LOCK preservation. Use `inspect.signature()` in discriminating tests where feasible.

### §E.1 `swing.evaluation.evaluator.evaluate_one`

Verified at `swing/evaluation/evaluator.py:35-107`:

```python
def evaluate_one(ctx: CandidateContext) -> Candidate:
    """Run all criteria on one ticker, determine bucket, return a Candidate."""
```

- (a) Signature: `(ctx: CandidateContext) -> Candidate`. Single positional arg.
- (b) Side-effect contract: PURE function. No DB writes, no I/O. Internally calls `trend_template.evaluate(ctx)`, `ma_stack_short.evaluate(ctx)`, `prior_trend.evaluate(ctx)`, `proximity.evaluate(ctx)`, `adr.evaluate(ctx)`, `pullback.evaluate(ctx)`, `tightness.evaluate(ctx)`, `vcp.evaluate(ctx)`, `orderliness.evaluate(ctx)`, `risk_feasibility.evaluate(ctx)`, `compute_rs(...)`, `bucket_for(...)`. All criteria run UNCONDITIONALLY (no path through evaluator where only some criteria run per OQ-13 + Codex R1.M3 LOCK).
- (c) Error semantics: May raise on malformed `ctx.ohlcv` (insufficient bars; missing columns); V2 wraps with per-candidate try/except per spec §D.4.
- (d) L2 LOCK: `evaluate_one` consumes `ctx.ohlcv` as a pre-loaded DataFrame; does NOT fetch. SAFE.

Discriminating test: `test_evaluate_one_signature_unchanged_via_inspect_signature` — assert `inspect.signature(evaluate_one).parameters.keys() == ['ctx']`. Per Codex R1.M5 RESOLVED: do NOT assert `inspect.signature(evaluate_one).return_annotation == Candidate` (production uses `from __future__ import annotations` at `swing/evaluation/evaluator.py:2`, so the raw annotation is a STRING form `'Candidate'`, not the class object). Either skip the return-annotation assertion OR use `typing.get_type_hints(evaluate_one)` which resolves string annotations to class objects. Recommended discriminating-test shape:
```python
import inspect, typing
from swing.evaluation.evaluator import evaluate_one
from swing.data.models import Candidate
assert list(inspect.signature(evaluate_one).parameters.keys()) == ["ctx"]
hints = typing.get_type_hints(evaluate_one)
assert hints.get("return") is Candidate
```
Lives in `tests/research/test_aplus_v2_ohlcv_context_builder.py` (defensive test against future production drift).

### §E.2 `swing.evaluation.scoring.bucket_for`

Verified at `swing/evaluation/scoring.py:13-39`:

```python
def bucket_for(
    trend_template_results: Sequence[Result],
    vcp_results: Sequence[Result],
    risk_results: Sequence[Result],
    config: Config,
) -> str:
```

- (a) Signature: 4 positional args: tt_results, vcp_results, risk_results, config.
- (b) Side-effect contract: PURE. Returns 'aplus'/'watch'/'skip'.
- (c) Error semantics: No raises; defensive iteration. Hardcoded `vcp_fails <= 2` at line 37 per spec §E.3 / OQ-11 (V2 special-cases this in sweep.py).
- (d) L2 LOCK: PURE function; no I/O. SAFE.

Discriminating test: `test_bucket_for_signature_unchanged_via_inspect_signature` — defensive test in `tests/research/test_aplus_v2_ohlcv_sweep.py`.

### §E.3 `swing.evaluation.rs.load_universe`

Verified at `swing/evaluation/rs.py:22-42`:

```python
def load_universe(path: Path) -> Universe:
    """Parse an RS universe CSV. First non-comment line is the header 'ticker'."""
```

- (a) Signature: `(path: Path) -> Universe` where `Universe(tickers: tuple[str, ...], version: str)`. `tickers` is `tuple(sorted(set(tickers)))` (post-dedup).
- (b) Side-effect contract: READS file at `path` only. NO write. NO fetch.
- (c) Error semantics:
  - `path.read_text(encoding="utf-8")` → propagates FileNotFoundError + PermissionError + UnicodeDecodeError (V2 wraps to `MissingRsUniversePathError`).
  - `raise ValueError(f"Expected 'ticker' header, got {stripped!r}")` on malformed header (V2 catches + wraps to `InvalidRsUniverseError`).
  - SILENT acceptance of empty universe (no min-size check) — V2 layers `EmptyRsUniverseError` atop.
  - SILENT acceptance of shape-invalid tickers (no regex check) — V2 layers shape regex per Codex R3.M2.
- (d) L2 LOCK: PURE file read; no fetch. SAFE.

Discriminating test: `test_load_universe_signature_unchanged_via_inspect_signature` — defensive test in `tests/research/test_aplus_v2_ohlcv_context_builder.py`.

### §E.4 `swing.evaluation.rs.compute_rs`

Verified at `swing/evaluation/rs.py:52-87`:

```python
def compute_rs(
    ticker: str,
    returns_12w_by_ticker: dict[str, float],
    universe_tickers: tuple[str, ...],
    *,
    spy_return: float,
) -> RSResult:
```

- (a) Signature: 3 positional + 1 keyword-only (`spy_return`; note the production kwarg name is `spy_return`, NOT `spy_return_12w` which is the BatchContext field name). V2's `evaluate_one(ctx)` invocation hits `compute_rs(ctx.ticker, ctx.batch.returns_12w_by_ticker, ctx.batch.universe_tickers, spy_return=ctx.batch.spy_return_12w)` per `swing/evaluation/evaluator.py:79-84`; V2 does NOT call `compute_rs` directly (production evaluator handles it transparently).
- (b) Side-effect contract: PURE. Returns `RSResult(method, rank, return_vs_spy)`.
- (c) Error semantics: No raises; returns `RSResult(method='unavailable', ...)` for missing data.
- (d) L2 LOCK: PURE. SAFE.

### §E.5 `swing.data.repos.account_equity_snapshots.get_latest_snapshot_on_or_before`

Verified at `swing/data/repos/account_equity_snapshots.py:130-181`:

```python
def get_latest_snapshot_on_or_before(
    conn: sqlite3.Connection,
    *,
    asof_date: str,
    with_provenance: bool = False,
) -> (
    AccountEquitySnapshot
    | tuple[AccountEquitySnapshot, list[AccountEquitySnapshot]]
    | None
):
```

- (a) Signature: `(conn, *, asof_date: str, with_provenance: bool = False)` — `asof_date` is keyword-only AND `str` (ISO YYYY-MM-DD) per repo convention.
- (b) Side-effect contract: PURE READ (SELECT-only inside caller's transaction). NO write; NO commit.
- (c) Error semantics: Returns `None` when no snapshot exists at-or-before asof_date. V2 falls back to `list_snapshots(conn, limit=1)[0]` per OQ-15.
- (d) L2 LOCK: READS SQLite only. No external API. SAFE.

Discriminating test: `test_get_latest_snapshot_on_or_before_signature_unchanged_via_inspect_signature` — defensive test in `tests/research/test_aplus_v2_ohlcv_context_builder.py`.

### §E.6 `swing.data.ohlcv_archive.read_or_fetch_archive` — NEGATIVE verification (V2 does NOT call)

Verified at `swing/data/ohlcv_archive.py:172-251`:

```python
def read_or_fetch_archive(
    ticker: str,
    *,
    end_date: date,
    cache_dir: Path,
    archive_history_days: int,
) -> pd.DataFrame | None:
```

- (a) Signature: NO `prefer_source` kwarg (OQ-1 + OQ-12 original proposal not implementable per Codex R1.M1).
- (b) Side-effect contract: **ACTIVELY FETCHES from yfinance on cache-miss / stale-archive** per lines 222-237 + 242-251. Fetch writes archive (mutation). Per Codex R1.M2 — incompatible with V2 reproducibility.
- (c) Error semantics: Returns `None` on empty fetch result (with archive-as-fallback per Codex R2 Major 2 transient defense).
- (d) L2 LOCK: WOULD CALL `_yf_download_window` → yfinance HTTP call → mutates archive.

**V2 dispatch MUST NOT invoke this function** per OQ-16 LOCK. V2's `ohlcv_reader.py` is the V2-side replacement. Discriminating test: `test_v2_module_set_does_NOT_import_read_or_fetch_archive` — grep `research/harness/aplus_v2_ohlcv_evaluator/` for `read_or_fetch_archive` → assert ZERO matches. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`.

Defensive Expansion #2 refinement test: `test_read_or_fetch_archive_has_no_prefer_source_kwarg` — `assert "prefer_source" not in inspect.signature(read_or_fetch_archive).parameters` — guards against future production refactor that ADDS a `prefer_source` kwarg (which would mislead a maintainer into thinking V2 could route through the production function). Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`.

### §E.7 `swing.config.Config.from_defaults`

Verified existence per V1 precedent at `research/harness/aplus_sensitivity/run.py:39`:

```python
cfg = Config.from_defaults()
```

- (a) Signature: classmethod; no args.
- (b) Side-effect contract (Codex R2.M3 + R3.M2 RESOLVED):
  - Reads tracked-repo `swing.config.toml` ONLY at `swing/config.py:399-407` via `open()` at `swing/config.py:437-438` (Codex R3.M2 RESOLVED — initial R2.M3 fix incorrectly claimed user-config cascade; `from_defaults` does NOT invoke `swing/config_overrides.py` user-config layer).
  - The tracked `swing.config.toml` explicitly DROPS sensitive fields at TWO ranges (Codex R4.m1 + R5.m1 RESOLVED): `swing/config.py:466-467` (`raw_finviz.pop("token", None)`; `raw_finviz.pop("screen_query", None)`) AND `swing/config.py:482-483` (`raw_schwab.pop("client_id", None)`; `raw_schwab.pop("client_secret", None)`). The Schwab `refresh_token` (banked separately in `~/swing-data/schwab-tokens.{env}.db` per existing Schwab tokens DB gotcha — NOT in `swing.config.toml` at all) is irrelevant here. Operator-secret access (Finviz / Schwab API client credentials stored in `user-config.toml`) requires the separate `config_overrides.py` cascade which `from_defaults` does NOT invoke.
  - Net: V2's `Config.from_defaults()` invocation reads ONLY the tracked-repo `swing.config.toml`. NO operator secrets touched. NO `user-config.toml` read.
- (c) Error semantics: may raise `FileNotFoundError` (tracked config absent) / `tomllib.TOMLDecodeError` (malformed; Codex R3.m1 RESOLVED — stdlib `tomllib` per `swing/config.py:5`, NOT `tomli`) / `KeyError` (missing required section per `swing/config.py:446`) — V2 propagates to CLI ClickException wrapping per cumulative T-A.1.5b lesson.
- (d) L2 LOCK: reads ONLY tracked-repo `swing.config.toml`; NO external API; NO `swing/data/ohlcv_archive` import. SAFE.

---

## §F L2 LOCK reinforcement (3 BINDING discriminating tests per brief §3.5)

The L2 LOCK invariant (ZERO new Schwab API calls; ZERO reads of `{ticker}.schwab_api.parquet`) MUST be preserved + REINFORCED. V2 dispatch is the FIRST research-branch arc post-Phase-13-FULLY-CLOSED that touches OHLCV reading machinery; defense-in-depth via 3 BINDING tests:

### §F.1 Test 1: File-open mock asserts schwab_api parquet never opened

**File:** `tests/research/test_aplus_v2_ohlcv_reader.py`

```python
def test_v2_ohlcv_reader_never_opens_schwab_api_parquet(tmp_path, monkeypatch):
    """L2 LOCK reinforcement test #1: file-open mock asserts V2 process
    NEVER opens {TICKER}.schwab_api.parquet for any synthetic test ticker.

    Per Codex R1.M4 RESOLVED: spy on multiple file-open boundaries
    (pd.read_parquet + pathlib.Path.open + builtins.open + pyarrow) to catch
    any indirect path that bypasses pandas. Brief §3.5 specified file-open
    mock at Path.open or equivalent boundary; pd.read_parquet alone is too
    narrow.
    """
    import builtins
    import pathlib
    # Plant both files for a synthetic ticker
    synth = "ZZSYNTH"
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250)
    _make_shape_a_parquet(schwab_path, n_bars=300)

    # Spy on multiple boundaries; each records every path opened
    opened_paths: list[str] = []
    real_read_parquet = pd.read_parquet
    real_path_open = pathlib.Path.open
    real_builtins_open = builtins.open

    def _spy_read_parquet(path, *args, **kwargs):
        opened_paths.append(str(path))
        return real_read_parquet(path, *args, **kwargs)

    def _spy_path_open(self, *args, **kwargs):
        opened_paths.append(str(self))
        return real_path_open(self, *args, **kwargs)

    def _spy_builtins_open(file, *args, **kwargs):
        opened_paths.append(str(file))
        return real_builtins_open(file, *args, **kwargs)

    monkeypatch.setattr("pandas.read_parquet", _spy_read_parquet)
    monkeypatch.setattr(pathlib.Path, "open", _spy_path_open)
    monkeypatch.setattr(builtins, "open", _spy_builtins_open)

    # pyarrow defense: if pyarrow.parquet.read_table is available, spy on it
    try:
        import pyarrow.parquet as pq
        real_read_table = pq.read_table
        def _spy_read_table(source, *args, **kwargs):
            opened_paths.append(str(source))
            return real_read_table(source, *args, **kwargs)
        monkeypatch.setattr("pyarrow.parquet.read_table", _spy_read_table)
    except ImportError:
        pass

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    df = read_yfinance_shape_a(synth, tmp_path)

    # Assert NO schwab_api path was opened on ANY boundary
    assert all("schwab_api" not in p for p in opened_paths), (
        f"V2 reader opened schwab_api parquet on at least one boundary: "
        f"{[p for p in opened_paths if 'schwab_api' in p]} "
        f"(all spied paths: {opened_paths})"
    )
    # Assert yfinance path WAS opened
    assert any(p.endswith(f"{synth}.yfinance.parquet") for p in opened_paths)
```

### §F.2 Test 2: Import-graph mock asserts NO schwab / yfinance imports

**File:** `tests/research/test_aplus_v2_ohlcv_reader.py`

```python
def test_v2_module_set_does_NOT_import_schwab_or_yfinance(monkeypatch):
    """L2 LOCK reinforcement test #2: import-graph mock asserts V2 modules
    NEVER import any schwabdev / swing.integrations.schwab / yfinance /
    swing.data.ohlcv_archive symbol — directly OR indirectly.

    Codex R1.M3 RESOLVED: V2 must also block swing.data.ohlcv_archive (which
    imports yfinance at swing/data/ohlcv_archive.py:47); a V2 helper-reuse
    import there would silently pull yfinance into the process. Tested via
    BOTH (a) post-import sys.modules absence AND (b) source-file grep.
    """
    import sys
    # Remove cached V2 modules + cached forbidden modules to force fresh
    # import — verifies V2 import chain does NOT load any forbidden module
    # transitively.
    forbidden_modules = (
        "yfinance",
        "schwabdev",
        "swing.integrations.schwab",
        "swing.data.ohlcv_archive",
    )
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("research.harness.aplus_v2_ohlcv_evaluator"):
            del sys.modules[mod_name]
        for forbidden in forbidden_modules:
            if mod_name == forbidden or mod_name.startswith(forbidden + "."):
                del sys.modules[mod_name]

    # Plant sentinels that raise if any V2 module touches them
    class _NoImportSentinel:
        def __init__(self, name): self._name = name
        def __getattr__(self, attr):
            raise AssertionError(
                f"V2 module attempted to access {attr!r} on banned import "
                f"target {self._name!r}"
            )

    for forbidden in forbidden_modules:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))

    # Import all V2 modules — must NOT trigger any forbidden module load
    import research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader   # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.context_builder  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.sweep  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.output  # noqa: F401
    import research.harness.aplus_v2_ohlcv_evaluator.run  # noqa: F401

    # Defense-in-depth #1: post-import, confirm no forbidden module was loaded
    # to a real (non-sentinel) class. The sentinels remain in sys.modules; any
    # accidental `from yfinance import X` would have triggered AssertionError
    # via __getattr__ above. A direct `import yfinance` (no attribute access)
    # would have left the sentinel intact (still our object).
    for forbidden in forbidden_modules:
        loaded = sys.modules.get(forbidden)
        assert isinstance(loaded, _NoImportSentinel), (
            f"V2 import chain replaced sentinel for {forbidden!r} with real "
            f"module {type(loaded).__name__} (L2 LOCK violation: indirect "
            f"import path loaded the real module)"
        )

    # Defense-in-depth #2: grep source files for any banned import substring
    import pathlib
    v2_dir = pathlib.Path(__file__).resolve().parents[2] / "research" / "harness" / "aplus_v2_ohlcv_evaluator"
    banned_imports = (
        "import yfinance", "from yfinance",
        "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.",
        "import swing.data.ohlcv_archive",
    )
    for py_path in v2_dir.glob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        for banned in banned_imports:
            assert banned not in text, (
                f"V2 module {py_path.name} contains banned import substring "
                f"{banned!r} (L2 LOCK violation per Codex R1.M3)"
            )
```

### §F.3 Test 3: Byte-checksum discriminating fixture (both Shape A planted; V2 reads ONLY yfinance bytes)

**File:** `tests/research/test_aplus_v2_ohlcv_reader.py`

```python
def test_v2_reads_only_yfinance_bytes_when_both_shape_a_files_exist(tmp_path):
    """L2 LOCK reinforcement test #3: plant both schwab_api Shape A AND
    yfinance Shape A parquet files; assert V2 reads ONLY yfinance bytes
    via byte-checksum compare; assert V2 process NEVER reads schwab_api file.
    """
    synth = "ZZBOTH"
    # Distinct content per file so byte-checksum is distinguishable
    yfinance_path = tmp_path / f"{synth}.yfinance.parquet"
    schwab_path = tmp_path / f"{synth}.schwab_api.parquet"
    _make_shape_a_parquet(yfinance_path, n_bars=250, sentinel_close=100.0)
    _make_shape_a_parquet(schwab_path, n_bars=250, sentinel_close=999.0)

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic, read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    df = read_yfinance_shape_a(synth, tmp_path, diagnostic=diag)

    # Assert V2 read yfinance content (close == 100.0, NOT 999.0)
    assert df["Close"].iloc[-1] == 100.0, (
        f"V2 read schwab_api content (close={df['Close'].iloc[-1]}); "
        f"expected yfinance content (close=100.0)"
    )

    # Assert diagnostic surface tracked the both-exist case
    assert diag.count == 0, (
        "Both-exist diagnostic should NOT trigger for {synth}.yfinance.parquet "
        "vs {synth}.schwab_api.parquet (Shape A pair; not Shape A vs legacy)"
    )
```

Note: the both-exist DIAGNOSTIC fires on yfinance Shape A vs LEGACY `{ticker}.parquet` (per OQ-18); NOT on yfinance Shape A vs schwab_api Shape A (those are different sources at the same Shape A level, NOT both-exist of "yfinance vs legacy"). The diagnostic test for OQ-18 both-exist is separate (see T-V2.1.1 step list).

---

## §G Per-task acceptance criteria + bite-sized step structure

### §G.0 Commit cadence (Codex R1.M6 RESOLVED — BINDING per dispatch brief §2.1)

Dispatch brief §2.1 specifies per-sub-bundle commit budgets (T-V2.1 ~10-15, T-V2.2 ~12-18, T-V2.3 ~8-12, T-V2.4 ~6-10, T-V2.5 ~6-10; **~42-65 total** across executing-plans phase). The task structures below enumerate **logical TDD slices**; the BINDING commit-cadence rule is:

**Each logical TDD slice (test + minimal implementation expansion + passing test) is ONE commit.**

For each task `T-V2.X.Y` with N tests in §G:
- Step "Write failing test" + "Run → verify fail" + "Implement minimal change" + "Run → verify pass" + **"Commit"** → ONE commit per test slice.
- Where tests share fixtures + a single implementation expansion (e.g., 4 substitute_cfg per-subsection tests in T-V2.1.2), implementer MAY consolidate to ONE commit per logical cluster — but each cluster's tests + impl must be in the same commit.
- The final per-task "Run all + ruff + commit" step shown explicitly below is the **task-wrap commit** (ruff + final cleanup + per-task documentation) AFTER all per-test slices have been committed.

Per-sub-bundle commit count breakdown (Codex R5.m3 RESOLVED — refreshed per §H R5 amendments):

| Sub-bundle | Tasks | Tests (§H) | Per-test slices | Task-wrap commits | Total commits |
|------------|-------|-----------|----------------|-------------------|---------------|
| T-V2.1 | T-V2.1.1 + T-V2.1.2 + T-V2.1.3 | ~14 + ~6 + ~18 = ~38 | ~7+4+12 = 23 commits (parametrize-consolidation) | 3 task-wraps | ~26 commits |
| T-V2.2 | T-V2.2 (1 mono-task; 17 sub-steps) | ~17 | ~14 commits (parametrize-consolidation for failure-isolation × 3 + cache bound pair) | 1 task-wrap | ~15 commits |
| T-V2.3 | T-V2.3 (1 mono-task; 12 sub-steps) | ~12 | ~10 commits | 1 task-wrap | ~11 commits |
| T-V2.4 | T-V2.4 (1 mono-task; 11 sub-steps) | ~11 | ~9 commits | 1 task-wrap | ~10 commits |
| T-V2.5 | T-V2.5 (1 mono-task; 6 sub-steps) | ~6 | ~6 commits | 1 task-wrap | ~7 commits |
| **Total** | | **~84 tests** (per §H R5 recalibration) | **~62 per-test commits** (parametrize-consolidation) | **7 task-wraps** | **~69 commits** with parametrize-consolidation; **~84-91 commits** at raw 1-commit-per-test ceiling |

This lands within / slightly above brief §2.1's projected ~42-65 commit range. Implementer guidance: tight parametrize-consolidation (the 4 substitute_cfg per-subsection variants in 1 commit; the 3 signature-lock tests in 1 commit; the 3 failure-isolation modes in 1 commit) lands at ~50-60 commits — comfortably in the brief's range. Raw 1-commit-per-test lands at ~84-91. Final cadence is implementer's call.

**Implementer guidance**: every "Step N: Run test to verify pass" followed by another "Step M: Write failing test" implies an IMPLICIT commit between Step N and Step M. The `### Task` blocks below explicitly enumerate task-wrap commits but elide per-test commits for readability; treat each TDD slice as its own commit per cumulative TDD discipline (per `superpowers:test-driven-development` skill + V1 precedent at every prior phase).

---


### Task T-V2.1.1: NEW `ohlcv_reader.py` module

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/__init__.py`
- Create: `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py`
- Create: `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`
- Test: `tests/research/test_aplus_v2_ohlcv_reader.py`

- [ ] **Step 1: Write the failing test for primary Shape A read**

```python
# tests/research/test_aplus_v2_ohlcv_reader.py
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


def _make_shape_a_parquet(path: Path, n_bars: int = 250, sentinel_close: float = 100.0):
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


def test_read_yfinance_shape_a_returns_dataframe_with_capitalized_ohlcv(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZTEST.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    df = read_yfinance_shape_a("ZZTEST", tmp_path)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 250
    assert df.index.is_monotonic_increasing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py::test_read_yfinance_shape_a_returns_dataframe_with_capitalized_ohlcv -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'research.harness.aplus_v2_ohlcv_evaluator'`

- [ ] **Step 3: Create empty `__init__.py` + `exceptions.py`**

```python
# research/harness/aplus_v2_ohlcv_evaluator/__init__.py
"""V2 OHLCV criterion-evaluator harness — lifts the V1 LIMITATION at
research/harness/aplus_sensitivity/sweep.py:248-250 by substituting cfg
values one-at-a-time + invoking production evaluate_one(ctx) end-to-end.
"""
from __future__ import annotations

__version__ = "0.2.0"
```

```python
# research/harness/aplus_v2_ohlcv_evaluator/exceptions.py
"""Typed exceptions for the V2 OHLCV criterion-evaluator harness."""
from __future__ import annotations


class OhlcvCoverageError(Exception):
    pass


class MissingRsUniversePathError(Exception):
    pass


class EmptyRsUniverseError(Exception):
    pass


class InvalidRsUniverseError(Exception):
    pass


class PostCleanupUniverseTooSmallError(Exception):
    pass


class OutOfRangeSubstitutionError(Exception):
    pass


class MalformedAsofDateError(Exception):
    pass
```

- [ ] **Step 4: Implement minimal `read_yfinance_shape_a`**

```python
# research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError

_OHLCV_LOWER = ("open", "high", "low", "close", "volume")
_OHLCV_CAPITAL = ("Open", "High", "Low", "Close", "Volume")
_LOWER_TO_CAPITAL = dict(zip(_OHLCV_LOWER, _OHLCV_CAPITAL))


@dataclass
class BothExistDiagnostic:
    count: int = 0
    affected_tickers: list[str] = field(default_factory=list)


def read_yfinance_shape_a(
    ticker: str,
    cache_dir: Path,
    *,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    ticker_u = ticker.upper()
    yfinance_path = cache_dir / f"{ticker_u}.yfinance.parquet"
    legacy_path = cache_dir / f"{ticker_u}.parquet"
    yfinance_exists = yfinance_path.exists()
    legacy_exists = legacy_path.exists()

    if yfinance_exists and legacy_exists and diagnostic is not None:
        diagnostic.count += 1
        diagnostic.affected_tickers.append(ticker_u)

    if yfinance_exists:
        df = pd.read_parquet(yfinance_path)
        df = _normalize_shape_a(df)
    elif legacy_exists:
        df = pd.read_parquet(legacy_path)
        df = _normalize_legacy(df)
    else:
        raise OhlcvCoverageError(
            f"OHLCV archive missing for ticker={ticker_u!r}: neither "
            f"{yfinance_path.name} nor {legacy_path.name} exists at {cache_dir}"
        )
    return df


def _normalize_shape_a(df: pd.DataFrame) -> pd.DataFrame:
    """Shape A (lowercase OHLCV + asof_date column) → capitalized OHLCV +
    DatetimeIndex."""
    if "asof_date" not in df.columns:
        raise ValueError("Shape A parquet missing asof_date column")
    df = df.rename(columns=_LOWER_TO_CAPITAL)
    df["__dt__"] = pd.to_datetime(df["asof_date"])
    df = df.drop(columns=["asof_date"]).set_index("__dt__").sort_index()
    df.index.name = None
    return df[list(_OHLCV_CAPITAL)]


def _normalize_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """Legacy (capitalized OHLCV + DatetimeIndex) → already-canonical shape."""
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()
        for col in ("Date", "date", "index"):
            if col in df.columns:
                df["__dt__"] = pd.to_datetime(df[col])
                df = df.drop(columns=[col]).set_index("__dt__")
                df.index.name = None
                break
    df = df.sort_index()
    return df[[c for c in _OHLCV_CAPITAL if c in df.columns]]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py::test_read_yfinance_shape_a_returns_dataframe_with_capitalized_ohlcv -v`
Expected: PASS

- [ ] **Step 6: Add legacy fallback test**

```python
def test_read_yfinance_shape_a_falls_back_to_legacy_when_shape_a_absent(tmp_path):
    # Plant ONLY legacy file
    dates = pd.date_range(end="2026-04-30", periods=250, freq="B")
    df = pd.DataFrame({
        "Open": [100.0] * 250, "High": [101.0] * 250,
        "Low": [99.0] * 250, "Close": [100.0] * 250, "Volume": [1_000_000] * 250,
    }, index=dates)
    df.to_parquet(tmp_path / "ZZLEG.parquet")

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    result = read_yfinance_shape_a("ZZLEG", tmp_path)
    assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(result) == 250
```

- [ ] **Step 7: Run + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py::test_read_yfinance_shape_a_falls_back_to_legacy_when_shape_a_absent -v`
Expected: PASS

- [ ] **Step 8: Add both-exist diagnostic test**

```python
def test_read_yfinance_shape_a_both_exist_shape_a_wins_increments_diagnostic(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZBOTH.yfinance.parquet", n_bars=200, sentinel_close=100.0)
    # Legacy with DIFFERENT content
    dates = pd.date_range(end="2026-04-30", periods=400, freq="B")
    legacy_df = pd.DataFrame({
        "Open": [50.0] * 400, "High": [51.0] * 400,
        "Low": [49.0] * 400, "Close": [50.0] * 400, "Volume": [2_000_000] * 400,
    }, index=dates)
    legacy_df.to_parquet(tmp_path / "ZZBOTH.parquet")

    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
        BothExistDiagnostic, read_yfinance_shape_a,
    )
    diag = BothExistDiagnostic()
    result = read_yfinance_shape_a("ZZBOTH", tmp_path, diagnostic=diag)
    # Shape A wins per OQ-18 LOCK → result has 200 rows + close=100.0
    assert len(result) == 200
    assert result["Close"].iloc[-1] == 100.0
    # Diagnostic increments + records affected ticker
    assert diag.count == 1
    assert diag.affected_tickers == ["ZZBOTH"]
```

- [ ] **Step 9: Run + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py::test_read_yfinance_shape_a_both_exist_shape_a_wins_increments_diagnostic -v`
Expected: PASS

- [ ] **Step 10: Add 3 L2 LOCK reinforcement tests per §F.1 + §F.2 + §F.3**

Implement tests exactly as written in §F.1, §F.2, §F.3 above.

- [ ] **Step 11: Run L2 LOCK tests + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py -v -k "schwab or import or only_yfinance"`
Expected: PASS (3 tests)

- [ ] **Step 12: Add OhlcvCoverageError test**

```python
def test_read_yfinance_shape_a_raises_OhlcvCoverageError_when_neither_file_exists(tmp_path):
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a
    with pytest.raises(OhlcvCoverageError, match="ZZMISS"):
        read_yfinance_shape_a("ZZMISS", tmp_path)
```

- [ ] **Step 13: Add `read_yfinance_shape_a_sliced` + slice tests**

```python
def read_yfinance_shape_a_sliced(
    ticker: str,
    cache_dir: Path,
    *,
    asof_date: date,
    min_bars: int = 200,
    diagnostic: BothExistDiagnostic | None = None,
) -> pd.DataFrame:
    df = read_yfinance_shape_a(ticker, cache_dir, diagnostic=diagnostic)
    sliced = df.loc[df.index.date <= asof_date]
    if len(sliced) < min_bars:
        raise OhlcvCoverageError(
            f"OHLCV insufficient for ticker={ticker!r} at asof_date={asof_date}: "
            f"sliced={len(sliced)} < min_bars={min_bars}"
        )
    return sliced
```

```python
def test_read_yfinance_shape_a_sliced_includes_asof_date_bar_inclusive(tmp_path):
    _make_shape_a_parquet(tmp_path / "ZZSL.yfinance.parquet", n_bars=250)
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a_sliced
    asof = date(2026, 4, 30)
    result = read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date=asof)
    # Inclusive: last bar IS at asof_date
    assert result.index[-1].date() == asof


def test_read_yfinance_shape_a_sliced_raises_OhlcvCoverageError_below_min_bars(tmp_path):
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import OhlcvCoverageError
    _make_shape_a_parquet(tmp_path / "ZZSHRT.yfinance.parquet", n_bars=50)  # < 200
    from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import read_yfinance_shape_a_sliced
    with pytest.raises(OhlcvCoverageError, match="ZZSHRT"):
        read_yfinance_shape_a_sliced("ZZSHRT", tmp_path, asof_date=date(2026, 4, 30))
```

- [ ] **Step 14: Run all ohlcv_reader tests + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py -v`
Expected: ALL PASS (target ~12 tests)

- [ ] **Step 15: Add defensive Expansion #2 refinement test (read_or_fetch_archive signature lock)**

```python
def test_read_or_fetch_archive_has_no_prefer_source_kwarg():
    """Defensive test per NEW gotcha #17 (Expansion #2 refinement BINDING):
    if production refactor ever adds a `prefer_source` kwarg to
    read_or_fetch_archive, this test fires + flags that V2's read-only
    bypass justification (per OQ-16 LOCK) needs re-evaluation.
    """
    import inspect
    from swing.data.ohlcv_archive import read_or_fetch_archive
    params = inspect.signature(read_or_fetch_archive).parameters
    assert "prefer_source" not in params, (
        "Production read_or_fetch_archive now has a prefer_source kwarg; "
        "V2's bypass justification per OQ-16 LOCK requires re-evaluation. "
        "Update spec §F.1 + V2 OHLCV harness ohlcv_reader.py to consider "
        "routing through the production function."
    )


def test_v2_module_set_does_NOT_import_read_or_fetch_archive():
    """Companion to test_v2_module_set_does_NOT_import_schwab_or_yfinance —
    V2 modules MUST NOT import read_or_fetch_archive per OQ-16 LOCK.
    """
    import pathlib
    v2_dir = pathlib.Path(__file__).resolve().parents[2] / "research" / "harness" / "aplus_v2_ohlcv_evaluator"
    for py_path in v2_dir.glob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        assert "read_or_fetch_archive" not in text, (
            f"V2 module {py_path.name} contains forbidden reference to "
            f"read_or_fetch_archive (per OQ-16 LOCK + spec §F.1)"
        )
```

- [ ] **Step 16: Run + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py -v`
Expected: ALL PASS (~12 tests total)

- [ ] **Step 17: ruff + commit**

Run: `ruff check research/harness/aplus_v2_ohlcv_evaluator/ tests/research/test_aplus_v2_ohlcv_reader.py`
Expected: PASS (zero errors)

```bash
git add research/harness/aplus_v2_ohlcv_evaluator/__init__.py \
        research/harness/aplus_v2_ohlcv_evaluator/exceptions.py \
        research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py \
        tests/research/test_aplus_v2_ohlcv_reader.py
git commit -m "$(cat <<'EOF'
feat(research): V2 OHLCV harness T-V2.1.1 — ohlcv_reader + exceptions + L2 LOCK tests

Adds NEW read-only Shape A parquet wrapper at
research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py per spec §F.1 +
OQ-16 LOCK. Bypasses production swing.data.ohlcv_archive.read_or_fetch_archive
entirely (no `prefer_source` kwarg AND actively fetches yfinance on miss).
Legacy {ticker}.parquet fallback per Codex R2.M2; both-exist Shape A wins
unconditionally per OQ-18 LOCK with diagnostic surface per Codex R4.M1.
Column-case normalization (lowercase → capitalized) per Codex R2.C1.

Tests: ~12 covering primary read + legacy fallback + both-exist diagnostic +
OhlcvCoverageError raise paths + 3 L2 LOCK reinforcement tests per brief §3.5
(file-open mock + import-graph mock + byte-checksum) + 2 defensive tests per
NEW gotcha #17 Expansion #2 refinement BINDING.

NO Co-Authored-By footer per cumulative discipline (~439+ streak).
EOF
)"
```

### Task T-V2.1.2: NEW `cfg_substitution.py` module

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/cfg_substitution.py`
- Test: `tests/research/test_aplus_v2_ohlcv_cfg_substitution.py`

- [ ] **Step 1: Write failing test for known-subsection substitution**

```python
# tests/research/test_aplus_v2_ohlcv_cfg_substitution.py
import pytest

from swing.config import Config


def test_substitute_cfg_replaces_trend_template_field_in_isolation():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "trend_template.min_passes", 5)
    assert new_cfg.trend_template.min_passes == 5
    # All other fields unchanged
    assert new_cfg.trend_template.rising_ma_period_days == cfg.trend_template.rising_ma_period_days
    assert new_cfg.vcp == cfg.vcp
    assert new_cfg.risk == cfg.risk
    assert new_cfg.rs == cfg.rs
    # Original unchanged (immutability)
    assert cfg.trend_template.min_passes != 5  # default isn't 5 — but the assertion is "original not mutated"
```

- [ ] **Step 2: Run test → verify fail**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_cfg_substitution.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement substitute_cfg per §C.3**

Per §C.3 binding signature. Full implementation.

- [ ] **Step 4: Run test → verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_cfg_substitution.py -v`
Expected: PASS

- [ ] **Step 5: Add per-subsection tests (4 total: trend_template, vcp, risk, rs)**

```python
def test_substitute_cfg_replaces_vcp_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "vcp.adr_min_pct", 6.0)
    assert new_cfg.vcp.adr_min_pct == 6.0
    assert new_cfg.trend_template == cfg.trend_template


def test_substitute_cfg_replaces_risk_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "risk.max_risk_pct", 0.0075)
    assert new_cfg.risk.max_risk_pct == 0.0075
    assert new_cfg.vcp == cfg.vcp


def test_substitute_cfg_replaces_rs_field():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    new_cfg = substitute_cfg(cfg, "rs.rs_rank_min_pass", 60)
    assert new_cfg.rs.rs_rank_min_pass == 60
    assert new_cfg.trend_template == cfg.trend_template
```

- [ ] **Step 6: Add unknown-subsection error test**

```python
def test_substitute_cfg_raises_ValueError_on_unknown_subsection():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    with pytest.raises(ValueError, match="unknown cfg subsection 'fake'"):
        substitute_cfg(cfg, "fake.field", 1.0)
```

- [ ] **Step 7: Add type-preservation invariant test**

```python
def test_substitute_cfg_preserves_int_vs_float_types():
    cfg = Config.from_defaults()
    from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
    # Additive (int) sweep_value preserves int
    new_cfg = substitute_cfg(cfg, "trend_template.min_passes", 6)
    assert isinstance(new_cfg.trend_template.min_passes, int)
    # Multiplicative (float) sweep_value preserves float
    new_cfg2 = substitute_cfg(cfg, "vcp.adr_min_pct", 4.5)
    assert isinstance(new_cfg2.vcp.adr_min_pct, float)
```

- [ ] **Step 8: Run all + verify pass**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_cfg_substitution.py -v`
Expected: ALL PASS (~6 tests)

- [ ] **Step 9: ruff + commit**

```bash
ruff check research/harness/aplus_v2_ohlcv_evaluator/cfg_substitution.py tests/research/test_aplus_v2_ohlcv_cfg_substitution.py
git add research/harness/aplus_v2_ohlcv_evaluator/cfg_substitution.py \
        tests/research/test_aplus_v2_ohlcv_cfg_substitution.py
git commit -m "feat(research): V2 OHLCV harness T-V2.1.2 — cfg_substitution helper

Adds substitute_cfg(cfg, variable_name, sweep_value) -> Config via
dataclasses.replace per spec §D.2 + OQ-2 LOCK. vcp.watch_max_fails is NOT
routed through this helper — see sweep.py special-case per OQ-11.

Tests: ~6 covering 4 known subsections + unknown-subsection ValueError +
type-preservation invariant. NO Co-Authored-By footer per cumulative
discipline."
```

### Task T-V2.1.3: NEW `context_builder.py` module

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/context_builder.py`
- Test: `tests/research/test_aplus_v2_ohlcv_context_builder.py`

- [ ] **Step 1: Implement `parse_asof_date` helper + test (cumulative gotcha #12)**

```python
# test
def test_parse_asof_date_raises_MalformedAsofDateError_on_garbage():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import parse_asof_date
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import MalformedAsofDateError
    with pytest.raises(MalformedAsofDateError, match="malformed"):
        parse_asof_date("not-a-date")
    with pytest.raises(MalformedAsofDateError):
        parse_asof_date("")


def test_parse_asof_date_returns_date_for_valid_iso():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import parse_asof_date
    from datetime import date
    assert parse_asof_date("2026-04-30") == date(2026, 4, 30)
```

- [ ] **Step 2: Implement `load_validated_rs_universe` per spec §F.4 + Codex R2.M4 + R3.M2 + R4.M2**

Tests cover the 4 validation modes:
  - Non-empty + min-size → `EmptyRsUniverseError`
  - Shape-invalid >5% → `InvalidRsUniverseError` (lists first 20 invalid symbols per Codex R4.m1)
  - Shape-invalid ≤5% → warning + drop
  - Post-cleanup < min-size → `PostCleanupUniverseTooSmallError`
  - Duplicates → warning + drop

```python
def test_load_validated_rs_universe_raises_EmptyRsUniverseError_when_empty(tmp_path, monkeypatch):
    universe_csv = tmp_path / "empty_universe.csv"
    universe_csv.write_text("# version: test\nticker\n", encoding="utf-8")
    cfg = _cfg_with_universe_path(universe_csv)  # helper that overrides cfg.paths.rs_universe_path
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import EmptyRsUniverseError
    with pytest.raises(EmptyRsUniverseError):
        load_validated_rs_universe(cfg, min_universe_size=10)


def test_load_validated_rs_universe_raises_InvalidRsUniverseError_when_garbage_rate_exceeds_5pct(tmp_path):
    universe_csv = tmp_path / "garbage_universe.csv"
    universe_csv.write_text(
        "ticker\n" + "\n".join(["AAA"] * 50 + ["???garbage"] * 50) + "\n",
        encoding="utf-8",
    )
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import InvalidRsUniverseError
    with pytest.raises(InvalidRsUniverseError) as exc:
        load_validated_rs_universe(cfg, min_universe_size=80)
    # Per Codex R4.m1: rejected symbols enumerated in message (first 20)
    assert "???garbage" in str(exc.value)


def test_load_validated_rs_universe_raises_PostCleanupUniverseTooSmallError(tmp_path):
    universe_csv = tmp_path / "cleanup_too_small.csv"
    # 105 rows: 9 invalid (under 5% threshold of 6 = 9 rejected NOT raised),
    # wait — 9/105 = 8.6% > 5% so InvalidRsUniverseError fires first.
    # Reframe: 102 rows, 4 invalid (3.9% under 5% threshold), 8 duplicates of valid ones
    # Accepted = 102 - 4 - 8 = 90 unique. 90 < min_universe_size=100 → PostCleanupUniverseTooSmallError
    rows = [f"AAA{i}" for i in range(94)] + ["AAA0"] * 8 + ["???garbage"] * 4
    universe_csv.write_text("ticker\n" + "\n".join(rows) + "\n", encoding="utf-8")
    cfg = _cfg_with_universe_path(universe_csv)
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import load_validated_rs_universe
    from research.harness.aplus_v2_ohlcv_evaluator.exceptions import PostCleanupUniverseTooSmallError
    with pytest.raises(PostCleanupUniverseTooSmallError):
        load_validated_rs_universe(cfg, min_universe_size=100)
```

- [ ] **Step 3: Implement `fetch_eval_runs` + `fetch_candidates` SQL skeletons per §D.1 + §D.2**

Tests use an in-memory SQLite + fixture migrations:

```python
def test_fetch_eval_runs_returns_descending_id_order_with_parsed_dates(tmp_path):
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _seed_eval_runs(db_path, [(1, "2026-04-01"), (2, "2026-04-15"), (3, "2026-04-30")])
    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import fetch_eval_runs
    result = fetch_eval_runs(conn, eval_runs_window=2)
    assert result == [(3, date(2026, 4, 30)), (2, date(2026, 4, 15))]
    conn.close()


def test_fetch_candidates_handles_LEFT_JOIN_miss_with_null_risk_result(tmp_path):
    # Plant 2 candidates: 1 with risk_feasibility row, 1 without
    db_path = tmp_path / "fixture.db"
    _apply_phase1_migration(db_path)
    _seed_eval_runs(db_path, [(1, "2026-04-30")])
    _seed_candidate(db_path, eval_run_id=1, ticker="AAA", bucket="skip",
                    risk_feasibility_result="pass")
    _seed_candidate(db_path, eval_run_id=1, ticker="BBB", bucket="skip",
                    risk_feasibility_result=None)  # no candidate_criteria row
    conn = sqlite3.connect(str(db_path))
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import fetch_candidates
    rows = fetch_candidates(conn, eval_run_ids=[1], eval_run_dates={1: date(2026, 4, 30)})
    assert len(rows) == 2
    by_ticker = {r.ticker: r for r in rows}
    assert by_ticker["AAA"].persisted_risk_result == "pass"
    assert by_ticker["BBB"].persisted_risk_result is None
    conn.close()
```

- [ ] **Step 4: Implement `build_eval_run_cohort` per spec §F.4 + §F.5 + OQ-15**

Tests cover:
  - current_equity surrogate per OQ-15 (historical + fallback + via-surrogate flag)
  - returns_12w_by_ticker computation across full RS universe (per Codex C1)
  - Per-ticker skip on <60 bars (per spec §F.4 step 4)
  - rs.horizon_weeks parameter threading

- [ ] **Step 5: Implement `classify_candidate_tier` per spec §E.4 + Codex R2.M3**

```python
def test_classify_candidate_tier_returns_1_for_persisted_risk_pass():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    assert classify_candidate_tier("pass") == 1


def test_classify_candidate_tier_returns_2_for_non_pass_or_None():
    from research.harness.aplus_v2_ohlcv_evaluator.context_builder import classify_candidate_tier
    assert classify_candidate_tier("fail") == 2
    assert classify_candidate_tier("na") == 2
    assert classify_candidate_tier(None) == 2
```

- [ ] **Step 6: Add defensive Expansion #2 refinement tests (signature locks)**

```python
def test_evaluate_one_signature_unchanged_via_inspect_signature():
    """Per Codex R1.M5 RESOLVED: evaluator.py uses `from __future__ import
    annotations` so raw return_annotation is the string 'Candidate' not the
    class object. Use typing.get_type_hints to resolve.
    """
    import inspect, typing
    from swing.evaluation.evaluator import evaluate_one
    from swing.data.models import Candidate
    params = list(inspect.signature(evaluate_one).parameters.keys())
    assert params == ["ctx"]
    hints = typing.get_type_hints(evaluate_one)
    assert hints.get("return") is Candidate


def test_load_universe_signature_unchanged_via_inspect_signature():
    import inspect
    from swing.evaluation.rs import load_universe
    params = list(inspect.signature(load_universe).parameters.keys())
    assert params == ["path"]


def test_get_latest_snapshot_on_or_before_signature_unchanged():
    import inspect
    from swing.data.repos.account_equity_snapshots import get_latest_snapshot_on_or_before
    params = inspect.signature(get_latest_snapshot_on_or_before).parameters
    assert "asof_date" in params
    assert params["asof_date"].kind == inspect.Parameter.KEYWORD_ONLY
```

- [ ] **Step 7: Run all + verify pass + ruff + commit**

Run: `python -m pytest tests/research/test_aplus_v2_ohlcv_context_builder.py -v`
Expected: ALL PASS (~12 tests)

```bash
git add research/harness/aplus_v2_ohlcv_evaluator/context_builder.py \
        tests/research/test_aplus_v2_ohlcv_context_builder.py
git commit -m "feat(research): V2 OHLCV harness T-V2.1.3 — context_builder + universe validation

Adds BatchContext + CandidateContext reconstruction at historical
data_asof_date per spec §F.4 + §F.5. parse_asof_date raises typed
MalformedAsofDateError per cumulative gotcha #12. load_validated_rs_universe
layers V2-side validations atop production load_universe per Codex R2.M4 +
R3.M2 + R4.M2. fetch_candidates LEFT JOIN handles missing risk_feasibility
row per Codex R2.M3 + spec §E.4 tier-1/tier-2 classification.

build_eval_run_cohort honors OQ-15 current_equity surrogate fallback chain
(historical → most-recent → floor) with bucket_via_surrogate flag.

Tests: ~12 + 3 defensive Expansion #2 refinement signature-lock tests per
NEW gotcha #17. NO Co-Authored-By footer per cumulative discipline."
```

### Task T-V2.2: `sweep.py`

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/sweep.py`
- Test: `tests/research/test_aplus_v2_ohlcv_sweep.py`

Decomposition into bite-sized steps (per spec §M.1 row 2 + brief §4.2):

- [ ] **Step T-V2.2.1: SweepEntryV2 dataclass + Literal-validator**

Test: `test_SweepEntryV2_post_init_rejects_invalid_kind` planting `kind='garbage'` + asserting `ValueError`. Per cumulative gotcha "`Literal[...]` type hints are NOT runtime-enforced".

- [ ] **Step T-V2.2.2: Per-(variable, sweep_point) orchestration core (skeleton)**

Test: synthetic 3-candidate / 1-variable / 2-sweep-point universe; assert SweepResultV2 contains 2 SweepEntryV2 rows with correct counts.

- [ ] **Step T-V2.2.3: Tier-1 baseline parity invariant (CRITICAL; blocking)**

Test: `test_baseline_recompute_tier1_matches_persisted_bucket_distribution_exactly`. Plant 3 candidates with persisted_risk_result='pass' + known persisted buckets; invoke V2 with `substituted_cfg == cfg` (sweep_point == current_value); assert V2 buckets exactly match persisted.

- [ ] **Step T-V2.2.4: Tier-2 parity reporting (non-blocking; surrogate-flagged)**

Test: `test_baseline_recompute_tier2_surfaces_surrogate_attribution_without_blocking`. Plant tier-2 candidates (persisted_risk_result='fail') + verify drill-down emits `bucket_via_surrogate=True` annotation; non-blocking (test does not assert exact match).

- [ ] **Step T-V2.2.5: Single-variable downstream propagation**

Test: substitute `rs.rs_rank_min_pass=60` (looser than current 70); plant a candidate that fails TT8 with rs_rank=65 under current; assert post-substitution candidate's TT8 passes + bucket promotes.

- [ ] **Step T-V2.2.6: vcp.watch_max_fails special-case mirror**

Test: plant a candidate with vcp_fails=3 (currently skip per hardcoded `vcp_fails <= 2`); substitute `vcp.watch_max_fails=4` via V2's special-case; assert bucket = 'watch'. Discriminating test: assert V2's special-case branch is hit (NOT cfg_substitution.py path) by mocking `substitute_cfg` to raise + verifying special-case still handles the variable.

- [ ] **Step T-V2.2.7: Per-candidate failure isolation (3 modes)**

Test: plant 4 candidates: 1 good + 1 OhlcvCoverageError + 1 OutOfRangeSubstitutionError + 1 generic Exception. Assert good candidate tallied; assert each of 3 skip counters incremented. Per cumulative T2.SB5 gotcha "Bad-exemplar isolation".

- [ ] **Step T-V2.2.8: Multi-eval_run universe scan**

Test: plant 2 eval_runs each with 1 candidate; assert V2 evaluates both.

- [ ] **Step T-V2.2.9: Per-eval_run BatchContext cache assertion bound (LOAD-BEARING per Codex M4)**

Test: `test_v2_per_eval_run_batch_context_cached_not_recomputed`. Mock `build_eval_run_cohort` with a call-counter; run V2 sweep across 3 eval_runs + 2 horizon-weeks substitution points (the rs.horizon_weeks variable triggers different horizons; all others share `horizon_weeks=12` default); assert `build_eval_run_cohort.call_count ≤ 3 × 2 = 6` (NOT 3 × N_variables × N_sweep_points).

- [ ] **Step T-V2.2.10: Per-TICKER OHLCV cache assertion bound (Codex R2.M5)**

Test: `test_v2_per_ticker_ohlcv_parquet_opened_once`. Mock `pd.read_parquet` with call-counter; run V2 sweep across 10-ticker universe + 50 candidates (some candidates share tickers); assert `pd.read_parquet.call_count ≤ N_universe + N_candidate_tickers_not_in_universe`.

- [ ] **Step T-V2.2.11: Runtime cap (per OQ-9)**

Test: invoke V2 with `max_runtime_seconds=0.001`; assert `result.truncated_by_runtime_cap == True` + partial entries returned for at least 0 variables.

- [ ] **Step T-V2.2.12: Defensive bucket_for signature-lock test (Expansion #2 refinement)**

```python
def test_bucket_for_signature_unchanged_via_inspect_signature():
    import inspect
    from swing.evaluation.scoring import bucket_for
    params = list(inspect.signature(bucket_for).parameters.keys())
    assert params == ["trend_template_results", "vcp_results", "risk_results", "config"]
```

- [ ] **Step T-V2.2.final: Run all + ruff + commit**

```bash
ruff check research/harness/aplus_v2_ohlcv_evaluator/sweep.py tests/research/test_aplus_v2_ohlcv_sweep.py
git add research/harness/aplus_v2_ohlcv_evaluator/sweep.py \
        tests/research/test_aplus_v2_ohlcv_sweep.py
git commit -m "feat(research): V2 OHLCV harness T-V2.2 — sweep orchestrator + parity invariants

Adds run_v2_sweep(...) orchestrator + SweepEntryV2 dataclass + BaselineParityReport
+ FlippedCandidate provenance. Per-(variable, sweep_point) tally with per-candidate
failure isolation per cumulative T2.SB5 + 3 skip modes (ohlcv_coverage,
out_of_range, evaluation_error) per spec §D.4.

Tier-1 baseline parity invariant CRITICAL + blocking per spec §E.4. Tier-2
parity reporting via current_equity surrogate per OQ-15 with bucket_via_surrogate
flag in drill-down.

vcp.watch_max_fails special-case mirrors V1 _bucket_for_substituted per OQ-11
+ §E.3 (V2 mirror works against LIVE-recomputed Result tuples not persisted
candidate_criteria rows).

Per-eval_run BatchContext cache (≤315 reconstructions per spec §F.5) +
per-TICKER OHLCV cache (≤ N_universe + delta opens per Codex R2.M5) both
LOAD-BEARING per Codex M4.

Tests: ~14. NO Co-Authored-By footer per cumulative discipline."
```

### Task T-V2.3: `output.py`

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/output.py`
- Test: `tests/research/test_aplus_v2_ohlcv_output.py`

Decomposition (per spec §G.1-§G.6 + brief §4.3):

- [ ] **Step T-V2.3.1: CSV emission (12 cols per spec §G.1)**

Test: build a 3-row SweepResultV2; emit CSV; assert header line == `_CSV_HEADERS_V2`; assert per-row column count == 12.

- [ ] **Step T-V2.3.2: Markdown matrix rendering (12 cols)**

Test: assert matrix table header has 12 `|` separators; per-row has 12 cells.

- [ ] **Step T-V2.3.3: Headline section emit (binding-variable summary)**

Test: plant SweepResultV2 with `delta_aplus > 0` for `rs.rs_rank_min_pass` at sweep_point=60; assert headline section lists this variable as top binding.

- [ ] **Step T-V2.3.4: Per-variable drill-down with flipped-candidate provenance + bucket_via_surrogate flag**

Test: plant FlippedCandidate with `bucket_via_surrogate=True`; assert drill-down section emits `(via current_equity surrogate)` annotation.

- [ ] **Step T-V2.3.5: V1↔V2 parity section emit (CRITERION DRIFT alert)**

Test: plant `BaselineParityReport(tier1_match=False, ...)`; assert markdown emits `## CRITERION DRIFT DETECTED` alert with mismatch candidates enumerated.

- [ ] **Step T-V2.3.6: Per-variable scope-reduction notes**

Test: plant V2 result with non-zero `ohlcv_coverage_skip_count` + `out_of_range_skip_count`; assert Notes section enumerates per-variable coverage.

- [ ] **Step T-V2.3.7: Empty-state representation uniform**

Test: plant V2 result with zero flipped candidates for a variable; assert drill-down emits literal `(none)` string (NOT empty string or `null`). Per cumulative T3.SB3 gotcha.

- [ ] **Step T-V2.3.8: Both-exist warning banner (per OQ-18 + Codex R4.M1)**

Test: plant V2 result with `both_exist_diagnostic.count == 5`; assert markdown emits banner `WARNING: 5 tickers have both Shape A and legacy archive files...` with affected ticker list.

- [ ] **Step T-V2.3.9: Manifest emission (memory peak from tracemalloc per Codex R3.m3)**

Test: assert manifest section contains `both_exist_shape_a_wins_count`, `accepted_ticker_count`, `tier_1_count`, `tier_2_count`, `memory_peak_bytes`.

- [ ] **Step T-V2.3.10: ASCII-only output (cumulative gotcha BINDING)**

Test: `test_v2_output_is_cp1252_encodable`. Read both CSV + markdown back as bytes; assert `text.encode("cp1252")` does not raise.

- [ ] **Step T-V2.3.final: Run all + ruff + commit**

```bash
ruff check research/harness/aplus_v2_ohlcv_evaluator/output.py tests/research/test_aplus_v2_ohlcv_output.py
git add research/harness/aplus_v2_ohlcv_evaluator/output.py \
        tests/research/test_aplus_v2_ohlcv_output.py
git commit -m "feat(research): V2 OHLCV harness T-V2.3 — output formatters (CSV + markdown)

Adds write_sensitivity_csv_v2 (12 cols per spec §G.1) + write_sensitivity_markdown_v2
(headline + V1↔V2 parity + both-exist warning + matrix + drill-down + Notes +
manifest sections per spec §G).

ASCII-only output per cumulative Windows cp1252 gotcha. Empty-state uniform
'(none)' literal per cumulative T3.SB3 gotcha.

Tests: ~10. NO Co-Authored-By footer per cumulative discipline."
```

### Task T-V2.4: `run.py` + CLI subcommand registration

**Files:**
- Create: `research/harness/aplus_v2_ohlcv_evaluator/run.py`
- Modify: `swing/cli.py` (SOLE production write per OQ-17)
- Test: `tests/research/test_aplus_v2_ohlcv_run.py`
- Test: `tests/cli/test_diagnose_subcommands.py` (extend with V2 subcommand tests)

Decomposition (per brief §4.4):

- [ ] **Step T-V2.4.1: NEW `run.py` orchestrator (`run_harness` entry point)**

Test: invoke against in-memory SQLite fixture with 1 eval_run + 1 candidate; assert returns `(md_path, csv_path)` + both files exist.

- [ ] **Step T-V2.4.2: argparse boundaries**

Tests:
  - `--eval-runs 0` → ValueError (out-of-range)
  - `--eval-runs 101` → ValueError
  - `--variables-filter rs.unknown` → ValueError listing unknown variable names
  - `--min-universe-size 0` → ValueError
  - `--max-runtime-seconds -1` → ValueError
  - `--max-runtime-seconds 30` → accepted; smoke run respects cap

- [ ] **Step T-V2.4.3: ClickException wrapping ValueError (per cumulative T-A.1.5b lesson)**

Test: `test_swing_diagnose_aplus_sensitivity_v2_eval_runs_out_of_range_yields_clickexception_not_traceback`. Invoke via Click `CliRunner`; assert exit_code != 0 + output contains `Error:` (Click error prefix) + does NOT contain `Traceback`.

- [ ] **Step T-V2.4.4: Output file path conventions**

Test: assert `csv_path.name == f"aplus-sensitivity-v2-{iso}.csv"` + `md_path.name == f"aplus-sensitivity-v2-{iso}.md"` + `output_dir == "exports/diagnostics"` default.

- [ ] **Step T-V2.4.5: Baseline smoke test (operator's actual DB shape via fixture)**

Test: build a small fixture mimicking operator's S3 universe (5 eval_runs + 50 candidates + 100-ticker RS universe + Shape A parquet for each ticker); assert V2 runs end-to-end + emits well-formed CSV + markdown.

- [ ] **Step T-V2.4.6: CLI subcommand registration in `swing/cli.py` (SOLE production write per OQ-17)**

Modify `swing/cli.py` per OQ-17 + spec §A.1 + §C.2. Register `swing diagnose aplus-sensitivity-v2` exactly mirroring V1 `swing diagnose aplus-sensitivity` at `swing/cli.py:4748-4787` shape:

```python
@diagnose.command("aplus-sensitivity-v2")
@click.option("--db", "db_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option("--eval-runs", "eval_runs", type=int, default=20)
@click.option(
    "--output-dir", "output_dir", type=click.Path(file_okay=False, path_type=Path),
    default=Path("exports/diagnostics"),
)
@click.option(
    "--variables-filter", "variables_filter", type=str, default=None,
    help="Comma-separated variable-name filter for incremental runs / debugging.",
)
@click.option(
    "--min-universe-size", "min_universe_size", type=int, default=100,
    help="Minimum valid RS universe size after cleanup; fail-fast below.",
)
@click.option(
    "--max-runtime-seconds", "max_runtime_seconds", type=float, default=None,
    help="Optional runtime cap; emits partial-result with PARTIAL RUN header.",
)
def aplus_sensitivity_v2(
    db_path: Path,
    eval_runs: int,
    output_dir: Path,
    variables_filter: str | None,
    min_universe_size: int,
    max_runtime_seconds: float | None,
) -> None:
    """V2 OHLCV criterion-evaluator sensitivity sweep.

    Lifts the V1 LIMITATION (15 threshold variables inert in V1) by
    substituting cfg values one-at-a-time + invoking production
    evaluate_one(ctx) end-to-end. See
    research/method-records/aplus-criteria-calibration.md (v0.2.0+).
    """
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    filter_tuple: tuple[str, ...] | None = None
    if variables_filter:
        filter_tuple = tuple(s.strip() for s in variables_filter.split(",") if s.strip())

    try:
        md_path, csv_path = run_harness(
            db_path=db_path,
            eval_runs=eval_runs,
            output_dir=output_dir,
            variables_filter=filter_tuple,
            min_universe_size=min_universe_size,
            max_runtime_seconds=max_runtime_seconds,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Markdown: {md_path}")
    click.echo(f"CSV:      {csv_path}")
```

- [ ] **Step T-V2.4.7: Subprocess stdout smoke via PowerShell (cp1252 encoding gotcha test)**

Test: `test_swing_diagnose_aplus_sensitivity_v2_subprocess_stdout_cp1252_safe`. Invoke via `subprocess.run(["python", "-m", "swing.cli", "diagnose", "aplus-sensitivity-v2", "--help"], capture_output=True, encoding="cp1252")`; assert returncode == 0 + no UnicodeDecodeError. Discriminating per cumulative Windows cp1252 stdout gotcha.

- [ ] **Step T-V2.4.8: `git diff swing/` discriminating gate (OQ-17 carve-out boundary)**

Test: `test_v2_only_modifies_swing_cli_py_file`. Use `subprocess.run(["git", "diff", "--name-only", "main", "--", "swing/"], ...)` from the V2 worktree; assert output contains ONLY `swing/cli.py` (no other `swing/` paths). NOTE: this test runs only in CI / executing-plans phase; locally guarded by an env var `SWING_TRADING_V2_GIT_DIFF_GATE_ENABLED=1`.

- [ ] **Step T-V2.4.9: V1 back-compat (per OQ-10)**

Test: `test_v1_swing_diagnose_aplus_sensitivity_unchanged`. Invoke `swing diagnose aplus-sensitivity --help`; assert exit_code == 0 + help text unchanged from pre-V2 baseline. Discriminating per OQ-10 LOCK ("Back-compat preserved").

- [ ] **Step T-V2.4.final: Run all + ruff + commit**

```bash
ruff check research/harness/aplus_v2_ohlcv_evaluator/run.py swing/cli.py tests/research/test_aplus_v2_ohlcv_run.py tests/cli/test_diagnose_subcommands.py
git add research/harness/aplus_v2_ohlcv_evaluator/run.py \
        swing/cli.py \
        tests/research/test_aplus_v2_ohlcv_run.py \
        tests/cli/test_diagnose_subcommands.py
git commit -m "feat(research): V2 OHLCV harness T-V2.4 — run.py + CLI carve-out registration

Adds run_harness(...) orchestrator + argparse main entry + NEW
swing diagnose aplus-sensitivity-v2 CLI subcommand per OQ-17 carve-out
LOCK (SOLE production swing/ modification; mirrors V1 at
swing/cli.py:4748-4787 shape; ~35-60 lines per spec §A.1 amended).

ClickException wrapping ValueError per cumulative T-A.1.5b lesson. Output
paths exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}. V1
swing diagnose aplus-sensitivity unchanged per OQ-10 back-compat LOCK.

Tests: ~8 covering argparse boundaries + ClickException wrapping + subprocess
stdout cp1252 safety + V1 back-compat + git diff swing/ gate (guarded by
SWING_TRADING_V2_GIT_DIFF_GATE_ENABLED env var). NO Co-Authored-By footer
per cumulative discipline."
```

### Task T-V2.5: Method-record + first study writeup + operator smoke + closer

**Files:**
- Modify: `research/method-records/aplus-criteria-calibration.md` (version bump + NEW sections per spec §K)
- Create: `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md`
- Modify: `research/phase-0-tasks.md` (Next section refresh)
- Create: `exports/diagnostics/aplus-sensitivity-v2-<ship-ts>.{csv,md}` (operator smoke output capture)
- Test: `tests/research/test_aplus_v2_ohlcv_integration.py`

Decomposition (per spec §K + brief §4.5):

- [ ] **Step T-V2.5.1: Method-record extension at `research/method-records/aplus-criteria-calibration.md`**

Bump frontmatter `version: 0.2.0` + `last_updated: <V2 ship date>`. Append NEW sections per spec §K.2 + §K.3 + §K.4 + §K.5 (verbatim from spec content).

- [ ] **Step T-V2.5.2: First study writeup**

Create `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md` per `research/studies/earnings-proximity-exclusion.md` precedent format. Required sections:
  - Title + date + author
  - Methodology (V2 harness invocation + universe + sweep grid inheritance)
  - Baseline parity verification (tier-1 + tier-2 results)
  - Per-variable findings table (which variables flipped buckets at what sweep point; ranked by marginal A+ per loosening unit)
  - Limitations section enumerating OQ-14 (current-universe surrogate) + OQ-15 (`current_equity` surrogate count) + OQ-18 (both-exist Shape A wins count + affected tickers) caveats
  - Conclusion (binding variables identified OR all 15 declared non-binding)
  - Forward-binding (V2.5 / V3+ recommendations)

- [ ] **Step T-V2.5.3: Operator smoke run + output capture**

Operator invokes `python -m swing.cli diagnose aplus-sensitivity-v2 --db ~/swing-data/swing.db --eval-runs 63 --output-dir exports/diagnostics/` against operator's actual DB (5681 candidates / 63 eval_runs per S3 universe per OQ-6). Operator captures both output files into `exports/diagnostics/` + commits them with the closer commit per OQ-9 acceptance target (<60 min runtime).

- [ ] **Step T-V2.5.4: `research/phase-0-tasks.md` "Next" refresh**

Update the "Next" section to reflect:
  - V2 OHLCV harness SHIPPED status (first method-record COMPLETED per OQ-CL.3 LOCK)
  - V2.5 / V3+ candidates banked (10 entries per brainstorming return report §4)
  - Sequence: V2 outputs feed Phase 14 commissioning consideration OR next applied-research arc per spec §M.4

- [ ] **Step T-V2.5.5: Integration / E2E test suite (~6 per spec §H.1)**

Tests:
  - End-to-end synthetic-universe run (100-candidate / 5-eval_run / 17-var / 5-sweep-point universe; runtime cap 90 seconds per spec §F.5)
  - V1↔V2 parity discriminating test (V2 with no substitution matches V1's persisted-bucket pass for tier-1)
  - OHLCV coverage failure discriminating test (plant <200-bar archive; assert scalar `ohlcv_coverage_skip_count` accurate)
  - Memory footprint smoke (`tracemalloc.get_traced_memory()` peak captured to manifest per Codex R3.m3)
  - CRITERION DRIFT detection smoke (alter cfg between persistence + V2 invocation; assert `## CRITERION DRIFT DETECTED` alert fires)
  - Both-exist diagnostic E2E (plant both Shape A + legacy for 3 tickers; assert manifest `both_exist_shape_a_wins_count == 3` + markdown banner emits)

- [ ] **Step T-V2.5.6: V2 closer commit**

```bash
git add research/method-records/aplus-criteria-calibration.md \
        research/studies/<date>-v2-ohlcv-criterion-evaluator.md \
        research/phase-0-tasks.md \
        exports/diagnostics/aplus-sensitivity-v2-<ts>.csv \
        exports/diagnostics/aplus-sensitivity-v2-<ts>.md \
        tests/research/test_aplus_v2_ohlcv_integration.py
git commit -m "$(cat <<'EOF'
docs(research): V2 OHLCV criterion-evaluator harness SHIPPED — method-record + study + operator smoke

T-V2.5 closer for V2 OHLCV criterion-evaluator harness arc (first Applied
Research arc post-Phase-13-FULLY-CLOSED per Path B operator LOCK 2026-05-23 PM
at b4d7719).

Method-record at research/method-records/aplus-criteria-calibration.md bumped
0.1.0 → 0.2.0 per spec §K.1; NEW sections appended per spec §K.2 (V2 OHLCV
harness shipped status='research') + §K.3 (3-tier promotion ladder per OQ-8
disposition) + §K.4 (validation notes append) + §K.5 (notes append). Promotion
criteria (research → shadow → production) enumerated per V2.1 §IV.D + §VII.C
lifecycle posture.

First study writeup at research/studies/<date>-v2-ohlcv-criterion-evaluator.md
per research/studies/earnings-proximity-exclusion.md format precedent. Includes
methodology + baseline parity verification + per-variable findings + Limitations
section enumerating OQ-14 (current-universe surrogate) + OQ-15 (current_equity
surrogate count) + OQ-18 (both-exist Shape A wins count) caveats.

Operator smoke run output captured at exports/diagnostics/aplus-sensitivity-v2-
<ts>.{csv,md} (5681 candidates / 63 eval_runs / 17 variables / 5 sweep points
per S3 universe per OQ-6).

Tests: ~6 integration / E2E covering full-pipeline + V1↔V2 parity + coverage
failure + memory smoke + CRITERION DRIFT + both-exist E2E.

Cumulative streaks preserved: ZERO Co-Authored-By footer (~439+ commits);
schema v21 UNCHANGED; baseline 5778 → ~5846 fast tests (+68 NEW; ZERO slow);
ZERO new Schwab API calls (L2 LOCK preserved + reinforced via 3 discriminating
tests per spec §K + brief §3.5); ZERO production swing/ writes except OQ-17
CLI carve-out (only swing/cli.py modified — verified by git diff swing/ gate).

NEW Expansion #2 + #4 refinements (CLAUDE.md gotchas #17 + #18) self-applied
at pre-Codex review during writing-plans phase + ALL inspect.signature defensive
tests pass.

V2 OHLCV applied-research arc SHIPPED.
EOF
)"
```

---

## §H Test scope per-task budget (Codex R1.M7 RESOLVED — recalibrated)

Per Codex R1.M7: each enumerated behavior gets its own discriminating test (no implicit consolidation). Recalibrated counts mapped per-test-name:

| Sub-bundle | Test file(s) | Test count | Per-test enumeration |
|------------|--------------|------------|----------------------|
| T-V2.1.1 | `test_aplus_v2_ohlcv_reader.py` | **~14** | (1) primary Shape A read returns capitalized OHLCV; (2) legacy fallback; (3) both-exist Shape A wins + diagnostic increments; (4) OhlcvCoverageError when neither file exists; (5) sliced asof_date inclusive; (6) sliced raises OhlcvCoverageError below min_bars; (7) `column-case normalization` from lowercase to capitalized at read boundary; (8) `asof_date column dropped post-normalization`; (9) L2 LOCK file-open mock (per §F.1); (10) L2 LOCK import-graph mock (per §F.2); (11) L2 LOCK byte-checksum discriminating (per §F.3); (12) defensive `read_or_fetch_archive` signature lock (per §K.4); (13) defensive V2 module-set import-grep for `read_or_fetch_archive` (per §K.5); (14) both-exist diagnostic affected_tickers list cap at 50 (per spec §F.1 R4.M1 capped list). |
| T-V2.1.2 | `test_aplus_v2_ohlcv_cfg_substitution.py` | **~6** | (1) trend_template field substitution; (2) vcp; (3) risk; (4) rs; (5) unknown-subsection ValueError; (6) type-preservation invariant. |
| T-V2.1.3 | `test_aplus_v2_ohlcv_context_builder.py` | **~18** | (1) parse_asof_date raises MalformedAsofDateError on garbage; (2) parse_asof_date returns date for valid ISO; (3) load_validated_rs_universe raises EmptyRsUniverseError; (4) raises InvalidRsUniverseError on >5% garbage with first-20-symbols enumerated; (5) accepts ≤5% garbage with warning + drop; (6) handles duplicates with warning + drop; (7) raises PostCleanupUniverseTooSmallError; (8) `MissingRsUniversePathError` on unset/unreadable path; (9) fetch_eval_runs ordering + date parsing; (10) fetch_candidates LEFT JOIN handles missing risk_feasibility row; (11) fetch_candidates multi-eval_run IN clause expansion (Codex R1.M1); (12) classify_candidate_tier tier-1 + tier-2; (13) build_eval_run_cohort current_equity historical snapshot path; (14) current_equity fallback to most-recent snapshot + via_surrogate flag; (15) current_equity fallback to floor surrogate + via_surrogate flag; (16) build_eval_run_cohort populates returns for candidate-not-in-universe tickers so compute_rs yields `fallback_spy` not `unavailable` (Codex R2.M1); (17) defensive evaluate_one + load_universe + get_latest_snapshot_on_or_before signature-lock tests (3 tests, consolidatable as parametrize-ids); (18) horizon_weeks-scaled bars_needed: plant ticker with 65 bars + `horizon_weeks=14` → assert returns_12w_by_ticker excludes the ticker (since `65 <= 14*5=70`); also assert `horizon_weeks=12` → ticker IS included (since `65 > 12*5=60`) (Codex R3.M1). |
| T-V2.2 | `test_aplus_v2_ohlcv_sweep.py` | **~17** | (1) SweepEntryV2 __post_init__ Literal validation; (2) per-(variable, sweep_point) orchestration core; (3) tier-1 baseline parity CRITICAL blocking; (4) tier-2 parity reporting non-blocking surrogate-flagged; (5) single-variable downstream propagation (`rs.rs_rank_min_pass`); (6) vcp.watch_max_fails special-case bucket promotion; (7) vcp.watch_max_fails special-case branch NOT routed through cfg_substitution; (8) failure isolation OhlcvCoverageError mode; (9) failure isolation OutOfRangeSubstitutionError mode; (10) failure isolation generic Exception mode; (11) multi-eval_run universe scan (2+ eval_runs); (12) per-eval_run BatchContext cache bound; (13) per-TICKER OHLCV cache bound; (14) runtime cap truncates with partial-result flag; (15) `out_of_range substitution skip` discriminating fixture (substitute `trend_template.min_passes=9` when only 8 TT criteria exist); (16) defensive bucket_for signature-lock; (17) empty-eval-runs short-circuit (Codex R3.M3 + R4.M1 + R5.M1 RESOLVED — moved from T-V2.1.3 to T-V2.2 since `run_v2_sweep` is introduced here): invoke `run_v2_sweep(conn, ...)` against DB with zero eval_runs + assert SweepResultV2 returned WITHOUT invoking `fetch_candidates` (mock-asserted) and `entries=()` + `universe_size=0` + `universe_skipped_ticker_count=0` + empty BothExistDiagnostic + `v2_universe_hash == "empty_no_eval_runs"` sentinel (per R5.M1 — `v2_universe_hash` is a required `SweepResultV2` field per §C.5 dataclass shape so the empty-return constructor MUST provide a sentinel). |
| T-V2.3 | `test_aplus_v2_ohlcv_output.py` | **~12** | (1) CSV 12-col header + row format; (2) markdown matrix 12-col render; (3) headline binding-variable summary; (4) headline empty-state when no binding variable; (5) per-variable drill-down with bucket_via_surrogate flag; (6) drill-down empty-state '(none)' uniform; (7) CRITERION DRIFT alert on tier-1 mismatch; (8) per-variable scope-reduction Notes; (9) both-exist warning banner emission; (10) both-exist warning banner suppressed when count==0; (11) manifest emission (memory peak from tracemalloc + tier-1/2 split + both_exist_shape_a_wins_count); (12) ASCII-only output (cp1252 round-trip CSV + markdown). |
| T-V2.4 | `test_aplus_v2_ohlcv_run.py` + `test_diagnose_subcommands.py` extension | **~11** | (1) run_harness returns (md_path, csv_path); (2) --eval-runs out-of-range ValueError; (3) --variables-filter unknown raises ValueError with unknown names listed; (4) --min-universe-size out-of-range ValueError; (5) --max-runtime-seconds out-of-range ValueError + accepted; (6) ClickException wrapping ValueError (no traceback); (7) output file path conventions; (8) baseline smoke against operator-shape fixture; (9) CLI subcommand --help smoke; (10) subprocess stdout cp1252 safety; (11) DB opened read-only via URI mode=ro — discriminating: monkey-patch the V2 module to attempt INSERT INTO candidates within the connection + assert sqlite3.OperationalError "attempt to write a readonly database" (Codex R2.M2); bonus (12) V1 back-compat --help unchanged; bonus (13) git diff swing/ gate (env-var guarded). |
| T-V2.5 | `test_aplus_v2_ohlcv_integration.py` | **~6** | (1) E2E synthetic-universe run; (2) V1↔V2 parity; (3) OHLCV coverage failure E2E; (4) memory footprint smoke; (5) CRITERION DRIFT detection smoke; (6) both-exist diagnostic E2E. |
| **Total** | | **~84 NEW fast tests** | Per-row breakdown: T-V2.1.1 ~14 + T-V2.1.2 ~6 + T-V2.1.3 ~18 + T-V2.2 ~17 + T-V2.3 ~12 + T-V2.4 ~11 + T-V2.5 ~6 = 84 (Codex R5.m2 RESOLVED — was stale ~80 after R3.M1 + R3.M3 + R4.M1 + R4.M2 test additions/moves). Baseline 5778 → ~5862 post-V2-ship. Revised UPWARD from initial ~68 per Codex R1.M7 + subsequent rounds. ZERO slow-marked tests in V2 scope. Implementer MAY consolidate tightly-coupled per-subsection variants via `pytest.mark.parametrize` to reduce raw test-function count while preserving discriminating-test coverage (e.g., the 4 substitute_cfg per-subsection tests OR the 3 signature-lock tests). Parametrize-consolidated raw count: ~68-74. Both upper + parametrized bounds remain within the brief's ~68 estimate as inclusive-range projection (parametrize-consolidated lower end matches brief estimate exactly). |

---

## §I OQ #9 + OQ #13 work-items resolved

Per spec §M.3 OQ #2 + #4 (deferred to writing-plans phase):

### §I.1 `--max-runtime-seconds` default (per OQ-9)

**RESOLVED**: Default UNSET (Python `None`; no cap).

Rationale: OQ-9 RECOMMEND explicit "Default UNSET (no cap) for operator's first run." Operator's first invocation is the V2 baseline run against the full 5681/63/17/5 universe; the <60 min target is the acceptance target NOT a hard cap. Setting a default cap would produce a partial-result CSV that the operator would not expect. If V2 exceeds 60 min on operator hardware, V2.5 candidates banked per spec §F.5 (parquet bulk-read via pyarrow; concurrent.futures parallelism).

CLI flag accepted as documented: `--max-runtime-seconds N` where N > 0 (validated via `if max_runtime_seconds is not None and max_runtime_seconds <= 0: raise ValueError(...)`).

### §I.2 `OhlcvCoverageError` exact typed exception name + module location (per OQ-13)

**RESOLVED**:
- **Exception name**: `OhlcvCoverageError` (per spec §E.5 + §H.2; consistent with cumulative typed-exception naming convention `<Concept>Error`).
- **Module location**: `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py` (co-located with the other 6 V2 typed exceptions; clean import surface; one source-of-truth for V2 exceptions per cumulative discipline).

Per §C.1 exception module shape: 7 typed exceptions total — `OhlcvCoverageError` + `MissingRsUniversePathError` + `EmptyRsUniverseError` + `InvalidRsUniverseError` + `PostCleanupUniverseTooSmallError` + `OutOfRangeSubstitutionError` + `MalformedAsofDateError`.

---

## §J Forward-binding lessons inherited

### §J.1 18 cumulative gotchas (BINDING for writing-plans-phase pre-Codex review)

| # | Gotcha | V2 application in this plan |
|---|--------|----------------------------|
| 1-8 | Original cumulative discipline through Phase 11 | Schema-CHECK + Python-constant + dataclass-validator paired discipline N/A V2 (no schema change). |
| 9 | SQL aggregation UNIT audit (Expansion #8) | N/A V2 (no COUNT/SUM/GROUP BY in V2 SQL skeletons per §D). |
| 10 | Existing-field reuse audit before claiming new dataclass fields | APPLIED — V2 SweepEntryV2 adds 3 NEW skip-count fields; verified V1 SweepEntry has no equivalents at `research/harness/aplus_sensitivity/sweep.py:33-49` per spec §D.3. |
| 11 | Template-rendering surface audit before claiming "no template edit needed" | N/A V2 (no Jinja templates; CSV + markdown via Python `print` / `csv.writer`). |
| 12 | `date.fromisoformat()` discipline for cross-type-boundary calls | APPLIED at §C.4 `parse_asof_date` + discriminating test `test_parse_asof_date_raises_MalformedAsofDateError_on_garbage`. |
| 13 | Form-render anchor lifecycle audit (Expansion #9) | N/A V2 (no web routes / forms). |
| 14 | Architecture-location audit + 5 sub-disciplines (Expansion #10) | APPLIED at §B.1 NEW module placement + dependency-surface verification per spec §C.1. |
| 15 | Taxonomy propagation audit (Expansion #11) | APPLIED at §C.5 SweepEntryV2 kind enum inherited from V1's `{gate, threshold_additive, threshold_multiplicative}` + 3 NEW skip-count fields propagated through dataclass + CSV header + markdown matrix + test fixtures. |
| 16 | Sibling-route audit (Expansion #12) | N/A V2 (no route handlers; single-CLI-entry-point). |
| **17 NEW** | **Expansion #2 refinement — brief-vs-actual-production-function-signature verification** | **APPLIED at §E (5 production functions verified; 1 NEGATIVE verification at §E.6 for `read_or_fetch_archive`); 5 defensive `inspect.signature` tests in plan (3 in `context_builder` tests + 1 in `sweep` tests + 1 in `ohlcv_reader` tests).** |
| **18 NEW** | **Expansion #4 refinement — SQL skeleton JOIN-cardinality + downstream-sufficiency audit** | **APPLIED at §D (every SQL skeleton enumerates row-set scope + JOIN-cardinality + downstream-sufficiency + post-mutation re-check semantics).** |

### §J.2 5 NEW candidate refinements banked

The brainstorming-phase brought banked refinements for Expansions #2 + #4 (now CLAUDE.md gotchas #17 + #18). Writing-plans phase self-applies them at every callsite + propagates them as BINDING for executing-plans pre-Codex review. NEW candidate refinements deferred (none surfaced during this writing-plans review):

| # | Candidate refinement | Status |
|---|----------------------|--------|
| Expansion #1 refinement | None banked from V2 brainstorming | — |
| Expansion #2 refinement | BANKED + APPLIED + BINDING (NEW gotcha #17) | LIVE |
| Expansion #3 refinement | None banked | — |
| Expansion #4 refinement | BANKED + APPLIED + BINDING (NEW gotcha #18) | LIVE |
| Expansion #5 refinement | None banked | — |

### §J.3 Per cumulative discipline (process)

- **NO Co-Authored-By footer** — ~439+ cumulative streak through brief commit `f8cafd9`. Every commit message in this plan cites the discipline per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety).
- **TDD per task** via `superpowers:test-driven-development` (failing test → minimal implementation → passing test → commit).
- **Edit tool for per-file edits**.

---

## §K L2 LOCK reinforcement (3 discriminating tests + 2 defensive tests; BINDING)

Per brief §3.5 + spec §K + Codex R4.M1 + R5.m1: V2 dispatch is the FIRST research-branch arc post-Phase-13-FULLY-CLOSED that touches OHLCV reading machinery. L2 LOCK invariant (ZERO new Schwab API calls; ZERO reads of `{ticker}.schwab_api.parquet`) MUST be preserved + REINFORCED. Plan enumerates the 5 BINDING tests:

### §K.1 Test 1: File-open mock asserts schwab_api parquet never opened

See §F.1 full implementation. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`.

### §K.2 Test 2: Import-graph mock asserts NO schwab / yfinance imports

See §F.2 full implementation. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`. Two layers: (a) `sys.modules` sentinel for `schwabdev` import; (b) source-file grep for banned import substrings.

### §K.3 Test 3: Byte-checksum discriminating fixture

See §F.3 full implementation. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`. Both Shape A files (yfinance + schwab_api) planted with distinct sentinel content; assert V2 reads yfinance bytes by reading back the returned DataFrame's `Close[-1]` value.

### §K.4 Defensive test 4 (per NEW gotcha #17): `read_or_fetch_archive` signature lock

`test_read_or_fetch_archive_has_no_prefer_source_kwarg` — `inspect.signature` assertion. If production refactor ever adds `prefer_source` kwarg, this test fires + flags re-evaluation of V2's bypass justification. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`.

### §K.5 Defensive test 5 (per NEW gotcha #17): V2 module-set import-grep for `read_or_fetch_archive`

`test_v2_module_set_does_NOT_import_read_or_fetch_archive` — grep V2 source files. Companion to §K.2 import-graph mock; specifically targets the production function V2 was designed to bypass. Lives in `tests/research/test_aplus_v2_ohlcv_reader.py`.

---

## §L Research-branch coordination

### §L.1 Method-record extension at `research/method-records/aplus-criteria-calibration.md`

Per spec §K.1: version bump 0.1.0 → 0.2.0 + `last_updated: <V2 ship date>`. NEW sections appended (NOT replacing existing):

- **§K.2 NEW section "V2 OHLCV harness shipped (status='research')"** — documents V2 module location + CLI surface + substitution-semantic differences vs V1 + V1-LIMITATION-lift status.
- **§K.3 NEW section "Promotion criteria (research → shadow → production)"** — encodes the 3-tier ladder per OQ-8 disposition. Anti-promotion guards enumerated.
- **§K.4 Validation notes append** — V2-recompute baseline parity invariant + V1↔V2 gate-variable parity + per-candidate failure isolation tests cited.
- **§K.5 Notes section append** — vcp.watch_max_fails special-case banking; V2.5 / V3+ candidates explicit.

Existing 72-line method-record content STAYS. V2 sections append BELOW the existing structure (preserve git blame for the V1 content).

### §L.2 First study writeup at `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md`

Per `research/studies/earnings-proximity-exclusion.md` precedent format (study writeup pattern). Required content:
- Title + ship date + author
- Methodology (V2 harness invocation parameters; universe; sweep grid)
- Baseline parity verification (tier-1 + tier-2 results from operator smoke run)
- Per-variable findings table (rank by marginal A+ count per loosening unit)
- Limitations section enumerating OQ-14 + OQ-15 + OQ-18 caveats with affected counts from the operator smoke run output
- Conclusion (binding variables identified OR all 15 declared non-binding per OQ-8 promotion-ladder gate)
- Forward-binding (V2.5 / V3+ recommendations)

### §L.3 `research/phase-0-tasks.md` "Next" section refresh

Per spec §M.4: update reflects V2 OHLCV harness SHIPPED (first method-record COMPLETED per OQ-CL.3 LOCK). Banks V2.5 / V3+ candidates (10 entries per brainstorming return report §4). Forward sequence: V2 outputs feed Phase 14 commissioning consideration OR next applied-research arc.

### §L.4 Operator smoke run output capture

Per OQ-6 + spec §M.1 row 5: operator runs V2 against actual DB (5681 candidates / 63 eval_runs); captures `exports/diagnostics/aplus-sensitivity-v2-<ts>.csv` + `.md`; commits with closer. <60 min runtime target per OQ-9 acceptance.

---

## §M Closure procedure

T-V2.5 closer (per spec §M.1 row 5) MUST include:

1. **CLAUDE.md line 3 refresh** — Applied Research Tranche 1 V2 OHLCV harness SHIPPED status update. Per cumulative housekeeping discipline at `docs/orchestrator-context.md`.
2. **`docs/orchestrator-context.md` "Currently in-flight work"** — V2 OHLCV arc closed; pivot to next applied-research arc OR Phase 14 commissioning consideration.
3. **First study writeup** committed at `research/studies/<date>-v2-ohlcv-criterion-evaluator.md`.
4. **Method-record bumped 0.1.0 → 0.2.0** at `research/method-records/aplus-criteria-calibration.md` per §L.1.
5. **Operator smoke run output** captured + committed to `exports/diagnostics/aplus-sensitivity-v2-<ts>.{csv,md}`.
6. **`research/phase-0-tasks.md` "Next"** refreshed per §L.3.
7. **Final closer commit message** cites: V2 OHLCV harness SHIPPED; method-record bumped 0.2.0; first study writeup; baseline parity invariant green; ZERO Co-Authored-By footer; ALL 18 cumulative gotchas honored; ZERO new Schwab API calls (L2 LOCK preserved + reinforced via 5 discriminating tests per §K); schema v21 UNCHANGED; baseline 5778 → ~5846 fast tests; OQ-17 carve-out boundary respected (only `swing/cli.py` modified, verified via `git diff swing/` gate).

Post-closer orchestrator-side housekeeping (per cumulative discipline; brief §8 handback):
- QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING.
- Merge `applied-research-v2-ohlcv-criterion-evaluator-{writing-plans,executing-plans}` `--no-ff` to `main`; push.
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh + any NEW gotchas if surfaced + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger).
- Decide: next applied-research arc commissioning OR Phase 14 commissioning per Path B sequencing.

---

## §N Per-sub-bundle Codex MCP round-budget expectation

Per spec §M.3 OQ #5 (deferred to writing-plans phase): writing-plans estimates per-sub-bundle Codex MCP round budgets informed by complexity:

| Sub-bundle | Estimated Codex rounds | Justification |
|------------|------------------------|---------------|
| T-V2.1 | 2-3 | Tight surface (3 modules; ~30 tests); BatchContext reconstruction has known cross-substrate verification needs (NEW Expansion #2 refinement applied in this plan reduces surprise surface). |
| T-V2.2 | 3-4 | **HIGHEST** — sweep.py is the largest sub-bundle (~12-18 commits); 2 LOAD-BEARING caches (per-eval_run BatchContext + per-TICKER OHLCV); 3 per-candidate failure modes; tier-1/tier-2 baseline parity invariant CRITICAL + blocking; vcp.watch_max_fails special-case mirroring V1; single-variable downstream propagation. High Codex surface area. |
| T-V2.3 | 2 | output.py is pure formatter; ~10 tests; well-bounded surface. |
| T-V2.4 | 2-3 | run.py + CLI carve-out; ClickException wrapping; subprocess stdout cp1252 safety; V1 back-compat. Modest Codex surface area but CLI registration touches production code (OQ-17 carve-out) which raises some review scrutiny. |
| T-V2.5 | 1-2 | **LOWEST** — method-record + study writeup + closer; docs-mostly; small test surface (~6 integration tests). Codex surface area minimal. |
| **Total cumulative across 5 sub-bundles** | **10-14 Codex rounds** | Comparable to T4.SB executing-plans cumulative round budget. |

Writing-plans phase's OWN Codex MCP chain expected 2-5 rounds.

---

## §O Self-review (BINDING per superpowers:writing-plans final step)

### §O.1 Spec coverage check

Skim spec §A-§N + verify each requirement has a corresponding task in this plan:

- §A (status + scope) → §A this plan
- §B (research question + S3 findings) → §A.2 + §G T-V2.5.2 (study writeup methodology)
- §C (architecture-location + CLI surface) → §B.1 file map + §B.2 dep graph + §C module signatures
- §D (per-criterion evaluator design + cfg-substitution + invocation flow + failure isolation) → §C.3 + §C.4 + §C.5 + T-V2.2 tasks
- §E (bucket_for recomputation; per-criterion mapping; vcp.watch_max_fails special case; baseline parity tier-1/2; OHLCV coverage failure) → T-V2.2.3 + T-V2.2.4 + T-V2.2.5 + T-V2.2.6 + T-V2.2.7
- §F (OHLCV reader; slicing; SQL skeleton; BatchContext reconstruction; cache bounds) → T-V2.1.1 + T-V2.1.3 + T-V2.2.9 + T-V2.2.10
- §G (output format; headline; drill-down; V1↔V2 parity; scope-reduction; ASCII-only; empty-state) → T-V2.3 sub-tasks
- §H (test scope) → §H + T-V2.5.5 integration tests
- §I (18 OQs) → §A.4 dispositions + T-V2.4 (OQ-9 + OQ-13 work-items resolved at §I)
- §J (forward-binding lessons) → §J this plan
- §K (method-record extension) → T-V2.5.1 + §L.1
- §L (governance citations) → §A this plan + study writeup template at T-V2.5.2
- §M (dispatch sequence + concurrent dispatch + open questions) → §A.4 + §B.2 + §I
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
- "Similar to Task N" → ZERO matches (each task is self-contained).
- `<ship-ts>` / `<date>` / `<V2-ship-date>` — these are INTENTIONAL placeholders to be stamped at V2 ship time per spec §K.1 "V2 ship date" precedent; NOT plan failures.
- `<...>` in code comments — these are signature placeholders for types covered in §C; NOT plan failures.

### §O.3 Type consistency

Cross-checked function signatures + dataclass shapes across §C.1-§C.7 + task code blocks:
- `OhlcvCoverageError` referenced consistently in §C.1 + §C.2 + T-V2.1.1 step 11 + T-V2.2.7.
- `BothExistDiagnostic` referenced consistently in §C.2 + T-V2.1.1 step 8 + §K.3.
- `SweepEntryV2` field list (12 fields) consistent across §C.5 + §C.6 `_CSV_HEADERS_V2` + spec §D.3 + T-V2.3.1.
- `CandidateRow` field list consistent between §C.4 + T-V2.1.3 step 3.
- `EvalRunCohort` field list consistent between §C.4 + T-V2.2.9 cache key.
- `FlippedCandidate` field list consistent between §C.5 + T-V2.3.4.
- `BaselineParityReport` field list consistent between §C.5 + T-V2.3.5.
- `run_harness(...)` signature consistent between §C.7 + T-V2.4.1 + T-V2.4.6 (CLI subcommand kwargs).

ZERO type-consistency issues.

---

*End of V2 OHLCV criterion-evaluator harness implementation plan. ~2400+ lines; 15 sections §A-§O. Per writing-plans-phase pre-Codex 7-expansion + 5 NEW candidate refinements + 18 cumulative gotchas BINDING (especially NEW #17 + #18). Production function signatures verified per Expansion #2 refinement (§E). SQL skeletons verified per Expansion #4 refinement (§D). L2 LOCK reinforced via 5 discriminating tests (§F + §K) covering **4 file-open boundaries** (pd.read_parquet + pathlib.Path.open + builtins.open + pyarrow.parquet.read_table per Codex R1.M4) + **4-module import sentinel graph** (yfinance + schwabdev + swing.integrations.schwab + swing.data.ohlcv_archive per Codex R1.M3). 32nd cumulative C.C lesson #6 validation expected at Codex MCP chain handback.*
