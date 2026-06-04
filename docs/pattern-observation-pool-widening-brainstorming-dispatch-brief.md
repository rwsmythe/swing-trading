# Pattern-Observation Pool Widening (aplus -> aplus+watch) -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the pattern-observation-pool-widening brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for **widening the nightly pattern detect + observe pool** from `bucket == 'aplus'` to `bucket IN ('aplus','watch')`, so the Phase-14 temporal observation log (`pattern_detection_events` + `pattern_forward_observations`) accumulates the ~80-83x-larger **watch** population as forward-walk learning data -- **at ZERO capital risk, ZERO Finviz-screen change, and (per the operator triage LOCKs) ZERO schema change.** This realizes the "decouple data-generation from capital deployment" objective the applied-research arc closure (2026-05-27) set as the forward direction: learn from the OBSERVATION log, not from forced trades. This is a standalone Phase-15 strategic-backlog (B-family) sub-bundle; it is **NOT** a ruleset/sizing/bucket-assignment/recommendation/Finviz change.

**This brief is a DISPATCH (the scope is already commissioned + triaged).** The governing scope document -- read it end-to-end -- is `docs/pattern-observation-pool-widening-commissioning-brief.md`; its **Sec 10 (operator triage 2026-06-03)** LOCKS decisions D1-D6 (below as L1-L6). The brainstorm propagates those locks; it does NOT re-open them. The brainstorm's real work is the OPEN questions: the observe-load measurement/bound (D5/L4), Q4 idempotency-under-the-wider-pool, and Q5 pattern-outcomes-tile isolation.

**Brief:** `docs/pattern-observation-pool-widening-brainstorming-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; THREE Phase-15 arcs CLOSED (schwabdev-v3 `#20`, B-7 failure-mode `#21`, process-grade-trend redesign `#22`). main HEAD at this dispatch: see §8 (branch from it). ~7105 fast tests green; **schema v24**. This arc adds **NO migration, NO schema change, NO lock change (the Schwab L2 LOCK is untouched -- zero new Schwab calls), NO live cutover.** The code trigger is a one-line predicate; **the substance is the observe-load bound + the provenance confirmation + the test rework**, NOT the predicate.

**Cumulative discipline:** the CLAUDE.md **Pattern-detector** gotchas are BINDING -- esp. **#27** (silent-skip-without-audit: any cap/sample MUST emit a `warnings_json` entry -- NO silent cap), **#28/#29** (exemplar OHLCV cache + historical depth -- less acute here since watch tickers are IN-universe, but the multi-session observe window re-raises cache-miss handling), **#24/#26** (archive freshness / bar-content temporal mutation -- the append-only `ohlc_today_json` LOCK-at-observation neutralizes these by construction; confirm it holds for watch tickers that rotate out mid-window); the **yfinance** OHLCV-fetch-scope + write-through-archive gotchas; **#9** (executescript -- N/A, NO migration) + **#11** (schema-CHECK/constant/validator triad -- N/A, NO schema). ~700+ cumulative ZERO `Co-Authored-By`; **Schema v24 UNCHANGED (D4 -- confirm at brainstorm).**

**Expected duration:** ~2-4 hours brainstorming + a Codex chain to convergence. Spec line target **~350-500 lines** (the bulk is the observe-load model + Q4/Q5 + the measurement methodology, not the predicate).

**Skill posture:**
- Invoke the `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end (D6). **Run to CONVERGENCE** (zero new criticals AND zero new majors; `NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED -- a bare invocation resolves the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex` (no node). PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). **Pass the prompt via STDIN** (`cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`), NOT `"$(cat ...)"` (breaks on parens). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE** (incl. the literal final `### Verdict` / `NO_NEW_CRITICAL_MAJOR` line) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/2026-06-04-pattern-observation-pool-widening-design.md`.

---

## §0 Read first (in this order; orchestrator-verified anchors -- TRUST the tree + re-grep at writing-plans per gotcha #2)

1. **THIS BRIEF end-to-end.**
2. **`docs/pattern-observation-pool-widening-commissioning-brief.md` END-TO-END** -- the governing scope. **Sec 10 is the operator-LOCKED triage (D1-D6); Sec 4 Q4/Q5 are the OPEN brainstorm work; Sec 3 is the grounded architecture; Sec 2 is the in/out-of-scope contract.** Where this brief and the commissioning brief agree, both bind; if they ever disagree, the commissioning brief's Sec 10 locks win and you flag the discrepancy.
3. **The two pipeline steps (the surface of this change):**
   - **`_step_pattern_detect`** -- `swing/pipeline/runner.py:1439`. **The pool predicate: `runner.py:1531-1533`** (`aplus_tickers = [c.ticker for c in candidates if c.bucket == "aplus"]`). The **#27 empty-pool audit: `runner.py:1535-1550`** (field `actual_aplus_pool` at `:1547`; log "zero aplus tickers" `:1536-1538`). The **FeatureDistributionLog universe context: `runner.py:1615-1623`** (`universe_size = len(aplus_tickers)` `:1616`; `stage_2_pass_rate: 1.0  # aplus bucket implies Stage 2 pass` `:1617`). The detect loop: `:1665` (`for ticker in aplus_tickers`). The Pass-2 candidate lookup: **`runner.py:2071`** (`candidate_by_ticker = {c.ticker: c for c in candidates}` -- built from ALL candidates, not just aplus). The event build: **`runner.py:2293-2310`** (`PatternDetectionEvent(... source='pipeline', finviz_screen_state=build_finviz_screen_state(cand) :2301, ...)`; `cand = candidate_by_ticker.get(ticker)` `:2209`).
   - **`_step_pattern_observe`** -- **`swing/pipeline/runner.py:2503-2564`**. Reads `list_observable_detections(read_conn, source="pipeline", observation_date=...)` (`:2525-2526`) -- **ALL pipeline detections regardless of bucket**; per-open-detection bar lookup `:2544` + idempotent already-observed-today guard `:2542-2543` + **#27 no-bar-for-date warning `:2546-2550`** + empty-pool warning `:2532-2537`. NOTE: the observe step has NO bucket predicate -- it observes every open pipeline detection. So widening DETECT automatically scales OBSERVE (no observe predicate change needed; the load grows as a CONSEQUENCE).
4. **The provenance emitter (the grounded D4 finding):** **`swing/pipeline/temporal_metadata.py:119-127`** -- `build_finviz_screen_state(candidate)` ALREADY serializes `{"bucket": candidate.bucket, "rs_rank": ..., "rs_method": ..., "criteria": {...}}`. Since `candidate_by_ticker` (`runner.py:2071`) is built from ALL candidates, a widened pool's watch detections auto-tag `"bucket": "watch"` with **ZERO new provenance code**. **D4 is satisfied by construction -- the brainstorm CONFIRMS this (with a discriminating test), it does not build it.**
5. **The bucket semantics (the grounded Stage-2 finding):** **`swing/evaluation/scoring.py:13-39`** (`bucket_for`): `aplus` = risk-pass + TT-gate-pass + ZERO vcp fails; `watch` = risk-pass + TT-gate-pass + 1-2 vcp fails; `skip` = risk-fail OR TT-gate-fail OR 3+ vcp fails. **CONSEQUENCE: both aplus AND watch PASS the Trend-Template/Stage-2 gate** -- they differ only in VCP-tightness. So the FeatureDistributionLog `stage_2_pass_rate: 1.0` invariant (`runner.py:1617`) **REMAINS TRUE** for the widened aplus+watch pool (no correctness break); only `universe_size` (`:1616`) + the inline comment need updating. (This is an Expansion #8 unit-audit point -- state it explicitly in the spec.)
6. **The schema (confirm NO change):** `swing/data/migrations/0022_phase14_temporal_log.sql` -- append-only `pattern_detection_events` (the `source` enum `{pipeline, v2_cohort, d2_baseline, backfill, synthetic}`; nullable `finviz_screen_state` JSON; **NO bucket column** -- the bucket rides in that JSON per D4) + `pattern_forward_observations` (the `ohlc_today_json` LOCK-at-observation that neutralizes #26/#37). The observe scan is served by `idx_pde_source_data_asof`.
7. **The empirical funnel:** `research/studies/finviz-pool-binding-constraints.md` -- aplus = 0.25% (3 on the snapshot), watch = 20.6% (249), skip = 74.3% (898); the dominant blockers (`proximity_20ma` 44%, `ma_stack` 13%, `TT2` 12%) are trend/VCP-quality, NOT capital criteria (`risk_feasibility` 2.3%). This is WHY widening the OBSERVED pool (not the price/risk band) adds learning data. **The brainstorm MEASURES the live numbers; the study's snapshot is non-binding context.**
8. **`docs/orchestrator-context.md`** -- the "Pre-Codex review + brief-authoring disciplines" (the Expansion #N catalog: esp. #2 signature-verify, #4 SQL-skeleton-column-verify, #6 content-completeness, #8 per-counter UNIT audit -- directly relevant to the #27 audit field + the universe-context semantics).
9. **Memory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`: `feedback_orchestrator_qa_implementer_product`, `feedback_await_return_before_qa`, `feedback_no_false_green_claim`, `feedback_verify_regression_test_arithmetic` (compute the test value under BOTH the aplus-only and aplus+watch paths to prove the test distinguishes), `feedback_codex_round_limit_suspended`, `feedback_wsl_native_codex_invocation`, `feedback_implementer_persist_codex_responses`, `project_applied_research_arc_2026-05-27`.

---

## §1 Pre-locked decisions + LOCKs (BINDING -- from the commissioning brief Sec 10, operator triage 2026-06-03)

These are LOCKED by the operator at commissioning. The brainstorm propagates them into the spec; deviations require a return-trip to the operator.

- **L1 (scope) -- D1.** Widen the `_step_pattern_detect` pool predicate from `bucket == 'aplus'` to `bucket IN ('aplus','watch')` (and the consequent observe-load scaling) ONLY. NO trade-management, sizing, bucket-assignment, or recommendation-engine change. NO Finviz-screen change. NO beyond-Finviz universe net (that is a SEPARATE larger future commissioning, explicitly out of scope). NO new operator-facing surface that reads the widened log (no consumer exists -- Sec 3 of the commissioning brief). NO historical backfill (V1 is forward-walk only, from ship date, per the append-only invariant). The risk-budget / `#3`-hypothesis discussion from the originating session is PARKED, out of scope.
- **L2 (pool) -- D3.** Pool = `aplus + watch`. **NOT** `+ skip` (skip is 74% of the pool but is mostly trend-template failures -- low-signal, much higher cost).
- **L3 (provenance + NO schema) -- D4.** Bucket provenance rides in the EXISTING `finviz_screen_state` JSON (already emits `"bucket"` per §0.4). **NO schema change; NO migration; v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24.** No first-class `source_bucket` column for V1 (there is no consumer surface yet; if a future consumer needs indexed filtering, that column is a follow-on, NOT this sub-bundle).
- **L4 (observe-load) -- D5: ACCEPT-AND-MEASURE.** The brainstorm **MEASURES** the widened observe-step runtime + bar-fetch volume (and the detect-step delta). A cap / sampling / shorter watch-origin observation window is introduced **ONLY** if the measurement crosses an operator-set threshold, and **ONLY** with a gotcha-#27 `warnings_json` audit accounting for every dropped/sampled detection. **A silent cap is FORBIDDEN.** Default posture: no cap in V1 unless the measurement forces the operator's hand.
- **L5 (invariants).** The Schwab **L2 LOCK** is untouched (zero new Schwab API calls). The **append-only invariant** + the `ohlc_today_json` **LOCK-at-observation** are preserved (no re-fetch/regeneration of locked facts). The yfinance OHLCV-fetch-scope discipline holds (watch tickers are evaluated upstream -> their bars are already in the shared cache/archive; quantify the net-new fetch).
- **L6 (Codex) -- D6.** SINGLE Codex chain per phase, run to convergence.

---

## §2 Spec scope to design

### §2.1 The pool predicate + the #27 audit + the universe-context (mechanical; design the details)
- The predicate change at `runner.py:1531-1533` (`c.bucket == "aplus"` -> `c.bucket in ("aplus", "watch")`). Decide the variable naming: keep `aplus_tickers` (now misleading) vs rename to a pool-neutral name (e.g. `pool_tickers` / `detect_pool_tickers`) -- the name appears at `:1531, :1616, :1665, :1830, :1832`. Recommend a rename for honesty; state the touched lines.
- The **#27 empty-pool audit (`runner.py:1535-1550`)**: the field `actual_aplus_pool` (`:1547`) + the log string "zero aplus tickers" must reflect the WIDENED pool. Design the audit shape -- e.g. `actual_pool` with a per-bucket breakdown (`{"aplus": N, "watch": M}`), or keep `actual_aplus_pool` + add `actual_watch_pool`. Keep the empty-pool audit ACCURATE (Expansion #8: state what each counter counts).
- The **FeatureDistributionLog universe context (`runner.py:1615-1623`)**: `universe_size = len(aplus_tickers)` -> the widened count. **`stage_2_pass_rate: 1.0` STAYS CORRECT** (both buckets are Stage-2 passers per §0.5 / `scoring.py:13-39`) -- update the inline comment to "aplus|watch buckets imply Stage 2 pass". Decide whether the FeatureDistributionLog should distinguish the aplus vs watch sub-populations (recommend: NO for V1 -- it is a single detector-universe snapshot; flag as a V2 candidate).

### §2.2 The observe-load measurement + bound (D5 / L4 -- THE SUBSTANCE)
- **Design the measurement methodology.** On a representative candidate set (the study snapshot: ~3 aplus vs ~249 watch -> ~83x), measure/model: (a) the detect-step runtime delta (~83x detector invocations/night = zigzag window-gen + 5 detectors + template-match Pass 2, on cached bars -> CPU not network); (b) the observe-step per-night load (~83x more OPEN detections, each getting a daily bar-lookup sustained across its `observe_max_pending_window_sessions` + `observe_max_post_trigger_window_sessions` window); (c) the **net-new OHLCV fetch** (watch tickers are evaluated upstream so largely cached at `window_days=400` -- QUANTIFY the cache-hit assumption; gotcha "return full archive / consumers slice").
- **Design the cap-policy mechanism + its #27 audit shape** EVEN IF V1 ships no cap (so the operator can flip it on without a re-architecture): WHERE a cap/sample/shorter-watch-window would sit, the threshold knob (likely a `cfg.pipeline.*` setting), and the exact `warnings_json` accounting entry it would emit (expected vs observed pool, dropped count, reason). Default V1 = no cap (accept-and-measure).
- State the acceptance criterion the operator will judge at writing-plans (e.g. "nightly pipeline runtime delta < X min AND net-new fetch < Y calls -> accept uncapped").

### §2.3 Q4 -- idempotency / partial-retry under the wider pool
- Confirm the SELECT-then-INSERT idempotency (`runner.py:1724` Pass-1 skip + `:1859-1903` Pass-2 reconcile) + the per-run composite-score histogram seed behave correctly at ~83x population.
- Reason about **watch tickers that flip bucket across same-day re-runs** (the finviz study documents per-day pipeline re-runs). The detection unique index is `(source, ticker, detection_date, pattern_class)` -- **bucket-agnostic** -- so a re-run is idempotent regardless of bucket. BUT `finviz_screen_state` is LOCKED at the FIRST detection (append-only): if a ticker is `watch` in run 1 and `aplus` in run 2, the locked provenance reflects run 1. Decide: is first-detection-wins the correct V1 semantic (recommend YES -- it matches the append-only forward-walk invariant)? Add a discriminating test (plant a bucket flip across two same-day runs; assert one row, first bucket locked).

### §2.4 Q5 -- pattern-outcomes tile isolation
- Confirm (re-grep `swing/web/` + `swing/metrics/pattern_outcomes.py`) that the exemplar-driven 9th metric tile reads `pattern_exemplars` (by `label_source`/`final_decision`), NOT `pattern_detection_events`/`pattern_forward_observations` -> **uncontaminated by construction** (there is NO current consumer of the widened log). State the grep result in the spec.
- Decide whether any FUTURE consumer of the widened log should DEFAULT to aplus-only with watch as an opt-in filter (design-forward hygiene; likely a documented recommendation, not V1 code).

### §2.5 Test + gate strategy
- The test rework: the existing detect/observe + temporal e2e fixtures assume aplus-only (enumerate them at brainstorm via grep; the writing-plans phase will pin exact files). Per `feedback_verify_regression_test_arithmetic`: each new/changed test must distinguish the aplus-only path from the aplus+watch path (compute the asserted count under BOTH).
- The provenance confirmation test (a watch detection's `finviz_screen_state` carries `"bucket":"watch"`).
- The bucket-flip idempotency test (§2.3).
- The #27 audit-accuracy test (the widened-pool empty + the cap-path, if any).
- **The pre-merge gate (design it -- OQ-4).** This arc has NO UI surface (no browser gate) and NO schema (no live-DB migration gate). The candidate gate is: orchestrator QA + the observe-load MEASUREMENT presented to the operator at writing-plans + a controlled pipeline-step smoke (test/isolated DB, NOT the operator's live nightly DB) -- and OPTIONALLY an operator-witnessed first live `swing pipeline run` post-merge to confirm acceptable real runtime (lighter than the schwabdev/b7 live gates -- append-only, low blast radius, no schema change). Propose the gate shape; the operator confirms at writing-plans.

---

## §3 Open questions (Codex surfaces; operator triage at writing-plans)
1. **OQ-1 (observe-load cap policy)** -- accept-and-measure with NO cap in V1 (D5 default; recommend, pending the measurement) vs pre-commit to a cap/sampling/shorter watch-origin window. **Operator-binding** (gated on §2.2's measured numbers).
2. **OQ-2 (universe-context semantics)** -- keep the single detector-universe FeatureDistributionLog snapshot (recommend) vs split aplus/watch sub-populations. Confirm `stage_2_pass_rate: 1.0` stays (it does -- §0.5).
3. **OQ-3 (#27 audit field naming)** -- `actual_aplus_pool` -> `actual_pool` + per-bucket breakdown (recommend) vs keep + add `actual_watch_pool`. (Back-compat: is any downstream reader keyed on the `actual_aplus_pool` field name? grep.)
4. **OQ-4 (pre-merge gate shape)** -- controlled measurement + step-smoke only (recommend) vs an operator-witnessed first live pipeline run for runtime acceptance.
5. **OQ-5 (future-consumer default)** -- document "future log consumers default aplus-only, watch opt-in" as forward hygiene (recommend) vs no statement. (No V1 code either way -- no consumer.)
6. **OQ-6 (variable rename)** -- rename `aplus_tickers` -> pool-neutral (recommend) vs keep the now-misleading name.

---

## §4 OUT OF SCOPE (do not design into V1)
- Any ruleset / trade-management / sizing / bucket-assignment / recommendation-engine change (L1).
- Any Finviz-screen change; any beyond-Finviz universe net (separate future commissioning).
- A schema change / migration / the v25 `source_bucket` column (D4 ruled it out -- JSON only; v24 holds).
- The `skip` bucket (D3 -- aplus+watch only).
- A new operator-facing surface that reads the widened log (no consumer; building one is a follow-on).
- Historical backfill of watch detections (forward-walk only).
- The risk-budget / `#3` hypothesis discussion (parked).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **L3 NO schema** -- the design adds NO migration; `EXPECTED_SCHEMA_VERSION` stays 24; the bucket provenance rides in the EXISTING `finviz_screen_state` JSON (D4 is confirmed-by-construction, not built).
2. **#27 audit accuracy** -- the widened-pool empty-pool audit + any cap path emit an accurate `warnings_json`; NO silent cap (L4); the audit field's UNIT is stated (Expansion #8).
3. **Observe-load is MEASURED, not assumed** (L4/D5) -- the spec carries a real measurement methodology + an operator-judgeable acceptance criterion + a designed (even if dormant) cap mechanism.
4. **Q4 idempotency** -- the bucket-agnostic unique index + first-detection-wins provenance lock are correct under ~83x population + same-day bucket flips; a discriminating test proves it.
5. **Q5 tile isolation** -- the exemplar-driven tile + every `swing/web/` surface is uncontaminated (grep result stated); no present consumer reads the widened log.
6. **L5 invariants** -- Schwab L2 LOCK untouched (zero new Schwab calls); append-only + `ohlc_today_json` LOCK-at-observation preserved; OHLCV-fetch-scope / write-through-archive gotchas (#24/#26/#28/#29) respected at the widened scale.
7. **`stage_2_pass_rate` correctness** -- the `1.0` invariant genuinely holds for watch (both buckets are Stage-2 passers per `scoring.py:13-39`); the comment is updated, not just the variable.
8. **Test arithmetic distinguishes** (`feedback_verify_regression_test_arithmetic`) -- each test value computed under BOTH the aplus-only and aplus+watch paths.
9. ASCII discipline on all new text (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape
**Design spec at `docs/superpowers/specs/2026-06-04-pattern-observation-pool-widening-design.md`** (mirror the prior brainstorm spec format): §1 Architecture overview (the funnel + the one-predicate trigger + why the substance is elsewhere) · §2 Pre-locked decisions + L1-L6 (from D1-D6) · §3 The pool predicate + #27 audit + universe-context · §4 The observe-load measurement + bound + the (dormant) cap mechanism · §5 Q4 idempotency-under-the-wider-pool · §6 Q5 tile-isolation · §7 Test + gate strategy · §8 Schema impact (NONE -- v24 holds; D4) · §9 Slice recommendation · §10 V1 simplifications + V2 candidates (the v25 `source_bucket` column; a future log-consumer surface; aplus/watch FeatureDistributionLog split) · §11 Operator decision items (OQ-1..OQ-6) · §12 Cumulative discipline compliance · §13 Position note (a standalone Phase-15 B-family sub-bundle; the cleanest expression of "decouple data-generation from capital").

**Target ~350-500 lines.** Commit stem: `docs(pool-widening-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`).

---

## §7 If you get stuck
- If a cited file:line no longer matches the live tree, TRUST the tree + re-grep (record the corrected anchor in the spec for writing-plans).
- If the design seems to need a SCHEMA change (a `source_bucket` column), STOP -- D4/L3 ruled it out; the bucket rides in the existing `finviz_screen_state` JSON (confirm the emitter at `temporal_metadata.py:119-127`). The v25 column is an explicit V2 follow-on.
- If the design seems to need a ruleset / sizing / bucket-assignment / recommendation / Finviz change, STOP -- L1; this is an OBSERVATION-substrate widening only.
- If the observe-load measurement shows an UNACCEPTABLE cost, do NOT silently cap -- design the cap mechanism + its #27 audit and surface OQ-1 to the operator (L4/D5).
- If `skip` looks tempting, STOP -- D3 locked aplus+watch only.
- HOLD THE LINE: aplus+watch (not skip); NO schema (JSON provenance); accept-and-measure with NO silent cap; the Schwab L2 LOCK + the append-only / LOCK-at-observation invariants survive; the substance is the observe-load bound + provenance confirmation + test rework, NOT the predicate.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix + stdin form (verify `codex --version` first).
- This is BRAINSTORMING ONLY -- the design spec + OQs; do NOT write production code, do NOT enter writing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `pattern-observation-pool-widening-brainstorming`. Dir `.worktrees/pattern-observation-pool-widening-brainstorming/`. **Branch from main HEAD = the commit that ADDS this brief** (the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief AND the commissioning brief). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. **NO live-DB concern** -- this arc adds no migration; do NOT run a connecting `swing pipeline`/`swing` command against the operator's live DB during brainstorm (brainstorm writes a SPEC, not code).
- **Codex chain count:** SINGLE chain at end (D6), run to convergence via the WSL prefix + stdin form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior brainstorm return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict` / `NO_NEW_CRITICAL_MAJOR`); spec line count + per-section; L1-L6 verbatim verification; the OQs resolved/deferred (flag OQ-1 [cap policy] + OQ-4 [gate shape] for the operator); the **schema verdict (NONE -- v24 holds; D4)**; the **D4 provenance-by-construction confirmation** (the `build_finviz_screen_state` finding + the planned discriminating test); the **observe-load measurement methodology** + the acceptance criterion + the dormant-cap design; the Q4 idempotency reasoning + the bucket-flip test; the Q5 tile-isolation grep result; Codex Majors accepted (ZERO preferred); V1 simplifications + V2 candidates; the L5 invariant confirmations (Schwab L2 LOCK + append-only + LOCK-at-observation); cumulative gotcha application (#27/#28/#29/#24/#26 + Expansion #8); ZERO Co-Authored-By confirmation; worktree teardown status; writing-plans dispatch-readiness.

---

*End of brief. Pattern-observation pool-widening brainstorming dispatch (a standalone Phase-15 B-family sub-bundle) -- design how to widen the nightly pattern detect/observe pool from `bucket=='aplus'` to `aplus+watch` so the Phase-14 temporal observation log accumulates ~83x more forward-walk learning data at ZERO capital risk, ZERO Finviz change, and ZERO schema change (D4 -- the bucket rides in the existing `finviz_screen_state` JSON, already emitted by construction). The substance is the observe-load bound (accept-and-measure; NO silent cap -- #27) + the Q4 idempotency-under-the-wider-pool + the Q5 tile-isolation + the test rework -- NOT the one-line predicate. NOT a ruleset/sizing/bucket/recommendation/Finviz change; NOT a beyond-Finviz net; NOT a new surface. OUTPUT: a design spec the writing-plans phase can derive a plan from.*
