# Phase 13 T2.SB6 — Closed-loop surface + Theme 1 annotated charts + T-A.1.6 Deficiency 1 fold-in dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 PM #2 post-T3.SB3 SHIPPED + housekeeping at main HEAD `4e71787`. **LARGEST remaining Phase 13 sub-bundle** (8 tasks; +100-150 fast tests + 1 fast E2E projected per plan §H). Per plan §G.9 lines 2109-2306.

**Branch:** `phase13-t2-sb6-closed-loop-surface` — branches from main HEAD `4e71787` at dispatch time (per plan §G.9 line 2113: T2.SB6 branches AFTER T3.SB3 merge).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb6-closed-loop-surface phase13-t2-sb6-closed-loop-surface`.

**Time estimate:** orchestrator wall-clock 12-18 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T2.SB6 is the LARGEST sub-bundle — 8 tasks vs T3.SB3's 5 / T2.SB5's 6 / T2.SB4's 7; introduces a NEW production module (`swing/web/charts.py`) + 4 NEW route handlers + 4 NEW VMs + 4 NEW Jinja templates + the `chart_renders` cache write-through architecture; operator-witnessed gate has 8 sub-gates S1-S8).

**⚠ PAUSE-FOR-LIST-ADDITIONS BINDING reminder**: per `project_phase13_t4_sb_pause_for_list_additions` memory, **the scheduled pause is between T2.SB6 SHIPPED + housekeeping and T4.SB dispatch brief commissioning**. Orchestrator MUST surface the pause at the T2.SB6 SHIPPED + housekeeping boundary; T4.SB will NOT be dispatched without operator's added items.

---

## §1 Scope summary

**Closed-loop pattern review surface + Theme 1 annotated charts + T-A.1.6 Deficiency 1 fold-in per spec §5.10 + §4.6 + §C.1-§C.5 + plan §G.9.** Ships the v2 brief §9.2 8-item evidence-to-show-reviewer checklist + §9.3 6-decision reviewer enum + §9.4 active-learning prioritization + Phase 10 9th metric tile + matplotlib SVG-inline renderer module + `chart_renders` cache write-through + Theme 1 chart surface integration across 4 web pages (watchlist + hyp-rec + position detail + market weather).

| Task | Title | Tests target |
|---|---|---|
| T-A.6.1 | `swing/web/charts.py` SVG-inline renderer per §C.1 LOCK (5 renderer functions) | 10+ tests |
| T-A.6.2 | `chart_renders` cache write-through integration per §C.2 LOCK | 5+ tests |
| T-A.6.3 | `/patterns/{candidate_id}/review` review form (8-item checklist + 6-decision enum) | 10+ tests |
| T-A.6.4 | `/patterns/queue` active-learning prioritization per spec §5.10 4-criterion ranking | 6+ tests |
| T-A.6.5 | `/metrics/pattern-outcomes` 9th metric tile per OQ-10 | 7+ tests |
| T-A.6.6 | Theme 1 chart surface integration + dashboard market weather (4 surfaces) | 8+ tests |
| T-A.6.6b | `/patterns/exemplars` enhanced rendering (T-A.1.6 Deficiency 1 fold-in) | 8+ tests |
| T-A.6.7 | T2.SB6 closer — integration E2E + ruff sweep + cross-bundle pin closures | 1 fast E2E + 2 cross-bundle pin un-skips |

Per plan §G.9 verbatim. Cross-bundle pin work at T-A.6.7 closer:
- **UN-SKIP** `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` per plan §H.3 row 10 (planted at T2.SB6 T-A.6.1; un-skips at T2.SB6 closer). The shared annotated chart renderer verifies all 5 V1 patterns (VCP + flat base + CWH + HTF + DBW) render correctly with `structural_evidence_json`.
- **UN-SKIP** `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 (un-skips at T2.SB6 + T4.SB Q4 service when used).
- Verify status of any other plan §H.3 pins (audit on main HEAD `4e71787` via `git grep "@pytest.mark.skip"` before commit).

### §1.1 Inheritance from T3.SB3 forward-binding lessons (per T3.SB3 return report §6)

T2.SB6 is the FOURTH Phase 13 web-form sub-bundle (after T3.SB1 entry + T3.SB2 exit + T3.SB3 review). Inherited disciplines (BINDING):

1. **Read-path mapping must keep pace with write-path on widened columns** (T3.SB3 R1 M#1 lesson) — T2.SB6 introduces NEW production writes to `pattern_exemplars` from `/patterns/{candidate_id}/review` POST (`label_source='closed_loop_review'` OR `'organic_trade_history'`). If T2.SB6 writes any new column OR widens an existing column, ALL `_row_to_pattern_exemplar` mapper functions in `swing/data/repos/pattern_exemplars.py` MUST be extended in the SAME task. Per `git grep`, verify the mapper is current at the start of T-A.6.3.
2. **"Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES rather than ACCEPTS** (T3.SB3 R1 M#2 lesson; semantic clarification of L10 LOCK) — `/patterns/{candidate_id}/review` POST handler MUST RECOMPUTE any audit envelope at POST time from canonical state (NOT consume GET-side hidden inputs as authoritative). Specifically: the `proposed_pattern_class` value MUST be re-derived from `pattern_evaluations.pattern_class` for the candidate_id at POST time, NOT from a hidden form input. Discriminating test: submit a tampered `proposed_pattern_class="vcp"` for a flat_base candidate; assert persisted `pattern_exemplars.proposed_pattern_class='flat_base'` matching server-recompute, NOT the tampered value.
3. **Audit envelope empty-state representation must be uniform across emit + persist paths** (T3.SB3 pre-Codex M#1 lesson) — if T2.SB6 introduces ANY new audit envelope on `pattern_exemplars` writes (`labeler_evidence_json` extension; new audit JSON columns), emit `None` (NOT `"[]"` / NOT `""`) on empty across all VM builders + persist paths.
4. **Pre-Codex orchestrator-side review with BOTH scope expansions applied is now load-bearing** (T3.SB3 22nd cumulative validation) — **BINDING for T2.SB6 pre-Codex review**. 23rd cumulative validation expected with BOTH scope expansions BINDING.

### §1.2 Inheritance from T3.SB1 + T3.SB2 + T3.SB3 form-driven discipline (BINDING)

T2.SB6 introduces 4 NEW HTMX form-driven routes. Inherited disciplines (BINDING):

5. **HTMX 3-surface discipline** per Phase 5 R1 M1+M2 + Phase 6 I3 inheritance:
   - (a) Embedded forms MUST include `hx-headers='{"HX-Request": "true"}'` under OriginGuard strict-mode
   - (b) Success-path response MUST be `204 + HX-Redirect: <url>` (NOT `303 + swap-target`)
   - (c) HX-Redirect target route MUST be REGISTERED in app's route table (verify via `assert any(r.path == target for r in app.routes)` OR follow the redirect with a second TestClient call asserting 200)
6. **Hidden anchor 4-tier rejection ladder** per T3.SB1 — if T2.SB6 introduces any new hidden audit anchors (e.g., `proposed_pattern_class` for tamper detection per #2 above), use the 4-tier rejection pattern: malformed JSON / non-dict / dict missing required keys / dict with invalid value shapes → 400 + clear anchor on recovery. The `_reject_anchor` helper at `swing/web/routes/trades.py:899-910` is the reusable template.
7. **Recovery form anchor-clear discipline** per T3.SB1 R3 M#2 — on anchor-rejection 400 responses, recovery form MUST clear the bad anchor.
8. **`selected_X_audit_id` is AUDIT TRAIL, not DEDUPE KEY** per T3.SB2 R2 M3 — `/patterns/{candidate_id}/review` form may present multiple template_match_nearest_exemplar_ids; persistence dedupe must key off "what was persisted" (the `pattern_exemplars` row's actual `proposed_pattern_class`), not "what operator selected from N options".
9. **For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING at handler entry** per Phase 8 R2-R5 family + L10 LOCK semantic clarification — see #2 above for the POST-recompute extension.
10. **Server-recompute at POST time** is the canonical L10 LOCK interpretation per T3.SB3 R1 M#2 — verify NO `/patterns/{candidate_id}/review` POST handler consumes operator-submitted hidden fields as authoritative.

### §1.3 Inheritance from Theme 1 chart discipline (per spec §4.3 + §A.9 + §C.1 LOCK)

11. **Matplotlib mathtext LOCK** per CLAUDE.md gotcha "Matplotlib mathtext fires on `$`, `^`, `_`, and unbalanced `\` — silently italicizes intervening text" + spec §A.9 + §C.1 LOCK. Every renderer function in `swing/web/charts.py` MUST:
    - Use ASCII-only text in titles/labels/annotations
    - Apply `parse_math=False` to `fig.suptitle` as defense-in-depth
    - Add discriminating tests asserting no `$` / `^` / `_` in titles per `test_charts_no_dollar_or_caret_or_underscore_in_titles`
    - **Operator-witnessed browser verification BINDING** per Phase 10 §A.10 inheritance — string-equality tests CANNOT catch mathtext rendering issues; visual browser verification at S8 gate is REQUIRED for sign-off.
12. **HTMX OOB-swap partials must not lead with `<tr>`** per CLAUDE.md gotcha — if any chart-rendering response leads with table-row content, htmx.js `makeFragment` synthetic-table-wrap drops `<table>` content inside OOB chunks. Pre-empt: lead responses with `<div>` or `<section>` at the root.
13. **HTMX 4xx fragments need explicit config override** — `base.html.j2` contains `htmx.config.responseHandling` override enabling 4xx swapping; preserve if T2.SB6 touches base layout.
14. **`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM** — if T2.SB6 extends `BaseLayoutVM` with new fields (e.g., chart bytes for dashboard market weather), EVERY base-layout VM must gain that field (with safe default).
15. **OHLCV fetch scope = open-trade tickers ONLY** for the position-detail chart — do NOT union with watchlist or `active_tickers` (existing gotcha; preserve).

### §1.4 Inheritance from cache discipline (per §A.13 + §A.15 + T1.SB0 + T2.SB5 substrate)

16. **Hook fallback window-completeness** per T1.SB0 R3 M#1 lesson — `chart_renders` cache hooks MUST return FULL archive; consumers slice. Default to "full history, consumer slices".
17. **Session-anchor read/write predicate alignment** per §A.13 LOCK + Phase 8 `cfacbc5` precedent — `chart_renders` writer stamps `data_asof_date = last_completed_session(now())`; reader staleness predicate uses SAME `last_completed_session(now())`. Discriminating round-trip test at T-A.6.2 step 1.
18. **Cache invalidation pattern**: DELETE-then-INSERT atomic refresh wrapped in `BEGIN IMMEDIATE` / `COMMIT` per §A.12 + §A.15 (NO `INSERT OR REPLACE` on `chart_renders` — audit-trail discipline).
19. **External-API empty-result must be treated as transient when write-through-caching** per existing CLAUDE.md gotcha — `chart_renders` cache populated from `chart_svg_bytes` rendering MUST handle empty/error returns gracefully (retain existing cache row; do NOT blank on transient failure).
20. **Schwab `price_history` API defaults to MINUTE bars without explicit kwargs** per T1.SB0 gate-fix lesson — N/A for T2.SB6 directly (consumes OhlcvCache); but verify any new bar-source-ladder usage at T-A.6.6 dashboard market weather chart explicitly passes daily-bar kwargs.

### §1.5 Inheritance from broader Phase 13 + cumulative arc disciplines

21. **`Literal[...]` type hints are NOT runtime-enforced** per T-A.1.5b R3 M#1 — `CriterionRow.status: Literal['pass', 'fail']` + any new VM `Literal[...]` fields need explicit `__post_init__` frozenset validation.
22. **Constant placement LOCK** per plan §B.7 + Phase 12 C.A T-A.2 + T3.SB2 hotfix `cf3c489` discipline — `swing/web/charts.py` MUST IMPORT the `_CHART_SURFACE_VALUES` 5-tuple from `swing/data/models.py` (NOT redefine). Verify at T-A.6.1 Step 0.
23. **Bar-clipping at detector entry** (inherited from T2.SB3) — chart renderers consuming `bars` should clip to candidate window or chart window BEFORE rendering boundaries.
24. **NEW: Web server restart required after VM/template-affecting merges** (NEW forward-binding observation from T3.SB3 operator-paired S2 gate 2026-05-21 PM #2). The S2 stale-server defect surfaced via operator-witnessed gate ONLY — algorithmic fast E2E + unit tests cannot detect stale-server-vs-current-code drift because they exercise fresh Python imports in the test process. For T2.SB6: ANY view-model field addition + any template change requires `swing web` restart for operator verification. Recommend adding "restart `swing web` after merge" to cycle-checklist (operator-pre-housekeeping); banked at T2.SB6 dispatch for explicit Codex-watch coverage.
25. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 23rd cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)** — implementer dispatches focused reviewer subagent BEFORE invoking Codex MCP. **Expansion #1** (T3.SB2 hotfix `cf3c489` discipline): grep `swing/` for hardcoded duplicates of any new T2.SB6 constants (chart size tuples; render kwargs; surface enum values — verify `_CHART_SURFACE_VALUES` is the canonical site). **Expansion #2** (T2.SB4 R1 M1 lesson): cross-check spec §5.10 + §4.6 + §C.1-§C.5 BINDING text byte-for-byte vs brief sketches (8-item checklist; 6-decision enum; 4-criterion active-learning ranking; renderer function signatures per §C.1; cache architecture per §C.2; chart inventory per §C.5; PASS/FAIL Literal validation at CriterionRow).

---

## §2 Per-task acceptance criteria (per plan §G.9 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-A.6.1 | `swing/web/charts.py` SVG-inline renderer | 10+ discriminating tests pass per plan §G.9 step 1 enumeration: 5 renderer functions (`render_watchlist_thumbnail_svg` + `render_hyprec_detail_svg` + `render_position_detail_svg` + `render_market_weather_svg` + `render_theme2_annotated_svg`) covering 5 chart surfaces × known-good fixture bytes parity + 5 separate tests covering VCP + flat base + CWH + HTF + DBW annotation shapes + ASCII-only text invariant + no-mathtext-metacharacters defense-in-depth. **L7 LOCK**: NO mathtext; `parse_math=False` on `fig.suptitle` defense-in-depth; ASCII-only. **L8 LOCK**: `_CHART_SURFACE_VALUES` imported from `swing/data/models.py` (canonical site); NOT redefined. |
| T-A.6.2 | `chart_renders` cache write-through | 5+ tests pass per plan §G.9 step 1: run-bound cache (one row per ticker × surface × pipeline_run_id); position-detail cache (no pipeline_run_id; unique per ticker); theme2-annotated cache (unique per ticker × surface × pipeline_run_id × pattern_class); session-anchor round-trip alignment per §A.13; cache invalidation DELETE-then-INSERT atomic per §A.15 (NO INSERT OR REPLACE). Modify `_step_charts` to write through cache for each surface. Modify VM consumers to READ `get_cached_chart_svg(conn, ticker, surface, pipeline_run_id, pattern_class) -> bytes \| None`. |
| T-A.6.3 | `/patterns/{candidate_id}/review` review form | 10+ tests pass per plan §G.9 step 1: 8-item checklist render (proposed pattern class + geometric_score breakdown + top-3 template thumbnails + trend-template badge + RS rank + volume profile + uncertainty reason + outcome distribution); 6-decision enum (confirm / watch / reject / relabel / pattern_present_outside_window / multiple_overlapping_patterns); confirm + trade-opened → `label_source='organic_trade_history'`; confirm + no-trade → `label_source='closed_loop_review'`; relabel persists `final_pattern_class` (cross-column CHECK invariant #1 enforced); window-shift + multi-exemplar emit; `PatternReviewFormVM` extends `BaseLayoutVM`; banner fields populated per Codex R2 Major #3 closure. **L9 LOCK**: server-recompute `proposed_pattern_class` at POST per §1.1 #2. **L12 LOCK**: HTMX 3-surface discipline + HX-Redirect target `/patterns/queue` registered. |
| T-A.6.4 | `/patterns/queue` active-learning prioritization | 6+ tests pass per plan §G.9 step 1: `prioritize_candidates(conn, top_k=20)` per spec §5.10 4-criterion ranking (borderline geometric \|score-0.5\|<0.1; rule/template disagreement \|geometric-template\|>0.3; underrepresented regimes low historical exemplar count for current weather; failed-rule near-misses geometric in [0.55, 0.70]); `PatternQueueVM` extends `BaseLayoutVM` + banner fields. Implements `swing/patterns/active_learning.py:prioritize_candidates` pure function. **L11 LOCK**: BaseLayoutVM banner field population per forward-binding lesson #12. |
| T-A.6.5 | `/metrics/pattern-outcomes` 9th metric tile | 7+ tests pass per plan §G.9 step 1: per-pattern-class outcome distribution (X% triggered + Y% reached 1R + Z% hit stop); Wilson-CI badge at n≥5 per Phase 10 honesty; suppressed at n<5 per Phase 10 §5.1; composes with Phase 10 cohort architecture (`swing/metrics/cohort.py` + `honesty.py` reuse). `PatternOutcomesVM` extends `BaseLayoutVM` + banner field population. **L10 LOCK**: Phase 10 §A.18 discrepancies helper reused; new tile is ADDITIVE on top of shipped 8 Phase 10 tiles + 1 umbrella `/metrics` navigator. |
| T-A.6.6 | Theme 1 chart surface integration + dashboard market weather | 8+ tests pass per plan §G.9 step 1 (HTMX trinity coverage explicit per Codex R1 Major #4 closure): DashboardVM populates `dashboard_weather_chart_svg_bytes`; watchlist row VM inline thumbnail SVG bytes; hyp-rec detail VM 800x500 SVG; position detail VM 800x500 SVG with fill markers; `POST /dashboard/weather-chart/refresh` invalidates cache + regenerates; `hx-headers='{"HX-Request": "true"}'` propagation; `204 + HX-Redirect: /dashboard` (NOT 303); HX-Redirect target `/dashboard` registered in app routes. **L13 LOCK**: dashboard market weather chart at TOP per §C.3. **L14 LOCK**: `base.html.j2` BaseLayoutVM extended consistently across all 5 base-layout VMs (existing gotcha — DashboardVM + PipelineVM + JournalVM + WatchlistVM + PageErrorVM). |
| T-A.6.6b | `/patterns/exemplars` enhanced rendering | 8+ tests pass per plan §G.9 step 1 (Deficiency 1 fold-in from T-A.1.6): chart per exemplar (consumes existing `render_theme2_annotated_svg` from T-A.6.1 — NO new renderer code); per-criterion PASS/FAIL table from `labeler_evidence_json.rule_criteria`; narrative text from `labeler_evidence_json.narrative`; cache-hit path consumes `chart_renders`; cache-miss path invokes renderer once; graceful at missing chart_renders + malformed labeler_evidence_json. **L15 LOCK**: `CriterionRow.status: Literal['pass', 'fail']` has `__post_init__` frozenset validation per CLAUDE.md gotcha. **L16 LOCK**: ASCII-only on narrative text; NO `→` / `§` / em-dash via Jinja literals. **L17 LOCK**: reuse `render_theme2_annotated_svg` from T-A.6.1 — do NOT duplicate matplotlib code. |
| T-A.6.7 | T2.SB6 closer — integration E2E + ruff sweep + 2 cross-bundle pin un-skips | Fast E2E PASS: seeds full happy path (pipeline run → pattern_evaluations rows → chart_renders cache → /patterns/queue lists → /patterns/{id}/review renders + POST persists → /metrics/pattern-outcomes renders cohort outcomes → /patterns/exemplars renders chart + criteria + narrative). Cross-bundle pin un-skips: (1) `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` per plan §H.3 row 10; (2) `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11. Verify pin status via `git grep "@pytest.mark.skip"` at Step 1 (other pins may also be stale; same pattern as T2.SB5 + T3.SB3 lag closures). |

**Recommended ordering**: T-A.6.1 (renderers; pure functions; no dependencies — substrate for all downstream tasks) → T-A.6.2 (cache write-through; sequential prerequisite for VM consumers) → T-A.6.3 (review form; consumes T-A.6.1 + T-A.6.2) → T-A.6.4 (active-learning queue; consumes pattern_evaluations only) → T-A.6.5 (metric tile; composes with Phase 10) → T-A.6.6 (Theme 1 chart integration; consumes T-A.6.1 + T-A.6.2) → T-A.6.6b (exemplars enhancement; consumes T-A.6.1 renderer + T-A.6.2 cache) → T-A.6.7 (closer + cross-bundle pin work).

---

## §3 Files in scope

**Create** (3 production modules + 4 VM modules + 4 Jinja templates + 4 test files):
- `swing/web/charts.py` — 5 SVG-inline renderer functions per §C.1 LOCK; ASCII-only; `parse_math=False`; imports `_CHART_SURFACE_VALUES` from `swing/data/models.py`.
- `swing/patterns/active_learning.py` — `prioritize_candidates(conn, top_k=20) -> list[CandidatePriority]` pure function per spec §5.10 4-criterion ranking.
- `swing/web/view_models/patterns/review_form.py` — `PatternReviewFormVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/queue.py` — `PatternQueueVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/outcomes_card.py` — `PatternOutcomesVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/annotated_chart.py` — shared annotated chart VM shape (Theme 1+Theme 2).
- `swing/web/templates/patterns/review.html.j2` — review form template.
- `swing/web/templates/patterns/queue.html.j2` — active-learning queue template.
- `swing/web/templates/patterns/outcomes.html.j2` — pattern-outcomes metric tile template.
- `swing/web/templates/patterns/annotated_chart_partial.html.j2` — shared chart partial.
- `tests/web/test_charts.py` — 10+ renderer unit tests (T-A.6.1).
- `tests/web/test_routes/test_patterns_review.py` — 10+ route handler tests (T-A.6.3).
- `tests/web/test_routes/test_patterns_queue.py` — 6+ tests (T-A.6.4).
- `tests/web/test_routes/test_metrics_pattern_outcomes.py` — 7+ tests (T-A.6.5).
- `tests/integration/test_phase13_t2_sb6_closed_loop_e2e.py` — 1 fast E2E (T-A.6.7).

**Modify**:
- `swing/web/routes/patterns.py` — add `/patterns/{candidate_id}/review` GET + POST; `/patterns/queue` GET; extend `/patterns/exemplars` for T-A.6.6b Deficiency 1 fold-in.
- `swing/web/routes/metrics.py` — add `/metrics/pattern-outcomes` 9th tile.
- `swing/web/routes/dashboard.py` — extend DashboardVM with market weather chart field; add `POST /dashboard/weather-chart/refresh`.
- `swing/pipeline/runner.py:_step_charts` — write `chart_renders` cache rows for 5 surfaces (watchlist + hyprec + position + market_weather + theme2_annotated).
- `swing/web/view_models/dashboard.py` — extend DashboardVM with `dashboard_weather_chart_svg_bytes: bytes | None = None`.
- `swing/web/view_models/watchlist.py` — extend WatchlistVM per-row with inline thumbnail SVG bytes.
- `swing/web/view_models/recommendations.py` — extend RecommendationsVM (hyp-rec) with detail chart SVG bytes.
- `swing/web/view_models/patterns/exemplars.py` (existing from T-A.1.6) — extend with `chart_svg_bytes` + `criterion_rows` + `narrative_text` per T-A.6.6b.
- `swing/web/templates/dashboard.html.j2` — render market weather at TOP per §C.3.
- `swing/web/templates/patterns/exemplars.html.j2` — render chart `<img>` (SVG inline) + criteria `<table>` + narrative `<p>` per exemplar (T-A.6.6b).
- `tests/web/test_routes/test_patterns_exemplars.py` (existing from T-A.1.6) — extend with 8 new tests for T-A.6.6b.
- `tests/pipeline/test_step_charts.py` (likely existing from T1.SB0) — extend with `chart_renders` cache write-through tests.

**Verify at T-A.6.7 cross-bundle pin status check**:
- `tests/<somewhere>/test_theme1_theme2_shared_renderer_handles_5_v1_patterns` per plan §H.3 row 10 — un-skip OR plant + un-skip per plan precedent (verify existence via `git grep` at Step 1).
- `tests/<somewhere>/test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 — un-skip OR plant + un-skip.

**NOT in scope (V2 / future sub-bundles)**:
- T4.SB Q4 close-tracking flag (separate sub-bundle per plan §G.10; awaits PAUSE-FOR-LIST-ADDITIONS first)
- Interactive client-side JS chart library (V2 per §C.6 + §4.7)
- Per-row sparklines in `/trades/` + `/watchlist/` (V2 per §C.6)
- Multi-timeframe chart toggle (V2 per §C.6)
- Annotation editor (V2 per §C.6)
- Schema changes (v20 LOCKED per spec §B.4; all required columns already landed at T-A.1.1)
- ZERO new Schwab API calls (T2.SB6 has zero Schwab dependencies; chart data via OhlcvCache + pattern_evaluations + chart_renders cache only)
- Phase 13.5 drift surfaces (separate dispatch per spec §5.11; un-blocked at ≥1 month feature_distribution_log_json accumulation)

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T2.SB6-specific watch items

1. **Spec §5.10 + §4.6 + §C.1-§C.5 LOCK fidelity**: every renderer signature + cache key shape + 8-item checklist order + 6-decision enum + 4-criterion ranking MUST match spec verbatim. Implementer SHOULD grep spec; do NOT paraphrase. **Cross-check spec source-of-truth against this brief's prescriptions per C.C lesson #6 Expansion #2 BINDING** (§1.5 #25).
2. **§C.1 matplotlib mathtext LOCK**: ASCII-only text in all renderer titles/labels/annotations; `parse_math=False` on `fig.suptitle` defense-in-depth; discriminating tests assert no `$` / `^` / `_` in titles. **Operator-witnessed browser verification at S8 BINDING** per Phase 10 §A.10 inheritance.
3. **§C.2 cache key shape LOCK**: run-bound surfaces key on `(ticker, surface, pipeline_run_id)`; position-detail keys on `(ticker, surface)` with `pipeline_run_id=NULL`; theme2-annotated keys on `(ticker, surface, pipeline_run_id, pattern_class)`.
4. **§C.2 cache invalidation pattern**: DELETE-then-INSERT atomic refresh wrapped in `BEGIN IMMEDIATE` / `COMMIT`. NO `INSERT OR REPLACE` per §A.15.
5. **§C.3 dashboard market weather TOP placement** per §C.3 LOCK — above existing Phase 10 metrics tile navigator AND above Phase 12 reconciliation banner.
6. **§5.10 8-item checklist ordering LOCK**: render order MUST match spec §5.10 lines 766-775 verbatim (proposed class → geometric breakdown → top-3 templates → trend badge → RS rank → volume profile → uncertainty reason → outcome distribution).
7. **§5.10 6-decision enum LOCK**: confirm / watch / reject / relabel / pattern_present_outside_window / multiple_overlapping_patterns. Each maps to `pattern_exemplars.final_decision` per spec §5.10 lines 785-794 verbatim.
8. **§5.10 label_source semantic split per Codex R4 M#1 LOCK**: `label_source='closed_loop_review'` if NO trade opened; `label_source='organic_trade_history'` if confirm + trade opened (resolved via `trades.candidate_id` backlink).
9. **§5.10 4-criterion active-learning ranking LOCK** per spec §5.10 lines 796-801: borderline geometric \|score-0.5\|<0.1; rule/template disagreement \|geometric-template\|>0.3; underrepresented regimes (low historical exemplar count for current weather); failed-rule near-misses geometric in [0.55, 0.70].
10. **§4.6 annotated chart per-pattern annotation LOCK** per spec §4.6 lines 416-420 verbatim per pattern: VCP contraction markers + pivot line; flat base top/bottom + ATR shading + duration; CWH cup edges + handle markers + depth ratio; HTF pole markers + consolidation box + days-tight; DBW trough_1 + center_peak + trough_2 + optional undercut.

### §4.2 Pipeline + cache integration watch items (T-A.6.2 + T-A.6.6)

11. **Server-recompute at POST time for `/patterns/{candidate_id}/review`** per §1.1 #2 LOCK — POST handler MUST re-derive `proposed_pattern_class` from `pattern_evaluations.pattern_class` for the candidate_id; tampered hidden inputs MUST NOT be authoritative.
12. **Read-path mapper extension for `pattern_exemplars`** per T3.SB3 R1 M#1 lesson — if T2.SB6 writes any new column on `pattern_exemplars` (likely via `labeler_evidence_json` extension), grep ALL `_row_to_pattern_exemplar` mappers in `swing/data/repos/pattern_exemplars.py` + extend in the SAME task with column-position comments.
13. **HTMX 3-surface discipline** for all 4 NEW POST routes (`/patterns/{id}/review`, `/dashboard/weather-chart/refresh`, etc.).
14. **`base.html.j2` shared-VM-field propagation** — if DashboardVM gains `dashboard_weather_chart_svg_bytes`, verify ALL 5 base-layout VMs (DashboardVM + PipelineVM + JournalVM + WatchlistVM + PageErrorVM) carry the field with safe default.
15. **OHLCV fetch scope = open-trade tickers ONLY** for position-detail chart (existing CLAUDE.md gotcha; preserve).
16. **Session-anchor read/write predicate alignment** per §A.13 LOCK — `chart_renders` writer + reader MUST use SAME `last_completed_session(now())`. Discriminating round-trip test pattern (Phase 8 `cfacbc5` precedent).

### §4.3 T-A.6.6b Deficiency 1 fold-in watch items

17. **Reuse `swing/web/charts.py:render_theme2_annotated_svg`** from T-A.6.1 — do NOT duplicate matplotlib code. Reuse `get_cached_chart_svg` from T-A.6.2.
18. **`CriterionRow.status: Literal['pass', 'fail']` runtime validation** per CLAUDE.md gotcha "`Literal[...]` not runtime-enforced" — add `__post_init__` frozenset validation.
19. **ASCII-only on narrative text rendering** — Jinja literals MUST NOT introduce `→` / `§` / em-dash; matplotlib mathtext caveat applies if narrative renders into chart annotations.
20. **Graceful at missing chart_renders + malformed labeler_evidence_json** per T-A.6.6b acceptance criteria — page MUST render placeholder, NOT 500.

### §4.4 Cross-bundle pin + cumulative process discipline (T-A.6.7)

21. **Cross-bundle pin un-skips at T-A.6.7 closer**:
    - `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` per plan §H.3 row 10 (planted at T2.SB6 T-A.6.1; un-skips here)
    - `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 (un-skips at T2.SB6 + T4.SB Q4 service)
    - Verify other plan §H.3 pins via `git grep "@pytest.mark.skip"` (same lag-closure pattern as T2.SB5's `test_pattern_exemplars_schema_shape_invariant` + T3.SB3's `test_ohlcv_cache_get_or_fetch_invariant`).
22. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 23rd cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)** — implementer dispatches focused reviewer subagent with brief §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. Reference: 22nd cumulative validation BANKED CLEAN at T3.SB3 with both expansions applied + 1 MAJOR + 2 MINORs caught BEFORE Codex.
    - **Expansion #1** (T3.SB2 hotfix `cf3c489` discipline): grep `swing/` for hardcoded duplicates of any new T2.SB6 constants (chart size tuples like `(200, 100)` / `(800, 500)`; render kwargs; surface enum values — verify `_CHART_SURFACE_VALUES` is the canonical site at `swing/data/models.py`).
    - **Expansion #2** (T2.SB4 R1 M1 lesson): cross-check spec §5.10 + §4.6 + §C.1-§C.5 BINDING text byte-for-byte vs brief sketches (8-item checklist + 6-decision enum + 4-criterion ranking + renderer function signatures + cache architecture + chart inventory).
23. **NO `Co-Authored-By` footer** — cumulative ~318+ commit streak ZERO trailer drift through T3.SB3 + housekeeping; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): explicit citation in commit messages required.
24. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory `feedback_worktree_cli_invocation`).
25. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun); chart renderer internal logging via stdlib logger handles encoding.
26. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite.
27. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 + T3.SB3 commit-message precedent).
28. **TDD discipline per task** via `superpowers:test-driven-development` (write failing test → see fail → minimal implementation → see pass → commit).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 8 T-A.6.X tasks committed per plan §G.9 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5463 + ~100-150 new fast tests = ~5563-5613 total + 2 un-skips from T-A.6.7 closer = ~5565-5615; 0 failures; ≤2 skipped (un-skips per §1 above adjust net).
- [ ] `python -m pytest -m slow tests/integration/test_phase13_t2_sb6_*.py -q` PASS if T-A.6.7 includes any slow E2E (verify at recon; likely fast-only per plan §G.9 T-A.6.7 step 1).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20 (no migrations; all required columns landed at T-A.1.1).
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (23rd cumulative C.C lesson #6 validation expected CLEAN with BOTH scope expansions applied).
- [ ] All commits on branch `phase13-t2-sb6-closed-loop-surface` have empty `Co-Authored-By` trailer.
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 3-5 rounds for largest-scope sub-bundle; T2.SB4 took 5 rounds; T2.SB5 + T3.SB3 took 2 rounds each via the inherited pre-Codex disciplines paying off).

### §5.2 S2-S8 (operator-paired post-merge per plan §G.9 lines 2294-2304)

- **S2 (browser)**: `/dashboard` → confirm market weather chart at TOP per §C.3
- **S3 (browser)**: `/patterns/queue` → confirm active-learning prioritization renders top-K candidates
- **S4 (browser)**: `/patterns/{id}/review` for a real candidate → confirm 8-item checklist renders + decision form submits + persistence to `pattern_exemplars`
- **S4b (browser)**: `/patterns/exemplars` → confirm chart + per-criterion table + narrative rendered per exemplar (T-A.6.6b Deficiency 1 fold-in)
- **S5 (browser)**: `/metrics/pattern-outcomes` → confirm per-pattern-class outcome distributions + Wilson-CI badges
- **S6 (browser)**: hyp-rec detail page → confirm annotated chart renders with pattern boundaries
- **S7 (browser)**: position detail page → confirm fill markers + current stop line + MFE/MAE shading
- **S8 (visual)**: operator browser-DevTools verification of SVG renderability — NO mathtext mishaps per §A.9 LOCK; ASCII-only text verified visually

**Important operational reminder per NEW forward-binding observation #24**: operator MUST restart `swing web` after T2.SB6 merge so the new ReviewVM + chart-related VM fields are loaded into the running Python process. Stale-server-vs-current-code drift is invisible to fast E2E + unit tests; ONLY surfaces at operator-witnessed browser gates.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.10 + §4.6 + §C.1-§C.5 BINDING text verbatim. 8-item checklist order; 6-decision enum; 4-criterion active-learning ranking; renderer function signatures; cache architecture; chart inventory.
- **L2**: ZERO new Schwab API calls (T2.SB6 consumes OhlcvCache + pattern_evaluations + chart_renders + Phase 10 metrics only).
- **L3**: ZERO schema changes (v20 LOCKED; all required columns landed at T-A.1.1 migration 0020).
- **L4**: Cross-bundle pin un-skips at T-A.6.7 closer per plan §H.3 rows 10 + 11.
- **L5**: Branch base = main HEAD `4e71787` at dispatch time. Verify at T-A.6.1 Step 0: `git merge-base --is-ancestor 4e71787 HEAD` returns 0.
- **L6**: Frozen dataclasses (`CandidatePriority` + `CriterionRow` + new VM types) carry `__post_init__` Literal[...] frozenset validation honoring T-A.1.5b R3 M#1 gotcha.
- **L7**: `swing/web/charts.py` ASCII-only text; `parse_math=False` on `fig.suptitle` defense-in-depth; NO `$` / `^` / `_` in titles. Operator-witnessed S8 BINDING.
- **L8**: `_CHART_SURFACE_VALUES` 5-tuple IMPORTED from `swing/data/models.py` (canonical site per plan §B.7 + Phase 12 C.A T-A.2 + T3.SB2 hotfix `cf3c489` discipline). Verify at T-A.6.1 Step 0 via `git grep "_CHART_SURFACE_VALUES"`.
- **L9**: `/patterns/{candidate_id}/review` POST handler SERVER-RECOMPUTES `proposed_pattern_class` from `pattern_evaluations` for the candidate_id (NOT consume operator-submitted hidden input as authoritative) per T3.SB3 R1 M#2 lesson.
- **L10**: 9th metric tile (`/metrics/pattern-outcomes`) COMPOSES with Phase 10 cohort + honesty architecture; ADDITIVE on top of shipped 8 metric tiles; NOT a replacement.
- **L11**: `PatternQueueVM` + `PatternReviewFormVM` + `PatternOutcomesVM` + extended `ExemplarsVM` all extend `BaseLayoutVM` + populate banner fields (`unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count`).
- **L12**: HTMX 3-surface discipline (HX-Request propagation + HX-Redirect-success + HX-Redirect-target-registered) per cumulative form-driven inheritance.
- **L13**: Dashboard market weather chart at TOP per §C.3 (above Phase 10 metrics tile navigator + Phase 12 reconciliation banner).
- **L14**: `base.html.j2` shared-VM-field propagation — DashboardVM extension propagates to ALL 5 base-layout VMs.
- **L15**: `CriterionRow.status: Literal['pass', 'fail']` `__post_init__` frozenset validation per `Literal[...]` gotcha.
- **L16**: ASCII-only on narrative text rendering — Jinja literals MUST NOT introduce non-ASCII glyphs.
- **L17**: T-A.6.6b reuses `render_theme2_annotated_svg` from T-A.6.1 — do NOT duplicate matplotlib code.
- **L18**: `chart_renders` cache invalidation: DELETE-then-INSERT atomic per §A.15 + `BEGIN IMMEDIATE` / `COMMIT` per §A.12. NO `INSERT OR REPLACE`.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.9 lines 2109-2306 (T2.SB6 verbatim 8-task spec) + §C lines 389-477 (Theme 1 architectural LOCKs) + §H.3 cross-bundle pin schedule rows 10 + 11.
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §5.10 Closed-loop surface (lines 760-801; 8-item checklist + 6-decision enum + label_source semantic split + 4-criterion active-learning ranking)
  - §4.6 Theme 2 annotated chart deliverable (lines 412-424; per-pattern annotation specs)
  - §4.3 Chart rendering technology LOCK (matplotlib SVG inline)
  - §4.4 Cache architecture LOCK (`chart_renders` schema + caching semantics)
  - §4.5 Market weather mini-chart placement
  - §A.9 Matplotlib mathtext LOCK + ASCII-only discipline
  - §A.13 Session-anchor read/write predicate alignment
  - §A.15 No INSERT OR REPLACE on audit-trail tables
- **T3.SB3 return report** at `docs/phase13-t3-sb3-return-report.md` §6 — 4 forward-binding lessons inherited (read-path mapper + server-recompute at POST + audit envelope empty-state + pre-Codex review BOTH expansions).
- **T2.SB5 return report** at `docs/phase13-t2-sb5-return-report.md` §8 — bad-exemplar isolation + DTW Sakoe-Chiba band infeasibility + universe histogram POST-template lessons.
- **T-A.1.6 implementer artifacts** at `swing/web/routes/patterns.py:patterns_exemplars` + `swing/web/view_models/patterns/exemplars.py` + `swing/web/templates/patterns/exemplars.html.j2` (existing; T-A.6.6b extends).
- **Phase 10 metrics architecture** at `swing/metrics/cohort.py` + `swing/metrics/honesty.py` + `BaseLayoutVM` mixin (Phase 10 §A.18 helper; reused at T-A.6.5).
- **v20 migration** at `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` lines 47-115 (`chart_renders` table) + line 410 (`review_log.auto_populated_field_keys_json`) — all required columns already landed at T-A.1.1.
- **CLAUDE.md gotchas relevant to T2.SB6** (read at brief recon):
  - Matplotlib mathtext fires on `$` / `^` / `_` / unbalanced `\` (BINDING per L7)
  - HTMX OOB-swap partials that hand-duplicate full-page markup drift silently
  - HTMX response leading with `<tr>` triggers `makeFragment` synthetic-table-wrap
  - HTMX 4xx fragments need explicit config override
  - `base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM
  - HTMX form-driven endpoints have 3 browser-only failure surfaces TestClient cannot detect (HX-Request + HX-Redirect + HX-Redirect-target-registered)
  - `Literal[...]` not runtime-enforced
  - Session-anchor read/write mismatch family
  - Schema-CHECK widening MUST audit ALL Python-side surface guards (per T3.SB2 hotfix `cf3c489`)
  - Read-path mapping must keep pace with write-path on widened columns (per T3.SB3 R1 M#1)
  - "Server-stamped" hidden inputs STILL tampering surfaces unless POST RECOMPUTES (per T3.SB3 R1 M#2)
  - Bad-exemplar isolation in retrieval functions (per T2.SB5 R1 M#1)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB6 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB6 SHIPPED + 23rd cumulative C.C lesson #6 validation (if CLEAN); mention any NEW gotchas surfaced. **Bank NEW gotcha #24 (web server restart required after VM/template-affecting merges) regardless of T2.SB6 Codex outcome** (banked at T3.SB3 S2 operator-paired gate; codify in CLAUDE.md at next housekeeping).
2. **phase3e-todo.md** — new top entry for T2.SB6 SHIPPED with Codex chain shape + ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T4.SB inheritance + cross-bundle pin closure notes + any new V2 candidates.
3. **orchestrator-context.md** — refresh current state; demote former current (T3.SB3) to Prior #1; archive-split per size-check trigger (Prior count post-this-demote will be 11 — over cap; archive oldest at line ~142+ per the established T2.SB5 + T3.SB3 housekeeping precedent).
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank 23rd cumulative C.C lesson #6 validation (if CLEAN); bank ~330+ cumulative ZERO Co-Authored-By streak (T2.SB6 expected ~10-15 commits including Codex fix bundles for the largest scope sub-bundle).
6. **PHASE 13 DISPATCH SEQUENCE — SURFACE THE PAUSE-FOR-LIST-ADDITIONS** per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory. Orchestrator action: AFTER T2.SB6 housekeeping commit, surface the pause in operator update + DO NOT commission T4.SB dispatch brief without operator's added items.

---

## §9 Forward-binding to T4.SB closer

T4.SB = Usability triage + Q4 close-tracking flag + metrics-dashboard hooked-up audit (8 tasks + operator-added items per plan §G.10). **PAUSE-FOR-LIST-ADDITIONS BINDING** between T2.SB6 SHIPPED + housekeeping and T4.SB dispatch brief commissioning per `project_phase13_t4_sb_pause_for_list_additions` memory.

**Forward-binding lessons expected from T2.SB6 to T4.SB:**
- Matplotlib mathtext LOCK + operator-witnessed visual gate (BINDING for T4.SB Q4 if any new chart surface introduces text).
- `chart_renders` cache write-through pattern (T4.SB Q4 close-tracking flag may consume this for any watchlist-row chart annotation).
- HTMX 3-surface discipline (T4.SB Q4 `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag` routes inherit).
- BaseLayoutVM banner field propagation (every new T4.SB VM extends BaseLayoutVM).
- Server-recompute at POST per T3.SB3 R1 M#2 + extended at T2.SB6 (if T4.SB introduces any operator-toggleable form state, recompute server-side at POST).
- Web server restart discipline (gotcha #24; BINDING for any T4.SB merge affecting VMs/templates).
- 23rd → 24th cumulative C.C lesson #6 validation with BOTH scope expansions applied (sets precedent for T4.SB dispatch).
- ZERO `Co-Authored-By` trailer streak (~330+ cumulative commits expected post-T2.SB6 merge + housekeeping).

---

*End of dispatch brief. Phase 13 T2.SB6 (8 tasks; +100-150 fast tests + 1 fast E2E + 2 cross-bundle pin un-skips projected; v20 schema UNCHANGED; ZERO Schwab API calls) — closed-loop surface + Theme 1 annotated charts + T-A.1.6 Deficiency 1 fold-in completing the Phase 13 Theme 1 + Theme 2 visible architecture. Inherits T3.SB3 forward-binding lessons (read-path mapper + server-recompute at POST + audit envelope empty-state + pre-Codex review BOTH expansions) + T2.SB5 forward-binding lessons (bad-exemplar isolation + DTW infeasibility + universe histogram POST-template) + cumulative Phase 13 disciplines (HTMX 3-surface + matplotlib mathtext + base layout VM propagation + Literal runtime validation + session-anchor alignment + cache invalidation DELETE-then-INSERT). 3-5 Codex rounds expected for largest-scope sub-bundle. **23rd cumulative C.C lesson #6 validation expected with BOTH SCOPE EXPANSIONS BINDING** (grep `swing/` for hardcoded duplicates of any new T2.SB6 constants + cross-check spec §5.10 + §4.6 + §C.1-§C.5 BINDING text byte-for-byte vs brief sketches). **PAUSE-FOR-LIST-ADDITIONS BINDING at T2.SB6 SHIPPED + housekeeping boundary BEFORE T4.SB dispatch.** ZERO Co-Authored-By footer drift streak (~318+ commits at handoff) preserved.*
