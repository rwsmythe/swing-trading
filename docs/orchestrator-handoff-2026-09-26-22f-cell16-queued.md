# Orchestrator handoff -- 2026-09-26 -- 22-F EXECUTING: Round 4 ruled; cell 16 queued, then Reviewer B pass 2

**Supersedes:** `orchestrator-handoff-2026-09-25-22f-r2-gate.md`.
**From:** the generation bootstrapped 2026-09-25 ~22:00Z (Opus 5.5). It rolled at ~370K self-read on a clean boundary: CHARC's Round 4 ruling was landed in the ledger and its path posted back. No cell was in flight. The operator was told the rollover would happen here.

**No cell is in flight.** Cells 10-15 have all returned. **Re-derive every fact below.**

## 1. STATE

- **`main`** is at this handoff commit, on top of `09986d95`. It is NOT pushed; the push is the operator's.
- **Schema v41 LIVE.** 22-F has no schema change.
- **Worktrees:**
  - `.worktrees/22-f-exec`, branch `22-f-exec` @ `77df1bd9`: ACTIVE and clean. The trailer audit over `704ac133..HEAD` is empty.
  - `.worktrees/22-f-plan` @ `846919c6`: merged. Remove the worktree when convenient and KEEP the branch, because the ledgers cite it.
- **Directors:**
  - CHARC `swing-charc-20260924-1903` measured **~591K, OVER the 400K cap**. That is CHARC's rollover to make; I told the operator.
  - RD `swing-rd-20260924-2100`, ~342K.
  - Trust the `ping ->` line.

## 2. IN FLIGHT, owner = you: 22-F EXECUTING

- **The executing ledger is the record:** `docs/superpowers/plans/2026-09-25-phase22-arc-f-handler-escape-sweep.exec-ledger.md` on `22-f-exec`, ~341KB. READ BY SECTION.
  - My sections begin at "### Round 2 gate -- CHARC's RULING". Every director ruling since then is block-quoted, checked byte-for-byte, and each is followed by a consolidated authorization.
- **Dispatch prompts** are in `~/swing-data/review-transcripts/22-f-exec/`. `dispatch-prompt-exec-c10.md` .. `-c16.md` each chain to the one before. Reviewer A evidence is in `r3/` and `r4/`; Reviewer B pass 1 is in `reviewer-b/` (with `run_b.sh`, which is reusable).
- **What happened this generation** (all in the ledger):
  - The R2 fixes (cell 10).
  - **STOP-6:** both close helpers now re-raise interrupts (cell 11).
  - **Round 3:** cell 11's three attempts were disqualified and NOT COUNTED. The "D67/D69 precedent" the cell cited does not exist; CHARC concurred.
  - **STOP-7:** three this-arc `log_contained` sites (cell 13).
  - **Round 3, counted:** R3-06, `ensure_schema` catches `BaseException` (cell 14), then G3 at 15319/13/0.
  - **Reviewer B pass 1**, mine, valid, 699,735 tokens: B-1..B-4 (cell 15).
  - **Round 4, counted**, 1,071,577 tokens: R4-01..R4-03.
- **Counted Reviewer A spend:** 721,619 + 649,427 + 724,192 + 1,071,577 = **3,166,815**. Reviewer B pass 1 cost 699,735 on top of that.
- **NEXT, in order** (the operator grant `d4f2cbed` covers all of it; it is NOT spent until the 22-F merge):
  1. **Dispatch cell 16**, `implementer-opus-high` (plan section 0.5), from `~/swing-data/review-transcripts/22-f-exec/dispatch-prompt-exec-c16.md`. It is written and unrun. Run `cell_depth --live` first. Cell 16 does five things, then RETURNS:
     - R4-01 (i): the preserve handler raises a non-`Exception` `from exc` with one record.
     - R4-01 (ii): the one-token change `_rollback_run_or_raise(conn, preserve_error)`.
     - One AL line in CHARC's text.
     - The declines recorded.
     - **G3** on the final head.
  2. **QA cell 16** on disk and fill its depth. Then **run Reviewer B pass 2 yourself**:
     - Copy `reviewer-b/` to `reviewer-b-2/`.
     - Regenerate `b-diff.txt` as `704ac133..<head> -- swing/ tests/`, and check that it plus the prompt stay under 1MB.
     - Set the head SHA in the prompt, and add R4-01 and B-1..B-4 to the claims and the banked list.
     - Run it with `wsl.exe bash -lc 'bash .../run_b.sh'` in the background.
     - Read the validity yourself: banner, `^ERROR` 0, one anchored verdict, footer, exit 0.
     **That transcript is CHARC's merge-gate transcript.**
  3. **Per CHARC (Round 4 ruling):**
     - **NO Reviewer A Round 5.**
     - If B pass 2 returns an unbanked INTRODUCED major, fix it WITHOUT a counted round and run B again.
     - A NEW class, meaning not the interrupt-at-cleanup class, goes to the OPERATOR.
  4. On a clean or dispositioned B: send the return report to the directors.
  5. **CHARC's code-only merge gate** (NO witness rung). It checks:
     - T-Z1, verbatim;
     - the census line pin, RE-MEASURED on the MERGED `cli.py`. It re-pinned five times in this arc, and CHARC re-checks mechanically on the final head;
     - the trailers;
     - the merged-head line with its SHA.
  6. The merge is `git merge --no-ff`, because the ledgers cite branch SHAs; never rebase. Then run the merged-head fast suite and READ it, with the orchestrator's `xhigh` escalation for the composition step.
- **Banked, order-dependent reds:** `test_setup_auth_failure_audit_status_and_sentinel_redaction` fails in isolation on the base (it passes in its whole file); `test_a2_94_...` and `test_phase8_pipeline_second_same_day_run_upserts` have gone red under xdist load. At G3 and at the merged head, reproduce with `-n 0` FIRST. Never wave one through on the register row.

## 3. AUTHORITIES (a grant is STATE)

- **Operator via CHARC `d4f2cbed`** ("Perform the resequencing and kick off the work"): 22-F's executing cells and gates. UNSPENT until the 22-F merge.
- **CHARC grants this generation** (all block-quoted in the ledger):
  - F-F2's new-type clause: `TosReconciliationFailedError(RuntimeError)`;
  - the helper-wide STOP-6 change;
  - no fourth round for R3-06;
  - Round 4 (on B-1/B-2);
  - NO Round 5.
- **My written authorizations** (in the ledger):
  - the R2-gate consolidation;
  - Round 3, spent on cell 13's attempt 1;
  - cell 12's two-attempt cap;
  - the plan T-G0 line;
  - B-4;
  - R4-01 (i);
  - Round 4, conditioned and then taken, SPENT.
  - **No Round 5 exists.**
- **Operator:** the round-5 check-in was REPORTED at the Round 4 gate. That covered the spend and the fact that every round since R2 has found new facets of the one interrupt-at-cleanup class. CHARC recommends B pass 2 plus fix-without-a-round. **The operator has not replied yet.** If they bound it differently, their word governs.

## 4. WHAT WILL BITE YOU

- **Blame LINES, never the block.** CHARC banked R3-03 on the handler's provenance, and B-2 found a branch this arc wrote inside that pre-arc handler. CHARC made it a register method note.
- **A cell cites precedents that do not exist.** Cell 11's "D67/D69 count-by-ruling" was grepped and was not there. Verify every cited precedent before relaying it.
- **Rulings name states the code does not measure.** Examples: CHARC's `durable=True` at `db-migrate`, the item-4 discriminator that forced `durable=True`, "all pre-arc", and "accepted as landed" when the edit was only authorized. Check each ruling against the code before encoding it, and say so when it is wrong.
- **An interrupt escaping into TestClient's portal HANGS it** (measured past 300 s). The route tests call the function directly. **This is queued for the recipe as harness content, and it is mine.**
- A `bash -c` heredoc holding backticks and apostrophes failed to parse. Write long prompts with the Write tool.
- Every ledger write goes through a temp file with `wc -c` and `git diff --stat` checked. The byte-for-byte quote check is in the Python snippet pattern visible in any of my ledger commits.

## 5. QUEUED (orchestrator's), not started

- The TestClient-portal hang goes into `docs/implementer-dispatch-recipe.md` as harness content.
- Re-anchor the census test on call TEXT, not line numbers. It rotted on every `cli.py` edit in this arc.
- `probe_22i_guard_census.py`'s `#SUMMARY` INFO=140 vs 142.
- RD 1(iii): the exit POST re-render's anchor (AL-6).
- The D67 L1 follow-on rider: read the grant's scope first.
- `cell_depth --live` "showing more than the newest cell" is held for the operator.
