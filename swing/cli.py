"""Click CLI for swing. Phase 1 subcommands: db-migrate, eval."""
from __future__ import annotations

import io as _io
import logging as _pe_backfill_logging
import sqlite3
import sys as _sys
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path

# Force UTF-8 on stdout/stderr so non-ASCII glyphs (§, →, ↔, etc.) in CLI
# output don't crash on Windows PowerShell's default cp1252 encoder.
# Same family as the matplotlib mathtext gotcha (CLAUDE.md): canonical fix is
# to remove the metacharacter from rendered text, but with 100+ § refs in
# classifier reason strings + spec citations, a systemic stdout reconfigure
# is the lower-risk path. Defense-in-depth alongside the ASCII swap of → to
# -> in swing/trades/reconciliation_backfill.py:_format_pass_2_line.
# Discovered 2026-05-17 during Phase 12 Sub-sub-bundle C.D operator-witnessed
# gate (S2 dry-run + S5 show-ambiguity both surfaced cp1252 mangling).
try:  # pragma: no cover — environment-dependent
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, _io.UnsupportedOperation):
    # Embedded consoles / non-TextIOWrapper streams (IDE / capture fixtures)
    # don't expose .reconfigure(); the original encoding is preserved.
    pass

import click
import pandas as pd

from swing.cli_config import config_group
from swing.cli_schwab import schwab_group
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


def _apply_toml_divergence_check(ctx: click.Context) -> None:
    """Phase 9 T-A.5 — post-schema-validation TOML divergence hook.

    Per Codex R3 M#1 architectural fix (plan §A.5.1): swing/config.py:load()
    REMAINS PURE; the divergence check moved here. Invoked from the
    @main.callback BEFORE every CLI subcommand EXCEPT db-migrate (which is
    the path that brings the DB to v17; running the check before the
    migration completes is the failure mode the helper's pre-v17
    silent-skip guards against — but the CLI ALSO skips defensively to
    avoid even opening the DB).

    On divergence: emits a stderr advisory line (mirrors pip / git
    divergence-warning pattern per spec §3.1.3 R3 Minor #2) AND rebinds
    ctx.obj["config"] to the corrected immutable Config. Subsequent CLI
    handler reads of cfg.account.risk_equity_floor see the policy value,
    NOT the stale TOML value.
    """
    from swing.trades.risk_policy import check_and_reconcile_toml_divergence

    cfg = ctx.obj["config"]
    db_path = cfg.paths.db_path
    if not db_path.exists():
        # Pre-migrate state — divergence check has nothing to compare against.
        return
    conn = sqlite3.connect(db_path)
    try:
        new_cfg, divergence = check_and_reconcile_toml_divergence(conn, cfg)
    finally:
        conn.close()
    if divergence is not None:
        click.echo(
            f"NOTE: TOML diverges from risk_policy: "
            f"cfg.account.risk_equity_floor={divergence['toml_value']} vs "
            f"risk_policy.capital_floor_constant_dollars={divergence['policy_value']}; "
            f"risk_policy is authoritative. To make TOML canonical, run: "
            f"swing config policy import-from-toml --field capital_floor_constant_dollars",
            err=True,
        )
        ctx.obj["config"] = new_cfg


# Subcommands that MUST NOT trigger the divergence hook. db-migrate is the
# canonical path that brings DB to v17; running the divergence check before
# the migration completes would either (a) silent-skip wastefully (the
# helper's pre-v17 path) or (b) surface a confusing advisory before the
# very table the operator is about to create exists. db-backup is a
# pure-IO operation with no policy semantics; skip too.
_DIVERGENCE_HOOK_SKIP_SUBCOMMANDS: frozenset[str] = frozenset({
    "db-migrate",
    "db-backup",
})


@click.group()
@click.option("--config", "config_path", default="swing.config.toml",
              help="Path to swing.config.toml")
@click.pass_context
def main(ctx: click.Context, config_path: str) -> None:
    """Swing trading CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(Path(config_path))
    ctx.obj["config_path"] = Path(config_path)
    if ctx.invoked_subcommand not in _DIVERGENCE_HOOK_SKIP_SUBCOMMANDS:
        _apply_toml_divergence_check(ctx)


main.add_command(config_group)
main.add_command(schwab_group)


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

    # Pre-version snoop so we can detect the v16 → v17 first-time landing
    # and ratify the migration's hard-coded seed against the operator's
    # actual swing.config.toml values (Codex R1 Major #1 fix). The
    # ratification ONLY fires on the v16 → v17 transition; subsequent
    # db-migrate invocations leave the active policy alone.
    pre_version = 0
    if db_path.exists():
        _probe = _sqlite3.connect(db_path)
        try:
            _row = _probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='schema_version'"
            ).fetchone()
            if _row is not None:
                _row2 = _probe.execute(
                    "SELECT version FROM schema_version"
                ).fetchone()
                pre_version = int(_row2[0]) if _row2 else 0
        finally:
            _probe.close()

    # Schwab API T-D.7 (plan §C.5 + §I.1): NO version-specific backup gate
    # fires for 17→18 because the Phase-9 gate is keyed on current==16 AND
    # target>=17. The auto-backup above still writes a defensive snapshot
    # to backups_dir, but plan §I.1 wants a visible operator-facing
    # recommendation to take a manual backup at a known location BEFORE
    # 0018 lands — defense-in-depth for the FIRST schema-change in the
    # Schwab arc. Fires only when pre_version < 18 (idempotent on rerun).
    if pre_version < 18:
        click.echo(
            "WARN: Migration 0018 (Schwab integration) will be applied. "
            "Manual backup recommended before continuing — copy "
            "%USERPROFILE%/swing-data/swing.db to "
            "swing.db.pre-phase11.backup as a recovery snapshot. "
            "(Auto-backup ALSO writes to backups_dir.)",
            err=True,
        )

    conn = ensure_schema(db_path)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    if pre_version <= 16 and version >= 17:
        # First-time v17 landing: ratify the migration's hard-coded seed
        # against cfg.{risk.max_risk_pct, position_limits.hard_cap_open,
        # account.risk_equity_floor, review.review_window_days} per spec
        # §3.1.3 SEED MAP. The migration cannot Python-eval cfg at
        # executescript time; this post-migration step is the canonical
        # cfg-derived seed.
        #
        # Codex R2 M#2 fix: ratify against the EFFECTIVE cfg (apply_overrides
        # over the raw load result) so any pre-Phase-9 user-config.toml
        # overrides for risk_equity_floor land in the seed too. Codex R2 M#3
        # fix: ratification failure raises ClickException (exits non-zero)
        # — leaving the DB at v17 with a wrong seed is worse than failing
        # the migrate command + asking the operator to fix the underlying
        # config error before re-running.
        from swing.config_overrides import apply_overrides
        from swing.trades.risk_policy import (
            ratify_seed_from_cfg_on_v17_landing,
        )
        effective_cfg = apply_overrides(cfg)
        try:
            ratified_id = ratify_seed_from_cfg_on_v17_landing(
                conn, effective_cfg,
            )
            if ratified_id is not None:
                click.echo(
                    f"Phase 9 ratification: superseded migration's hard-coded "
                    f"seed (policy_id=1) with cfg-derived values; new active "
                    f"policy_id={ratified_id}."
                )
        except Exception as exc:
            conn.close()
            raise click.ClickException(
                f"Phase 9 seed ratification failed: {exc}. The DB is at "
                f"v17 but the active policy seed may not match your "
                f"effective swing.config.toml + user-config.toml values. "
                f"Investigate the cfg field that failed validation, fix it, "
                f"then run the per-field repair path (the v17 ratification "
                f"will NOT re-fire on subsequent `swing db-migrate` because "
                f"pre_version is now 17). All four spec §3.1.3 mirrored "
                f"fields are repairable via `swing config policy "
                f"import-from-toml --field <name>` for: "
                f"capital_floor_constant_dollars, max_concurrent_positions, "
                f"review_lag_threshold_days, max_account_risk_per_trade_pct."
            ) from exc
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
    click.echo(
        f"Trade id {result.trade_id}: {ticker} {shares} sh @ "
        f"${entry_price:.2f}, stop ${initial_stop:.2f}"
    )


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
    click.echo(
        f"Exit {result.exit_id}: ${result.realized_pnl:+.2f} "
        f"({result.r_multiple:+.2f}R){closed}"
    )
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
    click.echo(
        f"{'ID':>4} {'Ticker':<6} {'Date':<10} {'Entry':>8} "
        f"{'Stop':>8} {'Sh':>4} {'State':<14}"
    )
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
@click.option("--adr-pct", type=float, default=None,
              help="trailing ~20-bar ADR%; drives §4.D parabolic_trim")
@click.option(
    "--maturity-stage",
    type=click.Choice(
        ["pre_+1.5R", "+1.5R_to_+2R", ">=+2R_trail_eligible"],
        case_sensitive=True,
    ),
    default=None,
    help=("Phase 8 daily-management maturity stage; drives §4.A.bis "
          "maturity_stage_trail_ma_hint advisory. Omit to skip the hint."),
)
@click.option("--weather", default="Bullish")
@click.option("--as-of-date", default=None, help="default: today")
@click.pass_context
def trade_advisory_cmd(ctx, trade_id, current_price, sma10, sma20, sma50,
                        previous_close, adr_pct, maturity_stage, weather,
                        as_of_date):
    """Print stop-advisory suggestions for an open trade."""
    from datetime import date as _date

    from swing.data.db import connect
    from swing.data.repos.fills import list_fills_for_trade
    from swing.data.repos.trades import get_trade
    from swing.trades.advisory import AdvisoryContext, compute_all_suggestions

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
        if trade is None:
            raise click.ClickException(f"trade {trade_id} not found")
        # 3e.8 Bundle 2 — load fills to derive has_been_trimmed so the new
        # §4.B trim_into_strength rule suppresses correctly on trades that
        # already have a non-entry fill. Same predicate as the web/pipeline
        # surfaces.
        fills = list_fills_for_trade(conn, trade_id)
    finally:
        conn.close()
    has_been_trimmed = any(f.action != "entry" for f in fills)
    asof = as_of_date or _date.today().isoformat()
    ctx_a = AdvisoryContext(
        as_of_date=asof, current_price=current_price,
        sma10=sma10, sma20=sma20,
        sma50=sma50, previous_close=previous_close,
        weather_status=weather,
        config=cfg.stop_advisory,
        adr_pct=adr_pct,
        has_been_trimmed=has_been_trimmed,
        maturity_stage=maturity_stage,
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


@journal_group.command("reconcile-tos")
@click.option(
    "--csv-path", "csv_path", required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to TOS Account Statement CSV.",
)
@click.option(
    "--period-end", default=None,
    help="Reconciliation period inclusive upper bound (YYYY-MM-DD).",
)
@click.option(
    "--period-start", default=None,
    help="Reconciliation period inclusive lower bound (YYYY-MM-DD).",
)
@click.option("--notes", default=None, help="Free-text operator note.")
@click.option(
    "--price-tolerance", type=float, default=0.01,
    help="Dollar threshold for price-mismatch detection (strict-greater-than).",
)
@click.pass_context
def journal_reconcile_tos_cmd(
    ctx, csv_path, period_end, period_start, notes, price_tolerance,
):
    """Reconcile a TOS Account Statement against the journal (Phase 9).

    Drives ``swing.trades.reconciliation.run_tos_reconciliation`` —
    INSERTs a ``reconciliation_runs`` row with discrepancies persisted
    in ``reconciliation_discrepancies``. Failure-path PRESERVES the
    row with ``state='failed'`` per spec §3.3.3.
    """
    from pathlib import Path as _Path

    from swing.data.db import connect
    from swing.trades.reconciliation import run_tos_reconciliation

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        run = run_tos_reconciliation(
            conn,
            csv_path=_Path(csv_path),
            period_end=period_end,
            period_start=period_start,
            notes=notes,
            price_tolerance=price_tolerance,
        )
    finally:
        conn.close()

    click.echo(
        f"Reconciliation run #{run.run_id}: state={run.state} "
        f"discrepancies={run.discrepancies_count or 0} "
        f"unresolved={run.unresolved_discrepancies_count or 0}"
    )
    if run.error_message:
        click.echo(f"Error: {run.error_message}", err=True)
        ctx.exit(1)
    if run.summary_json:
        import json as _json
        try:
            summary = _json.loads(run.summary_json)
            for k in sorted(summary.keys()):
                click.echo(f"  {k}: {summary[k]}")
        except (ValueError, TypeError):
            pass


@journal_group.command("import-tos")
@click.option(
    "--csv-path", "csv_path", required=True,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("--period-end", default=None)
@click.option("--period-start", default=None)
@click.option("--notes", default=None)
@click.option("--price-tolerance", type=float, default=0.01)
@click.pass_context
def journal_import_tos_cmd(
    ctx, csv_path, period_end, period_start, notes, price_tolerance,
):
    """Deprecated alias for ``swing journal reconcile-tos``.

    V1 retains this alias for one phase; alias removed in V2 per plan
    §A.2.2. Operator-visible stderr WARNING fires on every invocation.
    """
    click.echo(
        "WARNING: `swing journal import-tos` is deprecated; "
        "use `swing journal reconcile-tos` instead.",
        err=True,
    )
    ctx.invoke(
        journal_reconcile_tos_cmd,
        csv_path=csv_path,
        period_end=period_end,
        period_start=period_start,
        notes=notes,
        price_tolerance=price_tolerance,
    )


@journal_group.command("reconcile-backfill")
@click.option(
    "--apply", "apply_flag", is_flag=True, default=False,
    help=(
        "Actually execute backfill (mutates journal). Mutually exclusive "
        "with --dry-run."
    ),
)
@click.option(
    "--dry-run", "dry_run_flag", is_flag=True, default=False,
    help=(
        "Print projected classification only; no mutation. Mutually "
        "exclusive with --apply. Default mode when neither flag set."
    ),
)
@click.option(
    "--ticker", "ticker", type=str, default=None,
    help="Restrict iteration to a single ticker.",
)
@click.option(
    "--limit", "limit", type=int, default=None,
    help="Cap the number of discrepancies iterated.",
)
@click.option(
    "--no-pass-2-on-dry-run", "no_pass_2_on_dry_run", is_flag=True,
    default=False,
    help=(
        "Skip Pass-2 Schwab API calls during dry-run (T-D.8 consumer; "
        "no-op at T-D.6 scaffold)."
    ),
)
@click.option(
    "--retry-pass-2-failures", "retry_pass_2_failures", is_flag=True,
    default=False,
    help=(
        "Re-attempt Pass-2 on discrepancies whose previous backfill "
        "attempt failed at Pass 2 (idempotency hook; T-D.9 consumer)."
    ),
)
@click.pass_context
def journal_reconcile_backfill_cmd(
    ctx, apply_flag, dry_run_flag, ticker, limit,
    no_pass_2_on_dry_run, retry_pass_2_failures,
):
    """Backfill auto-correct + Tier-2 stamp across unresolved discrepancies.

    Phase 12 Sub-bundle C T-D.6 SCAFFOLD — iterates unresolved
    discrepancies + emits a per-row projection table. The actual
    Pass-1 / Pass-2 dispatch + tier-1 auto-apply + tier-2 stamp
    lands at T-D.7 / T-D.8 / T-D.9.

    Default mode is dry-run; pass ``--apply`` to actually execute.
    The two flags are mutually exclusive.
    """
    from swing.data.db import connect
    from swing.trades.reconciliation_backfill import (
        BackfillPipelineActiveError,
        format_projection_row,
        format_projection_table_header,
        format_projection_table_separator,
        format_summary_block,
        run_backfill,
    )

    # Mutually-exclusive --apply / --dry-run check per plan §E.6 #3.
    if apply_flag and dry_run_flag:
        raise click.UsageError(
            "--apply and --dry-run are mutually exclusive. Pass exactly "
            "one (or neither, for default dry-run).",
        )
    # Default behavior is dry-run unless --apply is explicit.
    dry_run = not apply_flag

    # Codex R1 Major #1 fix — apply_overrides() at CLI entry so the
    # cfg-cascade (env vars > user-config.toml > prompt) resolves
    # end-to-end. Mirrors Phase 12 Sub-bundle B forward-binding lesson
    # #6 (apply_overrides discipline at Schwab entry points). Fall back
    # to raw cfg if the helper can't operate on it (test fixtures supply
    # SimpleNamespace cfgs that bypass the Config dataclass round-trip).
    try:
        from swing.config_overrides import apply_overrides
        cfg = apply_overrides(ctx.obj["config"])
    except (AttributeError, TypeError):
        cfg = ctx.obj["config"]

    conn = connect(cfg.paths.db_path)
    try:
        environment = cfg.integrations.schwab.environment
        account_hash = getattr(
            cfg.integrations.schwab, "account_hash", None,
        )

        # Codex R1 Major #1 fix — construct the Schwab client at the CLI
        # entry so Pass 2 (T-D.8) actually has a live client to call
        # ``account_orders`` on. Without this, the previous scaffold
        # passed ``schwab_client=None`` and Pass 2's
        # ``get_account_orders_audited`` dereferenced ``client.account_orders``
        # → AttributeError; production --apply for DHC/VSAT would not
        # perform the audited Schwab re-fetch + would persist a fake
        # Pass-2 failure instead of real tier-2 ambiguity classification.
        #
        # Construction is short-circuited when:
        #   * environment == 'sandbox' (the C.C sandbox short-circuit
        #     LOCK fires at the inner service function regardless of
        #     whether the client was constructed — pass None to avoid
        #     burning OAuth state on a sandbox run);
        #   * dry_run AND no_pass_2_on_dry_run (caller opted out of
        #     Pass 2 entirely; client construction would be pure waste
        #     + would prompt unnecessarily when env vars are unset).
        #
        # Otherwise mirror ``swing schwab fetch`` preflight verbatim:
        # preflight account_hash + resolve credentials via cfg-cascade +
        # build schwabdev client.
        from swing.cli_schwab import (
            _build_schwabdev_client_for_fetch,
            _resolve_credentials_for_cli,
        )
        from swing.integrations.schwab.client import (
            SchwabAuthError,
            SchwabConfigMissingError,
        )

        schwab_client = None
        # Skip construction entirely under sandbox (C.C inner short-circuit
        # fires regardless) and under --dry-run + --no-pass-2-on-dry-run
        # (operator explicitly opted out of Pass 2).
        skip_client_construction = (
            environment == "sandbox"
            or (dry_run and no_pass_2_on_dry_run)
        )
        if not skip_client_construction:
            # --apply mode REQUIRES the client (Pass-2 dispatch must
            # actually re-fetch Schwab orders). Dry-run mode without
            # --no-pass-2-on-dry-run also wants the client (Pass 2 still
            # fires unless explicitly skipped). For both modes,
            # account_hash + credentials are mandatory preflight.
            if not account_hash:
                if not dry_run:
                    raise click.ClickException(
                        f"Schwab account_hash not configured. "
                        f"Run `swing schwab setup --environment "
                        f"{environment}` first."
                    )
                # Dry-run: emit advisory + leave client=None. If a
                # Pass-2-required discrepancy is reached, dispatch will
                # surface a Pass-2 re-fetch failure with descriptive
                # reason. This preserves the operator's ability to run
                # dry-run previews against pre-Phase-11 DBs where
                # account_hash was never configured.
                click.echo(
                    "(advisory) Schwab account_hash not configured; "
                    "Pass-2 dispatch will fail for unmatched_*_fill "
                    "discrepancies. Run `swing schwab setup` to enable "
                    "Pass-2 re-fetch.",
                    err=True,
                )
            else:
                try:
                    client_id, client_secret = _resolve_credentials_for_cli(
                        cfg, environment,
                    )
                except (click.ClickException, SchwabConfigMissingError) as exc:
                    # Codex R2 Major #1 fix — ``_resolve_credentials_for_cli``
                    # translates ``SchwabConfigMissingError`` into
                    # ``click.ClickException`` BEFORE the exception escapes
                    # (see ``swing/cli_schwab.py:126``). Catching ONLY
                    # ``SchwabConfigMissingError`` here was a no-op: the
                    # original exception was already a ``ClickException``
                    # by the time it reached this frame, so missing
                    # credentials still hard-failed even under ``--dry-run``.
                    # Catching both types preserves both paths:
                    #   * ``click.ClickException`` — actual cfg-cascade
                    #     resolution failure (what R1 surfaced).
                    #   * ``SchwabConfigMissingError`` — defense-in-depth
                    #     for any future surface that returns the typed
                    #     exception unwrapped.
                    if not dry_run:
                        # Re-raise ClickException as-is (already formatted);
                        # wrap raw SchwabConfigMissingError for parity.
                        if isinstance(exc, click.ClickException):
                            raise
                        raise click.ClickException(str(exc)) from exc
                    # Dry-run soft-fail (operator may not have shell
                    # env vars set for a non-destructive preview).
                    click.echo(
                        f"(advisory) Schwab credentials unavailable: "
                        f"{exc}. Pass-2 dispatch will fail for "
                        "unmatched_*_fill discrepancies.",
                        err=True,
                    )
                    client_id = None
                    client_secret = None
                if client_id is not None:
                    try:
                        schwab_client = _build_schwabdev_client_for_fetch(
                            cfg, environment, client_id, client_secret,
                        )
                    except SchwabAuthError as exc:
                        if not dry_run:
                            raise click.ClickException(
                                f"Authentication failed: {exc}",
                            ) from exc
                        click.echo(
                            f"(advisory) Schwab authentication failed: "
                            f"{exc}. Pass-2 dispatch will fail.",
                            err=True,
                        )
                    except SchwabConfigMissingError as exc:
                        if not dry_run:
                            raise click.ClickException(str(exc)) from exc
                        click.echo(
                            f"(advisory) Schwab config missing: {exc}. "
                            "Pass-2 dispatch will fail.",
                            err=True,
                        )

        try:
            summary = run_backfill(
                conn,
                dry_run=dry_run,
                schwab_client=schwab_client,
                environment=environment,
                account_hash=account_hash,
                ticker=ticker,
                limit=limit,
                no_pass_2_on_dry_run=no_pass_2_on_dry_run,
                retry_pass_2_failures=retry_pass_2_failures,
            )
        except BackfillPipelineActiveError as exc:
            # Codex R2 Major #3 — surface partial-progress summary before
            # the user-friendly error so the operator sees which rows
            # were already committed. The exception carries the partial
            # summary as ``exc.partial_summary`` when the abort happened
            # mid-iteration (rows already processed have committed via
            # their own service-layer txs). When the abort happened at
            # entry (no iteration ran), partial_summary is None.
            partial = getattr(exc, "partial_summary", None)
            if partial is not None and partial.per_discrepancy_outcomes:
                click.echo("Backfill aborted mid-iteration:\n")
                click.echo(format_projection_table_header())
                click.echo(format_projection_table_separator())
                for outcome in partial.per_discrepancy_outcomes:
                    click.echo(format_projection_row(outcome))
                click.echo(format_summary_block(partial))
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    if not summary.per_discrepancy_outcomes:
        click.echo("(no unresolved discrepancies)")
        return

    # Acceptance criterion #4 — dry-run projection matrix preamble.
    if dry_run:
        click.echo("Backfill --dry-run projection:\n")
    else:
        click.echo("Backfill --apply results:\n")
    click.echo(format_projection_table_header())
    click.echo(format_projection_table_separator())
    for outcome in summary.per_discrepancy_outcomes:
        click.echo(format_projection_row(outcome))
    click.echo(format_summary_block(summary))


@journal_group.group("discrepancy")
def discrepancy_group() -> None:
    """Phase 9 reconciliation discrepancy review + resolution."""


@discrepancy_group.command("list")
@click.option("--unresolved", is_flag=True, help="Only show unresolved rows.")
@click.option(
    "--material", is_flag=True,
    help="Only show rows with material_to_review=1.",
)
@click.option(
    "--trade-id", type=int, default=None, help="Filter to a specific trade.",
)
@click.option("--limit", type=int, default=50, help="Max rows to show.")
@click.option(
    "--resolved-by",
    type=str,
    default=None,
    help=(
        "Filter to a specific resolved_by value (e.g., "
        "'auto_tier1_multi_leg' for multi-leg auto-corrections)."
    ),
)
@click.pass_context
def discrepancy_list_cmd(
    ctx, unresolved, material, trade_id, limit, resolved_by,
):
    """List reconciliation discrepancies with optional filters."""
    from swing.data.db import connect

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        where = []
        params: list = []
        if unresolved:
            where.append("resolution = 'unresolved'")
        if material:
            where.append("material_to_review = 1")
        if trade_id is not None:
            where.append("trade_id = ?")
            params.append(trade_id)
        if resolved_by is not None:
            where.append("resolved_by = ?")
            params.append(resolved_by)
        sql = (
            "SELECT discrepancy_id, run_id, discrepancy_type, trade_id, "
            "ticker, field_name, material_to_review, resolution, delta_text "
            "FROM reconciliation_discrepancies"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY discrepancy_id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if not rows:
        click.echo("(no discrepancies)")
        return
    click.echo(
        f"{'ID':>5} {'Run':>4} {'Type':<22} {'Trade':>6} "
        f"{'Ticker':<8} {'Field':<14} {'Mat':>3} {'Resolution':<22} Delta"
    )
    for r in rows:
        did, rid, dtype, tid, tk, fn, mat, res, dt = r
        click.echo(
            f"{did:>5} {rid:>4} {dtype:<22} "
            f"{(tid if tid is not None else '-'):>6} "
            f"{(tk or '-'):<8} {fn:<14} {mat:>3} {res:<22} {dt or ''}"
        )


@discrepancy_group.command("list-pending-ambiguities")
@click.option(
    "--ambiguity-kind", type=str, default=None,
    help="Filter to a specific ambiguity_kind value.",
)
@click.option(
    "--ticker", type=str, default=None,
    help="Filter to a specific ticker.",
)
@click.option("--limit", type=int, default=50, help="Max rows to show.")
@click.pass_context
def discrepancy_list_pending_ambiguities_cmd(
    ctx, ambiguity_kind, ticker, limit,
):
    """List discrepancies pending operator ambiguity resolution.

    Surfaces rows in ``resolution='pending_ambiguity_resolution'`` (Phase
    12 Sub-bundle C Tier-2 state) for operator review before invoking
    ``resolve-ambiguity`` (T-D.3). Mirrors the existing ``discrepancy
    list`` shape; adds an ``Ambiguity`` column for the per-row
    ``ambiguity_kind`` discriminator.
    """
    from swing.data.db import connect

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        where = ["resolution = 'pending_ambiguity_resolution'"]
        params: list = []
        if ambiguity_kind:
            where.append("ambiguity_kind = ?")
            params.append(ambiguity_kind)
        if ticker:
            where.append("ticker = ?")
            params.append(ticker)
        sql = (
            "SELECT discrepancy_id, run_id, discrepancy_type, trade_id, "
            "ticker, field_name, ambiguity_kind, created_at "
            "FROM reconciliation_discrepancies WHERE "
            + " AND ".join(where)
            + " ORDER BY discrepancy_id DESC LIMIT ?"
        )
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if not rows:
        click.echo("(no pending ambiguities)")
        return
    click.echo(
        f"{'ID':>5} {'Run':>4} {'Type':<22} {'Trade':>6} "
        f"{'Ticker':<8} {'Field':<14} {'Ambiguity':<32} Created"
    )
    for r in rows:
        did, rid, dtype, tid, tk, fn, ak, created = r
        click.echo(
            f"{did:>5} {rid:>4} {dtype:<22} "
            f"{(tid if tid is not None else '-'):>6} "
            f"{(tk or '-'):<8} {fn:<14} {(ak or '-'):<32} {created or ''}"
        )


@discrepancy_group.command("show")
@click.argument("discrepancy_id", type=int)
@click.pass_context
def discrepancy_show_cmd(ctx, discrepancy_id):
    """Print full detail for a single discrepancy."""
    from swing.data.db import connect
    from swing.data.repos.reconciliation import get_discrepancy

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        d = get_discrepancy(conn, discrepancy_id)
    finally:
        conn.close()
    if d is None:
        raise click.ClickException(f"discrepancy {discrepancy_id} not found")
    click.echo(f"discrepancy_id: {d.discrepancy_id}")
    click.echo(f"run_id:         {d.run_id}")
    click.echo(f"type:           {d.discrepancy_type}")
    click.echo(f"trade_id:       {d.trade_id}")
    click.echo(f"fill_id:        {d.fill_id}")
    click.echo(f"cash_id:        {d.cash_movement_id}")
    click.echo(f"ticker:         {d.ticker}")
    click.echo(f"field:          {d.field_name}")
    click.echo(f"material:       {d.material_to_review}")
    click.echo(f"expected:       {d.expected_value_json}")
    click.echo(f"actual:         {d.actual_value_json}")
    click.echo(f"delta:          {d.delta_text}")
    click.echo(f"resolution:     {d.resolution}")
    click.echo(f"reason:         {d.resolution_reason}")
    click.echo(f"resolved_at:    {d.resolved_at}")
    click.echo(f"resolved_by:    {d.resolved_by}")
    click.echo(f"mistake_tag:    {d.mistake_tag_assigned}")
    click.echo(f"created_at:     {d.created_at}")


@discrepancy_group.command("show-ambiguity")
@click.argument("discrepancy_id", type=int)
@click.pass_context
def discrepancy_show_ambiguity_cmd(ctx, discrepancy_id):
    """Print discrepancy detail + the per-``ambiguity_kind`` choice menu.

    Surfaces the choices the operator can pass to ``resolve-ambiguity``
    via ``--choice <code>``. For ``multi_match_within_window``, the
    parametric ``pick_schwab_record_<N>`` entries are constructed from
    the candidate count parsed best-effort out of ``resolution_reason``
    (V1 source per plan §E.2 acceptance criterion #4; no dedicated
    ``candidate_choices_json`` column — banked V2 candidate §I.13).
    """
    import json
    import re

    from swing.data.db import connect
    from swing.data.repos.reconciliation import get_discrepancy
    from swing.trades.reconciliation_ambiguity_choices import (
        ChoiceMenuItem,
        get_choice_menu,
    )
    from swing.trades.reconciliation_render import (
        build_compared_pairs,
        render_journal_schwab_comparison_table_ascii,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        d = get_discrepancy(conn, discrepancy_id)
    finally:
        conn.close()
    if d is None:
        raise click.ClickException(
            f"discrepancy {discrepancy_id} not found"
        )
    # --- Shared discrepancy detail (mirrors discrepancy_show_cmd). ---
    click.echo(f"discrepancy_id: {d.discrepancy_id}")
    click.echo(f"run_id:         {d.run_id}")
    click.echo(f"type:           {d.discrepancy_type}")
    click.echo(f"trade_id:       {d.trade_id}")
    click.echo(f"fill_id:        {d.fill_id}")
    click.echo(f"ticker:         {d.ticker}")
    click.echo(f"field:          {d.field_name}")
    click.echo(f"material:       {d.material_to_review}")
    click.echo(f"expected:       {d.expected_value_json}")
    click.echo(f"actual:         {d.actual_value_json}")
    click.echo(f"delta:          {d.delta_text}")
    click.echo(f"resolution:     {d.resolution}")
    click.echo(f"ambiguity_kind: {d.ambiguity_kind}")
    click.echo(f"reason:         {d.resolution_reason}")
    click.echo(f"created_at:     {d.created_at}")

    # ----------------------------------------------------------------
    # Journal vs Schwab comparison table (T-Q2.4; brief §A.4).
    # Render the shared compared-pairs table after the disc detail header
    # and before the choice menu.  ASCII-only via cp1252-safe renderer.
    # Defensive JSON parsing matches the web VM's _render_pre_resolution_context
    # graceful-degradation contract: silently skip the table on parse failure.
    # ----------------------------------------------------------------
    try:
        _exp = json.loads(d.expected_value_json) if d.expected_value_json else {}
        _act = json.loads(d.actual_value_json) if d.actual_value_json else {}
    except (json.JSONDecodeError, TypeError):
        _exp = {}
        _act = {}
    if isinstance(_exp, dict) and isinstance(_act, dict):
        try:
            _pairs = build_compared_pairs(d.discrepancy_type, _exp, _act)
        except (KeyError, ValueError, TypeError):
            _pairs = None
        if _pairs is not None:
            click.echo("")
            if len(_pairs) > 0:
                click.echo(
                    render_journal_schwab_comparison_table_ascii(list(_pairs))
                )
            else:
                click.echo("(no comparison data)")

    # --- Choice menu per spec §6.2.1. ---
    click.echo("")
    if d.ambiguity_kind is None:
        click.echo(
            "(no candidate choices: discrepancy has no ambiguity_kind; "
            "not a Tier-2 pending row)"
        )
        return

    menu = get_choice_menu(d.ambiguity_kind)

    # multi_match_within_window: prepend parametric pick_schwab_record_<N>
    # entries derived best-effort from resolution_reason text. V1 source
    # per plan §E.2 acceptance criterion #4 — the classifier emits
    # ``Schwab returned <N> orders within the match window`` in the
    # reason. Fall through to static-only menu on parse failure
    # (defense-in-depth).
    if d.ambiguity_kind == "multi_match_within_window":
        parametric: list[ChoiceMenuItem] = []
        reason = d.resolution_reason or ""
        m = re.search(
            r"Schwab returned\s+(\d+)\s+orders within the match window",
            reason,
        )
        if m:
            n = int(m.group(1))
            for i in range(n):
                parametric.append(
                    ChoiceMenuItem(
                        code=f"pick_schwab_record_{i + 1}",
                        description=(
                            f"Pick Schwab candidate #{i + 1} as the "
                            f"canonical source for this fill (REQUIRES "
                            f"--custom-value with operator-supplied "
                            f"execution-level field values; Pass-2 "
                            f"candidates are order-grain not "
                            f"execution-grain per spec §4.3.2 LOCK)."
                        ),
                        requires_custom_value=True,
                        expected_payload_shape_description=(
                            '{"price": X.XX, "quantity": Q, '
                            '"fill_datetime": "..."}'
                        ),
                    )
                )
        menu = parametric + menu

    if not menu:
        click.echo(
            f"(no candidate choices for ambiguity_kind="
            f"{d.ambiguity_kind!r}; helper module not updated for "
            f"this kind — V1 forward-compatibility surface)"
        )
        return

    click.echo("Candidate choices (pass to resolve-ambiguity via --choice):")
    click.echo("")
    # RECOMMENDED entries surface first (operator scan-first per OQ-4).
    recommended_items = [it for it in menu if it.recommended]
    other_items = [it for it in menu if not it.recommended]
    for it in recommended_items + other_items:
        prefix = "[RECOMMENDED] " if it.recommended else "  "
        marker = " *" if it.requires_custom_value else ""
        click.echo(f"{prefix}{it.code}{marker}")
        click.echo(f"    {it.description}")
        if it.requires_custom_value:
            shape = it.expected_payload_shape_description
            if shape is not None:
                click.echo(
                    f"    * REQUIRES --custom-value with shape "
                    f"{shape}"
                )
            else:
                click.echo(
                    "    * REQUIRES --custom-value '<json>' payload"
                )
        click.echo("")


# Phase 12 Sub-bundle C.C lesson #1 — the 4 service-owned ``resolution``
# values must NOT be accepted as ``--choice`` values on the manual
# resolve-ambiguity surface (per plan §E.3 acceptance criterion + brief
# §0.5 #1 LOCK). These route through canonical C.C service entries
# (apply_tier1_correction via the pivot dispatcher; apply_tier2_resolution
# via this very CLI surface; apply_tier3_override via the override-
# correction CLI at T-D.4; stamp_pending_ambiguity via the pivot stamp).
# Mirrors ``_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS`` discipline introduced
# in C.C for ``resolve_discrepancy`` (CLAUDE.md gotcha
# "Schema-coverage Python constant is NOT necessarily the manual-input
# allowlist").
_TIER2_SERVICE_OWNED_RESOLUTION_VALUES = frozenset({
    "auto_corrected_from_schwab",
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
})


@discrepancy_group.command("resolve-ambiguity")
@click.argument("discrepancy_id", type=int)
@click.option(
    "--choice", "choice_code", required=True,
    help=(
        "Choice code from the per-ambiguity_kind menu surfaced by "
        "`swing journal discrepancy show-ambiguity <id>`. Must NOT be one "
        "of the 4 service-owned resolution values (those route through "
        "canonical service entries, not this manual surface)."
    ),
)
@click.option(
    "--custom-value", "custom_value", default=None,
    help=(
        "JSON payload for choices flagged `requires_custom_value=True` "
        "(per spec §6.2.1 menu). Parsed via json.loads; deeper shape "
        "validation lives at service-layer apply-time per-handler."
    ),
)
@click.option(
    "--reason", "reason", required=True,
    help=(
        "Operator-supplied free-text rationale (REQUIRED per spec §6.4 "
        "mandatory + §6.2 Codex R5 LOCK). Persisted on the new "
        "reconciliation_corrections row as `correction_reason`."
    ),
)
@click.option(
    "--schwab-api-call-id", "schwab_api_call_id", type=int, default=None,
    help=(
        "Optional `schwab_api_calls.call_id` to back-link the new "
        "correction row to. When supplied, the new row's "
        "`schwab_api_call_id` populates AND "
        "`schwab_api_calls.linked_correction_id` back-links via the C.C "
        "audit-chain helper. Operator-facing discovery: the backfill "
        "Pass-2 dry-run output (T-D.5) emits per-discrepancy "
        "`call_id=<N>` lines for copy-paste."
    ),
)
@click.pass_context
def discrepancy_resolve_ambiguity_cmd(
    ctx,
    discrepancy_id,
    choice_code,
    custom_value,
    reason,
    schwab_api_call_id,
):
    """Resolve a pending_ambiguity_resolution discrepancy via operator choice.

    Operator workflow (per plan §E.1 + §E.2 + §E.3):

    1. ``swing journal discrepancy list-pending-ambiguities`` — surface
       the discrepancy_id of interest.
    2. ``swing journal discrepancy show-ambiguity <id>`` — read the
       per-ambiguity_kind candidate choice menu (REQUIRES markers tell
       you which need --custom-value + the expected JSON shape).
    3. ``swing journal discrepancy resolve-ambiguity <id> --choice
       <code> --reason '<rationale>' [--custom-value '<json>']
       [--schwab-api-call-id <N>]`` — this surface.

    The CLI delegates to ``apply_tier2_resolution`` in
    ``swing.trades.reconciliation_auto_correct`` which owns the
    BEGIN IMMEDIATE / COMMIT / ROLLBACK transaction envelope + the
    per-(``ambiguity_kind``, ``choice_code``) handler dispatch + the
    validator-chain re-invocation defense-in-depth + the journal
    mutation + the audit row INSERT + the discrepancy resolution
    UPDATE.
    """
    import json as _json

    from swing.data.db import connect
    from swing.data.repos.reconciliation import get_discrepancy
    from swing.trades.reconciliation_ambiguity_choices import (
        get_choice_menu,
    )
    from swing.trades.reconciliation_auto_correct import (
        AlreadySupersededError,
        CallerHeldTransactionError,
        ValidatorRejectedError,
        apply_tier2_resolution,
    )
    from swing.trades.risk_policy import read_active_policy

    # NEW C.C lesson #1 — service-owned-state rejection at the CLI
    # boundary, BEFORE the DB is even opened. Routing-hint substring in
    # the error message tells operator where to go next.
    #
    # Codex R1 Minor #1 fix — normalize the operator-supplied --choice
    # value (strip surrounding whitespace + lowercase) BEFORE the
    # membership check. Without normalization a copy/paste with stray
    # whitespace or upper-case drift (' auto_corrected_from_schwab ' /
    # 'AUTO_CORRECTED_FROM_SCHWAB') falls through to generic-incompatible
    # handling, losing the routing-hint substring. The downstream
    # ``apply_tier2_resolution`` dispatch table is case-sensitive so we
    # only apply the normalization to THIS rejection check; the original
    # `choice_code` is passed through verbatim to the service layer
    # (which will then surface its own incompatible-choice error if the
    # case-drift was genuinely a typo rather than a service-owned value).
    if (
        choice_code is not None
        and choice_code.strip().lower()
        in _TIER2_SERVICE_OWNED_RESOLUTION_VALUES
    ):
        raise click.UsageError(
            f"--choice {choice_code!r} is a service-owned resolution "
            "value and is NOT accepted on this manual surface; those "
            "values route through canonical service entries (the pivot "
            "dispatcher in `apply_tier1_correction` / "
            "`apply_tier2_resolution` / `apply_tier3_override` — "
            "operator-driven via `override-correction` for "
            "tier-3 + this `resolve-ambiguity` for tier-2). Pick a "
            "choice from the per-ambiguity_kind menu surfaced by "
            "`swing journal discrepancy show-ambiguity <id>`."
        )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        d = get_discrepancy(conn, discrepancy_id)
        if d is None:
            raise click.ClickException(
                f"discrepancy {discrepancy_id} not found"
            )
        if d.ambiguity_kind is None:
            raise click.UsageError(
                f"discrepancy {discrepancy_id} has no ambiguity_kind "
                f"(resolution={d.resolution!r}); resolve-ambiguity is "
                f"only valid for Tier-2 pending_ambiguity_resolution "
                f"rows. Use `swing journal discrepancy resolve` for the "
                f"manual resolution surface, or `swing journal "
                f"discrepancy override-correction` for tier-3 overrides."
            )

        # Validate --choice against the per-ambiguity_kind menu BEFORE
        # touching the service layer (per plan §E.3 acceptance criterion
        # #3 + #4). The classifier's menu for multi_match_within_window
        # is static + parametric — for the parametric pick_schwab_record_<N>
        # branch we delegate to the service-layer dispatcher (which has
        # access to the actual candidate count via its handler-key
        # parametric-prefix dispatch); here we only enforce the static
        # member list + the per-choice --custom-value requirement.
        menu = get_choice_menu(d.ambiguity_kind)
        static_codes = {it.code for it in menu}
        # Per-choice --custom-value enforcement requires the
        # `requires_custom_value` flag from the menu entry; record it.
        is_parametric_pick = (
            d.ambiguity_kind == "multi_match_within_window"
            and choice_code.startswith("pick_schwab_record_")
        )

        if choice_code in static_codes:
            menu_item = next(it for it in menu if it.code == choice_code)
            if menu_item.requires_custom_value and custom_value is None:
                shape = (
                    menu_item.expected_payload_shape_description
                    or "<json>"
                )
                raise click.UsageError(
                    f"--custom-value is required for choice "
                    f"{choice_code!r}; expected JSON shape: {shape}"
                )
        elif is_parametric_pick:
            # Parametric pick_schwab_record_<N> ALWAYS requires
            # --custom-value (per T-D.2's parametric entry's
            # `requires_custom_value=True`).
            if custom_value is None:
                raise click.UsageError(
                    f"--custom-value is required for choice "
                    f"{choice_code!r}; expected JSON shape: "
                    '{"price": X.XX, "quantity": Q, '
                    '"fill_datetime": "..."}'
                )
        else:
            valid = sorted(static_codes)
            raise click.UsageError(
                f"--choice {choice_code!r} is not compatible with "
                f"ambiguity_kind={d.ambiguity_kind!r}; valid choices "
                f"per spec §6.2.1 menu: {valid}"
            )

        # Parse --custom-value as JSON (per plan §E.3 acceptance criterion
        # #5 — shape predicate tightening lives at service layer; CLI does
        # basic parse + service handles deeper shape rejection).
        parsed_payload = None
        if custom_value is not None:
            try:
                parsed_payload = _json.loads(custom_value)
            except _json.JSONDecodeError as e:
                raise click.UsageError(
                    f"--custom-value is not valid JSON: {e}; "
                    "expected a JSON object/array per the choice's "
                    "expected_payload_shape_description"
                ) from None

        # Resolve active risk policy id (Phase 9 Sub-bundle A surface).
        active_policy = read_active_policy(conn)

        try:
            result = apply_tier2_resolution(
                conn,
                discrepancy_id=discrepancy_id,
                choice_code=choice_code,
                operator_custom_payload=parsed_payload,
                operator_reason=reason,
                risk_policy_id=active_policy.policy_id,
                schwab_api_call_id=schwab_api_call_id,
            )
            # The C.C tier-2 handlers stamp the forward FK
            # (reconciliation_corrections.schwab_api_call_id) but only
            # the tier-1 path invokes `_back_link_schwab_api_call`. To
            # close the bidirectional audit chain per plan §E.3
            # acceptance criterion #5, back-link from the CLI in a
            # separate-but-immediate transaction. Best-effort: if the
            # service returned a sandbox-style no-op (correction_id is
            # None) or no --schwab-api-call-id was supplied, skip.
            if (
                schwab_api_call_id is not None
                and result.correction_id is not None
            ):
                from swing.data.repos.schwab_api_calls import (
                    update_call_linked_correction,
                )
                conn.execute("BEGIN IMMEDIATE")
                try:
                    update_call_linked_correction(
                        conn,
                        call_id=schwab_api_call_id,
                        correction_id=result.correction_id,
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
        except CallerHeldTransactionError as e:
            # Should not happen in the CLI path (connection is fresh) —
            # surface as a friendly error rather than a stack trace.
            raise click.ClickException(
                f"transactional discipline violation: {e}"
            ) from None
        except AlreadySupersededError as e:
            raise click.ClickException(str(e)) from None
        except ValidatorRejectedError as e:
            raise click.ClickException(
                f"validator rejected the operator choice: {e}"
            ) from None
        except ValueError as e:
            # Service-layer ValueError covers: incompatible (kind,
            # choice); missing required payload on the handler; malformed
            # payload at handler-level shape validation. Map to
            # UsageError (exit 2) per plan §E.3 acceptance criterion #9.
            raise click.UsageError(str(e)) from None
    finally:
        conn.close()

    click.echo(
        f"resolved discrepancy {discrepancy_id} via choice "
        f"{choice_code!r}; correction_id={result.correction_id}"
    )


# ---------------------------------------------------------------------------
# T-D.4 — `swing journal discrepancy override-correction` CLI surface
# (per plan §E.4 + spec §6.4 + OQ-8 confirmation prompt + OQ-15
# AlreadySupersededError chain-head guidance). Routes through the
# canonical C.C service entry `apply_tier3_override` which owns the
# BEGIN IMMEDIATE / COMMIT / ROLLBACK transaction envelope + validator
# chain re-run defense-in-depth + journal mutation + audit row INSERT.
# ---------------------------------------------------------------------------

# Sub-bundle 1 T-1.12 — GENERIC + ID-FREE historical-correction addendum
# (per spec §8.3 OQ-G + plan §A.1.12 R1 M#8 + R2 M#3 + R3 m#1 LOCK).
#
# Single source of truth — appears verbatim as the `--help` epilog on
# `swing journal discrepancy show-correction` AND `override-correction`
# subcommands. Operators reviewing pre-Sub-bundle-1 correction chains see
# this addendum at help-time + know the V1 historical context (order-grain
# vs execution-grain price provenance) without needing the implementer to
# bake operator-local correction IDs into help text.
_HISTORICAL_CORRECTION_NOTE: str = (
    "Note: reconciliation_corrections rows recorded PRIOR to the V2 "
    "mapper widening (swing/integrations/schwab/mappers.py extension to "
    "surface orderActivityCollection[].executionLegs[]; design doc: "
    "docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md) "
    "carry ORDER-grain prices in schwab_said_value_json -- the V1 mapper "
    "read order.price (LIMIT for buy/sell, trigger for stops), NOT the "
    "actual execution price. For any correction chain you are reviewing: "
    "the chain head's operator_truth_value_json (when the chain head's "
    "resolution is 'operator_overridden') is the AUTHORITATIVE truth; "
    "intermediate \"Schwab said\" values from V1-era rows may reflect "
    "order-grain limits. From the V2 widening's ship forward, "
    "schwab_said_value_json carries EXECUTION-grain prices via the new "
    "SchwabExecutionLeg dataclass."
)


@discrepancy_group.command(
    "show-correction",
    epilog=_HISTORICAL_CORRECTION_NOTE,
    # Prevent Click from word-wrapping the long spec path inside the epilog
    # at terminal-width-80 (which would break the path on a hyphen and
    # defeat substring searches in operator-actionable tooling). Per
    # plan §A.1.12 acceptance test 4 spec-path verbatim citation lock.
    context_settings={"max_content_width": 200},
)
@click.argument("correction_id", type=int)
@click.pass_context
def discrepancy_show_correction_cmd(ctx, correction_id):
    """Print full detail for a single reconciliation_corrections row.

    Sub-bundle 1 T-1.12 per spec §8.3 OQ-G + plan §A.1.12. Renders the
    audit-history row (~17 columns) analogous to ``discrepancy show`` —
    operator inspects which discrepancy was corrected, what the V1-era
    Schwab-said value was, what the applied correction wrote, and (for
    operator_overridden chains) what the operator-truth value is.

    See the --help epilog for the generic V1 historical-context addendum
    (ORDER-grain vs EXECUTION-grain price provenance for pre-Sub-bundle-1
    correction chains).
    """
    from swing.data.db import connect
    from swing.data.repos.reconciliation_corrections import get_correction

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        c = get_correction(conn, correction_id)
    finally:
        conn.close()
    if c is None:
        raise click.ClickException(f"correction {correction_id} not found")
    # Render correction detail per migration 0019 + dataclass at
    # swing/data/models.py:ReconciliationCorrection field order.
    click.echo(f"correction_id:            {c.correction_id}")
    click.echo(f"discrepancy_id:           {c.discrepancy_id}")
    click.echo(f"correction_action:        {c.correction_action}")
    click.echo(f"correction_choice:        {c.correction_choice}")
    click.echo(f"affected_table:           {c.affected_table}")
    click.echo(f"affected_row_id:          {c.affected_row_id}")
    click.echo(f"field_name:               {c.field_name}")
    click.echo(f"pre_correction_value:     {c.pre_correction_value_json}")
    click.echo(f"source_canonical_value:   {c.source_canonical_value_json}")
    click.echo(f"applied_value:            {c.applied_value_json}")
    click.echo(f"operator_truth_value:     {c.operator_truth_value_json}")
    click.echo(f"applied_at:               {c.applied_at}")
    click.echo(f"applied_by:               {c.applied_by}")
    click.echo(f"correction_set_id:        {c.correction_set_id}")
    click.echo(f"superseded_by_correction: {c.superseded_by_correction_id}")
    click.echo(f"risk_policy_id:           {c.risk_policy_id_at_correction}")
    click.echo(f"schwab_api_call_id:       {c.schwab_api_call_id}")
    click.echo(f"reconciliation_run_id:    {c.reconciliation_run_id}")
    click.echo(f"correction_reason:        {c.correction_reason}")
    click.echo(f"notes:                    {c.notes}")


@discrepancy_group.command(
    "override-correction",
    epilog=_HISTORICAL_CORRECTION_NOTE,
    context_settings={"max_content_width": 200},  # Sub-bundle 1 T-1.12 spec-path verbatim lock
)
@click.argument("correction_id", type=int)
@click.option(
    "--truth-value", "truth_value", required=True,
    help=(
        "JSON payload of operator-truth field values for the override. "
        "Parsed via json.loads; deeper shape + finiteness validation "
        "happens at the service layer (validator chain re-run on "
        "operator-truth BEFORE any mutation, per spec §5.7 Codex R1 "
        "Minor #1 reorder). Example: '{\"price\": 5.25}'."
    ),
)
@click.option(
    "--reason", "reason", required=True,
    help=(
        "Operator-supplied free-text rationale (REQUIRED per spec §6.4 "
        "mandatory). Persisted on the new reconciliation_corrections row "
        "as `correction_reason`."
    ),
)
@click.option(
    "--force", "force", is_flag=True, default=False,
    help=(
        "Bypass the interactive confirmation prompt (non-interactive "
        "mode; per plan §E.4 acceptance criterion #4)."
    ),
)
@click.pass_context
def discrepancy_override_correction_cmd(
    ctx, correction_id, truth_value, reason, force,
):
    """Operator-override a prior tier-1 / tier-2 correction (spec §5.7).

    Inserts a NEW ``reconciliation_corrections`` row with action
    ``operator_overridden`` + ``operator_truth_value_json`` populated;
    stamps the prior row's ``superseded_by_correction_id`` to chain the
    audit history; UPDATEs the journal column to the operator-truth
    value; flips the discrepancy resolution to ``operator_overridden``.

    Confirmation prompt is shown by default. Use ``--force`` for
    non-interactive automation. ``AlreadySupersededError`` is mapped to
    a friendly CLI error naming the current chain-head correction_id so
    the operator knows where to retarget.
    """
    import json as _json

    from swing.data.db import connect
    from swing.data.repos.reconciliation_corrections import (
        get_correction,
        list_corrections_by_discrepancy,
    )
    from swing.trades.reconciliation_auto_correct import (
        AlreadySupersededError,
        CallerHeldTransactionError,
        ValidatorRejectedError,
        apply_tier3_override,
    )
    from swing.trades.risk_policy import read_active_policy

    # Parse --truth-value as JSON BEFORE opening the DB (cheap rejection
    # of malformed payloads; exit 2 via UsageError). Per plan §E.4
    # acceptance criterion #6 error mapping.
    try:
        parsed_truth = _json.loads(truth_value)
    except _json.JSONDecodeError as e:
        raise click.UsageError(
            f"--truth-value is not valid JSON: {e}; expected a JSON "
            "object like '{\"price\": X.XX}'"
        ) from None
    if not isinstance(parsed_truth, dict):
        raise click.UsageError(
            f"--truth-value must be a JSON object (got "
            f"{type(parsed_truth).__name__}); expected shape like "
            "'{\"price\": X.XX}'"
        )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        # Surface the current correction row before prompting so the
        # operator sees what they're overriding (per plan §E.4 acceptance
        # criterion #3).
        target = get_correction(conn, correction_id)
        if target is None:
            raise click.UsageError(
                f"correction {correction_id} not found in "
                "reconciliation_corrections"
            )

        # Compute the chain head for friendly guidance — walk the
        # superseded_by_correction_id chain from the supplied id forward
        # via `list_corrections_by_discrepancy` (deterministic
        # applied_at ASC, correction_id ASC ordering).
        #
        # Codex R1 Minor #2 fix — defensive multi-chain-head detection.
        # Invariant: exactly ONE row per discrepancy carries
        # ``superseded_by_correction_id IS NULL`` (the chain head); the
        # service-layer ``apply_tier3_override`` enforces this via the
        # 2-step UPDATE-then-INSERT pattern. If the audit history is
        # corrupted (e.g., manual SQL surgery, schema-rollback artifact,
        # cycle from a future-rev override pattern), multiple chain heads
        # may exist. Pick the HIGHEST correction_id (deterministic
        # tiebreaker; matches the most-recent-row heuristic the service
        # layer would attempt on insert) and surface a clear advisory to
        # the operator so they can audit the corrupt state independently.
        sibling_rows = list_corrections_by_discrepancy(
            conn, target.discrepancy_id,
        )
        chain_heads = [
            r for r in sibling_rows
            if r.superseded_by_correction_id is None
        ]
        chain_head_id: int | None = None
        if len(chain_heads) > 1:
            # Sort by correction_id DESC + pick the highest.
            chain_heads.sort(
                key=lambda r: r.correction_id, reverse=True,
            )
            chain_head_id = chain_heads[0].correction_id
            head_ids = [r.correction_id for r in chain_heads]
            click.echo(
                f"WARNING: discrepancy {target.discrepancy_id} has "
                f"MULTIPLE chain heads (correction_ids={head_ids}); "
                f"this indicates corrupted audit-chain state (expected "
                f"exactly one row with superseded_by_correction_id "
                f"IS NULL). Picking the highest correction_id "
                f"({chain_head_id}) as the deterministic chain head; "
                f"audit the corrupt state via `swing journal "
                f"discrepancy show {target.discrepancy_id}` before "
                f"proceeding with the override.",
                err=True,
            )
        elif len(chain_heads) == 1:
            chain_head_id = chain_heads[0].correction_id

        if not force:
            click.echo(
                f"current correction_id={target.correction_id} "
                f"action={target.correction_action} "
                f"affected_table={target.affected_table} "
                f"field={target.field_name} "
                f"applied_value={target.applied_value_json} "
                f"schwab_said={target.source_canonical_value_json}"
            )
            click.echo(f"proposed override: {parsed_truth!r}")
            if chain_head_id == target.correction_id:
                click.echo(
                    f"this correction (id={target.correction_id}) IS "
                    "the current chain head."
                )
            else:
                click.echo(
                    f"chain head: correction_id={chain_head_id} "
                    "(supplied id is mid-chain; override will still be "
                    "rejected by the service layer with "
                    "AlreadySupersededError)."
                )
            answer = click.prompt(
                "Override this correction? [y/N]",
                default="N",
                show_default=False,
            )
            if not answer or not answer.strip().lower().startswith("y"):
                click.echo("(aborted)")
                return

        # Resolve active risk policy id (Phase 9 Sub-bundle A surface)
        # for the audit-row stamp.
        active_policy = read_active_policy(conn)

        try:
            result = apply_tier3_override(
                conn,
                correction_id=correction_id,
                operator_truth_value=parsed_truth,
                operator_reason=reason,
                risk_policy_id=active_policy.policy_id,
            )
        except CallerHeldTransactionError as e:
            raise click.ClickException(
                f"transactional discipline violation: {e}"
            ) from None
        except AlreadySupersededError:
            # Friendly message naming the chain-head correction_id per
            # OQ-15 + plan §E.4 acceptance criterion #6 (exit 2). Use
            # the chain head we computed above (more reliable than
            # parsing the service-layer exception text). UsageError
            # exits 2 vs ClickException's 1 — operator-misuse semantics
            # match the "you targeted the wrong row" failure mode.
            head_text = (
                str(chain_head_id) if chain_head_id is not None
                else "unknown"
            )
            raise click.UsageError(
                f"correction {correction_id} is already superseded by "
                f"correction {head_text}; override the chain head "
                f"({head_text}) instead"
            ) from None
        except ValidatorRejectedError as e:
            raise click.ClickException(
                f"validator rejected the operator-truth value: {e}"
            ) from None
        except ValueError as e:
            # Service-layer ValueError covers per-shape rejection /
            # missing fields. Map to UsageError (exit 2) per plan §E.4
            # acceptance criterion #6.
            raise click.UsageError(str(e)) from None
    finally:
        conn.close()

    click.echo(
        f"override applied: prior correction_id={correction_id}; "
        f"new correction_id={result.correction_id}"
    )


@discrepancy_group.command("resolve")
@click.argument("discrepancy_id", type=int)
@click.option(
    "--resolution",
    type=click.Choice([
        "journal_corrected", "source_treated_canonical",
        "manual_override", "acknowledged_immaterial",
    ]),
    required=True,
)
@click.option(
    "--reason", default=None,
    help="Required for journal_corrected / source_treated_canonical / "
         "manual_override; optional for acknowledged_immaterial.",
)
@click.option(
    "--material", type=click.IntRange(0, 1), default=None,
    help="Optional override of material_to_review (0 or 1).",
)
@click.option(
    "--mistake-tag", default=None,
    help="Optional mistake_tag from review.py vocabulary.",
)
@click.pass_context
def discrepancy_resolve_cmd(
    ctx, discrepancy_id, resolution, reason, material, mistake_tag,
):
    """Resolve a discrepancy with an operator-supplied resolution + reason."""
    from swing.data.db import connect
    from swing.trades.reconciliation import resolve_discrepancy

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            resolve_discrepancy(
                conn,
                discrepancy_id=discrepancy_id,
                resolution=resolution,
                resolution_reason=reason,
                mistake_tag_assigned=mistake_tag,
                material_to_review=material,
            )
        except ValueError as e:
            raise click.ClickException(str(e)) from None
    finally:
        conn.close()
    click.echo(
        f"Discrepancy {discrepancy_id} resolved: resolution={resolution}"
    )


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

    Allowed transitions per brief §4.6 + plan §A.1 + spec §3.4.1:
      active   -> paused | closed-escaped | closed-target-met
      paused   -> active | closed-escaped
      closed-escaped -> active
      closed-target-met -> (terminal — no reopen via CLI)

    Phase 9 Sub-bundle C T-C.4: this handler routes through the new
    service helper ``swing/trades/hypothesis.py:update_hypothesis_status_with_audit``
    which (a) appends a hypothesis_status_history audit row in the same
    transaction as the registry UPDATE, (b) treats identity transitions
    (current == new) as NoOpIdentityTransition (INFO, not ERROR) per spec
    §3.4.1 R3 Minor #1.
    """
    from swing.data.db import connect
    from swing.trades.hypothesis import (
        HypothesisStatusTransitionError,
        update_hypothesis_status_with_audit,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = update_hypothesis_status_with_audit(
                conn,
                hypothesis_id=hypothesis_id,
                new_status=new_status,
                change_reason=reason,
            )
        except HypothesisStatusTransitionError as exc:
            raise click.ClickException(f"transition not allowed: {exc}") from exc
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    if result == "noop_identity":
        click.echo(
            f"info: hypothesis #{hypothesis_id} already {new_status}; "
            "no change made"
        )
    else:
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


@main.group("account")
def account_group() -> None:
    """Account-level operator surfaces (V1: equity snapshots only).

    Phase 9 Sub-bundle C T-C.2. Spec §3.5 + §4.4 V1 cadence: operator
    records account net-liquidation snapshots manually (CLI). V2 surfaces
    Schwab API + TOS-CSV co-emission of snapshots with `source` enum
    values reserved at the schema.
    """


@account_group.command("snapshot")
@click.option(
    "--equity", "equity_dollars", type=float, required=True,
    help="Account net-liquidation value (REAL, > 0).",
)
@click.option(
    "--date", "snapshot_date_str", default=None,
    help="Snapshot date YYYY-MM-DD; defaults to last completed NYSE "
         "session per spec §4.4 + §A.9.",
)
@click.option(
    "--notes", default=None,
    help="Optional operator free-text note.",
)
@click.pass_context
def account_snapshot_cmd(
    ctx: click.Context,
    equity_dollars: float,
    snapshot_date_str: str | None,
    notes: str | None,
) -> None:
    """Record an account equity snapshot (source=manual).

    UPSERT semantics keyed on (snapshot_date, source=manual): re-recording
    for the same date updates the row in place (PK preserved). For
    snapshot_dates >7 days in the past relative to today, the CLI prints
    an advisory note + sets the back-recorded flag at read-time (per
    spec §3.5 GAP-FLAGGED policy).
    """
    from datetime import date as _date

    from swing.data.db import connect
    from swing.trades.account_equity_snapshots import (
        is_back_recorded,
        record_snapshot,
    )

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        try:
            snap = record_snapshot(
                conn,
                equity_dollars=equity_dollars,
                snapshot_date=snapshot_date_str,
                notes=notes,
            )
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    click.echo(
        f"snapshot #{snap.snapshot_id}: {snap.snapshot_date}  "
        f"${snap.equity_dollars:.2f}  source={snap.source}"
    )
    back = is_back_recorded(
        snapshot_date=snap.snapshot_date,
        recorded_at=snap.recorded_at,
    )
    today = _date.today().isoformat()
    if back:
        click.echo(
            f"  (back-recorded: snapshot_date {snap.snapshot_date} is "
            f">7 days before today {today})"
        )


# ============================================================================
# Phase 13 T2.SB1 — `swing patterns` group (T-A.1.5)
#
# `swing patterns label-exemplars` dispatches the pattern-labeler subagent
# for one (window, pattern_class) seed tuple per spec §5.9 step 1. V1 is
# operator-paired per OQ-6: WITHOUT --silver-response-file the CLI emits
# the dispatch payload + guidance; WITH --silver-response-file the CLI
# persists the parsed response as a silver-tier exemplar.
#
# Pattern-class choice constrained to DETECTOR_PATTERN_CLASSES via
# explicit validation (per plan §G.1 T-A.1.5 Step 2). ASCII-only output
# per §A.8 + CLAUDE.md Windows cp1252 stdout gotcha.
# ============================================================================


@main.group("patterns")
def patterns_group() -> None:
    """Phase 13 Theme 2 — pattern labeling + closed-loop review surfaces."""


_LABELING_BAR_REQUIRED_KEYS = frozenset(
    ("date", "open", "high", "low", "close", "volume")
)


def _load_bars_for_labeling_emit(
    *,
    window_bars_file: str | None,
    ticker: str,
    start_date: str,
    end_date: str,
    timeframe: str,
) -> list[dict[str, object]]:
    """Resolve the emit-payload bars list.

    Codex R1 M#1 + M#2 + M#6 closure:
      - operator override via --window-bars-file takes precedence + is
        shape-validated (list of dicts with the canonical OHLCV keys);
      - otherwise yfinance windowed auto-fetch via labeling_bars helper;
      - empty yfinance response raises a ClickException with operator
        guidance pointing at --window-bars-file (V1: silently emitting
        bars=[] would hand an unusable dispatch payload to the subagent).
    """
    import json as _json
    from pathlib import Path as _Path

    from swing.patterns.labeling_bars import (
        autofetch_bars_for_labeling as _autofetch,
    )

    if window_bars_file is not None:
        # Codex R2 Minor #2 closure: catch malformed JSON at the file
        # boundary so the operator sees a clean ClickException instead of
        # a raw json.JSONDecodeError traceback.
        try:
            raw = _json.loads(
                _Path(window_bars_file).read_text(encoding="utf-8")
            )
        except _json.JSONDecodeError as exc:
            raise click.ClickException(
                f"--window-bars-file content is not valid JSON: {exc}."
            ) from exc
        if not isinstance(raw, list):
            raise click.ClickException(
                "--window-bars-file content must be a JSON array of bar "
                f"objects; got top-level {type(raw).__name__}."
            )
        for idx, bar in enumerate(raw):
            if not isinstance(bar, dict):
                raise click.ClickException(
                    f"--window-bars-file bar #{idx} is "
                    f"{type(bar).__name__}; expected a JSON object with "
                    "keys date/open/high/low/close/volume."
                )
            missing = _LABELING_BAR_REQUIRED_KEYS - set(bar.keys())
            if missing:
                raise click.ClickException(
                    f"--window-bars-file bar #{idx} missing required "
                    f"OHLCV keys: {sorted(missing)}."
                )
        return raw

    bars = _autofetch(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )
    if not bars:
        raise click.ClickException(
            "yfinance auto-fetch returned no bars for "
            f"{ticker} {start_date}..{end_date} (timeframe={timeframe}). "
            "Possible causes: delisted ticker, transient empty upstream, "
            "rate-limit, or invalid window. Re-run with "
            "--window-bars-file <path> to supply pre-built bars."
        )
    return bars


@patterns_group.command("label-exemplars")
@click.option("--ticker", required=True, type=str)
@click.option(
    "--start", "start_date", required=True, type=str,
    help="ISO date YYYY-MM-DD; window left edge.",
)
@click.option(
    "--end", "end_date", required=True, type=str,
    help="ISO date YYYY-MM-DD; window right edge.",
)
@click.option(
    "--pattern-class", "pattern_class", required=True, type=str,
    help="Detector class (one of: vcp, flat_base, cup_with_handle, "
         "high_tight_flag, double_bottom_w).",
)
@click.option(
    "--timeframe", "timeframe", default="daily",
    type=click.Choice(("daily", "weekly")),
    show_default=True,
)
@click.option(
    "--ai-labeler-version", "ai_labeler_version",
    default="claude-code-pattern-labeler-v1", type=str,
    show_default=True,
)
@click.option(
    "--silver-response-file", "silver_response_file",
    type=click.Path(exists=True, dir_okay=False), default=None,
    help="Path to JSON file with the pattern-labeler subagent's response. "
         "When provided, the CLI persists the parsed response to "
         "pattern_exemplars. When omitted, the CLI emits the dispatch "
         "payload to stdout (operator-paired workflow per OQ-6).",
)
@click.option(
    "--window-bars-file", "window_bars_file",
    type=click.Path(exists=True, dir_okay=False), default=None,
    help="Optional path to JSON file with the window's OHLCV bars "
         "(list of dicts with keys date / open / high / low / close / "
         "volume). Consumed ONLY on the emit-payload path (i.e. when "
         "--silver-response-file is NOT set). When supplied on that "
         "path, the override pins the bars (fixture-pinned "
         "reproducibility) and yfinance is NOT called; when omitted on "
         "that path, the CLI auto-fetches daily bars via yfinance for "
         "the requested (ticker, start, end). The persist path "
         "(--silver-response-file) does not consume bars; if you pass "
         "--window-bars-file together with --silver-response-file, the "
         "file is only checked for existence by click and otherwise "
         "ignored.",
)
@click.pass_context
def label_exemplars_cmd(
    ctx: click.Context,
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    pattern_class: str,
    timeframe: str,
    ai_labeler_version: str,
    silver_response_file: str | None,
    window_bars_file: str | None,
) -> None:
    """Dispatch the pattern-labeler subagent for one (window, pattern_class).

    V1 operator-paired workflow (per OQ-6 + spec section 5.9 step 1):

    \b
    Step A (emit payload):
      swing patterns label-exemplars --ticker ABC --start 2024-01-01 \\
          --end 2024-02-01 --pattern-class vcp
      => writes dispatch payload JSON to stdout for operator handoff.

    \b
    Step B (operator dispatches in Claude Code session, captures response):
      Inside a paired Claude Code session, the operator invokes the
      pattern-labeler subagent with the payload + saves the response to a
      JSON file (e.g. silver.json).

    \b
    Step C (persist):
      swing patterns label-exemplars --ticker ABC --start 2024-01-01 \\
          --end 2024-02-01 --pattern-class vcp \\
          --silver-response-file silver.json
      => parses silver.json + persists one row to pattern_exemplars with
         label_source=claude_silver.
    """
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from swing.data.db import connect as _connect
    from swing.data.models import DETECTOR_PATTERN_CLASSES as _DPC
    from swing.patterns.labeling import (
        SilverLabelResponse as _SilverLabelResponse,
    )
    from swing.patterns.labeling import (
        fire_claude_silver_label as _fire_claude_silver_label,
    )
    from swing.patterns.spec_static import (
        get_rule_criteria as _get_rule_criteria,
    )
    from swing.patterns.spec_static import (
        get_structural_evidence_schema as _get_evidence_schema,
    )

    if pattern_class not in _DPC:
        raise click.BadParameter(
            f"pattern-class must be one of {list(_DPC)}, got "
            f"{pattern_class!r}",
            param_hint="--pattern-class",
        )

    # T-A.1.5b Defect 2: inline spec section 5.2 through 5.6 rule_criteria
    # + structural_evidence_schema for the requested pattern_class. Static
    # source-of-truth at swing/patterns/spec_static.py (V1 PATCH scope
    # only; T2.SB3+/SB4 detectors MAY rebase onto compute-derived defaults
    # when they land).
    rule_criteria: dict = _get_rule_criteria(pattern_class)
    structural_evidence_schema: dict = _get_evidence_schema(pattern_class)

    # T-A.1.5b Defect 3 (Option B) + Codex R1 M#1 fix: bars auto-fetched
    # ONLY in emit-payload mode. The persist-mode (--silver-response-file)
    # branch does not need bars - the subagent has already labeled - and
    # auto-fetching there would leak an unmocked yfinance call into the
    # persist path (which can fail offline and pollute the test surface).
    if silver_response_file is None:
        bars = _load_bars_for_labeling_emit(
            window_bars_file=window_bars_file,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )
        window_payload = {
            "ticker": ticker,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "bars": bars,
        }
        payload = {
            "window_payload": window_payload,
            "pattern_class": pattern_class,
            "rule_criteria": rule_criteria,
            "structural_evidence_schema": structural_evidence_schema,
            "ai_labeler_version": ai_labeler_version,
        }
        click.echo(_json.dumps(payload, sort_keys=True, indent=2))
        return

    # With --silver-response-file: parse + persist. No bars needed - the
    # subagent has already labeled the window; the persist path stores
    # ONLY the label rows in pattern_exemplars.
    window_payload = {
        "ticker": ticker,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "bars": [],
    }

    # Codex R3 Minor #1 closure: malformed JSON in --silver-response-file
    # now surfaces as a clean ClickException (matches the --window-bars-file
    # treatment under Codex R2 Minor #2).
    try:
        response_raw = _json.loads(
            Path(silver_response_file).read_text(encoding="utf-8")
        )
    except _json.JSONDecodeError as exc:
        raise click.ClickException(
            f"--silver-response-file content is not valid JSON: {exc}."
        ) from exc
    # Codex R4 Minor #1 closure: top-level JSON must be an object (dict).
    # A top-level JSON string / array / scalar would otherwise raise raw
    # TypeError on the response_raw["structural_evidence_json"] indexing
    # below, escaping the clean shape-invalid path.
    if not isinstance(response_raw, dict):
        raise click.ClickException(
            "silver-response-file shape invalid: top-level JSON must be "
            f"an object (dict); got {type(response_raw).__name__}."
        )
    # T-A.1.5b Defect 1 + Codex R1 M#3 fix — dict-or-str coercion at
    # structural_evidence_json with JSON-object validation when the input
    # is already a string.
    #
    # The pattern-labeler subagent's documented output contract emits this
    # field as a JSON OBJECT (dict); _SilverLabelResponse stores it as a
    # serialized JSON string for direct sqlite3 binding. Accept both shapes
    # (dict from real subagent + pre-serialized JSON dict string from
    # existing test fixtures); reject anything else with a clear error.
    # Codex R2 M#1 closure: explicit key-presence check so a missing
    # structural_evidence_json key surfaces as a clean shape-invalid error
    # rather than escaping through _SilverLabelResponse.__post_init__'s
    # ValueError (which the except clause widening below ALSO catches as
    # defense-in-depth).
    if "structural_evidence_json" not in response_raw:
        raise click.ClickException(
            "silver-response-file shape invalid: missing required key "
            "'structural_evidence_json' per .claude/agents/"
            "pattern-labeler.md output contract."
        )
    raw_evidence = response_raw["structural_evidence_json"]
    if isinstance(raw_evidence, dict):
        raw_evidence = _json.dumps(raw_evidence, sort_keys=True)
    elif isinstance(raw_evidence, str):
        # Verify the string parses as a JSON OBJECT (not a top-level
        # array / scalar / malformed JSON). Codex R1 M#3 closure: bad
        # strings must NOT silently persist as garbage that fails
        # downstream as a vague DB error.
        try:
            decoded = _json.loads(raw_evidence)
        except _json.JSONDecodeError as exc:
            raise click.ClickException(
                "silver-response-file shape invalid: "
                "structural_evidence_json string is not valid JSON: "
                f"{exc}."
            ) from exc
        if not isinstance(decoded, dict):
            raise click.ClickException(
                "silver-response-file shape invalid: "
                "structural_evidence_json string must decode to a JSON "
                "object (dict); got "
                f"{type(decoded).__name__}."
            )
        # Re-serialize canonically (sort_keys) for byte-stable persistence.
        raw_evidence = _json.dumps(decoded, sort_keys=True)
    elif raw_evidence is not None:
        raise click.ClickException(
            "silver-response-file shape invalid: "
            "structural_evidence_json must be a JSON object (per the "
            ".claude/agents/pattern-labeler.md contract) OR a pre-serialized "
            f"JSON object string; got {type(raw_evidence).__name__}."
        )
    try:
        response = _SilverLabelResponse(
            evaluation=response_raw["evaluation"],
            confidence=response_raw["confidence"],
            structural_evidence_json=raw_evidence,
            geometric_evidence_narrative=(
                response_raw["geometric_evidence_narrative"]
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        # Codex R2 M#1 closure: ValueError added so __post_init__
        # validation failures surface as ClickException (vs raw traceback).
        raise click.ClickException(
            f"silver-response-file shape invalid: {exc}; expected keys "
            "'evaluation', 'confidence', 'structural_evidence_json', "
            "'geometric_evidence_narrative' per .claude/agents/"
            "pattern-labeler.md output contract."
        ) from exc

    cfg = ctx.obj["config"]
    conn = _connect(cfg.paths.db_path)

    def _dispatch_from_file(**_kwargs: object) -> _SilverLabelResponse:
        return response

    try:
        try:
            exemplar_id = _fire_claude_silver_label(
                conn,
                ticker=ticker,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                pattern_class=pattern_class,
                window_payload=window_payload,
                rule_criteria=rule_criteria,
                structural_evidence_schema=structural_evidence_schema,
                ai_labeler_version=ai_labeler_version,
                dispatch_subagent=_dispatch_from_file,
                now_fn=lambda: _datetime.now(_UTC).isoformat(),
            )
        except ValueError as exc:
            # Codex R4 M#1 closure: service-layer ValueErrors (most notably
            # _map_silver_evaluation_to_decision rejecting
            # `relabel:<same_class_as_proposed>` per spec section 3.1
            # invariant #1) surface as a clean shape-invalid ClickException
            # rather than a raw traceback. The dataclass __post_init__
            # cannot detect the same-class collision because it doesn't
            # know the proposed pattern_class context; the service layer
            # owns that check.
            raise click.ClickException(
                "silver-response-file shape invalid: "
                f"{exc}"
            ) from exc
    finally:
        conn.close()

    click.echo(
        f"silver exemplar persisted: id={exemplar_id} ticker={ticker} "
        f"pattern_class={pattern_class} final_decision="
        f"{response.evaluation}"
    )


# ============================================================================
# Phase 13 T-T4.SB.4 Sub-task 4E (OQ-2.2 LOCK) — `swing patterns
# label-corpus-all` operator-paired bulk relabel emit-mode CLI.
#
# OQ-2.2 disposition: ship the corpus-all path as operator-paired V1.
# Production labeling is operator-paired by design (no in-process Agent
# tool callable from Python; LabelingDispatchError gates the
# subagent-callable kwarg). The CLI therefore EMITS one dispatch payload
# per claude_silver row to stdout as JSONL (one line per row) so the
# operator can iterate in a paired session + persist each response via
# the existing `label-exemplars --silver-response-file` path.
#
# Scope per spec section 5.9 step 5 + V1 simplification:
#   - Includes ONLY `label_source IN ('claude_silver', 'codex_silver')`
#     rows: gold rows are operator-validated + MUST NOT be relabeled;
#     other tiers (synthetic / perturbation / closed_loop / organic)
#     are out of the silver-tier review scope.
#   - Bars are NOT auto-fetched (would blast yfinance with N requests
#     + breach the OhlcvCache sliding-window breaker for any sizable
#     corpus). The emit payload includes `bars: []`; the operator's
#     paired session re-runs `label-exemplars --window-bars-file`
#     per row OR consults the original corpus dump bars.
#   - CTRL-C safe (no DB writes from the emit path).
#
# V1 simplification (banked in return report): no per-row persist
# subcommand. The operator iterates `label-exemplars --silver-response-file`
# per response file. V2 candidates: `--silver-response-dir <dir>` bulk
# persist; `--bars-cache-dir <dir>` reuse cached bars per row.
#
# ASCII-only output per CLAUDE.md Windows cp1252 stdout gotcha.
# ============================================================================


@patterns_group.command("label-corpus-all")
@click.option(
    "--ai-labeler-version", "ai_labeler_version",
    default="claude-code-pattern-labeler-v1", type=str,
    show_default=True,
    help="Stamped on subsequent persist invocations (operator passes "
         "via --ai-labeler-version on label-exemplars per row).",
)
@click.option(
    "--limit", "limit", type=int, default=None,
    help="Optional cap on the number of corpus rows to emit "
         "(operator-paired iteration convenience).",
)
@click.pass_context
def label_corpus_all_cmd(
    ctx: click.Context,
    *,
    ai_labeler_version: str,
    limit: int | None,
) -> None:
    """Emit per-exemplar dispatch payloads for operator-paired bulk relabel.

    \b
    OQ-2.2 LOCK — operator-paired bulk relabel for the silver corpus.

    \b
    Iterates `pattern_exemplars` rows where
    `label_source IN ('claude_silver', 'codex_silver')`, emits one
    JSON dispatch payload per row to stdout (JSONL), and exits 0.
    Bars are NOT auto-fetched; the operator's paired Claude Code
    session re-runs `label-exemplars --silver-response-file <path>`
    per-row to persist each response.

    \b
    V1 simplification (return-report-banked): emit-only — no
    per-row persist subcommand. CTRL-C is safe (no DB writes).
    """
    import json as _json

    from swing.data.db import connect as _connect
    from swing.data.repos import pattern_exemplars as _ex_repo
    from swing.patterns.spec_static import (
        get_rule_criteria as _get_rule_criteria,
    )
    from swing.patterns.spec_static import (
        get_structural_evidence_schema as _get_evidence_schema,
    )

    cfg = ctx.obj["config"]
    conn = _connect(cfg.paths.db_path)
    try:
        # Iterate claude_silver + codex_silver rows in deterministic id
        # order; gold + other tiers are out of scope (gold is
        # operator-validated + relabeling it would clobber the audit
        # trail; other tiers carry non-silver semantics).
        try:
            silver_rows = _ex_repo.list_exemplars(
                conn, label_source="claude_silver",
            )
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(
                f"failed to enumerate claude_silver corpus rows: {exc}"
            ) from exc
        codex_rows = _ex_repo.list_exemplars(
            conn, label_source="codex_silver",
        )
        all_rows = sorted(
            list(silver_rows) + list(codex_rows),
            key=lambda r: (r.id if r.id is not None else 0),
        )
        if limit is not None and limit >= 0:
            all_rows = all_rows[:limit]

        if not all_rows:
            click.echo(
                "no silver-tier exemplars found in corpus "
                "(label_source IN claude_silver | codex_silver). "
                "Run `swing patterns label-exemplars` first to "
                "bootstrap the silver corpus."
            )
            return

        emitted = 0
        for row in all_rows:
            try:
                rule_criteria = _get_rule_criteria(
                    row.proposed_pattern_class,
                )
                structural_evidence_schema = _get_evidence_schema(
                    row.proposed_pattern_class,
                )
            except (KeyError, ValueError) as exc:
                # Service-layer ValueError wrap at CLI boundary
                # (CLAUDE.md gotcha): surface as a clean per-row
                # warning + continue (CTRL-C-safe; no partial writes).
                click.echo(
                    f"# skip row id={row.id} ticker={row.ticker} "
                    f"pattern_class={row.proposed_pattern_class}: "
                    f"spec_static lookup failed: {exc}",
                    err=True,
                )
                continue

            window_payload = {
                "ticker": row.ticker,
                "timeframe": row.timeframe,
                "start_date": row.start_date,
                "end_date": row.end_date,
                # bars=[] per emit-mode contract; operator runs the
                # label-exemplars per-row persist path with
                # --window-bars-file OR auto-fetched bars.
                "bars": [],
            }
            payload = {
                "exemplar_id": row.id,
                "ticker": row.ticker,
                "pattern_class": row.proposed_pattern_class,
                "window_payload": window_payload,
                "rule_criteria": rule_criteria,
                "structural_evidence_schema": structural_evidence_schema,
                "ai_labeler_version": ai_labeler_version,
            }
            # JSONL: one compact JSON object per line (operator-friendly
            # `head -n 1 | jq` workflow).
            click.echo(_json.dumps(payload, sort_keys=True))
            emitted += 1

        click.echo(
            f"# emitted {emitted} dispatch payload(s) for "
            f"operator-paired relabel. Iterate via the paired Claude "
            "Code session + persist each response with "
            "`swing patterns label-exemplars --silver-response-file "
            "<response.json> --ticker <ticker> --start <start> "
            "--end <end> --pattern-class <class>`.",
            err=True,
        )
    finally:
        conn.close()


# ============================================================================
# T-A.1.8 — `swing patterns review-silver-with-codex` CLI subcommand
#
# Per closer dispatch brief T-1.8.1 + spec section 5.9 step 4 + OQ-5 phased
# rollout: random-15% Codex 2nd-reviewer dispatch wiring for the V1 phase
# (HARD-CODED phase='t2_sb1' per L9 LOCK — NO high-stakes disagreement
# clause activation; T2.SB3+/SB4 retroactively enables that path).
#
# Operator-paired V1 workflow (mirrors `label-exemplars` shape per OQ-6):
#   Step A (emit/sample):
#     swing patterns review-silver-with-codex --exemplar-id 5 --seed 42
#       => emits dispatch payload JSON if random-15% sample fires;
#          emits skip-note + exit 0 if sample does NOT fire.
#   Step B (operator dispatches Codex via paired session; saves response).
#   Step C (persist):
#     swing patterns review-silver-with-codex --exemplar-id 5 \
#         --codex-response-file codex.json
#       => bypasses policy gate (operator's response collection IS the
#          dispatch decision) via forced-fire rng so the existing
#          service-layer fire_codex_review_for_silver_row is exercised
#          end-to-end (per T-1.8.1 acceptance criterion #1).
#
# ASCII-only output per CLAUDE.md Windows cp1252 stdout gotcha.
# ============================================================================


@patterns_group.command("review-silver-with-codex")
@click.option(
    "--exemplar-id", "exemplar_id", required=True, type=int,
    help="pattern_exemplars.id of the claude_silver parent row to review.",
)
@click.option(
    "--seed", "seed", type=int, default=None,
    help="Optional integer seed for the random-15% sampling RNG. When "
         "omitted in emit mode, the sampling uses an unseeded random.Random "
         "(production); when supplied, the decision is deterministic "
         "(operator-paired pairing of emit + persist invocations). The "
         "persist path (--codex-response-file) IGNORES --seed because the "
         "operator's response collection IS the dispatch decision.",
)
@click.option(
    "--codex-response-file", "codex_response_file",
    type=click.Path(exists=True, dir_okay=False), default=None,
    help="Path to JSON file with the Codex 2nd-reviewer response per the "
         "CodexReviewResponse contract (keys: agreed, alternative_evaluation, "
         "alternative_confidence, alternative_structural_evidence_json, "
         "alternative_labeler_evidence_json). When provided, the CLI parses "
         "the response + invokes fire_codex_review_for_silver_row with a "
         "forced-fire RNG (bypassing the random-15% sampling gate because "
         "the operator's response collection IS the dispatch decision). When "
         "omitted, the CLI emits the dispatch payload to stdout (emit mode).",
)
@click.option(
    "--ai-labeler-version", "ai_labeler_version",
    default="gpt-5-codex-dispatch", type=str, show_default=True,
)
@click.pass_context
def review_silver_with_codex_cmd(
    ctx: click.Context,
    *,
    exemplar_id: int,
    seed: int | None,
    codex_response_file: str | None,
    ai_labeler_version: str,
) -> None:
    """Dispatch + persist Codex 2nd-reviewer for one claude_silver exemplar.

    \b
    V1 phase HARD-CODES phase='t2_sb1' per L9 LOCK (random-15% sampling
    ONLY; high-stakes disagreement clause activates at T2.SB3+/SB4
    retroactively per spec section A.6 + OQ-5).

    \b
    Step A (emit/sample): no --codex-response-file => sample + maybe emit
    payload. Exit 0 either way (skip is not an error).

    \b
    Step C (persist): with --codex-response-file => parse + invoke
    fire_codex_review_for_silver_row; persist codex_silver row on
    disagreement; flip parent codex_reviewed + codex_agreement either way.
    """
    import json as _json
    import random as _random
    from pathlib import Path as _Path

    from swing.data.db import connect as _connect
    from swing.data.repos import pattern_exemplars as _exemplars_repo
    from swing.patterns.labeling import (
        CODEX_RANDOM_SAMPLE_PROBABILITY as _CODEX_PROB,
    )
    from swing.patterns.labeling import (
        CodexReviewResponse as _CodexReviewResponse,
    )
    from swing.patterns.labeling import (
        fire_codex_review_for_silver_row as _fire_codex,
    )
    from swing.patterns.labeling import (
        should_fire_codex as _should_fire,
    )
    from swing.patterns.spec_static import (
        get_rule_criteria as _get_rule_criteria,
    )
    from swing.patterns.spec_static import (
        get_structural_evidence_schema as _get_evidence_schema,
    )

    cfg = ctx.obj["config"]
    conn = _connect(cfg.paths.db_path)
    try:
        parent = _exemplars_repo.get_exemplar_by_id(conn, exemplar_id)
        if parent is None:
            raise click.ClickException(
                f"exemplar {exemplar_id} not found in pattern_exemplars."
            )
        # L9 LOCK + service-layer invariant: codex review fires ONLY on
        # claude_silver rows. The fire_codex_review_for_silver_row helper
        # itself rejects non-claude_silver inputs; we duplicate the check
        # here so the emit-mode path also short-circuits with a clean
        # ClickException + routing hint.
        if parent.label_source != "claude_silver":
            raise click.ClickException(
                f"exemplar {exemplar_id} has label_source="
                f"{parent.label_source!r}; Codex 2nd-review fires ONLY on "
                f"claude_silver rows. (curated_gold rows are operator-"
                f"validated terminal; codex_silver rows are themselves "
                f"disagreement-chain children and are not re-reviewed.)"
            )

        if codex_response_file is None:
            _emit_or_skip_payload(
                parent=parent,
                exemplar_id=exemplar_id,
                seed=seed,
                random_sample_probability=_CODEX_PROB,
                should_fire=_should_fire,
                get_rule_criteria=_get_rule_criteria,
                get_evidence_schema=_get_evidence_schema,
            )
            return

        # Persist mode: parse response + invoke fire_codex_review_for_silver_row.
        try:
            response_raw = _json.loads(
                _Path(codex_response_file).read_text(encoding="utf-8")
            )
        except _json.JSONDecodeError as exc:
            raise click.ClickException(
                f"--codex-response-file content is not valid JSON: {exc}."
            ) from exc
        if not isinstance(response_raw, dict):
            raise click.ClickException(
                "codex-response-file shape invalid: top-level JSON must be "
                f"an object (dict); got {type(response_raw).__name__}."
            )
        if "agreed" not in response_raw:
            raise click.ClickException(
                "codex-response-file shape invalid: missing required key "
                "'agreed' per CodexReviewResponse contract."
            )
        # Codex R1 Major #1 closure: strict bool validation at CLI
        # boundary. Loose `bool(response_raw["agreed"])` would silently
        # treat JSON like `{"agreed": "false"}` as True (because the
        # non-empty string "false" is truthy), recording a disagreement
        # as agreement + skipping the codex_silver row insertion. JSON
        # has a real bool type — reject anything else explicitly with a
        # routing-hint error. Defense-in-depth: __post_init__ in
        # CodexReviewResponse also runtime-validates per the same lesson
        # family (T-A.1.5b R3 M#1 Literal[...] not runtime-enforced).
        if not isinstance(response_raw["agreed"], bool):
            raise click.ClickException(
                "codex-response-file shape invalid: 'agreed' must be a "
                "JSON boolean (true/false); got "
                f"{type(response_raw['agreed']).__name__} "
                f"value={response_raw['agreed']!r}. Common mistake: "
                'quoting the value (e.g. {"agreed": "false"}) — drop '
                "the quotes."
            )
        try:
            codex_response = _CodexReviewResponse(
                agreed=response_raw["agreed"],
                alternative_evaluation=response_raw.get(
                    "alternative_evaluation",
                ),
                alternative_confidence=response_raw.get(
                    "alternative_confidence",
                ),
                alternative_structural_evidence_json=response_raw.get(
                    "alternative_structural_evidence_json",
                ),
                alternative_labeler_evidence_json=response_raw.get(
                    "alternative_labeler_evidence_json",
                ),
            )
        except (TypeError, ValueError) as exc:
            raise click.ClickException(
                f"codex-response-file shape invalid: {exc}"
            ) from exc

        def _dispatch_from_file(
            **_kwargs: object,
        ) -> _CodexReviewResponse:
            return codex_response

        # Forced-fire RNG: the operator's response collection IS the
        # dispatch decision; bypass the random-15% sampling gate at the
        # service layer by feeding a deterministic Random whose first
        # .random() draw is well below the threshold. This still exercises
        # should_fire_codex inside fire_codex_review_for_silver_row end-to-
        # end (T-1.8.1 acceptance criterion #1).
        #
        # Pre-computed: random.Random(1).random() == 0.13436424411240122,
        # comfortably below CODEX_RANDOM_SAMPLE_PROBABILITY (0.15) for the
        # T2.SB1 phase. The defensive invariant assertion guards against a
        # future CPython-stdlib Mersenne Twister regression that would
        # silently break the gate (Python promises stable PRNG output for
        # a given seed, but the assertion makes the regression LOUD).
        forced_rng = _random.Random(1)
        _probe_rng = _random.Random(1)
        _probe = _probe_rng.random()
        if _probe >= _CODEX_PROB:
            raise click.ClickException(
                "internal invariant violated: random.Random(1).random() = "
                f"{_probe:.6f} >= CODEX_RANDOM_SAMPLE_PROBABILITY = "
                f"{_CODEX_PROB:.6f}; PRNG-output regression in CPython "
                "stdlib. Persist path cannot guarantee should_fire_codex "
                "fire decision; halting."
            )

        try:
            codex_id = _fire_codex(
                conn,
                exemplar_id=exemplar_id,
                phase="t2_sb1",
                silver_confidence=None,
                geometric_score=None,
                ai_labeler_version=ai_labeler_version,
                codex_dispatch=_dispatch_from_file,
                rng=forced_rng,
            )
        except ValueError as exc:
            # Service-layer ValueError (e.g., CodexReviewResponse.agreed=
            # False but missing alternative_evaluation) -> clean
            # ClickException per T-A.1.5b R4 M#1 forward-binding lesson.
            raise click.ClickException(
                f"codex-response-file shape invalid: {exc}"
            ) from exc

        if codex_response.agreed:
            click.echo(
                f"codex agreement recorded: exemplar_id={exemplar_id} "
                f"codex_agreement=1 (no new row inserted)"
            )
        else:
            click.echo(
                f"codex_silver row persisted: id={codex_id} "
                f"parent_exemplar_id={exemplar_id} final_decision="
                f"{codex_response.alternative_evaluation}"
            )
    finally:
        conn.close()


def _emit_or_skip_payload(
    *,
    parent: object,
    exemplar_id: int,
    seed: int | None,
    random_sample_probability: float,
    should_fire: object,
    get_rule_criteria: object,
    get_evidence_schema: object,
) -> None:
    """Emit dispatch payload OR skip-note per random-15% sampling decision.

    Pure stdout side-effect; no DB writes. Helper extracted so the persist
    path can stay tight + the emit-vs-skip branch is independently testable.
    """
    import json as _json
    import random as _random

    rng = _random.Random(seed) if seed is not None else _random.Random()
    fire = should_fire(phase="t2_sb1", rng=rng)
    if not fire:
        click.echo(
            f"[skip] exemplar {exemplar_id} not selected by random-"
            f"{int(random_sample_probability * 100)}% sample"
            + (f" (seed={seed})" if seed is not None else "")
            + ". No Codex dispatch fired."
        )
        return

    # Fire: emit dispatch payload JSON to stdout for operator-paired Codex
    # dispatch handoff (mirrors label-exemplars emit-payload contract).
    rule_criteria = get_rule_criteria(parent.proposed_pattern_class)
    structural_evidence_schema = get_evidence_schema(
        parent.proposed_pattern_class,
    )
    payload = {
        "parent_exemplar_id": exemplar_id,
        "parent_label_source": parent.label_source,
        "proposed_pattern_class": parent.proposed_pattern_class,
        "ticker": parent.ticker,
        "timeframe": parent.timeframe,
        "start_date": parent.start_date,
        "end_date": parent.end_date,
        "claude_silver_evaluation": parent.final_decision,
        "claude_silver_final_pattern_class": parent.final_pattern_class,
        "claude_silver_structural_evidence_json": (
            parent.structural_evidence_json
        ),
        "claude_silver_labeler_evidence_json": (
            parent.labeler_evidence_json
        ),
        "rule_criteria": rule_criteria,
        "structural_evidence_schema": structural_evidence_schema,
        "operator_guidance": (
            "Dispatch the copowers Codex MCP server with the claude silver "
            "label above + the rule_criteria + structural_evidence_schema. "
            "Capture the Codex response JSON per the CodexReviewResponse "
            "contract (agreed: bool; alternative_evaluation; "
            "alternative_confidence; alternative_structural_evidence_json) "
            "+ rerun this CLI with --codex-response-file <path> to persist."
        ),
    }
    click.echo(_json.dumps(payload, sort_keys=True, indent=2))


# ===========================================================================
# Phase 13 T2.SB6c T-A.6c.3 — §1.5.2 amendment: one-shot Path C backfill of
# pattern_exemplars.labeler_evidence_json (synthesize rule_criteria from
# pattern_exemplars.geometric_score_json COLUMN; copy narrative from
# geometric_evidence_narrative payload key; preserve original keys;
# idempotent; fail-soft per row).
# ===========================================================================

_pe_backfill_logger = _pe_backfill_logging.getLogger(__name__)


def _synthesize_rule_criteria_from_geometric_score(
    geometric_score_json: str | None,
) -> list[dict]:
    """Synthesize rule_criteria array from geometric_score_json column.

    Input: the geometric_score_json TEXT column value (NOT a key inside
           labeler_evidence_json).
    Output: list of {"name": str, "status": "pass"|"fail",
                     "evidence_value": str, "threshold": str,
                     "tolerance": str | None} entries.

    Returns empty list when geometric_score_json is NULL/empty OR when
    its JSON shape does not match the expected {"rules": {...}}
    convention (e.g. older shapes with "criteria": [...] array — V2
    candidate to widen).
    """
    if not geometric_score_json:
        return []
    import json as _json
    try:
        parsed = _json.loads(geometric_score_json)
    except _json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    criteria: list[dict] = []
    rules = parsed.get("rules") or {}
    if isinstance(rules, dict):
        # Sort by rule name for deterministic ordering (idempotency-safe).
        for rule_name in sorted(rules.keys()):
            rule_result = rules[rule_name]
            if not isinstance(rule_result, dict):
                continue
            passed = rule_result.get("pass")
            criteria.append({
                "name": rule_name,
                "status": "pass" if passed else "fail",
                "evidence_value": str(rule_result.get("value", "")),
                "threshold": str(rule_result.get("threshold", "")),
                "tolerance": (
                    str(rule_result.get("tolerance"))
                    if rule_result.get("tolerance") is not None else None
                ),
            })
    return criteria


def patterns_exemplars_backfill_labeler_evidence_run(conn) -> tuple[int, int]:
    """One-shot Path C backfill runner; returns (augmented, skipped).

    Idempotent: re-runs are no-ops on already-augmented payloads (detected
    by ``rule_criteria`` + ``narrative`` keys present pre-run).

    Skips rows where ``labeler_evidence_json IS NULL`` (Invariant #5
    NULL-required source class).

    Per Codex R2 MAJOR #5 closure: if ``rule_criteria`` missing AND
    ``geometric_score_json`` is NULL/empty, the row is SKIPPED (do NOT
    write an empty rule_criteria array; the operator can re-run after
    populating geometric_score_json).

    Fail-soft per row: any exception is WARN-logged + the row is skipped.
    """
    import json as _json

    from swing.data.repos.pattern_exemplars import (
        list_exemplars,
        update_exemplar_labeler_evidence_json,
    )

    augmented, skipped = 0, 0
    for row in list_exemplars(conn):
        if row.labeler_evidence_json is None:
            # Invariant #5 NULL-required source class; not eligible.
            continue
        try:
            payload = _json.loads(row.labeler_evidence_json)
            if not isinstance(payload, dict):
                _pe_backfill_logger.warning(
                    "backfill skipped exemplar %s: labeler_evidence_json "
                    "is not a JSON object", row.id,
                )
                skipped += 1
                continue
            if "rule_criteria" in payload and "narrative" in payload:
                # Already augmented; idempotent skip.
                skipped += 1
                continue
            # Per Codex R2 MAJOR #5: when rule_criteria is missing AND
            # geometric_score_json is unavailable, skip the row.
            if "rule_criteria" not in payload and not row.geometric_score_json:
                _pe_backfill_logger.warning(
                    "backfill skipped exemplar %s: geometric_score_json is "
                    "NULL/empty; rule_criteria cannot be synthesized",
                    row.id,
                )
                skipped += 1
                continue
            if "narrative" not in payload:
                payload["narrative"] = payload.get(
                    "geometric_evidence_narrative", "",
                )
            if "rule_criteria" not in payload:
                payload["rule_criteria"] = (
                    _synthesize_rule_criteria_from_geometric_score(
                        row.geometric_score_json,
                    )
                )
            new_json = _json.dumps(payload, sort_keys=True)
            with conn:
                update_exemplar_labeler_evidence_json(
                    conn, row.id, new_json,
                )
            augmented += 1
        except Exception as exc:  # fail-soft per row
            _pe_backfill_logger.warning(
                "backfill skipped exemplar %s: %s", row.id, exc,
            )
            skipped += 1
    return augmented, skipped


@main.command("patterns-exemplars-backfill-labeler-evidence")
@click.pass_context
def patterns_exemplars_backfill_labeler_evidence(ctx: click.Context) -> None:
    """Phase 13 T2.SB6c T-A.6c.3 — Path C one-shot backfill.

    Synthesizes ``rule_criteria`` + ``narrative`` keys on existing
    ``pattern_exemplars.labeler_evidence_json`` payloads.

    Idempotent + fail-soft per row. ASCII-only output per Windows cp1252
    stdout safety.
    """
    from swing.data.db import connect

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        augmented, skipped = patterns_exemplars_backfill_labeler_evidence_run(
            conn,
        )
    finally:
        conn.close()
    click.echo(f"Augmented: {augmented}; Skipped: {skipped}")


# ---------------------------------------------------------------------------
# Phase 13 T4.SB T-T4.SB.1 -- ``swing diagnose`` subcommand group.
#
# Read-only diagnostics: A+ sensitivity sweep harness + metrics-wiring audit.
# Each subcommand emits a deterministic markdown report (+ CSV sidecar where
# applicable) to ``exports/diagnostics/`` and writes ZERO domain rows.
# Per cumulative gotchas: ValueError-wrapping at CLI boundary;
# ASCII-only output for cp1252 Windows-stdout safety.
# ---------------------------------------------------------------------------


@main.group("diagnose")
def diagnose_group() -> None:
    """Diagnostic CLIs: aplus sensitivity sweep + metrics-wiring audit."""


def _validate_diagnose_db_path(db_path: Path) -> None:
    """Pre-validate the ``--db`` argument for diagnose subcommands.

    Codex R1 m#2 — raw ``sqlite3.connect(path)`` would CREATE an empty
    SQLite file at a typoed path before any query runs (sqlite3 default
    behavior); the operator gets an ugly ``OperationalError`` traceback
    on first SELECT + a stray empty DB file lingers on disk. Pre-
    validate existence + raise a friendly ``click.ClickException``
    BEFORE opening the connection.
    """
    if not db_path.exists():
        raise click.ClickException(
            f"DB not found: {db_path}. Run 'swing db-migrate' to "
            f"initialize, or check the --db path."
        )


@diagnose_group.command("aplus-sensitivity")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--eval-runs", type=click.IntRange(1, 100), default=20, show_default=True,
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/diagnostics"), show_default=True,
)
def diagnose_aplus_sensitivity(
    db_path: Path, eval_runs: int, output_dir: Path,
) -> None:
    """1D sensitivity sweep over A+ criteria thresholds.

    Reads persisted candidate_criteria from ``--db`` (last ``--eval-runs``
    runs); substitutes each variable across a sweep range; writes
    ``aplus-sensitivity-<ISO>.csv`` + ``.md`` to ``--output-dir``.
    """
    # Codex R1 m#2: pre-validate --db existence so a typo surfaces as a
    # friendly error before the harness opens any sqlite3 connection.
    _validate_diagnose_db_path(db_path)
    try:
        from research.harness.aplus_sensitivity.run import run_harness

        md_path, csv_path = run_harness(
            db_path=db_path, eval_runs=eval_runs, output_dir=output_dir,
        )
    except ValueError as exc:
        # Wrap service-layer ValueErrors at the CLI boundary per cumulative
        # gotcha (Phase 13 T-A.1.5b Codex R4 M#1).
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        # Codex R1 m#2: wrap raw OperationalError so the operator sees a
        # friendly message instead of a traceback.
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    click.echo(f"Markdown: {md_path}")
    click.echo(f"CSV:      {csv_path}")


@diagnose_group.command("aplus-sensitivity-v2")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--eval-runs", type=click.IntRange(1, 100), default=20, show_default=True,
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/diagnostics"), show_default=True,
)
@click.option(
    "--variables-filter", "variables_filter", type=str, default=None,
    help="Comma-separated variable-name filter for incremental runs / debugging.",
)
@click.option(
    "--min-universe-size", "min_universe_size", type=int, default=100,
    show_default=True,
    help="Minimum valid RS universe size after cleanup; fail-fast below.",
)
@click.option(
    "--max-runtime-seconds", "max_runtime_seconds", type=float, default=None,
    help="Optional runtime cap; emits partial-result with PARTIAL RUN header.",
)
def diagnose_aplus_sensitivity_v2(
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
    evaluate_one(ctx) end-to-end against historical OHLCV. See
    research/method-records/aplus-criteria-calibration.md (v0.2.0+).
    """
    # Codex R1 m#2 precedent: pre-validate --db existence so a typo surfaces
    # as a friendly error before the harness opens any sqlite3 connection.
    _validate_diagnose_db_path(db_path)
    from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness

    filter_tuple: tuple[str, ...] | None = None
    if variables_filter:
        filter_tuple = tuple(
            s.strip() for s in variables_filter.split(",") if s.strip()
        )

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
        # Wrap service-layer ValueErrors at the CLI boundary per cumulative
        # gotcha (Phase 13 T-A.1.5b Codex R4 M#1).
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    click.echo(f"Markdown: {md_path}")
    click.echo(f"CSV:      {csv_path}")


@diagnose_group.command("pattern-cohort-detect")
@click.option(
    "--cohort-csv", "cohort_csv", type=click.Path(path_type=Path), default=None,
    help="Path to cohort CSV (Mode (b)); mutually exclusive with --cohort-inline.",
)
@click.option(
    "--cohort-inline", "cohort_inline", type=str, default=None,
    help="Inline 'TICKER:YYYY-MM-DD,...' spec (Mode (a)); mutually exclusive with --cohort-csv.",
)
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/research"), show_default=True,
)
@click.option(
    "--window-mode", type=click.Choice(("last-only", "per-window")),
    default="per-window", show_default=True,
)
@click.option(
    "--template-match", "template_match_mode",
    type=click.Choice(("on", "off")), default="on", show_default=True,
)
@click.option(
    "--pattern-class-filter", "pattern_class_filter", type=str, default=None,
    help="Comma-separated pattern_class filter (subset of {vcp, flat_base, "
         "cup_with_handle, high_tight_flag, double_bottom_w}).",
)
def diagnose_pattern_cohort_detect(
    cohort_csv: Path | None,
    cohort_inline: str | None,
    db_path: Path,
    output_dir: Path,
    window_mode: str,
    template_match_mode: str,
    pattern_class_filter: str | None,
) -> None:
    """Pattern cohort detector evaluator harness (research-branch only).

    Invokes the 5 Phase 13 chart-shape detectors against an operator-supplied
    cohort of (ticker, asof_date) tuples + emits per-(entry, pattern_class,
    window) verdicts CSV + analyst-readable markdown summary + manifest JSON.
    Designed to answer gotcha #27's silent-skip research question for
    loosened-A+ cohorts. See research/method-records/pattern-cohort-detection.md.
    """
    _validate_diagnose_db_path(db_path)
    from research.harness.pattern_cohort_evaluator.exceptions import (
        BothCohortModesSuppliedError,
        NeitherCohortModeSuppliedError,
    )
    from research.harness.pattern_cohort_evaluator.run import run_harness

    filter_tuple: tuple[str, ...] | None = None
    if pattern_class_filter:
        filter_tuple = tuple(
            s.strip() for s in pattern_class_filter.split(",") if s.strip()
        )

    try:
        results_csv, summary_md, manifest_json = run_harness(
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
            f"Database error reading {db_path}: {exc}",
        ) from exc
    click.echo(f"Results CSV: {results_csv}")
    click.echo(f"Summary MD:  {summary_md}")
    click.echo(f"Manifest:    {manifest_json}")


@diagnose_group.command("double-bottom-w-backtest")
@click.option(
    "--results-csv", "results_csv", type=click.Path(path_type=Path), default=None,
    help="Path to pattern_cohort_evaluator results.csv (stream-parsed + deduped).",
)
@click.option(
    "--cohort-fixture", "cohort_fixture", type=click.Path(path_type=Path), default=None,
    help="Path to pre-extracted cohort.json (skips results.csv parsing).",
)
@click.option(
    "--cache-dir", "cache_dir", required=True, type=click.Path(path_type=Path),
    help="OHLCV Shape A cache directory (typically ~/swing-data/prices-cache).",
)
@click.option(
    "--output-dir", "output_dir", type=click.Path(path_type=Path),
    default=Path("exports/research"), show_default=True,
)
@click.option(
    "--composite-threshold", "composite_threshold", type=float, default=0.7,
    show_default=True,
)
@click.option(
    "--recency-max-calendar-days", "recency_max_calendar_days", type=int, default=60,
    show_default=True,
)
@click.option(
    "--no-recency-filter", "no_recency_filter", is_flag=True, default=False,
    help="Skip recency filter; backtest ALL unique W primary verdicts.",
)
@click.option(
    "--source-artifact-dir", "source_artifact_dir", type=click.Path(path_type=Path),
    default=None,
    help="Upstream pattern_cohort_evaluator run dir for manifest provenance.",
)
def diagnose_double_bottom_w_backtest(
    results_csv: Path | None,
    cohort_fixture: Path | None,
    cache_dir: Path,
    output_dir: Path,
    composite_threshold: float,
    recency_max_calendar_days: int,
    no_recency_filter: bool,
    source_artifact_dir: Path | None,
) -> None:
    """D1 double_bottom_w walk-forward backtest (research-branch only).

    Filters pattern_cohort_evaluator verdicts to double_bottom_w +
    composite>=threshold; deduplicates by (ticker, trough_1_date); restricts
    to RECENT W's (trough_2 within N calendar days of asof); walks forward
    from each pattern's data_asof_date applying 3 exit rulesets
    (Minervini trail-MA / fixed R-multiple / close-below-50d). Tests the
    Turn F study writeup R1 reframing hypothesis. See
    docs/pattern-cohort-double-bottom-w-backtest-dispatch-brief.md.
    """
    if (results_csv is None) == (cohort_fixture is None):
        raise click.ClickException(
            "Exactly one of --results-csv or --cohort-fixture must be supplied"
        )
    from research.harness.double_bottom_w_backtest.run import main as backtest_main

    argv: list[str] = []
    if results_csv is not None:
        argv += ["--results-csv", str(results_csv)]
    else:
        argv += ["--cohort-fixture", str(cohort_fixture)]
    argv += [
        "--cache-dir", str(cache_dir),
        "--output-dir", str(output_dir),
        "--composite-threshold", str(composite_threshold),
        "--recency-max-calendar-days", str(recency_max_calendar_days),
    ]
    if no_recency_filter:
        argv += ["--no-recency-filter"]
    if source_artifact_dir is not None:
        argv += ["--source-artifact-dir", str(source_artifact_dir)]
    exit_code = backtest_main(argv)
    if exit_code != 0:
        raise click.ClickException(f"Backtest harness exit code {exit_code}")


@diagnose_group.command("w-bottom-ruleset-comparison")
@click.option(
    "--results-csv", "results_csv", type=click.Path(path_type=Path), default=None,
    help="Path to pattern_cohort_evaluator results.csv (stream-parsed + deduped).",
)
@click.option(
    "--cohort-fixture", "cohort_fixture", type=click.Path(path_type=Path), default=None,
    help="Path to pre-extracted cohort.json (skips results.csv parsing).",
)
@click.option(
    "--cache-dir", "cache_dir", required=True, type=click.Path(path_type=Path),
    help="OHLCV Shape A cache directory (typically ~/swing-data/prices-cache).",
)
@click.option(
    "--output-dir", "output_dir", type=click.Path(path_type=Path),
    default=Path("exports/research"), show_default=True,
)
@click.option(
    "--composite-threshold", "composite_threshold", type=float, default=0.7,
    show_default=True,
)
@click.option(
    "--recency-max-calendar-days", "recency_max_calendar_days", type=int, default=60,
    show_default=True,
)
@click.option(
    "--no-recency-filter", "no_recency_filter", is_flag=True, default=False,
    help="Skip recency filter; backtest ALL unique W primary verdicts.",
)
@click.option(
    "--source-artifact-dir", "source_artifact_dir", type=click.Path(path_type=Path),
    default=None,
    help="Upstream pattern_cohort_evaluator run dir for manifest provenance.",
)
def diagnose_w_bottom_ruleset_comparison(
    results_csv: Path | None,
    cohort_fixture: Path | None,
    cache_dir: Path,
    output_dir: Path,
    composite_threshold: float,
    recency_max_calendar_days: int,
    no_recency_filter: bool,
    source_artifact_dir: Path | None,
) -> None:
    """D2 W-bottom ruleset comparison backtest (research-branch only).

    Extends D1 with 3 NEW literature-canonical rulesets (Minervini Stage-2 /
    O'Neil cup-with-handle + Bulkowski measured-move / Qullamaggie momentum-
    burst) tested against an S&P-500-wide W cohort (N=50-200 patterns).
    Six rulesets in total (A/B/C reused from D1; D/E/F NEW). See
    docs/pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md.
    """
    if (results_csv is None) == (cohort_fixture is None):
        raise click.ClickException(
            "Exactly one of --results-csv or --cohort-fixture must be supplied"
        )
    from research.harness.w_bottom_ruleset_comparison.run import main as backtest_main

    argv: list[str] = []
    if results_csv is not None:
        argv += ["--results-csv", str(results_csv)]
    else:
        argv += ["--cohort-fixture", str(cohort_fixture)]
    argv += [
        "--cache-dir", str(cache_dir),
        "--output-dir", str(output_dir),
        "--composite-threshold", str(composite_threshold),
        "--recency-max-calendar-days", str(recency_max_calendar_days),
    ]
    if no_recency_filter:
        argv += ["--no-recency-filter"]
    if source_artifact_dir is not None:
        argv += ["--source-artifact-dir", str(source_artifact_dir)]
    exit_code = backtest_main(argv)
    if exit_code != 0:
        raise click.ClickException(f"Backtest harness exit code {exit_code}")


@diagnose_group.command("metrics-wiring")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--output", "output_path", required=True, type=click.Path(path_type=Path),
)
def diagnose_metrics_wiring(db_path: Path, output_path: Path) -> None:
    """Enumerate metric surfaces + audit match strategy / state filter /
    join keys / operator-DB count / disposition. Writes markdown table.
    """
    import sqlite3 as _sqlite3

    from swing.diagnostics.metrics_wiring_audit import (
        write_metrics_wiring_audit_markdown,
    )

    # Codex R1 m#2: pre-validate --db existence so a typo surfaces as a
    # friendly error before sqlite3.connect auto-creates an empty file.
    _validate_diagnose_db_path(db_path)
    try:
        conn = _sqlite3.connect(str(db_path))
        try:
            write_metrics_wiring_audit_markdown(conn, output_path)
        finally:
            conn.close()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except _sqlite3.OperationalError as exc:
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    click.echo(f"Audit:    {output_path}")


@diagnose_group.command("prune-chart-cache")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--older-than", "older_than_days", required=True,
    type=click.IntRange(0, 36500),
    help="Delete chart_renders rows whose rendered_at is older than N days.",
)
def diagnose_prune_chart_cache(db_path: Path, older_than_days: int) -> None:
    """Phase 13 T-T4.SB.3 (Item 5; OQ-5.1 R4 LOCK) — manual prune of the
    chart_renders cache.

    Deletes ``chart_renders`` rows whose ``rendered_at`` is older than
    ``--older-than`` calendar days (UTC). Operator-invoked under monitored
    growth. V2 candidate banked for automated time-based eviction.
    """
    import sqlite3 as _sqlite3

    from swing.diagnostics.prune_chart_cache import (
        prune_chart_renders_older_than,
    )

    # Codex R1 m#2: pre-validate --db existence so a typo surfaces as a
    # friendly error before sqlite3.connect auto-creates an empty file.
    _validate_diagnose_db_path(db_path)
    try:
        conn = _sqlite3.connect(str(db_path))
        try:
            with conn:
                deleted = prune_chart_renders_older_than(
                    conn, older_than_days=older_than_days,
                )
        finally:
            conn.close()
    except ValueError as exc:
        # Wrap service-layer ValueErrors at the CLI boundary per cumulative
        # gotcha (Phase 13 T-A.1.5b Codex R4 M#1).
        raise click.ClickException(str(exc)) from exc
    except _sqlite3.OperationalError as exc:
        # Codex R1 m#2: wrap raw OperationalError so the operator sees a
        # friendly message instead of a traceback (e.g., DB missing
        # chart_renders table on a legacy schema).
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    click.echo(f"Deleted {deleted} chart_renders rows older than "
               f"{older_than_days} days.")


@diagnose_group.command("backfill-trades-sector-industry")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--apply", is_flag=True, default=False,
    help="Commit UPDATEs (atomic). Default: dry-run only.",
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/diagnostics"), show_default=True,
    help="Directory for the restore-SQL artifact + dry-run table.",
)
@click.option(
    "--allowlist", type=str, default="",
    help="Comma-separated tickers to opt-in (overrides default open-set).",
)
@click.option(
    "--include-closed", is_flag=True, default=False,
    help=(
        "Widen to all trade states (default: entered/managing/partial_exited)."
    ),
)
def diagnose_backfill_trades_sector_industry(
    db_path: Path, apply: bool, output_dir: Path, allowlist: str,
    include_closed: bool,
) -> None:
    """One-time backfill of trades.sector + trades.industry for V2.G3.

    Strict all-or-nothing semantic: only rows with BOTH sector and
    industry TRIM-empty get UPDATEd, AND only when the candidates-table
    helper returns BOTH non-empty replacements. Partial-empty rows are
    enumerated separately as SKIP_PARTIAL_EMPTY (V1 STRICT per spec
    section 4.3 R2.M3 LOCK; V2 candidate banked for per-column lookup).

    Dry-run (default) prints the affected count + emits a restore-SQL
    artifact at <output-dir>/backfill-trades-sector-industry-restore-<ISO>.sql
    so the apply step is reversible.

    Apply path commits the UPDATEs under ``with conn:`` atomically and
    re-emits the restore-SQL artifact BEFORE issuing UPDATEs (defense-
    in-depth against crash post-UPDATE; per spec section 4.3 R1.M3 LOCK).
    """
    _validate_diagnose_db_path(db_path)
    try:
        from swing.diagnostics.backfill_trades_sector_industry import (
            run_backfill,
        )
        summary = run_backfill(
            db_path=db_path,
            apply=apply,
            output_dir=output_dir,
            allowlist=_parse_allowlist(allowlist),
            include_closed=include_closed,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    for line in summary.report_lines:
        click.echo(line)
    click.echo(f"Restore-SQL artifact: {summary.restore_sql_path}")


def _parse_allowlist(raw: str) -> tuple[str, ...] | None:
    """Parse the --allowlist comma-separated option into a ticker tuple."""
    if not raw.strip():
        return None
    return tuple(t.strip().upper() for t in raw.split(",") if t.strip())


if __name__ == "__main__":  # pragma: no cover
    main()
