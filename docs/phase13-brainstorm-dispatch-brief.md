# Phase 13 — Charts + Pattern Recognition + Auto-fill + Usability Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for Phase 13 — a 4-theme architectural arc spanning chart rendering deepening + chart pattern recognition deepening (Minervini/CANSLIM family) + auto-fill across trade entries / exits / reviews + usability triage. Anchored on operator's pre-existing v2 chart pattern detection brief (`reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md`; 901 lines; AI-ingestion-ready). Schema migration to v20 confirmed; major banked items (sell-side detector module, ML re-ranker, drift detection) are explicitly OUT of Phase 13 scope.

**Brief:** `docs/phase13-brainstorm-dispatch-brief.md` (this file).

**Sequencing:** Phase 12 CLOSED 2026-05-17 (Sub-bundles A + B + C). Post-Phase-12 Schwab mapper execution-grain widening arc (Sub-bundles 1 + 2) + Phase 12.5 3-item bundle (OQ-F multi-leg auto-redirect + web Tier-2 surface + CLAUDE.md+orchestrator-context maintenance pass) ship BEFORE Phase 13 dispatches. Phase 13 is the next architectural arc post-Phase-12.5; Phase 13.5 (drift detection) follows Phase 13; Phase 14 candidates (sell-side detector, ML re-ranker gate revisit) follow Phase 13.5.

**Expected duration:** ~150-300 minutes brainstorm + 5-9 adversarial Codex rounds. Phase 13 brainstorm scope is comparable to Phase 12 Sub-bundle C brainstorm (9-substantive-round chain; 1444-line spec) — the chart pattern detection v2 brief already absorbs much architectural-design surface, but Phase 13 has 4 themes including auto-fill + usability + chart-rendering scope NOT in the v2 brief, so spec line target is ~1500-2200 lines.

---

## §0 Read first

In this order:

1. **`reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md`** — operator-authored 2026-05-08; 901 lines; AI-ingestion-ready analysis brief for chart pattern detection. **THIS IS THE PRIMARY SPEC SUBSTRATE FOR THEME 2.** Read end-to-end. §4 enumerates pattern families with tractability ratings; §5 enumerates mathematical approaches with primary/secondary/deferred designations; §10 recommended phased roadmap maps directly onto Phase 13 sub-bundle decomposition; §16 ML re-ranker decision analysis (DEFERRED per operator decision); §17 Recommended Starting Point gives 7-item starter list.
2. **`reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_delta_review.md`** — v1→v2 delta review (638 lines). Read for context on what was added/removed in v2 (informs which architectural decisions are already settled vs still open).
3. **`reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion.md`** — v1 (802 lines; superseded by v2). Read OPTIONALLY for historical context; v2 is authoritative.
4. **`docs/phase13-scope-brainstorm.md`** §0.5 — **OPERATOR-LOCKED SCOPE** (4 themes; 10 sub-bundles; 11 locked design decisions; what's banked). LOCKED 2026-05-17 via operator-orchestrator scope conversation. **DO NOT re-litigate §0.5.** Sections §1-§4 are historical reasoning that produced the lock.
5. **`reference/methodology/`** — Minervini Trend Template (28 lines; entry criteria); Minervini sell-side rules (151 lines; sell-side detector module BANKED for Phase 14, but rules inform sell-side scope-banking rationale); DST take-profit-and-trail (236 lines; pattern context). Plus `reference/phase_0_3_chart_reading_fundamentals.pdf` (binary PDF; pre-existing reference) + `reference/chart_study_worksheet*.docx` + `reference/images/flag_pattern.png` + `pennant_pattern.png`.
6. **`CLAUDE.md`** at repo root — project conventions + gotchas. Especially: HTMX gotcha trinity (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted) for Theme 1 dashboard surface work; matplotlib mathtext gotcha (Phase 10 §A.10 inline-SVG LOCK avoids); `base.html.j2` shared-field discipline (every new VM extending base.html.j2 must populate `unresolved_material_discrepancies_count`); session-anchor read/write mismatch family (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`) for any new session-keyed surface; SQLite `INSERT OR REPLACE` cascade-wipe gotcha for any new audit-trail-with-uniqueness pattern.
7. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — the LAST section has the ~60 cumulative forward-binding lessons inherited (Phase 11 17 + Phase 12 A 5 + B 12 + C brainstorm 5 + C.A 3 + C.B 7 + C.C 7 + C.D 7 + 4 NEW C.D-arc + post-Phase-12 brainstorm + writing-plans). All load-bearing.
8. **`docs/phase3e-todo.md`** top entries 2026-05-17 in TOP-DOWN order: post-Phase-12 Sub-bundle 1 SHIPPED entry; Phase 12.5 RESCOPED entry; Phase 13 scope-brainstorm IN PROGRESS entry; Phase 12 Sub-sub-bundle C.D SHIPPED entry. Cross-references the operator-locked decisions inherited by Phase 13.
9. **`docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`** — post-Phase-12 brainstorm spec (1086 lines; ZERO ACCEPT-WITH-RATIONALE; 5 Codex rounds). Read for SPEC FORMAT REFERENCE — Phase 13 spec mirrors this section-numbered style + locked-decisions-vs-OQ pattern + discriminating-example walkthroughs.
10. **`docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`** — post-Phase-12 writing-plans output (1215 lines; ZERO ACCEPT-WITH-RATIONALE; 6 Codex rounds with operator-override past MAX_ROUNDS+1). Read for PLAN FORMAT REFERENCE (writing-plans phase will mirror this).
11. **`swing/integrations/schwab/models.py:133+`** — `SchwabOrderResponse` dataclass with `executions: list[SchwabExecutionLeg] | None = None` field (just shipped by Sub-bundle 1). Phase 13 chart pattern detection consumes execution-grain data + Schwab/OhlcvCache caching architecture.
12. **`swing/data/repos/candidates.py`** + `swing/data/repos/trades.py` + `swing/data/repos/review_log.py` + `swing/data/repos/fills.py` + `swing/data/migrations/0010_trade_chart_pattern.sql` + `swing/data/migrations/0012_sector_industry.sql` + `swing/data/migrations/0014_phase7_state_machine_and_fills.sql` — shipped schema surfaces Phase 13 composes over. `candidate_id` → `trade_id` → `realized_R` chain is the closed-loop infrastructure §6.4/§9 of v2 brief assumes; verify shape via grep at brainstorm-time.

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema sketches + service-architecture sketches are NOT plan tasks.
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED + OPERATOR-LOCKED — do NOT re-litigate)

### §1.1 Operator-locked architectural framing

Per `docs/phase13-scope-brainstorm.md` §0.5 (LOCKED 2026-05-17):

1. **Algorithm posture: NO run-time AI inferencing.** Claude API in runtime pipeline NOT acceptable. Rule-based geometric detection PRIMARY; template matching SECONDARY; **DEV-TIME** Claude Code subagent dispatch for AI-assisted labeling per v2 brief §8.2 IS acceptable (silver-tier labels with `ai_labeler_version` tracking).
2. **V1 pattern set = 5 buy-side patterns**: VCP + flat base + cup-with-handle + high-tight-flag + double-bottom-W. Collapses v2 brief's Phase 1 + Phase 3 into Phase 13 V1.
3. **Sell-side detector module BANKED to Phase 14** (v2 brief §4.3 + §10 Phase 8 gated). Phase 13 does NOT design sell-side patterns.
4. **ML re-ranker DEFERRED indefinitely** per v2 brief §16.6 (12-18 months minimum) + operator "not near-term unless clear and convincing evidence" + 7 gates G1-G7 not yet met. Phase 13 does NOT design ML re-ranker.
5. **Drift detection SPLIT to Phase 13.5** (v2 brief §14 4 surfaces: feature / pattern frequency / outcome / self-drift). Phase 13 BAKES IN the LOGGING side (feature distributions captured per detector run) so Phase 13.5 has baseline material when it ships. Phase 13 does NOT design the monitoring/dashboard side.
6. **Schema appetite open** — operator confirmed v20 acceptable. `chart_pattern_evaluation` widening + new `pattern_exemplars` library table + `label_source` enum + `ai_labeler_version` tracking + likely `fill_origin` enum widening (Theme 3 auto-fill) + auto-fill audit columns. v21+ possible if specific theme demands.
7. **100% operational** — Branch B priority-stack continuation per V2.1 §VI; research-branch (V2.1 §V) Phase 0 activation NOT in Phase 13 scope.
8. **Single-strategy SEPA+DST focus** — operator 6mo strategic intent. Multi-cohort/multi-strategy deepening is Phase 14+ candidate.
9. **Codex as second reviewer = SELECTIVE** (NOT blanket) — 10-20% spot-check tier + high-stakes individual labels where Claude silver confidence diverges from rule-tier evidence. Schema-wise: `pattern_exemplars.codex_reviewed: bool NULL` + `codex_agreement: bool NULL`.
10. **Theme 3 absorbs original Phase 12.5 #2** (fill auto-population at trade-entry) — entries + exits + reviews + period reviews owned coherently by Theme 3.
11. **Theme 4 elicitation: operator drafts unreported-usability-issues list at brainstorm time** as one of the brainstorm spec inputs (alongside v2 brief + auto-fill scope decisions). Phase 13 Sub-bundle T4.SB implements the elicited list.

### §1.2 Concrete current-state evidence

Production state at dispatch time (per operator's actual operational use 2026-05-17):

- **Phase 4 `chart_pattern_evaluation`** is operator-classification-only with system-classifier flag (per migration 0010 + Phase 4 evaluation). "Very basic" — does NOT generate annotated charts for hyp-recs; pattern recognition is essentially manual.
- **OhlcvCache + ohlcv_archive parquet caching** (Phase 11 Sub-bundle C) means broader chart-rendering no longer burns yfinance quota for multi-day-list tickers. **Architectural constraint that previously blocked Phase 13-style chart breadth is RESOLVED.**
- **Methodology corpus** at `reference/methodology/` (3 files; 415 lines) includes Minervini Trend Template (entry) + Minervini sell-side rules + DST take-profit-and-trail. Sell-side rules WERE missing per Sub-bundle C investigation 2026-05-10 §3.G but appear to have been added since (Minervini sell-side rules file dates 2026-05-10 22:21). **Reference material constraint that previously blocked algorithm-design is RESOLVED.**
- **Closed-loop infrastructure** is LARGELY shipped: `candidates` table (Phase 4) + `trades.candidate_id` FK (Phase 7) + `trades.realized_R_if_plan_followed` + `actual_realized_R_effective` (Phase 7) + `review_log` per-trade reviews (Phase 6) + Phase 10 metrics hit rate + R-multiple per cohort. v2 brief §6.4 label schema (`candidate_id → trade_id → outcome`) maps onto existing schema.
- **Schwab Trader API integration** (Phase 11 Sub-bundle B) + `apply_overrides(cfg)` cascade (Phase 12 Sub-bundle B) + `construct_authenticated_client` 4-arg signature (Phase 12 Sub-bundle B + post-Phase-12 Sub-bundle 1) — all surfaces Theme 3 auto-fill consumes are operational.
- **Post-Phase-12 Sub-bundle 1 SHIPPED 2026-05-17** — `SchwabExecutionLeg` dataclass + `SchwabOrderResponse.executions` field + execution-grain comparator + Shape C classifier predicate + cassette infrastructure at `tests/integrations/cassettes/schwab/` + `scripts/record_schwab_cassettes.py` recording script. Phase 13 Theme 2 may compose over execution-grain data for pattern detection (e.g., breakout-volume validation per v2 brief §5.1 illustrative VCP criterion #7 — execution-leg volume aggregation could be richer than order-level breakdown).

### §1.3 Binding integrations

Phase 13 consumes shipped Phase 4 + Phase 6 + Phase 7 + Phase 9 + Phase 10 + Phase 11 + Phase 12 + post-Phase-12 surfaces:

- **`candidates` table (Phase 4 evaluation)**: pattern_class column already exists per migration `0010_trade_chart_pattern.sql`. Phase 13 widens CHECK enum to include 5 pattern classes ('VCP' / 'flat_base' / 'cup_with_handle' / 'high_tight_flag' / 'double_bottom_w'); current value set TBD by grep at writing-plans time.
- **`trades.candidate_id` FK (Phase 7)**: closed-loop back-link. Phase 13 Theme 2 Sub-bundle T2.SB6 surfaces outcome distributions per `candidates.pattern_class` cohort dimension. Reuses Phase 10 metrics cohort architecture.
- **`review_log` (Phase 6)**: per-trade review with frozen aggregates. Phase 13 Theme 3 review auto-fill at T3.SB3 pre-populates review form fields from prior reviews + MFE/MAE from candles. Composes with Phase 8 daily_management_records for MFE/MAE history.
- **`fills` table (Phase 7)**: `reconciliation_status` enum + `fill_origin` candidate widening for Theme 3 auto-fill provenance (operator-typed-from-memory vs Schwab-auto-populated vs operator-corrected). Schema v20 likely adds enum value + audit columns.
- **`schwab_api_calls` (Phase 11)**: audit table for Schwab API invocations. Phase 13 Theme 3 entry/exit auto-fill emits new audit rows with `surface='trade_entry'` or `surface='trade_exit'` (CHECK enum widening V2 candidate per Sub-bundle B precedent).
- **`reconciliation_corrections` (Phase 12 C.A)**: Theme 3 entry auto-fill avoids the "fiction-vs-truth" divergence pattern Phase 12 C addressed. Operator-typed-from-memory entry fills generated reconciliation discrepancies (CVGI 41 + DHC 39 + VSAT 40 + LION 45); Theme 3 closes the SOURCE side prospectively.
- **OhlcvCache + ohlcv_archive (Phase 11 Sub-bundle C)**: data substrate Theme 2 pattern detection consumes for daily + weekly bar processing. Already cached aggressively for multi-day-list tickers; Phase 13 leverages for chart rendering breadth (Theme 1) + pattern-detection input data (Theme 2).
- **Phase 4 evaluation pipeline**: universe filter + Stage 2 trend template + RS rank are LARGELY shipped (per V2.1 §VI.B1 priority + Phase 9 risk_policy at-lock-time stamp + Phase 10 trend-template surfaces). v2 brief §6.1 "Universe pipeline" Phase 0 is largely closed; gaps deferred to writing-plans-phase per operator decision 2026-05-17.
- **Phase 10 metrics dashboard architecture**: 8 metric surfaces + 6 base-layout VMs. Phase 13 Theme 2 T2.SB6 outcome distributions surface composes naturally (per-pattern-class cohort metrics).
- **Phase 12 Sub-bundle B + post-Phase-12 Sub-bundle 1 Schwab integration discipline**: `apply_overrides(cfg)` cascade at Schwab entry points; `construct_authenticated_client` 4-arg signature; cassette infrastructure with `before_record_request` URI/path sanitization + `before_record_response` body sanitization; `surface='cli'` / `surface='pipeline'` / `surface='trade_entry'` enum widening pattern.

### §1.4 Apply existing DROP rules

Inherits from prior phases — no new DROP rules unique to Phase 13:

- **No magnitude-based threshold** (Sub-bundle C §1.1 lock #3 inheritance; brief §5.1 weaknesses → mitigated via tolerance bands).
- **No retroactive audit-row rewriting** (Phase 12 Sub-bundle C §1.1 lock #4 inheritance; OQ-G inheritance).
- **No re-litigating operator-locked §0.5 decisions** (DO NOT re-open 4 themes / 10 sub-bundles / 11 design locks).
- **No run-time AI inferencing** (§1.1 lock #1; permanently out of scope).
- **No sell-side detector** (§1.1 lock #3; Phase 14 banked).
- **No ML re-ranker** (§1.1 lock #4; indefinitely deferred).
- **No drift detection monitoring/dashboard side** (§1.1 lock #5; Phase 13.5 banked; Phase 13 ONLY bakes in LOGGING side).
- **No multi-cohort architectural deepening** (Phase 14+ candidate; single-strategy SEPA+DST focus).
- **No image-based CV** (v2 brief §5.6 permanently out of scope; interpretability violation).
- **No sequence transformers** (v2 brief §5.7 permanently out of scope).
- **No harmonic / candlestick / intraday patterns** (v2 brief §4.4 permanently out of scope).
- **No fixed-window pattern detection** (v2 brief §3 — variable-window candidate generator with anchor-point search; VCP-style patterns have variable durations).

### §1.5 Sub-bundle decomposition expectation (LOCKED per `docs/phase13-scope-brainstorm.md` §0.5.2)

10 sub-bundles in dispatch sequence:

| SB | Theme | Scope summary |
|---|---|---|
| T2.SB1 | Theme 2 | Dev-time labeling infra + exemplar bootstrap; `pattern_exemplars` schema with silver/gold tagging |
| T3.SB1 | Theme 3 | Entry auto-fill (Schwab Trader API at trade-entry handler); CONCURRENT with T2.SB1 |
| T2.SB2 | Theme 2 | Foundation primitives: smoothing + extrema + zigzag + candidate-window generator |
| T2.SB3 | Theme 2 | Detectors batch 1: VCP + flat base + cup-with-handle |
| T3.SB2 | Theme 3 | Exit auto-fill (Schwab Trader API exit fill detection) |
| T2.SB4 | Theme 2 | Detectors batch 2: high-tight-flag + double-bottom-W |
| T2.SB5 | Theme 2 | Template matching layer (DTW Sakoe-Chiba OR shape-based distance) |
| T3.SB3 | Theme 3 | Review auto-fill (priors from previous reviews + MFE/MAE from candles + period review section text) |
| T2.SB6 | Theme 2 + Theme 1 | Closed-loop surface + annotated chart deepening (Theme 1 lands here); outcome distributions per pattern_class cohort |
| T4.SB | Theme 4 | Usability triage closer; operator-elicited list |

Brainstorm refines this decomposition + locks per-sub-bundle scope + identifies cross-sub-bundle dependencies + projects test deltas + projects line counts. Brainstorm should NOT re-litigate the SUB-BUNDLE COUNT or HIGH-LEVEL THEMES — just refine within.

### §1.6 Out-of-scope candidates (DO NOT design)

- **Sell-side detector module** (Phase 14; v2 brief §4.3 + §10 Phase 8)
- **ML re-ranker** (indefinitely deferred per v2 brief §16.6 + operator decision; gates G1-G7 in v2 brief §16.5)
- **Drift detection monitoring/dashboard side** (Phase 13.5; v2 brief §14)
- **Matrix Profile-based exemplar retrieval at scale** (Phase 14+; v2 brief §5.8 + §10 Phase 7)
- **Shapelet-based detection** (Phase 14+; v2 brief §5.9)
- **Web Tier-2 discrepancy-resolution surface** (Phase 12.5 #2; ships pre-Phase-13)
- **CLAUDE.md + orchestrator-context maintenance pass** (Phase 12.5 #3; ships pre-Phase-13)
- **OQ-F multi-leg tier-1 auto-redirect** (Phase 12.5 #1; ships pre-Phase-13)
- **Intraday / live-trading integration** (Phase 14+ candidate)
- **Tax-lot accounting** (Phase 14+ candidate)
- **Multi-cohort architectural deepening** (Phase 14+ candidate)
- **Branch A research-branch activation** (Phase 0 study harness + first promotion package; deferred per operator 100% operational decision)
- **Harmonic + candlestick + intraday + image CV + sequence transformer patterns** (v2 brief §4.4 + §5.6 + §5.7 permanently out of scope)

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/2026-05-17-phase13-design.md` covering §2.1-§2.5 below.

### §2.1 Theme 1 — Chart rendering deepening

For each chart surface proposed:

- **Surface name + audience** (e.g., watchlist row chart; hyp-rec detail page chart; active position detail page chart; market weather mini-chart on dashboard).
- **Rendering technology** (matplotlib SVG inline per Phase 10 §A.10 LOCK avoiding mathtext gotcha; OR HTMX-driven client-side JS chart library — brainstorm decides; recommend SVG inline for V1 with V2 candidate to upgrade to interactive client-side).
- **Chart content per surface**: timeframe (daily primary + weekly confirmation per v2 brief §3); indicators (MA50/MA150/MA200; volume bars; RS rank surface); annotations (pattern boundaries from Theme 2 output; pivot point; trigger + stop lines; entry/exit fill markers for active positions).
- **Cache architecture** — render-on-demand vs pre-rendered cache. If cached: new `chart_renders` table OR file-based cache OR existing OhlcvCache extension. Staleness rules (regenerate per-pipeline-run? per-data-asof-date check?).
- **Performance + quota budget** — N charts per dashboard load; lazy-load vs eager render; pagination.
- **Annotated chart deliverable** for Theme 2 (T2.SB6 closed-loop surface) — what annotations the chart shows for a confirmed VCP candidate (contraction markers per v2 brief §5.1 illustrative criteria; volume profile; pivot point; trend-template state surface; top-3 nearest historical bases overlay).
- **Market weather trend mini-chart on dashboard** — what shows (S&P 500? Sector breadth? Daily/weekly?); placement (dashboard top? Sidebar?); update cadence (per-pipeline-run? On-demand?).

Likely shape (brainstorm refines):
- `chart_renders` cache table with `(ticker, surface, render_at, chart_svg_bytes, source_data_hash)` shape; staleness via `source_data_hash` invalidation when OHLCV cache mtime changes.
- Existing matplotlib SVG inline pattern (Phase 10 §A.10) extended to support new surfaces.

### §2.2 Theme 2 — Pattern recognition deepening (anchored on v2 brief)

Mirror v2 brief's structure for the 5 buy-side patterns + foundation + template matching + closed-loop surface. Per v2 brief §10 Phase 0-4 roadmap.

For each pattern (VCP + flat base + cup-with-handle + high-tight-flag + double-bottom-W):

- **Rule-based geometric criteria** per v2 brief §5.1 illustrative VCP criteria precedent. Hand-tuned thresholds with tolerance bands.
- **Input substrate** — daily primary + weekly confirmation per v2 brief §3.
- **Foundation primitives** — smoothing (per v2 brief §5.2; recommend kernel regression OR EMA with documented tradeoffs); extrema extraction (per v2 brief §5.2; recommend zigzag adaptive percentage threshold for VCP-style patterns).
- **Composite scoring** — rule-tier geometric score + template-match score → composite per v2 brief §17 item 7.
- **Output contract** — `pattern_class` + `confidence` + `structural_evidence` (per v2 brief §1 introspection HARD constraint; evidence is OPERATOR-FACING + AUDITABLE per V2.1 §VI.C).

For the dev-time labeling infrastructure:

- **`pattern_exemplars` library table** schema per v2 brief §6.4 label schema; widened with `label_source` enum + `ai_labeler_version` tracking + `gold_validated_at` + `codex_reviewed` + `codex_agreement`.
- **AI-assisted labeling pipeline** per v2 brief §8.2 — Claude Code subagent dispatch consumes candidate window + emits silver label per `§6.4` shape; spot-check 10-20% routes to Codex 2nd reviewer per operator-locked SELECTIVE policy.
- **Operator mid-dispatch pause for exemplar bootstrap** — implementer ships dev-time labeling infra + recording-script + sanitization filter; operator runs labeling against historical universe → spot-checks → commits exemplar corpus to worktree branch → signals resume → implementer continues with detector builds consuming the corpus. Pattern mirrors post-Phase-12 Sub-bundle 1 cassette session precedent.

For the template matching layer (v2 brief §5.3):

- **Distance/similarity method** — brainstorm picks between DTW (with Sakoe-Chiba band per v2 brief §5.3 DTW caveat) OR shape-based distance (SBD) OR feature-vector distance.
- **Retrieval modes** — forward + reverse per v2 brief §5.3.
- **Composition with rule-based detector** — composite scoring per v2 brief §17 item 7.

For the closed-loop surface (v2 brief §9.2 + §13.2):

- **Evidence shown to reviewer** per v2 brief §9.2 8-item checklist.
- **Outcome distribution surfaced** — "of the last 20 VCPs flagged with similar scores, X% triggered, Y% reached 1R, Z% hit stop" composes with Phase 10 metrics cohort architecture.
- **Reviewer decision types** per v2 brief §9.3 6-decision-type enum.
- **Active learning prioritization** per v2 brief §9.4 4-priority axis.

### §2.3 Theme 3 — Auto-fill deepening across entries / exits / reviews

For each auto-fill surface:

- **Entry auto-fill (T3.SB1)** — trade entry form pre-populates fields from Schwab Trader API at form-render time. Composes with Sub-bundle 1 mapper widening (execution-grain data now available). Operator-typed-from-memory deviation flagged via `fill_origin` enum (e.g., `'schwab_auto'` vs `'operator_typed'` vs `'operator_corrected'`).
- **Exit auto-fill (T3.SB2)** — currently operator-types-from-memory at exit form. Schwab Trader API exit fill detection at form-render time; same `fill_origin` discipline.
- **Review auto-fill (T3.SB3)** — trade review form pre-populates priors from previous reviews + MFE/MAE from candle data. Composes with Phase 6 review_log + Phase 8 daily_management_records.
- **Period review auto-fill** — section text auto-fill from prior reviews (period reviews currently operator-types-from-memory).
- **Audit columns** — when auto-fill was used, original Schwab-source value, operator-corrected value if any. Forensically honest about provenance.

### §2.4 Theme 4 — Usability triage pass

Operator drafts the unreported-usability-issues list at brainstorm time as one of the brainstorm spec inputs. Brainstorm captures the list in §2.4 verbatim + classifies each issue by category (form-input ergonomics / display rendering / navigation flow / data freshness / etc.) + sizes each issue.

T4.SB closer Sub-bundle implements the list as polish per Phase 9 Sub-bundle E + Phase 10 Sub-bundle E closer precedent.

### §2.5 Sub-bundle decomposition refinement + dispatch sequence

Brainstorm refines the 10-sub-bundle decomposition locked at §1.5. Per-sub-bundle:
- Scope locked at task-grain (writing-plans does per-task acceptance criteria).
- Cross-sub-bundle dependencies enumerated (e.g., T2.SB3 detectors require T2.SB1 dev-time labeling infra + T2.SB2 foundation primitives).
- Projected test deltas (per Sub-bundle 1 + Sub-bundle C precedent: +40-100 tests per sub-bundle).
- Projected schema deltas (v20 confirmed; per-sub-bundle decomposition TBD).

### §2.6 Open questions for orchestrator triage

Per v2 brief format. Likely categories:

- **OQ-1** — Chart rendering technology: matplotlib SVG inline V1 vs HTMX client-side JS V2 (recommend SVG inline V1 per Phase 10 LOCK).
- **OQ-2** — Cache architecture for chart renders: new `chart_renders` table vs file-based cache vs OhlcvCache extension.
- **OQ-3** — `pattern_class` CHECK enum scope: 5 values for V1 buy-side ('VCP' / 'flat_base' / 'cup_with_handle' / 'high_tight_flag' / 'double_bottom_w') vs reserve sell-side values for Phase 14 (e.g., 'head_and_shoulders_top' / 'climax_run' / 'stage_4_breakdown' / 'ma50_violation' / 'ma200_violation').
- **OQ-4** — Template matching distance metric: DTW with Sakoe-Chiba band vs SBD vs feature-vector distance.
- **OQ-5** — Codex 2nd reviewer SELECTIVE policy definition: when exactly does Codex review fire? (Threshold for "high-stakes individual labels"; spot-check 10-20% sample selection method.)
- **OQ-6** — Operator-paired mid-dispatch exemplar bootstrap workflow: same shape as Sub-bundle 1 cassette session (T2.SB1 ships labeling infra; operator runs labeling; operator signals resume; T2.SB2+ continues)? OR variation?
- **OQ-7** — Theme 3 `fill_origin` enum values + schema impact (new column on `fills` vs new table).
- **OQ-8** — Theme 3 review auto-fill MFE/MAE candle-data source: yfinance vs Schwab Market Data API vs OhlcvCache vs computed-from-fills-and-current-price.
- **OQ-9** — Drift logging side at Theme 2 Sub-bundles: what feature distributions captured per detector run? `feature_log` table OR JSON in `pattern_evaluations`?
- **OQ-10** — Closed-loop surface T2.SB6 — does it ship as a new Phase 10 metric surface, OR a new `/patterns/{candidate_id}` route group, OR widening existing hyp-rec detail page?

Brainstorm picks each OQ + locks + provides recommendation rationale.

---

## §3 OUT OF SCOPE (do not do)

- **Migration SQL drafting** — that's writing-plans territory. Schema SKETCHES (column lists + CHECK semantics) are in scope; full `CREATE TABLE` SQL is not.
- **Code drafting** — service modules, view-models, query implementations, Jinja templates, route handlers, repo functions, CLI command bodies. Spec is design-only.
- **Sub-bundle task-decomposition into per-task acceptance criteria** — writing-plans output. Sub-bundle high-level scope is in §2.5 brainstorm-output; per-task decomposition is downstream.
- **Re-litigating §1 + §0.5 binding constraints** — accepted as given. Operator-locked.
- **Sell-side detector** (§1.6 lock; Phase 14)
- **ML re-ranker** (§1.6 lock; indefinitely deferred)
- **Drift detection monitoring side** (§1.6 lock; Phase 13.5)
- **Other §1.6 banked items**
- **Phase 12.5 items** (OQ-F multi-leg auto-redirect + web Tier-2 + CLAUDE.md maintenance pass — ship pre-Phase-13)
- **Re-deriving forward-binding lessons** — accept ~60 cumulative as given.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 9/10/12 brainstorm precedent if Codex finds substantive issues.
- **Commit message:** `docs(phase13): Phase 13 charts + pattern recognition + auto-fill + usability brainstorm spec`. **NO Claude co-author footer.** This is a CLAUDE.md binding convention. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) — do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. C.B R1 fix-bundle 4 commits carried the footer accidentally + required orchestrator-side rebase-strip pre-merge; C.C + C.D + post-Phase-12 brainstorm + writing-plans chains' explicit citation produced ZERO footer drift across 23 + 33 + 6 + 2 commits respectively — pattern is DURABLE. **This brainstorm MUST NOT regress.**
- No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (post-Phase-12 brainstorm canonical; 1086 lines + ZERO ACCEPT-WITH-RATIONALE + 5 Codex rounds + Shape C emergence pattern + Pass-1-only LIFT pattern). Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage with tentative recommendations.
- **Spec line target:** ~1500-2200 lines (LARGER than post-Phase-12 brainstorm 1086 lines because Phase 13 has 4 themes + 10 sub-bundles + closed-loop architecture detail; SMALLER than Phase 12 Sub-bundle C 1444 lines per theme — Phase 13 is breadth not depth-per-theme).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget **5-9 rounds** (matches Phase 12 Sub-bundle C 9-substantive-round chain; convergent chain expected per Phase 7/8/9 lesson family).
- **Schema sketches use simplified syntax** — column-name + type + CHECK descriptor + FK target, NOT full DDL.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **§1.1 11 operator-locked decisions integrity.** Spec respects all 11. If any spec recommendation appears to weaken these, flag for orchestrator — do NOT relax in spec.
2. **v2 brief §1 introspection HARD constraint preserved.** Every detector + every classifier + every template-match output has operator-facing + auditable evidence. Black-box outputs (e.g., un-interpretable composite scores) rejected.
3. **5 buy-side pattern coverage end-to-end.** Each of VCP + flat base + cup-with-handle + high-tight-flag + double-bottom-W has rule-based geometric criteria + foundation primitives + composite scoring + structural evidence definition. Coverage check: does spec address all 5?
4. **Sell-side scope-banking respected.** No spec section designs H&S top / climax run / Stage 4 breakdown / MA50/MA200 violations. Any sell-side reference is informational only (e.g., banked as Phase 14 candidate; rule structure for future reference).
5. **ML re-ranker scope-banking respected.** No spec section designs a small ML model for production inference. AI-assisted labeling is DEV-TIME-ONLY per §1.1 lock #1.
6. **Drift detection logging side IN SCOPE, monitoring side OUT OF SCOPE.** Spec includes feature-distribution-logging discipline at Theme 2 detectors (so Phase 13.5 has baseline material) but does NOT design dashboard surfaces for drift monitoring.
7. **Schema appetite bounded.** v20 confirmed; v21+ flagged per theme. Spec does NOT propose new tables / columns beyond what each theme demands. Brief enumeration of v20 deltas vs v21+ candidates.
8. **Closed-loop surface T2.SB6 integration with Phase 10 metrics.** Outcome distributions per pattern_class cohort compose with Phase 10 cohort architecture; do NOT propose Phase-10-replacing surface.
9. **Theme 1 + Theme 2 coupling at T2.SB6.** Annotated charts ARE the Theme 1 deliverable AND the Theme 2 §9.2 evidence-display deliverable. Brainstorm explicitly addresses how the two themes share T2.SB6 implementation.
10. **`construct_authenticated_client` 4-arg signature discipline** (writing-plans forward-binding lesson #1 from post-Phase-12) — every new Schwab API consumer (T3.SB1 entry auto-fill; T3.SB2 exit auto-fill; potentially T2.SB1 dev-time labeling if it touches Schwab) MUST resolve credentials via `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` BEFORE invoking the helper.
11. **vcrpy URI/path sanitization** (post-Phase-12 forward-binding lesson #2) — any new cassette infrastructure (Theme 2 detector exemplar cassettes? Theme 3 entry-fill cassettes?) MUST install BOTH `before_record_request` (URI/path) AND `before_record_response` (body) filters.
12. **Standalone recording scripts** (post-Phase-12 forward-binding lesson #3) — when cassettes must exist before consumer test code, prefer standalone recording script over `@pytest.mark.vcr(record_mode='new_episodes')`.
13. **HTMX gotcha trinity preservation** — Theme 1 dashboard surface + Theme 3 auto-fill form surfaces inherit HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted disciplines.
14. **Base-layout VM banner pin** — every new VM extending `base.html.j2` populates `unresolved_material_discrepancies_count` (Phase 10 Sub-bundle E T-E.3 + Phase 12 Sub-bundle C.D banner predicate widening inheritance).
15. **Session-anchor read/write mismatch family** — forward-looking `action_session_for_run` vs backward-looking `last_completed_session` for any new session-keyed surface (e.g., chart cache staleness check; auto-fill data-source freshness).
16. **Pre-emptive Codex round count.** Budget 5-9 rounds; if Codex converges early (e.g., 3 rounds), that's a sign architecture absorbed adequately at v2 brief authoring time. If Codex stalls past 9 rounds, orchestrator-override pattern (Phase 10 writing-plans precedent + post-Phase-12 writing-plans precedent) is acceptable but flag explicitly in return report.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/2026-05-17-phase13-design.md` covering §2.1-§2.6.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format (post-Phase-12 spec canonical).
4. Each of the 5 buy-side patterns walked through end-to-end as discriminating examples (rule criteria + composite scoring + structural evidence).
5. Each of the 10 OQs (OQ-1 through OQ-10) addressed with recommendation-with-rationale + binding-vs-deferrable disposition.
6. Sub-bundle decomposition refinement in §2.5 (10 sub-bundles per §1.5 LOCK + per-sub-bundle scope + cross-sub-bundle dependencies + test/schema projections).
7. Theme 4 usability list captured in §2.4 verbatim from operator (orchestrator routes operator-elicited list into brainstorm via dispatch prompt OR brainstorm prompts operator at session start).
8. Single commit OR landing+fixes split: `docs(phase13): Phase 13 charts + pattern recognition + auto-fill + usability brainstorm spec` (+ optional `docs(phase13): brainstorm spec — Codex R1-R<N> fixes`).
9. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 13 brainstorm

### Spec location
`docs/superpowers/specs/2026-05-17-phase13-design.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase13): Phase 13 charts + pattern recognition + auto-fill + usability brainstorm spec` (initial)
- (optional) {sha} `docs(phase13): brainstorm spec — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Theme 1 chart rendering decisions
Locked: rendering tech + cache architecture + market weather mini-chart shape + chart content per surface.
Rationale: ...

### Theme 2 pattern recognition decisions
Locked per pattern: rule criteria + composite scoring + structural evidence. Locked overall: dev-time labeling infra + template matching method + closed-loop surface shape.
Rationale: ...

### Theme 3 auto-fill decisions
Locked: entry + exit + review + period review auto-fill mechanisms. Locked: fill_origin enum widening + audit columns.
Rationale: ...

### Theme 4 usability list captured
[Verbatim from operator; classified by category + sized per issue]

### Sub-bundle decomposition refinement (per §2.5)
Locked: per-sub-bundle scope at task-grain + cross-sub-bundle dependencies + test/schema projections.

### Open questions for orchestrator triage
[Per OQ-1 through OQ-10 brainstorm dispositions]

### Capture-needs feedback FOR PHASE 13 WRITING-PLANS
- ...

### Outstanding capture-needs that DEFER to Phase 13.5 / Phase 14
- ...
```

---

## §8 If you get stuck

- If §1 + §0.5 binding constraints conflict with Codex finding, §1 + §0.5 win; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~2200 lines, re-scope.
- DO NOT propose migration SQL. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class PatternDetector`, stop.
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A/12-C-B/12-C-C/12-C-D/post-Phase-12 lesson that conflicts with a Phase 13 design proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a design constraint.
- If you find yourself proposing sell-side patterns OR ML re-ranker OR drift monitoring OR multi-cohort architectural deepening, STOP — §1.6 lock violated.
- If you find yourself proposing run-time AI inferencing (Claude API at pipeline run-time), STOP — §1.1 lock #1 violated.
- If you find yourself proposing a magnitude-based pattern-detection threshold, STOP — v2 brief §5.1 weakness; use tolerance bands.
- If v2 brief and §1 disagree on any architectural decision, **operator-locked §1 wins** (operator scope-conversation 2026-05-17 supersedes v2 brief authoring 2026-05-08).
- Operator-elicited usability list (Theme 4) MUST be captured verbatim from operator. If operator did not provide the list at dispatch time, prompt at brainstorm session start. Do NOT enumerate usability issues from your own analysis — operator owns the list.
- Codex 2nd reviewer SELECTIVE policy (OQ-5) — brainstorm defines the policy + spot-check sample selection method; writing-plans operationalizes. Do NOT propose blanket Codex review of every silver label (operator-locked decision §1.1 #9).

---

*End of brief. 4-theme architectural arc (Charts + Pattern Recognition + Auto-fill + Usability). 10 sub-bundles locked per §1.5. Spec output target: `docs/superpowers/specs/2026-05-17-phase13-design.md`. Expected 150-300 minutes brainstorm + 5-9 Codex rounds. Schema v20 confirmed; major banked items (sell-side, ML re-ranker, drift monitoring) explicitly OUT of Phase 13 scope. Operator-locked decisions per §0.5 of `docs/phase13-scope-brainstorm.md` 2026-05-17.*
