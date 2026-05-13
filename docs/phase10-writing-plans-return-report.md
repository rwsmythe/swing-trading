# Phase 10 writing-plans — Return Report

**Dispatch:** `docs/phase10-writing-plans-dispatch-brief.md` (commit `4539011`).
**Branch:** `phase10-writing-plans` (worktree `.worktrees/phase10-writing-plans/`).
**Skill:** `copowers:writing-plans` (wraps `superpowers:writing-plans` + Codex MCP adversarial review).
**Status:** APPROVED for orchestrator integration triage. Codex chain reached **NO_NEW_CRITICAL_MAJOR at Round 6** (operator overrode default MAX_ROUNDS=5 to continue until clean). ZERO ACCEPT-WITH-RATIONALE positions banked.

---

## §1 Final HEAD on branch

```
154a66f docs(phase10): Phase 10 writing-plans — Codex R6 fix — 1 Minor (NO_NEW_CRITICAL_MAJOR reached)
```

Branch is **8 commits ahead** of dispatch baseline `4539011` after this return-report rewrite commit lands.

## §2 Commit count breakdown

| Commit | Type | Summary |
|---|---|---|
| `28d2a43` | plan-write | Initial plan @ 1581 lines |
| `f8b117b` | Codex R1 fix | 7 Major + 4 Minor addressed |
| `3a6c32c` | Codex R2 fix | 6 Major + 2 Minor addressed |
| `4607121` | Codex R3 fix | 3 Major + 3 Minor addressed |
| `6bb357e` | Codex R4 fix | 3 Major + 2 Minor addressed |
| `7f84fd3` | Codex R5 fix | 1 Major + 1 Minor addressed (at original MAX_ROUNDS boundary) |
| `b28a7d4` | return-report v1 | Initial return report drafted at R5 boundary |
| `154a66f` | Codex R6 fix | 1 Minor addressed → NO_NEW_CRITICAL_MAJOR verdict |
| (this commit) | return-report v2 | Final return report with R6 chain |

**Final plan size: 2008 lines** (within projected 1500-2500 range from dispatch brief §6).

## §3 Codex round chain — full convergent tapering

```
R1: 0 Critical / 7 Major / 4 Minor → ISSUES_FOUND
R2: 0 Critical / 6 Major / 2 Minor → ISSUES_FOUND
R3: 0 Critical / 3 Major / 3 Minor → ISSUES_FOUND
R4: 0 Critical / 3 Major / 2 Minor → ISSUES_FOUND
R5: 0 Critical / 1 Major / 1 Minor → ISSUES_FOUND  (original MAX_ROUNDS=5 boundary; operator overrode to continue)
R6: 0 Critical / 0 Major / 1 Minor → NO_NEW_CRITICAL_MAJOR
```

Major-finding progression: **7 → 6 → 3 → 3 → 1 → 0** (monotonic decrease; healthy convergence).

**ZERO Critical findings** across the entire chain — matches Phase 9 Sub-bundle E + Sub-bundle D (post-resolution) + Sub-bundle B + C "ZERO Critical" pattern.

**Codex thread ID** (preserved for any post-ship audit): `019e1fed-3c0a-74f2-8a16-b01ec95240fd`.

**Total findings resolved: 20 Major + 13 Minor across 6 rounds** = 33 issues addressed in-tree, ZERO ACCEPT-WITH-RATIONALE positions banked. R5→R6 transition was the cleanest: every R5 issue (1 Major + 1 Minor) resolved with surgical edits requiring no further design changes.

## §4 Plan task decomposition rationale

5 sub-bundles A → B → C → D → E with **33 tasks total** per dispatch brief §1.2 + plan §A.23:

| Sub-bundle | Scope | Task count | Gate surfaces | Est. dispatch hr |
|---|---|---|---|---|
| A | Shared honesty utility + metric infra + base-layout VM coverage + index page + discrepancies helper | 10 (T-A.0..T-A.9, plus T-A.7.1) | 1 (umbrella `/metrics` index) | 6-9 |
| B | §4.1 trade-process card + §4.2 hypothesis-progress card | 7 (T-B.0..T-B.6) | 2 surfaces | 8-12 |
| C | §4.3 tier-comparison + §4.7 deviation-outcome | 5 (T-C.0..T-C.4) | 2 surfaces | 6-10 |
| D | §4.4 capital-friction + §4.5 maturity-stage + §4.6 identification-funnel | 8 (T-D.0..T-D.7) | 3 surfaces + 1 PROVISIONAL/LIVE flip | 8-12 |
| E | §4.8 process-grade-trend + reconciliation badge + Phase 11 hand-off | 5 (T-E.0..T-E.4) | 1 surface + 1 banner integration | 6-9 |

**Per-bundle gate session ≤ 6 surfaces** (dispatch brief §1.3 budget); all 5 bundles fit one operator gate session each.

**Cross-bundle dependencies (binding per §A.23):**
- A → {B,C,D,E}: honesty utility + BaseLayoutVM mixin + discrepancies helper interface contracts.
- B → C (cohort scaffolding reuse; non-binding).
- B → D (per-cohort filter helper reuse).
- D → E (PROVISIONAL/LIVE resolver pattern reuse for per-run aggregation).
- §A.18 reconciliation badge — **dual-path** (Codex R2 Major #6 restructure): metrics VMs populate from sub-bundle landing; existing 6 base-layout VMs retrofit in E.

**Total cumulative test projection: +180..+285 fast tests across the arc** (final ~2947..~3052; below Phase 9's +503 because Phase 10 has zero schema work).

## §5 Open-questions disposition (spec §8 + dispatch brief §0.4 + §0.5)

All 7 spec §8 + 6 dispatch-brief §0.4/§0.5 questions disposed in plan §A.4 + §A.18:

| Question | Default-disposition | Orchestrator-decision-pending? |
|---|---|---|
| §8.1 fills.action='add' enum gap | DEFER (capital-floor convention) | NO |
| §8.2 web-form manual snapshot capture in V1 | NO — CLI-only | YES — operator may elect (+1 task in E) |
| §8.3 benchmark series capture | DEFER (n<60 trading days) | NO |
| §8.4 Corporate_Actions MVP | DEFER to Phase 10+ follow-up | YES — operator may elect (+1 Sub-bundle F, ~3-6hr) |
| §8.5 process_grade_rolling_N window | HARDCODE N=10 | NO |
| §8.6 lucky_violation_R on review form | DEFER to standalone follow-up | YES — operator may elect (+1 task in B) |
| §8.7 hypothesis-cohort decision-criteria automation | MANUAL text-rendering | NO |
| §0.5 §11.2(a) reconciliation badge on dashboard | YES in Sub-bundle E | NO |
| §0.5 §11.2(b) per-trade discrepancy indicator | DEFER | YES — operator may elect (+1 surface in E) |
| §0.5 §11.2(c) per-cohort filter | DEFER | YES — operator may elect (+1 toggle in C) |
| §0.5 §11.3 V1 supersession (full hypothesis history) | YES — supersede spec §3.2 V1-limit | NO (Phase 9 Sub-bundle C closed the gap) |
| §0.5 §11.4 dynamic PROVISIONAL badge | LOCKED per §A.6 | NO |

Plan accepts all default dispositions; flags **5 orchestrator-decision-pending items** for integration triage. None are writing-plans blockers.

## §6 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE positions banked.** Every one of the 20 Major findings across R1+R2+R3+R4+R5 was resolved with a code-content fix, NOT an "accept-with-rationale" position. R6 closed with 0 Major findings. This matches the cleanest Phase 9 arc bundles (D + E).

**One spec-amendment-pending position banked at §A.21:** the spec §3.8 + §5.2 mapping for `mistake_cost_R_rolling_N_total` (sum-class with bootstrap CI) is ambiguous; V1 renders as point-only. Banked as V2.1 §VII.F amendment candidate; should be raised at Phase 10 V2.1 review or as a standalone amendment dispatch. Same recon-doc-supersession pattern as Phase 9 Sub-bundle D §7 sector_industry anchor + Sub-bundle E §6.2 multi-line parser.

**One existing spec-V1-limitation supersession** at §A.11 (Phase 10 V1 surfaces full hypothesis transition history; spec §3.2's "single most-recent transition only" V1-limitation note is superseded since Phase 9 Sub-bundle C closed the capture gap). Banked as spec amendment candidate alongside the §A.21 item.

## §7 §A resolved-during-planning summary (empirical findings)

24 §A items locked during writing-plans. Highlights:

- **§A.0 — ZERO new schema.** Pre-plan grep + read of v17 schema confirmed every spec §3 metric input is either (a) a stored column OR (b) derivable from a shipped helper. `EXPECTED_SCHEMA_VERSION` stays at 17. NO `0018_*.sql` migration. (Counter to early Explore-agent flag of 9 "MISSING" columns; verified directly that they are derivable, not missing.)
- **§A.0.1 — Per-pipeline-run aggregates derived on-the-fly via JOIN.** Historical reconstruction limitation locked: V1 multi-run trends are BEST-EFFORT against current trade state; today's-run point-in-time fully accurate; trend disclosure footnote required.
- **§A.5 — Risk_policy LIVE vs AT-TRADE-TIME read split.** Per-metric assignment binding.
- **§A.5.1 — Cohort-aggregate `cumulative_R_pct_of_capital` semantics** (Codex R1 Major #2 fix): per-trade contribution divided by ITS at-trade-time capital_floor; sum of per-trade contributions. NEVER LIVE policy + NEVER averaged.
- **§A.6 — Dynamic PROVISIONAL/LIVE badge resolver.** Backward-looking `last_completed_session(now)` per §A.15 alignment.
- **§A.7 — Honesty utility module interface locked** (`render_class_d` extended with `underlying_class` parameter for Class B/A/C/point dispatching per §A.21).
- **§A.8 + §A.18 — BaseLayoutVM mixin + reconciliation badge dual-population path** (Codex R2 Major #6 restructure): metrics VMs populate from sub-bundle landing; 6 existing VMs retrofit in E.
- **§A.10 — §4.8 chart rendering: inline SVG default-disposition** (avoids matplotlib mathtext gotcha entirely).
- **§A.11 — Hypothesis-progress card supersedes spec §3.2 V1-limitation** (Phase 9 Sub-bundle C closed the gap).
- **§A.11.1 — Paused-status temporal semantics** (Codex R1 Major #4 fix): V1 includes ALL trades labeled with cohort regardless of cohort status at trade-time.
- **§A.19 — `risk_feasibility_blocked_rate` SQL** (Codex R1 Major #1 + R2 Major #3 + R3 Major #3 + R4 Majors #1+#2+#3 fix sequence): correct numerator predicate; `na`-on-other-criteria fail-equivalent; partial-criterion-row defensive guard with set-membership; `na`-on-risk-feasibility excluded; `EXPECTED_CRITERIA_NAMES` enumerated explicitly across all 18 names emitted by canonical pipeline writer.
- **§A.21 — §3.8 rolling-metric Class assignments** (Codex R1 Major #6 + R3 Major #1 + R5 Major #1): per-metric `underlying_class` mapping mirroring spec §5.2 Class B; one explicit deviation (`mistake_cost_R_rolling_N_total` point-only) banked as V2.1 §VII.F amendment candidate.

## §8 Watch items for orchestrator (lock before executing-plans dispatch)

1. **Sub-bundle A is foundational + binds B/C/D/E.** Dispatch A first; B/C/D/E can mock-against-A's interface. Failure to land A's interface contracts (`honesty.py`, `BaseLayoutVM`, `discrepancies.py:count_unresolved_material`) per §A.7 + §A.8 + §A.18 will cascade into B/C/D/E rework.

2. **Five orchestrator-decision-pending items** at integration triage (per §5 above). Each enumerated with default-disposition + cost-if-elected. Operator elections at integration triage may add tasks to specific sub-bundles before dispatch.

3. **`verify_phase10.py` must land in T-A.9.** Cross-platform Python script per §J.2 is the executing-plans dispatch acceptance gate. Subsequent sub-bundles inherit + invoke at end of dispatch.

4. **Operator-witnessed verification gate per surface is BINDING** (spec §4.9 + §A.9 + §I.15). 9 surfaces total across A+B+C+D+E (1+2+2+3+1). Per-bundle gate session ≤ 6 surfaces → 5 separate operator gate sessions, one per sub-bundle.

5. **PROVISIONAL/LIVE flip operator-witnessed gate (S5 in Sub-bundle D)** requires operator to record an `account_equity_snapshot` via `swing account snapshot record` mid-gate to verify the dynamic flip. Operator may want to record one or more fresh snapshots PRE-Sub-bundle-D ship so the flip mechanic is operator-visible.

6. **Two spec amendments pending V2.1 §VII.F routing** (per §6 above): (a) §A.21 `mistake_cost_R_rolling_N_total` Class assignment for sum metrics; (b) §A.11 hypothesis transition timeline supersession of spec §3.2 V1-limit. Both can be raised post-Phase-10-arc-close as standalone amendment dispatches OR rolled into Phase 11 brainstorm scope.

7. **Reconciliation discrepancy badge cross-bundle integration** is the highest-risk integration step in the arc (15 VM constructors total: 9 metrics + 6 existing). The cross-bundle pin is the un-skipped `test_existing_dashboard_vm_has_unresolved_material_field` from T-A.7. Verify at T-E.3 the un-skip lands + the regression test passes.

8. **Historical-reconstruction trend footnote** (per §A.0.1 + §I.7) is a USER-FACING text element. Operator should review the proposed footnote text "Trend computed from current trade state; historical points approximate where state has changed since the run." at integration triage; minor wording revision is in-scope without re-Codex.

9. **§A.21 `mistake_cost_R_rolling_N_total` point-only rendering** is the ONE deliberate spec-conformance deviation in the plan. Marked clearly. If Codex reviewer at executing-plans dispatch flags it, point them to plan §A.21 + return-report §6.

10. **3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py`** persist UNCHANGED through the arc. Banked separately for triage; NOT a Phase 10 concern.

## §9 Worktree teardown status

Worktree created at `.worktrees/phase10-writing-plans/` per dispatch brief §2.1. Branch `phase10-writing-plans` 8 commits ahead of `main` after this return-report rewrite lands.

**Marker file** at `c:/Users/rwsmy/swing-trading/.copowers-subagent-active` will be removed at Step 10 of dispatch brief §5 (after this return report commits + before signaling orchestrator).

**Worktree teardown follows orchestrator-decision pattern** per Phase 6/7/8/9 lessons: expected ACL-locked husk on Windows after merge; orchestrator commands the cleanup post-merge.

**No push to origin from worktree** per dispatch brief constraints. Orchestrator owns merge + integration.

## §10 Phase 11 hand-off note candidates surfaced during planning

Per dispatch brief §9 sequencing 8 ✓ → 9 ✓ → 10 (this dispatch) → 11 (TBD). Phase 11 candidates surfaced or referenced during Phase 10 writing-plans:

1. **Schwab API Phase A** (banked pre-Phase-10 in `docs/phase3e-todo.md` 2026-05-04). Replaces TOS-CSV reconciliation primary path; replaces manual `account_equity_snapshots` with broker-authoritative source; would naturally flip more PROVISIONAL → LIVE situations on Phase 10 Sub-bundle D surfaces.

2. **Schwab "since-inception" Account Statement ingestion** (banked 2026-05-12 per phase3e-todo). V2 candidate; could backfill `cash_movements` + `account_equity_snapshots` historical series + reconcile fills. Would extend Phase 10 multi-run trend accuracy by enabling true historical reconstruction (closes the §A.0.1 best-effort limitation).

3. **`account_equity_snapshots.equity_dollars` semantic formalization** (banked 2026-05-12). Cash-basis vs net-liq disambiguation. Would refine Phase 10 §A.6 PROVISIONAL/LIVE contract semantics.

4. **2 spec amendments pending V2.1 §VII.F routing** from Phase 10 (per §6 above): §A.21 sum-metric Class + §A.11 hypothesis transition timeline supersession.

5. **Operator-elective Phase 10 V1 add-ons** (per §5 / §A.4 default-defers): Corporate_Actions MVP; manual snapshot web-form capture; `lucky_violation_R` on review form; per-trade discrepancy indicator; per-cohort discrepancy filter. Operator may elect at Phase 10 integration triage OR roll into a Phase 10+ small follow-up dispatch.

6. **§A.11.1 V2 candidate** banked: per-cohort filter "Exclude trades stamped during paused intervals" — operator-elective UI toggle. Useful family complement to the per-cohort "exclude trades with unresolved discrepancies" filter.

7. **`watch_take_rate_per_run` symmetric metric** (Codex R1 Minor #2 + R2 Major #2): banked as V2 candidate; spec §3.6 doesn't currently define it, but operator may elect to add for symmetry with `aplus_take_rate_per_run`.

8. **Per-pipeline-run aggregation table** (per §A.0.1 + §I.7): if multi-run trend queries exceed 500ms p95 at gate, V2 candidate to add `pipeline_runs_metrics_capital_aggregate` table OR extend `pipeline_runs` columns. Operator-paced; not Phase 10 V1 work.

---

## §11 Lessons banked during writing-plans

### §11.1 New CLAUDE.md gotcha promotion candidates

NONE arise from writing-plans alone (no code shipped this dispatch). Will surface at executing-plans dispatch returns if implementation reveals new failure modes.

### §11.2 Dispatch-brief-author lessons

1. **Empirical schema verification is structurally non-optional + must verify-via-derivation, NOT just direct-column-presence.** Initial Explore-agent recon flagged 9 "MISSING" columns in the v17 schema. Direct verification revealed all 9 are DERIVABLE from shipped helpers (`derived_metrics.py`, `equity.py`, `review.py`). Without the verify-via-derivation pass, the plan would have proposed schema additions that contradict §A.0's lock. Generalization for future writing-plans dispatches: every "MISSING" finding from a recon agent MUST be re-verified by the plan author before being written into a plan §A finding.

2. **Codex propagation lag** between §A locks + per-task acceptance criteria: every §A revision in R1-R4 needed mirror updates in the relevant Task acceptance + test list. R5 caught the last propagation gap (§A.19 tests not mirrored in Task D.1 list); R6 caught a residual list-mirror omission (§A.20 / Task D.5 trend test). Future writing-plans: when updating a §A lock, search-grep for ALL referencing tasks + update their test lists in the same commit.

3. **Cross-bundle restructure (§A.18 R2 Major #6)** showed the value of moving foundational helpers to Sub-bundle A even when the user-facing surface lands in Sub-bundle E. Eliminates per-metrics-VM retrofit in E + makes the cross-bundle pin a clean "field exists by definition + populated from start" rather than "every VM constructor must be touched in E".

4. **Spec-conformance vs spec-amendment posture**: a single deliberate deviation from spec (§A.21 `mistake_cost_R_rolling_N_total` point-only) is acceptable when (a) flagged explicitly in plan §A, (b) banked as V2.1 §VII.F amendment candidate at return report, (c) NOT described as "spec-conformant" in plan task acceptance. Codex R1 caught the original draft's silent deviation; R5 propagation pass made the deviation EXPLICIT in test acceptance.

5. **Operator-overridable MAX_ROUNDS budget**: copowers default config caps at MAX_ROUNDS=5. R5 ended with 1 Major + 1 Minor outstanding which were addressed in-tree pre-termination. Operator opted to continue past the budget; R6 surfaced 1 Minor (test list consistency) + verdict NO_NEW_CRITICAL_MAJOR. Lesson for future dispatches: when the R5 outstanding-issue count is small + clearly tractable, an additional R6 round is high-value (catches residual propagation gaps from the R5 fixes themselves).

### §11.3 Phase 9 forward-binding lesson application checklist (CLAUDE.md Gotchas + dispatch brief §0.3 + §7)

| Lesson | Application in plan |
|---|---|
| `__post_init__` validators | Locked at §A.7 for `WilsonCI`, `BootstrapCI`, `SuppressedMetric`. |
| Service-layer transaction discipline | By-construction satisfied; V1 has 0 new write paths (per §I.11). |
| NO `INSERT OR REPLACE` | By-construction satisfied (per §I.9); verify_phase10.py grep enforces. |
| Server-stamping at handler entry | By-construction satisfied; V1 has 0 new POST forms (per §I.12). |
| Composition-surface enumeration via `^def` grep | Pre-plan grep done; §A.7 + §A.18 enumerate consumers explicitly. |
| Empirical-verification of brief assertions | Done at §A.0; counter-verified against Explore agent's "MISSING" finding. |
| Form-render hidden anchors round-trip | By-construction satisfied (per §I.12). |
| POST-time recompute TOCTOU | By-construction satisfied (per §I.12). |
| Test fixtures USERPROFILE+HOME monkeypatch | By-construction satisfied (per §I.10). |
| HTMX browser-only failure surfaces | By-construction avoided (per §A.9 + §I.6 — no OOB-swap, no embedded forms). |
| `<tr>`-leading HTMX response | By-construction avoided (per §I.6). |
| matplotlib mathtext gotcha | By-construction avoided (per §A.10 — inline SVG default). |
| Session-anchor read/write predicate alignment | Locked at §A.15 + §A.6 + Task D.1/D.2 acceptance + Task D.5 (Codex R3 Major #3 + R4 Major #3 + R5 Minor #1 sequence). |
| `base.html.j2` shared field requires VM update everywhere | Locked at §A.8 + §A.18 + Task A.7 regression test (un-skipped at T-E.3). |

All 14 forward-binding lessons applied at the plan structural level. Codex chain did not surface any lesson violations.

---

*End of return report. Marker file removal + orchestrator signal pending.*
