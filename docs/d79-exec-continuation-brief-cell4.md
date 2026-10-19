# D79 executing -- CONTINUATION brief (cell 4): round-1 fixes, then Reviewer A round 2

**Audience:** a fresh implementer cell with no prior conversation context. Cells 1-3 have committed T1-T8, the supersession classification, the T9 census commands and Reviewer A round 1, which COUNTS. You fix round 1's findings and run round 2.

**These bind, in this order:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`), every section. In particular:
   - section 3: Reviewer A at `strong` with repo access, the five per-round assertions, return at EVERY counted-round gate, stop at the first `NO_NEW_CRITICAL_MAJOR`, and the round-5 check-in;
   - section 5: your return goes to chat only; you NEVER post to a mailbox or run role_mail.py.
2. The exec ledger, IN FULL: `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree. It holds every ruling, block-quoted, together with choices 1-4 and 6-16 and the round-1 adjudication.
   - Never edit the block-quoted sections or the orchestrator's sections.
   - You append round rows and adjudications under "Review (Reviewer A)".
3. Round 1's evidence, for the shape of the review only: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` (`prompt-r1.md`, `review-r1.txt`, `copowers-findings.md`).
   - Reuse the prompt's structure, rebuilt on your head's diff.
   - Do NOT give round 2's reviewer the round-1 findings: the prompt must forbid reading prior-round findings, and must not carry them.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `ac9467a7`. Your diff base is still `618d7b04`. **Cell:** `implementer-opus-high`.

**Stash:** the git stash stack is SHARED with main and other sessions. If you must set code aside for a red-first check, use a temporary WIP commit or `git stash push -m "<unique tag>"` plus `git stash apply <sha>`, then drop your own entry by tag. Never use a bare `pop`. The pre-existing `SB5.5-exec CORRUPTED...` entry is not yours: never touch it.

## 1. Fix, TDD, one commit per finding

- **D79-A1 (major).** `derives_from` truncates quantity with `int()` (`swing/trades/exit_auto_fill.py:1814`), and `_differing_fields` (~:1995) does the same.
  - Compare the quantity as a float, at the resolver's established `isclose` grain (`:1555`), in BOTH places. The one shared grain must survive (RD K5c: "ONE grain in both places").
  - RED first: a literal stored 5.9-share anonymous fill against a typed 5-share exit. Today it matches (verified by execution); after the fix it must not.
  - Also check a map entry with a fractional quantity against the typed int. Today it derives silently; after the fix it raises F1. Classify any existing test that pinned the truncation as SUPERSEDED (named) or REGRESSION.
- **D79-A2 (major): ruled, branch B** (ledger, "FORK D79-A2"). Scope the identities in `exit_record_flags` only:
  - possible partial: `possible_partial|<selected order id, or the selected signature hash when there is no usable id>|<fill_id>`;
  - unreadable: `unreadable_envelope|<linked order id>|<fill_id>`;
  - F1 and (c) are unchanged.
  - Required RED test, the browser shape: two candidates, both listing fill #F as a possible partial. Pick o1 and get the flag render. Switch the radio and values to o2, then Confirm with o1's acknowledgements. Expect 400, re-asked, no fill.
  - Update T7-h/i's identity strings, and the plan's "Naming used below" line, by replacement. Name both in the commit body.
- **D79-A3 (minor).** Rewrite the stale docstrings by replacement: `PossibleDuplicateFill`, and `resolve_exit_auto_fill` at ~:287, :562 and :613. No round is needed for this.

## 2. Then

1. The full fast suite GREEN on your head, backgrounded and read off the saved output. The last green was `c55b55b8`: 15455 passed, 13 skipped.
2. `ruff check swing/` clean; the trailer audit empty; no added file under `swing/`.
3. **Reviewer A round 2.**
   - The prompt carries the envelope, AL-1..AL-9, all five rulings (Forks 1, 2, 3, A2 and the read-connection ruling) and choices 1-4 and 6-16, with challenge invited. Findings against a ruling are TAGGED, not suppressed.
   - Copy the evidence to the `exec\` directory as `*-r2.*` the moment the assertions pass.
   - Commit the round-2 row and its adjudications.
   - Leave the depth column empty; the orchestrator fills it.
4. **STOP AND RETURN** with round 2's ledger row as your final message, whatever the verdict. If round 2 is clean, also re-run the full suite on the final head first and report its counts.

## 3. If a fork appears

STOP and return it with both branches specified. Do not choose for yourself.
