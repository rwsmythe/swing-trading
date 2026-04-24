# Rebuttal Response and Clarifying Decisions for Future Implementor Sessions

**Date:** 2026-04-23  
**Audience:** Future Claude Code / Codex implementation sessions and the developer  
**Status:** Binding clarification document for strategy-to-implementation handoff  
**Companion:** `2026-04-23-bifurcated-strategic-implementation-proposal-v2.md`

---

## Purpose

This document responds to the latest review feedback on the rebuttal and revised bifurcated proposal. Its role is narrow:

1. preserve the sound parts of the current strategic framing;
2. explicitly correct the weaknesses identified in review;
3. collapse ambiguity before downstream implementation sessions begin; and
4. keep future agents from overbuilding governance or infrastructure before the first research deliverables exist.

This is **not** a new critique and **not** a new proposal. It is a decision memo that tells downstream implementors what to keep, what to soften, what to defer, and what language should govern implementation choices.

---

## Current baseline assumptions

Downstream agents should treat the following as current baseline context unless the repo proves otherwise during the implementation session:

- The repo already exists and is active on `main`.
- `CLAUDE.md` is the primary current-state repo context file.
- The operational branch is materially ahead of the research branch.
- Phase 3d has shipped.
- The fast test suite is green on `main`.
- A concrete Phase 3e backlog already exists.
- SQLite must remain **outside** the Drive-synced folder.
- The project already has meaningful operational complexity and should not be treated as greenfield.

Any downstream session that finds repo drift should update these assumptions in the same commit as the work that depends on them.

---

## Top-level decisions

### Decision 1 — Keep the bifurcated architecture

The bifurcated architecture remains the correct strategic frame.

Keep the distinction between:

- **Research and Verification Branch**
- **Operational Trader-Facing Branch**

Do **not** collapse them into one runtime or one workflow.

### Decision 2 — Reduce process weight sharply in the first implementation tranche

The prior revised proposal was directionally right but still too heavy in governance and infrastructure for a solo, part-time project.

Future implementors must assume:

- early research throughput is more important than complete process machinery;
- the registry is valuable, but only in a minimum viable form at first;
- infrastructure is justified only when the first concrete study or production improvement needs it;
- unneeded governance is project drag, not rigor.

### Decision 3 — Treat the current rebuttal as a revision aid, not as standing doctrine

The existing rebuttal document is useful, but future agents should **not** treat it as the primary governing strategy artifact.

Use it to understand why the proposal changed. Do not use it as the implementation contract.

### Decision 4 — Make the next proposal revision the new strategic source of truth

The new proposal revision should become the only strategy document that downstream implementation sessions are expected to follow directly.

Older proposal and rebuttal files remain reference material.

---

## Accepted corrections from the latest review

The following review findings are accepted and should be treated as resolved requirements.

### 1. Minimum viable governance is required

The prior proposal specified too much upfront governance.

**Binding correction:** implementation begins with **minimum viable governance**, not full governance.

Minimum viable governance means:

- one lightweight method registry format;
- one clear lifecycle label set;
- one decision log for promotions/rejections;
- one provenance stamp pattern for research runs;
- no pre-commit enforcement until the registry is actually used by multiple methods.

### 2. “Identical output” parity language is too strong

Exact identity across research and operational environments is unrealistic once data vendors, timestamps, and normalization differ.

**Binding correction:** replace “identical output” with a two-part standard:

- **fixture identity** on canonical synthetic fixtures and frozen reference inputs;
- **toleranced equivalence** on live or vendor-backed data.

This is the standard future sessions should implement.

### 3. Research infrastructure must be built only as needed

The prior proposal still risked turning Branch A into an infrastructure project before the first real study shipped.

**Binding correction:** no research infrastructure may be introduced unless it is required by the currently selected study, the current data problem, or the current promotion handoff.

Future agents should default to the smallest implementation that can answer the active research question.

### 4. Manual delistings support must be time-boxed

A manual delistings list is acceptable only as a temporary bootstrap aid.

**Binding correction:** manual delistings support may be used only under an explicit timebox and must not become an indefinitely maintained pseudo-vendor.

If point-in-time survivorship handling becomes central to the selected study, the project should re-evaluate paid data rather than endlessly extending manual maintenance.

### 5. The proposal needs an explicit near-term priority stack

The operational workstreams were too broad and too coequal.

**Binding correction:** future sessions should treat near-term priorities as ordered, not flat.

Default near-term priority order:

1. stand up minimum viable research branch scaffolding;
2. validate one ranking study end-to-end;
3. ship the highest-value operational backlog items already known in the repo;
4. only then broaden governance or add additional research workstreams.

### 6. The registry must start small

The registry idea is worth keeping, but the first version was too platform-like.

**Binding correction:** the v1 registry is intentionally sparse.

Required initial fields only:

- `key`
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

Everything else is deferred until real usage justifies it.

---

## Clarifications for future implementors

### A. What must not be overbuilt in the next session

Do **not** start by building all of the following unless the chosen task explicitly requires them:

- generated dataclass mirrors for the full registry schema;
- pre-commit hooks for registry transitions;
- a full promotion package system;
- a generalized experiment platform;
- a broad DuckDB/Parquet abstraction layer with no immediate study behind it;
- a full evidence-tier bureaucracy;
- a broad branch-interaction framework before one method is ready to move between branches.

### B. What should be built first instead

Prefer the following sequence:

1. define the first research question;
2. define the minimum data and artifact needs for that question;
3. create the smallest shared method record needed to describe it;
4. produce one study result that could plausibly be promoted or rejected;
5. only then generalize.

### C. What counts as a valid first research question

A valid first study should be:

- narrow;
- deterministic;
- already close to the operational tool’s worldview;
- explainable to the trader;
- cheap enough to complete without a platform build-out.

Good examples:

- compare one stable RS formulation against the current ranking baseline;
- compare a 12-1 ranking baseline against a 3/6/9/12 ensemble on the project’s candidate universe;
- test a simple earnings-proximity exclusion rule;
- validate one operator-facing ranking rationale field against actual recommendation quality.

Bad first examples:

- full VCP research platform;
- generalized chart-pattern segmentation engine;
- institutional-grade portfolio optimizer;
- broad factor-library ingestion.

### D. How to treat fuzzy methods

Pattern-heavy methods such as VCP, cup-with-handle, and cycle-of-price-action states are still valid research topics, but they are **not** required to justify the bifurcated architecture.

Do not make Branch A wait on them.

Treat them as later-stage candidate methods that require clearer segmentation, richer fixtures, and likely more expensive validation.

### E. How to treat production parity

If a method is studied in a panel-data research environment and later promoted into the live operational tool, the production rewrite should preserve:

- formula intent;
- timing semantics;
- input field meaning;
- operator explanation;
- toleranced numerical behavior.

It does **not** need to preserve identical internal representation or runtime architecture.

---

## Binding wording changes for downstream documents

Future agents should use the following wording conventions.

### Replace this

> identical output across research and production

### With this

> identical results on canonical fixtures and equivalent results within defined tolerances on live or vendor-backed data

### Replace this

> full shared foundation before branch work begins

### With this

> minimum viable shared foundation sufficient to support the first selected study and the first plausible promotion handoff

### Replace this

> implement the signal registry

### With this

> implement the minimum viable method registry needed for the active study and current production handoff needs

### Replace this

> bootstrap with manual delistings support

### With this

> use a time-boxed manual delistings bridge only if the active study requires it and only until the data question justifies a paid-data decision

---

## Operational priority guidance

Until explicitly superseded by a newer strategy document, downstream agents should assume the operational branch should continue to prioritize improvements that directly improve decision quality and create future learning data.

Recommended near-term operational ordering:

1. **Candidate ranking and focus management**
2. **Trigger and setup explanation**
3. **Risk and trade-construction support**
4. **Journaling and decision-audit capture**
5. Regime dashboarding
6. Workflow and UX polish
7. Error/degradation UX expansion
8. Override/offboarding UX refinement

Rationale: the first four improve the quality of the operator’s actual decisions while also creating structured observations that later research work can use.

---

## Research priority guidance

Until explicitly superseded, downstream agents should assume the research branch should begin with one tractable study and one tractable promotion path.

Recommended initial ordering:

1. establish research repo location, artifact location, and provenance stamping;
2. create minimum viable method registry;
3. choose one ranking-related study;
4. build only the data ingestion and validation harness that study needs;
5. produce study output, rejection or promotion recommendation, and next-step note;
6. only then consider wider research platform work.

---

## What success looks like after the next two implementation sessions

A successful near-term implementation sequence should result in something like this:

### After first strategy-following session

- one new strategy document adopted as source of truth;
- one small registry or method-card mechanism present in the repo;
- one chosen research question documented;
- one concrete Phase 0 or Phase A1 task list added to the repo.

### After second strategy-following session

- one research study runnable end-to-end;
- one evidence summary artifact produced;
- one explicit decision: reject, defer, or prepare for shadow-mode promotion;
- no generalized governance machinery beyond what that work actually needed.

---

## Anti-patterns to avoid

Future implementors should avoid these failure modes:

1. **Strategy inflation** — turning every good idea into required architecture.
2. **Registry maximalism** — building a platform-like method catalog before a few methods exist.
3. **Infrastructure displacement** — spending multiple sessions on frameworks before answering one research question.
4. **Parity absolutism** — requiring exact numeric equality across unlike data contexts.
5. **Bootstrap drift** — turning temporary manual data maintenance into permanent hidden cost.
6. **Priority flattening** — treating all workstreams as equally near-term.
7. **Document worship** — optimizing strategy prose instead of making the repo more capable.

---

## Instruction to future implementor sessions

When using the companion proposal v2, treat this document as the short correction layer.

- If the proposal seems too heavy, use this document to simplify.
- If the proposal seems too vague, follow the proposal.
- If there is tension between rigor and speed, prefer the smallest move that preserves future correctness.
- If a governance mechanism is not needed for the current study or handoff, defer it.

The strategic objective is no longer to design a perfect governance system. It is to create a research branch and promotion path that are rigorous **enough** to improve the live tool without stalling the project.
