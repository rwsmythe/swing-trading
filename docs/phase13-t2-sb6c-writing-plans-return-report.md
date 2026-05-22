# Phase 13 T2.SB6c — Writing-plans return report

**Status:** WRITING-PLANS COMPLETE on branch `phase13-t2-sb6c-writing-plans` at HEAD `3644d55`. Branched from main HEAD `c9bd715` (post-dispatch-brief amendment). 7 commits total (1 initial plan + 6 Codex MCP adversarial-review fix bundles). Codex MCP chain converged at **R6 NO_NEW_CRITICAL_MAJOR** (R1-R5 each surfaced new findings closed in turn; R6 verdict cleared).

**Final plan:** [`docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md`](superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md) (~1730 lines; covers §A-§J done criteria per dispatch brief §5 verbatim).

**Inline self-verification at writing-plans close:**
- `ruff check swing/` → All checks passed (writing-plans touches docs/ only; no swing/ code).
- Schema v20 UNCHANGED at writing-plans phase (only plan docs added/edited).
- ZERO `Co-Authored-By` footers across all 7 commits (~360+ cumulative streak preserved through this dispatch).

---

## §1 Commits

| Commit | Title |
|---|---|
| `4568d69` | docs(phase13): T2.SB6c v21 schema + SB6 closure writing-plans plan |
| `b085f15` | docs(phase13): close T2.SB6c writing-plans Codex R1 - 1 CRITICAL + 4 MAJOR + 1 MINOR |
| `dc810f8` | docs(phase13): close T2.SB6c writing-plans Codex R2 - 5 MAJOR + 1 MINOR |
| `d3b28db` | docs(phase13): close T2.SB6c writing-plans Codex R3 - 3 MAJOR + 2 MINOR |
| `104550f` | docs(phase13): close T2.SB6c writing-plans Codex R4 - 2 MAJOR |
| `3644d55` | docs(phase13): close T2.SB6c writing-plans Codex R5 - 2 MAJOR |
| (R6) | (NO_NEW_CRITICAL_MAJOR; no closure commit required) |

ZERO `Co-Authored-By` footers across all 7 commits.

---

## §2 Plan-output §A-§J done criteria

| Section | Status | Notes |
|---|---|---|
| **§A Status + scope** | DONE | All 14 OQ dispositions operator-affirmed VERBATIM per orchestrator-paired triage 2026-05-21 PM #5 |
| **§B Schema deltas** | DONE | Delta A (`trades.candidate_id`) + Delta B (`trades.pattern_evaluation_id`) verbatim from brainstorm spec §2 + SVAI nullable-column pattern enumerated |
| **§C Atomic-landing strategy** | DONE | §A.14 paired discipline (schema + dataclass + read-path mapper + write-path INSERT + tests in ONE commit at T-A.6c.1) enumerated explicitly; §1.5.1 + §1.5.2 amendments folded into T-A.6c.2 + T-A.6c.3 atomic-landing scope; §C.5 anchor-threading 4-layer scope (VM/builder + template + POST handler 5-tier ladder + entry-path mapping fix) |
| **§D Closure consumer mapping** | DONE | Gap A.1-A.4 (4 chart-surface wirings) + Gap B.1-B.6 (6 review-form / queue / metric-tile items) + §1.5.1 + §1.5.2 amendments + OQ-affirmed dispositions VERBATIM; §D.3 cross-row lookup discipline with column-verified SQL skeletons; §D.4 content-completeness audit table (post-SB6c ZERO V1 STUBs on spec §5.10 8-item checklist) |
| **§E Cross-bundle pin updates** | DONE | Row 12 (parametrized over delta_label) PLANTED at T-A.6c.1; un-skip at T-A.6c.5 closer with §H.3 append |
| **§F Test scope projection** | DONE | ~92-95 fast tests + 1 fast E2E per §1.5.3 amendment range; per-task test budget enumerated; baseline 5559 → ~5651-5654 expected; ZERO new slow tests; S1-S11 operator-witnessed gates enumerated |
| **§G Per-task decomposition** | DONE | T-A.6c.1..T-A.6c.5 with bite-sized step structure (Step 1a-1e in T-A.6c.1; Step 1a-1c in T-A.6c.2/3; Step 1a-1f in T-A.6c.4; Step 1-6 in T-A.6c.5); per-task acceptance criteria + commit message templates |
| **§H Dispatch sequence** | DONE | Concurrent T-A.6c.1+2+3; sequential T-A.6c.4 + T-A.6c.5; sub-bundle dependency graph + merge gates |
| **§I Forward-binding lessons inherited** | DONE | 8 lessons from brainstorming return report §7 (Expansion #4 SQL-column verification refinement; Expansion #7 boundary clarification; function-name verification; missing-value semantics; server-derived discipline; EntryPath mapping; VM/builder anchor scope; SVAI for nullable columns) + inherited cumulative gotchas + V1 simplifications + V2 candidates banked |
| **§J References** | DONE | Brainstorm spec + brainstorming return report + dispatch brief (amended at c9bd715) + Phase 13 main plan + CLAUDE.md gotchas + schema migrations (column-verified per Expansion #4 NEW refinement) + canonical repo + dataclass + migration runner code references |

---

## §3 Sub-bundle decomposition (final; per OQ-10 affirmed)

5 tasks proposed with concurrent dispatch recommendation:

```
T-A.6c.1 (v21 migration; foundation; ~23 tests: 17 paired + 4 backup-gate + 2 pin)
    |
    +---> T-A.6c.2 (Gap A chart-surface wiring + §1.5.1 _step_charts cache write-through; ~17-19 tests; no schema dep)
    |
    +---> T-A.6c.3 (Gap B.1/B.2/B.6 no-schema + §1.5.2 labeler_evidence backfill; ~18 tests)
    |
    +---> T-A.6c.4 (Gap B.3/B.4/B.5 v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions; 31 tests; consumes Delta A + B)
              |
              +---> T-A.6c.5 (closer E2E + ruff + cross-bundle pin row 12 promote; 1 E2E)
```

**Concurrent dispatch (recommended)**: T-A.6c.1 + T-A.6c.2 + T-A.6c.3 in parallel; T-A.6c.4 sequential after T-A.6c.1; T-A.6c.5 sequential after all. Expected wall-clock savings ~30-40%.

**Total test forecast**: ~92-95 fast tests + 1 fast E2E (within dispatch brief §1.5.3 amendment range).

---

## §4 Codex MCP adversarial chain shape

Convergence path (6 rounds; nominal MAX_ROUNDS=5 extended to R6 to seek NO_NEW_CRITICAL_MAJOR — precedent: T2.SB6c brainstorm chain went to R8):

| Round | Verdict | Critical | Major | Minor | Cumulative resolved |
|---|---|---|---|---|---|
| R1 | ISSUES_FOUND | 1 | 4 | 1 | 6 (R1 fix bundle at `b085f15`) |
| R2 | ISSUES_FOUND | 0 | 5 | 1 | 6 (R2 fix bundle at `dc810f8`) |
| R3 | ISSUES_FOUND | 0 | 3 | 2 | 5 (R3 fix bundle at `d3b28db`) |
| R4 | ISSUES_FOUND | 0 | 2 | 0 | 2 (R4 fix bundle at `104550f`) |
| R5 | ISSUES_FOUND | 0 | 2 | 0 | 2 (R5 fix bundle at `3644d55`) |
| R6 | **NO_NEW_CRITICAL_MAJOR** | 0 | 0 | 0 | 0 |

**Total findings closed**: 1 CRITICAL + 16 MAJOR + 4 MINOR = 21 findings; ALL RESOLVED in-place (ZERO ACCEPT-WITH-RATIONALE; writing-plans-phase scope changes were absorbed in-place).

**The R1 CRITICAL was a SQL skeleton column-correctness defect** mirroring the brainstorm-phase R1 CRITICAL family: Gap B.4 SQL skeleton used `pe.evaluation_id` but the column is `pe.id` per `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:230-250`; Gap B.6 referenced non-existent `pattern_exemplars.weather_state_at_labeling` column. Both column-verified against actual migration files at R1 closure. Same Expansion #4 NEW refinement family as the brainstorm-phase catch.

**The 16 MAJOR findings spanned**: (R1) highest-composite reintroduction at hyp-rec builder + labeler backfill source mismatch + bite-sized step granularity + B.5 denominator window/class constraint; (R2) B.5 denominator over-count via COUNT(*) inflation + B.1 trend-template Phase-8-vs-Phase-13 module mismatch + B.6 benchmark_ticker plumbing through prioritize_candidates signature + §1.5.1 market_weather ticker pinning + labeler backfill missing-source skip semantic; (R3) B.5 numerator unit (trades vs evaluations) + B.1 date.fromisoformat conversion + queue.py file missing from T-A.6c.3 list; (R4) B.4 same per-trade unit risk + B.5 field/template contract (`*_n` vs `*_pct`); (R5) stale `_pct` in E2E + WilsonCI rendering claim correction.

**The 4 MINOR findings**: (R1) repo helper names (`list_all_exemplars` → `list_exemplars`; add `update_exemplar_labeler_evidence_json`); (R2) commit-add list missing `pattern_exemplars.py`; (R3) stale W9 watch item + CLI name normalization (Click hyphen vs Python underscore convention).

---

## §5 Per-expansion pre-Codex verdict (26th cumulative C.C lesson #6 validation)

**Second-run application of Expansions #6 (content-completeness audit) + #7 (cross-row semantic audit on operator-input flows) at writing-plans phase** — banked at T2.SB6c brainstorming (25th validation); T2.SB6c writing-plans is the inaugural binding execution AT WRITING-PLANS PHASE.

| Expansion | Pre-Codex orchestrator-side verdict | Codex-caught | Net assessment |
|---|---|---|---|
| #1 hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`) | CLEAN at writing-plans (N-mirror auditing of trade SELECT column lists enumerated at §C.1.7) | None | CLEAN |
| #2 brief-vs-spec source-of-truth (T2.SB4 R1 M1) + brief-vs-actual schema reality check | CLEAN at writing-plans (plan §B verifies brief §1.5 amendments against actual code state: chart_renders empty across surfaces + labeler payload 3-key shape) | None | CLEAN |
| #3 schema-CHECK-vs-semantic-contract (T2.SB6a R1 CRITICAL #1) | CLEAN at writing-plans (§C.3 cache key shape per ChartRender semantic validator + F6 transient-empty defense) | None | CLEAN |
| #4 CLAUDE.md gotcha specific-scenario trace + **NEW SQL skeleton column verification** (T2.SB6a R1 MAJOR #2 + T2.SB6c brainstorm R1 CRITICAL #1 banking) | **PARTIAL FAIL at writing-plans** — pre-Codex did NOT trace `pe.evaluation_id` (non-existent) vs `pe.id`, did NOT trace `pattern_exemplars.weather_state_at_labeling` (non-existent), did NOT trace `current_stage` Phase-13-vs-Phase-8 module misattribution; R1 CRITICAL + R2 MAJOR #2 caught all three. Expansion #4 refinement is BANKED BINDING for executing-plans phase. | R1 CRITICAL #1 + R2 MAJOR #2 + R3 MAJOR #2 | **NOTABLE** (lesson: even after the brainstorm-phase Expansion #4 refinement banking, writing-plans-phase pre-Codex review still missed 3 column-correctness defects; the refinement is non-trivial to internalize + benefits from automated tooling) |
| #5 cross-section spec inventory grep (T2.SB6a R1 MAJOR #3) | CLEAN at writing-plans (spec §5.10 inventory enumerated + per-item disposition at §D.4 content-completeness audit) | None | CLEAN |
| **#6 content-completeness audit** (FIRST RUN at writing-plans phase; T2.SB6b banking) | VERIFIED at writing-plans (§D.4 audit table enumerates every §5.10 8-item checklist item with per-field disposition; post-SB6c ZERO V1 STUBs remain) | None | CLEAN |
| **#7 cross-row semantic audit on operator-input flows** (FIRST RUN at writing-plans phase) + **NEW boundary clarification** (T2.SB6c brainstorm banking) | **PARTIAL FAIL at writing-plans** — §D.3 enumerated cross-row SCOPE explicitly (per-candidate vs per-ticker for Gap B.3/B.4/B.5) but did NOT catch the per-trade vs per-evaluation UNIT issue (a different axis than scope); R2 MAJOR #1 + R3 MAJOR #1 + R4 MAJOR #1 caught all three (B.5 denominator + B.5 numerator + B.4 cohort). Expansion #7 boundary clarification confirmed: scope audit ≠ unit audit. | R2 MAJOR #1 + R3 MAJOR #1 + R4 MAJOR #1 | **NOTABLE** (lesson: cross-row scope discipline at writing-plans phase MUST be complemented by per-aggregation-function UNIT audit — what is the SQL COUNT counting? trades? evaluations? candidates? — explicit per-SQL-skeleton enumeration BANKED for executing-plans phase) |

**Cumulative result**: 26th cumulative C.C lesson #6 validation = **NOTABLE** — first-run Expansions #6 + #7 at writing-plans phase; #6 CLEAN; #7 PARTIAL FAIL on unit-vs-scope distinction. 2 NEW lessons banked for 27th validation:

1. **Expansion #4 refinement BINDING continues at executing-plans phase** (NEW: SQL-column verification needs automated tooling). The T2.SB6c brainstorm banking of "every SQL skeleton's columns verified against actual `swing/data/migrations/*.sql` files" was BANKED but writing-plans-phase pre-Codex still missed 3 column-correctness defects (`pe.evaluation_id`, `weather_state_at_labeling`, `current_stage` module attribution). Manual grep-against-migrations is necessary but insufficient; consider a SQL-skeleton-extraction + sqlite-fixture-compile gate as V2 process automation.

2. **NEW Expansion #8 candidate (BANKED for 27th validation): per-aggregation-function UNIT audit on SQL skeletons** — for any GROUP BY / COUNT / SUM / aggregation function in a SQL skeleton, pre-Codex review MUST enumerate: (a) what unit the function is counting (trades, candidates, evaluations); (b) whether the unit matches the semantic ratio the consumer wants (e.g., "% of evaluations that triggered a trade" requires per-evaluation count, NOT per-trade count); (c) whether DISTINCT is needed to prevent JOIN-cardinality inflation. Discriminating test pattern: plant cardinality-multiplied rows (1 evaluation with 2 trades; 1 candidate with 2 overlapping exemplars) + assert per-unit counts match expectations. Banked as #8 because it's distinct from #7 (semantic scope = which rows participate) and from #4 (column existence) — this is about ARITHMETIC UNIT CORRECTNESS in aggregation.

---

## §6 V1 simplifications + V2 candidates banked

V1 simplifications at T2.SB6c executing-plans (closure dispatch — explicit + V2 dependency cited per `feedback_always_provide_inline_dispatch_prompt.md` cumulative discipline):

| V1 simplification | V2 dependency | Banked for |
|---|---|---|
| Existing pre-v21 trades persist `candidate_id = NULL` + `pattern_evaluation_id = NULL` (no retroactive heuristic match) | OQ-1 LOCK; operator-paired investigation of data quality required | V2 enrichment if operator surfaces value |
| Multi-pattern_class trade backlink = single anchor; one trade attaches to ONE pattern_evaluation | many-to-many `trade_pattern_evaluations` link table to capture "this trade was visible against N detector evaluations at lock time" | V2 schema dispatch |
| Volume profile fetch-on-cache-miss accepted as desired behavior (OQ-14 LOCK) | `get_cached_only` variant for pure read-only scenarios | V2 cache architecture |
| Backup-gate strict-equality skips backup on multi-version jump (v20→v22+) | `--enforce-stepwise` flag on `swing db-migrate` to refuse multi-version jumps | V2 migration-runner enhancement |
| `pattern_evaluations.candidate_id` direct column (alternative to JOIN via pipeline_runs.evaluation_run_id) | If Phase 13.5+ surfaces require frequent per-candidate cross-row lookups, this column would eliminate the two-table JOIN | V2 schema dispatch |
| Phase 6 `chart_pattern_algo` enum (`none`/`flag`) disjoint from Phase 13 detector enum | Unify the two enums via a separate spec dispatch | V2 schema migration |
| Path C labeler_evidence_json backfill (synthesis-from-existing) | Path A labeler subagent emit contract widening — fresh exemplars labeled post-T2.SB6c with rule_criteria + narrative emitted directly | V2 labeler subagent spec dispatch |
| Gap B.5 metric tile V1 display = ratio-only (`row.reached_1r_n / row.n` + `row.hit_stop_n / row.n`); `_ci` fields populated but NOT rendered | Template extension to surface WilsonCI alongside ratio per Phase 10 honesty.wilson_ci convention | V2 template surfacing |
| Gap B.1 trend-template state V1 returns only `'stage_2' | 'undefined'` per `current_stage` wrapper at `swing/patterns/foundation.py:745` | Full Weinstein 4-stage labeling (Stage 1 / 3 / 4 differentiation) per spec §5.1.5 LOCK line 523 ("thin wrapper") | V2 trend-template enhancement |

NO new V1 STUBs introduced by T2.SB6c executing-plans per §D.4 content-completeness audit + closure-dispatch intent. The 8 simplifications above are EITHER pre-existing arc-residual items (multi-pattern_class backlink; trend-template depth; cache architecture) OR new operator-paired V2 decisions (WilsonCI surfacing; pattern_evaluations.candidate_id direct column).

---

## §7 Forward-binding lessons banked

8 lessons inherited from brainstorming return report §7 + 4 NEW lessons banked at writing-plans phase:

**Inherited (verbatim from brainstorming):**
1. Brief-vs-actual schema reality check (Expansion #2 effective).
2. SQL skeleton column verification (Expansion #4 refinement).
3. Function name verification (NEW).
4. Hidden-anchor missing-value semantics (NEW).
5. Server-derived vs form-submitted value-domain discipline (NEW).
6. EntryPath mapping load-bearing for trade_origin derivation (NEW).
7. VM/builder fields are part of anchor-threading scope (NEW).
8. Schema-version-aware INSERT for nullable columns (R1 expansion).

**NEW (banked at writing-plans phase):**

9. **SQL aggregation UNIT audit (NEW Expansion #8 candidate)**: pre-Codex review MUST enumerate per-aggregation-function the COUNTING UNIT explicitly. Three R-rounds caught unit-mismatch defects: R2 MAJOR #1 (B.5 denominator without DISTINCT), R3 MAJOR #1 (B.5 numerator counting trades not evaluations), R4 MAJOR #1 (B.4 LIMIT on trade rows not evaluation rows). The lesson generalizes: any time SQL JOINs multi-row tables to single-row tables (1 evaluation : N trades; 1 candidate : N exemplars), the aggregation function MUST specify the unit explicitly via `COUNT(DISTINCT pe.id)` or CTE-then-aggregate pattern. Pre-empt: writing-plans §5 watch item — enumerate per-SQL-skeleton (a) what unit each COUNT counts; (b) whether DISTINCT is needed; (c) whether LIMIT applies at the correct unit. Discriminating test pattern: cardinality-multiplied row fixtures.

10. **Existing-field reuse audit (NEW)**: when extending a dataclass, FIRST grep for existing fields that match the planned-new-field shape. Codex R4 MAJOR #2 caught that `PatternOutcomeRow.reached_1r_n + reached_1r_ci + hit_stop_n + hit_stop_ci` fields ALREADY exist (populated as None per T2.SB6b V1 simplification); the writing-plans plan claimed NEW `*_pct` fields which would have created field-duplication. Pre-empt: writing-plans §5 watch item — `Grep "_n: int | None\|_ci: " <dataclass module>` before claiming new fields.

11. **Template-rendering surface audit (NEW)**: when populating existing-but-None fields, verify the template's render path explicitly. Codex R5 MAJOR #2 caught that `PatternOutcomeRow._ci` fields are populated but the template at `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` does NOT render WilsonCI — only the ratio. The plan claimed "no template edit needed" without verifying what the template actually renders. Pre-empt: writing-plans §5 watch item — for any V1 STUB → LIVE transition, read the template + enumerate which dataclass fields are rendered + which are persisted-but-not-rendered + whether the V1 display contract matches operator expectation.

12. **`date.fromisoformat()` discipline for cross-type-boundary calls (NEW)**: when calling a Python helper that requires `date` type from a column that stores TEXT ISO format, the conversion MUST be EXPLICIT at the call site. Codex R3 MAJOR #2 caught that `current_stage(conn, ticker, asof_date)` requires a `date` object but `pattern_evaluations.window_end_date` is TEXT; missing conversion would raise at runtime. Pre-empt: writing-plans §5 watch item — when a SQL TEXT column feeds a Python helper expecting `date`/`datetime`, cite the conversion explicitly + add malformed-input discriminating test (graceful fallback, not 500).

---

## §8 References

- **Plan** at [`docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md`](superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md) (HEAD `3644d55`)
- **Brainstorm spec** at [`docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md`](superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md) (BINDING substrate)
- **Brainstorming return report** at [`docs/phase13-t2-sb6c-brainstorm-return-report.md`](phase13-t2-sb6c-brainstorm-return-report.md)
- **Dispatch brief (AMENDED)** at [`docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md`](phase13-t2-sb6c-writing-plans-dispatch-brief.md) (commit `c9bd715`)
- **Phase 13 main plan** at [`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`](superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md)
- **Phase 13 main spec** at [`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`](superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md)
- **T2.SB6b return report** at [`docs/phase13-t2-sb6b-return-report.md`](phase13-t2-sb6b-return-report.md)
- **T2.SB6a return report** at [`docs/phase13-t2-sb6a-return-report.md`](phase13-t2-sb6a-return-report.md)
- **CLAUDE.md** at [`CLAUDE.md`](../CLAUDE.md)

---

## §9 Streaks preserved

- **ZERO `Co-Authored-By` footer trailer drift** across all 7 writing-plans commits (~360+ cumulative streak preserved through this dispatch).
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 + 23rd NOTABLE at T2.SB6a + 24th NOTABLE at T2.SB6b + 25th NOTABLE at T2.SB6c brainstorming + **26th NOTABLE at T2.SB6c writing-plans (FIRST RUN applying all 7 expansions AT WRITING-PLANS PHASE; Expansion #4 + #7 PARTIAL FAIL on column-correctness + unit-correctness; 2 NEW lessons banked for 27th validation at T2.SB6c executing-plans: SQL aggregation UNIT audit + existing-field reuse audit + template-rendering surface audit + date.fromisoformat discipline)**.
- **10 of 11 Phase 13 sub-bundles SHIPPED**; T2.SB6c writing-plans output unblocks the T2.SB6c executing-plans dispatch sequence. T4.SB remains paused per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.

---

## §10 Post-writing-plans handback

Writing-plans complete. Orchestrator-side next steps:

1. **Operator-paired review** of the writing-plans plan doc for any last-minute disposition refinements (e.g., WilsonCI V1 surfacing decision at Gap B.5).
2. **Merge writing-plans branch** to main via `--no-ff` per `feedback_orchestrator_performs_merge.md` BINDING memory + post-merge housekeeping bundle.
3. **Draft executing-plans dispatch brief** consuming the writing-plans plan + operator decisions. Per OQ-10 LOCK, executing-plans typically combines T-A.6c.1 + T-A.6c.2 + T-A.6c.3 into one concurrent-dispatch bundle + sequential T-A.6c.4 + T-A.6c.5 (~30-40% wall-clock savings) OR splits into 2 dispatch bundles per operator decision based on plan complexity.
4. **Phase 3e-todo + orchestrator-context refresh** to reflect T2.SB6c writing-plans SHIPPED.
5. **CLAUDE.md line 3 refresh** to reflect 26th cumulative C.C lesson #6 validation outcome + 4 NEW lessons banked (SQL aggregation UNIT audit + existing-field reuse audit + template-rendering surface audit + date.fromisoformat discipline).
6. **Codex MCP session state** at `~/.copowers/sessions/...` updated per adversarial-critic skill's post-output step.

PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding — separate from this dispatch.

---

*End of T2.SB6c writing-plans return report. Codex MCP chain converged at R6 NO_NEW_CRITICAL_MAJOR after 6 rounds (1 CRITICAL + 16 MAJOR + 4 MINOR cumulative findings, ALL RESOLVED in-place; zero ACCEPT-WITH-RATIONALE). 26th cumulative C.C lesson #6 validation = NOTABLE; Expansion #4 + #7 PARTIAL FAIL on column-correctness + unit-correctness despite brainstorm-phase banking; 4 NEW lessons banked for 27th validation at executing-plans. ~360+ ZERO Co-Authored-By footer streak preserved.*
