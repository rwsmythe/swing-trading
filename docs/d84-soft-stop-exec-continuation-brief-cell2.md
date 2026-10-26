# D84 soft-stop EXECUTING, continuation cell 2: apply the round-1 rulings, then Reviewer A round 2

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`, the same cell as executing cell 1.

**Why a fresh cell:** executing cell 1 returned at the round-1 gate at a depth of **758,413** (read by the orchestrator with `cell_depth.py --agent`, 2026-10-26). That is past the 400K cell cap, so the loop continues in a fresh cell off the committed branch and the preserved round evidence (recipe section 3). Nothing went wrong in cell 1.

**Authority:** unchanged from the executing brief `docs/d84-soft-stop-exec-dispatch-brief.md` (`d36a799c`), which you read FIRST and which still binds: the operator's grant "start the build cell", both seats' clearances, and the rule that a code-bearing change beyond the plan re-opens the clearance. **Everything below is an addition to that brief, not a replacement.**

## 0. Read, narrowly

1. The executing brief, `docs/d84-soft-stop-exec-dispatch-brief.md`.
2. This brief.
3. The exec ledger on the branch: `docs/superpowers/plans/2026-10-26-d84-soft-stop.exec-ledger.md` @ `101f271a`. It holds cell 1's task record and the round-1 row.
4. The round-1 evidence: `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\exec\round1\`. Read `final-message-r1.md` for the findings, `codex-prompt-r1.md` and `run_r1.sh` as the model for round 2, and `rulings-excerpt.md` for the ruling block quotes. Do NOT read `codex-review-r1.txt` whole: it is 2.2 MB.
5. The plan and its plan ledger, ONLY where a fix needs them (T11, 0.3b, R-T4.6, E-d).
6. `docs/implementer-dispatch-recipe.md` section 3.

Do not read `comms/`, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d84-exec`, branch `d84-exec`, head `101f271a`. All the conventions of the executing brief apply: `PYTHONPATH=.`; `-n 8`; the live DB `mode=ro` only; never call Schwab; long output goes to files, read with bounded tail/grep.

**Loop state:** cell 1 relocated the working findings file to
`C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\c53dc3dd-3af6-4b7f-8cd2-a63f00589cb4\scratchpad\review\.copowers-findings.md`
(a durable copy is in `round1\`). Keep it out of the worktree during the loop, and restore it to the worktree root when the loop ends.

## 1. The orchestrator's round-1 rulings (author: the orchestrator, 2026-10-26)

Transcribe this section into the exec ledger as a block quote, with the orchestrator as author. Also fill the round-1 depth column: **758,413, OVER, read by the orchestrator; cell 1 retired at this gate.**

> **A1-01 (major), T11 incomplete: ACCEPTED, prose only.** This applies rulings that have already landed (plan 0.3b; RD `20261026T082404Z`; T11's "each sentence replaced, never annotated"). It is an encoding, not a new decision.
> - Re-cast row 6 in `context_builder.py` so the tier-2 lead itself names the pre-D84 era. RD's B3 sentence stays verbatim and contiguous.
> - Replace each late-found claim sentence in the era-phrase shape: `research/finviz_pool_analysis/aggregator.py:53-55`, `research/finviz_pool_analysis/doctrine.py:21`, and the four `tests/research` docstrings.
> - Add no new placeholder. The pin count stays NINE.
> - Leave `_verify_aplus_consistency`'s runtime behaviour untouched. Moving it is a research computation, which T11 forbids. The post-boundary disagreement is the declared re-use precondition; the orchestrator routes it to RD as an fyi.
>
> **A1-02 (major), vacuous closed-hypothesis test: ACCEPTED.** Give the `aplus` candidate in `test_hypothesis_matcher.py::test_closed_hypothesis_is_not_matched` a risk `pass` row, so the test can distinguish closed from open. Check the paused-hypothesis sibling the same way and fix it if it has the same defect. **Show the discriminating arithmetic:** the test must FAIL if the closed-status filter is removed. Demonstrate that by a temporary local mutation, and quote the output.
>
> **A1-03 (major), unpinned empty-layer consumers: the three pins ACCEPTED; the rider DECLINED.**
> - Add one empty-risk-layer pin per direct matcher consumer (RD E-d): the dashboard recommendation builders, `cohort_hint_for`, and shadow attribution. Each pin must fail under a matcher that treats an empty layer as passing.
> - **The rider is declined.** The stale "ONLY opt-in caller" comment at `hypothesis.py:375` predates D84 and sits inside source the S1 digest hashes. Do not touch it. The orchestrator banks it for the next touch of that function.
>
> **A1-04 (minor), two stale comments: ACCEPTED, prose only.**
> - Fix `build.py:151`, keeping the exact phrase that `order_intent.py:394-398`'s content search locates. Prove the search still hits by running the test(s) that exercise it.
> - Fix the dashboard test comment at `:143`.
>
> **Fix commits:** conventional, pathspec-only, named by finding, e.g. `fix(research): Codex R1 Major 1 -- ...`. The same commit rules as the executing brief apply.
>
> **After the fixes:** re-run the T12 gates IN FULL. That means the full fast suite at `-n 8`, ruff, both placeholder counts (exactly 1 and exactly 9), and the envelope diffs. Do this BEFORE round 2.
>
> **Round 2 is AUTHORIZED** as a counted round, at the same tier and in the same form as round 1: repo access, five assertions, both underscored tokens named MID-LINE, zero line-initial tokens in the staged input, no prior-round reads, and the rulings inlined (now including this section). Point the reviewer at the round-1 fixes AND the census class, and carry the executing brief's checklist again. Save the round to `...\exec\round2\`.

## 2. Items held at the orchestrator, NOT for you to act on

These were routed to the directors and are not in your scope:
- cell 1's two flagged CHARC items (a band card with an undeterminable regime; leg (a) on an offered card);
- the `LATER_ARC_ROSTER` classification;
- the shared `seed_fire` fixture default.

If a director rules one of them into scope, it reaches you through the orchestrator. Do not change code for them.

## 3. Stops and return

- **STOP AND RETURN at the round-2 gate** with its ledger row, leaving the depth column empty.
- If round 2 is clean, post-verdict minors are fixed with no new round. Then run the FULL fast suite once more on the final head (the after-convergence gate), restore the findings file, and return.
- If round 2 is NOT clean, return at the gate. Do not open round 3 yourself: the orchestrator rules the findings first. Round 3 stays within the default three counted rounds; **a fourth counted round** needs the orchestrator's written authorization.
- Return as your final chat message:
  - the fix commits with their trailers;
  - the discriminating demonstrations (A1-02, A1-03);
  - the suite counts read off saved files;
  - the envelope;
  - the round row and its findings, each with a proposed disposition;
  - the summed `tokens used`;
  - every deviation.
- **You never post to a mailbox and never run `scripts/role_mail.py`.** The orchestrator QAs and posts.
