-- Migration 0029 (Phase 16 / Arc 4b+4c): routine cash reconciliation.
-- (1) cash_movements rebuild: widen kind CHECK 2->5, add ISO-date GLOB
--     CHECK, normalize the 3 legacy M/D/YY rows to ISO + strip row 1's
--     stray leading-quote ref (one-time sanctioned data fix). ux_cash_ref
--     recreated verbatim (Codex R1 M#1).
-- (2) account_equity_snapshots: add `basis` discriminator (backfill 'net_liq')
--     + widen the date/source uniqueness index to include basis (Codex R3 M#1).
-- gotcha #9: explicit BEGIN; ... COMMIT; (executescript autocommit). The
-- runner's _apply_migration wraps in try/except + holds foreign_keys=OFF so
-- the cash_movements rebuild does NOT cascade-null reconciliation_discrepancies.
BEGIN;

-- ---- (1) cash_movements rebuild --------------------------------------------
CREATE TABLE cash_movements_new (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  kind TEXT NOT NULL CHECK (kind IN ('deposit','withdraw','interest','dividend','fee')),
  amount REAL NOT NULL CHECK (amount >= 0),
  ref TEXT,
  note TEXT
);

-- Copy with in-transit normalization. ISO rows pass through; the three known
-- legacy M/D/YY rows are pinned to their exact ISO targets (spec §7.1 sanctions
-- pinning to the three known shapes); any OTHER non-ISO row falls through
-- unchanged to the ELSE and is caught by the GLOB CHECK on cash_movements_new
-- during THIS copy INSERT (abort = safe-fail).
INSERT INTO cash_movements_new (id, date, kind, amount, ref, note)
SELECT
  id,
  CASE date
    WHEN '3/30/26' THEN '2026-03-30'
    WHEN '4/29/26' THEN '2026-04-29'
    WHEN '5/10/26' THEN '2026-05-10'
    ELSE date
  END AS date,
  kind,
  amount,
  -- Strip ONLY the one known stray-quote ref (row 1). Pinning the exact value
  -- (not a general LIKE '"%' strip) avoids silently mutating any other ref that
  -- might one day begin with a quote (Codex R1 MINOR).
  CASE WHEN ref = '"115520131470' THEN '115520131470' ELSE ref END AS ref,
  note
FROM cash_movements;

-- SANITY GATE = the GLOB CHECK on cash_movements_new ITSELF. Any row whose date
-- the CASE did NOT normalize to ISO (i.e. an unexpected non-ISO shape that fell
-- through the ELSE) FAILS the GLOB CHECK during THIS copy INSERT -> the statement
-- raises -> _apply_migration's try/except rolls the whole migration back (stays
-- v28, table untouched). This is the safe-fail abort; no separate planted-row
-- gate is needed (Codex R2 MINOR -- the planted-row block was unreachable: the
-- copy already aborts before any post-copy assertion could run).

DROP TABLE cash_movements;
ALTER TABLE cash_movements_new RENAME TO cash_movements;
CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL;

-- ---- (2) account_equity_snapshots.basis ------------------------------------
ALTER TABLE account_equity_snapshots
  ADD COLUMN basis TEXT NOT NULL DEFAULT 'net_liq'
  CHECK (basis IN ('net_liq','cash'));

DROP INDEX ux_account_equity_snapshots_date_source;
CREATE UNIQUE INDEX ux_account_equity_snapshots_date_source_basis
  ON account_equity_snapshots (snapshot_date, source, basis);

UPDATE schema_version SET version = 29;
COMMIT;
