"""Item 7 metrics-wiring audit (Phase 13 T4.SB T-T4.SB.1 Phase 1).

Enumerates every metric surface in ``swing/metrics/``,
``swing/web/view_models/metrics/``, ``swing/journal/stats.py``, and dashboard
cards. For each, identifies the match strategy + state filter + join keys +
current operator-DB count + audit disposition (LIVE / V1 STUB / V1
PLACEHOLDER / WIRING DEFECT / FALSE-ZERO RISK).

V1 ships a hand-maintained registry (``_KNOWN_SURFACES``) per the cumulative
``_KNOWN_SURFACES`` simplification banking lesson; T-T4.SB.2 broader audit
extends the registry per audit findings. V2 candidate: codegen the registry
from a decorator-marked surface registry.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SurfaceAuditRow:
    """One row in the metrics-wiring audit registry.

    Attributes:
        surface_name: human-readable surface label (e.g.,
            ``"Dashboard hyp-progress card"``).
        file_path: ``swing/.../file.py:line`` -- entry-point for the surface's
            primary helper.
        match_strategy: one of ``{"exact_equality", "prefix_match",
            "delimiter_aware", "sql_like", "unknown"}``.
        state_filter: human-readable description of the state filter applied
            (or ``"n/a"`` when the surface does not filter by state).
        join_keys: how the surface joins to its source table (e.g.,
            ``"hypothesis_label = ?"`` or ``"GROUP BY hypothesis_label"`` or
            ``"n/a"``).
        operator_db_count: per-surface operator-DB count when known; ``None``
            in V1 (audit_surface_match_strategy is a V1 stub).
        disposition: one of ``{"LIVE", "V1 STUB", "V1 PLACEHOLDER",
            "WIRING DEFECT", "FALSE-ZERO RISK"}``.
        notes: short prose describing the audit finding + planned remediation.
    """

    surface_name: str
    file_path: str
    match_strategy: str
    state_filter: str
    join_keys: str
    operator_db_count: int | None
    disposition: str
    notes: str


_KNOWN_SURFACES: tuple[SurfaceAuditRow, ...] = (
    SurfaceAuditRow(
        surface_name="Dashboard hyp-progress card",
        file_path="swing/web/view_models/metrics/hypothesis_progress_card.py:404",
        match_strategy="exact_equality",
        state_filter="state IN ('closed','reviewed')",
        join_keys="hypothesis_label = ?",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes="Suffix-bearing labels exact-mismatch; Option 7C fix in T-T4.SB.2.",
    ),
    SurfaceAuditRow(
        surface_name="CLI compute_hypothesis_progress_breakdown",
        file_path="swing/journal/stats.py:325",
        match_strategy="prefix_match",
        state_filter="state IN ('closed','reviewed')",
        join_keys="_label_matches_hypothesis",
        operator_db_count=None,
        disposition="LIVE",
        notes=(
            "Existing bare-startswith helper; widens to 3-rule delimiter-aware"
            " in T-T4.SB.2."
        ),
    ),
    SurfaceAuditRow(
        surface_name="list_trades_for_cohort",
        file_path="swing/metrics/cohort.py:40",
        match_strategy="exact_equality",
        state_filter="(via state_filter param)",
        join_keys="hypothesis_label = ?",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes="Pivots to delimiter-aware SQL helper in T-T4.SB.2.",
    ),
    SurfaceAuditRow(
        surface_name="count_per_cohort",
        file_path="swing/metrics/cohort.py:99",
        match_strategy="exact_equality",
        state_filter="state IN closed-states",
        join_keys="GROUP BY hypothesis_label",
        operator_db_count=None,
        disposition="WIRING DEFECT",
        notes=(
            "Suffix-bearing labels create orphan cohorts; delimiter-aware"
            " GROUP BY in T-T4.SB.2 preserves orphan fallback."
        ),
    ),
    # T-T4.SB.1 ships the audit; T-T4.SB.2 extends with audit-derived WIRING
    # DEFECT entries (e.g., outcome distribution V1 STUB rows).
)


def enumerate_metric_surfaces() -> tuple[SurfaceAuditRow, ...]:
    """Return the BASE audit registry.

    Per-row ``operator_db_count`` is ``None`` unless
    ``audit_surface_match_strategy`` is invoked with a conn (V1 stub).

    V1 simplification acknowledged: this list is hand-maintained; future
    metric-tile surfaces require a manual append. V2 candidate: codegen the
    registry from a decorator-marked surface registry.
    """
    return _KNOWN_SURFACES


def audit_surface_match_strategy(
    conn: sqlite3.Connection, row: SurfaceAuditRow,
) -> SurfaceAuditRow:
    """Populate ``operator_db_count`` for the given row.

    **V1 stub**: returns the row as-is. T-T4.SB.2 broader audit may
    implement per-surface discriminating queries against ``conn`` to
    populate the count column. The conn parameter is preserved so the V2
    signature does not break.
    """
    # V1 stub: per-surface discriminating queries are V2 (banked).
    _ = conn  # explicitly unused under V1
    return row


def write_metrics_wiring_audit_markdown(
    conn: sqlite3.Connection, output_path: Path,
) -> Path:
    """Write the audit registry to ``output_path`` as a markdown report.

    Renders a per-surface table + Notes section. ASCII-only output per the
    Windows cp1252 stdout safety lesson (tests verify cp1252 encodability).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        audit_surface_match_strategy(conn, r) for r in enumerate_metric_surfaces()
    ]
    lines: list[str] = [
        "# Metrics Wiring Audit",
        "",
        f"**Generated:** {iso}",
        f"**Surfaces audited:** {len(rows)}",
        "",
        "## Per-surface table",
        "",
        (
            "| Surface | File:line | Match strategy | State filter | Join keys |"
            " Operator DB count | Disposition |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        count = r.operator_db_count if r.operator_db_count is not None else "n/a"
        lines.append(
            f"| {r.surface_name} | {r.file_path} | {r.match_strategy} | "
            f"{r.state_filter} | {r.join_keys} | {count} | {r.disposition} |"
        )
    lines.extend(["", "## Notes per surface", ""])
    for r in rows:
        lines.extend([f"### {r.surface_name}", "", r.notes, ""])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
