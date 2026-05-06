# Phase 6 — Post-Trade Review Surface — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author the Phase 6 implementation plan from the locked spec below; wrap with `copowers:writing-plans` for adversarial Codex review of the plan; iterate to `NO_NEW_CRITICAL_MAJOR`. Brainstorm is **skipped** — operator + orchestrator have locked the spec in-thread; the plan author's job is to convert spec → plan, not to re-design.

**Expected duration:** ~3-5 hours including 4-5 Codex rounds (Phase 6's bug-surface complexity is moderate — schema additions + new entity + new computed values + new web surface + new pipeline step; lessons predict ≥4 rounds).

**Dispatch type:** `copowers:writing-plans` wrapper (writing-plans is single-pass; marker-file workflow is NOT needed — that's executing-plans-only).

---

## §0 Read first

Required (in order):

1. **[CLAUDE.md](../CLAUDE.md)** (root, 91 lines) — project conventions, gotchas. The 5-VM rule, HTMX `<tr>`-leading `makeFragment` pathology, HTMX HX-Request + HX-Redirect, `os.replace` cross-device, weather-lookup-by-action_session, OHLCV fetch scope, `pipeline_runs` ORDER BY mask, OOB-swap partial drift — all directly relevant to this Phase. Re-skim every gotcha before drafting plan tasks.
2. **[docs/orchestrator-context.md](orchestrator-context.md)** — durable orchestrator framing. Read §"Currently in-flight work" + §"Recent decisions and framings" + §"Binding conventions" + §"Lessons captured" entries dated 2026-04-29 onward (pyramiding + new-VM existing-field inheritance + brief-speculation discipline + HTMX HX-Request/HX-Redirect + worktree+editable-install verify-command).
3. **[docs/phase3e-todo.md:946-1056](phase3e-todo.md#L946-L1056)** — the 2026-05-01 Journal v1.2 incorporation section. Phase 6 scope is at lines 962-980; cross-cutting framing at 952-961; sequencing alternatives at 1035-1042; modification rationale at 1044-1056.
4. **[reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md](../reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md)** §7.10 (Mistake_Tags taxonomy, line 1021), §7.11 (Review_Log entity, line 1071), §8.8 (mistake_cost / lucky_violation formulas, line 1211), §9.2 (Process Grade computation, line 1299), §10.4 (Post-Trade Review workflow, line 1447). These five sections are the canonical source-of-truth for Phase 6 logic.
5. **Empirical audit (do this BEFORE drafting plan):**
   - `grep -rn "<field_name>" swing/ tests/ swing.config.toml` for each of the 10 trade fields + Review_Log table name; confirm none exist (orchestrator pre-checked 2026-05-02; verify still true at dispatch time).
   - Read [swing/data/models.py:61](../swing/data/models.py#L61) (`Trade` dataclass — single source of truth for the 10 nullable additions).
   - Read [swing/journal/stats.py](../swing/journal/stats.py) full file — `compute_stats`, `JournalStats`, `period_filter`, `_trade_r`, `_trade_pnl`, `_trade_closed_date` are the building blocks for Review_Log auto-aggregates per locked decision Q4(B).
   - Read [swing/cli.py:344-499](../swing/cli.py#L344-L499) — `@trade_group.command` pattern (`entry`, `exit`); the new `swing trade review` command slots in here.
   - Read [swing/pipeline/runner.py](../swing/pipeline/runner.py) — `run_pipeline_internal` orchestration + `_step_evaluate`/`_step_watchlist`/`_step_recommendations`/`_step_charts`/`_step_export` step pattern. New `_step_review_log_cadence` is added near `_step_export` (idempotent pre-create runs once per cycle).
   - Read [swing/web/routes/trades.py](../swing/web/routes/trades.py) (entry/exit routes) and [swing/web/view_models/trades.py](../swing/web/view_models/trades.py) — the `/trades/<id>/review` route + `ReviewVM` extend the existing trade-related modules; mirror the entry-form HTMX patterns.
   - Read [swing/evaluation/dates.py:43](../swing/evaluation/dates.py#L43) — `action_session_for_run`. Cadence-boundary computation MUST use this, not `date.today()` (HST-vs-ET mismatch + partial-bar gotcha).
   - List `swing/data/migrations/` — confirm next migration is `0013_*.sql` (last is `0012_sector_industry.sql`).

Reference (read-as-needed, not required upfront):

- [docs/phase5-configuration-page-writing-plans-brief.md](phase5-configuration-page-writing-plans-brief.md) — most-recent writing-plans brief precedent; structure + binding conventions to mirror.
- [docs/superpowers/plans/2026-05-01-configuration-page-plan.md](superpowers/plans/2026-05-01-configuration-page-plan.md) — Phase 5 plan; reference for plan structure/depth.
- [docs/cycle-checklist.md](cycle-checklist.md) — operator's actual daily/weekly/monthly cadence (informs cadence-period boundary semantics).

---

## §0 Skill posture

**Invoke:** `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex review on the plan). Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`.

**Do NOT invoke:** `copowers:brainstorming` (brainstorm-skip per operator). Do NOT invoke `superpowers:brainstorming` either; the spec is locked in §2 below.

**Worktree isolation:** NOT required for writing-plans (no code commits — only the plan document). The plan you author MUST specify worktree isolation for the executing-plans dispatch (Phase 6 hits both triggers per orchestrator-context binding-convention 2026-05-02: >5 task commits expected AND base-layout-VM addition).

**Expectations from the wrapper:**

- The wrapper invokes `superpowers:writing-plans`, which produces an implementation plan from the spec in this brief.
- The wrapper then invokes `copowers:adversarial-critic` on the plan; you fix findings; iterate.
- 4-5 Codex rounds expected (Phase 6 has new schema + new entity + new computed values + new web surface + new pipeline step; bug-surface dense per the Phase 7 implementer-side lesson "5-round Codex loop shows compound ROI even on small (<500-line) test-only diffs").

---

## §1 Strategic context (compressed)

**Why Phase 6 is the next operational item.** Phase 5 (configuration page) shipped 2026-05-02 at `3a4195c`. Operator-commissioned external research at `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` (1953 lines) was decomposed into Phases 6-9 per `docs/phase3e-todo.md` 2026-05-01 entry. Phase 6 is the **cheapest highest-value piece** — closes the gap that operator-memory + ad-hoc review is the only behavioral discipline measurement today; touches the post-close path only; no schema disruption to open-trade flow.

**What Phase 6 is NOT.** Phase 6 is post-trade only. It does NOT touch:
- Trade lifecycle state machine (Phase 7 — `planned → triggered → entered → managing → partial_exited → closed → reviewed → canceled`)
- Fills first-class table (Phase 7 — replaces dual-source entry+exits pattern)
- `pre_trade_locked_at` immutability + thesis/why_now/invalidation/premortem fields (Phase 7)
- Daily_Management snapshots / MFE/MAE precision via OHLCV (Phase 8)
- Risk_Policy entity + Reconciliation_Run framework (Phase 9; subsumes the queued TOS-reconciliation-depth bundle)

**Production DB at brief-draft time (2026-05-02 at HEAD `b2d0b5c`):** VIR (closed; inaugural; no hypothesis attribution) + DHC (open; entry 2026-04-27 @ $7.58 × 39 shares; sub-A+ VCP-not-formed prefix) + CC (open; entry 2026-04-30 @ $26.97 × 5 shares; sub-A+ VCP-not-formed prefix). VIR is the ONLY closed trade in the production DB; Phase 6 will activate review on it, then carry forward as DHC + CC (and future trades) close.

**Operator constraints (from `project_capital_risk_floor.md` memory):** $7,500 risk floor convention; ~$1,300 actual balance; single operator; ~4-8 hrs/week sustained. Single-operator scope means lost-update races and multi-tab coordination are not concerns; soft-warn discipline is sufficient (per V2.1 minimum-viable-governance).

---

## §2 Locked design decisions (do NOT re-litigate)

These are operator + orchestrator locked in-thread 2026-05-02; the plan implements them as-specified. The adversarial-Codex review can find implementation defects, contract bugs, etc., but should NOT propose alternatives to these decisions.

### §2.1 Cross-cutting (from phase3e-todo.md:953-961)

- **DROP** self-rated framework quality scoring (pipeline asserts via bucket + criteria tags + hypothesis_label).
- **DROP** Setup_Playbook DB entity (setups encoded in `swing/evaluation/scoring.py` + `criteria.py`; git-versioned).
- **DROP** Screen_Definitions versioning (`finviz_schema.py` git-versioned).
- **DROP** pyramiding R-views (operator at $7,500 capital, 5 concurrent, no pyramiding plan).
- **DROP** `trade_origin` enum work (Phase 7 territory).
- **DEFER** thesis / why_now / invalidation_condition / premortem fields (Phase 7).
- **ALIGN** drawdown circuit breaker with v1.2 default (opt-in disabled).

### §2.2 Mistake_Tags taxonomy

Adopt **v1.2 §7.10 verbatim**: 6 categories (entry / risk / management / psychology / reconciliation / none), ~35 specific tags as enumerated. Stored as Python constant in `swing/trades/review.py` (or a new `swing/trades/mistakes.py` — plan author chooses); repo writer validates each tag against the constant before INSERT. SQLite cannot CHECK-constrain a JSON-list of strings; validation is repo-layer enforcement (see §6 watch-item: "JSON-list grouping-key requires canonicalization-at-persistence-boundary").

### §2.3 Process Grade computation

Adopt **v1.2 §9.2 verbatim**:
- Stage grade numeric map: A=4, B=3, C=2, D=1, F=0.
- Weights: entry 0.40, management 0.35, exit 0.25.
- Floor rules: any stage = F → process_grade = F. `disqualifying_process_violation = true` → process_grade = max D.
- Numeric → grade: A ≥ 3.50, B 2.75-3.49, C 2.00-2.74, D 1.00-1.99, F < 1.00.
- Disqualifying-process-violations list (v1.2 §9.2): `no_stop`, `oversized_beyond_policy`, `no_valid_setup`, `revenge_trade`, `circuit_breaker_override`, `held_after_invalidation_without_rule_basis`, `moved_stop_away_materially_increasing_risk`. Stored as Python constant; the `disqualifying_process_violation` boolean column on `trades` is the operator's manual flagging; the constant list is REFERENCE for the operator (rendered on the review form for guidance), not an auto-derivation.

Implemented as pure helper `compute_process_grade(*, entry, management, exit_, disqualifying)` in `swing/trades/review.py` (testable with parameterized inputs).

### §2.4 mistake_cost_R / lucky_violation_R storage shape

Per locked decision **Q3(A)** — store the COUNTERFACTUAL only:

- New trade column: `realized_R_if_plan_followed REAL` (nullable; operator-input via review form).
- `mistake_cost_R` and `lucky_violation_R` are DERIVED on read via the v1.2 §8.8 formulas:
  - `mistake_cost_R = max(0, realized_R_if_plan_followed - actual_realized_R_effective)`
  - `lucky_violation_R = max(0, actual_realized_R_effective - realized_R_if_plan_followed)`
- `actual_realized_R_effective` is computed from existing entry + exits + initial_stop infrastructure (mirror `swing/journal/stats.py:_trade_r`).
- They are NEVER netted (per v1.2 §8.8).
- Phase 7 will add Fills-derived `realized_R_if_plan_followed` computation as an upgrade; Phase 6 ships operator-input only.

Rationale: single source of truth; matches v1.2 formula exactly; counterfactual is genuinely operator-judgment (e.g., "would I have held to the stop?" requires re-imagining the trade).

### §2.5 Review_Log field set

Per locked decision **Q4(B)** — slim 14 + persist computed aggregates frozen-at-review:

**Slim 14 (always populated):**
- `review_id INTEGER PRIMARY KEY`
- `review_type TEXT NOT NULL` (CHECK in `('daily','weekly','monthly','quarterly','circuit_breaker')`)
- `period_start TEXT NOT NULL` (ISO date)
- `period_end TEXT NOT NULL` (ISO date)
- `scheduled_date TEXT NOT NULL` (ISO date)
- `completed_date TEXT` (nullable; ISO date)
- `skipped INTEGER NOT NULL DEFAULT 0` (boolean)
- `duration_minutes INTEGER` (nullable; required-if-completed at repo-layer enforcement)
- `n_trades_reviewed INTEGER NOT NULL DEFAULT 0`
- `total_mistake_cost_R REAL NOT NULL DEFAULT 0` (computed-at-review-completion from member trades' `realized_R_if_plan_followed` + actual_realized_R_effective)
- `total_lucky_violation_R REAL NOT NULL DEFAULT 0` (same)
- `primary_lesson TEXT` (nullable; required-if-completed at repo-layer enforcement)
- `next_period_focus TEXT` (nullable; required-if-completed at repo-layer enforcement)
- `created_at TEXT NOT NULL DEFAULT (datetime('now'))` (audit anchor)

**Persisted aggregates (computed at review completion, frozen on the row):**
- `net_R_effective REAL`
- `expectancy_R_effective REAL`
- `win_rate REAL` (0.0-1.0)
- `avg_win_R REAL`
- `avg_loss_R REAL` (natively negative)
- `profit_factor REAL`
- `max_drawdown_R REAL`

Aggregates computed via `swing/journal/stats.py:compute_stats` infrastructure; persisted on the Review_Log row at the moment of review completion (frozen-at-review). Subsequent trade re-review or DB edits do NOT mutate prior aggregates — pre-registration discipline analog.

**Dropped (Phase 9 territory):** `data_quality_score`, `review_compliance_rate`, `reconciliation_compliance_rate`. The first two require infrastructure that doesn't exist yet (data quality scoring); the third requires Reconciliation_Run (Phase 9).

### §2.6 Required-at-close discipline

Per locked decision **Q5(B)** — soft-warn at close + persistent dashboard "needs review" badge with day-count. NO hard-block.

Implementation:
- At trade close (web `/trades/<id>/exit` POST or CLI `swing trade exit`), if the final exit closes the trade, the response surfaces a soft-warn message: "Review due within 7 days. [Review now] / [Dismiss]". Soft-warn pattern mirrors entry_post soft-warn confirm.
- Dashboard "needs review" badge: query trades where `closed_date IS NOT NULL AND reviewed_at IS NULL AND DATE(closed_date) <= DATE('now', '-7 days')` → render badge with count + link to a list view.
- The 7-day window is a **configurable** value at `cfg.review.review_window_days` (default 7); per Phase 5's configuration-page infrastructure, surface this field as a tunable in V2 of the config page (Phase 6 doesn't add it to the V1 config UI; just defines the default in `swing.config.py`).

### §2.7 Cadence types in V1

Per locked decision **Q6(B)** — daily/weekly/monthly UI surfaces; quarterly + circuit_breaker schema-supported but no UI plumbing.

- Schema CHECK constraint on `review_type` accepts all 5 values (daily/weekly/monthly/quarterly/circuit_breaker).
- Pipeline-runner pre-create step (per §2.9) creates rows for daily/weekly/monthly only in V1.
- Dashboard cadence cards render daily/weekly/monthly; quarterly + circuit_breaker rows can exist in DB but no V1 UI.
- Period-boundary semantics (plan author MUST specify exact algorithm in plan tasks):
  - **daily**: `period_start = period_end = previous trading session date` (use `action_session_for_run` to find the most recent completed session; create the daily Review_Log for that session if not present).
  - **weekly**: previous Monday-Friday week (operator's actual workflow per `cycle-checklist.md`); `period_start = Monday of prior trading week`, `period_end = Friday of prior trading week`. Holidays do NOT shift the week boundary.
  - **monthly**: previous calendar month; `period_start = first day of prior month`, `period_end = last day of prior month`.
  - **quarterly**: schema-supported; not UI-wired in V1.
  - **circuit_breaker**: schema-supported; created on-demand by operator action (V1 has no UI for this; row creation is via direct repo function call).

### §2.8 Counterfactual derivation

Per locked decision **Q7(A)** — operator-input only in Phase 6; Phase 7 adds Fills-derived computation as upgrade.

The `realized_R_if_plan_followed` field is operator-supplied via the review form. Plan author should NOT scope any auto-derivation of this value (no use of planned_target, planned_stop, etc.) — that's Phase 7 territory. The form's helper text should remind the operator: "What R would you have realized if you'd followed your original plan exactly? (Phase 7 will auto-derive this from Fills.)"

### §2.9 Review_Log auto-creation cadence

Per locked decision **Q9(A)** — pre-create rows on cadence boundary via pipeline-runner step. Compliance natively observable.

- New step `_step_review_log_cadence` in `swing/pipeline/runner.py`, ordered AFTER `_step_export` (last-step pattern; doesn't block the pipeline's primary value chain).
- Idempotent: each pipeline run, for each of {daily, weekly, monthly} cadence types, compute the prior period's `(period_start, period_end)` per §2.7. If no Review_Log row exists for `(review_type, period_start, period_end)`, INSERT with `scheduled_date = period_end + 1 day`, `completed_date = NULL`, `skipped = false`. Pre-existing rows untouched.
- Anchor for "now" is `action_session_for_run(datetime.now())` per CLAUDE.md gotcha (HST-vs-ET + partial-bar lessons).
- Compliance is observable: `count(completed_date IS NOT NULL) / count(*) = review_compliance_rate` (deferred to Phase 9 wiring per §2.5).

### §2.10 Dispatch boundary + plan structure

Per locked decision **Q-bonus default**: single migration `0013_phase6_post_trade_review.sql` ships ALL trade-row additions + Review_Log table + indices in one file (single-dispatch executing-side default).

Plan structure: tasks ordered top-to-bottom such that Tasks 1-N (schema + repo + Trade dataclass + Mistake_Tags vocab + Process Grade helper + CLI `swing trade review`) form a coherent first slice (Dispatch A if split); Tasks (N+1)-M (web form + ReviewVM + templates + dashboard "needs review" badge + dashboard cadence cards) form the second slice (Dispatch B); pipeline-runner cadence-pre-create step lands wherever natural (likely first slice, since it's tested via repo + needs no web surface).

The executing-side may choose to split at the natural seam OR ship as a single dispatch; the plan should be structured to allow either. Default executing-side recommendation: **single dispatch** (worktree-isolated per binding convention).

---

## §3 Scope

### §3.1 In-scope

- **Schema migration `0013_phase6_post_trade_review.sql`** — 10 nullable columns on `trades` + new `review_log` table per §2.4 + §2.5.
- **Repo layer** — `swing/data/repos/trades.py` extension for new fields (write + read); new `swing/data/repos/review_log.py` for Review_Log CRUD + idempotent pre-create + completion path.
- **Trade dataclass** — extend [swing/data/models.py:61](../swing/data/models.py#L61) with 10 nullable fields (annotations match column types per §2.4).
- **Mistake_Tags vocabulary** — Python constant `MISTAKE_TAGS` in `swing/trades/review.py` (or `swing/trades/mistakes.py`); per-category dict; `validate_mistake_tags(tags: list[str]) -> None` raising ValueError on unknown tags.
- **Process Grade helper** — pure function `compute_process_grade(...)` per §2.3 in `swing/trades/review.py`.
- **`mistake_cost_R` / `lucky_violation_R` derivation helpers** — pure functions in `swing/trades/review.py` per §2.4 formulas.
- **CLI command** — `swing trade review <trade_id>` (interactive form OR flag-based per plan author's choice; mirror existing `entry`/`exit` patterns; add `--mistake-tags`, `--process-grade-entry`, `--process-grade-management`, `--process-grade-exit`, `--disqualifying-process-violation`, `--realized-r-if-plan-followed`, `--mistake-cost-confidence`, `--lesson-learned` flags). `swing trade review --list` shows trades needing review (closed_date NOT NULL AND reviewed_at IS NULL).
- **Web review form** — new route `/trades/<id>/review` (GET form + POST submission) in `swing/web/routes/trades.py` (extend existing module; do NOT create `review.py` route file unless plan author justifies the separation).
- **ReviewVM** — new view-model in `swing/web/view_models/trades.py` (extend existing module). MUST inherit ALL existing fields `base.html.j2` dereferences (per Phase 5 lesson: `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`).
- **Templates** — new `review.html.j2` template (full page extending `base.html.j2`) + partials for hard-refuse / soft-warn / success cases per established HTMX patterns.
- **Dashboard "needs review" badge** — extend `DashboardVM` with `needs_review_count` field; render badge linking to `/trades?filter=needs_review` OR a new `/reviews/pending` list view (plan author chooses; default to link to filtered `/trades` listing).
- **Dashboard cadence cards** — extend `DashboardVM` with daily/weekly/monthly cadence-card data (most-recent Review_Log per cadence + scheduled-but-not-completed indicator); render card per cadence type.
- **Pipeline-runner cadence pre-create step** — new `_step_review_log_cadence` in `swing/pipeline/runner.py` per §2.9.
- **Soft-warn at trade close** — modify trade-close paths (web `/trades/<id>/exit` POST + CLI `swing trade exit`) to surface "Review due within 7 days" message when the final exit closes the trade. Mirror entry_post soft-warn pattern.
- **TDD tests at every layer** — schema migration round-trip; repo write/read; dataclass field defaults; Mistake_Tags validation (positive + negative cases); Process Grade computation (parameterized table covering F-floor, disqualifying-D, weighted-numeric edges); cost / violation derivation (parameterized table); CLI command (click test runner); web form GET + POST (TestClient); ReviewVM build; dashboard badge + cadence-card rendering; pipeline-runner step idempotence; soft-warn trigger.
- **Fast-suite baseline preservation** — current 1472 fast tests at HEAD `b2d0b5c` must remain green.
- **Ruff baseline preservation** — 98 errors current; do not introduce new violations.

### §3.2 Out of scope (defer to later phases or DROPPED)

- Trade lifecycle state machine (Phase 7).
- Fills first-class table (Phase 7).
- `pre_trade_locked_at` immutability + thesis/why_now/invalidation/premortem fields (Phase 7).
- `trade_origin` 4-value enum (Phase 7).
- Daily_Management / MFE-MAE per-day snapshots (Phase 8).
- Risk_Policy entity (Phase 9).
- Reconciliation_Run + Reconciliation_Discrepancy framework (Phase 9; subsumes the 2026-04-30 TOS reconciliation depth bundle).
- Setup_Playbook as DB rows (DROPPED per cross-cutting framing).
- Screen_Definitions versioning (DROPPED).
- Pyramiding R-views (DROPPED).
- Self-rated quality scoring duplicates of pipeline outputs (DROPPED; emotional_state + confidence_score are operator-only fields and ARE in scope as future-Phase-7 work, NOT here).
- Fills-derived counterfactual `realized_R_if_plan_followed` (Phase 7 upgrade).
- Drawdown circuit breaker as a default-on feature (aligned with v1.2 default-disabled; no V1 wiring).
- Configuration-page surface for `cfg.review.review_window_days` (deferred; default of 7 is hardcoded at config-load time; future small dispatch surfaces it via the Phase 5 config infrastructure).
- Quarterly + circuit_breaker cadence dashboard cards (schema-supported only; no V1 UI).
- Compliance ratios (`data_quality_score`, `review_compliance_rate`, `reconciliation_compliance_rate`) on Review_Log (deferred to Phase 9; depend on Reconciliation_Run).
- Editing existing closed-trade outcome fields (entry_price, exit_price, etc.) via review form — review form is ADDITIVE only; outcome fields read-only.
- Trade re-review (overwriting `reviewed_at` and re-completing aggregates) — V1 is single-review per trade; if operator wants to revise a review, the path is direct DB edit OR a future small dispatch adds revise capability.

### §3.3 Phase isolation carve-outs

Per CLAUDE.md invariant ("`swing/trades/` and `swing/data/` are consumed read-only unless the current-phase spec explicitly scopes a carve-out"), Phase 6 carve-outs are:

- **`swing/data/`**: new migration `0013_phase6_post_trade_review.sql`, new repo file `swing/data/repos/review_log.py`, extend [swing/data/repos/trades.py](../swing/data/repos/trades.py) with read/write for the 10 new fields, extend [swing/data/models.py:61](../swing/data/models.py#L61) `Trade` dataclass with the 10 nullable fields. NO modification of existing repo functions' signatures or semantics; additions only.
- **`swing/trades/`**: new file `swing/trades/review.py` (or `swing/trades/review.py` + `swing/trades/mistakes.py` if plan author splits) containing Mistake_Tags vocabulary, Process Grade computation, cost/violation derivation, and review service entry-points. Existing `swing/trades/entry.py`, `swing/trades/exit.py`, `swing/trades/stop_adjust.py`, `swing/trades/advisory.py` consumed read-only EXCEPT for adding the soft-warn surface to the close path (extends existing exit-path logic — narrow modification).

NO modification to `swing/evaluation/`, `swing/pipeline/` (except the new `_step_review_log_cadence` per §2.9), `swing/recommendations/`, `swing/journal/` (consumed read-only as the aggregate-computation source), `swing/prices.py`, `swing/cli.py` (extend with new command — additive only).

---

## §4 Plan structure (guidance — not prescriptive task count)

The plan author chooses the task partitioning, but the plan SHOULD be ordered such that:

1. **Schema-first slice** (Tasks 1-N): migration → Trade dataclass extension → repo writers/readers → Mistake_Tags vocab → Process Grade helper → cost/violation derivation helpers → review service → CLI command → soft-warn at trade close → pipeline-runner cadence pre-create step.
2. **Web slice** (Tasks N+1 to M): ReviewVM → web form route GET → web form route POST → templates (full page + partials) → DashboardVM extensions (badge + cadence cards) → dashboard template extensions.
3. **Discriminating-test discipline** at every layer per §6 watch items.

The plan MAY be one monolithic ordered task list OR sectioned into "Slice A" and "Slice B" headers — author's choice.

---

## §5 Binding conventions

- **Branch:** `main`. No feature branches at writing-plans phase. Plan you author specifies worktree isolation for the executing-plans dispatch (per §0 Skill posture).
- **Commits:** plan author commits the plan file as `docs/superpowers/plans/2026-05-XX-phase6-post-trade-review-plan.md` with conventional-commit message (e.g., `docs(phase6): writing-plans output — Phase 6 post-trade review plan v1`). Adversarial-Codex review fix commits per orchestrator-context Binding-conventions §"Commit-message conventions" (e.g., `fix(phase6-plan): Codex R1 Major 2 — process_grade helper signature`). No `--no-verify`; no Claude co-author footer; no amending.
- **TDD discipline at executing-plans time:** every task includes RED test + GREEN implementation + commit. The plan you author specifies tests at the granularity that catches the bug class — use the discriminating-test discipline catalog in §6 below.
- **Worktree isolation in the executing-plans dispatch you specify:** required per binding convention (Phase 6 hits both triggers). Plan task §0 ("Setup") MUST include `superpowers:using-git-worktrees` invocation + `touch .copowers-subagent-active` marker file step (per orchestrator-context line 323).
- **No code skeletons treated as verbatim:** brief skeletons in this brief are spec, but plan-tasks-with-code-bodies are STARTING POINTS for the executing implementer; plan author should explicitly mark them as "starting point — verify against spec" rather than implying verbatim-correct (per Phase 7 brief-skeleton-bugs lesson, 2026-04-27).
- **Empirical verification at plan-draft time:** plan author MUST grep + read the actual codebase before drafting plan tasks (per chart-scope policy v2 writing-plans lesson, 2026-04-27 R1/R2/R3 multiple findings about implementer mis-references). Examples of required pre-empirical-verifications: confirm `compute_stats` signature; confirm Trade dataclass field count + types; confirm `_step_export` signature so `_step_review_log_cadence` ordering works; confirm `swing/web/routes/trades.py` route registration pattern.

---

## §6 Adversarial review

### §6.1 Target

`NO_NEW_CRITICAL_MAJOR` after 4-5 Codex rounds. Compound ROI per Phase 7 implementer-side lesson — Phase 6's bug-surface is dense (schema + new entity + new computed values + new web surface + new pipeline step + new CLI + soft-warn at close).

### §6.2 Operator-pre-designated watch items

Adversarial Codex will surface these; the plan author should pre-empt by enumerating mitigations in the relevant plan tasks. Pre-designated watch items are PRE-EMPTIVELY ACCEPTED-by-rationale ONLY when the plan task explicitly calls out the mitigation; otherwise they're real findings.

1. **Multi-path data ingestion needs full-path audit** (sector capture R2 M1, 2026-04-29). The 10 new trade fields are written via web review form, CLI `swing trade review`, AND repo direct edit. Plan task for repo writer MUST enumerate ALL writers + verify field-name parity. The Mistake_Tags vocabulary list must be the SAME constant referenced from CLI + web + repo validation — no copy-pasting.

2. **JSON-list grouping-key requires canonicalization-at-persistence-boundary** (hypothesis_label R1/R2 lesson, 2026-04-25). `mistake_tags` is a JSON-list field used for downstream grouping/aggregation (e.g., "trades with `OVERSIZED` mistake"). Repo writer MUST canonicalize: NFC normalization, control-char strip, sorted order (so `["A","B"]` and `["B","A"]` are stored identically), no duplicates. Discriminating tests must cover unicode + dup + order variants.

3. **Snapshot-semantic claims need transaction isolation explicitly addressed** (chart-scope policy v2 R1 M1, 2026-04-28). Review_Log row's persisted aggregates are a snapshot of a window of closed trades. The aggregate-compute → Review_Log INSERT operation MUST be wrapped in a single transaction (BEGIN/COMMIT) so a concurrent trade close mid-compute can't tear the snapshot. Plan task MUST specify transaction boundary explicitly.

4. **Operator-facing message strings emitted from MULTIPLE resolver paths must be valid for ALL paths** (chart-scope policy v2 R1 M2, 2026-04-28). The "Review due within 7 days" soft-warn message is emitted from web close path AND CLI close path. Both must produce the same operator-visible string; plan task should reference a shared constant or template.

5. **Helper-internal anchoring of side-effecting boundaries** (OHLCV archive R1 C1, 2026-04-30). The cadence-pre-create step has time-dependent side-effects (creating Review_Log rows for "prior" periods). It MUST anchor at `action_session_for_run(datetime.now())`, not `date.today()`. Plan task for `_step_review_log_cadence` MUST specify the anchor explicitly. The `period_start`/`period_end` calculation MUST be helper-internal — caller cannot supply an as-of-date that controls which prior period rows are created.

6. **HTMX form-driven endpoints have HX-Request + HX-Redirect failure surfaces** (Phase 5 R1 M1+M2, 2026-05-02). The `/trades/<id>/review` POST is a form-driven endpoint. Plan tasks MUST specify:
   - Embedded `<form>` includes `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode.
   - Success-path response is `204 + HX-Redirect: <url>` header (browser re-navigates), NOT `303` to swap-target. TestClient verifies status code only; operator-witnessed browser verification is BINDING for HTMX work.

7. **HTMX `<tr>`-leading `makeFragment` table-wrap pathology** (entry_post Bug B, 2026-04-29). If any review-form HTMX fragment leads with `<tr>`, the htmx.js `makeFragment` helper wraps in synthetic `<table><tbody>` and drops inner `<table>` content during fragment parse. Plan task for HTMX response design MUST keep response primary content table-row-free at fragment root (use `<div>` or `<section>` at root; deliver row updates via OOB swap into destination tbody).

8. **New-VM existing-field inheritance** (Phase 5 writing-plans Task 7, 2026-05-01). `ReviewVM` extends `base.html.j2` and MUST include all existing fields the base layout dereferences with safe defaults (`session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`). This is the COMPLEMENT case to the 5-VM rule (which is about NEW fields the base layout dereferences); both checks needed independently.

9. **Base-layout 5-VM rule applies only when `base.html.j2` dereferences the field** (Phase 4 lesson, 2026-04-26). New `DashboardVM.needs_review_count` and cadence-card fields are likely consumer-scoped (rendered in dashboard templates only, not base.html.j2). Plan task should NOT blanket-require the 5-VM rule; verify whether `base.html.j2` actually references the new fields before requiring mitigation. (The cadence-card fields are CERTAINLY consumer-scoped to dashboard.)

10. **TestClient cannot detect HTMX runtime DOM state** (multiple lessons). Operator-witnessed browser verification gate is BINDING for the `/trades/<id>/review` form work. Plan done-criteria MUST include operator-witnessed manual verification of: form renders correctly, soft-warn at close fires correctly, dashboard "needs review" badge appears + clickable, dashboard cadence cards render, review submission persists + redirects, review revisit shows correct frozen aggregates.

11. **Discriminating-test discipline** (multi-lesson catalog: secondary-key re-masking, bound-reference confusion, substring-vs-exact, symmetry-via-deterministic-tiebreaker, monkeypatch-capture failure, hand-crafted-multi-step-resubmit). Plan tasks MUST verify each discriminating test answers "would this test fail if the implementation never actually called the new code?" Specific Phase 6 risks:
    - Process Grade computation tests must use weighted-numeric inputs that distinguish weights (e.g., `entry=A, management=A, exit=F` should produce numeric `(0.40 × 4) + (0.35 × 4) + (0.25 × 0) = 3.0 = B`, NOT `F` from the floor — but `disqualifying=true` should override to `D`. The parameterized table MUST cover BOTH the weighted path AND the floor paths so a buggy implementation that ALWAYS returns the weighted value (skipping the floor) fails on the F-floor + disqualifying-D rows).
    - `mistake_cost_R` / `lucky_violation_R` derivation tests must use scenarios where `realized_R_if_plan_followed > actual` (cost), `realized_R_if_plan_followed < actual` (lucky), `realized_R_if_plan_followed = actual` (both zero), and verify they're NEVER netted (cost AND lucky should never both be > 0 for the same row).
    - Cadence pre-create idempotence test must run the step TWICE and assert no duplicate rows.
    - Review_Log aggregate freezing test must (a) compute aggregates, (b) close an additional trade, (c) re-render the same Review_Log row, and assert the persisted aggregates DID NOT change.

12. **Brief-speculation about consumer code state should be empirically verified at brief-draft time** (Phase 5 writing-plans lesson, 2026-05-01). Plan author MUST run `grep -rn` audits on every claimed signature / field path / function name in this brief BEFORE drafting plan tasks. The §0 "Read first" empirical audit step is the discipline; if any claim in this brief proves wrong at audit time, plan author corrects in plan tasks AND notes the correction in the return report.

13. **Pre-create step ordering vs `_step_export`** (operational concern). The new `_step_review_log_cadence` step lands after `_step_export` so it doesn't block briefing/export emission if it errors. Plan task MUST verify ordering AND specify error-handling: cadence-pre-create errors LOG but don't fail the pipeline (the pipeline's primary value chain is candidate evaluation + briefing emission; review log is auxiliary).

14. **Discriminating assertions vs coupled text updates** (Tier-1 mathtext fix lesson, 2026-04-27). Plan tasks updating multiple test lines should pre-classify each as "discriminating assertion" (will flip RED → GREEN with the fix) vs "coupled text update" (must stay in sync but doesn't independently discriminate). Avoids implementer confusion.

### §6.3 Pre-designated out-of-scope watch items

These will likely surface as adversarial findings; pre-empted dispositions:

- **Lost-update race on Review_Log completion across two browser tabs.** ACCEPTED out-of-scope per single-operator framing (per Phase 5 R1 Major 3 ACCEPTED with same rationale; see CLAUDE.md). V2 may add file locking if a multi-user surface ever emerges.
- **Mistake_Tags vocabulary completeness vs operator's actual mistakes.** v1.2 §7.10 is the source-of-truth for V1; if operator surfaces mistakes that don't fit any tag, future small dispatch extends the constant. Schema accepts any string in the JSON list (validation is repo-layer); future tag additions don't require migration.
- **Aggregate computation drift between `swing/journal/stats.py:compute_stats` and Review_Log persistence.** Plan task MUST use the existing `compute_stats` infrastructure as the SOLE source — no parallel re-implementation. If plan author finds `compute_stats` insufficient, capture as an out-of-scope finding with rationale; do NOT re-implement aggregates inside Phase 6.
- **`realized_R_if_plan_followed` interpretation ambiguity.** Operator-input field; semantics are operator-defined. Form helper text guides ("What R would you have realized if you'd followed your original plan exactly?") but doesn't enforce. Phase 7 Fills-derivation will tighten semantics.

---

## §7 Done criteria

The dispatch is complete when ALL of the following hold:

- [ ] Plan committed to `docs/superpowers/plans/2026-05-XX-phase6-post-trade-review-plan.md` with conventional-commit message.
- [ ] Plan structure follows §4 guidance (schema-first slice + web slice).
- [ ] Every locked decision in §2 is reflected in a plan task (no design re-litigation).
- [ ] Every operator-pre-designated watch item in §6.2 is either pre-empted by a plan task's mitigation OR explicitly tagged as "out-of-scope-by-design" with rationale.
- [ ] Adversarial Codex review iterated to `NO_NEW_CRITICAL_MAJOR`. Round count + per-round disposition summary in return report.
- [ ] §0 empirical audit step output captured in return report (which assertions in this brief turned out wrong; what plan tasks reflect the corrections).
- [ ] Plan task §0 ("Setup") specifies worktree isolation + marker-file workflow per binding convention.
- [ ] Plan done-criteria includes operator-witnessed browser verification gate per §6.2 watch item 10.

---

## §8 Return report format

Single Markdown message back to orchestrator. Sections:

1. **Status:** SHIPPED / BLOCKED / PARTIAL.
2. **Plan file:** path + commit SHA.
3. **Empirical audit findings:** list any §0 brief assertions that proved wrong + how the plan reflects the correction.
4. **Plan structure:** task count + slice partitioning (Slice A vs Slice B if used).
5. **Adversarial Codex disposition:** round count; per-round (Critical / Major / Minor) counts; FIXED vs ACCEPTED-with-rationale dispositions.
6. **Locked decisions reflected:** confirm each §2.1-§2.10 decision is encoded in plan tasks.
7. **Watch items pre-empted:** confirm each §6.2 watch item is addressed.
8. **Open questions:** anything you couldn't decide that needs orchestrator input. Default: none — the spec is locked.
9. **Test-baseline expectations:** plan's expected fast-test-count delta (current 1472).

---

## §9 If you get stuck

- **Spec ambiguity:** check phase3e-todo.md:946-1056 first; check v1.2 source sections second; if neither resolves, return open-question to orchestrator BEFORE drafting plan tasks against the ambiguity.
- **Empirical audit reveals brief-claim-wrong:** correct in plan tasks, capture in return report §3. Don't pass-through stale claims (see Phase 5 writing-plans lesson).
- **Adversarial Codex finding suggests changing a §2 locked decision:** ACCEPT-with-rationale citing the operator-lock; do NOT modify the plan to change the decision. If the finding's substance is independently real (e.g., the locked decision has a flaw the operator didn't anticipate), capture in return report §8 as open-question.
- **Plan exceeds 60 tasks:** consider splitting the brief into two writing-plans dispatches (Slice A + Slice B). Surface to orchestrator as open-question §8 BEFORE proceeding.
- **Codex round count exceeds 6:** writing-plans-phase failure surfaced post-dispatch (per chart-scope policy v2 lesson, 2026-04-27). Pause + return open-question §8 to orchestrator.

---

**End of brief.**
