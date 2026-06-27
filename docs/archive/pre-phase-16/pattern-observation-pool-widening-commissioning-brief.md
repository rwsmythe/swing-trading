# Pattern-Observation Pool-Widening — Commissioning Brief

**Audience:** A Claude Code instance taking on the orchestrator role for this sub-bundle. This is an ORCHESTRATOR HANDOFF / SCOPE COMMISSIONING, **NOT an implementation prompt.** Do not begin implementation. Do not draft an implementer dispatch brief before completing the operator-paired triage at Sec 9 and the `copowers:brainstorming` phase.

**Mission:** Widen the production pattern detect + observe pipeline pool from `bucket == 'aplus'` to `bucket IN ('aplus','watch')`, so the Phase-14 temporal observation log accumulates forward-walk data on the **watch** population (≈80× larger than aplus) **without trading any of it and without touching the Finviz screen or any capital path.** This realizes the "decouple data-generation from capital deployment" objective that the applied-research arc closure (2026-05-27) set as the forward direction — using the observation log, not trade volume, as the learning substrate.

**Status:** PROPOSED — not yet commissioned. Operator-paired triage (Sec 9) is the gate.

**Workflow expectation:** A single `copowers:brainstorming` → `copowers:writing-plans` → `copowers:executing-plans` cycle. This is one contained sub-bundle, not a multi-bundle phase.

**Main HEAD at brief-authoring:** `5ab6878e` (process-grade-trend redesign, writing-plans dispatch). **The orchestrator is mid-arc on PGT redesign** — see Sec 7 for why this sub-bundle should NOT be wedged into the in-flight Phase-15 todo.

**Cumulative discipline at brief-authoring:** Schema **v24** (a new schema migration here, IF the operator elects the bucket-tagging option, would be `0025` → v25). Baseline ~7086 fast tests green on `main`. Cumulative CLAUDE.md gotchas through **#29** BINDING. ZERO `Co-Authored-By` trailer streak (~700+ commits) to preserve. L2 LOCK (zero new Schwab API calls) untouched by this work.

---

## Sec 0 Read first (in this order)

1. **THIS BRIEF end-to-end.**
2. **`CLAUDE.md`** — the "Current state" line-3 paragraph (Phase 15 in-flight state); the **Gotchas** section, especially the Pattern-detector cluster (**#27** silent-skip-without-audit, **#28** pattern-exemplar OHLCV cache, **#29** exemplar OHLCV historical depth) and the SQLite cluster (**#9** executescript, **#11** schema-CHECK + Python-constant + dataclass-validator paired discipline) and the yfinance cluster (OHLCV fetch scope; archive write-through).
3. **`docs/orchestrator-context.md`** — durable orchestrator-role bootstrap; process disciplines.
4. **`swing/pipeline/runner.py`** — read [`_step_pattern_detect`](../swing/pipeline/runner.py) (line ~1439, esp. the pool predicate at ~1531) and [`_step_pattern_observe`](../swing/pipeline/runner.py) (line ~2503). These two steps ARE the surface of this change.
5. **`swing/data/migrations/0022_phase14_temporal_log.sql`** — the append-only `pattern_detection_events` + `pattern_forward_observations` schema. Note the `source` enum and `finviz_screen_state` column were built multi-source by design.
6. **`research/studies/finviz-pool-binding-constraints.md`** — the binding-constraint study that quantifies the funnel (aplus 0.25%, watch 20.6%, the proximity_20ma/MA/TT blocker profile). This is the empirical justification for "widening price/risk does not add volume; widening the OBSERVED pool does add learning data."
7. **The `memory/` directory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\` — especially `feedback_orchestrator_qa_implementer_product`, `feedback_orchestrator_performs_merge`, `feedback_commit_brief_before_inline_prompt`, `feedback_always_provide_inline_dispatch_prompt`, `feedback_await_return_before_qa`, `feedback_verify_regression_test_arithmetic`, `feedback_no_false_green_claim`, `project_applied_research_arc_2026-05-27`.

---

## Sec 1 Mission + strategic justification (provenance)

This sub-bundle was surfaced in the operator session of 2026-06-03/04, in a thread that began with closing the **Sub-A+ VCP-not-formed** hypothesis (#3) as `closed-target-met` (n=10 = 2× target; mean R −0.20; net −$79.02; the absolute-loss tripwire fired and the decision criterion — negative mean R — was confirmed). Closing #3 removed the hypothesis that was matching ~94% of the watch-bucket recommendation volume, which raised the operator's "trading data will go sparse" concern.

The analysis that followed established three facts that drive this brief:

1. **The candidate funnel is honestly sparse.** Per `research/studies/finviz-pool-binding-constraints.md`: aplus = **0.25%** of evaluations (and single-ticker on the snapshot); watch = **20.6%**; the dominant blockers (`proximity_20ma` 44%, `ma_stack` 13%, `TT2` 12%) are trend/VCP-quality criteria, NOT capital criteria. `risk_feasibility` blocks only 2.3%.
2. **Therefore the levers that DON'T help learning:** widening the Finviz price band (`sh_price_5to100`) dilutes the curated A+ substrate (operator already declined this on 2026-05-25); raising the risk budget increases position SIZE, not trade COUNT (risk is not the binding constraint). Both were considered and set aside in-session.
3. **The lever that DOES help:** the Phase-14 temporal observation log already runs nightly (`_step_pattern_detect` → `_step_pattern_observe`), but its pool predicate is `bucket == 'aplus'` only ([`runner.py` ~1531](../swing/pipeline/runner.py)). Widening it to include `watch` grows the observed population ~80× **at zero capital risk and zero Finviz-screen change** — the cleanest expression of the arc-closure forward direction (learn from observation, not from forced trades).

**This is observation-substrate widening, not a ruleset or trade-management change.** No production trade rule, sizing rule, bucket assignment, or recommendation surface is modified. Detections and forward-observations are an internal-derivation accumulator.

---

## Sec 2 Scope

### In scope (the contained version — RECOMMENDED V1)

- Change the `_step_pattern_detect` pool predicate from `bucket == 'aplus'` to `bucket IN ('aplus','watch')`, and the corresponding empty-pool warning field (`actual_aplus_pool`) so the gotcha-#27 audit entry stays accurate for the widened pool.
- Carry the bucket forward onto each detection so downstream/future consumers can distinguish aplus-origin from watch-origin patterns (see Sec 4 Q2 for the storage decision — JSON-only vs a first-class column).
- Verify and bound the `_step_pattern_observe` daily load under the widened detection set (the multi-session observation window now tracks ~80× more open detections).
- Full test rework for the widened pool (the existing detect/observe + temporal e2e fixtures assume aplus-only).

### Out of scope

- **Any beyond-Finviz universe net.** Running detectors over a universe wider than the Finviz pool (the original "supplemental screen for non-VCP setups" idea, banked 2026-05-25) is a much larger lift — it needs a separate universe source and its own bar-fetch budget. The contained version reuses already-evaluated watch tickers. A beyond-Finviz net is a SEPARATE future commissioning, explicitly NOT this sub-bundle.
- **Any trade-management, sizing, bucket-assignment, or recommendation-engine change.** Including the `#3`/`risk-budget` discussion from the originating session — that is a separate, parked decision.
- **Any Finviz screen change.**
- **A new operator-facing surface that reads the widened log.** There is no current production consumer (Sec 3); building one is a follow-on, not this sub-bundle. This sub-bundle ends at "the log accumulates the watch population, correctly tagged, with bounded cost."
- **Backfill of historical watch detections.** V1 is forward-walk only (start accumulating from ship date), consistent with the append-only forward-walk invariant.

---

## Sec 3 Architectural notes (grounded; for the brainstorming orchestrator to confirm)

- **The code trigger is one predicate.** [`runner.py` ~1531](../swing/pipeline/runner.py): `aplus_tickers = [c.ticker for c in candidates if c.bucket == "aplus"]`. The rest of `_step_pattern_detect` (window generation, 5-detector registry, SELECT-then-INSERT idempotency, histogram seed) is pool-agnostic. The substance of this sub-bundle is NOT the predicate — it is the systemic consequences below.
- **No schema change is strictly required.** `0022_phase14_temporal_log.sql` built `pattern_detection_events` with a `source` enum (`pipeline`, `v2_cohort`, `backfill`, …) and a nullable `finviz_screen_state` JSON that already captures per-ticker eval/screen state. Watch detections fit as `source='pipeline'` with bucket in that JSON. A first-class indexed `source_bucket` column (→ `0025`/v25) is an OPTION for clean future filtering, not a requirement — Sec 4 Q2.
- **No current consumer surface reads the temporal log.** A grep of `swing/web/` for `pattern_detection_events` / `pattern_forward_observations` / `list_observable_detections` returns ZERO hits; the 9th metric tile (`swing/metrics/pattern_outcomes.py`) is **exemplar-driven** (reads `pattern_exemplars` by `label_source`/`final_decision`), not detection-driven. **Implication:** widening the pool cannot contaminate any existing surface — there is none. The bucket-tagging decision (Q2) is forward hygiene for future consumers, not a fix for a present contamination.
- **OHLCV cost is bounded by reuse.** Watch-bucket tickers are evaluated upstream (`_step_evaluate`) — criteria require bars — so their OHLCV is already in the shared `ohlcv_cache` / on-disk archive. `_step_pattern_detect` fetches via `ohlcv_cache.get_or_fetch(window_days=400)` ([`runner.py` ~1668](../swing/pipeline/runner.py)); for watch tickers this largely hits cache. **Net-new fetch cost should be small — brainstorming MUST quantify it** (the dominant unknown is the observe step, below).
- **The observe step is the real scaling question.** `_step_pattern_observe` ([`runner.py` ~2503](../swing/pipeline/runner.py)) appends a daily bar + lifecycle status for every OPEN detection over a window of `observe_max_pending_window_sessions` + `observe_max_post_trigger_window_sessions`. ~80× more open detections means ~80× more daily per-detection bar lookups, sustained across each detection's observation window. Tickers that rotate out of the candidate pool mid-window hit the OHLCV-freshness gotchas (**#24** parallel-archive freshness, **#26** archive bar-content temporal mutation) — though the append-only `ohlc_today_json` LOCK-at-observation design (0022) is specifically built to neutralize re-fetch drift. Brainstorming MUST confirm the per-night observe cost is acceptable and the freshness invariants hold at the widened scale.
- **Compute.** ~80× more detector invocations/night (watch ≈ 249 vs aplus ≈ 3 on the snapshot), each running zigzag window generation + 5 detectors + template-match Pass 2. On cached bars this is CPU, not network — but the pipeline-runtime delta should be measured, not assumed.

---

## Sec 4 Open design questions for the brainstorming phase

These are the substantive decisions; resolve them operator-paired during `copowers:brainstorming`.

- **Q1 — Pool definition.** `aplus + watch` (recommended; reuses evaluated tickers) vs `aplus + watch + skip` (skip is 74% of the pool but is mostly trend-template failures — likely low-signal noise + much higher cost). Recommendation: `aplus + watch` for V1.
- **Q2 — Bucket provenance storage.** (a) Rely on the existing `finviz_screen_state` JSON (zero schema change; filtering by JSON extraction); or (b) add a first-class indexed `source_bucket` column via migration `0025` (→ v25; gotcha #11 paired schema-CHECK + dataclass-validator discipline; backup-gate equality form per #11). Recommendation lean: (b) is cheap insurance for the eventual consumer surface, but (a) is defensible for V1 since there is no consumer yet. Operator call.
- **Q3 — Observation-load bound.** Accept the ~80× observe load as-is (if brainstorming's measurement shows it's acceptable), or introduce a cap / sampling / shorter observation window for watch-origin detections than for aplus-origin. Recommendation: measure first; only cap if the nightly runtime or fetch volume crosses an operator-set threshold. Whatever is decided, a silent cap is forbidden (gotcha #27 — emit a `warnings_json` accounting of any dropped/sampled detections).
- **Q4 — Idempotency / partial-retry under the wider pool.** Confirm the SELECT-then-INSERT idempotency + the per-run composite-score histogram seed behave correctly when the population is 80× larger and may include watch tickers that flip bucket across same-day re-runs (the finviz-pool study documents per-day pipeline re-runs).
- **Q5 — Pattern-outcomes tile isolation.** Confirm (or, if needed, enforce) that the exemplar-driven 9th metric tile remains uncontaminated, and decide whether any FUTURE consumer of the widened log should default to aplus-only with watch as an opt-in filter.

---

## Sec 5 Cumulative discipline BINDING

The orchestrator inherits ALL cumulative discipline. The directly-relevant items:

- **#27 (silent-skip-without-audit in pipeline steps)** — the widened pool MUST keep the empty-pool/early-return `warnings_json` accounting accurate; any cap/sampling (Q3) MUST emit an audit entry. Do not let a wider-but-partially-dropped pool read as "covered everything."
- **#28 + #29 (pattern-exemplar OHLCV cache + historical depth)** — watch tickers are in-universe (unlike exemplars) so #28/#29 are less acute, but the multi-session observe window re-raises cache-miss handling; verify the bad-window isolation (per-element try/except) holds at scale.
- **#24 + #26 (archive freshness / bar-content temporal mutation)** — the observe step's `ohlc_today_json` LOCK-at-observation neutralizes these by construction; confirm the invariant holds for watch tickers that rotate out mid-window.
- **#11 (schema-CHECK + Python-constant + dataclass-validator paired)** — applies IFF Q2(b) elects the `source_bucket` column.
- **#9 (executescript implicit COMMIT)** — applies IFF a migration lands; explicit BEGIN/COMMIT/ROLLBACK runner discipline.
- **#1 (test-count drift)** — trust pytest output for the final test count; the estimates in Sec 6 are non-binding.
- **Streaks:** ZERO `Co-Authored-By` trailer; L2 LOCK (no new Schwab calls — untouched here); ASCII discipline on all new files; re-run the fast suite ON THE MERGED HEAD before any green claim (`feedback_no_false_green_claim`).

---

## Sec 6 Workflow expectation

A single copowers cycle:

1. **`copowers:brainstorming`** → spec at `docs/superpowers/specs/2026-XX-XX-pattern-observation-pool-widening-design.md`; resolve Sec 4 Q1–Q5 operator-paired; Codex adversarial review to convergence (per `feedback_codex_round_limit_suspended` — run to zero new crit/major, no round cap).
2. **`copowers:writing-plans`** → plan at `docs/superpowers/plans/2026-XX-XX-pattern-observation-pool-widening-plan.md`; Codex review to convergence.
3. **`copowers:executing-plans`** → dispatch to an implementer; orchestrator QAs against reality on disk, performs merge + push + housekeeping per `feedback_orchestrator_performs_merge`.

**Non-binding scope estimate** (trust pytest, not this line — gotcha #1): code change is trivial; the work is in observe-load verification, bucket-provenance, and test rework. Rough order: ~4–8 commits + ~20–40 tests; one optional v25 migration. **Codex chain count:** this is borderline analytical (it changes what statistical substrate accumulates) — recommend the two-chain treatment if the brainstorming spec includes any methodology claim about the widened substrate's analytical use; single chain is defensible if it stays purely a pipeline-pool mechanical change. Orchestrator discretion at the spec phase.

---

## Sec 7 Phase placement recommendation

**Do NOT wedge this into the in-flight Phase-15 todo.** Rationale:

1. **Domain mismatch.** Phase 15 is an integration/infrastructure phase (schwabdev-v3 upgrade CLOSED; B-7 failure-mode SHIPPED; PGT-redesign in-flight). Pattern detect/observe is Phase-14 (temporal pattern/observation) domain. Folding it in crosses phase isolation.
2. **The orchestrator is genuinely busy.** HEAD `5ab6878e` is a PGT-redesign writing-plans dispatch — an arc mid-flight. Injecting a nightly-pipeline-step + test-fixture change now muddies that arc's test baseline (currently ~7086 green) and risks scope creep.
3. **Small code, real systemic effects.** The observe-load scaling and the bucket-provenance decision are exactly the class of change that benefits from its own spec/plan/Codex pass — they are the substance, not the predicate.

**Recommended placement:** a standalone sub-bundle commissioned AFTER the current PGT-redesign arc closes (and, per CLAUDE.md, the Phase-14 cross-sub-bundle integration review), slotted as a Phase-15 strategic-backlog item (the B-1..B-8 family in phase3e-todo `#5`) or a Phase-16 candidate. The operator sets the label at Sec 9.

---

## Sec 8 What this brief is NOT

- **Not an implementation prompt.** The orchestrator drives the copowers cycle; this is the scope handoff.
- **Not a complete plan.** Sec 4 questions are unresolved by design; brainstorming resolves them.
- **Not a ruleset / trade-management / sizing change.** It widens an internal observation accumulator only. The risk-budget discussion from the originating session is explicitly parked and out of scope.
- **Not a Finviz-screen change, and not a beyond-Finviz universe net** (the latter is a separate, larger future commissioning).
- **Not a new operator-facing surface.** V1 ends at "the log accumulates the watch population correctly and affordably."

---

## Sec 9 Operator-paired decisions for the commissioning orchestrator

Open with operator pairing (likely `AskUserQuestion`) BEFORE drafting the brainstorming spec:

- **D1 — Commission now or bank?** Commission this as the next sub-bundle, or bank it until the PGT-redesign arc + Phase-14 integration review close (Sec 7 recommendation: bank, then commission standalone).
- **D2 — Phase label.** Phase-15 strategic-backlog item (B-X) vs Phase-16 candidate.
- **D3 — Pool definition (Q1):** confirm `aplus + watch` vs include `skip`.
- **D4 — Bucket provenance (Q2):** `finviz_screen_state` JSON only (no schema change) vs first-class `source_bucket` column (v25 migration).
- **D5 — Observe-load policy (Q3):** accept-and-measure vs pre-commit to a cap/sampling/shorter-window for watch-origin detections.
- **D6 — Codex chain count:** one vs two chains (per Sec 6).

Operator decisions LOCK at commissioning and propagate to the implementer dispatch; deviations require a return-trip to the operator.

---

## Sec 10 Triage outcome (operator-paired, 2026-06-03) -- BANKED + SCOPED

Sec 9 operator-paired triage completed 2026-06-03; decisions LOCKED for the eventual standalone commissioning:

- **D1 -- BANKED.** Do NOT commission now (the process-grade-trend-redesign writing-plans arc is in flight). Commission as a standalone copowers sub-bundle AFTER the PGT-redesign arc closes (and ideally the Phase-14 cross-sub-bundle integration review). Tracked in `docs/phase3e-todo.md` §A (Phase-15 strategic backlog).
- **D2 -- Phase-15 strategic-backlog item (B-family)** -- the B-1..B-8 substrate-augmentation family (orchestrator-recommended, operator-accepted).
- **D3 (Q1) -- pool = `aplus + watch`** (NOT skip). Reuses already-evaluated watch tickers (OHLCV largely cached); ~83x population (3 -> 252 on the snapshot).
- **D4 (Q2) -- `finviz_screen_state` JSON only; NO schema change.** No v25 `source_bucket` column for V1 -- there is no consumer surface yet; the bucket rides in the existing JSON. (If a future consumer needs indexed filtering, the column is a follow-on.)
- **D5 (Q3) -- accept-and-measure.** The brainstorm MEASURES the widened observe runtime + bar-fetch volume; cap/sample ONLY if it crosses an operator threshold, and ONLY with a gotcha-#27 `warnings_json` audit (NO silent cap).
- **D6 -- single Codex chain** per phase (orchestrator-recommended, operator-accepted; the scope is a mechanical pipeline-pool change with the analytical/consumer surface out of scope -- no methodology claim triggers the two-chain treatment).

**Verified at triage (against disk):** the predicate `runner.py:1531` (`c.bucket == "aplus"`) + the #27 audit field `actual_aplus_pool:1547`; the observe step `runner.py:2503` (`list_observable_detections(source="pipeline")` -> per-open-detection cached bar + idempotency + per-ticker #27 no-bar warning); migration 0022 (the `source` enum + nullable `finviz_screen_state` JSON, NO bucket column; append-only `ohlc_today_json` LOCK-at-observation neutralizes #26/#37); the study funnel (aplus 3/0.25%, watch 249/20.6%, skip 898/74.3%; blockers trend/VCP-quality, not capital).

**When commissioned:** these locks propagate into the `copowers:brainstorming` spec (Sec 4 Q1/Q2/Q3 are pre-resolved as D3/D4/D5; Q4 idempotency-under-the-wider-pool + Q5 pattern-outcomes-tile isolation remain brainstorm work). Deviations require a return-trip to the operator.

---

*End of commissioning brief. Mission: widen the nightly pattern detect/observe pool from aplus to aplus+watch so the Phase-14 observation log accumulates ~80× more forward-walk learning data at zero capital risk and zero Finviz-screen change — the clean expression of "decouple data-generation from capital." One contained copowers cycle. NOT a Phase-15 bolt-on (Sec 7). NOT a ruleset/sizing/screen change. NOT an implementation prompt. The substance is the observe-load bound + bucket-provenance + test rework, not the one-line predicate.*
