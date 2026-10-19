# D79 executing -- CONTINUATION brief (cell 7): round-6 rulings, then Reviewer A round 7

**Audience:** a fresh implementer cell with no prior conversation context. Cells 1-6 committed T1-T8 and six counted Reviewer A rounds, all `NEW_CRITICAL_MAJOR_FOUND` (majors 3, 3, 3, 1, 2, 2). Round 6 had no minors. You encode CHARC's two round-6 rulings and run round 7.

**These bind, in this order:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`), every section. In particular:
   - section 3: Reviewer A at `strong` with repo access, the five per-round assertions, return at EVERY counted-round gate, stop at the first `NO_NEW_CRITICAL_MAJOR`;
   - section 5: your return goes to chat only. You NEVER post to a mailbox or run role_mail.py.
2. The exec ledger, IN FULL: `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree.
   - It holds every ruling, block-quoted: Forks 1, 2, 3, the read-connection ruling, D79-A2, RA-02, D79-A-01, A-F01 with CHARC's addition, R5-02, RD's R5-01, and the NEW CHARC rulings on R6-01 and R6-02. It also holds choices 1-4 and 6-21 and every adjudication.
   - Never edit the block-quoted sections or the orchestrator's sections. You append your cell record, round rows and adjudications.
3. Round 6's evidence, for the shape of the review only: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` (`prompt-r6.md`, `review-r6.txt`, `copowers-findings.md`; cell 6's runner was in WSL at `~/d79r6/run_r6.sh`).
   - Reuse the prompt's structure, rebuilt on your head's diff.
   - Do NOT give round 7's reviewer any prior-round findings: the prompt must forbid reading them, and must not carry them.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `a5ccf93f`. Your diff base is still `618d7b04`. **Cell:** `implementer-opus-high`.

**Stash:** the git stash stack is SHARED with main and other sessions. To set code aside for a red-first check, use a temporary WIP commit, or `git stash push -m "<unique tag>"` plus `git stash apply <sha>`, then drop your own entry by tag. Never use a bare `pop`. The pre-existing `SB5.5-exec CORRUPTED...` entry is not yours: never touch it.

**Scripts:** keep one-off edit scripts self-contained. Cell 6's process slip was a helper that imported another script and re-ran its edits. Never import from an edit script.

## 1. Encode, TDD, one commit per ruling

The ruling text in the ledger is binding. These summaries do not replace it.

- **R6-01: branch A, the raw-anchor rung.**
  - `canonical_envelope_identity(<raw string>)` runs BEFORE `json.loads`, as the first rung of the ladder.
  - A `REFUSED` state goes to `_reject_anchor`: 400, the anchor cleared, the typed values kept. The message names the identity as unreadable and says how to recover (re-open the form).
  - A canonical reading, or a document naming no order, passes to the existing tiers unchanged.
  - The producer check (~`routes/trades.py:3430`) STAYS.
  - RED first, with CHARC's three discriminators:
    - (i) the reviewer's two cases: a padded top-level id with a canonical selected entry, and duplicate root identity keys. Each returns 400, the `record_exit` spy records zero calls, there is no fill, the anchor is cleared and the typed values are kept.
    - (ii) the non-redundancy control: a canonical raw anchor whose selected map entry carries a padded id passes the raw rung and is refused at the producer check, with zero `record_exit` calls.
    - (iii) the existing ladder tests and the T7-k suite stay green unchanged. Any test that submits a refused raw anchor and expects a record is classified SUPERSEDED, by name.
  - The raw rung's docstring says why it is first, and what FORK 2's producer rung still owns.
- **R6-02: branch C, with the contract restated and pinned.**
  - (i) Restate the contract BY REPLACEMENT in two places, in CHARC's words:
    - `record_exit`'s docstring transaction paragraph;
    - a NEW AL-10 in the plan, after AL-9.
  - Do NOT rewrite the ledger: the A-F01 pointer is already there.
  - (ii) The pinning test, two legs:
    - Leg 1: a connection proxy whose `commit()` performs the real commit and then raises. The original propagates, neither swallowed nor re-typed; `in_transaction` is False; and exactly ONE fill is durable, read on a FRESH connection, never the writer's own.
    - Leg 2: the retry of that same linked exit is refused by the (a) guard, naming the durable fill.
  - (iii) ONE ERROR record, through `log_contained_note` (`swing/trades/entry.py:260`, already imported by `exit.py`'s helper). Write it in `record_exit`'s except when `conn.in_transaction` is already False. The text is CHARC's, with the trade id and the order id if there is one.
    - An interrupt in flight keeps the D73 shape: the record is written first, then the interrupt propagates.
    - The D73 helper `_rollback_or_raise` stays UNCHANGED.
    - A test asserts the one record.
  - (iv) No schema, no new type, no new module, and no caller change.

## 2. Then

1. The full fast suite GREEN on your head, backgrounded and read off the saved output. The last green was `d539d273`: 15486 passed, 13 skipped.
2. Gates:
   - `ruff check swing/` clean;
   - the trailer audit empty across `618d7b04..HEAD`;
   - no added file under `swing/`;
   - nothing under `swing/data/` (RA-07 and R5-06 stay BANKED).
3. **Reviewer A round 7.**
   - The prompt carries the envelope, AL-1..AL-10, all twelve rulings and choices 1-4 and 6-21, with challenge invited. Findings against a ruling are TAGGED, not suppressed.
   - A capacity abort (`^ERROR` present, or no verdict token) does NOT count. Wait several minutes and re-run, preserving each failed transcript as `review-r7-attemptN-capacity.txt`.
   - Copy the evidence to the `exec\` directory as `*-r7.*` the moment the assertions pass.
   - Commit the round-7 row and its adjudications.
   - Leave the depth column empty; the orchestrator fills it.
4. **STOP AND RETURN** with round 7's ledger row as your final message, whatever the verdict.
   - **If round 7 is clean:** fix any minors it raises without another round, name them, re-run the full suite on the final head and report its counts.
   - **Depth:** if you will cross ~380K before the round-7 gate, stop at a clean commit and return what is done instead.

## 3. If a fork appears

STOP and return it with both branches specified. Do not choose for yourself. That includes any part of the R6-01 or R6-02 ruling that turns out to be unencodable against the code.
