# Phase 13 T4.SB Writing-Plans Return Report

**Branch:** `phase13-t4-sb-writing-plans` at `711637e`
**Baseline:** main HEAD `637f156`
**Plan artifact:** [`docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md`](superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md) — 4184 lines; 6 sub-bundle tasks T-T4.SB.1..T-T4.SB.6; 12 sections §A-§N
**Dispatch brief:** [`docs/phase13-t4-sb-writing-plans-dispatch-brief.md`](phase13-t4-sb-writing-plans-dispatch-brief.md) at `4690933`
**Substrate spec:** [`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`](superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md) at `f7dec0e`

---

## §1 Status

T4.SB writing-plans SHIPPED at branch HEAD `711637e`. Plan ready for executing-plans dispatch.

- 5 commits (1 initial plan + 4 Codex MCP fix bundles).
- 5670 fast tests baseline UNCHANGED (writing-plans is docs-only).
- Schema v21 UNCHANGED (writing-plans touches docs only; no migration created).
- Ruff `swing/` 0 E501 — `All checks passed!`.
- ZERO Co-Authored-By footer drift (~378+ cumulative streak preserved).

---

## §2 Codex MCP adversarial-critic chain shape

5 rounds executed. Thread ID `019e5208-7d2c-7e82-9927-570915f0bc3d`. Converged at R5 NO_NEW_CRITICAL_MAJOR.

| Round | Critical | Major | Minor | Verdict | Resolution commit |
|---|---|---|---|---|---|
| R1 | 2 | 6 | 3 | ISSUES_FOUND | `7cc5775` |
| R2 | 0 | 3 | 3 | ISSUES_FOUND | `0023df7` |
| R3 | 0 | 3 | 3 | ISSUES_FOUND | `600313f` |
| R4 | 0 | 2 | 3 | ISSUES_FOUND | `711637e` |
| R5 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** | (convergence) |

**Cumulative resolved:** 2 CRITICAL + 14 MAJOR + 12 MINOR = 28 findings. All resolved in-place.

### §2.1 Round-by-round headline themes

**R1 (2 CRITICAL + 6 MAJOR):**
- CRITICAL #1: T-T4.SB.1 sensitivity-harness left `_emit_*_thresholds` placeholders + sweep only handled 2 vars → REPLACED with 18-now-17-row concrete enumeration from real `Config` dataclass shapes.
- CRITICAL #2: `_bucket_for_substituted` missing `allowed_miss_names` invariant → REWRITE faithfully mirrors `bucket_for`; cfg threaded through.
- MAJOR #1: `hypothesis_registry.description` column doesn't exist → switched test fixtures to actual v8 schema columns.
- MAJOR #2: `ChartRender` construction missing 4 required fields → fixed to mirror dataclass at `swing/data/models.py:1907-1924` + existing `_step_charts` pattern.
- MAJOR #3: Renderer kwargs wrong (`render_market_weather_svg(ticker=...)` doesn't take ticker; `render_position_detail_svg` needs `fills`; `render_watchlist_thumbnail_svg` needs `ma_lines`) → corrected per actual signatures.
- MAJOR #4: `pipeline_runs.state='completed'` not in CHECK enum → changed to `'complete'`.
- MAJOR #5: Item 3 volume-yticks test API mismatch → updated to real signatures.
- MAJOR #6: `count_per_cohort` empty-registry orphan-handling gap → added `else` branch.

**R2 (0 CRITICAL + 3 MAJOR):**
- MAJOR #1: Variable count narrative inconsistency (18 vs 17) → corrected to 17 throughout; exact name-set assertion replaces `>=10` loose check.
- MAJOR #2: Output formatter doesn't surface gate vs threshold distinction → introduced 3-value `kind` taxonomy + binding Notes paragraph + 2 discriminating tests.
- MAJOR #3: `request.app.state.db_conn` doesn't exist → switched to per-request `sqlite3.connect(cfg.paths.db_path)` pattern from `account.py` / `charts.py` route precedent.

**R3 (0 CRITICAL + 3 MAJOR):**
- MAJOR #1: `kind` not propagated to `SweepEntry` / CSV / formatter → added `kind` field to dataclass + widened CSV headers + markdown matrix Kind column.
- MAJOR #2: Gate-variable test fixtures still used `kind="additive"` → corrected to `kind="gate"`.
- MAJOR #3: hyp-recs JIT fallback test didn't exercise `data_asof_date` requirement → test now passes anchor + verifies round-trip via cache row SELECT + added negative test asserting JIT skipped when `data_asof_date=None`.

**R4 (0 CRITICAL + 2 MAJOR):**
- MAJOR #1: Watchlist route called undefined `_latest_completed_pipeline_run` → imports actual `latest_completed_pipeline_run` from `swing.web.chart_scope` (verified at chart_scope.py:82).
- MAJOR #2: Method-record narrative contradicted gate-vs-threshold semantics → expanded with 6-section structure encoding the split explicitly.

**R5:** NO_NEW_CRITICAL_MAJOR convergence.

### §2.2 Minor findings RESOLVED across the chain

12 minors total resolved inline (no advisories left open). Highlights:
- Self-review wording updates as the taxonomy evolved (R1 → R3 → R4).
- CSV column count corrections (8 → 9 → 9; transient 10-count typo).
- Threshold variable count corrections (16 → 15) as `min_passes` gate-vs-threshold ambiguity collapsed.
- Module-global concurrency hazard removed (R2 Minor #1).
- CLI-invocation style clarified (implementer-side worktree vs operator-installed).

---

## §3 Plan deliverables (per dispatch brief §4 done criteria)

12 sections §A-§L all present + an additional §M references + §N self-review:

- §A Status + scope — encodes 7 triage items + 18 OQ dispositions verbatim + 4 §1.5 amendments + complete file map.
- §B Per-task design — 6 sub-bundle tasks with bite-sized TDD step lists (149 step-checkboxes total; 2-5 min each).
- §C Cross-task dependencies + concurrent-dispatch graph — sequential vs concurrent dispatch options + wall-clock savings estimate.
- §D Investigation outputs format — sensitivity matrix CSV (9 cols including Kind) + markdown analysis (Kind column + V1-LIMITATION paragraph) + audit table layout.
- §E Cross-bundle pin row 13 — parametrized 4-surface invariant; plant/promote schedule.
- §F Test scope projection — per-task budget ~5760-5805 fast + 1 fast E2E.
- §G Per-task acceptance criteria — lifted from §B per-task summaries.
- §H Dispatch sequence — sequential (conservative) + concurrent alternative + S1-S5 operator-witnessed gate.
- §I Forward-binding lessons — 14 cumulative gotchas applied per task + 7 expansions + 4 NEW candidate refinements (including Expansion #10 architecture-location 5-sub-discipline) BINDING for 29th cumulative validation.
- §J §1.5 amendments encoded — explicitly per amendment with rationale + scope impact.
- §K Research-branch coordination — V2.1 §IV.D + §VII.C lifecycle posture.
- §L Phase 13 closure procedure — T-T4.SB.6 acceptance criteria + triage-agenda artifact.

---

## §4 V1 simplifications + V2 candidates banked

Per cumulative discipline (T2.SB6b lessons gotcha), each V1 simplification carries an explicit V2 dependency citation. Banked at writing-plans phase:

| # | V1 simplification | Location | V2 dependency |
|---|---|---|---|
| 1 | Sensitivity-harness threshold variables (15 of 17) return persisted_bucket; deltas always 0 | `research/harness/aplus_sensitivity/sweep.py:_bucket_for_substituted` | V2 OHLCV criterion-evaluator harness consuming original bars at `candidate.data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end (cited in `research/method-records/aplus-criteria-calibration.md` V2 dependencies section). |
| 2 | `cfg.trend_template.allowed_miss_names` EXCLUDED from V1 variable enumeration (tuple-set; not numeric grid) | `research/harness/aplus_sensitivity/variables.py` | V2 set-membership sweep variant (e.g., add/remove TT8 from allowed set + recompute). |
| 3 | `cfg.rs.benchmark_ticker` EXCLUDED from V1 variable enumeration (string identifier; not threshold) | same | V2 benchmark-ticker sensitivity sweep (likely cross-coupled with RS module rewrite). |
| 4 | `metrics_wiring_audit._KNOWN_SURFACES` hand-maintained registry (4 entries V1) | `swing/diagnostics/metrics_wiring_audit.py` | V2 codegen from decorator-marked surface registry. |
| 5 | Item 2 `--corpus-all` re-label flag remains OPERATOR-PAIRED (slow; ~34 subagent invocations) | `swing/cli.py:patterns_label_silver` | V2 batched-async re-label OR triggered automatically post-cfg-policy-loosening. |
| 6 | OQ-5.1 R4 manual prune CLI; R1 default unbounded growth (estimated ~300 MB/year per spec §B.5) | `swing/diagnostics/prune_chart_cache.py` (conditional) | V2 automated retention policy R2 (N pipeline_runs) OR R3 (>60 days). |
| 7 | OQ-5.2 synchronous JIT, no timeout (worst-case ~1-2s cold) | `swing/web/chart_jit.py:get_or_render_surface` | V2 async-render with HTMX placeholder swap if operator observes UX regression. |
| 8 | `hyprec_detail` cache key shape grandfathered (`hyprec_detail` surface name used for full-ticker detail chart across MULTIPLE UI surfaces) | chart_renders schema CHECK | V2 rename to `ticker_detail` + v22 schema migration (low priority; cosmetic). |
| 9 | OHLCV cache validity at original `data_asof_date` not guaranteed for sensitivity harness | implied by V2 dependency #1 | OHLCV archive reconstruction at arbitrary historical asof_date (per cross-bundle V2 work). |
| 10 | `_known_surfaces` audit dispositions are seeded with R1 best-guess + flipped to LIVE by T-T4.SB.2 implementer after fix | `swing/diagnostics/metrics_wiring_audit.py` | V2 auto-derivation from grep / static analysis. |

---

## §5 Forward-binding lessons banked at writing-plans phase

Banked for executing-plans phase + future T4-style closer arcs:

1. **Pre-Codex Expansion #10 (Architecture-location audit 5-sub-discipline) confirmed CORRECT for writing-plans phase.** All 5 sub-disciplines (wrong-module placement; template-vs-VM-parser-vs-emitter triangulation; cache-key + renderer-kwargs uniformity; SQL LIKE binding asymmetry; orphan-label preservation) applied at the right tasks. Codex chain did NOT surface architecture-location regressions in R1-R5 — the brainstorming spec's discipline carried forward correctly. **First clean-on-arrival validation of Expansion #10 at the writing-plans tier.**

2. **R1 surfaced a NEW lesson: writing-plans-phase test fixtures MUST grep actual migration files for column names BEFORE writing INSERT row strings.** The `hypothesis_registry.description` non-existent column was a writing-plans-phase MAJOR that survived self-review; the existing Expansion #4 SQL-column verification covers brainstorm + executing-plans phases per its banking but is now formally extended to writing-plans-phase test scaffolds too. **Refinement to Expansion #4 BINDING for future writing-plans dispatches.**

3. **R1 + R3 + R4 surfaced a 3-instance lesson: when a plan introduces a NEW dataclass with a `kind`/`status`/`type` enum field, the kind value MUST propagate to (a) related entry/result dataclasses, (b) the CSV header, (c) the markdown matrix table, (d) all test fixtures.** Three Codex rounds were needed to fully scrub the propagation; banking this as: **NEW Expansion #11 candidate — taxonomy propagation audit** (when an enum-typed field is added to one dataclass, audit all downstream dataclasses + serializers + test fixtures for consumption).

4. **R4 surfaced a writing-plans-phase variant of the existing "grep for actual helper name" discipline.** The plan called `_latest_completed_pipeline_run` (with leading underscore prefix) but the actual public helper is `latest_completed_pipeline_run` (no prefix). Banking: when a plan references a helper function from another module, grep the actual function definition site before writing the callsite — same family as Expansion #4 SQL column verification, extended to Python identifier verification.

5. **R2 surfaced a `request.app.state.<attr>` audit lesson.** The plan called `request.app.state.db_conn` but the attribute does not exist on app.state. When a plan invokes `request.app.state.<X>`, grep `swing/web/app.py` lifespan setup for the actual attribute population before writing the route handler. **Refinement to Expansion #4 BINDING for any plan touching web routes.**

6. **R1 + R3 surfaced a writing-plans-phase Synthetic-fixture-vs-production-emitter shape drift discipline.** Test fixtures planted via `INSERT INTO hypothesis_registry (id, name, description)` mirrored a SHAPE that doesn't match production emitter (the schema doesn't have `description`). Pre-empt: synthetic-fixture INSERT statements MUST mirror the actual CREATE TABLE column list verbatim — grep `swing/data/migrations/*.sql` for the table definition. Already covered by Expansion #4 SQL column verification + Synthetic-fixture-vs-production-emitter cumulative gotcha — this is a 5th instance of the same family.

---

## §6 Cumulative streaks preserved

- **ZERO `Co-Authored-By` footer trailer drift** — every commit on this branch (5 total) explicitly free of footer. Cumulative project streak now ~378+ commits.
- **C.C lesson #6 cumulative validations:** 29th expected NOTABLE at writing-plans phase per dispatch brief; this dispatch's Codex R1 R2 R3 R4 caught 14 MAJOR + 2 CRITICAL findings, all resolved in-place. Pre-Codex 7-expansion + 4 candidate refinements BINDING; Expansion #10 (architecture-location) ran CLEAN at the writing-plans tier (no new architecture-location MAJOR found by Codex — the brainstorming spec already encoded the 5 sub-disciplines correctly). NEW Expansion #11 candidate banked (taxonomy propagation audit) per lesson #3.
- **Schema v21 UNCHANGED** through writing-plans phase (docs only).
- **ZERO new Schwab API calls** (L2 LOCK preserved through writing-plans phase).
- **5670 fast tests baseline UNCHANGED** (writing-plans is docs only).
- **Ruff `swing/` 0 E501** preserved.

---

## §7 Self-verification

- ✓ Plan written at `docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md` (4184 lines; 12 sections §A-§N; 6 sub-bundle tasks; 149 bite-sized step-checkboxes).
- ✓ Codex MCP chain converged at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds.
- ✓ All 28 R1-R4 findings RESOLVED in-place (2 CRITICAL + 14 MAJOR + 12 MINOR).
- ✓ `git log --oneline main..HEAD` shows 5 commits on branch.
- ✓ Ruff clean (`All checks passed!` on `swing/`).
- ✓ No schema migration created (v21 preserved).
- ✓ Session-state file written to temp dir per skill contract.
- ✓ Return report at `docs/phase13-t4-sb-writing-plans-return-report.md`.

---

## §8 Handoff to operator

Orchestrator-side next steps (Turn B; per dispatch brief §7):

1. QA implementer product per `feedback_orchestrator_qa_implementer_product` — verify file:line citations + shipped-behavior + locks-preserved against reality on disk (especially the 28 Codex findings the chain caught).
2. Merge `phase13-t4-sb-writing-plans` `--no-ff` to `main`; push.
3. Post-merge housekeeping bundle (CLAUDE.md current-state refresh; phase3e-todo.md top entry; orchestrator-context.md current-state + recent-decisions update; Prior demote + archive-split if size-check trigger; possibly NEW Expansion #11 candidate banked at CLAUDE.md gotcha #15).
4. Draft T4.SB executing-plans dispatch brief + amendments if any.
5. Provide inline implementer dispatch prompt for executing-plans phase.

---

*End of T4.SB writing-plans return report. 5-round Codex MCP convergence; 2 CRITICAL + 14 MAJOR + 12 MINOR all RESOLVED in-place; ZERO Co-Authored-By footer drift preserved; v21 schema UNCHANGED; baseline 5670 fast tests UNCHANGED; ruff clean. NEW Expansion #11 candidate banked (taxonomy propagation audit). Plan ready for executing-plans dispatch.*
