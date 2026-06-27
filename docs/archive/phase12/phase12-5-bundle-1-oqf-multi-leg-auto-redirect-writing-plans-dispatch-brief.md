# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #1 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan for the OQ-F multi-leg tier-1 auto-redirect — decomposing the locked spec at `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` into a single executing-plans dispatch with 11 tasks + per-task acceptance criteria + discriminating-test patterns + files-touched + tests-added projection + commit message stems. **7 operator-locked decisions** are pre-baked (4 from spec §2.1-§2.4 + 3 newly-locked from §15.B per operator-orchestrator scope conversation 2026-05-17 post-merge). Writing-plans surfaces remaining open implementation questions via Codex chain.

**Brief:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** Phase 12.5 #1 brainstorm SHIPPED 2026-05-17 at `a1582c0` (7 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE across 15 Major + 10 Minor — cleanest brainstorm chain in project history). Spec doc at 1236 lines. Writing-plans dispatch (this) produces the plan; executing-plans dispatch ships the code; operator-witnessed gate runs after executing-plans converges.

**Expected duration:** ~90-150 min plan-write + 3-5 adversarial Codex rounds. Scope is narrow: single-sub-bundle decomposition of an already-locked spec (zero schema; bounded surface). Plan line target: **~600-900 lines** (smaller than Phase 9's 2257 or Phase 10's 2008 because single-sub-bundle vs 5-bundle arcs).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the locked spec.
- `copowers:writing-plans` wraps `superpowers:writing-plans` + adversarial Codex review.
- Output is a plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`** — operator-LOCKED + Codex-ratified spec (1236 lines; 7 rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE). **THIS IS THE PRIMARY SPEC SUBSTRATE.** Read end-to-end. §2 operator-locks (4 binding clauses); §3 module touch list; §4 predicate design; §5 classifier dispatch state; §6 payload synthesis; §7 auto-correct service integration; §8 banner advisory design; §9 sub-bundle decomposition (single-sub-bundle ship recommended); §10 discriminating-example walkthroughs; §11 cascade analysis; §12 test fixture strategy; §13 schema impact (v19 UNCHANGED LOCK); §15.A brainstorm-locks (7 items); §15.B operator-decision items (3 items — NOW LOCKED per §1.5 below); §16 forward-binding lessons (8 items).
2. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md`** — brainstorm return report. Especially §8 Codex-chain-surfaced lessons (4 additional forward-binding lessons beyond spec §16) + §10 spec line breakdown + §12 V2 candidates banked.
3. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md`** — the brainstorm dispatch brief (`37b584d`). Read for context on the architectural surface the brainstorm was tasked to design (now realized in the spec).
4. **`docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` §6.6** — OQ-F V2 LOCK predecessor (post-Phase-12 mapper-widening spec lines 561-590). Brainstorm's architectural surface derives from this.
5. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** — Sub-bundle C brainstorm spec (1444 lines). Especially: §4 classifier sub-classifier surface; §5 service-layer auto-correct + `apply_tier2_resolution`; §6.2.1 `multi_partial_vs_consolidated` ChoiceMenu; §8.4 Pass-2-tier-1-FORBIDDEN policy.
6. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`** — Sub-bundle C plan (large; READ FOR PLAN-FORMAT REFERENCE). Mirror this format. Especially §A (task decomposition); §C (cross-bundle pins); §D (locked decisions roll-up); §E (test projection); §G (per-task acceptance criteria).
7. **`docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`** — post-Phase-12 mapper-widening plan (1215 lines). Read for PLAN FORMAT REFERENCE — closer in scope (2 sub-bundles vs C's 4) to what Phase 12.5 #1 plan needs.
8. **`swing/trades/reconciliation_classifier.py`** — current classifier module post-Sub-bundle 1. The plan's predicate + classifier-state extension will live here.
9. **`swing/trades/reconciliation_auto_correct.py`** — current auto-correct service post-Sub-bundle C.C. The plan's override-kwarg additions to `apply_tier2_resolution` live here.
10. **`swing/integrations/schwab/models.py`** + **`swing/integrations/schwab/mappers.py`** + **`swing/trades/schwab_reconciliation.py`** — Sub-bundle 1 + 1.5 shipped surfaces. The plan's predicate consumes `SchwabExecutionLeg[]` + helpers (`_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate`).
11. **`swing/web/view_models/base.py`** + base-layout VMs across `swing/web/view_models/`. The plan's banner field landing pattern.
12. **`CLAUDE.md` Gotchas section** — full read. Especially: Schema-CHECK + Python-constant + dataclass-validator paired-discipline; Free-text columns vs CHECK enum columns (NEW spec §16 lesson #3); Cross-column CHECK invariants; Sandbox short-circuit ALWAYS in inner; HTMX trinity; cp1252 stdout encoder (ASCII-only banner text); session-anchor read/write mismatch; SAVEPOINT-per-discrepancy pattern; Classifier is a PURE function.
13. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — ~60 cumulative forward-binding lessons inherited.

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Spec §2.1 operator-lock — Auto-redirect posture = ON

When V2 mapper exposes multi-leg execution data + VWAPs align within tolerance → tier-1 auto-correct. Plan inherits.

### §1.2 Spec §2.2 operator-lock — Confidence threshold = all-match-within-tolerance

Per spec §4.4 determinism principle. Plan inherits.

### §1.3 Spec §2.3 operator-lock — Auto-correct handler shape = reuse `apply_tier2_resolution`

Classifier emits new state; reconciliation flow-pivot loop invokes `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied', operator_custom_payload=synthesized_payload)`. Plan inherits.

### §1.4 Spec §2.4 operator-lock — Banner advisory only

NO dedicated review page. Base-layout VM banner pin pattern per Phase 10 T-E.3 + Sub-bundle 2 precedent. Plan inherits.

### §1.5 NEW operator-locks for §15.B items (locked 2026-05-17 post-brainstorm-merge)

Per operator-orchestrator scope conversation 2026-05-17 post-brainstorm-merge at `a1582c0` — all 3 §15.B items accepted at brainstorm defaults:

1. **§4.4 `price_tolerance` threshold = LOCK $0.01 absolute** (NOT `max($0.01, abs(journal_price) * 0.001)` relative override). Matches spec §4.4 inheritance + existing codebase pattern. Operator's universe is $1-$70 stocks; proportional override is V2 candidate banked if universe expands to $500+ stocks. Plan locks `price_tolerance = 0.01` constant verbatim.

2. **§6.3 `qty_tolerance` LOCK predicate=1e-9 (handler=1e-6 unchanged)**. Strictness asymmetry is safe by construction — predicate stricter than handler. Plan does NOT touch `swing/trades/reconciliation_auto_correct.py` handler's `1e-6` threshold; predicate uses `1e-9`. Documented inline.

3. **§6.4 defensive cap on N legs = LOCK NO cap V1**. Schwab supports arbitrary leg count; production evidence so far is ZERO multi-leg orders; mapper-coherence-check at `swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw` already filters pathological shapes via `sum(leg.qty) == filledQuantity` invariant. Plan does NOT introduce `MAX_LEGS_PER_ORDER` constant. V2 candidate banked.

**All 7 locks (4 spec §2 + 3 §15.B) are BINDING.** Plan MUST encode these verbatim. Codex chain MUST NOT re-litigate.

---

## §2 Brainstorm-locked items at §15.A (DO NOT re-litigate; Codex chain resolved during brainstorm)

Per spec §15.A — 7 items LOCKED via Codex chain Round 1-6 resolutions. Plan inherits verbatim:

- §6.5 n=1 single-order multi-leg path LOCKED YES via ambiguity_kind reclassification (Codex R1 M2).
- §8.6 `--resolved-by <value>` CLI filter LOCKED IN-BUNDLE at T-1.10 (Codex R1 M5; banner template cites the filter; both land together).
- §7.6 sandbox short-circuit gated-on-auto-redirect LOCKED with SAVEPOINT ROLLBACK pattern (Codex R1 M3).
- §7.4 service API parameter naming LOCKED to `operator_custom_payload` (existing kwarg) + new `applied_by_override` + `correction_action_override` + `resolved_by_override` overrides (Codex R1 M4).
- §11.2 briefing.md +1 line per run for `tier1_multi_leg_redirected_count` when > 0 (locked).
- §12.3 canary observability for empty-executions case ~+5 LOC + 1 test (Sub-bundle 1.5 canary precedent).
- §13.3 Brief §2.4 amendment banked — no `_RESOLVED_BY_VALUES` constant exists; `resolved_by` is free TEXT.

**Schema v19 UNCHANGED LOCK** (spec §13) — CHECK enums already accommodate. NO migration in this plan.

---

## §3 Plan decomposition target (single sub-bundle ship)

Spec §9 recommends **single-sub-bundle ship** (NOT 2-3 sub-bundle decomposition). Plan operationalizes this:

### §3.1 11-task projection (per spec §9 + Codex R5 + return report §3)

| Task | Title | Files (illustrative; plan §A locks) | Tests projected |
|---|---|---|---|
| T-1.1 | `auto_redirect_recipe` field on `ClassificationResult` (default None) | MODIFY `swing/trades/reconciliation_classifier.py` | ~5 |
| T-1.2 | Multi-leg auto-redirect predicate (qty alignment + VWAP + per-leg consistency) | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_multi_leg_auto_redirect_predicate.py` | ~15 |
| T-1.3 | Classifier state emission via predicate + recipe synthesis | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_classifier_auto_redirect_emission.py` | ~10 |
| T-1.4 | Payload synthesis from `SchwabExecutionLeg[]` to `split_into_partials` payload | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_payload_synthesis_for_multi_leg.py` | ~8 |
| T-1.5 | `apply_tier2_resolution` override kwargs (`applied_by_override` + `correction_action_override` + `resolved_by_override`) | MODIFY `swing/trades/reconciliation_auto_correct.py` + NEW `tests/trades/test_apply_tier2_resolution_override_kwargs.py` | ~10 |
| T-1.6 | Reconciliation flow-pivot dispatch of auto-redirect state | MODIFY `swing/trades/reconciliation_auto_correct.py` (flow pivot) + NEW `tests/trades/test_flow_pivot_auto_redirect_dispatch.py` | ~8 |
| T-1.7 | Sandbox short-circuit at inner gated on `applied_by_override=='auto'` | MODIFY `swing/trades/reconciliation_auto_correct.py` + NEW `tests/trades/test_sandbox_short_circuit_auto_redirect.py` | ~5 |
| T-1.8 | Banner field on base-layout VM + helper function + ASCII-only template text | MODIFY `swing/web/view_models/base.py` + ALL base-layout VM subclasses retrofit + MODIFY `swing/web/templates/base.html.j2` + NEW helper `_fetch_recent_multi_leg_auto_corrections_count` | ~12 |
| T-1.9 | briefing.md +1 line for `tier1_multi_leg_redirected_count` when > 0 | MODIFY `swing/pipeline/briefing.py` or `swing/pipeline/runner.py:_step_export` + NEW test | ~3 |
| T-1.10 | `--resolved-by <value>` CLI filter on `swing journal discrepancy list` | MODIFY `swing/cli.py` (discrepancy list command) + NEW `tests/cli/test_discrepancy_list_resolved_by_filter.py` | ~5 |
| T-1.11 | Canary observability for empty-executions case (Sub-bundle 1.5 precedent) | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_empty_executions_canary.py` | ~4 |

**Total projection**: ~+85 fast tests + 1 slow E2E (~+86 net) + ~+320 LOC.

**Plan §A SHALL refine** task boundaries + acceptance criteria + discriminating-test patterns (Codex chain may decompose differently).

### §3.2 Plan §B SHALL design cross-bundle pin (single-bundle dispatch; cross-bundle pin is to existing surfaces)

- Sub-bundle 1 / 1.5 / 2 shipped surfaces: read-only consumers (predicate consumes `SchwabExecutionLeg[]`; classifier consumes `_compute_execution_price` / `_resolve_match_quantity`; banner consumes existing T-E.3 retrofit pattern).
- Phase 10 banner discipline: NEW base-layout VM field per Sub-bundle 2 precedent (added 1 field; touched 10 base-layout VMs).

### §3.3 Plan §C+ SHALL enumerate

- §C cross-bundle pins (single-bundle; pins to shipped surfaces).
- §D locked decisions roll-up (all 7 locks from §1 above + 7 §15.A brainstorm-locks; verbatim).
- §E projected test delta (~+85 fast tests + 1 slow E2E; ~+320 LOC).
- §F escalation rules (if Codex surfaces schema need → STOP + escalate per §1.5 #3 + Phase 9 Sub-bundle A precedent).
- §G per-task acceptance criteria (mirror Sub-bundle C plan §G structure).
- §H per-sub-bundle gate plan (4-6 surfaces; mirror Sub-bundle 1.5 + 2 gate budgets).
- §I cross-bundle invariants (Codex chain MAY surface additional; plan author enumerates).
- §J operator-witnessed gate plan (specific gate surfaces: S1 pytest + S2-S4 visible surfaces + S5 ruff).

---

## §4 Adversarial review (Codex)

Invoked automatically by `copowers:writing-plans` after plan draft + before final commit.

**Expected chain shape:** 3-5 substantive Codex rounds (matches Sub-bundle C plan ~5 rounds + post-Phase-12 mapper-widening plan ~6 rounds; scope is similar single-sub-bundle decomposition). Brainstorm already absorbed 7 Codex rounds + ZERO ACCEPT-WITH-RATIONALE; plan should converge faster.

**Adversarial review watch items (Phase 12.5 #1 writing-plans-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Determinism principle preservation** (spec §4.4 inheritance). Plan task T-1.2's predicate test cases cover edge cases: zero-quantity legs; mismatched-currency legs (Schwab edge case); per-leg time skew; floating-point tolerance boundary.
2. **Classifier purity invariant** (CLAUDE.md gotcha). T-1.2 + T-1.3 + T-1.4 keep classifier pure (no DB writes; no Schwab API; no transaction management). Service-layer dispatch (T-1.6) is the only place DB writes occur.
3. **Audit-trail forensic-honesty** (Sub-bundle C inheritance). T-1.5's `applied_by_override` + `correction_action_override` + `resolved_by_override` parameter threading preserves verbatim existing-behavior for the manual-tier-2 path. Discriminating test asserts no regression on manual-tier-2 path WITHOUT supplying overrides.
4. **Schema-CHECK + Python-constant + dataclass-validator paired discipline** (CLAUDE.md gotcha). Spec §13 locks v19 unchanged + `resolved_by` free TEXT; plan does NOT propose schema additions. Codex verifies.
5. **Free-text columns vs CHECK enum columns** (spec §16 lesson #3 + return report §8 forward-binding lesson). Plan author MUST pre-flight `grep -n CHECK` against migration 0019 for EVERY new string value introduced. Plan §F documents the pre-flight verification.
6. **Cross-column CHECK invariants** (spec §16 lesson #4). Plan task T-1.6 verifies post-transition state passes the schema's `(ambiguity_kind, resolution)` cross-column CHECK via explicit probe.
7. **Banner field default + Phase 10 T-E.3 base-layout retrofit** (CLAUDE.md gotcha). T-1.8 covers ALL 10+ base-layout VMs with the new banner field at default value (NOT just the touched ones); cross-bundle pin test asserts no Jinja UndefinedError surface.
8. **Sandbox short-circuit gating** (CLAUDE.md gotcha + spec §7.6 LOCK). T-1.7 gates short-circuit on `applied_by_override == 'auto'` (NOT on environment alone). Discriminating test exercises manual-tier-2 path under sandbox (still mutates because operator-explicit) vs auto-redirect path under sandbox (short-circuits).
9. **`apply_tier2_resolution` payload contract** (Sub-bundle C.C). T-1.4's synthesized payload from `SchwabExecutionLeg[]` MUST pass existing `validate_split_into_partials_payload` validator (the existing handler at `_handle_split_into_partials`).
10. **Cassette + hand-rolled test discipline** (Sub-bundle 1 + 1.5 lesson family). T-1.2 predicate tests use hand-rolled synthetic fixtures (operator's production has ZERO multi-leg orders so far per Sub-bundle 1.5 diagnostic). V2 cassette opportunity banked.
11. **ASCII-only banner text** (CLAUDE.md cp1252 gotcha + spec §16 lesson #7). T-1.8 banner template uses ASCII only (no em-dash, arrows, glyphs).
12. **`Co-Authored-By` footer suppression** (project invariant; ZERO drift across ~90+ commits cumulative). Explicit citation in dispatch prompt.
13. **`--resolved-by` CLI filter implementation** (T-1.10). Spec §8.6 LOCK: filter lands IN-BUNDLE. Banner template cites the filter; both land together. Discriminating test exercises filter against fixture with auto-redirect rows.
14. **briefing.md +1 line condition** (T-1.9). Spec §11.2 LOCK: line emits only when `tier1_multi_leg_redirected_count > 0`. Discriminating test exercises both branches (0 → absent; > 0 → present).
15. **Canary observability test** (T-1.11; spec §12.3 LOCK + Sub-bundle 1.5 precedent). Mirror `_has_non_placeholder_leg` canary discipline.
16. **Operator-witnessed gate scope** (§J in plan). 4-6 surfaces; matches Sub-bundle 1.5 + 2 gate budgets. Plan author SHALL specify each surface + acceptance criterion.

---

## §5 Deliverable shape

**Plan document at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`** (mirror Sub-bundle C plan format):

- §0 Plan overview + cross-references to spec sections
- §1 Operator-locked decisions roll-up (verbatim from spec §2 + §15.B + brainstorm §15.A; 14 locks total)
- §A Task list (T-1.1 .. T-1.11; per-task scope + acceptance criteria + discriminating tests + files-touched + test projection + commit message stem)
- §B Cross-bundle pins (single-bundle; consumer-side of Sub-bundle 1 / 1.5 / 2 shipped surfaces)
- §C Locked decisions roll-up
- §D Test projection (~+85 fast tests + 1 slow E2E; ~+320 LOC)
- §E Plan-author schema additions escalation rule (per Phase 9 Sub-bundle A return report lesson #7)
- §F Pre-flight grep verifications (CHECK enums; cross-column CHECKs; `_RESOLVED_BY_VALUES`-style constants)
- §G Per-task acceptance criteria narrative (binding contracts)
- §H Per-sub-bundle gate plan (4-6 surfaces; specific acceptance criteria)
- §I Cross-bundle invariants
- §J Operator-witnessed gate plan
- §K If you get stuck (mirror brainstorm-brief §7)
- §L V2 candidates banked

**Target line count: ~600-900 lines.**

**Commit message stem:** `docs(phase12-5-1-oqf-plan): single-sub-bundle decomposition — <N> Codex rounds → NO_NEW_CRITICAL_MAJOR convergent (R1 ... → R<N> ...)`.

---

## §6 OUT OF SCOPE (do not design)

- **Schema additions** — spec §13 LOCK v19 unchanged. Plan-author schema additions escalation rule (per Phase 9 Sub-bundle A return report lesson #7 + spec §16 lesson #3). If plan author surfaces schema need, STOP + escalate.
- **Override of §1 operator-locks** — all 7 (spec §2.1-§2.4 + 3 §15.B) are BINDING; do NOT re-litigate.
- **Override of §2 brainstorm-locks** — all 7 (spec §15.A) are BINDING; do NOT re-litigate.
- **Web Tier-2 discrepancy-resolution surface** — Phase 12.5 #2 scope; separate dispatch.
- **CLAUDE.md / orchestrator-context archive-splits** — Phase 12.5 #3 scope.
- **Phase 8 walkthrough failing-test triage** — Phase 12.5 #3 scope.
- **Ruff 18 E501 cleanup** — Phase 12.5 #3 scope.
- **V2 candidates** (per spec §14; 12 banked items) — do NOT in-scope any; document banked-V2 list in plan §L.
- **Behavioral changes to non-touched existing surfaces** — Sub-bundle 1 / 1.5 / 2 architectural surfaces UNCHANGED. Especially: `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` / Shape C predicate / Path B sentinel / `/schwab/status` page / mapper / canary helper — all consumed unchanged.
- **Dedicated review page `/metrics/auto-redirects`** — Decision 4 Option C rejected by operator at brainstorm; V2 candidate.
- **Majority-rule confidence threshold** — Decision 2 rejected by operator; spec §4.4 all-match LOCK.
- **Dedicated new handler `apply_tier1_split_into_partials_auto`** — Decision 3 rejected by operator; reuse `apply_tier2_resolution` LOCK.

---

## §7 If you get stuck

- If plan needs a schema element NOT in spec §13, **STOP + escalate** (Phase 9 Sub-bundle A lesson #7 inheritance).
- If Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag in plan + return report.
- If Codex pushes back on the LIVE/PROVISIONAL/DEGRADED state triplet OR §1.5 operator-locks, HOLD THE LINE — operator-locked at scope conversation 2026-05-17 post-brainstorm-merge.
- If a Codex round surfaces a Sub-bundle 1 / 1.5 / 2 architectural concern (e.g., comparator semantic change needed for V1 LIFT), STOP + escalate — these surfaces are LOCKED unchanged per spec §3 module touch list.
- If `_handle_split_into_partials` signature doesn't accept `applied_by_override` / `correction_action_override` / `resolved_by_override` per spec §7.4 LOCK, ESCALATE — the spec assumes these are NEW kwargs added to the existing public signature in T-1.5.
- If plan-author surfaces a need for V2.1 §VII.F amendment, BANK in plan §L + return report §6.
- DO NOT propose new architectural surfaces within Phase 12.5 #1 plan scope.
- DO NOT add `Co-Authored-By` footer to any commit message (per project invariant; ZERO drift across ~90+ commits cumulative).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with §1 + §2 + §3 binding contracts as anchors; ask for deviation list ≤300 words. Cheap; absorbed LOCK divergences pre-Codex on Phase 12 C.C + C.D + Sub-bundle 1 + brainstorm.

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Plan line count.
4. 14 operator+brainstorm-locks verbatim verification.
5. Per-task acceptance criteria summary.
6. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO ACCEPT-WITH-RATIONALE (matches brainstorm + Sub-bundle 2 clean record).
7. V2 candidates banked (per spec §14 + any new surfaced in writing-plans Codex chain).
8. Forward-binding lessons for executing-plans dispatch.
9. CLAUDE.md status-line refresh draft text.
10. Schema impact verdict (v19 UNCHANGED expected; escalate if surfaced).
11. Composition-surface verification (`^def ` grep on touched modules confirming public-surface scope).
12. Worktree teardown status.

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-1-oqf-writing-plans` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-bundle-1-oqf-writing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~90-150 min plan-write + ~30-60 min Codex chain. Total ~2-3 hours operator-paced (per `feedback_time_estimates_overstated.md` calibration).

---

*End of brief. Phase 12.5 #1 writing-plans dispatch — 14 operator+brainstorm-locks pre-baked; single-sub-bundle decomposition target; ~600-900 line plan; 3-5 Codex round expectation. OUTPUT: plan doc that executing-plans phase decomposes into 11 tasks for the final code-ship.*
