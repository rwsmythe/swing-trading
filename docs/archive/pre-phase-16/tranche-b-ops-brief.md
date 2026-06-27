# Tranche B-ops session 1 — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Run a design session (no code) producing a mini-spec for Operational Branch improvements that absorb Bugs 3a/4/5/6 from `docs/Bugs.txt` plus one newly-flagged stop-form field-preservation issue. Invoke `copowers:brainstorming` — this session is genuine design work with real latitude.
**Expected duration:** One working session, heavy on user interaction during brainstorming.
**Prepared:** 2026-04-23 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, gotchas, Phase isolation rule. Note the template-duplication gotcha recently added (Tranche B-cleanup); relevant because your spec will likely propose new UX.
2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governing strategy. Focus on §VI (Branch B — Operational Trader-Facing) and §VI.B near-term priority stack (B2 trigger/setup explanation, B3 risk/trade-construction, B4 journaling). Also §IX (minimum viable governance).
3. `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — binding clarifications. Focus on §1 (minimum viable governance) and the Anti-patterns list.
4. `docs/Bugs.txt` — user's original bug reports. Your mission covers Bugs 3, 4, 5, 6. Bugs 1 and 2 shipped in Tranche A.
5. `docs/tranche-a-brief.md` and `docs/tranche-b-research-brief.md` — brief format precedent; context on what's been shipped.

**Skill posture.** Invoke `copowers:brainstorming` as your primary workflow skill. It wraps `superpowers:brainstorming` (interactive user dialogue exploring intent/requirements/design) with adversarial Codex review after the spec is drafted. This session's entire structure is that wrapper.

Other superpowers skills (e.g., `test-driven-development`) are not relevant this session — no code is produced. Invoke `superpowers:verification-before-completion` before declaring done.

---

## 1. Context you won't get from the repo alone

Context accumulated in the orchestrator session that produced this brief; repeated here because the implementer instance has no prior conversation history.

### 1.1 What the user reported vs. what the orchestrator reframed

- **Bug 3** was reported as "rationale boxes should be dropdowns with defined statements." Investigation revealed the CLI accepts `--rationale` as **free text** across all trade actions (entry, exit, stop-adjust). No canonical list exists in code. Only `ExitReason` is an enum (`stop-hit` / `target` / `manual` / `time-stop` / `weather` / `partial` / `other`), and that's a separate field.
- Bug 3 was split: **3a (this session)** is the rationale-taxonomy design; **3b (shipped in Tranche A)** added a `notes` field to `StopAdjustRequest` for free-form context.
- Bug 3a is therefore not a "fix CLI parity" task. It's **schema design work** — structured rationale is the raw material for future Branch A5 operator-behavior analytics (V2.1 §V.D candidate "validate one operator-facing ranking rationale field against actual recommendation quality"). Designing the taxonomy now prevents a later free-text→structured migration.

### 1.2 Bugs 4, 5, 6 summary

- **Bug 4:** expanded watchlist entries should show a reason when the chart is unavailable ("not enough data," etc.), rather than silently omitting the chart.
- **Bug 5:** the A+ entry form says "Stop Limit" but only collects/displays a stop value. Either the label is wrong (it's actually a stop-market) or the form is missing a limit-price field.
- **Bug 6:** total risk exposure (sum of open-position initial-risk dollars across the book) is not visible anywhere in the UI.

### 1.3 Stop-form field-preservation — new flag from Tranche A

The stop-adjust form loses user input on `StopRegressionError` re-render. Unlike the entry form (which preserves typed rationale + notes via `TradeEntryFormVM`), the stop form's VM has no field-preservation path. User types rationale + notes, submits, hits a regression error (new stop < current, no force), the 400 re-render clears both fields. Pre-existing behavior; orchestrator's decision was to fold it into this design session since the stop-adjust form is already in scope.

### 1.4 What V2.1 says about operational priority ordering

V2.1 §VI.B near-term priority stack is ordered, not flat:

1. Candidate ranking and focus management
2. Trigger and setup explanation
3. Risk and trade-construction support
4. Journaling and decision-audit capture
5. Regime and exposure dashboarding
6. Workflow and UX polish
7. Error and degradation UX
8. Override and offboarding UX

This session absorbs items that span B2 (Bug 5 — trigger/setup completeness), B3 (Bug 6 — risk display), B4 (Bug 3a — structured rationale as journaling input), and B7 (Bug 4 — chart-unavailable messaging). Do **not** expand scope into items 5, 8, or beyond — those are later sessions. If during brainstorming the user pushes toward regime dashboarding or override UX, record the idea as a non-scope note and continue.

### 1.5 What's already in the repo that you'll reference

- `swing/trades/entry.py`, `swing/trades/stop_adjust.py`, `swing/trades/exit.py` — trade action services. `StopAdjustRequest` now has a `notes` field (Tranche A).
- `swing/cli.py` — CLI entry points; `--rationale` and `--notes` options present.
- `swing/web/templates/partials/trade_entry_form.html.j2`, `trade_stop_form.html.j2`, `trade_exit_form.html.j2` — existing forms.
- `swing/web/view_models/trades.py` — form VMs. `TradeEntryFormVM` preserves field input on error; the stop form VM does not.
- `swing/data/models.py` — data models. `ExitReason` enum lives here.
- `swing/data/migrations/` — migration history. Most recent is `0005` (trade_events notes column, Tranche A).
- `swing/evaluation/` — A+ criteria, bucket rules.
- `swing/trades/advisory.py` — seven advisory rules, pure functions of state.

### 1.6 Posture reminders

- Minimum viable governance (V2.1 §IX). Do not build a general-purpose taxonomy framework. Design one taxonomy per action (entry / stop-adjust / exit) with an `other` escape-hatch. Adding generic pluggable schema infrastructure is registry maximalism.
- Preserve operator explainability (V2.1 §III principle 6). Each rationale dropdown option must be obviously meaningful to an operator on first read.
- The orchestrator's starting hypothesis is **implementer-drafts-taxonomy-first, user-reviews**. Honor that — propose candidate taxonomies derived from existing repo vocabulary (advisory rule names, bucket rules, Minervini trend-template criteria, ExitReason enum), then iterate with the user.

---

## 2. Tranche B-ops session 1 scope

### In scope

Design (not implement) a mini-spec covering:

1. **Rationale taxonomy (Bug 3a)** — three closed-list taxonomies (entry / stop-adjust / exit) with `other`-escape-hatch pattern. Draw options from existing repo vocabulary.
2. **A+ stop-limit field completeness (Bug 5)** — resolve the label/field mismatch. Either rename the label or add the limit field; recommend which based on operator workflow.
3. **Total risk exposure display (Bug 6)** — where and how the dashboard (or status strip) surfaces total-book risk. Must include definition (initial-risk sum? current-risk sum? both?).
4. **Chart-unavailable reason (Bug 4)** — message format and the enumeration of reasons (insufficient data, ticker rotation, fetch error, etc.).
5. **Stop-form field-preservation** — design the VM pattern (mirror `TradeEntryFormVM`, or propose a cleaner generic pattern if one emerges naturally — but beware over-abstraction).
6. **Implementation task list** — decompose the spec into implementer-ready tasks with enough detail to dispatch as subsequent Tranche B-ops session 2+. Commit-level granularity.

### Out of scope

- **Any code changes this session.** No `swing/` files modified. No migrations. No tests.
- Bugs 1 and 2 (shipped Tranche A).
- Bug 3b (shipped Tranche A).
- Research-branch work (Tranche B-research, shipped).
- Regime dashboarding, override/offboarding UX (V2.1 §VI.B items 5, 8).
- Any new ranking logic, advisory rules, or pipeline changes.
- Any enhancement to the structured rationale schema beyond the three per-action taxonomies (no meta-framework, no dynamic-plugin system, no YAML-driven registry).

### Items the user may raise that should be deferred

During brainstorming the user may surface adjacent concerns (new advisory rules, pipeline changes, regime indicators). Record them as non-scope notes in the spec's "Out of scope" section and keep the design session focused. Tranche B-ops session 1 delivers a bounded mini-spec, not a comprehensive operational-branch roadmap.

---

## 3. Workflow

Follow `copowers:brainstorming` as your primary workflow. The skill's internal structure (inherited from `superpowers:brainstorming`) will interact with the user to explore intent, requirements, and design. After the spec is drafted, the skill triggers adversarial Codex review. Respond to review findings, revise, and finalize.

Rough session shape (not rigid):

1. **Orient.** Read §0 references. Load context from §1.
2. **Brainstorm with user.** For each in-scope item (Bugs 3a, 4, 5, 6, field-preservation), explore intent, constraints, options. The orchestrator's posture is "propose candidates derived from existing vocabulary, iterate" — favor concrete options over open-ended discussion.
3. **Draft the spec.** One document at `docs/superpowers/specs/tranche-b-ops-session-1.md` (or another name if the user prefers). Structure per project precedent in `docs/superpowers/specs/`.
4. **Run adversarial review.** Per the `copowers:brainstorming` skill.
5. **Revise.** Address review findings.
6. **Land the spec.** One commit, docs-only.

### Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. `docs(spec): …`. No Claude co-author footer. No `--no-verify`. No amending.
- **Tests:** fast suite must remain green (N/A this session; no code changes, but run once pre-commit as a sanity check).
- **Ruff:** N/A.
- **Phase isolation:** N/A (no `swing/` changes).

### Commit format

One commit at session end:

```
docs(spec): mini-spec for Tranche B-ops session 1 (Bugs 3a/4/5/6 + field-preservation)

Covers rationale taxonomy (Bug 3a), A+ stop-limit completeness (Bug 5),
total risk exposure display (Bug 6), chart-unavailable reason (Bug 4),
and stop-form field-preservation on StopRegressionError.

Adversarial review via copowers:brainstorming; findings addressed in
the final spec.
```

Adjust the body if adversarial review surfaces notable revisions worth calling out in the message.

---

## 4. Deliverables

1. **The spec file** at `docs/superpowers/specs/tranche-b-ops-session-1.md` (or the filename the user approves).
2. **The commit** landing the spec on `main`.
3. **The return report** per §6 below.

### Spec contents (recommended structure — adjust if a better shape emerges)

- Title, date, status (draft | reviewed | approved).
- One-paragraph mission.
- Context references (V2.1 sections, Bugs.txt items, Tranche A flags).
- One section per in-scope item with: problem statement, decision(s), rationale, out-of-scope clarifications.
- Schema impacts (any migration requirements).
- Template impacts (which partials change, how).
- VM impacts (which view models change, what fields).
- CLI impacts (if any).
- Implementation task list with commit-level granularity.
- Open questions for orchestrator (anything the brainstorm couldn't resolve).
- Adversarial-review summary (Codex findings + resolution notes).

---

## 5. Done criteria

- Spec file committed on `main` under `docs/superpowers/specs/`.
- Every in-scope item (§2) addressed in the spec.
- Adversarial review completed; findings recorded.
- Implementation task list has enough detail to dispatch as subsequent sessions (each task sized to a single commit, scope-restrained, with acceptance criteria).
- Fast test suite green (pre-commit sanity check).
- Return report produced.

---

## 6. Return report format

```
## Tranche B-ops session 1 return report

### Commit landed
- <SHA> docs(spec): ...

### Spec file
- docs/superpowers/specs/<filename>.md (<N> lines)

### Summary of decisions
<One bullet per in-scope item, one sentence each: what the spec decided.>

### Rationale taxonomy draft (summary)
- Entry: <N options, with `other`>
- Stop-adjust: <N options, with `other`>
- Exit: <N options, with `other`>

### Implementation task list (summary)
<N> implementer tasks sized for <N> subsequent sessions, each targeting a single commit.

### Adversarial review
- Rounds: <N>
- Notable findings: <brief summary of what Codex caught; empty if nothing material>
- Revisions applied: <brief summary>

### Open questions for orchestrator
<Anything the brainstorm couldn't resolve.>

### Items flagged but not scoped
<Adjacent concerns the user surfaced that were parked.>
```

---

## 7. If you get stuck

- If the user wants to expand scope into items not listed in §2 "In scope," record the idea in "Items flagged but not scoped" and keep the session bounded. The orchestrator will triage those into later sessions.
- If the adversarial review surfaces a fundamental design problem you and the user can't resolve in this session, land the spec as `status: draft` with the open question recorded, and flag in the return report. The orchestrator will call the next move.
- If you find yourself proposing a generic rationale-framework / taxonomy-engine / schema-DSL, stop. Minimum viable means three per-action closed lists plus `other`. Nothing generic.
- If the user reports a bug or behavior unrelated to the in-scope items, record it and continue. New bugs go to `docs/Bugs.txt` or a return-report flag; they do not join this session's scope.
