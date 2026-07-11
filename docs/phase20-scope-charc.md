# Phase 20 — Reconciliation Integrity & Correction Paths (CHARC scope)

**Status:** OPERATOR-APPROVED 2026-07-11 (scope in-chat; RD consulted at the operator's direction — thread `phase20-scoping`, answered with additions folded below, NO objections; **operator timing: the phase COMPLETES over the weekend, pre-Monday-open**). **Author:** CHARC (§2.3). **Baseline:** main `652cfc82`; schema **v31** (no change expected); suite 9033/5/0; Phase 19 closed clean 2026-07-07.

## Theme

Harden the **trading-ledger measurement chain** — the mirror of Phase 19's research-chain hardening. Origin: the 2026-07-10 operator-driven forensic reconciliation ([`broker-ledger-forensic-reconciliation-2026-07-10.md`](broker-ledger-forensic-reconciliation-2026-07-10.md)) decomposed a $10.94 equity_delta to the cent and pinned **D25**: the tier-1 auto-corrector has corrupted 3 fill rows (wrong-leg matching on same-qty pairs), one H1 cohort outcome is materially wrong, and a phantom test trade sits in the journal. The equity_delta instrument caught it within 24h; both directors nearly dismissed it — the phase exists because the operator decomposed instead.

## Arcs

| Arc | Scope | Tripwire | Gates | Size | Sequence |
|---|---|---|---|---|---|
| **20-A** D25: fix the corrector, then the data | **Half A (corrector):** same-qty multi-candidate = ambiguity → tier-2, never tier-1; side/date-proximity/%-band plausibility guards; re-correction alarm; fills↔trades consistency invariant. **Half B (data):** the 3 fill corrections via the audited override path; **SATL trade-11 VOID (RD semantic: excluded from ALL cohorts/stats, preserved audit-visible — NEVER raw-delete; tuition restates 16→15)**; post-verify = badge self-clears (~$0.17) + **the RD-WITNESSED H1 ledger re-derivation** (epoch standard-cohort realized recomputed from corrected fills, Σ reconciled to the broker to the cent). **BINDING ORDER (RD, verified at plan review): Half A merges BEFORE or atomically with Half B — never data-first** (the #33→#34 re-corruption precedent) | `swing/trades` carve-out (classifier + auto-correct service) → CHARC §3 pass EMBEDDED in the brief. **Schema-STOP clause:** no 'voided' in the trade-state CHECK enum — the void mechanism must be no-schema, or a CHECK widening routes back to CHARC | RD plan-stage (SATL void mechanics + the ordering constraint) + RD merge-blocking + the RD-witnessed verification + operator witness (live corrections + badge death) | small-med | **FIRST — completes this weekend** |
| **20-B** D22: gate the general `discrepancy resolve` | Pending-state gate: FK-orphans pass; legitimate tier-2 pending rows require the choice-menu flow or explicit `--force` | cli + possible `swing/trades` carve-out → §3 pass in-brief | RD light; operator CLI witness | small | after 20-A (same module family) |
| **20-C** D23+D24: the coherence-UX cluster | Untracked-position resolve page surfaces the durable OOF-declare path; equity_delta gets a diagnostic breakdown (ledger vs NLV vs OOF → the record-cash action). Principle (RD-ENDORSED): coherence findings route to the DATA FIX, not the acknowledge | none (web-only) | operator GUI witness (HTMX family) | small | parallelizable with 20-A (file-disjoint) |
| **Riders** | R1 `comms_unread_hook` bare-import hardening · **R2 AGENTS.md THIN-POINTER conversion (operator-resolved 2026-07-11**; verify repo-access reviews follow the pointer) · R3 dead-gen registry tidy | — | — | tiny | lulls |

## Deferred (no forcing function — revisit at the Phase-20 close)

S4U/explicit-data-root (Interactive-only proven) · D15 base-VM consolidation · D5 suite runtime (acts at the 5-min line; 4:46 now). RD-lane watch items (his ledger): the floor-ratio 0.15–0.2 band; the shadow-twin divergence note (**SURVIVES the AMN correction** — RD's read predated the corruption; stays watch at n=1).

## Binding constraints + external checkpoints

- **Ordering (RD):** 20-A Half A before/atomic-with Half B.
- **Deadlines:** phase completes pre-Monday-open (operator); 20-A's corrected values land before RD's August monthly read (it consumes them).
- Zero schema expected phase-wide (v31); the 20-A void design carries the explicit schema-STOP.
- RD is available over the weekend for his three 20-A gates.
