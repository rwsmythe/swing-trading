# D79 executing -- CONTINUATION brief (cell 5): round-3 fixes, then Reviewer A round 4

**Audience:** a fresh implementer cell with no prior conversation context. Cells 1-4 have committed T1-T8 and three counted Reviewer A rounds, all `NEW_CRITICAL_MAJOR_FOUND`. You fix round 3's findings and run round 4.

**These bind, in this order:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`), every section. In particular:
   - section 3: Reviewer A at `strong` with repo access, the five per-round assertions, return at EVERY counted-round gate, stop at the first `NO_NEW_CRITICAL_MAJOR`, and the round-5 check-in;
   - section 5: your return goes to chat only; you NEVER post to a mailbox or run role_mail.py.
2. The exec ledger, IN FULL: `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree. It holds every ruling, block-quoted (Forks 1, 2, 3, the read-connection ruling, D79-A2, RA-02 and the NEW D79-A-01), together with choices 1-4 and 6-17 and every adjudication.
   - Never edit the block-quoted sections or the orchestrator's sections.
   - You append your cell record, round rows and adjudications.
3. Round 3's evidence, for the shape of the review only: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` (`prompt-r3.md`, `review-r3.txt`, `copowers-findings.md`; cell 4's runner was `~/d79r3/run_r3.sh` in WSL).
   - Reuse the prompt's structure, rebuilt on your head's diff.
   - Do NOT give round 4's reviewer any prior-round findings: the prompt must forbid reading them, and must not carry them.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `df7a74e7`. Your diff base is still `618d7b04`. **Cell:** `implementer-opus-high`.

**Stash:** the git stash stack is SHARED with main and other sessions. If you must set code aside for a red-first check, use a temporary WIP commit, or `git stash push -m "<unique tag>"` plus `git stash apply <sha>`, then drop your own entry by tag. Never use a bare `pop`. The pre-existing `SB5.5-exec CORRUPTED...` entry is not yours: never touch it.

## 1. Fix, TDD, one commit per finding

The adjudication text for each is in the ledger under "Round 3 adjudication".

- **D79-A-01 (major): ruled, branch B** (ledger, "FORK D79-A-01"). A map-bearing claim with no selection resolves to the unique map entry matching the top-level order id and quartet at the one grain. It is treated as a picked candidate: its flags are asked, its order id scopes the identities, and the selected/other hashes are stamped. Zero or several matches get the G1 re-confirm. Synthesis stays for the map-less, no-selection shape only, and the synthesis-site comment is rewritten by replacement to say so.
  - RED first: a default o2 carrying a possible partial, radio omitted -> 400, the partial asked, no fill.
  - Also add a RED for zero matches: a top-level order id no map entry carries -> 400, the refresh notice, no fill. And one for several matches, if the map can carry two entries with the same order id and quartet. If it cannot, say so in the commit body.
  - Re-run T6-h. Its legs are expected green UNCHANGED. Run `tests/web/test_routes/` in full and classify every red as SUPERSEDED (named) or REGRESSION (fixed).
- **D79-A-02 (major).** `_exit_values_well_formed` (`routes/trades.py` ~:2483): `OverflowError` from `float()` on a huge JSON int means not well formed (400, cleared). RED first, at both callers (tier (d) and the selected-entry check).
- **D79-A-03 (major).** `check_exit_preconditions` (`swing/trades/exit.py` ~:407): the "exceeds" refusal must be raised for a huge integer `shares`, with the existing text, without `float(req.shares)` overflowing. RED first: a helper test, plus one caller test.
- **D79-A-04 (minor).** The "quantity as an int" comment (~:3154) is rewritten by replacement to name the isclose grain. Then re-grep the arc's diff for the PROSE of the old grain, not only `int(`, and name every hit you fixed in the commit body. No round is needed for this.
- **D79-A-05 (minor).** Remove the unreachable `candidate_orders` legacy fallback (~:3196) and rewrite the retention-rule coverage text (~:3274) by replacement. If A-01's change touches the same lines, land A-05 after A-01. No round is needed for this.

## 2. Then

1. The full fast suite GREEN on your head, backgrounded and read off the saved output. The last green was `084c9a3a`: 15467 passed, 13 skipped.
2. `ruff check swing/` clean; the trailer audit empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/` (RA-07 stays BANKED).
3. **Reviewer A round 4.**
   - The prompt carries the envelope, AL-1..AL-9, all seven rulings and choices 1-4 and 6-17, with challenge invited. Findings against a ruling are TAGGED, not suppressed.
   - A capacity abort (`^ERROR` present, or no verdict token) does NOT count. Wait several minutes and re-run, preserving each failed transcript as `review-r4-attemptN-capacity.txt`.
   - Copy the evidence to the `exec\` directory as `*-r4.*` the moment the assertions pass.
   - Commit the round-4 row and its adjudications.
   - Leave the depth column empty; the orchestrator fills it.
4. **STOP AND RETURN** with round 4's ledger row as your final message, whatever the verdict. If round 4 is clean, also re-run the full suite on the final head first and report its counts.
   - Round 4 is the last before the brief's round-5 check-in. If it is not clean, return with the counts; do not start round 5.
   - **Depth:** if you will cross ~380K before the round-4 gate, stop at a clean commit and return what is done instead.

## 3. If a fork appears

STOP and return it with both branches specified. Do not choose for yourself. That includes any part of the D79-A-01 ruling that turns out to be unencodable against the code.
