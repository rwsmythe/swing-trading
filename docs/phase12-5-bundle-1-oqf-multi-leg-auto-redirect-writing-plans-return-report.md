# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Writing-Plans Return Report

**Date:** 2026-05-17
**Dispatch:** Phase 12.5 #1 OQ-F multi-leg tier-1 auto-redirect writing-plans
**Brief:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md` (commit `5c988d2`)
**Spec consumed:** `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (1236 lines; 7 Codex rounds; ZERO ACCEPT-WITH-RATIONALE; cleanest brainstorm chain in project history)
**Plan deliverable:** `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`
**Branch:** `phase12-5-bundle-1-oqf-writing-plans`
**Worktree:** `.worktrees/phase12-5-bundle-1-oqf-writing-plans/`

---

## §1 Final HEAD + commit breakdown

**Final HEAD on branch:** `6349486`

| Commit (SHA short) | Type | Description |
|---|---|---|
| `1063586` | plan-write | Initial 1008-line plan; 11 tasks T-1.1..T-1.11; 14 pre-locked decisions encoded; 19 invariants F1-F19 |
| `6349486` | Codex R1-R5 fixes | 12 Major + 5 Minor resolved in-tree; 6 NEW invariants F20-F25; backfill consumer wiring added (operational firing site); §F + §M + §K all refreshed |

**Commit count:** 2 plan commits = 1 initial + 1 Codex-fix bundle.

**ZERO `Co-Authored-By` footer drift** — verified across both commits (matches Phase 12 Sub-bundle C.B-D arc + brainstorm chain ZERO drift across ~95+ cumulative commits).

---

## §2 Codex round chain (R1–R5 convergent shape)

| Round | Critical | Major | Minor | Verdict | Outcome |
|---|---|---|---|---|---|
| R1 | 1 | 4 | 1 | ISSUES_FOUND | All resolved in `6349486` |
| R2 | 0 | 3 | 1 | ISSUES_FOUND | All resolved in `6349486` |
| R3 | 0 | 4 | 2 | ISSUES_FOUND | All resolved in `6349486` |
| R4 | 0 | 1 | 2 | ISSUES_FOUND | All resolved in `6349486` |
| R5 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** | Chain sealed; 2 minor cleanup items also resolved |

**Chain shape:** 1C+4M+1m → 3M+1m → 4M+2m → 1M+2m → 0C/0M/2m. Non-monotonic Major taper (4→3→4→1→0); R3's bump above R2 was driven by Codex catching downstream drift the R2 fixes themselves introduced (e.g., new backfill outcome enumeration needed counter wiring; new try/except needed more granular failure-routing).

**Cumulative finding disposition:**
- **1 Critical raised** (R1) → **RESOLVED with code-content fix**; ZERO ACCEPT-WITH-RATIONALE banked.
- **12 Major raised** across R1-R4 → **ALL 12 RESOLVED with code-content fixes**; ZERO ACCEPT-WITH-RATIONALE banked.
- **5 Minor raised** across R1-R5 (1 + 1 + 2 + 2 + 2 minus duplicates) — actually 8 distinct → 8 RESOLVED with code-content fixes; ZERO ACCEPT-WITH-RATIONALE banked. (Some minors were duplicate flags of the same stale text across multiple rounds.)
- **0 Critical findings post-R1 fix** entire chain.

**Comparison precedents** (per CLAUDE.md status line):
- Phase 12 Sub-bundle C.B writing-plans: 5 rounds, 1C/6M/2m resolved, ZERO accept-with-rationale.
- Phase 12 Sub-bundle C.D writing-plans: 4 rounds, 0C/6M/5m resolved, ZERO accept-with-rationale.
- Post-Phase-12 mapper-widening writing-plans: 6 rounds, 0C/?M/?m resolved, ZERO accept-with-rationale.
- Phase 12.5 #1 brainstorm: 7 rounds, 0C/15M/10m resolved, ZERO accept-with-rationale.
- **Phase 12.5 #1 writing-plans (this dispatch): 5 rounds, 1C/12M/5m resolved, ZERO accept-with-rationale.**

Codex caught the architectural gap (R1 Critical #1 — backfill is the operational firing site, not the initial pivot) AND multiple downstream drift cascades (R2-R4) AND stale-text leftovers (R5). The 5-round shape is mid-pack for project history; the architectural gap surfacing at R1 was high-value (would have shipped a dead-code dispatcher otherwise).

---

## §3 Plan line count + scope

| Phase | Lines |
|---|---|
| Plan draft (`1063586`) | 1008 |
| After R1-R5 fixes (`6349486`) | **1230** |

**Brief target: ~600-900 lines.** Plan ended 330 lines above the upper bound. Drivers:
- 5-round Codex chain absorbed substantive surface expansion (R1 Critical #1 doubled T-1.5's consumer-wiring scope; R2 added T-1.5.B subsection with 9-criterion backfill matrix; R3 added 4 additional acceptance criteria; R4 added format_summary_block renderer).
- §F invariants table expanded F1-F19 → F1-F25 (6 new contracts).
- §M forward-binding lessons grew from scaffold-only to 12 inherited + 6 NEW writing-plans-surfaced.

Accept the overshoot — the additional line count documents architectural depth Codex surfaced past the brief's nominal estimate. Executing-plans will consume the locked design rather than re-derive.

---

## §4 14 operator+brainstorm-locks verbatim verification

Per plan §D.

### §D.1 Operator-locks from spec §2 (brief §1.1-§1.4)

1. **Auto-redirect posture = ON** (spec §2.1) — encoded in §D.1 #1; threaded through T-1.2 (classifier emits recipe when predicate fires).
2. **Confidence threshold = all-match-within-tolerance** (spec §2.2) — encoded in §D.1 #2; T-1.1 predicate sub-conditions 3+5+6.
3. **Auto-correct handler shape = reuse `apply_tier2_resolution(split_into_partials)`** (spec §2.3) — encoded in §D.1 #3; T-1.4 + T-1.5 + recipe shape in T-1.1.
4. **Operator-facing UX = banner advisory only** (spec §2.4) — encoded in §D.1 #4; T-1.7 + T-1.8 + T-1.9 + T-1.10.

### §D.2 Operator-locks from spec §15.B (locked 2026-05-17 post-brainstorm-merge)

5. **`price_tolerance = $0.01` absolute LOCK** — encoded as `_MULTI_LEG_PRICE_TOLERANCE = 0.01` in T-1.1.
6. **`qty_tolerance` asymmetry preserved: predicate=1e-9 / handler=1e-6** — encoded as `_MULTI_LEG_QTY_TOLERANCE = 1e-9` in T-1.1; handler's `qty_tolerance = 1e-6` at line 1680 UNCHANGED + F8 invariant pins.
7. **NO defensive cap on N legs V1** — T-1.1 acceptance: no `MAX_LEGS_PER_ORDER` constant; F10 invariant pins.

### §D.3 Brainstorm-locks from spec §15.A (Codex chain resolved)

8. **§6.5 n=1 single-order multi-leg path via ambiguity_kind reclassification** — encoded in T-1.2 n=1 branch.
9. **§8.6 `--resolved-by <value>` CLI filter IN-BUNDLE at T-1.10** — encoded as T-1.10; banner template T-1.9 cites the filter verbatim.
10. **§7.6 sandbox short-circuit gated-on-auto-redirect + SAVEPOINT ROLLBACK** — encoded in T-1.6.
11. **§7.4 service API: `operator_custom_payload` + 3 NEW override kwargs** — encoded in T-1.4; positional `conn` first arg preserved per spec §7.1 Codex R3 M1 LOCK.
12. **§11.2 briefing.md +1 line when count > 0** — encoded in T-1.11; verbatim wording "Multi-leg auto-redirects applied this run: K" per Codex R1 Major #2 fix + F22 invariant.
13. **§12.3 canary observability for empty-executions** — encoded in T-1.11 (`~+5 LOC` predicate WARN log).
14. **`resolved_by` is free TEXT** (no constant exists) — F7 invariant pins; no schema CHECK widening.

**ZERO operator-lock or brainstorm-lock re-litigation** — Codex did NOT challenge any of the 14 locks; all 5-round chain findings were on implementation details that respected the locks.

---

## §5 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE banked** across all 1 Critical + 12 Major + 8 distinct Minor findings. Every finding resolved with code-content fixes to the plan.

This matches the clean record set by Phase 12 Sub-bundle C.D + post-Phase-12 Sub-bundle 1/2 + Phase 12.5 #1 brainstorm dispatches.

---

## §6 V2 candidates banked (mirrored from spec §14)

Plan §Z carries the 12 V2 candidates verbatim:

1. Banner predicate window — 7-day rolling.
2. Banner predicate window — persists-until-acknowledged.
3. Dedicated `/metrics/auto-redirects` review page.
4. Schwab cassette recording for multi-leg fill.
5. Defensive cap on N legs.
6. `_RESOLVED_BY_VALUES` Python constant formalization.
7. Promote `auto_redirect_recipe` to typed dataclass.
8. Per-leg `mismarked_quantity` consumption.
9. Operator-acknowledged-clear surface (`swing journal reconciliation acknowledge-redirects`).
10. Predicate-on-n=1 — LOCKED IN V1 (promoted from V2 to V1 LOCK at brainstorm).
11. Audit trail surfacing in `show-correction` epilog.
12. Other tier-2 ambiguity_kinds auto-redirect candidates.

**No NEW V2 candidates surfaced during writing-plans Codex chain** — all R1-R5 findings resolved in-tree.

---

## §7 Forward-binding lessons for executing-plans phase

Plan §M now carries **18 forward-binding lessons** for executing-plans inheritance:

### From brainstorm return report §8 (12 inherited):

1. Recipe-field discipline.
2. Override parameter threading.
3. Free-text vs CHECK-enum columns.
4. Cross-column CHECK invariants.
5. Sandbox short-circuit ALWAYS in inner.
6. Helper invocation completeness.
7. ASCII-only banner text.
8. Counter ROW-vs-LOGICAL semantics.
9. Validate override combos BEFORE state mutation.
10. Shape-aware terminal-state idempotency.
11. Exception specificity ordering in catch blocks.
12. Positional-vs-keyword signature audit at brainstorm/writing time.

### NEW from writing-plans Codex chain (6 added, plan §M lessons L-W1 through L-W6):

13. **L-W1 (R1 Critical #1):** When designing a "dispatcher pattern + recipe consumption" architecture, enumerate EVERY dispatcher consumer. Initial pivot's source_payload derivation matters; if it returns None for an unmatched sentinel, the dispatcher in that path is dead-code; the operational consumer lives ELSEWHERE.
14. **L-W2 (R1 Major #1):** Spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering in plan tasks, NOT as "PLAN DECISION" overrides aligned with adjacent graceful-degradation patterns.
15. **L-W3 (R1 Major #2):** Spec-locked rendering text MUST be verbatim-asserted in tests. Don't lift adjacent patterns (e.g., "last 7 days" wording from the neighboring `tier1_recent_count` legacy renderer) without checking the new lock.
16. **L-W4 (R1 Major #3):** Retrofit scope predicates MUST be enumerated by the canonical mechanism (template-mount), NOT by a proxy that happens to overlap most cases (field-presence on prior banner field).
17. **L-W5 (R1 Major #4):** Helper functions producing normalized dicts for downstream consumers MUST emit a stable key-set across ALL input branches. Permissive dict-passthrough creates shape drift between cassette/replay fixtures and production.
18. **L-W6 (R1 minor #1):** Conversion seams (dataclass→dict at a module boundary) MUST be owned by ONE task with clear contract; consumer tests should not duck-type both shapes.

**Codex-chain-surfaced additional insights (writing-plans-specific; not promoted to numbered lessons but worth capturing here for orchestrator triage):**

- **Per-service-write pipeline-exclusion recheck pattern.** Any new flow that performs ≥2 own-tx service writes in sequence MUST recheck `_check_pipeline_not_running` BEFORE EACH write. Plan-author missed this on R3 Major #4; existing backfill code at lines 745-751 + 966-974 + 1033-1036 is the canonical pattern.
- **Stamp-success tracking before fallback dispatch.** When wrapping a 2-step service sequence in try/except, the catch handler MUST know whether step 1 succeeded — otherwise step-1-failure misroutes through step-2's fallback semantics. Plan-author missed this on R3 Major #3; `stamp_succeeded` boolean tracker is the canonical pattern.
- **Counter wiring + CLI renderer parity.** New `BackfillSummary` counters must ALSO be threaded through `format_summary_block` (or equivalent operator-facing renderer). Tracking-without-rendering hides the surface from operators. Plan-author missed this on R4 Major #1.

---

## §8 CLAUDE.md status-line refresh draft text

```
**Phase 12.5 #1 writing-plans SHIPPED 2026-05-17** at `<integration-merge-sha>` (integration merge of `phase12-5-bundle-1-oqf-writing-plans` via `--no-ff`; 2 plan commits = 1 initial + 1 Codex-fix bundle; **5 Codex rounds → NO_NEW_CRITICAL_MAJOR** non-monotonic-Major shape (R1 1C/4M/1m → R2 0C/3M/1m → R3 0C/4M/2m → R4 0C/1M/2m → R5 0C/0M/2m sealed; R3 bump above R2 driven by downstream drift the R2 fixes themselves surfaced); **ZERO ACCEPT-WITH-RATIONALE banked** — all 1 Critical + 12 Major + 8 distinct Minor resolved with code-content fixes (matches Phase 12 Sub-bundle C.D + post-Phase-12 Sub-bundle 1/2 + Phase 12.5 #1 brainstorm clean-record precedent); ZERO Co-Authored-By footer drift across 2 commits; 1230-line plan at `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (above 600-900 brief target by ~330 lines — driven by R1 Critical #1 backfill-consumer scope expansion + R2-R4 acceptance-criteria depth). Single-sub-bundle decomposition; 11 tasks T-1.1..T-1.11; 14 pre-locked decisions verbatim-encoded; **25 binding invariants F1-F25** (6 NEW F20-F25 surfaced during Codex chain rounds 1-4); **18 forward-binding lessons** for executing-plans (12 inherited + 6 NEW writing-plans-surfaced L-W1..L-W6). Backfill consumer (`reconciliation_backfill.py:_handle_pass_2` + `run_backfill` orchestrator + `format_summary_block` renderer) identified as OPERATIONAL firing site per Codex R1 Critical #1 — initial pivot stays as defensive future-proofing. **Schema v19 UNCHANGED** (verified §13 audit + F1 invariant). Net projection refined: **~+102 fast tests + 1 slow E2E + ~+435 LOC** (was ~+85/+320 pre-Codex). 12 V2 candidates banked verbatim from spec §14; ZERO new V2 candidates surfaced this dispatch. **Executing-plans dispatch UNBLOCKED.**
```

(Insert actual integration merge SHA when orchestrator merges the branch.)

---

## §9 Schema impact verdict

**SCHEMA v19 UNCHANGED.**

Verified §13.1 audit (inherited from spec; pinned by plan F1 invariant + F19 plan-author schema additions escalation rule):
- `reconciliation_discrepancies.resolution` CHECK enum already includes `operator_resolved_ambiguity` (final state).
- `reconciliation_discrepancies.ambiguity_kind` CHECK enum already includes `multi_partial_vs_consolidated`.
- Cross-column CHECK satisfied (`operator_resolved_ambiguity` ↔ ambiguity_kind NOT NULL).
- `reconciliation_discrepancies.resolved_by` is free TEXT — new `'auto_tier1_multi_leg'` value requires NO migration.
- `reconciliation_corrections.applied_by` CHECK enum already includes `'auto'`.
- `reconciliation_corrections.correction_action` CHECK enum already includes `'auto_applied'`.
- `trade_events.event_type` CHECK enum already includes `'reconciliation_auto_correct'`.

**ZERO new schema modifications.** EXPECTED_SCHEMA_VERSION stays at 19. **F19 escalation rule was NOT triggered during writing-plans** — Codex chain did not surface any need for schema additions; all R1-R5 findings resolved at code-content layer (consumer-side only).

---

## §10 Composition-surface verification

Plan §C files-touched roster audited post-R5 (canonical surface enumeration per Codex R1-R4 fixes):

**Production code (touched by tasks):**
- `swing/trades/reconciliation_classifier.py` — T-1.1 + T-1.2 + T-1.11.
- `swing/trades/reconciliation_backfill.py` — T-1.3 (`_orders_to_classifier_payload`) + T-1.5 (`_handle_pass_2` + `run_backfill` orchestrator + `format_summary_block` renderer + `BackfillOutcome` + `BackfillSummary` per Codex R1 Critical #1 + R3 Major #2 + R4 Major #1 fixes).
- `swing/trades/reconciliation_auto_correct.py` — T-1.4 (`apply_tier2_resolution` outer + `_apply_tier2_resolution_inner` + `_build_tier2_correction` + every `_handle_*` helper + `_flip_discrepancy_to_resolved_ambiguity` + NEW `_validate_override_combo` helper + NEW `InvalidOverrideComboError` typed exception) + T-1.6 (sandbox short-circuit + `_SandboxAutoRedirectShortCircuit` sentinel + environment kwarg threading).
- `swing/trades/schwab_reconciliation.py` — T-1.5 (`_pivot_classify_and_dispatch_for_run` defensive future-proofing; line 429 docstring caveat; line 529 outer-catch ladder reordering).
- `swing/metrics/discrepancies.py` — T-1.7 (`count_recent_multi_leg_auto_corrections` helper).
- `swing/web/view_models/metrics/shared.py` — T-1.8 (`BaseLayoutVM` field).
- `swing/web/view_models/*.py` + `swing/web/view_models/metrics/*.py` + `swing/web/routes/account.py` — T-1.8 (≥17 VM + 3 route call sites per template-mount enumeration; Codex R1 Major #3 broadened scope).
- `swing/web/templates/base.html.j2` — T-1.9 (banner block).
- `swing/cli.py` — T-1.10 (`--resolved-by <value>` filter).
- `swing/pipeline/runner.py` — T-1.11 (`reconciliation_tier1_multi_leg_redirected_count` SQL).
- `swing/rendering/briefing.py` + `swing/rendering/briefing_md.py` — T-1.11 (`BriefingInputs` + `BriefingViewModel` + `## Reconciliation status` section).

**Surfaces explicitly NOT touched (UNCHANGED LOCK per spec §3):**
- `swing/integrations/schwab/mappers.py` — V2 mapper UNCHANGED.
- `swing/integrations/schwab/models.py` — `SchwabExecutionLeg` + `SchwabOrderResponse` UNCHANGED.
- Within `swing/trades/schwab_reconciliation.py`: helpers `_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate` + Path B sentinel emit UNCHANGED.
- `swing/web/routes/schwab.py` (`/schwab/status` + `/schwab/setup`) UNCHANGED.
- `swing/data/migrations/0019_*.sql` UNCHANGED (and no `0020_*.sql` introduced).
- `swing/trades/reconciliation_ambiguity_choices.py` — operator menu UNCHANGED.

---

## §11 Worktree teardown status

**Branch:** `phase12-5-bundle-1-oqf-writing-plans` — 2 commits ahead of `origin/main` (1063586 plan-draft + 6349486 Codex-fix-bundle).

**On-disk worktree:** `.worktrees/phase12-5-bundle-1-oqf-writing-plans/`. Branch matches cleanup-script regex `phase\d+[-_]` so `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` will identify it post-merge.

**Marker file:** `.copowers-subagent-active` at project root will be removed by the wrapper skill's Step 5 termination per the writing-plans dispatch brief §9 instruction.

**Post-merge action items** (orchestrator inheritance):

1. Operator-paired integration merge of `phase12-5-bundle-1-oqf-writing-plans` to `main` via `--no-ff`.
2. Update CLAUDE.md status-line per §8 draft text + insert actual merge SHA.
3. Update `docs/orchestrator-context.md` + `docs/phase3e-todo.md` pointer files with the plan's UNBLOCKED status.
4. Worktree teardown via `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (operator-driven).
5. Draft executing-plans dispatch brief for Phase 12.5 #1 — inherits plan §A T-1.1..T-1.11 + plan §D 14 locks + plan §F 25 invariants + plan §M 18 forward-binding lessons. Per plan §L scaffold.

---

## §12 Codex-chain insight summary (return-report supplement)

Beyond §2's tally, key Codex-surfaced insights worth capturing for project-wide pattern library:

- **R1 Critical #1** caught a true architectural gap the plan-author missed: the multi-leg auto-redirect classifier emit (n>=2 list-shape) can ONLY fire on the BACKFILL Pass-2 path. The initial pivot's `_extract_source_payload` returns None for `unmatched_*_fill` sentinels, so the recipe is never synthesized at pivot. The plan as initially drafted would have shipped dead-code dispatcher branches at pivot + a backfill dispatcher that ignored the recipe. **Lesson:** writing-plans MUST enumerate every dispatcher CONSUMER, not just the most obvious one.
- **R1 Major #1** caught a real spec-vs-plan contract divergence: the plan-author tried to align the new `InvalidOverrideComboError` with the existing pivot-loop graceful-degradation contract (`"never raises out"`), but the spec EXPLICITLY locked this exception to propagate out for fail-fast developer-bug detection. **Lesson:** spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering rules, NOT "PLAN DECISION" overrides; the cost of aligning with adjacent patterns is hiding the bug-detection signal.
- **R1 Major #2** caught a subtle wording lift — plan-author copied "(last 7 days)" wording from the adjacent `reconciliation_tier1_recent_count` line in the existing briefing.md `## Reconciliation status` section, but spec §11.2 locked the NEW counter to "this run" semantics. **Lesson:** spec-locked rendering text demands verbatim-substring assertions in tests; don't lift from neighbors.
- **R3 Major #3 + #4** are an example of a 2-step service sequence needing finer-grained failure routing than the plan-author anticipated. Wrapping both stamps in one try/except + applying §7.5 fallback uniformly would have caused stamp-failure to be misreported as `tier2_stamped` (with discrepancy still in `unresolved`). Splitting into two try/except blocks + tracking `stamp_succeeded` + adding a second `_check_pipeline_not_running` between steps closes both gaps. **Lesson:** any 2-step service sequence in plan acceptance criteria MUST enumerate per-step failure routing AND per-write pipeline-exclusion rechecks.
- **R4 Major #1** caught counter wiring + CLI renderer parity. New `BackfillSummary` counters get tracked but `format_summary_block` would hide them from operator. **Lesson:** new metric counter additions MUST be traced through to operator-facing renderers; tracking-without-rendering is a stealth-gap pattern.

These 5 insights compound into L-W1 through L-W6 forward-binding lessons (plan §M) for executing-plans inheritance.

---

*End of return report. Phase 12.5 #1 writing-plans CLOSES. Executing-plans dispatch UNBLOCKED.*
