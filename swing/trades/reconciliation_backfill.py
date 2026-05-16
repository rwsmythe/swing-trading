"""Phase 12 Sub-bundle C — `swing journal reconcile-backfill` orchestrator.

T-D.6 SCAFFOLD ONLY — establishes the iteration shell + transactional
contract + pipeline-exclusion guard + ``BackfillSummary`` /
``BackfillOutcome`` dataclasses + the ``_classify_and_apply`` private
callback as a STUB. Pass-1 / Pass-2 classification + tier-1 auto-apply
+ tier-2 stamp dispatch + idempotency are implemented in T-D.7 / T-D.8
/ T-D.9.

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
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from swing.data.models import ReconciliationDiscrepancy
from swing.data.repos.reconciliation import _DISCREPANCY_SELECT_COLUMNS, _row_to_discrepancy


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

    The full classification dispatch + correction lifecycle is T-D.7+;
    T-D.6 emits ``outcome='projection'`` placeholders for the dry-run
    iteration shell.
    """

    discrepancy_id: int
    ticker: str | None
    discrepancy_type: str
    tier: int | None  # 1, 2, or None for skipped/projection
    outcome: str
    # ``outcome`` is one of:
    #   'tier1_applied' | 'tier2_stamped' | 'pass_2_failed'
    #   'skipped_already_resolved' | 'skipped_pass_2_failed'
    #   'errored' | 'projection' (T-D.6 scaffold placeholder)
    ambiguity_kind: str | None = None
    correction_id: int | None = None
    pass_2_call_id: int | None = None
    reason: str | None = None


@dataclass
class BackfillSummary:
    """Aggregate counters + per-row outcomes for one backfill invocation.

    Per plan §E.6 #5. Counters incremented as ``_classify_and_apply``
    returns each ``BackfillOutcome``. ``per_discrepancy_outcomes`` is
    the full audit trail for the CLI summary table.
    """

    tier1_applied: int = 0
    tier2_stamped: int = 0
    tier_errored: int = 0
    pass_2_failed: int = 0
    skipped_already_resolved: int = 0
    skipped_pass_2_failed: int = 0
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
    """T-D.6 STUB — returns a placeholder ``'projection'`` outcome.

    T-D.7 + T-D.8 + T-D.9 will implement:
      * Pass 1 — classify from persisted JSON only (no Schwab API call).
      * Pass 2 — when Pass 1 returns ``_pass_2_required=True``, invoke
        ``get_account_orders_audited(...)`` (T-D.6.1) + re-classify
        with the fetched payload.
      * Tier-1 dispatch — call PUBLIC ``apply_tier1_correction(...)``
        (C.C; own-tx).
      * Tier-2 dispatch — call PUBLIC ``stamp_pending_ambiguity(...)``
        (C.C; own-tx).
      * Idempotency — terminal-state discrepancies return early as
        ``'skipped_already_resolved'``.

    At T-D.6, this function returns an ``outcome='projection'`` record
    so the iteration shell + CLI rendering + summary aggregation can be
    exercised by tests + by operator dry-run preview before the dispatch
    logic lands.
    """
    return BackfillOutcome(
        discrepancy_id=int(disc.discrepancy_id or 0),
        ticker=disc.ticker,
        discrepancy_type=disc.discrepancy_type,
        tier=None,
        outcome="projection",
        reason="T-D.6 scaffold: per-discrepancy classification deferred to T-D.7+",
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

    discrepancies = _iter_unresolved_discrepancies(
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
        # Counter wiring — only ``projection`` placeholder fires at T-D.6
        # (no journal mutation; no tier1/tier2/error category yet). The
        # real counter dispatch lands at T-D.7+ once outcome categories
        # are populated.
        if outcome.outcome == "tier1_applied":
            summary.tier1_applied += 1
        elif outcome.outcome == "tier2_stamped":
            summary.tier2_stamped += 1
        elif outcome.outcome == "pass_2_failed":
            summary.pass_2_failed += 1
        elif outcome.outcome == "skipped_already_resolved":
            summary.skipped_already_resolved += 1
        elif outcome.outcome == "skipped_pass_2_failed":
            summary.skipped_pass_2_failed += 1
        elif outcome.outcome == "errored":
            summary.tier_errored += 1
        # ``projection`` is the T-D.6 scaffold placeholder — no counter.

    return summary


# ============================================================================
# CLI rendering helpers (consumed by `swing journal reconcile-backfill`)
# ============================================================================


def format_projection_table_header() -> str:
    """Header line for the dry-run projection table emitted by the CLI."""
    return (
        f"{'ID':>5} {'Ticker':<8} {'Type':<24} "
        f"{'Tier':<6} {'Outcome':<24} Reason"
    )


def format_projection_row(outcome: BackfillOutcome) -> str:
    """Single-row formatter for the dry-run projection table."""
    tier_str = "-" if outcome.tier is None else str(outcome.tier)
    return (
        f"{outcome.discrepancy_id:>5} "
        f"{(outcome.ticker or '-'):<8} "
        f"{outcome.discrepancy_type:<24} "
        f"{tier_str:<6} {outcome.outcome:<24} "
        f"{outcome.reason or ''}"
    )


def format_summary_block(summary: BackfillSummary) -> str:
    """Multi-line summary block printed at end of CLI invocation."""
    return (
        "\nBackfill summary:\n"
        f"  tier1_applied:           {summary.tier1_applied}\n"
        f"  tier2_stamped:           {summary.tier2_stamped}\n"
        f"  tier_errored:            {summary.tier_errored}\n"
        f"  pass_2_failed:           {summary.pass_2_failed}\n"
        f"  skipped_already_resolved:{summary.skipped_already_resolved:>4}\n"
        f"  skipped_pass_2_failed:   {summary.skipped_pass_2_failed}\n"
        f"  total iterated:          {len(summary.per_discrepancy_outcomes)}"
    )
