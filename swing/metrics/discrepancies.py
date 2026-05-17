"""Reconciliation discrepancy badge count + per-trade helper (plan §A.18 + §I.5).

Phase 10 surfaces a "N unresolved material discrepancies" badge in
``base.html.j2`` whenever the count is > 0. The Sub-bundle E T-E.6
elective per-trade indicator on the trade-detail page reuses the same
material+unresolved predicate scoped to a single trade.

Per plan §A.18 Codex R2 Major #6 restructure: ``count_unresolved_material``
lands in Sub-bundle A so subsequent sub-bundles' metrics VMs populate the
field from the start; only the existing 6 base-layout VMs (Dashboard /
Pipeline / Journal / Watchlist / Config / PageError) get the field added
in E.

V1 SCOPE LIMITATION: both helpers exclude orphan-emit discrepancies
(sector_tamper / equity_delta / cash_movement_mismatch without a trade
attribution) since
:func:`swing.data.repos.reconciliation.list_unresolved_material_for_active_trades`
and the closed-trade companion JOIN on the trade row.
:func:`list_unresolved_material_for_trade` (T-E.6) ALSO excludes orphans
by construction (``WHERE trade_id = ?``); orphan attribution is a V2
candidate banked at return report §7.
"""

from __future__ import annotations

import sqlite3

from swing.data.models import ReconciliationDiscrepancy
from swing.data.repos.reconciliation import (
    _DISCREPANCY_SELECT_COLUMNS,
    _row_to_discrepancy,
    list_unresolved_material_for_active_trades,
    list_unresolved_material_for_closed_trades,
)


def count_unresolved_material(conn: sqlite3.Connection) -> int:
    """Return the sum of unresolved-material discrepancies attributed to
    active + closed trades.

    Read-only; opens no transaction; thin wrapper over the Phase 9
    Sub-bundle B canonical query helpers per plan §A.18 + spec §5.1
    CANONICAL #1+#2.
    """
    active = list_unresolved_material_for_active_trades(conn)
    closed = list_unresolved_material_for_closed_trades(conn)
    return len(active) + len(closed)


def list_unresolved_material_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> list[ReconciliationDiscrepancy]:
    """Per-trade unresolved-material discrepancies (T-E.6 elective).

    Returns discrepancies WHERE ``trade_id = ? AND material_to_review = 1
    AND resolution IN ('unresolved', 'pending_ambiguity_resolution')``.
    Orphan-emit discrepancies (``trade_id IS NULL``) are EXCLUDED by
    construction.

    Phase 12 Sub-sub-bundle C.D T-D.10: predicate widens to surface
    tier-2 ambiguity-pending discrepancies on /trades/{id} alongside
    true unresolved rows. Auto-corrected
    (``auto_corrected_from_schwab``) + operator-resolved
    (``operator_resolved_ambiguity``) + operator_overridden /
    acknowledged_immaterial / journal_corrected remain EXCLUDED (no
    operator action remaining).

    Read-only; opens no transaction. Mirrors the Phase 9 Sub-bundle B
    canonical query ordering (created_at DESC, discrepancy_id DESC) so
    the indicator surfaces newest-first.
    """
    rows = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} "
        "FROM reconciliation_discrepancies "
        "WHERE trade_id = ? "
        "  AND material_to_review = 1 "
        "  AND resolution IN ('unresolved', 'pending_ambiguity_resolution') "
        "ORDER BY created_at DESC, discrepancy_id DESC",
        (int(trade_id),),
    ).fetchall()
    return [_row_to_discrepancy(r) for r in rows]
