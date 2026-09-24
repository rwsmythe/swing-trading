# Orchestrator handoff — 2026-09-24 — 22-B MERGED, LIVE AT v40, CLOSED; no arc in flight

**Supersedes** `orchestrator-handoff-2026-09-24-22b-exec-r7.md`.
**From:** the generation bootstrapped 2026-09-24 ~12:15Z (session `ef20e515`, Opus 5.5, build 2.1.280).
**Rolled at:** 429,671 self-read (`cell_depth.py --sessions`). That is past the 400K cap, **BY THE OPERATOR'S EXPLICIT AUTHORIZATION**: *"you are authorized to exceed 400k to go through the witness. You may roll after we complete that task"*. The witness completed; this is that roll.
**No cell is in flight. No worktree exists but `main`.**

**Re-derive every fact below. Do not carry the numbers forward.**

## 1. STATE

- **`main` @ `57f5f677`** or later. It is **~220 commits ahead of `origin/main`**, NOT pushed; **the push is the operator's**. Tree clean except the untracked coa-chess finding `docs/cli-autoupdate-run-poisoning-finding-coa.md` (not ours).
- **Schema v40 LIVE.** Read on `mode=ro` after the migration: `schema_version` 40; `foreign_key_check` []; `quick_check` ok; 28 trades; `schema_manifest.py --db` clean at v40.
  - The 22b gate image is `~/swing-data/backups/swing-pre-22b-migration-20260924T163904Z.db`: ONE image, none in the swing-data root.
- **22-B merge `297a9566`** (`--no-ff`, parents `c93ca9a9` + `6913899c`, trailers empty). Its code is byte-identical to the trial merge `863329aa`. The merged-head suite on that trial head was **13413 passed / 13 skipped / 0 failed**, operator-run at `-n 8`; the evidence is `~/swing-data/review-transcripts/22-b-exec/merged-head-trial-full-suite.txt`.
- **Trade 20 (AMN)** carries `entry_intent = 'unintended_execution'`, with attestation 1: tier `contemporaneous_record`, leg `deployment`.
- **`swing web`** was restarted on merged code (pid 40608, 06:43 HST).
- **Last pre-merge pipeline run: 183** (`complete`, export ok). **The next scheduled run (17:30 HST) is the first on v40.** Read it the way run 172 was read at 22-A4: compare the per-class warning Counter against run 183.
- **The record** is the exec ledger, now on main: `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.exec-ledger.md`. Its closing sections, in order: REVIEWER B, RULING B, REVIEWER B RE-READ, RULING B2-01, GATE RD, GATE CHARC (+ the W3 correction), THE WITNESS, 22-B CLOSED.
- **Directors:** CHARC `swing-charc-20260924-0324` (rolled once this sitting; the new seat has nothing pending); RD `swing-rd-20260923-1851`. Trust the `ping ->` line `role_mail post` prints.

## 2. WHAT THIS GENERATION DID (the ledger is authoritative)

| step | outcome |
|---|---|
| RULING R7 transcribed | cell 18 encoded item 3 (assign-intent close-after-commit, the 22-A3 shape) + a sweep; Reviewer A round 8 **CLEAN** (0/0/1, footer 795,810) -> **A CONVERGED**; R8-1 fixed post-convergence |
| RULINGS R8 + R8-SCOPE | cell 19: the refusal text survives a close failure, chained, for every refused result including dry runs |
| Reviewer B (this seat) | 0/4/0 on the tree being merged. RULING B: B-01 = **AL-7** (declared); B-02 fixed by cell 20 (`trade review`'s close handler); B-03 banked; B-04 banked with a compensating control. The focused re-read was 0/0/1; B2-01 ruled (a), and I fixed the comment |
| gates | RD executing-return **PASS**; CHARC merge gate **CLEAR**, on tree `2c1b4be6`. CHARC corrected W3 to ONE backup on this seat's flag (the stale CLAUDE.md gotcha) |
| witness | W0-W4 and section-5 steps 3-4 all PASS in one attended sitting, one step per result. CHARC **CLOSED 22-B** (`341aa7ca`) |
| teardown | worktrees `22-b-exec` / `22-b-plan` / `22-b-trial` removed. The branches were deleted: `-d` for the two contained in main; `-D` for the throwaway trial, whose code was verified equal to main. The `.copowers-findings.md` sha256 matched the durable copy first. The predecessor's `g6/` scratch (1.6 GB migrated copy) was deleted |

**Spend:** Reviewer A R1-R8 **6,145,248**; Reviewer B 921,616 + 168,385.

## 3. WHAT IS NEXT

1. **RD's witness step 5 and his section-7 pointer line.** These are RD's, post-merge and not blocking. Read his return when it lands; the ledger's THE WITNESS table has a pending row for it. Transcribe his result as a block quote under THE WITNESS.
2. **The push** is the operator's (~220 ahead).
3. **The first v40 pipeline run** (17:30 HST 09-24): compare against run 183 by per-class warning Counter. A class absent from 183 is a finding. Read `export_status`, which was `ok` on 183.
4. **Nothing is commissioned.** CHARC's ratified order: 22-C/22-D when a live case exists; sweeps plus the harness compaction at phase close. **The next arc is the operator's to commission.**

## 4. AUTHORITIES GRANTED (a grant is STATE)

- **The 22-B standing grant** ("We have 7 days before 9-30 ... Let's go for 22-B", `e0a75a67`) is **SPENT**: the arc is merged and closed. It covers nothing further.
- **The over-400K authorization** was for this generation, through the witness only. It does not carry.
- **Cells dispatched** under the grant, all returned, none to resume: 18 (`implementer-opus-high`, R7 item 3 + round 8), 19 (`implementer-sonnet-high`, R8), 20 (`implementer-sonnet-high`, RULING B item 2 + the AL-7 comment).

## 5. WHAT WILL BITE YOU

- **Git Bash rewrites `/mnt/c/...` arguments** passed to `wsl.exe`: the first Reviewer B launch never ran (`wsl-exit=127`). Launch WSL scripts from **PowerShell**, or with `MSYS_NO_PATHCONV=1`.
- **The claude-in-chrome JS tool blocks output containing query strings.** Screenshot instead.
- **A background full suite can be reaped under host memory pressure.** Do not restart it unasked; the operator can run it with `!` (they did, at `-n 8`, in 11 min).
- **`$_` inside a `powershell -Command "..."` given to the operator's `!` bash is expanded by bash.** Give the operator commands without `$_`, or run the check yourself.
- **Director text is not code.** CHARC's W3 cited the CLAUDE.md gotcha; the code said otherwise. Read the code a ruling depends on.

## 6. QUEUE, owners named

- **Orchestrator:**
  - **the CLAUDE.md "`swing db-migrate` writes TWO backups" gotcha is STALE since D32/D50 (`a3b2f90c`)**. It misled CHARC at the 22-B gate. Retire it: move the bullet verbatim to `docs/CLAUDE.md-archive.md`, delete it from CLAUDE.md. **This seat asked the operator's OK first** (the edit was prompted by a director and CLAUDE.md is the operator's project instructions). The OK had not been given at the roll, so ask once;
  - the `_is_head` rename rider;
  - `cell_depth --sessions` printing the build (it already does);
  - `cell_depth --live` showing more than the newest cell;
  - **the stale §"Currently in-flight work" in `docs/orchestrator-context.md`**. It still says 2026-09-15; rewrite it from THIS handoff at the next sitting;
  - **D67** (the `insert_trade_with_event` `**kwargs` passthrough, masking mechanism stated first);
  - the `backfill-intent` post-merge rider (the raw ticker in the prompt line plus the per-row post-commit I/O, RULING R7 item 4 / B-03), witness-free;
  - `%TEMP%/pytest-of-rwsmy` (6 GB), not deleted this sitting because a pytest was running.
- **CHARC** (his register, D68-D71 already registered at his compaction touch):
  - the trend SERIES legend overlap;
  - the exit route's any-exception rebuild;
  - the entry command's c2 masking (D39 sweep);
  - B-04's runner-wide durability verdict (D39 sweep);
  - the mistaken-attestation reversal surface.
- **RD/operator:** the post-merge display gap (RULING G3a (i): no stored-trade page renders `entry_intent`); RD's October read.
