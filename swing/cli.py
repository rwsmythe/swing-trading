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
from swing.evaluation.dates import action_session_for_run, last_completed_session
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
    ctx.obj["config_path"] = Path(config_path)


@main.command("db-migrate")
@click.pass_context
def db_migrate(ctx: click.Context) -> None:
    """Apply DB migrations. Safe to run multiple times. Backs up DB before migrating."""
    import sqlite3 as _sqlite3

    cfg = ctx.obj["config"]
    db_path = cfg.paths.db_path

    # Spec §3: automatic backup before migration. DB runs in WAL mode, so a plain
    # shutil.copy2 can miss committed data still in the -wal sidecar. Use SQLite's
    # backup API, which produces a single consistent file regardless of WAL state.
    if db_path.exists():
        cfg.paths.backups_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        backup_path = cfg.paths.backups_dir / f"swing-{ts}.db"
        src = _sqlite3.connect(db_path)
        dst = _sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
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

    # Capture "now" once so data_asof/action_session/run_ts can't drift across a
    # session boundary (e.g., NYSE close happening between calls).
    run_now = datetime.now()

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
    elif as_of_date is not None:
        data_asof = as_of_date
    else:
        # All fetches failed — fall back to the last completed NYSE session (not
        # wall-clock today, which could be a weekend/holiday or mid-session).
        data_asof = last_completed_session(run_now)
    action_session = action_session_for_run(run_now)

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
        run_ts=run_now.isoformat(timespec="seconds"),
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


@main.command("weather")
@click.option("--ticker", default="QQQ", help="Benchmark to classify (default: QQQ)")
@click.option("--as-of-date", "as_of_date_str", default=None,
              help="YYYY-MM-DD - cap OHLCV to bars <= this date (parity).")
@click.pass_context
def weather_cmd(ctx: click.Context, ticker: str, as_of_date_str: str | None) -> None:
    """Classify market weather and persist to weather_runs."""
    from datetime import date as _date, datetime as _dt
    from swing.prices import PriceFetcher
    from swing.weather.runner import run_weather

    cfg = ctx.obj["config"]
    fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)
    run_ts = _dt.now().isoformat(timespec="seconds")
    as_of = _date.fromisoformat(as_of_date_str) if as_of_date_str else None

    result = run_weather(
        db_path=cfg.paths.db_path, fetcher=fetcher,
        ticker=ticker, as_of_date=as_of, run_ts=run_ts,
    )
    click.echo(f"Status: {result.status}  Close: ${result.close:.2f}  "
               f"20MA slope: {result.slope20_5bar:+.2f}%/5b")
    click.echo(result.rationale)


@main.group("trade")
def trade_group() -> None:
    """Trade lifecycle: entry, exit, list, stop adjust, advisory."""


@trade_group.command("entry")
@click.option("--ticker", required=True)
@click.option("--entry-date", required=True, help="YYYY-MM-DD")
@click.option("--entry-price", type=float, required=True)
@click.option("--shares", type=int, required=True)
@click.option("--initial-stop", type=float, required=True)
@click.option("--watchlist-target", type=float, default=None)
@click.option("--watchlist-stop", type=float, default=None)
@click.option("--rationale", required=True)
@click.option("--notes", default=None)
@click.option("--force", is_flag=True, help="Bypass soft-warn cap (still subject to hard cap)")
@click.pass_context
def trade_entry_cmd(ctx, ticker, entry_date, entry_price, shares, initial_stop,
                    watchlist_target, watchlist_stop, rationale, notes, force):
    """Record a trade entry."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.entry import (
        EntryRequest, record_entry,
        SoftWarnException, HardCapException, DuplicateOpenPositionException,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        req = EntryRequest(
            ticker=ticker.upper(), entry_date=entry_date, entry_price=entry_price,
            shares=shares, initial_stop=initial_stop,
            watchlist_entry_target=watchlist_target,
            watchlist_initial_stop=watchlist_stop,
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
        )
        try:
            result = record_entry(
                conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=force,
            )
        except (SoftWarnException, HardCapException, DuplicateOpenPositionException) as exc:
            raise click.ClickException(str(exc))
    finally:
        conn.close()

    if result.warning:
        click.echo(f"WARN: {result.warning}", err=True)
    if result.watchlist_archived:
        click.echo(f"Watchlist row for {ticker} archived (reason: entered)")
    click.echo(f"Trade id {result.trade_id}: {ticker} {shares} sh @ ${entry_price:.2f}, stop ${initial_stop:.2f}")


@trade_group.command("exit")
@click.option("--trade-id", type=int, required=True)
@click.option("--exit-date", required=True)
@click.option("--exit-price", type=float, required=True)
@click.option("--shares", type=int, required=True)
@click.option("--reason", type=click.Choice(
    ["stop-hit", "target", "manual", "time-stop", "weather", "partial", "other"]
), required=True)
@click.option("--notes", default=None)
@click.option("--rationale", required=True)
@click.pass_context
def trade_exit_cmd(ctx, trade_id, exit_date, exit_price, shares, reason, notes, rationale):
    """Record a trade exit (full or partial)."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        req = ExitRequest(
            trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
            shares=shares, reason=ExitReason(reason),
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
        )
        result = record_exit(conn, req)
    finally:
        conn.close()
    closed = " (FULL CLOSE)" if result.fully_closed else ""
    click.echo(f"Exit {result.exit_id}: ${result.realized_pnl:+.2f} ({result.r_multiple:+.2f}R){closed}")


@trade_group.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed trades")
@click.pass_context
def trade_list_cmd(ctx, show_all):
    """List open (or all) trades."""
    from swing.data.db import connect
    from swing.data.repos.trades import list_open_trades, list_closed_trades

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trades = list_open_trades(conn)
        if show_all:
            trades = trades + list_closed_trades(conn)
    finally:
        conn.close()
    if not trades:
        click.echo("(no trades)")
        return
    click.echo(f"{'ID':>4} {'Ticker':<6} {'Date':<10} {'Entry':>8} {'Stop':>8} {'Sh':>4} {'Status':<8}")
    for t in trades:
        click.echo(
            f"{t.id or 0:>4} {t.ticker:<6} {t.entry_date:<10} "
            f"${t.entry_price:>6.2f} ${t.current_stop:>6.2f} {t.initial_shares:>4} {t.status:<8}"
        )


@trade_group.command("stop-adjust")
@click.option("--trade-id", type=int, required=True)
@click.option("--new-stop", type=float, required=True)
@click.option("--rationale", required=True)
@click.option("--force", is_flag=True, help="Allow lowering the stop")
@click.pass_context
def trade_stop_adjust_cmd(ctx, trade_id, new_stop, rationale, force):
    """Adjust the stop on an open trade. Refuses to lower without --force."""
    from datetime import datetime as _dt
    from swing.data.db import connect
    from swing.trades.stop_adjust import StopAdjustRequest, adjust_stop, StopRegressionError

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            adjust_stop(conn, StopAdjustRequest(
                trade_id=trade_id, new_stop=new_stop, rationale=rationale,
                event_ts=_dt.now().isoformat(timespec="seconds"), force=force,
            ))
        except StopRegressionError as exc:
            raise click.ClickException(str(exc))
    finally:
        conn.close()
    click.echo(f"Trade {trade_id} stop -> ${new_stop:.2f}")


@trade_group.command("advisory")
@click.option("--trade-id", type=int, required=True)
@click.option("--current-price", type=float, required=True)
@click.option("--sma10", type=float, default=None)
@click.option("--sma20", type=float, default=None)
@click.option("--weather", default="Bullish")
@click.option("--as-of-date", default=None, help="default: today")
@click.pass_context
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, weather, as_of_date):
    """Print stop-advisory suggestions for an open trade."""
    from datetime import date as _date
    from swing.data.db import connect
    from swing.data.repos.trades import get_trade
    from swing.trades.advisory import AdvisoryContext, compute_all_suggestions

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise click.ClickException(f"trade {trade_id} not found")
    finally:
        conn.close()
    asof = as_of_date or _date.today().isoformat()
    ctx_a = AdvisoryContext(
        as_of_date=asof, current_price=current_price,
        sma10=sma10, sma20=sma20,
        sma50=None, previous_close=None,
        weather_status=weather,
        config=cfg.stop_advisory,
    )
    sugs = compute_all_suggestions(trade, ctx_a)
    if not sugs:
        click.echo("(no advisories)")
        return
    for s in sugs:
        click.echo(f"  [{s.rule}] {s.message}")


@main.group("journal")
def journal_group() -> None:
    """Review stats + record cash movements."""


@journal_group.command("review")
@click.option("--period", type=click.Choice(["week", "month", "quarter", "ytd", "all"]),
              default="all")
@click.option("--today", default=None, help="YYYY-MM-DD; defaults to today")
@click.pass_context
def journal_review_cmd(ctx, period, today):
    """Compute and print journal stats + behavioral flags."""
    from datetime import date as _date
    from swing.data.db import connect
    from swing.data.repos.cash import list_cash
    from swing.data.repos.trades import list_closed_trades, list_open_trades, list_all_exits
    from swing.journal.flags import compute_flags
    from swing.journal.stats import compute_stats, period_filter

    cfg = ctx.obj["config"]
    today = today or _date.today().isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        all_trades = list_open_trades(conn) + list_closed_trades(conn)
        all_exits = list_all_exits(conn)
        cash = list_cash(conn)
        weather_rows = conn.execute(
            "SELECT id, run_ts, asof_date, ticker, status, close, sma10, sma20, sma50, "
            "slope20_5bar, slope10_5bar, rationale FROM weather_runs"
        ).fetchall()
    finally:
        conn.close()

    from swing.data.models import WeatherRun
    weather_runs = [WeatherRun(*row) for row in weather_rows]
    filtered = period_filter(all_trades, all_exits, period=period, today=today)
    stats = compute_stats(trades=filtered, exits=all_exits, cash_movements=cash)
    flags = compute_flags(trades=filtered, exits=all_exits, weather_runs=weather_runs)

    click.echo(f"=== Journal Review ({period}) \u2014 {today} ===")
    click.echo(f"{stats.n_trades} trades \u00b7 {stats.n_wins}W / {stats.n_losses}L")
    click.echo(f"Win rate {stats.win_rate*100:.1f}%  Expectancy {stats.expectancy_r:+.2f}R")
    click.echo(f"Avg win {stats.avg_win_r:+.2f}R \u00b7 avg loss {stats.avg_loss_r:+.2f}R")
    click.echo(f"Total {stats.total_r:+.2f}R \u00b7 ${stats.total_pnl:+.2f}")
    click.echo(f"Streak: {stats.current_streak}{stats.current_streak_kind}")
    if flags:
        click.echo("\nBehavioral flags:")
        for f in flags:
            click.echo(f"  \u2022 {f.title} \u2014 {f.detail}")


@journal_group.command("cash")
@click.option("--deposit", "deposit", type=float, default=None)
@click.option("--withdraw", "withdraw", type=float, default=None)
@click.option("--date", "date_str", required=True, help="YYYY-MM-DD")
@click.option("--ref", default=None)
@click.option("--note", default=None)
@click.pass_context
def journal_cash_cmd(ctx, deposit, withdraw, date_str, ref, note):
    """Log a cash movement."""
    from swing.data.db import connect
    from swing.data.models import CashMovement
    from swing.data.repos.cash import insert_cash

    if (deposit is None) == (withdraw is None):
        raise click.ClickException("Specify exactly one of --deposit or --withdraw")
    kind = "deposit" if deposit is not None else "withdraw"
    amount = deposit if deposit is not None else withdraw
    if amount <= 0:
        raise click.ClickException(
            f"--{kind} amount must be > 0; got {amount}"
        )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = insert_cash(conn, CashMovement(
                id=None, date=date_str, kind=kind, amount=amount, ref=ref, note=note,
            ))
    finally:
        conn.close()
    click.echo(f"Cash {kind} #{cid}: ${amount:.2f}{f' ref={ref}' if ref else ''}")


@main.command("tos-import")
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True, help="Print report without committing anything")
@click.option("--auto-confirm", is_flag=True, help="Commit new cash movements without prompting")
@click.pass_context
def tos_import_cmd(ctx, csv_path, dry_run, auto_confirm):
    """Reconcile a TOS Account Statement CSV against the journal."""
    from pathlib import Path as _Path
    from swing.data.db import connect
    from swing.data.repos.cash import insert_cash
    from swing.journal.tos_import import reconcile_tos

    cfg = ctx.obj["config"]
    text = _Path(csv_path).read_text(encoding="utf-8")
    report = reconcile_tos(db_path=cfg.paths.db_path, tos_text=text)

    click.echo(f"Cash: {len(report.new_cash_movements)} new, "
               f"{len(report.duplicate_cash_movements)} duplicate")
    for c in report.new_cash_movements:
        click.echo(f"  + {c.kind} ${c.amount:.2f} on {c.date} (ref={c.ref})")
    click.echo(f"Fills: matched={len(report.matched_fills)}, "
               f"already-reconciled={len(report.already_reconciled_fills)}, "
               f"price-mismatch={len(report.price_mismatch_fills)}, "
               f"unmatched OPEN={len(report.unmatched_open_fills)}, "
               f"unmatched CLOSE={len(report.unmatched_close_fills)}")
    for f in report.price_mismatch_fills:
        click.echo(f"  ! PRICE MISMATCH: {f.ticker} {f.date} qty={f.qty} TOS=${f.price:.2f}")
    for f in report.unmatched_open_fills:
        click.echo(f"  ? unmatched OPEN: {f.ticker} {f.date} qty={f.qty} @ ${f.price:.2f}")
    for f in report.unmatched_close_fills:
        click.echo(f"  ? unmatched CLOSE: {f.ticker} {f.date} qty={f.qty} @ ${f.price:.2f}")

    if dry_run:
        click.echo("Dry run \u2014 no changes committed.")
        return

    if report.new_cash_movements and (auto_confirm or click.confirm(
            f"Commit {len(report.new_cash_movements)} new cash movements?", default=True)):
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                for c in report.new_cash_movements:
                    insert_cash(conn, c)
        finally:
            conn.close()
        click.echo("Cash movements committed.")

    if report.unmatched_open_fills and not auto_confirm:
        click.echo(
            "Unmatched OPEN fills require manual entry via `swing trade entry`. "
            "Listing only \u2014 no auto-creation."
        )


@main.group("pipeline")
def pipeline_group() -> None:
    """Nightly orchestrator: run, list, force-clear."""


@pipeline_group.command("run")
@click.option("--manual", is_flag=True, help="Mark as a manual (vs scheduled) run")
@click.pass_context
def pipeline_run_cmd(ctx, manual):
    """Run the nightly pipeline."""
    from swing.pipeline import run_pipeline
    cfg = ctx.obj["config"]
    result = run_pipeline(cfg=cfg, trigger="manual" if manual else "scheduled")
    click.echo(f"Run id {result.run_id}: state={result.state}")
    if result.error_message:
        click.echo(f"Error: {result.error_message}", err=True)
    if result.state == "blocked":
        ctx.exit(2)
    if result.state == "failed":
        ctx.exit(1)


@pipeline_group.command("list")
@click.option("--limit", type=int, default=10)
@click.pass_context
def pipeline_list_cmd(ctx, limit):
    """List recent pipeline runs."""
    from swing.data.repos.pipeline import list_recent_runs
    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        runs = list_recent_runs(conn, limit=limit)
    finally:
        conn.close()
    if not runs:
        click.echo("(no runs)")
        return
    click.echo(f"{'ID':>4} {'State':<14} {'Started':<19} {'Session':<10} {'Step':<14}")
    for r in runs:
        click.echo(
            f"{r.id:>4} {r.state:<14} {r.started_ts:<19} "
            f"{r.action_session_date:<10} {(r.current_step or ''):<14}"
        )


@pipeline_group.command("force-clear")
@click.argument("run_id", type=int)
@click.option("--reason", default="admin force clear")
@click.option("--bypass-staleness-check", is_flag=True,
              help="Skip the two-signal staleness check (use with care)")
@click.pass_context
def pipeline_force_clear_cmd(ctx, run_id, reason, bypass_staleness_check):
    """Force-clear a stuck pipeline run (revokes its lease).

    Spec §5.6 requires TWO signals for staleness: heartbeat age AND step-progress
    age must BOTH exceed their thresholds. Only then is force-clear allowed.
    Use --bypass-staleness-check to override (e.g. to clear a crashed run whose
    heartbeat thread outlived the main loop).
    """
    from datetime import datetime as _dt
    from swing.data.repos.pipeline import find_run, force_clear
    from swing.pipeline.staleness import is_stale_eligible

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
        if run is None:
            raise click.ClickException(f"run {run_id} not found")
        if run.state != "running":
            raise click.ClickException(
                f"run {run_id} not in 'running' state (currently {run.state})"
            )

        now = _dt.now()
        heartbeat_age: float | None = None
        step_age: float | None = None
        if run.lease_heartbeat_ts:
            heartbeat_age = (now - _dt.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
        if run.last_step_progress_ts:
            step_age = (now - _dt.fromisoformat(run.last_step_progress_ts)).total_seconds()
        is_stale = is_stale_eligible(run, cfg)

        def _fmt_age(age: float | None) -> str:
            return f"{age:.0f}s" if age is not None else "missing"

        if not is_stale and not bypass_staleness_check:
            raise click.ClickException(
                f"Run {run_id} does not meet staleness threshold "
                f"(heartbeat age {_fmt_age(heartbeat_age)} vs "
                f"{cfg.pipeline.stale_lease_threshold_seconds}s; "
                f"step-progress age {_fmt_age(step_age)} vs "
                f"{cfg.pipeline.stale_step_threshold_seconds}s). "
                "Spec §5.6 requires BOTH signals present and stale. "
                "Use --bypass-staleness-check to override."
            )

        click.confirm(
            f"Force-clear run {run_id} (state={run.state}, "
            f"heartbeat_age={_fmt_age(heartbeat_age)}, step_age={_fmt_age(step_age)})? "
            "Any still-live worker loses its lease and cannot commit further writes.",
            abort=True,
        )
        with conn:
            force_clear(conn, run_id=run_id,
                        error_message=f"{reason} at {now.isoformat(timespec='seconds')}")
    finally:
        conn.close()
    click.echo(f"Run {run_id} force-cleared.")


@main.group("rs-universe")
def rs_universe_group() -> None:
    """RS reference universe management."""


@rs_universe_group.command("refresh")
@click.option("--source", default="spx_ndx",
              help="Source identifier (default: spx_ndx = SPX + NASDAQ-100)")
@click.pass_context
def rs_universe_refresh_cmd(ctx, source):
    """Regenerate the RS reference universe from source. Snapshots the prior file."""
    from swing.evaluation.rs_refresh import refresh_rs_universe
    cfg = ctx.obj["config"]
    new_version = refresh_rs_universe(dest=cfg.paths.rs_universe_path, source=source)
    click.echo(f"RS universe refreshed: version {new_version}")
    click.echo(f"  Path: {cfg.paths.rs_universe_path}")
    click.echo(f"  Prior snapshot saved alongside")


@main.command("web")
@click.option("--host", default=None, help="Override [web].host from config")
@click.option("--port", type=int, default=None)
@click.option("--reload", is_flag=True, default=None, help="Enable auto-reload")
@click.pass_context
def web_cmd(ctx, host, port, reload):
    """Run the dashboard on localhost."""
    # Lazy import: do NOT hoist to module top — keeps base install working
    # without [web] extra (invariant 12).
    from swing.web.cli_cmd import run_server
    run_server(
        cfg=ctx.obj["config"],
        cfg_path=ctx.obj.get("config_path"),
        host=host, port=port, reload=reload,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
