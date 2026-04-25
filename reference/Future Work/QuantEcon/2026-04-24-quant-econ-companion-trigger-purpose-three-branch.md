# QuantEcon Program — Trigger, Purpose, and Three-Branch Companion

**Date:** 2026-04-24
**Companion to:** [`2026-04-24-quant-econ-future-research-program.md`](2026-04-24-quant-econ-future-research-program.md)
**Status:** Forward-looking strategic memo; **starting point for further discussion** with future sessions, not a finished spec.
**Audience:** Future Claude Code / Codex sessions consulted on strategic positioning, plus the developer.

---

## What this captures

A clarifying conversation between the developer and an orchestrator session on 2026-04-24 surfaced two refinements to the QuantEcon program's positioning that are not yet in the QuantEcon doc itself:

1. **Path A vs Path B framing** — and the trigger condition that activates Path B.
2. **Three-branch refinement** to V2.1's bifurcated architecture.

This companion captures both, so future sessions consulting the QuantEcon doc have the context to engage with it productively. It is deliberately short.

---

## Path A vs Path B

The project has two distinct long-run improvement paths:

- **Path A — Practitioner extension.** Add more rule-of-thumb setups (cup-with-handle variants, additional pattern detectors, more advisories), validate via post-hoc trend / fundamental analysis. Discovery and validation are the same kind of work the project has been doing.
- **Path B — Quant-rigor overlay.** Use data-driven methods (factor decomposition, decay detection, Kelly sizing, theoretical anchoring) to optimize / protect / scale a methodology that's already showing edge.

**The QuantEcon program is explicitly Path B.** Path B does not find what works; it scales / protects / optimizes what already works. This is the historical pattern of successful quant integration: discretionary edge first (often by founders with practitioner intuition), formalization and scaling by quants second.

---

## Trigger condition — when Path B activates

**Necessary condition:** the operational system has produced net-positive returns above a relevant market benchmark (e.g., SPY) over a meaningful period.

Without that evidence, Path B is premature. There is nothing to optimize, scale, or protect. The correct response to an unproven operational methodology is to revisit the methodology itself (Path A, methodology revision, or scope reduction) — not to add data-driven rigor on top.

**Two reasonable operationalizations of the trigger that can disagree:**

1. **Raw above-market returns.** Operational P&L beats SPY (or similar benchmark) over a meaningful period. Easy to measure. But can be entirely momentum-factor beta — in which case quant rigor would just be expensive infrastructure for "do what a momentum ETF does."
2. **Post-factor-decomposition alpha.** Returns are above-market AND above-factor-betas after Carhart-Fama-French-AQR-style decomposition. The right gate for Path B in spirit, but circular: factor decomposition is itself a QuantEcon program activity (Theme 3).

**Honest two-stage sequencing implied by this:**

- Raw above-market returns gate the **start of Theme 3** (without that, nothing is worth decomposing).
- Theme 3's alpha confirmation then gates **Themes 1, 2, 4**.

The QuantEcon doc's current single-gate sequencing slightly conflates these. Future sessions should treat the gate as two-stage per this companion.

---

## Theme 3 has a dual role under this framing

Under Path B framing, Theme 3 (factor decomposition / attribution) does double duty:

1. **Prerequisite infrastructure for Theme 1.** Kelly sizing on factor-beta-inflated alpha is dangerous — mathematically grounded constraint already in the QuantEcon doc.
2. **THE diagnostic that determines whether the entire QuantEcon program is the right move.** If post-decomposition alpha is small or absent, the practitioner methodology was approximating a known factor and quant rigor isn't warranted.

So Theme 3 is the load-bearing test of whether Path B is warranted at all, not just a prereq for Theme 1.

---

## Trade-history accumulation = "system proven" trigger (same problem, restated)

The QuantEcon doc names trade-history volume as failure mode FM1 (Theme 3 needs ≥50 closed trades, ≥100 strongly preferred). Under Path B framing, the trade-history constraint and the "system proven" trigger are the same constraint stated differently. You cannot measure "above-market returns" without enough trades to estimate it.

The QuantEcon doc's calendar estimates assume a trade-frequency that may exceed the operator's actual realized rate by ~6–10× (current rate: ~1 closed trade/month at most). The 18–24-month timeline as stated may be 5–7 years in practice. This should be re-examined when (if) Phase R1 begins.

---

## Three-branch refinement to V2.1's architecture

V2.1 specifies a bifurcated architecture: **Operational** and **Research-and-Verification**. A useful refinement, surfaced 2026-04-24, distinguishes two sub-branches within Research:

| Branch | Activity | Per-study/investigation time horizon | Success rate | Effort | Canonical example |
|---|---|---|---|---|---|
| **Operational** | Daily decision-making with promoted methods | Continuous | N/A | Steady | The `swing/` codebase |
| **Applied Research** | Testing rules developed elsewhere (other practitioners, prior project work, academic literature) for promotability | Weeks to a few months per study | Moderate-to-high (testing something already partially validated) | Modest per study | Earnings-proximity-exclusion study (Sessions 2a/b/c) |
| **Basic Research** | Discovering or refining rules at the fundamental level, often from theoretical starting points | Many months to years per investigation | Lower (first-principles exploration often fails) | Substantial; data-hungry | The QuantEcon program (Themes 1–4) |

**Branches are permanent capability, not time-bounded projects.** All three branches are ongoing means for process improvement and are not intended to be spun down or pruned as "mission complete." Individual studies within Applied Research complete in weeks-to-months and the branch may then idle until the next study. Individual investigations within Basic Research complete on years-long timelines and the branch may idle for extended periods between investigations. Idle ≠ failure; idle ≠ dismantle. The branches' **infrastructure** (harness scaffolding, method-record format, cache directories, study templates, provenance manifests) persists across idle periods so the next investigation starts warm rather than from scratch. Steady-state maintenance (yfinance version pinning, universe refresh, cache pruning) applies even to idle branches to prevent bit-rot.

**Promotion path:** Basic Research → Applied Research → Operational. A basic-research investigation that produces a promising candidate hands off to applied research for domain-specific validation, which then promotes to operational shadow / primary per V2.1 §IV.D.

**Implications (sketched, not normative — discussion topics for future sessions):**

- **Governance.** V2.1 §V.F's evidence standard (named baseline, explicit hypothesis, parameter sensitivity, decision) maps cleanly onto applied research. Basic research has fuzzier outputs (exploratory investigations, hypothesis generation, theoretical framings) that may need lighter-weight artifacts than the method-record format.
- **Time budget.** Because branches are permanent but individual studies/investigations have finite scope, research time within the 4–8 hrs/week sustained budget is allocated dynamically rather than steady-split. A typical pattern: 100% applied during a study, then idle, then 100% basic during an investigation, then idle. Sustained dual-allocation (e.g., 1 hr/week applied + 1 hr/week basic concurrently) is possible but not required — solo-developer parallelism has limits, and serial focus on one investigation usually outperforms split attention.
- **Evidence standards.** Applied research aims for a definitive reject/shadow/promote/defer per study. Basic research more often produces "we explored X, learned Y, here's a hypothesis worth applied-testing" — a different kind of output.
- **Interaction with V2.1 governance.** V2.1 currently doesn't preclude this distinction; it's just less granular. Whether to formalize as a V2.1 amendment, a separate V2.2-style strategic doc, or kept as a conceptual lens is deferred until a basic-research investigation actually starts.

---

## Path-not-taken — what happens if the trigger never fires

If the operational system does not produce above-market returns over a meaningful period, the QuantEcon program (Path B) does NOT trigger. The forward path in that case is some combination of:

- Revisit the practitioner methodology (Minervini Trend Template variants, additional source frameworks like O'Neil CANSLIM directly, etc.).
- Reduce project scope / commitment.
- Conclude that swing trading at this scale is not a good fit and pivot to other technical interests.

**The QuantEcon program is not a backup plan for an unproven methodology. It is an upgrade for a proven one.** Future sessions tempted to start QuantEcon work in the absence of operational-performance evidence should treat that temptation as a signal to revisit the methodology itself.

---

## Open discussion topics for future sessions

This companion is a starting point. The following are explicitly open for further discussion:

1. **Should the three-branch refinement become a V2.1 amendment, a separate strategic doc, or stay as conceptual lens for now?** Decision likely deferred until a basic-research investigation actually starts.
2. **What's the right time-budget split between applied and basic research?** With the current 4–8 hrs/week budget, the question is whether basic research is allocated steady time (e.g., 1 hr/week of theoretical reading) or starts at zero until a trigger fires.
3. **How does V2.1 §V.F's evidence standard apply to basic research?** Or does basic research need its own lighter-weight artifact spec — exploration logs, hypothesis registers, reading notes — distinct from the method-record format?
4. **At what point does the trade-history-accumulation rate get formally checked against the QuantEcon doc's calendar assumptions?** The doc currently assumes accumulation rates that may not match reality.
5. **What constitutes "system proven" in operational practice?** Raw above-market returns alone, or post-factor-decomposition alpha (which is itself a Path B activity, creating circularity)? The two-stage gate proposed above is one resolution; other resolutions are possible.
6. **Where does Theme 4 (setup-quality improvement via theoretical anchoring) belong — applied or basic?** It uses theoretical frames (basic-research-flavored) but operates on existing production setups (applied-flavored). Probably hybrid, which itself is worth discussing.

---

## Cross-references

- QuantEcon program (governing): [`./2026-04-24-quant-econ-future-research-program.md`](2026-04-24-quant-econ-future-research-program.md)
- Governing project strategy: [`../2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md)
- Binding clarifications on V2.1: [`../2026-04-23-rebuttal-response-for-implementors.md`](../2026-04-23-rebuttal-response-for-implementors.md)
- Current operational state: `CLAUDE.md` (repo root)
- First applied-research artifact: `research/studies/earnings-proximity-exclusion.md`
