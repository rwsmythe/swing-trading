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

## 4. ADDENDUM: CHARC's rulings on the held items 1-3 (author: CHARC, `20261026T164436Z`; the orchestrator is courier only)

**Item 1 is now IN SCOPE.** It is a code change to T7.4's key that CHARC ruled as a FORM correction to his own amendment 1. Section 2's hold on items 1-3 is lifted by this ruling.

**Do this:**
1. Transcribe the block quote below into the exec ledger as **"amendment 1 CORRECTED"**, author CHARC.
2. REPLACE (do not annotate) the plan's T7.4 text to match it.
3. Implement (a) and (b) by TDD, showing each discriminator RED first.
4. Re-run the full T12 gates.

**Timing:**
- If round 2's Codex run has NOT launched, do all of this BEFORE round 2, so round 2 reviews it.
- If round 2 is already running, let it finish. Do NOT apply item 1 then. Return at the gate as briefed, and say that item 1 is pending; the orchestrator folds it into the round-3 fixes.

Items 2 and 3 need no code. Transcribe them as rulings only. Item 3 corrects the record: `seed_fire(` is called by 18 test files, not 10.

The ruling, literal block quote:

> ITEM 1 -- IN SCOPE for D84, as a FORM correction to my own amendment 1 (20261026T084657Z). The GROUND stands; the FORM named a reason where the ground named a fact. Two clauses, both in T7.4's key (_risk_flag_attest_available, view_models/latches.py:996-1020), transcribed as 'amendment 1 CORRECTED' in the exec ledger and REPLACED (not annotated) in the plan's T7.4 text.
> 
> (a) Leg (b) keys on the SIZING FACT, not the withheld reason. Today: withheld_reason == 'sizing_infeasible' AND withheld_heading == _RISK_FLAG_HEADING. Rule: live card AND prepared_order.sizing is not None AND risk_bound_zero(prepared_order.sizing) (sizing.py:82). Ground: P3 admits sizing beside BOTH reasons (order_intent.py:293-297); the regime-undeterminable state is the ORDINARY intraday state of a live card (the VM docstring at :194 says so), so under the current form the band affordance exists only after a nightly dated close and never on a card withheld on regime grounds throughout -- the same unrecordable act amendment 1 was written against, behind a different gate. A heading string is a display, not a key; key on the fact it is derived from. The MARKER is unchanged (P1: the criterion passed). Discriminators, RED first: R-T7.8's geometry with regime_order_type=None -> True; the same regime-None card with FEASIBLE sizing -> False (unchanged pre-D84 posture: the offered form arrives with the close); regime-None with a CAP-bound zero -> False; R-T7.8 itself stays green.
> 
> (b) Leg (a) is WITHDRAWN while the card OFFERS an order. Rule: fire_flagged AND NOT (prepared_order is not None AND prepared_order.order is not None). Terminal cards (prepared_order None) keep leg (a) -- R-T7.7 unchanged. Ground: the D84 lead paragraph is a statement of fact about THIS card ('The framework has no order here'); on an offered card it is FALSE, and the act is recordable through the offered form's own place/decline path, so the declaration there is false AND redundant -- the E-i class (a true paragraph on one card is false on another; do not reuse it). The MARKER stays on an offered card: the fire's criterion did fail and the marker carries no sizing claim (P1). Reachability: by construction -- real equity rising above the 7,500 floor, or a risk-policy/config edit after the fire (the live path). A declared band is still a band (P2's own rule). Discriminators, RED first: fire flagged + live card with an order -> attest False, marker renders; fire flagged + live withheld card -> True; fire flagged + terminal -> True.
> 
> ITEM 2 -- CONFIRMED: computed. The roster's persisted test is 'built from a DB row by a _row_to_* mapper or a repo/reader row loop' (test_22f_inv_model_roster.py:12-15). RiskInputs has ONE constructor in swing/ by grep ('RiskInputs(' -> scoring.py:154 only), the counting adapter risk_inputs_from_criteria; the object is a reduction with no row and no CHECK to quote. The LATER_ARC_ROSTER comment carries the arc and the constructing site, the form the docstring requires. The 'reached from ...' clause in the comment is a reachability claim the test's DECLARED BOUND says it does not prove -- fine as a comment, not load-bearing.
> 
> ITEM 3 -- FORM PASSES. The default risk_result='pass' mirrors production: evaluator.py:51 evaluates risk_feasibility on EVERY candidate, LAYER='risk' (criteria/risk_feasibility.py:8), and the fixture's default bucket is aplus, so an aplus candidate with no risk row is a shape production never writes post-boundary; None names the exceptional shape explicitly -- the right polarity (production shape by default, the exception by name). Count correction, with method: 18 test files call seed_fire( (grep -rl 'seed_fire(' tests), not 10; all green per your report. Noted, no finding: the fixture INSERT omits value and rule, which production writes (repos/candidates.py:79-84); the counting adapter reads layer and result only, so nothing D84 reads is affected -- a future reader of those two columns through this fixture would be.
> 
> Evidence read at this seat: latches.py:130-146,190-240,333-345,995-1065,1176-1210; order_intent.py:281-321; sizing.py:82-160; scoring.py:99-157; evaluator.py:51; candidates.py:72-84; the plan T7.4 at 508-560; the roster test 1-40 and 315-329; the seed_fire diff.

## 5. ADDENDUM 2: the orchestrator's round-2 rulings (author: the orchestrator, 2026-10-26)

The cell continues: its depth at the round-2 gate is **306,585** (`cell_depth.py --agent`, read by the orchestrator), so it is under the cap. Transcribe this section into the exec ledger as a block quote with the orchestrator as author, and fill the round-2 depth column with that figure.

> **Correction first (the orchestrator's error, recorded).** My A1-01 ruling cited `_verify_aplus_consistency`'s "runtime behaviour". That method does not exist: `git grep` of the tree finds it only in the ledger. I took the name from cell 1's report without checking it on disk. Cell 2's handling is ACCEPTED: the replacement sentence drops the dangling pointer. The A1-01 ruling stands otherwise. The orchestrator corrects the fyi it sent RD.
>
> **A2-01 (major), the aggregator's drift comment and warning text: ACCEPTED, prose only, under 0.3b and CHARC C1 (emitted text is prose).**
> - Era-phrase the comment at `aggregator.py:181-193`, the two warning strings, and the docstring at `test_aggregator.py:306-308`.
> - The new text MUST keep the substring `re-aggregation drift` (`test_aggregator.py:323`).
> - The warning keeps firing. No computation moves.
>
> **A2-02 (major), the "parity invariant at current_value" claim: ACCEPTED, prose only.**
> - Scope the three sentences to pre-D84 rows and name the expected divergence: `output.py:79-81`, `aplus-criteria-calibration.md:55`, and `test_aplus_sensitivity_sweep.py:249`.
> - Keep the test name. Add no placeholder, and do not touch `sweep.py`.
>
> **A2-03 (minor), the refusal text at `cohort_provenance_correction.py:1578`: DECLINED in D84.**
> - It sits outside the S1 envelope, inside source the S1 digest hashes. The orchestrator banks it with the `hypothesis.py:375` rider, triggered by the next derivation-rule version bump.
> - CHARC is CC'd and may pull it into scope. Do not touch it unless that ruling reaches you.
>
> **Deviation 2 (the defaulted `sizing` field on `PreparedOrderVM`):** routed to CHARC to confirm the form. Do not change it unless his ruling reaches you.
>
> **SELF-SWEEP SS-1 (uncounted), BEFORE round 3.** A1-01, A2-01 and A2-02 are ONE class (T11: a sentence that still states the pre-D84 rule as current) and were found one round at a time. Residuals findable by search are found by search. So:
> - Grep `research/`, `tests/research/` and the docstrings and comments of every `swing/` file the arc touched for the class. At minimum: `should equal`, `should agree`, `by construction`, `parity`, `invariant`, `current_value`, `risk_feasibility`, `aplus` near `skip`/`watch`/`gate`/`pre-filter`.
> - List EVERY hit in the ledger under `SS-1`, with a disposition: replaced (era-phrase, prose only), not-a-claim, or out of envelope (named, banked, not touched).
> - Do not move a research computation, and add no placeholder.
>
> **Then:** re-run the T12 gates in full on the final head (full suite at `-n 8`, ruff, placeholders exactly 1 and exactly 9, envelope).
>
> **ROUND 3 is AUTHORIZED.** It is the last default counted round, in round 2's form. Carry the census class and the checklist, and point the reviewer at the SS-1 list. Save it to `...\exec\round3\`.
> - **Clean:** fix post-verdict minors with no new round, run the full suite once more on the final head, restore the findings file, and return.
> - **Not clean:** STOP and return at the gate. A fourth counted round needs the orchestrator's written authorization.

## 6. ADDENDUM 3: CHARC on the VM field and A2-03 (author: CHARC, `20261026T172421Z` as superseded in part by `20261026T172440Z`; the orchestrator is courier only)

Transcribe both block quotes into the exec ledger, with CHARC as author.

**What to do:**
- **The annotation fix** (`PreparedOrderVM.sizing` -> `SizingResult | None = None`) is prose-level and needs no RED. If round 3 has not launched, fold it into the round-3 fixes. If round 3 is already running or done, apply it as a post-verdict minor when round 3 is clean. If round 3 is not clean, it goes into the next fix set.
- **Touch nothing in `_derive`.** The `D84-MERGE-DATE.1` digest pins its source as it stands.

Literal block quote, `20261026T172421Z` (its ITEM 1 form note is SUPERSEDED by the next quote; everything else in it stands):

> PRIMARY charc on items 1 and 2 of 20261026T172229Z. Read on d84-exec at db412d3c.
> 
> ITEM 1 -- FORM CONFIRMED. The key as applied (latches.py:1028-1033) reads the two facts my ruling named through the VM: offers_order = prepared_order.offered, which the builder sets True on the order branch (:740) and False in _withheld_block (:594) -- the two branches are the exactly-one-of in PreparedOrderResult, so offered is 'result.order is not None' by construction; and sizing = prepared_order.sizing, which _withheld_block receives as getattr(result, 'sizing', None) for EITHER withheld reason and carries onto the VM (:598). On an offered card the VM's sizing is None by P3 (sizing admitted beside the two withheld reasons and nowhere else), so leg (b) cannot fire there -- consistent with (b) of my ruling without a second clause. The a2d85d66 move of the mutation guard to a FEASIBLE geometry is the right fix: a guard whose geometry satisfies both legs cannot kill a mutation of one.
> 
> One form note, prose-level, fold into the round-3 fixes (an annotation is not behaviour; no RED): PreparedOrderVM.sizing is annotated  (:244). Annotate it .  hides the contract from the reader and from any type check, and the module already imports from swing.recommendations.sizing at :64 (risk_bound_zero, zero_share_line), so naming the type costs no layer crossing the module has not already made.
> 
> ITEM 2 (A2-03) -- NO PULL; the decline stands, with the banked trigger sharpened. The refusal clause (cohort_provenance_correction.py:1573-1581, 'matches the A+ baseline and only it today') lives inside _derive, which DERIVATION_RULE_DEPENDENCIES hashes WHOLESALE with the wording noise accepted deliberately (:233-241, coordinator-ruled: do not narrow the hash). S1 scoped the swing/trades carve-out to TWO tuples on the ground that D84 changes no derivation semantics; a wording edit inside the hashed function is a third site in swing/trades for prose, and the refusal itself stays CORRECT (0 or 2 matches -> refuse) -- only its explanatory sentence is stale. Same class as the hypothesis.py:375 rider; bank them together. TRIGGER, sharpened: the next DERIVATION_RULE_HISTORY append for a SEMANTIC change -- the digest moves then anyway and both wording edits ride at zero version cost. Note for the merge gate: the D84-MERGE-DATE.1 row's digest (:420-421, 30ac9063...) pins _derive's source AS IT STANDS; nothing in the round-3 fixes may touch _derive, or that row's digest is stale at the fill.
> 
> Item 3 is RD's; nothing from this seat.

Literal block quote, `20261026T172440Z` (the supersession):

> ONE supersession: the ITEM 1 form note in 20261026T172421Z lost three spans to shell quoting. Everything else in that message stands (item 1 CONFIRMED; A2-03 declined with the sharpened trigger; the merge-gate note on the D84-MERGE-DATE.1 digest). The form note, restated whole:
> 
> PreparedOrderVM.sizing (latches.py:244) is annotated 'object | None = None'. Annotate it 'SizingResult | None = None'. The word object hides the contract from the reader and from any type check, and the module already imports from swing.recommendations.sizing at :64 (risk_bound_zero, zero_share_line), so naming SizingResult costs no layer crossing the module has not already made. Prose-level; fold into the round-3 fixes; an annotation is not behaviour, so no RED.
> 
> acked 2 message(s); moved inbox -> read.
