# 22-A4 EXECUTING — Task 4 dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, Tasks 0b/1/1b/3 landed (Task 1c was
CLOSED WITH NO COMMIT — see §2). Capture your base yourself (`git rev-parse HEAD`) and quote it.

## 0. WHICH COPY OF THE RULES GOVERNS YOU — read this first, it overrides your cell definition

Your cell definition names `docs/implementer-dispatch-recipe.md` by a **relative** path, which
resolves to the worktree's copy. **For this dispatch, read the MAIN-REPO copy instead:**

- **`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`**
- **`C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`**
- This brief itself lives at **`C:/Users/rwsmy/swing-trading/docs/22-a4-task4-dispatch-brief.md`**.

The branch is deliberately **not being rebased** for the whole ladder, so published shas move exactly
once, at the merge. **Where the two copies differ, main's copy wins.** I measured both blob ids at
dispatch time and today they are **byte-identical** across `main` and `22-a4-exec` — so this section
is a pointer against future drift, not a report of drift. I am not asserting a staleness I have not
measured; that claim was made in the Task 3 brief and the cell falsified it by reading the blob ids.

**Rules read from `main` @ the SHA in §8.**

---

## 1. THE PLAN OF RECORD DOES NOT CONTAIN YOUR TWO CENTRAL SPECIFICATIONS — this is Task 4's one structural difference from every task before it

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` — the 1,889-line
EXTRACT. **Task 4 begins at `:524`.**

Task 4's ladder specifies `_durability_probe` **"per S2.3"** and `_settle_by_attempt_identity`
**"per S2.4."** **S2 is not in the extract.** The extract carries S10, S4, S5, S3, S6 and Global
Constraints only, and its own preamble says S2 stays in the design record and *"the executor does not
act on"* it. That framing is correct for Tasks 0b/1/1b/3, whose ladder text is self-contained. **It is
not correct for Task 4**, which is the first task whose two central deliverables are specified by
reference. Read them:

- **`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`**
  — **S2.3 at `:1525`** (the probe: the `file:...?mode=rw` URI and why it is `rw` and not `ro`, the
  bounded busy timeout, `open_connection` and not `connect`, the ticker corroboration and the
  deliberate absence of price corroboration) and **S2.4 at `:1596`** (the handler's split shown as
  code, the four gate conditions, the three-branch absence argument, the signature, the return
  contract, and the `BaseException` containment rule).

**The extract's locator for that file is stale and I am correcting it here:** the extract says the
design record is *"on branch `22-a4-plan`."* It is on **`main` and in your own worktree**, and the
worktree's copy is **blob-identical to main's** (measured, `4d089bcd`). Read your local copy.

**Everything else in the extract's warning stands: prefer the extract where the two disagree.** The
design record is wrong against the plan on at least one known point (S2.2 claims `import sys` was
already in `entry.py:8`; it was absent until Task 3 added it). Read S2.3/S2.4 for the *specifications
the extract references and does not carry* — not as a second opinion on anything the extract states.

## 2. SCOPE — Task 4 only

The plan specifies this task completely, **including which tests were deliberately deferred out of
Task 3 into this commit and the single reason all of them were: each names the probe.** Read it and
follow it. **This brief adds nothing to it.**

**OUT OF SCOPE:** Task 5 (the declaration rewrite); the Codex loop (plan Tasks 6-7 — a separate
dispatch); the version-mirror test rename (post-merge rider, CHARC-ruled — **touch no test names**);
the live database.

## 3. TASK 1C IS CLOSED WITH NO COMMIT — so you are not looking for it

CHARC extended this arc's condition to re-base `ReservedJournalFieldError` to `ValueError`, then
**SUPERSEDED his own ruling and DECLINED it** after the 1c cell's repo-wide check found the re-base
would newly enter two `except (ValidatorRejectedError, ValueError)` handlers in the nightly
reconciliation and the backfill. **The type stays on `Exception`.** Nothing was written for 1c; you
will find no 1c commit and should not look for one.

## 4. TWO SHIPPED TEST ROWS YOU MUST NOT TIDY — the broad catch in (k7a)/(k7b) is load-bearing

Task 4 adds a **probe-call-count-of-ZERO** assertion to `(k7a)` and `(k7b)`, which already ship from
Task 3 in `tests/trades/test_22a4_clause2_settlement.py:607-700`.

`(k7b)` uses `pytest.raises(BaseException)` with `type(escaping) is _RaisingContext` asserted
separately, **and that shape is deliberate**: the row plants an exception whose `__context__` getter
raises, pytest's traceback formatter walks `__context__`, and an uncaught escape there produces a
**session-aborting `INTERNALERROR` rather than a readable red** — strictly worse than a failure,
because it can mask other results. The Task 3 cell hit this inside that row and wrote the reason into
the test's own comment. **Do not "tighten" that `pytest.raises(BaseException)` to the concrete type
while adding your assertion.** Discrimination is preserved by the `type(...) is` assertion beside it.

*(Stated because the prior generation's handoff put this hazard in `(RD-a4)`'s four-row matrix in
Task 4. It verified as wrong: the plan puts the subclass-descriptor axis in `(k7a)`-`(k7b)` in Task 3
explicitly, and says at `:1113` that scheduling it in `(RD-a4)` would have left Task 3 vacuously
green. `(RD-a4)`'s axes are `inside_except` and `chained`. The hazard is real; its location in the
handoff was not.)*

## 5. INTAKE — the arc's standing instruction

A ruling's REASONING is binding; its FACTS are inputs you verify at intake. **This arc has now
corrected facts in six separate rulings, briefs and handoffs — including three of the orchestrator
role's own and one of CHARC's — and every one was caught by the implementing cell, never by the
author.** §1 and §4 of this brief are two more, caught before dispatch this time rather than after.

**If a plan fact fails intake, or you find a genuine design fork: STOP and ROUTE to the orchestrator.**
Do not settle it inside the work. A stop is the valued outcome, not a delay — the cheapest dispatch of
this arc committed nothing and prevented the most.

**Where the plan scopes a check to one module or one file, consider whether the question is actually
about a module.** That distinction is exactly what that stop turned on.

## 6. BINDING CONVENTIONS

- **TDD**, one red → green → commit. The plan names the REDs explicitly. **A red that does not
  distinguish the shipped implementation from its naive substitute has not been pinned** — and
  `(pr1)`-`(pr5)` (`:1376`) are written as exactly that: five probe design requirements, each with the
  assertion that goes red if the requirement is dropped.
- **`(k3a)`'s ordering half and `(k2)`'s probe-call-count are additions to rows Task 3 already
  shipped**, and the plan states at `SS-14` why the ordering assertion could not be written in Task 3
  and would have passed vacuously there. Preserve what those rows already assert.
- Conventional commit; the plan gives the subject verbatim at the end of Task 4. **No
  `Co-Authored-By` trailer. No `--no-verify`. No amending.**
- Observable verification (the `-E` is required):
  `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 4"`
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...`. **Never open or migrate the live DB.**
- **Plan line anchors into `swing/trades/entry.py` have DRIFTED** by Tasks 1/1b/3 (e.g. `:884` →
  `:1012`). **Symbols are correct; numbers are not. Ground on symbols.**

## 7. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. **Baseline on your base is
   12247 passed / 13 skipped / 0 failed** — measured by me at `-n 4`, and the Task 3 cell's `-n auto`
   run agrees on that number. Re-measure and READ it. **State your worker count.** If the box is
   memory-constrained use `-n 4` and SAY SO — it is a weaker probe of the xdist-load flake class, and
   that distinction must survive into your report.
2. `ruff check swing/ --statistics` — a **SEPARATE command**. Exit 0 from a chained `pytest ; ruff` is
   ruff's exit code and is not evidence pytest ran. **Use `;` and not `&&` in verification chains:**
   `git ... | grep -c` returns exit 1 on zero matches, which silently skips the rest of an `&&` chain.
3. Trailer audit (KEY-filtered) over `<your base>..HEAD`: empty.
4. **Report an absence with the search that produced it, and name the instrument's blind spot.** A
   count without its method is not a finding.

## 8. RETURN REPORT (final chat message — post to no mailbox)

- Commit (sha + subject); **what each RED actually asserted, and which naive substitute it failed
  against** — for `(pr1)`-`(pr5)` that is the plan's own stated purpose for the block.
- **Intake results: every plan fact you checked; any corrected, with evidence.** Explicitly: whether
  S2.3's `open_connection(..., uri=True, busy_timeout_ms=...)` signature is the one the code actually
  exposes, and whether `find_trade_id_by_attempt_id` as Task 1 shipped it matches S2.3's contract.
- **`(RD-a4)`'s matrix: the value you MEASURED in each of the four cells**, and confirmation that rows
  1, 2 and 4 are identical under both predicates so row 3 is the whole delta.
- Confirmation that `(k7a)`/`(k7b)` still catch broadly (§4) and what your added assertion is.
- Suite + ruff + trailer, quoted, with the worker count.
- **Which copy of the recipe you read** (§0 says main's) and its `main` SHA.
- Anything you did NOT do, and why. Out-of-scope defects: name, do not fix.

## 9. IF YOU GET STUCK

STOP and return with the specific question. You report to the orchestrator in chat and to no one else.
