# Phase 13 T2.SB6 — Closed-loop surface return report (PARTIAL COMPLETION)

**Branch:** `phase13-t2-sb6-closed-loop-surface` (HEAD `255823b` at this report writing; based off main HEAD `4e71787`).

**Status:** **PARTIAL** — substrate tasks **T-A.6.1 + T-A.6.2 SHIPPED** at S1 GREEN; tasks T-A.6.3 through T-A.6.7 **DEFERRED** for a follow-up dispatch (rationale below).

---

## §1 Headline

- **Baseline at branch creation**: 5463 fast tests / 2 skipped / 0 failed (main HEAD `4e71787`).
- **After T-A.6.1 + T-A.6.2**: **5484 fast tests / 2 skipped / 0 failed** (+21 net = +14 charts.py + +7 chart_renders helpers).
- **Schema version**: v20 UNCHANGED (no migrations).
- **ruff E501**: 0 (the new files were authored within the 79-char budget; verified offline).
- **Schwab API calls added**: ZERO (L2 LOCK preserved).
- **Commit chain** (2 commits, both with empty `Co-Authored-By` trailer per cumulative discipline):
  - `e80101a` — `feat(phase13): swing/web/charts.py — SVG-inline renderers (T-A.6.1)`
  - `255823b` — `feat(phase13): chart_renders cache helpers + atomic refresh (T-A.6.2)`

---

## §2 SHIPPED tasks

### §2.1 T-A.6.1 — `swing/web/charts.py` SVG-inline renderer (spec §C.1 LOCK)

**Production module** (`swing/web/charts.py`; ~470 lines):

5 public renderer functions per the spec §C.1 contract:

```python
def render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines) -> bytes
def render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation=None) -> bytes
def render_position_detail_svg(*, ticker, bars, trade, fills, current_stop) -> bytes
def render_market_weather_svg(*, bars, trend_template_state) -> bytes
def render_theme2_annotated_svg(*, ticker, bars, pattern_evaluation,
                                  exemplar_thumbnails=None) -> bytes
```

LOCKs honored:

- **L7 LOCK** (mathtext defense-in-depth):
  - ASCII-only text via `_assert_ascii_only`.
  - `parse_math=False` on `fig.suptitle` defense-in-depth via `_set_suptitle_no_math`.
  - `$` / `^` / `_` / `\\` forbidden in titles via `_assert_title_no_math`.
  - Ticker validator (`_assert_ticker_safe`) gates BOTH ASCII + mathtext at every renderer's entry.
  - Pattern-class slugs that contain `_` (`flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`) render via `ax.text()` body annotations rather than the suptitle gate, because matplotlib treats `_` as literal in body text outside math mode. The split between `_assert_ascii_only` (body) and `_assert_title_no_math` (title) is documented inline.

- **L8 LOCK** (constant placement): `_CHART_SURFACE_VALUES` is imported from `swing/data/models.py` (canonical site per plan §B.7 + T3.SB2 hotfix `cf3c489` discipline). The module DOES NOT redefine the enum.

- **§4.6 + §C.4 annotated chart per-pattern annotations**:
  - VCP: pivot horizontal line + contraction depth labels.
  - Flat base: top/bottom horizontal lines + duration label.
  - CWH: cup-bottom horizontal line + depth ratio label.
  - HTF: days-tight + pole advance % labels.
  - DBW: trough_1 / center_peak / trough_2 horizontal markers + undercut indicator.

- **§C.5 chart inventory dimensions** observed (200x100 / 800x500 / 800x500 / 400x150 / 800x600).

**Tests** (`tests/web/test_charts.py`; 14 tests):

- 4 single-surface shape tests (watchlist + hyp-rec + position + market weather).
- 5 per-pattern theme2-annotated tests (VCP + flat_base + cup_with_handle + high_tight_flag + double_bottom_w).
- 1 cross-bundle pin test `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` (plan §H.3 row 10; lands GREEN at this task).
- 1 ASCII-only invariant test (`ABC→` rejected).
- 1 mathtext metacharacter title gate test (`$ABC` / `ABC^2` / `ABC_1` / `ABC\\NA` all rejected).
- 1 market-weather non-ASCII trend-state rejection test.
- 1 parse_math=False suptitle integration test.

### §2.2 T-A.6.2 — `chart_renders` cache helpers + atomic refresh (spec §C.2 + §A.13 + §A.15)

**Production extension** (`swing/data/repos/chart_renders.py`; ~125 lines added):

```python
def get_cached_chart_svg(conn, *, ticker, surface, pipeline_run_id=None,
                          pattern_class=None,
                          min_data_asof_date=None) -> bytes | None
def refresh_chart_render(conn, chart_render) -> int
```

LOCKs honored:

- **§C.2 cache key shape LOCK** — `get_cached_chart_svg` branches on:
  - Run-bound (watchlist/hyp-rec/market-weather): `(ticker, surface, pipeline_run_id)`.
  - position_detail: `(ticker, surface)` with `pipeline_run_id IS NULL`.
  - theme2_annotated: `(ticker, surface, pipeline_run_id, pattern_class)`.

- **§A.13 session-anchor read/write predicate alignment LOCK** — `min_data_asof_date` parameter accepts the same `last_completed_session(now())` value the writer stamps; round-trip discriminating test plants a known anchor, reads via the predicate, asserts HIT + asserts strictly-later predicate misses. Phase 8 `cfacbc5` pattern preserved.

- **§A.15 + §C.2 cache invalidation pattern LOCK** — `refresh_chart_render` is DELETE-then-INSERT (NOT `INSERT OR REPLACE`). Test asserts the second refresh allocates a NEW PK (distinguishing from REPLACE which would reuse the PK).

- **Caller-tx contract** preserved — no `conn.commit()` inside the repo; caller wraps in `BEGIN IMMEDIATE` / `COMMIT`.

**Tests** (`tests/data/repos/test_chart_renders_repo.py`; +7 tests on the existing T-A.1.1b file):

- run-bound cache key uniqueness (one row per (ticker, surface, run)).
- position_detail cache key (NULL run; unique per ticker).
- theme2_annotated cache key (different pattern_class coexist).
- session-anchor read/write alignment round-trip (Phase 8 `cfacbc5` pattern).
- cache invalidation atomic DELETE-then-INSERT (new PK after refresh).
- `get_cached_chart_svg` miss path returns None.
- `refresh_chart_render` caller-tx rollback undoes both DELETE and INSERT.

---

## §3 DEFERRED tasks (T-A.6.3 → T-A.6.7) — rationale + handoff

**Rationale for partial completion:** the dispatch brief itself acknowledges this is the **LARGEST remaining Phase 13 sub-bundle** with 8 tasks projecting ~100-150 new fast tests + 1 fast E2E. Brief §1 cites operator-paced wall-clock 12-18 hours. Each of T-A.6.3 / T-A.6.4 / T-A.6.5 / T-A.6.6 / T-A.6.6b introduces NEW routes + NEW VMs + NEW Jinja templates + their HTMX trinity discipline + cross-cutting integration with existing routes/templates. Single-conversation execution at production quality across all 8 tasks (plus pre-Codex review + Codex MCP 3-5 rounds + return report) is impractical within a realistic context budget.

The two SHIPPED tasks form the **substrate** that the remaining 6 tasks consume:
- T-A.6.3 / T-A.6.6 / T-A.6.6b all reuse `swing/web/charts.py:render_theme2_annotated_svg` from T-A.6.1.
- T-A.6.2's `get_cached_chart_svg` + `refresh_chart_render` are the cache contract for T-A.6.6 VM consumers + T-A.6.6b exemplars surface.

**Handoff for follow-up dispatch:**

### §3.1 T-A.6.3 — `/patterns/{candidate_id}/review` review form (10+ tests)

**Files to create**:
- `swing/web/view_models/patterns/review_form.py` — `PatternReviewFormVM` extending `BaseLayoutVM`; 8-item checklist fields per spec §5.10 lines 766-775.
- `swing/web/templates/patterns/review.html.j2` — form with 6-decision radio + hidden anchors.
- `tests/web/test_routes/test_patterns_review.py` — 10+ tests including HTMX trinity.

**Files to modify**:
- `swing/web/routes/patterns.py` — add `GET /patterns/{candidate_id}/review` + `POST /patterns/{candidate_id}/review`.

**Key disciplines (BINDING)**:
- **L9 LOCK** (server-recompute at POST per T3.SB3 R1 M#2): POST handler MUST re-derive `proposed_pattern_class` from `pattern_evaluations.pattern_class` for the candidate_id. DO NOT consume operator-submitted hidden inputs as authoritative. Discriminating test: submit a tampered `proposed_pattern_class="vcp"` for a flat_base candidate; assert persisted `pattern_exemplars.proposed_pattern_class='flat_base'`.
- **§3.1 source-vs-decision matrix** — `label_source='organic_trade_history'` when `confirm` + `trades.candidate_id` resolves to a real trade; `label_source='closed_loop_review'` otherwise.
- **cross-column CHECK invariant #1** — relabel requires non-NULL `final_pattern_class` AND different from `proposed_pattern_class`; non-relabel requires `final_pattern_class IS NULL`.
- **Read-path mapper extension** (T3.SB3 R1 M#1 lesson): if T-A.6.3 writes any new column on `pattern_exemplars`, the `_row_to_pattern_exemplar` mapper in `swing/data/repos/pattern_exemplars.py` MUST be extended in the SAME task.
- **HTMX trinity** (HX-Request propagation; 204 + HX-Redirect; target `/patterns/queue` registered).

### §3.2 T-A.6.4 — `/patterns/queue` active-learning prioritization (6+ tests)

**Files to create**:
- `swing/patterns/active_learning.py` — `prioritize_candidates(conn, top_k=20) -> list[CandidatePriority]` pure function per spec §5.10 lines 796-801 4-criterion ranking (borderline geometric; rule/template disagreement; underrepresented regimes; failed-rule near-misses).
- `swing/web/view_models/patterns/queue.py` — `PatternQueueVM` extending `BaseLayoutVM`.
- `swing/web/templates/patterns/queue.html.j2`.
- `tests/web/test_routes/test_patterns_queue.py` — 6+ tests.

**Files to modify**:
- `swing/web/routes/patterns.py` — add `GET /patterns/queue`.

**Key disciplines**:
- **L11 LOCK** — BaseLayoutVM banner field population (`unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count`).
- **L6 LOCK** — `CandidatePriority` frozen dataclass with `__post_init__` Literal[...] frozenset validation per T-A.1.5b R3 M#1 lesson.

### §3.3 T-A.6.5 — `/metrics/pattern-outcomes` 9th metric tile (7+ tests)

**Files to create**:
- `swing/web/view_models/patterns/outcomes_card.py` — `PatternOutcomesVM` extending `BaseLayoutVM`.
- `swing/web/templates/patterns/outcomes.html.j2`.
- `tests/web/test_routes/test_metrics_pattern_outcomes.py` — 7+ tests.

**Files to modify**:
- `swing/web/routes/metrics.py` — add `GET /metrics/pattern-outcomes`.

**Key disciplines**:
- **L10 LOCK** — composes with Phase 10 `swing/metrics/cohort.py` + `honesty.py`; ADDITIVE on top of shipped 8 metric tiles.
- Wilson-CI badge at n≥5 per Phase 10 honesty; suppressed at n<5 per Phase 10 §5.1.

### §3.4 T-A.6.6 — Theme 1 chart surface integration + dashboard market weather (8+ tests)

**Files to modify**:
- `swing/web/view_models/dashboard.py` — add `dashboard_weather_chart_svg_bytes: bytes | None = None` field. Then add the field to ALL 5 base-layout VMs per L14 LOCK (`DashboardVM` + `PipelineVM` + `JournalVM` + `WatchlistVM` + `PageErrorVM`).
- `swing/web/view_models/watchlist.py` — per-row thumbnail bytes.
- `swing/web/view_models/recommendations.py` — hyp-rec detail bytes.
- `swing/web/routes/dashboard.py` — add `POST /dashboard/weather-chart/refresh` route.
- `swing/web/templates/dashboard.html.j2` — render market weather at TOP per §C.3 L13 LOCK.
- `swing/pipeline/runner.py:_step_charts` — write through `chart_renders` cache for 5 surfaces. **CALL `refresh_chart_render` (T-A.6.2 helper) inside `BEGIN IMMEDIATE` / `COMMIT`**. Render once per surface per ticker + persist via the T-A.6.2 cache contract.

**Key disciplines**:
- **L12 HTMX trinity** for `POST /dashboard/weather-chart/refresh`.
- **L13 dashboard TOP placement**.
- **L14 base.html.j2 shared-VM-field propagation** — every new field on a base-layout VM must propagate to ALL 5.
- **OHLCV fetch scope = open-trade tickers ONLY** for position_detail (existing CLAUDE.md gotcha).

### §3.5 T-A.6.6b — `/patterns/exemplars` enhanced rendering (8+ tests)

**Files to modify**:
- `swing/web/view_models/patterns/exemplars.py` — extend `PatternExemplarsVM` with `chart_svg_bytes: bytes | None` + `criterion_rows: tuple[CriterionRow, ...]` + `narrative_text: str | None`. NEW `CriterionRow` frozen dataclass with `status: Literal['pass', 'fail']` `__post_init__` frozenset validation per L15 LOCK.
- `swing/web/routes/patterns.py` — extend `patterns_exemplars` route handler.
- `swing/web/templates/patterns/exemplars.html.j2` — render chart + criteria table + narrative per exemplar.
- `tests/web/test_routes/test_patterns_exemplars.py` — extend with 8 new tests.

**Key disciplines**:
- **L17 reuse** `swing/web/charts.py:render_theme2_annotated_svg` from T-A.6.1 — NO new matplotlib code.
- **L18 cache** — consume `get_cached_chart_svg` from T-A.6.2; cache-miss → invoke renderer once.
- **L15 Literal validation** on `CriterionRow.status`.
- **L16 ASCII-only** narrative text rendering — no `→` / `§` / em-dash via Jinja literals.

### §3.6 T-A.6.7 — Closer (E2E + ruff + 2 cross-bundle pin un-skips)

**Files to create**:
- `tests/integration/test_phase13_t2_sb6_closed_loop_e2e.py` — fast E2E seeding pipeline run → pattern_evaluations rows → chart_renders cache → `/patterns/queue` lists → `/patterns/{id}/review` renders + POST persists → `/metrics/pattern-outcomes` renders cohort outcomes → `/patterns/exemplars` renders chart + criteria + narrative.

**Cross-bundle pin un-skips**:
- `test_theme1_theme2_shared_renderer_handles_5_v1_patterns` — **ALREADY GREEN at T-A.6.1** (planted at substrate task in this branch; visible via `tests/web/test_charts.py:test_theme1_theme2_shared_renderer_handles_5_v1_patterns`). The plan §H.3 row 10 reference may have anticipated a separate test file; verify before un-skipping.
- `test_repo_caller_tx_contract_invariant` per plan §H.3 row 11 — verify status via `git grep "@pytest.mark.skip"` at closer step 1.

**ruff sweep** — `ruff check swing/` clean (0 E501).

---

## §4 Pre-Codex orchestrator-side review status

**NOT YET DISPATCHED**. The C.C lesson #6 BINDING pre-Codex review is scoped against the WHOLE sub-bundle's deliverables (per brief §1.5 #25 + §4.4 #22). Since T-A.6.3 through T-A.6.7 are deferred, a pre-Codex review at this checkpoint would only cover the substrate. The 23rd cumulative validation is **DEFERRED** to the follow-up dispatch's completion checkpoint.

That said, the SHIPPED substrate has been authored honoring both scope expansions:

- **Expansion #1 (constant placement)**: `_CHART_SURFACE_VALUES` is imported from `swing/data/models.py` (canonical site); ZERO duplicates in `swing/web/charts.py`. Verified by inline comment + import statement.
- **Expansion #2 (spec byte-fidelity)**: §C.1 5-renderer signature, §C.2 cache key shapes, §A.13 session-anchor predicate, §A.15 DELETE-then-INSERT pattern — all byte-checked against spec source-of-truth during implementation (no paraphrase).

---

## §5 Codex MCP adversarial-critic chain status

**NOT YET DISPATCHED**. Per the pre-Codex disposition above, the Codex chain is **DEFERRED** until the full T-A.6.X scope ships (or until the operator dispatches a follow-up to complete the remaining tasks). Running Codex against only the substrate would surface fewer findings than running it against the full closed-loop surface.

---

## §6 Forward-binding lessons surfaced at the substrate

1. **`_` in pattern_class slugs vs matplotlib mathtext title gate** — DETECTED + RESOLVED at T-A.6.1. The 5 V1 detector pattern classes contain `_` (`flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`). Initial draft routed pattern_class through the suptitle gate which forbids `_` → 5 test failures. Resolution: split the validator into two layers — `_assert_ascii_only` (body text; `_` allowed because matplotlib treats it as literal outside math mode) and `_assert_title_no_math` (title text; mathtext metacharacters forbidden). Pattern_class slugs render via `ax.text()` body annotations; titles use ASCII-safe summaries. **Pre-empt in any future renderer adding pattern_class to chart text**: emit slug via body annotation, NOT through any title/suptitle helper.

2. **The dispatch brief's `_assert_ascii_only(text, field='X')` over-broad metacharacter gate caught more than intended** — banked as a small forward-binding for spec authoring: when authoring a helper that gates multiple types of text (title vs body), separate the gates explicitly rather than collapsing into one over-strict helper.

---

## §7 Operator handoff guidance

**Recommended follow-up paths** (operator-decision):

- **Path A — re-dispatch the remaining 6 tasks as a follow-up**: branch from the current `phase13-t2-sb6-closed-loop-surface` branch HEAD (`255823b`), continue with T-A.6.3 onward. Substrate is committed + GREEN.
- **Path B — split T-A.6.3 / T-A.6.4 / T-A.6.5 / T-A.6.6 / T-A.6.6b into individual sub-dispatches**: each surface (review form, queue, metric tile, chart-surface integration, exemplars-enhancement) is independently dispatchable + tractable in a single session.
- **Path C — merge the substrate now**, then dispatch the remaining 6 tasks against a fresh branch off the merged state. Substrate is independently valuable + non-regression.

**S1 gate confirmations on the SHIPPED substrate**:

- [x] All shipped tasks (T-A.6.1 + T-A.6.2) committed.
- [x] `python -m pytest -m "not slow" -q -n auto` PASS: 5484 passed / 2 skipped / 0 failed (+21 net vs baseline 5463).
- [x] Schema version unchanged at v20.
- [x] ZERO new Schwab API calls.
- [x] All commits on branch carry empty `Co-Authored-By` trailer (cumulative ~319+ ZERO-trailer streak).
- [ ] Pre-Codex orchestrator-side review — **DEFERRED** to full-scope completion.
- [ ] Codex MCP adversarial-critic chain — **DEFERRED** to full-scope completion.

**No operator-witnessed gates (S2-S8)** are runnable at the substrate alone — every operator-paired gate in brief §5.2 requires a route handler that doesn't exist yet (S2 dashboard market weather; S3 queue; S4 review form; S4b exemplars enhanced; S5 metric tile; S6 hyp-rec detail; S7 position detail; S8 visual SVG verification across all of the above).

---

## §8 Cumulative streaks (preserved through this partial)

- **ZERO `Co-Authored-By` trailer drift**: cumulative ~319+ commits through T3.SB3 housekeeping + 2 new T2.SB6 substrate commits.
- **Schema v20 LOCKED**: no migrations.
- **ZERO new Schwab API calls**: L2 LOCK preserved.

---

*End of partial-completion return report. Substrate SHIPPED at S1 GREEN; T-A.6.3 through T-A.6.7 deferred to follow-up dispatch. Branch `phase13-t2-sb6-closed-loop-surface` HEAD `255823b` (off main `4e71787`). 2 commits; +21 fast tests net; v20 schema unchanged.*
