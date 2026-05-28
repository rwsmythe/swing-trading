# Phase 14 Sub-bundle 1 -- Data-wiring -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 1 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed implementation plan to ship three data-wiring fixes to production code + tests: **V2.G3** (VSAT lost Sector/Industry on `/dashboard`); **V2.G4** (Refresh weather chart SPY error); **P14.N3** (daily-management Capital % PROVISIONAL/LIVE/policy-missing badge contract). Plan is dispatch-ready per writing-plans return report §15.

**Brief:** `docs/phase14-sub-bundle-1-data-wiring-executing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; brainstorm SHIPPED at `9104bb8`; writing-plans SHIPPED at `b2546d5`; housekeeping at `51013a6`. Main HEAD at executing-plans dispatch time: `51013a6`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING; ~599+ cumulative ZERO Co-Authored-By trailer drift; 46th cumulative C.C lesson #6 validation NOTABLE at writing-plans SHIPPED; Schema v21 LOCKED (escalation rule per plan §K if surface reveals unavoidable migration); L2 LOCK preserved + REINFORCED via plan §G.T-4.1 multiset Counter source-grep design.

**Expected duration:** ~3-6 hours executing-plans implementation + ~30-90 min Codex chain. Plan §G enumerates 8 per-task slices T-1.1 + T-1.2 + T-1.3 OPTIONAL + T-2.1 + T-3.1 + T-4.1 + T-4.2; ~8-12 commits + ~42-46 fast tests projected. Operator-paced; SHIPS production code + tests under `swing/` + `tests/`.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief.
- `copowers:executing-plans` wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after all tasks complete.
- Codex chain count: **SINGLE chain at end** per Sec 9.1 Q7 LOCK + gotcha #36 caveat for pure UX/wiring sub-bundles without analytical artifacts.
- Output: production code + tests + return report at `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md`** -- the LOCKed plan (~3851 lines; AUTHORITATIVE for implementation; Codex R5 NO_NEW_CRITICAL_MAJOR convergence). Especially:
   - §A Goals + non-goals
   - §B File map (per-file diff projections with file:line citations against current production)
   - §C Surface-by-surface integration analysis
   - §E Operator-paired LOCKs reverification table (23 LOCKs preserved verbatim)
   - §F Cumulative discipline + watch items applied per task
   - **§G Per-task slicing (T-1.1 + T-1.2 + T-1.3 OPTIONAL + T-2.1 + T-3.1 + T-4.1 + T-4.2; bite-sized TDD step-checkbox slicing; BINDING substrate for executing-plans dispatch)**
   - §G.0 Commit cadence preface
   - §H Test surface (per-task fast-test count distribution; ~42-46 fast target)
   - §I Operator-witnessed gate runbook (S1-S5 + S5a/S5b/S5c per-state split for PROVISIONAL/LIVE/policy-missing cases)
   - §J Codex MCP single-chain placement
   - §K Schema impact analysis (v21 LOCK + escalation rule)
   - §L Test fixture strategy per item
   - §M Forward-binding lessons #1-#13 (9 inherited + 4 NEW from writing-plans return report §9; LOAD-BEARING per task)
   - §N Self-review checklist (pre-Codex)

3. **`docs/phase14-sub-bundle-1-data-wiring-writing-plans-return-report.md`** -- return report. Especially:
   - §5 OQ dispositions (all 8 OQs locked at plan-authoring time)
   - §7 Per-task acceptance criteria summary
   - §9 Forward-binding lessons #10-#13 (NEW at writing-plans; carry forward)
   - §15 Executing-plans dispatch readiness summary

4. **`docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md`** -- brainstorm spec (~810 lines; reference for architectural rationale). Especially:
   - §2 Pre-locked operator decisions (verbatim binding clauses; inherited at plan §E)
   - §4-§6 Per-item designs (V2.G3 + V2.G4 + P14.N3)
   - §10.1 Single-dispatch decomposition LOCK
   - §13 V1 simplifications + V2 candidates banked (do NOT design in V1)

5. **`docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md`** §8 Forward-binding lessons #1-#9 -- inherited at plan §M.

6. **`docs/phase14-sub-bundle-1-data-wiring-writing-plans-dispatch-brief.md`** §1 LOCKs + §5 watch items -- writing-plans-phase locks now carrying forward to executing-plans.

7. **`docs/phase14-sub-bundle-1-data-wiring-brainstorm-dispatch-brief.md`** §1 LOCKs -- brainstorm-phase sub-bundle LOCKs (§1.1 scope; §1.5 Schema v21 LOCKED escalation rule; §1.6 DHA/DHC carve-out).

8. **`docs/phase14-commissioning-brief.md`** Sec 9.1 LOCKs (binding for all Phase 14 sub-bundles).

9. **`CLAUDE.md`** -- gotchas cited at plan §F (per task); all 37 cumulative gotchas BINDING for the 47th cumulative C.C lesson #6 validation slot consumed by this dispatch.

10. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
    - `feedback_orchestrator_qa_implementer_product` (informational)
    - `feedback_verify_regression_test_arithmetic` (compute test arithmetic both pre/post-fix for V2.G4 narrow-exception + P14.N3 PROVISIONAL/LIVE/policy-missing state flip)
    - `feedback_swing_db_migrate_explicit` (informational; v21 LOCKED so likely n/a)
    - `feedback_worktree_cli_invocation` (python -m swing.cli, NOT bare `swing`)
    - `project_capital_risk_floor` ($7500 floor; relevant for P14.N3 PROVISIONAL fallback denominator semantic)
    - `project_applied_research_arc_2026-05-27` (substantive context on why Phase 14 prioritizes UX + wiring)

11. **Production code surfaces** verified by writing-plans implementer at plan §A.3 14-row signature-verification table. RE-VERIFY at executing-plans start to catch any drift since the writing-plans merge:
    - `swing/data/repos/trades.py:155 insert_trade_with_event(conn, trade, *, event_ts, rationale=None)` (R2.M#3+R3.M#1 LOCK)
    - `swing/data/repos/risk_policy.py:28 NoActivePolicyError` + `:98 get_active_policy(conn) -> RiskPolicy` (R1.M#1+R2.M#1+M#2 LOCK)
    - `swing/web/view_models/trades.py @dataclass DailyManagementTileVM` (location verified vs `daily_management.py` per R2.M#1)
    - `swing/web/view_models/dashboard.py:1336 build_dashboard import` + `:1390 tile inline construction`
    - `swing/metrics/equity_resolver.py:32-79 resolve_live_capital_denominator_dollars`
    - `swing/metrics/maturity.py:197-219 denominator-stamping pattern` + `:296 _compute_position_util_pct` (PERCENT semantic; do NOT use here)
    - `swing/trades/daily_management.py:381 compute_position_capital_utilization` (PROPORTION semantic; LOCKED at R3.M1)
    - `swing/web/routes/dashboard.py` weather-chart/refresh handler (no module-level logger pre-fix; add per T-2.1)
    - `swing/web/templates/daily_management.html.j2` line 92 (multiplies proportion by 100)
    - `swing/data/repos/candidates.py` (NEW helper landing site per T-1.1)

---

## §1 LOCKs inherited (BINDING through executing-plans; DO NOT re-litigate)

All 23 LOCKs preserved verbatim through 5 Codex rounds at writing-plans phase per plan §E. Cumulative LOCK chain:

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = data-wiring (Sub-bundle 1) -> temporal log V1+ -> charts -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q6** close-out = all 5 sub-bundles merged + operator browser-witnessed verification at each merge
- **Q7** Codex chain count = orchestrator discretion per sub-bundle; **SINGLE chain at end** for Sub-bundle 1

### §1.2 Brainstorm spec §2 LOCKs
- V2.G3 design = backfill CLI (Fix A) FIRST; VM fallback (Fix B) banked as Fix-1b (T-1.3 OPTIONAL)
- V2.G3 backfill = STRICT all-or-nothing semantic (AND-empty SELECT; SKIP_PARTIAL_EMPTY for partial-empty rows)
- V2.G3 restore-SQL artifact = MANDATORY emission at dry-run AND before apply (defense-in-depth)
- V2.G4 design = call-signature fix + module-level logger addition + narrow `ValueError`-only catch
- V2.G4 narrow exception = programming errors (TypeError, AttributeError, KeyError, RuntimeError) propagate to FastAPI 500
- P14.N3 design = denominator-stamping per `maturity.py:197-219` + PROPORTION-unit semantic + tooltip surface

### §1.3 Brainstorm dispatch brief §1 LOCKs
- **§1.1** scope = V2.G3 + V2.G4 + P14.N3 ONLY
- **§1.2** Codex single chain at end
- **§1.3** Serial execution
- **§1.4** Operator-witnessed gate at merge
- **§1.5** Schema v21 LOCKED; ESCALATE if any item surfaces unavoidable migration
- **§1.6** DHA/DHC legacy carve-out via `SKIP_NO_CANDIDATES_ROW` action label (no hardcoded ticker list)

### §1.4 Writing-plans dispatch brief §1.5 phase-specific LOCKs
- **L1** Single executing-plans dispatch (NOT 2+)
- **L2** Bite-sized per-task slicing (each task 3-5 commits max)
- **L3** Test count target ~34-46 fast tests
- **L4** Commit cadence target ~8-12 commits total
- **L5** Plan §E cumulative LOCK summary table preserved (23 LOCKs)

### §1.5 Plan §A semantic-extension acknowledgement (NOT a scope re-litigation)
- P14.N3 VM contract expanded from spec's locked 3 fields to 4 fields (NEW `position_capital_policy_missing` for NoActivePolicyError edge case per Codex R2.M#1+M#2 LOCK)
- Semantic extension consistent with spec §6.4 second bullet (anticipates NoActivePolicyError caveat)
- Plan §E reverification + return report §4 explicit: NOT a scope re-litigation

---

## §2 Scope inheritance from plan §G (BINDING substrate)

Plan §G is the AUTHORITATIVE substrate. Implement task-by-task in the order locked:

| Task | Item | Scope | Commits | Tests |
|---|---|---|---|---|
| **T-1.1** | V2.G3 | NEW `get_latest_sector_industry_per_ticker(conn, tickers: Sequence[str]) -> dict[str, CandidateSectorIndustryRecord]` repo helper at `swing/data/repos/candidates.py` + `CandidateSectorIndustryRecord` frozen dataclass (`sector, industry, candidate_id, evaluation_run_id` provenance per R1.M#6 LOCK) | ~2-3 | ~5 |
| **T-1.2** | V2.G3 | NEW CLI subcommand `swing diagnose backfill-trades-sector-industry [--dry-run / --apply]` + restore-SQL artifact emission (dry-run AND before apply per R1.M3 LOCK) + STRICT AND-empty SELECT + SKIP_PARTIAL_EMPTY action label + DHA/DHC SKIP_NO_CANDIDATES_ROW carve-out | ~2-3 | ~9 |
| **T-1.3 OPTIONAL** | V2.G3 | VM fallback Fix-1b at `swing/web/view_models/open_positions_row.py` -- **DO NOT pre-ship**; trigger only if operator-gate S2 surfaces residual empty cells post-T-1.2 apply | ~1-2 | ~3-4 |
| **T-2.1** | V2.G4 | 3 surgical edits at `swing/web/routes/dashboard.py`: (a) module-level `import logging; log = logging.getLogger(__name__)` per R3.M2 LOCK (SAME commit as the log.warning calls -- do NOT split per forward-binding lesson #4); (b) call-signature fix `get_or_fetch([benchmark])` -> `get_or_fetch(ticker=benchmark)`; (c) narrow `ValueError`-only catch with `log.warning` degraded path; (d) NEW pytest fixture `test_client_with_pipeline_run_no_raise` using `TestClient(app, raise_server_exceptions=False)` per R1.M#3 LOCK for FastAPI 500 propagation tests | ~1-2 | ~7-8 |
| **T-3.1** | P14.N3 | `DailyManagementTileVM` extended with 4 NEW fields (per spec 3 + 1 NEW `position_capital_policy_missing` per R2.M#1+M#2 LOCK); inline build at `swing/web/view_models/dashboard.py:1390-1417` populates via `maturity.py:197-219` denominator-stamping mirror + NoActivePolicyError try/except + PROPORTION-unit preserved (R3.M1 LOCK); template if/elif chain (policy_missing -> snapshot_missing -> no badge); focusable `<button type="button">` with ARIA replacing inline `<span>` per R1.M#2 LOCK | ~2-3 | ~12-14 |
| **T-4.1** | All | NEW multiset Counter L2 LOCK parametric source-grep test asserting HEAD multiset SUBSET of `bf7e071` commissioning baseline for `schwabdev.Client.` references under `swing/` per R1.M#5 + R2.M#6 LOCKs | ~1 | ~2 |
| **T-4.2** | All | Integration tests + return report at `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md` | ~1 | ~2 |

**Total: ~8-12 commits + ~42-46 fast tests** projected.

**Do NOT widen task scope.** Each task ships per plan §G acceptance criteria + step-checkbox TDD slicing. Do NOT add work beyond what plan §G prescribes per task.

---

## §3 Watch items + cumulative discipline (BINDING through executing-plans phase)

**13 forward-binding lessons inherited from prior phases (plan §M; LOAD-BEARING at each per-task commit):**

1. Brief-vs-production-function-signature verification (gotcha #17) -- RE-GREP each cited surface at executing-plans start to detect drift since writing-plans merge
2. Cumulative regression cascade audit (gotcha #21 / Expansion #13) -- post-fix sweep at each Codex round
3. Percent-vs-proportion unit lock (R3.M1 LOCK) -- T-3.1 step 9 BINDING test asserts `< 50%` rendering for 0.15 proportion fixture
4. Module-level logger addition (R3.M2 LOCK) -- T-2.1 SAME-commit landing
5. Restore-SQL artifact discipline (R1.M3 LOCK) -- T-1.2 step 4 + step 6 + step 11
6. Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 LOCK) -- T-1.2 step 3 + step 4 + step 5
7. Browser-only HTMX failure surface preservation -- T-2.1 step 9 regression test
8. Programming-error propagation discipline (R2.M2 LOCK) -- T-2.1 step 6 + step 7 + step 8
9. Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 LOCK) -- plan §I S5a/S5b/S5c split
10. **NoActivePolicyError fallback semantic-extension audit** (writing-plans R1.M#1 + R2.M#1+M#2 + R4.M#1 cumulative 4-round lesson) -- T-3.1 4th VM field + dedicated template branch + honest recovery tooltip
11. **TestClient `raise_server_exceptions=False` discipline** (writing-plans R1.M#3 LOCK) -- T-2.1 NEW fixture + propagation-to-500 tests
12. **Production API call-graph cascade verification at every Codex round** (writing-plans R2.M#3+M#4+M#5 + R3.M#1+M#2+M#3+M#4 cumulative 4-round lesson) -- at every fix bundle, IMMEDIATELY grep the production module + verify (a) function name; (b) parameter names + kinds; (c) parameter types; (d) caller-side preconditions; (e) recovery semantics
13. **Multiset-comparison discipline for source-grep regression tests** (writing-plans R1.M#5 + R2.M#6 cumulative 2-round lesson) -- T-4.1 multiset Counter SUBSET assertion (NOT count-only OR set-only)

**Cumulative discipline streaks to preserve:**
- ~599+ cumulative ZERO `Co-Authored-By` footer trailer drift (preserve through executing-plans phase + merge commit)
- Schema v21 LOCKED (ESCALATE per plan §K if surface reveals unavoidable migration; do NOT silently propose v22)
- L2 LOCK preserved (parametric source-grep test designed at T-4.1; SUBSET assertion against `bf7e071` baseline)
- ASCII discipline complete across NEW files per gotcha #32 (declare scope in return report)
- gotcha #33 banned-terms LOCK across all narrative output

**47th cumulative C.C lesson #6 validation slot consumed by this dispatch.** Pre-Codex orchestrator-side review applied all 19+ expansion candidates at writing-plans phase + caught 18 MAJOR; executing-plans Codex may surface additional defects against actual production code.

---

## §4 Codex MCP chain placement

**SINGLE chain at end** of executing-plans phase per Sec 9.1 Q7 LOCK + plan §J + gotcha #36 caveat ("production-feature dispatches without a substantive emitted artifact may continue to use single-chain placement at orchestrator discretion").

**Target convergence: 2-5 rounds.** Plan §J anticipates this range (writing-plans Codex took 5 rounds; executing-plans against production code may have similar or higher depth).

**Codex round expectations:**
- R1: production code drift catches (signature, import, dataclass shape) + initial test coverage gaps
- R2+: cascade verification per forward-binding lesson #12 (grep production at each fix bundle)
- Convergence sentinel: `NO_NEW_CRITICAL_MAJOR`

**If Codex finds defects requiring schema migration** (NOT anticipated; plan §K escalation rule): STOP + escalate to orchestrator. Do NOT silently propose v22.

---

## §5 Operator-witnessed gate (per plan §I + spec §10.5)

After all tasks ship + Codex converges + return report drafted, orchestrator returns to operator for operator-witnessed gate. Plan §I enumerates the runbook:

- **S1**: `pytest -m "not slow" -q` green (~5870+ fast tests including ~42-46 NEW) + `ruff check swing/` clean
- **S2**: V2.G3 -- VSAT row in `/dashboard` open-positions table renders non-NULL Sector + Industry post-backfill; DHA legacy NULL still gracefully renders (em-dash)
- **S3**: V2.G3 -- `python -m swing diagnose backfill-trades-sector-industry --dry-run` produces operator-friendly table + restore-SQL artifact emitted at `exports/diagnostics/backfill-trades-sector-industry-restore-<ISO>.sql`
- **S4**: V2.G4 -- `/dashboard` "Refresh weather chart" button produces fresh SPY weather chart SVG (NOT the "no OHLCV bars" error); narrow `ValueError`-only catch verified via test
- **S5a**: P14.N3 PROVISIONAL case -- plant no `account_equity_snapshots` row; reload `/daily-management`; assert PROVISIONAL badge present + tooltip describes clear-condition (`swing schwab fetch --snapshot` OR equivalent)
- **S5b**: P14.N3 LIVE case -- plant `account_equity_snapshots` row covering today's session; reload; assert PROVISIONAL badge NOT present + Capital % value renders correctly via PROPORTION semantic (recomputed proportion when stored denominator diverges)
- **S5c**: P14.N3 policy-missing case (NEW per R2.M#1+M#2 LOCK) -- delete all rows from `risk_policy` (or set all `is_active=0`); reload `/daily-management`; assert policy-missing badge present + EXTRA-CAVEAT tooltip describes the schema-corrupted state honestly

**Gate-pass triggers**: operator confirms "all surfaces pass" / "gate passed" / "all good" / equivalent -> orchestrator merges per `feedback_orchestrator_performs_merge` BINDING (hardened to cover all 3 copowers phases 2026-05-28).

---

## §6 Done criteria

Executing-plans phase is DONE when:

1. All 6 NON-OPTIONAL tasks shipped (T-1.1 + T-1.2 + T-2.1 + T-3.1 + T-4.1 + T-4.2); T-1.3 deferred to operator-gate-trigger
2. Codex MCP single chain CONVERGED at NO_NEW_CRITICAL_MAJOR
3. ~5870+ fast tests green on branch (baseline ~5828 + ~42-46 NEW); `python -m pytest -m "not slow" -q`
4. `ruff check swing/` clean (preserve 0 E501 baseline)
5. ZERO Co-Authored-By trailer drift across all branch commits (verify via `%(trailers)` inspection)
6. Schema v21 LOCKED (no `swing/data/migrations/0022_*.sql` added)
7. L2 LOCK preserved (multiset Counter test at T-4.1 PASSES against `bf7e071` baseline)
8. Return report at `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md` complete per §7 below
9. Branch pushed to origin; ready for orchestrator-side QA + operator-witnessed gate

---

## §7 Return report shape

After Codex chain converges + before merge return-trip:

1. Final HEAD on branch + commit count breakdown (per-commit Codex round attribution)
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper)
3. Per-task completion summary (T-1.1, T-1.2, T-2.1, T-3.1, T-4.1, T-4.2; T-1.3 deferred status)
4. Test surface verification (~42-46 fast tests projected; per-task actual count distribution; total before + after)
5. Pre-locked operator decisions verbatim verification (23 LOCKs preserved per plan §E)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO acceptances strongly preferred per writing-plans precedent)
7. Production-code citations verified at task completion (forward-binding lesson #1; per-task signature re-verification)
8. Schema impact verdict (v21 unchanged; explicit confirmation via direct file count)
9. L2 LOCK verification (multiset Counter test PASSES against `bf7e071` baseline; cite test name + result)
10. Operator-witnessed gate readiness (S1-S5 + S5a/S5b/S5c runbook ready; cite plan §I)
11. NEW forward-binding lessons banked (if any; for next-sub-bundle dispatches + CLAUDE.md gotcha banking consideration)
12. ASCII discipline scope (per gotcha #32; enumerate NEW + MODIFIED files)
13. Cumulative gotcha set application summary (per task)
14. Worktree teardown status
15. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits)
16. CLAUDE.md status-line refresh draft text (informational; orchestrator decides whether to apply at major milestone)
17. Operator-witnessed gate handback summary

---

## §8 OUT OF SCOPE (do not implement)

- T-1.3 OPTIONAL UNLESS operator-gate S2 surfaces residual empty cells post-T-1.2 apply
- V2 candidates banked at brainstorm return report §7 (8 candidates; V2-only)
- Schema migrations beyond v21 (escalation rule per plan §K + brief §1.5)
- Sub-bundle 2 / 3 / 4 / 5 scope (per Sec 9.1 Q1 LOCK; serial execution)
- Phase 15+ scope (P14.N7 schwabdev checker thread resilience; substrate-size augmentation; etc.)
- V2.G1 / V2.G2 / P14.N1 / P14.N2 / P14.N4 / CR.1 / P14.N6 / P14.N5 (per Sub-bundle 1 §1.1 scope LOCK)
- HTMX surface introductions (V2.G4 fix preserves existing `/dashboard/weather-chart/refresh` route; no new HTMX endpoints)
- Phase 8 daily-management state machine refactor beyond P14.N3 visibility/badge fix
- Schwab API integration changes (L2 LOCK)
- Operator failure-mode classification surface (Phase 15+ candidate)
- CLAUDE.md / orchestrator-context archive-splits
- Production code modifications NOT enumerated in plan §B file map

---

## §9 If you get stuck

- If production code has drifted SINCE writing-plans merge (`b2546d5`) and a plan-cited file:line no longer matches reality, ESCALATE to orchestrator (do NOT silently patch). Plan was verified against production at writing-plans phase; drift is anomalous.
- If a task's step-checkbox TDD slicing reveals an unavoidable schema migration NOT anticipated, STOP + escalate per plan §K.
- If Codex pushes back on the SINGLE-chain count, HOLD THE LINE -- Sec 9.1 Q7 LOCK + gotcha #36 caveat.
- If Codex pushes back on the 4th VM field `position_capital_policy_missing`, HOLD THE LINE -- plan §A.4 semantic-extension rationale + R2.M#1+M#2 LOCK + spec §6.4 second bullet authorization.
- If Codex pushes back on the AND-empty backfill SELECT, HOLD THE LINE -- spec §2 + R2.M3 LOCK.
- If Codex pushes back on the narrow `ValueError`-only catch, HOLD THE LINE -- spec §2 + R2.M2 LOCK.
- If Codex pushes back on the PROPORTION semantic, HOLD THE LINE -- spec §2 + R3.M1 LOCK.
- If Codex pushes back on the multiset Counter SUBSET assertion (vs equality), HOLD THE LINE -- writing-plans R1.M#5 + R2.M#6 LOCKs + forward-binding lesson #13.
- If a Codex round produces a finding you cannot disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec + return report (writing-plans hit ZERO acceptances; aim for the same).
- DO NOT propose schema migrations within Sub-bundle 1 scope.
- DO NOT add `Co-Authored-By` footer to ANY commit.
- DO NOT skip hooks (`--no-verify`).
- DO NOT widen scope to other Phase 14 items or Phase 15+ items.
- DO NOT pre-ship T-1.3 OPTIONAL (defer to operator-gate trigger).

---

## §10 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed for production code + tests).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-1-data-wiring-executing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-1-data-wiring-executing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~3-6 hours implementation + ~30-90 min Codex chain. Total ~5-8 hours operator-paced.
- **Codex MCP chain count:** SINGLE chain at end (per Sec 9.1 Q7 LOCK + plan §J + gotcha #36 caveat).
- **Production code surface:** `swing/data/repos/candidates.py` + `swing/cli.py` OR `swing/cli_diagnose.py` + `swing/web/routes/dashboard.py` + `swing/web/view_models/trades.py` + `swing/web/view_models/dashboard.py` + `swing/web/templates/daily_management.html.j2` + (OPTIONAL) `swing/web/view_models/open_positions_row.py`.
- **Test surface:** ~42-46 NEW fast tests across `tests/data/repos/` + `tests/cli/` + `tests/web/routes/` + `tests/web/view_models/` + `tests/integration/`.

---

*End of brief. Phase 14 Sub-bundle 1 executing-plans dispatch -- execute the LOCKed plan (3 data-wiring fixes; 6 NON-OPTIONAL tasks T-1.1 + T-1.2 + T-2.1 + T-3.1 + T-4.1 + T-4.2 + 1 OPTIONAL T-1.3); ~8-12 production commits + ~42-46 fast tests; SINGLE Codex chain at end; operator-witnessed gate at S1-S5 + S5a/S5b/S5c per plan §I. OUTPUT: production code + tests + return report; ready for orchestrator merge + operator-witnessed gate + post-merge housekeeping.*
