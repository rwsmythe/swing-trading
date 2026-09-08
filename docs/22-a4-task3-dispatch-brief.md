# 22-A4 EXECUTING — Task 3 dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, Tasks 0b/1/1b landed (Task 1c was
CLOSED WITH NO COMMIT — see §2). Capture your base yourself (`git rev-parse HEAD`) and quote it.

## 0. WHICH COPY OF THE RULES GOVERNS YOU — read this first, it overrides your cell definition

Your cell definition tells you to read `docs/implementer-dispatch-recipe.md` by a **relative** path,
which resolves to the worktree's copy. **For this dispatch, read the MAIN-REPO copy instead:**

- **`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`** — rules read from `main`.
- **`C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`** — same.
- This brief itself lives at **`C:/Users/rwsmy/swing-trading/docs/22-a4-task3-dispatch-brief.md`**.

**Your worktree's copies are stale BY DESIGN and are not being rebased.** The branch is deliberately
held on its base for the whole ladder so published shas move exactly once, at the merge. Where the two
copies differ, **main's copy wins.** (This is CHARC's composed form of THE BASE CARRIES THE RULES: the
invariant is that the cell reads CURRENT rules, not that the worktree contains them. A pointer to
main's copy satisfies it; a brief clause paraphrasing a rule never does — so this section points, and
paraphrases nothing.)

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` (in your worktree
is fine — it is the arc's own artifact, not a rules doc). **Task 3 begins at `:433`.**

---

## 1. SCOPE — Task 3 only

The three observations (two new fields): `_CommitOutcome` gains `resolution` and `cleanup_raised`; the
shared non-mutating `_read_resolution`; the immediate path's ladder annotated without touching
`raise cleanup_error from write_error`; `_CONTEXT_SLOT` + `_exit_rollback_failed`; the ambient capture;
the pre-arc gate split; and the deferred-path observation block in `record_entry`.

**The plan specifies this completely, including a scheduling rule written against a class that has cost
it four rounds. Read it and follow it. This brief adds nothing to it.**

Two points the plan makes that are easy to skim past, flagged only as pointers:
- **`import sys` is NOT currently in `swing/trades/entry.py`** (zero hits, verified at round 0). Task 3
  is where it arrives, for the `sys.exc_info()[1]` ambient capture. **`sys.exc_info()[1]`, not
  `sys.exception()`** — the latter is 3.12+ and `pyproject.toml:9` declares `>=3.11`.
- The plan's **"WHAT IS EXPLICITLY NOT HERE"** checklist excludes six rows **for one single reason:
  each names the probe**, and `_durability_probe` / `_settle_by_attempt_identity` do not exist until
  Task 4. Do not reach for them.

**OUT OF SCOPE:** Tasks 4 and 5; the Codex loop (plan Tasks 6-7); the version-mirror test rename
(post-merge rider, CHARC-ruled — touch no test names); the live database.

## 2. TASK 1C IS CLOSED WITH NO COMMIT — so you are not looking for it

CHARC extended this arc's condition to re-base `ReservedJournalFieldError` to `ValueError`, then
**SUPERSEDED his own ruling and DECLINED it** after the 1c cell's repo-wide check found the re-base
would newly enter two `except (ValidatorRejectedError, ValueError)` handlers in the nightly
reconciliation and the backfill. **The type stays on `Exception`.** Nothing was written for 1c. It is
banked to CHARC's register as D34's third instance. You will find no 1c commit and should not look for
one; `swing/trades/reconciliation_auto_correct.py` is not yours this task.

## 3. INTAKE — the arc's standing instruction

A ruling's REASONING is binding; its FACTS are inputs you verify at intake. **This arc has now
corrected facts in five separate rulings/briefs — including two of the orchestrator's own and one of
CHARC's — and every single one was caught by the implementing cell, never by the author.** The most
recent stopped a task outright and was right to.

**If a plan fact fails intake, or you find a genuine design fork: STOP and ROUTE to the orchestrator.**
Do not settle it inside the work. A stop is the valued outcome, not a delay — the cheapest dispatch of
this arc committed nothing and prevented the most.

**Where the plan scopes a check to one module or one file, consider whether the question is actually
about a module.** That distinction is exactly what the last stop turned on.

## 4. BINDING CONVENTIONS

- **TDD**, one red → green → commit. The plan names the REDs explicitly, including which naive
  substitutes each must fail against — `(k5)` against `return False`, `(k6a)`/`(k6b)` against two named
  naive immediate-path implementations. **A red that does not distinguish the shipped implementation
  from its naive substitute has not been pinned.**
- Conventional commit; the plan gives the subject verbatim at the end of Task 3. **No `Co-Authored-By`
  trailer. No `--no-verify`. No amending.**
- Observable verification (the `-E` is required):
  `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 3"`
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...`. **Never open or migrate the live DB.**

## 5. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. **Baseline is 12239 passed / 13 skipped /
   0 failed — measured by me at `-n auto` on your base.** Re-measure and READ it. **State your worker
   count.** If the box is memory-constrained use `-n 4` and SAY SO — it is a weaker probe of the
   xdist-load flake class, and that distinction must survive into your report.
2. `ruff check swing/ --statistics` — a **SEPARATE command**. Exit 0 from a chained `pytest ; ruff` is
   ruff's exit code and is not evidence pytest ran.
3. Trailer audit (KEY-filtered) over `<your base>..HEAD`: empty.
4. **Report an absence with the search that produced it, and name the instrument's blind spot.** A
   count without its method is not a finding. If you give a number, give how you got it and what it
   cannot see.

## 6. RETURN REPORT (final chat message — post to no mailbox)

- Commit (sha + subject); **what each RED actually asserted, and which naive substitute it failed
  against** — that is the plan's own scheduling rule and it is the thing to demonstrate.
- Intake results: every plan fact you checked; any corrected, with evidence.
- **`(k3a)`'s AST property**: what shape it rejects, and confirmation the `if not immediate:` branch is
  unedited (`with conn:` suite stays exactly `yield`).
- The `_CONTEXT_SLOT` docstring's citation: anchored on CONTENT plus upstream digest + fetch URL,
  **never bare line numbers, never a local copy's hash**.
- Suite + ruff + trailer, quoted, with the worker count.
- **Which copy of the recipe you read** (§0 says main's) and its `main` SHA.
- Anything you did NOT do, and why. Out-of-scope defects: name, do not fix.

## 7. IF YOU GET STUCK

STOP and return with the specific question. You report to the orchestrator in chat and to no one else.
