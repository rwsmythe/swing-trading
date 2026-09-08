# 22-A4 EXECUTING — the round-4 residuals leg + the uncounted self-sweep (dispatch brief)

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean at `8990f81f`. Capture your base
yourself (`git rev-parse HEAD`) and quote it. **Do not rebase.**

**THIS LEG BUYS NO CODEX ROUND. There is no fifth counted round and you are not authorized to open
one.** Round 4 cleared production — zero critical, zero major against `swing/`. Everything below is a
test, comment or docstring whose *claim* is false; none of it alters behaviour the round-4 verdict
examined. **CHARC concurred on the rule, not the budget:** the scope-of-the-change rule says
suite-verified fix, not a round. **RD's settling-shape endorsement applies here in full.**

## 0. WHICH COPY OF THE RULES GOVERNS YOU

Read the **MAIN-REPO** copies, not your worktree's:
`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md` and
`C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`. **Main's copy wins on any difference.**
This brief lives at `C:/Users/rwsmy/swing-trading/docs/22-a4-r4-residuals-leg-dispatch-brief.md`.

**Ledger** (append to the executing section, do not start a second):
`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.ledger.md`.
**Preserved evidence:** `~/swing-data/review-transcripts/22-a4-exec/`.

**Every line number below was measured by the orchestrator at `8990f81f` and is given so you can find
the thing, not so you can trust it. Ground on symbols and re-locate at read time.**

## 1. THE FOUR FIXES — premises already verified; do not re-derive them, but do re-confirm at the file

Each premise below was confirmed by the orchestrator with a direct read or grep. If any one of them
does **not** reproduce for you, **STOP and report that** — a premise that evaporates is the finding.

**`A4X-R4-01` — the `operator_alternative` path has no discriminating row.**
`grep -c operator_alternative tests/trades/test_22a4_corrector_refusal.py` → **0**. The byte-exact
gate at `reconciliation_auto_correct.py:2745` was added so "every corrector path" would be literally
true, and it is the one path the closure test does not close: delete that line and every `(m8f)` row
still passes. **Fix:** a parametrized `operator_alternative` row that spies on
`_validate_correction_target` and `_read_journal_value` and asserts neither is reached.
**Zero-write assertions CANNOT discriminate this mutant** — no write precedes the backstop on that
path — so the row must assert on the *spy*, not on row counts. **RED first: show it failing with
`:2745` deleted, then restored.**

**`A4X-R4-02` — `Attempt_Id` was dropped in the supersession, and the comment says otherwise.**
`_NON_CANONICAL_SPELLINGS` (`tests/trades/test_22a4_corrector_refusal.py:510-517`) has six members
and `Attempt_Id` is not one; the supersession note at `:431-435` names `Attempt_Id` among the
spellings the deleted `(m8e)` rows covered and says **"not relaxed"**. **That is a false claim in
normative position, in the comment written to record that nothing was lost.** Production refuses
`Attempt_Id` correctly, so this is a coverage regression, not a bypass.
**Fix:** add `"Attempt_Id"` to the tuple (a seventh member, mixed-case), and make the comment true.
**Scope discipline — read this before you get clever:** the enumeration here is a **TEST CORPUS**,
not a guard. The guard is byte-exact and needs no roster. **Do NOT re-engineer this into a generated
or closure-checked list** — that would be the roster-class reflex misapplied to the one place a
literal list is correct. One string and an honest comment.

**`A4X-R4-04` — the test twin of the docstring `d34e1493` already fixed.**
`tests/data/test_migration_0038_attempt_identity.py:150-151` cites `pre_version == target - 1` while
`:177-180` of the **same test** asserts the gate fires at 37→39, where that equation is false.
**Fix:** the docstring cites the implemented condition, exactly as `d34e1493` did for the production
side. **Do NOT touch the implementation — it is the Phase-9 canonical shape and it is right.**
**And do NOT sweep the other 19 occurrences in `swing/data/db.py`** — CHARC has ruled that class
closed from the other end (the CLAUDE.md gotcha text is being corrected to describe what the
implementations do, which is orchestrator content at a lull), so those docstrings will cite a
corrected rule and need no repaint. **Touching them here would be work that CHARC has ruled
unnecessary.**

**`A4X-R4-05` — a naive-substitute claim falsified inside its own leg.**
`tests/trades/test_22a4_clause2_settlement.py:2148` says *"THE NAIVE SUBSTITUTE IS TODAY'S SHIPPED
CODE"*; HEAD ships capture-then-return (`entry.py:1054-1055`, `:1070`). The same paragraph already
names `b3b518f9` as the pre-fix shape, so it contradicts itself. Written by `dd714d4c`, falsified by
`4589c2f9` in the same leg. **Fix: the comment names the shape that WAS the substitute and the commit
that retired it.** **This is a COMMENT-ONLY change to that file — the `(k7a)`/`(k7b)` rows and every
assertion in it stay exactly as they are.**

## 2. THE UNCOUNTED SELF-SWEEP — `SS-N` ids, no round number, no effect on convergence

**This is the remedy the recipe names for residuals of our own fixes: found by SEARCH, not bought at
~400K tokens a round.** The round-4 cell named its own miss precisely — *state-the-class-then-sweep,
missed on the very commit that stated the class.* This sweep is that discipline, performed
deliberately instead of hoped for.

**For each class below, search the ARC'S OWN artifacts** (`swing/trades/reconciliation_auto_correct.py`,
`swing/trades/entry.py`, `swing/data/db.py`, `tests/trades/test_22a4_*.py`,
`tests/data/test_migration_0038_*.py`, and the executing ledger) **and report the full hit list with
a disposition per hit — including NIL results, which are the point of a sweep:**

- **`SS-1` — falsified naive-substitute claims.** Any comment asserting what "today's shipped code"
  or "the current implementation" does, where a later commit in this arc changed it. `A4X-R4-05` is
  one instance; find the rest or report none.
- **`SS-2` — coverage claims that outlived their coverage.** Any "not relaxed", "still covered",
  "superseded by replacement", "each of N" or equivalent claim about what a test set asserts.
  `A4X-R4-02` is one instance.
- **`SS-3` — totality claims with no discriminating row.** Any comment or docstring claiming
  "every path", "all call sites", "no spelling survives" or equivalent, where deleting the thing it
  describes would leave the suite green. `A4X-R4-01` is one instance. **This is the closure-check
  question asked of PROSE.**
- **`SS-4` — rule citations that disagree with the code beside them.** `A4X-R4-04` is one instance.
  **Report hits; fix ONLY those inside this arc's own artifacts** — the `swing/data/db.py` docstring
  family is explicitly out per §1.

**Fix what the sweep finds inside the arc's artifacts; ROUTE anything outside them to the
orchestrator rather than fixing it.** Record every `SS-N` in the ledger with its hits and
disposition. **No round number. This does not touch convergence state, which remains: four counted
rounds, none converged, loop stopped short.**

## 3. BINDING CONVENTIONS

- **TDD, RED first** for `A4X-R4-01` (it is a real new test). The other three are comment/docstring
  corrections — no RED is possible or required; say so rather than inventing one.
- `test(trades):` / `docs(trades):` / `docs(data):` / `docs(22-a4):`. **No `Co-Authored-By`. No
  `--no-verify`. No amending.**
- **Keep the FINAL `-m` paragraph plain prose.** `b3b518f9` already carries a `Tests:` paragraph git
  parses as a trailer — **that one is the orchestrator's to reword at merge; do not add a second.**
  Audit the whole `%(trailers)` output, not just the `Co-Authored-By` key.
- **Use `;` not `&&`** in verification chains.
- **Baseline: 12299 passed / 13 skipped / 0 failed at `-n auto`, 16 workers, on `8990f81f`** —
  measured by the previous cell and re-verified by the orchestrator as arithmetic
  (12294 + 13 new − 8 deleted). **Prefer `-n auto`; state your worker count.** Run the full fast
  suite at the end; there is no review round to bracket it.
- `ruff check swing/ --statistics` as a **separate** command.
- **Never open or migrate the live DB.** Live schema v37; **0038 UNAPPLIED.**
- **The arc's standing locks, all still binding:** `_entry_transaction`, `_durability_probe` and
  `record_entry` are byte-identical since `a32ea9d5` — **measure them by AST source segment, never by
  `git diff --stat`, which shows this arc's legitimate `_settle_by_attempt_identity` work and reads
  like a breach.** PIN 1 not re-opened. `(k7a)`/`(k7b)` keep their broad `pytest.raises(BaseException)`.
  **No production behaviour change in this leg at all** — if you find yourself editing a non-comment
  line in `swing/`, stop and route it.

## 4. RETURN REPORT (final chat message — post to no mailbox)

- Commits (sha + subject).
- For `A4X-R4-01`: what the RED asserted and the measured failure with `:2745` deleted.
- For the other three: the before/after text, and confirmation that no behaviour changed.
- **The full `SS-1`..`SS-4` hit lists with dispositions, NIL results included**, and anything routed
  out rather than fixed.
- Confirmation that `swing/` carries **no non-comment change** in this leg (`git diff` evidence).
- The three locked functions, measured by AST segment against `a32ea9d5`.
- Full suite + ruff + trailer audit, quoted, with the worker count.
- **Which copy of the recipe you read** and its `main` SHA.
- Anything you did NOT do, and why.

**Do not estimate your own context depth** — a cell cannot see it. Report your state; the
orchestrator fills that column.

## 5. IF YOU GET STUCK

STOP and return with the specific question. Report to the orchestrator in chat and to no one else.
**You never run `scripts/role_mail.py` and you post to no mailbox.**
