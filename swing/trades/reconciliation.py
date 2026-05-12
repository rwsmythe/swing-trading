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
from swing.journal.tos_import import (
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


# Spec §3.3 CHECK enum (5 values).
RESOLUTION_TYPES: tuple[str, ...] = (
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
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
        - resolution must be in ``RESOLUTION_TYPES``.
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
    if resolution not in RESOLUTION_TYPES:
        raise ValueError(
            f"resolution must be one of {RESOLUTION_TYPES}; got {resolution!r}"
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
