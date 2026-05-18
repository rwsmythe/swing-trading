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
from typing import Literal

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


def list_pending_ambiguities_in_banner_set(
    conn: sqlite3.Connection,
) -> list[ReconciliationDiscrepancy]:
    """Return banner-set discrepancies whose resolution is
    ``pending_ambiguity_resolution``, oldest-first.

    Phase 12.5 #2 T-2.9: powers the banner-link target on
    ``base.html.j2``. Mirrors ``count_unresolved_material``'s
    trade-set semantics (active + closed trades) per plan §A
    LOCK — same UNION used by the banner count helper — then
    narrows to the tier-2 ambiguity-pending subset so the
    "Resolve via web" link points at the oldest still-pending
    row.

    Sort key per LOCK §1.2 #6: ``discrepancy_id ASC`` (deterministic
    oldest-first). The underlying canonical helpers order by
    ``created_at DESC, discrepancy_id DESC``; we resort here so the
    caller may take ``[0]`` for the first-pending without relying on
    DB-side ordering semantics.

    Orphan-emit discrepancies (``trade_id IS NULL``) are EXCLUDED by
    construction — the canonical helpers JOIN on the ``trades`` row.

    Read-only; opens no transaction.
    """
    active = list_unresolved_material_for_active_trades(conn)
    closed = list_unresolved_material_for_closed_trades(conn)
    union = list(active) + list(closed)
    pending = [
        d for d in union if d.resolution == "pending_ambiguity_resolution"
    ]
    return sorted(pending, key=lambda d: d.discrepancy_id)


def fetch_first_pending_ambiguity_resolve_link_path(
    conn: sqlite3.Connection,
) -> str | None:
    """Return the resolve-form path for the OLDEST pending-ambiguity
    discrepancy in the banner set, or None when the banner set carries
    no pending-ambiguity rows.

    Phase 12.5 #2 T-2.9: banner-link target consumed by every
    base-layout VM populator across the web + metrics surfaces.

    Returns ``f"/reconcile/discrepancy/{first.discrepancy_id}/resolve"``
    when :func:`list_pending_ambiguities_in_banner_set` is non-empty;
    None otherwise.

    Read-only; opens no transaction.
    """
    pending = list_pending_ambiguities_in_banner_set(conn)
    if not pending:
        return None
    return f"/reconcile/discrepancy/{pending[0].discrepancy_id}/resolve"


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


def count_recent_multi_leg_auto_corrections(
    conn: sqlite3.Connection,
    *,
    window: Literal["most_recent_run"] = "most_recent_run",
) -> int:
    """Count distinct discrepancies in the latest completed reconciliation_run
    that were resolved via multi-leg tier-1 auto-redirect.

    Per spec §8.2 + plan §F invariant F18 (COUNT(DISTINCT) LOGICAL semantic):
    a single multi-leg auto-redirect emits N+1 correction rows (1 anchor
    deletion + N partial inserts per
    ``_handle_split_into_partials``), all carrying the same
    ``discrepancy_id``. A naive ``COUNT(*)`` on
    ``reconciliation_corrections`` would inflate by N+1; we count
    ``COUNT(DISTINCT rd.discrepancy_id)`` to surface LOGICAL multi-leg
    auto-redirects (one count per discrepancy).

    The ``window`` parameter is locked to ``Literal['most_recent_run']``
    in V1 per spec §8.4 (banner-clears semantic — the banner advisory
    surfaces what happened on the latest run and clears when the next
    run lands without any multi-leg redirects). V2 widens to additional
    values (banked spec §14 + plan §Z #1+#2 — e.g.
    ``'past_n_runs'`` / ``'past_n_days'`` for trend charts). The current
    implementation ignores the parameter beyond type-narrowing.

    Phase 10 lesson #26 (deterministic-tiebreaker): the latest-completed-run
    SELECT uses ``ORDER BY finished_ts DESC, run_id DESC`` so two runs
    with identical ``finished_ts`` resolve deterministically to the
    higher ``run_id``.

    Read-only; opens no transaction. Returns 0 when no completed runs
    exist or the latest completed run has zero multi-leg auto-redirects.
    """
    # Step 1: locate the latest completed reconciliation_run.
    row = conn.execute(
        "SELECT run_id FROM reconciliation_runs "
        "WHERE state = 'completed' "
        "ORDER BY finished_ts DESC, run_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return 0
    latest_run_id = row[0]
    # Step 2: COUNT(DISTINCT discrepancy_id) for that run where the
    # underlying discrepancy carries the multi-leg-auto-redirect sentinel.
    count_row = conn.execute(
        "SELECT COUNT(DISTINCT rd.discrepancy_id) "
        "FROM reconciliation_corrections rc "
        "JOIN reconciliation_discrepancies rd "
        "  ON rc.discrepancy_id = rd.discrepancy_id "
        "WHERE rc.reconciliation_run_id = ? "
        "  AND rd.resolved_by = ?",
        (latest_run_id, "auto_tier1_multi_leg"),
    ).fetchone()
    return int(count_row[0]) if count_row else 0
