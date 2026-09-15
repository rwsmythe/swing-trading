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

---

## Executing -- Reviewer A

**Cell:** implementer-opus-high. **Worktree:** `.worktrees/d32-d50-exec`, base `eface268`. **Tier:** `strong`
(`codex exec -p strong -s read-only --skip-git-repo-check -C <worktree>`, the cold-audit form with repo read access,
prompt + full `git diff -U8 eface268..HEAD` on stdin; runner `bash run_round.sh N` with literal paths, LF-verified).
Prior-round scratch lived in the session scratchpad for the whole loop; the prompt forbade reading `.codex-*` /
`.copowers-*`; both transcripts were grepped and neither reached for them.

### Round ledger

| Round | Reviewed head | Findings (crit / major / minor as raised) | New vs reopened | Adjudicated | Model | Effort | `^ERROR` | `^tokens used` | Verdict token (anchored) | Exit (measured) | Transcript bytes | Depth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `f0ce201c` | 2 / 4 / 0 | 6 new, 0 reopened | R-1 major (fixed), R-2 major (fixed), R-3 major (fixed), R-4 major (partially accepted: skip->fail), R-5 major (tests added), R-6 minor (fixed) | gpt-5.6-sol | high | 0 | 1 -- 429,974 | NEW_CRITICAL_MAJOR_FOUND x2 (0.152.1 double emit), other token 0 | exit=0, process exited | 1,016,393 | |
| 2 | `cc24f716` | 0 / 0 / 0 | -- | none | gpt-5.6-sol | high | 0 | 1 -- 243,731 | NO_NEW_CRITICAL_MAJOR x2, other token 0 | exit=0, process exited | 1,218,369 | |

**Converged at round 2 (first clean verdict; the loop ended there).** Spend: 429,974 + 243,731 = **673,705 tokens**.
Evidence (copied per round the moment the assertions passed): `~/swing-data/review-transcripts/d32-d50-exec/`
`.codex-review-r1.txt` (1,016,393), `.codex-prompt-r1.md` (142,875), `.codex-review-r2.txt` (1,218,369),
`.codex-prompt-r2.md` (156,848), `.copowers-findings.md` (raw final messages + per-finding adjudication).

**Round 1 adjudications (full text in `.copowers-findings.md`):**
- R-1 same-second name collision: the creator and the CLI copy opened a second-granular name with `connect()`+`backup()`,
  which overwrites an existing image (pre-existing in all 23 old creators and the CLI copy). Fixed in `cc24f716`: exclusive
  create reservation; an occupied name refuses BEFORE migration; a failed snapshot removes only its own reserved file.
  A garbage-bytes occupant made the first draft of the test pass on the pre-fix code (backup() fails on a non-database by
  itself); the occupant is now a real database and the test is red pre-fix.
- R-2 inventory twin across a `-wal` sidecar: no twin is claimed when either side has one (`indeterminate-wal-sidecar`).
- R-3 the image-count alarm raised before the once-only v17 seed ratification (pre-versions 13/15/16): the alarm is now
  raised after ratification and the final echo.
- R-4 the base-source equivalence test skipped when `eface268` is unresolvable: now FAILS. A vendored copy of the base
  source was not adopted (declared as accepted limitation L4 in the round-2 prompt; round 2 called the limitations sound).
- R-5 added tests: an existing schema-less DB file gets the CLI copy; a DB newer than HEAD is refused with zero backups
  (both pass on the pre-fix head too -- the behaviour was right, the proof was missing).
- R-6 inventory error line under cp1252: routed through the ASCII conversion.

### The gate table (`swing/data/db.py:637`), 23 rows

Enumerated from `git show eface268:swing/data/db.py` by parsing each `def _*_backup_gate` body (predicate, creator,
expected-tables constant, label) and the creator's filename f-string; re-derived by
`tests/data/test_backup_gate_table.py::test_i_the_roster_re_derives_from_the_base_source_and_behaves_identically`, which
also runs OLD vs NEW wrappers over every (current 0..39, target in {c, c+1, c+2, 38}) on an in-memory connection and
requires identical raise/no-raise and message text. Ungated pre-versions: **14, 17**.

| pre | stem (image `swing-pre-<stem>-migration-<UTC>Z.db`) | wrapper | expected-tables constant | label | creator alias |
|---|---|---|---|---|---|
| 13 | phase7 | `_phase7_backup_gate` | `PHASE7_EXPECTED_TABLES` | pre-Phase-7 | `_create_pre_migration_backup` |
| 15 | phase8 | `_phase8_backup_gate` | `PHASE8_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-8 | |
| 16 | phase9 | `_phase9_backup_gate` | `PHASE9_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-9 | |
| 18 | phase12-bundle-c | `_phase12_bundle_c_backup_gate` | `PHASE12_BUNDLE_C_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-12-Sub-bundle-C | |
| 19 | phase13 | `_phase13_backup_gate` | `PHASE13_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-13 | |
| 20 | phase13-sb6c | `_phase13_sb6c_backup_gate` | `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-13-SB6c | |
| 21 | phase14 | `_phase14_backup_gate` | `PHASE14_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-14 | |
| 22 | phase14-sb3 | `_phase14_sb3_backup_gate` | `PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES` | pre-Phase-14-SB3 | |
| 23 | b7 | `_b7_backup_gate` | `B7_PRE_MIGRATION_EXPECTED_TABLES` | pre-B7 | |
| 24 | phase16 | `_phase16_backup_gate` | `PHASE16_PRE_MIGRATION_EXPECTED_TABLES` | pre-phase16 | |
| 25 | broad-watch-baseline | `_broad_watch_baseline_backup_gate` | `BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES` | pre-broad-watch | |
| 26 | entry-intent | `_entry_intent_backup_gate` | `ENTRY_INTENT_PRE_MIGRATION_EXPECTED_TABLES` | pre-entry-intent | |
| 27 | watchlist-pin | `_watchlist_pin_backup_gate` | `WATCHLIST_PIN_PRE_MIGRATION_EXPECTED_TABLES` | pre-watchlist-pin | |
| 28 | cash-recon | `_cash_recon_backup_gate` | `CASH_RECON_PRE_MIGRATION_EXPECTED_TABLES` | pre-cash-recon | |
| 29 | phase18-arc-c | `_phase18_arc_c_backup_gate` | `PHASE18_ARC_C_PRE_MIGRATION_EXPECTED_TABLES` | pre-phase18-arc-c | |
| 30 | phase18-arc-h6 | `_phase18_arc_h6_backup_gate` | `PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES` | pre-phase18-arc-h6 | |
| 31 | phase21-arc-a | `_phase21_arc_a_backup_gate` | `PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES` | pre-phase21-arc-a | `_create_pre_phase21_arc_a_migration_backup` |
| 32 | phase21-arc-b | `_phase21_arc_b_backup_gate` | `PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES` | pre-phase21-arc-b | `_create_pre_phase21_arc_b_migration_backup` |
| 33 | h1-amendment | `_h1_amendment_backup_gate` | `H1_AMENDMENT_PRE_MIGRATION_EXPECTED_TABLES` | pre-h1-amendment | `_create_pre_h1_amendment_migration_backup` |
| 34 | a4-taxonomy | `_a4_taxonomy_backup_gate` | `A4_TAXONOMY_PRE_MIGRATION_EXPECTED_TABLES` | pre-a4-taxonomy | |
| 35 | demand-c | `_demand_c_backup_gate` | `DEMAND_C_PRE_MIGRATION_EXPECTED_TABLES` | pre-demand-c | |
| 36 | 22a | `_phase22_arc_a_backup_gate` | `PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES` | pre-22-A | |
| 37 | 22a4 | `_phase22_arc_a4_backup_gate` | `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES` | pre-22-A4 | |

### Corrected incidental facts (the ruling's reasoning binds; its facts were verified)

- R0-6 names the CLI copy `swing-<14-digit-ts>.db`. The code writes `swing-%Y%m%dT%H%M%S.db` (`swing/cli.py`), i.e.
  8 digits, `T`, 6 digits; the inventory matches `^swing-\d{8}T\d{6}\.db$`.
- `backups/` also holds `swing db-backup`'s weekly `swing-YYYYWW.db` (`swing/data/backup.py:33 _WEEKLY_BACKUP_RE`). The
  inventory classes those `weekly-backup` rather than `unclassified` (a third named class beside the ruling's two; every
  other name still prints `unclassified`). The weekly pruner matches only that pattern, so gate images landing in
  `backups/` are outside its reach (read, `swing/data/backup.py:113-129`).
- The brief says open with plain sqlite3 `mode=ro`. MEASURED 2026-09-14 on a synthetic image: every `Connection.backup()`
  image of a WAL-mode source carries the WAL header (bytes 18-19 = `02 02`), and a plain `mode=ro` open of such a file
  CREATED `-shm` and `-wal` beside it. The inventory therefore opens `mode=ro&immutable=1`
  (`scripts/backup_inventory.py:73`); its test asserts the tree's names, sizes and mtimes are unchanged.
- R0-1 says four test-referenced creator names; confirmed by grep of `tests/` for `_create_pre_\w*backup` (the only
  hits: `_create_pre_migration_backup`, `..._phase21_arc_a_...`, `..._phase21_arc_b_...`, `..._h1_amendment_...`). The
  other 19 per-gate creators had no reference outside `db.py` (grep of `swing/`, `scripts/`, `tests/`) and were deleted.

### Witness prep (STEP 5)

**(a) D43 -- every path `python -m swing.cli --config <throwaway> db-migrate` writes.** Established by READ (file:line
below at head `cc24f716`) and cross-checked by EXECUTION: an audit hook (`sys.addaudithook`) recorded every
write-capable `open`, `os.mkdir/rename/replace/remove/rmdir/truncate/chmod/utime`, `shutil.*`, `sqlite3.connect`,
`subprocess.Popen`, `os.system/spawn/exec`, `socket.connect`, and ANY-mode `open` under the real `~/swing-data`, plus a
before/after file tree of the scenario directory. The hook sees Python-level calls; SQLite's own C-level sidecar files
are covered by the read and by the tree diff (no leftover sidecar in any scenario).

| # | Path written | Established by | Throwaway disposition |
|---|---|---|---|
| 1 | `cfg.paths.db_path` (open read-write; WAL reaffirm; migration writes) + transient `-wal`/`-shm` | `swing/data/db.py:951-952` (`db_path.parent.mkdir`, `open_connection(reaffirm_wal=True)`); audit `sqlite3.connect` | point at the temp COPY |
| 2 | `db_path.parent` (mkdir, exist_ok) | `swing/data/db.py:951`; audit `os.mkdir` | temp |
| 3 | `cfg.paths.backups_dir` (mkdir) + ONE of: gate image `swing-pre-<stem>-migration-<UTC>Z.db` (gated) or CLI copy `swing-<ts>.db` (ungated), each reserved by `open(...,"xb")`, transient `-journal` during backup | `swing/cli.py:298-335`, `swing/data/db.py:705-744`; audit `open`+`sqlite3.connect` | temp |
| 4 | `cfg.paths.logs_dir` (mkdir) + `cli.log` on the first emitted record (`delay=True`; none was emitted in any scenario) | `swing/cli.py:236` -> `swing/logging_config.py:85,125` | temp |
| 5 | v17 seed ratification writes to `db_path` (risk_policy) -- only if `pre_version <= 16` | `swing/cli.py:373-394` | unreachable for v37/v38 |
| 6 | `user-config.toml` is READ (never written) by `apply_overrides` -- only on the v17 landing; resolves `USERPROFILE`/`HOME` | `swing/cli.py:392`, `swing/config_overrides.py:82`, `swing/config_user.py:22-23` | unreachable for v37/v38; set USERPROFILE+HOME to temp anyway |
| 7 | relative `[paths]` resolve against `USERPROFILE`/`HOME` or the config's dir | `swing/config.py:758-777` | use ABSOLUTE paths in the throwaway |
| 8 | TOML-divergence hook (opens `db_path`) | skipped for `db-migrate`: `swing/cli.py:192` | not reached |
| 9 | yfinance audit context | skipped for `db-migrate`: `swing/cli.py:203` | not reached |
| 10 | comms, exports, charts, prices-cache, finviz inbox | no reference on the `main` callback or `db_migrate` path (read); audit: zero events | not reached |
| 11 | Python bytecode caches | environment, not the CLI | `PYTHONDONTWRITEBYTECODE=1` |

Audit result, all four scenarios: `write paths outside scenario dir: []`, `events naming real ~/swing-data: []`, no
process/socket events.

**(b) Throwaway config template** (replace `<SD>` with an absolute temp dir holding the COPY as `swing.db`, `<PROJ>` with an
absolute temp project dir containing `reference/rs-universe.csv`; run with `USERPROFILE`/`HOME` set to a temp home,
`PYTHONPATH=.`, `PYTHONDONTWRITEBYTECODE=1`, cwd = the checkout under test, and assert `swing.__file__` resolves there):

```toml
[paths]
db_path = "<SD>/swing.db"
data_dir = "<SD>"
logs_dir = "<SD>/logs"
charts_dir = "<SD>/charts"
backups_dir = "<SD>/backups"
prices_cache_dir = "<SD>/prices-cache"
finviz_inbox_dir = "<PROJ>/data/finviz-inbox"
exports_dir = "<PROJ>/exports"
rs_universe_path = "<PROJ>/reference/rs-universe.csv"

[account]
starting_equity = 1200.0
starting_date = "2026-03-16"
risk_equity_floor = 7500.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8_rs_rank"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
```

**(c) Synthetic end-to-end through the REAL CLI** (head `cc24f716`; fixtures built by `run_migrations` into a scratch dir;
the CLI run as `swing.cli.main` under the audit hook from the worktree with `PYTHONPATH=.`; `<RUN>` = the session
scratchpad run dir; every scenario printed `RESOLVED swing = C:\Users\rwsmy\swing-trading\.worktrees\d32-d50-exec\swing\__init__.py`,
`EXPECTED_SCHEMA_VERSION = 38`, and `EXIT 0`):

```
gated_v37 fixture 37 -> post 38
Backup (pre-migration gate, integrity-verified): <RUN>\gated_v37\sd\backups\swing-pre-22a4-migration-20260915T072304Z.db
DB at <RUN>\gated_v37\sd\swing.db - schema version 38
NEW/CHANGED files: sd/backups/swing-pre-22a4-migration-20260915T072304Z.db 839680 ; sd/swing.db 843776   (no swing-<ts>.db)

head_v38 fixture 38 -> post 38
Schema already at version 38 (HEAD); nothing to migrate, no backup taken.
DB at <RUN>\head_v38\sd\swing.db - schema version 38
NEW/CHANGED files: none (backups/ not created)

ungated_v17 fixture 17 -> post 38
Backup: <RUN>\ungated_v17\sd\backups\swing-20260914T212310.db
DB at <RUN>\ungated_v17\sd\swing.db - schema version 38
NEW/CHANGED files: sd/backups/swing-20260914T212310.db 327680 ; sd/swing.db 843776   (no swing-pre-* anywhere)

ungated_v14 fixture 14 -> post 38
Backup: <RUN>\ungated_v14\sd\backups\swing-20260914T212311.db
DB at <RUN>\ungated_v14\sd\swing.db - schema version 38
NEW/CHANGED files: sd/backups/swing-20260914T212311.db 212992 ; sd/swing.db 843776
```

Not run by this cell (the orchestrator's, with the operator, after return): the real v37 pre-image copy through the CLI,
`db-migrate` on the v38 live COPY, and `scripts/backup_inventory.py` against the real root. **The production proof of this
arc is the first real migration after merge (22-B), not this ledger.**

---

## Reviewer B -- orchestrator (merge gate), one round

**Seat:** orchestrator. **Tree reviewed:** `c0600ea1` (branch head; diff `eface268..c0600ea1` over swing/, scripts/, tests/). **Form:** cold audit, `codex exec -p strong -s read-only --skip-git-repo-check`, cwd = the worktree (repo read access), CLAIMS FIRST then the unchanged-code composition lens; prompt forbade reading A's scratch, and A's `.codex-*`/`.copowers-findings.md` were moved OUT of the worktree for the round (restored after; sha256-matched to the durable copies). The transcript cites the committed ledger's A summary (it read `docs/`), never A's raw files.

**First launch did not happen:** from Git Bash, MSYS rewrote `/mnt/c/...` to `C:/Program Files/Git/mnt/c/...` -> `wsl-exit=127`, zero-byte transcript. Re-launched from PowerShell. Not counted.

**Assertions (the counted round):** banner `model: gpt-5.6-sol`, `reasoning effort: high`; `^ERROR` = 0; `^tokens used` = 1 (235,984), runner exit file `0`, process exited (background task completed); verdict tokens `^NEW_CRITICAL_MAJOR_FOUND` = 2 (0.152.1 double-emit), `^NO_NEW_CRITICAL_MAJOR` = 0; prompt contains neither token line-initially (count 0). Transcript 806,741 bytes. Durable copies: `~/swing-data/review-transcripts/d32-d50-exec/.codex-b-{prompt.md,review.txt,diff.txt,run.sh}`.

**Claims:** F1 PASS · F2/R0-3/R0-4 FAIL-under-concurrency (B1) · F3/R0-1 PASS (independent 23-triple extraction matched) · R0-2 PASS · F4/R0-6 FAIL (B2, B3) · scope PASS. L1, L4, L5 judged sound; L2 challenged by B2; L3 sound given the no-holder condition.

| id | B severity | finding | orchestrator adjudication |
|---|---|---|---|
| B1 | critical | The pre-image is not fenced from writes committing between the snapshot and the migration; two concurrent `db-migrate` runs yield two images and the set-difference alarm. | **PRE-EXISTING, not introduced.** At `eface268` the CLI copy snapshots on its own connection and closes it before `ensure_schema` (`git show eface268:swing/cli.py:256-270`), and every old gate body opened, snapshotted and closed a separate source connection before `_apply_migration` -- the same interval. The arc moves where the image lands, not when it is taken. Operational control today is the CLAUDE.md gotcha (stop `swing web`, prove no holder by acquiring the exclusive lock) that every live migration witness runs. The concurrent-run alarm is the R0-4 alarm doing its job. **Recommend BANK** as a register row (a fenced migration: one exclusive lock held across version read, snapshot and migration), not widened into this arc. |
| B2 | major | The inventory's positive twin claim checks only `-wal`, not `-journal`; a hot rollback journal could make "identical" files recover differently, and F4(b) deletes on that evidence. | **INTRODUCED (new script), ACCEPT, fix in-arc.** A claim that licenses a delete must be fail-closed: any `-wal` OR `-journal` on either member -> indeterminate, never a positive twin. |
| B3 | major | One unreadable or vanishing file (`stat`/hash `OSError`) aborts the whole inventory, so not every file is classified. | **INTRODUCED, ACCEPT, fix in-arc.** Per-file isolation: an `error` row with its path, hash and twin state indeterminate, the scan continues. |

**Ruling needed (PRIMARY: charc):** B1 bank-vs-widen; B2+B3 fix in-arc; and L5 (an occupied backup name now refuses instead of overwriting) ratified. Fix leg after the ruling goes to a FRESH cell (the executing cell ended at 427,685 tokens, over the cap).

---

## B-gate RULING -- CHARC (PRIMARY), literal block quote

**Author:** CHARC. **Courier:** orchestrator (transcription only). **Source:** `comms/orchestrator/read/20260915T081445Z-charc-d32-d50-b-gate-ruling-b1-banked-as-d58-b.md` (posted 2026-09-15T08:14:45Z). Headers omitted.

> RULING PACKET -- D32+D50 B-gate (ledger 190e476a section Reviewer B). CHARC,
> PRIMARY. One pass. Block-quote into the ledger; the fix leg dispatches off
> that commit. Verified before ruling: the branch log eface268..190e476a; the
> old creator at eface268 (a separate source connection opened, snapshotted,
> closed, then the migration -- B1's interval is there); the new creator's
> exclusive-create reservation (db.py:723 on 190e476a); the trailer output of
> cc24f716.
>
> B1 (critical) -- RULED PRE-EXISTING, BANK. The arc moved WHERE the image lands
>   and made a collision LOUD; it did not create the unfenced interval, which
>   every gate body and the CLI copy have had since the first gate. Provenance
>   quoted by you at eface268 cli.py:256-270 and the old gate bodies; I re-read
>   the creator at eface268 and it agrees. Register row D58, mine, written with
>   this ruling: a FENCED migration -- one connection holding the exclusive lock
>   across version read, snapshot and migration, so a second db-migrate cannot
>   interleave. Two notes ride the row so the fixing arc does not rediscover
>   them: (i) the operational control today is the exclusive-lock witness idiom
>   (stop swing web, BEGIN EXCLUSIVE, ROLLBACK) that every live migration runs;
>   (ii) the R0-4 set-difference alarm and L5's refusal are what make the
>   collision visible -- they are the detector, not the fix. Not widened here:
>   a lock held across the migration is a transaction-shape change in the
>   runner, its own arc with its own tests, beyond a refactor that promised to
>   preserve firing semantics.
>
> B2 (major, introduced) -- RULED FIX IN-ARC, FAIL CLOSED. A claim that
>   licenses a delete is a proof, and a proof with a known hole is not one: any
>   -wal OR -journal beside EITHER member -> "twin: indeterminate", never a
>   positive twin. Discriminating test: plant an empty -journal beside an
>   otherwise byte-identical pair; pre-fix the row says twin, post-fix it says
>   indeterminate; keep the -wal case as its sibling.
>
> B3 (major, introduced) -- RULED FIX IN-ARC. Per-file isolation: an OSError on
>   stat or hash yields an `error` row carrying the path and the exception text,
>   hash and twin state indeterminate, and the scan CONTINUES; the run's exit
>   status stays 0 (an inventory is evidence, not a gate) but the summary line
>   counts error rows so the operator sees them. Discriminating test: one
>   unreadable member in a three-file root -> three rows, one of them error.
>   Same family as gotcha #27 (an early abort that reports nothing for the rest).
>
> L5 -- RATIFIED. An occupied second-granular name now REFUSES before anything
>   migrates instead of overwriting the image. It is a behaviour change beyond
>   the refactor, in the only direction the register allows (an existing
>   pre-image is never destroyed by a role's own hand -- D32's move-then-retain,
>   applied to the writer). Keep the test that pins the refusal; the docstring
>   says it is deliberate and why.
>
> Trailer defect on cc24f716 -- RULED RECORD, NOT REWRITE. The final paragraph
>   begins "R-1:" and git parses it as a trailer. It is NOT a Co-Authored-By: the
>   streak audit filters on that trailer KEY and this does not touch it. A
>   rewrite would move three SHAs the ledger and A's convergence record cite;
>   the CITE-THE-CONTENT rule exists for exactly that cost, and it is not worth
>   paying for a cosmetic. Record it in the ledger in one line; merge --no-ff.
>   The rule for the fix-leg cell, verbatim in its dispatch: the LAST paragraph
>   of a commit message is plain prose -- never a "Word:" line -- and it checks
>   `git log -1 --format='%(trailers)'` prints empty before reporting.
>
> Fix leg -- RULED as proposed, with the gate condition stated. A FRESH
>   sonnet-high cell for B2+B3 only, red-first, suite on the final head. B's
>   re-read is bounded to the two fixes AND carries one mechanical assertion
>   that makes the bound honest: `git diff --stat c0600ea1..<final>` touches only
>   scripts/backup_inventory.py, its tests and the ledger -- so B's verdict on
>   every other file at c0600ea1 is a verdict on the tree being merged. If that
>   diff touches anything else, B re-reads in full. The over-cap disclosure
>   (427,685 at the executing cell's end) is recorded, not penalised: the rule's
>   remedy IS the fresh cell you are dispatching.
>
> Merge conditions at my gate (unchanged, listed so nothing is inferred): the
>   bounded B re-read with the diff-stat assertion; the merged-head suite line
>   with SHA -- the OPERATOR's run per D52, transcribed into the ledger; the
>   section 4 witness on the COPY, step by step with the operator (R0-5's
>   write-surface enumeration in the ledger BEFORE the CLI runs); the inventory
>   output to the operator for the per-file disposition.
>
> D58 landed at ef6e498f (register + charc-state).

**Record (per the ruling):** trailer defect on `cc24f716` -- its final message paragraph begins `R-1:` and git parses it as a trailer; it is NOT a `Co-Authored-By`; recorded, not rewritten; the arc merges `--no-ff`.
**Record:** the executing cell ended at 427,685 tokens (over the 400K cap, measured by the orchestrator via `cell_depth.py`); the fix leg goes to a fresh cell.

---

## Fix leg -- B2 + B3

**Cell:** fresh `implementer-sonnet-high`. **Worktree:** `.worktrees/d32-d50-exec`, continuing on branch `d32-d50-exec`
from `3ae98ced`. **Commit:** `e690ebe6` -- `fix(scripts): B2+B3 -- fail-closed sidecar twin check, per-file scan
isolation` (touches `scripts/backup_inventory.py` and `tests/scripts/test_backup_inventory.py` only; no other commit in
this leg). `git log -1 --format='%(trailers)'` on `e690ebe6` prints empty.

**B2 red-then-green.** `test_no_twin_is_claimed_across_a_wal_sidecar` (existing test, its gate-side assertion
strengthened) and `test_no_twin_is_claimed_across_a_journal_sidecar` (new, its sibling). Both proven red by temporarily
checking out the pre-fix script alone (`git checkout 3ae98ced -- scripts/backup_inventory.py`, tests unchanged, then
restored via `git checkout HEAD --`) before the fix commit landed, and separately via a scoped `git stash push -u -- 
scripts/backup_inventory.py` (captured, applied back, dropped) while drafting the fix:
- `test_no_twin_is_claimed_across_a_wal_sidecar` (gate-side wal case) --
  `AssertionError: assert 'none' == 'indeterminate-wal-sidecar'`
- `test_no_twin_is_claimed_across_a_journal_sidecar` (new) --
  `AssertionError: assert '...swing-pre-22a4-migration-20260908T010203Z.db' == 'indeterminate-journal-sidecar'`
  (pre-fix the code never checked for a `-journal` sidecar at all, so the byte-identical gate path was reported as a
  positive twin).

Post-fix: both green, plus the pre-existing CLI-side wal case unchanged.

**B3 red-then-green.** `test_a_per_file_stat_or_hash_error_does_not_abort_the_scan` (new; `sha256_of` monkeypatched to
raise `OSError` for one of three fixture files) --
red: `OSError: synthetic hash failure`, propagating out of `_scan` -> `inventory` -> `render` and aborting the whole
scan (only the exception traceback, zero rows). Post-fix: green -- 3 rows, the bad file's row carries
`error:OSError:synthetic hash failure` in the schema-version column, `indeterminate` in both the sha256 and twin
columns, the other two files unaffected, `# errors: 1` in the summary, and the run exits 0.

**Suite (final head `e690ebe6`):** `python -m pytest -m "not slow" -q -n 4` --
`12428 passed, 13 skipped, 1159 warnings in 1067.62s (0:17:47)`, exit code 0.

**Scope-lock diff-stat**, `git diff --stat c0600ea1..e690ebe6` (the orchestrator's stated merge condition):

```
 docs/phase22-arc-d32-d50-ledger.md     | 104 ++++++++++++++++++++++++++++++
 scripts/backup_inventory.py            | 113 ++++++++++++++++++++++++++-------
 tests/scripts/test_backup_inventory.py |  70 +++++++++++++++++++-
 3 files changed, 262 insertions(+), 25 deletions(-)
```

Only `scripts/backup_inventory.py`, its test, and this ledger changed since `c0600ea1` -- the bounded B re-read holds.

---

## Reviewer B -- bounded re-read of the fix leg (orchestrator)

**Tree:** `1cbd6ef1`. **Bound held mechanically:** `git diff --stat c0600ea1..1cbd6ef1` = the ledger, `scripts/backup_inventory.py`, `tests/scripts/test_backup_inventory.py` only (verified by the orchestrator). **Inputs:** the script and test diffs `3ae98ced..e690ebe6` plus the two current files; A's and B's earlier scratch moved out of the worktree for the round and restored after. **Assertions:** `gpt-5.6-sol` / `high`; `^ERROR` 0; `^tokens used` 1 (92,461); exit file 0, process exited; `^NEW_CRITICAL_MAJOR_FOUND` 2, `^NO_NEW_CRITICAL_MAJOR` 0; prompt carries neither token line-initially. Transcript 315,400 bytes at `~/swing-data/review-transcripts/d32-d50-exec/.codex-b2-review.txt`.

**Verdict:** B2 PASS · B3 FAIL · read-only/ASCII PASS · both new tests discriminating.

| id | B severity | finding | orchestrator adjudication |
|---|---|---|---|
| B2R-1 | critical | A file whose schema read ERRORED is not an `Entry.error`, so an identically-hashed unreadable gate can still be named a positive twin. | **ACCEPT, fix.** Byte identity is arguably still proven, but the ruled principle is FAIL CLOSED for a claim that licenses a delete: any member with a schema-read error -> twin indeterminate. Residual of B2. |
| B2R-2 | major | `Path.is_file()` runs before the guarded block and swallows `OSError`, so an inaccessible or vanishing candidate is silently SKIPPED, not an error row. | **ACCEPT, fix.** Residual of B3 (every matched file gets a row). |
| B2R-3 | minor | A hash-error row discards the size/mtime/sidecar already read (reports 0 bytes). | **ACCEPT, fix** (same function, no extra round). |
| B2R-4 | minor | The summary classifies twins by string PREFIX `indeterminate-`, so a relative gate path beginning with that text is misclassified. | **ACCEPT, fix** (compare against the exact sentinel set). |
| B2R-5 | (test gap) | The B3 test exercises only the hash failure, not stat, and asserts no `main()` exit status. | **ACCEPT, add** a stat-failure case and a `main()` exit-0 assertion. |

**Authority:** no new ruling needed -- every item is a residual of the requirements CHARC already ruled for B2 and B3 (fail closed; every file classified; exit 0; error rows counted). The orchestrator authorizes a second fix pass on the same cell, same scope lock, followed by one more bounded B re-read.

---

## Fix leg pass 2

**Cell:** the same `implementer-sonnet-high`, continuing on branch `d32-d50-exec` from `f5ff5280` (the bounded-re-read
ledger section above). **Commits:**
- `75c710e9` -- `fix(scripts): B2R-1..B2R-5 -- fail-closed schema-read errors, no silent skip, metadata preserved,
  exact sentinels` (`scripts/backup_inventory.py`, `tests/scripts/test_backup_inventory.py`).
- `f0fc2ecb` -- `test(scripts): correct the B2R-2 discriminating test to actually discriminate`
  (`tests/scripts/test_backup_inventory.py` only) -- the first `75c710e9` draft of the B2R-2 test patched only
  `Path.stat`, which does not exercise the real defect on this box: `Path.is_file()` (`follow_symlinks=True`)
  resolves to `os.path.isfile()`, a Windows C builtin that calls the OS-level stat syscall directly and bypasses
  the patchable `Path.stat` method entirely (measured empirically, both by direct probe and by re-running the
  original test against the pre-`75c710e9` script: it failed, but only on the new error COLUMN not existing --
  `len(rows) == 3` still passed, i.e. the file was never silently dropped -- so the test was not proving what its
  name claimed). Corrected by also patching `Path.is_file` to return `False` for the bad path, reproducing the
  observable consequence of the real swallow without depending on Windows ACLs; re-verified red against the
  pre-pass-2 script with the corrected assertion firing for the right reason (`len(rows) == 2`, matching the
  ruling's own description of the defect).

`git log -1 --format='%(trailers)'` prints empty on both `75c710e9` and `f0fc2ecb`.

**Red-then-green, all five items:**

- **B2R-1** (`test_no_twin_is_claimed_when_the_schema_version_read_errors`, new) -- red against the pre-pass-2
  script: `AssertionError: assert 'C:\...swing-pre-22a4-migration-20260908T010203Z.db' == 'indeterminate'` -- a
  byte-identical corrupt (non-sqlite) CLI-copy/gate-image pair read as a positive twin because a schema-version
  read failure was never recorded on `Entry.error`. Green post-fix: both members' schema-version column shows
  `error:...`, the CLI copy's twin is `indeterminate`, `0 of 1`.
- **B2R-2** (`test_a_stat_failure_on_a_matched_file_yields_an_error_row_not_a_silent_skip`, new, corrected in
  `f0fc2ecb`) -- red against the pre-pass-2 script (corrected assertion): `AssertionError: assert 2 == 3` -- the
  bad file silently dropped with NO row at all (`Path.is_file()` swallowing the injected failure before the
  per-file guard ever ran). Green post-fix: 3 rows, the bad file's own error row (`error:OSError:synthetic stat
  failure` in the new error column, sha256/twin both `indeterminate`), `# errors: 1`.
- **B2R-3** (`test_a_per_file_stat_or_hash_error_does_not_abort_the_scan`, amended) -- red against the pre-pass-2
  script: `AssertionError: assert 'error:OSError:synthetic hash failure' == '36'` -- the schema version, already
  successfully read before the hash step failed, was being discarded/zeroed instead of preserved. Green post-fix:
  the bad row's schema-version column shows the real `36` and its size matches the real file, while sha256/twin
  stay `indeterminate` and the exception text moved to the new dedicated error column.
- **B2R-4** (`test_summary_twin_count_uses_exact_sentinels_not_a_string_prefix`, new) -- red against the
  pre-pass-2 script: `AttributeError: module 'backup_inventory' has no attribute '_is_positive_twin'` -- no
  extracted, independently-testable classifier existed; the buggy string-prefix check was inlined in `render()`.
  Green post-fix: `_is_positive_twin` is exact-sentinel-set membership, asserted directly (a `render()`-level
  fixture cannot reproduce the prefix bug on Windows, since an absolute path always leads with the drive letter).
- **B2R-5** (`test_main_exits_0_with_an_error_row_present`, new) -- a coverage item, not a code defect: it PASSED
  against the pre-pass-2 script too (the CLI already exited 0 with an error present under the first fix leg),
  recorded per the ruling's own `(test gap)` classification rather than misreported as a red-then-green fix.

**Suite (final head `f0fc2ecb`):** `python -m pytest -m "not slow" -q -n 4` --
`12432 passed, 13 skipped, 1159 warnings in 849.26s (0:14:09)`, exit code 0.

**Scope-lock diff-stat**, `git diff --stat c0600ea1..f0fc2ecb`:

```
 docs/phase22-arc-d32-d50-ledger.md     | 166 +++++++++++++++++++++++++++
 scripts/backup_inventory.py            | 179 +++++++++++++++++++++++++------
 tests/scripts/test_backup_inventory.py | 198 ++++++++++++++++++++++++++++++++-
 3 files changed, 510 insertions(+), 33 deletions(-)
```

Only `scripts/backup_inventory.py`, its test, and this ledger changed since `c0600ea1` -- the second bounded B
re-read's diff-stat assertion holds.

---

## Reviewer B -- bounded re-read 2 (orchestrator)

**Tree:** `4ded0590` (bound held: `git diff --stat c0600ea1..4ded0590` = ledger + `scripts/backup_inventory.py` + its test). **Assertions:** `gpt-5.6-sol`/`high`; `^ERROR` 0; footer 1; exit 0, process exited; `^NEW_CRITICAL_MAJOR_FOUND` 2, `^NO_NEW_CRITICAL_MAJOR` 0; prompt token-free. 340,105 bytes, `~/swing-data/review-transcripts/d32-d50-exec/.codex-b3-review.txt`.

**Verdict:** B3 PASS; B2R-1, B2R-2, B2R-4, B2R-5 PASS; read-only/ASCII PASS; **B2 FAIL, B2R-3 FAIL.**

| id | B severity | finding | adjudication |
|---|---|---|---|
| B3R-1 | critical | The sidecar probes use `Path.exists()`, which returns False when the metadata lookup raises, so a real but unprobeable `-wal`/`-journal` reads as absent and the pair can still be named a positive twin. | **ACCEPT.** Same CLASS as B2R-2 (`is_file()` swallowing `OSError`) -- fixed as an instance, not as a class. |
| B3R-2 | major | The journal-sidecar flag is obtained but never rendered, so an error row cannot report it; the B2R-3 test asserts neither sidecar flag. | **ACCEPT.** |

**Loop shape (the orchestrator's call, recipe section 3):** three bounded B reads, each finding residuals of the previous fixes -- the Expansion-#13 signature. The remedy is NOT another instance fix plus another round. It is ONE CLASS SWEEP by a fresh cell: state the class once -- **every filesystem probe in the script whose failure can be swallowed into a Boolean or skipped (`exists`, `is_file`, `is_dir`, `glob`/`iterdir` over an unreadable directory, `os.path.*`) must distinguish ABSENT (not-found) from UNKNOWN (any other `OSError`), and UNKNOWN on either member withholds a positive twin** -- then read the WHOLE script for members of the class, record each site under uncounted `SS-N` ids, fix, and follow with ONE confirming bounded B round. The previous fix-leg cell ended at 357,044 tokens; the sweep goes to a fresh cell.
