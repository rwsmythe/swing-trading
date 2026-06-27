# Phase 14 Sub-bundle 3 -- Chart-Surface Uniformity -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 3 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for **chart-surface uniformity** -- the cluster of chart-rendering quality + consistency items carried over from the V2 gate findings + operator backlog: **V2.G1** (candlestick discipline) + **V2.G2** (`hyprec_detail` -> `ticker_detail` rename; v23 schema migration) + **P14.N1** (chart thumbnail surfaces) + **P14.N2** (candlestick discipline / renderer uniformity) + **P14.N4** (BULZ entry/stop/target shaded zones) + **P14.N8** (weather-chart refresh-handler regression) + the **S6 cosmetic** (flat_base duration-text/legend overlap surfaced at Sub-bundle 2's gate). The unifying thread: the 5 SVG renderers in `swing/web/charts.py` have drifted in candlestick discipline, annotation placement, and renderer-kwargs, and one surface needs a semantic rename (v23).

**Brief:** `docs/phase14-sub-bundle-3-chart-surface-uniformity-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; **Sub-bundle 1 (data-wiring) SHIPPED end-to-end at `e323339`**; **Sub-bundle 2 (temporal log V1+; v22) SHIPPED end-to-end at `27f8007`** (operator-witnessed gate PASS; v22 live); housekeeping at `d508343`. Main HEAD at Sub-bundle 3 brainstorming dispatch: `d508343`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING (as of `665cab0` the CLAUDE.md Gotchas section is compressed to trigger+fix; the "Expansion #N" process/review + brief-authoring disciplines were RELOCATED to `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~620+ cumulative ZERO Co-Authored-By trailer drift; 49th cumulative C.C lesson #6 validation NOTABLE at Sub-bundle 2 executing-plans SHIPPED; **Schema v22 LOCKED -- Sub-bundle 3 INTRODUCES v23** (the V2.G2 rename migration; backup-gate STRICT `pre_version == 22` per gotcha #11); L2 LOCK preserved (multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

**Expected duration:** ~3-5 hours brainstorming + 2-4 Codex rounds. Spec line target **~600-900 lines** (multiple chart items + a v23 data-migration design + renderer-uniformity audit across 5 renderers).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` with adversarial Codex MCP review after the spec is written.
- **Codex chain count: SINGLE chain at end** for THIS brainstorming phase per Sec 9.1 Q7 LOCK + gotcha #36 caveat (pure UX/chart sub-bundle without a substantive analytical artifact). Reconsider at writing-plans if the v23 data-migration surfaces substrate-changing risk warranting the two-chain default.
- **Codex MCP transport (FB-N1):** the copowers Codex MCP launcher fix (`cmd /c codex mcp-server`) is now applied to all three `.mcp.json` copies (1.0.0/2.0.0/marketplace). **Restart Claude Code before this dispatch** so the MCP binds; if it still times out, the `codex exec` CLI with INLINE-pasted artifacts is the transport-independent backstop (codex-cli `-s read-only` cannot spawn shells on this host; paste the spec inline). See memory `feedback_copowers_codex_mcp_windows_launcher`.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-3-chart-surface-uniformity-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase14-commissioning-brief.md`** -- especially **Sec 2.1** (chart-surface uniformity sub-bundle architectural notes: gotcha #11 + Expansion #10c renderer-kwargs uniformity LOCK; V2.G2 v23 rename + data-migration discipline; P14.N2 likely subsumes V2.G1; BULZ shaded zones via axhspan/axvspan/fill_between) + **Sec 6** (cross-cutting watch items) + **Sec 9.1 LOCKs** (Q1 sequencing, Q2 serial, Q4 V2.G2 rename in THIS sub-bundle as v23, Q6 operator-witnessed close-out, Q7 Codex chain discretion).

3. **`docs/phase3e-todo.md`** -- the Phase 14 preliminary scope roll-up (2026-05-27 PM #2): the 5-field detail blocks for **V2.G1, V2.G2, P14.N1, P14.N2, P14.N4**. Also the **P14.N8 banking entry** (`9b2b81e`) + the Sub-bundle 2 SHIPPED top entry (which banked the S6 duration-text/legend cosmetic for THIS sub-bundle).

4. **CLAUDE.md** (compressed gotchas) -- especially:
   - **Matplotlib mathtext** fires on `$` `^` `_` and unbalanced `\` -> omit metacharacters from titles/labels/annotations; **manual visual verification of rendered text is non-optional** (the binding operator-witnessed gate for chart work)
   - **(#11)** Schema-CHECK + Python-constant + dataclass-validator paired (same task) + read-path `_row_to_*` mappers same task + migration backup-gate STRICT `pre_version == 22` (the V2.G2 v23 rename)
   - **(#9)** executescript implicit COMMIT -> explicit BEGIN/COMMIT/ROLLBACK migration-runner discipline
   - **HTMX OOB-swap / fragment** disciplines (if any thumbnail/refresh surface is HTMX-driven) + **HTMX form browser-only failure surfaces** + **HX-Redirect target-route** discipline
   - **Cache + executor race** + **External-API empty-result transient (F6)** + **OHLCV fetch scope = open-trade tickers** (chart bar sourcing)
   - **Session-anchor read/write mismatch** + **Weather lookup must NOT query by action_session** (P14.N8 weather chart)
   - AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- especially **Expansion #10** (architecture-location audit + sub-discipline **(c) renderer-kwargs uniformity LOCK + cache-collision discriminating tests when a surface enum is reused**) + **#2** (brief-vs-signature) + **#4** (SQL column verification) + **#11** (taxonomy/attribution propagation -- the surface-enum rename propagates everywhere).

5. **Production code surfaces to read BEFORE drafting (architectural anchors; re-grep at writing-plans per #2):**
   - `swing/web/charts.py` -- the 5 SVG renderers: `render_watchlist_thumbnail_svg:180`, `render_hyprec_detail_svg:226`, `render_position_detail_svg:284`, `render_market_weather_svg:334`, `render_theme2_annotated_svg:481` (+ the shared helpers `_close_series`, `_figsize_inches`, `_assert_ticker_safe`, the `_annotate_*` family). This is the renderer-uniformity surface.
   - `swing/web/chart_jit.py` + `swing/data/repos/chart_renders.py` -- the JIT cache + `chart_renders` persistence (surface enum; `refresh_chart_render`; cache-key shape).
   - `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:179-219` -- the `chart_renders.surface` CHECK enum (`'watchlist_row','hyprec_detail','position_detail','market_weather','theme2_annotated', ...`) + the partial unique indexes that reference `hyprec_detail` (the V2.G2 rename must migrate the CHECK + the indexes + existing rows).
   - `swing/data/migrations/0022_phase14_temporal_log.sql` + `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION = 22`; `_phase14_backup_gate`; `run_migrations`) -- the v23 migration template + backup-gate insertion point.
   - `swing/web/routes/dashboard.py:~112-120` -- the **P14.N8** weather-chart refresh handler: `render_market_weather_svg(bars=bars, trend_template_state="n/a")` -- the hardcoded `"n/a"` + (likely) missing gridlines kwarg vs the pipeline-time render path. Find the pipeline-time `render_market_weather_svg` call site + diff the kwargs (Expansion #10c uniformity).
   - `swing/web/routes/patterns.py` + `swing/web/view_models/patterns/` + any templates rendering the `hyprec_detail` surface (callers of the renamed surface/renderer).

6. **`docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md`** + **`docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md`** -- REFERENCE for spec shape + Codex-catch documentation precedent + the cumulative forward-binding lessons.

7. **`docs/orchestrator-context.md`** §"Currently in-flight work" (Phase 14 in-flight; Sub-bundle 3 next) + §"Pre-Codex review + brief-authoring disciplines".

8. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_copowers_codex_mcp_windows_launcher` (FB-N1: restart binds MCP; CLI backstop + read-only-sandbox inline-paste wrinkle)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`)
   - `feedback_verify_regression_test_arithmetic` (relevant for the BULZ zone-boundary + the candlestick-vs-line render tests)

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)
- **Q1** sequencing = data-wiring (SHIPPED) -> temporal log (SHIPPED) -> **chart-surface uniformity (THIS SUB-BUNDLE)** -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q4** V2.G2 schema rename = **ship the `hyprec_detail` -> `ticker_detail` rename in THIS sub-bundle as a v23 migration** (data-migration discipline for existing `chart_renders` rows per gotcha #11 LOCK)
- **Q6** close-out = operator browser-witnessed verification at merge (the rendered chart is the BINDING visual gate per the matplotlib gotcha)
- **Q7** Codex chain count = orchestrator discretion; **SINGLE chain** for THIS brainstorming (pure UX/chart; gotcha #36 caveat)

### §1.2 Sub-bundle 3 phase-specific LOCKs (this brief)
- **L1** Scope = V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + P14.N8 + the S6 cosmetic ONLY. Do NOT widen to other Phase 14 items (review+journal / metrics) or Phase 15+.
- **L2** **v23 schema migration** for the V2.G2 rename -- gotcha #11 paired discipline (CHECK enum + Python constants + any dataclass validator + read-path `_row_to_*` mapper, ALL in one task) + gotcha #9 explicit BEGIN/COMMIT/ROLLBACK + backup-gate STRICT `pre_version == 22`. The rename MUST migrate: the `surface` CHECK enum, the partial unique indexes referencing `hyprec_detail`, AND existing `chart_renders` rows (`UPDATE ... SET surface='ticker_detail' WHERE surface='hyprec_detail'`).
- **L3** **Renderer-kwargs uniformity LOCK** (Expansion #10c): when a renderer is invoked from 2+ call sites (e.g. `render_market_weather_svg` from the pipeline-time path AND the dashboard refresh handler), ALL call sites MUST pass the SAME kwargs (P14.N8's bug is the refresh path passing `trend_template_state="n/a"` + missing gridlines vs the pipeline path). Cache-collision discriminating tests at the `chart_renders` surface enum where surfaces are reused.
- **L4** **Matplotlib visual-gate discipline:** byte/format/string-equality tests are INSUFFICIENT for chart-render correctness; the spec MUST enumerate an operator-witnessed visual gate (rendered SVG/PNG) for each changed renderer. ASCII-only annotation text (no `$`/`^`/`_`/unbalanced `\` -> mathtext corruption).
- **L5** **Backwards-compat at the rename:** no orphaned `hyprec_detail` references may remain after V2.G2 (grep ALL `swing/` + templates + tests for the old surface string + the old renderer name); the rename is atomic across schema + Python + templates + tests.
- **L6** L2 LOCK preserved -- ZERO new `schwabdev.Client.*` call sites; the source-grep test MUST continue passing.
- **L7** P14.N8 is a pre-existing Phase 13 regression (revealed, not introduced, by Sub-bundle 1's V2.G4 fix); the fix is to make the refresh-handler render MATCH the pipeline-time render (real `trend_template_state` + gridlines), NOT to suppress it.

---

## §2 Spec scope to design

### §2.1 Renderer-uniformity audit (V2.G1 + P14.N2; likely a single audit closing both)
- Audit all 5 renderers in `charts.py` for candlestick discipline: do they plot a close-LINE or OHLC candlesticks? P14.N2 candlestick discipline likely subsumes V2.G1. Spec defines the canonical candlestick rendering + which renderers adopt it (V1 scope: which surfaces get candlesticks vs stay line).
- Shared-helper extraction (if the candlestick logic + axis/gridline/legend conventions should be a shared helper for uniformity).
- ASCII annotation discipline across all renderers (matplotlib mathtext).

### §2.2 V2.G2 rename `hyprec_detail` -> `ticker_detail` (v23 migration)
- v23 migration `00XX_*.sql`: CHECK enum update + partial-unique-index migration + `UPDATE` existing rows + backup-gate STRICT `pre_version == 22`.
- Python: surface constants + any `Literal`/frozenset mirrors + `refresh_chart_render` callers + the renderer rename `render_hyprec_detail_svg` -> `render_ticker_detail_svg` (decide: rename the function too, or just the surface enum value? spec recommends + locks).
- Templates + routes + view-models + tests referencing the old surface/renderer (L5 atomic rename).

### §2.3 P14.N1 chart thumbnail surfaces
- Define the thumbnail rendering contract (small-chart surfaces) + where they're consumed (couples with the future review+journal sub-bundle per commissioning Sec 2.3, but Sub-bundle 3 ships the thumbnail RENDERER substrate). Reuse `render_watchlist_thumbnail_svg` patterns.

### §2.4 P14.N4 BULZ entry/stop/target shaded zones
- In `render_position_detail_svg` (BULZ is an open position): add green/yellow shaded zones for entry/stop/target. Investigate `axhspan` / `fill_between`. Define the zone-boundary semantics (entry-to-target = green? stop-to-entry = yellow/red?) + the data source for entry/stop/target levels (open-trade row).

### §2.5 P14.N8 weather-chart refresh-handler regression
- `dashboard.py:~117` `render_market_weather_svg(bars=bars, trend_template_state="n/a")` -> compute the REAL `trend_template_state` (match the pipeline-time render's source) + restore gridlines (Expansion #10c renderer-kwargs uniformity). Spec defines the trend-state source + the uniform kwarg set + a discriminating test asserting the refresh-path kwargs match the pipeline-path kwargs.

### §2.6 S6 cosmetic (flat_base duration-text/legend overlap)
- In `render_theme2_annotated_svg`, the `flat_base` "duration: N days" text at axes (0.02, 0.92) overlaps the legend box at upper-left. Reposition (or move the legend) so they don't collide. Minor; bundle into the renderer-uniformity audit.

### §2.7 Operator-witnessed gate enumeration
- S1 fast suite + ruff; S2 v23 applied (`schema_version=23`; `chart_renders` rows migrated `hyprec_detail`->`ticker_detail`; backup written); S3+ per-renderer visual gates (rendered SVG/PNG for each changed surface -- candlesticks, BULZ zones, weather-chart trend+gridlines, theme2 duration-text placement); the rendered chart is the BINDING visual gate (matplotlib).

---

## §3 Open questions (Codex SHOULD surface answers; operator triage at writing-plans dispatch)

1. Candlestick scope -- which of the 5 renderers adopt candlesticks in V1 vs stay line? (all 5 uniform, or detail-surfaces only?)
2. V2.G2 -- rename the renderer FUNCTION (`render_hyprec_detail_svg` -> `render_ticker_detail_svg`) too, or only the surface enum value? (atomic-rename scope)
3. P14.N4 BULZ zone semantics -- exact entry/stop/target zone colors + boundaries + data source (open-trade row fields).
4. P14.N1 thumbnail -- ship the renderer substrate only in Sub-bundle 3, or also wire a consuming surface? (couples with review+journal Sub-bundle 4)
5. P14.N8 -- the real `trend_template_state` source for the refresh path (the pipeline-time computation site).
6. Shared-helper extraction -- candlestick + gridline + legend conventions as a shared helper, or per-renderer?
7. v23 data-migration -- in-migration `UPDATE` of existing `chart_renders` rows, or a separate backfill step? (recommend in-migration; it's a pure value rename).
8. Codex chain count at writing-plans -- single (pure-UX) vs two-chain (the v23 data-migration is substrate-touching)?

---

## §4 OUT OF SCOPE (do not design into V1)
- Review + journal UX (Sub-bundle 4) + metrics overview (Sub-bundle 5) -- per Sec 9.1 Q1 serial LOCK
- Temporal log changes (Sub-bundle 2 SHIPPED; do not modify v22 substrate)
- Schema migrations beyond v23
- NEW analytical artifacts / ruleset changes
- Schwab API integration changes (L2 LOCK)
- JS-based charting libraries (matplotlib SVG only, per Sec 9.1 Q5 precedent)
- Backfill of historical chart_renders bytes / re-rendering historical charts
- Phase 15+ scope

---

## §5 Adversarial review (Codex) -- watch items

Invoked by `copowers:brainstorming` after the spec draft. SINGLE chain (Q7); 2-4 round target.

1. **Brief-vs-production-signature verification (#2)** -- cite real renderer names + signatures (`render_*_svg`, `refresh_chart_render`, the `_annotate_*` family); re-grep at writing-plans.
2. **Schema-CHECK + constant + validator + read-path mapper paired (#11)** -- the V2.G2 v23 rename lands all layers in one task; backup-gate STRICT `pre_version == 22`; partial-unique-index migration; existing-row `UPDATE`.
3. **Migration runner discipline (#9)** -- explicit BEGIN/COMMIT/ROLLBACK; rollback-through-runner test for the v23 rename.
4. **Renderer-kwargs uniformity (Expansion #10c)** -- every multi-call-site renderer (esp. `render_market_weather_svg`) passes identical kwargs; cache-collision discriminating tests at reused surfaces.
5. **Taxonomy/attribution propagation (#11 promotion)** -- the `hyprec_detail`->`ticker_detail` rename propagates to schema + constants + renderer name + routes + templates + view-models + tests + the partial indexes; NO orphaned old references (L5).
6. **Matplotlib mathtext + visual-gate discipline** -- ASCII annotation text; per-renderer operator-witnessed visual gate; byte/string tests declared INSUFFICIENT.
7. **HTMX surfaces** -- if any thumbnail/refresh surface is HTMX-driven, the OOB-swap + HX-Request + 204/HX-Redirect + table-row-free-fragment disciplines apply.
8. **L2 LOCK source-grep** -- continues passing; ZERO new `schwabdev.Client.*` call sites.
9. **ASCII discipline (#16/#32)** -- declare scope across NEW files.
10. **Co-Authored-By footer suppression** + the trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-3-chart-surface-uniformity-design.md`** (mirror Sub-bundle 2 brainstorm spec format):
§1 Architecture overview · §2 Pre-locked operator decisions (Sec 9.1 + L1-L7) · §3 Module touch list (charts.py renderers + chart_jit + chart_renders repo + v23 migration + db.py + dashboard.py refresh handler + routes/templates) · §4 Renderer-uniformity audit (V2.G1+P14.N2) · §5 V2.G2 v23 rename design (migration + atomic Python/template/test rename) · §6 P14.N1 thumbnail substrate · §7 P14.N4 BULZ shaded zones · §8 P14.N8 refresh-handler uniformity fix · §9 S6 cosmetic · §10 Sub-bundle decomposition recommendation (single executing-plans dispatch?) · §11 Test fixture strategy (+ visual-gate enumeration) · §12 Schema impact analysis (v23) · §13 V1 simplifications + V2 candidates · §14 Operator decision items (OQs) · §15 Cumulative discipline compliance summary.

**Target line count: ~600-900 lines.** **Commit message stem:** `docs(phase14-sub-bundle-3-spec): brainstorm <draft|R1|...> -- ...` (keep the final `-m` paragraph plain prose).

---

## §7 If you get stuck
- If a renderer's candlestick adoption forces an OHLCV-bar-shape change NOT anticipated, ESCALATE (do not silently restructure).
- If Codex pushes back on the v23 rename being in THIS sub-bundle, HOLD THE LINE -- Sec 9.1 Q4 LOCK.
- If Codex pushes back on matplotlib SVG (proposes a JS charting lib), HOLD THE LINE -- Sec 9.1 Q5 precedent.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose (verify `%(trailers)` is `[]`).
- DO NOT widen scope to Sub-bundle 4/5 or Phase 15+.
- DO NOT modify the Sub-bundle 2 v22 temporal-log substrate.
- If the Codex MCP times out (FB-N1), restart + verify the active copowers version; else use `codex exec` CLI with INLINE artifacts.

---

## §8 Return report shape

Mirror the Sub-bundle 2 brainstorm return report (15 items): final HEAD + commit breakdown; Codex round chain + convergent shape; spec line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L7); OQs resolved + deferred; Codex Major findings accepted (ZERO preferred); V1 simplifications + V2 candidates; forward-binding lessons for writing-plans; sub-bundle decomposition recommendation; schema impact verdict (v23); cumulative gotcha application summary; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness summary.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-3-chart-surface-uniformity-brainstorming`. Dir `.worktrees/phase14-sub-bundle-3-chart-surface-uniformity-brainstorming/`.
- **Codex MCP chain count:** SINGLE chain at end (Sec 9.1 Q7). Restart for MCP; `codex exec` CLI + inline artifacts is the backstop (FB-N1).
- **Expected duration:** ~3-5 hours brainstorming + ~30-90 min Codex chain.

---

*End of brief. Phase 14 Sub-bundle 3 brainstorming dispatch -- produce a design spec for chart-surface uniformity (V2.G1 + V2.G2 v23 rename + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6 cosmetic; ~600-900 lines; single Codex chain). The unifying thread is renderer uniformity across the 5 `charts.py` SVG renderers + a v23 surface-enum rename. The rendered chart is the BINDING operator-witnessed visual gate (matplotlib gotcha). OUTPUT: design spec the writing-plans phase can derive an implementation plan from.*
