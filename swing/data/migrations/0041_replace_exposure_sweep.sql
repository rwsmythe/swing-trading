-- 0041_replace_exposure_sweep.sql -- Arc 22-I (the REPLACE-exposure sweep).
--
-- This migration ADDS TRIGGERS ONLY, REBUILDS NOTHING: no table, index, view
-- or column is created, altered or rebuilt, and no row is written except the
-- schema_version bump. One transaction, the runner's (`foreign_keys=OFF` at
-- the runner). Bumps schema_version 40 -> 41.
--
-- D60 DECLARATION: pre-existing rows replay unchanged: a trigger does not
-- touch stored rows. Every guard below binds FUTURE statements only; a row
-- already stored at v40 is neither read nor rewritten by this file.
--
-- WHY. A declared append-only / immutability contract with no SQL guard is a
-- WRITER-ABSENCE claim (RD, F-I1): it holds only while nobody writes. At the
-- default `PRAGMA recursive_triggers = 0` (this repo never enables it) an
-- INSERT OR REPLACE deletes the conflicting row WITHOUT firing any DELETE
-- trigger, and a BEFORE INSERT trigger cannot see the statement's conflict
-- algorithm, so a guard is the TRIPLE no_update + no_delete + a
-- conflict-scoped no_replace (the 0037 shape). Every WHEN this file writes is
-- COALESCE-wrapped (a NULL WHEN fails OPEN); every PK clause in a no_replace is
-- `(NEW.<pk> != -1 AND <pk> = NEW.<pk>)` (an omitted INTEGER PRIMARY KEY is -1
-- inside BEFORE INSERT, 0037's measurement).
--
-- ============================================================================
-- REVERSIBILITY HEADER
-- ============================================================================
-- (i) THE GATE: BackupGateSpec(40, "22i", PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES,
--     "_phase22_arc_i_backup_gate", "pre-22-I") in swing/data/db.py, clause
--     `pre_version == 40 AND target_version >= 41`: a database at v40 migrated
--     to any target >= 41 writes the image swing-pre-22i-migration-<UTC>Z.db
--     before this file runs.
--
-- (ii) EVERY OBJECT THIS MIGRATION CREATES, each with its retiring statement:
--
-- ============================================================================

BEGIN;

-- The version bump is the FINAL statement before COMMIT.
UPDATE schema_version SET version = 41;

COMMIT;
