# Process-Grade-Trend Chart Redesign (+ reviews-page nav-date fix) -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the process-grade-trend-redesign brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for a small **web/UI fix bundle** -- the THIRD commissioned **Phase 15** arc (after schwabdev-v3 `#20` + B-7 `#21`, both CLOSED). Two items, one cycle:
1. **PRIMARY (the design decision): redesign the `/metrics/process-grade-trend` chart.** Today it overlays 7 incommensurate rolling series on ONE grade-labeled y-axis (A=4..F=0): 4 grade lines [0,4] + a disqualifying-violation rate [0,1] + two UNBOUNDED `mistake_cost_R` lines [0,inf), each independently normalized onto the same SVG viewport -> reading any non-grade line against the A-F axis is meaningless ("plunge-lines"). Decide the right presentation WITHIN the existing inline-SVG-only constraint.
2. **BUNDLED (a trivial one-liner, no design): the reviews-page nav-date fix.** `/reviews/pending`'s shared topbar date renders blank because `build_reviews_pending_vm` never sets `session_date`. Pinned below; carry it as a small task in the same plan.

**Brief:** `docs/process-grade-trend-redesign-brainstorming-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the schwabdev-v3 + B-7 arcs CLOSED; main HEAD at this dispatch: see §8 (branch from it). ~7086 fast tests green; schema v24. This is the LIGHTEST Phase-15 arc yet -- **NO schema change, NO migration, NO lock, NO live cutover, NO live-DB touch** (pure web read-surface + a VM one-liner).

**Cumulative discipline:** the CLAUDE.md **Web/HTMX/forms** gotchas are BINDING (esp. the shared-`base.html.j2` 5-VM rule, the matplotlib-mathtext gotcha [N/A here -- the chart is inline SVG, NOT matplotlib], the session-anchor read/write gotcha for the nav-date fix); ~700+ cumulative ZERO Co-Authored-By; **Schema v24 UNCHANGED** (this arc adds NO migration -- confirm at brainstorm).

**Expected duration:** ~2-3 hours brainstorming + a Codex chain to convergence. Spec line target **~250-400 lines** (one focused UI design decision + a trivial bundled fix).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED -- a bare `command -v codex` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex`. PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` (+ the 2026-06-03 prefix-required correction) + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/2026-06-03-process-grade-trend-redesign-design.md`.

---

## §0 Read first (in this order; orchestrator-verified anchors -- re-grep at writing-plans per #2)
1. **THIS BRIEF end-to-end.**
2. **The chart surface (the primary item):**
   - Route: `swing/web/routes/metrics.py:216-231` (`metrics_process_grade_trend` -> `build_process_grade_trend_vm` -> `metrics/process_grade_trend.html.j2`). **§A.10 LOCK in its docstring `:221`: "Inline SVG ... NO matplotlib"; §I.6 LOCK `:225`: pure server-rendered HTML.**
   - VM: `swing/web/view_models/metrics/process_grade_trend.py` -- `build_process_grade_trend_vm` (`:454-519`); `_y_axis_bounds_for_metric` (`:315-335`: grades fixed [0,4], rate fixed [0,1], costs DATA-DRIVEN [min,max] -> unbounded); `_polyline_y` (`:240-260`); `_format_polyline_segments` (`:262-312`); `_build_rolling_display` (`:338`).
   - Template: `swing/web/templates/metrics/process_grade_trend.html.j2` -- single 800x360 `<svg>` (`:24-66`); grade-axis labels A=4..F=0 (`:31-37`); per-trade `<circle>` markers (`:39-51`); the 7 rolling `<polyline>`s (`:55-65`, `data-series=` + `class="process-grade-rolling-line metric-{name}"`); the per-metric TABLE (`:68-120`, all 7 metrics already shown tabular).
   - Metric matrix: `swing/metrics/process_grade_trend.py:68-76` (`PROCESS_GRADE_TREND_METRIC_CLASSES`: 4 grades "B"/BootstrapCI, 1 rate "A"/WilsonCI, `mistake_cost_R_..._per_trade` "B", `mistake_cost_R_..._total` "point"); grade encoding `GRADE_TO_NUMERIC` A=4..F=0 (`:58`); the >=5-effective-sample suppression floor; `mistake_cost_R` = `max(0, realized_R_if_plan_followed - actual_realized_R_effective)` (`swing/trades/review.py:189-196`; >=0, UNBOUNDED above).
3. **The nav-date fix (the bundled item):** `base.html.j2:69` renders `<span class="date">{{ vm.session_date }}</span>`; `build_reviews_pending_vm` (`swing/web/view_models/trades.py:1490`; `ReviewsPendingVM.session_date` defaults `""` at `:1459`) does NOT set `session_date`, unlike `build_review_vm:1351` (`session_date = last_completed_session(_dt.now()).isoformat()`). The fix is that ONE line (use `last_completed_session` -- the backward-looking TOPBAR anchor -- NOT `action_session_for_run`).
4. **CLAUDE.md -- the Web/HTMX/forms gotchas** (the shared-`base.html.j2` 5-VM rule; the session-anchor read/write gotcha -- `last_completed_session` for the topbar; ASCII #16/#32 for any new text) **+ the A-6 dark-mode fix** (the chart's stroke/fill use the theme-aware `var(--accent)` token -- a redesign MUST preserve theme-aware coloring; `tests/web/test_app_css_process_grade.py`). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines".
5. **Memory:** the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + `feedback_visual_gate_both_render_and_browser` (the operator browser-witness for both charts) + `feedback_seeded_gate_masks_default_state` (witness the empty/under-floor default too).

---

## §1 Pre-locked decisions + LOCKs (BINDING)
- **L1** Scope = the process-grade-trend chart redesign + the reviews-page nav-date one-liner ONLY. Do NOT change the underlying metric COMPUTATIONS (`swing/metrics/process_grade_trend.py` is consumed read-only -- the redesign is presentation-layer), do NOT add new metrics, do NOT touch other metrics surfaces.
- **L2 (the inline-SVG-only LOCK -- HARD)** the redesign STAYS inline-SVG + server-rendered HTML (the §A.10 / §I.6 LOCKs; the route test `test_process_grade_trend_does_not_use_matplotlib_or_external_chart_lib` asserts NO matplotlib / NO Chart.js / NO D3). Do NOT introduce matplotlib, a JS charting library, or a client-side renderer. Any redesign (separate panels / a secondary axis / table-emphasis) is hand-rolled inline SVG + the existing table.
- **L3** **NO schema change** (v24 holds; this is a web read-surface + a VM one-liner; NO migration, `EXPECTED_SCHEMA_VERSION` stays 24). NO `swing/trades/` or `swing/data/` write (the metric computations are read-only). Confirm at brainstorm.
- **L4** **Preserve the established chart invariants:** the A-6 theme-aware `var(--accent)` stroke/fill (dark-mode visibility); the >=5-effective-sample suppression floor + the per-trade markers; the DECOUPLED badge text elements (drawability_text / window-not-full / confidence-floor as SEPARATE elements, lesson #23); the per-metric TABLE (it already shows all 7 -- the redesign may LEAN on it). Whatever layout is chosen, these survive.
- **L5 (the nav-date fix)** use `last_completed_session(...).isoformat()` (the backward-looking topbar anchor that every other base-layout VM uses) -- NOT `action_session_for_run` (forward-looking -> would mismatch the other pages + silently blank on weekends per the session-anchor gotcha). One-line VM change + a render-assertion test (the topbar date is non-empty on `/reviews/pending`).
- **L6 (the binding gate)** an operator-witnessed BROWSER comparison: the redesigned chart renders legibly (no plunge-lines; each metric readable against a meaningful scale) in BOTH light + dark mode, AND the empty/under-floor default state is witnessed (memory `feedback_seeded_gate_masks_default_state`); the `/reviews/pending` topbar now shows the date matching the other pages. TestClient asserts structure (the SVG/panel elements, the non-empty date); the legibility judgment is the operator's.

---

## §2 Spec scope to design
### §2.1 The chart redesign (the design decision -- OQ-1)
Design the presentation that makes 7 incommensurate series legible within L2 (inline SVG only). Weigh AT LEAST these, with a recommendation:
- **Small-multiples (separate inline-SVG panels by scale):** a GRADES panel (the 4 grade lines on a shared [0,4] axis -- they ARE commensurate) + a RATE panel ([0,1]) + a COST panel (the two `mistake_cost_R` lines on a data-driven [0,max] axis). Each panel its own small SVG + its own axis labels. The most honest; establishes a small-multiples precedent (none exists today).
- **Primary grade chart + costs/rate to the table:** keep ONE chart of only the commensurate grade lines [0,4] (the headline "is my process improving"); demote the rate + the two unbounded costs to the existing table (they already live there). Simplest; loses the cost/rate trend-as-a-line.
- **Secondary axis / restyle within one SVG:** a right-hand axis for costs + dashing/legend to disambiguate. Hand-rolled-SVG-feasible but still cognitively busy; weakest at fixing incommensurability.
- **Table-only (drop the chart):** the table already shows all 7. Simplest; loses all trend visualization.
Define the chosen layout's SVG structure, the axis/label scheme per panel, the legend/series identification, the theme-aware coloring (per-series colors vs the single `--accent`), and how the suppression-floor / decoupled-badges / empty-state behave in the new layout.

### §2.2 The nav-date fix (§0.3 / L5)
The one-line `build_reviews_pending_vm` change + the render-assertion test. Trivial; no design.

### §2.3 Test + gate strategy
The chart structural tests (the new panel/axis elements; the no-matplotlib/no-JS-lib assertion still passes; theme-aware stroke preserved; the table still present; the empty/under-floor state); the nav-date render test; the operator browser gate (§L6).

---

## §3 Open questions (Codex surfaces; operator triage at writing-plans)
1. **OQ-1 the layout** -- small-multiples (recommend, if the operator wants to keep all series as trend lines) vs primary-grade-chart + table-for-the-rest vs secondary-axis vs table-only. **Operator-binding (the core UX call).**
2. **OQ-2 per-series color** -- distinct theme-aware colors per grade line (entry/mgmt/exit/overall) + a legend, vs the single `--accent` (current) with dashing. (Affects legibility; small.)
3. **OQ-3 cost-panel scale** -- the two unbounded cost lines: shared data-driven [0,max] axis, or `mistake_cost_R_total` (a sum, "point" class) demoted to the table while only `_per_trade` charts. (Note: `_total` is a running sum -- its trend may not belong on the same panel as the per-trade mean.)
4. **OQ-4 nav-date** -- confirm `last_completed_session` (recommend; matches the other pages) is the right topbar anchor for `/reviews/pending`.
5. **OQ-5 scope** -- is V1 the redesign only, or also any adjacent metrics-card affordance? (Recommend redesign-only.)

---

## §4 OUT OF SCOPE (do not design into V1)
- Any change to the metric COMPUTATIONS (`swing/metrics/process_grade_trend.py`) -- presentation-layer only (L1).
- matplotlib / any JS charting library / client-side rendering (L2).
- A schema change / migration (L3 -- v24 holds).
- New metrics, other metrics surfaces, or the `/metrics` overview card.
- The failure-mode analysis tile (that is the separate B-7-follow-on arc).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **L2 inline-SVG LOCK** -- the design introduces NO matplotlib / JS chart lib; the existing no-matplotlib route test still passes; the redesign is hand-rolled SVG + the table.
2. **Incommensurability actually fixed** -- the chosen layout means NO metric is read against a scale it doesn't belong to (the plunge-line bug is genuinely resolved, not just restyled).
3. **L4 invariants preserved** -- theme-aware `--accent` (dark-mode); the suppression floor; the decoupled badges (lesson #23); the table.
4. **L3 no schema / no compute change** -- presentation-only; v24 holds.
5. **The nav-date fix** -- `last_completed_session` (NOT `action_session_for_run`); the shared-`base.html.j2` rule respected; a render test asserts the non-empty date.
6. **The binding gate is the operator browser-witness** (both light/dark + the empty/under-floor default); TestClient declared structural-only.
7. ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape
**Design spec at `docs/superpowers/specs/2026-06-03-process-grade-trend-redesign-design.md`** (mirror the prior brainstorm spec format): §1 Architecture overview (the bug + the inline-SVG constraint) · §2 Pre-locked decisions + L1-L6 · §3 The chart redesign (the layout options + the recommendation + the chosen SVG structure) · §4 The nav-date fix · §5 Test strategy + the operator browser gate · §6 Schema impact (NONE -- v24 holds) · §7 Slice recommendation · §8 V1 simplifications + V2 candidates · §9 Operator decision items (the OQs) · §10 Cumulative discipline compliance · §11 Position note (third Phase-15 arc; presentation-only; the lightest).

**Target ~250-400 lines.** Commit stem: `docs(pgt-redesign-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a cited file:line no longer matches the live tree, TRUST the tree + re-grep.
- If the redesign seems to need matplotlib / a JS chart lib, STOP -- that violates L2 (inline SVG only); re-think within hand-rolled SVG + the table.
- If it seems to need a metric-computation change, STOP -- presentation-only (L1); the computations are read-only.
- If it seems to need a schema change, ESCALATE -- there is none (L3; v24 holds).
- HOLD THE LINE: inline-SVG-only; fix the incommensurability (not just restyle); preserve the A-6 theme-aware stroke + the suppression floor + the badges + the table; the nav-date uses `last_completed_session`; the operator browser-witness is binding.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify `codex --version`).
- This is BRAINSTORMING ONLY -- the design spec + OQs; do NOT write code, do NOT enter writing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `process-grade-trend-redesign-brainstorming`. Dir `.worktrees/process-grade-trend-redesign-brainstorming/`. **Branch from main HEAD = the commit that ADDS this brief** (the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. (NO live-DB concern -- this arc adds no migration; but still do NOT run a connecting `swing` command against the operator's live DB unnecessarily.)
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior brainstorm return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); spec line count + per-section; L1-L6 verbatim verification; the OQs resolved/deferred (flag OQ-1 the layout for the operator); the schema verdict (NONE -- v24 holds); Codex Majors accepted (ZERO preferred); V1 simplifications + V2 candidates; the inline-SVG-LOCK confirmation; the nav-date fix design; cumulative gotcha application (the web/form + session-anchor checklists); ZERO Co-Authored-By confirmation; worktree teardown status; writing-plans dispatch-readiness.

---

*End of brief. Process-grade-trend chart redesign + the reviews-page nav-date fix brainstorming dispatch (the THIRD Phase-15 arc; the lightest -- presentation-only, NO schema/lock/migration) -- design how to present 7 incommensurate process-grade-trend rolling series legibly WITHIN the inline-SVG-only LOCK (small-multiples by scale [recommend] vs primary-grade-chart + table vs secondary-axis vs table-only), preserving the A-6 theme-aware stroke + the suppression floor + the decoupled badges + the existing table; AND fix the `/reviews/pending` topbar blank date (`build_reviews_pending_vm` set `session_date = last_completed_session(...)`). The binding gate is an operator browser-witness (both light/dark + the empty default + the fixed nav-date). OUTPUT: a design spec the writing-plans phase can derive a plan from.*
