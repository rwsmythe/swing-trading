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
from datetime import UTC, datetime
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
        match_strategy="delimiter_aware",
        state_filter="state IN ('closed','reviewed')",
        join_keys="hypothesis_label = ? (via list_closed_trades_for_cohort)",
        operator_db_count=None,
        disposition="LIVE",
        notes=(
            "Pre-T-T4.SB.2: WIRING DEFECT (exact-equality silently dropped"
            " suffix-bearing labels). T-T4.SB.2 Sub-tasks 2B + 2C: card now"
            " consumes the 3-rule delimiter-aware SQL helper transitively"
            " via list_closed_trades_for_cohort -> list_trades_for_cohort."
            " See tests/metrics/test_hypothesis_progress_card_suffix_labels.py."
        ),
    ),
    SurfaceAuditRow(
        surface_name="CLI compute_hypothesis_progress_breakdown",
        file_path="swing/journal/stats.py:325",
        match_strategy="delimiter_aware",
        state_filter="state IN ('closed','reviewed')",
        join_keys="_label_matches_hypothesis (delegates to label_match helper)",
        operator_db_count=None,
        disposition="LIVE",
        notes=(
            "Pre-T-T4.SB.2: prefix_match (bare-startswith) -- accepted"
            " bare-prefix extensions like 'Sub-A+ VCP-not-formedness'."
            " T-T4.SB.2 Sub-task 2A: _label_matches_hypothesis pivots to"
            " the shared 3-rule delimiter-aware helper at"
            " swing.metrics.label_match.label_matches_hypothesis."
        ),
    ),
    SurfaceAuditRow(
        surface_name="list_trades_for_cohort",
        file_path="swing/metrics/cohort.py:40",
        match_strategy="delimiter_aware",
        state_filter="(via state_filter param)",
        join_keys="label_matches_hypothesis_sql 3-predicate fragment",
        operator_db_count=None,
        disposition="LIVE",
        notes=(
            "Pre-T-T4.SB.2: WIRING DEFECT (exact-equality SQL)."
            " T-T4.SB.2 Sub-task 2B: SQL switched to the shared 3-predicate"
            " OR-joined fragment from swing.metrics.label_match."
            " Wildcard chars (% / _) in registered names are escaped via"
            " ESCAPE '\\\\' clause + sql_escape_wildcard helper."
        ),
    ),
    SurfaceAuditRow(
        surface_name="count_per_cohort",
        file_path="swing/metrics/cohort.py:99",
        match_strategy="delimiter_aware",
        state_filter="state IN closed-states",
        join_keys=(
            "per-registered-name 3-predicate OR fragment + orphan-fallback"
            " second query"
        ),
        operator_db_count=None,
        disposition="LIVE",
        notes=(
            "Pre-T-T4.SB.2: WIRING DEFECT (suffix-bearing labels surfaced"
            " as orphan cohorts instead of aggregating to the registered"
            " name). T-T4.SB.2 Sub-task 2C: rewrites to per-cohort"
            " delimiter-aware count + orphan-fallback second query that"
            " preserves orphan-label rows for cohorts NOT matching any"
            " registered hypothesis (Expansion #10 sub-discipline (e)"
            " ORPHAN-PRESERVATION LOCK)."
        ),
    ),
    # T-T4.SB.1 ships the audit; T-T4.SB.2 flips the 3 WIRING DEFECT entries
    # to LIVE post-fix. Future broader-audit FALSE-ZERO RISK entries
    # (e.g., outcome distribution V1 STUB rows) are added by future
    # dispatches per V1 simplification banking discipline.
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
    iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
