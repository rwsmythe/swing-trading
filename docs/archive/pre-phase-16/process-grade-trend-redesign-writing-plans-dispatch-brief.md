# Process-Grade-Trend Chart Redesign (+ nav-date fix) -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the process-grade-trend-redesign writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan for a small **web/UI fix bundle** -- the THIRD commissioned **Phase 15** arc (after schwabdev-v3 `#20` + B-7 `#21`, both CLOSED). Two items: (1) redesign the `/metrics/process-grade-trend` chart to **small-multiples** (3 scale-separated inline-SVG panels); (2) the bundled one-line `/reviews/pending` nav-date fix. **Presentation-only -- NO schema, NO migration, NO lock, NO live cutover, NO live-DB touch.**

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-06-03-process-grade-trend-redesign-design.md` (236 lines; merged to main `bdde2aa5`; single WSL Codex chain CONVERGED R2 `NO_NEW_CRITICAL_MAJOR`). Execute its design verbatim; **re-grep every cited file:line at writing-plans STEP 0** (the spec cites the dispatch HEAD; line numbers shift -- discipline #2).

**Brief:** `docs/process-grade-trend-redesign-writing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the schwabdev-v3 + B-7 arcs CLOSED; pgt-redesign brainstorm SHIPPED+merged `bdde2aa5`; main HEAD at this dispatch: see §8 (branch from it). ~7086 fast tests green; schema v24.

**Cumulative discipline:** the CLAUDE.md **Web/HTMX/forms** gotchas are BINDING (esp. the session-anchor read/write gotcha for the nav-date; the shared-`base.html.j2` 5-VM rule [NOT triggered -- neither item adds a new `vm.foo`]; the matplotlib-mathtext gotcha is N/A -- inline SVG); the **ASCII #16/#32** discipline for the SVG/legend strings; ~700+ cumulative ZERO Co-Authored-By; **Schema v24 UNCHANGED** (this arc adds NO migration).

**Expected duration:** ~2-3 hours writing-plans + a Codex chain to convergence. Plan line target **~500-800 lines** (2 slices).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the spec.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED (a bare `command -v codex` resolves to the DEAD Windows shim). PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). **Pass the prompt via STDIN, NOT command-substitution** -- `cat prompt.txt | codex exec -s read-only --skip-git-repo-check -` (the trailing `-` reads stdin); `"$(cat prompt.txt)"` breaks on parentheses/multiline. Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`; the Codex output is large + has non-ASCII glyphs -- extract the tail to a file to Read (do NOT `print()` it -- the cp1252 stdout crash, #16/#32). Memory `feedback_wsl_native_codex_invocation` (+ the 2026-06-03 prefix + stdin-pipe corrections) + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/2026-06-03-process-grade-trend-redesign-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end** -- esp. §1 (the LOCKed OQs) + §3 (slices).
2. **The SPEC** (`...redesign-design.md`, 236 lines) -- AUTHORITATIVE. Especially §3.2-3.7 (the 3-panel structure; the per-panel SVG; the per-series CSS two-class specificity fix; the 0-anchored cost axis + the all-zero `[0,1]` fallback; the VM per-panel grouping; the under-floor captions), §4 (the nav-date fix), §5 (tests + the operator browser gate), §7 (the 2 slices).
3. **The surface anchors (re-grep at writing-plans):** route `swing/web/routes/metrics.py:216-231`; VM `swing/web/view_models/metrics/process_grade_trend.py` (`build_process_grade_trend_vm:454-519`; `_y_axis_bounds_for_metric:315-335`; `_polyline_y:240-260`; `_polyline_x`; `_build_rolling_display:338`); template `swing/web/templates/metrics/process_grade_trend.html.j2` (the single `<svg>` `:24-66` -> 3 panels; the table `:68-120` UNCHANGED); CSS `swing/web/static/app.css` (the `--accent` + `body.dark` tokens); the metric matrix `swing/metrics/process_grade_trend.py:68-76` (read-only). Nav-date: `base.html.j2:69`; `build_reviews_pending_vm`/`ReviewsPendingVM` (`swing/web/view_models/trades.py:~1455/1490`; `:1459` the `session_date=""` default); `build_review_vm:1351` (the precedent line); `last_completed_session` in `swing/evaluation/dates`.
4. **CLAUDE.md -- the Web/HTMX/forms gotchas** (session-anchor read/write; shared-`base.html.j2`; matplotlib-mathtext N/A) **+ the Windows ASCII gotcha #16/#32** (the legend/axis/caption SVG strings) **+ the A-6 dark-mode fix** (`var(--accent)`; `tests/web/test_app_css_process_grade.py`). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines".
5. **Memory:** the WSL Codex transport (+ stdin-pipe) + persist-responses + round-limit-suspended + trailer-hazard + `feedback_visual_gate_both_render_and_browser` + `feedback_seeded_gate_masks_default_state` (the under-floor/empty default witness) + `feedback_regression_test_arithmetic`.

---

## §1 LOCKed OQ resolutions (operator 2026-06-03; BINDING -- DO NOT re-litigate)
| OQ | LOCKed |
|----|--------|
| **OQ-1 layout** | **Small-multiples -- 3 stacked inline-SVG panels** sharing ONE X (trade ordinal): GRADES `[0,4]` (the 4 grade lines + legend + `process_grade` markers), RATE `[0,1]`, COST `[0,max]` 0-anchored. (spec §3.2-3.3) |
| **OQ-2 colors** | **Distinct theme-aware colors + a legend** -- 4 new `--series-*` CSS tokens (`--series-process`=`var(--accent)`, `--series-entry/management/exit`) in BOTH `:root` + `body.dark`; per-series stroke via a **TWO-class selector** (`.process-grade-rolling-line.metric-<name>`) so specificity (not source order) wins (spec §3.4; Codex R1-M1). |
| **OQ-3 cost-scale** | **Chart `mistake_cost_R_..._per_trade` ONLY (0-anchored `[0,max]`); demote `_total` to the table.** The all-zero/no-data edge uses `[0,1]` (NOT `[0,0]`) so zero maps to the baseline with non-degenerate labels (spec §3.5; Codex R1-M2). |
| **OQ-4 nav-date** | **`last_completed_session(datetime.now()).isoformat()`** -- the backward-looking anchor (matches the sibling `build_review_vm:1351`); NOT `action_session_for_run`. |
| **OQ-5 scope** | **Redesign-only** -- no adjacent metrics-card affordance, no `/metrics` overview change. |

### §1.1 Inherited LOCKs (from the spec §2 / L1-L6; BINDING)
- **L1** presentation-only -- the metric COMPUTATIONS (`swing/metrics/process_grade_trend.py`) are READ-ONLY; no new metrics; the redesign is VM coordinate-mapping + template + CSS only.
- **L2 (inline-SVG-only, HARD)** hand-rolled inline SVG + the existing table; NO matplotlib / Chart.js / D3 / client renderer; the route test `test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib` STAYS GREEN.
- **L3** NO schema change (v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24; no migration; no `swing/data` or `swing/trades` write).
- **L4** preserve: the A-6 `var(--accent)` stroke/fill (additive `--series-*` tokens -- the existing 4 CSS assertions stay green); the >=5-effective-sample suppression floor + the per-trade `process_grade` markers; the DECOUPLED badge text elements (in the TABLE, lesson #23 -- untouched); the per-metric table (the redesign LEANS on it for `_total`).
- **L5** the nav-date fix uses `last_completed_session` + a render-assertion test.
- **L6** the binding gate is an operator browser-witness (legibility light+dark; the empty/under-floor DEFAULT state witnessed; `/reviews/pending` shows the date). TestClient = structural-only.

### §1.2 The CRITICAL test-preservation contract (do NOT break the existing route tests)
The GRADES panel MUST preserve the EXACT hooks the current route tests assert, so they stay green UNTOUCHED: `<svg viewBox`, `data-series="process_grade_rolling_N"`, `<polyline points=`, `class="process-grade-rolling-line metric-process_grade_rolling_N"`, the `A=4`/`F=0` axis labels, `<circle `, the `data-empty-state` empty render, the decoupled badge text (table), and the no-matplotlib assertion (spec §3.3/§5.1). The plan MUST enumerate WHICH existing tests stay green untouched vs which get NEW assertions added.

---

## §2 Production anchors + risks (BINDING; re-grep at writing-plans STEP 0)
- The VM currently normalizes each series independently then draws ALL into one box (`_y_axis_bounds_for_metric` + `_polyline_y`) -- the redesign replaces this with per-panel grouping (recommend the grouped-tuples shape: `grade_series` / `rate_series` / `cost_series`; `_total` -> table-only) + per-panel SVG-height constants (`grades_svg_height=360`, `rate_svg_height=160`, `cost_svg_height=160`); the shared `_polyline_x` is UNCHANGED.
- The CSS two-class specificity (`.process-grade-rolling-line.metric-entry_grade_rolling_N`) is REQUIRED -- a single `.metric-*` class is EQUAL specificity to `.process-grade-rolling-line`, so source order would decide (Codex R1-M1). The base `.process-grade-rolling-line { stroke: var(--accent); }` rule STAYS (the A-6 test asserts it).
- The cost-axis all-zero `[0,1]` fallback (Codex R1-M2): `_polyline_y` centers the line when `y_max==y_min`, so `[0,0]` would float a zero-cost line mid-panel with degenerate `0.0/0.0/0.0` labels; `[0,1]` maps zero to the baseline with non-degenerate labels.
- The segmented-polyline (F-3 None-gap splitting) + `is_drawable` gate run UNCHANGED per series, within each panel's bounds.
- ASCII discipline: the legend (`process / entry / management / exit` -- slash, NOT a middle-dot), the axis labels (`A=4 B=3 C=2 D=1 F=0`, `0.0 / 0.5 / 1.0`, `%.2f`), and the under-floor caption (`... >=5 effective samples` -- `>=`, NOT the glyph) are ASCII.
- Nav-date: `build_reviews_pending_vm` adds `session_date=last_completed_session(datetime.now()).isoformat()` + a local `from swing.evaluation.dates import last_completed_session` (mirror `build_review_vm:1351`; `datetime` already module-level). NO new `vm.foo` -> the 5-VM rule is not triggered.

---

## §3 Slice structure (from the spec §7; the plan decomposes into TDD tasks)
Two independent slices (Slice A ships first; lowest risk):
- **Slice A -- the nav-date fix** (trivial): the one-line `build_reviews_pending_vm` change (`session_date=last_completed_session(...).isoformat()` + the local import) + the render-assertion test (pre-fix `""` vs post-fix ISO date, per `feedback_regression_test_arithmetic`). Independent of the chart; unblocks the operator's reported topbar bug.
- **Slice B -- the chart redesign** (4 tasks): **B1** the `--series-*` theme tokens (`:root` + `body.dark`) + the per-series two-class CSS (additive; the existing 4 assertions stay green) -- TDD via `tests/web/test_app_css_process_grade.py`; **B2** the VM per-panel grouping + the 0-anchored cost bounds (+ the all-zero `[0,1]` fallback) + the panel SVG-height constants -- TDD via the VM tests; **B3** the template: split the one `<svg>` into 3 panels (GRADES 360 / RATE 160 / COST 160) + the legend + the under-floor captions, preserving the GRADES panel's exact existing hooks (§1.2) -- TDD via the route tests (the new `data-panel`/axis/legend assertions + the preserved ones); **B4** the structural + VM + CSS test additions enumerated in spec §5.1. The operator browser gate (§L6) runs at the end of Slice B (+ a quick nav-date check at Slice A).

---

## §4 OUT OF SCOPE (do not plan into V1)
- Any change to the metric COMPUTATIONS (L1) -- presentation only.
- matplotlib / a JS charting library / a client-side renderer (L2).
- A schema change / migration (L3 -- v24 holds).
- New metrics, other metrics surfaces, the `/metrics` overview card, the failure-mode analysis tile.
- Charting `_total` (OQ-3 = table-only); a `not_a_loss`-style sentinel; a calendar X axis; per-trade markers in the rate/cost panels (V2).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **L2 inline-SVG** -- no matplotlib/JS-lib; the no-matplotlib route test stays green; 3 hand-rolled `<svg>` panels + the table.
2. **Test-preservation (§1.2)** -- the plan names WHICH existing route tests stay green UNTOUCHED (the GRADES panel preserves the exact hooks) vs which gain NEW assertions; no existing test is silently broken or weakened.
3. **CSS two-class specificity (R1-M1)** -- the per-series override wins by specificity, not source order; the base `--accent` rule stays.
4. **Cost-axis (R1-M2)** -- 0-anchored; the all-zero `[0,1]` fallback (zero at baseline, non-degenerate labels); a discriminating test.
5. **Incommensurability actually fixed** -- each series renders against a scale it belongs to (not just restyled).
6. **L4 invariants** -- A-6 `var(--accent)` (additive tokens); the suppression floor + markers; the decoupled badges (table); the table; the under-floor captions make the default state witnessable.
7. **Nav-date** -- `last_completed_session` (NOT `action_session_for_run`); a render test distinguishing pre/post; no new `vm.foo`.
8. **L3 no schema; ASCII (#16/#32)**; Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §6 Deliverable shape
**Plan at `docs/superpowers/plans/2026-06-03-process-grade-trend-redesign-plan.md`** (mirror the prior plan format): a 2-slice TDD task list, each task with (a) the failing test (file + assertion + the pre-fix-vs-post-fix value check), (b) the minimal implementation, (c) the commit message stem, (d) the locks/gotchas it touches. Include the test-preservation enumeration (§1.2), the operator browser gate (Slice B), and a task-count + line estimate. **Target ~500-800 lines.** Commit stem: `docs(pgt-redesign-plan): writing-plans <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a spec file:line no longer matches the live tree, TRUST the tree + re-grep (main is now `bdde2aa5`+).
- If the redesign seems to need matplotlib / a JS chart lib, STOP -- L2 (inline SVG only).
- If it seems to need a metric-computation or schema change, STOP -- presentation-only (L1) / no schema (L3).
- If an existing route test would break, STOP -- the GRADES panel must preserve its exact hooks (§1.2); adapt the plan, do not weaken the test.
- HOLD THE LINE: small-multiples (3 panels); the two-class CSS specificity; the 0-anchored cost + `[0,1]` fallback; the nav-date uses `last_completed_session`; the operator browser-witness is binding.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form + STDIN-pipe (verify `codex --version`).
- This is WRITING-PLANS ONLY -- the plan + per-task tests; do NOT write code, do NOT enter executing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `process-grade-trend-redesign-writing-plans`. Dir `.worktrees/process-grade-trend-redesign-writing-plans/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `bdde2aa5`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged spec). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. NO isolated venv + NO live-DB concern (presentation-only; no migration) -- but still do NOT run a connecting `swing` command against the operator's live DB unnecessarily.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix + stdin-pipe form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); plan line + task count per slice; the OQ resolutions reflected (all 5 LOCKed); L1-L6 verification + the §1.2 test-preservation enumeration; Codex Majors accepted (ZERO preferred); the operator browser gate enumerated; schema verdict (NONE -- v24 holds); ZERO Co-Authored-By confirmation; worktree teardown status; executing-plans dispatch-readiness + the slice sequencing (A before B).

---

*End of brief. Process-grade-trend chart redesign + the reviews nav-date fix writing-plans dispatch (the THIRD Phase-15 arc; presentation-only) -- turn the merged, Codex-converged brainstorm spec into a TDD-task plan across 2 slices: Slice A the one-line nav-date fix (`last_completed_session`), Slice B the small-multiples chart (3 inline-SVG panels GRADES [0,4] / RATE [0,1] / COST [0,max] 0-anchored per_trade-only; distinct `--series-*` theme colors + legend via two-class CSS specificity; the all-zero cost `[0,1]` fallback; under-floor captions). PRESERVE the existing route-test hooks (the GRADES panel keeps its exact markup), the A-6 theme stroke, the suppression floor, the decoupled badges, and the table. NO schema/lock/migration. The binding gate is an operator browser-witness (light/dark + the empty default + the fixed nav-date). OUTPUT: a plan the executing-plans phase can drive to a shipped feature.*
