# Phase 6 — Post-Trade Review Surface — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` end-to-end. The plan is committed on `main` after 5 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR` in the writing-plans dispatch (commit chain `1be4622..e976d64`); design decisions are locked, task partitioning is fixed, all 14 watch items from the writing-plans brief §6.2 are pre-empted by plan-task mitigations.

**Expected duration:** ~6-9 hours including 2-4 Codex rounds. Plan is 16 tasks (~3450 lines) covering: schema migration `0013` + repo + Trade dataclass + Mistake_Tags vocab + Process Grade computation + cost/violation derivation + Review_Log entity + pipeline cadence pre-create step + CLI `swing trade review` + soft-warn at trade close + web review form + dashboard "needs review" badge + dashboard cadence cards + cadence-completion path (Task 12b — added in writing-plans R1 Critical fix) + final operator-witnessed verification gate (Task 15).

**Dispatch type:** **Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic`** (NOT the `copowers:executing-plans` wrapper). Worktree isolation + global PreToolUse Codex-blocking hook both in effect — see §0 Skill posture for the 7-step workflow. Same pattern as Phase 5 re-dispatch (canonical reference: `docs/phase5-configuration-page-executing-plans-brief.md`).

---

## §0 Read first

Read these in order before executing:

1. **`docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md`** — THE PLAN. Source of truth for task partitioning, per-task acceptance criteria, test specifications, file paths. ~3450 lines; budget 45-60 minutes for thorough read. Do NOT skim — Codex review surfaced 5 rounds of refinement; the per-task TDD specifications encode that refinement and must be followed exactly. Pay particular attention to:
   - **§A audit findings** — 8 empirical-audit corrections including the `last_completed_session` cadence anchor (orchestrator-concurred per writing-plans return triage), `closed_date`-is-derived-not-stored, and `Config` not zero-arg constructible.
   - **§D Mistake_Tags vocabulary** — v1.2 §7.10 verbatim transcription.
   - **§E Process Grade** — v1.2 §9.2 verbatim transcription with parameterized table.
   - **§F mistake_cost_R / lucky_violation_R derivation** — v1.2 §8.8 formulas.
   - **§I watch-item-mitigation table** — every brief §6.2 watch item paired with the plan task that pre-empts it.
   - **Task 6** — `complete_review_atomic` BEGIN IMMEDIATE → trade selection → `compute_stats` → augmentation helpers → UPDATE → COMMIT/ROLLBACK in one function (R1 Major 1 fix; caller cannot supply aggregates).
   - **Task 7** — `_step_review_log_cadence` lands AFTER `lease.step("complete")`; idempotent via UNIQUE INDEX; uses `last_completed_session(now)` not `action_session_for_run`.
   - **Task 12b** — cadence-completion CLI (`swing review complete`) + web (`/reviews/{id}/complete`) + `CadenceCompleteVM` (R1 Critical 1 fix).
   - **Task 15** — operator-witnessed verification gate (6 surfaces, BINDING).

2. **`docs/phase6-post-trade-review-writing-plans-brief.md`** — the brief that drove the plan. Locked decisions (§2), out-of-scope items (§3), binding conventions (§5), 14 adversarial-review watch items (§6.2), 4 pre-designated out-of-scope items (§6.3). The plan IMPLEMENTS this brief; if you find a divergence, the plan is the implementation contract — but surface the divergence in your return report.

3. **`CLAUDE.md`** at repo root — gotchas to pre-empt:
   - HTMX `<tr>`-leading `makeFragment` pathology (review form is `<form>`-rooted; soft-warn-at-close partial is `<div>`-rooted; cadence-cards section is `<section>`-rooted; no `<tr>` leads any HTMX response root per plan).
   - HTMX `HX-Request` header propagation on embedded forms + `HX-Redirect` for HTMX success — both browser-only failure surfaces TestClient cannot detect (Phase 5 R1 Major 1+2 lesson; review form Task 11/12 must include both).
   - HTMX OOB-swap partial drift (use `{% include %}` to share partials).
   - `base.html.j2` 5-VM rule + new-VM existing-field-inheritance audit (Phase 5 lesson) — `ReviewVM`, `ReviewsPendingVM`, `CadenceCompleteVM` each MUST include `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded` with safe defaults.
   - `os.replace` cross-device-link (atomic write tempfile MUST be in dest dir).
   - `pipeline_runs` ORDER BY mask (two-read pattern for "last completed" vs "currently running").
   - Weather-lookup-by-action_session is forward-looking and STALE for backward-looking queries — same lesson family as the cadence anchor §A.8 defection (use `last_completed_session` for backward-looking).
   - Starlette `TemplateResponse(request, "name", {...}, status_code=...)` signature.
   - TestClient lifespan: `with TestClient(app) as client:` for any route test.

4. **`docs/orchestrator-context.md`** — focus on:
   - §"Currently in-flight work" — Phase 6 row will reflect this dispatch's status.
   - §"Binding conventions" — 4-tier commit-message convention; subject-only ERE grep observable verification (`git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`); ruff baseline 98 (current at HEAD `e976d64`); no-amend; no Claude footer; worktree+editable-install verify-command convention.
   - §"Anti-patterns to avoid".
   - §"Lessons captured" — the **Phase 5 cycle** lessons are direct context: extended-window subagent self-collision (motivates worktree); off-spec Codex per-task invocation (motivates marker file); HTMX HX-Request + HX-Redirect (binds Tasks 11/12 design); worktree+editable-install verify-command (binds Task 15 operator-witnessed gate); brief-speculation discipline (already paid down in plan §A audit).

5. **`swing/data/migrations/`** — confirm next migration is `0013_*.sql` (last is `0012_sector_industry.sql`); plan Task 1 ships `0013_phase6_post_trade_review.sql` with all 10 trade columns + `review_log` table + indices in a single file.

6. **`swing/journal/stats.py`** — read in full. Plan re-uses `compute_stats(*, trades, exits, cash_movements=())` for Review_Log aggregates. Plan §A.1 documents the carve-out-driven re-paste of `_share_weighted_r` + `_trade_closed_date_for_review` (4-line byte-identical formulas) into `swing/trades/review.py` because `swing/journal/` is read-only for Phase 6 per writing-plans brief §3.3. DO NOT modify `swing/journal/`.

7. **`swing/evaluation/dates.py`** — both `last_completed_session` (line 21) and `action_session_for_run` (line 43) live here. Plan uses `last_completed_session(now)` for cadence-period bound (orchestrator-concurred §A.8 defection from the writing-plans brief).

8. **`swing/data/models.py:60-92`** — Trade dataclass. Plan Task 2 extends from 17 to 27 columns (10 nullable additions); insert pattern at `swing/data/repos/trades.py:48-91`.

9. **`swing/cli.py:344-499`** — `@trade_group.command("entry"|"exit")` pattern. New `swing trade review` (Task 8) + `swing review complete` (Task 12b) follow the same Click pattern.

10. **`swing/web/routes/trades.py`** + **`swing/web/view_models/trades.py`** + **`swing/web/templates/`** — review form route (Task 11/12) extends `trades.py` route file; `ReviewVM` extends `trades.py` view-model file. Mirror entry-form HTMX patterns.

11. **`swing/pipeline/runner.py:786`** — `_step_export` anchor; `_step_review_log_cadence` (Task 7) lands AFTER it (per plan; cadence-pre-create errors LOG but don't roll back briefing emission).

12. **`swing.config.toml`** — Plan adds new `[review]` section with `review_window_days = 7` (R1 Major 3 fix). Verify the existing TOML structure before plan-mandated additions.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before executing the plan task.

---

## §0 Skill posture (7-step workflow — execute in order)

**Step 1 — Create isolated worktree.** INVOKE `superpowers:using-git-worktrees` to create an isolated worktree on a new branch (suggested: `phase6-post-trade-review`) from base `main` HEAD (currently `e976d64` at brief-draft time; verify before invocation via `git rev-parse main`). All work commits onto the worktree branch. This is REQUIRED per `superpowers:subagent-driven-development` skill docs (line 268-269) AND per orchestrator-context binding-convention 2026-05-02 (worktree isolation is the default for any plan with >5 task commits OR base-layout-VM additions; Phase 6 hits both triggers).

**Step 2 — Activate the Codex-blocking marker.** From within the worktree: `touch .copowers-subagent-active`. This activates the global PreToolUse hook (`~/.claude/hooks/block-copowers-during-subagent.sh`, registered in `~/.claude/settings.json`) which physically blocks any subagent invocation of `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, or `mcp__plugin_copowers_codex__codex-reply` with a clear error message. Hook is harness-level and cannot be bypassed by subagent reasoning.

**Step 3 — Invoke subagent-driven-development DIRECTLY** (NOT via the `copowers:executing-plans` wrapper):

- **INVOKE** `superpowers:subagent-driven-development` and execute Tasks 0-15 per the plan. Subagents will physically be unable to invoke Codex/copowers review while the marker is active.
- **DO NOT INVOKE** `copowers:executing-plans` — it bundles both phases without marker management.
- **DO NOT INVOKE** `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, or `mcp__plugin_copowers_codex__codex-reply` from within subagent dispatches. Hook blocks; explicit prohibition is belt-and-suspenders.
- **DO NOT INVOKE** `superpowers:brainstorming` / `copowers:brainstorming` — design is locked.
- **DO NOT INVOKE** `copowers:writing-plans` — plan is locked at HEAD `e976d64`. If you find a plan task is impossible to implement as written, STOP and surface in the return report; do NOT silently re-plan.

**Step 4 — Remove marker.** After all subagent-driven-development tasks complete + final code reviewer approves: `rm .copowers-subagent-active`. Verify: `ls .copowers-subagent-active` → `No such file`.

**Step 5 — Invoke Codex adversarial review.** INVOKE `copowers:adversarial-critic` directly with:
- `PHASE`: `executing-plans`
- `SPEC_PATH`: `docs/phase6-post-trade-review-writing-plans-brief.md` (the brief that drove the plan; per copowers convention this is the spec)
- `PLAN_PATH`: `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md`
- `BASELINE_SHA`: `e976d64` (or whatever main HEAD is at worktree creation time — review covers all worktree commits since base)

Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`. Internal-Codex pre-emption (commit message qualifier `(internal)` per 4-tier convention) is encouraged; saves orchestrator-Codex round budget per Phase 6/7 lessons.

**Step 6 — Operator-witnessed verification gate** (BINDING; see §7).

**Step 7 — Prepare worktree merge to `main`.** Surface the merge command + worktree cleanup in the return report; the operator executes the merge after final review.

---

## §1 Strategic context (compressed)

Phase 6 ships the post-trade review surface — the cheapest highest-value piece of the journal v1.2 incorporation roadmap (Phases 6-9). Closes the gap that operator-memory + ad-hoc review is the only behavioral discipline measurement today. Touches the post-close path only; no schema disruption to open-trade flow. Phases 7-9 (state machine + Fills first-class + Daily_Management + Risk_Policy + reconciliation depth) are gated on Phase 6 evaluation.

**What ships in this dispatch (per plan):**

- **Schema migration `0013`**: 10 nullable columns on `trades` (`mistake_tags`, `process_grade`, `entry_grade`, `management_grade`, `exit_grade`, `disqualifying_process_violation`, `realized_R_if_plan_followed`, `mistake_cost_confidence`, `lesson_learned`, `reviewed_at`); new `review_log` table (slim 14 always-populated + 7 persisted aggregates frozen-at-completion).
- **`swing/trades/review.py`**: Mistake_Tags constant (v1.2 §7.10 verbatim) + canonicalization + validation; Process Grade computation (v1.2 §9.2 weighted formula + F-floor + disqualifying-D); cost/violation derivation (v1.2 §8.8 max(0,...) formulas); aggregate helpers (`compute_profit_factor`, `compute_max_drawdown_R`) re-pasted from `swing/journal/stats.py` private symbols per §A.1.
- **`swing/data/repos/review_log.py`**: idempotent pre-create + atomic complete-review (single transaction owns BEGIN IMMEDIATE → compute aggregates → UPDATE → COMMIT) + reads.
- **CLI**: `swing trade review <trade_id>` (with `--list` flag); `swing review complete <review_id>` (cadence-completion path, R1 Critical 1 fix).
- **Web**: `/trades/<id>/review` GET form + POST (HX-Redirect on success); `/reviews/{id}/complete` GET form + POST (cadence-completion); `/reviews/pending` list view.
- **Pipeline**: new `_step_review_log_cadence` after `_step_export`; idempotent; uses `last_completed_session(now)`; cadence failures LOG but don't fail the pipeline.
- **Soft-warn at trade close**: shared `SOFT_WARN_REVIEW_DUE_MESSAGE` constant emitted from web `/trades/<id>/exit` POST + CLI `swing trade exit` final-exit path.
- **Dashboard**: "needs review" badge with day-count linking to `/reviews/pending`; daily/weekly/monthly cadence cards (quarterly + circuit_breaker schema-supported but no V1 UI).
- **`cfg.review.review_window_days`**: new config field (default 7; required at config-load via 3-edit cascade per §A.8 — dataclass + top-level + Config(...) constructor).

**Production DB at brief-draft time (HEAD `e976d64`):** VIR (closed; inaugural; no hypothesis attribution) + DHC (open; entry 2026-04-27 @ $7.58 × 39 shares) + CC (open; entry 2026-04-30 @ $26.97 × 5 shares). VIR is the ONLY closed trade — operator-witnessed verification (Task 15) will exercise the review form on VIR.

**Test baseline:** 1472 fast tests passed, 1 skipped, 8 deselected at HEAD `e976d64`. Plan projects ~+30-45 tests across 16 tasks → ~1502-1517 fast tests post-dispatch. Ruff baseline ≤98.

---

## §2 Locked decisions (DO NOT re-litigate)

All design decisions locked in `docs/phase6-post-trade-review-writing-plans-brief.md` §2 + plan §2. The plan implements them as written; do NOT re-design. If you find a locked decision is impossible to implement as written (per plan), STOP and surface in the return report; do NOT silently deviate.

Notable locked decisions (NOT exhaustive — read brief §2 for full list):

- **`mistake_cost_R` / `lucky_violation_R` are DERIVED, not stored.** Brief §2.4 (Q3=A). New trade column is `realized_R_if_plan_followed REAL` (counterfactual; operator-input). The two metrics are computed on read via v1.2 §8.8 formulas. They are NEVER netted (one or both is always 0).
- **Review_Log: slim 14 always-populated + 7 aggregates frozen-at-completion.** Brief §2.5 (Q4=B). 3 compliance ratios (`data_quality_score`, `review_compliance_rate`, `reconciliation_compliance_rate`) DEFERRED to Phase 9.
- **Soft-warn at close + dashboard badge with day-count.** Brief §2.6 (Q5=B). NO hard-block.
- **5 cadence types schema-supported; daily/weekly/monthly UI-wired in V1.** Brief §2.7 (Q6=B). Quarterly + circuit_breaker schema-supported but no V1 UI plumbing.
- **Counterfactual `realized_R_if_plan_followed`: operator-input only in Phase 6.** Brief §2.8 (Q7=A). Phase 7 will add Fills-derived computation as upgrade. Form helper text reminds: "Phase 7 will auto-derive this from Fills."
- **Cadence pre-create via pipeline runner step.** Brief §2.9 (Q9=A). Idempotent; uses `last_completed_session(now)` (NOT `action_session_for_run` — orchestrator-concurred §A.8 defection).
- **Single migration `0013` ships all schema additions.** Brief §2.10 (Q-bonus default).
- **Mistake_Tags taxonomy: v1.2 §7.10 verbatim.** Brief §2.2. Validation is repo-layer (SQLite cannot CHECK-constrain JSON-list contents).
- **Process Grade: v1.2 §9.2 verbatim.** Brief §2.3. Weights 0.40/0.35/0.25; F-floor; disqualifying-D rule. Pure helper function in `swing/trades/review.py`; testable with parameterized inputs.
- **Worktree isolation: REQUIRED.** Per binding convention 2026-05-02 + `subagent-driven-development` skill docs. Plan Task 0 specifies setup.
- **`swing/journal/` is READ-ONLY for Phase 6.** Per writing-plans brief §3.3. Forces re-paste of 4-line private-symbol formulas (per §A.1 audit finding); accepted as scope discipline. DO NOT modify `swing/journal/`.

---

## §3 Scope

### In scope (this dispatch)

Execute the plan task list at `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` from **Task 0 onward**. 16 tasks total (Tasks 0-15, including Task 12b cadence-completion path).

### Out of scope (explicitly NOT this dispatch)

- **Re-litigating any locked decision** in brief §2 / plan §2.
- **Phase 7 territory** — trade lifecycle state machine, Fills first-class table, `pre_trade_locked_at` immutability, thesis/why_now/invalidation/premortem fields, `trade_origin` 4-value enum, Fills-derived `realized_R_if_plan_followed`.
- **Phase 8 territory** — Daily_Management snapshots, MFE/MAE precision via OHLCV.
- **Phase 9 territory** — Risk_Policy entity, Reconciliation_Run + Reconciliation_Discrepancy framework (subsumes the 2026-04-30 TOS reconciliation depth bundle), `data_quality_score` / `review_compliance_rate` / `reconciliation_compliance_rate` Review_Log columns.
- **DROPPED items** — Setup_Playbook DB rows, Screen_Definitions versioning, pyramiding R-views, self-rated quality scoring duplicates of pipeline outputs, drawdown circuit breaker default-on.
- **Modifying `swing/journal/`** — read-only per writing-plans brief §3.3; forces re-paste per §A.1.
- **Editing existing closed-trade outcome fields** (entry_price, exit_price, etc.) via review form — review form is ADDITIVE only.
- **Trade re-review** (overwriting `reviewed_at` and re-completing aggregates) — V1 is single-review per trade.
- **V1 quarterly + circuit_breaker dashboard cards** — schema-supported only; no UI plumbing.
- **Configuration-page surface for `cfg.review.review_window_days`** — default 7 hardcoded; future small dispatch surfaces via Phase 5 config infrastructure.

---

## §4 Binding conventions

- **Worktree isolation:** all work commits within the dispatch's isolated worktree (per §0 Skill posture Step 1). The worktree's branch is the integration branch; merge to `main` at end-of-dispatch via `--no-ff` if there are docs commits ahead of base, else `--ff-only`. DO NOT commit directly to `main` from within this dispatch.
- **Marker-file management for Codex blocking:** `touch .copowers-subagent-active` BEFORE Step 3; `rm` AFTER Step 3 / BEFORE Step 5. Forgetting (a) re-opens the off-spec Codex invocation surface (extended-window subagent collision risk). Forgetting (b) makes the orchestrator-side Codex review fail with the BLOCKED error.
- **Commits:** conventional 4-tier convention per orchestrator-context "Binding conventions":
  - Task implementation: `feat(<area>): Task X — <subject>` (e.g., `feat(trades): Task 4 — compute_process_grade helper`).
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>`.
  - Internal-Codex (within-task): append `(internal)` qualifier (e.g., `fix(trades): Codex R1 (internal) Major 1 — atomic complete-review tx boundary`).
  - Internal code-review fix: `fix(<area>): code-review I<N> — <subject>` (Phase 5 precedent).
  - Format-only cleanup (ruff, comment-only): no task ID prefix needed.
- **Subject-only ERE grep observable verification** before EVERY task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X'
  ```
  Empty output for THIS phase's task ID → safe to proceed. Cross-phase noise is expected (per the 2026-04-30 ERE grep cross-phase-collision lesson) — distinguish fresh-vs-stale by date/SHA. **STOP IMMEDIATELY** and surface in return report if a duplicate appears for the same Task ID within THIS dispatch's commits (extended-window collision — Phase 5 first-attempt was the canonical example; the marker file + worktree are designed to prevent it but do not eliminate the failure class).
- **NO OVERWRITING LANDED-TASK COMMITS:** before starting any task, verify the prior task's commit is present (`git log --grep="Task <prior-id>"` within the worktree branch) AND read the landed file to understand the existing API. If the existing API is wrong per your reading, **STOP** and surface in return report; do NOT silently rewrite.
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task. Plan task text already specifies the failing test FIRST in each task body.
- **Ruff baseline ≤98 warnings** (current at HEAD `e976d64`). New code MUST NOT increase the baseline. `ruff check swing/` after each task to verify.
- **No-amend.** Every commit is a NEW commit. If a Codex round triggers a fix, that fix is its own commit (not an amend of the task commit).
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **TestClient lifespan:** any test exercising route behavior MUST use `with TestClient(app) as client:` (enters app lifespan).
- **Atomic write idiom** (where applicable): `tempfile.NamedTemporaryFile(mode="w", dir=<dest_dir>, delete=False, encoding="utf-8")` + write + `os.replace(tmp.name, dest)`. NEVER `shutil.move`. NEVER tempfile in `$TMP` for cross-volume destinations. (Phase 6 doesn't add new file persistence beyond the migration; included here as standing discipline.)
- **JSON-list canonicalization-at-persistence-boundary** (writing-plans brief §6.2 watch item 2): `mistake_tags` write path canonicalizes (NFC + control-char strip + sorted + dedup). Plan Task 3 specifies; verify execution.
- **Single-transaction snapshot for Review_Log completion** (writing-plans brief §6.2 watch item 3 + plan Task 6): `complete_review_atomic` owns BEGIN IMMEDIATE → trade selection → compute_stats → augmentation → UPDATE → COMMIT/ROLLBACK in one function. Caller cannot supply aggregates.
- **Helper-internal anchoring** (writing-plans brief §6.2 watch item 5 + plan Task 7): `_step_review_log_cadence` uses `last_completed_session(now)` internally; caller cannot supply an as-of-date that controls which prior period rows are created.

---

## §5 Per-task acceptance criteria

Per-task acceptance criteria are specified in the plan itself. Plan task body is the source of truth; this brief does NOT duplicate per-task specs. Honor the plan exactly.

If you find a task acceptance criterion ambiguous OR contradictory with the locked decisions in brief §2: STOP, surface in the return report under "Plan ambiguities surfaced," and do NOT silently re-interpret.

---

## §6 Adversarial review

**Target:** `NO_NEW_CRITICAL_MAJOR` after up to 5 Codex rounds.

**Watch items** (from plan §I + writing-plans brief §6.2 — pre-empt these; Codex will probe them):

1. **Multi-path data ingestion (review-field writes via CLI + web + repo).** Single repo-write path `update_trade_review_fields` consumed by both surfaces; shared `MISTAKE_TAGS` + `validate_mistake_tags` + `canonicalize_mistake_tags` constants. No copy-pasting between CLI and web.
2. **JSON-list canonicalization-at-persistence-boundary.** `mistake_tags` repo writer applies NFC + control-char strip + sorted + dedup. Discriminating tests cover unicode + dup + order variants.
3. **Snapshot-transaction isolation on Review_Log completion.** `complete_review_atomic` BEGIN IMMEDIATE wraps the entire compute-and-freeze sequence. Caller cannot supply pre-computed aggregates. Discriminating test covers concurrent-trade-close-mid-compute scenario.
4. **Operator-facing message-string parity across resolver paths.** `SOFT_WARN_REVIEW_DUE_MESSAGE` shared constant emitted from web close path AND CLI close path; both produce identical operator-visible string.
5. **Helper-internal cadence anchoring** (`last_completed_session(now)` in `_step_review_log_cadence`; NOT `action_session_for_run`; NOT caller-supplied as-of-date). Period-boundary computation is helper-internal.
6. **HTMX HX-Request + HX-Redirect.** `/trades/<id>/review` + `/reviews/{id}/complete` POSTs return `204 + HX-Redirect: <url>` (NOT 303 swap-target). Embedded `<form>` includes `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode. TestClient verifies status code only; operator-witnessed browser verification (Task 15) is BINDING.
7. **HTMX `<tr>`-leading `makeFragment` pathology.** Review form is `<form>`-rooted; soft-warn-at-close partial is `<div>`-rooted; cadence-cards section is `<section>`-rooted; no `<tr>` leads any HTMX response root.
8. **5-VM existing-fields rule on new VMs.** `ReviewVM`, `ReviewsPendingVM`, `CadenceCompleteVM` each carry `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded` with safe defaults.
9. **5-VM rule narrow scope on new fields.** `DashboardVM.needs_review_count` + cadence-card fields are consumer-scoped (rendered in dashboard templates only); `base.html.j2` does not reference them; do NOT blanket-require propagation to other base-layout VMs.
10. **TestClient cannot detect HTMX runtime DOM state.** Operator-witnessed browser verification (Task 15) is BINDING. 6 surfaces enumerated in plan Task 15 Step 2.
11. **Discriminating-test discipline.** Process Grade parameterized table covers F-floor, disqualifying-D, weighted boundaries; cost/lucky never-netted invariant; cadence pre-create idempotence (twice-call); aggregate freezing integration test (compute → close additional trade → re-render → assert frozen).
12. **Cadence-step error handling vs `_step_export` ordering.** `_step_review_log_cadence` lands AFTER `lease.step("complete")`; `run_pipeline_internal` wrapper try/except `log.warning(...)` so cadence failures do NOT roll back briefing emission.
13. **`closed_date` is derived not stored** (plan §A correction). "Needs review" query iterates closed unreviewed trades + computes close-date via existing `_trade_closed_date` semantic (or its re-paste); production volume (1 closed today; <500/year forecast) makes Python-side iteration trivial.
14. **`Config` not zero-arg constructible.** `cfg.review.review_window_days` addition required 3-edit cascade in `swing/config.py:load()` + toml row + direct-Config-construction audit (Task 12b Step 2 enumerates). Verify all 3 edits landed and no test fixture constructs `Config()` without required fields.
15. **No overwriting landed-task work.** Within this dispatch, Codex MUST verify each new commit's diff does NOT touch prior-task files unless the plan explicitly authorizes (e.g., Task 12b modifies Task 7's cadence helpers per plan; otherwise prohibited). A finding here is a Critical-severity stop.

---

## §7 Done criteria

- All 16 plan tasks (Tasks 0-15) executed; all per-task acceptance criteria met.
- `python -m pytest -m "not slow" -q` exits clean. Test count 1472 (current at `e976d64`) → ~1502-1517 (within plan's projection).
- `ruff check swing/` reports baseline-or-better (≤98 warnings).
- All 4-tier commit-message convention checks pass; subject-only ERE grep returns empty (within-phase) before each task implementation commit; **NO commit overwrites prior-task work** (watch item #15).
- Codex adversarial review reaches `NO_NEW_CRITICAL_MAJOR`.
- **OPERATOR-WITNESSED VERIFICATION GATE (BINDING; per plan Task 15):** the implementer MUST run `swing web` locally from inside the worktree using the `$env:PYTHONPATH = "."; python -m swing.cli web` (PowerShell) or `PYTHONPATH=. python -m swing.cli web` (bash) prefix per binding convention 2026-05-02 (worktree+editable-install verify-command). Walk the 6 BINDING surfaces per plan Task 15 Step 2:
  1. Form render: `/trades/{VIR_id}/review` GET shows all fields with helper text.
  2. Soft-warn at close: simulated trade close fires soft-warn message.
  3. Needs-review badge: dashboard shows badge with day-count when a trade is past review window.
  4. Cadence cards: dashboard daily/weekly/monthly cards render with most-recent Review_Log per cadence.
  5. Review submission persists + redirects: POST `/trades/{VIR_id}/review` lands at `/trades` (HX-Redirect verified).
  6. Cadence-completion frozen-aggregates revisit: complete a Review_Log, close another trade, revisit the completed Review_Log → aggregates unchanged.
- Browser verification findings reported in return report under "Operator-witnessed verification" section. Any defect surfaced → fix in a new commit before declaring done.
- **Worktree merge to `main`:** at end-of-dispatch (post-verification gate pass), prepare the worktree branch for merge to `main`. Surface the merge command + worktree cleanup in the return report; the operator executes the merge after final review.

---

## §8 Return report format

Produce as final message:

```
## Return Report — Phase 6 Post-Trade Review Surface Executing-Plans (Worktree)

### Worktree
- Worktree path: <path>
- Branch: <branch-name>
- Base: e976d64 (or actual base SHA at worktree creation)
- Final HEAD on branch: <hash>
- Suggested merge command: git merge --no-ff <branch-name> (operator executes; --no-ff required if docs commits ahead of base)

### Code landed (within worktree)
- Commits (Tasks 0-15): <N>
- Test count: 1472 → <post> (delta: +<N>)
- Ruff: <baseline> warnings (<= 98 baseline preserved)

### Codex review
- Rounds: <N>
- Final verdict: NO_NEW_CRITICAL_MAJOR
- Per-round summary: <C>/<M>/<m>/<advisory> with disposition (FIXED / ACCEPTED-with-rationale)
- Notable accepts: <list>
- Watch item #15 (no overwriting prior-task work): <verified clean / flagged in round X>

### Operator-witnessed verification
- Browser flow executed: <yes/no>
- Verify-command used: $env:PYTHONPATH = "."; python -m swing.cli web (PowerShell)
- Findings: <list any defects + commit hashes that resolved them; if none, "all 6 surfaces pass">
- Specific real-browser checks (per plan Task 15):
  - Form render: <pass/fail>
  - Soft-warn at close: <pass/fail>
  - Needs-review badge: <pass/fail>
  - Cadence cards: <pass/fail>
  - Review submission persists + HX-Redirect: <pass/fail>
  - Cadence-completion frozen-aggregates revisit: <pass/fail>

### Plan deviations (if any)
- <list any plan-task ambiguities surfaced + how resolved; if none, "none">

### Out-of-scope discoveries (if any)
- <list any latent bugs or follow-up items surfaced during execution; do NOT fix in this dispatch — capture for orchestrator triage>

### Operator handoff
- Next move: operator executes worktree merge to main + post-execution housekeeping (orchestrator-context status update, phase3e-todo SHIPPED marker, lessons capture if any)
- Phase 7 (state machine + Fills first-class) is GATED on Phase 6 evaluation per orchestrator-context; operator decides whether to proceed.
```

---

## §9 If you get stuck

- **If `superpowers:using-git-worktrees` invocation fails** (Windows ACL state, disk space, branch name collision): STOP. Surface in the return report. Do NOT proceed without worktree isolation — `superpowers:subagent-driven-development` documents worktrees as REQUIRED.
- **If a tool invocation returns `BLOCKED: Skill(copowers:...)` or `BLOCKED: mcp__plugin_copowers_codex__...`**: that's the global PreToolUse hook firing as designed. The marker file `.copowers-subagent-active` is present. If you are a subagent: do not retry; the per-task Codex review surface is intentionally closed. If you are the orchestrator and all subagent tasks are complete: `rm .copowers-subagent-active` then re-invoke. If you are the orchestrator and tasks are NOT complete: do NOT remove the marker; you should not be invoking Codex yet.
- **If a plan task is impossible to implement as written** (e.g., signature surprise in `compute_stats`, undocumented constraint in repo): STOP. Surface in the return report under "Plan ambiguities surfaced." Do NOT silently re-design or re-scope.
- **If `swing/journal/` modification appears necessary** (e.g., `_trade_r` private-symbol formula needs a fix that affects Phase 6 derivation): STOP. Surface in return report. The carve-out is read-only per writing-plans brief §3.3; modifying `swing/journal/` requires explicit operator re-authorization.
- **If `swing web` from inside the worktree returns 404 on `/trades/<id>/review`**: editable-install resolver is pointing at main, not the worktree (per binding convention 2026-05-02 worktree+editable-install verify-command). Use `$env:PYTHONPATH = "."; python -m swing.cli web` (PowerShell) or `PYTHONPATH=. python -m swing.cli web` (bash) from inside the worktree dir.
- **If Codex flags a CLAUDE.md gotcha not pre-empted by the plan**: it's a real finding; FIX or ACCEPT-with-rationale per standard cycle.
- **If you find an additional latent bug** unrelated to Phase 6 scope: capture in return report under "Out-of-scope discoveries"; do NOT fix in this dispatch.
- **If the operator-witnessed verification surfaces a defect**: fix in a new commit (not an amend); update the verification report; do NOT declare done until the operator confirms the fix.
- **If a within-phase task-ID duplicate commit appears** (the Phase 5 first-attempt rogue-commit shape): STOP IMMEDIATELY. Do NOT push the worktree. Surface in return report; the operator decides whether to revert + continue or re-dispatch.
- **If the cadence-step `_step_review_log_cadence` produces unexpected behavior on weekend/holiday boundaries** (Sunday-evening pipeline run, etc.): consult `swing/evaluation/dates.py` for the canonical session-boundary helpers; verify `last_completed_session(now)` is invoked, not `action_session_for_run`. The `_NYSE.previous_session(action_session_for_run(now)) == last_completed_session(now)` invariant on normal trading days does NOT hold uniformly across all calendar edges.
- **If `complete_review_atomic` integration test is hard to set up** (concurrent-write simulation): the discriminating test can use a controlled second-thread + barrier OR a monkeypatched mid-compute hook that triggers a sibling write. Do NOT skip the discriminating test — it's the snapshot-transaction-isolation watch item.

---

**End of brief.**
