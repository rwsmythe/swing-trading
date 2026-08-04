# Phase 21 Close Audit — CHARC

**Auditor:** CHARC (the 2026-07-29 generation; the phase spans two CHARC generations — scoping and 21-A/21-D under the 07-02 generation, everything from the H1 amendment onward under this one).
**Audited head:** `1c0ddb2b` (feature-complete: four production arcs + two riders merged). **Date:** 2026-08-04.
**Scope caveat, stated up front:** the **close RITUAL has not yet run** (archival sweep, CLAUDE.md line-3 compaction, orchestrator-context compaction, §6 log compaction). This audit binds to the feature-complete head; per the D21 rule, **the final "green on close" claim requires a cheap post-ritual re-verification** (suite + probe re-run postdating the ritual's last commit). §8 lists what that addendum must re-check.

---

## §1 Binding gates on the audited head — CHARC's own runs

| Gate | Result |
|---|---|
| Fast suite (own run, postdating `1c0ddb2b`) | **10122 passed / 7 skipped / 0 failed** in 5:26 — read off the run, not carried forward; matches the orchestrator's merged-head number exactly |
| `ruff check swing/` | clean, exit 0 |
| Live DB | **schema v33**; `latch_order_intents` present, **0 rows** (the first real parity row still unwritten — the sizing-basis fix and any knob work land before it by RD's conditions) |
| Worktrees | none remain; all branches deleted at merged SHAs |
| `Co-Authored-By` streak | **4,253 consecutive trailer-free commits ending at HEAD** (4,325 total; the only exceptions remain the 3 genesis-week commits of 2026-04-17/18 — parsed-trailer scan + raw body grep, both clean) |
| Harness probe | **exactly ONE ATTENTION** — `orchestrator-context.md` at 121,180 vs the 120,000 ceiling, with a named owner and an operator-scheduled remedy (the in-flight-section refresh at this close). RD's ceiling breach was self-cleared mid-phase (132,769 → 34,299, archive companion). Corpus healthy: 47 top-level docs vs the 600 ceiling |

## §2 Tripwire review — ZERO false negatives

Every §3-tripwire event this phase routed correctly:

- **Migration 0032** (21-A, v31→v32) + the **`swing/latches` package** + the §2.10 `swing/data` carve-out (`resolve_ohlcv_window` migrate flag) — §3-passed by the prior CHARC generation, recorded in the charter.
- **Migration 0033** (21-B, v32→v33) — §3 carried in its brief; the two mid-flight amendments both routed: the D30 date-CHECK rider (CHARC-routed onto the rebuild, RD's two requirements + condition) and the ITEM-3 attest/broker-id contract entering 0033 (CHARC-authorized explicitly — amending an unapplied migration is a text edit; after apply it is a table rebuild).
- **21-G** — zero files under `swing/evaluation`, `swing/data`, `swing/trades`, `migrations`; hard stops verified on disk by the orchestrator AND independently by RD.
- **Both riders** — correctly self-certified no-tripwire (docs/config; web+display production code with no schema/module/dep/process/carve-out).
- **The H1 amendment** — §3-passed by this generation (mechanism replaced; see §3 below for its execution status).

## §3 THE AUDIT'S ONE SIGNIFICANT FINDING — the H1 amendment arc is UNEXECUTED, dropped at a generational handoff

**Verified on the live DB:** `hypothesis_registry` id 1 still reads the ORIGINAL criterion (`Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%`); `preregistered_decision_criteria` does not exist; no registry migration has landed (0033 is the newest, and it is 21-B's).

**The arc is fully ruled and was fully ready:** operator-authorized 2026-07-29, RD's brief committed, CHARC's §3 pass GO with the mechanism settled (the additive column, NULL-defined), the canonical text pinned by sha256 and independently reproduced, both acceptance repairs made. It was dispatched to the then-orchestrator at `20260729T090502Z` — **which then ran 21-B to feature-complete (correctly: 21-B was the in-flight priority) and handed off 2026-07-31 naming two undischarged obligations but not this third.** The successor generation drained the inbox but the dispatch was by then an acked message, and no tracker on the orchestrator side carried it. **CHARC's state pointer did carry it, which is how this audit caught it** — the mailbox-is-transport-not-a-tracker rule working exactly as designed, on its first real test at a generational boundary.

**Consequences attached to it:** RD's H1 merge-blocking QA (he reads the live row himself) and **D29** (the `entry_intent` cohort-reader divergence, CARRIED at that gate) are both stalled behind it. And RD's clean-window argument **ages with every closed trade** — the amendment is unimpeachable while H1 has no signal, and trade 19 (the first A+ latch fill) is already in the record pending its label question.

**Disposition: RE-DISPATCH FIRST AT THE BOUNDARY, alongside the sizing-basis fix.** It is small, fully ruled, and needs zero new decisions. Its migration takes the next free number at authoring time (0034 as of this audit).

**Process lesson (harness-architecture candidate, CHARC-lane):** a generational handoff enumerates obligations from the outgoing generation's memory; an obligation that arrived just before an all-consuming arc is exactly the one that gets omitted. The existing mitigation (directors track dispatches they originate in their own state pointers) caught it. A structural fix candidate — the handoff doc must reconcile against the inbox's acked-but-unactioned dispatches, not only against memory — is banked for the harness backlog, not imposed mid-close.

## §4 Register motion this phase

- **OPENED:** D26 (health-VM banner, prior gen) · D27 (dual `data_asof_date` semantics — evidence twice corrected, now precise: structural in one direction, the straddle unifies it with survey hit 7 at 0/140) · D28 (comms/shell body hazard; now with TWO same-day instances + the persistent-CWD variant) · D29 (cohort readers omit `entry_intent`; carried at RD's H1 gate) · D30 (SQLite CHECK passes on NULL) · D31 (auto-fill entry-date defect, H1-cohort corruption, arc scoped) · D32 (arc-mirror backups in swing-data root, move-then-retain).
- **CLOSED:** **D30** — the paired-CHECK form shipped on 21-B's rebuild at THREE sites with both halves independently pinned; RD-verified at merge QA.
- **MOTION on standing items:** **D5** firing RETRACTED (prior gen's own n=1 error, four-sample refutation; suite now 10,122 at ~5:29 — still inside variance, no trend claim). **D9** upgraded to demonstrated-cost, REFRAMED (ambient-state, code-or-test), **five instances** (two in one day, one production-side) — **sweep scheduled at this close, operator-concurred.** D12/D15/D16/D17 unchanged WATCH.

## §5 What this phase built that outlives it (the harness ledger)

Conventions, every one born from a same-phase failure and most tested in anger before close:
- **Supersession-by-replacement** + the standing brief clause (violated by its own author 11 minutes after committing it — the argument for structural over remembered), exercised by RD, the orchestrator, and the recipe repoint.
- **A clearance attaches to the tree the gate-holder verified** (docs-only lands GREPPED-not-assumed; code/tests re-open).
- **One supersession per message** (the actionability half; RD's own second correction left behind at a merge).
- **The review ladder** (§5.1) — four instruments, four structural blind spots, no rung credited for the rung below; **plus the composition gap** (no rung reviews two arcs' composition — three instances this phase; the rebase/merge-integration step is the de-facto gate and is now a named xhigh escalation).
- **The banner assertion + the tokens-used FOOTER assertion** (round started right / round finished / ERROR-free middle — three assertions, three failure windows, no overlap), both proven in anger.
- **Premise-sourcing with five owners** + gate visibility, exercised in both directions (holds stated; the clean case stated affirmatively at merge).
- **The model/effort recalibration** (Fable 5/high directors, Opus 5/high orchestrator + two named xhigh escalations, Opus/Sonnet 5 implementers) with **the discriminating rule**: removable only if it compensates for a MODEL limitation, never a PROJECT fact or a cross-agent evidence gate.

## §6 CHARC self-critique (this generation; every item net-caught, none reached a witnessed merge)

1. **The "one-line default on a display surface" dispatch premise** — a fact sourced from a colleague's trace instead of the code (7→8 render sites; a web-editable knob). The premise-sourcing rule violated by its custodian; caught by the orchestrator's grep-before-authoring.
2. **The ruling-fidelity pass sequenced under the wrong OWNER** (right requirement; RD corrected — handing a fidelity check to the role that wrote the encoding asks it to audit itself).
3. **The recipe-residual undercount** (claimed 1; live-imperative truth 4) — my own completeness lesson applied to my own catch, twice corrected.
4. **The state-pointer annotation** 11 minutes after committing replace-don't-annotate (self-caught, replaced, reported as evidence for the structural argument).
5. **The unfounded routing alarm** on RD's 21-G clearance (peeked, disproved my own concern, said so).
6. **The "7-line block" count** (8 — immaterial, and exactly why a line count was never a safe referent).

The pattern across 1, 3, and 6 is one failure mode — counting/characterizing without the full-pattern grep — and it is the same one the orchestrator (×2) and RD (incidence, unrounded quantity) hit this phase. The **"a grep that names three files can only ever return three"** formulation goes into the recipe's verification vocabulary.

## §7 Boundary proposals (per §2.1 — the operator commissions)

The ordered queue stands as recorded in `charc-state.md` #−1, with §3's finding amending it: **0. RE-DISPATCH THE H1 AMENDMENT (new; first, alongside item 1)** · 1. sizing-basis fix (RD-elevated) · 2. criteria_lapsed §3 pass · 3. cancel questions · 4. D9 ambient sweep · 5. prescriptiveness audit · 6. D31+A-4 entry-date arc · 7. D27 provenance arc (now carrying rung-A EQUALS + `latches.py:1381`) · 8. Phase-22 demand decomposition (item 1 = knob removal + disclosure-block deletion + the one-cent exemption revisit) · 9. D32 backups retention · 10. orchestrator-context compaction · 11. `_PRICE_DP`×4 consolidation.

## §8 POST-RITUAL ADDENDUM (2026-08-04) — every item re-verified. **THE AUDIT IS CLEAN. PHASE 21 IS CLOSED.**

The §3 finding was **discharged before the ritual ran**: the H1 amendment executed, merged (`f2c92dfd`), and live-migrated the same day — **schema is v34**, RD's gate closed on his own live-row read, the amendment five-times independently verified (four hash derivations + the live read). Its arc contributed one further major finding: the original migration would have **FAILED OPEN** (a zero-row UPDATE fabricating a preserved-original while concealing a drift) — codex-auto-review caught it; PRE/POST guards with self-describing constraint names shipped instead. Consequence: **D29 went live-visible** (H1 renders 3/20 where the shipped criterion says 2/20) and is re-scoped to FOUR reader sites and re-prioritized to **first post-close arc** (RD's own reversal). Interim: the operator reads H1 from the criterion — 2/20.

**Ritual verified (`d7ab5c96` + the two director disposition commits):** the §4.3 sweep moved 5 clean artifacts, top-level docs 48→**41**; **the D21 grep caught shipped migration 0034 citing both H1 documents by path — both RETAINED on the Phase-20 production-cites precedent** (the rule's best save yet: a sweep on the naive dead-after-merge rule would have left a shipped migration pointing at two dead paths). Five citations-deferred artifacts were dispositioned by their owning directors (CHARC 2 archived+repathed at `81d2c95c`; RD 1 archived+repathed, 1 deliberately retained, at `d1770240`; the recalibration brief retained while it grounds the live allocation). CLAUDE.md line-3 recompacted (3,400 chars; schema v31→**v34**; the streak stated WITH ITS METHOD after the orchestrator's own scan artefact — its string-grep broke on a commit *mentioning* the convention and returned 2,098; the trailer-KEY filter gives **4,263**, reconciling exactly with this audit's 4,253 + the commits since; the fourth grep-proves-what-it-names holder in one week, and the reason the method now sits beside the number). orchestrator-context refreshed to 117,246 — **the probe reads ALL CHECKS WITHIN THRESHOLDS, zero ATTENTION.**

**Final own-run gates, postdating my archival commit (`81d2c95c`):** suite **10158 passed / 7 skipped / 0 failed in 5:06** · probe zero-ATTENTION · trailer audits zero throughout the ritual range. RD's concurrent disposition commit (`d1770240`) landed during the suite run and is **verified docs-only** (one rename + two repaths of his own referrers) — under the clearance-attaches-to-the-tree rule it cannot move the result, and that rule is applied here by its stated precondition: grepped, not assumed.

**PHASE 21 CLOSED at v34** — four production arcs, two riders, the H1 governance amendment, three live-migrations each rehearsed and verified, 10,158 tests, zero tripwire false-negatives, and a phase that was audited by the instruments it built.
