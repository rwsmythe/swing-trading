"""Production-DB read + harness-input reconstruction for parity check.

This module is the parity check's reconstruction primitive. It mirrors
``swing/pipeline/runner.py:_step_evaluate`` exactly so the harness side
of the comparison sees identical inputs to what production saw at run
time. Three public surfaces:

- :func:`fetch_production` — read the production candidates + criteria
  for a given ``evaluation_run_id``.
- :func:`select_default_evaluation_run` — auto-pick the most-recent run
  whose Finviz CSV is still present (skipping rotated CSVs).
- :func:`reconstruct_harness_inputs` — build the per-ticker
  ``CandidateContext`` set for the harness to call ``evaluate_one`` on.
  The BatchContext universe is the FULL ``rs-universe.csv`` (verified
  against production's recorded ``rs_universe_hash``); ``current_equity``
  uses the ``sizing_equity(current_equity(starting, exits, cash), floor)``
  formula production uses.

Phase isolation: read-only consumption of ``swing.data``, ``swing.config``,
``swing.evaluation``, ``swing.prices``, ``swing.trades.equity``. No DB
mutations.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from swing.config import Config
from swing.data.models import Candidate, Trade
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import list_open_trades
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.trades.equity import current_equity, sizing_equity


# C.14 migration helper (was: list_all_exits shim from repos/trades.py).
# Mirrors the _ExitShape adapter used in web view models, journal/stats,
# review_log repo, and pipeline runner — duck-typed Exit-shape over fills
# filtered to non-entry actions. Dies in a future cleanup phase when
# equity.py refactors to consume Fill directly.
@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str | None
    realized_pnl: float | None
    r_multiple: float | None


def _list_all_exitshape_via_fills(
    conn: sqlite3.Connection,
) -> list[_ExitShape]:
    """C.14 migration: return the ExitLike collection that the
    deleted ``list_all_exits(conn)`` shim previously returned, sourced
    from fills (action != 'entry'). Per-fill realized_pnl / r_multiple
    derive on the fly via ``swing.trades.derived_metrics`` — single
    source of math truth. Sort matches the legacy shim via
    ``list_all_fills``'s ``ORDER BY fill_datetime ASC, fill_id ASC``.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import list_closed_trades
    from swing.trades.derived_metrics import (
        initial_risk_per_share,
        r_multiple,
        realized_pnl,
    )

    trades_by_id: dict[int, Trade] = {}
    for t in list_open_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t
    for t in list_closed_trades(conn):
        if t.id is not None:
            trades_by_id[t.id] = t

    out: list[_ExitShape] = []
    for f in list_all_fills(conn):
        if f.action == "entry":
            continue
        trade = trades_by_id.get(f.trade_id)
        if trade is None:
            continue  # orphan fill — skip (parent trade missing)
        rps = initial_risk_per_share(
            entry_price=trade.entry_price,
            initial_stop=trade.initial_stop,
        )
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        if rps == 0 or f.quantity == 0:
            rmult: float | None = None
        else:
            rmult = r_multiple(
                realized_pnl=pnl, initial_risk_per_share=rps,
                quantity=f.quantity,
            )
        exit_date = (
            f.fill_datetime.split("T")[0]
            if "T" in f.fill_datetime else f.fill_datetime
        )
        out.append(_ExitShape(
            trade_id=f.trade_id,
            exit_date=exit_date,
            exit_price=float(f.price),
            shares=int(f.quantity),
            reason=f.reason,
            realized_pnl=pnl,
            r_multiple=rmult,
        ))
    return out

log = logging.getLogger(__name__)

_EVALUATED_BUCKETS = frozenset({"aplus", "watch", "skip"})


class NoRunsWithCsvError(RuntimeError):
    """No production evaluation_runs row has a present Finviz CSV."""


@dataclass(frozen=True)
class HarnessInputs:
    """Bundle of inputs the harness needs to evaluate the comparison set.

    ``contexts_by_ticker`` keys are the comparison set: tickers production
    placed in ``{aplus, watch, skip}`` (i.e., ran through ``evaluate_one``).
    ``skipped_tickers`` records tickers that were in the comparison set
    on the production side but couldn't be re-evaluated by the harness
    (typically yfinance fetch failures), with a short reason string.
    """
    evaluation_run_id: int
    data_asof_date: str
    finviz_csv_path: str | None
    contexts_by_ticker: dict[str, CandidateContext]
    skipped_tickers: dict[str, str]
    current_equity: float
    equity_derivation: str
    universe_version_recorded: str | None
    universe_version_current: str
    universe_hash_recorded: str | None
    universe_hash_current: str
    universe_match_with_production: bool
    universe_size: int
    cache_hits: int
    cache_misses: int


def fetch_production(
    conn: sqlite3.Connection, evaluation_run_id: int,
) -> dict[str, Candidate]:
    """Return ``{ticker: Candidate}`` for the given evaluation run.

    Wraps :func:`swing.data.repos.candidates.fetch_candidates_for_run`,
    re-keying the list by ticker for direct comparison with the harness
    output. Empty dict if the run has no candidates (or doesn't exist).
    """
    candidates = fetch_candidates_for_run(conn, evaluation_run_id)
    return {c.ticker: c for c in candidates}


def select_default_evaluation_run(
    conn: sqlite3.Connection, finviz_inbox_dir: Path,
) -> int:
    """Most-recent eval run whose Finviz CSV is still present.

    Walks ``evaluation_runs`` ordered by ``run_ts DESC``. Returns the
    first run whose ``finviz_csv_path`` either exists at the recorded
    absolute path OR exists by basename inside the supplied inbox
    directory (covers cross-machine DB moves where the absolute path is
    stale but the file is still available).

    Skips runs with NULL ``finviz_csv_path``. Raises
    :class:`NoRunsWithCsvError` if no run qualifies.
    """
    rows = conn.execute(
        "SELECT id, finviz_csv_path FROM evaluation_runs "
        "WHERE finviz_csv_path IS NOT NULL "
        "ORDER BY run_ts DESC"
    ).fetchall()
    inbox = Path(finviz_inbox_dir)
    for run_id, csv_path in rows:
        absolute = Path(csv_path)
        if absolute.exists():
            return int(run_id)
        basename_in_inbox = inbox / absolute.name
        if basename_in_inbox.exists():
            return int(run_id)
    raise NoRunsWithCsvError(
        f"No evaluation_runs row has a present Finviz CSV under {inbox}"
    )


def _compute_returns_12w(
    closes: pd.Series, horizon_weeks: int,
) -> float | None:
    """Mirror ``_step_evaluate`` lines 316-318, 329-330, 339-340.

    Returns ``(closes.iloc[-1] / closes.iloc[-bars-1]) - 1`` where
    ``bars = horizon_weeks * 5``. ``None`` when the series is too short.
    """
    bars = horizon_weeks * 5
    if len(closes) <= bars:
        return None
    start = float(closes.iloc[-bars - 1])
    if start <= 0:
        return None
    return float(closes.iloc[-1]) / start - 1.0


def _derive_current_equity(conn: sqlite3.Connection, cfg: Config) -> tuple[float, str]:
    """Re-run ``_step_evaluate`` lines 358-369 against the supplied conn.

    Returns ``(value, derivation_string)`` so the manifest can record
    both the resulting number and the formula used.
    """
    real = current_equity(
        starting_equity=cfg.account.starting_equity,
        exits=_list_all_exitshape_via_fills(conn),
        cash_movements=list_cash(conn),
    )
    sized = sizing_equity(
        real_equity=real, floor=cfg.account.risk_equity_floor,
    )
    derivation = (
        f"sizing_equity(real_equity=current_equity(starting={cfg.account.starting_equity}, "
        f"exits, cash_movements), floor={cfg.account.risk_equity_floor}) → "
        f"real={real:.2f} sized={sized:.2f}"
    )
    return sized, derivation


def reconstruct_harness_inputs(
    *,
    conn: sqlite3.Connection,
    evaluation_run_id: int,
    fetcher,
    cfg: Config,
    finviz_tickers: tuple[str, ...],
) -> HarnessInputs:
    """Build the harness inputs to mirror ``_step_evaluate`` exactly.

    Steps mirror runner.py:_step_evaluate:
      - Load the rs-universe at ``cfg.paths.rs_universe_path`` and verify
        the hash against the production eval row. Mismatch is recorded
        but not fatal (manifest flags the drift).
      - Fetch OHLCV for ``finviz_tickers`` ∪ held_tickers (lookback 400d).
      - Fetch OHLCV for ``universe.tickers`` not yet covered (lookback 120d)
        purely for ``returns_12w`` cross-section.
      - Fetch SPY OHLCV (lookback 365d) for spy_return_12w.
      - Build BatchContext with FULL universe.tickers.
      - Derive ``current_equity`` via the production formula.
      - Build CandidateContext for tickers in the production-evaluated
        comparison set ({aplus, watch, skip}). Held + ETF-blocklist
        tickers are out of the comparison per D1 §"Comparison primitive."

    yfinance fetch failures are non-fatal: the failed ticker is recorded
    in ``skipped_tickers`` and dropped from the comparison set.
    """
    eval_meta = conn.execute(
        "SELECT data_asof_date, finviz_csv_path, rs_universe_version, "
        "rs_universe_hash FROM evaluation_runs WHERE id = ?",
        (evaluation_run_id,),
    ).fetchone()
    if eval_meta is None:
        raise ValueError(f"evaluation_run_id={evaluation_run_id} not found")
    data_asof_date, finviz_csv_path, universe_version_recorded, \
        universe_hash_recorded = eval_meta

    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash_current = universe_version_hash(cfg.paths.rs_universe_path)

    # Production candidate set governs the comparison.
    prod_candidates = fetch_production(conn, evaluation_run_id)
    comparison_tickers: tuple[str, ...] = tuple(sorted(
        t for t, c in prod_candidates.items() if c.bucket in _EVALUATED_BUCKETS
    ))

    held_tickers = sorted({t.ticker.upper() for t in list_open_trades(conn)})

    # Mirror _step_evaluate's tickers list construction (finviz + held, deduped).
    primary_tickers: list[str] = []
    seen: set[str] = set()
    for t in finviz_tickers + tuple(held_tickers):
        u = t.upper()
        if u not in seen:
            primary_tickers.append(u)
            seen.add(u)

    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
    skipped_tickers: dict[str, str] = {}
    returns_12w: dict[str, float] = {}
    cache_hits = 0
    cache_misses = 0

    def _fetch(ticker: str, lookback_days: int) -> pd.DataFrame | None:
        nonlocal cache_hits, cache_misses
        try:
            df = fetcher.get(
                ticker, lookback_days=lookback_days,
                as_of_date=_data_asof_to_date(data_asof_date),
            )
        except Exception:
            return None
        # Track cache stats heuristically — :class:`PriceFetcher` exposes
        # cache_hits/misses on the instance after the test_fetcher mock
        # interface; if the supplied object lacks them, fall back to
        # treating every call as a miss.
        return df

    # SPY (line 313-318).
    spy_return_12w = 0.0
    spy_df = _fetch(cfg.rs.benchmark_ticker, 365)
    if spy_df is not None and not spy_df.empty:
        ret = _compute_returns_12w(spy_df["Close"], cfg.rs.horizon_weeks)
        if ret is not None:
            spy_return_12w = ret

    # Primary tickers: finviz + held, lookback 400 (line 324-332).
    for t in primary_tickers:
        df = _fetch(t, 400)
        if df is None:
            skipped_tickers[t] = "harness OHLCV fetch failed (primary)"
            continue
        ohlcv_by_ticker[t] = df
        ret = _compute_returns_12w(df["Close"], cfg.rs.horizon_weeks)
        if ret is not None:
            returns_12w[t] = ret

    # Universe-only tickers: lookback 120 for returns_12w only (line 333-342).
    for t in universe.tickers:
        if t in returns_12w:
            continue
        df = _fetch(t, 120)
        if df is None:
            continue  # silently skipped per production semantics
        ret = _compute_returns_12w(df["Close"], cfg.rs.horizon_weeks)
        if ret is not None:
            returns_12w[t] = ret

    # Cache stats (only meaningful if fetcher exposes them).
    if hasattr(fetcher, "hits") and hasattr(fetcher, "misses"):
        cache_hits = int(fetcher.hits)
        cache_misses = int(fetcher.misses)

    batch = BatchContext(
        returns_12w_by_ticker=returns_12w,
        universe_tickers=universe.tickers,
        universe_version=universe.version,
        universe_hash=universe_hash_current,
        spy_return_12w=spy_return_12w,
    )
    market = MarketContext()

    sizing_eq, equity_derivation = _derive_current_equity(conn, cfg)

    contexts_by_ticker: dict[str, CandidateContext] = {}
    for t in comparison_tickers:
        if t not in ohlcv_by_ticker:
            # Either the ticker wasn't in finviz_tickers (orchestration bug)
            # or its OHLCV fetch failed. The skipped_tickers record above
            # captures the latter; the former should not occur in practice
            # since comparison_tickers ⊆ finviz_tickers ∪ held_tickers in
            # production semantics.
            skipped_tickers.setdefault(
                t, "no OHLCV available (not in finviz_tickers or fetch failed)",
            )
            continue
        contexts_by_ticker[t] = CandidateContext(
            ticker=t, ohlcv=ohlcv_by_ticker[t], config=cfg,
            batch=batch, market=market, current_equity=sizing_eq,
        )

    universe_match = (
        universe_hash_recorded is not None
        and universe_hash_current == universe_hash_recorded
    )

    return HarnessInputs(
        evaluation_run_id=evaluation_run_id,
        data_asof_date=str(data_asof_date),
        finviz_csv_path=finviz_csv_path,
        contexts_by_ticker=contexts_by_ticker,
        skipped_tickers=skipped_tickers,
        current_equity=sizing_eq,
        equity_derivation=equity_derivation,
        universe_version_recorded=universe_version_recorded,
        universe_version_current=universe.version,
        universe_hash_recorded=universe_hash_recorded,
        universe_hash_current=universe_hash_current,
        universe_match_with_production=universe_match,
        universe_size=len(universe.tickers),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


def _data_asof_to_date(data_asof_date: str | None):
    """Translate the eval row's ``data_asof_date`` (YYYY-MM-DD string) to
    a ``date`` object, or ``None`` if the column was NULL.

    Passing ``as_of_date=<production data_asof>`` to ``PriceFetcher.get``
    pins the cache key to production's session boundary, maximizing
    cache hits when production's parquet files are still on disk.
    """
    if data_asof_date is None:
        return None
    from datetime import date as _date
    return _date.fromisoformat(str(data_asof_date))
