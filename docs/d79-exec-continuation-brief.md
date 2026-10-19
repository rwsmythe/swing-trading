# D79 executing -- CONTINUATION brief (cell 2)

**Audience:** a fresh implementer cell with no prior conversation context. Cell 1 committed T1-T5, stopped at two forks, and returned past the 400K depth cap. You continue from its committed work. You are not redoing anything.

**The binding brief is still `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`).** Read it IN FULL first. Its sections 0 (the read list), 2 (TDD, commits, envelope), 3 (Reviewer A at `strong`, repo access, the five assertions, return at EVERY counted-round gate), 4 (merge gate), 5 (return report: chat only, NEVER post to a mailbox, never run role_mail.py) and 6 (stop conditions) all bind unchanged. This file only adds what has changed since that brief was written.

**Authority:** unchanged (the brief's header). Cell: `implementer-opus-high`, for the brief's stated reason.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`. Your diff base is still `618d7b04`. HEAD at dispatch is `efd3a80f` (T5 at `417b4674` plus three ledger commits by the orchestrator).

## 1. State you inherit (orchestrator-QA'd against disk)

- `1b470e99` T1, `62cbcc1d` T2, `bb26bfad` T3, `4b12f8f3` T4, `417b4674` T5. Read their commit bodies; they name the six tests already superseded.
- **Untracked on disk: `tests/cli/test_d79_cli_exit_confirm.py`.** Cell 1 wrote the T8 tests and left them uncommitted because they are red until T8. Read them against plan T8 before you use them. They are yours to keep, fix or rewrite, and they get committed with T8.
- Baseline fast suite on the untouched base: **15380 passed, 13 skipped, 0 failed** (cell 1, 709.96 s). You do not re-run the baseline. **The full suite has NOT been run since T5**: run it once, before T6, backgrounded (~12 min; it outlives the 600 s Bash timeout), and read the saved output. A red there is cell 1's to classify, and you classify it before writing T6 code.
- The exec ledger exists: `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md`. **Read all of it.** It holds cell 1's record, the four encodings cell 1 made without a fork, and both fork rulings, block-quoted. You append a `## Review (Reviewer A)` section per counted round. Never edit the block-quoted sections or the orchestrator's sections.

## 2. The two fork rulings (full text in the ledger; these bind)

**Fork 1, CHARC: A1, with the helper PURE.**
- `check_exit_preconditions(trade: Trade | None, ...)` goes in `swing/trades/exit.py`. It takes no connection and does no read. It raises, in this order and with the EXISTING texts, exactly the six refusals: invalid reason; shares <= 0; `ExitPriceRefusedError`; "not found"; "not active"; "exceeds".
- **`record_exit`:** CallerHeld check -> F2-(iii) envelope read (stays before BEGIN) -> BEGIN IMMEDIATE -> `get_trade` -> `check_exit_preconditions` -> the identity guard -> the writes. The pre-BEGIN argument checks are REMOVED, not kept alongside. The docstring's transaction paragraph is rewritten by replacement, naming the accepted cost (an argument refusal now takes one BEGIN/ROLLBACK).
- **The route:** inside the existing `try` whose `except ValueError` drives the d2-strict re-render, after the anchor ladder and BEFORE any flag (F1 and unreadable alike). **The orchestrator's intake check corrects one fact:** the route holds NO trade row before `record_exit` today. It reads one with `get_trade` (imported at `routes/trades.py:19`) on the short read-only connection T7 step 2 opens for the flag reads, closed before `record_exit`'s connection opens. Its comment names the window: the read is outside the lock, the in-lock call is the barrier, and this call only orders the refusal before the question.
- **Discriminators, RED first:**
  - (i) `test_exit_rerender_anchor.py` green UNCHANGED (T7-k);
  - (ii) an over-size, price-edited claimed POST -> 400, "exceeds", NO confirm text, NO `acknowledged_flag` input, no fill;
  - (iii) the spy pin: called from BOTH sites on an accepted POST and from the ROUTE ONLY on a refused one, patched where each site resolves the name;
  - (iv) a unit test over a synthetic `Trade` for each of the six texts, plus `inspect.signature` showing no `conn`.
- **The order-change check** (ledger, intake item 2): grep for any existing test pinning "argument refusal before envelope refusal" at the SERVICE level. A red there is SUPERSEDED (named) only if it pins exactly that order; otherwise it is a regression.
- **Placement:** land the helper and test (iv) as their own commit before T7 (`refactor(trades): T7a -- ...`); the route call and (ii)/(iii) land in T7.

**Fork 2, orchestrator: synthesize from the top-level quartet whenever no selection is sent.**
- The route synthesizes `selected_entry` from the top-level quartet whenever the claim is a dict and `authoritative_selected is None`, map or no map. There is still ONE synthesis site, and its comment names both shapes.
- New RED test **T6-h**: a claimed multi-entry envelope, top-level o2, no candidate inputs:
  - (i) price edited -> 400, F1 `NO_CANDIDATE` naming "price", no fill. **REQUIRED confirm leg (RD's suggestion, adopted):** the flagged re-render's `_checked_radios(body) == [<o2's index>]`; after confirm, the persisted `selected_candidate_signature_hash` is o2's and the top-level `schwab_order_id == "o2"`;
  - (ii) typed values equal to o1's entry -> 400, F1 `OTHER_ORDER` naming o1, no fill;
  - (iii) unedited -> `schwab_auto`, one fill, 200 (the control).

## 3. What remains, in order

1. The full fast suite on `efd3a80f` (above).
2. T6 (plan T6 plus Fork 2 and T6-h).
3. T7a (the Fork 1 helper and (iv)).
4. T7 (plan T7 plus the Fork 1 route call and (ii)/(iii)).
5. T8.
6. The T6 supersession classification over ALL of `tests/web/test_routes/` (brief section 2).
7. T9 step 1, and the census commands checked against the live DDL (`mode=ro`, schema only) and written into the exec ledger.
8. The full fast suite green, then Reviewer A.

**Reviewer A's prompt carries, in addition to the brief's list:**
- the four cell-1 encodings from the ledger, challenge invited;
- both fork rulings, as rulings: findings against them are TAGGED, not suppressed;
- the AL-1..AL-9 accepted limitations with their reasons.

**Return at every counted-round gate**, per the brief, with that round's ledger row as your final message.

## 4. If a fork appears

STOP and return it with both branches specified (brief section 1). Do not choose for yourself. That includes any ruling above that turns out unencodable against the code, and any fact that does not hold.
