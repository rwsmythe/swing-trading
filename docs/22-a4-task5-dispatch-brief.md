# 22-A4 EXECUTING — Task 5 dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, Tasks 0b/1/1b/3/4 landed (Task 1c
was CLOSED WITH NO COMMIT — see §3). Capture your base yourself (`git rev-parse HEAD`) and quote it.

## 0. WHICH COPY OF THE RULES GOVERNS YOU — read this first, it overrides your cell definition

Your cell definition names `docs/implementer-dispatch-recipe.md` by a **relative** path, which
resolves to the worktree's copy. **For this dispatch, read the MAIN-REPO copy instead:**

- **`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`**
- **`C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`**
- This brief itself lives at **`C:/Users/rwsmy/swing-trading/docs/22-a4-task5-dispatch-brief.md`**.

The branch is deliberately **not being rebased**. **Where the two copies differ, main's copy wins.**
I measured both blob ids at dispatch time and they are **byte-identical** today across `main` and
`22-a4-exec` — a pointer against future drift, not a report of drift.

**Rules read from `main` @ `61021228`.** That is where I read them; it is **not** a base for your
branch and you must not rebase onto it. §8 asks for the SHA of the copy YOU read — that is the
independent half of the check, not a restatement of this one.

---

## 1. SCOPE — Task 5 only, and it is the arc's DECLARATION

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`.
**Task 5 begins at `:569`.** It is four bullets; read them.

Task 5 rewrites the DECLARED-RESIDUAL block in `swing/trades/entry.py` so it records **what the
residual was, both reproductions, and how each precondition is now supplied** — because the two
reproductions are the reason the design has the shape it has, and deleting them would leave the
shape unexplained. Plus `_entry_transaction`'s and `_CommitOutcome`'s docstrings for the new
observations. **No behaviour change.**

**THE PLAN'S LINE ANCHOR FOR THAT BLOCK IS STALE AND I AM CORRECTING IT HERE.** Task 5 says
`entry.py:973-1030`. Tasks 1/1b/3/4 have all edited that file (Task 4 alone added 226 lines).
**The block's `THE FOLLOW-ON, ruled and deliberately NOT built here:` sentence is at `:1575` as I
write this.** Locate it by CONTENT, not by number, and re-locate it yourself — **symbols and
content are correct throughout this plan; numbers are not.**

**OUT OF SCOPE:** the Codex loop (plan Tasks 6-7 — a separate dispatch); **any test rename**,
including `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises`, whose name Task 4 falsified
and which is queued to a post-merge rider — **record it if the declaration needs it, rename nothing**;
the live database; the commit-message trailer on `b3b518f9`, which is **mine** to resolve at merge.

## 2. WHAT TO READ, AND WHY EACH ONE

1. **The block you are rewriting**, in full. The plan's S10 item 2 says Task 5 "cannot do so
   honestly without having read it."
2. **`docs/superpowers/plans/2026-09-02-phase22-arc-a3-record-entry-caller-half.md` §7** — the
   **limitation-declaration standard** this arc reuses rather than re-invents. Your output is judged
   against it.
3. **`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`** — the design
   record. **S2.3 at `:1525`** and **S2.4 at `:1596`** are where the preconditions are specified, and
   your declaration states how each is now supplied. *(These are not in the EXECUTING extract; that
   is a known and confirmed gap, not a trap.)* **Prefer the extract wherever the two disagree** — the
   design record is known wrong on at least one point (its S2.2 claims `import sys` was already in
   `entry.py`; it was absent until Task 3 added it).
4. **`docs/22-a-merge-request.md` S4.4** — the ruling and the **two reproductions** your rewrite must
   carry forward.

## 3. TASK 1C IS CLOSED WITH NO COMMIT — so you are not looking for it

CHARC extended this arc's condition to re-base `ReservedJournalFieldError` to `ValueError`, then
**SUPERSEDED his own ruling and DECLINED it** after the 1c cell found the re-base would newly enter
two `except (ValidatorRejectedError, ValueError)` handlers in the nightly reconciliation and the
backfill. The type stays on `Exception`. Nothing was written for 1c.

## 4. ONE LIMITATION I AM ROUTING INTO YOUR DECLARATION — and it is MY addition, so verify it

Task 4's cell found, and I verified at the code, that **condition 3's token half is a PRECONDITION,
not a reachable branch**: `_begin_attempt_identity`'s mint `except` arm returns a bare
`_AttemptIdentity()` — token `None` **and** `db_path` `None` — **before** `_resolve_main_db_path` is
reached. So the state "token is `None` with a resolved path" is not producible by today's code. The
gate checks it anyway, for the same reason S2.4 gives for rejecting `"unattempted"`: the gate's
safety must not rest on the internal statement ordering of a different function.

**I am ruling that this belongs in Task 5's declaration rather than in a review-round note**, because
Task 5 is this arc's limitation-declaration surface and a round note has no durable home. **This is
an addition to the plan and therefore the thing most likely to be wrong in this brief** — the last
three generations of this arc each added a fact to a brief and each added fact was the defect.
**Verify it at the code yourself. If you conclude it does not belong here, STOP and route it back.**

## 5. INTAKE — the arc's standing instruction

A ruling's REASONING is binding; its FACTS are inputs you verify at intake. **This arc has now
corrected facts in nine separate rulings, briefs, plan rows and handoffs, and every one was caught by
the implementing cell or the dispatching orchestrator, never by the author.** Task 4 alone failed
three plan facts at intake, one of which would otherwise have shipped a test that passed against the
mutant it existed to exclude.

**Your task is prose about a mechanism, which is exactly where this arc's errors have hidden** — the
design record's own `import sys` claim, a handoff's mis-sited hazard, two of RD's rows that were
passing for the wrong reason. **A sentence in this block that is not true of the code as committed is
the same defect class, in the artifact whose entire job is to be true.** Check each claim you write
against `b3b518f9`'s actual code.

**If a plan fact fails intake, or you find a genuine design fork: STOP and ROUTE to the orchestrator.**
Do not settle it inside the work. The cheapest dispatch of this arc committed nothing and prevented
the most.

## 6. BINDING CONVENTIONS

- **No behaviour change.** The suite must be **unchanged-green** — same pass count, same skips.
- Conventional commit; the plan gives the subject verbatim at the end of Task 5. **No
  `Co-Authored-By` trailer. No `--no-verify`. No amending.**
- **Keep the FINAL `-m` paragraph plain prose.** A paragraph beginning `Word:` is parsed by git as a
  trailer — Task 4's commit did exactly this with a `Tests:` paragraph and it is still awaiting my
  reword at merge. Do not repeat it.
- Observable verification (the `-E` is required):
  `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 5"`
- **ASCII discipline** in anything reaching stdout; this block is a comment, but keep it ASCII anyway
  — the file is read on a cp1252 console.
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...`. **Never open or migrate the live DB.**

## 7. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. **Baseline on your base is
   12278 passed / 13 skipped / 0 failed — measured by the TASK 4 CELL at `-n 4`, not by me.** I have
   not independently re-run the full suite at this point in the ladder; the binding merged-head run
   is mine at the merge gate. **Any deviation from that count on a task with no behaviour change is a
   STOP-AND-ROUTE, not something to explain in the report.**
2. `ruff check swing/ --statistics` — a **SEPARATE command**. Exit 0 from a chained `pytest ; ruff` is
   ruff's exit code and is not evidence pytest ran. **Use `;` not `&&` in verification chains:**
   `git ... | grep -c` returns exit 1 on zero matches and silently skips the rest of an `&&` chain.
3. Trailer audit (KEY-filtered) over `<your base>..HEAD`: `Co-Authored-By` = 0, and **check the whole
   `%(trailers)` output too**, so a prose mis-parse is caught by you rather than by me.
4. **State your worker count.** If the box is memory-constrained use `-n 4` and SAY SO.

## 8. RETURN REPORT (final chat message — post to no mailbox)

- Commit (sha + subject) and the diff's shape.
- **The declaration, walked:** for each precondition S2.3/S2.4 names, the sentence you wrote and the
  code at `b3b518f9` that makes it true. This is the deliverable; the commit is just where it lives.
- **Both reproductions:** confirmation they survive the rewrite, and where.
- Your disposition of §4, with the code you checked.
- Anything in the old block you DELETED, and why it was safe to delete.
- Suite + ruff + trailer, quoted, with the worker count.
- **Which copy of the recipe you read** (§0 says main's) and its `main` SHA.
- Anything you did NOT do, and why. Out-of-scope defects: name, do not fix.

## 9. IF YOU GET STUCK

STOP and return with the specific question. You report to the orchestrator in chat and to no one else.
