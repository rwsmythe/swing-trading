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

    Codex R2 Major #3 — carries the accumulated ``partial_summary`` when
    a pipeline lands mid-iteration so the CLI can surface what was
    already committed BEFORE the abort. The first iteration that
    committed a tier-1 correction / tier-2 stamp remains persisted (its
    own service-tx already COMMITed); the abort cleanly skips remaining
    rows. ``partial_summary`` is None when the exception is raised at
    entry (no iteration ran yet).
    """

    def __init__(
        self,
        message: str,
        *,
        partial_summary: BackfillSummary | None = None,
    ) -> None:
        super().__init__(message)
        self.partial_summary = partial_summary


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
    #   'projection_auto_redirect'       (dry-run, Pass-2 reclassified to
    #                                     multi-leg auto-redirect; Phase
    #                                     12.5 #1 T-1.5.B)
    #   'tier1_applied'                  (--apply, tier-1 auto-corrected)
    #   'tier1_skipped_sandbox'          (--apply, env='sandbox' short-circuit)
    #   'tier1_multi_leg_auto_redirected' (--apply, Pass-2 reclassified to
    #                                     multi-leg auto-redirect + dispatched
    #                                     via apply_tier2_resolution with
    #                                     auto-redirect overrides; Phase
    #                                     12.5 #1 T-1.5.B)
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
    # Codex R2 Minor #1 + Codex R3 Minor #1 — counts ONLY dry-run
    # projection paths where the Schwab Pass-2 fetch FAILED (raised an
    # exception during ``--dry-run`` execution). Other Pass-2 "did not
    # produce a useful classification" paths use distinct counters:
    # explicit ``--no-pass-2-on-dry-run`` increments ``projection_pass_2``;
    # sandbox-skip (apply-mode, no Schwab call) increments
    # ``tier2_skipped_sandbox``; honest apply-mode Pass-2 fetch failures
    # increment ``pass_2_failed`` (which IS a subset of ``tier2_stamped``).
    # Keeping these distinct preserves R1's nested-overlap semantics for
    # apply-mode while giving dry-run a dedicated top-level line so the
    # operator sees that PROJECTION accuracy was lost on N rows.
    pass_2_projection_unavailable: int = 0
    # Codex R2 Major #3 — mid-iteration abort signal. Set to True when
    # ``run_backfill`` aborts because a pipeline_runs row appeared
    # mid-iteration; the partial summary is still returned via
    # ``BackfillPipelineActiveError.partial_summary`` so the CLI can
    # surface what completed BEFORE the abort.
    aborted_mid_iteration: bool = False
    abort_reason: str | None = None
    # Phase 12.5 #1 T-1.5.B — multi-leg auto-redirect counters per spec
    # §7.2 + plan §A T-1.5.B. The backfill ``_handle_pass_2`` is the
    # OPERATIONAL firing site (per F20: the initial pivot CANNOT emit
    # the recipe today; backfill's ``_orders_to_classifier_payload``
    # builds the rich list-shape source_payload from freshly-fetched
    # Schwab orders WITH execution-grain data).
    tier1_multi_leg_auto_redirected: int = 0
    projection_auto_redirect: int = 0
    # Codex R2 Major #1 fix — removed the dedicated sandbox-skip counter
    # for the multi-leg auto-redirect branch. The corresponding pre-check
    # in ``_handle_pass_2`` was unreachable under real production flow
    # because ``_pass_2_dispatch`` short-circuits sandbox BEFORE
    # classification (per §9.7 LOCK) and returns ``reclassification=None``
    # — the auto-redirect branch never fires under sandbox. The real
    # sandbox outcome for a Pass-2 discrepancy is ``tier2_skipped_sandbox``
    # (see line ~1029). T-1.6's inner-fn short-circuit in
    # ``apply_tier2_resolution`` + pivot-loop sentinel remain as defensive
    # future-proofing per F20 + spec §7.6 LOCK.
    per_discrepancy_outcomes: list[BackfillOutcome] = field(default_factory=list)


def _check_pipeline_not_running(
    conn: sqlite3.Connection,
    *,
    partial_summary: BackfillSummary | None = None,
) -> None:
    """Raise ``BackfillPipelineActiveError`` if a pipeline_runs row is running.

    Mirrors ``swing/cli_schwab.py:_check_pipeline_not_running``.

    Codex R1 Major #3 — Race-window note: the entry-time check at
    ``run_backfill`` is necessary but not sufficient. ``run_backfill``
    operates in AUTOCOMMIT MODE (no outer transaction; per-discrepancy
    service helpers own their own BEGIN IMMEDIATE / COMMIT envelopes
    per plan §E.6 #4). A pipeline can therefore start AFTER the entry
    check and BEFORE / DURING per-discrepancy dispatch. The mitigation
    is to call this helper BEFORE EACH per-discrepancy iteration in
    ``run_backfill``'s loop. If a pipeline started mid-iteration the
    helper raises ``BackfillPipelineActiveError`` and the loop aborts
    with a clean partial-progress summary (rows processed so far stay
    persisted via their own transactions; remaining rows are skipped).
    The cost is one SELECT per iteration — cheap (~50 production
    discrepancies even on a backlog).
    """
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE state = 'running' LIMIT 1",
    ).fetchone()
    if row is not None:
        message = (
            f"Pipeline run {row[0]} is currently in flight. Refusing to "
            f"run `swing journal reconcile-backfill`. Wait for the "
            f"pipeline to complete or kill it."
        )
        # Codex R2 Major #3 — carry partial_summary on the exception so
        # the CLI can render rows already processed BEFORE the abort.
        # When called at entry (no iteration yet), partial_summary is
        # None and the exception behaves as a plain RuntimeError.
        if partial_summary is not None:
            partial_summary.aborted_mid_iteration = True
            partial_summary.abort_reason = message
        raise BackfillPipelineActiveError(
            message, partial_summary=partial_summary,
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
            # F24 LOCK (Codex R1 Major #4): every output dict MUST carry
            # an ``executions`` key so the dict-branch + non-dict-branch
            # outputs converge on shape contract. Cassette/replay
            # fixtures pre-Phase-12.5 #1 do NOT include ``executions``
            # keys; normalize to ``None`` (data-unavailable sentinel)
            # when absent; pass through verbatim when present.
            if "executions" not in o:
                out.append({**o, "executions": None})
            else:
                out.append(o)
            continue
        # Phase 12.5 #1 T-1.3 — tri-valued execution-grain emit
        # (None / [] / [legs...]) so the classifier's multi-leg
        # auto-redirect path (T-1.1 predicate) consumes leg-grain data
        # via ``so.get('executions')`` from each source_payload entry.
        # Leg dataclass-instances are flattened to plain dicts with the
        # 4 plan-prescribed keys (leg_id / price / quantity / time);
        # ``mismarked_quantity`` + ``instrument_id`` are NOT surfaced
        # at this seam — they're not consumed by the classifier (F25:
        # no SchwabExecutionLeg references leak out of this function).
        out.append({
            "order_id": getattr(o, "order_id", None),
            "status": getattr(o, "status", None),
            "enter_time": getattr(o, "enter_time", None),
            "instrument_symbol": getattr(o, "instrument_symbol", None),
            "instruction": getattr(o, "instruction", None),
            "quantity": getattr(o, "quantity", None),
            "order_type": getattr(o, "order_type", None),
            "price": getattr(o, "price", None),
            "executions": (
                [
                    {
                        "leg_id": leg.leg_id,
                        "price": leg.price,
                        "quantity": leg.quantity,
                        "time": leg.time,
                    }
                    for leg in (o.executions or [])
                ]
                if getattr(o, "executions", None) is not None
                else None
            ),
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
    outcome: str | None = None,
) -> str:
    """Render the per-discrepancy Pass-2 printout line per plan §E.8 #9.

    Shape:
      ``disc <id> <ticker> (<type>): Pass 2 -> call_id=<int>; tier-<n>;
        ambiguity_kind='<kind>'``

    The format is operator-facing — they copy ``call_id`` for use with
    ``swing journal discrepancy resolve-ambiguity --schwab-api-call-id``
    (T-D.3-wired flag) for forward-linkage of correction rows to the
    Pass-2 audit row (`reconciliation_corrections.schwab_api_call_id`).

    Phase 12.5 #1 T-1.5 — when ``outcome == 'tier1_multi_leg_auto_redirected'``
    (or ``'projection_auto_redirect'``), annotate ``tier=1`` + the
    ambiguity_kind with the ``(auto-redirected)`` suffix for operator
    forensic transparency. Both the apply-mode and the dry-run-projection
    rows surface as tier-1 in the printout (the auto-redirect path resolves
    a tier-2 discrepancy with a tier-1-equivalent execution-grain payload
    + auto attribution, so operators read it as "tier-1-by-auto-redirect").
    ASCII-only per F12 / CLAUDE.md cp1252 gotcha.
    """
    tk = ticker or "-"
    if outcome in {
        "tier1_multi_leg_auto_redirected",
        "projection_auto_redirect",
    }:
        annotated_tier_str = "tier-1 (auto-redirected)"
        annotated_kind = (
            f"{ambiguity_kind} (auto-redirected)"
            if ambiguity_kind
            else "multi_partial_vs_consolidated (auto-redirected)"
        )
        return (
            f"disc {discrepancy_id} {tk} ({discrepancy_type}): "
            f"Pass 2 -> call_id={call_id}; {annotated_tier_str}; "
            f"ambiguity_kind={annotated_kind!r}"
        )
    tier_str = f"tier-{tier}" if tier is not None else "tier-?"
    return (
        f"disc {discrepancy_id} {tk} ({discrepancy_type}): "
        f"Pass 2 -> call_id={call_id}; {tier_str}; "
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
    partial_summary: BackfillSummary | None = None,
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

    Phase 12.5 #1 T-1.5.B — when the C.B sub-classifier emits an
    ``auto_redirect_recipe`` (multi-leg execution-grain Pass-2
    reclassification per spec §7.2), this helper short-circuits the
    legacy tier-2 stamp path + dispatches via
    :func:`apply_tier2_resolution` with the auto-redirect overrides.
    Returns one of two outcomes on the auto-redirect branch:
    ``'projection_auto_redirect'`` (dry-run) /
    ``'tier1_multi_leg_auto_redirected'`` (apply, production).
    The §7.5 fallback fires when ``apply_tier2_resolution`` raises
    ``ValidatorRejectedError`` / ``ValueError`` post-stamp (e.g., qty-
    tolerance trip): the stamp persists + the outcome is
    ``'tier2_stamped'`` with a reason citing the auto-redirect decline.

    Sandbox + apply-mode on a Pass-2 discrepancy short-circuits inside
    ``_pass_2_dispatch`` (returns ``reclassification=None``) and falls
    through to the legacy ``tier2_skipped_sandbox`` path; the auto-
    redirect branch is therefore unreachable under sandbox by design
    (Codex R2 Major #1).
    """
    from swing.trades.reconciliation_auto_correct import (
        CallerHeldTransactionError,
        InvalidOverrideComboError,
        ValidatorRejectedError,
        _validate_override_combo,
        apply_tier2_resolution,
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

    # Phase 12.5 #1 T-1.5.B — multi-leg auto-redirect dispatch.
    # Recognized when the C.B sub-classifier emits a recipe on the
    # Pass-2 reclassification (multi-leg execution-grain shape).
    # OPERATIONAL firing site per F20 (the initial pivot at
    # ``schwab_reconciliation._pivot_classify_and_dispatch_for_run``
    # cannot emit the recipe today because Pass-1 source_payload is
    # the persisted ``{"matched": null}`` sentinel).
    if (
        reclassification is not None
        and reclassification.auto_redirect_recipe is not None
    ):
        recipe = reclassification.auto_redirect_recipe

        # Defense-in-depth: validate override combo BEFORE any mutation
        # (matches T-1.4 service-layer guard at apply_tier2_resolution
        # entry). InvalidOverrideComboError MUST propagate per F21.
        _validate_override_combo(
            choice_code=recipe["choice_code"],
            applied_by_override=recipe["applied_by_override"],
            correction_action_override=recipe[
                "correction_action_override"
            ],
            resolved_by_override=recipe["resolved_by"],
        )

        # Per-discrepancy Pass-2 printout — annotated with the auto-
        # redirect outcome label for operator forensic transparency.
        # Use the projection-mode label when dry-run; the apply-mode
        # label otherwise (both annotate tier-1 + auto-redirected).
        annotation_outcome = (
            "projection_auto_redirect" if dry_run
            else "tier1_multi_leg_auto_redirected"
        )
        print(
            _format_pass_2_line(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                call_id=call_id,
                tier=1,
                ambiguity_kind=ambiguity_kind,
                outcome=annotation_outcome,
            ),
        )

        if dry_run:
            # Dry-run: project the auto-redirect outcome without mutating.
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="projection_auto_redirect",
                ambiguity_kind="multi_partial_vs_consolidated",
                correction_id=None,
                pass_2_call_id=call_id,
                reason=(
                    f"would auto-redirect via split_into_partials: "
                    f"{reclassification.correction_reason}"
                ),
                projection_outcome_label=(
                    "multi-leg auto-redirect (projected)"
                ),
                projection_action_needed=(
                    "--apply will dispatch via apply_tier2_resolution"
                    "(applied_by_override='auto', ...)"
                ),
            )

        # Codex R2 Major #1 fix — removed unreachable sandbox pre-check
        # from this branch. ``_pass_2_dispatch`` short-circuits sandbox
        # at line ~630 BEFORE classification per §9.7 LOCK; that path
        # returns ``reclassification=None`` so this auto-redirect branch
        # is never entered under real production flow. Defensive sandbox
        # short-circuiting persists at T-1.6's inner-fn level + the
        # pivot-loop sentinel per F20 / spec §7.6 LOCK.

        # --apply, production: 2-step own-tx sequence per spec §7.2.
        # Codex R3 Major #4 fix — per-service-write pipeline-exclusion
        # recheck (matches existing patterns at lines 745-751 + 966-974
        # + 1033-1036). Recheck BEFORE EACH own-tx mutation.
        _check_pipeline_not_running(conn, partial_summary=partial_summary)
        stamp_succeeded = False
        try:
            # Step 1: stamp pending_ambiguity_resolution via PUBLIC
            # own-tx helper. apply_tier2_resolution's inner reads this
            # state to gate the handler dispatch.
            stamp_pending_ambiguity(
                conn,
                discrepancy_id=disc_id,
                ambiguity_kind="multi_partial_vs_consolidated",
                resolution_reason=reclassification.correction_reason,
                allow_pending_update=allow_pending_update,
            )
            stamp_succeeded = True
        except InvalidOverrideComboError:
            raise  # Developer-bug propagates per F21
        except CallerHeldTransactionError:
            raise
        except Exception as exc:  # noqa: BLE001 — stamp failure path
            # Codex R3 Major #3 fix — stamp failure is NOT a §7.5
            # fallback case (the §7.5 fresh-savepoint pattern presumes
            # stamp succeeded inside a rolled-back outer SAVEPOINT;
            # backfill uses own-tx so no SAVEPOINT exists). Stamp
            # failure routes to existing 'errored' outcome path.
            logger.warning(
                "backfill auto-redirect stamp_pending_ambiguity failed "
                "on discrepancy %s: %s: %s",
                disc_id, type(exc).__name__, exc,
            )
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="errored",
                ambiguity_kind="multi_partial_vs_consolidated",
                pass_2_call_id=call_id,
                reason=(
                    f"auto-redirect stamp failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                projection_outcome_label="auto-redirect errored",
                projection_action_needed="investigate manually",
            )

        # Codex R3 Major #4 fix — second pipeline-not-running check
        # between stamp + apply closes the in-row race window per the
        # existing per-service-write recheck pattern.
        _check_pipeline_not_running(conn, partial_summary=partial_summary)
        try:
            # Step 2: dispatch via PUBLIC apply_tier2_resolution own-tx
            # with overrides. T-1.6's environment kwarg threading lands
            # here; sandbox short-circuit at the inner is defensive
            # belt-and-suspenders (this branch already short-circuited
            # above for sandbox). schwab_api_call_id=call_id preserves
            # audit linkage from the Pass-2 refetch audit row.
            result = apply_tier2_resolution(
                conn,
                discrepancy_id=disc_id,
                choice_code=recipe["choice_code"],
                operator_custom_payload=recipe["payload"],
                operator_reason=(
                    f"multi-leg auto-redirect: "
                    f"{reclassification.correction_reason}"
                ),
                applied_by_override=recipe["applied_by_override"],
                correction_action_override=recipe[
                    "correction_action_override"
                ],
                resolved_by_override=recipe["resolved_by"],
                schwab_api_call_id=call_id,
                environment=environment,
            )
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="tier1_multi_leg_auto_redirected",
                ambiguity_kind="multi_partial_vs_consolidated",
                correction_id=result.correction_id,
                pass_2_call_id=call_id,
                reason=(
                    f"auto-redirected: {reclassification.correction_reason}"
                ),
                projection_outcome_label="multi-leg auto-redirected",
                projection_action_needed="(none)",
            )
        except InvalidOverrideComboError:
            raise  # Developer-bug propagates per F21
        except CallerHeldTransactionError:
            raise
        except (ValidatorRejectedError, ValueError) as exc:
            # Per spec §7.5 fallback: stamp_succeeded is True at this
            # point; apply_tier2_resolution own-tx rollback unwinds the
            # apply attempt; discrepancy stays in
            # pending_ambiguity_resolution (set by step 1). Return
            # tier2_stamped outcome with note citing the fallback.
            assert stamp_succeeded, (
                "step 2 catch unreachable without step 1 success"
            )
            return BackfillOutcome(
                discrepancy_id=disc_id,
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=2,
                outcome="tier2_stamped",
                ambiguity_kind="multi_partial_vs_consolidated",
                pass_2_call_id=call_id,
                reason=f"auto-redirect declined post-stamp: {exc}",
                projection_outcome_label=(
                    "tier-2 stamped (auto-redirect declined)"
                ),
                projection_action_needed=(
                    "operator resolution via `swing journal discrepancy`"
                ),
            )

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
    #
    # Codex R2 Major #2 — per-service-write pipeline-exclusion recheck
    # closes the in-row race window. A pipeline starting AFTER the
    # Pass-2 fetch (which may have made an audited Schwab API call) +
    # BEFORE the stamp would race against stamp_pending_ambiguity's
    # own BEGIN IMMEDIATE. Recheck here gates the journal mutation.
    # Codex R2 Major #3 — pass partial_summary so the abort surfaces.
    _check_pipeline_not_running(conn, partial_summary=partial_summary)
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
    partial_summary: BackfillSummary | None = None,
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
            partial_summary=partial_summary,
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
        # Codex R2 Major #2 — per-service-write pipeline-exclusion recheck
        # closes the in-row race window. The per-iteration recheck at
        # ``run_backfill`` fires BEFORE classifier; a pipeline starting
        # AFTER that check + BEFORE this service-write would race against
        # ``apply_tier1_correction``'s own BEGIN IMMEDIATE. Recheck here
        # (~1 SELECT per write; cheap at <100 production discrepancies).
        # Codex R2 Major #3 — pass partial_summary so the abort surfaces
        # accumulated work to the CLI.
        _check_pipeline_not_running(conn, partial_summary=partial_summary)
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
    #
    # Codex R2 Major #2 — per-service-write pipeline-exclusion recheck
    # closes the in-row race window (see apply_tier1 callsite above).
    # Codex R2 Major #3 — pass partial_summary so the abort surfaces.
    _check_pipeline_not_running(conn, partial_summary=partial_summary)
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
        # Codex R1 Major #3 — per-iteration pipeline-exclusion recheck
        # to close the entry-check vs per-discrepancy-dispatch race
        # window. ``run_backfill`` operates in AUTOCOMMIT (no outer tx
        # per plan §E.6 #4) so a pipeline can land between the entry
        # check + the next per-discrepancy dispatch. The recheck raises
        # ``BackfillPipelineActiveError`` and aborts further iteration;
        # rows already processed remain persisted (their own service-
        # layer txs committed end-to-end).
        #
        # Codex R2 Major #3 — pass ``partial_summary=summary`` so the
        # exception carries the rows processed so far for CLI rendering.
        _check_pipeline_not_running(conn, partial_summary=summary)
        outcome = _classify_and_apply(
            conn,
            disc,
            dry_run=dry_run,
            schwab_client=schwab_client,
            environment=environment,
            account_hash=account_hash,
            no_pass_2_on_dry_run=no_pass_2_on_dry_run,
            retry_pass_2_failures=retry_pass_2_failures,
            partial_summary=summary,
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
        # Phase 12.5 #1 T-1.5.B — multi-leg auto-redirect counters.
        elif outcome.outcome == "tier1_multi_leg_auto_redirected":
            summary.tier1_multi_leg_auto_redirected += 1
        elif outcome.outcome == "projection_auto_redirect":
            summary.projection_auto_redirect += 1
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
        #
        # Codex R2 Minor #1 — distinguishes dry-run / projection paths
        # from apply-mode Pass-2 re-fetch failures. The R1 nested
        # rendering "(of which Pass 2 re-fetch failed: L)" beneath
        # "Tier 2 stamped: M" assumed L ⊆ M; under dry-run soft-fail
        # (credentials missing) the reason started with the prefix but
        # the outcome was ``projection_pass_2`` (no stamp), inflating
        # ``pass_2_failed`` above zero while ``tier2_stamped`` stayed at
        # zero — visually contradictory. Apply-mode failures whose
        # outcome IS a tier-2 stamp still increment ``pass_2_failed``;
        # dry-run/projection failures route to the separate
        # ``pass_2_projection_unavailable`` counter, which the summary
        # block renders top-level (not nested).
        if (
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
        elif (
            outcome.reason
            and outcome.reason.startswith(_PASS_2_FAILURE_REASON_PREFIX)
            and outcome.outcome == "projection_pass_2"
        ):
            # Dry-run / sandbox-projection Pass-2 unavailability — NOT a
            # subset of tier2_stamped (no stamp happened). Route to a
            # separate top-level counter so the summary doesn't render
            # "(of which Pass 2 re-fetch failed: 1)" beneath "Tier 2
            # stamped: 0".
            summary.pass_2_projection_unavailable += 1
        elif (
            outcome.reason
            and outcome.reason.startswith(_PASS_2_FAILURE_REASON_PREFIX)
            and outcome.outcome != "errored"
        ):
            # Any other path (e.g., pass_2_pending placeholder reached
            # under apply-mode without a stamp). Keep the prior
            # diagnostic counter behavior for defense-in-depth.
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
    # Codex R2 Minor #1 — top-level Pass-2-unavailable line for the
    # dry-run projection-failure path only (NOT nested under tier2_stamped
    # because no stamp happened); rendered only when non-zero so the
    # standard apply-mode summary stays compact.
    # Codex R3 Minor #1 — label narrowed to the actual counter semantics:
    # only dry-run Pass-2 fetch failures feed this counter; sandbox-skip +
    # explicit `--no-pass-2-on-dry-run` outcomes use different counters
    # (tier2_skipped_sandbox + projection_pass_2 respectively).
    projection_unavailable_line = ""
    if summary.pass_2_projection_unavailable:
        projection_unavailable_line = (
            f"  Pass 2 unavailable (dry-run projection — fetch failed): "
            f"{summary.pass_2_projection_unavailable}\n"
        )

    # Codex R2 Major #3 — abort banner surfaces above the counters so
    # the operator immediately sees that this is a partial summary; the
    # numeric lines below reflect rows that DID commit before the abort.
    abort_banner = ""
    if summary.aborted_mid_iteration:
        reason_suffix = (
            f" ({summary.abort_reason})" if summary.abort_reason else ""
        )
        abort_banner = (
            f"  *** ABORTED MID-ITERATION{reason_suffix}; counters "
            f"below reflect rows processed BEFORE the abort. ***\n"
        )

    # Phase 12.5 #1 T-1.5.B — multi-leg auto-redirect counters.
    # Each line emits ONLY when its counter > 0 (matches existing
    # per-counter suppression pattern at projection_unavailable_line).
    # ASCII-only per F12 / CLAUDE.md cp1252 gotcha.
    multi_leg_lines = ""
    if summary.tier1_multi_leg_auto_redirected:
        multi_leg_lines += (
            f"  Multi-leg auto-redirects applied: "
            f"{summary.tier1_multi_leg_auto_redirected}\n"
        )
    if summary.projection_auto_redirect:
        multi_leg_lines += (
            f"  Multi-leg auto-redirects (dry-run projection): "
            f"{summary.projection_auto_redirect}\n"
        )

    return (
        "\nBackfill summary:\n"
        + abort_banner
        + f"  Tier 1 applied: {summary.tier1_applied}\n"
        + f"  Tier 2 stamped: {summary.tier2_stamped}\n"
        + f"    (of which Pass 2 re-fetch failed: {summary.pass_2_failed})\n"
        + projection_unavailable_line
        + multi_leg_lines
        + f"  Errored: {summary.tier_errored}\n"
        + f"  Skipped (already resolved): {summary.skipped_already_resolved}\n"
        + "  Skipped (Pass-2-failed; use --retry-pass-2-failures to retry): "
        + f"{summary.skipped_pass_2_failed}\n"
        + "  --- diagnostic counters ---\n"
        + f"  tier1_skipped_sandbox:    {summary.tier1_skipped_sandbox}\n"
        + f"  tier2_skipped_sandbox:    {summary.tier2_skipped_sandbox}\n"
        + f"  pass_2_pending:           {summary.pass_2_pending}\n"
        + f"  projection_tier1:         {summary.projection_tier1}\n"
        + f"  projection_tier2:         {summary.projection_tier2}\n"
        + f"  projection_pass_2:        {summary.projection_pass_2}\n"
        + f"  total iterated:           {len(summary.per_discrepancy_outcomes)}"
    )
