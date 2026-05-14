"""Schwab pipeline-step entry points (Phase 11 Sub-bundle B T-B.3 + T-B.4).

Two functions wired into the nightly pipeline between `_step_recommendations`
and `_step_charts` per plan §H.4.3:

  - `_step_schwab_snapshot(conn, cfg, pipeline_run_id, *, client=None)` —
    fetch `accounts.details`; under production env, write
    `account_equity_snapshots` row + stamp `schwab_account_hash` via combined
    tx2 (`link_snapshot_and_stamp_account_hash`).
  - `_step_schwab_orders(conn, cfg, pipeline_run_id, *, client=None)` —
    fetch orders + transactions + details; under production env, invoke
    `run_schwab_reconciliation` + UPDATE all 3 audit rows with the
    reconciliation_run_id.

Sandbox short-circuit per plan §A.3:
  - Both steps CALL Schwab + WRITE audit rows under either env (production
    or sandbox), when a `client` IS supplied.
  - Domain writes (snapshot, reconciliation_run, discrepancies) are SKIPPED
    when `cfg.integrations.schwab.environment != 'production'`.

The `client` parameter is optional for test injection + CLI use. The
schwabdev `Client` instance is constructed by:
  - `swing/integrations/schwab/auth.py:construct_authenticated_client` for
    the CLI `swing schwab fetch` surface (Bundle B T-B.5).
  - `auth.py:setup_paste_flow` / `force_refresh` for setup/refresh CLI.
The pipeline runner currently passes `client=None`; per Codex R2 M#1 +
R3 M#1 + M#2 fix, the no-client path silent-skips (log only, NO audit
row) to avoid polluting degraded-health surfaces on every nightly run.
Pipeline-internal Schwab fetching is best-effort V1 + opt-in via the
CLI surface as primary operator entry point.

Failure-tolerance per plan §3.4.4:
  - Trader-API failures (auth/rate/etc.) are caught + logged + the step
    returns 'failed' without aborting the pipeline. The audit row
    reflects the failure (`status='auth_failed'` / `'rate_limited'` /
    `'error'`).
  - Programming errors propagate to the pipeline runner's per-step
    `except Exception` wrapper which logs + continues.

Account-hash-missing path (Codex R3 M#1):
  - Pipeline surface: silent-skip (log only, NO audit row).
  - CLI surface: writes advisory error audit row (operator-actionable
    signal).
No domain writes; no schwabdev call in either case.

Same-day account_hash flip protection (Codex R1 M#8): if a same-day
source='schwab_api' snapshot already exists with a DIFFERENT non-NULL
schwab_account_hash, refuse overwrite + emit a SEPARATE advisory audit
row. NULL-hash rows are crash-window recovery candidates (§H.4.1.bis);
the current call fills in the NULL via combined-tx2 stamp.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from swing.evaluation.dates import last_completed_session
from swing.integrations.schwab import audit_service
from swing.integrations.schwab.client import (
    SchwabApiError,
    SchwabConfigMissingError,
)
from swing.integrations.schwab.trader import (
    TRANSACTION_TYPES_ALL,
    get_account_details,
    get_account_orders,
    get_account_transactions,
)
from swing.trades.account_equity_snapshots import (
    CallerHeldTransactionError as SnapshotCallerHeldTxError,
)
from swing.trades.account_equity_snapshots import record_snapshot

log = logging.getLogger(__name__)


def _now_iso_ms() -> str:
    """Server-stamp at handler entry (Phase 8 server-stamping discipline)."""
    return datetime.now().isoformat(timespec="microseconds")


def _build_default_client(cfg: Any, environment: str) -> Any:
    """Construct a fresh `schwabdev.Client(...)` for production use.

    Pipeline-step + CLI consumers call this when they don't have an existing
    client instance. Tests inject `client=...` to bypass.

    Per Sub-bundle A T-A.0.b §6.bis schwabdev 2.5.1 signature:
        Client(app_key, app_secret, callback_url='https://127.0.0.1',
               tokens_file='tokens.json', timeout=10, capture_callback=False,
               use_session=True, call_on_notify=None)

    schwabdev requires `app_key` + `app_secret`. In the pipeline context,
    these are NOT stored in cfg (sensitive). Pipeline-step consumers cannot
    construct a fresh client without operator credentials — so this helper
    raises `SchwabConfigMissingError` to surface the dependency. The CLI
    surfaces (`swing schwab fetch *`) prompt the operator at handler entry
    just like `swing schwab setup` / `refresh`.

    For V1, pipeline-internal use of Schwab API requires the operator to
    have run `swing schwab setup` previously (tokens DB persisted at
    `~/swing-data/schwab-tokens.{env}.db`) AND the CLI subcommand to be the
    primary entry point (operator-paced). The pipeline-internal step is a
    best-effort fallback that requires a pre-built client OR fails gracefully.
    """
    raise SchwabConfigMissingError(
        "pipeline-internal schwabdev.Client construction requires operator "
        "credentials (client_id + client_secret); V1 expects callers to "
        "supply an existing schwabdev.Client instance via the `client=` "
        "kwarg, OR to invoke via the CLI surface which prompts at handler "
        "entry. See plan §A.2 single-Client-instance discipline."
    )


def _step_schwab_snapshot(
    conn: sqlite3.Connection,
    cfg: Any,
    pipeline_run_id: int | None,
    *,
    client: Any = None,
    surface: str = "pipeline",
) -> dict:
    """Pipeline step: fetch `accounts.details` + record snapshot under production.

    Algorithm per plan §H.4.1:
      1. Read cfg.integrations.schwab.{environment, account_hash}.
      2. If account_hash is None: write a no-op advisory audit row + return.
      3. Invoke `get_account_details(client, ...)` — this writes the audit
         row INSERT/UPDATE lifecycle internally.
      4. On Trader-API failure: caller's audit row reflects it; step returns
         + the pipeline runner continues.
      5. On success: extract NLV from the response.
      6. Production-only gate (per plan §A.3):
         - If env='production': invoke `record_snapshot(source='schwab_api',
           ...)` + `link_snapshot_and_stamp_account_hash` combined tx2.
         - If env='sandbox': skip domain writes; audit row stays
           `linked_snapshot_id=NULL`.

    Caller MUST NOT hold an open transaction (the snapshot service rejects).

    Returns:
        dict with keys: `status` ∈ {'completed', 'skipped_no_account_hash',
        'failed', 'sandbox_audit_only'}; `call_id` (or None); `snapshot_id`
        (or None); `error` (or None).
    """
    if conn.in_transaction:
        raise SnapshotCallerHeldTxError(
            "_step_schwab_snapshot expects caller-controlled transaction discipline; "
            "caller MUST NOT hold an open transaction (record_snapshot service "
            "owns BEGIN IMMEDIATE)."
        )

    schwab_cfg = cfg.integrations.schwab
    environment = schwab_cfg.environment
    account_hash = schwab_cfg.account_hash

    if not account_hash:
        # Codex R3 M#1 fix — surface-aware advisory audit row.
        # Pipeline surface (nightly runner): silent-skip — log only,
        # NO audit row. Avoids polluting degraded-health surfaces with
        # persistent 'error' rows when operator hasn't yet run `swing
        # schwab setup` (fresh / unconfigured install state).
        # CLI surface: write the advisory error row — operator explicitly
        # invoked `swing schwab fetch` AND the missing-account-hash is
        # operator-actionable signal worth surfacing.
        if surface == "pipeline":
            log.info(
                "_step_schwab_snapshot: skipped (account_hash not "
                "configured; pipeline-internal silent-skip)"
            )
            return {
                "status": "skipped_no_account_hash",
                "call_id": None,
                "snapshot_id": None,
                "error": "account_hash not configured",
            }
        ts = _now_iso_ms()
        call_id = audit_service.record_call_start(
            conn,
            ts=ts,
            endpoint="accounts.details",
            pipeline_run_id=pipeline_run_id,
            surface=surface,
            environment=environment,
        )
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            response_time_ms=0,
            rate_limit_remaining=None,
            signature_hash=None,
            status="error",
            error_message=(
                "<account_hash not configured; run `swing schwab setup` first>"
            ),
        )
        log.info(
            "_step_schwab_snapshot: skipped (account_hash not configured)"
        )
        return {
            "status": "skipped_no_account_hash",
            "call_id": call_id,
            "snapshot_id": None,
            "error": "account_hash not configured",
        }

    if client is None:
        # Codex R2 M#1 + R3 M#1 + M#2 — pipeline-internal call without an
        # explicit client. V1 pipeline-internal Schwab fetching is best-
        # effort + opt-in via the `swing schwab fetch` CLI surface. We
        # log + return WITHOUT writing an audit row to avoid polluting
        # degraded-health surfaces with persistent 'error' rows on every
        # nightly run.
        #
        # R3 M#2 ACCEPT-WITH-RATIONALE: Bundle D's degraded-health surface
        # cannot distinguish "intentionally skipped" from "step never
        # executed" from `schwab_api_calls` alone. The lease.step()
        # breadcrumb name (`schwab_snapshot`) + the log entry are the V1
        # discriminators; Bundle D's status output can query the lease
        # row's `current_step` to surface the breadcrumb. Adding a
        # durable status row would require either (a) a new schema
        # column (violates ZERO-new-schema scope of Bundle B), or (b) a
        # sentinel-prefixed 'error' row (which Codex R2 M#1 correctly
        # objected to as health-surface pollution). V2 can add a
        # dedicated `schwab_step_status` lease field.
        try:
            client = _build_default_client(cfg, environment)
        except SchwabConfigMissingError:
            log.info(
                "_step_schwab_snapshot: skipped (no client supplied "
                "pipeline-internally; use `swing schwab fetch --snapshot` "
                "CLI as primary entry point)"
            )
            return {
                "status": "skipped_no_client",
                "call_id": None,
                "snapshot_id": None,
                "error": "no client supplied pipeline-internally",
            }

    # Invoke trader wrapper (writes audit row internally).
    try:
        response = get_account_details(
            client, conn, account_hash,
            surface=surface, environment=environment,
            pipeline_run_id=pipeline_run_id,
        )
    except SchwabApiError as exc:
        log.warning(
            "_step_schwab_snapshot: get_account_details failed: %s",
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "call_id": _latest_call_id_for_pipeline(conn, pipeline_run_id),
            "snapshot_id": None,
            "error": f"{type(exc).__name__}: api call failed",
        }

    # The trader wrapper just wrote its audit row's success close. Pull the
    # call_id back via the most-recent-audit-row lookup (deterministic — we
    # JUST wrote it, single connection, single thread).
    call_id = _latest_call_id_for_pipeline(conn, pipeline_run_id)
    if call_id is None:
        # Should not happen if get_account_details returned without raising.
        log.error(
            "_step_schwab_snapshot: trader returned but call_id not found"
        )
        return {
            "status": "failed", "call_id": None, "snapshot_id": None,
            "error": "call_id not found post-trader-success",
        }

    # Production-only gate (plan §A.3).
    if environment != "production":
        log.info(
            "_step_schwab_snapshot: env=%s; sandbox short-circuit (no domain write)",
            environment,
        )
        return {
            "status": "sandbox_audit_only",
            "call_id": call_id,
            "snapshot_id": None,
            "error": None,
        }

    # Compute snapshot_date = last_completed_session(now()) per plan §A.9.
    snapshot_date = last_completed_session(datetime.now())

    # Codex R1 M#8 — account_hash-flip protection. If a same-day
    # source='schwab_api' snapshot already exists with a DIFFERENT
    # schwab_account_hash, refuse to overwrite + emit an explicit audit
    # row. V1 single-primary-account contract means the only way to hit
    # this is a mid-day cfg flip (operator ran `swing config set
    # integrations.schwab.account_hash <new>`); the operator-visible
    # contract is "one account per env per day" — V2 multi-account
    # supersedes.
    existing_row = conn.execute(
        "SELECT schwab_account_hash FROM account_equity_snapshots "
        "WHERE snapshot_date = ? AND source = 'schwab_api' LIMIT 1",
        (snapshot_date.isoformat(),),
    ).fetchone()
    # Codex R1 M#8 — refuse overwrite when existing same-day row has a
    # DIFFERENT non-NULL schwab_account_hash. Codex R2 m#1 note: NULL
    # hash rows are recovery candidates (crash-window per §H.4.1.bis);
    # ALLOW the current call to proceed AND fill in the NULL hash via
    # the combined-tx2 stamp. This is the intentional asymmetry —
    # NULL → fill (recovery), differing → block (flip protection).
    if (
        existing_row is not None
        and existing_row[0] is not None
        and existing_row[0] != account_hash
    ):
        # Emit an additional advisory audit row (status='error') noting the
        # flip detection. The trader call's own audit row stays
        # status='success' (the schwabdev call DID succeed; this is a
        # post-call domain-write guard, NOT an API-side failure).
        advisory_call_id = audit_service.record_call_start(
            conn,
            ts=_now_iso_ms(),
            endpoint="accounts.details",
            pipeline_run_id=pipeline_run_id,
            surface=surface,
            environment=environment,
        )
        audit_service.record_call_finish(
            conn,
            call_id=advisory_call_id,
            http_status=None,
            response_time_ms=0,
            rate_limit_remaining=None,
            signature_hash=None,
            status="error",
            error_message=(
                "<same-day schwab_account_hash flip detected; refusing to "
                "overwrite existing snapshot — V1 single-primary-account>"
            ),
        )
        log.warning(
            "_step_schwab_snapshot: account_hash flip detected for %s "
            "(existing differs from cfg) — refusing overwrite",
            snapshot_date.isoformat(),
        )
        return {
            "status": "failed",
            "call_id": call_id,
            "snapshot_id": None,
            "error": "account_hash_flip_same_day",
        }

    # tx1 — Phase 9 Sub-bundle C record_snapshot (owns BEGIN IMMEDIATE).
    snapshot = record_snapshot(
        conn,
        equity_dollars=response.net_liquidating_value,
        snapshot_date=snapshot_date,
        source="schwab_api",
        source_artifact_path=f"schwab_api:call/{call_id}",
        recorded_by="schwab_api",
        notes=None,
    )
    snapshot_id = snapshot.snapshot_id

    # tx2 — combined link audit + stamp schwab_account_hash (plan §H.4.1 step 8d).
    audit_service.link_snapshot_and_stamp_account_hash(
        conn,
        call_id=call_id,
        snapshot_id=snapshot_id,
        account_hash=account_hash,
    )

    log.info(
        "_step_schwab_snapshot: completed; snapshot_id=%d call_id=%d nlv=%.2f",
        snapshot_id, call_id, response.net_liquidating_value,
    )
    return {
        "status": "completed",
        "call_id": call_id,
        "snapshot_id": snapshot_id,
        "error": None,
    }


def _step_schwab_orders(
    conn: sqlite3.Connection,
    cfg: Any,
    pipeline_run_id: int | None,
    *,
    client: Any = None,
    surface: str = "pipeline",
) -> dict:
    """Pipeline step: fetch orders + transactions + details; reconcile.

    Algorithm per plan §H.4.2:
      1. Read cfg.{environment, account_hash, lookback_days}.
      2. If account_hash is None: advisory audit row + return.
      3. Compute period_end = last_completed_session(now()); period_start =
         period_end - lookback_days.
      4. Three sequential Trader-API calls: orders → transactions → details.
      5. On any failure: audit row reflects + step returns (pipeline continues).
      6. Production-only gate: invoke `run_schwab_reconciliation` + UPDATE all
         3 audit rows with the reconciliation_run_id via `link_reconciliation_run`.
      7. Sandbox: skip reconciliation; audit rows stay `linked_reconciliation_run_id=NULL`.

    Returns:
        dict with `status` ∈ {'completed', 'skipped_no_account_hash',
        'failed', 'sandbox_audit_only'}; `call_ids` list (one per call
        made); `reconciliation_run_id` (or None); `error` (or None).
    """
    if conn.in_transaction:
        from swing.trades.schwab_reconciliation import (
            CallerHeldTransactionError as ReconCallerHeldTxError,
        )
        raise ReconCallerHeldTxError(
            "_step_schwab_orders expects caller-controlled transaction; "
            "caller MUST NOT hold an open transaction."
        )

    schwab_cfg = cfg.integrations.schwab
    environment = schwab_cfg.environment
    account_hash = schwab_cfg.account_hash
    lookback_days = int(schwab_cfg.lookback_days)

    if not account_hash:
        # Codex R3 M#1 fix — surface-aware advisory audit row.
        # Pipeline silent-skip; CLI advisory-row. See _step_schwab_snapshot
        # for full rationale comment.
        if surface == "pipeline":
            log.info(
                "_step_schwab_orders: skipped (account_hash not "
                "configured; pipeline-internal silent-skip)"
            )
            return {
                "status": "skipped_no_account_hash",
                "call_ids": [],
                "reconciliation_run_id": None,
                "error": "account_hash not configured",
            }
        ts = _now_iso_ms()
        call_id = audit_service.record_call_start(
            conn,
            ts=ts,
            endpoint="accounts.orders.list",
            pipeline_run_id=pipeline_run_id,
            surface=surface,
            environment=environment,
        )
        audit_service.record_call_finish(
            conn,
            call_id=call_id,
            http_status=None,
            response_time_ms=0,
            rate_limit_remaining=None,
            signature_hash=None,
            status="error",
            error_message=(
                "<account_hash not configured; run `swing schwab setup` first>"
            ),
        )
        log.info(
            "_step_schwab_orders: skipped (account_hash not configured)"
        )
        return {
            "status": "skipped_no_account_hash",
            "call_ids": [call_id],
            "reconciliation_run_id": None,
            "error": "account_hash not configured",
        }

    if client is None:
        # Codex R2 M#1 fix — pipeline-internal no-client skip is silent
        # (no audit row written) to avoid polluting degraded-health
        # surfaces with persistent 'error' rows on every nightly run.
        try:
            client = _build_default_client(cfg, environment)
        except SchwabConfigMissingError:
            log.info(
                "_step_schwab_orders: skipped (no client supplied "
                "pipeline-internally; use `swing schwab fetch --orders` "
                "CLI as primary entry point)"
            )
            return {
                "status": "skipped_no_client",
                "call_ids": [],
                "reconciliation_run_id": None,
                "error": "no client supplied pipeline-internally",
            }

    period_end = last_completed_session(datetime.now())
    from datetime import timedelta
    period_start = period_end - timedelta(days=lookback_days)

    call_ids: list[int] = []
    try:
        orders = get_account_orders(
            client, conn, account_hash,
            from_entered_time=datetime.combine(period_start, datetime.min.time()),
            to_entered_time=datetime.combine(period_end, datetime.max.time()),
            surface=surface, environment=environment,
            pipeline_run_id=pipeline_run_id,
            status=None,
        )
        call_ids.append(_latest_call_id_for_pipeline(conn, pipeline_run_id))

        transactions = get_account_transactions(
            client, conn, account_hash,
            start_date=datetime.combine(period_start, datetime.min.time()),
            end_date=datetime.combine(period_end, datetime.max.time()),
            surface=surface, environment=environment,
            pipeline_run_id=pipeline_run_id,
            types=list(TRANSACTION_TYPES_ALL),
        )
        call_ids.append(_latest_call_id_for_pipeline(conn, pipeline_run_id))

        details = get_account_details(
            client, conn, account_hash,
            surface=surface, environment=environment,
            pipeline_run_id=pipeline_run_id,
        )
        call_ids.append(_latest_call_id_for_pipeline(conn, pipeline_run_id))
    except SchwabApiError as exc:
        log.warning(
            "_step_schwab_orders: Trader-API failure: %s",
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "call_ids": call_ids,
            "reconciliation_run_id": None,
            "error": f"{type(exc).__name__}: api call failed",
        }

    # Production-only gate.
    if environment != "production":
        log.info(
            "_step_schwab_orders: env=%s; sandbox short-circuit (no reconciliation)",
            environment,
        )
        return {
            "status": "sandbox_audit_only",
            "call_ids": call_ids,
            "reconciliation_run_id": None,
            "error": None,
        }

    # Production path: run reconciliation.
    from swing.trades.schwab_reconciliation import run_schwab_reconciliation

    primary_audit_call_id = call_ids[-1]  # the details call (latest semantically)
    try:
        reconciliation_run = run_schwab_reconciliation(
            conn,
            account_hash=account_hash,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            schwab_orders=orders,
            schwab_transactions=transactions,
            schwab_account=details,
            pipeline_run_id=pipeline_run_id,
            schwab_api_call_id=primary_audit_call_id,
        )
    except Exception as exc:
        log.warning(
            "_step_schwab_orders: run_schwab_reconciliation raised: %s",
            type(exc).__name__,
        )
        return {
            "status": "failed",
            "call_ids": call_ids,
            "reconciliation_run_id": None,
            "error": f"reconciliation_failed: {type(exc).__name__}",
        }

    # Link reconciliation_run_id back to each of the 3 audit rows.
    for cid in call_ids:
        if cid is None:
            continue
        audit_service.link_reconciliation_run(
            conn,
            call_id=cid,
            reconciliation_run_id=reconciliation_run.run_id,
        )

    log.info(
        "_step_schwab_orders: completed; reconciliation_run_id=%d "
        "audit_call_ids=%s",
        reconciliation_run.run_id, call_ids,
    )
    return {
        "status": "completed",
        "call_ids": call_ids,
        "reconciliation_run_id": reconciliation_run.run_id,
        "error": None,
    }


def _latest_call_id_for_pipeline(
    conn: sqlite3.Connection, pipeline_run_id: int | None,
) -> int | None:
    """Return the most-recent call_id for this pipeline run (or overall if None).

    Used after a trader wrapper returns successfully — the call_id was just
    written + we need to pass it forward to domain-write linkage.
    """
    if pipeline_run_id is None:
        row = conn.execute(
            "SELECT call_id FROM schwab_api_calls "
            "ORDER BY call_id DESC LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT call_id FROM schwab_api_calls "
            "WHERE pipeline_run_id = ? "
            "ORDER BY call_id DESC LIMIT 1",
            (pipeline_run_id,),
        ).fetchone()
    return row[0] if row else None


__all__ = [
    "_step_schwab_orders",
    "_step_schwab_snapshot",
]
