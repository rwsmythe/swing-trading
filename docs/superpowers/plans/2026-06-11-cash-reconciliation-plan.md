# Routine Cash Reconciliation + Equity Coherence (Phase 16 / Arc 4b+4c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the journal cash ledger UNABLE to silently drift from the broker — auto-ingest ALL Schwab cash types (ref-idempotent, append-only) inside the nightly reconciliation, fix the brittle exact-date matcher to a ±4-day window, add a real ledger-vs-NLV equity-coherence check, and normalize the legacy `M/D/YY` cash rows.

**Architecture:** A new ingest phase (step 6.5) runs INSIDE `run_schwab_reconciliation`'s existing `BEGIN IMMEDIATE` transaction, before the journal→source scan. A pure classifier maps each `SchwabTransactionResponse` to a cash disposition; a dedup ladder (transactionId → ±4d ref-less fallback → INSERT) guarantees idempotency + append-only by construction. The journal→source matcher and the new source→journal direction share ONE ±4-day date-window predicate. An equity-coherence check compares the ledger-computed `current_equity` against the FRESH broker NLV at zero-open-trades, with tolerance `max($5, 0.5% × NLV)`. Migration 0029 rebuilds `cash_movements` (widened kind CHECK + ISO-date CHECK + one-time data normalization) and adds the `basis` discriminator to `account_equity_snapshots`.

**Tech Stack:** Python 3.14, SQLite (migration runner in `swing/data/db.py`), pytest (`-m "not slow"`), Click CLI, FastAPI+HTMX web, schwabdev v3. No new Schwab REST endpoint (L2 lock NOT triggered).

---

## Binding pre-reads (the executing engineer MUST read before Task 1)

- Spec: [`docs/superpowers/specs/2026-06-11-cash-reconciliation-design.md`](../specs/2026-06-11-cash-reconciliation-design.md) — §3 operator decisions, §4 ingestion, §5 matcher, §6 coherence, §7 schema, §9 testing, §10 locks. The plan implements it; do NOT re-litigate.
- CLAUDE.md Gotchas: #9 (`executescript` implicit COMMIT → in-file `BEGIN;…COMMIT;`), #11 (CHECK + constant + validator atomic; grep ALL mirrors), backup-gate STRICT equality `pre_version == target-1`, `INSERT OR REPLACE` cascade hazard, `... or None` vs CHECK nullability, audit-envelope `None`-uniformity, the source-anchor read/write mismatch family, `feedback_regression_test_arithmetic`, `feedback_adversarial_review_verify_data_shapes`.

## Locks propagated verbatim (spec §10) — hold these in every task

- **L2 LOCK: NOT TRIGGERED.** Zero new Schwab REST endpoints. Reuse the EXISTING `get_account_transactions` (`swing/integrations/schwab/trader.py:437`, audit label `accounts.transactions.list`). A different window/params would require signature-pin tests first — do NOT change the wrapper.
- Sandbox → audit rows only; production-only domain writes. Inherited by construction (`run_schwab_reconciliation` is called by `_step_schwab_orders` only under `environment=='production'`).
- `cash_movements` rows are NEVER UPDATEd in place at runtime; the migration-0029 one-time normalization is the SOLE exception. No runtime ref backfill.
- `reconciliation_corrections` APPEND-ONLY — untouched.
- Risk floor `max($7500, actual)` + the sizing denominator resolution semantics intact.
- Phase-isolation carve-out: `swing/trades/schwab_reconciliation.py` (extend) + `swing/trades/equity.py` (the 5-kind `net_cash_movements` arithmetic + the lifted exits-adapter) + `swing/data/` (migration 0029, `models.py`, `repos/cash.py`, `repos/account_equity_snapshots.py`). Also touched (listed non-carve-out surfaces): `swing/integrations/schwab/pipeline_steps.py`, `swing/pipeline/runner.py`, `swing/web/view_models/dashboard.py` + dashboard template, `swing/trades/reconciliation_ambiguity_choices.py`, `swing/trades/reconciliation_auto_correct.py`, web/CLI resolve paths, `swing/cli.py`, `swing/metrics/equity_resolver.py`, `swing/trades/reconciliation_validators.py`, `swing/trades/account_equity_snapshots.py`.
- Conventional commits; ZERO `Co-Authored-By`; no `--no-verify`. Suite baseline **7869** fast tests green.

## STEP 0 — the #11 grep-sweep inventory (resolves §12 item 6; consume in Tasks 1–5)

The `('deposit','withdraw')` kind-vocabulary lives in these mirrors (grepped on the worktree HEAD). All five-kind widenings (Tasks 1–5) form ONE atomic #11 sweep and MUST land in this single arc (they do — one PR):

| Locus | File:line | Audit | Task |
|---|---|---|---|
| SQL CHECK | `swing/data/migrations/0003`:80 → rebuilt in 0029 | service-wide → 5-kind | 1 |
| validator constant | `swing/trades/reconciliation_validators.py:43` `_CASH_MOVEMENT_KINDS` (1 consumer: `validate_cash_movement_correction`:256) | service-wide → 5-kind | 3 |
| model comment / no validator | `swing/data/models.py:382` `CashMovement` (NO `__post_init__` today) | add 5-frozenset + ISO validator | 2 |
| equity arithmetic | `swing/trades/equity.py:17` `net_cash_movements` (1 consumer: `current_equity`:33) | 5-kind + unknown-raise | 4 |
| CLI input | `swing/cli.py:1790-1820` `journal_cash_cmd` | manual-input-allowlist → add `--interest/--dividend/--fee` + ISO validation | 5 |
| Schwab type-set match | `swing/trades/schwab_reconciliation.py:87-92` `_SCHWAB_DEPOSIT_TYPES`/`_SCHWAB_WITHDRAW_TYPES` | extend kind→type mapping | 7 |
| TOS import extractor | `swing/journal/tos_import.py:375` `kind = "deposit" if amount > 0 else "withdraw"` | **AUDITED — intentionally narrow.** TOS CSV cash rows are pure deposit/withdraw by sign; it never needs to emit interest/dividend/fee. Leave unchanged; a comment-line note added in Task 4. | 4 (note only) |

No other Python mirror exists (verified: `net_cash_movements` and `_CASH_MOVEMENT_KINDS` each have exactly one consumer). The executing engineer re-runs the STEP 0 grep at branch start and STOPS if a new mirror appears:
```bash
grep -rn "deposit" swing/ tests/ --include=*.py | grep -i "withdraw"
```

---

## Task 1: Migration 0029 — `cash_movements` rebuild + `account_equity_snapshots.basis` + db.py gate wiring

**Resolves §12 item 1.** Schema v28 → **v29**.

**Files:**
- Create: `swing/data/migrations/0029_cash_reconciliation.sql`
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION` 28→29; add `CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES`, `_create_pre_cash_recon_migration_backup`, `_cash_recon_backup_gate`; register the gate in `run_migrations`)
- Test: `tests/data/test_migration_0029_cash_reconciliation.py`

**GROUNDING CORRECTION (verified against the live DB `~/swing-data/swing.db`, 2026-06-11; the spec §2 amounts/kinds were stale):** the live `cash_movements` 4 rows are:
| id | date (raw) | kind | amount | ref (raw) |
|---|---|---|---|---|
| 1 | `3/30/26` | deposit | 100.0 | `"115520131470` (stray leading quote) |
| 2 | `4/29/26` | deposit | 100.0 | `117872135649` |
| 3 | `5/10/26` | deposit | 600.0 | `118723211591` |
| 4 | `2026-05-28` | deposit | 100.0 | NULL (manual 4a) |
All four are **deposits** (spec §2 mis-stated row 3 as a withdraw and rows 1/3 amounts as $50/$25 — corrected here; the design is unaffected, only the migration test fixtures). schema_version=28; `account_equity_snapshots`=22 rows (3 manual + 19 schwab_api), `basis` column absent. **Live discrepancies 66/67:** both `cash_movement_mismatch`, `field_name='net_amount'`, **`cash_movement_id=4`** (journal-direction; NOT all-NULL FK), `trade_id=NULL`, `resolution='pending_ambiguity_resolution'`, `ambiguity_kind='schwab_returned_no_match'`. (They have `trade_id=NULL`, so the banner-join caveat in Task 9 applies to them as well.)

**Context the engineer needs:**
- The migration runner holds `foreign_keys=OFF` during `_apply_migration` (`db.py:315`), so the `cash_movements` CREATE-copy-DROP-rename does NOT cascade-null `reconciliation_discrepancies.cash_movement_id` (FK `ON DELETE SET NULL`, declared in 0017:243 + 0019:109). IDs are preserved by explicit-column copy. **Note: discrepancy 66/67 carry `cash_movement_id=4` — the id-preserving copy keeps row 4's id=4 so that FK stays valid post-rebuild.**
- `account_equity_snapshots` already carries an ALTER-added `schwab_account_hash` column (0018). ALTER ADD COLUMN `basis` is additive + compatible. The uniqueness index `ux_account_equity_snapshots_date_source` on `(snapshot_date, source)` (0017:339) must DROP + recreate as `(snapshot_date, source, basis)` — index-only, no table rebuild.
- Precedent: the 0023 single-table rebuild (`BEGIN;` … `UPDATE schema_version SET version = 23;` `COMMIT;`) and the 0028 ALTER ADD COLUMN idiom.
- `ux_cash_ref` (0003:85): `CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL;` — recreate VERBATIM post-rename (Codex R1 Major #1).

- [ ] **Step 1: Write the failing migration round-trip test**

Create `tests/data/test_migration_0029_cash_reconciliation.py`. Seed a v28 DB by running migrations to 28, INSERT the 4-row live cash shape + a sample snapshot, then migrate to 29 and assert post-states.

```python
import sqlite3
import pytest
from pathlib import Path
from swing.data import db


def _seed_v28(tmp_path: Path) -> sqlite3.Connection:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    # Pre-migration cash_movements: the REAL live 4-row shape (M/D/YY +
    # stray-quote ref on row 1; row 4 ISO/ref=NULL). The pre-v29 table has
    # the legacy 2-kind CHECK + free-text date, so these INSERTs succeed.
    conn.execute("BEGIN")
    conn.executescript(
        """
        INSERT INTO cash_movements (id, date, kind, amount, ref, note) VALUES
          (1, '3/30/26', 'deposit', 100.0, '"115520131470', 'r1 navy fed'),
          (2, '4/29/26', 'deposit', 100.0, '117872135649', 'r2 navy fed'),
          (3, '5/10/26', 'deposit', 600.0, '118723211591', 'r3 usaa'),
          (4, '2026-05-28', 'deposit', 100.0, NULL, 'r4 manual 4a');
        """
    )
    conn.commit()
    return conn


def test_migration_0029_normalizes_dates_and_strips_quote(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    rows = {
        r[0]: (r[1], r[2], r[3], r[4])
        for r in conn.execute(
            "SELECT id, date, kind, amount, ref FROM cash_movements ORDER BY id"
        )
    }
    # REAL live values (verified vs ~/swing-data/swing.db 2026-06-11).
    assert rows[1] == ("2026-03-30", "deposit", 100.0, "115520131470")  # quote stripped
    assert rows[2] == ("2026-04-29", "deposit", 100.0, "117872135649")
    assert rows[3] == ("2026-05-10", "deposit", 600.0, "118723211591")
    assert rows[4] == ("2026-05-28", "deposit", 100.0, None)  # ISO row untouched
    # id=4 preserved so reconciliation_discrepancies 66/67 (cash_movement_id=4) FK survives.
    assert 4 in rows


def test_migration_0029_widens_kind_check_to_five(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    # Each of the 5 kinds now inserts; an unknown kind still raises.
    for k in ("deposit", "withdraw", "interest", "dividend", "fee"):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-01', ?, 1.0, NULL, NULL)", (k,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-01', 'bogus', 1.0, NULL, NULL)")


def test_migration_0029_iso_date_check_and_glob(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('6/1/26', 'deposit', 1.0, NULL, NULL)")  # non-ISO rejected


def test_migration_0029_aborts_on_unexpected_noniso_shape(tmp_path):
    # A 4th legacy row with an UNPINNED shape must ABORT (safe-fail), not
    # silently pass through. The GLOB sanity gate plants a CHECK-violating row.
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO cash_movements (id, date, kind, amount, ref, note) "
        "VALUES (5, '03/30/26', 'deposit', 1.0, NULL, 'unexpected shape')")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.run_migrations(conn, target_version=29)
    # The migration rolled back: still v28, the table untouched.
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 28


def test_migration_0029_preserves_discrepancy_fk_to_cash_movement(tmp_path):
    # Seed a reconciliation run + a discrepancy referencing cash_movement_id=4
    # (the live 66/67 shape). After the cash_movements rebuild under the
    # runner's foreign_keys=OFF, the FK must still resolve.
    conn = _seed_v28(tmp_path)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO reconciliation_runs (run_id, source, state, started_ts, "
        "period_start, period_end) VALUES (48, 'schwab_api', 'completed', 1, "
        "'2026-05-01', '2026-05-30')")
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (discrepancy_id, run_id, "
        "discrepancy_type, field_name, cash_movement_id, material_to_review, "
        "created_at, resolution) VALUES (66, 48, 'cash_movement_mismatch', "
        "'net_amount', 4, 1, 1, 'pending_ambiguity_resolution')")
    conn.commit()
    db.run_migrations(conn, target_version=29)
    cm_id = conn.execute(
        "SELECT cash_movement_id FROM reconciliation_discrepancies "
        "WHERE discrepancy_id=66").fetchone()[0]
    assert cm_id == 4
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

# NOTE: the two raw INSERTs above must list every NOT-NULL column of the live
# reconciliation_runs / reconciliation_discrepancies schema (the column lists
# here are illustrative). The executing engineer either fills the real NOT-NULL
# set OR uses swing.data.repos.reconciliation.insert_run / insert_discrepancy to
# build the fixture rows — verify against the migrated-to-v28 schema first.


def test_migration_0029_recreates_ux_cash_ref_and_blocks_dup_ref(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='ux_cash_ref'"
    ).fetchone()
    assert idx is not None
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cash_movements (date, kind, amount, ref, note) "
            "VALUES ('2026-06-02', 'deposit', 9.0, '115520131470', 'dup')")


def test_migration_0029_backfills_snapshot_basis_net_liq(tmp_path):
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes) "
        "VALUES ('2026-05-01', 1234.0, 'manual', NULL, '2026-05-01T00:00:00', 'op', NULL)")
    conn.commit()
    db.run_migrations(conn, target_version=29)
    basis = conn.execute(
        "SELECT basis FROM account_equity_snapshots WHERE snapshot_date='2026-05-01'"
    ).fetchone()[0]
    assert basis == "net_liq"


def test_migration_0029_snapshot_basis_index_allows_coexisting_basis(tmp_path):
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29)
    # Same date+source, different basis → BOTH coexist (the widened index).
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes, basis) "
        "VALUES ('2026-06-01', 100.0, 'manual', NULL, 't', 'op', NULL, 'net_liq')")
    conn.execute(
        "INSERT INTO account_equity_snapshots "
        "(snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes, basis) "
        "VALUES ('2026-06-01', 90.0, 'manual', NULL, 't', 'op', NULL, 'cash')")
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots WHERE snapshot_date='2026-06-01'"
    ).fetchone()[0]
    assert n == 2


def test_migration_0029_migrate_twice_is_noop(tmp_path):
    conn = _seed_v28(tmp_path)
    db.run_migrations(conn, target_version=29)
    db.run_migrations(conn, target_version=29)  # second pass — no error, no change
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 29
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/data/test_migration_0029_cash_reconciliation.py -q`
Expected: FAIL — `0029` migration does not exist; `run_migrations(target_version=29)` raises (EXPECTED_SCHEMA_VERSION still 28 → `final_version != target_version`).

- [ ] **Step 3: Write the migration SQL**

Create `swing/data/migrations/0029_cash_reconciliation.sql`.

**Explicit normalization contract (deliberate divergence from the spec §7.1 "defensive general transform" suggestion — Codex R1 MAJOR):** the date CASE pins ONLY the three known live raw shapes (`3/30/26`,`4/29/26`,`5/10/26`) to their ISO targets. ANY other non-ISO `date` value passes through the `ELSE` unchanged and is then caught by the GLOB sanity gate, which ABORTS the migration (safe-fail). This is chosen over a general `M/D/YY` parser because: (a) the live DB contains EXACTLY those three legacy shapes plus the ISO row 4 (verified 2026-06-11) — there is no other shape to normalize; (b) a general `substr/instr` `M/D/YY` parser is fragile + unreadable for a one-time fix; (c) safe-fail-on-unknown (operator investigates) is strictly safer than silent-mutate-on-unknown. The spec §7.1 explicitly delegates "the writing-plans phase writes the exact SQL" and pins only the EXPECTED post-states (which this matches). A migration test asserts an unexpected shape ABORTS rather than silently passing.

```sql
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
-- unchanged to the ELSE and is caught by the GLOB sanity gate below (abort).
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
-- through the ELSE) FAILS the GLOB CHECK during THIS copy INSERT → the statement
-- raises → _apply_migration's try/except rolls the whole migration back (stays
-- v28, table untouched). This is the safe-fail abort; no separate planted-row
-- gate is needed (Codex R2 MINOR — the planted-row block was unreachable: the
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
```

> **Codex verification target (binding data claim):** the date `CASE` pins the exact three live raw shapes (`3/30/26`,`4/29/26`,`5/10/26`) to their ISO targets. Codex MUST confirm (a) the three pins match the live raw `date` strings verbatim (verified 2026-06-11: yes), (b) row 4's ISO date passes through the ELSE unchanged, (c) any UNEXPECTED non-ISO row fails the `cash_movements_new` GLOB CHECK DURING the copy INSERT → the migration raises + rolls back (the abort path is the CHECK itself, not a planted row), and (d) the ref strip replaces ONLY the exact `'"115520131470'` value (row 1), leaving all other refs untouched.

- [ ] **Step 4: Wire the db.py backup gate + bump EXPECTED_SCHEMA_VERSION**

In `swing/data/db.py`:

1. `EXPECTED_SCHEMA_VERSION = 28` → `EXPECTED_SCHEMA_VERSION = 29`.
2. After `WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES` (~line 247), add (0029 adds NO new table — cash_movements rebuild + basis ALTER only — so the v28 table set equals the v27 set):
```python
# 0029 (cash reconciliation) rebuilds cash_movements + ALTERs
# account_equity_snapshots — NO new table — so the pre-v29 (v28) table set is
# identical to the watchlist-pin pre-migration set.
CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES
)
```
3. After `_create_pre_watchlist_pin_migration_backup` add a mirror helper `_create_pre_cash_recon_migration_backup` (filename `swing-pre-cash-recon-migration-<ISO>.db`), copying the `_create_pre_watchlist_pin_migration_backup` body verbatim with the new filename.
4. After `_watchlist_pin_backup_gate` add:
```python
def _cash_recon_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Cash-reconciliation (0029) backup-before-migrate gate.

    Fires ONLY when ``current_version == 28 AND target_version >= 29`` -- a real
    production v28 DB about to cross v29. STRICT EQUALITY on pre_version per the
    ``pre_version == (target - 1)`` gotcha (NOT ``<=``); multi-version jumps from
    pre-v28 baselines bypass this gate by design.
    """
    if target_version < 29 or current_version != 28:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-cash-recon backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_cash_recon_migration_backup(
            src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-cash-recon backup failed: {exc}"
        ) from exc
```
5. In `run_migrations`, after the `_watchlist_pin_backup_gate(...)` call (~line 1427), add the `_cash_recon_backup_gate(conn, current_version=current, target_version=target_version, backup_dir=backup_dir)` call.

- [ ] **Step 5: Add the backup-gate strict-equality test**

Append to the test file:
```python
def test_migration_0029_backup_gate_strict_equality(tmp_path):
    # A v28 file-backed DB fires the gate (writes a backup); a v27→v29 multi-step
    # walk bypasses it (strict ==28). Mirror the prior gates' test shape:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=28)
    conn.close()
    backups_before = list(tmp_path.glob("swing-pre-cash-recon-migration-*.db"))
    assert backups_before == []
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29, backup_dir=tmp_path)
    backups_after = list(tmp_path.glob("swing-pre-cash-recon-migration-*.db"))
    assert len(backups_after) == 1
```

- [ ] **Step 6: Run the full test file to verify it passes**

Run: `python -m pytest tests/data/test_migration_0029_cash_reconciliation.py -q`
Expected: PASS (all 8 tests).

- [ ] **Step 7: Commit**

```bash
git add swing/data/migrations/0029_cash_reconciliation.sql swing/data/db.py tests/data/test_migration_0029_cash_reconciliation.py
git commit -m "feat(data): migration 0029 — cash_movements rebuild + snapshot basis (Arc 4b/4c)"
```

---

## Task 2: `models.py` — `CashMovement` 5-kind+ISO validator + `AccountEquitySnapshot.basis`

**Part of the #11 atomic sweep (STEP 0).**

**Files:**
- Modify: `swing/data/models.py` (`CashMovement` ~line 378-386; `AccountEquitySnapshot` ~line 1412-1471)
- Test: `tests/data/test_models_cash_and_snapshot_basis.py`

**Context:** `CashMovement` (models.py:378) has NO `__post_init__` today. `AccountEquitySnapshot` (models.py:1423) HAS one validating `source ∈ _AES_SOURCES` + NaN/inf + ISO date (mirror its house style; `_AES_SOURCES = ("manual","tos_csv","schwab_api")` at line 1412). The `Fill.__post_init__` enum-frozenset pattern (models.py:360) is the house style for enum validation.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from swing.data.models import CashMovement, AccountEquitySnapshot


@pytest.mark.parametrize("kind", ["deposit", "withdraw", "interest", "dividend", "fee"])
def test_cashmovement_accepts_five_kinds(kind):
    CashMovement(id=None, date="2026-06-01", kind=kind, amount=1.0, ref=None, note=None)


def test_cashmovement_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        CashMovement(id=None, date="2026-06-01", kind="bogus", amount=1.0, ref=None, note=None)


@pytest.mark.parametrize("bad", ["6/1/26", "2026-6-01", "abcd-ef-gh", "2026-13-40", "2026/06/01"])
def test_cashmovement_rejects_non_iso_date(bad):
    # Must mirror the migration-0029 SQL GLOB (digit shape) AND reject
    # calendar-invalid — every value here would either fail the GLOB or be a
    # raw IntegrityError if it slipped through (Codex R1 MAJOR).
    with pytest.raises(ValueError, match="date"):
        CashMovement(id=None, date=bad, kind="deposit", amount=1.0, ref=None, note=None)


def test_snapshot_basis_field_validates():
    s = AccountEquitySnapshot(
        snapshot_id=None, snapshot_date="2026-06-01", equity_dollars=100.0,
        source="schwab_api", source_artifact_path=None,
        recorded_at="2026-06-01T00:00:00", recorded_by="op", notes=None,
        basis="net_liq")
    assert s.basis == "net_liq"
    with pytest.raises(ValueError, match="basis"):
        AccountEquitySnapshot(
            snapshot_id=None, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None,
            recorded_at="2026-06-01T00:00:00", recorded_by="op", notes=None,
            basis="bogus")
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/data/test_models_cash_and_snapshot_basis.py -q`
Expected: FAIL (`CashMovement` accepts bogus kind; `AccountEquitySnapshot` has no `basis` param → `TypeError`).

- [ ] **Step 3: Implement**

In `swing/data/models.py`, near `CashMovement` add a module constant + `__post_init__`:
```python
_CASH_MOVEMENT_KINDS = ("deposit", "withdraw", "interest", "dividend", "fee")
```
```python
@dataclass(frozen=True)
class CashMovement:
    id: int | None
    date: str
    kind: str  # 'deposit' | 'withdraw' | 'interest' | 'dividend' | 'fee'
    amount: float
    ref: str | None
    note: str | None

    def __post_init__(self) -> None:
        from datetime import date as _date
        if self.kind not in _CASH_MOVEMENT_KINDS:
            raise ValueError(
                f"kind must be one of {_CASH_MOVEMENT_KINDS}; got {self.kind!r}")
        # Mirror the migration-0029 SQL GLOB '[0-9]{4}-[0-9]{2}-[0-9]{2}' AND
        # calendar validity. date.fromisoformat rejects single-digit months,
        # non-digit chars, and out-of-range month/day — a strict superset of
        # the GLOB, so it NEVER accepts a value the DB CHECK would reject.
        if (
            len(self.date) != 10
            or self.date[4] != "-"
            or self.date[7] != "-"
        ):
            raise ValueError(f"date must be YYYY-MM-DD; got {self.date!r}")
        try:
            _date.fromisoformat(self.date)
        except ValueError as exc:
            raise ValueError(f"date must be a valid YYYY-MM-DD; got {self.date!r}") from exc
```
For `AccountEquitySnapshot`: add `basis: str` as the LAST field (after `notes`; default `"net_liq"` so positional construction at existing call sites stays valid), add a module constant `_AES_BASES = ("net_liq", "cash")`, and add to `__post_init__`:
```python
    basis: str = "net_liq"
```
```python
        if self.basis not in _AES_BASES:
            raise ValueError(
                f"basis must be one of {_AES_BASES}; got {self.basis!r}")
```

> Note: `basis` carries a default so the migration-era / unrelated callers that build `AccountEquitySnapshot` positionally (without basis) do not break; new domain writers stamp it explicitly (Task 3).

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/data/test_models_cash_and_snapshot_basis.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/models.py tests/data/test_models_cash_and_snapshot_basis.py
git commit -m "feat(data): CashMovement 5-kind+ISO validator + AccountEquitySnapshot.basis"
```

---

## Task 3: snapshot `basis` plumbing (repo + service + writers + resolver) + validator constant widening

**Part of the #11 atomic sweep.** Read-path + write-path widen together (CLAUDE.md #11).

**Files:**
- Modify: `swing/data/repos/account_equity_snapshots.py` (`_SELECT_COLUMNS`:28; `_row_to_model`:45; `insert_snapshot`:~58; `upsert_snapshot`:81; `get_latest_snapshot_on_or_before`:130)
- Modify: `swing/trades/account_equity_snapshots.py` (`record_snapshot`:66 — add `basis` param + thread through)
- Modify: `swing/integrations/schwab/pipeline_steps.py:368`, `swing/cli.py:3788`, `swing/web/routes/account.py:151` (each `record_snapshot(...)` call → pass `basis="net_liq"`)
- Modify: `swing/metrics/equity_resolver.py:51` (the `get_latest_snapshot_on_or_before` call → `basis="net_liq"`)
- Modify: `swing/trades/reconciliation_validators.py:43` (`_CASH_MOVEMENT_KINDS` → 5-kind)
- Test: `tests/data/repos/test_account_equity_snapshots_basis.py`, `tests/trades/test_reconciliation_validators_five_kinds.py`

- [ ] **Step 1: Write the failing tests**

`tests/data/repos/test_account_equity_snapshots_basis.py`:
```python
import sqlite3
import pytest
from pathlib import Path
from swing.data import db
from swing.data.repos import account_equity_snapshots as repo


def _v29(tmp_path: Path) -> sqlite3.Connection:
    conn = db.open_connection(tmp_path / "swing.db", reaffirm_wal=True)
    db.run_migrations(conn, target_version=29)
    return conn


def test_insert_and_read_roundtrips_basis(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        sid = repo.insert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None,
            recorded_at="t", recorded_by="op", notes=None, basis="net_liq")
    snap = repo.get_latest_snapshot_on_or_before(conn, asof_date="2026-06-01")
    assert snap.basis == "net_liq"


def test_get_latest_filters_basis_net_liq(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        repo.insert_snapshot(
            conn, snapshot_date="2026-06-02", equity_dollars=50.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="cash")
        repo.insert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
    # basis-filtered read returns the net_liq row even though the cash row is newer.
    snap = repo.get_latest_snapshot_on_or_before(
        conn, asof_date="2026-06-30", basis="net_liq")
    assert snap.snapshot_date == "2026-06-01" and snap.basis == "net_liq"


def test_upsert_conflict_key_includes_basis(tmp_path):
    conn = _v29(tmp_path)
    with conn:
        a = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
        b = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=90.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="cash")
        c = repo.upsert_snapshot(
            conn, snapshot_date="2026-06-01", equity_dollars=110.0,
            source="manual", source_artifact_path=None, recorded_at="t",
            recorded_by="op", notes=None, basis="net_liq")
    assert a != b  # different basis → distinct rows
    assert a == c  # same (date, source, basis) → replaced, same id
```

`tests/trades/test_reconciliation_validators_five_kinds.py`:
```python
from swing.trades.reconciliation_validators import _CASH_MOVEMENT_KINDS


def test_validator_kinds_widened_to_five():
    assert set(_CASH_MOVEMENT_KINDS) == {
        "deposit", "withdraw", "interest", "dividend", "fee"}
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/data/repos/test_account_equity_snapshots_basis.py tests/trades/test_reconciliation_validators_five_kinds.py -q`
Expected: FAIL (`insert_snapshot` has no `basis` param; `_CASH_MOVEMENT_KINDS` is 2-tuple).

- [ ] **Step 3: Implement the repo widening**

In `swing/data/repos/account_equity_snapshots.py`:
- `_SELECT_COLUMNS` → append `, basis`.
- `_row_to_model` → add `basis=row[8]`.
- `insert_snapshot` → add `basis: str` kwarg (no default — callers must stamp) + add `basis` to the INSERT column list + value tuple.
- `upsert_snapshot` → add `basis: str` kwarg; the SELECT predicate becomes `WHERE snapshot_date = ? AND source = ? AND basis = ?` (3-tuple); the INSERT-fallthrough passes `basis=basis`. (The UPDATE branch leaves the conflict columns unchanged.)
- `get_latest_snapshot_on_or_before` → add `basis: str | None = None` kwarg; when non-None, AND `basis = ?` into BOTH the `MAX(snapshot_date)` subquery and the row SELECT.

In `swing/trades/account_equity_snapshots.py:record_snapshot` → add `basis: str = "net_liq"` param; thread it into the `AccountEquitySnapshot(...)` construction (line ~119) AND the `repo.upsert_snapshot(...)` call (line ~133, `basis=basis`).

At the 3 writer call sites, pass `basis="net_liq"` explicitly (spec §7.3 "stamp explicitly"):
- `swing/integrations/schwab/pipeline_steps.py:368` (`source='schwab_api'`)
- `swing/cli.py:3788`
- `swing/web/routes/account.py:151`

In `swing/metrics/equity_resolver.py:51` → `get_latest_snapshot_on_or_before(conn, asof_date=asof_date.isoformat(), basis="net_liq")`.

In `swing/trades/reconciliation_validators.py:43` → `_CASH_MOVEMENT_KINDS = ("deposit", "withdraw", "interest", "dividend", "fee")`.

- [ ] **Step 4: Run the new tests + the snapshot/resolver/account regression set**

Run: `python -m pytest tests/data/repos/test_account_equity_snapshots_basis.py tests/trades/test_reconciliation_validators_five_kinds.py tests/metrics/test_equity_resolver.py tests/web/routes/test_account.py tests/integrations/schwab/test_pipeline_steps.py -q`
Expected: PASS (fix any signature-mismatch fallout in the regression set — every `record_snapshot`/`insert_snapshot`/`upsert_snapshot` caller in `tests/` must pass `basis`).

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/account_equity_snapshots.py swing/trades/account_equity_snapshots.py swing/integrations/schwab/pipeline_steps.py swing/cli.py swing/web/routes/account.py swing/metrics/equity_resolver.py swing/trades/reconciliation_validators.py tests/data/repos/test_account_equity_snapshots_basis.py tests/trades/test_reconciliation_validators_five_kinds.py
git commit -m "feat(data): thread snapshot basis through repo/service/writers + widen validator kinds"
```

---

## Task 4: `equity.py` — 5-kind `net_cash_movements` + the lifted exits-adapter

**Part of the #11 atomic sweep. Resolves §12 item 3 (exits-adapter lift).**

**Files:**
- Modify: `swing/trades/equity.py` (`net_cash_movements`:17; add `_ExitShape` + `list_all_exitshape_via_fills`)
- Modify: `swing/web/view_models/dashboard.py` (delete the local `_ExitShape`:42 + `_list_all_exitshape_via_fills`:58; import from equity.py; the call site at :927 uses the shared name)
- Modify: `swing/journal/tos_import.py:375` (add a one-line note only — STEP 0 audit)
- Test: `tests/trades/test_equity_five_kind.py`, `tests/trades/test_exit_adapter_lift.py`

**Context:** `net_cash_movements` (equity.py:17) currently sums only deposit(+)/withdraw(−) and SILENTLY IGNORES other kinds (the drift hazard). The exits-adapter `_list_all_exitshape_via_fills` (dashboard.py:58) uses LAZY internal imports (`from swing.trades.derived_metrics import ...`) — preserve that to avoid module-load cycles when equity.py hosts it.

- [ ] **Step 1: Write the failing tests**

`tests/trades/test_equity_five_kind.py`:
```python
import pytest
from swing.data.models import CashMovement
from swing.trades.equity import net_cash_movements


def _cm(kind, amount):
    return CashMovement(id=None, date="2026-06-01", kind=kind, amount=amount, ref=None, note=None)


def test_net_cash_movements_five_kinds():
    movements = [
        _cm("deposit", 100.0), _cm("withdraw", 25.0),
        _cm("interest", 3.0), _cm("dividend", 7.0), _cm("fee", 1.0),
    ]
    # +100 -25 +3 +7 -1 = 84
    assert net_cash_movements(movements) == pytest.approx(84.0)


def test_net_cash_movements_unknown_kind_raises():
    bogus = CashMovement.__new__(CashMovement)  # bypass __post_init__ to plant a bad kind
    object.__setattr__(bogus, "kind", "bogus")
    object.__setattr__(bogus, "amount", 5.0)
    with pytest.raises(ValueError, match="unknown cash kind"):
        net_cash_movements([bogus])
```

`tests/trades/test_exit_adapter_lift.py`:
```python
from swing.trades.equity import list_all_exitshape_via_fills, _ExitShape
import swing.web.view_models.dashboard as dash


def test_dashboard_reexports_shared_adapter():
    # The dashboard module must reference the SHARED adapter, not a local dupe.
    assert dash.list_all_exitshape_via_fills is list_all_exitshape_via_fills
    assert not hasattr(dash, "_list_all_exitshape_via_fills") or \
        dash._list_all_exitshape_via_fills is list_all_exitshape_via_fills
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/trades/test_equity_five_kind.py tests/trades/test_exit_adapter_lift.py -q`
Expected: FAIL (`net_cash_movements` ignores interest/dividend/fee + does not raise; `equity.list_all_exitshape_via_fills` does not exist).

- [ ] **Step 3: Implement the 5-kind arithmetic + the lift**

In `swing/trades/equity.py`, replace `net_cash_movements`:
```python
_CASH_ADD_KINDS = frozenset({"deposit", "interest", "dividend"})
_CASH_SUB_KINDS = frozenset({"withdraw", "fee"})


def net_cash_movements(cash_movements: Iterable[CashMovement]) -> float:
    total = 0.0
    for c in cash_movements:
        if c.kind in _CASH_ADD_KINDS:
            total += c.amount
        elif c.kind in _CASH_SUB_KINDS:
            total -= c.amount
        else:
            raise ValueError(f"unknown cash kind {c.kind!r} in net_cash_movements")
    return total
```
Then move `_ExitShape` (the frozen dataclass) + `list_all_exitshape_via_fills` (renamed public, body verbatim from dashboard.py:58 incl. the lazy `from swing.trades.derived_metrics import ...` + the `list_open_trades`/`list_closed_trades`/`list_all_fills` reads done via lazy imports inside the function) into equity.py. Keep the internal imports LAZY (inside the function body) to avoid any import cycle with `swing.web` / `swing.data.repos`.

In `swing/web/view_models/dashboard.py`: delete the local `_ExitShape` + `_list_all_exitshape_via_fills`; add `from swing.trades.equity import list_all_exitshape_via_fills` (and `_ExitShape` if referenced elsewhere in dashboard.py — grep first); update the call site at :927 to `all_exits = list_all_exitshape_via_fills(conn)`. Add a module-level alias `_list_all_exitshape_via_fills = list_all_exitshape_via_fills` ONLY if other dashboard code or tests reference the underscored name (grep `tests/` first; otherwise omit).

In `swing/journal/tos_import.py:375` add a comment:
```python
        # NOTE (Arc 4b #11 audit): TOS-CSV cash rows are pure deposit/withdraw
        # by sign — intentionally narrow; never emits interest/dividend/fee.
        kind = "deposit" if amount > 0 else "withdraw"
```

- [ ] **Step 4: Run the new tests + the dashboard/equity regression set**

Run: `python -m pytest tests/trades/test_equity_five_kind.py tests/trades/test_exit_adapter_lift.py tests/web/view_models/test_dashboard.py tests/trades/test_equity.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/equity.py swing/web/view_models/dashboard.py swing/journal/tos_import.py tests/trades/test_equity_five_kind.py tests/trades/test_exit_adapter_lift.py
git commit -m "feat(trades): 5-kind net_cash_movements + lift exits-adapter into equity.py"
```

---

## Task 5: `cli.py journal cash` — `--interest/--dividend/--fee` + ISO date validation

**Part of the #11 atomic sweep.**

**Files:**
- Modify: `swing/cli.py:1790-1820` (`journal_cash_cmd`)
- Test: `tests/test_cli_journal_cash_kinds.py`

**Context:** Today `journal_cash_cmd` accepts only `--deposit`/`--withdraw` with `(deposit is None) == (withdraw is None)` exactly-one-of. The date is NOT validated (relied on the old free-text column). Post-0029, the column has an ISO GLOB CHECK — a non-ISO `--date` would raise a raw `IntegrityError`; we add a clean `ClickException`.

- [ ] **Step 1: Write the failing tests**

```python
from click.testing import CliRunner
import pytest
from swing.cli import cli  # adjust to the real root group name if different


@pytest.mark.parametrize("flag", ["--interest", "--dividend", "--fee"])
def test_journal_cash_accepts_new_kinds(flag, monkeypatch, tmp_path):
    # ... arrange a migrated DB via the project's CLI test harness/fixture ...
    runner = CliRunner()
    res = runner.invoke(cli, ["journal", "cash", flag, "5", "--date", "2026-06-01"])
    assert res.exit_code == 0


@pytest.mark.parametrize("bad", ["6/1/26", "2026-6-01", "abcd-ef-gh", "2026-13-40"])
def test_journal_cash_rejects_non_iso_date(bad):
    runner = CliRunner()
    res = runner.invoke(cli, ["journal", "cash", "--deposit", "5", "--date", bad])
    assert res.exit_code != 0
    assert "YYYY-MM-DD" in res.output


def test_journal_cash_rejects_two_kinds():
    runner = CliRunner()
    res = runner.invoke(
        cli, ["journal", "cash", "--deposit", "5", "--interest", "5", "--date", "2026-06-01"])
    assert res.exit_code != 0
    assert "exactly one" in res.output.lower()
```

> The executing engineer wires the DB fixture using the project's existing CLI-test pattern (see other `tests/test_cli_*.py` for the `connect`/`ctx.obj["config"]` monkeypatch shape). Compute the assertion both ways per `feedback_regression_test_arithmetic`: pre-fix `--interest` is an unknown option (exit≠0 for the WRONG reason — "no such option"); post-fix it succeeds. The test must distinguish (assert exit_code==0, not just ≠prev).

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_cli_journal_cash_kinds.py -q`
Expected: FAIL (`--interest/--dividend/--fee` are unknown options; non-ISO date not caught).

- [ ] **Step 3: Implement**

Replace the option block + body of `journal_cash_cmd`:
```python
@click.option("--deposit", "deposit", type=float, default=None)
@click.option("--withdraw", "withdraw", type=float, default=None)
@click.option("--interest", "interest", type=float, default=None)
@click.option("--dividend", "dividend", type=float, default=None)
@click.option("--fee", "fee", type=float, default=None)
@click.option("--date", "date_str", required=True, help="YYYY-MM-DD")
@click.option("--ref", default=None)
@click.option("--note", default=None)
def journal_cash_cmd(ctx, deposit, withdraw, interest, dividend, fee, date_str, ref, note):
    """Log a cash movement (deposit/withdraw/interest/dividend/fee)."""
    from swing.data.db import connect
    from swing.data.models import CashMovement
    from swing.data.repos.cash import insert_cash

    _kinds = {
        "deposit": deposit, "withdraw": withdraw,
        "interest": interest, "dividend": dividend, "fee": fee,
    }
    supplied = {k: v for k, v in _kinds.items() if v is not None}
    if len(supplied) != 1:
        raise click.ClickException(
            "Specify exactly one of --deposit/--withdraw/--interest/--dividend/--fee")
    kind, amount = next(iter(supplied.items()))
    if amount <= 0:
        raise click.ClickException(f"--{kind} amount must be > 0; got {amount}")
    from datetime import date as _date
    _ok = len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-"
    if _ok:
        try:
            _date.fromisoformat(date_str)
        except ValueError:
            _ok = False
    if not _ok:
        raise click.ClickException(f"--date must be a valid YYYY-MM-DD; got {date_str!r}")

    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cid = insert_cash(conn, CashMovement(
                id=None, date=date_str, kind=kind, amount=amount, ref=ref, note=note))
    finally:
        conn.close()
    click.echo(f"Cash {kind} #{cid}: ${amount:.2f}{f' ref={ref}' if ref else ''}")
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_cli_journal_cash_kinds.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/test_cli_journal_cash_kinds.py
git commit -m "feat(cli): journal cash --interest/--dividend/--fee + ISO date validation"
```

---

## Task 6: The ingestion core — classifier + dedup ladder + tier-2 source-direction emit (step 6.5)

**Resolves §12 item 2 (real-payload precondition).** This is the heart of 4b.

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (add the classifier `_classify_cash_transaction`, the ingest function `_ingest_cash_transactions`, the source-direction emit helper `_emit_source_direction_cash`, the marker frozensets; call `_ingest_cash_transactions` as step 6.5 inside `run_schwab_reconciliation`)
- Test: `tests/trades/test_schwab_cash_ingestion.py`

**§12 item 2 — REAL-payload precondition for dividend/interest markers (BINDING). Resolution:**
The marker frozensets MUST be seeded from REAL `DIVIDEND_OR_INTEREST` payload descriptions, not invented strings. The capture mechanism, in order of preference:
1. **Preferred — the existing nightly audit artifact.** `_step_schwab_orders` already fetches all 15 `TRANSACTION_TYPES_ALL` over the 30-day lookback every night and the raw payloads pass through `schwab_api_calls` (audit table). During executing, the engineer runs ONE supervised `swing schwab fetch --verify-marketdata` (or inspects the most recent `schwab_api_calls` row body) and greps the captured `DIVIDEND_OR_INTEREST` `description` strings. **The operator must perform this capture step (it touches the live broker account); it is gated in the Task-6 executing checklist as an OPERATOR-ASSISTED step.**
2. **If the live account history contains NO `DIVIDEND_OR_INTEREST` transaction yet** (likely — the account is small/new): ship the marker frozensets EMPTY, every `DIVIDEND_OR_INTEREST` flags tier-2 (the safe default per §4.1), and pin the type-specific tests as **marker-verified-deferred**:
   - The ingestion CODE is present + tested via SYNTHETIC fixtures (a fixture description containing a planted marker classifies; an unknown description flags tier-2).
   - A test `test_dividend_marker_set_is_real_payload_sourced` is added with `@pytest.mark.skip(reason="pending real DIVIDEND_OR_INTEREST payload capture — see plan Task 6 §item-2")` so the deferral is VISIBLE in the suite, not silent.
   - The plan's executing return-report records which branch fired (real markers captured vs empty-shipped-deferred).

This keeps `feedback_adversarial_review_verify_data_shapes` honored: no invented marker strings ship as if real.

**The classifier (`_classify_cash_transaction`) — a PURE function** (no DB, no Schwab calls; the Phase-12 classifier discipline). Returns a small dataclass `CashDisposition(action, kind, flag_reason)` where `action ∈ {'candidate','skip','flag','skip_warn'}`:

| Schwab `type` | Disposition |
|---|---|
| `ACH_RECEIPT`,`WIRE_IN`,`CASH_RECEIPT` | candidate `deposit` |
| `ACH_DISBURSEMENT`,`WIRE_OUT`,`CASH_DISBURSEMENT` | candidate `withdraw` |
| `ELECTRONIC_FUND`,`JOURNAL` | `net_amount>0`→`deposit`; `<0`→`withdraw`; `==0`→skip |
| `DIVIDEND_OR_INTEREST` | `net_amount<0`→flag(`negative_income_amount`); else description→ marker: dividend-marker→`dividend`; interest-marker→`interest`; unrecognized→flag(`unrecognized_income_description`) |
| `TRADE`,`RECEIVE_AND_DELIVER` | skip — BY DESIGN (trade cash already in ledger via realized P&L) |
| `MEMORANDUM`,`MARGIN_CALL`,`MONEY_MARKET`,`SMA_ADJUSTMENT` | skip; if `net_amount!=0` → skip_warn (one warnings_json note) |

**The dedup ladder (`_ingest_cash_transactions`, per candidate, in order):**
1. `find_by_ref(conn, ref=str(transaction_id))` hit → skip (`matched_by_ref`).
2. **Cross-run suppression belt** (§4.3): if a TERMINAL-or-pending source-direction discrepancy already exists for this `transactionId` (the suppression predicate below) → skip ingest + skip re-flag (`pending_suppressed`).
3. Ref-less fallback: among journal rows with `ref IS NULL`, same `kind`, `abs(amount−abs(net_amount)) <= price_tolerance`, `date` within ±4 calendar days INCLUSIVE of `tx.transaction_date`, excluding rows claimed by an earlier candidate THIS run (in-memory `claimed_ids` set). Exactly ONE → skip, NO write, NO ref backfill (`matched_by_fallback`); TWO-PLUS → tier-2 flag (`fallback_multi_match`, envelope carries `candidate_cash_movement_ids`), no write.
4. No match → `insert_cash(CashMovement(date=tx.transaction_date, kind, amount=abs(net_amount), ref=str(transaction_id), note="auto-ingested from Schwab: {description} [reconciliation run {run_id}]"))`.

**The source-direction emit (`_emit_source_direction_cash`)** for flag cases — the `_emit` dedup-key + `{"matched": null}` sole-key contract (§4.3, Codex R1 Major #2 + R2 Major #1):
- `discrepancy_type='cash_movement_mismatch'`, `field_name='missing_journal_row'`, all FK NULL.
- `expected_value_json` = `{"transactionId": str, "date": iso, "type": str, "net_amount": float, "description": <redaction-safe or None>, "flag_reason": <enum>}` plus, for `fallback_multi_match`, `"candidate_cash_movement_ids": [ids]`.
- `actual_value_json` = EXACTLY `{"matched": null}` (sole key — load-bearing; `_extract_source_payload` maps sole-key `{"matched": null}` → None → classifier routes `schwab_returned_no_match`).
- Because `actual_value_json` is the CONSTANT `{"matched": null}` for every source-direction row, `_emit`'s default payload_key collides. Add an `_emit` parameter `dedup_key_override: tuple | None = None`; when provided it REPLACES the `payload_key` slot of the dedup tuple. Source-direction emits pass `dedup_key_override=("missing_journal_row", transaction_id)` so two distinct unmatched transactions in one run produce two rows.

**Cross-run suppression predicate (source→journal, pending OR terminal, keyed on transactionId):** skip the emit AND skip auto-ingest when ANY row exists:
```sql
SELECT 1 FROM reconciliation_discrepancies
WHERE discrepancy_type='cash_movement_mismatch'
  AND field_name='missing_journal_row'
  AND json_extract(expected_value_json, '$.transactionId') = :tx_id
  AND resolution IN ('pending_ambiguity_resolution','operator_resolved_ambiguity',
                     'operator_overridden','acknowledged_immaterial')
LIMIT 1
```
Suppressed emits are COUNTED (`cash_pending_suppressed_count`).

**Placement (step 6.5):** `_ingest_cash_transactions(conn, run_id=..., schwab_transactions=..., price_tolerance=..., cash_warnings=...)` is called INSIDE the `BEGIN IMMEDIATE` block, AFTER step 6 (fill matching, ~line 1038) and BEFORE step 7 (the cash scan at 1040). It returns a counters dict merged into the run `summary`. Because it INSERTs into `cash_movements`, step 7 + the equity check (Task 8) RE-READ `list_cash(conn)` after ingestion.

**Coverage-gap detection (§4.5, Codex R1 MAJOR — concrete this time).** A helper `_detect_coverage_gap(conn, *, period_start, cash_warnings)` runs at the START of step 6.5 (inside the txn). It reads the most-recent COMPLETED `schwab_api` run's `period_end` — the two-read `pipeline_runs` analog; the current run's own row is `state='running'` so it is excluded by construction:
```sql
SELECT period_end FROM reconciliation_runs
WHERE source='schwab_api' AND state='completed' AND finished_ts IS NOT NULL
ORDER BY finished_ts DESC LIMIT 1
```
- Prior `period_end` exists AND `prior_period_end < period_start` (ISO string compare is valid for ISO dates) → a window of transactions was never scanned → append `{"step":"schwab_orders","reason":"coverage_gap","detail":f"coverage_gap: {prior_period_end} .. {period_start}"}` to `cash_warnings` + one `log.warning` line. (The §4.5 backstop is the §6 coherence check; V1 does NOT auto-widen the fetch window — operator runbook step 4, Task 11.)
- No prior completed run (first-ever) → append an INFORMATIONAL note (`reason="coverage_first_run"`), NOT a warning.

- [ ] **Step 1: Write the failing tests** (idempotency, ±4d fallback, TRADE-skip, zero-amount skip, multi-match flag, sole-key shape, within-run dedup, suppression)

```python
# tests/trades/test_schwab_cash_ingestion.py — SYNTHETIC fixtures mirror the
# REAL SchwabTransactionResponse emitter shape (ISO transaction_date, str
# transaction_id, float net_amount, optional description). See spec §9.
import json
from swing.integrations.schwab.models import SchwabTransactionResponse
from swing.trades.schwab_reconciliation import (
    _classify_cash_transaction, _ingest_cash_transactions,
)
# ... DB fixture migrated to v29; helper to run a minimal reconciliation run row ...


def _tx(tid, date, ttype, amt, desc=None):
    return SchwabTransactionResponse(
        transaction_id=str(tid), transaction_date=date, type=ttype,
        net_amount=amt, description=desc)


def test_classifier_trade_skips_by_design():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "TRADE", 500.0))
    assert d.action == "skip"


def test_classifier_zero_amount_electronic_fund_skips():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "ELECTRONIC_FUND", 0.0))
    assert d.action == "skip"


def test_classifier_ach_receipt_is_deposit_candidate():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "ACH_RECEIPT", 100.0))
    assert d.action == "candidate" and d.kind == "deposit"


def test_classifier_unrecognized_dividend_flags_tier2():
    d = _classify_cash_transaction(_tx(1, "2026-06-01", "DIVIDEND_OR_INTEREST", 5.0, "MYSTERY"))
    assert d.action == "flag" and d.flag_reason == "unrecognized_income_description"


def test_ingest_inserts_unmatched_then_is_idempotent(cash_recon_run):
    conn, run_id = cash_recon_run
    txs = [_tx(900001, "2026-06-01", "ACH_RECEIPT", 100.0)]
    c1 = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                   price_tolerance=0.01, cash_warnings=[])
    assert c1["cash_ingested_count"] == 1
    c2 = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                   price_tolerance=0.01, cash_warnings=[])
    assert c2["cash_ingested_count"] == 0 and c2["cash_matched_by_ref_count"] == 1
    n = conn.execute("SELECT COUNT(*) FROM cash_movements WHERE ref='900001'").fetchone()[0]
    assert n == 1  # ZERO duplicates


def test_fallback_matches_refless_row_within_4_days_no_write(cash_recon_run):
    conn, run_id = cash_recon_run
    # Live row-4 analog: manual ISO deposit, ref=NULL on 2026-05-28.
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'manual 4a')")
    # Schwab books the same transfer 1 day off → ±4d fallback matches; NO new row.
    txs = [_tx(900002, "2026-05-29", "ACH_RECEIPT", 100.0)]
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_matched_by_fallback_count"] == 1 and c["cash_ingested_count"] == 0
    assert conn.execute("SELECT COUNT(*) FROM cash_movements").fetchone()[0] == 1


def test_fallback_5_days_off_does_not_match_ingests_new(cash_recon_run):
    conn, run_id = cash_recon_run
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'manual')")
    txs = [_tx(900003, "2026-06-02", "ACH_RECEIPT", 100.0)]  # 5 days off
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_matched_by_fallback_count"] == 0 and c["cash_ingested_count"] == 1


def test_multi_candidate_fallback_flags_tier2_no_write(cash_recon_run):
    conn, run_id = cash_recon_run
    with conn:
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-28','deposit',100.0,NULL,'a')")
        conn.execute("INSERT INTO cash_movements (date, kind, amount, ref, note) "
                     "VALUES ('2026-05-29','deposit',100.0,NULL,'b')")
    txs = [_tx(900004, "2026-05-28", "ACH_RECEIPT", 100.0)]
    c = _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                                  price_tolerance=0.01, cash_warnings=[])
    assert c["cash_flagged_count"] == 1 and c["cash_ingested_count"] == 0
    row = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM reconciliation_discrepancies "
        "WHERE field_name='missing_journal_row'").fetchone()
    exp, act = json.loads(row[0]), json.loads(row[1])
    assert act == {"matched": None}  # sole-key shape (load-bearing)
    assert exp["flag_reason"] == "fallback_multi_match"
    assert sorted(exp["candidate_cash_movement_ids"])  # candidate ids carried


def test_two_unmatched_in_one_run_emit_two_rows(cash_recon_run):
    conn, run_id = cash_recon_run
    txs = [_tx(900005, "2026-06-01", "DIVIDEND_OR_INTEREST", 5.0, "MYSTERY-A"),
           _tx(900006, "2026-06-01", "DIVIDEND_OR_INTEREST", 6.0, "MYSTERY-B")]
    _ingest_cash_transactions(conn, run_id=run_id, schwab_transactions=txs,
                              price_tolerance=0.01, cash_warnings=[])
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies "
        "WHERE field_name='missing_journal_row'").fetchone()[0]
    assert n == 2  # dedup_key_override prevents the {"matched":null} collision


def test_coverage_gap_warns_on_uncovered_span(cash_recon_full):
    # A prior completed schwab_api run ended 2026-05-01; the new run's
    # period_start is 2026-05-20 → a 19-day window was never scanned → warn.
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=1000.0, open_trades=0, broker_positions=[],
        prior_completed_period_end="2026-05-01", period_start="2026-05-20")
    summary = __import__("json").loads(run.summary_json)
    assert any(w.get("reason") == "coverage_gap" for w in summary.get("cash_warnings", []))


def test_no_coverage_gap_when_contiguous(cash_recon_full):
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=1000.0, open_trades=0, broker_positions=[],
        prior_completed_period_end="2026-05-25", period_start="2026-05-20")
    summary = __import__("json").loads(run.summary_json)
    assert not any(w.get("reason") == "coverage_gap" for w in summary.get("cash_warnings", []))
```

> `cash_recon_full` must accept optional `prior_completed_period_end` (seeds a prior `state='completed'` `schwab_api` run row) + `period_start` so the coverage-gap read has a prior row to compare.

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/trades/test_schwab_cash_ingestion.py -q` → FAIL (symbols missing).

- [ ] **Step 3: Implement** the `CashDisposition` dataclass, the marker frozensets (EMPTY-or-real per §item-2), `_classify_cash_transaction`, `_emit`'s `dedup_key_override` param, `_emit_source_direction_cash`, the suppression-predicate helper `_source_direction_suppressed(conn, tx_id)`, the `_detect_coverage_gap(conn, *, period_start, cash_warnings)` helper, and `_ingest_cash_transactions`. Then insert the step-6.5 call in `run_schwab_reconciliation` between line 1038 and 1040, calling `_detect_coverage_gap` FIRST, then `_ingest_cash_transactions`, threading a `cash_warnings: list[dict]` accumulator and merging the returned counters into `summary` (Task 9 wires `summary_json["cash_warnings"]`).

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/trades/test_schwab_cash_ingestion.py -q` → PASS.

- [ ] **Step 5: Add the marker-deferred visibility test + commit**

Add `test_dividend_marker_set_is_real_payload_sourced` with the `@pytest.mark.skip(reason="pending real DIVIDEND_OR_INTEREST payload capture — plan Task 6 §item-2")` (unskipped + real-marker-asserting only if the operator capture in §item-2 yielded real markers).
```bash
git add swing/trades/schwab_reconciliation.py tests/trades/test_schwab_cash_ingestion.py
git commit -m "feat(trades): auto-ingest Schwab cash transactions (ref-idempotent, append-only) as recon step 6.5"
```

---

## Task 7: The matcher fix — shared ±4-day predicate + kind→type-set widening + journal-direction suppression

**Resolves the §5 brittleness + the live 66/67 class.**

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (add `_within_cash_match_window`; rewrite the step-7 scan 1040-1107 to use it + the widened type-set map; add the journal-direction pending-only suppression)
- Test: `tests/trades/test_schwab_cash_matcher_window.py`

**Context:** The exact-date `if tx.transaction_date != cm.date` (line 1079) is the brittleness. ONE shared predicate `_within_cash_match_window(date_a_iso, date_b_iso, days=4)` is used by BOTH the step-7 journal→source scan AND the Task-6 ref-less fallback (the Arc-6 shared-predicate lesson — two impls WILL diverge). Kind→type-set extends: `interest`/`dividend` → `{DIVIDEND_OR_INTEREST}` (sign>0); `fee` → `{DIVIDEND_OR_INTEREST}` (sign<0).

**Regression arithmetic (binding, `feedback_regression_test_arithmetic`):** the run-48/49 scenario — journal `2026-05-28` $100 deposit vs a Schwab `ACH_RECEIPT` $100 booked on a NEIGHBORING date. Compute BOTH paths:
- Pre-fix (exact-date): `tx.transaction_date != cm.date` → no match → emits `cash_movement_mismatch` (this is exactly discrepancies 66/67).
- Post-fix (±4d): matches → NO emit. The test asserts the post-fix run emits ZERO `cash_movement_mismatch` for the 2026-05-28 row.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date
from swing.trades.schwab_reconciliation import _within_cash_match_window


def test_window_inclusive_4_days():
    assert _within_cash_match_window("2026-05-28", "2026-06-01", days=4) is True   # 4 off
    assert _within_cash_match_window("2026-05-28", "2026-06-02", days=4) is False  # 5 off
    assert _within_cash_match_window("2026-05-28", "2026-05-24", days=4) is True   # -4 off


def test_step7_neighbor_date_no_longer_mismatches(cash_recon_full):
    # journal 2026-05-28 $100 deposit; Schwab ACH_RECEIPT $100 on 2026-05-29.
    # Pre-fix: emits cash_movement_mismatch (66/67). Post-fix: ZERO.
    conn, result = cash_recon_full(
        journal_cash=[("2026-05-28", "deposit", 100.0, None)],
        schwab_txs=[("ACH_RECEIPT", "2026-05-29", 100.0)])
    n = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_discrepancies d "
        "JOIN reconciliation_runs r ON d.run_id=r.run_id "
        "WHERE d.discrepancy_type='cash_movement_mismatch' "
        "AND d.field_name='net_amount'").fetchone()[0]
    assert n == 0
```

> `cash_recon_full` is a fixture that runs `run_schwab_reconciliation` end-to-end on a v29 DB with the given journal-cash rows + synthetic Schwab transactions + a flat account payload. Build it from the REAL emitter shapes (spec §9).

- [ ] **Step 2: Run to verify fail** — FAIL (`_within_cash_match_window` missing; exact-date scan still emits).

- [ ] **Step 3: Implement** `_within_cash_match_window` (parse both ISO via `date.fromisoformat`, `abs((a-b).days) <= days`); replace line 1079's exact-date check with it; widen the kind→type-set map to include the income/fee kinds (extend `_SCHWAB_DEPOSIT_TYPES`/`_SCHWAB_WITHDRAW_TYPES` OR add `_SCHWAB_INCOME_TYPES`/the per-kind map — writing-plans picks: add a `_CASH_KIND_TO_SCHWAB_TYPES` dict keyed by the 5 kinds with sign rules). Add the journal-direction pending-only suppression before the `_emit` at 1086:
```sql
-- skip the emit when an OPEN pending already exists for this cm.id
SELECT 1 FROM reconciliation_discrepancies
WHERE discrepancy_type='cash_movement_mismatch' AND cash_movement_id = :cm_id
  AND resolution='pending_ambiguity_resolution' LIMIT 1
```
Counted as `cash_pending_suppressed_count` (shared counter with the source direction).

- [ ] **Step 4: Run to verify pass** — PASS. Also run `tests/trades/test_schwab_reconciliation.py` to confirm the existing journal-direction tests still pass (the widened predicate must not regress the genuine-mismatch cases — a journal row with NO Schwab counterpart in ±4d still emits).

- [ ] **Step 5: Commit**

```bash
git add swing/trades/schwab_reconciliation.py tests/trades/test_schwab_cash_matcher_window.py
git commit -m "fix(trades): ±4-day shared cash match window + income/fee kind mapping + journal-direction suppression"
```

---

## Task 8: Equity coherence — ledger-vs-NLV check (flat-only, tolerance max($5, 0.5%), basis envelope keys)

**Resolves §12 item 5 confirmation (basis envelope keys).**

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (replace step-8 equity_delta 1109-1125 with the ledger-vs-NLV check; add `_cash_coherence_tolerance`)
- Test: `tests/trades/test_schwab_equity_coherence.py`

**Context:** Today's equity_delta compares `get_latest_snapshot_on_or_before(period_end)` (broker NLV) vs fresh broker NLV — broker-vs-broker, ≈0 (spec §2.4). Replace with: `ledger_equity = current_equity(starting_equity=cfg.account.starting_equity, exits=list_all_exitshape_via_fills(conn), cash_movements=list_cash(conn))` computed INSIDE the txn AFTER ingestion, compared against the FRESH `source_nlv` (already at line 743). `run_schwab_reconciliation` does not currently receive `cfg` — pass `starting_equity` in as a new kwarg `starting_equity: float` (sourced by `_step_schwab_orders` from `cfg.account.starting_equity`); signature-additive with a default for test ergonomics is acceptable but the production caller MUST pass it.

**The persisted run-row metadata must move to ledger too (Codex R1 MAJOR — otherwise the broker-vs-broker blind spot survives in `reconciliation_runs`).** Today `journal_equity` is read from `get_latest_snapshot_on_or_before` BEFORE `BEGIN` (line 747) and written at both `insert_run` (`account_equity_journal_dollars=journal_equity`, line 808) AND `update_run_completed` (line 1182) + `equity_delta_dollars` (line 810/1184). The rewrite:
- DROP the pre-BEGIN `journal_snap`/`journal_equity` read + the pre-BEGIN `equity_delta` from the Schwab equity path entirely.
- At `insert_run`: pass `account_equity_journal_dollars=None`, `equity_delta_dollars=None` (the authoritative value is post-ingestion; the run row is updated at completion).
- After ingestion compute `ledger_equity`; compute `coherence_delta = ledger_equity - source_nlv` (only meaningful when flat — but store it regardless for audit).
- At `update_run_completed`: pass `account_equity_journal_dollars=ledger_equity`, `equity_delta_dollars=coherence_delta`.
- The `equity_delta` discrepancy emits only when flat-and-over-tolerance (below), using `ledger_equity`/`source_nlv` + the basis envelope keys.

**Flat-state gate (Codex R1 Major #5):** full-strength check requires BOTH `len(open_trades)==0` AND `len(schwab_positions)==0` (`schwab_positions` from line 849). If journal-flat but broker-positions non-empty → SUPPRESS the check + emit a `warnings_json` orphan-position note (NOT a badge — §6.2). If not flat at all (open journal trades) → no check, no badge.

**Tolerance:** `_cash_coherence_tolerance(nlv) = max(5.00, 0.005 * abs(nlv))`. Emit `equity_delta` when flat AND `abs(ledger − nlv) > tolerance`. Envelopes carry the basis keys (additive — confirmed tolerated by `_pairs_equity_delta` reconciliation_render.py:296 + `_render_pre_resolution_context_equity_delta` reconcile.py:480, both read `equity_dollars` directly):
- `expected_value_json = {"equity_dollars": ledger, "basis": "ledger"}`
- `actual_value_json = {"equity_dollars": nlv, "basis": "net_liq"}`

The existing `EQUITY_DELTA_EMIT_THRESHOLD_DOLLARS` constant is superseded by `_cash_coherence_tolerance` for the schwab path.

- [ ] **Step 1: Write the failing tests** (tolerance arithmetic both sides of the boundary; flat gate; not-flat suppression; orphan-position suppression+warn; basis envelope keys + render tolerance)

```python
import json
from swing.trades.schwab_reconciliation import _cash_coherence_tolerance


def test_tolerance_is_max_of_5_and_half_pct():
    assert _cash_coherence_tolerance(100.0) == 5.0          # 0.5% = 0.50 < 5
    assert _cash_coherence_tolerance(2000.0) == 10.0        # 0.5% = 10 > 5


def test_coherence_silent_within_tolerance(cash_recon_full):
    # FLOOR-binding boundary: ledger 1000.00 vs NLV 995.01 → Δ=$4.99.
    # tolerance = max($5, 0.5%×995.01=$4.975) = $5.00; 4.99 < 5.00 → silent.
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=995.01, open_trades=0, broker_positions=[])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0


def test_coherence_warns_past_tolerance(cash_recon_full):
    # FLOOR-binding boundary: ledger 1000.00 vs NLV 994.99 → Δ=$5.01.
    # tolerance = max($5, 0.5%×994.99=$4.975) = $5.00; 5.01 > 5.00 → emits.
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=994.99, open_trades=0, broker_positions=[])
    row = conn.execute(
        "SELECT expected_value_json, actual_value_json FROM reconciliation_discrepancies "
        "WHERE discrepancy_type='equity_delta'").fetchone()
    assert row is not None
    exp, act = json.loads(row[0]), json.loads(row[1])
    assert exp["basis"] == "ledger" and act["basis"] == "net_liq"


def test_coherence_suppressed_with_open_trade(cash_recon_full):
    conn, _ = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=5000.0, open_trades=1, broker_positions=[("AAPL", 10)])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0  # not flat → no check


def test_coherence_orphan_position_suppresses_and_warns(cash_recon_full):
    # journal-flat but broker has a position → suppress check, warn.
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[], schwab_txs=[],
        nlv=5000.0, open_trades=0, broker_positions=[("AAPL", 10)])
    n = conn.execute("SELECT COUNT(*) FROM reconciliation_discrepancies "
                     "WHERE discrepancy_type='equity_delta'").fetchone()[0]
    assert n == 0
    summary = json.loads(run.summary_json)
    assert any("orphan" in w.get("reason", "") for w in summary.get("cash_warnings", []))


def test_equity_delta_render_tolerates_basis_keys():
    from swing.trades.reconciliation_render import build_compared_pairs
    pairs = build_compared_pairs(
        "equity_delta",
        {"equity_dollars": 1000.0, "basis": "ledger"},
        {"equity_dollars": 1005.0, "basis": "net_liq"})
    assert pairs == [("equity dollars", 1000.0, 1005.0)]


def test_completed_run_stores_ledger_equity_not_stale_snapshot(cash_recon_full):
    # After auto-ingesting a $100 deposit at flat, the completed run row's
    # account_equity_journal_dollars must equal the LEDGER equity (starting +
    # realized + net cash), NOT the pre-run snapshot-derived value (Codex R1 MAJOR).
    conn, run = cash_recon_full(
        starting_equity=1000.0, journal_cash=[],
        schwab_txs=[("ACH_RECEIPT", "2026-05-29", 100.0, "900099")],
        nlv=1100.0, open_trades=0, broker_positions=[])
    row = conn.execute(
        "SELECT account_equity_journal_dollars, equity_delta_dollars "
        "FROM reconciliation_runs WHERE run_id=?", (run.run_id,)).fetchone()
    # ledger = 1000 starting + 0 realized + 100 ingested deposit = 1100.
    assert row[0] == pytest.approx(1100.0)
    assert row[1] == pytest.approx(0.0)  # ledger 1100 - NLV 1100
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement** `_cash_coherence_tolerance`; add `starting_equity` kwarg to `run_schwab_reconciliation`; replace the step-8 block (1109-1125): compute `ledger_equity` (after ingestion), read `open_trades`/`schwab_positions`, apply the flat-gate + orphan-position warn, emit `equity_delta` with the basis envelope keys when flat-and-over-tolerance. Update `_step_schwab_orders` (pipeline_steps.py:577) to pass `starting_equity=cfg.account.starting_equity`.

- [ ] **Step 4: Run to verify pass** — PASS. Run `tests/trades/test_schwab_reconciliation.py` to confirm the prior equity_delta tests are updated/superseded (they asserted the broker-vs-broker shape — update them to the new ledger-vs-NLV contract).

- [ ] **Step 5: Commit**

```bash
git add swing/trades/schwab_reconciliation.py swing/integrations/schwab/pipeline_steps.py tests/trades/test_schwab_equity_coherence.py
git commit -m "feat(trades): ledger-vs-NLV equity coherence check (flat-only, max($5,0.5%) tolerance)"
```

---

## Task 9: Surfacing — #27 plumbing + pipeline.log + dashboard ACCOUNT tile + badge

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (write `summary_json["cash_warnings"]`; one INFO `log` line)
- Modify: `swing/integrations/schwab/pipeline_steps.py` (`_step_schwab_orders` result dict gains `"warnings"` extracted from the returned run's `summary_json["cash_warnings"]`)
- Modify: `swing/pipeline/runner.py` (capture `_step_schwab_orders` result + `run_warnings.extend(result["warnings"])`)
- Modify: `swing/web/view_models/dashboard.py` (`DashboardVM.cash_coherence_badge` field + populate; ACCOUNT-tile NLV secondary line) + the dashboard template
- Test: `tests/integrations/schwab/test_cash_warnings_plumbing.py`, `tests/web/view_models/test_dashboard_cash_badge.py`

**Context (#27, Codex R2 Major #3):** `_step_schwab_orders` returns a dict but `runner.py:976-996` DISCARDS it and passes no `run_warnings`. The fix: `_step_schwab_orders` reads the just-returned `reconciliation_run.summary_json` → `cash_warnings` and returns them in its result dict; the runner captures the result and `run_warnings.extend(...)`. `run_warnings` persists via `lease.release(warnings_json=... if run_warnings else None)` (runner.py:1062 — the `None`-not-`"[]"` audit-envelope discipline).

**Badge (§6.2, Codex R1 Major #6 — exact predicates, DashboardVM-only so no base.html.j2 shared-VM gotcha):** `cash_coherence_badge` renders when EITHER:
1. `SELECT COUNT(*) FROM reconciliation_discrepancies WHERE discrepancy_type='cash_movement_mismatch' AND resolution='pending_ambiguity_resolution'` > 0 (any run), OR
2. the most-recent `state='completed'` `source='schwab_api'` run has `SELECT COUNT(*) ... WHERE run_id=:latest AND discrepancy_type='equity_delta' AND resolution='unresolved'` > 0.

> **Flagged for executing (banner-join caveat — surfaced during grounding):** the existing account-page banner (`swing/metrics/discrepancies.py:list_pending_ambiguities_in_banner_set`) JOINs `trades` and EXCLUDES `trade_id IS NULL` rows. The NEW source-direction `missing_journal_row` pendings (all FK NULL) therefore will NOT appear in that banner or `count_unresolved_material`. The §6.2 dashboard badge (a DIRECT count, no trade join) is the surface that makes them visible. The plan does NOT widen the banner (out of scope; the badge + reconcile page cover it). A test asserts the badge predicate-1 counts a source-direction pending.

**Tile secondary line (§6.2):** the ACCOUNT tile keeps the ledger `current_equity` headline (unchanged formula, now 5-kind) and adds a secondary "Schwab NLV $X (MM-DD)" from `get_latest_snapshot_on_or_before(conn, asof_date=<today>, basis="net_liq")`, rendering a "no snapshot" state gracefully.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/schwab/test_cash_warnings_plumbing.py
def test_step_result_carries_cash_warnings(...):
    # run _step_schwab_orders against a v29 DB with a cash transaction;
    # assert its result dict has a non-empty "warnings" list mirroring
    # summary_json["cash_warnings"].
    ...

def test_runner_persists_cash_warnings_into_pipeline_runs(...):
    # end-to-end: a pipeline run with cash activity persists the entries into
    # pipeline_runs.warnings_json (json-decodes to a list including a cash entry).
    ...
```
```python
# tests/web/view_models/test_dashboard_cash_badge.py
def test_badge_lights_on_pending_source_direction_row(...):
    # insert a missing_journal_row pending (all FK NULL); build DashboardVM;
    # assert vm.cash_coherence_badge is truthy.
    ...

def test_badge_dark_when_no_pendings_and_no_unresolved_equity_delta(...):
    ...
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement** the `summary_json["cash_warnings"]` write + the INFO log line in `run_schwab_reconciliation`; the `_step_schwab_orders` result `"warnings"` extraction; the runner capture+extend; the `DashboardVM.cash_coherence_badge` field (additive, default falsy) + its compute helper + the NLV secondary line; the template badge block (inside the dashboard-only ACCOUNT tile region — verify it does NOT leak into a shared base partial).

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/schwab_reconciliation.py swing/integrations/schwab/pipeline_steps.py swing/pipeline/runner.py swing/web/view_models/dashboard.py swing/web/templates/ tests/integrations/schwab/test_cash_warnings_plumbing.py tests/web/view_models/test_dashboard_cash_badge.py
git commit -m "feat(web): surface cash ingestion/coherence — #27 warnings plumbing + ACCOUNT-tile NLV + badge"
```

---

## Task 10: The no-FK-safe resolve branch + choice-menu wiring

**Resolves §12 item 4.**

**Files:**
- Modify: `swing/trades/reconciliation_ambiguity_choices.py` (add the `source_without_journal` 3-choice menu; add `choice_menu_for_discrepancy(disc)` helper)
- Modify: `swing/trades/reconciliation_auto_correct.py` (add `apply_source_direction_resolution(...)` — a no-FK-safe terminal resolver that NEVER calls `_resolve_affected_target`)
- Modify: `swing/cli.py` (`resolve-ambiguity` + `show-ambiguity` route `missing_journal_row` rows to the new menu+resolver) + `swing/web/routes/reconcile.py` + `swing/web/view_models/reconcile.py` (same)
- Test: `tests/trades/test_source_direction_resolution.py`

**Design (grounded):** Source-direction rows are STAMPED `ambiguity_kind='schwab_returned_no_match'` by the pivot (no pivot change — the classifier-routing test in spec §4.3 stays green). But that menu (`mark_unmatched`+`operator_truth`) routes through `_resolve_affected_target` → RAISES on all-NULL FK. So the resolve surfaces DETECT `discrepancy_type='cash_movement_mismatch' AND field_name='missing_journal_row'` and (a) show `get_choice_menu('source_without_journal')` via `choice_menu_for_discrepancy(disc)`, (b) dispatch to `apply_source_direction_resolution` instead of `apply_tier2_resolution`.

**The 3-choice menu (`source_without_journal`):**
- `acknowledge_not_journal_event` — `requires_custom_value=False`. Terminal, no journal mutation → resolution `acknowledged_immaterial`.
- `record_journal_row` — `requires_custom_value=False`. VERIFYING (Codex R3 M#2 / R4 M#3 / R5 M#1): permitted ONLY when `find_by_ref(transactionId)` returns a row whose `kind` is determinate-equal OR (for `unrecognized_income_description`) DIRECTION-COMPATIBLE (positive `net_amount` → `{interest,dividend}`; negative → `{fee,withdraw}`; general positive → `{deposit,interest,dividend}`, negative → `{withdraw,fee}`), AND `abs(amount−abs(net_amount)) <= 0.01`, AND `date` within ±4d of the envelope date. Any mismatch REJECTS with a specific message; a missing row REJECTS with the kind-appropriate command `swing journal cash --<kind-flag> <amt> --date <iso> --ref <transactionId>` (NOT hardcoded `--deposit`). On success → resolution `operator_resolved_ambiguity`, the verified linkage in `resolution_reason`.
- `matched_existing_row` — `requires_custom_value=True` (`{"cash_movement_id": N}`). The id MUST be in the envelope's `candidate_cash_movement_ids` AND the row must still exist with matching kind/amount. → resolution `operator_resolved_ambiguity`, `resolution_reason="matched_existing_cash_movement_id=<id>"`.

All three are terminal + durable (the §4.3 cross-run suppression treats these terminal states as final for the transactionId).

- [ ] **Step 1: Write the failing tests** (all-3-choices resolve without raising; (b) rejects wrong-amount/wrong-kind/out-of-window/missing; (c) rejects an id outside the candidate list; an acknowledged transactionId neither re-flags NOR auto-ingests next run)

```python
def test_acknowledge_not_journal_event_terminal(source_dir_pending):
    conn, disc_id = source_dir_pending(flag_reason="unrecognized_income_description")
    from swing.trades.reconciliation_auto_correct import apply_source_direction_resolution
    apply_source_direction_resolution(conn, discrepancy_id=disc_id,
                                      choice_code="acknowledge_not_journal_event",
                                      operator_reason="not a ledger event")
    res = conn.execute("SELECT resolution FROM reconciliation_discrepancies "
                       "WHERE discrepancy_id=?", (disc_id,)).fetchone()[0]
    assert res == "acknowledged_immaterial"


def test_record_journal_row_rejects_when_no_matching_ref(source_dir_pending):
    conn, disc_id = source_dir_pending()
    from swing.trades.reconciliation_auto_correct import (
        apply_source_direction_resolution, SourceResolutionRejected)
    import pytest
    with pytest.raises(SourceResolutionRejected, match="swing journal cash"):
        apply_source_direction_resolution(conn, discrepancy_id=disc_id,
                                          choice_code="record_journal_row",
                                          operator_reason="x")


def test_matched_existing_rejects_id_outside_candidate_list(source_dir_pending):
    conn, disc_id = source_dir_pending(
        flag_reason="fallback_multi_match", candidate_ids=[10, 11])
    from swing.trades.reconciliation_auto_correct import (
        apply_source_direction_resolution, SourceResolutionRejected)
    import pytest
    with pytest.raises(SourceResolutionRejected, match="candidate"):
        apply_source_direction_resolution(conn, discrepancy_id=disc_id,
                                          choice_code="matched_existing_row",
                                          operator_custom_payload={"cash_movement_id": 999},
                                          operator_reason="x")


def test_acknowledged_txid_not_reflagged_or_reingested(cash_recon_full):
    # after acknowledge, a second run with the same transactionId emits nothing
    # and ingests nothing (cross-run suppression belt).
    ...
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement** the menu entry, `choice_menu_for_discrepancy`, `SourceResolutionRejected`, `apply_source_direction_resolution` (own SAVEPOINT/transaction discipline mirroring `apply_tier2_resolution`; NEVER calls `_resolve_affected_target`), and the CLI/web routing branch (both `show`/`resolve` surfaces check `field_name=='missing_journal_row'` first). Confirm `_render_pre_resolution_context_cash_movement_mismatch` (reconcile.py:388) reads `expected["amount"]` — for source-direction rows the envelope has NO `amount` key (it has `net_amount`); ADD a source-direction render branch (or map `net_amount`→display) so the pre-resolution context renders. (Grounding flagged: the existing helper reads `expected["amount"]`; a source-direction envelope would `KeyError`. Add a guard/branch.)

- [ ] **Step 4: Run to verify pass** — PASS. Run the web + cli reconcile test suites.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/reconciliation_ambiguity_choices.py swing/trades/reconciliation_auto_correct.py swing/cli.py swing/web/routes/reconcile.py swing/web/view_models/reconcile.py tests/trades/test_source_direction_resolution.py
git commit -m "feat(trades): no-FK-safe source-direction resolve branch + 3-choice menu"
```

---

## Task 11: Full-suite green + ruff + the post-merge operator runbook

**Resolves §12 item 7 (operator disposition of pendings 66/67) — runbook only, NOT code.**

**Files:**
- Create/append: `docs/phase16-todo.md` Arc 4 runbook section (operator-gated post-merge steps)

- [ ] **Step 1: Full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS at **7869 + the new tests** (the 3 banked `-n0` schwab-route flakes are pre-existing — confirm they are the SAME 3, not new). Read the ACTUAL post-merge count (`feedback_no_false_green_claim`).

- [ ] **Step 2: ruff**

Run: `ruff check swing/`
Expected: clean.

- [ ] **Step 3: Write the post-merge operator runbook** (append to `docs/phase16-todo.md`)

```markdown
### Arc 4b/4c post-merge operator-gated runbook (NOT auto-executed)

1. **Migrate the live DB (backup-gated):** `swing db-migrate` (fires the
   v28→v29 `_cash_recon_backup_gate`; verify `swing-pre-cash-recon-migration-*.db`
   written). Confirm `cash_movements` rows 1-3 are ISO + row 1's ref has no
   leading quote; `account_equity_snapshots` all show `basis='net_liq'`.
2. **REAL dividend/interest marker capture (Task 6 §item-2):** run one supervised
   `swing schwab fetch --verify-marketdata` (or inspect the latest
   `schwab_api_calls` body) and record any `DIVIDEND_OR_INTEREST` descriptions.
   If found, file a follow-up to seed the marker frozensets + unskip
   `test_dividend_marker_set_is_real_payload_sourced`. If none, the empty-default
   (everything tier-2-flags) is correct — no action.
3. **Dispose live pendings 66/67 ONCE:** via the existing web tier-2 resolve flow
   (`/reconcile/discrepancy/66/resolve`, `/67`). After the ±4d widening ships the
   2026-05-28 row matches its Schwab transaction; these two are pre-fix audit
   history — resolve them, do NOT bulk-edit or migrate them away.
4. **Coverage-gap catch-up (only if a gap warning fires):** if `pipeline.log`
   shows `coverage_gap: <prev_end> .. <start>`, bump `lookback_days` in
   `~/swing-data/user-config.toml` + run the on-demand `swing schwab fetch` once
   to re-scan the uncovered span, then restore `lookback_days=30`.
5. **First-live-run gate:** confirm the next nightly run writes the cash summary
   line to `pipeline.log`, persists `cash_warnings` into `pipeline_runs.warnings_json`,
   and (at the next flat night) the ACCOUNT tile shows ledger + NLV with the badge
   reflecting any pending/coherence breach.
```

- [ ] **Step 4: Commit**

```bash
git add docs/phase16-todo.md
git commit -m "docs(phase16): Arc 4b/4c post-merge operator runbook"
```

---

## Self-Review (run by the writing-plans author; verified before Codex)

**Spec coverage map:**
- §3 OQ-1 auto-ingest all types → Task 6 classifier table. OQ-2 cadence + #27 + badge → Tasks 6/9. OQ-3 ledger-primary + NLV + tolerance + flat-only → Task 8/9. OQ-4 basis backfill → Task 1. OQ-5 date normalization → Task 1. OQ-6 5 kinds → Tasks 1-5. Match window ±4d → Tasks 6/7. Architecture (inside the txn) → Task 6 step 6.5.
- §4 ingestion (classification, dedup ladder, tier-2 flags, sole-key shape, dedup-key override, suppression, placement, coverage-gap) → Task 6 (+ suppression belt). §4.5 coverage-gap → Task 6 `_detect_coverage_gap` (the prior-completed-run read + the two coverage tests) + Task 9 (warning surfacing). The §6 coherence run-row metadata (account_equity_journal_dollars=ledger) → Task 8.
- §5 matcher fix + exits-adapter lift → Tasks 7 + 4. §6 coherence + tile + badge → Tasks 8 + 9. §7 migration + #11 sweep → Tasks 1-5. §8 audit/surfacing → Task 9. §9 testing posture → every task's discriminators. §10 locks → header + per-task. §11 NOT-list → respected (no fee auto-ingest; no statement parsing; no intraday; no position decomposition). §12 deferred items 1-7 → Tasks 1, 6, 4, 10, 8/9, 0, 11 respectively.

**Placeholder scan:** none — every code step carries real code or an exact locus; the two genuinely operator-gated unknowns (real marker strings; the live 66/67 disposition) are explicitly deferred with a visible-skip test + a runbook, not a silent TODO.

**Type consistency:** `CashDisposition(action, kind, flag_reason)`, `list_all_exitshape_via_fills`, `_within_cash_match_window`, `_cash_coherence_tolerance`, `apply_source_direction_resolution`, `SourceResolutionRejected`, `choice_menu_for_discrepancy`, `cash_coherence_badge`, the `summary_json["cash_warnings"]` channel, and the `dedup_key_override` `_emit` param are used consistently across Tasks 4/6/7/8/9/10.

## Flagged for the executing phase (carry into the executing dispatch)

1. **Migration date-CASE robustness** — Codex must validate the `substr/instr` transform vs the 3 live shapes; fall back to explicit `WHEN`-pins if fragile (Task 1 Step 3 note).
2. **REAL marker capture is operator-assisted** — Task 6 §item-2; ships empty-default + visible-skip if no live payload exists.
3. **`run_schwab_reconciliation` gains a `starting_equity` kwarg** — additive; the production caller (`_step_schwab_orders`) MUST pass `cfg.account.starting_equity` (Task 8).
4. **Banner-join caveat** — source-direction all-NULL-FK pendings are surfaced by the §6.2 badge, NOT the trade-joined account-page banner (Task 9). Confirm this is the accepted V1 surface.
5. **`_render_pre_resolution_context_cash_movement_mismatch` KeyError risk** — it reads `expected["amount"]`; source-direction envelopes carry `net_amount`, not `amount`. Task 10 adds a source-direction render branch.
6. **summary_json round-trip for warnings** — `cash_warnings` is surfaced via the persisted `summary_json` and re-read by `_step_schwab_orders` for the run_warnings channel (Task 9); confirm this indirection is acceptable vs a return-signature change.
7. **`net_cash_movements` now RAISES on unknown kind** — any pre-existing test or fixture planting a non-5-kind CashMovement will surface; audit at Task 4 Step 4.
```

