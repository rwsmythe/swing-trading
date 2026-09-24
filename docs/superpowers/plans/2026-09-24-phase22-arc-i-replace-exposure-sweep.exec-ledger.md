# Phase 22 arc 22-I EXECUTING -- exec ledger (the REPLACE-exposure sweep, migration 0041)

**Plan:** `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.md` (424 lines; blob sha256 `ac1920c7838ab13a9d2771565f7ef187d544a169a380ddd8d382e149c37d0bc2`, measured `git show 555acce3:<plan> | sha256sum`; the CRLF working copy hashes differently). **Plan ledger:** `...-sweep.ledger.md`. **Census:** `...-sweep.census.md`.
**Base:** `555acce3` (main, the merge of the accepted plan). **Worktree:** `.worktrees/22-i-exec`, branch `22-i-exec`. **Rules read from main @ `555acce3`** by absolute path: `docs/implementer-dispatch-recipe.md` (in full), `docs/harness-architecture.md` section 5.1, the brief (22-I sections 0-5, incl. CHARC's architecture-pass line @ `9d3bba10` and its three notes), CLAUDE.md section Gotchas (SQLite block).

## Round 0 (no Codex) -- premise re-derivation at `555acce3`

Nothing open. Every file:line the plan cites that this arc touches was read at the base; the column partitions of plan section 1.3 were re-added against `PRAGMA table_info` on a fresh `run_migrations(target_version=40)` DB (rc 20, rp 34, hr 13, hsh 7, rr 20, rd 20, sac 15, yfc 11, aes 10, dmr 42, rl 24, lve 16 = 7 + 5 + 4); every FK/`ON DELETE` action the a17 table names was re-read from `PRAGMA foreign_key_list`; the writer manifest was re-run (`grep -rnE "(UPDATE|DELETE FROM|REPLACE INTO|INSERT OR [A-Z]+ INTO)\s+(<the 21 tables>)\b" swing scripts research --include=*.py`, plus the dynamic `f"UPDATE ...{` shape) and every SET list read -- each M set in plan section 1.3 equals its writer's SET list. One count wording, not a fork: plan T1 says "28 files"; the measurement is 28 `EXPECTED_SCHEMA_VERSION == 40` assertions in 27 files (`grep -rnE "EXPECTED_SCHEMA_VERSION\s*==\s*40" tests`).

## Per-task commits

T0-T11 by the first executing cell (stopped at 641K context by the orchestrator, a normal re-dispatch); T12-T18 by the continuation cell, which re-read the rules from main @ `11c623d7` by absolute path and found T11's own tests green at `306ce348` (the 22-I test modules + the manifest + the 0037 roster: 1187 passed) before starting.

| Task | Commit | Note |
|---|---|---|
| T0 | `dd100aa7` | exec ledger opened at base `555acce3` |
| T1 | `310d71b0` | 0041 skeleton, `EXPECTED_SCHEMA_VERSION` 41, the `BackupGateSpec(40, "22i", ...)` row; version-test BODIES -> 41, no rename (CHARC note (iii)) |
| T2 | `fe609242` | F-I2 rebuild of `trg_provenance_corrections_append_only_update` (the COALESCE wrap); the seam module created |
| T3 | `c5d787e5` | the six blanket (a) triples |
| T4 | `5c2be44b` | `pde` triple with the a17 `no_update` twin |
| T5 | `00636f90` | F-I5 `trg_lve_first_view_immutable` |
| T6 | `efed9e77` | `rr` + `rd` (c) guards |
| T7 | `6b889d6a` | `rc` (c) guards (S3-F1 as amended) |
| T8 | `c91e467d` | `sac` + `yfc` (c) guards |
| T9 | `d47571eb` | `aes` (c) guards; AL-7 pinned |
| T10 | `36b22bc2` | `rp`, `hr`, `hsh` (c) guards; the `hr` twin carries the 0034 amendment-precedent comment INSIDE the trigger (CHARC note (i), verified on disk in 0041's `trg_hr_immutable`) |
| T11 | `306ce348` | `dmr` state-machine twin (S3-F2 + RD's FLIP tightening) |
| T12a | `ec7de424` | the service twin FIRST: `ReviewAlreadyCompletedError(ValueError)` in `repos/review_log.py`, SELECT-first inside the existing `BEGIN IMMEDIATE`; the CLI wraps it to `click.ClickException("Review already completed")`; a web POST 409 pin added (no existing test pinned the text the CLI mirrors) |
| T12b | `a10236b7` | `trg_rl_no_replace` + `trg_rl_no_delete` and the F-I3 writer (`INSERT ... SELECT ... WHERE NOT EXISTS`, `rowcount == 0` -> `None`, the `IntegrityError` matcher retained verbatim); the contract pin RED at 41 before the writer change |
| T12c | `33ce36ce` | `trg_rl_immutable`; the section 4.4 closure test |
| T13 | `66af69ff` | `pex` + `wla` barrier pairs, no twin |
| T14 | `11308807` | the six F-I6 backstop pins |
| T15 | `409dae60` | meta tests over the whole of 0041 (COALESCE, the `-1` idiom, the manifest composition by execution, triggers-only) |
| T16 | `91ae4358`, `cb8674cc`, `9de7fe0c` | fixture fallout: 119 reds on the first full run, every one a TEST's raw SQL (method: the `--tb=line` crash location of each, all under `tests/`) -- no production writer was aborted; rules (a)/(c), (d), (b) respectively |
| T17 | `bd45bda9` | `cohort_provenance_correction.py` drift-reader docstring cites the guards (comment-only; docstring lines only; the `_resolve_affected_target` docstring NOT touched, CHARC note (ii)) |
| T18 | `a29351e8` + this ledger commit | step 1 `--post-migrate` (tests first); step 2 and the rehearsal recorded below |
| (style) | `37f54860` | two E501 lines + one import order in the T2/T11 test modules (cosmetic) |

## T18 -- the post-migrate probe and the live-copy rehearsal (2026-09-24 ~22:36Z)

**Rehearsal (the 22-B G6 shape).** A backup-API copy of LIVE (source opened `mode=ro`; live `schema_version` = 40) into a fresh scratch root `C:\Users\rwsmy\swing-data\scratch\22-i-exec-rehearsal-20260924T223609Z\`, with a scratch config whose NINE `[paths]` entries are absolute paths inside that root. `swing.__file__` was asserted to resolve inside the worktree (`...\.worktrees\22-i-exec\swing\__init__.py`) and `EXPECTED_SCHEMA_VERSION` = 41, then `PYTHONPATH=. python -m swing.cli --config <scratch cfg> db-migrate` (exit 0): ONE gate image, `swing-pre-22i-migration-20260924T223623Z.db`, in the scratch `backups_dir`, and no other copy. The migrated copy: `schema_version` 41; `quick_check` ok; `foreign_key_check` []; `schema_manifest.py --db <copy>` clean; triggers 43 -> 102; ADDED 59 == the spec's 59 names; DELETED none; CHANGED exactly `trg_provenance_corrections_append_only_update`, 4,140 -> 4,153 chars, transform(v40 text) == v41 text and the inverse reproduces the v40 text byte-for-byte (v41 text sha256 `8827c541c0d34bcae747e525867b3767aa66151b57568fd5b2266b214a0753a4`). Nothing was written under `~/swing-data` outside the scratch root (`find -maxdepth 2 -newer <scratch cfg>`, scratch excluded, returned nothing). The probe copy at `~/swing-data/scratch/22-i-probe/` was not touched.

**Probe.** `python scripts/probe_22i_guard_census.py --post-migrate --copy <migrated copy>`: 1,746 lines, `PASS=1491 FAIL=34 INFO=140`. **`G-0041`: 708 PASS, 0 FAIL, 14 INFO** (the 14: an F column NULL on the probed live row, so no parent-present probe applies there; C4b covers every F column in the suite). **FAIL = 34, every one in a declared class** (method: `awk` over the verdict column by section and outcome): 16 citation snapshot-key CHECK + 1 `applied_at` NOT NULL (F-I6, pinned T14) + 5 citation declared-open (AL-2: `rung7_consumption_scan_fill_ids.input[0]` absent / JSON-null, `decision_ordering.input[0]` absent, `remote_ref_age_seconds` / `remote_ref_updated_at` JSON-null) + 12 `eia` isolated probes backstopped by NOT NULL / UNIQUE / a sibling (F-I6) -- the plan's 101 - 62 - 5 = 34.

**Evidence (durable, outside the repo):** `~/swing-data/review-transcripts/22-i-exec/`: `probe-output-post-migrate.tsv` (281,566 B, sha256 `1cd6836f18617e24ee0d585f821f127a6ec8622a0164575530a97ea90ba2afe8`), `rehearsal-record.txt` (1,619 B, sha256 `c5e38a52cba0d14fab247d0c08b35d7f4f1621c94b42eab55933b28e48d3d544`), `db-migrate.out` (302 B), `manifest-db-check.txt` (143 B). The scratch root also holds the gate image and the migrated copy.

## Deviations and flagged items (each with a proposed disposition; the return report carries the same list)

1. **Seam uses beyond AL-10's "exactly two kinds".** T10 (the first cell) dropped `trg_hsh_immutable` for fixture construction over MIGRATION-seeded rows (`tests/trades/_cohort_provenance_fixtures.py::rebase_status_history_recorded_at`); T16 used the seam for FK-action DDL pins and test disposal (both "(b) with reason" under T16 rule (d)) and for an older trigger's clause that a newer 0041 trigger pre-empts. The seam docstring now lists the four kinds in use. The one use no plan rule covers is T10's; the T16 sweep planted the equivalent state at v40, before 0041, where it could (the 0036 module). Proposed: amend AL-10 to the four kinds, or convert T10's helper to plant at v40 -- CHARC's call.
2. **T18 needed a SECOND setup change the plan did not count:** the lve identity-UPDATE probes now drop `trg_lve_first_view_immutable` (it pre-empts the identity trigger they pin), and the first-view expectation covers all three first-view columns the probe touches (`actionable_at_first_view` too). Instrument-only; the FAIL arithmetic is exactly the plan's 34.
3. **Plan premise short: "Existing web 409 test green"** -- no test pinned the web POST 409; T12a added one.
4. **T16 moved two version-pinned artifacts the T1 sweep did not reach:** the trade-20 acceptance world (read by the CLI, whose `connect()` refuses v40) -> `target_version=41`, and the 0040 foreign-trades census, which now names 0041's three matches (`V41_NEW_FOREIGN_TRADES_OBJECTS`).
