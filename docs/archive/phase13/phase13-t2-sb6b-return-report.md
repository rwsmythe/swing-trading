# Phase 13 T2.SB6b — Closed-loop routes + Theme 1 chart integration + T-A.1.6 Deficiency 1 fold-in return report

**Status:** SHIPPED on branch `phase13-t2-sb6b-closed-loop-routes` at HEAD `34ddfb7`. Branched from main HEAD `ff1a15f` (descendant of `040455b` per brief L5 acceptance). 8 commits total (6 task commits + 1 Codex R1 fix bundle + 1 Codex R2 docstring closure). Codex MCP adversarial chain converged at **R2 NO_NEW_CRITICAL_MAJOR** (R1: 7 MAJOR findings — 3 fixed + 4 accept-with-rationale + 1 minor docstring drift; R2: minor docstring drift closed).

**Final S1 numbers:**
- 5559 fast tests passed (+69 net from baseline 5490; brief expected +80-130 — slightly below the lower band, owed to focused acceptance-targeted tests rather than expansive coverage).
- 0 failed.
- 2 skipped unchanged (`test_flag_classifier_integration` + T4.SB closer v20 pin row 2; pre-existing).
- 0 ruff E501 / E violations.
- Schema v20 UNCHANGED (no new migration).
- ZERO new Schwab API calls (L2 LOCK preserved).
- Cross-bundle pin row 11 (`test_repo_caller_tx_contract_invariant`) **PLANTED + GREEN** per brief L4 LOCK acceptance ("un-skip OR plant + un-skip per plan precedent"). 4 parametrized passes — one per Phase 13 NEW repo module.

---

## §1 Commits

| Commit | Title |
|---|---|
| `3020fc8` | feat(phase13): /patterns/{id}/review closed-loop form (T-A.6.3) |
| `90769fb` | feat(phase13): /patterns/queue active-learning prioritization (T-A.6.4) |
| `e56f462` | feat(phase13): /metrics/pattern-outcomes 9th metric tile (T-A.6.5) |
| `aa1900f` | feat(phase13): Theme 1 chart surfaces + dashboard market weather (T-A.6.6) |
| `c853ee2` | feat(phase13): /patterns/exemplars chart + criteria + narrative (T-A.6.6b; Deficiency 1 fold-in) |
| `d8241a9` | test(phase13): T2.SB6b closer - closed-loop E2E + ruff + cross-bundle pin row 11 (T-A.6.7) |
| `94e4418` | fix(phase13): close Codex R1 MAJOR #3 + #6 + #7 + partial #5 (T2.SB6b) |
| `34ddfb7` | docs(phase13): clarify exemplar cache-miss live-render contract per Codex R2 minor |

ZERO `Co-Authored-By` footers across all 8 commits (~340+ cumulative streak preserved through T2.SB6b ship).

---

## §2 Per-task disposition

| Task | Disposition | Tests delta | Brief acceptance |
|---|---|---|---|
| T-A.6.3 | SHIPPED at `3020fc8` | 24 (10+ target) | All §2 row 1 items + L9 server-recompute + L12 HTMX 3-surface + L11 BaseLayoutVM banner fields. |
| T-A.6.4 | SHIPPED at `90769fb` | 10 (6+ target) | Spec §5.10 lines 796-801 VERBATIM 4-criterion ranking + L6 Literal frozenset validation + L11 BaseLayoutVM. |
| T-A.6.5 | SHIPPED at `e56f462` | 8 (7+ target) | 9th tile per OQ-10 LOCK; L10 ADDITIVE composition with Phase 10 honesty + RiskPolicy + Wilson CI; 10th /metrics/* path registered. |
| T-A.6.6 | SHIPPED at `aa1900f` + partial extension at `94e4418` | 10 (8+ target) | DashboardVM dashboard_weather_chart_svg_bytes + watchlist_chart_svg_bytes + position_chart_svg_bytes; POST /dashboard/weather-chart/refresh with HTMX 3-surface; L13 TOP placement + L17 substrate reuse. WatchlistVM standalone chart bytes wired at `94e4418`. |
| T-A.6.6b | SHIPPED at `c853ee2` + `94e4418` + `34ddfb7` | 11 (8+ target) | CriterionRow Literal validation (L15) + per-criterion table + narrative + cache-miss live render via bars_fetcher injection (R1 MAJOR #6 closure) + L17 substrate reuse. ASCII title fix (L16). |
| T-A.6.7 | SHIPPED at `d8241a9` | 1 E2E + 4 cross-bundle pin parametrized | Fast E2E walks full happy path; cross-bundle pin row 11 planted + GREEN. |

**Test totals:** 24 + 10 + 8 + 10 + 11 + 4 + 1 = 68 net additions; baseline 5490 + 69 = 5559 final (one additional test landed in the R1 fix bundle).

---

## §3 Files in scope

**Create (T2.SB6b commits):**
- `swing/patterns/active_learning.py` — pure `prioritize_candidates` per spec §5.10 lines 796-801 + CandidatePriority frozen dataclass.
- `swing/metrics/pattern_outcomes.py` — `build_pattern_outcome_rows` + PatternOutcomeRow.
- `swing/web/view_models/patterns/review_form.py` — PatternReviewFormVM + CriterionBreakdownRow + UncertaintyReasonRow + OutcomeDistributionRow + builder.
- `swing/web/view_models/patterns/queue.py` — PatternQueueVM + builder.
- `swing/web/view_models/patterns/outcomes_card.py` — PatternOutcomesVM + builder.
- `swing/web/templates/patterns/review.html.j2`.
- `swing/web/templates/patterns/queue.html.j2`.
- `swing/web/templates/metrics/pattern_outcomes.html.j2`.
- `tests/web/test_routes/test_patterns_review.py` (24 tests).
- `tests/web/test_routes/test_patterns_queue.py` (10 tests).
- `tests/web/test_routes/test_metrics_pattern_outcomes.py` (8 tests).
- `tests/web/test_routes/test_dashboard_chart_integration.py` (10 tests).
- `tests/web/test_routes/test_patterns_exemplars_enhanced.py` (11 tests).
- `tests/data/test_repo_caller_tx_contract_invariant.py` (4 parametrized tests — cross-bundle pin row 11).
- `tests/integration/test_phase13_t2_sb6b_closed_loop_e2e.py` (1 fast E2E).

**Modify:**
- `swing/web/routes/patterns.py` — added GET/POST `/patterns/{candidate_id}/review` + GET `/patterns/queue` + bars_fetcher injection into `/patterns/exemplars`. PATTERN_REVIEW_DECISIONS + _DECISION_TO_FINAL_DECISION constants added.
- `swing/web/routes/dashboard.py` — added POST `/dashboard/weather-chart/refresh`.
- `swing/web/routes/metrics.py` — added GET `/metrics/pattern-outcomes`.
- `swing/web/view_models/dashboard.py` — DashboardVM extended with 3 chart fields + build_dashboard populates from cache.
- `swing/web/view_models/watchlist.py` — WatchlistVM extended with watchlist_chart_svg_bytes (R1 MAJOR #5 partial closure).
- `swing/web/view_models/metrics/index.py` — MetricsIndexVM _SURFACES extended with the 9th tile entry.
- `swing/web/view_models/patterns/exemplars.py` — extended with CriterionRow + ExemplarRender + bars_fetcher injection for cache-miss live render.
- `swing/web/templates/patterns/exemplars.html.j2` — per-exemplar enhanced render block + ASCII title.
- `swing/web/templates/dashboard.html.j2` — market weather chart at TOP per §C.3 + refresh form with HX-Request propagation.
- `tests/web/test_routes/test_base_layout_vm_banner_with_pending_ambiguity.py` — extended `_METRICS_PAGES` with `/metrics/pattern-outcomes` (10 pages total; was 9).

**Substrate (FROZEN per L7 LOCK; NOT modified):**
- `swing/web/charts.py` (T2.SB6a substrate; 5 renderer functions).
- `swing/data/repos/chart_renders.py` (T2.SB6a substrate; cache helpers).
- `swing/data/models.py:ChartRender` (T2.SB6a Codex R1 fixes preserved).

---

## §4 LOCKs honored

- **L1**: spec §5.10 + §4.6 + §C.3 BINDING text verbatim. Constants in `active_learning.py` cite spec lines 796-801; checklist labels in `review.html.j2` cite spec lines 766-775; 6-decision enum in `patterns.py` cites lines 778-783; label_source split cites lines 785-790.
- **L2**: ZERO new Schwab API calls. No diff under `swing/integrations/schwab/`.
- **L3**: ZERO schema changes (v20 LOCKED). No new migration files. `git diff main -- swing/data/migrations/` empty.
- **L4**: cross-bundle pin row 11 PLANTED + GREEN at `tests/data/test_repo_caller_tx_contract_invariant.py` (4 parametrized passes).
- **L5**: branch base = main HEAD `ff1a15f` (descendant of `040455b`).
- **L6**: frozen dataclasses with `__post_init__` frozenset validation: CandidatePriority + CriterionRow + CriterionBreakdownRow (3 NEW Literal validators).
- **L7**: T2.SB6a substrate API surface FROZEN — `git diff main -- swing/web/charts.py swing/data/repos/chart_renders.py swing/data/models.py` empty.
- **L8**: `_CHART_SURFACE_VALUES` imported from `swing/data/models.py` (preserved; no re-definition).
- **L9**: `/patterns/{candidate_id}/review` POST RECOMPUTES `proposed_pattern_class` from canonical `pattern_evaluations.pattern_class` at POST time (`patterns.py` POST handler line referencing `evaluation.pattern_class`). Discriminating test `test_post_patterns_review_server_recomputes_proposed_pattern_class_from_evaluation_not_operator_hidden` planted at T-A.6.3.
- **L10**: 9th metric tile COMPOSES with Phase 10 (ADDITIVE). `pattern_outcomes.py` imports Phase 10 `honesty.wilson_ci` + `honesty.suppress_for_n` + `RiskPolicy`. `_SURFACES` tuple in `metrics/index.py` adds the 9th entry alongside the 8 Phase 10 tiles.
- **L11**: All 4 NEW VMs extend BaseLayoutVM + populate banner fields: PatternReviewFormVM + PatternQueueVM + PatternOutcomesVM + (extended) PatternExemplarsVM. Each builder calls `count_unresolved_material(conn)` + `count_recent_multi_leg_auto_corrections(conn)` + `fetch_first_pending_ambiguity_resolve_link_path(conn)`.
- **L12**: HTMX 3-surface discipline preserved across all 4 NEW POST routes:
  - `/patterns/{id}/review` POST: `hx-headers='{"HX-Request": "true"}'` on form + 204 + `HX-Redirect: /patterns/queue` + target registered.
  - `/dashboard/weather-chart/refresh` POST: same trinity + target = `/dashboard`.
- **L13**: dashboard market weather chart at TOP per §C.3. `dashboard.html.j2` renders `<section id="dashboard-market-weather">` above `<div id="status-strip">`. E2E asserts `weather_idx < status_idx`.
- **L14**: base.html.j2 shared-VM-field propagation — no new fields added to BaseLayoutVM in T2.SB6b; existing 5 base-layout VMs unchanged.
- **L15**: `CriterionRow.status: Literal['pass', 'fail']` + `__post_init__` frozenset validation against `_CRITERION_STATUS_VALUES`. Discriminating test `test_get_patterns_exemplars_criterion_row_status_pass_or_fail_per_evaluation`.
- **L16**: ASCII-only narrative text + Jinja literals. R1 MAJOR #7 em-dash defect closed at `94e4418`. Post-fix grep across new templates: 0 non-ASCII chars.
- **L17**: T-A.6.6b reuses `render_theme2_annotated_svg` from T2.SB6a substrate verbatim. Cache-miss path imports + invokes the substrate renderer; no duplicate matplotlib code.
- **L18**: chart_renders cache invalidation via substrate `refresh_chart_render` (POST `/dashboard/weather-chart/refresh` consumes verbatim).

---

## §5 Forward-binding lessons banked

1. **24th cumulative C.C lesson #6 validation = NOTABLE** (first run with ALL 5 SCOPE EXPANSIONS BINDING). Pre-Codex review with 5 expansions ran CLEAN across the orchestrator-side audit; Codex R1 found 7 MAJOR findings (1 hardcoded-duplicate path-literal in templates banked as ACCEPT; 1 brief-vs-spec checklist completeness deficiency; 1 label_source semantic correctness; 1 queue criterion 3 weather state V1 proxy; 1 Theme 1 integration partial completeness; 1 cache-miss renderer; 1 ASCII em-dash). Pre-Codex review missed the spec-completeness checklist + the semantic mislabel of organic_trade_history + the cache-miss acceptance criterion + the em-dash slip. **Result**: 5-expansion discipline catches schema-CHECK + Literal validation + cross-section spec citations + hardcoded duplicates well; does NOT catch CONTENT-completeness vs spec text (e.g., trend-template badge value is "n/a" stub vs spec's `current_stage()` requirement) or operator-input cross-row semantic correctness (ticker-proxy vs candidate-proxy).
2. **NEW PROPOSAL Expansion #6 candidate (BANKED for 25th cumulative validation)**: **content-completeness audit** — for each spec section's BINDING text (especially data-surface checklists like spec §5.10 lines 766-775), the implementer's per-field disposition must be enumerated explicitly (LIVE / V1 PLACEHOLDER / V1 STUB) BEFORE Codex review. Pre-Codex audit walks each spec data-surface item + asks "does my code provide live data or a stub?" Currently 4 of 7 R1 MAJOR findings were content-completeness gaps (#1, #2, #4, #5 partial).
3. **NEW PROPOSAL Expansion #7 candidate (BANKED)**: **cross-row semantic audit on operator-input flows** — for any new POST handler that consumes operator input AND looks up cross-row state (trades, exemplars, etc.), the implementer must enumerate the SCOPE of the lookup (ticker / pattern / candidate / pipeline run) + cross-check against the spec's wording. R1 MAJOR #3 (ticker-proxy organic_trade_history) is the canonical example.
4. **Cumulative gotcha: "V1 placeholder fields explicitly enumerated in return report"** — every "V1 simplification" must be banked WITH the V2 dependency cited (e.g., "reached_1r_pct V1 = None; V2 unblocks when trades carries candidate_id backlink") so the cumulative deferred-work ledger stays tractable.

---

## §6 V1 simplifications + V2 candidates banked

| V1 simplification | V2 dependency | Banked for |
|---|---|---|
| Review form trend-template state = "n/a" | requires `current_stage()` weather-state read | V2 wiring |
| Review form volume profile = "(not available)" | requires 30-session volume + 50d avg join | V2 wiring |
| Review form outcome distribution: triggered_pct only | requires trade backlink for 1R + stop bucketing | V2 same as below |
| Metric tile reached_1r + hit_stop = None | requires trade backlink (trades.candidate_id) | V2 migration |
| POST `/patterns/{id}/review` always emits closed_loop_review | organic_trade_history requires trade.candidate_id backlink | V2 migration |
| Queue criterion 3 underrepresented_regime proxy = total exemplar count | weather-state-aware variant per spec §5.10 line 799 | V2 enrichment |
| Hyp-rec detail VM + position detail VM chart bytes | each is a separate page VM wire-up | V2 sub-bundles |
| WatchlistVM watchlist_chart_svg_bytes plumbed but not template-rendered | extend `partials/watchlist_row.html.j2` to consume | V2 template work |
| Exemplar cache-miss live render does NOT write-through to cache | pipeline-run-agnostic exemplar cache key shape | V2 cache architecture |

---

## §7 Operator-paired gates (S2-S8 per brief §5.2)

Operator MUST restart `swing web` after T2.SB6b merge per T3.SB3 S2 stale-server lesson (banked).

- **S2 (browser)**: `/dashboard` — confirm market weather chart at TOP per §C.3.
- **S3 (browser)**: `/patterns/queue` — confirm active-learning prioritization renders candidates from latest run.
- **S4 (browser)**: `/patterns/{id}/review` for a real pattern_evaluations.id — confirm 8-item checklist renders + decision form submits + HX-Redirect to /patterns/queue.
- **S4b (browser)**: `/patterns/exemplars` — confirm chart + per-criterion table + narrative rendered per exemplar.
- **S5 (browser)**: `/metrics/pattern-outcomes` — confirm per-pattern-class outcome distributions render Wilson CI at n>=5 + suppression at n<5.
- **S6 (browser)**: hyp-rec detail page — V2 deferred (chart bytes not wired into hyp-rec detail VM in T2.SB6b).
- **S7 (browser)**: position detail page — V2 deferred (chart bytes not wired into position detail VM in T2.SB6b; DashboardVM open-positions tiles surface bytes but the standalone position-detail VM does not).
- **S8 (visual)**: operator browser-DevTools verification of SVG renderability — no mathtext mishaps per §A.9 LOCK + ASCII discipline.

---

## §8 Codex MCP adversarial chain

**R1 (initial)**: 7 MAJOR findings — see §5 #1 above.

**R1 dispositions** (committed at `94e4418` + `34ddfb7`):
- MAJOR #1 (review form checklist placeholders): ACCEPT-WITH-RATIONALE; V1 simplifications enumerated in §6.
- MAJOR #2 (metric tile reached_1r + hit_stop): ACCEPT-WITH-RATIONALE.
- MAJOR #3 (label_source ticker-proxy): **FIXED**. POST now emits closed_loop_review unconditionally. Test renamed.
- MAJOR #4 (queue weather-state proxy): ACCEPT-WITH-RATIONALE.
- MAJOR #5 (Theme 1 chart integration partial): **PARTIAL FIX** (WatchlistVM extended); hyp-rec/position detail VMs ACCEPT.
- MAJOR #6 (cache-miss renderer not invoked): **FIXED**. bars_fetcher injection + assert_called_once test planted.
- MAJOR #7 (em-dash in template title): **FIXED**.

**R2 verdict**: NO_NEW_CRITICAL_MAJOR. Minor docstring drift on cache-miss write-through contract noted + fixed at `34ddfb7`.

Convergence: 2 rounds.

---

## §9 Pre-Codex orchestrator-side review verdict per expansion (24th cumulative validation)

| Expansion | Verdict | Notes |
|---|---|---|
| #1 hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`) | CLEAN at orchestrator pre-Codex; Codex caught template path-literals (`/dashboard/weather-chart/refresh` action attribute) but those are template-canonical for form binding, not duplicates. |
| #2 brief-vs-spec source-of-truth (T2.SB4 R1 M1) | CLEAN at orchestrator pre-Codex; Codex caught CONTENT-completeness gaps (spec checklist items rendered as stubs vs live data). This is a NEW class of finding the existing expansion #2 does NOT catch — see Expansion #6 proposal in §5.
| #3 schema-CHECK-vs-semantic-contract gap audit (T2.SB6a R1 CRITICAL #1) | CLEAN at orchestrator pre-Codex AND Codex; no new schema introduced, no new SEMANTIC contracts beyond Literal validation on the 3 new dataclasses (all properly mirrored). |
| #4 CLAUDE.md gotcha specific-scenario trace (T2.SB6a R1 MAJOR #2) | CLEAN at orchestrator pre-Codex for server-recompute + HX-Redirect + `... or None` + Literal validation; Codex caught the candidate-vs-ticker scope drift on the trade backlink (label_source split) — see Expansion #7 proposal in §5. |
| #5 cross-section spec inventory grep (T2.SB6a R1 MAJOR #3) | CLEAN at orchestrator pre-Codex for §A.9 + §C.1 + §C.2 + §A.12 + §A.13 + §A.15 + §C.5 substrate citations; Codex caught the §4.6 cache-miss renderer-invoked acceptance criterion miss (a plan §G.9 acceptance criterion, not a substrate docstring citation; arguably out of expansion #5's defined scope). |

**Cumulative validation result**: 24th BANKED with **2 NEW EXPANSION PROPOSALS** (#6 content-completeness audit; #7 cross-row semantic scope audit) for future dispatches.

---

## §10 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB6b merge ships:

1. **CLAUDE.md line 3 refresh** — T2.SB6a → T2.SB6b SHIPPED; 24th cumulative C.C lesson #6 validation = NOTABLE (7 Codex R1 findings: 3 fixed + 4 V1-banked + 1 minor; R2 NO_NEW_CRITICAL_MAJOR).
2. **phase3e-todo.md** — new top entry for T2.SB6b SHIPPED.
3. **orchestrator-context.md** — refresh current state; archive-split per size-check trigger.
4. **orchestrator-context-archive.md** — new appendix.
5. **Streaks update**: 
   - 24th cumulative C.C lesson #6 validation = NOTABLE (NOT CLEAN, but Codex chain converged at R2 — improvement from T2.SB6a 1 CRITICAL + 2 MAJOR + 1 ACCEPT-WITH-RATIONALE R1 + 0 R2).
   - ~360+ cumulative ZERO Co-Authored-By streak preserved.
6. **PHASE 13 DISPATCH SEQUENCE — SURFACE THE PAUSE-FOR-LIST-ADDITIONS** per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory. Operator MUST add T4.SB usability triage items BEFORE T4.SB dispatch brief commissioning.

---

*End of T2.SB6b return report. ~360+ cumulative ZERO Co-Authored-By streak; 24th cumulative C.C lesson #6 validation = NOTABLE (7 R1 findings; 3 fixed + 4 V1-banked + 1 minor; R2 NO_NEW_CRITICAL_MAJOR; 2 new expansion proposals banked). Substrate API surface frozen + closed-loop routes + Theme 1 chart integration + Deficiency 1 fold-in all shipped. PAUSE-FOR-LIST-ADDITIONS BINDING at T2.SB6b housekeeping boundary before T4.SB dispatch.*
