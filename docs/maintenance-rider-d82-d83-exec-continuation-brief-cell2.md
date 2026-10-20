# Maintenance rider: EXECUTING continuation brief, cell 2 (Reviewer A loop)

**Audience:** a fresh cell with no prior context. Cell 1 finished T1-T5 and every T6 gate except the ruff gate, which is ruled below. It then neared the context cap before Reviewer A, so you run the review loop.

**Cell:** `implementer-opus-high`. Keep your reading NARROW.

**Read, and only these:**
1. `docs/maintenance-rider-d82-d83-exec-dispatch-brief.md` (main `e35bb1d6`). It still binds, especially section 3 (Reviewer A) and section 4 (return).
2. The exec ledger on the branch: `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.exec-ledger.md`. It holds the clearances, the T1-T5 results and the T6 gates.
3. `docs/implementer-dispatch-recipe.md` section 3, the executing criterion and the per-round assertions.
4. Cell 1's staged round-1 prompt head: `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\exec\round1\prompt-head.md`. Re-verify it before you use it.
5. The diff and the code it touches, as the review needs.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider`, branch `maint-rider`, head `cf5a6afa`, clean. Tests run with `PYTHONPATH=.`.

## 1. Orchestrator rulings (transcribe them into the exec ledger, block-quoted, with the orchestrator as author)

> RUFF GATE -- RULED (a). The gate reads "zero NEW findings on the touched files". `ruff check swing/` is clean, and so are the three new test files. The 34 findings in `test_criteria_lapse.py` (29), `test_research_health_checks.py` (4 E702) and `test_step_evaluate_warm.py` (1 I001) are all present at base `033d1053` at the same codes and sites (`exec/t6-ruff.txt`). They are not this rider's, and are not fixed here. `test_criteria_lapse.py`'s 28 N802 would be a rename sweep, which T2 step 2 forbids.

> STALE-BY-CONTRAST COMMENT -- FIX, comment only. `research_health.py:994` reads "the other two reasons keep their existing RAW-count pct thresholds (NOT baselined)". After T1 nothing is baselined, so the parenthetical contrasts with a rule that no longer exists. Replace the parenthetical so the comment says the other two reasons are judged by the `_EXCL_*_PCT` floors, and that invalid_ohlc is the rate rule above. Comment only; no code change. That keeps it inside CHARC's clearance, which re-opens only on a code-bearing change.

## 2. Do this

1. **The comment fix.**
   - Commit it pathspec-only.
   - Run `tests/monitoring/`.
   - Re-run the FULL fast suite on the new head, read off the saved output. Production code is unchanged, so this re-establishes the gate on the exact head under review.
2. **Reviewer A**, per the executing brief's section 3:
   - `strong`, with repo access, on the diff `033d1053..HEAD -- swing tests`;
   - the rulings inlined, or the ledgers cut before any round section;
   - no prior-round reads, grepped;
   - all five per-round assertions;
   - DESCRIBE the verdict tokens and never write one line-initially; grep the prompt.
   - Add the ruff ruling and the comment fix to the prompt as context.
3. **Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\exec\round<N>\`.
4. **STOP AND RETURN at EVERY counted round gate with its ledger row.** Leave the depth column empty, and give each finding a proposed disposition. Stop at the first clean verdict.

You NEVER post to a mailbox and never run `scripts/role_mail.py`. **If anything does not fit, STOP and return.**
