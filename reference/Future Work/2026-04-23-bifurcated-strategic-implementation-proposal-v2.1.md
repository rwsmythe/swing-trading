# Bifurcated Strategic Implementation Proposal for the Swing Trading Tool — V2.1

**Date:** 2026-04-23  
**Supersedes:**
- `2026-04-22-bifurcated-strategic-implementation-proposal.md`
- `2026-04-23-bifurcated-strategic-implementation-proposal-revised.md`
- `2026-04-23-bifurcated-strategic-implementation-proposal-v2-addendum.md`

**Audience:** Future Claude Code / Codex implementation sessions and the developer  
**Status:** Governing strategy document for near-term implementation  
**Companion:** `2026-04-23-rebuttal-response-for-implementors.md`

---

## How to use this document

This document is intended to be the primary strategy artifact for future implementation sessions.

Read in this order:

1. this document;
2. `CLAUDE.md` for current repo state and invariants;
3. current repo docs directly relevant to the active task;
4. the companion rebuttal-response file if simplification or clarification is needed.

Do **not** start from older proposal versions unless a historical comparison is necessary.

---

## Executive summary

The project should continue as **two deliberately different branches built on a limited shared foundation**:

1. **Research and Verification Branch** — used to define, test, falsify, and justify methodological changes.
2. **Operational Trader-Facing Branch** — used to improve real daily decision quality, execution discipline, interpretability, and workflow.

This separation remains necessary because the branches answer different questions:

- Research asks: **Is this method real, robust, and promotable?**
- Operations asks: **What should I do today, and why?**

The key correction in this V2 proposal is that the shared foundation is now intentionally **minimum viable**, not platform-maximal. The project should not spend its next phase building generalized governance before producing one concrete research result and one clearer production improvement.

---

## I. Current state and planning assumptions

Unless contradicted by the repo during the implementation session, downstream agents should assume:

- the repo is active on `main`;
- the operational branch is materially more mature than the research branch;
- Phase 3d has shipped;
- the fast test suite is green on `main`;
- the Phase 3e backlog already exists;
- SQLite must remain outside the Drive-synced folder;
- the repo already contains enough structure that operational work should extend existing patterns rather than replacing them wholesale.

**Planning implication:** the immediate asymmetry matters. The near-term strategic task is **not** to redesign the operational tool from scratch. It is to stand up a lean research capability and a disciplined, lightweight path for moving validated methods into the production tool.

---

## II. Strategic rationale

The project sits at the intersection of two legitimate but non-identical goals:

- building a better trading product for actual daily use;
- building a better research process for methodological improvement.

A single runtime can support both only up to a point. After that point, the design incentives diverge:

| Dimension | Research branch | Operational branch |
|---|---|---|
| Primary question | Is the method defensible? | What should the trader do now? |
| Latency tolerance | High | Low |
| Data requirements | Point-in-time aware, reproducible, falsification-oriented | Timely, stable, operationally convenient |
| Acceptance threshold | Robustness and interpretability | Decision quality and usability |
| Main failure mode | False inference | Trader confusion or workflow drag |

The wrong move is to force one branch to fully inherit the other branch’s constraints.

**Governing sentence:**

> Do not make the production tool carry the full burden of research correctness, and do not make the research environment inherit the speed and simplicity constraints of the production tool.

---

## III. Governing design principles

### 1. Separate research promotion from production deployment

A method does not enter the operator-facing workflow merely because it is attractive, familiar, or interesting in one backtest.

### 2. Share concepts, not full runtimes

The two branches should share:

- naming and vocabulary;
- timing semantics;
- method definitions;
- selected provenance conventions;
- the promotion/rejection decision surface.

They do **not** need to share:

- storage engines;
- vendor stack;
- runtime structure;
- test harnesses;
- optimization targets.

### 3. Default to minimum viable governance

Governance must start small and earn expansion.

If a governance mechanism is not needed to support the active study, the active promotion candidate, or the current production safety boundary, it should be deferred.

### 4. Prefer explicit layer ownership

Every method should declare one primary layer:

- universe
- ranking
- trigger
- sizing
- stop
- exit
- regime
- portfolio
- operator governance
- monitoring

### 5. Promote only methods with explicit marginal value

A method is not “better” in the abstract. It is only better relative to a named baseline, a named problem, or a named gap.

### 6. Preserve operator explainability

A method that cannot be explained clearly to the trader should not drive operator-facing recommendations, even if it remains valuable as research.

### 7. Calibrate scope to time-budget reality

This project is developed part-time by a single developer with significant competing commitments. Sustained developer attention should be assumed at **4–8 hours per week averaged over a year**, split roughly 70/30 production/research during near-term work.

Implications:

- Methods requiring more than a calendar month of evening work to validate should be questioned — they are likely either over-specified or better deferred.
- Registry discipline is leverage when time is short, not overhead. The minimum-viable posture (V2 §IV, §IX) is correct partly for this reason.
- A month with zero research progress is not a failure signal. A quarter with zero progress is.

---

## IV. Minimum viable shared foundation

This section is deliberately narrower than the prior revision.

### A. Canonical timing semantics

Both branches must share the same timing model.

The canonical model is the repo’s two-date discipline:

- `data_asof_date`
- `action_session_date`

Research work that collapses these into a single date invites subtle look-ahead errors. This timing discipline is non-negotiable.

### B. Canonical method record

Instead of a full platform-like registry at the outset, the project begins with a **minimum viable method record**.

Recommended v1 fields:

- `key` — stable identifier
- `name`
- `layer`
- `status`
- `definition`
- `inputs`
- `parameters`
- `outputs`
- `baseline_or_predecessor`
- `validation_notes`
- `operator_explainability`

Recommended status values:

- `backlog`
- `specified`
- `prototype`
- `validated`
- `production`
- `production_unvalidated`
- `deprecated`
- `retired`
- `rejected`

Implementation guidance:

- start with one human-editable format;
- prefer simplicity over schema completeness;
- do not generate auxiliary tooling until multiple method records actually exist.

### C. Minimum provenance requirements

Every research run should stamp at least:

- git SHA or equivalent code version;
- config identifier or snapshot;
- data source/vendor;
- run timestamp;
- universe definition or snapshot identifier where relevant.

This is enough for early reproducibility. More elaborate experiment tracking is deferred.

### D. Promotion boundary

No method may drive primary operator recommendations unless its status is explicitly production-capable.

A method studied in research may enter the operational branch in one of two ways:

- **shadow/challenger mode** — visible but non-primary;
- **production** — primary operator-facing logic.

The boundary should be explicit in code and in the method record.

---

## V. Branch A — Research and Verification

### Mission

Create a lean but credible environment where candidate methods can be defined, tested, rejected, or prepared for operational adoption.

### A. Near-term objective

Produce **one complete, decision-grade study** before building generalized research infrastructure.

This is the most important correction in V2.

### B. Phase 0 rule

**Only build research infrastructure that the first chosen study requires.**

If a component is not needed by the active study, defer it.

### C. Initial research priorities

Default priority order:

1. establish where research artifacts live;
2. create the minimum viable method record mechanism;
3. choose one ranking-oriented study;
4. build only the data harness that study needs;
5. produce an evidence summary and decision;
6. only then broaden infrastructure.

### D. Candidate first studies

Prefer narrow, deterministic, operator-relevant studies.

Good first candidates:

- compare current ranking baseline vs one stable RS formulation;
- compare current ranking baseline vs 12-1 or multi-horizon ensemble ranking;
- validate a simple earnings-proximity exclusion rule;
- test one risk-budgeting or exposure-throttle refinement that maps cleanly to operator decisions.

Avoid as first studies:

- VCP generalization platform;
- cup-with-handle engine;
- generalized pattern segmentation framework;
- broad factor zoo ingestion;
- broad research platform work with no active study.

### E. Data strategy

Use a **bootstrap-first** approach, but with explicit limits.

#### Allowed bootstrap posture

The research branch may begin with free data and limited bootstrap support if the active study can tolerate it.

#### Constraint

A manually maintained delistings bridge is temporary only. It must be:

- explicitly time-boxed;
- attached to a specific study need;
- revisited before expanding into broader point-in-time claims.

If the active study genuinely depends on trustworthy survivorship handling, a paid-data decision should be considered rather than indefinite manual maintenance.

### F. Research evidence standard

Early studies do not need institutional-grade formalism, but they do need disciplined comparisons.

At minimum, a promotable study should include:

- named baseline;
- explicit hypothesis or question;
- parameter choices recorded;
- sensitivity check where parameters matter;
- clear result summary;
- decision: reject, defer, shadow, or prepare for promotion.

---

## VI. Branch B — Operational Trader-Facing

### Mission

Improve the trader’s actual daily decisions, clarity, and workflow without forcing the live tool to become a research platform.

### A. Governing rule

Operational work should extend the current repo’s real shape and backlog, not replace it with an abstract ideal architecture.

### B. Near-term operational priority stack

The workstreams are **ordered**, not coequal.

#### B1. Candidate ranking and focus management

Highest near-term value.

Goals:

- clearer ranking logic;
- stable focus ordering;
- explicit near-miss and rationale surfaces;
- better focus management for daily review.

#### B2. Trigger and setup explanation

Goals:

- exact actionable level;
- stop basis;
- distance-to-trigger and distance-to-stop;
- short narrative explanation;
- quality flags.

#### B3. Risk and trade-construction support

Goals:

- risk-budget-aware share suggestions;
- exposure caps or warnings;
- earnings proximity warnings;
- gap-risk warnings;
- better stop-adjustment guidance.

#### B4. Journaling and decision audit

Build this early enough that future research can learn from it.

Goals:

- log what the system recommended;
- log what the operator did;
- capture deviations and rationale;
- preserve enough structure for later study.

#### B5. Regime and exposure dashboarding

Useful, but after the first four.

#### B6. Workflow and UX polish

Only after decision quality surfaces are improved.

#### B7. Error and degradation UX

Continue where necessary, but do not let this consume the entire roadmap unless an actual reliability issue demands it.

#### B8. Override and offboarding UX

Important, but later than ranking, trigger clarity, risk support, and decision logging.

### C. Operational adoption rules

A method should only become production-driving if it is:

- explainable;
- auditable after the fact;
- not excessively parameter-sensitive;
- compatible with the existing daily workflow;
- net-positive for decision quality.

Methods that are interesting but too fuzzy, too fragile, or too data-hungry remain research-only.

---

## VII. Interaction model between the branches

The branches interact through a **lightweight promotion pipeline**, not a heavyweight governance bureaucracy.

### A. Minimum promotion package

A method prepared for operational consideration should have:

1. a method record;
2. an implementation or implementation sketch;
3. an evidence summary;
4. operator-facing explanation text;
5. a clear decision recommendation.

This is enough for early project stages.

### B. Parity standard

Replace the prior “identical output” wording with the following standard:

> A promoted method must produce identical results on canonical fixtures and equivalent results within defined tolerances on live or vendor-backed data.

This is the correct practical standard for cross-environment promotion.

### C. Shadow mode

When a research result looks promising but not fully proven for operator-facing primary use, deploy it in shadow mode first.

Shadow mode should be preferred over premature full promotion.

### D. Rejection is a first-class outcome

A study that cleanly rejects a candidate method is a success, not a failure. The research branch exists to reduce false enthusiasm as much as to discover improvements.

### E. Demotion pathway

Demotion is symmetric to promotion and reuses the existing lifecycle states (V2 §IV.B). Three pathways:

- **Demotion to shadow** — a production method whose challenger outperforms in shadow mode for a defined evaluation window (default: ≥6 months and ≥30 trade signals) has its primary/shadow flag flipped. The challenger becomes primary; the incumbent continues running in shadow.
- **Deprecation** — a production method with a validated superior replacement is marked `deprecated` for a transition window (default 30 days), then `retired`.
- **Emergency demotion** — a production method that produces a defined-severity operational failure may have its primary/shadow flag flipped to shadow by direct action, with the method record updated in the same commit and a research-branch review queued.

### F. Source-of-truth corrections

When a primary source (a book, paper, or definitive publication) is acquired that corrects or refines a method currently implemented based on an approximation, the correction is handled as a standard research-to-promotion cycle, not as a hotfix:

1. The correction is filed as a new method-record version.
2. The corrected method enters research-branch validation against the same evidence standard as any new method (V2 §V.F).
3. If validated, it enters shadow mode in production alongside the approximation.
4. If shadow evidence supports the correction, the approximation is deprecated via the standard demotion pathway.

Source-of-truth corrections often turn out on investigation to be (a) misremembered, (b) ambiguously specified in the source, or (c) context-dependent in a way the approximation accidentally captures. Treating them as hotfixes imports that uncertainty directly into production.

---

## VIII. What is deferred in V2

The following items are intentionally deferred unless the active work specifically requires them:

- full signal-registry platform features;
- generated code from the registry schema;
- transition-window automation;
- pre-commit enforcement of registry transitions;
- generalized experiment framework;
- broad evidence-tier bureaucracy;
- broad vendor-equivalence frameworks;
- generalized panel-data architecture without an immediate study behind it.

These may become useful later. They are not the next move by default.

---

## IX. Minimum viable governance

This section replaces the heavier governance stance from the prior revision.

The project currently needs only:

1. one primary strategy document;
2. one method-record mechanism;
3. one promotion/rejection note format;
4. one provenance convention for research runs;
5. one explicit boundary between shadow and production logic.

If future sessions cannot justify governance beyond these five items using concrete repo needs, they should defer it.

---

## X. Initial implementation roadmap

### Session tranche 1

Goal: make the strategy executable without overbuilding.

Deliverables:

- adopt this document as strategy baseline;
- add a lightweight method-record location and format to the repo;
- document one chosen research question;
- add a small Phase 0 / Branch A task list to the repo.

### Session tranche 2

Goal: complete one decision-grade study.

Deliverables:

- runnable study harness for one chosen question;
- evidence summary artifact;
- reject/defer/shadow/promote recommendation;
- only the infrastructure that study needed.

### Session tranche 3

Goal: improve the operational branch along the highest-value existing path.

Deliverables should come from the actual repo backlog and should prioritize:

- ranking/focus improvements;
- trigger explanation;
- risk construction support;
- journaling/decision audit capture.

---

## XI. Success criteria for this strategy revision

This V2 proposal is successful if future sessions:

- stand up a research branch without stalling on infrastructure;
- avoid overbuilding governance;
- produce one concrete research result quickly;
- preserve the operational branch’s momentum;
- create a credible but lightweight path for future promotions.

This V2 proposal has failed if future sessions spend multiple rounds implementing strategy machinery without producing one usable study result or one clearer production improvement.

---

## V2 → V2.1 changelog

- Added §III principle 7 (time-budget anchor) from addendum Addition 3.
- Added §VII.E (demotion pathway) from addendum Addition 1.
- Added §VII.F (source-of-truth correction protocol) from addendum Addition 2.
- No other semantic changes. Existing §III principles 1–6 and §VII.A–D preserved verbatim.
- First concrete source-of-truth correction artifact: `reference/methodology/minervini-trend-template.md` (Trend Template criteria 1–8 as printed on p. 79 of *Trade Like a Stock Market Wizard*, transcribed 2026-04-23).

---

## XII. Final instruction to future implementors

When in doubt:

- prefer smaller over more abstract;
- prefer one completed study over an unfinished framework;
- prefer one clear operational improvement over broad speculative redesign;
- preserve timing discipline and provenance;
- defer governance that has not yet earned its cost.

The project does not need a perfect institutional research platform right now. It needs a lean research capability and a disciplined way to improve the live tool without confusing the trader or freezing the roadmap.
