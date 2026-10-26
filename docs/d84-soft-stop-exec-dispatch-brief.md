# D84 -- the capital soft-stop arc (risk as a flag, not a gate): EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`, CHARC's choice (plan header). The arc changes the bucket gate and the hypothesis matcher, both inputs to the H1/H4 cohorts, and it carries a `swing/trades` carve-out.

**Authority:**
- **Operator, 2026-10-26, verbatim:** "start the build cell". This is the executing grant. The prior grant was plans only.
- **The plan is CLEARED for executing by both seats**, each block-quoted in the plan ledger:
  - RD (semantics), `20261026T084823Z`, at plan `6137a7b6`;
  - CHARC (form), `20261026T084925Z`, at plan `5004c51c`.
- **The final plan is `5004c51c`; the ledger tip is `ef4ecd85`.**
- **A code-bearing change beyond the plan re-opens the clearance: STOP and return.** So does any change under `swing/trades/` beyond the S1 envelope (plan 0.2).

**KEEP YOUR READING NARROW.** Read only:
1. **The plan:** `docs/superpowers/plans/2026-10-26-d84-soft-stop.md`. It is your task ladder, and it binds. Its front page (section 0) states the grant, the tripwire envelope, the two declared limitations and section 0.5b.
2. **Its ledger:** `docs/superpowers/plans/2026-10-26-d84-soft-stop.plan-ledger.md`, for the rulings and their reasons. Where the plan and a ruling differ, the ruling wins, and the difference is a plan defect to REPORT, never a choice to make.
3. **The fixture list:** `docs/superpowers/plans/2026-10-26-d84-soft-stop.e-d-fixture-tests.txt` (73 node ids).
4. **This brief.**
5. **`docs/implementer-dispatch-recipe.md` section 3:** the executing criterion, the per-round assertions and the ledger-cut note.
6. **The code each task names.**

Do not read `comms/`, director state files, other arcs' ledgers, or the D84 plan-cell briefs.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d84-exec`, branch `d84-exec`, head `ef4ecd85`. It was cut from `d84-plan`'s tip; `swing/`, `tests/` and `research/` there are byte-identical to `main` (`git diff --stat main d84-exec -- swing tests research` is empty, checked 2026-10-26 by the orchestrator).
- Run tests with `PYTHONPATH=.`.
- Run the full suite at `-n 8`. This box ran out of memory at `-n auto`.
- Read the live DB with `mode=ro` only, never through `swing`'s `connect`.
- The tests stub the broker. Never call Schwab.

## 1. Execution

**FIRST ACT, before the first commit (plan section 0.5b, CHARC amendment 2).** Sections 4 and 5 are LOWER BOUNDS. Re-run cell 2's probe method (plan section 5, "How the list was built", and its cell-3 re-run):
- a throwaway `git archive` export of this branch, kept in your scratchpad and NEVER in the repo;
- the minimal D84 semantics patched in;
- the full fast suite.

Reconcile the new failures against section 5's two tables and against T8's named supersession (`test_sizing_basis_is_the_limit.py:534`). Report every failure that section 5 does not name. Such a failure is a superseded test only when a plan task or a ruling names its behaviour as changed. **If one is not covered: STOP and return** with the list. Do not decide its fate.

**Then execute the plan's tasks in the order section 2 states (R2-03):** T2, T1, T3, T4, T5, T6, T7 (T7.1, T7.2, T7.3, T7.4), T8, T9, T10, T11, T12.
- **T4 is ONE commit:** the matcher change, the `DERIVATION_RULE_HISTORY` append, its digest and the section-5 supersessions that go red at the matcher change.
- **R-T4.6** (RD B2) and **R-T7.8** (CHARC amendment 1, a GUARD over the band geometry pivot 100.00 / stop 63.00) are in the roster; both were added at the plan-stage read.
- **TDD:** RED, then GREEN, then the commit the task names. Quote every RED and GREEN result, read off saved output.
- **Commits:** conventional and pathspec-only. `%(trailers)` empty; no final `-m` paragraph begins with `Word:`; no Co-Authored-By, no `--no-verify`, no amend.
- **Placeholders stay unfilled:** `D84-MERGE-DATE` (one line, the T4 history entry) and `<D84 merge sha>` (the nine T11 pin rows). The orchestrator fills them at the merge (plan section 6.1).

**T12 gates, before Reviewer A:**
- the FULL fast suite (`-m "not slow" -q -n 8 -p no:cacheprovider`) green, read off the saved output;
- `ruff check swing/` clean, and zero NEW findings on the touched test files;
- the T12 step 4 placeholder checks, with their pathspecs, returning exactly 1 and exactly 9;
- **the envelope:**
  - `git diff --stat ef4ecd85..HEAD -- swing/data` is EMPTY, and no new migration exists;
  - `git diff ef4ecd85..HEAD -- swing/trades` shows ONLY the `DERIVATION_RULE_HISTORY` append and the `DERIVATION_RULE_DEPENDENCIES` manifest entries (S1). Name the file(s) and the entries;
  - name every `swing/` and `research/` file changed. Each `research/` change must be PROSE or a test (CHARC C1).

If the suite reds outside this arc's files: classify it by mechanism, reproduce it at `-n 0`, and never re-run until green.

## 2. Reviewer A (executing)

Run Reviewer A per recipe section 3:
- `strong` tier, with REPO ACCESS, on the diff `ef4ecd85..HEAD -- swing tests research`, generated on Windows. Tell Codex not to run git.
- All five per-round assertions, including the model name equal to the tier's declared model.

**The prompt:**
- DESCRIBE the verdict tokens. Name both underscored tokens MID-LINE and require one alone on the final line. Never write either one line-initially, and grep the prompt to prove it. (On this arc's plan-stage Reviewer B, a prompt that described the tokens only in words got the spaced phrase back, so the round did not count.)
- Inline the rulings, or give a ledger copy cut before any round section.
- No prior-round reads. Relocate `.codex-*` and `.copowers-findings*` for the loop, then restore them. Grep each transcript.
- **Point the reviewer at the CENSUS class BY NAME (0.5b):** an omitted consumer of `bucket == "aplus"` / `("aplus", "watch")` / `risk_feasibility` / `STABLE_CRITERION_NAMES`; a test that asserts pre-D84 behaviour and was neither superseded nor updated; a behaviour true after D84 with no pin.
- Carry a per-item checklist, each item answered holds / fails / cannot-tell with a file:line:
  - E1: `bucket_for` has no risk input and no risk pre-skip, and the criterion still computes and persists;
  - E2: `risk_layer_passes` / `risk_layer_flagged` over ONE `RiskInputs`; an EMPTY layer is neither; `na` is a non-pass; one counting adapter;
  - H1 = aplus AND risk passes; H4 = aplus AND risk flagged; the old `watch|skip` H4 form deleted; an `aplus` row with no risk row matches nothing;
  - S1: the history append and the five manifest entries, and nothing else under `swing/trades/`;
  - ONE formatter, `zero_share_line`, owning both forms; the stated-zero texts as T1 states them, ASCII;
  - a zero-share framework order stays unwritable;
  - T7.4's affordance key is the UNION (the fire's flagged layer OR a live card's own `sizing_infeasible` with `risk_bound_zero`); the band card shows the affordance and NO marker;
  - F3: `risk_feasibility` out of `STABLE_CRITERION_NAMES`;
  - F4: "flagged", not "blocked", with field and value unchanged;
  - T11: nine pin rows, each sentence replaced, never annotated; no research computation moved;
  - the A6 never-500 discipline on the latch panel; the HTMX embedded-form rules (`hx-headers`, in-place swap targets).
- Invite challenge.

**Evidence:** save each round to `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\exec\round<N>\`.

**Stops:**
- **STOP AND RETURN at EVERY counted round gate** with its ledger row, leaving the depth column empty.
- Stop at the first clean verdict. Post-verdict minors are fixed with no new round.
- A fourth counted round needs the orchestrator's written authorization (recipe section 3 rule 5).
- Reviewer B, the merge, the placeholder fills and the operator's browser witness (plan section 6.3) are the orchestrator's.

## 3. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- the first-act probe: failures, and their reconciliation against section 5;
- commits, with their trailers;
- RED and GREEN results per task;
- suite counts;
- the envelope diffs;
- the round row(s) and findings, each with a proposed disposition;
- the summed Codex `tokens used`;
- every deviation.

**If anything does not fit, STOP and return.**
