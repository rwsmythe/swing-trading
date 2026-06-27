# Phase 14 Sub-bundle 5 -- Metrics Overview -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan derived from the SB5 brainstorm spec. Plan at `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-5-metrics-overview-plan.md`. Decompose the spec into bite-sized TDD tasks with per-task acceptance criteria, file-level diff projections, test scope, an operator-witnessed render-gate runbook, and an executing-plans dispatch-readiness package. SB5 is the **FINAL** Phase 14 sub-bundle.

**Brief:** `docs/phase14-sub-bundle-5-metrics-overview-writing-plans-dispatch-brief.md` (this file).

**Commissioning context:** SB1 `e323339`; SB2 `27f8007` (v22); SB3 `edd098d` (v23); SB4 `31da4a5` (end-to-end); **SB5 brainstorm SHIPPED `3c18b81`** (spec 526 lines; genuine v2.0.2 WSL Codex CONVERGED R3, 11 majors fixed); housekeeping `3e82fbb`. Main HEAD at writing-plans dispatch: `3e82fbb`.

**Cumulative discipline:** ~690+ ZERO Co-Authored-By; **Schema v23 LOCKED -- SB5 introduces NO schema change** (OQ-5 LOCK: render-direct / inline-SVG; `chart_renders` is ticker/run-keyed so cached sparklines are structurally incompatible -> no v24 trigger); L2 LOCK preserved; read-mostly (reuse the existing metric computations).

**Expected duration:** ~2-3 hours writing-plans + a Codex chain run to convergence. Plan line target **~800-1400 lines** (a single overview enhancement; smaller than SB4).

**Skill posture:**
- Invoke `copowers:writing-plans` against this brief.
- **Codex chain count: SINGLE chain** (operator-LOCKed OQ-7). **Run to CONVERGENCE** (zero new crit/major; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`; may exceed 5 rounds; do NOT pad after convergence).
- **Codex transport -- copowers v2.0.2 WSL Codex CLI fallback (reads the worktree FROM DISK):** the MCP tools are DEAD in the VS Code extension -- do NOT attempt them. The `adversarial-critic` skill auto-routes to the WSL fallback. **Preferred: invoke `copowers:writing-plans` normally.** Direct: `wsl.exe bash -ilc` (INTERACTIVE login for the node22 PATH), `codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/<this-worktree> - < <promptfile>` (R1), `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; **note: `codex exec resume` REJECTS `-s` AND `-C`/`--cd` -- use only `-c sandbox_mode="read-only"`; pre-generate the diff on Windows since WSL can't resolve the worktree `.git` path**). See memory `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation`.
- Output: plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-5-metrics-overview-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF.**
2. **`docs/superpowers/specs/2026-05-30-phase14-sub-bundle-5-metrics-overview-design.md`** -- the brainstorm spec (526 lines; AUTHORITATIVE; Codex CONVERGED R3). All 15 sections; esp. §4 overview design, §5 sparkline contract (3 trend surfaces), §6 headline-stat contract (the EXACT verified accessors -- the 11 Codex majors), §7 sparkline-tech (OQ-1), §8 render path / schema (NO change), §9 decomposition, §13 OQs.
3. **`docs/phase14-sub-bundle-5-metrics-overview-brainstorming-dispatch-brief.md`** §1 LOCKs (L1-L9) + §0.5 the production anchors.
4. **CLAUDE.md** -- esp. **shared `base.html.j2` VM-field defaults on ALL base VMs** (the metrics VMs inherit `BaseLayoutVM`); session-anchor read/write (the metrics surfaces use backward-looking `last_completed_session` -- preserve); matplotlib mathtext (N/A if inline-SVG; relevant only if any matplotlib slips in -- it should NOT). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature verify; re-grep at plan time), **#4** (data-shape verify -- the per-surface series + thresholds).
5. **Production anchors** (ORCHESTRATOR-VERIFIED at brainstorm QA; re-grep at plan time per #2/#4):
   - **The index (ENHANCE):** `metrics_index` (`swing/web/routes/metrics.py:50`); `build_metrics_index_vm` (`swing/web/view_models/metrics/index.py:97` -- currently `(conn)`, **must widen to `(cfg, conn)`** per the Codex majors; per-surface builders need `cfg`); `MetricsIndexVM(BaseLayoutVM)` (`:91`); `_SURFACES` registry (`:36`); template `swing/web/templates/metrics/index.html.j2`.
   - **The 3 trend-bearing surfaces (sparkline targets; per-surface thresholds NOT uniform):** `capital_friction` (`compute_capital_friction:509` -> `trend_runs`; **PROVISIONAL flag, NOT a suppression flag**; threshold **5**), `identification_funnel` (`compute_identification_funnel:206` -> `trend_runs`; threshold **10**), `process_grade_trend` (`compute_process_grade_trend:524` -> `rolling_series`; **line-band** suppression). **`process_grade_trend` ALREADY builds an inline `<polyline>` (`RollingSeriesDisplay.svg_polyline_points`, `swing/web/view_models/metrics/process_grade_trend.py:70`)** -- the inline-`<polyline>` precedent to GENERALIZE for the sparkline helper.
   - **Headline accessors (the EXACT 11-Codex-verified fields; spec §6 is the binding list):** e.g. `expectancy_R`, `APLUS_COHORT`/`.expectancy`, `triggered_pct_text`/`triggered_ci`, `len(vm.cohorts)`, `row_suppressed`, etc. **Use spec §6 verbatim; re-grep each at plan time.**
   - **BaseLayoutVM:** `swing/web/view_models/metrics/shared.py:28` (session_date + banner/discrepancy fields; `MetricsIndexVM` already inherits it).
   - **Schema:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`). **Add NO migration.**
6. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (the WSL transport + the `resume` flag wrinkle), `feedback_codex_round_limit_suspended` (run to convergence), `feedback_commit_message_trailer_parse_hazard`, `feedback_visual_gate_both_render_and_browser` (the operator render gate; re-confirm for SB5).

---

## §1 LOCKs inherited (BINDING; DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs
- **Q1** sequencing = ... -> **metrics overview (THIS, LAST)**; **Q2** SERIAL; **Q5** no-JS static graphics; **Q6** operator browser-witnessed render gate; **Q7** SINGLE chain (operator-LOCKed OQ-7).

### §1.2 Brainstorm spec §2 + L1-L9 LOCKs
- **L1** scope = P14.N5 metrics overview ONLY (enhance the existing `/metrics` index; per-surface headline + sparkline-where-trend-exists; drill-down preserved). NO new metric computations; do NOT modify the 9 per-surface routes' DATA logic.
- **L2** read-mostly; reuse the existing `build_*_vm`/`compute_*` outputs (post-T-T4.SB.2 delimiter-aware correct); ZERO new computation / ZERO data-write. Escalate if a write/new-metric seems needed.
- **L3** **NO schema change** (OQ-5 LOCK; render-direct / inline-SVG; `chart_renders` ticker/run-keyed -> cached sparklines incompatible). `EXPECTED_SCHEMA_VERSION` stays 23; add NO migration.
- **L4** honesty floor -- ONLY the 3 trend surfaces get sparklines; the other 6 get a headline stat or honest suppressed/empty state; **each sparkline respects ITS OWN suppression threshold** (capital=5, funnel=10, process-grade=line-band) -- NOT a uniform constant.
- **L5** visual-gate discipline; the rendered overview is the BINDING operator-witnessed gate; ASCII text.
- **L6** render path: inline-`<polyline>` SVG (OQ-1) -> NO `_RENDER_LOCK` contention, NO matplotlib per-card cost. (If any matplotlib is proposed, HOLD -- OQ-1 LOCKed inline.)
- **L7** BaseLayoutVM contract preserved on the enhanced `MetricsIndexVM`; new fields get safe defaults across the base contract.
- **L8** the existing metrics pages are pure server-rendered HTML (no HTMX) -- keep the overview that way unless a lazy-load is justified (OQ-6 LOCKed eager). If any HTMX is introduced, the trinity applies.
- **L9** SB5 is the LAST sub-bundle -- the plan/return-report notes Phase 14 close-out readiness (all 5 merged + the Sec 9.1 Q6 cross-sub-bundle integration review + the banked close-out punch-list in phase3e-todo).

### §1.3 Operator-LOCKed OQ dispositions (operator-paired triage 2026-05-30; BINDING)

| OQ | LOCKed disposition |
|---|---|
| **OQ-1 sparkline tech** | **Inline `<polyline>` SVG** (generalize the existing `process_grade_trend.svg_polyline_points` approach). NOT matplotlib. No `_RENDER_LOCK`, no per-card figure cost, no-JS/static. |
| **OQ-2 breadth** | Sparkline on the **3 trend-bearing surfaces ONLY** (capital_friction, identification_funnel, process_grade_trend); the other 6 get a headline stat + honest suppressed state. |
| **OQ-3 route** | **Enhance `/metrics` in place** (the existing index is the landing). |
| **OQ-4 headline selectors** | Use the spec §6 EXACT verified accessors for all 9; **finalize the per-surface headline figure at writing-plans** (re-grep each). |
| **OQ-5 render path / schema** | **Render-direct / inline; NO cache; NO schema** (Codex-resolved). |
| **OQ-6 eager vs lazy** | **Eager** render (inline-`<polyline>` is cheap). |
| **OQ-7 Codex chain count** | **SINGLE chain** (run to convergence). |

---

## §2 Architectural surface for the plan (BINDING substrate)

### §2.1 Per-task slicing (plan §G; the spec §9 decomposition -- single executing-plans bundle, ~4 tasks; 3-5 commits/task)
- **T-5.1 inline-`<polyline>` sparkline helper** -- a pure helper that builds an inline `<polyline>` SVG (points string + a small `<svg>` fragment) from a numeric series + dimensions; threshold-aware (returns a suppressed sentinel when the series is below the surface's own threshold). Generalize the existing `process_grade_trend.svg_polyline_points` pattern (NO matplotlib, NO `_RENDER_LOCK`). ASCII-only. Tests: known series -> expected points; degenerate/empty/below-threshold -> suppressed; single-point -> no fabricated line.
- **T-5.2 `MetricsIndexVM` enhancement** -- widen `build_metrics_index_vm(conn)` -> `(cfg, conn)`; per-surface card data: headline stat (spec §6 exact accessors, all 9) + sparkline (the 3 trend surfaces via T-5.1, each with ITS OWN threshold 5/10/line-band) + suppressed_reason; preserve the `BaseLayoutVM` fields. Reuse the existing `build_*_vm`/`compute_*` outputs (no re-derivation). Tests: per-surface headline value; sparkline present on the 3 / absent on the 6; threshold suppression per surface; BaseLayoutVM fields populated.
- **T-5.3 route + template enhancement** -- `metrics_index` passes `cfg` to the widened builder; `metrics/index.html.j2` renders the card grid (label + headline + inline-`<polyline>` sparkline where present + honest suppressed state + the existing drill-down links). Tests: response contains the headline stats + the 3 inline `<polyline>` fragments + the drill-down links; the 6 non-trend cards render their headline + suppressed-state (no `<polyline>`).
- **T-5.4 closer + operator render gate** -- full suite + ruff; L2 source-grep continued-pass; the operator-witnessed render-gate runbook (§2.3); the Phase 14 close-out readiness note (L9); return report.

### §2.2 Per-task acceptance criteria (plan §G.X.acceptance)
Files modified/added (exact paths); functions/VMs added + signatures verified (#2); discriminating tests (name + assertion shape); per-task LOCK/OQ/discipline preservation; the EXACT spec §6 accessor per surface (re-grep at plan time, #4).

### §2.3 Operator-witnessed render gate (plan §I)
The BINDING gate is the RENDERED overview in a real browser (Q6). Steps: S1 suite + ruff; S2 schema = NO migration (`schema_version=23`); S3 the `/metrics` overview renders -- all 9 cards with headline stats; the 3 trend cards show inline-`<polyline>` sparklines (suppressed honestly below threshold); the 6 non-trend cards show headline + suppressed state; drill-down links work. DB-scriptable where possible; the prior-sub-bundle fallback (operator-driven browser + orchestrator DB-side probes; OR orchestrator renders the page + reads it) applies. Re-confirm the gate split with the operator at executing-plans.

### §2.4 Codex single-chain + schema (plan §J + §K)
- SINGLE chain at end (OQ-7); run to convergence (no fixed cap).
- Plan §K: **NO new migration.** `EXPECTED_SCHEMA_VERSION` stays 23. Assert ZERO `00XX` added + the render-direct/inline linkage that keeps it schema-free.

---

## §3 Residual OQs (Codex SHOULD lock in the plan)
1. The exact per-surface headline figure (OQ-4; spec §6 accessors -- re-grep each at plan time).
2. The sparkline helper API (series in -> points/`<svg>` out; dimensions; the per-surface threshold wiring 5/10/line-band).
3. The suppressed-state presentation (text/empty for below-threshold trend surfaces + the 6 non-trend surfaces).
4. Commit cadence preface (§G.0; cascade audit each task).

---

## §4 OUT OF SCOPE (do not plan)
- Any new metric computation / surface; changes to the 9 per-surface routes' data logic; SB1-SB4 surfaces; the v22/v23 substrate; ANY schema/migration (L3); a new data-write path (L2); matplotlib sparklines (OQ-1 LOCKed inline); JS charting (Q5); the SB5.5 Schwab items + the close-out polish batch + B-7 (sequenced separately per the phase3e-todo punch-list); Phase 15+; production code NOT in the plan's file map.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. Signature/data-shape verify (#2/#4) -- `build_metrics_index_vm` widening; the spec §6 exact accessors per surface; the 3 trend series + their NON-uniform thresholds (5/10/line-band); re-grep at plan time.
2. Read-mostly (L2) -- ZERO new computation/write; reuse existing outputs; honesty floor (no fabricated sparklines; per-surface threshold).
3. NO schema (L3) -- assert ZERO migration; the render-direct/inline linkage documented.
4. Inline-`<polyline>` (OQ-1) -- no matplotlib, no `_RENDER_LOCK`; ASCII; degenerate-series handling.
5. BaseLayoutVM (L7) + shared-`base.html.j2` field defaults; backward-looking session anchor preserved.
6. Metrics-wiring correctness -- the overview consumes the post-T-T4.SB.2 (delimiter-aware) values; no re-derivation.
7. L2 Schwab source-grep continues passing; ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose). The return report EVIDENCES the chain ran genuinely via WSL.

---

## §6 Deliverable shape
Plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-5-metrics-overview-plan.md`: §A Goals/non-goals · §B File map · §C Surface integration · §D Out-of-scope · §E LOCK reverification (Sec 9.1 + L1-L9 + the §1.3 OQ dispositions) · §F Discipline hooks · §G Per-task tasks (T-5.1..T-5.4) + §G.0 cadence · §H Test surface (sum-check) · §I Operator render-gate runbook · §J Codex single-chain placement · §K Schema (NO change) · §L Fixtures · §M Forward-binding lessons · §N Self-review · §O Phase 14 close-out readiness. **Target ~800-1400 lines.** Commit stem: `docs(phase14-sub-bundle-5-plan): writing-plans -- ...` (final `-m` paragraph plain prose).

---

## §7 If you get stuck
- If a spec §6 accessor no longer matches production at plan time, ESCALATE / re-grep (the 11 majors were Codex-verified at brainstorm but re-confirm).
- If the overview appears to need a new metric computation, a data-write, or a schema change, ESCALATE -- L2/L3 forbid all three.
- HOLD THE LINE: inline-`<polyline>` not matplotlib (OQ-1); no-JS (Q5); single chain run-to-convergence (OQ-7); the per-surface NON-uniform thresholds; the honesty floor (3 surfaces, no fabricated sparklines).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools; use the WSL fallback (`codex exec resume` rejects `-s`/`-C`).
- DO NOT widen to SB5.5 / the close-out batch / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §8 Return report shape
Mirror prior writing-plans return reports (15 items): final HEAD + commit breakdown (Codex round attribution); Codex chain + convergent shape (EVIDENCE genuine via WSL); plan line count + per-section; pre-locked decisions verbatim (Sec 9.1 + L1-L9 + the §1.3 OQ dispositions); residual OQs locked; Codex Major accepted (ZERO preferred); per-task acceptance summary; test surface (sum-check); forward-binding lessons for executing-plans; schema impact verdict (NO change); cumulative gotcha application; worktree teardown; ZERO Co-Authored-By (`%(trailers)`); CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness summary + the Phase 14 close-out readiness note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-5-metrics-overview-writing-plans`. Dir `.worktrees/phase14-sub-bundle-5-metrics-overview-writing-plans/`. Branch from main HEAD `3e82fbb`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain (OQ-7), run to convergence via the WSL Codex fallback (copowers v2.0.2; MCP dead).
- **Expected duration:** ~2-3 hours writing-plans + a Codex chain run to convergence.

---

*End of brief. Phase 14 Sub-bundle 5 (FINAL) writing-plans dispatch -- produce a per-task implementation plan from the 526-line brainstorm spec (enhance the existing `/metrics` index: per-surface headline stats [exact spec §6 accessors] + inline-`<polyline>` sparklines on the 3 trend-bearing surfaces with their NON-uniform thresholds 5/10/line-band; render-direct; NO schema; ~800-1400 lines; SINGLE Codex chain to convergence). The 7 operator-LOCKed OQ dispositions are in §1.3 (OQ-1 = inline-`<polyline>`, NOT matplotlib); HOLD THE LINE. The rendered overview is the BINDING operator-witnessed gate. After SB5: SB5.5 (Schwab) + close-out batch + B-7 + Phase 14 close-out review. OUTPUT: an implementation plan the executing-plans phase can dispatch directly.*
