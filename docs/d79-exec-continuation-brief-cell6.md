# D79 executing -- CONTINUATION brief (cell 6): round-4 fixes, then Reviewer A round 5

**Audience:** a fresh implementer cell with no prior conversation context. Cells 1-5 have committed T1-T8 and four counted Reviewer A rounds, all `NEW_CRITICAL_MAJOR_FOUND` (majors 3, 3, 3, 1). You fix round 4's findings and run round 5. The orchestrator APPROVED continuing past the round-5 check-in (ledger, "Round-5 check-in").

**These bind, in this order:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`), every section. In particular:
   - section 3: Reviewer A at `strong` with repo access, the five per-round assertions, return at EVERY counted-round gate, stop at the first `NO_NEW_CRITICAL_MAJOR`;
   - section 5: your return goes to chat only; you NEVER post to a mailbox or run role_mail.py.
2. The exec ledger, IN FULL: `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree. It holds every ruling, block-quoted (Forks 1, 2, 3, the read-connection ruling, D79-A2, RA-02, D79-A-01 and the NEW A-F01), together with choices 1-4 and 6-21 (18 confirmed by the orchestrator) and every adjudication.
   - Never edit the block-quoted sections or the orchestrator's sections.
   - You append your cell record, round rows and adjudications.
3. Round 4's evidence, for the shape of the review only: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` (`prompt-r4.md`, `review-r4.txt`, `copowers-findings.md`; cell 5's runner was under WSL `~/d79r4/`).
   - Reuse the prompt's structure, rebuilt on your head's diff.
   - Do NOT give round 5's reviewer any prior-round findings: the prompt must forbid reading them, and must not carry them.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `df3cceb1`. Your diff base is still `618d7b04`. **Cell:** `implementer-opus-high`.

**Stash:** the git stash stack is SHARED with main and other sessions. If you must set code aside for a red-first check, use a temporary WIP commit, or `git stash push -m "<unique tag>"` plus `git stash apply <sha>`, then drop your own entry by tag. Never use a bare `pop`. The pre-existing `SB5.5-exec CORRUPTED...` entry is not yours: never touch it.

## 1. Fix, TDD, one commit per finding

The adjudication text for each is in the ledger under round 4's adjudication.

- **A-F01 (major): ruled, branch A** (ledger, "FORK A-F01"). The P&L, risk-per-share and R-multiple computations move inside `record_exit`'s `try`, before `conn.commit()`. Only the `ExitResult` construction stays after it. Rewrite the "post-commit; pure math" comment and the docstring's transaction paragraph by replacement.
  - RED first: `trades.entry_price` set to TEXT by raw UPDATE; `record_exit` raises, and zero exit fills are written (one before the fix).
  - The existing `record_exit` tests stay green; classify any red as SUPERSEDED (named) or REGRESSION.
- **A-F02 (minor).** `_exit_values_well_formed` holds the quantity to the same bound as the price: an int that cannot convert to a finite float is not well formed. RED first: a `10**400` quantity is refused at both callers.
- **A-F03 (minor).** Rewrite the stale prose by replacement: `routes/trades.py:2991-2992`; plan line 335 (T6-g's first leg, per Fork 3); the template comment at `trade_exit_form.html.j2:102-106`. The test renames (T6-h's name and docstring, its confirm leg, RA-03's docstring) are a naming change only: land them in their OWN commit, apart from any behaviour change. Then re-grep the arc's diff, INCLUDING templates and tests, for the prose of every superseded shape ("Fork 2 synthesis" on a map-bearing claim, `candidate_order_id_<i>` being read), and name every hit in the commit body.
- **A-F04 (minor).** Add the caller-held test the adjudication describes: a caller-held call carrying an envelope, with the authority spied, asserting `CallerHeldTransactionError` and zero authority calls.

## 2. Then

1. The full fast suite GREEN on your head, backgrounded and read off the saved output. The last green was `33a3bfa2`: 15475 passed, 13 skipped.
2. `ruff check swing/` clean; the trailer audit empty across `618d7b04..HEAD`; no added file under `swing/`; nothing under `swing/data/` (RA-07 stays BANKED).
3. **Reviewer A round 5.**
   - The prompt carries the envelope, AL-1..AL-9, all eight rulings and choices 1-4 and 6-21, with challenge invited. Findings against a ruling are TAGGED, not suppressed.
   - A capacity abort (`^ERROR` present, or no verdict token) does NOT count. Wait several minutes and re-run, preserving each failed transcript as `review-r5-attemptN-capacity.txt`.
   - Copy the evidence to the `exec\` directory as `*-r5.*` the moment the assertions pass.
   - Commit the round-5 row and its adjudications.
   - Leave the depth column empty; the orchestrator fills it.
4. **STOP AND RETURN** with round 5's ledger row as your final message, whatever the verdict.
   - If round 5 is clean: fix any minors it raises without another round, name them, re-run the full suite on the final head and report its counts.
   - **Depth:** if you will cross ~380K before the round-5 gate, stop at a clean commit and return what is done instead.

## 3. If a fork appears

STOP and return it with both branches specified. Do not choose for yourself. That includes any part of the A-F01 ruling that turns out to be unencodable against the code.
