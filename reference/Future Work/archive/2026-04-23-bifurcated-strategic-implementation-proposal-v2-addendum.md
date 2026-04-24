# V2 Proposal — Targeted Additions Addendum

**Date:** 2026-04-23
**Companion to:** `2026-04-23-bifurcated-strategic-implementation-proposal-v2.md` and `2026-04-23-rebuttal-response-for-implementors.md`
**Status:** Optional addendum. Each item is independent; adopt or reject piecewise.
**Audience:** Future Claude Code / Codex implementation sessions and the developer

---

## Purpose

V2 is a sound simplification of the prior revised proposal and is correctly the new strategic source of truth. This addendum proposes three targeted additions to V2 — items dropped or omitted in the simplification that carry concrete operational value beyond their governance cost.

Each item is presented independently. None are required for V2 to be coherent; each is a separate small adoption decision. Per V2 §IX, if an item cannot justify its own cost against a concrete repo or workflow need, defer it.

The additions intentionally respect V2's minimum-viable posture. None reintroduce platform-like infrastructure. Each is small, scoped, and addresses a specific failure mode the V2 simplification did not preserve.

---

## Addition 1 — Demotion pathway

**Where it goes:** V2 §VII (interaction model), as a new subsection after §VII.D.

**What to add:**

> ### E. Demotion pathway
>
> Demotion is symmetric to promotion and reuses the existing lifecycle states (V2 §IV.B). Three pathways:
>
> - **Demotion to shadow** — a production method whose challenger outperforms in shadow mode for a defined evaluation window (default: ≥6 months and ≥30 trade signals) has its primary/shadow flag flipped. The challenger becomes primary; the incumbent continues running in shadow.
> - **Deprecation** — a production method with a validated superior replacement is marked `deprecated` for a transition window (default 30 days), then `retired`.
> - **Emergency demotion** — a production method that produces a defined-severity operational failure may have its primary/shadow flag flipped to shadow by direct action, with the method record updated in the same commit and a research-branch review queued.

**Why:** V2 §VII.D treats rejection as a first-class outcome, but rejection is the disposition of a *candidate*. It does not cover demoting an *incumbent*. In practice, the incumbent's failure mode (drift, regime change, post-promotion degradation) is the more frequent event. Without a stated pathway, the first time this case arises the response will be ad hoc.

**Cost:** ~50 words in V2. No new infrastructure. Reuses existing lifecycle states and the shadow-mode primary/shadow distinction already in V2 §VII.C.

---

## Addition 2 — Source-of-truth correction protocol

**Where it goes:** V2 §VII, as a new subsection after Addition 1 (or in §VII.E if Addition 1 is rejected).

**What to add:**

> ### F. Source-of-truth corrections
>
> When a primary source (a book, paper, or definitive publication) is acquired that corrects or refines a method currently implemented based on an approximation, the correction is handled as a standard research-to-promotion cycle, not as a hotfix:
>
> 1. The correction is filed as a new method-record version.
> 2. The corrected method enters research-branch validation against the same evidence standard as any new method (V2 §V.F).
> 3. If validated, it enters shadow mode in production alongside the approximation.
> 4. If shadow evidence supports the correction, the approximation is deprecated via the standard demotion pathway.
>
> Source-of-truth corrections often turn out on investigation to be (a) misremembered, (b) ambiguously specified in the source, or (c) context-dependent in a way the approximation accidentally captures. Treating them as hotfixes imports that uncertainty directly into production.

**Why:** A specific case is foreseeable — the Minervini book arrives and the RS rank approximation currently in production is found to be slightly different from the canonical formulation. The natural impulse is to patch production directly. That impulse skips the validation step that catches misremembering and ambiguity. The protocol exists to channel the impulse, not to add ceremony.

**Cost:** ~80 words in V2. Reuses existing lifecycle and demotion machinery; no new infrastructure.

---

## Addition 3 — Time-budget anchor

**Where it goes:** V2 §III (governing design principles), as principle 7.

**What to add:**

> ### 7. Calibrate scope to time-budget reality
>
> This project is developed part-time by a single developer with significant competing commitments. Sustained developer attention should be assumed at **4–8 hours per week averaged over a year**, split roughly 70/30 production/research during near-term work.
>
> Implications:
>
> - Methods requiring more than a calendar month of evening work to validate should be questioned — they are likely either over-specified or better deferred.
> - Registry discipline is leverage when time is short, not overhead. The minimum-viable posture (V2 §IV, §IX) is correct partly for this reason.
> - A month with zero research progress is not a failure signal. A quarter with zero progress is.

**Why:** V2's minimum-viable stance implicitly assumes scarce developer time but does not name the constraint. Naming the constraint is what tells a future agent (or a future review cycle) *why* the minimum-viable posture is correct, not just *that* it is. Without the anchor, a subsequent critique cycle can re-inflate the proposal without anyone remembering why it was deliberately small. The anchor is the audit trail for V2's own simplification.

**Cost:** ~100 words in V2. No infrastructure. Pure framing.

---

## Adoption guidance

Each addition is independent. If all three are adopted, a natural sequence:

1. **Time-budget anchor** — no infrastructure; frames every subsequent scoping decision.
2. **Demotion pathway** — needed before the first method enters production formally.
3. **Source-of-truth correction protocol** — needed before the first primary source arrives that corrects an existing method.

If only one is adopted, the time-budget anchor (Addition 3) carries the most leverage — it informs every other scoping decision and protects V2's simplification from drift.

If none are adopted, V2 stands and these become reference material in case the failure modes they address materialize later.

---

## On Decision 3 of the rebuttal-response

The meta-stance in Decision 3 ("treat the current rebuttal as a revision aid, not as standing doctrine") is correct and should be preserved. REBUTTAL was input to producing the prior revised proposal; it is not the implementation contract for V2 or for any downstream session.

The note: a handful of REBUTTAL findings carry content that retains operational value independent of REBUTTAL's status as a revision aid. Examples:

- **Finding 2.10** — production provenance acknowledgment (`config_revisions`, `pipeline_runs.rs_universe_version`, `trade_events`). This is repo-factual content that should inform any session touching the production provenance schema, regardless of how REBUTTAL is otherwise treated. This addendum does not address it because V2 already preserves the provenance discipline implicitly via §IV.C, but a future session designing new audit fields would benefit from reading the finding directly.
- **Findings 3.6, 3.7, 3.9** — demotion pathway, time-budget reality, source-of-truth corrections. Operational-reality content that this addendum incorporates as Additions 1, 3, and 2 respectively.

Future sessions should not dismiss these findings on Decision-3 grounds. The correct posture: evaluate each REBUTTAL finding on its merits when the question it addresses arises in the active work. This addendum is one such evaluation; others may be warranted later.

Decision 3 is about not treating REBUTTAL as a contract. It is not a license to ignore content the document happens to carry.
