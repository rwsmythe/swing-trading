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
    _TRADE_SELECT_COLS,
    _row_to_trade,
)
from swing.trades.entry import canonicalize_hypothesis_label

# Per spec §A.16 + plan §I.14: cohort listing for the dashboard.
_HYPOTHESIS_REGISTRY_NAMES_SQL = (
    "SELECT name FROM hypothesis_registry ORDER BY id"
)

_CLOSED_TRADE_COUNT_PER_LABEL_SQL = (
    "SELECT hypothesis_label, COUNT(*) "
    "FROM trades "
    f"WHERE state IN {_CLOSED_STATES_SQL} "
    "  AND hypothesis_label IS NOT NULL "
    "GROUP BY hypothesis_label"
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
    """
    canonical = (
        canonicalize_hypothesis_label(hypothesis_label)
        if hypothesis_label is not None
        else None
    )
    where_clauses: list[str] = []
    params: list[object] = []
    if canonical is not None:
        where_clauses.append("hypothesis_label = ?")
        params.append(canonical)
    if state_filter:
        placeholders = ",".join("?" for _ in state_filter)
        where_clauses.append(f"state IN ({placeholders})")
        params.extend(state_filter)

    sql = f"SELECT {_TRADE_SELECT_COLS} FROM trades"  # noqa: S608
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
    rows.

    Per plan §A.16 empty-cohort discipline: cohorts with zero closed trades
    are INCLUDED with value 0 (NOT omitted). This is what the dashboard
    needs to render every cohort tab even at our current n<5 state.
    """
    cohort_counts: dict[str, int] = {}
    for (name,) in conn.execute(_HYPOTHESIS_REGISTRY_NAMES_SQL):
        cohort_counts[name] = 0

    for label, count in conn.execute(_CLOSED_TRADE_COUNT_PER_LABEL_SQL):
        if label in cohort_counts:
            cohort_counts[label] = int(count)
        else:
            # Label exists on trades but not in registry — defensive surface
            # the orphan-labeled cohort so the dashboard can render an
            # "(unregistered cohort)" placeholder. Include in returned dict.
            cohort_counts[label] = int(count)
    return cohort_counts
