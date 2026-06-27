# Phase 13 T4.SB Brainstorming Return Report

**Branch:** `phase13-t4-sb-brainstorming`
**Baseline:** main HEAD `e75f743` (T4.SB brainstorming dispatch brief + triage list operator-confirmed fields)
**HEAD at handback:** `2e34e97`
**Date:** 2026-05-22
**Workflow:** `copowers:brainstorming` (wraps `superpowers:brainstorming` with adversarial Codex MCP review)
**Dispatch:** Phase 13 T4.SB brainstorming — scope the closer covering 7 operator-confirmed usability triage items + identify investigations the executing-plans phase will need to perform.

---

## §1 Commit chain

6 commits — 1 initial spec + 4 Codex MCP fix bundles + 1 R5 MINOR closure. All commits ZERO `Co-Authored-By` trailer per cumulative ~370+ streak discipline.

| Order | SHA | Title | Notes |
|---|---|---|---|
| 1 | `0072a5b` | docs(phase13): T4.SB closer brainstorming spec | Initial 945-line spec §A-§M |
| 2 | `3ae42af` | docs(phase13): T4.SB brainstorm spec Codex R1 fix bundle | 7 MAJOR + 3 MINOR resolved |
| 3 | `608345c` | docs(phase13): T4.SB brainstorm spec Codex R2 fix bundle | 4 MAJOR + 2 MINOR resolved |
| 4 | `d9d5cd3` | docs(phase13): T4.SB brainstorm spec Codex R3 fix bundle | 3 MAJOR + 2 MINOR resolved |
| 5 | `74d0238` | docs(phase13): T4.SB brainstorm spec Codex R4 fix bundle | 3 MAJOR + 1 MINOR resolved |
| 6 | `2e34e97` | docs(phase13): T4.SB brainstorm spec Codex R5 MINOR closure | NO_NEW_CRITICAL_MAJOR — 2 advisory MINORs closed |

Final spec file: ~990 lines, 12 sections (§A-§L) + closing notes (§M).

## §2 Codex chain shape

**5 rounds. ZERO CRITICAL findings cumulatively. ZERO ACCEPT-WITH-RATIONALE on MAJOR findings. All 17 MAJOR findings RESOLVED in-place.**

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 7 | 3 | ISSUES_FOUND |
| R2 | 0 | 4 | 2 | ISSUES_FOUND |
| R3 | 0 | 3 | 2 | ISSUES_FOUND |
| R4 | 0 | 3 | 1 | ISSUES_FOUND |
| R5 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** |

### §2.1 MAJOR findings + resolutions (17 total; all RESOLVED in-place)

**R1 (7 MAJOR):**
- R1.M1: Item 1 diagnostic "re-runs against same input snapshot" overpromise → schema does NOT persist OHLCV snapshots; rescoped to consume PERSISTED `candidate_criteria` per migration `0001_phase1_initial.sql:48-56`.
- R1.M2: Item 5 JIT side effects in `chart_scope` wrong location → `chart_scope` LOCKED read-only; NEW `swing/web/chart_jit.py:get_or_render_surface` accepts conn + ohlcv_cache + surface explicitly; invoked from route handlers / VM builders.
- R1.M3: Item 5 OHLCV dependency plumbing missing → explicit threading via `request.app.state.ohlcv_cache` (T1.SB0 LOCK); writing-plans verifies via grep.
- R1.M4: Item 7 Option 7C "SQL LIKE/prefix-match" too broad → 3-rule delimiter-aware matching: (1) exact; (2) `name + " "`; (3) `name + ";"`. SHARED helper in Python + SQL.
- R1.M5: Item 2 existing labeler contract names ignored → `SilverLabelResponse.geometric_evidence_narrative` already exists; contract widening is ADDITIVE for `rule_criteria` ONLY.
- R1.M6: Item 2 template extension claimed but not needed → `exemplars.html.j2` ALREADY renders `criterion_rows` + `narrative_text`; gap is at EMITTER + PERSISTENCE.
- R1.M7: Item 6 WatchlistRowVM extension heavier than need → pivoted to Option 6B (partial-rewire); template parameter `chart_svg_bytes_for_row` passed explicitly from BOTH page-render AND collapse route.

**R2 (4 MAJOR):**
- R2.M1: Expanded views (hyp-recs + watchlist) PNG-fallback NOT suppressed by inline-SVG → both templates pivot to if-else cascade; `WatchlistExpandedVM` gains `watchlist_expanded_chart_svg_bytes`; JIT fallback wired into `build_hyp_recs_expanded` + `build_watchlist_expanded`.
- R2.M2: R1 resolutions NOT propagated into §G + §J + commit templates → §G.1.3 / §G.1.4 / §G.1.5 rewritten; OQ-2.1 lock-updated; commit templates aligned.
- R2.M3: Item 2 `rule_criteria` schema incompatible with existing VM parser → schema LOCKED to `{name, status (pass|fail), evidence_value, threshold, tolerance}` per `_parse_criterion_rows:110-160`.
- R2.M4: Item 7 broader audit missed `count_per_cohort` → code-surfaces extends to `count_per_cohort` at lines 99-119; cross-bundle pin row 13 parametrize set NOW 4 surfaces.

**R3 (3 MAJOR):**
- R3.M1: Internal contract contradiction in §B.2 — dataclass validation said `rule_name` + `passed` but schema-LOCK was `{name, status, ...}` → `__post_init__` requires `name` + `status IN {"pass", "fail"}` per pinned shape; discriminating tests aligned.
- R3.M2: "Preserve `geometric_evidence_narrative` + no parser change" does NOT fix narrative rendering → existing `_parse_narrative_text` reads `labeler_evidence_json['narrative']` not `['geometric_evidence_narrative']`; envelope-ALIAS pattern persists both keys.
- R3.M3: `surface='hyprec_detail'` reused for watchlist expanded without LOCK → `hyprec_detail` LOCKED as CANONICAL "full-ticker detail chart with MA + volume" rendered in ANY UI surface; V2 `ticker_detail` rename banked.

**R4 (3 MAJOR):**
- R4.M1: `count_per_cohort` rewrite risked dropping orphan-label behavior → PRESERVE orphan-label via second query for closed trades NOT delimiter-matching any registered hypothesis; discriminating test plants 3 rows (registered-suffix + registered-exact + orphan).
- R4.M2: SQL helper parameter contract for `%` / `_` registry names — exact-equality predicate must use UNESCAPED name; only LIKE params need escaped name → helper returns `(where_fragment, [raw_lowercased, escaped_lowercased, escaped_lowercased])`; discriminating test with synthetic registry name `'cohort_X%'` + 4 persisted labels.
- R4.M3: `hyprec_detail` cache collision if callers pass different renderer kwargs → Renderer-kwargs CACHE-COLLISION LOCK: both JIT callsites pass identical minimal kwargs (`pattern_evaluation=None` for V1); discriminating cache-collision test mocks renderer + asserts call_count == 1.

**R5 (0 MAJOR — convergence).**

### §2.2 MINOR findings summary (10 total; all RESOLVED inline or via wording fix)

- R1.MIN1: Item 3 SVG test broad assertion → RESOLVED (narrow to `ax_vol.get_yticklabels()` empty list).
- R1.MIN2: JIT latency claim ~1-2s unsupported → RESOLVED (annotated UNVERIFIED ESTIMATE; commission measured-timing diagnostic).
- R1.MIN3: Item 5 vs Item 7 dispatch sequencing → RESOLVED (code deps unchanged; operator-witnessed gate ordering note added).
- R2.MIN1: failed_pct denominator ambiguous → RESOLVED (explicit LOCK: `failed_count / non_aplus_candidate_count`; separate `na_pct`).
- R2.MIN2: "cold-Schwab-token" wording inconsistent with L2 LOCK → RESOLVED (replaced with "cold OHLCV/archive fetch"; cites L2 LOCK).
- R3.MIN1: §A.2 severity table label inconsistent → RESOLVED (updated to "additive `rule_criteria` + narrative envelope alias").
- R3.MIN2: §B.2 phrasing "VM builder does NOT extract `rule_criteria`" wrong → RESOLVED (rephrased; parser already extracts; gap is emit/persist).
- R4.MIN1: OQ-2.1 alias mention missing → RESOLVED (alias explicit in OQ-2.1).
- R5.MIN1: Cache-collision test independent matplotlib byte-comparison fragile → RESOLVED (rewrote to read-comparison + mock renderer + assert call_count == 1).
- R5.MIN2: Registered-hypothesis-name non-overlap invariant → RESOLVED (banked invariant test in T-T4.SB.2).

## §3 28th cumulative C.C lesson #6 validation — per-expansion verdict

**Verdict: NOTABLE.** First application of all 7 expansions + 3 NEW refinements (Expansion #4 + #8 + #9) + 5 NEW gotchas (#9-#13) at the BRAINSTORMING phase. Pre-Codex spec-write phase CLEAN on most surfaces; Codex R1-R4 surfaced 17 MAJOR escalations across 5 sub-issues categories that pre-Codex review missed:

| Expansion | Source | Pre-Codex catch? | Codex catch? | Verdict |
|---|---|---|---|---|
| #1 hardcoded-duplicate audit | T3.SB2 hotfix `cf3c489` | CLEAN | n/a | CLEAN |
| #2 brief-vs-spec source-of-truth + brief-vs-actual schema | T2.SB6c brainstorm | CLEAN at orchestrator brief read | n/a | CLEAN |
| #3 schema-CHECK-vs-semantic-contract gap | T2.SB6a R1 CRITICAL #1 | CLEAN (no schema changes proposed at brainstorm phase) | n/a | CLEAN |
| #4 specific-scenario gotcha trace + SQL skeleton column verification | T2.SB6c brainstorm | CLEAN at SQL skeleton draft | n/a | CLEAN |
| #5 cross-section spec inventory grep | T2.SB6a R1 MAJOR #3 | CLEAN | n/a | CLEAN |
| #6 content-completeness audit | T2.SB6b lessons | CLEAN (7 items + 17 OQs enumerated) | n/a | CLEAN |
| #7 cross-row semantic SCOPE audit | T2.SB6b lessons | CLEAN-ish (per-item code surfaces audited) | **PARTIAL FAIL** — Codex R1.M2+M3+M7 caught wrong-location architecture (chart_scope JIT invocation + missing OHLCV plumbing + WatchlistRowVM over-extension) | RESOLVED |
| #8 NEW: per-aggregation-function UNIT audit | T2.SB6c writing-plans | CLEAN at SQL helper draft | n/a (SQL helper design CLEAN) | CLEAN |
| #9 NEW: form-render anchor lifecycle audit | T2.SB6c executing-plans | CLEAN (no new hidden form anchors proposed) | n/a | CLEAN |

**NEW lesson categories surfaced via Codex R1-R5:**

1. **Architecture-location audit for cross-cutting helpers** (R1.M2): when a brief proposes wiring a NEW helper into an EXISTING module, audit whether that module has the necessary dependency-context to host the helper. `chart_scope.py` is a PURE availability-check module; injecting JIT side-effects there breaks separation of concerns + requires deps the module doesn't have. Future briefs should enumerate "where does the new logic LIVE (NEW module) vs INVOKE FROM (existing route/handler)" explicitly.

2. **Template-vs-VM-parser-vs-emitter gap-location triangulation** (R1.M6 + R3.M2): when a "feature doesn't render" gap exists, code-read ALL THREE LAYERS — template, VM-parser, emitter — to identify WHERE the data flow breaks. The brief originally identified the gap at the template; code reading confirmed template + parser already correct; gap is at emit/persist. Future Item-N audits should triangulate all three layers BEFORE proposing a fix.

3. **Cache-key shape and renderer-kwargs uniformity** (R4.M3): when a `surface` enum is reused across multiple callers with different render kwargs, the cache key shape `(ticker, surface, pipeline_run_id)` becomes ambiguous; second caller overwrites first. LOCK both rendererkwargs uniformity AND a discriminating cache-collision test that mocks the renderer.

4. **SQL LIKE wildcard escape + raw-vs-escaped binding-param asymmetry** (R4.M2): when a SQL helper produces both an EQUALITY predicate AND a LIKE predicate against the same name parameter, the equality predicate must use the RAW name (escape sequences break verbatim equality) and the LIKE predicates must use the ESCAPED name (or wildcards in the name broaden the match). Helper signature must return distinct binding params.

5. **Orphan-label preservation when refactoring exact-match groupings to delimiter-aware** (R4.M1): existing `count_per_cohort` intentionally returns unregistered cohorts as orphan placeholders; the delimiter-aware refactor must PRESERVE this via a second query.

**Banked as Expansion #10 CANDIDATE (BINDING for 29th cumulative validation onwards):** **architecture-location audit + template-vs-VM-parser-vs-emitter triangulation + cache-key+renderer-kwargs LOCK + SQL-LIKE-binding-asymmetry + orphan-preservation under refactor** — these 5 sub-categories are sufficiently distinct from Expansions #1-#9 to warrant their own banking.

## §4 V1 simplifications (banked) + V2 candidates

### §4.1 V1 simplifications shipped at brainstorm (BANKED for executing-plans + writing-plans phases)

| Row | NEW V1 simplification | V2 dependency cited | Banked for |
|---|---|---|---|
| 1 | Item 1 diagnostic does NOT re-run criteria against original OHLCV snapshot (schema does not persist) | V2 OHLCV reconstruction via `read_or_fetch_archive` at the data_asof_date per candidate + cross-day cache-validity verification | V2 enhanced diagnostic |
| 2 | Item 1 margin-of-failure: numeric criteria parse `value` as float; non-numeric criteria emit "boolean-fail" with no margin | V2 structured `(criterion_value_numeric, criterion_threshold_numeric)` columns OR per-criterion rule-schema parsing helper | V2 candidate_criteria enrichment |
| 3 | Item 5 retention policy R1 unbounded + R4 manual prune CLI; R2/R3 automated retention V2-deferred | V2 automated retention TTL config | V2 if operator observes growth |
| 4 | Item 5 synchronous-JIT-no-timeout (worst-case ~1-2s; acceptable for operator-paced workflow) | V2 async-render with HTMX placeholder polling | V2 if operator UX regression |
| 5 | Item 5 `hyprec_detail` surface name reused for watchlist-expanded full-ticker chart (historical naming grandfathered) | V2 rename to `ticker_detail` with v22 schema migration + CHECK widening | V2 cosmetic refactor |
| 6 | Item 2 forward-only re-label corpus is operator-paired; not auto-fired at execution | V2 automated re-label corpus orchestrator workflow | V2 cohort import workflow |
| 7 | Item 2 Path C backfill script retained for future cohort-import scenarios | NONE (already shipped at T2.SB6c §1.5.2) | n/a |
| 8 | Item 7 Option 7C READ-time delimiter-aware match (NOT canonicalize-at-persistence) preserves operator's per-trade suffix | V2 OPTIONAL `trades.hypothesis_label_suffix` column (Option 7B) IF operator wants suffix as separate column for query convenience | V2 schema if operator decides |
| 9 | Item 7 broader audit V1 closes WIRING DEFECT entries identified at diagnostic; FALSE-ZERO RISK entries from T2.SB6c §4.1 (rows 1 + 4 + 5) may be CLOSED inline IF marginal cost low OR re-BANKED V2 with citation | Per-V1-simplification V2 backlogs | V2 OHLCV-aware metrics |
| 10 | Item 5 expanded-view inline-SVG-suppresses-PNG-banner contract — PNG fallback path PRESERVED for legacy genuinely-errored cases; `out-of-scope` banner becomes unreachable for `watchlist_row` + `hyprec_detail` once JIT lights up but message-dispatch-table preserved for other reasons | V2 banner removal if zero genuinely-errored cases observed | V2 cosmetic cleanup |
| 11 | Item 5 measured-timing diagnostic ships as part of T-T4.SB.1 or T-T4.SB.3 reporting render-time-ms | V2 continuous render-time monitoring + alert | V2 observability |
| 12 | Item 6 partial-rewire updates BOTH page-render + collapse route to pass `chart_svg_bytes_for_row` explicitly; no shared VM-shape coupling | NONE — this IS the canonical pattern | n/a |
| 13 | Cross-bundle pin row 13 parametrized over 4 metric surfaces (not 5+) for V1 LIFT scope | V2 expand pin parametrize set when new metric surfaces add hypothesis-label-grouping | V2 metrics expansion |
| 14 | Registered-hypothesis-name non-overlap invariant test plants in T-T4.SB.2; fires if future registry entry shares delimiter-aware prefix with existing | V2 enforce non-overlap as schema CHECK at hypothesis_registry insert | V2 if registry grows |

### §4.2 V2 candidates from this dispatch (inherited)

All 14 V1 rows above are V2-banked. Plus inherited V2 candidates from T2.SB6c return report §4.1 + main spec §7.4:
- All 8 T2.SB6c §4.1 V1 simplifications preserved through T4.SB scope (rows 1-8 in T2.SB6c return report).
- Phase 14 / Applied Research branch transition decision (operator-driven per OQ-CL.2).
- Pattern_review_detail SURFACE enum (V2 chart_renders extension for gold-tier pattern-review surface with pattern_evaluation overlay).

## §5 Forward-binding lessons banked

### §5.1 Lessons from this dispatch (NEW)

1. **Architecture-location audit for cross-cutting helpers** — when a brief proposes wiring NEW logic into an EXISTING module, audit dependency-context availability before locking the location. Codex R1 M#2 + M#3 + M#7 caught 3 instances of this pattern at brainstorm phase.

2. **Template-vs-VM-parser-vs-emitter gap-location triangulation** — code-read all three layers before locking a "feature doesn't render" fix design. Codex R3 M#2 caught the narrative-rendering gap was at PERSISTENCE-ENVELOPE-EMIT not at the field-name-preservation level.

3. **Cache-key shape + renderer-kwargs uniformity LOCK** — when a `surface` enum is reused across multiple callers with potentially different render kwargs, lock the renderer kwargs identical across callsites AND add a discriminating cache-collision test that mocks the renderer + asserts call_count == 1 for the second caller. Codex R4 M#3 caught this.

4. **SQL LIKE wildcard-escape + raw-vs-escaped binding-param asymmetry** — equality predicate uses RAW name; LIKE predicates use ESCAPED name. Helper signature must return per-param distinguishable bindings. Codex R4 M#2 caught this.

5. **Orphan-label preservation when refactoring exact-match groupings to delimiter-aware** — existing exact-match GROUP BY surfaces intentionally surface unregistered labels as orphan placeholders; the delimiter-aware refactor MUST add a second-query orphan-fallback. Codex R4 M#1 caught this.

6. **R1+R2+R3 propagation discipline** — when a Codex round resolves architectural changes in narrative sections (§B), the downstream §G task definitions + §J OQs + commit message templates MUST be updated in the SAME fix bundle to prevent executing-plans phase following stale instructions. Codex R2.M2 explicitly called out propagation gaps from R1 resolutions.

### §5.2 Cumulative lessons inherited (BINDING; preserved through this dispatch)

All cumulative gotchas in CLAUDE.md honored:
- Pre-Codex 7-expansion + 3 NEW refinements (Expansion #4 + #8 + #9) BINDING — applied at spec-write phase; Expansion #7 caught PARTIAL FAIL via Codex (matches T2.SB6c executing-plans pattern of Expansion #7 partial-fail).
- 5 NEW gotchas (#9-#13) BINDING — applied at spec-write phase for each item's design narrative.
- ZERO Co-Authored-By footer (~370+ commit cumulative streak preserved through 6 brainstorm commits).
- ASCII-only narrative + commit messages.
- `python -m swing.cli` from worktree cwd discipline (cited at §I.3 + commit message templates).
- TDD per task discipline (cited at §I.3).

## §6 Cumulative streaks preserved

- **`Co-Authored-By` trailer:** ZERO on all 6 brainstorm commits → cumulative ~376+ commit streak.
- **C.C lesson #6 cumulative validations:** 22x CLEAN through T3.SB3 → 23rd NOTABLE T2.SB6a → 24th NOTABLE T2.SB6b → 25th NOTABLE T2.SB6c brainstorming → 26th NOTABLE T2.SB6c writing-plans → 27th NOTABLE T2.SB6c executing-plans → **28th NOTABLE T4.SB brainstorming** (this dispatch). Pre-Codex review CLEAN on 8 of 9 expansions; **Expansion #7 PARTIAL FAIL** (architecture-location wrong-module placement; Codex R1 caught 3 sub-instances). NEW Expansion #10 CANDIDATE banked.
- **Sub-bundle ship count:** Phase 13 sub-bundles SHIPPED = 11 of 11 (T4.SB brainstorming is the FIRST of 6 closer-sub-bundle phases; T4.SB SHIPPED transitions to 12 of 12 / FULLY CLOSED).
- **Schema v21 LOCKED streak:** preserved through brainstorming phase (docs-only).
- **Zero new Schwab API calls:** L2 LOCK preserved.

## §7 Inline self-verification

- **Schema version:** `schema_version: 21` (confirmed via direct `sqlite3` read against operator's `~/swing-data/swing.db`; UNCHANGED).
- **Ruff sanity:** `python -m ruff check swing/` → **All checks passed!** (0 violations; docs-only branch did not touch swing/).
- **Test count:** UNCHANGED at baseline 5670 fast (docs-only branch; no test changes).
- **Spec file:** ~990 lines committed at HEAD `2e34e97`.
- **Codex chain:** 5 rounds; R5 verdict NO_NEW_CRITICAL_MAJOR; ZERO CRITICAL entire chain.
- **Session state file:** written atomically to `/tmp/.copowers-session-ced564459472.json` per skill protocol.

## §8 Schema delta

**NONE.** T4.SB brainstorming proposes ZERO schema changes; the closer phase is expected schema-UNCHANGED (v21 trades-backlinks landed at T2.SB6c T-A.6c.1). If OQ-7.3 Option 7B (NEW `trades.hypothesis_label_suffix` column) is chosen at operator-paired triage post-brainstorming, the v22 schema bump + §A.14 paired discipline would apply in the writing-plans phase. Orchestrator-recommended Option 7C (no schema change) is the V1 default.

## §9 Open questions for operator-paired triage post-brainstorming

Per spec §J, 17+ OQs surfaced for operator-paired triage BEFORE writing-plans dispatch:

- **Item 1 (4 OQs):** OQ-1.1 diagnostic output format; OQ-1.2 diagnostic time window; OQ-1.3 post-diagnostic action threshold; OQ-1.4 production vs research branch placement.
- **Item 2 (3 OQs):** OQ-2.1 subagent emit contract schema (LOCKED to existing parser shape + narrative envelope alias); OQ-2.2 re-label corpus OR forward-only; OQ-2.3 V1 Path C backfill retention.
- **Item 5 (5 OQs):** OQ-5.1 cache retention policy (R1-R4); OQ-5.2 JIT cache-miss render latency budget (sync-no-timeout / sync-with-timeout / async-V2); OQ-5.3 pre-gen scope (top-5 watchlist + market_weather + position_detail recommended); OQ-5.4 re-run collision semantics (Option A pipeline_run-anchored / Option B latest-regardless); OQ-5.5 chart-unavailable banner removal vs keep-as-fallback.
- **Item 7 (3 OQs):** OQ-7.1 diagnostic-then-fix sequencing; OQ-7.2 broader audit scope; OQ-7.3 canonicalization-at-persistence (Option 7A strip / Option 7B new column / Option 7C READ-time delimiter-aware match — RECOMMENDED).
- **Phase 13 closure (3 OQs):** OQ-CL.1 closure marker naming; OQ-CL.2 Phase 14 trigger; OQ-CL.3 research-branch first-method-record selection timing.
- **Cross-item (1+ OQ):** OQ-X.1 Items 3+4+6 bundle as one Codex round.

## §10 Post-brainstorming next steps (orchestrator-side)

1. **Operator-paired OQ triage** per §9 above. Operator confirms / overrides per-OQ disposition; updates spec inline at the OQ paragraphs.
2. **Merge brainstorming branch `--no-ff` to main** post-operator-OQ-triage + housekeeping.
3. **Draft T4.SB writing-plans dispatch brief** consuming the brainstorming spec + locked OQ dispositions.
4. **Continue copowers chain:** writing-plans → executing-plans → operator-witnessed gates (S2 browser + S3+S4 CLI + S5 CLI) → merge + housekeeping → **Phase 13 FULLY CLOSED marker** (CLAUDE.md current-state line + orchestrator-context updates).
5. **Phase 14 / research-branch transition** decision per OQ-CL.2 — separate dispatch after Phase 13 FULLY CLOSED.

End of return report.
