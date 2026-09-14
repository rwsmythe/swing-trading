# Phase 22 — D32 + D50: the pre-migration backup gates (destination, parameterisation, and a retention INVENTORY)

**Author:** CHARC, 2026-09-14. **Status:** COMMISSIONED — the operator ruled both forks in chat 2026-09-14 ("Concur with your recommendations for both 1 and 2. proceed"): F2 = branch (b); F4 = move-all / delete-only-proven-twins / keep-the-rest. Dispatched. **Executor:** orchestrator → implementer cell (**opus-high minimum**: `swing/data/db.py`, migration-adjacent, a wrong gate is confident and only found at the next live migration).
**Tripwire (harness §5): CROSSED — a `swing/data` carve-out.** CHARC authorizes it, scoped exactly to §3 below. Reviewer A to convergence at the strong tier; **Reviewer B REQUIRED** at the orchestrator's gate (charter §2.9; harness §5.1 B-gate).

---

## §0 READ FIRST (pointers)

1. `docs/tool-director-context.md` §4 rows **D32** (the misplaced pre-images, re-measured 09-09: 31 root pre-images 10.2 GB + 65 CLI copies 22 GB; MOVE-THEN-RETAIN; RD's "last copy of a schema" constraint) and **D50** (23 near-identical gates, 24 strict-equality clauses).
2. `swing/data/db.py` — `run_migrations` (the 23 gate call sites, each `if target_version < N+1 or current_version != N: return` then `_create_pre_<stem>_migration_backup` + `_verify_backup_integrity(expected_tables=<STEM>_PRE_MIGRATION_EXPECTED_TABLES)`), `ensure_schema` (calls `run_migrations` with NO `backup_dir`), and the `backup_dir is None → src_path.parent` default at every gate.
3. `swing/cli.py` `db_migrate` — the UNCONDITIONAL copy to `cfg.paths.backups_dir` (`swing-<local-ts>.db`) taken BEFORE `ensure_schema`; then `ensure_schema(db_path)`.
4. CLAUDE.md §Gotchas: "Migration backup-gate: strict equality on the PRE-version…" (the ONE clause shape, and why `<=` was the bug); "`swing db-migrate` writes TWO backups, not one"; "NEVER open a BACKUP through a code path that reaches `ensure_schema`".
5. `docs/harness-architecture.md` §5.1 the RUNTIME composition read (a migration touched here is exercised only at the next live migration; the witness is the proof).

## §1 THE DEFECTS, measured

- **D32 mechanism, one line:** `ensure_schema(db_path)` → `run_migrations(conn, target_version=…)` with no `backup_dir`, so every gate's `backup_dir = src_path.parent` = the swing-data ROOT, beside the live DB, outside `backups/` and outside any sweep aimed there. Additionally the 0037 gate's mirror wrote into the ROOT even when the migrated file was a COPY (D43 addendum).
- **D50 shape:** 23 hand-copied gate functions + 23 call-site clauses + 23 expected-tables constants, differing only in `N`, the filename stem, and the table set. 23 chances to retype `<=`; a "which backup fires" question costs 23 reads (the D49 undercount was that cost realised).
- **The double copy:** on every witnessed migration since 0038 the CLI copy and the gate copy are the SAME bytes twice (1.5 GB each at v37→38), and only one is echoed.

## §2 FORK CENSUS (both branches stated; CHOSEN branches are CHARC's rulings unless marked OPERATOR)

**F1 — destination. CHOSEN:** the CLI passes `backup_dir=cfg.paths.backups_dir` into `ensure_schema` (new keyword-only param, default `None` preserved for every other caller) → `run_migrations`. Gates land in `backups/`. The `src_path.parent` fallback stays for callers that pass nothing (tests; in-place tools), unchanged. Rejected: changing the gates' own default — it would move the behaviour for every caller at once.

**F2 — the double copy. OPERATOR-RULED 2026-09-14: branch (b).** (a) keep both (belt and braces; 2× DB size per migration); (b) **CHARC RECOMMENDS:** the CLI's unconditional copy is taken ONLY when no gate covers the transition — the gate's copy is strictly better (named by arc, integrity-verified by `_verify_backup_integrity`, UTC-stamped), the CLI copy is the safety net for un-gated migrations; requires the pre-version snoop to run BEFORE the copy (it already runs, after — reorder). The CLI echoes whichever fired, with its path. (c) drop the gate copy when the CLI copied — rejected: it removes the verified, named image.

**F3 — parameterise. CHOSEN:** one table `_PRE_MIGRATION_BACKUP_GATES: tuple[GateSpec, ...]` of `(pre_version, filename_stem, expected_tables)` and ONE gate function that fires when `current_version == pre_version and target_version >= pre_version + 1`; the 23 functions and 23 clauses deleted by replacement; **every filename stem preserved BYTE-FOR-BYTE** (D32's move-then-retain sweep names them; the 0038 witness record cites `swing-pre-22a4-migration-<UTC>Z.db`). Tests: (i) the table covers exactly the 23 pre-versions gated today (enumerate them from `git show HEAD~:swing/data/db.py` in the test's docstring, not from the table under test); (ii) for each row, migrating a fixture DB at `pre_version` to HEAD produces exactly ONE backup whose name matches the stem and passes the integrity check; (iii) a fixture at `pre_version - 1` walked to HEAD fires the gate exactly once at the right step (the multi-step walk; strict equality, not `<=` — the original bug's discriminator); (iv) the D51 precondition: the existing per-migration backup tests keep passing unchanged (they are the byte-for-byte proof).

**F4 — retention of the 31 root pre-images (10.2 GB) + 65 CLI copies (22 GB). OPERATOR-RULED 2026-09-14 as written below; the arc ships an INVENTORY, never a delete.** The arc adds `scripts/backup_inventory.py` (read-only, stdlib): for every `swing-pre-*.db` in the root and every `swing-*.db` in `backups/`, print path · size · mtime · `PRAGMA user_version` (opened with PLAIN `sqlite3` in `mode=ro`, NEVER `swing`'s `connect`) · sha256 · and for each CLI copy whether a gate image exists with the SAME sha256 (the byte-identical twin). Then the disposition, by the operator's hand and witnessed: **(a) MOVE all root pre-images to `backups/pre-images/`** (retain; D32's ruling); **(b) CLI copies with a byte-identical gate twin: DELETE the CLI copy** (the same bytes twice is one copy of retention, not two — provable per file by the hash line); **(c) everything else: KEEP** (RD's constraint: a file may be the sole pre-image of a schema version). No automation deletes; the script's output is the evidence the operator rules on, per file. Rejected: a `db-backups prune` CLI — a standing tool for a one-time disposition is process footprint.

## §3 SCOPE — exactly this, refuse the rest

- `swing/data/db.py`: the gate table + one function replacing 23; `ensure_schema(db_path, *, backup_dir=None)`. NOTHING else in `swing/data/`.
- `swing/cli.py` `db_migrate`: pass `backup_dir`; F2 branch (b) — the CLI copy fires ONLY for an un-gated transition, the pre-version snoop reordered before it; echo whichever fired, with its path.
- `scripts/backup_inventory.py` + its test on a synthetic root.
- Tests per F3. Existing per-migration tests UNCHANGED (the byte-for-byte proof; if one must change, that is a fork — stop and return).
- **REFUSE:** any delete, move, or rename of any file under `~/swing-data/`; any change to a migration SQL file; any change to `_verify_backup_integrity`'s four checks; any change to `connect()`'s schema-version refusal.

## §4 THE WITNESS (the load-bearing gate)

No live migration exists to run, so the witness is on a COPY: (1) copy the live DB (plain file copy, `swing web` stopped, exclusive-lock proof first — the CLAUDE.md idiom); (2) `PRAGMA user_version` on the copy = 38; (3) run the parameterised gate path against the copy at a synthetic transition (the test harness's fixture walk, not a live migration) and show ONE named file in the configured `backups/`; (4) run `backup_inventory.py` against the real root + `backups/` and hand its output to the operator (F4). The temporal clause binds: the first REAL migration after merge (22-B) is the production proof; this arc's ledger says so.

## §5 RETURN (the ORCHESTRATOR posts to `charc,rd` after QA — RD because the disposition touches the sole pre-images of schema versions)

Head SHA; the gate table (23 rows quoted); the A verdict; the B transcript path + verdict + every banked finding with its evidence; the witness outputs (1)–(4); the suite line with SHA; the inventory output path.
