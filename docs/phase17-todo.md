# Phase 17 — Consolidation & Parity-Drift Elimination (TODO)

**Opened:** 2026-06-12, operator-approved at the Phase 16 close (proposed by CHARC — [`docs/phase16-close-audit-charc.md`](phase16-close-audit-charc.md) §7; operator added 17-D). **Theme:** the tool is feature-complete for the current trading program and the RD lane is in measurement-awaits-market-time posture; the highest-risk open debt is drift-class, not capability-class. This phase pays it down. **Demand-side:** none anticipated from the RD at commissioning (operator, 2026-06-12); any later demand routes through the operator as usual.

**Schema:** NO migrations anticipated. Any arc that discovers a schema need crosses the §3 tripwire → CHARC architecture pass before dispatch.
**Tripwire posture:** 17-A and 17-B are each expected to introduce NEW modules under `swing/` → their commissioning briefs route through CHARC (cheap pass; CHARC co-authors the scopes, so largely by-construction).
**Baseline at open:** main 8053 fast green · schema v29 · ruff clean · zero open discrepancies · pipeline 2m20s.

---

## Arc 17-A — Single evaluation orchestration (D6) [HEADLINE]

**The hazard:** `swing/cli.py:369-374` says it outright — `eval_cmd` hand-mirrors `_step_evaluate`'s plumbing "so standalone `swing eval` and the pipeline persist classification identically." The criterion core (`evaluate_batch`) IS shared; the orchestration around it (CSV parse, sector/industry passthrough, RS universe, SPY benchmark, OHLCV fetch, context assembly, persistence) is a comment-enforced parallel copy. This is the V1↔V2 parity-drift family (#24–#26) living in PRODUCTION: drift means `swing eval` and the nightly silently classify differently.

**Scope:** extract ONE shared orchestration path consumed by both entry points; the mirror comment dies because the mirror dies. Likely a new module (name at commissioning; e.g. `swing/evaluation/orchestration.py`) → tripwire pass at commissioning.
**Binding test posture:** characterization FIRST — a golden-parity harness pinning that both entry points produce identical persisted rows on the same inputs BEFORE the extraction, kept green through it. The parity tests must exercise the PRODUCTION derivation path, not stub fixtures (the byte-parity-insufficient gotcha).
**Gate:** one nightly + one manual `swing eval` on the same session producing identical persisted classification rows, operator-witnessed via a diff query.

## Arc 17-B — runner.py step-wrapper extraction (D1)

**Scope:** the outer `lease.step()`/try-except wrapper boilerplate repeated ~11× (runner.py L820-1065 region) becomes a decorator/context-manager; optionally relocate the non-step infrastructure (finviz CSV select L4264-4576, shadow-expectancy helpers, chart/briefing composers) into their own modules (new modules → tripwire pass). Behavior-preserving: #27 warnings semantics, fence hygiene (the #16 fetch-hoist locus), per-step timing emission, and failure-state transitions all byte-identical.
**Sequencing note:** AFTER 17-A — the extraction then wraps the new shared evaluate call rather than the old inline body (one churn pass over that region, not two).

## Arc 17-C — exports retention (D3 / P5)

**Scope:** `swing exports cleanup` mirroring the shipped `swing logs cleanup` shape — age-based, operator-gated, dry-run default; covers the dated `exports/<action_session>/` briefing+chart dirs (41) and `exports/research/` artifact dirs (26) beyond what `_prune_shadow_expectancy_artifacts` already handles. NO schema. Disjoint from 17-A/B — schedulable anytime.

## Arc 17-D — OPEN bug-fix container (operator-added at commissioning)

Standing arc for defects found between Phase 17 commissioning and closeout. Each fix gets its own focused dispatch (TDD; review depth proportional to blast radius — the orchestrator's call, tripwire rules apply as everywhere); entries accumulate here with commit SHAs so the close audit has one place to look. Empty at open — that's the goal state too.

## Riders (fold-ins, not arcs)

- **R1 (P4/D7):** declare `requests` in `[project] dependencies` — fold into the FIRST arc that touches pyproject; fast suite required on the change (the inline-edit memory).
- **R2 (P6/D9):** one frozen-clock convention line in `docs/orchestrator-context.md` (NEW tests touching dates use a frozen-clock fixture; no retrofit). Orchestrator-lane content; land with the first Phase 17 brief.
- **R3 (optional, on explicit operator want only):** the Arc-1c yfinance call-audit deferred from Phase 16.

## Sequencing (operator's call; CHARC recommendation)

**17-A → 17-B → 17-C**, riders per trigger, 17-D as-needed. 17-A first while the phase is young — it is the risk item and the reason the phase exists; 17-B second so the wrapper extraction happens once over the post-17-A shape; 17-C is disjoint filler for any gap.
