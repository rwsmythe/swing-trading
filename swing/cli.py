"""Click CLI for swing. Phase 1 subcommands: db-migrate, eval."""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run
from swing.evaluation.evaluator import evaluate_batch
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.prices import PriceFetcher


@click.group()
@click.option("--config", "config_path", default="swing.config.toml",
              help="Path to swing.config.toml")
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """Swing trading CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(Path(config_path))


@main.command("db-migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply DB migrations. Safe to run multiple times. Backs up DB before migrating."""
    import shutil

    cfg = ctx.obj["config"]
    db_path = cfg.paths.db_path

    # Spec §3: CLI db-migrate takes an automatic backup before running any migration.
    if db_path.exists():
        cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = cfg.paths.backups_dir / f"swing-{ts}.db"
        shutil.copy2(db_path, backup_path)
        click.echo(f"Backup: {backup_path}")

    conn = ensure_schema(db_path)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()
    click.echo(f"DB at {db_path} - schema version {version}")


@main.command("eval")
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--as-of-date", "as_of_date_str", default=None,
              help="YYYY-MM-DD - cap OHLCV data to bars <= this date (for parity).")
@click.pass_context
def eval_cmd(ctx: click.Context, csv_path: str, as_of_date_str: str | None) -> None:
    """Evaluate tickers from a Finviz-style CSV."""
    cfg = ctx.obj["config"]
    csv_file = Path(csv_path)
    as_of_date = _date.fromisoformat(as_of_date_str) if as_of_date_str else None

    # 1. Read tickers — require a `Ticker` column; fail fast on malformed CSV
    finviz_df = pd.read_csv(csv_file)
    if "Ticker" not in finviz_df.columns:
        raise click.ClickException(
            f"{csv_file.name}: required column 'Ticker' not found. "
            f"Got columns: {list(finviz_df.columns)}"
        )
    tickers = finviz_df["Ticker"].dropna().astype(str).str.upper().tolist()

    click.echo(f"Evaluating {len(tickers)} tickers from {csv_file.name}")

    # 2. Load RS universe
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)

    fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)

    # 3. Fetch SPY benchmark
    spy_return = 0.0
    try:
        spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=as_of_date)
        spy_closes = spy_df["Close"]
        weeks = cfg.rs.horizon_weeks
        if len(spy_closes) > weeks * 5:
            bars = weeks * 5
            spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)
        else:
            click.echo(
                f"Warning: SPY has only {len(spy_closes)} bars, need {weeks * 5 + 1}. Using 0.0.",
                err=True,
            )
    except Exception as exc:
        click.echo(f"Warning: SPY benchmark fetch failed ({exc}), using 0.0", err=True)

    # 4. Fetch OHLCV per ticker
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
        except Exception as exc:
            click.echo(f"  {t}: fetch error - {exc}", err=True)
            error_tickers.append(t)

    # Fetch universe returns for RS ranking
    for t in universe.tickers:
        if t in returns_12w:
            continue
        try:
            df = fetcher.get(t, lookback_days=120, as_of_date=as_of_date)
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:
            pass

    batch = BatchContext(
        returns_12w_by_ticker=returns_12w,
        universe_tickers=universe.tickers,
        universe_version=universe.version,
        universe_hash=universe_hash,
        spy_return_12w=spy_return,
    )

    # 5. Determine dates
    max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
    if max_dates:
        data_asof = max(max_dates).date()
    else:
        data_asof = as_of_date or datetime.now().date()
    action_session = action_session_for_run(datetime.now())

    # 6. Build contexts
    contexts: list[CandidateContext] = []
    excluded = set(cfg.etf_exclusion.manual_block)
    excluded_tickers: list[str] = []
    for t in tickers:
        if t in excluded:
            excluded_tickers.append(t)
            continue
        if t not in ohlcv_by_ticker:
            continue
        contexts.append(CandidateContext(
            ticker=t,
            ohlcv=ohlcv_by_ticker[t],
            config=cfg,
            batch=batch,
            market=MarketContext(),
            current_equity=cfg.account.starting_equity,
        ))

    # 7. Evaluate
    candidates = evaluate_batch(contexts)

    # 8. Add excluded + error rows (spec §4.3 — 5 buckets)
    for t in excluded_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="excluded",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="ETF/fund blocklist", criteria=(),
        ))
    for t in error_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="error",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
        ))

    # 9. Persist atomically — run row + candidates + criteria in a single transaction
    conn = connect(cfg.paths.db_path)
    run = EvaluationRun(
        id=None,
        run_ts=datetime.now().isoformat(timespec="seconds"),
        data_asof_date=data_asof.isoformat(),
        action_session_date=action_session.isoformat(),
        finviz_csv_path=str(csv_file),
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=len(excluded_tickers),
        error_count=len(error_tickers),
        rs_universe_version=universe.version,
        rs_universe_hash=universe_hash,
    )
    try:
        with conn:  # `with conn:` commits on success, rolls back on exception
            run_id = insert_evaluation_run(conn, run)
            insert_candidates(conn, run_id, candidates)
    finally:
        conn.close()

    click.echo(
        f"Run {run_id}: A+={run.aplus_count} watch={run.watch_count} "
        f"skip={run.skip_count} excluded={run.excluded_count} error={run.error_count}"
    )
    click.echo(f"Data as of: {run.data_asof_date}  Action session: {run.action_session_date}")


if __name__ == "__main__":  # pragma: no cover
    main()
