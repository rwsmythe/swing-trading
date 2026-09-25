# Orchestrator handoff — 2026-09-24 (late) — 22-I at the PRE-REVIEW gate; D67/D69 held on Reviewer B

**Supersedes** `orchestrator-handoff-2026-09-24-22i-plan-returned.md`.
**From:** the generation bootstrapped 2026-09-24 ~19:20Z (session `0701ec7a`, Opus 5.5). **Rolled at:** ~335K self-read, on a CLEAN BOUNDARY. Both cells have returned; the next packets (22-I Reviewer A→B→witness, and the D67/D69 fork, fix and round) do not fit in what remains.
**No cell is in flight.** **Re-derive every fact below.**

## 1. STATE

- **`main`** is the committed plan-merge `555acce3` plus directors' and my docs commits (my recipe guards are at `e929e580`). It is far ahead of `origin`, not pushed; the push is the operator's. Schema **v40** live.
- **Pipeline:** the first v40 nightly (run 184, 17:30 HST 09-24) has NOT been compared by this seat. Compare its per-class warning Counter and `export_status` against run 183 (RD's successor owns a T1 check on the same run).
- **Worktrees:**
  - `.worktrees/22-i-exec` (branch `22-i-exec` @ `6b65eda3`, clean). THE LIVE ARC.
  - `.worktrees/d67-d69-riders` (branch @ `e0afe08a`, clean). HELD.
  - `.worktrees/22-i-plan`: the plan branch, merged at `555acce3`. Remove it at your convenience (`git worktree remove`).
- **Directors:** new generations `swing-charc-20260924-1127` and `swing-rd-20260924-1130` (both rolled today). Trust the `ping ->` line.

## 2. IN FLIGHT, owner = you

### 22-I — T0–T18 DONE; the pre-review gate PASSED; NO Codex round opened

- **Tree and records:**
  - Exec ledger in the worktree: `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.exec-ledger.md`.
  - Evidence: `~/swing-data/review-transcripts/22-i-exec/`, which holds:
    - the probe output, sha256 `1cd6836f…`;
    - the rehearsal record;
    - `db-migrate.out` and the manifest check.
  - The QA'd return report is posted to both directors (`20260925T020958Z`). Read it; it carries every number.
- **QA done at this seat:**
  - The tree is clean at `6b65eda3`: 27 commits, trailers empty.
  - The `swing/` diff is exactly the ruled carve-outs, and T17's diff is docstring-only, read.
  - `reconciliation_auto_correct.py` is untouched.
  - The probe sha256 was verified.
  - The suite (14698 passed) is the cell's claim. **Your merged-head run is the binding one.**
- **Open fork for CHARC:** deviation 1, AL-10. The test seam `guards_dropped` is used in four kinds of site, not AL-10's two. Don't open review rounds that would churn over it; get the ruling first, or state that Reviewer A treats AL-10 as amended pending CHARC.
- **Next:**
  1. Dispatch a FRESH `implementer-opus-high` cell for **Reviewer A**:
     - `codex exec -p strong`, and the banner MUST read `model: gpt-5.6-sol` (the recipe guards @ `e929e580`: no fallback; model-name assertion). The operator keeps strong at `gpt-5.6-sol` (charc-state `7592553a`).
     - Return at EVERY round gate; copy each round to `~/swing-data/review-transcripts/22-i-exec/`.
     - Read the list LEAN: the plan's §4–§5, the exec ledger, the ruling sections of the plan ledger, the recipe §3. The continuation cell spent ~300K on reading; a full re-read will cap it again.
     - Read `cell_depth --agent <id>` at every gate.
  2. **Reviewer B is yours** (cold audit, `-p strong`, banner asserted). The D67/D69 B prompt at `~/swing-data/review-transcripts/d67-d69-riders/reviewer-b/b-prompt.md` is a working shape: state the claims first, then the envelope, the limitations, and the verdict described but never written line-initially.
  3. **CHARC's merge gate = the WITNESS SITTING W0–W5** (brief §5), step by step with the operator present, never across the 17:30 HST pipeline.
- **Calendar:** Reviewer B must be clean by **10-01 EOD HST** and the sitting must land **before 10-02 EOD HST**, or 22-I PARKS to 10-21. Post the park if it comes.
- **After the merge:** delete `~/swing-data/scratch/22-i-probe/` and `~/swing-data/scratch/22-i-exec-rehearsal-*`.

### D67/D69 — Reviewer B NOT clean; the merge is HELD

- **Branch** `d67-d69-riders` @ `e0afe08a` (9 commits, trailers empty).
- **A rounds:** R1, R2, R3-rerun and R4, all `NEW_CRITICAL_MAJOR_FOUND`, each fixed. The ledger (`.copowers-findings.md`, worktree root and the durable dir) has them. A spend 573,737.
- **Reviewer B:** `~/swing-data/review-transcripts/d67-d69-riders/reviewer-b/` (`-p strong`, banner `gpt-5.6-sol`, verdict `NEW_CRITICAL_MAJOR_FOUND`). Findings and branches are in my mail `20260925T021027Z`:
  - **B-1** (introduced by R4-1): the wrapper must test `"attempt_id" in kwargs`. Tests-only. Mine to fix.
  - **B-2** (introduced by R2): FORK to CHARC. Brief clause (d) (contain) collides with clause (e) (a prompt failure propagates). Both branches are in the mail; my lean is (i), propagate.
  - **B-3:** minor; bank it.
  - B also found L2's wording too broad; correct it in the ledger.
- **Next:**
  1. Get CHARC's B-2 ruling.
  2. Dispatch ONE `implementer-sonnet-high` cell. It fixes B-1 and B-2 per the ruling, then runs ONE counted A round (`-p strong`, model asserted) on the fixed tree; that round reads R4-1, B-1 and B-2 together.
  3. Re-run B on the fixed tree.
  4. Merge (`--no-ff`: ledgers cite SHAs), then the merged-head suite.
- **Also:**
  - Transcribe CHARC's `381943bd` ruling (clause (b) = `n_written`) into that ledger as a block quote.
  - `plan-ledger.md` and `step3-ledger.md` in the D67 durable dir look like 22-I files swept in by my predecessor's scratchpad copy. Read them and relocate to `review-transcripts/22-i-plan/`.
  - The D67 merge also closes a PRE-EXISTING isolated-run failure on main (`test_entry_post_audit_columns.py::test_fill_origin_enum_all_three_new_values_persistable_via_route`, the `attempt_id` TypeError).

### Queued, not started

- **22-F plan cell** (`implementer-opus-high`; census first, no Codex; brief = the same file, 22-F sections). CHARC routed assign-intent's ascii gap into it as row 7a (`11c623d7`). May dispatch now (22-I's plan is accepted).
- **D67 L1 follow-on rider** (CHARC-ruled, you sequence): the fixture patches `swing.trades.entry.insert_trade_with_event` at the LOOKUP SITE, never an `entry.py` edit. Discriminator: a sentinel side-effect asserted after `record_entry` in a module that imports after `tests/trades/`. Gotcha candidate: patch where looked up; a fixture is verified by being reached.

## 3. DONE THIS GENERATION

- **22-I plan:** read end to end and QA'd. RD's dmr FLIP tightening encoded. Both director passes transcribed (`d9b88b64`). Merged `--no-ff` at `555acce3`, merged-head suite 13417 / 0 failed.
- **22-I executing:**
  - Cell 1 did T0–T11 and was stopped at 641K.
  - Cell 2 did T12–T18. The OPERATOR ruled "let it run past cap" when it was projected to cross 400K. That grant is SPENT.
- **Recipe:** the two Codex-tier guards (`e929e580`).
- **Codex fact:** CHARC's "strong profile absent" was corrected by measurement. `strong.config.toml` has existed since 07-22, and a `-p strong` probe gives `gpt-5.6-sol`/high. CHARC superseded item 3.
- **D67/D69:** round 4 authorized in writing and run; Reviewer B run.

## 4. AUTHORITIES (a grant is STATE)

- **Operator "Fix the remaining 6 items on your list"** covers D67/D69 through merge. It is NOT spent.
- **Operator via CHARC `d4f2cbed`** ("Perform the resequencing and kick off the work") covers 22-I → 22-F: plan cells, executing cells and gates as the brief states. The 22-I witness sitting still needs the operator present, step by step.
- **My written authorizations by cell message, all SPENT:**
  - D67/D69 round 4 (the task-bearing finding named R3-1; tree `e9692c0d`; no round 5).
  - The CHARC `381943bd` relay (discriminators (a)/(b), the declared limitation, AL-7 on both increments).
- **Operator 2026-09-24 (AskUserQuestion):** let the 22-I continuation cell run past the 400K cap. SPENT; it applied to that cell only.

## 5. WHAT WILL BITE YOU

- **A cell's REQUIRED READING can cost ~300K before it does any work.** Trim the read list for continuation and review cells.
- **A cell will call a loop "converged" after FIXING a not-clean round's finding.** It is not. The gate is a clean token, OR every major fixed AND read by a later counted round (harness-architecture, the dispositioned-not-clean paragraph).
- **A Codex profile is a FILE (`~/.codex/<tier>.config.toml`), not a `[profiles.*]` section.** An unbounded `ls` and a `-p` banner are the only proof. Two seats got this wrong today in opposite directions.
- **`timeout N python -m pytest … | tail` can kill the suite and still print exit 0.** No summary line means no result. Log to a file and read the summary line.
- **Reading a file inside a worktree via Read auto-loads that worktree's CLAUDE.md** (~50K). Use `cat`/`sed` for worktree files.
