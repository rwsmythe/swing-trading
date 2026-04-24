# Tranche B-research — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Stand up minimum-viable research-branch scaffolding in the repo and produce a study-ready first method record (earnings-proximity exclusion). No study execution this session; no code under `swing/`.
**Expected duration:** One working session. All outputs are documentation.
**Prepared:** 2026-04-23 by orchestrator instance.

---

## 0. Read first

1. Read `CLAUDE.md` in the project root. Note especially the `## Strategy` section added in Tranche A and the conventional-commits + no-Claude-co-author-footer rules.
2. Read `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` (governing strategy — V2.1 is the post-Tranche-A merged version). Particularly §IV (minimum viable shared foundation), §V (Branch A research), §IX (minimum viable governance), and §X (roadmap).
3. Read `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` (binding clarifications). Note especially §1 (minimum viable governance), §2 (toleranced parity), §3 (infrastructure as-needed only), §4 (time-boxed manual delistings), §6 (v1 registry fields), and the full Anti-patterns list.
4. Read `docs/tranche-a-brief.md` and `docs/tranche-b-cleanup-brief.md` for context on what's shipped and the house style for briefs (you will track the research brief itself, so the filing pattern continues).
5. Read `reference/methodology/minervini-trend-template.md` — short reference file, example of methodology reference material. Not directly used this session; read for format precedent.

**Skill posture.** Do NOT invoke the `copowers:*` wrapper skills. The study design, method-record fields, and Phase 0 scope were settled by the orchestrator session that produced this brief. Invoke `superpowers:verification-before-completion` before declaring done. Other superpowers skills are available but likely unneeded — this session is pure documentation authoring.

---

## 1. Strategic context (compressed)

The project runs a bifurcated architecture per V2.1: a **Research and Verification Branch** for defining/testing/falsifying methodological changes, and an **Operational Trader-Facing Branch** (the existing `swing/` codebase) for daily use. Tranche A adopted V2.1 as the strategy baseline and fixed three operator-facing bugs. Tranche B-cleanup tracked the session artifacts.

Tranche B-research is the first session to physically stand up the research branch. It's scoped to minimum viable per V2.1 §IX — a research location, a method-record format, one populated method record, one short study-design doc, and one Phase 0 task list. No more.

**The first study is already chosen: earnings-proximity exclusion** (V2.1 §V.D candidate list; settled in the orchestrator session that wrote this brief). You will populate the first method record for it. You will NOT run the study.

**Binding posture throughout:**

- Minimum viable governance (V2.1 §IX). Do not build general-purpose machinery. Build what this session and the next session require, nothing more.
- Bootstrap-first data strategy (V2.1 §V.E, rebuttal-response §4). Free sources only. Manual delistings (if used at all) time-boxed to the study.
- Toleranced parity (V2.1 §VII.B, rebuttal-response §2). Fixture identity on canonical inputs; toleranced equivalence on vendor-backed data. No "identical output" claims.
- Time-budget realism (V2.1 §III.7). Solo part-time developer. A month of evening work is a lot. A calendar-month method is the upper edge of acceptable.

Review the rebuttal-response Anti-patterns list (strategy inflation, registry maximalism, infrastructure displacement, parity absolutism, bootstrap drift, priority flattening, document worship) and apply the posture to every decision.

---

## 2. Tranche B-research scope

### In scope (exactly seven artifacts, one commit)

| # | Artifact | Kind |
|---|----------|------|
| T1 | Create `research/` directory tree | Docs |
| T2 | Create `research/README.md` — research-branch intro + conventions | Docs |
| T3 | Create `research/method-records/_template.md` — method-record template | Docs |
| T4 | Create `research/method-records/earnings-proximity-exclusion.md` — populated first method record | Docs |
| T5 | Create `research/studies/earnings-proximity-exclusion.md` — study design doc | Docs |
| T6 | Create `research/phase-0-tasks.md` — Phase 0 task list | Docs |
| T7 | Track `docs/tranche-b-cleanup-brief.md` and `docs/tranche-b-research-brief.md` (both untracked) and update CLAUDE.md §Strategy to point at `research/` | Docs |

### Explicitly out of scope

- Any code under `swing/`. Production branch is not touched this session.
- Any data fetching, yfinance calls, earnings-calendar integration, or test harness. Those are Phase 0 / study-execution items for a later session.
- Any broader governance machinery — pre-commit hooks, generated code, validators, schema enforcement, CI. V2.1 §VIII explicitly defers these.
- Any additional method records beyond earnings-proximity. One is enough for minimum viable.
- Any rewrite, expansion, or restructure of CLAUDE.md beyond the one pointer-update in T7.
- Any `tests/` additions. Pure documentation this session.

If you find yourself designing generic infrastructure, creating a base-class hierarchy of method-record types, or writing a validator — stop. That's exactly the "infrastructure displacement" and "registry maximalism" anti-patterns this brief is designed to prevent.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer.** **No `--no-verify`.** **No amending.** One commit for this session.
- **Tests:** fast suite (`python -m pytest -m "not slow" -q`) must remain green. No code changes this session, but run it before commit as a final check.
- **Ruff:** N/A (no Python).
- **Phase isolation:** not triggered — nothing under `swing/` is touched.

---

## 4. Task specifications

### T1 — Create `research/` directory tree

Create the following directory structure at repo root:

```
research/
├── README.md              (T2)
├── method-records/
│   ├── _template.md       (T3)
│   └── earnings-proximity-exclusion.md    (T4)
├── studies/
│   └── earnings-proximity-exclusion.md    (T5)
└── phase-0-tasks.md       (T6)
```

No `__init__.py` or similar. This is a documentation tree, not a Python package.

### T2 — `research/README.md`

Short intro file. Structure:

```markdown
# Research and Verification Branch

This directory contains the Research and Verification branch of the Swing Trading project's bifurcated architecture (see `../reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`, §V).

## What lives here

- `method-records/` — one file per method under research, production, or retired. Format per `method-records/_template.md`. Versioned in-place; major version bumps follow V2.1 §VII.F source-of-truth correction protocol.
- `studies/` — one file per study. Each references the method record it validates, documents baseline/variants/metrics/decision surface.
- `phase-0-tasks.md` — small task list for the current research phase, sized to the time budget (V2.1 §III.7).

## Posture

- Minimum viable governance (V2.1 §IX). Add governance machinery only when an active study or promotion requires it.
- Bootstrap-first data (V2.1 §V.E). Free sources only unless a specific study justifies a paid-data decision.
- Toleranced parity (V2.1 §VII.B). Fixture identity + toleranced vendor-backed equivalence.
- Read the rebuttal-response Anti-patterns list (`../reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`) and apply it.

## Promotion boundary

No method in this directory drives primary operator recommendations unless its method-record `status` field is `production`. Methods in `shadow` status may run in production but do not drive primary decisions (V2.1 §IV.D, §VII.C).
```

### T3 — `research/method-records/_template.md`

Template file. Matches the V2.1 §IV.B minimum viable field list exactly. Use YAML frontmatter for structured fields + Markdown body for narrative. This is a balance: frontmatter is machine-readable if we ever grow tooling, body is hand-editable today.

```markdown
---
key: <stable-identifier-kebab-case>
name: <human-readable-name>
layer: <universe|ranking|trigger|sizing|stop|exit|regime|portfolio|operator-governance|monitoring>
status: <backlog|specified|prototype|validated|production|production_unvalidated|deprecated|retired|rejected>
baseline_or_predecessor: <method-key or "none" or description>
version: 0.1.0
last_updated: YYYY-MM-DD
---

# <Method name>

## Definition

<One paragraph: the deterministic logic/formula/rule that constitutes this method. Include inline citations to source material where the method has a source; use "internal" where the method originates in this project.>

## Inputs

<Bullet list: data fields / prior signals this method consumes. Note timing semantics where relevant (T-1 close vs. T-0 intraday, etc.).>

## Parameters

<Bullet list: named parameters with default values and valid ranges. If none, write "None.">

## Outputs

<Shape of output: scalar per ticker / ranked list / boolean flag / tuple. Units where applicable.>

## Operator explainability

- **One-sentence rationale:** <what the trader sees on the card>
- **One-paragraph explanation:** <what the trader sees when expanding>
- **FAQ:** <the most common operator objection and its answer>

## Validation notes

<Free text: what's been tested, what hasn't, known caveats, edge cases, regime dependencies, failure modes. As the method moves through statuses, this section grows.>

## Changelog

- YYYY-MM-DD — v0.1.0 — initial record.
```

Add a short note at the top of the template (above the frontmatter, as a Markdown comment block) explaining field semantics briefly:

```markdown
<!--
Method record template — V2.1 §IV.B minimum viable fields.

Fields above the triple-dash are YAML frontmatter (parseable; don't add free-form
prose here). Fields below are Markdown (free-form).

`status` lifecycle per V2.1 §IV.B. Transitions require a changelog entry and a
new `version` value. Major version bumps (output semantics changes) require
source-of-truth correction protocol per V2.1 §VII.F.

Keep it short. This is the minimum viable record, not a dissertation.
-->
```

### T4 — `research/method-records/earnings-proximity-exclusion.md`

Populated first method record. Use the template as structural guide but populate all fields for real.

Content specifics:

```yaml
---
key: earnings-proximity-exclusion
name: Earnings-Proximity Exclusion
layer: universe
status: specified
baseline_or_predecessor: none (candidate universe currently has no earnings-aware filter)
version: 0.1.0
last_updated: 2026-04-23
---
```

Definition: the rule excludes a ticker from the candidate universe on a given `action_session_date` if its next scheduled earnings announcement falls within X trading days of that date. X is a tunable parameter; the study validates values X ∈ {3, 5, 7, 10}.

Inputs: ticker's next scheduled earnings date (from an earnings-calendar source); `action_session_date` from the current pipeline run; NYSE trading-day calendar (already used in the repo — see CLAUDE.md on the two-date model and the `action_session_for_run` helper).

Parameters: one parameter, `blackout_trading_days: int`, default `5`, valid range `[0, 21]`. `blackout_trading_days = 0` disables the exclusion (baseline).

Outputs: boolean flag per (ticker, action_session_date) pair. `True` = excluded; `False` = eligible.

Operator explainability:
- One-sentence rationale: "Don't enter within N trading days of earnings — the gap risk isn't priced into the setup."
- One-paragraph explanation: "Stocks that announce earnings within a short window of your entry expose you to overnight gap risk that the stop cannot defend against. The setup signals (MA stack, VCP tightness, RS rank) are all daily-bar signals; they say nothing about what the stock does between the close and the next day's open. Excluding candidates close to earnings keeps the signal-action loop on the same risk basis the setup was measured on."
- FAQ: "Doesn't this lock me out of the best post-earnings moves?" → "Post-earnings is outside the blackout window; this rule doesn't prevent post-earnings entries. It prevents pre-earnings entries where the announcement is imminent."

Validation notes: this record is `specified` status. The study in `../studies/earnings-proximity-exclusion.md` validates the parameter choice. Known caveats (to be tested during the study): (a) free earnings-calendar sources (yfinance, Yahoo, Finviz) are often unreliable on before-market / after-market timing; for EOD trading this matters less than date-precision, but the study's data-quality step must verify source reliability on dates not times; (b) small-cap and OTC tickers may have sparse or missing calendar coverage, which will need a handling rule (default: if no scheduled earnings date is findable, do NOT exclude — treat absent-data as eligible, but flag for review).

Changelog:
- 2026-04-23 — v0.1.0 — initial record, status `specified`, pre-study.

### T5 — `research/studies/earnings-proximity-exclusion.md`

Study design doc. Cites the method record by relative path. Short but complete.

Sections:

```markdown
# Study: Earnings-Proximity Exclusion Parameter Sweep

**Method record:** `../method-records/earnings-proximity-exclusion.md`
**Status:** designed; not yet run.
**Target duration:** one evening's work for data setup + one for analysis (per V2.1 §III.7 time budget).

## Question

Does excluding candidates within X trading days of scheduled earnings improve expectancy and/or reduce gap-risk drawdowns?

## Null hypothesis

Earnings proximity does not systematically affect expectancy or tail-loss magnitude; the exclusion is noise-at-best, cost-at-worst (reduces signal count without improving outcomes).

## Baseline

Current candidate pipeline output without any earnings-proximity filter (equivalent to `blackout_trading_days = 0`).

## Variants

Four treatment variants: `blackout_trading_days ∈ {3, 5, 7, 10}`. Optionally, if cheap to compute, also include a post-earnings cooling-off variant (e.g., skip the first 3 trading days after announcement).

## Data

- Historical candidate set: the repo's own `candidates` table (once it has enough history) OR a synthetic replay using yfinance EOD data + historical earnings calendar. Prefer historical candidates for verisimilitude.
- Earnings calendar source: evaluate ≥2 free sources (Phase-0 task) and commit to the one with better date accuracy. Free sources are known to be unreliable on before-market / after-market timing but adequate on date precision (per V2.1 §V.E, rebuttal Finding 2.20).
- Universe: same as current production evaluation (no broadening).

## Metrics

- Expectancy per signal (R-multiple).
- Gap-through rate (fraction of stopped trades where the stop was breached via gap rather than intraday move).
- Magnitude of gap-through losses (mean and max, normalized by initial risk).
- Signal volume reduction (how many trades does the rule prevent? — cost of the rule).

## Decision surface

One of: `reject` / `shadow` / `promote`. If `promote`, name the chosen `blackout_trading_days` value.

## Parity standard (per V2.1 §VII.B)

- Fixture identity: two synthetic test cases (one excluded ticker, one eligible ticker) must produce bit-identical exclusion flags under the method's computation function.
- Toleranced vendor-backed equivalence: on live calendar data, excluded/eligible classification must agree with a hand-checked spot set of ≥10 tickers × ≥3 calendar months. No claim of exactness against calendar vendors.

## Promotion payload (if `promote` is the decision)

- Candidate-row flag (`is_earnings_blackout BOOLEAN`) emitted by the evaluate step.
- Operator-UI warning badge on candidates within the blackout window (maps to Tranche B-ops B3 risk-warning work).
- Optional hard exclusion in the evaluate step, gated by a `swing.config.toml` flag (default off in shadow phase, configurable once promoted).

## Non-goals

- Intraday earnings-timing precision. EOD workflow does not require it.
- Optimizing X beyond the four candidate values. The grid is deliberately sparse — finer sensitivity analysis is a later-phase refinement, not this first study.
- Post-earnings gap-capture strategy. Out of scope; if interesting, it becomes its own method record later.
```

### T6 — `research/phase-0-tasks.md`

Small task list for Phase 0 (the steady-state governance/scaffolding work per V2.1 §X tranche 1). Realistic for a part-time solo developer per V2.1 §III.7.

```markdown
# Phase 0 task list — Research branch

Per V2.1 §X tranche 1. Time-budget anchor: 4–8 hours/week total project time, 70/30 production/research. Realistic allocation: 1–2 hours/week on research during Phase 0.

Tasks are sized for completion in one evening each (2–4 hours). No task larger than 4 hours; split if it grows.

## Done

- [x] Adopt V2.1 as governing strategy (Tranche A, 2026-04-23).
- [x] Create research-branch scaffolding: directory, README, method-record template (Tranche B-research, 2026-04-23).
- [x] First method record: earnings-proximity exclusion (Tranche B-research, 2026-04-23).
- [x] First study design: earnings-proximity parameter sweep (Tranche B-research, 2026-04-23).

## Next

- [ ] **Evaluate ≥2 free earnings-calendar sources** for date-precision accuracy. Candidates: yfinance (`Ticker.calendar`, `Ticker.get_earnings_dates`), Finviz export columns, Yahoo Finance calendar scrape. Output: short comparison note in `research/notes/earnings-calendar-sources.md`. Pick one; document reliability caveats. (2–3 hours.)
- [ ] **Decide historical-candidate data source** for the study. Either use the repo's own `candidates` table (if there's enough history) or build a synthetic replay harness (yfinance EOD + chosen earnings source). Document decision and rationale. (1–2 hours; decision-only, not implementation.)
- [ ] **Build the study harness** — minimum viable Python script (can live under `research/` as a notebook or plain `.py`; does not go under `swing/`). Reads historical candidates, applies each `blackout_trading_days` variant, emits expectancy/gap-rate/gap-loss/signal-volume metrics. (3–4 hours.)
- [ ] **Run the study** — execute harness with variants ∈ {0, 3, 5, 7, 10}. Capture raw output. (1 hour.)
- [ ] **Write evidence summary** — `research/studies/earnings-proximity-exclusion-results.md`. Includes decision (reject/shadow/promote) and rationale. Triggers copowers adversarial review per Tranche-B-research session 2. (2–3 hours.)

## Later (deferred)

- [ ] Second method record authored (TBD — orchestrator will choose based on study outcomes and operator-branch priorities).
- [ ] Parity test harness — single pytest fixture + helper. Deferred until the first promotion package needs it; minimum viable is fixture-identity on a synthetic input.
- [ ] Cross-study shared utility code (if any pattern emerges across multiple studies). Deferred per V2.1 §V.B until a second study actually surfaces a shared pattern.

## Off the list (V2.1 §VIII deferred)

Explicitly NOT Phase 0 work:

- Full signal-registry platform features.
- Generated code from registry schema.
- Pre-commit enforcement of registry transitions.
- Generalized experiment framework.
- Broad evidence-tier bureaucracy.
- Broad vendor-equivalence frameworks.
- Generalized panel-data architecture.

Revisit these only when a concrete active study demands them and no cheaper alternative exists.
```

### T7 — Track new briefs + CLAUDE.md pointer

**Stage for commit:**

- `docs/tranche-b-cleanup-brief.md` (currently untracked)
- `docs/tranche-b-research-brief.md` (currently untracked; this file)
- All new files created in T1–T6
- CLAUDE.md edit below

**CLAUDE.md edit:** In the `## Strategy` section, after the existing paragraph about methodology references, add one paragraph:

```markdown
The research branch lives at `research/` (created Tranche B-research, 2026-04-23). Method records in `research/method-records/` follow the V2.1 §IV.B minimum viable field list; studies in `research/studies/` follow the format established by `earnings-proximity-exclusion.md`. Phase 0 tasks in `research/phase-0-tasks.md`. No runtime code is under `research/` as of this writing — it is pure documentation and study artifacts.
```

Do not edit any other section of CLAUDE.md.

---

## 5. Commit

One commit covering all seven tasks.

Stage:

```bash
git add research/ docs/tranche-b-cleanup-brief.md docs/tranche-b-research-brief.md CLAUDE.md
git status  # verify expected state
```

Commit message:

```
docs(research): stand up research branch scaffolding and first method record

- Create research/ directory tree with README, method-record template,
  studies/ subdirectory, and Phase 0 task list.
- Populate first method record: earnings-proximity-exclusion (status:
  specified), per V2.1 §IV.B minimum viable field list.
- Author first study design: earnings-proximity parameter sweep
  (X ∈ {3, 5, 7, 10} trading days) with baseline, metrics, parity
  standard, and promotion payload per V2.1 §VII.B.
- Phase 0 task list sized to V2.1 §III.7 time-budget anchor
  (1–2 hrs/week research during Phase 0; no task >4 hrs).
- Track tranche-b-cleanup-brief.md and tranche-b-research-brief.md
  as historical scoping records.
- Update CLAUDE.md Strategy section to point at research/.
```

Run `python -m pytest -m "not slow" -q` before commit. Must be green.

---

## 6. Done criteria

- One commit on `main` with the message above.
- `research/` directory exists with six files (README, template, first method record, first study design, Phase 0 task list, studies dir).
- Both Tranche B briefs tracked.
- CLAUDE.md `## Strategy` section has one new paragraph.
- Fast test suite green.
- Return report produced.

---

## 7. Return report format

```
## Tranche B-research return report

### Commit landed
- <SHA> docs(research): stand up research branch scaffolding and first method record

### Tests
- After: <N> passing, 0 failing (fast suite). No change from baseline expected.

### Deviations from brief
<Anything different from the brief, and why. Empty if none.>

### Files created / modified
- research/README.md (<N> lines)
- research/method-records/_template.md (<N> lines)
- research/method-records/earnings-proximity-exclusion.md (<N> lines)
- research/studies/earnings-proximity-exclusion.md (<N> lines)
- research/phase-0-tasks.md (<N> lines)
- CLAUDE.md (+<N> lines)
- docs/tranche-b-cleanup-brief.md (tracked, no content change)
- docs/tranche-b-research-brief.md (tracked, no content change)

### Items flagged but not done (scope discipline)
<Any adjacent cleanup or enhancement you noticed but deliberately did not do. Orchestrator triages into later sessions.>

### Open questions for orchestrator
<Anything the brief under-specified or where you had to make a judgment call. Empty if none.>
```

---

## 8. If you get stuck

- If the V2.1 field list seems incomplete for the earnings-proximity method record, populate what you have and flag the gap in "Open questions." Do not invent new fields.
- If the template format feels awkward, note it in Open questions and ship the version specified. Format iteration is a later-phase concern.
- If you feel the urge to build generic tooling (a validator, a generator, a registry CLI), stop. That's the infrastructure-displacement anti-pattern. Minimum viable means the minimum.
- If any part of the earnings-proximity study design feels wrong to you (e.g., a metric missing, a variant poorly chosen, a parity claim over-broad), implement what's written and flag the concern in Open questions. The orchestrator will triage.
