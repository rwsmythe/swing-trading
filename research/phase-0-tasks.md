# Phase 0 task list — Research branch

Per V2.1 §X tranche 1. Time-budget anchor: 4–8 hours/week total project time, 70/30 production/research. Realistic allocation: 1–2 hours/week on research during Phase 0.

Tasks are sized for completion in one evening each (2–4 hours). No task larger than 4 hours; split if it grows.

## Done

- [x] Adopt V2.1 as governing strategy (Tranche A, 2026-04-23).
- [x] Create research-branch scaffolding: directory, README, method-record template (Tranche B-research, 2026-04-23).
- [x] First method record: earnings-proximity exclusion (Tranche B-research, 2026-04-23).
- [x] First study design: earnings-proximity parameter sweep (Tranche B-research, 2026-04-23).
- [x] Evaluate ≥2 free earnings-calendar sources for date-precision accuracy (Tranche B-research 2a, 2026-04-24). See `notes/earnings-calendar-sources.md`. Decision: yfinance `get_earnings_dates()`; 5/5 primary-source spot-check matches.
- [x] Decide historical-candidate data source (Tranche B-research 2a, 2026-04-24). See `notes/historical-candidate-source-decision.md`. Decision: Option B (synthetic replay); repo has 2 A+ signals vs. ≥120 threshold; ~77% of replay logic reusable from `swing/evaluation`, `swing/recommendations`, `swing/trades`.

## Next

- [ ] **Build the study harness** — minimum viable Python script (can live under `research/` as a notebook or plain `.py`; does not go under `swing/`). Reads historical candidates, applies each `blackout_trading_days` variant, emits expectancy/gap-rate/gap-loss/signal-volume metrics. (3–4 hours.)
- [ ] **Run the study** — execute harness with variants ∈ {0, 3, 5, 7, 10}. Capture raw output. (1 hour.)
- [ ] **Write evidence summary** — `research/studies/earnings-proximity-exclusion-results.md`. Includes decision (reject/shadow/promote) and rationale. Triggers copowers adversarial review per Tranche-B-research session 2. (2–3 hours.)

## Later (deferred)

- [ ] **Evaluate which A+-like indicators from source-of-truth references warrant method-records + studies** (operator-surfaced 2026-05-22 PM; depends on T4.SB Item 1 0-A+-candidates diagnostic outcome). Context: across 63 evaluation runs since v20 detector chain landed, ZERO A+ candidates have surfaced. Open question is whether (a) calibration is too tight (T4.SB Item 1 diagnostic answers) AND/OR (b) the source-of-truth references (Minervini *Trade Like a Stock Market Wizard*; "Disciplined Swing Trader" PDF; Lo-Mamaysky-Wang 2000 chart-pattern paper; Ken French data library; QuantEcon companion docs) suggest A+-like indicators we should add. Candidate indicators surveyed by orchestrator 2026-05-22 PM (8 total — see git log / chat 2026-05-22 PM for full table): Trend Template Stage 2 confirmed (Minervini 8-criteria; #1 candidate — already half-built via `current_stage()` wrapper at `swing/patterns/foundation.py:745`); earnings/sales acceleration (CAN SLIM-adjacent); VCP base-maturity quantitative (Lo-Mamaysky-Wang bootstrap significance); momentum-factor exposure (Fama-French MOM); sector/industry RS confirmation; pre-A+ "Watch+" tier (M-of-N bucketing — surfaces today's hyp-recs as 1st-class output); 52-week-high proximity gate; earnings-proximity exclusion (already designed at `studies/earnings-proximity-exclusion.md`). Next-action sequence: wait for T4.SB Item 1 diagnostic ship → pick 1-3 indicators to advance → author method-record stub(s) per `method-records/_template.md` → design study per `studies/earnings-proximity-exclusion.md` precedent. **Time budget**: per V2.1 §X 4-8h/wk total, 70/30 production/research = ~1-2h/wk research. First method-record stub fits in one evening; full study (build harness + run + write evidence summary) ~6-9 hours over 3-4 weeks. **Posture per V2.1 §IX**: minimum viable governance — don't pre-commit to a Phase 14 program; let the T4.SB diagnostic inform the first study choice.
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
