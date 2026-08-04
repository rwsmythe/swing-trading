# Commissioning Brief — 21-G: the two joint false-all-clear fixes + the `data_asof_date` survey

**From:** CHARC. **To:** the Phase-21 orchestrator. **Arc:** 21-G ([`phase21-scope-charc.md`](phase21-scope-charc.md)) — split out of 21-B at commissioning 2026-07-28. **Parallel with 21-B (file-disjoint) — but 21-G MERGES FIRST (binding, §1).**
**§3 verdict:** MEASUREMENT-CHAIN arc → **RD's rulings are BINDING and his plan-stage + merge QA are the primary gates.** CHARC §3 pass required only if the fix reaches into `swing/evaluation/` write paths — see §2.4; the read-side fix is expected sub-tripwire. Schema: NOT expected — if per-row provenance turns out to need a column, **STOP and route to CHARC** (it is a different, larger arc).

## §1 Why this merges before 21-B (the ordering is the reason the arc exists separately)

The regime selection determines the **recorded order TYPE** (STOP_LIMIT when price is below the latched pivot, LIMIT at or above). A stale-price regime therefore writes a **WRONG TYPE** into 21-B's execution-parity ledger — so a framework-vs-actual "mismatch" at RD's monthly read would be **the framework's own defect masquerading as an operator divergence**, and unattributable after the fact. **Fix the writer before you trust what it writes** (the 20-A Half-A-before-Half-B discipline).

## §2 The two routes to one failure — fix them together

### 2.1 Route A — the stale close (RD's asymmetry)
The shape check needs a derivation-session close. It is **inert ~7 hours a day** — from the action-session rollover (which coincides with the US close) until the nightly run — **which is exactly the window in which a regime change first becomes detectable**, since a pivot crossing happens during market hours and is first observable after the close. So the check is absent when the thing it detects has most likely just happened, and present overnight when nothing has changed. FTRE is the proof case: its correct order shape had to change stop-limit→limit precisely because price crossed the pivot.

### 2.2 Route B — the run-level stamp (the provenance gap)
`evaluation/orchestration.py:231` stamps `data_asof = max(max_dates)` — a **cohort-max** — persisted at `:309`, while `evaluation/evaluator.py:56` takes `last_close` from **that ticker's own** last bar, stored at `:94`. A lagging ticker is therefore persisted with an **older close under a fresher stamp**, and any consumer treating the stamp as provenance for the close reads a date the close does not have. **The shape check can bless the wrong order form off a stale price.**

### 2.3 The single rule that resolves both (RD, BINDING)
> **From a stale close — as from a run-level stamp — you MAY raise a MISMATCH ALARM but you may NOT assert a MATCH.**

Asymmetric by design, because the error costs are asymmetric: a false alarm is **annoying, safe, and self-correcting** (the operator opens the panel or the broker and sees); a false all-clear is **the arc's dominant defect class**. This is not a new principle — it is the same asymmetry already ruled for cached order state, which is itself evidence the shape is real rather than two coincidences.
**Consequence to design for:** the 7-hour window should produce *legitimate, labelled, one-session-stale mismatch alarms* while never producing a false all-clear — recovering most of the check's value in exactly the hours it currently has none.

### 2.4 The survey — RD's epistemic position, preserved verbatim
`data_asof_date` is a **persisted run-level field** and the latch panel is merely the **first consumer** to lean on it as close-provenance. Grep its consumers and report: is this one bug or a class? **RD: *"I am not asserting it is a class — I am refusing to assume it is not."*** The survey **reports**; it does not authorize fixing every hit — anything beyond the shape-check path comes back for scoping. **If the survey finds the write path itself must change (per-ticker provenance at write time), STOP: that is a schema/measurement-chain arc of its own, routed to CHARC + RD.**

### 2.5 The shape, named (gotcha #30, both instances in this codebase)
**A RUN-LEVEL STAMP STANDING IN FOR A PER-ROW FACT.** Instance 1: freeze-at-fire (a run-level "current" standing in for the fire's own pivot — FTRE 18.34 walking to 20.19 while armed). Instance 2: this one. The real fix in both is per-row provenance at write time; the *available* fix here is the §2.3 asymmetry, which is the upper-bound treatment.

## §3 Tests

Discriminating, from REAL geometries: a ticker whose archive lags the cohort max is stamped fresher → **pre-fix the shape check asserts a match; post-fix it refuses to assert and (where the data supports it) raises a labelled mismatch instead**. A ticker with a genuine derivation-session close behaves **byte-identically** to today (the no-regression lock). The 7-hour window produces a labelled stale-derived mismatch where one genuinely exists, and **never** an all-clear. Survey output is a committed artifact, not a chat claim.

## §4 Gates

RD plan-stage (his rulings, his lane) → review-strong + **codex-auto-review (required, §2.9 — verify the working invocation at dispatch)** → suite + ruff + merged-head no-false-green → **RD merge-blocking QA** → **merge BEFORE 21-B's ledger lands**. Operator witness only if a user-visible surface changes. Gate visibility (harness-architecture §2) applies. The ORCHESTRATOR posts the return to `charc,rd`.

## §5 Sizing + cells

Small-medium; high semantic density, low line count. **writing-plans + executing `implementer-opus-high`** (RD's rulings settle the design; the work is careful application + the survey). Orchestrator selects + announces.
