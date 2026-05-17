# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Brainstorm Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #1 brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for the OQ-F multi-leg tier-1 auto-redirect — the V2 follow-up dispatch deferred at post-Phase-12 mapper-widening spec §6.6. When Sub-bundle 1's V2 mapper exposes execution-grain data for multi-leg fills AND all legs' VWAPs align within `price_tolerance`, classifier auto-emits tier-1 (auto-correct) bypassing the operator menu's `multi_partial_vs_consolidated` ambiguity flow. Operator has pre-locked 4 high-level architectural decisions (§1 below); your job is to design the COMPLETE architectural surface around those decisions + surface remaining open questions via Codex chain.

**Brief:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (this file).

**Sequencing:** Post-Phase-12 mapper-widening arc CLOSED 2026-05-17 (Sub-bundles 1 + 1.5 + 2; integration merges `120c992` → `a7c1016` → `690aed0`). Phase 12.5 #1 (this dispatch) ships FIRST in Phase 12.5; Phase 12.5 #2 (Web Tier-2 discrepancy-resolution surface) + #3 (Project hygiene maintenance pass) follow. Phase 13 (4 themes; chart pattern recognition + auto-fill + usability) gated on Phase 12.5 close.

**Expected duration:** ~120-180 min brainstorm + 3-5 adversarial Codex rounds. Scope is narrower than Phase 12 Sub-bundle C brainstorm (which had ~9 rounds + 1444-line spec) because (a) the 4 high-level decisions are pre-locked, (b) the V1 mapper-widening spec §6.6 already enumerates 3 of the dimensions, and (c) the architectural surface is bounded — classifier widening + auto-correct handler reuse + new banner field. Spec line target: **~600-1000 lines**.

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` + adversarial Codex review.
- Output is a spec doc at `docs/superpowers/specs/<date>-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` §6.6** — OQ-F V2 LOCK deferred analysis. **THIS IS THE PRIMARY SPEC SUBSTRATE.** Spec lines 561-590 enumerate 3 of the 4 operator-decision dimensions (confidence threshold, classifier dispatch state cascade, operator UX). The 4th (handler-shape reuse) is pre-locked here per operator §1.3 below.
2. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** — Sub-bundle C brainstorm spec (1444 lines). Especially: §4 classifier sub-classifier surface (`_classify_unmatched_fill_shared` + the dispatch pattern); §5 service-layer (auto-correct service + `apply_tier2_resolution`); §6.2.1 `multi_partial_vs_consolidated` ambiguity_kind ChoiceMenu definition; §8.4 Pass-2-tier-1-FORBIDDEN policy (with Pass-1 V2-RESOLVED amendment per Sub-bundle 1 ship); §10 worked examples for `multi_partial_vs_consolidated` case (3-fill consolidated journal vs multi-leg Schwab order).
3. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §C.6 + §C.9** — `apply_tier2_resolution` handler registry + payload shape for `multi_partial_vs_consolidated` × `split_into_partials` choice. **THIS IS THE PRE-LOCKED REUSE TARGET** per operator §1.3.
4. **`swing/trades/reconciliation_classifier.py`** — current classifier module (~700 lines post-Sub-bundle 1). 10 per-discrepancy-type sub-classifiers + dispatch table at `_DISPATCH` + `ClassificationResult` `@dataclass(frozen=True)` + validator-respecting-downgrade dispatcher. Phase 12.5 #1 EXTENDS the classifier with a NEW sub-classifier branch OR widens existing `_classify_entry_price_mismatch` / `_classify_close_price_mismatch` to recognize the multi-leg auto-redirect predicate. Verify exact extension point at brainstorm time.
5. **`swing/trades/reconciliation_auto_correct.py`** — current auto-correct service. Especially `apply_tier2_resolution(discrepancy_id, choice_code, payload, resolved_by, conn, environment)` signature + the 17+1 per-(`ambiguity_kind`, `choice_code`) handler registry + sandbox short-circuit at inner function + `CorrectionResult` return shape. Phase 12.5 #1 INVOKES `apply_tier2_resolution(..., choice_code='split_into_partials', resolved_by='auto')` from the classifier dispatch path (NOT from operator CLI).
6. **`swing/trades/reconciliation_ambiguity_choices.py`** — `multi_partial_vs_consolidated` ChoiceMenu definition. `split_into_partials` is one of 4 choices; carries `recommended=False` for V1 (operator's `keep_journal_as_is` is recommended). Brainstorm decides: does Phase 12.5 #1 change the `recommended` flag when auto-redirect fires? OR is the menu untouched (auto-redirect bypasses the menu entirely)?
7. **`swing/integrations/schwab/models.py`** — `SchwabExecutionLeg` dataclass (Sub-bundle 1 T-1.1) + `SchwabOrderResponse.executions: list[SchwabExecutionLeg] | None` field. The multi-leg auto-redirect predicate consumes these fields.
8. **`swing/trades/schwab_reconciliation.py:_compute_execution_price`** + `_resolve_match_quantity` + `_is_execution_bearing_candidate` — Sub-bundle 1 helpers. The multi-leg auto-redirect predicate consumes `_compute_execution_price` (VWAP rendering) + per-leg quantities. Verify helper shapes at brainstorm time.
9. **`CLAUDE.md` Gotchas section** — especially: `Pass-2-tier-1-FORBIDDEN + Pass-1-tier-1` gotcha (V2-RESOLVED for Pass-1; Pass-2 STAYS tier-2-always); `Classifier is a PURE function` gotcha; `Reconciliation flow pivot uses SAVEPOINT-per-discrepancy` gotcha (auto-correct service inherits transactional discipline); `Tier-1 auto-correct service inherits sandbox short-circuit gating` gotcha (multi-leg auto-redirect inherits identically); `Sub-bundle 2 Sub-bundle 2 base-layout VM banner pin` gotcha precedent (Phase 10 T-E.3 retrofit + Sub-bundle 2's SchwabStatusVM banner field — Phase 12.5 #1 banner advisory follows the same pattern).
10. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — ~60 cumulative forward-binding lessons inherited.
11. **`docs/phase3e-todo.md`** Phase 12.5 RESCOPED entry — high-level scope summary of Phase 12.5 #1 + #2 + #3.

---

## §1 Pre-locked operator decisions (OPERATOR-LOCKED 2026-05-17; DO NOT re-litigate)

Per orchestrator-operator scope conversation 2026-05-17 (4-question AskUserQuestion batch post-Sub-bundle-2-merge):

### §1.1 Decision 1 — Auto-redirect posture: ON (operator-locked)

When V2 mapper exposes multi-leg execution data AND VWAPs align within tolerance, classifier auto-emits tier-1 (auto-correct) bypassing the operator menu.

**Locked rationale:**
- Same justification that makes Pass-1 tier-1 auto-correct safe (Sub-bundle 1 ship) makes multi-leg tier-1 auto-correct safe.
- Sub-bundle 1.5 production data showed real multi-leg fills are uncommon (30-day sample had ZERO) but they WILL occur; auto-redirect streamlines operator's daily flow.
- Operator can revert via tier-3 `override-correction` (Sub-bundle C.C precedent).

**DO NOT design alternatives** — auto-redirect ON is the architectural posture. Brainstorm designs the implementation.

### §1.2 Decision 2 — Confidence threshold: all-match-within-tolerance (operator-locked)

Every execution leg's price must match within `price_tolerance=0.01` of the order-level VWAP (per-leg consistency check); journal price must match the VWAP within `price_tolerance`. Single outlier-leg flips classifier to tier-2 `multi_partial_vs_consolidated` (operator menu disposition).

**Locked rationale:**
- Spec §4.4 determinism principle (one and only one tier-1 emission per discrepancy; predictable).
- Defensible; predictable; tier-2 is the safe fall-back.
- Acceptable tradeoff: rejects some cases where operator might find it OK manually.

**DO NOT design majority-rule or strict-single alternatives** — all-match is the threshold. Brainstorm designs the exact comparison + tolerance handling.

### §1.3 Decision 3 — Auto-correct handler shape: reuse `apply_tier2_resolution(choice_code='split_into_partials')` (operator-locked)

Classifier synthesizes the payload that an operator's manual `split_into_partials` menu choice would produce (N partial fills with execution-leg quantities + per-leg prices) + invokes Sub-bundle C.C `apply_tier2_resolution(discrepancy_id, choice_code='split_into_partials', payload=synthesized_payload, resolved_by='auto', conn=conn, environment=cfg.integrations.schwab.environment)`.

**Locked rationale:**
- Minimum new code; auto vs manual differentiated by `resolved_by` field (`'auto'` for auto-redirect; `'operator'` for menu).
- Audit-trail forensic-honesty preserved (operator sees identical correction shape whether auto OR manual).
- Architectural lesson from Sub-bundle 1: pure-function classifier + service-layer enforcement keeps the architecture clean.

**Brainstorm SHALL design:**
- Exact payload synthesis from `SchwabExecutionLeg[]` to `split_into_partials` payload shape (N partial fills with per-leg `quantity` + `price` + timestamp + provenance).
- Whether `resolved_by='auto'` is sufficient OR a new value `resolved_by='auto_tier1_multi_leg'` (distinguishable from Pass-1 tier-1 auto-correct's `resolved_by='auto'`) is needed. **Recommended: extend the `_RESOLVED_BY_VALUES` enum** to distinguish.
- Classifier-to-service dispatch path: does the classifier directly invoke `apply_tier2_resolution` (would require service-import in classifier — breaks pure-function discipline)? OR does it emit a new tier-1 state that the reconciliation flow-pivot loop dispatches?

**The latter (emit-tier-1-state + flow-pivot dispatches)** is the CLAUDE.md gotcha-compliant pattern — preserves classifier-is-pure invariant. Brainstorm SHOULD lock this.

**DO NOT design dedicated new handler `apply_tier1_split_into_partials_auto`** — operator rejected this option.

### §1.4 Decision 4 — Operator-facing UX: banner advisory only (operator-locked)

Dashboard renders banner advisory when one OR more multi-leg auto-corrections fire in the most recent reconciliation_run. Operator-actionable surface; cheap to add. **Does NOT include a dedicated review page** (Decision 4 Option C was rejected).

**Locked rationale:**
- Operator wants to KNOW when auto-redirect fires (vigilance + trust calibration).
- Banner is cheap; per Phase 10 T-E.3 + Sub-bundle 2 base-layout VM banner pin precedent.
- Drill-down via existing surfaces: Phase 10 metrics dashboard + CLI `swing journal discrepancy show-correction <id>` + `swing journal discrepancy list --resolved auto` (verify exact CLI flag at brainstorm).

**Brainstorm SHALL design:**
- Banner predicate: count of multi-leg auto-corrections in WHICH window? (most-recent reconciliation_run? last 7 days? last operator-engagement-since? "since last view"?) — **operator-decision deferred to brainstorm Codex chain**.
- Banner template message wording (e.g., "⚠ N multi-leg auto-corrections in last reconciliation run. Review via `swing journal discrepancy list --resolved-by=auto_tier1_multi_leg` or /metrics/auto-redirects" — note the latter URL is NOT shipping V1 per operator decision).
- Banner clears semantics: when does the count reset to 0? (next reconciliation_run? operator-explicit-clear action? auto-clear after view-acknowledgment?).
- Banner-clears-on-fresh-run vs persists-until-acknowledged tradeoff.
- Base-layout VM field name + type (suggested `recent_multi_leg_auto_correction_count: int = 0`).
- Phase 10 T-E.3 base-layout VM retrofit (5 fields currently default-initialized — `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`, `unresolved_material_discrepancies_count`; this adds a 6th).
- Helper function shape: `_fetch_recent_multi_leg_auto_corrections_count(db_path, window_predicate)` parallel to `_fetch_unresolved_material_count`.
- Sentinel-leak audit pattern: the banner reads from `reconciliation_corrections` rows; ZERO sensitive data should leak.

**DO NOT design new web page `/metrics/auto-redirects`** — operator rejected this surface (V2 candidate banked).

---

## §2 Architectural surface for the brainstorm to design

Given §1's 4 pre-locked decisions, the brainstorm spec MUST design + Codex-review the following:

### §2.1 Multi-leg auto-redirect predicate

**Input:** `SchwabOrderResponse` (from `SchwabExecutionLeg[]` Sub-bundle 1 ship) + journal-side `Fill` row + `Trade` row.

**Output:** boolean (auto-redirect fires? yes/no) + rationale-text-for-audit.

**Predicate components** (brainstorm enumerates):
- `so.executions is not None and len(so.executions) >= 2` (multi-leg pre-condition; single-leg routes to Pass-1 tier-1 per Sub-bundle 1 ship).
- `sum(leg.quantity for leg in so.executions) == f.quantity` (qty alignment per Sub-bundle 1's `_resolve_match_quantity` semantics).
- VWAP computation: `vwap = sum(leg.price * leg.quantity for leg) / sum(leg.quantity for leg)` per Sub-bundle 1's `_compute_execution_price`.
- `abs(vwap - f.price) <= price_tolerance` (journal-VWAP alignment).
- All-legs check: `all(abs(leg.price - vwap) <= price_tolerance for leg in so.executions)` (per-leg consistency per §1.2 operator-lock; single outlier flips to tier-2).
- Edge case: what if `len(so.executions) == 2` and the 2 legs have OPPOSITE-direction prices (impossible for a single execution, but mapper could produce on malformed data)? — defensive: classifier emits tier-2 + audit warning.
- Edge case: zero-quantity legs (mapper rejects via `__post_init__` per Sub-bundle 1; defensive double-check at classifier).

### §2.2 Classifier dispatch state extension

**Option A (recommended at brainstorm):** classifier emits NEW tier-1 state `split_into_partials_auto_correct` (distinguishable from manual `split_into_partials` choice). Reconciliation flow-pivot loop dispatches this state via the SAME `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto')` path (the new state acts as a routing marker; service treats it like tier-2 `split_into_partials` for journal mutation).

**Option B (alternative):** classifier emits tier-2 `multi_partial_vs_consolidated` with a synthesized `recommended_choice='split_into_partials'` field; reconciliation flow-pivot loop reads the recommendation + invokes `apply_tier2_resolution(...)` automatically.

**Brainstorm decides + locks**, with Codex-round adversarial review on:
- Audit-trail forensic-honesty (which state name is more transparent in `reconciliation_corrections.ambiguity_kind` for analytics queries?).
- Coupling between classifier + reconciliation flow-pivot loop (which option keeps the classifier-is-pure invariant cleanest?).
- Schema impact: `_AMBIGUITY_KINDS` enum extension (if Option A) vs new `recommended_choice` field on `ClassificationResult` (if Option B).

### §2.3 Payload synthesis from `SchwabExecutionLeg[]` to `split_into_partials` payload

**Reference shape** (per Sub-bundle C plan §C.6 expected payload):
- `split_into_partials` payload is a list of N partial-fill specifications, each carrying `{quantity, price, timestamp_ish, provenance}`.

**Brainstorm enumerates** the mapping from `SchwabExecutionLeg` to partial-fill spec:
- `leg.quantity` → partial fill `quantity`.
- `leg.price` → partial fill `price`.
- `leg.time` → partial fill `timestamp` (verify timezone handling; spec §4.3.1 inherits ISO 8601 from Sub-bundle 1).
- `leg.instrumentId` + `leg.legId` → partial fill `provenance` JSON (for audit traceability).
- Validation: payload passes `validate_split_into_partials_payload` (per Sub-bundle C.C `default_validator_chain`).

**Edge cases:**
- N=2 vs N=20+ legs (Schwab API spec allows arbitrary leg count; defensive cap at brainstorm?).
- Per-leg `mismarked_quantity` field (Sub-bundle 1 dataclass) — does it map to anything in the partial-fill payload? Probably NO (informational; not consumed by journal).

### §2.4 New `resolved_by` value: `auto_tier1_multi_leg`

`_RESOLVED_BY_VALUES` enum (Sub-bundle C.C) extension. Distinguishable from:
- `'auto'` — Pass-1 tier-1 auto-correct (Sub-bundle 1 ship; single-leg + already-Shape-C-compliant)
- `'operator'` — operator menu CLI
- `'auto_tier1_multi_leg'` — Phase 12.5 #1 multi-leg auto-redirect

**Brainstorm locks** the exact enum string AND whether the schema CHECK constraint needs widening (likely YES per Phase 9 Sub-bundle A precedent; widens schema v19 → v20 IF schema-CHECK was constrained at v19; OR no-schema-change IF Sub-bundle C.A's CHECK was permissive).

**Schema-CHECK + Python-constant + dataclass-validator paired-discipline** (CLAUDE.md gotcha): if schema CHECK widens, the entire bundle T-A.1 lands the migration + Python constants + validators in ONE atomic commit.

### §2.5 Banner advisory infrastructure

**Base-layout VM field** (per §1.4):
- `recent_multi_leg_auto_correction_count: int = 0` (suggested name; brainstorm finalizes).
- Phase 10 T-E.3 retrofit pattern: ~10-11 base-layout VMs extended (existing 5 fields → 6 fields).

**Banner predicate window** (operator-decision deferred to brainstorm):
- Option A: count from MOST-RECENT `reconciliation_run` (clears when next run completes).
- Option B: count from LAST N days (e.g., 7 days; rolling window).
- Option C: count from LAST OPERATOR ENGAGEMENT (requires "last-acknowledged" persistence — heavier).

**Brainstorm recommends** + Codex-reviews. Operator-decision-locking points: see §3 below.

**Banner template wording** (suggested):
> ⚠ N multi-leg auto-corrections applied. Review via `swing journal discrepancy list --resolved-by auto_tier1_multi_leg` (CLI) or Phase 10 metrics dashboard.

**Banner clears semantics:**
- A: clears when next reconciliation_run completes (simplest; matches most-recent-run window).
- B: persists until operator-explicit-clear (heavier; requires a new "acknowledged_until" timestamp).

### §2.6 Test infrastructure (cassette OR fixture)

Sub-bundle 1's cassette infrastructure recorded only 3 of 4 order types (LIMIT BUY + LIMIT SELL + STOP FIRED + MARKET BUY hand-rolled). Sub-bundle 1.5 added 3 cassette + 14 canary tests but did NOT record a true multi-leg fill (operator's 30-day production had ZERO multi-leg orders).

**Brainstorm decides** test fixture shape:
- Option A: hand-rolled synthetic multi-leg fixtures (mirror Sub-bundle 1.5's H1-extended pattern).
- Option B: NEW cassette session if/when operator's production sees a multi-leg fill (operator-paired).
- Option C: combined (hand-rolled for synthetic coverage + opportunistic cassette for production-shape verification when available).

**Recommended: Option C** — hand-rolled synthetic fixtures for the 5-10 discriminating cases (all-match-within-tolerance pass; single-outlier fail; qty mismatch fail; per-leg shape predicate variations) + cassette opportunity reserved for V2 once production data surfaces.

### §2.7 Cascade analysis (what existing surfaces consume the new state?)

**Brainstorm enumerates downstream consumers** of the new classifier state + reconciliation_corrections rows:

- `reconciliation_corrections` rows with `ambiguity_kind='split_into_partials_auto_correct'` (Option A naming): consumed by Phase 10 metrics dashboard? show-correction CLI? base-layout banner?
- `briefing.md` "Reconciliation status" section (per Sub-bundle C.C `_step_export` wiring): does it call out auto-redirect counts separately?
- Phase 10 banner predicate widening (per Sub-bundle C.D `'pending_ambiguity_resolution'` widening precedent): does the new state affect banner count?
- Test surfaces inherited (per Sub-bundle C cross-bundle pin discipline): which existing tests must un-skip + which need re-running post-extension?

### §2.8 Sub-bundle decomposition

**Brainstorm proposes** (phase3e-todo says "estimated 2-3 sub-bundles"):

- Phase 12.5-1A: classifier widening + payload synthesis (~7-12 tasks; ~+40-80 fast tests).
- Phase 12.5-1B: banner infrastructure + base-layout VM retrofit + helper function (~4-7 tasks; ~+15-30 fast tests; possibly folded into 1A if scope permits).
- Schema impact: brainstorm decides v19→v20 OR v19-unchanged (per §2.4 enum widening analysis).

**Brainstorm SHOULD lock** a recommended decomposition with sub-bundle count + test projection + Codex-round projection.

---

## §3 Open questions (Codex-rounds SHOULD surface answers)

Brainstorm Codex chain SHOULD enumerate + design (operator decision pending at brainstorm-output time):

1. **§2.5 banner predicate window** — most-recent-run vs rolling-7-day vs operator-acknowledged. Brainstorm proposes + Codex argues tradeoffs.
2. **§2.5 banner clears semantics** — auto-clear-on-next-run vs persists-until-acknowledged. Operator-decision pending; brainstorm proposes default.
3. **§2.2 classifier state name** — `split_into_partials_auto_correct` vs `multi_partial_vs_consolidated` with `recommended_choice` field. Brainstorm proposes + locks.
4. **§2.4 schema impact** — does `_RESOLVED_BY_VALUES` widening require schema CHECK migration? (verify at brainstorm time via Sub-bundle C.A v19 migration SQL).
5. **§2.7 cascade impact** — Phase 10 banner predicate widening required? `briefing.md` Reconciliation section format change? Other downstream consumers?
6. **§2.1 edge cases** — opposite-direction-prices on legs; zero-quantity legs; mismatched timestamps within an order; `mismarked_quantity` consumption.
7. **§2.6 test fixture scope** — hand-rolled vs cassette vs hybrid; defensive coverage of how many discriminating cases.
8. **§2.3 payload validation** — does the existing `validate_split_into_partials_payload` (Sub-bundle C.C) cover the auto-synthesized shape? Or does it need extension?
9. **Banner field default in Phase 10 base-layout VM retrofit** — does the field need to land in Sub-bundle 1A (classifier ship) OR Sub-bundle 1B (banner ship)? Cross-bundle pin pattern (per Phase 10 T-E.3 + Sub-bundle 2 precedent).
10. **Determinism** — given the all-match-within-tolerance threshold, are there cases where two different runs (with identical inputs) could produce different `recommended_choice` values? Spec §4.4 determinism principle requires NO. Brainstorm verifies.

---

## §4 OUT OF SCOPE (do not design)

- **Schema additions beyond §2.4 `_RESOLVED_BY_VALUES` enum widening** — Phase 12.5 #3 maintenance pass absorbs anything else (per phase3e-todo Phase 12.5 RESCOPED entry).
- **Dedicated review page `/metrics/auto-redirects`** — Decision 4 Option C rejected by operator; V2 candidate banked.
- **Majority-rule confidence threshold** — Decision 2 rejected by operator (all-match-within-tolerance locked).
- **Dedicated new handler `apply_tier1_split_into_partials_auto`** — Decision 3 rejected by operator (reuse `apply_tier2_resolution` locked).
- **Pass-2 LIFT beyond the current spec §6.6 multi-leg scope** — Pass-2 single-leg single-matched-order LIFT remains DEFERRED V2 follow-up (operator-paced; separate dispatch).
- **CLI / web surface for `swing journal discrepancy list --resolved-by` filter** — if it doesn't already exist, V2 candidate (banner template can reference the CLI in operator-actionable text even if the flag is V2).
- **Web Tier-2 discrepancy-resolution surface** — Phase 12.5 #2 scope; separate dispatch.
- **CLAUDE.md / orchestrator-context archive-splits** — Phase 12.5 #3 scope.
- **Phase 8 walkthrough failing-test triage** — Phase 12.5 #3 scope.
- **Ruff 18 E501 cleanup** — Phase 12.5 #3 scope.
- **Behavioral changes to non-touched existing surfaces** — Phase 12.5 #1 is consumer-side of Sub-bundle 1 + 1.5 + 2 ships; the only modifications are classifier widening + auto-correct handler reuse + banner infrastructure. Especially: `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` / Shape C predicate / Path B sentinel / `/schwab/status` page / `_extract_executions_from_order_raw` mapper / `_has_non_placeholder_leg` canary helper — all UNCHANGED.

---

## §5 Adversarial review (Codex)

Invoked automatically by `copowers:brainstorming` after the spec draft + before final commit.

**Expected chain shape:** 3-5 substantive Codex rounds (smaller than Sub-bundle C brainstorm's 9-round chain because the architectural surface is bounded by §1's operator-locks; matches Sub-bundle 1 brainstorm's 3-round chain shape; ZERO new schema unless §2.4 surfaces necessity).

**Adversarial review watch items (Phase 12.5 #1-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Determinism principle preservation** (spec §4.4 inheritance from Sub-bundle C.B). All-match-within-tolerance MUST produce identical classification on identical inputs. Codex verifies no race / ordering / floating-point edge cases.
2. **Classifier purity invariant** (CLAUDE.md gotcha). Classifier MUST remain pure (no DB writes; no Schwab API calls; no transaction management). Auto-redirect dispatch MUST live in service layer / reconciliation flow-pivot loop.
3. **Audit-trail forensic-honesty** (Sub-bundle C inheritance). `reconciliation_corrections.resolved_by` MUST distinguish auto-redirect from manual. Code-content reasoning: which `resolved_by` value preserves analytics + forensic chase.
4. **Schema-CHECK + Python-constant + dataclass-validator paired discipline** (CLAUDE.md gotcha). If §2.4 widens enum, all 3 surfaces land in 1 task atomic.
5. **Banner field default + Phase 10 T-E.3 base-layout retrofit** (CLAUDE.md gotcha). New base-layout VM field MUST have safe default + every base-layout VM gets retrofitted; cross-bundle pin if needed (Sub-bundle 2 precedent).
6. **Sandbox short-circuit gating** (CLAUDE.md gotcha). Multi-leg auto-redirect inherits Sub-bundle C.C sandbox discipline; verify auto-redirect short-circuits at inner function NOT outer.
7. **`apply_tier2_resolution` payload contract** (Sub-bundle C.C). Synthesized payload from `SchwabExecutionLeg[]` MUST pass existing `validate_split_into_partials_payload` validator OR validator MUST be extended (atomic commit per discipline #4 above).
8. **Cassette + hand-rolled test discipline** (Sub-bundle 1 lesson family). Synthetic fixtures plant production-shape payloads byte-for-byte. Sub-bundle 1.5's `_has_non_placeholder_leg` pattern is mirrored if needed for multi-leg observability.
9. **`Co-Authored-By` footer suppression** (project invariant). Explicit citation in dispatch prompts.
10. **Banner predicate window operator-decision routing** — Codex SHOULD surface tradeoffs + propose default; operator may override at brainstorm-output review.

---

## §6 Deliverable shape

**Spec document at `docs/superpowers/specs/<YYYY-MM-DD>-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`** (mirror Sub-bundle C spec format):

- §0 Glossary
- §1 Architecture overview
- §2 Pre-locked operator decisions (the 4 from §1 above; verbatim binding clauses)
- §3 Module touch list
- §4 Multi-leg auto-redirect predicate
- §5 Classifier dispatch state design
- §6 Payload synthesis design
- §7 Auto-correct service integration
- §8 Banner advisory design
- §9 Sub-bundle decomposition (12.5-1A / 12.5-1B if needed)
- §10 Discriminating-example walkthroughs (5-10 cases covering pass + fail predicates)
- §11 Cascade analysis
- §12 Test fixture strategy
- §13 Schema impact analysis (v19 → v20 OR v19 unchanged)
- §14 V2 candidates banked
- §15 Operator decision items pending (anything Codex chain surfaces)

**Target line count: ~600-1000 lines** (smaller than Sub-bundle C's 1444 because architectural surface is bounded).

**Commit message stem:** `docs(phase12-5-1-oqf-spec): multi-leg tier-1 auto-redirect brainstorm — <N> Codex rounds → NO_NEW_CRITICAL_MAJOR convergent (R1 ... → R<N> ...)`.

---

## §7 If you get stuck

- If the architectural shape proposed at §2 conflicts with operator §1 LOCKs, the operator LOCKs WIN.
- If §1 LOCKs ARE the source of conflict (e.g., banner-only UX surface drift creates a design hole), SURFACE the conflict as an Open Question (§3 above) for operator review.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec + return report.
- If you need a schema element NOT in §2.4 enum widening, **STOP + escalate** (any schema additions must route through orchestrator).
- If Codex pushes back on the all-match-within-tolerance threshold, HOLD THE LINE — §1.2 operator-lock + spec §4.4 determinism principle.
- If Codex pushes back on the `apply_tier2_resolution` reuse pattern, HOLD THE LINE — §1.3 operator-lock + Sub-bundle C.C precedent.
- If Codex pushes back on banner-only UX scope (e.g., "but a dedicated review page is operationally important..."), HOLD THE LINE — §1.4 operator-lock + V2 candidate banked.
- DO NOT propose schema additions within Phase 12.5 #1 scope beyond §2.4 enum widening (escalation rule).
- DO NOT add `Co-Authored-By` footer to ANY commit message.

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Spec line count.
4. Pre-locked operator decisions verbatim verification.
5. §3 Open Questions: which surfaced + which Codex resolved + which deferred to operator review.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Cumulative V2 candidates banked.
8. Forward-binding lessons for writing-plans dispatch.
9. CLAUDE.md status-line refresh draft text.
10. Sub-bundle decomposition recommendation (12.5-1A / 12.5-1B or single sub-bundle).
11. Schema impact verdict (v19 unchanged OR v20 migration required + rationale).
12. Composition-surface verification.
13. Worktree teardown status.

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-1-oqf-brainstorm` (matches cleanup-script regex `phase\d+-*`? VERIFY — cleanup script regex was tightened to `(phase\d+[-_]|schwab(?:-\w+)?-bundle-)` at Phase 12 Sub-bundle A T-A.4; `phase12-5-...` should match `phase\d+[-_]` if regex parses `5` as part of `\d+`; brainstorm verifies at worktree-creation time; fall back to bare `phase125-bundle-1-oqf-brainstorm` if needed). Worktree directory `.worktrees/phase12-5-bundle-1-oqf-brainstorm/`.
- **Model:** defer to harness default.
- **Expected duration:** ~120-180 min brainstorm + ~30-60 min Codex chain. Total ~3 hours operator-paced.

---

*End of brief. Phase 12.5 #1 brainstorm dispatch — 4 operator-locked decisions pre-baked; architectural surface bounded; ~600-1000 line spec target; 3-5 Codex round expectation. OUTPUT: design spec for OQ-F multi-leg tier-1 auto-redirect that writing-plans phase can decompose into 1-2 executing-plans dispatches.*
