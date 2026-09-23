# Orchestrator handoff — 2026-09-23 — 22-A2 EXECUTING: Tasks 1-12 DONE and QA'd; Reviewer A is the successor's first dispatch

**Supersedes** `orchestrator-handoff-2026-09-23-22a2-exec-through-gt9f.md`.
**From:** the generation launched 2026-09-23 ~04:23Z (session `0492607f`, Opus 5.5, build 2.1.280, seat `swing-orchestrator-20260922-1823`).
**Rolled at:** 322,185 (`cell_depth.py --sessions --live 1`), under the 400K trigger, at the cleanest boundary of the arc: every executing task committed and QA'd, nothing in flight, no ruling outstanding. Reviewer A is a multi-round loop that would have crossed the trigger mid-loop.
**Precondition met:** no cell in flight. Cells 10-13 have all returned; each gate verified `git status` clean.

**Re-derive every fact below; do not carry the numbers.**

---

## 1. STATE

- **`main`** is pushed and equal to origin as of the operator's push (`a4ac72ee`); the directors have committed on main since (CHARC's `fcc9f3b2` at least). Check `git rev-list --left-right --count origin/main...main`. The auto-mode classifier blocks `git push` from this seat; hand the operator `! git push origin main`.
- **22-A2 branch `22-a2-exec` @ `8633cf22`** (worktree `.worktrees/22-a2-exec`). Code head is **`eceeaac1`**; every commit after it is ledger-only. NOT pushed, by design (it merges `--no-ff` after the witness).
- **G3, the first full fast suite, on `9ae35214`** (cell-read tail, `-n 4`): **12,873 passed / 13 skipped / 0 failed**. `eceeaac1` added two test-only files after that; the cell ran tests/data + tests/trades green on it. **The merged-head suite is still owed** and is the binding one.
- Live DB **v38**, untouched by this generation. Live `swing.db` size/mtime were identical before and after cell 11's live-copy work (I re-stat'd).
- **Worktrees:** `.worktrees/22-a2-exec` (THE ARC) and `.worktrees/22-a2-plan` (KEEP until 22-A2 merges; then tear down with the sha256 reconciliation against `~/swing-data/review-transcripts/22-a2-plan/`). `launcher-color-scrub` is confirmed gone.
- Stash: exactly one entry (the 2026-05-31 quarantine). Never pop it.

## 2. WHAT THIS GENERATION DID

| Gate | Unit | Commit | Result |
|---|---|---|---|
| G-T10 (stop) | fork: the four P35 readers did not map onto four once-per-invocation call sites | — | routed; CHARC ruled G-T10-1 (option a, threaded read + budget), RD ruled G-T10-2 (a rendered cohort N carries its exclusion marker) |
| G-T10 | Task 10 + `Tier2CohortRead` + both rulings | `fc5df863` | 8506/9/0 (7 pkgs); A2-75 exactly four callers; digest `.3` unchanged |
| — | four facts differing from the rulings | — | CHARC F1 (metrics index = THREE invocations, bound 6 s) + N1 (process-card counts BANKED, post-merge follow-on); RD F3 (index cards carry no marker) + F4 (`hypothesis status` = full lines, no marker) + the N1 question (per-hypothesis tab N IS a cohort N; All is not) |
| G-T11 | Task 11 acceptance + live-copy evidence | `9a1f6638` | 5228/9/0; live-copy dry run on a MIGRATED COPY reads **ADMIT**, ONE backup written and echoed, live untouched |
| G-F4 | RD's F4 follow-on | `3b696fcc` | `hypothesis status` renders the named lines, no marker |
| G-T12 | Task 12 (retire `PENDING`; the executing record) + G3 | `ef851af2`, `9ae35214` | record `...task12-record.md` carries all 17 gate reports byte-for-byte; G3 12873/13/0 |
| G-S1 | CHARC's P34-1 + S-1 ruling (test-only) | `eceeaac1` | closure tests re-pointed to HEAD; the interval-vocabulary SQL-vs-Python comparator; no production emitter of `uncovered_barrier_absent` exists (searched) |

Rulings this generation landed byte-for-byte in the exec ledger, each courier-posted back: G-T10-2 (RD) `d85852ed` · G-T10-1 (CHARC) `047c7f8c` · G-T10-F3+F4 (RD) `3439ed13` · G-T10-F1+N1 (CHARC) `6ab2523f` · G-T10-N1Q (RD) `d973fd74` · G-T12-P34+S1 (CHARC) `5001ee20`. **Operator decision** `5fcb6b1c`: the FK-orphan repair rides the 22-A2 witness (below).

Also: the launcher color-scrub rider CLOSED on the operator's witness (my measurement: the PowerShell TOOL injects `NO_COLOR=1` into its own shell, so the pane — not a `!` probe — is the check). Both directors rolled mid-sitting: CHARC is now `swing-charc-20260922-1913`, RD `swing-rd-20260922-1915` (trust the `ping ->` line, not these names).

## 3. 22-A2 — WHAT IS NEXT, IN ORDER

1. **Reviewer A at `strong` to convergence** on `eceeaac1` (base `c212238a`). Dispatch a fresh cell per the recipe (the plan's section 8 is the envelope for every review prompt; per-round evidence preserved to `~/swing-data/review-transcripts/22-a2-exec/`; the cell returns at EVERY round gate and you read its depth before resuming; three counted rounds, then a self-sweep; a fourth needs your written authorization). Verify convergence from the persisted transcript's anchored VERDICT TOKEN with `^ERROR` = 0 — the footer alone is falsified. Report the summed `tokens used`.
2. **Reviewer B at your gate** on the tree being merged (production code under `swing/trades` + `swing/data`; REQUIRED). The nine recorded deviations are in the Task 12 record's "Deviations for Reviewer B".
3. **RD's merge-blocking measurement gate** (his successor state names it): the four readers exclude by name; the H1 count is the reader's, never pinned; the B transcript is on the tree being merged.
4. **Merge** `--no-ff` (the ledgers cite branch SHAs); then `python scripts/schema_manifest.py --write` on the merged head (the gate reads four changed pairs, zero deletions); the **merged-head fast suite at `xhigh`**, `-n 4`, READ from the tail.
5. **The witness** — plan section 9, as corrected by ruling R4 (OPERATOR-EXECUTED, ORCHESTRATOR-SCRIPTED, one step per operator result; steps 2, 4, 5 write live and are the operator's; RD owns step 6, the H1 count re-read). **Add the FK-orphan step** per `5fcb6b1c`: record rows 72/73; plain sqlite3 with `PRAGMA foreign_keys = ON`; `UPDATE reconciliation_discrepancies SET cash_movement_id = NULL WHERE discrepancy_id IN (72, 73)`; `PRAGMA foreign_key_check` must read the EMPTY SET. Placement vs `db-migrate` is yours to fix when you write the script. `swing web` must be stopped first; prove no holder with `BEGIN EXCLUSIVE` on plain sqlite3. **09-30 hard stop; no witness 10-03..10-20.**
6. After the witness: CHARC QA on disk; tear down both worktrees (sha256 reconciliation of dotfile evidence first).

## 4. AUTHORITIES GRANTED BY CELL MESSAGE

None open. Cell 10's resume carried the two G-T10 rulings as its spec; cell 12's resume added two record contents (the FK disposition line, its own G-F4 report). Both ended at their gates and are recorded in the ledger rows they produced.

## 5. QUEUE (mine, not done)

- **Post-merge, witness-free:** CHARC's FK instrument — `PRAGMA foreign_key_check` in the read-only live probe (`scripts/schema_manifest.py --db` or `tool_health`, my choice of seam) and in the witness script's post-migrate step (his register row). CHARC's **N1 process-card follow-on** (RD ruled YES: per-hypothesis tabs exclude and mark; All does not; the caller pin widens four -> five by that ruled amendment) — CHARC writes the register row.
- **CLAUDE.md:** the "`swing db-migrate` writes TWO backups" gotcha is STALE (measured ONE at G-T11; `cli.py:284-289`); the new FK gotcha text (a raw sqlite3 delete runs with foreign_keys OFF, so ON DELETE clauses do not fire — set it ON first, run `foreign_key_check` after); both ride the Gotchas compression pass (§Gotchas is at its cap).
- The `_is_head` rename rider (its own commit); the em-dash in `swing/cli.py`'s pre-18 WARN line.
- `orchestrator-context.md` §"Currently in-flight work" is STALE (still describes D56). Rewrite at a clean boundary.
- 22-B: CHARC's brief `74c15b77`, NOT dispatched; the go/no-go is the OPERATOR's at 22-A2's landing.

## 6. WHAT WILL BITE YOU

- **Standing authorization:** "We will execute these in order without needing additional permissions unless I say otherwise." (`docs/phase22-arc-a2-commissioning-brief.md` line 3 @ `78a395ed`). Reviewer A needs no fresh go. I re-asked once and CHARC corrected it; the bootstrap now says so.
- **Mail to a rolled director lands in the successor's inbox** — `role_mail` prints the CURRENT name on the `ping ->` line; the names moved twice this sitting.
- **Director rulings often arrive as plain paragraphs, not block quotes.** I transcribe by script and label the `> ` prefix as the only added byte; never call a re-set "verbatim".
- **Never `git checkout <sha>` in the exec worktree** — I did it once by a stray argument in a QA command (detached HEAD, no damage, reattached immediately). The cell shares your worktree; your ledger commits are `git commit -m ... --only -- <ledger>` (the `-m` BEFORE `--`).
- `role_mail` subjects cap at 80 chars; `--body-file` always; cd to main in the same invocation; verify on disk.
- Every prior section-6 item still applies: `-n 4` for the full suite; no stash; cp1252 on both sides.
