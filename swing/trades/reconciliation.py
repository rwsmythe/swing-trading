"""reconciliation service layer — TOS-CSV reconciliation orchestration.

Phase 9 spec §3.3.3 + §4.2 + §6.5 + plan §A.2 + §B file map (T-B.6).

Transactional contract (per dispatch brief §0.3 #5 + Phase 8 R3→R4 lesson —
"reject + simple contract over auto-detect + complicate"; CLAUDE.md gotcha
"in_transaction auto-detect re-introduces the very race the explicit lock
was meant to close"): caller MUST NOT hold an open transaction; this
function ALWAYS owns ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK``; it
REJECTS (does NOT auto-detect) caller-held transactions.

Failure-path semantics per spec §3.3.3 + plan §A.2.1: when reconcile_tos
raises an exception, the run row is PRESERVED + UPDATEd to
``state='failed', error_message=...`` inside the same outer transaction;
discrepancies + cash_movements + fills emitted prior to the failure are
RETAINED in the committed transaction. Audit-trail integrity is
prioritized over rollback purity.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from swing.data.datetime_helpers import now_ms
from swing.data.models import ReconciliationRun
from swing.data.repos import reconciliation as repo
from swing.data.repos.account_equity_snapshots import (
    get_latest_snapshot_on_or_before,
)
from swing.journal.tos_import import (
    extract_account_summary_net_liq,
    extract_stock_fills,
    parse_tos_export,
    reconcile_tos,
)

# Spec §3.3 CHECK enum (10 values).
DISCREPANCY_TYPES: tuple[str, ...] = (
    "close_price_mismatch",
    "stop_mismatch",
    "position_qty_mismatch",
    "cash_movement_mismatch",
    "sector_tamper",
    "snapshot_mismatch",
    "unmatched_open_fill",
    "unmatched_close_fill",
    "entry_price_mismatch",
    "equity_delta",
)


# Spec §3.3 CHECK enum — Phase 12 Sub-bundle C T-A.1 widened 5 → 9 values
# at the migration 0019 schema layer; Codex R1 Major #4 folded the matching
# widening into this Python constant. ``RESOLUTION_TYPES`` is the
# SCHEMA-COVERAGE source-of-truth: the dataclass validator at
# ``swing/data/models.py:_RESOLUTION_VALUES`` mirrors this set verbatim so
# reads of existing rows never raise. Paired schema-CHECK + Python-constant
# + dataclass-validator discipline per CLAUDE.md gotcha.
#
# IMPORTANT (Codex R2 Major #1 + R3 Minor #1 clarification):
# ``resolve_discrepancy`` (the manual operator-resolver service in this
# module) does NOT accept the full 9-value set. The 4 service-owned
# resolutions (``auto_corrected_from_schwab``, ``pending_ambiguity_resolution``,
# ``operator_resolved_ambiguity``, ``operator_overridden``) route through
# the auto-correct service entries in ``swing.trades.reconciliation_auto_correct``
# (apply_tier1 / stamp_pending_ambiguity / apply_tier2 / apply_tier3) and
# are REJECTED by ``resolve_discrepancy`` via
# ``_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS`` + ``_SERVICE_OWNED_RESOLUTIONS``
# below.
RESOLUTION_TYPES: tuple[str, ...] = (
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
    # Phase 12 Sub-bundle C T-A.1 widening (matches migration 0019 +
    # swing/data/models.py:_RESOLUTION_VALUES; spec §3.3 lifecycle).
    "auto_corrected_from_schwab",
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
)


# Spec §3.3.1 + §3.3.2 — default material_to_review per discrepancy type.
# Operator may override post-INSERT via the CLI ``swing journal
# discrepancy resolve --material`` flag (T-B.7). The lookup is the
# binding artifact for emitter-time classification; schema CHECK does
# NOT bind type → material mapping (spec §3.3.2).
MATERIAL_BY_TYPE: dict[str, int] = {
    "close_price_mismatch": 1,
    "stop_mismatch": 1,
    "position_qty_mismatch": 1,
    "cash_movement_mismatch": 0,
    "sector_tamper": 0,  # V1 immaterial; V2 elevates per spec §3.3.2
    "snapshot_mismatch": 0,
    "unmatched_open_fill": 1,
    "unmatched_close_fill": 1,
    "entry_price_mismatch": 1,
    "equity_delta": 0,
}


# Operator hardcoded for V1 (resolved_by audit identifier).
_V1_RESOLVED_BY = "operator"


# Phase 12 C.C Codex R2 M#1 — manual-resolve allowlist.
#
# ``RESOLUTION_TYPES`` (above) is the schema-CHECK-coverage constant
# mirroring migration 0019's 9-value enum. It is the correct
# source-of-truth for the dataclass validator at
# ``swing.data.models._RESOLUTION_VALUES``.
#
# ``resolve_discrepancy`` is the MANUAL operator-driven entry point
# (CLI ``swing journal discrepancy resolve``; future web counterparts).
# The 4 service-owned lifecycle states added at C.A T-A.1 widen the
# schema enum but MUST NOT be settable via the manual entry — each
# requires its own service-layer path in
# ``swing.trades.reconciliation_auto_correct`` which enforces paired
# invariants:
#
#   - ``auto_corrected_from_schwab`` paired with a
#     ``reconciliation_corrections`` audit row (apply_tier1_correction).
#   - ``pending_ambiguity_resolution`` paired with non-NULL
#     ``ambiguity_kind`` per migration 0019 cross-column CHECK
#     (stamp_pending_ambiguity).
#   - ``operator_resolved_ambiguity`` paired with non-NULL
#     ``ambiguity_kind`` AND a correction row
#     (apply_tier2_resolution).
#   - ``operator_overridden`` paired with a correction row
#     (apply_tier3_override).
#
# Allowing manual operator entry into any of these would (a) violate the
# migration 0019 cross-column CHECK for tier-2 ambiguity pairs, and
# (b) forge tier-1/tier-3 audit trails without an actual correction row.
_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS: tuple[str, ...] = (
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
)
_SERVICE_OWNED_RESOLUTIONS: tuple[str, ...] = (
    "auto_corrected_from_schwab",
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
)
_SERVICE_OWNED_ROUTING_HINT: dict[str, str] = {
    "auto_corrected_from_schwab":
        "apply_tier1_correction (or run_*_reconciliation pivot)",
    "pending_ambiguity_resolution": "stamp_pending_ambiguity",
    "operator_resolved_ambiguity": "apply_tier2_resolution",
    "operator_overridden": "apply_tier3_override",
}


# Phase 9 Sub-bundle C T-C.6 cross-bundle wiring (dispatch brief §0.5 #5).
# Emit ``equity_delta`` discrepancy when ``abs(source_net_liq -
# journal_equity) > EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS``. Strict
# greater-than (boundary at $10.00 is NOT-emit; matches Bundle B's
# strict-GT precedent on close_price tolerance comparisons). V2 may
# operator-override via a CLI flag.
EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS: float = 10.00


class CallerHeldTransactionError(RuntimeError):
    """Raised when a caller invokes ``run_tos_reconciliation`` while
    holding an open transaction.

    Phase 8 R3→R4 lesson + CLAUDE.md gotcha "in_transaction auto-detect
    re-introduces the very race the explicit lock was meant to close":
    single-transaction services own BEGIN IMMEDIATE / COMMIT / ROLLBACK;
    they REJECT caller-held transactions rather than silently
    auto-detecting (auto-detect is the failure mode).
    """


def _sha256_hex(data: bytes) -> str:
    """Return hex digest. Empty input yields the spec'd empty-SHA256
    constant (e3b0c44298fc...); pre-empted Codex finding."""
    return hashlib.sha256(data).hexdigest()


def run_tos_reconciliation(
    conn: sqlite3.Connection,
    *,
    csv_path: Path,
    period_end: date | str | None = None,
    period_start: date | str | None = None,
    notes: str | None = None,
    price_tolerance: float = 0.01,
    environment: str | None = None,
) -> ReconciliationRun:
    """Orchestrate a TOS-CSV reconciliation run per spec §3.3.3 + plan §A.2.

    Steps:
      1. Reject caller-held transaction at entry.
      2. Read CSV bytes; compute SHA-256.
      3. BEGIN IMMEDIATE.
      4. INSERT reconciliation_runs row state='running', source='tos_csv',
         source_artifact_{path,sha256}, period_{start,end}, started_ts.
      5. Call reconcile_tos with run_id + emitter forwarded into the
         transaction.
      6. On success: UPDATE state='completed', finished_ts, summary
         fields. COMMIT.
      7. On exception: UPDATE state='failed', finished_ts, error_message.
         COMMIT (preserves the failed row + any partial discrepancies +
         cash_movements + fills committed prior to the exception, per
         spec §3.3.3 audit-trail-integrity-over-rollback-purity).

    Returns:
        ``ReconciliationRun`` dataclass reflecting the row's final state
        (completed or failed).

    Raises:
        CallerHeldTransactionError: caller holds an open transaction.
        FileNotFoundError: csv_path does not exist.
        Any exception from reconcile_tos is caught + folded into the
        failure-path UPDATE (the exception itself is RE-RAISED after the
        COMMIT so the caller learns about the failure, but the row is
        already persisted as failed state at that point).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "run_tos_reconciliation owns its own transaction; caller MUST "
            "NOT hold an open transaction. See dispatch-brief §0.3 #5 + "
            "CLAUDE.md gotcha 'Service-layer with conn:' + 'in_transaction "
            "auto-detect outer transaction guards re-introduce the very "
            "race the explicit lock was meant to close'."
        )

    # Codex R1 M#4 fix: normalize to absolute path per spec §3.2
    # ("absolute path to TOS CSV"). Relative CLI/test invocations are
    # resolved against the process cwd here so the stored provenance
    # is portable across operator sessions.
    csv_path = Path(csv_path).resolve()
    csv_bytes = csv_path.read_bytes()
    sha256 = _sha256_hex(csv_bytes)
    csv_text = csv_bytes.decode("utf-8")

    # period_end / period_start TEXT normalization (accept date or str).
    def _ds(d: date | str | None) -> str | None:
        if d is None:
            return None
        if isinstance(d, date):
            return d.isoformat()
        return str(d)
    period_end_str = _ds(period_end)
    period_start_str = _ds(period_start)

    # Codex R4 M#1 fix: per plan §A.10 + spec §10.6, period_end defaults
    # to the max fill date in the parsed CSV when caller omits it. The
    # filename is operator-controlled and unreliable; last-fill-date is
    # the meaningful data-derived default.
    if period_end_str is None:
        try:
            _sections = parse_tos_export(csv_text)
            _fills = extract_stock_fills(
                _sections.get("Account Trade History", [])
            )
            _dates = [f.date for f in _fills if f.date]
            if _dates:
                period_end_str = max(_dates)
        except Exception:
            # Best-effort default; if the parse breaks here, the same
            # parse will surface inside reconcile_tos and the failure-
            # path UPDATE will capture it. period_end stays None for
            # this run.
            pass

    started_ts = now_ms()

    # Phase 9 within-run dedup is implemented BOTH inside reconcile_tos's
    # _emit closure (per-emit tuple-set skip) AND additionally at the
    # service-emitter layer for defense-in-depth: the service's emitter
    # may be invoked from non-reconcile_tos sites in V2 (e.g., a future
    # CLI for manual discrepancy injection) which would lack the
    # in-process dedup. Keeping both ensures the contract holds.
    dedup_seen: set[tuple] = set()
    counters: dict[str, int] = {
        "discrepancies_count": 0,
        "unresolved_discrepancies_count": 0,
        "trades_reconciled_count": 0,
        "fills_reconciled_count": 0,
    }

    def _emit_to_db(**fields) -> int:
        dtype = fields["discrepancy_type"]
        if dtype not in DISCREPANCY_TYPES:
            raise ValueError(
                f"emitter received unknown discrepancy_type: {dtype!r}"
            )
        # Defense-in-depth on top of the in-tos_import dedup. When the
        # row lacks a fill_id AND cash_movement_id PK anchor (orphan
        # unmatched fills OR trade-attributed overfill closes — Codex
        # R2 M#1 + R3 M#1), the actual_value_json is added to the
        # dedup key so distinct source fills don't collapse silently.
        trade_id = fields.get("trade_id")
        fill_id = fields.get("fill_id")
        cash_id = fields.get("cash_movement_id")
        payload_key: str | None = None
        if fill_id is None and cash_id is None:
            payload_key = fields.get("actual_value_json")
        key = (
            trade_id,
            dtype,
            fields.get("field_name"),
            fields.get("ticker"),
            fill_id,
            cash_id,
            payload_key,
        )
        if key in dedup_seen:
            return -1
        dedup_seen.add(key)
        # Codex R1 M#2 fix: MATERIAL_BY_TYPE is authoritative at INSERT
        # time per spec §3.3.2. Detection-site emitters may PASS a
        # material_to_review hint, but the service IGNORES it and
        # derives from the lookup — preventing a future caller from
        # persisting `stop_mismatch` as immaterial or
        # `cash_movement_mismatch` as material. Operator-override
        # happens POST-INSERT via update_discrepancy_material (CLI
        # `swing journal discrepancy resolve --material` flag).
        material = MATERIAL_BY_TYPE[dtype]
        did = repo.insert_discrepancy(
            conn,
            run_id=fields["run_id"],
            discrepancy_type=dtype,
            field_name=fields["field_name"],
            material_to_review=int(material),
            created_at=now_ms(),
            trade_id=fields.get("trade_id"),
            fill_id=fields.get("fill_id"),
            cash_movement_id=fields.get("cash_movement_id"),
            linked_daily_management_record_id=fields.get(
                "linked_daily_management_record_id"
            ),
            ticker=fields.get("ticker"),
            expected_value_json=fields.get("expected_value_json"),
            actual_value_json=fields.get("actual_value_json"),
            delta_text=fields.get("delta_text"),
            resolution="unresolved",
        )
        counters["discrepancies_count"] += 1
        counters["unresolved_discrepancies_count"] += 1
        return did

    try:
        conn.execute("BEGIN IMMEDIATE")
        run_id = repo.insert_run(
            conn,
            source="tos_csv",
            state="running",
            started_ts=started_ts,
            source_artifact_path=str(csv_path),
            source_artifact_sha256=sha256,
            period_start=period_start_str,
            period_end=period_end_str,
            notes=notes,
        )

        try:
            report = reconcile_tos(
                conn=conn,
                tos_text=csv_text,
                price_tolerance=price_tolerance,
                run_id=run_id,
                emitter=_emit_to_db,
            )
        except Exception as e:
            finished_ts = now_ms()
            # Re-stamp finished_ts to be strictly >= started_ts in cases
            # where the failure is instantaneous (uncommon but defensive
            # against clock-tick collisions on Windows).
            if finished_ts < started_ts:
                finished_ts = started_ts
            repo.update_run_failed(
                conn,
                run_id=run_id,
                finished_ts=finished_ts,
                error_message=f"{type(e).__name__}: {e}",
            )
            conn.commit()
            # Re-raise so the caller learns; the row is preserved.
            raise

        # Success path — populate summary fields.
        # Update fills_reconciled / trades_reconciled best-effort
        # counters from the report.
        counters["fills_reconciled_count"] = (
            len(report.matched_fills)
            + len(report.unmatched_open_fills)
            + len(report.unmatched_close_fills)
            + len(report.price_mismatch_fills)
            + len(report.already_reconciled_fills)
        )
        counters["trades_reconciled_count"] = len({
            d.fill.ticker for d in report.fill_decisions
        })

        summary = {
            "matched_fills": len(report.matched_fills),
            "unmatched_open_fills": len(report.unmatched_open_fills),
            "unmatched_close_fills": len(report.unmatched_close_fills),
            "price_mismatch_fills": len(report.price_mismatch_fills),
            "already_reconciled_fills": len(report.already_reconciled_fills),
            "new_cash_movements": len(report.new_cash_movements),
            "duplicate_cash_movements": len(report.duplicate_cash_movements),
        }

        # ----- T-C.6: equity_delta cross-bundle wiring -----------------
        # Per dispatch brief §0.5 #5 + spec §3.5 + §3.3.1: AFTER the
        # emitter loop + BEFORE update_run_completed, compute the
        # source-side vs journal-side equity delta. Emit
        # ``discrepancy_type='equity_delta'`` only when BOTH sides are
        # available AND the absolute delta exceeds
        # EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS. Stamp the per-run
        # equity columns regardless (NULL when either side is None).
        account_equity_source: float | None = (
            extract_account_summary_net_liq(csv_text)
        )
        account_equity_journal: float | None = None
        if period_end_str is not None:
            journal_snap = get_latest_snapshot_on_or_before(
                conn, asof_date=period_end_str,
            )
            if journal_snap is not None:
                account_equity_journal = journal_snap.equity_dollars
        equity_delta: float | None = None
        if (
            account_equity_source is not None
            and account_equity_journal is not None
        ):
            # Spec §3.3.1 sign convention: journal MINUS source. Result is
            # also persisted on reconciliation_runs.equity_delta_dollars.
            equity_delta = account_equity_journal - account_equity_source
            if abs(equity_delta) > EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS:
                # equity_delta is run-grain: trade_id / fill_id /
                # cash_movement_id / ticker all None per spec §3.3 +
                # §3.3.1. Within-run dedup tuple naturally collapses to
                # a single row (one equity_delta per run).
                _emit_to_db(
                    run_id=run_id,
                    discrepancy_type="equity_delta",
                    field_name="net_liquidating_value",
                    expected_value_json=json.dumps(
                        {"equity_dollars": account_equity_journal},
                        sort_keys=True,
                    ),
                    actual_value_json=json.dumps(
                        {"equity_dollars": account_equity_source},
                        sort_keys=True,
                    ),
                    delta_text=(
                        f"${equity_delta:+.2f} (journal minus source)"
                    ),
                )

        # ----- T-C.6 (Phase 12 C.C): classify + dispatch pivot -----
        # Spec §7.1 LOCKED savepoint-per-discrepancy discipline. Mirrors
        # the T-C.5 pivot at `run_schwab_reconciliation` (per OQ-2 PIVOT
        # BOTH). Skipped under sandbox per spec §5.9.
        if environment != "sandbox":
            from swing.trades.schwab_reconciliation import (
                _pivot_classify_and_dispatch_for_run,
            )
            _pivot_classify_and_dispatch_for_run(
                conn,
                run_id=run_id,
                schwab_orders=[],  # TOS-CSV has no Schwab-side orders
                schwab_api_call_id=None,
                environment=environment,
                counters=counters,
            )
        # Augment summary with pivot counters (defaults preserve back-compat
        # for callers that only read existing summary keys).
        summary["tier1_applied_count"] = counters.get("tier1_applied_count", 0)
        summary["tier2_pending_count"] = counters.get("tier2_pending_count", 0)
        summary["tier3_overridden_count"] = 0  # always 0 — tier-3 post-run
        summary["tier_errored_count"] = counters.get("tier_errored_count", 0)

        # Codex R1 Major #3 — recompute unresolved_discrepancies_count
        # post-pivot. _emit increments at INSERT time; the pivot loop
        # (T-C.6 cross-bundle wiring above) flips rows OFF 'unresolved'
        # (tier-1 → auto_corrected_from_schwab; tier-2 →
        # pending_ambiguity_resolution). Recomputing from the canonical
        # resolution column is more robust than tracking decrement deltas.
        unresolved_now = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "
            "WHERE run_id = ? AND resolution = 'unresolved'",
            (run_id,),
        ).fetchone()[0]
        counters["unresolved_discrepancies_count"] = int(unresolved_now)

        finished_ts = now_ms()
        if finished_ts < started_ts:
            finished_ts = started_ts
        repo.update_run_completed(
            conn,
            run_id=run_id,
            finished_ts=finished_ts,
            trades_reconciled_count=counters["trades_reconciled_count"],
            fills_reconciled_count=counters["fills_reconciled_count"],
            discrepancies_count=counters["discrepancies_count"],
            unresolved_discrepancies_count=counters[
                "unresolved_discrepancies_count"
            ],
            summary_json=json.dumps(summary, sort_keys=True),
            account_equity_journal_dollars=account_equity_journal,
            account_equity_source_dollars=account_equity_source,
            equity_delta_dollars=equity_delta,
        )
        conn.commit()
    except CallerHeldTransactionError:
        raise
    except Exception:
        # Defensive: any exception OUTSIDE the inner try (e.g., the
        # outer INSERT run row itself fails) — best-effort rollback +
        # re-raise. The spec §3.3.3 failure-path is for exceptions
        # DURING reconcile_tos; outer-layer failures (DDL drift,
        # constraint surprises) get rollback semantics.
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise

    out = repo.get_run(conn, run_id)
    assert out is not None  # we just committed
    return out


def resolve_discrepancy(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    resolution: str,
    resolution_reason: str | None = None,
    resolved_by: str = _V1_RESOLVED_BY,
    mistake_tag_assigned: str | None = None,
    material_to_review: int | None = None,
) -> None:
    """Update an existing discrepancy's resolution lifecycle.

    Per spec §3.3 + §4.2 — operator dispositions via this entry point
    (CLI ``swing journal discrepancy resolve`` wraps it in T-B.7).

    Validation:
        - resolution must be in ``_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS``
          (a TIGHTER subset of ``RESOLUTION_TYPES`` — the 4 service-owned
          lifecycle states added at C.A T-A.1 route through
          ``swing.trades.reconciliation_auto_correct`` entries instead
          per Codex R2 M#1).
        - resolution_reason required for journal_corrected /
          source_treated_canonical / manual_override (acknowledged_immaterial
          allows null per spec §3.3 + dataclass validator).
        - material_to_review override (if provided) restricted to {0, 1}.

    Rejects caller-held transaction (single-transaction service).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "resolve_discrepancy owns its own transaction; caller MUST NOT "
            "hold an open transaction."
        )
    if resolution in _SERVICE_OWNED_RESOLUTIONS:
        routing_hint = _SERVICE_OWNED_ROUTING_HINT[resolution]
        raise ValueError(
            f"resolution={resolution!r} is service-owned and cannot be set "
            f"via resolve_discrepancy; route through {routing_hint} in "
            f"swing.trades.reconciliation_auto_correct"
        )
    if resolution not in _MANUAL_RESOLVE_ALLOWED_RESOLUTIONS:
        raise ValueError(
            f"resolution must be one of {_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS}; "
            f"got {resolution!r}"
        )
    # spec §3.3 nullability rule.
    if (
        resolution in ("journal_corrected", "source_treated_canonical",
                       "manual_override")
        and not resolution_reason
    ):
        raise ValueError(
            f"resolution={resolution!r} requires non-empty resolution_reason"
        )

    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = repo.get_discrepancy(conn, discrepancy_id)
        if existing is None:
            raise ValueError(f"discrepancy_id={discrepancy_id} not found")
        repo.update_discrepancy_resolution(
            conn,
            discrepancy_id=discrepancy_id,
            resolution=resolution,
            resolution_reason=resolution_reason,
            resolved_by=resolved_by,
            resolved_at=now_ms(),
            mistake_tag_assigned=mistake_tag_assigned,
        )
        if material_to_review is not None:
            repo.update_discrepancy_material(
                conn,
                discrepancy_id=discrepancy_id,
                material_to_review=int(material_to_review),
            )
        # If the resolution moved off 'unresolved', decrement the
        # parent run's unresolved counter (best-effort — only when
        # the prior state was unresolved AND new is not).
        if (
            existing.resolution == "unresolved"
            and resolution != "unresolved"
        ):
            conn.execute(
                "UPDATE reconciliation_runs SET "
                "unresolved_discrepancies_count = "
                "  MAX(0, COALESCE(unresolved_discrepancies_count, 0) - 1) "
                "WHERE run_id = ?",
                (existing.run_id,),
            )
        conn.commit()
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


__all__ = [
    "CallerHeldTransactionError",
    "DISCREPANCY_TYPES",
    "MATERIAL_BY_TYPE",
    "RESOLUTION_TYPES",
    "resolve_discrepancy",
    "run_tos_reconciliation",
]
