# Phase 14 Sub-bundle 5 (FINAL) -- Metrics Overview (P14.N5) -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed implementation plan to ship the **metrics overview** to production code + tests: enhance the EXISTING text-only `GET /metrics` index into a graphics-driven overview -- a pure inline-`<polyline>` SVG **sparkline helper** (T-5.1), the **`build_metrics_index_vm(conn)` -> `(cfg, conn)` widening** with the route + 3 call-site tests updated ATOMICALLY plus **9 read-only per-surface extractors** emitting a headline stat on all 9 cards + sparklines on the **3 trend-bearing surfaces only** (T-5.2), the **card-grid template + CSS** (T-5.3), and the closer gates + operator render gate (T-5.4). This is a **read-mostly UX sub-bundle: ZERO new metric computation, ZERO data-write, NO schema change** (render-direct inline keeps SB5 schema-free; v23 held). Plan is dispatch-ready per the writing-plans return report §15. **SB5 is the FINAL Phase 14 sub-bundle.**

**Brief:** `docs/phase14-sub-bundle-5-metrics-overview-executing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; SB1 SHIPPED `e323339`; SB2 SHIPPED end-to-end `27f8007` (v22 live); SB3 SHIPPED end-to-end `edd098d` (v23 LIVE in the operator's real DB); SB4 SHIPPED end-to-end `31da4a5` (v23 held); **SB5 brainstorm SHIPPED `3c18b81`** (spec 526 lines; genuine v2.0.2 WSL Codex CONVERGED R3, 11 majors fixed); **SB5 writing-plans SHIPPED `9635d17`** (plan 1351 lines; genuine single WSL Codex chain CONVERGED R3, 2 crit + 4 major fixed; non-uniform thresholds 5/10/line-band; route widening atomic with builder); housekeeping at `b0175dd`. **Main HEAD at executing-plans dispatch: `b0175dd`.**

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (compressed to trigger+fix; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~695+ cumulative ZERO Co-Authored-By trailer drift**; **Schema v23 LOCKED -- SB5 introduces NO migration** (do NOT add a `0024`; do NOT touch the v22 temporal-log or v23 chart-rename substrate); L2 LOCK preserved (source-grep test at `tests/integration/test_l2_lock_source_grep.py`).

**Expected duration:** ~3-5 hours executing-plans implementation + 1 Codex chain. Plan §G enumerates 4 tasks (T-5.1 -> T-5.4, serial; T-5.2 has 4 sub-steps a-d); **~12-20 commits + ~24 fast tests** projected (trust `pytest -m "not slow" -q` over the estimate per gotcha #1; **capture the exact baseline at branch creation** -- prior merged-main baseline was ~6905). Operator-paced; SHIPS production code + tests under `swing/` + `tests/` with **ZERO new migration**.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief.
- `copowers:executing-plans` wraps `superpowers:subagent-driven-development` with adversarial Codex review after all tasks complete.
- **Codex chain count: ONE chain** per OQ-7 LOCK + Sec 9.1 Q7 + the brainstorm/writing-plans precedent (single chain, converged). **Run to CONVERGENCE** (zero new criticals AND zero new majors) -- the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); may exceed 5 rounds; do NOT stop while majors surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.2 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt the MCP tools or the launcher/settings angle.** The `adversarial-critic` skill auto-routes to a WSL Codex fallback that reads the worktree from disk (no inline-size limit), read-only. **Preferred: invoke `copowers:executing-plans` normally and let it drive the WSL fallback.** If driving directly: R1 `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-5-metrics-overview-executing-plans - < <promptfile>'`; R2+ `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (NOTE: `resume` REJECTS `-s` AND `-C`/`--cd`; pre-generate the diff on Windows since WSL cannot resolve the worktree `.git`). WSL is fully provisioned. See memory `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher`.
- **PERSIST THE CODEX RESPONSES, NOT JUST THE PROMPTS (BINDING -- operator-directed 2026-05-30; memory `feedback_implementer_persist_codex_responses`):** for EACH adversarial round, write BOTH the prompt AND the Codex RESPONSE (verdicts + per-finding findings, and especially the final-round `NO_NEW_CRITICAL_MAJOR` line) to a gitignored on-disk file in the worktree (e.g. `.copowers-findings.md`, or `.codex-review-r{N}-prompt.md` + `.codex-review-r{N}-response.md`). The SB5 writing-plans chain saved only the prompts, so the orchestrator could not independently read the convergence verdict on disk -- DO NOT repeat that. The on-disk RESPONSES are how the orchestrator confirms the chain ran genuinely AND converged at QA. (These artifacts are gitignored -- they live on disk for QA, NOT committed.)
- Output: production code + tests + return report at `docs/phase14-sub-bundle-5-metrics-overview-executing-plans-return-report.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/plans/2026-05-30-phase14-sub-bundle-5-metrics-overview-plan.md`** -- the LOCKed plan (1351 lines; AUTHORITATIVE for implementation; genuine WSL Codex CONVERGED R3). Especially: §A Goals/non-goals; §B File map (+ the verified accessor table with file:line); §C Surface integration (the per-surface headline accessor table + §C.3 non-uniform thresholds + §C.4 OQ-4 fixed selectors); §E LOCK reverification matrix; §F Discipline hooks; **§G 4 tasks T-5.1->T-5.4 (+ §G.0 commit cadence; step-checkbox TDD)** (BINDING); §H Test surface (sum-check ~24); **§I Operator-witnessed render gate runbook**; §J Codex placement; §K Schema (NO change); §L Fixtures; §M Forward-binding lessons; §N Self-review; §O Phase 14 close-out readiness.

3. **`CLAUDE.md`** -- the compressed gotchas. Most relevant for SB5: **shared `base.html.j2` -- a new `vm.foo` field needs a safe default on EVERY base VM** (BUT note L7 below: SB5's new fields land on the LEAF `MetricsIndexSurface`, NOT `BaseLayoutVM`, so NO base-VM fan-out -- verify `BaseLayoutVM` shared.py is untouched); **Windows cp1252 / #16/#32 ASCII** (the load-bearing SB5 gotcha -- reused metric strings carry a real `>=` glyph; see §3); **matplotlib mathtext** (N/A -- inline `<polyline>` carries no text; if ANY matplotlib appears on this path it is an OQ-1 violation -> STOP); **bad-exemplar isolation** (the per-card try/except pattern). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature verify; re-grep at STEP 0), **#11/#13** (cascade audit each task -- esp. the `build_metrics_index_vm` signature).

4. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_implementer_persist_codex_responses` (**NEW -- persist each round's RESPONSE to disk, not just the prompt**)
   - `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (MCP dead in VS Code ext; WSL fallback is the path; `resume` rejects `-s`/`-C`)
   - `feedback_codex_round_limit_suspended` (run to convergence; no 5-round cap)
   - `feedback_regression_test_arithmetic` (the 7-run discriminator: compute under capital>=5 draws AND funnel>=10 suppresses on the SAME DB)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`)
   - `feedback_visual_gate_both_render_and_browser` (the gate split: operator-driven browser + orchestrator DB-side probes; re-confirm the SB5 split)
   - `feedback_no_false_green_claim` (re-run the suite on the actual head + READ it; never carry a count forward)

5. **Production code surfaces** cited in plan §B. **RE-VERIFY at executing-plans STEP 0** (the plan re-grepped on its worktree; main is now `b0175dd`). The orchestrator re-verified the core accessors at SB5 writing-plans QA (§3 "Verified anchors"); re-confirm per #2.

---

## §1 LOCKs inherited (BINDING through executing-plans; DO NOT re-litigate)

All LOCKs preserved verbatim through 1 brainstorm + 1 writing-plans Codex chain per plan §E.

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = ... -> review+journal -> **metrics (THIS, LAST)**; **Q2** SERIAL
- **Q5** static graphics, **NO JS charting** -- inline `<polyline>` SVG, pure server-render
- **Q6** operator browser-witnessed verification at merge (the rendered overview is the BINDING visual gate)
- **Q7** Codex chain count -> **SINGLE chain** (OQ-7)

### §1.2 L1-L9 LOCKs (plan §E)
- **L1** scope = **P14.N5 only** -- NO new metric/surface; the 9 per-surface routes' DATA logic is UNTOUCHED.
- **L2** **read-mostly** -- reuse the existing `build_*_vm`/`compute_*` outputs; **ZERO new computation; ZERO data-write** (no `chart_renders` write, no trade/fill/review write). Escalate if any task appears to need a write or a new cross-row aggregate.
- **L3** **NO schema change** -- `EXPECTED_SCHEMA_VERSION` stays 23; **add NO migration**; sparklines render-direct inline.
- **L4** **honesty floor** -- sparklines on the 3 trend-bearing surfaces ONLY (`capital_friction`/`identification_funnel`/`process_grade_trend`), each gated by its OWN threshold; the other 6 get a headline + honest suppressed state; NEVER a fabricated/flat line.
- **L5** **visual-gate discipline** -- the rendered card is binding; ASCII-only strings (incl. reused metric text).
- **L6** **render-lock N/A** -- pure string build; NO `_RENDER_LOCK`, NO matplotlib on this path (OQ-1 inline-only).
- **L7** **BaseLayoutVM contract preserved** -- new fields live on the leaf `MetricsIndexSurface`, NOT `BaseLayoutVM` (NO shared base.html.j2 fan-out).
- **L8** **HTMX disciplines** -- overview stays pure server-render (NO HTMX added).
- **L9** **close-out readiness** -- SB5 is the FINAL sub-bundle; draft the §O close-out note.

### §1.3 The 7 operator-LOCKed OQ dispositions (BINDING)

| OQ | LOCKed disposition |
|---|---|
| **OQ-1 sparkline tech** | **inline-`<polyline>` SVG** (generalise the `process_grade_trend` polyline algorithm; NOT matplotlib; no `_RENDER_LOCK`). |
| **OQ-2 sparkline breadth** | **3 trend-bearing surfaces ONLY** (honesty floor); the other 6 get a headline + honest suppressed state. |
| **OQ-3 route** | **Enhance `GET /metrics` in place** (NO new `/metrics/overview` route). |
| **OQ-4 headline selectors** | spec §6 exact accessors (re-grepped, §C.2); the 2 fixed selectors defaulted in §C.4 (`DEVIATION_HEADLINE_COHORT="Near-A+ defensible: extension test"`, `PATTERN_HEADLINE_CLASS="vcp"`) -- **operator-overridable at executing-plans** (confirm or re-point in one place). |
| **OQ-5 cache/schema** | **render-direct, no cache, no schema** (v23 held). |
| **OQ-6 render mode** | **eager** (no HTMX lazy-load per card). |
| **OQ-7 Codex chain** | **SINGLE chain** (run to convergence; cap suspended). |

---

## §2 Scope inheritance from plan §G (BINDING substrate)

Plan §G is AUTHORITATIVE. Implement task-by-task in the locked order; **3-5 commits/task; cascade-audit (Expansion #11/#13) after each task -- esp. re-grep `build_metrics_index_vm(` across `swing/` + `tests/` after T-5.2 (only the route + the 3 listed tests should call it); verify `%(trailers)` is `[]` after each commit** (§G.0). Tasks are serial T-5.1 -> T-5.2 -> T-5.3 -> T-5.4.

| Task | Scope | ~sub-steps |
|---|---|---|
| **T-5.1 -- sparkline helper** | NEW `swing/web/view_models/metrics/sparkline.py`: pure `build_sparkline_points(values, *, width=100, height=30, pad=2.0, min_points=2) -> str \| None`. X over the ORIGINAL index (None gaps do NOT compress time); Y normalised over defined min/max, inverted (SVG y-down); flat -> mid-line; `< min_points` defined -> `None`; 2-dp; ASCII-only; NO matplotlib/`_RENDER_LOCK`. 9 unit tests. | 5 steps |
| **T-5.2 -- VM enhancement (4 sub-steps a-d)** | (a) `MetricsIndexSurface` +6 leaf fields + `_OverviewCard` + `_format_metric_value` + the central **`_ascii()` chokepoint** + ASCII-ify the one non-ASCII `_SURFACES` description (`sec 3.1`); (b) the 3 trend-surface extractors (sparklines; each its OWN threshold -- capital=5, funnel=10, process-grade line-band); (c) the 6 headline-only extractors + the 2 OQ-4 constants; (d) **widen `build_metrics_index_vm(conn)` -> `(cfg, conn)` + the dispatch + per-card try/except isolation + the central `_ascii` application in `_enrich_surface` + the ROUTE call-site + the 3 existing call-site tests -- ALL ATOMIC** (Codex R1 MAJOR #2: the route MUST widen in the SAME commit as the builder, or `GET /metrics` 500s). | a-d |
| **T-5.3 -- template + CSS** | Rewrite `metrics/index.html.j2` (`<ul>` -> 9-card grid: label + headline-or-suppressed + inline `<svg><polyline>` on the 3 trend cards else sparkline-suppressed caption + preserved drill-down link); add card-grid + sparkline CSS to `app.css`. **Deterministic render tests via a monkeypatched `swing.web.routes.metrics.build_metrics_index_vm`** (OPERATOR-CONFIRMED; the route imports it into namespace at `metrics.py:30` so the patch resolves -- verified) -> route 200; exactly 3 `<polyline>`; `body.isascii()`; 9 drill-down hrefs preserved; below-threshold -> 0 polylines + honest caption. The route was already widened in T-5.2.d. | 5 steps |
| **T-5.4 -- closer + gates + render gate** | full fast suite + ruff green; `EXPECTED_SCHEMA_VERSION==23` + ZERO new migration; L2 Schwab source-grep passes; ASCII gate (source grep + the rendered `body.isascii()` tests); `%(trailers)` empty; operator render gate (§I); §O close-out note + return report. NO production code. | 8 steps |

**Total: ~24 new tests** across 3 new files (+1 route edit, +3 call-site edits, +1 `_SURFACES` description ASCII edit). **Do NOT widen task scope** beyond plan §G acceptance criteria + step-checkbox TDD.

### §2.1 The central `_ascii()` chokepoint (the load-bearing SB5 item; Codex R1+R2 CRITICAL)
Reused metric strings (`SuppressedMetric.placeholder_text`, etc.) embed a real `>=` (U+2265) glyph (`swing/metrics/honesty.py`; `capital.py:640`/`funnel.py:288` build their suppressed strings with it). A source-grep ASCII gate MISSES imported non-ASCII. The plan's central `_ascii()` chokepoint in `_enrich_surface` coerces EVERY reused text field (mapped substitutions `>=`/`<=`/`->`/etc. THEN `encode("ascii","replace")`) AND the static label/description (defense-in-depth). The `_ascii()` substitution map MUST cover every glyph the reused strings actually use (a `?` in overview text = an unmapped-glyph BUG; the no-`?` test guards it). **Verify via a RENDERED `body.isascii()` route test on a LOW-sample DB where suppression text appears -- NOT just a source grep.**

### §2.2 The process_grade single-compute path (plan §C.2 / §M lesson 3)
`build_process_grade_trend_vm` exposes only a pre-scaled-to-800x360 `svg_polyline_points` string -- it CANNOT be re-scaled to 100x30. Use a SINGLE `compute_process_grade_trend(conn)` call for BOTH the headline (`series.rendered_value`/`series.suppressed`) AND the sparkline raw values (`series.line_points`, each `.value: float | None`) AND the gate (`series.drawability_text == "rolling line drawable"`). Do NOT call the VM for the sparkline; do NOT double-compute.

---

## §3 Production corrections + verified anchors + watch items (BINDING)

### Verified anchors (orchestrator re-grep at SB5 writing-plans QA against `b0175dd`-era source; re-confirm at STEP 0 per #2)
- **Index (EXISTS -- enhancement):** `build_metrics_index_vm(conn)` currently conn-only (`swing/web/view_models/metrics/index.py:97`) -- widen to `(cfg, conn)`; `_SURFACES` has 9 entries; exactly ONE non-ASCII description (trade-process `sec 3.1`/`§`).
- **Route:** `metrics_index` imports `build_metrics_index_vm` INTO namespace (`swing/web/routes/metrics.py:30`) + calls it bare at `:56` -- so monkeypatching `swing.web.routes.metrics.build_metrics_index_vm` (T-5.3) resolves; current call is `(conn)` -> widen to `(cfg, conn)` in T-5.2.d.
- **Non-uniform thresholds:** `TREND_MIN_RUNS = 5` (`swing/metrics/capital.py:61`) vs `= 10` (`swing/metrics/funnel.py:42`) -- import EACH by name; never hardcode a single `n<5`. The process-grade gate is `series.drawability_text == "rolling line drawable"` (line-band).
- **Headline accessors (re-grep at STEP 0; the plan corrected spec drift):** `build_trade_process_card_vm` (`trade_process_card.py:123`), `ALL_COHORTS_KEY="__all__"` (`:46`), `MetricCellB` (`swing/metrics/process.py:343`, `.value: BootstrapCI | SuppressedMetric`); `build_hypothesis_progress_card_vm` (`hypothesis_progress_card.py:404`); `build_tier_comparison_vm` + `APLUS_COHORT` (`swing/metrics/tier.py`); `compute_process_grade_trend` (`swing/metrics/process_grade_trend.py:524`); `build_pattern_outcomes_vm(conn, *, session_date)` (`swing/web/view_models/patterns/outcomes_card.py:39` -- **positional `conn`, NO `cfg`**). The `vm.result` indirection is `... | None` on tier/capital/maturity/funnel/deviation -- ALWAYS guard `is None` + empty-collection (`trend_runs[-1]`, `next(...)`).
- **Schema:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`); highest migration `0023_*`. **Add NO migration.**

### Cumulative gotchas (plan §F)
**#16/#32 ASCII** (the central `_ascii()` chokepoint + rendered `body.isascii()` test -- §2.1) / **L7 leaf-VM** (new fields on `MetricsIndexSurface`, NOT `BaseLayoutVM`; verify shared.py untouched) / **per-card try/except isolation** (one extractor failure -> that card "unavailable" + `_LOG.warning`, grid still renders 9; `# noqa: BLE001`, NOT a silent swallow) / **`vm.result is None` + empty-collection guards** / **shared connection** (pass the route's `conn` to all 9 builders; surfaces 1-7 via `conn=conn`, 9 positionally, 8 via `compute_*(conn)`; no builder opens its own tx when conn passed) / **TestClient lifespan** (`with TestClient(app) as client:`) / **trailer-parse hazard** (plain-prose final `-m` paragraph; `%(trailers)` `[]`).

**Streaks to preserve:** ~695+ ZERO `Co-Authored-By` (verify `%(trailers)` per commit; final `-m` paragraph plain prose); **NO new migration (v23 held; no v24; v22/v23 substrates UNTOUCHED)**; L2 LOCK (source-grep continues passing); ASCII discipline.

---

## §4 Codex SINGLE-chain placement (OQ-7 LOCK; plan §J)

Run ONE chain at the end of executing-plans, after ALL code + tests land + green, BEFORE the operator-witnessed gate. **Run to CONVERGENCE** (`NO_NEW_CRITICAL_MAJOR`; cap suspended -- may exceed 5 rounds).

**Lens (plan §J watch items):** (1) the spec §6 accessors re-grepped against production (`MetricCellB.value` wrapping; `vm.result` indirection; `build_*_card_vm` names; pattern_outcomes' non-cfg `(conn, *, session_date)` signature); (2) NON-uniform thresholds (5/10/line-band) each from its own constant -- the 7-run discriminator test valid; (3) the process_grade single-`compute_*` path (not the pre-scaled VM points string); (4) L2 zero-write/zero-new-compute; (5) L3 no schema; (6) OQ-1 inline only (no matplotlib/`_RENDER_LOCK`); (7) L7 leaf-VM fields (BaseLayoutVM untouched); (8) honesty floor (3 sparklines, no fabrication); (9) per-card error isolation; (10) ASCII (the central `_ascii()` + rendered `body.isascii()`) + trailer hygiene; (11) the T-5.3 monkeypatch target name-resolution; (12) the `dataclasses.replace(cfg, paths=...)` construction validity in the tmp_path-only call-site test.

**PERSIST EACH ROUND'S PROMPT AND RESPONSE TO A GITIGNORED ON-DISK FILE** (§ skill posture; memory `feedback_implementer_persist_codex_responses`) -- the final-round verdict line must be readable on disk for orchestrator QA.

**Transport:** the WSL Codex fallback reads the worktree from disk (copowers v2.0.2; MCP dead). Aim for ZERO Major accepted-as-rationale (brainstorm + writing-plans both resolved all in-place). **If Codex finds a defect requiring a schema change OR a new write path:** STOP + escalate (do NOT add a migration; do NOT add a write).

---

## §5 Operator-witnessed gate (plan §I; BINDING)

After the chain converges + return report drafted, the orchestrator returns to the operator. **The BINDING gate is the RENDERED overview in a REAL browser.** **Re-confirm the gate split with the operator** (`feedback_visual_gate_both_render_and_browser`: operator-driven browser for the rendered cards/sparklines + orchestrator DB-side probes for S1/S2). Note: the metrics index is pure server-render (no HTMX), so a render-and-Read fallback is also viable -- but the operator browser pass is binding.

| Step | Surface | What to verify |
|---|---|---|
| **S1** | pytest + ruff (orchestrator) | full fast suite green (baseline + ~24 NEW); `ruff check swing/` clean. READ the actual numbers (no false-green). |
| **S2** | schema (orchestrator) | `EXPECTED_SCHEMA_VERSION == 23`; NO new migration file; operator DB still v23. |
| **S3** | browser overview (operator; BINDING) | 9 cards in registry order; the 3 trend cards show an inline sparkline when data sufficient ELSE the honest suppressed caption (e.g. *"trend needs >=5 runs (have N)"*), NEVER a flat/fabricated line; the 6 non-trend cards show a headline (or honest suppressed) + NO sparkline slot; EVERY drill-down link resolves to its existing per-surface route; headline figures match the drill-down (no invented numbers); no mojibake / no `UnicodeEncodeError` in the `swing web` console. |
| **S4** | L2 source-grep (orchestrator) | no new Schwab call-sites. |
| **S5** | ASCII (orchestrator) | the §G T-5.4 grep returns nothing AND the rendered `body.isascii()` tests pass (covers reused suppression text the source grep would miss). |
| **S6** | trailers (orchestrator) | `git log -1 --format='%(trailers)'` == `[]`. |

**Teardown (memory `feedback_taskstop_does_not_kill_detached_server`):** if a `swing web` server is launched for the gate (orchestrator runs the BRANCH server from the worktree -- `python -m swing.cli web --port 8081` -- against the live v23 DB; read-mostly so safe), kill it via `Get-NetTCPConnection -LocalPort 8081` -> `Stop-Process -Force` and VERIFY the port is free + no straggler `python ... swing.cli web` procs before claiming teardown. TaskStop does NOT kill a detached server.

**Gate-pass triggers** ("all surfaces pass" / "gate passed" / equivalent) -> orchestrator merges per `feedback_orchestrator_performs_merge` BINDING. **After merge: re-run the fast suite ON THE MERGED HEAD and READ the result before claiming green** (`feedback_no_false_green_claim`); then reinstall `swing` from main (`pip install -e . --no-deps`).

---

## §6 Done criteria

1. All 4 tasks shipped (T-5.1 -> T-5.4)
2. Codex SINGLE chain CONVERGED at NO_NEW_CRITICAL_MAJOR (run to convergence; cap suspended); **the on-disk gitignored Codex artifacts evidence it ran genuinely via WSL AND show the final verdict (prompt AND response per round)**
3. fast suite green on branch (baseline + ~24 NEW); `python -m pytest -m "not slow" -q`
4. `ruff check swing/` clean (0 E501)
5. ZERO Co-Authored-By trailer drift (verify `%(trailers)`); final `-m` paragraphs plain prose
6. **NO migration; `EXPECTED_SCHEMA_VERSION` stays 23; ZERO data-write + ZERO new computation from SB5 paths** (escalate if a migration or write seems needed)
7. L2 LOCK preserved (source-grep test PASSES)
8. The 3 trend sparklines each gated by its OWN constant (capital=5, funnel=10, process-grade line-band); the 6 others headline-only; the central `_ascii()` chokepoint + rendered `body.isascii()` tests present; per-card try/except isolation tested
9. Return report at `docs/phase14-sub-bundle-5-metrics-overview-executing-plans-return-report.md` complete per §7
10. Branch pushed to origin; ready for orchestrator QA + operator-witnessed gate

---

## §7 Return report shape

1. Final HEAD + commit count breakdown (per-commit Codex round attribution)
2. Codex round chain (single chain; summary table + convergent shape; **EVIDENCE genuine via WSL -- cite the on-disk gitignored prompt+response files per round, incl. the final NO_NEW_CRITICAL_MAJOR line**)
3. Per-task completion summary (T-5.1 -> T-5.4; T-5.2 a-d)
4. Test surface verification (~24 fast projected; per-task actual; total before + after -- READ the actual count, no false-green)
5. Pre-locked decisions verbatim verification (Sec 9.1 + L1-L9 + the 7 OQ dispositions; the OQ-4 fixed selectors as-shipped or operator-re-pointed)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO preferred)
7. Production-code citations verified at task completion (#2 re-grep; the accessor corrections honored)
8. Schema impact verdict (**NO migration**; v23 held; the read-mostly assertion -- ZERO data-write + ZERO new computation)
9. The central `_ascii()` chokepoint + non-uniform-threshold + per-card-isolation verification
10. L2 LOCK verification (source-grep PASSES; cite test name + result)
11. Operator-witnessed gate readiness (S1-S6; the rendered overview + the 3 inline sparklines + honest suppressed states + drill-down)
12. NEW forward-binding lessons banked (for Phase 14 close-out + CLAUDE.md gotcha consideration)
13. ASCII discipline scope (gotcha #32; enumerate NEW + MODIFIED files)
14. Cumulative gotcha set application summary (per task)
15. Worktree teardown status
16. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits)
17. CLAUDE.md status-line refresh draft text (SB5 executing-plans SHIPPED -> Phase 14 close-out)
18. **§O Phase 14 close-out readiness note** (SB5 is the FINAL sub-bundle; all 5 merged; the Sec 9.1 Q6 cross-sub-bundle integration review + the banked follow-ups sequencing per phase3e-todo `#5`)

---

## §8 OUT OF SCOPE (do not implement)

- SB5.5 (Schwab: A-3 daily-bar web wiring + P14.N7 checker-thread resilience) -- its own cycle, after SB5
- The Phase 14 close-out polish batch (P14.N1 dashboard thumbnails + A-1 market_weather 200MA + A-2 vcp crowding + A-4 `_bulz_*` rename + the group-(a) minor advisories) -- after SB5.5
- B-7 operator failure-mode classification (Phase 14 final touch)
- Any NEW metric computation / surface / cross-row aggregate for a headline (L1/L2)
- Any new schema/migration (L3; no v24) OR any data-write (`chart_renders`/trade/fill/review) (L2)
- Matplotlib sparklines / `_RENDER_LOCK` on this path (OQ-1 inline-only) / JS charting (Q5)
- A new `/metrics/overview` route (OQ-3 enhance-in-place) / HTMX lazy-load per card (OQ-6 eager)
- Sparklines on the other 6 surfaces (OQ-2 / L4 honesty floor)
- Multi-series sparklines / "delta vs prior run" arrows / cached sparkline SVGs (V2, spec §12)
- Temporal-log (v22) or chart-rename (v23) substrate changes; Schwab API changes (L2 LOCK)
- Production code modifications NOT in plan §B file map
- Phase 15+

---

## §9 If you get stuck

- If production drifted since the writing-plans merge (`9635d17`/`b0175dd`) and a plan-cited file:line no longer matches, ESCALATE (do NOT silently patch). Orchestrator re-verified the core accessors at SB5 QA (§3); re-grep at STEP 0.
- If any task appears to need a NEW write path OR a schema change OR a new cross-row aggregate, STOP + escalate -- L1/L2/L3 forbid all three (the render-direct/read-mostly decision is the schema-free + zero-write guarantee).
- HOLD THE LINE if Codex pushes back on: inline-`<polyline>` (OQ-1; NO matplotlib); 3-trend-surfaces-only (OQ-2 honesty floor); enhance-in-place (OQ-3); render-direct/no-schema (OQ-5); eager render (OQ-6); single chain run-to-convergence (OQ-7); the NON-uniform thresholds; the leaf-VM-fields (L7).
- If a Codex finding needs a schema change or a write path, STOP + escalate.
- If the Codex MCP times out, do NOT attempt to fix it (dead in the VS Code extension); use the WSL Codex fallback (reads the worktree from disk; copowers v2.0.2 auto-routes). **Save the responses to disk per round (`feedback_implementer_persist_codex_responses`).**
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT widen scope to SB5.5 / the close-out polish batch / B-7 / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §10 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface for production code + tests).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-5-metrics-overview-executing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-5-metrics-overview-executing-plans/`. Branch from main HEAD `b0175dd`.
- **Model:** defer to harness default.
- **CLI invocation in the worktree:** `python -m swing.cli` (NOT bare `swing` -- the editable install points at main, not the worktree).
- **Expected duration:** ~3-5 hours implementation + ~30-90 min for the single Codex chain (run to convergence). Operator-paced.
- **Codex chain count:** ONE chain (OQ-7 LOCK + plan §J), run to convergence via the WSL Codex fallback (copowers v2.0.2; MCP dead in the VS Code extension). **Persist prompt AND response per round to a gitignored on-disk file.**
- **Production surface (plan §B):** NEW `swing/web/view_models/metrics/sparkline.py` + MODIFY `swing/web/view_models/metrics/index.py` + `swing/web/routes/metrics.py` + `swing/web/templates/metrics/index.html.j2` + `swing/web/static/app.css`. **NO migration.** **Test surface:** NEW `tests/web/view_models/metrics/test_sparkline.py` + `tests/web/view_models/metrics/test_index_overview.py` + `tests/web/test_routes/test_metrics_index_overview.py`; UPDATE `tests/web/test_base_layout_vm_recent_multi_leg_field.py` + `tests/web/test_routes/test_metrics_routes.py` + `tests/web/test_routes/test_metrics_pattern_outcomes.py` (call-site widening).

---

*End of brief. Phase 14 Sub-bundle 5 (FINAL) executing-plans dispatch -- execute the LOCKed 1351-line plan (a pure inline-`<polyline>` sparkline helper; the `build_metrics_index_vm(conn)` -> `(cfg, conn)` widening atomic with the route + 3 call-site tests; 9 read-only per-surface extractors emitting a headline on all 9 cards + sparklines on the 3 trend-bearing surfaces each gated by its OWN threshold 5/10/line-band; a card-grid template; the central `_ascii()` chokepoint for reused metric text; ~12-20 commits + ~24 fast tests); ONE Codex chain run to convergence (persist prompt AND response per round to disk); the operator-witnessed S1-S6 render gate per plan §I. NO schema change (v23 held); NO data-write; NO new computation. The rendered overview in a real browser is the BINDING gate. OUTPUT: production code + tests + return report; ready for orchestrator merge + operator-witnessed gate + post-merge housekeeping (re-run the suite on the merged HEAD per feedback_no_false_green_claim + reinstall swing from main). SB5 ship completes all 5 sub-bundles -> Phase 14 close-out review (Sec 9.1 Q6); Phase 14 lands at v23.*
