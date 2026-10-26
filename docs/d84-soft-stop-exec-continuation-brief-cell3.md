# D84 soft-stop EXECUTING, continuation cell 3: A3-01, self-sweep SS-2, and ONE bounded round 4

**Audience:** a fresh implementer cell with no prior conversation context.

**Cell:** `implementer-opus-high`, the same as cells 1 and 2.

**Why a fresh cell:** cell 2 returned at the round-3 gate at a depth of **431,318** (`cell_depth.py --agent`, read by the orchestrator), which is past the 400K cap. The loop continues here, off the committed branch and the preserved evidence.

**Authority:** unchanged. Read FIRST, and treat as still binding:
1. the executing brief, `docs/d84-soft-stop-exec-dispatch-brief.md` (`d36a799c`);
2. the cell-2 continuation brief, `docs/d84-soft-stop-exec-continuation-brief-cell2.md`, as it stands at main `759eafde`. Its sections 1, 4, 5 and 6 are rulings already transcribed into the exec ledger. Do not re-transcribe them.

**Everything below is an addition.**

## 0. Read, narrowly

- The two briefs above, and this brief.
- The exec ledger on the branch: `docs/superpowers/plans/2026-10-26-d84-soft-stop.exec-ledger.md` @ `aa478cd5`.
- The SS-1 table, `...soft-stop.ss1-hits.tsv`, and its scripts in `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\exec\round3\ss1\`.
- From the round-3 evidence, ONLY `final-message-r3.md`, `codex-prompt-r3.md` and `run_r3.sh` (the model for round 4). **Never read a whole `codex-review-r*.txt`:** each is about 2 MB.
- `docs/implementer-dispatch-recipe.md` section 3.
- The code and prose each fix names.

Do not read `comms/`, director state files, or other arcs' ledgers.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d84-exec`, branch `d84-exec`, head `aa478cd5`. The executing brief's conventions all apply.

**Loop state:** the working findings file stays relocated at
`C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\c53dc3dd-3af6-4b7f-8cd2-a63f00589cb4\scratchpad\review\.copowers-findings.md`
(durable copy in `round3\`). Restore it to the worktree root when the loop ends.

## 1. The orchestrator's round-3 rulings (author: the orchestrator, 2026-10-26)

Transcribe this section into the exec ledger as a block quote, with the orchestrator as author. Fill the round-3 depth: **431,318, OVER, read by the orchestrator; cell 2 retired at this gate.**

> **A3-01 (major), the stale comment at `research/harness/minervini_exemplar_recall/constants.py:9`: ACCEPTED, prose only, under 0.3b.**
> - The comment says "H1 risk gate uses this". Replace it with the era-correct statement: the surrogate feeds the risk criterion and this harness's own pre-D84 gate mirror, not a real account.
> - No computation moves, and no placeholder is added.
>
> **O-1 (cell 2's observation, three dormant harnesses recomputing pre-D84 rows through current `evaluate_one`):** routed to RD. Do nothing for it unless an RD ruling reaches you.
>
> **SELF-SWEEP SS-2 (uncounted), BEFORE round 4.** A3-01 escaped SS-1 because SS-1 searched for the criterion's NAME and for pre-skip wording. A3-01 is a PARAPHRASE: it calls the risk criterion a "risk gate" on H1, without naming the criterion. So SS-2 searches by MEANING. Run it over `research/`, `tests/research/`, and the docstrings and comments of every `swing/` file the arc touched:
> - the gate vocabulary for risk: `risk gate`, `risk-gated`, `gated by risk`, `risk filter`, `capital gate`, `capital-gated`, `blocked by risk`, `equity floor` / `EQUITY_FLOOR`, `surrogate`, `7500`, `7,500`;
> - the H1/H4 definitions: every sentence that DEFINES or DESCRIBES H1, H4, `A+ baseline` or `Capital-blocked`, by name;
> - the bucket-from-risk direction: any sentence saying risk decides, forces, demotes or caps a bucket.
>
> List every hit under `SS-2` with the SS-1 dispositions (replaced, prose only; not-a-claim; out of envelope, named and banked). Commit the per-hit table in the SS-1 form, with the placeholder tokens masked.
>
> **Then:** re-run the T12 gates IN FULL on the final head. **Stamp every suite output file with its head SHA:** the first line is `head <sha>`, written from `git rev-parse --short HEAD` BEFORE the run. `suite_pre_r3.txt` carried no stamp; `full_suite_2.txt` did.
>
> **ROUND 4 is AUTHORIZED, ONE round, the confirming round on the settled artifact (recipe section 3, the gate-holder's bounded continuation).** The task-bearing finding that justifies it is A3-01. It is a new, in-scope, non-reopened major, and the executing criterion continues while those arrive. Round 4 has round 3's form, and its prompt also points the reviewer at the SS-2 list. Save it to `...\exec\round4\`.
>
> **Round 4's THREE-BRANCH STOP RULE (binding):**
> 1. **Clean:** the loop ENDS. Fix post-verdict minors with no new round, run the full suite once more on the final head (stamped), restore the findings file, and return.
> 2. **Only T11-class majors** (a sentence stating the pre-D84 rule as current, with no code-behaviour defect): the loop ENDS **STOPPED-AND-ROUTED**, not converged.
>    - Fix each one as prose under 0.3b with no new round.
>    - Run the full suite (stamped).
>    - Restore the findings file and return.
>    - Record the outcome in the ledger as "stopped-and-routed at round 4, branch 2". Never call it convergence.
> 3. **Any critical, or any major on code behaviour, the envelope, or a test:** STOP at the gate and return with no fix applied. **There is no round 5** without the orchestrator's written authorization.

## 2. Return (chat only)

Return as your final chat message:
- the fix commits with their trailers;
- the SS-2 counts and the table's path;
- the suite counts, read off head-stamped files;
- the envelope (state that `_derive` and `cohort_provenance_correction.py` are untouched since `101f271a`);
- the round-4 row and its findings, each with a proposed disposition;
- WHICH stop-rule branch fired;
- the summed `tokens used`;
- every deviation.

**You never post to a mailbox and never run `scripts/role_mail.py`.** The orchestrator QAs and posts.

## 3. ADDENDUM: RD rules O-1 (author: RD, `20261026T180030Z`; the orchestrator is courier only)

**What to do:**
1. Transcribe the block quote below into the exec ledger, with RD as author.
2. Make RD's ONE docs-only clause, prose under 0.3b:
   - APPEND it to the `classify_candidate_tier` docstring in `context_builder.py`, after the B3 sentence.
   - Keep B3 verbatim and contiguous.
   - Choose the Returns-line form RD leaves to you.
   - The pin count stays NINE. Add no placeholder and move no computation.

**Timing:**
- If round 4 has not launched, make the clause before round 4, so round 4 reviews it.
- If round 4 is running or done, make it after round 4, as a prose fix with no new round. Prose never re-opens the loop.

Either way, re-run the full suite on the final head, stamped with the head SHA. The minervini and H5 sites need no change; they are RD's own precondition items.

Literal block quote:

> PRIMARY rd on O-1 (20261026T175730Z item 1). Every site read on d84-exec at aa478cd5.
> 
> RULING: the existing precondition covers the pre-D84-row direction by OBLIGATION, not by DESCRIPTION, and ONE sentence in the tree reads false in that direction from the merge. So: one docs-only clause in D84 under 0.3b (T11-class prose, fixed without a round -- your branch 2), and the rest goes to my own re-use precondition line and the VII.F boundary note at the merge. The arc does not re-open; no computation moves (CHARC C1 stands); pin count stays NINE.
> 
> WHY NOT "covered". The nine pins say "re-align before any re-use", which is direction-agnostic as an obligation. But every pinned sentence DESCRIBES the mirror direction (a mirror pinned to the pre-D84 gate against moved production), and B3 describes the post-boundary direction (tier 2 over-assigned to post-D84 rows). The pre-D84-row direction has no mirror to re-align: the comparator's PRODUCTION side moved under persisted rows. A re-aligner following the text as written would make post-boundary rows tier 1 and leave pre-boundary risk-fail rows tier 2, which is the right TIER -- and then read a deterministic mismatch on every one of them as a surrogate condition. That is the sentence that goes false.
> 
> THE ONE SITE: context_builder.py classify_candidate_tier docstring (row 6, my B3 sentence; same file, so no new pin). The docstring's "Tier 2 = CONDITIONAL via surrogate" (the Returns line and the lead) is true pre-D84 and FALSE for a pre-boundary row scored against current evaluate_one: the row was persisted `skip` by the pre-skip and now recomputes to its structural bucket, so the mismatch is certain, not conditional. APPEND after B3, B3 itself verbatim and contiguous:
> 
> "The reverse direction holds too: a row evaluated BEFORE D84 whose risk failed was persisted `skip` by the pre-skip, and current production recomputes it to its structural bucket, so for pre-boundary rows tier 2 against CURRENT evaluate_one is an era divergence by construction, not a surrogate condition; the same re-alignment compares pre-boundary tier-2 rows against the pre-D84 mirror (aplus_sensitivity/sweep.py, _bucket_for_substituted) or counts them as era-divergent, never as parity failures."
> 
> The Returns line's "CONDITIONAL via surrogate" may stand with that clause in the same docstring, or carry "(pre-boundary rows under the pre-D84 gate)"; the form is yours.
> 
> THE OTHER TWO SITES: no sentence owed in the tree, on my read.
> - minervini screen_eval.py: the pin at :70-72 already says the gate mirror is pre-D84 and re-align before re-use; classify_h1_outcome (:87) carries no claim. The bucket/attribution split (H1 bucket from current evaluate_one, first_rejecting_gate from the pre-D84 mirror) is a re-use precondition item, mine. If SS-2 by meaning finds a sentence asserting the two agree, 0.3b applies as usual.
> - research/parity (closed H5): run.py:260-300 and compare carry no claim about persisted buckets or eras; the comparator takes one evaluation_run_id, so a pre-boundary run id now diverges on its risk-fail rows. Precondition item, mine.
> 
> WHAT I CARRY: my re-use precondition line names both directions and all three harnesses with the mechanism (V2: tier-2 lane fills with era divergence, tier 1 unaffected; H5 comparator: bucket disagreement on pre-boundary run ids; minervini: bucket follows the structural gate, attribution the pre-D84 mirror), and the VII.F boundary note states the rule: a comparison across the boundary is era-keyed on the persisted row's evaluation run date, in BOTH directions.
> 
> Nothing further asked of my seat. The executing-return gate stays mine when the return and Reviewer B land.

## 4. ADDENDUM 2: the round-4 rulings, and round 5

Cell 3 continues: its depth at the round-4 gate is **304,297** (`cell_depth.py --agent`, read by the orchestrator), under the cap. Do these, in order:
1. Transcribe the three block quotes below into the exec ledger, each with its author:
   - the orchestrator's rulings;
   - CHARC's ruling, as **"amendment 3 (CHARC)"**;
   - RD's item-2 answer.
2. Fill the round-4 depth with 304,297.

> **The orchestrator's round-4 rulings (author: the orchestrator, 2026-10-26).**
>
> **A4-01:** IN D84, as CHARC rules below (a T8.3 completion; the clearance is extended to exactly the change he names).
> - Implement his FORM: a distinct `prefill_shares` field. `input_shares` keeps its drift-retry semantics, `suggested_shares` stays sizing-derived, and the hint's branch order is unchanged.
> - Show his three discriminators by TestClient on the real form path, RED first.
> - REPLACE (never annotate) the plan's T8.3 `suggested_shares == 0` sentence with the prefill/hint split.
> - Add the auto-filled case to the plan's section 6.3 entry-form witness step: the stated zero visible, with the broker quantity in the input.
>
> **A4-02 (a test): ACCEPTED.**
> - Add `fetch_candidate_by_id` (D84's read inside `_panel_risk_inputs`, `latches.py:1146-1169`) to the A6 never-500 parametrize at `test_latch_prepared_order_vm.py:608-611`.
> - Assert that the affected row renders with no marker and no affordance.
> - Show it RED with the local try/except removed, as a temporary mutation that is never committed.
>
> **A4-03 (T11 prose plus a test): ACCEPTED, on both legs.**
> - Era-word the `instrumented_replay.py:80-87` docstring (0.3b; no computation moves).
> - Era-pin the docstring of the test at `:244-265` as a pre-boundary-shaped fixture.
> - ADD a pin that a risk-flagged `aplus` row returns `None` from the binding-constraint derivation (census item 3: a behaviour true after D84 with no pin). Show that it fails under a mutation.
>
> **Correct the SS-1 table rows for `:244`, `:248` and `:265`** (misclassified), and the SS-2 table if the same lines appear there.
>
> **SS-3 (uncounted), narrow, BEFORE round 5.** A4-03 escaped both sweeps as the paraphrase "genuinely A+".
> - Grep `research/` and `tests/research/` (excluding `research/studies`) for `genuinely`, `truly`, `nothing failed`, `all criteria pass`, `all pass`, `passes everything` and `fully qualified`, each near `A+`/`aplus`.
> - List the hits under SS-3 with the SS-1 dispositions. Fix any claim as prose.
>
> **Then:** the T12 gates IN FULL on the final head, every suite file head-stamped.
>
> **ROUND 5 is AUTHORIZED in writing.** It is justified by A4-01 and A4-02: new, in scope, not reopened, and the first code and test findings in four rounds. This is the recipe's round-5 check-in. The ledger's composition says CONTINUE: round 4 is not an oscillation and reopens nothing.
> - Form: round 4's form. Point the reviewer at the A4 fixes, the census class, the checklist, CHARC's amendment 3, and the SS-3 list.
> - Save it to `...\exec\round5\`.
> - **The THREE-BRANCH STOP RULE applies unchanged** (section 1):
>   1. **Clean:** the loop ends.
>   2. **Only T11-class prose majors:** fix them without a round. The loop ends STOPPED-AND-ROUTED, branch 2.
>   3. **Any critical, or any major on code behaviour, the envelope or a test:** STOP at the gate, with no fix applied.
> - There is no round 6 without the orchestrator's written authorization.

CHARC's ruling (`20261026T185127Z`), literal block quote:

> PRIMARY charc on A4-01 (20261026T184907Z item 1). Read on d84-exec at 1ae5b141: view_models/trades.py:793-815, partials/trade_entry_form.html.j2:92-112, partials/sizing_hint.html.j2, routes/trades.py:579-643 and :2098, the plan's entry-form paragraph (section 3 of T8) and its witness step (plan :1024), the executing brief :13. RD CC: the clearance extension below touches the H4 manual path RD's cohort semantics ride on; no RD ruling asked.
> 
> RULING: (a) and (b) collapse into one answer. A4-01 is IN D84 as a T8.3 COMPLETION, and the plan-stage clearance is EXTENDED by this ruling to the change named below. The brief's STOP-and-return (:13) was the right act; this is the gate-holder's answer to it. My merge-gate read verifies the extension on the final tree, as it verifies everything else.
> 
> GROUND. The plan's T8.3 sentence 'the template shows it in the suggested_shares == 0 branch' carried a PREMISE: that suggested_shares is zero when the sizing is zero. The Phase-13 SB1 override at trades.py:812-815 makes that premise false whenever the Schwab auto-fill is populated, and that is not a corner: under F1-A EVERY H4 fill takes the manual path (attest on the card, then the entry form), and the entry form on that path is auto-filled FROM the fill. So D84's stated zero is absent on exactly the path D84 exists to record, and the plan's own witness step (:1024, 'the entry form for that ticker shows the H4 prefill') would have found it. This is the 0.5b census class (sections 4 and 5 are lower bounds; the plan's site list did not read the override), not a new feature. Option (c) is refused on its own terms: a declared limitation that voids the arc's purpose on its primary path is a refusal of the arc wearing a limitation's label. The pre-D84 line on that path ('Suggested max: N sh (~$0.00 risk = 0.00%)', N from the fill, the risk from a zero-share sizing) was already false; D84 inherits it only if it leaves it.
> 
> FORM (the cell's proposal, with one constraint). The HINT keys on the SizingResult; the shares INPUT keeps the broker quantity. Do NOT overload input_shares for it: that field is the operator's SUBMITTED value on a drift-retry (:238, '0 = no override'; set at routes/trades.py:2098) and carries resubmit semantics (the hidden-anchor family). Add a distinct prefill field -- call it prefill_shares -- equal to the auto-fill's share count when populated, else the sizing-derived shares; the input's value becomes input_shares if set, else prefill_shares; suggested_shares stays sizing-derived and the hint's existing branch order (suggested_shares > 0 -> the numbers; elif sizing_zero_line -> the stated zero; else the guidance) is unchanged. The SB1 purpose ('the input pre-population matches the actual fill') is preserved on the input, where it belonged. Side effect, correct: on an auto-filled form with FEASIBLE sizing the hint now states the sizing-derived maximum rather than echoing the fill's count -- the initial render then agrees with what the HTMX swap (sizing_hint.html.j2 Mode 1) already renders from sizing alone.
> 
> Envelope: swing/web only (one view model, one partial), no swing/trades, no schema, no tripwire. No order, money or cohort path reads the hint (the cell's claim; I checked suggested_shares readers by grep: the partial and the route comment only).
> 
> DISCRIMINATORS, RED first, TestClient on the real form path: (1) populated auto-fill + risk-bound-zero sizing -> the hint renders the stated-zero line AND the shares input is prefilled with the broker quantity (RED today: the numbers line renders); (2) populated auto-fill + feasible sizing -> the hint renders the sizing-derived shares and risk, not the fill's count, and the input is prefilled with the fill; (3) a drift-retry with input_shares set -> the input shows the submitted value (the existing behaviour, kept green).
> 
> RECORD: transcribe as 'amendment 3 (CHARC)' in the exec ledger, block-quoted; REPLACE the plan's T8.3 sentence (the suggested_shares == 0 premise) with the prefill/hint split -- never annotate it. The section-6.3 witness step on the entry form now includes the auto-filled case: the stated zero visible with the broker quantity in the input.
> 
> A4-02 and A4-03 as you hold them: no dissent. Round 5 may launch on my account.

RD's answer on the fourth harness (`20261026T185015Z`), literal block quote:

> PRIMARY rd on 20261026T184907Z item 2 (the fourth harness). Answer before round 5: NO 0.3b sentence in the tree. SS-2's not-a-claim classification STANDS on my read.
> 
> Read at 1ae5b141: diagnostic_run.py:8 names the operator HYPOTHESIS the diagnostic was built to probe ("low capital binding risk_feasibility"), dated to its run; it is not a statement about current production, so it does not go false at the merge. What changes is the probe's REACHABILITY: through current evaluate_one the risk criterion can never bind the bucket, so the capital-multiplier matrix can no longer find that hypothesis true or false -- the same O-1 family, by a different route. The module that derives the binding constraint (instrumented_replay.py:52, :74) is already under your A4-03 era-wording; recompute_binding_prod_gated.py carries its pin (row 4). Nothing else in that harness reads false to me.
> 
> It goes in my re-use precondition line as the fourth harness, with the mechanism: the capital-multiplier probe is unreachable under post-D84 production; re-run it against the pre-D84 mirror (recompute_binding_prod_gated.py) or re-state the hypothesis as the risk FLAG's incidence against capital, which post-D84 rows do carry (the persisted risk row), not as bucket binding.
> 
> A4-01 is CHARC's; A4-02/A4-03 are yours; read as CC, no dissent. Round 5 may launch on my account.
