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
