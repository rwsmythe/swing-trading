# Phase 13 T2.SB6b — Closed-loop routes + Theme 1 chart integration + T-A.1.6 Deficiency 1 fold-in dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 PM #3 post-T2.SB6a substrate merge + housekeeping at main HEAD `040455b`. **6 deferred T2.SB6 tasks** + 1 closer (T-A.6.3 review form + T-A.6.4 queue + T-A.6.5 metric tile + T-A.6.6 chart-surface integration + T-A.6.6b exemplars enhancement + T-A.6.7 closer). ~T2.SB5-sized scope (+80-130 fast tests + 1 fast E2E + 1 cross-bundle pin row 11 un-skip projected per plan §H). Per plan §G.9 lines 2164-2305 (the 6 tasks deferred from the original T2.SB6 brief).

**Branch:** `phase13-t2-sb6b-closed-loop-routes` — branches from main HEAD `040455b` at dispatch time (post-T2.SB6a substrate merge + housekeeping). **FRESH BRANCH** — NOT a continuation of `phase13-t2-sb6-closed-loop-surface` (that branch closed cleanly at T2.SB6a merge `340f868`).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb6b-closed-loop-routes phase13-t2-sb6b-closed-loop-routes`.

**Time estimate:** orchestrator wall-clock 6-10 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T2.SB6b is ~T2.SB5-sized — 6 tasks; T2.SB5 was 6 tasks at +50-80 fast tests; T2.SB6b is +80-130 fast tests; substrate is FROZEN so no renderer/cache work required; routes + VMs + templates only).

**⚠ PAUSE-FOR-LIST-ADDITIONS BINDING reminder**: per `project_phase13_t4_sb_pause_for_list_additions` memory, **the scheduled pause is between T2.SB6b SHIPPED + housekeeping and T4.SB dispatch brief commissioning**. Orchestrator MUST surface the pause at the T2.SB6b SHIPPED + housekeeping boundary; T4.SB will NOT be dispatched without operator's added items.

---

## §1 Scope summary

**Closed-loop pattern review routes + Theme 1 chart surface integration + T-A.1.6 Deficiency 1 fold-in per spec §5.10 + §4.6 + §C.3 + plan §G.9 (6 deferred tasks from original T2.SB6 partial-completion).** Consumes the FROZEN substrate API surface from T2.SB6a (5 renderer functions in `swing/web/charts.py` + 2 cache helpers in `swing/data/repos/chart_renders.py` + `ChartRender.__post_init__` validators per §C.2 semantic contract).

| Task | Title | Tests target |
|---|---|---|
| T-A.6.3 | `/patterns/{candidate_id}/review` review form (8-item checklist + 6-decision enum + label_source semantic split) | 10+ tests |
| T-A.6.4 | `/patterns/queue` active-learning prioritization per spec §5.10 4-criterion ranking | 6+ tests |
| T-A.6.5 | `/metrics/pattern-outcomes` 9th metric tile per OQ-10 (composes with Phase 10) | 7+ tests |
| T-A.6.6 | Theme 1 chart surface integration + dashboard market weather + `POST /dashboard/weather-chart/refresh` | 8+ tests |
| T-A.6.6b | `/patterns/exemplars` enhanced rendering (T-A.1.6 Deficiency 1 fold-in) | 8+ tests |
| T-A.6.7 | T2.SB6b closer — integration E2E + ruff sweep + cross-bundle pin row 11 un-skip | 1 fast E2E + 1 cross-bundle pin closure |

Per plan §G.9 verbatim (6 of 8 tasks). Cross-bundle pin work at T-A.6.7 closer:
- **UN-SKIP** `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 (un-skip at T2.SB6 + T4.SB closer when used) — verify status via `git grep "@pytest.mark.skip"` at Step 1; un-skip OR plant + un-skip per plan precedent.
- Verify other plan §H.3 pin status (rows 10 already closed at T2.SB6a substrate; row 11 closes here).

### §1.1 Inheritance from T2.SB6a (substrate) — FROZEN API SURFACE

T2.SB6b consumes the substrate API surface verbatim post-Codex; **NO modifications to substrate code** (per T2.SB6a L1 LOCK preservation). The substrate provides:

1. **5 renderer functions in `swing/web/charts.py`** (524 lines on main HEAD `040455b`):
   - `render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines) -> bytes` (200×100 SVG; price + MA + volume bars per §C.5 line 449)
   - `render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation=None) -> bytes` (800×500 SVG; price + MA + volume + pattern boundaries from `structural_evidence_json`)
   - `render_position_detail_svg(*, ticker, bars, trade, fills, current_stop) -> bytes` (800×500 SVG; price + MA + fill markers + current stop line + MFE/MAE shading)
   - `render_market_weather_svg(*, bars, trend_template_state) -> bytes` (400×150 SVG; SPY + MA + volume + trend-template badge)
   - `render_theme2_annotated_svg(*, ticker, bars, pattern_evaluation, exemplar_thumbnails=None) -> bytes` (800×600 SVG with overlay panel; per-pattern annotations per §C.4 + top-3 historical thumbnails)
2. **2 cache helpers in `swing/data/repos/chart_renders.py`**:
   - `get_cached_chart_svg(conn, ticker, surface, pipeline_run_id=None, pattern_class=None) -> bytes | None` (per §C.2 cache key shapes)
   - `refresh_chart_render(conn, chart_render: ChartRender) -> None` (DELETE-then-INSERT atomic per §A.15; BEGIN IMMEDIATE/COMMIT per §A.12)
3. **`ChartRender.__post_init__` validators** (per T2.SB6a Codex R1 fixes):
   - §C.2 cache key shape invariants (run-bound surfaces require non-NULL `pipeline_run_id`; `position_detail` requires NULL `pipeline_run_id`; `theme2_annotated` requires both `pattern_class` + `pipeline_run_id`)
   - Non-empty `chart_svg_bytes` guard (F6 defense at construction barrier)
4. **`_CHART_SURFACE_VALUES` 5-tuple** at `swing/data/models.py:75` (canonical site; T2.SB6b VMs + routes IMPORT from there; NEVER redefine)

### §1.2 Inheritance from T2.SB6a forward-binding lessons (24th cumulative C.C lesson #6 BINDING with BOTH SCOPE EXPANSIONS + 3 NEW PROPOSALS)

T2.SB6a banked 3 NEW scope expansion proposals from the FIRST BREAK in the 22-cumulative pre-Codex CLEAN streak. **ALL 5 expansions BINDING for T2.SB6b pre-Codex review** (per T2.SB6a return report §6.1):

5. **Expansion #1 (T3.SB2 hotfix `cf3c489` discipline; original)**: grep `swing/` for hardcoded duplicates of any new T2.SB6b constants. Specifically: route path strings (e.g., `/patterns/queue` / `/dashboard/weather-chart/refresh`); ranking constants (e.g., `geometric_score_borderline_band = 0.1`; `rule_template_disagreement_threshold = 0.3`); 6-decision enum (`PATTERN_REVIEW_DECISIONS = frozenset({"confirm", "watch", "reject", "relabel", "pattern_present_outside_window", "multiple_overlapping_patterns"})`); cohort-outcome thresholds.
6. **Expansion #2 (T2.SB4 R1 M1 lesson; original)**: cross-check brief prescriptions against spec §5.10 + §4.6 + §C.3 BINDING text byte-for-byte. Verify 8-item checklist render order matches spec §5.10 lines 766-775 verbatim; 6-decision enum matches lines 778-783 verbatim; 4-criterion ranking matches lines 796-801 verbatim; `label_source` semantic split per Codex R4 M#1 LOCK (`closed_loop_review` vs `organic_trade_history`); dashboard weather TOP placement per §C.3.
7. **NEW Expansion #3 (T2.SB6a R1 CRITICAL #1; schema-CHECK-vs-semantic-contract gap audit)**: any dataclass `__post_init__` that mirrors a schema CHECK MUST also mirror SEMANTIC contracts layered atop (cache key shapes; partial-index existence semantics; cross-column uniqueness via partial UNIQUE only). For T2.SB6b: if any new VM dataclasses are introduced (`PatternReviewFormVM` / `PatternQueueVM` / `PatternOutcomesVM`), verify each `__post_init__` covers BOTH the schema CHECK (if it mirrors one) AND the SEMANTIC contract from spec/plan. **Anchor: T2.SB6a CRITICAL #1** — `chart_renders` schema CHECK permitted `(surface='watchlist_row', pipeline_run_id=NULL)` invisible to canonical reader because §C.2 SEMANTIC cache key contract extends beyond schema CHECK. Pre-Codex review MUST enumerate every semantic invariant from spec/plan on tables touched by the substrate + verify validator mirrors EACH.
8. **NEW Expansion #4 (T2.SB6a R1 MAJOR #2; CLAUDE.md gotcha specific-scenario trace)**: each cumulative gotcha cited in this brief (§4 watch items + §6 LOCKs) MUST be walked through a SPECIFIC failure scenario in the substrate code path — NOT generic "is the lesson applied" sufficiency check. For T2.SB6b: enumerate gotcha + specific scenario per item:
   - "Server-stamped" hidden form inputs STILL tampering surfaces (T3.SB3 R1 M#2) → trace: operator submits tampered `proposed_pattern_class="vcp"` for flat_base candidate; assert POST RECOMPUTES from `pattern_evaluations` + persists `flat_base` not the tampered value
   - HTMX HX-Redirect target route registered (Phase 6 I3) → trace: `/patterns/{id}/review` POST returns `HX-Redirect: /patterns/queue`; assert `/patterns/queue` is registered in app.routes
   - `... or None` SQL nullability (Phase 6 deviation #3) → trace: empty form field → POST persists NULL not empty-string (if any new nullable CHECK columns introduced)
   - Read-path mapping must keep pace with write-path (T3.SB3 R1 M#1) → trace: any new column written by T2.SB6b POST MUST be in `_row_to_pattern_exemplar` mapper
   - `Literal[...]` runtime validation (T-A.1.5b R3 M#1) → trace: any new dataclass `Literal[...]` field has `__post_init__` frozenset validation
9. **NEW Expansion #5 (T2.SB6a R1 MAJOR #3; cross-section spec inventory grep)**: extend byte-fidelity scope to ALL spec/plan sections cited in substrate docstrings, NOT just brief-explicit LOCK'd sections. For T2.SB6b: grep production code under `swing/web/routes/patterns.py` + `swing/web/routes/metrics.py` + `swing/web/routes/dashboard.py` + new VM modules for `§<section>` citations + add each to pre-Codex byte-fidelity scope. **Anchor: T2.SB6a MAJOR #3** — `render_watchlist_thumbnail_svg` docstring cited "Per spec §C.5" + plan §C.5 inventory table is the source-of-truth for renderer content (volume bars required); pre-Codex covered LOCK'd sections (§C.1 + §C.2 + §A.9 + §A.12 + §A.13 + §A.15) but didn't extend to §C.5 inventory. Pre-Codex review MUST do this for T2.SB6b.

### §1.3 Inheritance from T3.SB3 form-driven discipline (BINDING)

10. **Read-path mapping must keep pace with write-path on widened columns** (T3.SB3 R1 M#1) — if T2.SB6b writes any new column on `pattern_exemplars` (via `label_source='closed_loop_review'` or `'organic_trade_history'` row emits), grep ALL `_row_to_pattern_exemplar` mapper functions in `swing/data/repos/pattern_exemplars.py` + extend in SAME task with column-position comments.
11. **"Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES** (T3.SB3 R1 M#2 LOCK; semantic clarification of L10) — `/patterns/{candidate_id}/review` POST handler MUST RECOMPUTE `proposed_pattern_class` from `pattern_evaluations.pattern_class` for the candidate_id at POST time, NOT consume operator-submitted hidden input as authoritative. Discriminating test: submit tampered `proposed_pattern_class="vcp"` for flat_base candidate; assert persisted row has `proposed_pattern_class='flat_base'`.
12. **Audit envelope empty-state representation must be uniform** (T3.SB3 pre-Codex M#1; emit `None` not `"[]"`) — if T2.SB6b introduces any audit envelope on `pattern_exemplars` writes, emit `None` (NOT `"[]"`) on empty.
13. **Hidden anchor 4-tier rejection ladder** (T3.SB1) — if T2.SB6b form has hidden anchors driving POST-time validation, apply 4-tier rejection (malformed JSON / non-dict / dict missing keys / dict with invalid values → 400 + clear anchor on recovery).
14. **Recovery form anchor-clear discipline** (T3.SB1 R3 M#2) — on anchor-rejection 400, recovery form MUST clear bad anchor.
15. **`selected_X_audit_id` is AUDIT TRAIL, not DEDUPE KEY** (T3.SB2 R2 M#3) — if T2.SB6b presents N options (e.g., top-3 template_match_nearest_exemplar_ids), dedupe MUST key off "what was persisted" (envelope's top-level value), not "what operator picked" (selected_*_audit_id).

### §1.4 Inheritance from Theme 1 chart discipline (BINDING)

16. **Matplotlib mathtext LOCK** per CLAUDE.md gotcha + §A.9 + §C.1 LOCK + T2.SB6a operator-witnessed S8 BINDING (deferred from substrate to T2.SB6b) — operator-witnessed browser verification at S8 BINDING; string-equality tests CANNOT catch mathtext rendering. T2.SB6b template + route handlers MUST NOT introduce non-ASCII text into rendered surfaces.
17. **HTMX OOB-swap partials must not lead with `<tr>`** per existing gotcha — chart-rendering responses MUST NOT lead with table-row content.
18. **HTMX 4xx fragments need explicit config override** — preserve `base.html.j2` `htmx.config.responseHandling` if touching base layout.
19. **`base.html.j2` shared-VM-field propagation** — if T2.SB6b extends `BaseLayoutVM` with new fields, propagate to ALL 5 base-layout VMs (DashboardVM + PipelineVM + JournalVM + WatchlistVM + PageErrorVM) with safe default.
20. **OHLCV fetch scope = open-trade tickers ONLY** for position-detail chart — preserve existing discipline.
21. **HTMX 3-surface discipline** for all 4 NEW POST routes (Phase 5 R1 M1+M2 + Phase 6 I3):
    - (a) Embedded forms MUST include `hx-headers='{"HX-Request": "true"}'` under OriginGuard strict-mode
    - (b) Success-path response MUST be `204 + HX-Redirect: <url>` (NOT `303 + swap-target`)
    - (c) HX-Redirect target route MUST be REGISTERED in app's route table

### §1.5 Inheritance from cumulative Phase 13 + cross-arc discipline

22. **Schema-CHECK-vs-semantic-contract paired discipline** (T2.SB6a R1 CRITICAL #1; NEW CLAUDE.md gotcha banked at `040455b`) — applies to ANY new dataclass with `__post_init__` validators on tables touched by T2.SB6b. Surface every semantic invariant from spec/plan + mirror in `__post_init__`.
23. **F6 transient-empty defense at CONSTRUCTION barrier** (T2.SB6a R1 MAJOR #2; NEW CLAUDE.md gotcha banked at `040455b`) — applies to ANY new write-through-cache helper that accepts a dataclass parameter.
24. **`Literal[...]` runtime validation** (T-A.1.5b R3 M#1) — `CriterionRow.status: Literal['pass', 'fail']` + any new VM `Literal[...]` fields need explicit `__post_init__` frozenset validation.
25. **`... or None` SQL nullability** (Phase 6 deviation #3) — for any new nullable CHECK columns introduced by T2.SB6b writes, use `... or None` not `... or ""`.
26. **Session-anchor read/write alignment** (recurring family) — any new session-keyed predicates use same anchor function as writer.
27. **Web server restart required after VM/template-affecting merges** (T3.SB3 S2 stale-server lesson banked) — operator MUST restart `swing web` after T2.SB6b merge so new VM fields + templates load.
28. **NO `Co-Authored-By` footer** — cumulative ~340+ commit streak ZERO trailer drift through T2.SB6a + housekeeping; do NOT regress.
29. **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
30. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun).
31. **Edit tool for per-file edits** when fixing E501 / type / import-order — do NOT bulk-rewrite.
32. **TDD per task** via `superpowers:test-driven-development`.

---

## §2 Per-task acceptance criteria (per plan §G.9 verbatim; 6 deferred tasks)

| Task | Title | Acceptance |
|---|---|---|
| T-A.6.3 | `/patterns/{candidate_id}/review` review form | 10+ tests pass per plan §G.9 step 1 enumeration: 8-item checklist render (proposed pattern class + geometric_score breakdown + top-3 template thumbnails + trend-template badge + RS rank + volume profile + uncertainty reason + outcome distribution) per spec §5.10 lines 766-775 VERBATIM; 6-decision enum (confirm / watch / reject / relabel / pattern_present_outside_window / multiple_overlapping_patterns) per lines 778-783 VERBATIM; confirm + trade-opened → `label_source='organic_trade_history'`; confirm + no-trade → `label_source='closed_loop_review'`; relabel persists `final_pattern_class` (cross-column CHECK invariant #1 enforced); window-shift + multi-exemplar emit; `PatternReviewFormVM` extends `BaseLayoutVM`; banner fields populated. **L9 LOCK**: server-recompute `proposed_pattern_class` at POST per §1.3 #11. **L12 LOCK**: HTMX 3-surface discipline + HX-Redirect target `/patterns/queue` registered. **L11 LOCK**: read-path mapper extended if any new pattern_exemplars column written. |
| T-A.6.4 | `/patterns/queue` active-learning prioritization | 6+ tests pass: `prioritize_candidates(conn, top_k=20)` per spec §5.10 lines 796-801 VERBATIM 4-criterion ranking (borderline geometric \|score-0.5\|<0.1; rule/template disagreement \|geometric-template\|>0.3; underrepresented regimes low historical exemplar count for current weather; failed-rule near-misses geometric in [0.55, 0.70]); `PatternQueueVM` extends `BaseLayoutVM` + banner fields. Pure function in `swing/patterns/active_learning.py`. |
| T-A.6.5 | `/metrics/pattern-outcomes` 9th metric tile | 7+ tests pass: per-pattern-class outcome distribution (X% triggered + Y% reached 1R + Z% hit stop); Wilson-CI badge at n≥5 per Phase 10 honesty; suppressed at n<5; composes with Phase 10 cohort architecture (`swing/metrics/cohort.py` + `honesty.py` reuse); `PatternOutcomesVM` extends `BaseLayoutVM` + banner fields. **L10 LOCK**: Phase 10 §A.18 discrepancies helper reused; new tile is ADDITIVE on top of shipped 8 Phase 10 tiles + 1 umbrella navigator; NOT a replacement. |
| T-A.6.6 | Theme 1 chart surface integration + dashboard market weather | 8+ tests pass (HTMX trinity explicit): DashboardVM populates `dashboard_weather_chart_svg_bytes`; watchlist row VM inline thumbnail SVG bytes; hyp-rec detail VM 800×500 SVG; position detail VM 800×500 SVG with fill markers; `POST /dashboard/weather-chart/refresh` invalidates cache + regenerates; `hx-headers='{"HX-Request": "true"}'` propagation; `204 + HX-Redirect: /dashboard` (NOT 303); HX-Redirect target `/dashboard` registered in app routes. **L13 LOCK**: dashboard weather TOP per §C.3. **L14 LOCK**: BaseLayoutVM extension propagated to ALL 5 base-layout VMs. Consumes T2.SB6a substrate (`get_cached_chart_svg` reads + `refresh_chart_render` writes) verbatim. |
| T-A.6.6b | `/patterns/exemplars` enhanced rendering (Deficiency 1 fold-in) | 8+ tests pass (Deficiency 1 fold-in from T-A.1.6): chart per exemplar (REUSES `render_theme2_annotated_svg` from T-A.6.1 — NO new renderer code); per-criterion PASS/FAIL table from `labeler_evidence_json.rule_criteria`; narrative text from `labeler_evidence_json.narrative`; cache-hit path consumes `chart_renders`; cache-miss path invokes renderer once; graceful at missing chart_renders + malformed labeler_evidence_json. **L15 LOCK**: `CriterionRow.status: Literal['pass', 'fail']` has `__post_init__` frozenset validation. **L16 LOCK**: ASCII-only on narrative text; NO `→` / `§` / em-dash via Jinja literals. **L17 LOCK**: reuse `render_theme2_annotated_svg` from T2.SB6a substrate — do NOT duplicate matplotlib code. |
| T-A.6.7 | T2.SB6b closer — integration E2E + ruff sweep + cross-bundle pin row 11 un-skip | Fast E2E PASS: seeds full happy path (pipeline run → pattern_evaluations rows → chart_renders cache → /patterns/queue lists → /patterns/{id}/review renders + POST persists → /metrics/pattern-outcomes renders cohort outcomes → /patterns/exemplars renders chart + criteria + narrative). Cross-bundle pin un-skip: `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 (un-skips at T2.SB6 + T4.SB closer when used). Verify pin status via `git grep "@pytest.mark.skip"` at Step 1; un-skip OR plant + un-skip per plan precedent. |

**Recommended ordering**: T-A.6.3 (review form — largest task; consumes T2.SB6a annotated chart renderer for top-3 thumbnails) → T-A.6.4 (queue — pure function + VM; small) → T-A.6.5 (metric tile — Phase 10 composition pattern; small-mid) → T-A.6.6 (chart-surface integration — 4 surfaces × VM extension; mid) → T-A.6.6b (exemplars enhancement — REUSES T2.SB6a + T-A.6.6 wiring; small-mid) → T-A.6.7 (closer + cross-bundle pin row 11).

---

## §3 Files in scope

**Create** (4 VM modules + 4 Jinja templates + 1 module + 4 test files):
- `swing/patterns/active_learning.py` — `prioritize_candidates(conn, top_k=20) -> list[CandidatePriority]` pure function per spec §5.10 4-criterion ranking. `CandidatePriority` frozen dataclass.
- `swing/web/view_models/patterns/review_form.py` — `PatternReviewFormVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/queue.py` — `PatternQueueVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/outcomes_card.py` — `PatternOutcomesVM` extending `BaseLayoutVM`.
- `swing/web/view_models/patterns/annotated_chart.py` — shared annotated chart VM shape.
- `swing/web/templates/patterns/review.html.j2`
- `swing/web/templates/patterns/queue.html.j2`
- `swing/web/templates/patterns/outcomes.html.j2`
- `swing/web/templates/patterns/annotated_chart_partial.html.j2`
- `tests/web/test_routes/test_patterns_review.py` — 10+ route tests (T-A.6.3)
- `tests/web/test_routes/test_patterns_queue.py` — 6+ tests (T-A.6.4)
- `tests/web/test_routes/test_metrics_pattern_outcomes.py` — 7+ tests (T-A.6.5)
- `tests/integration/test_phase13_t2_sb6b_closed_loop_e2e.py` — 1 fast E2E (T-A.6.7)

**Modify**:
- `swing/web/routes/patterns.py` — add `/patterns/{candidate_id}/review` GET + POST; `/patterns/queue` GET; extend `/patterns/exemplars` for T-A.6.6b Deficiency 1 fold-in.
- `swing/web/routes/metrics.py` — add `/metrics/pattern-outcomes` 9th tile.
- `swing/web/routes/dashboard.py` — extend DashboardVM with market weather chart field; add `POST /dashboard/weather-chart/refresh`.
- `swing/pipeline/runner.py:_step_charts` — write `chart_renders` cache rows for 5 surfaces (consumes T2.SB6a `refresh_chart_render` verbatim).
- `swing/web/view_models/dashboard.py` — `DashboardVM.dashboard_weather_chart_svg_bytes: bytes | None = None`.
- `swing/web/view_models/watchlist.py` — per-row inline thumbnail SVG bytes.
- `swing/web/view_models/recommendations.py` — hyp-rec detail chart SVG bytes.
- `swing/web/view_models/patterns/exemplars.py` (existing from T-A.1.6) — extend with `chart_svg_bytes` + `criterion_rows` + `narrative_text`.
- `swing/web/templates/dashboard.html.j2` — render market weather at TOP per §C.3.
- `swing/web/templates/patterns/exemplars.html.j2` — render chart `<img>` + criteria `<table>` + narrative `<p>` per exemplar.
- `tests/web/test_routes/test_patterns_exemplars.py` (existing from T-A.1.6) — extend with 8 new tests for T-A.6.6b.
- `tests/pipeline/test_step_charts.py` (likely existing) — extend with chart_renders cache write-through tests.

**Substrate (FROZEN; do NOT modify)**:
- `swing/web/charts.py` (T2.SB6a substrate; 5 renderer functions)
- `swing/data/repos/chart_renders.py` (T2.SB6a substrate; cache helpers)
- `swing/data/models.py:ChartRender.__post_init__` (T2.SB6a Codex R1 fixes)

**Verify at T-A.6.7 cross-bundle pin status**:
- `tests/<somewhere>/test_repo_caller_tx_contract_invariant` per plan §H.3 row 11

**NOT in scope (V2 / T4.SB / future)**:
- T4.SB Q4 close-tracking flag (separate sub-bundle; PAUSE-FOR-LIST-ADDITIONS first)
- Interactive client-side JS chart library (V2)
- Per-row sparklines / multi-timeframe toggle / annotation editor (V2)
- Schema changes (v20 LOCKED)
- ZERO new Schwab API calls
- Phase 13.5 drift surfaces (separate dispatch; ≥1 month feature_distribution_log_json accumulation)

---

## §4 Watch items

### §4.1 T2.SB6b-specific watch items

1. **Spec §5.10 + §4.6 + §C.3 LOCK fidelity**: 8-item checklist order + 6-decision enum + 4-criterion ranking + dashboard weather TOP placement byte-fidelity. Implementer grep spec; do NOT paraphrase.
2. **`label_source` semantic split per Codex R4 M#1 LOCK**: `closed_loop_review` if NO trade opened; `organic_trade_history` if confirm + trade opened (resolved via `trades.candidate_id` backlink).
3. **§5.10 4-criterion active-learning ranking LOCK** per lines 796-801 verbatim.
4. **9th metric tile COMPOSES with Phase 10** (NOT replacement); reuse `swing/metrics/cohort.py` + `honesty.py` + Phase 10 §A.18 discrepancies helper.
5. **Dashboard market weather TOP placement** per §C.3 LOCK.

### §4.2 Substrate-consumer watch items

6. **Substrate API FROZEN**: 5 renderer functions + 2 cache helpers signatures verbatim from T2.SB6a. NO modifications.
7. **ChartRender semantic contract** per T2.SB6a R1 CRITICAL #1 fix: cache row construction MUST satisfy §C.2 cache key shape invariants (run-bound surfaces non-NULL `pipeline_run_id`; `position_detail` NULL; `theme2_annotated` both + `pattern_class`).
8. **`refresh_chart_render` at construction barrier** per T2.SB6a R1 MAJOR #2 fix: caller MUST NOT pass empty SVG bytes (rejected at `ChartRender.__post_init__`).

### §4.3 Form-driven discipline watch items (T-A.6.3 + T-A.6.6)

9. **Server-recompute `proposed_pattern_class` at POST** per T3.SB3 R1 M#2 LOCK + §1.3 #11 above. Discriminating test required.
10. **HTMX 3-surface discipline** per Phase 5 R1 M1+M2 + Phase 6 I3 for all 4 NEW POST routes.
11. **Hidden anchor 4-tier rejection** per T3.SB1 — if any form introduces hidden audit anchors driving POST validation.
12. **`base.html.j2` shared-VM-field propagation** — if DashboardVM gains `dashboard_weather_chart_svg_bytes`, propagate to all 5 base-layout VMs.
13. **Read-path mapper extension** per T3.SB3 R1 M#1 — if `pattern_exemplars` new column written, grep `_row_to_pattern_exemplar` mappers + extend in SAME task.

### §4.4 T-A.6.6b Deficiency 1 fold-in watch items

14. **Reuse `render_theme2_annotated_svg` from T2.SB6a substrate** — do NOT duplicate matplotlib code.
15. **Reuse `get_cached_chart_svg` from T2.SB6a substrate** — cache-hit path; cache-miss invokes renderer once.
16. **`CriterionRow.status: Literal['pass', 'fail']` runtime validation** per `Literal[...]` gotcha.
17. **ASCII-only on narrative text** — Jinja literals MUST NOT introduce `→` / `§` / em-dash.
18. **Graceful at missing chart_renders + malformed labeler_evidence_json** — page renders placeholder, NOT 500.

### §4.5 Cross-bundle pin + cumulative process discipline (T-A.6.7 + brief-wide)

19. **Cross-bundle pin un-skip at T-A.6.7 closer**: `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11.
20. **Pre-Codex orchestrator-side review (24th cumulative C.C lesson #6 BINDING with BOTH ORIGINAL EXPANSIONS + 3 NEW PROPOSALS BINDING)** — see §1.2 #5-#9 above. 23rd validation surfaced 3 gap classes; T2.SB6b is the first dispatch to apply all 5 expansions explicitly. **Pre-Codex review MUST explicitly cover each expansion + cite the verdict per expansion in return report §10.**
21. **NO `Co-Authored-By` footer** — cumulative ~340+ commit streak ZERO trailer drift.
22. **`python -m swing.cli` from worktree cwd**, NOT bare `swing`.
23. **ASCII-only on runtime CLI paths**.
24. **Edit tool for per-file edits**.
25. **Cite the discipline in commit messages** (matches all prior precedent).
26. **TDD per task**.

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 6 T-A.6.X tasks committed per plan §G.9 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5490 + ~80-130 new fast tests = ~5570-5620 total + 1 un-skip from T-A.6.7 closer = ~5571-5621; 0 failures; ≤1 skipped (T-A.6.7 un-skip brings 2 → 1).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20.
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (24th cumulative C.C lesson #6 validation with **5 SCOPE EXPANSIONS** applied: original #1 hardcoded-duplicate + #2 spec source-of-truth + NEW #3 schema-CHECK-vs-semantic-contract + NEW #4 specific-scenario gotcha trace + NEW #5 cross-section spec inventory grep). **Verdict per expansion captured in return report §10.**
- [ ] All commits on branch `phase13-t2-sb6b-closed-loop-routes` have empty `Co-Authored-By` trailer.
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-4 rounds — pre-Codex with 5 expansions BINDING should catch what would have been Codex findings).

### §5.2 S2-S8 (operator-paired post-merge per plan §G.9 lines 2294-2304)

- **S2 (browser)**: `/dashboard` → confirm market weather chart at TOP per §C.3
- **S3 (browser)**: `/patterns/queue` → confirm active-learning prioritization
- **S4 (browser)**: `/patterns/{id}/review` for a real candidate → 8-item checklist + decision form
- **S4b (browser)**: `/patterns/exemplars` → confirm chart + per-criterion table + narrative
- **S5 (browser)**: `/metrics/pattern-outcomes` → per-pattern-class outcome distributions
- **S6 (browser)**: hyp-rec detail page → annotated chart with pattern boundaries
- **S7 (browser)**: position detail page → fill markers + current stop line + MFE/MAE shading
- **S8 (visual)**: operator browser-DevTools verification of SVG renderability — NO mathtext mishaps per §A.9 LOCK

**Important operational reminder**: operator MUST restart `swing web` after T2.SB6b merge so the new VMs + templates are loaded into the running Python process (stale-server-vs-current-code drift invisible to fast E2E per T3.SB3 S2 lesson).

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.10 + §4.6 + §C.3 BINDING text verbatim.
- **L2**: ZERO new Schwab API calls.
- **L3**: ZERO schema changes (v20 LOCKED; all columns landed at T-A.1.1).
- **L4**: Cross-bundle pin row 11 un-skip at T-A.6.7 closer per plan §H.3.
- **L5**: Branch base = main HEAD `040455b` at dispatch time.
- **L6**: Frozen dataclasses (`CandidatePriority` + `CriterionRow` + new VM types) carry `__post_init__` runtime validation.
- **L7**: T2.SB6a substrate API surface FROZEN — `swing/web/charts.py` + `swing/data/repos/chart_renders.py` + `swing/data/models.py:ChartRender` UNMODIFIED.
- **L8**: `_CHART_SURFACE_VALUES` imported from `swing/data/models.py` (canonical site).
- **L9**: `/patterns/{candidate_id}/review` POST SERVER-RECOMPUTES `proposed_pattern_class` (NOT operator-submitted hidden) per T3.SB3 R1 M#2.
- **L10**: 9th metric tile COMPOSES with Phase 10 (ADDITIVE).
- **L11**: All 4 NEW VMs extend `BaseLayoutVM` + populate banner fields.
- **L12**: HTMX 3-surface discipline.
- **L13**: Dashboard market weather chart at TOP per §C.3.
- **L14**: `base.html.j2` shared-VM-field propagation (5 base-layout VMs).
- **L15**: `CriterionRow.status: Literal['pass', 'fail']` `__post_init__` frozenset validation.
- **L16**: ASCII-only narrative text.
- **L17**: T-A.6.6b reuses `render_theme2_annotated_svg` from T2.SB6a substrate.
- **L18**: `chart_renders` cache invalidation: DELETE-then-INSERT atomic per §A.15 + `BEGIN IMMEDIATE` / `COMMIT` per §A.12 (handled by T2.SB6a `refresh_chart_render` substrate; T2.SB6b callers consume verbatim).
- **L19**: Pre-Codex review applies ALL 5 SCOPE EXPANSIONS per §1.2 #5-#9 + §4.5 #20. Verdict captured per expansion in return report §10.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.9 lines 2164-2305 (6 deferred tasks; T-A.6.3 onwards) + §H.3 row 11 cross-bundle pin schedule.
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §5.10 Closed-loop surface (lines 760-801; 8-item checklist + 6-decision + label_source split + 4-criterion ranking)
  - §4.6 Theme 2 annotated chart deliverable
  - §4.5 Market weather mini-chart placement (TOP per §C.3)
  - §A.9 + §A.10 Matplotlib mathtext LOCK
- **T2.SB6a substrate brief + return report**: `docs/phase13-t2-sb6a-substrate-codex-completion-dispatch-brief.md` + `docs/phase13-t2-sb6a-return-report.md` — substrate API surface + 3 NEW scope expansion proposals + 2 NEW gotchas + 1 V2 brief-drafting candidate.
- **Original T2.SB6 brief**: `docs/phase13-t2-sb6-closed-loop-surface-dispatch-brief.md` (316 lines on main HEAD `f562100`) — full 8-task scope; 6 tasks here are §2 rows 3-8.
- **T2.SB6 partial-completion return report**: `docs/phase13-t2-sb6-return-report.md` — §3 deferred task handoff documentation.
- **T3.SB3 return report**: `docs/phase13-t3-sb3-return-report.md` §6 — 4 forward-binding lessons inherited.
- **CLAUDE.md gotchas relevant to T2.SB6b**:
  - Matplotlib mathtext LOCK (BINDING per L19 → S8 operator-visual gate)
  - HTMX OOB-swap partials, HTMX HX-Request + HX-Redirect, base.html.j2 shared
  - `Literal[...]` not runtime-enforced
  - Session-anchor read/write mismatch family
  - Schema-CHECK widening MUST audit ALL Python-side surface guards (T3.SB2 hotfix)
  - Read-path mapping must keep pace with write-path on widened columns (T3.SB3 R1 M#1)
  - "Server-stamped" hidden inputs STILL tampering surfaces unless POST RECOMPUTES (T3.SB3 R1 M#2)
  - **NEW** Schema-CHECK + Python-constant + dataclass-validator EXTENDS to semantic contracts (T2.SB6a R1 CRITICAL #1)
  - **NEW** F6 transient-empty at construction barrier (T2.SB6a R1 MAJOR #2)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB6b merge ships:

1. **CLAUDE.md line 3 refresh** — T2.SB6a → T2.SB6b SHIPPED; 24th cumulative C.C lesson #6 validation result (CLEAN or BROKEN — track if the 5-expansion discipline is load-bearing).
2. **phase3e-todo.md** — new top entry for T2.SB6b SHIPPED.
3. **orchestrator-context.md** — refresh current state; Prior demote (T2.SB6a → Prior #1); archive-split per size-check trigger.
4. **orchestrator-context-archive.md** — new appendix.
5. **Streaks update** — bank 24th cumulative C.C lesson #6 validation (CLEAN or NOTABLE); bank ~360+ cumulative ZERO Co-Authored-By streak.
6. **PHASE 13 DISPATCH SEQUENCE — SURFACE THE PAUSE-FOR-LIST-ADDITIONS** per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory. Orchestrator action: AFTER T2.SB6b housekeeping commit, surface the pause in operator update + DO NOT commission T4.SB dispatch brief without operator's added items.

---

## §9 Forward-binding to T4.SB closer

T4.SB = Usability triage + Q4 close-tracking flag + metrics-dashboard hooked-up audit (8 tasks + operator-added items per plan §G.10). **PAUSE-FOR-LIST-ADDITIONS BINDING** between T2.SB6b SHIPPED + housekeeping and T4.SB dispatch brief commissioning per `project_phase13_t4_sb_pause_for_list_additions` memory.

**Forward-binding lessons expected from T2.SB6b to T4.SB**:
- 5-scope-expansion pre-Codex discipline (24th cumulative validation result informs T4.SB; if any of the 3 NEW expansions caught findings at T2.SB6b, they're load-bearing for T4.SB)
- HTMX 3-surface discipline (T4.SB Q4 `POST /watchlist/{ticker}/flag` + `POST /watchlist/{ticker}/unflag` routes inherit)
- BaseLayoutVM banner field propagation (T4.SB VMs)
- Server-recompute at POST (any T4.SB operator-toggleable form)
- Web server restart discipline (T4.SB inherits)
- ~360+ cumulative ZERO Co-Authored-By streak

---

*End of dispatch brief. Phase 13 T2.SB6b (6 deferred tasks; +80-130 fast tests + 1 fast E2E + 1 cross-bundle pin row 11 un-skip projected; v20 schema UNCHANGED; ZERO Schwab API calls) — closed-loop routes + Theme 1 chart integration + Deficiency 1 fold-in consuming T2.SB6a FROZEN substrate API surface. Inherits T2.SB6a forward-binding lessons (3 NEW scope expansion proposals #3 + #4 + #5; 2 NEW gotchas just banked at `040455b`) + T3.SB3 forward-binding (read-path mapper + server-recompute at POST + audit envelope empty-state) + cumulative Phase 13 disciplines. 2-4 Codex rounds expected (pre-Codex with 5 expansions BINDING should catch findings before Codex). **24th cumulative C.C lesson #6 validation expected with ALL 5 SCOPE EXPANSIONS BINDING** — verdict per expansion required in return report §10. **PAUSE-FOR-LIST-ADDITIONS BINDING at T2.SB6b SHIPPED + housekeeping boundary BEFORE T4.SB dispatch.** ZERO Co-Authored-By footer drift streak (~340+ commits at handoff) preserved.*
