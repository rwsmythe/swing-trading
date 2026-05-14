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
  - Both steps CALL Schwab + WRITE audit rows under either env.
  - Domain writes (snapshot, reconciliation_run, discrepancies) are SKIPPED
    when `cfg.integrations.schwab.environment != 'production'`.

The `client` parameter is optional for test injection. In production,
callers (pipeline runner; CLI `swing schwab fetch` subcommands) construct
`schwabdev.Client(...)` directly and pass in. The schwabdev Client
construction is NOT performed inside this module (single-Client-instance
discipline per plan §A.2).

Failure-tolerance per plan §3.4.4:
  - Trader-API failures (auth/rate/etc.) are caught + logged + the step
    returns without aborting the pipeline. The audit row reflects the
    failure (`status='auth_failed'` / `'rate_limited'` / `'error'`).
  - Other exceptions (programming errors, config-missing) propagate so
    the pipeline runner's per-step `except Exception` catch can decide.

Account-hash-missing path: if `cfg.integrations.schwab.account_hash` is
None (operator hasn't run `swing schwab setup` yet), the step writes a
single advisory audit row + returns. No domain writes; no schwabdev call.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from swing.data.datetime_helpers import now_ms
from swing.data.repos import schwab_api_calls as schwab_repo
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
        # No account configured — emit a single advisory audit row + return.
        # Endpoint='accounts.details' (the call we would have made).
        # Status='error' with explanatory error_message.
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
        client = _build_default_client(cfg, environment)

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
        client = _build_default_client(cfg, environment)

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
