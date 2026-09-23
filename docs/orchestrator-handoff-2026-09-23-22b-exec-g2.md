# Orchestrator handoff — 2026-09-23 — 22-B EXECUTING through gate G2 (Task 8), full suite green

**Supersedes** `orchestrator-handoff-2026-09-23-22b-plan-r3.md`.
**From:** the generation bootstrapped 2026-09-23 ~19:25Z (session `8760514f`, Opus 5.5, build 2.1.280).
**Rolled at:** ~354K self-read (`cell_depth.py --sessions --live 1`), on a CLEAN boundary. **No cell is in flight**: cell 4 returned at G2 and was NOT resumed; it dies with this session.

**Re-derive every fact below. Do not carry the numbers forward.**

## 1. STATE

- **The standing grant (unchanged; still covers everything below).** The operator ruled GO on 22-B in the RD session on 2026-09-23: *"We have 7 days before 9-30, plenty of time. Let's go for 22-B"*. The record is the header of `docs/phase22-arc-b-rd-rulings-f1-f3.md` (`e0a75a67`). CHARC's commissioning dispatch (brief `9d89e304`) carried it into this inbox, and it covers writing-plans AND executing. **Dispatch the next executing cell without a fresh go.**
- **Stop line:** Reviewer B (THIS SEAT's own cold audit) must be clean on the finished EXECUTED tree by **2026-09-29 EOD HST**. Otherwise the arc PARKS: the plan goes to `main`, the exec branch is WIP-committed, the witness moves to 10-21, and the orchestrator posts the park. There is no witness 10-03..10-20 and no merge over the read week.
- **`main`** @ `640a8f28` (CHARC's latest brief ruling). The operator pushed through `5e39a446`; `main` has director commits since. The push is the operator's.
- **Plan branch `22-b-plan`** (`.worktrees/22-b-plan`) @ `e61dad27`. It is CONVERGED at `351b2e60` (364 lines; backup `~/swing-data/review-transcripts/22-b-plan/.plan-converged.md`). The ledger carries RD-PLAN-READ and CHARC-S3. Keep it: its SHAs are cited. Do not rebase.
- **Exec branch `22-b-exec`** (`.worktrees/22-b-exec`), cut from `e61dad27`, HEAD **`377523da`**.
  - **Tasks done:** encode `f5fc0568`, then Tasks 1, 2, 2A, 3, 4, 5, 6, 7 and 8, plus RULING G1 (d), RULING G1b and RULING G1d, each encoded.
  - **Main merged in `--no-ff` at docs-safe stops:** `6d906729` (0f63d6a6), `d2cd1483` (93cfe8bd), `a685dc86` (640a8f28). The branch is in sync with `main` @ `640a8f28`.
  - **Last full fast suite (`-n 4`, cell 4 on `3d69c001`): 13266 passed, 13 skipped, 0 failed.**
  - Trailers are empty across the branch (checked at every gate).
  - Migration 0040 is complete: v39 → v40, 181 manifest objects, D51 = changed {trades} + 18 additions + 0 deletions, re-derived independently at G1.
- **The EXEC LEDGER** `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.exec-ledger.md` is the arc's record. It has the gate table with the depth column filled, every ruling as a literal block quote transcribed by script with every line asserted present (RULING G1, G1b, G1d), and the open items.
- **Evidence:** `~/swing-data/review-transcripts/22-b-exec/`. No Codex round has run yet. It holds `.task5-service-draft-cell1.WIP.py`, which is reference only and superseded by the committed Task 5.
- **Directors:** CHARC `swing-charc-20260923-0802` (not rolled). RD rolled at 19:52Z; the successor is `swing-rd-20260923-0952`. **Trust the `ping ->` line `role_mail post` prints, never these names.**

## 2. GATES SO FAR (the exec ledger's table is authoritative)

| gate | cell | last commit | work | full suite | depth |
|---|---|---|---|---|---|
| G1 | 1 | `cd5945b5` | encode, T1, T2, T2A, T3, T4 (0040 complete) | (subset only) | 648,799 OVER |
| G1b | 2 | `a06b219a` | T5 service; found FORK G1b | (subset) | 298,873 |
| G1c | 2 | `2c13b940` | G1 (d), pin move, T6 CLI | (subset) | 373,211 |
| G1d | 3 | `78bdc61b` | RULING G1b (zero SQL envelope reads) | 13230/13/0 | 320,892 |
| G2a | 3 | `a789ed22` | T7 N4 terminality | 13241/13/0 | 419,583 OVER |
| G2b | 4 | `34d96a38` | RULING G1d (entry_date_ambiguous; NULL-id close) | 13246/13/0 | 186,302 |
| G2 | 4 | `3d69c001` | T8 cohort exclusion + naming + UNATTESTED | 13266/13/0 | 353,978 |

**Gate shape now in force** (CHARC, adopted): return after EVERY task until the first counted review round, and the FULL fast suite (`-n 4`, ~17 min) at every gate. A subset suite missed FORK G1b for a whole gate.

## 3. WHAT IS NEXT

1. **Drain the inbox.** Expect RD's answer to the G2 query.
   - **The question:** is `swing/web/view_models/metrics/trade_process_card.py` correctly on b22_130's REASONED_EXCLUSION roster, as the D29 observational caller of `count_per_cohort`?
   - A strike means a small change; transcribe any ruling into the exec ledger as a block quote, as with the others.
2. **Dispatch a FRESH `implementer-opus-high` cell for Task 9 (Display).** Use the shape of this generation's cell 2/3/4 prompts: targeted reads, a return per task, the full suite at the gate, the no-stash override, and "the orchestrator commits ledger rows". Then Tasks 10, 11, 12, 13 and 14 the same way.
   - **Task 11 (authorize-then-abort closure)** must carry the plan-text map updates G1b/G1d made: `placement_session` is SERVICE_ONLY; the `null_id_absent_or_canonical_reading` predicate on `trg_eia_trade_binding` is new; the trigger hashes are taken from the target_version=40 image.
   - **Task 13** uses a live-DB COPY only (the backup API from `mode=ro`).
   - **Task 14** is the close-out.
3. **Reviewer A**: `strong` (gpt-5.6-sol, high), repo access, run to convergence, the five assertions per round, with a committed round table in the exec ledger. Diff base `e61dad27`.
4. **Reviewer B** is THIS SEAT's cold audit on the finished tree (charter §2.9; recipe §3 "THE SECOND EYE"). CLAIMS_FIRST: the brief's required end state, measured against the running artifact. The runner model is `~/swing-data/review-transcripts/22-a2-exec/run_b.sh`; set `git config --local core.autocrlf true` in the worktree before any WSL git use.
5. **CHARC's merge gate asks for:**
   - B's transcript on THE TREE BEING MERGED, every finding under DEFAULT TO INTRODUCED;
   - the merged-head fast-suite line with its SHA;
   - the D51 read regenerated on the merged checkout;
   - the RUNTIME composition: `swing web` stopped, then `BEGIN EXCLUSIVE; ROLLBACK` with its result stated, then merge + `db-migrate` in ONE sitting, then `schema_manifest.py --db` clean at v40, then `PRAGMA foreign_key_check` = [].
   - The witness is operator-executed, one step per result, before 09-30.
6. **Merge form:** `git merge --no-ff`, never rebase. Its SHAs are cited in the ledgers.

## 4. AUTHORITIES GRANTED BY CELL MESSAGE (a grant is STATE)

- **Plan cell 5** (the dispatch prompt only): encode R0.K, self-sweep, the converged commit. No fourth counted round was authorized.
- **Exec cell 1** (dispatch): the encode commit plus Tasks 0-14 with gates. It was retired at G1.
- **Exec cell 2**, dispatched for Tasks 5-8 and resumed once: "G1 (d)'s obligation + move the brief pins to 0f63d6a6 + Task 6; do NOT encode any FORK G1b branch."
- **Exec cell 3**, dispatched for RULING G1b only and resumed once: "Task 7 only; do NOT change the provisional entry_date encoding or add the NULL-id clause until CHARC rules."
- **Exec cell 4**, dispatched for RULING G1d only (unit G2b) and resumed once: "Task 8 only; plant unattested values with the twin triggers dropped in the test DB."
- **No review round has been authorized or run.**

## 5. WHAT WILL BITE YOU

- **Cells overrun silently.** Cell 1 did four tasks in one pass and hit 648K; cell 3 hit 419K. Read `cell_depth --live 1` at every gate; past ~370K the next unit goes to a fresh cell.
- **`git stash list` slips.** Cells 1 and 2 each ran one despite an explicit prohibition. The likely source is the harness's own worktree notice ("capture your entry's SHA via `git stash list`"). Keep the explicit override in every prompt; cells 3 and 4 had it and did not slip.
- **b22_33's per-member roster reds on every new PROSE mention** of `unintended_execution` (G2a, G2). It is ours each time; the fix is to add the site to the roster with its reason.
- **Ruling facts measured false four times this arc** (R0.J (iii), CHARC-S3's census, R0.I's two gates, G1b's "duplicates refused by the stored reading"). Every one was caught because a cell measured instead of trusting the ruling text. Keep "report differences, never settle them" in every prompt.
- **Post from the MAIN repo cwd in the same invocation**; the tool moves cwd into a worktree after git ops there. **`role_mail` subjects cap at 80 chars.**
- **Gotcha candidates banked for CHARC's CLAUDE.md compression pass:**
  - SQLite fires the NEWEST BEFORE trigger first, so a new barrier changes the message an existing test sees (SS-12);
  - a discriminator on a real row can be pre-empted by a table CHECK, so assert the MESSAGE;
  - a modern `ALTER TABLE … RENAME` re-parses every trigger (R0.J);
  - the still-FALSE "`swing db-migrate` writes TWO backups" line.
- **The orchestrator's own queue, unlanded:**
  - the `_is_head` rename rider;
  - the `cli.py` em-dash;
  - `cell_depth --sessions` printing each session's build;
  - rewriting the stale §"Currently in-flight work" in `docs/orchestrator-context.md` (it still describes 2026-09-15; this handoff is the current record).
