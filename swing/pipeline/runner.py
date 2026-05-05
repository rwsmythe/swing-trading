"""Pipeline runner — orchestrates 9 spec §5.1 steps with lease + staging + recovery."""
from __future__ import annotations

import base64
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime as _dt
from pathlib import Path

from swing.config import Config
from swing.data.backup import do_backup, prune_old_backups, should_backup
from swing.data.db import connect
from swing.data.models import Candidate, EvaluationRun
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.cash import list_cash
from swing.data.repos.pattern_classifications import insert_classification
from swing.data.repos.pipeline import (
    LeaseRevoked,
    insert_chart_target,
    set_evaluation_run_id,
    update_chart_target_status,
)
from swing.data.repos.recommendations import upsert_recommendation
from swing.data.repos.trades import list_open_trades
from swing.data.repos.watchlist import (
    archive_watchlist_entry,
    list_active_watchlist,
    upsert_watchlist_entry,
)
from swing.data.repos.weather import get_latest_for_date
from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.evaluation.evaluator import evaluate_batch
from swing.evaluation.patterns.flag_classifier import (
    FlagClassificationResult,
    classify_flag,
)
from swing.evaluation.rs import load_universe, universe_version_hash
from swing.pipeline.finviz_schema import reject_csv, validate_csv
from swing.pipeline.finviz_select import AmbiguousInboxError, NoFilesError, select_csv
from swing.pipeline.heartbeat import Heartbeat
from swing.pipeline.lease import (
    ConcurrentRunBlocked,
    Lease,
    acquire_lease,
)
from swing.pipeline.recovery import sweep_stale_artifacts
from swing.pipeline.staging import StagingDir, promote_staging
from swing.prices import PriceFetcher
from swing.recommendations.build import BuildContext, build_recommendations
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.charts import (
    ChartingUnavailable,
    PatternOverlay,
    render_chart,
)
from swing.rendering.exporter import export_briefing
from swing.trades.equity import current_equity, sizing_equity
from swing.watchlist.service import compute_watchlist_changes

log = logging.getLogger(__name__)


# C.10 migration helper (was: list_all_exits shim from repos/trades.py).
# current_equity() is duck-typed on .realized_pnl; we only need a list of
# objects exposing that attribute. Mirrors the per-module _ExitShape
# pattern in web view models and review_log; dies in the future cleanup
# phase when equity.py refactors to consume Fill directly.
@dataclass(frozen=True)
class _ExitShape:
    trade_id: int
    realized_pnl: float | None


def _exits_via_fills_for_equity(
    conn: sqlite3.Connection,
) -> list[_ExitShape]:
    """Return ExitLike-shape rows (action != 'entry' fills) for equity
    computation. Per-row realized_pnl derives from the parent trade's
    entry_price via ``swing.trades.derived_metrics`` — single source of
    math truth.
    """
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.trades import list_closed_trades
    from swing.trades.derived_metrics import realized_pnl

    trades_by_id: dict[int, object] = {}
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
        pnl = realized_pnl(
            entry_price=trade.entry_price, exit_price=f.price,
            quantity=f.quantity,
        )
        out.append(_ExitShape(trade_id=f.trade_id, realized_pnl=pnl))
    return out


@dataclass(frozen=True)
class RunResult:
    run_id: int
    state: str
    error_message: str | None


def _b64_chart(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")




_BACKUP_RETENTION_WEEKS = 12


def _maybe_weekly_backup(cfg: Config) -> None:
    """First pipeline run of each ISO calendar week snapshots the DB.

    Runs BEFORE any DB writes by this pipeline run (sweep, lease, evaluation).
    Failures (disk full, permissions, missing DB) are logged but do NOT abort
    the pipeline — operational data flow takes precedence over backup hygiene.
    KeyboardInterrupt and SystemExit are intentionally NOT caught.
    """
    try:
        now = _dt.now()
        if not cfg.paths.db_path.exists():
            return
        if not should_backup(cfg.paths.backups_dir, now):
            return
        path = do_backup(cfg.paths.db_path, cfg.paths.backups_dir, now=now)
        log.info("weekly backup written: %s", path)
    except (OSError, sqlite3.Error) as exc:
        log.warning("weekly backup failed (continuing pipeline): %s", exc)
        return
    try:
        prune_old_backups(cfg.paths.backups_dir, keep=_BACKUP_RETENTION_WEEKS)
    except (OSError, sqlite3.Error) as exc:
        log.warning("weekly backup prune failed (continuing pipeline): %s", exc)


def run_pipeline_internal(*, cfg: Config, trigger: str) -> RunResult:
    """Synchronous pipeline run. Caller owns the process — heartbeat is in this thread."""
    _maybe_weekly_backup(cfg)
    sweep = sweep_stale_artifacts(
        db_path=cfg.paths.db_path,
        artifact_dirs=[cfg.paths.charts_dir, cfg.paths.exports_dir],
        prev_retention_days=cfg.pipeline.prev_dir_retention_days,
        orphan_age_seconds=cfg.pipeline.staging_orphan_age_seconds,
        stale_heartbeat_seconds=cfg.pipeline.stale_lease_threshold_seconds,
    )
    if sweep.flagged_stale_running_runs:
        log.warning(
            "sweep: running runs %s have heartbeats older than %ss — "
            "inspect via `swing pipeline list` and consider force-clear "
            "if step-progress is also stale (spec §5.6 two-signal check).",
            sweep.flagged_stale_running_runs,
            cfg.pipeline.stale_lease_threshold_seconds,
        )

    # Acquire the lease BEFORE touching the Finviz inbox so concurrent runs
    # cannot both select/validate/reject the same file before one is fenced
    # (adversarial review Batch 4 Round 1 Major 1). finviz_csv_path is set
    # lease-fenced after select_csv resolves the file.
    run_now = _dt.now()
    action_session = action_session_for_run(run_now)
    data_asof_str = last_completed_session(run_now).isoformat()
    universe = load_universe(cfg.paths.rs_universe_path)
    universe_hash = universe_version_hash(cfg.paths.rs_universe_path)

    try:
        lease = acquire_lease(
            db_path=cfg.paths.db_path, trigger=trigger,
            data_asof_date=data_asof_str,
            action_session_date=action_session.isoformat(),
            block_threshold_seconds=cfg.pipeline.block_if_running_within_seconds,
            finviz_csv_path=None,
            rs_universe_version=universe.version,
            rs_universe_hash=universe_hash,
        )
    except ConcurrentRunBlocked as exc:
        log.warning("blocked: %s", exc)
        return RunResult(run_id=0, state="blocked", error_message=str(exc))

    hb = Heartbeat(lease=lease, interval_seconds=cfg.pipeline.heartbeat_interval_seconds)
    hb.start()

    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
    eval_run_id = 0
    try:
        # Finviz selection/validation under the lease.
        try:
            csv_path = select_csv(cfg.paths.finviz_inbox_dir)
        except (NoFilesError, AmbiguousInboxError) as exc:
            log.error("Finviz inbox: %s", exc)
            lease.release(state="failed", error_message=str(exc))
            return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))

        val = validate_csv(csv_path)
        if not val.is_valid:
            rejected_dir = cfg.paths.finviz_inbox_dir / "rejected"
            reject_csv(csv_path, val, rejected_dir=rejected_dir)
            msg = f"Finviz CSV rejected: {val.reasons}"
            lease.release(state="failed", error_message=msg)
            return RunResult(run_id=lease.run_id, state="failed", error_message=msg)

        # Record the selected CSV path on the pipeline_runs row, lease-fenced.
        # Zero-row UPDATE means the lease was revoked between acquire and now;
        # raise explicitly rather than silently proceeding (adversarial review
        # Batch 4 Round 2 Major 1).
        conn = connect(cfg.paths.db_path)
        try:
            cur = conn.execute(
                "UPDATE pipeline_runs SET finviz_csv_path = ? "
                "WHERE id = ? AND lease_token = ? AND state = 'running'",
                (str(csv_path), lease.run_id, lease.token),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise LeaseRevoked(
                    f"lease revoked before finviz_csv_path update "
                    f"for run_id={lease.run_id}"
                )
        finally:
            conn.close()

        try:
            lease.step("weather")
            try:
                from swing.data.models import WeatherRun
                from swing.data.repos.weather import upsert_weather_run
                from swing.weather.classifier import classify_weather
                ohlcv = fetcher.get(
                    cfg.rs.benchmark_ticker, lookback_days=180, as_of_date=None,
                )
                classification = classify_weather(ohlcv)
                # Lease-fenced write: BEGIN IMMEDIATE + in-txn lease check +
                # upsert + COMMIT. A concurrent force_clear either commits
                # before us (we ROLLBACK) or waits behind our RESERVED lock
                # (our write lands atomically then force_clear proceeds).
                with lease.fenced_write() as conn:
                    upsert_weather_run(conn, WeatherRun(
                        id=None,
                        run_ts=_dt.now().isoformat(timespec="seconds"),
                        asof_date=classification.asof_date,
                        ticker=cfg.rs.benchmark_ticker,
                        status=classification.status,
                        close=classification.close,
                        sma10=classification.sma10,
                        sma20=classification.sma20,
                        sma50=classification.sma50,
                        slope20_5bar=classification.slope20_5bar,
                        slope10_5bar=classification.slope10_5bar,
                        rationale=classification.rationale,
                    ))
                lease.status(weather_status="ok")
            except LeaseRevoked:
                raise
            except Exception as exc:
                log.warning("weather failed: %s", exc)
                lease.status(weather_status="failed")

            lease.step("evaluate")
            try:
                eval_run_id = _step_evaluate(
                    cfg=cfg, fetcher=fetcher, csv_path=csv_path,
                    universe=universe, universe_hash=universe_hash,
                    run_now=run_now, action_session=action_session,
                    lease=lease,
                )
                lease.status(evaluation_status="ok")
            except LeaseRevoked:
                raise
            except Exception as exc:
                log.error("evaluation failed: %s", exc)
                lease.status(evaluation_status="failed")
                lease.release(state="failed", error_message=str(exc))
                return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))

            lease.step("watchlist")
            try:
                _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                                data_asof_date=lease_data_asof(cfg, lease),
                                lease=lease)
                lease.status(watchlist_status="ok")
            except LeaseRevoked:
                raise
            except Exception as exc:
                log.warning("watchlist failed: %s", exc)
                lease.status(watchlist_status="failed")

            lease.step("recommendations")
            try:
                _step_recommendations(cfg=cfg, eval_run_id=eval_run_id,
                                       action_session=action_session,
                                       data_asof=lease_data_asof(cfg, lease),
                                       lease=lease)
                lease.status(recommendations_status="ok")
            except LeaseRevoked:
                raise
            except Exception as exc:
                log.warning("recommendations failed: %s", exc)
                lease.status(recommendations_status="failed")

            lease.step("charts")
            chart_paths: dict[str, Path] = {}
            try:
                chart_paths = _step_charts(
                    cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                    data_asof=lease_data_asof(cfg, lease), fetcher=fetcher,
                )
                lease.status(charts_status="ok")
            except LeaseRevoked:
                raise
            except ChartingUnavailable:
                lease.status(charts_status="skipped")
            except Exception as exc:
                log.warning("charts failed: %s", exc)
                lease.status(charts_status="failed")

            lease.step("export")
            try:
                _step_export(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                             action_session=action_session,
                             data_asof=lease_data_asof(cfg, lease),
                             chart_paths=chart_paths)
                lease.status(export_status="ok")
            except LeaseRevoked:
                raise
            except Exception as exc:
                log.warning("export failed: %s", exc)
                lease.status(export_status="failed")

            lease.step("complete")
            try:
                _step_review_log_cadence(lease=lease)
            except Exception as exc:
                # Cadence pre-create is auxiliary — its failure must NOT roll back the
                # primary value chain (briefing emission). Log + continue. Brief §6.2
                # watch item 13.
                log.warning("review_log cadence step failed (continuing): %s", exc)
            lease.release(state="complete")
        except LeaseRevoked as exc:
            # Force-cleared mid-run. The pipeline_runs row has already moved to
            # state='force_cleared'; we cannot lease.release() anymore. Just
            # log, stop the heartbeat via `finally`, and surface the outcome.
            log.warning("lease revoked during run: %s", exc)
            return RunResult(
                run_id=lease.run_id, state="force_cleared",
                error_message=str(exc),
            )
    finally:
        hb.stop()

    return RunResult(run_id=lease.run_id, state="complete", error_message=None)


def lease_data_asof(cfg: Config, lease: Lease) -> str:
    """Read back data_asof_date from the pipeline_runs row (single source of truth)."""
    conn = connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT data_asof_date FROM pipeline_runs WHERE id=?", (lease.run_id,)
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def _step_evaluate(
    *, cfg, fetcher, csv_path: Path, universe, universe_hash: str,
    run_now: _dt, action_session: _date, lease: Lease,
) -> int:
    lease.verify_held()
    import pandas as pd
    finviz_df = pd.read_csv(csv_path)
    if "Ticker" not in finviz_df.columns:
        raise ValueError(f"finviz CSV missing 'Ticker' column: {list(finviz_df.columns)}")
    tickers = finviz_df["Ticker"].dropna().astype(str).str.upper().tolist()

    # Sector/Industry passthrough from Finviz CSV -> candidate rows. Built
    # from the same DataFrame we just read so row-index-vs-ticker binding
    # matches the CSV exactly. NaN cells become empty strings; tickers not
    # in the CSV (held-position tickers appended via the loop below;
    # ETF-blocklist rows synthesized post-evaluate_batch) default to ('','').
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

    # Include open-trade tickers in the OHLCV fetch so their fresh close lands
    # in candidates.close. PriceCache._last_close reads that table; without
    # this, an open position whose ticker has rotated out of the finviz
    # screener keeps showing whatever close was captured the last time it
    # appeared in finviz (potentially days stale on the dashboard).
    open_conn = connect(cfg.paths.db_path)
    try:
        held_tickers: list[str] = sorted({
            t.ticker.upper() for t in list_open_trades(open_conn)
        })
    finally:
        open_conn.close()
    seen = set(tickers)
    for t in held_tickers:
        if t not in seen:
            tickers.append(t)
            seen.add(t)

    spy_return = 0.0
    spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=None)
    spy_closes = spy_df["Close"]
    weeks = cfg.rs.horizon_weeks
    if len(spy_closes) > weeks * 5:
        bars = weeks * 5
        spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)

    returns_12w: dict[str, float] = {}
    ohlcv_by_ticker: dict[str, "pd.DataFrame"] = {}
    error_tickers: list[str] = []
    bars_needed = cfg.rs.horizon_weeks * 5
    for t in tickers:
        try:
            df = fetcher.get(t, lookback_days=400, as_of_date=None)
            ohlcv_by_ticker[t] = df
            closes = df["Close"]
            if len(closes) > bars_needed:
                returns_12w[t] = float((closes.iloc[-1] / closes.iloc[-bars_needed - 1]) - 1)
        except Exception:
            error_tickers.append(t)
    for t in universe.tickers:
        if t in returns_12w:
            continue
        try:
            df = fetcher.get(t, lookback_days=120, as_of_date=None)
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

    max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
    if max_dates:
        data_asof = max(max_dates).date()
    else:
        data_asof = last_completed_session(run_now)

    eq_conn = connect(cfg.paths.db_path)
    try:
        sizing_eq = sizing_equity(
            real_equity=current_equity(
                starting_equity=cfg.account.starting_equity,
                exits=_exits_via_fills_for_equity(eq_conn),
                cash_movements=list_cash(eq_conn),
            ),
            floor=cfg.account.risk_equity_floor,
        )
    finally:
        eq_conn.close()

    # Held positions are locally-excluded from evaluation (they're already in
    # our portfolio — no buy/watch decision needed) but we still want their
    # fresh close in candidates.close for the dashboard price fallback.
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
            current_equity=sizing_eq,
        ))

    candidates = evaluate_batch(contexts)
    for t in excluded_tickers:
        # Preserve the ticker's close so PriceCache._last_close returns a
        # fresh value. ETF blocklist rows intentionally have no OHLCV fetch,
        # so they'll still carry close=None.
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
    for t in error_tickers:
        candidates.append(Candidate(
            ticker=t, bucket="error",
            close=None, pivot=None, initial_stop=None,
            adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
            rs_rank=None, rs_return_12w_vs_spy=None, rs_method="unavailable",
            pattern_tag=None, notes="OHLCV fetch failed", criteria=(),
        ))

    # Apply Sector/Industry uniformly across all candidate buckets (aplus /
    # watch / skip / error / excluded). evaluate_batch returns dataclasses
    # without these fields populated; held-position + ETF-blocklist + error
    # tickers were appended above in this function. Tickers in the CSV pull
    # from the lookup; tickers NOT in the CSV (held-position rows whose
    # symbol rotated out of finviz) default to ('','') -- graceful degradation
    # mirrors hypothesis_label free-text behavior.
    from dataclasses import replace as _dc_replace
    candidates = [
        _dc_replace(
            c,
            sector=sector_industry_by_ticker.get(c.ticker, ("", ""))[0],
            industry=sector_industry_by_ticker.get(c.ticker, ("", ""))[1],
        )
        for c in candidates
    ]

    run = EvaluationRun(
        id=None, run_ts=run_now.isoformat(timespec="seconds"),
        data_asof_date=data_asof.isoformat(),
        action_session_date=action_session.isoformat(),
        finviz_csv_path=str(csv_path),
        tickers_evaluated=len(candidates),
        aplus_count=sum(1 for c in candidates if c.bucket == "aplus"),
        watch_count=sum(1 for c in candidates if c.bucket == "watch"),
        skip_count=sum(1 for c in candidates if c.bucket == "skip"),
        excluded_count=len(excluded_tickers), error_count=len(error_tickers),
        rs_universe_version=universe.version, rs_universe_hash=universe_hash,
    )
    with lease.fenced_write() as conn:
        run_id = insert_evaluation_run(conn, run)
        insert_candidates(conn, run_id, candidates)
        # Tranche C T2: bind this pipeline_runs row to its OWN eval row in
        # the same transaction. Replaces the chart_scope resolver's
        # data_asof + run_ts heuristic for new runs (drift mode A); legacy
        # rows fall back to the heuristic when evaluation_run_id IS NULL.
        set_evaluation_run_id(
            conn, pipeline_run_id=lease.run_id, evaluation_run_id=run_id,
        )
    return run_id


def _step_watchlist(
    *, cfg, eval_run_id: int, data_asof_date: str, lease: Lease,
) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    # Read phase (no fence — reading is idempotent).
    read_conn = connect(cfg.paths.db_path)
    try:
        prior = list_active_watchlist(read_conn)
        candidates = fetch_candidates_for_run(read_conn, eval_run_id)
    finally:
        read_conn.close()
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=candidates,
        data_asof_date=data_asof_date,
    )
    # Write phase (lease-fenced — atomic with lease verification).
    with lease.fenced_write() as conn:
        for entry in delta.adds:
            upsert_watchlist_entry(conn, entry)
        for entry in delta.requalifies:
            upsert_watchlist_entry(conn, entry)
        for entry in delta.streak_increments:
            upsert_watchlist_entry(conn, entry)
        for archive in delta.removes:
            archive_watchlist_entry(conn, archive)


def _step_recommendations(*, cfg, eval_run_id: int,
                           action_session, data_asof: str, lease: Lease) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    # Read phase (no fence).
    read_conn = connect(cfg.paths.db_path)
    try:
        candidates = fetch_candidates_for_run(read_conn, eval_run_id)
        watchlist = list_active_watchlist(read_conn)
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=_exits_via_fills_for_equity(read_conn),
            cash_movements=list_cash(read_conn),
        )
    finally:
        read_conn.close()
    sized_eq = sizing_equity(real_equity=equity, floor=cfg.account.risk_equity_floor)
    ctx = BuildContext(
        evaluation_run_id=eval_run_id, data_asof_date=data_asof,
        action_session_date=action_session.isoformat(),
        current_equity=sized_eq,
        max_risk_pct=cfg.risk.max_risk_pct,
        position_pct_cap=cfg.sizing.position_pct_cap,
        near_trigger_above_pct=cfg.near_trigger.above_pct,
        near_trigger_below_pct=cfg.near_trigger.below_pct,
    )
    recs = build_recommendations(
        ctx=ctx,
        today_aplus=[c for c in candidates if c.bucket == "aplus"],
        prior_watchlist=watchlist,
    )
    # Write phase (lease-fenced).
    with lease.fenced_write() as conn:
        for r in recs:
            upsert_recommendation(conn, r)


def _step_charts(*, cfg, lease: Lease, eval_run_id: int, data_asof: str,
                  fetcher: PriceFetcher) -> dict[str, Path]:
    """Render charts for A+ + top-N near-trigger watchlist via staging.

    Writes go through `promote_staging`, which re-reads pipeline_runs in-line
    and raises `LeaseRevoked` if the lease has been force-cleared before the
    canonical rename. `verify_held()` is a cheap fail-fast so we don't render
    a staging dir's worth of charts only to discard them at promote time."""
    lease.verify_held()
    _walltime_start = time.monotonic()
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.trades import list_open_trades  # NEW (Task 5)
    conn = connect(cfg.paths.db_path)
    try:
        # Spec §A "Open-position tier snapshot semantics": all three reads
        # MUST observe the same committed DB state. Without an explicit
        # transaction, SQLite begins a fresh read transaction per statement
        # — a concurrent writer (e.g., operator entering a trade mid-pipeline)
        # could tear the snapshot across tiers.
        conn.execute("BEGIN")
        try:
            candidates = fetch_candidates_for_run(conn, eval_run_id)
            watchlist = list_active_watchlist(conn)
            # Task 5 (spec §A "Open-position tier"): read open trades inside the
            # same snapshot block — must happen BEFORE conn.close() below so the
            # 3-tier composition sees a consistent view of candidates +
            # watchlist + trades.
            open_trades = list_open_trades(conn)
        finally:
            # Read-only transaction — ROLLBACK to release the read lock without
            # writing anything (COMMIT would be valid too; ROLLBACK is more
            # explicit about the read-only intent).
            conn.execute("ROLLBACK")
    finally:
        conn.close()

    # Spec §A — three-tier composition with precedence-ordered dedup.
    aplus = [c for c in candidates if c.bucket == "aplus"]

    # Tag-aware top-N from watchlist via the shared sort helper (Task 4
    # extracted `_tag_aware_sort_key` so this loop and `_sort_watchlist` in
    # the dashboard view-model are byte-identical by construction).
    # Filter to data-eligible rows first (entry_target + last_close populated)
    # to enforce spec §A "Residual filter-intersection limitation" — a
    # tagged-but-data-incomplete row cannot enter chart-scope.
    data_eligible = [w for w in watchlist if w.entry_target and w.last_close]
    by_ticker = {c.ticker: c for c in candidates}
    from swing.web.view_models.dashboard import (
        _flag_tags as _dashboard_flag_tags,
    )
    from swing.web.view_models.dashboard import _tag_aware_sort_key
    flag_tags = _dashboard_flag_tags(by_ticker)
    tag_aware_sorted = sorted(
        data_eligible,
        key=lambda w: _tag_aware_sort_key(w, flag_tags),
    )
    tag_aware_top_n = tag_aware_sorted[: cfg.pipeline.chart_top_n_watch]

    # Spec §A "Deduplication": linear pass through tiers in precedence order
    # (aplus > open_position > tag_aware_top_n) with ticker canonicalization
    # (.upper()) before being added to `seen` (Codex R1 Minor 3
    # defense-in-depth — production data is already upper-case but the
    # canonicalization makes the dedup robust to a future code path that
    # introduces mixed case).
    seen: set[str] = set()
    targets: list[tuple[str, float, float, str]] = []  # ticker, pivot, stop, source
    for c in aplus:
        t_canon = c.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        targets.append((t_canon, c.pivot or 0.0, c.initial_stop or 0.0, "aplus"))
    for tr in open_trades:
        t_canon = tr.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        # Spec §A "Pivot/stop sourcing": entry_price is the pivot proxy for
        # an open position; current_stop reflects the post-stop_adjust value
        # (Phase 2 stop_adjust event mutates current_stop in place).
        targets.append((
            t_canon, tr.entry_price, tr.current_stop or 0.0, "open_position",
        ))
    for w in tag_aware_top_n:
        t_canon = w.ticker.upper()
        if t_canon in seen:
            continue
        seen.add(t_canon)
        targets.append((
            t_canon, w.entry_target, w.initial_stop_target or 0.0,
            "tag_aware_top_n",
        ))

    # Persist all targets as 'pending' BEFORE per-ticker chart attempts so that
    # mid-step crashes leave a structurally complete record (the run's state
    # will be 'failed' or 'force_cleared'; pending rows are inert because the
    # resolver only reads from state='complete' runs). Single fenced batch.
    if targets:
        with lease.fenced_write() as conn:
            for ticker, _pivot, _stop, source in targets:
                insert_chart_target(
                    conn, pipeline_run_id=lease.run_id,
                    ticker=ticker, source=source, chart_status="pending",
                )

    base = cfg.paths.charts_dir
    staging = StagingDir(base=base, run_id=lease.run_id, artifact_type="charts")
    staging.create()
    out_paths: dict[str, Path] = {}
    # Classifier-summary counters: track classifier outcomes directly. A
    # ticker reaches the classifier iff fetcher.get succeeded (fetcher_failed
    # tickers `continue` before classify_flag is called). The summary's
    # denominator is "classifier attempts" = success + errors, NOT len(targets)
    # — fetcher_failed and chart-render outcomes are unrelated to classifier
    # health (Codex R1 Major 1).
    classifier_success = 0
    classifier_errors = 0
    for ticker, pivot, stop, _source in targets:
        try:
            ohlcv = fetcher.get(ticker, lookback_days=200, as_of_date=None)
        except Exception:
            with lease.fenced_write() as conn:
                update_chart_target_status(
                    conn, pipeline_run_id=lease.run_id, ticker=ticker,
                    chart_status="fetcher_failed",
                )
            continue

        bars_60 = ohlcv.tail(60)
        try:
            classification = classify_flag(bars_60)
            classifier_success += 1
        except Exception as exc:
            log.warning(f"flag_classifier failed for {ticker}: {exc!r}")
            classifier_errors += 1
            classification = FlagClassificationResult(
                detected=False, confidence=0.0, pattern=None,
                pole_start_date=None, pole_end_date=None,
                flag_start_date=None, flag_end_date=None,
                pole_high=None, flag_low=None, pivot=None,
                components={"error": repr(exc)},
            )

        pattern_overlay = PatternOverlay.from_classification(classification)

        path = render_chart(
            ticker=ticker, ohlcv=ohlcv, pivot=pivot, stop=stop,
            output_path=staging.path / f"{ticker}.png",
            pattern_overlay=pattern_overlay,
        )
        if path is not None:
            out_paths[ticker] = path
            chart_status = "ok"
        else:
            # render_chart returns None when the (post-tail) frame has fewer
            # than MIN_BARS rows — the spec §8 deferred "too_few_bars" case.
            chart_status = "too_few_bars"

        # Single fenced write per ticker — chart_status update + classification
        # row commit together so a partial-failure leaves a structurally
        # consistent state.
        with lease.fenced_write() as conn:
            update_chart_target_status(
                conn, pipeline_run_id=lease.run_id, ticker=ticker,
                chart_status=chart_status,
            )
            insert_classification(
                conn, pipeline_run_id=lease.run_id, ticker=ticker,
                result=classification,
                computed_at=_dt.now().isoformat(timespec="seconds"),
            )

    # End-of-step summary. Denominator is classifier attempts (success +
    # error), NOT len(targets) — fetcher_failed tickers never reached the
    # classifier and are not in the classifier-health denominator. Spec §3.3
    # contract: `flag_classifier: {ok}/{total} ok, {errors} errors` where
    # totals are classifier-attempt-scoped (Codex R1 Major 1 fix).
    classifier_attempts = classifier_success + classifier_errors
    log.info(
        f"flag_classifier: {classifier_success}/{classifier_attempts} ok, "
        f"{classifier_errors} errors"
    )
    # Spec §A "Timer-boundary specification": timer ends after the last
    # per-ticker fenced_write for chart_status. promote_staging runs
    # OUTSIDE the timer because it's a separate concern (artifact-promote,
    # not chart-step measured work). Codex R3 Minor 2.
    _walltime_elapsed = time.monotonic() - _walltime_start
    _scope_count = len(targets)
    if _walltime_elapsed > 120.0:
        log.error(
            f"chart-step wall-time exceeded hard budget: "
            f"{_walltime_elapsed:.1f}s > 120s; scope={_scope_count} tickers"
        )
    elif _walltime_elapsed > 60.0:
        log.warning(
            f"chart-step wall-time exceeded soft budget: "
            f"{_walltime_elapsed:.1f}s > 60s; scope={_scope_count} tickers; "
            "consider reducing chart_top_n_watch"
        )
    promote = promote_staging(
        staging=staging, target=base / data_asof,
        lease_token=lease.token, db_path=cfg.paths.db_path,
        manifest_extras={"data_asof_date": data_asof},
    )
    return {t: promote.target_path / f"{t}.png" for t in out_paths}


def _step_export(*, cfg, lease: Lease, eval_run_id: int, action_session,
                  data_asof: str, chart_paths: dict[str, Path]) -> None:
    lease.verify_held()
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.recommendations import list_for_session
    conn = connect(cfg.paths.db_path)
    try:
        candidates = fetch_candidates_for_run(conn, eval_run_id)
        # Tranche C T4 follow-up (adversarial review Major 1): scope export
        # recs to the pipeline's own eval too, otherwise candidates and recs
        # in the briefing can diverge if a re-run pipeline overwrites only
        # the tickers it covered (UNIQUE on action_session_date,ticker,
        # recommendation lets older recs persist for tickers the new eval
        # dropped). Same FK already used for `candidates` above; pass it
        # through here so the briefing is internally consistent.
        recs = list_for_session(
            conn, action_session.isoformat(), evaluation_run_id=eval_run_id,
        )
        watchlist = list_active_watchlist(conn)
        weather = get_latest_for_date(conn, data_asof, ticker=cfg.rs.benchmark_ticker)
        trades = list_open_trades(conn)
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=_exits_via_fills_for_equity(conn),
            cash_movements=list_cash(conn),
        )
    finally:
        conn.close()

    inputs = BriefingInputs(
        action_session_date=action_session.isoformat(),
        data_asof_date=data_asof,
        generated_at=_dt.now().isoformat(timespec="seconds"),
        weather=weather, weather_is_stale=(weather is None),
        equity=equity, open_count=len(trades),
        soft_warn=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        last_pipeline_ts=_dt.now().isoformat(timespec="seconds"),
        pipeline_is_stale=False, current_session_match=True,
        recommendations=recs, open_trades=trades,
        open_trade_advisories={}, open_trade_last_prices={},
        watchlist=watchlist, watchlist_last_prices={},
        candidates_by_ticker={c.ticker: c for c in candidates},
        chart_b64s={t: _b64_chart(p) for t, p in chart_paths.items()},
        near_trigger_above_pct=cfg.near_trigger.above_pct,
        near_trigger_below_pct=cfg.near_trigger.below_pct,
    )
    vm = build_briefing_view_model(inputs)

    base = cfg.paths.exports_dir
    staging = StagingDir(base=base, run_id=lease.run_id, artifact_type="exports")
    staging.create()
    export_briefing(
        vm=vm, out_dir=staging.path,
        chart_files=chart_paths,
        size_cap_kb=cfg.export.size_cap_kb,
        retain_markdown_sibling=cfg.export.retain_markdown_sibling,
    )
    promote_staging(
        staging=staging, target=base / action_session.isoformat(),
        lease_token=lease.token, db_path=cfg.paths.db_path,
        manifest_extras={
            "data_asof_date": data_asof,
            "action_session_date": action_session.isoformat(),
        },
    )

    from swing.rendering.retention import archive_old_exports
    archive_old_exports(
        exports_dir=cfg.paths.exports_dir,
        retention_days=cfg.export.retention_days,
    )


def _step_review_log_cadence(*, lease: Lease) -> None:
    """Idempotent: pre-create one Review_Log row per cadence (daily/weekly/
    monthly) for the prior period, anchored on `last_completed_session(
    datetime.now())`. Quarterly + circuit_breaker schema-supported but no
    pre-create in V1 (locked decision §2.7).

    Anchor is helper-internal — caller cannot supply an as-of-date that
    controls which prior period rows are created (brief §6.2 watch item 5).

    No `cfg` parameter: the function uses `lease.fenced_write()` for the DB
    connection (already cfg-bound at lease-acquire time) — passing cfg would
    duplicate state. R3 Major 1 fix.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from swing.data.repos.review_log import insert_pre_create
    from swing.trades.review import (
        compute_daily_period,
        compute_monthly_period,
        compute_weekly_period,
    )

    now = _dt.now()
    cadence_periods: list[tuple[str, _date, _date]] = [
        ("daily", *compute_daily_period(now)),
        ("weekly", *compute_weekly_period(now)),
        ("monthly", *compute_monthly_period(now)),
    ]
    with lease.fenced_write() as conn:
        for review_type, p_start, p_end in cadence_periods:
            scheduled = (p_end + _td(days=1)).isoformat()
            insert_pre_create(
                conn,
                review_type=review_type,
                period_start=p_start.isoformat(),
                period_end=p_end.isoformat(),
                scheduled_date=scheduled,
            )
