"""Pipeline runner — orchestrates 9 spec §5.1 steps with lease + staging + recovery."""
from __future__ import annotations

import base64
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC
from datetime import date as _date
from datetime import datetime as _dt
from pathlib import Path

from swing.config import Config
from swing.data.backup import do_backup, prune_old_backups, should_backup
from swing.data.db import connect
from swing.data.models import Candidate, EvaluationRun
from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.cash import list_cash
from swing.data.repos.pattern_classifications import insert_classification
from swing.data.repos.pipeline import (
    LeaseRevokedError,
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
from swing.integrations.schwab.auth import (
    construct_authenticated_client,
    resolve_credentials_env_or_prompt,
)
from swing.integrations.schwab.client import (
    SchwabConfigMissingError,
)
from swing.metrics.discrepancies import count_recent_multi_leg_auto_corrections
from swing.pipeline.finviz_schema import reject_csv, validate_csv
from swing.pipeline.finviz_select import AmbiguousInboxError, NoFilesError, select_csv
from swing.pipeline.heartbeat import Heartbeat
from swing.pipeline.lease import (
    ConcurrentRunBlockedError,
    Lease,
    acquire_lease,
)
from swing.pipeline.ohlcv import compute_adr_pct as _compute_adr_pct
from swing.pipeline.ohlcv import compute_smas as _compute_smas
from swing.pipeline.ohlcv import previous_close as _previous_close
from swing.pipeline.recovery import sweep_stale_artifacts
from swing.pipeline.staging import StagingDir, promote_staging
from swing.prices import PriceFetcher
from swing.recommendations.build import BuildContext, build_recommendations
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.charts import (
    ChartingUnavailableError,
    PatternOverlay,
    render_chart,
)
from swing.rendering.exporter import export_briefing
from swing.rendering.view_models import AdvisorySuggestionVM
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
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


def _construct_pipeline_schwab_client(cfg) -> object | None:
    """Construct a `schwabdev.Client` for pipeline-internal use from env vars.

    Phase 12 Sub-bundle A T-A.3 — env-var-driven construction. Reads
    ``SCHWAB_CLIENT_ID`` + ``SCHWAB_CLIENT_SECRET`` via the public T-A.1
    helper ``resolve_credentials_env_or_prompt(cfg, env, allow_prompt=False)``.
    The pipeline cannot prompt (no TTY), so the helper is invoked with
    ``allow_prompt=False`` per T-A.1 contract.

    Three return paths:

      * Both env vars absent → ``(None, None)`` from the helper →
        return ``None`` SILENTLY (no log noise; preserves V1 graceful-
        skip path for operators not using env-var integration).
      * Partial env vars (one set, one absent / empty / whitespace-only)
        → helper raises ``SchwabConfigMissingError`` → caught here,
        return ``None`` + emit a single ``WARNING`` line naming
        ``CLIENT_ID=<present|absent>`` / ``CLIENT_SECRET=<present|absent>``
        so operators can diagnose misconfiguration. Pipeline does NOT crash.
      * Both env vars set → invoke ``construct_authenticated_client``;
        return the live client on success. On construction failure
        (``SchwabApiError`` / ``SchwabAuthError`` / ``SchwabConfigMissingError``
        / etc.) → catch + return ``None`` + emit a single ``WARNING``
        line. V1 graceful-degradation: a stale tokens DB or rotation
        failure must NOT crash the whole pipeline run.

    When a non-``None`` client IS returned, the ladder hooks installed by
    ``_install_pipeline_marketdata_caches`` route through the T-C.1 wrappers
    with ``surface='pipeline'``. When ``None``, the ladder gracefully falls
    through to yfinance (per T-C.3 test #15) and zero ``schwab_api_calls``
    rows are written.

    Tests can either set the env vars + monkeypatch
    ``construct_authenticated_client`` (mirror of integration tests) OR
    leave env vars absent (silent-skip mode). Pre-T-A.3 monkeypatching
    of this function itself remains supported — callers can still patch
    ``_construct_pipeline_schwab_client`` directly when they want to
    inject a MagicMock without going through env vars.

    Sandbox short-circuit lives inside the ladder layer (per T-C.3
    §H.6.1 LOCK); this helper unconditionally constructs the Client
    regardless of env. The ladder layer does the env check + skips audit
    + yfinance-fall-through when ``cfg.integrations.schwab.environment !=
    'production'``.
    """
    environment = cfg.integrations.schwab.environment
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError:
        id_present = os.environ.get("SCHWAB_CLIENT_ID") is not None
        secret_present = os.environ.get("SCHWAB_CLIENT_SECRET") is not None
        log.warning(
            "Pipeline schwab_client construction skipped: env-var credentials "
            "incomplete (CLIENT_ID=%s; CLIENT_SECRET=%s). Pipeline will "
            "silent-skip Schwab steps.",
            "present" if id_present else "absent",
            "present" if secret_present else "absent",
        )
        return None

    if client_id is None or client_secret is None:
        # Both env vars genuinely absent — V1 silent-skip path. No log noise
        # so operators not using env-var integration see a clean pipeline run.
        return None

    try:
        return construct_authenticated_client(
            cfg, environment,
            client_id=client_id, client_secret=client_secret,
        )
    except Exception as exc:  # noqa: BLE001 — V1 graceful-degradation safety boundary
        # Codex R1 Major fix (2026-05-15): pre-fix this caught only
        # `(SchwabApiError, SchwabConfigMissingError)`, but
        # `construct_authenticated_client` ultimately invokes
        # `schwabdev.Client(...)` which can raise arbitrary unwrapped
        # exceptions — `OSError` (tokens DB filesystem failure),
        # `sqlite3.DatabaseError` (tokens DB corruption), `RuntimeError`
        # or `ValueError` from schwabdev-internal validation,
        # `ConnectionError`/`TimeoutError` from network preflight, etc.
        # The pipeline boundary is a SAFETY boundary, not a typed-correctness
        # boundary; the V1 graceful-degradation contract demands the
        # pipeline never crash on Schwab construction issues. Widen to
        # bare `Exception` so every construction failure surfaces as a
        # single silent-skip WARNING.
        #
        # Message is redacted via `_redacted_excerpt` before logging
        # because the underlying exception text from schwabdev /
        # urllib3 / sqlite3 may contain credentials or token-shaped
        # substrings (Layer-0 + Layer-1 redactor catches registered
        # secrets + heuristic regex on hex/base64 sequences).
        from swing.integrations.schwab.auth import _redacted_excerpt
        log.warning(
            "Pipeline schwab_client construction failed (%s: %s). "
            "Pipeline will silent-skip Schwab steps.",
            type(exc).__name__,
            _redacted_excerpt(exc),
        )
        return None


def _install_pipeline_marketdata_caches(
    cfg, schwab_client: object | None, pipeline_run_id: int | None,
) -> tuple[object | None, object | None]:
    """Construct PriceCache + OhlcvCache + install Schwab-market-data ladder hooks.

    Per Phase 11 Sub-bundle C T-C.6 dispatch brief §0.5 pre-emption #5 +
    plan §H.6: when the operator has tokens for ``cfg.integrations.schwab.
    environment`` AND ``cfg.integrations.schwab.marketdata_ladder_enabled``
    is True, route pipeline-internal quote + window fetches through the
    ladder so the audit table records ``surface='pipeline'`` rows.

    Algorithm:
      1. If ``schwab_client is None`` → return (None, None) (no caches
         constructed; pipeline retains existing PriceFetcher / yfinance
         path; ZERO ``schwab_api_calls`` rows written).
      2. Otherwise: construct ``PriceCache(cfg)`` + ``OhlcvCache(cfg)``;
         install ladder hooks via ``set_ladder_fetcher`` /
         ``set_ladder_bars_fetcher``; each hook closes over
         ``(cfg, schwab_client, pipeline_run_id, surface='pipeline')`` +
         opens a fresh ``conn`` per invocation (audit-service wrappers
         require ``conn``).

    Sandbox short-circuit lives INSIDE the ladder (per T-C.3 §H.6.1 LOCK);
    this helper unconditionally installs the hook regardless of env. The
    ladder layer does the env check + falls through to yfinance with
    ``provider='yfinance'`` + ZERO audit rows when env != 'production'.

    Single-Client-instance discipline (dispatch brief §0.5 pre-emption #6):
    the same ``schwab_client`` is shared by both PriceCache + OhlcvCache
    via captured closures. No duplicate construction.

    Returns:
        ``(price_cache, ohlcv_cache)`` — both ``None`` when no client.

    Consumer surfaces (post-Phase-13 T1.SB0): PriceCache is consumed by
    ``_step_evaluate`` (open-trade-ticker warm); OhlcvCache is consumed by
    ``_step_charts`` via ``ohlcv_cache.get_or_fetch(...)`` for chart-target
    OHLCV (closes the Phase 11 Sub-bundle C R1 M#5 V1 deferral). Both caches
    share the same ``schwab_client`` via captured closures.
    """
    if schwab_client is None:
        return None, None

    from swing.integrations.schwab.marketdata_ladder import (
        fetch_quote_via_ladder,
        fetch_window_via_ladder,
    )
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.web.price_cache import PriceCache

    price_cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)

    def _yf_quote_fallback(ticker: str):
        # Best-effort yfinance fallback for the ladder. The cache layer
        # absorbs errors; if this raises, the ladder catches + the cache
        # falls back to last_close via its own machinery. The ladder
        # expects a PriceSnapshot return per T-C.3 contract.
        from datetime import datetime as _dt2

        from swing.web.price_cache import PriceSnapshot
        price = price_cache._fetch_live_price(ticker)
        return PriceSnapshot(
            ticker=ticker, price=price, asof=_dt2.now(),
            is_stale=False, source="live", provider="yfinance",
        )

    def _quote_hook(ticker: str) -> tuple[float, str]:
        # PriceCache `set_ladder_fetcher` contract: (price, provider).
        # The cache stamps `source='live'` itself; we only return the
        # numeric price + provider tag.
        conn = connect(cfg.paths.db_path)
        try:
            snap, provider_tag = fetch_quote_via_ladder(
                ticker,
                cfg=cfg,
                schwab_client=schwab_client,
                yfinance_fallback_fn=_yf_quote_fallback,
                conn=conn,
                surface="pipeline",
                pipeline_run_id=pipeline_run_id,
            )
        finally:
            conn.close()
        return (snap.price, provider_tag)

    def _yf_window_fallback(ticker: str, start, end):
        # Window-ladder yfinance fallback. The ladder expects a window-
        # shaped object; the cache's bars fetcher contract returns the
        # bars frame + provider.
        #
        # Phase 13 T1.SB0 (Codex R3 Major #1 fix 2026-05-18): return FULL
        # archive history via `read_or_fetch_archive` directly, NOT
        # `fetch_daily_bars(n_bars=60)`. Pre-fix the 60-row truncation
        # silently capped the chart-step bars-worker window at 60 rows
        # — `OhlcvCache.get_or_fetch._fetch_bars_window` slices to
        # `window_days=200` (calendar) AFTER the hook, so it could not
        # recover history past the 60-bar cap. Bundle worker (60-bar
        # SMA50 requirement) is unaffected: it tails the full history
        # internally via `compute_smas` rolling. Bars worker now gets
        # ~1260 business days (`archive_history_days` default), more
        # than sufficient for any V1 chart-window requirement.
        bars = read_or_fetch_archive(
            ticker,
            end_date=last_completed_session(_dt.now()),
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
        )
        return bars

    def _bars_hook(ticker: str):
        # OhlcvCache `set_ladder_bars_fetcher` contract:
        # (bars_df_or_none, provider). Window-ladder returns
        # (window_or_bars, provider_tag); we pass through verbatim since
        # both sides accept a pandas-DataFrame-or-None shape.
        #
        # Phase 13 T1.SB0 gate-fix (T-GF2.2): pass EXPLICIT daily-bar
        # period/frequency kwargs. Without them, schwabdev defaults to
        # periodType=day, period=10, frequencyType=minute, frequency=1 -
        # returning ~3000 1-minute intraday candles per ticker instead of
        # daily bars (Schwab API table at
        # `reference/schwabdev/api-calls.md:425-435`). The intraday output
        # contaminates the chart-step render with duplicate-DatetimeIndex
        # timestamps + per-minute volume scale + 00:00 x-axis labels - the
        # operator-witnessed S3 regression 2026-05-18 PM (CVGI). Recon at
        # `docs/phase13-t1-sb0-gate-fix-recon.md` section 2. Selected
        # daily-window tuple `(year, 5, daily, 1)` matches
        # `cfg.archive.archive_history_days` ~ 1260 trading days ~ 5y. The
        # CLI verify path at `swing/cli_schwab.py:1100-1111` uses
        # `(month, 1, daily, 1)` - both are valid daily-bar specs; the
        # year/5 choice maximizes archive coverage in one call so the
        # Shape A parquet's first write captures full history.
        conn = connect(cfg.paths.db_path)
        try:
            window, provider_tag = fetch_window_via_ladder(
                ticker,
                start=None, end=None,
                cfg=cfg,
                schwab_client=schwab_client,
                yfinance_fallback_fn=_yf_window_fallback,
                conn=conn,
                surface="pipeline",
                pipeline_run_id=pipeline_run_id,
                period_type="year",
                period=5,
                frequency_type="daily",
                frequency=1,
            )
        finally:
            conn.close()
        # When provider='yfinance', `window` is whatever the yfinance
        # fallback returned (bars DataFrame). When provider='schwab_api',
        # `window` is a SchwabPriceHistoryWindow — convert to bars-shape
        # via the T-C.1 mapper's `to_dataframe()` helper.
        if provider_tag == "schwab_api" and hasattr(window, "to_dataframe"):
            bars = window.to_dataframe()
        else:
            bars = window
        return (bars, provider_tag)

    price_cache.set_ladder_fetcher(_quote_hook)
    ohlcv_cache.set_ladder_bars_fetcher(_bars_hook)

    return price_cache, ohlcv_cache


def _warm_pipeline_marketdata(
    *,
    cfg,
    price_cache,
    held_tickers: list[str],
) -> None:
    """Warm the marketdata ladder for open-trade tickers under pipeline lease.

    Phase 11 Sub-bundle C T-C.6 — invoke ``PriceCache.get(ticker)`` for each
    open-trade ticker so the ladder fires + writes ``surface='pipeline'``
    audit rows under production. Sandbox short-circuit at the ladder layer
    means ZERO ``schwab_api_calls`` rows are written under
    ``cfg.environment='sandbox'``.

    Pipeline-internal call sites with no installed cache (``price_cache=None``
    when no schwab_client could be constructed) are no-ops — the existing
    yfinance-only PriceFetcher path continues to populate
    ``candidates.close`` per the existing _step_evaluate semantics.

    Cache TTL provides the test-#4 hit-rate property: invoking this twice
    within the cache TTL (`cfg.web.price_cache_ttl_seconds`, default 120s)
    causes the second call to hit cache for already-fetched tickers, so the
    ladder fires fewer times on the second run.

    Failures here MUST NOT abort the pipeline — best-effort. The PriceCache's
    own machinery falls back to last-close on per-ticker failure; this
    wrapper additionally catches any framework-level exception.
    """
    if price_cache is None or not held_tickers:
        return
    for ticker in held_tickers:
        try:
            # PriceCache.get hits the ladder hook (which uses surface='pipeline')
            # on a miss; on a hit (TTL-warm) returns immediately without
            # invoking the ladder.
            price_cache.get(ticker)
        except Exception as exc:
            log.warning(
                "pipeline marketdata warm failed for %s: %s",
                ticker, type(exc).__name__,
            )


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
    except ConcurrentRunBlockedError as exc:
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
        # Finviz selection/validation under the lease. Ensure the inbox
        # dir exists (first-run bootstrap; mirrors `_step_finviz_fetch`
        # mkdir at L1832 per Codex R1 Major-2 fix family). Without this,
        # `select_csv` on a non-existent dir raises a misleading
        # `NoFilesError("No CSV files in <dir>")` because Path.glob on
        # a missing directory returns empty silently.
        try:
            cfg.paths.finviz_inbox_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.error("Finviz inbox dir create failed: %s", exc)
            lease.release(state="failed", error_message=f"finviz inbox mkdir: {exc}")
            return RunResult(
                run_id=lease.run_id,
                state="failed",
                error_message=f"finviz inbox mkdir: {exc}",
            )
        # Phase 12.5 finviz-inbox-auto-fetch-fix: split the catch so an empty
        # inbox (NoFilesError) triggers ONE inline auto-fetch attempt via
        # ``_step_finviz_fetch`` BEFORE bailing — fresh worktrees always start
        # empty and previously crashed here before site-2's pipeline-step ever
        # ran. AmbiguousInboxError stays fail-fast (operator manual-override
        # misconfiguration; auto-fetch wouldn't help). Site-2 honors the
        # ``finviz_fetched_inline`` flag to avoid a double-fire on the same
        # run (which would write 2 ``finviz_api_calls`` audit rows).
        finviz_fetched_inline = False
        try:
            csv_path = select_csv(cfg.paths.finviz_inbox_dir)
        except AmbiguousInboxError as exc:
            log.error("Finviz inbox: %s", exc)
            lease.release(state="failed", error_message=str(exc))
            return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))
        except NoFilesError as exc_initial:
            log.info(
                "Finviz inbox empty; attempting inline auto-fetch via "
                "_step_finviz_fetch (one attempt; no exponential retry)"
            )
            # Codex R2 Major #1: snapshot MAX(call_id) BEFORE the inline
            # _step_finviz_fetch call so the follow-up diagnostic read
            # (in the retry-failed path) is causally scoped to rows
            # inserted by THIS call — eliminates the R1 "latest globally"
            # misattribution risk under multi-surface concurrency.
            pre_call_max_id = _read_finviz_call_max_id_snapshot(cfg)
            # Codex R1 Major #3: mark the active step BEFORE the inline
            # _step_finviz_fetch call so ``swing pipeline status`` /
            # stale-run diagnosis attributes the API call to the correct
            # step. The site-2 ``lease.step("finviz_fetch")`` at L638 still
            # fires (lease-step tracking is the same UPDATE; idempotent).
            lease.step("finviz_fetch")
            try:
                _step_finviz_fetch(cfg=cfg, lease=lease)
                finviz_fetched_inline = True
            except LeaseRevokedError:
                raise
            except Exception as exc_fetch:
                msg = (
                    f"inbox empty + auto-fetch failed: "
                    f"{type(exc_fetch).__name__}: {exc_fetch} "
                    f"(initial: {exc_initial})"
                )
                log.error("Finviz inbox auto-fetch: %s", msg)
                lease.release(state="failed", error_message=msg)
                return RunResult(
                    run_id=lease.run_id, state="failed", error_message=msg,
                )
            try:
                csv_path = select_csv(cfg.paths.finviz_inbox_dir)
            except (NoFilesError, AmbiguousInboxError) as exc_retry:
                # Codex R1 Major #1 + R2 Major #1: _step_finviz_fetch does
                # NOT raise for expected Finviz API failures (missing token,
                # auth, rate limit, schema parity) — _finviz_fetch_core
                # returns status='error' + the audit row is inserted but
                # the function returns normally. Surface that audit row's
                # status + error_message in the combined report so the
                # operator sees the real "why" rather than a redundant
                # "No CSV files". The diagnostic read is causally scoped
                # via the pre-call_id snapshot (R2 M#1).
                fetch_status, fetch_err = _read_latest_finviz_call_diagnostic(
                    cfg, after_call_id=pre_call_max_id,
                )
                # Codex R2 Minor #2 + R3 Minor #2 defenses: cap the
                # embedded error to 512 chars to bound combined-message
                # size, and collapse embedded newlines/carriage-returns
                # to single spaces so the combined message stays on one
                # log line (operator scan-ability). The source-of-truth
                # audit row itself already truncates at 1024 + is
                # untouched.
                if fetch_err:
                    fetch_err = fetch_err.replace("\r", " ").replace("\n", " ")
                    if len(fetch_err) > 512:
                        fetch_err = fetch_err[:512] + "..."
                fetch_detail = (
                    f" [auto-fetch audit: status={fetch_status!r}"
                    + (f", error={fetch_err}" if fetch_err else "")
                    + "]"
                    if fetch_status is not None
                    else ""
                )
                msg = (
                    f"inbox empty + auto-fetch did not produce a CSV: "
                    f"{exc_retry} (initial: {exc_initial}){fetch_detail}"
                )
                log.error("Finviz inbox auto-fetch: %s", msg)
                lease.release(state="failed", error_message=msg)
                return RunResult(
                    run_id=lease.run_id, state="failed", error_message=msg,
                )

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
                raise LeaseRevokedError(
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
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning("weather failed: %s", exc)
                lease.status(weather_status="failed")

            lease.step("finviz_fetch")
            # Phase 12.5 finviz-inbox-auto-fetch-fix: ``finviz_fetched_inline``
            # is True iff site-1's NoFilesError-retry path ran
            # ``_step_finviz_fetch`` already. Skip the body here to avoid
            # double-firing (would persist 2 ``finviz_api_calls`` audit rows
            # for one pipeline run). ``lease.step("finviz_fetch")`` still
            # fires above for defense-in-depth lease tracking.
            if finviz_fetched_inline:
                log.info(
                    "finviz_fetch step skipped (already ran inline "
                    "pre-select_csv on empty inbox)"
                )
            else:
                try:
                    _step_finviz_fetch(cfg=cfg, lease=lease)
                except LeaseRevokedError:
                    raise
                except Exception as exc:
                    # _step_finviz_fetch is itself error-tolerant; this catches
                    # programming errors only (KeyError, etc.). Pipeline must
                    # not abort here either — preserve fallback semantics.
                    log.warning("finviz_fetch programming error (continuing): %s", exc)

            # Phase 11 Sub-bundle C T-C.6 — construct + install market-data
            # ladder hooks for pipeline-internal use. Pipeline cannot prompt
            # for credentials, so `_construct_pipeline_schwab_client` returns
            # None by default (matches `_step_schwab_snapshot` precedent);
            # tests monkeypatch the constructor to inject a mock client. When
            # client is None → caches are None → `_step_evaluate` warm is a
            # no-op + the existing PriceFetcher/yfinance path remains
            # authoritative for candidates.close. When client is provided,
            # the ladder fires under production env + writes `surface=
            # 'pipeline'` audit rows; sandbox short-circuit lives in the
            # ladder layer per T-C.3 LOCK.
            #
            # Phase 13 T1.SB0 (plan §G.0) — closes the Phase 11 Sub-bundle C
            # R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral by wiring `ohlcv_cache`
            # into `_step_charts`. When `_install_pipeline_marketdata_caches`
            # returns `None` (no Schwab client), a ladder-less `OhlcvCache`
            # is constructed here so `_step_charts` has a uniform consumer
            # surface; the ladder-less cache falls through to
            # `read_or_fetch_archive` directly (identical shape to the
            # legacy `PriceFetcher.get` path — verified by the T-T1.SB0.2
            # shape-parity test).
            schwab_client = _construct_pipeline_schwab_client(cfg)
            price_cache, ohlcv_cache = _install_pipeline_marketdata_caches(
                cfg, schwab_client, pipeline_run_id=lease.run_id,
            )
            if ohlcv_cache is None:
                from swing.web.ohlcv_cache import OhlcvCache
                ohlcv_cache = OhlcvCache(cfg)

            lease.step("evaluate")
            try:
                eval_run_id = _step_evaluate(
                    cfg=cfg, fetcher=fetcher, csv_path=csv_path,
                    universe=universe, universe_hash=universe_hash,
                    run_now=run_now, action_session=action_session,
                    lease=lease,
                    price_cache=price_cache,
                )
                lease.status(evaluation_status="ok")
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.error("evaluation failed: %s", exc)
                lease.status(evaluation_status="failed")
                lease.release(state="failed", error_message=str(exc))
                return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))

            lease.step("daily_management")
            try:
                _step_daily_management(
                    lease=lease, run_now=run_now, eval_run_id=eval_run_id,
                    archive_history_days=cfg.archive.archive_history_days,
                    ohlcv_archive_dir=cfg.paths.prices_cache_dir,
                )
            except LeaseRevokedError:
                raise
            except Exception as exc:
                # Cadence-step semantics: per-trade failures are already
                # logged + swallowed inside _step_daily_management. This
                # catches programming errors (KeyError, ImportError, etc.)
                # — pipeline must continue regardless.
                log.warning(
                    "daily_management step programming error (continuing): %s",
                    exc,
                )

            lease.step("watchlist")
            try:
                _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                                data_asof_date=lease_data_asof(cfg, lease),
                                lease=lease)
                lease.status(watchlist_status="ok")
            except LeaseRevokedError:
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
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning("recommendations failed: %s", exc)
                lease.status(recommendations_status="failed")

            # Phase 13 T2.SB3 (plan section G.4 T-A.3.6) — pattern detect step.
            # Recon at docs/phase13-t2-sb3-recon.md section 2 binds the
            # insertion point: AFTER _step_recommendations + BEFORE the
            # Schwab snapshot block. Best-effort failure shape mirrors
            # _step_watchlist / _step_recommendations / _step_charts.
            lease.step("pattern_detect")
            try:
                _step_pattern_detect(
                    cfg=cfg,
                    lease=lease,
                    eval_run_id=eval_run_id,
                    ohlcv_cache=ohlcv_cache,
                )
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning("pattern_detect failed: %s", exc)

            # Phase 11 Sub-bundle B (T-B.3 + T-B.4 + Codex R1 M#1 + R2 M#1 +
            # R3 M#1 + M#2 fix) — Schwab snapshot + orders pipeline steps
            # per plan §H.4.3 ordering: AFTER _step_recommendations, BEFORE
            # _step_charts. Both are failure-tolerant per plan §3.4.4.
            #
            # Pipeline-internal use passes client=None — the step path
            # falls through to a silent-skip (log only, NO audit row) per
            # the R2 M#1 + R3 M#1 + M#2 disposition to avoid polluting
            # degraded-health surfaces with persistent 'error' rows on
            # every nightly run. V1 design point: pipeline-internal
            # Schwab fetching is best-effort + opt-in via the `swing
            # schwab fetch` CLI surface as the primary operator entry
            # point. Bundle D's status surface uses the lease.step()
            # breadcrumb name `schwab_snapshot` / `schwab_orders` to
            # surface "step executed but silent-skipped". V2 adds a
            # dedicated lease status column.
            lease.step("schwab_snapshot")
            try:
                from swing.integrations.schwab.pipeline_steps import (
                    _step_schwab_snapshot,
                )
                # Phase 12 Sub-bundle A T-A.3 — pass the env-var-constructed
                # schwab_client (from L640) instead of hardcoded None. When env
                # vars absent → schwab_client is None → step short-circuits via
                # the existing client=None silent-skip path (per Sub-bundle B
                # M#1 surface-aware advisory pattern). When env vars present →
                # step actually fires + writes audit + domain rows with
                # surface='pipeline'. Closes the T-A.3 acceptance criterion #4
                # gap that orchestrator-inline gate-fix caught at S5.
                _conn = connect(cfg.paths.db_path)
                try:
                    _step_schwab_snapshot(
                        _conn, cfg, pipeline_run_id=lease.run_id,
                        client=schwab_client, surface="pipeline",
                    )
                finally:
                    _conn.close()
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning(
                    "schwab_snapshot failed (continuing pipeline): %s",
                    type(exc).__name__,
                )

            lease.step("schwab_orders")
            try:
                from swing.integrations.schwab.pipeline_steps import (
                    _step_schwab_orders,
                )
                # T-A.3 same fix family — wire schwab_client through.
                _conn = connect(cfg.paths.db_path)
                try:
                    _step_schwab_orders(
                        _conn, cfg, pipeline_run_id=lease.run_id,
                        client=schwab_client, surface="pipeline",
                    )
                finally:
                    _conn.close()
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning(
                    "schwab_orders failed (continuing pipeline): %s",
                    type(exc).__name__,
                )

            lease.step("charts")
            chart_paths: dict[str, Path] = {}
            try:
                chart_paths = _step_charts(
                    cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                    data_asof=lease_data_asof(cfg, lease),
                    ohlcv_cache=ohlcv_cache,
                )
                lease.status(charts_status="ok")
            except LeaseRevokedError:
                raise
            except ChartingUnavailableError:
                lease.status(charts_status="skipped")
            except Exception as exc:
                log.warning("charts failed: %s", exc)
                lease.status(charts_status="failed")

            lease.step("export")
            try:
                _step_export(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                             action_session=action_session,
                             data_asof=lease_data_asof(cfg, lease),
                             chart_paths=chart_paths,
                             fetcher=fetcher)
                lease.status(export_status="ok")
            except LeaseRevokedError:
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
        except LeaseRevokedError as exc:
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
    price_cache=None,
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

    # Phase 11 Sub-bundle C T-C.6 — invoke the market-data ladder for each
    # open-trade ticker via the (optional) installed PriceCache. When
    # `price_cache is None` (no schwab_client constructed), this is a no-op
    # and the existing PriceFetcher / yfinance path continues to populate
    # candidates.close downstream. When the cache IS installed AND
    # env='production' AND ladder_enabled=True, the ladder fires + writes
    # `surface='pipeline'` audit rows. Sandbox short-circuit at ladder
    # layer → ZERO audit rows. NO new pipeline step; NO step-ordering
    # change; minimal additive call at the existing held_tickers boundary.
    _warm_pipeline_marketdata(
        cfg=cfg, price_cache=price_cache, held_tickers=held_tickers,
    )

    spy_return = 0.0
    spy_df = fetcher.get(cfg.rs.benchmark_ticker, lookback_days=365, as_of_date=None)
    spy_closes = spy_df["Close"]
    weeks = cfg.rs.horizon_weeks
    if len(spy_closes) > weeks * 5:
        bars = weeks * 5
        spy_return = float((spy_closes.iloc[-1] / spy_closes.iloc[-bars - 1]) - 1)

    returns_12w: dict[str, float] = {}
    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
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
    data_asof = max(max_dates).date() if max_dates else last_completed_session(run_now)

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


# ---------------------------------------------------------------------------
# Phase 13 T2.SB3 (plan section G.4 T-A.3.6) — pattern detect step
# ---------------------------------------------------------------------------

# 3 V1 detectors run in deterministic order per recon section 3
# (vcp -> flat_base -> cup_with_handle). Wired as a tuple so iteration
# order is stable across runs (recon section 3 forbids `set` iteration).
def _pattern_detect_registry():
    """Return [(detector_callable, pattern_class, version_str), ...].

    Imported lazily to keep runner module import cheap when pattern
    detection is skipped (zero candidates / cfg-disabled future flag).
    """
    from swing.patterns.cup_with_handle import (
        DETECTOR_VERSION as CUP_VERSION,
    )
    from swing.patterns.cup_with_handle import detect_cup_with_handle
    from swing.patterns.flat_base import (
        DETECTOR_VERSION as FLAT_VERSION,
    )
    from swing.patterns.flat_base import detect_flat_base
    from swing.patterns.vcp import DETECTOR_VERSION as VCP_VERSION
    from swing.patterns.vcp import detect_vcp

    return (
        (detect_vcp, "vcp", VCP_VERSION),
        (detect_flat_base, "flat_base", FLAT_VERSION),
        (detect_cup_with_handle, "cup_with_handle", CUP_VERSION),
    )


def _resolve_eval_run_action_session_date(
    *,
    cfg,
    lease: Lease,
    eval_run_id: int,
):
    """Return the eval_run's ``action_session_date`` (as ``datetime.date``).

    Codex R1 Major #2: detectors require a canonical run-anchored
    asof_date for ``current_stage`` lookups, NOT the wall-clock now()
    which can leak future evaluation_runs into the lookup window.

    Resolution: read ``evaluation_runs.action_session_date`` for
    ``eval_run_id``. Falls back to today's date only if the row cannot
    be read (defensive; logged WARNING).
    """
    from datetime import date as _date_cls
    from datetime import datetime as _dt_inner

    iso: str | None = None
    read_conn = connect(cfg.paths.db_path) if cfg is not None else None
    try:
        if read_conn is not None:
            row = read_conn.execute(
                "SELECT action_session_date FROM evaluation_runs WHERE id = ?",
                (eval_run_id,),
            ).fetchone()
        else:
            with lease.fenced_write() as _conn:
                row = _conn.execute(
                    "SELECT action_session_date FROM evaluation_runs "
                    "WHERE id = ?",
                    (eval_run_id,),
                ).fetchone()
        if row is not None and row[0] is not None:
            iso = str(row[0])
    finally:
        if read_conn is not None:
            read_conn.close()

    if iso is None:
        log.warning(
            "pattern_detect: evaluation_runs row not found for "
            "eval_run_id=%d; falling back to wall-clock asof_date",
            eval_run_id,
        )
        return _dt_inner.now(UTC).date()
    try:
        return _date_cls.fromisoformat(iso)
    except ValueError:
        log.warning(
            "pattern_detect: evaluation_runs.action_session_date "
            "unparseable (%r) for eval_run_id=%d; falling back to "
            "wall-clock asof_date",
            iso,
            eval_run_id,
        )
        return _dt_inner.now(UTC).date()


def _step_pattern_detect(
    *,
    cfg,
    lease: Lease,
    eval_run_id: int,
    ohlcv_cache,
) -> None:
    """Run 3 V1 geometric detectors over the Stage-2-filtered candidate pool.

    Per recon section 1-9 (docs/phase13-t2-sb3-recon.md):
    - Pool predicate: candidates.bucket == 'aplus' (Stage-2 + RS-rank-filtered).
    - Per-ticker: fetch bars via `ohlcv_cache.get_or_fetch`; generate
      candidate windows (zigzag_pivot mode); run all 3 detectors on each
      window's evidence-emit; write one `pattern_evaluations` row per
      (pipeline_run_id, ticker, pattern_class) tuple.
    - SELECT-then-INSERT idempotency (LOCK L3 forbids INSERT OR REPLACE).
    - pipeline_run_id := lease.run_id (NOT eval_run_id) per recon section 8.
    - NO sandbox gating (recon section 6): pattern_evaluations is an
      internal-derivation surface; bars-source ladder already handles sandbox.
    - Per-detector failures are isolated + logged WARNING; the step
      continues (recon section 4.4).
    """
    import dataclasses
    import json as _json
    from datetime import datetime as _dt_inner

    from swing.data.models import PatternEvaluation
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.pattern_evaluations import insert_evaluation
    from swing.patterns.drift_logging import capture_feature_distribution
    from swing.patterns.foundation import generate_candidate_windows

    pipeline_run_id = lease.run_id

    # Read phase (no fence -- idempotent SELECT).
    read_conn = connect(cfg.paths.db_path) if cfg is not None else None
    try:
        if read_conn is not None:
            candidates = fetch_candidates_for_run(read_conn, eval_run_id)
        else:
            # Test-stub path: pull candidates through the lease's connection
            # (single-connection in-memory test fixtures don't have a cfg).
            with lease.fenced_write() as _read_via_lease:
                candidates = fetch_candidates_for_run(
                    _read_via_lease, eval_run_id
                )
    finally:
        if read_conn is not None:
            read_conn.close()

    # Pool predicate: Stage-2-filtered + RS-rank-filtered candidates =
    # aplus bucket (mirrors _step_recommendations line 1211).
    aplus_tickers: list[str] = [
        c.ticker for c in candidates if c.bucket == "aplus"
    ]

    if not aplus_tickers:
        log.info(
            "pattern_detect: no candidate windows -- zero aplus tickers; "
            "skipping (no writes)"
        )
        return

    detectors = _pattern_detect_registry()

    # Codex R1 Major #2: derive asof_date from the eval_run's OWN
    # action_session_date (the run's canonical session anchor), NOT the
    # wall-clock now(). The wall-clock could leak FUTURE evaluation_runs
    # rows into ``current_stage`` lookups (e.g. operator backfilling an
    # earlier run while a later run already exists in the DB).
    asof_run = _resolve_eval_run_action_session_date(
        cfg=cfg, lease=lease, eval_run_id=eval_run_id
    )

    rows_written = 0
    rows_skipped_idempotent = 0

    # Universe context for FeatureDistributionLog (per spec section D.7).
    # Codex R1 Major #3: ``composite_scores`` is populated via a TWO-PASS
    # architecture (Option A) -- pass 1 collects scores; pass 2 emits rows
    # whose feature_distribution_log_json carries the FULL universe
    # histogram. Pass 1 is read-only (no DB writes); pass 2 owns writes.
    universe_context: dict = {
        "universe_size": len(aplus_tickers),
        "stage_2_pass_rate": 1.0,  # aplus bucket implies Stage 2 pass.
        "rs_rank_distribution": {},
        "verdict_counts_per_pattern_class": {},
        "smoothing_params": {},
        "extrema_density_per_session": 0.0,
        "composite_scores": [],
    }

    # Pass 1 + Pass 2 share the lease-fenced connection. Pass 1 runs the
    # detectors + collects evidence; pass 2 serializes + INSERTs against
    # the universe-wide histogram.
    with lease.fenced_write() as conn:
        # ------------------------------------------------------------------
        # Pass 1: detector invocations + composite_scores accumulation.
        # ------------------------------------------------------------------
        # Each per-(ticker, pattern_class) entry collects (window,
        # evidence, version_str, composite_score, criteria_pass) for
        # pass 2 to consume.
        emit_queue: list[
            tuple[str, str, str, object, object, float]
        ] = []  # (ticker, pattern_class, version_str, window, evidence, score)

        for ticker in aplus_tickers:
            # Fetch bars (per-ticker failure: log + continue).
            try:
                bars = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)
            except Exception as exc:
                log.warning(
                    "pattern_detect: bars fetch failed for %s "
                    "(continuing): %s",
                    ticker,
                    exc,
                )
                continue

            # Generate candidate windows (zigzag_pivot anchor mode for V1;
            # detectors backward-slice for non-zigzag modes per recon
            # section 5).
            try:
                windows = generate_candidate_windows(
                    bars,
                    "zigzag_pivot",
                    ticker=ticker,
                    timeframe="daily",
                )
            except Exception as exc:
                log.warning(
                    "pattern_detect: generate_candidate_windows failed "
                    "for %s (continuing): %s",
                    ticker,
                    exc,
                )
                continue

            if not windows:
                log.info(
                    "pattern_detect: no candidate windows generated for "
                    "%s; skipping",
                    ticker,
                )
                continue

            # V1: use the LAST (most-recent-anchor) window per ticker so
            # we emit one verdict per (ticker, pattern_class) tuple,
            # honoring the unique-index constraint. The candidate
            # generator may emit multiple historical anchors but the
            # PER-pipeline-run verdict is the most-recent. V2 may
            # multi-anchor + UPDATE-in-place.
            window = windows[-1]

            for detector_fn, pattern_class, version_str in detectors:
                # Idempotency check: skip if a row already exists for this
                # (pipeline_run_id, ticker, pattern_class) tuple. Recon
                # section 4.2 -- LOCK L3 forbids INSERT OR REPLACE.
                existing = conn.execute(
                    "SELECT id FROM pattern_evaluations "
                    "WHERE pipeline_run_id = ? AND ticker = ? "
                    "AND pattern_class = ? LIMIT 1",
                    (pipeline_run_id, ticker, pattern_class),
                ).fetchone()
                if existing is not None:
                    log.info(
                        "pattern_detect: row exists for (%d, %s, %s); "
                        "skipping idempotent re-invocation",
                        pipeline_run_id,
                        ticker,
                        pattern_class,
                    )
                    rows_skipped_idempotent += 1
                    continue

                # Per-detector failure isolation (recon section 4.4).
                try:
                    evidence = detector_fn(
                        bars,
                        window,
                        conn=conn,
                        ticker=ticker,
                        asof_date=asof_run,
                    )
                except Exception as exc:
                    log.warning(
                        "pattern_detect: %s detector failed for %s "
                        "(continuing): %s: %s",
                        pattern_class,
                        ticker,
                        type(exc).__name__,
                        str(exc)[:200],
                    )
                    continue

                geometric_score = float(
                    getattr(evidence, "geometric_score", 0.0)
                )
                # T2.SB3: composite_score = geometric_score (template
                # matching lands at T2.SB5 -- recon section 8).
                composite_score = geometric_score

                # Accumulate composite_scores for the run-level histogram.
                universe_context["composite_scores"].append(composite_score)

                emit_queue.append(
                    (
                        ticker,
                        pattern_class,
                        version_str,
                        window,
                        evidence,
                        composite_score,
                    )
                )

        # ------------------------------------------------------------------
        # Pass 2: serialize + INSERT against the now-complete universe
        # histogram (every row carries the SAME run-level histogram).
        # ------------------------------------------------------------------
        for (
            ticker,
            pattern_class,
            version_str,
            window,
            evidence,
            composite_score,
        ) in emit_queue:
            # Drift-log capture (T-A.3.5 surface).
            try:
                fdl = capture_feature_distribution(
                    pattern_class, evidence, universe_context
                )
                fdl_json = _json.dumps(
                    dataclasses.asdict(fdl), default=str
                )
            except Exception as exc:
                log.warning(
                    "pattern_detect: drift-log capture failed for "
                    "(%s, %s) (continuing): %s",
                    ticker,
                    pattern_class,
                    exc,
                )
                continue

            # Evidence serialization (15-col row shape per recon
            # section 8).
            try:
                evidence_json = _json.dumps(
                    dataclasses.asdict(evidence), default=str
                )
            except Exception as exc:
                log.warning(
                    "pattern_detect: evidence serialization failed "
                    "for (%s, %s) (continuing): %s",
                    ticker,
                    pattern_class,
                    exc,
                )
                continue

            criteria_pass = getattr(evidence, "criteria_pass", {})
            try:
                geometric_score_json = _json.dumps(criteria_pass)
            except Exception:
                geometric_score_json = "{}"

            row = PatternEvaluation(
                id=None,
                pipeline_run_id=pipeline_run_id,
                ticker=ticker,
                pattern_class=pattern_class,
                detector_version=version_str,
                geometric_score=float(composite_score),
                geometric_score_json=geometric_score_json,
                composite_score=composite_score,
                structural_evidence_json=evidence_json,
                feature_distribution_log_json=fdl_json,
                window_start_date=window.start_date.isoformat(),
                window_end_date=window.end_date.isoformat(),
                created_at=_dt_inner.now(UTC).isoformat(),
                template_match_score=None,
                template_match_nearest_exemplar_ids_json=None,
            )
            try:
                insert_evaluation(conn, row)
                rows_written += 1
            except Exception as exc:
                log.warning(
                    "pattern_detect: INSERT failed for (%s, %s) "
                    "(continuing): %s",
                    ticker,
                    pattern_class,
                    exc,
                )
                continue

    log.info(
        "pattern_detect: wrote %d pattern_evaluations rows across %d "
        "aplus tickers (%d skipped idempotent)",
        rows_written,
        len(aplus_tickers),
        rows_skipped_idempotent,
    )


def _step_charts(*, cfg, lease: Lease, eval_run_id: int, data_asof: str,
                  ohlcv_cache) -> dict[str, Path]:
    """Render charts for A+ + top-N near-trigger watchlist via staging.

    Phase 13 T1.SB0 (plan §G.0): consumes OHLCV via
    ``ohlcv_cache.get_or_fetch(ticker=..., window_days=200)`` — closes the
    Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral. Caller
    is the runner's outer step loop; tests pass a duck-typed stub exposing
    ``get_or_fetch`` (NOT the legacy ``PriceFetcher.get``).

    Writes go through `promote_staging`, which re-reads pipeline_runs in-line
    and raises `LeaseRevokedError` if the lease has been force-cleared before the
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
            # Phase 13 T1.SB0 (plan §G.0): consume OHLCV via OhlcvCache.
            # ``get_or_fetch`` matches ``PriceFetcher.get``'s shape + raise-
            # on-empty contract (recon §1 + §3), so the except clause
            # preserves the existing ``fetcher_failed`` semantic.
            ohlcv = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)
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


def compose_open_trade_advisories_for_briefing(
    *,
    trades,
    fetcher,
    candidates_by_ticker,
    weather_status: str,
    stop_advisory_config,
    action_session_date: str,
    data_asof_date: str | None = None,
    trimmed_trade_ids: set[int] | None = None,
    maturity_stage_by_trade_id: dict[int, str | None] | None = None,
) -> dict[int, list[AdvisorySuggestionVM]]:
    """Compose per-trade advisories for the pipeline briefing renderer.

    Mirrors the dashboard's ``compute_all_suggestions(trade, AdvisoryContext)``
    composition (see ``swing/web/view_models/dashboard.py`` build_dashboard
    loop) so the briefing emits the SAME advisories an operator would see on
    the dashboard. Pipeline-side divergence from web side
    (locked design §0.3 #2):

      * No live ``PriceCache``. ``current_price`` is sourced from the open-
        position synthetic candidate row's ``close`` (written by
        ``_step_evaluate`` per CLAUDE.md "PriceCache._last_close only sees
        tickers in today's candidates table"), then falls back to the OHLCV
        ``previous_close`` if the candidate has no close. The pipeline runs
        end-of-day; ``previous_close`` IS the most-recent completed-session
        close → semantically equivalent to the dashboard's last-close
        fallback in the after-hours render path.
      * SMA + ``previous_close`` from ``fetcher.get(ticker, lookback_days=200,
        as_of_date=date.fromisoformat(data_asof_date))`` which consumes the
        per-ticker archive (``swing.data.ohlcv_archive``) ``_step_charts``
        already populated FOR THE SAME LEASE / data_asof. The
        ``as_of_date`` pin (Codex R1 Major 3 fix) prevents
        wall-clock-vs-data-asof drift on retries / cross-session runs that
        ``PriceFetcher._resolve_asof(None)`` would otherwise mask.

    "No new yfinance calls" claim (brief A.AC.5; Codex R1 Major 4
    disposition — ACCEPTED with rationale; R2 Minor #2 docstring
    correction): re-reading the archive consults ``read_or_fetch_archive``,
    which COULD refresh from yfinance under its own staleness rules
    (weekly full-refresh on metadata; gap-fill when
    ``archive.index.max() < last_completed_session_today()``). In practice
    this never happens in steady state because open-trade tickers are
    guaranteed to be in chart-step scope (Tier-2 dedup precedence at
    ``_step_charts`` lines 728-752); the archive is freshly written within
    the same lease ~seconds before ``_step_export`` runs, so when this
    helper re-consults the archive the latest stored bar is already today's
    completed-session bar.

    Note: the archive's refresh rules are WALL-CLOCK driven (today =
    ``_last_completed_session_today()``), NOT keyed on the ``end_date``
    parameter we pass via ``as_of_date``. Our ``as_of_date`` pin only
    SLICES the returned DataFrame; it does NOT control refresh behavior.
    A pipeline run whose wall-clock day differs from its ``data_asof``
    (e.g., retry on Tuesday for Monday's session) MAY therefore trigger a
    gap-fill yfinance call. Acceptance precedent matches ``_step_charts``
    itself, which has the same dependency. A stricter "archive-only" knob
    on ``PriceFetcher`` would be V2 scope.

    Returns ``{trade.id: [AdvisorySuggestionVM, ...]}`` keyed by every open
    trade — empty list when no advisory triggers fire OR when the fetcher
    fails (defensive: briefing emission must not abort on per-ticker
    fetcher failure; logged as warning).

    Companion helper ``compose_open_trade_last_prices_for_briefing`` uses
    the SAME candidate.close → OHLCV previous_close fallback chain to
    populate ``BriefingInputs.open_trade_last_prices``. Both helpers must
    stay in sync — Codex R2 Major #2 closure.
    """
    # Pin as_of_date so PriceFetcher does NOT default-fall back to
    # `last_completed_session(datetime.now())` (Codex R1 Major 3 fix —
    # mismatch on retries / cross-session runs).
    pinned_asof = (
        _date.fromisoformat(data_asof_date) if data_asof_date else None
    )
    out: dict[int, list[AdvisorySuggestionVM]] = {}
    for t in trades:
        if t.id is None:
            # Briefing renderer key uses `t.id or 0` — defensive: skip rows
            # that lack a PK (data-integrity bug; would otherwise collide).
            continue
        try:
            bars = fetcher.get(
                t.ticker, lookback_days=200, as_of_date=pinned_asof,
            )
        except Exception as exc:
            log.warning(
                "briefing advisory: fetcher.get failed for %s: %s",
                t.ticker, exc,
            )
            # Codex R2 Major #1 — even on fetcher failure, the DB-sourced
            # §4.A.bis maturity-stage hint should fire (the helper's stated
            # contract at swing/trades/advisory.py compute_price_independent_suggestions
            # says "PriceCache degraded; OHLCV fetch failed; etc."). Pre-fix
            # ``out[t.id] = []`` skip silently dropped the hint here.
            ctx_mat = AdvisoryContext(
                as_of_date=action_session_date,
                current_price=0.0,
                sma10=None, sma20=None, sma50=None,
                previous_close=None,
                weather_status=weather_status,
                config=stop_advisory_config,
                maturity_stage=(
                    maturity_stage_by_trade_id.get(t.id)
                    if maturity_stage_by_trade_id is not None
                    else None
                ),
            )
            from swing.trades.advisory import (
                compute_price_independent_suggestions,
            )
            mat_raw = compute_price_independent_suggestions(t, ctx_mat)
            out[t.id] = [
                AdvisorySuggestionVM(rule=s.rule, message=s.message)
                for s in mat_raw
            ]
            continue

        smas = _compute_smas(bars, [10, 20, 50])
        prev_close = _previous_close(bars)
        # 3e.8 Bundle 2 — adr_pct from the SAME bars helper consumed for SMAs.
        # No new fetch; identical caching/staleness semantics.
        adr_pct = _compute_adr_pct(bars, lookback=20)

        cand = candidates_by_ticker.get(t.ticker)
        cand_close = cand.close if cand is not None else None
        # current_price precedence: candidate's last_close (kept fresh for
        # open-position tickers by `_step_evaluate`) → OHLCV last-bar close
        # fallback. Both anchor on the last completed session.
        current_price = cand_close if cand_close is not None else prev_close
        # 3e.8 Bundle 3 Codex R1 Major #2 — when no current_price is
        # available, the §4.A.bis maturity-stage advisory should still
        # fire from the DB-sourced snapshot. Use a sentinel price (0.0)
        # and the price-independent composer rather than dropping the
        # trade entirely.
        if current_price is None:
            ctx_mat = AdvisoryContext(
                as_of_date=action_session_date,
                current_price=0.0,
                sma10=None, sma20=None, sma50=None,
                previous_close=None,
                weather_status=weather_status,
                config=stop_advisory_config,
                maturity_stage=(
                    maturity_stage_by_trade_id.get(t.id)
                    if maturity_stage_by_trade_id is not None
                    else None
                ),
            )
            from swing.trades.advisory import (
                compute_price_independent_suggestions,
            )
            mat_raw = compute_price_independent_suggestions(t, ctx_mat)
            out[t.id] = [
                AdvisorySuggestionVM(rule=s.rule, message=s.message)
                for s in mat_raw
            ]
            continue

        ctx = AdvisoryContext(
            as_of_date=action_session_date,
            current_price=current_price,
            sma10=smas.get(10),
            sma20=smas.get(20),
            sma50=smas.get(50),
            previous_close=prev_close,
            weather_status=weather_status,
            config=stop_advisory_config,
            adr_pct=adr_pct,
            has_been_trimmed=(
                t.id in trimmed_trade_ids
                if trimmed_trade_ids is not None
                else False
            ),
            # 3e.8 Bundle 3 — caller supplies a {trade_id: maturity_stage} map
            # built from the same ``list_open_position_active_snapshots`` read
            # ``_step_export`` performs for ``daily_mgmt_snapshots``. Missing
            # trade_id ⇒ None ⇒ rule no-ops.
            maturity_stage=(
                maturity_stage_by_trade_id.get(t.id)
                if maturity_stage_by_trade_id is not None
                else None
            ),
        )
        raw = compute_all_suggestions(t, ctx)
        out[t.id] = [
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        ]
    return out


class _CachingFetcherWrapper:
    """Wraps a fetcher protocol (PriceFetcher or test stub) and caches
    per-key bars + per-key failure across both
    ``compose_open_trade_advisories_for_briefing`` and
    ``compose_open_trade_last_prices_for_briefing`` invocations.

    Codex R3 Major #1 closure — without the cache, the two helpers can
    diverge under transient fetcher failures: the first call (advisory
    composition) succeeds and uses ``prev_close``, but the second call
    (last-price resolution) raises → ticker omitted from
    ``open_trade_last_prices`` → briefing renderer falls back to
    ``t.entry_price`` for Last/R/P&L while advisories fire from a newer
    price. By caching the SAME (ticker, lookback, as_of_date) → bars
    mapping AND the failure state, both helpers see identical results.

    Lifecycle: instantiated per ``_step_export`` call; discarded at end.
    Not thread-safe; pipeline run is single-threaded by lease design.
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self._cache: dict[tuple, object] = {}
        self._failures: dict[tuple, BaseException] = {}

    def get(self, ticker, lookback_days, *, as_of_date=None):
        key = (ticker, lookback_days, as_of_date)
        if key in self._failures:
            # Re-raise the original exception type so callers (helpers) get
            # the same failure semantics as the un-cached path.
            raise self._failures[key]
        if key in self._cache:
            return self._cache[key]
        try:
            bars = self._inner.get(
                ticker, lookback_days, as_of_date=as_of_date,
            )
        except BaseException as exc:  # noqa: BLE001 — re-raise after caching
            self._failures[key] = exc
            raise
        self._cache[key] = bars
        return bars


def compose_open_trade_last_prices_for_briefing(
    *,
    trades,
    fetcher,
    candidates_by_ticker,
    data_asof_date: str | None = None,
) -> dict[str, float]:
    """Resolve per-ticker last prices using the SAME candidate.close →
    OHLCV previous_close fallback chain that
    ``compose_open_trade_advisories_for_briefing`` uses for advisory
    ``current_price``. Codex R2 Major #2 closure.

    Without this companion helper, the briefing renderer's
    ``open_trade_last_prices.get(t.ticker, t.entry_price)`` fallback at
    ``swing/rendering/briefing.py:123`` can render Last == entry_price for
    a trade whose advisories fired from a newer prev_close — the very
    contradiction R1 Major #2 closed for the candidate-present path.

    Returns ``{ticker: float}`` matching the
    ``BriefingInputs.open_trade_last_prices`` contract. Tickers without a
    resolved price (no candidate row AND fetcher.get raised OR returned no
    Close column) are OMITTED — the briefing renderer's
    ``.get(ticker, t.entry_price)`` fallback handles those, and that's the
    correct semantic: "we genuinely have no price data; show entry price
    as a degraded fallback".
    """
    pinned_asof = (
        _date.fromisoformat(data_asof_date) if data_asof_date else None
    )
    out: dict[str, float] = {}
    for t in trades:
        cand = candidates_by_ticker.get(t.ticker)
        if cand is not None and cand.close is not None:
            out[t.ticker] = cand.close
            continue
        # Candidate.close missing — fall back to OHLCV previous_close.
        # Archive read is cheap (parquet); duplicates the advisory helper's
        # read for the same ticker but keeps both helpers single-purpose.
        try:
            bars = fetcher.get(
                t.ticker, lookback_days=200, as_of_date=pinned_asof,
            )
        except Exception as exc:
            log.warning(
                "briefing last-price: fetcher.get failed for %s: %s",
                t.ticker, exc,
            )
            continue
        prev = _previous_close(bars)
        if prev is not None:
            out[t.ticker] = prev
    return out


def _step_export(*, cfg, lease: Lease, eval_run_id: int, action_session,
                  data_asof: str, chart_paths: dict[str, Path],
                  fetcher: PriceFetcher | None = None) -> None:
    lease.verify_held()
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.daily_management import (
        list_open_position_active_snapshots,
    )
    from swing.data.repos.fills import list_all_fills
    from swing.data.repos.recommendations import list_for_session
    from swing.data.repos.schwab_api_calls import is_schwab_degraded
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
        daily_mgmt_snapshots = list_open_position_active_snapshots(conn)
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=_exits_via_fills_for_equity(conn),
            cash_movements=list_cash(conn),
        )
        # 3e.8 Bundle 2 — build trimmed_trade_ids alongside the equity /
        # exits-aggregation reads above. SQLite Python autocommit gives each
        # SELECT its own implicit transaction, so this is NOT a strict
        # multi-statement snapshot; the export step relies on the pipeline
        # lease serializing pipeline-side writers, matching the pre-existing
        # posture of the equity/exits/trades reads in this same block.
        # A trade is "trimmed" iff at least one non-entry fill exists.
        # (Codex R1 Major #2 — ACCEPTED-with-rationale: lease-guarded
        # isolation; raising this to a true BEGIN IMMEDIATE snapshot is a
        # broader cleanup outside Bundle 2 scope.)
        trimmed_trade_ids: set[int] = {
            f.trade_id for f in list_all_fills(conn) if f.action != "entry"
        }
        # 3e.8 Bundle 3 — build {trade_id: maturity_stage} alongside the
        # daily_mgmt_snapshots read above so the briefing composer can fire
        # the §4.A.bis maturity-stage advisory. Reuses the SAME snapshot list
        # the briefing renderer's daily-management section consumes — single
        # source of truth.
        maturity_stage_by_trade_id: dict[int, str | None] = {
            s.trade_id: s.maturity_stage for s in daily_mgmt_snapshots
        }
        # Schwab API arc-closer Sub-bundle D Task T-D.5 — degraded predicate.
        # Read-only check on most-recent schwab_api_calls row; emits the
        # spec §3.4.4 / §7.2 banner when status != 'success'. ZERO-rows-yet
        # state is NOT degraded (false-positive guard per dispatch brief
        # §5.2 T-D.5 pre-emption).
        schwab_degraded, schwab_degraded_endpoint_name = is_schwab_degraded(conn)

        # Phase 12 Sub-bundle C T-C.10 — Reconciliation status counters.
        # ``reconciliation_pending_count`` reads the operator backlog;
        # ``reconciliation_tier1_recent_count`` reads the last-7-day
        # tier-1 auto-corrections. Both surface in briefing.md via the
        # T-C.9 "Reconciliation status" section.
        reconciliation_pending_count = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE resolution = 'pending_ambiguity_resolution' "
            "AND material_to_review = 1"
        ).fetchone()[0])
        # 7-day window anchored on action_session (data_asof drift is OK
        # — the briefing already disclaims best-effort historical
        # accuracy per Phase 10 §A.0.1 footnote).
        from datetime import datetime as _dtcls
        from datetime import timedelta as _td
        cutoff_iso = (
            _dtcls.utcnow().replace(microsecond=0) - _td(days=7)
        ).isoformat(timespec="seconds")
        reconciliation_tier1_recent_count = int(conn.execute(
            "SELECT COUNT(*) FROM reconciliation_corrections "
            "WHERE correction_action = 'auto_applied' "
            "AND applied_at >= ?",
            (cutoff_iso,),
        ).fetchone()[0])
        # Phase 12.5 #1 T-1.11 — multi-leg tier-1 auto-redirect counter.
        # DISTINCT-discrepancy semantic (F18) + banner-clears semantic
        # (only the LATEST completed reconciliation_run; spec §8.4 +
        # §11.2). Returns 0 when no completed runs exist or the latest
        # completed run has zero multi-leg auto-redirects.
        reconciliation_tier1_multi_leg_redirected_count = (
            count_recent_multi_leg_auto_corrections(conn)
        )
    finally:
        conn.close()

    candidates_by_ticker = {c.ticker: c for c in candidates}

    # 3e.8 Bundle 1 Task A.2 — compose per-trade advisories so the briefing
    # surfaces the SAME advisories the dashboard renders. ``fetcher`` is
    # threaded from ``run`` (the pipeline orchestrator) and re-reads the
    # per-ticker OHLCV archive _step_charts already populated → no new
    # yfinance calls. If the caller did NOT supply a fetcher (test paths,
    # explicit opt-out), fall back to the legacy empty-dict.
    #
    # Codex R3 Major #1 fix — wrap fetcher in a per-step bars cache so the
    # advisory helper AND the last-price helper see IDENTICAL bars (or
    # identical failures) for any given (ticker, lookback, as_of_date)
    # tuple. Without the cache, a transient failure between the two helper
    # calls could diverge: advisory uses prev_close path while last-prices
    # omits the ticker.
    cached_fetcher = (
        _CachingFetcherWrapper(fetcher) if fetcher is not None else None
    )
    open_trade_advisories: dict[int, list[AdvisorySuggestionVM]]
    if cached_fetcher is not None:
        open_trade_advisories = compose_open_trade_advisories_for_briefing(
            trades=trades,
            fetcher=cached_fetcher,
            candidates_by_ticker=candidates_by_ticker,
            weather_status=(weather.status if weather else "STALE"),
            stop_advisory_config=cfg.stop_advisory,
            action_session_date=action_session.isoformat(),
            data_asof_date=data_asof,
            trimmed_trade_ids=trimmed_trade_ids,
            maturity_stage_by_trade_id=maturity_stage_by_trade_id,
        )
    else:
        open_trade_advisories = {}

    # 3e.8 Bundle 1 Codex R1 Major 2 + R2 Major 2 fix — populate
    # open_trade_last_prices from the SAME source chain the advisory
    # composition uses for ``current_price`` (candidate.close →
    # OHLCV previous_close). Without the matched fallback, the briefing
    # renderer's ``open_trade_last_prices.get(t.ticker, t.entry_price)``
    # at swing/rendering/briefing.py:123 displays Last == entry_price for
    # the (rare) candidate-absent path, while advisories fire from the
    # prev_close — the residual contradiction R2 Major 2 surfaced.
    open_trade_last_prices: dict[str, float]
    if cached_fetcher is not None:
        open_trade_last_prices = compose_open_trade_last_prices_for_briefing(
            trades=trades,
            fetcher=cached_fetcher,
            candidates_by_ticker=candidates_by_ticker,
            data_asof_date=data_asof,
        )
    else:
        # No fetcher → no OHLCV fallback available; degenerate to
        # candidate.close only.
        open_trade_last_prices = {
            t.ticker: candidates_by_ticker[t.ticker].close
            for t in trades
            if t.ticker in candidates_by_ticker
            and candidates_by_ticker[t.ticker].close is not None
        }

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
        open_trade_advisories=open_trade_advisories,
        open_trade_last_prices=open_trade_last_prices,
        watchlist=watchlist, watchlist_last_prices={},
        candidates_by_ticker=candidates_by_ticker,
        chart_b64s={t: _b64_chart(p) for t, p in chart_paths.items()},
        near_trigger_above_pct=cfg.near_trigger.above_pct,
        near_trigger_below_pct=cfg.near_trigger.below_pct,
        daily_management_active_snapshots=daily_mgmt_snapshots,
        schwab_degraded_endpoint=(
            schwab_degraded_endpoint_name if schwab_degraded else None
        ),
        reconciliation_pending_count=reconciliation_pending_count,
        reconciliation_tier1_recent_count=reconciliation_tier1_recent_count,
        reconciliation_tier1_multi_leg_redirected_count=(
            reconciliation_tier1_multi_leg_redirected_count
        ),
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


def _step_daily_management(
    *, lease, run_now: _dt, eval_run_id: int,
    archive_history_days: int, ohlcv_archive_dir,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,  # noqa: N803  -- name locked by spec §6.6
) -> None:
    """Spec §4.1 step body — emit a daily_approximate snapshot per open trade.

    Cadence-step semantics: per-trade failures logged + step continues —
    EXCEPT for ``LeaseRevokedError``, which MUST re-raise so force-clear remains
    authoritative (Codex R2 Major #5; mirrors all other pipeline steps'
    discipline at the run_pipeline_internal try/except branches).

    Gap-flagged policy (spec §4.1): one snapshot per ``last_completed_session
    (run_now)``. NO auto back-fill of missed sessions — if the pipeline
    didn't run on a given day, no snapshot exists for that day.

    Idempotent same-session re-run: ``upsert_snapshot`` does
    SELECT-then-UPDATE-or-INSERT against ``(trade_id, data_asof_session,
    mfe_mae_precision_level)``, so re-running on the same day preserves
    ``management_record_id`` (audit-FK chain stable).

    State-machine transition: trades in state ``'entered'`` advance to
    ``'managing'`` after the first snapshot row lands.
    """
    from swing.data.repos.daily_management import upsert_snapshot
    from swing.data.repos.trades import list_open_trades
    from swing.pipeline.lease import LeaseRevokedError
    from swing.trades import daily_management as _dm
    from swing.trades.state import state_transition

    asof_session = last_completed_session(run_now)
    with lease.fenced_write() as conn:
        trades = list_open_trades(conn)
    for trade in trades:
        try:
            with lease.fenced_write() as conn:
                fields = _dm.compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id,
                    asof_session=asof_session,
                    run_now=run_now,
                    ohlcv_archive_dir=ohlcv_archive_dir,
                    archive_history_days=archive_history_days,
                    # Codex R1 Critical 1 fix: snapshot.pipeline_run_id is
                    # FK to pipeline_runs(id), NOT evaluation_runs(id).
                    # ``lease.run_id`` is the pipeline_runs.id (set during
                    # lease acquisition); ``eval_run_id`` is the
                    # evaluation_runs.id from _step_evaluate. They diverge
                    # in normal operation; the FK will fire when ids
                    # diverge and the eval id can't be found in pipeline_runs.
                    pipeline_run_id=lease.run_id,
                    capital_floor_dollars=capital_floor_dollars,
                    trail_MA_period_days_default=trail_MA_period_days_default,
                )
                if fields is None:
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): archive returned None",
                        trade.id, trade.ticker,
                    )
                    continue
                upsert_snapshot(
                    conn, trade_id=trade.id, snapshot_fields=fields,
                )
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=fields["created_at"],
                        rationale="first_daily_management_record",
                    )
        except LeaseRevokedError:
            # Force-clear authoritative — propagate immediately. Codex R2 M5.
            raise
        except Exception as exc:
            log.warning(
                "daily_management step failed for trade %s: %s",
                trade.id, exc,
            )


def _finviz_fetch_core(cfg) -> dict:
    """Shared API fetch + normalize + signature computation.

    Returns a dict with keys:
        status: 'ok' | 'error' | 'skipped_manual_override'
        csv_text: str | None  (canonical 13-column CSV text; None if not written)
        csv_path: Path        (target path; written by caller on status=='ok')
        row_count: int | None
        response_time_ms: int | None
        signature_hash: str | None
        rate_limit_remaining: int | None
        error_message: str | None

    Performs the fetch but does NOT write to DB or filesystem; the caller
    persists per-surface (lease-fenced for pipeline; raw conn for CLI).
    """
    import os  # noqa: F401
    import platform
    import time

    from swing.integrations.finviz_api import (
        FinvizApiError,
        FinvizClient,
        FinvizConfigMissingError,
        FinvizRateLimitError,
        FinvizSchemaParityError,
    )

    action_session = action_session_for_run(_dt.now())
    fmt = "%#d" if platform.system() == "Windows" else "%-d"
    date_str = action_session.strftime(f"{fmt}%b%Y")
    csv_path = cfg.paths.finviz_inbox_dir / f"finviz{date_str}.csv"

    # Codex R1 Major-2 fix: inbox-dir creation can fail (PermissionError on
    # locked-down filesystems; OSError on non-existent parent + read-only mount).
    # Plan §A.13/§H requires file-write failures to downgrade to status='error'
    # with an audit row inserted last — same contract as the shadow-write path.
    # Returning early with status='error' here lets the caller's lease-fenced
    # audit insert record the failure truthfully rather than escaping as a
    # generic "programming error" via the outer try/except.
    try:
        cfg.paths.finviz_inbox_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        log.warning("Finviz inbox-dir creation failed: %s", msg)
        return {
            "status": "error", "csv_text": None, "csv_path": csv_path,
            "row_count": None, "response_time_ms": 0,
            "signature_hash": None, "rate_limit_remaining": None,
            "error_message": msg[:1024],
        }

    if csv_path.exists():
        log.info(
            "Manual CSV present at %s; Finviz API fetch skipped (manual override).",
            csv_path,
        )
        return {
            "status": "skipped_manual_override", "csv_text": None,
            "csv_path": csv_path, "row_count": None,
            "response_time_ms": None, "signature_hash": None,
            "rate_limit_remaining": None, "error_message": None,
        }

    # Pre-check config presence so a missing-token does NOT trigger any
    # network call (the test asserts fetch_screen.assert_not_called()).
    fz_cfg = cfg.integrations.finviz
    if not fz_cfg.token:
        return {
            "status": "error", "csv_text": None, "csv_path": csv_path,
            "row_count": None, "response_time_ms": 0,
            "signature_hash": None, "rate_limit_remaining": None,
            "error_message": "FinvizConfigMissingError: token is missing",
        }
    # Codex R2 Minor-1: validate AFTER stripping leading '?' so a bare '?'
    # (or '?'-only padding) is treated as missing — same canonicalization as
    # FinvizClient.fetch_screen so the surface-vs-helper precheck matches.
    if not fz_cfg.screen_query.lstrip("?"):
        return {
            "status": "error", "csv_text": None, "csv_path": csv_path,
            "row_count": None, "response_time_ms": 0,
            "signature_hash": None, "rate_limit_remaining": None,
            "error_message": "FinvizConfigMissingError: screen_query is missing",
        }

    start = time.monotonic()
    try:
        client = FinvizClient(cfg)
        body = client.fetch_screen()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        canonical_text = client.normalize_to_canonical_csv(body)
        sig = client.compute_signature_hash(body)
        return {
            "status": "ok", "csv_text": canonical_text, "csv_path": csv_path,
            "row_count": canonical_text.count("\n") - 1,
            "response_time_ms": elapsed_ms, "signature_hash": sig,
            "rate_limit_remaining": client.last_rate_limit_remaining,
            "error_message": None,
        }
    except (
        FinvizConfigMissingError, FinvizApiError, FinvizRateLimitError,
        FinvizSchemaParityError,
    ) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        msg = f"{type(exc).__name__}: {exc}"
        log.warning("Finviz API fetch failed: %s", msg)
        return {
            "status": "error", "csv_text": None, "csv_path": csv_path,
            "row_count": None, "response_time_ms": elapsed_ms,
            "signature_hash": None, "rate_limit_remaining": None,
            "error_message": msg[:1024],
        }


def _finviz_persist_csv_shadow(csv_path: Path, csv_text: str) -> Path:
    """Write CSV to a shadow path '<canonical>.api-pending' atomically.
    Returns the shadow path for later promotion. Per plan §A.13."""
    import os
    shadow_path = Path(str(csv_path) + ".api-pending")
    tmp_path = Path(str(shadow_path) + ".tmp")
    tmp_path.write_text(csv_text, encoding="utf-8")
    os.replace(tmp_path, shadow_path)
    return shadow_path


def _finviz_promote_shadow(shadow_path: Path, canonical_path: Path) -> None:
    """Atomic rename shadow → canonical."""
    import os
    os.replace(shadow_path, canonical_path)


def _read_finviz_call_max_id_snapshot(cfg) -> int | None:
    """Snapshot ``MAX(call_id)`` for causal scoping of diagnostic enrichment.

    Phase 12.5 finviz-inbox-auto-fetch-fix Codex R2 Major #1 helper:
    capture BEFORE invoking the inline ``_step_finviz_fetch`` so the
    follow-up diagnostic read can scope its query to ``WHERE call_id >
    <snapshot>`` — guaranteeing the read returns ONLY rows inserted by
    THIS call (not a prior unrelated row from a CLI surface, not a
    misattributed concurrent insert, not a future-dated test row).
    Returns ``0`` if the table is currently empty (any subsequent insert
    will have ``call_id >= 1`` per SQLite ``INTEGER PRIMARY KEY
    AUTOINCREMENT`` semantics). Returns ``None`` only when the read
    itself fails (DB locked, table missing) — the diagnostic enrichment
    then no-ops rather than risk a false-confidence misattribution.
    """
    from swing.data.db import connect as _connect
    try:
        conn = _connect(cfg.paths.db_path)
        try:
            row = conn.execute(
                "SELECT MAX(call_id) FROM finviz_api_calls"
            ).fetchone()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover — defensive read-side guard
        log.warning(
            "Finviz call_id snapshot read failed (continuing): %s", exc,
        )
        return None
    return int(row[0]) if row and row[0] is not None else 0


def _read_latest_finviz_call_diagnostic(
    cfg, *, after_call_id: int | None,
) -> tuple[str | None, str | None]:
    """Read the FIRST ``finviz_api_calls`` row inserted after ``after_call_id``.

    Phase 12.5 finviz-inbox-auto-fetch-fix Codex R1 Major #1 +
    R2 Major #1 helper: ``_step_finviz_fetch`` does NOT raise for
    expected Finviz API failures (missing token, auth, rate limit,
    schema parity) — ``_finviz_fetch_core`` returns ``status='error'``
    and the audit row is inserted, but the function returns normally.
    To enrich the combined-error message in the retry-failed path with
    the real "why", surface THAT just-written audit row's status +
    error_message. The R2 ``after_call_id`` scoping causally ties the
    read to this pipeline's audit row insert — eliminates the prior
    R1 "latest globally" misattribution risk under multi-surface
    concurrency.

    When ``after_call_id is None`` (snapshot read failed) → return
    ``(None, None)`` and skip diagnostic enrichment rather than
    risk misattributing a prior row. Defensive: any other read
    failure also returns ``(None, None)`` so the combined-error
    report continues to fail-fast with the existing minimal-
    information message rather than masking the original failure
    with a diagnostic-read error.
    """
    if after_call_id is None:
        return (None, None)
    from swing.data.db import connect as _connect
    try:
        conn = _connect(cfg.paths.db_path)
        try:
            row = conn.execute(
                "SELECT status, error_message FROM finviz_api_calls "
                "WHERE call_id > ? ORDER BY call_id ASC LIMIT 1",
                (after_call_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover — defensive read-side guard
        log.warning(
            "Finviz audit-row diagnostic read failed (continuing): %s", exc,
        )
        return (None, None)
    if row is None:
        return (None, None)
    return (row[0], row[1])


def _finviz_cleanup_stale_shadows(inbox_dir: Path) -> None:
    """Delete '.api-pending' files older than 1 hour. Belt-and-suspenders
    cleanup for the rare case where a process-kill leaks a shadow."""
    import time
    cutoff = time.time() - 3600  # 1 hour
    if not inbox_dir.exists():
        return
    for f in inbox_dir.glob("*.api-pending"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def _assert_no_active_pipeline_run(conn: sqlite3.Connection) -> None:
    """Refuse standalone Finviz fetch if a pipeline run is currently running.
    Plan §A.14 (Codex R2 Major-3 fix). Pipeline-internal _step_finviz_fetch
    does NOT call this — it runs WHILE the lease is held."""
    from swing.integrations.finviz_api import FinvizPipelineActiveError
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE state = 'running' "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        raise FinvizPipelineActiveError(
            f"A pipeline run is currently in flight (run_id={row[0]}); "
            "the standalone Finviz fetch is refused to avoid corrupting "
            "the inbox or audit log. Wait for the run to complete "
            "(swing pipeline status) and retry, OR run the fetch as "
            "part of the pipeline (swing pipeline run)."
        )


def _step_finviz_fetch(*, cfg, lease) -> None:
    """Pipeline step: fetch today's Finviz screen via API.

    Sequence (Codex R3 Major-1 fix — file work BEFORE audit insert; audit row
    is THE ground truth):
      1. Recovery sweep for stale shadow files.
      2. _finviz_fetch_core (in-memory fetch + normalize + signature).
      3. If result['status']=='ok': lease-fenced read of prior signature →
         drift warning; shadow-write CSV; promote shadow to canonical.
      4. Any exception during step-3 file work → DOWNGRADE result to
         status='error' with the OS-error message; clean any leftover shadow.
      5. Lease-fenced audit-row insert with the (possibly-downgraded) result.
    """
    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import get_latest_signature_hash, insert_call

    _finviz_cleanup_stale_shadows(cfg.paths.finviz_inbox_dir)
    result = _finviz_fetch_core(cfg)
    now_iso = _dt.now().isoformat(timespec="seconds")
    # Codex R5: canonicalize for direct runner callers (defense-in-depth
    # complement to apply_overrides() + fetch_screen() canonicalization).
    sq = cfg.integrations.finviz.screen_query.lstrip("?")

    if result["status"] == "ok":
        shadow_path: Path | None = None
        try:
            with lease.fenced_write() as conn:
                prior_sig = get_latest_signature_hash(conn, screen_query=sq)
            if prior_sig is not None and prior_sig != result["signature_hash"]:
                log.warning(
                    "Finviz screen signature changed since prior run "
                    "(%s -> %s); operator may have edited the saved screen.",
                    prior_sig[:12], result["signature_hash"][:12],
                )
            shadow_path = _finviz_persist_csv_shadow(
                result["csv_path"], result["csv_text"],
            )
            _finviz_promote_shadow(shadow_path, result["csv_path"])
            shadow_path = None  # promoted; nothing to clean
        except Exception as exc:
            # File-write OR promote OR fenced-read failed. DOWNGRADE the
            # result so the audit row reflects ground truth (Codex R3 M1).
            log.warning("Finviz CSV write/promote failed: %s", exc)
            result["status"] = "error"
            result["row_count"] = None
            result["signature_hash"] = None
            result["error_message"] = f"{type(exc).__name__}: {exc}"
        finally:
            if shadow_path is not None and shadow_path.exists():
                try:
                    shadow_path.unlink()
                except OSError as _exc:
                    log.warning("failed to clean up Finviz shadow file: %s", _exc)

    # Final audit-row insert. If THIS fenced_write raises LeaseRevokedError,
    # the audit row is missing but file state is consistent.
    with lease.fenced_write() as conn:
        insert_call(conn, FinvizApiCall(
            call_id=None, ts=now_iso, screen_query=sq,
            status=result["status"], row_count=result["row_count"],
            response_time_ms=result["response_time_ms"],
            rate_limit_remaining=result["rate_limit_remaining"],
            signature_hash=result["signature_hash"],
            error_message=result["error_message"],
        ))


def _perform_finviz_fetch_no_lease(*, cfg, conn: sqlite3.Connection) -> None:
    """Standalone (non-pipeline) Finviz fetch — used by `swing finviz fetch` CLI.

    Refuses execution if a pipeline run is currently in flight (plan §A.14).
    Same file-work-before-audit-insert ordering as `_step_finviz_fetch`
    (Codex R3 Major-1 fix). Writes through the caller-provided `conn`.
    """
    from swing.data.models import FinvizApiCall
    from swing.data.repos.finviz_api_calls import get_latest_signature_hash, insert_call

    _assert_no_active_pipeline_run(conn)
    _finviz_cleanup_stale_shadows(cfg.paths.finviz_inbox_dir)
    result = _finviz_fetch_core(cfg)
    now_iso = _dt.now().isoformat(timespec="seconds")
    # Codex R5: canonicalize for direct runner callers (defense-in-depth
    # complement to apply_overrides() + fetch_screen() canonicalization).
    sq = cfg.integrations.finviz.screen_query.lstrip("?")

    if result["status"] == "ok":
        shadow_path: Path | None = None
        try:
            prior_sig = get_latest_signature_hash(conn, screen_query=sq)
            if prior_sig is not None and prior_sig != result["signature_hash"]:
                log.warning(
                    "Finviz screen signature changed since prior run "
                    "(%s -> %s); operator may have edited the saved screen.",
                    prior_sig[:12], result["signature_hash"][:12],
                )
            shadow_path = _finviz_persist_csv_shadow(
                result["csv_path"], result["csv_text"],
            )
            _finviz_promote_shadow(shadow_path, result["csv_path"])
            shadow_path = None
        except Exception as exc:
            log.warning("Finviz CSV write/promote failed: %s", exc)
            result["status"] = "error"
            result["row_count"] = None
            result["signature_hash"] = None
            result["error_message"] = f"{type(exc).__name__}: {exc}"
        finally:
            if shadow_path is not None and shadow_path.exists():
                try:
                    shadow_path.unlink()
                except OSError as _exc:
                    log.warning("failed to clean up Finviz shadow file: %s", _exc)

    insert_call(conn, FinvizApiCall(
        call_id=None, ts=now_iso, screen_query=sq,
        status=result["status"], row_count=result["row_count"],
        response_time_ms=result["response_time_ms"],
        rate_limit_remaining=result["rate_limit_remaining"],
        signature_hash=result["signature_hash"],
        error_message=result["error_message"],
    ))
