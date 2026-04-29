# Sector/Industry Capture + Display — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for sector/industry capture + display in the Swing Trading project. Brainstorm is EXPLICITLY SKIPPED — operator locked all design decisions on 2026-04-28 (see §2). This dispatch goes directly to writing-plans phase.

**Expected duration:** ~30-90 min plan-authoring + 3-5 Codex rounds via `copowers:writing-plans` wrapper = ~2-4 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT executing-plans; this dispatch produces a plan, NOT shipped code).

---

## §0 Read first

Read these in order before drafting:

1. **`CLAUDE.md`** at repo root — project conventions, gotchas, invariants. Note the base-layout 5-VM rule (only applies if `base.html.j2` actually dereferences the new field; per 2026-04-26 lesson don't blanket-require unless applicable).
2. **`docs/orchestrator-context.md`** — §"Currently in-flight work" (current state at HEAD), §"Binding conventions" (commit-message convention, observable-verification grep, ruff baseline 91, no-amend, no Claude footer), §"Anti-patterns to avoid" (vacuous regression tests, brief drafting drift, etc.), §"Lessons captured" (read entire section — multiple lessons apply: discriminating-test discipline, compounding-confound class, snapshot-semantic transaction-isolation, toml-shadowing).
3. **`docs/phase3e-todo.md`** §"2026-04-28 sector/industry capture + display" — **THE SCOPE-OF-WORK SOURCE OF TRUTH** for this dispatch. All locked decisions are recorded there verbatim; §2 below mirrors them but the todo entry is canonical if there's any divergence.
4. **`swing/data/migrations/0007_trade_hypothesis_label.sql`** — pattern precedent: text field added to `trades` for snapshot-at-entry capture.
5. **`swing/data/migrations/0010_trade_chart_pattern.sql`** — pattern precedent: multi-field snapshot-at-entry capture with cross-column invariants. Sector/industry is SIMPLER (no cross-column invariant), but follow the snapshot-at-entry pattern.
6. **`swing/data/migrations/0011_pipeline_chart_targets_source_taxonomy.sql`** — most-recent migration (numbering reference: this dispatch's migration is 0012).
7. **`swing/pipeline/finviz_schema.py`** — confirms `Sector` and `Industry` are validated columns at CSV ingestion.
8. **`swing/data/repos/candidates.py`** — pipeline-side ingestion target (where `_step_evaluate` writes candidate rows).
9. **`swing/data/models.py`** — `Candidate` and `Trade` dataclass definitions; sector/industry fields will be added here.
10. **`swing/web/view_models/dashboard.py`** — VM precedents for hyp-recs row + watchlist row + open positions row.
11. **`swing/web/view_models/`** — find `TradeEntryFormVM` (likely in `trade_entry_form.py` or similar) for trade entry surface.
12. **`swing/web/templates/partials/`** — templates for hyp-recs row, watchlist row expansion, trade entry form, open positions row.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before drafting plan tasks against it.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming` or `copowers:brainstorming` — design decisions are pre-locked (see §2). Re-litigation is out of scope. If you find a locked decision is impossible to implement as written, STOP and surface it in the return report; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Plan output target path:** `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`. Commit the plan as part of the standard cycle.

---

## §1 Strategic context

**The data is ingested but dropped.** Finviz CSV schema validator at `swing/pipeline/finviz_schema.py:12` requires both `Sector` and `Industry` columns; rejected to `data/finviz-inbox/rejected/` if either column is missing. CSV is INGESTED with both fields, then both fields are DISCARDED before persistence. Zero hits for `sector` or `industry` columns anywhere in `swing/data/` (11 migrations + repo files + dataclass models surveyed pre-dispatch).

**The framework presumes sector analysis happens.** `docs/orchestrator-context.md` lines 156-157 explicitly include sector in operator's manual decision process: "Operator validates the recommendation (chart pattern, risk, **sector preference**) and either takes the trade or declines." The operator currently has to look up sector externally per ticker because the framework drops the data on the way in.

**This dispatch closes the gap.** Persist sector + industry on `candidates` (per pipeline run) and on `trades` (frozen at entry, per snapshot-at-entry-surface pattern); display on 4 surfaces; capture on trade entry.

**Sequencing context.** This dispatch ships BEFORE the queued hyp-recs trade-prep expansion brainstorm (operator decision 2026-04-28). Hyp-recs expansion will consume sector as a pre-captured field; that's a downstream concern — out of scope for THIS dispatch.

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked 2026-04-28. The plan implements these as written; no re-design.

1. **Granularity.** Persist BOTH sector AND industry. Display BOTH on display surfaces. Don't reduce to sector-only.
2. **Display surfaces (V1).** Four surfaces:
   - Hyp-recs row expansion (HTMX-expanded panel under `partials/`).
   - Watchlist row expansion (existing expand panel; add sector/industry rows).
   - Trade entry form (read-only field showing the snapshot value to be persisted).
   - Open positions row (informational; show sector/industry alongside the existing fields).
   - **Out of scope (V2 deferred):** Journal review aggregation; sector concentration warnings.
3. **Frozen-at-entry vs always-current.** **Frozen-at-entry** on `trades` table. Mirrors `hypothesis_label` (migration 0007) and `chart_pattern_*` (migration 0010) snapshot-at-entry-surface pattern. Reasoning per todo: if sector data drifts post-entry due to ticker reclassification, that's information worth preserving — operator entered when ticker was Tech; analysis should know it's now Industrials.
4. **Source-of-truth.** Finviz only. Do NOT reconcile with yfinance sector taxonomy (yfinance has its own taxonomy that differs). Finviz is single authoritative source.

---

## §3 Scope

### V1 in-scope (this dispatch's plan covers ALL of these):

**A. Schema migration 0012.**
- Add `sector TEXT NOT NULL DEFAULT ''` to `candidates` table.
- Add `industry TEXT NOT NULL DEFAULT ''` to `candidates` table.
- Add `sector TEXT NOT NULL DEFAULT ''` to `trades` table.
- Add `industry TEXT NOT NULL DEFAULT ''` to `trades` table.
- Migration uses simple ALTER TABLE ADD COLUMN (no CREATE-COPY-DROP-RENAME needed; no cross-column invariants in V1; default empty string preserves backfill behavior on historical rows).
- Bump `EXPECTED_SCHEMA_VERSION` from 11 → 12 in `swing/data/__init__.py` (or wherever it lives).

**B. Pipeline ingestion.**
- `_step_evaluate` writes Sector + Industry from each Finviz CSV row into the candidate row. Already-validated by schema; just needs to flow to persistence.
- `Candidate` dataclass in `swing/data/models.py` gains `sector: str` and `industry: str` fields.
- `swing/data/repos/candidates.py` `insert_candidate` (or equivalent) signature extended; SELECT queries return the new columns.
- `_row_to_candidate` (or equivalent) populates the new fields.

**C. Trade entry capture (frozen-at-entry).**
- `Trade` dataclass gains `sector: str` and `industry: str` fields.
- `EntryRequest` dataclass (or equivalent — verify name) gains `sector: str` and `industry: str` fields.
- `record_entry` persists what's passed AS-IS (per existing snapshot-at-entry-surface ToCToU pattern, spec §3.6 / Phase 5 chart-pattern lesson).
- Trade entry form's POST handler resolves sector + industry from the candidate row at form-render time, passes through hidden fields (or via separate lookup at submit time — verify the existing `chart_pattern_*` field mechanism and mirror it).
- Trade entry CLI (`swing trade entry`) accepts `--sector` and `--industry` (or — preferred — auto-resolves from candidate row by ticker; if no candidate exists, persist empty strings rather than failing).

**D. Display surfaces.**

For each of the 4 surfaces, add sector + industry as read-only display rows:

- **Hyp-recs row expansion.** Likely `partials/hypothesis_recommendations.html.j2` or expansion thereof. Add 2 rows: "Sector: ..." and "Industry: ..." after existing context fields.
- **Watchlist row expansion.** `partials/watchlist_expanded.html.j2` (per Phase 3e §3e.4/§3e.5 history). Add 2 rows.
- **Trade entry form.** `partials/trade_entry_form.html.j2`. Add 2 read-only rows showing the resolved snapshot (these are NOT editable inputs; they show what'll be frozen).
- **Open positions row.** Likely `partials/open_positions_row.html.j2`. Add 2 rows (informational only).

VM-level changes needed depending on which VMs feed which template:
- `DashboardVM` — likely needs sector/industry on the hyp-rec items + open-position items.
- `WatchlistVM` — needs sector/industry on watchlist entries.
- `TradeEntryFormVM` — needs `sector` + `industry` fields populated from candidate snapshot at render time.
- **Base-layout 5-VM rule:** does `base.html.j2` reference `sector`/`industry`? Almost certainly NOT (these are consumer-scoped fields, not page-level). Verify before requiring all 5 base-layout VMs to gain the field; per 2026-04-26 lesson, don't blanket-require.

### V1 out-of-scope (DEFER; V2 candidates):

- Journal review aggregation (group by sector; per-sector expectancy / win rate / R-multiple).
- Sector concentration warning surface (dashboard banner: "you have N positions in Sector X exceeding Y% of risk").
- Industry-level concentration warning (probably not useful at $7,500 / 5-position scale anyway).
- yfinance sector reconciliation.
- Sector/industry editing (manual override of the captured snapshot — V2 if ever; V1 trusts Finviz).
- Sector/industry display on briefing.md / briefing.html (briefing template not in V1 surface list).

---

## §4 Plan acceptance criteria

The plan output (at `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`) MUST satisfy:

1. **Per-task TDD discipline.** Each task: failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
2. **Discriminating-test discipline (per orchestrator-context lessons).** Every task with a discriminating test includes a "would this test fail if the implementation never actually called the new code?" sanity-check sentence in the task body. Failure to include = plan-quality miss.
3. **Compounding-confound class avoidance** (Phase 4 + chart-scope-policy-v2 lessons). Tests that assert on a primary key must NOT have secondary keys (alphabetical tiebreakers, default sort orders) that mask the bug. Plan tasks must INVERT setups so bug's output diverges from correct output's secondary-key path.
4. **Sequential single-subagent execution discipline.** Plan tasks are SEQUENTIAL; no parallel-subagent collision risk at this scale. Plan task IDs follow the convention (Task X.Y format).
5. **Observable-verification subject-only grep pattern** per binding conventions: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` before each task implementation commit. ERE flag required (BRE chokes on `+`); POSIX `[0-9]` for digit class. Each task includes this verification step in its body.
6. **Commit-message convention (4-tier per binding conventions).**
   - Task implementations: `feat(area): Task X.Y — <description>`
   - Codex review-fix commits: `fix(area): Codex R1 Major 2 — <description>`
   - Internal-Codex within-task: `(internal)` qualifier
   - Internal code-review: `fix(area): code-review I1 — <description>`
   - Format-only cleanup: no task ID
7. **Schema migration 0012 task** is the FIRST task. All subsequent tasks depend on the migration landing.
8. **Pipeline ingestion task** comes second. Display surface tasks come after pipeline ingestion (display has nothing to display until candidates have sector populated).
9. **Display surface tasks** are independent of each other; each is its own task. Plan can sequence them in any order after pipeline ingestion.
10. **Trade entry capture task** comes after pipeline ingestion (depends on candidate having sector field) but is independent of display surface tasks.
11. **Test count baseline pinned at plan-time:** plan should note the current fast-test count (`python -m pytest -m "not slow" -q` to get exact number) and project per-task test additions.
12. **Plan passes copowers:writing-plans Codex review cycle:** iterate to `NO_NEW_CRITICAL_MAJOR`. Major findings are RESOLVED-by-fix (not ACCEPTED-with-rationale unless genuinely out-of-scope).

---

## §5 Adversarial review watch items (for Codex during writing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check:

1. **Discriminating-test vacuousness on primary-key assertions.** Cross-reference Phase 4 / chart-scope-policy-v2 lessons. Every task asserting "sector field rendered correctly" needs a setup where the sector value is DIFFERENT from a default/fallback that could mask the bug.
2. **Snapshot-at-entry-surface ToCToU pattern compliance.** Per spec §3.6 / Phase 5 lessons. The candidate's sector at form-render time is what gets persisted; do NOT re-resolve at submit-time. Mirror the `chart_pattern_*` precedent.
3. **Cross-column invariant absence — verify deliberate.** Unlike `chart_pattern_*` (4 invariants), sector + industry have NO cross-column invariants in V1. Plan should NOT introduce repo-layer validation beyond NULL-default-handling. If Codex pushes for invariants, ACCEPT-with-rationale: V1 trusts Finviz as source-of-truth; future V2 might add concentration constraints but not field-format invariants.
4. **Migration 0012 default-empty-string preserves historical rows.** Codex should verify the migration doesn't break any existing query that filters on sector/industry being NULL (there shouldn't be any, but verify).
5. **Plan task partitioning is DISJOINT.** Per Phase 2 self-collision lesson + 4-phase ZERO-rogue track record. Each plan task assigned to exactly one notional subagent (this dispatch is single-subagent so the partitioning is trivial; verify the partitioning is documented).
6. **Base-layout 5-VM rule application.** Is `base.html.j2` going to dereference sector/industry? Almost certainly not — these are consumer-scoped to row-level partials. Verify explicitly; if confirmed, plan should NOT require all 5 base-layout VMs to gain the field.
7. **Toml-shadowing audit.** Per `aeb2084` lesson. Sector/industry don't have config defaults to shadow (these are data fields, not config), but verify there's no config field named `sector_*` or similar that this dispatch would inadvertently introduce that would need toml-shadowing audit.
8. **Trade-entry CLI auto-resolution failure mode.** If a candidate row doesn't exist for the entered ticker (e.g., off-pipeline trade), what happens? Plan should specify: persist empty strings and log a warning, OR refuse the entry. Recommendation: persist empty strings (graceful degradation; matches `hypothesis_label` free-text behavior). Plan should make this explicit.

---

## §6 Done criteria

- Plan committed to `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`.
- Plan passes `copowers:writing-plans` Codex review cycle: 3-5 rounds, terminating at `NO_NEW_CRITICAL_MAJOR`.
- All Major findings RESOLVED-by-fix; ACCEPTED-with-rationale only if genuinely out-of-scope per §3.
- Test count baseline pinned in plan body.
- Per-task observable-verification step included in each task body.
- Per-task discriminating-test sanity-check sentence included in each task body where applicable.

---

## §7 Return report format

Post as final message:

```
## Sector/Industry Capture Plan — Writing-Plans Return Report

**Plan committed at:** docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md (commit <SHA>)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Test baseline pinned:** <count> fast tests at HEAD <SHA>
**Plan task count:** <N tasks>
**Migration version:** 0012

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- R2: <count> Critical, <count> Major, <count> Minor — all RESOLVED / <N> ACCEPTED with rationale
- ... (per round)

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision before executing-plans dispatch>

**Recommended next dispatch:** copowers:executing-plans on this plan, OR <alternative if implementer surfaces a concern>
```

---

## §8 If you get stuck

- **If a locked decision (§2) appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design. Examples: schema migration breaks an existing query (probably not but verify); existing display surface architecture incompatible with the read-only display rows.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Pre-dispatch survey may have stale references.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the discriminating-test sanity check reveals a vacuousness pattern across multiple plan tasks:** STOP, restructure the plan to eliminate the pattern, then resume Codex cycle. This is a plan-quality issue worth investing extra time in.

---

## Appendix A: Why brainstorm is skipped

Standard pattern is brainstorm → writing-plans → executing-plans. Per the 2026-04-27 brainstorm-pattern decision (orchestrator-context), brainstorm dispatch is appropriate when ≥3 medium-complexity decisions OR spec ≥500 lines OR orchestrator context approaching 60%+. This dispatch hits zero of those conditions:

- All 4 design decisions pre-locked by operator (granularity, display surfaces, snapshot-at-entry, source-of-truth).
- Spec content fits in §3 above (~100 lines); writing-plans phase will expand into per-task plan content but that's not a "spec" in the brainstorm-output sense.
- Orchestrator context at dispatch time was ~25-30%.

Adversarial review at writing-plans + executing-plans phases still applies; the brainstorm phase contributes nothing the locked decisions don't already provide.

If during plan-drafting the implementer discovers a design dimension the operator did NOT lock, surface in return report rather than deciding unilaterally.
