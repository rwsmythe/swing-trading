# Orchestrator handoff — 2026-08-13 — Demand C at the executing boundary

**From:** the generation that QA'd and merged D31-exit, ran the §8.5 wave-close pass, executed the four
ledger dispositions, and took Demand C from commissioning through writing-plans and both director gates.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact below was re-derived from disk or the live DB at handoff time.** That is not a formality:
**three separate written inventories went stale under me today**, the last of them an hour ago. Do the
same before you rely on anything here.

---

## 1. YOUR FIRST ACTION — the one acked-but-unactioned dispatch

**Demand C EXECUTING is commissioned, briefed, gated, and NOT DISPATCHED.** That is the whole of the
in-flight work and it is the thing a from-memory handoff would drop.

- **Brief:** `docs/demand-c-executing-brief.md` (`2a1739bb`, on main).
- **Plan (the spec):** `docs/superpowers/plans/2026-08-12-demand-c-cohort-provenance-arc.md`, 2624
  lines, on branch **`demand-c-plan`** @ `32fd80a4` in worktree `.worktrees/demand-c-plan`.
- **Both director gates are PASS** — CHARC §3 clear + envelope extension approved (`6cc13ec1`); RD's
  gate PASS on all four items (`ea41dabf`).
- **Dispatch as `implementer-opus-high`** into a NEW worktree `.worktrees/demand-c-exec` off current
  main. The operator's "go" is the only thing missing.

**Deadline:** shipped AND applied to the live CADL row before **monthly read #3, first trading week of
September.** The live application is a SEPARATE operator-witnessed gate, step by step, after merge —
§5 of the brief says so and the implementer must not touch the live DB.

**READ §0 OF THE BRIEF BEFORE YOU DISPATCH.** The plan is **NOT converged-clean**: rounds 10 and 11's
fixes are unreviewed because the loop terminated on a disposition rule, not a clean verdict. The plan's
author flagged that against its own interest and both directors accepted it on that basis. **Do not
cite the plan as converged**, and make sure the executing A-loop knows which sections carry the extra
risk.

## 2. STATE, re-derived

**main `2a1739bb`, 12 ahead of origin, UNPUSHED.** I pushed once today (100 commits, `3f75127b..7223d812`);
director docs have accumulated since. **Schema live v35** (CLAUDE.md line 3 said v34 and CHARC corrected
it; Demand C's migration will be **0036**).

**Worktrees:** `.worktrees/demand-c-plan` (branch `demand-c-plan`, the plan — keep until Demand C
merges). The `d31-exit` worktree and branch are **removed and deleted**; that arc merged at `5a6d39cd`.

**Suite on the merged head: 10815 / 7 skipped / 0 failed.** Two known non-regressions, both named in the
brief's §4.8: the ladder-lock flake (load-sensitive by construction) and
`test_run_stub_skip_exits_zero`, **which fails on `main` itself** — I verified by running it there, so
do not read it as a regression and do not fix it.

**Ledger: ONE open discrepancy, 86** (`equity_delta`, `material_to_review=0`, the known monthly-deposit
drift class). Discrepancies 96/97/98/99 were closed today at the surfaces, operator-run, each with a
per-row reason.

## 3. LIVE TRADING STATE — and it moved twice today

**OPEN: ORKA (trade 22, 1 share, `managing`) and CADL (trade 23, 18 shares, `entered`).**

- **AMN (20) closed** 2026-08-11, stop-hit, ≈ **−0.996R**. It is the deliberate-`entry_intent`-NULL row,
  so the project carries **a closed trade with a realized result in no cohort at all**. That is correct
  under the operator's ruling and is Demand A's motivating case.
- **LQDA (21) closed 2026-08-12** — stop fill 46 at **84.70** against a 91.81 entry, 2 shares.
  **RD's own message hours ago still listed it as open.** I caught it only because I re-queried.
- **CADL (23) is Demand C's live target:** `hypothesis_label` NULL, `candidate_id` NULL,
  `trade_origin='manual_off_pipeline'`. `entry_intent='standard'` is already set.

## 4. THE RULINGS THAT WILL BITE IF YOU FORGET THEM

- **The CADL target label is `'A+ baseline (aplus); failed: TT8_rs_rank'`** — the faithful derivation,
  NOT the clean sibling string. RD ruled the literal string is not wanted. Candidate 12341 carries
  `TT8_rs_rank='na'`.
- **`<=`, not strict `<`**, for "PRE-DATE the fill" — strict refuses 10 of 11 live candidate-bearing
  trades including the two the rule was derived from.
- **The anchor is the cited row's own `action_session_date`, NEVER `evaluation_runs.data_asof_date`**
  (a cohort MAX, gotcha #30). `data_asof_date < action_session_date` on **138 of 138** runs — the wrong
  anchor is monotonically MORE PERMISSIVE. **Both anchors ACCEPT on CADL**, so the acceptance case
  cannot discriminate; the live discriminator is trade 21 / LQDA across a weekend.
- **The envelope extension is BOUNDED**: the constant + the two `dates.py` defaults + this arc's
  imports. The other five-plus `Pacific/Honolulu` spellings are D37's, not this arc's.
- **The migration stays ADDITIVE.** No rebuild enters through review.

## 5. OPEN, WITH OWNERS

| item | owner | state |
|---|---|---|
| **VSTS ledger record** | operator | broker order cancelled 08-03; the decline is UNREACHABLE (prepared order withheld → no decline control). CHARC canonicalized it as a deadlock; ruled (c) expire 2026-09-08 + (d) Phase-22 abandonment path |
| **The unexplained FTRE cessation** | RD | the chain stopped at run 97, four days BEFORE the fix landed — so the fix is NOT what silenced it. Banked |
| **Demands A and B** | Phase-22 scoping | C-first per RD's concession |
| **D37 / D38 sweeps** | CHARC | ONE scoping item, not two — both are TEXT-timestamp traps walking the same sites |
| **`derive_trade_origin`** | not scoped | reads "latest complete run", not the run the operator acted on — the ROOT CAUSE of CADL's empty keys. Recurs every time a ticker drops off the screen between recommendation and fill |
| disc 86 | — | untouched, immaterial |

## 6. WHAT THIS GENERATION LEARNED, and it is mostly one lesson

**I stated three things as facts that a bounded search or an unpropagated premise had produced, and I
was corrected on all three — twice by a director and once by the operator.**

- **"No rung would have caught this"** — asserted from a grep of ONE file, which was the one file where
  the rule was queued to land but had not. The FIVE_ROUND_GATE existed the whole time. **Report every
  absence with the search that produced it**; "grep of the recipe" would have been truthful and
  self-limiting.
- **"The D31 entry-side fix TOOK"** — post-hoc reasoning. The emission chain stopped four days before
  the fix existed, and I had both timestamps in hand and never crossed them.
- **Dropping the WSL PATH prefix** because I understood the expansion mechanism, overriding recorded
  behaviour with an inference. Cost a dead review round that **exited 0**.

**The composite rule, and RD and CHARC each hit it independently the same day: a method sound for the
shape it looks for is blind to a shape that exists. The response is a method, not more care.**

Two smaller ones worth keeping: **an inventory is a snapshot — a cleanup pass re-derives, it does not
tick a list** (that is what surfaced disc 99 and the sequence that broke RD's own forward test); and
**exit code 0 is not evidence a review ran** — two dead Codex runs today, two different signatures,
both exiting clean. The banner is the evidence.

**The instruments worked.** The five-round gate fired on its first use and said CONTINUE where the same
criterion would have said STOP on D31-exit. The accepted-limitations declaration ran at seven items with
nothing re-raised and findings still returning. The introduced-vs-banked merge gate let a
`NEW_CRITICAL_MAJOR_FOUND` verdict pass on provenance evidence rather than blocking an arc for defects
it did not cause.

**Do not read the candour here as a warning about the work.** Every one of those errors was caught, and
three of the four were caught by someone else's instrument doing exactly what it was built to do.
