# 22-A4 EXECUTING — the fork-fix leg + the confirming round (dispatch brief)

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean at `a32ea9d5`. Capture your base
yourself (`git rev-parse HEAD`) and quote it. **Do not rebase.**

**WHY THIS BRIEF QUOTES A RULING INSTEAD OF POINTING AT IT:** RD's ruling arrived by role-mail, and
**`comms/` is gitignored** (`.gitignore:21`) — the message is not in git and will not survive a
generational handoff. §2 is therefore the ruling's operative text, transcribed. **RD is the author of
every clause in §2; I am the courier.** The original is at
`comms/orchestrator/read/20260908T062659Z-rd-ruled-a4x-r2-01-02-minimal-b-for-window.md` on this
machine while it lasts.

## 0. WHICH COPY OF THE RULES GOVERNS YOU

Read the **MAIN-REPO** copies, not your worktree's:
`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md` (**§3 is your review protocol**)
and `C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`. **Main's copy wins on any
difference.** This brief lives at `C:/Users/rwsmy/swing-trading/docs/22-a4-fork-fix-leg-dispatch-brief.md`.

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`.
**Design record** (S2.3 at `:1525`, S2.4 at `:1596`):
`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`.
**Ledger** (append, do not start a second): `…-primitive.ledger.md`, which now carries three
top-level sections — the executing loop's is the third.

## 1. STATE — where the loop stopped, and why

The A-loop ran **two counted rounds, both `NEW_CRITICAL_MAJOR_FOUND`** (`gpt-5.6-sol` / `high`,
`^ERROR`=0 on both — I verified this from the transcripts, not from a claim). Round 2 raised
**`A4X-R2-01` (CRITICAL)**, a genuine design fork; the loop STOPPED and routed rather than absorbing
it. **RD ruled it. You implement the ruling. You do not re-open it.**

**The fork, in one sentence:** at `_settle_by_attempt_identity`'s `return found` (`entry.py:1021`)
the probe has already returned a row AND the ticker has already matched — durability is **proven** —
yet that `return` sits inside the helper's own `except BaseException`, so a fault there discards the
proof and the caller re-raises over a durable entry. Same shape at `record_entry:1404-1408`.

## 2. THE RULING — RD, 2026-09-08, PRIMARY. Operative text.

> **Form of this section: RE-SET, VERIFIED BY THE RULING DIRECTOR.** Not a verbatim transcription —
> RD's ruling re-set in this brief's voice, reordered and bolded, attributed to him clause by clause.
> RD checked it paragraph-by-paragraph against his posted body on 2026-09-08 and verified every
> operative clause survives, nothing tightened and nothing loosened. **Implement from this text as it
> stands.** (Label added by the successor orchestrator on RD's own correction; the section body is
> unchanged.)

**R1 — branch A (re-probe) is REJECTED.** A second probe does not close the class (the re-probe's own
return is the same window one frame later), adds a second I/O on an already-failing money path, and
contradicts a shipped deliberate pin (`tests/trades/test_22a4_attempt_identity.py:685`, one probe per
attempt — **verified present at that line**). *"A ruling that adds a read to shrink a window by one
frame is not a bound; it is a regress."*

**The class is IRREDUCIBLE.** An asynchronous `BaseException` can land at any bytecode boundary
between obtaining a proof and returning it, including inside the `return`. **No branch closes it;
every branch narrows it.** The real question is the DIRECTION of what is reported when the fault
lands, and whether the surviving residual is declared with its composition.

**The precedent that decides it:** **clause 1 already treats a fault after `commit()` returned as a
degraded SUCCESS.** The outer `except BaseException` catches any fault on the committed path,
interrupts included, and builds the degraded `EntryResult` naming the trade with *"do NOT retry."*
S2.4 states the settle produces *a weaker-but-admissible fact*. So a fault after the PROOF is the
same event one rung down — and today the arc handles the two identical situations **oppositely**:
post-commit fault → true success reported; post-proof fault → true success discarded **and a false
alarm raised, with a false note** (the arm says *"the read FAILED"* when the read succeeded).

### R2 — WINDOW 1: branch B in its MINIMAL form — CAPTURE-THEN-RETURN. The `except` scope is UNCHANGED.

- Declare `proven = None` **before** the `try`. After the ticker corroboration succeeds, bind
  `proven = found`. Then `return proven`.
- In the `except BaseException as settle_error` arm: **if `proven is not None`**, note through
  `log_contained_note` **on `post_commit_error`** that the settle SUCCEEDED (row `<id>`) and a fault
  arrived AFTER the proof (`<safe_text(settle_error)>`), the durable row stands — **and RETURN
  `proven`.** Otherwise the arm behaves **byte-for-byte as today** (note + `None`).
- **This is NOT the cell's framing of B** (narrowing the `except` so the return sits outside it).
  **Narrowing changes WHICH EXCEPTION ESCAPES** on a post-proof fault — the fault instead of the
  original — which is the **R11-03 identity property this module pins**, for no gain over
  capture-then-return, which keeps the proof AND the identity property. Weakest sufficient change.
- **Direction, with its belt named:** a post-proof interrupt is swallowed in favour of a TRUE success,
  exactly as clause 1 swallows a post-commit interrupt in favour of a true success. The fault's text
  reaches the operator through **the same channel clause 1 uses** — the contained note on
  `post_commit_error`, rendered into the degraded result's warning.
- **VERIFY AT THE CODE that the note is actually carried into `warning_text` on the lost-commit
  branch. If it is not, THAT IS A FINDING — route it; it is NOT a licence to add a channel.** (RD
  marked this as his own open question rather than asserting it. Start at
  `post_commit_error_text = safe_text(post_commit_error)` and the lost-commit `warning_text` that
  interpolates it, and determine what `safe_text` does and does not carry.)
- The helper's *"CONTAINMENT IS BaseException"* docstring paragraph gains one sentence: an interrupt
  delivered AFTER the proof is swallowed in favour of the proven entry, as clause 1 swallows one
  after the commit; in both, a TRUE fact is reported.
- **The existing note's wording *"the read FAILED"* must stop being emitted when the read succeeded.**
  A false sentence in an alarm is a defect on its own — a row that reads as a false positive teaches
  the next reader to distrust the check.
- **Untouched:** the byte-locked deferred branch, `with conn:`, and the probe. **PIN 1 is not
  re-opened.** Re-run Task 3's diff-token filter on this commit; it must return **zero** code lines
  on those.

### R3 — WINDOW 2: DECLARED, as a NAMED member of the alarm family the declaration already prices

The two statements at `:1404-1408` cannot be made zero-width. The declaration already enumerates the
alarm family (rollback raised, no `db_path`, no token, probe fails, wrong ticker) and prices them
identically: durable row + reported failure → retry → `ux_trades_one_open_per_ticker` refuses,
**except a ticker closed between the two attempts**. This window is **one more member with the same
cost and the same belt** — not a new uncovered direction.

The declaration gains:
1. the post-proof two-statement window in `record_entry`, as a **named member**;
2. **the composition, stated ONCE for the WHOLE family** (not only this window): *the only path from
   any alarm-family member to a SECOND position is alarm × operator retry × the position closed
   between the attempts — and an exit recorded against a row the operator was told does not exist
   requires him to have SEEN that row*;
3. the bound in its weakest sufficient form: *bounded above by the rate of asynchronous faults
   landing in a two-statement window; **no independence assumed, no strictness claimed**.*

*(Branch C is refused for window 1 — R2 is cheaper and strictly truer. C's residual is accepted for
window 2 because nothing cheaper exists.)*

### R4 — `A4X-R2-02`: three assertions, RED first, by the arc's own mutation discipline

1. **Window-1 row.** Inject a `BaseException` at the `return proven` line via the `(k3b)`
   `sys.settrace` technique, probe returning a corroborated row. Assert: a degraded **SUCCESS** whose
   `trade_id` is the **PROBE's** id, the lost-commit `warning_text` names the trade, and the warning
   carries the post-proof fault's text. **Naive substitute = TODAY'S CODE**, which raises the original
   commit error → RED.
2. **Window-2 row.** Inject at the unpack/replace line. Assert the escaping exception **IS** the
   injected fault (`type(...) is`, the module's existing form) with `__context__` the original commit
   error — the honest chain, not a swallow. **Naive substitute = a `try/except` that swallows it** →
   RED. This pins R3's DECLARED direction.
3. **Probe-count pin across both rows: exactly ONE probe call.** This is the discriminator against
   branch A and keeps the `:685` pin unchanged.

**`(k7a)`/`(k7b)` keep the broad `pytest.raises(BaseException)` catch** per the Task-4 preservation
instruction — **a cell that tightens it while touching these rows re-introduces a session-aborting
INTERNALERROR** that can mask other results.

## 3. THEN: ROUND 3 — the CONFIRMING round

Per RD: **round 3 reviews the FINAL shape after R2/R3/R4 land.** It is the confirming round under the
three-round default. Recipe §3 governs it — the five per-round assertions, scratch relocation, the
copy-per-round `cp` to `~/swing-data/review-transcripts/22-a4-exec/` **the moment the assertions
pass**, and the ledger append.

**A FOURTH ROUND NEEDS THE ORCHESTRATOR'S WRITTEN AUTHORIZATION naming the task-bearing finding.**
Stop and report the full cumulative ledger instead. **A stopped-short loop is a permitted, reportable
outcome and is never relabelled as convergence.** Any NEW fork stops the loop and routes — it does
not get settled inside the work.

**Do not estimate your own context depth** — a cell cannot see it. Report your state; the
orchestrator fills that column.

## 4. BINDING CONVENTIONS

- **TDD, RED first**, with the naive substitute named for each row (R4 names all three).
- `fix(trades): …` / `test(trades): …` / `docs(trades): …`. **No `Co-Authored-By`. No `--no-verify`.
  No amending.**
- **Keep the FINAL `-m` paragraph plain prose.** `b3b518f9` already carries a `Tests:` paragraph git
  parsed as a trailer — **that one is the orchestrator's to reword at merge; do not add a second.**
  Check the whole `%(trailers)` output, not just the `Co-Authored-By` key.
- **Use `;` not `&&`** in verification chains (`git … | grep -c` exits 1 on zero matches).
- **Baseline: 12290 passed / 13 skipped / 0 failed** on `a32ea9d5` at `-n 4` — measured by the
  previous cell, **not by me**. State your worker count; `-n 4` is a weaker probe of the xdist-load
  flake class than `-n auto`.
- `ruff check swing/ --statistics` as a **separate** command.
- **Never open or migrate the live DB.**

## 5. RETURN REPORT (final chat message — post to no mailbox)

- Commits (sha + subject). **What each RED asserted and which naive substitute it failed against** —
  for row 1 that substitute is today's shipped code, so say what it did.
- **Your disposition of R2's open question:** is the contained note carried into `warning_text`? Show
  the code. If not, state it as a finding — you were pre-ruled not to add a channel.
- Confirmation that the deferred branch, `with conn:` and the probe are untouched, **with Task 3's
  diff-token filter output**.
- Round 3's ledger row and its five measurements (model, effort, `^ERROR`, footer, anchored verdict
  token). **Only the verdict token with `^ERROR`=0 proves the review FINISHED.**
- **The SPEND LINE:** round 3's `tokens used`, and the running total (rounds 1-2 were 441,127 +
  590,318 = 1,031,445).
- Full suite + ruff + trailer audit, quoted, with the worker count.
- **Which copy of the recipe you read** and its `main` SHA.
- Anything you did NOT do, and why.

## 6. IF YOU GET STUCK

STOP and return with the specific question. Report to the orchestrator in chat and to no one else.
