"""V2.G3 one-time backfill of trades.sector + trades.industry.

See spec at docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-
wiring-design.md section 4 + plan at docs/superpowers/plans/2026-05-28-
phase14-sub-bundle-1-data-wiring-plan.md section G.T-1.2.

Strict all-or-nothing semantic (R2.M3 LOCK):
- SELECT: TRIM(sector)='' AND TRIM(industry)=''
- UPDATE: requires both replacements non-empty
- SKIP_PARTIAL_EMPTY: rows with one column empty (not both)
- SKIP_NO_CANDIDATES_ROW: rows with no qualifying candidates row

Restore-SQL artifact (R1.M3 LOCK):
- Emitted at <output-dir>/backfill-trades-sector-industry-restore-<ISO>.sql
- Contains per-affected-row UPDATE statements with OLD values
- Operator can re-apply via `sqlite3 swing.db < restore.sql`
- Emitted in BOTH dry-run AND apply paths (defense-in-depth against
  crash post-UPDATE).

Concurrency discipline (Codex round 1 Major #1):
- Apply path wraps the final SELECT + restore-SQL emit + UPDATE in a
  single ``BEGIN IMMEDIATE`` write transaction so the row set seen at
  emit-time matches the row set actually UPDATEd. Without the lock, a
  concurrent writer could fill an AND-empty row between SELECT and
  UPDATE; the UPDATE would correctly no-op (the WHERE clause guards
  per ``_apply_updates``), but the restore-SQL would still contain an
  UPDATE-to-empty for that row -- the operator applying restore later
  would clobber the concurrent writer's valid data.
- Dry-run path is preview-only; no lock required.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.candidates import (
    CandidateSectorIndustryRecord,
    get_latest_sector_industry_per_ticker,
)

_DEFAULT_ACTIVE_STATES: tuple[str, ...] = (
    "entered", "managing", "partial_exited",
)


@dataclass(frozen=True)
class BackfillRow:
    """One row in the dry-run table emit.

    source_candidate_id + source_evaluation_run_id are populated for
    UPDATE rows (Codex R1.M#6 LOCK -- provenance auditability per
    spec section 4.3); None for SKIP rows where no candidates row
    qualified.
    """
    trade_id: int
    ticker: str
    current_sector: str
    current_industry: str
    proposed_sector: str
    proposed_industry: str
    action: str  # 'UPDATE' | 'SKIP_NO_CANDIDATES_ROW' | 'SKIP_PARTIAL_EMPTY'
    source_candidate_id: int | None
    source_evaluation_run_id: int | None


@dataclass(frozen=True)
class BackfillSummary:
    """Top-level result returned to the CLI."""
    rows: tuple[BackfillRow, ...]
    update_count: int
    skip_no_candidates_count: int
    skip_partial_empty_count: int
    restore_sql_path: Path
    report_lines: tuple[str, ...]
    applied: bool


def run_backfill(
    *,
    db_path: Path,
    apply: bool,
    output_dir: Path,
    allowlist: tuple[str, ...] | None,
    include_closed: bool,
) -> BackfillSummary:
    """Run the backfill in dry-run or apply mode.

    Per CLAUDE.md gotcha #27 (silent-skip-without-audit): emits operator-
    friendly counts for every per-action skip path.
    """
    conn = connect(db_path)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        restore_path = (
            output_dir
            / f"backfill-trades-sector-industry-restore-{iso}.sql"
        )
        if apply:
            # Per Codex round 1 Major #1: serialize the SELECT + restore-SQL
            # emit + UPDATE against concurrent writers via BEGIN IMMEDIATE.
            # Without the lock, a concurrent writer could fill an AND-empty
            # row between SELECT and UPDATE; the UPDATE would correctly
            # no-op via the WHERE-clause guard at ``_apply_updates``, but
            # the restore-SQL would still contain an UPDATE-to-empty
            # statement for that row -- applying restore later would
            # clobber the concurrent writer's valid data. Re-selecting
            # under the write lock ensures the restore artifact and the
            # actual UPDATE set are the same row set.
            conn.execute("BEGIN IMMEDIATE")
            try:
                rows = _gather_backfill_rows(
                    conn,
                    include_closed=include_closed,
                    allowlist=allowlist,
                )
                update_rows = [r for r in rows if r.action == "UPDATE"]
                # Per R1.M3 LOCK: emit restore-SQL BEFORE UPDATE fires
                # (defense-in-depth against crash mid-UPDATE). Now also
                # TOCTOU-safe per the BEGIN IMMEDIATE lock above.
                _emit_restore_sql(restore_path, update_rows)
                _apply_updates(conn, update_rows)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            applied_flag = True
        else:
            # Dry-run path: preview-only; no lock required (no writes fire).
            rows = _gather_backfill_rows(
                conn,
                include_closed=include_closed,
                allowlist=allowlist,
            )
            # Per R1.M3 LOCK: emit restore-SQL on dry-run too so operator
            # can review the artifact before --apply (defense-in-depth).
            _emit_restore_sql(
                restore_path, [r for r in rows if r.action == "UPDATE"],
            )
            applied_flag = False
        update_count = sum(1 for r in rows if r.action == "UPDATE")
        skip_no_cand = sum(
            1 for r in rows if r.action == "SKIP_NO_CANDIDATES_ROW"
        )
        skip_partial = sum(
            1 for r in rows if r.action == "SKIP_PARTIAL_EMPTY"
        )
        report = _format_report(
            rows=rows, update_count=update_count,
            skip_no_cand=skip_no_cand, skip_partial=skip_partial,
            apply=apply,
        )
        return BackfillSummary(
            rows=tuple(rows),
            update_count=update_count,
            skip_no_candidates_count=skip_no_cand,
            skip_partial_empty_count=skip_partial,
            restore_sql_path=restore_path,
            report_lines=tuple(report),
            applied=applied_flag,
        )
    finally:
        conn.close()


def _gather_backfill_rows(
    conn: sqlite3.Connection,
    *,
    include_closed: bool,
    allowlist: tuple[str, ...] | None,
) -> list[BackfillRow]:
    """Gather + filter + replacement-lookup + row-assembly pipeline.

    Extracted so the apply-path can re-run it under BEGIN IMMEDIATE
    (Codex round 1 Major #1) and the dry-run path can run it without
    a lock with shared code.
    """
    and_empty_rows = _select_and_empty_trade_rows(
        conn, include_closed=include_closed,
    )
    partial_rows = _select_partial_empty_trade_rows(
        conn, include_closed=include_closed,
    )
    if allowlist is not None:
        and_empty_rows = [r for r in and_empty_rows if r[1] in allowlist]
        partial_rows = [r for r in partial_rows if r[1] in allowlist]
    candidate_tickers = sorted({r[1] for r in and_empty_rows})
    replacements = get_latest_sector_industry_per_ticker(
        conn, candidate_tickers,
    )
    return _build_backfill_rows(
        and_empty_rows=and_empty_rows,
        partial_rows=partial_rows,
        replacements=replacements,
    )


def _select_and_empty_trade_rows(
    conn: sqlite3.Connection, *, include_closed: bool,
) -> list[tuple[int, str, str, str]]:
    """SELECT (id, ticker, sector, industry) where BOTH empty + state in
    allowlist. Active-state allowlist applied unless --include-closed."""
    sql = (
        "SELECT id, ticker, sector, industry FROM trades "
        "WHERE TRIM(sector) = '' AND TRIM(industry) = ''"
    )
    params: list[object] = []
    if not include_closed:
        placeholders = ",".join("?" * len(_DEFAULT_ACTIVE_STATES))
        sql += f" AND state IN ({placeholders})"
        params.extend(_DEFAULT_ACTIVE_STATES)
    return [(r[0], r[1], r[2], r[3]) for r in conn.execute(sql, params)]


def _select_partial_empty_trade_rows(
    conn: sqlite3.Connection, *, include_closed: bool,
) -> list[tuple[int, str, str, str]]:
    """SELECT (id, ticker, sector, industry) for partial-empty rows
    (one of sector/industry empty; not both)."""
    sql = (
        "SELECT id, ticker, sector, industry FROM trades "
        "WHERE (TRIM(sector) = '' OR TRIM(industry) = '') "
        "AND NOT (TRIM(sector) = '' AND TRIM(industry) = '')"
    )
    params: list[object] = []
    if not include_closed:
        placeholders = ",".join("?" * len(_DEFAULT_ACTIVE_STATES))
        sql += f" AND state IN ({placeholders})"
        params.extend(_DEFAULT_ACTIVE_STATES)
    return [(r[0], r[1], r[2], r[3]) for r in conn.execute(sql, params)]


def _build_backfill_rows(
    *,
    and_empty_rows: Iterable[tuple[int, str, str, str]],
    partial_rows: Iterable[tuple[int, str, str, str]],
    replacements: dict[str, CandidateSectorIndustryRecord],
) -> list[BackfillRow]:
    """Assemble per-(trade_id, action) rows for the table emit.

    Provenance (source_candidate_id + source_evaluation_run_id) is
    carried through from the helper's CandidateSectorIndustryRecord
    so the dry-run table can audit which candidates row supplied each
    backfill (Codex R1.M#6 LOCK).
    """
    rows: list[BackfillRow] = []
    no_match_sentinel = CandidateSectorIndustryRecord(
        sector="", industry="",
        candidate_id=None, evaluation_run_id=None,
    )
    for tid, ticker, cur_sector, cur_industry in and_empty_rows:
        rec = replacements.get(ticker, no_match_sentinel)
        action = (
            "UPDATE" if rec.sector and rec.industry
            else "SKIP_NO_CANDIDATES_ROW"
        )
        rows.append(BackfillRow(
            trade_id=tid, ticker=ticker,
            current_sector=cur_sector, current_industry=cur_industry,
            proposed_sector=rec.sector, proposed_industry=rec.industry,
            action=action,
            source_candidate_id=rec.candidate_id,
            source_evaluation_run_id=rec.evaluation_run_id,
        ))
    for tid, ticker, cur_sector, cur_industry in partial_rows:
        rows.append(BackfillRow(
            trade_id=tid, ticker=ticker,
            current_sector=cur_sector, current_industry=cur_industry,
            proposed_sector="", proposed_industry="",
            action="SKIP_PARTIAL_EMPTY",
            source_candidate_id=None, source_evaluation_run_id=None,
        ))
    rows.sort(key=lambda r: (r.action, r.ticker, r.trade_id))
    return rows


def _emit_restore_sql(
    path: Path, update_rows: list[BackfillRow],
) -> None:
    """Write per-affected-row UPDATE statements with OLD values.

    File is always written (even when update_rows is empty) so the
    artifact path returned to the operator is always real.
    """
    lines = [
        "-- V2.G3 backfill-trades-sector-industry restore artifact",
        f"-- Generated at {datetime.now(UTC).isoformat()}",
        "-- Apply via: sqlite3 swing.db < <this-file>",
        "",
    ]
    for r in update_rows:
        # Escape single quotes in original values (defensive; sector +
        # industry come from finviz CSV which historically has none, but
        # guard regardless).
        safe_sector = r.current_sector.replace("'", "''")
        safe_industry = r.current_industry.replace("'", "''")
        lines.append(
            f"UPDATE trades SET sector='{safe_sector}', "
            f"industry='{safe_industry}' WHERE id={r.trade_id};"
        )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _apply_updates(
    conn: sqlite3.Connection, update_rows: list[BackfillRow],
) -> None:
    """Issue idempotent UPDATEs (WHERE clause makes re-runs no-op)."""
    for r in update_rows:
        conn.execute(
            "UPDATE trades SET sector=?, industry=? "
            "WHERE id=? AND TRIM(sector)='' AND TRIM(industry)=''",
            (r.proposed_sector, r.proposed_industry, r.trade_id),
        )


def _format_report(
    *,
    rows: list[BackfillRow], update_count: int,
    skip_no_cand: int, skip_partial: int, apply: bool,
) -> list[str]:
    """ASCII-only operator-friendly report (gotcha #32)."""
    mode = "APPLY" if apply else "DRY-RUN"
    out = [
        f"V2.G3 backfill-trades-sector-industry ({mode})",
        "",
        f"  UPDATE                 : {update_count}",
        f"  SKIP_NO_CANDIDATES_ROW : {skip_no_cand}",
        f"  SKIP_PARTIAL_EMPTY     : {skip_partial}",
        "",
        "Per-row detail (provenance per Codex R1.M#6 LOCK):",
        (
            "  trade_id | ticker | current | proposed | "
            "source_cand_id | source_eval_run_id | action"
        ),
    ]
    for r in rows:
        cur = f"({r.current_sector!r}, {r.current_industry!r})"
        prop = f"({r.proposed_sector!r}, {r.proposed_industry!r})"
        cand_id_cell = (
            str(r.source_candidate_id)
            if r.source_candidate_id is not None else "-"
        )
        run_id_cell = (
            str(r.source_evaluation_run_id)
            if r.source_evaluation_run_id is not None else "-"
        )
        out.append(
            f"  {r.trade_id:>8} | {r.ticker:<6} | "
            f"{cur} | {prop} | "
            f"{cand_id_cell:>14} | {run_id_cell:>18} | {r.action}"
        )
    return out
