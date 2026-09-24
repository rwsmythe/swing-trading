# Phase 22 arc 22-I EXECUTING -- exec ledger (the REPLACE-exposure sweep, migration 0041)

**Plan:** `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.md` (424 lines; blob sha256 `ac1920c7838ab13a9d2771565f7ef187d544a169a380ddd8d382e149c37d0bc2`, measured `git show 555acce3:<plan> | sha256sum`; the CRLF working copy hashes differently). **Plan ledger:** `...-sweep.ledger.md`. **Census:** `...-sweep.census.md`.
**Base:** `555acce3` (main, the merge of the accepted plan). **Worktree:** `.worktrees/22-i-exec`, branch `22-i-exec`. **Rules read from main @ `555acce3`** by absolute path: `docs/implementer-dispatch-recipe.md` (in full), `docs/harness-architecture.md` section 5.1, the brief (22-I sections 0-5, incl. CHARC's architecture-pass line @ `9d3bba10` and its three notes), CLAUDE.md section Gotchas (SQLite block).

## Round 0 (no Codex) -- premise re-derivation at `555acce3`

Nothing open. Every file:line the plan cites that this arc touches was read at the base; the column partitions of plan section 1.3 were re-added against `PRAGMA table_info` on a fresh `run_migrations(target_version=40)` DB (rc 20, rp 34, hr 13, hsh 7, rr 20, rd 20, sac 15, yfc 11, aes 10, dmr 42, rl 24, lve 16 = 7 + 5 + 4); every FK/`ON DELETE` action the a17 table names was re-read from `PRAGMA foreign_key_list`; the writer manifest was re-run (`grep -rnE "(UPDATE|DELETE FROM|REPLACE INTO|INSERT OR [A-Z]+ INTO)\s+(<the 21 tables>)\b" swing scripts research --include=*.py`, plus the dynamic `f"UPDATE ...{` shape) and every SET list read -- each M set in plan section 1.3 equals its writer's SET list. One count wording, not a fork: plan T1 says "28 files"; the measurement is 28 `EXPECTED_SCHEMA_VERSION == 40` assertions in 27 files (`grep -rnE "EXPECTED_SCHEMA_VERSION\s*==\s*40" tests`).

## Per-task commits

| Task | Commit | Note |
|---|---|---|
