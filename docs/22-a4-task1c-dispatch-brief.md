# 22-A4 EXECUTING — Task 1c dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, Tasks 0b/1/1b landed. Capture your
base yourself (`git rev-parse HEAD`) before your first commit and quote it in the return report.
**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`. **Task 1c is NOT
in it** — it is a CHARC ruling of 2026-09-07 extending the arc's authorized condition. This brief is
its specification. Task 1b's commit is your template throughout.

---

## 1. WHY THIS TASK EXISTS

Task 1b gave the NEW column (`attempt_id`) a typed refusal that reaches the operator, because
`ImmutableJournalFieldError` derives from `ValueError` and both delivery callers already handle that.

**The older, larger sibling family never got that.** `ReservedJournalFieldError` derives directly from
`Exception` (`swing/trades/reconciliation_auto_correct.py:109`) and **is caught nowhere in `swing/`**.
So refusing any of the SEVEN pre-existing `_RESERVED_JOURNAL_FIELDS` members delivers today as an
uncaught CLI traceback and a web 500 with a generic "Unexpected internal error" — the refusal text
never reaches the operator. That is the exact experience CHARC's condition exists to eliminate, still
live on the family that has been shipping longest.

**CHARC ruled the condition EXTENDS to the sibling type** — a base change is the TYPE-LEVEL fix,
discharging all seven raise sites and both handlers in one word, which is the shape his condition
already took for the new column. It lands **inside 22-A4, before the Codex loop opens**, so the loop
and the reviewer-B pass see it as part of the tree they are already reviewing.

---

## 2. SCOPE — bounded by the ruling, and nothing beyond it

- `class ReservedJournalFieldError(ValueError)` — the one-word base change.
- Its docstring gains **ONE sentence**: the two siblings share the delivery contract (a refusal reaches
  the operator through the existing `ValueError` handlers).
- **Discriminating tests in the Task 1b shape** (`tests/cli/test_22a4_corrector_refusal_cli.py` is the
  template): a tier-2 write to ONE reserved field reaches the CLI as a `ClickException` carrying the
  refusal text, and the web route as a **visible refusal, not a 500**. **Pin the RED first against the
  `Exception` base**, by the same method Task 1b used to pin its own red.
- **NO production caller edit.** `swing/cli.py` and `swing/web/**` must be absent from the diffstat —
  that absence is the evidence, exactly as it was in Task 1b.
- **The premise-4 path check** (§3 below), reported with its method.

**NOTHING ELSE.** No other exception type. No handler-tuple audit. No message rewording. No sweep.

**OUT OF SCOPE:** Tasks 3/4/5; the Codex loop (plan Tasks 6-7); the version-mirror test rename (a
post-merge rider, CHARC-ruled — do not touch test names); the live database.

---

## 3. THE ONE THING THAT COULD INVALIDATE THIS TASK — establish it, do not assume it

A re-base to `ValueError` widens what CATCHES the type. **The real hazard is an intermediate
`except ValueError` that NEWLY SWALLOWS a refusal that today propagates.**

CHARC read the file and found: the only `except ValueError` in it (`:343`) sits **upstream** of the
raise — it catches the datetime validator's error and raises the reservation error *from* it — so the
reservation error propagates unchanged. There are **five `except Exception:` sites** (`:680`, `:821`,
`:996`, `:1032`, `:1067`) which already swallow it today and are unchanged by a re-base.

**Your job: establish by EXECUTION or AST — not by reading the call sites you already know about —
whether any of those five sits on a path from any of the seven raise sites** (`:320`, `:344`, `:362`,
`:399`, `:438`, `:452`, `:2203`). Task 1b's own closure walk is the method to reuse.

**If one does: STOP and ROUTE. That is a REPORTED FINDING, not a fix.** The extension does not survive
a finding that the re-base changes behaviour anywhere but the two delivery handlers.

---

## 4. WHAT IS ALREADY ESTABLISHED, AND A COUNT I AM DELIBERATELY NOT GIVING YOU

Verified at the source (by me, and independently by CHARC):

- `ReservedJournalFieldError(Exception)` at `:109`; caught nowhere in `swing/`.
- The family already voted for `ValueError`: `EntryDateCorrectionError(ValueError)` at
  `swing/trades/entry_date_correction.py:215`, whose own docstring says it is a `ValueError` *"so the
  CLI boundary's existing except ValueError -> ClickException discipline applies"* — and Task 1b's
  `ImmutableJournalFieldError(ValueError)` at `:117`. **The `Exception` base on the oldest type is the
  odd one out, not a design.**
- **The load-bearing invariant: ZERO tests assert that the refusal is NOT a `ValueError`, and ZERO
  assert a 500.** Tests that merely name the type keep passing under a base change — they assert the
  subclass, which still exists. This is what makes the change safe, and it is instrument-independent.

**On the number of tests naming the type: three of us have now produced three different counts** (7,
10, 13) from three different grep forms — an exact-call-form grep misses `match=` and tuple forms.
**So no count is given here.** Do not quote one. The invariant above is what matters; if you need a
number, derive it yourself and state the method beside it.

*(This paragraph exists because a blast-radius claim was relayed up this chain unverified and was
overstated. Prefer the invariant to the tally.)*

---

## 5. BINDING CONVENTIONS

- **TDD**: pin the red against the `Exception` base FIRST, see it fail, then the one-word change.
- Conventional commit: `fix(trades): Task 1c — ReservedJournalFieldError re-based to ValueError so the
  seven coupled-column refusals reach the operator instead of a traceback`.
  **No `Co-Authored-By` trailer. No `--no-verify`. No amending.**
- Observable verification (the `-E` is required):
  `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 1c"`
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...`. **Never open or migrate the live DB.**

## 6. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. **Baseline is 12239 passed / 13 skipped /
   0 failed — I measured that myself on your base.** Re-measure and READ it. **If the box is memory
   constrained, use `-n 4` and SAY SO** — it is a valid correctness probe but a weaker probe of the
   xdist-load flake class, and that distinction must survive into your report.
2. `ruff check swing/ --statistics` — a **SEPARATE command**. Exit 0 from a chained
   `pytest ; ruff` is not evidence pytest ran.
3. Trailer audit (KEY-filtered) over `<your base>..HEAD`: empty.
4. **Report an absence with the search that produced it**, and name the instrument's blind spot.

## 7. RETURN REPORT (final chat message — post to no mailbox)

- Commit (sha + subject); what the red actually asserted.
- **The premise-4 path check: the method, and the result for each of the five `except Exception:` sites.**
- Delivery: CLI `ClickException` with the refusal text; web visible refusal, not 500 — through
  **unchanged** callers, with the diffstat as proof.
- Suite + ruff + trailer, quoted, with the worker count you used.
- Anything you did NOT do, and why. Out-of-scope defects: name, do not fix.

## 8. IF YOU GET STUCK

STOP and return with the specific question. A fork stops the task and routes to me. You report to the
orchestrator in chat and to no one else.
