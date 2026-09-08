# 22-A4 EXECUTING — Tasks 6-7 (the Codex A-loop) dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, Tasks 0b/1/1b/3/4/5 landed. Capture
your base yourself (`git rev-parse HEAD`) and quote it.
**This is the LAST dispatch before the gates.** After you return: orchestrator QA, reviewer B, the
merge gate where both directors wait, a blocking live pipeline run, and the operator-witnessed
migration. **You are the last automated net.**

## 0. WHICH COPY OF THE RULES GOVERNS YOU — read this first, it overrides your cell definition

Your cell definition names `docs/implementer-dispatch-recipe.md` by a **relative** path, which
resolves to the worktree's copy. **For this dispatch, read the MAIN-REPO copy instead:**

- **`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`** — **§3 is your protocol and
  this brief does not restate it.** Read §3 in full, at main's copy, before you invoke anything.
- **`C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`** — §5.1.
- This brief lives at **`C:/Users/rwsmy/swing-trading/docs/22-a4-tasks67-codex-loop-dispatch-brief.md`**.

**Where the two copies differ, main's copy wins.** Measured at dispatch time: the recipe and
`harness-architecture.md` are **byte-identical** across `main` and `22-a4-exec` today. **Rules read
from `main` @ `86f92b43`** — that is where I read them; it is **not** a rebase target. §7 asks for the
SHA of the copy YOU read, which is the independent half of this check, not a restatement of mine.

**A brief clause paraphrasing a rule is not the rule.** Everything mechanical about the loop —
the invocation, the five per-round assertions, scratch relocation, copy-per-round preservation, the
stop-at-first-clean-verdict rule, the adjudication standards — **lives in recipe §3 and you follow it
there.** This brief carries only what §3 cannot: this arc's scope, its authorities, its baseline, and
the two obligations attached to it by name.

---

## 1. SCOPE — plan Tasks 6 and 7, in that order, with the loop between them

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`.
**Task 6 at `:580`, Task 7 at `:586`.**

1. **Task 6 — the PRE-REVIEW full-suite gate.** Full fast suite green and `ruff check swing/` clean
   **before** you open round 1, so the review converges on a green diff.
2. **The A-loop**, per recipe §3, over the whole arc diff `2d9e4a34..HEAD` (six commits: Tasks 0b+1,
   1b, 3, 4, 5).
3. **Task 7 — the POST-CONVERGENCE final-head gate.** Full suite re-run on the final head; the number
   in your report is READ OFF THAT RUN. Trailer audit over `<base>..HEAD`.

**OUT OF SCOPE:** any test rename (the post-merge rider owns them — including
`test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises`, whose name Task 4 falsified: **record
it, rename nothing**); the live database; the merge itself; **the commit-message trailer on
`b3b518f9`, which is MINE** — see §4.

## 2. REVIEW TIER, AND THE TWO GATES THAT ARE MINE AND NOT YOURS

**TIER: `strong`.** This is production-code review and recipe §3 forbids tiering it down. Assert the
banner reads **`gpt-5.6-sol`** and `model_reasoning_effort` reads **`high`**; `gpt-5.5` means you are
on the retired profile and **the round does not count.**

**ROUND 0 IS A PREMISE + FORK CENSUS WITH NO CODEX** (plan-stage protocol, binding from this arc's
executing dispatch onward). Before round 1: census the premises and any open design forks across the
six commits. **A fork goes to me as ONE PACKET, and no review round opens while a ruling is
outstanding.** A fork discovered mid-loop STOPS the loop and re-enters round 0. *(Why: this arc's own
writing-plans loop settled design INSIDE the review loop at one ruling per round, and rounds 8, 9 and
10 each spent most of their yield on the previous ruling's residue — round 10 returned 6 of 7 findings
residual. The loop was reviewing its own wake.)*

**THREE COUNTED ROUNDS IS THE DEFAULT. A FOURTH REQUIRES MY WRITTEN AUTHORIZATION NAMING THE
TASK-BEARING FINDING.** Stop after round 3 and report the **full cumulative ledger** — not a one-line
summary; an early stop was once ratified off a summary and would have shipped a blocker found in
round 7. **A stopped-short loop is a permitted, reportable outcome and is never relabelled as
convergence.** If residuals of the loop's own fixes dominate, say so — the remedy is a dedicated
UNCOUNTED self-sweep under `SS-N` ids plus ONE confirming round, and that is my call to make, not
yours to take.

**THE DEPTH COLUMN IS MINE TO FILL.** A cell cannot see its own depth — no hook fires for a subagent —
so do not estimate it. Report your state at each gate and I will fill it.

**If I stop the loop for depth, that is normal:** the loop re-dispatches to a fresh cell off the
committed ledger and the per-round preserved evidence. Report your state and stop.

## 3. THE LEDGER — one file for the arc, and it is COMMITTED

`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.ledger.md` already holds
this arc's writing-plans loop. **Append the executing loop as a NEW top-level section** — that file
already carries two (`# 22-A4 — REVIEW LEDGER` and `# 22-A4 writing-plans -- Codex A-loop findings
ledger`), so you are following its own convention, not inventing one. **Do not start a second ledger
file:** the arc's evidence must travel in one merge.

**Read that file's `## LEDGER CONVENTIONS` section first** (added 2026-09-07 because the ledger's own
totals were once used as convergence evidence and were not establishable from it) and conform to it.

Transcripts: `~/swing-data/review-transcripts/22-a4-exec/` **already exists** — the copy-per-round
`cp` goes there **the moment the five assertions pass**, in the same command that records the round.
Never at report time, never at teardown.

## 4. TWO OBLIGATIONS ATTACHED TO THIS LOOP BY NAME

**(a) THE ACCEPTED-LIMITATIONS PROMPT CITES THE DECLARATION; IT DOES NOT RESTATE IT** (CHARC,
2026-09-08). The arc's declared limitation lives in the Task 5 declaration in
`swing/trades/entry.py` — the block between `_CommitOutcome` and `_entry_transaction`, clause
**"CONDITION 3's TOKEN HALF IS A PRECONDITION, NOT A REACHABLE BRANCH"**. **Your review prompt cites
it by path and clause, carrying the reason, and does not paraphrase it.** WHY THIS IS LOAD-BEARING:
without the citation, round 1 reads the condition-3 gate, cannot see the declaration in the diff hunk
it is shown, and files the dead-code finding the limitation exists to pre-empt — buying a full round
to re-derive reasoning already on disk. Locate the clause by CONTENT and cite the line you find.

**(b) EVERY "SCHEMA-PREVENTED / OUT-OF-SCOPE" ADJUDICATION CITES THE EXACT CONSTRAINT** — the
migration line, `CHECK`, `UNIQUE`, `NOT NULL` or FK that makes the value impossible — **and the
citation is load-bearing: without it the finding stays IN scope.** I verify every one of these at QA
by READING the migration, because a `CHECK` weaker than assumed is a real hole, not dead code. Note
also that this arc's write path is a WRITER, and the exemption's scope is read-only consumers.

## 5. INTAKE — the arc's standing instruction, and it applies to CODEX's facts too

A ruling's REASONING is binding; its FACTS are inputs you verify. **This arc has corrected facts in
nine separate rulings, briefs, plan rows and handoffs, and every one was caught by an implementing
cell or the dispatching orchestrator, never by the author.** Task 4 alone failed three plan facts at
intake — one would otherwise have shipped a test that passed against the mutant it existed to exclude,
and two of RD's own attached rows were passing for the wrong reason as specified.

**This cuts toward Codex as well as toward the plan.** A finding premised on a fact about the code is
checkable, and you check it before you fix anything. **A wrong fix bought by an unchecked finding is
worse than the finding** — it is the Expansion-#13 cascade, and this arc's own loop has already paid
for it once.

**If a fact fails intake, or you find a genuine design fork: STOP and ROUTE to me.** The cheapest
dispatch of this arc committed nothing and prevented the most.

## 6. BINDING CONVENTIONS

- Fix commits: `fix(area): Codex R<N> Major <k> — …`. **No `Co-Authored-By`. No `--no-verify`. No
  amending** (new commit per fix).
- **Keep the FINAL `-m` paragraph plain prose.** A paragraph beginning `Word:` is parsed by git as a
  trailer — Task 4's commit did exactly this with a `Tests:` paragraph and it awaits my reword at
  merge. **Do not add a second instance.** Check `git log <base>..HEAD --format='%(trailers)'`
  yourself, not just the `Co-Authored-By` key.
- **Use `;` not `&&` in verification chains** — `git … | grep -c` exits 1 on zero matches and
  silently skips the rest of an `&&` chain.
- `ruff check swing/ --statistics` is a **SEPARATE command**; a chained exit code is ruff's, not
  pytest's.
- **Baseline: 12278 passed / 13 skipped / 0 failed** on `c9bc4838` — measured by the Task 4 cell at
  `-n 4` and re-confirmed unchanged by the Task 5 cell at `-n 4`. **Not measured by me at this point
  in the ladder.** State your worker count; if the box is memory-constrained use `-n 4` and SAY SO,
  because it is a weaker probe of the xdist-load flake class than `-n auto`.
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...`. **Never open or migrate the live DB.**

## 7. RETURN REPORT (final chat message — post to no mailbox)

- **The cumulative round ledger**, per recipe §3's shape — severity counts, NEW vs REOPENED, reverts.
- **Per round: the asserted model, effort, `^ERROR` count, footer, and the anchored VERDICT TOKEN.**
  Only the verdict token with `^ERROR` = 0 proves a review FINISHED; the footer proves only that the
  file is complete. State them as measurements, not as "assertions passed".
- **The SPEND LINE:** the SUM of every counted round's `tokens used` footer. A spend experiment
  without this number is a feeling.
- Every finding's adjudication, and for each dismissal the **cited constraint** per §4(b).
- Confirmation that no round read prior-round findings (the grep that shows it).
- Task 6 and Task 7 suite results, quoted, with the worker count; ruff; the trailer audit.
- Post-convergence minors you fixed WITHOUT another round, named.
- **Which copy of the recipe you read** and its `main` SHA.
- Anything you did NOT do, and why. Out-of-scope defects: name, do not fix.

## 8. IF YOU GET STUCK

STOP and return with the specific question. Report to the orchestrator in chat and to no one else.
