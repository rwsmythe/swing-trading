# Process-Grade-Trend Chart Redesign (+ nav-date fix) -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the process-grade-trend-redesign executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged implementation plan -- redesign the `/metrics/process-grade-trend` chart to **small-multiples** (3 scale-separated inline-SVG panels) + the bundled `/reviews/pending` nav-date one-liner -- via `copowers:executing-plans` (wraps `subagent-driven-development`). TDD task-by-task (failing test -> minimal impl -> see pass -> commit), strictly Slice A then B1->B2->B3->B4. This is the THIRD commissioned **Phase 15** arc and the lightest: **presentation-only -- NO schema, NO migration, NO lock, NO live cutover, NO live-DB touch, NO isolated venv.**

**Plan (AUTHORITATIVE -- the task contract):** `docs/superpowers/plans/2026-06-03-process-grade-trend-redesign-plan.md` (516 lines; 5 TDD tasks [A1 + B1-B4]; merged to main `9d71c771`; single WSL Codex chain CONVERGED R3 `NO_NEW_CRITICAL_MAJOR`). Execute its tasks verbatim; **re-grep every cited file:line at task start** (the plan cites earlier HEADs; line numbers shift -- discipline #2).

**Spec (design rationale):** `docs/superpowers/specs/2026-06-03-process-grade-trend-redesign-design.md` (236 lines) -- consult for the WHY (esp. §3 the 3-panel structure; the orthogonality of the bug).

**Brief:** `docs/process-grade-trend-redesign-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the schwabdev-v3 + B-7 arcs CLOSED; pgt-redesign brainstorm+writing-plans SHIPPED+merged (`bdde2aa5`/`9d71c771`); main HEAD at this dispatch: see §8 (branch from it). ~7086 fast tests green on main; schema v24.

**Cumulative discipline:** the CLAUDE.md **Web/HTMX/forms** gotchas BINDING (the session-anchor read/write gotcha for the nav-date; the shared-`base.html.j2` 5-VM rule [NOT triggered]; matplotlib-mathtext N/A -- inline SVG); the **ASCII #16/#32** discipline for the SVG/legend/caption strings; ~700+ cumulative ZERO Co-Authored-By; **Schema v24 UNCHANGED** (NO migration).

**Expected duration:** ~2-4 hours executing + a Codex chain to convergence. One executing-plans cycle, single Codex chain at end.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief + the plan.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- WSL fallback (MCP DEAD -- do NOT attempt).** USE EXACTLY: `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'` -- the PATH prefix is REQUIRED; PROVE liveness with `codex --version` -> `codex-cli 0.135.0`. **Pass the prompt via STDIN** (`cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`), NOT `"$(cat ...)"` (breaks on parens). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. `### Verdict`) to `.copowers-findings.md`; extract the verdict tail to a file to Read (do NOT `print()` -- cp1252 glyph crash). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.

---

## §1 LOCKed OQ resolutions + L1-L6 (BINDING; full detail in the plan §1-§2 / the writing-plans brief §1)
- **OQ-1** small-multiples, 3 stacked inline-SVG panels sharing one X-ordinal: GRADES `[0,4]` / RATE `[0,1]` / COST `[0,max]` 0-anchored. **OQ-2** distinct theme-aware `--series-*` colors + legend via a TWO-class CSS selector. **OQ-3** chart `mistake_cost_R_..._per_trade` ONLY (0-anchored; all-zero edge -> `[0,1]`); `_total` table-only. **OQ-4** nav-date = `last_completed_session(datetime.now()).isoformat()`. **OQ-5** redesign-only.
- **L1** presentation-only (metric computations READ-ONLY). **L2 (inline-SVG-only, HARD)** no matplotlib/JS-lib; the `does_not_use_matplotlib_or_external_chart_lib` route test STAYS GREEN. **L3** NO schema (v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24; no migration; no `swing/data`/`swing/trades` write). **L4** preserve the A-6 `var(--accent)` (additive `--series-*` tokens -- the existing 4 CSS assertions stay green), the >=5-sample suppression floor + the `process_grade` markers, the decoupled badges (in the TABLE), the table. **L5** nav-date uses `last_completed_session`. **L6** the binding gate is the operator browser-witness (§3).

### §1.1 The CRITICAL test-preservation contract (plan §3 -- the #1 risk)
The GRADES panel MUST keep the EXACT hooks the current route tests assert, so the **9 route + 11 VM + 5 segment + 1 CSS tests stay GREEN UNTOUCHED** (`<svg viewBox`, `data-series="process_grade_rolling_N"`, `<polyline points=`, `class="process-grade-rolling-line metric-process_grade_rolling_N"`, `A=4`/`F=0`, `<circle `, `data-empty-state`, the n=2 `"<polyline" not in r.text` trap [captions are `<text>`, swatches `<rect>`], the no-matplotlib assertion). New assertions are ADDITIVE. Plan §3 enumerates the exact stay-green-vs-new split -- follow it; do NOT weaken any existing assertion.

---

## §2 Slice execution order (STRICT A -> B1 -> B2 -> B3 -> B4; plan tasks)
- **Slice A -- the nav-date fix** (A1; ships first, independent): `build_reviews_pending_vm` stamps `session_date=last_completed_session(datetime.now()).isoformat()` + a local `from swing.evaluation.dates import last_completed_session` (mirror `build_review_vm:1351`). A frozen-clock render test (pre-fix `""` vs post-fix ISO date). No new `vm.foo` -> the 5-VM rule is not triggered.
- **Slice B -- the chart redesign** (B1->B2->B3->B4, HARD order): **B1** the 4 `--series-*` tokens (`:root` + the combined `html.dark, body.dark` block) + the two-class per-series stroke rules + the legend-swatch fill rules (additive; the existing 4 A-6 CSS assertions stay green); **B2** the VM per-panel grouping (`grade_series`/`rate_series`/`cost_series`; `rolling_series` [all 7] UNCHANGED) + the 0-anchored cost bounds + the `[0,1]` all-zero fallback (`_polyline_y` centers when `y_max==y_min` -- the rationale) + panel-height constants + `rate_axis_labels`/`cost_axis_labels` + an additive `__post_init__` group validation (use the stub-first RED to avoid an ImportError false-fail); **B3** the template: split the single `<svg>` into 3 panels + the legend + the under-floor captions (ASCII `>=5`, NOT the glyph; raw-text safe -- not HTML-escaped `&gt;`) + the cost caption, PRESERVING the GRADES panel's exact hooks (§1.1); **B4** the structural sweep + the zero-regression green-bar verification. B3 consumes B2's VM fields + B1's CSS tokens -- the order is hard.

---

## §3 The operator browser-witness gate (BINDING -- L6; PRE-MERGE)
The chart is a VISUAL change; TestClient asserts structure only. **The gate is operator-driven and runs BEFORE the orchestrator merges** (memory `feedback_visual_gate_both_render_and_browser`):
1. **Implementer (pre-return):** all TDD via TestClient (structural). DOCUMENT the gate steps. Do NOT run the live browser gate yourself; do NOT merge.
2. **At orchestrator QA:** the orchestrator runs the BRANCH `swing web` from the worktree on a NON-default port (`python -m swing.cli web --port 8081`) -- SAFE (presentation-only; NO migration, so connecting to the live DB does NOT mutate it) -- and the operator drives a real browser through:
   - **Legibility, light + dark:** each panel reads against its own labeled scale; NO plunge-lines; the 4 grade colors are distinguishable + the legend is correct; dark mode shows all lines (the `--series-*` + `--accent` tokens resolve).
   - **The empty/under-floor DEFAULT state** (the operator's live DB likely has <5 reviewed trades -> this IS the default): axes + `process_grade` markers + the under-floor captions render -- NO blank box (memory `feedback_seeded_gate_masks_default_state`).
   - **`/reviews/pending`** shows a non-empty topbar date (the `last_completed_session` ISO date).
3. **Merge is BLOCKED until the operator confirms all three.** After the gate, the orchestrator kills the branch server by PID (`Get-NetTCPConnection -LocalPort 8081` -> `Stop-Process -Force`) + verifies the port is free (memory `feedback_taskstop_does_not_kill_detached_server`) BEFORE merging.

---

## §4 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Test-preservation (§1.1)** -- the GRADES panel keeps its exact hooks; the enumerated existing tests stay green UNTOUCHED; no assertion weakened; new assertions additive.
2. **L2 inline-SVG** -- no matplotlib/JS-lib; the no-matplotlib route test stays green; 3 hand-rolled `<svg>` panels + the table.
3. **The two-class CSS specificity** (`.process-grade-rolling-line.metric-<name>`) wins by specificity, not source order; the base `var(--accent)` rule stays; the `--series-*` tokens are defined under BOTH `:root` and `html.dark, body.dark` (block-scoped assertion).
4. **The cost-axis** -- 0-anchored; the all-zero `[0,1]` fallback (zero at baseline, non-degenerate labels; the Y-baseline discriminator).
5. **Incommensurability fixed** -- each series renders against a scale it belongs to (not just restyled); `_total` is table-only (not charted).
6. **L4 invariants + under-floor captions** make the default state witnessable; the decoupled badges (table) + the suppression floor + the markers + the table survive.
7. **Nav-date** -- `last_completed_session` (NOT `action_session_for_run`); the frozen-clock render test distinguishes pre/post; no new `vm.foo`.
8. **L3 no schema** (`EXPECTED_SCHEMA_VERSION == 24`; no `swing/data`/`swing/trades`/migration diff); **ASCII (#16/#32)** on the legend (`process / entry / management / exit`), the under-floor caption (`>=5`), the axis labels; Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

---

## §5 TDD + commit discipline
- Per task: failing test FIRST with the pre-fix-vs-post-fix value check (memory `feedback_regression_test_arithmetic`; the plan bakes in the discriminators -- the cost-axis Y=120-vs-72 baseline + the stub-first RED for the cost helper); see it fail; minimal impl; see it pass; commit. Conventional messages (`fix(web):`/`feat(web):`/`test(web):`).
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph PLAIN PROSE; verify `git log -1 --format='%(trailers)'` is `[]` before any push.
- Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit. If mid-batch tool cancellations recur, switch to single sequential tool calls + re-Read before each Edit.

---

## §6 If you get stuck
- Plan file:line no longer matches the tree -> TRUST the tree + re-grep.
- An existing route test would break -> STOP; the GRADES panel must preserve its exact hooks (§1.1); adapt, do not weaken.
- The redesign seems to need matplotlib / a JS lib -> STOP (L2). A metric-computation or schema change -> STOP (L1/L3).
- HOLD THE LINE: small-multiples (3 panels); the two-class CSS specificity; the 0-anchored cost + `[0,1]` fallback; the nav-date `last_completed_session`; the operator browser-witness is binding + PRE-merge.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix + STDIN-pipe (verify `codex --version`).
- DO NOT merge (orchestrator) and DO NOT run the live browser gate yourself (orchestrator+operator at QA).

---

## §7 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `process-grade-trend-redesign-executing`. Dir `.worktrees/process-grade-trend-redesign-executing/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `9d71c771`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the merged plan). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). NO isolated venv (presentation-only; no shared-dep change). NO live-DB migration concern (no schema change) -- but the live browser gate is the ORCHESTRATOR's at QA, not yours.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix + stdin-pipe form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §8 Return report shape
Mirror the prior executing-plans return reports: final HEAD + per-task commit breakdown (A1 + B1-B4); the fast-suite result (count; cite it; note the baseline delta from the new tests); the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); per-task completion; the OQ resolutions reflected (all 5); L1-L6 verification + the §1.1 test-preservation confirmation (which existing tests stayed green untouched; no assertion weakened); Codex Majors accepted (ZERO preferred); the operator browser-gate runbook (documented for the orchestrator+operator PRE-merge gate); schema verdict (NONE -- v24 holds; the `git diff --stat` shows zero `swing/data`/`swing/trades`/migration changes); ZERO Co-Authored-By confirmation; worktree status (left intact for the orchestrator's pre-merge browser gate + merge); merge-readiness.

---

*End of brief. Process-grade-trend chart redesign + the reviews nav-date fix executing-plans dispatch (the THIRD Phase-15 arc; presentation-only) -- execute the merged Codex-converged plan: Slice A the one-line nav-date fix (`last_completed_session`), Slice B the small-multiples chart (B1 `--series-*` tokens + two-class CSS -> B2 VM per-panel grouping + 0-anchored cost + `[0,1]` fallback -> B3 the 3-panel template + legend + under-floor captions -> B4 the structural sweep). PRESERVE the existing route-test hooks (the GRADES panel keeps its exact markup -- the #1 risk), the A-6 theme stroke, the suppression floor, the decoupled badges, and the table. NO schema/lock/migration/live-DB. The binding gate is the operator browser-witness (light/dark + the empty/under-floor default + the fixed nav-date), driven by the orchestrator from the branch worktree BEFORE merge. OUTPUT: the merged-ready redesign, suite-green + Codex-converged.*
