# Home-dir leakage cleanup (post-Stage-1.5 chore brief)

**Authored:** 2026-06-11 by CHARC. **Sequencing:** operator-directed — dispatch AFTER comms Stage 1.5 completes. **Scale:** an ops chore, not an arc — no copowers cycle; no tests; the safety discipline below is binding.

## What leaked

Arc development has been leaving artifacts in `C:\Users\rwsmy\` (one level above the repo). Inventory verified 2026-06-11 (`ls -lat` + `git worktree list`):

| Class | Items | Disposition |
|---|---|---|
| Orphaned ex-worktree dirs (NOT in `git worktree list`) | `swing-arc7-plan`, `swing-arc7-brainstorm`, `swing-trading-sqlite-lock` | Inspect-then-delete (see procedure) |
| Empty leftovers | `swing-trading-worktrees` (empty container), `.benchmarks` (empty) | Delete |
| Stray output files | `sb55_final.txt`, `sb55_fastsuite.txt`, `cl.txt`, `test_localsystem.txt`, `sample_cassette.yaml`, `dst-ch10.txt`, `dst-ch11-12.txt` | Inspect-then-delete; the `dst-ch*.txt` look like book-transcription intermediates — confirm regenerable against `reference/Books/` before removing |
| Retired isolated venv | `schwabdev305venv` (the deliberate schwabdev-v3 migration env, memory `feedback_isolated_venv_for_shared_dependency_migration`; that arc is closed) | Delete ONLY on explicit operator confirm in-chat |
| ACTIVE — DO NOT TOUCH | `swing-trading-arc4-plan` (in-flight 4b/4c writing-plans worktree, registered, branch `arc4-cash-recon-plan`) · `swing-trading/.worktrees/comms-ui` (in-flight Stage 1.5) | After the arc4 cycle merges: `git worktree remove` + `git worktree prune` for its dir |
| NOT ours / NOT leakage | `swing-data` (DB-location INVARIANT), `copowers-sync`, `copowers-cleanup-backup` (both deliberate, per memory), `My Drive`, `PyTrader`, `SwimData`, `MBSEConvert`, all dotfile dirs | Leave alone |

## Procedure (binding safety discipline)

1. For each ex-worktree dir: if it contains a `.git`, run `git -C <dir> status --porcelain` and `git -C <dir> log --branches --not --remotes --oneline` — anything dirty or unpushed gets surfaced to the operator BEFORE deletion, not silently destroyed. Clean → `Remove-Item -Recurse -Force`.
2. Stray files: open each, confirm project-born and value-dead, then delete. Anything ambiguous → ask, don't guess.
3. `schwabdev305venv`: operator confirm in-chat, then delete.
4. After the arc4-plan worktree retires (its cycle merges): `git worktree remove C:/Users/rwsmy/swing-trading-arc4-plan` (or `prune` if already gone) and delete the dir.
5. Verify: `git worktree list` shows only the repo (+ any then-active in-repo worktrees); re-`ls` the home dir; report exactly what was deleted and what was spared, with reasons.

## The recurrence fix (process, one line)

Two worktree conventions are in live use: sibling-of-repo (`../swing-arc7-plan` style — the leak) and in-repo `.worktrees/<name>` (the comms-ui precedent — clean, repo-contained, gitignore-covered). **Convention going forward: all implementer worktrees at `<repo>/.worktrees/<name>`.** The orchestrator records this in `docs/orchestrator-context.md` (orchestrator-lane content; CHARC flags FORM only) and applies it to future dispatch briefs. **Gitignore finding (verified 2026-06-11):** `.worktrees/` is currently excluded only via the LOCAL `.git/info/exclude:7` — untracked, per-clone, invisible to review. Move it into the tracked `.gitignore` (this is a tracked-config commit: run the fast suite per memory `feedback_orchestrator_inline_edits_need_suite_run`).
