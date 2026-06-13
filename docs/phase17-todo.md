# Phase 17 — Consolidation & Parity-Drift Elimination (TODO)

**Opened:** 2026-06-12, operator-approved at the Phase 16 close (proposed by CHARC — [`docs/phase16-close-audit-charc.md`](phase16-close-audit-charc.md) §7; operator added 17-D). **Theme:** the tool is feature-complete for the current trading program and the RD lane is in measurement-awaits-market-time posture; the highest-risk open debt is drift-class, not capability-class. This phase pays it down. **Demand-side:** none anticipated from the RD at commissioning (operator, 2026-06-12); any later demand routes through the operator as usual.

**Schema:** NO migrations anticipated. Any arc that discovers a schema need crosses the §3 tripwire → CHARC architecture pass before dispatch.
**Tripwire posture:** 17-A and 17-B are each expected to introduce NEW modules under `swing/` → their commissioning briefs route through CHARC (cheap pass; CHARC co-authors the scopes, so largely by-construction).
**Baseline at open:** main 8053 fast green · schema v29 · ruff clean · zero open discrepancies · pipeline 2m20s.

---

## Phase 16 trailing items (tracked HERE — their tracker, the P16 orchestrator, was decommissioned 2026-06-12)

> Each item stays until checked off with evidence; the Phase 17 close audit sweeps this section. Verification specs live in [`docs/orchestrator-handoff-2026-06-12-phase16-close.md`](orchestrator-handoff-2026-06-12-phase16-close.md).

- [ ] **T16-1 TROX frozen-not-removed check** — after the NEXT nightly. Expectation (handoff, stated precisely): screen-absent + unpinned → the absent-skip contract; NO injection/suppression audit entries; streak holds at 3; removal fires only on a screen re-entry. Owner: operator or any role with DB read access (read-only query); the first Phase 17 orchestrator session inherits it if still open.
- [ ] **T16-2 Dividend-marker capture** — ORGANIC trigger: the account's first `DIVIDEND_OR_INTEREST` transaction. Action: capture the real description string(s), seed the marker frozensets, UNSKIP `tests/trades/test_schwab_cash_ingestion.py:246` (`test_dividend_marker_set_is_real_payload_sourced`) and make it assert the real-sourced markers. Until then every such transaction tier-2 flags (the safe default — a flag arriving IS the trigger firing).
- [ ] **T16-3 Monthly cadence look** — ORGANIC: when the first monthly review triggers, witness the Arc-9 monthly reference text renders. Owner: operator ritual.
- [ ] **T16-4 RD QAs at next read** — the 0026 §ADDENDUM language · Arc 9's rendered text · the measurement-universe note. Owner: Research Director.

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

### 17-D.1 — `swing eval` persisted runs may displace the nightly's enriched "latest" run (latent risk / open design question — NOT a confirmed defect)

Surfaced 2026-06-12 at the Arc 17-A Task-C divergence sitting (a side-find of the D6 parity work, not 17-A scope). With the operator's rulings **D1 (held-ticker union) and D2 (Arc-7 pin injection) = INTENTIONAL pipeline-only**, an ad-hoc `swing eval` persists an `evaluation_run` *without* the held-union or pin-injection enrichment. If such a run can become "latest" and feed the dashboard / watchlist "latest `evaluation_run`" reads, an interactive `swing eval` could transiently displace the nightly's enriched run (stale held closes; pins not refreshed). **Pre-existing behavior, NOT introduced by 17-A.** Open question for triage before any fix is scoped: should `swing eval` runs be "latest"-eligible, or marked non-displacing (e.g. a run source/kind flag the "latest" query filters on)? Operator-directed landing 2026-06-12; fyi sent to CHARC (who may reclassify or veto — "let CHARC say no").

### 17-D.2 — Dark mode for the comms GUI (enhancement, not a defect)

Operator-requested 2026-06-12. Add a dark-mode theme to the comms mail UI (`scripts/comms_ui.py` — the on-demand localhost FastAPI/HTMX view at 127.0.0.1:8765). Scope at dispatch: a CSS dark theme + a toggle (client-side-persisted); NO new dependency. `scripts/comms_ui.py` is CHARC-custody harness tooling, but this crosses no §3 tripwire (existing script; no new module/schema/dependency/standing process) so it dispatches without an architecture gate.

## Riders (fold-ins, not arcs)

- **R1 (P4/D7):** declare `requests` in `[project] dependencies` — fold into the FIRST arc that touches pyproject; fast suite required on the change (the inline-edit memory).
- **R2 (P6/D9):** one frozen-clock convention line in `docs/orchestrator-context.md` (NEW tests touching dates use a frozen-clock fixture; no retrofit). Orchestrator-lane content; land with the first Phase 17 brief.
- **R3 (optional, on explicit operator want only):** the Arc-1c yfinance call-audit deferred from Phase 16.

## Sequencing (operator's call; CHARC recommendation)

**17-A → 17-B → 17-C**, riders per trigger, 17-D as-needed. 17-A first while the phase is young — it is the risk item and the reason the phase exists; 17-B second so the wrapper extraction happens once over the post-17-A shape; 17-C is disjoint filler for any gap.
