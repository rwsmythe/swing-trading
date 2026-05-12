"""Phase 9 Sub-bundle C T-C.1 — hypothesis_status_history seed verification.

Per spec §3.4.1 R3 Major #2 + plan §A.7 #3:

  - For each existing hypothesis_registry row, migration 0017 INSERTs ONE
    hypothesis_status_history row with effective_to IS NULL (open interval).
  - effective_from = strftime('%Y-%m-%dT00:00:00.000', registry.created_at)
    (day-start anchor — preserves chronology while satisfying the
    millisecond-precision datetime validator).
  - status matches the registry row's status.
  - change_reason IS NULL (no prior change).
  - recorded_at is a valid millisecond-precision ISO datetime (migration
    apply time).

Production DB at v17 has 4 hypotheses (per dispatch brief §0.3); a freshly-
migrated test DB inherits the migration 0008 INSERT-OR-IGNORE seeds (4
rows: VIR, DHC, CC + one more — see migration 0008 source). The seed
predicate `SELECT id, status, created_at FROM hypothesis_registry` drives
the audit-row count exactly.

Discriminating test (per plan §F T-C.1 acceptance #5): inserting a NEW
hypothesis_registry row POST-migration does NOT auto-create a history row
(seed runs ONCE; the service helper landed in T-C.4 handles post-migration
status transitions).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import validate_ms_iso
from swing.data.db import ensure_schema


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "phase9_seed.db"
    return ensure_schema(db_path)


# ============================================================================
# §1 — seed count parity with hypothesis_registry
# ============================================================================


def test_hypothesis_status_history_has_one_seed_per_registry_row(
    conn: sqlite3.Connection,
) -> None:
    registry_count = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_registry"
    ).fetchone()[0]
    history_count = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    assert registry_count > 0, "fixture should inherit migration 0008 seed"
    assert history_count == registry_count, (
        f"seed parity broken: {registry_count} hypotheses but "
        f"{history_count} history rows"
    )


def test_every_seed_history_row_is_open_interval(
    conn: sqlite3.Connection,
) -> None:
    """All seeds have effective_to IS NULL (the current/open row)."""
    closed = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history "
        "WHERE effective_to IS NOT NULL"
    ).fetchone()[0]
    assert closed == 0


def test_every_hypothesis_has_exactly_one_open_history_row(
    conn: sqlite3.Connection,
) -> None:
    """Partial-unique index guarantees this — verify behaviorally."""
    rows = conn.execute(
        "SELECT hypothesis_id, COUNT(*) FROM hypothesis_status_history "
        "WHERE effective_to IS NULL GROUP BY hypothesis_id"
    ).fetchall()
    for hyp_id, count in rows:
        assert count == 1, f"hypothesis_id={hyp_id} has {count} open rows; expected 1"


# ============================================================================
# §2 — per-field shape of seed rows
# ============================================================================


def test_seed_status_matches_registry_status(conn: sqlite3.Connection) -> None:
    """spec §3.4.1: seed status = current hypothesis_registry.status."""
    rows = conn.execute(
        "SELECT hr.id, hr.status, hsh.status "
        "FROM hypothesis_registry hr "
        "JOIN hypothesis_status_history hsh "
        "  ON hsh.hypothesis_id = hr.id AND hsh.effective_to IS NULL"
    ).fetchall()
    assert rows, "expected at least one seed pair"
    for hyp_id, reg_status, hist_status in rows:
        assert reg_status == hist_status, (
            f"hypothesis_id={hyp_id}: registry.status={reg_status!r} "
            f"vs history.status={hist_status!r}"
        )


def test_seed_change_reason_is_null(conn: sqlite3.Connection) -> None:
    """spec §3.4.1: seed rows carry change_reason=NULL (no prior change)."""
    rows = conn.execute(
        "SELECT history_id, change_reason FROM hypothesis_status_history"
    ).fetchall()
    for hid, reason in rows:
        assert reason is None, (
            f"seed history_id={hid} has non-NULL change_reason={reason!r}"
        )


def test_seed_effective_from_is_day_start_of_registry_created_at(
    conn: sqlite3.Connection,
) -> None:
    """spec §3.4.1 R3 Major #2: effective_from = strftime day-start anchor.

    The migration normalizes hypothesis_registry.created_at (which is
    typically date-only like '2026-04-25') to '2026-04-25T00:00:00.000'.
    The validator-format anchor.
    """
    rows = conn.execute(
        "SELECT hr.created_at, hsh.effective_from "
        "FROM hypothesis_registry hr "
        "JOIN hypothesis_status_history hsh "
        "  ON hsh.hypothesis_id = hr.id AND hsh.effective_to IS NULL"
    ).fetchall()
    assert rows
    for reg_created_at, hist_eff_from in rows:
        # Format conformance.
        validate_ms_iso(hist_eff_from)
        # Day-start anchor: T part must be 00:00:00.000.
        date_part, t_part = hist_eff_from.split("T")
        assert t_part == "00:00:00.000", (
            f"effective_from {hist_eff_from!r} is not a day-start anchor"
        )
        # Date-part agrees with registry.created_at's date-part.
        # registry.created_at may be 'YYYY-MM-DD' (migration 0008 seed) or
        # an ISO datetime; both share the YYYY-MM-DD prefix.
        assert reg_created_at.startswith(date_part), (
            f"seed history effective_from {hist_eff_from!r} does not match "
            f"registry created_at {reg_created_at!r}"
        )


def test_seed_recorded_at_is_valid_millisecond_iso(
    conn: sqlite3.Connection,
) -> None:
    """recorded_at = migration apply time, millisecond-precision validator format."""
    rows = conn.execute(
        "SELECT recorded_at FROM hypothesis_status_history"
    ).fetchall()
    assert rows
    for (recorded_at,) in rows:
        validate_ms_iso(recorded_at)


# ============================================================================
# §3 — Discriminating test: NEW post-migration hypothesis does NOT auto-seed
# ============================================================================


def test_new_hypothesis_post_migration_does_not_auto_create_history_row(
    conn: sqlite3.Connection,
) -> None:
    """Spec §4.3 + plan §F T-C.1 acceptance #5.

    The migration seeds ONCE (at v16 → v17 transition). NEW hypotheses
    added post-migration do NOT auto-create a history row via SQL trigger;
    the application-layer service helper landed in T-C.4 is the canonical
    write path. Until that service helper fires, no history row exists.
    """
    pre_count = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO hypothesis_registry "
        "(name, statement, target_sample_size, decision_criteria, "
        " consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at) "
        "VALUES ('test-post-migration', 'unused', 50, 'unused', 5, 25.0, "
        "'2026-05-12')"
    )
    post_count = conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    assert post_count == pre_count, (
        f"new registry row triggered an auto-seed; pre={pre_count}, "
        f"post={post_count} — there should be no SQL trigger"
    )


def test_seed_runs_only_once_idempotent_under_ensure_schema(
    tmp_path: Path,
) -> None:
    """Re-running ensure_schema on a v17 DB does not duplicate seeds.

    Per Phase 7 migration-runner discipline: schema_version=17 → runner
    skips 0017. Seed INSERTs do not re-fire.
    """
    db_path = tmp_path / "idempotent.db"
    conn1 = ensure_schema(db_path)
    count1 = conn1.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    conn1.close()

    conn2 = ensure_schema(db_path)
    count2 = conn2.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history"
    ).fetchone()[0]
    conn2.close()
    assert count1 == count2, (
        f"seed rows duplicated on re-ensure_schema: {count1} → {count2}"
    )
