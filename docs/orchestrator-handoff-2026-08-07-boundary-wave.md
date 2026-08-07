# Orchestrator handoff — 2026-08-07 — the Phase-21 boundary wave, mid-flight

**From:** the orchestrator generation that drove the Phase-21 close and the boundary paydown wave. Handing off on context exhaustion, at a clean boundary.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.
**Main HEAD at handoff: `01c91ae8`.** Schema **v34**. Suite on main **10322 / 7 skipped / 0 failed**.

---

## 1. YOUR FIRST ACTION

**3b is paused at the pre-Codex gate with everything committed.** Its full state — branch, the ten commits, the exact stopping point, every ruling pointer, and the constraints not to re-litigate — is in **[`docs/3b-resume-state-2026-08-07.md`](3b-resume-state-2026-08-07.md)**. Read that, not this, for 3b. Delete it when 3b merges.

Remaining for 3b is only the §3 Codex loop + cold audit, then the post-convergence suite and trailer audit. No design work, no open questions. Resume by dispatching a fresh implementer (`opus-high`) pointed at that file — the prior agent's context is gone.

## 2. WAVE STATE

**Phase 21 CLOSED 2026-08-04** at v34 (audit `docs/phase21-close-audit-charc.md`). The boundary paydown wave then opened — brief: `docs/phase21-boundary-paydown-commissioning-brief.md`, seven pre-ruled items.

| | |
|---|---|
| **DONE, merged** | item 1 D29 four-site `entry_intent` · item 2 sizing-basis · `coverage_gaps` clause-1 · item 3a `declined` |
| **PAUSED** | item 3b — see §1 |
| **NEXT** | item 4 — cancel decoupling · the declined surface (render/route **+ flag B's server-computed session**, its write half) · `_PRICE_DP` ×4 · the below-pivot refusal with the **equality-preservation** refinement |
| **AFTER** | items 5 (D31 + A-4), 6 (D32 retention), 7 (D9 sweep) |

Also done: the recipe window (six banked items, `60488762`), the Phase-21 close ritual, the item-3 plan merged to main.

## 3. HOW THIS WAVE RUNS

- **Serial by default.** Parallelism is permitted ONLY with the merge-integration composition step **named as a gate in your dispatch**. I invoked it once (3a ∥ `coverage_gaps`); it discharged clean and is now precedent, not policy.
- **`--ff-only` refused five times** on a moving main. That guard works — rebase, re-verify the tree is byte-identical to what the gate-holder cleared, then merge.
- **Verify every brief premise against the code before dispatching.** This produced **five** corrections at dispatch time — a seven-site count that was eight, a "code-only default" that was web-editable, a worked case from an illustrative fixture, a CHECK-widening tripwire on an enum with **no SQL mirror**, and a stale VSTS state I inherited from a director's older message. It is the highest-yield step in the protocol and the recipe now says so.
- **State what your grep PROVES.** I was caught by this three times and self-caught each: `_PRICE_DP` (3 vs 4), `invalid_ohlc` (tip-diff vs branch-commits), and nearly the #11 atomicity call. Scope the query to the claim.
- **QA against disk, never against the report** — and the report is usually right. The exception that mattered: 3a's flag C rested on "no changed lines" about a line the diff changed. RD then confirmed the conclusion on the *mechanism*. Refuse the evidence, not necessarily the claim.

## 4. STANDING OBLIGATIONS

- **Item 4 carries flag B** as the write half of the declined-surface piece (RD's counting — not a fifth piece; splitting a feature's read and write across arcs is the interleaving mistake). CHARC's **artifact-scale watch** attaches: if findings cluster as INTERACTIONS between pieces, propose the split — an outcome, not a failure.
- **Directors:** CHARC (`docs/charc-state.md`) + RD (`docs/rd-state.md`). A director's action-bearing inbox message is operator-pre-authorized. Post status/return_report to them **after** QA; the implementer never posts.
- **The operator authorizes every merge and every dispatch**, and drives witnesses **one step at a time**. Do not hand him a multi-step runbook.
- **Comms:** singular inbox, `--to orchestrator`, no `:<sid>`. Run `role_mail.py` from the MAIN repo dir. Bodies backtick-free and `$`-free.

## 5. WHAT THIS GENERATION LEARNED

- **A ruled decision with no arc decays.** The H1 amendment sat undone five days because a handoff enumerated obligations from memory and the inbox's read-state is generation-agnostic — "acked" and "actioned" are one bit with no owner. I hit the same class twice more (flag B unassigned; the item-3 plan on an unmerged branch). **Give every ruling a parent before you move on.**
- **Five of the six recipe items came from implementers instrumenting their own failures** — the self-matching `pgrep`, cp1252 prompt mangling, the unanchored `ERROR` grep, a redirect that silently ate three runs, and a disqualification applied against its own convenience. The harness improved from the inside, not from the gate. Read return reports for that, not just for compliance.
- **A witness must be reachable, not merely correct.** I built a gate around a surface I had only ever reached by `curl`, and sent the operator to it twice. Zero A+ candidates that day meant the cards genuinely weren't there — and RD's "merge, then witness" ordering, which I second-guessed as loose phrasing, was load-bearing for exactly that reason.
- **Two honest non-convergence reports beat one claimed convergence.** Both were right, and the second produced the diagnosis (artifact scale) that split item 3 correctly.
