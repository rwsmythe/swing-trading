"""Per-hypothesis-cohort filter + aggregation helper (plan §D Task A.4).

Provides the Phase 10 read-side cohort-grain interface consumed by
Sub-bundles B + C metric computations. The helpers are pure SELECTs —
classification (win/loss/scratch) happens at the per-trade level in
``swing/metrics/process.py`` (Sub-bundle B).

Label canonicalization is via the existing
:func:`swing.trades.entry.canonicalize_hypothesis_label` helper to match
the persistence-boundary form: trades store the canonical label, and
queries by ``hypothesis_label`` use the same canonical form.
"""

from __future__ import annotations

import sqlite3

from swing.data.models import Trade
from swing.data.repos.trades import (
    _CLOSED_STATES_SQL,
    _row_to_trade,
    _trade_select_cols,
)
from swing.metrics.label_match import label_matches_hypothesis_sql
from swing.trades.entry import canonicalize_hypothesis_label

# Per spec §A.16 + plan §I.14: cohort listing for the dashboard.
_HYPOTHESIS_REGISTRY_NAMES_SQL = (
    "SELECT name FROM hypothesis_registry ORDER BY id"
)

def list_trades_for_cohort(
    conn: sqlite3.Connection,
    *,
    hypothesis_label: str | None,
    state_filter: tuple[str, ...] | None = None,
) -> list[Trade]:
    """Return trades matching the cohort filter.

    Arguments:
        hypothesis_label: cohort name to filter on; ``None`` returns ALL
          trades (no cohort filter — the "all trades" view).
        state_filter: optional tuple of states to filter on (e.g.,
          ``('closed', 'reviewed')``). When ``None``, no state filter
          applied.

    Per plan §A.11.1: include ALL trades labeled with the cohort regardless
    of cohort status (active / paused / closed). Paused intervals do NOT
    cause exclusion (operator-intent-at-entry semantics).

    Phase 13 T-T4.SB.2 (Item 7 Option 7C LOCK): match contract widened from
    exact equality to 3-rule delimiter-aware (exact / space-delimited /
    semicolon-delimited) so per-trade-suffix labels like
    ``"Sub-A+ VCP-not-formed (watch); failed: proximity_20ma"`` are
    correctly attributed to the canonical cohort. See
    :func:`swing.metrics.label_match.label_matches_hypothesis_sql`.
    """
    canonical = (
        canonicalize_hypothesis_label(hypothesis_label)
        if hypothesis_label is not None
        else None
    )
    where_clauses: list[str] = []
    params: list[object] = []
    if canonical is not None:
        fragment, fragment_params = label_matches_hypothesis_sql(canonical)
        where_clauses.append(fragment)
        params.extend(fragment_params)
    if state_filter:
        placeholders = ",".join("?" for _ in state_filter)
        where_clauses.append(f"state IN ({placeholders})")
        params.extend(state_filter)

    cols = _trade_select_cols(conn)
    sql = f"SELECT {cols} FROM trades"  # noqa: S608
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY entry_date, ticker, id"

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_trade(r) for r in rows]


def list_closed_trades_for_cohort(
    conn: sqlite3.Connection, *, hypothesis_label: str | None,
) -> list[Trade]:
    """Return trades in 'closed' or 'reviewed' state for the cohort.

    Convenience wrapper over :func:`list_trades_for_cohort` with the
    closed-state tuple pre-filled.
    """
    return list_trades_for_cohort(
        conn,
        hypothesis_label=hypothesis_label,
        state_filter=("closed", "reviewed"),
    )


def count_per_cohort(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{cohort_name: closed_trade_count}`` for ALL ``hypothesis_registry``
    rows, aggregating per the 3-rule delimiter-aware match contract plus
    an orphan-preservation second query.

    Per plan §A.16 empty-cohort discipline: cohorts with zero closed trades
    are INCLUDED with value 0 (NOT omitted). This is what the dashboard
    needs to render every cohort tab even at our current n<5 state.

    Phase 13 T-T4.SB.2 (Item 7) widens the per-cohort count from exact
    equality GROUP BY to delimiter-aware match per registered hypothesis
    via :func:`swing.metrics.label_match.label_matches_hypothesis_sql`.
    A SECOND query (orphan-fallback) selects closed trades with non-NULL
    ``hypothesis_label`` that match NONE of the registered hypotheses --
    those labels surface as their own entries in the returned dict so
    operator can see an "(unregistered cohort)" placeholder. Closes
    Expansion #10 sub-discipline (e) ORPHAN-PRESERVATION-WHEN-REFACTORING
    LOCK.
    """
    cohort_counts: dict[str, int] = {}
    registered_names: list[str] = []
    for (name,) in conn.execute(_HYPOTHESIS_REGISTRY_NAMES_SQL):
        registered_names.append(name)
        cohort_counts[name] = 0

    # Per-cohort count via the shared SQL helper.
    for name in registered_names:
        fragment, params = label_matches_hypothesis_sql(name)
        sql = (
            "SELECT COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "  AND hypothesis_label IS NOT NULL "
            f"  AND {fragment}"
        )  # noqa: S608
        (count,) = conn.execute(sql, params).fetchone()
        cohort_counts[name] = int(count)

    # Orphan-label preservation: a SECOND query selects closed trades with
    # ``hypothesis_label`` NOT NULL that match NONE of the registered
    # hypotheses (Codex R4 M#1 LOCK; Expansion #10 sub-discipline (e)).
    if registered_names:
        not_clauses: list[str] = []
        not_params: list[object] = []
        for name in registered_names:
            fragment, params = label_matches_hypothesis_sql(name)
            not_clauses.append(f"NOT {fragment}")
            not_params.extend(params)
        orphan_sql = (
            "SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "  AND hypothesis_label IS NOT NULL "
            f"  AND {' AND '.join(not_clauses)} "
            "GROUP BY hypothesis_label"
        )  # noqa: S608
        for label, count in conn.execute(orphan_sql, not_params):
            cohort_counts[label] = int(count)
    else:
        # Empty-registry defensive branch (production seeds registry rows
        # via migration 0008; this covers test DBs / future startup
        # transient states). EVERY non-NULL label is an orphan; surface
        # raw labels per orphan contract.
        orphan_sql_empty = (
            "SELECT hypothesis_label, COUNT(*) FROM trades "
            f"WHERE state IN {_CLOSED_STATES_SQL} "
            "  AND hypothesis_label IS NOT NULL "
            "GROUP BY hypothesis_label"
        )  # noqa: S608
        for label, count in conn.execute(orphan_sql_empty):
            cohort_counts[label] = int(count)
    return cohort_counts


# ---------------------------------------------------------------------------
# T-C.5 elective — per-cohort discrepancy filter
# ---------------------------------------------------------------------------

def filter_trades_without_unresolved_material_discrepancies(
    conn: sqlite3.Connection, trades: list[Trade],
) -> list[Trade]:
    """Return the subset of trades that have ZERO unresolved material
    reconciliation discrepancies.

    Per electives amendment §2 Task C.5 acceptance (with the helper's
    intent — the amendment text uses "resolution IS NULL" loosely; the
    Phase 9 schema actually stores ``resolution`` as NOT NULL with the
    sentinel value ``'unresolved'`` as the default):

    - INCLUDE trades with no discrepancy rows.
    - INCLUDE trades whose discrepancies are ALL resolved
      (``resolution != 'unresolved'`` — i.e. one of
      ``'journal_corrected'`` / ``'source_treated_canonical'`` /
      ``'manual_override'`` / ``'acknowledged_immaterial'``).
    - INCLUDE trades whose discrepancies are non-material
      (``material_to_review = 0``).
    - EXCLUDE trades with at least one discrepancy row where
      ``material_to_review = 1 AND resolution = 'unresolved'``.

    Mirrors :func:`swing.data.repos.reconciliation.list_unresolved_material_for_active_trades`
    semantics so the global banner count + this per-cohort filter agree
    on which discrepancies count as "unresolved + material".

    Single-query: SELECT DISTINCT trade_id FROM reconciliation_discrepancies
    WHERE material_to_review=1 AND resolution='unresolved' AND trade_id
    IS NOT NULL; exclude those ``trade_id``s from the input list.

    Orphan-emit discrepancies (``trade_id IS NULL`` — sector_tamper /
    equity_delta / cash_movement_mismatch without a trade attribution per
    Phase 9 Sub-bundle B) do NOT affect this filter (they cannot exclude
    a specific trade). Codex R1 Minor #1 follow-up: they are ALSO excluded
    from the global ``unresolved_material_discrepancies_count`` banner
    today — :func:`swing.metrics.discrepancies.count_unresolved_material`
    JOINs on ``trades.id`` per the V1 SCOPE LIMITATION documented in
    ``swing/metrics/discrepancies.py`` (banked V2 candidate: include
    orphan discrepancies via a separate sub-query). The filter helper's
    behavior here remains correct in isolation (filtering trades), and
    no banner/filter divergence exists at V1 because both consume the
    "trade-attributed only" subset.
    """
    if not trades:
        return list(trades)
    rows = conn.execute(
        "SELECT DISTINCT trade_id FROM reconciliation_discrepancies "
        "WHERE material_to_review = 1 "
        "  AND resolution = 'unresolved' "
        "  AND trade_id IS NOT NULL",
    ).fetchall()
    excluded_ids = {int(r[0]) for r in rows}
    return [t for t in trades if t.id not in excluded_ids]
