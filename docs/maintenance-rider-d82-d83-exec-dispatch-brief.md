# Maintenance rider (D82 + D83 + shadow 900 s): EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`. The orchestrator chose it, and CHARC and RD concur, because condition (v) puts a measurement-neutrality obligation on the archive that observe reads.

**Authority:** the plan was cleared for executing by CHARC (`comms/orchestrator/read/20261020T014312Z-charc-maint-rider-plan-charc-clears-al-10-reas.md`) and by RD on the F5 encoding (`comms/orchestrator/read/20261020T014211Z-rd-maint-rider-plan-rd-clears-the-f5-encodi.md`). Both clearances attach to the plan as written at `maint-rider` `f70640ed`. **A code-bearing change to a task beyond the plan re-opens the clearance: STOP and return instead.**

**Keep your reading NARROW.** Two planning cells ran past the context cap reading the whole record. Read only:
1. **The plan:** `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.md` on the branch. It is the task ladder, and it binds.
2. **The plan ledger**, in the same folder (`.plan.ledger.md`): its rulings sections, for reasons when you need them.
3. **This brief.**
4. **`docs/implementer-dispatch-recipe.md` section 3:** the EXECUTING criterion and the per-round assertions.
5. **The two clearance mail files above**, for transcription only.
6. **The code each task names.**

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider`, branch `maint-rider`, head `8a275a3a`. Run every test from the worktree with `PYTHONPATH=.`, because the editable install resolves MAIN. Live DB: `mode=ro` only; never through `swing`'s `connect`.

## 1. Additions the clearances make (no task changes)

- **First, ledger:**
  - Block-quote both clearances, each with its author: CHARC's items 1-8, and RD's verdict with its L-3 and L-4 paragraphs.
  - Add an exec-ledger section for this cell, or a separate `.exec-ledger.md` beside the plan. That is your choice; say which.
  - Commit.
- **W2 docstring (CHARC item 1), verbatim:** "the warm sorts and dedupes this list itself (`ohlcv_archive.py:666`); the prefix shape pins the composition of the cohort, not an order the warm honours". AL-10's reason is diff-locality, not chunking. If a comment you write cites a reason, use that one.
- **Condition (v) (CHARC item 4):** the T6 step 4 mutation touches the batch (`list`) branch ONLY. Quote both N-V assertions and the mutation result.
- **L-3, as RD worded it, for the merge-report draft:** on this domain the integer form and the unrounded float form are the same function, so there is NO behaviour to test. Say that, not "untested".
- **L-1 becomes a reading rule (CHARC item 5).** It is the orchestrator's at merge; just keep it in the merge-report checklist.

## 2. Execution

Run T1 to T6 in order, per the plan:
- TDD: RED, then GREEN, then a commit per task, conventional, pathspec-only;
- `%(trailers)` empty after each commit; no final `-m` paragraph begins with `Word:`;
- no Co-Authored-By, no `--no-verify`, no amend.

Quote every RED run and every GREEN run, read off saved output.

**Gates before Reviewer A:**
- the FULL fast suite (`python -m pytest -m "not slow" -q -n auto -p no:cacheprovider`) green, read off the saved output;
- `ruff check swing/` clean, and ruff clean on the touched test files;
- every closure grep (T1 step 3, T2, T4 step 3) at ZERO;
- `git diff --stat 033d1053..HEAD -- swing/data swing/trades` EMPTY;
- the condition (vi) and condition (v) mutation checks (T6 steps 3-4), run in scratch and REVERTED. `git diff --exit-code swing/data` must return 0 afterwards.

**If the suite reds in a test outside this rider's files:**
- classify it by MECHANISM;
- reproduce it with `-n 0`;
- never re-run until green;
- report it.

Since D87, the known load-sensitive tests are hardened, so a red is evidence.

## 3. Reviewer A (executing)

Run it per recipe section 3:
- `strong`, with REPO ACCESS, on the diff `033d1053..HEAD`, generated on Windows; tell Codex not to run git;
- the plan's executing-review bundle;
- all five per-round assertions:
  1. banner/model;
  2. `^ERROR` 0;
  3. the footer;
  4. exactly one distinct anchored verdict token, read from the model's region;
  5. the exit file written after codex returned.

**Prompt rules:**
- DESCRIBE the verdict tokens; never write one line-initially. Grep the prompt to prove it.
- No prior-round reads. Relocate any `.codex-*` / `.copowers-findings*` out of the worktree for the loop. Give rulings INLINE or as a ledger copy cut before any round section, per the recipe note at main `db9ab223`. Grep each transcript for the ledger path and the round folders.
- The prompt carries:
  - the envelope;
  - both clearances' operative text;
  - the six D83 conditions;
  - the AL list.
- Invite challenge, especially on condition (v), AL-6/AL-12, and the F10 conditions.

**Evidence:** save each round's prompt, transcript, exit file, diff and findings to `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\exec\`.

**Stops:**
- **STOP AND RETURN at EVERY counted round gate with its ledger row.** Leave the depth column empty.
- Stop at the first clean verdict. After a clean verdict, minors are corrected without another round.
- The round-5 check-in (recipe section 3) binds. It judges the COMPOSITION of the findings, not their count.
- Reviewer B is NOT yours. The orchestrator runs it on the tree being merged.

## 4. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits in order, with their trailers;
- per task: the RED and GREEN results;
- the full-suite counts;
- the closure greps;
- the mutation-check results;
- the round ledger row(s) and findings, each with a proposed disposition;
- every deviation.

**If anything does not fit, STOP and return.** Do not choose for yourself.
