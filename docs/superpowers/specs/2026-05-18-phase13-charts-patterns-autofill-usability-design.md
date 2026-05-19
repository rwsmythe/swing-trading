---
title: "Phase 13 — Charts + Pattern Recognition + Auto-fill + Usability Design Spec"
purpose: "Brainstorm-locked architectural design for Phase 13 4-theme arc + Theme 4 Q4 close-tracking flag fold-in"
version: "1.0"
created: "2026-05-18"
anchored_on:
  - "reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md (901 lines; operator-authored 2026-05-08; AI-ingestion-ready)"
  - "docs/phase13-scope-brainstorm.md §0.5 (operator-locked 2026-05-17; 4 themes / 11 sub-bundles / 11 design locks)"
  - "docs/phase13-brainstorm-dispatch-brief.md (implementer dispatch with §2.4 Q4 fold-in amendment 2026-05-18)"
spec_format_mirror: "docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md (post-Phase-12 brainstorm canonical; 1086 lines; ZERO ACCEPT-WITH-RATIONALE)"
binding_constraints:
  - "11 §1.1 operator-locked decisions (chart pattern v2 brief inheritance + sell-side BANKED + ML re-ranker DEFERRED + drift split + run-time AI inferencing FORBIDDEN)"
  - "Schema v19 -> v20 (single migration confirmed); v21 candidates flagged per theme"
  - "ASCII-only on runtime CLI paths (Windows cp1252 stdout gotcha)"
  - "NO Co-Authored-By footer on ANY commit (~175+ cumulative ZERO drift streak)"
  - "v2 brief §1 introspection HARD constraint preserved verbatim across every detector + classifier output"
---

# Phase 13 Design Spec — Charts + Pattern Recognition + Auto-fill + Usability

## §0 Document scope and audience

This spec is the brainstorm-phase output for the Phase 13 architectural arc. It is consumed by:

1. **The orchestrator-pre-writing-plans operator review pass** that locks the §15.B-style still-open items at brainstorm defaults (Phase 12.5 #1 + #2 + #3 brainstorm precedent).
2. **The writing-plans-phase implementer** who decomposes each of the 11 sub-bundles into per-task acceptance criteria with adversarial Codex review.
3. **The executing-plans implementers** dispatched per sub-bundle who consume operator-locked decisions verbatim and produce shipped code under adversarial review.

It is NOT a plan document (no per-task acceptance criteria; no SQL DDL; no code drafting). It IS a section-numbered architectural design with locked decisions, open questions enumerated with recommendations, schema sketches, and discriminating examples — mirroring the canonical post-Phase-12 brainstorm spec.

### §0.1 Date and path drift acknowledgment

The dispatch brief §2 names the output path `docs/superpowers/specs/2026-05-17-phase13-design.md`. Actual creation date is 2026-05-18 (post-Phase-12.5-arc-close). Path follows project naming convention (verbose hyphenated kebab-case after date prefix) and `2026-05-18-...` to reflect actual creation. Brief drift banked as orchestrator-pre-writing-plans triage item; spec authoritative.

### §0.2 Reading order for the orchestrator

1. **§1** — strategic context + 11 binding LOCKS (do NOT re-litigate).
2. **§2** — v2 brief inheritance summary + dispatch-brief reconciliations.
3. **§3** — schema v19 → v20 sketch + v21 candidates flagged per theme.
4. **§4–§7** — Theme 1 / Theme 2 / Theme 3 / Theme 4 architecture (one section per theme).
5. **§8** — sub-bundle decomposition refinement (11 sub-bundles per scope-brainstorm §0.5.2 LOCK).
6. **§9** — OQ-1..OQ-12 + Q4 sub-decisions D-Q4.1..D-Q4.7 (the orchestrator-pre-writing-plans lock surface; OQ-11 added in pre-Codex review; OQ-12 added in Codex R1 fix bundle).
7. **§10** — five-pattern discriminating-example walkthroughs (rule criteria + composite scoring + structural evidence).
8. **§11..§15** — forward-binding lessons, risks, V2 candidates, out-of-scope reaffirmation, references.

### §0.3 Drift between dispatch brief §1.5 (10 sub-bundles) and scope-brainstorm §0.5.2 (11 sub-bundles)

The dispatch brief §1.5 enumerates 10 sub-bundles. The operator-locked scope-brainstorm §0.5.2 (newer; 2026-05-18 T1.SB0 amendment) enumerates **11 sub-bundles** with T1.SB0 as the FIRST in dispatch sequence (OhlcvCache→`_step_charts` wiring; releases the Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral). Per scope-brainstorm `DO NOT re-litigate §0.5` LOCK, this spec follows §0.5.2 — Phase 13 has 11 sub-bundles. The dispatch brief §1.5 table is treated as a stale view of the same operator-locked decomposition; the discrepancy is surfaced for orchestrator-pre-writing-plans triage at §9 OQ-1.

---

## §1 Strategic context — 11 operator-locked binding decisions (do NOT re-litigate)

Per `docs/phase13-scope-brainstorm.md` §0.5 (LOCKED 2026-05-17 via operator-orchestrator scope conversation):

| # | Decision | LOCK | Rationale source |
|---|---|---|---|
| L1 | **Algorithm posture**: rule-based geometric PRIMARY; template matching SECONDARY; NO run-time AI inferencing | Claude API in pipeline runtime FORBIDDEN; dev-time Claude Code subagent dispatch for labeling per v2 brief §8.2 IS allowed (silver-tier with `ai_labeler_version` tracking) | Operator: "Claude API in runtime pipeline is not acceptable"; v2 brief §1 introspection HARD constraint |
| L2 | **V1 pattern set**: 5 buy-side patterns | VCP + flat base + cup-with-handle + high-tight-flag + double-bottom-W (collapses v2 brief's Phase 1 + Phase 3 into Phase 13 V1) | Operator scope conversation 2026-05-17 |
| L3 | **Sell-side detector module**: BANKED to Phase 14 | H&S top + climax run + Stage 4 breakdown + MA50/MA200 violations all OUT | v2 brief §4.3 + §10 Phase 8 gated |
| L4 | **ML re-ranker**: DEFERRED indefinitely | 12-18 months minimum per v2 brief §16.6; 7 gates G1-G7 not yet met | Operator: "not near-term unless clear and convincing evidence" |
| L5 | **Drift detection monitoring side**: SPLIT to Phase 13.5 | 4 surfaces feature/pattern frequency/outcome/self-drift; Phase 13 BAKES IN the LOGGING side (feature distributions captured per detector run) so Phase 13.5 has baseline material; Phase 13 does NOT design dashboards | v2 brief §14 |
| L6 | **Schema appetite**: v19 → v20 single migration confirmed; v21+ possible per theme | `chart_pattern_evaluation` widening + `pattern_exemplars` library table + `label_source` enum + `ai_labeler_version` tracking + `fill_origin` enum widening (Theme 3) + Q4 close-tracking-flag schema (Theme 4) | Operator: "Open to heavy schema work for the right architectural pivot" |
| L7 | **Strategic posture**: 100% operational | Branch B priority-stack continuation per V2.1 §VI; research-branch (V2.1 §V) Phase 0 activation NOT in Phase 13 scope | Operator decision 2026-05-17 |
| L8 | **Single-strategy focus**: SEPA + DST | 6mo operator strategic intent; multi-cohort/multi-strategy deepening is Phase 14+ candidate | Operator decision |
| L9 | **Codex as second reviewer**: SELECTIVE (NOT blanket) | 10-20% spot-check tier + high-stakes individual labels where Claude silver confidence diverges from rule-tier evidence | Operator scope conversation |
| L10 | **Theme 3 absorbs original Phase 12.5 #2**: fill auto-population at trade-entry | Entries + exits + reviews + period reviews owned coherently by Theme 3 | Phase 12.5 RESCOPED 2026-05-17 |
| L11 | **Theme 4 elicitation**: operator drafts unreported-usability-issues list at brainstorm time | Brainstorm captures verbatim + classifies + sizes; T4.SB closer Sub-bundle implements; **AMENDMENT 2026-05-18**: Q4 operator close-tracking flag for watchlist symbols folded into T4.SB with 7 architectural sub-decisions for Codex chain to resolve | Operator decision 2026-05-17 + Q4 fold-in operator decision 2026-05-18 |

### §1.1 Concrete current-state evidence (per dispatch brief §1.2)

- **Phase 4 `chart_pattern_evaluation`** is operator-classification-only with system-classifier flag (per migration 0010). "Very basic" — does NOT generate annotated charts for hyp-recs; pattern recognition is essentially manual.
- **OhlcvCache + ohlcv_archive parquet caching** (Phase 11 Sub-bundle C) means broader chart rendering no longer burns yfinance quota for multi-day-list tickers. The architectural constraint that previously blocked Phase 13-style chart breadth is RESOLVED — but OhlcvCache is constructed with Schwab ladder hooks and NOT yet consumed by `_step_charts` (per Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral; `swing/pipeline/runner.py:620-639` legacy `fetcher.get(...)` path still active for daily-bar chart generation). Phase 13 T1.SB0 closes this deferral.
- **Methodology corpus** at `reference/methodology/` (3 files; 415 lines: Minervini Trend Template + Minervini sell-side rules + DST take-profit-and-trail) is sufficient for the 5 buy-side V1 pattern set algorithm-design substrate.
- **Closed-loop infrastructure** is LARGELY shipped: `candidates` table (Phase 4) + `trades.candidate_id` FK (Phase 7) + `trades.realized_R_if_plan_followed` + `actual_realized_R_effective` (Phase 7) + `review_log` per-trade reviews (Phase 6) + Phase 10 metrics hit rate + R-multiple per cohort. v2 brief §6.4 label schema (`candidate_id` → `trade_id` → outcome) maps onto existing schema.
- **Schwab Trader API integration** (Phase 11 Sub-bundle B) + `apply_overrides(cfg)` cascade (Phase 12 Sub-bundle B) + `construct_authenticated_client` 4-arg signature (Phase 12 Sub-bundle B + post-Phase-12 Sub-bundle 1) — all surfaces Theme 3 auto-fill consumes are operational.
- **Post-Phase-12 Sub-bundle 1 SHIPPED 2026-05-17** — `SchwabExecutionLeg` dataclass + `SchwabOrderResponse.executions` field + execution-grain comparator + Shape C classifier predicate + cassette infrastructure at `tests/integrations/cassettes/schwab/` + `scripts/record_schwab_cassettes.py` recording script. Phase 13 Theme 2 may compose over execution-grain data for pattern detection (e.g., breakout-volume validation per v2 brief §5.1 illustrative VCP criterion #7).

### §1.2 Schema verification surfaced during brainstorm reads

- **`candidates.pattern_class` column DOES NOT EXIST** per `swing/data/migrations/0001..0019` grep. The dispatch brief §1.3 claim that "candidates table (Phase 4 evaluation): pattern_class column already exists per migration `0010_trade_chart_pattern.sql`" is incorrect; migration 0010 widens `trades` (NOT `candidates`) with `chart_pattern_classification_pipeline_run_id`. The pattern-classification surface that DOES exist is the separate `pipeline_pattern_classifications` table (migration 0009) which carries a `classification` column whose CHECK enum scope is verified at writing-plans time. **Phase 13 Theme 2 must propose either**: (a) widen `pipeline_pattern_classifications.classification` CHECK enum to include the 5 V1 patterns; OR (b) add a new `candidates.pattern_class` column with CHECK enum + FK to a NEW `pattern_exemplars` library table. See §3 schema sketch + §9 OQ-3.
- **`fill_origin` not present in `fills` schema** per grep (no matches across `swing/`). Theme 3 introduces this as a NEW column on `fills` with CHECK enum widening — see §3 + §9 OQ-7.

### §1.3 Binding integrations Phase 13 consumes

Phase 13 composes over shipped Phase 4 + Phase 6 + Phase 7 + Phase 9 + Phase 10 + Phase 11 + Phase 12 + post-Phase-12 surfaces. Per dispatch brief §1.3 (rephrased for accuracy after §1.2 corrections):

- **`pipeline_pattern_classifications` (Phase 4 evaluation)**: pattern-classification surface that DOES exist. Phase 13 Theme 2 either widens its `classification` CHECK enum OR introduces a parallel `candidates.pattern_class` column with CHECK enum. Operator-pre-writing-plans-decision at §9 OQ-3.
- **`trades.candidate_id` FK (Phase 7)**: closed-loop back-link. Phase 13 Theme 2 Sub-bundle T2.SB6 surfaces outcome distributions per (effective) pattern-class cohort dimension. Reuses Phase 10 metrics cohort architecture.
- **`review_log` (Phase 6)**: per-trade review with frozen aggregates. Phase 13 Theme 3 review auto-fill at T3.SB3 pre-populates review form fields from prior reviews + MFE/MAE from candles. Composes with Phase 8 daily_management_records for MFE/MAE history.
- **`fills` table (Phase 7)**: introduces `fill_origin` enum column (Theme 3 auto-fill provenance). Schema v20 likely adds this.
- **`schwab_api_calls` (Phase 11)**: audit table for Schwab API invocations. Phase 13 Theme 3 entry/exit auto-fill emits new audit rows with `surface='trade_entry'` and `surface='trade_exit'` (CHECK enum widening; v20).
- **`reconciliation_corrections` (Phase 12 C.A)**: Theme 3 entry auto-fill prevents the "fiction-vs-truth" divergence pattern Phase 12 C addressed. Operator-typed-from-memory entry fills generated reconciliation discrepancies (CVGI 41 + DHC 39 + VSAT 40 + LION 45); Theme 3 closes the SOURCE side prospectively.
- **OhlcvCache + ohlcv_archive (Phase 11 Sub-bundle C)**: data substrate Theme 2 pattern detection consumes for daily + weekly bar processing. T1.SB0 wires OhlcvCache into `_step_charts`; Theme 2 detectors composed downstream consume the same cache.
- **Phase 4 evaluation pipeline**: universe filter + Stage 2 trend template + RS rank are LARGELY shipped. v2 brief §6.1 "Universe pipeline" Phase 0 is largely closed; remaining gaps deferred to writing-plans-phase per operator decision 2026-05-17.
- **Phase 10 metrics dashboard architecture**: 8 metric surfaces + 13 base-layout VMs (per Phase 12.5 #2 retrofit). Theme 2 T2.SB6 outcome-distributions surface composes as a 9th metric surface; every new VM extending `base.html.j2` MUST populate `unresolved_material_discrepancies_count` + `banner_resolve_link` (Phase 10 + 12.5 #2 base-layout pin discipline).
- **Phase 12 Sub-bundle B + post-Phase-12 Sub-bundle 1 Schwab integration discipline**: `apply_overrides(cfg)` cascade at all new Schwab entry points; `construct_authenticated_client` 4-arg signature; cassette infrastructure with `before_record_request` URI/path sanitization + `before_record_response` body sanitization; `surface='trade_entry'` / `surface='trade_exit'` enum widening pattern.

### §1.4 Inherited DROP rules (per dispatch brief §1.4)

- **No magnitude-based threshold** (Phase 12 Sub-bundle C §1.1 lock #3 inheritance; v2 brief §5.1 weaknesses → mitigated via tolerance bands; same DROP applies to pattern-detection thresholds).
- **No retroactive audit-row rewriting** (Phase 12 Sub-bundle C OQ-G inheritance).
- **No re-litigating §1 LOCKS** (operator-locked).
- **No run-time AI inferencing** (L1; permanently out of scope).
- **No sell-side detector** (L3; Phase 14 banked).
- **No ML re-ranker** (L4; indefinitely deferred).
- **No drift monitoring/dashboard side** (L5; Phase 13.5 banked; ONLY logging-side baseline in Phase 13).
- **No multi-cohort architectural deepening** (Phase 14+ candidate; L8 single-strategy focus).
- **No image-based CV** (v2 brief §5.6 permanently out of scope; interpretability violation).
- **No sequence transformers** (v2 brief §5.7 permanently out of scope).
- **No harmonic / candlestick / intraday patterns** (v2 brief §4.4 permanently out of scope).
- **No fixed-window pattern detection** (v2 brief §3 — variable-window candidate generator with anchor-point search; VCP-style patterns have variable durations).

---

## §2 V2 brief inheritance + dispatch-brief reconciliation

### §2.1 What Phase 13 absorbs from v2 brief

The operator-authored v2 brief at `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` (901 lines; 2026-05-08) is the PRIMARY substrate for Theme 2. Phase 13 absorbs:

- **§1 Objective + introspection HARD constraint** — every detector + classifier + template-match output MUST emit operator-facing + auditable structural evidence. Black-box outputs (un-interpretable composite scores) are forbidden across the entire Theme 2 surface.
- **§3 Detection unit**: daily primary + weekly confirmation; variable-window candidate generator with anchor-point search; split/dividend-adjusted OHLCV.
- **§4.1 5-pattern primary buy-side set** — exactly the L2 V1 lock.
- **§4.2 Upstream context** — Stage 2 / trend template / RS rank / liquidity filter ARE pre-conditions, NOT patterns. Phase 4 evaluation pipeline already covers these; Theme 2 consumes them.
- **§5.1 Rule-based geometric detection PRIMARY** — illustrative VCP criteria precedent encoded verbatim into V1 detector spec (§5.2 below).
- **§5.2 Smoothing + extrema FOUNDATION** — zigzag adaptive percentage threshold is the de facto primitive for VCP-style patterns.
- **§5.3 Template matching STRONG SECONDARY** — DTW (constrained) OR shape-based distance for the secondary layer.
- **§6.1 Universe pipeline** — Phase 4 already covers; Theme 2 consumes Stage 2 + RS-rank-filtered candidate pool.
- **§6.4 Label schema** — `pattern_exemplars` library table mirrors this schema (with widening per §3 below for label_source + ai_labeler_version tracking).
- **§7 Normalization** — percentage returns OR z-score normalization for shape comparison; median/MAD over mean/std for robustness with gaps.
- **§8.2 AI-assisted labeling at scale** — DEV-TIME ONLY (per L1); Claude Code subagent dispatch consumes candidate window + emits silver label per §6.4 shape.
- **§9.2 Evidence to show reviewer** — 8-item checklist becomes the T2.SB6 closed-loop surface contract.
- **§9.3 6 reviewer decision types** — confirm / watch / reject / relabel / pattern-present-outside-window / multiple-overlapping-patterns. Encoded into T2.SB6 form surface.
- **§9.4 4 active-learning priorities** — borderline geometric scores + rule/template disagreement + underrepresented regimes + failed-rule near-misses. Encoded into T2.SB6 prioritization helper.
- **§10 Phased roadmap** — Phases 0+1+2+3+4 absorb into Phase 13 V1; Phase 5 (drift monitoring) splits to Phase 13.5; Phases 6+7+8 banked indefinitely or to Phase 14.
- **§13 Evaluation metrics** — detection metrics (precision/recall/calibration/top-K) + closed-loop outcome metrics (score-conditioned hit rate / R-multiple) + drift metrics (logging-side baseline only V1).
- **§14 Drift detection** — LOGGING SIDE absorbed in Theme 2 sub-bundles (feature distributions captured per detector run); monitoring/dashboard side SPLIT to Phase 13.5.
- **§16 ML re-ranker decision** — DEFERRED indefinitely per L4.

### §2.2 What Phase 13 ADDS beyond v2 brief

The v2 brief is pattern-detection-focused. Phase 13 adds:

- **Theme 1** — chart rendering deepening (NOT in v2 brief; Phase 13-specific).
- **Theme 3** — auto-fill across entries/exits/reviews (NOT in v2 brief; absorbs original Phase 12.5 #2 fill auto-population scope per L10).
- **Theme 4** — operator-elicited usability triage list + Q4 close-tracking flag (NOT in v2 brief; Phase 13-specific).
- **T1.SB0 prerequisite** — wire OhlcvCache into `_step_charts` (releases Phase 11 Sub-bundle C R1 M#5 V1 deferral; operator-added 2026-05-18; mid-flight scope-brainstorm amendment).

### §2.3 Where v2 brief and dispatch brief / scope-brainstorm DIVERGE — operator-locked §1 wins

Per dispatch brief §8: "If v2 brief and §1 disagree on any architectural decision, operator-locked §1 wins (operator scope-conversation 2026-05-17 supersedes v2 brief authoring 2026-05-08)."

Two specific divergences surface at brainstorm time:

1. **v2 brief §10 Phase 8 sell-side detector** vs **§1 L3 BANKED to Phase 14**. Operator-locked §1 wins — Phase 13 designs ZERO sell-side patterns.
2. **v2 brief §10 Phase 6 ML re-ranker (gated)** vs **§1 L4 DEFERRED indefinitely**. Operator-locked §1 wins — Phase 13 designs ZERO ML re-ranker.

### §2.4 What's OUT of Phase 13 scope per dispatch brief §1.6 (reaffirmed verbatim)

- Sell-side detector module → Phase 14 (v2 brief §10 Phase 8).
- ML re-ranker → indefinitely deferred per v2 brief §16.6 + 7 gates G1-G7.
- Drift detection monitoring/dashboard side → Phase 13.5 (v2 brief §14 4 surfaces).
- Matrix Profile-based exemplar retrieval at scale → Phase 14+ (v2 brief §5.8 + §10 Phase 7).
- Shapelet-based detection → Phase 14+ (v2 brief §5.9).
- Phase 12.5 #1/#2/#3 dispatches — already SHIPPED 2026-05-18 pre-Phase-13.
- Intraday / live-trading integration → Phase 14+ candidate.
- Tax-lot accounting → Phase 14+ candidate.
- Multi-cohort architectural deepening → Phase 14+ candidate.
- Branch A research-branch activation → Phase 0 study harness + first promotion package; deferred per operator 100% operational decision.
- Harmonic + candlestick + intraday + image CV + sequence transformer patterns → permanently out of scope per v2 brief §4.4 + §5.6 + §5.7.

---

## §3 Schema delta — v19 → v20 single migration sketch

This section enumerates schema deltas Phase 13 introduces. Full DDL is writing-plans territory; this is column-list + CHECK semantics + FK target shape only.

### §3.0 Shared detector-pattern enum LOCK (closes Codex R3 M#1)

To avoid cross-table reference rot after the R2 three-column refactor on `pattern_exemplars`, the project defines ONE canonical 5-value detector-pattern enum named **`DETECTOR_PATTERN_CLASSES`** that is referenced verbatim by every column carrying a detector-class semantic:

```text
DETECTOR_PATTERN_CLASSES = ('vcp', 'flat_base', 'cup_with_handle', 'high_tight_flag', 'double_bottom_w')
```

Tables / columns referencing this enum:
- `pattern_exemplars.proposed_pattern_class` (NOT NULL)
- `pattern_exemplars.final_pattern_class` (NULL except for `final_decision='relabeled'`)
- `pattern_evaluations.pattern_class` (NOT NULL)
- `chart_renders.pattern_class` (NULL except for `surface='theme2_annotated'`)

v21+ widening (Phase 14 sell-side detectors): the LOCK enumerates the V1 set; sell-side patterns added at Phase 14 migration. Schema-CHECK + Python-constant + dataclass-validator paired discipline applies per Phase 12 C.A T-A.2 LOCK — every CHECK widening of `DETECTOR_PATTERN_CLASSES` must touch ALL referencing columns + the Python-side constant simultaneously.

### §3.1 New table — `pattern_exemplars` (Theme 2)

Library of curated + AI-labeled + closed-loop-reviewed + organic-trade-history + synthetic + perturbation pattern instances (per Codex R5 m#2 — updated intro to include the 7 label_source categories explicitly per §3.1 enum). Anchors v2 brief §6.4 label schema. ~17-20 columns expected (incremented post-R2 + R4 + R5 schema additions: proposed_pattern_class / final_decision / final_pattern_class / labeler_evidence_json / parent_exemplar_id).

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `ticker` | TEXT NOT NULL | |
| `timeframe` | TEXT NOT NULL | CHECK in (`daily`, `weekly`) |
| `start_date` | TEXT NOT NULL | ISO date; window left edge |
| `end_date` | TEXT NOT NULL | ISO date; window right edge |
| `proposed_pattern_class` | TEXT NOT NULL | CHECK enum: `DETECTOR_PATTERN_CLASSES` (per §3.0 LOCK). **THE DETECTOR CLASS BEING EVALUATED** for this exemplar — required on every row regardless of label_source. The labeling pipeline per §5.9 invokes the labeler per (window, pattern_class) so a row legitimately carries the class under test even when the operator/labeler ultimately rejects it (closes Codex R3 M#3 — NO sentinel value pollution). |
| `final_decision` | TEXT NOT NULL | CHECK enum: `confirmed` / `watch` / `rejected` / `relabeled` / `generated` (source-neutral 5-value enum; closes Codex R3 M#2 + R3 m#2 source-leakage in decision names). Semantic: `confirmed` = operator/curator agreed with proposed_pattern_class; `watch` = pattern valid but not yet tradeable; `rejected` = operator decided this is NOT the proposed_pattern_class; `relabeled` = operator decided this is a DIFFERENT class (final_pattern_class populated); `generated` = synthetic/perturbation row (no operator decision; row was machine-generated). The valid `(label_source, final_decision)` matrix is schema-defended in the cross-column CHECK below. |
| `final_pattern_class` | TEXT NULL | CHECK enum: `DETECTOR_PATTERN_CLASSES` (per §3.0 LOCK); NULL when `final_decision IN ('confirmed', 'watch', 'rejected', 'generated')` (proposed_pattern_class is the relevant class for all non-relabel decisions); populated with the relabeled class when `final_decision='relabeled'`. Cross-column CHECK: `(final_decision = 'relabeled' AND final_pattern_class IS NOT NULL AND final_pattern_class != proposed_pattern_class) OR (final_decision != 'relabeled' AND final_pattern_class IS NULL)` schema-defended. |
| `label_source` | TEXT NOT NULL | CHECK enum: `curated_gold` / `claude_silver` / `codex_silver` / `closed_loop_review` / `organic_trade_history` / `synthetic` / `perturbation` (per v2 brief §8 5-source taxonomy + NEW `closed_loop_review` per Codex R4 M#1 — exemplars emitted from the T2.SB6 closed-loop review surface where operator reviewed a detector candidate but no trade was opened; `organic_trade_history` is reserved for exemplars where an ACTUAL trade was opened on the candidate; 7 values total). Rejection of an exemplar proposal is encoded via `final_decision='rejected'` (source-neutral name); `label_source` itself remains the SOURCE of the exemplar's origin, NOT the decision verb. |
| `ai_labeler_version` | TEXT NULL | dispatch SHA for Claude Code subagent / Codex; `NULL` for gold/organic/synthetic |
| `gold_validated_at` | TEXT NULL | ISO timestamp when operator promoted silver → gold |
| `codex_reviewed` | INTEGER NOT NULL DEFAULT 0 | boolean — did Codex 2nd reviewer fire (per L9 SELECTIVE policy) |
| `codex_agreement` | INTEGER NULL | boolean — Codex agreed with Claude silver label (`NULL` if `codex_reviewed=0`) |
| `geometric_score_json` | TEXT NULL | per-rule pass/fail breakdown (v2 brief §9.2 evidence-to-show-reviewer). **NULLABLE per Codex R4 M#2**: rule-tier evaluation requires T2.SB3+/SB4 detectors; pre-backfill rows persist with `geometric_score_json=NULL`. Cross-column CHECK invariant (closes Codex R5 M#1 — relaxed to allow `curated_gold` with NULL `geometric_score_json` when `labeler_evidence_json IS NOT NULL`, supporting T2.SB1 operator-promotion-pre-detector-backfill): `(geometric_score_json IS NULL AND (label_source IN ('claude_silver', 'codex_silver') OR (label_source = 'curated_gold' AND labeler_evidence_json IS NOT NULL))) OR (geometric_score_json IS NOT NULL AND label_source IN ('curated_gold', 'closed_loop_review', 'organic_trade_history', 'synthetic', 'perturbation'))`. The T2.SB3+/SB4 backfill task recomputes `geometric_score_json` against ALL rows that have NULL but should have it (silver-tier rows + curated_gold-with-labeler_evidence rows promoted at T2.SB1). |
| `labeler_evidence_json` | TEXT NULL | NEW per Codex R4 M#2 + revised post-Codex R6 M#1 — the Claude/Codex subagent's structural-evidence narrative output (distinct from rule-tier `geometric_score_json`). Populated when `label_source IN ('claude_silver', 'codex_silver')` AND ALSO preserved when those rows are operator-promoted to `label_source='curated_gold'` at T2.SB1 pre-detector-backfill (closes Codex R6 M#1 — preserves the silver-tier audit trail through gold-promotion). NULL for other label_sources (`closed_loop_review` / `organic_trade_history` / `synthetic` / `perturbation` — those derive evidence from rule-tier `geometric_score_json` at insert time). Schema-defended via the geometric_score_json cross-column CHECK at invariant #4 below. |
| `structural_evidence_json` | TEXT NOT NULL | per-detector structured fields (contraction depths for VCP, pivot price, etc.) |
| `quality_grade` | INTEGER NULL | 1-5 scale per v2 brief §6.4 self-drift detection field |
| `notes` | TEXT NULL | free-text operator notes |
| `parent_exemplar_id` | INTEGER NULL | FK to `pattern_exemplars(id)` `ON DELETE RESTRICT` (closes Codex R4 M#3 + R6 M#2 — RESTRICT not SET NULL because the §3.1 invariant #3 requires codex_silver rows to have non-NULL parent_exemplar_id; SET NULL on parent delete would violate the CHECK). Audit semantics align with append-only `reconciliation_corrections` precedent at Phase 12 C.A — pattern_exemplars rows are not deleted in normal operation; RESTRICT prevents accidental orphaning. Populated when `label_source='codex_silver'` AND the row was inserted because Codex disagreed with a parent `claude_silver` row; preserves the disagreement-chain linkage for cohort queries + template-match double-counting prevention. NULL for all other rows. |
| `created_at` | TEXT NOT NULL | server-stamped ISO timestamp |
| `created_by` | TEXT NOT NULL | CHECK in (`operator`, `claude_dispatch`, `codex_dispatch`, `synthetic_generator`); ASCII-only |

Indexes: `(proposed_pattern_class, label_source)` for cohort surfaces; `(ticker, start_date)` for ticker-history lookups.

**Cross-column CHECK invariants** (per Phase 12 C.A schema-defended cross-column CHECK precedent; rewritten post-Codex R3 M#2 source-neutral decision names):

1. **Relabel-vs-non-relabel coherence**: `(final_decision = 'relabeled' AND final_pattern_class IS NOT NULL AND final_pattern_class != proposed_pattern_class) OR (final_decision != 'relabeled' AND final_pattern_class IS NULL)`.

2. **Source-vs-decision matrix** (closes Codex R3 M#2 — now allows ANY non-curated source to carry decision verbs including `organic_trade_history` operator-rejected rows):

| `label_source` | Allowed `final_decision` values |
|---|---|
| `curated_gold` | `confirmed` (curator-curated implies confirmed by default; no rejection semantic on this source) |
| `claude_silver` | `confirmed` / `watch` / `rejected` / `relabeled` (operator decisions on AI-proposed exemplars) |
| `codex_silver` | `confirmed` / `watch` / `rejected` / `relabeled` (same as claude_silver) |
| `closed_loop_review` | `confirmed` / `watch` / `rejected` / `relabeled` (operator decisions in T2.SB6 closed-loop surface where NO trade was opened on the candidate; closes Codex R4 M#1) |
| `organic_trade_history` | `confirmed` / `watch` / `rejected` / `relabeled` (operator decisions PLUS trade-opened semantics — the operator actually traded the candidate; subset of closed_loop_review semantically but distinguished for cohort-query clarity) |
| `synthetic` | `generated` only (machine-generated; no operator decision applicable) |
| `perturbation` | `generated` only (same as synthetic) |

Encoded as: `(label_source = 'curated_gold' AND final_decision = 'confirmed') OR (label_source IN ('claude_silver', 'codex_silver', 'closed_loop_review', 'organic_trade_history') AND final_decision IN ('confirmed', 'watch', 'rejected', 'relabeled')) OR (label_source IN ('synthetic', 'perturbation') AND final_decision = 'generated')`.

3. **`parent_exemplar_id` linkage invariant** (closes Codex R5 M#2): `(label_source = 'codex_silver' AND parent_exemplar_id IS NOT NULL) OR (label_source != 'codex_silver' AND parent_exemplar_id IS NULL)`. Codex silver rows are V1-only emitted as disagreement-chain children of Claude silver parents per §5.9 step 4; standalone Codex labeling (Codex as primary labeler, not 2nd-reviewer) is OUT-OF-SCOPE V1 per L9. V2 candidate: relax to allow standalone Codex labeling. FK on `parent_exemplar_id` uses `ON DELETE RESTRICT` (per Codex R6 M#2 — SET NULL would violate this CHECK).

4. **`geometric_score_json` nullability CHECK** (closes Codex R6 m#2 — promoted from column-note to numbered invariant for implementation visibility): `(geometric_score_json IS NULL AND (label_source IN ('claude_silver', 'codex_silver') OR (label_source = 'curated_gold' AND labeler_evidence_json IS NOT NULL))) OR (geometric_score_json IS NOT NULL AND label_source IN ('curated_gold', 'closed_loop_review', 'organic_trade_history', 'synthetic', 'perturbation'))`. Silver-tier AI labels may have NULL `geometric_score_json` pre-backfill; curated_gold-promoted-from-silver rows may have NULL when `labeler_evidence_json IS NOT NULL` (T2.SB1 pre-detector-backfill state); all other label_sources require rule-tier evidence at insert.

5. **`labeler_evidence_json` source coherence**: `(labeler_evidence_json IS NOT NULL AND label_source IN ('claude_silver', 'codex_silver', 'curated_gold')) OR (labeler_evidence_json IS NULL AND label_source IN ('closed_loop_review', 'organic_trade_history', 'synthetic', 'perturbation'))` — closes Codex R6 M#1; preserves silver-tier audit trail through gold-promotion.

Schema-defended; mirror Python-side validator at landing per Phase 12 C.A schema-CHECK + Python-constant + dataclass-validator paired discipline.

**Semantic split (closes Codex R2 M#3 + M#4 + R3 M#1 + M#2)**: `pattern_exemplars` uses `proposed_pattern_class` + `final_decision` + `final_pattern_class` (the THREE-COLUMN labeling shape) — NOT a single `pattern_class` enum with a `none` sentinel value. `pattern_evaluations` + `chart_renders` retain a clean `pattern_class` enum (5 detector classes only; no `none`) because they emit detector-grain verdicts (the pattern being evaluated is always one of the 5; whether the verdict is "confirmed" or "low geometric score" is encoded in the geometric_score numeric, NOT a label-style enum). The proposed-vs-final labeling semantic is exclusively a `pattern_exemplars` concern. All four detector-class columns reference `DETECTOR_PATTERN_CLASSES` per §3.0 LOCK (closes Codex R3 M#1).

### §3.2 New table — `chart_renders` (Theme 1 cache; full sketch — closes Codex R1 M#2 §3 omission)

Per §4.4 LOCK (Theme 1 cache architecture). Inserted here in §3 schema delta to close R1 M#2 omission. Detail discussion remains at §4.4; this section enumerates the schema shape canonically.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `ticker` | TEXT NOT NULL | |
| `surface` | TEXT NOT NULL | CHECK enum: `watchlist_row` / `hyprec_detail` / `position_detail` / `market_weather` / `theme2_annotated` |
| `pipeline_run_id` | INTEGER NULL | FK to `pipeline_runs(id)` `ON DELETE CASCADE`; `NULL` for non-run-bound surfaces (`position_detail` rendered on-demand after a fill) |
| `pattern_class` | TEXT NULL | CHECK enum: `DETECTOR_PATTERN_CLASSES` (per §3.0 LOCK); populated ONLY for `surface='theme2_annotated'` (NULL for all other surfaces by design) |
| `chart_svg_bytes` | BLOB NOT NULL | inline SVG bytes |
| `source_data_hash` | TEXT NOT NULL | SHA256 of input OHLCV slice + pattern_evaluation row (if theme2_annotated) — staleness invalidation key |
| `rendered_at` | TEXT NOT NULL | server-stamped ISO timestamp |
| `data_asof_date` | TEXT NOT NULL | session date of input OHLCV (last completed session); per session-anchor LOCK at §4.4 |

**Indexes (uniqueness LOCK — closes Codex R1 M#3 SQLite NULL-distinct semantics defect)**: Per SQLite NULL-distinct semantics, a unique index over columns including NULL allows duplicate rows where the NULL fields participate. Use **partial unique indexes per surface class** to enforce one-row-per-cache-key:

- `CREATE UNIQUE INDEX idx_chart_renders_run_bound ON chart_renders(ticker, surface, pipeline_run_id) WHERE pipeline_run_id IS NOT NULL AND surface != 'theme2_annotated'`.
- `CREATE UNIQUE INDEX idx_chart_renders_position_detail ON chart_renders(ticker, surface) WHERE pipeline_run_id IS NULL AND surface = 'position_detail'`.
- `CREATE UNIQUE INDEX idx_chart_renders_theme2_annotated ON chart_renders(ticker, surface, pipeline_run_id, pattern_class) WHERE surface = 'theme2_annotated' AND pipeline_run_id IS NOT NULL` (closes Codex R2 M#5 — partial-index predicate now ALSO requires `pipeline_run_id IS NOT NULL`; combined with the CHECK below ensures duplicate NULL-pipeline_run_id `theme2_annotated` rows cannot exist).

These three partial indexes collectively enforce one cache row per legitimate cache key per surface class without colliding on NULL semantics. Cross-column CHECK enforces: `(surface = 'theme2_annotated' AND pattern_class IS NOT NULL AND pipeline_run_id IS NOT NULL) OR (surface != 'theme2_annotated' AND pattern_class IS NULL)` schema-defended (closes Codex R2 M#5 — CHECK now ALSO requires `pipeline_run_id IS NOT NULL` for the `theme2_annotated` surface; rejects rows that would slip past the partial-index predicate).

**Landing**: in v20 migration alongside `pattern_exemplars` + `pattern_evaluations` (§3.4 LOCK).

### §3.3 New table — `pattern_evaluations` (Theme 2 detector run output cache)

Per-`(pipeline_run_id, ticker, pattern_class)` detector verdict with full structural evidence. Bound to `pipeline_runs.id` (per `pipeline_pattern_classifications` shape precedent at migration 0009). ~14-16 columns expected:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `pipeline_run_id` | INTEGER NOT NULL | FK to `pipeline_runs(id)` |
| `ticker` | TEXT NOT NULL | |
| `pattern_class` | TEXT NOT NULL | CHECK enum: `DETECTOR_PATTERN_CLASSES` (per §3.0 LOCK) |
| `detector_version` | TEXT NOT NULL | rule-set version that fired (e.g., `vcp-v1.0`) |
| `geometric_score` | REAL NOT NULL | 0..1 composite rule pass rate |
| `geometric_score_json` | TEXT NOT NULL | per-rule breakdown |
| `template_match_score` | REAL NULL | 0..1 if template-matching layer ran; `NULL` if foundation-only sub-bundle |
| `template_match_nearest_exemplar_ids_json` | TEXT NULL | JSON array of top-3 nearest `pattern_exemplars.id` |
| `composite_score` | REAL NOT NULL | weighted geometric + template per §5.8 |
| `structural_evidence_json` | TEXT NOT NULL | dataclass-shape evidence per detector (see §10 walkthroughs) |
| `feature_distribution_log_json` | TEXT NOT NULL | LOGGING SIDE drift baseline (per v2 brief §14 + L5) — captures input feature values for Phase 13.5 baseline material |
| `window_start_date` | TEXT NOT NULL | anchor-point search left edge per v2 brief §3 |
| `window_end_date` | TEXT NOT NULL | anchor-point search right edge |
| `created_at` | TEXT NOT NULL | server-stamped |

Unique index `(pipeline_run_id, ticker, pattern_class)` — one verdict per pattern per ticker per run.

### §3.4 Schema widening — existing tables

| Table | Change | Notes |
|---|---|---|
| `pipeline_pattern_classifications` | (a) widen `classification` CHECK enum to include 5 V1 patterns; OR (b) leave alone and route through new `pattern_evaluations` table | Operator-pre-writing-plans-decision at §9 OQ-3 |
| `fills` | NEW column `fill_origin TEXT NOT NULL DEFAULT 'operator_typed'` | CHECK enum: `operator_typed` / `schwab_auto` / `schwab_auto_then_operator_corrected` / `tos_import` / `imported_legacy`. Backfill: all existing rows set to `operator_typed` (faithful to journal-typed-from-memory pre-Phase-13 state). |
| `fills` | NEW columns `schwab_source_value_json TEXT NULL` + `operator_corrected_value_json TEXT NULL` + `auto_fill_audit_at TEXT NULL` | Theme 3 audit columns — when auto-fill was used, original Schwab-source value preserved; operator-correction-on-top preserved; timestamp of auto-fill capture |
| `review_log` | NEW column `auto_populated_field_keys_json TEXT NULL` | Theme 3 review auto-fill audit — which fields were auto-populated at form-render time (vs operator-typed). `NULL` for pre-Phase-13 rows. |
| `schwab_api_calls.surface` | widen CHECK enum to include `trade_entry` and `trade_exit` | Theme 3 entry/exit auto-fill emits new audit rows with these surfaces |
| `candidates` OR new column on a Theme-4 close-tracking table | Q4 close-tracking flag schema — see §7.2 below | Operator-pre-writing-plans-decision at §10 D-Q4.1 |

### §3.5 Migration mechanics LOCK

- **Migration file**: `0020_phase13_charts_patterns_autofill_usability.sql` (single file per L6 single-migration LOCK).
- **Backup-gate**: `pre_version == 19` strict equality form (per CLAUDE.md gotcha "Migration runner backup-gate equality form: strict equality, NOT `<=`").
- **Schema-CHECK + Python-constant + dataclass-validator paired discipline**: every new CHECK enum MUST land in the SAME task as its Python-side mirror constants + dataclass `__post_init__` validators (per CLAUDE.md gotcha lesson from Phase 12 C.A T-A.2). Per Codex R3 M#5 audit + R5 m#1 count correction, the v20 atomic-landing roster is: **`DETECTOR_PATTERN_CLASSES`** (5 detector classes; per §3.0; referenced by `pattern_exemplars.proposed_pattern_class` + `pattern_exemplars.final_pattern_class` + `pattern_evaluations.pattern_class` + `chart_renders.pattern_class`); **`label_source`** enum (7 values per §3.1 — `curated_gold` / `claude_silver` / `codex_silver` / `closed_loop_review` / `organic_trade_history` / `synthetic` / `perturbation`); **`final_decision`** enum (5 values per §3.1 source-neutral); the FIVE numbered cross-column CHECK invariants on `pattern_exemplars` (per §3.1 invariants list: #1 relabel-vs-non-relabel coherence; #2 source-vs-decision matrix; #3 `parent_exemplar_id` linkage per Codex R5 M#2; #4 `geometric_score_json` nullability per Codex R6 m#2; #5 `labeler_evidence_json` source coherence per Codex R6 M#1); **`fill_origin`** enum (5 values per §3.4); widened **`schwab_api_calls.surface`** enum (adds `trade_entry` + `trade_exit`); **`chart_renders.surface`** enum (5 values per §3.2); the cross-column CHECK invariants on `chart_renders` (per §3.2); **Q4 enum** for `watchlist_close_track_flag_events.event_type` + `watchlist_close_track_flag_events.surface` + `watchlist_close_track_flags.cleared_reason` (per §7.2).
- **No `INSERT OR REPLACE`** on `pattern_exemplars` or `pattern_evaluations` — both tables have audit-trail intent; use SELECT-then-UPDATE-or-INSERT pattern per CLAUDE.md gotcha.
- **Foreign keys** (revised post-Codex R6 m#1 — `pattern_exemplars` HAS one self-FK now): `pattern_evaluations.pipeline_run_id` → `pipeline_runs(id)` `ON DELETE CASCADE` (one verdict ties to one run); `pattern_exemplars.parent_exemplar_id` → `pattern_exemplars(id)` `ON DELETE RESTRICT` (per Codex R4 M#3 + R6 M#2 — Codex disagreement-chain audit linkage; SET NULL would violate codex_silver invariant); `chart_renders.pipeline_run_id` → `pipeline_runs(id)` `ON DELETE CASCADE` when non-NULL; `watchlist_close_track_flag_events.flag_id` → `watchlist_close_track_flags(id)` `ON DELETE CASCADE`.

### §3.6 v21+ candidates flagged per theme

| Theme | v21+ candidate | Rationale |
|---|---|---|
| Theme 2 | Sell-side patterns added to `pattern_class` CHECK enum | Phase 14 |
| Theme 2 | `pattern_exemplars` widened with `embedding_json` for ML re-ranker | Phase 6 gated per v2 brief §16 (deferred) |
| Theme 3 | `review_log.fields_auto_populated_count INTEGER` + `auto_fill_disagreement_count INTEGER` aggregate columns | V2 — derived from `auto_populated_field_keys_json` query-time; promote to first-class column when query frequency justifies |
| Phase 13.5 | `feature_drift_baseline` table reading from `pattern_evaluations.feature_distribution_log_json` | Phase 13.5 monitoring side |

(Codex R1 m#2 fix: removed stale `watchlist_close_track_flags v21+ candidate` entry — D-Q4.1 LOCK confirms Q4 schema folds into v20 with active-flag partial unique index per Codex R1 M#9 resolution.)

---

## §4 Theme 1 — Chart rendering deepening

Audience: operator daily decision-making across watchlist + hyp-rec + active position + dashboard surfaces. Production state per dispatch brief §1.2: "very basic" coverage; pattern recognition is essentially manual; no annotated charts for hyp-recs.

### §4.1 T1.SB0 — OhlcvCache → `_step_charts` wiring (prerequisite Sub-bundle)

**Scope**: closes the Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral. Operator-added 2026-05-18 as a Phase 13 prerequisite (scope-brainstorm §0.5.2). Dispatches FIRST in Phase 13 sequence.

**Architectural framing**: OhlcvCache is constructed with Schwab→yfinance fallback ladder hooks but NOT yet consumed by `_step_charts` (per `swing/pipeline/runner.py:620-639` legacy `fetcher.get(ticker, lookback_days=180, as_of_date=None)` → `swing/pipeline/ohlcv.py:fetch_daily_bars` → `swing/data/ohlcv_archive.py:read_or_fetch_archive`). The legacy path still touches yfinance for daily-bar chart generation. Phase 11 Sub-bundle C R1 M#5 deferred the wiring because the shape semantics differ (capitalized columns + DatetimeIndex from `OhlcvCache.to_dataframe()` vs legacy fetcher's archive-managed shape) and weekly-refresh + `archive_history_days` semantics needed alignment to ladder window semantics.

**T1.SB0 closes the deferral via 3-prerequisite refactor**:
1. **Align `fetcher.get`'s weekly-refresh + `archive_history_days` semantics to ladder window semantics**. Concretely: replace the bare `fetcher.get(ticker, lookback_days=180, as_of_date=None)` call at runner.py:620-639 with `ohlcv_cache.get_or_fetch(ticker, window_days=180)` (exact method name TBD at writing-plans). Pre-empt the legacy fetcher's archive-managed weekly-refresh discipline by passing through to `ohlcv_archive.py:read_or_fetch_archive` at the cache layer.
2. **Shape reconciliation**: chart renderers (matplotlib SVG inline per Phase 10 §A.10 LOCK avoiding mathtext gotcha) accept the `to_dataframe()` shape (capitalized cols + DatetimeIndex). Discriminating test: assert chart bytes match a known-good fixture rendered from both paths.
3. **Per-cache locking + lifecycle semantics for OhlcvCache**: today single-threaded per request. T1.SB0 verifies the cache survives `_step_charts`'s multi-ticker loop without contention. Add a per-cache `RLock` if needed (per cache-poisoning gotcha "Cache + executor race: workers must not write to shared state when the request thread cancels on deadline miss").

**T1.SB0 ALSO** captures the daily-bar data substrate for downstream Theme 2 pattern detectors — every Theme 2 detector consumes daily + weekly bars; routing through OhlcvCache means yfinance is V2-fallback only. Per L5 + L6, ALSO: T1.SB0 plants the LOGGING SIDE substrate of feature distributions captured per detector run by guaranteeing the cache shape is deterministic.

**Schema impact**: ZERO. T1.SB0 is consumer-side only. Migration v20 lands at T2.SB1 with `pattern_exemplars` table.

**Test projection**: +20-40 fast tests (cache integration + chart-renderer shape parity + discriminating per-cache-locking test).

**Operator-witnessed gate**: S1 fast pytest + ruff; S2 `python -m swing.cli pipeline run` against operator's production produces a complete briefing.md with `_step_charts` succeeding through OhlcvCache (cassette-mode acceptable for CI; live-mode under operator-paired session).

### §4.2 Chart surface inventory

| Surface | Audience | Rendering scope | Cache architecture | Performance budget |
|---|---|---|---|---|
| **Watchlist row chart** | Operator daily watchlist scan | Daily bars × 90 sessions; MA50/MA150/MA200 lines; volume bars in lower pane | `chart_renders` cache table (see §4.4); regenerated when `pipeline_runs.id` changes | Inline thumbnail (200x100 SVG); rendered eagerly per pipeline run; cached |
| **Hyp-rec detail chart** | Operator hyp-rec review | Daily bars × 180 sessions; MA50/MA150/MA200; volume; pattern boundaries from Theme 2 output (T2.SB6 closed-loop); pivot point; trigger + stop lines | `chart_renders` cache table; regenerated per-pipeline-run | Full-size (800x500 SVG); rendered eagerly per pipeline run |
| **Active position detail chart** | Operator active position monitoring | Daily bars from entry-30 sessions → present; entry/exit fill markers; current stop line; trail-MA line if active; MFE/MAE shading | `chart_renders` cache table; regenerated per-pipeline-run + on fill events | Full-size (800x500 SVG); rendered eagerly |
| **Market weather mini-chart** | Operator dashboard top | S&P 500 (`^GSPC`) daily bars × 90 sessions; MA50/MA200; volume bars; current trend-template state badge (Stage 1/2/3/4) | `chart_renders` cache table; regenerated per-pipeline-run | Inline mini (400x150 SVG) |
| **Theme 2 annotated detector chart** | Operator hyp-rec review for confirmed patterns | Same as hyp-rec detail PLUS: pattern boundaries (per detector `structural_evidence_json`); contraction markers for VCP; top-3 nearest historical-base overlay (small inline thumbnails) | `chart_renders` cache table keyed by `(ticker, pattern_class, pipeline_run_id)` | Full-size (800x600 SVG with overlay panel) |

### §4.3 Rendering technology LOCK — matplotlib SVG inline

**LOCK per Phase 10 §A.10 inheritance** (Phase 10 Sub-bundle E `/metrics/process-grade-trend` SVG inline + matplotlib mathtext gotcha CLAUDE.md entry; inline SVG avoids mathtext fires on `$`/`^`/`_`/`\\` entirely):

- **All Theme 1 charts render as inline SVG embedded in HTMX partial responses**. NO PNG. NO matplotlib mathtext usage.
- **No `$` / `^` / `_` / unbalanced `\\` in any axis label / title / annotation text** — same canonical pattern as Phase 10 Sub-bundle E §A.10 LOCK and the matplotlib mathtext CLAUDE.md gotcha ("omit the metacharacter from the title format entirely").
- **ASCII-only on all rendered text** — Windows cp1252 stdout safety (per Phase 12 C.D gate-fix #1 + #3 gotchas; though SVG bytes don't flow through stdout, defense-in-depth + cross-surface code reuse).
- **`fig.suptitle(..., parse_math=False)` as defense-in-depth** if any chart title rendering surface emerges where avoiding metacharacters is infeasible.

**V2 candidate**: upgrade to interactive client-side JS chart library (e.g., Lightweight Charts / Plotly / TradingView Lightweight Charts). Per §9 OQ-1, V1 LOCK is SVG inline; V2 is interactive client-side. Rationale: V1 SVG-inline gives operator the immediate value (deeper chart surfaces) without HTMX-JS-coupling complexity Phase 13's other themes don't tax.

### §4.4 Cache architecture LOCK — `chart_renders` cache table

**Schema sketch is the canonical §3.2 LOCK** (per Codex R2 M#1 — replaced the prior duplicate competing-text formulation here with a cross-reference + uniqueness invariant restatement to keep §3 and §4 consistent):

- See §3.2 for the canonical column list + types + CHECK semantics.
- See §3.2 for the 3-partial-unique-index discipline (`idx_chart_renders_run_bound` / `idx_chart_renders_position_detail` / `idx_chart_renders_theme2_annotated`) that closes the SQLite NULL-distinct semantics defect.
- See §3.2 for the cross-column CHECK invariant ensuring `(surface = 'theme2_annotated' AND pattern_class IS NOT NULL AND pipeline_run_id IS NOT NULL) OR (surface != 'theme2_annotated' AND pattern_class IS NULL)`.

**Staleness rules**:
- Charts bound to `pipeline_run_id` are regenerated only when a new run completes (`pipeline_runs.state='complete'`).
- `position_detail` charts (NULL `pipeline_run_id`) are regenerated on `fills` change events OR when `data_asof_date < last_completed_session(now())`.
- Operator-facing manual refresh: web button on each surface that bypasses the cache for one render cycle (no schema change; just a route param).

**Session-anchor read/write mismatch discipline LOCK** (per dispatch brief §5 watch item 15 + CLAUDE.md gotcha family): both writes AND reads of `data_asof_date` MUST use the SAME session-anchor function. WRITES at chart-render time stamp `data_asof_date = last_completed_session(now())` (backward-looking; the session whose bars are the most recent COMPLETED bars in the OHLCV substrate). READS at staleness-check time MUST also use `last_completed_session(now())` (backward-looking) — NOT `action_session_for_run(now())` (forward-looking; which is the NEXT session being prepped + would diverge on weekends/holidays/evenings/pre-market). Discriminating round-trip test pattern (per Phase 8 `cfacbc5` precedent in CLAUDE.md gotcha "Session-anchor read/write mismatch silently invisibles UI display"): render a chart at a known session anchor, then immediately query the cache via the staleness predicate, assert HIT (no false-MISS due to read/write anchor mismatch).

**Why a separate table, not OhlcvCache extension**: chart rendering is a write-through cache backed by deterministic pure-function rendering over OHLCV data; OhlcvCache is the input substrate. Coupling them risks the cache+executor race gotcha (Phase 11 lesson: workers must not write to shared state when request thread cancels on deadline miss). Charts have N orders of magnitude more "rows" (one per ticker × surface × run) than OhlcvCache's input substrate. See §9 OQ-2 for the alternatives (file-based cache, OhlcvCache extension).

**Performance + quota budget**:
- Watchlist row chart: rendered eagerly per pipeline-run for top 20 tickers (operator-paced); ~20 × 200x100 SVG ≈ 400KB/run. Cached.
- Hyp-rec detail chart: rendered eagerly for hyp-rec list (typically 5-10 tickers); ~10 × 800x500 SVG ≈ 1MB/run.
- Active position detail: rendered eagerly for open trades (typically 3-8); ~6 × 800x500 SVG ≈ 600KB/run.
- Market weather mini-chart: 1 chart per run; ~50KB/run.
- Theme2 annotated: rendered for confirmed pattern candidates (typically 0-3 per run); ~3 × 800x600 SVG ≈ 400KB/run.

Total per-run write to `chart_renders`: ~2.5MB. Annual storage ~1GB (250 sessions × 2.5MB × ~1.6 retention factor). Acceptable for SQLite BLOB cache.

### §4.5 Market weather mini-chart placement on dashboard

- **Surface placement**: TOP of `/dashboard` (above existing Phase 10 metrics tile navigator AND above the Phase 12 reconciliation banner). Operator daily-glance shows weather context BEFORE drilling into specifics.
- **Trigger**: regenerated per-pipeline-run; cached in `chart_renders` table; rendered inline as part of `DashboardVM` (Phase 10 base-layout VM retrofit pattern; new `dashboard_weather_chart_svg_bytes: bytes | None` field; populated `is None` if no recent pipeline run).
- **Content**: S&P 500 daily bars × 90 sessions + MA50 + MA200 + volume + current trend-template state badge (Stage 2 / 3 / 4 / undefined) + Phase 10 §A.10 inline-SVG pattern.
- **Update cadence**: per-pipeline-run; on-demand refresh button surfaces a manual regeneration (route handler `POST /dashboard/weather-chart/refresh`).

### §4.6 Theme 2 annotated chart deliverable (closed-loop coupling at T2.SB6)

The Theme 2 annotated chart at T2.SB6 IS the v2 brief §9.2 evidence-to-show-reviewer deliverable AND the Theme 1 deepest-coverage chart. Annotations rendered per the Theme 2 detector's `structural_evidence_json`:

- **VCP**: contraction sequence markers (one per contraction; depth % labels); pivot price horizontal line; volume profile lower panel; trend-template state badge.
- **Flat base**: top-of-range + bottom-of-range horizontal lines; ATR shading; duration label.
- **Cup-with-handle**: cup left edge + bottom + right edge + handle entry + handle bottom; depth ratio label.
- **High-tight flag**: prior advance pole markers; consolidation range box; days-tight count.
- **Double-bottom W**: trough-1 + center-peak + trough-2 markers; optional undercut indicator on trough-2 vs trough-1.

PLUS: top-3 nearest historical-base overlay (per template-matching layer T2.SB5 output) rendered as small inline thumbnails (200x100 SVG) in a right-side panel of the main chart.

Theme 1 + Theme 2 share T2.SB6 implementation: the annotated chart is rendered by a Theme 1 SVG-inline renderer that CONSUMES Theme 2's `pattern_evaluations.structural_evidence_json` payload. Per dispatch brief §5 watch item 9, both themes' bindings reconcile here.

### §4.7 V2 candidates (banked for Phase 14+)

- **Interactive client-side JS chart library** (TradingView Lightweight Charts / Plotly / Bokeh) for zoom + pan + drill-down. V1 SVG-inline keeps complexity low + avoids HTMX-JS-coupling.
- **Per-row sparklines** in the `/trades/` list view + `/watchlist/` list view (inline 60x20 SVG).
- **Multi-timeframe chart synchronization** — toggle daily ↔ weekly bars on the same chart surface.
- **Annotation editor** — operator-drawn boundaries override Theme 2 detector boundaries (closed-loop active learning per v2 brief §9.4).

---

## §5 Theme 2 — Pattern recognition deepening (HEADLINE)

Anchored on `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` v2 brief (901 lines; AI-ingestion-ready). V1 pattern set: 5 buy-side patterns (VCP + flat base + cup-with-handle + high-tight-flag + double-bottom-W) per L2.

This is the largest section; ~650 lines covering foundation primitives + 5 detector designs + template matching + composite scoring + dev-time labeling infrastructure + closed-loop surface + drift logging baseline.

### §5.1 Foundation primitives (T2.SB2)

Per v2 brief §5.2. T2.SB2 ships pure-logic primitives consumed by T2.SB3 (VCP + flat base + cup-with-handle) and T2.SB4 (high-tight-flag + double-bottom-W) detectors. ZERO DB writes; pure functions.

**Module location**: NEW `swing/patterns/foundation.py` (parallel to `swing/recommendations/` + `swing/metrics/` per Phase 10 module-pattern precedent).

#### §5.1.1 Smoothing

V2 brief §5.2 enumerates 7 smoothing methods. **V1 LOCK**: **Exponential Moving Average (EMA)** for the primary smoothing layer + **kernel regression** for centered (non-lag-introducing) smoothing on stable historical analysis. Rationale:

- EMA is computationally trivial, deterministic, well-understood by operator (Minervini Trend Template uses MA50/MA150/MA200 SMAs; EMA generalizes naturally).
- Kernel regression is the Lo-Mamaysky-Wang reference standard (per `reference_external_studies.md` memory + v2 brief §18.1) but doesn't extend to recent-bar data — V1 reserves it for historical-exemplar curation and template-matching reference computation.
- Wavelet denoising + spline smoothing + piecewise linear approximation deferred to V2 (per §5.2 weaknesses: "single setting will miss patterns at other scales") — V1 picks one primary + accepts the temporal-scale limitation.

**API sketch**:
```text
swing/patterns/foundation.py
  smooth_ema(prices: np.ndarray, window: int) -> np.ndarray
  smooth_kernel_regression(prices: np.ndarray, bandwidth: float) -> np.ndarray  # historical only, no recent-bar
```

#### §5.1.2 Extrema extraction

V2 brief §5.2 enumerates 3 methods. **V1 LOCK**: **Zigzag with adaptive percentage threshold** as the de facto primitive. PIPs + local-maxima-after-smoothing deferred to V2.

**Adaptive threshold** — for VCP-style patterns where contraction depths decrease monotonically, the zigzag threshold must adapt per swing. V1 algorithm:
- Start with threshold % = `max(3.0, ATR_5d_pct × 1.5)` (heuristic — wider than ATR to avoid noise).
- After each swing, narrow the threshold by `0.75 ×` for the next swing — this catches monotonically-decreasing contractions (VCP-specific).
- For flat-base / cup-with-handle detectors, use static threshold % = 3.0 (no monotonic narrowing).

**API sketch**:
```text
swing/patterns/foundation.py
  extract_zigzag_swings(bars: DataFrame, initial_threshold_pct: float, monotonic_narrow: bool = False) -> list[Swing]
  
@dataclass(frozen=True)
class Swing:
    start_date: date
    end_date: date
    start_price: float
    end_price: float
    direction: Literal['up', 'down']
    depth_pct: float  # abs((end-start)/start)
    duration_days: int
```

#### §5.1.3 Variable-window candidate generator

Per v2 brief §3 LOCK: variable-window candidate generator with anchor-point search; VCP-style patterns have variable durations (3-12 weeks per v2 brief §5.1 illustrative criterion #5).

**API sketch**:
```text
swing/patterns/foundation.py
  generate_candidate_windows(bars: DataFrame, anchor_search_method: Literal['zigzag_pivot', 'ma_crossover', 'high_low_breakout']) -> list[CandidateWindow]
  
@dataclass(frozen=True)
class CandidateWindow:
    ticker: str
    timeframe: Literal['daily', 'weekly']
    start_date: date
    end_date: date
    anchor_date: date  # the candidate base start
    anchor_reason: str  # e.g., 'zigzag_pivot:swing_3_down', for evidence trail
```

**Per-pipeline-run scope**: candidate-window generation runs ONCE per pipeline run AFTER trend-template filter + RS-rank filter (i.e., AFTER `_step_evaluate`). Output candidate set is consumed by every detector in T2.SB3+T2.SB4.

**T2.SB1 cross-bundle bootstrap window LOCK (closes Codex R1 M#4 T2.SB1↔T2.SB2 dependency inversion)**: T2.SB1 labeling pipeline (per §5.9 below) needs SOME candidate-window input for the AI-assisted labeling pass to operate against. The full variable-window candidate generator ships at T2.SB2 — but T2.SB1 ships a MINIMUM-VIABLE candidate-window seed mechanism via operator-supplied date ranges: operator selects historical (ticker, start_date, end_date) tuples directly (via a NEW `swing patterns label-exemplars --ticker <T> --start <D> --end <D>` CLI subcommand OR similar) + AI-labeling pipeline operates on those operator-curated windows. The full algorithmic candidate-window generator at T2.SB2 is then a REFINEMENT that closes the loop (auto-generate windows + label them); T2.SB1 bootstrap accepts the manual-window path. This preserves the operator-locked dispatch sequence (T2.SB1 → T2.SB2) at scope-brainstorm §0.5.2 without requiring out-of-order dispatch.

#### §5.1.4 Volume profile primitives

Used by VCP volume-decline-through-contractions criterion (v2 brief §5.1 #4) and high-tight-flag tight-consolidation-volume-confirmation criterion.

**API sketch**:
```text
swing/patterns/foundation.py
  volume_trend_through_swings(bars: DataFrame, swings: list[Swing]) -> list[VolumeSegment]
  breakout_volume_ratio(bars: DataFrame, breakout_date: date, baseline_days: int = 50) -> float  # ratio vs 50d avg
```

#### §5.1.5 Trend template state surface (consumed; not new)

Phase 4 already ships Stage 2 trend template evaluation. T2.SB2 exposes a thin convenience wrapper:
```text
swing/patterns/foundation.py
  current_stage(ticker: str, asof_date: date) -> Literal['stage_1', 'stage_2', 'stage_3', 'stage_4', 'undefined']
```
Sources from `evaluation_results` or equivalent shipped Phase 4 surface — exact callsite verified at writing-plans.

### §5.2 VCP detector (T2.SB3)

**Pattern definition**: Volatility Contraction Pattern. Minervini's signature setup. Per v2 brief §4.1 high tractability + §5.1 illustrative criteria.

**Rule-based geometric criteria** (v2 brief §5.1 verbatim + writing-plans-time thresholds + tolerance bands):

| # | Criterion | LOCK shape | Tolerance band |
|---|---|---|---|
| 1 | In Stage 2 uptrend per trend template | `current_stage(ticker, asof_date) == 'stage_2'` | NONE — hard gate |
| 2 | Prior uptrend leg of >= 30% over >= 8 weeks | `prior_uptrend_pct >= 0.30 AND prior_uptrend_weeks >= 8` | ±2% tolerance on uptrend pct |
| 3 | Sequence of N >= 2 contractions where each depth % decreases monotonically | `len(contractions) >= 2 AND all(c[i].depth_pct < c[i-1].depth_pct for i in range(1, len(contractions)))` | ±0.5% tolerance on monotonicity (per v2 brief §5.1 weakness mitigation) |
| 4 | Typical depths: T1 ~15-30%, T2 ~10-15%, T3 ~5-10% | Per-contraction bounds; T1 in [10%, 35%]; T2 in [5%, 20%]; T3 in [3%, 15%] (loosened from typical to acceptance range) | NONE — these are bounds, not point thresholds |
| 5 | Volume declines through the contraction sequence | `volume_segments[i].avg_volume < volume_segments[i-1].avg_volume for i in range(1, len(volume_segments))` | ±10% tolerance per pair |
| 6 | Duration: 3-12 weeks total base | `(base_end - base_start).days in [21, 84]` | NONE — duration is the bound |
| 7 | Pivot formed near top of base | `pivot_price / base_top_price in [0.99, 1.01]` (within 1% of base top) | ±0.5% tolerance |
| 8 | Optional: breakout above pivot on volume >= 40% above 50d avg | `breakout_volume_ratio >= 1.40` | NONE — optional criterion |

**Composite scoring per §5.8**: weighted sum of criteria pass/fail with #1 + #6 as hard gates (no partial credit; pattern rejected if either fails).

**Structural evidence shape** (frozen dataclass; serialized to `pattern_evaluations.structural_evidence_json`):
```text
@dataclass(frozen=True)
class VCPEvidence:
    stage: Literal['stage_2', ...]
    prior_uptrend_pct: float
    prior_uptrend_weeks: int
    base_start_date: date
    base_end_date: date
    contractions: tuple[Contraction, ...]
    pivot_price: float
    base_top_price: float
    pivot_within_top_pct: float
    volume_decline_passes: bool
    breakout_observed: bool  # optional criterion
    breakout_volume_ratio: float | None  # populated if breakout_observed
    criteria_pass: dict[str, bool]  # per-criterion granular
    geometric_score: float  # 0..1
    
@dataclass(frozen=True)
class Contraction:
    start_date: date
    end_date: date
    peak_price: float
    trough_price: float
    depth_pct: float
    duration_days: int
    avg_volume: float
```

**Worked example** (§10.1 below): operator's CVGI pre-2026-05-15 base candidate — anchor 2026-04-15; base 3 contractions; depths 22%/12%/7%; volume decline passes; pivot 5.30 within 0.8% of base top 5.34 → geometric score 1.0.

### §5.3 Flat base detector (T2.SB3)

**Pattern definition**: O'Neil/CANSLIM consolidation base. Bounded range with low slope and tight ATR for >= 5-7 weeks.

**Rule-based geometric criteria**:

| # | Criterion | LOCK shape | Tolerance band |
|---|---|---|---|
| 1 | In Stage 2 uptrend | `current_stage == 'stage_2'` | NONE — hard gate |
| 2 | Prior uptrend leg (similar to VCP) | `prior_uptrend_pct >= 0.20 AND prior_uptrend_weeks >= 5` | ±2% |
| 3 | Bounded range: top - bottom in [3%, 12%] | `(range_top - range_bottom) / range_bottom in [0.03, 0.12]` | ±0.5% |
| 4 | Low slope: linear regression slope of mid-range / range_bottom <= 0.005/week | `regression_slope_pct_per_week <= 0.005` | NONE |
| 5 | Tight ATR: avg(ATR_5d) / mid_range <= 0.025 | `mean_atr_pct <= 0.025` | NONE |
| 6 | Duration >= 5-7 weeks | `(base_end - base_start).days >= 35` | NONE — duration is the bound |
| 7 | Pivot at top of range | `pivot_price / range_top in [0.99, 1.01]` | ±0.5% |

**Structural evidence shape**: `FlatBaseEvidence` with `range_top` / `range_bottom` / `regression_slope_pct_per_week` / `mean_atr_pct` / `duration_days` / `pivot_price` / `geometric_score`.

**Worked example** (§10.2): operator's historical YOU consolidation base — anchor 2026-04-01; range $10.50-$11.80 (12% width); slope +0.003/week; ATR 2.1%; duration 6.5 weeks; pivot $11.78 → geometric score 1.0.

### §5.4 Cup-with-handle detector (T2.SB3)

**Pattern definition**: O'Neil/CANSLIM cup with shallow pullback handle.

**Rule-based geometric criteria**:

| # | Criterion | LOCK shape | Tolerance |
|---|---|---|---|
| 1 | Stage 2 uptrend | `current_stage == 'stage_2'` | NONE |
| 2 | Cup left edge to bottom: smooth decline of >= 12% over >= 4 weeks; <= 35% | `cup_depth_pct in [0.12, 0.35] AND cup_left_to_bottom_days >= 28` | ±0.5% |
| 3 | Cup bottom to right edge: rounded recovery (NOT sharp V); cup right edge >= 95% of cup left edge | `cup_right_edge_price >= 0.95 × cup_left_edge_price` | ±1% |
| 4 | Cup duration: 6-26 weeks (per O'Neil bounds) | `cup_duration_days in [42, 182]` | NONE |
| 5 | Handle: shallow pullback from cup right edge of <= 15% AND >= 5d duration | `handle_depth_pct <= 0.15 AND handle_duration_days >= 5` | ±1% on depth |
| 6 | Handle low above cup midpoint | `handle_low_price > (cup_left_edge_price + cup_bottom_price) / 2` | NONE |
| 7 | Pivot at cup right edge (above the resistance level) | `pivot_price / cup_right_edge_price in [0.99, 1.01]` | ±0.5% |
| 8 | Volume drying up during handle | `handle_avg_volume / cup_avg_volume <= 0.85` | ±5% |

**Rounded-vs-V cup test**: cup-bottom curvature evaluated by checking that bars near cup midpoint are NOT the absolute low (V-shapes have midpoint = bottom; round cups have a stretched-out trough). Specifically:
- Compute the 5-day window centered on the cup midpoint (`cup_midpoint_date = cup_start_date + (cup_bottom_date - cup_start_date)/2`).
- If `min(window_lows) < cup_bottom_price × 1.02` (window contains bars within 2% of the absolute low), cup is rounded.
- If `min(window_lows) > cup_bottom_price × 1.05`, cup is V-shaped → reject.

**Structural evidence shape**: `CupWithHandleEvidence` with `cup_left_edge_*` / `cup_bottom_*` / `cup_right_edge_*` / `handle_*` / `pivot_*` / `is_rounded` / `geometric_score`.

**Worked example** (§10.3): hypothetical $XYZ candidate — cup from $20 → $14 → $19.50 over 90 days (rounded; volume dries 30% lower at bottom); handle pulls back to $18 over 8 days; pivot $19.55; volume during handle 80% of cup avg → geometric score 1.0.

### §5.5 High-tight-flag detector (T2.SB4)

**Pattern definition**: Minervini/O'Neil HTF; defined prior advance + tight consolidation.

**Rule-based geometric criteria**:

| # | Criterion | LOCK shape | Tolerance |
|---|---|---|---|
| 1 | Stage 2 uptrend | `current_stage == 'stage_2'` | NONE |
| 2 | Prior advance ("pole"): >= 90% gain over 4-8 weeks | `pole_pct >= 0.90 AND pole_duration_days in [28, 56]` | ±5% on pct |
| 3 | Consolidation: tight; <= 25% pullback from pole top over 3-5 weeks | `consolidation_pullback_pct <= 0.25 AND consolidation_duration_days in [21, 35]` | ±2% |
| 4 | Consolidation range: <= 15% width (top to bottom) | `consolidation_width_pct <= 0.15` | NONE |
| 5 | Volume contracts during consolidation | `consolidation_avg_volume / pole_avg_volume <= 0.65` | ±10% |
| 6 | Pivot at consolidation top | `pivot_price / consolidation_top_price in [0.99, 1.01]` | ±0.5% |

**Structural evidence shape**: `HighTightFlagEvidence` with `pole_*` / `consolidation_*` / `pivot_*` / `geometric_score`.

**Worked example** (§10.4): hypothetical HTF candidate — $WXYZ advances 120% from $5 → $11 in 35 days; consolidates 18% pullback to $9, range $8.80-$10.40 (15% width) over 25 days; volume drops 40% during consolidation; pivot $10.40 → geometric score 1.0.

### §5.6 Double-bottom-W detector (T2.SB4)

**Pattern definition**: Both methodologies; two troughs with center peak, optional undercut.

**Rule-based geometric criteria**:

| # | Criterion | LOCK shape | Tolerance |
|---|---|---|---|
| 1 | Stage 2 uptrend OR coming OUT of Stage 4 toward 2 | `current_stage in ('stage_2',) OR (recent_stage == 'stage_4' AND current_stage in ('stage_2',))` | NONE |
| 2 | Trough 1: low point with >= 15% drawdown from prior peak | `trough_1_drawdown_pct >= 0.15` | ±1% |
| 3 | Center peak: recovery >= 50% retracement | `center_peak_retracement_pct >= 0.50` | ±2% |
| 4 | Trough 2: at approximately same level as trough 1 (±5%) OR undercut by <= 5% | `abs(trough_2 - trough_1) / trough_1 <= 0.05 OR (trough_2 < trough_1 AND (trough_1 - trough_2) / trough_1 <= 0.05)` | ±0.5% |
| 5 | Symmetric structure: trough_1 → center_peak duration in [5d, 35d]; center_peak → trough_2 duration in [5d, 35d] | `both durations in [5, 35]` | NONE |
| 6 | Pivot at center peak height | `pivot_price / center_peak_price in [0.99, 1.01]` | ±0.5% |
| 7 | Volume rises into trough_2 (optional; shakeout signal) | `trough_2_avg_volume / trough_1_avg_volume in [1.0, 2.0]` | OPTIONAL |
| 8 | Trough_2 undercut adds geometric_score bonus | `geometric_score += 0.10 if undercut else 0` | LOCK |

**Structural evidence shape**: `DoubleBottomWEvidence` with `trough_1_*` / `center_peak_*` / `trough_2_*` / `undercut` / `pivot_*` / `geometric_score`.

**Worked example** (§10.5): hypothetical DBW candidate — $UVWX trough_1 at $20 after 25% drawdown from $26.67 peak; center peak at $23 (60% retracement); trough_2 at $19 (5% undercut; bonus); pivot $23 → geometric score 1.10 (with undercut bonus).

### §5.7 Template matching layer (T2.SB5)

Per v2 brief §5.3 "Strong secondary."

**V1 LOCK at §9 OQ-4 recommendation**: **DTW with Sakoe-Chiba band** as the distance metric. Rationale:

- DTW with constrained warping handles VCP-style variable durations naturally (per v2 brief §5.3).
- Sakoe-Chiba band (typically window = 0.1 × series length) prevents over-warping (per v2 brief §5.3 caveat: "unconstrained DTW can over-warp, matching patterns that don't actually look alike").
- Shape-Based Distance (SBD) is an alternative; deferred to V2 per OQ-4.
- Feature-vector distance deferred to V2 ML re-ranker (which is itself deferred per L4).

**Two retrieval modes** (per v2 brief §5.3):
1. **Forward retrieval**: "Show me historical bases that look like this candidate."
2. **Reverse retrieval**: "Show me candidates that look like this confirmed historical base."

**API sketch**:
```text
swing/patterns/template_matching.py
  match_forward(candidate_window: CandidateWindow, exemplar_corpus: list[PatternExemplar], top_k: int = 3) -> list[TemplateMatchHit]
  match_reverse(exemplar: PatternExemplar, candidate_corpus: list[CandidateWindow], top_k: int = 10) -> list[TemplateMatchHit]
  
@dataclass(frozen=True)
class TemplateMatchHit:
    exemplar_id: int  # or candidate_id depending on direction
    distance: float  # DTW distance, lower is closer
    similarity_score: float  # normalized 0..1 (1=identical, 0=max distance)
```

**Normalization**: candidate windows + exemplar windows normalized via min-max scaling per v2 brief §7 (LOCK: min-max for V1; z-score is V2 option).

**Composition with rule-based detector** (per §5.8 composite scoring): rule-tier geometric score + template-match score → composite via weighted sum.

**Performance budget (revised post-Codex R1 M#10)**: DTW is O(n²) — for ~30-day daily candidate windows × ~30-day exemplar windows, ~900 cells per pair. The production-scale projection must use v2 brief §6.1 universe-pipeline output (200-500 names post-trend-template-filter) NOT my prior 50-name underestimate. **Realistic projection**: 250-name candidate universe × 5 patterns × ~50 exemplars per pattern (after per-pattern filtering — see pruning LOCK below) = 62,500 DTW pair-computations per run = ~60-100 seconds CPU time per pipeline run. Borderline for batch-mode EOD pipeline. **Pruning LOCK (BINDING for T2.SB5 writing-plans)**:

1. **Per-pattern exemplar filtering**: DTW comparisons are scoped to `same pattern_class` — VCP candidate compares ONLY against VCP exemplars, not against flat-base/CWH/HTF/DBW exemplars. Reduces comparisons by factor of 5.
2. **Geometric-score pre-gate**: DTW only fires for candidates with `geometric_score >= 0.4` (rule-tier minimum signal); ZERO-rule-confidence candidates skip the expensive DTW pass. Reduces active candidate pool 30-50%.
3. **Max windows per ticker**: at most 3 candidate windows per ticker per pattern per pipeline run (top-3 by zigzag-anchor strength). Prevents pathological tickers with many marginal anchors from blowing up the budget.
4. **Exemplar corpus subsampling**: when `pattern_exemplars` for a given pattern_class exceeds 100 rows, T2.SB5 subsamples 50 highest-quality_grade exemplars for DTW comparison. Full-corpus comparison is a writing-plans-decision V2 option.

**Benchmark gate at T2.SB5 dispatch**: writing-plans includes a `pytest-benchmark` discriminating test asserting that the full DTW pass completes within 120 seconds on operator's hardware (~3GHz CPU baseline). If the benchmark fails, T2.SB5 either tightens the pruning OR adopts SBD (per OQ-4 V2 fallback).

### §5.8 Composite scoring (T2.SB5)

Per v2 brief §17 item 7 + §13.1 calibration discipline.

**V1 formula LOCK**:
```text
composite_score = 0.60 × geometric_score + 0.40 × template_match_score
```

Where:
- `geometric_score` is the 0..1 weighted pass/fail of detector-specific rule criteria (see per-pattern §5.2-§5.6 above; bonuses like double-bottom-W undercut increment by 0.10 capping at 1.10 for evidence; composite formula caps at 1.0 via `min(1.0, ...)`).
- `template_match_score` is the max similarity over top-3 forward-retrieval matches (per §5.7 retrieval mode).
- For pattern classes where template_match_score is unavailable (first run; exemplar corpus empty), composite_score = geometric_score (LOCK).

**Why 60/40 weighting**: rule-tier is operator-interpretable + has strong methodology backing (Minervini/O'Neil); template-matching is a "looks like this" overlay. Weight balance leans toward interpretability per v2 brief §1 introspection HARD constraint.

**Calibration LOCK**: V1 composite_score is NOT a probability. It is a 0..1 evidence-strength signal for operator triage. Per v2 brief §13.1: any "confidence score" used to gate decisions must be calibrated (Brier score + isotonic regression); V1 does NOT calibrate — operator uses composite_score as a ranking signal, NOT a threshold. V2 calibration is gated on label-volume threshold (per v2 brief §16.5 G2 200 confirmed positives per pattern class) which is years away under organic-only labeling.

### §5.9 Dev-time labeling infrastructure (T2.SB1)

Per v2 brief §8.2 "AI-assisted labeling at scale." DEV-TIME ONLY per L1 (Claude API at pipeline run-time FORBIDDEN; subagent dispatch for labeling is allowed).

**T2.SB1 ships** + **operator paired mid-dispatch pause for exemplar bootstrap** + **operator signals resume** + **T2.SB2+ continues with detector builds consuming the corpus**. Pattern mirrors post-Phase-12 Sub-bundle 1 cassette session precedent (operator-paired execution; resumption pattern). Per §9 OQ-6.

**Pipeline**:
1. Operator selects historical universe (e.g., tickers × 2-year history) AND supplies **(ticker, start_date, end_date, pattern_class)** seed tuples for the labeling pass — per §5.1.3 T2.SB1 bootstrap window LOCK, T2.SB1 ships the manual-seed mechanism via the NEW `swing patterns label-exemplars` CLI subcommand. The labeler is invoked **PER (window, pattern_class)** (closes Codex R3 M#3 — no `no_pattern_detected` sentinel value; the row legitimately carries the class under test, whether confirmed or rejected). The CLI takes `--pattern-class <CLASS>` (one of `DETECTOR_PATTERN_CLASSES`) explicitly; operator can invoke multiple pattern classes per window if multi-pattern testing is desired.
2. For each operator-supplied (ticker, start_date, end_date, pattern_class) seed tuple, T2.SB1 dispatches a Claude Code subagent (`Agent` tool with custom subagent_type defined in the worktree) with:
   - The seed window OHLCV slice serialized as compact JSON.
   - The SPECIFIC pattern class being evaluated (one of 5; per the seed tuple).
   - The rule criteria + structural-evidence schema for THAT specific pattern.
   - Instructions to emit `{evaluation: 'confirmed' | 'watch' | 'rejected' | 'relabel:<other_class>', confidence: 'high' | 'medium' | 'low', structural_evidence_json}`.
3. Claude Code subagent returns silver label. Persisted to `pattern_exemplars` with:
   - `label_source='claude_silver'` + `ai_labeler_version=<dispatch_sha>`.
   - `proposed_pattern_class=<the seed tuple's class>` (legitimately reflects what was tested).
   - `final_decision` mapped from subagent's `evaluation` field: `confirmed`/`watch`/`rejected`/`relabeled`.
   - `final_pattern_class` populated only when `evaluation` was `relabel:<other_class>`.
   - `gold_validated_at=NULL` + `codex_reviewed=0`.
4. **Selective Codex 2nd reviewer** (per L9 + §9 OQ-5; rewritten post-Codex R4 M#3): T2.SB1 uses **ONLY random 15% sampling** (rule/silver-disagreement clause DEFERRED to T2.SB3+/SB4 per Codex R3 M#4). At T2.SB1 the Codex MCP fires on the random-sample subset only; updates the **SAME `pattern_exemplars` row** (NOT a separate row) with `codex_reviewed=1` + `codex_agreement=<bool>`. If Codex disagrees materially (different `final_decision` OR different `final_pattern_class`), a SECOND row is INSERTed with `label_source='codex_silver'` + `proposed_pattern_class` matching the original + Codex's `final_decision` + linkage via a NEW column `parent_exemplar_id INTEGER NULL REFERENCES pattern_exemplars(id)` on `pattern_exemplars` (closes Codex R4 M#3 — Codex disagreement rows link back to their Claude parent for cohort-query clarity + double-counting prevention in template matching). When `codex_agreement=true`, NO second row is created. The full SELECTIVE policy (random 15% + high-stakes individual labels) ACTIVATES at T2.SB3+/SB4 sub-bundles when detector geometric_score is available.
5. **Operator spot-check 10-20%**: operator reviews `claude_silver` rows + (a) promotes accurate `confirmed` rows to `label_source='curated_gold'` + `final_decision='confirmed'` + `gold_validated_at=<now>`; (b) flips wrong-class proposals to `final_decision='relabeled'` + `final_pattern_class=<corrected_class>`; (c) flips false-positive proposals to `final_decision='rejected'`; (d) flags watch-not-yet-tradeable as `final_decision='watch'`. Surfaced via a NEW `/patterns/exemplars` web surface OR CLI subcommand (per §9 OQ-6).
6. Operator signals resume; T2.SB2+ detector builds consume the resulting corpus.

**Codex SELECTIVE policy operationalization** (§9 OQ-5; phased per Codex R3 M#4):
- **At T2.SB1** (rule detectors not yet shipped): random 15% sample of `claude_silver` rows per pattern class. NO rule/silver disagreement clause (geometric_score is unavailable).
- **At T2.SB3+/SB4** (rule detectors shipped at T2.SB3 + T2.SB4): random 15% sample CONTINUES PLUS the high-stakes individual labels — Claude silver confidence == 'high' AND rule-tier `geometric_score < 0.5` (rule/silver disagreement A direction); OR Claude silver confidence == 'low' AND rule-tier `geometric_score >= 0.8` (rule/silver disagreement B direction). The full SELECTIVE policy ACTIVATES retroactively against the T2.SB1 corpus when T2.SB3+/SB4 evaluators have access to recompute `geometric_score` against the existing exemplars.

**Subagent + cassette infrastructure**:
- NEW Claude Code subagent type consumed via `Agent(subagent_type='pattern-labeler', ...)`. **Subagent definition location is operator-pre-writing-plans-decision** (banked as additional OQ; see §9 OQ-11 below): three candidate locations are (a) `.claude/agents/pattern-labeler.md` (project-local subagent per Claude Code conventions); (b) `agents/pattern-labeler.md` at repo root (if a project-wide agent collection emerges); (c) a NEW `swing-trading` plugin namespace under `.claude/plugins/cache/local/` mirroring the copowers plugin precedent. Brainstorm-recommendation: (a) `.claude/agents/pattern-labeler.md` — matches Claude Code's standard project-local subagent convention + avoids introducing a plugin scaffolding for one subagent.
- NEW `tests/integrations/cassettes/pattern_labeler/` for VCR-recorded subagent traffic. Per L9 + post-Phase-12 forward-binding lesson #2: `before_record_request` (URI/path sanitization) + `before_record_response` (body sanitization) filters BOTH installed.
- NEW `scripts/record_pattern_labeler_cassettes.py` standalone recording script per post-Phase-12 lesson #3 (standalone recording script OVER `@pytest.mark.vcr(record_mode='new_episodes')` when cassettes must exist before consumer test code).

**ASCII-only on labeler prompts + outputs** — Windows cp1252 stdout safety (operator may surface dispatch transcripts).

### §5.10 Closed-loop surface (T2.SB6)

Per v2 brief §9.2 evidence-to-show-reviewer + §9.3 reviewer decision types + §9.4 active learning prioritization.

**Surface scope**: NEW `/patterns/{candidate_id}/review` web route AND NEW `/metrics/pattern-outcomes` tile (per §9 OQ-10 LOCK). The `/metrics/pattern-outcomes` tile **composes with** (does NOT replace) Phase 10 metrics architecture: reuses `swing/metrics/` module pattern (parallel to `swing/metrics/cohort.py`); reuses Phase 10 Sub-bundle A `honesty.py` confidence-floor + Wilson-CI badge helpers; reuses Phase 10 Sub-bundle A `BaseLayoutVM` mixin so the new `PatternOutcomesVM` populates `unresolved_material_discrepancies_count` + `banner_resolve_link` automatically; reuses Phase 10 §A.18 discrepancies helper. Per dispatch brief §5 watch item 8: the surface is ADDITIVE on top of the shipped 8 Phase 10 metric tiles + 1 umbrella `/metrics` navigator, not a replacement.

**Page content** (8-item v2 brief §9.2 checklist verbatim):

1. **Proposed pattern class** — `pattern_evaluations.pattern_class` rendered as labeled tile (color-coded per pattern class).
2. **Geometric score breakdown by rule component** — `geometric_score_json` rendered as per-criterion pass/fail/marginal table.
3. **Top-3 nearest historical bases (template matches)** — `template_match_nearest_exemplar_ids_json` rendered as 3 thumbnails (Theme 1 annotated chart deliverable per §4.6).
4. **Trend-template status for the ticker** — `current_stage()` output rendered as badge.
5. **RS rank** — Phase 4 evaluation result rendered as numeric badge.
6. **Recent volume profile** — last 30 sessions volume sparkline + 50d avg comparison.
7. **Reason for any uncertainty in rule evaluation** — `structural_evidence_json.criteria_pass` per-criterion text with explanatory notes (per v2 brief §1 introspection HARD constraint).
8. **Outcome distribution from prior similar candidates** — "of the last N similar-score candidates, X% triggered, Y% reached 1R, Z% hit stop" — composes with Phase 10 metrics cohort architecture (NEW surface as a 9th `/metrics/...` tile per §9 OQ-10).

**Reviewer decision form** (per v2 brief §9.3 6-decision-type enum):
- `confirm` — pattern valid + tradeable now.
- `watch` — pattern valid + not yet tradeable (pre-breakout).
- `reject` — no valid pattern.
- `relabel` — pattern exists + proposed class is wrong (operator picks correct class via dropdown).
- `pattern_present_outside_window` — real pattern + system framed it wrong (operator notes correct window).
- `multiple_overlapping_patterns` — more than one valid pattern in window (operator notes additional patterns).

**Form action** (rewritten post-Codex R4 M#1 label_source semantic split): POST writes to `pattern_exemplars` with:

- `label_source='closed_loop_review'` if the operator reviewed the candidate but did NOT open a trade on it (closes Codex R4 M#1 — reserves `organic_trade_history` for trade-opened exemplars).
- `label_source='organic_trade_history'` if the operator's decision was `confirm` AND the operator then opened a trade on the candidate (the candidate-to-trade backlink at `trades.candidate_id` resolves to this row).
- `proposed_pattern_class=<the detector's class>` (per §3.0 LOCK).
- `final_decision` mapped from operator decision per source-neutral enum: `confirm` -> `confirmed`; `watch` -> `watch`; `reject` -> `rejected`; `relabel` -> `relabeled` + `final_pattern_class=<operator-corrected-class>`.
- `pattern_present_outside_window` and `multiple_overlapping_patterns` route through a separate window-shift / multi-exemplar emit per v2 brief §9.3.
- `gold_validated_at=<now>` for all branches except `rejected` which retains `gold_validated_at=NULL`.

All `(label_source, final_decision)` pairs above are valid per the §3.1 source-vs-decision matrix CHECK invariant.

**Active learning prioritization helper** (per v2 brief §9.4): NEW `/patterns/queue` route showing top-K candidates prioritized by:
1. Borderline geometric scores (`abs(geometric_score - 0.5) < 0.1`).
2. Rule/template disagreement (`abs(geometric_score - template_match_score) > 0.3`).
3. Underrepresented regimes (low historical exemplar count for current weather state).
4. Failed-rule near-misses (`geometric_score in [0.55, 0.70]`).

### §5.11 Drift logging baseline substrate (per L5; Phase 13 LOGGING side only)

Per L5 + v2 brief §14 4 surfaces. Phase 13 logs feature distributions per detector run; Phase 13.5 ships monitoring/dashboard side.

**Substrate**: `pattern_evaluations.feature_distribution_log_json` column (per §3.2 schema sketch).

**Per-detector-run, T2.SB3+T2.SB4 emit** to `feature_distribution_log_json`:
- Distribution moments (mean/median/std/min/max) of input feature values that fed the detector (e.g., for VCP: contraction depths array; volume ratios array; pivot proximity ratio).
- Universe size + Stage-2-pass-rate + RS-rank distribution at run time.
- Detector verdict counts per pattern class.

Phase 13.5 will compose this substrate into:
1. Feature drift surface — PSI / KL divergence vs trailing 1y baseline.
2. Pattern frequency drift surface — per pattern class, density vs trailing 90d baseline.
3. Outcome drift surface — hit rate + R-multiple per pattern class vs trailing baseline.
4. Self-drift surface — quarterly re-grading comparison.

**Phase 13.5 dispatch UNBLOCKED** when Phase 13 V1 has at least 1 month of `pattern_evaluations.feature_distribution_log_json` accumulation (per v2 brief §14 trailing-baseline-window discipline).

---

## §6 Theme 3 — Auto-fill deepening across entries / exits / reviews

Absorbs original Phase 12.5 #2 (fill auto-population at trade-entry) per L10. Three sub-bundles T3.SB1 + T3.SB2 + T3.SB3.

### §6.1 T3.SB1 — Entry auto-fill (concurrent with T2.SB1)

**Scope**: trade entry form pre-populates fields from Schwab Trader API at form-render time. Composes with post-Phase-12 Sub-bundle 1 mapper widening (execution-grain data via `SchwabExecutionLeg`).

**Architecture**:
- **Form-render-time fetch**: `GET /trades/entry/form` route handler calls Schwab Trader API `account_orders` + `account_details` for recent fills matching the entered ticker.
- **Schwab client construction discipline (BINDING per dispatch brief §5 watch item 10 + post-Phase-12 Sub-bundle 1 lesson)**: every Schwab API consumer surface in T3.SB1 MUST resolve credentials via `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` (the `allow_prompt=False` form prevents form-render-time stdin prompts that would block the HTTP handler) BEFORE invoking `construct_authenticated_client(client_id, client_secret, environment, tokens_db_path)` (the 4-arg signature shipped at post-Phase-12 Sub-bundle 1). `apply_overrides(cfg)` is called at handler entry to consume the cfg-cascade per Phase 12 Sub-bundle B discipline. Sandbox short-circuit + DEGRADED-state degraded path inherit per Phase 11 Sub-bundle D.
- **Field pre-population**:
  - `entry_date` — auto-populated from most recent BUY fill matching ticker (within 7-day lookback window per cfg).
  - `entry_price` — auto-populated from `_compute_execution_price(SchwabOrderResponse)` per post-Phase-12 Sub-bundle 1 mapper (single-leg → leg price; multi-leg → VWAP).
  - `initial_shares` — auto-populated from `_resolve_match_quantity(SchwabOrderResponse)` execution-grain quantity.
  - `fill_origin` — server-stamped to `schwab_auto` at form render; flips to `schwab_auto_then_operator_corrected` if operator edits a pre-populated field before submit.
- **Hidden audit anchors** (per CLAUDE.md gotcha "For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING at handler entry"):
  - `schwab_source_value_json` server-stamped to original auto-populated values; persisted regardless of operator edits.
  - `auto_fill_audit_at` server-stamped to ISO timestamp at form render.
- **Form input handling**: display-only `<span class="muted">` text for `fill_origin` + `auto_fill_audit_at`; operator-editable input fields for `entry_date`/`entry_price`/`initial_shares` with auto-populated values pre-filled.
- **Soft-warn confirm**: if operator edits a pre-populated field, soft-warn fragment renders with `form_values` dict round-tripping the hidden anchors (per CLAUDE.md gotcha "Form-render hidden anchors driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict").

**Empty-state handling**:
- If Schwab Trader API returns no matching fills: form renders with empty auto-fill fields + `fill_origin='operator_typed'` + advisory text "No matching Schwab fills found; please enter manually."
- If Schwab integration is DEGRADED (per Phase 11 Sub-bundle D banner predicate): form renders with empty auto-fill fields + `fill_origin='operator_typed'` + advisory banner "Schwab integration degraded; auto-fill unavailable."
- If `cfg.integrations.schwab.environment == 'sandbox'`: auto-fill SHORT-CIRCUITS (per Schwab sandbox-gating gotcha "domain rows ONLY when environment=='production'"); form renders with empty auto-fill fields.

**Audit-row emission**: each form-render fetch emits a `schwab_api_calls` row with `surface='trade_entry'` (CHECK enum widening v20).

### §6.2 T3.SB2 — Exit auto-fill

**Scope**: trade exit form (the existing `/trades/{id}/exit` route) pre-populates exit fill fields from Schwab Trader API at form-render time. Currently operator-types-from-memory (per dispatch brief §2.3).

**Architecture mirrors T3.SB1** (including the `resolve_credentials_env_or_prompt(allow_prompt=False)` + `construct_authenticated_client` 4-arg signature + `apply_overrides(cfg)` discipline at every entry point):
- `exit_date` auto-populated from most recent SELL fill matching ticker (within 7-day lookback window).
- `exit_price` auto-populated from execution-grain price via post-Phase-12 Sub-bundle 1 mapper.
- `closed_shares` auto-populated from execution-grain quantity.
- `fill_origin` server-stamped to `schwab_auto` / `schwab_auto_then_operator_corrected` / `operator_typed` per same rules as T3.SB1.
- Hidden audit anchors `schwab_source_value_json` + `auto_fill_audit_at` server-stamped.
- Audit-row `schwab_api_calls.surface='trade_exit'` (CHECK enum widening v20).

**Partial exits**: if Schwab returns multiple SELL fills since `entry_date` (partial exits over time), form lists each as a candidate; operator picks one OR enters consolidated value (per Phase 12 multi-leg `split_into_partials` auto-redirect precedent, but at FORM RENDER not POST-resolution).

**Dispatches after T2.SB3** (per scope-brainstorm §0.5.2 dispatch sequence) to avoid Schwab Trader API consumer merge conflicts with T3.SB1.

### §6.3 T3.SB3 — Review auto-fill (dispatches after T2.SB5)

**Scope**: trade review form (Phase 6 `/reviews/{id}/complete` route) pre-populates priors from previous reviews + MFE/MAE from candles.

**Auto-fill fields**:
1. **Priors from previous reviews** (same ticker; most recent N completed reviews):
   - `mistake_tags` candidates surfaced as suggestions (operator can confirm/edit/add).
   - `process_grade` baseline = mean of recent N grades for same ticker (operator can adjust).
   - `lesson_learned` candidates surfaced (LATEST N entries; operator can copy/edit/expand).
2. **MFE/MAE from candles** (Phase 8 daily_management_records + OhlcvCache):
   - `mfe_pct` computed from `max(daily highs since entry) / entry_price - 1` over open trade duration.
   - `mae_pct` computed from `min(daily lows since entry) / entry_price - 1`.
   - Source: `daily_management_records` if Phase 8 daily-management coverage exists; ELSE fallback to OhlcvCache daily-bar synthesis.
3. **`realized_R_if_plan_followed` recompute** at form render — Phase 7 derived metric refreshed against current state (operator's actual plan-following review may differ).

**Period reviews** (the higher-level cadence reviews):
- Per dispatch brief §2.3 "section text auto-fill from prior reviews."
- `previous_period_lessons_summary` — auto-extracted from review_log rows in prior period (week / month); surfaced as starter text in the section.
- `most_common_mistake_tags_this_period` — aggregate of mistake_tags across all reviews this period.
- `cohort_health_summary` — surfaces deltas vs prior period.

**Audit trail**:
- NEW `review_log.auto_populated_field_keys_json` column tracks which fields were auto-populated at form render (vs operator-typed).
- ZERO Schwab API calls (review auto-fill consumes OhlcvCache + Phase 8 daily_management_records + existing review_log; no broker-side data needed).

**Dispatches after T2.SB5** (per scope-brainstorm §0.5.2 dispatch sequence) to consume the OhlcvCache patterns + candidate-window primitives that T2.SB5 cements.

### §6.4 `fill_origin` enum widening + audit columns LOCK

**CHECK enum**: `operator_typed` / `schwab_auto` / `schwab_auto_then_operator_corrected` / `tos_import` / `imported_legacy`. Per §3.3.

**Backfill discipline** for v20 migration:
- All existing `fills` rows get `fill_origin='operator_typed'` (faithful to pre-Phase-13 journal-typed-from-memory state).
- The 6 existing Schwab-auto-correct rows (CVGI fill 9 + LION fill 15 chain heads + others from Phase 12 C.D gate + post-Phase-12) get `fill_origin='operator_typed'` initially (the journal was operator-typed; Schwab corrections happened AFTER the fact and Phase 12 doesn't speak to `fill_origin` semantics). V2 candidate: backfill historical `reconciliation_corrections` rows into `fills.schwab_source_value_json` + `fills.fill_origin='schwab_auto_then_operator_corrected'` (chain-head correction); operator-pre-writing-plans-decision at §9 OQ-7.

**Schema-CHECK + Python-constant + dataclass-validator paired discipline** (per Phase 12 C.A T-A.2 gotcha): `_FILL_ORIGIN_VALUES` Python constant + `Fill.__post_init__` validator + schema CHECK in the SAME task at v20 landing.

**Discriminating test**: plant 5 fills (one of each `fill_origin` value) + assert journey through `apply_overrides(cfg)` + Schwab fetch + auto-fill form + operator edit + persist correctly stamps `fill_origin` at each step.

### §6.5 Cross-bundle dependencies

- **T3.SB1 dispatches CONCURRENT with T2.SB1** (independent codebase touch).
- **T3.SB2 dispatches AFTER T2.SB3** (Schwab Trader API consumer merge-conflict avoidance).
- **T3.SB3 dispatches AFTER T2.SB5** (consumes OhlcvCache patterns + candidate-window primitives).

### §6.6 Forward-binding lessons referenced

- Phase 12 Sub-bundle B `apply_overrides(cfg)` discipline at every new Schwab entry point.
- Phase 11 Sub-bundle D `surface='X'` CHECK enum widening pattern (`trade_entry` + `trade_exit` v20 additions).
- Phase 8 server-stamping discipline for hidden audit fields.
- Phase 5 HTMX failure surfaces (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted) — every new form-driven route inherits.
- Phase 9 Sub-bundle D form-render hidden-anchor round-trip-through-soft-warn-confirm-form-values discipline.
- Phase 11 Sub-bundle C `synthetic-fixture-vs-production-emitter shape drift` family — Theme 3 auto-fill tests against real production-shape responses, not synthetic fixtures.

---

## §7 Theme 4 — Usability triage + Q4 close-tracking flag

Theme 4 is the Phase 13 closer Sub-bundle (T4.SB; one Sub-bundle implementing two scope items together).

### §7.1 Operator-elicited usability list (verbatim capture)

Per L11 + dispatch brief §2.4: "Operator drafts the unreported-usability-issues list at brainstorm time as one of the brainstorm spec inputs."

**At dispatch time (2026-05-17 + Q4 fold-in 2026-05-18), the operator has NOT YET provided a usability list to this brainstorm-implementer.** Per dispatch brief §8: "Operator-elicited usability list (Theme 4) MUST be captured verbatim from operator. If operator did not provide the list at dispatch time, prompt at brainstorm session start. Do NOT enumerate usability issues from your own analysis — operator owns the list."

This brainstorm-implementer is dispatched in work-without-stopping mode + cannot prompt operator interactively. The usability list is therefore **DEFERRED to orchestrator-pre-writing-plans operator-paired elicitation** (per Phase 12.5 #1/#2/#3 brainstorm precedent for §15.B-style operator-decision-pending items). The brainstorm spec §7 captures:

1. The Q4 close-tracking-flag scope as the seed item (per §7.2 below; absorbed into T4.SB).
2. An elicitation template (per §7.3 below) that the orchestrator drives at the operator-pre-writing-plans review.
3. A sizing framework (per §7.4 below) that the orchestrator applies at elicitation time.

**T4.SB scope LOCK at brainstorm time (closes Codex R1 M#1 scope-weakening defect)**: T4.SB ships **Q4 close-tracking flag (per §7.2 D-Q4.1..D-Q4.7) as the MINIMUM BINDING scope**. The operator usability list elicitation produces a SPEC §7 AMENDMENT before writing-plans dispatch; the writing-plans dispatch consumes BOTH the Q4 scope (already brainstorm-locked) AND the elicited usability list. If the operator usability list is empty (operator confirms NO additional items), T4.SB ships Q4-only without scope loss. If the operator usability list adds N items, T4.SB scope expands by those N items + writing-plans phase decomposes the extended scope into per-task acceptance criteria. **L11 is preserved**: the operator-elicited list IS captured into the spec BEFORE writing-plans dispatch (just not at this implementer-dispatch time); the dispatch-brief §8 fallback ("operator did not provide the list at dispatch time, prompt at brainstorm session start") is operationalized as orchestrator-pre-writing-plans elicitation per the project's established §15.B-style operator-decision-pending pattern.

**Orchestrator-pre-writing-plans action item**: prompt operator to draft the usability list verbatim; this spec §7 is amended in-place pre-writing-plans dispatch with the verbatim list.

### §7.2 Q4 close-tracking flag (operator-elicited; PTEN canonical use case)

**Operator use case (verbatim from dispatch brief §2.4 + phase3e-todo Q4 entry)**:

> Operator looking at top watchlist symbol for 5/19 process run; PTEN closed past its pivot value -> high-probability of opening a position when markets open. NOT flagged by hyp-rec (the existing algorithm doesn't elect it as a recommendation) but visually looks like a good candidate. Operator wants a visual mechanism to flag such symbols for personal close-tracking, persisting across pipeline runs even if the watchlist algorithm decides the symbol no longer meets criteria (false-negative guard).

**Two sub-use-cases**:
1. **At-breakout** (PTEN today): symbol just crossed its pivot/trigger; immediate-action candidate; flag retains visual prominence on watchlist.
2. **Approaching-breakout**: symbol trending in correct direction but not yet at pivot; flag breaks it out from the rest of the watchlist visually + ensures it's not dropped from the surface if the watchlist algorithm next-run decides criteria not met.

**7 architectural sub-decisions** (per dispatch brief §2.4 amendment; orchestrator-pre-writing-plans triage):

| ID | Decision area | Brainstorm-default recommendation | Rationale |
|---|---|---|---|
| **D-Q4.1** | Schema: NEW column on `candidates` OR NEW table `watchlist_close_track_flags` | **NEW table** `watchlist_close_track_flags` (Option B) | (1) Ticker is the primary key; not bound to `candidates.id` (which rotates per evaluation run + has lifecycle bound to pipeline runs). Flag must persist ACROSS pipeline runs (false-negative guard). NEW table with `ticker TEXT NOT NULL UNIQUE` + lifecycle metadata. (2) `candidates` rotation churn means an additive column there gets effectively-reset every pipeline run — wrong semantic. (3) Operator-visible CRUD surface (set/unset) is much simpler with own table. |
| **D-Q4.2** | Setting / unsetting UI: web vs CLI vs both | **Web BOTH operator-toggle + CLI for scripting** | (1) Web UI: small toggle button on watchlist row (top-right of row; star icon or pin icon). Click sets flag; click again clears. (2) CLI: `swing watchlist flag <ticker> --close-track` + `swing watchlist unflag <ticker>` for scripting / operator-paired sessions. Both surfaces persist to same table. |
| **D-Q4.3** | Persistence semantics: per-session / per-run / persistent-until-cleared / auto-expire / auto-clear-on-position-open | **Persistent until operator clears OR auto-clear on operator opens a position in that ticker** (with transactional discipline locked per below) | (1) Persistent matches operator intent ("persisting across pipeline runs even if the watchlist algorithm decides the symbol no longer meets criteria"). (2) Auto-clear on position open: when `trades` row inserts with the flagged ticker, flag is auto-cleared (close-tracking served its purpose). **Auto-clear transactional discipline LOCK** (per Phase 8 + 12 C.C lesson #2 + #3 inheritance): the auto-clear fires inside the SAME transaction that INSERTs the `trades` row; service-function pattern is reject-caller-held-tx at the outer + `BEGIN IMMEDIATE` discipline uniform-regardless-of-environment + sandbox short-circuit lives in the inner function (NOT outer) + audit-row append-only (per `reconciliation_corrections` Phase 12 C.A precedent — `watchlist_close_track_flag_events` gets a new `event_type='clear'` row; the parent `watchlist_close_track_flags` row gets `cleared_at` + `cleared_reason='auto_cleared_on_position_open'` UPDATE not DELETE). (3) NO auto-expire by date — operator decides cleanup cadence. (4) V2 candidate: optional auto-expire after N days configurable per-flag. |
| **D-Q4.4** | Visual rendering: badge / separate section / row background | **Badge on watchlist row** (small `[FLAGGED]` ASCII marker OR pin emoji `[*]` ASCII swap for cp1252 safety) **+ rendering priority within existing watchlist sort** | (1) ASCII-only per Windows cp1252 stdout safety (CLAUDE.md gotcha). (2) Badge inline on the row maintains current watchlist layout. (3) Sort priority: flagged rows appear FIRST in the watchlist surface regardless of pipeline algorithm's sort order — this is the false-negative-guard mechanism (flagged rows can't be dropped from view). (4) V2 candidate: separate "Actively tracked" section above main watchlist. |
| **D-Q4.5** | Filtering interaction: false-negative guard mechanic | **Flagged tickers UNION'D with pipeline algorithm output on the watchlist surface** | (1) `watchlist` view-model query is `UNION(pipeline_algorithm_output, flagged_tickers_not_in_algorithm_output)`. (2) Sort order: flagged-first, then pipeline algorithm order. (3) Visual differentiation: flagged-but-not-in-algorithm gets a sub-badge "(operator-flagged; algo dropped)" so operator knows the algorithm + operator disagree. |
| **D-Q4.6** | Relation to hyp-rec: do flagged symbols get hyp-rec treatment? | **NO — watchlist-surface-only** | (1) Hyp-rec is the algorithm's high-conviction surface; operator-flagged is a SEPARATE surface ("operator-tracked"). (2) Conflating them dilutes hyp-rec's semantic. (3) V2 candidate: "elevated to hyp-rec" toggle if operator wants algorithm-flag fusion. |
| **D-Q4.7** | Audit trail: per-flag-event row | **YES — per-flag-event row with timestamp + ticker + reason text (optional) + flag_source ('web' / 'cli')** | (1) Operator review history matters; flag events deserve audit per Phase 8 + 9 + 12 audit-trail discipline. (2) Reason text is OPTIONAL (operator may flag without explanation; especially the PTEN at-breakout case). (3) `flag_source` distinguishes surface attribution per Phase 12.5 #2 `resolved_by IN ('operator', 'operator_web')` precedent — values `web` / `cli`. (4) Audit table separate from primary table OR same table with append-only INSERT discipline (no UPDATE-in-place; per `reconciliation_corrections` precedent at Phase 12 C.A). |

**Schema sketch for D-Q4.1 Option B (NEW table)**:

| Table | Column | Type | Notes |
|---|---|---|---|
| `watchlist_close_track_flags` | `id` | INTEGER PK | |
| | `ticker` | TEXT NOT NULL | uniqueness via PARTIAL UNIQUE INDEX (active-flag only); see "Indexes" row below — closes Codex R1 M#9 re-flag-same-ticker defect |
| | `flagged_at` | TEXT NOT NULL | server-stamped ISO timestamp |
| | `flagged_by_surface` | TEXT NOT NULL | CHECK enum: `web` / `cli` |
| | `reason_text` | TEXT NULL | operator-optional |
| | `cleared_at` | TEXT NULL | NULL if currently active; ISO timestamp when operator cleared OR auto-cleared on position-open |
| | `cleared_reason` | TEXT NULL | CHECK enum when non-NULL: `operator_cleared` / `auto_cleared_on_position_open` |
| (indexes) | `CREATE UNIQUE INDEX idx_wclf_active_ticker ON watchlist_close_track_flags(ticker) WHERE cleared_at IS NULL` | | **Partial unique index on ACTIVE flags only** (closes Codex R1 M#9). Allows historical cleared-flag rows to persist as audit history while enforcing one ACTIVE flag per ticker. Re-flagging a previously-cleared ticker INSERTs a new row (new lifecycle episode) without UNIQUE collision. |
| `watchlist_close_track_flag_events` | (audit table per D-Q4.7) | | append-only row per set/clear event |
| | `id` | INTEGER PK | |
| | `flag_id` | INTEGER NOT NULL | FK to `watchlist_close_track_flags(id)` |
| | `event_type` | TEXT NOT NULL | CHECK enum: `set` / `clear` |
| | `event_at` | TEXT NOT NULL | server-stamped |
| | `surface` | TEXT NOT NULL | CHECK enum: `web` / `cli` |
| | `reason_text` | TEXT NULL | |

**v20-vs-v21 SCHEMA-LANDING decision** (per dispatch brief §2.4 "likely schema work (v20 → v21 OR fold into v20)"): **Q4 schema FOLDS INTO v20** (single migration LOCK per L6). Rationale: Q4's two tables + `candidates` column avoidance + audit table is bounded; doesn't justify a v21 split. v21 candidates per §3.5 unchanged.

**Theme 4 Sub-bundle T4.SB scope additions** (per dispatch brief §2.4): "~+15-30 fast tests + likely schema work (column on `candidates` OR new `watchlist_close_track_flags` table) + 1 new toggle action on watchlist row + 1 visual surface (badge or section) + 1 new CLI subcommand (possible)." Estimated test delta WITH Q4 included: ~+40-70 fast tests for T4.SB.

### §7.3 Elicitation template for operator-pre-writing-plans pass

This brainstorm spec leaves §7 ready to be amended with the verbatim operator usability list at orchestrator-pre-writing-plans elicitation. The orchestrator drives:

1. **Prompt operator** to draft an unreported-issues list. Provide the structured template below for each issue.
2. **Capture verbatim** in §7 of the spec (amend in place).
3. **Classify each issue by category** per the framework in §7.4.
4. **Size each issue** per the framework in §7.4.

**Per-issue template**:
```
Issue title: <short description>
Surface affected: <web / cli / dashboard / pipeline / specific route>
Frequency: <daily / weekly / per-pipeline-run / occasional>
Severity: <blocking / friction / cosmetic>
Operator framing: <verbatim operator description>
Proposed resolution: <if operator has one>
```

### §7.4 Sizing framework

Per Phase 9 Sub-bundle E + Phase 10 Sub-bundle E "closer" precedent (polish bundles ship 5-10 small fixes within one Sub-bundle).

**Categories**:
- **Form-input ergonomics** (hidden-input tampering surfaces; cp1252 stdout safety; auto-fill polish).
- **Display rendering** (chart-rendering polish; table layout drift; OOB-swap consistency).
- **Navigation flow** (HX-Redirect targets verified registered; broken-link audit; route table coherence).
- **Data freshness** (session-anchor read/write mismatch family; cache invalidation surfaces).
- **CLI ergonomics** (--help text accuracy; subcommand discovery; output formatting).
- **Schema audit** (deferred CLAUDE.md gotcha bug-class promotions).

**Sizing**:
- **SMALL** (~5-15 LOC + 1-3 tests): one-line fixes; sub-bundle target ~5-8 items.
- **MEDIUM** (~30-80 LOC + 5-15 tests): contained per-route or per-surface fixes.
- **LARGE** (~150+ LOC + 20+ tests; multi-surface): typically routes to its own sub-bundle.

**LARGE items NOT absorbed in T4.SB**: escalated to orchestrator-pre-writing-plans for triage; may route to Phase 14 candidate triage.

### §7.5 V2 candidates banked for Theme 4

- Auto-expire on Q4 close-tracking flags after N days configurable per-flag.
- Per-ticker watchlist annotation (free-text notes attached to ticker; NOT a binary flag).
- Operator-drawn chart annotations (closed-loop active learning per v2 brief §9.4 + Phase 14 candidate).
- Bulk-flag CLI (operator pastes ticker list; bulk-flag with shared reason text).

---

## §8 Sub-bundle decomposition refinement (11 sub-bundles per scope-brainstorm §0.5.2 LOCK)

The dispatch sequence + sub-bundle-by-sub-bundle scope from scope-brainstorm §0.5.2 is preserved verbatim. This brainstorm refines:

- Per-sub-bundle scope at task-grain (writing-plans does per-task acceptance criteria).
- Cross-sub-bundle dependencies enumerated.
- Projected test deltas per Sub-bundle 1 + Sub-bundle C precedent: ~+40-100 tests per sub-bundle (Phase 12.5 baseline; Phase 13 may run slightly higher per detector LOC).
- Projected schema deltas (v20 confirmed; per-sub-bundle decomposition).

### §8.1 Dispatch sequence diagram

```
Brainstorm phase (THIS SPEC; THEN orchestrator-pre-writing-plans operator-paired triage)
    -> writing-plans phase
    -> executing-plans phase per Sub-bundle below

T1.SB0 (OhlcvCache -> _step_charts wiring)
    -> T2.SB1 (dev-time labeling infra)          ||  T3.SB1 (entry auto-fill)
        -> [operator paired exemplar bootstrap pause; per OQ-6 LOCK]
    -> T2.SB2 (foundation primitives)
    -> T2.SB3 (detectors VCP + FB + CWH)
    -> T3.SB2 (exit auto-fill)
    -> T2.SB4 (detectors HTF + DBW)
    -> T2.SB5 (template matching)
    -> T3.SB3 (review auto-fill)
    -> T2.SB6 (closed-loop surface + Theme 1 annotated charts)
    -> T4.SB (usability triage + Q4)
    -> Phase 13 CLOSED
```

One concurrent point: T2.SB1 + T3.SB1; rest serial. Estimated wall-clock per scope-brainstorm §0.5.2: ~3-6 weeks operator-paced (orchestrator naive estimate ~30-50 sub-bundle-weeks; operator calibration shows ~3-5x overestimate per `feedback_time_estimates_overstated.md` memory entry).

### §8.2 Per-sub-bundle scope, dependencies, projections

| SB | Scope | Cross-bundle deps | Test delta | Schema delta |
|---|---|---|---|---|
| **T1.SB0** | OhlcvCache wiring into `_step_charts`; shape reconciliation; per-cache locking | NONE (first in sequence) | +20-40 fast | NONE |
| **T2.SB1** | Dev-time labeling infra; Claude Code subagent + selective Codex; operator-paired exemplar bootstrap pause | T1.SB0 | +50-90 fast + ~30-80 silver-tier exemplars persisted manually by operator | v20 migration lands as T2.SB1 task 1 per `T-V20.PRELIM` Option E (closes Codex R2 M#2 — Option C T-V20.PRELIM-at-both-branches fragility); T3.SB1 branches off T2.SB1's first-commit SHA for concurrent dispatch. See §9 OQ-12 for full enumeration. |
| **T3.SB1** | Entry auto-fill via Schwab Trader API at form render; `fill_origin` + audit columns | T1.SB0 (concurrent with T2.SB1) | +40-70 fast + 1 slow E2E | v20 (concurrent with T2.SB1) — `fills` widening |
| **T2.SB2** | Foundation primitives: smoothing + extrema + zigzag + candidate-window generator | T1.SB0 + T2.SB1 (exemplar corpus for parameter tuning) | +60-100 fast | NONE (consumer-side over v20) |
| **T2.SB3** | Rule-based detectors batch 1: VCP + flat base + cup-with-handle | T2.SB2 | +90-150 fast + 1 slow E2E | NONE (writes to `pattern_evaluations` from v20) |
| **T3.SB2** | Exit auto-fill | T3.SB1 + T2.SB3 (Schwab Trader API consumer merge avoidance) | +40-70 fast + 1 slow E2E | NONE (v20 already lands `surface='trade_exit'`) |
| **T2.SB4** | Rule-based detectors batch 2: high-tight-flag + double-bottom-W | T2.SB3 | +70-120 fast | NONE |
| **T2.SB5** | Template matching: DTW with Sakoe-Chiba band; forward + reverse retrieval | T2.SB4 | +60-100 fast | NONE (consumes `pattern_exemplars` + `pattern_evaluations`) |
| **T3.SB3** | Review auto-fill: priors from prior reviews + MFE/MAE from candles + period review section text | T2.SB5 (OhlcvCache patterns + candidate-window primitives) | +50-90 fast | NONE (consumer-side; `review_log.auto_populated_field_keys_json` already in v20) |
| **T2.SB6** | Closed-loop surface (`/patterns/{candidate_id}/review` + outcome distributions on `/metrics/...` 9th tile) + Theme 1 annotated chart deliverable (T2.SB6 closes Theme 1+Theme 2 arc) | T2.SB5 + T3.SB3 | +70-120 fast + 1 slow E2E | NONE |
| **T4.SB** | Usability triage closer + Q4 close-tracking flag (per §7) | All prior | +40-70 fast | v20 already lands `watchlist_close_track_flags` + audit table |

**Cumulative test delta projection**: +590-1020 fast tests + 4 slow E2E across Phase 13 arc. Baseline at Phase 13 start: ~4924 fast (per Phase 12.5 #2 ship). Phase 13 close projection: ~5500-5940 fast.

**Cumulative schema delta**: v19 → v20 single migration (per L6 LOCK). Contents per §3.

### §8.3 v20 migration landing timing

**Five candidate options for landing the v20 migration** (closes Codex R3 m#1 enumeration coherence):

| Option | When | Pros | Cons | Disposition |
|---|---|---|---|---|
| **A** | v20 lands at T2.SB1 (any task position); T3.SB1 must merge AFTER T2.SB1 with NO branching off T2.SB1 | Atomic; simple | Reduces concurrency: T3.SB1 effectively starts after T2.SB1's merge lands | Viable fallback |
| **B** | Dual-schema toleration — T3.SB1 writes `fill_origin` conditionally based on `schema_version` | T3.SB1 runs against pre-v20 base | Dead code paths after v20 ship; complexity | NOT RECOMMENDED |
| **C** | T-V20.PRELIM at head of both branches simultaneously | None — fragile | Duplicate migration files create merge conflict; not natural no-op rebase | REJECTED per Codex R2 M#2 |
| **D** | NEW standalone sub-bundle T-V20 inserted between T1.SB0 and the T2.SB1∥T3.SB1 fork | Clean architectural separation | Breaks scope-brainstorm §0.5.2 11-sub-bundle LOCK; out-of-scope without re-litigation | RE-LITIGATION-REQUIRED |
| **E** (recommended) | v20 lands as T2.SB1 task 1 (first commit on T2.SB1 branch is migration-only); T3.SB1 branches off T2.SB1's first-commit SHA (NOT off main) | Concurrent dispatch preserved; merge ordering locks T2.SB1 first, T3.SB1 second; ZERO duplicate-write-set conflict | Implementer-dispatch coordination required: T3.SB1 worktree branches from T2.SB1's first-commit SHA explicitly, NOT from main | BINDING brainstorm-recommendation |

**Brainstorm recommendation**: **Option E**. Closes the duplicate-write-set conflict that Option C (T-V20.PRELIM at head of both) would have created while preserving the operator-locked concurrency at scope-brainstorm §0.5.2. Operator-pre-writing-plans decision at §9 OQ-12.

### §8.4 Cross-bundle pin discipline

Per Phase 10 T-A.7 + T-E.3 + Phase 12 C.A T-A.7 + Phase 12.5 #2 cross-bundle-pin precedent:

- **T2.SB1 plants** `test_pattern_exemplars_schema_shape_invariant` cross-bundle pin tests that un-skip at later sub-bundles consuming the table.
- **T3.SB1 plants** `test_fill_origin_enum_complete_after_v20` cross-bundle pin that un-skips at T3.SB2 (which extends the consumer surface).
- **T2.SB6 closes** Theme 1 + Theme 2 cross-bundle pin: the annotated chart renderer is shared. Operator-witnessed gate verifies the shared rendering path renders correctly with structural evidence JSON for all 5 V1 patterns.

---

## §9 Open questions OQ-1..OQ-12 with recommendations

### OQ-1 — Sub-bundle count drift (10 vs 11)

**Question**: Dispatch brief §1.5 enumerates 10 sub-bundles; scope-brainstorm §0.5.2 enumerates 11 (T1.SB0 prerequisite added 2026-05-18). Brainstorm follows §0.5.2 LOCK. Should the dispatch brief §1.5 be amended in writing-plans phase?

**Brainstorm recommendation**: YES — amend dispatch brief §1.5 in-place at writing-plans phase to reflect 11 sub-bundles. **Disposition**: BINDING — the operator-locked §0.5.2 is authoritative.

### OQ-2 — Chart rendering technology + cache architecture

**Question**: V1 LOCK is matplotlib SVG inline + new `chart_renders` cache table per §4.3 + §4.4. Are alternatives (HTMX client-side JS chart library; file-based cache; OhlcvCache extension) preferable?

**Brainstorm recommendation**: V1 = matplotlib SVG inline (per Phase 10 §A.10 LOCK precedent) + `chart_renders` cache table. V2 = interactive client-side JS upgrade. **Disposition**: BINDING for V1; operator-pre-writing-plans confirms.

### OQ-3 — `pattern_class` CHECK enum scope + table location

**Question**: Phase 13 widens pattern-classification schema. Two options:
- (a) Widen `pipeline_pattern_classifications.classification` CHECK enum to include 5 V1 patterns.
- (b) Leave alone + route through new `pattern_evaluations` table per §3.2.

ALSO: should `pattern_class` CHECK enum reserve sell-side values for Phase 14 (e.g., `head_and_shoulders_top`, `climax_run`, `stage_4_breakdown`, `ma50_violation`, `ma200_violation`)?

**Brainstorm recommendation**: Option (b) — leave `pipeline_pattern_classifications` alone + route through new `pattern_evaluations` table. New table has richer schema (structural_evidence_json + feature_distribution_log_json + composite_score) that doesn't fit on the existing table. CHECK enum starts with 5 V1 values; sell-side enum widening deferred to Phase 14 migration. **Disposition**: BINDING brainstorm-lock; operator-pre-writing-plans confirms.

### OQ-4 — Template matching distance metric

**Question**: V1 LOCK is DTW with Sakoe-Chiba band per §5.7. SBD + feature-vector distance deferred to V2. Confirm DTW LOCK?

**Brainstorm recommendation**: DTW LOCK with Sakoe-Chiba band, window=0.1 × series length. **Disposition**: BINDING V1; SBD as V2 fallback if the §5.7 pytest-benchmark gate fails (120s/run ceiling on operator's hardware; revised post-Codex R1 M#10 from prior >30s informal threshold — now harmonized with §5.7 LOCK per Codex R2 M#6).

### OQ-5 — Codex SELECTIVE policy definition

**Question**: L9 says "selective (NOT blanket) — 10-20% spot-check tier + high-stakes individual labels." When exactly does Codex review fire?

**Brainstorm recommendation** (per §5.9):
- **Random 15% sample** of `claude_silver` rows per pattern class (median of operator-stated 10-20% band).
- **PLUS high-stakes individual labels**:
  - Claude silver confidence == 'high' AND rule-tier `geometric_score < 0.5` (silver/rule disagreement A direction).
  - Claude silver confidence == 'low' AND rule-tier `geometric_score >= 0.8` (silver/rule disagreement B direction).
- **NO blanket Codex review** of every silver label (matches L9 LOCK).

**Disposition**: BINDING brainstorm-lock; operator-pre-writing-plans confirms.

### OQ-6 — Operator-paired exemplar bootstrap workflow

**Question**: Is the operator-paired mid-dispatch pause for exemplar bootstrap the same shape as post-Phase-12 Sub-bundle 1 cassette session? OR variation?

**Brainstorm recommendation**: SAME SHAPE as Sub-bundle 1 cassette session — T2.SB1 ships labeling infra + recording-script + sanitization filter; operator runs labeling against historical universe in operator-paired session (~30-80 silver-tier exemplars to start); operator spot-checks; operator commits exemplar corpus to worktree branch; operator signals resume; T2.SB2+ continues consuming the corpus.

**Pause-resume mechanism**: identical to Sub-bundle 1 cassette pattern. Operator pastes the resume signal back to the implementer session. **Disposition**: BINDING brainstorm-lock; orchestrator drives operator-paired session.

### OQ-7 — Theme 3 `fill_origin` enum values + backfill discipline

**Question**: §3.3 sketches `fill_origin` CHECK enum as `operator_typed` / `schwab_auto` / `schwab_auto_then_operator_corrected` / `tos_import` / `imported_legacy`. Backfill for v20 sets ALL existing rows to `operator_typed`. Should historical `reconciliation_corrections` chains (CVGI 9 + LION 15 + others) be backfilled into `schwab_source_value_json` + flipped to `schwab_auto_then_operator_corrected`?

**Brainstorm recommendation**: V1 = simple backfill (all `operator_typed`) per §6.4 LOCK. V2 = historical correction-chain backfill candidate (banked). Rationale: V1 keeps schema landing atomic + risk-free; V2 backfill needs careful semantic mapping (Phase 12 reconciliation_corrections have rich audit history not trivially serialized).

**Disposition**: BINDING V1; operator-pre-writing-plans confirms V2 banking.

### OQ-8 — Theme 3 review auto-fill MFE/MAE candle-data source

**Question**: T3.SB3 review auto-fill computes MFE/MAE from candles. Source options:
- yfinance (legacy default).
- Schwab Market Data API (post-Phase-11 Sub-bundle C).
- OhlcvCache (post-T1.SB0).
- Computed from `fills` and current price (no candle data needed).

**Brainstorm recommendation**: OhlcvCache (post-T1.SB0). Rationale:
- Single substrate; consistent with Theme 2 detector data substrate.
- T1.SB0 has already wired OhlcvCache into `_step_charts`; review-auto-fill reuses the same cache.
- yfinance V2-fallback only.
- Schwab Market Data API isn't required for daily-bar history (T1.SB0 routes through OhlcvCache + ohlcv_archive parquet).

**Disposition**: BINDING brainstorm-lock; operator-pre-writing-plans confirms.

### OQ-9 — Drift logging side at Theme 2 Sub-bundles

**Question**: What feature distributions captured per detector run? `feature_log` table OR JSON in `pattern_evaluations`?

**Brainstorm recommendation**: JSON column on `pattern_evaluations` (per §3.2 + §5.11). Rationale:
- JSON column is simpler than dedicated table for the V1 logging-side baseline.
- Phase 13.5 monitoring side can read JSON column at-rest OR promote to dedicated table at that phase's discretion.
- One row per detector run keeps cardinality manageable.

**Disposition**: BINDING V1; Phase 13.5 may promote to dedicated table if query complexity demands.

### OQ-10 — Closed-loop surface T2.SB6 — route location

**Question**: T2.SB6 closed-loop surface ships as:
- (a) NEW Phase 10 metric surface (9th `/metrics/...` tile).
- (b) NEW `/patterns/{candidate_id}/review` route group (parallel to `/reconcile/discrepancy/{id}/resolve` Phase 12.5 #2 surface).
- (c) Widening existing hyp-rec detail page.

**Brainstorm recommendation**: BOTH (a) AND (b):
- (a) `/metrics/pattern-outcomes` — 9th metric surface showing outcome distributions per pattern class cohort. Composes with Phase 10 metrics architecture.
- (b) `/patterns/{candidate_id}/review` — per-candidate review form per v2 brief §9.2 8-item evidence checklist + §9.3 6-decision-type form.
- (c) NO widening of existing hyp-rec detail page — keeps semantic separation between "algorithm flagged" (hyp-rec) and "pattern detector flagged" (new surface).

**Disposition**: BINDING brainstorm-lock; operator-pre-writing-plans confirms.

### OQ-11 — T2.SB1 pattern-labeler subagent definition location

**Question**: T2.SB1 ships a Claude Code subagent for AI-assisted labeling per v2 brief §8.2. Definition file location options: (a) `.claude/agents/pattern-labeler.md` (project-local subagent per Claude Code standard); (b) `agents/pattern-labeler.md` at repo root; (c) NEW `swing-trading` plugin namespace under `.claude/plugins/cache/local/` mirroring copowers plugin precedent.

**Brainstorm recommendation**: (a) `.claude/agents/pattern-labeler.md` — matches Claude Code's standard project-local subagent convention + avoids introducing plugin scaffolding for one subagent. The subagent is consumed via `Agent(subagent_type='pattern-labeler', ...)` from T2.SB1 implementation code.

**Disposition**: BRAINSTORM-recommendation; operator-pre-writing-plans confirms. **Surfaced 2026-05-18 pre-Codex orchestrator-side review** as a banked OQ not previously enumerated.

### OQ-12 — v20 migration landing timing (closes Codex R1 m#3 cross-reference drift; ordering reflects ordered enumeration per Codex R2 m#1)

**Question**: v20 migration introduces tables consumed concurrently by T2.SB1 (`pattern_exemplars` + `pattern_evaluations` + `chart_renders` + `watchlist_close_track_flags`) and T3.SB1 (`fills.fill_origin` enum widening). The scope-brainstorm §0.5.2 locks T2.SB1 + T3.SB1 as CONCURRENT.

**Brainstorm recommendation (revised post-Codex R2 M#2)**: **Option E** — v20 lands as T2.SB1 task 1; T3.SB1 branches OFF T2.SB1's first-commit SHA (NOT off main); concurrent dispatch on bulk of work; merge ordering: T2.SB1 merges first; T3.SB1 second. Closes the duplicate-write-set conflict at the migration file that Option C (T-V20.PRELIM at head of both) would have created.

See §8.3 above for full enumeration of Options A/B/C/D/E with trade-offs.

**Disposition**: BINDING brainstorm-lock; operator-pre-writing-plans confirms.

---

## §10 Discriminating examples — 5-pattern end-to-end walkthroughs

Each walkthrough exercises rule-criteria evaluation + composite scoring + structural evidence emit + (for V1 LOCK validation) hard cases that would trip each criterion.

### §10.1 VCP — CVGI 2026-04-15 anchor (hypothetical reconstruction)

**Input**: CVGI daily bars + Stage 2 confirmed; prior uptrend $3.50 → $5.50 over 9 weeks (57% pct, satisfies criterion #2).

**Candidate window**: anchor 2026-04-15; base $5.20-$5.50 over 32 days (3 weeks - end-2026-05-17).

**Contractions identified** (via zigzag adaptive threshold with monotonic_narrow=True):
1. Contraction 1: $5.50 → $4.30 (22% depth, 8 days).
2. Contraction 2: $5.45 → $4.85 (11% depth, 9 days).
3. Contraction 3: $5.35 → $5.05 (5.6% depth, 7 days).

**Criteria evaluation**:
- #1 stage_2 ✓
- #2 prior uptrend 57% > 30%; 9 weeks > 8 ✓
- #3 N=3 contractions; monotonic 22% > 11% > 5.6% ✓
- #4 T1 22% in [10,35]; T2 11% in [5,20]; T3 5.6% in [3,15] ✓
- #5 volume declines: 145% → 110% → 75% of 50d avg ✓
- #6 duration 32 days in [21, 84] ✓
- #7 pivot $5.30 / base_top $5.34 = 0.992 in [0.99, 1.01] ✓
- #8 breakout volume optional — not observed pre-2026-05-15 in scenario.

**Geometric score**: 7/7 hard + soft criteria pass → 1.0.

**Template-match score**: hypothetical 0.78 forward-retrieval similarity to top historical exemplar.

**Composite score**: 0.60 × 1.0 + 0.40 × 0.78 = 0.91.

**Structural evidence JSON shape**: VCPEvidence dataclass per §5.2; serialized to `pattern_evaluations.structural_evidence_json`.

**T2.SB6 surface render**: 8-item v2 brief §9.2 checklist; contraction sequence rendered with depth labels; top-3 nearest historical bases overlaid; geometric_score breakdown visible.

### §10.2 Flat base — YOU 2026-04-01 anchor (hypothetical reconstruction)

**Input**: YOU daily bars; Stage 2; prior advance $9.20 → $10.50 over 6 weeks (14% pct, satisfies criterion #2 just barely with tolerance).

**Candidate window**: anchor 2026-04-01; range $10.50-$11.80 (12.4% width) over 47 days (~6.7 weeks).

**Criteria evaluation** (rewritten post-Codex R2 M#1 to use §10.6 LOCK semantics inline):
- #1 stage_2 ✓
- #2 prior uptrend 14% vs bound `>= 20%` with tolerance band ±2% (per §10.6 LOCK): the relaxed threshold is `>= 18%`. Operator's hypothetical 14% < 18% → FAILS by 4 percentage points (well outside the tolerance band). Pattern → REJECT; geometric_score = 0.0.

**Alternative pass scenario** (illustrating the rule): if prior uptrend was 22% (over 5+ weeks; >= 18% tolerance-relaxed threshold) → ✓; range slope < 0.005/week ✓; ATR 2.1% / mid_range 11.15 = 0.019 < 0.025 ✓; duration 47 days > 35 ✓; pivot $11.78 / range_top $11.80 = 0.998 in [0.99, 1.01] ✓ → 1.0 geometric score.

**Discriminating point**: criterion #2 hard-gates with ±2% tolerance band; 14% (4 points below relaxed 18% threshold) rejects; 22% (4 points above relaxed 18%) passes.

### §10.3 Cup-with-handle — hypothetical $XYZ candidate

**Input**: $XYZ Stage 2; cup from $20 (left edge 2025-11-01) → $14 (bottom 2025-12-15) → $19.50 (right edge 2026-02-15) — 90 days cup duration; cup_depth 30%; handle from $19.50 → $18 (8 days; depth 7.7%); pivot $19.55.

**Criteria evaluation**:
- #1 stage_2 ✓
- #2 cup_depth 30% in [12%, 35%]; cup_left_to_bottom 45 days >= 28 ✓
- #3 cup_right_edge / cup_left_edge = $19.50/$20 = 0.975 >= 0.95 ✓
- #4 cup_duration 90 days in [42, 182] ✓
- #5 handle_depth 7.7% <= 15%; handle_duration 8 days >= 5 ✓
- #6 handle_low $18 > cup_midpoint ($17) ✓
- #7 pivot $19.55 / cup_right_edge $19.50 = 1.0026 in [0.99, 1.01] ✓
- #8 handle_avg_volume / cup_avg_volume = 0.80 <= 0.85 ✓
- **Rounded-vs-V** (rewritten post-Codex R2 M#1 to use §10.7 LOCK semantics): window centered on `cup_bottom_date=2025-12-15` ±10 days = `[2025-12-05, 2025-12-25]`. Operator confirms 6 bars in this window have `low <= cup_bottom_price × 1.02 = $14.28`; 6 >= 5 → ROUNDED ✓ (V-shape rejection threshold is <= 2 bars; marginal zone is 3-4 bars).

**Geometric score**: 8/8 → 1.0. Composite with template-match: 1.0 × 0.6 + (template-match score) × 0.4.

### §10.4 High-tight flag — hypothetical $WXYZ pole

**Input**: $WXYZ Stage 2; pole $5 → $11 over 35 days (120% gain); consolidation $9-$10.40 over 25 days (range width 15.6%; pullback from peak 18%); volume during consolidation drops 40% from pole_avg.

**Criteria evaluation**:
- #1 stage_2 ✓
- #2 pole_pct 120% >= 90%; pole_duration 35 days in [28, 56] ✓
- #3 consolidation_pullback 18% <= 25%; consolidation_duration 25 days in [21, 35] ✓
- #4 consolidation_width 15.6% vs bound `<= 15%` with tolerance NONE per §5.5 LOCK (rewritten post-Codex R2 M#1 to use §10.6 LOCK semantics inline): the bound is STRICT; 15.6% > 15% → FAILS. Pattern → REJECT; geometric_score = 0.0.

**Alternative pass scenario** (illustrating the rule): if consolidation_width was 14.8% (`<= 15%` strict) → ✓; #5 volume drop 40% (consolidation_avg 0.60 of pole_avg <= 0.65 cap) → ✓; #6 pivot at consolidation_top $10.40 ✓ → all 6 criteria pass; geometric_score = 1.0.

**Discriminating point**: HTF criterion #4 width is a STRICT bound (NONE tolerance). Any width > 15% rejects; orchestrator-pre-writing-plans may revisit the tolerance band at writing-plans time, but the brainstorm LOCK keeps it strict per the §10.6 LOCK semantics.

### §10.5 Double-bottom-W — hypothetical $UVWX recovery

**Input**: $UVWX recently transitioning from Stage 4 → Stage 2; trough_1 $20 (after 25% drawdown from $26.67 peak); center peak $23 (60% retracement); trough_2 $19 (5% undercut of trough_1).

**Criteria evaluation**:
- #1 stage_2 from recent stage_4 ✓
- #2 trough_1_drawdown 25% >= 15% ✓
- #3 center_peak_retracement 60% >= 50% ✓
- #4 trough_2 $19 / trough_1 $20 = 0.95 (5% undercut) within [0.95, 1.05] ✓
- #5 trough_1→center_peak duration 20 days in [5, 35] ✓; center_peak→trough_2 duration 18 days in [5, 35] ✓
- #6 pivot at center_peak $23 ✓
- #7 trough_2 volume rises (shakeout) — optional; observed 1.4× trough_1 volume — ✓
- #8 undercut bonus +0.10 → geometric_score 1.10 (capped at 1.0 in composite).

**Composite score**: min(1.0, 0.60 × 1.10 + 0.40 × template_match_score) — discriminating: 5-pattern V1 needs bonus-clip handling in composite formula.

### §10.6 Tolerance-semantics + composite-scoring uniformity LOCK (closes Codex R1 M#7 + M#8)

The per-pattern criteria tables (§5.2-§5.6) and the worked examples (§10.1-§10.5) must use uniform tolerance semantics. **Brainstorm-locked semantics** (BINDING for writing-plans):

- **"Tolerance band ±X%"** in a criterion table means the criterion PASSES if `actual_value` falls within `[bound - X%, bound + X%]`. The criterion FAILS if outside this range. The band is symmetric.
- **"NONE — hard gate"** means the criterion uses STRICT inequalities with NO tolerance; failure rejects the pattern.
- **"NONE — these are bounds, not point thresholds"** means the criterion uses RANGE checks (e.g., depth in [10%, 35%]); failure-on-out-of-range; ZERO tolerance.

**Errata corrections from R1 M#7 worked-example arithmetic**:

- **§10.2 Flat base worked example errata**: criterion #2 has tolerance band ±2% on the `prior_uptrend_pct >= 20%` bound. Operator's hypothetical 14% prior_uptrend FAILS (14% < 20% - 2% = 18%; 4-6 percentage points outside the tolerance band). Worked example previously stated REJECT correctly but with confusing tolerance language; clarified verbatim above. The alternative-pass scenario at §10.2 uses 22% which is >= 18% so PASSES the relaxed threshold.
- **§10.4 High-tight flag worked example errata**: criterion #4 (consolidation_width) tolerance LOCKED at NONE; the criterion bound is 15% upper limit. With NO tolerance, 15.6% > 15% rejects. Previous worked-example mid-text ("with ±1% tolerance: 15.6% > 16% rejects") confused the bound (16%) with the tolerance-relaxed threshold; the actual NO-tolerance evaluation correctly REJECTs at 15.6% > 15%. The final disposition (REJECT) is correct.

### §10.7 Cup curvature definition LOCK (closes Codex R1 M#8 incoherent rounded-vs-V test)

The §5.4 cup-with-handle "rounded-vs-V test" must be DEFINED around the **cup_bottom_date** (the price extremum), NOT around the temporal midpoint between cup_start and cup_bottom. The previous formulation conflated TWO different points.

**Brainstorm-locked rounded-vs-V test**: centered on `cup_bottom_date` with a ±10-day window:

- Compute `window_lows = bars where bar_date in [cup_bottom_date - 10 days, cup_bottom_date + 10 days]`.
- Compute `bars_within_2pct_of_bottom = bars in window_lows where bar.low <= cup_bottom_price × 1.02`.
- **Rounded test**: `len(bars_within_2pct_of_bottom) >= 5` (at least 5 bars within 2% of bottom indicates the trough is stretched out, not a V).
- **V-shape rejection**: `len(bars_within_2pct_of_bottom) <= 2` rejects the candidate as V-shaped.
- **Marginal zone**: 3-4 bars within 2% is operator-review-flagged (composite score penalty 0.10).

**Worked example errata at §10.3**: previously stated `cup_midpoint_date = 2025-12-30` but `cup_bottom_date = 2025-12-15` — these are 15 days apart. Under the LOCKED definition, the 21-day window centered on `cup_bottom_date=2025-12-15` is `2025-12-05` to `2025-12-25`. Operator confirms 5+ bars in this window have low <= $14.00 × 1.02 = $14.28 → ROUNDED ✓. The §10.3 example is structurally sound; only the midpoint date confusion was the defect (now corrected via this LOCK).

---

## §11 Forward-binding lessons inherited (cited)

Phase 13 inherits ~60 cumulative forward-binding lessons from Phase 11 + 12 + 12.5 arcs. The most-load-bearing for Phase 13 sub-bundle dispatches:

1. **Schema-CHECK + Python-constant + dataclass-validator paired atomic landing** (Phase 12 C.A T-A.2). Applies to every CHECK enum widening + cross-column CHECK invariant in v20 (per §3.5 audit; full roster: `DETECTOR_PATTERN_CLASSES` + `label_source` + `final_decision` + the source-vs-decision matrix CHECK on `pattern_exemplars` + the relabel-vs-non-relabel coherence CHECK + `fill_origin` + widened `schwab_api_calls.surface` + `chart_renders.surface` + chart_renders cross-column CHECKs + Q4 enums on `watchlist_close_track_*`).
2. **Migration backup-gate strict equality form** (`pre_version == 19`, NOT `<=`) — Phase 12 C.A.
3. **No `INSERT OR REPLACE` on audit-trail tables** — pattern_exemplars + pattern_evaluations + watchlist_close_track_flags inherit SELECT-then-UPDATE-or-INSERT discipline.
4. **`executescript()` implicit COMMIT** — v20 migration uses explicit `BEGIN`+`executescript`+`COMMIT` in `_apply_migration` per existing discipline.
5. **`apply_overrides(cfg)` + `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` + `construct_authenticated_client` 4-arg signature discipline** at every new Schwab entry point (Phase 12 Sub-bundle B `apply_overrides` discipline + post-Phase-12 Sub-bundle 1 `construct_authenticated_client` 4-arg signature). T3.SB1 + T3.SB2 emit new Schwab consumer surfaces. The `allow_prompt=False` form is REQUIRED for any HTTP handler entry point (form-render time) to prevent blocking stdin prompts.
6. **Cassette infrastructure URI/path + body sanitization** (post-Phase-12 forward-binding lesson #2). T2.SB1 dev-time labeling cassettes + T3.SB1 entry auto-fill cassettes inherit.
7. **Standalone recording scripts** (post-Phase-12 lesson #3). T2.SB1 labeler-cassette recording script + T3.SB1+SB2 Schwab-fetch cassette extension.
8. **HTMX gotcha trinity**: HX-Request propagation on embedded forms + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted. T3.SB1/SB2/SB3 forms + T2.SB6 review form + T4.SB Q4 toggle inherit.
9. **Base-layout VM banner pin** (Phase 10 T-E.3 + Phase 12.5 #2 13-VM standalone retrofit). New VMs introduced in Theme 1 + Theme 2 + Theme 3 + Theme 4 MUST populate `unresolved_material_discrepancies_count` + `banner_resolve_link`.
10. **Session-anchor read/write mismatch family**: forward-looking `action_session_for_run` vs backward-looking `last_completed_session`. T1.SB0 cache staleness check + Theme 1 `chart_renders` cache invalidation per §4.4 LOCK + T2.SB6 closed-loop surface + T3.SB3 review auto-fill MFE/MAE candle anchor + T4.SB Q4 flag persistence all inherit. Discriminating round-trip test pattern per Phase 8 `cfacbc5` precedent (CLAUDE.md gotcha "Session-anchor read/write mismatch silently invisibles UI display"): write a row, immediately read via the UI/read predicate, assert visibility flips correctly.
11. **OhlcvCache writes from in-deadline futures only** (Phase 11 lesson). T1.SB0 verifies discipline preserved.
12. **External-API empty-result transient handling** (Phase 11 lesson). T3.SB1 + T3.SB2 Schwab Trader API empty response handling.
13. **Synthetic-fixture-vs-production-emitter shape drift** (Phase 12 C.D family + Phase 12.5 Q2). T2.SB1 + T3.SB1 + T3.SB2 + T3.SB3 + T4.SB tests use real-shape fixtures, not invented synthetic shapes.
14. **Windows cp1252 stdout safety** (Phase 12 C.D gate-fix #1+#3). All Theme 1 + Theme 2 + Theme 3 + Theme 4 CLI surfaces ASCII-only.
15. **Matplotlib mathtext gotcha** — Theme 1 SVG inline + ZERO `$`/`^`/`_`/`\\` in any chart title/axis label.
16. **Pre-Codex orchestrator-side review BINDING** (C.C lesson #6; 8th cumulative validation). Phase 13 writing-plans + executing-plans dispatches inherit.
17. **Implementer self-report accuracy gate — cite file:line evidence** (C.C lesson #7).
18. **`Co-Authored-By` footer suppression** (C.B lesson #7). Every commit in Phase 13 arc: NO footer.
19. **Pass-2-tier-1-FORBIDDEN family resolution** (Phase 12 + post-Phase-12 Sub-bundle 1 mapper widening). T3.SB1 + T3.SB2 consume execution-grain price + quantity from post-Phase-12 Sub-bundle 1 mapper.
20. **Hidden audit field server-stamping** (Phase 8 R2-R5 family). T3.SB1 + T3.SB2 + T3.SB3 + T4.SB form audit fields server-stamped at handler entry.

---

## §12 Risks + mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Theme 2 detectors brittle on threshold tuning; over-fitting to operator's recent regime | HIGH | (1) Tolerance bands per criterion (per v2 brief §5.1 weakness mitigation); (2) AI-assisted parameter tuning against curated exemplars (per v2 brief §5.1 + §8.2); (3) Synthetic-generation negative examples per v2 brief §8.3 |
| Multi-comparisons: ~250 tickers × 5 patterns × 1 timeframe = ~1250 detector tests / day; false-positive density | MEDIUM | (1) Universe pre-filter is hard gate (Stage 2 only); (2) Pattern frequency drift surface in Phase 13.5 monitoring side; (3) Composite scoring + ranking presents top-K to operator |
| Survivorship bias under trend-template universe selection (per v2 brief §15) | MEDIUM | (1) Delisted-stock data inclusion — operator-pre-writing-plans confirms data source covers delisted; (2) V2 candidate: Schwab data archive expansion |
| Self-drift in operator labels (per v2 brief §14.4 + §6.4 quality_grade field) | MEDIUM | (1) Quarterly re-grading helper at T2.SB6 surface; (2) Phase 13.5 monitoring side surfaces self-drift rate |
| OhlcvCache contention under T1.SB0 + Theme 2 detectors + Theme 1 chart renders all touching cache | MEDIUM | (1) Per-cache locking + lifecycle semantics LOCK at T1.SB0; (2) Discriminating test: concurrent fetch + chart-render |
| Theme 3 auto-fill regressions on Schwab API empty response / DEGRADED / sandbox state | MEDIUM | (1) Per §6.1+6.2 empty-state handling LOCK; (2) Discriminating test per state |
| Q4 close-tracking flag inflation (operator flags 50 tickers, never clears) | LOW | (1) V2 candidate: auto-expire after N days; (2) V1 visual differentiation flagged-but-not-algo so operator sees own staleness |
| Theme 2 detector LOC explosion (5 patterns × ~200 LOC each = ~1000 production LOC; +90-150 fast tests per pattern detector sub-bundle = ~250 fast tests per pattern detector) | MEDIUM | Plan accordingly; T2.SB3 + T2.SB4 may overshoot Phase 12.5 sub-bundle baseline test counts. Per `feedback_time_estimates_overstated.md` memory: orchestrator-side estimates overrun by 3-5x; trust operator wall-clock pacing. |
| Subagent-cassette infrastructure complexity (T2.SB1 ships labeling infra with Claude Code subagent + Codex MCP) | MEDIUM | (1) Mirror post-Phase-12 Sub-bundle 1 cassette session precedent verbatim; (2) Operator-paired session for first labeling pass |
| ASCII-only invariant regressions in detector + chart code surfaces | LOW | (1) Inherits CLAUDE.md gotcha + Phase 12 C.D gate-fix #3 stdout UTF-8 reconfigure as safety net; (2) Discriminating test: cp1252 stdout encode-test on rendered text |

---

## §13 V2 / Phase 14 candidates banked

(Mirrors the v2 brief out-of-scope list + theme-specific V2 candidates surfaced during brainstorm.)

| ID | Candidate | Source | Disposition |
|---|---|---|---|
| V2-1 | Interactive client-side JS chart library (TradingView Lightweight Charts / Plotly) | Theme 1 §4.7 | Phase 14+ |
| V2-2 | Per-row sparklines in `/trades/` + `/watchlist/` | Theme 1 §4.7 | Phase 14+ |
| V2-3 | Multi-timeframe chart toggle (daily ↔ weekly) | Theme 1 §4.7 | Phase 14+ |
| V2-4 | Annotation editor (operator-drawn pattern boundaries override detector) | Theme 1 §4.7 + v2 brief §9.4 | Phase 14+ |
| V2-5 | Z-score normalization for template-matching shape comparison (vs V1 min-max) | Theme 2 §5.7 | Phase 14+ (gated on calibration discipline) |
| V2-6 | Calibration of composite_score (Brier + isotonic regression) | Theme 2 §5.8 | V2 — gated on v2 brief §16.5 G2 200 confirmed positives per pattern |
| V2-7 | SBD or feature-vector template-matching distance metric | Theme 2 §5.7 | Phase 14+ |
| V2-8 | Matrix Profile-based exemplar retrieval at scale | v2 brief §5.8 + §10 Phase 7 | Phase 14+ |
| V2-9 | Shapelet-based detection | v2 brief §5.9 | Phase 14+ |
| V2-10 | Small ML re-ranker (Role 2 per v2 brief §16.1) | v2 brief §16.6 + 7 gates | Indefinitely deferred |
| V2-11 | Sell-side detector module (H&S top + climax run + Stage 4 breakdown + MA50/MA200 violations) | v2 brief §4.3 + §10 Phase 8 | Phase 14 |
| V2-12 | Drift monitoring side (feature drift / pattern frequency / outcome / self-drift dashboards) | v2 brief §14 | Phase 13.5 |
| V2-13 | Backfill historical `reconciliation_corrections` chains into `fills.schwab_source_value_json` | Theme 3 §6.4 + §9 OQ-7 | V2 |
| V2-14 | `review_log.fields_auto_populated_count` + `auto_fill_disagreement_count` aggregate columns | Theme 3 §3.5 | V2 |
| V2-15 | Q4 close-tracking flag auto-expire after N days | Theme 4 §7.5 | V2 |
| V2-16 | Per-ticker watchlist annotation (free-text notes attached to ticker) | Theme 4 §7.5 | V2 |
| V2-17 | Bulk-flag CLI for Q4 | Theme 4 §7.5 | V2 |
| V2-18 | "Elevated to hyp-rec" toggle for Q4 flags | Theme 4 §7.5 + §10 D-Q4.6 | V2 |
| V2-19 | Multi-cohort architectural deepening (per-cohort risk policy / capital allocation / state machine) | Dispatch brief §1.6 | Phase 14+ |
| V2-20 | Intraday / live-trading integration | Dispatch brief §1.6 | Phase 14+ |
| V2-21 | Tax-lot accounting + cost-basis tracking | Dispatch brief §1.6 | Phase 14+ |
| V2-22 | Branch A research-branch activation (Phase 0 study harness + first promotion) | Dispatch brief §1.6 | Deferred per operator 100% operational |

---

## §14 Out-of-scope reaffirmation

Per dispatch brief §3 + §1.6 + scope-brainstorm §0.5.4. Phase 13 does NOT:

- Draft migration SQL (writing-plans territory).
- Draft service-module / view-model / query implementations / Jinja templates / route handlers / repo functions / CLI command bodies.
- Decompose sub-bundles into per-task acceptance criteria (writing-plans output).
- Re-litigate §1 + §0.5 binding constraints (operator-locked).
- Design sell-side detector (Phase 14).
- Design ML re-ranker (indefinitely deferred).
- Design drift monitoring side (Phase 13.5).
- Address Phase 12.5 items (already SHIPPED 2026-05-18 pre-Phase-13).
- Re-derive forward-binding lessons (accept ~60 cumulative as given).
- Design intraday / tax-lot / multi-cohort / harmonic / candlestick / image-CV / sequence-transformer patterns (out of scope).

---

## §15 References

### §15.1 Anchored documents (read in order at brainstorm)

1. `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` — operator-authored 2026-05-08; 901 lines; AI-ingestion-ready. PRIMARY substrate for Theme 2.
2. `docs/phase13-scope-brainstorm.md` §0.5 — operator-locked scope 2026-05-17; 4 themes / 11 sub-bundles / 11 design locks.
3. `docs/phase13-brainstorm-dispatch-brief.md` — implementer dispatch brief (368 + Q4 amendment lines).
4. `docs/phase3e-todo.md` Item Q4 entry — operator close-tracking flag use case + 7 architectural decisions.
5. `CLAUDE.md` gotcha section (~60 cumulative gotchas) at repo root.
6. `docs/orchestrator-context.md` (~60 cumulative forward-binding lessons).

### §15.2 Methodology corpus (Phase 13 Theme 2 substrate)

7. `reference/methodology/minervini-trend-template.md` — Stage 2 entry criteria.
8. `reference/methodology/minervini-sell-side-rules.md` — sell-side patterns (Phase 14 substrate; informational here).
9. `reference/methodology/dst-take-profit-and-trail.md` — Disciplined Swing Trader take-profit + trail mechanics.
10. `reference/phase_0_3_chart_reading_fundamentals.pdf` + `reference/chart_study_worksheet*.docx` + `reference/images/flag_pattern.png` + `reference/images/pennant_pattern.png` — pre-existing operator-reference materials.

### §15.3 v2 brief references (foundational literature)

11. **Lo, Mamaysky, and Wang (2000)** — *Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation.* J. Finance. Kernel-regression smoothing reference for Theme 2 historical-exemplar curation.
12. **Berndt and Clifford (1994)** — Dynamic Time Warping for pattern matching. T2.SB5 DTW with Sakoe-Chiba constraint.
13. **Marshall, Young, Rose (2006)** — Candlestick technical trading strategies; weak-to-zero predictive power on developed-market equity. v2 brief §4.4 candlestick-out-of-scope rationale.
14. **Minervini, M.** — *Trade Like a Stock Market Wizard.* VCP definition + Stage 2 specifics.
15. **O'Neil, W.J.** — *How to Make Money in Stocks.* CANSLIM + cup-with-handle + flat base + base structures.

### §15.4 Precedent spec docs (format reference)

16. `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` — post-Phase-12 brainstorm canonical (1086 lines; section-numbered format mirrored here).
17. `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` — Phase 12.5 #2 brainstorm spec; OQ-LOCK pattern mirrored.

---

*End of Phase 13 design spec. 4-theme architectural arc (Charts + Pattern Recognition + Auto-fill + Usability + Q4 fold-in). 11 sub-bundles per scope-brainstorm §0.5.2 LOCK. 12 open questions OQ-1..OQ-12 with brainstorm-recommendations for orchestrator-pre-writing-plans confirmation (OQ-11 added pre-Codex; OQ-12 added Codex R1 fix bundle for v20 landing timing). 7 Q4 sub-decisions D-Q4.1..D-Q4.7 with recommendations. Schema v19 → v20 single migration. Phase 13.5 (drift monitoring) + Phase 14 (sell-side + ML re-ranker gated) banked. Writing-plans dispatch UNBLOCKED pending operator-pre-writing-plans triage of §9 OQs + §7.3 usability-list elicitation.*
