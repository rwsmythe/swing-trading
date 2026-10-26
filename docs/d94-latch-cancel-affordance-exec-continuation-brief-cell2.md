# D94 (a)+(b) -- EXECUTING continuation brief, cell 2 (the round-1 rulings, then round 2)

**Audience:** a fresh cell with no prior context. Cell 1 executed Tasks 1-5, ran the Task-6 gates and Reviewer A round 1, then neared the context cap.

**Cell:** `implementer-opus-high`. Keep your reading NARROW.

**Read, and only these:**
1. **The original brief:** `docs/d94-latch-cancel-affordance-exec-dispatch-brief.md` (main `7b2dca9e`). It still binds.
2. **The exec ledger on the branch:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.exec.ledger.md`, plus the plan beside it.
3. **The round-1 rulings of record, from the main repo:**
   - CHARC: `comms/orchestrator/read/20261026T041655Z-charc-d94-exec-r1-charc-rules-r1-1-i-book-cont.md`;
   - RD: `comms/orchestrator/read/20261026T041752Z-rd-d94-exec-r1-rd-rules-r1-1-i-book-control.md`.

   Block-quote BOTH, in full, in the exec ledger, with their authors.
4. **`docs/implementer-dispatch-recipe.md` section 3.**
5. **The round-1 evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\round1\`.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d94-cancel`, branch `d94-cancel`, head `c9359ff7`. Run with `PYTHONPATH=.`; the full suite at `-n 8`. Read the live DB with `mode=ro` only.

## 1. The rulings (both directors, identical dispositions; RD governs semantics)

**R1-1: (i). G2 suppresses the TESTIMONY controls only, never the book control.**
- G2 withholds the correction control and the LEDGER-keyed cancel control.
- The shipped BOOK cancel control for an order STILL RESTING stands.
- **No code change** beyond the comment that names the two control sources.
- **ONE new discriminator, RED first against an implementation that suppresses every cancel control:**
  - Setup: a fill-cleared latch, plus an accepted validity child on the latest place, plus the order STILL IN the book.
  - Expected: the fill line; exactly ONE cancel form (source book, no W2 note); no correction control; no ledger control.
- **Declared limitation**, in RD's words, in the ledger: a STALE book status renders a book control beside the "filled" line.

**R1-2: A. Keep the ticker-wide indeterminate skip** (`latches.py` about :3441) as a DECLARED LIMITATION.
- Use **RD's TRUE GROUND**, not the orchestrator's reason, which RD corrected: under an indeterminate ticker the book IS known.
- RD's four parts:
  - bounded and self-limiting, via `INDETERMINATE_ORDER_STATUSES`;
  - the just-cancelled order is PENDING_CANCEL, so it is resting, so it gets the book control;
  - an honest unknown: the indeterminate note comes from the same predicate;
  - pre-existing, so it is BANKED.
- Write it into the ledger, and into a #31-true comment AT the skip.
- **The re-open trigger, named:** an indeterminate status persisting across a session boundary on a ticker carrying an accepted, absent, unexplained row.

**R1-3: FIX.** One helper, `_governing_validity_child`, called from both `_displaced_cycle_prompts` and `_accepted_row_gate`. No behaviour change.

**R1-4: FIX.** The `validity_explained` and template comments use RD's verbatim wording: "a fill explains the place whatever its child says; a recorded cancel explains an accepted row whose order is gone".

**No clearance is re-opened.**

## 2. Then

1. Apply 1-4 as commits: pathspec-only, empty trailers, no amend. The new discriminator goes RED first, with the RED quoted.
2. **Run the full fast suite at `-n 8`, read off the saved output.**
   - KNOWN, outside the arc: `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py::test_ohlcv_cache_get_or_fetch_invariant` reds on this branch. It is a wall-clock anchor, FIXED on main at `00d2d818` (test-only), and the merged-head run reads it in.
   - Report it as that known red. **Do NOT fix it on this branch.**
   - ANY other red: classify it by mechanism, reproduce it at `-n 0`, and STOP.
3. Ruff: clean on `swing/`, and zero NEW findings on the touched test files. The envelope diff stays EMPTY.
4. **Reviewer A round 2:**
   - `strong`, with repo access, on the diff `8acea975..HEAD -- swing tests`;
   - all five assertions;
   - the verdict tokens described, never written line-initially, with the prompt grepped;
   - the rulings inlined, or a ledger copy cut before its round section;
   - relocate `.codex-*` and `.copowers-*`, then restore them; no prior-round reads, grepped;
   - the per-item checklist plus R1-1's and R1-2's dispositions, with challenge invited;
   - save to `...\exec\round2\`.
5. **STOP AND RETURN at the round-2 gate** with its ledger row and findings, each with a proposed disposition. Leave the depth column empty.

You NEVER post to a mailbox and never run `scripts/role_mail.py`. **If anything does not fit, STOP and return.**
