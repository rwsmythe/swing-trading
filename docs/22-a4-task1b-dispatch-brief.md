# 22-A4 EXECUTING — Task 1b dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, **Task 0b + Task 1 already landed
in one commit**. Capture your base yourself (`git rev-parse HEAD`) before your first commit and quote
it in the return report.
**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` — the EXTRACT.
**Task 1b begins at `:319`.** Its tests are the S3 rows `(m8a)`, `(m8b)`, `(m8c)`, `(m8d)`.

---

## 1. SCOPE — Task 1b only

The corrector's typed refusal: `field_name="attempt_id"` on `trades` is refused **before the UPDATE is
composed**, with a typed error, not an abort from the database. CHARC refused to bank this as a
follow-on and widened the envelope by **exactly** `swing/trades/reconciliation_auto_correct.py`.

**The plan specifies this task completely** — the sibling set, the message's content, the exception's
base class, the three call sites and why they are a closure rather than a roster, and what is
explicitly DECLINED. **Read it and follow it. This brief deliberately adds nothing to it.**

**OUT OF SCOPE:** Tasks 3/4/5; the Codex review loop (plan Tasks 6-7, after the ladder); the
version-mirror test rename sweep (**CHARC-ruled 2026-09-07 to happen as a separate rider AFTER the
22-A4 merge** — a rename landing in this arc obscures the 37→38 diff the merge gate must read; do not
touch test names); and **the live database** — migration 0038 is applied only at an operator-witnessed
POST-MERGE gate (extract S6). Nobody in a worktree touches it.

**No sweep.** The widening is exactly one sibling refusal set, one message constant, the shared
predicate at three call sites, and the named assertions. `_preflight_reserved_transitions` is
explicitly DECLINED at the third site, for the reason the plan gives.

---

## 2. WHAT I ALREADY VERIFIED, SO YOU KNOW WHAT IS AND IS NOT CHECKED

I re-derived three of the plan's load-bearing claims at the source before writing this. **All three
hold.** I am telling you which, so you spend your intake on the rest rather than on these:

- `ReservedJournalFieldError` inherits **directly from `Exception`** (`reconciliation_auto_correct.py:109`).
  This is what makes the plan's `ImmutableJournalFieldError(ValueError)` requirement load-bearing
  rather than stylistic: a bare-`Exception` refusal reaches neither existing caller's handler and
  surfaces as a CLI traceback and a web 500.
- `_RESERVED_JOURNAL_FIELDS` has **SEVEN** members at `:178-196`. The plan's note that the range
  `:178-190` was short is **correct** — two members sit at `:194` and `:195`.
- `_update_journal_field` has exactly **FOUR** call sites: `:1348`, `:1749`, `:2542`, `:2680`
  (`:2036` is the definition).

**Everything else in the plan is yours to verify at intake.** A ruling's REASONING is binding; its
FACTS are inputs. **This arc has corrected four such facts so far, every one caught by the
implementing cell — including one my own brief got wrong last dispatch.** If something fails intake,
**STOP and route to me**; do not proceed on a corrected premise of your own invention. Routing is the
valued outcome, not a delay.

---

## 3. READ FIRST

1. The plan's **Task 1b** (`:319`) end to end, and its S3 rows `(m8a)`-`(m8d)`.
2. `swing/trades/reconciliation_auto_correct.py` — the module docstring, `ReservedJournalFieldError`
   and `_RESERVED_JOURNAL_FIELDS`, `_update_journal_field` and its four callers,
   `_preflight_reserved_transitions`, `_apply_tier3_override_inner` and the public
   `apply_tier3_override`. **Read the module, not just the cited lines** — the plan's own closure
   argument was established by an AST walk plus a raw-SQL grep, and it says why an enumeration of
   call sites is not to be trusted on its own.
3. The two delivery callers the typed refusal must reach unchanged: `swing/cli.py` (~`:3929`) and
   `swing/web/routes/reconcile.py` (~`:1640`).
4. `CLAUDE.md` §Gotchas — the reconciliation/classifier entries, the append-only
   `reconciliation_corrections` rule, and the SAVEPOINT-per-discrepancy transaction discipline.

---

## 4. BINDING CONVENTIONS

- **TDD, one red → green → commit.** The plan declares the first red: `(m8a)`'s
  `sqlite3.IntegrityError`. See it fail before writing the implementation.
- Conventional commit, subject as the plan specifies it at the end of Task 1b. **No `Co-Authored-By`
  trailer. No `--no-verify`. No amending.**
- Observable verification before the commit (the `-E` is required or it silently returns empty):
  `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 1b"`
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...` — the bare `swing` entry point resolves to the
  editable install in the MAIN repo, not your tree.
- **Never open or migrate the live DB.** Tests use `tmp_path`.

## 5. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. **Baseline on your base is 12229 passed /
   13 skipped / 0 failed — I measured that myself on this exact head, it is not carried forward from
   an older report.** Re-measure and READ the result.
2. `ruff check swing/ --statistics` — a **separate command**. A chained `pytest ; ruff` reports ruff's
   exit code, and **exit 0 is not evidence pytest ran**; that cost a near-false-green on this arc.
3. Trailer audit, filtered on the trailer KEY: `git log --format="%(trailers:key=Co-Authored-By)" <your base>..HEAD` empty.
4. **Report an absence with the search that produced it.** "There is no X" requires saying what you
   searched and whether it could have found X.

## 6. RETURN REPORT (your final chat message — do NOT post to any mailbox)

- Commit (sha + subject), and what each red step actually asserted.
- **Intake results**: every plan fact you checked, and any you corrected, with the evidence.
- **The three call sites — say how you established the predicate reaches every operator surface**, and
  whether you re-derived the plan's closure argument or relied on it. Either answer is acceptable;
  an unstated one is not.
- The delivery assertions: CLI exit 2 with no traceback, web status 400, both through **unchanged**
  callers. If either needed a production caller edit, that contradicts the plan's premise — stop and
  say so rather than making the edit.
- Suite + ruff + trailer results, quoted.
- Anything you did NOT do, and why.
- Out-of-scope defects noticed: name them, do not fix them.

## 7. IF YOU GET STUCK

STOP and return with the specific question. A fork discovered mid-task stops the task and routes to me
— it does not get settled inside the work. You report to the orchestrator in chat and to no one else.
