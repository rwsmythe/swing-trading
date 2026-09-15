"""SQLite connection + migrations + schema-version gate."""
from __future__ import annotations

import contextlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# pipeline_pattern_classifications + trade chart_pattern columns (migrations 0009 + 0010)
# chart_targets source taxonomy expansion (migration 0011)
# sector + industry columns on candidates + trades (migration 0012)
# post-trade review surface: 10 trade fields + review_log table (migration 0013)
# phase 7 state machine + fills first-class (migration 0014)
# finviz_api_calls table (migration 0015)
# phase 8 daily_management_records table + planned_target_R column (migration 0016)
# phase 9 risk_policy + reconciliation depth (migration 0017): 5 new tables
#   (risk_policy / reconciliation_runs / reconciliation_discrepancies /
#   hypothesis_status_history / account_equity_snapshots) + 2 ALTER ADDs
#   (trades.risk_policy_id_at_lock + review_log.risk_policy_id_at_review_completion)
# phase 11 schwab API integration (migration 0018): schwab_api_calls audit
#   table + 2 ALTER ADDs (account_equity_snapshots.schwab_account_hash +
#   reconciliation_runs.schwab_api_call_id). Migration opens with explicit
#   BEGIN; / COMMIT; per Codex R1 Critical #1 (executescript implicit COMMIT
#   gotcha) — sets new discipline for all future migrations.
# phase 12 sub-bundle C.A auto-correct reconciliation (migration 0019):
#   reconciliation_corrections audit table (20 cols + 4 indexes) +
#   reconciliation_discrepancies rebuild (widen resolution CHECK 5→9 + new
#   ambiguity_kind column + cross-column CHECK) + ALTER review_log ADD
#   superseded_by_correction_id + ALTER schwab_api_calls ADD linked_correction_id +
#   trade_events rebuild (widen event_type CHECK 6→7 to add
#   'reconciliation_auto_correct'). Atomic BEGIN/COMMIT discipline preserved.
# phase 13 t2.sb1 charts patterns autofill usability (migration 0020):
#   5 new tables (pattern_exemplars + chart_renders + pattern_evaluations +
#   watchlist_close_track_flags + watchlist_close_track_flag_events) +
#   schwab_api_calls rebuild (widen surface CHECK 2 -> 4: add 'trade_entry' +
#   'trade_exit') + fills widening (4 ALTER ADDs: fill_origin DEFAULT
#   'operator_typed' + 3 audit JSON cols) + review_log widening
#   (auto_populated_field_keys_json). Atomic BEGIN/COMMIT discipline
#   preserved. OQ-12 Option E migration-only commit boundary.
# phase 13 t2.sb6c trades backlinks atomic landing (migration 0021):
#   2 NULLable INTEGER FK columns on trades — candidate_id (REFERENCES
#   candidates(id) ON DELETE SET NULL) + pattern_evaluation_id (REFERENCES
#   pattern_evaluations(id) ON DELETE SET NULL) + 2 indexes. Closes T2.SB6b
#   V1 simplifications #4 + #5; enables outcome bucketing per spec §5.10
#   lines 785-790 + line 775. Backfill semantics: NULL for all pre-v21
#   existing rows (OQ-1). Atomic BEGIN/COMMIT discipline preserved.
# phase 14 sub-bundle 3 chart-surface uniformity (migration 0023):
#   atomic rename of the chart_renders.surface old detail token to
#   'ticker_detail' via an id-preserving single-table rebuild. NO new tables,
#   NO column-shape change, NO candlestick change. Atomic BEGIN/COMMIT
#   discipline preserved (gotcha #9).
# phase 18 arc 18-H.6 untracked_broker_position (migration 0031): rebuild
#   reconciliation_discrepancies to widen discrepancy_type CHECK 10 -> 11
#   (add 'untracked_broker_position'). 0019 table-rebuild pattern; all columns
#   / indexes / FKs / cross-column CHECK preserved. Atomic BEGIN/COMMIT.
# phase 21 arc 21-A latch_view_events (migration 0032): ONE new table holding
#   a single view-telemetry fact per (latch, action session), keyed on the
#   shared latch identity block (candidate_id NOT NULL / ON DELETE RESTRICT --
#   the immutable 21-A <-> 21-B bridge key -- plus evaluation_run_id / ticker /
#   detection_date / pipeline_run_id nullable ON DELETE SET NULL). NO existing
#   table touched. Atomic BEGIN/COMMIT.
# h1 decision-criteria amendment (migration 0034): a V2.1 section VII.F
#   governance amendment to a PRE-REGISTERED decision rule. ONE additive
#   nullable column, hypothesis_registry.preregistered_decision_criteria
#   (NULL DEFINED as "never amended", NOT "unknown"), plus two UPDATEs on the
#   'A+ baseline' row only. NO new table; rows 2-5 untouched. Atomic
#   BEGIN/COMMIT.
# item-5 A-4 fills_trades_price_divergence (migration 0035): rebuild
#   reconciliation_discrepancies to widen discrepancy_type CHECK 11 -> 12
#   (add 'fills_trades_price_divergence', the 20-A A-5 fills<->trades entry-VWAP
#   invariant promoted off its `entry_price_mismatch` + discriminator
#   approximation). 0031/0019 table-rebuild pattern; all columns / indexes /
#   FKs / cross-column CHECK preserved. Atomic BEGIN/COMMIT.
# demand-c provenance_corrections (migration 0036): ONE new append-only audit
#   table whose schema IS the evidence rule -- the cited candidate,
#   recommendation, evaluation run, hypothesis, status interval and pipeline
#   run are all NOT NULL FKs, and the frozen anchors make contemporaneity an
#   INTRA-row CHECK. ADDITIVE ONLY: nothing is rebuilt, dropped or renamed.
#   Atomic BEGIN/COMMIT.
# 22-A latch_order_mandate_links (migration 0037): the durable order<->mandate
#   link minted by a trigger at broker acceptance, plus the STRUCTURAL
#   immutability that makes a fire's frozen invalidation provable -- a
#   candidates UPDATE + DELETE barrier and a CONFLICT-SCOPED BEFORE INSERT
#   barrier closing the measured REPLACE bypass, a single-state
#   candidates_immutability_epoch with its own three barriers, SIX ADD COLUMNs
#   on provenance_corrections and the TRANSACTIONAL replacement of that table's
#   two triggers (CHARC CONDITION-4 exception 2, declared in the migration
#   header). ADDITIVE: nothing rebuilt, no existing row mutated. Atomic
#   BEGIN/COMMIT.
# 22-A4 trades.attempt_id (migration 0038): the PER-ATTEMPT IDENTITY TOKEN --
#   one nullable TEXT column with a `typeof(...) = 'text' AND length(...) = 36`
#   CHECK, a partial UNIQUE index over non-NULL tokens, and an UNCONDITIONAL
#   `BEFORE UPDATE OF attempt_id` write-once trigger. Written by the SAME
#   INSERT that writes the trade row, so it is CO-DURABLE rather than a
#   run-level stamp (gotcha #30), and unique per attempt by mechanism, which
#   the rowid is not (a rolled-back rowid is reissued by the engine). It is
#   what lets a commit whose own RETURN was lost be resolved by identity on a
#   FRESH connection. NO BACKFILL -- every pre-existing row reads NULL, which
#   is what the partial index is for. ADDITIVE: nothing rebuilt, no existing
#   row mutated. Atomic BEGIN/COMMIT.
EXPECTED_SCHEMA_VERSION = 38
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DEFAULT_BUSY_TIMEOUT_MS = 30000
"""Default per-connection SQLite busy_timeout (ms). 30 s is safe and fully
effective for the no-deadline OHLCV fetch path (the #23-amplified bulk of the
lock-contention degrade); it cannot rescue the 6 s-deadline quote path on its
own (see the serialized audit-writer mechanism). busy_timeout is per-connection
(NOT persistent like WAL), so it MUST be set on every connection."""


def open_connection(
    db_path_or_uri,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    reaffirm_wal: bool = False,
    uri: bool = False,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Public swing.db opener. Every swing.db connection routes through here so
    the busy_timeout is uniform (OQ-B). Applies, in THIS order:

      1. busy_timeout  : FIRST -- so any subsequent lock acquisition (a WAL
                         reaffirm, a BEGIN IMMEDIATE) is covered by the handler.
      2. foreign_keys=ON
      3. journal_mode=WAL : ONLY when reaffirm_wal=True (the ensure_schema path).
                         NOT on the hot connect() path -- the live DB is already
                         WAL (persistent in the file header); reaffirming per-open
                         is needless overhead and a needless lock point.

    ``uri=True`` forwards to ``sqlite3.connect(..., uri=True)`` so callers can
    pass a ``file:...?mode=rw`` URI and KEEP fail-closed semantics (backup source).
    ``check_same_thread=False`` is for the single shared serialized audit-writer
    connection (guarded by audit_service._AUDIT_WRITE_LOCK); do NOT use a shared
    connection across threads without that lock.
    """
    conn = sqlite3.connect(
        db_path_or_uri, uri=uri, check_same_thread=check_same_thread
    )
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys=ON")
    if reaffirm_wal:
        conn.execute("PRAGMA journal_mode=WAL")
    return conn

# Phase 7 backup gate (spec §12.1): when migrating to schema_version >= 14,
# the runner takes a SQLite-native Connection.backup() snapshot of the source
# DB and verifies it against this table set BEFORE applying any migration.
# Update this set when new tables are added in subsequent phases so the
# integrity check stays meaningful.
PHASE7_EXPECTED_TABLES: set[str] = {
    "trades",
    "exits",
    "trade_events",
    "pipeline_runs",
    "weather_runs",
    "candidates",
    "evaluation_runs",
    "daily_recommendations",
    "watchlist",
    "cash_movements",
    "review_log",
    "schema_version",
}

# Phase 8 backup gate (spec §8.2 + plan §A.5): when migrating from v15 → v16+,
# snapshot the live v15 DB. The expected table set is the ACTUAL post-Phase-7-
# post-Finviz v15 schema (NOT the Phase 7 v13 source set). Phase 7's migration
# 0014 dropped `exits` and added `fills`; migration 0015 (Finviz V1) added
# `finviz_api_calls`. Per Codex R4 Major #1: derive deterministically from the
# Phase 7 set so future maintainers can reason about provenance.
PHASE8_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    (PHASE7_EXPECTED_TABLES - {"exits"}) | {"fills", "finviz_api_calls"}
)

# Phase 9 backup gate (spec §9.3 + plan §A.0): when migrating from v16 → v17+,
# snapshot the live v16 DB. Adds `daily_management_records` to the post-Phase-8
# baseline; derive deterministically from PHASE8 set so provenance stays
# auditable. Filename pattern `swing-pre-phase9-migration-<ISO>.db`.
PHASE9_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE8_PRE_MIGRATION_EXPECTED_TABLES | {"daily_management_records"}
)

# Phase 12 Sub-bundle C backup gate (spec §11.3 + plan §A.12 + plan §B.4):
# when migrating from v18 → v19+, snapshot the live v18 DB. Adds the Phase 9
# tables (risk_policy / reconciliation_runs / reconciliation_discrepancies /
# hypothesis_status_history / account_equity_snapshots) AND the Phase 11
# schwab_api_calls audit table to the post-Phase-9 baseline. Derived
# deterministically from PHASE9 set so provenance stays auditable. Phase 11
# itself did NOT wire a version-specific gate (plan §C.5 LOCK on Sub-bundle B
# of Phase 11; no swing-pre-phase11-*.db backups exist in the wild). Filename
# pattern `swing-pre-phase12-bundle-c-migration-<ISO>.db` per plan §B.4 #1.
PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE9_PRE_MIGRATION_EXPECTED_TABLES
    | {
        "risk_policy",
        "reconciliation_runs",
        "reconciliation_discrepancies",
        "hypothesis_status_history",
        "account_equity_snapshots",
        "schwab_api_calls",
    }
)

# Phase 13 T2.SB1 backup gate (spec §3.5 + plan §B.1): when migrating from
# v19 -> v20+, snapshot the live v19 DB. Adds reconciliation_corrections
# (introduced in migration 0019) to the post-Phase-12-Sub-bundle-C baseline.
# Derived deterministically from PHASE12 set so provenance stays auditable.
# Filename pattern: ``swing-pre-phase13-migration-<ISO>.db`` per plan §B.1 +
# CLAUDE.md migration-runner backup-gate strict-equality gotcha
# (``pre_version == 19`` STRICT EQUALITY, NOT ``<=``).
PHASE13_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES
    | {"reconciliation_corrections"}
)

# Phase 13 T2.SB6c backup gate (spec §A.14 + plan §B.5): when migrating from
# v20 -> v21+, snapshot the live v20 DB. Adds the 5 v20-shipped Phase 13
# tables (pattern_exemplars + chart_renders + pattern_evaluations +
# watchlist_close_track_flags + watchlist_close_track_flag_events) to the
# post-Phase-13-v20 baseline. Derived deterministically from PHASE13 set so
# provenance stays auditable. Filename pattern:
# ``swing-pre-phase13-sb6c-migration-<ISO>.db`` per plan §B.5 + OQ-8 LOCK +
# CLAUDE.md migration-runner backup-gate strict-equality gotcha
# (``pre_version == 20`` STRICT EQUALITY, NOT ``<=``).
PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_PRE_MIGRATION_EXPECTED_TABLES
    | {
        "pattern_exemplars",
        "chart_renders",
        "pattern_evaluations",
        "watchlist_close_track_flags",
        "watchlist_close_track_flag_events",
    }
)

# Phase 14 Sub-bundle 2 backup gate (spec section 2.3 + plan T-2.1): when
# migrating from v21 -> v22+, snapshot the live v21 DB. Migration 0021 added
# only trades columns + indexes -- NO new tables -- so the table set present
# at v21 equals the set present at v20. Derived deterministically from the
# PHASE13_SB6C set so provenance stays auditable. Filename pattern:
# ``swing-pre-phase14-migration-<ISO>.db`` per CLAUDE.md migration-runner
# backup-gate strict-equality gotcha (``pre_version == 21`` STRICT EQUALITY,
# NOT ``<=``).
PHASE14_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 14 Sub-bundle 3 backup gate (plan §G Task T-3.1): when migrating from
# v22 -> v23+, snapshot the live v22 DB. Migration 0023 only renames a
# chart_renders.surface enum value via a single-table rebuild -- NO new tables
# -- so the table set present at v22 equals the set present after Sub-bundle 2
# (which added pattern_detection_events + pattern_forward_observations).
# Derived deterministically from the PHASE14 set so provenance stays auditable.
# Filename pattern ``swing-pre-phase14-sb3-migration-<ISO>.db`` per CLAUDE.md
# migration-runner backup-gate strict-equality gotcha (``pre_version == 22``
# STRICT EQUALITY, NOT ``<=``).
PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE14_PRE_MIGRATION_EXPECTED_TABLES
    | {"pattern_detection_events", "pattern_forward_observations"}
)

# B-7 (Phase 15) backup gate: migrating v23 -> v24 snapshots the live v23 DB.
# Migration 0024 only ADDs the nullable failure_mode column -- NO new tables --
# so the table set present at v23 equals the post-SB3 set. Derived from the SB3
# set so provenance stays auditable.
B7_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 16 backup gate: migrating v24 -> v25 snapshots the live v24 DB before
# migration 0025 (pipeline_step_timings). Migration 0024 added only the nullable
# failure_mode COLUMN (no new tables), so the v24 table set equals the B7 set.
PHASE16_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    B7_PRE_MIGRATION_EXPECTED_TABLES
)

# Broad-watch-baseline (migration 0026) backup gate: migrating v25 -> v26
# snapshots the live v25 DB. 0026 adds NO table (additive registry row only), so
# the v26 table set equals the v25 set. The v25 set = the v24 set PLUS
# pipeline_step_timings (created by 0025) -- PHASE16_PRE_MIGRATION_EXPECTED_TABLES
# is the v24 set, so derive the v25 set from it for auditable provenance.
BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE16_PRE_MIGRATION_EXPECTED_TABLES | {"pipeline_step_timings"}
)

# entry_intent (migration 0027) backup gate: migrating v26 -> v27 snapshots the
# live v26 DB. 0027 is an ALTER ADD COLUMN -- it adds NO table -- and 0026 added
# no table either, so the v26 table set EQUALS the v25 set. Alias the broad-watch
# (true-v25) set for auditable provenance.
ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES
)

# 0028 (watchlist pin) adds columns to `watchlist` only — no new table — so the
# pre-v28 (v27) table set is identical to the entry_intent pre-migration set.
WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES
)

# 0029 (cash reconciliation) rebuilds cash_movements + ALTERs
# account_equity_snapshots — NO new table — so the pre-v29 (v28) table set is
# identical to the watchlist-pin pre-migration set.
CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 18 Arc 18-C (0030) pre-migration table set. The pre-v30 (v29) table set
# EQUALS the pre-v29 (cash-recon) set: 0029 adds NO new table (it rebuilds
# cash_movements + ALTERs account_equity_snapshots), so the cash-recon alias
# chain (which already includes pipeline_step_timings added by 0025) is the
# correct expected-tables baseline. 0030 is the first NEW table since 0025.
PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 18 Arc 18-H.6 (0031) pre-migration table set. The pre-v31 (v30) table
# set = the Arc-C (pre-v30) set PLUS yfinance_calls (the only NEW table since
# 0025, created by 0030). 0031 rebuilds reconciliation_discrepancies in place
# (widen the discrepancy_type CHECK) -> adds NO new table. Derived
# deterministically for auditable provenance.
PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES | {"yfinance_calls"}
)

# Phase 21 Arc 21-A (0032) pre-migration table set. 0031 rebuilt
# reconciliation_discrepancies in place -> added NO new table, so the v31 table
# set EQUALS the 18-H.6 (pre-v31) set. Derived deterministically for auditable
# provenance.
PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES
)

# Phase 21 Arc 21-B (0033) pre-migration table set. 0032 added exactly ONE
# table, `latch_view_events`, so the v32 set is the 21-A set plus that one.
# Derived deterministically for auditable provenance -- never hand-listed.
PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {"latch_view_events"}
)

# H1 decision-criteria amendment (0034) pre-migration table set. 0033 REBUILT
# latch_view_events (already in the 21-B set) and added exactly ONE new table,
# `latch_order_intents`, so the v33 set is the 21-B set plus that one. 0034
# itself adds NO table -- it is one ALTER ADD COLUMN plus two row UPDATEs.
# Derived deterministically for auditable provenance -- never hand-listed.
#
# `hypothesis_registry` is added EXPLICITLY. These expected-table sets are a
# PRESENCE subset, not an exhaustive manifest, and the chain they derive from
# (PHASE7_EXPECTED_TABLES, the v13 set) never listed it -- so every gate to
# date could approve a backup missing it. That is tolerable for a gate whose
# migration does not touch the table; it is not tolerable HERE, where the
# backup exists specifically to preserve the pre-amendment governance row.
# A gate that does not require the one table its migration amends is not a
# fail-closed belt. Scoped to this gate deliberately: retrofitting the shared
# chain is a separate change across 18 gates.
H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES
    | {"latch_order_intents", "hypothesis_registry"}
)

# Item-5 A-4 (migration 0035) pre-migration expected-table set. Derived from
# the H1 chain, which already carries `reconciliation_discrepancies` -- the
# table 0035 REBUILDS. That is the fail-closed property the H1 gate's comment
# was written to establish (a gate that does not require the one table its
# migration touches is not a belt), and it is inherited here rather than
# re-argued. `reconciliation_corrections` is added EXPLICITLY: it holds the FK
# into the rebuilt table, the runner drops that table with foreign_keys=OFF,
# and a backup missing the child rows would be useless for exactly the failure
# this gate exists for.
A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES
    | {"reconciliation_discrepancies", "reconciliation_corrections"}
)

# Demand C (migration 0036) pre-migration expected-table set. INHERITED from
# the A-4 chain with NO additions: 0036 CREATEs a table rather than rebuilding
# one, so it requires nothing new in the PRE set -- but the chain is inherited
# rather than restarted so the backup's provenance stays auditable (the
# `PHASE14_PRE_MIGRATION_EXPECTED_TABLES` precedent). The tables 0036's FKs
# POINT AT -- trades, fills, candidates, daily_recommendations,
# evaluation_runs, hypothesis_registry, hypothesis_status_history,
# pipeline_runs, risk_policy -- are all already members via that chain.
DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES
)

# 22-A (migration 0037) pre-migration expected-table set. INHERITED from the
# Demand-C chain PLUS `provenance_corrections` EXPLICITLY: 0037 ALTERs that
# table (six ADD COLUMNs) and transactionally replaces two of its triggers, and
# the H1 gate's own rule is that a gate which does not require the one table its
# migration TOUCHES is not a belt. `candidates` and `latch_order_intents` -- the
# tables the barrier and the backfill read -- are already members via the chain
# (verified by reading the resolved set, not by assuming the chain covers them).
PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES | {"provenance_corrections"}
)

# 22-A4 (migration 0038) pre-migration expected-table set. INHERITED from the
# 22-A chain PLUS the THREE tables 0037 itself created -- read out of
# `0038`'s predecessor migration file (`0037_latch_order_mandate_links.sql`
# sections at :121, :289 and :518) rather than recalled.
#
# THE SET IS A FLOOR, NOT A MANIFEST, and the instrument says so:
# `_verify_backup_integrity` computes `missing = expected_tables -
# actual_tables` and raises only on a MISSING member, so a pre-image carrying
# MORE tables than this set is still a valid backup. Ruled 2026-09-07 (CHARC)
# against a plan that had asked for equality here; the equality belongs to a
# separate schema-manifest comparator, beside this gate rather than inside it.
PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {
        "candidates_immutability_epoch",
        "latch_order_mandate_links",
        "fill_envelope_identity",
    }
)


class SchemaVersionMismatchError(RuntimeError):
    """Raised when the DB schema version doesn't match what the code expects."""


class DuplicateOpenTradesError(RuntimeError):
    """Migration 0004 cannot apply while duplicate active-trade rows exist.

    Migration 0004 enforces the one-open-per-ticker invariant via a partial
    unique index. Pre-Phase-7 the index was keyed on ``status='open'``;
    Phase 7 re-keys it to ``state IN ('entered','managing','partial_exited')``
    once migration 0014 lands. The runtime preflight below still queries the
    legacy ``status='open'`` column because Migration 0004 fires DURING the
    0001 -> 0014 migration walk and the ``state`` column does not yet exist
    when this preflight runs. Helper-body rewrite (plan §2.1 line 165) is
    deferred to a later Sub-A task that owns the runtime call-site rewrite;
    in practice the preflight only fires once on a fresh-seed migration walk
    starting at v3 or earlier, and existing DBs already past v4 never hit it.
    """


class MigrationBackupRequiredException(RuntimeError):  # noqa: N818  -- name fixed by Phase 7 spec §12.1
    """Raised when pre-migration backup creation or verification fails.

    Migration runner refuses to apply schema changes; source DB unchanged.
    Per spec §12.1: SQLite-native Connection.backup() is the ONLY accepted
    snapshot path; size threshold is advisory; PRAGMA integrity_check must
    return exactly 'ok' and the expected table set must be present.
    """


def _apply_migration(conn: sqlite3.Connection, sql_path: Path) -> None:
    """Apply a migration SQL script atomically; rollback on any failure.

    sqlite3.Connection.executescript() leaves the in-script transaction open
    if a statement fails mid-script — without explicit rollback, a caller that
    catches the exception can later commit() the partial state and persist a
    half-applied migration. Phase 7's 0014 migration is large + invasive
    (table rebuilds, FK cascade, multi-step backfill); a half-applied state
    would leave the production DB at an undefined version with no clean
    forward path. Wrap execution in try/except to guarantee rollback on
    failure; re-raise so run_migrations() abort behavior is preserved.

    Hotfix 2026-05-05 (Sub-C integration layer; Sub-A territory exception
    authorized per chained-branch posture): toggle foreign_keys=OFF before
    executescript + restore prior value after. Migration 0014's step 10
    (CREATE-COPY-DROP-RENAME on trades) triggers ON DELETE CASCADE on
    fills.trade_id + trade_events.trade_id when foreign_keys=ON, wiping
    the just-populated fills table (5 rows) AND the audit-log trade_events
    (11 rows in production) during the table rebuild. Sub-A T10 test passed
    because the test fixture's connection had foreign_keys=OFF (sqlite3's
    default for fresh connections); production has foreign_keys=ON
    (db.ensure_schema sets it explicitly). Per SQLite docs §11.2, table-
    rebuild migrations should disable foreign_keys for the duration. Apply
    the fix at the runner level so all current + future migrations inherit
    the discipline.

    PRAGMA foreign_keys is a no-op inside an active transaction. The PRAGMA
    must be set when no transaction is open; sqlite3.Connection.executescript
    issues an implicit COMMIT before running its script, so the connection
    is in autocommit mode at the moment of the PRAGMA call.
    """
    sql = sql_path.read_text(encoding="utf-8")
    prior_fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(
            "PRAGMA foreign_keys=ON" if prior_fk else "PRAGMA foreign_keys=OFF"
        )


def _preflight_migration_0004(conn: sqlite3.Connection) -> None:
    """Reject migration 0004 if the trades table already has duplicate open rows."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
    )
    if cur.fetchone() is None:
        return
    rows = conn.execute(
        "SELECT ticker, COUNT(*) AS n FROM trades WHERE status='open' "
        "GROUP BY ticker HAVING n > 1 ORDER BY ticker"
    ).fetchall()
    if not rows:
        return
    details = ", ".join(f"{t} ({n} open)" for t, n in rows)
    raise DuplicateOpenTradesError(
        "Cannot apply migration 0004 (one-open-trade-per-ticker invariant): "
        f"duplicate open trades exist for: {details}. "
        "Inspect with: SELECT id, ticker, entry_date, entry_price, status FROM trades "
        "WHERE status='open' ORDER BY ticker, entry_date; "
        "Resolve the duplicates via the journal so the audit trail stays intact: "
        "for a legitimate exit, close the trade through `swing trade exit` "
        "(records an `exits` row and a `trade_events` row in one transaction); "
        "for an erroneous INSERT (no real fill ever occurred), keep the row "
        "and mark it closed with a correction note in a SINGLE transaction: "
        "(1) UPDATE trades SET status='closed' WHERE id=?; (2) INSERT INTO "
        "trade_events (trade_id, ts, event_type, payload_json) VALUES (?, ?, "
        "'note', json_object('correction','erroneous duplicate open — closed "
        "to resolve one-open-per-ticker invariant')). Both statements inside "
        "BEGIN/COMMIT. Never flip `trades.status` without the paired note "
        "event — the CHECK constraint only allows event_type in "
        "('entry','stop_adjust','note','exit','flag'), and deleting the bad "
        "row won't work either because `trade_events.trade_id` cascades on "
        "delete and would drop any audit note you try to attach."
    )


def _current_version(conn: sqlite3.Connection) -> int:
    """Return DB's schema_version, or 0 if no schema_version table exists."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        return 0
    cur = conn.execute("SELECT version FROM schema_version")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _verify_backup_integrity(
    backup_path: Path, *, expected_tables: set[str]
) -> None:
    """Run 4 binding integrity checks per spec §12.1; raise on any failure.

    Checks (each independent + separately tested):
      1. File exists at ``backup_path``.
      2. File is non-empty (size > 0). Size threshold relative to source is
         advisory only — VACUUM INTO can legitimately compact, so do NOT use
         a percentage-of-source heuristic as a hard gate.
      3. ``PRAGMA integrity_check`` returns exactly 'ok' (page-level
         corruption, broken indices, FK issues all surface here).
      4. ``sqlite_master`` contains ``expected_tables``.
    """
    if not backup_path.exists():
        raise MigrationBackupRequiredException(
            f"backup file missing: {backup_path}"
        )
    if backup_path.stat().st_size == 0:
        raise MigrationBackupRequiredException(
            f"backup file empty: {backup_path}"
        )
    conn = sqlite3.connect(backup_path)
    try:
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise MigrationBackupRequiredException(
                f"PRAGMA integrity_check failed on backup: {exc}"
            ) from exc
        if result is None or result[0] != "ok":
            raise MigrationBackupRequiredException(
                f"PRAGMA integrity_check failed on backup: {result}"
            )
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        actual_tables = {r[0] for r in rows}
        missing = expected_tables - actual_tables
        if missing:
            raise MigrationBackupRequiredException(
                f"backup missing expected table(s): {sorted(missing)}"
            )
    finally:
        conn.close()


def _resolve_main_db_path(conn: sqlite3.Connection) -> Path | None:
    """Return the filesystem path of the connection's main DB, or None for memory."""
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        # row format: (seq, name, file)
        if row[1] == "main":
            file_str = row[2] or ""
            if not file_str:
                return None
            return Path(file_str)
    return None


@dataclass(frozen=True, eq=False)
class BackupGateSpec:
    """One pre-migration backup gate: a row of ``_PRE_MIGRATION_BACKUP_GATES``.

    ``filename_stem`` names the image ``swing-pre-<stem>-migration-<UTC>Z.db``
    and is preserved byte-for-byte from the hand-copied gate it replaced (the
    D32 retention sweep and the witness records name files by it).
    ``expected_tables`` CITES the module constant (the same object).
    ``gate_name`` is the module-level wrapper ``run_migrations`` resolves BY
    ATTRIBUTE at call time. ``label`` prefixes both refusal messages.
    ``creator_alias`` names a legacy creator kept as an alias of the one
    parameterised creator, resolved by attribute at call time so a patch on
    that name intercepts; ``None`` calls ``_create_gate_backup`` directly.
    """

    pre_version: int
    filename_stem: str
    expected_tables: set[str]
    gate_name: str
    label: str
    creator_alias: str | None = None

    @property
    def filename_glob(self) -> str:
        """Non-recursive glob matching every image this gate can write."""
        return f"swing-pre-{self.filename_stem}-migration-*.db"


# THE gate table (D50). A gate fires exactly when ``current_version ==
# pre_version AND target_version >= pre_version + 1`` -- strict equality on the
# PRE version, ``>=`` on the target -- and that predicate is written ONCE, in
# ``_run_pre_migration_gate``. Ungated pre-versions: 14 and 17 (no gate was ever
# wired for 0015 or 0018). Ascending pre_version, which is the call order the
# 23 hand-written calls in ``run_migrations`` had.
_PRE_MIGRATION_BACKUP_GATES: tuple[BackupGateSpec, ...] = (
    BackupGateSpec(13, "phase7", PHASE7_EXPECTED_TABLES,
                   "_phase7_backup_gate", "pre-Phase-7",
                   creator_alias="_create_pre_migration_backup"),
    BackupGateSpec(15, "phase8", PHASE8_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase8_backup_gate", "pre-Phase-8"),
    BackupGateSpec(16, "phase9", PHASE9_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase9_backup_gate", "pre-Phase-9"),
    BackupGateSpec(18, "phase12-bundle-c", PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase12_bundle_c_backup_gate", "pre-Phase-12-Sub-bundle-C"),
    BackupGateSpec(19, "phase13", PHASE13_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase13_backup_gate", "pre-Phase-13"),
    BackupGateSpec(20, "phase13-sb6c", PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase13_sb6c_backup_gate", "pre-Phase-13-SB6c"),
    BackupGateSpec(21, "phase14", PHASE14_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase14_backup_gate", "pre-Phase-14"),
    BackupGateSpec(22, "phase14-sb3", PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase14_sb3_backup_gate", "pre-Phase-14-SB3"),
    BackupGateSpec(23, "b7", B7_PRE_MIGRATION_EXPECTED_TABLES,
                   "_b7_backup_gate", "pre-B7"),
    BackupGateSpec(24, "phase16", PHASE16_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase16_backup_gate", "pre-phase16"),
    BackupGateSpec(25, "broad-watch-baseline", BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES,
                   "_broad_watch_baseline_backup_gate", "pre-broad-watch"),
    BackupGateSpec(26, "entry-intent", ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES,
                   "_entry_intent_backup_gate", "pre-entry-intent"),
    BackupGateSpec(27, "watchlist-pin", WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES,
                   "_watchlist_pin_backup_gate", "pre-watchlist-pin"),
    BackupGateSpec(28, "cash-recon", CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES,
                   "_cash_recon_backup_gate", "pre-cash-recon"),
    BackupGateSpec(29, "phase18-arc-c", PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase18_arc_c_backup_gate", "pre-phase18-arc-c"),
    BackupGateSpec(30, "phase18-arc-h6", PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase18_arc_h6_backup_gate", "pre-phase18-arc-h6"),
    BackupGateSpec(31, "phase21-arc-a", PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase21_arc_a_backup_gate", "pre-phase21-arc-a",
                   creator_alias="_create_pre_phase21_arc_a_migration_backup"),
    BackupGateSpec(32, "phase21-arc-b", PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase21_arc_b_backup_gate", "pre-phase21-arc-b",
                   creator_alias="_create_pre_phase21_arc_b_migration_backup"),
    BackupGateSpec(33, "h1-amendment", H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES,
                   "_h1_amendment_backup_gate", "pre-h1-amendment",
                   creator_alias="_create_pre_h1_amendment_migration_backup"),
    BackupGateSpec(34, "a4-taxonomy", A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES,
                   "_a4_taxonomy_backup_gate", "pre-a4-taxonomy"),
    BackupGateSpec(35, "demand-c", DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES,
                   "_demand_c_backup_gate", "pre-demand-c"),
    BackupGateSpec(36, "22a", PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase22_arc_a_backup_gate", "pre-22-A"),
    BackupGateSpec(37, "22a4", PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES,
                   "_phase22_arc_a4_backup_gate", "pre-22-A4"),
)
_GATE_BY_PRE_VERSION: dict[int, BackupGateSpec] = {
    s.pre_version: s for s in _PRE_MIGRATION_BACKUP_GATES
}


def backup_gate_for_pre_version(pre_version: int) -> BackupGateSpec | None:
    """The gate a migration starting at ``pre_version`` fires, or ``None``.

    Read from the table ``run_migrations`` iterates, so a caller (the
    ``db-migrate`` CLI) decides whether a gate covers a transition from the
    same single source. A returned spec fires for any ``target_version >=
    pre_version + 1``; whether there is a transition at all is the caller's
    check."""
    return _GATE_BY_PRE_VERSION.get(pre_version)


def _create_gate_backup(
    src_path: Path, *, dest_dir: Path | None = None, filename_stem: str,
) -> Path:
    """Create a SQLite-native consistent-snapshot backup of ``src_path`` named
    ``swing-pre-<filename_stem>-migration-<UTC>Z.db`` in ``dest_dir``
    (``src_path.parent`` when ``None``).

    Uses ``sqlite3.Connection.backup()`` (transactional, consistent under live
    writers). ``shutil.copy2()`` is NOT acceptable per spec §12.1 -- a
    filesystem-level copy of a live SQLite DB can yield a torn snapshot.
    """
    if dest_dir is None:
        dest_dir = src_path.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-{filename_stem}-migration-{timestamp}.db"
    # NO-CLOBBER: the name is second-granular, and connect()+backup() onto an
    # existing file OVERWRITES it -- possibly the only pre-image of a schema
    # version. Reserve the name by exclusive create; an occupied name raises
    # FileExistsError (an OSError), which the gate turns into a refusal BEFORE
    # any migration runs.
    with open(backup_path, "xb"):
        pass
    try:
        src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
        try:
            dest_conn = sqlite3.connect(backup_path)
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            src_conn.close()
    except BaseException:
        # Remove only the file THIS attempt reserved and partially wrote.
        with contextlib.suppress(OSError):
            backup_path.unlink(missing_ok=True)
        raise
    return backup_path


def _bind_creator_alias(pre_version: int):
    """A legacy creator name as an alias of ``_create_gate_backup``, its stem
    read from the row (not retyped)."""
    spec = _GATE_BY_PRE_VERSION[pre_version]
    stem = spec.filename_stem

    def creator(src_path: Path, *, dest_dir: Path | None = None) -> Path:
        return _create_gate_backup(src_path, dest_dir=dest_dir, filename_stem=stem)

    creator.__name__ = creator.__qualname__ = str(spec.creator_alias)
    creator.__doc__ = (
        f"Alias of _create_gate_backup bound to the v{pre_version} row's stem "
        f"({stem!r})."
    )
    return creator


# The four legacy creator names existing tests call or patch. The other 19
# per-gate creators had no reference outside their own gate and were deleted.
_create_pre_migration_backup = _bind_creator_alias(13)
_create_pre_phase21_arc_a_migration_backup = _bind_creator_alias(31)
_create_pre_phase21_arc_b_migration_backup = _bind_creator_alias(32)
_create_pre_h1_amendment_migration_backup = _bind_creator_alias(33)


def _run_pre_migration_gate(
    spec: BackupGateSpec,
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """THE backup-before-migrate gate body (spec §12.1), shared by every row.

    Fires ONLY when ``current_version == spec.pre_version AND target_version
    >= spec.pre_version + 1``. STRICT EQUALITY on the PRE version (never
    ``current_version <= N`` -- the original bug) and ``>=`` on the target
    (never ``== N + 1``, which would skip the pre-image for an installation
    jumping straight to a later head). The shorthand ``pre_version == (target -
    1)`` is NOT this condition: it diverges at ``target_version >= N + 2``.

    INTENTIONAL NARROWNESS (accepted; carried from the Phase 12 Sub-bundle C
    gate, Codex R1 Major #1): the predicate is evaluated ONCE per gate at
    ``run_migrations`` entry against the INITIAL ``current_version``, not before
    each individual migration. A DB below a gate's pre-version walking past it
    does not fire that gate; only the gate for the starting version fires.
    Per-version firing is a banked V2 candidate (plan section I), not
    implemented here. An operator who skipped a phase takes a manual one-off
    ``sqlite3.Connection.backup()``.

    A file-backed source is required. On backup creation or verification
    failure (``OSError`` / ``sqlite3.Error``) the gate raises
    ``MigrationBackupRequiredException`` so the runner refuses to migrate and
    the source DB is unchanged. ``backup_dir=None`` falls back to the source
    DB's parent directory.
    """
    if current_version != spec.pre_version or target_version < spec.pre_version + 1:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            f"{spec.label} backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        if spec.creator_alias is None:
            backup_path = _create_gate_backup(
                src_path, dest_dir=backup_dir, filename_stem=spec.filename_stem)
        else:
            backup_path = globals()[spec.creator_alias](src_path, dest_dir=backup_dir)
        _verify_backup_integrity(backup_path, expected_tables=spec.expected_tables)
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"{spec.label} backup failed: {exc}"
        ) from exc


def _bind_gate_wrapper(pre_version: int):
    """A module-level gate name as a one-line wrapper bound to ITS row. The
    wrapper carries no predicate; ``backup_gate_spec`` exposes the row so the
    closure test can prove the binding."""
    spec = _GATE_BY_PRE_VERSION[pre_version]

    def gate(
        conn: sqlite3.Connection,
        *,
        current_version: int,
        target_version: int,
        backup_dir: Path | None,
    ) -> None:
        _run_pre_migration_gate(
            spec, conn, current_version=current_version,
            target_version=target_version, backup_dir=backup_dir,
        )

    gate.__name__ = gate.__qualname__ = spec.gate_name
    gate.__doc__ = (
        f"Pre-migration backup gate for the v{pre_version} -> v{pre_version + 1} "
        f"crossing (image stem {spec.filename_stem!r}); body: "
        "_run_pre_migration_gate."
    )
    gate.backup_gate_spec = spec  # type: ignore[attr-defined]
    return gate


# The 23 gate NAMES survive (tests call and patch them); each is bound to its
# row. ``run_migrations`` does NOT call these names from a list -- it iterates
# the table and resolves ``spec.gate_name`` by module attribute at call time.
_phase7_backup_gate = _bind_gate_wrapper(13)
_phase8_backup_gate = _bind_gate_wrapper(15)
_phase9_backup_gate = _bind_gate_wrapper(16)
_phase12_bundle_c_backup_gate = _bind_gate_wrapper(18)
_phase13_backup_gate = _bind_gate_wrapper(19)
_phase13_sb6c_backup_gate = _bind_gate_wrapper(20)
_phase14_backup_gate = _bind_gate_wrapper(21)
_phase14_sb3_backup_gate = _bind_gate_wrapper(22)
_b7_backup_gate = _bind_gate_wrapper(23)
_phase16_backup_gate = _bind_gate_wrapper(24)
_broad_watch_baseline_backup_gate = _bind_gate_wrapper(25)
_entry_intent_backup_gate = _bind_gate_wrapper(26)
_watchlist_pin_backup_gate = _bind_gate_wrapper(27)
_cash_recon_backup_gate = _bind_gate_wrapper(28)
_phase18_arc_c_backup_gate = _bind_gate_wrapper(29)
_phase18_arc_h6_backup_gate = _bind_gate_wrapper(30)
_phase21_arc_a_backup_gate = _bind_gate_wrapper(31)
_phase21_arc_b_backup_gate = _bind_gate_wrapper(32)
_h1_amendment_backup_gate = _bind_gate_wrapper(33)
_a4_taxonomy_backup_gate = _bind_gate_wrapper(34)
_demand_c_backup_gate = _bind_gate_wrapper(35)
_phase22_arc_a_backup_gate = _bind_gate_wrapper(36)
_phase22_arc_a4_backup_gate = _bind_gate_wrapper(37)


def run_migrations(
    conn: sqlite3.Connection,
    *,
    target_version: int = EXPECTED_SCHEMA_VERSION,
    backup_dir: Path | None = None,
) -> None:
    """Apply pending SQL migrations on ``conn`` up to ``target_version``.

    Phase 7 spec §12.1 backup gate: when migrating to ``target_version >= 14``
    from a pre-14 DB, take a SQLite-native ``Connection.backup()`` snapshot
    and verify integrity BEFORE applying any migration. If the backup or
    verification fails, raise ``MigrationBackupRequiredException`` and leave
    the source DB unchanged.

    Note: target_version semantics — this runner only applies migrations
    whose version number is ``<= min(target_version, EXPECTED_SCHEMA_VERSION)``.
    Passing ``target_version=14`` before migration 0014 is registered fires
    the backup gate (correct per spec) but does not actually advance past
    EXPECTED_SCHEMA_VERSION; the gate is "ready" for T2 to land 0014.
    """
    current = _current_version(conn)
    if current >= target_version:
        return

    # Every gate row, resolved BY MODULE ATTRIBUTE at call time (never a bound
    # list): the table is the single source, and a future row is called by
    # construction. At most one row fires (strict equality on the INITIAL
    # ``current``); a refusing gate raises before any migration is applied.
    for spec in _PRE_MIGRATION_BACKUP_GATES:
        globals()[spec.gate_name](
            conn,
            current_version=current,
            target_version=target_version,
            backup_dir=backup_dir,
        )

    apply_ceiling = min(target_version, EXPECTED_SCHEMA_VERSION)
    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for mig in migration_files:
        try:
            version = int(mig.stem.split("_", 1)[0])
        except ValueError:
            continue
        if current < version <= apply_ceiling:
            if version == 4:
                _preflight_migration_0004(conn)
            _apply_migration(conn, mig)

    final_version = _current_version(conn)
    if (
        target_version <= EXPECTED_SCHEMA_VERSION
        and final_version != target_version
    ):
        raise RuntimeError(
            "Migration ran but schema_version did not reach expected value."
        )


def ensure_schema(
    db_path: Path, *, backup_dir: Path | None = None,
) -> sqlite3.Connection:
    """Create or upgrade the DB schema. Use from the CLI migrate command, NOT from app startup.

    ``backup_dir`` is where a firing pre-migration backup gate writes its image
    (D32: the CLI passes ``cfg.paths.backups_dir``). ``None`` keeps the gate's
    own default, the DB's parent directory, for every other caller.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_connection(db_path, reaffirm_wal=True)
    # busy_timeout + foreign_keys + WAL are applied by open_connection (WAL FIRST
    # covered by busy_timeout).
    current = _current_version(conn)
    if current == EXPECTED_SCHEMA_VERSION:
        return conn
    if current > EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatchError(
            f"DB schema version {current} newer than code ({EXPECTED_SCHEMA_VERSION}). "
            "Update the swing package."
        )

    try:
        run_migrations(
            conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=backup_dir,
        )
    except Exception:
        conn.close()
        raise
    return conn


def connect(
    db_path: Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
) -> sqlite3.Connection:
    """Open a connection for normal app use. Raises if schema is not current.

    WAL is NOT reaffirmed here -- the DB only reaches a current schema via
    ensure_schema, which sets WAL persistently (file-header property), so every
    DB connect() ever opens is already WAL. Reaffirming on the hot path buys
    nothing and adds a lock point (OQ-0 / R1 major #1).
    """
    if not db_path.exists():
        raise SchemaVersionMismatchError(
            f"DB not found at {db_path}. Run: swing db-migrate"
        )
    conn = open_connection(db_path, busy_timeout_ms=busy_timeout_ms, reaffirm_wal=False)
    current = _current_version(conn)
    if current != EXPECTED_SCHEMA_VERSION:
        conn.close()
        raise SchemaVersionMismatchError(
            f"DB schema version {current}, code expects {EXPECTED_SCHEMA_VERSION}. "
            "Run: swing db-migrate"
        )
    return conn
