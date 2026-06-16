"""Pipeline runner — orchestrates 9 spec §5.1 steps with lease + staging + recovery."""
from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC
from datetime import date as _date
from datetime import datetime as _dt
from pathlib import Path

from swing.config import Config
from swing.data.backup import do_backup, prune_old_backups, should_backup
from swing.data.db import connect, open_connection

# Phase 13 T2.SB6c T-A.6c.2 §1.5.1 amendment — chart_renders cache
# write-through helpers + Theme 1 SVG renderers. Imported at module top
# so test fixtures may monkeypatch `swing.pipeline.runner.render_*`
# per F6 transient-empty discriminating test pattern.
from swing.data.models import ChartRender
from swing.data.ohlcv_archive import read_or_fetch_archive, warm_archives_batch
from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
from swing.data.repos.cash import list_cash
from swing.data.repos.chart_renders import refresh_chart_render
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
from swing.data.yfinance_audit_context import (
    yfinance_audit_disabled,
    yfinance_audit_scope,
)

# Phase 14 close-out follow-on (F-2): module-top import so the pipeline
# call-site test may monkeypatch ``swing.pipeline.runner.structural_stage``.
# Pure compute over fetched closes (no DB; replaces the persisted-criteria
# current_stage read at the market_weather site). No import cycle:
# trend_template imports only swing.evaluation.{context,criteria._base,rs}.
from swing.evaluation.criteria.trend_template import structural_stage
from swing.evaluation.dates import action_session_for_run, last_completed_session
from swing.evaluation.orchestration import (
    EvaluationBehaviorPolicy,
    OrchestrationOutput,
    UniverseAugmentation,
    orchestrate_evaluation,
)
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
from swing.log_correlation import set_pipeline_run_id
from swing.metrics.discrepancies import count_recent_multi_leg_auto_corrections
from swing.patterns.composite import compute_composite_score
from swing.patterns.template_matching import (
    GEOMETRIC_SCORE_PREGATE_THRESHOLD,
    TemplateMatchExemplar,
    match_forward,
)

# Phase 14 Sub-bundle 2 (T-2.4): module-top import so test fixtures may
# monkeypatch ``swing.pipeline.runner.render_and_capture_detection_chart``
# (a function-local import would shadow the module attribute the patch
# targets).
from swing.pipeline.detection_chart_capture import (
    render_and_capture_detection_chart,
)
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
from swing.pipeline.step_guard import step_guard
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
from swing.web.charts import (
    compute_chart_source_hash,
    render_market_weather_svg,
    render_position_detail_svg,
    render_watchlist_thumbnail_svg,
)

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
) -> tuple[object | None, object | None, object | None]:
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
        ``(price_cache, ohlcv_cache, audit_conn)`` — all ``None`` when no
        client. ``audit_conn`` is the single shared serialized audit-writer
        connection (OQ-C); the caller MUST close it in the run ``finally``.

    Consumer surfaces (post-Phase-13 T1.SB0): PriceCache is consumed by
    ``_step_evaluate`` (open-trade-ticker warm); OhlcvCache is consumed by
    ``_step_charts`` via ``ohlcv_cache.get_or_fetch(...)`` for chart-target
    OHLCV (closes the Phase 11 Sub-bundle C R1 M#5 V1 deferral). Both caches
    share the same ``schwab_client`` via captured closures.
    """
    if schwab_client is None:
        return None, None, None

    from swing.integrations.schwab.marketdata_ladder import (
        fetch_quote_via_ladder,
        fetch_window_via_ladder,
        resolve_full_archive_bars,
    )
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.web.price_cache import PriceCache

    price_cache = PriceCache(cfg)
    ohlcv_cache = OhlcvCache(cfg)

    # SQLite lock-contention arc (OQ-C): ONE shared serialized audit-writer
    # connection for ALL pipeline market-data audit writes, replacing the
    # <=16 per-hook connect()/close() pairs. The pipeline invokes the hooks
    # SYNCHRONOUSLY on this thread (PriceCache.get / OhlcvCache.get_or_fetch run
    # the hook inline -- the abandonable PriceCache.get_many executor path is
    # web-only and never used here), so the run `finally` closes audit_conn only
    # after all hook calls have returned. check_same_thread=False +
    # audit_service._AUDIT_WRITE_LOCK are forward-defensive: they keep audit
    # writes correct if a future caller ever invokes a hook from a worker thread.
    # The market-data path uses `conn` ONLY for audit (record_call_start/finish).
    audit_conn = open_connection(
        cfg.paths.db_path,
        busy_timeout_ms=cfg.web.db_busy_timeout_ms,
        reaffirm_wal=False,
        check_same_thread=False,
    )

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
        # OQ-C: use the single shared serialized audit connection (closed by the
        # run finally); audit_service._AUDIT_WRITE_LOCK serializes its writes.
        snap, provider_tag = fetch_quote_via_ladder(
            ticker,
            cfg=cfg,
            schwab_client=schwab_client,
            yfinance_fallback_fn=_yf_quote_fallback,
            conn=audit_conn,
            surface="pipeline",
            pipeline_run_id=pipeline_run_id,
        )
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
        # OQ-C: use the single shared serialized audit connection (closed by the
        # run finally); audit_service._AUDIT_WRITE_LOCK serializes its writes.
        window, provider_tag = fetch_window_via_ladder(
            ticker,
            start=None, end=None,
            cfg=cfg,
            schwab_client=schwab_client,
            yfinance_fallback_fn=_yf_window_fallback,
            conn=audit_conn,
            surface="pipeline",
            pipeline_run_id=pipeline_run_id,
            period_type="year",
            period=5,
            frequency_type="daily",
            frequency=1,
        )
        # Full-archive-return contract (CLAUDE.md: "cache hooks must return the
        # FULL archive; consumers slice"). On the schwab_api success path the
        # ladder's `window` is only the short freshly-fetched Schwab sub-window
        # (XMAX = 16 daily bars); the shared helper re-reads the full archive so
        # the pipeline thumbnail converges with the no-ladder ticker_detail path
        # and reports the effective provider of the returned bars. Full rationale
        # in resolve_full_archive_bars' docstring.
        bars, effective_provider = resolve_full_archive_bars(
            ticker, window, provider_tag,
            yfinance_window_fn=_yf_window_fallback,
        )
        return (bars, effective_provider)

    price_cache.set_ladder_fetcher(_quote_hook)
    ohlcv_cache.set_ladder_bars_fetcher(_bars_hook)

    return price_cache, ohlcv_cache, audit_conn


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


@contextlib.contextmanager
def _pipeline_yfinance_audit_scope(cfg: Config, lease):
    """Enter the pipeline-surface yfinance audit scope for the run body (Phase 18
    Arc 18-C). NO-RAISE production entry: if the scope guard rejects (a stray
    stale/overlapping scope), DEGRADE to the disabled overlay instead of
    stranding the lease OR misattributing rows to the stale context. An audit-
    context problem must NEVER wedge a pipeline lease nor misattribute its rows
    (Codex R10/R12)."""
    try:
        cm = yfinance_audit_scope(
            db_path=cfg.paths.db_path, pipeline_run_id=lease.run_id,
            surface="pipeline",
        )
        cm.__enter__()
    except Exception:  # noqa: BLE001 -- scope entry failed -> degrade to disabled
        log.warning(
            "yfinance audit scope entry failed for run %s; recording disabled "
            "for this run (no misattribution)", lease.run_id, exc_info=True,
        )
        with yfinance_audit_disabled():
            yield
        return
    try:
        yield
    finally:
        cm.__exit__(None, None, None)


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

    # Correlation (Arc-2 Slice-2): stamp the run id on every subsequent log record
    # in this process. CorrelationFilter reads it at filter() time from any thread
    # (incl. the price-fetch executor + threaded steps). The lease row is already
    # inserted at this point (acquire_lease returned).
    set_pipeline_run_id(lease.run_id)

    # Phase 18 Arc 18-C: tag every post-lease yfinance call surface='pipeline'
    with _pipeline_yfinance_audit_scope(cfg, lease):
        hb = Heartbeat(lease=lease, interval_seconds=cfg.pipeline.heartbeat_interval_seconds)
        hb.start()

        fetcher = PriceFetcher(
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
        )
        eval_run_id = 0
        # OQ-C: the single shared serialized audit-writer connection (opened in
        # _install_pipeline_marketdata_caches when a Schwab client exists). Init to
        # None so the run finally can close it unconditionally.
        audit_conn = None
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
                with step_guard(lease, "weather", status_key="weather_status", logger=log):
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
                price_cache, ohlcv_cache, audit_conn = _install_pipeline_marketdata_caches(
                    cfg, schwab_client, pipeline_run_id=lease.run_id,
                )
                if ohlcv_cache is None:
                    from swing.web.ohlcv_cache import OhlcvCache
                    ohlcv_cache = OhlcvCache(cfg)

                # Phase 14 Sub-bundle 2 (FB-N6): run-level structured warnings
                # accumulator. Steps append {step, reason, ...} dicts (gotcha #27
                # silent-skip-without-audit). Serialized to the completion
                # lease.release(warnings_json=...) below (None when empty, not
                # "[]" -- audit-envelope-empty-state gotcha).
                run_warnings: list[dict] = []

                lease.step("evaluate")
                try:
                    eval_run_id = _step_evaluate(
                        cfg=cfg, fetcher=fetcher, csv_path=csv_path,
                        universe=universe, universe_hash=universe_hash,
                        run_now=run_now, action_session=action_session,
                        lease=lease,
                        price_cache=price_cache,
                        run_warnings=run_warnings,
                    )
                    lease.status(evaluation_status="ok")
                except LeaseRevokedError:
                    raise
                except Exception as exc:
                    log.error("evaluation failed: %s", exc)
                    lease.status(evaluation_status="failed")
                    lease.release(state="failed", error_message=str(exc))
                    return RunResult(run_id=lease.run_id, state="failed", error_message=str(exc))

                # Cadence-step semantics: per-trade failures are already logged +
                # swallowed inside _step_daily_management. The guard's log_failure
                # catches programming errors (KeyError, ImportError, etc.) — pipeline
                # must continue regardless (byte-identical "programming error
                # (continuing)" warning text preserved via log_failure).
                with step_guard(
                    lease, "daily_management", logger=log,
                    log_failure=lambda lg, name, exc: lg.warning(
                        "daily_management step programming error (continuing): %s", exc),
                ):
                    _step_daily_management(
                        lease=lease, run_now=run_now, eval_run_id=eval_run_id,
                        archive_history_days=cfg.archive.archive_history_days,
                        ohlcv_archive_dir=cfg.paths.prices_cache_dir,
                        run_warnings=run_warnings,
                    )

                with step_guard(lease, "watchlist", status_key="watchlist_status", logger=log):
                    _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                                    data_asof_date=lease_data_asof(cfg, lease),
                                    lease=lease, run_warnings=run_warnings)

                with step_guard(lease, "recommendations",
                                status_key="recommendations_status", logger=log):
                    _step_recommendations(cfg=cfg, eval_run_id=eval_run_id,
                                           action_session=action_session,
                                           data_asof=lease_data_asof(cfg, lease),
                                           lease=lease)

                # Phase 13 T2.SB3 (plan section G.4 T-A.3.6) — pattern detect step.
                # Recon at docs/phase13-t2-sb3-recon.md section 2 binds the
                # insertion point: AFTER _step_recommendations + BEFORE the
                # Schwab snapshot block. Best-effort failure shape mirrors
                # _step_watchlist / _step_recommendations / _step_charts.
                with step_guard(lease, "pattern_detect", logger=log):
                    _step_pattern_detect(
                        cfg=cfg,
                        lease=lease,
                        eval_run_id=eval_run_id,
                        ohlcv_cache=ohlcv_cache,
                        run_warnings=run_warnings,
                    )

                # Phase 14 Sub-bundle 2 (T-2.5): forward-walk observe step. Appends
                # one pattern_forward_observations row per OPEN detection (today's
                # bar + lifecycle status). Best-effort failure shape mirrors
                # _step_pattern_detect (re-raise LeaseRevokedError; log.warning
                # others). Inserted AFTER pattern_detect, BEFORE schwab_snapshot.
                with step_guard(lease, "pattern_observe", logger=log):
                    _step_pattern_observe(
                        cfg=cfg, lease=lease, ohlcv_cache=ohlcv_cache,
                        run_warnings=run_warnings,
                    )

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
                with step_guard(
                    lease, "schwab_snapshot", logger=log,
                    log_failure=lambda lg, name, exc: lg.warning(
                        "schwab_snapshot failed (continuing pipeline): %s",
                        type(exc).__name__),
                ):
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

                with step_guard(
                    lease, "schwab_orders", logger=log,
                    log_failure=lambda lg, name, exc: lg.warning(
                        "schwab_orders failed (continuing pipeline): %s",
                        type(exc).__name__),
                ):
                    from swing.integrations.schwab.pipeline_steps import (
                        _step_schwab_orders,
                    )
                    # T-A.3 same fix family — wire schwab_client through.
                    _conn = connect(cfg.paths.db_path)
                    try:
                        _schwab_result = _step_schwab_orders(
                            _conn, cfg, pipeline_run_id=lease.run_id,
                            client=schwab_client, surface="pipeline",
                        )
                        # Arc 4b #27 — the step's cash_warnings reach the run-level
                        # run_warnings channel (persisted to pipeline_runs.warnings_json).
                        _schwab_warnings = (_schwab_result or {}).get("warnings") or []
                        if _schwab_warnings:
                            run_warnings.extend(_schwab_warnings)
                    finally:
                        _conn.close()

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

                with step_guard(lease, "export", status_key="export_status", logger=log):
                    _step_export(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                                 action_session=action_session,
                                 data_asof=lease_data_asof(cfg, lease),
                                 chart_paths=chart_paths,
                                 fetcher=fetcher)

                # Phase 16 Arc 5 -- shadow-expectancy drumbeat (commission
                # docs/phase16-shadow-expectancy-drumbeat-integration-commissioning-brief.md).
                # Last functional step: run the read-only engine over the
                # just-completed session so expectancy evidence accrues every
                # nightly run unattended. Best-effort (mirrors weather/observe):
                # re-raise LeaseRevokedError, warn on any other programming error
                # -- never fails the run. lease.step() first for the free Arc-1
                # pipeline_step_timings row + breadcrumb.
                lease.step("shadow_expectancy")
                try:
                    _step_shadow_expectancy(cfg=cfg, run_warnings=run_warnings)
                except LeaseRevokedError:
                    raise
                except Exception as exc:
                    # The step self-audits its expected failure modes to
                    # run_warnings; this catches any UNEXPECTED programming error and
                    # still surfaces it in the run envelope (gotcha #27), never
                    # failing the run.
                    log.warning("shadow_expectancy failed: %s", exc)
                    run_warnings.append({
                        "step": "shadow_expectancy",
                        "reason": "unexpected step error",
                        "detail": _shadow_expectancy_tail(str(exc)),
                    })

                # Read-only research data-collection-health roll-up (18-D §6.7):
                # runs after shadow_expectancy so it reads the freshly-emitted
                # engine manifest, BEFORE complete. BARE B-shape step_guard (NO
                # status_key per the O1 ruling -- a status_key would trip
                # update_status_columns' allowed-set + need a pipeline_runs column):
                # LeaseRevokedError propagates, all else swallowed+logged, the run
                # is never failed. Writes ONLY latest.json, NEVER the DB.
                with step_guard(lease, "research_health", logger=log):
                    _step_research_health(cfg=cfg)

                lease.step("complete")
                try:
                    _step_review_log_cadence(lease=lease)
                except LeaseRevokedError:
                    raise
                except Exception as exc:
                    # Cadence pre-create is auxiliary — its failure must NOT roll back the
                    # primary value chain (briefing emission). Log + continue. Brief §6.2
                    # watch item 13. (17-D.3: revoke now propagates like every other step.)
                    log.warning("review_log cadence step failed (continuing): %s", exc)
                lease.release(
                    state="complete",
                    warnings_json=(json.dumps(run_warnings) if run_warnings else None),
                )
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
            try:
                lease.flush_step_timings()
            except Exception as exc:
                log.error("step-timing flush failed: %s", exc)
            # OQ-C: close the single shared serialized audit-writer connection.
            if audit_conn is not None:
                audit_conn.close()

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


# Phase 16 Arc 5 — shadow-expectancy drumbeat tunables.
SHADOW_EXPECTANCY_TIMEOUT_S = 300
_SHADOW_EXPECTANCY_KEEP = 90


def _shadow_expectancy_tail(text, *, limit: int = 512) -> str:
    """Collapse newlines + cap length for a redaction-safe run_warnings detail.

    The engine handles no secrets, but we mirror the combined-message tail
    pattern used elsewhere (cap ~512 + single-space collapse) so a noisy
    stderr cannot bloat the warnings envelope."""
    if not text:
        return ""
    return " ".join(str(text).split())[-limit:]


def _attributed_card_count(card) -> int:
    """Sum the leaf signal counts of one ``per_hypothesis`` card.

    The real producer (research/harness/shadow_expectancy/funnel.py) emits each
    hypothesis card as a nested dict
    ``{closed, open_at_horizon, never_triggered, excluded: {reason: int}}`` --
    NOT a bare int. The flat keys are counts; ``excluded`` is itself a per-reason
    breakdown. Tolerant of unexpected key shapes (skip non-numeric leaves)."""
    if not isinstance(card, dict):
        return 0
    total = 0
    for key, value in card.items():
        if key == "excluded" and isinstance(value, dict):
            total += sum(int(v) for v in value.values())
        elif isinstance(value, bool):
            continue
        elif isinstance(value, (int, float)):
            total += int(value)
    return total


def _parse_shadow_manifest_path(stdout) -> Path | None:
    """Extract the manifest path the CLI echoes (``manifest.json:   <path>``).

    Locked artifact-dir mechanism (dispatch brief §3.3): the CLI emits the
    absolute manifest path on stdout deterministically, so we read it directly
    rather than racing the filesystem for the newest dir (robust to a
    concurrent manual run). ``split(":", 1)`` is drive-letter safe on Windows."""
    if not stdout:
        return None
    for line in str(stdout).splitlines():
        if line.startswith("manifest.json:"):
            rest = line.split(":", 1)[1].strip()
            if rest:
                return Path(rest)
    return None


def _prune_shadow_expectancy_artifacts(
    output_root: Path, *, keep: int = _SHADOW_EXPECTANCY_KEEP
) -> None:
    """Keep-last-N prune of ``shadow-expectancy-*`` dirs only (brief §3.4).

    Best-effort: a prune failure logs + returns, never fails the step. The UTC
    basic-timestamp dir names sort lexically == chronologically, so a reverse
    name-sort is newest-first. Matches ONLY the ``shadow-expectancy-*`` prefix
    (never any other research export)."""
    try:
        dirs = sorted(
            (p for p in output_root.glob("shadow-expectancy-*") if p.is_dir()),
            key=lambda p: p.name, reverse=True,
        )
        for stale in dirs[keep:]:
            shutil.rmtree(stale, ignore_errors=True)
    except OSError as exc:
        log.warning("shadow_expectancy: artifact prune failed: %s", exc)


def _step_shadow_expectancy(*, cfg, run_warnings: list[dict]) -> None:
    """Best-effort drumbeat: run the read-only shadow-expectancy engine over the
    just-completed session and relay a one-line funnel summary into pipeline.log.

    Last functional step (after export, before complete) so a slow/failed shadow
    run never delays or damages the briefing/charts/export chain (commission §1).
    The installed CLI is invoked as a subprocess via the interpreter
    (``-m swing.cli``) -- robust to PATH in the spawned-pipeline context, NOT
    relying on ``swing.exe`` -- against ``cfg.paths.db_path``, writing to the
    project-root ``exports/research`` (where the operator's manual runs land).

    The engine opens the DB read-only (``mode=ro`` URI) under WAL, so a
    concurrent lease heartbeat write does not block it; any residual transient
    lock surfaces as a nonzero exit -> a warned failure. NO retry machinery
    (locked design resolution §3.1).

    Failure tolerance (gotcha #27): nonzero exit / timeout / spawn error /
    missing-or-unparseable manifest -> ``log.warning`` + a ``run_warnings`` entry;
    NEVER fails the run. Zero unique signals -> a ``run_warnings`` entry
    (expected-vs-actual honest-empty audit). LeaseRevokedError is NOT caught here
    (the subprocess except clause is targeted, not broad) -> it propagates to the
    runner wiring which re-raises it (standard best-effort shape)."""
    output_root = cfg.paths.exports_dir / "research"
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("shadow_expectancy: output dir %s unavailable: %s", output_root, exc)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "output dir unavailable",
            "detail": _shadow_expectancy_tail(str(exc)),
        })
        return

    argv = [
        sys.executable, "-m", "swing.cli", "diagnose", "shadow-expectancy",
        "--db", str(cfg.paths.db_path),
        "--output-dir", str(output_root),
    ]
    try:
        proc = subprocess.run(
            argv, capture_output=True, encoding="utf-8", errors="replace",
            timeout=SHADOW_EXPECTANCY_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        log.warning("shadow_expectancy: timed out after %ss (child killed)",
                    SHADOW_EXPECTANCY_TIMEOUT_S)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "engine timed out",
            "detail": _shadow_expectancy_tail(exc.stderr),
        })
        return
    except OSError as exc:
        log.warning("shadow_expectancy: subprocess spawn failed: %s", exc)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "subprocess spawn failed",
            "detail": _shadow_expectancy_tail(str(exc)),
        })
        return

    if proc.returncode != 0:
        log.warning("shadow_expectancy: engine exited %s", proc.returncode)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": f"engine exited {proc.returncode}",
            "detail": _shadow_expectancy_tail(proc.stderr),
        })
        return

    manifest_path = _parse_shadow_manifest_path(proc.stdout)
    if manifest_path is None or not manifest_path.is_file():
        log.warning("shadow_expectancy: manifest missing after zero-exit run")
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "manifest missing after zero-exit run",
            "detail": _shadow_expectancy_tail(proc.stdout),
        })
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("shadow_expectancy: manifest unparseable: %s", exc)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "manifest unparseable",
            "detail": _shadow_expectancy_tail(str(exc)),
        })
        return

    try:
        funnel = manifest.get("funnel", {}) or {}
        detection = funnel.get("detection_level", {}) or {}
        total = int(detection.get("total_detections", 0) or 0)
        unique = int(detection.get("unique_signals", 0) or 0)
        # The REAL per_hypothesis value is a nested card
        # {closed, open_at_horizon, never_triggered, excluded:{reason:int}}
        # (research/harness/shadow_expectancy/funnel.py) -- NOT a bare int.
        # Sum the leaf counts (excluded is itself a per-reason breakdown).
        attributed = sum(
            _attributed_card_count(c)
            for c in (funnel.get("per_hypothesis", {}) or {}).values()
        )
        # unattributed is a flat {reason: int} bucket -> sum its values.
        unattributed = sum(
            int(v) for v in (funnel.get("unattributed", {}) or {}).values()
        )
    except (AttributeError, TypeError, ValueError) as exc:
        # Manifest parsed but the funnel shape is not what we expect (e.g. a
        # future producer change). Surface it (gotcha #27) rather than letting
        # an uncaught error escape to a log-only outer wrapper.
        log.warning("shadow_expectancy: manifest funnel shape unexpected: %s", exc)
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "manifest funnel shape unexpected",
            "detail": _shadow_expectancy_tail(str(exc)),
        })
        return
    log.info(
        "shadow_expectancy: total_detections=%d unique_signals=%d "
        "attributed=%d unattributed=%d artifact=%s",
        total, unique, attributed, unattributed, manifest_path.parent.name,
    )
    if unique == 0:
        # Gotcha #27: the engine ran fine but produced an empty funnel --
        # honest output, surfaced not silent. A zero-PRICED (but nonzero-signal)
        # run is NOT warned -- that is the honest funnel.
        run_warnings.append({
            "step": "shadow_expectancy",
            "reason": "engine produced zero unique signals",
            "total_detections": total,
            "unique_signals": unique,
        })

    _prune_shadow_expectancy_artifacts(output_root)


def _step_research_health(*, cfg) -> None:
    """Best-effort nightly research-data-collection-health roll-up (18-D §6.7).

    Runs the SAME read-only ``compute_research_health`` the script runs, then
    single-sources the atomic ``latest.json`` write via
    ``write_research_health_artifact`` -- the artifact 18-F's research stoplight
    consumes. Placed immediately AFTER ``_step_shadow_expectancy`` (so it reads
    the freshly-emitted engine manifest) and BEFORE ``complete``.

    C-NH2 (read-only): opens a SEPARATE ``mode=ro`` URI conn (mirrors
    scripts/research_health.py) -- NEVER the runner's read-write ``connect()``;
    only ``latest.json`` is written, NEVER the measurement DB.

    C-NH5 (write-nothing-on-failure): the status is COMPUTED FIRST and only on
    SUCCESS does the writer run -- any exception in the ``mode=ro`` connect or
    inside compute propagates to the ``step_guard`` BEFORE any write, leaving the
    prior ``latest.json`` untouched. The writer is itself atomic (tmp + os.replace)
    so even a write-time crash never leaves a partial artifact.

    Wrapped at the call site by the BARE B-shape ``step_guard`` (NO status_key --
    the O1 resolution): ``LeaseRevokedError`` propagates, all other exceptions are
    swallowed + logged; the step NEVER fails the run.
    """
    from swing.monitoring.research_health import (
        compute_research_health,
        write_research_health_artifact,
    )
    ro_uri = cfg.paths.db_path.as_uri() + "?mode=ro"  # C-NH2 (mirror the script)
    conn = sqlite3.connect(ro_uri, uri=True, timeout=2.0)
    try:
        # Read the manifests from EXACTLY the root _step_shadow_expectancy just
        # wrote to (cfg.paths.exports_dir / "research"), so the #2/#5
        # manifest-consuming checks see the freshly-emitted run regardless of the
        # configured exports_dir. In the shipped prod config this equals the
        # contract default (RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent); passing
        # it explicitly de-couples correctness from that coincidence (Codex R1).
        status = compute_research_health(
            conn, cfg=cfg, exports_root=cfg.paths.exports_dir / "research")
    finally:
        conn.close()
    write_research_health_artifact(status)  # C-NH4 default = the contract latest.json


def _prewarm_evaluate_archives(
    *, cfg, candidate_tickers: list[str], universe_tickers: list[str],
    run_now, run_warnings: list[dict] | None,
) -> None:
    """Arc 6: ONE batched gap pre-warm before the serial evaluate loops, so each
    of the three serial fetch loops hits the cache-hit branch (zero per-ticker
    round-trips). PURE ACCELERATOR — any miss falls through to the serial path;
    a wholesale failure is caught + #27-audited, never sinks evaluate.

    `run_now` is accepted for the documented end_date symmetry (the warm anchors
    writes on _last_completed_session_today() internally — see warm_archives_batch
    docstring; end_date is a signature-contract value the warm does not use for
    writes); pass None in unit tests."""
    from datetime import datetime

    from swing.evaluation.dates import last_completed_session
    warm_set = [cfg.rs.benchmark_ticker, *candidate_tickers, *universe_tickers]
    try:
        end_date = last_completed_session(run_now if run_now is not None else datetime.now())
        report = warm_archives_batch(
            warm_set,
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001 — warm is best-effort; never sink evaluate
        log.warning("evaluate warm failed wholesale (serial loops will refetch): %s", exc)
        if run_warnings is not None:
            run_warnings.append({
                "step": "evaluate_warm",
                "reason": "warm raised wholesale: " + " ".join(str(exc).split())[:200],
            })
        return
    # Always-on cohort telemetry (Arc 6 §6 R1 Minor #1) — a misbucketing bug that
    # looks "clean" (zero fallbacks) is still visible as an anomalous distribution.
    log.info(
        "evaluate warm: cache_hit=%d gap=%d deep_gap=%d full_refresh=%d "
        "chunks=%d chunk_failures=%d fallback=%d trimmed=%d wall=%.1fs",
        report.cache_hit, report.gap, report.deep_gap, report.full_refresh,
        report.chunks_attempted, report.chunk_failures, len(report.fallback),
        report.trailing_nan_trimmed, report.wall_seconds,
    )
    # Arc 8 (#27): trailing-ragged trims at the warm write barrier are a state
    # event worth surfacing even when the warm is otherwise clean — a yfinance
    # raggedness night should leave an audit trail, not vanish.
    if report.trailing_nan_trimmed > 0 and run_warnings is not None:
        run_warnings.append({
            "step": "evaluate_warm",
            "reason": "trailing-ragged bars trimmed at warm write barrier "
                      "(retried next fetch)",
            "trailing_nan_trimmed": report.trailing_nan_trimmed,
        })
    if report.degraded and run_warnings is not None:
        run_warnings.append({
            "step": "evaluate_warm",
            "reason": "warm degraded; affected tickers re-fetched serially",
            "fallback_count": len(report.fallback),
            "chunk_failures": report.chunk_failures,
            "cache_hit": report.cache_hit,
            "gap": report.gap,
            "deep_gap": report.deep_gap,
            "full_refresh": report.full_refresh,
        })


def _step_evaluate(
    *, cfg, fetcher, csv_path: Path, universe, universe_hash: str,
    run_now: _dt, action_session: _date, lease: Lease,
    price_cache=None, run_warnings: list[dict] | None = None,
) -> int:
    # Arc 17-A: this is the PIPELINE adapter over the shared orchestrator
    # (swing.evaluation.orchestration.orchestrate_evaluation). It assembles the
    # genuinely-pipeline-specific seams and delegates; the CLI (swing eval) is a
    # sibling adapter over the same orchestrator. The run-level `action_session`
    # captured by the caller is FORWARDED to the orchestrator (which derives it
    # from run_now only when None -- the CLI path). run_pipeline passes
    # action_session_for_run(run_now), so production is byte-identical; do NOT
    # drop the forward (a direct caller may pass a different session). See
    # docs/phase17-arc-a-task-c-divergence-rulings.md.
    lease.verify_held()

    # --- Universe augmentation: held (close-only) + pinned (full eval). ---
    # Open-trade tickers keep their fresh close in candidates.close
    # (PriceCache._last_close reads that table; a position rotated off the finviz
    # screen would otherwise show a stale close on the dashboard).
    open_conn = connect(cfg.paths.db_path)
    try:
        held_tickers: list[str] = sorted({
            t.ticker.upper() for t in list_open_trades(open_conn)
        })
    finally:
        open_conn.close()
    # Arc 7: union PINNED watchlist tickers so a tracked name stays fetched +
    # fully evaluated even off-screen. The orchestrator de-dupes pins already in
    # the screen∪held set and fires the pin_injection warning for the remainder.
    pin_conn = connect(cfg.paths.db_path)
    try:
        pinned_eval_tickers = sorted({
            e.ticker.upper() for e in list_active_watchlist(pin_conn) if e.pinned
        })
    finally:
        pin_conn.close()
    augmentation = UniverseAugmentation(
        held_tickers=tuple(held_tickers),
        pinned_inject=tuple(pinned_eval_tickers),
    )

    # --- current_equity: real-equity sizing (DIVERGENCE-EQUITY, ruled unify). ---
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

    # --- LOCK #16: warm + prewarm fire at the held-tickers boundary. The warm
    # gets the captured HELD set; the prewarm gets the merged screen∪held∪pins
    # set (the orchestrator's argument) as candidate_tickers + universe.tickers
    # separately -- the two take DIFFERENT argument sets (Codex R2), reproduced
    # verbatim. ---
    def _pre_fetch_hook(merged_tickers: list[str]) -> None:
        # Phase 11 Sub-bundle C T-C.6 — market-data ladder per open-trade ticker
        # via the (optional) installed PriceCache; a no-op when price_cache is
        # None. Sandbox short-circuit at the ladder layer → ZERO audit rows.
        _warm_pipeline_marketdata(
            cfg=cfg, price_cache=price_cache, held_tickers=held_tickers,
        )
        # Arc 6: batched gap pre-warm before the serial fetch loops.
        _prewarm_evaluate_archives(
            cfg=cfg, candidate_tickers=merged_tickers,
            universe_tickers=universe.tickers, run_now=run_now,
            run_warnings=run_warnings,
        )

    # --- output seam: emit the pin_injection run-warning (exact dict shape). ---
    def _note_pin_injection(injected: list[str]) -> None:
        if run_warnings is not None:
            run_warnings.append({
                "step": "evaluate", "kind": "pin_injection",
                "count": len(injected), "tickers": injected,
            })

    output = OrchestrationOutput(note_pin_injection=_note_pin_injection)

    # --- persist seam (LOCK #1): lease/fence + eval-run binding stay HERE; the
    # orchestrator never imports Lease. ---
    def _persist(run, candidates) -> int:
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

    result = orchestrate_evaluation(
        cfg=cfg, csv_path=csv_path, universe=universe, universe_hash=universe_hash,
        run_now=run_now, fetcher=fetcher, current_equity=sizing_eq,
        persist=_persist, as_of_date=None,
        # Honor the run-level action_session the caller captured (byte-faithful to
        # the pre-refactor _step_evaluate, which persisted the passed value).
        action_session=action_session,
        augmentation=augmentation,
        pre_fetch_hook=_pre_fetch_hook, output=output,
        # DIVERGENCE-SPY-GUARD ruled intentional: the pipeline hard-fails on a
        # SPY fetch exception (RS rankings are meaningless without SPY).
        behavior=EvaluationBehaviorPolicy(spy_failure_mode="raise"),
    )
    return result.run_id


def _step_watchlist(
    *, cfg, eval_run_id: int, data_asof_date: str, lease: Lease,
    run_warnings: list[dict] | None = None,
) -> None:
    from swing.data.repos.candidates import fetch_candidates_for_run
    # Read phase (no fence — reading is idempotent).
    read_conn = connect(cfg.paths.db_path)
    try:
        prior = list_active_watchlist(read_conn)
        candidates = fetch_candidates_for_run(read_conn, eval_run_id)
    finally:
        read_conn.close()
    # Arc 7: pinned tickers veto the nightly age-off. Derive the pin set from
    # the live watchlist and pass it to the service so a pinned removal-grade
    # ticker is diverted into suppressed_removes + a streak_increment instead
    # of an archive (the archive would DELETE the live row the operator pinned).
    pinned_tickers = frozenset(e.ticker for e in prior if e.pinned)
    delta = compute_watchlist_changes(
        prior=prior, today_candidates=candidates,
        data_asof_date=data_asof_date, pinned_tickers=pinned_tickers,
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
    # #27: a suppressed removal is NOT archived (that would delete the live
    # row); emit a per-ticker run-warning so the pin veto is auditable, not
    # silent. The archive reason is
    # "aged out (failed stable {new_streak} consecutive runs)" so
    # sup.reason.split()[-3] == the streak int.
    if run_warnings is not None:
        for sup in delta.suppressed_removes:
            run_warnings.append({
                "step": "watchlist", "kind": "pin_suppressed_removal",
                "ticker": sup.ticker,
                "streak": int(sup.reason.split()[-3]) if sup.reason else None,
                "detail": "pin prevented age-off",
            })


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

# 5 V1 detectors run in deterministic order per recon section 3
# (vcp -> flat_base -> cup_with_handle -> high_tight_flag ->
# double_bottom_w). Wired as a tuple so iteration order is stable
# across runs (recon section 3 forbids `set` iteration).
#
# T2.SB3 (T-A.3.6) landed the first 3 detectors; T2.SB4 (T-A.4.3)
# extends the registry to 5 by adding HTF + DBW. Data-driven extension
# via the registry tuple alone -- the consumer loop at
# `_step_pattern_detect` (line ~1599) iterates `detectors` generically
# (no per-detector if/elif branches). All 5 detectors share the same
# kwargs contract: `(bars, candidate_window, *, conn, ticker, asof_date)`
# returning a frozen `*Evidence` dataclass.
def _pattern_detect_registry():
    """Return [(detector_callable, pattern_class, version_str), ...].

    Imported lazily to keep runner module import cheap when pattern
    detection is skipped (zero candidates / cfg-disabled future flag).
    """
    from swing.patterns.cup_with_handle import (
        DETECTOR_VERSION as CUP_VERSION,
    )
    from swing.patterns.cup_with_handle import detect_cup_with_handle
    from swing.patterns.double_bottom_w import (
        DETECTOR_VERSION as DBW_VERSION,
    )
    from swing.patterns.double_bottom_w import detect_double_bottom_w
    from swing.patterns.flat_base import (
        DETECTOR_VERSION as FLAT_VERSION,
    )
    from swing.patterns.flat_base import detect_flat_base
    from swing.patterns.high_tight_flag import (
        DETECTOR_VERSION as HTF_VERSION,
    )
    from swing.patterns.high_tight_flag import detect_high_tight_flag
    from swing.patterns.vcp import DETECTOR_VERSION as VCP_VERSION
    from swing.patterns.vcp import detect_vcp

    return (
        (detect_vcp, "vcp", VCP_VERSION),
        (detect_flat_base, "flat_base", FLAT_VERSION),
        (detect_cup_with_handle, "cup_with_handle", CUP_VERSION),
        (detect_high_tight_flag, "high_tight_flag", HTF_VERSION),
        (detect_double_bottom_w, "double_bottom_w", DBW_VERSION),
    )


class EvalRunResolutionError(Exception):
    """Raised when ``_resolve_eval_run_action_session_date`` cannot
    determine the canonical run-anchored ``action_session_date``.

    Codex R2 Major #3: the prior implementation fell back to
    wall-clock ``datetime.now(UTC).date()`` on row-missing or
    malformed metadata. That fallback reintroduced the very
    future-stage leak the Codex R1 Major #2 fix was meant to harden.
    The fallback is REMOVED; raise this typed exception instead.

    The best-effort wrapper around ``_step_pattern_detect`` at
    ``runner.py:819-834`` catches it, logs WARNING, and SKIPS pattern
    detection for the run (zero rows written).
    """


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

    Codex R2 Major #3: removed wall-clock fallback on row-missing or
    malformed action_session_date. Raises ``EvalRunResolutionError``
    instead; the best-effort wrapper at runner.py:819-834 catches it
    and SKIPS pattern detection for the run (zero rows written).
    """
    from datetime import date as _date_cls

    iso: str | None = None
    read_conn = connect(cfg.paths.db_path) if cfg is not None else None
    _opened_conn = read_conn is not None
    try:
        if read_conn is None:
            # Test-stub path: reuse the lease's shared conn for read
            # WITHOUT entering fenced_write (which would issue BEGIN
            # IMMEDIATE -- Codex R2 Major #1 keeps Pass 1 lock-free).
            read_conn = getattr(lease, "_conn", None)
        if read_conn is not None:
            row = read_conn.execute(
                "SELECT action_session_date FROM evaluation_runs WHERE id = ?",
                (eval_run_id,),
            ).fetchone()
        else:
            # Defensive: no cfg AND no shared lease conn.
            with lease.fenced_write() as _conn:
                row = _conn.execute(
                    "SELECT action_session_date FROM evaluation_runs "
                    "WHERE id = ?",
                    (eval_run_id,),
                ).fetchone()
        if row is not None and row[0] is not None:
            iso = str(row[0])
    finally:
        if _opened_conn and read_conn is not None:
            read_conn.close()

    if iso is None:
        log.warning(
            "pattern_detect: evaluation_runs row missing or "
            "action_session_date NULL for eval_run_id=%d; aborting "
            "pattern detection for this run",
            eval_run_id,
        )
        raise EvalRunResolutionError(
            f"evaluation_runs row missing or action_session_date NULL "
            f"for eval_run_id={eval_run_id}"
        )
    try:
        return _date_cls.fromisoformat(iso)
    except ValueError as exc:
        log.warning(
            "pattern_detect: evaluation_runs.action_session_date "
            "unparseable (%r) for eval_run_id=%d; aborting pattern "
            "detection for this run",
            iso,
            eval_run_id,
        )
        raise EvalRunResolutionError(
            f"evaluation_runs.action_session_date unparseable ({iso!r}) "
            f"for eval_run_id={eval_run_id}"
        ) from exc


def _step_pattern_detect(
    *,
    cfg,
    lease: Lease,
    eval_run_id: int,
    ohlcv_cache,
    run_warnings: list[dict] | None = None,
) -> None:
    """Run 5 V1 geometric detectors over the Stage-2-filtered candidate pool.

    Per recon section 1-9 (docs/phase13-t2-sb3-recon.md) + T2.SB4
    T-A.4.3 extension:
    - Pool predicate: candidates.bucket == 'aplus' (Stage-2 + RS-rank-filtered).
    - Per-ticker: fetch bars via `ohlcv_cache.get_or_fetch`; generate
      candidate windows (zigzag_pivot mode); run all 5 detectors on each
      window's evidence-emit; write one `pattern_evaluations` row per
      (pipeline_run_id, ticker, pattern_class) tuple. T2.SB3 shipped
      the first 3 detectors (vcp, flat_base, cup_with_handle); T2.SB4
      T-A.4.3 added high_tight_flag + double_bottom_w via a single
      registry tuple extension (no consumer-loop change).
    - SELECT-then-INSERT idempotency (LOCK L3 forbids INSERT OR REPLACE).
    - pipeline_run_id := lease.run_id (NOT eval_run_id) per recon section 8.
    - NO sandbox gating (recon section 6): pattern_evaluations is an
      internal-derivation surface; bars-source ladder already handles sandbox.
    - Per-detector failures are isolated + logged WARNING; the step
      continues (recon section 4.4).

    Connection contract (Codex R3 Minor #1 ACCEPT-WITH-RATIONALE):
    The production caller ALWAYS passes a non-None ``cfg`` -- the
    cfg-path branches open dedicated read-only connections via
    ``connect(cfg.paths.db_path)``. The ``cfg is None`` test-stub path
    reuses the lease's shared ``_conn`` attribute (set by
    ``_StubLease``) for read-only SELECTs WITHOUT entering
    ``lease.fenced_write()`` (which would needlessly issue BEGIN
    IMMEDIATE). The defensive ``fenced_write`` fallback at
    eval-run resolution + candidate read + histogram-seed read fires
    ONLY when (a) cfg is None AND (b) lease has no ``_conn`` attribute
    -- a path that NO production caller AND NO current test fixture
    exercises. This is a defense-in-depth fallback; if a future test
    fixture lands here, the BEGIN IMMEDIATE around a read is a tiny
    correctness-preserving overhead, not a functional defect.
    """
    import dataclasses
    import json as _json
    from datetime import datetime as _dt_inner

    import pandas as pd

    from swing.data.models import PatternDetectionEvent, PatternEvaluation
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.pattern_detection_events import insert_detection_event
    from swing.data.repos.pattern_evaluations import insert_evaluation
    from swing.data.repos.pattern_exemplars import list_exemplars
    from swing.patterns.drift_logging import capture_feature_distribution
    from swing.patterns.foundation import generate_candidate_windows
    from swing.pipeline.temporal_metadata import (
        build_finviz_screen_state,
        build_per_pattern_metadata,
        build_structural_anchors_json,
    )

    pipeline_run_id = lease.run_id

    # Read phase (no fence -- idempotent SELECT).
    # Codex R2 Major #1: do NOT enter ``lease.fenced_write()`` here for
    # the test-stub path; that would issue BEGIN IMMEDIATE before Pass 1.
    # Borrow the lease's underlying connection for the read instead.
    read_conn = connect(cfg.paths.db_path) if cfg is not None else None
    try:
        if read_conn is not None:
            candidates = fetch_candidates_for_run(read_conn, eval_run_id)
        else:
            # Test-stub path: single-connection in-memory test fixtures
            # expose the shared sqlite3.Connection as ``lease._conn``.
            lease_conn = getattr(lease, "_conn", None)
            if lease_conn is None:
                # Defensive fallback (no shared conn attribute): enter
                # fenced_write briefly. This will issue BEGIN IMMEDIATE
                # but only in code paths without a cfg AND without an
                # in-memory test stub -- not a production path.
                with lease.fenced_write() as _read_via_lease:
                    candidates = fetch_candidates_for_run(
                        _read_via_lease, eval_run_id
                    )
            else:
                candidates = fetch_candidates_for_run(lease_conn, eval_run_id)
    finally:
        if read_conn is not None:
            read_conn.close()

    # Pool predicate (pool-widening 2026-06-04): Stage-2-filtered +
    # RS-rank-filtered candidates = aplus|watch buckets (Stage-2 passers;
    # watch differs only in VCP-tightness). The observation log accumulates
    # the ~83x watch population as forward-walk data; the widen is kept
    # invisible to operator-facing surfaces via the provable-aplus consumer
    # isolation (swing/evaluation/pe_origin.py).
    detect_pool_tickers: list[str] = [
        c.ticker for c in candidates if c.bucket in ("aplus", "watch")
    ]

    if not detect_pool_tickers:
        log.info(
            "pattern_detect: no candidate windows -- zero detect-pool "
            "(aplus|watch) tickers; skipping (no writes)"
        )
        # Gotcha #27: an empty-pool early-return inside a best-effort step
        # must emit a warnings_json audit entry (expected vs actual pool +
        # reason) so a zero-work completion is not silent.
        if run_warnings is not None:
            _aplus_n = sum(1 for c in candidates if c.bucket == "aplus")
            _watch_n = sum(1 for c in candidates if c.bucket == "watch")
            run_warnings.append({
                "step": "pattern_detect",
                "expected_pool": len(candidates),
                "expected_detect_pool": _aplus_n + _watch_n,
                "expected_pool_by_bucket": {"aplus": _aplus_n, "watch": _watch_n},
                "actual_pool": len(detect_pool_tickers),
                "actual_pool_by_bucket": {"aplus": _aplus_n, "watch": _watch_n},
                "reason": "zero aplus|watch candidates",
            })
        return

    # Dormant Lever 1 (pool-widening 2026-06-04): cap the watch detect pool.
    # Fires AFTER the raw-empty guard (the raw pool is non-empty here), so the
    # empty-pool path always emits the empty-pool audit, never the cap audit.
    # aplus is NEVER capped; watch is ranked by rs_rank ASC (deterministic,
    # reproducible) + truncated to the cap. Because aplus is uncapped and
    # cap >= 1, a non-empty raw pool stays non-empty post-cap (no double-emit).
    _cap = getattr(cfg.pipeline, "detect_watch_pool_cap", None) if cfg else None
    if _cap is not None:
        _aplus = [c for c in candidates if c.bucket == "aplus"]
        _watch = sorted((c for c in candidates if c.bucket == "watch"),
                        key=lambda c: c.rs_rank)  # lowest rs_rank first
        _kept_watch = _watch[:_cap]
        _capped = [c.ticker for c in _aplus] + [c.ticker for c in _kept_watch]
        if len(_capped) < len(detect_pool_tickers) and run_warnings is not None:
            run_warnings.append({
                "step": "pattern_detect",
                "expected_pool": len(candidates),
                "expected_detect_pool": len(detect_pool_tickers),
                "expected_pool_by_bucket": {
                    "aplus": len(_aplus), "watch": len(_watch)},
                "actual_pool": len(_capped),
                "actual_pool_by_bucket": {
                    "aplus": len(_aplus), "watch": len(_kept_watch)},
                "dropped_count": len(detect_pool_tickers) - len(_capped),
                "dropped_bucket": "watch",
                "reason": (f"watch detect pool capped at {_cap} "
                           "(cfg.pipeline.detect_watch_pool_cap)"),
            })
        detect_pool_tickers = _capped

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

    # Codex R2 Major #2 (Option B): seed ``composite_scores`` from any
    # pre-existing pattern_evaluations rows for THIS pipeline_run_id, so
    # newly-inserted rows on a partial retry carry a histogram that
    # represents the FULL universe (already-inserted + newly-inserted).
    #
    # On first run this SELECT returns an empty result set, seeding an
    # empty list (semantically equivalent to the V1 init). This is a
    # READ-ONLY operation; it runs OUTSIDE the write transaction.
    existing_composite_scores: list[float] = []
    existing_idempotency_keys: set[tuple[str, str]] = set()
    read_conn_for_seed = connect(cfg.paths.db_path) if cfg is not None else None
    _opened_seed_conn = read_conn_for_seed is not None
    try:
        if read_conn_for_seed is None:
            # Test-stub path: reuse the lease's shared conn for read
            # WITHOUT entering fenced_write (which would issue BEGIN
            # IMMEDIATE).
            read_conn_for_seed = getattr(lease, "_conn", None)
        if read_conn_for_seed is not None:
            seed_rows = read_conn_for_seed.execute(
                "SELECT ticker, pattern_class, composite_score "
                "FROM pattern_evaluations WHERE pipeline_run_id = ?",
                (pipeline_run_id,),
            ).fetchall()
        else:
            # Defensive: no cfg AND no shared lease conn -- fall back
            # to a brief fenced_write read (not a production path).
            with lease.fenced_write() as _seed_conn:
                seed_rows = _seed_conn.execute(
                    "SELECT ticker, pattern_class, composite_score "
                    "FROM pattern_evaluations WHERE pipeline_run_id = ?",
                    (pipeline_run_id,),
                ).fetchall()
        import contextlib as _contextlib
        for sr_ticker, sr_pattern_class, sr_score in seed_rows:
            existing_idempotency_keys.add((str(sr_ticker), str(sr_pattern_class)))
            # Defensive: if score is NULL/garbage, skip the score but
            # still record the idempotency key.
            with _contextlib.suppress(TypeError, ValueError):
                existing_composite_scores.append(float(sr_score))
    finally:
        # Close only the connection we OPENED (cfg path); never close
        # the lease-derived connection borrowed via getattr.
        if _opened_seed_conn and read_conn_for_seed is not None:
            read_conn_for_seed.close()

    # Universe context for FeatureDistributionLog (per spec section D.7).
    # Codex R1 Major #3 + R2 Major #2: ``composite_scores`` is seeded
    # from existing rows (Option B) then appended during pass 1.
    universe_context: dict = {
        "universe_size": len(detect_pool_tickers),
        "stage_2_pass_rate": 1.0,  # aplus|watch buckets imply Stage 2 pass.
        "rs_rank_distribution": {},
        "verdict_counts_per_pattern_class": {},
        "smoothing_params": {},
        "extrema_density_per_session": 0.0,
        "composite_scores": list(existing_composite_scores),
    }

    # ----------------------------------------------------------------------
    # Pass 1: detector invocations + composite_scores accumulation.
    # Codex R2 Major #1: Pass 1 runs OUTSIDE the write transaction.
    # Per-ticker OHLCV fetches + window generation + detector invocation
    # are all read-only operations; opening BEGIN IMMEDIATE here would
    # hold the lock across network/cache I/O.
    #
    # Detectors invoke ``current_stage`` read-only against ``conn``;
    # provide a dedicated read-only connection (cfg-path) or fall back
    # to the lease's underlying connection in the test-stub path.
    # ----------------------------------------------------------------------
    # Each per-(ticker, pattern_class) entry collects:
    #   (ticker, pattern_class, version_str, window, evidence,
    #    geometric_score, candidate_close_prices)
    # for pass 2 to consume. T2.SB5 T-A.5.4: composite_score is now
    # derived in Pass 2 AFTER template matching (was Pass 1 in T2.SB4
    # and earlier). candidate_close_prices is the bar Close-slice for
    # the candidate's window, used by match_forward in Pass 2.
    import numpy as _np_pd_inner
    emit_queue: list[
        tuple[str, str, str, object, object, float, _np_pd_inner.ndarray]
    ] = []

    # Phase 14 Sub-bundle 2 (T-2.4): retain the Pass-1 fetched bars so the
    # Pass-2 emit loop reuses them for per-pattern metadata + chart capture
    # WITHOUT a re-fetch (gotcha #5 + L2 LOCK). Keyed by ticker.
    bars_by_ticker: dict[str, pd.DataFrame] = {}

    detector_read_conn = connect(cfg.paths.db_path) if cfg is not None else None
    # Test-stub path: no cfg, so reuse the lease's underlying connection
    # for read-only detector lookups WITHOUT opening BEGIN IMMEDIATE
    # (the contextmanager exit would otherwise commit a no-op tx + the
    # spy lease records that as a BEGIN). We rely on the test fixture
    # exposing a shared sqlite3.Connection accessible as ``lease._conn``
    # OR via ``lease.fenced_write()`` -- we intentionally do NOT enter
    # the latter contextmanager here to keep Pass 1 lock-free.
    if detector_read_conn is None:
        detector_read_conn = getattr(lease, "_conn", None)

    try:
        for ticker in detect_pool_tickers:
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

            # T-2.4: retain for Pass-2 metadata + chart capture (no re-fetch).
            bars_by_ticker[ticker] = bars

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
                # Codex R2 Major #2 (Option B): if a row already exists
                # for this (pipeline_run_id, ticker, pattern_class)
                # tuple, skip the detector invocation entirely. The
                # pre-existing row's composite_score is already seeded
                # into universe_context. This is cheaper than the V1
                # SELECT-per-detector pattern and keeps Pass 1 fully
                # read-only.
                if (ticker, pattern_class) in existing_idempotency_keys:
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
                        conn=detector_read_conn,
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
                # T2.SB5 T-A.5.4: composite_score derivation MOVED to Pass 2
                # so template matching (which requires the canonical
                # pattern_exemplars corpus inside the lease-fenced read) can
                # contribute to the composite per spec section 5.8 formula.
                # Pre-T2.SB5 baseline at runner.py was
                # ``composite_score = min(1.0, geometric_score)`` here in
                # Pass 1 (the section 5.8 line 720 template=None fallback);
                # equivalent post-T2.SB5 behavior persists when match_forward
                # returns no hits via ``compute_composite_score(geo, None)``
                # which preserves the ``min(1.0, ...)`` wrap on the fallback
                # path (L5 LOCK; DBW evidence may reach 1.10).
                #
                # Slice the candidate's close-price series for template
                # matching in Pass 2. The candidate window's boundaries
                # come from the foundation primitive's emitted
                # ``CandidateWindow``; clipping inclusive on both ends
                # mirrors T2.SB3 detector entry discipline (L12).
                try:
                    _ts_start = pd.Timestamp(window.start_date)
                    _ts_end = pd.Timestamp(window.end_date)
                    _window_mask = (bars.index >= _ts_start) & (
                        bars.index <= _ts_end
                    )
                    _close_series = bars.loc[_window_mask, "Close"]
                    if hasattr(_close_series, "ndim") and _close_series.ndim == 2:
                        _close_series = _close_series.iloc[:, 0]
                    candidate_close_prices = _np_pd_inner.asarray(
                        _close_series.values, dtype=float
                    )
                except Exception as exc:
                    log.warning(
                        "pattern_detect: candidate close-price slice failed "
                        "for (%s, %s) (continuing with empty slice): %s",
                        ticker,
                        pattern_class,
                        exc,
                    )
                    candidate_close_prices = _np_pd_inner.asarray(
                        [], dtype=float
                    )

                # Codex R4 Major #1: do NOT append Pass-1 scores to
                # universe_context here. The histogram universe is built
                # once in Pass 2 (after re-read + reconcile) so that
                # concurrent-skipped queued scores never phantom into
                # the histogram.
                emit_queue.append(
                    (
                        ticker,
                        pattern_class,
                        version_str,
                        window,
                        evidence,
                        geometric_score,
                        candidate_close_prices,
                    )
                )
    finally:
        # Close only the connection we opened (cfg path); never close
        # the lease-derived connection borrowed via getattr.
        if cfg is not None and detector_read_conn is not None:
            detector_read_conn.close()

    # ----------------------------------------------------------------------
    # Pass 2: serialize + INSERT against the now-complete universe
    # histogram (every row carries the SAME run-level histogram).
    # Codex R2 Major #1: open the lease-fenced write transaction ONCE
    # here, scoped tightly to the INSERT loop only.
    # ----------------------------------------------------------------------
    if not emit_queue:
        log.info(
            "pattern_detect: wrote %d pattern_evaluations rows across %d "
            "detect-pool tickers (%d skipped idempotent)",
            rows_written,
            len(detect_pool_tickers),
            rows_skipped_idempotent,
        )
        return

    # ----------------------------------------------------------------------
    # Fetch-vs-write-ordering fix (locus #8): snapshot the exemplar corpus +
    # pre-fetch its bars OUTSIDE the lease.fenced_write() transaction. The
    # exemplar bar fetch is an audit-writing network call (Schwab market-data
    # ladder -> audit_conn BEGIN IMMEDIATE) that MUST NOT run under a held
    # fence, or audit_conn deadlocks on the lease's write lock (Run-92).
    #
    # OQ-A/C: this snapshot is the run's AUTHORITATIVE scoring membership.
    # Membership == prefetched bars BY CONSTRUCTION, so there is no silent
    # score-lowering path (Codex R1 MAJOR #1): every exemplar that contributes
    # to a composite had its bars prefetched; every exemplar whose bars failed
    # is uniformly absent from BOTH the match and the universe (and #27-audited).
    # The cfg=None test-stub path reuses lease._conn WITHOUT entering
    # fenced_write (mirrors the detector_read_conn discipline ~1714-1723) so the
    # snapshot read stays lock-free.
    exemplar_snapshot_conn = (
        connect(cfg.paths.db_path) if cfg is not None
        else getattr(lease, "_conn", None)
    )
    snapshot_exemplar_rows: list = []
    try:
        if exemplar_snapshot_conn is not None:
            try:
                snapshot_exemplar_rows = list_exemplars(exemplar_snapshot_conn)
            except Exception as exc:
                log.warning(
                    "pattern_detect: exemplar corpus snapshot failed "
                    "(continuing with empty corpus; template_match_score "
                    "will be NULL): %s",
                    exc,
                )
                snapshot_exemplar_rows = []
        else:
            # Defensive edge (Codex R1 MINOR): cfg is None AND the lease exposes
            # no shared _conn. Read the corpus via a SHORT lease.fenced_write() --
            # a PURE READ (no audit-writing fetch inside, so deadlock-safe) --
            # mirroring the pre-fix in-fence list_exemplars so this unreachable
            # stub path does not silently degrade to an empty corpus. Bars are
            # still pre-fetched OUTSIDE any fence below.
            try:
                with lease.fenced_write() as _snap_conn:
                    snapshot_exemplar_rows = list_exemplars(_snap_conn)
            except Exception as exc:
                log.warning(
                    "pattern_detect: exemplar corpus snapshot via lease fence "
                    "failed (continuing with empty corpus): %s",
                    exc,
                )
                snapshot_exemplar_rows = []
    finally:
        if cfg is not None and exemplar_snapshot_conn is not None:
            exemplar_snapshot_conn.close()

    # Build the exemplar bundles from the snapshot (filter confirmed+watch only,
    # the same filter previously at @1989). snapshot_eligible_ids is the
    # authoritative eligible-ID set for the OQ-E in-fence divergence guard
    # (Task 2). Per-exemplar bar-fetch failure / empty-slice is isolated and
    # #27-audited (silent-skip-without-audit is forbidden).
    exemplar_bundles_by_class: dict[str, list[TemplateMatchExemplar]] = {}
    snapshot_eligible_ids: set[int] = set()
    _valid_exemplar_decisions = ("confirmed", "watch")
    for ex_row in snapshot_exemplar_rows:
        if ex_row.final_decision not in _valid_exemplar_decisions:
            continue
        snapshot_eligible_ids.add(int(ex_row.id))
        try:
            # window_days=400 IDENTICAL to the prior in-fence call (#28/#29
            # historical depth preserved byte-for-byte).
            ex_bars = ohlcv_cache.get_or_fetch(
                ticker=ex_row.ticker, window_days=400
            )
            _ex_start = pd.Timestamp(ex_row.start_date)
            _ex_end = pd.Timestamp(ex_row.end_date)
            _mask = (ex_bars.index >= _ex_start) & (ex_bars.index <= _ex_end)
            _ex_close = ex_bars.loc[_mask, "Close"]
            if hasattr(_ex_close, "ndim") and _ex_close.ndim == 2:
                _ex_close = _ex_close.iloc[:, 0]
            ex_close_arr = _np_pd_inner.asarray(_ex_close.values, dtype=float)
            if ex_close_arr.size == 0:
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect",
                        "exemplar_ticker": ex_row.ticker,
                        "reason": "exemplar bars unavailable",
                    })
                continue
            bundle = TemplateMatchExemplar(
                exemplar=ex_row, close_prices=ex_close_arr
            )
        except Exception as exc:
            log.info(
                "pattern_detect: exemplar bars pre-fetch failed for "
                "exemplar_id=%s ticker=%s (continuing): %s",
                ex_row.id, ex_row.ticker, exc,
            )
            if run_warnings is not None:
                run_warnings.append({
                    "step": "pattern_detect",
                    "exemplar_ticker": ex_row.ticker,
                    "reason": "exemplar bars unavailable",
                })
            continue
        exemplar_bundles_by_class.setdefault(
            ex_row.proposed_pattern_class, []
        ).append(bundle)

    with lease.fenced_write() as conn:
        # Codex R4 Major #1 + #2: Pass-2 final-universe semantics +
        # reconciliation-before-serialize. The prior R3 fix (per-recheck-hit
        # amend) had two architectural defects:
        #   (a) over-count: every queued detector score was already in
        #       ``universe_context['composite_scores']`` from Pass 1
        #       (line 1646), so when a concurrent row caused the recheck
        #       to skip the queued INSERT, the queued score remained in
        #       the histogram as a PHANTOM (counted but never persisted).
        #   (b) order dependence: per-tuple amend only fired when the
        #       loop REACHED the conflicting tuple; rows serialized
        #       EARLIER in emit_queue carried a STALE histogram that
        #       omitted the late-discovered concurrent row's score.
        #
        # Fix: RE-READ canonical existing rows ONCE inside the fenced
        # write; RECONCILE emit_queue against the re-read set (drop any
        # tuple already persisted); BUILD final universe = existing
        # scores + surviving queued scores; SERIALIZE + INSERT every
        # surviving row against this SAME final universe. The invariant
        # is that ``universe_context['composite_scores']`` represents
        # the FINAL persisted set for this pipeline_run_id -- never a
        # queued-but-not-persisted phantom.
        canonical_existing = conn.execute(
            "SELECT ticker, pattern_class, composite_score "
            "FROM pattern_evaluations WHERE pipeline_run_id = ?",
            (pipeline_run_id,),
        ).fetchall()
        existing_keys: set[tuple[str, str]] = set()
        canonical_existing_scores: list[float] = []
        import contextlib as _contextlib3
        for _row in canonical_existing:
            existing_keys.add((str(_row[0]), str(_row[1])))
            with _contextlib3.suppress(TypeError, ValueError):
                _val = _row[2]
                if _val is not None:
                    _f = float(_val)
                    # Skip non-finite (NaN/inf) defensively -- the
                    # histogram bucketer enforces [0.0, 1.0] anyway and
                    # NaN would raise there.
                    if _f == _f and _f not in (float("inf"), float("-inf")):
                        canonical_existing_scores.append(_f)

        # Reconcile emit_queue against canonical existing: any queued
        # tuple already present is DROPPED (its concurrent persisted
        # row's score, not the queued score, counts toward universe).
        # T2.SB5 T-A.5.4: emit tuple shape is now
        # (ticker, pattern_class, version_str, window, evidence,
        #  geometric_score, candidate_close_prices) - composite_score
        # is derived AFTER match_forward below.
        final_emit_list: list[
            tuple[str, str, str, object, object, float, _np_pd_inner.ndarray]
        ] = []
        for tup in emit_queue:
            tup_ticker = tup[0]
            tup_pattern_class = tup[1]
            if (tup_ticker, tup_pattern_class) in existing_keys:
                log.info(
                    "pattern_detect: row exists for (%d, %s, %s) at "
                    "Pass 2 reconcile; skipping (queued score dropped "
                    "from universe)",
                    pipeline_run_id,
                    tup_ticker,
                    tup_pattern_class,
                )
                rows_skipped_idempotent += 1
                continue
            final_emit_list.append(tup)

        # Exemplar corpus snapshot + bars pre-fetched OUTSIDE this fence
        # (fetch-vs-write-ordering fix locus #8, above). ``exemplar_bundles_by_class``
        # and ``snapshot_eligible_ids`` are built there from the Pass-2-entry
        # snapshot; the in-fence path no longer reads the corpus or fetches bars.

        # OQ-E observable-divergence guard (spec section 3). pattern_exemplars
        # has live writers OUTSIDE the pipeline lease (web routes, CLI labeling,
        # backfill), so the corpus can change mid-run. Scoring uses the
        # Pass-2-entry snapshot (<=1-run staleness, benign for a forward-walk
        # substrate); a CHEAP in-fence re-read of just the eligible IDs (no bars,
        # no network) detects a membership change and AUDITS it (#27) rather than
        # silently. This detects ID-set membership changes, NOT same-ID
        # confirmed<->watch decision flips (which do not change scoring
        # membership). Scoring still proceeds from the snapshot bundles.
        try:
            _infence_eligible_ids = {
                int(_r[0]) for _r in conn.execute(
                    "SELECT id FROM pattern_exemplars "
                    "WHERE final_decision IN ('confirmed','watch')"
                ).fetchall()
            }
        except Exception as exc:
            log.warning(
                "pattern_detect: in-fence exemplar-ID re-read failed "
                "(continuing; divergence guard skipped): %s",
                exc,
            )
            _infence_eligible_ids = snapshot_eligible_ids
        _eligible_added = _infence_eligible_ids - snapshot_eligible_ids
        _eligible_removed = snapshot_eligible_ids - _infence_eligible_ids
        if (_eligible_added or _eligible_removed) and run_warnings is not None:
            run_warnings.append({
                "step": "pattern_detect",
                "reason": (
                    "exemplar eligible-ID membership changed mid-run; "
                    "run used Pass-2-entry snapshot"
                ),
                "added": len(_eligible_added),
                "removed": len(_eligible_removed),
            })

        # Resolve each emit's template_match_score + nearest_ids +
        # composite_score per spec section 5.8 formula.
        # ``resolved_emit_list`` extends the tuple shape with:
        #   (..., template_match_score, nearest_exemplar_ids, composite_score)
        resolved_emit_list: list[
            tuple[
                str, str, str, object, object, float,
                float | None, list[int], float,
            ]
        ] = []
        for tup in final_emit_list:
            (
                tup_ticker,
                tup_pattern_class,
                tup_version_str,
                tup_window,
                tup_evidence,
                tup_geometric_score,
                tup_candidate_close,
            ) = tup
            template_match_score: float | None = None
            nearest_exemplar_ids: list[int] = []
            bundles_for_class = exemplar_bundles_by_class.get(
                tup_pattern_class, []
            )
            if (
                bundles_for_class
                and tup_candidate_close.size > 0
                and tup_geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD
            ):
                try:
                    hits = match_forward(
                        candidate_close_prices=tup_candidate_close,
                        candidate_pattern_class=tup_pattern_class,
                        candidate_ticker=tup_ticker,
                        exemplar_corpus=bundles_for_class,
                        top_k=3,
                        geometric_score=tup_geometric_score,
                    )
                except Exception as exc:
                    log.warning(
                        "pattern_detect: match_forward failed for "
                        "(%s, %s) (continuing with template_match=None): "
                        "%s",
                        tup_ticker,
                        tup_pattern_class,
                        exc,
                    )
                    hits = []
                if hits:
                    template_match_score = max(
                        h.similarity_score for h in hits
                    )
                    nearest_exemplar_ids = [h.exemplar_id for h in hits]
            # Spec section 5.8 composite formula via the L5-locked helper
            # (clamp inside compute_composite_score on BOTH paths).
            composite_score = compute_composite_score(
                geometric=tup_geometric_score,
                template_match=template_match_score,
            )
            resolved_emit_list.append(
                (
                    tup_ticker,
                    tup_pattern_class,
                    tup_version_str,
                    tup_window,
                    tup_evidence,
                    tup_geometric_score,
                    template_match_score,
                    nearest_exemplar_ids,
                    composite_score,
                )
            )

        # Build the FINAL universe ONCE: existing persisted scores plus
        # the surviving queued scores (post-template-match composites).
        # Every serialized row sees this SAME universe (no order
        # dependence).
        final_universe_scores: list[float] = list(canonical_existing_scores)
        for r in resolved_emit_list:
            with _contextlib3.suppress(TypeError, ValueError):
                final_universe_scores.append(float(r[8]))
        universe_context["composite_scores"] = final_universe_scores

        # Phase 14 Sub-bundle 2 (T-2.4): compute the detection-event anchors
        # ONCE before the emit loop.
        #   - detection_date = asof_run (the action-session label; FB-N4).
        #   - data_asof_date = lease_data_asof(cfg, lease) (forward-walk
        #     boundary anchor; the detector data cutoff; FB-N4).
        #   - candidate_by_ticker = the in-memory candidate rows (ZERO new
        #     query) for per-pattern metadata + finviz screen-state.
        detection_date_str = asof_run.isoformat()
        # data_asof_date = the forward-walk boundary anchor (detector data
        # cutoff). Production path reads it via lease_data_asof(cfg, lease);
        # the cfg-None test-stub path reads it off the shared lease conn (the
        # same row), mirroring _resolve_eval_run_action_session_date's
        # connection contract so the existing detect-step tests (cfg=None)
        # stay green (L7).
        if cfg is not None:
            data_asof_date = lease_data_asof(cfg, lease)
        else:
            _daa_row = conn.execute(
                "SELECT data_asof_date FROM pipeline_runs WHERE id=?",
                (pipeline_run_id,),
            ).fetchone()
            data_asof_date = _daa_row[0] if _daa_row is not None else None
        candidate_by_ticker = {c.ticker: c for c in candidates}

        for (
            ticker,
            pattern_class,
            version_str,
            window,
            evidence,
            _geometric_score,
            template_match_score,
            nearest_exemplar_ids,
            composite_score,
        ) in resolved_emit_list:
            # Defensive guard for the cfg-None/no-run-row edge: if the
            # pipeline_runs lookup returned no row, data_asof_date is None and
            # build_per_pattern_metadata(..., asof=None) -> date.fromisoformat(
            # None) would raise at PatternDetectionEvent construction (BEFORE
            # the insert try/except, so it would propagate uncaught). This path
            # is test-only/unreachable in production; skip the append for this
            # verdict and record a warning rather than crash.
            if data_asof_date is None:
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect", "ticker": ticker,
                        "pattern_class": pattern_class,
                        "reason": "data_asof_date unresolved; "
                                  "detection-event append skipped",
                    })
                continue

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

            # Codex R3 Major #1: persist RAW evidence geometric_score
            # (rule-tier value, may reach 1.10 for DBW per spec section
            # 5.8 line 718 + section 10.5 line 1325 undercut bonus). The
            # composite_score column carries the min(1.0, ...) wrapped
            # value per spec section 5.8 line 712 composite formula.
            # `pattern_evaluations.geometric_score` has no CHECK
            # constraint (migration 0020 line 240 declares `REAL NOT
            # NULL` only) so the column can carry 1.10 directly --
            # Option C in the R3 dispatch brief. Pre-R3 bug:
            # geometric_score=float(composite_score) used the CLAMPED
            # composite as the column value, losing the DBW rule-tier
            # evidence; only structural_evidence_json kept the 1.10.
            # T2.SB5 T-A.5.4: template_match_score + nearest_exemplar_ids_json
            # are now populated from match_forward hits when an exemplar
            # corpus of the same pattern_class is available AND the
            # candidate's geometric_score meets the section 5.7 pruning #2
            # pre-gate (>= 0.4). Otherwise both columns remain NULL (the
            # T2.SB4 backward-compat fallback path through
            # compute_composite_score's None branch preserves the
            # min(1.0, geometric_score) wrap per L5 LOCK).
            template_match_ids_json: str | None
            if nearest_exemplar_ids:
                try:
                    template_match_ids_json = _json.dumps(
                        list(nearest_exemplar_ids)
                    )
                except (TypeError, ValueError):
                    template_match_ids_json = None
            else:
                template_match_ids_json = None
            row = PatternEvaluation(
                id=None,
                pipeline_run_id=pipeline_run_id,
                ticker=ticker,
                pattern_class=pattern_class,
                detector_version=version_str,
                geometric_score=float(
                    getattr(evidence, "geometric_score", composite_score)
                ),
                geometric_score_json=geometric_score_json,
                composite_score=float(composite_score),
                structural_evidence_json=evidence_json,
                feature_distribution_log_json=fdl_json,
                window_start_date=window.start_date.isoformat(),
                window_end_date=window.end_date.isoformat(),
                created_at=_dt_inner.now(UTC).isoformat(),
                template_match_score=(
                    float(template_match_score)
                    if template_match_score is not None
                    else None
                ),
                template_match_nearest_exemplar_ids_json=template_match_ids_json,
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

            # --- Phase 14 Sub-bundle 2 (T-2.4): append the frozen detection
            # event in the SAME lease.fenced_write() transaction. ---
            cand = candidate_by_ticker.get(ticker)
            if cand is None:
                # Defensive: an emit without a candidate row should not
                # happen (the emit came from an aplus candidate); skip the
                # detection append rather than fabricate metadata.
                # gotcha #27: skipping leaves a pattern_evaluations row with
                # NO pattern_detection_events row -- a SILENT substrate
                # desync. AUDIT the skip (run_warnings) so it is
                # operator-visible. Audit-skip (not degrade) is correct here:
                # without the candidate row the per-pattern metadata +
                # finviz_screen_state cannot be meaningfully built.
                log.warning(
                    "pattern_detect: no candidate row for emitted verdict "
                    "(%s, %s); skipping detection append",
                    ticker,
                    pattern_class,
                )
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect", "ticker": ticker,
                        "pattern_class": pattern_class,
                        "reason": "candidate row missing for emitted verdict; "
                                  "evaluation written without detection row "
                                  "(substrate desync)",
                    })
                continue

            # SELECT-then-skip idempotency on the unique key (re-run safety):
            # a re-run must NOT duplicate AND must NOT recompute the frozen
            # facts. The skip fires BEFORE any chart render.
            existing_det = conn.execute(
                "SELECT 1 FROM pattern_detection_events WHERE source='pipeline' "
                "AND ticker=? AND detection_date=? AND pattern_class=?",
                (ticker, detection_date_str, pattern_class),
            ).fetchone()
            if existing_det is not None:
                continue

            # Substrate-completeness invariant (Codex chain #1 R2 Major #1):
            # EVERY emitted verdict appends a pattern_detection_events row.
            # bars SHOULD always be present (the emit came from a candidate
            # whose bars were fetched in Pass-1 + retained in bars_by_ticker).
            # If they are absent (internal inconsistency) DO NOT skip the
            # detection append -- degrade: empty-frame metadata (the compute_*
            # helpers return None on len-0 input via the _usable guard), no
            # chart, + a warnings_json entry.
            det_bars = bars_by_ticker.get(ticker)
            if det_bars is None:
                det_bars = pd.DataFrame()
                chart_render_id = None
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect", "ticker": ticker,
                        "pattern_class": pattern_class,
                        "reason": "bars absent for emitted verdict (internal); "
                                  "detection written with null computed "
                                  "metadata fields; no chart",
                    })
            else:
                try:
                    chart_render_id = render_and_capture_detection_chart(
                        conn, ticker=ticker, bars=det_bars,
                        pattern_evaluation=row,
                        pipeline_run_id=pipeline_run_id,
                        data_asof_date=data_asof_date,
                    )
                except Exception as exc:
                    # Programming error -> distinct ERROR; still degrade to
                    # NULL (the detection is never lost).
                    chart_render_id = None
                    log.error(
                        "pattern_detect: chart capture unexpected error "
                        "(%s, %s): %s",
                        ticker,
                        pattern_class,
                        exc,
                    )
                if chart_render_id is None and run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect", "ticker": ticker,
                        "pattern_class": pattern_class,
                        "reason": "chart render failed",
                    })

            detection = PatternDetectionEvent(
                detection_id=None, ticker=ticker,
                detection_date=detection_date_str,
                data_asof_date=data_asof_date, pattern_class=pattern_class,
                structural_anchors_json=build_structural_anchors_json(
                    window, evidence),
                composite_score=float(composite_score),
                detector_version=version_str,
                finviz_screen_state=build_finviz_screen_state(cand),
                source="pipeline",
                per_pattern_metadata_json=build_per_pattern_metadata(
                    cand, det_bars, asof=data_asof_date),
                created_at=_dt_inner.now(UTC).isoformat(),
                pipeline_run_id=pipeline_run_id,
                chart_render_id=chart_render_id,
            )
            try:
                insert_detection_event(conn, detection)
            except Exception as exc:
                log.warning(
                    "pattern_detect: detection-event INSERT failed for "
                    "(%s, %s) (continuing): %s",
                    ticker,
                    pattern_class,
                    exc,
                )
                # gotcha #27: a failed detection-event INSERT leaves the
                # pattern_evaluations row written but NO detection row -- a
                # SILENT substrate desync. Convert it into an AUDITED skip.
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect", "ticker": ticker,
                        "pattern_class": pattern_class,
                        "reason": "detection-event INSERT failed; evaluation "
                                  "written without detection row (substrate "
                                  "desync)",
                    })
                continue

    log.info(
        "pattern_detect: wrote %d pattern_evaluations rows across %d "
        "detect-pool tickers (%d skipped idempotent)",
        rows_written,
        len(detect_pool_tickers),
        rows_skipped_idempotent,
    )


# --- Phase 14 Sub-bundle 2 (T-2.5): forward-walk observe step + status machine.

# Terminal observation statuses (incl. V1-reserved closed_* names): a detection
# whose latest status is terminal must NEVER reach _advance_status
# (list_observable_detections excludes it). The guard is defense-in-depth.
_OBS_TERMINAL_STATUSES = frozenset({
    "invalidated", "expired",
    "triggered_closed_at_target", "triggered_closed_at_stop",
})


def _structural_invalidation_level(pattern_class: str, evidence: dict) -> float | None:
    """Per-class structural low (spec section 7.3.1), read from the frozen
    structural_anchors_json evidence dict."""
    if pattern_class == "flat_base":
        return evidence.get("range_bottom_price")
    if pattern_class == "vcp":
        contractions = evidence.get("contractions") or []
        lows = [c.get("low") for c in contractions if isinstance(c, dict)
                and c.get("low") is not None]
        return min(lows) if lows else None
    if pattern_class == "cup_with_handle":
        return evidence.get("cup_bottom_price")
    if pattern_class == "high_tight_flag":
        return evidence.get("pole_start_price")
    if pattern_class == "double_bottom_w":
        t1, t2 = evidence.get("trough_1_price"), evidence.get("trough_2_price")
        vals = [v for v in (t1, t2) if v is not None]
        return min(vals) if vals else None
    return None


def _advance_status(det, *, prev, bar, sessions_since_detection,
                    max_pending, max_post_trigger):
    """Compute (new_status, status_change_event) for one observation.

    V1+ emits ONLY the ruleset-agnostic subset
    {pending, triggered_open, invalidated, expired}. Anchors are read from
    the detection's FROZEN structural_anchors_json (never recomputed).
    """
    anchors = json.loads(det.structural_anchors_json)
    evidence = anchors.get("evidence", {})
    pivot = evidence.get("pivot_price")
    invalidation = _structural_invalidation_level(det.pattern_class, evidence)
    prev_status = prev.status if prev is not None else "pending"

    # Defensive terminal guard (Codex chain #2 Major #4):
    # list_observable_detections only returns detections whose latest status is
    # OPEN ('pending'/'triggered_open') or which have no observation yet. A
    # terminal prev status reaching here is a WIRING BUG -- raise loudly rather
    # than silently re-transition a frozen terminal chain (and never emit a
    # reserved closed_* status in V1+).
    if prev_status in _OBS_TERMINAL_STATUSES:
        raise ValueError(
            f"_advance_status called on terminal prev status {prev_status!r}; "
            "list_observable_detections should have excluded this detection")

    if prev_status == "triggered_open":
        if sessions_since_detection >= max_pending + max_post_trigger:
            return "expired", "observation_horizon_reached"
        return "triggered_open", None

    # prev pending (or first observation). PRECEDENCE (Codex chain #2 Major #1
    # + #3 -- explicit conflict ordering for a single bar that satisfies >1
    # condition):
    #   1. INVALIDATION (close < structural low): a CONFIRMED end-of-day shape
    #      break is the most decisive ruleset-agnostic signal; it WINS even when
    #      the same bar's intraday high also touched the pivot (a breakout that
    #      closes below the base low is a FAILED breakout, not a valid entry).
    #   2. BREAKOUT (high >= pivot, close >= structural low): an intraday pivot
    #      break that did NOT close below the structural low. A breakout that
    #      occurs ON the max_pending boundary still fires (the trigger happened
    #      within the pending window).
    #   3. EXPIRY (sessions_since_detection >= max_pending): only when NEITHER
    #      invalidation NOR breakout fired (matches spec section 7.3 "without
    #      trigger"). The boundary is inclusive (>=), so a non-triggering bar AT
    #      max_pending expires.
    if invalidation is not None and bar["close"] < invalidation:
        return "invalidated", "shape_break"
    if pivot is not None and bar["high"] >= pivot:
        return "triggered_open", "entry_fired"
    if sessions_since_detection >= max_pending:
        return "expired", "time_exit"
    return "pending", None


def _bar_for_date(cfg, ohlcv_cache, ticker: str, observation_date: str):
    """Return an ohlc dict (with provider) for exactly ``observation_date``, or
    None if the archive has no bar for that session.

    OQ-17 read path (writing-plans decision): (1) populate/refresh the archive
    via the OhlcvCache write-through ladder (archive-first; zero Schwab); (2)
    read the date-anchored bar + provider provenance via resolve_ohlcv_window
    (keyed end=observation_date). Selects the row whose asof_date ==
    observation_date (NOT iloc[-1]); freezes it; never re-reads it later
    (#26 elimination honest).
    """
    from datetime import date, datetime, timedelta

    from swing.data.ohlcv_archive import resolve_ohlcv_window

    # L3 date-only guard: never select a bar for the current in-progress
    # session. observation_date MUST be <= last_completed_session(now). In
    # normal operation observation_date == data_asof_date == the completed
    # session, so this never fires; it catches a wiring regression.
    cutoff = last_completed_session(datetime.now())
    if date.fromisoformat(observation_date) > cutoff:
        raise ValueError(
            f"_bar_for_date: observation_date {observation_date} is not a "
            f"completed session (cutoff {cutoff.isoformat()}); refusing to "
            f"select a partial/in-progress bar for the append-only log"
        )
    # 1. Populate the archive (write-through; the same call detect makes).
    #    Best-effort by design (Codex chain #1 Major #6): the date-anchored
    #    archive read in step 2 is AUTHORITATIVE. A get_or_fetch failure here
    #    is not fatal -- if it leaves no bar for observation_date, step 2's
    #    "no match" path returns None and the CALLER records a #27 no-bar
    #    warning + skips (operator-visible). T-2.5 step 0 confirmed (PASS) that
    #    get_or_fetch write-throughs to the same prices_cache_dir
    #    resolve_ohlcv_window reads (Shape-A {TICKER}.{provider}.parquet).
    try:
        # window_days=400 mirrors the detect-step Pass-1 fetch window (~400
        # calendar days) so the archive refresh covers the same depth.
        ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)
    except Exception as exc:  # noqa: BLE001 - best-effort populate; read is authoritative
        log.debug("observe populate get_or_fetch best-effort miss for %s: %s",
                  ticker, exc)
    # 2. Date-anchored archive read with per-asof_date provenance.
    # A small (10 calendar-day) back-pad guarantees the target session row is
    # inside the [start, end] window even across weekends/holidays; the exact
    # observation_date row is then selected below.
    start = (date.fromisoformat(observation_date) - timedelta(days=10)).isoformat()
    df, provenance = resolve_ohlcv_window(
        ticker, start=start, end=observation_date,
        cache_dir=cfg.paths.prices_cache_dir,
    )
    if df.empty:
        return None
    match = df[df["asof_date"] == observation_date]
    if match.empty:
        return None  # no bar for the gap day -> caller records a warning + skips
    r = match.iloc[-1]
    provider = provenance.get(observation_date)
    if provider is None:
        # No verified provenance for this date -> treat as no-bar (do NOT
        # fabricate a provider into the append-only log). The caller records a
        # #27 no-bar warning + skips.
        return None
    return {
        "open": float(r["open"]), "high": float(r["high"]),
        "low": float(r["low"]), "close": float(r["close"]),
        "volume": float(r["volume"]),
        "provider": provider,
    }


def _sessions_since(data_asof_date: str, observation_date: str) -> int:
    """Count trading sessions from data_asof_date UP TO AND INCLUDING
    observation_date (FB-N4: keyed on data_asof_date, NOT detection_date).
    Uses pandas bdate_range (business days) as the V1 trading-day proxy;
    holidays are an acceptable V1 approximation (the windows are coarse 30/60).
    date.fromisoformat boundary conversion at the callsite with malformed-input
    guard.
    """
    from datetime import date

    import pandas as pd
    start = date.fromisoformat(data_asof_date)
    end = date.fromisoformat(observation_date)
    if end <= start:
        return 0
    return int(len(pd.bdate_range(start=start, end=end)) - 1)


def _step_pattern_observe(*, cfg, lease, ohlcv_cache, run_warnings):
    """Append today's bar + lifecycle status to pattern_forward_observations
    for every open detection. Zero new detector invocations (L4)."""
    from datetime import UTC, datetime

    from swing.data.db import connect
    from swing.data.models import PatternForwardObservation
    from swing.data.ohlcv_finiteness import is_finite_ohlc
    from swing.data.repos.pattern_detection_events import (
        list_observable_detections,
    )
    from swing.data.repos.pattern_forward_observations import (
        get_latest_observations_for_detections,
        insert_observation,
    )
    from swing.pipeline.temporal_metadata import build_ohlc_today_json

    observation_date = lease_data_asof(cfg, lease)  # run DATA cutoff (R2 M#1)
    # L3 completed-day guard cutoff: passed to build_ohlc_today_json so a
    # non-completed-session bar can never enter the append-only log.
    observe_cutoff = last_completed_session(_dt.now())
    max_pending = cfg.pipeline.observe_max_pending_window_sessions
    max_post = cfg.pipeline.observe_max_post_trigger_window_sessions

    read_conn = connect(cfg.paths.db_path)
    try:
        open_dets = list_observable_detections(
            read_conn, source="pipeline", observation_date=observation_date)
        latest = get_latest_observations_for_detections(
            read_conn, [d.detection_id for d in open_dets])
    finally:
        read_conn.close()

    if not open_dets:
        run_warnings.append({
            "step": "pattern_observe", "actual_open_pool": 0,
            "reason": "no observable detections",
        })
        return

    _pend_w = getattr(cfg.pipeline,
                      "observe_max_pending_window_sessions_watch", None)
    _post_w = getattr(cfg.pipeline,
                      "observe_max_post_trigger_window_sessions_watch", None)
    _shed_count = 0
    _observed_count = 0
    # Reset cache telemetry at observe ENTRY so the observe_load audit reflects
    # observe-ONLY fetch cost (Codex R1 MAJOR): the runner shares ONE OhlcvCache
    # across _step_pattern_detect / _step_charts / _step_pattern_observe, so
    # without this reset the post-loop drain double-counts the prior steps'
    # fetches. Best-effort (a bare stub cache has no drain_telemetry).
    if hasattr(ohlcv_cache, "drain_telemetry"):
        ohlcv_cache.drain_telemetry()
    # Fetch-vs-write-ordering fix (locus #9): COMPUTE PASS outside the fence.
    # The per-detection body (idempotency skip, watch-shed, _bar_for_date fetch,
    # _advance_status, row-build) is fence-independent; only insert_observation
    # needs the lease. Running _bar_for_date (-> get_or_fetch -> audit-writing
    # market-data ladder) here means it never executes under a held write lock
    # (Run-92 deadlock removed). Shed is evaluated BEFORE _bar_for_date, so shed
    # tickers are still never fetched (OQ-A; identical Schwab quota to today).
    to_insert: list[PatternForwardObservation] = []
    for det in open_dets:
        prev = latest.get(det.detection_id)
        if prev is not None and prev.observation_date == observation_date:
            continue  # idempotent: already observed today
        # Dormant Lever 2 (pool-widening 2026-06-04): watch-origin pre-fetch
        # shed. A no-fetch SKIP (NOT an `expired` transition -- a no-fetch
        # expiry is impossible without a schema change; ohlc_today_json is
        # NOT NULL). The bucket is read from the LOCKED finviz_screen_state
        # (never recomputed). The horizon is STATUS-AWARE (mirrors
        # _advance_status): a pending/unobserved watch detection sheds past
        # the watch pending window; a triggered_open one sheds past watch
        # pending + watch post-trigger (each falling back to the aplus
        # window when its knob is None). Repeated runs cheaply re-skip.
        if _pend_w is not None or _post_w is not None:
            _bucket = None
            if det.finviz_screen_state:
                try:
                    _bucket = json.loads(det.finviz_screen_state).get("bucket")
                except (ValueError, TypeError):
                    _bucket = None
            if _bucket == "watch":
                _sess = _sessions_since(det.data_asof_date, observation_date)
                _prev_status = prev.status if prev is not None else "pending"
                if _prev_status == "triggered_open":
                    _horizon = (
                        (_pend_w if _pend_w is not None else max_pending)
                        + (_post_w if _post_w is not None else max_post))
                else:  # pending / no observation yet
                    _horizon = (
                        _pend_w if _pend_w is not None else max_pending)
                if _sess > _horizon:
                    _shed_count += 1
                    continue  # no fetch, no observation row, no terminal
        bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)
        if bar is None:
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "no bar for observation_date",
            })
            continue
        # Phase 18 Arc 18-A -- non-finite OHLC skip-with-warning (mirrors the
        # bar-is-None branch + Arc-8 "leave the hole; the engine tolerates a
        # hole, not a NaN"). A completed-session bar whose OHLC is non-finite
        # (the 2026-06-10 yfinance Close=NaN artifact, O/H/L/V-finite) must NEVER
        # enter the append-only temporal log. Volume is EXEMPT (not passed) --
        # validate_bars ignores volume too. Skipping HERE, before _advance_status,
        # also means a NaN close never drives a phantom status transition. The
        # one-session interior hole is permanent (not backfilled on later runs);
        # the engine prices around it. is_finite_ohlc (C1) is the SAME predicate
        # the Arc-8 archive trim and the serializer belt consume.
        if not is_finite_ohlc(bar["open"], bar["high"], bar["low"], bar["close"]):
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "non_finite_ohlc",
            })
            continue
        sessions = _sessions_since(det.data_asof_date, observation_date)
        status, change = _advance_status(
            det, prev=prev, bar=bar,
            sessions_since_detection=sessions,
            max_pending=max_pending, max_post_trigger=max_post)
        to_insert.append(PatternForwardObservation(
            observation_id=None, detection_id=det.detection_id,
            observation_date=observation_date,
            ohlc_today_json=build_ohlc_today_json(
                bar, observation_date=observation_date, cutoff=observe_cutoff,
            ),  # validated shape + provider domain + completed-day guard
            status=status, status_change_event=change,
            sessions_since_detection=sessions,
            created_at=datetime.now(UTC).isoformat(),
        ))

    # WRITE PASS: a single short fence wraps ONLY the inserts (the lease-fencing
    # contract is preserved; the write still happens inside fenced_write).
    if to_insert:
        with lease.fenced_write() as conn:
            for row in to_insert:
                insert_observation(conn, row)
                _observed_count += 1

    # Lever 2 #27 audit: any shed is recorded (a silent shed is forbidden).
    if _shed_count > 0:
        run_warnings.append({
            "step": "pattern_observe",
            "shed_count": _shed_count,
            "reason": ("watch observe window shortened "
                       "(cfg.pipeline.observe_max_*_watch)"),
        })

    # Observe-load instrumentation (truthful fetch-vs-hit at the cache
    # boundary; Codex R1 MAJOR #5). drain_telemetry() may be absent on a bare
    # stub cache -> default to zeros (best-effort, never crash observe). Units:
    # observed = rows written; fetch_window = get_or_fetch calls that consulted
    # archive/network; in_memory_hit = TTL hits.
    _tele = (ohlcv_cache.drain_telemetry()
             if hasattr(ohlcv_cache, "drain_telemetry") else {})
    run_warnings.append({
        "step": "pattern_observe",
        "metric": "observe_load",
        "observed": _observed_count,
        "fetch_window": _tele.get("fetch_window", 0),
        "in_memory_hit": _tele.get("in_memory_hit", 0),
    })


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

    # Phase 14 close-out (A-1): imported lazily (NOT module-top) -- a module-top
    # `from swing.web.ohlcv_cache import ...` creates a runner<->ohlcv_cache
    # import cycle (ohlcv_cache imports swing.pipeline -> __init__ imports
    # runner) that breaks `import swing.web.ohlcv_cache` standalone.
    from swing.web.ohlcv_cache import (
        MIN_CALENDAR_DAYS_FOR_MA200,
        MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
        slice_recent_calendar_days,
    )
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
            ohlcv = ohlcv_cache.get_or_fetch(
                ticker=ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
            )
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

    # Phase 13 T2.SB6c T-A.6c.2 §1.5.1 amendment — write-through to the
    # chart_renders cache so downstream surfaces (dashboard / watchlist /
    # trade detail / hyp-rec expansion) can serve charts inline without
    # re-rendering at request time. 4 surfaces:
    #   - watchlist_row: per active watchlist ticker (pipeline_run_id non-NULL)
    #   - ticker_detail: per A+ candidate (pipeline_run_id non-NULL)
    #   - position_detail: per open trade (pipeline_run_id IS NULL per v20 §3.2)
    #   - market_weather: cfg.rs.benchmark_ticker (pipeline_run_id non-NULL,
    #     per Codex R2 MAJOR #4 closure)
    # F6 transient-empty defense lives at the ChartRender __post_init__
    # construction barrier (T2.SB6a R1 MAJOR #2 LOCK): a renderer returning
    # b"" raises ValueError which we catch + WARN-log + continue.
    _now_iso = _dt.now().isoformat(timespec="seconds")

    def _bars_or_none(ticker: str):
        try:
            return ohlcv_cache.get_or_fetch(
                ticker=ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
            )
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            log.warning(
                "chart_renders write-through: ohlcv fetch failed for %s: %s",
                ticker, exc,
            )
            return None

    def _refresh_one(*, ticker: str, surface: str,
                     pipeline_run_id: int | None, pattern_class: str | None,
                     bytes_: bytes, source_data_hash: str) -> None:
        try:
            chart_render = ChartRender(
                id=None,
                ticker=ticker,
                surface=surface,
                chart_svg_bytes=bytes_,
                source_data_hash=source_data_hash,
                rendered_at=_now_iso,
                data_asof_date=data_asof,
                pipeline_run_id=pipeline_run_id,
                pattern_class=pattern_class,
            )
        except ValueError as exc:
            log.warning(
                "F6 transient empty chart skipped: ticker=%s surface=%s err=%s",
                ticker, surface, exc,
            )
            return
        try:
            with lease.fenced_write() as conn:
                refresh_chart_render(conn, chart_render)
        except LeaseRevokedError:
            raise
        except Exception as exc:  # noqa: BLE001 - per-surface isolation
            log.warning(
                "chart_renders write-through: refresh failed for "
                "ticker=%s surface=%s: %s",
                ticker, surface, exc,
            )

    # watchlist_row surface — per data-eligible dashboard-top-5 watchlist
    # ticker. Phase 13 T-T4.SB.3 (OQ-5.3 LOCK): pre-gen scope reduced
    # from top-N (`chart_top_n_watch` = 10) to dashboard-top-5
    # visible-by-default. Out-of-scope (positions 6-10) thumbnails are
    # JIT'd at request time via swing/web/chart_jit.py:get_or_render_surface.
    # The dashboard renders only the top-5 by default — pre-genning the
    # full 10 burned ~50% of chart-step wall time on rows operators
    # rarely opened.
    #
    # Renderer-kwargs uniformity LOCK: ma_lines=[20, 50] matches the
    # JIT helper's default (per Codex R4 M#3 cache-collision avoidance).
    # NOTE: this changes the kwargs from the prior [50, 150, 200] —
    # operator-facing change accepted per plan §B.3 Sub-task 3E.
    _pregen_watchlist_top_n = 5
    for w in tag_aware_top_n[:_pregen_watchlist_top_n]:
        ticker = w.ticker.upper()
        bars = _bars_or_none(ticker)
        if bars is None or bars.empty:
            continue
        try:
            svg_bytes = render_watchlist_thumbnail_svg(
                ticker=ticker, bars=bars, ma_lines=[20, 50],
            )
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            log.warning(
                "render_watchlist_thumbnail_svg failed for %s: %s",
                ticker, exc,
            )
            continue
        _refresh_one(
            ticker=ticker, surface="watchlist_row",
            pipeline_run_id=lease.run_id, pattern_class=None,
            bytes_=svg_bytes,
            source_data_hash=compute_chart_source_hash(bars),
        )

    # ticker_detail surface — Phase 13 T-T4.SB.3 (OQ-5.3 LOCK): pre-gen
    # DROPPED from chart-step. The hyp-recs expanded surface is operator-
    # opened on-demand from the dashboard hyp-recs card; pre-genning all
    # A+ tickers wastes ~one render per ticker, most never opened. The
    # /hyp-recs/{ticker}/expand route + build_hyp_recs_expanded VM
    # builder now JIT-fall-back to swing/web/chart_jit.py:get_or_render_surface
    # on cache miss + write-through.

    # position_detail surface — per open trade. Run-agnostic key shape:
    # pipeline_run_id IS NULL per v20 §3.2 LOCK so the dashboard reader
    # (which doesn't anchor on a specific run for open positions) finds
    # the row.
    if open_trades:
        from swing.data.repos.fills import list_fills_for_trade
        for tr in open_trades:
            ticker = tr.ticker.upper()
            bars = _bars_or_none(ticker)
            if bars is None or bars.empty:
                continue
            _conn = connect(cfg.paths.db_path)
            try:
                trade_fills = list_fills_for_trade(_conn, tr.id)
            finally:
                _conn.close()
            try:
                svg_bytes = render_position_detail_svg(
                    ticker=ticker, bars=bars, trade=tr,
                    fills=trade_fills, current_stop=tr.current_stop,
                )
            except Exception as exc:  # noqa: BLE001 - per-ticker isolation
                log.warning(
                    "render_position_detail_svg failed for %s: %s",
                    ticker, exc,
                )
                continue
            _refresh_one(
                ticker=ticker, surface="position_detail",
                pipeline_run_id=None, pattern_class=None,
                bytes_=svg_bytes,
                source_data_hash=compute_chart_source_hash(bars),
            )

    # market_weather surface — cfg.rs.benchmark_ticker per Codex R2 MAJOR #4
    # closure. Dashboard reader at T2.SB6b reads via the SAME ticker;
    # divergence here silently invisibles the chart.
    #
    # F-2 (Phase 14 close-out follow-on): compute the trend state LIVE from a
    # wide (>= MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE) benchmark fetch via
    # structural_stage. current_stage read PERSISTED candidate_criteria for the
    # benchmark, which is NOT in the evaluated set -> always 'undefined'. Display
    # the narrower MIN_CALENDAR_DAYS_FOR_MA200 window (legibility unchanged);
    # the wider compute window is sliced down (anchored on the frame's own last
    # bar, cache-lag-safe).
    benchmark_ticker = cfg.rs.benchmark_ticker.upper()
    try:
        compute_bars = ohlcv_cache.get_or_fetch(
            ticker=benchmark_ticker,
            window_days=MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
        )
    except Exception as exc:  # noqa: BLE001 - per-ticker isolation
        log.warning(
            "market_weather benchmark fetch failed for %s: %s",
            benchmark_ticker, exc,
        )
        compute_bars = None
    if compute_bars is not None and not compute_bars.empty:
        # Fail-soft: a structural_stage error must NEVER abort the charts step.
        try:
            closes = compute_bars["Close"]
            if getattr(closes, "ndim", 1) == 2:
                closes = closes.iloc[:, 0]
            weather_state = structural_stage(
                closes, rising_period=cfg.trend_template.rising_ma_period_days,
            )
        except Exception as exc:  # noqa: BLE001 - fail-soft, never abort step
            log.warning(
                "market_weather structural_stage failed for %s: %s",
                benchmark_ticker, exc,
            )
            weather_state = "undefined"
        display_bars = slice_recent_calendar_days(
            compute_bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
        )
        try:
            svg_bytes = render_market_weather_svg(
                bars=display_bars, trend_template_state=weather_state,
            )
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            log.warning(
                "render_market_weather_svg failed for %s: %s",
                benchmark_ticker, exc,
            )
        else:
            _refresh_one(
                ticker=benchmark_ticker, surface="market_weather",
                pipeline_run_id=lease.run_id, pattern_class=None,
                bytes_=svg_bytes,
                source_data_hash=compute_chart_source_hash(display_bars),
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
    run_warnings: list[dict] | None = None,
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
            # --- WARM, OUTSIDE the fence (yfinance I/O here, lock-free) ---
            # read_or_fetch_archive is lease-free (touches no lease/lock), so it
            # cannot raise LeaseRevokedError; a warm error degrades to
            # archive_df=None -> the single #27 skip branch below.
            miss_reason: str | None = None
            try:
                archive_df = read_or_fetch_archive(
                    trade.ticker, end_date=asof_session,
                    cache_dir=ohlcv_archive_dir,
                    archive_history_days=archive_history_days,
                )
                if archive_df is None or archive_df.empty:
                    miss_reason = "warm_empty_or_stale"
            except LeaseRevokedError:
                # Structural force-clear guard (Codex R2 MAJOR): LeaseRevokedError
                # subclasses Exception, so the catch-all below would otherwise
                # downgrade a revoke to warm_raised+skip. read_or_fetch_archive is
                # lease-free today, but this guard keeps force-clear authority
                # structural -- a revoke from the warm path propagates, matching
                # the outer per-trade discipline.
                raise
            except Exception as warm_exc:  # noqa: BLE001 -- best-effort warm; miss funnels to #27
                log.warning(
                    "daily_management warm fetch failed for trade %s "
                    "(ticker=%s): %s -- proceeding to skip path",
                    trade.id, trade.ticker, warm_exc,
                )
                archive_df = None
                miss_reason = "warm_raised"

            # --- FENCE: fast SQLite read + compute + persist (no network) ---
            with lease.fenced_write() as conn:
                res = _dm.compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id,
                    asof_session=asof_session,
                    run_now=run_now,
                    archive_df=archive_df,
                    expected_ticker=trade.ticker,  # the snapshot ticker, NOT a re-read
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
                if res.fields is None:
                    # All miss causes funnel here. The warm pre-set miss_reason
                    # (warm_raised / warm_empty_or_stale) wins when set; otherwise
                    # the warm succeeded and the typed return is authoritative for
                    # the in-fence cause (ticker_changed / no_eligible_window).
                    if miss_reason is None:
                        miss_reason = res.miss_reason
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): %s", trade.id, trade.ticker, miss_reason,
                    )
                    if run_warnings is not None:   # #27 audit (gotcha #27)
                        run_warnings.append({
                            "step": "daily_management",
                            "ticker": trade.ticker,
                            "reason": "archive unavailable for asof_session",
                            "miss_reason": miss_reason,
                        })
                    continue
                upsert_snapshot(
                    conn, trade_id=trade.id, snapshot_fields=res.fields,
                )
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=res.fields["created_at"],
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
