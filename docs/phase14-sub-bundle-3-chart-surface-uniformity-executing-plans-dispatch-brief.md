# Phase 14 Sub-bundle 3 -- Chart-Surface Uniformity -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 3 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed implementation plan to ship **chart-surface uniformity** to production code + tests: a **v23 schema migration** atomically renaming `hyprec_detail`->`ticker_detail` (CHECK enum + in-migration row `UPDATE`) across schema + Python + routes + view-models + templates + tests; a shared **mplfinance candlestick helper** adopted on the 4 detail surfaces (`ticker_detail` [renamed], `position_detail`, `market_weather`, `theme2_annotated`) with the watchlist thumbnail staying a line; **P14.N4 BULZ entry/stop/target zones** on `position_detail`; **P14.N2 50/200 MAs** on `market_weather`; **P14.N8 real `current_stage`** at the 2 live weather sites + an honest-`undefined` JIT default; **P14.N1 thumbnail renderer substrate** (substrate-only; consuming-surface wiring deferred to SB4); and **S6** repositioning the theme2 duration text to upper-right. This is a **pure UX/chart + value-rename sub-bundle** -- NOT a permanent append-only substrate (the v22 temporal-log substrate is UNTOUCHED). Plan is dispatch-ready per the writing-plans return report §15.

**Brief:** `docs/phase14-sub-bundle-3-chart-surface-uniformity-executing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; Sub-bundle 1 SHIPPED end-to-end at `e323339`; Sub-bundle 2 SHIPPED end-to-end at `27f8007` (v22 LIVE in the operator's real DB); **Sub-bundle 3 brainstorm SHIPPED at `f16735f`** (spec 494 lines; Codex single-chain CONVERGED R3); **writing-plans SHIPPED at `4fa20dd`** (plan 1311 lines; Codex single-chain CONVERGED R4, 0C+20M+6m all resolved in-place); housekeeping + orchestrator handoff at `b7fd46b`. **Main HEAD at executing-plans dispatch: `b7fd46b`.**

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING (compressed to trigger+fix as of `665cab0`; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~624+ cumulative ZERO Co-Authored-By trailer drift**; **Schema v22 LOCKED -> v23 INTRODUCED by THIS dispatch** (exactly ONE new `0023_*.sql`; do NOT add a v24; do NOT touch the v22 temporal-log substrate); L2 LOCK preserved (source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

**Expected duration:** ~4-7 hours executing-plans implementation + 1 Codex chain. Plan §G enumerates 6 task slices T-3.1..T-3.6; **~18-26 commits + ~60-66 fast tests** projected (trust `pytest -m "not slow" -q` over the estimate per gotcha #1; **capture the exact baseline at branch creation** -- ~6660 expected after SB2). Operator-paced; SHIPS production code + tests + ONE new migration under `swing/` + `tests/`.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief.
- `copowers:executing-plans` wraps `superpowers:subagent-driven-development` with adversarial Codex review after all tasks complete.
- **Codex chain count: ONE chain** per the operator-LOCKed OQ-chain disposition (§1.3) + Sec 9.1 Q7 + the writing-plans precedent (single chain, converged R4). The v23 rename is a mechanical value-rename, NOT a permanent append-only substrate -> one chain (see §4).
- **Codex MCP transport (FB-N1):** the MCP times out at 1s on this host. **The operator is investigating that separately -- do NOT attempt to fix the MCP.** Use the `codex exec` CLI + `codex exec resume --last` thread-continuity backstop (paste artifacts INLINE; codex-cli `-s read-only` cannot spawn shells here -> on the `resume` subcommand use `-c sandbox_mode="read-only"`, NOT `-s`). Identical adversarial substance.
- Output: production code + tests + return report at `docs/phase14-sub-bundle-3-chart-surface-uniformity-executing-plans-return-report.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/plans/2026-05-30-phase14-sub-bundle-3-chart-surface-uniformity-plan.md`** -- the LOCKed plan (1311 lines; AUTHORITATIVE for implementation; Codex single chain CONVERGED R4). Especially:
   - §A Goals + non-goals (the 7-item L1 scope); §B File map (per-file diff projections); §C Surface-by-surface integration (the shared candlestick helper `_render_candles_fig` §C.1, the `_normalize_ohlc_for_mpf` barrier §C.1b, `_x_for_date` §C.1c, BULZ arithmetic §C.3a, weather `current_stage` §C.4a)
   - §D Out of scope; §E LOCK reverification (Sec 9.1 + L1-L7 + the §1.3 OQ dispositions)
   - §F Discipline + watch items (FB#1-FB#3 + matplotlib/session-anchor/#11/L2 globals)
   - **§G Per-task slicing (T-3.1..T-3.6; bite-sized step-checkbox TDD) + §G.0 commit cadence preface** (BINDING)
   - §H Test surface (per-task distribution; ~60-66 sum-check); **§I Per-renderer operator-witnessed visual-gate runbook (S1-S7)**
   - §J Codex SINGLE-chain placement; §K Schema impact (v23); §L Test fixture strategy; §M Forward-binding lessons (the 10 carried verbatim); §N Self-review checklist (pre-Codex)

3. **`docs/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans-return-report.md`** -- return report (15 items). Especially §4 (the 11 operator-LOCKed OQ dispositions honored), §5 (residual OQs locked: v23 filename, candle-helper API, MA palette hex, `current_stage` signature/asof, BULZ target field), §6 (20 Codex majors resolved -- the design rationale), §10 (the 10 forward-binding lessons for executing-plans), §11 (schema impact verdict).

4. **`docs/superpowers/specs/2026-05-29-phase14-sub-bundle-3-chart-surface-uniformity-design.md`** -- brainstorm spec (494 lines; reference for architectural rationale). Especially §2 (pre-locked decisions), §4 (candlesticks), §5 (v23 rename), §7 (BULZ -- NOTE the V1 simplification deviates from §7's avg-fill anchor, see §3 below), §8 (P14.N8 weather), §13 V1 simplifications.

5. **`docs/phase14-sub-bundle-3-chart-surface-uniformity-writing-plans-dispatch-brief.md`** §1 LOCKs (incl. §1.3 the 11 operator-LOCKed OQ dispositions) + §5 watch items -- carry forward.

6. **`CLAUDE.md`** -- the compressed gotchas. Most relevant: **matplotlib mathtext** (ASCII annotation text; `mpf.plot` title->suptitle; manual visual verification non-optional); **#11** (Schema-CHECK + constant + validator + `_row_to_*` mapper same task; STRICT backup-gate `pre_version == 22`); **#9** (executescript implicit COMMIT -> explicit BEGIN/COMMIT/ROLLBACK); **Weather lookup must NOT query by `action_session`** (P14.N8 `current_stage` asof); **byte-parity insufficiency** (the rendered chart is the binding gate; `mpf.plot` spy + non-literal sentinels); **Windows cp1252** (renderers return bytes; ASCII discipline). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **Expansion #10c** (renderer-kwargs uniformity + cache-collision tests), **#2** (signature verify), **#4** (SQL column verify), **#11** (taxonomy propagation for the rename), **#13** (cascade audit each task).

7. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_verify_regression_test_arithmetic` (compute both at-boundary + over-boundary for the BULZ zone-bounds + the off-range far-target + candle-vs-line tests)
   - `feedback_copowers_codex_mcp_windows_launcher` (FB-N1: MCP off-purview; `codex exec` CLI backstop; restart-required IF you attempt the MCP; codex-cli `-s read-only` can't spawn shells -> paste artifacts inline; `resume` uses `-c sandbox_mode="read-only"`)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]` before push)
   - `feedback_worktree_cli_invocation` (`python -m swing.cli`, NOT bare `swing`)

8. **Production code surfaces** cited in plan §B + §C. **RE-VERIFY at executing-plans start** to catch drift since the writing-plans merge (FB#1/#2; the plan re-grepped at `69efa80`, main is now `b7fd46b`). The orchestrator already re-verified these anchors at `b7fd46b` (see §3 "Verified anchors"); re-confirm per #2:
   - `swing/web/charts.py` -- the 5 renderers (`render_watchlist_thumbnail_svg:181`, `render_hyprec_detail_svg:227`, `render_position_detail_svg:285`, `render_market_weather_svg:334`, `render_theme2_annotated_svg:482`) + the `_annotate_*` family + shared helpers. **`swing/rendering/charts.py` does NOT exist** -- all rendering is in `swing/web/charts.py` (FB#1 RESOLVED).
   - `swing/web/chart_jit.py` (the JIT weather default `stage_2` hardcode ~`158`) + `swing/data/repos/chart_renders.py` (surface CHECK enum mirror + `refresh_chart_render` + `_row_to_*`)
   - `swing/data/migrations/0020_chart_renders.sql:179` (the `surface` CHECK enum -- `hyprec_detail`; the 3 partial unique indexes do NOT reference `hyprec_detail`) + `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION = 22`; `_phase14_backup_gate` template; `run_migrations`; `_apply_migration` FK-restore in `finally` on BOTH success + rollback)
   - `swing/pipeline/runner.py` (pipeline-time weather `trend_template_state="stage_2"` hardcode ~`2883`) + `swing/web/routes/dashboard.py` (refresh-handler ~`117`) + `swing/web/routes/patterns.py` + `swing/web/templates/_pattern_card.html.j2` + `swing/web/view_models/patterns/detail.py` (the 8 `hyprec_detail`-bearing tracked files -- the atomic-rename scope)
   - `current_stage` -- the orchestrator located it at `swing/patterns/foundation.py` (signature `current_stage(conn, ticker, asof_date: date)`; returns ONLY `"stage_2"`/`"undefined"` in V1; the spec's cited `review_form.py:454` caller does NOT exist; see §3 correction 1). **RE-GREP its exact path+line at STEP 0** (`git grep -n "def current_stage" -- swing/`).
   - `pyproject.toml` (`[web]` extra -- `mplfinance>=0.12`) + the `Trade` model (`entry_price`, `initial_stop`, `planned_target_R` for P14.N4 BULZ -- verify per #4)

---

## §1 LOCKs inherited (BINDING through executing-plans; DO NOT re-litigate)

All LOCKs preserved verbatim through 1 brainstorm + 1 writing-plans Codex chain per plan §E.

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = data-wiring (SHIPPED) -> temporal log V1+ (SHIPPED) -> **chart-surface uniformity (THIS)** -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q4** V2.G2 `hyprec_detail`->`ticker_detail` rename ships in THIS sub-bundle as a **v23 migration** (data-migration discipline)
- **Q5** matplotlib SVG only -- **mplfinance is matplotlib-based -> within the no-JS LOCK**
- **Q6** operator browser-witnessed verification at merge (the rendered chart is the BINDING visual gate)
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** (operator-LOCKed, §1.3)

### §1.2 Brainstorm spec §2 + L1-L7 LOCKs
- **L1** scope = V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6 cosmetic ONLY (the 7-item scope)
- **L2** v23 migration (gotcha #11 paired + gotcha #9 + backup-gate STRICT `pre_version == 22`; migrate CHECK enum + existing rows; the 3 partial indexes do NOT reference `hyprec_detail` -- recreate verbatim)
- **L3** renderer-kwargs uniformity LOCK (Expansion #10c); cache-collision discriminating tests at reused surfaces
- **L4** matplotlib visual-gate discipline (byte/string tests INSUFFICIENT; per-renderer operator-witnessed visual gate; ASCII annotation text)
- **L5** atomic rename (no orphaned `hyprec_detail` across schema + Python + renderer fn name + routes + templates + view-models + tests; two-tier zero-orphan grep widened to static assets + leaked prose `"hyp-rec detail"`)
- **L6** L2 LOCK preserved (ZERO new `schwabdev.Client.*` call sites; `current_stage` reads weather/candidate/eval rows only)
- **L7** P14.N8 fixes the render to show the REAL trend, not suppress it

### §1.3 The 11 operator-LOCKed OQ dispositions (BINDING; operator-paired triage 2026-05-29 #5)

| OQ | LOCKed disposition |
|---|---|
| **P14.N8 scope (OD-3)** | Real `current_stage` at the **2 LIVE weather sites** -- the pipeline-time render (`runner.py:~2883`) + the refresh handler (`dashboard.py:~117`) -- using the render-context asof (pipeline = `lease_data_asof`->`date.fromisoformat`; refresh = `last_completed_session(now)`; NOT `action_session`, per the weather-lookup gotcha). The **JIT default (`chart_jit.py:~158`) = honest `"undefined"`** (no live caller exists; correction 2 below). `current_stage` reads weather/candidate/eval rows only (no Schwab/yfinance; L6). |
| **Candlestick scope (OD-2)** | The **4 DETAIL surfaces get mplfinance candlesticks** (`ticker_detail` [renamed], `position_detail`, `market_weather`, `theme2_annotated`); the **watchlist thumbnail STAYS a line** (illegible at thumbnail size). |
| **Codex chain count (OQ-chain)** | **SINGLE chain** at executing-plans. |
| **OQ-4 (P14.N1)** | Ship the thumbnail RENDERER substrate ONLY; **defer consuming-surface wiring to Sub-bundle 4**. |
| **OQ-6 (market_weather MAs)** | **50/200 only** (10/20 too noisy at 400px). |
| **OQ-7 (v23 row rename)** | **In-migration row migration** (`INSERT...SELECT` with `CASE surface WHEN 'hyprec_detail' THEN 'ticker_detail' ELSE surface END`), atomic with the schema change (id-preserving). |
| **OQ-S6 (duration text)** | **Move the annotation text to upper-right** (matches slug placement; clears the legend). |
| **OQ-mav-color** | **Pinned colorblind-safe MA palette** = Okabe-Ito 5-hex `#0072B2 / #E69F00 / #009E73 / #CC79A7 / #D55E00` in the shared helper (`_MA_COLORS`); avoid the BULZ red/green fills; ASCII-safe. |
| **OQ-N4-target** | BULZ target from `planned_target_R` (`entry_price + planned_target_R*(entry_price - initial_stop)`); **draw the target zone ONLY if `planned_target_R` is present** (risk-zone-only fallback if absent). |
| **OQ-N4-color** | Zone semantics (entry/stop/target) are binding; **exact hues confirmed at the operator-witnessed gate** (cosmetic). |
| **Full rename** | Rename the renderer FUNCTION too: `render_hyprec_detail_svg` -> `render_ticker_detail_svg` (+ all callers). |

---

## §2 Scope inheritance from plan §G (BINDING substrate)

Plan §G is AUTHORITATIVE. Implement task-by-task in the locked order; **3-5 commits/task; SERIAL; cascade-audit (Expansion #13) after each task; verify `%(trailers)` is `[]` after each commit** (§G.0).

| Task | Scope | Tests |
|---|---|---|
| **T-3.1** v23 rename + atomic taxonomy propagation | `0023_phase14_sb3_chart_surface_rename.sql` (NEW; single-table rebuild CREATE-COPY(id-preserving `CASE` rename)-DROP-RENAME; 3 partial indexes + cross-column CHECK recreated verbatim; `INSERT...SELECT` row migration). `db.py` `EXPECTED_SCHEMA_VERSION` 22->23 + `_phase14_sb3_backup_gate` STRICT `pre_version == 22` (mirror `_phase13_sb6c_backup_gate`) + `PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES`. `chart_renders.py` CHECK-enum mirror + `_row_to_*` (gotcha #11 paired). Rename `render_hyprec_detail_svg`->`render_ticker_detail_svg` + ALL callers (routes/VMs/templates/tests). The neutral title lands HERE (R2-M2; no intermediate leaked-title state). Cascade audit: ZERO orphaned `hyprec_detail` / `render_hyprec_detail_svg` (allowlist frozen migrations 0020/0022). **STEP 0:** derive v23 DDL from a migrated-to-v22 fixture's live `sqlite_schema` (FB#2). | ~14 |
| **T-3.2** candle helper + ticker_detail + theme2 | `_normalize_ohlc_for_mpf` barrier (single-ticker MultiIndex flatten; RAISE on multi-ticker; DatetimeIndex; sort ascending) + `_render_candles_fig` (mplfinance `returnfig=True`; pinned `_MA_COLORS`; ASCII-safe) + `_x_for_date` (operates on the NORMALIZED `df`, R1-M5). Adopt on `render_ticker_detail_svg` (volume ON) + `render_theme2_annotated_svg` (volume OFF) + S6 duration text upper-right. **STEP 0 (T-3.2-step-0):** render the CURRENT `ticker_detail` SVG + diagnose how it embeds (viewBox/CSS) BEFORE the mpf swap (FB#3; a viewBox/CSS clipping bug would survive the swap). | ~22 |
| **T-3.3** position_detail + BULZ zones (P14.N4) | Adopt `_render_candles_fig` (volume ON) on `render_position_detail_svg`; BULZ target arithmetic (`entry_price + planned_target_R*(entry_price - initial_stop)`; target-only-if-present); `axhspan` risk/reward zones (gate-confirmed hues; ASCII labels); invalid trade-shape -> skip zone + WARN (#27, no silent skip). | ~12 |
| **T-3.4** market_weather + real current_stage (P14.N8) + 50/200 MAs (P14.N2) | Adopt `_render_candles_fig` (volume OFF; `ma_windows=(50,200)`). Real `current_stage` at the pipeline site (`runner.py:~2883`; asof = `lease_data_asof`) + the refresh site (`dashboard.py:~117`; asof = `last_completed_session(now)`). JIT default -> honest `"undefined"`. Expansion #10c renderer-kwargs uniformity test (pipeline vs refresh pass IDENTICAL kwargs); fail-soft to `"undefined"` (pipeline no-abort). | ~9 |
| **T-3.5** P14.N1 thumbnail substrate + S6 verification | Reusable thumbnail renderer entrypoint (substrate-only; NO consuming-surface wiring -- SB4); row-VM thumbnail binding (substrate-only); S6 final verification (duration text upper-right). | ~5 |
| **T-3.6** closer | `pyproject.toml` `[web]` declares mplfinance + metadata test + import smoke; L2 source-grep continued-pass; full suite + ruff; per-renderer visual-gate artifacts (render each surface to PNG/SVG + regen commands for the gate); return report. | ~3 |

**Total: ~60-66 fast tests** projected (trust pytest per gotcha #1; **0 slow tests** -- all charts render from fixture bars). **Do NOT widen task scope** beyond plan §G acceptance criteria + step-checkbox TDD.

---

## §3 Two production corrections + one confirm-item + watch items (BINDING)

### Two production corrections (carry into implementation)
1. **`current_stage` location + return shape.** The spec cited `review_form.py:454` as a `current_stage` caller -- **that caller does NOT exist.** `current_stage` lives at `swing/patterns/foundation.py` (signature `current_stage(conn, ticker, asof_date: date)`; returns ONLY `"stage_2"`/`"undefined"` in V1 -- a limited V1 detector, NOT a full 1-4 trend-template stage machine). Use the detector pattern (the plan's FB#8 references `vcp.py:500`). **RE-GREP the exact path+line at STEP 0.** Plan §C.4a / return report §10 lesson 8.
2. **No live `market_weather` JIT caller exists.** The dashboard reads `market_weather` from cache only (no live JIT derivation path). So the `chart_jit.py:~158` `stage_2` default is dead/defensive -> set it to honest `"undefined"`, NOT a live derivation. **P14.N8 = 2 LIVE sites (`runner.py` pipeline + `dashboard.py` refresh) + 1 DEFENSIVE default (`chart_jit.py`).** Plan §C.4a / return report §10 lesson 7.

### One confirm-item (surface at the operator-witnessed gate)
3. **BULZ entry-anchor V1 simplification (OPERATOR-CONFIRM at the gate).** The plan anchors the BULZ zones on the LOCKED `trade.entry_price` (deriving the target from `planned_target_R`), **deviating from spec §7's avg-fill anchor.** This is an explicit operator-surfaced V1 simplification (banked to V2; plan §D.2 + return report §7/§10 lesson 10). The implementer ships it as planned; **the orchestrator surfaces it for operator confirmation at the executing-plans operator-witnessed visual gate.** Re-adding avg-fill (V2) needs BOTH the entry swap AND a target re-derivation.

### Verified anchors (orchestrator re-grep at `b7fd46b`, dispatch HEAD)
- `swing/rendering/charts.py` does NOT exist -> all rendering in `swing/web/charts.py` (FB#1 RESOLVED).
- 5 renderers at `swing/web/charts.py:181/227/285/334/482` (1-line drift from the plan's `180/226/284/334/481`; re-grep per #2).
- `hyprec_detail` present in 8 tracked files: `0020_chart_renders.sql`, `chart_renders.py`, `chart_jit.py`, `charts.py`, `routes/dashboard.py`, `routes/patterns.py`, `templates/_pattern_card.html.j2`, `view_models/patterns/detail.py` -- the atomic-rename scope (L5).
- `EXPECTED_SCHEMA_VERSION = 22` (v22 LIVE since SB2 `27f8007`).

### Forward-binding lessons (plan §M + return report §10; LOAD-BEARING per task)
1. **Re-grep all signatures at executing time (#2):** post-T-3.1 names are `render_ticker_detail_svg` + `_TICKER_DETAIL_SIZE_PX`; `current_stage(conn, ticker, asof_date: date)`; the `_step_charts` asof var (`lease_data_asof`); `Trade.planned_target_R/entry_price/initial_stop`; `Fill.action/price/quantity`; **confirm `last_completed_session` return type BEFORE any `.date()` suffix.**
2. Derive the v23 DDL from a migrated-to-v22 fixture's `sqlite_schema` (T-3.1 Step 1).
3. **T-3.2-step-0 (browser-embedding diagnosis) runs BEFORE the candlestick conversion** -- a viewBox/CSS clipping bug would survive the mpf swap; mpf + `bbox_inches="tight"` changes the SVG `width`/`height`/`viewBox`.
4. The **MA palette + S6 reserved-region map are PINNED** in the plan -- visual-gate-critical (do NOT improvise).
5. The visual gate is BINDING -- **enumerate per-surface SVG/PNG artifacts + regen commands in the return report**; the operator is the named gate owner.
6. mplfinance must be in EVERY `swing web` profile + the import smoke + the `pyproject.toml` metadata test.
7. No live `market_weather` JIT caller exists today -- the JIT default is honest `"undefined"` (correction 2).
8. The spec's cited `current_stage` caller (`review_form.py:454`) does not exist -- use the detector pattern; `current_stage` returns ONLY `"stage_2"`/`"undefined"` in V1 (correction 1).
9. **Confirm SVG keeps text-as-text (`svg.fonttype`)** for the byte text assertions, OR assert on text artists pre-serialization.
10. The avg-fill->locked-entry BULZ basis is an operator-surfaced V1 simplification -- confirm at the visual gate (confirm-item 3).

### Cumulative gotchas (plan §F)
matplotlib mathtext (ASCII annotation; `mpf.plot` title->suptitle; manual visual verification non-optional) / **#11** (CHECK+constant+validator+`_row_to_*`+renderer+routes+VMs+templates+tests one task; STRICT backup-gate `pre_version == 22`; run-migrate-twice no-op) / **#9** (BEGIN/COMMIT/ROLLBACK + rollback-through-runner via mid-script-failure injection `_patch_0023_sql` -- the wrapper must raise MID-script, not post-commit, or it won't prove rollback) / **Expansion #10c** (renderer-kwargs uniformity; cache-collision tests) / **#11 taxonomy propagation** (two-tier zero-orphan grep, widened to static assets + prose) / **byte-parity insufficiency** (non-literal sentinel + `mpf.plot(type="candle")` spy per converted surface + behavioral chart_jit default test) / **session-anchor read/write** (weather `last_completed_session`/`lease_data_asof`, NOT `action_session`) / **#4** (BULZ `planned_target_R`/`entry_price`/`initial_stop`; partial-index correction) / **#27** (fail-soft WARN, no silent skip) / L2 source-grep / **#16/#32** (ASCII discipline; renderers return bytes -> Windows cp1252).

**Streaks to preserve:** ~624+ ZERO `Co-Authored-By` (verify `%(trailers)` per commit; keep final `-m` paragraph plain prose per `feedback_commit_message_trailer_parse_hazard`); **Schema v23 INTRODUCED -- exactly ONE `0023_*.sql`; do NOT exceed v23 (no v24); do NOT touch the v22 temporal-log substrate**; L2 LOCK (source-grep continues passing); ASCII discipline; gotcha #33 banned-terms across narrative.

---

## §4 Codex SINGLE-chain placement (OQ-chain LOCK; plan §J)

Run ONE chain at the end of executing-plans, after ALL code + tests land + green, BEFORE the operator-witnessed gate. 2-4 round target; converges to `NO_NEW_CRITICAL_MAJOR`.

**Lens:** production-signature correctness; v23 migration parity + FK-survival (`pattern_detection_events.chart_render_id` `ON DELETE SET NULL` preserved via id-preserving copy + FK-off-during-rebuild + `_apply_migration` FK-restore in `finally`) + rollback (mid-script-failure injection); mplfinance determinism + ASCII; BULZ arithmetic + target-only-if-present + off-range-drawn; weather real-state + Expansion #10c kwargs uniformity; atomic-rename no-orphan (two-tier grep); L2 source-grep continues passing; visual-gate declared binding; no placeholders; cascade-regression audit.

**FB-N1:** MCP off-purview (operator investigating); use `codex exec` CLI with INLINE artifacts (read-only sandbox can't read files -> paste the GIT DIFF + spec + plan + a re-grepped production-signature DIGEST inline; `resume --last -c sandbox_mode="read-only"` preserves thread continuity). Re-build the verified-signature digest at executing-plans HEAD (drift since `69efa80`). Aim for ZERO Major accepted-as-rationale (brainstorm + writing-plans both resolved all in-place).

**If Codex finds a defect requiring a schema change beyond v23:** STOP + escalate (do NOT add a v24; do NOT touch the v22 substrate).

---

## §5 Operator-witnessed gate (plan §I; S1-S7; per-renderer visual)

After the chain converges + return report drafted, the orchestrator returns to the operator. **The BINDING gate is the RENDERED chart** (matplotlib; byte/string tests insufficient -- L4). Browser MCP may be unavailable -- **proven fallback (SB2 S6):** the orchestrator renders each surface to PNG via the branch code + Reads the PNG visually (the Read tool views PNGs); OR operator-driven browser + orchestrator DB-side probes. **The operator directed the orchestrator to RUN the gates at SB2** -- the orchestrator will confirm their preference for SB3.

| Step | Surface | What to verify |
|---|---|---|
| **S1** | pytest + ruff | full fast suite green (~6660 baseline + ~60-66 NEW) + `ruff check swing/` clean (0 E501 preserved) |
| **S2** | v23 schema | `schema_version = 23`; `chart_renders` rows migrated `hyprec_detail`->`ticker_detail` (same id); pre-migration backup emitted at the `pre_version == 22` boundary |
| **S3** | `ticker_detail` | candlestick render (volume pane); MAs distinct (Okabe-Ito palette); annotations legible (ASCII) |
| **S4** | `position_detail` | candlesticks + BULZ entry/stop/target zones; **target zone only if `planned_target_R` present** (confirm-item 3: entry anchored on locked `entry_price`) |
| **S5** | `market_weather` | candlesticks + 50/200 MAs; **real trend-state (not `stage_2` hardcode)** |
| **S6** | `theme2_annotated` | duration text upper-right (no legend overlap) |
| **S7** | refresh vs pipeline | weather refresh-handler render MATCHES the pipeline-time render (Expansion #10c kwargs uniformity) |

**Gate-pass triggers** ("all surfaces pass" / "gate passed" / equivalent) -> orchestrator merges per `feedback_orchestrator_performs_merge` BINDING.

---

## §6 Done criteria

1. All 6 tasks shipped (T-3.1..T-3.6)
2. Codex SINGLE chain CONVERGED at NO_NEW_CRITICAL_MAJOR
3. ~6660+ fast tests green on branch (baseline + ~60-66 NEW); `python -m pytest -m "not slow" -q`
4. `ruff check swing/` clean (preserve 0 E501 baseline)
5. ZERO Co-Authored-By trailer drift (verify `%(trailers)`); final `-m` paragraphs plain prose
6. **Schema v23 applied; exactly ONE new migration `0023_*.sql`; no v24; v22 temporal-log substrate UNTOUCHED** (escalate if a v24 seems needed)
7. L2 LOCK preserved (source-grep test PASSES against `bf7e071` baseline)
8. Atomic rename complete: ZERO orphaned `hyprec_detail` / `render_hyprec_detail_svg` across runtime paths (allowlist frozen migrations 0020/0022); two-tier grep test green
9. Return report at `docs/phase14-sub-bundle-3-chart-surface-uniformity-executing-plans-return-report.md` complete per §7 (incl. per-renderer visual-gate artifacts + regen commands)
10. Branch pushed to origin; ready for orchestrator QA + operator-witnessed gate

---

## §7 Return report shape

1. Final HEAD + commit count breakdown (per-commit Codex round attribution)
2. Codex round chain (single chain; summary table + convergent shape)
3. Per-task completion summary (T-3.1..T-3.6)
4. Test surface verification (~60-66 fast projected; per-task actual distribution; total before + after)
5. Pre-locked decisions verbatim verification (Sec 9.1 + L1-L7 + the 11 OQ dispositions)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO preferred)
7. Production-code citations verified at task completion (FB#1/#2 re-grep; per-task signature re-verification; the `current_stage` exact path + the `last_completed_session` return type)
8. Schema impact verdict (v23 applied; exactly one `0023_*.sql`; backup-gate STRICT `== 22`; runner discipline; parity + FK-survival + rollback test coverage)
9. Atomic-rename verification (two-tier zero-orphan grep; allowlist; the neutral-title regression)
10. L2 LOCK verification (source-grep PASSES against `bf7e071`; cite test name + result)
11. **Operator-witnessed gate readiness (S1-S7 runbook; per-surface SVG/PNG artifacts + regen commands; the BULZ entry-anchor confirm-item flagged for the operator)**
12. NEW forward-binding lessons banked (for SB4 + CLAUDE.md gotcha consideration)
13. ASCII discipline scope (gotcha #32; enumerate NEW + MODIFIED files)
14. Cumulative gotcha set application summary (per task)
15. Worktree teardown status
16. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits) + `%(trailers)` empty on merge-candidate
17. CLAUDE.md status-line refresh draft text
18. Operator-witnessed gate handback summary

---

## §8 OUT OF SCOPE (do not implement)

- P14.N1 consuming-surface wiring (SB4; OQ-4 LOCK -- substrate-only here)
- Avg-fill-anchored BULZ zones (V2; V1 uses locked `entry_price` -- confirm-item 3)
- Candlestick thumbnails (V2; the watchlist thumbnail STAYS a line)
- Per-surface configurable MA windows/styles (V2; V1 pins 50/200 on weather)
- `chart_renders` retention/eviction policy change
- theme2_annotated coexisting-writer reconciliation (last-writer-wins stays; FB-N3 from SB2)
- Schema beyond v23 (no v24; the v22 temporal-log substrate is UNTOUCHED; escalation rule)
- Historical chart re-render/backfill (no regeneration of existing `chart_renders` bytes)
- JS charting (matplotlib/mplfinance SVG only; Q5)
- Schwab API changes (L2 LOCK; ZERO new `schwabdev.Client.*` call sites)
- SB4/SB5 scope (Sec 9.1 Q1 serial LOCK); Phase 15+
- Production code modifications NOT in plan §B file map
- CLAUDE.md / orchestrator-context archive-splits

---

## §9 If you get stuck

- If production drifted since the writing-plans merge (`4fa20dd`) and a plan-cited file:line no longer matches, ESCALATE (do NOT silently patch). Plan was verified at `69efa80`; orchestrator re-verified core anchors at `b7fd46b` (§3).
- If `current_stage` is NOT at `swing/patterns/foundation.py` or its signature differs, ESCALATE (do NOT guess the asof param). RE-GREP at STEP 0.
- If a renderer's candlestick adoption forces an OHLCV-bar-shape change NOT anticipated, ESCALATE (the brainstorm confirmed bars already carry OHLC -- the escalation trigger did NOT fire at writing-plans).
- If the T-3.2-step-0 embedding diagnosis surfaces a pre-existing viewBox/CSS clipping bug, document it + ESCALATE the scope question (do NOT silently expand scope to a CSS fix).
- HOLD THE LINE if Codex pushes back on: v23 rename in THIS sub-bundle (Q4); matplotlib/mplfinance no-JS (Q5); SINGLE chain (OQ-chain LOCK); real `current_stage` at the 2 live weather sites + honest-undefined JIT default (operator LOCK + correction 2); 4-detail-surfaces candlesticks / thumbnail-line (operator LOCK); BULZ locked-entry basis (operator-surfaced V1 simplification); 50/200 weather MAs; Okabe-Ito MA palette; target-only-if-present.
- If a Codex finding needs a schema change beyond v23, STOP + escalate (no v24; do NOT touch v22).
- If the Codex MCP times out, do NOT attempt to fix it (operator investigating separately); use the `codex exec` CLI with INLINE artifacts.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT widen scope to SB4/SB5 or Phase 15+; DO NOT touch the v22 temporal-log substrate.

---

## §10 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface for production code + tests + migration).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-3-chart-surface-uniformity-executing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-3-chart-surface-uniformity-executing-plans/`.
- **Model:** defer to harness default.
- **CLI invocation in the worktree:** `python -m swing.cli` (NOT bare `swing` -- the editable install points at main, not the worktree).
- **Expected duration:** ~4-7 hours implementation + ~30-90 min for the single Codex chain. Operator-paced.
- **Codex MCP chain count:** ONE chain (OQ-chain LOCK + plan §J). FB-N1: MCP off-purview; `codex exec` CLI + inline artifacts is the backstop.
- **Production surface:** `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` (NEW) + `swing/data/db.py` + `swing/data/repos/chart_renders.py` + `swing/web/charts.py` + `swing/web/chart_jit.py` + `swing/pipeline/runner.py` + `swing/web/routes/dashboard.py` + `swing/web/routes/patterns.py` + `swing/web/view_models/patterns/detail.py` + `swing/web/templates/_pattern_card.html.j2` + `pyproject.toml` ([web] mplfinance). **Test surface:** `tests/data/` + `tests/data/repos/` + `tests/web/` + `tests/pipeline/` + `tests/integration/`.

---

*End of brief. Phase 14 Sub-bundle 3 executing-plans dispatch -- execute the LOCKed 1311-line plan (v23 atomic `hyprec_detail`->`ticker_detail` table-rebuild + shared mplfinance `_render_candles_fig` across 4 detail renderers + BULZ risk/reward zones + real `current_stage` at 2 live weather sites + honest-undefined JIT default + 50/200 weather MAs + S6 reposition + P14.N1 thumbnail substrate; 6 tasks T-3.1..T-3.6; ~18-26 commits + ~60-66 fast tests); ONE Codex chain; per-renderer operator-witnessed visual gate S1-S7 per plan §I. The rendered chart is the BINDING visual gate (matplotlib). OUTPUT: production code + tests + the v23 migration + return report; ready for orchestrator merge + operator-witnessed gate + post-merge housekeeping.*
