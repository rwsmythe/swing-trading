# Return report — Phase 13 brainstorm

## Spec location

`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines)

Commits on `phase13-brainstorm` branch:

- `b321142` — `docs(phase13): Phase 13 charts + pattern recognition + auto-fill + usability brainstorm spec` (initial draft, 1343 lines)
- `67859f2` — `docs(phase13): brainstorm spec — pre-Codex orchestrator-side review fixes` (5 LOCK-divergence deviations absorbed pre-chain per C.C lesson #6 BINDING; +11 lines)
- `9725500` — `docs(phase13): brainstorm spec — Codex R1 fix bundle (0C/10M/3m -> 0C/0M/0m)` (10 Major + 3 Minor; +81 lines)
- `6c9e929` — `docs(phase13): brainstorm spec — Codex R2 fix bundle (0C/7M/2m -> 0C/0M/0m)` (7 Major + 2 Minor; +7 lines)
- `481a0a2` — `docs(phase13): brainstorm spec — Codex R3 fix bundle (0C/5M/2m -> 0C/0M/0m)` (5 Major + 2 Minor; +23 lines)
- `cbc79b6` — `docs(phase13): brainstorm spec — Codex R4 fix bundle (0C/3M/2m -> 0C/0M/0m)` (3 Major + 2 Minor; +12 lines)
- `0ad0b2c` — `docs(phase13): brainstorm spec — Codex R5 fix bundle (0C/2M/2m -> 0C/0M/0m)` (2 Major + 2 Minor; +2 lines)
- `b149f18` — `docs(phase13): brainstorm spec — Codex R6 fix bundle (0C/2M/2m -> 0C/0M/0m)` (2 Major + 2 Minor; +4 lines)
- `4df0429` — `docs(phase13): brainstorm spec — Codex R7 trailing minor (0C/0M/1m -> NO_NEW_CRITICAL_MAJOR)` (1 Minor advisory; +0 net)

Total: 9 commits = 1 draft + 1 pre-Codex review-fix + 7 Codex-fix. ZERO Co-Authored-By footer drift across all 9 commits (~190+ project-cumulative streak preserved).

## Codex review history

| Round | Critical | Major | Minor | Verdict | Notes |
|---|---|---|---|---|---|
| Pre-Codex (orchestrator-side) | 0 | 5 LOCK-divergences | 0 | ABSORBED PRE-CHAIN | C.C lesson #6 BINDING; 9th cumulative validation |
| R1 | 0 | 10 | 3 | ISSUES_FOUND | Substantive schema + scope-locking + detector-coherence findings |
| R2 | 0 | 7 | 2 | ISSUES_FOUND | Coherence drift from R1 patches; competing-text replacement needed |
| R3 | 0 | 5 | 2 | ISSUES_FOUND | Cascade from three-column schema refactor at R2 |
| R4 | 0 | 3 | 2 | ISSUES_FOUND | Residual schema-CHECK coherence + label-source semantics |
| R5 | 0 | 2 | 2 | ISSUES_FOUND | Tight residual cross-column CHECK interactions |
| R6 | 0 | 2 | 2 | ISSUES_FOUND | Coherence cleanup from R5 fixes (FK action + column note drift) |
| R7 | 0 | 0 | 1 | **NO_NEW_CRITICAL_MAJOR** | Trailing minor advisory absorbed; chain CLOSES |

**Final verdict**: NO_NEW_CRITICAL_MAJOR after 7 substantive rounds.

**Convergent monotonic-Major taper**: 10 -> 7 -> 5 -> 3 -> 2 -> 2 -> 0.

**Aggregate**: 32 Critical-or-Major findings + 14 Minor advisory findings across 7 rounds. ALL resolved with code-content fixes; **ZERO ACCEPT-WITH-RATIONALE banked**. **ZERO Critical findings entire chain**. Matches project clean-record streak: Phase 10 arc 0 ACCEPTs across 5 sub-bundles; Phase 12.5 #1+#2+#3 brainstorms 0 ACCEPTs; this brainstorm continues the streak.

**Operator-override past MAX_ROUNDS=5**: invoked at R6 + R7 per project precedent (Phase 10 writing-plans 6 rounds; Phase 12.5 #1 brainstorm 7 rounds; Phase 12.5 #2 brainstorm 6 rounds — all with operator-override under clean convergent shape).

## Three highest-leverage design decisions

### 1. The `pattern_exemplars` three-column labeling refactor (R2 M#4 / R3 M#2 / R4 M#1 cascade)

The initial draft used a single `pattern_class` enum on `pattern_exemplars` with a `none` sentinel value for operator-rejected exemplars. Codex R2 M#4 caught the leak: `pattern_evaluations.pattern_class` + `chart_renders.pattern_class` also referenced this enum and inherited the polluted reject semantics. Resolved via THREE-COLUMN refactor at §3.1:

- `proposed_pattern_class` (NOT NULL; 5-value detector enum) — the detector class BEING evaluated.
- `final_decision` (NOT NULL; 5-value source-neutral enum: `confirmed` / `watch` / `rejected` / `relabeled` / `generated`) — the operator/labeler/generator decision.
- `final_pattern_class` (NULL except for `final_decision='relabeled'`) — the corrected class.

Plus the §3.0 shared `DETECTOR_PATTERN_CLASSES` enum LOCK + 5 numbered cross-column CHECK invariants schema-defending the matrix. The detector tables (`pattern_evaluations` + `chart_renders`) keep a clean 5-value `pattern_class` enum (no `none` leak).

**Why high-leverage**: pattern_exemplars is the corpus that grows over 12-18 months and powers template matching + outcome metrics. Wrong-shape schema would have polluted EVERY downstream cohort query + template-match retrieval; correcting it post-ship would require migration churn.

### 2. T1.SB0 OhlcvCache wiring as Phase 13 prerequisite Sub-bundle

The dispatch brief §1.5 enumerated 10 sub-bundles; scope-brainstorm §0.5.2 enumerated 11 (T1.SB0 added 2026-05-18 — operator-amended late). T1.SB0 closes the Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral: OhlcvCache was constructed with Schwab ladder hooks but NOT yet consumed by `_step_charts` (legacy yfinance path remained active at `swing/pipeline/runner.py:600-700`). T1.SB0 wires OhlcvCache into the chart-rendering daily-bar consumption path; Theme 2 detectors compose downstream over the same cache substrate. The brainstorm acknowledges the drift between dispatch brief §1.5 (10) and scope-brainstorm §0.5.2 (11) at §0.3 + §9 OQ-1; resolves to 11 sub-bundles per the operator-LOCKED scope.

**Why high-leverage**: without T1.SB0, Theme 2 detectors would carry an implicit yfinance dependency for daily bars — operationally fragile (rate limits + delisted-ticker errors) and architecturally regressive against the Phase 11 Sub-bundle C investment.

### 3. v20 migration landing timing via Option E (T2.SB1 task 1 + T3.SB1 branches off first-commit)

Codex R1 M#6 + R2 M#2 surfaced the v20 landing concurrency conflict: T2.SB1 + T3.SB1 are operator-locked CONCURRENT at scope-brainstorm §0.5.2, but BOTH consume v20 schema (T2.SB1 adds tables; T3.SB1 widens `fills`). The brainstorm enumerated 5 options (A: serial merge; B: dual-schema toleration; C: T-V20.PRELIM at both — REJECTED for duplicate-write-set conflict; D: new standalone sub-bundle — breaks 11-sub-bundle LOCK; **E: v20 lands as T2.SB1 task 1, T3.SB1 branches off T2.SB1's first-commit SHA**, concurrent on bulk of work, merge ordering T2.SB1 first then T3.SB1).

**Why high-leverage**: this is the operator-pre-writing-plans coordination point that determines whether the project gets concurrent dispatch or serial merge for the first ~2-3 weeks of Phase 13 execution. The brainstorm-recommended Option E preserves the LOCK while closing the duplicate-write-set defect Option C would have created.

## Theme 1 chart rendering decisions

**Locked**:
- T1.SB0 OhlcvCache wiring as prerequisite (per §4.1).
- 5 chart surfaces: watchlist row / hyp-rec detail / position detail / market weather mini-chart / Theme 2 annotated (per §4.2).
- Rendering tech: matplotlib SVG inline (Phase 10 §A.10 LOCK precedent; avoids mathtext gotcha entirely; ASCII-only on all rendered text).
- Cache architecture: NEW `chart_renders` table with 3 partial unique indexes per surface class + cross-column CHECK invariant (closes SQLite NULL-distinct semantics defect).
- Market weather mini-chart placement: TOP of `/dashboard` above Phase 10 tile navigator.
- Theme 1 + Theme 2 coupling at T2.SB6 closes the arc (annotated chart IS the v2 brief §9.2 evidence-display deliverable AND the Theme 1 deepest-coverage chart).

**Rationale**: V1 SVG inline gives operator the immediate value (deeper chart surfaces) without HTMX-JS-coupling complexity Phase 13's other themes don't tax. V2 candidate: interactive client-side JS chart library (TradingView Lightweight Charts / Plotly). Cache architecture decision separates `chart_renders` from `OhlcvCache` to avoid the cache+executor race gotcha at write time.

## Theme 2 pattern recognition decisions

**Locked per pattern** (§5.2-§5.6):
- **VCP** — 8 rule criteria (Stage 2 + prior uptrend >= 30%/8w + N>=2 contractions with monotonic depth + volume decline + duration 21-84d + pivot near base top + optional breakout volume); tolerance bands per criterion; `VCPEvidence` dataclass shape.
- **Flat base** — 7 criteria; range 3-12% width; slope < 0.005/week; ATR/mid_range <= 0.025; duration >= 35d.
- **Cup-with-handle** — 8 criteria + rounded-vs-V test centered on `cup_bottom_date ±10 days` (5+ bars within 2% of bottom = rounded; <=2 = V-reject; 3-4 = marginal).
- **High-tight flag** — 6 criteria; pole >= 90% over 4-8w; consolidation pullback <= 25% over 3-5w; volume contracts.
- **Double-bottom-W** — 8 criteria; trough_1 drawdown >= 15%; center peak >= 50% retracement; trough_2 within ±5% OR <= 5% undercut; undercut bonus +0.10 composite score.

**Locked overall**:
- Foundation primitives (§5.1): EMA smoothing primary + kernel regression secondary; zigzag adaptive-threshold extrema (monotonic_narrow=True for VCP-style); variable-window candidate generator with anchor-point search.
- Template matching method (§5.7): DTW with Sakoe-Chiba band (window=0.1 × series length); SBD as V2 fallback if §5.7 120s benchmark gate fails.
- Composite scoring (§5.8): `0.60 × geometric_score + 0.40 × template_match_score`; V1 not calibrated (operator triage signal, not probability gate).
- Dev-time labeling infrastructure (§5.9): Claude Code subagent dispatch per-(window, pattern_class) seed tuple via NEW `swing patterns label-exemplars` CLI; selective Codex 2nd reviewer phased (random 15% at T2.SB1; +high-stakes geometric_score disagreement at T2.SB3+/SB4 retroactively).
- Closed-loop surface T2.SB6 (§5.10): NEW `/patterns/{candidate_id}/review` web route + NEW `/metrics/pattern-outcomes` 9th metric tile (composes with Phase 10 metrics architecture; reuses honesty.py + BaseLayoutVM mixin + §A.18 discrepancies helper).
- Drift logging baseline substrate (§5.11): `pattern_evaluations.feature_distribution_log_json` per detector run; monitoring side SPLIT to Phase 13.5.

**Rationale**: v2 brief §5.1 illustrative VCP criteria precedent encoded verbatim with tolerance bands (closes v2 brief §5.1 weakness "hand-tuned thresholds"). 5 buy-side patterns per L2; sell-side BANKED to Phase 14 per L3. Composite scoring follows v2 brief §17 item 7 recommendation. ML re-ranker DEFERRED indefinitely per L4 + v2 brief §16.6.

## Theme 3 auto-fill decisions

**Locked**:
- Entry auto-fill T3.SB1 (§6.1): `GET /trades/entry/form` calls Schwab Trader API `account_orders` + `account_details`; auto-populates `entry_date` / `entry_price` (execution-grain via post-Phase-12 Sub-bundle 1 mapper) / `initial_shares`; server-stamps `fill_origin` per state machine (`schwab_auto` / `schwab_auto_then_operator_corrected` / `operator_typed`); hidden audit anchors `schwab_source_value_json` + `auto_fill_audit_at`. `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature + `apply_overrides(cfg)` discipline at every Schwab entry point.
- Exit auto-fill T3.SB2 (§6.2): mirrors T3.SB1 architecture; handles partial exits via operator-pick OR consolidated value.
- Review auto-fill T3.SB3 (§6.3): priors from previous reviews (mistake_tags / process_grade baseline / lesson_learned candidates) + MFE/MAE from OhlcvCache (post-T1.SB0 substrate) + period-review section-text auto-fill.
- `fill_origin` enum widening LOCK (§6.4): 5-value CHECK enum; backfill all existing fills to `operator_typed`; V2 candidate banks historical correction-chain backfill into `schwab_source_value_json`.
- Cross-bundle dependencies (§6.5): T3.SB1 concurrent with T2.SB1; T3.SB2 sequenced after T2.SB3 (Schwab consumer merge-avoidance); T3.SB3 sequenced after T2.SB5 (OhlcvCache + candidate-window primitives).

**Rationale**: Absorbs original Phase 12.5 #2 fill auto-population at trade-entry per L10. Composes over post-Phase-12 Sub-bundle 1 execution-grain mapper + Phase 12 Sub-bundle B `apply_overrides` cascade. Server-stamping at handler entry per Phase 8 R2-R5 gotcha family.

## Theme 4 usability list captured

**Status**: usability list elicitation DEFERRED to orchestrator-pre-writing-plans operator-paired session (per dispatch brief §8 fallback). Operator did not provide the list at this implementer-dispatch time + work-without-stopping mode prevents interactive elicitation.

**T4.SB scope LOCK at brainstorm time** (§7.1): T4.SB ships **Q4 close-tracking flag as MINIMUM BINDING scope** (per §7.2 D-Q4.1..D-Q4.7 below). Operator-elicited usability list at orchestrator-pre-writing-plans produces a SPEC §7 AMENDMENT consumed by the writing-plans dispatch. If empty, T4.SB ships Q4-only without scope loss. If non-empty, T4.SB scope expands by N items + writing-plans decomposes the extended scope.

**Operator-elicited list verbatim** (PENDING — orchestrator-pre-writing-plans elicitation):

[Empty — to be amended pre-writing-plans dispatch]

**Q4 close-tracking flag scope decisions** (§7.2; 7 architectural sub-decisions D-Q4.1..D-Q4.7 with brainstorm-default recommendations):

| ID | Decision | Brainstorm-default |
|---|---|---|
| D-Q4.1 | Schema location | **NEW table** `watchlist_close_track_flags` (Option B); persistence across pipeline-run rotation; NOT a column on `candidates` |
| D-Q4.2 | Setting/unsetting UI | **Web toggle + CLI** (both surfaces; one source of truth) |
| D-Q4.3 | Persistence semantics | **Persistent until operator-cleared OR auto-clear on position open** (transactional discipline: reject-caller-held-tx + BEGIN IMMEDIATE uniform-regardless-of-env + sandbox short-circuit in inner + audit-row append-only) |
| D-Q4.4 | Visual rendering | **Badge inline on watchlist row + sort-priority-first** (false-negative-guard mechanism; ASCII-only per cp1252 stdout safety) |
| D-Q4.5 | Filtering interaction | **Flagged tickers UNION'D with pipeline algorithm output** (false-negative guard; sub-badge "operator-flagged; algo dropped" when divergent) |
| D-Q4.6 | Hyp-rec relation | **NO — watchlist-surface-only** (preserves hyp-rec semantic clarity; V2 candidate: "elevated to hyp-rec" toggle) |
| D-Q4.7 | Audit trail | **YES — append-only `watchlist_close_track_flag_events` table** with timestamp + surface + reason + flag_source per Phase 12 C.A `reconciliation_corrections` precedent |

Schema folds into v20 (per L6 single-migration LOCK; v21 split rejected).

## Sub-bundle decomposition refinement (per §2.5)

**Locked**: 11 sub-bundles in dispatch sequence per scope-brainstorm §0.5.2 LOCK; per-sub-bundle scope at task-grain enumerated at §8.2; cross-sub-bundle dependencies + test/schema projections.

| SB | Test delta projection | Schema delta |
|---|---|---|
| T1.SB0 | +20-40 fast | NONE |
| T2.SB1 | +50-90 fast + ~30-80 silver-tier exemplars persisted manually | v20 lands here per Option E LOCK |
| T3.SB1 | +40-70 fast + 1 slow E2E | v20 (consumes via branch-off-T2.SB1-first-commit) |
| T2.SB2 | +60-100 fast | NONE |
| T2.SB3 | +90-150 fast + 1 slow E2E | NONE |
| T3.SB2 | +40-70 fast + 1 slow E2E | NONE |
| T2.SB4 | +70-120 fast | NONE |
| T2.SB5 | +60-100 fast | NONE |
| T3.SB3 | +50-90 fast | NONE |
| T2.SB6 | +70-120 fast + 1 slow E2E | NONE |
| T4.SB | +40-70 fast (incl Q4) | NONE |

**Cumulative**: +590-1020 fast tests + 4 slow E2E across Phase 13 arc; baseline 4924 fast (Phase 12.5 #2 ship); Phase 13 close projection ~5500-5940 fast.

**Estimated wall-clock**: ~3-6 weeks operator-paced per scope-brainstorm §0.5.2 + `feedback_time_estimates_overstated.md` calibration.

## Open questions for orchestrator triage

| OQ | Topic | Brainstorm recommendation | Disposition |
|---|---|---|---|
| OQ-1 | Sub-bundle count drift (10 vs 11) | Amend dispatch brief §1.5 in writing-plans phase to reflect 11 (per scope-brainstorm §0.5.2 operator-LOCK) | BINDING |
| OQ-2 | Chart rendering tech + cache architecture | V1: matplotlib SVG inline + `chart_renders` table (per Phase 10 §A.10 LOCK precedent); V2: interactive client-side JS | BINDING V1 |
| OQ-3 | `pattern_class` enum scope + table location | New `pattern_evaluations` table (NOT widen `pipeline_pattern_classifications`); 5 V1 values; sell-side reserved for Phase 14 | BINDING |
| OQ-4 | Template matching distance metric | DTW with Sakoe-Chiba band (window=0.1 × series length); SBD V2 fallback if §5.7 120s benchmark fails | BINDING V1 |
| OQ-5 | Codex SELECTIVE policy definition | Phased rollout: T2.SB1 random 15% only; T2.SB3+/SB4 adds high-stakes geometric_score disagreement clause | BINDING |
| OQ-6 | Operator-paired exemplar bootstrap workflow | Same shape as post-Phase-12 Sub-bundle 1 cassette session precedent | BINDING |
| OQ-7 | Theme 3 `fill_origin` enum values + backfill | V1: simple backfill (all existing rows -> `operator_typed`); V2: historical correction-chain backfill | BINDING V1 |
| OQ-8 | Theme 3 review auto-fill MFE/MAE candle-data source | OhlcvCache (post-T1.SB0); yfinance V2-fallback only | BINDING |
| OQ-9 | Drift logging side — `feature_log` table vs JSON in `pattern_evaluations` | JSON column on `pattern_evaluations` (V1); promote to dedicated table V2 if Phase 13.5 demands | BINDING V1 |
| OQ-10 | Closed-loop surface T2.SB6 route location | BOTH NEW `/patterns/{candidate_id}/review` route AND NEW `/metrics/pattern-outcomes` 9th metric tile | BINDING |
| OQ-11 | T2.SB1 pattern-labeler subagent definition location | `.claude/agents/pattern-labeler.md` (Claude Code standard project-local convention) | BRAINSTORM-RECOMMENDATION |
| OQ-12 | v20 migration landing timing | Option E: v20 lands as T2.SB1 task 1; T3.SB1 branches off T2.SB1's first-commit SHA; concurrent on bulk; merge order T2.SB1 first | BINDING |

## Capture-needs feedback FOR PHASE 13 WRITING-PLANS

- **NEW DETECTOR_PATTERN_CLASSES enum at §3.0 LOCK** — writing-plans phase emits a Python-side constant `DETECTOR_PATTERN_CLASSES = ('vcp', 'flat_base', 'cup_with_handle', 'high_tight_flag', 'double_bottom_w')` in `swing/patterns/__init__.py` (or similar) + dataclass `__post_init__` validators on all 4 referencing columns. Schema-CHECK + Python-constant + dataclass-validator paired discipline applies (Phase 12 C.A T-A.2 LOCK).
- **NEW pattern_exemplars schema** — 3-column labeling (proposed_pattern_class + final_decision + final_pattern_class) + cross-column CHECK invariants (5 numbered at §3.1; relabel-vs-non-relabel coherence + source-vs-decision matrix + parent_exemplar_id linkage + geometric_score_json nullability + labeler_evidence_json source coherence). Writing-plans translates these into per-task acceptance criteria.
- **NEW chart_renders schema** — 3 partial unique indexes per surface class + 1 cross-column CHECK; writing-plans phase derives the discriminating-test pattern (insert duplicate-by-NULL-fields candidates per surface class + assert reject).
- **T-V20.PRELIM Option E coordination** — writing-plans for T2.SB1 + T3.SB1 must enumerate the T3.SB1-branches-off-T2.SB1-first-commit discipline + merge ordering (T2.SB1 first; T3.SB1 second).
- **T1.SB0 OhlcvCache wiring 3-prerequisite refactor** — writing-plans for T1.SB0 must decompose: (a) `fetcher.get` weekly-refresh + `archive_history_days` semantics aligned to ladder window; (b) shape reconciliation (`to_dataframe()` capitalized cols + DatetimeIndex vs legacy fetcher's archive-managed shape); (c) per-cache locking + lifecycle semantics for OhlcvCache.
- **Tolerance-band uniformity LOCK at §10.6** — writing-plans must translate the tolerance semantics ("±X%" / "NONE — hard gate" / "NONE — bounds") into per-criterion test cases. Each pattern detector's discriminating tests assert PASS at tolerance edge + FAIL at tolerance breach.
- **Cup curvature definition LOCK at §10.7** — writing-plans for T2.SB3 cup-with-handle detector must implement curvature test centered on `cup_bottom_date ±10 days` with 5+/2-/3-4 bar thresholds.
- **DTW pruning LOCK at §5.7** — writing-plans for T2.SB5 must enumerate the 4-rule pruning (per-pattern filtering + geometric_score >= 0.4 pre-gate + max 3 candidate windows per ticker per pattern per run + exemplar corpus subsampling at 50 when corpus > 100) + pytest-benchmark gate at 120s ceiling.
- **Codex phased SELECTIVE policy at §5.9** — writing-plans must encode the T2.SB1 random-15%-only vs T2.SB3+/SB4 random-15%+high-stakes-disagreement split + the retroactive evaluation of T2.SB1 corpus when T2.SB3+/SB4 ship.
- **Theme 3 Schwab integration discipline** — writing-plans for T3.SB1 + T3.SB2 must enumerate `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature + `apply_overrides(cfg)` at every handler entry + empty-state + DEGRADED-state + sandbox-state handling.
- **HTMX gotcha trinity for every new form-driven route** — Theme 1 dashboard chart-refresh button + Theme 3 entry/exit/review forms + T4.SB Q4 toggle button + T2.SB6 review form: HX-Request propagation on embedded forms + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted disciplines per Phase 5/6 lessons.
- **Base-layout VM banner pin** — every new VM extending `base.html.j2` (Theme 1 chart VMs + Theme 2 review VM + Theme 3 form VMs + T4.SB Q4 watchlist VM) populates `unresolved_material_discrepancies_count` + `banner_resolve_link` per Phase 10 T-E.3 + Phase 12.5 #2 13-VM retrofit precedent.
- **§7.1 usability-list elicitation** — orchestrator drives operator-paired session BEFORE writing-plans dispatch to amend §7 with verbatim list + classify + size each issue.

## Outstanding capture-needs that DEFER to Phase 13.5 / Phase 14

- **Phase 13.5 (drift detection monitoring side)**: 4 surfaces (feature drift / pattern frequency drift / outcome drift / self-drift) per v2 brief §14 — composes over Phase 13 logging-side baseline material (`pattern_evaluations.feature_distribution_log_json`). Phase 13.5 dispatch UNBLOCKED when Phase 13 V1 has ≥1 month of `feature_distribution_log_json` accumulation.
- **Phase 14 (sell-side detector module)**: H&S top + climax run + Stage 4 breakdown + MA50/MA200 violations per v2 brief §4.3 + §10 Phase 8 gated. Widens `DETECTOR_PATTERN_CLASSES` + adds new geometric criteria per pattern.
- **Phase 14+ (ML re-ranker)**: indefinitely deferred per v2 brief §16.6 + 7 gates G1-G7 not yet met. V1 composite_score is NOT calibrated; V2 gates on 200 confirmed positives per pattern class + quarterly re-grading discipline.
- **Phase 14+ (Matrix Profile-based exemplar retrieval at scale)**: per v2 brief §5.8 + §10 Phase 7; gated on curated exemplar corpus size.
- **Phase 14+ (Shapelet-based detection)**: per v2 brief §5.9; gated on labeled corpus.
- **V2 candidates banked at §13** (22 items): interactive client-side JS chart library; per-row sparklines; multi-timeframe chart toggle; annotation editor; z-score normalization; composite_score calibration; SBD template-matching alternative; etc.
- **V2 calibration discipline (per v2 brief §13.1)**: any "confidence score" used to gate decisions must be calibrated (Brier score + isotonic regression). V1 composite_score is operator-triage signal NOT decision gate.
- **Operator-elicited usability list amendment** (per §7.3 elicitation template) — orchestrator-pre-writing-plans operator-paired elicitation produces §7 amendment + sizes each issue per §7.4 framework.
- **OQ-12 confirmation** (v20 migration landing timing) — operator-pre-writing-plans confirms Option E vs fallback Option A.
- **All 12 OQs** — operator-pre-writing-plans triage of brainstorm-recommendations (most BINDING-recommended; OQ-11 BRAINSTORM-RECOMMENDATION-only).

---

*End of return report — Phase 13 brainstorm. Spec at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (1483 lines; 4-theme architectural arc + Q4 fold-in; 11 sub-bundles; 12 OQs; 7 Q4 sub-decisions; ZERO ACCEPT-WITH-RATIONALE across 7 Codex rounds; convergent monotonic-Major taper 10 -> 7 -> 5 -> 3 -> 2 -> 2 -> 0; ZERO Critical findings entire chain; ZERO Co-Authored-By footer drift across 9 commits). Writing-plans dispatch UNBLOCKED pending operator-pre-writing-plans triage of 12 OQs + §7.1 usability-list elicitation.*
