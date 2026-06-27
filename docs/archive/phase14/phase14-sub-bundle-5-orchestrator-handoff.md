# Phase 14 Sub-bundle 5 -- Orchestrator Handoff (SB5 writing-plans in flight onward)

**Audience:** Fresh Claude Code instance taking on the Phase 14 orchestrator role at the **SB5 writing-plans → executing-plans boundary**. The prior orchestrator handed off mid-flight (SB5 writing-plans dispatched + working) as context reached the <30% trigger (operator-directed 2026-05-30).

**Clean boundary:** **SB5 brainstorm SHIPPED end-to-end at `3c18b81`** (spec 526 lines; genuine v2.0.2 WSL Codex CONVERGED R3). **SB5 writing-plans is DISPATCHED + IN FLIGHT** (brief committed at `3d022d4`; inline prompt given to the operator; the implementer is working in a worktree). **main = `3d022d4`.** Your first action: **await/QA the SB5 writing-plans return**, then drive writing-plans-merge → executing-plans → operator-witnessed render gate → SB5.5 → close-out.

---

## Bootstrap (read in order)
1. **CLAUDE.md** line-3 "Current state" (SB1-SB4 SHIPPED end-to-end; SB5 brainstorm SHIPPED; the SB5.5 + close-out tail) + the compressed Gotchas. The "Expansion #N" process disciplines live in [`docs/orchestrator-context.md`](docs/orchestrator-context.md) §"Pre-Codex review + brief-authoring disciplines" -- read BOTH.
2. **`docs/phase3e-todo.md`** top entries: **#6** (SB5 brainstorm SHIPPED -- the 7 LOCKed OQs + corrections) + **#5** (the consolidated Phase 14 close-out + SB5.5 punch-list -- the canonical tail tracker). Then #4 (SB4 end-to-end) for the gate/gate-fix precedent.
3. **`docs/phase14-sub-bundle-5-metrics-overview-writing-plans-dispatch-brief.md`** -- the brief the in-flight implementer is executing (the 7 OQ LOCKs §1.3; the ~4-task decomposition; the production anchors). **QA the return against THIS.**
4. **`docs/superpowers/specs/2026-05-30-phase14-sub-bundle-5-metrics-overview-design.md`** -- the SB5 brainstorm spec (526 lines; §6 exact headline accessors; §5 sparkline contract; the 3-of-9-surfaces + non-uniform-thresholds findings).
5. **`docs/phase14-commissioning-brief.md`** Sec 2.4 (metrics overview) + Sec 9.1 LOCKs (Q1/Q2/Q5/Q6/Q7).
6. **Memory** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\` -- esp. `feedback_no_false_green_claim`, `feedback_orchestrator_performs_merge`, `feedback_orchestrator_qa_implementer_product`, `feedback_commit_brief_before_inline_prompt`, `feedback_always_provide_inline_dispatch_prompt`, `feedback_pause_means_pause`, `feedback_commit_message_trailer_parse_hazard`, `feedback_codex_round_limit_suspended`, `feedback_copowers_codex_mcp_windows_launcher`, `feedback_wsl_native_codex_invocation`, `feedback_visual_gate_both_render_and_browser`, `feedback_taskstop_does_not_kill_detached_server`.

## Phase 14 state

| Sub-bundle | State |
|---|---|
| 1 data-wiring · 2 temporal-log (v22) · 3 chart-surface (v23) · 4 review+journal | SHIPPED end-to-end (`e323339`/`27f8007`/`edd098d`/`31da4a5`) |
| **5 metrics overview (P14.N5)** | **brainstorm SHIPPED `3c18b81`; writing-plans IN FLIGHT** |
| SB5.5 Schwab-focused (A-3 + P14.N7) | NEW; after SB5 (operator-decided) |
| close-out polish batch + B-7 final touch + close-out review | after SB5.5 |

**main = `3d022d4`.** ~690+ commits ZERO `Co-Authored-By`. **Schema v23 LOCKED** (SB5 adds NO schema; OQ-5 LOCK). L2 LOCK preserved. Phase 14 lands at v23.

## SB5 scope + the 7 LOCKed OQ dispositions (BINDING; do NOT re-litigate)
Enhance the EXISTING text-only `/metrics` index into a graphics-driven overview: per-surface headline stat (all 9) + sparkline on the **3 trend-bearing surfaces ONLY** (capital_friction/identification_funnel/process_grade_trend). Read-mostly; reuse existing `build_*_vm`/`compute_*`; NO schema.

| OQ | LOCKed |
|---|---|
| OQ-1 | **inline-`<polyline>` SVG** (generalize `process_grade_trend.svg_polyline_points`; NOT matplotlib; no `_RENDER_LOCK`) |
| OQ-2 | 3 trend surfaces only (honesty floor) |
| OQ-3 | enhance `/metrics` in place |
| OQ-4 | spec §6 exact headline accessors (finalize at writing-plans) |
| OQ-5 | render-direct, no cache, no schema |
| OQ-6 | eager render |
| OQ-7 | single Codex chain |

**Key corrections (Codex-verified):** `build_metrics_index_vm(conn)` MUST widen to `(cfg, conn)`; thresholds are NON-uniform (capital=5, funnel=10, process-grade=line-band); `/metrics` already exists (ENHANCEMENT, not greenfield).

## First action + forward path
1. **Await/QA the SB5 writing-plans return** (`feedback_orchestrator_qa_implementer_product`): branch HEAD + 3-N commits ZERO `Co-Authored-By`; docs-only (plan + nothing else); plan ~800-1400 lines; NO `0024`/schema; the §1.3 OQ dispositions honored; the chain ran genuinely via WSL (the findings are gitignored now -- read the on-disk `.copowers-findings.md` in the worktree to verify; see below). Spot-check the `build_metrics_index_vm` widening + the non-uniform thresholds.
2. **Merge** `--no-ff` (QA-pass + convergence IS the trigger; do NOT ask "shall I merge"; `feedback_orchestrator_performs_merge`) + push + worktree/branch teardown + housekeep (CLAUDE.md line-3 + phase3e-todo top entry).
3. **Author the SB5 executing-plans dispatch brief** (mirror `docs/phase14-sub-bundle-4-review-journal-ux-executing-plans-dispatch-brief.md`) + commit BEFORE the inline prompt (`feedback_commit_brief_before_inline_prompt`) + provide the inline prompt.
4. SB5 executing-plans ship → QA → **operator-witnessed RENDER gate** (the `/metrics` overview in a real browser; see gate mechanics below) → merge → **re-run the suite on the MERGED HEAD and READ it before claiming green** (`feedback_no_false_green_claim` -- BINDING) → reinstall `swing` from main → housekeep.
5. **Then the Phase 14 tail (phase3e-todo #5):** SB5.5 (Schwab: A-3 daily-bar web wiring + P14.N7 checker-thread resilience -- its own copowers cycle; L2-LOCK central) → close-out polish batch (P14.N1 dashboard thumbnails + A-1 market_weather 200MA + A-2 theme2 vcp crowding + A-4 `_bulz_*` rename + the group-(a) minor advisories) → **B-7 operator failure-mode classification (final touch)** → **Phase 14 close-out review (Sec 9.1 Q6: all merged + operator browser-witnessed cross-sub-bundle integration)** → CLAUDE.md "Phase 14 CLOSED" at v23.

## Operating disciplines (binding -- the same set the prior orchestrators carried)
- **Merge:** gate-pass / QA-pass / Codex-convergence IS the trigger across all copowers phases; the next-phase dispatch brief + inline prompt are orchestrator actions. Do NOT ask "shall I merge."
- **Never false-green:** after every merge, RUN `python -m pytest -m "not slow" -q` ON THE MERGED HEAD and READ the actual result before claiming green. Do NOT carry a branch number forward. (The SB5 brainstorm implementer self-caught a false-green this arc -- the discipline is live.)
- **QA every product against disk** before merge (branch/trailers/merge-base; docs-only-or-code scope; schema verdict; LOCKs; spot-check Codex catches vs production).
- **Trailer hazard:** keep the FINAL `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` before every push. NO `Co-Authored-By`; NO `--no-verify`.
- **Codex transport (RESOLVED):** the MCP `codex`/`codex-reply` tools are DEAD in the VS Code extension (do NOT attempt them). copowers is GitHub-sourced (`copowers@copowers`, v2.0.2+) and its `adversarial-critic` skill auto-routes to a **WSL Codex CLI fallback** that reads the worktree from disk. **Run chains to CONVERGENCE** (zero new crit/major; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`). Direct WSL: `wsl.exe bash -ilc` (INTERACTIVE login for the node22 PATH); `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < prompt` (R1); `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+ -- **`resume` REJECTS `-s` AND `-C`/`--cd`**; pre-generate the diff on Windows since WSL can't resolve the worktree `.git`). Findings go to `.copowers-findings.md` which is now **gitignored** (along with `.codex-prompt-*.md`, `.copowers-session-*.json`) -- read it from the worktree on disk to verify a chain ran genuinely; it is NOT committed/merged.
- **Operator-witnessed gate (code phases):** the rendered surface in a real browser is BINDING. Mechanics that worked at SB4: run the branch server from the worktree -- `cd <worktree> && python -m swing.cli web --port 8081` (background) -- against the operator's LIVE v23 DB (safe for read-mostly sub-bundles); the operator drives the browser for the binding surfaces while you run DB-side probes (S1 suite, S2 schema). For SB5 the gate is the rendered `/metrics` overview (cards + the 3 inline-`<polyline>` sparklines + honest suppressed states + drill-down). **Kill the server via PID** when done: `Get-NetTCPConnection -LocalPort 8081` → `Stop-Process -Force` → VERIFY the port is free + no straggler `python ... swing.cli web` procs (`feedback_taskstop_does_not_kill_detached_server` -- TaskStop does NOT kill it).
- **Worktree CLI:** `python -m swing.cli` (NOT bare `swing`). After an executing-plans merge, reinstall `swing` from main (`pip install -e . --no-deps`).
- **Inline prompts:** every dispatch brief gets a paste-ready inline implementer prompt in chat; commit the brief BEFORE the prompt.

## Session-specific notes for continuity
- **The gitignore-of-Codex-artifacts convention is now established** (SB5 brainstorm): `.copowers-findings.md` + `.codex-prompt-*.md` + `.copowers-session-*.json` are gitignored. Verify a chain's authenticity by reading the on-disk findings in the worktree (not the repo). Operator accepted removing SB4's previously-committed verbatim findings for consistency.
- **The close-out structure is operator-LOCKed (2026-05-30):** A-3 + P14.N7 → SB5.5; B-7 → Phase 14 final touch; A-5 (styled 404) → CLOSED (no revisit); group-(a) minor advisories → folded into the close-out polish batch. Phase-15+ research items (B-1..B-6, B-8) are tracked but OUT of Phase 14. Full detail in phase3e-todo #5.
- **The operator is highly engaged + paces deliberately at sub-bundle boundaries** -- present milestones + the forward path + let them set pace; honor `feedback_pause_means_pause`.

---

*End of handoff. Clean boundary: SB5 brainstorm SHIPPED `3c18b81`; SB5 writing-plans dispatched + in flight; main = `3d022d4`. First action: await/QA the SB5 writing-plans return → merge → author the SB5 executing-plans dispatch brief + inline prompt → drive the executing-plans cycle + operator-witnessed render gate → then SB5.5 (Schwab) + the close-out polish batch + B-7 final touch + the Phase 14 close-out review (Sec 9.1 Q6). SB5 is the FINAL sub-bundle; Phase 14 closes at v23. The 7 SB5 OQ dispositions are LOCKed (OQ-1 = inline-`<polyline>`); the v22/v23 substrates are LOCKED.*
