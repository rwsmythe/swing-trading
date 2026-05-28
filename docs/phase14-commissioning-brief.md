# Phase 14 Commissioning Brief

**Audience:** Fresh Claude Code instance taking on the role of Phase 14 commissioning orchestrator. This brief is an ORCHESTRATOR HANDOFF, NOT an implementation prompt. Do not begin implementation. Do not draft dispatch briefs for sub-bundles before completing the operator-paired triage at Sec 9 + the per-sub-bundle brainstorming phase per Sec 5.

**Mission:** Commission Phase 14 -- a multi-sub-bundle phase that closes (a) the V2.G1-G4 gate findings carried over from post-Phase-13 T4.SB; (b) operator-banked UX + wiring improvements (CR.1 + P14.N1-N6); (c) the NEW temporal pattern detection + observation log infrastructure (highest-leverage methodological improvement surfaced at the close of the applied research arc per Turn H 2026-05-27 PM #3 substantive synthesis).

**Phase 14 is now COMMISSIONED.** Prior deferral (locked at 2026-05-23 PM per `docs/phase13-closer-next-phase-triage.md`) is CLEARED per operator decision 2026-05-27 PM #3 post G2 SHIPPED.

**Workflow expectation:** Phase 14 will likely require MULTIPLE copowers cycles (one per sub-bundle), NOT a single mega-dispatch. Each sub-bundle: `copowers:brainstorming` -> `copowers:writing-plans` -> `copowers:executing-plans`. Sub-bundle sequencing is operator-paired at Sec 9.

**Main HEAD at commissioning:** `e1a4bdf` (gotcha #37 banked post-G2 SHIPPED).

**Cumulative discipline at commissioning:** 37 CLAUDE.md gotchas BINDING; ~580+ cumulative ZERO Co-Authored-By trailer drift; 44th cumulative C.C lesson #6 validation NOTABLE (Codex two-chain pattern VALIDATED at G2); Schema v21 LOCKED; L2 LOCK (zero new Schwab API calls beyond OQ-13 carve-outs) preserved through 12 applied research arcs to date.

---

## Sec 0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase3e-todo.md`** -- the cross-phase operational backlog. Especially:
   - **2026-05-27 PM #2 Phase 14 preliminary scope roll-up** (operator-authored Turn H parallel instance) -- the CANONICAL Phase 14 scope table with CR.1 + V2.G1-G4 + P14.N1-N6 items + sub-bundle decomposition + cross-cutting watch items
   - **2026-05-27 PM #3 Turn H G2 SHIPPED entry** -- substrate-freshness candidate gotcha #37 (now BANKED at `e1a4bdf`); applied research arc closure synthesis (NO ruleset deployment justified by arc evidence)
   - **2026-05-27 PM operator-identified operational backlog** -- closeout review surface enhancement (CR.1; details below the table)
   - **2026-05-26 PM Turn H V2-mechanic SHIPPED entry** + earlier R2-A + R2-D entries for cumulative methodology context

3. **`CLAUDE.md`** (entire file) -- especially:
   - The "Current state" massive paragraph at line 3 (Applied Research Tranche 1 + V2 evaluator + Phase 13 closure context)
   - All 37 cumulative gotchas at the bottom; gotcha #36 (two-Codex-chain default) + gotcha #37 (substrate-freshness sensitivity) are the most recent BINDING items
   - "Invariants" + "Conventions" + "Gotchas" sections

4. **`docs/phase13-closer-next-phase-triage.md`** -- the deferred-Phase-14 decision document. This brief CLEARS the deferral; the triage doc is reference for the historical rationale + cross-cohort robustness rubric.

5. **`docs/orchestrator-context.md`** -- durable orchestrator-role bootstrap context. Read for project-specific framing, processes, in-flight state.

6. **G2 arc artifacts** for substantive context on the applied research arc close-out:
   - `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md` (Sec 1 headline finding; Sec 6 hypothesis assessment)
   - `docs/g2-w-bottom-ruleset-backtest-return-report.md`
   - `research/studies/2026-05-26-v2-selection-mechanic-analysis.md` (V2-mechanic study writeup; per-ticker enrichment finding)
   - `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/` (smoke artifact)

7. **`docs/superpowers/specs/`** + **`docs/superpowers/plans/`** -- per-phase design docs for prior phases; the canonical superpowers brainstorming + writing-plans + executing-plans artifact location. Phase 14 will produce specs + plans here per sub-bundle.

8. **The `memory/` directory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\` -- durable auto-memory; especially:
   - `feedback_orchestrator_qa_implementer_product` (QA against reality on disk before merge)
   - `feedback_orchestrator_performs_merge` (orchestrator owns merge + push + housekeeping)
   - `feedback_commit_brief_before_inline_prompt` (commit brief, THEN provide inline prompt)
   - `feedback_always_provide_inline_dispatch_prompt` (every brief gets an inline prompt for operator paste)
   - `feedback_pause_means_pause` (pause for implementer ship; no preemptive action)
   - `feedback_handoff_briefs_only_when_context_actually_exhausting` (handoff briefs only when <30% context)
   - `feedback_verify_regression_test_arithmetic` (compute test arithmetic both pre/post-fix)
   - `feedback_worktree_cli_invocation` -- `python -m swing.cli` (NOT bare `swing`)
   - `feedback_orchestrator_vs_implementer_execution` (default to implementer-dispatch)
   - `project_capital_risk_floor` (capital floor = max($7500, actual balance); current actual ~$1300)
   - `project_phase13_t4_sb_pause_for_list_additions` (precedent for accumulating scope before commissioning)

---

## Sec 1 Phase 14 mission + scope summary

Phase 14 is a UX + wiring + methodological-infrastructure phase. It is **NOT a ruleset deployment phase**: the applied research arc (D1 -> D2 -> R2-A -> R2-D -> V2-mechanic -> G2) closed with the operator-validated synthesis that NO tested ruleset (A through I; 9 rulesets across 4 substrates) produces robust positive expectancy at current substrate scale. Phase 14 does NOT include any work bundle that modifies production trade-management rules based on the applied research arc evidence.

Phase 14 DOES include:

| Sub-bundle | Scope | Source |
|---|---|---|
| **Chart-surface uniformity** | V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 (candlestick discipline + thumbnail surfaces + chart annotation legends) | phase3e-todo PM #2 roll-up |
| **Data-wiring** | V2.G3 + V2.G4 + P14.N3 (Sector/Industry persistence + SPY weather fetch + Capital % PROVISIONAL flag explanation) | phase3e-todo PM #2 roll-up |
| **Review + journal UX** | CR.1 (closeout review exit data + chart snapshot) + P14.N6 (journal page redesign) | phase3e-todo PM #2 roll-up + Turn H operator feedback 2026-05-27 PM |
| **Metrics overview** | P14.N5 (metrics overview dashboard + graphics-driven surfaces) | phase3e-todo PM #2 roll-up |
| **Temporal pattern detection + observation log infrastructure** (NEW addition for Phase 14) | Append-only pattern_detection_events + pattern_forward_observations tables + `_step_pattern_observe` pipeline step + per-pattern metadata enrichment at detection time | Operator decision 2026-05-27 PM #3 (this commissioning) |

Phase 14 does NOT include (DEFERRED to Phase 15+ or to operator-paired future commissioning):

- Substrate-size augmentation experiment (applied research arc; depends on temporal log accumulation)
- Finviz filter widening investigation (applied research arc; coupled with temporal log + market-regime work)
- Cohort-stability LOCK at fixture-write time (gotcha #37 V2 candidate; lower-priority than temporal log)
- D2 baseline canonical_survival_rate L4 remediation (small effort; could fold into temporal log work-bundle if convenient)
- Any ruleset deployment work (NO justification per applied research arc closure)
- Phase 15 commissioning scope (not yet enumerated)

---

## Sec 2 Items in scope (detailed pointers)

### Sec 2.1 Chart-surface uniformity sub-bundle

Five line items in phase3e-todo PM #2 roll-up: V2.G1, V2.G2, P14.N1, P14.N2, P14.N4. Read each detail block (5-field template) for full context.

**Key architectural notes:**
- Cumulative gotcha #11 + Expansion #10 sub-discipline (c) renderer-kwargs uniformity LOCK applies; cache-collision discriminating tests at `chart_renders` surface enum
- V2.G2 rename `hyprec_detail` -> `ticker_detail` is a v22 schema migration -- backup-gate equality form per gotcha #11 LOCK applies
- P14.N2 candlestick discipline likely subsumes V2.G1 -- single renderer-uniformity audit closes both
- BULZ green/yellow shaded region (P14.N4) is likely entry-stop-target zones; investigate `axhspan` / `axvspan` / `fill_between` in `render_position_detail_svg`
- All chart-render surfaces under `swing/web/charts.py` + `swing/web/chart_jit.py` + 4 render functions enumerated at P14.N2 detail block

**Likely workflow:** single `copowers:brainstorming` -> `copowers:writing-plans` -> `copowers:executing-plans` cycle since the five items cohere around the same chart_renders + chart_jit substrate. Estimated scope: ~15-25 commits + ~40-80 tests; v22 schema migration; non-trivial.

### Sec 2.2 Data-wiring sub-bundle

Three line items: V2.G3, V2.G4, P14.N3. Cohere around persistence + JOIN + cfg-resolution debugging.

**Key architectural notes:**
- V2.G3 VSAT Sector/Industry loss is same gotcha family as PriceCache `_last_close` ticker-rotation -- likely a candidates-table-vs-finviz-CSV join semantic issue
- V2.G4 SPY weather post-pipeline failure may share root cause with V2.G1 (chart-render path divergence) OR be a distinct OHLCV cache miss; investigation at brainstorming phase
- P14.N3 Capital % PROVISIONAL flag is likely a daily_management_records state machine surface; investigate flip-condition via `Grep "PROVISIONAL"` in `swing/`

**Likely workflow:** single copowers cycle; smaller scope than chart-surface bundle. Estimated ~8-15 commits + ~25-50 tests.

### Sec 2.3 Review + journal UX sub-bundle

Two line items: CR.1 + P14.N6. Cohere around per-trade close-the-loop workflow.

**Key architectural notes:**
- CR.1 closeout review extends Phase 13 T2.SB6 `chart_renders` substrate; surfaces exit data + chart snapshot at the per-trade review surface; couples with operator failure-mode classification (Tier 4 in Turn H forward recommendations)
- P14.N6 journal page redesign is the LARGEST single item in Phase 14 scope; comprehensive database-browsing surface with rich trade rows + clickable drill-down + annotated full chart + small thumbnails
- BOTH items likely require small-chart integration per P14.N1 (chart-surface uniformity bundle dependency)

**Likely workflow:** single copowers cycle; P14.N6 is large enough that the writing-plans phase may sub-decompose into 2-3 commits-worth of slices. Estimated ~20-35 commits + ~50-100 tests. **Order this AFTER chart-surface uniformity bundle** since both CR.1 + P14.N6 consume the thumbnail-rendering substrate.

### Sec 2.4 Metrics overview sub-bundle

Single line item: P14.N5. Standalone scope.

**Key architectural notes:**
- New `/metrics` index route with overview cards summarizing the 9 existing metric surfaces
- Each card shows sparkline / mini-chart graphics rather than pure text
- Graphics library decision at brainstorming: matplotlib SVG (consistent with existing chart_renders) vs JS-based charting (new dependency)
- Couples with P14.N6 at the visualization-library decision point -- recommend resolving at the FIRST sub-bundle to touch graphics

**Likely workflow:** single copowers cycle; potentially sub-decomposed at writing-plans phase (overview substrate first; per-surface card extensions follow). Estimated ~10-20 commits + ~25-50 tests.

### Sec 2.5 Temporal pattern detection + observation log infrastructure (NEW; HIGHEST METHODOLOGICAL LEVERAGE)

**This is the most substantive Phase 14 addition** and is the primary forward-looking benefit for future applied research investigations. Substantive context lives in the Turn H session's forward-recommendations response (operator query 2026-05-27 PM #3 "Are there any changes that we can make to improve the overall quality of the next investigation?"). The recommendation:

**Architectural primitive: append-only pattern detection log + observation log.**

```
pattern_detection_events
  detection_id PK
  ticker
  detection_date          (= asof_date at which the pattern was identified)
  pattern_class           (double_bottom_w / cup_with_handle / vcp / etc.)
  structural_anchors_json (trough_1_date, center_peak_date, etc. -- LOCKED at detection)
  composite_score         (LOCKED at detection)
  finviz_screen_state     (which Finviz criteria the ticker passed at detection)
  source                  ('pipeline' / 'V2_cohort' / 'D2_baseline' / etc.)
  per_pattern_metadata    (sector / industry / market_cap / ATR_pct / 90d_return / 52w_prox at detection time; LOCKED)

pattern_forward_observations
  observation_id PK
  detection_id FK -> pattern_detection_events
  observation_date
  ohlc_today              (locked at observation; never re-fetched)
  status                  ('pending' / 'triggered_open' / 'triggered_closed_*' / 'invalidated')
  status_change_event     (entry_fired / stop_fired / target_fired / etc.)
```

**Key properties (eliminates gotchas #26 + #37 by construction):**
- Append-only; once a detection event is recorded with its `structural_anchors_json` + `composite_score`, those values are LOCKED
- Forward-walk, not back-walk; each daily pipeline run records THAT DAY's bar; no archive re-fetch possible -> gotcha #26 eliminated
- No regeneration; the detection log accumulates indefinitely; never regenerated from current state -> gotcha #37 eliminated
- Backtest = replay; future investigations replay the observation log against ruleset definitions; deterministic; reproducible
- Substrate grows organically; each day's Finviz screen produces a new batch of candidates; multi-month accumulation routinely surfaces N>=200+ patterns enabling robust statistical defensibility

**Daily pipeline integration:**
- `_step_pattern_detect` (Phase 13; already exists) -> EXTEND to append rows to `pattern_detection_events`
- NEW `_step_pattern_observe` -> enumerates open patterns; appends today's bar + status change to `pattern_forward_observations`
- Both are zero-cost beyond existing detector invocations

**Schema migration v22 (or whichever next version): introduce 2 NEW tables with append-only invariants + indexes for forward observation lookups. Backup-gate equality form per gotcha #11 LOCK applies.**

**Couples with Sec 2.1 chart-surface uniformity (chart_render bytes optionally captured at detection time per CR.1 + closeout review).**

**Couples with Sec 2.3 review + journal UX (P14.N6 journal redesign consumes the temporal log to populate the database-browsing surface).**

**Likely workflow:** dedicated copowers cycle; v22 schema migration; substrate-changing work-bundle. Estimated ~15-25 commits + ~50-100 tests. Schema-CHECK + Python-constant + dataclass-validator paired discipline (gotcha #11) applies. Per-pattern metadata enrichment SHOULD include sector / industry / market-cap / ATR% / 90d-return / 52w-proximity captured at detection time (NOT reconstructed later) for future stratified analysis.

**Important V2-leveraging note:** the V2 sensitivity + V2 OHLCV evaluator infrastructure already exists in research/harness/. The temporal log work does NOT replace V2; it COMPLEMENTS it. V2 sensitivity continues to identify which thresholds would expand the A+ population. The temporal log accumulates the resulting A+ candidates' actual forward outcomes. Future investigations can then evaluate "given a V2-style threshold relaxation, do the new A+ candidates produce positive expectancy under ruleset X?" with the temporal log providing the forward-walk data instead of retroactive reconstruction.

---

## Sec 3 Sub-bundle decomposition + sequencing recommendations

Based on dependency analysis + Phase 14 scope:

**Recommended sequence (operator may override at Sec 9):**

1. **Data-wiring sub-bundle (Sec 2.2; smallest scope; unblocks P14.N3 PROVISIONAL flag explanation)** -- fastest to ship; clears 3 gate items; no downstream dependencies. ~1-2 weeks.

2. **Temporal log infrastructure sub-bundle (Sec 2.5; methodological leverage)** -- ship EARLY in Phase 14 so the log starts accumulating substrate immediately + future Phase 14 sub-bundles can reference the temporal log for any cross-feature integration. Schema v22 migration. ~2-3 weeks.

3. **Chart-surface uniformity sub-bundle (Sec 2.1; unblocks #4 + #5)** -- candlestick discipline + thumbnail surfaces + chart annotation legends. Schema v23 migration if V2.G2 rename `hyprec_detail` -> `ticker_detail` proceeds. ~2-3 weeks.

4. **Review + journal UX sub-bundle (Sec 2.3; consumes thumbnails + temporal log)** -- CR.1 closeout review + P14.N6 journal redesign. ~3-4 weeks (P14.N6 alone is large).

5. **Metrics overview sub-bundle (Sec 2.4; standalone; lowest-leverage but enumerated)** -- P14.N5 metrics overview dashboard. ~1-2 weeks.

**Total Phase 14 estimated duration:** 9-14 weeks of operator-paced work. Operator may prefer parallel sub-bundle dispatches IF the sub-bundles have low dependency overlap; but recommend serial execution to preserve cumulative discipline verification at each merge.

**Alternative sequencing (operator preference may differ):**
- Front-load chart-surface uniformity (Sec 2.1) before data-wiring (Sec 2.2) if operator prioritizes visual feedback
- Defer Sec 2.4 metrics overview to Phase 15 if Phase 14 scope feels overstuffed

---

## Sec 4 Cumulative discipline BINDING

The next orchestrator inherits ALL cumulative discipline. The complete list at commissioning:

**Cumulative gotchas (#1-#37) all BINDING.** The most recent + most relevant for Phase 14:
- **#37 (substrate-freshness sensitivity)** -- applies if ANY Phase 14 sub-bundle references prior-arc cohort fixtures (e.g., R2-A N=65, D2 EXPANDED N=42, V2-mechanic cohorts); brief MUST cite fixture SHA + filter params + source artifact SHA + regeneration-stability assertion
- **#36 (two-Codex-chain default for applied research)** -- applies to ANY analytical sub-bundle (e.g., temporal log MIGHT include analytical methodology; brainstorming will assess); does NOT apply to pure UX/wiring sub-bundles unless they include a substantive analytical artifact
- **#35 (substrate density metric disambiguation)** -- applies if any brief cites prior-arc numerical anchors
- **#34 (brief-prescription cross-table verification)** -- applies if any brief references V2 sensitivity tuples or analogous artifact-derived (parameter, threshold) pairs
- **#33 (cohort-validity-vs-verdict-criteria)** -- BANNED terminology in any narrative output; PARTIAL POSITIVE / NEGATIVE / POSITIVE forbidden
- **#32 (ASCII discipline scope clarity)** -- all NEW Python / Markdown / JSON / CSV ASCII-only; declare scope in return reports
- **#31 (narrative artifact path/fact lag)** -- post-fix sweep MANDATORY for findings docs + return reports
- **#26 (OHLCV archive bar-content TEMPORAL mutation)** -- L6-style caveat; affects any forward-walk metric on legacy archive
- **#11 (Schema-CHECK + Python-constant + dataclass-validator paired discipline)** -- applies to v22 + v23 schema migrations
- **#9 (executescript implicit COMMIT)** -- applies to migration runner discipline
- **#1 (test-count drift in plan docs)** -- trust pytest output, not plan estimates

**Streaks to preserve through Phase 14 (ZERO-tolerance):**
- ~580+ cumulative ZERO `Co-Authored-By` footer trailer drift through `e1a4bdf`
- Schema v21 unchanged baseline (v22 + v23 introductions at Phase 14 are expected schema work; ratcheted up per migration discipline)
- L2 LOCK (zero new Schwab API calls beyond OQ-13 CLI carve-outs) preserved through 12 applied research arcs to date
- ASCII discipline complete across NEW files
- gotcha #33 banned-terms LOCK across all narrative output

**The cumulative C.C lesson #6 validation count:**
- Current: 44th validation NOTABLE at G2 SHIPPED (`31fa281`)
- Phase 14 sub-bundles each consume their own validation slot
- Two-chain pattern (gotcha #36) applies per analytical sub-bundle

---

## Sec 5 Workflow expectations per sub-bundle

Each sub-bundle follows the canonical copowers cycle:

1. **`copowers:brainstorming`** -- operator-paired spec authoring; spec lives at `docs/superpowers/specs/2026-XX-XX-<sub-bundle-slug>-design.md`. Codex MCP adversarial review at the spec phase.

2. **`copowers:writing-plans`** -- implementation plan derived from spec; plan lives at `docs/superpowers/plans/2026-XX-XX-<sub-bundle-slug>-plan.md`. Codex MCP adversarial review at the plan phase.

3. **`copowers:executing-plans`** -- dispatched to implementer Claude Code instance; orchestrator drives QA against reality + merge + post-merge housekeeping. Codex MCP per gotcha #36 (TWO chains for analytical work; single chain at the orchestrator's discretion for pure-UX work that produces no substantive emitted artifact).

**Sequencing per sub-bundle:**
1. Brainstorming spec drafted + operator-paired
2. Codex MCP review on spec -> converge -> commit spec
3. Writing-plans drafted from spec
4. Codex MCP review on plan -> converge -> commit plan
5. Executing-plans dispatch to implementer
6. Implementer ships per plan; orchestrator QAs + merges + housekeeps
7. Post-merge housekeeping commits + phase3e-todo top entry

**Operator-paired decision points per sub-bundle:**
- Spec scope (what's in / out)
- Architectural choices (e.g., schema design for temporal log; graphics library for metrics overview)
- V1 simplifications + V2 candidates banking
- Sub-bundle test surface estimates
- Post-merge gotcha banking decisions

---

## Sec 6 Cross-cutting watch items (likely BINDING at each sub-bundle's brainstorming)

- **L2 LOCK** -- zero new Schwab API calls; preserve through Phase 14; parametric source-grep tests at each sub-bundle
- **V2.G2 rename `hyprec_detail` -> `ticker_detail` v22 schema migration** -- backup-gate equality form per gotcha #11; data-migration discipline for existing rows
- **Renderer-kwargs uniformity** per Expansion #10 sub-discipline (c); cache-collision discriminating tests
- **Browser-only HTMX failure surfaces** (Phase 5 R1 M1 + M2 + Phase 6 I3 trinity) for any new HTMX-driven journal / metrics / closeout-review / temporal-log surfaces; operator-witnessed browser verification gate per phase precedent
- **Cumulative gotcha set (#1-#37) BINDING** for Nth cumulative validation onwards at each sub-bundle dispatch time; pre-Codex review applies all 19+ expansion candidates
- **Append-only invariants** for temporal log tables -- discriminating tests at fixture-write time + at read time
- **Schema migration runner discipline** -- explicit BEGIN/COMMIT/ROLLBACK per gotcha #9; per gotcha #11 paired Python-constant + dataclass-validator
- **Forward-walking discipline** for temporal log -- gotchas #26 + #37 ELIMINATED BY CONSTRUCTION at design time; verify the design holds

---

## Sec 7 What this brief is NOT

- **Not an implementation prompt.** The next orchestrator drives the copowers cycle per sub-bundle; this brief is the scope handoff, not the implementation directive.
- **Not a complete plan.** The sub-bundle decomposition recommendations at Sec 3 are starting points; brainstorming will refine per operator triage.
- **Not a ruleset deployment phase.** Applied research arc closure (Turn H synthesis 2026-05-27 PM #3) established that NO tested ruleset has deployable evidence. Phase 14 does not modify production trade-management rules.
- **Not an operator-paired sub-bundle decision lock.** Sec 9 enumerates pending operator decisions; the commissioning orchestrator opens with operator pairing.

---

## Sec 8 Forward look beyond Phase 14

Phase 15 + 16+ scope is NOT enumerated at commissioning time. Likely candidates accumulating in phase3e-todo Turn H next-arc enumeration:

- Substrate-size augmentation experiment (applied research; depends on temporal log accumulation; ~3-6 months post Phase 14 start)
- Finviz filter widening investigation (applied research; couples with temporal log)
- Cohort-stability LOCK at fixture-write time (gotcha #37 V2 candidate; could fold into a future cohort-extraction maintenance arc)
- D2 baseline canonical_survival_rate L4 remediation (small effort)
- Real-time prospective tracking (D + E hybrid; banked Option C V2 candidate)
- Other-gates-not-enumerated market-conditions investigation
- Multi-pattern composite signals (W AND cup-and-handle co-occurrence; etc.)
- Operator failure-mode classification surface (extends Phase 14 CR.1; could be Phase 15 or Phase 14 final sub-bundle)

The commissioning orchestrator MAY surface Phase 15 candidates for operator triage near Phase 14 close-out but should not commission Phase 15 unilaterally.

---

## Sec 9 Operator-paired decisions for the commissioning orchestrator

The commissioning orchestrator should open with operator pairing (likely via `AskUserQuestion`) on the following decisions BEFORE drafting any sub-bundle brainstorming spec:

**Q1 -- Sub-bundle sequencing (per Sec 3):** confirm or override the recommended sequence (data-wiring -> temporal log -> chart-surface uniformity -> review + journal UX -> metrics overview).

**Q2 -- Parallel vs serial sub-bundle execution:** serial (recommended; preserves cumulative discipline verification at each merge) or parallel (faster wall-clock but higher conflict risk).

**Q3 -- Temporal log sub-bundle scope:** V1 minimum (2 tables + 1 pipeline step + per-pattern metadata enrichment); V1+ (V1 + chart_render bytes capture at detection per CR.1 coupling); V1++ (V1+ + operator failure-mode classification surface). Recommendation: V1+ since the chart_render bytes coupling is small + closes CR.1 dependency.

**Q4 -- V2.G2 schema rename scope:** ship the `hyprec_detail` -> `ticker_detail` rename as part of chart-surface uniformity sub-bundle (v23 migration; data migration for existing rows; full cumulative-discipline workflow) OR defer to a standalone maintenance arc post-Phase-14.

**Q5 -- Metrics overview graphics library:** matplotlib SVG (consistent with existing chart_renders; no new dependency) vs JS-based charting library (richer interactivity; new dependency surface). Recommend matplotlib SVG for V1; revisit at Phase 15 if interactivity becomes a need.

**Q6 -- Phase 14 close-out criteria:** when does Phase 14 ship? When all 5 sub-bundles merged? When operator-verified at the web UI? Define close-out at commissioning to prevent scope creep.

**Q7 -- Codex MCP chain count per sub-bundle:** apply gotcha #36 two-chain default to ANALYTICAL sub-bundles (temporal log methodology may qualify; brainstorming will assess); single-chain at orchestrator discretion for pure UX/wiring sub-bundles (chart-surface uniformity; data-wiring; metrics overview; review + journal UX) unless they include a substantive analytical artifact.

Operator decisions are LOCKED at commissioning + propagate through all sub-bundle dispatches; deviations require return-trip to operator.

---

*End of Phase 14 commissioning brief. Mission: close V2 gate findings + UX/wiring backlog + ship the temporal pattern detection + observation log infrastructure (the highest-leverage methodological improvement surfaced at the close of the applied research arc). 5 sub-bundles enumerated; serial sequencing recommended; ~9-14 weeks operator-paced total. 37 cumulative CLAUDE.md gotchas BINDING. ~580+ cumulative ZERO Co-Authored-By trailer drift to preserve. NOT a ruleset deployment phase. NOT an implementation prompt; the next orchestrator drives the copowers cycle per sub-bundle with operator-paired triage at Sec 9.*
