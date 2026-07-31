# Orchestrator handoff — 2026-07-31 — Phase 21 mid-flight, 21-B at the witness gate

**From:** orchestrator gen `5a1f33a0` (drove all of Phase 21: 21-A, 21-D, 21-G merged; 21-B carried from commissioning to the witness gate). Handing off mid-arc at the operator's direction, not at a phase boundary.
**To:** the next orchestrator generation.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.
**Main HEAD at handoff: `7ced0de9`.** Live DB **schema v32**. Suite on main ~9512/7/0; on the 21-B branch **10080/7/0**.

---

## 1. STATE — read this first

**PHASE 21 (Latched-Entry Execution Surface & Comms Simplification) is OPEN.** Three of four production arcs are merged; **21-B is the last one and it is at the operator witness gate.**

| arc | state |
|---|---|
| **21-A** latch panel + telemetry | **MERGED** `1955aa59`. Shipped migration 0032, schema v31→v32, live-migrated and witnessed. |
| **21-D** comms singular inbox | **MERGED** `57e4e797`. Per-gen orchestrator tracking retired; history archived, never deleted. |
| **21-G** close-provenance asymmetry | **MERGED** `6b1a7860`. No schema. |
| **21-B** prepared-order form + execution-parity ledger | **BRANCH `phase21-b-prepared-order`, head `c12475cc`, 51 commits ahead of main. NEEDS REBASE (main moved). Converged, QA'd, awaiting the OPERATOR WITNESS.** |
| **21-F** dashboard surfacing | Proposed, **blocked** on the telemetry contract settling. Order-cache is a hard prerequisite. |
| **21-C** execution (preview→live) | Deferred behind stage-1 evidence + an operator-signed L2 endpoint diff. |
| **21-E** D5 runtime | **Retired** — D5 retracted on CHARC's four-sample measurement. |

## 2. WHAT YOU OWE, IMMEDIATELY

### 2.1 The operator witness — FIVE paths, STEP BY STEP

**The operator has stated (2026-07-30) that witnesses are driven ONE STEP AT A TIME.** Present a single step, wait for his observed result, then the next. **Do NOT hand him a multi-step runbook** — a batch collapses the gate into a self-report. Memory: `feedback_witness_step_by_step`. Pre-verify each expected value against the live DB *before* asking him to look, so a mismatch means something.

The five paths, and why each is here rather than in a byte test:

1. **The validity prompt**, end to end, **by clicking** — not by asserting a template contains a string. *This is the one that matters most:* the prompt did not exist for most of the arc, every validity byte-test passed anyway because each built its own POST, and the agreement measurement would have sat permanently at `validity_unknown`. RD called it an operator-witness catch, not a byte-test catch.
2. **The cancel control** — same standard. Found by asking "what else was in the manifest and is missing the same way?"
3. **The A→B→A correction path** — RD's ruling 3. A byte test cannot tell a correction from a replay any better than the code could.
4. **A zero-data render** — RD's ruling 4 acceptance criterion. Every rate must read **unmeasured**, never *clean*. Only visible on a screen.
5. **The Route-B panel geometry** (CHARC, added 2026-07-31) — confirm the price line and the prepared order **agree about what is known**. This is the cross-arc defect that was just fixed; witness that it stays fixed.

Run the server from the worktree (`$env:PYTHONPATH="."; python -m swing.cli web`), never the editable-install `swing` entry point. **Precedent worth reusing:** for states the live DB does not currently show, take a `sqlite3` `.backup()` snapshot, mutate the copy, point a second server at it via `--config` with `db_path` overridden, and witness both states side by side. That is how 21-A, 21-D and 21-G were witnessed. Tear down explicitly and **verify the ports are free** — a detached uvicorn survives task teardown (memory `feedback_taskstop_does_not_kill_detached_server`).

### 2.2 TWO PENDING OBLIGATIONS I AM HANDING YOU UNDISCHARGED

**(a) A polluted git trailer on commit `35c1cdba`** (`test(latches): Task 10 — behavioural pin of ZERO Schwab writes…`). Its final `-m` paragraph begins `Also:`, which git parses as a trailer key, so that commit's `%(trailers)` is **non-empty**. It is **not** a `Co-Authored-By` — the streak is intact — but it breaks the audit that *proves* the streak. Per recipe §2 this is stop-and-flag for an implementer and **the orchestrator's to resolve at merge** by amend + force-with-lease; safe because the branch is unpushed. **Every implementer has been told to leave it alone.** It survives rebases with a new SHA — re-find it with `git log main..HEAD --format='%h %(trailers)'`.

**(b) The recipe tier repoint — OPERATOR-RULED, deferred deliberately.** The operator concurred (2026-07-30) that `docs/implementer-dispatch-recipe.md` should point at his **canonical `strong`/`fast`** profiles rather than `review-strong`/`review-fast`. Reason: `review-strong` resolves to **gpt-5.5** while canonical `strong` resolves to **gpt-5.6-sol** — the recipe currently points every binding review at the weaker model. **Deferred until no implementer is mid-convergence**, because renaming the tier an in-flight dispatch is using changes the invocation underneath it. Both names resolve today, so nothing is broken meanwhile. **Do this once 21-B's implementer work is done.**

### 2.3 Then: RD's merge QA → merge → live migration

After the witness: post the QA'd return to `charc,rd`, get **RD's merge-blocking QA**, then rebase onto current main, `merge --ff-only`, re-run the suite on the merged head, and **publish that number** — RD asks for the number that will actually be on main, not a pre-merge one.

**The merge and the live migration are ONE atomic operator-authorized step.** The schema guard is an **exact match** (`current != EXPECTED`), so the moment main expects v33 the live DB must follow or the weeknight pipeline hard-fails. **Time it clear of the 17:30 HST window.** 21-A's migration is the worked precedent: rehearse against a `.backup()` snapshot first, then `python -m swing.cli db-migrate`, verify schema + row counts + the new table, and confirm the panel renders against the live DB before declaring done.

## 3. OPEN DIRECTOR QUESTIONS (do not decide these)

- **Rung A proves *equals*, not *is*** (routed 2026-07-31, unanswered at handoff). A same-cent coincidence on top of a per-ticker lag could still fabricate a rung-A match. **The 21-B fix is a strict tightening regardless** — pre-fix, every stamp-matching close was asserted with no archive check at all. The question is whether rung A's definition tightens in a **later** arc; its remedy (per-row `close_asof_date` at write time) is a named hard stop needing a migration. My read: it belongs with the two joint false-all-clear priorities already scoped — the stale-close asymmetry and the run-level-stamp provenance gap — same family, same remedy.
- **`latches.py:1381`** renders a run stamp as a close's date in a *label* (shipped 21-G; not a gate, asserts nothing, reaches no ledger). Out of scope where it sits; may belong with the above if that arc is scoped.
- **Banked for 21-B/later:** the beacon subset contract; `_PRICE_DP` defined twice (`orders.py:32`, `service.py:41`) — CHARC scoped it as a close-time item.

## 4. WHAT THIS GENERATION LEARNED — carry these

- **A stop rule only counts if you honour it when it goes against you.** I pre-committed a falsifiable band + stop rule before round 30, it was falsified on both halves, and the implementer stopped. Both directors called that the method working. Do it again.
- **Trend lines lie when the tooling changes underneath them.** I diagnosed this arc partly from finding-count trends; CHARC pointed out that a stronger reviewer arriving mid-loop can legitimately surface findings the weaker one missed. **Judge findings on content, not the trend line.**
- **Verify what a grep actually proves.** I twice concluded from a grep what it did not establish — "all ten tasks complete" (I checked for the *existence of names*, not the *completeness of a task*, and missed an entire unbuilt UI), and a `CRITICAL/MAJOR` count over files that contained the whole plan. Both were caught by others. **State what the grep proves, not what you infer from it.**
- **Say which quantity you measured.** The float-defect incidence went wrong three times in a row — I measured a literal, RD measured the unrounded product, the implementer traced the actual production expression (43 in 100k). Each correction was real. "I verified it" needs to name *what*.
- **Large edits on this plan have a ~4-site miss rate regardless of care.** Three structural interventions each fixed their class and none moved the rate; the counts-to-derivations pass *fed* the generator by being itself a 20-site edit. **The only thing that ever changed the outcome was making re-grep verification mandatory rather than hoped-for.**
- **The durable fix is a mechanism, not a warning.** Three times this week: the banner check, the single-sourced price, the drift guard. RD *predicted* the comparison-layer recurrence in a message and it recurred anyway — because the prediction lived in a message rather than in the code.
- **Rebase/merge-integration is a GATE, not mechanics** (CHARC, harness-architecture §5.1). No review rung reviews the *composition* of two arcs; the cross-arc defect surfaced only because a rebase forced one agent to hold both in view. This project runs parallel arcs routinely.

## 5. STANDING FACTS

- **Directors:** CHARC (`docs/charc-state.md`) + RD (`docs/rd-state.md`). Both generations are FRESH (CHARC handed off 2026-07-29; RD 2026-07-28). A director's action-bearing inbox message is operator-pre-authorized. `decision_request` is operator-only — the L1 lock enforces it (it refused mine, correctly).
- **Comms:** singular inbox since 21-D — `role_mail.py --to orchestrator`, **no `:<sid>` suffix** (it now fails loudly). Run from the MAIN repo dir. Bodies must be **backtick-free and `$`-free** (I reproduced the argv-substitution hazard *inside a message describing it*).
- **Conventions adopted this phase, all in `harness-architecture.md`:** supersedes-in-the-subject · premise-sourcing (source every premise from the role that owns it) · gate visibility (if a merge proceeds with a director gate outstanding, say so in one clause) · preserve-the-quote (a downstream editor corrects surrounding text, never a director's words) · one supersession per message · a clearance attaches to the tree the gate-holder verified (docs-only lands, **grepped not assumed**; code/tests re-open).
- **Codex:** two installs, separate config homes, **both now 0.146.0**. Use the WSL binary (`~/.codex/`). **`codex exec review` is unusable from a worktree** — use the cold-audit form, prompt on **STDIN, never argv**. **Mandatory per-round banner assertion** (recipe §3): model, `effort: high`, `grep ERROR` — a round failing any of the three **did not happen**.
- **Local-first:** main is many commits ahead of `origin/main`; the operator pushes at his cadence.
- Full per-arc record: `docs/phase21-scope-charc.md` + the four commissioning briefs.
