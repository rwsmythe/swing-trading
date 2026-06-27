# Pattern-Observation Pool Widening (aplus -> aplus+watch) -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the pattern-observation-pool-widening executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged implementation plan -- widen the nightly `_step_pattern_detect`/`_step_pattern_observe` pool from `bucket=='aplus'` to `bucket IN ('aplus','watch')`, keeping the widen INVISIBLE to every operator-facing surface -- via `copowers:executing-plans` (wraps `subagent-driven-development`). TDD task-by-task (failing test -> see fail -> minimal impl -> see pass -> commit), in the STRICT execution order Part A (isolation) -> Part B (widen) -> Part C (levers + measurement) -> Part D (re-baseline + gate). A standalone **Phase-15 strategic-backlog (B-family)** sub-bundle: **NO schema, NO migration, NO lock change, NO isolated venv, NO live-DB touch during dev** (the first-live-run is a POST-merge operator gate, §3).

**Plan (AUTHORITATIVE -- the task contract):** `docs/superpowers/plans/2026-06-04-pattern-observation-pool-widening-plan.md` (1431 lines; 15 TDD tasks across 4 parts; merged to main `a78443ce`; single WSL Codex chain CONVERGED R5 `NO_NEW_CRITICAL_MAJOR`). Execute its tasks verbatim; **re-grep every cited file:line at task start** (the plan re-grepped at HEAD `db2cc378`; line numbers shift -- discipline #2; the plan's §1 anchor table is the starting map).

**Spec (design rationale):** `docs/superpowers/specs/2026-06-04-pattern-observation-pool-widening-design.md` (796 lines) -- consult for the WHY (esp. §4 the observe-load model + the two dormant levers; §6 the consumer-isolation rationale; §6.3 the provable-aplus ladder + the DURABLE detection_date boundary [the brainstorm `pipeline_run_id` boundary was proven UNSOUND at writing-plans -- `ON DELETE SET NULL` leak]).

**Brief:** `docs/pattern-observation-pool-widening-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; THREE Phase-15 arcs CLOSED (`#20`/`#21`/`#22`); this arc's brainstorm + writing-plans SHIPPED+merged (`a45d3bc4`/`a78443ce`). main HEAD at this dispatch: see §7 (branch from it). ~7105 fast tests green on main; schema v24.

**Cumulative discipline:** the CLAUDE.md **Pattern-detector** gotchas BINDING -- **#27** (silent-skip-without-audit: every cap/shed/empty-pool path emits an accurate `warnings_json`; NO silent cap), **#28/#29** (exemplar OHLCV -- less acute; watch is in-universe), **#24/#26** (archive freshness -- the `ohlc_today_json` LOCK-at-observation neutralizes; confirm for rotated-out watch tickers); the **SQLite** cluster (the `IN`-clause `?`-expansion; `... or None` CHECK-nullability; `json_extract` is production-proven); the **Windows cp1252 / ASCII #16/#32** discipline (every new log/warning/`cfg`-help string -- no non-ASCII glyphs); `feedback_verify_regression_test_arithmetic` (each test's value computed under BOTH states of the change it guards; the discriminating AXIS differs per test -- the plan bakes this in); ~700+ cumulative ZERO Co-Authored-By; **Schema v24 UNCHANGED** (NO migration; `EXPECTED_SCHEMA_VERSION` stays 24).

**Expected duration:** a substantive executing-plans cycle (15 tasks, ~12 commits, ~22-30 new tests + 1 updated) + a single Codex chain to convergence at end.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief + the plan.
- **Codex chain count: SINGLE chain** at end (after ALL tasks). **Run to CONVERGENCE** (zero new criticals AND zero new majors; `NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- WSL fallback (MCP DEAD -- do NOT attempt).** USE EXACTLY: `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'` -- the PATH prefix is REQUIRED; PROVE liveness with `codex --version` -> `codex-cli 0.135.0`. **Pass the prompt via STDIN** (`cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`), NOT `"$(cat ...)"` (breaks on parens). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. `### Verdict`) to `.copowers-findings.md`; extract the verdict tail to a file to Read (do NOT `print()` -- cp1252 glyph crash). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.

---

## §1 LOCKed decisions + L1-L6 (BINDING; full detail in the plan §0 / the spec §2)
- **L1 (scope)** widen the detect predicate to `aplus+watch` + the consequent observe scaling + the consumer isolation that keeps it invisible ONLY. NO ruleset/sizing/bucket-assignment/recommendation/Finviz change; NO beyond-Finviz net; NO new operator-facing surface reading the widened log; NO historical backfill.
- **L2/L3 (pool + NO schema)** pool = `aplus+watch` (NOT skip). Provenance rides in the EXISTING `finviz_screen_state` JSON (already emits `"bucket"` -- confirm by test, do NOT build). **NO migration; `EXPECTED_SCHEMA_VERSION` STAYS 24; NO `source_bucket` column.** If a task seems to need a schema column, STOP (D4/L3).
- **L4 (observe-load)** ACCEPT-AND-MEASURE: V1 ships UNCAPPED; both relief levers ship DORMANT (cfg knobs default `None`). **A silent cap is FORBIDDEN** -- any drop/shed emits a #27 audit.
- **L5 (invariants)** Schwab **L2 LOCK** untouched (zero new Schwab calls -- `git diff` shows no `swing/integrations/schwab/` change). Append-only + `ohlc_today_json` LOCK-at-observation preserved. yfinance OHLCV-fetch-scope discipline holds.
- **OQ-1** V1 uncapped + dormant levers; the accept-uncapped criterion is judged at the §3 gate. **OQ-4** the 4-part gate (§3). **OQ-7** KEEP the by-ticker/by-id trade backlinks (isolate ONLY the 3 silent aggregate/queue consumers). **L6** single Codex chain to convergence.

### §1.1 The CRITICAL correctness contract (plan §3/§4 -- the #1 risk)
1. **The INVISIBLE-WIDEN property.** After the widen, the 3 isolated consumers' DISPLAYED counts (pattern-outcomes tile reached-1R/hit-stop denominator; review-form B.4 cohort; active_learning queue) MUST NOT change vs the aplus-only baseline. Part A's tests assert this (plant a watch-origin PE that WOULD enter the aggregate + an aplus-origin row; post-isolation count == aplus-only). On real PRE-widen data every PE is aplus-origin, so the ladder is a NO-OP on the operator's current rows (a "dark landing").
2. **The provable-aplus LADDER is SOUND (NO leak).** Use `PROVABLE_APLUS_PE_PREDICATE` (`swing/evaluation/pe_origin.py`) -- the 4-step ladder (candidate.bucket='aplus' -> PDE JSON bucket='aplus' -> historical gate `action_session_date < MIN(detection_date over watch PDEs)` [DURABLE -- NOT `MIN(pipeline_run_id)`, which leaks via `ON DELETE SET NULL`] -> EXCLUDE). A naive `OR c.id IS NULL` is the UNSOUND leak -- FORBIDDEN. Apply the ladder INSIDE the review-form cohort CTE BEFORE `ORDER BY ... LIMIT ?` (filter-before-LIMIT, else the cohort silently shrinks). The 6-case ladder regression (Task 1) + the run-pruning regression are binding.
3. **The KEPT backlinks (OQ-7).** Do NOT filter the by-ticker/by-id trade backlinks -- a watch-ticker trade must still anchor to its detection. The backlink-KEEP guard test proves it.
4. **#27 audit accuracy.** The standardized vocabulary is SHARED between Task 7 (empty-pool/widen) + Task 10 (Lever 1). No silent cap.

---

## §2 Execution order (STRICT Part A -> B -> C -> D; the plan's 15 tasks)
The plan binds **ISOLATION FIRST** (spec §9: isolation lands WITH or BEFORE the widen reaches the live pipeline). Follow the plan's linear task order:
- **Part A -- consumer isolation (Tasks 1-5).** Task 1 the `pe_origin.PROVABLE_APLUS_PE_PREDICATE` ladder constant + the 6-case regression; Tasks 2-4 interpolate it into the 3 consumers (pattern-outcomes denominator; review-form B.4 cohort with filter-before-LIMIT; active_learning queue); Task 5 the backlink-KEEP guard (via a real `record_entry` callsite). Part A is green standalone (synthetic watch PEs; a no-op on real aplus-only data).
- **Part B -- the widen (Tasks 6-9).** The predicate widen + `aplus_tickers`->`detect_pool_tickers` rename (ALL sites) + the #27 audit reshape (standardized vocabulary; remove `actual_aplus_pool`, update its ONE test reader); the FDL `universe_size` rename + the `stage_2_pass_rate` comment update; provenance-by-construction (watch detection's `finviz_screen_state` carries `"bucket":"watch"`); bucket-flip first-detection-wins.
- **Part C -- dormant levers + measurement (Tasks 10-13).** Lever 1 detect-pool cap (deterministic `rs_rank`; cap>=1; AFTER the empty-pool guard) + its #27 audit; Lever 2 status-aware observe pre-fetch SHED (NOT an `expired` transition -- `ohlc_today_json` is NOT NULL; a no-fetch skip; repeated-runs-no-refetch test) + its #27 audit; Task 12 the TRUTHFUL `OhlcvCache` telemetry (`drain_telemetry()` at the fetch boundary -- candidate membership is a PROXY, not truth, per Codex R1-M5) + observe-scaling; **Task 13 the measurement RUN (produces NO commit -- it produces the NUMBERS for the §3 gate; SEEDED/isolated DB ONLY, NEVER the live DB).**
- **Part D -- re-baseline + gate (Tasks 14-15).** Task 14 re-baseline any existing detect/observe fixtures that assume aplus-only (enumerate via the actual pytest run; gotcha #1 -- trust the final count). Task 15 the OQ-4 4-part gate (§3 -- the implementer does the seeded step-smoke + documents the gate; the live run + operator judgment are orchestrator+operator).

---

## §3 The OQ-4 pre/post-merge gate (BINDING; NOT a browser gate)
This arc has NO UI surface and NO schema -- so the gate is the OQ-4 4-part data/runtime gate, with the live run POST-merge (memory `feedback_seeded_gate_masks_default_state`: the seeded smoke models, the live run confirms). The CHOREOGRAPHY:
1. **Implementer (pre-return):** all TDD via seeded/test DBs; run **Task 13 the measurement** on a seeded ~83x DB (the detect+observe wall-clock delta; the per-night `get_or_fetch`/`fetch_window` count; the TRUE net-new yfinance count via the `_yf_download_window` monkeypatch; the ~90-session steady-state projection) -> RECORD the numbers in the return report; run **Task 15 part 3 the seeded step-smoke** (`_step_pattern_detect` -> `_step_pattern_observe` end-to-end on the seeded set; confirm the widened pool, the watch provenance tags, the isolated consumers' counts UNCHANGED vs the aplus-only baseline, the #27 audits). Do NOT run a connecting pipeline against the operator's live DB. Do NOT merge.
2. **Orchestrator QA (gate part 1):** verify against disk (the ladder SQL; the invisible-widen tests; L1-L6; schema NONE via `git diff --stat`; Codex convergence).
3. **Orchestrator presents the Task-13 measurement (part 2) + the seeded step-smoke (part 3) to the operator;** the operator judges the OQ-1 acceptance criterion (ACCEPT UNCAPPED iff runtime delta < the operator budget AND steady-state net-new fetch < the `OhlcvCache` breaker thresholds). If either fails, the operator flips the matching dormant lever (WITH its #27 audit) -- never a silent cap.
4. **Orchestrator merges** (after QA + accept-uncapped + the fast suite re-run ON THE MERGED HEAD, isolating the known xdist co-residency flakes per `feedback_no_false_green_claim`).
5. **Operator runs the first live `swing pipeline run` POST-merge (part 4):** the orchestrator confirms acceptable REAL runtime + fetch volume + the operator-facing surfaces unchanged + the watch detections accumulating in the temporal log. Arc closes.

**The implementer's job ends at step 1** (code + measurement numbers + seeded smoke + Codex convergence + the return report). Steps 2-5 are orchestrator+operator.

---

## §4 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **The invisible-widen property (§1.1)** -- the 3 isolated consumers' displayed counts do NOT move vs the aplus-only baseline; the tests plant watch + aplus PEs and assert the post-isolation count.
2. **The ladder is SOUND** -- the 4 steps in order; NO `c.id IS NULL` leak; the DURABLE `detection_date` boundary (survives run-pruning -- the `pipeline_run_id` boundary leaks via `ON DELETE SET NULL`); filter-before-LIMIT for the review-form cohort; the 6-case + run-pruning regressions present.
3. **The KEPT backlinks** are NOT isolated (watch-ticker trade linkage preserved); the backlink-KEEP test discriminates intended-exception vs blanket-isolation.
4. **#27 audit accuracy + UNIT** -- the standardized vocabulary shared Task 7<->10; both dormant levers + the empty-pool path emit accurate `warnings_json`; NO silent cap; each counter's unit stated.
5. **The widen is correct** -- count == aplus+watch > aplus; provenance-by-construction (`"bucket":"watch"`); bucket-flip first-detection-wins (1 row locked `watch`); the rename is complete (no stray `aplus_tickers`).
6. **The dormant levers** -- Lever 1 after the empty-guard + cap>=1 + deterministic `rs_rank`; Lever 2 a no-fetch SKIP (not an `expired` transition) + repeated-runs-no-refetch; Task 12 telemetry at the TRUE fetch boundary (not the candidate-membership proxy).
7. **L5 invariants** -- Schwab L2 LOCK untouched (zero new Schwab calls); append-only + LOCK-at-observation preserved; OHLCV-fetch-scope respected.
8. **L3 no schema** (`EXPECTED_SCHEMA_VERSION == 24`; `git diff --stat` shows zero `swing/data/migrations`/schema-version change); **ASCII (#16/#32)** on all new strings; Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §5 TDD + commit discipline
- Per task: failing test FIRST with the pre-vs-post value check + the NAMED discriminating axis (the plan bakes the discriminators in -- e.g. the widen count A+W-vs-A; the audit field-name/shape; the pre/post-isolation count; the bucket-flip locked bucket). See it fail; minimal impl; see it pass; commit. Conventional messages (`feat(pipeline):`/`fix(...)`/`test(...)`).
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph PLAIN PROSE; verify `git log -1 --format='%(trailers)'` is `[]` before any push.
- Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. **If mid-batch tool cancellations recur, switch to single sequential tool calls + re-Read before each Edit** (memory `feedback_degraded_harness_sequential_tool_calls` -- a failed call invalidates the file-read state; do not let broken Edits proceed into commits).
- Run `python -m pytest -m "not slow" -q` to confirm green before the Codex chain; the known xdist co-residency flakes (`test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor`) PASS in isolation (`-n0`) -- if one flakes, re-run it `-n0`; do NOT treat it as a regression.

---

## §6 If you get stuck
- Plan file:line no longer matches the tree -> TRUST the tree + re-grep (the plan's §1 table is the map; main is `a78443ce`+).
- A task seems to need a SCHEMA column (`source_bucket`) -> STOP (D4/L3 -- the bucket rides in the existing `finviz_screen_state` JSON).
- The isolation seems to need `OR c.id IS NULL` -> STOP (the UNSOUND leak); use the provable-aplus ladder + the DURABLE `detection_date` boundary.
- The measurement seems to need a live pipeline run -> STOP; seeded/isolated DB only; the live run is the POST-merge operator gate (§3 step 5).
- A relief lever seems to need a per-night observe COUNT cap -> STOP (V1 is window-based, no starvation; the count cap is V2).
- An operator-facing count WOULD shift under the widen -> STOP; the isolation (Part A) must keep it aplus-only; fix the ladder, do not accept a visible shift.
- HOLD THE LINE: aplus+watch (not skip); NO schema (JSON provenance); isolation lands first; the provable-aplus ladder (durable boundary); accept-and-measure with NO silent cap; the Schwab L2 LOCK + append-only + LOCK-at-observation survive.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix + STDIN-pipe (verify `codex --version`).
- DO NOT merge (orchestrator); DO NOT run the live pipeline gate yourself (orchestrator+operator, POST-merge).

---

## §7 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `pattern-observation-pool-widening-executing`. Dir `.worktrees/pattern-observation-pool-widening-executing/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `a78443ce`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged plan + spec). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). **NO isolated venv** (no shared-dep change). **NO live-DB touch** -- all dev + the Task-13 measurement use seeded/isolated DBs; the live `swing pipeline run` is the orchestrator+operator POST-merge gate, not yours.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix + stdin-pipe form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §8 Return report shape
Mirror the prior executing-plans return reports: final HEAD + per-task commit breakdown (Tasks 1-15 across Parts A-D); the fast-suite result (count; cite it; the baseline delta from the new tests; isolate the known xdist flakes); the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); per-task completion; L1-L6 + OQ-1/4/7 verification; the §1.1 correctness-contract confirmation (the invisible-widen tests + the ladder soundness + the KEPT backlinks + the #27 vocabulary); **the Task-13 MEASUREMENT NUMBERS** (detect+observe wall-clock delta; per-night `fetch_window`/net-new yfinance count; the ~90-session steady-state projection) presented for the operator's OQ-1 accept-uncapped judgment; the seeded step-smoke result (the isolated counts unchanged); Codex Majors accepted (ZERO preferred); the schema verdict (NONE -- v24 holds; `git diff --stat` shows zero migration/schema-version change); the Schwab L2-LOCK-untouched confirmation; ZERO Co-Authored-By confirmation; worktree status (left intact for the orchestrator's QA + merge); merge-readiness + the §3 gate-state (which parts the implementer completed [1] vs which are orchestrator+operator [2-5]).

---

*End of brief. Pattern-observation pool-widening executing-plans dispatch (a standalone Phase-15 B-family sub-bundle) -- execute the merged Codex-converged 1431-line plan: Part A consumer isolation (the provable-aplus ladder via `pe_origin.PROVABLE_APLUS_PE_PREDICATE`; isolate the 3 silent aggregate/queue consumers to aplus-origin, filter-before-LIMIT, the DURABLE `detection_date` historical gate, KEEP the trade backlinks) -> Part B the predicate widen + `detect_pool_tickers` rename + #27 audit reshape + provenance-by-construction + bucket-flip first-detection-wins -> Part C the two DORMANT relief levers + the truthful `OhlcvCache` telemetry + the seeded-DB observe-load measurement -> Part D re-baseline + the OQ-4 gate. THE BINDING CONTRACT: the widen is INVISIBLE to operator-facing surfaces (the isolated counts do not move) + the ladder leaks NO watch row. NO schema (v24); accept-and-measure with NO silent cap; the Schwab L2 LOCK + append-only + LOCK-at-observation survive. The gate is QA + the measurement + the seeded step-smoke + an operator-witnessed first live run POST-merge. OUTPUT: the merged-ready widen, suite-green + Codex-converged, with the measurement numbers for the operator's accept-uncapped call.*
