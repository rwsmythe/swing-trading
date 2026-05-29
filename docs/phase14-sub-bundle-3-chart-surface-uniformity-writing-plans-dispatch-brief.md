# Phase 14 Sub-bundle 3 -- Chart-Surface Uniformity -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 3 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan derived from the Sub-bundle 3 brainstorm spec. Plan lives at `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-3-chart-surface-uniformity-plan.md` (or operator-paired date). The plan decomposes the spec into bite-sized TDD slices with per-task acceptance criteria, file-level diff projections, test scope, commit cadence, a **per-renderer operator-witnessed visual-gate runbook**, and an executing-plans dispatch-readiness package.

**Brief:** `docs/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; Sub-bundle 1 SHIPPED at `e323339`; Sub-bundle 2 SHIPPED end-to-end at `27f8007` (v22 live); **Sub-bundle 3 brainstorm SHIPPED at `f16735f`** (spec 494 lines; Codex single-chain CONVERGED R3); housekeeping at `4d33de8`. Main HEAD at writing-plans dispatch: `4d33de8`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING (compressed in CLAUDE.md as of `665cab0`; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~622+ cumulative ZERO Co-Authored-By trailer drift; 50th cumulative C.C lesson #6 validation NOTABLE at Sub-bundle 3 brainstorm; **Schema v22 LOCKED -- Sub-bundle 3 DESIGNS the v23 rename migration (applied at executing-plans, NOT writing-plans)**; L2 LOCK preserved.

**Expected duration:** ~2-3 hours writing-plans + 1 Codex chain. Plan line target **~1500-2800 lines** (multi-renderer candlestick rebuild + v23 atomic rename + BULZ zones + 3-site weather fix + per-renderer visual-gate runbook).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief.
- **Codex chain count: SINGLE chain** per the operator-LOCKed OQ-chain disposition (§1.3) + Sec 9.1 Q7 + gotcha #36 caveat (pure UX/chart; the v23 rename is a mechanical value-rename, not a permanent append-only substrate).
- **Codex MCP transport:** the MCP is timing out at 1s on this host (FB-N1); **the operator is investigating that separately -- do NOT attempt to fix the MCP.** Use the `codex exec` CLI + `resume --last` thread continuity as the documented backstop (paste artifacts INLINE; codex-cli `-s read-only` cannot spawn shells here). Identical adversarial substance.
- Output: plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-3-chart-surface-uniformity-plan.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/specs/2026-05-29-phase14-sub-bundle-3-chart-surface-uniformity-design.md`** -- the brainstorm spec (494 lines; AUTHORITATIVE; Codex CONVERGED R3). Especially §2 (pre-locked decisions + the OD items), §3 module touch list, §4 renderer-uniformity (candlesticks), §5 V2.G2 v23 rename, §6 P14.N1 thumbnail, §7 P14.N4 BULZ zones, §8 P14.N8 weather fix, §9 S6, §10 decomposition, §11 test fixture + visual-gate strategy, §12 schema impact (v23), §13 V1 simplifications, §14 OQ table.

3. **`docs/phase14-sub-bundle-3-chart-surface-uniformity-brainstorm-return-report.md`** -- return report (15 items): forward-binding lessons + the 3 brief-vs-production corrections + V2 candidates.

4. **`docs/phase14-sub-bundle-3-chart-surface-uniformity-brainstorming-dispatch-brief.md`** §1 LOCKs (L1-L7) + §5 watch items.

5. **`docs/phase14-commissioning-brief.md`** Sec 2.1 + Sec 9.1 LOCKs (Q1/Q2/Q4/Q5/Q6/Q7).

6. **`CLAUDE.md`** -- the compressed gotchas. Most relevant: **matplotlib mathtext** (ASCII annotation text; manual visual verification non-optional); **#11** (Schema-CHECK + constant + validator + `_row_to_*` mapper same task; backup-gate STRICT `pre_version == 22`); **#9** (executescript implicit COMMIT -> BEGIN/COMMIT/ROLLBACK); HTMX disciplines if any surface is HTMX-driven; **Weather lookup must NOT query by action_session** (P14.N8 `current_stage` asof). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **Expansion #10c** (renderer-kwargs uniformity + cache-collision tests) + **#2** (signature verify) + **#4** (SQL column verify) + **#11** (taxonomy propagation for the rename).

7. **Production code surfaces** (re-grep at plan-authoring per #2; the brainstorm verified these at `f16735f`):
   - `swing/web/charts.py` -- the 5 renderers (`render_watchlist_thumbnail_svg:180`, `render_hyprec_detail_svg:226`, `render_position_detail_svg:284`, `render_market_weather_svg:334`, `render_theme2_annotated_svg:481`) + the `_annotate_*` family + shared helpers
   - `swing/web/chart_jit.py:158` (the JIT weather default `stage_2` hardcode) + `swing/data/repos/chart_renders.py` (surface enum + `refresh_chart_render`)
   - `swing/data/migrations/0020_*.sql:179-219` (the `surface` CHECK enum -- `hyprec_detail`; the partial unique indexes do NOT reference `hyprec_detail`) + `swing/data/migrations/0022_*.sql` + `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION=22`; `_phase14_backup_gate`; `run_migrations`)
   - `swing/pipeline/runner.py:2883` (pipeline-time weather `trend_template_state="stage_2"` hardcode) + the `current_stage` reader
   - `swing/web/routes/dashboard.py:~117` (refresh-handler `"n/a"`) + routes/templates/view-models referencing the `hyprec_detail` surface/renderer
   - `pyproject.toml:40,42` (`mplfinance>=0.12` -- already declared) + the `Trade` model (BULZ entry/stop/target fields for P14.N4)

8. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` (MCP off-purview; CLI backstop), `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose; verify `%(trailers)`), `feedback_verify_regression_test_arithmetic` (BULZ zone-boundary + candlestick-vs-line tests).

---

## §1 LOCKs inherited (BINDING through writing-plans; DO NOT re-litigate)

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = ... -> **chart-surface uniformity (THIS)** -> review+journal -> metrics; **Q2** SERIAL
- **Q4** V2.G2 `hyprec_detail`->`ticker_detail` rename ships in THIS sub-bundle as a **v23 migration** (data-migration discipline)
- **Q5** matplotlib SVG only (mplfinance is matplotlib-based -> within the no-JS LOCK)
- **Q6** operator browser-witnessed verification at merge (the rendered chart is the BINDING visual gate)
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** (operator-LOCKed, §1.3)

### §1.2 Brainstorm spec §2 + L1-L7 LOCKs
- **L1** scope = V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6 cosmetic ONLY
- **L2** v23 migration (gotcha #11 paired + gotcha #9 + backup-gate STRICT `pre_version == 22`; migrate CHECK enum + existing rows; the partial indexes do NOT reference `hyprec_detail`)
- **L3** renderer-kwargs uniformity LOCK (Expansion #10c); cache-collision discriminating tests at reused surfaces
- **L4** matplotlib visual-gate discipline (byte/string tests INSUFFICIENT; per-renderer operator-witnessed visual gate; ASCII annotation text)
- **L5** atomic rename (no orphaned `hyprec_detail` across schema + Python + renderer name + routes + templates + tests)
- **L6** L2 LOCK preserved (ZERO new `schwabdev.Client.*` call sites)
- **L7** P14.N8 fixes the render to show the REAL trend, not suppress it

### §1.3 Operator-LOCKed OQ dispositions (operator-paired triage 2026-05-29 #5; BINDING)

| OQ | LOCKed disposition |
|---|---|
| **P14.N8 scope (OD-3)** | **Real `current_stage` at ALL 3 weather sites** -- the refresh handler (`dashboard.py:~117`) + the pipeline-time render (`runner.py:2883`) + the JIT default (`chart_jit.py:158`). `current_stage` reads weather rows only (no Schwab/yfinance; L6 preserved). Use the render-context asof (NOT `action_session`; the weather-lookup gotcha). |
| **Candlestick scope (OD-2)** | **The 4 DETAIL surfaces get mplfinance candlesticks** (`ticker_detail` [renamed], `position_detail`, `market_weather`, `theme2_annotated`); the **watchlist thumbnail STAYS a line** (illegible at thumbnail size). |
| **Codex chain count (OQ-chain)** | **SINGLE chain** at writing-plans AND executing-plans. |
| **OQ-4 (P14.N1)** | Ship the thumbnail RENDERER substrate only; **defer consuming-surface wiring to Sub-bundle 4**. |
| **OQ-6 (market_weather MAs)** | **50/200 only** (10/20 too noisy at 400px). |
| **OQ-7 (v23 row rename)** | **In-migration row `UPDATE`** (`SET surface='ticker_detail' WHERE surface='hyprec_detail'`), atomic with the schema change. |
| **OQ-S6 (duration text)** | **Move the annotation text to upper-right** (matches existing slug placement; clears the legend). |
| **OQ-mav-color** | **Pin a colorblind-safe distinct MA palette in the shared helper at writing-plans** (BEFORE implementation; MA distinguishability is central to the visual gate; ASCII-safe). |
| **OQ-N4-target** | **Verify the `Trade` target field at plan-authoring** (#4 SQL/field verify); **draw the target zone only if the field is present** (risk-zone-only fallback if absent). |
| **OQ-N4-color** | Zone semantics (entry/stop/target) are binding; **exact hues confirmed at the operator-witnessed gate** (cosmetic). |
| **Full rename** | Rename the renderer FUNCTION too: `render_hyprec_detail_svg` -> `render_ticker_detail_svg` (+ all callers). |

---

## §2 Architectural surface for the plan (BINDING substrate)

### §2.1 Per-task slicing (plan §G; bite-sized; each task 3-5 commits max)
Suggested buckets (plan refines):
- **T-3.1 v23 rename** -- `00XX_*.sql` (CHECK enum `hyprec_detail`->`ticker_detail` + in-migration row `UPDATE`; backup-gate STRICT `pre_version == 22`; gotcha #9 BEGIN/COMMIT; rollback-through-runner test) + `db.py` `EXPECTED_SCHEMA_VERSION` 22->23 + `_phase14`-style backup gate + surface constants/`Literal` mirrors + `_row_to_*` mapper + the renderer-fn rename + ALL callers (routes/templates/view-models/tests). Atomic (L5); gotcha #11 paired. Grep-asserts ZERO orphaned `hyprec_detail`.
- **T-3.2 candlesticks** -- shared candlestick helper (mplfinance) + adopt on the 4 detail surfaces; thumbnail stays line; the pinned colorblind-safe MA palette in the helper; ASCII annotation discipline. Per-surface visual-gate fixtures.
- **T-3.3 P14.N4 BULZ zones** -- entry/stop/target shaded zones in `render_position_detail_svg` (axhspan/fill_between); target-only-if-present (OQ-N4-target); zone semantics fixed, hues gate-confirmed.
- **T-3.4 P14.N8 weather** -- real `current_stage` at all 3 sites (`runner.py:2883` + `chart_jit.py:158` + `dashboard.py:~117`); Expansion #10c renderer-kwargs uniformity test (all call sites pass identical kwargs); render-context-asof (not action_session).
- **T-3.5 P14.N1 + S6** -- thumbnail renderer substrate (substrate-only; wiring deferred SB4) + S6 duration-text -> upper-right.
- **T-3.6 closer** -- cross-surface integration + L2 source-grep continued-pass + ASCII verify + per-renderer visual-gate runbook + return report.

### §2.2 Per-task acceptance criteria (plan §G.X.acceptance)
Files modified/added (exact paths); functions added/renamed + signatures verified; discriminating tests (name + assertion shape); cumulative discipline preservation per task; Sec 9.1 + L1-L7 + OQ-LOCK preservation per task.

### §2.3 Test surface (plan §H)
Distributed across T-3.1..T-3.6 (rough: v23 rename/migration ~12-18; candlestick helper + 4 surfaces ~12-20; BULZ zones ~6-10; weather 3-site uniformity ~8-12; thumbnail + S6 ~4-8; integration + L2 ~4). **Plan sum-checks** in §H (trust pytest per gotcha #1). **0 slow tests** (charts render from fixture bars). Mandatory: the renderer-kwargs uniformity (Expansion #10c) cache-collision tests; the atomic-rename no-orphan grep test; the candlestick-vs-line per-surface assertion; the BULZ target-only-if-present branch.

### §2.4 Operator-witnessed visual-gate runbook (plan §I; per-renderer)
Plan SHALL produce a per-surface runbook where the BINDING gate is the RENDERED chart (matplotlib; byte/string tests insufficient):
- **S1** pytest + ruff; **S2** v23 applied (`schema_version=23`; `chart_renders` rows migrated `hyprec_detail`->`ticker_detail`; backup written); **S3** ticker_detail candlestick render; **S4** position_detail candlesticks + BULZ entry/stop/target zones; **S5** market_weather real-trend + candlesticks + 50/200 MAs; **S6** theme2_annotated duration-text upper-right (no legend overlap); **S7** weather-chart refresh-handler render MATCHES the pipeline-time render (Expansion #10c). DB-scriptable where possible (the prior sub-bundles' browser-MCP-unavailable fallback: operator-driven browser + orchestrator DB-side probes; OR orchestrator renders to PNG + reads it, as at Sub-bundle 2's S6).

### §2.5 Codex single-chain placement + schema v23 (plan §J + §K)
- SINGLE chain at end (OQ-chain LOCK); 2-4 round target.
- Plan §K: v23 is the ONLY new migration (`EXPECTED_SCHEMA_VERSION` 22->23; backup-gate STRICT `pre_version == 22`; gotcha #9; gotcha #11 paired). NO v24. Schema v22 stays LOCKED at writing-plans (v23 DDL is DESIGNED, applied at executing-plans).

---

## §3 Residual OQs (Codex SHOULD lock in the plan)
1. v23 migration filename/number (`0023_*`) + exact CHECK-enum rewrite shape.
2. The candlestick shared-helper API (figure construction reused across 4 surfaces).
3. The pinned MA color palette (OQ-mav-color -- exact 5 colorblind-safe hex values).
4. The `current_stage` callsite signature + the render-context asof param at each of the 3 weather sites.
5. The `Trade` field for BULZ target (OQ-N4-target verify).
6. Commit cadence preface (§G.0; Expansion #13 cascade audit each round).

---

## §4 OUT OF SCOPE (do not design into the plan)
- Review+journal (SB4) + metrics (SB5); P14.N1 consuming-surface wiring (deferred to SB4); temporal-log/v22 changes; schema beyond v23; JS charting; historical chart re-render/backfill; Schwab API changes (L2); Phase 15+; production code NOT in the plan's file map.

---

## §5 Adversarial review (Codex) -- SINGLE chain; watch items
1. Signature verify (#2) -- the 5 renderers + `current_stage` + `refresh_chart_render` + the `Trade` BULZ fields; re-grep at plan time.
2. Schema-CHECK + constant + validator + `_row_to_*` paired (#11) -- v23 rename all layers one task; backup-gate STRICT `pre_version == 22`; rollback-through-runner.
3. Atomic-rename no-orphan (L5) -- grep test asserts ZERO `hyprec_detail` + ZERO `render_hyprec_detail_svg` post-rename across swing/ + templates + tests.
4. Renderer-kwargs uniformity (Expansion #10c) -- the 3 weather sites pass identical kwargs; cache-collision tests.
5. Matplotlib mathtext + visual-gate -- ASCII annotation text; per-renderer visual gate declared; byte/string insufficient.
6. mplfinance integration -- candlestick render is deterministic + ASCII-safe; thumbnail correctly stays line.
7. BULZ target-only-if-present branch (OQ-N4-target); zone semantics correct.
8. L2 LOCK source-grep continues passing; ASCII discipline (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape
Plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-3-chart-surface-uniformity-plan.md`: §A Goals/non-goals · §B File map · §C Surface-by-surface integration · §D Out-of-scope · §E LOCK reverification (Sec 9.1 + L1-L7 + the §1.3 OQ dispositions) · §F Discipline + watch items per task · §G Per-task slicing (T-3.1..T-3.6) + §G.0 commit cadence · §H Test surface (sum-check) · §I Per-renderer operator-witnessed visual-gate runbook · §J Codex single-chain placement · §K Schema impact (v23) · §L Test fixture strategy (+ visual-gate fixtures) · §M Forward-binding lessons · §N Self-review checklist. **Target ~1500-2800 lines.** Commit stem: `docs(phase14-sub-bundle-3-plan): writing-plans -- ...` (final `-m` paragraph plain prose).

---

## §7 If you get stuck
- If a renderer's candlestick adoption forces an OHLCV-bar-shape change NOT anticipated, ESCALATE (the brainstorm confirmed bars already carry OHLC).
- If production drifted since the brainstorm merge (`f16735f`) and a spec-cited file:line no longer matches, ESCALATE.
- HOLD THE LINE: v23 rename in THIS sub-bundle (Q4); matplotlib/mplfinance no-JS (Q5); SINGLE chain (OQ-chain LOCK); real `current_stage` at all 3 weather sites (operator LOCK); 4-detail-surfaces candlesticks/thumbnail-line (operator LOCK).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT attempt to fix the Codex MCP (operator is investigating separately); use the `codex exec` CLI backstop with INLINE artifacts.
- DO NOT widen scope to SB4/SB5 or Phase 15+; DO NOT touch the v22 temporal-log substrate.

---

## §8 Return report shape
Mirror prior writing-plans return reports (15 items): final HEAD + commit breakdown (Codex round attribution); Codex chain + convergent shape; plan line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L7 + the §1.3 OQ dispositions); residual OQs locked; Codex Major accepted (ZERO preferred); per-task acceptance summary; test surface (sum-check); forward-binding lessons for executing-plans; schema impact verdict (v23 DESIGNED); cumulative gotcha application; worktree teardown; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness summary (per-renderer visual-gate runbook ready).

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-3-chart-surface-uniformity-writing-plans`. Dir `.worktrees/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans/`.
- **Codex MCP chain count:** SINGLE chain (OQ-chain LOCK). MCP off-purview (operator investigating); `codex exec` CLI + inline artifacts is the backstop.
- **Expected duration:** ~2-3 hours writing-plans + ~30-90 min Codex chain.

---

*End of brief. Phase 14 Sub-bundle 3 writing-plans dispatch -- produce a per-task implementation plan from the 494-line brainstorm spec (mplfinance candlesticks on 4 detail surfaces + V2.G2 ticker_detail v23 rename + P14.N1 thumbnail substrate + P14.N4 BULZ zones + P14.N8 real current_stage at 3 weather sites + S6 reposition; ~1500-2800 lines; SINGLE Codex chain). The 11 operator-LOCKed OQ dispositions are in §1.3; HOLD THE LINE. The rendered chart is the BINDING operator-witnessed visual gate (matplotlib). OUTPUT: implementation plan the executing-plans phase can dispatch directly.*
