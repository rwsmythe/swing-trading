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
