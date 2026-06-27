# Pattern-Observation Pool Widening (aplus -> aplus+watch) -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the pattern-observation-pool-widening writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan for a standalone **Phase-15 strategic-backlog (B-family)** sub-bundle: widen the nightly `_step_pattern_detect`/`_step_pattern_observe` pool from `bucket=='aplus'` to `bucket IN ('aplus','watch')` so the Phase-14 temporal observation log accumulates the ~83x watch population as forward-walk data -- **at ZERO capital risk, ZERO Finviz-screen change, and ZERO schema change.** The predicate is one line; the SUBSTANCE is the observe-load bound + the sibling-`pattern_evaluations` consumer isolation + idempotency + the test rework.

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-06-04-pattern-observation-pool-widening-design.md` (796 lines; merged to main `a45d3bc4`; single WSL Codex chain CONVERGED R5 `NO_NEW_CRITICAL_MAJOR` after R1[4maj]->R2[3maj]->R3[2maj]->R4[2maj]->R5). Execute its design verbatim; **re-grep every cited file:line at writing-plans STEP 0** (the spec cites the base HEAD `32132654`; line numbers shift -- discipline #2).

**Brief:** `docs/pattern-observation-pool-widening-writing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; THREE Phase-15 arcs CLOSED (schwabdev-v3 `#20`, B-7 `#21`, PGT-redesign `#22`); this arc's brainstorm SHIPPED+merged `a45d3bc4`. main HEAD at this dispatch: see §8 (branch from it). ~7105 fast tests green; **schema v24**. This arc adds **NO migration, NO schema change, NO lock change (Schwab L2 untouched), NO isolated venv (no shared-dep change), NO live cutover** -- but it DOES change what the nightly pipeline writes to the live DB (forward-walk watch detections), so the executing-plans gate includes an operator-witnessed first-live-run (§1.2 / OQ-4).

**Cumulative discipline:** the CLAUDE.md **Pattern-detector** gotchas are BINDING -- **#27** (silent-skip-without-audit: NO silent cap; both dormant levers + the empty-pool path emit accurate `warnings_json`), **#28/#29** (exemplar OHLCV -- less acute; watch is in-universe), **#24/#26** (archive freshness -- neutralized by the `ohlc_today_json` LOCK-at-observation; confirm for rotated-out watch tickers); the **yfinance** OHLCV-fetch-scope + write-through-archive gotchas; **#9/#11** N/A (no migration/schema-CHECK); `feedback_verify_regression_test_arithmetic` (each test's value computed under BOTH states of the change it guards -- and the discriminating AXIS DIFFERS per test, spec Sec 7.1); ~700+ ZERO Co-Authored-By; **Schema v24 UNCHANGED.**

**Expected duration:** ~3-4 hours writing-plans + a Codex chain to convergence. Plan line target **~700-1000 lines** (3 slices, the provable-aplus-ladder SQL, the measurement harness, the dormant levers).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the spec.
- **Codex chain count: SINGLE chain** at end (D6). **Run to CONVERGENCE** (zero new criticals AND zero new majors; `NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED (a bare invocation resolves the DEAD Windows shim, no node). PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). **Pass the prompt via STDIN, NOT command-substitution** -- `cat prompt.txt | codex exec -s read-only --skip-git-repo-check -` (the trailing `-` reads stdin); `"$(cat prompt.txt)"` breaks on parentheses/multiline. Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`; the Codex output is large + may carry non-ASCII -- extract the tail to a file to Read (do NOT `print()` it -- the cp1252 stdout crash, #16/#32). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/2026-06-04-pattern-observation-pool-widening-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end** -- esp. §1 (the LOCKs + the operator-triage-at-writing-plans items) + §3 (slices + the SEQUENCING CONSTRAINT).
2. **The SPEC** (`...pool-widening-design.md`, 796 lines) -- AUTHORITATIVE. Especially: §3 (predicate + the #27 standardized-audit vocabulary + the rename anchors + provenance-by-construction); §4 (the observe-load model + the acceptance criterion + the TWO dormant levers -- Lever 1 detect-pool cap [future-relief] vs Lever 2 observe pre-fetch shed [immediate-relief, no-expiry]); §5 (Q4 idempotency + first-detection-wins); **§6 (consumer isolation -- the provable-aplus LADDER, the historical gate, the filter-before-LIMIT, the KEPT backlinks)**; §7 (the 8 test surfaces + their per-test discriminating axis + the pre-merge gate); §9 (the 3 slices + the sequencing constraint); §11 (the OQ log).
3. **The surface anchors (re-grep at writing-plans STEP 0 -- the spec cites base `32132654`):** `_step_pattern_detect` (`swing/pipeline/runner.py:~1439`; the predicate `:~1531-1533`; the #27 empty-pool audit `:~1535-1550` field `actual_aplus_pool`; the FDL universe-context `:~1615-1623`; the detect loop `:~1665`; the Pass-2 `candidate_by_ticker` `:~2071`; `insert_evaluation` `:~2195`; the detection-event build + `build_finviz_screen_state(cand)` `:~2293-2310`); `_step_pattern_observe` (`:~2503-2564`; `list_observable_detections(source="pipeline")` `:~2525`; `_bar_for_date` `:~2427`); the provenance emitter `swing/pipeline/temporal_metadata.py:119-127`; `bucket_for` `swing/evaluation/scoring.py:13-39`; the consumers (spec §6.2 table): `swing/metrics/pattern_outcomes.py:~100/200`, `swing/web/view_models/patterns/review_form.py:~340-369`, `swing/patterns/active_learning.py:~243`, + the KEEP backlinks (`web/view_models/dashboard.py`, `web/view_models/trades.py`, `web/routes/trades.py`, `trades/entry.py`, `web/view_models/journal.py`, `data/repos/pattern_evaluations.py`); migration `0022_phase14_temporal_log.sql` (append-only; the unique index `:50-51`; `finviz_screen_state` `:36`) + `0020_*` (`pattern_evaluations`; the `ON DELETE CASCADE` `pipeline_run_id`); `EXPECTED_SCHEMA_VERSION` `swing/data/db.py:51` (STAYS 24).
4. **CLAUDE.md -- the Pattern-detector gotchas** (#27 silent-skip; #28/#29 exemplar OHLCV; #24/#26 archive freshness) **+ the SQLite cluster** (the `IN`-clause `?`-expansion; the `... or None` CHECK-nullability) **+ the ASCII #16/#32** (every new log/warning/`cfg`-help string) AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. Expansion #2 signature-verify, #4 SQL-skeleton-column-verify, #8 per-counter UNIT audit).
5. **Memory:** the WSL Codex transport (+ stdin-pipe) + persist-responses + round-limit-suspended + trailer-hazard + `feedback_verify_regression_test_arithmetic` + `feedback_no_false_green_claim` (re-run the suite on the MERGED HEAD; isolate the known xdist co-residency flakes).

---

## §1 LOCKed decisions (BINDING -- DO NOT re-litigate) + the operator-triage-at-writing-plans items

### §1.1 Inherited LOCKs (spec §2 / L1-L6; BINDING)
- **L1 (scope)** widen the detect predicate to `aplus+watch` (+ the consequent observe scaling) + the consumer isolation that keeps it invisible to operator-facing surfaces ONLY. NO ruleset / sizing / bucket-assignment / recommendation / Finviz change. NO beyond-Finviz net. NO new operator-facing surface that READS the widened log. NO historical backfill (forward-walk from ship date).
- **L2 / L3 (pool + provenance + NO schema)** pool = `aplus+watch` (NOT skip). Bucket provenance rides in the EXISTING `finviz_screen_state` JSON (already emits `"bucket"` -- spec §3.4; confirm by test, do NOT build). **NO migration; `EXPECTED_SCHEMA_VERSION` stays 24; no `source_bucket` column.**
- **L4 (observe-load) ACCEPT-AND-MEASURE** -- V1 ships UNCAPPED; both relief levers ship DORMANT (cfg knobs default `None`). A cap is activated ONLY post-measurement past an operator threshold, ONLY with a #27 audit. **A silent cap is FORBIDDEN.**
- **L5 (invariants)** Schwab **L2 LOCK** untouched (zero new Schwab calls). Append-only + `ohlc_today_json` LOCK-at-observation preserved. The yfinance OHLCV-fetch-scope discipline holds.
- **L6 (Codex)** SINGLE chain per phase, run to convergence.

### §1.2 Operator-triage AT writing-plans (spec §11 -- operator-pair these; the resolutions LOCK into the plan)
| OQ | Spec resolution to confirm operator-paired |
|----|--------------------------------------------|
| **OQ-1 cap policy** | V1 UNCAPPED + the dormant mechanism designed (both levers, knobs default `None`). Confirm the **acceptance-criterion SHAPE** (spec §4.3: accept-uncapped iff runtime delta < operator budget AND steady-state net-new fetch < the `OhlcvCache` breaker thresholds). The actual numbers + the accept-or-cap decision land at the executing-plans measurement / first-live-run gate. |
| **OQ-4 pre-merge gate** | The 4-part gate (spec §7.2): orchestrator QA + the observe-load measurement presented to the operator + an isolated step-smoke (seeded test DB, NOT the live DB) + an operator-witnessed first live `swing pipeline run` post-merge. Confirm. |
| **OQ-7 backlink exception** | The 3 silent-aggregate/queue consumers are ISOLATED to aplus-origin; the by-ticker/by-id trade backlinks are KEPT (spec §6.4 -- blanket isolation would break legitimate watch-ticker trade linkage). Confirm the KEEP exception (the alternative -- literal isolation -- additionally requires deciding watch-ticker trade-anchor behavior). |

---

## §2 Production anchors + risks (BINDING; re-grep at writing-plans STEP 0)
- **The predicate + the rename (spec §3.1).** `c.bucket == "aplus"` -> `c.bucket in ("aplus","watch")`; rename `aplus_tickers` -> `detect_pool_tickers` at EVERY reference (the spec §3.1 table lists ~7 sites incl. log strings; re-grep `aplus_tickers` for the live set). The FDL `stage_2_pass_rate: 1.0` STAYS CORRECT (both buckets pass Stage 2 -- `scoring.py:13-39`); update the INLINE COMMENT too (not just the variable).
- **The #27 audit standardized vocabulary (spec §3.2 -- a Codex MAJOR closed a per-key unit conflict).** The SAME keys/units in BOTH the empty-pool audit AND the dormant Lever-1 audit: `expected_pool` (total candidate rows), `expected_detect_pool` (aplus+watch pre-cap), `expected_pool_by_bucket`, `actual_pool` (entering the loop, post-cap), `actual_pool_by_bucket`, `dropped_count` (cap path). REMOVE `actual_aplus_pool` -- the ONLY reader is one test (`tests/pipeline/test_step_pattern_detect_temporal_extension.py:~195`), updated in the same task. Lever-2 (observe shed) uses a DISTINCT `pattern_observe` entry keyed on `shed_count`+`reason` (a different unit -- do NOT reuse the detect-pool keys).
- **The consumer isolation -- the provable-aplus LADDER (spec §6.3; THE substance; pin the EXACT SQL).** `pattern_evaluations` has NO bucket column (D4 forbids one). Reach the bucket by a PROVABLE ladder, in order: (1) fast path `candidates.bucket='aplus'` (join PE->pipeline_runs->candidates on ticker+evaluation_run_id); (2) robust path the LOCKED bucket in `pattern_detection_events.finviz_screen_state` (join PE->PDE on pipeline_run_id+ticker+pattern_class, require JSON bucket==`aplus`); (3) **MANDATORY historical gate** -- a pre-widen PE with neither candidate nor PDE is aplus BY CONSTRUCTION; INCLUDE iff its run is **strictly before the FIRST widened pipeline run** (define the boundary by the first widened `pipeline_run_id`/`finished_ts`; date fallback only for legacy rows); (4) otherwise (post-widen, unprovable) EXCLUDE. **A naive `OR c.id IS NULL` is UNSOUND (Codex R2 -- leaks future watch rows on candidate deletion).** Apply the ladder INSIDE the review-form B.4 cohort CTE BEFORE `ORDER BY pe.id DESC LIMIT ?` (Codex R4 -- filter-before-LIMIT, else the cohort silently SHRINKS). The leak vector is CANDIDATE LOSS (PE `pipeline_run_id` is `ON DELETE CASCADE`, so run-pruning removes PEs entirely -- no orphan-PE vector); steps 2-4 handle it.
- **The 3 isolated consumers** (spec §6.2): pattern-outcomes tile reached-1R/hit-stop DENOMINATOR (`pattern_outcomes.py:~100`); review-form B.4 cohort (`review_form.py:~343`); active_learning queue (`active_learning.py:~243`). **The KEPT backlinks** (by-ticker/by-id; spec §6.2 table + §6.4) are NOT filtered.
- **Q4 first-detection-wins (spec §5.2).** The unique index is bucket-agnostic; on a same-day bucket flip run 2 SKIPS the detection-event append (the SELECT-then-skip) and does NOT rewrite the LOCKED `finviz_screen_state`. (Run 2 MAY still write a per-run `pattern_evaluations` row -- that is acceptable; first-detection-wins applies to the LOCKED detection facts, not the per-run PE verdict.)
- **The dormant levers (spec §4.4).** Lever 1 `cfg.pipeline.detect_watch_pool_cap: int|None=None` (a DETERMINISTIC selection rule -- e.g. rank watch by `rs_rank` asc, top N -- NOT random). Lever 2 `cfg.pipeline.observe_max_*_window_sessions_watch: int|None=None` -- a PRE-FETCH SKIP (NOT an `expired` transition: a no-fetch expiry is impossible without a schema change since `ohlc_today_json` is NOT NULL); a regression asserts repeated runs do NOT re-fetch the shed detections. NO per-night observe COUNT cap in V1 (it would starve later detections -- deferred to V2 with a fairness rule).
- **The observe-load measurement (spec §4.2).** A PLAN TASK that builds the instrumentation (a counter/probe around `_bar_for_date` distinguishing cache-hit in-pool watch vs net-new rotated-out fetch; #27-compliant). It RUNS at executing-plans on a seeded/isolated DB (NOT during writing-plans, which is plan-only); the numbers + the accept-uncapped decision are presented at the gate (OQ-4). **Do NOT run a connecting `swing pipeline` against the operator's live DB at any dev phase** -- seeded test/isolated DB only.

---

## §3 Slice structure (from spec §9; the plan decomposes into TDD tasks) -- WITH the sequencing constraint
Three slices. **THE BINDING SEQUENCING CONSTRAINT (spec §9):** Slice 2 (consumer isolation) MUST land WITH or BEFORE Slice 1's widen behavior reaches the live pipeline -- otherwise the first widened run silently shifts the tile/cohort/queue. The plan SHOULD order isolation FIRST (the widen stays dark until the surfaces are protected), OR make Slice 1 + Slice 2 a single atomic landing. State the chosen ordering + WHY it satisfies the constraint.
- **Slice 1 -- the widen + audit + rename + provenance confirmation.** The predicate widen; the `aplus_tickers`->`detect_pool_tickers` rename (all sites); the #27 audit reshape (standardized vocabulary); the `stage_2_pass_rate` comment update; the FDL `universe_size` rename. Tests: detect-pool widen (count==A+W > A); provenance-by-construction (a watch detection's `finviz_screen_state` carries `"bucket":"watch"`); bucket-flip idempotency (first-detection-wins -> 1 row locked `watch`); #27 audit-accuracy (widened-empty pool -- the field-name/shape is the discriminator).
- **Slice 2 -- consumer isolation (the invisible-widen requirement, spec §6).** The provable-aplus ladder applied to the 3 silent consumers; KEEP the backlinks. Tests: per-consumer pre/post-isolation (widen does NOT change the displayed count vs the aplus-only baseline); the 2 ladder-edge regressions (post-rollout watch PE with a DELETED candidate -> EXCLUDED; pre-rollout historical aplus PE with neither candidate nor PDE -> INCLUDED); the cohort filter-before-LIMIT regression; the backlink-KEEP test (enter a trade on a watch ticker -> the PE-anchor resolves NOT None).
- **Slice 3 -- the dormant relief levers + the observe-load instrumentation.** The two cfg knob families (both default `None`); both #27 audit shapes; the observe-load measurement probe + the observe-scaling tests. Tests: dormant-lever audit-accuracy (both levers); observe-scaling + the net-new-fetch counter; repeated-runs-no-refetch for the shed.

---

## §4 OUT OF SCOPE (do not plan into V1)
- Any ruleset / sizing / bucket-assignment / recommendation / Finviz change (L1).
- A schema change / migration / the `source_bucket` column (L3 -- v24 holds).
- The `skip` bucket; a beyond-Finviz universe net; a new operator-facing surface that reads the widened log; historical backfill.
- An ACTIVE cap (V1 dormant only); a per-night observe COUNT cap (V2 -- needs a fairness rule); an aplus/watch FeatureDistributionLog split (V2).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **L3 NO schema** -- no migration; `EXPECTED_SCHEMA_VERSION` stays 24; the provenance rides in the existing JSON (D4 confirmed-by-construction, not built).
2. **The sequencing constraint (spec §9)** -- the plan orders/atomizes Slice 2 so the widen NEVER reaches the live pipeline before the 3 consumers are isolated; stated + justified.
3. **The provable-aplus ladder is SOUND** -- the 4 steps in order; NO `c.id IS NULL` leak; the mandatory historical gate (strictly-before-first-widened-run); the filter-before-LIMIT for the review-form cohort; the 2 ladder-edge regression tests present.
4. **The KEPT backlinks are correct** -- the by-ticker/by-id backlinks are NOT isolated (watch-ticker trade linkage preserved); the backlink-KEEP test discriminates intended-exception vs blanket-isolation.
5. **#27 audit accuracy + UNIT** -- the standardized vocabulary (no per-key unit drift); both dormant levers + the empty-pool path emit accurate `warnings_json`; NO silent cap; each counter's unit stated (Expansion #8).
6. **Q4 first-detection-wins** -- bucket-agnostic unique index + locked provenance under ~83x + same-day flips; the discriminating test locks `watch` on the widened path.
7. **The observe-load measurement is a real executable plan task** (probe + seeded-DB run + the acceptance criterion); the levers are dormant; NO live-DB run at dev time.
8. **L5 invariants** -- Schwab L2 LOCK untouched; append-only + LOCK-at-observation preserved; OHLCV-fetch-scope respected at the widened scale.
9. **Test arithmetic distinguishes (per-axis)** -- each test value computed under BOTH states of the CHANGE it guards; the discriminating AXIS named per test (widen-behavior / audit-shape / pre-post-isolation / intended-backlink-exception) -- spec §7.1.
10. **L2/D4 no schema; ASCII (#16/#32)**; Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §6 Deliverable shape
**Plan at `docs/superpowers/plans/2026-06-04-pattern-observation-pool-widening-plan.md`** (mirror the prior plan format): a 3-slice TDD task list, each task with (a) the failing test (file + assertion + the pre-vs-post value check + the named discriminating axis), (b) the minimal implementation, (c) the commit message stem, (d) the locks/gotchas it touches. Include: the rename-site enumeration; the EXACT provable-aplus-ladder SQL per isolated consumer (re-grepped); the slice-sequencing justification (§3); the observe-load measurement-task definition; the pre-merge gate (§1.2 / OQ-4); a task-count + line estimate (gotcha #1 -- trust the final pytest count, not the estimate). **Target ~700-1000 lines.** Commit stem: `docs(pool-widening-plan): writing-plans <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a spec file:line no longer matches the live tree, TRUST the tree + re-grep (main is now `a45d3bc4`+).
- If the design seems to need a SCHEMA change (a `source_bucket` column), STOP -- D4/L3 ruled it out; the bucket rides in the existing `finviz_screen_state` JSON.
- If the isolation seems to need `OR c.id IS NULL`, STOP -- that is the UNSOUND leak (Codex R2); use the provable-aplus ladder with the mandatory historical gate.
- If the observe-load measurement seems to need a live pipeline run, STOP -- seeded/isolated DB only; the live run is the post-merge operator gate (OQ-4), not a dev step.
- If a relief lever seems to need a per-night observe COUNT cap, STOP -- V1 is window-based (no selection rule, no starvation); the count cap is V2.
- HOLD THE LINE: aplus+watch (not skip); NO schema (JSON provenance); isolation lands with/before the widen reaches live; the provable-aplus ladder (not a NULL fallback); accept-and-measure with NO silent cap; the Schwab L2 LOCK + append-only + LOCK-at-observation survive.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form + STDIN-pipe (verify `codex --version`).
- This is WRITING-PLANS ONLY -- the plan + per-task tests; do NOT write production code, do NOT enter executing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `pattern-observation-pool-widening-writing-plans`. Dir `.worktrees/pattern-observation-pool-widening-writing-plans/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `a45d3bc4`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged spec + the commissioning + brainstorming briefs). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. **NO isolated venv** (no shared-dep change). **NO live-DB touch** -- writing-plans writes a PLAN; do NOT run a connecting `swing pipeline`/`swing` command against the operator's live DB.
- **Codex chain count:** SINGLE chain at end (D6), run to convergence via the WSL prefix + stdin-pipe form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); plan line + task count per slice; the slice-sequencing justification (§3); the 3 operator-triage items reflected (OQ-1/OQ-4/OQ-7 -- their writing-plans-paired resolutions); L1-L6 verification; the provable-aplus-ladder SQL pinned (re-grepped, per consumer); the observe-load measurement-task definition; the pre-merge gate enumerated; the test-arithmetic per-axis confirmation; Codex Majors accepted (ZERO preferred); the schema verdict (NONE -- v24 holds); ZERO Co-Authored-By confirmation; worktree teardown status; executing-plans dispatch-readiness + the slice ordering.

---

*End of brief. Pattern-observation pool-widening writing-plans dispatch (a standalone Phase-15 B-family sub-bundle) -- turn the merged, Codex-converged 796-line spec into a 3-slice TDD plan: Slice 1 the widen + #27 audit reshape + rename + provenance-by-construction confirmation; Slice 2 the sibling-`pattern_evaluations` consumer isolation via the provable-aplus ladder (the Codex-surfaced substance -- isolate the 3 silent aggregate/queue consumers to aplus-origin, KEEP the trade backlinks, filter-before-LIMIT, the mandatory historical gate); Slice 3 the dormant relief levers + the observe-load measurement instrumentation. THE BINDING SEQUENCING CONSTRAINT: isolation lands with/before the widen reaches the live pipeline. NO schema (v24; JSON provenance); accept-and-measure with NO silent cap; the Schwab L2 LOCK + append-only + LOCK-at-observation survive. The pre-merge gate is QA + the observe-load measurement + an isolated step-smoke + an operator-witnessed first live run. OUTPUT: a plan the executing-plans phase can drive to a shipped widen.*
