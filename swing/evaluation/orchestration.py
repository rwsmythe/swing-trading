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
from dataclasses import replace as _dc_replace
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from swing.data.models import Candidate, EvaluationRun
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.evaluation.evaluator import evaluate_batch


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
    out = output if output is not None else OrchestrationOutput()

    # 1. ticker extraction + sector/industry passthrough map (lifted verbatim).
    finviz_df = pd.read_csv(csv_path)
    if "Ticker" not in finviz_df.columns:
        raise ValueError(f"finviz CSV missing 'Ticker' column: {list(finviz_df.columns)}")
    tickers = finviz_df["Ticker"].dropna().astype(str).str.upper().tolist()

    sector_industry_by_ticker: dict[str, tuple[str, str]] = {}
    for _, fv_row in finviz_df.iterrows():
        t_raw = fv_row.get("Ticker")
        if pd.isna(t_raw):
            continue
        ticker_key = str(t_raw).upper()
        sec = fv_row.get("Sector", "")
        ind = fv_row.get("Industry", "")
        sec = "" if pd.isna(sec) else str(sec)
        ind = "" if pd.isna(ind) else str(ind)
        sector_industry_by_ticker[ticker_key] = (sec, ind)

    # 2. Universe augmentation: held (close-only) then pins (full eval).
    #    DIVERGENCE-1/2 (intentional): the pipeline supplies these sets; the CLI
    #    supplies an empty UniverseAugmentation.
    held_tickers = list(augmentation.held_tickers)
    seen = set(tickers)
    for t in held_tickers:
        if t not in seen:
            tickers.append(t)
            seen.add(t)
    injected_pins = [t for t in augmentation.pinned_inject if t not in seen]
    for t in injected_pins:
        tickers.append(t)
        seen.add(t)
    if injected_pins:
        out.note_pin_injection(injected_pins)

    # 3. LOCK #16: the pipeline's warm + prewarm fire here, at the held-tickers
    #    boundary (after augmentation, before the fetch loops), with the full
    #    screen∪held∪pins set. The CLI passes None.
    if pre_fetch_hook is not None:
        pre_fetch_hook(list(tickers))

    # 4. SPY benchmark fetch -- DIVERGENCE-SPY-GUARD (intentional policy field).
    spy_return = 0.0
    weeks = cfg.rs.horizon_weeks
    if behavior.spy_failure_mode == "warn_and_zero":
        try:
            spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=as_of_date)
            spy_closes = spy_df["Close"]
            if len(spy_closes) > weeks * 5:
                bars = weeks * 5
                spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)
            else:
                out.warn(
                    f"Warning: SPY has only {len(spy_closes)} bars, "
                    f"need {weeks * 5 + 1}. Using 0.0."
                )
        except Exception as exc:  # noqa: BLE001 -- CLI tolerates any fetch failure
            out.warn(f"Warning: SPY benchmark fetch failed ({exc}), using 0.0")
    elif behavior.spy_failure_mode == "raise":
        spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=as_of_date)
        spy_closes = spy_df["Close"]
        if len(spy_closes) > weeks * 5:
            bars = weeks * 5
            spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)
    else:
        raise ValueError(f"unknown spy_failure_mode: {behavior.spy_failure_mode!r}")

    # 5. Per-ticker OHLCV fetch + universe returns for RS ranking (lifted).
    returns_12w: dict[str, float] = {}
    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
    error_tickers: list[str] = []
    bars_needed = cfg.rs.horizon_weeks * 5
    for t in tickers:
        try:
            df = fetcher.get(t, lookback_days=400, as_of_date=as_of_date)
            ohlcv_by_ticker[t] = df
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception as exc:  # noqa: BLE001
            # Output seam: the CLI echoes per-ticker fetch errors to stderr; the
            # pipeline's warn channel is a no-op (it never emitted these).
            out.warn(f"  {t}: fetch error - {exc}")
            error_tickers.append(t)
    for t in universe.tickers:
        if t in returns_12w:
            continue
        try:
            df = fetcher.get(t, lookback_days=120, as_of_date=as_of_date)
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:  # noqa: BLE001 -- universe RS returns are best-effort
            pass

    # 6. Batch context.
    batch = BatchContext(
        returns_12w_by_ticker=returns_12w,
        universe_tickers=universe.tickers,
        universe_version=universe.version,
        universe_hash=universe_hash,
        spy_return_12w=spy_return,
    )

    # 7. Dates (run_now captured once by the adapter). The three-branch data_asof
    #    is the CLI's form; the pipeline (as_of_date always None) is a subset.
    max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
    if max_dates:
        data_asof = max(max_dates).date()
    elif as_of_date is not None:
        data_asof = as_of_date
    else:
        data_asof = last_completed_session(run_now)
    action_session = action_session_for_run(run_now)

    # 8. Build contexts. Held + ETF blocklist are excluded from evaluation;
    #    current_equity is the injected sizing equity (DIVERGENCE-EQUITY unified).
    held_set = set(held_tickers)
    excluded = set(cfg.etf_exclusion.manual_block) | held_set
    excluded_tickers: list[str] = []
    contexts: list[CandidateContext] = []
    for t in tickers:
        if t in excluded:
            excluded_tickers.append(t)
            continue
        if t not in ohlcv_by_ticker:
            continue
        contexts.append(CandidateContext(
            ticker=t, ohlcv=ohlcv_by_ticker[t], config=cfg,
            batch=batch, market=MarketContext(),
            current_equity=current_equity,
        ))

    # 9. Evaluate.
    candidates = evaluate_batch(contexts)

    # 10. Synthesize excluded rows. DIVERGENCE-EXCLUDED-CLOSE (unified): preserve
    #     the fetched close when available; ETF blocklist rows that were never
    #     fetched still carry close=None.
    for t in excluded_tickers:
        close = None
        if t in ohlcv_by_ticker:
            df = ohlcv_by_ticker[t]
            if not df.empty:
                close = float(df["Close"].iloc[-1])
        notes = "open position" if t in held_set else "ETF/fund blocklist"
        candidates.append(Candidate(
            ticker=t, bucket="excluded",
            close=close, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes=notes, criteria=(),
        ))

    # 11. Synthesize error rows. DIVERGENCE-ERROR-DEDUP (unified): an excluded
    #     ticker never also emits an error row (avoids the watchlist last-write
    #     blanking AND the candidates UNIQUE(run_id, ticker) IntegrityError).
    error_tickers = [t for t in error_tickers if t not in excluded]
    for t in error_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="error",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
        ))

    # 12. Plumb Sector/Industry uniformly across every bucket.
    candidates = [
        _dc_replace(
            c,
            sector=sector_industry_by_ticker.get(c.ticker, ("", ""))[0],
            industry=sector_industry_by_ticker.get(c.ticker, ("", ""))[1],
        )
        for c in candidates
    ]

    # 13. Run row.
    run = EvaluationRun(
        id=None,
        run_ts=run_now.isoformat(timespec="seconds"),
        data_asof_date=data_asof.isoformat(),
        action_session_date=action_session.isoformat(),
        finviz_csv_path=str(csv_path),
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=len(excluded_tickers),
        error_count=len(error_tickers),
        rs_universe_version=universe.version,
        rs_universe_hash=universe_hash,
    )

    # 14. Persist (LOCK #1): the adapter owns the transaction strategy.
    run_id = persist(run, candidates)
    return OrchestrationResult(run_id=run_id, run=run, candidates=candidates)
