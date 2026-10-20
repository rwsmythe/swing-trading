# Maintenance rider: PLAN REVIEW brief, cell 3 (narrow)

**Audience:** a fresh cell with no prior context. Cell 2 wrote the plan and went over the context cap before the plan was reviewed. You make one ruled edit and then run the plan-stage review rounds. Nothing else.

**Cell:** `implementer-opus-high`. Keep your reading NARROW: the cell-2 cell ran out of context reading the whole comms record. You need only the files listed here.

**Read, in this order, and nothing more unless a finding sends you there:**
1. **The plan**, ON DISK and UNCOMMITTED by design (the recipe commits a plan once, at convergence): `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider\docs\superpowers\plans\2026-10-20-maintenance-rider-d82-d83.plan.md`
2. **The ledger**, committed at `a8221cea`, in the same folder: `2026-10-20-maintenance-rider-d82-d83.plan.ledger.md`. It holds both directors' Round-0 rulings, block-quoted, and intake items I-1 to I-10.
3. **`docs/implementer-dispatch-recipe.md` section 3**, the PLAN-STAGE PROTOCOL, plus the per-round assertions.
4. **Section 2 of `docs/maintenance-rider-d82-d83-plan-continuation-brief-cell2.md`** (main), the review protocol.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider`, branch `maint-rider`, head `a8221cea`. Do not delete or regenerate the uncommitted plan file; it is the work product.

## 1. The ruled edit (orchestrator, I-1)

> I-1 RULED A (widen). The second copy of the false sentence, `tests/latches/test_criteria_lapse.py:1136-1138` (the `_envelope_case` docstring), gets the same replacement as `swing/latches/service.py:393-394` in plan T2 step 2. The envelope widens by those docstring lines only.

1. Apply it to the plan's T2 step 2.
2. Record the ruling in the ledger, block-quoted with the orchestrator as author.
3. Commit the ledger edit, pathspec-only.

**I-4 stays flagged, not resolved:** the plan's change of CHARC's F12 depth relation from `>=` to `>`. CHARC reads it at the plan-stage read. Keep it listed as a deviation in the ledger.

## 2. Review rounds (recipe section 3, plan-stage protocol, exactly)

- **Tier:** `fast`, which is `gpt-5.6-luna` at effort `medium` per cell 2's check. The banner must show it; a `strong` banner is a mis-tiered round.
- **Rounds:** at most THREE counted. Stop at the first round with ZERO task-bearing findings. In any case, stop after round 3 and run the uncounted self-sweep.
- **Blocking findings:** task-bearing only, meaning a finding that changes a task, a test or the envelope. Instrument findings get fixed with no new round.
- **Repo access:** Codex reads the repo from disk through WSL. Tell it not to run git. It may read the live DB with `mode=ro` (WSL python3 can) to check the plan's load-bearing data claims. Pre-generate any diff on Windows.
- **Prompt content:**
  - the envelope;
  - both rulings, by pointer to the ledger;
  - the live measurements the plan cites.
- **Prompt rules:** DESCRIBE the verdict tokens and never write one line-initially; grep the prompt to prove it. Invite challenge.
- **Per-round assertions:**
  - banner and model;
  - `^ERROR` 0;
  - the footer;
  - exactly one distinct anchored verdict token, read from the model's region;
  - the exit file written after codex returned;
  - no prior-round reads;
  - report any content-filter event.
- **Evidence:** save each round's prompt, transcript, exit file and findings to `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\plan\`.
- **Ledger:** keep the round table in the ledger. Leave the depth column empty.
- **STOP AND RETURN at EVERY counted round gate, with its ledger row.** Fix task-bearing findings only after I rule or concur, unless a fix is plainly mechanical and inside the rulings. If you are unsure, return.
- **At convergence,** commit the plan once, pathspec-only.

## 3. Gates and return

- `%(trailers)` empty after each commit; no final `-m` paragraph begins with `Word:`.
- No Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` change.

**Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- the round row;
- the findings, each with your proposed disposition;
- commits;
- deviations.

**If anything does not fit, STOP and return.**
