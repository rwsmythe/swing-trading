"""Click CLI for swing. Phase 1 subcommands: db-migrate, eval."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from swing.cli_config import config_group
from swing.config import load as load_config
from swing.data.db import connect, ensure_schema
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.evaluation.evaluator import evaluate_batch
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.prices import PriceFetcher
from swing.recommendations.hypothesis_prefill import lookup_active_recommendation_label


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
    """C.11: reconstruct Exit-like rows from non-entry fills.

    Mirrors the per-module ``_ExitShape`` adapter pattern from C.1/C.9/C.10.
    Migrates the ``swing trade list`` and ``swing journal review`` CLI
    consumers off the legacy Exit-shim before C.14 deletes it.
    """
    from swing.data.models import Trade
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )
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
            continue
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


@click.group()
@click.option("--config", "config_path", default="swing.config.toml",
              help="Path to swing.config.toml")
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """Swing trading CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(Path(config_path))
    ctx.obj["config_path"] = Path(config_path)


main.add_command(config_group)


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


@main.command("db-backup")
@click.option("--force", is_flag=True, default=False,
              help="Bypass the once-per-ISO-week check and back up unconditionally.")
@click.pass_context
def db_backup(ctx: click.Context, force: bool) -> None:
    """Snapshot the production DB to <backups_dir>/swing-YYYYWW.db.

    Default behavior: only back up if the current ISO week's file does not
    already exist. `--force` skips the check. After a successful backup,
    older weekly snapshots are pruned to the 12 most-recent (~3 months).
    """
    from swing.data.backup import (
        compute_backup_destination,
        do_backup,
        prune_old_backups,
        should_backup,
    )

    cfg = ctx.obj["config"]
    db_path = cfg.paths.db_path
    if not db_path.exists():
        raise click.ClickException(f"DB not found at {db_path} — run `swing db-migrate` first.")

    now = datetime.now()
    if not force and not should_backup(cfg.paths.backups_dir, now):
        target = compute_backup_destination(now, cfg.paths.backups_dir)
        click.echo(f"no backup needed for current week ({target.name} already exists)")
        return

    path = do_backup(db_path, cfg.paths.backups_dir, now=now)
    click.echo(f"backup written: {path}")
    deleted = prune_old_backups(cfg.paths.backups_dir, keep=12)
    if deleted:
        click.echo(f"pruned {len(deleted)} old weekly backup(s)")


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

    # Sector/Industry passthrough from Finviz CSV -> candidate rows. Mirrors
    # the `_step_evaluate` plumbing in swing/pipeline/runner.py so standalone
    # `swing eval` and the pipeline persist classification identically. The
    # downstream `latest_evaluation_run_id()` helper falls back to standalone
    # evaluation_runs when no pipeline-bound eval exists, so this is the
    # only place classification can land for an operator running eval-only.
    # eval_cmd does NOT enforce finviz_schema.REQUIRED_COLUMNS — `Sector`
    # and `Industry` may be absent; `.get(..., "")` degrades to empty
    # strings (same default as the dataclass) without raising.
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

    click.echo(f"Evaluating {len(tickers)} tickers from {csv_file.name}")

    # 2. Load RS universe
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)

    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )

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

    # Plumb Sector/Industry uniformly across every bucket — applied AFTER
    # both the evaluate_batch result and the synthesized excluded/error rows
    # so any candidate whose ticker is in the CSV gets classification, and
    # any ticker not in the CSV (defensive — eval_cmd only sources tickers
    # from finviz_df, so this should be empty in practice) defaults to the
    # ('', '') dataclass default. Mirrors the runner._step_evaluate pattern.
    from dataclasses import replace as _dc_replace
    candidates = [
        _dc_replace(
            c,
            sector=sector_industry_by_ticker.get(c.ticker, ("", ""))[0],
            industry=sector_industry_by_ticker.get(c.ticker, ("", ""))[1],
        )
        for c in candidates
    ]

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
    from datetime import date as _date
    from datetime import datetime as _dt

    from swing.prices import PriceFetcher
    from swing.weather.runner import run_weather

    cfg = ctx.obj["config"]
    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
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
@click.option("--rationale", required=True,
              type=click.Choice([
                  "aplus-setup", "near-trigger-breakout", "vcp-breakout",
                  "pivot-breakout", "post-earnings-continuation",
                  "relative-strength", "other",
              ]),
              help="Entry rationale (closed taxonomy). "
                   "'other' requires --notes.")
@click.option("--notes", default=None)
@click.option("--hypothesis", "hypothesis", default=None,
              help="Optional free-text pre-trade hypothesis label. Frozen at "
                   "entry time; aggregated by `swing journal review`.")
@click.option("--chart-pattern-operator", "chart_pattern_operator",
              default=None,
              help="Operator override for chart pattern (free text per "
                   "spec §3.6 — canonicalized at persistence). Refused "
                   "if the ticker has no cached classification (V1 "
                   "cached-only; manual fallback deferred to V2).")
# Phase 7 Sub-B B.8 — 18 pre-trade fields + entry_path discriminator.
# All non-required at click level; the validator (record_entry's
# pre-trade gate) is the single source of truth for required-field
# enforcement. MissingPreTradeFieldsException is caught below and
# re-raised as click.UsageError with operator-actionable flag names.
@click.option("--entry-path",
              type=click.Choice([
                  "aplus_today_decision", "hyp_recs_button",
                  "manual_web_form", "cli_manual",
              ]),
              default="cli_manual",
              help="Entry-path origin discriminator.")
@click.option("--thesis", default=None,
              help="Pre-trade thesis (required).")
@click.option("--why-now", default=None,
              help="Why-now trigger (required).")
@click.option("--invalidation", default=None,
              help="Invalidation condition (required).")
@click.option("--expected-scenario", default=None,
              help="Expected scenario (required).")
@click.option("--premortem-technical", default=None,
              help="Pre-mortem: technical failure mode (required).")
@click.option("--premortem-market-sector", default=None,
              help="Pre-mortem: market/sector failure mode (required).")
@click.option("--premortem-execution", default=None,
              help="Pre-mortem: execution failure mode (required).")
@click.option("--premortem-additional", default=None,
              help="Pre-mortem: additional notes (optional).")
@click.option("--event-risk", type=click.Choice(["yes", "no"]),
              default="no",
              help="Known event risk (earnings, fed, etc.) before exit?")
@click.option("--event-handling",
              type=click.Choice([
                  "avoid_event", "hold_through", "reduce_before",
                  "exit_before", "not_applicable",
              ]),
              default=None,
              help="How to handle the event (required if --event-risk yes).")
@click.option("--event-type",
              type=click.Choice([
                  "earnings", "fed_meeting", "cpi_release",
                  "economic_data", "product_announcement",
                  "legal_ruling", "other",
              ]),
              default=None,
              help="Event type (required if --event-risk yes).")
@click.option("--event-date", default=None,
              help="Event date YYYY-MM-DD (required if --event-risk yes).")
@click.option("--gap-risk", type=click.Choice(["yes", "no"]),
              default="no",
              help="Material overnight-gap risk?")
@click.option("--gap-risk-handling",
              type=click.Choice([
                  "accept", "reduce_size", "tight_stop",
                  "exit_before_close", "not_applicable",
              ]),
              default=None,
              help="Gap-risk handling (required if --gap-risk yes).")
@click.option("--emotional-state", multiple=True,
              type=click.Choice([
                  "calm", "confident", "anxious", "fomo", "revenge",
                  "hopeful", "doubtful", "distracted",
              ]),
              help="Pre-trade emotional state (one or more; required).")
@click.option("--manual-entry-confidence",
              type=click.Choice(["high", "normal", "low"]),
              default=None,
              help="Manual-entry confidence (required).")
@click.option("--market-regime",
              type=click.Choice(["Bullish", "Caution", "Bearish"]),
              default=None,
              help="Market regime at entry (required).")
@click.option("--catalyst",
              type=click.Choice([
                  "earnings_driven", "guidance_change", "corporate_action",
                  "sector_rotation", "macro_event", "sympathy_move",
                  "product_news", "technical_only", "other",
              ]),
              default=None,
              help="Catalyst class (required).")
@click.option("--catalyst-other-description", default=None,
              help="Catalyst description (required if --catalyst other).")
@click.option("--force", is_flag=True, help="Bypass soft-warn cap (still subject to hard cap)")
@click.pass_context
def trade_entry_cmd(ctx, ticker, entry_date, entry_price, shares, initial_stop,
                    watchlist_target, watchlist_stop, rationale, notes,
                    hypothesis, chart_pattern_operator,
                    entry_path, thesis, why_now, invalidation,
                    expected_scenario, premortem_technical,
                    premortem_market_sector, premortem_execution,
                    premortem_additional, event_risk, event_handling,
                    event_type, event_date, gap_risk, gap_risk_handling,
                    emotional_state, manual_entry_confidence,
                    market_regime, catalyst, catalyst_other_description,
                    force):
    """Record a trade entry."""
    import json as _json
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.trades.entry import (
        DuplicateOpenPositionError,
        EntryRequest,
        HardCapError,
        MissingPreTradeFieldsException,
        SoftWarnError,
        record_entry,
    )
    from swing.trades.origin import EntryPath

    # T4: --notes required when --rationale=other (parity with web form).
    if rationale == "other" and not (notes and notes.strip()):
        raise click.ClickException("--notes required when --rationale=other")

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        # Phase 5 spec §3.6 ToCToU fix — resolve the chart-pattern
        # cache row ONCE at command start (entry-surface). Snapshot
        # then flows through EntryRequest and record_entry persists
        # AS-IS. Phase 4 (Task 4): consume `latest_completed_pipeline_run`
        # — pipeline-bound contract; chart-pattern resolve only fires
        # when a completed pipeline exists.
        cp_algo: str | None = None
        cp_conf: float | None = None
        cp_anchor: int | None = None
        cp_evaluated = False
        from swing.web.chart_scope import latest_completed_pipeline_run
        binding = latest_completed_pipeline_run(conn)
        if binding is not None and binding.run_id is not None:
            from swing.data.repos.pattern_classifications import (
                get_classification,
            )
            cls = get_classification(
                conn, pipeline_run_id=binding.run_id,
                ticker=ticker.upper(),
            )
            if cls is not None and cls.pattern in ("flag", "none"):
                cp_algo = cls.pattern
                cp_conf = cls.confidence
                cp_anchor = cls.pipeline_run_id
                cp_evaluated = True

        # Spec §3.7 R1 C1 — CLI parity gate. Symmetric with the form's
        # "Not classified" stub gate (Task 5.3) and the POST handler's
        # 400 refusal (Task 5.4): if the operator passed
        # ``--chart-pattern-operator`` for a ticker without a cached
        # classification (or only a classifier-error row), refuse.
        if chart_pattern_operator is not None and not cp_evaluated:
            raise click.ClickException(
                f"--chart-pattern-operator requires a cached classification "
                f"for {ticker.upper()}; ticker is out-of-scope for the "
                f"latest pipeline run. (V1 cached-only; manual fallback "
                f"deferred to V2.)"
            )

        # Pre-fill --hypothesis from the latest pipeline run's active
        # recommendation when the operator did NOT pass --hypothesis
        # explicitly (frontend brief §4.3). Empty-string is treated as an
        # explicit override (operator-typed "no label"), preserved
        # downstream by `canonicalize_hypothesis_label` → NULL. None means
        # the flag was omitted, which is the only branch that triggers
        # pre-fill.
        if hypothesis is None:
            prefilled = lookup_active_recommendation_label(
                conn, ticker=ticker.upper(),
                starting_equity=cfg.account.starting_equity,
            )
            if prefilled is not None:
                hypothesis = prefilled
                click.echo(f"Pre-filled --hypothesis: {prefilled}")

        # NEW (Task 7): sector/industry candidate-row lookup via the canonical
        # helper, mirroring the entry-form VM (Task 6) for cross-surface
        # consistency. Falls back to '' when no eval or ticker absent.
        from swing.web.view_models.dashboard import latest_evaluation_run_id
        cli_sector = ""
        cli_industry = ""
        sector_eval_id = latest_evaluation_run_id(conn)
        if sector_eval_id is not None:
            cand_row = conn.execute(
                """SELECT sector, industry FROM candidates
                   WHERE evaluation_run_id = ? AND ticker = ?""",
                (sector_eval_id, ticker.upper()),
            ).fetchone()
            if cand_row is not None:
                cli_sector = cand_row[0] or ""
                cli_industry = cand_row[1] or ""

        # Phase 7 Sub-B B.8 — convert click-string inputs to EntryRequest
        # value types: yes/no -> int (0|1), tuple -> JSON-list TEXT, path
        # string -> EntryPath enum. Defaults: event/gap risk default to 0
        # (operator must consciously opt in to either risk).
        emotional_state_json = (
            _json.dumps(list(emotional_state)) if emotional_state else None
        )
        req = EntryRequest(
            ticker=ticker.upper(), entry_date=entry_date, entry_price=entry_price,
            shares=shares, initial_stop=initial_stop,
            watchlist_entry_target=watchlist_target,
            watchlist_initial_stop=watchlist_stop,
            notes=notes, rationale=rationale,
            event_ts=_dt.now().isoformat(timespec="seconds"),
            # Canonicalization happens in `record_entry` so non-CLI callers
            # (web routes, scripts) get the same normalization. CLI passes
            # raw user input through unchanged.
            hypothesis_label=hypothesis,
            chart_pattern_operator=chart_pattern_operator,
            chart_pattern_algo=cp_algo,
            chart_pattern_algo_confidence=cp_conf,
            chart_pattern_classification_pipeline_run_id=cp_anchor,
            sector=cli_sector,
            industry=cli_industry,
            entry_path=EntryPath(entry_path),
            thesis=thesis,
            why_now=why_now,
            invalidation_condition=invalidation,
            expected_scenario=expected_scenario,
            premortem_technical=premortem_technical,
            premortem_market_sector=premortem_market_sector,
            premortem_execution=premortem_execution,
            premortem_additional=premortem_additional,
            event_risk_present=1 if event_risk == "yes" else 0,
            event_handling=event_handling,
            event_type=event_type,
            event_date=event_date,
            gap_risk_present=1 if gap_risk == "yes" else 0,
            gap_risk_handling=gap_risk_handling,
            emotional_state_pre_trade=emotional_state_json,
            market_regime=market_regime,
            catalyst=catalyst,
            catalyst_other_description=catalyst_other_description,
            manual_entry_confidence=manual_entry_confidence,
        )
        try:
            result = record_entry(
                conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=force,
            )
        except MissingPreTradeFieldsException as exc:
            # B.8: structured-exception → click.UsageError mapping.
            # Source-of-truth for required fields lives in
            # swing.trades.state.OPERATION_REQUIRED_FIELDS; this layer
            # only translates field names back to operator-facing flags.
            flag_map = {
                "thesis": "--thesis",
                "why_now": "--why-now",
                "invalidation_condition": "--invalidation",
                "expected_scenario": "--expected-scenario",
                "premortem_technical": "--premortem-technical",
                "premortem_market_sector": "--premortem-market-sector",
                "premortem_execution": "--premortem-execution",
                "emotional_state_pre_trade": "--emotional-state (one or more)",
                "market_regime": "--market-regime",
                "catalyst": "--catalyst",
                "manual_entry_confidence": "--manual-entry-confidence",
                "event_handling": "--event-handling",
                "event_type": "--event-type",
                "event_date": "--event-date",
                "gap_risk_handling": "--gap-risk-handling",
                "catalyst_other_description": "--catalyst-other-description",
            }
            flags = [
                flag_map.get(f, f"--{f.replace('_', '-')}")
                for f in exc.missing_fields
            ]
            raise click.UsageError(
                f"Missing required pre-trade fields: {', '.join(flags)}"
            ) from exc
        except (SoftWarnError, HardCapError, DuplicateOpenPositionError) as exc:
            raise click.ClickException(str(exc)) from exc
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
@click.pass_context
def trade_exit_cmd(ctx, trade_id, exit_date, exit_price, shares, reason, notes):
    """Record a trade exit (full or partial).

    ``trade_events.rationale`` is derived server-side from ``--reason``;
    use ``--notes`` for free-form context.
    """
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.trades.exit import ExitReason, ExitRequest, record_exit

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        reason_enum = ExitReason(reason)
        req = ExitRequest(
            trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
            shares=shares, reason=reason_enum,
            notes=notes, rationale=reason_enum.value,
            event_ts=_dt.now().isoformat(timespec="seconds"),
        )
        result = record_exit(conn, req)
    finally:
        conn.close()
    closed = " (FULL CLOSE)" if result.fully_closed else ""
    click.echo(f"Exit {result.exit_id}: ${result.realized_pnl:+.2f} ({result.r_multiple:+.2f}R){closed}")
    if result.fully_closed:
        from swing.trades.review import soft_warn_review_due_message
        click.echo(soft_warn_review_due_message(cfg.review.review_window_days))


@trade_group.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include closed trades")
@click.pass_context
def trade_list_cmd(ctx, show_all):
    """List open (or all) trades."""
    from collections import defaultdict

    from swing.data.db import connect
    from swing.data.repos.trades import (
        list_closed_trades,
        list_open_trades,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trades = list_open_trades(conn)
        if show_all:
            trades = trades + list_closed_trades(conn)
        # Group exits by trade to compute remaining shares — matches the
        # web dashboard's `remaining = initial_shares - sum(exits.shares)`
        # pattern so both surfaces agree.
        exits_by_trade: dict[int, list] = defaultdict(list)
        for e in _list_all_exitshape_via_fills(conn):
            exits_by_trade[e.trade_id].append(e)
    finally:
        conn.close()
    if not trades:
        click.echo("(no trades)")
        return
    click.echo(f"{'ID':>4} {'Ticker':<6} {'Date':<10} {'Entry':>8} {'Stop':>8} {'Sh':>4} {'State':<14}")
    for t in trades:
        remaining = t.initial_shares - sum(
            e.shares for e in exits_by_trade.get(t.id or 0, [])
        )
        click.echo(
            f"{t.id or 0:>4} {t.ticker:<6} {t.entry_date:<10} "
            f"${t.entry_price:>6.2f} ${t.current_stop:>6.2f} {remaining:>4} {t.state:<14}"
        )


@trade_group.command("stop-adjust")
@click.option("--trade-id", type=int, required=True)
@click.option("--new-stop", type=float, required=True)
@click.option("--rationale", required=True,
              type=click.Choice([
                  "breakeven", "trail-10ma", "trail-20ma", "weather-tighten",
                  "manual-trail", "news", "other",
              ]),
              help="Stop-adjust rationale (closed taxonomy). "
                   "'other' requires --notes.")
@click.option("--notes", default=None)
@click.option("--force", is_flag=True, help="Allow lowering the stop")
@click.pass_context
def trade_stop_adjust_cmd(ctx, trade_id, new_stop, rationale, notes, force):
    """Adjust the stop on an open trade. Refuses to lower without --force."""
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.trades.stop_adjust import StopAdjustRequest, StopRegressionError, adjust_stop

    # T5: --notes required when --rationale=other (parity with web form).
    if rationale == "other" and not (notes and notes.strip()):
        raise click.ClickException("--notes required when --rationale=other")

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            adjust_stop(conn, StopAdjustRequest(
                trade_id=trade_id, new_stop=new_stop, rationale=rationale,
                notes=notes,
                event_ts=_dt.now().isoformat(timespec="seconds"), force=force,
            ))
        except StopRegressionError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    click.echo(f"Trade {trade_id} stop -> ${new_stop:.2f}")


@trade_group.command("advisory")
@click.option("--trade-id", type=int, required=True)
@click.option("--current-price", type=float, required=True)
@click.option("--sma10", type=float, default=None)
@click.option("--sma20", type=float, default=None)
@click.option("--sma50", type=float, default=None)
@click.option("--previous-close", type=float, default=None)
@click.option("--weather", default="Bullish")
@click.option("--as-of-date", default=None, help="default: today")
@click.pass_context
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, sma50,
                        previous_close, weather, as_of_date):
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
        sma50=sma50, previous_close=previous_close,
        weather_status=weather,
        config=cfg.stop_advisory,
    )
    sugs = compute_all_suggestions(trade, ctx_a)
    if not sugs:
        click.echo("(no advisories)")
        return
    for s in sugs:
        click.echo(f"  [{s.rule}] {s.message}")


@trade_group.command("analyze")
@click.argument("trade_id", type=int)
@click.pass_context
def trade_analyze_cmd(ctx, trade_id):
    """Per-trade retrospective: recommendation context + criteria + deviations.

    Reads only — composes from production tables (trades, exits, candidates,
    candidate_criteria, evaluation_runs). Manually-sourced trades render with
    a sentinel and skip the deviations section. See
    `docs/trade-analyze-cli-brief.md` for the schema joins this command
    automates.
    """
    from swing.data.db import connect
    from swing.journal.analyze import analyze_trade

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        # Connection-level write guard on top of the analyze function's
        # behavioral discipline: PRAGMA query_only=ON makes SQLite refuse any
        # INSERT/UPDATE/DELETE/DDL on THIS CONNECTION for its lifetime. It
        # does not open the underlying file read-only — concurrent writers on
        # other connections (e.g. the pipeline) are unaffected — but it does
        # prevent a future bug in the compute path from mutating the
        # production DB through this command. Chosen over URI ?mode=ro to
        # preserve the standard `connect()` schema-version check path.
        conn.execute("PRAGMA query_only = ON")
        try:
            a = analyze_trade(conn, trade_id)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    for line in _render_trade_analysis(a):
        click.echo(line)


def _fmt_optional_money(value: float | None) -> str:
    return f"${value:.2f}" if value is not None else "n/a"


def _fmt_optional_pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def _render_trade_analysis(a) -> list[str]:
    """Render `TradeAnalysis` as scannable text. Returns lines (no trailing
    newlines); CLI emits each via `click.echo`. Pure function — easy to test
    independently of click."""
    from swing.journal.analyze import TradeAnalysis  # local for cycle-free imports
    assert isinstance(a, TradeAnalysis)

    lines: list[str] = []
    header = f"TRADE #{a.trade_id} — {a.ticker}"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append(f"Status: {a.state}")
    lines.append(
        f"Entry: {a.entry_date} @ ${a.entry_price:.2f} × "
        f"{a.initial_shares} sh"
    )
    lines.append(
        f"Initial stop: ${a.initial_stop:.2f}     "
        f"Current stop: ${a.current_stop:.2f}"
    )
    lines.append(f"Hypothesis: {a.hypothesis_label or '(none)'}")
    lines.append(f"Notes: {a.notes or '(none)'}")
    lines.append("")

    # Recommendations section
    if a.recommendations:
        lines.append(f"RECOMMENDATIONS ({len(a.recommendations)})")
        lines.append("-" * 21)
        for rec in a.recommendations:
            lines.append(
                f"[{rec.eval_run_id}] {rec.eval_run_action_session_date} — "
                f"bucket={rec.bucket}"
            )
            lines.append(
                f"  pivot={_fmt_optional_money(rec.pivot)}  "
                f"rec_stop={_fmt_optional_money(rec.initial_stop)}  "
                f"close={_fmt_optional_money(rec.close_at_eval)}"
            )
            rs_rank_disp = rec.rs_rank if rec.rs_rank is not None else "n/a"
            rs_excess_disp = (
                _fmt_optional_pct(rec.rs_return_12w_vs_spy)
                if rec.rs_return_12w_vs_spy is not None else "n/a"
            )
            lines.append(
                f"  rs_rank={rs_rank_disp}  rs_vs_spy={rs_excess_disp}"
            )
            failed = [c for c in rec.criteria if c.result == "fail"]
            passed = [c for c in rec.criteria if c.result == "pass"]
            na = [c for c in rec.criteria if c.result == "na"]
            if failed:
                lines.append(f"  Failed criteria ({len(failed)}):")
                for c in failed:
                    val = c.value if c.value is not None else ""
                    rule = f"  ({c.rule})" if c.rule else ""
                    lines.append(
                        f"    {c.layer}/{c.criterion_name}: {val}{rule}"
                    )
            if na:
                # Surface na criteria so an operator auditing the recommendation
                # can tell when criteria were skipped vs. evaluated. Hiding na
                # would let "all 8 trend_template pass" mask a layer that was
                # only partially evaluated.
                lines.append(f"  N/A criteria ({len(na)}):")
                for c in na:
                    val = c.value if c.value is not None else ""
                    rule = f"  ({c.rule})" if c.rule else ""
                    lines.append(
                        f"    {c.layer}/{c.criterion_name}: {val}{rule}"
                    )
            if passed:
                # Group counts by layer for the all-passed summary.
                from collections import Counter
                layer_counts = Counter(c.layer for c in passed)
                summary = "; ".join(
                    f"{layer}: {count}"
                    for layer, count in sorted(layer_counts.items())
                )
                lines.append(f"  All passed by layer — {summary}")
        lines.append("")
    else:
        lines.append("RECOMMENDATIONS (0)")
        lines.append("-" * 21)
        lines.append(
            "  MANUALLY-SOURCED — no production recommendation in DB before "
            "entry_date"
        )
        lines.append("")

    # Exits section
    if a.exits:
        lines.append(f"EXITS ({len(a.exits)})")
        lines.append("-" * 8)
        for ex in a.exits:
            lines.append(
                f"  {ex.exit_date}: {ex.shares} sh @ ${ex.exit_price:.2f}  "
                f"reason={ex.reason}  "
                f"pnl=${ex.realized_pnl:+.2f}  R={ex.r_multiple:+.2f}"
            )
        lines.append("")
    else:
        lines.append("EXITS (0)")
        lines.append("-" * 8)
        lines.append("  (no exits yet — trade still open)")
        lines.append("")

    # Deviations section — only when at least one usable rec exists
    if a.recommendations:
        lines.append("DEVIATIONS (vs latest pre-entry recommendation)")
        lines.append("-" * 47)
        days = a.days_rec_to_entry
        if days is None:
            days_disp = "n/a"
        elif days < 0:
            # Action-session-after-entry indicates a forward-looking
            # recommendation captured before its target session, which is
            # unusual enough to label rather than print as a raw negative.
            days_disp = f"{days} (rec action_session is AFTER entry — unusual)"
        else:
            days_disp = str(days)
        lines.append(f"  Days from rec to entry: {days_disp}")
        lines.append(
            f"  Entry % above pivot: {_fmt_optional_pct(a.pct_above_pivot)}"
        )
        lines.append(
            f"  Stop deviation vs recommended: "
            f"{_fmt_optional_pct(a.stop_dev_pct)}"
        )
        lines.append("")

    # Outcomes section
    lines.append("OUTCOMES")
    lines.append("-" * 8)
    lines.append(f"  Realized P&L total: ${a.realized_pnl_total:+.2f}")
    if a.r_multiple_avg is not None:
        lines.append(
            f"  R-multiple (shares-weighted): {a.r_multiple_avg:+.2f}"
        )
    else:
        lines.append("  R-multiple (shares-weighted): n/a (no exits)")
    # Hold duration: branch on trade status so a partial exit on an open
    # trade doesn't get reported as "entry to last exit" (the position is
    # still live). Adversarial review R2 M2.
    from datetime import date as _date
    if a.exits and a.status == "closed":
        try:
            entry_d = _date.fromisoformat(a.entry_date)
            last_exit_d = max(
                _date.fromisoformat(e.exit_date) for e in a.exits
            )
            hold_days = (last_exit_d - entry_d).days
            lines.append(
                f"  Hold duration: {hold_days} days (entry to last exit)"
            )
        except ValueError:
            lines.append("  Hold duration: n/a (date parse error)")
    elif a.exits and a.status == "open":
        # Partial exits on an open trade — duration is ongoing.
        try:
            entry_d = _date.fromisoformat(a.entry_date)
            today = _date.today()
            hold_days = (today - entry_d).days
            last_partial_d = max(
                _date.fromisoformat(e.exit_date) for e in a.exits
            )
            lines.append(
                f"  Hold duration: {hold_days} days ongoing (entry to today; "
                f"last partial exit {last_partial_d.isoformat()}; trade still open)"
            )
        except ValueError:
            lines.append("  Hold duration: n/a (date parse error)")
    elif not a.exits and a.status == "open":
        try:
            entry_d = _date.fromisoformat(a.entry_date)
            today = _date.today()
            hold_days = (today - entry_d).days
            lines.append(
                f"  Hold duration: {hold_days} days ongoing (entry to today; trade still open)"
            )
        except ValueError:
            lines.append("  Hold duration: n/a (trade still open)")
    else:
        # status == 'closed' with no exits is invariant-violating per the
        # trades repo; surface defensively rather than crash.
        lines.append("  Hold duration: n/a (closed trade with no exits — data anomaly)")
    return lines


@trade_group.command("review")
@click.option("--list", "list_mode", is_flag=True,
              help="List closed trades pending review and exit. "
                   "When set, all other args are ignored.")
@click.option("--window-days", type=int, default=None,
              help="Threshold in days since close (used with --list). "
                   "Defaults to 7.")
@click.option("--trade-id", type=int, default=None,
              help="REQUIRED unless --list is set.")
@click.option(
    "--mistake-tags", multiple=True,
    help="Repeatable. e.g., --mistake-tags CHASED --mistake-tags FOMO. "
         "Use 'none_observed' if no mistakes (must NOT be combined with others).",
)
@click.option("--entry-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--management-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--exit-grade", type=click.Choice(["A", "B", "C", "D", "F"]),
              default=None, help="REQUIRED unless --list is set.")
@click.option("--disqualifying-process-violation", is_flag=True,
              help="Set if any of the 7 v1.2 §9.2 disqualifying violations occurred. "
                   "Caps process_grade at D.")
@click.option("--realized-r-if-plan-followed", "realized_r_if_plan_followed",
              type=float, default=None,
              help="Counterfactual R if the original plan had been followed. Optional.")
@click.option("--mistake-cost-confidence",
              type=click.Choice(["high", "medium", "low"]), default=None)
@click.option("--lesson-learned", default=None,
              help="REQUIRED unless --list is set. Free-text reflection.")
@click.pass_context
def trade_review_cmd(
    ctx, list_mode, window_days, trade_id, mistake_tags,
    entry_grade, management_grade, exit_grade,
    disqualifying_process_violation, realized_r_if_plan_followed,
    mistake_cost_confidence, lesson_learned,
):
    """Post-trade review surface — log mistakes, process grade, and outcome attribution."""
    import json
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.data.repos.review_log import list_unreviewed_closed_trades
    from swing.data.repos.trades import get_trade
    from swing.trades.review import (
        canonicalize_mistake_tags,
        complete_trade_review,
        compute_process_grade,
        validate_mistake_tags,
    )

    cfg = ctx.obj["config"]

    # ---- LIST MODE ----
    if list_mode:
        conn = connect(cfg.paths.db_path)
        try:
            # Spec §3.1: list-view shows ALL closed-unreviewed (window_days=None).
            # The badge (count_needs_review) keeps using window_days; that's separate.
            trades = list_unreviewed_closed_trades(
                conn, window_days=None, today_iso=None,
            )
        finally:
            conn.close()
        if not trades:
            click.echo("No trades pending review.")
            return
        click.echo("Trades pending review (all closed trades awaiting review):")
        for t in trades:
            click.echo(f"  #{t.id} {t.ticker} entry={t.entry_date}")
        return

    # ---- REVIEW MODE — validate required args ----
    missing = []
    if trade_id is None:
        missing.append("--trade-id")
    if entry_grade is None:
        missing.append("--entry-grade")
    if management_grade is None:
        missing.append("--management-grade")
    if exit_grade is None:
        missing.append("--exit-grade")
    if not lesson_learned or not lesson_learned.strip():
        missing.append("--lesson-learned")
    if missing:
        raise click.UsageError(
            f"Missing required args (or pass --list to enter list mode): "
            f"{', '.join(missing)}"
        )

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise click.ClickException(f"Trade #{trade_id} not found")
        # B.7: spec §2.1 — precondition is `state == 'closed'` (NOT
        # `state in ('closed','reviewed')`). The reviewed-state path is
        # rejected here so an already-reviewed trade cannot be reviewed
        # twice; the `reviewed_at is not None` check below stays as
        # belt-and-suspenders for legacy rows that may carry a reviewed_at
        # timestamp without the corresponding state transition.
        if trade.state != "closed":
            raise click.ClickException(
                f"Trade #{trade_id} is not closed (state={trade.state!r}); "
                f"cannot review"
            )
        if trade.reviewed_at is not None:
            raise click.ClickException(
                f"Trade #{trade_id} already reviewed at {trade.reviewed_at}; "
                f"V1 supports single-review only"
            )

        canonical_tags = canonicalize_mistake_tags(list(mistake_tags))
        if not canonical_tags:
            raise click.UsageError(
                "--mistake-tags is required (use 'none_observed' if no mistakes observed)"
            )
        try:
            validate_mistake_tags(canonical_tags)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

        process_grade = compute_process_grade(
            entry=entry_grade, management=management_grade, exit_=exit_grade,
            disqualifying=disqualifying_process_violation,
        )

        # B.7: route through `complete_trade_review` service so the review
        # fields write + state_transition(closed → reviewed) land atomically
        # in a single transaction. The service opens its own `with conn:`
        # block (B.6 implementation) so no outer wrapper is needed.
        reviewed_at = _dt.now().isoformat(timespec="seconds")
        complete_trade_review(
            conn, trade_id,
            reviewed_at=reviewed_at,
            mistake_tags_json=json.dumps(canonical_tags),
            entry_grade=entry_grade,
            management_grade=management_grade,
            exit_grade=exit_grade,
            process_grade=process_grade,
            disqualifying_process_violation=disqualifying_process_violation,
            realized_R_if_plan_followed=realized_r_if_plan_followed,
            # Column is nullable; empty string fails the CHECK constraint.
            # Pass None when operator did not specify --mistake-cost-confidence.
            mistake_cost_confidence=mistake_cost_confidence or None,
            lesson_learned=lesson_learned,
            event_ts=reviewed_at,
            rationale=None,
        )
    finally:
        conn.close()

    click.echo(
        f"Review recorded for trade #{trade_id} ({trade.ticker}). "
        f"Process grade: {process_grade}."
    )


@main.group("review")
def review_group() -> None:
    """Cadence review — complete daily / weekly / monthly Review_Log entries."""


@review_group.command("complete")
@click.option("--list", "list_mode", is_flag=True,
              help="List pending Review_Log rows (completed_date IS NULL) and exit.")
@click.option("--review-id", type=int, default=None,
              help="REQUIRED unless --list is set.")
@click.option("--duration-minutes", type=int, default=None,
              help="REQUIRED unless --list. Operator-self-reported review duration.")
@click.option("--primary-lesson", default=None,
              help="REQUIRED unless --list. The single most important lesson.")
@click.option("--next-period-focus", default=None,
              help="REQUIRED unless --list. What to focus on next period.")
@click.pass_context
def review_complete_cmd(
    ctx, list_mode, review_id, duration_minutes, primary_lesson,
    next_period_focus,
):
    """Mark a Review_Log row complete + freeze aggregates atomically.

    Atomic compute-and-freeze per brief §6.2 watch item 3 — caller does
    NOT supply aggregates; complete_review_atomic owns the transaction.
    """
    from datetime import date as _date

    from swing.data.db import connect
    from swing.data.repos.review_log import (
        complete_review_atomic,
        list_pending,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        if list_mode:
            pending = list_pending(conn)
            if not pending:
                click.echo("No pending cadence reviews.")
                return
            click.echo("Pending cadence reviews:")
            for r in pending:
                click.echo(
                    f"  #{r.review_id} {r.review_type} "
                    f"{r.period_start}..{r.period_end} "
                    f"scheduled={r.scheduled_date}"
                )
            return

        missing = []
        if review_id is None:
            missing.append("--review-id")
        if duration_minutes is None:
            missing.append("--duration-minutes")
        if not primary_lesson or not primary_lesson.strip():
            missing.append("--primary-lesson")
        if not next_period_focus or not next_period_focus.strip():
            missing.append("--next-period-focus")
        if missing:
            raise click.UsageError(
                f"Missing required args (or pass --list to enter list mode): "
                f"{', '.join(missing)}"
            )

        complete_review_atomic(
            conn, review_id=review_id,
            completed_date=_date.today().isoformat(),
            duration_minutes=duration_minutes,
            primary_lesson=primary_lesson,
            next_period_focus=next_period_focus,
        )
    finally:
        conn.close()
    click.echo(f"Review #{review_id} marked complete + aggregates frozen.")


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
    from swing.data.repos.trades import list_closed_trades, list_open_trades
    from swing.journal.flags import compute_flags
    from swing.journal.stats import (
        compute_hypothesis_breakdown,
        compute_hypothesis_progress_breakdown,
        compute_stats,
        period_filter,
        render_hypothesis_progress,
    )

    cfg = ctx.obj["config"]
    today = today or _date.today().isoformat()
    conn = connect(cfg.paths.db_path)
    try:
        all_trades = list_open_trades(conn) + list_closed_trades(conn)
        all_exits = _list_all_exitshape_via_fills(conn)
        cash = list_cash(conn)
        weather_rows = conn.execute(
            "SELECT id, run_ts, asof_date, ticker, status, close, sma10, sma20, sma50, "
            "slope20_5bar, slope10_5bar, rationale FROM weather_runs"
        ).fetchall()
        # Per backend brief §4.5: "Hypothesis investigation progress"
        # section is registry-driven (not period-filtered) — operator wants
        # the full investigation state regardless of `--period`.
        progress_rows = compute_hypothesis_progress_breakdown(
            conn, starting_equity=cfg.account.starting_equity,
        )
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

    # Brief \u00a74.5: hypothesis breakdown \u2014 additive section after the existing
    # review output. Closed-only (matches compute_stats frame); section is
    # emitted only when at least one bucket exists so an empty journal stays
    # quiet.
    # Win-rate definition lives in `compute_hypothesis_breakdown.__doc__`
    # (brief §5 watch item: definition stated in docstring is acceptable).
    # Adversarial review round 1: M2 (display escaping) + m1 (definition note).
    import json as _json
    breakdown = compute_hypothesis_breakdown(trades=filtered, exits=all_exits)
    if breakdown:
        any_win_rate = any(b.win_rate is not None for b in breakdown)
        header = "\nHypothesis breakdown:"
        if any_win_rate:
            header += "  (win rate = fraction of trades with realized P&L > 0; shown when N>=3)"
        click.echo(header)
        for b in breakdown:
            # json.dumps escapes embedded quotes and any residual control bytes
            # — defense-in-depth on top of the service canonicalization (M2).
            label_display = (
                "(no label)" if b.label is None
                else _json.dumps(b.label, ensure_ascii=False)
            )
            n_word = "trade" if b.n_trades == 1 else "trades"
            line = f"  - {label_display}: {b.n_trades} {n_word}, ${b.total_pnl:.2f} total"
            if b.win_rate is not None:
                line += f", win rate {b.win_rate * 100:.1f}%"
            click.echo(line)

    # Backend brief §4.5: per-hypothesis investigation progress against
    # the pre-registered v0.1 plan. Always rendered (registry has 4 seed
    # rows; section gives the operator a stable at-a-glance view of
    # what's running, what's near target, what's tripped).
    click.echo(render_hypothesis_progress(progress_rows))


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
@click.option("--verbose", is_flag=True, help=(
    "Surface per-section row counts + per-fill price-comparison detail. "
    "Default output is byte-identical to the non-verbose summary; --verbose "
    "appends an extra block so silent extraction failures (3e.12) are "
    "observable-with-context."
))
@click.pass_context
def tos_import_cmd(ctx, csv_path, dry_run, auto_confirm, verbose):
    """Reconcile a TOS Account Statement CSV against the journal."""
    from pathlib import Path as _Path

    from swing.data.db import connect
    from swing.data.repos.cash import insert_cash
    from swing.journal.tos_import import extract_stock_fills, parse_tos_export, reconcile_tos

    cfg = ctx.obj["config"]
    text = _Path(csv_path).read_text(encoding="utf-8")
    # Surface absent required sections in default mode — the silent-zero
    # failure mode (3e.12) was operator-actionable only via verbose, which
    # left the bare `swing tos-import` invocation diagnostic-free. A
    # warning here is non-disruptive (synthetic fixture has both sections
    # so back-compat tests pass) and turns "matched=0" with no context
    # into "matched=0 because section X is missing — likely upstream
    # format drift."
    _required_sections = ("Cash Balance", "Account Trade History")
    _parsed_for_warn = parse_tos_export(text)
    for _section in _required_sections:
        if _section not in _parsed_for_warn:
            click.echo(
                f"WARNING: '{_section}' section not found in CSV — "
                f"upstream export format may have drifted; "
                f"re-run with --verbose for per-section diagnostics."
            )
    # Single source of truth for the price-comparison tolerance — passed
    # to reconcile_tos AND echoed in verbose output so any future change
    # propagates to both surfaces (Codex R2 Minor 1).
    price_tolerance = 0.01
    report = reconcile_tos(
        db_path=cfg.paths.db_path, tos_text=text,
        price_tolerance=price_tolerance,
    )

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

    if verbose:
        # Per-section diagnostic. Re-parses the text — cheap, and gives the
        # CLI direct visibility into what `parse_tos_export` saw without
        # widening the reconcile_tos return surface. Also surfaces the
        # silent-zero-result symptom (rows>0 but extracted_fills=0) directly.
        click.echo("")
        click.echo("--- VERBOSE diagnostic ---")
        bom_present = text.startswith("﻿")
        click.echo(
            f"[parse] encoding=utf-8 bom={'yes' if bom_present else 'no'} "
            f"chars={len(text)} bytes={len(text.encode('utf-8'))}"
        )
        sections = parse_tos_export(text)
        for section_label in (
            "Cash Balance", "Account Trade History", "Account Order History",
            "Futures Statements", "Forex Statements", "Crypto Statements",
            "Account Summary", "Equities", "Profits and Losses",
        ):
            rows = sections.get(section_label) or []
            present = "yes" if section_label in sections else "no"
            sample_summary = ""
            if rows:
                # First row's first 2-3 fields summarized — full dict can
                # be wide for ATH (13 cols) but the operator just needs a
                # shape sanity-check: are these the right kind of rows?
                first = rows[0]
                items = list(first.items())[:3]
                sample_summary = " sample={" + ", ".join(
                    f"{k!r}: {v!r}" for k, v in items
                ) + (", ..." if len(first) > 3 else "") + "}"
            click.echo(
                f"[section] {section_label}: detected={present} "
                f"rows={len(rows)}{sample_summary}"
            )
        ath_rows = sections.get("Account Trade History") or []
        skip_log: dict[str, int] = {}
        extracted = list(extract_stock_fills(ath_rows, _skip_log=skip_log))
        click.echo(
            f"[fills] extracted={len(extracted)} from "
            f"{len(ath_rows)} Account Trade History rows; "
            f"tolerance=${price_tolerance:.4f}"
        )
        if skip_log:
            skip_summary = " ".join(
                f"{reason}={count}" for reason, count in sorted(skip_log.items())
            )
            click.echo(f"[skipped] {skip_summary}")
        else:
            click.echo("[skipped] (none)")
        # Per-fill outcome with journal-vs-TOS price comparison.
        for d in report.fill_decisions:
            f = d.fill
            jp = (
                f"journal=${d.journal_price:.4f}"
                if d.journal_price is not None
                else "journal=N/A"
            )
            click.echo(
                f"  [{d.outcome}] {f.ticker} {f.date} {f.side} qty={f.qty} "
                f"TOS=${f.price:.4f} {jp} tol=${d.tolerance:.4f}"
            )

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
    from swing.config_overrides import apply_overrides
    from swing.pipeline import run_pipeline
    # Apply user-config overrides so sensitive cred fields (Finviz token /
    # screen_query) propagate when the web layer spawns this CLI subprocess.
    # Discriminating test for the propagation contract lives in Task 7.
    cfg = apply_overrides(ctx.obj["config"])
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
    click.echo("  Prior snapshot saved alongside")


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


@main.group("hypothesis")
def hypothesis_group() -> None:
    """Inspect + mutate the hypothesis investigation registry.

    Backend brief §4.6: only `--status` is mutable via CLI; frozen
    fields (target_sample_size, tripwire thresholds, decision criteria)
    can ONLY be changed via a NEW migration with explicit version bump.
    """


@hypothesis_group.command("list")
@click.pass_context
def hypothesis_list_cmd(ctx: click.Context) -> None:
    """List all registered hypotheses with status + sample progress."""
    from swing.data.db import connect
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import compute_tripwire_status

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        rows = list_hypotheses(conn)
        click.echo("ID  STATUS              N/TARGET  TRIPWIRE  NAME")
        for h in rows:
            tw = compute_tripwire_status(
                conn, hypothesis_id=h.id,
                starting_equity=cfg.account.starting_equity,
            )
            tw_label = "FIRED" if tw.any_tripwire_fired else "ok"
            click.echo(
                f"{h.id:<3} {h.status:<19} "
                f"{tw.current_sample}/{h.target_sample_size:<7} "
                f"{tw_label:<9} {h.name}"
            )
    finally:
        conn.close()


@hypothesis_group.command("status")
@click.argument("hypothesis_id", type=int)
@click.pass_context
def hypothesis_status_cmd(ctx: click.Context, hypothesis_id: int) -> None:
    """Print detailed status for one hypothesis."""
    from swing.data.db import connect
    from swing.data.repos.hypothesis import get_hypothesis
    from swing.recommendations.hypothesis import compute_tripwire_status

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        h = get_hypothesis(conn, hypothesis_id)
        if h is None:
            raise click.ClickException(f"hypothesis {hypothesis_id} not found")
        tw = compute_tripwire_status(
            conn, hypothesis_id=h.id,
            starting_equity=cfg.account.starting_equity,
        )
    finally:
        conn.close()

    click.echo(f"Hypothesis #{h.id}: {h.name}")
    click.echo(f"  Status:           {h.status}")
    click.echo(f"  Statement:        {h.statement}")
    click.echo(f"  Target sample:    {h.target_sample_size}")
    click.echo(f"  Current sample:   {tw.current_sample}")
    click.echo(f"  Decision criteria:{h.decision_criteria}")
    click.echo(
        f"  Consecutive -1R tripwire: streak {tw.consecutive_max_loss_streak} "
        f"of {h.consecutive_loss_tripwire}"
        + ("  [FIRED]" if tw.consecutive_tripwire_fired else "")
    )
    click.echo(
        f"  Absolute-loss tripwire:   cumulative ${tw.cumulative_loss:+.2f} "
        f"vs {h.absolute_loss_tripwire_pct:.1f}%-of-equity threshold"
        + ("  [FIRED]" if tw.absolute_tripwire_fired else "")
    )
    click.echo(f"  Created at:       {h.created_at}")
    if h.status_changed_at:
        click.echo(f"  Status changed:   {h.status_changed_at}")
        click.echo(f"  Status reason:    {h.status_change_reason or '(none)'}")


@hypothesis_group.command("update")
@click.argument("hypothesis_id", type=int)
@click.option(
    "--status", "new_status", required=True,
    type=click.Choice(["active", "paused", "closed-escaped", "closed-target-met"]),
    help="New status. Frozen fields (target, tripwire thresholds, "
         "decision_criteria) are NOT mutable via CLI.",
)
@click.option(
    "--reason", required=True,
    help="Required free-text reason; recorded to audit trail.",
)
@click.pass_context
def hypothesis_update_cmd(ctx: click.Context, hypothesis_id: int,
                          new_status: str, reason: str) -> None:
    """Update a hypothesis's status. Records change with timestamp + reason.

    Allowed transitions per brief §4.6:
      active   -> paused | closed-escaped | closed-target-met
      paused   -> active | closed-escaped
      closed-escaped -> active
      closed-target-met -> (terminal — no reopen via CLI)
    """
    from datetime import datetime as _dt

    from swing.data.db import connect
    from swing.data.repos.hypothesis import (
        HypothesisStatusTransitionError,
        update_hypothesis_status,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            try:
                update_hypothesis_status(
                    conn, hypothesis_id,
                    new_status=new_status,
                    reason=reason,
                    now_iso=_dt.now().isoformat(timespec="seconds"),
                )
            except HypothesisStatusTransitionError as exc:
                # Make the error message explicit so the test (and
                # operator) can tell it's a transition issue, not a
                # generic value error.
                raise click.ClickException(f"transition not allowed: {exc}") from exc
            except ValueError as exc:
                raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    click.echo(
        f"hypothesis #{hypothesis_id} -> {new_status} "
        f"(reason: {reason})"
    )


@main.group("finviz")
def finviz_group() -> None:
    """Finviz Elite API integration: fetch + status."""


@finviz_group.command("fetch")
@click.pass_context
def finviz_fetch_cmd(ctx: click.Context) -> None:
    """Fetch the saved-screen via Finviz Elite API + emit canonical CSV.

    Same file-collision behavior as the pipeline step: if today's CSV is
    already present in the inbox, fetch is skipped (manual override).
    """
    from swing.config_overrides import apply_overrides
    from swing.data.db import connect
    from swing.data.repos.finviz_api_calls import list_recent_calls
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    from swing.pipeline.runner import _perform_finviz_fetch_no_lease

    cfg = apply_overrides(ctx.obj["config"])
    conn = connect(cfg.paths.db_path)
    try:
        try:
            # Codex R2 Major-1: missing-credential failures route through the
            # shared helper so the audit trail (finviz_api_calls) records them
            # — same cross-surface observability as the pipeline step. The CLI
            # then translates a status='error' result into a friendly Click
            # exception (preserves the operator-facing token-missing message).
            _perform_finviz_fetch_no_lease(cfg=cfg, conn=conn)
        except FinvizPipelineActiveError as exc:
            raise click.ClickException(str(exc)) from exc
        # code-review I1 (2026-05-06): commit the audit row from the CLI body.
        # insert_call no longer commits internally (broke lease.fenced_write
        # transaction-control contract on the pipeline path); CLI raw-conn
        # callers commit explicitly here. Without this, the implicit
        # transaction would roll back at conn.close() below + the audit row
        # would be lost.
        conn.commit()
        recent = list_recent_calls(conn, limit=1)
        if recent:
            r = recent[0]
            click.echo(
                f"status={r.status}  rows={r.row_count}  "
                f"elapsed={r.response_time_ms}ms  "
                f"signature={(r.signature_hash or '')[:12]}"
            )
            if r.status == "error":
                # Surface the just-written audit row as a friendly CLI failure
                # so exit_code != 0 + the error_message is visible to the
                # operator. The audit row remains in the DB for `swing finviz
                # status` to display later.
                raise click.ClickException(
                    r.error_message or "Finviz fetch failed; see swing finviz status."
                )
    finally:
        conn.close()


@finviz_group.command("status")
@click.option(
    "--limit", type=int, default=10,
    help="Number of recent calls to show (default: 10).",
)
@click.pass_context
def finviz_status_cmd(ctx: click.Context, limit: int) -> None:
    """Show recent Finviz API call history (last N rows)."""
    from swing.data.db import connect
    from swing.data.repos.finviz_api_calls import list_recent_calls

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        rows = list_recent_calls(conn, limit=limit)
    finally:
        conn.close()
    if not rows:
        click.echo("No Finviz API calls recorded yet.")
        return
    click.echo(
        f"{'ts':<22} {'status':<26} {'rows':>5} {'elapsed':>9} "
        f"{'rl_left':>7} {'sig':<12}"
    )
    for r in rows:
        sig = (r.signature_hash or "")[:12].ljust(12)
        rc = r.row_count if r.row_count is not None else "-"
        rt = (
            f"{r.response_time_ms}ms"
            if r.response_time_ms is not None
            else "-"
        )
        rl = (
            r.rate_limit_remaining
            if r.rate_limit_remaining is not None
            else "-"
        )
        click.echo(
            f"{r.ts:<22} {r.status:<26} "
            f"{rc!s:>5} {rt:>9} {rl!s:>7} {sig}"
        )


if __name__ == "__main__":  # pragma: no cover
    main()
