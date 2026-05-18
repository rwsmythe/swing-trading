# Cross-Phase Operational Backlog

> **Filename note (2026-05-01):** this file is named `phase3e-todo.md` for historical reasons (it was created at the end of the Phase 3d walkthrough as the Phase 3e backlog). It has since accumulated cross-phase items (Phase 4 / 4.5 / 6-9 + standalone bundles + Tier-3 deferrals + research-branch followups). The filename is preserved to keep ~46 cross-references in shipped briefs valid; the canonical title is "Cross-Phase Operational Backlog." Not a commitment, just a trackable list.

> **Archive companion (2026-05-05):** SHIPPED + closed entries previously inline have moved to `docs/phase3e-todo-archive.md`. Fresh-orchestrator bootstrap reads only this active file; grep the archive on demand for historical context (commit hashes, prior dispatches). Retention discipline + archive-split trigger are documented in `docs/orchestrator-context.md` §"Maintenance: retention discipline."

> **Archive companion (2026-05-18 Phase 12.5 #3 T-3.2 split):** Additional SHIPPED entries dated 2026-05-12 and earlier moved to [`docs/phase3e-todo-archive.md`](docs/phase3e-todo-archive.md) (boundary 2026-05-12 inclusive; SHIPPED-only predicate). 23 sections moved this pass; archive doc gained an "Appended Phase 12.5 #3 archive-split" appendix at its end. Grep both files for full history.

---

## 2026-05-18 Phase 12.5 #3 (Project Hygiene Maintenance Pass) SHIPPED at `b436067` — CLOSES Phase 12.5 arc; 3 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; orchestrator-side QA review PASS-CLEAN across 13 watch items + Q3 skipped-test audit completed; T-3.5 Bucket A landed (3 Phase 8 tests promoted to PASSING); Ruff 18 E501 → 0; schema v19 UNCHANGED; 4847 → 4850 fast pass

**Integration-merge at `b436067`** (branch `phase12-5-bundle-3-project-hygiene-executing-plans` via `--no-ff`; 11 task-branch commits = 7 task-impl (T-3.1..T-3.7) + 3 Codex-fix (R1+R2+R3) + 1 return-report). 3 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/5M/2m → R2 0C/2M/1m → R3 0C/0M/1m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Major findings (all 7 cumulative Major resolved with code-content fixes). ZERO Co-Authored-By footer drift across all 11 commits (~165+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review APPROVED_AS_IS** (C.C lesson #6 BINDING; 8th cumulative validation).

**Orchestrator-side QA review PASS-CLEAN** across 13 watch items: T-3.7 3-site amendments verified file:line accurate + accurately describe shipped helper SQL semantic; T-3.5 Bucket A fix verified `datetime.now() + timedelta(days=7)` anchor at `tests/integration/test_phase8_pipeline_walkthrough.py:57` with L-E2 lesson citation + 7-day buffer per Codex R1 M#5 hardening; T-3.5 test pass verified 3 previously-failing tests promoted to PASSING (4847 → 4850 fast pass); T-3.6 Ruff cleanup verified zero E501 + zero other error classes; T-3.6 ASCII preservation honored on runtime CLI paths (1 em-dash at cli.py L1142 is in docstring NOT runtime print/echo per L-W4 scope); T-3.4 amendment inventory verified 74 rows + spot-checks resolved to correct source docs; T-3.1 CLAUDE.md status-line archive-split verified (47 entries → 18 archived; 29 retained active within plan [15,30] band); T-3.2 phase3e-todo verified (3768 lines + archive 1372 lines); T-3.3 orchestrator-context verified (715 → 698 lines + 20 lessons archived); 4 operator-locks preserved verbatim; cross-document consistency verified; ZERO red flags.

**Operator-driven Q3 skipped-test audit COMPLETED** (5 skipped roster classified):
- **1 LEGITIMATE-DEFERRED**: `tests/evaluation/patterns/test_flag_classifier_integration.py:21` "No labeled fixtures committed yet (Task 7.3 operator-only)" — Phase 13 Theme 2 territory; auto-un-skips when fixtures land.
- **4 POTENTIALLY-STALE**: `tests/journal/test_account_summary_net_liq_extraction.py:43` parametrized over `thinkorswim/2026-04-15/-04-30/-05-08/-05-12-AccountStatement.csv` (gitignored privacy-sensitive). Sanitized fixtures exist at `tests/fixtures/tos/schwab-real-world-2026-04-15..2026-05-12.csv` (per Phase 9 Sub-bundle E ship; account-number sanitization preserves Net Liq Value).
- **Operator-pending disposition for #2-5**: (a) UPDATE tests to use sanitized fixtures → 4 skips become PASS (baseline 4850 + 5 → 4854 + 1); (b) KEEP AS-IS as operator-environment-only smoke tests.
- **ZERO prunable. ZERO Bucket-C-style** (T-3.5 landed Bucket A; no new skips added).

**Test count**: 4847 → **4850 fast pass** (the +3 are T-3.5 promotions; ZERO new skips).
**Ruff**: 18 E501 → **0** (acceptance LOCK met).
**Schema**: v19 UNCHANGED.

**Key shipped artifacts:**
- `docs/v2-1-section-7f-amendments-2026-05-18.md` (NEW; 74 amendments).
- `docs/CLAUDE.md-archive.md` (NEW; 18 entries).
- `docs/phase3e-todo-archive.md` (extended; +23 sections via 2026-05-18 appendix).
- `docs/orchestrator-context-archive.md` (extended; +20 lessons).
- 3-site amendment on Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104.
- T-3.5 fix at `tests/integration/test_phase8_pipeline_walkthrough.py:57`.
- T-3.6 18-site E501 fixes across 11 swing/ files.

**Operator-paired post-merge S2-S4 gate UNBLOCKED** (S1 already PASS at 4850/5/0 + ruff 0; S2 visual archive-split boundaries + S3 amendment doc readability + S4 amendment 3-site verification — orchestrator-driven post-merge).

**4 NEW forward-binding lessons L-E1..L-E4** banked at return report §9:
- L-E1: operational-follow-through vs amendment classification.
- L-E2: time-dependent fixture calendar-buffer ≥7d (the Bucket A fix lesson).
- L-E3: operator-runtime-override + post-hoc audit transparency pattern.
- L-E4: row-contract grep-verification pre-Codex.

**Phase 12.5 arc CLOSED.** Aggregate across Phase 12.5 (#1 + finviz-fix + #2 + #3): ~7-8 total executing-plans dispatches if you count the brainstorm + writing-plans + executing-plans triplets; ~5 Codex chains total. **Phase 13 dispatch UNBLOCKED post**: operator-witnessed S2-S4 gate + Q1 reconciliation walkthrough + Q2 tabularize web+CLI + Q3 skipped-test disposition closures.

### Predecessor (2026-05-18 AM; writing-plans)

## 2026-05-18 Queued post-Phase-12.5-#3 / pre-Phase-13 cleanup items (operator-added 2026-05-18 post-Phase-12.5-#3-writing-plans-merge)

Two cleanup items operator queued for post-Phase-12.5-#3 closure, BEFORE Phase 13 commissioning. Both are bounded scope; neither is in Phase 12.5 #3 plan (intentionally separated to keep Phase 12.5 #3 scope narrow).

### Item Q1: Open reconciliation discrepancy walkthrough — investigate suspected Schwab API response parser bug

**Posture:** Orchestrator-paired walkthrough first; investigation dispatch second IF walkthrough surfaces a real bug.

**Trigger:** Operator suspects the Schwab API response parser may have a bug surfaced by the pattern of open discrepancies currently pending (54+55+56+57 + any newer Pass-1 `unmatched_open_fill` re-emissions from runs #67/#68). Operator wants to step through each open discrepancy with orchestrator, examine the source `schwab_api_calls.response_body_json` (or raw response if logged elsewhere) vs the journal-side fill row vs the emitted discrepancy shape, and identify whether the parser is misreading a Schwab response field.

**Scope (walkthrough)**:
- Read each open `reconciliation_discrepancies` row (resolution='unresolved' OR resolution='pending_ambiguity_resolution' OR resolution NULL).
- For each: surface the linked `schwab_api_calls` row's audit metadata + the journal-side fill row (`fills` table) + the discrepancy's `expected_value_json` + `actual_value_json` envelope.
- Compare against operator's actual TOS / Schwab broker-statement reality (operator brings broker-statement evidence to the walkthrough).
- Identify pattern: random / per-fill / per-order-shape / per-discrepancy-type / parser-specific.

**Scope (investigation dispatch — IF walkthrough surfaces bug)**:
- Investigation-first dispatch shape (precedent: 3e.12 tos-import diagnostic at `a9541d2`; post-Phase-12 Sub-bundle 1.5 diagnostic at `a7c1016`).
- Diagnostic script bypasses `_audited_get_account_orders` audit wrapper to capture pre-parser raw shape (precedent: `scripts/diagnose_schwab_executionlegs.py` at Sub-bundle 1.5).
- Operator-paired diagnostic run against production (recovery sequence + redacted output).
- Fix dispatch after root cause identified.
- Expected dispatch shape: 2-4 Codex rounds; gate 3-5 surfaces; schema likely v19 unchanged.

**Cross-references:**
- CLAUDE.md gotcha "Synthetic-fixture-vs-production-emitter shape drift" (Phase 12 Sub-sub-bundle C.D gate finding family).
- CLAUDE.md gotcha "Pass-2-tier-1-FORBIDDEN + Pass-1-tier-1 — V2-RESOLVED for Pass-1; Pass-2 STAYS tier-2-always".
- Post-Phase-12 Sub-bundle 1.5 diagnostic precedent (4 placeholder shapes identified + 5 real FILLED LIMIT orders).
- Phase 12.5 #1 ship verified architectural fix HOLDS positive sense (production run #15 ZERO false-positive Pass-1; but Pass-2 still tier-2-always per OQ-F V2-deferred).

**Decision-pending at walkthrough time**:
- Whether suspected bug is real (vs operator-perceived pattern that's actually correct).
- Whether fix is V1 dispatch OR V2-deferred (depends on severity + workaround availability).
- Whether parser fix sequencing should go BEFORE or AFTER Phase 12.5 #3 close.

**Status**: QUEUED; orchestrator-paired walkthrough on operator's signal.

### Item Q2: Discrepancy resolution — render journal/Schwab value comparison as table on BOTH web AND CLI (presentation-only)

**Scope amended 2026-05-18 (operator)**: CLI parity is IN SCOPE — `swing journal discrepancy show-ambiguity` (and any other discrepancy CLI surfaces that emit the comparison) MUST output a similar table for operator-readability purposes.

**Posture:** Small executing-plans-shape dispatch (or inline-fix if simple enough; orchestrator chooses at commission time).

**Trigger:** Phase 12.5 #2 shipped `/reconcile/discrepancy/{id}/resolve` form page with pre-resolution context section ABOVE choice menu. Current rendering uses list format for the journal-side vs Schwab-side value comparison on BOTH web AND CLI (`swing journal discrepancy show-ambiguity <id>` emits list-shape output). Operator wants this rendered as a TABLE on both surfaces (2 columns: journal-side | Schwab-side; rows per compared field) — VM data is already structured; only the rendering paths need adjustment + possibly a shared helper.

**Scope (web)**:
- MODIFY `swing/web/templates/reconcile_discrepancy_resolve.html.j2` — replace list rendering of pre-resolution context with `<table>` (2-column journal-side | Schwab-side; ARIA-compliant; ASCII-only per F20 LOCK from Phase 12.5 #2).
- MAYBE MODIFY `swing/web/view_models/reconcile.py` — if `pre_resolution_context_pairs` field shape needs restructuring from `list[tuple[str, str]]` to `list[tuple[str, Any, Any]]` (field-label + journal-value + Schwab-value) for cleaner table rendering. Spec §5.2 ReconcilePreResolutionContext (15 fields per Phase 12.5 #2 A3 amendment) — verify existing shape suits table rendering.
- Per-discrepancy-type render helpers may need touch-up (10 helpers in `reconcile.py` per Phase 12.5 #2 plan).
- NEW discriminating tests asserting `<table>` element + `<th>` headers + correct row count per discrepancy type.

**Scope (CLI)**:
- MODIFY `swing/cli.py` (or wherever the discrepancy CLI subcommands render the comparison; the C.D-shipped surfaces include `discrepancy show-ambiguity` + possibly `discrepancy show` + `discrepancy show-correction`). Locate via `grep -n "def show_ambiguity\|def show_discrepancy\|def show_correction" swing/cli.py`.
- Replace list output (likely `click.echo()` lines) with an ASCII-only tabular renderer. **BINDING per CLAUDE.md cp1252 stdout gotcha**: table-drawing characters MUST be plain ASCII (`+`, `-`, `|`) — do NOT use Unicode box-drawing characters (`┌`, `─`, `│`, `┐`, etc.) since they crash on Windows PowerShell cp1252 stdout. Optional: lightweight 2-line border using `|` and `-`. NO third-party dependencies (no `rich`, no `tabulate`) — render inline.
- Shared rendering helper between CLI + web preferred IF VM field-shape restructure lands (e.g., a `render_journal_schwab_comparison_table_ascii(pairs)` helper that returns a plain-text table; web template wraps the same pairs in HTML `<table>`). This is operator-decision at commission time vs duplication.
- NEW discriminating tests asserting CLI output contains tabular pattern (e.g., `|` column separator + per-row content correctness) + subprocess test capturing stdout through PowerShell to validate cp1252 encoding doesn't crash (per CLAUDE.md "Discriminating-test gap" note on subprocess vs capsys).

**Out of scope:**
- Behavioral changes — POST handler + service-layer + classifier untouched.
- Schema changes (v19 LOCK).
- Adding new discrepancy types or comparison fields.

**Operator-locks (anticipated; operator confirms at commission)**:
- Per-discrepancy-type table column headers (Journal | Schwab vs Ours | Theirs vs etc.) — operator-decision at commission. Suggested default: "Journal" | "Schwab".
- Whether VM field-shape changes (suggesting yes for clarity + cleaner CLI/web shared helper) OR template/CLI render-only restructure (extract fields by name from existing shape) — operator decides based on dispatch-author proposal.
- Whether CLI shared helper lives in `swing/web/view_models/reconcile.py` (web has it; CLI imports) OR a NEW neutral location (e.g., `swing/trades/reconciliation_render.py`) — operator decides.

**Expected dispatch shape:**
- 2-4 tasks (web template rewrite + CLI render rewrite + shared helper + tests).
- 1-2 Codex rounds.
- **3-4 surface operator-witnessed gate**: S1 inline pytest + ruff; S2 visual verification of `/reconcile/discrepancy/{id}/resolve` page renders table on browser; S3 visual verification across the 10 per-type render helpers (web); S4 CLI table rendering verified on PowerShell terminal (`python -m swing.cli journal discrepancy show-ambiguity <id>` against real production discrepancy) — operator confirms readability + ZERO cp1252 crash.
- Schema v19 unchanged.

**Cross-references:**
- Phase 12.5 #2 plan A3 amendment (15-field ReconcilePreResolutionContext drift).
- Phase 12.5 #2 spec §5.2 + spec §6.
- CLAUDE.md gotcha "Windows PowerShell stdout defaults to cp1252" — ASCII-only table-drawing constraint.
- Phase 12 Sub-bundle C.D ship — `swing journal discrepancy {list-pending-ambiguities, show-ambiguity, resolve-ambiguity, override-correction}` CLI subcommands (and post-Phase-12 Sub-bundle 1 added `show-correction`).

**Status**: QUEUED; commission timing operator-paced.

### Item Q3: Skipped-test inventory audit — investigate + prune (orchestrator-driven; in spirit of Phase 12.5 #3 T-3.5 failing-test triage)

**Posture:** Orchestrator-driven investigation at Phase 12.5 #3 executing-plans return time. NOT a separate dispatch unless triage surfaces work that warrants one.

**Trigger:** Operator-added 2026-05-18 — Phase 12.5 #3 audits the 3 pre-existing Phase 8 walkthrough FAILING tests (T-3.5 bucket triage); in the same spirit, the SKIPPED-test inventory deserves audit. Skipped tests carry an implicit "deferred-work" cost that compounds over time; some skips become stale (the original blocker resolved but the skip decorator was never removed); some skips mask deferred-but-still-pending work; some are legitimate operator-only fixtures.

**Baseline at brief drafting time (2026-05-18 fresh pytest run on main HEAD `9407dad`)**: **5 skipped** (4847 fast pass + 3 pre-existing phase8 walkthrough failures + 5 skipped + 1 known enumerated):
- `tests/evaluation/patterns/test_flag_classifier_integration.py:21` "No labeled fixtures committed yet (Task 7.3 operator-only)" — legitimate-deferred per operator commit posture.
- 4 OTHERS not yet enumerated at brief time; investigation surfaces the full roster.

**Skipped-count growth scenario**: if Phase 12.5 #3 T-3.5 lands **Bucket C** (skip-pattern with operator approval), skip count grows from 5 → 8 (3 Phase 8 walkthrough tests added). The Bucket C disposition is itself a deliberate skip; this Q3 audit covers it identically (legitimate-deferred per operator approval; standalone-dispatch entry banked).

**Scope (orchestrator-driven; ~10-30 min):**
1. **Enumerate every currently-skipped test**: `python -m pytest -m "not slow" -rs -q -n 0 2>&1 | grep -E "^SKIPPED"` to get the full roster with skip reasons.
2. **For each skip**, surface:
   - File:line + test name + skip decorator (`@pytest.mark.skip(reason=...)` vs `@pytest.mark.skipif(...)` vs runtime `pytest.skip(...)`).
   - Skip rationale text (verbatim).
   - Date the skip was introduced (`git log -p --diff-filter=A -- <file> | grep -B5 "pytest.mark.skip"` or similar; approximate via blame).
   - Cross-bundle pin status if applicable (e.g., Phase 10 T-A.7 + T-E.3 cross-bundle pin pattern — un-skip happens at later sub-bundle; verify the un-skip already landed).
3. **Classify per skip** as one of:
   - **Legitimate-deferred** (e.g., operator-only labeled fixtures pending; cross-bundle pin awaiting later sub-bundle that hasn't landed yet; slow-marked test requiring live API access).
   - **Stale** (the original blocker has resolved but the skip decorator was never removed; un-skip + verify-passes is the action).
   - **Prunable** (the test itself is no longer needed; the surface it exercised was removed/refactored; DELETE the test).
   - **Bucket-C-style** (Phase 12.5 #3 T-3.5 disposition; legitimate-deferred per operator approval + standalone-dispatch entry banked).
4. **Propose per-skip disposition** + operator-paired decision per skip.

**Operator-locks (anticipated; operator confirms at audit time)**:
- Whether any reclassification + per-skip action lands inline (small orchestrator-driven commit) OR requires a separate dispatch (if e.g. multiple un-skips reveal real test failures requiring fixes).
- Whether the audit-summary doc itself is durably tracked (e.g., new `docs/skipped-test-inventory-2026-05-18.md` companion to T-3.4's V2.1 §VII.F amendment inventory pattern) OR ephemeral (banked inline in this phase3e-todo entry).

**Likely outcomes (per audit pattern history)**:
- 1-2 legitimate-deferred (operator-only fixtures + cross-bundle pin awaiting later phase).
- 1-3 stale (project moved past the original blocker; un-skip + verify-passes).
- 0-1 prunable (rare; tests rarely become unnecessary).
- 0-3 Bucket-C-style if Phase 12.5 #3 T-3.5 lands Bucket C.

**Out of scope:**
- Auditing FAILING tests beyond the 3 Phase 12.5 #3 T-3.5 targets (Phase 12.5 #3 owns that).
- Adding NEW tests to cover gaps revealed by un-skipping.
- Test-runtime profiling beyond skip-resolution work.

**Status**: QUEUED at executing-plans return time. Orchestrator-driven; no implementer dispatch unless triage surfaces work warranting one.

**Cross-references:**
- Phase 12.5 #3 T-3.5 failing-test triage (same spirit; complementary discipline).
- Phase 10 T-A.7 + T-E.3 cross-bundle pin un-skip pattern (precedent for legitimate-deferred → un-skip at later sub-bundle).
- Phase 12.5 #2 cross-bundle pin (1 of the 5 baseline skipped; un-skipped during writing-plans but may or may not have landed via executing-plans merge — audit verifies).
- `feedback_orchestrator_qa_implementer_product.md` (orchestrator QA discipline; Q3 is QA-adjacent triage).

### Sequencing relative to Phase 12.5 #3 + Phase 13

- **Phase 12.5 #3 executing-plans** — dispatched (UNBLOCKED post operator approval); brief at `docs/phase12-5-bundle-3-project-hygiene-executing-plans-dispatch-brief.md`.
- **Item Q3 skipped-test audit** — orchestrator-driven at Phase 12.5 #3 executing-plans RETURN time (before merge); part of post-return QA + triage window.
- **Item Q1 walkthrough** — orchestrator-paired; operator commissions on signal. May or may not lead to investigation dispatch.
- **Item Q2** — small executing-plans dispatch; operator commissions on signal.
- **Phase 13** — gated on Phase 12.5 closure (Phase 12.5 #3 + Q1 + Q2 + Q3). Phase 13 scope LOCKED at `docs/phase13-scope-brainstorm.md` §0.5.

---

## 2026-05-18 Phase 12.5 #3 writing-plans SHIPPED at `fb27be2` — project-hygiene maintenance pass plan; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; orchestrator-side QA review PASS-CLEAN; schema v19 UNCHANGED; executing-plans dispatch UNBLOCKED

**Integration-merge at `fb27be2`** (branch `phase12-5-bundle-3-project-hygiene-writing-plans` via `--no-ff`; 1 task-branch commit at `63f1943` combined plan-write + return-report). 6 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/4M/4m → R2 0C/3M/3m → R3 0C/3M/2m → R4 0C/1M/2m → R5 0C/1M/2m → R6 0C/0M/1m; operator-override past default MAX_ROUNDS=5 at R6 per Phase 12.5 #1+#2 brainstorm precedent). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Major findings (all 12 cumulative Major resolved with code-content fixes). 2 Minor accepted as advisory (line count overshoot 1101 vs 400-700 brief target + section letter drift collapsed-gate precedent). ZERO Co-Authored-By footer drift (~165+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review APPROVED_AS_IS** (NEW C.C lesson #6 BINDING; 7th cumulative validation; brief tight enough that pre-review absorbed nothing pre-chain).

**Orchestrator-side QA review PASS-CLEAN** across all 10 watch items: T-3.7 amendment-target file:line accuracy verified at plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 + amendment text accurately describes shipped helper SQL semantic; T-3.5 Phase 8 walkthrough inventory verified 3-fail/1-pass via fresh pytest; T-3.6 18-row E501 roster byte-for-byte matches `ruff check swing/`; T-3.4 amendment-scope spot-check passed on Phase 12.5 #2 R-R §7 cross-references; T-3.1/T-3.2/T-3.3 archive-split boundary discipline coherent; 4 operator-locks preserved verbatim; schema v19 UNCHANGED LOCK + escalation rule encoded; footer suppression cited in every commit stem; cross-document consistency verified; ZERO red flags beyond known runtime-pairing points (T-3.5 Bucket C HARD STOP + T-3.3 pre-flight roster operator review).

**Test count baseline correction**: 4847 fast (NOT 4851 per dispatch brief; L-W3 NEW lesson banked captures brief-baseline-vs-fresh-baseline drift family).

**1101-line plan** at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (above 400-700 brief target; matches Phase 12.5 #1 1230 + #2 1082 overshoot precedent driven by Codex chain rigor + per-task acceptance specificity + 18-row Ruff roster verbatim + 33-file return-report grouped roster verbatim + 4-test Phase 8 walkthrough inventory verbatim).

**7 tasks T-3.1..T-3.7 single-sub-bundle decomposition**:
1. **T-3.7** (FIRST since smallest + de-risks downstream) — amend Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104 amendment text (3 sites; banner clears immediately on tier-3 override per shipped helper SQL semantic).
2. **T-3.5** Phase 8 walkthrough triage with 3-bucket disposition (Bucket A trivial fixture fix / Bucket B small runner-side adjustment / Bucket C HARD STOP requires operator approval BEFORE skip-pattern + standalone-dispatch entry).
3. **T-3.6** Ruff 18 E501 cleanup with full 18-row roster (file:line specific) + ASCII-preservation contract on runtime-path string literals; ZERO `# noqa` without rationale.
4. **T-3.4** V2.1 §VII.F amendment inventory at NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` with canonical 33-file return-report grouped roster + grep supplement.
5. **T-3.1** CLAUDE.md status-line archive-split (boundary 2026-05-12-inclusive + PROCEED_WITH_WRITE count gate at 15-30 active-retain band).
6. **T-3.2** phase3e-todo archive-split (SHIPPED-only predicate + pre-write roster gate).
7. **T-3.3** orchestrator-context archive-split (pre-flight roster + operator review BEFORE script-write).

**2 operator-locks preserved verbatim**: skip-brainstorm; amend-text-only for item #5 (NO code fix to preserve banner mid-window — shipped helper SQL semantic accepted).

**Schema v19 UNCHANGED LOCK** preserved (F1 + F5 + T-3.5 STOP-and-escalate rule).

**4-surface operator-witnessed gate plan** (per plan §H): S1 inline pytest+ruff+per-task post-conditions; S2 visual verification of archive-split boundaries; S3 V2.1 §VII.F amendment doc readability + cross-reference accuracy; S4 Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment verification.

**4 NEW forward-binding lessons L-W1..L-W4** banked at return report §9 for executing-plans inheritance:
- L-W1: Bucket-classification math requires explicit test-inventory table (compute expected counts FROM the table, NOT memory).
- L-W2: Pre-write gate pattern for archive-split scripts (`PROCEED_WITH_WRITE = False` until operator reviews roster).
- L-W3: Brief-baseline-vs-fresh-baseline drift verification (plan-author MUST re-verify pytest baseline at plan-write time).
- L-W4: ASCII-only invariant scope discipline (runtime CLI paths only; documentation freely uses em-dashes + § glyphs).

**Test projection** (per plan §E): ~+0 to ~+5 fast tests (most tasks text-edit zero-test-delta; possible +1-3 if T-3.5 lands fixes that need new regression pins); ~+50-200 LOC moves across archive-companion files; ruff baseline expected → 0 E501 post-T-3.6.

**Executing-plans dispatch UNBLOCKED** post operator-paired plan review.

### Predecessor (2026-05-18 PM; Phase 12.5 #2 executing-plans)

## 2026-05-18 Phase 12.5 #2 (Web Tier-2 discrepancy-resolution surface) SHIPPED at `0cecf28` — 5 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; +135 fast tests + 1 slow E2E; schema v19 UNCHANGED; 6-surface operator-witnessed gate ALL PASS; Sub-bundle B T-B.7 PROMISE FULFILLED

**Integration-merge at `0cecf28`** (branch `phase12-5-bundle-2-web-tier2-executing-plans` via `--no-ff`; 17 task-branch commits = 11 task-impl + 1 orchestrator-inline gate-fix `25f4554` (4th cumulative inline gate-fix; /dashboard route alias closing Phase 6 I3 HX-Redirect-target-unrouted gotcha) + 4 Codex-fix bundles + 1 return-report). 5 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/2M/1m → R2 0C/2M/0m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Majors (all 6 cumulative resolved with code-content fixes); 1 Minor accepted as advisory (L-W5 LOCK forbids `error_kind Literal` tightening). ZERO Co-Authored-By footer drift across 17 commits (~163+ project-cumulative streak preserved).

**First operator-visible web Tier-2 surface ships** — dedicated GET/POST `/reconcile/discrepancy/{id}/resolve` form page mirrors `swing journal discrepancy resolve-ambiguity` CLI 1:1; same service entry `apply_tier2_resolution`; same choice menu; same audit shape; distinguishable via `resolved_by IN ('operator', 'operator_web')`. Dashboard banner links directly to the resolve form for the oldest pending-ambiguity discrepancy (ORDER BY ASC per LOCK #6).

**Sub-bundle B T-B.7 PROMISE FULFILLED** — Phase 12 Sub-bundle B's deferred T-B.7 web counterpart to CLI Tier-2 is now SHIPPED.

**6-surface operator-witnessed gate ALL PASS**: S1 inline pytest+ruff+slow E2E (4847 fast + 18 ruff + 10.59s E2E); S2 banner-link nav (/reconcile/discrepancy/52/resolve oldest ASC); S3 form-render with 10 context pairs + hidden `ambiguity_kind_at_render` anchor + custom-value textarea + F20 ASCII-only; S4 POST disc #52 → 204 + `HX-Redirect: /dashboard?reconcile_resolved=18` + correction_id=18 + `resolved_by='operator_web'` (F17 server-stamp LOCK preserved); S5 banner-clears 6 → 5 + link advances 52 → 53; S6 CLI/web parity disc 53 CLI `resolved_by='operator'` vs disc 52 web `resolved_by='operator_web'` (LOCK #3 distinguishability verified) + banner 5 → 4 post-S6.

**Test delta**: +135 fast tests (4712 → 4847; vs +81 plan projection — overshoot from parametrize granularity + Codex regression pins). +1 slow E2E (Phase 12.5 #2 happy-path PASS). Ruff 18 E501 unchanged. Schema v19 UNCHANGED (F1 LOCK preserved).

**3 V2.1 §VII.F amendment candidates banked** (A1 plan §C.1 class-name drift + A2 plan §K projection +81 vs actual +135 + A3 plan §A T-2.2 acceptance 14-vs-15 fields drift).

**5 NEW forward-binding lessons L-E1..L-E5**: L-E1 pre-Codex orchestrator-side review absorbed 1 Major-class finding pre-chain (/dashboard unrouted) — C.C lesson #6 validated 3rd time; L-E2 `OperationalError` pre-flight scope cascades — R1 wrap revealed adjacent paths R2-R4 incrementally (Python sibling-except clauses do NOT cascade); L-E3 Builder `ValueError` cause classification belongs in shared helper — extracted at R4; L-E4 Plan-class-name drift surfaces via Pass A AST grep at task time; L-E5 Pass B grep count drifts +N during dispatch as new code lands (21 → 24; F11/F21 contract handled).

**Production state post-gate**: 4 pending-ambiguity discreps remaining (54+55+56+57); operator continues dispositioning per C.D-cleanup precedent.

**Phase 12.5 #3 dispatch UNBLOCKED.**

### Predecessor (2026-05-18 AM; writing-plans)

## 2026-05-18 Phase 12.5 #2 writing-plans SHIPPED at `9220dac` — 5 Codex rounds + R5 confirmation NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; 1082-line plan; 11-task single-sub-bundle decomposition; 12 operator-locks + 21 invariants F1-F21 + 8+5 forward-binding lessons; schema v19 UNCHANGED; executing-plans dispatch UNBLOCKED

**Writing-plans-merge at `9220dac`** (branch `phase12-5-bundle-2-web-tier2-writing-plans` via `--no-ff`; 7 commits = 1 draft + 1 pre-Codex-review-fix + 4 Codex-fix + 1 return-report). 5 Codex rounds + 1 R5 confirmation NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (pre-Codex 0C/3M/2m → R1 0C/3M/4m → R2 0C/2M/3m → R3 0C/1M/4m → R4 0C/0M/4m → R5 0C/0M/0m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE (all 6 Major + 15 Minor resolved with code-content fixes). ZERO Co-Authored-By footer drift across 7 commits (~147+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING) absorbed 3M+2m before R1** — validated again across Phase 12 C.C+C.D + Sub-bundle 1 + Phase 12.5 #1 brainstorm + writing-plans + Phase 12.5 #2 brainstorm precedent.

**Highest-value Codex catches:**
- **R1 M#1** task-ordering would break T-2.5/T-2.6 green-ship contract — fixed via stub-then-extend reorder (T-2.5 stubs 2 error-template branches; T-2.6 extends 3 more inline; T-2.10 polish-only). Each task ships green standalone.
- **R1 M#2** POST-service `ValueError` uniformly mapped to 400 + re-render would have looped operator through internal-error state on concurrent-resolve race — Branch 14 split into 14a (400 if re-read confirms pending) + 14b (409 if re-read shows terminal state). New discriminating test pinned via separate-connection + commit semantics. +1 fast test from projection.
- **R2 M#2** spec sections out of sync with R1+R2 plan fixes — banked J2 + J3 amendments with explicit "Plan supersedes spec" notes so executing-plans implementer treats plan as binding without spec rewrite.

**Key plan elements**: 1082-line plan at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`. 11 tasks T-2.1..T-2.11 single-sub-bundle decomposition (1 GET + 1 POST route + 1 VM module + 2 templates + 13-VM standalone-field retrofit + 21-callsite Pass B retrofit). 12 operator-locks verbatim-encoded at §D (4 spec §2 + 8 §16 ACCEPTED at brainstorm defaults). 21 invariants F1-F21 at §F. Schema v19 UNCHANGED (F1 LOCK). 3 V2.1 §VII.F amendments banked at §J (J1 builder kwarg + J2 ValueError 14a/14b split + J3 parametric valid_choices). 13 V2 candidates mirrored from spec §15 at §Z. 6-surface operator-witnessed gate at §H verbatim per LOCK §1.2 #12.

**Refined projection** post-Codex chain: ~+81 fast tests (+1 race regression from R1 M#2) + 1 slow E2E + ~+970 production LOC + ~+1145 test LOC. Ruff 18 E501 baseline preserved. Baseline 4712 fast → projected ~4793 post-executing-plans-merge.

**5 NEW writing-plans-surfaced forward-binding lessons L-W1..L-W5** (8 inherited from brainstorm + 5 new = 13 total for executing-plans): L-W1 stub-then-extend ordering for shared templates; L-W2 service ValueError requires re-read disambiguation in concurrent-write callers; L-W3 F# cross-reference accuracy audit at sealing time; L-W4 spec-out-of-sync requires explicit "Plan supersedes" notes + §J amendment banking; L-W5 late VM-validator additions risk breaking already-green callers.

**Executing-plans dispatch UNBLOCKED.**

### Predecessor (2026-05-18 AM; brainstorm)

## 2026-05-18 Phase 12.5 #2 brainstorm SHIPPED at `ac6eb88` — Web Tier-2 discrepancy-resolution surface design; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked (R1 M#4 surface attribution literal naming — schema v19 UNCHANGED; brief §2.7 conjecture corrected); 721-line spec; 8 §16 operator-decision items ALL accepted at brainstorm defaults; writing-plans dispatch UNBLOCKED

**Brainstorm-merge at `ac6eb88`** (branch `phase12-5-bundle-2-web-tier2-brainstorm` via `--no-ff`; 3 commits = 1 draft + 1 Codex-R1-R6-fix-bundle + 1 return-report). 6 Codex rounds convergent monotonic-Major taper (R1 0C/5M/3m → R2 0C/3M/2m → R3 0C/3M/2m → R4 0C/1M/3m → R5 0C/1M/2m → R6 0C/0M/2m); operator-override past default MAX_ROUNDS=5 invoked at R6 per Phase 12.5 #1 brainstorm + Phase 10 writing-plans precedent given clean convergent shape. ZERO Critical findings entire chain. ZERO Co-Authored-By footer drift across 3 commits.

**Key catch (R3):** brief §2.7 conjectured that `reconciliation_corrections.surface` column would need CHECK widening to permit `'web'`. **WRONG** — brainstorm verified by reading migration 0019 directly: there is NO `surface` column on `reconciliation_corrections`. Attribution achieved via existing free-TEXT `reconciliation_discrepancies.resolved_by` column with NEW value `'operator_web'`. ZERO schema work. ZERO new Python constant. ZERO new validator. **Forward-binding lesson banked**: brief-conjecture-vs-actual-schema gap → grep verify any column reference at brainstorm time (L-W1 family reapplication).

**4 operator pre-locks baked verbatim** (spec §2.1-§2.4): dedicated `/reconcile/discrepancy/{id}/resolve` form page + HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` on success + CLI preservation AS-IS (`surface='cli'` vs `surface='web'` distinguishable via `resolved_by`) + pre-resolution context section ABOVE choice menu.

**8 §16 operator-decision items ALL ACCEPTED at brainstorm defaults** (operator-orchestrator scope conversation 2026-05-18 post-merge): (1) banner navigation target → first-pending; (2) ORDER BY ASC oldest-first; (3) NO V1 dashboard per-discrepancy list (banked V2); (4) HX-Redirect query token `?reconcile_resolved={id}` included; (5) uniform `/dashboard` HX-Redirect target; (6) 12-line inline `<script>` for custom-value toggle; (7) `_parse_parametric_pick_count` helper duplicated private in web VM (CLI refactor V2-deferred); (8) 6-surface operator-witnessed gate (S1 inline pytest+ruff + S2 banner-link nav + S3 form-render with context + S4 successful POST + HX-Redirect + S5 banner-clears + S6 CLI/web parity).

**Sub-bundle decomposition recommended**: SINGLE sub-bundle with 11 tasks (T-2.1..T-2.11). Projection ~+45-75 fast tests + 1 slow E2E; 3-5 Codex rounds for executing-plans; ~6-10 hours operator-paced. Schema v19 UNCHANGED end-to-end.

**13 V2 candidates banked** (§15): audit-chain show page; success toast renderer; web Tier-3 override surface; web Tier-1 auto-correct undo; `/reconcile/pending` list page; pipeline-active exclusion on Tier-2; explicit `surface` column V2 migration; etc.

**8 forward-binding lessons banked** for writing-plans (return report §8): brief-conjecture-vs-actual-schema gap; BaseLayoutVM-inheritance asymmetric (13 existing VMs DO NOT inherit; carry standalone fields); hidden state anchors distinct from hidden audit fields; OriginGuard strict-vs-non-strict 303-fallback shapes; banner-link targets derive from canonical helper; audit-row parity tests use semantic-shape projection; grep-driven audits split by intent (field-declaration vs call-site); retrofit completeness is a discriminating test.

**Writing-plans dispatch UNBLOCKED.**

---

## 2026-05-18 Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect) SHIPPED at `6109261` — 4 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked (R1 M#3 banner-vs-briefing wording false-positive); ~+132 fast tests net (4575 → 4712); ruff/schema unchanged; 6-surface gate ALL PASS

**Integration-merge at `6109261`** (branch `phase12-5-bundle-1-oqf-executing-plans` via `--no-ff`; 18 task-branch commits = 11 task-impl + 2 task-review-fixes + 1 cross-bundle-pin follow-up + 2 Codex-fix + 2 return-report + 1 in-branch merge-of-finviz-fix). Includes orchestrator-driven 6-surface operator-witnessed gate PASS: S1 4712 fast + ruff 18 + slow E2E; S2 spec §10 cases A/C/E/I + determinism × 10 identical; S3 production run #15 ZERO multi-leg fires + ZERO false-positive Pass-1 (architectural fix HOLDS in negative sense); S4 banner-fires `data-banner-count="1"` + verbatim §8.3 wording + banner-clears via planted run #16 + ASCII-only + full revert; S5 `--resolved-by` filter operational; S6 pipeline #68 from empty inbox → `briefing.md` `## Reconciliation status` section + multi-leg line correctly omitted (count=0; F22 omit-when-zero works end-to-end through T-1.11).

**Highlights:**
- **Codex R2 surfaced a Sub-bundle C.C latent defect** — `_handle_split_into_partials` hardcoded `action="entry"` would have corrupted close-fill discrepancies via the new auto-routing path; fixed at handler (benefits both new auto-redirect path AND existing manual operator-resolved menu path) with 2 discriminating regression tests.
- **Sandbox-skipped path infrastructure deletion** — Codex R2 Major #1 surfaced + deleted unreachable `auto_redirect_skipped_sandbox` backfill counter (collides with Sub-bundle C.D §9.7 LOCK upstream which short-circuits sandbox BEFORE classification). T-1.6 service-layer + pivot-loop counter PRESERVED per F20 + spec §7.6 LOCK.
- **1 V2.1 §VII.F amendment candidate banked** (plan §A T-1.5.B 3-line drift after the deletion above).
- **1 new forward-binding lesson L-X1** (handler-extension audit pattern when auto-routing widens a handler's reach).
- **1 architectural inconsistency banked for Phase 12.5 #3** (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL — orchestrator-spotted during S4 gate sub-test planning: shipped helper SQL queries `rd.resolved_by = 'auto_tier1_multi_leg'` directly, so `apply_tier3_override` flipping parent disc `resolved_by` to `'operator'` WOULD clear the banner immediately, contradicting plan §H.4's "STILL present + count unchanged" claim. Reasonable operator semantic, but plan wording is imprecise. Phase 12.5 #3 watch-item).
- **Mid-gate dispatch: empty-finviz-inbox auto-fetch fix** — Phase 12.5 #1 S6 surfaced the pre-existing `phase3e-todo:940-958` bug (3rd gate-blocker occurrence). Inline-fix dispatched + shipped at `7a84942`; Phase 12.5 #1 branch merged main back in via `c406817` (in-branch merge); S6 re-ran successfully on merged state.
- **Phase 12.5 #2 dispatch UNBLOCKED.**

### Original entry (2026-05-17 PM; pre-executing-plans; superseded by SHIPPED outcome above)

## 2026-05-17 PM Phase 12.5 #1 writing-plans SHIPPED — OQ-F multi-leg tier-1 auto-redirect single-sub-bundle decomposition (11 tasks; ~+102 fast tests + 1 slow E2E + ~+435 LOC; schema v19 unchanged) — 5 Codex rounds NO_NEW_CRITICAL_MAJOR — 1 Critical + 12 Major + 8 Minor ALL RESOLVED; ZERO ACCEPT-WITH-RATIONALE

**Writing-plans SHIPPED 2026-05-17** at `2e8b10a` (integration merge of `phase12-5-bundle-1-oqf-writing-plans` via `--no-ff`; 2 plan commits = 1 initial + 1 Codex-fix bundle; **5 Codex rounds → NO_NEW_CRITICAL_MAJOR** non-monotonic-Major shape (R1 1C/4M/1m → R2 0C/3M/1m → R3 0C/4M/2m → R4 0C/1M/2m → R5 0C/0M/2m sealed; R3 bump above R2 driven by downstream drift the R2 fixes themselves surfaced); **ZERO ACCEPT-WITH-RATIONALE banked** — all 1 Critical + 12 Major + 8 distinct Minor resolved with code-content fixes; ZERO Critical findings post-R1 resolution; ZERO Co-Authored-By footer drift across 2 commits.

### Deliverable

- **Plan doc**: `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (1230 lines; grew from 1008 absorbing Codex chain; ~330 above 600-900 brief target — driven by R1 Critical #1 backfill-consumer scope expansion + R2-R4 acceptance-criteria depth).
- **Return report**: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md`.

### R1 Critical #1 — highest-value Codex catch (dead-code dispatcher prevention)

Initial draft would have shipped a dead-code dispatcher — multi-leg auto-redirect can only fire on the BACKFILL Pass-2 path (`reconciliation_backfill.py:_handle_pass_2`), NOT the initial pivot (which reads persisted `actual_value_json={"matched": null}` for `unmatched_*_fill` sentinels). T-1.5 scope widened to wire BOTH consumers; slow E2E moved to the operational firing site (backfill). Initial pivot stays as defensive future-proofing.

**Backfill consumer surface identified**:
- `reconciliation_backfill.py:_handle_pass_2`
- `reconciliation_backfill.py:run_backfill` orchestrator
- `reconciliation_backfill.py:format_summary_block` renderer
- `BackfillOutcome` dataclass
- `BackfillSummary` dataclass

### Single-sub-bundle decomposition LOCKED

- **11 tasks T-1.1..T-1.11** per plan §A
- **~+102 fast tests + 1 slow E2E** (refined from ~+85 pre-Codex)
- **~+435 LOC** (refined from ~+320 pre-Codex)
- **Schema v19 UNCHANGED** (F1 invariant + F19 plan-author schema additions escalation rule NOT triggered)

### 14 pre-locked decisions verbatim-encoded in plan §D

- 4 spec §2.1-§2.4 operator-locks (auto-redirect ON; all-match-within-tolerance; reuse apply_tier2_resolution; banner advisory only)
- 3 spec §15.B operator-locks (price_tolerance=$0.01 absolute; qty_tolerance asymmetry preserved; NO N-legs cap V1)
- 7 spec §15.A brainstorm-locks (n=1 multi-leg path; --resolved-by CLI filter; sandbox short-circuit gated; service API overrides; briefing.md +1 line; canary observability; resolved_by free TEXT)

### 25 binding invariants F1-F25

19 inherited + 6 NEW F20-F25 surfaced this dispatch:
- F20+F21 backfill-consumer wiring
- F22 service API override-parameter contracts
- F23 dataclass→dict boundary ownership
- F24 helper-function key-set stability
- F25 spec-locked rendering text verbatim

### 18 forward-binding lessons in plan §M (executing-plans inheritance)

**12 inherited from brainstorm** (8 spec §16 + 4 return report §8):
1-8. recipe-field discipline; override-parameter threading; free-text vs CHECK-enum distinction; cross-column CHECK invariants; sandbox short-circuit ALWAYS in inner; helper invocation completeness; ASCII-only banner text; discriminating-test patterns
9-12. 4 chain-surfaced lessons in brainstorm return report §8

**6 NEW writing-plans-surfaced L-W1..L-W6:**
- L-W1 (R1 Critical #1): When designing a dispatcher pattern + recipe consumption, enumerate EVERY dispatcher consumer; initial pivot's source_payload derivation matters; if it returns None for unmatched sentinel, the dispatcher in that path is dead-code; operational consumer lives ELSEWHERE.
- L-W2 (R1 Major #1): Spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering in plan tasks, NOT as "PLAN DECISION" overrides.
- L-W3 (R1 Major #2): Spec-locked rendering text MUST be verbatim-asserted in tests; don't lift adjacent patterns without checking the new lock.
- L-W4 (R1 Major #3): Retrofit scope predicates MUST be enumerated by canonical mechanism (template-mount), NOT proxy field-presence.
- L-W5 (R1 Major #4): Helper functions producing normalized dicts MUST emit stable key-set across ALL input branches.
- L-W6 (R1 minor #1): Conversion seams (dataclass→dict at module boundary) MUST be owned by ONE task with clear contract.

### Comparison to precedents

1C/12M mid-pack for project history:
- C.B was 1C/6M
- C.D was 0C/6M
- post-Phase-12 mapper-widening ~6 rounds
- Phase 12.5 #1 brainstorm 0C/15M (cleanest)

R1 Critical was high-value architectural catch; R2-R4 absorbed downstream drift from R1 fixes themselves; R5 cleaned up final stale text.

### Executing-plans dispatch UNBLOCKED

Orchestrator's next deliverable: draft executing-plans dispatch brief encoding plan §A T-1.1..T-1.11 + plan §D 14 locks + plan §F 25 invariants + plan §M 18 forward-binding lessons. Per plan §L scaffold.

### Worktree teardown status

- Branch `phase12-5-bundle-1-oqf-writing-plans` merged via `--no-ff` at `2e8b10a`; on-disk husk at `.worktrees/phase12-5-bundle-1-oqf-writing-plans/` matches cleanup-script regex `phase\d+[-_]` — operator-paired cleanup pass post-merge.

### Cross-references

- Writing-plans dispatch brief: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md` (`5c988d2`).
- Plan doc: `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (in `2e8b10a` merge).
- Return report: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md` (in `2e8b10a` merge).
- Integration merge: `2e8b10a`.
- Brainstorm spec (predecessor): `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (at `a1582c0`).

---

## 2026-05-17 PM Phase 12.5 #1 brainstorm SHIPPED — OQ-F multi-leg tier-1 auto-redirect (V2 follow-up from post-Phase-12 mapper-widening spec §6.6) — 7 Codex rounds NO_NEW_CRITICAL_MAJOR — ZERO ACCEPT-WITH-RATIONALE banked across 15 Major + 10 Minor (cleanest brainstorm chain in project history)

**Brainstorm SHIPPED 2026-05-17** at `a1582c0` (integration merge of `phase12-5-bundle-1-oqf-brainstorm` via `--no-ff`; 8 implementer commits = 1 draft + 6 Codex-fix + 1 return-report; **7 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 5M/2m → R2 3M/2m → R3 2M/2m → R4 2M/2m → R5 2M/1m → R6 1M/1m → R7 0); **ZERO ACCEPT-WITH-RATIONALE banked across all 15 Major + 10 Minor findings — cleanest brainstorm chain in project history**; ZERO Critical findings entire chain; ZERO Co-Authored-By footer drift across 8 commits.

### Deliverables

- **Spec doc**: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (1236 lines; mirrors Sub-bundle C spec format §0-§17).
- **Return report**: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md`.
- **Session state**: `%TEMP%/.copowers-session-0ca8f15d6677.json`.

### 4 operator-locked decisions (§2.1-§2.4 verbatim binding clauses; preserved through all 7 Codex rounds)

1. Auto-redirect posture = ON
2. Confidence threshold = all-match-within-tolerance per spec §4.4 determinism principle
3. Auto-correct handler shape = reuse `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied')`
4. Operator-facing UX = banner advisory only

### Brainstorm-locked at §15.A (Codex chain resolved during 7 rounds)

- §6.5 n=1 single-order multi-leg path LOCKED YES via ambiguity_kind reclassification (Codex R1 M2)
- §8.6 `--resolved-by <value>` CLI filter LOCKED IN-BUNDLE at T-1.10 (Codex R1 M5; banner template cites filter; both land together)
- §7.6 sandbox short-circuit gated-on-auto-redirect + SAVEPOINT ROLLBACK pattern (Codex R1 M3)
- §7.4 service API LOCKED to `operator_custom_payload` (existing kwarg) + new `applied_by_override` / `correction_action_override` / `resolved_by_override` overrides (Codex R1 M4)
- §11.2 briefing.md +1 line per run for `tier1_multi_leg_redirected_count` when > 0
- §12.3 canary observability for empty-executions case (~+5 LOC + 1 test; Sub-bundle 1.5 canary precedent)
- §13.3 Brief §2.4 amendment banked — no `_RESOLVED_BY_VALUES` constant exists; resolved_by is free TEXT; brief writer error caught by Codex R1 M4

### Schema v19 UNCHANGED LOCK

Corrections + discrepancies CHECK enums already accommodate `auto_applied` + `auto` + new free-TEXT `resolved_by='auto_tier1_multi_leg'`. NO migration required.

### 3 still-open operator-decision items at §15.B (writing-plans handoff)

Brainstorm proposes defaults; operator may override at writing-plans-brief drafting:

1. **§4.4 `price_tolerance` threshold** — brainstorm default: LOCK $0.01 absolute (matches spec §4.4 inheritance + existing codebase). Operator may override toward `max($0.01, abs(journal_price) * 0.001)` for higher-priced stocks.
2. **§6.3 `qty_tolerance` mismatch** — brainstorm default: LOCK predicate=1e-9 (handler uses 1e-6; strictness asymmetry is safe — predicate stricter than handler).
3. **§6.4 defensive cap on N legs** — brainstorm default: NO cap V1 (production evidence supports unbounded; mapper-coherence-check already filters pathological shapes). Operator may impose cap (e.g., 50) for memory hygiene.

### Single sub-bundle ship recommended

**NOT** 2-3 sub-bundle decomposition originally projected. Brainstorm consolidated to:
- ~+320 LOC across 11 tasks
- ~+85 fast tests + 1 slow E2E
- 3-5 Codex rounds projected for executing-plans

### 12 V2 candidates banked at §14

(further widening; per-leg surfacing; multi-account variants; etc.)

### 12 forward-binding lessons for writing-plans

8 from spec §16 + 4 Codex-chain-surfaced in return report §8:
1. Recipe-field discipline (auto_redirect_recipe=None default preserves existing emit paths)
2. Override-parameter threading with verbatim-existing default values
3. Free-text columns vs CHECK enum columns (pre-flight `grep -n CHECK` for every new string value)
4. Cross-column CHECK invariants (`(ambiguity_kind, resolution)` pairing through service-layer)
5. Sandbox short-circuit ALWAYS in inner (C.C lesson #2 carry-forward)
6. Helper invocation completeness + grep retrofit test discipline (Phase 10 T-E.3 + Sub-bundle 2 precedent)
7. ASCII-only banner text (CLAUDE.md cp1252 gotcha pre-emption)
8. Discriminating-test patterns for predicate edge cases (Codex R2 M2 + R3 M1)
9-12. 4 Codex-chain-surfaced lessons per return report §8

### Writing-plans dispatch UNBLOCKED

Consumes locked spec (§2 operator-locks + §15.A brainstorm-locks) + 12 forward-binding lessons + 3 still-open §15.B items. Expected 3-5 Codex rounds; output plan doc decomposing into 11 tasks for single-sub-bundle executing-plans dispatch.

### Worktree teardown status

- Branch `phase12-5-bundle-1-oqf-brainstorm` merged via `--no-ff` at `a1582c0`; on-disk husk matches cleanup-script regex `phase\d+[-_]` — operator-paired `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass post-merge.

### Cross-references

- Brainstorm dispatch brief: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (`37b584d`).
- Spec doc: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (in `a1582c0` merge).
- Return report: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md` (in `a1582c0` merge).
- Integration merge: `a1582c0`.
- Spec §6.6 OQ-F V2 LOCK (predecessor): `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md:561-590`.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 2 SHIPPED — /schwab/status web counterpart (T-B.7 follow-up from Phase 12 Sub-bundle B) — 5-surface orchestrator-witnessed GATE ALL PASS — CLOSES post-Phase-12 mapper-widening arc

**Sub-bundle 2 SHIPPED 2026-05-17** at `690aed0` (integration merge of `schwab-mapper-bundle-2` via `--no-ff`; 13 implementer commits = 7 task-impl (T-2.0..T-2.6) + 3 Codex-fix (R1 Critical #1 + Major #1 + R2 Major #1 + R3 Minor #1) + 1 return-report + 1 merge; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/1M → R2 0C/1M → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 findings resolved with code-content fixes; ZERO Co-Authored-By footer drift; **+52 fast tests** (4523 → 4575); ruff 18 unchanged; schema v19 unchanged consumer-side.

### Architectural surface (deferred Phase 12 Sub-bundle B T-B.7 task — read-only web mirror of `swing schwab status` CLI)

1. **`swing/web/view_models/schwab.py`** — NEW `SchwabStatusVM` + `SchwabCallSummary` frozen dataclasses with `__post_init__` validators (LIVE/PROVISIONAL/DEGRADED triplet per plan §A.0.1 D3 + shipped CLI; `state_reason is None iff state == 'LIVE'` invariant; 5-field base-layout VM banner pin per Phase 10 T-E.3 retrofit).
2. **`swing/web/routes/schwab.py`** — NEW `GET /schwab/status` route handler with `apply_overrides(cfg)` discipline + case-insensitive `?environment=` query-param override + PlainTextResponse for invalid env (Codex R1 Major #7 + R2 Major #1 XSS-safe primitive) + sentinel-leak audit + `_redact_error_message_for_audit` read-time re-redactor at `build_schwab_status_vm`. EXISTING `POST /schwab/setup` HX-Redirect retarget `/config?schwab_setup=ok` → `/schwab/status` with passive no-op consumer retention one release window (Codex R1 m#2 LOCK).
3. **`swing/web/templates/schwab_status.html.j2`** — NEW template extending `base.html.j2` + 3-state LIVE/PROVISIONAL/DEGRADED color-coded badge (`state-ok` green / `state-warn` yellow / `state-error` red) + refresh-token TTL countdown with severity styling + recent-calls table + environment switcher (`?environment=production` / `?environment=sandbox` plain anchor links) + re-auth link to `/schwab/setup` when state != LIVE + Jinja2 autoescape regression test + 4-sentinel audit-trail coverage.
4. **`swing/web/templates/config.html.j2`** — ONE-LINE addition: second `<a>` in "External integrations" `<ul>` section linking to `/schwab/status`.

### Codex chain convergence

- **R1 Critical #1 (error_excerpt sentinel leakage)**: template rendered `vm.error_excerpt` directly + sentinel-leak test exempted audit `error_message` sentinel "operator-visible by design". If any historical or future audit row contained unredacted token bytes, `/schwab/status` would disclose them. **Two-layer fix**: (a) drop `error_excerpt` rendering from template per spec §7.4 OQ-D CLI 1:1 LOCK (CLI `_render_recent_calls` shows endpoint + status + http only); (b) re-redact `c.error_message` at read time in `build_schwab_status_vm` via `_redact_error_message_for_audit` (idempotent; defense-in-depth); strengthen sentinel-leak test to assert ALL 4 sentinels absent.
- **R1 Major #1 (status enum narrower than CLI)**: `_SCHWAB_CALL_STATUSES = {'success', 'auth_failed', 'rate_limited', 'error'}` (4) silently dropped `in_flight` + `concurrent_refresh` rows. CLI renders every row regardless of status. **Fix**: widen frozenset to all 6 schema CHECK values per migration 0018 + drop now-no-op filter.
- **R2 Major #1 (tokens_db_path leak)**: VM stored `str(tokens_path)` rendering operator's full local home (Windows `C:\Users\rwsmy\swing-data\...` / POSIX `/home/<username>/swing-data/...`). Spec §7.1 explicitly requires "display-only, masked if path contains user-profile prefix". **Fix**: mask via `Path.relative_to(home).as_posix()` prefixed with `~/` when under `_user_home()`; falls back to full path defensively. NEW discriminating regression test plants tokens DB in `tmp_path`, asserts masked form rendered + absolute form NOT in body.
- **R3 Minor #1 (template sentinel audit narrower)**: template-surface ratchet planted tokens-DB sentinels only; plan §B T-2.2 test #10 requires both tokens DB AND `schwab_api_calls.error_message` row sentinels. Route-level T-2.1 test 13 already covers broader scope. **Fix**: extend template sentinel list to 4 (add `LEAK_TPL_AUDIT_ERROR_MESSAGE_SENTINEL`); plant via direct INSERT; assert ZERO substring matches for ALL 4.

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM via curl + grep on worktree web server port 8081)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4575 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~85s wall-clock).
- **S2 PASS** — `/schwab/status` HTTP 200 / 8765 bytes — `class="schwab-status-badge state-ok"` + `data-state="LIVE"` discriminating CSS marker + H1 "Schwab integration status (production)" + Refresh token TTL section + env switcher links (production + sandbox) + 6-row Recent API calls `<table class="schwab-recent-calls">` + **masked tokens_db_path (ZERO `C:\Users` occurrences in response body — Codex R2 Major #1 fix HOLDS)** + ZERO Jinja UndefinedError / TemplateSyntaxError leaks + base-layout integration intact (Metrics nav link + theme toggle).
- **S3 PASS** — `/config` HTTP 200 / 11362 bytes — "External integrations" section + BOTH `href="/schwab/setup"` + `href="/schwab/status"` nav-links present (count=1 each; T-2.3 acceptance MET).
- **S4 SKIPPED** per brief §3 default (refresh-token clock healthy ~5 days remaining at gate time; T-2.4 retarget covers via test).
- **S5 PASS** — ruff 18 E501 unchanged.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0** (preserved through Sub-bundle 1+1.5+2 ships).
- `/schwab/status` renders LIVE for production environment with masked path; visible-only fields are derived metadata (no raw token bytes ever surface).
- 4 historical correction chains preserved unchanged.

### Post-Phase-12 mapper-widening arc CLOSED — Phase 12.5 dispatches UNBLOCKED

**Arc-cumulative aggregate** (Sub-bundle 1 + 1.5 + 2):
- ~24 + 14 + 11 = **49 commits** (28 task-impl + 13 Codex-fix + 3 return-reports + 3 merges + 2 housekeeping)
- 5 + 4 + 3 = **12 Codex rounds total** (NO_NEW_CRITICAL_MAJOR all rounds)
- +115 + 48 + 52 = **+215 cumulative fast tests** (~4360 → 4575)
- 0 + 2 + 0 = **2 ACCEPT-WITH-RATIONALE banked** (both Sub-bundle 1.5; T-1.5.4 sequence + canary minimal scope)
- 0 + 0 + 0 = **ZERO Co-Authored-By footer drift**
- 0 + 0 + 4 = **4 V2.1 §VII.F amendments banked** (all Sub-bundle 2; spec §7.1)
- 0 + 0 + 2 = **2 CLAUDE.md gotcha promotion candidates banked** (all Sub-bundle 2; for Phase 12.5 #3)
- Schema v19 unchanged across entire arc

**Next dispatches** (Phase 12.5; operator-locked 2026-05-17 sequencing):
1. **Phase 12.5 #1: OQ-F multi-leg tier-1 auto-redirect** — direct V2-mapper-widening successor; consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers + Sub-bundle 1.5's confirmed-firing extraction path. **RECOMMENDED FIRST.**
2. **Phase 12.5 #2: Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2; web counterpart of C.D's CLI surface.
3. **Phase 12.5 #3: Project hygiene maintenance pass** (5 sub-items per operator-requested 2026-05-17 expansion) — (a) CLAUDE.md archive-split + (b) orchestrator-context archive-split + (c) V2.1 §VII.F amendment batch processing + (d) Phase 8 walkthrough failing-test triage/fix + (e) Ruff 18 E501 cleanup.

**Phase 13 scope LOCKED** at `docs/phase13-scope-brainstorm.md` §0.5 (operator-decided 2026-05-17); dispatch gated on Phase 12.5 close.

### Worktree teardown status

- Branch `schwab-mapper-bundle-2` merged via `--no-ff` at `690aed0`; on-disk husk at `.worktrees/schwab-mapper-bundle-2/` **CLEANED by operator post-merge** (`cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass; branch matches `schwab(?:-\w+)?-bundle-` regex). All 3 post-Phase-12 husks (`schwab-mapper-bundle-1` + `schwab-mapper-bundle-1.5` + `schwab-mapper-bundle-2`) cleared in single operator pass.

### S2 visual confirmation closed

- The 5-surface gate was orchestrator-driven via curl + grep (per phase3e-todo gate-outcome §"GATE OUTCOME"). **S2 visual confirmation closed post-merge by operator** via Chrome MCP-equivalent browser inspection of `/schwab/status` page (LIVE state-ok badge color rendering + recent-calls table + env switcher behavior + base-layout integration all OK end-to-end). The curl+grep gate caveat from Sub-bundle 2 gate-outcome message is RESOLVED.

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-2-schwab-status-web-counterpart-executing-plans-dispatch-brief.md` (`01d2e11`).
- Return report: `docs/post-phase12-schwab-mapper-bundle-2-return-report.md` (in `690aed0` merge).
- Plan §B: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md:624-857` (T-2.0..T-2.6).
- Integration merge: `690aed0`.

### 4 V2.1 §VII.F amendments banked (return report §7)

1. Spec §7.1 state-triplet misnamed (CONFIGURED/PROVISIONAL/NOT_CONFIGURED → actual LIVE/PROVISIONAL/DEGRADED per shipped CLI).
2. Status enum widening (4 → 6 values matching schema CHECK constraint per migration 0018).
3. `tokens_db_path` masking pattern (display-only; mask under user-home prefix; Path.relative_to fallback discipline).
4. `error_excerpt` rendering scope per OQ-D CLI 1:1 LOCK (drop from template + read-time re-redact at VM build).

### 2 CLAUDE.md gotcha promotion candidates banked for Phase 12.5 #3 triage

1. **Read-time re-redactor discipline**: when a VM rendering surface exposes audit fields that flow from `*.error_message` rows, the VM-build helper MUST re-invoke the redactor at read-time (defense-in-depth against pre-redaction-discipline rows OR future write-time redactor bugs). Pattern: `vm.error_message_for_audit = _redact_error_message_for_audit(row.error_message)` at the VM construction step.
2. **`tokens_db_path` masking pattern**: file-path fields rendered in operator-facing UI MUST mask paths under `_user_home()` prefix via `Path.relative_to(home).as_posix()` prefixed with `~/`; fall back to full path defensively when `relative_to` raises (defense against unexpected paths). Pre-empt in any new file-path-in-VM design.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 1.5 SHIPPED — Schwab mapper validator-drop fix (filledQuantity==0 early-exit gate + observability canary + diagnostic script + production-shape regression tests) — 5-surface operator-witnessed GATE ALL PASS — CLOSES Sub-bundle 1's validator-drop defect; post-Phase-12 architectural arc CLOSED

**Sub-bundle 1.5 SHIPPED 2026-05-17** at `a7c1016` (integration merge of `schwab-mapper-bundle-1.5` via `--no-ff`; 13 implementer commits + 1 return-report + 1 merge; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/6M/2m → R2 0C/2M/2m → R3 0C/0M/2m → R4 0C/0M/1m); **2 ACCEPT-WITH-RATIONALE banked** (R1 M#2 T-1.5.4 sequence-by-design + R2 M#1 canary intentionally minimal — `price > 0` strongest signal + widening false-positives on placeholder `quantity > 0`); ZERO Co-Authored-By footer drift; **+48 fast tests** (4475 → 4523); ruff 18 unchanged; schema v19 unchanged.

### Architectural fix lands across 2 surfaces

1. **`swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw`** — 12-line additive early-exit gate when `filled_qty == 0` (EXPLICIT zero only; preserves "filledQuantity absent: permissive" stance for legacy V1 path). Returns `None` pre-empting drop+warn cascade across STOP-typed placeholder family.
2. **`swing/integrations/schwab/mappers.py:_has_non_placeholder_leg`** — NEW module-level canary helper emits WARN inside gate when any leg in `activityType=EXECUTION` activity has `price > 0` (anomalous-shape canary for future Schwab regression where real-fill sentinel surfaces despite `filledQuantity=0`).

**T-1.5.1 diagnostic infrastructure (FOLDED)**:
- `scripts/diagnose_schwab_executionlegs.py` (859 lines + 25 tests with 5-sentinel sentinel-leak audit; 3-layer redaction Layer 0 exact-replace + Layer 1a JSON-key regex + Layer 1b 32+ hex + Layer 1c 40+ base64; ASCII-only stdout for cp1252 safety; bypasses `_audited_get_account_orders` to capture pre-validator raw shape).
- Generalizable diagnostic-script pattern for any future Schwab API-shape investigation (forward-binding lesson #1).

### Root cause (CONFIRMED via T-1.5.1 against operator's production 2026-05-17 16:52:48 UTC)

H1-H5 from brief §0.1 ALL FALSIFIED. Actual root cause = **H1-extended (UNANTICIPATED family)**: Schwab emits placeholder `executionLegs[]` on STOP-typed orders that NEVER executed (status REPLACED/CANCELED/PENDING_ACTIVATION) — `filledQuantity=0` AND `executionLegs[0].price=0.0` (sentinel placeholder) AND `executionLegs[0].quantity>0` (reflects order's intended size).

**Production data distribution (30-day window)**:
- 22 total orders inspected
- 17 with `executionLegs[]` present
- **12 of 17 are placeholder shapes** (filledQuantity=0 / leg.price=0.0) — STOP/REPLACED/CANCELED/PENDING_ACTIVATION family
- **5 of 17 are real FILLED LIMIT orders with `price > 0`**:
  - CVGI @ $12.6999 (filled 2026-05-15; 18 shares)
  - LION @ $8.585 (filled 2026-05-14; 9 shares)
  - VIR @ $55.5337 (filled 2026-05-13; 2 shares)
  - YOU @ $10.78 (filled 2026-05-13; 7 shares)
  - YOU @ $11.7066 (filled 2026-05-08; 7 shares)

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM via implementer-paired session)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4523 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~93s wall-clock).
- **S2 PASS** — 4 new test files 23/23 regression coverage PASS.
- **S3 PRODUCTION FETCH PASS** — `python -m swing.cli schwab fetch --orders` (worktree-side per `feedback_worktree_cli_invocation.md`) emitted reconciliation_run #14 (state=completed; tier1_applied_count=0; tier2_pending_count=2; schwab_orders_checked=30 vs Sub-bundle 1's 18; ZERO validator-drop warnings in stderr/audit; ZERO false-positive entry/close_price_mismatch — architectural fix HOLDS both negative sense AND positive sense [executions flow through extraction; 4 FILLED LIMIT orders matched cleanly via Shape A/B without needing Shape C tier-1 corrections because operator's journal prices already align]).
- **S4 PASS** — Phase 10 banner cleared to 0 after 2 dispositions (run #14 ids 50+51 — same Pass-1-NO-MATCH DHC+VSAT family run #13 handled identically; `acknowledge` per C.D-precedent for `ambiguity_kind=unsupported`; correction_ids 15+16).
- **S5 PASS** — ruff 18 E501 unchanged.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0** (preserved).
- System EXITS safe-degraded mode. V2 mapper widening's positive lift now confirmed firing on production data via Shape A/B paths.
- 4 historical correction chains preserved (correction_ids 11+12+13+14 from Sub-bundle 1 gate + 15+16 from Sub-bundle 1.5 gate — all acknowledge-only no-mutation entries for DHC+VSAT unmatched-fill family).

### Post-Phase-12 architectural arc CLOSED — Sub-bundle 2 + Phase 12.5 dispatches UNBLOCKED

**Next dispatches** (Phase 12.5; operator-locked 2026-05-17):
1. **Phase 12.5 #1: OQ-F multi-leg tier-1 auto-redirect** — direct V2-mapper-widening successor; consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers + Sub-bundle 1.5's confirmed-firing extraction path. Highest operator-fit value.
2. **Phase 12.5 #2: Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2; web counterpart of C.D's `swing journal discrepancy resolve-ambiguity` + `override-correction` CLIs.
3. **Phase 12.5 #3: CLAUDE.md + orchestrator-context.md maintenance pass** — addresses cap-drift (~50+ entries vs ~30 cap).

**Phase 13 scope LOCKED** at `docs/phase13-scope-brainstorm.md` §0.5 (operator-decided 2026-05-17); dispatch gated on Phase 12.5 close.

### Worktree teardown status

- Branch `schwab-mapper-bundle-1.5` merged via `--no-ff` at `a7c1016`; on-disk husk at `.worktrees/schwab-mapper-bundle-1.5/` ACL-locked pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (branch matches `schwab(?:-\w+)?-bundle-` regex per `cleanup-locked-scratch-dirs.ps1:156`).

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-1.5-validator-drop-fix-executing-plans-dispatch-brief.md` (`aec3019`).
- Return report: `docs/post-phase12-schwab-mapper-bundle-1.5-return-report.md` (in `a7c1016` merge).
- Integration merge: `a7c1016`.
- Sub-bundle 1 SHIPPED entry below: predecessor (PASS-WITH-FINDING; closes the validator-drop defect routing).

### 5 forward-binding lessons (return report §11)

1. **Diagnostic-script pattern generalizable** to any future Schwab API-shape investigation (3-layer redaction + ASCII-only stdout + thin-seam helpers for mock-testability + sentinel-leak audit pattern).
2. **TYPE-only "would_pass_validator" labels are misleading** — always discriminate type vs value-range. Codex R1 M#5 caught the diagnostic script's misleading `legs_would_pass_validator` metric → renamed `legs_would_pass_type_shape_only`.
3. **Canary observability hooks for silently-suppressed code paths require explicit design-decision documentation** — minimal-canary + ACCEPT-WITH-RATIONALE pattern (documented inline in helper docstring) is project-canonical approach for "silent skip" semantics.
4. **Codex-chain brittleness around line-number references** — prefer function/block names + descriptive English over file:line citations in docstrings/comments. AI-generated docstrings often pin line numbers that become stale within months.
5. **T-1.5.4 / S3 operator-witnessed gate sequencing is post-Codex-by-design** — include "operator-witnessed gate sequencing" explicitly in §0.5 BINDING contracts of future briefs to pre-empt Codex Major finding family.

### 1 V2 candidate banked

1. **Separate canary helper for malformed-shape detection** (R2 Minor #2 banked V2). Current `_has_non_placeholder_leg` returns False on malformed (non-coercible) leg prices, preserving no-false-positive contract. Future hardening: separate helper / result enum distinguishing "anomalous positive-price" from "malformed/uncoercible". Documented inline in `_has_non_placeholder_leg` docstring.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 1 SHIPPED — V2 Schwab mapper execution-grain widening + classifier consumer + comparator + housekeeping (FOLDED) — GATE PASS-WITH-FINDING; Sub-bundle 1.5 follow-up dispatch UNBLOCKED

**Sub-bundle 1 SHIPPED 2026-05-17** at `120c992` (integration merge of `schwab-mapper-bundle-1` via `--no-ff`; ~24 implementer commits + 1 orchestrator handoff brief at `54c7b9d`; 26 files / 5225 insertions). 5 Codex rounds NO_NEW_CRITICAL_MAJOR; **ZERO ACCEPT-WITH-RATIONALE banked**; ZERO Co-Authored-By footer drift; +115 fast tests (4360 → 4475); ruff 18 unchanged; schema v19 unchanged.

### Architectural fix lands across 4 surfaces

1. **`swing/integrations/schwab/models.py`** — NEW `SchwabExecutionLeg` frozen dataclass (6 fields; `__post_init__` validators rejecting bool/NaN/inf/zero/negative) + `SchwabOrderResponse.executions: list[SchwabExecutionLeg] | None = None` tri-valued tail field (8-positional backward compat preserved).
2. **`swing/integrations/schwab/mappers.py`** — `map_orders_to_fill_candidates` widened via NEW `_extract_executions_from_order_raw` helper with defensive parsing (non-EXECUTION skip; non-dict skip+warn; leg-validator drop+warn; empty→None collapse; `sum(legs.qty) == filledQuantity` coherence check else collapse; R2 pre-coercion bool/non-str-time rejection).
3. **`swing/trades/schwab_reconciliation.py`** — NEW helpers `_compute_execution_price` (single-leg → leg.price; multi-leg → VWAP), `_resolve_match_quantity` (execution-grain quantity), `_is_execution_bearing_candidate` (candidate-pool widening for MARKET-with-price=None + CANCELED/REPLACED partials). Comparator switched to execution-grain price + Path B `execution_unavailable=true` sentinel emit + Shape C `actual_value_json` shape + 4dp delta_text precision.
4. **`swing/trades/reconciliation_classifier.py`** — NEW `_EXECUTION_AUDIT_KEYS` + `_SHAPE_C_EXPECTED_KEYS` constants. Shape C branch added to `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` (ADDITIVE; Shape A + B preserved). `_classify_unmatched_fill_shared` Path B sentinel recognition (V1 Pass-2 LIFT scope = Pass-1 only; OQ-F V2 deferred).

**Housekeeping FOLDED** per operator decision 2026-05-17:
- CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amended V2-RESOLVED for Pass-1 family.
- CVGI date typo verified ZERO matches in CLAUDE.md (no-op-with-note).
- NEW `swing journal discrepancy show-correction <id>` CLI subcommand + generic ID-free `_HISTORICAL_CORRECTION_NOTE` epilog (per spec §8.3 OQ-G + plan §A.0.1 D1).

**Infrastructure**: T-1.0 cassette runbook at `docs/runbooks/schwab-cassette-recording.md` + NEW `scripts/record_schwab_cassettes.py` (686 lines) + `tests/conftest.py:vcr_config` sanitization filter extension. Operator-paired cassette session `ec498fe` recorded 3 of 4 REQUIRED order types (MARKET BUY + STOP_LIMIT FIRED hand-rolled per operator history absence). Codex R3 Critical accountNumber leak + R4 over-redaction both fixed in-place across the 3 committed cassettes at `tests/integrations/cassettes/schwab/`.

**E2E test (T-1.13; `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py`):** 6 slow tests exercising 3 cassette-driven + 3 hand-rolled fixtures end-to-end through the mapper → comparator → classifier → audit-row persistence pipeline.

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4475 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~93s wall-clock).
- **S2 PASS** — 6 slow E2E tests via cassette + hand-rolled fixtures (4.35s).
- **S3 PASS-WITH-FINDING** — `python -m swing.cli schwab fetch --orders` from worktree emitted reconciliation_run #13 (state=completed; discrepancies_emitted=2; tier1_applied_count=0; tier2_pending_count=2). **ZERO false-positive entry/close_price_mismatch** confirms architectural fix HOLDS in negative sense. **CRITICAL FINDING (routes to Sub-bundle 1.5)**: ALL 18 production orders had `orderActivityCollection[0].executionLegs[0]` uniformly rejected by `SchwabExecutionLeg.__post_init__` validator at mapper drop+warn. Positive lift NEVER FIRED on production despite cassette + hand-rolled E2E tests all passing. Root cause unknown — `schwab_api_calls` does NOT capture `response_body_json`. Hypothesis: synthetic-fixture-vs-production-emitter shape drift family (C.D-arc lesson #2 + #4 inheritance).
- **S4 SKIPPED** operator preference (S3 sufficient).
- **S5 PASS** — Phase 10 banner cleared to 0 after 4 dispositions (run #12 ids 46+47 + run #13 ids 48+49 — all DHC+VSAT unmatched_open_fill; `acknowledge` per C.D-precedent for `ambiguity_kind='unsupported'`; correction_ids 11+12+13+14). 4 dispositioned because run #12 fired ~3 min before our gate (per-run-vs-per-fill re-emission family).
- **S6 + S7** deferred operator-async review (CLAUDE.md gotcha amendment text + `show-correction --help` epilog).
- **S8 PASS** — ruff 18 E501 unchanged.
- **S9 SKIPPED** optional.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0.**
- System operating in safe-degraded mode (V1-equivalent behavior + Path B sentinel emit; no false-positives; positive lift gated on Sub-bundle 1.5 fix).
- 4 historical correction chains preserved (correction_ids 11+12+13+14 are acknowledge-only no-mutation entries for DHC fill_id=2 + VSAT fill_id=6).

### Sub-bundle 1.5 follow-up dispatch UNBLOCKED — NEXT ORCHESTRATOR FIRST DELIVERABLE

**Scope**: validator-drop defect investigation + fix.
- **Diagnostic phase**: capture raw Schwab response shape for one failing order (options: temp debug logging at mapper drop-point + re-run schwab fetch; OR one-shot direct API call via schwabdev bypassing mapper; OR schema extension to capture `response_body_json` — implementer picks).
- **Fix phase**: amend validator OR amend mapper pre-coercion OR amend field-extraction to match actual Schwab production shape. Discriminating regression test landing in cassette form.
- **Re-verification**: re-run S3 against production; verify `tier1_applied_count > 0` IF eligible discrepancies, OR at minimum NO validator-drop warnings logged.

**Dispatch metadata**:
- Branch: `schwab-mapper-bundle-1.5` (matches cleanup-script regex `schwab(?:-\w+)?-bundle-`)
- Worktree: `.worktrees/schwab-mapper-bundle-1.5/`
- Codex chain budget: 2-4 rounds (focused defect fix)
- Gate: 3-5 surfaces (S1 fast tests + S2 cassette + S3 production re-run + S4 banner + S5 ruff)
- Schema impact: likely v19 unchanged unless schema extension chosen for diagnostic capture

### Worktree teardown status

- Branch `schwab-mapper-bundle-1` merged via `--no-ff` at `120c992`; on-disk husk at `.worktrees/schwab-mapper-bundle-1/` ACL-locked pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass.

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-1-execution-grain-widening-executing-plans-dispatch-brief.md` (`e2a11bf`).
- Plan: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (`cc6fd2d`).
- Spec: `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (`dda8730`).
- Integration merge: `120c992`.
- Handoff brief: `docs/orchestrator-handoff-2026-05-17-post-sub-bundle-1.md` (`54c7b9d`).

---

## 2026-05-17 Phase 12.5 RESCOPED — 3-item bundle (operator-locked scope; queued post-Sub-bundle-2 ship of post-Phase-12 mapper-widening arc; item #2 fill auto-population FOLDED INTO Phase 13 Theme 3 per operator decision 2026-05-17)

**Scope (operator-locked 2026-05-17; rescoped 2026-05-17 to drop fill auto-population → moved to Phase 13 Theme 3 which absorbs entries + exits + reviews coherently):**

1. **OQ-F multi-leg tier-1 auto-redirect** — direct successor to V2 mapper widening. When V2 mapper exposes execution-grain data for multi-leg fills (sum of `executionLegs[].quantity` matches journal qty + per-leg VWAPs align within `price_tolerance`), classifier auto-redirects tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` instead of forcing operator menu disposition. Spec §6.6 V2 LOCK + writing-plans §Z #1 V2 candidate. Cascade analysis required: confidence threshold; classifier dispatch state; auto-correct handler shape (consumes Sub-bundle C.C `apply_tier2_resolution(..., choice_code='split_into_partials', payload=...)` with operator-derived payload synthesized from execution-leg data); operator-decided UX (does the auto-redirect emit a banner advisory? Surface for review?). **Estimated 2-3 sub-bundles** (brainstorm + writing-plans + 1-2 executing-plans dispatches); **schema v19 likely unchanged** (auto-redirect consumes existing handler registry).
2. **Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2. Web counterpart of C.D's `swing journal discrepancy resolve-ambiguity` + `override-correction` CLIs. Operator-facing HTMX form for tier-2 menu selection + `--custom-value` shape entry + tier-3 override workflow. Inherits Sub-bundle B + 2 web architecture (apply_overrides cascade; HTMX gotcha trinity; base-layout VM banner pin; Phase 6 I3 target-route-registered check). **Estimated 1-2 sub-bundles**; consumes existing C.C service entries + C.D CLI menu helper unchanged.
3. **Project hygiene maintenance pass** — addresses cap-drift + test stability + ruff cleanup in one focused dispatch (operator-requested scope expansion 2026-05-17 post-Sub-bundle-1.5-merge). Five sub-items:
   - **(a) CLAUDE.md archive-split** — active status-line paragraph cap-drift (~52 entries vs ~30 cap); archive SHIPPED phase entries to `CLAUDE.md.archive` following 2026-05-05 archive-companion precedent; preserve index/cross-references in active file.
   - **(b) orchestrator-context.md archive-split** — active "Lessons captured" section growing past retention discipline cap (~52 entries vs ~30); archive older lessons to `docs/orchestrator-context-archive.md` (already present); preserve in-flight + recent-lesson framing.
   - **(c) V2.1 §VII.F amendment batch processing** — ~17 cumulative amendments pending across Phase 9/10/12 + post-Phase-12 brainstorm + writing-plans (per Phase 13 scope-brainstorm §3 OQ-6 disposition). Process the batch atomically; commit amended spec/plan/brief documents through V2.1 §VII.F correction-protocol routing.
   - **(d) Phase 8 walkthrough failing-test triage + fix** — 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` unchanged since Phase 8 ship (`test_phase8_pipeline_emits_snapshots_for_open_trades_only` + `test_phase8_pipeline_second_same_day_run_upserts` + `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id`). Operator-requested review + correction (post-Sub-bundle-1.5 2026-05-17). Root cause investigation first (was banked at Phase 8 ship without immediate fix); decide whether to fix the tests (test-side drift) OR fix the production behavior (real regression) OR mark `xfail` with documented rationale.
   - **(e) Ruff 18 E501 cleanup** — long-line warnings accumulated across Phase 11/12 + post-Phase-12 ship; banked since polish-bundle-2026-05-10 N818 sweep. Manual review + targeted wraps (favor variable extraction over noqa) to bring baseline back toward zero. Operator-requested cleanup (post-Sub-bundle-1.5 2026-05-17).

   **Estimated 1-2 dispatches** (docs+test+style; mostly docs/test hygiene; ZERO production-architecture surface). (d) may need 1 Codex round if root-cause investigation surfaces real production-behavior drift; (a)+(b)+(c)+(e) are zero-Codex.

**Sequencing rationale (orchestrator-recommended):**
- **1 first** because it's the direct architectural successor to V2 mapper widening; closes the OQ-F V2 LOCK that Sub-bundle 1 explicitly defers; Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers are the load-bearing primitives auto-redirect consumes. Highest operator-fit value.
- **2 second** because it's smaller scope + consumes already-shipped C.C/C.D surfaces; standalone web-counterpart work.
- **3 third** because (a)+(b)+(c)+(e) are docs/style-only (cheap; opportunistically schedulable; prevents cap-drift compounding) AND (d) phase8 walkthrough triage is operator-paced investigation (cheap if test-side drift; bounded Codex round if real production-behavior drift surfaces).

**Rescope note (2026-05-17):** Original Phase 12.5 #2 (Fill auto-population at trade-entry time) MOVED to Phase 13 Theme 3 (Auto-fill deepening across entries + exits + reviews) per operator decision. The broader Phase 13 auto-fill scope (entries + exits + reviews + period reviews) would have required Phase 12.5 #2 to be refactored once Phase 13 lands; folding it into Phase 13 from the start avoids that refactor cost.

**Pre-flight check before Phase 12.5 dispatch:**
- Post-Phase-12 mapper-widening arc (Sub-bundle 1 + 2) MUST be SHIPPED + integration-merged. Phase 12.5 #1 (OQ-F auto-redirect) consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers; cannot dispatch before.
- Operator confirms Phase 12.5 scope is still LIVE at dispatch time (~weeks-to-months out depending on Phase 13 sequencing decisions); may want to adjust per learnings from Sub-bundle 1+2 gates.
- V2.1 §VII.F amendment batch processing may benefit from being folded into Phase 12.5 #4 maintenance pass — operator decision.

**Cross-references:**
- Spec §6.6 OQ-F V2 LOCK: `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`
- Sub-bundle C plan §I.3 (web Tier-2 V2): `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`
- Phase 12 Sub-bundle C brainstorm §1.6 (fill auto-population at entry): `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`
- Writing-plans §Z V2 candidates: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §Z

---

## 2026-05-17 Phase 13 scope-brainstorm DOC IN PROGRESS — formal scope development while Sub-bundle 1 implementer is in execution

See `docs/phase13-scope-brainstorm.md` for the surveying-categories + candidate-options + discriminating-questions doc. Operator-paced. Phase 13 candidate triage is the strategic conversation post-Phase-12 mapper-widening arc + Phase 12.5 closure.

---

## 2026-05-17 Phase 12 Sub-sub-bundle C.D SHIPPED — Tier-2 CLI + reconcile-backfill + Phase 10 banner widening (CLOSES Sub-bundle C; 4 Codex rounds + 3 orchestrator-inline gate-fixes + 7 production-discrepancy dispositions; 10-surface operator-witnessed gate THE BIG ONE — largest in project history; ZERO ACCEPT-WITH-RATIONALE banked; ~33 commits; CRITICAL ARCHITECTURAL FINDING: Pass-1 tier-1 entry_price_mismatch shares limit-vs-fill defect with Pass-2-tier-1-FORBIDDEN — V2 mapper widening priority bumped)

**Sub-sub-bundle C.D SHIPPED 2026-05-17** at `bd1a62b` (integration merge of `phase12-bundle-C-D-tier2-cli-and-backfill` via `--no-ff`). Branch HEAD `32812f7` (~33 commits = 15 task-impl (T-D.1..T-D.14 + T-D.6.1) + 1 pre-Codex review fix + 10 Codex-driven fixes (4 R1 + 4 R2 + 1 R3 + 1 R4) + 3 ORCHESTRATOR-INLINE GATE-FIXES + 1 return-report). Operator-dispatched implementer per orchestrator brief at `047e3db`.

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/3M/2m → R2 0C/3M/1m → R3 0C/0M/1m → R4 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 14 findings resolved with code-content fixes (ties cleanest sub-sub-bundle in Phase 12 arc); ZERO Co-Authored-By footer drift across all ~33 commits (C.B forward-binding lesson #7 carry-forward worked for 2nd time); pre-Codex orchestrator-side review absorbed 1 Major + 1 Minor (NEW C.C lesson #6 validated for 2nd time).

**+156 fast tests** (4204 → 4360 worktree-side; ~4363 main HEAD post-merge); ruff 18 unchanged; schema v19 unchanged consumer-side.

### 10-surface operator-witnessed gate ALL PASS (orchestrator-driven 2026-05-17 — THE BIG ONE)

S1 fast suite ✅ 4360 pass; S2 dry-run ✅ classification matrix showed 7 unresolved-material (4 more than handoff brief expected — Run #11 emerged between C.B+C.C merges + included NEW LION not in handoff); S3a CVGI tier-1 + S3b LION tier-1 ⚠️ APPLIED-THEN-OVERRIDE per critical operator pushback (limit-vs-fill defect surfaced — see architectural finding below); RECOVERY A1+A2+B2 via `override-correction` restored fills.price to operator's TOS Net Price values; S4a/S4b DHC+VSAT tier-2 stamps ✅; S5 show-ambiguity 39 ✅ (post-gate-fix-#3 § glyph restored); S6a synthetic-fixture acceptance ✅ 18/18 PASS in 5.64s; S6b operator-real DHC 39 `mark_unmatched` + S6b.dup DHC 42 `acknowledge`; S7 VSAT 40+43 `acknowledge`; S8 Phase 10 banner clears to ZERO ✅ via `swing web --port 8081` curl-grep; S9 ruff 18 ✅; S10 cycle-checklist + 6 CLAUDE.md gotcha additions verified ✅.

### 3 ORCHESTRATOR-INLINE GATE-FIXES (committed on worktree branch + merged)

1. **Gate-fix #1 `a542f65`**: swap U+2192 `→` to ASCII `->` in `_format_pass_2_line` at `swing/trades/reconciliation_backfill.py:512` — Windows PowerShell stdout cp1252 crash during S2 dry-run.
2. **Gate-fix #2 `34d74f7`**: `_handle_no_mutation_audit` handles synthetic `field_name='fill_match'` for `unmatched_open_fill`/`unmatched_close_fill` discrepancies — `_DiscrepancyInfo` extended with `expected_value_json`; helper branches on `discrepancy_type` to skip column read.
3. **Gate-fix #3 `32812f7`**: force UTF-8 on `sys.stdout`/`sys.stderr` at `swing/cli.py` entry — defense-in-depth covering all non-ASCII glyphs.

### 7 production-discrepancy dispositions (post-gate: banner count=0)

- **41 CVGI** + **44 CVGI** → `operator_overridden` chain heads correction_ids 3+4 (S3a wrong tier-1 → A1+A2 override-back to $5.23 per operator's TOS Net Price $5.2244)
- **45 LION** → `operator_overridden` chain head correction_id 6 (B1 wrong tier-1 → B2 override-back to $12.70 per operator's TOS Net Price $12.6999)
- **39 DHC** → `mark_unmatched` correction_id 7
- **42 DHC**, **40 VSAT**, **43 VSAT** → `acknowledge` correction_ids 8+9+10 (pre-Phase-11 entries; Schwab order-history incomplete; journal canonical per operator's TOS context)

Production fills.price restored: CVGI fill 9 = $5.23; LION fill 15 = $12.70.

### CRITICAL architectural finding: Pass-1 tier-1 entry_price_mismatch limit-vs-fill defect

V1 Schwab mapper at `swing/integrations/schwab/mappers.py:223-230` reads `order.price` (LIMIT or STOP TRIGGER) — NOT `orderActivityCollection[].executionLegs[].price` (EXECUTION). Reconciliation comparator at `swing/trades/schwab_reconciliation.py:693` compares `so.price` (limit) vs journal `f.price` (execution); when limit ≠ execution (typical for slippage / VWAP / partial fills), emits false `entry_price_mismatch`. Both CVGI ($5.30 limit vs $5.2244 fill) + LION ($12.75 limit vs $12.6999 fill) empirically falsified the operator-locked Pass-1 "order/limit ≈ execution" assumption. **CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha AMENDED at integration housekeeping to cover Pass-1 family.** `close_price_mismatch` has same defect (same code path). `stop_mismatch` is architecturally sound (trigger-vs-trigger comparison).

### V2 mapper widening: priority BUMPED (operator-locked next-architectural-dispatch slot)

Per OQ-4 + plan §I.1: widen mapper to expose `orderActivityCollection[].executionLegs[].price` for execution-grain comparison. Already operator-locked as next dispatch; today's gate evidence demonstrates the assumption breaks operationally + bumps priority. Pre-V2 operator workflow: `reconcile-backfill --apply` then manual TOS-audit + tier-3 `override-correction` on any wrong tier-1 corrections. **Brainstorm dispatch needed.**

### 2 NEW CLAUDE.md gotcha promotions

1. **Windows PowerShell stdout cp1252 family** — non-ASCII glyphs (`§`/`→`/etc.) in CLI output paths crash on Windows; canonical fix is ASCII swap + defense-in-depth UTF-8 stdout reconfigure.
2. **Synthetic-fixture-vs-production-emitter shape drift** — test fixtures planting real column names pass; production emitter using synthetic field labels (e.g., `field_name='fill_match'`) breaks; pre-empt via discriminating tests using production-shape values.

### Sub-bundle C arc closer aggregate (4 sub-sub-bundles SHIPPED 2026-05-15 → 2026-05-17)

- **Cumulative commits**: ~88 (A=16 + B=26 + C=23 + D=33 - merge overhead)
- **Cumulative Codex rounds**: 14 (A=2 + B=5 + C=3 + D=4)
- **Cumulative fast tests**: +494 (104 + 139 + 95 + 156)
- **Cumulative ACCEPT-WITH-RATIONALE**: 1 (C.A backup-gate; ZERO in B+C+D)
- **Cumulative Co-Authored-By footer drift**: 0 (C.B caught + rebase-stripped pre-merge; C.C + C.D held the line via explicit dispatch-prompt citation)
- **Schema v18 → v19** at C.A T-A.1 atomic single-file landing; consumer-side only through B+C+D
- **CLAUDE.md gotchas promoted**: ~8 across arc (3 C.A + 1 C.B + 4 C.C + 3 C.D)
- **V2.1 §VII.F amendments pending**: ~17 across arc (5 C.A + 6 C.B + 6 C.C + ~5 C.D)
- **V2 candidates banked**: ~25 across arc; **headline V2 = mapper widening** (operator-locked next architectural dispatch; priority BUMPED per today's gate evidence)

### Worktree teardown status

Branch `phase12-bundle-C-D-tier2-cli-and-backfill` pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`. On-disk husk at `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/` ACL-locked; cleanup-script regex matches cleanly. **4 phase12-bundle-c-* husks total pending** (A+B+C+D).

---

## 2026-05-16 Phase 12 Sub-sub-bundle C.C SHIPPED — Auto-correction service + reconciliation flow pivot (4 public service fns + 17+1 handlers + savepoint-per-discrepancy pivot at BOTH Schwab + TOS reconciliation; 3 Codex rounds NO_NEW_CRITICAL_MAJOR — ties C.A for fastest Phase 12 chain; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; 23 commits; THIRD Phase 12 Sub-bundle C sub-sub-bundle; Sub-bundle C 75% shipped)

**Sub-sub-bundle C.C SHIPPED 2026-05-16** at `0b9d253` (integration merge of `phase12-bundle-C-C-auto-correction-service-and-flow-pivot` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `97fc8b9` (23 commits = 12 task-impl T-C.1..T-C.11 + T-C.3.1 + 1 UP035/UP017/I001/F401/SIM118/B905/N802 ruff baseline-restore + 3 pre-Codex review fixes (SC-1 sandbox-threading + SC-2 T-C.11 E2E scope + SC-1 follow-up sandbox-precedence) + 4 Codex-R1-fix + 1 Codex-R2-fix + 1 Codex-R3-polish + 1 return-report on top of dispatch brief `5ed3e74`). Operator-dispatched implementer per orchestrator brief at `5ed3e74`.

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/0m → R2 0C/1M/0m → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 R1 Major + 1 R2 Major + 1 R3 Minor resolved with code-content fixes. **Ties Phase 12 Sub-sub-bundle C.A's 2-round chain for FASTEST Phase 12 chain** (C.A=2, C.B=5, C.C=3; Sub-bundle C-arc average so far = 3.3 rounds). **ZERO Co-Authored-By footer drift** entire 23-commit chain — C.B forward-binding lesson #7 carry-forward worked. The dispatch prompt's explicit citation of CLAUDE.md "No Claude co-author footer" convention with reference to the C.B R1 fix-bundle recurrence-prevention pattern prevented the drift. **Pre-Codex orchestrator-side review absorbed 2 Major findings** (SC-1 sandbox threading + SC-2 T-C.11 E2E scope) saving an estimated 1-2 Codex rounds (NEW lesson #6 banked at return report §10).

### Operator-witnessed gate (2026-05-16 post-merge-prep; orchestrator-driven; 4 surfaces ALL PASS)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 4200 fast pass on C.C branch (88.70s wall-clock) + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (the 2 C.A cross-bundle pin tests un-skipped at C.B T-B.14 still PASS post-rebase) |
| S2 production-env walkthrough | ✅ | Explicit `python -c` harness invoked `apply_tier1_correction(env='production')` against CVGI 41 fixture seeded via test helper `_seed_cvgi_world`; BEFORE state `fills.price=$5.23` + `discrepancy.resolution='unresolved'` + 0 correction rows + 0 trade_events → CALL returned `correction_id=1`/`action='auto_applied'`/`affected_table='fills'`/`field='price'` → AFTER state `fills.price=$5.30` + `discrepancy.resolution='auto_corrected_from_schwab'`/`resolved_by='auto'` + 1 correction row + 1 `trade_events.event_type='reconciliation_auto_correct'` row; full spec §10.1 end-to-end mutation verified |
| S3 sandbox-env walkthrough | ✅ | Same harness invoked `apply_tier1_correction(env='sandbox')` against fresh CVGI fixture; CALL returned `correction_id=None` + `notes='sandbox: domain write short-circuited'` + WARNING log line `_apply_tier1_correction_inner short-circuited under sandbox environment for discrepancy_id=41` emitted per spec §5.9; AFTER state byte-for-byte identical to BEFORE — ZERO journal mutation, ZERO audit rows, discrepancy stays `unresolved` |
| S4 ruff baseline | ✅ | 18 E501 unchanged |

### Code deltas (no schema; pure service + flow-pivot + briefing extension per dispatch brief §0.5 #1 LOCK)

1. **NEW MODULE `swing/trades/reconciliation_auto_correct.py`** — 4 public service functions (`apply_tier1_correction` + `apply_tier2_resolution` + `apply_tier3_override` + `stamp_pending_ambiguity`) + 4 caller-tx inner variants + 3 exception classes (`CallerHeldTransactionError` / `ValidatorRejectedError` / `AlreadySupersededError`) + `CorrectionResult` dataclass + 17+1 per-(`ambiguity_kind`, `choice_code`) handler registry with `_PICK_SCHWAB_RECORD_PREFIX` parametric entry + savepoint-per-discrepancy pivot helper `_pivot_classify_and_dispatch_for_run` shared across Schwab+TOS via lazy import. Per spec §5 + §7 + §10 LOCKs preserved verbatim.
2. **MODIFIED `swing/trades/schwab_reconciliation.py`** — flow pivot at `run_schwab_reconciliation` Step 2 classify+dispatch loop with savepoint-per-discrepancy discipline (spec §7.1 LOCK; fresh-savepoint fallback for tier-2 stamp on validator-rejection path per writing-plans R2 Minor #1 LOCK) + `summary_json` counters (`tier1_applied_count` / `tier2_pending_count` / `tier3_overridden_count` ZERO at run-time) + post-pivot `unresolved_discrepancies_count` recompute (R1 M#3 fix).
3. **MODIFIED `swing/trades/reconciliation.py`** — TOS flow pivot mirror at `run_tos_reconciliation` per OQ-2 PIVOT BOTH; consumes shared pivot helper via lazy import (NEW lesson #5 banked).
4. **MODIFIED `swing/rendering/briefing.py`** + **`swing/rendering/briefing_md.py`** — `BriefingInputs` extended with `reconciliation_pending_count` + `reconciliation_tier1_recent_count` fields; "Reconciliation status" section emits when counters non-zero per spec §7.5.
5. **MODIFIED `swing/pipeline/runner.py:_step_export`** — wires counters via inline SQL.
6. **MODIFIED `swing/data/repos/reconciliation.py` (RESOLUTION_TYPES Python constant)** — widened 5→9 values mirroring `_RESOLUTION_VALUES` per R1 M#4 (schema-CHECK + Python-constant + dataclass-validator paired discipline gotcha applied to a SECOND Python-side mirror; the manual `resolve_discrepancy` CLI surface accepted the new service-owned states which it should NOT) + tightened `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist per R2 M#1 (4 service-owned states route through canonical service entries NOT manual `resolve_discrepancy`; NEW lesson #1 banked).
7. **12 NEW TEST FILES** under `tests/trades/` + `tests/rendering/` + `tests/pipeline/` + `tests/integration/` covering transactional discipline, atomic flows for all 3 tiers, savepoint regression suite, flow pivot at both reconciliation entry points, briefing extension, _step_export wire, and T-C.11 slow E2E `test_phase12_bundle_c_cvgi_41_end_to_end` (mirrors Phase 11 D R1 M#4 ACCEPT-WITH-RATIONALE precedent at scope; tests service-composition + `_step_export` invocation per pre-Codex SC-2 widening).

### NEW V2.1 §VII.F amendment candidates banked (6 items per return report §5)

1. **D1 pivot helper relocation candidate** — `_pivot_classify_and_dispatch_for_run` currently lives in `reconciliation_auto_correct.py` but is consumed by both `schwab_reconciliation.py` + `reconciliation.py` via lazy import; V2 candidate to relocate to neutral module (NEW lesson #5 watch item).
2. **D2 sentinel rule wording** — spec §3.1.1 `__delete__`/`__insert__` sentinel handling could be clarified at writing-plans level (multi-fill split-into-partials handler is the only V1 consumer).
3. **D3 test-side adjustments dependency on C.D filter widening** — Phase 9 Sub-bundle B unresolved-material list filter currently keys on `resolution='unresolved'` only; C.D banner predicate widening to include `pending_ambiguity_resolution` cascades to filter widening too (transitive helper effect; documented for C.D dispatch).
4. **D4 SAVEPOINT-uniqueness test mechanic** — current uniqueness assertion relies on PK autoincrement; V2 candidate for explicit unique-name discriminating test.
5. **D5 inline SQL vs repo helpers** — `_step_export` uses inline SQL for the new counters rather than introducing repo helpers; V2 candidate to formalize as `count_discrepancies_pending_ambiguity` / `count_corrections_tier1_recent` repo functions.
6. **D6 T-C.11 scope** + **D7 view_models.py touch** — both are scope-boundary clarifications for the cross-bundle interaction with Phase 10 (deferred until C.D Phase 10 banner widening lands).

### Three highest-leverage SHIPPED deliverables

1. **Auto-correction service layer as the canonical INSERT-time enforcement boundary.** Lifecycle invariants on `reconciliation_corrections` rows (`correction_action='auto_applied'` implies `applied_by='auto'`; tier-3 override requires non-null `operator_truth_value_json`; tier-1 cannot land with non-NULL `ambiguity_kind`) enforced at C.C `apply_*_inner` INSERT time per spec §5.4 + C.B forward-binding lesson #1. SELECT-first idempotency precedes payload validation per R1 M#2 (NEW lesson #3 banked). Outer transaction discipline UNIFORM regardless of sandbox per R1 M#1 (NEW lesson #2 banked) — outer ALWAYS `BEGIN IMMEDIATE`; inner short-circuits sandbox cases internally.
2. **Savepoint-per-discrepancy pivot enables graceful degradation under per-discrepancy classifier/apply failures.** Spec §7.1 LOCK preserved verbatim: `SAVEPOINT correction_sp_<discrepancy_id>` per iteration; RELEASE on success; ROLLBACK TO + RELEASE on failure; validator-rejection fallback uses FRESH `correction_fallback_sp_<discrepancy_id>` (writing-plans R2 Minor #1 fix). Outer reconciliation_run transaction survives per-discrepancy failures with WARNING-logged failures captured in `summary_json.tier_errored` counter. T-C.7 savepoint discipline regression suite locks the invariant.
3. **Production reconciliation flow pivot landed at BOTH Schwab + TOS entry points per OQ-2 PIVOT BOTH.** `_pivot_classify_and_dispatch_for_run` extracted as shared helper (NEW lesson #5 DRY discipline) via lazy import to break circular dependencies. Briefing.md "Reconciliation status" section + counter wires in `_step_export` mean every future pipeline run emits operator-visible state about pending tier-2 ambiguities + recent tier-1 auto-corrects. **3 unresolved material discrepancies (39 DHC + 40 VSAT + 41 CVGI) LEFT UNRESOLVED BY DESIGN** pending C.D backfill operation — production reconciliation flow will dispatch tier-1/tier-2 inline on next run, but existing discrepancies (`resolution='unresolved'`) aren't re-classified by the flow pivot which only acts on freshly-emitted rows.

### Forward-binding lessons for C.D dispatch (per return report §10)

1. **Schema-coverage constant ≠ manual-resolver allowlist.** When widening a Python enum to mirror schema CHECK, audit every existing manual callsite that validates against the constant. Service-owned values (requiring routing through specific service entries) MUST have a separate tighter allowlist for the manual path. Discriminating test: per-service-owned-value rejection with routing hint substring in error message.
2. **Outer transaction discipline UNIFORM regardless of sandbox.** Sandbox short-circuit MUST live in the inner (caller-tx) function, NOT the outer (own-tx) function. Outer ALWAYS issues `BEGIN IMMEDIATE` → call inner → `COMMIT` (or ROLLBACK). Inner short-circuits internally. Prevents (a) outer-skip bypassing caller-held-tx check + (b) nonexistent discrepancy_id succeeding as silent no-op.
3. **SELECT-first idempotency must precede payload validation.** Reorder: (1) sandbox short-circuit, (2) SELECT + None-check, (3) terminal-state idempotent return, (4) payload validation, (5) atomic flow. Terminal discrepancy returns existing `correction_id` even with stale/malformed/None payload.
4. **Counter staleness after inline state mutation requires post-loop recompute.** When a flow emits rows incrementing counters THEN mutates those rows' states, the run-summary counter MUST be recomputed via `SELECT COUNT(*)` post-loop. Inline mutation invalidates emit-time counters.
5. **DRY helper extraction across pivot mirror sites with lazy import.** When plan says "mirrors T-X verbatim" + mirror is non-trivial (100+ lines), extract a private helper; lazy-import to break circular dependencies. Watch item: asymmetric import direction = V2 candidate to relocate to neutral module.
6. **Pre-Codex orchestrator-side review catches LOCK divergences cheaply.** Orchestrator-side spec-compliance + code-quality review BEFORE invoking adversarial-critic saves an estimated 1-2 Codex rounds. Pattern: dispatch a focused reviewer subagent with the plan acceptance criteria + brief BINDING contracts as anchors, ask for a deviation list ≤600 words.
7. **Implementer self-report accuracy gate.** Implementer self-report MUST cite specific file:line evidence for each fix claim; orchestrator-side review MUST verify the cited lines actually match the claim (regression tests pinning wrong behavior can pass while violating the LOCK).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) ~4-5 days remaining (expires 2026-05-22). C.D dispatch likely consumes 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md` (`5ed3e74`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans) §D C.C section (lines 1604-2569).
- Return report: `docs/phase12-bundle-C-C-return-report.md` (`97fc8b9`).
- Integration merge: `0b9d253`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner predicate widening — CLOSES Sub-bundle C) UNBLOCKED.** Per plan §E decomposition: 16 tasks (T-D.1..T-D.14 + T-D.6.1 + T-D.11); +55-80 fast tests projected; 4-6 Codex rounds expected; **10-surface operator-witnessed gate per plan §G.4** including S6 synthetic-fixture-only acceptance test for `--custom-value` payload contract per brainstorm lesson "synthetic-fixture-only acceptance test for production-write-contract surfaces" + S6b operator-real-disposition of DHC 39 (per spec §15.5 LOCKED revised mechanic). Will consume `apply_tier2_resolution` + `apply_tier3_override` + `stamp_pending_ambiguity` from C.C + `classify_discrepancy` + `default_validator_chain` from C.B + `insert_correction` from C.A. **Production backfill of 39 DHC + 40 VSAT + 41 CVGI** via `swing journal reconcile-backfill --apply` is the operator-witnessed gate centerpiece at S3+S4+S6+S7 — CVGI 41 → auto-correct tier-1; DHC 39 + VSAT 40 → pending_ambiguity_resolution; operator dispositions per real data. **Phase 10 dashboard banner predicate widening** to include `pending_ambiguity_resolution` alongside `unresolved` retrofits 10 base-layout VMs (per spec §A.5; 14 VM-instance regression tests for defense-in-depth). **Recommended timing: dispatched post-handoff-or-when-operator-commissions** per operator-paced cadence.

---

## 2026-05-15 Phase 12 Sub-sub-bundle C.B SHIPPED — Classifier + validator-shim modules (pure logic; ZERO journal mutations; 5 Codex rounds NO_NEW_CRITICAL_MAJOR; 26 commits; ZERO ACCEPT-WITH-RATIONALE — cleanest finding-disposition in Phase 12 arc; SECOND Phase 12 Sub-bundle C sub-sub-bundle)

**Sub-sub-bundle C.B SHIPPED 2026-05-15** at `aacd1cd` (integration merge of `phase12-bundle-C-B-classifier-and-validator-shim` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `c48188a` post orchestrator-side rebase (26 commits = 14 task-impl + 1 UP035 ruff style + 4 Codex-R1-fix + 2 Codex-R2-fix + 1 R2-N806-style + 2 Codex-R3-fix + 1 Codex-R4-fix + 1 return-report on top of dispatch brief `fdb4276`). Operator-dispatched implementer per orchestrator brief at `fdb4276`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/3M/0m → R2 0C/1M/1m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 1 Critical + 6 Major + 2 Minor resolved with code-content fixes. **Cleanest finding-disposition record in Phase 12 arc to date** (C.A had 1 ACCEPT-WITH-RATIONALE; Sub-bundle B had 0 but with 7 Major; C.B closes 1 Critical + 6 Major + 2 Minor with zero deferrals). R1 C#1 + R2 M#1 + R3 M#1 + R4 M#1 form a single **determinism-principle-tightening sequence on `entry_price_mismatch`** Shape B predicate — each round tightened further; R5 converged.

### Orchestrator-side rebase (Co-Authored-By footer strip; operator-decision 2026-05-15)

R1 fix-bundle 4 commits accidentally carried `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer (CLAUDE.md says "No Claude co-author footer"). Implementer surfaced as deviation #3 in return report §5 with two options: rebase-strip pre-merge OR accept-drift into history. Operator elected **rebase-strip via AskUserQuestion 2026-05-15**. Orchestrator performed `git rebase -i fdb4276` with `GIT_SEQUENCE_EDITOR` marking the 4 commits as `reword` + `GIT_EDITOR` Python one-liner stripping the footer line + rstripping trailing whitespace. SHAs shifted (`6e4bd30→a14401c` / `fcff4d3→63909f5` / `180838e→1cd5951` / `78d98b2→69a2cc8`); 26-commit count preserved; content unchanged; ZERO footer matches on `fdb4276..HEAD` post-rebase confirmed via grep. CLAUDE.md `No Claude co-author footer` convention preserved on integrated history. **Forward-binding lesson #7 banked**: future dispatch prompts MUST explicitly suppress the footer in subagent context (passive inheritance from CLAUDE.md is insufficient because subagents have isolated context).

### Code deltas (no schema; pure logic per dispatch brief §0.5 #1 LOCK)

1. **NEW MODULE `swing/trades/reconciliation_classifier.py`** — 10 per-discrepancy-type sub-classifiers + dispatch table + `ClassificationResult` `@dataclass(frozen=True)` + public `classify_discrepancy(...)` entry with validator-respecting-downgrade dispatcher + 4 shared `_candidate_choices_*` helpers. Per spec §4 + §6.2.1 + §8.4 LOCKS preserved verbatim.
2. **NEW MODULE `swing/trades/reconciliation_validators.py`** — 4 dry-run validators `validate_fill_correction` + `validate_trade_correction` + `validate_cash_movement_correction` + `validate_snapshot_correction` with `math.isfinite()` guard on all 5 numeric fields (mirrors `swing/data/models.py` REAL-field discipline) + `default_validator_chain(conn)` dispatcher composing on `affected_table` partial-application. Per spec §5.5 LOCKS preserved verbatim. SELECT-only against the conn passed in; NEVER mutates the DB.
3. **12 NEW TEST FILES** under `tests/trades/` — one per sub-classifier + one for shim validators + one for default chain + public-entry tests + cross-bundle pin strengthening.
4. **2 cross-bundle pin tests un-skipped at T-B.14** at `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` — both strengthened at R1 M#3 (`78d98b2`→`69a2cc8` post-rebase) to discriminatingly pin classifier + validator-chain behavior end-to-end via tmp_path schema-v19 fixture.

### Operator-witnessed gate (2026-05-15 post-merge-prep; orchestrator-driven; 3 surfaces ALL PASS)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 4110 fast pass on rebased C.B branch + 3 pre-existing phase8 walkthrough failures (unchanged from main baseline) + 5 skipped (the 2 C.A cross-bundle pin tests un-skipped at T-B.14 now PASS; 4 Schwab-fixture-not-present skips + 1 Task 7.3 flag-classifier remain) |
| S2 classifier walkthrough | ✅ | Explicit `python -c` walkthrough invoked `classify_discrepancy` against CVGI 41 + DHC 39 + VSAT 40 fixtures per spec §10; ASSERTED expected `ClassificationResult` shapes — CVGI tier=1 `correction_target={'price': 5.30}` with reason matching spec §10.1 verbatim; DHC + VSAT both tier=2 `ambiguity_kind='unsupported'` with `_pass_2_required=True` signal in `correction_reason` matching spec §10.2/10.3 Pass-1 OUTPUT; determinism principle spot-check (CVGI fixture × 100 invocations) byte-for-byte identical via frozen dataclass equality |
| S3 ruff baseline | ✅ | 18 E501 unchanged |

### NEW V2.1 §VII.F amendment candidates banked (6 items per return report §6)

1. **Spec §4.3.1 entry_price_mismatch source_payload shape** — enumerate Shape A persisted-JSON-only `{'price'}` OR Shape B full match-tuple (ticker+date+quantity) explicitly.
2. **Spec §4.3.1 contradictory date evidence** — neither source-side nor journal-side internal date/fill_datetime divergence is addressed; C.B rejects both as tier-2 unsupported per determinism §4.4.
3. **Plan §C.3** — pin `:.2f` rendering format for currency in `correction_reason` strings.
4. **Plan §C.9** — enumerate canonical 4-field comparison vector (`'date'`, `'kind'`, `'amount'`, `'ref'`) for `cash_movement_mismatch` tier-1 multi-field correction.
5. **Spec §5.5** — document `functools.partial` composition requirement between `default_validator_chain` + `classify_discrepancy` explicitly.
6. **Spec §6.2.1** — already locks `pick_schwab_record_<N>` `requires_custom_value=True` per Codex R7 M#2; banked only for cross-reference completeness.

### Three highest-leverage SHIPPED deliverables

1. **Classifier + validator-shim modules as pure-logic foundation for the entire auto-correct reconciliation architecture.** ZERO journal mutations + ZERO Schwab API calls + ZERO transaction management. Sub-sub-bundle C.C will consume `classify_discrepancy` + `default_validator_chain` to build the auto-correction service; Sub-sub-bundle C.D will consume them at backfill time. Spec §4 + §5.5 LOCKS preserved verbatim.
2. **Determinism principle enforcement (spec §4.4) discriminatingly tested.** `entry_price_mismatch` Shape A/B predicate LOCKED through 4-round Codex tightening sequence — partial-tuple OR contradictory-date-evidence (source-side OR journal-side internal inconsistency) → tier-2 `unsupported`. CVGI 100×-invocation determinism test pins reproducibility. Pass-2-tier-1-FORBIDDEN LOCK at T-B.4/T-B.5 parametrized over 6 distinct input shapes; classifier NEVER emits tier-1 from V1 order-grain mapper data.
3. **Cross-bundle pin discipline operational** — both T-A.7 pins un-skipped at T-B.14 + strengthened to discriminatingly pin end-to-end behavior via tmp_path schema-v19 fixture. Demonstrates the project-wide "pin test ships SKIPPED at producer task; un-skips at consumer task landing" discipline working as designed for the C.A→C.B handoff.

### Forward-binding lessons for C.C dispatch (per return report §11)

1. Classifier output is C.B → service-layer enforcement is C.C boundary (lifecycle invariants enforced at `apply_tier1_correction` INSERT time, NOT classifier-output time).
2. Validator chain MUST be re-invoked at C.C apply time (defense-in-depth per spec §4.6 + §5.5 BINDING — schema state may shift between classifier run + apply call).
3. `functools.partial` composition between `default_validator_chain` + `classify_discrepancy` is non-obvious (chain's `(correction_target, *, affected_table, affected_row_id)` signature must be partial-applied to match dispatcher's `validator_chain(correction_target)` single-arg invocation). Pre-empt in C.C dispatch brief.
4. `_pass_2_required=True` is a free-form-string convention in `correction_reason` (NOT a typed field on `ClassificationResult`). C.D backfill reads via substring match. Document exact substring in C.D dispatch brief.
5. Shape predicate tightening discipline (R1 C#1 → R2 M#1 → R3 M#1 → R4 M#1 sequence) — C.C handlers that classify operator-supplied `--custom-value` payloads will face the same scrutiny; implement input-shape checks EXPLICITLY at handler entry; reject unrecognized key sets; reject contradictory evidence within the payload.
6. Same-source-keys-on-source-and-journal evidence convergence pattern — when both `source_payload` AND `journal_row` carry an information field in MULTIPLE forms (e.g., `date` + `fill_datetime`), determinism principle requires each side's internal forms must agree AND both sides must agree with each other.
7. Co-Authored-By footer drift requires EXPLICIT suppression in dispatch prompts (CLAUDE.md passive inheritance is insufficient because subagents have isolated context).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) ~5 days remaining (expires 2026-05-22T17:05:00+00:00). C.C dispatch likely consumes 3-5 days; C.D 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-B-classifier-and-validator-shim-executing-plans-dispatch-brief.md` (`fdb4276`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans) §C C.B section (lines 1068-1601).
- Return report: `docs/phase12-bundle-C-B-return-report.md` (`c48188a` post-rebase).
- Integration merge: `aacd1cd`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.C (Auto-correction service + reconciliation flow pivot) UNBLOCKED.** Per plan §D decomposition: 12 tasks (T-C.1..T-C.11 + T-C.3.1); +65-115 fast tests projected; 4-6 Codex rounds expected. Will consume `classify_discrepancy` + `default_validator_chain` from C.B + `insert_correction` from C.A schema. Transactional discipline (reject caller-held tx; BEGIN IMMEDIATE / COMMIT / ROLLBACK); validator chain re-invocation at apply time; surface-aware audit attribution; flow pivot at `run_schwab_reconciliation` AND `run_tos_reconciliation` callsites. **Recommended timing: dispatched post-handoff-or-when-operator-commissions** per operator-paced cadence.

---

## 2026-05-15 Phase 12 Sub-sub-bundle C.A SHIPPED — Foundation (schema v18→v19 atomic migration + minimal repos for auto-correct reconciliation; 2 Codex rounds NO_NEW_CRITICAL_MAJOR; 16 commits; FIRST Phase 12 Sub-bundle C sub-sub-bundle)

**Sub-sub-bundle C.A SHIPPED 2026-05-15** at `354b6c0` (integration merge of `phase12-bundle-C-A-foundation` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `56e6993` (16 commits = 9 task-impl (T-A.1..T-A.8 + T-A.7 cross-bundle pin) + 4 Codex-fix (R1 + R2) + 2 docs + 1 return-report on top of dispatch brief `3cb334d`). Operator-dispatched implementer per orchestrator brief at `3cb334d`.

**2 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/2m → R2 0C/0M/2m); **ZERO Critical findings** entire chain; **1 ACCEPT-WITH-RATIONALE banked** (R1 Major #1 — backup-gate narrowness; matches Phase 9 Sub-bundle A precedent; documenting test + extended docstring). **Ties Phase 12 Sub-bundle A precedent for fastest Phase 12 chain.**

### Schema deltas (atomic v18→v19 migration at `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql`)

1. **NEW TABLE `reconciliation_corrections`** (20 columns; audit-history forensic trail). Preserves pre-correction journal value + Schwab-said value + applied correction + operator-truth value (if any) + lifecycle metadata + per-row policy stamp `risk_policy_id_at_correction` nullable + `ON DELETE SET NULL` per Phase 9 §3.1.1 trades.risk_policy_id_at_lock precedent. Self-reference chain via `superseded_by_correction_id` for override-of-override edge case.
2. **NEW COLUMN `reconciliation_discrepancies.ambiguity_kind`** (TEXT NULL CHECK enum) + cross-column CHECK with `resolution` enforcing tier-1 (NULL kind + auto_corrected_from_schwab resolution) vs tier-2 (non-NULL kind + pending_ambiguity_resolution OR operator_resolved_ambiguity) vs tier-3 (NULL kind + operator_overridden) invariants schema-defended.
3. **WIDENING `reconciliation_discrepancies.resolution`** CHECK enum 5 → 9 values via table-rebuild (`+ 'auto_corrected_from_schwab' / 'pending_ambiguity_resolution' / 'operator_resolved_ambiguity' / 'operator_overridden'`; PRAGMA foreign_keys=OFF during rebuild per Phase 7 hotfix `283d4fa` discipline; preserves all 30+ existing rows).
4. **NEW COLUMN `review_log.superseded_by_correction_id`** (INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL). Phase 6 freezing audit per spec §9.1 RETAIN-and-mark-superseded.
5. **WIDENING `trade_events.event_type`** CHECK enum + `'reconciliation_auto_correct'` via table-rebuild.
6. **NEW COLUMN `schwab_api_calls.linked_correction_id`** (INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL). Bidirectional provenance chase with `reconciliation_corrections` per Phase 11 source-artifact reference shape gotcha.

### Operator-witnessed gate (2026-05-15 post-merge-prep; orchestrator-driven; SKIPPED-with-test-coverage per polish-bundle-2026-05-10 precedent)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 3966 fast pass on main HEAD post-merge + 3 pre-existing failures (3 phase8 walkthrough; the 4th sentinel-leak failure at `test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` no longer surfacing post-merge — flaky pre-existing per writing-plans return report §7 #2) + 3 skipped (flag-classifier + C.A cross-bundle pin + 1 other) |
| S2 db-migrate fresh DB | ✅ SKIPPED-with-test-coverage | Inline migration runner tests cover fresh-DB migration end-to-end; no new discovery via standalone CLI run |
| S3 db-migrate production-snapshot | ✅ SKIPPED-with-test-coverage | T-A.8 slow-marked `test_migration_0019_against_production_snapshot.py` already exercised against operator's real v18 DB (full run_migrations flow including backup-gate fire); dynamic snapshot equality preserved all 30+ existing rows |
| S4 ruff baseline | ✅ | 18 E501 unchanged |

### NEW V2.1 §VII.F amendment candidates banked (per return report)

1. **Spec §3.1 column-count header drift (§I.16):** header text says "Column count: 19 columns" but table-row enumeration is 20 (correction_id through notes). Plan T-A.1 LOCKED 20-column count from the table verbatim.
2. **Plan §A.12 Phase 11 backup-gate precedent claim:** writing-plans plan referenced a Phase 11 backup-gate that does NOT exist (Codex R1 Major #1 surfaced); the actual backup-gate precedent is Phase 9 Sub-bundle A. Plan §A.12 wording amendment candidate.
3. **Plan §B.4 SHA256 byte-equality impossibility with SQLite Connection.backup:** plan §B.4 proposed SHA256 byte-equality verification but SQLite's `Connection.backup()` API doesn't preserve bytewise SHA256 (Codex R2 Minor #1 correction at `0e26d2b`).
4. **Dispatch brief §0.5 pre_version <= 18 vs == 18 equality form:** orchestrator brief §0.5 used `pre_version <= 18` but Phase 9 precedent uses `pre_version == (target - 1)` strict equality.
5. **Plan §B.2 _RESOLUTION_VALUES widening fold-into T-A.2:** plan §B.2 proposed widening the Python `_RESOLUTION_VALUES` constant in a separate task; should have folded into T-A.2 dataclass task for atomic consistency.

### Three highest-leverage SHIPPED deliverables

1. **Schema v19 foundation** — 5 schema deltas under one atomic `BEGIN IMMEDIATE; ... COMMIT;` envelope; new audit-history table + 4 column extensions + 2 CHECK enum widenings via table-rebuild; backup-gate fires correctly at `pre_version == 18 AND post_version >= 19` boundary; 30+ existing rows preserved; `EXPECTED_SCHEMA_VERSION = 19` bumped same commit.
2. **Cross-column CHECK schema-defended** — tier-1 / tier-2 / tier-3 invariants between `(ambiguity_kind, resolution)` enforced at schema CHECK time; app-layer enforcement in C.C service-layer is the secondary defense.
3. **ZERO behavioral changes to existing surfaces** — C.A is consumer-side passive. Existing 30+ discrepancies + fills + trades + review_log + schwab_api_calls all preserved unchanged. New schema sits idle until C.B/C.C/C.D consumers ship.

### Forward-binding lessons for C.B dispatch (per return report §11)

1. Schema-CHECK + Python-validator paired work (any new column with CHECK enum at schema time + Python constant + validator in dataclass MUST land in same task for atomic consistency).
2. Cross-column CHECK precedence at schema vs app layer (schema CHECK is defense-in-depth; app-layer enforcement in service-time is primary path).
3. Backup-gate equality form (`pre_version == (target - 1)` strict equality NOT `pre_version <= (target - 1)`).
4. UPDATE-self-reference anchor (`correction_set_id` two-step pattern at T-A.3 + T-C.3.4).
5. 20-column LOCK on `reconciliation_corrections` (spec drift §I.16 documented).
6. Lifecycle invariants as C.C service-layer concern (NOT C.B classifier; classifier produces ClassificationResult; service-layer enforces invariants).
7. Plan-author schema additions escalation (matches NEW orchestrator-context lesson at `657b8a0`; if C.B implementer encounters need for schema element NOT in plan + spec, STOP + escalate; do NOT bank-after-write).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) is currently at ~5-6 days remaining (expires 2026-05-22). C.B dispatch likely consumes 2-3 days; C.C 3-5 days; C.D 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md` (`3cb334d`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans).
- Return report: `docs/phase12-bundle-C-A-return-report.md` (`56e6993`).
- Integration merge: `354b6c0`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.B (Classifier + validator-shim modules) UNBLOCKED.** Per plan §C decomposition: 14 tasks (T-B.1..T-B.14); +55-95 fast tests projected; classifier consumes the C.A schema; validator-shim mirrors Phase 7 fills schema invariants as importable Python predicates (per spec §5.5 LOCK + §14.OQ-14). Un-skips 2 cross-bundle pin tests at C.B T-B.1 + T-B.2. Pure logic; no journal mutations. **Recommended timing: dispatched by new-orchestrator post-handoff** per operator's session-context-budget-management decision 2026-05-15.

---

## 2026-05-15 Phase 12 Sub-bundle B SHIPPED — Schwab web-UI-friendliness mini-bundle (credentials-in-file + web OAuth paste-back form; Outcome B manual token exchange; 4 Codex rounds NO_NEW_CRITICAL_MAJOR; 16 commits + 1 orchestrator-inline gate-fix; SECOND Phase 12 sub-bundle)

**Sub-bundle B SHIPPED 2026-05-15** at `b09eb06` (integration merge of `phase12-bundle-B-schwab-web-ui-friendliness` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `7b75d4a` (16 implementer commits + 1 orchestrator-inline gate-fix on top of dispatch brief). Operator-dispatched implementer per orchestrator brief at `fc86b8e`.

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/5M/3m → R2 0C/1M/2m → R3 0C/1M/1m → R4 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE on Critical+Major banked** (all 1 Critical + 7 Major resolved with code-content fixes); **+1 orchestrator-inline gate-fix at `7b75d4a`** (operator-paired gate caught a UX gap — `/schwab/setup` was reachable only by typing the URL; orchestrator added "External integrations" section on `/config` page with link to `/schwab/setup` + 1 regression test; mirrors 12A `e2c0384` + 11B `34be84e` precedent — **now 3 inline gate-fix instances cumulatively**).

**The two preceding 2026-05-15 phase3e-todo entries are NOW FULFILLED by this dispatch:** "Web-UI OAuth paste-back form" → T-B.4 `GET/POST /schwab/setup` Outcome B; "Schwab CLIENT_ID + CLIENT_SECRET in user-config.toml" → T-B.1 (cascade) + T-B.2 (cfg dataclass + FIELD_REGISTRY) + T-B.3 (CLI). Both entries are retained below for one-phase-cooldown per orchestrator-context.md retention discipline; will migrate to archive at next Sub-bundle ship.

### Operator-paired gate (2026-05-15 post-merge-prep; orchestrator-driven)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 3862 fast pass on main HEAD post-merge + 4 pre-existing failures (3 phase8 walkthrough + 1 schwab_setup_cli sentinel — return report §7 #2 banked separately) + 1 skipped |
| S2 `swing config set integrations.schwab.client_id\|client_secret` | ✅ | Operator's REAL Developer Portal credentials written to user-config.toml; `swing config show` renders masked `6m6***l7` / `2jp***T5` with `source=override` badge |
| S3 cascade resolution (env vars cleared) | ✅ | `swing schwab status --environment production` renders LIVE with NO prompt fired — cfg-tier resolves end-to-end through `apply_overrides` at status callsite (closes Codex R1 Critical fix `e418d56`'s post-conditions) |
| S4 web GET /schwab/setup | ✅ | Worktree-side `swing web --port 8081`; form renders 4 elements (authorize URL link + callback URL paste input + submit button + existing-tokens-DB advisory) + zero console errors |
| S5 web POST /schwab/setup (destructive) | ✅ | Outcome B manual token exchange — operator pastes Schwab callback URL → handler extracts `code` via raw-`&`-split → POSTs to `/v1/oauth/token` → tokens DB rewritten atomically via T-A.2 self-healing rename to `*.deleted-20260515T170457` → HX-Redirect to `/config?schwab_setup=ok` → fresh 7-day refresh-token clock starting 2026-05-15T17:05:00+00:00 (expires 2026-05-22T17:05:00+00:00) + 3 new audit rows (call_id=39 `oauth.code_exchange` self-healing rename http=— + call_id=40 `oauth.code_exchange` actual exchange http=200 + call_id=41 `accounts.linked` http=200) |
| Gate-caught UX gap | ✅ resolved inline at `7b75d4a` | Operator surfaced "no link to navigate to `/schwab/setup`"; orchestrator-inline gate-fix added link on `/config` + regression test |
| S7 ruff baseline | ✅ | 18 E501 unchanged |
| S8 + S9 sentinel-leak + masked rendering | ✅ via S1 pytest | Both covered by T-B.6 + T-B.2 + T-B.3 tests in the fast suite |

### Three highest-leverage SHIPPED deliverables

1. **Credentials-in-file cfg-cascade** — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` join the cfg-cascade as middle tier between env vars and prompt. Persistent across shells; mirrors Finviz token precedent. Asymmetry locked: partial env-tier RAISES (Sub-bundle A LOCK preserved — operator-typo signal); partial cfg-tier FALLS THROUGH (file-tier is operator-friendly per phase3e-todo "Cascade design" intent). Forward-binding lesson #1 for Sub-bundle C.
2. **Web `GET/POST /schwab/setup`** — Outcome B locked (manual token exchange since schwabdev's `Client.__init__` blocks on stdin paste-back). New `setup_paste_flow_with_callback_url` service helper mirrors schwabdev's `Tokens._post_oauth_token` HTTP shape + `Tokens._set_tokens` JSON file format byte-for-byte. HTMX patterns preserved (HX-Request propagation + HX-Redirect success + route-table assertion). Eliminates PowerShell drop-out for weekly Schwab OAuth re-auth.
3. **Orchestrator-inline gate-fix precedent extension to 3 instances** — `/schwab/setup` nav link on `/config` page closes operator-surfaced UX gap; the brief's mandated T-B.4 route-level integration test caught Sub-bundle A T-A.3 implementer-gap-class defects pre-emptively (Codex R1 Critical `apply_overrides` missing at 5 entry points resolved at `e418d56`).

### NEW V2 candidates banked

1. **T-B.7 `/schwab/status` web counterpart** — deferred per Outcome B decision rule. When this ships in a follow-up dispatch, the T-B.4 HX-Redirect target retargets from `/config?schwab_setup=ok` to `/schwab/status`.
2. **`surface='web'` CHECK enum widening** — schema v18 → v19 migration. Resolves T-B.4 audit-row ambiguity (currently `surface='cli'` for web audit rows per v18 CHECK constraint). V2.1 §VII.F amendment candidate.
3. **Option B HTTPS callback handler** — eliminates paste-back entirely. Substantial complexity: local self-signed HTTPS cert, browser security warning, Schwab Developer Portal callback URL reconfiguration. Separate dispatch.
4. **Per-environment-namespaced credentials** — separate `[integrations.schwab.sandbox]` / `[integrations.schwab.production]` tables. V2 candidate.
5. **Web multi-account picker** — V1 raises `SchwabConfigMissingError` for multi-account on web; V2 adds picker UI.
6. **Token encryption-at-rest** — schwabdev's optional `encryption=<key>` Fernet wrapper. Q2 from Phase 11 brainstorm. Operator-paired key management.
7. **Promote `masked_writeable` to `FieldSpec` attribute** — replace `_MASKED_WRITEABLE_PATHS` frozenset allowlist with per-FieldSpec attribute when the catalog grows beyond 2-3 entries. T-B.3 forward-binding lesson #4.
8. **`/config?schwab_setup=ok` query-param consumer** — currently dead query param; future enhancement could surface "Schwab setup successful" toast on `/config` page.
9. **schwabdev version pin + extended compat test** — Outcome B mirrors schwabdev's private API byte-for-byte; defensive `schwabdev==2.5.1` pin in pyproject.toml + extended regression test that constructs a real `schwabdev.Client` (not just `Tokens`) against the written file.
10. **T-B.2 stale-comment cleanup** at `swing/config_validation.py:91-93` + `swing/config_overrides.py:25-26` — comments saying client_id/client_secret are "NOT editable via `swing config set`" are now factually incorrect post-T-B.3. Banked here for next polish-bundle dispatch.

### 12 forward-binding lessons for Sub-bundle C dispatch (return report §10)

1. Three-tier credential cascade asymmetry pattern (env partial RAISES; cfg partial FALLS THROUGH)
2. Outcome A vs B SDK-wrapping recipe — manual token-exchange byte-for-byte mirror + atomic tokens-file write + SDK construction reads back
3. `surface='X'` CHECK constraint workaround pattern — when enum widens at v_N but schema migrations out-of-scope, document deviation in code comment + bank V2.1 §VII.F amendment
4. `_MASKED_WRITEABLE_PATHS` allowlist + `_FIELD_PATHS` filter pattern (canonical way to gate masked CLI fields)
5. N-part dotted-path generalization at write/read/delete (all 3 call sites touch together: `config_user.py:delete_user_override` + `cli_config.py:_write_override_nested` + `config_overrides.py:get_field_source`)
6. **`apply_overrides()` discipline at Schwab entry points** — Codex R1 Critical surfaced — project-wide invariant candidate: consider moving `apply_overrides` into `load_config` itself OR into the FastAPI lifespan hook
7. `parse_qs` vs `unquote` for OAuth code parsing — `parse_qs` applies `application/x-www-form-urlencoded` semantics; OAuth codes are opaque; use raw query-string split + `urllib.parse.unquote` (NOT `unquote_plus` or `parse_qs`)
8. Atomic file-write fsync discipline — match `swing/config_user.py:write_user_overrides` pattern (tempfile same-dir → write → flush → fsync → os.replace → best-effort parent-dir fsync)
9. Real-SDK compat regression test pattern — when mirroring an external SDK's private API byte-for-byte, the regression test MUST invoke the real SDK's loader
10. Cross-bundle base-layout VM pin discipline — every new VM extending `base.html.j2` MUST populate `unresolved_material_discrepancies_count` (Phase 10 T-E.3 pin)
11. HTMX gotcha trinity preserved for any new form-driven route (HX-Request propagation + 204+HX-Redirect + HX-Redirect target route exists)
12. Sub-bundle A T-A.3 implementer gap pre-emption discipline — for any new entry point that threads credentials through multiple call sites, the route-level integration test MUST mock the service function + assert the EXACT cascade-resolved credential values were threaded through

### Cross-references

- Dispatch brief: `docs/phase12-bundle-B-schwab-web-ui-friendliness-executing-plans-dispatch-brief.md` (`fc86b8e`).
- Return report: `docs/phase12-bundle-B-return-report.md` (on main post-merge).
- Orchestrator-inline gate-fix: `7b75d4a` (on worktree branch + merged via `--no-ff`).
- Integration merge: `b09eb06`.

### Next dispatch

**Phase 12 Sub-bundle C (auto-correct journal-from-Schwab service) UNBLOCKED.** Per the architectural pivot banked at `28a7d01` + `75b876c`. Substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected. Operator-paced. Three-tier resolution model (auto-correct unambiguous + ambiguity surfaced + operator override); magnitude is the WRONG axis (determinism is the axis); closes the 3 unresolved-material discrepancies (39 DHC + 40 VSAT + 41 CVGI) + future categorical fiction-vs-truth divergences.

---

## 2026-05-15 Web-UI OAuth paste-back form (`GET/POST /schwab/setup`) — operator-stated UX gap; bundle with credentials-in-file as Phase 12 Sub-bundle B

**Operator UX gap (2026-05-15 during Phase 12 Sub-bundle A close discussion):** `swing schwab setup` is CLI-only. Operator's normal mode is the web interface (`swing web` on 127.0.0.1:8080). Weekly OAuth re-auth currently forces operator to drop to a separate PowerShell session for the paste-back flow. No web-side equivalent exists.

**Proposed Option A (simpler; recommended for V1):** new web route `GET /schwab/setup` renders a simple form:
- Step 1: pre-populated clickable link to the Schwab authorize URL (opens in new tab via `target="_blank"`).
- Step 2: text input for "paste your callback URL here".
- Step 3: submit button.

`POST /schwab/setup` handler runs the same `setup_paste_flow` service-layer function from Sub-bundle A T-A.4 (NOT a re-implementation). T-A.2 self-healing (auto-rename stale tokens DB before invoking schwabdev) applies identically. Operator interaction: navigate to `/schwab/setup` → click authorize link (new tab) → complete OAuth → copy callback URL from address bar → paste into form on original tab → submit. Same number of paste actions as CLI flow but stays inside web UI context — operator never leaves browser.

Web-form must use HTMX patterns per Phase 5+ HTMX failure-surface gotchas: embedded form `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode propagation; success-path `204 No Content` + `HX-Redirect: /schwab/status` (NOT 303 swap-target); HX-Redirect target route must exist (verify via TestClient route-table assertion). Server-stamping discipline applies (operator-supplied = the callback URL; everything else server-stamped).

**Option B (V2 candidate; eliminates paste-back entirely):** local HTTPS callback handler at e.g. `https://127.0.0.1:8443/schwab/oauth/callback`. Browser hits handler directly after Schwab redirects; server extracts `code` from URL params; completes exchange automatically. Pros: zero paste-back. Cons: requires local self-signed HTTPS cert (browser security warning; operator must accept cert), separate HTTPS port listener, Schwab Developer Portal app callback URL must be reconfigured. Substantial complexity for the UX win — banked V2 candidate.

### Bundle with credentials-in-file (preceding phase3e-todo entry) as Phase 12 Sub-bundle B

Both target the same operator pain — "make Schwab setup work without dropping to PowerShell":
- **Credentials-in-file** (`user-config.toml` cascade): CLI + web both read app credentials from one place; no per-shell env vars.
- **Web OAuth setup form** (`GET/POST /schwab/setup`): operator never leaves browser for weekly re-auth.

Bundled scope: ~12-18 fast tests; 2-3 Codex rounds; 1-2 days. Shared infrastructure (`construct_authenticated_client` cascade for credentials; `setup_paste_flow` for OAuth) makes bundling efficient. Combined dispatch as "Phase 12 Sub-bundle B — Schwab web-UI-friendliness mini-bundle."

### Architectural changes required (web-form portion)

1. **New route at `swing/web/routes/schwab.py`** (or co-located in existing routes module). `GET /schwab/setup` renders the form template; `POST /schwab/setup` runs `setup_paste_flow(cfg, environment, client_id, client_secret, callback_url=<operator-pasted>)`. Credentials sourced from the cascade (env vars > user-config.toml > prompt — except prompt path is N/A in web context; if neither env vars nor file values present, render an error pointing operator at `/config` or `swing config set`).
2. **New template at `swing/web/templates/schwab_setup.html.j2`** following base.html.j2 extension pattern (must add any new VM fields to ALL base-layout VMs per CLAUDE.md gotcha).
3. **New view model `SchwabSetupVM`** with the standard base-layout fields + setup-specific fields (authorize URL, optional success/error message, optional pre-existing-tokens-DB warning).
4. **CycleChecklist update** to reference the web URL (`http://127.0.0.1:8080/schwab/setup`) as the primary weekly re-auth path; CLI command remains as fallback.
5. **`swing schwab status` web counterpart at `GET /schwab/status`** — V2 candidate (smaller; not load-bearing for OAuth flow); could ship in same Sub-bundle B if operator wants the status surface in the web UI too.
6. **CLAUDE.md gotcha addition** — "Schwab OAuth web setup flow" documents Option A's HTMX requirements (embedded form HX-Request propagation; HX-Redirect success path; T-A.2 self-healing applies identically; route table must include `/schwab/setup` GET + POST).

### Sequencing within Sub-bundle B

If bundled with credentials-in-file:
- Task 1: credentials-in-file cascade extension (T-A.1 helper extends; SchwabConfig dataclass extends).
- Task 2: `swing config set integrations.schwab.client_id` + `client_secret` cascade emitter wires.
- Task 3: web `GET/POST /schwab/setup` form + POST handler integration.
- Task 4: cycle-checklist + CLAUDE.md updates.
- Task 5: optional `GET /schwab/status` web counterpart.
- Task 6: end-to-end happy-path integration test.

### Cross-references

- Sub-bundle A T-A.4 setup_paste_flow CLI implementation: `swing/integrations/schwab/auth.py:setup_paste_flow`.
- Sub-bundle A T-A.2 self-healing logic (applies identically to web POST): same file.
- Phase 5 HTMX failure-surface gotchas: CLAUDE.md HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted gotchas.
- Phase 8 server-stamping discipline gotcha (relevant to web POST: operator-supplied = callback URL only; everything else server-stamped).

---

## 2026-05-15 Schwab CLIENT_ID + CLIENT_SECRET in user-config.toml (Finviz precedent; operator-stated UX gap during Phase 12 Sub-bundle A S6 gate)

**Operator UX clarification (2026-05-15):** Phase 12 Sub-bundle A T-A.1 env-var path is "better than copying and pasting" but not great from a user perspective:
- Each shell session needs `$env:SCHWAB_CLIENT_ID` + `$env:SCHWAB_CLIENT_SECRET` set (PowerShell shell for CLI; separate shell for `swing web`; etc.). Operator could set in PowerShell profile but that's per-shell-application.
- Operator initially worried about weekly reset — **clarification: app credentials (CLIENT_ID + CLIENT_SECRET) are STABLE from Schwab Developer Portal app registration; do NOT weekly-rotate.** What rotates weekly is the OAuth refresh_token (managed by schwabdev's tokens DB; rotated via paste-back; separate concern). So env vars only need to be set ONCE per Schwab Developer Portal credential rotation (rare — only when operator regenerates app credentials from the portal).

**Operator's intended UX:** file-based credential storage in `~/swing-data/user-config.toml` under `[integrations.schwab]` (mirrors Finviz precedent — Finviz token already lives here under `[integrations.finviz]`; per CLAUDE.md gotcha "Finviz Elite API token storage": user-config.toml is `%USERPROFILE%/swing-data/user-config.toml` — operator's home dir, NOT in repo, NOT git-tracked, per-machine, plaintext). Operator edits ONCE per app credential rotation; every shell automatically picks up the same values; no per-shell setup required.

### Cascade design

Three-tier credential resolution (extend the T-A.1 helper):
1. **Env vars** (highest priority) — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`. Useful for: scripted ops; CI/CD; per-invocation override of file-stored values; security-conscious operators who don't want plaintext on disk.
2. **`user-config.toml` `[integrations.schwab].client_id` + `.client_secret`** (middle priority) — file-stored; persists across shells + reboots; operator edits once per credential rotation. The DEFAULT operator path.
3. **Interactive prompt** (lowest priority; fallback) — current Sub-bundle A T-A.2 behavior preserved when neither env vars nor file values present. Useful for: first-run operators; one-off CLI invocations on a fresh machine.

`construct_authenticated_client(cfg, environment)` consults in this order; first non-empty pair wins. Both-or-neither at each tier (partial → next tier) — UNLIKE T-A.1 partial-rejects-with-error, since file-tier may have CLIENT_ID set without CLIENT_SECRET (rare but valid as the operator may want to fall through to env vars or prompt for the secret).

### Architectural changes required

1. **Extend `SchwabConfig` dataclass** (`swing/config.py`) with `client_id: str | None = None` + `client_secret: str | None = None` fields. ADD to `FIELD_REGISTRY` with `masked=True` (first-3 + *** + last-2 per existing FIELD_REGISTRY pattern). `swing config show` displays masked values.
2. **Extend `resolve_credentials_env_or_prompt`** (T-A.1 helper at `swing/integrations/schwab/auth.py`) with the three-tier cascade. Currently env-var-or-prompt; becomes env-var-or-cfg-or-prompt.
3. **`swing config set integrations.schwab.client_id <value>`** + `client_secret <value>` paths via existing `swing config set` cascade emitter. Mirrors existing finviz token-set path.
4. **CLAUDE.md gotcha addition** — "Schwab CLIENT_ID + CLIENT_SECRET storage" mirrors existing "Finviz Elite API token storage" entry. Tracked `swing.config.toml` MUST NOT contain the values (sensitive); only `~/swing-data/user-config.toml`. `.gitignore` patterns for `user-config.toml*` should already cover (verify).
5. **Sentinel-leak audit extension** — env-var sentinel-leak coverage exists post-Sub-bundle-A; extend to cfg-cascade-sourced credentials so Layer 0 redactor's known-secret registry picks them up at SchwabClient construction time.
6. **Backwards-compat** — operators relying on env vars continue to work unchanged (env vars are highest-priority tier).

### Sequencing — could ship BEFORE Sub-bundle B (auto-correct service)

This is a small Tier 1.5 polish dispatch (smaller than Sub-bundle B's architectural pivot). ~6-10 fast tests; 1-2 Codex rounds; 1 day. Could ship as Phase 12 Sub-bundle B (re-scoped) OR as a fast-follow before the auto-correct service work.

### Cross-references

- Finviz precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` + CLAUDE.md "Finviz Elite API token storage" gotcha.
- Sub-bundle A T-A.1 implementation: `swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt`.
- Sub-bundle A T-A.2 design rationale (credentials NOT in cfg cascade): security posture per dispatch brief; this entry SUPERSEDES with a more nuanced cascade design.

---

## 2026-05-15 ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab, not surface for operator-triage (Phase 12 Sub-bundle B headline candidate)

**Surfaced (operator-stated 2026-05-15 during Phase 12 Sub-bundle A S5 gate):** the current Phase 9 + Phase 11 reconciliation model surfaces journal-vs-Schwab discrepancies for operator-triage with resolutions of `acknowledged_immaterial` / `journal_corrected` / `mistake_corrected`. Operator pushed back: when Schwab data is available, **Schwab IS truth — there is no "immaterial" price magnitude**. Operator-action loop is the wrong design. The fact that 3 discrepancies re-emerged on pipeline #63 after operator "resolved" 7 of 8 yesterday demonstrates this concretely: yesterday's resolutions only marked OLD discrepancy ROWS as resolved; they did NOT update the underlying fills. Each fresh `reconciliation_run` re-detects the same mismatches because journal data still diverges from Schwab.

**Operator's intended model — three-tier resolution (operator clarification 2026-05-15):**

1. **Unambiguous auto-correct (the common case):** reconciliation detects a journal-vs-Schwab mismatch where the correction is deterministic — single Schwab record maps to single journal fill, single field differs, clear "set journal field to Schwab value." System auto-corrects journal to match Schwab + writes audit row capturing pre/post values. No operator involvement needed. Example: CVGI disc 41 (journal $5.23 vs Schwab $5.30 on a single matching fill) — system can unambiguously resolve.

2. **Ambiguity surfaced for operator decision (operationally important — second most common):** system detects mismatch but cannot deterministically decide the correction. Examples:
   - Schwab shows multiple partial fills (e.g., DHC entry as 20+19 partials at slightly different prices) + journal has single consolidated entry — system cannot decide whether to (a) split journal into matching partials, (b) keep journal consolidated + use Schwab's volume-weighted avg price, (c) pick a representative fill, (d) something operator-specific.
   - Multiple Schwab transactions could match the same journal fill within a window — which is the "right" match?
   - Schwab data shape doesn't fit existing journal schema (e.g., new transaction subtype not in CHECK enum).
   - Data shape transformation requires operator judgment (intraday timestamps preserved vs rolled to EOD; fee allocation across split fills).
   
   Surfaced to operator with **clear message: what the discrepancy is + what the ambiguity is + what the resolution choices are**. Operator picks (or provides custom). System then auto-applies the chosen resolution + audits.

3. **Operator overrides an auto-correction (the rare edge case):** operator has ground-truth knowledge that Schwab itself is wrong (known broker error; reporting glitch; operator caught it before it propagated). Operator marks an applied correction as `operator_overridden` + provides ground-truth value + reason. Audit chain preserves all three values: pre-correction journal / Schwab-said / operator-override.

The current Phase 9 + 11 model collapses tiers (1) + (2) into a single "operator triages everything" loop, which is the wrong default. The new architecture must distinguish: **deterministic correction → auto-apply silently** vs **ambiguous case → surface with clear choices** vs **rare override case → preserve all three values in audit**.

### Concrete current-state evidence

Discrepancies 39/40/41 from pipeline #63 (run_id=10) are LITERALLY IDENTICAL to siblings 32/36/37/34/38 from runs 8+9 (same fill_id, same expected_value_json, same actual_value_json):

- **disc 41 CVGI entry_price_mismatch:** journal `fills.fill_id=9` price=$5.23, Schwab=$5.30, **delta $+0.07** (yesterday's resolution claimed "~$0.01 off" — wrong magnitude AND no actual correction made).
- **disc 39 DHC unmatched_open_fill:** journal `fills.fill_id=2` entry @$7.58 × 39 on 2026-04-27, Schwab `actual={"matched": null}` (likely Schwab split entry into multiple partial fills with different timestamps/prices; operator's single-row journal entry can't match).
- **disc 40 VSAT unmatched_open_fill:** journal `fills.fill_id=6` entry @$65.69 × 2 on 2026-05-06, `manual_entry_confidence='low'` (operator flagged as uncertain at entry time!), Schwab `actual={"matched": null}`.

**All three fills carry `reconciliation_status='unreconciled'` + `tos_match_id=NULL`** — they were operator-typed-from-memory and never linked to a Schwab/TOS source record at entry time. Reconciliation correctly identifies them as fiction-vs-truth divergences.

### Architectural changes required

1. **New ambiguity classifier** at the reconciliation layer. For every detected mismatch, classify as:
   - `auto_correctable` — single journal fill + single Schwab record + single field differs + clear target value → tier 1 auto-apply.
   - `ambiguous` — multiple-to-one mapping, shape mismatch, missing-field-on-one-side, schema-doesn't-fit, or any case where multiple deterministic resolutions exist → tier 2 surface for operator. Classifier MUST emit a structured `ambiguity_kind` enum (e.g., `multi_partial_vs_consolidated`, `multi_match_within_window`, `unknown_schwab_subtype`, `field_shape_incompatible`, `schwab_returned_no_match`) so the operator-facing UI can render type-specific resolution choices.
   - `unsupported` — system genuinely cannot reason about the mismatch (e.g., new Schwab API field shape; cassette-fixture-only edge case) → tier 2 with explicit "system needs code update; please report" message.
2. **New service-layer auto-correction module** at `swing/trades/reconciliation_auto_correct.py` (or similar). Transactional (BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject caller-held tx per Phase 8 lesson family). Validator-respecting (Phase 7 fills validators; Phase 9 risk_policy). Audit-aware. Handles tier-1 auto-correctable cases only; tier-2 cases get queued for operator decision (do NOT auto-apply ambiguous cases).
3. **New audit-history table** OR extension of `event_log` to preserve pre-correction journal values (forensic trail; "what did the operator originally enter; what did Schwab show; what action was taken; when").
4. **Tier-2 ambiguity-resolution UI/CLI** — operator-facing surface that renders the discrepancy + ambiguity_kind + resolution choices specific to the kind. E.g., `multi_partial_vs_consolidated` choices: (a) split journal into matching partials; (b) keep consolidated + use Schwab volume-weighted avg price; (c) keep journal as-is + mark schwab_partial_fill_aggregation_acknowledged; (d) operator-custom value. Each choice maps to a deterministic action; operator pick → service auto-applies + audits.
5. **Reconciliation flow pivot:** discrepancy emission becomes a multi-tier dispatch — tier-1 cases auto-apply silently; tier-2 cases surface for operator decision; tier-3 (operator override of an applied tier-1 correction) is a separate post-hoc UI surface. Discrepancy table semantics shift: rows represent classification + (for tier-2) pending operator decision OR (for tier-1+tier-3) audit history.
6. **`fills.reconciliation_status` enum change:** `unreconciled` → `auto_matched` / `auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`. `tos_match_id` populated for auto-matched + auto-corrected + operator-resolved.
7. **No magnitude-based auto-vs-surface threshold** — magnitude is the WRONG axis (operator clarification: $0.07 isn't "small"; the question is whether the correction is deterministic, not whether the delta is big). Ambiguity classifier replaces threshold gates.
8. **Backfill path** for existing unresolved-material discrepancies (39/40/41 + any future): when the auto-correction service ships, run the classifier across all currently-unresolved discrepancies. Tier-1 cases auto-apply + audit. Tier-2 cases get queued for operator decision via the new UI.
9. **Fill auto-population at trade-entry time** (the unstated V2 candidate): create fills directly from Schwab Trader API responses at trade-entry handler time instead of operator-typing-from-memory. Closes the entire discrepancy stream as a CATEGORY (not just one-at-a-time). Fills get `tos_match_id` populated from start; no future fiction-vs-truth divergence possible. Probably a separate sub-bundle (Sub-bundle B vs Sub-bundle C decision; brainstorm should determine ordering).

### Per-discrepancy classification of the current 3 unresolved (illustrative — informs the new architecture's expected workload)

- **disc 41 CVGI entry_price_mismatch** → likely **`auto_correctable` (tier 1)**: single journal fill `fill_id=9` matches single Schwab transaction by date+ticker+qty; only `price` field differs ($5.23 vs $5.30). System sets journal price to $5.30 + writes audit row + done. No operator involvement.
- **disc 39 DHC unmatched_open_fill** → likely **`ambiguous` (tier 2)** with `ambiguity_kind=multi_partial_vs_consolidated`: journal has single fill `qty=39 @ $7.58`; Schwab almost certainly has partial fills (e.g., 20 + 19 at slightly different prices). Operator picks split-into-partials vs keep-consolidated + average + audit.
- **disc 40 VSAT unmatched_open_fill** → either `ambiguous` (`multi_partial_vs_consolidated` if Schwab split entry) OR `auto_correctable` (if Schwab has single fill at slightly different price/qty). Classifier determines which on a per-row basis.

### What this is NOT

- NOT a polish/observability bundle (those were the Tier 2 items I originally outlined).
- NOT a Sub-bundle A scope expansion (Sub-bundle A's env-var + setup-self-healing + pipeline-env-var changes are still independently valuable; merge as planned).
- NOT a quick fix (touches reconciliation core + introduces new audit semantics + requires careful migration of existing data; substantial brainstorm + writing-plans + multi-bundle executing-plans cycle).

### Recommended sequence

1. **Finish Sub-bundle A gate (S6 + S7) + merge** — Tier 1 ops-pain fixes ship as scoped.
2. **Leave the 3 current unresolved-material discrepancies (39/40/41) alone for now.** They're correct signal; operator-action would just mark-as-resolved without fixing the underlying fiction-vs-truth divergence. Phase 10 dashboard banner shows "3 unresolved" until auto-correction ships — that's accurate state.
3. **Phase 12 Sub-bundle B = brainstorm + writing-plans + executing-plans for the auto-correction pivot.** Operator-paced; substantial dispatch.

### Cross-references

- Phase 9 Sub-bundle B reconciliation_run shape: `swing/trades/reconciliation.py` (`run_tos_reconciliation` mirror used by `run_schwab_reconciliation`).
- Phase 11 Sub-bundle B `swing_schwab_reconciliation` service.
- Phase 8 transactional-discipline pattern (caller-rejection + BEGIN IMMEDIATE) for the new auto-correction service.
- Phase 7 single-write-path discipline + audit-trail patterns.
- Phase 10 Sub-bundle E §A.18 dashboard banner consumer (continues to read `count(unresolved-material)` predicate; semantics shift when that count drops to ~0 once auto-correction is the norm).

---

## 2026-05-15 `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex too narrow — `phase\d+-*` doesn't match `schwab-bundle-*`

**Symptom (operator-surfaced 2026-05-15 during Sub-bundle D post-merge cleanup):** the cleanup script's `-DeregisterFirst` safety filter regex `phase\d+-*` does NOT match the Schwab arc's worktree naming convention `schwab-bundle-*`. Result: all 4 Schwab worktrees were skipped during the deregister scan; operator + orchestrator had to manually invoke `git worktree remove --force` for each + then re-run the script to clean ACL-locked dirs.

**Root cause:** the script was authored at post-Phase-10 infrastructure bundle SHIPPED (commit `27ce96f`) when ALL prior worktree branches had `phase\d+-*` naming (phase8/phase9/phase10 bundles). The Schwab arc's `schwab-bundle-A/B/C/D-...` naming was the first deviation; the regex didn't follow.

**Fix candidate:** widen the safety filter regex to `(phase\d+|schwab(?:-\w+)?)-bundle-` OR introduce a configurable filter (e.g., `-BranchPattern` parameter; default `phase\d+-*` for backward compat). Operator-paced; bundle into the next polish dispatch OR address inline at next worktree-husk cleanup cycle.

**Defense-in-depth:** orchestrator briefs for future arc-style dispatches MUST either (a) use `phase{NN}-bundle-*` naming convention to match the existing regex, OR (b) explicitly thread the cleanup-script regex extension into the dispatch brief as a watch item.

**Cross-reference:** Phase 10 infrastructure bundle SHIPPED entry at `27ce96f` — the original `-DeregisterFirst` switch addition (Codex R1 Critical #1 confirm-before-deregister gate landed in that bundle).

---

## 2026-05-15 Pipeline run on empty finviz inbox should auto-trigger `_step_finviz_fetch` — **SHIPPED 2026-05-18 at `7a84942`** (3rd gate-blocker occurrence closed; 3 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; +6 fast tests; ruff/schema unchanged)

**SHIPPED 2026-05-18** at integration merge `7a84942` (branch `phase12-5-finviz-inbox-auto-fetch-fix`; 5 commits = 1 task-impl + 3 Codex-fix + 1 return-report). Fix at `swing/pipeline/runner.py:525-602` splits the combined catch — `NoFilesError` triggers ONE inline `_step_finviz_fetch` attempt + retry `select_csv`; `AmbiguousInboxError` stays fail-fast. Site 2 (line 638) gated on `not finviz_fetched_inline` to prevent double-fire (would persist 2 `finviz_api_calls` audit rows per run). 2 new private helpers: `_read_finviz_call_max_id_snapshot` (causal anchor) + `_read_latest_finviz_call_diagnostic` (scoped read of audit row inserted by THIS call). Combined error message now surfaces the real Finviz cause (missing token / auth / rate-limit / schema parity) instead of redundant "No CSV files" twice. Operator-witnessed 2-surface gate PASS: S1 4581 fast + ruff 18; S2 pipeline #67 complete from empty inbox in 45s (F5 audit-row contract verified — 1 finviz_api_calls row, no double-fire). 3 forward-binding lessons banked (audit-row contract tests require lower-level monkeypatch; `_read_latest_*` helpers in multi-surface code must scope by PK snapshot; USERPROFILE/HOME read-side pollution symmetric to existing write-side gotcha).

### Original entry (2026-05-15; pre-dispatch; superseded by SHIPPED outcome above)

**Symptom (operator-surfaced 2026-05-15 during Phase 12 Sub-bundle A S5 gate):** `swing pipeline run` against an empty `data/finviz-inbox/` (folder exists but contains no CSV — common in fresh worktrees per yesterday's #3 fix that auto-creates the dir but doesn't populate it) errors with `No CSV files in <dir>` + state=failed. Should instead invoke the Finviz Elite API fetch path (`_step_finviz_fetch` semantics) to auto-populate the inbox + then proceed.

**Root cause:** at `swing/pipeline/runner.py:run_pipeline_internal` L425+, `select_csv(cfg.paths.finviz_inbox_dir)` runs FIRST + raises `NoFilesError` on empty dir → pipeline fails. `_step_finviz_fetch` (which DOES auto-fetch via Finviz API) is registered as a pipeline step at L499, AFTER `select_csv` has already errored. The architectural intent appears to have been "pipeline reads existing CSV from prior `swing finviz fetch` invocation" — but on first-run empty-inbox state, there's no prior CSV.

**Fix candidate:** when `select_csv` raises `NoFilesError`, attempt a synchronous `_step_finviz_fetch` (or extracted core helper `_finviz_fetch_core(cfg)`) inline + retry `select_csv`. If the auto-fetch ALSO produces no CSV (Finviz API rate-limited, Finviz Elite credentials missing, etc.) → THEN fail with combined error message ("inbox empty + auto-fetch failed: <reason>"). Preserves the existing select-then-error path for AmbiguousInboxError; only the empty-inbox path is widened.

**Discriminating-test pattern:** plant empty inbox dir (after yesterday's #3 mkdir bootstrap fix) + monkeypatch `_finviz_fetch_core` to write a known CSV + invoke `run_pipeline_internal` + assert (a) auto-fetch fired, (b) CSV present in inbox post-call, (c) pipeline state != "failed" on the inbox-empty cause (may still fail later on yfinance / Schwab / etc. — that's fine; the empty-inbox cause is the specific axis under test).

**Defer-or-fix-soon disposition:** small-scope bug; bundle into next polish dispatch (could be next Phase 12 sub-bundle OR standalone). Operator-paced.

**Cross-references:**
- 2026-05-15 yesterday's missing-folder fix at commit `6ea94f7` (closed the missing-FOLDER case; this is the empty-FOLDER follow-up).
- `_step_finviz_fetch` definition at `swing/pipeline/runner.py:1956` + `_finviz_fetch_core` helper at L1791.
- `select_csv` at `swing/pipeline/finviz_select.py:50`.

---

## 2026-05-15 Pipeline run errors out on missing `data/finviz-inbox/` folder — **SHIPPED 2026-05-15 at `6ea94f7`** (missing-FOLDER case closed; companion empty-FOLDER case shipped 2026-05-18 at `7a84942` — see entry above)

**SHIPPED 2026-05-15** at commit `6ea94f7` (mkdir bootstrap in `_step_finviz_fetch` + mirrored in `run_pipeline_internal:510` per Codex R1 Major-2 fix family). Closed the missing-FOLDER case (`data/finviz-inbox/` directory absent). The companion empty-FOLDER case (`data/finviz-inbox/` exists but contains no CSV) shipped 2026-05-18 at `7a84942` (see entry above).

### Original entry (2026-05-15; pre-fix; superseded by SHIPPED outcome above)

**Symptom (operator-surfaced 2026-05-15 during Sub-bundle D operator-witnessed gate):** `swing pipeline run` errors out with "no csv found" when `data/finviz-inbox/` directory does not exist on the operator's filesystem.

**Expected behavior:** pipeline should check for folder existence first + create the folder via `os.makedirs(..., exist_ok=True)` if missing. The directory is operator-data convention (configured in `swing.config.toml`) — its absence is the natural first-run state, not an error condition.

**Likely fix location:** `swing/pipeline/runner.py:_step_finviz_fetch` (the step that consumes the inbox). Add `Path(cfg.paths.finviz_inbox_dir).mkdir(parents=True, exist_ok=True)` near the top of the step.

**Discriminating-test pattern:** delete `data/finviz-inbox/` (or use a tmp_path with the dir absent) + invoke pipeline run + assert directory was auto-created + step completed (or surfaced "no manual CSV; using API fallback" path correctly per existing `_step_finviz_fetch` semantics).

**Defer-or-fix-soon disposition:** trivial fix; bundle into a near-term polish dispatch OR address inline. NOT Schwab-arc-related; banked here for orchestrator triage.

---

## 2026-05-15 Phase 12 Sub-bundle A SHIPPED — Schwab API operational-pain mini-bundle (env vars + setup self-healing + pipeline env-var wiring + cleanup-script regex; 3 Codex rounds + 1 orchestrator-inline gate-fix; 12 commits; FIRST Phase 12 dispatch)

**Sub-bundle A SHIPPED 2026-05-15** at `123d27a` (integration merge of `phase12-bundle-A-schwab-operational-pain` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `e2c0384` (12 commits = 4 task-impl + 2 pre-Codex review fixes + 5 Codex-fix + 1 orchestrator-inline gate-fix on top of return report `2cbb8c4`). Operator-dispatched implementer per orchestrator brief at `892e3e3`.

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/2M → R2 0C/1M → R3 0C/0M); **ZERO ACCEPT-WITH-RATIONALE banked**; **+1 orchestrator-inline gate-fix at `e2c0384`** (closed T-A.3 acceptance #4 gap that operator-paired S5 surfaced — implementer's T-A.3 wired the env-var-constructed schwab_client into the market-data ladder hook but LEFT both `_step_schwab_snapshot` + `_step_schwab_orders` callsites with `client=None` HARDCODED; orchestrator-inline fix wired schwab_client through both callsites + added discriminating regression test).

**Why no brainstorm + no writing-plans:** Per operator scope decision 2026-05-15, V2 candidates from Phase 11 arc were well-defined; this bundle went straight to executing-plans dispatch as a focused operational-pain mini-bundle.

### Operator-paired live gate (Option A; 2026-05-15)

Full S2-S7 live verification against operator's production-tier Schwab account + worktree-side inline S1+S8+S9 PASS:

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite (worktree) | ✅ | 3786 → 3787 passed (post-orchestrator-inline gate-fix); 3 pre-existing phase8 failures unchanged |
| S2 status with env vars | ✅ | NO credential prompt (T-A.1); LIVE indicator + token TTL 6d 18h + recent calls (24-28); ZERO token bytes |
| S3 fetch --verify-marketdata with env vars | ✅ | NO prompt; calls 30 + 31 success against live Schwab Market Data API |
| S4 setup self-healing | ✅ | T-A.2 atomic rename of existing tokens DB to `*.deleted-20260515T095338` + audit row at call 32 + fresh paste-back; same hashValue=E8F...0676 auto-picked; **fresh 7-day clock started 2026-05-15T03:59:25 UTC** |
| S5 pipeline with env vars | ❌→✅ post-fix `e2c0384` | Initial pipeline #62 ran with ZERO new schwab_api_calls (T-A.3 implementer-side gap caught at gate). **Orchestrator-inline gate-fix** wired schwab_client through both Sub-bundle B step callsites + added regression test. Re-run pipeline #63 completed in 11s with 4 new schwab_api_calls (calls 35-38; surface=pipeline; endpoints accounts.details + accounts.orders.list + accounts.transactions.list) + new reconciliation_run #10 + 3 fresh discrepancies (39 DHC + 40 VSAT + 41 CVGI). **BONUS validation: Sub-bundle B same-day-replay UPSERT path NOW operationally validated** (snapshot_id=5 from yesterday preserved; call 35 linked via linked_snapshot_id=5 — closes one of the three V2-deferred validations from Phase 11 Sub-bundle B SHIPPED entry). |
| S6 pipeline without env vars | ✅ | Pipeline #64 in 9s; ZERO new schwab_api_calls + ZERO new domain rows (T-A.3 silent-skip path preserved per acceptance #2) |
| S7 cleanup-script regex | ✅ via test coverage | 11 cleanup-script regex unit tests inline GREEN at `tests/scripts/test_cleanup_script_regex.py` (skip destructive plant-fake-worktree path) |
| S8 ruff baseline | ✅ | 18 E501 unchanged |
| S9 sentinel-leak audit | ✅ | New T-A.1 + T-A.3 paths covered by existing `tests/integrations/test_schwab_token_redaction_audit.py` patterns |

### Orchestrator-inline gate-fix at `e2c0384` (mirrors Sub-bundle B's `34be84e` precedent)

**Defect:** runner.py L728-738 + L747-757 hardcoded `client=None` at both Sub-bundle B `_step_schwab_snapshot` + `_step_schwab_orders` callsites. T-A.3 implementer wired env-var helper into `_install_pipeline_marketdata_caches` (market-data ladder) but missed parallel wiring into snapshot/orders callsites. Implementer's +5 helper-return-contract tests didn't integration-test the runner-level wiring through to Sub-bundle B's pipeline steps.

**Fix:** pass `client=schwab_client` instead of `client=None` at both callsites. Single-line per callsite + 1 discriminating regression test (`test_runner_threads_schwab_client_into_snapshot_and_orders_steps` does source-level pattern matching on runner.py to assert `client=schwab_client, surface="pipeline"` shape; explicitly rejects pre-fix `client=None, surface="pipeline"` shape).

### Three highest-leverage SHIPPED deliverables

1. **Credential entry UX** — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` env vars supersede interactive prompt at `construct_authenticated_client`. Both-or-neither resolution (partial → SchwabConfigMissingError with actionable message). Operator can now `$env:SCHWAB_CLIENT_ID = "..."; $env:SCHWAB_CLIENT_SECRET = "..."` once per shell session (or in PowerShell profile) → every Schwab CLI invocation runs without prompts. Daily-use unblock.
2. **`swing schwab setup` self-healing** — auto-detects + atomically renames stale tokens DB to `*.deleted-<ts>` (24h recovery window) BEFORE invoking schwabdev. Closes Sub-bundle C operator-paired-gate finding from yesterday (`logout → setup` recovery sequence is no longer needed; `setup` now handles it in one shot).
3. **Pipeline env-var path** — `_construct_pipeline_schwab_client(cfg)` reads same env vars; both-or-neither (partial → return None + log WARNING). Pipeline now actually fires Schwab steps end-to-end when operator has env vars set. Closes T-C.6 D1 ACCEPT-WITH-RATIONALE V1 graceful-degradation gap.

### NEW V2.1 §VII.F amendment candidates banked (per implementer return report)

1. `oauth.tokens_db_rename` dedicated endpoint enum value for T-A.2 audit row (currently uses `oauth.code_exchange` with descriptive error_message; would require schema v18→v19 to add new enum value).
2. Unify `logout` `revoke_and_delete` timestamp to UTC.

### Tests + ruff + schema deltas

- Tests: 3752 → 3787 (+35 net = +34 implementer + 1 inline gate-fix regression). Within +20..+40 brief projection.
- Ruff baseline: 18 E501 unchanged.
- Schema version: v18 unchanged (Sub-bundle A is consumer-side only).

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **3 unresolved material discrepancies (39/40/41) from pipeline #63 are LEFT UNRESOLVED by design** — they're correct signal of fiction-vs-truth divergences; will be auto-corrected categorically when Phase 12 Sub-bundle B (auto-correct service) ships. Phase 10 dashboard banner shows "3 unresolved" until then — that's accurate state.
2. **Worktree husk pending operator cleanup-script** — branch `phase12-bundle-A-schwab-operational-pain` deleted post-merge; on-disk husk at `.worktrees/phase12-bundle-A-schwab-operational-pain/` ACL-locked per all prior-phase precedent. **The cleanup-script's regex (post T-A.4 fix) DOES match `phase12-*` so `-DeregisterFirst` should pick it up cleanly without any manual `git worktree remove --force` workaround.** Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` at convenience.
3. **7-day refresh-token clock** restarted 2026-05-15T03:59:25 UTC during S4; expires ~2026-05-22.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md` (`892e3e3`).
- Return report: `docs/phase12-bundle-A-return-report.md` (worktree branch).
- Orchestrator-inline gate-fix: `e2c0384` (worktree branch).
- Integration merge: `123d27a`.

### Next dispatch

**Phase 12 Sub-bundle B (auto-correct journal-from-Schwab service) UNBLOCKED.** Per the architectural pivot banked in the 2026-05-15 entry above (top of phase3e-todo). Substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected; operator-paced.

---

## 2026-05-14 Schwab API Sub-bundle D SHIPPED + Phase 11 CLOSED — status surface full + briefing degraded banner + cycle-checklist + CLAUDE.md gotchas + E2E + migration verification + review-form polish (3 Codex rounds; 14 commits; CLOSES THE SCHWAB ARC)

**Sub-bundle D SHIPPED 2026-05-14** at branch tip `cae6e7f` (integration merge to main pending operator-witnessed gate; baseline `23161a0`). 14 commits = 7 task-impl (T-D.1 `9ff7967` status surface; T-D.2 `3f462c8` cycle-checklist; T-D.3 `6aa8f44` E2E; T-D.4 `0cf2ade` CLAUDE.md gotchas; T-D.5 `4b6153e` briefing degraded banner; T-D.7 `7339957` migration verification; T-D.elective.1 `1f30cb3` review-form Phase-7 stale-promise replacement) + 2 pre-Codex review fixes (§J.5 cassette reword `37084bf`; cycle-checklist TTL alignment `edf0e43`) + 5 Codex-fix (R1 M#1+M#2 PROVISIONAL + tokens-parse `a0d618d`; R1 M#3 setup message `0327845`; R1 M#4 docstring `9341fd9`; R1 m#1 cycle-checklist `2703341`; R2 bundled `cae6e7f`).

### Post-merge addendum (orchestrator) 2026-05-15

**Integration merged to main at `e51e6eb`** via `--no-ff` per Sub-bundle B + C precedent (preserves Codex-fix chain visibility). Branch HEAD `6f943db` (return report `6f943db` + Phase 11 SHIPPED entry `9028ab6`); 16 commits since baseline 23161a0 (the implementer count of 14 above omitted the final 2 — return report + this Phase 11 entry).

**Operator-witnessed gate ALL PASS** (5 operator-driven + 4 inline = 9 surfaces):
- S1+S5+S6+S9 inline PASS (3747 fast pass per implementer; T-D.3 E2E + T-D.7 migration atomicity + ruff baseline GREEN).
- **S2 PASS** — `swing schwab status --environment production` rendered LIVE indicator + "expired 2h 30m ago" access token + "6d 20h remaining" refresh token + recent calls (24-28) + masked account_hash (`E8F***76`) + recent errors (8 in 24h, 10 in 7d from C gate's expired-token attempts) + ZERO credential prompt + ZERO token bytes.
- **S3 PASS** — `--environment sandbox` rendered DEGRADED indicator on call 29 (HTTP 401 from C gate); banner predicate fires correctly.
- **S4 PASS** — pipeline #60 + briefing.md emits the degraded banner verbatim per spec §3.4.4: `> **Schwab integration: degraded** — most recent API call to \`marketdata.quotes\` did not succeed. Run \`swing schwab status\` to diagnose.` Banner is GENERIC (no token bytes / no error_message body content) + endpoint-named + remediation hint + Markdown-blockquote-formatted at top of briefing.md.
- **S7 PASS** — cycle-checklist review by operator clean.
- **S8 PASS via template inspection** — `swing/web/templates/partials/review_form.html.j2:67` reads "plan exactly? Auto-derivation from Fills is a future enhancement; manual entry V1." — stale "(Phase 7 will auto-derive this from Fills.)" parenthetical GONE; new phrasing matches brief recommendation verbatim.

**Production state delta from gate** (post-merge):
- `schwab_api_calls`: 29 → 30+ (small delta from S2/S3 status surface NOT writing audit rows — pure read-side; only pipeline #60 which silent-skipped Schwab steps per T-C.6 D1 added zero rows; no new rows expected from D scope).
- Domain rows unchanged (D scope is read-side only).
- `~/swing-data/schwab-tokens.production.db` clock started 2026-05-15T03:59:25+00:00; expires ~2026-05-22.
- `~/swing-data/schwab-tokens.sandbox.db` clock started 2026-05-14T20:30:55+00:00; expires ~2026-05-21.
- D worktree husk: 4th in cleanup-script queue (A + B + C + D pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`).

**Operator-paired-gate brief inaccuracies banked for V2.1 §VII.F amendment routing:**
- Brief §4 surface table referenced `/reviews` route for S8; actual routes are `/reviews/pending` (listing) + `/reviews/{review_id}/complete` (form).
- Brief §0.7 referenced "3 pre-existing failures"; actual baseline is 4 (per Sub-bundle C SHIPPED entry banking; xdist-flaky setup CLI test).

**Operator-reported NEW bug surfaced during S4 gate** — pipeline run errors on missing `data/finviz-inbox/` folder; banked as separate entry above (2026-05-15).

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/2m → R2 0C/2M/2m → R3 0C/0M/1m); **ZERO Critical findings** entire chain; **1 ACCEPT-WITH-RATIONALE banked** (R1 M#4 — E2E test scope service-composition-driven not CLI-driven; per-CLI tests already cover the CLI surfaces; banked at return report).

### Test count + style + schema deltas

- **+30 fast tests** (3717 → 3747; brief projected +19; overshoot from R1+R2 defensive coverage + parametrize)
- 3 pre-existing failures unchanged (`tests/integration/test_phase8_pipeline_walkthrough.py`)
- 5 skipped (1 flag-classifier only — baseline preserved)
- Ruff baseline 18 E501 unchanged
- Schema version 18 unchanged (consumer-side; v18 landed by Sub-bundle A); ZERO new schema work in D scope

### Sub-bundle D operator-visible deliverables

1. **`swing schwab status` full per-environment surface** (T-D.1) — three-state determination (CONFIGURED / PROVISIONAL / NOT_CONFIGURED) per environment; refresh-token TTL with severity escalation (≤24hr WARN; ≤2hr ERROR + bold red); recent-call audit summary. R1 M#1 + M#2 restored PROVISIONAL state (narrowly scoped to "tokens DB missing on disk" per R2 M#2) + consults tokens-DB `parse_err` / `refresh_token_issued`. R2 M#1 closed `token_dictionary` bypass; R2 M#2 narrowed PROVISIONAL strictly; R2 m#1 aligned expiry boundary; R2 m#2 refreshed 3-state docstring.
2. **Briefing.md degraded banner** (T-D.5) — emits "Schwab integration: degraded" when most-recent `schwab_api_calls.status != 'success'`. V1 ships banner-only (NOT always-present section per spec §7.2 + cycle-checklist initially claimed; cycle-checklist narrowed post-R1 m#1).
3. **Cycle-checklist updates** (T-D.2) — weekly re-auth reminder + 7-day refresh-token TTL aligned with operator-paired-gate observation (pre-Codex review fix `edf0e43`).
4. **CLAUDE.md gotchas promotion** (T-D.4) — 12 entries (6 brief §3 + 6 plan §J supplementary; §J.5 reworded as V2-PLANNED per spec-review fix). Covers: schwabdev camelCase kwarg discipline; typed `SchwabApiError` audit-row close discipline; `swing schwab setup` clean-state requirement; 7-day refresh-token clock; `Schwabdev` capital-S logger prefix; silent-failure-mode discipline; tokens DB plaintext-at-rest; pipeline-active CLI exclusion; sandbox short-circuit gating; `setLogRecordFactory` content-redaction wrapper; cassette runbook V2-PLANNED; source-artifact reference shape.
5. **E2E happy-path integration test** (T-D.3) — service-composition-driven (NOT CLI-driven per ACCEPT-WITH-RATIONALE R1 M#4); per-CLI tests cover the CLI surfaces.
6. **Migration 0018 BEGIN/COMMIT discipline + manual-backup warning verification** (T-D.7).
7. **Review-form polish (T-D.elective.1)** — replaced stale Phase-7-auto-derive parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67` with forward-looking phrasing per orchestrator default — "Auto-derivation from Fills is a future enhancement; manual entry V1." Closes the 2026-05-13 polish task entry below.

### Schwab arc closer aggregate (4-bundle Phase 11 closure)

| Sub-bundle | Merge SHA | Codex rounds | Commits |
|---|---|---:|---:|
| **A** (foundational) | `5b6e5ba` | 4 | 19 |
| **B** (trader API + snapshot) | `df29232` | 5 + 1 orchestrator-inline gate-fix at `34be84e` | ~24 |
| **C** (market data + cache ladder) | `fd457de` | 5 | 26 |
| **D** (arc-closer; this bundle) | (pending integration merge) | 3 | 14 |

**Arc total: ~17 Codex rounds across 4 bundles; ~83 commits; ZERO Critical findings entire arc.**

**5 ACCEPT-WITH-RATIONALE banked across arc:**
- Sub-bundle A: 1
- Sub-bundle B: 1 (lease status fields V2-deferred)
- Sub-bundle C: 2 (R1 M#5 `_step_charts` ladder V2; R4 M#1 file-level mtime V1 best-effort)
- Sub-bundle D: 1 (R1 M#4 E2E test scope — service-composition vs CLI-driven)

### V2 candidates banked across arc

**Operator-visible Q-deferrals from spec §10:** Q2 token encryption-at-rest (schwabdev `encryption=<key>`); Q3 multi-account support; Q4 WebSocket streaming; Q5 web UI for Schwab integration (status surface only V1); Q6 Schwab inception-CSV ingestion (separate dispatch per phase3e-todo 2026-05-12 entry); Q7 TOS reconciliation deprecation milestone.

**Sub-bundle C return report §7 + Sub-bundle D V2 banks:**

1. `_step_charts` ladder wiring (R1 M#5 from C).
2. `read_or_fetch_archive` Shape A read-path extension.
3. `empty_flag is True` pattern review across other JSON-boolean Schwab response flags.
4. `_yfinance_window_to_shape_a_df` heuristic conversion → explicit fallback contract.
5. Legacy parquet cleanup pass (after all consumers refactor to Shape A).
6. REPLACE-mode `write_window` for explicit archive reset.
7. Per-row `recorded_at` column as freshness signal alternative to filesystem mtime (R4 M#1 family).
8. Pipeline `client_id`/`client_secret` env-var path (T-C.6 D1).
9. `swing schwab setup` self-healing (detect-and-rename stale tokens DB; gotcha #3 candidate from D T-D.4).
10. Briefing always-present "Schwab integration" section (D R1 Minor #1 — currently banner-only).
11. Future Schwab live-test cassette infrastructure + cassette staleness runbook (D T-D.4 §J.5 V2-PLANNED).
12. **(D NEW) `swing config set integrations.schwab.environment` CLI surface** — currently FIELD_REGISTRY doesn't include the env field; operators must hand-edit `user-config.toml` (caught by T-D.2 + adapted CLI message at R1 M#3).
13. **(D NEW) Briefing always-present "Schwab integration" section** — V1 ships banner-only; spec §7.2 + cycle-checklist initially claimed always-present section; cycle-checklist narrowed to banner-only post-R1 m#1.

### Plan-text amendments pending V2.1 §VII.F routing

- ~17 from Sub-bundle A.
- ~5 from Sub-bundle B.
- ~18 from Sub-bundle C.
- **(D NEW) `swing schwab setup` success message wording (R1 M#3)** — plan §I.1 referenced `swing config set integrations.schwab.environment` command which doesn't exist.
- **(D NEW) Refresh-token TTL claim** (90d/7d split → 7d uniform per operator-paired-gate observation 2026-05-14; pre-Codex review fix).
- **(D NEW) E2E test scope wording (R1 M#4)** — plan §Tasks-D T-D.3 said "cassette-driven" but no Schwab cassettes exist; implementation is MagicMock-driven service-composition E2E.
- **(D NEW) PROVISIONAL state narrowed** strictly to "tokens DB missing on disk" per Codex R2 Major #2.
- **(D NEW) Briefing always-present "Schwab integration" section** was specified but ships banner-only V1.

### Production state delta from D scope

- ZERO new domain rows from D operator-witnessed gate surfaces (S2-S8 are inline tests OR read-only operator-driven CLI/filesystem/browser surfaces).
- Operator's Schwab tokens DB clock still on the fresh 7-day cycle from Sub-bundle C gate recovery (refreshed 2026-05-14; expires ~2026-05-21).

### Closure

- Phase 11 (Schwab API integration) **CLOSED** — 4 sub-bundles A → B → C → D all SHIPPED in strict dispatch order.
- **Phase 12+ candidate triage UNBLOCKED** for orchestrator-paced dispatching.
- Worktree teardown: branch `schwab-bundle-D-arc-closer` ready for integration merge to main; on-disk husk will be 4th in operator's cleanup-script queue (after A, B, C still pending per Sub-bundle C SHIPPED entry).

---

## 2026-05-13 Trade exit review form — stale "Phase 7 will auto-derive" promise + counterfactual still operator-input

**Symptom (operator-surfaced 2026-05-13):** trade exit review form's "Counterfactual (optional)" fieldset displays helper text:

> "What R would you have realized if you'd followed your original plan exactly? (Phase 7 will auto-derive this from Fills.)"

Source: [`swing/web/templates/partials/review_form.html.j2:66-67`](../swing/web/templates/partials/review_form.html.j2#L66-L67). The promise is from Phase 6 design (form authored before Phase 7 shipped); Phase 7 SHIPPED 2026-05-05 at `c617777` (per CLAUDE.md status line) but did NOT wire counterfactual auto-derivation. The `realized_R_if_plan_followed` field remains an operator-input column on `trades` (per `swing/data/repos/trades.py:427+445`); only the DOWNSTREAM `mistake_cost_R` + `lucky_violation_R` are derived (per `swing/trades/review.py:158-174`) — but only IF operator manually fills in `realized_R_if_plan_followed`.

**Phase 7 deliverables actually shipped** (per CLAUDE.md status + grep): state machine (`swing/trades/state.py`), origin tracking (`swing/trades/origin.py`), derived-metrics infrastructure (`swing/trades/derived_metrics.py`), Fills first-class (`fills` table + repo). **Counterfactual auto-derivation NOT in scope of any shipped Phase 7 task.**

### Two-part fix candidate

**(a) Immediate polish (trivial; ~5-line change in one template):**

Update `swing/web/templates/partials/review_form.html.j2:66-67` to remove the stale Phase 7 reference. Replace with current-state-honest helper text. Two phrasing options:

- Minimal: drop the parenthetical entirely. Helper text becomes just "What R would you have realized if you'd followed your original plan exactly?"
- Forward-looking: "What R would you have realized if you'd followed your original plan exactly? (Auto-derivation from Fills is a future enhancement; manual entry V1.)"

Operator preference TBD; orchestrator default = forward-looking phrasing (preserves the deferred-derivation intent for future implementer).

**(b) V2 design dispatch (actual auto-derivation):**

Define what "R if plan followed" means when plan-followed conditions can take multiple shapes:
- Trade stopped via violation: counterfactual = R at original planned stop (operator EXITED above-stop manually).
- Trade target hit but operator exited early: counterfactual = R at planned target.
- Trade trailed out: counterfactual = R at planned trail-MA exit.
- Trade closed for non-plan reason: counterfactual = ?

Each scenario needs a deterministic mapping from `Fills` + `trades.planned_*` columns + `trade_events` history → counterfactual R. Likely a new helper in `swing/trades/derived_metrics.py` consuming the existing infrastructure.

**Schwab API arc adjacency:** Schwab API integration may strengthen this — Schwab returns authoritative fill timing/price granular enough to support more sophisticated counterfactual computations (e.g., "R if you had exited at the same intraday timestamp where you actually exited but at the planned-stop price"). Could be V2-bundled with Schwab market-data ladder OR remain standalone.

### Disposition

- **(a) Polish — LOCKED 2026-05-13:** bundled into Schwab API executing-plans **last sub-bundle** (likely Sub-bundle E "polish" per writing-plans dispatch brief §0.7 guidance, but plan author picks final shape; orchestrator threads this task into whichever sub-bundle ships last). **Orchestrator action item:** when writing-plans implementer returns the plan, amend the LAST sub-bundle's executing-plans dispatch brief to include the polish task — update `swing/web/templates/partials/review_form.html.j2:66-67` to drop the stale "(Phase 7 will auto-derive this from Fills.)" parenthetical; replace with forward-looking phrasing per orchestrator default ("Auto-derivation from Fills is a future enhancement; manual entry V1.") OR per operator preference at that triage. NOT added to writing-plans dispatch brief mid-flight (writing-plans implementer dispatched ~2026-05-13 +20min before this triage; mid-flight scope changes cause re-runs).
- **(b) Design** = standalone V2 dispatch (not Schwab-arc-bundled; needs its own brainstorm to lock the counterfactual semantics across stopped/target/trailed/non-plan exit shapes). Operator-paced.

### Cross-references

- Phase 6 source-of-promise: `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md`.
- Phase 7 actual deliverables: `swing/trades/state.py` + `swing/trades/derived_metrics.py` + migration `0014_phase7_state_machine_and_fills.sql`.
- Existing manual-entry consumer: `swing/trades/review.py:158-174` (`compute_mistake_cost_R` + `compute_lucky_violation_R`).

---

## 2026-05-14 Schwab API Sub-bundle C SHIPPED — Market Data API + Shape A cache ladder + PriceCache/OhlcvCache integration + sandbox short-circuit + --verify-marketdata CLI + cross-bundle pin closure (5 Codex rounds; 26 commits; LARGEST NOVEL SCOPE of the arc)

**Sub-bundle C SHIPPED 2026-05-14** at `fd457de` (integration merge of `schwab-bundle-C-marketdata-and-cache-ladder` worktree branch via `--no-ff` to preserve Codex-fix chain per Sub-bundle B precedent at `df29232`). Branch HEAD `88267fd` (26 commits = 1 recon + 7 task-impl + 17 Codex-fix + 1 return-report). Operator-dispatched implementer per orchestrator brief at `8356b34`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0/6/2 → R2 0/2/2 → R3 0/1/2 → R4 0/1/2 → R5 0/0/2); **ZERO Critical findings** entire chain; **2 ACCEPT-WITH-RATIONALE banked** (R1 M#5 `_step_charts` ladder wiring V2; R4 M#1 file-level mtime V1 best-effort awaiting V2 per-row `recorded_at` column); 8 Major resolved with code-content fixes + discriminating regression tests.

### Operator-paired live gate (Option A; 2026-05-14)

Full S2-S5 live verification against operator's production-tier Schwab account + worktree-side inline S1+S6+S7+S8+S9 PASS:

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite (worktree) | ✅ | 3713 passed; 4 pre-existing failures (3 Phase 8 walkthrough + 1 xdist-flaky setup CLI test); 5 skipped. **Main-HEAD post-merge:** 3717 passed; 3 failed (Phase 8 walkthrough only; xdist-flaky setup test passed this time); 1 skipped (only flag-classifier) — both cross-bundle pins (T-C.5 + T-C.7) un-skipped + GREEN. |
| S2 `--verify-marketdata` prod | ❌→✅ post-recovery | First attempt failed: 7-day refresh-token expired (anticipated per dispatch brief §0.7). Recovery via `logout → setup` paste-back. Re-run: calls 27 (`marketdata.quotes` AAPL) + 28 (`marketdata.pricehistory` AAPL bars=23) BOTH success / HTTP 200 / signature_hash present / linked_* NULL ✓. **First live Schwab Market Data API success in production.** |
| S3 `--verify-marketdata --environment sandbox` | ✅ via demonstration | Stale sandbox tokens DB triggered same auto-refresh failure → call 29 audit landed with `status='error'` / `http_status=401` / redacted `error_message` (no token bytes) + ZERO new domain rows. **Production-only-domain-writes contract per spec §3.6.3 holds even on auth failure.** |
| S4 `swing pipeline run` (production env) | ✅ | Pipeline run #58 complete in 47s. Per T-C.6 D1 ACCEPT-WITH-RATIONALE: `_construct_pipeline_schwab_client` returned `None` (cfg has no `client_id`/`client_secret`) → both Sub-bundle B's snapshot/orders steps + Sub-bundle C's ladder warming silent-skipped per Sub-bundle B M#1 surface-aware advisory pattern. ZERO new `schwab_api_calls` rows from pipeline; ZERO domain-row deltas. **V1-shipped behavior; V2 enhancement banked.** |
| S5 backward-compat copy-not-move | ✅-with-inspection-only | V1 ladder silent-skip (S4) blocks live trigger of `_backward_compat_rename`. Archive at `~/swing-data/prices-cache/` has 776 legacy `{TICKER}.parquet` files; ZERO Shape A files yet. T-C.2 unit tests (+18) cover Shape A persistence + backward-compat-rename comprehensively (R1 M#6 + R2 M#1 + R2 M#2 + R3 M#1 + R4 M#1 fixes all landed discriminating regression coverage). |
| S6 sentinel-leak audit Bundle C | ✅ | `tests/integrations/test_schwab_token_redaction_audit.py` GREEN; un-skipped Market Data API portions covered + 2 NEW tests using `MagicMock.side_effect` emitting Schwabdev-logger sentinels FROM INSIDE actual `quotes`/`price_history` calls (R1 M#6 fix discriminating against pre-fix BEFORE-the-call pattern). |
| S7 `SchwabPipelineActiveError` exclusion | ✅ | `test_b6_10_fetch_verify_marketdata_NOT_protected` un-skipped at T-C.5 + GREEN. |
| S8 E2E pipeline production-only gate | ✅ | Bundle B suite unchanged by C (cache-layer integration does NOT regress). |
| S9 ruff baseline | ✅ | 18 E501 unchanged. |

**Sub-bundle C is operationally validated end-to-end against live Schwab Market Data API in production.** First live `marketdata.quotes` + `marketdata.pricehistory` calls; first Shape A parquet-per-(ticker, provider) persistence layer + ladder fetcher infrastructure.

### Anticipated failure: 7-day refresh-token recovery sequence

S2 attempt 1 failed exactly per dispatch brief §0.7 prediction (7-day clock from Sub-bundle A phase-2 OAuth setup expired). Recovery sequence:

1. `swing schwab refresh` — failed (refresh attempted but operator's refresh_token is dead).
2. `swing schwab setup` — **also failed** (auto-refresh fires on stale tokens DB before paste-back; bails out hard with `unsupported_token_type`).
3. `swing schwab logout` — atomically renamed `~/swing-data/schwab-tokens.production.db` → `*.deleted-20260514T175833` (24h recovery window) per A T-A.5 design even though revoke best-effort failed.
4. `swing schwab setup` against now-empty path — clean paste-back; same `hashValue=E8F...0676` auto-selected; fresh 7-day clock started.

**NEW gotcha-promotion candidate (Sub-bundle D T-D.4):** `swing schwab setup` requires clean tokens DB state; auto-refresh fires on stale tokens DB and bails before paste-back code path. Recovery sequence is `logout → setup`, NOT `setup` standalone. **Possible V2 self-healing:** make `setup` detect-and-rename stale tokens DB itself.

### Three highest-leverage SHIPPED deliverables

1. **Market Data API endpoint methods** at `swing/integrations/schwab/marketdata.py` (646 lines; `get_quotes_batch` + `get_price_history` + 4 helpers + `_call_endpoint` shared wrapper). camelCase kwarg trap (B's `34be84e` defect family) PRE-EMPTED via `inspect.signature(schwabdev.Client.price_history)` discriminating test landing in T-C.1 BEFORE code; ZERO defects of that family caught by Codex chain.
2. **OHLCV archive Shape A persistence** at `swing/data/ohlcv_archive.py` (extended +500 lines): `write_window` empty-window-guard + `resolve_ohlcv_window` window-filter + `_backward_compat_rename` 4-case copy-not-move (R2 M#1) with both-files-exist merge-and-quarantine + mtime-based freshness winner (R3 M#1) with nanosecond-precision (R4 m#2). 1512-line test file at `tests/data/test_ohlcv_archive_shape_a.py` covers ALL Codex-caught edge cases.
3. **Market-data ladder fetcher** at `swing/integrations/schwab/marketdata_ladder.py` (455 lines; `fetch_quote_via_ladder` + `fetch_window_via_ladder` + 7 helpers). Sandbox short-circuit per spec §3.6.3 + §H.6.1; yfinance fallback discipline preserved; per-provider tagging through `provider` field on `PriceSnapshot` (NOT plan's hypothetical `PriceCacheEntry` class — actual class name preserved per T-C.4 D1).

### High-leverage Codex fixes worth flagging at integration triage

- **R1 M#1:** `_backward_compat_rename` not wired into ladder hot path — fixed in `1a5e099`.
- **R1 M#3:** Schwab bars NOT persisted to Shape A archive — fixed in `700265c` (write-side) + R3 M#1 / R4 M#1 partial wiring on read-side (chart step deferred V2).
- **R1 M#6:** Sentinel-leak audit tests stubbed sentinels OUTSIDE schwabdev call (would silently pass even without redaction) — fixed at `3663d2c` with `MagicMock.side_effect` pattern.
- **R2 M#1:** Backward-compat rename should COPY-NOT-MOVE the legacy parquet (preserve operator's V1 reads via legacy path) — fixed at `26efbae`.
- **R3 M#1 / R4 M#1:** mtime-based freshness winner for both-files-exist merge — banked as V1 best-effort + V2 candidate #7 (per-row `recorded_at` column closes both staleness + rollback failure modes).

### 2 ACCEPT-WITH-RATIONALE family

1. **R1 M#5** (`_step_charts` ladder wiring V2): chart step still uses legacy `read_or_fetch_archive` path (does NOT consult Shape A files); full wiring requires `fetcher.get()` refactor + weekly-refresh + archive_history_days reconciliation. V1 behavior unchanged for chart-step downstream consumers; ladder ships persistence infrastructure + V2 read-path extension closes the loop.
2. **R4 M#1** (file-level mtime as row-level conflict signal V1 best-effort): coarse signal for fine-grained question. V2 per-row `recorded_at` column closes both directions. V1 impact bounded — `read_or_fetch_archive` consumers read legacy directly; Shape A merge state does NOT affect their reads.

### Production state delta (post-gate)

- `schwab_api_calls`: 17 → **29** (+12 net: failed pre-recovery attempts at calls 18-26 + S2 success calls 27+28 + S3 sandbox auth-failed call 29). All audit rows correctly classified per Sub-bundle B M#3 typed-SchwabApiError discipline.
- `account_equity_snapshots`: **5 unchanged** (no Schwab snapshot writes from V1 pipeline; B-shipped step silent-skipped per T-C.6 D1).
- `reconciliation_runs`: **9 unchanged** (no Schwab orders reconciliation from V1 pipeline; same path).
- `reconciliation_discrepancies`: **38 unchanged**.
- `~/swing-data/prices-cache/`: 776 legacy `{TICKER}.parquet` files unchanged; ZERO Shape A files yet (V1 ladder silent-skip blocks live trigger).
- Tokens DB: fresh 7-day clock started 2026-05-14 (post `logout → setup` recovery).

### NEW gotcha-promotion candidates (Sub-bundle D T-D.4 candidates)

1. **`swing schwab setup` requires clean tokens DB state** (operator-witnessed gate finding) — see "Anticipated failure" section above.
2. **schwabdev camelCase kwarg discipline reinforced** — Sub-bundle B's gate-caught defect (`account_orders(maxResults=...)`) was the precedent; Sub-bundle C pre-empted via `inspect.signature` discriminating test on `Client.price_history`. Both belong in CLAUDE.md.
3. **Pre-existing flaky test baseline correction** — `test_setup_auth_failure_audit_status_and_sentinel_redaction` (Sub-bundle A's T-A.4 setup CLI suite) is xdist-flaky and confirmed pre-existing on main `8356b34` (deterministic-fails serial too). Brief §0.7 said "3 pre-existing failures" — actual is **4**. Doc correction; not a regression.

### V2 candidates banked (7)

Per return report §7.2:

1. `_step_charts` ladder wiring (R1 M#5 follow-up).
2. `read_or_fetch_archive` Shape A read-path extension.
3. `empty_flag is True` pattern review across other JSON-boolean Schwab response flags.
4. `_yfinance_window_to_shape_a_df` heuristic conversion → explicit fallback contract.
5. Legacy parquet cleanup pass (after all consumers refactor to Shape A).
6. REPLACE-mode `write_window` for explicit archive reset.
7. Per-row `recorded_at` column as freshness signal alternative to filesystem mtime.

Plus pipeline `client_id`/`client_secret` env-var path for V2 (T-C.6 D1).

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **Sub-bundle A + B + C worktree husks pending operator cleanup-script** — branches A + B + C all deleted post-merge; on-disk husks at `.worktrees/` ACL-locked. **C is 3rd in cleanup-script queue.** Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (elevated PowerShell) at convenience.
2. **Refresh sandbox tokens DB** (optional V2 work) — sandbox path has stale tokens; `swing schwab fetch --verify-marketdata --environment sandbox` will continue to surface auth-failure-with-correct-discipline until refreshed via paste-back.
3. **8 material discrepancies from Sub-bundle B's gate — ALL RESOLVED** (operator action 2026-05-14 → 2026-05-15: 7 resolved as `journal_corrected` during D-gate window — DHC 9-share trim recorded as fill + VSAT/CVGI/DHC entry-prices corrected — + 1 final stale-re-emission cleanup at disc 37 post-D-merge per VSAT entry-price companion to disc 33). Final state: 30 `acknowledged_immaterial` + 8 `journal_corrected` + 0 `unresolved`. Phase 10 dashboard banner now clear.

### Cross-bundle pin status

**ZERO cross-bundle pins remaining for Sub-bundle D.** Both T-C.5 (`test_b6_10_fetch_verify_marketdata_NOT_protected`) + T-C.7 (Market Data API sentinel-coverage) un-skipped at branch tip + GREEN.

### 18 plan-text deviations banked (V2.1 §VII.F amendment candidates)

Per return report §5: 8 cosmetic + 6 architectural + 4 scope. Includes:
- T-C.1 D3: `_finish_hook` parameter on marketdata `_call_endpoint` (architectural — supports quotes partial-response audit messaging).
- T-C.2 D1: `cache_dir` kwarg threading (matches existing `read_or_fetch_archive` API).
- T-C.3 D2: ladder signatures take `conn` + `surface` kwargs.
- T-C.4 D1: cache layer uses INJECTABLE FETCHER HOOK pattern (rationale: keeps cache env-agnostic; avoids fixture-rewrite cascades).
- T-C.5 D1: sandbox-vs-production interpretation (b) — both envs invoke schwabdev; orchestrator-decision pending Sub-bundle D `swing schwab status` revisit.
- T-C.6 D1: pipeline `_construct_pipeline_schwab_client(cfg)` returns `None` (cfg lacks credentials; V1 graceful degradation).

Plus 5 plan-text deviations from T-C.0.b recon (§A camelCase / §B datetime permissiveness / §C `PriceCacheEntry`→`PriceSnapshot` / §D archive path / §E `OhlcvCacheEntry` existence).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle C executing-plans dispatch brief: `docs/schwab-bundle-C-marketdata-and-cache-ladder-executing-plans-dispatch-brief.md` (`8356b34`).
- Sub-bundle C return report: `docs/schwab-bundle-C-return-report.md` (`88267fd`).
- Sub-bundle C T-C.0.b recon doc: `docs/schwab-bundle-C-task-C0b-recon.md` (`9d1e3e4`).
- Integration merge: `fd457de`.
- Branch HEAD: `88267fd`.

### Next dispatch

**Sub-bundle D executing-plans dispatch UNBLOCKED.** D closes the Schwab arc. Operator-paced. Brief drafting MUST consume:
1. Sub-bundle C return report §9 (5 NEW forward-binding lessons): camelCase signature pinning; dual empty-signal defense-in-depth; injectable fetcher hook architectural pattern; mtime-based freshness V1 best-effort; `construct_authenticated_client` requires sensitive secrets NOT in cfg (V1 pipeline silent-skip).
2. Sub-bundles A + B + C cumulative forward-binding lessons (still BINDING).
3. Plan §Tasks-D at line 2214+ (7 tasks T-D.1..T-D.7; +19 fast tests projected; 2-3 Codex rounds estimated; smallest sub-bundle of the arc).
4. **3 NEW gotcha-promotion candidates** banked above for T-D.4.
5. Review-form polish task (drop stale "(Phase 7 will auto-derive...)" per phase3e-todo 2026-05-13 entry).
6. 7-day refresh-token expiry alert design + `unsupported_token_type` recovery surface design per spec §3.5.
7. `reference/schwabdev/api-calls.md` already pre-checked for all V1 wrappers — no live verification expected at T-D.x.

---

**Sub-bundle B SHIPPED 2026-05-14** at `df29232` (integration merge of `schwab-bundle-B-trader-and-snapshot` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `34be84e` (11 commits = 10 implementer + 1 orchestrator-inline gate-caught fix). Operator-dispatched implementer per orchestrator brief at `19622b6`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR**; **0 Critical / 15 Major** (14 resolved + 1 ACCEPT-WITH-RATIONALE family — see below); +92 fast tests projected by implementer (will land closer to +94 with the 5 added orchestrator gate-fix tests).

### Operator-paired live gate (Option A; 2026-05-14)

Full S2-S5 live verification against operator's production-tier Schwab account:

| Surface | Result | Key observation |
|---|---|---|
| Refresh (bonus A.S4 close) | ✅ | Call 5 `auth_failed` + call 6 `success` retry — honest audit log |
| S2 `--snapshot` prod | ✅ | **First live source-ladder write**: snapshot_id=4 / NLV $2034.78 / `source='schwab_api'` / `schwab_account_hash` populated / call_id=7 |
| S3 `--orders` prod | ❌→✅ post-fix `34be84e` | Caught real defect (see below); reconciliation_run_id=8 with 4 real material discrepancies |
| S4 `--all` prod | ✅ | snapshot_id=5 / NLV $2036.04 / `snapshot_date` rolled to 2026-05-14 between S2 and S4; **same-day-replay UPSERT path NOT exercised live** (cassette unit test covers); reconciliation_run_id=9 with same 4 discrepancies re-emitted |
| S5 `--snapshot --environment sandbox` | ✅ | call_id=17 / `environment='sandbox'` / `linked_snapshot_id=NULL` / **ZERO new domain rows** — production-only domain writes per spec §3.6.3 verified |

**Sub-bundle B is operationally validated end-to-end against live Schwab Trader API in production.** First Schwab API write to source-ladder; first Schwab-sourced reconciliation_run; first sandbox-gating verified.

### Gate-caught defect + orchestrator-inline fix (commit `34be84e`)

**Defect:** trader.py:362 used snake_case `max_results=max_results` but schwabdev 2.5.1 `Client.account_orders` signature uses camelCase `maxResults=`. Cassette tests didn't catch because they stub the entire schwabdev call (any kwargs accepted).

**Audit + degradation worked correctly** per Sub-bundle A T-A.9 typed-SchwabApiError discipline + R1 M#3 audit-success-fire ordering — both error rows landed with `status='error'`, `http_status=None`, error_message redact-truncated. The defect was JUST the kwarg name.

**Fix:** rename to `maxResults=max_results` + 5 NEW discriminating tests at `tests/integrations/test_schwab_trader_kwarg_signatures.py`:
- `test_account_linked_no_kwargs_required` — pins zero-param signature.
- `test_account_details_kwargs_match_schwabdev` — pins `{accountHash, fields}`.
- `test_account_orders_kwargs_match_schwabdev` — pins `{accountHash, fromEnteredTime, toEnteredTime, maxResults, status}` — the post-fix camelCase.
- `test_transactions_kwargs_match_schwabdev` — pins `{accountHash, startDate, endDate, types, symbol}`.
- `test_no_snake_case_kwarg_in_trader_calls` — source-level grep regression defense.

Other 3 trader methods cross-checked + already correct: `account_linked()` no-kwargs; `account_details(account_hash, fields=fields)` where 'fields' matches; `transactions(...)` all positional + `symbol=symbol` matches. **ONLY `account_orders` had the camelCase mismatch.** Skip Codex re-review (mechanical fix; 5-test discipline pin substitutes).

### Three highest-leverage SHIPPED deliverables

1. **Trader API endpoint methods** at `swing/integrations/schwab/trader.py` (4 methods + mappers + models): `get_accounts_linked` / `get_account_details` / `get_account_orders` / `get_account_transactions`. Each wrapped via `_call_endpoint` with audit-row INSERT-then-UPDATE lifecycle from Sub-bundle A T-A.9.
2. **Pipeline steps** at `swing/integrations/schwab/pipeline_steps.py`: `_step_schwab_snapshot` (production-only via spec §3.6.3 gate) + `_step_schwab_orders` (calls trader methods + invokes new `run_schwab_reconciliation` service). Wired into `swing/pipeline/runner.py` AFTER `_step_recommendations` BEFORE `_step_charts`.
3. **`run_schwab_reconciliation` service** at `swing/trades/schwab_reconciliation.py`: mirrors Phase 9 Sub-bundle B `run_tos_reconciliation` shape; reuses `MATERIAL_BY_TYPE` lookup + 5 discrepancy types verbatim; failure-path PRESERVES run row (UPDATE state='failed' per spec §3.3.3).

### High-leverage Codex fixes worth flagging at integration triage

- **R1 M#3:** typed `SchwabApiError` audit-row close discipline (`auth_failed`/`rate_limited`/`error` classification before re-raise) — NEW gotcha family.
- **R1 M#7:** single-Client-instance discipline enforced via new `construct_authenticated_client()` in `auth.py` (cli_schwab now delegates).
- **R1 M#8:** same-day account_hash-flip guard (refuses on differing non-NULL hash).
- **R2 M#1:** pipeline-internal silent-skip (log only, NO audit row) for `client=None` — diverges from CLI surface which writes advisory rows.
- **R5 M#1:** CLI fetch preflight account_hash check before credentials prompt.

### 1 ACCEPT-WITH-RATIONALE family (R2 M#2 + R3 M#2)

**Lease status fields deferred to V2.** Bundle B's ZERO-new-schema scope precluded adding a dedicated `schwab_step_status` lease column; audit row status + `lease.step()` breadcrumb sufficient for V1. Banked for V2.

### Production state delta (post-gate)

- `schwab_api_calls`: 4 → **17** (+13 net: 1 success + 1 auth_failed + 1 success refresh + 1 success snapshot + 2 error orders + 3 success orders re-run + 4 success --all + 1 success sandbox)
- `account_equity_snapshots`: 3 → **5** (+2: snapshot_id=4 NLV $2034.78 / snapshot_date='2026-05-13'; snapshot_id=5 NLV $2036.04 / snapshot_date='2026-05-14'; both `source='schwab_api'`, both `schwab_account_hash` populated)
- `reconciliation_runs`: 7 → **9** (+2: runs 8+9 both `source='schwab_api'`, both `schwab_api_call_id` populated, 7-day windows shifted by 1 day)
- `reconciliation_discrepancies`: 30 → **38** (+8 NEW: 4 each on runs 8+9, same shape — DHC `position_qty_mismatch` + DHC `unmatched_open_fill` + VSAT `entry_price_mismatch` + CVGI `entry_price_mismatch`)

### ⚠ 4 unresolved material discrepancies pending operator triage (with operator-supplied explanations)

These are **real broker-vs-journal divergences** the system surfaced against operator's actual Schwab account (NOT bugs — Phase 9 emit machinery working as designed). Will appear on the dashboard's reconciliation banner per Phase 10 Sub-bundle E T-E.3. Operator-supplied explanations 2026-05-14:

- **DHC `position_qty_mismatch`** + **DHC `unmatched_open_fill`** (rows on runs 8 + 9): operator sold 9 shares today (2026-05-14) as ~25% position reduction (sell into strength). **NOT YET in journal — expected divergence.** Operator-action sequence: (1) record the trim fill via journal CLI; (2) resolve discrepancies as `mistake_corrected`. Sub-bundle B reconciliation correctly surfaced the journal-lag-behind-broker state.
- **VSAT `entry_price_mismatch`** + **CVGI `entry_price_mismatch`** (rows on runs 8 + 9): probably off by ~$0.01; **journal entry-price misreading mistake** (operator misread actual purchase price at original journal entry). Operator-action sequence: (1) update entry price in journal to match Schwab broker record; (2) resolve discrepancies as `mistake_corrected`.

**8 row IDs total / 4 distinct issues / 2 root causes** (1 NEW operator action not yet journaled + 1 OLD journal-entry-data mistake). All 4 represent EXACTLY the kind of operational signal the source-ladder + reconciliation system was built to surface — Sub-bundle B is doing its job. Resolution is operator-action via journal CLI + `swing journal discrepancy resolve <id> --resolution=mistake_corrected --reason="..."`.

### NEW gotcha-promotion candidate (Sub-bundle D T-D.4 candidate)

**schwabdev camelCase parameter names vs project snake_case convention.** schwabdev uses `accountHash`, `fromEnteredTime`, `toEnteredTime`, `maxResults`, `startDate`, `endDate`, etc. — project convention is snake_case throughout. Wrapper kwargs MUST match schwabdev's camelCase exactly OR they fail at runtime with `TypeError: got an unexpected keyword argument`. Sub-bundle A's lesson #5 ("schwabdev 2.5.1 actual surfaces") covered response shapes but missed this kwarg-naming dimension; B's gate exposed it. **CLAUDE.md gotcha promotion at Sub-bundle D T-D.4:** discriminating-test pattern is to pin every wrapper's kwarg names against `inspect.signature(schwabdev.Client.X)` (Sub-bundle B established the pattern at `tests/integrations/test_schwab_trader_kwarg_signatures.py`); replicate for any future schwabdev wrapper additions.

### NEW V2 candidate banked

**Credential entry UX** (`SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` env-var fallback OR session-cached prompt OR `--client-id` / `--client-secret` CLI flags). Operator prompted for `client_id` + `client_secret` on every CLI invocation in the gate session — by Sub-bundle A T-A.2 design (security posture; not in cfg cascade). Acceptable for V1 but friction-heavy for ops use. Matches Q2 V2 token encryption hardening family.

### Same-day-replay-provenance live-validation deferred

Sub-bundle B same-day-replay-provenance test (plan T-B.3 + T-B.4 R3 Major #4 ACCEPT-WITH-RATIONALE family) pins UPSERT-preserves-snapshot_id + LATEST-writer-wins-source_artifact_path semantics. Live gate (S2 + S4) didn't exercise this path because `last_completed_session(now())` rolled from 2026-05-13 to 2026-05-14 between S2 (12:30 PM PT) and S4 (1:27 PM PT) — `(snapshot_date, source)` UNIQUE INDEX correctly inserted a NEW row instead of UPSERTing. **Cassette unit test in T-B.3 stubs dates to force the same-day path; provenance discipline still locked at unit-test level.** Note for operator: date-resolution semantics may surprise — both gate snapshots resolved to different sessions during your active market hours; worth verifying the `last_completed_session` cutoff if it surprises you.

### Cross-bundle pin status

T-B.8 cross-bundle pin un-skipped at branch-tip (Trader API portion of sentinel-leak audit). 1 cross-bundle pin remaining (T-C.7 Market Data API portion).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle B executing-plans dispatch brief: `docs/schwab-bundle-B-executing-plans-dispatch-brief.md` (`19622b6`).
- Sub-bundle B return report: `docs/schwab-bundle-B-return-report.md` (`0124a76`).
- Sub-bundle B T-B.0.b recon doc: `docs/schwab-bundle-B-task-B0b-recon.md`.
- Orchestrator-inline gate-fix: `34be84e` (trader.py:362 maxResults camelCase + 5 discriminating tests).
- Sub-bundle C executing-plans dispatch brief: TBD (orchestrator drafts; operator-paced).

### Next dispatch

**Sub-bundle C executing-plans dispatch UNBLOCKED.** Operator-paced. Brief drafting MUST consume:
1. Recon doc §6 + §6.bis as binding LOCKED inputs.
2. Sub-bundle A's 5 forward-binding lessons (still BINDING for C).
3. Sub-bundle B's NEW lessons (camelCase kwarg discipline + R1 M#3 typed-SchwabApiError audit-row close + R1 M#7 single-Client-instance via construct_authenticated_client + R1 M#8 same-day account_hash-flip guard + R2 M#1 pipeline-internal silent-skip vs CLI advisory rows + R5 M#1 CLI preflight account_hash check).
4. `reference/schwabdev/api-calls.md` pre-check for Market Data API method-name + signature pre-answers (Q12 + Q17 likely pre-answerable).
5. `reference/schwab-api/market-data-{documentation,specification}.md` Schwab Developer Portal canonical docs.
6. Cross-bundle pin (un-skip at T-C.7).

---

## 2026-05-14 Schwab API Sub-bundle A SHIPPED — schwabdev wrap + auth + migration 17→18 + audit infrastructure (4 Codex rounds; 19 commits; phase-2 live OAuth executed end-to-end against production)

**Sub-bundle A SHIPPED 2026-05-14** at `5b6e5ba` (integration merge of `schwab-bundle-A-foundational` worktree branch — preserved Codex-fix chain via `--no-ff` per operator note). Operator-dispatched implementer per orchestrator brief at `bd166c5`. Branch HEAD `6550494` (19 commits = 11 task-impl + 1 hotfix bdf82da + 1 phase-2 addendum + 3 Codex-fix + 1 cleanup-script-help-escape + 1 return-report).

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent shape (R1 0C/5M → R2 0C/1M/1m → R3 0C/1M/1m → R4 0C/0M); **ZERO Critical findings**; **1 ACCEPT-WITH-RATIONALE banked** (R2 Minor #2 `force_refresh` unchanged-token integrity check per plan §H.2 step 6 — operator-facing error already distinguishes "<not rotated>" from "<raised>").

### Three highest-leverage SHIPPED deliverables

1. **Schema migration 17 → 18** (T-A.7) with file-level explicit `BEGIN;`/`COMMIT;` discipline per plan §C.4 — `schwab_api_calls` table (14 columns + 4 indexes + 3 FKs `ON DELETE SET NULL`) + ALTER `account_equity_snapshots.schwab_account_hash TEXT NULL` + ALTER `reconciliation_runs.schwab_api_call_id INTEGER NULL`. Counter-example test locks the discipline (canonical-minus-BEGIN-fixture FAILS rollback). **Forward-binding for migrations 0019+** until runner is updated.

2. **Three-layer token redactor** (T-A.10): Layer 0 known-secret exact-replace from process-global registry (5 long-lived slots: client_id/client_secret/access_token/refresh_token/account_hash) + Layer 1 heuristic regex (hex 32+ / base64 24+) + Layer 2 `logging.setLogRecordFactory()` with recursion guard + factory-replacement defense via `ensure_*` re-wrap. **Logger prefix `"Schwabdev"` (capital S — live schwabdev 2.5.1 deviation from plan §H.8 lowercase)**. R7-R10 chain hardenings encoded with discriminating tests. Cross-bundle pins added for B/C surfaces (`@pytest.mark.skip(reason='un-skip at T-B.8 + T-C.7')`).

3. **`swing/integrations/schwab/` sub-package** with composition over `schwabdev.Client`: 8 typed exception classes; `_suppress_transport_debug_logs` covering 4 transport-debug loggers; audit-service caller-held-tx-rejecting transactional wrappers (`record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash` combined-tx2, `link_reconciliation_run`).

### CLI subcommands SHIPPED

`swing schwab {setup, refresh, logout, status}` with audit lifecycle wrapping; pipeline-active exclusion (`--force` overrides on setup/logout; refresh has NO `--force` per Codex R1 Minor #3 concurrent-safe); schema-check-fail-fast (T-A.4 hotfix `bdf82da` from phase-2 findings); server-stamped audit timestamps; `account_hash` masking via FIELD_REGISTRY (first-3 + `***` + last-2).

### Phase-2 live verification (2026-05-14; operator-paired end-to-end against production)

OAuth paste-back flow executed end-to-end against operator's production-tier Schwab Developer Portal app:
- Tokens DB persisted at `~/swing-data/schwab-tokens.production.db` (957-byte JSON despite `.db` extension; valid access + refresh tokens).
- 64-char `account_hash` auto-picked from `client.account_linked()` + cfg-cascade-written to `~/swing-data/user-config.toml` `[integrations.schwab].account_hash`.
- 4 production `schwab_api_calls` rows: 2 corrected to `status='auth_failed'` via `scripts/fix_phase2_misleading_audit_rows.py` (idempotent; safe to re-run) + 2 `status='success'`.
- **7-day refresh-token clock started 2026-05-14** — operator must re-auth by ~2026-05-21 per recon §2.11 (will be threaded into Sub-bundle D status alert design + cycle-checklist update + CLAUDE.md gotcha promotion).

### Tests + ruff + schema deltas

- Tests: ~3287 baseline → expected ~3413 main HEAD (+126 net per return report §3; pending fast-suite run completion to confirm).
- Ruff: 18 E501 unchanged.
- Schema: v17 → **v18** (verified `EXPECTED_SCHEMA_VERSION=18` post-merge).

### Operator-witnessed verification gate state

Per dispatch brief §3 + return report §4:

- **S1 pytest fast-suite** PASSED (Codex required green to converge across 4 rounds).
- **S2 Migration 0018 lands cleanly** PASSED via phase-2 live verification (production swing.db migrated successfully; `schwab_api_calls` table + 2 ALTERs verified).
- **S3 `swing schwab setup` paste-back** PASSED via phase-2 live verification (end-to-end against operator's production-tier app; tokens DB persisted; `account_hash` cfg-cascade-written).
- **S4 `swing schwab refresh`** NOT EXPLICITLY DRIVEN — operator-elective (return report notes code-path coverage may be sufficient OR drive at follow-up gate session).
- **S5 `swing schwab status` skeleton** NOT EXPLICITLY DRIVEN — same operator-elective.
- **S6 `swing schwab logout`** NOT EXPLICITLY DRIVEN — same operator-elective.
- **S7 Sentinel-token-leak audit** PASSED inline (24 assertions per T-A.10 GREEN).
- **S8 ruff baseline** PASSED inline (18 E501 unchanged).

### 13 V2.1 §VII.F amendment candidates banked

8 recon-doc-banked plan deviations (§5.1) + 5 NEW Codex-chain deviations (§5.2). Cumulative pending arc total: **40** entering Sub-bundle B (was 27 at Phase 10 close + 13 from this dispatch). Detailed in return report §5.

### 5 forward-binding lessons for Sub-bundle B (return report §8)

1. **schwabdev's silent-failure-mode discipline** — `Client.__init__` + `update_tokens()` do NOT raise on auth failure; they print + retry + return silently. Wrappers MUST verify post-call state (`client.tokens.access_token` populated + rotated). Discriminating-test pattern: stub schwabdev call to NOT mutate `tokens.access_token`; assert wrapper raises `SchwabAuthError` + audit row `status='auth_failed'`.
2. **Audit-success-fire ordering** — `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes (R1 M#3 family). Pattern: validate response shape → validate response content → validate operator-pickable state → fire success audit. Each pre-success rejection path fires `record_call_finish(status='auth_failed')` with redacted `error_message` + raises.
3. **Pre-call factory-replacement defense** — `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call. Discriminating-test pattern: install third-party factory between two schwab calls; assert second call re-wraps the factory before invoking schwabdev.
4. **Redact-then-truncate audit-error ordering** — `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate to audit-column-budget. Discriminating-test pattern: register a sentinel that straddles the truncation boundary; assert no partial-prefix survives.
5. **schwabdev 2.5.1 actual surfaces** (banked from phase-2 live verification):
   - `Client` ctor: 8 params (`app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None`).
   - Tokens DB content: **JSON (NOT SQLite)**; content shape `{access_token_issued, refresh_token_issued, token_dictionary: {access_token, refresh_token, id_token, expires_in: 1800, token_type, scope}}`.
   - `client.account_linked()` success: list of dicts `[{accountNumber, hashValue}, ...]`.
   - `client.account_linked()` failure: dict error envelope (NOT a list).
   - Force-refresh kwarg: `client.update_tokens(force_access_token=True)` (NOT `force_refresh_token=True` which triggers full OAuth dance).
   - Schwab `code` expiry window: ~30 seconds from redirect.
   - Logger name: `"Schwabdev"` (capital S).
   - NO `revoke()` method exposed; use manual `POST /v1/oauth/revoke` (Basic auth + `token=<refresh_token>&token_type_hint=refresh_token` form body).

### Production state post-merge (per return report §6 #4)

- Schema: **v18**.
- 4 rows in `schwab_api_calls` (2 corrected-to-auth_failed + 2 success).
- `~/swing-data/schwab-tokens.production.db` exists (JSON, 957 bytes; valid access + refresh tokens).
- `~/swing-data/user-config.toml` has `[integrations.schwab].account_hash` = 64-char `hashValue`.
- 7-day refresh-token clock started 2026-05-14 (operator must re-auth by ~2026-05-21).

### Post-merge housekeeping items

1. **`pip install -e .` shim rebuild — COSMETIC only; post-merge code already reachable.** Per return report §6 #2: editable install pointer was already at MAIN (T-A.1 failed to repoint to worktree, so install stayed at main throughout). Merge automatically updated the code under the pointer. Orchestrator attempted post-merge `pip install -e .` for shim refresh; hit the same `swing.exe`-locked `WinError 32` (`c:\users\rwsmy\appdata\roaming\python\python314\scripts\swing.exe` held by another process). **This is a Windows-Python entry-point-shim rebuild blocker, NOT a code-pointer problem.** Operator already used `python -m swing.cli ...` workaround during phase-2 OAuth setup successfully; post-merge invocations via `python -m swing.cli ...` from main repo dir hit the post-merge Sub-bundle A code. The `swing` shim may also work (if it was rebuilt with the post-merge entry-point definition at any prior `pip install -e .` cycle). If operator wants to refresh the shim cleanly, stop the locking process (likely a running `swing web` instance) + re-run `pip install -e .` — but it's not blocking any functionality.
2. **Worktree husk pending operator cleanup-script** — branch `schwab-bundle-A-foundational` deleted post-merge; on-disk husk at `.worktrees/schwab-bundle-A-foundational/` will be ACL-locked per Phase 6+7+8+9+10 precedent. **9th pending husk** in cleanup-script queue per return report §7. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` post-merge to clean up.
3. **Optional gate completion S4/S5/S6** — operator-elective per return report §6 #1; sub-second-cost CLI invocations against operator's existing production tokens DB. Code-path coverage may be sufficient.
4. **Production audit-row cleanup script** at `scripts/fix_phase2_misleading_audit_rows.py` is idempotent; banked at return report §6 #3 for future archeologists.

### Cross-bundle reminders for B/C/D dispatch brief drafting

- **Single-Client-instance discipline:** B/C/D MUST consume the SAME `SchwabClient` instance from A; MUST NOT create additional `schwabdev.Client(...)` instances elsewhere (per Finding 2 in 2026-05-13 schwabdev distillation entry).
- **`Schwabdev` capital-S logger prefix:** any logger filtering/inspection in B/C/D MUST use the live capital-S form, NOT the lowercase plan §H.8 assumption.
- **`ensure_schwab_log_redaction_factory_installed()`** pre-call defense BINDING for every schwabdev API call (Sub-bundle B + C wrappers).
- **`reference/schwab-bundle-A-task-A0b-recon.md`** (recon doc §6 + §6.bis) is LOCKED input for Sub-bundle B dispatch brief drafting per return report §6 #6.
- **`ReconciliationRun.schwab_api_call_id`** field already exists at branch-tip (R1 M#5 landed it); Sub-bundle B's `run_schwab_reconciliation` populates it (no re-implement).
- **Codex chain pre-emption table** (return report §12 #6): Sub-bundle B brief should pre-empt the 4 patterns Sub-bundle A Codex caught — silent-failure post-call validation (M#1 family); audit-success-fire ordering (M#3 family); factory-replacement defense (M#2 family); redact-then-truncate (R3 M#1 family).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle A executing-plans dispatch brief: `docs/schwab-bundle-A-executing-plans-dispatch-brief.md` (`bd166c5`).
- Sub-bundle A return report: `docs/schwab-bundle-A-return-report.md` (`6550494`).
- Sub-bundle A T-A.0.b recon doc: `docs/schwab-bundle-A-task-A0b-recon.md` (Phase 1 pre-check + Phase 2 operator-paired live verification observations).
- Production audit-row cleanup script: `scripts/fix_phase2_misleading_audit_rows.py`.
- Distilled refs consumed: `reference/schwab-api/{account,market-data}-{documentation,specification}.md` + `reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md`.

### Next dispatch

**Sub-bundle B executing-plans dispatch UNBLOCKED.** Operator-paced. Orchestrator drafts the executing-plans brief when operator commissions. Brief drafting MUST consume:
1. Recon doc §6 + §6.bis as binding LOCKED inputs.
2. The 5 forward-binding lessons in this entry's "5 forward-binding lessons for Sub-bundle B" section.
3. Confirmed schwabdev 2.5.1 surfaces (lesson #5 above) — Sub-bundle B's `trader.py` consumes these.
4. Cross-bundle pins (un-skip-at-T-B.8).
5. Codex chain pre-emption table (4 patterns to pre-empt).
6. `reference/schwabdev/api-calls.md` pre-check for Trader API method-name + signature pre-answers (3 accounts + 7 orders + 2 transactions endpoints documented).
7. `reference/schwab-api/account-{documentation,specification}.md` pre-check for Trader API endpoint shape pre-answers.

---

## 2026-05-13 schwabdev library distillation SHIPPED — 7 tracked refs at `reference/schwabdev/` + 3 operator-flagged cross-bundle findings

**Distillation SHIPPED 2026-05-13** at `62f5dde` (single commit on main; `docs(schwabdev): distill 7 schwabdev library docs pages into reference/schwabdev/`). Operator-driven via parallel instance, post-Sub-bundle-A-dispatch-brief (`bd166c5`). Sub-bundle A implementer is aware + has taken the findings into account; impacts will be noted in the A return report.

### Tracked distillation files at `reference/schwabdev/`

| File | Size | Coverage highlight |
|---|---|---|
| `setup-guide.md` | 6 KB | App registration on developer.schwab.com (callback URL, scopes, "Ready for use" gate); 3-positional `Client` init; first-run paste-back-URL flow |
| `examples.md` | 35 KB | 8 example files verbatim incl. `capture_callback.py` (custom OAuth flow) + `encrypted_db_setup.py` (Fernet token store) + async variant |
| `client.md` | 14 KB | Full `Client`/`ClientAsync` constructors (all 8 params); access-token 30-min + refresh-token 7-day lifecycle; auto-refresh scheduling; **rate limits 120/min + 4000 orders/day** |
| `api-calls.md` | 25 KB | **23 wrapper methods → 23 Schwab REST endpoints with verbatim mapping** (3 accounts + 7 orders + 2 transactions + 1 prefs + 2 quotes + 2 chains + 1 history + 1 movers + 2 markets + 2 instruments) |
| `streaming.md` | 32 KB | 22 Stream methods incl. 13 subscription helpers; LOGIN handshake captured verbatim; **field-ID translation gap flagged** (no helper in schwabdev; defers to our `reference/schwab-api/market-data-documentation.md`) |
| `orders.md` | 15 KB | 5 order helpers + 10 payload recipes (schwabdev adds 3 beyond Schwab's 7: Limit Buy stock, Sell Options open-short, Iron Condor 4-leg) — **NOT V1 SCOPE** (order placement is explicit OUT-OF-SCOPE per spec §1.2 + §3.3.3) |
| `troubleshooting.md` | 8 KB | `unsupported_token_type` → `update_tokens(force_refresh_token=True)`; trailing-slash callback fix; macOS SSL cert; permessage-deflate DNS/proxy fix |

### 3 operator-flagged findings (BINDING for cross-bundle dispatch brief drafting)

**Finding 1: `tokens_file` vs `tokens_db` kwarg name discrepancy.** Setup Guide narrative uses `tokens_file=` parameter name; examples in `examples.md` use `tokens_db=`. **Sub-bundle A T-A.4 + T-A.5 implementer must verify the FINAL kwarg name against schwabdev source before integration** (likely `tokens_db` per examples; setup-guide may be stale doc). Implementer is aware per operator's note; Sub-bundle A return report will record the verified name.

**Cross-bundle impact:** none for B/C/D (they consume the `Client` instance constructed in A; no direct kwarg usage).

**Finding 2: Multi-Client-instance file-locking semantics not documented.** schwabdev's only guidance is "share the same `tokens_db`." Concurrent Client instances with the same `tokens_db` rely on schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` per the writing-plans research, but the multi-instance behavior is integration-layer concern.

**Cross-bundle impact:** Sub-bundles B + C + D MUST consume the SAME `Client` instance constructed in Sub-bundle A's wrapper (`swing/integrations/schwab/client.py:SchwabClient`); MUST NOT create additional `schwabdev.Client(...)` instances elsewhere. This is a binding constraint for B/C/D dispatch brief drafting — orchestrator threads it explicitly into each brief.

**Finding 3: 7-day refresh-token expiry forces full re-auth; no programmatic workaround.** schwabdev's auto-refresh covers the 30-min access_token; refresh_token's 7-day TTL means operator must re-run `swing schwab setup` paste-back at minimum every 7 days. No way to extend programmatically.

**Cross-bundle impact across entire arc:**
- **Sub-bundle A:** T-A.6 `swing schwab status` skeleton SHOULD surface refresh_token validity time-remaining (Sub-bundle A scope per plan §Tasks-A T-A.6 already includes "refresh_token validity displayed").
- **Sub-bundle D:** `swing schwab status` full surface MUST clearly alert operator when refresh_token expiry is approaching (e.g., ≤24 hr remaining = WARN; ≤2 hr = ERROR + bold red). Bundle D dispatch brief explicitly calls this out.
- **Sub-bundle D briefing banner:** the `briefing.md` "Schwab integration: degraded" banner per plan §0.1 SHOULD include refresh_token expiry warning when applicable.
- **Cycle-checklist update:** plan §I.X cycle-checklist additions in Bundle D MUST include "weekly: re-run `swing schwab setup` paste-back if refresh_token approaching 7-day expiry."
- **CLAUDE.md gotcha promotion in Bundle D T-D.4:** add a Schwab-specific gotcha about the 7-day refresh ceiling.

### Cross-bundle orchestrator-action items (BINDING for Sub-bundle B/C/D dispatch brief drafting)

When orchestrator drafts each subsequent dispatch brief, BIND these:

1. **Include `reference/schwabdev/` in §0 reads** (mirroring the existing `reference/schwab-api/` orchestrator-action item from `abb6177`). Both reference dirs are now binding §0 reads for ALL Sub-bundle B/C/D briefs. `reference/schwabdev/` is the SECOND-tier source-of-truth (library wrapping behavior); `reference/schwab-api/` is the FIRST-tier source-of-truth (Schwab Developer Portal canonical docs).

2. **Pre-check `reference/schwabdev/api-calls.md` for Bundle B + C method-name + signature pre-answers.** 23 wrapper methods documented with verbatim Schwab REST endpoint mappings. Many Bundle B + C `[VERIFY]` tags from plan §E (Trader API + Market Data API) may already be answered there — implementer skips the operator-paired live verification for items already in api-calls.md.

3. **Pre-check `reference/schwabdev/client.md` for Bundle A + B + C rate-limit assumptions.** Documented 120/min + 4000 orders/day. Reduces or pre-answers Q17 (Market Data API rate limits independent of Trader API).

4. **Pre-check `reference/schwabdev/troubleshooting.md` for Bundle D status-surface alert design.** `unsupported_token_type` → `update_tokens(force_refresh_token=True)` is operationally critical for the status surface — should surface as actionable alert with the exact remediation command.

5. **Single-Client-instance discipline (Finding 2):** B/C/D dispatch briefs explicitly enumerate that the SchwabClient instance is constructed in A + consumed (NOT re-constructed) by B/C/D. Discriminating test pattern: search `swing/integrations/schwab/` + assert `schwabdev.Client(...)` is invoked ZERO times outside `client.py:SchwabClient.__init__`.

6. **7-day refresh expiry (Finding 3):** Bundle D dispatch brief MUST include the status-surface alert design + cycle-checklist weekly re-auth reminder + CLAUDE.md gotcha promotion. Operator-attention item across entire arc — surface in operator-witnessed gate criteria for each subsequent bundle ("verify status surface refresh_token validity displayed correctly").

### `streaming.md` content disposition (V2 candidate)

Streaming WebSocket support is **NOT V1 SCOPE** per Q4 disposition (V1 batch-poll). However, the field-ID translation gap flagged in `streaming.md` (no helper in schwabdev; would need `reference/schwab-api/market-data-documentation.md` as a manual translation source) is a **V2 design constraint** — when streaming is added in V2, the field-ID translation layer is a NEW design surface NOT covered by schwabdev's API. Bank for V2 streaming dispatch.

### `orders.md` content disposition (OUT-OF-SCOPE)

Order placement (5 helpers + 10 payload recipes) is **explicit OUT-OF-SCOPE** per spec §1.2 + §3.3.3 (project is operator-discretion-trade-execution; automated order placement out of scope). The orders.md distillation is informational only; NOT consumed by any V1 dispatch.

### Cross-references

- Distillation: `reference/schwabdev/` (7 files; commit `62f5dde`).
- Sub-bundle A dispatch brief: `docs/schwab-bundle-A-executing-plans-dispatch-brief.md` (`bd166c5`; Sub-bundle A implementer aware of these findings per operator's note).
- Companion distilled refs: `reference/schwab-api/` (4 files; commit `829dffd`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).

### Next dispatch

**Sub-bundle A executing-plans dispatch UNCHANGED** (already commissioned per operator; brief at `bd166c5`; implementer aware of findings per operator's note). Sub-bundle B/C/D dispatch briefs (drafted post-A-ship) will consume these findings as binding §0 reads + cross-bundle constraints.

---

## 2026-05-13 Schwab API integration writing-plans SHIPPED — 2447-line plan + ZERO open orchestrator-triage questions + 11 Codex rounds (most in project history)

**Plan SHIPPED 2026-05-13** at `7faab72` (single commit on main; `docs(schwab-api): integration writing-plans implementation plan`). Operator-dispatched implementer per orchestrator-drafted brief at `5bf425d` + COA B amendment at `9fd50e6`. Plan at `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (2447 lines; above 1500-2500 brief budget upper-bound by 0%; acceptable due to 11-round adversarial chain producing additional plan content).

**11 Codex rounds → NO_NEW_CRITICAL_MAJOR** (most in project history; Phase 9 = 19 across 5 bundles; Phase 10 = 13 across 5 bundles; Schwab single plan = 11). Cumulative findings 2C + 26M + 23m all RESOLVED inline; **1 ACCEPT-WITH-RATIONALE banked** (R3 Major #4 same-day-UPSERT provenance asymmetry — explicit S7 wording covers).

### Two Critical-class finds (both Codex-discovered + RESOLVED in-tree)

1. **R1 Critical #1 — migration atomicity claim contradicted actual runner.** Plan author misread CLAUDE.md's `executescript() implicit COMMIT` gotcha + assumed `_apply_migration` issues explicit BEGIN. It does not. Migration 0018 SQL file now opens with `BEGIN;` + closes with `COMMIT;` to compensate (file-level discipline; runner-level update banked for V2). Forward-binding for migrations 0019+: mirror this pattern until runner is updated.
2. **R7 Critical #1 — token-redaction filter design based on FALSE Python logging assumption.** Plan author's Layer 2 redactor used `logging.Filter` on root logger; Codex caught that `Logger.callHandlers()` does NOT re-apply ancestor filters during propagation. Fix: switched to `logging.setLogRecordFactory()` approach which catches records at creation time regardless of which logger emits or which handler captures (covers pytest caplog + third-party handlers + lazily-created schwabdev sub-loggers). R7-R10 chain hardened against factory-chaining recursion + reset-fixture contamination + LogRecord direct-call fallback. **One of the deepest design-fix sequences in project history.**

### Sub-bundle decomposition (final shape — 4 sub-bundles per §0.1)

| # | Sub-bundle | Tasks | Tests projected | Inter-bundle deps |
|---|---|---:|---:|---|
| **A** | schwabdev wrap + auth + migration 0018 + audit infra + CLI setup/refresh/logout/status skeleton | 11 (T-A.0..T-A.10) | +126 (range +100..+135) | NONE (foundational) |
| **B** | Trader API + `_step_schwab_snapshot` + `_step_schwab_orders` + `run_schwab_reconciliation` + sandbox-gating + CLI fetch + `SchwabPipelineActiveError` | 9 (T-B.0.b..T-B.8) | +80 (range +75..+95) | A (audit infra + auth + migration) |
| **C** | Market Data API + Shape A parquet-per-(ticker, provider) + `PriceCache` provider field + cache integration + `--verify-marketdata` CLI + sandbox short-circuit | 8 (T-C.0.b..T-C.7) | +68 (range +60..+80) | A (audit infra + auth); independent of B |
| **D** | `swing schwab status` full surface + briefing banner + E2E + cycle-checklist + CLAUDE.md + Phase 11 hand-off | 7 (T-D.1..T-D.7) | +19 (range +15..+30) | A + B + C |
| **Total** | | **35** | **+293 (range +250..+340)** | |

**Strict dispatch ordering: A → B → C → D.** A is BLOCKING for B+C (migration + audit contract); B+C are functionally independent but share files (cli/schwab.py + integrations/schwab/mappers.py — sequential B→C avoids merge conflicts trivially); D is BLOCKING on all three (E2E + handoff).

### Schema posture decisions (§C)

- **Migration 0018:** single atomic file with explicit `BEGIN;` / `COMMIT;` discipline. Creates `schwab_api_calls` table (14 columns + 4 CHECK enums + 4 indexes + 3 FKs `ON DELETE SET NULL`). ALTERs: `account_equity_snapshots ADD COLUMN schwab_account_hash TEXT NULL` (Q16 forward-prep multi-account); `reconciliation_runs ADD COLUMN schwab_api_call_id INTEGER NULL REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL`. UPDATE schema_version 17→18.
- **EXPECTED_SCHEMA_VERSION bump:** 17 → 18 (T-A.7 implements).
- **Backup gate:** does NOT auto-fire for 17→18 (R1 Major #1 corrected — existing gate is version-specific to 13→14/15→16/16→17). **Operator-manual backup recommended per §I.1 cycle-checklist update** before first `swing db-migrate` lands 0018.
- **CHECK enums already permit `'schwab_api'`** (Phase 9 Sub-bundle B + C foresight): `reconciliation_runs.source` line 194 + `account_equity_snapshots.source` line 332 of migration 0017. NO ALTER on either CHECK enum needed.

### Market-data ladder persistence shape decision (V1 INCLUDE branch per Q11)

**Shape A LOCKED** (parquet-per-(ticker, provider)) per spec §3.8.2 default. Justification: cleanest separation; no SQL migration for OHLCV path; resolver code is small (~50 LOC merge); per-provider files operator-greppable; matches Phase 9 source-ladder pattern. Downstream impact: filename change `{TICKER}.parquet` → `{TICKER}.{PROVIDER}.parquet`; new `resolve_ohlcv_window(ticker, start, end)` resolver; `PriceCacheEntry` gains `provider` field DISTINCT from existing `source` TTL-state field; backward-compat handles 4 cases including both-files-exist via MERGE-AND-QUARANTINE.

### Q1-Q18 disposition wiring + plan §D Task 0.b items

**ZERO open questions for orchestrator triage.** All 18 dispositions (Q1-Q18) wired through plan §A.1 + §A.2 acceptance criteria. The 6 §D entries are operator-paired Task 0.b live verification items (NOT open questions for the orchestrator):

- §D.1 Q8 sandbox-vs-production HTTP-layer differentiation (base URL / path / scope / TTL).
- §D.2 Q12 premium-tier Schwab Market Data endpoint access vs operator's actual subscription tier.
- §D.3 Q13 residual paste-back UX verification.
- §D.4 Q14 OAuth scope-string composition (default `readonly`; verify exact format).
- §D.5 Q15 refresh-token rotation behavior.
- §D.6 Q17 Market Data API rate limits independent of Trader API.

These BLOCK each downstream sub-bundle dispatch until completed (operator-paired live verification).

### Three highest-leverage plan decisions (return report §3)

1. **Migration 0018 explicit `BEGIN;`/`COMMIT;` discipline at the SQL file level** — corrects the misreading of CLAUDE.md's `executescript()` gotcha; future migrations 0019+ MUST mirror this discipline until the runner is updated.
2. **Three-layer token redactor with `logging.setLogRecordFactory()` (NOT `logging.Filter`)** — corrects a fundamental Python logging misunderstanding (filters on ancestor loggers do NOT fire during propagation); the factory approach catches records at creation time regardless of which logger emits or which handler captures, covering pytest caplog + third-party handlers + lazily-created schwabdev sub-loggers.
3. **Production-only domain writes gating matrix across 5 distinct surfaces** — Trader API call-with-audit-no-domain in sandbox; market-data pipeline SKIPs Schwab entirely in sandbox; `--verify-marketdata` env-independent. Prevents sandbox responses from poisoning production metrics via the source-ladder.

### Inherited disciplines from Phase 9 + Phase 10 + Finviz (per return report)

- Source-ladder consumer (no re-design): §A.4 enumerates verbatim consumption; new `run_schwab_reconciliation()` service mirrors `run_tos_reconciliation` shape; reuses Phase 9 Sub-bundle B `MATERIAL_BY_TYPE` lookup.
- Service-layer transaction discipline: §A.9 #2 + §H.4.1 step 8d combined-tx2 + new audit service `link_snapshot_and_stamp_account_hash` all OWN BEGIN IMMEDIATE; REJECT caller-held tx.
- Token redaction layering: §G.3 cassette filters + §H.8 three-layer redactor (Layer 0 known-value exact-replace; Layer 1 heuristic regex; Layer 2 setLogRecordFactory wrapper with thread-local recursion guard + ensure_* re-install defense).
- Server-stamping: §A.9 #4 + §H.1 setup + §H.2 refresh.
- USERPROFILE+HOME monkeypatch: §A.9 #8 covers BOTH user-config.toml write path AND schwabdev Tokens DB path resolution.
- Session-anchor read/write alignment: §A.9 #9 uses `last_completed_session(now())` matching Phase 10 capital-friction read predicate.

### Brief deviations from dispatch brief (per return report; ONE flagged)

- Brief §0.7 estimated "Likely Sub-bundle D: Audit trail + observability + `swing schwab status`". Plan FOLDS audit-infra into Sub-bundle A (must land before B+C consume) + leaves status-full-surface in Sub-bundle D-polish. Justified: A must land the audit-row contract that B+C consume; splitting it from B+C would require A to ship a stub-only audit and then re-touch A's files during D, breaking file-isolation discipline. Acceptable deviation; orchestrator concurs.

### Operator-attention items (per return report)

- **`schwabdev>=2.4.0,<3.0.0` version pin** synthesized; T-A.1 pins exact version + verifies method signatures match §E at Task 0.b. Operator-actionable verification item.
- **6 deferred Task 0.b verification items** enumerated in plan §D — operator-paired live verification BLOCKS each sub-bundle dispatch until completed (Q8 + Q12 + Q13-residual + Q14 + Q15 + Q17).
- **Operator-manual DB backup** before first `swing db-migrate` run that lands 0018 (no auto-gate fires per §C.5; cycle-checklist update covers).
- **NO CLAUDE.md gotchas promoted YET** — plan §J.1-§J.6 enumerate 6 entries that Bundle D T-D.4 will land at executing-plans time.

### Operator-provided distilled Schwab API references (tracked at `reference/schwab-api/`)

Operator created 2026-05-13 via parallel instance: 4 distilled markdown files derived from saved Schwab Developer Portal HTML pages (raw HTML at `reference/SchwabAPI/`, gitignored as bulk reference per same posture as `reference/Books/`). The distilled MDs are tracked + small + canonical:

- `reference/schwab-api/account-documentation.md` — Trader API account/order/transaction documentation digest.
- `reference/schwab-api/account-specification.md` — Trader API account/order/transaction OpenAPI / response-shape specification.
- `reference/schwab-api/market-data-documentation.md` — Market Data API quotes/pricehistory documentation digest.
- `reference/schwab-api/market-data-specification.md` — Market Data API OpenAPI / response-shape specification.

**Orchestrator action item — BINDING for ALL future Schwab API executing-plans dispatch briefs (Sub-bundle A through D):** include `reference/schwab-api/` in the brief's §0 reads list. These distilled references are HIGHER-FIDELITY than the synthesized §E endpoint catalog in the spec/plan because they're derived directly from Schwab's published documentation. **Implications for Task 0.b verification gates:**

- May materially reduce operator-paired live verification burden for Q8 (HTTP-layer differentiation: base URL / path / scope), Q14 (OAuth scope-string composition), Q17 (Market Data API rate limits), and the §E synthesized endpoint shapes flagged with `[VERIFY]` tags.
- Implementer should consult `reference/schwab-api/` FIRST during Task 0.b — many `[VERIFY]` items may already be answered in the distilled references; only items NOT covered need live API verification.
- Spec + plan §E + §D do NOT cite these references (operator created them after writing-plans shipped). The executing-plans dispatch briefs are the right surface to thread them in.

**Plan + spec amendment posture:** spec §E + plan §E + plan §D §D.1-§D.6 may benefit from a future amendment-pass to cite the distilled refs explicitly. Operator-paced; not blocking executing-plans dispatch (the executing-plans brief threading + Task 0.b runbook update is sufficient).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Writing-plans dispatch brief: `docs/schwab-api-writing-plans-dispatch-brief.md` (`5bf425d` + `9fd50e6` COA B amendment).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **Operator-provided Schwab API distilled references:** `reference/schwab-api/{account,market-data}-{documentation,specification}.md` (4 files).
- Sub-bundle A executing-plans dispatch brief: TBD (orchestrator drafts; operator-paced).

### Next dispatch

**Sub-bundle A executing-plans dispatch UNBLOCKED.** Operator-paced. Orchestrator drafts the executing-plans brief when operator commissions. Plan §K T-A.0.b runbook covers the operator-paired Task 0.b live API verification gate that blocks Sub-bundle A dispatch start. **`reference/schwab-api/` distilled refs go into the dispatch brief's §0 reads + may pre-answer several §D items** (orchestrator pre-checks at draft time).

**Threading reminder:** review-form polish task (per phase3e-todo entry "Trade exit review form — stale Phase 7 will auto-derive promise") goes into Sub-bundle D's executing-plans dispatch brief at draft time per operator-locked 2026-05-13 disposition.

---

## 2026-05-13 Schwab API Q18 build-vs-buy disposition LOCKED — COA B = `schwabdev`

**Brainstorm-spec gap surfaced post-triage.** The 2026-05-13 brainstorm spec at `585556f` implicitly chose COA C (roll our own) by enumerating `swing/integrations/schwab/` sub-package + `SchwabClient` + sidecar JSON token storage + custom file-lock + custom OAuth flow as the V1 architecture, **without ever explicitly comparing against the two community-maintained Python wrappers it lists in §12 references** (`schwab-py`, `schwabdev`). Operator surfaced the gap immediately after orchestrator drafted the writing-plans dispatch brief at `5bf425d`; orchestrator researched both libraries' OAuth implementations + presented tradeoff matrix; operator confirmed COA B on 2026-05-13.

### Three-way comparison (orchestrator research findings)

Library OAuth + token-handling implementation comparison (sourced from `alexgolec/schwab-py:schwab/auth.py` + `tylerebowers/Schwabdev:schwabdev/{client,tokens}.py` direct fetch):

| Dimension | schwab-py (COA A) | schwabdev (COA B) | Wins |
|---|---|---|---|
| Storage | JSON file; **no atomicity** (raw `open(..., 'w')`) | SQLite with `BEGIN EXCLUSIVE` transaction; atomic replacement across processes | **schwabdev** — matches our spec §3.2.4 file-lock intent with stronger semantics |
| Refresh strategy | Lazy only (authlib-driven) | Hybrid: lazy per-request `update_tokens()` + proactive async `_checker()` every 30s | **schwabdev** — matches spec §3.2.3 design intent exactly |
| Safety margin | 300s leeway (authlib `leeway=300`) | 61s access threshold + 3630s refresh threshold (separate tracking; tunable) | **schwabdev** — explicit + testable thresholds |
| Refresh-token rotation | Opaque passthrough (whatever authlib gives the callback) | Explicit `if new_refresh_token: self.refresh_token = new_refresh_token` + immediate persist | **schwabdev** — explicit handling simplifies spec Q15 verification |
| Concurrency | **None** (no file locks, no thread locks) | `threading.RLock` (in-process) + SQLite `BEGIN EXCLUSIVE` (cross-process) | **schwabdev** — solves spec §3.2.4 file-lock requirement out of box |
| Encryption at rest | Not visible | Optional Fernet cipher (operator provides 32-byte URL-safe base64 key; `enc:` prefix in DB) | **schwabdev** — spec Q2 V2 hardening optionally available V1 |
| Callback flow | Both: localhost (Flask listener) + paste-back fallback + Jupyter auto-detect | Paste-back only (with optional `webbrowser.open()`) | **schwab-py** — both modes; schwabdev requires paste-once at setup |
| Token logging audit | `register_redactions(token)` registered after fetch (extent unclear beyond fetched code) | No tokens logged directly; one caveat: `tokens.py:~338` logs `response.text` on auth failure (could include token-related error details) | schwab-py has explicit redaction call site; both need our wrapping audit |
| Maturity | ~1.5k stars; Alex Golec's tda-api lineage; battle-tested | Newer; smaller community; less battle-tested | **schwab-py** — wider user base |

**Streaming use case clarification:** Both libraries support Schwab's WebSocket streaming API. Per community consensus, streaming is primarily a day-trading feature (low-latency tick data, Level-I/II order books, real-time order push notifications). For this project's daily-pipeline-cadence swing trading, streaming is V2-deferrable (Q4 disposition: V1 batch-poll). Neither library forecloses streaming — both make it available if V2 wants intraday position monitoring or real-time stop-violation alerts.

### LOCKED disposition: COA B (schwabdev)

Operator decision rationale: spec §3.2.2-3.2.4 design intent (atomic storage + cross-process locking + hybrid refresh + explicit rotation handling) is exactly what schwabdev already ships. Re-implementing those from scratch in COA C is high implementation risk for security-critical OAuth code; using a library where the maintainer cares about exactly the right details + has SQLite-backed atomic storage is more defensible than rolling our own. COA A's wider community is offset by COA A's design gaps (no concurrency protection; opaque rotation; lazy-only refresh).

**Tradeoff accepted:** schwabdev's paste-only callback flow (no localhost listener) — operator pastes once at `swing schwab setup` per env, never again. Spec Q13 disposition simplifies to paste-back V1; localhost listener becomes V2 candidate if operator surfaces friction post-V1.

### Spec sections SUPERSEDED by COA B

Per writing-plans dispatch brief §0.3a (commit `<post-COA-B-update>`): plan author re-derives in plan §A or §H —

- §3.1 module layout: still `swing/integrations/schwab/` sub-package; now thin wrapper around `schwabdev.Client`.
- §3.2.1 setup flow: paste-back only V1 (was both modes).
- §3.2.2 token storage: per-environment SQLite DB at `%USERPROFILE%/swing-data/schwab-tokens.{sandbox,production}.db` (was JSON sidecar).
- §3.2.3 refresh strategy: schwabdev's hybrid lazy + proactive 30s `_checker()` + 61s/3630s thresholds (better than spec).
- §3.2.4 concurrency: schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` (custom file-lock shim NOT NEEDED).
- §3.3.1 + §3.3.2 endpoint catalogs: call schwabdev `Client` methods (`account_details`, `account_orders`, `transactions`, `quotes`, `price_history`); raw HTTP details deferred to schwabdev docs.
- §3.5 CLI subcommand bodies: wrap schwabdev's auth flow (paste-back) + `update_tokens(force_refresh_token=True)`.
- §5 token redaction: cassette discipline + DEBUG-log suppression context manager STILL apply; sentinel-token-leak audit STILL required + extends to verifying schwabdev's loggers don't leak (one known caveat: `tokens.py:~338` `response.text` on auth failure).
- §10 Q2 token encryption: optional Fernet now AVAILABLE V1 if operator wants (default V1 plaintext per spec disposition; operator may elect Fernet at writing-plans review).
- §10 Q13 callback localhost vs paste: paste-only V1 (schwabdev constraint; operator confirmed acceptable).
- §10 Q15 refresh-token rotation: schwabdev handles explicitly; Task 0.b verification simplifies to "observe rotation behavior + record one cassette per case."

### Spec sections UNAFFECTED by COA B

- §3.4 pipeline integration architecture (steps + ordering + failure tolerance + `SchwabPipelineActiveError`).
- §3.6 audit trail (`schwab_api_calls` table + INSERT/UPDATE lifecycle).
- §3.6.2 audit-write surface boundary.
- §3.6.3 production-only domain writes.
- §3.7 source-ladder write path.
- §3.8 market-data ladder design (V1 INCLUDE branch).
- §4 schema candidates (`schwab_api_calls` table + ALTERs).
- §6 failure-mode catalog.
- §7 operator setup flow + cycle-checklist.
- §9 watch items.

### Plan-scope impact

- New runtime dependency: `schwabdev>=<version>` added to `[project.dependencies]` (NOT dev-extras).
- Sub-bundle scopes shrink relative to spec §0.7 estimate — Sub-bundle A no longer designs OAuth from scratch; auth + token storage become "wrap schwabdev's `Tokens` class with our gotcha discipline."
- Plan §B file map removes the file-lock module (no longer needed).
- New plan §K verification gate: schwabdev's own logger output verified token-redaction-safe at integration-test level.

### Brief-template improvement candidate (orchestrator-side learning)

Future brainstorm dispatch briefs for any "integrate external system X" scope MUST include an explicit build-vs-buy question (Q18-equivalent) in §1 strategic-context OR §2 brainstorm scope. The Schwab brainstorm brief silently assumed "we'll roll our own per Finviz precedent" without surfacing the question. The Finviz precedent itself was COA C because no Finviz Elite Python wrapper existed at brainstorm time; Schwab has TWO mature wrappers + the question deserved first-class treatment. Brief author (orchestrator) caught this only after operator pushback post-brainstorm.

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Writing-plans dispatch brief (updated with §0.3a Q18 disposition): `docs/schwab-api-writing-plans-dispatch-brief.md` (`<post-COA-B-update>`).
- schwabdev source consulted: `tylerebowers/Schwabdev:schwabdev/{client,tokens}.py` (raw GitHub fetch via WebFetch 2026-05-13).
- schwab-py source consulted: `alexgolec/schwab-py:schwab/auth.py` (raw GitHub fetch via WebFetch 2026-05-13).

### Next dispatch

**Operator-paced.** Writing-plans dispatch brief now reflects Q18 = COA B; operator dispatches when ready.

---

## 2026-05-13 Schwab API integration brainstorm SHIPPED — 939-line spec + 17 open questions for orchestrator triage (operator-paced)

**Brainstorm SHIPPED 2026-05-13** at `585556f` (single commit on main; `docs(schwab-api): integration brainstorm spec`). Operator-dispatched implementer per orchestrator-drafted brief at `c4252d3` (`docs/schwab-api-brainstorm-dispatch-brief.md`, 390 lines). Spec at `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (939 lines; within 600-1100 brief budget).

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/10M/5m → R2 0C/6M/3m → R3 1C/3M/2m → R4 0C/2M/2m → R5 0C/0M/0m); cumulative 1C + 21M + 12m all RESOLVED inline; **ZERO ACCEPT-WITH-RATIONALE banked** — matches Phase 10 cleanest-arc precedent. Terminated within MAX_ROUNDS=5; no operator-override past default needed.

### Three highest-leverage design decisions

1. **§3.6.3 production-only domain writes (R3 Critical resolution).** `cfg.integrations.schwab.environment` gates `record_snapshot()` + `run_schwab_reconciliation()`; sandbox is verification-only (audit rows written; ZERO domain rows; market-data ladder short-circuits). Prevents synthetic Schwab data from winning the source-ladder (Schwab is precedence 0) and silently contaminating Phase 10 metrics + reconciliation discrepancies + cohort analysis. **Critical-class find Codex R3 surfaced; brief did not anticipate.**
2. **§3.8 market-data ladder rewrite scope honestly enumerated for writing-plans.** Brief recommended V1 INCLUDE (per operator §1.9 preference); spec writes the INCLUDE branch. Honestly admits current `PriceCache`/`OhlcvCache` do NOT have multi-source semantics today. Writing-plans picks persistence shape A (parquet-per-(ticker, provider)) / B (SQLite table) / C (provider column inside parquet). Default recommendation: A.
3. **§3.6.2 audit-write surface boundary.** Pipeline + CLI surfaces SYNCHRONOUS audit; web-page-render path is EXPLICITLY-UNAUDITED V1 (logs-only). Prevents SQLite contention from web cache misses + cardinality explosion. V2 candidates (batched-summary writer; `/admin/schwab-counters` debug endpoint) enumerated.

### Auth + token storage decisions LOCKED in spec

- **Initial-setup flow:** two first-class variants — `--callback localhost` default (one-shot HTTPS listener on 127.0.0.1:8765 with self-signed cert) + `--callback paste` V1 IF Task 0.b verifies one of three OOB mechanisms; else DROPPED V1.
- **Token storage:** per-environment sidecar JSON file at `%USERPROFILE%/swing-data/schwab-state.{sandbox,production}.json` — NOT user-config.toml.
- **Refresh strategy:** lazy-on-first-API-call with 60s proactive safety margin; file-lock on sidecar during refresh.
- **Encrypted at rest:** V1 plaintext, disclosed as **HIGHER-RISK deviation from Finviz precedent** (client_secret + long-TTL refresh_token co-stored). V2 hardening (`keyring` / DPAPI) promoted to high priority (§10 Q2).
- **Active env selection:** `cfg.integrations.schwab.environment` is SoT (default production); CLI `--environment` override per-invocation; pipeline cfg-only.
- **Revocation:** `swing schwab logout` revokes via Schwab endpoint + atomically renames sidecar to `schwab-state.{env}.json.deleted-<ts>` + unlinks.

### Pipeline integration LOCKED

- **New steps:** `_step_schwab_snapshot` + `_step_schwab_orders` (two new pipeline steps). Market-data path is NOT a separate step; integrated into `_step_evaluate`/`_step_charts` cache fetch boundaries.
- **Step ordering:** AFTER `_step_recommendations`, BEFORE `_step_charts` (briefing-includes-Schwab-data + charts-can-feed-back-on-stop-drift).
- **Failure tolerance:** continue-with-error (mirror Finviz precedent at `swing/pipeline/runner.py:285-294`).
- **CLI surface:** `swing schwab {setup, refresh, fetch [--snapshot|--orders|--all|--verify-marketdata], status, logout}`.
- **Concurrency:** `SchwabPipelineActiveError` hard exclusion for `fetch --snapshot/--orders/--all` (UPSERT-provenance race + INSERT-only duplication); `logout`/`setup` refused unless `--force`; `refresh`/`status` concurrent-safe (sidecar file-lock handles refresh).

### Schema candidates DEFERRED to writing-plans

- **New table:** `schwab_api_calls` (14 columns enumerated in spec §4.1).
- **ALTER candidates:** `account_equity_snapshots.schwab_account_hash TEXT NULL` (V1 ADD per §10 Q16 default; forward-prep multi-account V2); `reconciliation_runs.schwab_api_call_id INTEGER NULL` (FK candidate).
- **Market-data persistence:** writing-plans picks Shape A/B/C per §3.8.2 (default A: parquet-per-(ticker, provider) — no new SQL table).
- **EXPECTED_SCHEMA_VERSION bump:** 17 → 18 (driven by `schwab_api_calls` + ALTERs; Shape B would also drive a bump from market-data side).

### 17 open questions for orchestrator triage (operator-paced)

Orchestrator-grouped by triage urgency for operator review:

**A. Operator-decide-NOW (impacts writing-plans scope; 4 items):**
- Q1: Schwab Developer Portal app status — **OPERATOR-CONFIRMED 2026-05-13: production-tier approval already in hand.** Updated disposition: production-only V1; sandbox registration deferred to Task 0.b (operator decides at executing-plans whether sandbox cassette-recording adds value — depends on whether Schwab requires distinct sandbox app registration vs unified credentials, which Task 0.b verifies).
- Q3: Multi-account support — orchestrator default: V1 single-primary-account; V2 multi-account.
- Q11: Market-data ladder V1 INCLUDE vs EXCLUDE — orchestrator default: **V1 INCLUDE** (operator-flagged at brief time; spec writes INCLUDE branch).
- Q6: Schwab inception-CSV ingestion — orchestrator default: **separate dispatch** (per phase3e-todo 2026-05-12 entry; keep this arc focused).

**B. Operator-confirm-defaults (orchestrator-can-take; 6 items):**
- Q2: Token encryption — V1 plaintext (Finviz precedent + risk disclosed; V2 keyring/DPAPI = high-priority hardening).
- Q5: Operator UI — V1 CLI-only.
- Q7: TOS CSV deprecation — stays as V1 fallback.
- Q9: Cash-basis manual snapshot retention — yes (source-ladder resolves at read time).
- Q10: Pipeline step ordering — after `_step_recommendations`, before `_step_charts` (architectural).
- Q16: `account_hash` column on `account_equity_snapshots` — V1 ADD (NULL-permissible; forward-prep multi-account; cheap insurance).

**C. Defer-to-Task-0.b live verification (5 items; operator-paired at executing-plans):**
- Q4: Streaming vs batch-poll — V1 batch-poll; V2 streaming.
- Q8: Sandbox vs production HTTP-layer differentiation (per-env sidecar LOCKED; HTTP-layer base URL / path / scope / TTL OPEN).
- Q12: Premium-tier Market Data endpoint access (default: V1 default-tier delayed quotes).
- Q13: OAuth callback localhost vs paste — localhost default + `--paste` flag fallback if Task 0.b reveals env block.
- Q14: OAuth scope-string composition — synthesize default; live-verify exact format.
- Q15: Refresh-token rotation behavior — design handles both rotate-every and rotate-near-expiry; cassette+test fixtures need known canonical case from operator-witnessed verification.
- Q17: Market Data API rate limits independent of Trader API — synthesized "~Trader API limits or looser"; flag Task 0.b verification.

(Note: Q14 + Q15 + Q17 are 3 of the 5 in C; total = Q4+Q8+Q12+Q13+Q14+Q15+Q17 = 7 items — orchestrator counts 5+7+4 = 16 not 17 due to Q4 fitting both B confirm + C verify; numerically 17 questions total.)

### Inherited disciplines from Finviz precedent (verbatim)

- urllib3 + requests-bundled-urllib3 DEBUG-log suppression context manager (`_suppress_transport_debug_logs`).
- Cassette `filter_headers=['authorization']` + EXTENDED `filter_query_parameters=['code', 'refresh_token', 'client_id', 'client_secret', 'redirect_uri', 'access_token']` + `filter_post_data_parameters` + custom body redactor for token/secret substrings.
- Sentinel-token-leak audit test pattern (`tests/integrations/test_schwab_token_redaction_audit.py`).
- Exception `__str__` no-token contract on every Schwab exception class.
- CLI vs pipeline concurrency exclusion via `SchwabPipelineActiveError` — INHERITED from Finviz's `FinvizPipelineActiveError` (V1 decision REVERSED implementer's R1 initial framing per brief watch-item #17 reversal; R2 Major-3 surfaced UPSERT-provenance race + reconciliation_runs INSERT-only duplication risk — **brief watch-item #17 was technically violated by final design BUT the rationale is Codex-discovered + documented**).
- Single-retry-on-429 semantics with `Retry-After` cap at 30s.

### Capture-needs feedback

- For Phase 6/7/8/9/10: **None.** All consumer surfaces already in place (Phase 9 source-ladder + Phase 10 metrics consume transparently; capital-friction LIVE badge gap closes automatically).
- **For writing-plans dispatch (12 firm-up items):** §3.3.1 endpoint shapes via Task 0.b; §3.3.1 scope strings via Task 0.b; §3.5 CLI subcommand body design; §3.6 `schwab_api_calls` DDL; §3.2.4 file-lock cross-platform shim; §3.2.1 callback HTTPS-vs-HTTP; §7 cycle-checklist updates; test fixtures + Task 0.b runbook; integration test E2E mirroring Phase 9 Sub-bundle E pattern; market-data persistence shape A/B/C choice; account_hash column V1/V2; `schwab_account_hash` + `reconciliation_runs.schwab_api_call_id` ALTERs.

### Brief deviations flagged for orchestrator awareness

1. **Amended single commit instead of one-shot commit at end of all rounds.** Brief §4 listed "no amending" alongside "single commit ... no rogue commits" — orchestrator-author-side phrasing was internally contradictory because Codex iteration produces multiple rounds of fixes that must all land in ONE commit. Implementer committed prematurely at R0 (`da30045`) before adversarial loop, then amended through R1-R5 fixes; final SHA `585556f`. Local-only history (no push); does not violate published-commit safety the "no amending" guard targets. **Brief-template improvement to orchestrator-side authoring:** future brainstorm-dispatch briefs should phrase as "defer commit until all Codex rounds complete + commit once at end" — explicit prescription removes the apparent conflict between "single commit" and "no amending."
2. **Brief watch-item #17 reversed during R2 (NORMAL TRIAGE FLOW; not a special case).** Initial spec at R0 followed brief watch-item recommendation (no hard exclusion; file-lock-only). R2 Major-3 surfaced UPSERT-provenance race (snapshot UPSERT preserves PK but overwrites `source_artifact_path` + audit row pointing to the OTHER writer's call_id — real audit-trail integrity break) + reconciliation_runs INSERT-only duplication risk. Implementer reversed to "HARD exclusion via `SchwabPipelineActiveError` on `fetch --snapshot/--orders/--all`" + escalated via return-report deviation note. **Triage outcome: orchestrator ACCEPTS reversal (rationale is sound; UPSERT-provenance race is real; final design correctly inherits Finviz precedent).** This is the elevation-via-return-report flow operating as designed — Codex catches brief-author errors + implementer surfaces them + orchestrator dispositions at triage. Not a "lesson" to bank; the system is doing what it's supposed to.

### Cross-references

- Brainstorm dispatch brief: `docs/schwab-api-brainstorm-dispatch-brief.md` (`c4252d3`).
- Spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Closest API integration precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (Finviz; merged `002338a`) + `swing/integrations/finviz_api.py`.
- Source-ladder consumer (binding inheritance per spec §3.7): `swing/data/repos/account_equity_snapshots.py:_SOURCE_PRECEDENCE` + `get_latest_snapshot_on_or_before(with_provenance=True)`; `swing/trades/account_equity_snapshots.py:record_snapshot`.
- Spec format precedent: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines).
- Post-Phase-10-close handoff: `docs/orchestrator-handoff-2026-05-13-schwab-api.md`.

### Next dispatch

**Operator-paced.** Triage 17 open questions (C-bucket items can defer to Task 0.b at executing-plans; A+B-bucket items decide-now-or-rubber-stamp orchestrator defaults). Once triage complete, orchestrator dispatches Schwab API writing-plans via separate brief.

---

## 2026-05-13 Post-Phase-10 infrastructure bundle SHIPPED — cleanup-script `-DeregisterFirst` + pytest-xdist baseline (6.56× speedup)

**Bundle SHIPPED 2026-05-13** at `27ce96f` (integration merge of `post-phase10-infra-bundle`). 5 commits = 3 task-impl (T-2 + T-3 + T-6) + 1 Codex-fix (R1 Critical #1 confirm-before-deregister) + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR**. ZERO ACCEPT-WITH-RATIONALE. **ZERO production code touched** (binding lock from dispatch brief §0; read-side / infrastructure-only).

Tests: 3255 → 3283 worktree-side (+28 net). Ruff 18 unchanged. Schema v17 unchanged.

### Key deliverables

**1. `cleanup-locked-scratch-dirs.ps1` `-DeregisterFirst` switch** (default OFF; opt-in):
- Pre-pass scans `git worktree list` for paths matching `^.+\.worktrees[\\/]+phase\d+.*` OR `^.+\.claude[\\/]+worktrees[\\/]+phase\d+.*`.
- Presents candidate list to operator + prompts for confirmation BEFORE invoking `git worktree remove --force` (R1 Critical #1 defense-in-depth gate).
- After deregister loop, existing orphan-discovery pass picks up resulting orphans.
- Safety filter: BINDING regex strict `phase\d+-*` prefix; rejects non-matching branches.
- `test_safety_filter_rejects_own_worktree_explicitly` pins that `post-phase10-infra-bundle` itself is REJECTED.
- DryRun compatibility preserved.

**2. pytest-xdist baseline integration:**
- Added `pytest-xdist>=3.5.0` to `[project.optional-dependencies].dev`.
- Configured `[tool.pytest.ini_options].addopts = "-n auto"` (operator override via `-n 0` / `-n logical` / `-n N`).
- All 3283 tests pass under `-n auto` across 3 independent runs (zero xdist-unsafe state-leak failures).

### Measurement (BINDING per dispatch brief §0.7)

- Serial baseline: **415.17s** (3255 tests).
- Parallel median (`-n auto`; 3 runs): **63.24s** (3276 tests; #1 60.82s, #2 76.07s, #3 63.24s).
- **Speedup ratio: 6.56×** (well above 2× minimum + 3-5× projection).
- Post-R1-fix final sweep: 60.96s at 3283 tests + 5 skipped + 3 pre-existing fails.

### T-1 recon findings + conditional-task disposition

**T-4 (session-scoped schema fixtures) SKIPPED:**
- `ensure_schema` NOT in `--durations` top-30 (called 254 times but aggregate <0.3% of serial baseline).
- Risk asymmetry: migration tests + rollback-semantics tests + pre/post-v17 ratify tests would silently break if schema state shared across tests.

**T-5 (TestClient lifespan audit) SKIPPED:**
- Lifespan footprint is microsecond-level (`ThreadPoolExecutor` constructor + `shutdown(wait=False)`).
- Top-30 cost is route-execution time, NOT lifespan startup.
- Audit cost (per-test app.state reachability analysis) exceeds savings.

Both remain backlog-eligible if operator surfaces a specific hotspot later.

### 5 deviations from brief (none require V2.1 §VII.F)

1. §6.1 — 1+3 serial+parallel readings instead of 3+3 (6.56× speedup unambiguous from one baseline + three readings).
2. §6.2 — Python-side tests reading `.ps1` source (NOT PowerShell Pester); 26 admit/reject corpus tests + 5 source-invariants at zero PowerShell infrastructure cost.
3. §6.3 — `-n auto` in addopts default (NOT opt-in via CLI); matches operator's stated goal.
4. §6.4 — integration test file created (was optional per brief).
5. R1 Critical #1 — confirm-before-deregister gate added in `cdea854` (not in brief; surfaced by Codex as defense-in-depth for the new destructive surface).

### Operator-witnessed gate S2 PENDING

Elevated PowerShell run of `-DeregisterFirst` against the 7 pre-merge husks + 1 new infra-bundle orphan = **8 husks to clear**. Operator-driven — orchestrator surfaces to operator post-merge for plain-chat authorization. Run:

```powershell
cd c:\Users\rwsmy\swing-trading
.\cleanup-locked-scratch-dirs.ps1 -DeregisterFirst
```

### Cross-references

- Return report: `docs/post-phase10-infra-bundle-return-report.md`.
- Dispatch brief: `docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md`.
- Cleanup script: `cleanup-locked-scratch-dirs.ps1` (extended with `-DeregisterFirst` switch).

### Next dispatch

Post-bundle handoff to NEW ORCHESTRATOR INSTANCE for Schwab API integration (multi-day brainstorm + writing-plans + executing-plans cycle). Operator-decided sequencing.

---

## 2026-05-13 Phase 10 Sub-bundle E ship: CLOSES Phase 10 — arc closer aggregate

**Sub-bundle E SHIPPED 2026-05-13** at `38dbac3` (integration merge of `phase10-bundle-E-process-grade-trend-and-polish`). 8 commits = 6 task-impl (T-E.1..T-E.6 + T-E.4 closer) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (matches Sub-bundle B + C + Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3147 worktree-side → 3254 (+107 net; ~3257 main HEAD post-merge). Ruff 18 unchanged. Schema v17 unchanged.

**Cross-bundle T-A.7 pin UN-SKIPPED at T-E.3 SAME COMMIT** (`fb6e48a`) — `test_existing_dashboard_vm_has_unresolved_material_field` no longer carries `@pytest.mark.skip` decorator + passes against retrofitted DashboardVM. Plan §H named 6 base-layout VMs to retrofit; implementation retrofitted **10** (defense-in-depth catching 4 additional VMs that extend base.html.j2 per CLAUDE.md gotcha — ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM).

### 7-surface operator-witnessed gate ALL PASS via Chrome MCP on port 8081

- **S1 inline** pytest+ruff+verify_phase10 PASS at 3254 tests.
- **S2** `/metrics/process-grade-trend` PASS — spec §4.8 reference + numeric encoding A=4..F=0 visible per lesson #19 + N=10 window + 3 closed-reviewed trades + 7-metric Class column per §A.21 matrix; all 7 metrics suppressed at n=3<5 per spec §5.4; ZERO console errors.
- **S3 banner FIRES** PASS — planted discrepancy id=1 (DHC #2 stop_mismatch material) → dashboard shows §A.18 banner "1 unresolved material reconciliation discrepancy" + "Resolve via CLI" CLI hint.
- **S4 banner CLEARS** PASS — reverted discrepancy to acknowledged_immaterial → banner absent from DOM; count=0 restored.
- **S5** `/metrics` umbrella PASS — 8 tile descriptions verified.
- **S6 T-E.5 form POST** PASS — `equity_dollars=2000` + note "S6 gate test 2026-05-13" submitted via curl (form_input + computer click did not trigger HTMX events; curl with HX-Request header reproduced operator browser submit semantics) → HTTP 204 + `HX-Redirect: /metrics/capital-friction` per Phase 5 R1 M2 LOCK; snapshot #3 created in DB with server-stamped `snapshot_date='2026-05-13'` per lesson #4 + Phase 8 server-stamping discipline; HX-Redirect target resolves to capital-friction with LIVE badge $2000.00; multi-run trend shows $1800 → $2000 transition by date correctly; ZERO console errors.
- **S7 T-E.6 trade detail indicator** PASS — DHC #2 with planted discrepancy shows "⚠ Unresolved reconciliation discrepancy (1)" at top per electives §2 Task E.6 acceptance; after revert, indicator section hidden entirely per "hide when empty" rule.

### Production state post-gate

- Snapshot #3 left in production as valid operator cash-basis reading per dispatch brief §7 #11 default (operator can update via CLI any time).
- Discrepancy id=1 reverted to `acknowledged_immaterial` with reason "post-S3/S4/S7 gate cleanup 2026-05-13".
- 30 reconciliation_discrepancies all resolved (production state restored).

### Phase 10 arc closer aggregate (return report §9)

| Sub-bundle | Commits | Codex rounds | Tests delta | Critical-resolved | Major-resolved | ACCEPT-WITH-RATIONALE | CLAUDE.md gotchas |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 15 | 4 | +128 | 0 | 3 | 0 | 0 |
| B | 9 | 2 | +73 | 0 | 2 | 0 | 0 |
| C | 8 | 2 | +84 | 0 | 2 | 0 | 0 |
| D | 12 | 3 | +102 | 0 | 5 | 0 | 0 |
| E | 8 | 2 | +107 | 0 | 1 | 0 | 0 |
| **Total** | **52** | **13** | **+494** | **0** | **13** | **0** | **0** |

**Phase 10 closer highlights:**

- **52 commits across A+B+C+D+E** (34 task-impl + 12 Codex-fix + 5 return-reports + 1 ruff).
- **13 Codex rounds total** (4+2+2+3+2).
- **+494 cumulative fast tests** (final 3254 worktree-side / ~3257 main HEAD; from pre-Phase-9 baseline 1957 → +1297 across Phase 9 + Phase 10).
- **ZERO Critical findings entire arc.**
- **ZERO ACCEPT-WITH-RATIONALE banked** — **cleanest 5-bundle arc-final state in project history.** Phase 9 had 4 banked (2 A + 1 B-later-resolved-C + 1 C; D + E clean).
- **ZERO CLAUDE.md gotchas promoted** — every defect class hit during Phase 10 was already covered by existing gotchas. Phase 9 promoted 6.
- **27 V2.1 §VII.F amendments pending** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 + 3 elsewhere). See T-E.4 "Phase 10 closer" section near end of file for full enumeration.
- **3 post-Phase-10 standalone dispatches unblocked** (cleanup-script `-DeregisterFirst` + test-runtime xdist + §8.4 Corporate_Actions MVP).
- **§A.0 ZERO-new-schema LOCK preserved** through entire arc — schema v17 unchanged through Phase 10 V1.

### 8 operator-visible Phase 10 surfaces shipped

1. `GET /metrics` (A T-A.8) — umbrella index.
2. `GET /metrics/trade-process` (B T-B.3) — 7 cohort tabs × 22 §3.1 metrics.
3. `GET /metrics/hypothesis-progress` (B T-B.5) — 4 cohort row + tripwire + transition timeline.
4. `GET /metrics/tier-comparison` (C T-C.2) — 4-cohort Wilson + bootstrap CIs + descriptor.
5. `GET /metrics/deviation-outcome` (C T-C.3) — doctrine deviation class + decision criterion.
6. `GET /metrics/capital-friction` (D T-D.2) — 6 §3.4 metrics + PROVISIONAL/LIVE dynamic badge + trend.
7. `GET /metrics/maturity-stage` (D T-D.4) — per-open-position table.
8. `GET /metrics/identification-funnel` (D T-D.6) — per-run + 30-trading-session trend.
9. `GET /metrics/process-grade-trend` (E T-E.2) — per-trade markers + rolling lines per §A.21.

Plus 4 cross-bundle integrations:
- Reconciliation banner on 10 base-layout pages (E T-E.3 retrofit; A-D inheritance).
- T-B.7 lucky_violation_R on Phase 6 review form (B elective).
- T-E.5 web-form snapshot capture at `/account/snapshot` (E elective).
- T-E.6 per-trade discrepancy indicator on `/trades/{id}` (E elective).

### Phase 11 candidate triage UNBLOCKED

Phase 11 triage owned by operator+orchestrator at next session. Pre-banked candidates enumerated at T-E.4 closer section (line 1788+):
- §8.4 Corporate_Actions MVP (standalone post-Phase-10).
- Schwab API Phase A integration.
- `mistake_cost_R_rolling_N_total` sum-class with bootstrap CI.
- Schwab inception-CSV ingestion.
- `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM semantic formalization.
- Orphan discrepancy detail surface.
- Per-cohort paused-interval filter (T-C.5 UI pattern reuse).
- 27 V2.1 §VII.F amendments triage.

### Cross-references

- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Phase 10 closer details (T-E.4 commit 4a666d1): bottom of this file at line 1788+.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md`.
- Post-Phase-10 standalone dispatch backlog: 2026-05-13 entries below (cleanup-script + test-runtime).

---

## 2026-05-13 Phase 10 Sub-bundle D ship: 5 spec amendments + 4 forward-binding lessons (FIRST PROVISIONAL/LIVE dynamic contract)

**Sub-bundle D SHIPPED 2026-05-13** at `a71cc24` (integration merge of `phase10-bundle-D-capital-maturity-funnel`). 12 commits = 7 task-impl (T-D.1..T-D.7) + 3 Codex-fix (R1+R2+R3) + 2 return-report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering. ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3045 worktree-side → 3147 (+102 net; upper end of +67..+104 projection; matches Sub-bundle A +128 / B +73 / C +84 overshoot precedent). S1 inline gate ~6:00 wall-clock. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **D1: Dispatch brief §0.8 PROVISIONAL/LIVE math wording.** Brief said `LIVE: denominator = max(capital_floor_constant_dollars, snapshot.equity_dollars)`. Plan §A.6 line 222 + the shipped `resolve_live_capital_denominator_dollars` (Sub-bundle A) return `snapshot.equity_dollars` directly (NO max-with-floor). Implementation followed plan + shipped code. **Amendment:** brief §0.8 wording should remove the `max()` qualifier.

2. **D2: Plan §A.19 SQL references `criterion_results.criterion_name`; actual schema is `candidate_criteria`.** Plan §A.19 lines 463-490 use `criterion_results cr ON cr.candidate_id ...` in the worked SQL example. Actual schema table (migration 0001:48) is `candidate_criteria` with the same column names. Implementation uses `candidate_criteria`. **Amendment:** plan §A.19 should match actual table name OR clarify the example is logical pseudo-schema.

3. **D3: Capital-friction trend window size not explicitly pinned.** Plan §G T-D.1 + spec §4.4 do not explicitly pin the multi-run trend window size for capital-friction (spec §4.4 only specifies "≥5 runs"). Implementation reused the funnel surface's 30-trading-session window for operator-readability parity. **Amendment:** plan §G T-D.1 wording — add explicit window-size lock.

4. **D4: `MaturityStageRow` carries `capital_denominator_dollars` + `capital_denominator_badge_text` fields not in plan §G T-D.3 acceptance.** Per Codex R1 M#1 + R2 M#1 fixes (verbatim plan §A.6 line 233 inline-text LOCK required visibility per-row), the dataclass gains both fields beyond what plan §G T-D.3 enumerated. **Amendment:** plan §G T-D.3 acceptance criteria.

5. **D5: `IdentificationFunnelPoint.aplus_take_rate_per_run` is NOT clamped to [0, 1].** Per Codex R1 M#3 fix, the rate is honestly emitted as `aplus_taken / aplus_id` without bounding. Plan §G T-D.5 + spec §3.6 say "proportion" implying [0, 1] in typical reading. **Amendment:** clarify "≥0; values >1 surface as data-quality anomaly signals (not clamped)" — see lesson #25.

### 4 forward-binding lessons for Sub-bundle E dispatch (return report §9; #23-#26 in cumulative catalog)

1. **#23 (NEW from D R1 M#1):** Plan-prescribed verbatim explanatory text MUST surface through a dedicated dataclass FIELD + template rendering target (NOT a `title="..."` hover-only attribute, which fails mobile + non-mouse usage AND loses audit-trail intent). Discriminating-test pattern: assert `data-{marker}=` substring in body PLUS assert `title="{format_prefix}"` substring absent. Forward-relevance for Sub-bundle E: process-grade-trend chart annotations + reconciliation badge text MUST follow this pattern.

2. **#24 (NEW from D R1 M#2):** Session-anchor read/write mismatch family extension — when a plan pins per-run aggregation on `pipeline_runs.started_ts.date()`, the implementation MUST use exactly that column (NOT `data_asof_date`, NOT `action_session_date`). These diverge on weekend/holiday runs in ways that silently drop or misbucket historical data points. Discriminating-test pattern: seed a row with `started_ts` and `data_asof_date` divergent, assert correct inclusion.

3. **#25 (NEW from D R1 M#3):** Bounded-range metrics MUST distinguish mathematically-bounded cases (e.g., `num <= denom` by SQL construction → rate ∈ [0, 1] guaranteed) from two-source aggregates (numerator + denominator independently computed → ratio can exceed 1 in anomaly cases). Clamping the latter HIDES data-quality issues. Pattern: bounded-by-construction → assert bounds; two-source → allow honest values + add anomaly badge surface. Forward-relevance for Sub-bundle E: process_grade aggregates may face the same.

4. **#26 (NEW from D R3 m#1):** SQL `ORDER BY` clauses on potentially-tied columns MUST include a deterministic tiebreaker (typically `id DESC`). Plan + Codex consistently catch nondeterminism in latest-record queries.

### Production-state observation (not blocking)

Maturity-stage surface renders 4 of 5 open positions (DHC/YOU/VSAT/CVGI shown; **LAR missing**). Production has 5 open trades per Phase 9 + Phase 10 prior gates. Root cause: `swing/data/repos/daily_management.list_open_position_active_snapshots(conn)` clamps to latest `data_asof_session` per trade; LAR has no recent daily_management snapshot covering current session. This is a **daily-management capture gap** at the operator-flow level, NOT a code regression. Operator may record fresh LAR snapshot via daily-management surface to surface LAR in maturity-stage.

### Post-merge state

- HEAD on main: `a71cc24` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (unchanged through Sub-bundles A+B+C+D).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle E executing-plans dispatch UNBLOCKED (CLOSES Phase 10).
- Cumulative pending V2.1 §VII.F amendment candidates: **22** entering Sub-bundle E (was 17 entering D; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (cleanest 4-bundle arc state in project history).
- 6 worktree husks pending cleanup-script (4 Phase 9 still-registered + 1 Sub-bundle C orphan + 1 Sub-bundle D orphan).

### Cross-references

- Sub-bundle D return report: `docs/phase10-bundle-D-return-report.md`.
- Sub-bundle D dispatch brief: `docs/phase10-bundle-D-executing-plans-dispatch-brief.md`.
- Plan §G (lines 1354-1550) consumed; AMENDED §A.6 + §A.7 + §A.18 + §A.19 + §A.20 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.

---

## 2026-05-13 Phase 10 Sub-bundle C ship: 5 spec amendments + 3 forward-binding lessons + cleanup-script gap surfaced

**Sub-bundle C SHIPPED 2026-05-13** at `a814006` (integration merge of `phase10-bundle-C-tier-and-deviation`). 8 commits = 5 task-impl (T-C.1..T-C.5) + 1 Codex-fix + 2 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (B + Phase 9 E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2961 worktree-side → 3045 (+84 new; ~3048 main post-merge from 2964 baseline; above projection +34..+56; matches Sub-bundle A +128 + B +73 overshoot precedent). Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **T-C.1 `cohort_relative_to_aplus` rendering.** Spec §3.3 row 147 defines as `cohort_expectancy_R / aplus_expectancy_R - 1` (delta proportion); dispatch brief §0.9 LOCK specified PERCENT raw-ratio `cohort_expectancy / aplus_expectancy * 100`. Implementation followed brief (binding implementer-facing artifact). Two semantically distinct metrics exist at the same numeric value: §3.3's "what fraction of A+ does this cohort achieve?" (0–200% typical) vs §3.7's "how far above/below A+" (-100% to +∞%). **Amendment:** spec §3.3 + §3.7 text should explicitly state rendering-unit semantics + the two-metric split.

2. **T-C.1 `cohort_doctrine_deviation_class` baseline enum value.** Spec §3.7 row 205 uses `"0"` as A+ baseline cohort's deviation class; implementation uses `"baseline"` string. Rationale: text field rendering; integer "0" would visually collide with the descriptive enum strings + operator's mental model that baseline IS a class label. Test pins `"baseline"` for A+. **Amendment:** cosmetic spec wording.

3. **T-C.5 filter SQL predicate.** Electives amendment §2 specified `resolution IS NULL`; schema reality (Phase 9 migration 0017) stores resolution as NOT NULL with sentinel `'unresolved'` enum default. Implementation uses `resolution = 'unresolved'` matching `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` Phase 9 Sub-bundle B convention. **Amendment:** electives amendment §2 wording.

4. **T-C.5 filter threading.** Amendment specified `CohortFilter` enum OR new bool param on tier + deviation VMs. Implementation chose bool throughout (compute + VM + route layers). Filter applied AT COMPUTE LAYER (before classification) so surface-locked cohort suppression cascade fires correctly when filter brings n<5. **Amendment:** minor; aligns with "new bool param" alternative.

5. **T-C.5 toggle href shape.** Amendment showed `<a href="/metrics/tier-comparison?exclude_discrepancies=1">` (absolute path). Implementation uses relative query href `<a href="?exclude_discrepancies=1">` + `<a href="?">` (Codex R1 M#1 fix). Relative form is more robust under mounted-app / root-path deployments. **Amendment:** illustrative-vs-binding-shape clarification.

### 3 forward-binding lessons for Sub-bundle D dispatch (return report §9; #20-#22 in cumulative catalog)

1. **#20: body-wide unit-substring assertions are non-discriminating when seed text contains the same substring** (e.g., decision-criteria contains literal `%` from "win rate > 30%"). Discriminating-test pattern: seed a specific worked example + assert the EXACT rendered numeric+unit substring at the cell location, NOT a body-wide `unit_string in body` check. Forward-relevance for Sub-bundle D: capital-friction percent-unit metrics + PROVISIONAL/LIVE badge text should follow this pattern.

2. **#21: toggle/filter links use relative query href** (`href="?key=value"` to set + `href="?"` to clear) rather than absolute path hrefs. Survives mounted-app / root-path deployments. Forward-relevance: capital-friction + identification-funnel + maturity-stage surfaces may need similar per-cohort or per-stage filter toggles.

3. **#22: per-cohort filters affecting cell suppression MUST be applied at compute layer** (before surface-locked suppression cascade fires). Applying at VM-layer post-compute would require duplicating suppression logic. Discriminating test: seed cohort with N>=5 where K trades have filter-trigger condition; filter-active brings cohort to (N-K) AND re-triggers suppression if (N-K) < surface floor.

### Cleanup-script gap surfaced (operator-decided 2026-05-13)

Operator verified the cleanup-script (`cleanup-locked-scratch-dirs.ps1`) catches **only orphaned** worktree dirs (deregistered from `git worktree list` but on-disk dir remains). Currently registered worktrees are by-design skipped (lines 215-234 short-circuit on `$isRegistered = $true`). The 4 remaining Phase 9 husks (B/C/D/E) are still registered and require `git worktree remove --force` first (deregisters; likely fails at on-disk delete due to ACL lock → produces orphan → script catches on next run). **Operator concurred with option 2: extend script with `-DeregisterFirst` switch** that drives `git worktree remove --force` against matched paths before orphan-discovery. **DEFERRED as separate orchestrator dispatch on `main`** (read-side, non-blocking, separate PR from Phase 10 sub-bundles). 5 husks pending after this dispatch (4 Phase 9 + new Phase 10 Sub-bundle C).

### Test-runtime concern surfaced 2026-05-13

Fast pytest suite at 3045 tests is 5:15 wall-clock (~103ms/test average; slow for unit-style). Orchestrator recommendation queued: (1) `pytest --durations=30` profile pass; (2) `pytest-xdist -n auto` parallelization (highest ROI; ~3-5x wall-clock reduction at zero coverage cost); (3) session-scoped schema fixtures audit. **DEFERRED as separate orchestrator dispatch.** Reduce-tests-with-coverage-preservation is the WRONG frame — each test exists as a discriminating-pin; the real lever is eliminating per-test fixture overhead.

### Post-merge state

- HEAD on main: `a814006` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B + C).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle D executing-plans dispatch UNBLOCKED.
- Pending V2.1 §VII.F amendment candidates cumulative: **17** entering Sub-bundle D (was 12 entering C; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (A+B+C clean record).

### Cross-references

- Sub-bundle C return report: `docs/phase10-bundle-C-return-report.md`.
- Sub-bundle C dispatch brief: `docs/phase10-bundle-C-executing-plans-dispatch-brief.md`.
- Plan §F (lines 1257-1334) consumed verbatim; AMENDED §A.7 + §A.18 + §A.5.1 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2 Task C.5: `docs/phase10-electives-amendment.md`.

---

## 2026-05-13 Post-Phase-10 standalone dispatches (deferred per operator decision; sequence AFTER Phase 10 Sub-bundles D + E ship)

Operator decision 2026-05-13 (mid-Phase-10, post-Sub-bundle-C-ship): two operational improvements surfaced during the Sub-bundle C dispatch + post-ship triage. Both are **read-side / infrastructure-side**, non-blocking for Sub-bundles D + E, and **DEFERRED as separate orchestrator dispatches AFTER Phase 10 completes** (Sub-bundle E ship closes the phase).

### Item 1 — Extend `cleanup-locked-scratch-dirs.ps1` with `-DeregisterFirst` switch

**Problem:** the script's worktree-orphan discovery (lines 215-234) currently catches ONLY orphaned worktree dirs (deregistered from `git worktree list` but on-disk dir remains due to Windows `.tmp/pytest-of-rwsmy/` ACL-lock pattern). Worktrees that are still registered in `git worktree list` are by-design skipped. The standard post-merge workflow is two-step: (a) operator/orchestrator runs `git worktree remove --force`; (b) if on-disk delete fails (ACL lock), the dir is now orphaned + the cleanup-script catches it on next run. Workflow gap: between step (a) and step (b), the operator's environment carries registered husks indefinitely if step (a) is skipped.

**Evidence:** at handoff 2026-05-13 mid-Phase-10, 11 worktree husks were pending operator cleanup-script per the handoff brief enumeration. After the operator's cleanup pass, 4 Phase 9 husks remained (B/C/D/E) because they were still git-registered (step (a) was never run on them). Operator confirmed cleanup-script-as-shipped does not catch them.

**Proposed extension:** add a `-DeregisterFirst` switch that drives `git worktree remove --force` against paths matching `^.worktrees/phase\d+-.*` (or accepts an explicit list) before the orphan-discovery pass. After deregistration completes, the existing orphan-discovery pass picks up the now-orphaned dirs + cleans them.

**Estimated effort:** ~30-45 min orchestrator-or-implementer dispatch on `main`. Read-side / infrastructure-side; no production-code impact; cannot conflict with Phase 10 sub-bundle worktrees (D + E will run on their own worktree branches with their own husks).

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids worktree-management changes mid-arc.

### Item 2 — Test-runtime analysis + improvements (zero-coverage-loss interventions)

**Problem:** fast pytest suite is at 3045 tests / ~5:15 wall-clock on Windows + Python 3.14 (Sub-bundle C post-ship). Per-test overhead average is ~103ms which is slow for unit-style tests (typical: 10-30ms). Going to ~3100+ tests at Sub-bundle D + E ship pushes past 6 min wall-clock. Operator surfaced 2026-05-13 the concern that approaching 3000 tests is making the dev-loop test-feedback latency painful.

**Wrong frame:** "reduce tests to retain coverage" — each test exists as a discriminating-pin for a Codex finding or regression-prevention assertion; deletion re-opens closed risks. The right frame is **eliminate per-test fixture overhead**, not test count.

**Recommended interventions in order of ROI (zero coverage loss):**

1. **Profile first (5 min, zero risk):** `pytest --durations=30` to identify the 80/20 hotspots. Without profiling, every other intervention is guessing.
2. **`pytest-xdist` parallelization (highest ROI; estimated ~3-5x wall-clock reduction):** single-line dependency add + `-n auto` in pyproject. With 8+ cores this is a 5 min → ~90s win at zero coverage cost. Risks: SQLite contention (file-based DBs need per-worker tmp dirs — `tmp_path_factory` already gives this); shared `pipeline_runs` lease tests need careful scoping. Most of the suite is already worker-safe by construction.
3. **Session/module-scoped schema fixtures:** large fraction of tests do `tmp_path → ensure_schema(conn) → seed → assert`. `ensure_schema` walks all 17 migrations on every call. Caching a fresh-DB template at session scope + `shutil.copy()` per test is ~10-50ms saved per test × thousands of tests = several minutes recovered. Medium-impact; fixture refactor required.
4. **TestClient lifespan audit:** `with TestClient(app) as client:` enters lifespan (starts `price_fetch_executor`); plain `TestClient(app)` does not. Many web tests use the `with` form even when they don't need the executor. Mechanical sweep.
5. **Audit duplicate discriminating-tests:** some Phase 9 + 10 Codex rounds added 2-3 tests pinning the same invariant via different fixtures. Manual audit; small wins; some risk of removing a real pin (requires careful per-test review).
6. **Move E2E integration tests behind `slow` marker:** `tests/integration/test_phase8_pipeline_walkthrough.py` already slow-marked. Audit `tests/integration/` for others. Doesn't reduce coverage, just reduces fast-suite footprint.

**Expected outcome:** profile + xdist together likely 5 min → ~1-1.5 min with zero coverage loss. Fixture-scope refactor adds another 30-60s reduction.

**Estimated effort:** ~1-2 hr orchestrator profile pass + ~30 min xdist integration + ~2-4 hr fixture-scope refactor if profile evidence warrants. Dispatch as a standalone read-side / infrastructure-side bundle.

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids test-runner / fixture changes mid-arc that could mask Codex-detectable regressions in Sub-bundle D + E.

### Cross-references

- Sub-bundle C return report §7 #7-#8 (this bundle surfaced the gap).
- Cleanup-script: `cleanup-locked-scratch-dirs.ps1` lines 215-234 (orphan-only discovery branch).
- Test-runtime baseline: 2964 → 3045 worktree-side at Sub-bundle C ship (~5:15 wall-clock).

---

## 2026-05-13 Phase 10 Sub-bundle B ship: 5 spec amendments + 2 forward-binding lessons + 4 V2 candidates banked

**Sub-bundle B SHIPPED 2026-05-13** at `6ed0f35` (integration merge of `phase10-bundle-B-trade-process-and-hypothesis-progress`). 9 commits = 7 task-impl (T-B.1..T-B.7 incl. T-B.7 elective) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — FASTEST Phase 10 chain (matches Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2895 worktree-side → 2951 (+73 new tests; +56 net; matches +46..+75 dispatch brief projection); 2899 → 2960 main HEAD. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (4 from return report §5 + 1 surfaced at orchestrator-driven gate)

1. **Plan §E Task B.1 acceptance text — `mistake_cost_R` aggregator source.** Plan said "prefer `review_log.total_mistake_cost_R` aggregate when present; fall back to per-trade compute when absent"; implementation always recomputes per-trade because `review_log` is **CADENCE-grain** (one row per daily/weekly/monthly review window covering N trades) with NO per-trade foreign key. The cadence aggregate CANNOT be cleanly mapped onto a cohort-grain sum at the metrics layer. Discriminating regression test `test_mistake_cost_R_recomputes_per_trade_ignoring_review_log_aggregate` pins the per-trade-recompute behavior. **Amendment:** plan §E Task B.1 should say "always re-compute via Phase 6 helpers; cohort-grain sum is reproducible from per-trade fields." V2 candidate: add `review_log_trade_links` audit table; cohort aggregator could then prefer frozen review-time values for already-reviewed trades + recompute only for unreviewed.

2. **Plan §E Task B.2 acceptance text — sentinel value for "All closed trades" toggle.** Plan didn't specify a URL-parameter sentinel. Implementation uses `__all__` as the sentinel (`?cohort=__all__`) to avoid collision with any legitimate cohort name containing the literal "all". Documented in the module docstring. **Amendment:** plan §E Task B.2 should include the sentinel choice explicitly.

3. **Plan §A.5.1 + spec §3.2 `cumulative_R_pct_of_capital` rendering unit.** Plan §A.5.1 specifies the metric as "proportion" (dimensionless); implementation stores + surfaces in **PERCENT units** (e.g., `-1.667` means `-1.667%`, NOT `-1.667 ratio` = `-166.7%`) because spec §3.2 `distance_to_absolute_loss_tripwire = absolute_loss_tripwire_pct - abs(min(0, cumulative_R_pct_of_capital))` requires comparing against `absolute_loss_tripwire_pct` which is in percent units per migration 0008 (e.g., `5.0` = `5%`). Conversion `sum(dimensionless ratios) * 100` happens inside `_build_cohort_vm`. **Amendment:** plan §A.5.1 + spec §3.2 should explicitly state the rendering unit.

4. **Electives amendment §2 Task B.7 acceptance text — existing display assumption.** Amendment said the new field renders "symmetrically alongside the existing `mistake_cost_R` display." Empirical verification of the Phase 6 template showed there was **NO pre-existing `mistake_cost_R` display** — only the operator-input form for `realized_R_if_plan_followed`. Implementation surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived display values in a new `<dl class="counterfactual-pair">` block placed BEFORE the existing form. Symmetric rendering criterion is met WITHIN the new block. **Amendment:** electives amendment §2 should be corrected: "the new block surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived per-trade display values; the existing form is unchanged."

5. **(GATE-SURFACED 2026-05-13)** **Plan §E Task B.2 acceptance text — cohort-tab enumeration scope.** Plan said `test_vm_renders_4_cohort_tabs_plus_all_toggle` expecting "5 tabs total" (4 registered + "all"). Implementation surfaces 7 tabs at production gate (4 pre-registered + 2 orphan-label + "All") because production has 2 orphan-labeled closed trades ("inaugural trade test" with 1 closed VIR + "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness" with 2 closed). Hiding orphan-labeled cohorts would hide closed-trade data from the operator. **Sensible deviation; not banked in return report but caught at orchestrator-driven S2 gate via Chrome MCP read_page.** **Amendment:** plan §E Task B.2 should say "render tabs for ALL distinct `hypothesis_label` values across closed trades (registered + orphan) + "All" toggle; default-active is FIRST registered cohort regardless of orphan presence."

### 2 forward-binding lessons for Sub-bundle C dispatch (return report §8)

1. **Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK.** Sub-bundle B R1 Major #1 surfaced the mismatch between `review_log` (cadence-grain, no trade FK) and cohort-grain `mistake_cost_R` sum. If Sub-bundle C (tier-comparison + deviation-outcome) or future sub-bundles encounter similar cadence-grain audit columns (e.g., `reconciliation_runs.summary_json` for cohort-grain "data-quality" gating), document the mismatch + always re-compute from per-trade source data. **Discriminating-test pattern** (canonical regression-pin): plant a conflicting cadence row + assert metric reflects per-trade compute, NOT the planted aggregate. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #18.

2. **Unit-semantic precision needs explicit rendering pin (percent vs proportion).** Sub-bundle B's `cumulative_R_pct_of_capital` rendered in PERCENT units to match the `absolute_loss_tripwire_pct` comparison. Future tier-comparison metrics (`cohort_relative_to_aplus`, `cohort_expectancy_relative_to_aplus_pct`) likely face the same: explicit rendering-unit pin in the VM + template + discriminating test is required at writing-plans time. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #19.

### 4 V2 candidates banked (return report §7)

1. **`review_log_trade_links` audit table** — would unlock cadence-prefer for already-reviewed trades; recompute only for unreviewed. Connects to Phase 11 candidate scoping.
2. **Per-cohort "exclude paused-interval trades" filter** — same UI pattern as Sub-bundle C's T-C.5 "exclude trades with unresolved discrepancies" filter family. Sub-bundle C may surface the reuse pattern when T-C.5 lands.
3. **`mistake_cost_R_per_trade` Class B representation alongside cohort sum** — implementation surfaces BOTH `MetricCellB` (Class B mean) AND `PointMetricCell` (cohort sum); spec §3.1 only enumerates "cohort sum." V2 candidate: clarify spec or drop the Class B representation if redundant.
4. **`canonicalize_hypothesis_label` query-time canonicalization** — `list_trades_for_cohort` already canonicalizes; verify that `count_per_cohort` orphan-label fallback path also canonicalizes (current implementation uses the registry's stored name directly + the orphan label as-is from `trades.hypothesis_label`). Edge case: an orphan trade with a non-canonicalized stored label might appear separately from a canonicalized-form match. Low risk in V1 (writer canonicalizes at persist time); banked for V2 audit.

### Post-merge state

- HEAD on main: `6ed0f35` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle C executing-plans dispatch UNBLOCKED.
- Sub-bundle B added 4 new sub-VM exclusions to `tests/web/test_view_models/test_base_layout_vm_coverage.py::_SUB_VM_EXCLUSIONS`: `CohortTabVM`, `CohortProgressVM`, plus the existing `ConfidenceBadgeVM` / `ProvisionalBadgeVM` / `SuppressionRowVM`. Sub-bundle C dispatch brief should propagate the pattern: new sub-VMs ending in `VM` that compose into a page VM (not BaseLayoutVM-extending) should be added to the exclusion set in the same commit.

### Cross-references

- Sub-bundle B return report: `docs/phase10-bundle-B-return-report.md`.
- Plan §E (lines 1063-1254; AMENDED at integration triage per amendments #1, #2, #5 above + §A.5.1 percent-unit clarification #3).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2: `docs/phase10-electives-amendment.md` (amendment #4 above corrects "existing display" assumption).
- Sub-bundle C dispatch brief: TBD (orchestrator drafts post-merge; will propagate T-C.5 elective + 2 NEW forward-binding lessons + Sub-bundle A AMENDED §A.7 interface).
- Pending V2.1 §VII.F spec amendments cumulative count: **12** (2 Phase 9 D/E + 3 Sub-bundle A + 4 Sub-bundle B return-report + 1 Sub-bundle B gate-surfaced + 2 Sub-bundle A return-report orphans-from-Phase-10-spec).

---

## 2026-05-13 Phase 10 Sub-bundle A ship: spec amendments + forward-binding lessons + V2 candidates banked

**Sub-bundle A SHIPPED 2026-05-13** at `096de83` (integration merge of `phase10-bundle-A-shared-honesty-utility`). 15 commits = 11 task-impl + 3 Codex-fix + 1 return-report; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR; ZERO Critical + ZERO ACCEPT-WITH-RATIONALE; +128 fast tests (2767 → 2895); ruff 18 unchanged; schema v17 unchanged.

### 3 V2.1 §VII.F amendment candidates (plan-text corrections; banked from return report §8)

1. **Plan §D Task A.1 Wilson CI reference value drift.** Plan acceptance criterion locked `k=2,n=4 → [0.094, 0.901]` (Wilson-with-continuity-correction); implementation chose standard Wilson (yields `[0.150, 0.850]`); plan's other two reference values `k=0,n=20 → [0.000, 0.161]` + `k=20,n=20 → [0.839, 1.000]` match standard Wilson exactly. Plan §D Task A.1 should be amended to either (a) correct the k=2,n=4 reference to `[0.150, 0.850]` (matches standard Wilson; downstream comparable to `statsmodels.stats.proportion_confint(method='wilson')`); OR (b) explicitly require Wilson-with-continuity-correction + update implementation. Implementer chose (a) per Wikipedia primary formula + statsmodels-default alignment. **V2.1 §VII.F routing recommended:** standalone amendment dispatch or fold into Phase 10 plan revision.

2. **Plan §A.5 `read_at_trade_time_policy` signature.** Plan signature `read_at_trade_time_policy(conn, *, trade: Trade) -> RiskPolicy` assumes `Trade` dataclass carries `risk_policy_id_at_lock` field. Phase 9 Sub-bundle A added the column via ALTER but did NOT extend `Trade` dataclass (`_TRADE_SELECT_COLS` in `swing/data/repos/trades.py` omits it). Implementation signature is `read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` with two convenience accessors `get_trade_policy_id_stamp(conn, *, trade_id: int)` + `get_review_policy_id_stamp(conn, *, review_id: int)` added in `swing/metrics/policy.py`. Sub-bundle B consumers fetch the stamp from DB then pass into resolver. Plan §A.5 to be amended to match implementation; OR alternatively V2-disruptive option: extend `Trade` dataclass to include `risk_policy_id_at_lock` (every existing consumer accepts new field).

3. **Plan §A.6 `BaseLayoutVM.stale_banner` type.** Plan says `stale_banner: bool = False`; implementation chose `stale_banner: str | None = None` to match existing base-layout VM pattern (`DashboardVM`/`PipelineVM`/`JournalVM`/`WatchlistVM`/`ConfigVM` all use `str | None`). `base.html.j2` renders `{% if vm.stale_banner %}` + included partial does `{{ vm.stale_banner }}` (substitutes banner text). With `bool = False` the rendered banner would be literal "True"/"False" text. Plan §A.6 to be amended to `str | None = None`.

### Plan §A.7 + §D Task A.1 amendments ALREADY APPLIED in-tree

Codex R2 + R3 caught the SAME failure-mode twice (plan-text drift from code interface changes). Implementer amended plan §A.7 + §D Task A.1 IN THE WORKTREE during Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). These are NOT pending amendments — they LANDED at merge `096de83`. The 3 candidates above are SEPARATE from those (plan-text-vs-impl divergences caught at return-report-time, not at Codex-time).

### 2 forward-binding lessons for Sub-bundle B+ dispatch (banked from return report §10)

1. **Plan §A.7 binding-interface amendments flow into plan text in SAME commit as code change.** Codex R2 Major #1 + R3 Major #1 in Sub-bundle A caught the SAME failure-mode twice: code-level interface changes (adding `HonestyBadges.window_not_full_warning` in R1; making `badges_for_n` public in R1) were NOT reflected in binding plan §A.7 text, even though Sub-bundles B-E read §A.7 as binding. **Pre-empt for Sub-bundle B+ dispatch brief §0.5:** when implementer changes any §A.7-listed interface element (HonestyBadges fields, function signatures, Decoupling discipline assignment), update plan §A.7 IN THE SAME COMMIT. Brief watch item: "if implementer adds new public function / dataclass field / signature param in `swing/metrics/honesty.py`, plan §A.7 binding interface MUST update in-tree to match."

2. **Statistical helpers with multiple textbook-correct variants need explicit spec pin at writing-plans time.** Wilson CI standard-vs-continuity-correction divergence (deviation #1 above) is a textbook ambiguity. Plan §A.7 cited "Wikipedia formula" but Wikipedia documents BOTH variants; plan's reference values mixed the two. **Pre-empt for future writing-plans dispatches:** any statistical helper that has multiple textbook-correct implementations (Wilson CI, bootstrap CI tail-handling, bias-correction, Wilson-vs-Agresti-Coull, etc.) needs an EXPLICIT formula pin in the plan with a citation to Wikipedia section, scipy/statsmodels function name, or equivalent. Add to writing-plans §5 watch items: "for statistical helpers, plan §A.7 names the SPECIFIC variant + cites Wikipedia/scipy/statsmodels function name to disambiguate."

### 2 V2 candidates banked (from return report §7)

1. **`count_unresolved_material` widen to include orphan-emit discrepancies.** Current implementation returns ONLY trade-attributed discrepancies (underlying repo helpers JOIN on trades). Orphan-emit discrepancies (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id from Phase 9 Sub-bundle D's sector_tamper audit + Sub-bundle C's equity_delta) are EXCLUDED from the count. Discriminating regression test `tests/metrics/test_discrepancies.py::test_count_unresolved_material_excludes_orphan_emit_no_trade` pins V1 behavior. V2 could widen via separate sub-query joining on the run-attribution side.

2. **`render_class_d` "point" branch hardcodes sum semantics.** Implementation hardcodes sum semantics per §A.21 + §J.1.1 for `mistake_cost_R_rolling_N_total`. Other future "point" callers (if any) needing mean semantics would need a new helper or a parameter to switch aggregation. Banked at the §A.21 V2.1 §VII.F amendment candidate; consider when Sub-bundle E lands the §3.8 process-grade-trend surface.

### Post-merge state

- HEAD on main: `096de83` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert; `max_account_risk_per_trade_pct=0.5` cfg-aligned per operator decision 2026-05-13). Policy chain: 1 (seed) → 2 (operator test) → 3 (S2.bis divergence) → 4 (S2.bis revert) → **5 (Option C revert; ACTIVE)**.
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle B executing-plans dispatch UNBLOCKED.

### Cross-references

- Sub-bundle A return report: `docs/phase10-bundle-A-return-report.md`.
- Plan §A.7 + §D Task A.1 (AMENDED in-tree at `e32f71c` + `75dd63f`).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md` (Sub-bundle B will propagate T-B.7 elective).

---

## 2026-05-13 §8.4 Corporate_Actions MVP — standalone post-Phase-10 dispatch (deferred per Phase 10 electives amendment)

**Decision (operator 2026-05-13 post-Phase-10-writing-plans-merge):** §8.4 Corporate_Actions MVP defers to a standalone post-Phase-10 dispatch. Phase 10 plan §A.0 ZERO-new-schema lock preserved; Phase 10 V1 arc shape stays at 5 sub-bundles A→B→C→D→E with 39 tasks (4 other electives propagated; see `docs/phase10-electives-amendment.md`).

**Scope when dispatched (per Phase 10 spec §8.4 + plan §A.4 cost estimate):**
- New `corporate_actions` table: columns approximately `(id, ticker, action_type, action_date, ratio_numerator, ratio_denominator, notes, recorded_at, source)`. Action types: `split`, `dividend`, `ticker_change`, `delisting`. `0018_*.sql` migration bumping `EXPECTED_SCHEMA_VERSION` 17 → 18.
- New CLI surface: `swing corporate-action {record,list,resolve}` group (mirrors Phase 9 `swing journal discrepancy` shape).
- Manual reconcile flow: operator-driven; defensive logging only; NO automated price-adjustment in V1 (per spec §8.4 recommendation).
- Estimated ~3-6hr executing-plans wall-clock; brainstorm + writing-plans + executing-plans full cycle since schema work merits independent Codex rigor.

**Rationale for standalone (not Phase 10 V1):**
- Phase 10 V1 is read-side dominant (metrics dashboard atop v17 schema); §A.0 ZERO-new-schema lock was a Codex-converged 6-round decision.
- Bundling §8.4 into Phase 10 V1 as "Sub-bundle F" would break the §A.0 lock + add ~3-6hr + 1 new table + 1 CLI surface to the executing-plans arc. Operator chose to preserve §A.0 lock + preserve Phase 10 arc shape.
- §8.4 ships first among Phase 11 candidates (along with Schwab API Phase A, inception-CSV ingestion, snapshot semantics formalization — see Phase 10 plan §10 hand-off + return-report §10).

**Sequencing:** standalone dispatch unblocks AFTER Phase 10 V1 closes (all 5 sub-bundles A→B→C→D→E integrated). Standalone dispatch may run in parallel with other Phase 11 candidates per orchestrator + operator triage.

**Cross-references:**
- Phase 10 spec §8.4 (orchestrator-decision open question; brainstorm recommendation = DEFENSIVE log-only).
- Phase 10 plan §A.4 disposition (default DEFER; operator decision 2026-05-13 confirms defer-as-standalone).
- Phase 10 electives amendment `docs/phase10-electives-amendment.md` §5.
- v1.1-alternate F-019 corporate-action interaction concern (anchored spec §8.4 risk framing).

---

## 2026-05-12 Phase 9 closer: Sub-bundle E lessons banked + Phase 10 writing-plans hand-off note

**Phase 9 arc SHIPPED 2026-05-12** (Sub-bundles A → B → C → D → E). Bundle E shipped as `phase9-bundle-E-polish-and-phase10-handoff` worktree dispatch (T-E.0 combined E2E happy path + T-E.1 CLAUDE.md gotcha promotion ratification + T-E.2 this hand-off note + T-E.3 cross-bundle Account Order History multi-line parser fix). Plan §H Task E.2 acceptance verified: `ruff check swing/ --statistics` returns 18 E501 (unchanged from Sub-bundle A baseline; zero new violations across A+B+C+D+E).

### Phase 10 writing-plans hand-off (binding inputs from Phase 9 spec §11)

Phase 10 writing-plans dispatch follows Phase 9 close. Phase 9 design choices Phase 10 needs to know about:

**§11.1 Risk_Policy as the source for metric defaults at dashboard read-time.** Phase 10 dashboard reads LIVE policy (`risk_policy.is_active=1`) for: `low_sample_size_threshold_class_*_n` (suppression at render); `global_confidence_floor_n` (n=20 floor); `bootstrap_resample_count` (CI computation); `process_grade_weight_*` (weight reconstitution if stamp absent on legacy review_log rows). Phase 10 dashboard reads AT-TRADE-TIME policy (`trades.risk_policy_id_at_lock`) for: `capital_floor_constant_dollars` (preserves historical-trade interpretation under capital-floor change); `scratch_epsilon_R` (preserves win/loss/scratch classification under threshold change); trade-grain metrics that need policy-as-of-trade-time semantics. Locked decision per spec §3.1.1: the per-row stamp on trades + review_log enables this at-trade-time vs live-time distinction. **Schema ready; Phase 10 wires the queries.**

**§11.2 Reconciliation discrepancy surface for metrics-data-quality reporting.** Phase 9 ships `reconciliation_runs` + `reconciliation_discrepancies` + the canonical query `list_unresolved_material_for_active_trades` (with closed-trade companion). Phase 10+ writing-plans may add a "reconciliation status" badge on dashboard / journal review surfaces. Recommended Phase 10+ surfaces: (a) dashboard top "N unresolved material discrepancies" badge (links to discrepancy list); (b) per-trade detail "Trade X has unresolved reconciliation discrepancies" indicator; (c) per-cohort metrics view optional filter "exclude trades with unresolved discrepancies" for sample-purity. **Schema scopes the LEFT JOIN pattern per spec §5.3; Phase 10+ implements the rendering.**

**§11.3 Hypothesis status history surfaces.** Phase 10 §3.2 surfaces "single most-recent transition only" in V1; full history requires Phase 9's `hypothesis_status_history` audit table. Phase 10 writing-plans uses the new table to render: (a) per-hypothesis transition timeline (active → paused → active → closed-target-met); (b) cohort-level "active period" calculations (excludes paused intervals from rate-metric numerators if operator opts in). **Schema sufficient; Phase 10 wires the queries via `list_history_for_hypothesis` + cohort-aggregation helpers.**

**§11.4 account_equity_snapshots resolution for `live_capital_denominator_dollars`.** Phase 10 §6.2 + §3.4 capital-friction metrics depend on a unified denominator. Phase 9 ships the table + the source-ladder discipline (schwab_api > tos_csv > manual). Phase 10 metric layer resolves:

```sql
live_capital_denominator_dollars(asof_date) :=
  COALESCE(
    (SELECT equity_dollars FROM account_equity_snapshots
       WHERE snapshot_date <= asof_date
       ORDER BY snapshot_date DESC,
                CASE source WHEN 'schwab_api' THEN 1
                            WHEN 'tos_csv' THEN 2
                            WHEN 'manual' THEN 3 END ASC
       LIMIT 1),
    (SELECT capital_floor_constant_dollars FROM risk_policy WHERE is_active = 1)
  )
```

Source ladder enforces broker-authoritative > csv > manual when same date has multiple rows. Fallback to `risk_policy.capital_floor_constant_dollars` when no snapshot exists at-or-before asof_date (Phase 10 §2 split-policy PROVISIONAL). **`get_latest_snapshot_on_or_before` already implements the source-ladder + provenance; Phase 10 consumes it.**

**§11.5 Phase 9 capture-needs already accommodated for Phase 10.** Phase 10 §6.3 enumerated capture-needs beyond Phase 8/9 plans: (a) per-pipeline-run capital-utilization aggregate — Phase 10+ writing-plans territory; uses Phase 9 `account_equity_snapshots` for live denominator; NOT a Phase 9 column; (b) benchmark series capture (Phase 10 §8.3 open question) — OUT of Phase 9 scope; orchestrator triages separately; (c) Corporate_Actions MVP (Phase 10 §8.4 open question) — OUT of Phase 9 scope; orchestrator triages separately; (d) daily account equity capture (Phase 10 §8.2 open question) — SATISFIED by Phase 9 `account_equity_snapshots`.

### Phase 9 final ruff sweep (T-E.2 acceptance criterion 1)

`ruff check swing/ --statistics` returns **18 E501** (line-too-long only). Unchanged from:
- Pre-Phase-9 baseline at HEAD `622c669` (verified 2026-05-11 in Phase 9 writing-plans return report §6).
- Sub-bundle A landing at `6c8f3a9`.
- Sub-bundle B landing at `e96834a`.
- Sub-bundle C landing at `e5d5892`.
- Sub-bundle D landing at `4894688` + housekeeping `6ba1925`.
- Sub-bundle E task family commits.

**Phase 9 introduces ZERO new ruff violations** across +500+ lines of consumer-side code + 5 new tables' worth of repo functions + 4 new service modules + ~430+ new fast tests.

### Phase 9 closing summary (for orchestrator)

- 5 sub-bundles SHIPPED across 2026-05-12 (one calendar day end-to-end).
- ~430+ new fast tests across the arc; cumulative fast suite 2462 → ~2766 at Bundle E close.
- Schema version v16 → v17 in atomic landing at Sub-bundle A T-A.1; v17 unchanged through B/C/D/E (consumer-side only).
- 1 single ACCEPT-WITH-RATIONALE position banked across the arc (Sub-bundle C R1 M#1 equity_delta sign convention; brief-vs-spec cosmetic — implementation correctly followed spec).
- 6 CLAUDE.md gotchas promoted (3 Sub-bundle A at `de10601` + 2 Sub-bundle D at `6ba1925` + 1 Sub-bundle E at T-E.1).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle D's §7 supersession to chart_pattern-mirror hidden-anchor pattern; recon doc `docs/phase9-bundle-D-task-D0-recon.md` carries the binding design).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle E T-E.3's §6.2 supersession to multi-line group parser; recon doc `docs/phase9-bundle-E-task-E3-parser-recon.md` carries the binding design).
- 2 V2 candidates banked at this file (Schwab inception-CSV ingestion; account_equity_snapshots semantic formalization).

**Phase 10 writing-plans dispatch is unblocked.** Orchestrator queues Phase 10 writing-plans next per spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-dashboard-design.md`. Brainstorm already SHIPPED 2026-05-06 at `fe6cb45`. Phase 10 reads this hand-off note's binding inputs.

---

## 2026-05-12 Phase 9 Sub-bundle D/E candidate: Schwab "since-inception" Account Statement ingestion

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Operator's "since-inception" Schwab Account Statement export `thinkorswim/2026-05-12-AccountStatementInception.csv` is structurally richer than the 7-day Account Statement Bundle B's `extract_account_summary_net_liq` (T-C.6) consumes. The inception export's full section inventory:

| Section | Bundle B/C consumes | V2 ingestion candidate use |
|---|---|---|
| Cash Balance (full inception history) | partially (cash_movements only) | seed `cash_movements` retroactively from inception; reconcile against existing rows for any pre-Phase-7 gaps |
| Account Order History | yes (Bundle B `extract_stop_orders` — banked Bundle E parser-gap fix pending) | richer inception sample for the Bundle E parser fix's regression corpus |
| Account Trade History | partially (Bundle B's `extract_stock_fills`) | full-history fill reconciliation against the journal's `fills` table for any pre-Phase-7 gaps |
| Equities (current open positions snapshot) | no | could seed `position_qty_mismatch` baselines or feed Phase 10 dashboard's open-position MTM |
| Profits and Losses (per-position YTD aggregates) | no | could seed `realized_R` cross-checks against Phase 6 `review_log` aggregates |
| Account Summary (current Net Liq + buying power) | yes (Bundle C T-C.6 `extract_account_summary_net_liq`) | unchanged |

**Concrete use cases:**

1. **Cash movements historical seed.** Bundle B's reconciliation already extracts cash_movements from any TOS export. The inception export covers the full history; ingesting it would seed the `cash_movements` table with deposits/withdrawals since account inception (verified via the operator-witnessed gate: 2 deposits of $100 each on 3/30/26 + 4/29/26 totaling $200 are in the production cash_movements; inception export would surface the same + any prior we missed).
2. **Account equity snapshots historical series.** Per-statement Net Liq values from prior monthly statements could seed an `account_equity_snapshots` historical series, giving Phase 10 metrics dashboard a real cash-basis vs MTM trajectory rather than just current point-in-time.
3. **Fills audit against the journal.** Account Trade History since inception could audit the `fills` table for any pre-Phase-7 fills missing from the journal (especially historical trades where operator may not have manually backfilled).
4. **Equity_delta historical baseline.** Bundle C's T-C.6 wires equity_delta for present-day reconciliation; an inception ingestion could backfill equity_delta history.

**Scope notes:**

- The existing `swing/journal/tos_import.py` parsing infrastructure is already there for the 7-day export shape. The inception export uses the same column structures + section headers (verified during operator-witnessed gate); the diff is the date range (full inception vs 7 days). The parser may "just work" against the inception export with minor section-specific handling.
- Section "Profits and Losses" is NEW to consume — not currently parsed. Would need a new extractor.
- Section "Equities" (current open positions snapshot) is NEW to consume — not currently parsed (Bundle B's `extract_equity_positions` parses ONLY the qty column for `position_qty_mismatch`; the Trade Price + Mark + Mark Value columns are not extracted).
- The 4 prior sample exports in `thinkorswim/` are 7-day; the inception export is the first multi-month sample. Bundle D/E or post-Phase-9 work could leverage it.

**Cross-references:**
- Schwab inception export: `thinkorswim/2026-05-12-AccountStatementInception.csv` (untracked, ~20 KB).
- Operator-witnessed gate Sub-bundle C 2026-05-12 — equity reconciliation discussion that surfaced this candidate.
- Bundle B's `extract_stop_orders` + `extract_stock_fills` + `extract_equity_positions` + Bundle C's `extract_account_summary_net_liq` in `swing/journal/tos_import.py`.
- Phase 10 metrics dashboard (brainstorm `fe6cb45`; writing-plans pending post-Phase-9) §3 `live_capital_denominator_dollars` (R1 M2 + R3 M1 lock) — would benefit directly from historical cash basis + MTM series.
- V2.1 §VII.F source-of-truth correction protocol (if ingestion changes invariants).

**Operator-paced; not orchestrator-blocking.** Phase 9 Sub-bundles D + E + Phase 10 brainstorm are higher-priority; this ingestion candidate sequences behind in-flight phases.

---

## 2026-05-12 Phase 9 / V2 candidate: account_equity_snapshots semantic formalization (cash-basis vs net-liq)

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Bundle C's T-C.6 equity_delta wiring revealed a semantic ambiguity in `account_equity_snapshots.equity_dollars`. The operator stored `$2000` representing "cash basis since inception" (deposits − withdrawals); Schwab's Account Summary reports `$2014.36` as Net Liquidating Value (cash basis + realized P&L + unrealized MTM). The equity_delta column then surfaces as ≈ -(YTD P/L) which is informative but ambiguous — the operator must mentally distinguish what `equity_dollars` meant when each snapshot was taken.

**Concrete impact:**

If Bundle C had stored `$2014.36` (MTM), equity_delta would be near zero and the comparison would surface only Schwab-vs-journal drift (e.g., parser-gap stops, missing fills). If it stored `$2000` (cash basis), equity_delta ≈ Schwab's YTD P/L — informative for "where is my P&L?" but not the spec's apparent intent (which is "where do my equity numbers disagree?").

The operator's clarification post-gate established that V1 stored cash basis, not MTM — but V1's spec/CLI doesn't force the disambiguation. Future operator could store either value at different times, producing inconsistent equity_delta interpretation.

**V2 hardening options:**

1. **Add `kind` discriminator** to `account_equity_snapshots` (`'cash_basis'` / `'net_liq'` / `'cash_balance'` — 3-value CHECK enum). Bundle B's reconciliation T-C.6 then compares like-to-like: if snapshot is `kind='net_liq'`, compare directly to Schwab's Net Liq; if `kind='cash_basis'`, compute expected_net_liq = cash_basis + realized + unrealized (using journal-computed P&L) and compare to Schwab's Net Liq. Equity_delta becomes meaningful regardless of kind.
2. **Distinct columns** instead of `kind` discriminator: `equity_cash_basis_dollars`, `equity_net_liq_dollars`, `equity_cash_balance_dollars`. Operator inputs whichever they have visibility into; reconciliation does multi-axis comparison.
3. **Auto-derive cash basis from `cash_movements`.** If `cash_movements` is fully populated (deposit / withdrawal kinds), cash basis = SUM(deposit amounts) − SUM(withdrawal amounts). Then operator doesn't even need to input cash basis — only MTM observations. Requires the Schwab inception-CSV ingestion above to seed cash_movements fully.
4. **Defer / accept V1.** Keep `equity_dollars` ambiguous; document operator convention in CLI help text + operator-facing reference; resolve via Phase 10 metrics dashboard's prescribed convention.

**Recommendation:** option 3 (auto-derive cash basis from `cash_movements`) sequenced AFTER the Schwab inception-CSV ingestion task above. Cleanest data model + lowest operator burden. Option 1 (kind discriminator) is a fallback if cash_movements completeness can't be guaranteed.

**Cross-references:**
- Bundle C return report §6 (R1 M#1 equity_delta sign convention ACCEPT-WITH-RATIONALE).
- Bundle C operator-witnessed gate S6 + post-gate equity reconciliation discussion 2026-05-12.
- Spec `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` §3.5 + §3.2 + §3.3.1 equity_delta JSON shape.
- Phase 10 metrics dashboard `live_capital_denominator_dollars` spec (R1 M2 + R3 M1 lock) — uses similar split semantic (constant vs live).

**Operator-paced; not orchestrator-blocking.** Sequences behind Schwab inception-CSV ingestion (above) for option 3 path.

---

## 2026-05-12 Phase 9 Sub-bundle E polish: Account Order History multi-line parser gap (operator-witnessed gate finding)

**Observation (operator-witnessed gate finding 2026-05-12):** Phase 9 Sub-bundle B's `stop_mismatch` detection emitted 5 false-positive discrepancies during the operator-witnessed gate when reconciling the operator's real-world Schwab/TOS export `thinkorswim/2026-05-12-AccountStatement.csv` against the production journal. All 5 open trades (DHC/YOU/VSAT/CVGI/LAR) were flagged "no broker working stop" despite working stops being placed at Schwab with prices matching journal `current_stop` values exactly.

**Root cause:** Bundle B's `extract_stop_orders` in `swing/journal/tos_import.py` per spec §6.2 looks narrowly for `STP` in the order_type column. Real-world Schwab/TOS Account Order History exports use a **2-line group** structure per working order:

```
,,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,CVGI,,,STOCK,~,MKT,GTC,WORKING
,,,RE #1006290692715,,,,,,,,4.36,STP,STD,
```

The header line carries `order_type=MKT` + `price=~` + `time_in_force=GTC` + `status=WORKING`. The continuation row carries the STP trigger price + `STP STD` qualifier. The parser only sees the header line and concludes "no STP order" — missing the actual trigger price in the continuation row.

Additional patterns observed across the 4 sample exports in `thinkorswim/`:

| File | Pattern | Notes |
|---|---|---|
| 2026-04-15 | (no Account Order History rows) | empty section — operator had no working orders on that date |
| 2026-04-30 (CC) | 3-line group: header + `TRG BY #ID BASE-6.74 STP STD` + `20.51 STP` | Conditional trigger (base-price relative) chained with absolute stop trigger |
| 2026-05-08 (DHC) | header `MKT GTC WAIT TRG` (no continuation) | Conditional order not yet armed; status `WAIT TRG` not `WORKING` |
| 2026-05-08 + 2026-05-12 | header `MKT GTC WORKING` + continuation `<price> STP STD` | Canonical 2-line stop-market group |
| various | header `MKT GTC CANCELED` | Correctly skipped (not WORKING) |

**Bundle E acceptance criteria:**

1. **Multi-line grouping.** Rewrite `extract_stop_orders` (or introduce a streaming-grouper) to read the Account Order History section as **order groups** — header row + N continuation rows until the next dated header row OR section boundary.
2. **Stop trigger extraction from continuation.** When the continuation row contains `STP STD` (or just `STP` per Schwab's column conventions), read the trigger price from the price column. Handle both simple absolute (`4.36 STP STD`) and conditional `TRG BY #ID BASE-X.XX STP STD` + absolute trigger row variants.
3. **Status filter widening.** Include `WAIT TRG` alongside `WORKING` — both indicate a placed-but-not-yet-filled stop. `CANCELED` and `FILLED` correctly remain excluded.
4. **Backwards compatibility.** Existing fixture-based discriminating tests (boundary delta=0/0.005/0.01/0.02 + 3 stop_mismatch sub-cases) MUST still pass. Add new fixture CSVs at `tests/fixtures/tos/` capturing the multi-line pattern variants observed in the operator's 4 sample exports.
5. **Regression test against operator's real-world exports.** Add a new fast-test that reconciles `thinkorswim/2026-05-12-AccountStatement.csv` against a fixture journal with the matching open trades + asserts ZERO stop_mismatch discrepancies emitted (the matching path). Mirror for the 2026-05-08 export (with `WAIT TRG` DHC).
6. **Spec §6.2 amendment.** Update spec text to reflect the 2-line group structure (currently spec assumes 1-row STP rows). Brief explicitly notes the spec text was a brainstorm-time approximation; the migration + production reality require the 2-line parse.

**Scope:** ~3-4 hr implementation. Single-task dispatch suitable for inline orchestrator OR a small implementer dispatch. Sub-bundle E's existing scope (E2E happy path + CLAUDE.md gotcha promotion + Phase 10 hand-off prep per plan §H) absorbs this naturally as a new task T-E.0.bis or T-E.3.

**Operator-side action items pending parser fix:**

- The 5 `acknowledged_immaterial` resolutions on discrepancies 1-5 in production DB stand as the V1 disposition. Operator should re-reconcile after Bundle E ships to confirm the matching path produces zero stop_mismatch findings.
- Real-world fixture corpus at `thinkorswim/*.csv` is currently untracked (in project root, not in `data/finviz-inbox/` or `tests/fixtures/tos/`); Bundle E should formalize the corpus location (copy a subset to `tests/fixtures/tos/schwab-real-world-*.csv` for the regression tests; keep the originals untracked at the operator's working location).

**Cross-references:**

- Sub-bundle B return report `docs/phase9-bundle-B-return-report.md` (merge `e96834a`).
- Operator-witnessed gate findings: §S4 of Sub-bundle B gate, 2026-05-12.
- Spec §6.2 + §3.3.1 expected_value/actual_value JSON shapes for `stop_mismatch`.
- Bundle B parser current implementation: `swing/journal/tos_import.py` (the `extract_stop_orders` function — verified single-line per the current spec; gap is the multi-line group recognition).
- Prior 3e.12 tos-import diagnostic fixed multi-day `Exec Time` parsing (commit `a9541d2`) — similar real-world-export-structure investigation pattern.

---

## 2026-05-12 Low priority: Minervini + body-of-knowledge reference review vs current strategy implementation

**Observation (operator-surfaced 2026-05-12; SCOPE EXPANDED 2026-05-13):** New methodology reference artifacts landed in two locations:

`reference/minervini/`:
- `896159773-Minervini-Trading-Strategy-Deep-Dive.txt` — 91 KB summary of SEPA.
- `Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf` — Minervini's second book (~6 MB).
- `think-and-trade-like-a-champion.md` — pymupdf4llm conversion of the PDF (415 KB markdown + 87 figures in `reference/minervini/figures/`).

`reference/Books/` (operator-added; **currently untracked in git** — operator decides tracking posture; orchestrator notes for visibility): 14 PDFs each with a converted `<slug>/<slug>.md` + `figures/` subdirectory (pymupdf4llm output). Files:
- `Trade Like a Stock Market Wizard (2013).pdf` (Minervini PRIME — already cited in 3e.8 investigation as TLSMW Ch 13 p. 296 anchor for M.2 R-multiple stop-tighten).
- `Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf` (Minervini PRIME; duplicate of `reference/minervini/` copy).
- `Mind Secrets for Winning - Mark Minervini.pdf` (Minervini PRIME; psychology + discipline emphasis).
- `momentum_masters mark minirvani.pdf` (Minervini contributor + Boucher + Minervini + Ryan + Zanger; PRIME on momentum-trading patterns + multi-author confirmation).
- `Stan-Weinstein-Stan-Weinsteins-Secrets-For-Profiting-in-Bull-and-Bear-Markets-McGraw-Hill-1988.pdf` (CONFIRMING — Stage Analysis is the doctrine predecessor underlying both Minervini's trend template + O'Neill's CAN SLIM stage methodology).
- `trade-like-an-o-neill-disciple-2010.pdf` (Morales/Kacher; CONFIRMING — O'Neill lineage; pivot/pocket-pivot/buyable-gap-up entry doctrine; sister to TLSMW VCP).
- `In the trading cockpit with the O'Neil disciples ...18,000% in the stock market.pdf` (CONFIRMING/EXTENDING — Morales/Kacher; trade-journal cadence + post-trade analysis discipline).
- `Insider Buy - Superstocks (2013).pdf` (CONFIRMING — Morales; insider-buying signal as VCP confirmation; sizing emphasis).
- `Mark Douglas - Trading in the Zone_New.pdf` + `Trading in the Zone - Master the Market with Confidence, Discipline and a Winning Attitude 2000.pdf` (DISCIPLINE/PSYCHOLOGY axis; primary source for "trade the plan not the P&L" framing).
- `Stock Market Wizards_ Interviews ...Top Stock Traders_1.pdf` + `_2.pdf` + `The New Market Wizards_ Conversations with America's Top Traders.pdf` + `The Little Book of Market Wizards.pdf` (Schwager; BREADTH/ALTERNATIVE — cross-doctrine validation; surfacing where Minervini's posture aligns with vs diverges from broader top-trader consensus).
- `Trading for a Living - Psychology, Trading Tactics, Money Management 1993.pdf` (Elder; ALTERNATIVE — different framework (technical indicators + triple-screen); useful for surfacing ALTERNATIVES to Minervini's pure-price-action posture).
- `The Big Secret To Trading Success.pdf` (BREADTH; uncategorized until skim).

These supplement the existing `reference/methodology/minervini-trend-template.md` + `reference/methodology/minervini-sell-side-rules.md` source-of-truth extracts + the Qullamaggie commentary KB at MCP server `localhost:9871` (per memory `reference_qullamaggie_mcp.md`) but contain broader doctrine + commentary not yet reconciled against current implementation.

**Body-of-knowledge hierarchy (operator-locked 2026-05-13):**
- **PRIME sources:** Minervini (TLSMW + TTLAC + Mind Secrets + Momentum Masters) + Qullamaggie (MCP commentary KB).
- **CONFIRMING / ADDITIONAL DETAIL sources:** Stan Weinstein (Stage Analysis foundation); O'Neill lineage (Morales/Kacher books).
- **ALTERNATIVE sources:** Schwager Market Wizards series (cross-doctrine breadth); Elder Trading for a Living (different technical framework); Mark Douglas Trading in the Zone (psychology baseline); The Big Secret To Trading Success.

The hierarchy means: review-dispatch findings classify reference disagreement by source role. **A PRIME-source prescription that current implementation lacks = GAP.** **A PRIME-source prescription that current implementation diverges from = DIVERGES (rationale required).** **A CONFIRMING source aligning with PRIME = strengthens the finding.** **A CONFIRMING source diverging from PRIME = surface as UNCLEAR for operator adjudication.** **An ALTERNATIVE source presenting a different approach = surface as POTENTIAL-ALTERNATIVE (NOT a GAP unless operator wants to consider adopting; informational only).**

**Regime-priority qualifier (operator-locked 2026-05-13):** sources may be DE-PRIORITIZED when their content is focused on non-swing-trading regimes (day trading; long-term position investing; intraday scalping; futures/options-specific tactics). Project trades the swing-trading regime (multi-day to multi-week holds; pivot-based entries; trend-following exits). De-prioritization is per-source-or-per-chapter at review-dispatch time — implementer surfaces the regime classification per source and operator confirms the de-prioritization OR the implementer applies the qualifier when the source's regime is unambiguously non-swing. **Per-book regime triage is review-dispatch work** (NOT pre-locked here); high-level rule is captured for review-dispatch implementer to apply.

**Scope of review (operator-locked focus: entry/exit/stop; NOT limited to these):**

- **Entry criteria.** Current implementation: `swing/evaluation/` (A+ criteria); `swing/web/routes/trades.py` entry form; `swing/trades/entry.py:entry_create` lock-time service; sector/industry tamper hardening (Phase 9 Bundle D queued). Compare to: Trend Template threshold logic; VCP / pivot pattern requirements; volume-confirmation rules; relative-strength minimums; sector-leadership posture.
- **Exit criteria.** Current implementation: `swing/trades/exit.py`; advisory rules in `swing/trades/advisory.py` (3e.8 Bundle 2 = `suggest_trim_into_strength` + `suggest_planned_target_r_hit` + `suggest_parabolic_trim`); Phase 6 review-completion outcome bucketing. Compare to: profit-take rules; +20% / +25% targets; parabolic / blow-off climax exits; "violation of the line" exits.
- **Stop criteria.** Current implementation: `swing/trades/stop_adjust.py`; trail-MA advisories (3e.8 Bundle 3 = `suggest_maturity_stage_trail_ma_hint` + `suggest_r_multiple_stop_tighten`); R-multiple stop tightening per TLSMW Ch 13 p. 296. Compare to: maximum-loss rule (-7%/-8% absolute floor); breakeven-stop timing; trailing-stop discipline; sell on first violation vs second.
- **Position sizing + risk per trade.** Current: `swing/recommendations/compute_shares` + capital floor convention ($7500 floor; user memory `project_capital_risk_floor.md`); Phase 9 risk_policy `max_account_risk_per_trade_pct` (currently 0.75 inherited from S3 test). Compare to: 1.25-2.5% baseline per Minervini; concentration vs diversification stance; pyramid-up rules.
- **Portfolio-level risk.** Current: Phase 9 risk_policy `max_concurrent_positions` + `max_portfolio_heat_pct` + `max_sector_concentration_positions` (foundation landed Sub-bundle A; consumption queued). Compare to: Minervini's portfolio-heat convention; pause-on-drawdown thresholds; consecutive-loss exit-the-market discipline.
- **Trade journal cadence + post-trade review.** Current: Phase 6 review_log + cadence card; Phase 8 daily_management_records (event_log + daily_snapshot); MFE/MAE precision tiers. Compare to: Minervini's "post-analysis" prescription (Chapter 8 of TLSMW; chapters in TTLAC); win/loss size asymmetry tracking; batting-average framing.
- **Mental model / discipline (not limited).** Compare current advisory + cadence surfaces to Minervini's psychological framework — pre-trade plan locking, batting-average framing, "trade the plan not the P&L" discipline, post-loss review cadence.

**Output target:** `docs/methodology-review-body-of-knowledge-2026-MM-DD.md` (or per-axis split if scope warrants — see dispatch shape below) enumerating divergences + gaps with citations to source role (PRIME / CONFIRMING / ALTERNATIVE) + current-code surfaces. Memo classifies each finding:
- **MATCHES** (current implementation aligns with PRIME source; CONFIRMING sources also align; no action).
- **DIVERGES** (current implementation deliberately differs from PRIME; document rationale or escalate via V2.1 §VII.F).
- **GAP** (PRIME source prescribes something current implementation lacks; potential V1+ candidate; route through V2.1 §VII.F if production-touching).
- **UNCLEAR** (PRIME source ambiguous OR PRIME-vs-CONFIRMING disagreement; flag for operator adjudication).
- **POTENTIAL-ALTERNATIVE** (ALTERNATIVE source presents a different approach; informational only; operator decides whether to consider adopting).

**Suggested dispatch shape (when sequenced):**

Original 3-source scope (~2-4 hr) is now SUPERSEDED by the body-of-knowledge expansion (~14 books + 2 Minervini/methodology source-extracts + Qullamaggie MCP). Single dispatch would burn excessive context + produce an unwieldy memo. **Recommend modular per-axis dispatch:**

1. **Axis dispatch 1 — Entry criteria reconciliation.** PRIME inputs: TLSMW Ch 5-7 + TTLAC entry chapters + Momentum Masters + Qullamaggie episodic-breakout commentary. CONFIRMING: Trade Like an O'Neil Disciple + In the Trading Cockpit + Stan Weinstein Stage 2 entry criteria. Compare: `swing/evaluation/` A+ rules + entry form + sector/industry tamper hardening.
2. **Axis dispatch 2 — Exit criteria reconciliation.** PRIME inputs: TLSMW Ch 11-13 + TTLAC exit chapters + Qullamaggie sell-side commentary + 3e.8 investigation as prior-art baseline. CONFIRMING: O'Neill disciple sell rules. Compare: `swing/trades/exit.py` + 3e.8 Bundle 2 advisories + Phase 6 review-completion bucketing. **Largely covered by 3e.8 investigation; this axis is the smallest incremental dispatch.**
3. **Axis dispatch 3 — Stop criteria reconciliation.** PRIME inputs: TLSMW Ch 13 (R-multiple stop-tighten anchor already cited in 3e.8 Bundle 3) + TTLAC stop chapters + Qullamaggie trail-MA commentary. CONFIRMING: O'Neill disciple stop discipline. Compare: `swing/trades/stop_adjust.py` + 3e.8 Bundle 3 advisories. **Largely covered by 3e.8 investigation; smallest incremental dispatch.**
4. **Axis dispatch 4 — Position sizing + portfolio-level risk reconciliation.** PRIME inputs: TLSMW Ch 9 (1.25-2.5% baseline) + TTLAC sizing + Insider Buy Superstocks (sizing emphasis) + Momentum Masters portfolio heat. CONFIRMING: O'Neill disciple position-sizing. ALTERNATIVE: Elder triple-screen sizing (different framework). Compare: `swing/recommendations/compute_shares` + $7500 capital floor + Phase 9 risk_policy fields (`max_account_risk_per_trade_pct`, `max_concurrent_positions`, `max_portfolio_heat_pct`, `max_sector_concentration_positions`).
5. **Axis dispatch 5 — Trade journal + post-trade review reconciliation.** PRIME inputs: TLSMW Ch 8 ("post-analysis" prescription) + TTLAC review chapters + In the Trading Cockpit (O'Neil disciples journal cadence). CONFIRMING: Trading in the Zone (review discipline). Compare: Phase 6 review_log + Phase 8 daily_management_records + MFE/MAE precision tiers + Phase 10 metrics surfaces.
6. **Axis dispatch 6 — Mental model + discipline reconciliation.** PRIME inputs: TLSMW + TTLAC mental-game chapters + Mind Secrets for Winning. CONFIRMING: Trading in the Zone (Douglas) + Trading for a Living (Elder) psychology chapters + Schwager Market Wizards interview anti-patterns. Compare: current advisory + cadence surfaces.

Dispatch shape per axis: single research-subagent dispatch (Explore or general-purpose agent), NOT orchestrator-inline. Implementer brief per axis: read PRIME sources for that axis + skim CONFIRMING sources for alignment + spot-check ALTERNATIVE sources + grep current implementation surfaces + produce per-axis memo. Adjudicate findings with operator after each axis ships.

**Operator can elect:** (a) full 6-axis sequence (largest scope; most thorough; ~4-12 hr per axis); (b) skip axes 2 + 3 since 3e.8 investigation already covered them at PRIME-source depth (smallest incremental scope; defer 2+3 unless TTLAC fills 3e.8-deferred items M.1, M.4, §4.A full, §4.C/§4.C.bis); (c) bundled "TTLAC-incremental + body-of-knowledge confirmation" pass (1 dispatch covering only what's NEW since 3e.8 investigation; smallest credible scope; ~4-6 hr).

**Operator-paced; not orchestrator-blocking.** Schwab API arc (in-flight 2026-05-13) + post-Schwab next-arc (TBD) are higher-priority; this review is durable reference work that should sequence behind code-shipping arcs. Capturing here so the body-of-knowledge artifacts don't sit unreconciled.

**Tracking posture for `reference/Books/`:** currently untracked; orchestrator surfaces for operator decision. Options: (a) commit (preserves doctrine-anchor reproducibility for future review-dispatches; +110 MB to repo + figures); (b) keep untracked (smaller repo + assumes operator-local stability of the corpus; review-dispatches need operator's local copy); (c) commit MD-only + .gitignore PDFs (mid-ground; preserves text reference at modest size; figures still tracked since they're cited inline). Operator-paced decision; not orchestrator-blocking.

**Cross-references:**
- `reference/minervini/think-and-trade-like-a-champion.md` (converted 2026-05-12 via pymupdf4llm).
- `reference/methodology/minervini-trend-template.md` + `minervini-sell-side-rules.md` (existing source-of-truth extracts).
- `reference/Books/<slug>/<slug>.md` + `figures/` (14 books pymupdf4llm-converted 2026-05-11; operator-added).
- Qullamaggie commentary KB at MCP server `localhost:9871` (per memory `reference_qullamaggie_mcp.md`; PRIME source).
- `docs/3e8-sell-side-advisories-investigation.md` (746-line survey of sell-side advisory surface vs Minervini SEPA + DST + Qullamaggie doctrine; SHIPPED 2026-05-10 at `63350ad`; **substantially covers axes 2 + 3** — exit + stop reconciliation; the body-of-knowledge expansion's incremental value over 3e.8 is axes 1 + 4 + 5 + 6 plus TTLAC-fills-3e.8-deferred-items check).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F (source-of-truth correction protocol; routes production-touching findings).
- CLAUDE.md "Strategy" section — `reference/methodology/` is reference-only; any production change driven by methodology reference routes through V2.1 §VII.F.

---

## 2026-05-07 Research candidate: risk level vs earnings proximity correlation

**Observation (operator-surfaced 2026-05-07):** There appears to be a correlation between risk level and proximity to earnings announcements. Pattern not yet quantified; surfacing for future research-branch investigation.

**Possible mechanisms (NON-exhaustive; investigation should disambiguate):**

1. **Stop-overshoot magnitude.** Earnings gaps (overnight 10-30% moves) blow through stops; realized loss exceeds planned -1R. Correlation = "trades held through earnings have higher realized-R variance than trades closed before earnings."
2. **Implied volatility expansion.** ATR-based position sizing reads pre-earnings ATR as elevated; risk_per_share inflates; planned_risk_budget_dollars allocates differently. Correlation = "trades entered N days before earnings have wider initial stops AND higher position-size variance."
3. **Per-cohort earnings exposure imbalance.** Sub-A+ VCP-not-formed cohort may attract more pre-earnings trades than A+ baseline (operator hasn't waited for clean post-earnings setups). Correlation = "hypothesis cohort × earnings-proximity is non-uniform."
4. **Pipeline criteria-pass interaction.** Some trend-template / VCP criteria are MORE forgiving in the post-earnings window (e.g., gap-up creates new pivot context); correlation = "criteria pass-rate × earnings-proximity is non-uniform."
5. **Discretionary-confirmation drift.** Operator-perceived risk correlates with earnings calendar awareness (operator may take MORE / FEWER trades pre-earnings based on framing). Confounds outcome attribution.

**Existing infrastructure that could feed investigation:**

- `research/studies/earnings-proximity-exclusion.md` (Tranche B-research Sessions 2a/b/c; methodology established; canonical applied-research study format).
- `research/method-records/` (V2.1 §IV.B minimum viable field list).
- Phase 6 + Phase 7 + queued Phase 8 schema captures `mistake_cost_R` + `lucky_violation_R` + per-day MFE/MAE + outcome bucketing — enables per-cohort × earnings-proximity outcome aggregation when sample size matures.
- `swing/data/ohlcv_archive.py` historical OHLCV archive (Phase 3 consolidation; 696 tickers).
- External earnings-calendar data source: undecided. yfinance `Ticker.calendar` exists but reliability is unverified for historical earnings dates. Schwab API Phase B (queued) may surface fundamentals incl. earnings; alternative paid sources exist (Earnings Whispers, Zacks, EOD historical-earnings APIs).

**Suggested dispatch shape (when sequenced):**

1. **Brainstorm** to lock the research question — which mechanism (or set) is the primary investigative target. Per V2.1 §X pre-registration discipline, decision tiers + thresholds committed before viewing data.
2. **Replay-harness extension** to per-trade-window earnings-proximity binning (mirror earnings-proximity-exclusion study's binning).
3. **Applied-research dispatch** to compute per-cohort × earnings-proximity outcome distributions over operator's actual closed trades (n=2 today; usable for n≥10 baseline).
4. **Tier-3 outcome adjudication** per V2.1 promotion path. If pattern is robust, eventual policy change candidate routes through V2.1 §VII.F source-of-truth correction protocol.

**Operator-paced; not orchestrator-blocking.** Sample size today (n=2 closed) is insufficient for any quantitative investigation; the right time to dispatch is when n≥10 closed trades accumulate AND the operator has spare research-branch time. Capturing here so the observation doesn't decay; signal-tracking only until investigation triggers.

**Cross-references:**
- `research/studies/earnings-proximity-exclusion.md` (existing study; methodology baseline).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §IV.B (research-branch method-record format) + §VII.F (source-of-truth correction protocol).
- `docs/orchestrator-context.md` §"Three-branch architecture" (Applied Research is the right home).
- 2026-04-25 Hypothesis 5 (Production-vs-replay parity check) — establishes the harness pattern.

---

## Dashboard / UX enhancements

> **Archived:** 3e.1 (mark-to-market on Account card; SHIPPED 2026-04-26 `2b5cded`) + 3e.3 (`POST /prices/refresh` clears OHLCV breaker; SHIPPED 2026-04-26 `5b56a2d`). See archive.

### 3e.9 — Market weather chart surface (INVESTIGATION; operator-surfaced 2026-05-08)

**Operator question:** evaluate for a good way to display a chart of market weather. Today the UI surfaces only a one-word label (Bullish / Caution / Bearish / STALE) on the dashboard `status_strip` + pipeline progress + open-positions row VMs. The classifier at `swing/weather/classifier.py:53` already computes close + 10MA + 20MA + 50MA + slope20_5bar + slope10_5bar from 180-day OHLCV on `cfg.rs.benchmark_ticker`; all values are persisted per run in `weather_runs`. The visual signal is absent.

**Investigation scope:**

1. **Survey current state** (above; ground truth captured in this entry).
2. **Display options to evaluate:**
   - **Option A — Benchmark price chart with MA overlays.** Mirror the per-trade chart-rendering pattern (`swing/rendering/charts.py` if applicable; matplotlib/mplfinance pipeline). 180-day candles + 10MA + 20MA + 50MA lines; current close annotation. Static PNG generated by pipeline alongside per-trade charts; rendered as `<img>` in dashboard `status_strip` or a dedicated `market_weather` section. Pre-empts mathtext gotcha (CLAUDE.md — no `$` / `^` / `_` in title format).
   - **Option B — Historical weather-status timeline.** Render `weather_runs` history (last N days) as a horizontal color-coded ribbon (green=Bullish / amber=Caution / red=Bearish). Lightweight; no new chart-rendering pipeline. Could be inline SVG or HTML divs colored via CSS.
   - **Option C — Combined.** A above with a B-style ribbon below the chart showing classification history.
   - **Option D — Trader-style breadth/regime mini-dashboard.** Beyond benchmark — add SPY/QQQ/IWM relative strength, ADL/breadth proxies if data sourceable. Higher scope; potential research-branch territory.
3. **Recommend.** Match recommendation to operator's actual decision-making cadence. Daily-prep-only? Daily-prep + intra-day glance? At-trade-entry? Each cadence implies different latency tolerance + chart freshness expectations.
4. **Implementation sketch.** Once option is locked: VM extension (likely `MarketWeatherChartVM`); rendering surface (pipeline-time chart-render OR runtime SSR); template wire-up; cache discipline (matches existing weather-run cadence — daily). Estimated 2-4 hr implementation depending on option.

**Out-of-scope until investigation completes:** what specific chart library, where in the dashboard layout, frequency of refresh, mobile-friendliness considerations.

**Cross-references:**
- `swing/weather/classifier.py:53` — current classification logic (binding; do NOT reinvent).
- `swing/data/repos/weather.py:get_latest`, `list_weather_runs` — historical data source for Option B/C ribbon.
- `swing/rendering/charts.py` (if exists) — per-trade chart-rendering pipeline pattern to mirror for Option A/C.
- `swing/web/templates/partials/status_strip.html.j2` — current weather label rendering (the surface to extend or replace).
- CLAUDE.md gotcha "Matplotlib mathtext fires on `$` / `^` / `_`" — applies to any new chart titles.
- CLAUDE.md gotcha "yfinance `interval='1d'` includes in-progress bar" — applies to any benchmark-OHLCV fetch in the new chart pipeline.
- Phase 10 metrics-dashboard spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` — may have overlapping regime-display requirements; investigate during scoping.

### 3e.2 — Include realized-from-partial-exits in journal stats total

**Observed:** `swing journal review --period month` shows 0 trades / $0.00 total
when you have 1 partial exit recorded on a still-open trade. The realized $0.74
is in the DB and in the Account card, but not in the journal stats.

**Proposed:** Split the journal stats into two figures:
- **Closed-trade metrics** (existing): win rate, expectancy, avg win/loss, R multiples
  — require a full trade cycle to compute
- **Cash-realized total** (new): sum of `realized_pnl` across ALL exits in period,
  regardless of whether the trade is closed

**Rationale:** "What have I made this month?" should include locked-in partial
exits even on open trades. R-multiple math doesn't fit a partial, but dollar
P&L does.

**Scope:** Journal stats computation + review output. Phase 2 untouched.

---

## Tranche B-ops deferred items (2026-04-24)

Items surfaced during Tranche B-ops sessions 1 (design) and 2 (execution) that were deliberately deferred. See the session-1 design spec §8 (`docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md`) for full context on items marked (§8).

### From design (§8):

- **Pipeline-linkage bundle** — add `evaluation_run_id` FK on `pipeline_runs` + new `pipeline_chart_targets` table keyed on `(run_id, ticker)`. Would eliminate both chart-scope drift modes documented in spec §4 AND subsume the `insufficient-data` → `fetcher-failed` / `too-few-bars` split. Estimated ~1 pipeline-layer session. Phase 2 carve-out required.
- **Exit-form field preservation** — `TradeExitFormVM` has the same latent preservation gap as the stop form. No live bug; the spec scopes preservation specifically to the stop form. Low-effort follow-up.
- **ExitRationale enum distinct from ExitReason** — revisit when journal analysis produces evidence that `reason=partial|manual` rows corrupt downstream queries.
- **Total-book risk cap config** — `cfg.risk.max_total_risk_pct` + warn-coloring on the Open-risk tile. Deferred until evidence about the right default.
- **Book-equity-based Open-risk percent** — requires live prices in risk math. Current denominator is realized equity.
- **Chart-reason split: `insufficient-data` → `fetcher-failed` vs `too-few-bars`** — needs pipeline-layer per-ticker chart-status persistence. Subsumed by the pipeline-linkage bundle above.

### From Session 2 adversarial review:

- **Session-gating propagation for read-only surfaces** — `DashboardVM.stale_banner` currently does not propagate to watchlist/expand and other non-dashboard surfaces. Chart-scope resolver accepts the weekend/holiday drift for this reason. A future brainstorming session would design strict cross-UI session-gating. Spec-level decision required.
- **Transport/decode img failure fallback** — Session 2 C3 intentionally dropped `<img onerror>` per spec §4 rationale (transient static-mount errors "should page someone"). If real operational experience argues for a narrow client-side fallback distinct from the server-side intentional-absence states, reconsider. Low priority; monitor.

### From Session 3 adversarial review:

- **`TradeEntryFormVM.force` pre-existing dead field** — symmetric to the `TradeStopFormVM.force` removal shipped in Session 3 C5. No template consumer; no re-render usage. Session 3 declined to touch it mid-session per scope discipline. ~5-minute cleanup commit.
- **`(str, Enum)` → `StrEnum` migration across three enums** — `ExitReason`, `EntryRationale`, `StopAdjustRationale` all currently use the `(str, Enum)` pattern and carry `# noqa: UP042`. A single-commit migration clears all three `noqa` comments at once. Cohesive, small, low-priority.

---

## Tranche C deferred items (2026-04-25)

Items surfaced during Tranche C sessions (pipeline-linkage bundle, commits `f45dae8..1cfc117`; candidate-sparsity diagnostic, commits `1b33e21..bd0dae6`) that were deliberately deferred per scope discipline.

### From pipeline-linkage bundle:

- **`build_watchlist` mixed-anchor fix.** Same disease as today_decisions / candidates_by_ticker / _step_export had pre-Tranche-C; the standalone `/watchlist` page still reads via "latest eval" rather than `pipeline_run.evaluation_run_id`. Small commit (~30-60 min) now that the FK exists. File: `swing/web/view_models/watchlist.py:50-53` (the `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` query).
- **Stale `pipeline_chart_targets` rows on lease revoke.** When `_step_charts` writes `'pending'` rows then crashes / is force-cleared, those rows persist for the now-force_cleared `pipeline_runs` row. Resolver only reads `state='complete'` so they're inert, but accumulate over many failed runs. Worth a `sweep_stale_artifacts`-style addition if they grow.
- **"no-run" chart-reason wording inconsistency.** Pre-existing message says "for this session" but resolver is no longer session-gated. Revisit only if operators report confusion.
- **Per-ticker `fenced_write` granularity in `_step_charts`.** Each ticker outcome is its own `lease.fenced_write()` transaction (~15 small transactions per pipeline run). Acceptable now; if chart-step performance becomes a bottleneck, batching the per-ticker UPDATEs into a single fenced commit at end-of-step is straightforward.

### From candidate-sparsity diagnostic:

- **Hypothesis 5 — Production-vs-replay parity check.** The diagnostic's most-permissive matrix cell (Russell 3000 5×) reaches 0.0098%; production observation (Session 2a) is ~0.5%. **~50× residual gap unexplained** by universe + capital combined. Cheapest applied-research follow-on: side-by-side comparison of harness `evaluate_one` output vs production pipeline output for same inputs over the same window. Surfaces any silent code drift between research-branch reuse and production execution. Estimated ~1 session, applied-research scope.
- **Hypothesis 6 — Finviz universe reconstruction.** Most explanatory route to closing the residual gap but multi-week scope. Reconstructs the time-series of operator's actual Finviz-filtered universes to test universe-source hypothesis. Out of scope absent specific reason and time budget.
- **Newcombe interval on cross-universe rate difference.** Diagnostic R2 review noted the disjoint-CI rule has anti-conservative properties; a formal Newcombe interval on (p_C − p_A) would be the proper instrument. The qualitative-direction conclusion is robust to choice of test; nice-to-have refinement, not load-bearing.
- **Supplementary `--base-capital 100000 --capital-multiplier 1.0` parity run.** Would reproduce Session 2c's 11 A+ count (or surface a parity drift) and close the matrix's third capital interval [$37.5k, $100k]. Pre-authorized as thin follow-on if hypothesis-5 work happens.
- **`recompute_binding_prod_gated.py` parameterization.** Currently hardcoded against `build_harness_config()`. If a future diagnostic uses different criteria configurations, parameterize. Defer until that need arises (registry-maximalism risk per V2.1 anti-patterns).
- **Methodology lesson — production-gating-aware instrumentation as standing pattern.** Captured durably in `docs/orchestrator-context.md` §"Lessons captured." When instrumenting production logic for diagnostic measurement, mimic production's gating order, not criteria emission order. Future diagnostic instrumentation should adopt this pattern from the start.

### Capital-sensitivity finding disposition (informational):

The diagnostic established that risk_feasibility blocking is highly capital-sensitive in proportional terms but modest in deterministic A+ count terms. Operator (2026-04-25) declined to act: "the amount of money available is the amount of money available; without proven history, doesn't make sense to raise capital 2 orders of magnitude to go from 5 months to 2.5 months per A+ candidate." Recorded here so future operator/orchestrator sessions don't re-litigate.

---

## 2026-04-25 parallel-work follow-ups

Items surfaced during the parallel `build_watchlist` mixed-anchor fix (commit `77877c1`) and harness-vs-production parity check (commits `c47a783..1a88fb7`) that were deliberately deferred per scope discipline.

### From `build_watchlist` mixed-anchor fix:

- **Stale banner on `/watchlist`.** `WatchlistVM.stale_banner` is currently always `None` on the standalone `/watchlist` page despite being declared. On "new day, no fresh pipeline yet" workflows the page can render today's session_date alongside flag tags from the previous completed pipeline. Moderate-scope follow-on: touches `WatchlistVM`, `build_watchlist`, watchlist template; coordinates with the base-layout shared-VM gotcha listed in CLAUDE.md (every base-layout VM must gain new fields). Mirror `build_dashboard`'s stale_banner derivation at `dashboard.py:154-165`. Genuine UX gap; defer until you want to scope a session for it.
- **Deterministic tiebreaker on `ORDER BY finished_ts DESC LIMIT 1` (class-level pattern).** Several query sites in `swing/web/` (dashboard.py:107-111, 143-147, 155-159; watchlist.py uses the new pattern in `build_watchlist` post-`77877c1`; `build_watchlist_expanded` separately) use second-precision timestamp ordering without a deterministic tiebreaker. **Recommendation: defer indefinitely.** SQLite second-precision collision requires two pipeline completions in the same second — essentially impossible given pipeline runtime. Pre-existing across the layer; cost is small but value is theoretical until we see an actual collision in the wild. Capture here so a future session doesn't accidentally pick it up as urgent.

### From harness-vs-production parity check:

- **Multi-run parity characterization.** The Tier 1 result is on n=1 production run (eval_15, action_session 2026-04-25). For tighter inference, run the parity comparator across the last 5–6 production runs with preserved Finviz CSVs. Operator-decision gated; not urgent given the Tier 1 single-run result.
- **A+-surface-exercising parity run.** The n=80 eval_15 produced zero A+ candidates, so parity at A+ classification level is empirically unverified. Pick a historical production run that produced ≥1 A+; verify parity at A+ level. Not urgent given Tier 1 already verifies the watch/skip-level classification logic.
- **Parity comparator as periodic regression check.** Open question whether to run the parity comparator on every release or never again. **Recommendation: never-again unless a future change to `swing/evaluation/` or `research/harness/` specifically warrants it** (any change to the production scoring chain or the harness's evaluator wrapper). The comparator is durable in `research/parity/`; re-running is ~30 min when the question recurs.
- **`PriceFetcher` cache-stat introspection.** Production's `swing.prices.PriceFetcher` does not expose hit/miss counts; the parity comparator wrapped it in `_CountingPriceFetcher` (in `research/parity/run.py`) to report cache stats in the D3 manifest. Minor architectural gap; backlog item for if cache observability becomes operationally valuable elsewhere in the production layer.

---

## 2026-04-25 Bug 1 follow-ups (watchlist Enter-button event-propagation)

Items raised by Codex during Bug 1's adversarial review (commit `9aabe8b` shipped) and accepted-with-rationale per scope-bounded brief. Captured here for future-session pickup; not urgent but real architectural concerns.

- **Watchlist row HTMX trigger architecture refactor.** The current row design — `<tr hx-get="/watchlist/<ticker>/expand">` makes the entire row a click target — means any interactive child added to the row (button, input, link) has to remember `onclick="event.stopPropagation()"`. Bug 1's fix is a point-fix at the Enter button; it doesn't prevent recurrence with future interactive children (e.g., when Phase 3e §3e.5's "Log entry" button replaces the existing CLI placeholder in `watchlist_expanded.html.j2:33`). Two architectural alternatives:
  - **Option A: dedicated chevron cell** — move the expand trigger from the row to a leftmost `<td class="expand-trigger">` chevron. Visual UI change; explicit affordance for expand.
  - **Option B: scope the trigger** — use `hx-trigger="click from:td.row-trigger"` to limit the row's expand trigger to a specific cell or class. Invisible to user; same effect as Option A.
  - **Recommendation when scoped:** Option B unless operator wants the chevron UI affordance. Estimated ~1-2 sessions including tests. Picks itself up when more row-level controls ship.
- **JS-execution test harness gap.** Project currently uses FastAPI TestClient + assertion on rendered HTML strings for web-layer tests. Sufficient for server-side rendering correctness; INSUFFICIENT for JavaScript event behavior, HTMX runtime swap targeting, DOM updates after script execution, and CSS-driven visual states. Bug 1's fix test (string-match `stopPropagation`) confirms the attribute is present but does NOT confirm the runtime behavior is correct — operator manual verification is the actual confidence source. Adding a JS test harness (Playwright or Selenium) would close this gap but adds: heavy dependency (chromium driver), slow tests (browser startup overhead), flakiness risk (timing-dependent failures), CI complexity. **Recommendation: defer** until either (a) 5+ event-handling-related bugs accumulate, (b) chart-pattern algorithm or other rich-UI work approaches and would benefit, or (c) manual verification becomes a bottleneck. When scoped: ~2-4 sessions for harness setup + CI integration + re-architecture of test patterns. For now, manual verification remains the JS-behavior testing surface for the project.

---

## 2026-04-25 Bug 2 follow-ups (trade entry form vanishes mid-typing)

Items flagged by the Bug 2 investigation (commits `04ef355` → `20d2cab` shipped) as defense-in-depth opportunities and pre-existing degradations not in the fix scope.

- ~~**`_handle_any` HX-Target-awareness (defense-in-depth).**~~ SHIPPED 2026-04-26 as Session 1 T7 of the QoL UI-polish bundle (commit `d9603c9`). `_handle_any` now uses `_is_row_swap_target(request)` and `_ROW_TARGET_PREFIXES`-aware fragment selection, mirroring `_handle_http_exc`. Latent risk for unhandled non-HTTPException raised inside row-target routes is closed.
- **Sizing-hint hx-trigger parsing bug (pre-existing behavioral degradation).** Current trigger string in `partials/trade_entry_form.html.j2` (sizing-hint span): `change from:input[name=entry_price],input[name=initial_stop] delay:200ms`. Per HTMX 2.0.3's tokenizer, this parses as TWO separate triggers because HTMX splits on top-level commas: (1) `change` event from `input[name=entry_price]` with NO delay (delay:200ms attaches to the second trigger only); (2) `input` event with broken filter expression `[name=initial_stop]` which compiles into `event.name = (event.initial_stop ?? window.initial_stop)` — always evaluates undefined → never fires. Net effect: sizing-hint fires correctly on entry_price changes (without intended debounce) but NEVER fires on initial_stop changes. **Recommendation:** likely fix is HTMX's parens-grouped from-selector syntax: `change from:(input[name=entry_price],input[name=initial_stop]) delay:200ms`. Verify against HTMX 2.0.3 behavior (test in browser; check HTMX docs). ~30 min including a smoke test that asserts both fields trigger sizing-hint requests with debounce. Behavioral degradation; affects sizing feedback UX but not correctness. **2026-04-29 update:** investigation-first bug-fix dispatch's DevTools capture confirmed `htmx:syntax:error: Invalid left-hand side in assignment` fires on EVERY entry-form render at `partials/trade_entry_form.html.j2:22-23` from the same selector. Severity confirmed; fix is the parens-grouped syntax above. Form still works because HTMX recovers from the syntax error, but every form open logs a JS error. Prioritize bundling with other entry-form-touching dispatches (reuses operator-witnessed-verification overhead) OR pick up standalone if a CLAUDE.md gotcha entry isn't sufficient.

### Bug 2 root-cause fix history note (informational, not a follow-up)

Bug 2's actual root cause was **not** the form-submit ValueError path that the first fix attempt (`04ef355` → `20d2cab`) addressed. The actual mechanism was sizing-hint span `hx-target` inheritance from parent `<form>`: the span had no explicit `hx-target`, so it inherited `hx-target="closest tr"` from the form, causing every sizing-hint hx-get response to swap into the entry-form `<tr>` position — replacing the entire form with just the sizing-hint span. Real fix: `2a167d1` adds explicit `hx-target="this"` to the sizing-hint span (one-line). The first fix is preserved as defense-in-depth (correct behavior for actual form submission with stop≥entry). Lesson captured in `docs/orchestrator-context.md` anti-patterns: "Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction"; mitigation in operating-processes via investigation-phase operator-confirmation gate for INVESTIGATION-FIRST bug-fix briefs.

---

## 2026-04-25 hypothesis-engine + analyze + backup follow-ups

Items surfaced from the Monday-prep operational batch (commits `4a565c6` → `fe270a6`).

### From hypothesis-recommendation engine work:

- **WatchlistVM extension for active recommendations** (optional). hyp2 declined per scope discipline — dashboard + CLI pre-fill cover the primary loop; the watchlist page already shows flag tags. If operator wants the standalone `/watchlist` page to also list active recommendations, clean follow-up: add `active_recommendations` field to `WatchlistVM`; render the same partial in the watchlist template. ~30 min work.
- **Monitor for first hypothesis closure → revisit longer-horizon planning.** Per orchestrator-context.md 2026-04-25 entry: when the first hypothesis closes (target sample met OR tripwire-fired escape), revisit the longer-horizon planning question with operator. Likely first to close: Sub-A+ VCP-not-formed (5-sample target; VIR is sample 1) or A+ baseline (20-sample) depending on operator's actual identification + take pace.
- **Hypothesis registry-mutation discipline (operator-facing).** Per pre-registration discipline, only `status` is mutable via `swing hypothesis update`. To add a NEW hypothesis or change target_sample / tripwire / decision_criteria of existing hypotheses requires a formal new migration (e.g., `0009_hypothesis_v0.2_amendment.sql`). This boundary is a feature, not a limitation; preserves anti-rationalization integrity. If operator decides to add hypothesis 5 (e.g., post-first-closure planning), it's a small Phase 2 carve-out: new migration + seed.

### From `swing trade analyze` CLI work:

- **Cross-contamination commit-title misattribution.** Commits `375344f` (titled "feat(pipeline): trigger weekly DB backup...") and `43b4d35` (titled "feat(cli): add db-backup subcommand...") accidentally bundled trade-analyze implementer's work due to parallel `git add` race. Code is correct; commit titles are misattributed. Could be addressed via git notes if attribution preservation matters; recommendation per orchestrator-context.md 2026-04-25 lesson is to leave as-is (the lesson is durable; archaeology fix is administrative overhead). Future parallel dispatches should use git worktrees to prevent this class of issue.

### From weekly DB backup work:

- (No follow-ups; clean implementation.)

---

## 2026-04-26 QoL bundle + watchlist sort follow-ups

Items surfaced during the QoL UI-polish bundle (Session 1, commits `4c264b2..d9603c9` + adversarial fixes `61424f2`, `20ecc70`, `d9ab7ff`) and the watchlist sort-by-tags session (Session 2, commits `1d6ed42..e613f39`) that were deliberately deferred per scope discipline. Adversarial review reached `NO_NEW_CRITICAL_MAJOR` in both sessions (Session 1 R3, Session 2 R5).

### From Session 1 (QoL UI-polish bundle):

- **Target-family-aware error fragments (Session 1 R1 Major 2 — accepted, not fixed).** `partials/trade_form_error.html.j2` hardcodes `colspan="8"`; watchlist row tables use 7 cells. Affects both `_handle_any` (T7 just shipped) and `_handle_http_exc` (pre-existing) symmetrically. Browsers tolerate `colspan` greater than column count, so functionally non-blocking; structural correctness would pick a fragment per `_ROW_TARGET_PREFIXES` family. Cheap follow-up when a future row-target table gains a different cell count or when a stricter validator complains.
- **Alternating-row CSS scoping (Session 1 R1 Minor 2 — accepted with rationale).** Global `tbody tr:nth-child(even) td` rule may bleed striping into future tables that don't want it. Currently relies on source-order vs `tr.tripwire-fired`. If a future class needs to override, increase its specificity (e.g., `tr.expanded > td`) or scope the alternating rule to specific tables (`#open-positions tbody tr:nth-child(even) td`). Operator manually verified that `tr.expanded` rows currently inherit the underlying stripe color naturally — no awkward mid-table jump.
- **`build_watchlist_row` single-ticker performance (Session 1 R2 Minor 1 — accepted with rationale).** `swing/web/view_models/watchlist.py:build_watchlist_row` scans the full active watchlist and full candidates list to render one row. Acceptable today; **trigger threshold: watchlist > ~100 rows**, at which point add a single-ticker variant of `list_active_watchlist`.
- **Close-button server-round-trip failure model (Session 1 R2 Major 1 — accepted with rationale per Option-A spec).** A transient backend failure on `/watchlist/<ticker>/row` (collapse) can leave the row temporarily stuck expanded or replaced with an error fragment. Identical failure model to `/expand`. If operator-visible failures occur, evaluate Option B (client-side stash + collapse via cached compact-row HTML).

### From Session 2 (watchlist sort-by-tags):

- **Centralize eval-anchor resolver (Session 2 R2 Minor 3 — accepted, out of scope).** The same ~10-line `pipeline_runs.evaluation_run_id`-with-fallback block now lives in three places: `swing/web/view_models/dashboard.py:73-86` (already factored as `latest_evaluation_run_id`), `swing/web/view_models/watchlist.py:59-66`, and `swing/web/routes/pipeline.py` `/prices/refresh` route. The dashboard module already exports `latest_evaluation_run_id`; the other two sites should consume it. ~30-min DRY refactor.
- **Extract `swing/web/watchlist_ranking.py` module (Session 2 R1 Minor 1 — accepted, out of scope).** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, and `_flag_tags` currently live in `swing/web/view_models/dashboard.py` and are imported from `watchlist.py` and `routes/pipeline.py`. Module extraction would clarify ownership; minor cleanup.
- **Decouple `_TAG_PRECEDENCE` from UI label strings (Session 2 R1 Minor 3 — accepted, out of scope).** `_TAG_PRECEDENCE` is keyed on the same presentation strings (`"TT✓"`, `"VCP✓"`, `"A+"`) that templates render. A future label rename would silently zero out precedence (unknown keys score 0 because the fallback for unknown tags is `0`). Decoupling: introduce a tag-id enum or constants like `TAG_TT_PASS = "TT✓"` referenced from both the precedence map and the templates. Not urgent; current state is correct.
- **(2026-04-28 sector dispatch follow-up) Factor non-web utility helpers out of `swing.web.view_models.dashboard` once 3+ cross-imports exist.** Surfaced during sector-capture writing-plans dispatch return report. Pattern observation: `latest_evaluation_run_id()` is now imported by CLI for sector auto-resolution (sector dispatch Task 7), making it the second cross-import from `swing.web.view_models.dashboard` (first precedent: `_lookup_active_recommendation_label` for hypothesis pre-fill). Currently fine — two consumers is below the refactor threshold. **Trigger:** when a third non-web call-site needs to consume one of these helpers, factor them into a non-web-bound module (likely `swing/data/utils.py` or similar). Picks itself up naturally.
- **(2026-04-29 journal-flag fix follow-up) Emit a dedicated "all winners closed same-day" behavioral flag instead of silently skipping the losers-held-too-long ratio.** Current behavior post-2026-04-29 fix: when `avg_w == 0` (all winners are same-day-open-and-close), `_losers_held_too_long` returns None (silent skip). The same-day-winner pattern is itself a behavioral signal worth surfacing — operator may be cutting winners short by closing same-day instead of letting them run. Proposed flag: code `winners_closed_same_day`, title "All winners closed same-day", detail along the lines of "{N} winners closed same-day; consider letting winners run multi-day for trend continuation." Defer until operator confirms the signal is operator-relevant (currently the losers-held flag is the canonical "behavioral concern" surface; adding a parallel flag is a UX decision). Small dispatch when picked up: extend `_losers_held_too_long` OR add a sibling `_winners_closed_same_day` function in `swing/journal/flags.py`; add discriminating regression test mirroring the just-shipped guard test.

- **(2026-04-29 production-verification investigation dispatch follow-up) `/watchlist` standalone entry-flow polish (R1 Critical 1 ACCEPTED).** Trade records correctly via the `/watchlist` standalone page; UX is silent (no confirmation banner; no on-page open-positions table; no toast). Operator confirms trade was recorded by navigating to dashboard. Operator workflow is dashboard-centric so low-priority. Proposed enhancement: toast notification on success + status-strip rendering + open-positions section parity with dashboard flow on the standalone `/watchlist` page. Investigation evidence at `C:/tmp/bug-probe/` (2026-04-29; may decay; reproduce on demand). ~1-2 dispatch cycles when picked up.

- **(2026-04-29 production-verification investigation dispatch follow-up) Shared protocol/dataclass for `hypothesis_recommendations.html.j2` partial (R3 Minor 1 ACCEPTED).** Duck-typed VM contract — `vm=dashboard_vm` and `vm=HypRecsSectionVM` both work today because the partial only reads `vm.active_recommendations`. Future template edit reading another field could break one consumer. Long-term hardening: introduce a shared protocol (e.g., `class HypRecsConsumerVM(Protocol)`) with the partial's required fields; both consuming VMs implement it; partial template-typed against the protocol. Discipline currently documented in source comments at the call sites. Pick up when (a) the partial gains a new field reference OR (b) a third consumer joins.

- **(2026-04-30 OHLCV archive Phase 3 follow-up) `research/parity/run.py:178` references removed `_cache_path` method on `PriceFetcher`.** Phase 3's PriceFetcher refactor removed the `_cache_path` method (replaced by per-ticker archive helper). `research/parity/run.py:178` still calls it — research-branch CLI code (per CLAUDE.md bifurcated architecture); not in fast suite; runtime-fails if invoked. Not used in production `swing/` flow. **Bundle into Phase 4 cleanup-remainder dispatch** (or fold into the eventual `_CountingPriceFetcher` rewrite that the new archive directory shape requires for cache-stat introspection).

- **(2026-04-30 OHLCV archive Phase 3 follow-up) Parallel cold-start test with today-aligned archive (R1 Minor 1 advisory).** Current OhlcvCache cold-start test mocks `yf.download` empty as a safety guard against test-suite network calls; this weakens the "no network call" claim because the discriminating contract is verified via `helper_calls == ["AAPL"]` + bundle reflects archive content. Future improvement: add a parallel cold-start test using a today-aligned archive (no gap fetch needed) to assert TRUE zero-yfinance behavior end-to-end. Small additive test; ~30 min when picked up. Bundle into Phase 4 cleanup-remainder.

- **(2026-04-30 OHLCV archive Phase 3 process-meta) Task 5/6 scope co-dependency observation.** Phase 3 plan partitioned `swing/web/ohlcv_cache.py` kwargs wiring under Task 6, but the wiring had to land in Task 5 commit (`9a61d19`) to keep the fast suite green during the `fetch_daily_bars` signature change. Task 6 commit (`75526fe`) became pure test-additive. **Generalization:** task-by-task plan partitioning can have "gotcha co-dependencies" where a downstream task's wiring must land co-temporal with an upstream task's signature change to preserve test-green throughout. Writing-plans phase should anticipate these by tracing signature-change ripple effects across consumer files; task partitioning that splits a signature change from its consumer wiring across tasks should explicitly call out the co-temporal-landing requirement. Add to writing-plans phase as a checklist item for any plan modifying a function signature that's consumed by other plan-affected files.

- **(2026-04-30 hypothesis_label web-form gap) ARCHITECTURAL: web entry form does not capture `hypothesis_label`.** Latent since 2026-04-25 hypothesis-recommendation-engine ship; surfaced by operator's CC trade entry on 2026-04-30 (per-row "Take this trade" button on hyp-recs expansion). **Concrete failure mode:** every web-form trade entry persists `hypothesis_label = NULL` (then empty string at canonicalization) → progress count never increments → tripwire never fires from web entries. Verified in `swing/web/`: ZERO references to `hypothesis_label` in views, view_models, routes, templates. CLI has full pre-fill machinery (`swing/cli.py:415-501`); web has none. VIR (id=1) only has its label because backfilled via SQL UPDATE 2026-04-25; CC (id=3) backfilled the same way 2026-04-30. **Operator workflow tax:** every hypothesis-tagged trade taken via the web form requires a SQL UPDATE backfill to attribute it correctly. Bearable at current ~50-trades/year ceiling, but real friction. **Fix scope:** small-medium dispatch (~3-5 tasks): (a) add `hypothesis_label` field to `TradeEntryFormVM` populated via the same matcher logic the CLI uses (`_lookup_active_recommendation_label` from `swing.web.view_models.dashboard` already exists; matches the cross-import note); (b) add hidden input + read-only display rows in `partials/trade_entry_form.html.j2` (mirrors the sector/industry pattern from sector capture Phase 1); (c) add `Form(...)` param + thread through `EntryRequest.hypothesis_label` in `swing/web/routes/trades.py entry_post`; (d) discriminating tests + soft-warn round-trip preserves the label (per the multi-path-ingestion lesson 2026-04-29). **Sequencing:** sequence after Phase 4 cleanup-remainder ships (operator-paced; not Phase-4-blocking). OR inline into Phase 4 if implementer has bandwidth — but operator decided Phase 4 plan continues separately, so default to standalone follow-up dispatch post-Phase-4. **Cross-references:** orchestrator-context.md "Recent decisions and framings" 2026-04-25 (hypothesis-recommendation engine framing — "dashboard PROPOSES, operator DISPOSES"); 2026-04-25 "Prefix-label convention" (operator-facing — manual labels start with canonical hypothesis name); CLI precedent at `swing/cli.py:486-501` (pre-fill logic to mirror in web). _Note: 2026-04-30 SHIPPED as Phase 4.5 hypothesis_label web-form gap fix at `f9a07bf` per orchestrator-context in-flight ledger; entry retained here for cross-reference._

- **(2026-04-30 entry-form stop-value observation; defer-investigate)** Operator reported during CC entry (Take-this-trade button on hyp-recs expansion, 2026-04-30): "the table did not have the stop values correctly populated; potentially others." Operator instruction: "we do not need to investigate further" until another instance reproduces. Logged for memory; if a second observation surfaces with screenshots or specific field values, dispatch investigation-first. **Possible mechanisms (NON-exhaustive; do NOT design fixes against these without empirical reproduction):** (a) sell-stop snapshot field reads from the wrong source (Candidate.initial_stop vs SizingResult.stop_loss vs computed-fallback); (b) origin-aware re-resolution at form-render time loses snapshot context; (c) PriceFetcher stale archive returning wrong reference price (Phase 3 just shipped; not yet operator-verified end-to-end); (d) ToCToU window between expansion-render and form-render. **No action until reproducer.**

---

## 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups

Items surfaced during the chart-pattern flag-v1 brainstorm dispatch (commit chain `9583f19..081f689`, spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, 5 adversarial Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`). Implementation Phase 1-7 SHIPPED via the per-phase dispatch chain (archived); these items are explicitly out of V1 scope.

### V2+ pattern coverage (deferred per locked-constraint #1):

- **Pennant pattern.** Same shape geometry as flag but with converging trendlines. V2 adds to `pattern` IN-list via new migration; classifier adds geometric gates for trendline convergence.
- **Cup-with-handle pattern.** Multi-month U-shape + shallow pullback near pivot. Larger geometric definition surface; likely benefits from multi-timeframe consideration.
- **Flat base pattern.** ≥5 weeks, range ≤~15%. Simpler than flag; mostly range-CV + duration check.
- **Tight channel pattern.** 2+ weeks of converging highs/lows. Variant of flag with stricter parallel-line geometry. **Methodology-reference candidate:** Lo, Mamaysky, Wang (2000) covers "rectangle" (RTOP/RBOT) which is the academic-finance name for tight-channel geometry — kernel-regression-smoothed local-extrema definitions in their §II.A are a starting point for V2 spec drafting.
- **Qullamaggie taxonomy patterns.** episodic_pivot, power_earnings_gap, parabolic_short, gap_and_go, base_breakout, ipo_breakout — all available as reference layer via the qullamaggie MCP; some require external context (earnings calendar, IPO date) and are not pure-shape classifications.

### Methodology reference for future pattern-catalog expansion (added 2026-04-28):

- **Lo, Mamaysky, Wang (2000) — "Foundations of Technical Analysis"** (Journal of Finance 55(4), pp. 1705–1765; PDF at `https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf`; full reference entry in `reference/Future Work/QuantEcon/external-references.md`). Canonical academic paper on algorithmic chart-pattern detection via Nadaraya-Watson kernel regression + geometric detection on local extrema. Pattern catalog: HS/IHS, broadening top/bottom, triangle top/bottom, rectangle top/bottom, double top/bottom — 10 patterns, NOT including flag/pennant/cup-handle/base. **Use as starting-point methodology reference if V2+ pattern scope ever expands beyond the current operator V2+ list to include head-and-shoulders, triangle, rectangle, or double-top patterns.** Replication caveats: 0.3×h* bandwidth is admitted ad-hoc tuning; effect sizes small (information, not profit); sample period 1962–1996 pre-modern-microstructure. Treatment: reference-only per V2.1 §VII.F; the operator-drives-agent-serves discipline (QuantEcon companion) flags academic methodology homogenization as a risk — Lo et al. is evidence base + methodology reference, NOT prescription.

### V2 capability extensions:

- **Sort-PARTICIPATING flag tag (operator-decision; affects production UX-priority).** V1 keeps `_sort_watchlist` byte-for-byte unchanged; flag tag is parallel render-only data via `pattern_tags`. Promoting to sort-participation would change watchlist ordering — affects production UX-priority surface and would require V2.1 §VII.F protocol.
- **Calibration study (algo vs operator agreement-rate).** Gated on 20+ overrides accumulated. Compares `chart_pattern_algo` vs `chart_pattern_operator` to surface algorithm bias / blind spots / threshold-mis-calibration. Output: tuning recommendations for `cfg.classifier.*` defaults and `cfg.web.flag_pattern_display_threshold`.
- **Slow-test live-fetch suite (`tests/evaluation/patterns/test_flag_classifier_live.py`, `@pytest.mark.slow`).** Exercises classifier against live yfinance pulls for upstream-data-format-drift detection. Deferred per V1 scope; useful when yfinance API changes or pandas/numpy upgrades land.
- **Tuning-history versioning.** Record `cfg.classifier.*` values per pipeline run alongside the cached classification. Currently `components_json` captures clearances but not the threshold values themselves; without history, retroactive analysis can't distinguish "operator override during low-tightness window" from "operator override after we tuned tightness threshold." Modest scope: extend cache schema, capture threshold dict at compute time.
- **Manual-trade fallback for out-of-chart-scope tickers.** V1 explicitly does not handle this — operator entering a trade for a ticker not in chart-scope sees "Not classified" stub with override surface hidden. V2 adds synchronous classifier fetch on form load (single-ticker yfinance pull + classifier run + persist). Adds entry-time latency (~1-3s for cold fetch); needs cache-warm check + circuit-breaker discipline.
- **Multi-timeframe classification (weekly + daily).** V1 is daily-only. Some patterns (cup-with-handle, long bases) are more naturally weekly. V2 extension: classifier accepts both timeframes; gates can require confirmation across timeframes.
- **Real-time / intraday classification.** Out of V1 scope; classifier runs on completed-bar daily data. V2 candidate if intraday execution becomes operator-relevant (currently it's not — daily-cycle workflow).

### V2 schema / hardening:

- **Schema-layer hardening for trades cross-column constraint.** V1 enforces the `chart_pattern_algo='flag' iff confidence IS NOT NULL` invariant at the repo layer (`insert_trade_with_event` raises `ValueError`). Schema-layer enforcement requires CREATE-COPY-DROP-RENAME migration — heavyweight. **Bundle with the next column-change migration on `trades`** to amortize the cost. Risk in the meantime: non-repo writers (raw SQL via sqlite3 CLI, future migrations) can violate the invariant.
- **Hidden form-field tampering hardening for chart_pattern_classification_pipeline_run_id.** V1 accepts the field as operator-claimed input from a hidden form field (per §3.6 threat model: "operator-claimed input, not server-verified provenance"). For personal-use single-operator scope this is acceptable residual risk. V2 hardening: re-resolve cache at submit + validate against form-supplied pipeline_run_id; refuse if mismatched.
- **Dashboard banner for classifier-error count per pipeline run.** V1 emits `logger.warning` per-ticker on classifier exception + end-of-step error count summary log line. Dashboard surface deferred — pipeline logs cover the operational visibility gap. V2 surface = banner showing "Pipeline N had X classifier errors" with drill-down to which tickers.

### Process / lessons-derivative:

- **`swing/web/watchlist_ranking.py` module extraction (per 2026-04-26 deferred item) — natural place to land flag-tag separation if extracted.** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, `_flag_tags` currently in `swing/web/view_models/dashboard.py`; flag-tag rendering also lives in `_pattern_tags`. Bundling all tag/sort logic in one module clarifies ownership and provides a single edit point for future pattern additions.
- **§1.2 doc inconsistency fix.** Spec §1.2 item 2 originally said "three trade columns" but R4 added a 4th (audit anchor). Fixed in this housekeeping commit; preserved as a lesson on doc/spec drift across adversarial review rounds.
- **d266e5f commit message says "R3 fixes" but is actually R4 fixes.** Implementer flagged; preserved per no-amend rule. Commit substance is correct; only the message header is inaccurate.

---

## 2026-04-27 chart-pattern flag-v1 V1-ship gates (operator-paced; long-horizon)

> Tasks 7.1 + 7.2 SHIPPED via Phase 7 implementer-side dispatch (archived). Tasks 7.3 + 7.4 retained here as operator-paced; cross-referenced from `docs/orchestrator-context.md` §"Currently in-flight work."

- **Task 7.3 (operator-paced fixture labeling, ≥15 fixtures)** — operator's earlier framing: blocked more by external constraints (figuring out best way to label) than by orchestrator-side bandwidth. No urgency. Loader + parametrized test infrastructure shipped at `tests/evaluation/patterns/fixtures/README.md` + `test_flag_classifier_integration.py`.
- **Task 7.4 (FP-biased classifier tuning checkpoint)** — gated on Task 7.3. Per Q2 (2026-04-27): operator does manual FP/FN classification from pytest output; no automated aggregator added in V1. Tune `cfg.classifier.*` if FP > FN per spec §3.1.4.

---

## 2026-04-27 chart-pattern flag-v1 manual verification round 1 — Tier 3 operator-design questions (retained)

> Tier 1 (mathtext fix) + Tier 2 (chart-image route + open-positions expand + chart-scope alignment) + Tier 4 (verification doc fixes) all SHIPPED — see archive. Tier 3 items retained here; also cross-referenced from `docs/orchestrator-context.md` §"Operator-paced items."

5. **Lightning icon trigger logic re-evaluation.** Current rule: `price >= 0.99 × entry_target`. Operator surfaced concern that simple "near pivot" indicator may not be the right "actionability" signal post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine). Options enumerated in `docs/chart-pattern-flag-v1-manual-verification-results.md`.
6. **Multiple concurrent advisories vs single price-stop field.** Open positions can show multiple trail-stop advisories (e.g., 10MA + 20MA based) but trade row supports only one stop value. Reconciliation needed: state-machine when stop adjusted to satisfy one but not all advisories. Phase 3d follow-up. _Operator framing recorded 2026-04-27 (verification-results doc §#6): maximum-communication principle — annotate, don't suppress; trade-maturity gating concept (default 20MA early, upgrade to 10MA after ~+1.5-2R)._

---

## 2026-04-28 chart-scope policy v3 (4th tier `hypothesis_rec`) — operator-paced deferral

> Chart-scope policy v2 SHIPPED 2026-04-28 (`c4820d0..527e334`); follow-up V1-deferred items + hyp-recs trade-prep expansion design — all archived. v3 retained as the only OPEN item.

**Original deferral per hyp-recs trade-prep expansion brainstorm Q2 (2026-04-28):** "Chart unavailable message for now is fine. We may eventually adjust the rules for when charts are created, that will be explicit direction from me if/when I feel the workflow needs it."

**2026-04-30 reaffirm-deferral signal:** operator took CC trade (hyp-rec; Sub-A+ VCP-not-formed); chart was unavailable per design (CC not in `aplus + open_position + tag_aware_top_n`). Operator wanted to view chart for hyp-rec trade-decision; "Chart unavailable" was working as designed but cost was real. **Operator decided to keep deferring** rather than dispatch v3 now. Trigger condition was nearly hit; track future occurrences as accumulating signal.

**Fix scope when picked up:** mirrors chart-scope policy v2 cycle structurally — migration 0013 extends `pipeline_chart_targets.source` CHECK to allow `'hypothesis_rec'`; resolver gains 4th tier (`aplus > open_position > tag_aware_top_n > hypothesis_rec`); pipeline `_step_charts` enumerates hyp-recs and renders charts. Cost: +5-15 chart renders per pipeline run (bounded by hyp-recs panel size). With Phase 3 OHLCV archive shipped, the yfinance cost is mostly archive cache hits. Brainstorm-skip viable when picked up — Q1-Q6-equivalent of v2 already known.

---

## 2026-04-30 Phase 4 cleanup-remainder follow-up

- **(2026-04-30 Phase 4 Task 7 follow-up) Promote 7-day staleness threshold to a public constant in `swing/data/ohlcv_archive.py`.** Phase 4 Task 7 inlined a `_STALENESS_THRESHOLD_DAYS = 7` class constant in `research/parity/run.py:_CountingPriceFetcher` because the data-layer's predicate is inlined at line 205-210 with no public symbol; promoting it would have required a `swing/data/` carve-out beyond Phase 4 scope (research-branch rewrite). **Risk:** if the data-layer threshold ever changes from 7, the wrapper's duplicate must be updated in lockstep — easy to miss. Promote when a `swing/data/ohlcv_archive` touch becomes natural (next archive-related dispatch).

## 2026-04-30 TOS reconciliation depth follow-ups (BUNDLED — single dispatch)

Surfaced after operator dry-ran + reconciled the 4/30 Schwab/TOS export against the production DB. Current `reconcile_tos` only verifies a SUBSET of the disagreement surface; three concrete gaps where TOS-vs-DB drift would pass reconciliation silently. **Operator decision 2026-05-01: bundle all three as a single dispatch ("real reconciliation depth").** Estimated half-day; not orchestrator-blocking; pick up when operator-prioritized vs Phase 5 / Tier-3 #6 / chart-scope-v3.

### What `reconcile_tos` verifies today (audit-trail anchor):

- **OPEN fill (BUY TO OPEN):** ticker + entry_date + qty matched against `find_open_trade_by_match`; entry_price compared with `price_tolerance` (default $0.01). Mismatches surface in `price_mismatch_fills`.
- **CLOSE fill (SELL TO CLOSE):** ticker matched against `find_any_open_trade`; cumulative qty across the batch ≤ `initial_shares`. **No price comparison.** No-match attempts a historical-claim against unclaimed recorded exits before falling through to `unmatched_close_fills`.
- **`Account Order History` section:** parsed by `parse_tos_export` but NEVER consumed by `reconcile_tos`. Working orders, stops, OCO triggers — all silently dropped.
- **`Equities` section, `Profits and Losses` section, `Account Summary` net-liq:** not parsed at all (sections aren't in `_SECTION_LABELS`).

### Gaps to address:

- **(1) CLOSE-fill price-mismatch detection.** Symmetric to the OPEN-fill check at `swing/journal/tos_import.py:193-194`. If TOS reports `SLD -5 X @42.50` but the recorded exit's `exit_price = 42.30`, surface to `price_mismatch_fills` (or a sibling `close_price_mismatch_fills` field if separate categories matter). Small fix (~30 min): in the CLOSE branch (line 208-244), after a successful match, compare `f.price` to the matching exit's price and route to the mismatch list. Need to identify WHICH exit row matched the fill — currently the live-allocation branch doesn't track that explicitly. Likely need to refactor the within_batch_alloc tracking or add an exit-id lookup. **Test:** seed an open trade with a recorded partial exit at $42.30; pass a TOS CSV with a CLOSE fill at $42.50; assert it surfaces as price_mismatch.

- **(2) Stop-order reconciliation against `Account Order History`.** TOS exports include WORKING SELL TO CLOSE stop orders in this section (e.g., the operator's 4/30 CSV has CC stop at `20.51` and DHC stop at `7.06`). `reconcile_tos` currently parses but ignores the section. Add an extractor for the STP rows + a new report category `stop_mismatches: list[(ticker, db_stop, tos_stop)]`. For each open trade, look up the corresponding TOS WORKING stop; compare `current_stop` with the TOS stop price within `price_tolerance`. Surface mismatches. ~1-2 hr including parser + reconciliation logic + tests. **Notable parser challenge:** the Order History section has variable columns + the stop value lives across two row types (`TRG BY #ref` parent row + child row with the actual stop price); needs careful parsing. **Test:** seed open trade with current_stop=20.00; pass TOS CSV with WORKING stop at 20.51; assert mismatch surfaces.

- **(3) Position-level holdings reconciliation against `Equities` section.** TOS lists current open quantities per ticker (e.g., operator's 4/30 CSV shows `CC +5` and `DHC +39`). DB's `list_open_trades` should agree, factoring partial exits. Add `Equities` to `_SECTION_LABELS` + an extractor + a new report category `position_mismatches: list[(ticker, db_qty, tos_qty)]`. Catches "TOS shows 5 shares CC; DB shows 0 shares CC" (or vice versa) — most likely cause is an unrecorded partial exit OR a missed entry. ~1-2 hr including parser + tests. **Test:** seed open trade with 5 shares + 0 exits; pass TOS CSV showing only 3 shares for that ticker; assert mismatch surfaces.

### Bundle dispatch shape (when scoped):

Single brainstorm-skip writing-plans dispatch covering all three gaps; one schema-free implementation across `swing/journal/tos_import.py` + `tests/journal/test_tos_import.py`. Real-world fixture base: operator's 4/30 Schwab/TOS export at `thinkorswim/2026-04-30-AccountStatement.csv` exercises stops + Equities; pair with synthetic permutations for edge cases (qty mismatch, price mismatch, missing stop, ticker-not-in-DB). Per-gap tasks roughly: Task 1 close-fill price-mismatch (cheapest symmetric fix); Task 2 Order-History parser + stop reconciliation; Task 3 Equities-section parser + position-qty reconciliation; Task 4 CLI report integration (display the new mismatch categories). Done criteria includes operator-witnessed dry-run against the 4/30 CSV showing all three new categories surface zero mismatches (production DB is correctly reconciled today; the new checks should confirm the existing matched state, not flag false positives).

### Cross-references:
- `swing/journal/tos_import.py:reconcile_tos` (current verification surface).
- `swing/journal/tos_import.py:_SECTION_LABELS` (parsed sections; extend for Equities + others).
- 2026-04-30 TRD-as-withdrawal fix (`c9159c7`) — same module; same operator-surfaced via 4/30 export.
- `tests/fixtures/tos/synthetic-tos.csv` — current synthetic fixture only covers entry+exit fills + DEP/WD cash flow. Bundle dispatch should extend it.
- 2026-05-04 Schwab API integration entry below — Phase A subsumes this bundle (API surfaces close-price + stop + position-qty natively).

## 2026-05-01 Journal v1.2 incorporation (Phases 6-9)

> **Phase 6 SHIPPED 2026-05-04 at `51c79ed`** + **Phase 7 SHIPPED 2026-05-05 at `c617777`** — full per-phase detail in archive. This active entry retains cross-cutting framing + Phase 8/9 (gated on Phase 7) + sequencing alternatives + modification rationale.

Sourced from operator-commissioned research at `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` (and the v1.0 → v1.1 → v1.2 evolution chain at `reference/Future Work/Trading Journal/swing_trading_journal_*.md`). v1.2 is a discretionary-trader's journal spec; OUR platform is a framework-research-loop. The phases below adopt v1.2's discipline scaffold WHERE it adds value over our existing infrastructure, modify it WHERE its assumptions conflict with our framework-driven flow, and DROP elements we don't need (pyramiding, Setup_Playbook as DB rows, Screen_Definitions versioning).

**Umbrella sequencing decision (operator 2026-05-01):** Decompose into four phases by value × independence; ship Phase 6 first as the cheapest highest-value piece, re-evaluate before committing to Phase 7's larger schema disruption. Phase 6 + Phase 7 SHIPPED; Phase 8 + 9 unblocked, operator-paced.

### Cross-cutting framing (applies to all four phases):

- **v1.2 assumes self-rated quality scoring.** Drop self-rated components that the pipeline asserts (valid setup, regime supportive, sector supportive). Keep operator-only fields (emotional_state, confidence_score, manual override-of-doctrine).
- **v1.2 assumes operator-composed thesis.** Adapt to "thesis = pipeline bucket + criteria tags + hypothesis_label" + operator-added context (why_now, invalidation_condition).
- **v1.2's `trade_origin` enum** maps onto our actual ingestion paths: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` (4-value, NOT v1.2's 7-value discretionary enum).
- **Setup_Playbook as DB entity:** DROP. Our setups are encoded in `swing/evaluation/scoring.py` + `criteria.py`; v1.2's setup_id maps to our `hypothesis_id` + doctrine layer.
- **Screen_Definitions versioning:** DROP. `finviz_schema.py` is git-versioned; explicit screen-version entity adds friction without value.
- **Pyramiding R-views (R_initial / R_effective / R_campaign):** DROP. Operator at $7,500 capital, 5 concurrent, no pyramiding plan.
- **Drawdown circuit breaker:** v1.2 defaults this opt-in disabled; align (do not enable by default).

### Sequencing alternatives (for future re-evaluation):

- **(A) Phase 6 only, defer 7-9 indefinitely.** Operator stops journal extension at the cheapest piece. Acceptable if Phase 6 turns out sufficient.
- **(B) Phase 6 + 9, defer 7 + 8.** "Journal Lite" — post-trade review + risk policy + reconciliation depth. Skips state-machine + Daily_Management.
- **(C) Full sequence 6 → 7 → 8 → 9.** Multi-month commitment to full v1.2 equivalence.
- **(D) Defer all of v1.2 until first hypothesis closure.** Per orchestrator-context lesson: "the actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence." If journal-discipline-measurement isn't bottlenecking the loop today, defer engagement until a hypothesis closes and "did the framework work?" requires deeper retrospective tooling.

**Outcome (2026-05-05):** Phase 6 + Phase 7 shipped along path (C). Phase 8/9 sequencing decision pending evaluation soak of Phase 7 production behavior.

### Modification rationale (why we don't adopt v1.2 verbatim):

v1.2 was authored agnostic of our platform. Several design choices encode discretionary-trader assumptions that don't fit our framework-research-loop:

| v1.2 assumption | Why it doesn't fit | Our adaptation |
|---|---|---|
| Trader independently composes thesis per trade | Our framework asserts thesis via bucket + criteria + hypothesis_label | Keep thesis as text field but auto-pre-fill from candidate row + hypothesis matcher; operator adds context |
| Self-rated `pre_trade_quality_score` 0-10 | Pipeline already computes A+/watch/skip + criteria pass/fail; self-rating duplicates and conflicts | Drop self-rated framework components; keep emotional_state, confidence_score, manual override |
| Setup_Playbook as DB rows with status active/pilot/paused/retired | Our setups are encoded in `swing/evaluation/`; trader doesn't manage setups as data | DROP; reference hypothesis_id when setup-attribution needed |
| Pyramiding R_views | Operator at $7,500 capital with 5 concurrent doesn't pyramid | DROP indefinitely |
| `trade_origin` 7-value discretionary enum | Our ingestion is pipeline-driven (4 paths) | 4-value pipeline-aware enum: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` |
| Drawdown circuit breaker | v1.2 default opt-in disabled (matches our caution) | Align: opt-in disabled by default |

---

## 2026-05-06 Phase 10 metrics dashboard — **brainstorm SHIPPED 2026-05-06 at `fe6cb45`**

> **Outcome:** Operator-commissioned external research at `reference/Future Work/Metrics/` (5 docs: v1.0 baseline + v1.1 + v1.1-alternate + findings + rebuttal-determinations) — orchestrator-thread analysis confirmed v1.1-alternate as structural baseline + identified framework-fit gaps requiring NEW design (hypothesis-cohort as primary axis; tier-comparison; capital-friction; maturity-stage; identification-vs-trade-funnel; deviation-outcome; process-grade-trend). Brainstorm-dispatched 2026-05-06; brief at `docs/phase10-metrics-brainstorm-brief.md` (`3ad5ea2`). Spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` (641 lines; commits `a46b458` + `fe6cb45`; 5 substantive Codex rounds + R6 confirmation → `NO_NEW_CRITICAL_MAJOR`). Three highest-leverage locked decisions: (1) **capital-denominator split-policy** — governance metrics lock to constant `$7,500`; operational/live-state metrics PROVISIONAL with `$7,500` fallback until §8.2 resolves; (2) **global statistical-confidence floor** `n=20` decoupled from cohort target; (3) **tier-comparison view** explicitly avoids false-significance signals (text-only `cohort_ci_overlap_descriptor`; no boolean flag). Mistake-cost formula DECISION: brainstorm AFFIRMS Phase 6's already-shipped v1.1-alternate / v1.2 §8.8 formula (the brief's §1.5 premise that Phase 6 ships v1.1-main was empirically wrong; Phase 6 already ships the correct formula at `swing/trades/review.py:157-174`). Spec §11 enumerates capture-needs feedback for Phase 8 (consumed) + Phase 9 + Phase 10+. **Sequencing locked: brainstorms 10 → 8 → 9; execution order 8 → 9 → 10.** RESEARCH-posture (no schema/code; only metric definitions + dashboard sketches + capture-needs feedback). Per retention discipline, this entry stays in active until next phase ship.

### Open follow-ups from Phase 10 brainstorm (operator-paced)

- **§8.6 — Surface `lucky_violation_R` on Phase 6 review form.** Phase 6 already computes + persists `total_lucky_violation_R` (per migration 0013); review form does NOT surface the per-trade or cohort field. Operator concurred with implementer's recommendation: small standalone follow-up dispatch (~30 min), separate from Phase 10 writing-plans. Not bundled with Phase 10 because it's Phase-6-surface-extension, not metrics-dashboard scope. Pick up when bandwidth allows.
- Other open questions (§8.1 fills.action enum gap; §8.2 daily equity capture; §8.3 benchmark series location; §8.4 Corporate_Actions MVP; §8.5 process_grade_rolling_N window; §8.7 decision-criteria automation) — operator concurred with implementer's recommendations across all 7. Bundled with Phase 10+ writing-plans + execution unless re-litigated.

### Open follow-ups from Phase 8 writing-plans dispatch (operator-paced)

- **V2 CLI `swing trade event-log` follow-up.** Phase 8 plan §A.2 deferred CLI per Phase 6 review surface web-only-V1 precedent. Schema + service are CLI-agnostic; landing wire-up estimated ~1-2 hours. Pick up when convenient post-Phase-8-ship; dispatch shape: small standalone CLI dispatch (mirror Phase 6 review CLI pattern at `swing/cli.py` review-command region; reuse Phase 8's `record_event_log` service helper).

### Phase 8 V1 follow-ups (operator-witnessed gate observations 2026-05-07)

> **Status: BOTH SHIPPED to main 2026-05-08 at integration merge `24b3e9a`** (worktree branch `worktree-phase8-v1-polish` → main; 16 commits = 12 task-impl + 4 adversarial-fix). Plan: `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`. Test count delta: 2079 → 2090 (+11 fast tests). Ruff baseline 78 preserved. Schema unchanged at v16. Writing-plans 2 Codex rounds + executing-plans 3 Codex rounds → both NO_NEW_CRITICAL_MAJOR; convergent shape (executing-plans tapered 3→1→0 majors; sort-key tiebreak hardened in `7c08f12` from R1 finding). 4-surface operator-witnessed gate PASS via Chrome MCP walkthrough 2026-05-08 (Surface 1 Detail button on every open-position row; Surface 2 timeline union surfaces orphan stop-adjusts on DHC chronologically; Surface 3 dedup via `linked_trade_event_id` correctly suppresses Phase-8-form-written trade_events; Surface 4 regression-spot-check across all 7 routes). Three V2 advisory items captured at the §"Phase 8 V2 advisory items" subsection below. Per retention discipline this entry stays in active until next phase ship.

- **Phase 7 stop-adjust legacy path doesn't surface in Phase 8 timeline (Surface 6 finding).** ~~When operator uses the dashboard's "Adjust stop" button (Phase 7 route at `/trades/<id>/stop`), the resulting `trade_events` row IS audit-trailed but does NOT appear in Phase 8's per-trade `daily-management-timeline` view~~ — **SHIPPED.** Took path (a): VM-level read-side union. `build_daily_management_timeline_vm` now unions Phase 7 orphan `trade_events` of `event_type='stop_adjust'` (those NOT linked via `daily_management_records.linked_trade_event_id`) into the timeline, rendered as `record_type='trade_event_legacy'` with badge "Stop adjustment (legacy quick-adjust)".
- **No dashboard → bare detail page navigation link.** ~~Operator can navigate to `/trades/<id>` only via direct URL~~ — **SHIPPED.** `partials/open_positions_row.html.j2` now emits `<a href="/trades/{id}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>` after the existing Exit + Adjust stop buttons.
- **emotional_state form preserves stale checkbox state across browser visit cycles.** When operator visually toggles checkboxes during inspection (without submitting), those checkmarks persist in browser form state through subsequent navigations away + back to the detail page. Cosmetic; potentially confusing for next-time submission. **Fix:** form re-render on detail-page GET should explicitly clear any preserved checkbox state (re-initialize `vm.emotional_state_set` to `()`). May require deeper investigation of where the persistence comes from (server-side render OR browser autofill). Defer until operator confirms confusion; not a correctness issue.
- **Spec wording vs implementation: "GAP-FLAGGED" → "gap-by-absence".** Phase 8 spec §2.2 + Surface 5 brief-language said gap-handling would "flag missed-day in §7.2 timeline as `(no snapshot — pipeline did not run)`"; actual implementation is gap-by-absence (no row written for missed days; operator infers gap from row-date discontinuity in timeline). Functionally equivalent (operator sees the gap visually) but spec-vs-impl wording mismatch. **Fix:** Phase 8 V2 adds explicit placeholder rows in timeline for missed days OR spec amended to match gap-by-absence. Defer until operator naturally encounters a gap workflow + confirms whether explicit placeholders would be useful. Cosmetic.
- ~~**Worktree husk `.worktrees/phase8-daily-management/` ACL-locked at integration merge.**~~ **RESOLVED 2026-05-07** (operator-elevated cleanup performed). Same Windows ACL pattern as Phase 6/7 cleanup leftovers; cleared via existing `cleanup-locked-scratch-dirs.ps1` extension landed at `5430c1c`.

### Phase 8 V2 advisory items (surfaced 2026-05-07 writing-plans + executing-plans phase8-v1-polish)

Three non-blocking advisories surfaced during phase8-v1-polish dispatches (2026-05-07; plan at `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`). All noted as out-of-scope for V1 polish; surfaced here so they don't decay.

- **Audit-chain symmetry: legacy `/trades/{id}/stop` route also writes Phase 8 event_log row.** V1 polish surfaces legacy stop-adjusts via read-side VM union; does NOT write Phase 8 audit rows for them. If operator eventually wants the timeline uniformly Phase-8-shaped (every stop-change has both a `trade_events` row AND an `event_log` row with `linked_trade_event_id`), the legacy route should be refactored to call `record_event_log` atomically instead of writing only `trade_events` directly. ~3-4 hr standalone dispatch (route + tests + audit-chain alignment). Defer until operator surfaces a workflow gap that this would close.
- **Template `data-trade-event-id` attribute for orphan rows.** Plan §A.2 sort-tiebreak uses `-trade_events.id` for orphan rows; the template currently exposes `data-timeline-record-id="-{event.id}"` (negative-int-from-positive-PK). If a future feature deep-links to a specific orphan row (e.g., notification → "your stop-adjust on AAPL was logged as legacy"), parsing the negative ID is awkward. A dedicated `data-trade-event-id` attribute on `trade_event_legacy` rows would be cleaner. ~15 min cosmetic; defer until first deep-link consumer surfaces.
- **Read-side snapshot consistency for `build_daily_management_timeline_vm` (R2 acceptance, 2026-05-07).** Surfaced by adversarial-critic R1 Major 2 + clarified by R2 Major 1. The VM build issues two sequential SELECTs (`list_for_trade_timeline` then `list_events_for_trade`) without a wrapping read transaction. Python's default `sqlite3` isolation does NOT escalate SELECT-only flows to a snapshot read; `with conn:` only manages commit/rollback on exit. If a `record_event_log` COMMIT lands BETWEEN the two reads, the timeline VM can compute `linked_event_ids` from a pre-commit `records` view while seeing the post-commit `trade_events` row in `events` — producing a false "(legacy quick-adjust)" row that omits the canonical Phase 8 `event_log` row for the same change. Impact framing (R2-corrected): NOT a microsecond UI flash; the rendered HTML page persists with the wrong content until the operator refreshes or navigates. Underlying tables stay correct (no data corruption). Probability: very low on a single-operator desktop app (Windows, journal_mode=delete, single FastAPI worker process; the operator must submit the Phase 8 form AND view the same trade's detail page via separate concurrent requests AT exactly the moment the read interleaves with the commit). Fix options: (a) collapse the union into a single SQL query JOIN (clean V2 refactor); (b) manually `BEGIN DEFERRED + COMMIT` around both reads (requires `conn.isolation_level=None` manipulation that ripples through the function's call chain). Both options exceed V1-polish dispatch scope; banked here for V2.

---

## 2026-05-04 Finviz Elite API integration — **SHIPPED 2026-05-06 at `002338a`** (V1)

> **Outcome:** Brainstorm-skipped per operator + orchestrator in-thread design lock 2026-05-05 (Q1-Q8 from the original queued entry below answered + locked + Q-bonus on file-collision policy). Writing-plans dispatch shipped plan `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (5 Codex rounds → NO_NEW_CRITICAL_MAJOR; HEAD `734ba6f`). Executing-plans dispatch on worktree branch `finviz-api-integration` (BASELINE_SHA `734ba6f`); 17 task-anchored commits + 5 Codex-fix commits; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR. Operator-witnessed verification gate 2026-05-06: 1 mid-verification fix (`code-review I1` at `0e02ed6` — `swing/data/repos/finviz_api_calls.py:insert_call` removed internal `conn.commit()` that was breaking `lease.fenced_write()` contract on the pipeline path; CLI raw-conn path now commits explicitly); all 8 surfaces PASS post-fix. Integration merge `002338a`. Test count delta: +63 fast (1877 → 1940) + 2 slow live tests; ruff baseline 78 preserved. Production DB at schema_version 15 with new `finviz_api_calls` audit table. New `swing/integrations/` namespace established as pattern for future Schwab API integration. New CLI: `swing finviz fetch` + `swing finviz status`. Drift-detection signature-hash + WARNING emission verified via DB-tamper test (Finviz API URL params fully define the screen — no saved-screen-handle to edit on UI side per writing-plans research finding). Two new lessons captured in `docs/orchestrator-context.md` §"Lessons captured": subprocess cfg-propagation (Codex R2 finding; child-process CLI body is binding override point) + repo-functions-must-not-commit (operator-witnessed I1 finding). Per retention discipline, this entry stays in active until next phase ship; original queued content retained below for historical reference.

### Current state (orchestrator survey 2026-05-04):

- **Manual ingestion:** operator exports a Finviz screen as CSV with 13 specific columns (`No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`); names file `finvizDDMmmYYYY.csv`; drops in `data/finviz-inbox/`.
- **Validator:** `swing/pipeline/finviz_schema.py:12` checks 13-column schema; missing columns → reject to `data/finviz-inbox/rejected/` with sidecar JSON.
- **Pipeline consumption:** `_step_evaluate` reads the CSV, ingests rows as candidates, drops Sector/Industry until Phase 4 wired them.
- **Cadence:** daily (operator's actual workflow per `docs/cycle-checklist.md`).
- **Failure modes today:** wrong column count (rejected); wrong filename pattern (silently skipped); operator forgot to export (pipeline runs against stale or empty inbox).

### V1 scope (sketch — pre-brainstorm):

1. **`swing/integrations/finviz_api.py`** — auth (API token from a new `cfg.integrations.finviz.token` field; persist in user-config TOML per Phase 5 infrastructure, NOT tracked toml). Wraps the Finviz Elite REST endpoint with the operator's saved-screen-id parameter.
2. **Pipeline ingestion path** — new `_step_finviz_fetch` runs BEFORE `_step_evaluate`; pulls latest screen results; emits to the same 13-column CSV format in `data/finviz-inbox/` (preserves the existing validator + rejected-fallback pattern). Manual CSV drop remains supported as fallback if API unavailable.
3. **Structured logging** — per-call: timestamp, screen_id, row count, response time, rate-limit consumed, rate-limit remaining; persisted to a new `finviz_api_calls` table (or appended to `pipeline_runs.notes`); surfaced on dashboard pipeline-status surface.
4. **CLI parity** — `swing finviz fetch` command for ad-hoc invocation outside the pipeline; `swing finviz status` for rate-limit + recent-call inspection.
5. **Config surface** — add `[integrations.finviz]` section with token + screen_id + (optional) timeout/retry params; surface in Phase 5 config page in V2 if operator wants edit access.

### Open design questions (for brainstorm dispatch):

1. **Cost confirmation.** Finviz Elite is a paid subscription (~$40/mo). Confirm operator is on Elite OR plans to subscribe before any work commits. If not, this entry stays QUEUED indefinitely.
2. **Screen-id management.** The screen is currently a saved Finviz user-screen (operator-created). API likely requires a screen_id reference. Persist as cfg field; surface in config page as V2.
3. **Rate-limit handling.** Finviz Elite API documents rate limits (TBD: needs operator-confirmed quota). Pipeline cadence is daily so likely fine; ad-hoc CLI invocations need backoff.
4. **Schema-parity verification.** Verify Finviz API response fields map 1:1 to the 13-column CSV schema. If API returns different column set, the integration layer normalizes before emitting to the canonical schema (same validator runs).
5. **Failure fallback.** If API returns error / rate-limit-exceeded / network failure, pipeline should LOG and skip — not fail the entire run. Operator can drop a manual CSV as backup.
6. **Token storage.** API token is sensitive; persist in user-config TOML (per Phase 5 infrastructure, outside Drive) NOT in tracked `swing.config.toml`. Revisit if Phase 9 introduces a secrets-management layer.
7. **Sector/industry consistency.** Phase 4 wired Sector/Industry from the CSV; API-emitted CSV must preserve same field names + values to avoid breaking the existing pipeline ingestion.
8. **Screen-version drift.** The operator's saved screen on Finviz can be edited; API call would silently start returning different rows. Capture screen-id + (if available) screen-version-hash on each fetch; surface drift detection on dashboard.

### V1-deferred / V2:

- **Multi-screen support** (operator currently runs one screen; future: A+ screen + watchlist screen + research screen).
- **Backfill mode** — pull historical screen results for evidence-loop research (depends on Finviz Elite API supporting historical-screen endpoints; unverified).
- **Real-time price feed** (Finviz Elite has a price stream; out-of-V1; redundant with potential Schwab API integration below).

### Cross-references:

- `swing/pipeline/finviz_schema.py:12` (validator — preserve schema contract).
- `data/finviz-inbox/` (canonical drop directory; preserve as fallback).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.finviz` section).
- `docs/cycle-checklist.md` (daily operator workflow — fetch step replaces manual export).
- 2026-05-04 Schwab API integration entry below (may share `swing/integrations/` namespace + secrets-management approach).

---

## 2026-05-04 Schwab API integration (QUEUED; Large effort; multi-phase; brainstorm needed)

Operator-surfaced 2026-05-04. Three concurrent uses of the official Charles Schwab Trader API (https://developer.schwab.com/): (1) automate account reconciliation (replace TOS-CSV-import workflow + subsume the queued 2026-04-30 TOS reconciliation depth bundle); (2) potentially automate trade entry/exit/stop-management; (3) provide an alternative data source to yfinance (real-time prices + intraday OHLCV + fundamentals — addresses 4+ yfinance gotchas in CLAUDE.md). This is a comparable-to-Phase-7-9-scope multi-phase commitment; not a single dispatch.

### Current state (orchestrator survey 2026-05-04):

- **Operator already on Schwab.** `thinkorswim/2026-04-30-AccountStatement.csv` is the manual TOS export; production DB has 3 trades reconciled against it.
- **TOS-CSV reconciliation:** `swing journal import-tos` reads the CSV; `reconcile_tos` verifies a SUBSET of disagreement surface (entry-fill price-mismatch only; gaps for close-price, stop-orders, position-qty per the queued 2026-04-30 TOS bundle).
- **yfinance is the SOLE production data source** — historical OHLCV (consolidated archive at `swing/data/ohlcv_archive.py` after Phase 3 OHLCV consolidation 2026-04-30); price fetcher (`swing/prices.py PriceFetcher`); `_step_charts` chart fetch. Multiple production-impacting yfinance API regressions captured in CLAUDE.md gotchas.
- **No trade automation today** — all entry / exit / stop-adjust go through manual CLI or web form; trader places orders manually in Schwab/TOS UI.

### V1 scope (sketch — pre-brainstorm; multi-phase decomposition):

**Candidate library:** [Schwabdev](https://github.com/tylerebowers/Schwabdev) — unofficial Python wrapper for the Schwab Trader API; covers OAuth 3-legged flow + account/positions/orders/quotes/streamer endpoints. Evaluate at brainstorm time vs build-from-scratch (see design question 1 below).

**Phase A — OAuth + read-only account access (cheapest first):**
1. **Schwab Developer Portal app registration** (operator action; production-access approval can take days).
2. **`swing/integrations/schwab/auth.py`** — OAuth 3-legged flow; refresh-token persistence in user-config TOML (parallel to Phase 5 infrastructure). If Schwabdev adopted, this layer is a thin wrapper around Schwabdev's auth handling rather than rolling our own.
3. **`swing/integrations/schwab/account.py`** — read-only: positions, balances, transactions. Maps to current `tos_import` data shape.
4. **`swing journal reconcile-schwab`** CLI — replaces `swing journal import-tos` for the API-available account-state surfaces. CSV import path remains supported as fallback.
5. **Subsumes the 2026-04-30 TOS reconciliation depth bundle** (close-price + stop + position-qty mismatch detection) — API surfaces these natively; no CSV-parsing edge cases.

**Phase B — Alternative data source (highest-value second):**
6. **`swing/integrations/schwab/market_data.py`** — quote, OHLCV (daily + intraday), fundamentals. Wrap with same interface as `swing/prices.py PriceFetcher` so caller code is data-source-agnostic.
7. **`cfg.data_source.primary`** = `"yfinance" | "schwab"` (default `"yfinance"` for V1; flip to `"schwab"` after parity verification). Per-call fallback if primary errors.
8. **Parity verification harness** — research-branch dispatch comparing yfinance vs Schwab on N tickers × M sessions; document divergence (price + dividend-adjustment + corporate-action handling).
9. **Replaces multiple yfinance gotchas** — `Ticker.history` `threads=` regression; `group_by='column'` MultiIndex; `interval=1d` partial-bar inclusion; rate-limit pressure.

**Phase C — Trade automation (highest-risk last; opt-in only):**
10. **`swing/integrations/schwab/orders.py`** — place stop-buy entry (per hypothesis-tagged trade discipline); place initial stop; modify stop on advisory-trail trigger.
11. **`cfg.trade_automation.enabled`** = `false` default; explicit operator opt-in per trade.
12. **Dry-run mode** — emit the order JSON without submitting; operator reviews + confirms manually OR commits to live submission.
13. **Audit log** — every API call logged with request + response + timestamp; persisted to a new `schwab_orders` table joined to `trades` for full audit trail.
14. **Bilateral verification** — every automated order followed by a Schwab API position-state read to confirm the order landed; mismatch → halt automation + alert operator.

### Open design questions (for brainstorm dispatch):

1. **Library choice: three candidates surfaced 2026-05-06.** Evaluate at brainstorm time:
   - **Schwabdev** (https://github.com/tylerebowers/Schwabdev) — wraps entire Schwab Trader API surface (auth/account/orders/market data/streamer); single-author; newer trajectory.
   - **schwab-py** (https://github.com/alexgolec/schwab-py) — by alexgolec who previously authored `tda-api` for the TD Ameritrade API; multi-year community-usage lineage; broker-API client design experience.
   - **Build-from-scratch** — direct Schwab Trader API integration in `swing/integrations/schwab/`; max control + max maintenance burden.
   Operator leaning toward schwabdev (2026-05-06) but explicitly evaluating at brainstorm time. Risks: unofficial wrappers can break on Schwab API changes; maintainer-bus-factor; supply-chain trust. For any wrapper choice, recommend vendored / version-pinned dependency + thin abstraction layer (`swing/integrations/schwab/client.py`) so swap-to-direct-API is bounded if the wrapper goes stale.
2. **Phase A vs Phase B vs Phase C ordering — operator preference.** Recommendation: A (account reconciliation) → B (data source) → C (trade automation). A is cheapest; B has highest yfinance-pain-relief value; C is highest-risk + lowest urgency at $7,500 capital with 1-2 trades/month pace.
3. **OAuth refresh-token storage location.** User-config TOML (per Phase 5)? New encrypted store? Operator's risk preference.
4. ~~**Schwab Developer Portal production-access approval time.**~~ **RESOLVED 2026-05-06.** Operator confirms Dev Portal app registration + production-access approval are both COMPLETE. The long-pole approval friction is gone — when Phase A is sequenced, brainstorm + writing-plans + executing-plans can dispatch immediately without external approval gating.
5. **Schwab API entitlements scope.** Read-only account vs trading entitlements require separate Schwab approvals; operator decides per-phase.
6. **yfinance vs Schwab data parity.** Adjusted vs unadjusted prices; corporate-action handling; dividend treatment; intraday-bar timestamping. Need a parity study before flipping `cfg.data_source.primary`.
7. **Trade automation safety gates.** Hard maximums (per-trade size; daily order count; circuit breaker on N consecutive failed orders); operator-defined override path.
8. **Subsumption of TOS-CSV bundle.** When Schwab API account access works, does the 2026-04-30 TOS reconciliation depth bundle get DROPPED or RETAINED as fallback for offline-mode? Recommendation: retain CSV path as fallback (defense-in-depth); but the queued depth-bundle work becomes lower priority since the API surfaces the same data natively.
9. **Sequencing vs Phase 9 (Risk_Policy + reconciliation depth).** Phase 9 from journal v1.2 covers reconciliation depth + Risk_Policy entity. Schwab API Phase A IS the reconciliation-depth implementation; logical merger is "Phase 9 ships using Schwab API as the data layer." Re-evaluate when both items ripen.
10. **Cost.** Schwab API access is free for account holders; no subscription cost like Finviz Elite. Approval friction is the primary cost.
11. **Failure fallback.** Trade-automation failure modes are operationally severe (failed entry on a hypothesis-tagged trade = lost evidence). Phase C MUST have explicit fallback-to-manual semantics + clear operator alerting.

### V1-deferred / V2:

- **Multi-account support** (operator has one trading account; future: separate research / paper-trading accounts).
- **Options trading** (out of framework scope; equity swing-trade only).
- **Schwab StreamerAPI** (real-time quotes via WebSocket; future if dashboard real-time price ticks become valuable).

### Cross-references:

- `thinkorswim/2026-04-30-AccountStatement.csv` (current manual reconciliation source; replaced by Phase A).
- `swing/journal/tos_import.py` (`reconcile_tos` + `extract_cash_movements`; CSV path retained as fallback).
- 2026-04-30 TOS reconciliation depth follow-ups bundle (subsumed by Phase A; lower priority once API works).
- 2026-05-01 Journal v1.2 incorporation Phase 9 (Risk_Policy + reconciliation depth — logical merger with Schwab API Phase A).
- `swing/prices.py PriceFetcher` (current yfinance interface; Phase B mirrors).
- `swing/data/ohlcv_archive.py` (Phase 3 consolidated archive; Phase B fetch path writes here for parity).
- CLAUDE.md gotchas (4+ yfinance regressions Phase B replaces).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.schwab` section).
- 2026-05-04 Finviz API integration entry above (shared `swing/integrations/` namespace + secrets-management approach).
- Schwabdev unofficial Python wrapper: https://github.com/tylerebowers/Schwabdev (candidate library; see V1 sketch + design question 1).

---

## 2026-05-05 Sector/industry tamper vector hardening (BACKLOG; SCHEDULED for Phase 9; low-stakes)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R3 Minor 2** (accepted-deferred per operator triage 2026-05-05; **operator-decided Phase 9 inclusion**). Sub-C C.3 entry route hardened the chart_pattern_algo + classification_pipeline_run_id round-trip with route-layer enum + FK existence + cache-content match validation (Codex R1 M1 + R2 M1 fixes). The sector + industry hidden-form snapshots have NO analogous server-side cache/content validation — a forged form POST could persist arbitrary sector/industry strings.

**Why low-stakes (today):** sector + industry are descriptive metadata only; they do NOT feed gating logic, A+ identification, hypothesis attribution, or trade-decision algorithms (per spec §11.3 + observations across `swing/evaluation/`). Compromising them produces wrong dashboard labels but does not corrupt correctness-critical paths.

**Why scheduled for Phase 9:** Phase 9 Risk_Policy entity introduces sector concentration limits (`max_sector_concentration_positions` per v1.2 §7.8). Once sector becomes a gating dimension, the tamper vector becomes correctness-critical — same severity as the chart_pattern_algo concern. Bundling the hardening into Phase 9 aligns the fix with the criticality elevation.

**V1 scope (executed within Phase 9):**
1. Route-layer Finviz-snapshot existence check at trade entry POST (mirror chart_pattern pattern in `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`).
2. Reject if `(ticker, action_session)` sector/industry snapshot doesn't match cached candidate row.
3. Same-shape route + test pattern as chart_pattern hardening.

**Estimated effort if triggered:** 1-2 hours (mechanical mirror of chart_pattern route-layer pattern).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R3 Minor 2 accepted-deferred + operator decision to schedule for Phase 9).
- `swing/web/routes/trades.py` chart_pattern hardening (commits `117dc97` + `2b9d6f3`) — fix-pattern template.
- Phase 9 Risk_Policy entity (sector concentration limits = trigger).
- v1.2 §7.8 `max_sector_concentration_positions` field.

---

## 2026-05-05 Fill.quantity fractional-share forward-compat (BACKLOG; gated on fractional-share feature)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R1 Major 3** (accepted-with-rationale per operator triage). `Fill.quantity` is REAL in schema (Sub-A migration 0014); ~7 modules currently truncate to int via `_ExitShape` adapters because all current production code paths produce integer-share fills (`compute_shares()` returns int; CLI/web/trim/exit all submit `shares: int`). Forward-compat concern: when fractional-share trading lands, the int truncation across 7 modules becomes a bug surface.

**Trigger:** future feature work introducing fractional-share trading. Most likely path: Schwab API integration Phase B (broker fills can be fractional in modern broker APIs) OR an explicit operator decision to trade fractional shares.

**V1 scope when triggered:**
1. Audit the 7 modules with `_ExitShape` int-truncation (enumerated in code comment at `swing/web/view_models/trades.py:_ExitShape` declaration per Sub-C R1 M3 ACCEPTED-with-rationale).
2. Refactor each consumer to handle REAL `quantity` correctly (display formatting; aggregation arithmetic; CLI parsing; web form input).
3. Update `compute_shares()` to optionally return float when fractional flag set.
4. Add Fractional-share-specific test coverage.

**Estimated effort if triggered:** 3-5 hours (mechanical type widening across 7 modules + format polish + tests).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R1 Major 3 accepted-with-rationale).
- `swing/web/view_models/trades.py:_ExitShape` declaration — code comment enumerates the 7 affected modules.
- Schwab API integration Phase B (`docs/phase3e-todo.md` 2026-05-04 entry) — likely activation trigger.

---

## 2026-05-04 Future schema migration: trade.entry_date datetime promotion (BACKLOG)

**Surfaced 2026-05-04 by Phase 7 Sub-B Codex R5 finding** (open question 2). Phase 7 keeps `trades.entry_date` as YYYY-MM-DD date-only TEXT column. The B.1 atomic-flow refactor's `_normalize_trade_event_date_to_iso` helper accepts the date-only `entry_date` + synthesizes the `T<HH:MM:SS>` portion for the entry-fill `fill_datetime`. Many downstream consumers call `date.fromisoformat(trade.entry_date)` directly (CLI hold-duration; `swing/journal/{flags,analyze}.py`; `swing/trades/advisory.py`; `swing/pipeline/briefing.py`; `swing/cli.py`).

**Why this is in the backlog:** any future schema migration that wants to promote `trades.entry_date` to ISO datetime (e.g., for sub-second precision; for tz-aware tracking; for richer chronology in research-branch back-tests) would need to migrate every `date.fromisoformat(trade.entry_date)` consumer. Scope is bounded but cross-cutting.

**Trigger:** future phase that has a use case for sub-day entry datetime precision (likely Phase 9 if Schwab API integration ships and broker fill timestamps become canonical) OR research-branch needs (intraday entry timing studies).

**Estimated dispatches if triggered:** 1 brainstorm (operator decides whether to promote vs keep date-only) + 1 writing-plans + 1 executing-plans (consumer audit + migration + per-consumer rewrite + tests).

**Cross-references:**
- Phase 7 Sub-B return report 2026-05-04 (open question 2).
- `swing/cli.py`, `swing/journal/flags.py`, `swing/journal/analyze.py`, `swing/trades/advisory.py`, `swing/pipeline/briefing.py` — current consumers of `date.fromisoformat(trade.entry_date)`.
- Phase 7 Sub-B `_normalize_trade_event_date_to_iso` helper (commits `e6541fe..71ddb95`) — established pattern for trade-chronology canonicalization at service boundary; likely the migration's API surface.
- 2026-05-04 Schwab API integration entry (Phase B market_data integration may surface intraday-precision needs).

## 2026-05-09 Chart pattern detection v2 — research captured (RESEARCH-CAPTURED; greenfield expansion; brainstorm-needed)

**Operator-surfaced 2026-05-09**: dropped three reference documents into `reference/Future Work/Chart Pattern Detection/` (committed `6b40292`). These describe research informing potential paths forward for expanding chart-pattern detection from the shipped flag-v1 classifier to a full swing-trading setup detector.

### Reference documents

- **`stock_chart_pattern_detection_ai_ingestion.md`** (v1.0) — generic original; surveys 9 mathematical approaches across all chart-pattern families.
- **`stock_chart_pattern_detection_delta_review.md`** — section-by-section critical review re-scoping for swing trading (Minervini/CANSLIM); adds VCP as headline pattern, Development Data Strategy, Drift Detection, Small ML Model Decision Analysis with G1-G7 implementation gates.
- **`stock_chart_pattern_detection_ai_ingestion_v2.md`** (v2.0; **canonical** — supersedes v1.0 per its frontmatter) — merged swing-trading-scoped analysis brief; 8-phase roadmap; rule-based + template-matching as production primary; ML re-ranker deferred 12-18 months gated on G1-G7.

### Trigger and effort estimate

**Trigger:** operator decision to expand beyond flag-v1 classifier scope. Likely sequence-locked after Phase 9 (risk_policy + reconciliation) + Phase 10 (metrics dashboard) ship, since outcome-distribution surfaces in the review interface depend on the metrics infrastructure being in place.

**Effort estimate (pre-brainstorm; speculative):** comparable-to-Phase-7-or-larger multi-phase commitment. Universe pipeline (Phase 0 in v2's roadmap) is potentially valuable on its own and could be the first dispatchable slice — runs once daily, gates pattern detection, surfaces useful trend-template state independent of any pattern detector.

**Brainstorm gate:** v2 doc is research-quality — explicit + introspectable but not project-scoped. Brainstorm dispatch would translate the 8-phase roadmap into project-specific phase decomposition (likely "Phase 11+ chart-pattern detection v2" or similar) with concrete schema + CLI + web surfaces, reconciliation against shipped flag-v1 module, and integration points with shipped Phase 6 (review_log) + Phase 7 (state machine + fills) + Phase 9 (risk_policy) + Phase 10 (metrics).

### Cross-references

- `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` — canonical v2 analysis brief.
- 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups (above) — flag-v1-specific, narrower scope; calibration study + schema-layer hardening + hidden-form-field tampering hardening remain valid for flag-v1 itself even under v2.
- 2026-04-27 chart-pattern flag-v1 V1-ship gates — operator-paced gates for shipping flag-v1 V1 (precedes any v2 work).
- `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` — flag-v1 brainstorm spec (subsumed under v2's broader scope but flag-v1 implementation choices remain authoritative for the pole-and-flag pattern).
- 2026-05-06 Phase 10 metrics dashboard entry (above) — outcome-distribution surfaces in v2's review interface depend on Phase 10 infrastructure.
- 2026-05-04 Schwab API integration entry (above) — v2's "delisted-stock data is essential" requirement may surface in Schwab Phase B market-data integration scope.

## 2026-05-10 Ruff residual cleanup (BACKLOG; **N818 SHIPPED 2026-05-10 at `44ac760`**; E501 still open)

> **N818 outcome (2026-05-10):** SHIPPED as Task family C in polish bundle 2026-05-10 (commit `efd3e15`). All 8 exception class renames landed in one mechanical commit: `SchemaVersionMismatch`, `LeaseRevoked`, `WatchlistEntryNotFound`, `ConcurrentRunBlocked`, `ChartingUnavailable`, `SoftWarnException`, `HardCapException`, `DuplicateOpenPositionException` → `…Error` suffixed. ~284 lines changed across `swing/` + `tests/` + `docs/` (the docs/ touches were spec/plan/backlog historical-reference renames; Codex R1 Minor #1 surfaced that the phase3e-todo N818 table cells got reflowed by the sed pass and the audit trail was restored via parenthetical). Ruff baseline 26 → 18 (matches expectation). 18 E501 still open per below.

**Surfaced 2026-05-10** during a ruff sweep that took the `swing/` baseline from 78 → 26 across three commits (`e99047f` safe auto-fixes 78→44, `33338f7` unsafe auto-fixes 44→34, `9c9b57c` manual B904+E741+SIM115-noqa batch 34→26). The 26 remaining are deferred for bundling with other minor fixes rather than a dedicated dispatch.

### Remaining ruff issues in `swing/`

| Code | Count | Description | Effort | Risk |
|---|---:|---|---|---|
| **N818** | 8 | Exception class names lacking `Error` suffix | ~10 min mechanical rename + verify | Medium — cross-cutting (~79 file references across swing/ + tests/) |
| **E501** | 18 | Lines exceeding 100-char `line-length` | ~30 min judgment work | Low per-site; no mechanical fix |

### N818 — exception class renames (8 classes)

Each rename is a sed-style global replace; names are distinctive enough that no substring false-positives are likely.

| Old | New | swing/ files | tests/ files |
|---|---|---:|---:|
| `SchemaVersionMismatch` (renamed to `SchemaVersionMismatchError`) | `SchemaVersionMismatchError` | 4 | 4 |
| `LeaseRevoked` (renamed to `LeaseRevokedError`) | `LeaseRevokedError` | 10 | 12 |
| `WatchlistEntryNotFound` (renamed to `WatchlistEntryNotFoundError`) | `WatchlistEntryNotFoundError` | 2 | 2 |
| `ConcurrentRunBlocked` (renamed to `ConcurrentRunBlockedError`) | `ConcurrentRunBlockedError` | 4 | 4 |
| `ChartingUnavailable` (renamed to `ChartingUnavailableError`) | `ChartingUnavailableError` | 4 | 2 |
| `SoftWarnException` (renamed to `SoftWarnError`) | `SoftWarnError` | 6 | 4 |
| `HardCapException` (renamed to `HardCapError`) | `HardCapError` | 7 | 2 |
| `DuplicateOpenPositionException` (renamed to `DuplicateOpenPositionError`) | `DuplicateOpenPositionError` | 7 | 5 |

(Note: this table was a planning artifact pre-2026-05-10 polish bundle rename. Both columns originally read identically because the planner left the "Old" cell as a TODO mirror of "New"; the polish-bundle-2026-05-10 sed pass through `docs/` reflowed the still-pending TODO mirrors. The old-name parenthetical above restores the audit trail.)

**Approach when attempted:** `git grep -l <OldName> | xargs sed -i 's/<OldName>/<NewName>/g'` per class; run `pytest -m "not slow"` after each batch (or after the full set) to verify; commit as a single rename pass.

**Watch-item:** verify no test asserts on the OLD class name as a string literal (e.g., `pytest.raises(ValueError, match="WatchlistEntryNotFound")` would have to become `match="WatchlistEntryNotFoundError"`). If found, those test assertions need the new name too — sed handles that uniformly since the match string contains the class name.

### E501 — line-too-long (18 lines)

`line-length = 100` is already configured (per `pyproject.toml`). The 18 violators exceed even that. No mechanical fix; each needs an editorial choice (break the string literal, extract a variable, accept a `# noqa: E501` for a justified comment). Would benefit from looking at all 18 sites and grouping by category (long log strings, long expressions, long comments) before deciding.

### Bundling guidance

These are good candidates to fold into ANY future small-scope dispatch as out-of-band cleanup, e.g.:
- A backlog UX-polish bundle (3e.4 + 3e.7) — add the N818 rename as a separate commit in the same dispatch
- A future tooling/lint pass — bundle with any pyproject.toml or CI configuration work
- Phase 9 writing-plans/executing-plans dispatch — N818 may surface naturally if any new exception classes get added (single batch commit at that point covers both new + legacy)

Per project baseline-tracking convention: when bundled in, update `docs/orchestrator-context.md`'s "ruff baseline" line in the track-record summary to the post-fix count. (CLAUDE.md does not currently track a ruff baseline; the living-state mention is in orchestrator-context.md.)

### Cross-references

- Sweep commits: `e99047f`, `33338f7`, `9c9b57c` on `main` (2026-05-10).
- `docs/orchestrator-context.md` track-record summary still reads "ruff baseline 78 preserved" (anchored to HEAD `b4bb9dd` polish-bundle ship — historical narrative). The live state at HEAD `9c9b57c` is **26**; orchestrator-context.md track-record summary line should be updated to the new live count at next housekeeping commit, OR when this backlog item is attempted (whichever comes first).

---

## 2026-05-10 Formalize orchestrator-vs-implementer execution-mode policy (PROCESS; below current backlog priority)

**Operator-surfaced 2026-05-10** during the 3e.16 dispatch design-question round. Operator clarified the principle: **default to implementer-dispatch over orchestrator-inline; minimize orchestrator context growth; crossover where inline beats dispatch is when orchestrator's token cost is less than the implementer's spinup-plus-task cost.** Captured as auto-memory at `feedback_orchestrator_vs_implementer_execution.md`. This entry tracks the formalization work to make the policy operationally enforceable across future sessions.

### Why formalize

- Auto-memory captures the principle but is fuzzy on the cost-estimation method. Without a heuristic the orchestrator can run pre-task, the default-to-dispatch rule will erode under orchestrator-side optimism ("this one is small enough").
- This session already had orchestrator-inline drift (operator-gate I1 + 3e.15 both inline) before the principle was made explicit. Recurrence likely without a checklist.
- Brief-drafting checklist + orchestrator-context Conventions section both lack a "decide execution mode" step — currently implicit in operator-driven choice (which means the orchestrator carries the cognitive load each time).

### Scope (what "formalize" likely means)

1. **Cost-estimation heuristic.** A back-of-envelope rubric the orchestrator runs before each task:
   - Estimate orchestrator token cost: file reads + file edits + tests written + commit drafting + housekeeping. Use ~prior-session anchors as benchmarks (3e.15 was ~5-8k orchestrator tokens; operator-gate I1 was ~3-4k; polish-bundle-2026-05-10 brief authorship was ~12-15k orchestrator tokens for the dispatch path).
   - Estimate implementer spinup cost: bootstrap (CLAUDE.md + orch-context + brief read) ≈ 30-50k tokens; plus task-implementation cost (~similar to orchestrator-inline since same code surface).
   - Crossover: if estimated orchestrator-inline < ~30k AND task is single-file + no TDD discipline benefit + no adversarial-review benefit, INLINE; else DISPATCH.

2. **Brief-drafting checklist addition.** Add a §0 "execution mode decision" line: orchestrator records the chosen mode + rationale BEFORE drafting brief content. Forces explicit consideration.

3. **Orchestrator-context Conventions update.** Promote the auto-memory feedback into a Conventions §-level entry (with cap-rotation if needed). Future fresh-orchestrator sessions read it at bootstrap.

4. **Telemetry-style retrospective.** After each ship, capture in the return report: actual orchestrator tokens consumed (estimable from the conversation log) vs the pre-task estimate. Builds a feedback loop on the heuristic's calibration.

5. **Edge cases worth enumerating:**
   - Mid-gate operator-driven scope changes (operator-gate I1 pattern) — defaults to inline regardless because dispatch overhead doesn't make sense for a 30-min mid-gate hotfix on an active worktree branch
   - Housekeeping commits (orchestrator-context updates, phase3e-todo SHIPPED markers, post-merge memory captures) — always inline
   - Brief-author-error mid-dispatch fixes — could be either path; operator's call

### Effort estimate

~1-2 hr orchestrator-thread work to draft the checklist + heuristic + memory→conventions promotion + brief-template addition. No code; pure process-doc work. Can be done by orchestrator inline in a quiet moment between dispatches OR queued as a thinking-session task.

**NOT a dispatch candidate** — this is orchestrator-doctrine work that lives in orchestrator-context + brief templates; an implementer doesn't have the cross-session orchestrator-perspective to do it well. (And this very item demonstrates the principle: process-doc work IS the kind of thing where orchestrator-inline beats implementer-dispatch on the cost-crossover.)

### Cross-references

- `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_orchestrator_vs_implementer_execution.md` — the auto-memory entry capturing the principle
- `docs/orchestrator-context.md` Conventions section — target home for the formalized policy
- `feedback_orchestrator_performs_merge.md` — pattern complement (both about scoping orchestrator actions to high-leverage edges)

---

## 2026-05-10 3e.8 disposition + commission bundles (derived from sell-side advisories investigation)

**Operator-orchestrator walkthrough 2026-05-10** of the 14 operator-decision items in [`docs/3e8-sell-side-advisories-investigation.md`](3e8-sell-side-advisories-investigation.md) §6 produced the dispositions below. Three commission bundles + three deferred-with-gate items + one in-flight operator-action (§4.G transcription) + two banked-without-gate items.

### Disposition matrix (14 items)

| # | §3e.8 item | Disposition | Workstream / trigger |
|---|---|---|---|
| 1 | §4.A trail-MA gating | §4.A.bis commissioned (advisory-only); §4.A deferred (V2.1 §VII.F-routed; gated on §4.G) | Bundle 3 below |
| 2 | §4.B trim/sell-into-strength | Commission V1 (single hint at +1R; default 25%) | Bundle 2 below |
| 3 | §4.C / §4.C.bis time-stop | Defer both; revisit at n≥10 closed sub-A+ trades OR §4.G-driven Minervini 7-week confirmation | Banked — see "Banked without gate" below |
| 4 | §4.D parabolic detector | Commission, bundled with §4.B + §4.K (sell-side bundle) | Bundle 2 below |
| 5 | §4.E briefing advisories | Commission, bundled with §4.F (parity bundle) | Bundle 1 below |
| 6 | §4.F detail+expanded advisory column | Commission, bundled with §4.E | Bundle 1 below |
| 7 | §4.G Minervini SEPA + DST sell-side transcription | Commission as immediate priority — operator-action; PRECEDES Bundles 1-3 | In-flight — scaffolding files at `reference/methodology/minervini-sell-side-rules.md` + `reference/methodology/dst-take-profit-and-trail.md` |
| 8 | §4.H sector RS check | Defer with second-source gate | Deferred-with-gate below |
| 9 | §4.I volume-confirmed exit | Defer with §4.G-completion-gate-trichotomy | Deferred-with-gate below |
| 10 | §4.J combined-violation | Defer with second-source gate | Deferred-with-gate below |
| 11 | §4.K planned_target_R hit | Commission, bundled with §4.B + §4.D | Bundle 2 below |
| 12 | DHC §6.2 decision | Case A confirmed 2026-05-10 (snapshot 2026-05-08T11:24:23: open_R=0.85, MFE=0.88R, maturity_stage=pre_+1.5R) — keep 20MA trail; ignore 10MA suggestion | Resolved |
| 13 | §6.3 sequencing | Approved as 4-step: §4.G transcription → Bundle 1 → Bundle 2 → Bundle 3 | Resolved |
| 14 | §6.4 [UNVERIFIED] flags (13 items) | Triage folded into §4.G transcription work | In-flight — see scaffolding files |

### §4.G transcription — **COMPLETE 2026-05-10 within available sources**

**DST file** (`reference/methodology/dst-take-profit-and-trail.md`): `~ PARTIAL` — 3/5 CONFIRMED-with-correction; 2/5 NOT-PRESENT-IN-SOURCE; 2 NEW rules surfaced (D.6 intraday-EMA parabolic + D.7 ADR-extension trim). Orchestrator pre-filled via PyMuPDF extraction of the DST PDF.

**Minervini file** (`reference/methodology/minervini-sell-side-rules.md`): `~ PARTIAL` — 1/7 CONFIRMED-QUANTITATIVE (M.2 sell-into-strength with R-multiple-of-stop-loss anchor); 4/7 BRIEF-MENTION-NO-DETAIL; 2/7 NOT-PRESENT-IN-AVAILABLE-SOURCES (M.1, M.4). Operator reviewed TLSMW (2013) on 2026-05-10. Think & Trade Like a Champion (2017) is NOT available — M.4 7-week rule remains unverifiable.

**Triggered post-completion (resolutions):**

- **§4.I gate-trichotomy → OUTCOME 2 (escalate to second-source gate).** M.6 is qualitative-without-threshold in TLSMW. §4.I now in same bucket as §4.H + §4.J (deferred-with-second-source-gate).
- **§4.A full + §4.C/§4.C.bis deferrals REINFORCED.** No quantitative anchor for either in available sources. §4.C/§4.C.bis: doctrine landscape on time-stops favors the AGGRESSIVE end (Q.1 3-5 day) — opposite of original 3e.8 framing.
- **Bundle 2 §4.B trim defaults need re-anchoring.** Doctrine = DST D.2 (50% on Day 3-5 calendar window) OR Minervini M.2 (R-multiple stop-tighten, NOT trim). The 3e.8 default (+1R first-time / 25% trim) is operator-policy hybrid. Implementation brief should support EITHER trigger pattern OR keep operator-policy hybrid with explicit annotation.
- **Bundle 2 §4.D parabolic defaults need re-anchoring.** Doctrine = DST D.7 (>7x ADR above 50SMA per Realsimpleariel). The 3e.8 defaults (25%/5d/15%) are arbitrary. Implementation brief should re-anchor.
- **Bundle 3 reframed to Option δ (hybrid α + β-LITE).** Operator-locked 2026-05-10. TWO complementary advisories: (a) §4.A.bis maturity-stage MA hint (operator-policy per Tier-3 #6); (b) M.2 R-multiple stop-tighten hint (doctrine per TLSMW Ch 13 p. 296). Different triggers (MFE-anchored stage vs live R-multiple); complementary signals. ~4-5 hr bundled.
- **13 [UNVERIFIED] flags in `docs/3e8-sell-side-advisories-investigation.md` §6.4 — dispositions captured in methodology files.** Future doc-update pass can refresh §6.4 inline if/when operator wants the investigation doc to reflect the post-transcription state.

### Deferred §4.H — Sector RS check (second-source gate)

**Trigger to revisit:** A doctrine-confluent sector-lag exit rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only) is structural weakness; no Minervini or DST analog in surveyed sources. Cost-benefit (10-14 hr + V2.1 §VII.F) doesn't change with trade-volume scale. Drop-equivalent for now; gate preserves optionality.

**Cross-refs:** §3e.8 §4.H + §3.H.

### Deferred §4.I — Volume-confirmed exit overlay (§4.G-completion-gate-trichotomy)

**Trigger to revisit:** §4.G transcription completes. Then THREE possible dispositions per M.6 outcome:
- M.6 carries **specific** volume threshold in source → commission §4.I with confirmed defaults (~2-3 hr; advisory-message-only)
- M.6 is **qualitative** without numerical threshold → escalate to second-source gate (mirror §4.H pattern)
- M.6 **doesn't exist** in source → drop §4.I

**Rationale:** Threshold-tuning friction without doctrine anchor; premature optimization. Gate ties revisit to concrete trichotomy.

**Cross-refs:** §3e.8 §4.I + §3.I.

### Deferred §4.J — Combined-violation rule (second-source gate)

**Trigger to revisit:** A doctrine-confluent combined-violation rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only); cosmetic refinement (operator already sees both messages). Same gate-pattern as §4.H for matrix consistency.

**Cross-refs:** §3e.8 §4.J + §3.J.

### Banked without gate — §4.A full + §4.C / §4.C.bis

**§4.A full** (classification-altering trail-MA gating with suppression): Banked. Trigger to revisit = sufficient evidence accumulation from Bundle 3's §4.A.bis hint adoption (n≥10 closed trades where operator's actual stop adjustments consistently follow the maturity-stage-recommended MA). At that point, the §4.A.bis behavioral evidence IS the shadow-mode-equivalent that V2.1 §VII.F would otherwise require.

**§4.C / §4.C.bis** (time-stop discipline change): Banked. Triggers to revisit = either (a) n≥10 closed sub-A+ hypothesis trades giving statistical signal on whether 10/0.5R is too aggressive, OR (b) operator surfaces a specific trade time-stopped prematurely with hypothesis still under evaluation, OR (c) §4.G Minervini transcription confirms 7-week rule context that justifies an informed default change.

### Cross-references for this disposition

- `docs/3e8-sell-side-advisories-investigation.md` — full investigation analysis (746 lines)
- `reference/methodology/minervini-sell-side-rules.md` — §4.G scaffolding (Minervini)
- `reference/methodology/dst-take-profit-and-trail.md` — §4.G scaffolding (DST)
- Earlier 3e.8 entry above (line 311) — investigation entry summary

---

## 2026-05-11 V2 watch items banked from 3e.8 Bundle 1 ship

### V2 — Extract shared advisory composer (drift-risk reduction)

**Banked from:** Bundle 1 Codex R1 Minor #1 (orchestrator triage 2026-05-11).

**Symptom:** Advisory composition is now hand-duplicated across 5 paths post-Bundle-1 ship: `build_dashboard`, `build_open_positions_row`, `build_trade_detail_vm`, `build_open_positions_expanded`, briefing helper (`compose_open_trade_advisories_for_briefing`). Future drift risk if `AdvisoryContext` inputs change — every change to advisory composition needs to be propagated to all 5 sites independently.

**Brief-locked deferral:** Bundle 1 brief §0.3 #2 explicitly locks "mirror dashboard composition" for V1 to avoid scope-creep. The hand-duplication is a known trade-off accepted at brief time.

**Proposed V2:** Extract a shared "compose advisory VMs for trade" web-side helper + a separate data_asof-pinned pipeline-side helper. Both consume a common `AdvisoryContext` constructor; both produce the same `tuple[AdvisorySuggestionVM, ...]` shape. Single source of truth for advisory composition logic.

**Effort estimate:** ~3-4 hr (refactor + update 5 call sites + verify all existing tests still pass).

**Trigger:** When `AdvisoryContext` inputs change OR a third advisory-rendering surface gets added OR a Codex round on a future bundle flags drift.

### V2 — `build_open_positions_expanded` cache I/O during SQLite read-snapshot

**Banked from:** Bundle 1 Codex R1 Minor #2 (orchestrator triage 2026-05-11).

**Symptom:** `build_open_positions_expanded` performs cache I/O (PriceCache.get_many) while the route holds a SQLite read-snapshot transaction. Lock window is bounded by `cfg.web.price_fetch_deadline_seconds` (typically 5-8s) but the pattern diverges from `build_dashboard`'s open-own-conn-DB-phase-then-cache-phase canonical pattern.

**Operational impact:** Under sustained load (many concurrent expand requests), the SQLite read-snapshot lock window blocks other read transactions for the cache-I/O duration. At single-operator scale this is invisible; it surfaces if/when the project ever supports concurrent operator sessions or background read-heavy workloads.

**Proposed V2:** Refactor `build_open_positions_expanded` to mirror `build_dashboard`'s pattern — open own connection, complete DB phase, close connection, then enter cache phase. Symmetric with the canonical pattern.

**Effort estimate:** ~2-3 hr (refactor + verify expand-route tests still pass).

**Trigger:** When concurrent-session support becomes a project goal OR when operator surfaces lock-related latency on the expand route.

### Cross-references

- Bundle 1 SHIPPED entry above (line ~417 post-housekeeping)
- `docs/3e8-bundle-1-advisory-parity-brief.md` §0.3 #2 (mirror-dashboard-composition lock)
- `swing/web/view_models/dashboard.py:build_dashboard` — canonical open-own-conn pattern reference

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 2 ship

### V2 — Brief composition-surface enumeration: grep, don't memory-enumerate

**Banked from:** Bundle 2 Codex R1 Major #1 (orchestrator triage 2026-05-11).

**Symptom:** Bundle 2 dispatch brief §0.2 enumerated 5 advisory-composition surfaces (4 web VMs + 1 pipeline briefing composer). The actual surface count is **6** — `swing/cli.py:trade_advisory_cmd` was the 6th, missed by orchestrator recon. Without Codex's discovery in R1 Major #1, the CLI `swing trade advisory` command would have emitted `trim_into_strength` advisories on already-trimmed trades because `has_been_trimmed` defaulted to `False` at the CLI composition site (no fill-loading wired through). Fixed in same Codex round with new `--adr-pct` flag + fill loading + 3 CLI tests.

**Generalized lesson:** When writing a dispatch brief that lists N composition / hand-mirroring sites for a new feature, the orchestrator MUST grep the codebase for ALL invocations of the canonical composition target — never enumerate from memory. Bundle 1 also listed 5 surfaces (same memory enumeration); Bundle 2 inherited the count without re-grepping. The CLI command lives outside the obvious web + pipeline namespaces and gets missed.

**Pre-empt in future dispatches:** writing-plans phase grep target = the function name or class name of the composition target (e.g., `compose_open_trade_advisories`, `AdvisorySuggestion`, `build_open_positions_row`). Cross-reference grep output against the brief's surface list before approving for dispatch.

**Effort estimate:** N/A — process change, not a code change. Lesson encoded in this entry + applied to all future bundle briefs.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory composition has 6 sites (web ×4 + pipeline ×1 + CLI ×1) — grep for invocations, don't memory-enumerate" as a gotcha if a third bundle adds new rules. For now, lesson lives here.

### Inherited from Bundle 1 (unchanged)

The two V2 watch items banked at the 2026-05-11 Bundle 1 section above carry forward unchanged — Bundle 2 incremented the hand-duplication surface count from 5 → 6 (CLI added) but did NOT extract a shared composer. Same accept-with-rationale on the drift risk. Same trigger for V2 composer extract.

### Cross-references

- Bundle 2 SHIPPED entry above (line ~1108)
- `docs/3e8-bundle-2-sell-side-advisories-brief.md` §0.2 (5-site enumeration that missed CLI; §0.3 #4 V2 hand-duplication acceptance)
- `swing/cli.py:trade_advisory_cmd` — the 6th composition site

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 3 ship

### V2 — Price-independent vs price-dependent advisory degradation pathways differ

**Banked from:** Bundle 3 Codex R1 Major #2 (`compute_price_independent_suggestions` helper introduction; orchestrator triage 2026-05-11).

**Symptom:** Before R1 fix, when PriceCache was degraded (live price unavailable), ALL advisory rules silently no-opped because the entire advisory composition was gated on having a valid `current_price`. But §4.A.bis (maturity_stage_trail_ma_hint) reads `maturity_stage` from DB and does NOT consume `ctx.current_price` — so it should still fire even when PriceCache fails. The original composition path conflated "price unavailable" with "skip ALL advisories", which masked DB-sourced advisories like §4.A.bis.

**Architectural fix (Bundle 3 R1 M#2):** `compute_price_independent_suggestions` helper splits the rule set into two tiers:
- **Price-independent rules** (e.g., §4.A.bis): fire when `AdvisoryContext` has the relevant DB-sourced fields populated; do NOT require valid `current_price`.
- **Price-dependent rules** (existing breakeven, trail_*, exit_below_*, weather, time_stop, Bundle 2's trim_into_strength + planned_target_r_hit + parabolic_trim): require valid `current_price`; no-op when PriceCache is degraded.

**Generalized lesson:** When adding new advisory rules in future bundles, classify the rule by data dependencies:
- If the rule's predicate consumes ONLY DB-sourced fields (from `AdvisoryContext` or `trade` model), it's price-independent — must remain visible under PriceCache degradation.
- If the rule's predicate consumes `ctx.current_price` (directly or via `r_so_far`), it's price-dependent — correctly no-ops under degradation.

The current 11-rule advisory surface is:
- Price-independent: §4.A.bis maturity_stage_trail_ma_hint (1 rule).
- Price-dependent: breakeven, trail_10ma, trail_20ma, exit_below_10ma, exit_below_20ma, exit_below_50ma, weather, time_stop, trim_into_strength, planned_target_r_hit, parabolic_trim, r_multiple_stop_tighten (12 rules including Bundle 3's M.2 trigger via `r_so_far`).

**Pre-empt in future dispatches:** writing-plans phase classifies each new rule + verifies it lands in the appropriate composition tier. Discriminating test: simulate PriceCache degradation; assert price-independent rules still fire while price-dependent rules no-op.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory degradation must differentiate price-independent vs price-dependent rules — the `compute_price_independent_suggestions` split is the canonical pattern" as a gotcha if a third bundle adds a price-independent rule. For now, lesson lives here.

### V2 — Orchestrator brief composition-surface enumeration must use `def build_*` grep, not caller-site grep

**Banked from:** Bundle 3 brief §0.2 file-attribution error (orchestrator triage 2026-05-11).

**Symptom:** Bundle 3 brief §0.2 listed `build_open_positions_expanded` as living in `swing/web/view_models/dashboard.py`. Actual location: `swing/web/view_models/open_positions_row.py`. The implementer addressed the function at its actual location without surfacing the discrepancy. Brief inaccuracy did not block dispatch but creates rot-risk for future bundles that grep the brief looking for canonical surface enumerations.

**Root cause:** orchestrator's grep in §0.2 of Bundle 3 was scoped too broadly (matched any file referencing the function NAME) rather than the file containing the function DEFINITION. The brief recorded a CALLER location, not a DEFINITION location.

**Generalized lesson:** When orchestrator briefs enumerate function locations, the grep MUST scope to definitions:
```
grep -rn "^def build_" swing/web/view_models/
# Or, more targeted:
grep -rn "def build_open_positions_expanded" swing/
```
NOT:
```
grep -rn "build_open_positions_expanded" swing/  # matches both definitions AND callers
```

**Pre-empt in future dispatches:** writing-plans phase enumeration step uses `^def` anchored patterns for function locations; verify each location is a definition (the line starts with `def` or `class`, not a call).

### Cross-references

- Bundle 3 SHIPPED entry above (line ~1152)
- `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md` §0.2 (file-attribution error documented; addressed at actual location by implementer)
- `docs/3e8-bundle-3-return-report.md` §7 (process deviation: inline TDD per task family; not surfaced to orchestrator mid-flight)
- `swing/trades/advisory.py:compute_price_independent_suggestions` — canonical pattern for advisory-degradation split
- `swing/web/view_models/open_positions_row.py:build_open_positions_expanded` — corrected location (NOT dashboard.py as brief §0.2 stated)

---

## 2026-05-13 Phase 10 closer — Phase 11 hand-off

Sub-bundle E SHIPPED (T-E.0..T-E.4 + T-E.5 + T-E.6 electives). Phase 10 CLOSED.

### Capture-needs surfaced during Phase 10 implementation (V2.1 §VII.F amendments pending)

Cumulative pending V2.1 §VII.F amendments at Phase 10 close (27+):

- (A T-A.7 + R2/R3) plan §A.7 binding-interface amendments (3): Wilson CI standard-vs-continuity-correction; `read_at_trade_time_policy` policy_id_stamp shape; `BaseLayoutVM.stale_banner` `str | None` vs `bool` (matches existing pattern).
- (B) plan-text deviations (5): T-B.1 `mistake_cost_R` cadence-grain rejection; T-B.2 `ALL_COHORTS_KEY='__all__'`; T-B.4 `cumulative_R_pct_of_capital` PERCENT units; T-B.7 display-block placement; T-B.2 7 cohort tabs (4 pre-registered + 2 orphan-label + "All").
- (C) plan-text deviations (5): T-C.1 cohort_relative_to_aplus rendering; T-C.1 doctrine_deviation_class baseline enum; T-C.5 filter SQL predicate; T-C.5 threading; T-C.5 toggle href shape.
- (D) plan-text deviations (5): D1 PROVISIONAL/LIVE math; D2 `candidate_criteria` vs `criterion_results.criterion_name`; D3 capital-friction trend window size; D4 `MaturityStageRow` per-row badge fields; D5 `aplus_take_rate_per_run` un-clamped.
- (E NEW) plan-text deviations (4):
  1. T-E.3 `ConfigPageVM` (not `ConfigVM` per brief §0.11).
  2. T-E.3 retrofitted 10 base-layout VMs (6 plan-named + 4 additional whose templates extend base.html.j2: ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM). Defense-in-depth per CLAUDE.md "base.html.j2 is shared" gotcha.
  3. T-E.5 service function is `record_snapshot` (NOT `record_snapshot_with_audit` per brief §0.5); Phase 9 Sub-bundle C ship-time naming preserved.
  4. T-E.1 N=10 + global_confidence_floor_n=20 + spec §5.4 "drops at n>=20": with the §A.4 N=10 LOCK the confidence-floor warning NEVER drops via the production callsite by construction. Implementation matches the locked behavior; spec wording could be amended to make the conditional dependence explicit. Discriminating test exercises window_size=20 to verify the band semantics are reachable.

- (D R2 M#1 banked at D) Phase 9 §7 sector_industry anchor + Phase 9 §6.2 multi-line parser amendments still pending.

**Total V2.1 §VII.F amendments pending: 27** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 = 24 Phase 10 + Phase 9 amendments banked).

### Operator-decision items pending Phase 11

1. **§8.4 Corporate_Actions MVP** — DEFERRED at Phase 10 electives triage (electives amendment §5). Banked at this section's existing 2026-05-13 entry. Phase 11 candidate.

2. **Schwab API Phase A** — operational metrics in Sub-bundle D (capital-friction + maturity-stage PROVISIONAL/LIVE) consume the Phase 9 Sub-bundle C `account_equity_snapshots` table. Schwab API integration (future phase) would write `source='schwab_api'` snapshots that outrank `source='manual'` per the spec §A.9 source ladder. Pre-Phase-11 triage decision: operator-paced.

3. **`mistake_cost_R_rolling_N_total` sum-class with bootstrap CI** — §A.21 spec-conformance deviation banked at writing-plans + carried through E T-E.1. Sub-bundle E ships "point" class (bare float); V2 may add sum-class with bootstrap CI on the window sum.

4. **Schwab inception-CSV ingestion** + **`account_equity_snapshots.equity_dollars` cash-basis vs MTM semantic formalization** (both banked at 2026-05-12 Phase 9 Sub-bundle C entry). Phase 11 candidates.

### Post-Phase-10 standalone dispatches (UNBLOCKED by Phase 10 close)

Per dispatch brief §1 + §7 watch items:

1. **Cleanup-script `-DeregisterFirst` extension** — Phase 9 husks (B/C/D/E) + Phase 10 Sub-bundle C/D/E orphan husks remain still-registered. Standalone dispatch will extend cleanup-script with a `-DeregisterFirst` switch + clear all pending husks.
2. **Test-runtime xdist + fixture-scope analysis** — fast suite at ~6:45 wall-clock at 3300+ tests; recommendation: profile → pytest-xdist → fixture-scope refactor for ~3-5x wall-clock reduction at zero coverage cost.
3. **§8.4 Corporate_Actions MVP** — schema-introducing standalone dispatch (new `corporate_actions` table + `0018_*.sql` migration + CLI surface + manual reconcile flow). Preserves Phase 10 §A.0 ZERO-new-schema lock; Phase 9 Sub-bundle A precedent (schema-introducing bundles get their own scoped review).

### V2 candidates banked at Phase 10 ship

1. **Orphan-emit discrepancy attribution surface** — Phase 9 Sub-bundle B per-run dedup allows orphan emits (discrepancies not attributed to a specific trade_id). Global discrepancy badge (T-E.3) counts these; per-trade indicator (T-E.6) does NOT. V2: "orphan discrepancy detail page" surfacing trade-less discrepancies.
2. **`render_class_d` "point" branch mean-semantics switch** (banked from Sub-bundle A return report §7). V2 may add sum-class semantics with bootstrap CI.
3. **Per-cohort "exclude trades stamped during paused intervals" filter** (banked from Sub-bundle B + electives amendment §7). Same UI shape as T-C.5; same VM pattern. Phase 11 candidate.

### Cross-references

- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (HEAD `a34c00d`).
- Phase 10 electives amendment: `docs/phase10-electives-amendment.md`.
- Phase 10 spec: `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
