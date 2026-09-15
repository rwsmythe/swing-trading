# Phase 22 — D32 + D50 ledger

**Arc:** the pre-migration backup gates (brief `docs/phase22-arc-d32-d50-backup-gates-dispatch-brief.md` @ `9e18b642`).
**Dispatch authority:** operator pre-authorized, CHARC courier mail `20260915T053025Z`.
**Seat:** orchestrator (generation 2026-09-14 ~18:23 HST). **Base:** `main` @ `e3698f70`.

---

## Round 0 — premise + fork census (orchestrator, no Codex, no cell yet)

Read against `main` @ `e3698f70`: `swing/data/db.py` (gates, `run_migrations`, `ensure_schema`), `swing/cli.py:247-310`
(`db_migrate`), every `tests/`/`scripts/`/`swing/` reference to the gate internals.

### Premises that HOLD

- **23 gates.** Gated pre-versions: **13** (`_phase7_backup_gate`, `db.py:627`, clause written as
  `target < 14 or current >= 14 or current < 13` — equivalent to `current == 13 and target >= 14`, but NOT the
  textual shape of the other 22), then **15, 16, 18, 19 … 37** (`if target_version < N+1 or current_version != N`).
  **Ungated: 14 and 17.** Brief §0's "24 strict-equality clauses" is a count slip; the gates are 23.
- `ensure_schema(db_path)` (`db.py:2324`) calls `run_migrations` with no `backup_dir`; every gate falls back to
  `src_path.parent`. **Its only production caller is `swing/cli.py:310`.**
- The CLI copy (`cli.py:259-270`) is unconditional and runs BEFORE the pre-version snoop (`cli.py:277-291`); the snoop
  already reads the `schema_version` TABLE.
- Every gate evaluates ONCE against the INITIAL `current` (`db.py:2159-2300`).

### Forks / gaps — RULING PACKET (PRIMARY: charc, all items)

**R0-1 (MAJOR) — "23 functions deleted by replacement" contradicts "existing per-migration tests UNCHANGED" (§2 F3 +
§3).** 25 test files outside `db.py` import the per-gate internals: the gate functions (all 23 names referenced), the
`*_PRE_MIGRATION_EXPECTED_TABLES` constants, and four creators (`_create_pre_migration_backup` ×5,
`_create_pre_phase21_arc_a/_arc_b/_h1_amendment_migration_backup`). Decisively,
`tests/data/test_migration_0038_attempt_identity.py:224` **monkeypatches `db_mod._phase22_arc_a4_backup_gate`** to prove
the runner calls the gate and stops on its refusal — a single table-driven function called directly cannot be
intercepted by that patch, so the test either goes red or passes vacuously. The brief's own §3 says a test change is a
fork → stop. Branches:
- **(a) ORCHESTRATOR RECOMMENDS:** one table + one parameterised gate body + one parameterised creator; the 23 gate
  NAMES survive as one-line module-level wrappers bound to their table row, and `run_migrations` iterates the table
  resolving each row's wrapper BY MODULE ATTRIBUTE (so a monkeypatch still intercepts); the expected-tables constants
  stay (the table cites them); the four test-referenced creator names stay as aliases. Tests byte-unchanged; the 23
  hand-copied bodies (the `<=` retype risk D50 is about) are gone.
- (b) delete every name and edit the ~25 test files to the table — the tests stop being the unchanged byte-for-byte
  proof F3(iv) relies on.

**R0-2 — F3 test (iii) describes behaviour the code does not have.** "A fixture at `pre_version - 1` walked to HEAD
fires the gate exactly once at the right step" reads as per-step firing. The runner fires only gates matching the
INITIAL version (the deliberate narrowness documented at `db.py:1300-1333` and `:2106-2112`). From `N-1`, gate `N` does
NOT fire; gate `N-1` fires iff `N-1` is gated (14 and 17 are not). F3 is a refactor. **Recommend:** (iii) asserts the
PRESERVED semantics — from `N-1` → HEAD, the gate for `N` does not fire, exactly the `N-1` gate fires iff gated, zero
otherwise; the `<=` discriminator is kept by that assertion.

**R0-3 — F2(b) on an already-current DB.** Today every no-op `swing db-migrate` (its docstring says "safe to run multiple
times") writes a full CLI copy (~1.5 GB) though nothing migrates. F2(b) read literally — "only for an un-gated
TRANSITION" — takes no copy when there is no transition. **Recommend:** confirm no transition → no copy, echoed as such.

**R0-4 — F2(b) "echo whichever fired, with its path": the gate's path never reaches the CLI.** The gate returns None;
`run_migrations` returns None; `ensure_schema` returns the connection. Branches: (a) thread a return value out through
`run_migrations`/`ensure_schema`; **(b) RECOMMENDED:** `db.py` exposes a lookup `gate for pre_version -> spec | None`
from the table; the CLI uses it both for the F2 decision and, after `ensure_schema`, to find the one new file matching
that row's stem in `backups_dir`. No return-signature change.

**R0-5 — §4 witness step (3) cannot run on the copy.** The live copy is v38 = HEAD; the highest gate is pre-version 37,
so no gate can fire on it. **Recommend:** (3) is a v37 fixture migrated through the REAL CLI (`python -m swing.cli
--config <throwaway> db-migrate`, the throwaway's `db_path` at the fixture and `backups_dir` at a temp dir — NEVER the
live `backups/`, the D43 hazard) showing exactly one gate-named file and no CLI copy; plus `db-migrate` on the v38 COPY
with the same throwaway config showing no backup written (R0-3). (4) the inventory stays read-only against the real root
+ `backups/`.

**R0-6 (minor, for the cell unless ruled otherwise)** — once gates land in `backups/`, the inventory's `swing-*.db` glob
matches BOTH CLI copies (`swing-<ts>.db`) and gate images (`swing-pre-*`); classify by name pattern, and after the F4(a)
move also scan `backups/pre-images/`.

**Cell (after the packet lands):** `implementer-opus-high` (CHARC's minimum; `swing/data` migration-adjacent). Worktree
`.worktrees/d32-d50-exec` off `main` at or above the commit that lands the ruling.
