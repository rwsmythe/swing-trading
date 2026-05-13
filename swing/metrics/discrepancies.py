"""Reconciliation discrepancy badge count (plan §A.18 + §I.5).

Phase 10 surfaces a "N unresolved material discrepancies" badge in
``base.html.j2`` whenever the count is > 0. This helper produces the count
read-only; the banner block ships in Sub-bundle E T-E.3 + the field
populates from Sub-bundle A's :class:`BaseLayoutVM` onward.

Per plan §A.18 Codex R2 Major #6 restructure: the helper lands in
Sub-bundle A so subsequent sub-bundles' metrics VMs populate the field
from the start, eliminating per-VM retrofit in Sub-bundle E. Only the
existing 6 base-layout VMs (DashboardVM/PipelineVM/JournalVM/WatchlistVM/
ConfigVM/PageErrorVM) get the field added in E.

V1 SCOPE LIMITATION: helper counts discrepancies JOINed on
``trades.id`` — orphan-emit discrepancies (sector_tamper /
equity_delta / cash_movement_mismatch without a trade attribution) are
EXCLUDED from the count since
:func:`swing.data.repos.reconciliation.list_unresolved_material_for_active_trades`
and
:func:`swing.data.repos.reconciliation.list_unresolved_material_for_closed_trades`
JOIN on the trade row. V2 candidate (banked at return report §7): include
orphan-emit discrepancies via a separate sub-query.
"""

from __future__ import annotations

import sqlite3

from swing.data.repos.reconciliation import (
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
