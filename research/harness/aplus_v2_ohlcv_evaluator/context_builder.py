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
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
from swing.data.repos.account_equity_snapshots import (
    get_latest_snapshot_on_or_before,
    list_snapshots,
)
from swing.evaluation.context import BatchContext
from swing.evaluation.rs import load_universe

# Shape regex per Codex R3.M2: starts with capital letter; followed by
# capital letters / digits / dots / hyphens.
_TICKER_SHAPE_RE = re.compile(r"^[A-Z][A-Z0-9.\-]*$")

_BENCHMARK_TICKER = "SPY"

# Project capital floor convention per auto-memory (max($7500, equity))
_CAPITAL_FLOOR_DOLLARS = 7500.0

# Codex R3.M1 RESOLVED: per-ticker min-bars threshold for returns_12w is
# NOT a fixed 60; it must scale with the (possibly-substituted)
# rs.horizon_weeks per production at swing/pipeline/runner.py:1060-1077
# (`bars_needed = cfg.rs.horizon_weeks * 5`; check `len(closes) > bars_needed`).
# Computed dynamically inside build_eval_run_cohort as:
#   bars_needed = horizon_weeks * 5  # candidate skip threshold for THIS run


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
    universe_skipped_ticker_count: int  # tickers with insufficient bars; per Codex C1


def parse_asof_date(raw: str) -> date:
    """Parse TEXT data_asof_date -> datetime.date.

    Raises:
      MalformedAsofDateError: when raw is not a valid ISO YYYY-MM-DD string
        (cumulative gotcha #12 -- must be typed exception, NOT TypeError deep
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
      (a) Non-empty + min_universe_size (Codex R2.M4) -> EmptyRsUniverseError.
      (b) Ticker-shape regex (Codex R3.M2) -> InvalidRsUniverseError if
          shape-invalid rows >5% of total (or >10 rows whichever is greater).
          Warning + drop otherwise. Rejected symbols enumerated (first 20).
      (c) Duplicate detection -> warning + drop.
      (d) Post-cleanup re-check (Codex R4.M2) ->
          PostCleanupUniverseTooSmallError if accepted < min_universe_size.

    Raises:
      MissingRsUniversePathError, EmptyRsUniverseError, InvalidRsUniverseError,
      PostCleanupUniverseTooSmallError.
    """
    rs_path = cfg.paths.rs_universe_path
    if rs_path is None:
        raise MissingRsUniversePathError(
            "cfg.paths.rs_universe_path is None; V2 requires a valid RS universe path. "
            "Set paths.rs_universe_path in swing.config.toml."
        )
    rs_path = Path(rs_path)

    try:
        universe = load_universe(rs_path)
    except FileNotFoundError as exc:
        raise MissingRsUniversePathError(
            f"RS universe file not found at {rs_path!r}: {exc}"
        ) from exc
    except PermissionError as exc:
        raise MissingRsUniversePathError(
            f"RS universe file unreadable at {rs_path!r}: {exc}"
        ) from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise InvalidRsUniverseError(
            f"RS universe file malformed at {rs_path!r}: {exc}"
        ) from exc

    raw_tickers = list(universe.tickers)  # already sorted + dedup by load_universe

    # (a) Initial empty check (zero-tickers case -- truly empty file)
    if len(raw_tickers) == 0:
        raise EmptyRsUniverseError(
            f"RS universe is empty (0 tickers after load_universe); path={rs_path!r}"
        )

    # (b) Shape regex validation
    valid_tickers = []
    invalid_tickers = []
    invalid_count = 0  # initialize before conditional block to avoid NameError in (d)
    for t in raw_tickers:
        if _TICKER_SHAPE_RE.match(t):
            valid_tickers.append(t)
        else:
            invalid_tickers.append(t)

    if invalid_tickers:
        invalid_count = len(invalid_tickers)
        total_count = len(raw_tickers)
        invalid_pct = invalid_count / total_count if total_count > 0 else 0.0
        first_20 = invalid_tickers[:20]

        if invalid_pct > 0.05 and invalid_count > 10:
            raise InvalidRsUniverseError(
                f"RS universe has {invalid_count}/{total_count} ({invalid_pct:.1%}) "
                f"shape-invalid tickers (exceeds 5% + >10 row threshold); "
                f"first 20 invalid: {first_20!r}; path={rs_path!r}"
            )
        else:
            warnings.warn(
                f"RS universe: dropping {invalid_count} shape-invalid tickers "
                f"({first_20!r}); accepted {len(valid_tickers)}/{total_count}",
                UserWarning,
                stacklevel=2,
            )

    # (c) Duplicate detection (load_universe already deduplicates via sorted(set(...))
    # but we do an explicit check in case the contract changes)
    seen = set()
    dedup_tickers = []
    dup_count = 0
    for t in valid_tickers:
        if t in seen:
            dup_count += 1
        else:
            seen.add(t)
            dedup_tickers.append(t)

    if dup_count > 0:
        warnings.warn(
            f"RS universe: dropping {dup_count} duplicate tickers; "
            f"accepted {len(dedup_tickers)} unique tickers",
            UserWarning,
            stacklevel=2,
        )

    # (d) Post-cleanup re-check
    if len(dedup_tickers) < min_universe_size:
        raise PostCleanupUniverseTooSmallError(
            f"RS universe post-cleanup has {len(dedup_tickers)} accepted tickers "
            f"(< min_universe_size={min_universe_size}); "
            f"dropped {invalid_count} invalid + {dup_count} duplicates; "
            f"path={rs_path!r}"
        )

    accepted = tuple(sorted(dedup_tickers))

    # Compute v2_universe_hash = "v2_universe_hash_" + SHA-256 of sorted tuple bytes
    hash_bytes = "\n".join(accepted).encode("utf-8")
    sha256_hex = hashlib.sha256(hash_bytes).hexdigest()
    v2_universe_hash = f"v2_universe_hash_{sha256_hex}"

    return accepted, v2_universe_hash


def fetch_eval_runs(
    conn: sqlite3.Connection,
    *,
    eval_runs_window: int,
) -> list[tuple[int, date]]:
    """SELECT id, data_asof_date FROM evaluation_runs ORDER BY id DESC
    LIMIT ?. Returns list of (eval_run_id, parsed asof_date).

    Per cumulative gotcha #12: TEXT data_asof_date -> date via parse_asof_date.
    """
    rows = conn.execute(
        "SELECT id, data_asof_date FROM evaluation_runs ORDER BY id DESC LIMIT ?",
        (eval_runs_window,),
    ).fetchall()
    return [(row[0], parse_asof_date(row[1])) for row in rows]


def fetch_candidates(
    conn: sqlite3.Connection,
    *,
    eval_run_ids: list[int],
    eval_run_dates: dict[int, date],
) -> list[CandidateRow]:
    """SELECT candidates + LEFT JOIN risk_feasibility per spec §F.3 SQL
    skeleton (Codex R2.M3 amended).

    Per cumulative gotcha #20 (Expansion #4 sub-refinement BINDING):
    dynamic ? IN-clause expansion (NOT single :name placeholder which
    sqlite3 cannot bind a list to).

    JOIN-cardinality:
      - candidates JOIN evaluation_runs ON er.id = c.evaluation_run_id: 1:1
      - candidates LEFT JOIN candidate_criteria cc_risk: 1:0-or-1

    Empty-input short-circuit (cumulative gotcha #20):
    returns empty list immediately when eval_run_ids is empty.
    """
    if not eval_run_ids:
        return []

    # Dynamic ? expansion per Codex R1.M1 RESOLVED (cumulative gotcha #20)
    placeholders = ",".join("?" for _ in eval_run_ids)
    sql = f"""
        SELECT c.id, c.ticker, c.bucket, er.data_asof_date,
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
        risk_result = row[4]
        asof_date = parse_asof_date(asof_raw)
        result.append(CandidateRow(
            candidate_id=candidate_id,
            ticker=ticker,
            persisted_bucket=bucket,
            data_asof_date=asof_date,
            persisted_risk_result=risk_result,
        ))
    return result


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
    ohlcv_getter: object = None,  # Codex R1.M3: optional per-ticker OHLCV cache
) -> EvalRunCohort:
    """Build the BatchContext + resolve current_equity surrogate for one
    (eval_run_id, data_asof_date) cohort.

    Steps:
      1. For each ticker in `universe_tickers union candidate_tickers union {SPY}`
         (Codex R2.M1 RESOLVED): read Shape A (via ohlcv_getter cache when
         provided, else direct parquet read per Codex R1.M3 Option A);
         slice to <= data_asof_date; compute `horizon_weeks * 5`-bar trailing
         return (per-ticker skip if `len(closes) <= horizon_weeks * 5` per
         production at `swing/pipeline/runner.py:1060-1077`).
      2. SPY return -> spy_return_12w (fallback 0.0 if missing).
      3. current_equity per OQ-15: query account_equity_snapshots;
         fallback to most-recent; fallback to floor surrogate.
      4. Construct BatchContext + return EvalRunCohort.

    Args:
      ohlcv_getter: optional callable(ticker: str) -> full-history DataFrame
        (same contract as sweep.py's _get_ohlcv). When provided, uses the
        per-ticker OHLCV cache from the sweep orchestrator (Codex R1.M3
        Option A: dependency injection to share cache between build_eval_run_cohort
        and the main sweep loop). When None (default, backward-compatible),
        falls back to direct read_yfinance_shape_a / read_yfinance_shape_a_sliced.
    """
    cache_dir = Path(cache_dir)
    bars_needed = horizon_weeks * 5  # Codex R3.M1: scales with horizon_weeks

    # Build the union ticker set: full RS universe + candidate tickers + SPY
    all_tickers = set(universe_tickers) | set(candidate_tickers) | {_BENCHMARK_TICKER}

    returns_12w_by_ticker: dict[str, float] = {}
    skipped_count = 0

    for ticker in all_tickers:
        try:
            if ohlcv_getter is not None:
                # Use injected per-ticker cache (Codex R1.M3 Option A).
                # _get_ohlcv returns full-history frame; slice here.
                full_df = ohlcv_getter(ticker)
                df = full_df.loc[full_df.index.date <= data_asof_date]
                if len(df) < 1:
                    skipped_count += 1
                    continue
            else:
                # Fallback: direct read (backward-compatible; used in isolated
                # unit tests that don't have a sweep-level ohlcv_getter).
                df = read_yfinance_shape_a_sliced(
                    ticker, cache_dir,
                    asof_date=data_asof_date,
                    min_bars=1,  # We gate on bars_needed below; coverage gate (200) is separate
                    diagnostic=diagnostic,
                )
        except (OhlcvCoverageError, FileNotFoundError, OSError):
            skipped_count += 1
            continue

        closes = df["Close"]
        # Per production at swing/pipeline/runner.py:1060-1077:
        # skip ticker if len(closes) <= bars_needed (NOT <; strict inequality)
        if len(closes) <= bars_needed:
            skipped_count += 1
            continue

        # Compute horizon_weeks * 5 bar trailing return
        end_price = float(closes.iloc[-1])
        start_price = float(closes.iloc[-(bars_needed + 1)])
        if start_price > 0:
            returns_12w_by_ticker[ticker] = (end_price - start_price) / start_price
        else:
            skipped_count += 1

    # SPY return fallback 0.0 if missing
    spy_return_12w = returns_12w_by_ticker.get(_BENCHMARK_TICKER, 0.0)

    # current_equity per OQ-15: historical -> most-recent -> floor surrogate
    current_equity_via_surrogate = False
    current_equity = _CAPITAL_FLOOR_DOLLARS  # initial fallback

    snapshot = get_latest_snapshot_on_or_before(conn, asof_date=data_asof_date.isoformat())
    if snapshot is not None:
        current_equity = float(snapshot.equity_dollars)
    else:
        # Fallback: most-recent snapshot (any date)
        recent_snapshots = list_snapshots(conn, limit=1)
        if recent_snapshots:
            current_equity = float(recent_snapshots[0].equity_dollars)
            current_equity_via_surrogate = True
        else:
            # No snapshots at all: use project capital floor per auto-memory
            current_equity = _CAPITAL_FLOOR_DOLLARS
            current_equity_via_surrogate = True

    # Apply project floor convention: max($7500 floor, actual balance)
    current_equity = max(_CAPITAL_FLOOR_DOLLARS, current_equity)

    batch = BatchContext(
        returns_12w_by_ticker=returns_12w_by_ticker,
        universe_tickers=universe_tickers,
        universe_version=universe_hash,  # use V2 hash as universe_version
        universe_hash=universe_hash,
        spy_return_12w=spy_return_12w,
    )

    return EvalRunCohort(
        eval_run_id=eval_run_id,
        data_asof_date=data_asof_date,
        batch=batch,
        current_equity=current_equity,
        current_equity_via_surrogate=current_equity_via_surrogate,
        universe_skipped_ticker_count=skipped_count,
    )


def classify_candidate_tier(persisted_risk_result: str | None) -> int:
    """Per spec §E.4 Codex R2.M3 (Codex R1.C1-amended):
      Tier 1 = bucket is INDEPENDENT of risk gate outcome:
        - persisted_risk_result == 'pass': risk passed; bucket determined by TT/VCP
          gates (risk was not the load-bearing gate).
        - persisted_risk_result is None: LEFT JOIN miss -- risk criterion was NOT
          persisted for this candidate (historical eval-run predating risk_feasibility
          criterion, or pre-schema-v-risk row). Risk was not evaluated => bucket
          independent of risk => tier-1.
      Tier 2 = bucket DEPENDED on risk gate outcome:
        - persisted_risk_result == 'fail': risk hard-filtered the candidate to 'skip'
          (risk WAS evaluated and failed => load-bearing).
        - persisted_risk_result == 'na': risk returned insufficient-data => treated as
          fail by bucket_for => risk was load-bearing for skip outcome.

    Returns: 1 (tier-1 EXACT parity required) or 2 (tier-2 CONDITIONAL via surrogate).

    Discriminating cases (Codex R1.C1 fix):
      pass  -> 1  (risk passed; non-load-bearing)
      None  -> 1  (risk not evaluated; non-load-bearing; was incorrectly tier-2 pre-fix)
      fail  -> 2  (risk blocked the candidate)
      na    -> 2  (risk returned insufficient-data; treated as fail by bucket_for)
    """
    return 1 if persisted_risk_result in ("pass", None) else 2
