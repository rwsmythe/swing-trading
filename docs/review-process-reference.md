# Review-Process Reference -- collected directions, with provenance

**Purpose:** a calibration reference for this project's reviewer process, collecting every
standing review direction from the coa-chess harness (where the process evolved under load),
each with its source and the failure that produced it. The failures are the calibration
data: adopt a rule where you face the failure class it closes; skip it where you do not.

**Sources referenced below (all in `C:\Users\rwsmy\coa-chess` unless noted):**
`docs/review-gate-seam.md` (the generic contract) · `docs/review-gate-coa-chess.md` (the
instance fill -- most rules live here, with commit SHAs) · `docs/codex-reviewer.md`
(reviewer mechanics) · `docs/dispatch-recipe.md` (cell-side protocol) ·
`.claude/agents/implementer-*.md` (cell definitions) · `docs/model-prompting-standard.md`
(operating economy).

---

## 1. The architecture: two reviewers, different jobs

**Reviewer A** -- run BY the implementer, iteratively, at its own seat, to convergence.
**Reviewer B** -- run BY the dispatcher/orchestrator, single-pass, as the gating second eye
at accept. Their finding sets are often DISJOINT: A reviews the delta as it evolves; B reads
the whole artifact fresh. *(Source: review-gate-seam.md + orchestrator-context.md; the
disjointness is an empirical observation across ~10 arcs.)*

**The empirical result that calibrates everything else:** in one generation, Reviewer B
rejected 3 of 5 arcs, every time on something a CONVERGED Reviewer-A loop had missed -- via
two distinct mechanisms:
- **Delta-blindness:** a convergence loop reviews the DELTA, so a defect on a line no round
  changed is structurally invisible to it. (A live wrong import survived four converged
  rounds; B's fresh whole-artifact pass found it immediately.)
- **Unmeasured headline claims:** ten deep, productive rounds on internals while the arc's
  own top-level promises ("the bound is bounded", "drops are accounted") were never measured
  end-to-end.

**Calibration takeaway: the independent whole-artifact pass is where load-bearing catches
come from. Terminate the iterative loop early and invest in B, not the reverse.**

## 2. Arc flavors -- match the criterion to the product

*(Source: review-gate-coa-chess.md, the three-flavor structure.)*

- **Software arcs:** critical/major blocking; convergence = zero-new-blocking.
- **Analysis arcs (reports, measurements, verdicts):** created 2026-07-28 after three rungs
  were accepted with the net never closing -- because **`zero-new-blocking` HAS NO FIXPOINT
  ON PROSE**: a good adversarial reader can always find one more sentence claiming a shade
  too much. Criterion instead: **RESULT-BEARING vs ADVISORY** -- blocking only if a finding
  would change a number, verdict, claim scope, or the evidence under them; convergence = two
  consecutive rounds with zero result-bearing findings. Classification is the REVIEWER'S
  call; contested classification counts result-bearing (fail-safe).
- An arc producing BOTH code and a report carries BOTH criteria, each against its own
  surface.

## 3. Loop termination -- the accumulated ruleset (each with its incident)

All in `review-gate-coa-chess.md`, software-arc section, unless noted.

1. **ROUND_TERMINATION** (added 2026-08-06 `0796a6a`; **REBOUND 2026-08-08 `56da984`**):
   *a Reviewer-A round with ZERO NEW BLOCKING (critical/major) findings TERMINATES the
   loop. Non-blocking findings -- result-bearing minors and advisory alike -- are fixed ONCE
   in the terminating round's cleanup and NEVER trigger another round; a result-bearing
   minor is additionally NAMED in the accept record.* The fix's correctness is backed by the
   gates + Reviewer B, not by another A round.
   - *Incident 1 (created it):* two arcs ran ~11 rounds each whose tails were pure
     comment-wording precision -- comment prose has the same no-fixpoint property as report
     prose.
   - *Incident 2 (rebound it):* the first form terminated on zero RESULT-BEARING findings --
     imported from the analysis flavor where result-bearing IS the blocking tier (2 tiers).
     Software has THREE tiers, so the terminator sat BELOW the blocker and EXTENDED loops.
     **Run the tier arithmetic before ratifying an imported rule.**
2. **ENVELOPE_TERMINATION** (2026-08-06 `2d88000`): *a round whose result-bearing findings
   are ALL reachable only OUTSIDE the arc's DECLARED operating envelope triggers
   stop-and-route.* Conditions: the envelope is declared IN THE BRIEF at dispatch (never
   improvised at stop time); out-of-envelope findings are BANKED riding the accept, never
   refuted; the accept states the stop.
3. **ENVELOPE_SEVERITY** (2026-08-09 `b72b4b5`, operator-directed): *severity is
   ENVELOPE-RELATIVE -- a finding reachable only outside the declared envelope is
   NON-BLOCKING BY RULE, banked, never loop-driving, whatever its nominal tag.* Closes the
   gap ENVELOPE_TERMINATION leaves (a mixed round never trips it; a nominal CRITICAL behind
   an impossible caller could spin the loop forever).
   - *Incident:* a third consecutive arc spent rounds hardening against inputs the code
     will never see.
4. **ROUND_LEDGER + FIVE_ROUND_GATE** (2026-08-09 `b72b4b5`, operator-directed): *the cell
   keeps a CUMULATIVE ROUND LEDGER (per round: severity counts, in/out-of-envelope, NEW vs
   REOPENED, reverts). At round 5 and every 5 after, the cell STOPS and reports the ledger
   to its dispatcher for APPROVAL TO CONTINUE. Continue ONLY if NEW, IN-ENVELOPE,
   NON-REOPENED CRITICAL/MAJOR findings are still arriving* -- minors-only, reopened items
   (oscillation), circular identifications, or rabbit-hole depth = stop-and-route.
   - *Incident (why the ledger, not a summary):* an early stop was once ratified off a
     one-line round summary and would have shipped a blocker found in round 7. **The ledger
     is the instrument; a summary is not.**
5. **Guard 5 -- no hard round cap; review runs to convergence** (operator ruling, restored
   2026-08-03) with two guardrails: a round whose findings are all about the review
   APPARATUS triggers stop-and-route, not another round; and MANDATORY DISCLOSURE -- a loop
   stopped short of convergence is stated on the accept with residuals named, and an
   unconverged accept can never carry a GO-direction reading. **Capped/stopped
   non-convergence is a PERMITTED, reportable outcome -- never silently relabeled as
   convergence.**

## 4. What the B pass checks, in order

1. **CLAIMS_FIRST** (2026-08-08 `513de53`): *B checks the artifact's OWN TOP-LEVEL CLAIMS
   first, measured end-to-end against the running artifact, before any code-level lens.*
   The brief's REQUIRED END-STATE section is the claim list.
   - *Incident:* the two headline promises of an arc both failed their first independent
     check after ten productive rounds. Depth and convergence do not substitute for
     does-what-it-says-on-the-tin.
2. Both gate surfaces on the FINAL head (re-run after every commit that changes what a
   guard sees), judged **no-NEW-failures BY NAME, never by a remembered count**.
3. Verification against reality, never the cell's self-report -- reproduce findings, run
   the controls, read the actual artifacts. *(dispatch-recipe.md disciplines + standing
   memory doctrine.)*

## 5. Accept-time obligations (beyond the review itself)

1. **FOLLOWON_DISPOSITION** (2026-08-10 `1c26be1`): *every follow-on, gap, or deferred item
   named in a cell's return report gets an EXPLICIT disposition in the accept record:
   COMMISSIONED (named arc), BANKED (named owner + trigger), or DECLINED (cited ground).*
   - *Incident:* a disclosed follow-on ("a follow-on for whichever arc runs a treatment
     game") belonged to nobody through two clean accepts, leaving the system unrunnable
     with every precondition formally met. **Disclosure without ownership is archive, not
     action.**
2. **FROZEN_CONSUMER_CHECK** (2026-08-10 `1b08a33`): *an accept that moves a producer
   contract/schema version ENUMERATES the frozen instruments consuming it and VERIFIES each
   still admits the new era's output* -- era widenings use a new EXACT closed key set per
   era (never superset-allowed, never check-skipped) and re-verify the frozen baseline
   BYTE-IDENTICAL (mismatch = revert, not explain).
   - *Incident:* third occurrence of frozen-instrument-vs-moving-producer; both arcs gated
     green; the seam was tested by neither; discovered when a completed live run's endpoint
     could not be computed.
3. **The accept trigger is a cell's EXPLICIT DONE** -- never commits that look finished;
   verify cell liveness by PROCESS + MTIME, never artifact presence. *(memory doctrine;
   a premature accept once triggered an irreversible cleanup sweep.)*

## 6. Reviewer mechanics (codex-reviewer.md)

- **Tier by BLAST-RADIUS OF A MISSED FINDING, not task difficulty** -- strong tier for
  production/gating reviews, never tiered down; fast tier for plan/doc rounds. Tier the
  model/effort, NEVER the rigor.
- **State the arc's DECLARED OPERATING ENVELOPE in the review prompt and ask the reviewer
  to TAG findings reachable only outside it.** Report-everything is unchanged -- never tell
  a reviewer to be conservative (it complies literally and drops real findings); the tag
  pre-sorts, never suppresses. **Findings never generated cost zero rounds -- the envelope
  in the prompt is the cheapest control in the chain.**
- **A crashed or stalled round is NEVER a clean round:** check the exit code AND that the
  output carries an actual VERDICT before counting it. "Started" and "finished" are two
  separate facts, each established by evidence.
- Persist every round's verbatim response + per-finding adjudication so convergence is
  independently verifiable from the transcript, not just claimed.
- Diff-only review is blind to defects whose correctness depends on unchanged surrounding
  code -- give the reviewer repo read access or bundle the reference graph.

## 7. Finding adjudication (dispatch-recipe.md + fill)

- **Reproduce, then triage:** in-model defect -> fix; contract-scope question -> escalate
  to the owner; out-of-scope -> adjudicate ONLY with a cited constraint (absent the
  citation it stays in-scope). Never blind-fix, never blind-dismiss.
- **REPLY_PARSE_REUSE** (2026-08-11 `6c2fd3d`, coa-chess-specific but the shape is
  portable): new code consuming an already-hardened contract REUSES the hardened
  implementation -- a fresh parallel implementation is a blocking finding by construction
  (a lock forbids EDITING, never IMPORTING). Fixture corollary: test the REAL producer's
  output forms, not just the convenient one -- scripted fixtures that only emit the clean
  form leave the real contract invisible to every non-model check.

## 8. The economy frame (model-prompting-standard.md + operator rulings)

- **Verification at GATES only, not ambiently.** Short principles over enumerations.
- **Proportionality at the RUNG level:** ask of a whole commission what it produces and
  whether that is worth the spend. A gate is justified by IRREVERSIBILITY, not its track
  record -- count what each finding PROTECTS; block only on the unrecoverable; everything
  recoverable-and-informative is better discovered by running than prevented by rounds.
- **All AI token usage is spend** (build and review included) -- never "free"; label token
  classes. The review process itself is the largest historical consumer; the rules in Sec 3
  exist because review premiums repeatedly exceeded the losses they insured against.

---

## Calibration quick-guide for this project

Start from the smallest set and add rules only when you hit their failure class:

| Adopt immediately | Adopt when the failure appears |
|---|---|
| A/B split (iterative + fresh-eyes gate) | ENVELOPE_* rules (when out-of-scope hardening spirals) |
| ROUND_TERMINATION at the blocking tier | ROUND_LEDGER + FIVE_ROUND_GATE (when loops exceed ~5 rounds) |
| CLAIMS_FIRST at the gate | FROZEN_CONSUMER_CHECK (when you have frozen instruments + moving schemas) |
| Reproduce-then-triage; cited-constraint dismissals | Analysis-flavor criterion (when reviewing prose/reports) |
| Declared envelope in every brief + review prompt | FOLLOWON_DISPOSITION (as soon as multiple arcs run) |
| No-conservative instruction to reviewers; tag don't suppress | Result-bearing-minor naming in accept records |
