# Phase 14 Sub-bundle 1 -- Data-wiring -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 1 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan derived from the Sub-bundle 1 brainstorm spec. Plan lives at `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md`. The plan decomposes the spec into bite-sized TDD slices with per-task acceptance criteria, file-level diff projections, test scope, commit cadence, and an executing-plans dispatch-readiness package.

**Brief:** `docs/phase14-sub-bundle-1-data-wiring-writing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; Sub-bundle 1 brainstorm SHIPPED at `9104bb8` (~810-line spec); housekeeping at `b7819a2`. Main HEAD at writing-plans dispatch time: `b7819a2`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING; ~588+ cumulative ZERO Co-Authored-By trailer drift; 45th cumulative C.C lesson #6 validation NOTABLE (Sub-bundle 1 brainstorm; single chain caught 1 CRITICAL + 10 MAJOR despite pre-Codex orchestrator-side review applying all 19+ expansion candidates); Schema v21 LOCKED (V1 expectation per Sec 9.1 + brainstorm spec §12 verdict); L2 LOCK preserved.

**Expected duration:** ~90-150 min writing-plans + 2-4 Codex rounds. Scope is bounded (single dispatch per spec §10.1; ~8-12 commits + ~34-36 tests). Plan line target: **~1500-2500 lines** (matches recent writing-plans plans at e.g. Phase 13 T2.SB4 + V2-mechanic implementer plans; substantive per-task acceptance criteria + step-checkbox TDD slicing inflate the plan beyond the spec).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief.
- `copowers:writing-plans` wraps `superpowers:writing-plans` with adversarial Codex MCP review after the plan is written.
- Codex chain count: **SINGLE chain** per Sec 9.1 Q7 LOCK + gotcha #36 caveat for pure UX/wiring sub-bundles without analytical artifacts.
- Output: plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-1-data-wiring-plan.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md`** -- the brainstorm spec (~810 lines; AUTHORITATIVE for architectural decisions). Especially:
   - §1 Architecture overview
   - §2 Pre-locked operator decisions (Sec 9.1 LOCKs + sub-bundle §1.1-§1.6 LOCKs verbatim)
   - §3 Module touch list (NEW / MODIFIED / OPTIONAL annotations)
   - §4 V2.G3 design (backfill CLI + restore-SQL artifact + DHA/DHC SKIP_NO_CANDIDATES_ROW + partial-empty SKIP_PARTIAL_EMPTY all-or-nothing)
   - §5 V2.G4 design (kwarg fix + narrow ValueError-only catch + module-level logger addition)
   - §6 P14.N3 design (3-field VM contract + denominator-stamping per maturity.py:197-219 + proportion-unit lock + tooltip)
   - §7 Error handling + edge cases (per item)
   - §8 Cross-item coherence
   - §9 Discriminating-example walkthroughs
   - §10.1 Sub-bundle decomposition recommendation (single dispatch)
   - §10.2 Commit cadence (writing-plans phase refines)
   - §10.5 Operator-witnessed gate enumeration (S1-S5 + S5a/S5b split)
   - §11 Test fixture strategy
   - §12 Schema impact analysis (v21 LOCKED + escalation rule)
   - §13 V1 simplifications + V2 candidates banked
   - §14 Operator decision items pending (Open Questions)
   - §15 Cumulative discipline compliance summary

3. **`docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md`** -- return report. Especially:
   - §7 V2 candidates banked (8 candidates; do NOT design into V1 plan)
   - **§8 Forward-binding lessons for writing-plans dispatch (8 lessons; LOAD-BEARING for plan authoring)**
   - §10 Sub-bundle decomposition recommendation
   - §11 Schema impact verdict (v21 LOCKED)
   - §12 Cumulative gotcha set application summary

4. **`docs/phase14-sub-bundle-1-data-wiring-brainstorm-dispatch-brief.md`** -- original brainstorm dispatch brief (for tertiary context; especially §1 LOCKs + §3 Open Questions).

5. **`docs/phase14-commissioning-brief.md`** -- Phase 14 commissioning + Sec 9.1 LOCKs (BINDING). Cross-reference Sec 2.2 data-wiring sub-bundle architectural notes + Sec 4 cumulative discipline + Sec 6 cross-cutting watch items + Sec 9.1 LOCKed dispositions table.

6. **`CLAUDE.md`** -- especially gotchas cited per item at brainstorm spec §15.2; same gotchas re-apply at writing-plans phase. Most relevant:
   - PriceCache `_last_close` ticker-rotation (V2.G3)
   - OHLCV fetch scope = open-trade tickers ONLY (V2.G4)
   - Session-anchor read/write mismatch (V2.G4)
   - Empty-pool early-return + audit emission (#27; V2.G4)
   - Schema-CHECK + Python-constant + dataclass-validator paired discipline (#11; ESCALATE if any item surfaces unavoidable migration per spec §12)
   - OHLCV archive bar-content TEMPORAL mutation (#26; V2.G4)
   - Test fixture shape vs production emitter shape (Phase 12 C.D family; all items)
   - Read-path mapping must keep pace with write-path on widened columns

7. **`docs/orchestrator-context.md`** -- "Currently in-flight work" + "Lessons captured".

8. **Production code surfaces enumerated in brainstorm spec §3 module touch list** -- read each surface BEFORE plan-authoring to verify the spec's path citations + signature claims:
   - `swing/metrics/equity_resolver.py:32-79 resolve_live_capital_denominator_dollars`
   - `swing/metrics/policy.py:39 read_live_policy`
   - `swing/metrics/maturity.py:197-219 denominator-stamping pattern` + `:296-304 _compute_position_util_pct` (PERCENT semantic)
   - `swing/trades/daily_management.py:381-394 compute_position_capital_utilization` (PROPORTION semantic)
   - `swing/web/routes/dashboard.py` weather-chart/refresh handler (NO module-level logger; add one)
   - `swing/web/view_models/dashboard.py:1390-1417` daily-management tile VM construction
   - `swing/web/templates/daily_management.html.j2` line 92 capital % rendering (multiplies by 100)
   - `swing/data/repos/candidates.py` for the new `get_latest_sector_industry_per_ticker` repo helper

9. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_orchestrator_qa_implementer_product` (orchestrator-side; informational)
   - `feedback_commit_brief_before_inline_prompt` (commit brief BEFORE inline prompt if you spawn sub-implementer work)
   - `feedback_verify_regression_test_arithmetic` (compute test arithmetic both pre/post-fix for the V2.G4 narrow-exception case + the P14.N3 PROVISIONAL/LIVE state-flip test)
   - `feedback_swing_db_migrate_explicit` (informational)
   - `project_applied_research_arc_2026-05-27` (substantive context on why Phase 14 prioritizes UX + wiring over ruleset deployment)

---

## §1 Pre-locked operator decisions (DO NOT re-litigate at writing-plans phase)

### §1.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)

Per `docs/phase14-commissioning-brief.md` Sec 9.1:
- **Q1** sequencing = data-wiring (Sub-bundle 1) -> temporal log V1+ -> charts -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q6** close-out = all 5 sub-bundles merged + operator browser-witnessed verification
- **Q7** Codex chain count = orchestrator discretion per sub-bundle; **SINGLE chain at end** for Sub-bundle 1 (pure UX/wiring; no analytical artifact)

### §1.2 Brainstorm dispatch brief LOCKs (per `docs/phase14-sub-bundle-1-data-wiring-brainstorm-dispatch-brief.md` §1)

- **§1.1** Sub-bundle scope = ONLY V2.G3 + V2.G4 + P14.N3
- **§1.2** Codex single chain at end; 2-4 round convergence target
- **§1.3** Serial execution; Sub-bundle 2 depends on this sub-bundle merge
- **§1.4** Operator-witnessed gate at merge
- **§1.5** Schema v21 LOCKED; ESCALATE to orchestrator if any item surfaces unavoidable migration
- **§1.6** Backwards-compat for legacy NULL Sector/Industry on pre-feature trades (DHA/DHC carve-out via `SKIP_NO_CANDIDATES_ROW` action label; no hardcoded ticker list)

### §1.3 Brainstorm spec LOCKs (per `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md` §2)

The spec's §2 enumerates 6 LOCKs that flow forward (verbatim binding clauses; see spec for full text):
- V2.G3 design = backfill CLI (Fix A) FIRST; VM fallback (Fix B) banked as Fix-1b for operator-gate-trigger
- V2.G3 backfill = STRICT all-or-nothing semantic (AND-empty SELECT; partial-empty SKIP_PARTIAL_EMPTY; DHA/DHC SKIP_NO_CANDIDATES_ROW)
- V2.G3 restore-SQL artifact = MANDATORY emission at dry-run AND before apply (defense-in-depth)
- V2.G4 design = call-signature fix + module-level logger addition + narrow `ValueError`-only catch
- V2.G4 narrow exception = LOCK programming errors (TypeError, AttributeError, KeyError, RuntimeError) propagate to FastAPI 500
- P14.N3 design = 3-field VM extension + denominator-stamping per `maturity.py:197-219` + PROPORTION-unit semantic + tooltip surface

### §1.4 Sub-bundle decomposition LOCK (per spec §10.1)

**Single writing-plans + executing-plans dispatch for all three items.** Items cohere on dashboard + daily-management surfaces; no inter-item dependencies; combined surface within ~8-12 commits + ~34-36 tests.

Do NOT propose splitting into 1a/1b/1c sub-sub-bundles. Do NOT propose sequencing items across multiple dispatches.

### §1.5 Writing-plans phase-specific LOCKs (this brief)

- **L1**: Plan SHALL produce ONE executing-plans dispatch (not 2+). Per §1.4.
- **L2**: Per-task slicing in §G of the plan MUST be bite-sized (each task 3-5 commits max; per-task acceptance criteria + step-checkbox TDD).
- **L3**: Test count target = ~34-36 fast tests (matches spec §10.4 estimate post-R4 bump). Plan SHALL distribute tests across tasks + verify total in §H.
- **L4**: Commit cadence target = ~8-12 commits total (matches spec §10.2). Plan SHALL enumerate per-task commit count + verify total in §G.
- **L5**: Plan §F SHALL re-cite Sec 9.1 LOCKs + spec §2 LOCKs + this brief §1 LOCKs in a cumulative LOCK summary table.

---

## §2 Architectural surface for the plan to design

Given §1's locks, the writing-plans phase MUST produce:

### §2.1 Per-task slicing (plan §G)

Bite-sized tasks aligned with the spec's §10.2 commit cadence guidance + the natural surface boundaries:

- **T-1**: V2.G3 backfill CLI scaffold + restore-SQL artifact emission discipline
- **T-1.1**: NEW repo helper `candidates.get_latest_sector_industry_per_ticker` + tests
- **T-1.2**: NEW CLI subcommand `swing diagnose backfill-trades-sector-industry [--dry-run / --apply]` + dry-run output formatting + restore-SQL artifact emission + tests
- **T-1.3** (OPTIONAL): VM fallback Fix-1b at `swing/web/view_models/open_positions_row.py` -- ONLY if operator-gate trigger surfaces residual empty cells; do NOT pre-ship
- **T-2**: V2.G4 fix at `swing/web/routes/dashboard.py` weather-chart/refresh handler
- **T-2.1**: Module-level logger addition (`import logging; log = getLogger(__name__)`) + V2.G4 kwarg fix (`get_or_fetch([benchmark])` -> `get_or_fetch(ticker=benchmark)`) + narrow `ValueError`-only catch + propagation tests
- **T-3**: P14.N3 daily-management Capital % PROVISIONAL/LIVE state contract
- **T-3.1**: VM extension (3 new fields: `position_capital_denominator_dollars_resolved`, `position_capital_utilization_is_provisional`, `position_capital_utilization_pct_effective`) + denominator-stamping per `maturity.py:197-219` + PROPORTION-unit lock + tooltip template extension + S5a/S5b operator-gate fixture instructions
- **T-4** (closer): cross-item integration tests + Sec 9.1 LOCK verification + L2 LOCK parametric source-grep test extension + return report

**Plan SHALL define** per-task commit count (~1-3 per task), per-task fast-test count (cumulative ~34-36), per-task acceptance criteria with file:line citations, per-task step-checkbox TDD slicing.

### §2.2 Per-task acceptance criteria (plan §G.X.acceptance)

Each task's acceptance criteria SHALL enumerate:
- Files modified / added (with exact paths)
- Functions added / signatures verified against production code
- Discriminating tests added (with test name + assertion shape)
- Cumulative discipline preservation (specific gotchas applied at this task; verify each)
- Sec 9.1 LOCK preservation (specific LOCK at this task; verify)

### §2.3 Test surface (plan §H)

- **~34-36 fast tests** distributed across T-1 / T-2 / T-3 (rough proportions per spec §10.4):
  - T-1: ~14-16 tests (backfill helper + CLI happy path + AND-empty filter + SKIP_PARTIAL_EMPTY + SKIP_NO_CANDIDATES_ROW + restore-SQL artifact roundtrip)
  - T-2: ~6-8 tests (kwarg fix + narrow exception + logger emit + 4 propagation cases per spec §5.2)
  - T-3: ~10-12 tests (denominator-stamping LIVE / PROVISIONAL split + 3-field VM + tooltip render + S5a/S5b fixtures + percent-vs-proportion regression)
  - T-4: ~2-4 tests (integration + L2 LOCK source-grep)
- **0 slow tests** anticipated (V2.G4 mocks `OhlcvCache.get_or_fetch`; no yfinance fetch)
- **Plan SHALL verify** the test count matches the spec §10.4 target via a sum-check in §H

### §2.4 Operator-witnessed gate runbook (plan §I per spec §10.5)

Plan SHALL produce a per-surface operator-witnessed gate runbook:
- **S1**: `pytest -m "not slow"` green + `ruff check swing/` clean
- **S2**: V2.G3 -- VSAT row in `/dashboard` open-positions table renders non-NULL Sector + Industry; DHA legacy NULL still gracefully renders
- **S3**: V2.G3 -- `swing diagnose backfill-trades-sector-industry --dry-run` produces operator-friendly table + restore-SQL artifact emitted
- **S4**: V2.G4 -- `/dashboard` "Refresh weather chart" button produces fresh SPY weather chart (NOT the "no OHLCV bars" error)
- **S5a**: P14.N3 PROVISIONAL case -- plant no `account_equity_snapshots` row; reload `/daily-management`; assert PROVISIONAL badge present + tooltip describes the flag
- **S5b**: P14.N3 LIVE case -- plant `account_equity_snapshots` row covering today's session; reload; assert PROVISIONAL badge NOT present + Capital % value renders correctly (recomputed proportion when stored denominator diverges)

### §2.5 Codex chain count locked + watch items (plan §J)

- **Single chain at end** per Sec 9.1 Q7 LOCK
- Target convergence within 2-4 rounds (matching brainstorm phase)
- Plan §J SHALL enumerate the watch items from return report §8 explicitly (8 forward-binding lessons; LOAD-BEARING for plan-authoring discipline)

### §2.6 Schema impact analysis (plan §K)

Plan SHALL re-verify (NOT re-decide) the v21 LOCK:
- Confirm 21 *.sql files in `swing/data/migrations/` (no v22+ added)
- Confirm V2.G3 backfill is UPDATE-only (no schema change)
- Confirm V2.G4 fix is route-handler-only (no schema change)
- Confirm P14.N3 VM extension consumes EXISTING `equity_resolver.resolve_live_capital_denominator_dollars` + EXISTING `account_equity_snapshots` table (no schema change)
- ESCALATION RULE: if writing-plans-phase code-read surfaces an UNAVOIDABLE schema migration NOT anticipated in the brainstorm spec, STOP + return to orchestrator per spec §12 explicit escalation rule. Do NOT propose v22 silently (would collide with Sub-bundle 2 temporal log v22 claim).

---

## §3 Open questions (Codex chain SHOULD surface answers)

The brainstorm spec §14 enumerated 8 Open Questions. Writing-plans Codex chain SHALL re-visit each + lock dispositions for the plan:

1. V2.G3 backfill helper location: `swing/data/repos/candidates.py` (recommended per brainstorm §6.1) OR a new helper module? Plan locks.
2. V2.G3 active-state allowlist for backfill (`'entered', 'managing', 'partial_exited'`): Plan verifies + locks default.
3. V2.G3 `--include-closed` flag: include in V1 OR defer to V2? Plan locks.
4. V2.G4 `OhlcvCache.refresh_archive` helper existence: Plan verifies via grep against production code; locks Fix-A vs hydrate-then-fetch Fix-C.
5. P14.N3 module location for `DailyManagementTileVM` (brainstorm spec banked `swing/web/view_models/daily_management.py` OR `swing/web/view_models/dashboard.py:1390-1417` inline construction): Plan verifies + locks exact module.
6. P14.N3 tooltip placement: inline-after-PROVISIONAL-text OR title attribute on the badge OR aside element? Plan verifies + locks per existing dashboard tooltip precedent.
7. Test fixture strategy per item: TestClient + monkeypatched repos OR cassette-recorded? Plan locks per item.
8. Plan §G commit cadence preface: enumerate the deviations from default commit cadence if any (e.g., T-1.1 + T-1.2 may consolidate if scope is small; T-2.1 + T-3.1 may not). Plan §G.0 commit-cadence preface MANDATORY per brainstorm forward-binding lesson #2 cumulative regression cascade audit.

---

## §4 OUT OF SCOPE (do not design into the plan)

- V2 candidates banked at return report §7 (8 candidates; V2-only)
- VM fallback Fix-1b (T-1.3) UNLESS operator-gate trigger fires; pre-ship NOT IN PLAN
- Schema migrations beyond v21 (escalation rule; spec §12)
- Sub-bundle 2 / 3 / 4 / 5 scope (per Sec 9.1 Q1 LOCK; serial execution)
- Phase 15+ scope
- V2.G2 schema rename (Sub-bundle 3 scope per Sec 9.1 Q4 LOCK)
- Temporal log infrastructure (Sub-bundle 2 scope per Sec 9.1 Q3 LOCK; v22 belongs there)
- HTMX surface introductions (V2.G4 fix preserves existing `/dashboard/weather-chart/refresh` route; no new HTMX endpoints)
- Phase 8 daily-management state machine refactor beyond P14.N3 visibility fix
- Schwab API integration changes (L2 LOCK)
- Operator failure-mode classification surface (Phase 15+ candidate)
- CLAUDE.md / orchestrator-context archive-splits

---

## §5 Adversarial review (Codex)

Invoked automatically by `copowers:writing-plans` after the plan draft + before final commit.

**Expected chain shape:** 2-4 substantive Codex rounds (matches brainstorm phase + brief §1.2 LOCK target).

**Adversarial review watch items (writing-plans-specific; LOAD-BEARING from return report §8)**:

1. **Brief-vs-production-function-signature verification (gotcha #17 / Expansion #2 refinement)** -- Plan SHALL re-verify `resolve_live_capital_denominator_dollars` + `read_live_policy` + `compute_position_capital_utilization` signatures against current production code at plan-authoring time. Cite file:line for each.
2. **Cumulative regression cascade audit (gotcha #21 / Expansion #13)** -- post-fix sweep at each Codex round. Plan §G.0 commit-cadence preface required.
3. **Percent-vs-proportion unit lock (R3.M1 LOCK)** -- preserve PROPORTION semantic across all P14.N3 surfaces. Plan §G.T-3 acceptance criteria SHALL cite the binding test asserting `1.50 < proportion < 2.00` (or similar) NOT `15.0 < percent < 20.0`.
4. **Module-level logger addition (R3.M2 LOCK)** -- bundle the logger import into the SAME commit as new log calls. Plan §G.T-2.1 SHALL specify the import order + verify no `log` references appear in commits BEFORE the import lands.
5. **Restore-SQL artifact discipline (R1.M3 LOCK)** -- define exact emission path + format + emission-time (dry-run AND before apply); discriminating test asserts artifact exists post-dry-run + post-apply.
6. **Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 LOCK)** -- AND-empty WHERE clause; SKIP_PARTIAL_EMPTY label; separate diagnostic enumeration. V1 STRICT only.
7. **Browser-only HTMX failure surface preservation (cumulative)** -- Sub-bundle 1 does NOT introduce new HTMX surfaces; preserve `/dashboard/weather-chart/refresh` trinity (HX-Request header + 204 + HX-Redirect + target route registered). Plan §G.T-2.1 acceptance criteria SHALL include a regression test asserting these invariants.
8. **Programming-error propagation discipline (R2.M2 LOCK)** -- narrow `ValueError`-only catch; propagation test asserts `TypeError`, `AttributeError`, `KeyError`, `RuntimeError` bubble to FastAPI 500.
9. **Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 LOCK)** -- S5a/S5b split MUST appear in plan §I runbook. State-planting fixture instructions per case.
10. **Schema v21 verification (spec §12 + brief §1.5)** -- plan SHALL count `swing/data/migrations/*.sql` files at plan-authoring time + assert 21. Escalation rule MANDATORY if surface reveals unavoidable migration.
11. **L2 LOCK parametric source-grep extension** -- Plan §G.T-4 SHALL design a parametric source-grep test asserting ZERO new `schwabdev.Client.*` call sites introduced under `swing/` against the `bf7e071` commissioning baseline.
12. **Test fixture shape vs production emitter shape** (Phase 12 C.D family) -- all test fixtures match production candidates row shape, OhlcvArchive write shape, daily_management_records row shape exactly. Plan §H SHALL cite per-fixture production-shape source.
13. **Server-stamping discipline** (Phase 8 family) -- P14.N3's PROVISIONAL/LIVE state derived SERVER-SIDE at VM build time; NOT operator-supplied. No hidden form input carrying provisional state.
14. **`Co-Authored-By` footer suppression** -- explicit citation in plan; ~588+ cumulative ZERO drift streak.
15. **ASCII-only template + CLI output** (gotcha #32) -- plan §K1 SHALL declare ASCII scope explicitly across all NEW + MODIFIED files.

---

## §6 Deliverable shape

**Plan document at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-1-data-wiring-plan.md`** (mirror existing writing-plans plan format, e.g. recent Phase 13 / V2-mechanic implementer plans):

- §A Goals + non-goals
- §B File map (per-file diff projections; cite exact paths + line ranges from production code)
- §C Surface-by-surface integration analysis (V2.G3 + V2.G4 + P14.N3 architectural touch surface)
- §D Out-of-scope explicit list
- §E Operator-paired locks reverification (cumulative LOCK summary table; cites Sec 9.1 LOCKs + brainstorm spec §2 LOCKs + brainstorm dispatch brief §1 LOCKs + this brief §1 LOCKs)
- §F Cumulative discipline + watch items applied (per item + per task)
- §G Per-task slicing (T-1, T-1.1, T-1.2, T-2, T-2.1, T-3, T-3.1, T-4; per-task acceptance criteria + step-checkbox TDD)
- §G.0 Commit cadence preface (deviations from default; ~8-12 commits total estimate)
- §H Test surface (fast / slow split; ~34-36 fast target; per-task distribution table)
- §I Operator-witnessed gate runbook (S1-S5 + S5a/S5b split per spec §10.5)
- §J Codex MCP single-chain placement (post-plan-draft; 2-4 round convergence target)
- §K Schema impact analysis (v21 LOCK reverification + escalation rule)
- §L Test fixture strategy (per item)
- §M Forward-binding lessons (from brainstorm return report §8; carry forward)
- §N Self-review checklist (pre-Codex)

**Target line count: ~1500-2500 lines** (matches recent writing-plans plans; substantive per-task acceptance + step-checkbox TDD inflate vs the spec's ~810 lines).

**Commit message stem:** `docs(phase14-sub-bundle-1-plan): writing-plans -- <N> Codex rounds -> NO_NEW_CRITICAL_MAJOR convergent (R1 ... -> R<N> ...)`.

---

## §7 If you get stuck

- If a code-read against production surfaces a signature drift NOT cited in the brainstorm spec, ESCALATE to orchestrator (do NOT silently patch). Brainstorm verified the listed surfaces at R1-R4; if production has drifted SINCE the brainstorm merge, escalate.
- If writing-plans phase code-read surfaces an unavoidable schema migration, STOP + escalate per spec §12.
- If Codex pushes back on the single-chain count per §1.5 L5, HOLD THE LINE -- Sec 9.1 Q7 LOCK.
- If Codex pushes back on the single-dispatch decomposition per §1.4, HOLD THE LINE -- spec §10.1 LOCK.
- If Codex pushes back on the AND-empty backfill SELECT (R2.M3 LOCK), HOLD THE LINE -- spec §2 LOCK.
- If Codex pushes back on the narrow `ValueError`-only catch (R2.M2 LOCK), HOLD THE LINE -- spec §2 LOCK.
- If Codex pushes back on the PROPORTION semantic for P14.N3 (R3.M1 LOCK), HOLD THE LINE -- spec §2 LOCK.
- DO NOT propose schema migrations within Sub-bundle 1 scope (escalation rule).
- DO NOT add `Co-Authored-By` footer to ANY commit (project invariant).
- DO NOT skip hooks (`--no-verify`) on commits.
- DO NOT propose V2 candidates within Sub-bundle 1 plan (per spec §13 + return report §7).
- DO NOT widen scope to other Phase 14 items (V2.G1, V2.G2, P14.N1, P14.N2, P14.N4, CR.1, P14.N6, P14.N5).

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase14-sub-bundle-1-data-wiring-writing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown (with per-commit Codex round attribution).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Plan line count + per-section line count breakdown.
4. Pre-locked operator decisions verbatim verification (Sec 9.1 LOCKs + spec §2 LOCKs + this brief §1 LOCKs).
5. §3 Open Questions: which Codex resolved + which locked at plan-authoring time.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Per-task acceptance criteria summary (T-1, T-1.1, T-1.2, T-2, T-2.1, T-3, T-3.1, T-4).
8. Test surface verification (~34-36 fast tests projected; per-task distribution).
9. Forward-binding lessons for executing-plans dispatch.
10. Schema impact verdict (v21 unchanged; explicit confirmation).
11. Cumulative gotcha set application summary (per task).
12. Worktree teardown status.
13. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` inspection across all branch commits).
14. CLAUDE.md status-line refresh draft text.
15. Executing-plans dispatch readiness summary (operator-paired gate items pending; OQs all resolved).

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-1-data-wiring-writing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-1-data-wiring-writing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~90-150 min writing-plans + ~30-90 min Codex chain. Total ~3 hours operator-paced.
- **Codex MCP chain count:** SINGLE chain at end (per §1.5 L5 + Sec 9.1 Q7 LOCK).

---

*End of brief. Phase 14 Sub-bundle 1 writing-plans dispatch -- produce a per-task implementation plan derived from the brainstorm spec (3 data-wiring items; 4 task buckets T-1 + T-2 + T-3 + T-4; ~8-12 commits + ~34-36 fast tests target); ~1500-2500 line plan target; 2-4 Codex round expectation. OUTPUT: implementation plan that executing-plans phase can dispatch directly to an implementer.*
