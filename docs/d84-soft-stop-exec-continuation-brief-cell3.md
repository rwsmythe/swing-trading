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
