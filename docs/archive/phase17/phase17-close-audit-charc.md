# Phase 17 Close Audit — CHARC (Tool Development Director)

**Date:** 2026-06-13. **Auditor:** CHARC, per charter §2.4 (phase audit) + §4.2 (harness probe mandatory at phase close). **Scope:** Phase 17 (Consolidation & Parity-Drift Elimination) — arcs 17-A/B/C/D + riders. **Trigger:** all 17-D actionable items closed (orchestrator report `0867337d`/`f0756f56`); the only remaining Phase-17 items are this audit + the orchestrator's close-out ritual.

---

## 1. Verdict

**Phase 17 is clean to close.** Every commissioned arc landed or was correctly withdrawn; both §2.4 tripwire-gate exercises held end-to-end (CHARC-verified on disk); zero tripwire false-negatives; main green throughout; the consolidation thesis paid off concretely — the work flushed THREE latent production defects that were invisible until the code was consolidated around them. The next-phase deliverable (Phase 18 scope) is already drafted and operator-approved.

## 2. Arc roster + outcomes

| Arc | Outcome |
|---|---|
| 17-A single eval orchestration (D6) | SHIPPED+GATED `bc05958c`. Mirror dead; §6 live gate byte-identical (110 rows, P-but-not-C=0). **Dividend: surfaced + fixed a latent CLI crash** (ERROR-DEDUP IntegrityError). Ratification C1/C2/C3 held (CHARC-verified on disk). **D6 CLOSED.** |
| 17-B step-wrapper extraction (D1) | SHIPPED+GATED `5c86c254`. 9 best-effort sites → tested `step_guard` CM; runner −85 lines; smoke run #103 complete. 2 fatal + 5 special-shape sites correctly left explicit. **D1 PARTIAL** (wrapper sub-debt closed; size/infra-relocation deferred). |
| 17-C exports retention (D3) | WITHDRAWN — premise false (`archive_old_exports` already retains dated dirs). **CHARC error owned** (§5.7 added: absence-claims need a whole-tree grep). Caught at writing-plans, no code. **D3 CLOSED** (resolved-by-pre-existing-mechanism). |
| 17-D bug container | ALL closed: .1 not-a-defect (CHARC veto, verified); .2 dark mode (gated); .3 review_log_cadence revoke re-raise (**D13 CLOSED** — CHARC-found at the 17-B gate); .4 `-n auto` de-flake (**D14 CLOSED** — healed the polluter class, 8132/0 ×2 verified); .5 weather-chart declutter (gated). |

## 3. Tripwire-gate scorecard (the §2.4 gate's first phase in service)

Two live exercises, both held end-to-end, both CHARC-verified on disk (not from self-report):
- **17-A behavior-policy seam** — ratified within-shape with conditions C1 (no defaults) / C2 (post-ruling pruning) / C3 (containment). Shipped code verified: policy = exactly one no-default field, no Lease in the orchestrator, mirror dead.
- **17-B second-fatal site** — the gate's own STOP condition fired (a 2nd fatal site); ratified as-is (the abstraction doesn't grow; both fatals stay explicit). Verified: `step_guard` re-raises revoke; fatals explicit.

**Zero tripwire false-negatives.** One process lesson banked (§5.6: commissioning-brief return-report wording is the orchestrator's post-QA action, not an implementer instruction — from the 17-A premature-post).

## 4. Debt register at Phase-17 close (full state → charter §4)

**Closed this phase:** D6 (17-A), D13 (17-D.3), D14 (17-D.4), D3 (17-C, phantom), D11 (Phase-16 P2 archive pass, confirmed by the probe at 95K). **Partial:** D1 (wrapper closed; size/relocation deferred — not a Phase-18 item, off the data-integrity theme). **Open/carried to Phase 18:** D7→R1, D9→R2, D10→18-G (broad brief sweep). **Watch (no trigger):** D5 (suite runtime — now 8132 tests, de-flaked), D8 (anchor ladder), D12 (latest-eval guard).

## 5. Harness probe (2026-06-13 phase-close run)

**All checks within thresholds — zero ATTENTION** (first fully-clean probe). Highlights: CLAUDE.md 50,551 (line-3 3,811); orchestrator-context **95,396** (the Phase-16 P2 archive pass held it under 100K — D11 stays closed); docs corpus 438 files / 256 brief-named (D10 → the 18-G sweep will trim further); comms mailboxes in heavy live use (44/28/17 archived). Note for a future compaction (not now, under threshold): `tool-director-context.md` at 57,385 has grown with this phase's session logging — a line-3-style compaction of the CHARC session log is due around the next phase close.

## 6. Phase-17 theme verdict: consolidation paid compounding dividends

The phase existed to pay down drift-class debt. It did — and every careful look flushed a latent *production* defect that was sitting invisible: 17-A's CLI IntegrityError crash, D13's lease-revoke swallow, D14's `-n auto` 500-flake (and the class behind it). Three real defects surfaced by consolidation, none by a user report. That is the concrete case for the register-driven paydown posture.

## 7. Close-out + Phase 18 readiness

- **The orchestrator's close-out ritual** (CLAUDE.md line-3 re-compaction if needed — currently healthy at 3,811; a Phase-17→18 handoff doc) is the orchestrator lane, not this audit. CHARC clears the engineering side.
- **Phase 18 is already scoped + operator-approved** (`docs/phase18-todo.md`, data-collection integrity; 6 arcs + 18-G + 18-H catch-all + riders). The §2.3 "next-phase proposal" deliverable is COMPLETE. CHARC owes the architecture passes for 18-B/18-C/18-E/18-F at their commissioning.
- **Phase 17 → CLOSED** pending the operator's call; **Phase 18 → ready to open** on operator go (no commission until then).
