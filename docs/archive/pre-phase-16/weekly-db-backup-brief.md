# Weekly DB Backup — Phase 3e Operational Hygiene Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Add automated weekly backups of the production SQLite DB. The first pipeline run of each ISO calendar week copies `~/swing-data/swing.db` to `~/swing-data/backups/swing-YYYYWW.db` BEFORE any DB writes in that pipeline run. Rolling retention of 12 most-recent backups (~3 months coverage). CLI hook `swing db-backup --force` for manual triggering. Phase 2 carve-out scoped to specific files.
**Expected duration:** ~1 session (3 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation, TDD, fast suite must stay green). Note: the DB lives at `%USERPROFILE%/swing-data/swing.db` per the hard invariant — outside the repo.
2. `docs/orchestrator-context.md` — particularly §"Currently in-flight work" (n=1 closed trade VIR; production DB now contains real trade outcomes that are operationally irreplaceable) and the recently-added §"Recent decisions" 2026-04-25 entries on operational-branch as evidence-generation surface.
3. `swing/pipeline/runner.py` — current pipeline orchestrator. You'll add a backup step at the START of the runner, before any DB writes. Read it end-to-end to understand the lease-acquisition + step ordering.
4. `swing/data/db.py` — DB connection helper. May need a small read-only-clone helper or you can use `shutil.copy2` directly with appropriate locking discipline.
5. `swing/cli.py` — current CLI structure. You'll add a `swing db-backup` subcommand.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after task commits land. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The production DB is the source-of-truth for trade outcomes, per-criterion evaluation data, hypothesis labels, and ~25 evaluation_runs of operator history. As of 2026-04-25 it contains the inaugural VIR trade with backfilled hypothesis_label and 15 evaluation_runs of candidate-criteria data. **Loss would be unrecoverable** — there's no remote replica, no cloud sync (the DB is deliberately outside the Drive folder per the hard SQLite-corruption invariant), and no current backup mechanism.

The operator has now committed to evidence-generation via hypothesis-tagged trades; outcome data is going to accumulate. Protecting that accumulation is operational hygiene, not optional. Weekly cadence at the first pipeline run of the calendar week balances coverage against backup-storage cost (12 weekly snapshots × ~current DB size ≈ negligible disk).

---

## 2. Scope

### In scope (Phase 2 carve-out granted to these files)

- **New module:** `swing/data/backup.py` — backup helper with: `compute_backup_destination(now: datetime, dest_dir: Path) -> Path`, `should_backup(dest_dir: Path, now: datetime) -> bool` (returns True if no backup exists for current ISO week), `do_backup(db_path: Path, dest_dir: Path) -> Path` (does atomic copy via tempfile-in-dest-dir + rename), `prune_old_backups(dest_dir: Path, keep: int) -> list[Path]` (returns deleted paths).
- **Pipeline runner integration:** at the start of `swing/pipeline/runner.py`'s main run function, BEFORE any lease acquisition or DB writes, call `should_backup` → if True, call `do_backup` then `prune_old_backups(keep=12)`. Wrap in try/except — backup failure should NOT block the pipeline run; log the failure and continue. The pipeline must remain operational even if backup fails (e.g., disk full).
- **CLI hook:** new `swing db-backup` subcommand. Default behavior: same as `should_backup` check (only backup if needed for current week). `--force` flag bypasses the should_backup check and creates a backup unconditionally.
- **Tests:** `tests/data/test_backup.py` for the helper functions; `tests/pipeline/test_runner_backup_integration.py` for the pipeline-runner integration; `tests/cli/test_cli_db_backup.py` for the CLI subcommand.

### Out of scope

- Backup destination customization. Hardcode to `~/swing-data/backups/` (parent of `swing.db`'s directory + `/backups/`).
- Compression, encryption, deduplication. Plain SQLite file copy.
- Restore tooling. SQLite restoration is `cp <backup> ~/swing-data/swing.db` — operator-driven, no tooling needed.
- Remote/cloud backup. Local filesystem only.
- Backup verification (e.g., open the backup and run `PRAGMA integrity_check`). Out of scope — verification could be a follow-on if backup corruption is observed.
- Per-table or partial backups. Whole-DB only.
- Modification of any other pipeline-runner step. Backup goes BEFORE existing steps; nothing else changes.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. **Trust pytest output.** Baseline at start of session is 822 (per `4b83eb8`); will shift as parallel work lands.
- **Phase isolation + Phase 2 carve-out:** carve-out granted ONLY for `swing/data/backup.py` (new), `swing/pipeline/runner.py` (integration), `swing/cli.py` (subcommand). Touching any other Phase 2 file requires return-report deviation note.
- **DB invariant:** DB stays at `%USERPROFILE%/swing-data/swing.db`. Backups go to `%USERPROFILE%/swing-data/backups/`. Both outside the Drive folder.

---

## 4. Task specifications

### 4.1 Backup helper module commit

Create `swing/data/backup.py`. Functions per §2.

**ISO week computation:** Python's `datetime.isocalendar()` returns `(year, week, weekday)`. Backup filename pattern: `swing-{year:04d}{week:02d}.db` (e.g., `swing-202617.db` for ISO 2026 week 17).

**Atomic copy pattern:** create temp file in `dest_dir` via `tempfile.NamedTemporaryFile(dir=dest_dir, delete=False)`, copy bytes via `shutil.copyfileobj(src, tmp)`, close tmp, then `os.replace(tmp.name, final_path)`. Per CLAUDE.md gotcha (`os.replace` requires same filesystem) — using `tempfile` with `dir=dest_dir` keeps the temp file on the same filesystem as the destination.

**Pruning:** list backups in `dest_dir` matching glob `swing-*.db`, sort by filename DESC (which is also chronological since ISO YYYYWW is ordered), keep first `keep` entries, delete the rest. Return deleted paths.

TDD: tests for each function on synthetic fixtures (tmp directories; mocked datetime).

Commit: `feat(data): add weekly DB backup helper module`.

### 4.2 Pipeline runner integration commit

Insert backup logic at the start of the pipeline runner's main entry point, BEFORE any lease acquisition or DB writes. Wrap in try/except; log failures via the existing pipeline logger; do NOT block the run on backup failure.

TDD: integration test that monkeypatches `should_backup` to return True, runs the pipeline runner, asserts the backup destination file exists. Second test asserts that if `do_backup` raises, the pipeline still completes.

Commit: `feat(pipeline): trigger weekly DB backup at start of pipeline run`.

### 4.3 CLI hook commit

Add `swing db-backup` subcommand with `--force` flag. Default: check `should_backup`; if False, print "no backup needed for current week" and exit 0; if True, do backup + prune. `--force`: skip `should_backup` check; always do backup + prune.

TDD: CLI tests for both default and `--force` paths.

Commit: `feat(cli): add db-backup subcommand for manual backup triggering`.

---

## 5. Adversarial review (post-tasks)

After all task commits land, invoke `copowers:adversarial-critic` on the combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Atomic-copy correctness.** Verify `os.replace` is used (not `shutil.move`) and that the temp file is created in the destination directory (not in `$TMP` which may be a different filesystem on Windows per CLAUDE.md gotcha).
- **Pipeline non-blocking on backup failure.** Verify the try/except is broad enough to catch IOError, OSError, etc. but NOT KeyboardInterrupt or SystemExit. Pipeline must remain runnable when disk is full or destination is unwritable.
- **ISO week vs calendar week.** Verify the should_backup logic uses ISO week consistently (operator's intent was "calendar week"; ISO week is the unambiguous definition). Document the choice.
- **Concurrent pipeline runs.** Two pipeline processes starting in the same second of the same week could both attempt backup. The atomic-copy pattern handles this correctly (both write to different temp files; both rename to the same final path; one wins; no corruption). Verify the test exercises this race.
- **Pruning safety.** Verify pruning never deletes a backup that was just created in the current invocation. Verify it doesn't delete files that don't match the backup glob (e.g., manual operator backups with different naming).

Fix major findings in NEW commits per no-amend rule.

---

## 6. Done criteria

- All task commits landed.
- `~/swing-data/backups/` directory created on first run (helper handles missing parent).
- A pipeline run after Sunday/Monday boundary creates a fresh backup; subsequent runs in the same week do not.
- `swing db-backup` and `swing db-backup --force` both work as specified.
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green; trust pytest output.
- Return report produced per §7.

---

## 7. Return report format

```
## Weekly DB backup — return report

### Commits landed
- <SHA1> feat(data): add weekly DB backup helper module
- <SHA2> feat(pipeline): trigger weekly DB backup at start of pipeline run
- <SHA3> feat(cli): add db-backup subcommand for manual backup triggering
- <SHA4+> (if any) fix: address adversarial review findings

### Tests
- Before: <baseline>
- After: <N>, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Verification
- Manual `swing db-backup --force` produced backup at <path>; size <bytes>.
- Manual `swing db-backup` (no force, after backup exists for current week) reported "no backup needed."

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- **If `swing/cli.py` is split into multiple files** (e.g., `swing/cli/db.py`): place the new subcommand in the file matching the `swing db ...` namespace if one exists, else in the main cli module. Flag in return report.
- **If the pipeline runner's main entry point is not obviously where to insert the backup step**: place it after argument parsing but before any lease-related code. The intent is "before any DB writes by this pipeline run."
- **If tests for atomic-copy require simulating a cross-filesystem error**: hard to do in unit tests; document the manual-test verification you did.
- **If the existing test suite has any test that pre-creates `~/swing-data/`** that would interfere with backup directory creation: investigate before adding workarounds. Probably indicates the test should use a tmp directory.
