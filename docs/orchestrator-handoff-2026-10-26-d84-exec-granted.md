# Orchestrator handoff -- 2026-10-26 -- D84 EXECUTING GRANTED; dispatching the build cell is your first act

**Supersedes:** `orchestrator-handoff-2026-10-26-d84-plan-loop-closed.md`.

**From:** the generation bootstrapped 2026-10-26 (session `a3a96bd1`, Opus 5.5).
- It rolled at about 300K self-read, below the trigger on purpose.
- The operator granted executing at that point. QA of the return, Reviewer B on the code, the merge gate and the step-by-step witness would not fit under 400K. A subagent dies with the session that spawned it, so the build cell is yours to dispatch (bootstrap: a dispatch you cannot QA within budget is the successor's).

**Re-derive every fact below. Each one carries its method.**

## 1. STANDING GRANT (STATE) -- dispatch without a fresh go

**Operator, 2026-10-26, verbatim, in chat with this generation: "start the build cell".**
- It was given after the plan stage closed and in answer to "start the build cell (`implementer-opus-high`, working from plan `5004c51c`), or hold?".
- It is the executing grant for D84. The prior grant was plans only.
- **It names the next act: dispatch the executing cell.** Per the bootstrap's standing-authorization exception, dispatch it without re-asking. Quote this grant and this handoff's SHA in your online notice.

## 2. STATE (verified at write time)

- **`main`:** ahead of origin by 64 or more (`git status -sb`); not pushed, the push is the operator's. Schema v41.
- **Executing brief:** `docs/d84-soft-stop-exec-dispatch-brief.md`, committed on main at `d36a799c`. Read it before dispatching; it is the cell's whole instruction.
- **Worktree:** `.worktrees/d84-exec`, branch `d84-exec`, cut at `ef4ecd85` (= `d84-plan`'s tip).
  - `git diff --stat main d84-exec -- swing tests research` was EMPTY at cut.
  - `git diff --stat d84-plan main -- docs/implementer-dispatch-recipe.md docs/harness-architecture.md` was EMPTY, so the rules in that tree are current. Re-check both before dispatching (base-SHA rule).
- **Plan:** `docs/superpowers/plans/2026-10-26-d84-soft-stop.md`, final at `5004c51c`.
- **Ledger:** `...soft-stop.plan-ledger.md` @ `ef4ecd85`. It block-quotes every ruling, including this generation's:
  - Reviewer B (run 1 did NOT count: the spaced verdict phrase; run 2 counted, 0/2/1);
  - RD's plan-stage read and item B (`20261026T084545Z`), and RD's clearance at `6137a7b6` (`20261026T084823Z`);
  - CHARC's plan-stage read, item A and amendments 1 and 2 (`20261026T084657Z`), and CHARC's clearance at `5004c51c` (`20261026T084925Z`).
- **Cells:** none running (`python scripts/cell_depth.py --live 2` shows only the four returned plan cells of the prior generation; none will be resumed).
- **Directors:** BOTH rolled over minutes before this handoff on clean boundaries: CHARC state `ab9ff4fa`, RD state `4ad5b7bc`. Their successors take the executing-stage gates. Trust the `ping ->` line for session names.
- **Inbox:** drained and empty at write.
- **Wake:** the ping convention; no Monitor armed.

## 3. NEXT, owner = you, in order

1. **Dispatch** `implementer-opus-high`, `run_in_background`, with NO model override, pointed at the brief.
   - Announce the cell choice in chat (it is vetoable).
   - Run `cell_depth.py --live 2` first.
   - Post the lifecycle status (executing dispatched) to charc,rd.
2. **At every counted round gate:** `cell_depth.py --agent <id>`, fill the depth column, and rule or route the findings. A fourth counted round needs your written authorization naming the task-bearing finding.
3. **On return:**
   - QA against disk (the first-act probe reconciliation, the envelope diffs, the T12 gates);
   - then **Reviewer B, yours, on the final code tree.** The model to copy is `~/swing-data/review-transcripts/d94-cancel/exec/reviewer-b/run_b.sh` (`strong`, repo access, the diff fed in).
   - **Name both underscored verdict tokens MID-LINE in the B prompt.** This generation's plan-stage B run 1 was voided because the prompt described them only in words. The corrected prompt is at `~/swing-data/review-transcripts/d84-soft-stop/plan/reviewer-b/b-prompt.md`.
4. **Merge gate:** the return report and the B transcript go to both seats; CHARC holds the merge gate. Then:
   - `merge --no-ff` (ledgers cite the branch SHAs);
   - the merged-head suite at `-n 4` or `-n 8`, read off a SHA-stamped file;
   - plan section 6.1's two placeholder fills, in ONE docs-only commit on main after the merge: `D84-MERGE-DATE`, and `<D84 merge sha>` at the NINE T11 pin rows. Then the path-scoped greps return nothing;
   - plan section 6.3's operator-witnessed browser step, ONE STEP AT A TIME, on a scratch DB copy, including the band card and the UNSEEDED default.
5. **Post-merge:** RD writes the VII.F boundary note. The Finviz widening is the operator's config edit, the night after.

## 4. AUTHORITIES granted this generation (all recorded in the ledger)

- The B2-02 and B2-03 plan fixes (encodings of RD floor (1) / CHARC F1-A and of the `CitedCandidate` API shape).
- Two same-count edits beyond RD's "exactly", disclosed to RD and accepted by him.
- Amendment 2 placed on the plan's front page as section 0.5b, CHARC's stated fallback, because no executing brief existed yet. The executing brief now also carries it.
- No other authority was given.

## 5. OPEN / OWED

- **The Friday 10-24 nightly did not run** (RD's state). If Monday 10-26's also missed, that is two in a row: T1. RD's successor checks; tell the operator if you see it first.
- **The Schwab refresh token lapses 2026-11-02T05:20Z.** Remind the operator to run `swing schwab setup`.
- **CHARC NOTED (not ruled):** one line in the recipe's B section about prompt shape (the spaced verdict phrase). CHARC's own, at phase close.
- **Registered, not commissioned:** D91, D92, D93, D95, D94 (c), the governing-child duplicate spellings, the unfloored entry-form sizing, F1-B.
- **Push:** the operator's.

## 6. WHAT WILL BITE YOU

- **Context:** the bootstrap plus CLAUDE.md costs about 220K before any work. A `cd` into a worktree re-loads that worktree's CLAUDE.md (~40K). Avoid it: use `git -C <path>` and absolute paths. Command output goes to files, read with bounded `tail`/`grep`.
- **Every `role_mail` post goes from the MAIN repo cwd**, with `--body-file` (a temp file) and a subject of 80 characters or fewer.
- **A verdict described in words gets the spaced phrase back.** Name the underscored tokens mid-line.
