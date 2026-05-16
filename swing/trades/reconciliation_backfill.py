"""Phase 12 Sub-bundle C — `swing journal reconcile-backfill` orchestrator.

T-D.6 scaffold landed the iteration shell + transactional contract +
pipeline-exclusion guard + ``BackfillSummary`` / ``BackfillOutcome``
dataclasses + the ``_classify_and_apply`` private callback as a stub.

T-D.7 (this task) implements **Pass 1**: persisted-JSON-only
classification + dispatch. Reads each unresolved discrepancy's
``expected_value_json`` + ``actual_value_json`` + the FK-referenced
journal row, invokes :func:`swing.trades.reconciliation_classifier.classify_discrepancy`
(with ``validator_chain=None`` — defense-in-depth is enforced at C.C
service-layer apply-time), then branches:

  * Tier-1 → :func:`swing.trades.reconciliation_auto_correct.apply_tier1_correction`
    (public own-tx); records ``BackfillOutcome(tier=1,
    outcome='tier1_applied', correction_id=...)``.
  * Tier-2 (NOT ``_pass_2_required``) →
    :func:`swing.trades.reconciliation_auto_correct.stamp_pending_ambiguity`
    (public own-tx); records ``BackfillOutcome(tier=2,
    outcome='tier2_stamped', ambiguity_kind=...)``.
  * Pass-2-required (classifier emits tier-2 ``unsupported`` with
    ``_pass_2_required=True`` substring in ``correction_reason``) →
    Pass 1 SKIPS dispatch; records ``BackfillOutcome(tier=None,
    outcome='pass_2_pending', ...)`` placeholder for T-D.8 to overwrite.

T-D.8 will fill in Pass-2 Schwab re-fetch via
``get_account_orders_audited`` + reclassify + dispatch.

Transaction-ownership contract (Codex R2 Major #1 fix, plan §E.6 #4):
  ``run_backfill`` operates in AUTOCOMMIT MODE — it does NOT open its
  own ``BEGIN IMMEDIATE``. Per-discrepancy service helpers (C.C's
  ``apply_tier1_correction`` / ``stamp_pending_ambiguity`` etc.) own
  their own transactions end-to-end; the backfill orchestrator only
  sequences invocations + aggregates the ``BackfillSummary``.

Pipeline-exclusion guard (Codex R2 Major #2 fix, plan §E.6 #4):
  At entry, ``run_backfill`` asserts ``pipeline_runs.state='running'``
  count is zero; raises ``BackfillPipelineActiveError`` otherwise.
  Mirrors ``FinvizPipelineActiveError`` (``swing/integrations/finviz_api``)
  + ``SchwabPipelineActiveError`` (``swing/integrations/schwab/client``)
  precedent.

Sandbox short-circuit:
  When ``environment='sandbox'``, tier-1 dispatch via
  ``apply_tier1_correction`` invokes its inner short-circuit (spec §5.9
  + C.C T-C.2 LOCK): no journal mutation; ``CorrectionResult.correction_id
  is None``. T-D.7 records the resulting BackfillOutcome with
  ``outcome='tier1_skipped_sandbox'`` so the counter wiring honors the
  no-mutation invariant. Tier-2 stamp still fires under sandbox per
  C.C contract (it's a journal-resolution flip, not a domain mutation).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from swing.data.models import ReconciliationDiscrepancy
from swing.data.repos.reconciliation import _DISCREPANCY_SELECT_COLUMNS, _row_to_discrepancy

# Re-export at module attribute path so tests can ``patch(
# "swing.trades.reconciliation_backfill.get_account_orders_audited", ...)``
# at the backfill seam instead of monkey-patching the integrations module
# directly (tests use ``unittest.mock.patch`` with this dotted path).
from swing.integrations.schwab.trader import get_account_orders_audited

logger = logging.getLogger(__name__)


# Pass-2 source-canonical sandbox short-circuit rationale (spec §9.7).
_SANDBOX_PASS_2_REASON = (
    "sandbox: cannot re-fetch source-canonical payload"
)


# Substring sentinel emitted by the C.B unmatched_*_fill sub-classifier
# in ``correction_reason`` when Pass 1 input was insufficient (persisted
# JSON gives no candidate enumeration). Backfill T-D.7 reads this
# substring + records a 'pass_2_pending' placeholder for T-D.8.
#
# Source of truth: swing/trades/reconciliation_classifier.py:742
# ("_pass_2_required=True; backfill must re-fetch Schwab orders ...").
_PASS_2_REQUIRED_SENTINEL = "_pass_2_required=True"


class BackfillPipelineActiveError(RuntimeError):
    """Raised by ``run_backfill`` when a pipeline run is currently in flight.

    Mirrors ``FinvizPipelineActiveError`` + ``SchwabPipelineActiveError``
    precedent. The backfill orchestrator MUST refuse to run while a
    pipeline-internal reconciliation is in progress, since both write
    domain rows under their own transactions and Pass-2 Schwab API
    calls would compete for the same ``schwab_api_calls`` audit-row PK
    range (plan §E.6 #4 / Codex R2 Major #2).
    """


@dataclass
class BackfillOutcome:
    """One per-discrepancy outcome record aggregated into ``BackfillSummary``.

    T-D.7 (Pass 1) classifies + dispatches inline. T-D.8 (Pass 2) will
    re-fetch Schwab orders + reclassify for ``outcome='pass_2_pending'``
    placeholders.
    """

    discrepancy_id: int
    ticker: str | None
    discrepancy_type: str
    tier: int | None  # 1, 2, or None for skipped/projection/pass-2-pending
    outcome: str
    # ``outcome`` is one of:
    #   'projection_tier1' / 'projection_tier2' / 'projection_pass_2'
    #       (dry-run mode; no journal mutation)
    #   'tier1_applied'                  (--apply, tier-1 auto-corrected)
    #   'tier1_skipped_sandbox'          (--apply, env='sandbox' short-circuit)
    #   'tier2_stamped'                  (--apply, tier-2 stamp via service)
    #   'tier2_skipped_sandbox'          (--apply, env='sandbox' Pass-2
    #                                     short-circuit — discrepancy left
    #                                     unresolved; Codex R1 Major #2)
    #   'pass_2_pending'                 (--apply, Pass-1 emitted
    #                                     _pass_2_required; T-D.8 will retry)
    #   'pass_2_failed'                  (T-D.8 consumer)
    #   'skipped_already_resolved'       (idempotency early-return; T-D.9)
    #   'skipped_pass_2_failed'          (T-D.9 consumer)
    #   'errored'                        (classifier / service raised)
    ambiguity_kind: str | None = None
    correction_id: int | None = None
    pass_2_call_id: int | None = None
    reason: str | None = None
    # T-D.7: rendering hints for the dry-run projection matrix.
    # ``projection_outcome_label`` is the rendered "Projected outcome"
    # column text per acceptance criterion #4 (e.g., "tier-1 auto-apply",
    # "Pass 2 required (re-fetch)").
    projection_outcome_label: str | None = None
    # ``projection_action_needed`` is the rendered "Action needed"
    # column text (e.g., "(none)", "--apply or --no-pass-2").
    projection_action_needed: str | None = None


@dataclass
class BackfillSummary:
    """Aggregate counters + per-row outcomes for one backfill invocation.

    Per plan §E.6 #5. Counters incremented as ``_classify_and_apply``
    returns each ``BackfillOutcome``. ``per_discrepancy_outcomes`` is
    the full audit trail for the CLI summary table.
    """

    tier1_applied: int = 0
    tier1_skipped_sandbox: int = 0
    tier2_stamped: int = 0
    # Codex R1 Major #2 fix — sandbox + --apply short-circuit for
    # Pass-2-required discrepancies preserves the C.C sandbox LOCK
    # (no journal mutation under sandbox). The discrepancy stays
    # ``unresolved`` rather than being stamped ``pending_ambiguity_
    # resolution``; this counter tracks the no-op outcome.
    tier2_skipped_sandbox: int = 0
    tier_errored: int = 0
    pass_2_pending: int = 0
    pass_2_failed: int = 0
    skipped_already_resolved: int = 0
    skipped_pass_2_failed: int = 0
    # Dry-run projection counters (no journal mutation; populated when
    # ``run_backfill(dry_run=True)``).
    projection_tier1: int = 0
    projection_tier2: int = 0
    projection_pass_2: int = 0
    per_discrepancy_outcomes: list[BackfillOutcome] = field(default_factory=list)


def _check_pipeline_not_running(conn: sqlite3.Connection) -> None:
    """Raise ``BackfillPipelineActiveError`` if a pipeline_runs row is running.

    Mirrors ``swing/cli_schwab.py:_check_pipeline_not_running``.
    """
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE state = 'running' LIMIT 1",
    ).fetchone()
    if row is not None:
        raise BackfillPipelineActiveError(
            f"Pipeline run {row[0]} is currently in flight. Refusing to "
            f"run `swing journal reconcile-backfill`. Wait for the "
            f"pipeline to complete or kill it.",
        )


def _iter_unresolved_discrepancies(
    conn: sqlite3.Connection,
    *,
    ticker: str | None,
    limit: int | None,
) -> list[ReconciliationDiscrepancy]:
    """Return the unresolved discrepancies that backfill should iterate.

    Filters by ``ticker`` (optional) + caps by ``limit`` (optional).
    Sort order is ``discrepancy_id ASC`` (deterministic; oldest first
    so Pass-2 audit-row attribution stays monotonic).
    """
    where = ["resolution = 'unresolved'"]
    params: list[Any] = []
    if ticker:
        where.append("ticker = ?")
        params.append(ticker)
    sql = (
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} "
        "FROM reconciliation_discrepancies "
        "WHERE " + " AND ".join(where) + " "
        "ORDER BY discrepancy_id ASC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_discrepancy(r) for r in rows]


# Substring fingerprint of Pass-2 failure-state persisted via
# ``stamp_pending_ambiguity(..., resolution_reason='Pass 2 re-fetch failed:
# ...')``. Used by T-D.9 to identify rows eligible for the
# ``--retry-pass-2-failures`` flag's scoped iteration.
_PASS_2_FAILED_REASON_LIKE = "%Pass 2 re-fetch failed%"


def _iter_pass_2_failed_discrepancies(
    conn: sqlite3.Connection,
    *,
    ticker: str | None,
    limit: int | None,
) -> list[ReconciliationDiscrepancy]:
    """Return the Pass-2-failed discrepancies eligible for retry.

    Per plan §E.9 acceptance #3 + spec §8.2/§8.3: scopes iteration to
    rows WHERE ``resolution = 'pending_ambiguity_resolution' AND
    ambiguity_kind = 'unsupported' AND resolution_reason LIKE '%Pass 2
    re-fetch failed%'``.

    Used in two paths:
      (a) The ``--retry-pass-2-failures`` branch in :func:`run_backfill`
          uses this list as the iteration target.
      (b) The default-``--apply`` branch uses this list to enumerate
          skip-only outcomes so the operator sees an accurate
          ``skipped_pass_2_failed`` counter.
    """
    where = [
        "resolution = 'pending_ambiguity_resolution'",
        "ambiguity_kind = 'unsupported'",
        "resolution_reason LIKE ?",
    ]
    params: list[Any] = [_PASS_2_FAILED_REASON_LIKE]
    if ticker:
        where.append("ticker = ?")
        params.append(ticker)
    sql = (
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} "
        "FROM reconciliation_discrepancies "
        "WHERE " + " AND ".join(where) + " "
        "ORDER BY discrepancy_id ASC"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_discrepancy(r) for r in rows]


def _read_current_resolution(
    conn: sqlite3.Connection, discrepancy_id: int,
) -> str | None:
    """Fresh single-column read of a discrepancy's resolution.

    Used by ``_classify_and_apply`` for the apply-time SELECT-first
    idempotency check (NEW C.C lesson #3 — SELECT-first idempotency
    precedes payload validation; defense-in-depth against a race between
    iteration-list SELECT and per-row apply).

    Returns ``None`` if the discrepancy does not exist (defensive — should
    not happen in normal flow since the iteration list was derived from
    the same DB).
    """
    row = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?",
        (int(discrepancy_id),),
    ).fetchone()
    if row is None:
        return None
    return row[0]


def _parse_actual_value_json(disc: ReconciliationDiscrepancy) -> Any | None:
    """T-D.7 — derive a classifier-friendly source_payload from
    ``actual_value_json``.

    Mirrors :func:`swing.trades.schwab_reconciliation._extract_source_payload`
    semantics so the Pass-1 classifier receives the same shape it sees
    during the in-pipeline pivot at C.C. The ``{"matched": null}``
    sentinel emitted by unmatched_*_fill discrepancies maps to ``None``
    so the classifier's None-branch fires (which produces tier-2 with
    ``_pass_2_required`` for unmatched_*_fill, or
    ``schwab_returned_no_match`` for entry_price_mismatch).
    """
    if disc.actual_value_json is None:
        return None
    try:
        payload = json.loads(disc.actual_value_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if (
        isinstance(payload, dict)
        and "matched" in payload
        and payload["matched"] is None
        and len(payload) == 1
    ):
        return None
    return payload


def _fetch_journal_row(
    conn: sqlite3.Connection, disc: ReconciliationDiscrepancy,
) -> dict[str, Any] | None:
    """T-D.7 — read the journal row associated with a discrepancy's FK.

    Mirrors :func:`swing.trades.schwab_reconciliation._fetch_journal_row`
    verbatim so the classifier sees the same shape Pass-1-in-pipeline
    sees. Discrepancies whose FK columns are all NULL (e.g., equity_delta
    keyed only by run_id) return ``None``.
    """
    if disc.fill_id is not None:
        row = conn.execute(
            "SELECT fill_id, trade_id, fill_datetime, action, quantity, price "
            "FROM fills WHERE fill_id = ?",
            (int(disc.fill_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "fill_id": row[0], "trade_id": row[1],
            "fill_datetime": row[2], "action": row[3],
            "quantity": row[4], "price": row[5],
        }
    if disc.trade_id is not None:
        row = conn.execute(
            "SELECT id, ticker, current_stop FROM trades WHERE id = ?",
            (int(disc.trade_id),),
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "ticker": row[1], "current_stop": row[2]}
    if disc.cash_movement_id is not None:
        row = conn.execute(
            "SELECT id, date, kind, amount FROM cash_movements WHERE id = ?",
            (int(disc.cash_movement_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "date": row[1], "kind": row[2], "amount": row[3],
        }
    return None


_PASS_2_FAILURE_REASON_PREFIX = "Pass 2 re-fetch failed"


def _orders_to_classifier_payload(
    orders: list[Any],
) -> list[dict[str, Any]]:
    """Convert ``list[SchwabOrderResponse]`` → ``list[dict]`` for the
    classifier's expected source_payload shape.

    The C.B ``_classify_unmatched_fill_shared`` (spec §4.3.2/.3.3) treats
    source_payload as ``list[Mapping]`` where each entry responds to
    ``.get("quantity")``. ``SchwabOrderResponse`` is a frozen dataclass
    (no ``.get()``); convert at the backfill→classifier seam.

    Per C.B classifier source comments: ``SchwabOrderResponse.price`` is
    limit/stop price, NOT execution price; surfacing here gives the
    classifier the qty + price fields it needs to choose between
    ``multi_partial_vs_consolidated`` / ``multi_match_within_window``
    /etc. — the Pass-2-tier-1-FORBIDDEN LOCK at §8.4 is encoded
    structurally in the sub-classifier (never emits tier-1 regardless of
    payload shape).
    """
    out: list[dict[str, Any]] = []
    for o in orders:
        # Defensive: tolerate either dataclass-instance or pre-converted
        # dict (for cassette/replay flexibility).
        if isinstance(o, dict):
            out.append(o)
            continue
        out.append({
            "order_id": getattr(o, "order_id", None),
            "status": getattr(o, "status", None),
            "enter_time": getattr(o, "enter_time", None),
            "instrument_symbol": getattr(o, "instrument_symbol", None),
            "instruction": getattr(o, "instruction", None),
            "quantity": getattr(o, "quantity", None),
            "order_type": getattr(o, "order_type", None),
            "price": getattr(o, "price", None),
        })
    return out


def _parse_disc_created_at(disc: ReconciliationDiscrepancy) -> datetime:
    """Parse ``ReconciliationDiscrepancy.created_at`` (ISO string) into
    a ``datetime`` for Pass-2 window arithmetic. Falls back to ``now()``
    when the field is missing or malformed (defense-in-depth)."""
    raw = disc.created_at
    if not raw:
        return datetime.now()
    # Strip a trailing 'Z' if present (datetime.fromisoformat doesn't
    # accept it in pre-3.11 — we target 3.11+ but be tolerant).
    s = raw.rstrip("Z")
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return datetime.now()


def _format_pass_2_line(
    *,
    discrepancy_id: int,
    ticker: str | None,
    discrepancy_type: str,
    call_id: int | None,
    tier: int | None,
    ambiguity_kind: str | None,
) -> str:
    """Render the per-discrepancy Pass-2 printout line per plan §E.8 #9.

    Shape:
      ``disc <id> <ticker> (<type>): Pass 2 → call_id=<int>; tier-<n>;
        ambiguity_kind='<kind>'``

    The format is operator-facing — they copy ``call_id`` for use with
    ``swing journal discrepancy resolve-ambiguity --schwab-api-call-id``
    (T-D.3-wired flag) for forward-linkage of correction rows to the
    Pass-2 audit row (`reconciliation_corrections.schwab_api_call_id`).
    """
    tk = ticker or "-"
    tier_str = f"tier-{tier}" if tier is not None else "tier-?"
    return (
        f"disc {discrepancy_id} {tk} ({discrepancy_type}): "
        f"Pass 2 → call_id={call_id}; {tier_str}; "
        f"ambiguity_kind={ambiguity_kind!r}"
    )


def _pass_2_dispatch(
    conn: sqlite3.Connection,
    disc: ReconciliationDiscrepancy,
    *,
    schwab_client: Any,
    environment: str,
    account_hash: str | None,
    dry_run: bool,
    no_pass_2_on_dry_run: bool,
) -> tuple[Any, int | None, str | None]:
    """Run Pass 2 for one Pass-2-required discrepancy.

    Returns ``(reclassification, call_id, failure_reason)``:
      - ``reclassification``: a ``ClassificationResult`` (always tier-2
        per §8.4 Pass-2-tier-1-FORBIDDEN LOCK) OR ``None`` when the
        caller should stamp tier-2 ``unsupported`` directly with a custom
        rationale (sandbox / dry-run-skip / re-fetch failure).
      - ``call_id``: the persisted ``schwab_api_calls.call_id`` returned
        by ``get_account_orders_audited`` when invoked; ``None``
        otherwise.
      - ``failure_reason``: a free-text rationale to thread into
        BackfillOutcome.reason / persisted resolution_reason when
        ``reclassification`` is ``None``.

    Branches:
      1. ``environment='sandbox'``: short-circuit BEFORE Schwab API call
         per §9.7. No audit row written. Return tier-2 ``unsupported``
         shape via ``failure_reason``.
      2. Dry-run + ``--no-pass-2-on-dry-run``: skip API entirely. Same as
         sandbox failure-rationale-only path.
      3. Otherwise: invoke ``get_account_orders_audited`` + filter by
         ticker + classify via shared C.B sub-classifier. On raised
         exception, return ``(None, None, "Pass 2 re-fetch failed: ...")``.
    """
    from swing.trades.reconciliation_classifier import classify_discrepancy

    # Sandbox short-circuit — §9.7 LOCK. Fires BEFORE any Schwab API call.
    if environment == "sandbox":
        return (None, None, _SANDBOX_PASS_2_REASON)

    # Dry-run with --no-pass-2-on-dry-run — skip Pass 2 entirely.
    if dry_run and no_pass_2_on_dry_run:
        return (
            None, None,
            "Pass 2 skipped per --no-pass-2-on-dry-run (dry-run mode)",
        )

    # Re-fetch via audited wrapper. Failure-mode per acceptance #6.
    created_at = _parse_disc_created_at(disc)
    from_dt = created_at - timedelta(days=1)
    to_dt = created_at + timedelta(days=1)

    try:
        call_id, schwab_orders = get_account_orders_audited(
            schwab_client,
            conn,
            account_hash or "",
            from_entered_time=from_dt,
            to_entered_time=to_dt,
            surface="cli",
            environment=environment,
        )
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        # Pipeline NEVER crashes (Phase 11 forward-binding lesson #2).
        reason = (
            f"{_PASS_2_FAILURE_REASON_PREFIX}: "
            f"{type(exc).__name__}: {exc}"
        )
        logger.warning(
            "backfill Pass 2 re-fetch raised on discrepancy %s: %s: %s",
            disc.discrepancy_id, type(exc).__name__, exc,
        )
        return (None, None, reason)

    # Filter by ticker (audited wrapper returns ALL orders in the window
    # across all symbols per plan §E.8 #2).
    matching_orders = [
        o for o in schwab_orders
        if getattr(o, "instrument_symbol", None) == disc.ticker
    ]
    source_payload = _orders_to_classifier_payload(matching_orders)

    # Read the journal row (same shape Pass 1 uses) so the classifier's
    # qty-sum comparison works (journal_row.get("quantity")).
    journal_row = _fetch_journal_row(conn, disc)

    # Invoke the C.B sub-classifier with the Pass-2 source payload.
    # Per §8.4 Pass-2-tier-1-FORBIDDEN LOCK: the sub-classifier NEVER
    # emits tier-1 from this code path regardless of payload shape.
    reclassification = classify_discrepancy(
        disc,
        source_payload=source_payload,
        journal_row=journal_row,
        validator_chain=None,
    )
    return (reclassification, call_id, None)


def _handle_pass_2(
    conn: sqlite3.Connection,
    disc: ReconciliationDiscrepancy,
    *,
    disc_id: int,
    dry_run: bool,
    schwab_client: Any,
    environment: str,
    account_hash: str | None,
    no_pass_2_on_dry_run: bool,
    allow_pending_update: bool = False,
) -> BackfillOutcome:
    """Pass-2 dispatch for one Pass-2-required discrepancy.

    Combines:
      (a) ``_pass_2_dispatch`` (sandbox / dry-run-skip / fetch + classify);
      (b) per-discrepancy ``call_id`` printout (plan §E.8 #9);
      (c) ``--apply`` tier-2 stamp via PUBLIC ``stamp_pending_ambiguity``;
      (d) Pass-2 failure-counter increment via the caller's summary
          wiring (returned outcome.outcome == 'pass_2_failed' but also
          tier-2 stamped per the LOCK).

    The Pass-2-tier-1-FORBIDDEN LOCK is enforced STRUCTURALLY at the
    C.B sub-classifier — this helper trusts the reclassification result.
    """
    from swing.trades.reconciliation_auto_correct import (
        CallerHeldTransactionError,
        stamp_pending_ambiguity,
    )

    reclassification, call_id, failure_reason = _pass_2_dispatch(
        conn,
        disc,
        schwab_client=schwab_client,
        environment=environment,
        account_hash=account_hash,
        dry_run=dry_run,
        no_pass_2_on_dry_run=no_pass_2_on_dry_run,
    )

    # Default rendering values (overwritten below on Pass-2 success).
    ambiguity_kind: str | None = None
    reason: str | None = None

    if reclassification is not None:
        ambiguity_kind = reclassification.ambiguity_kind
        reason = reclassification.correction_reason
    else:
        # Sandbox / dry-run-skip / fetch-failure path: emit tier-2
        # unsupported with custom rationale. The ``run_backfill`` counter
        # loop reads ``outcome.reason.startswith(_PASS_2_FAILURE_REASON_PREFIX)``
        # to increment ``BackfillSummary.pass_2_failed`` — sandbox and
        # --no-pass-2-on-dry-run skip paths use different prefixes so
        # they do NOT increment the failure counter.
        ambiguity_kind = "unsupported"
        reason = failure_reason

    # Per-discrepancy Pass-2 printout (plan §E.8 #9). Operator copies
    # call_id from this line to use --schwab-api-call-id on resolve.
    print(
        _format_pass_2_line(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            call_id=call_id,
            tier=2,
            ambiguity_kind=ambiguity_kind,
        ),
    )

    if dry_run:
        # Spec §8.2 LOCK — dry-run DOES write the audit row (read's
        # audit-trail contract; already written by audited wrapper above
        # when not sandbox-skipped) but does NOT stamp the discrepancy.
        label = (
            f"tier-2 stamp ({ambiguity_kind})"
            if ambiguity_kind and reclassification is not None
            else f"tier-2 stamp ({ambiguity_kind})"
        )
        action = "operator resolution via `swing journal discrepancy`"
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=2,
            outcome="projection_pass_2",
            ambiguity_kind=ambiguity_kind,
            correction_id=None,
            pass_2_call_id=call_id,
            reason=reason,
            projection_outcome_label=label,
            projection_action_needed=action,
        )

    # Codex R1 Major #2 fix — under sandbox + --apply, the
    # ``_pass_2_dispatch`` short-circuit returns BEFORE any Schwab API
    # call (preserves the C.C sandbox short-circuit LOCK contract:
    # environment='sandbox' MUST NOT mutate domain rows). Without this
    # guard, ``stamp_pending_ambiguity`` would flip the discrepancy
    # resolution to ``pending_ambiguity_resolution`` + emit ambiguity_kind
    # — which IS a journal mutation. The discrepancy stays ``unresolved``
    # under sandbox so the operator can re-run under production for
    # honest tier-2 classification.
    if environment == "sandbox":
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=2,
            outcome="tier2_skipped_sandbox",
            ambiguity_kind=None,
            correction_id=None,
            pass_2_call_id=call_id,
            reason=(
                "sandbox: Pass 2 short-circuited; discrepancy left "
                "unresolved (re-run under production for honest tier-2 "
                "classification)"
            ),
            projection_outcome_label="tier-2 skipped (sandbox)",
            projection_action_needed=(
                "re-run under environment='production'"
            ),
        )

    # --apply mode: stamp via PUBLIC stamp_pending_ambiguity (own-tx).
    # T-D.9: when ``allow_pending_update=True`` (retry-pass-2-failures
    # path), the inner UPDATE overwrites a prior ``pending_ambiguity_
    # resolution`` stamp; otherwise it's a no-op-idempotent return.
    try:
        stamp_pending_ambiguity(
            conn,
            discrepancy_id=disc_id,
            ambiguity_kind=ambiguity_kind or "unsupported",
            resolution_reason=reason or "",
            allow_pending_update=allow_pending_update,
        )
    except CallerHeldTransactionError:
        raise
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning(
            "backfill Pass 2 stamp_pending_ambiguity failed on "
            "discrepancy %s: %s: %s",
            disc_id, type(exc).__name__, exc,
        )
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=2,
            outcome="errored",
            ambiguity_kind=ambiguity_kind,
            pass_2_call_id=call_id,
            reason=f"stamp_pending failed: {type(exc).__name__}: {exc}",
            projection_outcome_label="tier-2 errored",
            projection_action_needed="investigate manually",
        )

    return BackfillOutcome(
        discrepancy_id=disc_id,
        ticker=disc.ticker,
        discrepancy_type=disc.discrepancy_type,
        tier=2,
        outcome="tier2_stamped",
        ambiguity_kind=ambiguity_kind,
        pass_2_call_id=call_id,
        reason=reason,
        projection_outcome_label=(
            f"tier-2 stamped ({ambiguity_kind})"
            if ambiguity_kind
            else "tier-2 stamped"
        ),
        projection_action_needed=(
            "operator resolution via `swing journal discrepancy`"
        ),
    )


def _classify_and_apply(
    conn: sqlite3.Connection,
    disc: ReconciliationDiscrepancy,
    *,
    dry_run: bool,
    schwab_client: Any,
    environment: str,
    account_hash: str | None,
    no_pass_2_on_dry_run: bool,
    retry_pass_2_failures: bool,
) -> BackfillOutcome:
    """T-D.7 — Pass 1 persisted-JSON-only classification + dispatch.

    Flow:
      1. Read ``expected_value_json`` + ``actual_value_json`` from the
         discrepancy + the FK-referenced journal row.
      2. Invoke ``classify_discrepancy`` with ``validator_chain=None``
         (defense-in-depth re-invocation lives at C.C apply-time).
      3. Detect the ``_pass_2_required=True`` substring in
         ``classification.correction_reason``: that branch is the C.B
         unmatched_*_fill sub-classifier signaling that Pass 1's
         persisted-JSON-only input is insufficient + Pass 2 must fire.
      4. Dispatch:
         - Dry-run → no mutation; record projection outcome.
         - ``--apply``, tier-1 → public ``apply_tier1_correction`` (own-tx).
         - ``--apply``, tier-2 (NOT _pass_2_required) → public
           ``stamp_pending_ambiguity`` (own-tx).
         - ``--apply``, _pass_2_required → record ``'pass_2_pending'``
           placeholder for T-D.8 to overwrite.

    Per acceptance criterion #2 the call site MUST pass
    ``validator_chain=None`` — Pass 1 is intentionally simpler than the
    C.C pivot (which composes ``functools.partial(default_validator_chain
    ...)`` for defense-in-depth). C.C re-runs the validator chain inside
    ``_apply_tier1_correction_inner`` step 3 (spec §5.4 + lesson
    "validator-chain re-invocation at C.C apply time defense-in-depth"),
    so backfill doesn't need to pre-validate.
    """
    # Lazy-import C.B + C.C to avoid cyclical imports at module load.
    from swing.trades.reconciliation_auto_correct import (
        CallerHeldTransactionError,
        apply_tier1_correction,
        stamp_pending_ambiguity,
    )
    from swing.trades.reconciliation_classifier import classify_discrepancy

    disc_id = int(disc.discrepancy_id or 0)

    # T-D.9 SELECT-first idempotency check (NEW C.C lesson #3 —
    # SELECT-first idempotency precedes payload validation).
    # Race-condition defense between iteration-list SELECT and
    # apply-time: if a concurrent writer (or a prior backfill loop
    # iteration that mutated state) has flipped the discrepancy to a
    # terminal state OR to ``pending_ambiguity_resolution``, SKIP the
    # row + emit a discriminating BackfillOutcome BEFORE invoking the
    # classifier or any service-layer payload validation.
    #
    # Exception: under ``retry_pass_2_failures=True``, the iteration
    # target is itself ``pending_ambiguity_resolution`` rows — do NOT
    # skip those (the retry path must overwrite via
    # ``allow_pending_update=True``).
    current_resolution = _read_current_resolution(conn, disc_id)
    if current_resolution is not None and current_resolution != "unresolved":
        if retry_pass_2_failures and (
            current_resolution == "pending_ambiguity_resolution"
        ):
            # Retry path: this is the expected state; proceed.
            pass
        else:
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=None,
                outcome="skipped_already_resolved",
                reason=(
                    f"discrepancy already in resolution="
                    f"{current_resolution!r}; skipping (idempotent)"
                ),
                projection_outcome_label="skipped (already resolved)",
                projection_action_needed="(none)",
            )

    try:
        source_payload = _parse_actual_value_json(disc)
        journal_row = _fetch_journal_row(conn, disc)
        classification = classify_discrepancy(
            disc,
            source_payload=source_payload,
            journal_row=journal_row,
            validator_chain=None,  # Acceptance criterion #2 — intentional.
        )
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning(
            "backfill Pass 1 classifier exception on discrepancy %s: %s: %s",
            disc_id, type(exc).__name__, exc,
        )
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=None,
            outcome="errored",
            reason=f"classifier exception: {type(exc).__name__}: {exc}",
            projection_outcome_label="error (classifier)",
            projection_action_needed="investigate manually",
        )

    # Pass-2-required signal: C.B unmatched_*_fill emits tier-2
    # 'unsupported' with `_pass_2_required=True` substring in the
    # `correction_reason`. T-D.7 reads this signal + records a
    # placeholder; T-D.8 will overwrite with the real Pass-2 outcome.
    pass_2_required = (
        classification.tier == 2
        and _PASS_2_REQUIRED_SENTINEL in (classification.correction_reason or "")
    )

    # T-D.8 — Pass-2-required short-circuit (BEFORE the dry-run branch).
    # The Pass-2 path covers BOTH dry-run (writes audit row by spec §8.2
    # LOCK; does NOT stamp the discrepancy) AND --apply (writes audit
    # row + stamps via stamp_pending_ambiguity).
    if pass_2_required:
        return _handle_pass_2(
            conn,
            disc,
            disc_id=disc_id,
            dry_run=dry_run,
            schwab_client=schwab_client,
            environment=environment,
            account_hash=account_hash,
            no_pass_2_on_dry_run=no_pass_2_on_dry_run,
            allow_pending_update=retry_pass_2_failures,
        )

    if dry_run:
        # No journal mutation; just build the projection record.
        if classification.tier == 1:
            label = "tier-1 auto-apply"
            action = "(none)"
            outcome = "projection_tier1"
        else:
            label = (
                f"tier-2 stamp ({classification.ambiguity_kind})"
                if classification.ambiguity_kind
                else "tier-2 stamp"
            )
            action = "operator resolution via `swing journal discrepancy`"
            outcome = "projection_tier2"
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=classification.tier,
            outcome=outcome,
            ambiguity_kind=classification.ambiguity_kind,
            reason=classification.correction_reason,
            projection_outcome_label=label,
            projection_action_needed=action,
        )

    # --apply mode below — dispatch to C.C public services.

    if classification.tier == 1:
        try:
            result = apply_tier1_correction(
                conn,
                discrepancy_id=disc_id,
                classification=classification,
                environment=environment,
            )
        except CallerHeldTransactionError:
            # Propagate — contract violation by the orchestrator.
            raise
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            logger.warning(
                "backfill Pass 1 apply_tier1_correction failed on "
                "discrepancy %s: %s: %s",
                disc_id, type(exc).__name__, exc,
            )
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="errored",
                reason=f"apply_tier1 failed: {type(exc).__name__}: {exc}",
                projection_outcome_label="tier-1 errored",
                projection_action_needed="investigate manually",
            )
        if result.correction_id is None:
            # Sandbox short-circuit per C.C spec §5.9 + LOCK lesson #2.
            # No journal mutation occurred; classify as a distinct
            # outcome so the counter wiring stays honest.
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="tier1_skipped_sandbox",
                reason=result.notes or "sandbox: domain write short-circuited",
                projection_outcome_label="tier-1 (sandbox skipped)",
                projection_action_needed="(none)",
            )
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=1,
            outcome="tier1_applied",
            correction_id=result.correction_id,
            reason=classification.correction_reason,
            projection_outcome_label="tier-1 applied",
            projection_action_needed="(none)",
        )

    # Tier-2, NOT pass-2-required → stamp pending_ambiguity_resolution
    # via the public C.C service helper. The service owns its own tx;
    # sandbox does NOT short-circuit tier-2 stamps (they're
    # journal-resolution flips, not domain mutations — per C.C
    # _stamp_pending_ambiguity_inner contract).
    try:
        stamp_pending_ambiguity(
            conn,
            discrepancy_id=disc_id,
            ambiguity_kind=classification.ambiguity_kind or "unsupported",
            resolution_reason=classification.correction_reason,
        )
    except CallerHeldTransactionError:
        raise
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning(
            "backfill Pass 1 stamp_pending_ambiguity failed on "
            "discrepancy %s: %s: %s",
            disc_id, type(exc).__name__, exc,
        )
        return BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=2,
            outcome="errored",
            ambiguity_kind=classification.ambiguity_kind,
            reason=f"stamp_pending failed: {type(exc).__name__}: {exc}",
            projection_outcome_label="tier-2 errored",
            projection_action_needed="investigate manually",
        )
    return BackfillOutcome(
        discrepancy_id=disc_id,
        ticker=disc.ticker,
        discrepancy_type=disc.discrepancy_type,
        tier=2,
        outcome="tier2_stamped",
        ambiguity_kind=classification.ambiguity_kind,
        reason=classification.correction_reason,
        projection_outcome_label=(
            f"tier-2 stamped ({classification.ambiguity_kind})"
            if classification.ambiguity_kind
            else "tier-2 stamped"
        ),
        projection_action_needed=(
            "operator resolution via `swing journal discrepancy`"
        ),
    )


def run_backfill(
    conn: sqlite3.Connection,
    *,
    dry_run: bool,
    schwab_client: Any,
    environment: str,
    account_hash: str | None,
    ticker: str | None = None,
    limit: int | None = None,
    no_pass_2_on_dry_run: bool = False,
    retry_pass_2_failures: bool = False,
) -> BackfillSummary:
    """Orchestrate Pass-1 / Pass-2 backfill across unresolved discrepancies.

    T-D.6 SCAFFOLD — iterates unresolved rows + emits per-row
    ``BackfillOutcome`` placeholder records via the ``_classify_and_apply``
    stub. The actual classification + dispatch logic is implemented in
    T-D.7 (Pass 1) + T-D.8 (Pass 2 + Schwab audited fetch) + T-D.9
    (idempotency + counter wiring).

    Args:
        conn: SQLite connection; MUST NOT have an open transaction
            (run_backfill operates in autocommit mode and lets the
            per-discrepancy service helpers own their own txs).
        dry_run: When True, no journal mutations are performed.
        schwab_client: Schwabdev client for Pass 2 (T-D.8). Opaque at
            T-D.6 scaffold — pass-through.
        environment: ``'production'`` or ``'sandbox'``. Propagated to
            C.C public-service calls so sandbox short-circuits are
            honored end-to-end.
        account_hash: Schwab account hash for Pass 2 (T-D.8).
        ticker: When provided, scopes iteration to a single ticker.
        limit: When provided, caps the number of discrepancies iterated.
        no_pass_2_on_dry_run: When True, dry-run skips Pass-2 Schwab
            API calls (avoid burning audit-row PKs on a preview). T-D.8
            consumer.
        retry_pass_2_failures: When True, re-attempts Pass-2 on
            discrepancies whose previous backfill attempt failed at
            Pass 2 (idempotency hook for T-D.9).

    Returns:
        ``BackfillSummary`` with counters + per-row outcomes.

    Raises:
        BackfillPipelineActiveError: if a pipeline_runs row is in state
            ``'running'`` at backfill entry.
    """
    _check_pipeline_not_running(conn)

    # T-D.9 — iteration-target branch on retry-pass-2-failures flag.
    #
    #   retry_pass_2_failures=False (default): iterate unresolved rows
    #     (Pass 1 + Pass 2 dispatch); ALSO enumerate Pass-2-failed rows
    #     as SKIP-only outcomes so the operator sees an accurate
    #     ``skipped_pass_2_failed`` counter (spec §8.3 + plan §E.9 #2).
    #
    #   retry_pass_2_failures=True (opt-in): iterate Pass-2-failed rows
    #     ONLY; each retry re-fetches Schwab + re-classifies + overwrites
    #     the prior failure stamp via ``stamp_pending_ambiguity(...,
    #     allow_pending_update=True)`` (plan §E.9 #3 + spec §8.2/§8.3).
    if retry_pass_2_failures:
        discrepancies = _iter_pass_2_failed_discrepancies(
            conn, ticker=ticker, limit=limit,
        )
        pass_2_failed_skip_list: list[ReconciliationDiscrepancy] = []
    else:
        discrepancies = _iter_unresolved_discrepancies(
            conn, ticker=ticker, limit=limit,
        )
        # Default-mode enumeration of Pass-2-failed rows for skip-only
        # outcome emission (--retry-pass-2-failures hint surfaces in
        # CLI summary).
        pass_2_failed_skip_list = _iter_pass_2_failed_discrepancies(
            conn, ticker=ticker, limit=limit,
        )

    summary = BackfillSummary()
    for disc in discrepancies:
        outcome = _classify_and_apply(
            conn,
            disc,
            dry_run=dry_run,
            schwab_client=schwab_client,
            environment=environment,
            account_hash=account_hash,
            no_pass_2_on_dry_run=no_pass_2_on_dry_run,
            retry_pass_2_failures=retry_pass_2_failures,
        )
        summary.per_discrepancy_outcomes.append(outcome)
        # Counter wiring — T-D.7 Pass 1 outcomes + T-D.8 Pass 2 outcomes.
        if outcome.outcome == "tier1_applied":
            summary.tier1_applied += 1
        elif outcome.outcome == "tier1_skipped_sandbox":
            summary.tier1_skipped_sandbox += 1
        elif outcome.outcome == "tier2_stamped":
            summary.tier2_stamped += 1
        elif outcome.outcome == "tier2_skipped_sandbox":
            summary.tier2_skipped_sandbox += 1
        elif outcome.outcome == "pass_2_pending":
            # Legacy T-D.7 placeholder — should NOT be emitted now that
            # T-D.8 ships; retained for graceful-degradation defense.
            summary.pass_2_pending += 1
        elif outcome.outcome == "pass_2_failed":
            summary.pass_2_failed += 1
        elif outcome.outcome == "skipped_already_resolved":
            summary.skipped_already_resolved += 1
        elif outcome.outcome == "skipped_pass_2_failed":
            summary.skipped_pass_2_failed += 1
        elif outcome.outcome == "errored":
            summary.tier_errored += 1
        elif outcome.outcome == "projection_tier1":
            summary.projection_tier1 += 1
        elif outcome.outcome == "projection_tier2":
            summary.projection_tier2 += 1
        elif outcome.outcome == "projection_pass_2":
            summary.projection_pass_2 += 1
        # T-D.8 — Pass-2 re-fetch failure-mode counter (orthogonal to
        # the canonical ``outcome`` enum; transported via the
        # ``reason`` substring per spec §8.4 + plan §E.8 #6 LOCK).
        # T-D.9 fix: do NOT double-count tier2_stamped + pass_2_failed;
        # only increment pass_2_failed when the outcome itself is NOT
        # already incrementing tier2_stamped (which already represents
        # the Pass-2 attempt outcome). The failure-mode signal lives in
        # the reason substring for operator triage but the canonical
        # bucket counter is tier2_stamped; the pass_2_failed bucket is
        # the rate of Pass-2 RE-FETCH FAILURES specifically.
        if (
            outcome.reason
            and outcome.reason.startswith(_PASS_2_FAILURE_REASON_PREFIX)
            and outcome.outcome != "tier2_stamped"
            and outcome.outcome != "errored"
        ):
            summary.pass_2_failed += 1
        elif (
            outcome.reason
            and outcome.reason.startswith(_PASS_2_FAILURE_REASON_PREFIX)
            and outcome.outcome == "tier2_stamped"
        ):
            # tier2_stamped already counts the row; we treat
            # pass_2_failed as a parallel signal counter (operator
            # diagnostic — "how many of the tier-2 stamps were caused by
            # Pass-2 fetch failure vs honest tier-2 classification?").
            # Keep the increment but it does NOT double-count anything
            # because tier2_stamped + pass_2_failed are SEPARATE
            # diagnostic bucket counters per spec §8.4 + plan §E.9 #4.
            summary.pass_2_failed += 1

    # T-D.9 — emit SKIP-only outcomes for Pass-2-failed rows on default
    # ``--apply``. Per plan §E.9 #2 + spec §8.3, the operator sees an
    # accurate ``skipped_pass_2_failed`` counter even though the rows
    # were not iterated by the default ``resolution = 'unresolved'``
    # filter. This is the explicit-enumeration path (no journal mutation;
    # no Schwab API call; no service-layer invocation).
    for disc in pass_2_failed_skip_list:
        disc_id = int(disc.discrepancy_id or 0)
        skip_outcome = BackfillOutcome(
            discrepancy_id=disc_id,
            ticker=disc.ticker,
            discrepancy_type=disc.discrepancy_type,
            tier=None,
            outcome="skipped_pass_2_failed",
            ambiguity_kind=disc.ambiguity_kind,
            reason=(
                "Pass-2-failed state persisted; "
                "use --retry-pass-2-failures to retry"
            ),
            projection_outcome_label="skipped (Pass-2-failed)",
            projection_action_needed="--retry-pass-2-failures",
        )
        summary.per_discrepancy_outcomes.append(skip_outcome)
        summary.skipped_pass_2_failed += 1

    return summary


# ============================================================================
# CLI rendering helpers (consumed by `swing journal reconcile-backfill`)
# ============================================================================


def format_projection_table_header() -> str:
    """Header for the dry-run projection table per acceptance criterion #4.

    5-column shape: ID | Ticker | Type | Projected outcome | Action needed.
    """
    return (
        f"{'ID':<4}| {'Ticker':<6} | {'Type':<22} | "
        f"{'Projected outcome':<32} | Action needed"
    )


def format_projection_table_separator() -> str:
    """Underline beneath the header to mirror acceptance-criterion-#4 sample."""
    return (
        f"{'-' * 4}+{'-' * 8}+{'-' * 24}+{'-' * 34}+{'-' * 26}"
    )


def format_projection_row(outcome: BackfillOutcome) -> str:
    """Single-row formatter for the dry-run projection table.

    Reads ``projection_outcome_label`` + ``projection_action_needed``
    populated by ``_classify_and_apply``; falls back to ``outcome`` if
    those rendering hints are absent (e.g., legacy callers).
    """
    label = outcome.projection_outcome_label or outcome.outcome
    action = outcome.projection_action_needed or "—"
    return (
        f"{outcome.discrepancy_id:<4}| "
        f"{(outcome.ticker or '-'):<6} | "
        f"{outcome.discrepancy_type:<22} | "
        f"{label:<32} | {action}"
    )


def format_summary_block(summary: BackfillSummary) -> str:
    """Multi-line summary block printed at end of CLI invocation.

    Layout per plan §E.9 #4 (T-D.9) — operator-facing canonical lines:
      Backfill summary:
        Tier 1 applied: N
        Tier 2 stamped: M
          (of which Pass 2 re-fetch failed: L)
        Errored: K
        Skipped (already resolved): X
        Skipped (Pass-2-failed; use --retry-pass-2-failures to retry): Y

    Overlap semantics (Item 2 pre-Codex review):
      ``pass_2_failed`` is a DIAGNOSTIC SUB-COUNTER of ``tier2_stamped``,
      NOT a parallel bucket. Per the counter wiring at
      :func:`run_backfill` (lines marked "T-D.9 fix: do NOT double-count"),
      every row whose ``reason`` starts with "Pass 2 re-fetch failed" and
      whose outcome is ``tier2_stamped`` increments BOTH counters
      (``tier2_stamped`` is the canonical bucket; ``pass_2_failed`` is the
      operator-diagnostic signal "how many of those tier-2 stamps came
      from a Pass-2 re-fetch failure vs honest tier-2 classification?").
      Reading them as flat parallel counters would double-count L rows.
      Rendering nested with "(of which ...)" makes the overlap explicit
      so an operator seeing ``M=5, L=3`` correctly interprets 5 distinct
      tier-2 outcomes with 3 of them stemming from Pass-2 re-fetch
      failure (NOT 8 distinct outcomes).

    Diagnostic counters (tier1_skipped_sandbox + pass_2_pending +
    projection_*) follow on indented lines for operator triage but are
    NOT part of the §E.9 #4 binding layout.
    """
    return (
        "\nBackfill summary:\n"
        f"  Tier 1 applied: {summary.tier1_applied}\n"
        f"  Tier 2 stamped: {summary.tier2_stamped}\n"
        f"    (of which Pass 2 re-fetch failed: {summary.pass_2_failed})\n"
        f"  Errored: {summary.tier_errored}\n"
        f"  Skipped (already resolved): {summary.skipped_already_resolved}\n"
        f"  Skipped (Pass-2-failed; use --retry-pass-2-failures to retry): "
        f"{summary.skipped_pass_2_failed}\n"
        "  --- diagnostic counters ---\n"
        f"  tier1_skipped_sandbox:    {summary.tier1_skipped_sandbox}\n"
        f"  tier2_skipped_sandbox:    {summary.tier2_skipped_sandbox}\n"
        f"  pass_2_pending:           {summary.pass_2_pending}\n"
        f"  projection_tier1:         {summary.projection_tier1}\n"
        f"  projection_tier2:         {summary.projection_tier2}\n"
        f"  projection_pass_2:        {summary.projection_pass_2}\n"
        f"  total iterated:           {len(summary.per_discrepancy_outcomes)}"
    )
