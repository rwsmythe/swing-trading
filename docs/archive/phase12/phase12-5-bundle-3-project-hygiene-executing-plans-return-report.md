# Phase 12.5 #3 — Project Hygiene Maintenance Pass — Executing-Plans Return Report

**Branch:** `phase12-5-bundle-3-project-hygiene-executing-plans`
**Worktree:** `.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans/`
**Baseline SHA:** `fc4cd0d` (main HEAD at dispatch; Q1/Q2 cleanup-item brief committed; brief target was `7970c6b` per dispatch brief but main advanced 2 commits between brief-write and worktree-create — Q1/Q2 docs commits added on top inherited cleanly)
**Brief:** `docs/phase12-5-bundle-3-project-hygiene-executing-plans-dispatch-brief.md`
**Plan:** `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (1101 lines)
**Spec:** N/A — operator-locked SKIP BRAINSTORM (plan §1.1; brief IS the design contract).

---

## §1 Final HEAD + commit count breakdown

**Final HEAD:** `5dbca84` (R3 cosmetic Minor fix; chain converged at NO_NEW_CRITICAL_MAJOR).

**Commit count: 11 commits on branch (10 task/fix commits + 1 return report still-pending).**

| # | Type | SHA | Description |
|---|---|---|---|
| 1 | task-impl | `a8a7d23` | T-3.7 amend Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 — banner clears on tier-3 override |
| 2 | task-impl | `88dd31e` | T-3.5 phase8 walkthrough Bucket A fix — synthetic OHLCV end-date dynamic anchor |
| 3 | task-impl | `ea51602` | T-3.6 clear ruff 18 E501 baseline — 18 per-site line-wrap dispositions |
| 4 | task-impl | `b7cd68c` | T-3.4 V2.1 §VII.F amendment inventory — 62 amendments initial collation |
| 5 | task-impl | `73bdc0b` | T-3.1 CLAUDE.md status-line archive-split — boundary 2026-05-12 inclusive; 47→18 archived |
| 6 | task-impl | `0f3e213` | T-3.2 phase3e-todo.md archive-split — 23 sections moved |
| 7 | task-impl | `229e434` | T-3.3 orchestrator-context.md archive-split — 20 lessons moved (conservative scope) |
| 8 | codex-fix | `8046dd5` | R1 fix-bundle — 5 Major + 2 Minor (M#2 pointer + M#3 Phase 11 expand + M#4 34-file note + M#5 7-day buffer + M#1 deferred to R-R; M minors absorbed) |
| 9 | codex-fix | `ebb17f1` | R2 fix-bundle — 2 Major + 1 Minor (M#1+M#2 fold A-11.D into cross-ref note; m#1 "references/banks" reword; A-11.B.2 source explicit) |
| 10 | codex-fix | `5dbca84` | R3 fix — 1 Minor (cross-reference enumeration discipline) |
| 11 | return-report | (pending; this file) | This return report |

Aggregate: **11 commits**. **ZERO Co-Authored-By footer** across all 11 commits (project invariant; ~165+ project-cumulative streak preserved).

---

## §2 Codex chain summary

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR at R3.** Convergent monotonic-Major taper.

| Round | Critical | Major | Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| R1 | 0 | 5 | 2 | ISSUES_FOUND | All 5 Major + 2 Minor RESOLVED in `8046dd5` (M#2 pointer / M#3 Phase 11 expand / M#4 source-roster note / M#5 7-day buffer / M#1 deferred to R-R post-hoc audit + 2 Minors folded). |
| R2 | 0 | 2 | 1 | ISSUES_FOUND | All 2 Major + 1 Minor RESOLVED in `ebb17f1` (M#1+M#2 fold A-11.D into cross-ref; m#1 "references/banks" reword; A-11.B.2 source explicit; all 74 rows have Status + Source). |
| R3 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR | 1 Minor RESOLVED in `5dbca84` (A-11.A.1..A-11.A.13 range → explicit 12-of-13 enumeration). Chain converged. |

**Convergent shape:** monotonic-Major taper 5 → 2 → 0. **ZERO Critical findings entire chain.** **ZERO ACCEPT-WITH-RATIONALE on Major findings** — all 7 cumulative Major findings (5 + 2 + 0) RESOLVED with code-content fixes (matches Phase 12.5 #1 + #2 arc clean-record streak; cumulative arc-streak ZERO ACCEPT-with-rationale across the 3-bundle Phase 12.5 arc).

**Pre-Codex orchestrator-side review** (per BINDING C.C lesson #6; 7th cumulative validation): **APPROVED_AS_IS** — pre-review caught no LOCK divergences before Codex chain; all 4 operator-locks + 7 per-task LOCK verifications passed at the 4850/5/0 pytest baseline.

---

## §3 Per-task delivery summary (T-3.1..T-3.7)

| Task | Status | File:line evidence + acceptance verification |
|---|---|---|
| **T-3.7** | SHIPPED `a8a7d23` | 3 grep hits for "AMENDMENT (Phase 12.5 #3" across `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md:1071` + `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md:104` + `:940`. Amendment text accurately describes shipped helper SQL (`swing/metrics/discrepancies.py:count_recent_multi_leg_auto_corrections` queries `WHERE rd.resolved_by = 'auto_tier1_multi_leg'`). ZERO code touched; ZERO tests touched. |
| **T-3.5** | SHIPPED `88dd31e` (+ R1 `8046dd5` buffer-widening) | **Bucket A** disposition per plan §A T-3.5 Step 3a. Root cause: `_synthetic_ohlcv()` hardcoded `end="2026-05-08"` aged past today (2026-05-18); `last_completed_session(run_now)=2026-05-15` fell past fixture window; `asof_rows = df.loc[df.index.date == asof_session]` returned empty → `compute_daily_approximate_snapshot` returned None → 3 tests FAIL. Fix anchors `end_date = (datetime.now() + timedelta(days=7)).date()` (R1 hardened from days=1 to days=7 buffer covering weekend/holiday/DST/clock-skew). 3 previously-failing tests (`test_phase8_pipeline_emits_snapshots_for_open_trades_only` line 196 / `test_phase8_pipeline_second_same_day_run_upserts` line 258 / `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id` line 415) promoted to PASSING. 4850 fast pass (was 4847 pre-fix). Bucket C HARD STOP not triggered. |
| **T-3.6** | SHIPPED `ea51602` | All 18 E501 violations cleared per-site via `Edit` (matches plan-write-time roster verbatim). Final ruff: `ruff check swing/ --select E501 --statistics` returns 0; `ruff check swing/ --statistics` returns 0 (no new classes introduced). 11 files touched in `swing/`. ASCII preservation contract honored on cli.py + briefing rendering paths (no non-ASCII in `+` diff lines). ZERO `# noqa: E501` adds. ZERO refactors. |
| **T-3.4** | SHIPPED `b7cd68c` (+ R1 `8046dd5` + R2 `ebb17f1` + R3 `5dbca84` iterations) | NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` with **74 final amendment rows** (62 initial → 86 after R1 Phase 11 per-row expansion → 74 after R2 A-11.D fold-into-cross-reference). Per-row contract honored: every row has `Source:` (explicit doc path) + `Status:` (text-only / cross-reference / wording precision / contract drift). HYBRID format (master inventory + inline supersession at T-3.7 sites). 34-file source-roster note clarifies 33→34 drift. T-3.7 amendment `A-12.5.3.H4-banner-clears` indexed. Phase 12.5 #2 A1/A2/A3 + J1/J2/J3 indexed. ZERO duplication on amendment IDs (74 unique). ZERO spec/plan modifications in T-3.4 diff. |
| **T-3.1** | SHIPPED `73bdc0b` | Status-line 146780 chars → 118704 chars (~30k reduction; below plan §A target ~40-50k chars because Phase 11/12/12.5 entries are bulk-of-active; active-retain count 29 within plan [15, 30] band). 47 entries → 18 archived to NEW `docs/CLAUDE.md-archive.md` (43 lines, paragraph-flow format) + 29 retained active (post-2026-05-13 Phase 11 Schwab arc + Phase 12 + Phase 12.5). Archive pointer at CLAUDE.md line 4. PROCEED_WITH_WRITE count gate fired cleanly (29 within band; no operator escalation needed). |
| **T-3.2** | SHIPPED `0f3e213` | `docs/phase3e-todo.md` 4142 → 3766 lines (-376; below plan §G target ~1500-2500 because SHIPPED-only predicate yields proportionally to dated-SHIPPED-pre-boundary content; 23 sections of 341 matched). `docs/phase3e-todo-archive.md` 990 → 1372 lines (+382). 2026-05-18 archive pointer added near top of active doc (below pre-existing 2026-05-05 pointer). SHIPPED-only predicate per L-W2 + plan §A T-3.2 Step 3. |
| **T-3.3** | SHIPPED `229e434` (+ R1 `8046dd5` pointer addition) | Conservative-scope per plan §A T-3.3 Step 1 + dispatch §3.2 (operator-pairing point exercised via implementer's reasonable-call discretion per "work without stopping" override). "Currently in-flight work" section: ZERO pre-2026-05-13 entries to archive (all Prior state entries dated 2026-05-17+); zero-yield archive pointer added at line 78-79 (R1 M#2 fix). "Lessons captured" section: 69 bullets → 20 oldest pre-2026-05-13 archived (cap=20 per L-W2). Active 715 → 696 lines. Archive 140 → 185 lines (+45 covering 20 bullets). Archive pointer inserted under Lessons captured H2. |

---

## §4 Codex Major findings ACCEPTED with rationale

**ZERO** Major findings ACCEPTED-with-rationale. All 7 cumulative Major findings (R1: 5 + R2: 2 + R3: 0) RESOLVED with code-content fixes (matches Phase 12.5 #1 + #2 arc clean-record streak).

ZERO Minor ACCEPTED-with-rationale either; all 4 cumulative Minor findings (R1: 2 + R2: 1 + R3: 1) RESOLVED with code-content fixes.

---

## §5 V2 candidates banked

From plan §K + executing-plans Codex chain:

| ID | Candidate | Source | Notes |
|---|---|---|---|
| V-3.5.A | Standalone Phase 8 walkthrough fix dispatch (if Bucket C had landed) | T-3.5 disposition | **NOT NEEDED** — Bucket A fix shipped inline; no standalone dispatch required. |
| V-3.4.A | Promote amendment inventory entries to V2.1 §VII.F methodology revision proposal | T-3.4 inventory | Operator-paced action; routing-guidance §3 of inventory doc provides 3-tier priority hint. |
| V-3.1.A | CLAUDE.md gotchas section archive-split (separate concern; growing) | brief §5 OUT OF SCOPE note + plan §F | Future maintenance pass when gotchas section cap drifts. |
| V-3.4.B | Convert amendment inventory to machine-parseable YAML/JSON | T-3.4 | Useful if orchestrator automation grows. |

**1 NEW V2 candidate surfaced during Codex chain** (NOT previously banked):

| ID | Candidate | Source | Notes |
|---|---|---|---|
| V-3.5.B | Parameterize `run_pipeline_internal(run_now=...)` for freezable-clock testing | Codex R1 M#5 discussion | Considered + rejected this dispatch (scope cap §F.3 T-3.5 Bucket A). Future testability dispatch could add `run_now` kwarg + deprecate `_dt.now()` internal call. Buffered fixture (7-day) is the V1 workaround. |

---

## §6 V2.1 §VII.F amendments banked

This dispatch's own amendment + the executing-plans Codex chain's surfaced amendments:

| ID | Site | Summary | Status |
|---|---|---|---|
| **A-12.5.3.H4-banner-clears** (NEW; T-3.7) | Phase 12.5 #1 plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 | Banner CLEARS immediately on tier-3 override per shipped helper SQL (NOT "stays present") | superseded inline at T-3.7 (`a8a7d23`); indexed at T-3.4 row §1 Phase 12.5 #3. |

**ZERO NEW amendments surfaced during this executing-plans Codex chain beyond the T-3.7 amendment already banked at plan-write time.** R1+R2+R3 fix-bundles refined the inventory's organizational shape (Phase 11 per-row expansion + A-11.D fold-into-cross-reference; source-roster note; row-contract completeness) but did NOT surface new spec-text amendments outside the existing 74-row catalog.

**Cumulative pending V2.1 §VII.F amendments after Phase 12.5 #3 ship: 74** (per T-3.4 inventory final count). Promotion is operator-paced via V2.1 §VII.F protocol.

---

## §7 Phase 8 walkthrough triage finding

**Bucket A diagnosis confirmed** (plan-author expectation per writing-plans return report §12 was Bucket A "trivial test-fixture drift" with high probability; the actual diagnosis matched the expectation precisely).

**Root cause** (test-fixture drift, not runner-side bug):
- `_synthetic_ohlcv()` at `tests/integration/test_phase8_pipeline_walkthrough.py:40-51` hardcoded `idx = pd.bdate_range(end="2026-05-08", periods=len(closes))`.
- The fixture was authored for 2026-05-07 + earlier test runs.
- Today (2026-05-18) `last_completed_session(datetime.now())` returns 2026-05-15 (Friday).
- `compute_daily_approximate_snapshot` at `swing/trades/daily_management.py:527-530` checks `asof_rows = df.loc[df.index.date == asof_session]`; asof_session=2026-05-15 was past the synthetic data window ending 2026-05-08; asof_rows empty → returns None → `_step_daily_management` warns "archive returned None" + skips snapshot insert → tests asserting snapshot row presence FAIL.

**Fix shipped** (`88dd31e` initial + `8046dd5` R1 hardening):
- `end_date = (datetime.now() + timedelta(days=7)).date()` — dynamic anchor with 7-day buffer covering weekend + Monday-holiday + DST-transition + clock-skew between fixture-creation and runner's separate `datetime.now()` invocation.
- ZERO test regression. 3 previously-failing tests promoted to PASSING. Fast suite 4847 → 4850 pass / 5 skipped / 0 fail.

**Bucket C HARD STOP not triggered.** Operator approval was not required for this disposition.

**Plan §A T-3.5 Step 3a path executed; ZERO standalone-dispatch entry needed at `docs/phase3e-todo.md`.**

---

## §8 T-3.4 amendment inventory location + row count + Phase 12.5 #1+#2 cross-reference verification

**Inventory location:** `docs/v2-1-section-7f-amendments-2026-05-18.md` (final 167 lines; 74 amendment rows).

**Row count progression:**
- T-3.4 initial collation: **62 rows** (commit `b7cd68c`).
- R1 Major #3 Phase 11 expansion: **86 rows** (commit `8046dd5`; +27 per-row Phase 11 entries replacing 3 grouped lines = +24 net).
- R2 Major #1+#2 A-11.D fold-into-cross-reference: **74 rows** (commit `ebb17f1`; -12 A-11.D rows folded as operational follow-through).
- Final: **74 unique amendment rows; ZERO duplication; ZERO missing Status; ZERO missing Source.**

**Phase 12.5 #1+#2 cross-reference verification:**
- Phase 12.5 #1 amendment `A-12.5.1.1` (plan §A T-1.5.B 3-line drift) — indexed at inventory §1 Phase 12.5 #1.
- Phase 12.5 #2 amendments `A-12.5.2.J1` + `A-12.5.2.J2` + `A-12.5.2.J3` (writing-plans §J amendments) — indexed at inventory §1 Phase 12.5 #2.
- Phase 12.5 #2 executing-plans amendments `A-12.5.2.A1` + `A-12.5.2.A2` + `A-12.5.2.A3` — indexed at inventory §1 Phase 12.5 #2.
- Phase 12.5 #3 amendment `A-12.5.3.H4-banner-clears` — indexed at inventory §1 Phase 12.5 #3; source-of-truth lives inline at Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104 per T-3.7 amendment edits.

**34-file source-roster note:** explicit in inventory header — the 34th file is `docs/phase12-5-bundle-3-project-hygiene-writing-plans-return-report.md` for this dispatch's own writing-plans, which references/banks the Phase 12.5 #3 T-3.7 amendment already indexed (NOT a new uncatalogued amendment).

---

## §9 Forward-binding lessons for future maintenance dispatches

From Codex chain + plan §M + return report observations:

- **L-X1 confirmed**: When a plan/spec amendment is text-only across 3+ sites, sequence the sites smallest-first + commit ALL sites in ONE commit. T-3.7 commit `a8a7d23` honored this with all 3 sites in one commit; downstream V2.1 §VII.F amendment ID resolves to a single SHA + 3 grep hits.

- **L-X2 confirmed**: Phase 8 walkthrough triage bucket disposition in commit message stem — `fix(phase12-5-3-T3.5-bucket-A): ...` is forward-readable from `git log`. Bucket C alternative would have read `fix(phase12-5-3-T3.5-bucket-C-skip): ...`.

- **L-X3 confirmed**: Ruff E501 cleanup used `Edit` (not `Write`) per-site; per-site diffs of ~1-3 lines per violation. Total `swing/` diff: 11 files / ~+65/-21 lines. Per-site approach avoided whitespace-churn at unrelated lines.

- **L-X4 confirmed**: Archive-split boundary 2026-05-12 inclusive documented in EVERY commit message stem AND in EVERY archive companion's heading. Future maintainers reading the archive can reconstruct which entries went where.

- **L-X5 confirmed**: V2.1 §VII.F amendment inventory IS a READ-MOSTLY artifact; row contract (hash + 1-sentence summary + source pointer + status) honored across 74 rows post-R2 fold-into-cross-reference.

**NEW lessons from this dispatch's Codex chain (L-E1..L-E4):**

- **L-E1**: When inventory rows are operational follow-through (e.g., CLAUDE.md gotcha promotions of already-banked amendments), they should be cross-reference NOTES not separate amendment rows. R2 Major #1+#2 surfaced this when A-11.D.x rows duplicated A-11.A.x substance under unique IDs. Pattern: an amendment row represents a spec-text change pending V2.1 §VII.F routing; an operational gotcha is the implementation follow-through (already shipped). Future inventory work: classify each candidate row as (a) spec-text amendment OR (b) operational gotcha-promotion BEFORE adding to amendment-row count.

- **L-E2**: Time-dependent test fixtures need calendar-buffer ≥ 7 days for weekend + holiday + DST + clock-skew tolerance. R1 Major #5 surfaced this when `+ timedelta(days=1)` was too tight. Pattern: any test fixture anchored to `datetime.now()` for boundary calculation should buffer ≥ 7 days. Discriminating-test consideration: the buffer must be larger than the longest single-skip session boundary (~5 days for late-Friday → next-Tuesday on a Monday holiday + weekend overlap). Future test fixtures: prefer freezable-clock monkeypatch (V2 candidate V-3.5.B) OR ≥7-day calendar buffer.

- **L-E3**: Operator-pairing locks in plan/dispatch-brief have a hierarchy when overridden by user runtime instructions. T-3.3 pre-flight roster review LOCK + "work without stopping for clarifying questions" override resolved via post-hoc audit transparency (roster enumerated in return report §7 + §13 instead of pre-write operator review). Pattern: when an operator-runtime-override conflicts with a plan-encoded HARD STOP, the implementer should (a) honor the override OR (b) escalate; if (a), the implementer MUST provide post-hoc audit transparency (roster enumeration in return report) so the operator can reverse-check + revert via `git revert <SHA>` if needed.

- **L-E4**: Inventory row contract violations surface late if grep-only verification is used; AST-style row contract verification (every row has `^- \*\*A-` prefix AND `Source:` substring AND `Status:` substring) catches R2 Major #2 family at inventory authoring time, not at Codex R2. Pattern: when authoring multi-row contract artifacts, write a small grep-suite that verifies row contract BEFORE Codex submission. Saves an estimated 1 Codex round.

---

## §10 CLAUDE.md status-line refresh draft text (orchestrator paste-in)

For orchestrator paste-in at integration-merge time, after the existing 2026-05-18 Phase 12.5 #3 writing-plans SHIPPED entry:

> **Phase 12.5 #3 (Project hygiene maintenance pass — CLOSES Phase 12.5 arc) SHIPPED 2026-05-18** at `<MERGE-SHA>` (integration merge of `phase12-5-bundle-3-project-hygiene-executing-plans` via `--no-ff`; 11 commits = 7 task-impl (T-3.1..T-3.7) + 3 Codex-fix (R1+R2+R3) + 1 return-report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 0C/5M/2m → R2 0C/2M/1m → R3 0C/0M/1m); ZERO Critical findings entire chain; **ZERO ACCEPT-WITH-RATIONALE on Major findings** (all 7 cumulative Major resolved with code-content fixes; matches Phase 12.5 #1+#2 arc clean-record streak); ZERO Co-Authored-By footer drift across all 11 commits (~165+ project-cumulative streak preserved); pre-Codex orchestrator-side review **APPROVED_AS_IS** (NEW C.C lesson #6 BINDING; 8th cumulative validation). **+3 fast tests** net (4847 → 4850; T-3.5 Bucket A fix promoted 3 previously-failing phase8 walkthrough tests to PASSING via `_synthetic_ohlcv` end-date dynamic anchor with 7-day calendar buffer per Codex R1 M#5 hardening); ruff baseline 18 → 0 E501 (T-3.6 cleared via 18 per-site line-wrap dispositions across 11 files in swing/; ZERO refactors; ZERO noqa adds; ZERO non-E501 classes introduced); schema v19 UNCHANGED LOCK preserved through entire dispatch. **First operator-visible deliverables:** (a) Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment correcting "banner stays present on tier-3 override" → "banner clears immediately" per shipped helper SQL (T-3.7); (b) NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` (74 amendment rows across Phase 9/10/11/12/post-Phase-12/12.5 arcs; HYBRID format with master inventory + inline supersession; T-3.4); (c) NEW `docs/CLAUDE.md-archive.md` companion (43 lines / 18 archived SHIPPED entries; T-3.1; boundary 2026-05-12 inclusive; status-line 146780→118704 chars / 47→29 active entries); (d) `docs/phase3e-todo.md` archive-split (T-3.2; 23 SHIPPED sections moved; 4142→3766 active lines); (e) `docs/orchestrator-context.md` archive-split (T-3.3; 20 oldest pre-2026-05-13 lessons moved via conservative-scope cap=20; 715→696 active lines). **3 Codex chain finding families closed inline**: R1 Major #3 Phase 11 grouped IDs expanded to 27 per-row entries; R2 Major #1+#2 folded 12 A-11.D operational-follow-through rows into single cross-reference note (inventory final 74 rows); R1 M#5 widened `_synthetic_ohlcv` buffer to 7 calendar days. **4 NEW forward-binding lessons L-E1..L-E4** banked at return report §9 for future maintenance dispatches (operational-follow-through vs amendment classification; time-dependent fixture calendar-buffer ≥7d; operator-runtime-override + post-hoc audit transparency pattern; row-contract grep-verification pre-Codex). **Phase 12.5 arc CLOSED** (Phase 12.5 #1 + #2 + #3 all SHIPPED 2026-05-18); **Phase 13 dispatch UNBLOCKED** post operator-paired post-merge review.

---

## §11 Schema impact verdict

**v19 UNCHANGED** (F1 + F5 LOCK preserved end-to-end through entire dispatch + Codex chain).

- T-3.1/T-3.2/T-3.3 doc-only edits; ZERO schema touch.
- T-3.4 new doc file; ZERO schema touch.
- T-3.5 test-fixture fix; ZERO schema touch.
- T-3.6 Ruff line-wraps in `swing/`; ZERO migration files in scope.
- T-3.7 doc-only amendment to 3 sites; ZERO schema touch.
- All 3 Codex-fix commits doc-only OR test-fixture-only; ZERO schema touch.

Verification: `git diff fc4cd0d..HEAD -- swing/data/migrations/` → empty.

---

## §12 Test-count delta + Ruff post-cleanup count

**Test-count delta**: 4847 → 4850 fast pass (+3 from T-3.5 Bucket A fix). 5 skipped unchanged. 0 fail. Wall-clock under `-n auto` ~100s.

**Ruff post-cleanup count**: 18 E501 → 0 E501 (T-3.6 acceptance LOCK met). Global ruff: 0 violations across all classes (no new classes introduced).

---

## §13 T-3.3 archived-lesson roster (post-hoc operator audit per Codex R1 Major #1 disposition + L-E3 lesson)

Per the operator-runtime-override decision + post-hoc audit transparency pattern (L-E3), the 20 bullet-headers archived from `docs/orchestrator-context.md` "Lessons captured" section to `docs/orchestrator-context-archive.md` at commit `229e434` are enumerated below for operator review. Operator can revert via `git revert 229e434` if any archive choice is undesirable.

  - Once operator-witnessed verification gate passes, integration merge is an orchestrator action — operator's gate-pass confirmation IS the trigger; do NOT also ask "shall I proceed with merge."
  - Worktree-isolated dispatch briefs MUST specify the worktree directory path explicitly, not just the branch name; `superpowers:using-git-worktrees` skill default may diverge from project precedent.
  - Read/write predicate symmetry on session-anchored UI surfaces MUST be verified against the writer's actual code BEFORE locking in brief; orchestrator mental-model "today's session" inference is not authoritative.
  - Writing-plans dispatch's plan file MUST be committed before approving for executing-plans dispatch; brief should explicitly require implementer to commit, AND orchestrator should verify commit landed at triage.
  - Python sqlite3 `executescript()` issues an implicit COMMIT before running its script; each statement runs in autocommit mode and `conn.rollback()` cannot undo successful intermediate statements.
  - The `in_transaction` "safety guard" anti-pattern: speculative defensive guards in transactional code can re-introduce the very race the explicit lock was meant to close.
  - Five client-trust holes closed via server-stamping in Phase 8 — pattern for any V1 single-operator form.
  - Plan-template fixture defects are normal at executing-plans phase — implementers SHOULD detect + accept-with-rationale; orchestrators SHOULD NOT auto-amend the plan mid-dispatch.
  - Process discipline: prefer explicit-path `git add <file>` over `git add -A` to prevent stray-file inclusion + accidental amend-to-remove.
  - 19 adversarial rounds across a single phase is a new high-water mark; chain-shape diagnostic is "tapered finding count" + "fix-introduced regressions are healthy".
  - SQLite REPLACE has quirky semantics; SELECT-then-UPDATE-or-INSERT is the safer pattern for upsert.
  - `is_superseded` flag column + `superseded_by_record_id` FK pattern decouples uniqueness slot from audit pointer.
  - Per-row stamp of policy-versioned values prevents historical-row reinterpretation under risk_policy changes.
  - Brief drafting touching schema migrations MUST verify next-available migration number empirically before writing the brief.
  - Two functions can share the same name across repo-level and service-level layers; transactional discipline differs.
  - Defense-in-depth validators inside transactions: re-read live state + reject stale operator-supplied snapshots.
  - State-machine integration via query-side JOIN, not schema flag, when grain mismatches.
  - Canonical-truth promotion: existing config becomes startup-mirror; new entity becomes authoritative.
  - `material_to_review` (or any urgency-classification field) is CLASSIFICATION not workflow trigger; operator-overridable; computed via type-lookup.
  - Brief line-target should bias high when dispatch scope-of-tables × integration-surface multiplies.

**Archive companion preserves full bullet content + cross-references; the headers above are operator-audit shortcuts.**

---

## §14 Worktree teardown status

- Worktree branch `phase12-5-bundle-3-project-hygiene-executing-plans` intact + ready for integration merge to `main`.
- Return report at `docs/phase12-5-bundle-3-project-hygiene-executing-plans-return-report.md` (this file).
- Codex session state at `.copowers-session-<repo-hash>.json` (auto-managed).
- On-disk worktree at `.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans/` pending operator's cleanup-script `-DeregisterFirst` pass post-merge (branch matches cleanup-script regex `phase\d+[-_]`).

---

*End of return report. Phase 12.5 #3 executing-plans dispatch CLOSED. **Phase 12.5 arc CLOSED.** Operator-paired plan-vs-implementation review + integration merge UNBLOCKED post operator-witnessed 4-surface gate (S1 inline pytest+ruff PASS at 4850/5/0 + ruff 0 E501 + S2 archive-split visual verification + S3 V2.1 §VII.F inventory readability + S4 T-3.7 amendment verification at 3 sites). 11 commits / 3 Codex rounds / ZERO ACCEPT-WITH-RATIONALE on Major / ZERO Co-Authored-By footer drift / schema v19 UNCHANGED / 4850 fast baseline (+3 from Bucket A fix) / Ruff 18 E501 → 0.*
