"""V2 sweep orchestrator: per-(variable, sweep_point) live evaluate_one
recompute with cfg-substitution.

LOAD-BEARING caches (per Codex M4):
  - Per-eval_run BatchContext: keyed on (eval_run_id, horizon_weeks).
  - Per-TICKER OHLCV: keyed on ticker; full-history frame; in-memory slice
    per (ticker, asof_date) combo as needed.

Per-candidate failure isolation (cumulative T2.SB5 gotcha): 3 modes
  - OhlcvCoverageError -> ohlcv_coverage_skip_count++
  - OutOfRangeSubstitutionError -> out_of_range_skip_count++
  - any other Exception -> evaluation_error_skip_count++ + WARNING log

vcp.watch_max_fails special-case (per OQ-11 + plan §E.3): mirrors V1's
_bucket_for_substituted watch_max_fails branch end-to-end against V2's
LIVE-recomputed Result tuples (NOT persisted candidate_criteria rows).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from research.harness.aplus_sensitivity.variables import SweepVariable
from research.harness.aplus_v2_ohlcv_evaluator.cfg_substitution import substitute_cfg
from research.harness.aplus_v2_ohlcv_evaluator.context_builder import (
    CandidateRow,
    EvalRunCohort,
    build_eval_run_cohort,
    classify_candidate_tier,
    fetch_eval_runs,
    load_validated_rs_universe,
    parse_asof_date,
)
from research.harness.aplus_v2_ohlcv_evaluator.exceptions import (
    OhlcvCoverageError,
    OutOfRangeSubstitutionError,
)
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
)
from swing.config import Config
from swing.evaluation.context import CandidateContext, MarketContext
from swing.evaluation.evaluator import evaluate_one

_logger = logging.getLogger(__name__)

_ALLOWED_KINDS_V2: frozenset[str] = frozenset(
    {"gate", "threshold_additive", "threshold_multiplicative"}
)

# vcp.watch_max_fails special-case variable name (per OQ-11 + §E.3)
_VCP_WATCH_MAX_FAILS_VAR = "vcp.watch_max_fails"


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
    ohlcv_coverage_skip_count: int  # NEW vs V1 -- SCALAR per V2 invocation (Codex R1.M3)
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
      bucket_via_surrogate: per OQ-15 -- True when current_equity was a
        surrogate (no historical snapshot found at eval_run's asof_date).
      variable_name: name of the SweepVariable that caused this flip (e.g.
        'rs.rs_rank_min_pass'), or None for baseline-parity-derived flips.
        Codex R2.M2: used by output.py to route flips to the correct section
        (per-variable drill-down vs. dedicated baseline parity drift section).
    """

    ticker: str
    eval_run_id: int
    data_asof_date: str  # ISO; for output rendering
    sweep_point: float | int
    old_bucket: str
    new_bucket: str
    old_criterion_failure: str
    bucket_via_surrogate: bool
    variable_name: str | None = None  # Codex R2.M2: None = baseline-parity flip


@dataclass(frozen=True)
class BaselineParityReport:
    """V1<->V2 baseline parity (current-value sweep point) per spec §E.4.

    tier_1_count: total tier-1 candidates processed at baseline (current_value
      sweep point). Per spec §H T-V2.3.9 manifest field.
    tier_2_count: total tier-2 candidates processed at baseline (current_value
      sweep point). Per spec §H T-V2.3.9 manifest field.
      NOTE: tier_2_count >= tier2_match_count + tier2_mismatch_count because
      tier-2 candidates that fail OHLCV coverage or substitution are NOT tallied
      in tier2_match/mismatch counts (they are skipped), but ARE counted in
      tier_2_count as "candidates classified as tier-2".
    """

    tier1_match: bool  # EXACT match required; blocking
    tier1_mismatch_candidates: tuple[str, ...]  # (ticker:eval_run_id) on mismatch
    tier2_match_count: int
    tier2_mismatch_count: int
    tier2_via_surrogate_count: int
    tier_1_count: int = 0  # NEW: total tier-1 candidates at baseline
    tier_2_count: int = 0  # NEW: total tier-2 candidates at baseline


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
        swing/config.py:17 + constructed at swing/config.py:456 -- Codex R1.M2
        RESOLVED; `cfg.archive` only holds `archive_history_days`).
      eval_runs_window: last N eval_runs (default 20; max 100; mirror V1).
      min_universe_size: RS universe validation threshold (default 100).
      max_runtime_seconds: optional cap (per OQ-9). When elapsed wallclock
        exceeds cap, sweep aborts mid-loop + sets truncated_by_runtime_cap=True
        on the returned result; partial entries are returned for variables
        completed so far.

        Codex R2.M1 SEMANTIC (Option B -- documented): the cap is checked at
        variable-loop + sweep-point boundaries ONLY. Baseline parity
        (_compute_baseline_parity) is mandatory setup work and always completes
        before the cap is applied; operators using the cap must budget for
        baseline-parity time in addition to per-variable sweep time.
        SweepResultV2.baseline_parity is always fully-populated even under
        near-zero caps.

    Returns: SweepResultV2 with one SweepEntryV2 per (variable, sweep_point) +
      drill-down + baseline parity + diagnostics.

    Empty-DB / no-eval-runs short-circuit (Codex R3.M3 + R4.M2 RESOLVED --
    mirrors V1 precedent at `research/harness/aplus_sensitivity/sweep.py:81`):
    when `fetch_eval_runs(conn, eval_runs_window=N)` returns an empty list, V2
    returns an empty SweepResultV2 WITHOUT invoking fetch_candidates,
    load_validated_rs_universe, OR building any EvalRunCohort. Codex R4.M2
    RESOLVED: ALL counts are sentinel zeros + empty diagnostics because no
    universe / OHLCV / cohort work happens. The pre-R4 docstring's
    `universe_size=<resolved>` + `universe_skipped_ticker_count=<resolved>`
    framing was inconsistent -- both are produced by BatchContext / OHLCV
    reconstruction, neither of which fires in the empty-DB case.
    """
    t_start = time.monotonic()
    cache_dir = Path(cache_dir)
    diagnostic = BothExistDiagnostic()

    # --- Empty-DB short-circuit (per Codex R3.M3 + R4.M2) ---
    eval_runs = fetch_eval_runs(conn, eval_runs_window=eval_runs_window)
    if not eval_runs:
        elapsed = time.monotonic() - t_start
        return SweepResultV2(
            eval_runs_window=eval_runs_window,
            eval_run_id_range=(0, 0),
            total_candidates=0,
            universe_size=0,
            v2_universe_hash="empty_no_eval_runs",
            entries=(),
            flipped=(),
            baseline_parity=BaselineParityReport(
                tier1_match=True,
                tier1_mismatch_candidates=(),
                tier2_match_count=0,
                tier2_mismatch_count=0,
                tier2_via_surrogate_count=0,
            ),
            ohlcv_coverage_skip_count=0,
            universe_skipped_ticker_count=0,
            both_exist_diagnostic=diagnostic,
            runtime_seconds=elapsed,
            truncated_by_runtime_cap=False,
        )

    eval_run_ids = [run_id for run_id, _ in eval_runs]
    eval_run_dates = {run_id: asof_date for run_id, asof_date in eval_runs}

    # --- Load + validate RS universe ---
    universe_tickers, v2_universe_hash = load_validated_rs_universe(
        cfg, min_universe_size=min_universe_size
    )

    # --- Fetch all candidates (with eval_run_id) ---
    candidate_rows_with_run = _fetch_candidates_with_run_id(
        conn, eval_run_ids=eval_run_ids
    )
    total_candidates = len(candidate_rows_with_run)

    # Group candidates by eval_run_id for cohort-building
    by_run: dict[int, list[tuple[CandidateRow, int]]] = {}
    for cand_row, run_id in candidate_rows_with_run:
        by_run.setdefault(run_id, []).append((cand_row, run_id))

    # --- LOAD-BEARING caches (per Codex M4) ---
    # Per-TICKER OHLCV cache: keyed on ticker; full-history frame
    ohlcv_cache: dict[str, pd.DataFrame] = {}

    # Per-eval_run BatchContext cache: keyed on (eval_run_id, horizon_weeks)
    cohort_cache: dict[tuple[int, int], EvalRunCohort] = {}

    def _get_ohlcv(ticker: str) -> pd.DataFrame:
        """Return full-history DataFrame from OHLCV cache; read parquet if miss."""
        if ticker not in ohlcv_cache:
            ohlcv_cache[ticker] = read_yfinance_shape_a(ticker, cache_dir, diagnostic=diagnostic)
        return ohlcv_cache[ticker]

    def _get_cohort(run_id: int, horizon_weeks: int) -> EvalRunCohort:
        """Return EvalRunCohort from cache; build if miss."""
        key = (run_id, horizon_weeks)
        if key not in cohort_cache:
            asof_date = eval_run_dates[run_id]
            # Collect candidate tickers for Codex R2.M1 (candidate-not-in-universe)
            run_cands = by_run.get(run_id, [])
            candidate_tickers = tuple({c.ticker for c, _ in run_cands})
            cohort_cache[key] = build_eval_run_cohort(
                conn,
                eval_run_id=run_id,
                data_asof_date=asof_date,
                cfg=cfg,
                universe_tickers=universe_tickers,
                candidate_tickers=candidate_tickers,
                universe_hash=v2_universe_hash,
                cache_dir=cache_dir,
                horizon_weeks=horizon_weeks,
                diagnostic=diagnostic,
                ohlcv_getter=_get_ohlcv,  # Codex R1.M3: share per-ticker OHLCV cache
            )
        return cohort_cache[key]

    # Eagerly build baseline cohorts (default horizon_weeks) to get universe stats
    _baseline_horizon = cfg.rs.horizon_weeks
    for run_id, _ in eval_runs:
        _get_cohort(run_id, _baseline_horizon)

    universe_skipped_ticker_count = max(
        (cohort_cache[(run_id, _baseline_horizon)].universe_skipped_ticker_count
         for run_id, _ in eval_runs),
        default=0,
    )

    # --- Main sweep loop ---
    entries: list[SweepEntryV2] = []
    flipped: list[FlippedCandidate] = []

    # Global OHLCV coverage skip count (per-V2-invocation scalar, Codex R1.M3)
    # This is precomputed: a candidate that fails OHLCV coverage fails for ALL
    # sweep points. Count unique (ticker, eval_run_id) pairs that fail coverage
    # using baseline horizon (the failures are architecture-driven, not sweep-driven).
    global_ohlcv_coverage_skips = _precompute_ohlcv_coverage_skips(
        candidate_rows_with_run=candidate_rows_with_run,
        eval_run_dates=eval_run_dates,
        ohlcv_getter=_get_ohlcv,
    )

    # --- Baseline parity computed ONCE (Codex R1.M2 RESOLVED) ---
    # Run ONE baseline pass with unsubstituted cfg to populate parity counts.
    # Pre-fix: parity was tracked inside the variable loop at is_current_point,
    # causing baseline_tier_1_count / tier2_* to be inflated by N_variables
    # (each variable's current_value sweep_point re-tallied the same candidates).
    baseline_parity = _compute_baseline_parity(
        candidate_rows_with_run=candidate_rows_with_run,
        eval_runs=eval_runs,
        by_run=by_run,
        cfg=cfg,
        flipped=flipped,
        ohlcv_getter=_get_ohlcv,
        cohort_getter=_get_cohort,
    )

    truncated = False

    for var in variables:
        # Runtime cap check at variable boundary
        if max_runtime_seconds is not None and (time.monotonic() - t_start) >= max_runtime_seconds:
            truncated = True
            break

        current_aplus = current_watch = 0
        sub_entries: list[SweepEntryV2] = []

        for sweep_point in var.sweep_points:
            # Runtime cap check at sweep_point boundary
            elapsed_now = time.monotonic() - t_start
            if max_runtime_seconds is not None and elapsed_now >= max_runtime_seconds:
                truncated = True
                break

            aplus_count = 0
            watch_count = 0
            skip_count = 0
            excluded_count = 0
            out_of_range_skips = 0
            ohlcv_skips_this_point = 0
            eval_error_skips = 0

            is_current_point = (sweep_point == var.current_value)

            # Determine horizon_weeks for cohort cache key
            horizon_weeks = cfg.rs.horizon_weeks
            if var.name == "rs.horizon_weeks":
                horizon_weeks = int(sweep_point)

            for run_id, _asof_date in eval_runs:
                cohort = _get_cohort(run_id, horizon_weeks)
                run_cands = by_run.get(run_id, [])

                for cand_row, _rid in run_cands:
                    try:
                        bucket = _evaluate_candidate_under_sweep(
                            cand_row=cand_row,
                            cohort=cohort,
                            var=var,
                            sweep_point=sweep_point,
                            cfg=cfg,
                            ohlcv_getter=_get_ohlcv,
                        )
                    except OhlcvCoverageError:
                        ohlcv_skips_this_point += 1
                        continue
                    except OutOfRangeSubstitutionError:
                        out_of_range_skips += 1
                        continue
                    except Exception as exc:
                        eval_error_skips += 1
                        _logger.warning(
                            "V2 sweep: evaluation_error for ticker=%r "
                            "eval_run_id=%d variable=%r sweep_point=%r: %s",
                            cand_row.ticker, run_id, var.name, sweep_point, exc,
                        )
                        continue

                    # Count bucket
                    if bucket == "aplus":
                        aplus_count += 1
                    elif bucket == "watch":
                        watch_count += 1
                    elif bucket == "excluded":
                        excluded_count += 1
                    else:
                        skip_count += 1

            sub_entries.append(SweepEntryV2(
                variable_name=var.name,
                kind=var.kind,
                sweep_point=sweep_point,
                aplus_count=aplus_count,
                watch_count=watch_count,
                skip_count=skip_count,
                excluded_count=excluded_count,
                delta_aplus=0,  # filled below
                delta_watch=0,
                out_of_range_skip_count=out_of_range_skips,
                ohlcv_coverage_skip_count=global_ohlcv_coverage_skips,  # scalar per invocation
                evaluation_error_skip_count=eval_error_skips,
            ))

            if is_current_point:
                current_aplus = aplus_count
                current_watch = watch_count

        if truncated:
            break

        # Fill deltas relative to current_value entry
        for e in sub_entries:
            entries.append(SweepEntryV2(
                variable_name=e.variable_name,
                kind=e.kind,
                sweep_point=e.sweep_point,
                aplus_count=e.aplus_count,
                watch_count=e.watch_count,
                skip_count=e.skip_count,
                excluded_count=e.excluded_count,
                delta_aplus=e.aplus_count - current_aplus,
                delta_watch=e.watch_count - current_watch,
                out_of_range_skip_count=e.out_of_range_skip_count,
                ohlcv_coverage_skip_count=e.ohlcv_coverage_skip_count,
                evaluation_error_skip_count=e.evaluation_error_skip_count,
            ))

    elapsed = time.monotonic() - t_start
    return SweepResultV2(
        eval_runs_window=eval_runs_window,
        eval_run_id_range=(min(eval_run_ids), max(eval_run_ids)),
        total_candidates=total_candidates,
        universe_size=len(universe_tickers),
        v2_universe_hash=v2_universe_hash,
        entries=tuple(entries),
        flipped=tuple(flipped),
        baseline_parity=baseline_parity,
        ohlcv_coverage_skip_count=global_ohlcv_coverage_skips,
        universe_skipped_ticker_count=universe_skipped_ticker_count,
        both_exist_diagnostic=diagnostic,
        runtime_seconds=elapsed,
        truncated_by_runtime_cap=truncated,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_baseline_parity(
    *,
    candidate_rows_with_run: list[tuple[CandidateRow, int]],
    eval_runs: list[tuple[int, object]],
    by_run: dict[int, list[tuple[CandidateRow, int]]],
    cfg: object,
    flipped: list[FlippedCandidate],
    ohlcv_getter: object,
    cohort_getter: object,
) -> BaselineParityReport:
    """Compute baseline parity ONCE using unsubstituted cfg.

    Codex R1.M2 RESOLVED: baseline parity was computed inside the per-variable
    loop at is_current_point. With N=17 variables each having one current_value
    sweep_point, baseline_tier_1_count and tier2_* were inflated 17x.

    This helper runs ONE pass over all candidates with original cfg (no
    substitution) and produces the TRUE single-invocation baseline counts.

    Returns a BaselineParityReport with accurate (non-inflated) counts.
    """
    # Use a dummy variable-like context: evaluate with cfg unchanged.
    # We reuse _evaluate_candidate_under_sweep with a sentinel variable that
    # won't trigger any substitution -- but that function needs a SweepVariable.
    # Simpler: inline the baseline evaluation here using the existing
    # _get_ohlcv / _get_cohort interface (no substitution, just evaluate_one).
    from swing.evaluation.context import CandidateContext, MarketContext

    baseline_horizon = cfg.rs.horizon_weeks  # type: ignore[union-attr]

    tier1_mismatch_keys: list[str] = []
    tier2_match_count = 0
    tier2_mismatch_count = 0
    tier2_via_surrogate_count = 0
    baseline_tier_1_count = 0
    baseline_tier_2_count = 0

    for run_id, _asof_date in eval_runs:
        cohort = cohort_getter(run_id, baseline_horizon)
        run_cands = by_run.get(run_id, [])

        for cand_row, _rid in run_cands:
            ticker = cand_row.ticker
            asof_date = cand_row.data_asof_date

            # Get sliced OHLCV; skip on coverage failure (not a parity error)
            try:
                full_df = ohlcv_getter(ticker)
                sliced = full_df.loc[full_df.index.date <= asof_date]
                if len(sliced) < 200:
                    continue  # ohlcv_coverage_skip; not a parity candidate
            except (OhlcvCoverageError, FileNotFoundError, OSError):
                continue

            market = MarketContext()
            ctx = CandidateContext(
                ticker=ticker,
                ohlcv=sliced,
                config=cfg,
                batch=cohort.batch,
                market=market,
                current_equity=cohort.current_equity,
            )
            try:
                candidate = evaluate_one(ctx)
            except Exception as exc:
                _logger.warning(
                    "V2 baseline parity: evaluation_error for ticker=%r "
                    "eval_run_id=%d: %s",
                    ticker, run_id, exc,
                )
                continue

            bucket = candidate.bucket
            tier = classify_candidate_tier(cand_row.persisted_risk_result)

            if tier == 1:
                baseline_tier_1_count += 1
            else:
                baseline_tier_2_count += 1

            if cand_row.persisted_bucket != bucket:
                _record_flip(
                    flipped,
                    cand_row=cand_row,
                    run_id=run_id,
                    sweep_point=cfg.rs.rs_rank_min_pass,  # type: ignore[union-attr]
                    new_bucket=bucket,
                    via_surrogate=cohort.current_equity_via_surrogate,
                    variable_name=None,  # Codex R2.M2: baseline-parity flip
                )
                if tier == 1:
                    tier1_mismatch_keys.append(f"{ticker}:{run_id}")
                else:
                    tier2_mismatch_count += 1
            else:
                if tier == 2:
                    tier2_match_count += 1
                    if cohort.current_equity_via_surrogate:
                        tier2_via_surrogate_count += 1

    return BaselineParityReport(
        tier1_match=(len(tier1_mismatch_keys) == 0),
        tier1_mismatch_candidates=tuple(tier1_mismatch_keys),
        tier2_match_count=tier2_match_count,
        tier2_mismatch_count=tier2_mismatch_count,
        tier2_via_surrogate_count=tier2_via_surrogate_count,
        tier_1_count=baseline_tier_1_count,
        tier_2_count=baseline_tier_2_count,
    )


def _fetch_candidates_with_run_id(
    conn: sqlite3.Connection,
    *,
    eval_run_ids: list[int],
) -> list[tuple[CandidateRow, int]]:
    """Fetch candidates with their eval_run_id.

    Returns list of (CandidateRow, eval_run_id) tuples.
    Per cumulative gotcha #20: dynamic ? IN-clause expansion.
    Empty-input short-circuit returns [] immediately.
    """
    if not eval_run_ids:
        return []

    placeholders = ",".join("?" for _ in eval_run_ids)
    sql = f"""
        SELECT c.id, c.ticker, c.bucket, er.data_asof_date, er.id AS eval_run_id,
               cc_risk.result AS persisted_risk_result
          FROM candidates c
          JOIN evaluation_runs er ON er.id = c.evaluation_run_id
          LEFT JOIN candidate_criteria cc_risk
            ON cc_risk.candidate_id = c.id
           AND cc_risk.layer = 'risk'
           AND cc_risk.criterion_name = 'risk_feasibility'
         WHERE c.evaluation_run_id IN ({placeholders})
         ORDER BY er.id DESC, c.ticker ASC
    """
    rows = conn.execute(sql, eval_run_ids).fetchall()
    result = []
    for row in rows:
        candidate_id = row[0]
        ticker = row[1]
        bucket = row[2]
        asof_raw = row[3]
        run_id = row[4]
        risk_result = row[5]
        asof_date = parse_asof_date(asof_raw)
        cand_row = CandidateRow(
            candidate_id=candidate_id,
            ticker=ticker,
            persisted_bucket=bucket,
            data_asof_date=asof_date,
            persisted_risk_result=risk_result,
        )
        result.append((cand_row, run_id))
    return result


def _precompute_ohlcv_coverage_skips(
    *,
    candidate_rows_with_run: list[tuple[CandidateRow, int]],
    eval_run_dates: dict[int, object],
    ohlcv_getter: object,
) -> int:
    """Precompute the global OHLCV coverage skip count.

    Counts unique (ticker, eval_run_id) pairs where OHLCV sliced to
    asof_date has fewer than 200 bars (OhlcvCoverageError). This is a
    per-V2-invocation scalar (same value across all sweep points per
    Codex R1.M3 / OQ-13).
    """
    count = 0
    for cand_row, _run_id in candidate_rows_with_run:
        asof_date = cand_row.data_asof_date
        try:
            full_df = ohlcv_getter(cand_row.ticker)
            sliced = full_df.loc[full_df.index.date <= asof_date]
            if len(sliced) < 200:
                count += 1
        except (OhlcvCoverageError, FileNotFoundError, OSError):
            # FileNotFoundError / OSError: parquet absent (delisted between eval_run
            # and harness invocation) -- semantically equivalent to "no coverage";
            # tally as ohlcv_coverage_skip rather than crashing the entire sweep.
            count += 1
    return count


def _record_flip(
    flipped: list[FlippedCandidate],
    *,
    cand_row: CandidateRow,
    run_id: int,
    sweep_point: float | int,
    new_bucket: str,
    via_surrogate: bool,
    variable_name: str | None,
) -> None:
    """Append a FlippedCandidate record to flipped list.

    variable_name: name of the SweepVariable causing the flip, or None for
      baseline-parity-derived flips (Codex R2.M2 fix). output.py uses this
      to route flips to the correct section: per-variable drill-down vs.
      dedicated '## V1<->V2 Baseline Parity Drift' section.
    """
    # V1 stub: old_criterion_failure always '(none)'.
    # Computing the old criterion failure would require fetching the persisted
    # candidate_criteria rows for the old bucket from the DB (the persisted
    # Candidate evaluation result is not carried in CandidateRow). Deferred
    # to T-V2.3 output rendering; see executing-plans return report §6.
    # V2 candidate: thread the pre-sweep evaluate_one result through _record_flip
    # and emit '<criterion_name> value=<v> rule=<r>' for the first failing criterion.
    flipped.append(FlippedCandidate(
        ticker=cand_row.ticker,
        eval_run_id=run_id,
        data_asof_date=cand_row.data_asof_date.isoformat(),
        sweep_point=sweep_point,
        old_bucket=cand_row.persisted_bucket,
        new_bucket=new_bucket,
        old_criterion_failure="(none)",
        bucket_via_surrogate=via_surrogate,
        variable_name=variable_name,
    ))


def _evaluate_candidate_under_sweep(
    *,
    cand_row: CandidateRow,
    cohort: EvalRunCohort,
    var: SweepVariable,
    sweep_point: float | int,
    cfg: Config,
    ohlcv_getter: object,
) -> str:
    """Evaluate one candidate under the sweep substitution.

    Returns the V2 bucket string.

    For vcp.watch_max_fails (special-case per OQ-11 + §E.3):
      Invokes evaluate_one with production cfg (NOT substituted), then
      applies the watch_max_fails substitution on the LIVE Result tuples
      (not persisted rows). This mirrors V1's _bucket_for_substituted
      special-case for watch_max_fails.

    For all other variables:
      Substitutes cfg via substitute_cfg(), then invokes evaluate_one
      end-to-end.

    Raises:
      OhlcvCoverageError: propagated from ohlcv_getter.
      OutOfRangeSubstitutionError: raised by substitute_cfg when sweep_value
        falls outside valid range.
    """
    ticker = cand_row.ticker
    asof_date = cand_row.data_asof_date

    # Get sliced OHLCV from per-ticker cache (full-history frame already cached)
    full_df = ohlcv_getter(ticker)
    # Slice to <= asof_date (backward-looking inclusive per cumulative gotcha)
    sliced = full_df.loc[full_df.index.date <= asof_date]
    if len(sliced) < 200:
        raise OhlcvCoverageError(
            f"OHLCV insufficient for ticker={ticker!r} at asof_date={asof_date}: "
            f"sliced={len(sliced)} < min_bars=200"
        )

    market = MarketContext()

    if var.name == _VCP_WATCH_MAX_FAILS_VAR:
        # Special-case per OQ-11 + §E.3: evaluate with production cfg,
        # then override bucket with substituted watch_max_fails value
        # applied to LIVE-recomputed criteria (NOT persisted rows).
        ctx = CandidateContext(
            ticker=ticker,
            ohlcv=sliced,
            config=cfg,
            batch=cohort.batch,
            market=market,
            current_equity=cohort.current_equity,
        )
        candidate = evaluate_one(ctx)
        return _apply_watch_max_fails_override(candidate, int(sweep_point), cfg)
    else:
        # Standard path: substitute cfg, run evaluate_one end-to-end
        substituted_cfg = substitute_cfg(cfg, var.name, sweep_point)
        ctx = CandidateContext(
            ticker=ticker,
            ohlcv=sliced,
            config=substituted_cfg,
            batch=cohort.batch,
            market=market,
            current_equity=cohort.current_equity,
        )
        candidate = evaluate_one(ctx)
        return candidate.bucket


def _apply_watch_max_fails_override(
    candidate: object,
    watch_max_fails: int,
    cfg: Config,
) -> str:
    """Re-derive bucket applying a substituted watch_max_fails against
    LIVE-recomputed criteria in the Candidate object.

    Mirrors V1's _bucket_for_substituted watch_max_fails branch, but
    operates on LIVE criteria stored in candidate.criteria
    (NOT persisted candidate_criteria rows).

    Per OQ-11 + plan §E.3: vcp.watch_max_fails is hardcoded at
    swing/evaluation/scoring.py:37 (NOT a cfg field). V2 mirrors V1's
    special-case at sweep layer working against LIVE Result tuples.
    """
    criteria = candidate.criteria  # tuple[CriterionResult, ...]

    # Risk hard filter: any non-pass risk criterion -> skip
    risk_criteria = [c for c in criteria if c.layer == "risk"]
    if any(c.result != "pass" for c in risk_criteria):
        return "skip"

    # TT gate with production allowed_miss_names
    tt_criteria = [c for c in criteria if c.layer == "trend_template"]
    tt_passes = sum(1 for c in tt_criteria if c.result == "pass")
    tt_fails = [c.criterion_name for c in tt_criteria if c.result != "pass"]
    allowed = set(cfg.trend_template.allowed_miss_names)

    if tt_passes < cfg.trend_template.min_passes:
        return "skip"
    if not all(n in allowed for n in tt_fails):
        return "skip"

    # VCP gate with substituted watch_max_fails
    vcp_criteria = [c for c in criteria if c.layer == "vcp"]
    vcp_fails = sum(1 for c in vcp_criteria if c.result in ("fail", "na"))
    if vcp_fails == 0:
        return "aplus"
    if vcp_fails <= watch_max_fails:
        return "watch"
    return "skip"
