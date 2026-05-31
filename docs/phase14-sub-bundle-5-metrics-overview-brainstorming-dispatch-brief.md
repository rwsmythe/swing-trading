# Phase 14 Sub-bundle 5 -- Metrics Overview -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **metrics overview** sub-bundle (**P14.N5**) -- the LAST Phase 14 sub-bundle. Turn the existing text-only `/metrics` index into a **graphics-driven overview dashboard**: each of the 9 metric surfaces gets an at-a-glance **headline stat + a sparkline/mini-chart where genuine trend data exists**, with clickthrough drill-down to the existing per-surface routes preserved. This is a **read-mostly UX sub-bundle** that REUSES the existing metric computations + the SB3/SB4 chart infrastructure -- NOT a new-metrics or new-data-path sub-bundle.

**Brief:** `docs/phase14-sub-bundle-5-metrics-overview-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at `bf7e071`; Sec 9.1 LOCKs at `7a558e4`. **SB1 (data-wiring) SHIPPED `e323339`; SB2 (temporal log v22) SHIPPED `27f8007`; SB3 (chart-surface uniformity v23) SHIPPED `edd098d`; SB4 (review + journal UX) SHIPPED end-to-end `31da4a5`** (operator-witnessed gate PASS; 6905 fast tests green; render lock + render-direct charts live). Housekeeping at `07bdaa6`. Main HEAD at SB5 brainstorming dispatch: `07bdaa6`. **SB5 is the FINAL sub-bundle; Phase 14 close-out (Sec 9.1 Q6) follows.**

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~690+ cumulative ZERO Co-Authored-By trailer drift; **Schema v23 LOCKED -- SB5 likely introduces NO schema change** (render-direct / inline-SVG over existing metric data; a `chart_renders` surface-enum widening is the only realistic v24 trigger and is avoidable); L2 LOCK preserved.

**Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence. Spec line target **~500-800 lines** (a single overview surface enhancing an existing index + a per-surface card/sparkline contract; smaller than SB4's P14.N6).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end (Sec 9.1 Q7 + gotcha #36 caveat -- pure UX). **Run to CONVERGENCE** (zero new criticals AND zero new majors); the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); may exceed 5 rounds; do NOT stop while majors surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.2 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt the MCP tools.** The `adversarial-critic` skill auto-routes to a WSL Codex fallback that reads the worktree from disk + appends findings to `.copowers-findings.md`. **Preferred: invoke `copowers:brainstorming` normally.** Direct WSL invocation: `wsl.exe bash -ilc` (INTERACTIVE login -- node22 PATH is in `~/.bashrc`), `codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/<this-worktree> - < <promptfile>` (R1) / `... codex exec resume --last -c sandbox_mode="read-only" ...` (R2+). The worktree `.git` points to a Windows path WSL can't resolve, so pre-generate the diff on Windows and have Codex read the file + on-disk files. See memory `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation`.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-5-metrics-overview-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase14-commissioning-brief.md`** -- especially **Sec 2.4** (metrics overview sub-bundle: NEW `/metrics` index with overview cards summarizing the 9 surfaces with sparkline/mini-chart graphics; drill-down preserved; graphics-library decision; couples with P14.N6 at the viz-library decision point -- RESOLVED at SB4 to matplotlib) + **Sec 9.1 LOCKs** (Q1 sequencing, Q2 serial, **Q5 matplotlib SVG / no JS**, Q6 operator-witnessed close-out, Q7 Codex chain discretion).

3. **`docs/phase3e-todo.md`** -- the **2026-05-27 PM #2** P14.N5 5-field detail block (the operator framing: "Metrics page needs to show some kind of overall dashboard so the pages don't need to be navigated to except as a drill down. Ideally some kind of graphics would help display the information better rather than the current pure text.") + the SB4 EXECUTING-PLANS SHIPPED top entry (the chart infra + render lock SB5 reuses).

4. **CLAUDE.md** (compressed gotchas) -- especially: **matplotlib mathtext** (ASCII annotation text; manual visual verification non-optional, IF matplotlib sparklines are chosen); **shared `base.html.j2` -- a new `vm.foo` field needs a safe default on EVERY base VM** (the metrics VMs inherit `BaseLayoutVM`); **HTMX browser-only failure surfaces** (IF the overview lazy-loads cards or has interactive elements); **Cache + executor race**; **Weather/session-anchor read/write** (the metrics surfaces use backward-looking `last_completed_session` anchors -- preserve). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature verify; re-grep at writing-plans), **#4** (SQL/data-shape verify -- which surfaces actually carry series data), **Expansion #10c** (renderer-kwargs uniformity if matplotlib charts reused).

5. **Production code surfaces to read BEFORE drafting (architectural anchors -- ORCHESTRATOR-VERIFIED at dispatch; re-grep at writing-plans per #2).** **KEY brief-vs-reality finding: the `/metrics` index ALREADY EXISTS as a TEXT navigator** -- P14.N5 is an ENHANCEMENT (graphics + headline stats on the cards), NOT a greenfield route.
   - **The existing index (ENHANCE this):** `GET /metrics` -> `metrics_index` (`swing/web/routes/metrics.py:50`) -> `build_metrics_index_vm(conn)` -> `MetricsIndexVM(BaseLayoutVM)` (`swing/web/view_models/metrics/index.py:91`/`:97`) -> `metrics/index.html.j2` (a static list of `vm.surfaces` links). The 9 surfaces are the hand-maintained `_SURFACES` tuple of `MetricsIndexSurface` at `swing/web/view_models/metrics/index.py:36`.
   - **The 9 surface routes (drill-down targets; do NOT modify their data logic):** `/metrics/trade-process` (`:65`), `/metrics/hypothesis-progress` (`:262`), `/metrics/tier-comparison` (`:82`), `/metrics/capital-friction` (`:144`), `/metrics/maturity-stage` (`:169`), `/metrics/identification-funnel` (`:194`), `/metrics/deviation-outcome` (`:112`), `/metrics/process-grade-trend` (`:216`), `/metrics/pattern-outcomes` (`:234`) -- each builds its `build_*_vm(cfg[, ...])` (`swing/web/view_models/metrics/*.py`) over `swing/metrics/*.py` `compute_*` functions.
   - **WHICH surfaces carry sparkline-able SERIES data (the load-bearing data-shape finding):** ONLY THREE -- `capital_friction` (`compute_capital_friction:509` -> `trend_runs`, 30-session window), `identification_funnel` (`compute_identification_funnel:206` -> `trend_runs`, 30-session window), `process_grade_trend` (`compute_process_grade_trend:524` -> `rolling_series`, 7 metrics x 30-trade rolling). The OTHER SIX (trade_process, hypothesis_progress, tier_comparison, maturity_stage, deviation_outcome, pattern_outcomes) are POINT estimates / per-row tables with NO multi-run trend -> they get a HEADLINE STAT, not a fabricated sparkline.
   - **PRECEDENT -- `process_grade_trend` already renders an INLINE `<polyline>` SVG (NOT matplotlib):** `swing/web/templates/metrics/process_grade_trend.html.j2` renders `RollingSeriesDisplay.svg_polyline_points` (`swing/web/view_models/metrics/process_grade_trend.py:70`) as a hand-built `<polyline>` per a prior "NO matplotlib" LOCK. This is the central sparkline-tech OQ (see §3 OQ-1).
   - **Chart-infra reuse (IF matplotlib sparklines):** `swing/web/charts.py` -- `_svg_bytes_from_fig:111` (generic figure->SVG bytes), `_render_candles_fig:433`, `_normalize_ohlc_for_mpf:255`, the **process-wide render lock** `_RENDER_LOCK = threading.RLock()` (`:83`) + the `@_serialized_render` decorator (`:86`), the Okabe-Ito `_MA_COLORS` palette (`:256`); `swing/web/trade_charts.py` -- the SB4 render-direct thumbnail `render_trade_window_thumbnail_svg:87` (2.4x1.4in proves tiny-figure viability). **Reuse, do not re-implement** (L5).
   - **BaseLayoutVM contract:** `swing/web/view_models/metrics/shared.py:28` -- `MetricsIndexVM` already inherits it (session_date + the banner/discrepancy/auto-correction fields). Any new overview VM fields get safe defaults on the base contract.
   - **Metrics-wiring correctness (Item 7 / T-T4.SB.2):** the 4 hypothesis-cohort surfaces were fixed to delimiter-aware matching (`swing/metrics/label_match.py`; audit at `swing/diagnostics/metrics_wiring_audit.py:55`). The overview MUST consume the existing (post-fix correct) `build_*_vm`/`compute_*` outputs -- do NOT re-derive metric values.
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`); `chart_renders.surface` enum `("watchlist_row","ticker_detail","position_detail","market_weather","theme2_annotated")` (`swing/data/models.py:100`). SB5 adds NO surface enum (render-direct / inline-SVG) -> NO migration.

6. **`docs/superpowers/specs/2026-05-30-phase14-sub-bundle-4-review-journal-ux-design.md`** (the SB4 spec -- REFERENCE for the render-direct + render-lock pattern SB5 may reuse) + the SB3 spec (the mplfinance renderers).

7. **`docs/orchestrator-context.md`** §"Pre-Codex review + brief-authoring disciplines".

8. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (the WSL Codex transport), `feedback_codex_round_limit_suspended` (run to convergence), `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose), `feedback_visual_gate_both_render_and_browser` (the operator-witnessed gate pattern; re-confirm for SB5).

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs
- **Q1** sequencing = ... -> charts -> review+journal (SHIPPED) -> **metrics overview (THIS, LAST)**; **Q2** SERIAL
- **Q5** graphics = **matplotlib SVG; NO JS charting library** (the binding constraint is no-JS, static server-rendered graphics). *Note:* the existing `process_grade_trend` satisfies no-JS via a hand-built inline `<polyline>` SVG -- whether SB5 sparklines use matplotlib OR the lighter inline-`<polyline>` approach is OQ-1 (both are no-JS static SVG).
- **Q6** operator browser-witnessed verification at merge (the rendered overview is the BINDING visual gate)
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** for THIS brainstorming (pure UX)

### §1.2 Sub-bundle 5 phase-specific LOCKs (this brief)
- **L1** Scope = **P14.N5 metrics overview ONLY** -- enhance the existing `/metrics` index into a graphics-driven overview dashboard (per-surface headline stat + sparkline-where-genuine-trend-exists; drill-down preserved). Do NOT modify the 9 per-surface routes' DATA logic; do NOT add new metric computations/algorithms; do NOT widen to SB1-SB4 surfaces or Phase 15+.
- **L2** **Read-mostly; NO new data path.** REUSE the existing `build_*_vm`/`compute_*` outputs (post-wiring-fix correct); the overview is a pure READ/aggregate surface. ZERO new metric computation; ZERO `chart_renders`/domain writes.
- **L3** **Likely NO schema change.** Sparklines render-direct (matplotlib) or inline-SVG -> no `chart_renders` writes. A NEW `chart_renders` surface enum (only if cached matplotlib sparklines are chosen -- NOT recommended) would be the sole v24 trigger (STRICT `pre_version == 23`; gotcha #11 paired + #9). **Recommend render-direct / inline-SVG to stay schema-free; confirm at brainstorm.** Do NOT touch v22/v23 substrate.
- **L4** **Honesty floor (BINDING; mirrors the existing metrics n<5 suppression discipline):** do NOT fabricate a sparkline from insufficient/point-estimate-only data. ONLY the 3 trend-bearing surfaces (capital_friction, identification_funnel, process_grade_trend) get sparklines; the other 6 show a headline stat or an honest suppressed/empty state. A sparkline must reflect REAL series data the drill-down also shows.
- **L5** **Visual-gate discipline; reuse the SB3/SB4 helpers.** IF matplotlib: byte/string tests INSUFFICIENT -> operator-witnessed rendered gate; ASCII annotation text (no mathtext metachars); reuse `_svg_bytes_from_fig`/`_render_candles_fig`/`_RENDER_LOCK` -- no re-implementation. IF inline-SVG: the rendered card is still the binding visual gate.
- **L6** **Render-lock contention (assess at brainstorm):** IF matplotlib sparklines, every overview load renders N figures serialized through `_RENDER_LOCK` (potential latency / a render-storm). Mitigate (lazy-load, cache, or prefer inline-SVG). The lightweight inline-`<polyline>` approach has NO render-lock contention.
- **L7** **BaseLayoutVM contract:** the enhanced `MetricsIndexVM` (already a `BaseLayoutVM`) keeps session_date + the banner/discrepancy fields; any NEW VM field gets a safe default across the base contract.
- **L8** **HTMX disciplines** apply to any lazy-loaded/interactive overview card (the trinity; operator-witnessed browser verification). The existing metrics pages are pure server-rendered HTML (no HTMX) -- if SB5 stays that way, simpler.
- **L9** **Close-out readiness:** SB5 is the LAST sub-bundle. The spec/return report should note Phase 14 close-out readiness (all 5 merged + the operator-witnessed cross-sub-bundle integration review per Sec 9.1 Q6) + the banked Phase 14 follow-ups to sequence (Schwab daily-bar wiring; market_weather 200MA; theme2 vcp crowding; `_bulz_*` rename).

---

## §2 Spec scope to design

### §2.1 The overview dashboard (enhance the existing `/metrics` index)
- Decide: enhance `GET /metrics` (the existing index) IN PLACE into the overview dashboard (recommended -- it's already the landing), vs a NEW `/metrics/overview` route (index stays). Define the card grid: one card per surface (the `_SURFACES` registry), each with: a label, a clickthrough to the drill-down route (already present), a **headline stat** (the at-a-glance number), and a **sparkline** where the surface carries trend data.
- Define the `MetricsIndexVM` enhancement (or a new overview VM): per-card { surface, headline_stat, sparkline (bytes/inline-svg/None), suppressed_reason }. Reuse the existing `build_*_vm`/`compute_*` outputs to populate headline + series.

### §2.2 The sparkline contract (the 3 trend-bearing surfaces)
- capital_friction `trend_runs` / identification_funnel `trend_runs` / process_grade_trend `rolling_series` -> a sparkline each. Define: which series per surface, the dimensions, the n<5 suppression, the ASCII/no-mathtext discipline (if matplotlib), and the render path (OQ-1).
- The other 6 surfaces: a headline stat only (define which number per surface) + an honest empty/suppressed state.

### §2.3 The headline-stat contract (all 9)
- Per surface, the single at-a-glance figure (e.g. trade_process -> expectancy_R; capital_friction -> current utilization/heat; funnel -> A+ count; pattern_outcomes -> trigger rate). Reuse the existing VM/result fields; honesty floor for suppressed surfaces.

### §2.4 Operator-witnessed gate enumeration
- S1 fast suite + ruff; S2 schema (assert NO migration unless the cached-matplotlib OQ lands "new surface"); S3+ the rendered overview in a real browser -- cards render with headline stats + sparklines (the 3 trend surfaces) + honest suppressed states (the 6 others) + working drill-down. The rendered overview is the BINDING visual gate.

---

## §3 Open questions (Codex SHOULD surface answers; operator triage at writing-plans dispatch)

1. **OQ-1 (sparkline tech -- THE key decision):** matplotlib-SVG sparklines (Q5 consistency + reuse `_svg_bytes_from_fig`/`_render_candles_fig`; but per-card `_RENDER_LOCK` serialization + matplotlib figure cost on every overview load) **vs** lightweight hand-built inline-`<polyline>` SVG (the EXISTING `process_grade_trend` precedent; no render-lock contention; no matplotlib per-card cost; still no-JS static SVG). **Recommend lean inline-`<polyline>` for tiny sparklines** unless the operator wants matplotlib consistency -- HOLD for operator triage.
2. **OQ-2 (sparkline breadth):** the 3 trend-bearing surfaces only (recommend) vs attempt all 9 (the 6 point-estimate surfaces would need fabricated/degenerate sparklines -- violates the honesty floor L4).
3. **OQ-3 (route shape):** enhance `/metrics` in place (recommend) vs a new `/metrics/overview` route.
4. **OQ-4 (headline stat per surface):** confirm the single at-a-glance figure for each of the 9.
5. **OQ-5 (render path / cache):** render-direct / inline (no schema; recommend) vs cached `chart_renders` surface (v24).
6. **OQ-6 (lazy-load):** render all cards inline on the overview load vs HTMX lazy-load per card (matters more if matplotlib).
7. **OQ-7 (Codex chain count at writing-plans):** single (pure-UX) vs two-chain (unlikely -- no analytical artifact).

---

## §4 OUT OF SCOPE (do not design into V1)
- Any new metric COMPUTATION / algorithm / surface (reuse the existing 9); changes to the 9 per-surface routes' data logic
- SB1-SB4 surfaces (charts, review, journal, temporal log); the v22/v23 substrate
- Schema beyond an optional v24 (only if §3 OQ-5 lands "cached matplotlib sparklines"; recommend avoiding)
- A new trade-mutation / data-write path (L2)
- JS-based charting libraries (Q5 no-JS)
- The banked Phase 14 follow-ups (Schwab daily-bar wiring; market_weather 200MA; theme2 vcp crowding; `_bulz_*` rename) -- sequence at close-out, not here
- Phase 15+ scope

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Brief-vs-production-signature/data-shape verification (#2/#4)** -- cite real route/VM/compute names (`metrics_index`, `build_metrics_index_vm`, `_SURFACES`, `compute_capital_friction.trend_runs`, etc.); CONFIRM the index-already-exists correction + the 3-of-9-surfaces-have-series finding (do not promise sparklines on point-estimate surfaces).
2. **Honesty floor (L4)** -- no fabricated sparklines; n<5 suppression mirrored; sparkline reflects real drill-down series.
3. **Sparkline-tech decision (OQ-1)** -- the spec lays out matplotlib-vs-inline-polyline with the render-lock-contention tradeoff; HOLD for operator (don't unilaterally pick matplotlib just because Q5 says "matplotlib SVG" -- the existing precedent is inline-polyline + Q5's real intent is no-JS).
4. **No schema (L3)** -- assert NO migration unless cached-matplotlib chosen; if so, gotcha #11 paired + #9 + STRICT `pre_version == 23`.
5. **Render-lock contention (L6)** -- if matplotlib, the N-sparkline render-storm is assessed (lazy/cache/inline mitigation).
6. **Reuse, no re-implementation (L5)** -- the SB3/SB4 helpers; matplotlib ASCII + visual gate; byte/string insufficient.
7. **BaseLayoutVM (L7)** + HTMX trinity (L8 if interactive) + shared-`base.html.j2` field defaults.
8. **Metrics-wiring correctness** -- the overview consumes the post-T-T4.SB.2 (delimiter-aware) values; no re-derivation.
9. **L2 Schwab source-grep** continues passing; ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-5-metrics-overview-design.md`** (mirror the SB4 brainstorm spec format):
§1 Architecture overview (the index-enhancement + the 3-of-9-series finding) · §2 Pre-locked decisions (Sec 9.1 + L1-L9) · §3 Module touch list (metrics route + index VM + index template + a sparkline helper [matplotlib or inline]; reuse charts.py/trade_charts.py if matplotlib) · §4 Overview dashboard design · §5 Sparkline contract (3 trend surfaces) · §6 Headline-stat contract (all 9) · §7 Sparkline-tech decision (OQ-1; matplotlib vs inline-polyline + tradeoffs) · §8 Render path / schema (NO change, or v24) · §9 Sub-bundle decomposition recommendation · §10 Test fixture strategy + visual-gate enumeration · §11 Schema impact (NO change) · §12 V1 simplifications + V2 candidates · §13 Operator decision items (OQs) · §14 Cumulative discipline compliance · §15 Phase 14 close-out readiness note.

**Target ~500-800 lines.** Commit stem: `docs(phase14-sub-bundle-5-spec): brainstorm <draft|R1|...> -- ...` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a surface you assumed has series data turns out to be point-estimate-only (or vice-versa), ESCALATE / re-scope -- the 3-of-9 finding is orchestrator-verified but re-grep the `compute_*` return shapes at the spec.
- If the overview appears to need a new metric computation or a data-write, ESCALATE -- L2 forbids it (reuse the existing outputs).
- If the schema can be avoided by render-direct/inline, PREFER that (L3).
- HOLD THE LINE: no-JS graphics (Q5); single chain run-to-convergence; the honesty floor (no fabricated sparklines); reuse the existing metric computations.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead in the VS Code extension); use the WSL Codex fallback.
- DO NOT widen scope to other Phase 14 surfaces / the banked follow-ups / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §8 Return report shape

Mirror the SB4 brainstorm return report (15 items): final HEAD + commit breakdown; Codex round chain + convergent shape (EVIDENCE it ran genuinely via WSL -- cite `.copowers-findings.md` rounds); spec line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L9); OQs resolved + deferred; Codex Major findings accepted (ZERO preferred); the index-already-exists + 3-of-9-series corrections + any other brief-vs-production corrections; V1 simplifications + V2 candidates; forward-binding lessons for writing-plans; sub-bundle decomposition recommendation; schema impact verdict (NO change, or v24); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness summary + the Phase 14 close-out readiness note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-5-metrics-overview-brainstorming`. Dir `.worktrees/phase14-sub-bundle-5-metrics-overview-brainstorming/`. Branch from main HEAD `07bdaa6`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain at end (Sec 9.1 Q7), run to convergence via the WSL Codex fallback (copowers v2.0.2; MCP dead in the VS Code extension).
- **Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence.

---

*End of brief. Phase 14 Sub-bundle 5 (the FINAL sub-bundle) brainstorming dispatch -- produce a design spec for the metrics overview (enhance the existing text-only `/metrics` index into a graphics-driven dashboard: per-surface headline stat + sparkline-where-genuine-trend-exists [only 3 of the 9 surfaces carry series data]; drill-down preserved; ~500-800 lines; single Codex chain to convergence). The central decision is OQ-1 (matplotlib-SVG vs the existing lighter inline-`<polyline>` precedent -- both no-JS). Read-mostly over existing metric computations; the `/metrics` index ALREADY EXISTS (enhancement, not greenfield); likely NO schema change. The rendered overview is the BINDING operator-witnessed gate. After SB5: Phase 14 close-out. OUTPUT: a design spec the writing-plans phase can derive a plan from.*
