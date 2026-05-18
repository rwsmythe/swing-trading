# Phase 12.5 #3 — Project Hygiene Maintenance Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per project convention, the executing-plans dispatch wraps in `copowers:executing-plans` (adds adversarial Codex review).

**Goal:** Land the Phase 12.5 #3 project-hygiene maintenance pass — archive-split 3 cap-drifting docs, batch-bank ~30+ pending V2.1 §VII.F amendments, triage the 3 pre-existing Phase 8 walkthrough failures, clear Ruff 18 E501 baseline, and amend Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 mirror wording to match shipped helper semantics.

**Architecture:** Maintenance-only — ZERO new architectural surfaces. Mechanical text moves + 1 small Phase 8 triage decision (fix-or-skip) + Ruff line-wrap cleanup. Schema v19 UNCHANGED. ZERO new runtime production code expected (T-3.5 MAY add a small runner fix if root-cause is small + safe; bounded by scope-cap in §F).

**Tech Stack:** Python 3.14, pytest, Ruff, SQLite (v19). No new dependencies.

---

## Table of contents

- §0 Plan overview + cross-references
- §1 Operator-locked decisions roll-up (2 locks; verbatim)
- §A Task list (T-3.1 .. T-3.7; per-task scope + steps + acceptance + tests + commit stem)
- §B Cross-bundle pins (none expected; documented negative)
- §C Task ordering rationale
- §D Locked decisions roll-up
- §E Test projection (~+0 to ~+5 fast tests; ~+50-200 LOC moves)
- §F Pre-flight verifications + escalation rules + scope-cap notes
- §G Per-task acceptance narratives (binding contracts)
- §H Operator-witnessed gate plan (4 surfaces)
- §I Cross-bundle invariants (Co-Authored-By streak; schema v19; Ruff post-cleanup target)
- §J If you get stuck
- §K V2 candidates banked
- §L V2.1 §VII.F amendments banked (this dispatch's own; forward-pointer to T-3.4)
- §M Forward-binding lessons for executing-plans

---

## §0 Plan overview + cross-references

**Brief:** `docs/phase12-5-bundle-3-project-hygiene-writing-plans-dispatch-brief.md` (this dispatch's source-of-truth contract).

**Brainstorm:** SKIPPED per operator-lock §1.1 (this plan is the implementation contract for the brief).

**Sequencing:** Phase 12.5 #2 SHIPPED at `0cecf28` (16 task commits + 1 orchestrator-inline gate-fix + 4 Codex-fix bundles). Phase 12.5 #3 is the LAST Phase 12.5 dispatch before Phase 13 commission. Schema v19 expected to remain UNCHANGED end-to-end.

**Baseline at plan-write time** (verified via worktree-side `python -m pytest -m "not slow" -q -n auto` at branch `phase12-5-bundle-3-project-hygiene-writing-plans` HEAD `3b4bd53`):
- **4847 fast passing**
- **3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures** (brief §3 watch item #9 noted handoff doc said 4847 but brief author observed 4851 — plan-author fresh baseline came back at exactly 4847, matching the handoff doc + matching CLAUDE.md banked baseline; **4847 is the authoritative figure for this plan**; the 4851 in the brief may reflect a transient between brief-write and plan-write OR a transient delta now reverted)
- **5 skipped** (1 evaluation-patterns; 4 Schwab CSV fixture-gated)
- **Ruff 18 E501** baseline
- **Wall-clock:** 81.37s under `-n auto`

**Cap-drift inputs** (verified via `wc -l` at plan-write time):
- `CLAUDE.md`: 138 lines total — **line 3 is 143,843 characters** (the single physical status-line "PARAGRAPH" with ~70 SHIPPED entries crammed via bold separators). This is the primary T-3.1 archive-split target.
- `docs/phase3e-todo.md`: 4014 lines. Companion `docs/phase3e-todo-archive.md`: 990 lines.
- `docs/orchestrator-context.md`: 708 lines. Companion `docs/orchestrator-context-archive.md`: 140 lines.

**Amendment inputs** (cataloged at T-3.4):
- Phase 12.5 #1 plan §H.4 wording + spec §9.3 S4 mirror + spec §5 line-104 table-cell mirror (T-3.7 sub-targets).
- Phase 12.5 #2 NEW A1/A2/A3 (from `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md` §7).
- ~30+ cumulative pending amendments across Phase 9 + Phase 10 + Phase 11 + Phase 12 + Phase 12.5 return reports.

**Targeted T-3.7 amendment text** (verbatim shipped-helper semantic):

- Plan §H.4 line 1071 currently says: *"Tier-3 override does NOT clear the banner mid-window — invoke `apply_tier3_override` on the auto-redirected chain head + assert banner STILL present + count unchanged"*.
- Spec §9.3 S4 (line 940) carries the same claim verbatim with longer explanatory text.
- Spec §5 line 104 (a `tests/web/test_dashboard_banner.py` table cell) says *"assert banner UNCHANGED (Codex R4 minor 2 + R5 minor 1 LOCK)"*.
- **Shipped helper** (`swing/metrics/discrepancies.py:count_recent_multi_leg_auto_corrections`) reads `WHERE rd.resolved_by = 'auto_tier1_multi_leg' AND rc.reconciliation_run_id = latest_completed_run_id`. The helper joins on `reconciliation_discrepancies.resolved_by`, so any path that flips a parent discrepancy's `resolved_by` from `'auto_tier1_multi_leg'` to `'operator'` IMMEDIATELY drops the discrepancy from the helper count. `apply_tier3_override` does precisely this on the chain head per Sub-bundle C.C `_handle_operator_override`.
- **Operator-accepted semantic** (2026-05-18 lock §1.2): banner clears immediately on tier-3 override is correct + accepted. Plan/spec text is wrong; code is right. Amend text-only.

---

## §1 Operator-locked decisions roll-up (verbatim from brief §1)

### §1.1 Dispatch shape — SKIP BRAINSTORM

Operator-locked 2026-05-18 post-Phase-12.5-#2-merge. NO design spec at `docs/superpowers/specs/...phase12-5-3...`. This plan absorbs architectural-surface review during the Codex chain.

### §1.2 Item #5 disposition — AMEND PLAN/SPEC TEXT ONLY

Operator-locked 2026-05-18. NO code fix for tier-3-override-banner-clear semantic. Shipped behavior (banner clears immediately when override flips `resolved_by` from `'auto_tier1_multi_leg'`) is the operator-accepted semantic. T-3.7 amends 3 sites (plan §H.4 + spec §9.3 S4 + spec §5 line 104 table cell). V2.1 §VII.F amendment banked in T-3.4 catalog.

### §1.3 Schema v19 UNCHANGED LOCK (durable; carries from Phase 12.5 #1 + #2)

If any task surfaces a need for schema work, **STOP + escalate** per §F escalation rule. T-3.5 Phase 8 triage is the only task with non-zero schema risk; §F caps the scope.

### §1.4 ZERO Co-Authored-By footer drift (durable project invariant)

Cumulative streak ~163+ commits across Phase 11/12/post-Phase-12/Phase-12.5. Every commit message stem in §A explicitly cites suppression. Executing-plans dispatch prompt MUST include the suppression citation verbatim.

---

## §A Task list

Each task ships green standalone (per-task pytest sweep at commit time). All task commits land on the executing-plans worktree branch `phase12-5-bundle-3-project-hygiene-executing-plans` (NEW worktree; this writing-plans dispatch's branch is `phase12-5-bundle-3-project-hygiene-writing-plans`).

### Task T-3.7 — Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment

**Files:**
- Modify: `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md:1071`
- Modify: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md:940` (§9.3 S4 longer block)
- Modify: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md:104` (§5 file-table row for `tests/web/test_dashboard_banner.py`)

**Why this is task #1:** Smallest task, well-bounded (3 specific text sites verified at plan-write time via grep). De-risks T-3.4 since the amendment text becomes an inventory entry. ZERO code-fix scope (operator-locked §1.2).

- [ ] **Step 1: Verify the 3 target sites exist verbatim** (defensive — guard against drift if these docs were re-touched).

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
grep -n "Tier-3 override does NOT clear the banner mid-window" docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md
grep -n "Tier-3 override does NOT clear the banner mid-window" docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md
grep -n "assert banner UNCHANGED" docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md
```

Expected: 1 line each.

- [ ] **Step 2: Amend plan §H.4 line 1071** — supersede the current bullet with a forward-binding supersession note prepended in-place.

Replace the bullet text with:

```markdown
- **AMENDMENT (Phase 12.5 #3 at <THIS-SHA>):** Banner CLEARS immediately when tier-3 override flips parent discrepancy `resolved_by` from `'auto_tier1_multi_leg'` to `'operator'`. Prior claim that banner persists with count unchanged is INCORRECT per shipped helper SQL — `swing/metrics/discrepancies.py:count_recent_multi_leg_auto_corrections` queries `WHERE rd.resolved_by = 'auto_tier1_multi_leg'`; `apply_tier3_override` writes a NEW correction row + UPDATEs the parent discrepancy `resolved_by` to `'operator'`, which immediately drops the row from the helper count. The operator-accepted semantic is "banner clears on override" — V1 ship behavior is correct; only this plan-text claim is wrong. Banked as V2.1 §VII.F amendment at `docs/v2-1-section-7f-amendments-2026-05-18.md`.
```

`<THIS-SHA>` is filled in at commit time after the file edit (placeholder during the Edit; replaced with actual abbreviated SHA via `git commit --amend` OR left as the literal string for the task commit + replaced by a 2nd commit if simpler — implementer decides).

- [ ] **Step 3: Amend spec §9.3 S4 line 940** — same supersession pattern; replace from "Tier-3 override does NOT clear" through "next reconciliation_run completion flips the helper's `latest_run_id` -> banner clears." with:

```markdown
**AMENDMENT (Phase 12.5 #3 at <THIS-SHA>):** Banner CLEARS immediately when tier-3 override flips parent discrepancy `resolved_by` to `'operator'`. The shipped helper queries `WHERE rd.resolved_by = 'auto_tier1_multi_leg'`; `apply_tier3_override` UPDATEs the parent discrepancy `resolved_by`, dropping the row from the count instantly. Discriminating test for S4 amends to: plant a multi-leg auto-correction -> curls dashboard -> grep banner present -> invokes tier-3 override on the chain head -> curls again -> grep banner ABSENT (count drops to 0 if this was the only auto-redirect in the latest run; else N-1). The "preserves vigilance signal" rationale in the prior text is incorrect; the shipped semantic is "banner reflects current state of unresolved auto-redirects". Banked as V2.1 §VII.F amendment.
```

ASCII-only (NO arrow glyphs; use `->`).

- [ ] **Step 4: Amend spec §5 line 104 table-cell** — replace the cell `"assert banner UNCHANGED (Codex R4 minor 2 + R5 minor 1 LOCK)"` with `"assert banner count drops (per Phase 12.5 #3 amendment of §9.3 S4)"`.

- [ ] **Step 5: Run discriminating verification grep** — verify each amended site contains the literal "AMENDMENT (Phase 12.5 #3" marker.

```bash
grep -n "AMENDMENT (Phase 12.5 #3" docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md
```

Expected: 3 hits (1 in plan; 2 in spec).

- [ ] **Step 6: Commit (no test changes; doc-only).**

```bash
git add docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md \
        docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md
git commit -m "docs(phase12-5-3-T3.7): amend phase12-5-1 plan H.4 + spec 9.3 S4 + spec 5 line-104 — banner clears on tier-3 override (no Co-Authored-By footer per project invariant; ~163+ commit streak)"
```

**Acceptance:**
- 3 grep hits for "AMENDMENT (Phase 12.5 #3" across the 2 files.
- No code touched. No tests touched. No new files.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

### Task T-3.5 — Phase 8 walkthrough failing-test triage

**Files:**
- Investigate: `tests/integration/test_phase8_pipeline_walkthrough.py:196-491` (3 failing tests + 1 Codex R1 discriminator that also fails)
- Possibly modify: `swing/pipeline/runner.py` and/or `tests/integration/test_phase8_pipeline_walkthrough.py` (depends on root-cause classification per §F escalation rule)
- Possibly modify: `docs/phase3e-todo.md` (add a forward-binding ticket if accepted-as-skip)

**Why this is task #2:** Investigation might reveal scope creep — do early to fail-fast at §F escalation if root-cause is architectural. Banked failure description "archive returned None" suggests `read_or_fetch_archive` monkeypatch wiring drift; may be a 1-line test-side fix OR a runner-side fix.

- [ ] **Step 1: Reproduce the failures with full tracebacks + verify 3-fail/1-pass inventory holds at task time** (R5 Minor #2 LOCK).

First run the WHOLE file to verify the 3-fail/1-pass inventory matches plan §A T-3.5 Step 3b table:

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
python -m pytest tests/integration/test_phase8_pipeline_walkthrough.py -v 2>&1 | tail -20
```

Expected: 3 FAIL + 1 PASS (matching plan table). If the inventory has drifted (e.g., test #3 now also fails OR test #4 now passes), STOP + reconcile before proceeding; the Bucket C skip-set + expected count math depends on the inventory.

Then capture the full traceback for diagnosis of test #1 (the canonical "archive returned None" failure):

```bash
python -m pytest tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_emits_snapshots_for_open_trades_only -xvs 2>&1 | tail -60
```

- [ ] **Step 2: Diagnose root-cause** — classify into ONE of three buckets:
  - **Bucket A: Trivial test-fixture drift** (e.g., `synthetic_pipeline_env` no longer monkeypatches the right import path, archive helper signature changed, OHLCV dataframe column shape drift). Implementer proceeds directly to Step 3a fix. Estimated impact: ~+0 tests, runtime unchanged.
  - **Bucket B: Small runner-side bug surfaced by the fixture** (e.g., `_step_daily_management` lazy-import path changed, monkeypatch target invalidated by a recent refactor). Implementer proceeds directly to Step 3a fix (smallest-possible runner adjustment + verify no other tests regress). Estimated impact: ~+0 tests, no production-behavior change.
  - **Bucket C: Architectural issue requiring deeper Phase 8 refactor** (e.g., archive contract changed under a recent feature; multiple downstream consumers affected). **HARD STOP — DO NOT PROCEED TO STEP 3.** Implementer must escalate to operator with a brief diagnosis summary (1-2 paragraphs: root-cause hypothesis + scope estimate + recommended disposition). Operator decides whether to (a) authorize the `@pytest.mark.skip` + phase3e-todo ticket workflow described in Step 3b, OR (b) redirect to a different disposition (e.g., narrower fix, immediate standalone-dispatch carve-out, accept-as-failing pending Phase 13). Step 3b workflow is the operator's DEFAULT-but-not-pre-authorized fallback; ONLY proceed to Step 3b after explicit operator approval.

- [ ] **Step 3a (Bucket A or B only): Implement the smallest possible fix + verify.**

Run the targeted test suite first:

```bash
python -m pytest tests/integration/test_phase8_pipeline_walkthrough.py -xvs 2>&1 | tail -15
```

Expected: 4/4 PASS (3 original + the Codex R1 discriminator).

Then run the full fast suite to verify zero regression:

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
```

Expected: 4847+4 = 4851 fast pass (no other regression); 0 failures; 5 skipped (unchanged); ruff baseline 18 unchanged.

- [ ] **Step 3b (Bucket C only — REQUIRES OPERATOR APPROVAL FROM STEP 2 ABOVE): Document the architectural issue + skip the 3 tests.**

Add `@pytest.mark.skip(reason="...")` decorators to the **3 currently-failing tests** with verbatim rationale citing the standalone-dispatch ticket. **Test inventory** (R4 Major #1 LOCK — `test_phase8_pipeline_walkthrough.py` has 4 tests total: 3 currently failing + 1 currently passing; the "Codex R1 discriminator" mentioned in earlier briefs IS `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id` at line 415, which is ONE OF the 3 currently failing — NOT a 4th distinct test):

| # | Test name | File line | Current status | Bucket C action |
|---|---|---|---|---|
| 1 | `test_phase8_pipeline_emits_snapshots_for_open_trades_only` | 196 | FAIL | SKIP |
| 2 | `test_phase8_pipeline_second_same_day_run_upserts` | 258 | FAIL | SKIP |
| 3 | `test_phase8_pipeline_record_event_log_after_run_links_correctly` | 329 | PASS | DO NOT SKIP |
| 4 | `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id` (Codex R1 discriminator) | 415 | FAIL | SKIP |

Skip set: tests 1, 2, 4. Test 3 stays as-is (currently passing).

Append to `docs/phase3e-todo.md` (above existing entries, below the Phase 12.5 #3 SHIPPED entry once that's written):

```markdown
### Phase 8 walkthrough archive-contract drift (Phase 12.5 #3 triage findings — banked as V2 standalone-dispatch)

**Status:** **3 tests** in `tests/integration/test_phase8_pipeline_walkthrough.py` SKIPPED via `@pytest.mark.skip` decorators since Phase 12.5 #3 at `<THIS-SHA>` (the 3 currently-failing tests per R4 Major #1 LOCK; test #3 `test_phase8_pipeline_record_event_log_after_run_links_correctly` stays passing). Pre-existing failures known since Phase 7 ship (`622c669` HEAD); banked at every gate since C.A. Phase 12.5 #3 T-3.5 investigation diagnosed root cause as <root-cause-summary-from-investigation>. Architectural scope exceeded T-3.5 fix-or-document cap; deferred as standalone post-Phase-12.5 dispatch. Post-skip suite state: 4847 pass / 8 skipped / 0 fail.

**Repro:** `python -m pytest tests/integration/test_phase8_pipeline_walkthrough.py -xvs` (with the skip decorators temporarily removed).

**Dispatch readiness:** orchestrator briefs the fix at next session.
```

Then verify the full suite is GREEN (no failures; 3 fewer passes; 4 more skipped):

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
```

Expected: **4847 pass + 0 fail + 8 skipped** (was 5 skipped; +3 added per skip set above; test #3 remains in the 4847 passing bucket; R4 Major #1 LOCK corrects prior plan-author miscount of "4 tests / -3 from passing / 4844 pass + 9 skipped").

- [ ] **Step 4: Commit.**

```bash
git add tests/integration/test_phase8_pipeline_walkthrough.py [+ swing/pipeline/runner.py if Bucket B + docs/phase3e-todo.md if Bucket C]
git commit -m "fix(phase12-5-3-T3.5): phase8 walkthrough triage — <bucket A/B/C disposition + 1-line summary> (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- Buckets A/B: all 4 phase8-walkthrough tests PASS; full suite green; ruff 18 unchanged.
- Bucket C (**if operator-approved skip-pattern disposition at Step 2 escalation**): **3 tests SKIPPED** with rationale (the 3 currently-failing tests; test #3 stays passing); phase3e-todo entry added; full suite green (no failures); **4847 pass / 8 skipped / 0 fail**; ruff 18 unchanged; `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0. Bucket C with alternative operator-approved disposition: acceptance criteria adjust per operator decision.

---

### Task T-3.6 — Ruff 18 E501 cleanup

**Files:** 18 line-numbered sites across `swing/` (canonical roster fetched via `ruff check swing/ --select E501 --output-format full` at task time).

**Why this is task #3:** Mechanical; safe to ship after T-3.7 + T-3.5 because the diff is small + non-intersecting with the other archive-split text moves.

- [ ] **Step 1: Enumerate the 18 violations + verify against plan-write-time roster.**

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
ruff check swing/ --select E501 --output-format concise 2>&1 | tee /tmp/ruff-e501-roster.txt
```

**Plan-write-time roster** (verified at branch `phase12-5-bundle-3-project-hygiene-writing-plans` HEAD `3b4bd53` via `ruff check swing/ --select E501 --output-format concise`):

| # | File:line | Length |
|---|---|---|
| 1 | `swing/cli.py:894` | 114 |
| 2 | `swing/cli.py:932` | 105 |
| 3 | `swing/cli.py:968` | 104 |
| 4 | `swing/config.py:407` | 102 |
| 5 | `swing/config.py:412` | 107 |
| 6 | `swing/config_overrides.py:156` | 101 |
| 7 | `swing/evaluation/criteria/trend_template.py:46` | 102 |
| 8 | `swing/evaluation/criteria/trend_template.py:68` | 102 |
| 9 | `swing/recommendations/build.py:87` | 103 |
| 10 | `swing/rendering/briefing.py:123` | 105 |
| 11 | `swing/rendering/briefing_md.py:32` | 117 |
| 12 | `swing/rendering/briefing_md.py:40` | 123 |
| 13 | `swing/rendering/briefing_md.py:50` | 102 |
| 14 | `swing/trades/advisory.py:82` | 108 |
| 15 | `swing/web/routes/trades.py:1029` | 113 |
| 16 | `swing/web/routes/trades.py:1101` | 133 |
| 17 | `swing/web/view_models/dashboard.py:1398` | 101 |
| 18 | `swing/web/view_models/trades.py:458` | 105 |

If task-time roster diverges from the plan-write-time list above (drift expected on touched-files between plan-write and task), implementer dispositions the new set; the count 18 is the target.

- [ ] **Step 2: Per-violation disposition table** (R2 Major #3 — full 18-row roster with per-site disposition; plan-author defaults are LINE-WRAP for all 18 since E501 is whitespace-only by nature; implementer MAY revise per-site at task time if line-wrap produces awkward semantics):

| # | Site | Length | Default disposition | Rationale (plan-author best-effort; implementer revises if needed) |
|---|---|---|---|---|
| 1 | `swing/cli.py:894` | 114 | Line-wrap | CLI help/error string; trivially wrappable preserving message text |
| 2 | `swing/cli.py:932` | 105 | Line-wrap | CLI help/error string; wrap at natural clause boundary |
| 3 | `swing/cli.py:968` | 104 | Line-wrap | CLI help/error string; wrap at natural clause boundary |
| 4 | `swing/config.py:407` | 102 | Line-wrap | likely config error message or dataclass default; wrap at clause |
| 5 | `swing/config.py:412` | 107 | Line-wrap | same family as #4 |
| 6 | `swing/config_overrides.py:156` | 101 | Line-wrap | 1-char overrun; trivial wrap |
| 7 | `swing/evaluation/criteria/trend_template.py:46` | 102 | Line-wrap | criteria definition; preserve readability |
| 8 | `swing/evaluation/criteria/trend_template.py:68` | 102 | Line-wrap | same family as #7 |
| 9 | `swing/recommendations/build.py:87` | 103 | Line-wrap | sizing helper; wrap at function-call or operator boundary |
| 10 | `swing/rendering/briefing.py:123` | 105 | Line-wrap | briefing renderer; wrap at format-string clause |
| 11 | `swing/rendering/briefing_md.py:32` | 117 | Line-wrap | markdown template; wrap at format clause |
| 12 | `swing/rendering/briefing_md.py:40` | 123 | Line-wrap | same family as #11 |
| 13 | `swing/rendering/briefing_md.py:50` | 102 | Line-wrap | same family as #11 |
| 14 | `swing/trades/advisory.py:82` | 108 | Line-wrap | f-string param list; wrap across 2 lines preserving message format |
| 15 | `swing/web/routes/trades.py:1029` | 113 | Line-wrap (inline comment shorten or move above) | inline comment overrun |
| 16 | `swing/web/routes/trades.py:1101` | 133 | Line-wrap (inline comment) | continuation line on inline comment; wrap after `# V1:` |
| 17 | `swing/web/view_models/dashboard.py:1398` | 101 | Line-wrap | generator expression; pull to local var OR break at `for` |
| 18 | `swing/web/view_models/trades.py:458` | 105 | Line-wrap | ternary expression; format with binary line continuation |

Each site dispositioned as ONE of:
  - **Line-wrap** (default for ALL 18 above): break into 2-3 physical lines without semantic change. Default for E501.
  - **Refactor**: extract to local variable / private helper if the readability gain warrants. Use sparingly; implementer MAY upgrade a "Line-wrap" row to "Refactor" at task time with a 1-line rationale in the commit message body.
  - **`# noqa: E501`**: ONLY with binding rationale documented in the same line (e.g., URL that cannot be wrapped without breaking; SQL literal that must stay on one line for readability). Plan-author default is NONE since no plan-write-time roster row appears to require a noqa exception.

**Codex R5 watch item #5 BINDING:** NO `# noqa: E501` shall be added without per-violation rationale captured in the commit message body. Codex chain verifies this constraint.

**ASCII preservation contract** (per plan §D #10 + §I F4): if the original violating line contains a string literal that flows through `print()` / `click.echo()` / `logger.warning()` (mostly applies to rows #1-3 cli.py + row #10 briefing.py), the line-wrap MUST preserve the line's ASCII-only status. Plan-write-time spot check via `python -c "open('swing/cli.py').readlines()[893]"` confirms cli.py:894 is ASCII; same for the other runtime-path rows. Implementer re-verifies at task time when touching each row.

- [ ] **Step 3: Apply per-site fixes.** Use `Edit` (NOT `Write`) on each site. Verify after EACH file edit that:
  - The semantic of the line is unchanged.
  - String literals that flow through `print()`/`click.echo()`/`logger.warning()` (Windows cp1252 gotcha) remain ASCII-only.
  - F-strings preserve their format placeholders verbatim.

- [ ] **Step 4: Verify ruff baseline drops to 0 E501 + verify no NEW non-E501 classes introduced** (R2 Major #1 — global ruff zero-target is wrong contract; the binding contract is "E501 drops + no new other classes introduced").

```bash
ruff check swing/ --select E501 --statistics 2>&1 | tail -3
ruff check swing/ --statistics 2>&1 | tail -10
```

Expected:
- `--select E501` returns 0 violations. **BINDING.**
- Global `--statistics` returns 0 violations (since the plan-write-time baseline was 18 E501 + 0 non-E501 per `ruff check swing/ --statistics`). **BINDING** as a regression check: any non-zero non-E501 result means the line-wrap accidentally introduced a new class (e.g., UP035 via Python 3.10+ syntax in an unrelated line). If the pre-T-3.6 baseline already had non-zero non-E501 (re-verify at task time), the contract becomes "non-E501 count unchanged from pre-T-3.6 baseline" instead of "0".

- [ ] **Step 5: Run full fast suite — verify ZERO test regression.**

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
```

Expected: same pass count as post-T-3.5 baseline.

- [ ] **Step 6: Commit.**

```bash
git add swing/
git commit -m "style(phase12-5-3-T3.6): clear ruff 18 E501 baseline — 18 line-wrap dispositions; ZERO refactors; ZERO noqa adds; ZERO test regression (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- `ruff check swing/ --select E501` returns 0 violations.
- Full fast suite green at same count as post-T-3.5 baseline.
- ZERO `# noqa: E501` strings added without per-site rationale.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

### Task T-3.4 — V2.1 §VII.F amendment batch (collation doc + inline supersession audit)

**Files:**
- Create: `docs/v2-1-section-7f-amendments-2026-05-18.md` (master inventory; chronological + cross-referenced; ASCII-only).
- ZERO modifications to spec/plan docs in this task (T-3.7 already amended the Phase 12.5 #1 sites; this task INDEXES the amendment).

**Why this is task #4:** Lands AFTER T-3.7 so the §H.4 amendment is part of the inventory at creation time. Lands BEFORE T-3.1/T-3.2/T-3.3 archive-splits so the amendment doc itself is NOT subject to archive-split.

**Format decision (operator-default; Codex may refine):** HYBRID approach:
- **Master inventory doc** at `docs/v2-1-section-7f-amendments-2026-05-18.md` listing every amendment with hash-id + status + source-of-truth doc + line ref + 1-sentence summary.
- **Inline supersession notes** stay at each affected spec/plan doc (T-3.7 already did this for the Phase 12.5 #1 sites; future amendments add inline notes in the same pattern).

This mirrors the "Archive companion" pattern (`docs/phase3e-todo-archive.md` is a companion, not a replacement; same for orchestrator-context-archive).

- [ ] **Step 1: Inventory all pending V2.1 §VII.F amendments from the canonical return-report roster** (per brief §3 Codex watch item #7; Codex R1 Major #4 fix — narrow grep across all docs is too brittle; instead enumerate the exact 33 return-report files + grep inside each).

The canonical return-report roster as of plan-write time (verified via `ls docs/*return-report*.md`; **grouped summary** — 33 files total; individual paths enumerable via the `ls` command at task time):

```
docs/phase9-writing-plans-return-report.md
docs/phase9-bundle-{A,B,C,D,E}-return-report.md          (5 files)
docs/phase10-writing-plans-return-report.md
docs/phase10-bundle-{A,B,C,D,E}-return-report.md         (5 files)
docs/post-phase10-infra-bundle-return-report.md
docs/schwab-bundle-{A,B,C,D}-return-report.md            (4 files)
docs/phase12-bundle-{A,B}-return-report.md               (2 files)
docs/phase12-bundle-C-{A,B,C,D}-return-report.md         (4 files)
docs/post-phase12-schwab-mapper-bundle-{1.5,2}-return-report.md (2 files)
docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-{brainstorm,writing-plans,executing-plans}-return-report.md (3 files)
docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-{brainstorm,writing-plans,executing-plans}-return-report.md (3 files)
docs/phase12-5-finviz-inbox-auto-fetch-fix-return-report.md
docs/3e8-bundle-3-return-report.md
```

Total: **33 return-report files** (re-enumerate at task time via `ls docs/*return-report*.md` to catch any new arrivals between plan-write and task-execution).

**Shell environment** (per CLAUDE.md "Windows + gitbash" section + dispatch environment): Git Bash is the canonical project shell for these commands; PowerShell-equivalent variants are trivial substitutions but NOT required by this plan. The commands below assume Git Bash:

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
ls docs/*return-report*.md | wc -l    # verify count; investigate if drift from 33
for f in docs/*return-report*.md; do
  echo "=== $f ==="
  grep -nE "amendment|VII\.F|V2\.1.*amend|banked.*amend|pending.*amend|deviation.*banked" "$f" || echo "(no amendment hits)"
done > /tmp/amendments-by-file.txt
wc -l /tmp/amendments-by-file.txt
```

Implementer reads `/tmp/amendments-by-file.txt` end-to-end + extracts per-file amendment entries into the master inventory's §1 chronologically.

Also supplement with a global grep ACROSS all docs (not just return-reports) for amendments banked in plan/spec bodies (e.g., recon docs, spec §J/§K/§L sections):

```bash
grep -rn -E "V2\.1.*§?VII\.F amendment|amendment candidates? (banked|pending)" docs/ --include="*.md" | grep -v archive | grep -v return-report | sort -u >> /tmp/amendments-by-file.txt
```

Expected: ~30-40 hits across the 33 return-reports + supplementary plan/spec/recon docs.

If grep-count is wildly off (e.g., <15 OR >60), STOP + reconcile (the grep regex may be missing a banking convention; OR a phase had no amendments banked).

- [ ] **Step 2: Write the master inventory doc.**

Structure:

```markdown
# V2.1 §VII.F Amendment Inventory — 2026-05-18 (Phase 12.5 #3 collation)

This doc indexes all pending V2.1 §VII.F amendments accumulated across Phase 9 / Phase 10 / Phase 11 / Phase 12 / Phase 12.5 return reports + plan docs as of Phase 12.5 #3 ship. Each entry carries an `A-<phase>.<id>` hash for cross-reference + a 1-sentence summary + the source-of-truth doc + the line ref. Inline supersession notes live at each affected spec/plan doc (per T-3.7 precedent).

**V2.1 §VII.F is the source-of-truth methodology-correction protocol** (per `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`). Each amendment routes through this protocol when promoted to a methodology revision. This inventory is the orchestrator's working list; promotion is a separate operator action.

## Table of contents

- §1 Amendments by phase
- §2 Amendments by classification (text-only / cross-reference / wording / contract drift)
- §3 Promotion routing (V2.1 §VII.F protocol entry path)

## §1 Amendments by phase

### Phase 9 (3 amendments banked)
- **A-9.1**: <summary>. Source: <doc path>:<line>. Status: <text-only / cross-ref / etc>.
- ...

### Phase 10 (4 amendments banked)
- ...

### Phase 11 (2 amendments banked)
- ...

### Phase 12 (12 amendments banked)
- ...

### Phase 12.5 (~7 amendments banked + this dispatch's own)
- **A-12.5.H4-banner-clears (NEW; Phase 12.5 #3 T-3.7)**: Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 tier-3-override-banner-clears semantic. Banner clears immediately when override flips parent disc `resolved_by` (NOT "stays present"). Source: amended at <SHA>. Status: text-only; superseded inline.
- **A-12.5.2.A1 (Phase 12.5 #2 R-R §7)**: Plan §C.1 class-name drift in `trades.py` + `schwab.py:558` (4 names mis-labeled; line numbers correct).
- **A-12.5.2.A2 (Phase 12.5 #2 R-R §7)**: Plan §K projection +81 fast tests vs actual +135 (parametrize-granularity overshoot precedent).
- **A-12.5.2.A3 (Phase 12.5 #2 R-R §7)**: Plan §A T-2.2 acceptance count "14 fields" for `ReconcilePreResolutionContext` vs spec §5.2 actual 15.
- ...

## §2 Amendments by classification

| Class | Count | Notes |
|---|---|---|
| Text-only supersession | <N> | inline + indexed |
| Cross-reference drift | <N> | doc-doc mismatch |
| Wording precision | <N> | binding contracts |
| Contract drift | <N> | shipped-vs-stated semantic |

## §3 Promotion routing

When an amendment is promoted to a V2.1 §VII.F methodology revision, follow the protocol at `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F. The orchestrator selects amendments from this inventory + drafts a single revision proposal. Methodology references in `reference/methodology/` are NEVER modified in-place per V2.1 §VII.F protocol.
```

**Codex R5 watch item #3 BINDING:** the inventory MUST be navigable for operator-routing (one amendment per row; explicit hash-id; explicit source-of-truth pointer). Codex chain verifies a sample-amendment can be routed end-to-end.

**Codex R5 watch item #7 BINDING:** if T-3.4 inventory surfaces a NEW amendment NOT already in any prior return report (e.g., a drift cascade discovered DURING this collation), bank it in the inventory + bank it in the plan §M.

- [ ] **Step 3: Verify ZERO duplication** (every amendment appears exactly once in §1; cross-references in §2 are by hash-id only).

```bash
grep -E "^- \*\*A-" docs/v2-1-section-7f-amendments-2026-05-18.md | sort -u | wc -l
grep -E "^- \*\*A-" docs/v2-1-section-7f-amendments-2026-05-18.md | wc -l
```

Expected: both counts match.

- [ ] **Step 4: Commit.**

```bash
git add docs/v2-1-section-7f-amendments-2026-05-18.md
git commit -m "docs(phase12-5-3-T3.4): V2.1 §VII.F amendment inventory — <N> amendments collated chronologically + classified + promotion-routed (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- Inventory doc exists at `docs/v2-1-section-7f-amendments-2026-05-18.md`; em-dashes + `§` glyphs ARE permitted per plan §D #10 (ASCII-only invariant scoped to runtime code paths only; this inventory doc is markdown documentation matching existing project precedent).
- Every amendment listed in any prior return-report-pending-amendments section is indexed exactly once.
- T-3.7's amendment (`A-12.5.H4-banner-clears`) is indexed.
- Phase 12.5 #2's A1+A2+A3 are indexed.
- ZERO modifications to spec/plan docs in this task's diff.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

### Task T-3.1 — CLAUDE.md status-line archive-split

**Files:**
- Modify: `CLAUDE.md` (line 3 status-line PARAGRAPH; 143,843 chars).
- Create OR Append: `docs/CLAUDE.md-archive.md` (new companion if implementer chooses; or append into `docs/orchestrator-context-archive.md` — implementer-decision per brief §4 §A scope).

**Recommended companion:** NEW `docs/CLAUDE.md-archive.md` (format is distinct: paragraph-flow with bold separators, not section-formatted like orchestrator-context-archive). Plan author's default.

**Why this is task #5:** Largest mechanical text move (~143k char paragraph). Order LAST among non-amendment tasks so that any T-3.7 promotion text or T-3.5 disposition is already in the active section when split occurs.

**Boundary selection (DETERMINISTIC per Codex R5 watch item #1):**

> **Move everything dated 2026-05-12 and earlier** (i.e., everything through Phase 9 arc close + Phase 10 arc + Phase 8 polish bundles + Phase 7 + earlier). **Retain in active**: Phase 11 (Schwab arc) entries from 2026-05-13 onward + Phase 12 + Phase 12.5 entries.

Rationale: 2026-05-12 is the natural seam — Phase 9 arc closed that day; Phase 10 writing-plans landed; Phase 11 (Schwab) commissioned 2026-05-13. The active section after the split retains the "current operational arc" (Schwab integration + Phase 12 reconciliation auto-correct + Phase 12.5 polish). Expected active-entry count: ~25-30 (within cap target).

**Codex R5 watch item #1 BINDING — preserve all active references.** Before the split, grep for any incoming cross-references to status-line entries that are about to be archived:

```bash
grep -rn "CLAUDE\.md.*Phase [6-9]\|CLAUDE\.md status-line.*Phase 10" docs/ swing/ tests/ --include="*.md" --include="*.py" | head -20
```

If any active doc references an archive-bound entry by SHA or by name, the cross-reference must be rewritten to point to the archive companion ("see `docs/CLAUDE.md-archive.md` -> Phase 8 entry") OR the entry kept in active. Plan §F documents this pre-flight grep verification.

- [ ] **Step 1: Pre-flight grep verification** for incoming cross-references to about-to-be-archived entries.

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
grep -rn -E "CLAUDE\.md.*(Phase [6-9]|Phase 10|polish-bundle|finviz)" docs/ swing/ tests/ --include="*.md" --include="*.py" 2>&1 | grep -v archive | head -40
```

Capture the count + any concerning matches. If matches reference specific archive-bound SHIPPED entries, address per the disposition below:
- Cross-reference is to a stable shape (e.g., "Phase 7 introduced X feature"): can be kept; archive doesn't break the meaning.
- Cross-reference is to a specific SHA / merge-commit / entry-narrative: rewrite to point at the archive companion explicitly.

- [ ] **Step 2: Extract archive-bound text from `CLAUDE.md` line 3.**

The status-line uses **bold-marker `**Phase N ... SHIPPED YYYY-MM-DD**`** as the entry-start delimiter. Use a small Python script (NOT shell awk; the paragraph is one line + has many special chars) to split the paragraph at each bold marker + emit two paragraphs.

**Implementer note:** create the transient script via the Write tool at the path shown below (the `scripts/` directory exists; the file is git-untracked by gitignore precedent for transient scripts OR by explicit `git add` omission). Delete via `rm scripts/<name>.py` BEFORE the task commit so it never lands in the tree.

```python
# scripts/split_claude_md_status_line.py (transient; created via Write; deleted via `rm` pre-commit)
import re
from pathlib import Path

src = Path("CLAUDE.md")
text = src.read_text(encoding="utf-8")
lines = text.split("\n", 4)  # status-line is line 3 (index 2; 0-based)
assert len(lines) >= 4, "CLAUDE.md must have at least 4 lines"
status_line = lines[2]

# Entry-start markers: **Phase X ... SHIPPED YYYY-MM-DD** OR **[topic] SHIPPED YYYY-MM-DD**
ENTRY = re.compile(r"\*\*([^*]+SHIPPED\s+(\d{4}-\d{2}-\d{2}))")
entries: list[tuple[int, str]] = []  # (start_offset, date_iso)
for m in ENTRY.finditer(status_line):
    entries.append((m.start(), m.group(2)))

# Boundary: 2026-05-12 inclusive -> archive. 2026-05-13+ -> active.
BOUNDARY = "2026-05-12"
archive_entries: list[str] = []
active_entries: list[str] = []
preamble = status_line[:entries[0][0]] if entries else ""
for i, (start, date) in enumerate(entries):
    end = entries[i + 1][0] if i + 1 < len(entries) else len(status_line)
    chunk = status_line[start:end]
    if date <= BOUNDARY:
        archive_entries.append(chunk)
    else:
        active_entries.append(chunk)

print(f"Total entries: {len(entries)}")
print(f"Archive-bound: {len(archive_entries)}")
print(f"Active-retain: {len(active_entries)}")

# Pre-write count gate (R4 Minor #1 LOCK — mirror T-3.2 pre-write pattern):
# If active-retain count exceeds 30 OR drops below 15, STOP + ask operator
# per fallback rule below + plan §F.2. Otherwise proceed.
if not (15 <= len(active_entries) <= 30):
    raise SystemExit(
        f"Active-retain count {len(active_entries)} outside expected [15, 30] range. "
        "STOP + ask operator with 2-3 boundary candidates per plan T-3.1 fallback."
    )

# Write archive companion (one paragraph per entry for readability).
archive_path = Path("docs/CLAUDE.md-archive.md")
archive_path.write_text(
    "# CLAUDE.md status-line archive (Phase 12.5 #3 split; pre-2026-05-13 entries)\n\n"
    "This companion preserves the SHIPPED entries that were moved out of `CLAUDE.md` line 3 "
    "at the Phase 12.5 #3 archive-split (boundary: 2026-05-12 inclusive). The active section "
    "in `CLAUDE.md` retains entries from 2026-05-13 onward (Phase 11 Schwab arc + Phase 12 + "
    "Phase 12.5). Format mirrors the active section's paragraph-flow style.\n\n"
    "---\n\n"
    + "\n\n".join(archive_entries)
    + "\n",
    encoding="utf-8",
)

# Rewrite CLAUDE.md status-line in place (preamble + active entries joined by space).
new_status_line = preamble + " ".join(active_entries)
lines[2] = new_status_line
src.write_text("\n".join(lines), encoding="utf-8")

print(f"CLAUDE.md status-line reduced: {len(status_line)} -> {len(new_status_line)} chars")
```

Run the script:

```bash
python scripts/split_claude_md_status_line.py
```

Expected output:
- Total entries: ~70
- Archive-bound: ~40-50
- Active-retain: ~20-30
- CLAUDE.md status-line reduced: 143,843 -> ~40,000-50,000 chars (target).

If active-retain count exceeds 30 OR drops below 15, **STOP + ask operator** with 2-3 boundary candidates + tradeoffs (per §F.2 escalation rule precedent + R3 Major #2 LOCK). Do NOT auto-shift the boundary; operator-paired decision. Candidate alternatives to surface: (a) push boundary FORWARD to 2026-05-13 inclusive (archives Phase 11 Schwab arc too; active retains Phase 12 + Phase 12.5 only; ~10-15 active entries); (b) push boundary BACKWARD to 2026-05-11 inclusive (archives only through Phase 9 close; active retains Phase 10 + Phase 11 + Phase 12 + Phase 12.5; ~35-45 active entries); (c) custom boundary at a clean phase-arc seam.

**Codex R5 watch item #8 BINDING — format consistency.** The archive companion's format must MATCH the active section's paragraph-flow (NOT section-formatted). Codex verifies by visual diff of the first archive entry against the active section's entry format.

- [ ] **Step 3: Sanity-check character count + entry count.**

```bash
awk 'NR==3 {print length, "chars on active status-line"}' CLAUDE.md
grep -cE "\*\*[^*]+SHIPPED" docs/CLAUDE.md-archive.md
```

Expected: active line ~40-50k chars; archive ~40-50 entry markers.

- [ ] **Step 4: Add a 1-line pointer in `CLAUDE.md` immediately AFTER line 3 (status-line).**

```markdown
*Archive companion (Phase 12.5 #3 split): pre-2026-05-13 SHIPPED entries at [`docs/CLAUDE.md-archive.md`](docs/CLAUDE.md-archive.md).*
```

This is line 4 (or 5 if line 4 was blank); preserves discoverability for future readers.

- [ ] **Step 5: Run grep verification — any cross-reference now stale.**

```bash
grep -rn "CLAUDE\.md.*Phase [6-9]" docs/ --include="*.md" | grep -v archive
```

If hits, validate each: cross-reference still meaningful in active context (allow) OR rewrite to point at archive (rewrite).

- [ ] **Step 6: Run full fast suite — verify ZERO test regression.**

Doc-only edit; suite should be green at same count.

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
```

- [ ] **Step 7: Delete the transient script + commit.**

```bash
rm scripts/split_claude_md_status_line.py
git add CLAUDE.md docs/CLAUDE.md-archive.md
git commit -m "docs(phase12-5-3-T3.1): CLAUDE.md status-line archive-split — boundary 2026-05-12 inclusive; ~40-50 SHIPPED entries moved to docs/CLAUDE.md-archive.md; active retains ~25-30 (post-2026-05-13 Phase 11+12+12.5 arc) (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- `CLAUDE.md` line 3 length reduced to ~40-50k chars (down from 143,843).
- `docs/CLAUDE.md-archive.md` exists; contains ~40-50 SHIPPED entries; format matches active-section paragraph-flow.
- `CLAUDE.md` line 4 (or wherever it naturally lands) contains the archive-companion pointer.
- ZERO test regression.
- ZERO new architectural surface.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

### Task T-3.2 — `docs/phase3e-todo.md` archive-split

**Files:**
- Modify: `docs/phase3e-todo.md` (4014 lines; trim by moving pre-2026-05-13 SHIPPED entries).
- Append: `docs/phase3e-todo-archive.md` (existing 990 lines; append the moved entries while preserving its existing structure).

**Boundary:** Same 2026-05-12 inclusive boundary as T-3.1 — ensures cross-doc consistency.

- [ ] **Step 1: Pre-flight inventory of archive-bound entries.**

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
grep -nE "^### .*SHIPPED.*(2026-0[1-4]|2026-05-0[1-9]|2026-05-1[0-2])" docs/phase3e-todo.md | head -40
```

Capture the line-number range of each archive-bound section. The grep regex matches dates 2026-01-XX through 2026-05-12.

- [ ] **Step 2: Identify the existing structure of `docs/phase3e-todo-archive.md`** (R4 Minor #2 LOCK — chronological-ordering audit).

```bash
head -20 docs/phase3e-todo-archive.md
grep -nE "^# |^## |^### " docs/phase3e-todo-archive.md | head -20
```

Inspect ordering convention. `docs/phase3e-todo.md` active file is **newest-first** (Phase 12.5 #2 SHIPPED at top; Phase 12.5 #1 next; etc.). The script in Step 3 preserves source-file order when extracting sections, so the archive appendix will land newest-first within the appended block. If the existing `docs/phase3e-todo-archive.md` uses a DIFFERENT ordering (e.g., oldest-first), the implementer sorts `archive_bound` to match the archive's convention BEFORE writing the appendix — prose-only instruction (NOT script template); the implementer adds the appropriate `archive_bound.sort(key=...)` line using whichever date-extraction pattern matches the actual section heading format observed in the audit above. Implementer makes this call at task time.

- [ ] **Step 3: Author the move script** (small Python script extracting entries by date-range; same shape as T-3.1 step 2 but for sectioned markdown).

```python
# scripts/split_phase3e_todo.py (transient; created via Edit/Write; deleted post-task)
import re
from pathlib import Path

src = Path("docs/phase3e-todo.md")
archive = Path("docs/phase3e-todo-archive.md")
text = src.read_text(encoding="utf-8")

# Section delimiters are H3 headings "### " followed by a date-bearing title.
sections = re.split(r"(?m)^(?=### )", text)
preamble = sections[0]  # everything before first H3

archive_bound: list[str] = []
active_retain: list[str] = []
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
BOUNDARY = "2026-05-12"

# SHIPPED-only marker: archive ONLY sections whose heading carries an explicit
# SHIPPED marker (case-insensitive). Pre-empts moving unresolved-backlog OR
# operator-pending sections that happen to have an old date in their body.
# Per R3 Major #1 LOCK.
SHIPPED_HEADER = re.compile(r"^### .*\bSHIPPED\b", re.IGNORECASE)

for sec in sections[1:]:
    first_line = sec.split("\n", 1)[0]
    is_shipped_section = bool(SHIPPED_HEADER.match(first_line))
    m = DATE.search(sec[:200])  # check first 200 chars for a date
    if is_shipped_section and m and m.group(1) <= BOUNDARY:
        archive_bound.append(sec)
    else:
        active_retain.append(sec)

print(f"Archive-bound sections (SHIPPED + dated <= {BOUNDARY}): {len(archive_bound)}")
print(f"Active-retain sections (non-SHIPPED OR newer-dated): {len(active_retain)}")

# Pre-write sanity check: implementer reviews archive_bound section headers
# BEFORE writing. If any look operator-pending OR active-backlog, STOP + reconcile.
print("\n=== Archive-bound section headers (review before writing) ===")
for sec in archive_bound:
    print(sec.split("\n", 1)[0])
print("=== END ===\n")

# Implementer-side gate: uncomment the next line to proceed with the write
# after reviewing the archive-bound headers above.
# PROCEED_WITH_WRITE = True
PROCEED_WITH_WRITE = False  # default-OFF; implementer flips after roster review
if not PROCEED_WITH_WRITE:
    raise SystemExit("Set PROCEED_WITH_WRITE=True after reviewing archive-bound roster.")

src.write_text(preamble + "".join(active_retain), encoding="utf-8")

# Append to archive, preserving its existing structure.
existing_archive = archive.read_text(encoding="utf-8")
appendix = (
    "\n\n---\n\n"
    "## Appended Phase 12.5 #3 archive-split (2026-05-18; boundary 2026-05-12 inclusive; SHIPPED-only)\n\n"
    + "".join(archive_bound)
)
archive.write_text(existing_archive + appendix, encoding="utf-8")
```

Run + verify counts.

- [ ] **Step 4: Add an archive pointer at the TOP of `docs/phase3e-todo.md`** (immediately under the H1):

```markdown
> **Archive companion**: SHIPPED entries dated 2026-05-12 and earlier moved to [`docs/phase3e-todo-archive.md`](docs/phase3e-todo-archive.md) at Phase 12.5 #3. Grep both files for full history.
```

- [ ] **Step 5: Verify ZERO test regression + ZERO cross-reference breakage.**

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
grep -rn "phase3e-todo\.md" docs/ swing/ tests/ --include="*.md" --include="*.py" 2>&1 | head -10
```

Cross-references to `phase3e-todo.md` are OK because the pointer at the top makes the archive discoverable.

- [ ] **Step 6: Delete transient script + commit.**

```bash
rm scripts/split_phase3e_todo.py
git add docs/phase3e-todo.md docs/phase3e-todo-archive.md
git commit -m "docs(phase12-5-3-T3.2): phase3e-todo.md archive-split — boundary 2026-05-12 inclusive; ~N sections moved to phase3e-todo-archive.md; pointer added at TOP of active doc (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- `docs/phase3e-todo.md` line-count reduced from 4014 toward 1500-2500 (depending on archive yield).
- `docs/phase3e-todo-archive.md` extended with appendix; total line count grows; existing structure preserved.
- Pointer present at the TOP of `docs/phase3e-todo.md`.
- ZERO test regression.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

### Task T-3.3 — `docs/orchestrator-context.md` archive-split (in-flight narratives + Lessons captured)

**Files:**
- Modify: `docs/orchestrator-context.md` (708 lines; trim Currently-in-flight narratives older than 2026-05-12 + Lessons captured older than 2026-05-12).
- Append: `docs/orchestrator-context-archive.md` (existing 140 lines; append while preserving structure).

**Boundary:** Same 2026-05-12 inclusive boundary.

- [ ] **Step 1: Pre-flight roster extraction + operator review** (R3 Major #3 LOCK — T-3.3 is more deterministic-fragile than T-3.1/T-3.2 because orchestrator-context.md's "Lessons captured" entries are NOT uniformly date-prefixed; some carry inline date markers + some don't; clean date-based extraction is unreliable).

Implementer FIRST builds a deterministic roster of archive-bound items + presents to operator BEFORE any artifact edit:

```bash
cd c:/Users/rwsmy/swing-trading/.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
grep -nE "^##|^###|^####" docs/orchestrator-context.md > /tmp/orch-ctx-headings.txt
wc -l /tmp/orch-ctx-headings.txt
```

Inspect the heading-by-heading structure. For the "Currently in-flight work" section: identify each prior-state-preservation paragraph (typically nested ## entries OR explicit date markers); extract date from each; build a candidate-roster of "paragraphs to archive" (pre-2026-05-13).

For the "Lessons captured" section: if entries are dated, use the same 2026-05-12 boundary. If entries are NOT uniformly dated, build the roster by HEADING-TEXT chronological ordering (oldest first; cap at 20 entries to archive per cap target ~30).

Output a roster summary to operator (max ~30 lines): "Proposed archive-bound roster: <N> Currently-in-flight paragraphs + <M> Lessons captured entries". Operator approves the roster OR redirects (e.g., narrower cut; different boundary). Plan §F.2 escalation rule applies: if structure prevents clean deterministic extraction at task time, STOP + ask operator.

- [ ] **Step 2: Extract pre-2026-05-13 entries from EACH of the two cap-drifting sections** (post operator approval of roster from Step 1).

Use a small transient script (created via Edit/Write; deleted post-task) similar to T-3.2's pattern but operating on the operator-approved roster (NOT on auto-date-detection). Iterate the roster's enumerated headings + move their full section content.

- [ ] **Step 3: Append to `docs/orchestrator-context-archive.md`** preserving its existing structure (small 140-line file; format is well-defined).

- [ ] **Step 4: Add archive pointer at the TOP of the cap-drifting sections** (one pointer per archived section):

```markdown
> **Archive companion**: pre-2026-05-13 entries moved to [`docs/orchestrator-context-archive.md`](docs/orchestrator-context-archive.md) at Phase 12.5 #3.
```

- [ ] **Step 5: Verify ZERO test regression.**

```bash
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5
```

- [ ] **Step 6: Commit.**

```bash
git add docs/orchestrator-context.md docs/orchestrator-context-archive.md
git commit -m "docs(phase12-5-3-T3.3): orchestrator-context.md archive-split — boundary 2026-05-12 inclusive; ~20 lessons + N narrative paragraphs moved; pointers added at section TOPs (no Co-Authored-By footer per project invariant)"
```

**Acceptance:**
- `docs/orchestrator-context.md` line-count reduced toward 400-500 range (depending on yield).
- `docs/orchestrator-context-archive.md` extended with appendix; existing format preserved.
- Pointers present at the TOPs of "Currently in-flight work" + "Lessons captured" sections.
- ZERO test regression.
- `git log --format='%(trailers)' -1 | grep -c 'Co-Authored-By'` returns 0.

---

## §B Cross-bundle pins (none expected; documented negative)

Phase 12.5 #3 is a SINGLE sub-bundle ship. **NO cross-bundle pins** — this dispatch consumes nothing from prior sub-bundles' in-progress code (text-edit + Ruff cleanup + Phase 8 test triage do NOT consume in-progress Phase code surfaces).

T-3.7 amends already-SHIPPED Phase 12.5 #1 plan + spec docs; this is a CONSUMER-side text-edit, not a code pin.

T-3.4 collates already-SHIPPED return reports; this is a CONSUMER-side text-collation, not a code pin.

T-3.5 triages a pre-existing Phase 8 condition; banked since Phase 7 ship; not blocked by any in-progress dispatch.

T-3.6 / T-3.1 / T-3.2 / T-3.3 touch no consumer-side code at all.

---

## §C Task ordering rationale

Recommended order: **T-3.7 -> T-3.5 -> T-3.6 -> T-3.4 -> T-3.1 -> T-3.2 -> T-3.3**.

Justification:
1. **T-3.7 first**: smallest, well-bounded (3 specific text sites verified at plan-write time via grep). Producing the amendment text early lets T-3.4 index it as a banked amendment. ZERO downstream blockers.
2. **T-3.5 second**: investigation might reveal scope-creep; do early to fail-fast at §F escalation if Bucket C surfaces. Buckets A/B fix immediately; Bucket C ships skips + documentation.
3. **T-3.6 third**: mechanical Ruff cleanup; non-intersecting diff with the doc-edits. Easier to verify before the bigger doc-move tasks.
4. **T-3.4 fourth**: amendment-batch collation references T-3.7's output + prior return-report amendments. Lands BEFORE the archive-splits so the inventory doc itself is not archive-eligible.
5. **T-3.1 -> T-3.2 -> T-3.3 last**: archive-splits are the largest mechanical text moves; ship together at the end so any cross-reference to the just-completed earlier tasks (T-3.4 amendment doc, T-3.7 amendment SHAs) is already stable.

Alternative orderings (Codex may refine):
- Reverse: archive-splits FIRST so the active doc set is smaller during T-3.4 collation. Downside: archive-splits consume the most diff churn; risk of conflict cascades is higher.
- T-3.4 LAST: amendment doc accrues amendments from intermediate tasks' findings. Downside: amendment doc is harder to bound (open-ended).

---

## §D Locked decisions roll-up

1. **Brainstorm SKIPPED** (operator-lock §1.1; durable).
2. **Item #5 amend-text-only** (operator-lock §1.2; NO code fix; T-3.7 scope).
3. **Schema v19 UNCHANGED** (operator-lock §1.3; T-3.5 STOP-and-escalate if surfaced).
4. **ZERO Co-Authored-By footer** (operator-lock §1.4; explicit citation in every commit stem).
5. **2026-05-12 inclusive archive boundary** (this plan §A; consistent across T-3.1 + T-3.2 + T-3.3).
6. **HYBRID amendment format** (this plan §A T-3.4; master inventory doc + inline supersession at affected spec/plan docs).
7. **T-3.5 Bucket-A/B/C disposition + cap** (this plan §F; A/B fix directly; **Bucket C: HARD STOP requiring operator approval BEFORE any artifact change**; skip-pattern + phase3e-todo entry is the DEFAULT disposition IF operator approves, NOT pre-authorized).
8. **Per-Ruff-violation rationale** (this plan §A T-3.6 step 2 + Codex R5 watch item #5; NO `# noqa: E501` without binding rationale).
9. **CLAUDE.md archive companion = NEW `docs/CLAUDE.md-archive.md`** (this plan §A T-3.1; format mirror of paragraph-flow active section).
10. **ASCII-only is SCOPED to runtime code paths** (durable project invariant; Windows cp1252 gotcha per CLAUDE.md "Windows PowerShell stdout defaults to cp1252" entry). The invariant applies to strings that flow through `print()` / `click.echo()` / `sys.stdout.write()` / `logger.warning()` — NOT to documentation markdown OR commit messages (project docs including CLAUDE.md status-line itself freely use em-dashes + `§` glyphs per established precedent; git handles UTF-8 in commit messages on Windows). T-3.7 amendment text uses ASCII (`->` not arrow glyph) as a defensive convention but documentation glyphs in plan/spec body text are NOT in-scope of the runtime invariant. T-3.6 Ruff fixes MUST preserve ASCII-vs-non-ASCII status of any string literal touched: if the original was ASCII-only, the line-wrap MUST stay ASCII-only; if the original carried a glyph (rare in runtime paths after Phase 12 C.D cleanup), Codex audits.

---

## §E Test projection

| Task | Test delta | LOC delta (approx) | Notes |
|---|---|---|---|
| T-3.7 | 0 | +3 amendment paragraphs (~+15-30 lines) | doc-only |
| T-3.5 (Bucket A) | 0 | +1-5 lines (fixture fix) | tests pass; runtime same |
| T-3.5 (Bucket B) | 0 | +1-10 lines (runner fix) | tests pass; runtime same |
| T-3.5 (Bucket C, **OPERATOR-APPROVED SKIP-PATTERN**) | 3 fail -> skipped; pass count unchanged | +6 lines `@pytest.mark.skip` + ~20-line phase3e-todo entry | tests skip; no new tests; **expected post-Bucket-C suite: 4847 pass + 0 fail + 8 skipped** (was 4847+3 fail+5 skipped); alternative dispositions per operator decision NOT projected here |
| T-3.6 | 0 | +18-30 lines (line-wraps) | 18 E501 -> 0 E501 |
| T-3.4 | 0 | NEW file ~150-300 lines | inventory doc |
| T-3.1 | 0 | -100k chars from CLAUDE.md + same to new archive file ~150-300 lines visible (paragraphs) | doc-only |
| T-3.2 | 0 | -1500-2500 lines from active todo + same to archive | doc-only |
| T-3.3 | 0 | -200-300 lines from active context + same to archive | doc-only |

**Total test projection** (R5 Major #1 LOCK correction): 4847 pass / 5 skipped (Buckets A/B; baseline preserved post-fix) OR **4847 pass / 8 skipped** (Bucket C operator-approved skip-pattern; 3 currently-failing tests flip from FAIL to SKIP via decorator; ZERO change to pass count). Suite is GREEN (0 failures) in both end-states.

**Total LOC delta** (production code): ~+10-30 LOC max (Bucket A/B Ruff fixes + possible T-3.5 fixture line). Doc moves dominate at ~+5000-10,000 line-deltas across moves but ZERO new active content.

**Ruff baseline target**: 18 E501 -> 0 E501.

**Wall-clock target**: ~81s -> ~81s (no change; some test files smaller after Bucket C skips, but `-n auto` parallelism dominates).

---

## §F Pre-flight verifications + escalation rules + scope-cap notes

### §F.1 Pre-flight verifications (run at the START of each task; document in task commit OR scratchpad)

| Task | Pre-flight grep / command | Expected output |
|---|---|---|
| T-3.7 | `grep -cn "Tier-3 override does NOT" docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` | 1 + 1 = 2 hits across the 2 files |
| T-3.5 | `python -m pytest tests/integration/test_phase8_pipeline_walkthrough.py -xvs 2>&1 | tail -60` | full traceback for Bucket classification |
| T-3.6 | `ruff check swing/ --select E501 --statistics | tail -3` | 18 E501 |
| T-3.4 | `grep -rn "V2.1 §VII.F amendment\|amendment.*banked\|amendment candidates" docs/ | wc -l` | ~30+ hits |
| T-3.1 | `awk 'NR==3 {print length}' CLAUDE.md` | 143843 |
| T-3.2 | `wc -l docs/phase3e-todo.md` | 4014 |
| T-3.3 | `wc -l docs/orchestrator-context.md` | 708 |

If pre-flight output drifts from expected, **STOP + reconcile** before proceeding.

### §F.2 Escalation rules (STOP + escalate to operator)

- **Any task surfaces a need for schema work**: per operator-lock §1.3 + Phase 9 Sub-bundle A precedent + Phase 12.5 #1 plan §F. Schema v19 LOCK preserved.
- **T-3.5 Bucket C (any architectural issue beyond trivial fixture / runner fix)**: HARD STOP — operator approval required BEFORE any artifact change. Implementer escalates with 1-2 paragraph diagnosis summary; operator decides skip-pattern OR alternative disposition (narrower fix, standalone-dispatch carve-out, accept-as-failing pending Phase 13). DO NOT pre-authorize skip-ship from a Bucket C diagnosis alone.
- **T-3.4 amendment collation reveals an amendment that contradicts operator decision OR shipped invariant**: STOP + escalate; do NOT silently bank.
- **T-3.1/T-3.2/T-3.3 archive boundary selection has no clean default**: propose 2-3 candidates with tradeoffs + ask operator at writing-plans-output review.
- **Cross-reference cascade discovered DURING archive-split**: if rewriting one cross-ref reveals another, contained within the same task is OK; if cascade crosses 5+ docs, STOP + bank as separate task within Phase 12.5 #3 OR escalate.

### §F.3 Scope-cap notes

- **T-3.5 cap**: clean diagnose+fix OR clean skip+document. No deeper Phase 8 refactor. Codex R5 watch item #4.
- **T-3.6 cap**: only the 18 E501 dispositioned. Other Ruff violation classes stay banked.
- **T-3.1/T-3.2/T-3.3 cap**: archive-split only; do NOT rewrite active-section content; do NOT introduce new active-section sections.
- **T-3.4 cap**: collation + indexing only; do NOT promote amendments to methodology revisions in this dispatch (V2.1 §VII.F protocol is a separate operator action).
- **T-3.7 cap**: 3 sites only; do NOT amend other Phase 12.5 #1 plan/spec text.
- **NO Phase 13 work** (operator-lock; Phase 13 scope locked at `docs/phase13-scope-brainstorm.md` §0.5).
- **NO `# noqa: E501` without binding rationale** (Codex R5 watch item #5).
- **NO new architectural surface** (operator-lock §1; durable project invariant).

**Operator-pending items explicitly OUT OF SCOPE** (per brief §5 OUT OF SCOPE; operator-paced; NOT orchestrator-blocking; NOT touched by any task in this plan):

- **Worktree husk cleanup**: 7+ worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (3 Phase 12.5 #1 + 1 finviz-fix + 3 Phase 12.5 #2; cumulative cleanup is operator-paced). Phase 12.5 #3 will ADD 1 new husk (this writing-plans worktree) + 1 more (executing-plans worktree) which the operator cleans up post-ship.
- **4 pending-ambiguity discrepancy dispositions**: production has 4 pending-ambiguity discreps (54+55+56+57; DHC+VSAT family from runs #67+#68). Operator dispositions via CLI OR the new web `/reconcile/discrepancy/{id}/resolve` surface (Phase 12.5 #2). Phase 12.5 #3 does NOT touch reconciliation state.
- **Schwab refresh-token clock re-auth**: token clock healthy ~5 days remaining at plan-write time (expires ~2026-05-24T06:40). Routine `/schwab/setup` re-auth is operator-paced. Phase 12.5 #3 does NOT exercise any Schwab API endpoints.
- **CLAUDE.md gotchas section archive-split**: separate concern; banked in brief §5 OUT OF SCOPE. Phase 12.5 #3 T-3.1 archive-splits the STATUS-LINE PARAGRAPH only; the Gotchas section stays in active CLAUDE.md.
- **2 NEW CLAUDE.md gotcha promotion candidates from Sub-bundle 2** (read-time re-redactor discipline; tokens_db_path masking pattern): banked in CLAUDE.md status-line via Phase 12.5 #2 ship; NOT promoted to Gotchas section in this dispatch unless plan author folds into T-3.1 archive-split. Default disposition: stays banked at status-line + carried to archive when T-3.1 splits.
- **Other Ruff violation classes** (non-E501): only the 18 E501 are operator-tagged for cleanup. Other classes (e.g., UP035) stay banked.

---

## §G Per-task acceptance-criteria narrative (binding contracts)

Each task ships green standalone; per-task pytest sweep + ruff sweep at commit time. ZERO regression target on all 4 of {fast test pass count, ruff E501 count post-T-3.6, ruff total count, schema version}.

**T-3.7**: 3 amendment sites carry the "AMENDMENT (Phase 12.5 #3" marker (verified via grep); no code touched. Codex audits that the amendment text accurately describes the shipped `swing/metrics/discrepancies.py:count_recent_multi_leg_auto_corrections` behavior (Codex R5 watch item #6 BINDING).

**T-3.5**: full fast suite green at one of 2 expected counts (4847 pass / 5 skipped if Buckets A/B; **4847 pass / 8 skipped if Bucket C** operator-approved skip-pattern; per R4 Major #1 LOCK — the skip set is the 3 currently-failing tests; test #3 `test_phase8_pipeline_record_event_log_after_run_links_correctly` stays passing). Per-bucket commit message accurately describes disposition. Bucket C skip-pattern adds phase3e-todo entry (POST operator approval).

**T-3.6**: `ruff check swing/ --select E501` returns 0. Full fast suite green. Per-site rationale in commit message OR scratchpad (verified by Codex).

**T-3.4**: master inventory doc exists; ZERO duplication (every amendment indexed exactly once); ZERO modifications to spec/plan docs in T-3.4's diff; T-3.7's amendment + Phase 12.5 #2's A1/A2/A3 included.

**T-3.1**: `CLAUDE.md` line 3 reduced to ~40-50k chars; archive companion at `docs/CLAUDE.md-archive.md` with ~40-50 paragraph-flow entries; archive pointer at line 4-5 of `CLAUDE.md`; ZERO cross-reference breakage.

**T-3.2**: `docs/phase3e-todo.md` line-count toward 1500-2500; `docs/phase3e-todo-archive.md` extended with appendix; archive pointer at TOP of active doc; ZERO cross-reference breakage.

**T-3.3**: `docs/orchestrator-context.md` line-count toward 400-500; `docs/orchestrator-context-archive.md` extended; archive pointers at TOPs of cap-drifting sections; ZERO cross-reference breakage.

---

## §H Operator-witnessed gate plan (4 surfaces)

Smaller scope than Phase 12.5 #1/#2 (which had 6+ surfaces). Phase 12.5 #3 is text-edit + 1 small fix + Ruff cleanup; 4 gate surfaces cover.

### §H.1 S1 — Inline pytest + ruff + per-task post-conditions

- Run: `python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5` from worktree CWD.
- PASS: target count from T-3.5 disposition (4847 pass / 0 fail / 5 skipped if Bucket A/B; **4847 pass / 0 fail / 8 skipped if Bucket C operator-approved skip-pattern** per R4 Major #1 LOCK; alternative count per operator decision if a different Bucket C disposition was approved).
- Run: `ruff check swing/ --select E501 --statistics 2>&1 | tail -3` (BINDING: 0 E501 down from 18).
- Run: `ruff check swing/ --statistics 2>&1 | tail -10` (regression check: non-E501 count unchanged from pre-T-3.6 baseline; if plan-write-time baseline was 0 non-E501, post-T-3.6 should also be 0; else compare against captured pre-T-3.6 snapshot).

### §H.2 S2 — Visual verification of archive-split boundaries

- Inspect: `head -3 docs/CLAUDE.md-archive.md` + `head -5 CLAUDE.md` (verify archive pointer present at line 4-5).
- Inspect: `head -5 docs/phase3e-todo.md` (verify archive pointer at TOP).
- Inspect: `head -10 docs/orchestrator-context.md` (verify section pointers present).
- PASS: each split has an archive pointer; active sections retain expected post-2026-05-13 entries; archives contain expected pre-2026-05-13 entries.

### §H.3 S3 — V2.1 §VII.F amendment doc readability + cross-reference accuracy

- Inspect: `cat docs/v2-1-section-7f-amendments-2026-05-18.md | head -80`.
- Pick: 3 random amendments from §1; verify each entry's `Source: <doc path>:<line>` resolves via `grep -n` to the cited line.
- PASS: 3/3 random samples resolve; ZERO broken cross-references.

### §H.4 S4 — Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment verification

- Inspect: `grep -A 5 "AMENDMENT (Phase 12.5 #3" docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`.
- Inspect: `grep -A 5 "AMENDMENT (Phase 12.5 #3" docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`.
- PASS: 3 amendment blocks present; each accurately describes the shipped helper semantic ("banner clears on tier-3 override").

**SKIPPED gate surfaces** (per polish-bundle-2026-05-10 precedent + Phase 12.5 #2 S6 precedent): NO additional surfaces planned. T-3.6 ruff statistic check folded into S1.

---

## §I Cross-bundle invariants (non-negotiable contracts spanning multiple tasks)

| # | Invariant | Source | Enforcement |
|---|---|---|---|
| F1 | ZERO new schema | operator-lock §1.3 | T-3.5 STOP-and-escalate; T-3.7 doc-only; all other tasks doc-or-style |
| F2 | ZERO Co-Authored-By footer | operator-lock §1.4 + cumulative 163+ commit streak | every commit stem in §A explicitly cites suppression; executing-plans dispatch prompt MUST cite |
| F3 | Ruff post-cleanup target = 0 E501 | T-3.6 acceptance + S1 gate | full suite + ruff check at every task tail |
| F4 | ASCII-only on RUNTIME CODE PATHS (NOT documentation) per §D #10 scope clarification | durable project gotcha (Windows cp1252) | T-3.6 string-literal touched-line ASCII preservation contract; T-3.4 inventory doc + T-3.1 archive doc + T-3.7 amendment text MAY use em-dashes + `§` per documentation precedent (CLAUDE.md status-line itself does so) |
| F5 | Schema v19 UNCHANGED | F1 corollary | `git diff baseline..HEAD -- swing/data/migrations/` empty |
| F6 | 2026-05-12 inclusive archive boundary | §D #5 | T-3.1 + T-3.2 + T-3.3 use the same boundary |
| F7 | HYBRID amendment format | §D #6 | T-3.4 master + inline supersession via T-3.7 precedent |
| F8 | NO Phase 13 work | §F.3 scope-cap | grep verification at S2 |

---

## §J If you get stuck

- If Codex surfaces a NEW schema need (Phase 12.5 #3 should NOT have any), **STOP + escalate** per F1.
- If Codex pushes back on the brainstorm-skip + direct writing-plans posture, HOLD THE LINE — operator-locked 2026-05-18 (§1.1).
- If Codex pushes back on item #5 amend-text-only disposition, HOLD THE LINE — operator-locked 2026-05-18 (§1.2).
- If T-3.5 Phase 8 triage reveals an architectural issue beyond a clean fix-or-document (Bucket C), **STOP + escalate** per F1/§F.2.
- If T-3.4 amendment collation reveals an amendment that contradicts operator decision OR shipped invariant, **STOP + escalate** per §F.2.
- If T-3.1/T-3.2/T-3.3 archive-split boundary selection surfaces no clean default at task time (e.g., 2026-05-12 boundary produces wildly off active-count), propose 2-3 alternative boundaries with tradeoffs + ask operator at task-output review.
- If T-3.6 Ruff cleanup uncovers code paths where line-wrap would change semantic (rare; E501 is whitespace), document + propose `# noqa: E501` with rationale per §F.3 cap.
- If plan-author surfaces a NEW V2.1 §VII.F amendment beyond the items already enumerated, bank in plan §L + T-3.4 inventory.
- DO NOT propose new architectural surfaces within Phase 12.5 #3 plan scope.
- DO NOT add `Co-Authored-By` footer to any commit message (per project invariant; cumulative streak ~163+ commits).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic` for executing-plans dispatch, dispatch a focused reviewer subagent with §1 + §A binding contracts + the 7 scope tasks as anchors; ask for deviation list <=300 words. Cheap; absorbed Major-class findings pre-chain 7x cumulatively.

---

## §K V2 candidates banked

| ID | Candidate | Source | Notes |
|---|---|---|---|
| V-3.5.A | Standalone Phase 8 walkthrough fix dispatch (if Bucket C lands) | T-3.5 disposition | banked at phase3e-todo per §F.3 |
| V-3.4.A | Promote amendment inventory entries to V2.1 §VII.F methodology revision proposal | T-3.4 | operator action; protocol-routed |
| V-3.1.A | CLAUDE.md gotchas section archive-split (separate concern; growing) | brief §5 OUT OF SCOPE note + plan §F | future maintenance pass when section cap drifts |
| V-3.4.B | Convert amendment inventory to machine-parseable YAML/JSON | T-3.4 | useful if orchestrator automation grows |

---

## §L V2.1 §VII.F amendments banked (this dispatch's own; forward-pointer to T-3.4)

| ID | Site | Summary | Status |
|---|---|---|---|
| A-12.5.H4-banner-clears | Plan + spec mirror | Banner clears immediately on tier-3 override (NOT "stays present") | superseded inline at T-3.7; indexed at T-3.4 |
| A-12.5.2.A1 | Phase 12.5 #2 R-R §7 | Plan §C.1 class-name drift in `trades.py` + `schwab.py:558` | indexed at T-3.4 |
| A-12.5.2.A2 | Phase 12.5 #2 R-R §7 | Plan §K projection +81 fast tests vs actual +135 | indexed at T-3.4 |
| A-12.5.2.A3 | Phase 12.5 #2 R-R §7 | Plan §A T-2.2 acceptance count 14 vs spec 15 fields | indexed at T-3.4 |
| A-12.5.3.* | (TBD at T-3.4 task time) | any NEW amendments surfaced during inventory collation | indexed at T-3.4; banked in return report §8 |

T-3.4's inventory doc carries the canonical chronological list across Phase 9 + 10 + 11 + 12 + 12.5.

---

## §M Forward-binding lessons for executing-plans

5 NEW lessons banked at writing-plans for executing-plans inheritance:

- **L-X1**: When a plan/spec amendment is text-only across 3+ sites, sequence the sites left-to-right (smallest first) + commit ALL sites in ONE commit so the V2.1 §VII.F amendment ID resolves to a single SHA. Easier to cite in T-3.4 inventory + easier to audit via grep.

- **L-X2**: Phase 8 walkthrough triage requires Bucket classification BEFORE code changes — surface the bucket disposition in the commit message stem. Bucket A/B commits read like "fix(phase12-5-3-T3.5-bucket-A): ..."; Bucket C commits read like "fix(phase12-5-3-T3.5-bucket-C-skip): ...". Forward-readable from `git log`.

- **L-X3**: Ruff E501 cleanup must use `Edit` (not `Write`) per-site; large-file `Write` rebuilds risk re-introducing whitespace at unrelated lines + churn-explodes the diff. Per-site Edit keeps the diff to ~1-3 lines per violation.

- **L-X4**: Archive-split boundary selection MUST be deterministic AND operator-reproducible. Document the boundary in BOTH the commit message stem AND the archive-companion's heading. A future maintainer reading the archive companion alone must be able to reconstruct WHICH entries went where.

- **L-X5**: V2.1 §VII.F amendment inventory doc is a READ-MOSTLY artifact (operator routes amendments to methodology revisions one-by-one). Optimize for grep-ability: every amendment row carries a `A-<phase>.<id>` hash + a 1-sentence summary + a source-of-truth pointer. NO multi-paragraph entries.

These 5 lessons feed into the executing-plans dispatch prompt's "forward-binding lessons" section.

---

*End of plan. Phase 12.5 #3 project hygiene maintenance pass — 7 tasks T-3.1 to T-3.7; single sub-bundle ship; 4-surface gate; ~+0 to ~+5 LOC production code (Buckets A/B Ruff fixes) + ~+5000-10,000 doc-move line-deltas; schema v19 UNCHANGED; ZERO Co-Authored-By footer; ASCII-only on new text. Executing-plans dispatch UNBLOCKED post operator-paired plan review.*
