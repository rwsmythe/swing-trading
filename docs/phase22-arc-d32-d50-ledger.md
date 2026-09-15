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

---

## Round 0 RULING — CHARC (PRIMARY, all six), literal block quote

**Author:** CHARC. **Courier:** orchestrator (transcription only). **Source:** `comms/orchestrator/read/20260915T055125Z-charc-d32-d50-round-0-ruling-r0-1-a-r0-2-r0-6.md` (posted 2026-09-15T05:51:25Z). Transcribed as a literal block quote of the message body, headers omitted.

> RULING PACKET -- D32+D50 round 0 (ledger 92b6ffb4). CHARC, PRIMARY on all six.
> One pass. Transcribe as a block quote into the ledger; dispatch off that commit.
> I read the ledger's Round 0, brief 9e18b642 sections 1-4, db.py (run_migrations,
> ensure_schema, the phase7 and 21-A/22-A4 gate bodies, the narrowness docstring
> at db.py:1300-1333), cli.py:247-310 and the 0038 monkeypatch test at :224
> before ruling. Every premise the packet lists as HOLDING, I re-read and it holds.
>
> R0-1 -- RULED (a), with three sharpenings.
>   The D50 defect is 23 hand-copied BODIES and 23 hand-typed PREDICATES. It is
>   not the 23 NAMES. A one-line wrapper bound to a table row carries no predicate
>   and cannot be retyped as <=, so keeping the names costs nothing D50 is about
>   and buys the byte-unchanged test proof that F3(iv) relies on. Branch (b)
>   would edit 25 test files to prove a refactor did not change behaviour, which
>   is the proof destroying its own instrument.
>   (1) run_migrations iterates the TABLE, resolving each row's wrapper by module
>       attribute at call time. It must NOT keep a hard-coded list of 23 calls:
>       then a future row would not be called and the table would not be the
>       single source. The 0038 monkeypatch test (:224) is the reachability test
>       for that resolution -- it stays byte-unchanged and it is what proves the
>       wrappers are wired, not decoration.
>   (2) A closure test, both directions: every module-level `_*_backup_gate` name
>       maps to exactly one table row, and every table row names a wrapper that
>       exists. A row without a wrapper, or a wrapper without a row, goes red.
>       This is the D51 comparator shape (the object set, not the value set).
>   (3) The phase7 gate (pre 13) goes through the same body. Its clause is
>       textually different and logically equivalent; the table row is 13, and
>       test (i) enumerates the 23 from `git show HEAD~:swing/data/db.py` as the
>       brief says, never from the table under test. The four creator names stay
>       as aliases of one parameterised creator; the expected-tables constants
>       stay and the table cites them.
>
> R0-2 -- RULED as recommended. (iii) pins the PRESERVED semantics. The runner
>   evaluates every gate ONCE against the INITIAL version (db.py:1300-1333, the
>   accepted narrowness; the per-version-firing candidate stays banked at plan
>   section I, NOT this arc -- F3 is a refactor and changes no firing rule).
>   The `<=` discriminator, stated so the cell writes the right two cases:
>   from a GATED N-1 walked to HEAD: exactly ONE file, N-1's stem, and NOT N's.
>   From an UNGATED pre-version (14 or 17) walked to HEAD: exactly ZERO files.
>   A `<=` body would fire every gate at or above the start on the second case
>   (from 17: twenty files). The zero case is the sharper discriminator; write
>   both.
>
> R0-3 -- RULED as recommended. No transition, no copy. The CLI echoes that the
>   schema is already at HEAD and that no backup was taken, naming the version
>   read. The pre-18 WARN block is untouched.
>
> R0-4 -- RULED (b), with two sharpenings.
>   (1) The lookup is `gate for pre_version -> spec | None` from the table. The
>       F2 decision is: spec is None AND pre_version < EXPECTED -> the CLI copy;
>       spec present -> no CLI copy. The snoop moves BEFORE the copy.
>   (2) Finding the gate's file: SET-DIFFERENCE of the stem glob in backups_dir
>       taken immediately before and after ensure_schema, non-recursive (after
>       F4(a) `backups/pre-images/` holds old images with the same stems -- a
>       "newest matching" read could name one of those). Exactly one new file ->
>       echo its path. Zero or more than one -> RAISE with the count, never echo
>       nothing: alarm-never-assert at the CLI. The gate itself already refuses
>       on failure, so zero-new-files after a successful ensure_schema is a
>       defect in this arc's wiring, and the CLI must say so.
>
> R0-5 -- RULED as recommended, with the D43 obligation stated.
>   (3) is a v37 fixture through the REAL CLI with a throwaway config. Prefer the
>   fixture to be a plain file COPY of a real v37 pre-image (`swing-pre-22a4-
>   migration-*.db` in the root, 1.5 GB) over the synthetic `_v37`: the witness
>   is about production bytes, and the 0038 m3c test already proved the
>   expected-tables constant is a SUBSET of that real shape. Fall back to the
>   synthetic only if disk is tight (the step needs ~3 GB: copy + gate image);
>   say which was used. Plus `db-migrate` on the v38 COPY with the same throwaway
>   config showing no backup written (R0-3). D43 binds: BEFORE running the real
>   CLI, the cell ENUMERATES every path a `db-migrate` invocation writes under
>   that config (db_path, backups_dir, and anything the CLI's startup touches --
>   logs, comms, exports) and points each at temp or states why it cannot be
>   reached; the ledger records the list. "backups_dir at a temp dir" is one
>   surface, not the enumeration.
>
> R0-6 -- RULED as recommended; the cell's. Classify by name pattern
>   (`swing-pre-*` = gate image; `swing-<14-digit-ts>.db` = CLI copy); a file
>   matching NEITHER prints as `unclassified` with its path, never skipped
>   silently (the #27 class). Scan `backups/pre-images/` after the move.
>
> Cell: implementer-opus-high confirmed. B on the merged tree at my gate as
> usual; the witness on the copy per R0-5; the inventory output to the operator.
> Nothing here is RD's; RD's successor QAs the return on the pre-image
> disposition, per the brief section 5.
