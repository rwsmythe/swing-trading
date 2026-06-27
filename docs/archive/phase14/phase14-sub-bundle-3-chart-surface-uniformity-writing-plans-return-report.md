# Phase 14 Sub-bundle 3 — Chart-Surface Uniformity — Writing-Plans Return Report

**Phase:** 14 Sub-bundle 3 (chart-surface uniformity) — WRITING-PLANS.
**Branch:** `phase14-sub-bundle-3-chart-surface-uniformity-writing-plans` (cut from main HEAD `69efa80`).
**Date:** 2026-05-29.
**Deliverable:** implementation plan at `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-3-chart-surface-uniformity-plan.md` + this report.

---

## 1. Final HEAD + commit breakdown

**Branch HEAD: `c3207b4`** (2 commits, both docs-only):

| Commit | Content |
|---|---|
| `65b6423` | `docs(phase14-sub-bundle-3-plan): writing-plans pre-Codex draft -- chart-surface uniformity` — the initial 987-line plan (§A-§N; T-3.1..T-3.6), authored after re-grepping production at `69efa80`. |
| `c3207b4` | `docs(phase14-sub-bundle-3-plan): writing-plans Codex single-chain R1-R4 -- converged at R4` — all 20 major + 6 minor Codex findings resolved in-place. Final 1311 lines. |

No `swing/` writes. **Schema v22 stays LOCKED** at writing-plans (v23 DESIGNED in the plan, applied at executing-plans). L2 LOCK preserved (zero new Schwab call sites — docs-only).

## 2. Codex chain + convergent shape

**SINGLE chain** (OQ-chain operator LOCK + Sec 9.1 Q7). **Converged at Round 4** (within the 2-4 target).

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 12 | 3 | ISSUES_FOUND |
| R2 | 0 | 6 (NEW) | 2 (NEW) | ISSUES_FOUND |
| R3 | 0 | 2 (NEW) | 1 (NEW) | ISSUES_FOUND |
| R4 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**Cumulative: 0 CRITICAL + 20 MAJOR + 6 MINOR. ALL resolved in-place; ZERO accepted-without-fix** (R3-M1, the avg-fill scope question, was resolved by recording an EXPLICIT operator-surfaced V1 simplification + a §D out-of-scope entry, not a silent accept).

**Transport note (FB-N1):** the Codex MCP times out at 1s on this host (operator investigating separately — NOT touched). Backstop = `codex exec` CLI. R1 via stdin with spec+plan inlined (1713-line prompt); the read-only sandbox's "spawn setup refresh" error did NOT stop Codex reasoning from the inline artifacts (it produced 12 substantive codebase-aware majors). R2-R4 via `codex exec resume --last -c sandbox_mode="read-only"` (thread continuity PRESERVED — Codex remembered prior rounds; delta-only prompts). `-s` flag is rejected by the `resume` subcommand on this CLI version — use `-c sandbox_mode="read-only"` instead (recorded for the next implementer).

## 3. Plan line count + per-section

**1311 lines.** All §A-§N present (brief §6):

| § | Section | Start line |
|---|---|---|
| A | Goals / non-goals | 13 |
| B | File map | 49 |
| C | Surface-by-surface integration | 87 |
| D | Out of scope | 336 |
| E | LOCK reverification | 352 |
| F | Discipline + watch items | 393 |
| G | Per-task slicing (T-3.1..T-3.6) + §G.0 | 409 |
| H | Test surface (sum-check) | 1132 |
| I | Per-renderer operator-witnessed visual-gate runbook | 1155 |
| J | Codex single-chain placement | 1177 |
| K | Schema impact (v23) | 1185 |
| L | Test fixture strategy (+ fixtures) | 1199 |
| M | Forward-binding lessons | 1286 |
| N | Self-review checklist | 1299 |

> Note: 1311 lines is below the ~1500-2800 brief guide, but dense + non-redundant — the bulk is concrete TDD test code (Codex pushed for fleshing the discriminating tests, which the plan now carries in full). Mirrors the brainstorm spec's accepted "below-guide but dense" verdict.

## 4. Pre-locked decisions — verbatim verification

**Sec 9.1 commissioning LOCKs (all honored, §E.1):** Q1 (charts after temporal log = this SB), Q2 (serial), Q4 (v23 rename THIS SB), Q5 (matplotlib/mplfinance no-JS), Q6 (operator browser-witnessed gate = §I), Q7 (single chain = §J). OK.

**Brainstorm L1-L7 (all honored, §E.2):** L1 (7-item scope only), L2 (v23 #11 paired + #9 BEGIN/COMMIT + STRICT `pre_version==22`), L3 (renderer-kwargs uniformity + cache-collision tests), L4 (visual-gate binding; byte/string insufficient), L5 (two-tier zero-orphan grep — widened R2 to static assets + the leaked prose), L6 (L2 preserved; `current_stage` reads candidate/eval rows only), L7 (P14.N8 computes real state, not suppress). OK.

**§1.3 operator-LOCKed OQ dispositions (all 11 honored, §E.3 table):** real `current_stage` at the LIVE sites + honest-undefined defensive default; 4 detail surfaces candlesticks / thumbnail-line; SINGLE chain; P14.N1 substrate-only; weather 50/200 MAs; v23 in-migration `UPDATE`; S6 text upper-right; pinned Okabe-Ito MA palette; BULZ `planned_target_R` derived + target-only-if-present; zone semantics binding / hues at gate; full renderer-fn rename. OK.

## 5. Residual OQs locked in the plan (§3 of the brief)

1. **v23 migration filename** = `0023_phase14_sb3_chart_surface_rename.sql`; CHECK-enum rewrite shape pinned (§K, T-3.1) — DDL derived from a migrated-to-v22 fixture's live `sqlite_schema` (authoring-time, static file).
2. **Candlestick shared-helper API** = `_render_candles_fig(df, *, ma_windows, figsize, volume, style) -> (fig, price_ax, vol_ax)` + `_normalize_ohlc_for_mpf` barrier + `_x_for_date(price_ax, df, target_date)` (§C.1/C.1b/C.1c).
3. **MA palette** PINNED = Okabe-Ito 5-hex (`#0072B2/#E69F00/#009E73/#CC79A7/#D55E00`), avoiding the BULZ red/green fills (§C.1 `_MA_COLORS`).
4. **`current_stage` callsite signature + asof** = `current_stage(conn, ticker, asof_date: date)`; pipeline asof = `lease_data_asof(cfg, lease)`→`date.fromisoformat`; refresh = `last_completed_session(now)`; JIT default = honest `"undefined"` (§C.4a).
5. **BULZ target field** = `planned_target_R` (R-multiple); absolute target = `entry_price + planned_target_R*(entry_price - initial_stop)` (§C.3a).
6. **Commit cadence preface** = §G.0 (3-5 commits/task, cascade audit each task, SERIAL).

## 6. Codex Major findings accepted (ZERO preferred; resolved-in-place dominates)

20 majors total; **20 RESOLVED in-place; 0 pure-accept.** Highlights:
- **R1-M5 (overlay coordinate correctness):** `_x_for_date` re-specified to operate on the NORMALIZED `df` (not raw `bars`) — renderers normalize once and pass the same `df` to both the candle helper and every coordinate lookup; added an unsorted-input regression test.
- **R1-M2/M6/M10 (test rigor):** non-literal trend sentinel; `mpf.plot(type="candle")` spy per converted surface; behavioral (not source-string) chart_jit default test.
- **R1-M3/M4 → (corrected design):** rollback + FK-restore tests inject a mid-script SQL failure (`_patch_0023_sql`) so the runner's except/rollback path actually fires — the original wrapper raised post-commit (would not prove rollback).
- **R1-M11 (yfinance footgun):** `_normalize_ohlc_for_mpf` flattens ONLY a single-ticker MultiIndex; RAISES on multiple tickers.
- **R1-M12 → R2-M1 (BULZ basis):** single entry basis on the LOCKED `trade.entry_price` (target = 120 in the example), matching the canonical R formula; avg-fill helper dropped.
- **R2-M2 (atomic-rename completeness):** neutral title moved into T-3.1 (no intermediate leaked-title state).
- **R2-M3/M4 (L5 gate completeness):** grep widened to static assets (`.css`/`.js`) + the leaked prose `"hyp-rec detail"`; glob allowlist for frozen migrations.
- **R2-M6 (packaging guarantee):** a `pyproject.toml` metadata test asserting the `[web]` extra declares mplfinance (the import-smoke alone passes in a dev env).
- **R3-M1 (scope honesty):** the avg-fill→locked-entry change recorded as an EXPLICIT operator-surfaced V1 simplification (deviation from spec §7, banked to V2).
- **R3-M2 (off-range zone):** discriminating far-target test (`planned_target_R=20`→target 300) asserting the valid band is drawn, not hidden.

## 7. V1 simplifications + V2 candidates

**V1 simplifications (banked):** thumbnails stay line; P14.N1 reuses `watchlist_row` surface (no new enums); market_weather MA = 50/200; BULZ target drawn only if `planned_target_R` present; **BULZ zone geometry uses locked `trade.entry_price`, NOT avg-fill (NEW V1 simplification, operator-surfaced, deviation from spec §7)**; P14.N1 consuming-surface wiring deferred to SB4; no chart_renders retention/eviction.

**V2 candidates:** avg-fill-anchored BULZ zones (+ re-derived target); candlestick thumbnails; per-surface configurable MA windows/style; mpf style theming; distinct thumbnail surfaces (SB4 + a v24 rename).

## 8. Per-task acceptance summary

- **T-3.1** (v23 + rename + backup gate + L5): v23 applies on a real v22 DB (rows renamed same-id, backup written, `foreign_key_check` clean, FK resolves, FK enforcement restored on success+rollback); validator rejects `'hyprec_detail'`; neutral title lands here; L5 grep zero in runtime-forbidden paths. ~14 tests.
- **T-3.2** (candle helper + ticker_detail/theme2): vol-axis-by-role; normalization barrier (incl. MultiIndex + collision); `_x_for_date` normalized-order pin; candle-not-line spy; neutral-title regression; single-cached-row (L3). ~22 tests.
- **T-3.3** (position_detail + BULZ): target arithmetic (verify-distinguish); risk/reward zone bounds; risk-only-when-no-target; invalid-shape skip+log; off-range drawn; ASCII legend. ~12 tests.
- **T-3.4** (market_weather + 2-live-site state): candles; 50/200 MAs; grid; real-state derivation (non-literal sentinel) at pipeline + refresh; fail-soft to `"undefined"` (incl. pipeline-no-abort); JIT default `"undefined"` (behavioral). ~9 tests.
- **T-3.5** (thumbnail substrate + S6): annotation stack upper-right; non-watchlist thumbnail via JIT; row-VM thumbnail binding (substrate-only). ~5 tests.
- **T-3.6** (closer): pyproject `[web]` mplfinance + metadata test + import smoke; L2 grep verified; full suite + ruff; visual-gate artifacts. ~3 tests.

## 9. Test surface (sum-check)

~60-66 new/updated tests across T-3.1..T-3.6 (§H table), within the spec §10 indicative envelope (~40-80). **0 slow tests** (all render from fixture bars). Mandatory discriminating tests enumerated in §H: renderer-kwargs uniformity / cache-collision (Expansion #10c); atomic-rename no-orphan grep (L5); `mpf.plot(type="candle")` spy per surface (R1-M6); BULZ target-only-if-present + zone-bounds-distinguish (verify-arithmetic) + off-range (R3-M2); schema-parity normalized-SQL + FK-restore success+rollback (R1-M2/M3/M4, R2-M1). Concrete fixture builders in §L.2.

## 10. Forward-binding lessons for executing-plans (§M of the plan)

1. Re-grep all signatures at executing time (#2) — post-T-3.1 names are `render_ticker_detail_svg` + `_TICKER_DETAIL_SIZE_PX`; `current_stage(conn, ticker, asof_date: date)`; the `_step_charts` asof (`lease_data_asof`); `Trade.planned_target_R/entry_price/initial_stop`; `Fill.action/price/quantity`; confirm `last_completed_session` return type before the `.date()` suffix.
2. Derive v23 DDL from a migrated-to-v22 fixture's `sqlite_schema` (T-3.1 Step 1).
3. T-3.2-step-0 (browser-embedding diagnosis) runs BEFORE the candlestick conversion (a viewBox/CSS clipping bug would survive the mpf swap; mpf + `bbox_inches="tight"` changes the SVG `width`/`height`/`viewBox`).
4. The MA palette + S6 reserved-region map are PINNED in the plan — visual-gate-critical.
5. The visual gate is BINDING — enumerate per-surface SVG/PNG artifacts + regen commands in the executing-plans return report; operator is the named gate owner.
6. mplfinance must be in EVERY `swing web` profile + the import smoke + the metadata test.
7. No live `market_weather` JIT caller exists today — the JIT default is honest `"undefined"`, not a live derivation.
8. The spec's cited `current_stage` caller (`review_form.py:454`) does not exist — use the detector pattern (`vcp.py:500`); `current_stage` returns ONLY `"stage_2"`/`"undefined"` in V1.
9. Confirm SVG keeps text-as-text (`svg.fonttype`) for the byte text assertions, or assert on text artists pre-serialization.
10. The avg-fill→locked-entry BULZ basis is an operator-surfaced V1 simplification — confirm at the visual gate; re-adding avg-fill needs BOTH the entry swap AND a target re-derivation.

## 11. Schema impact verdict (v23 DESIGNED, not applied)

Single-table rebuild of `chart_renders` (`0023_*.sql`): CHECK enum `hyprec_detail`→`ticker_detail` via CREATE-COPY(id-preserving `CASE` rename)-DROP-RENAME; 3 partial indexes + cross-column CHECK recreated verbatim (no value change — verified the indexes do NOT reference `hyprec_detail`); `INSERT…SELECT` row migration (OQ-7); `EXPECTED_SCHEMA_VERSION=23`; `_phase14_sb3_backup_gate` STRICT `==22`. FK from `pattern_detection_events.chart_render_id` (`ON DELETE SET NULL`) preserved via id-preserving copy + FK-off-during-rebuild (`_apply_migration` restores `foreign_keys` in `finally` on BOTH success + rollback — verified `db.py:183-226`). No new columns/tables; no enum widening. v22 temporal-log substrate UNTOUCHED. **Verdict: a clean, low-risk single-table rename migration with strong parity + FK-survival + rollback test coverage. v22 stays LOCKED at writing-plans.**

## 12. Cumulative gotcha application

Matplotlib mathtext (two-gate title/body distinction; `mpf.plot` title→suptitle); #11 paired (CHECK+constant+validator+`_row_to_*`+renderer+routes+VMs+templates+tests in T-3.1); #9 BEGIN/COMMIT/ROLLBACK + rollback-through-runner (mid-script-failure injection); #11 STRICT backup gate `==22` + run-migrate-twice; Expansion #10c kwargs uniformity (shared helper + cache-collision tests); #11 taxonomy propagation (two-tier zero-orphan grep, widened to static + prose); byte-parity insufficiency (non-literal sentinel + `mpf.plot` spy + binding visual gate); session-anchor read/write (weather `last_completed_session`/`lease_data_asof`); #4 SQL/field verification (BULZ `planned_target_R`; partial-index correction; review_form.py-absent correction); #27 silent-skip audit (fail-soft WARN, no silent skip); L2/ASCII (#16/#32); Windows cp1252 (renderers return bytes); ZERO Co-Authored-By + trailer-parse hazard (final `-m` paragraphs plain prose, `%(trailers)` `[]`).

## 13. Worktree teardown status

**Worktree RETAINED + CLEAN** for orchestrator merge. `git status --porcelain` empty (after deleting the `/tmp/codex_r*` prompt artifacts). Branch `phase14-sub-bundle-3-chart-surface-uniformity-writing-plans` at `c3207b4`, 2 commits ahead of `main` (`69efa80`).

## 14. ZERO Co-Authored-By confirmation

Both commits: `git log -1 --format='%(trailers)'` returns EMPTY for `c3207b4`; verified `[]` for `65b6423` at commit time. No `Co-Authored-By`, no `noreply@anthropic.com`. Final `-m` paragraphs are plain prose (no `Word:`-leading trailer-parse hazard). Streak preserved (~622+).

## 15. CLAUDE.md status-line refresh draft (for orchestrator at merge)

> **Sub-bundle 3 (chart-surface uniformity; V2.G1 + V2.G2 v23 rename + P14.N1/N2/N4 + P14.N8 + S6) WRITING-PLANS SHIPPED at `<merge-sha>`** — plan at `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-3-chart-surface-uniformity-plan.md` (1311 lines; Codex single chain converged R4, 0C+20M+6m all resolved). 6 tasks (T-3.1..T-3.6): v23 atomic `hyprec_detail`→`ticker_detail` table-rebuild (id-preserving, STRICT `pre_version==22`); shared mplfinance `_render_candles_fig` across 4 detail renderers; BULZ risk/reward zones (target from `planned_target_R`); real `current_stage` at 2 live weather sites + honest-undefined JIT default; S6 reposition; P14.N1 thumbnail substrate. v23 DESIGNED not applied (v22 still LOCKED). **Executing-plans NEXT (SINGLE chain; per-renderer operator-witnessed visual gate is binding).**

### Executing-plans dispatch-readiness summary

**READY.** The plan is dispatchable: real signatures re-verified at `69efa80` (2 spec corrections recorded — `review_form.py` absent; no live `market_weather` JIT caller); v23 migration + backup-gate + parity/FK/rollback tests fully specified; mplfinance integration anchored on `swing/rendering/charts.py:render_chart`; BULZ/weather/S6/P14.N1 designed with explicit data-source + fail-soft + single-basis decisions; MA palette + S6 region map PINNED; T-3.2-step-0 embedding diagnosis sequenced first; per-renderer visual-gate runbook (§I) with artifacts/commands/ownership ready. Executing-plans should: (a) re-grep signatures (#2); (b) derive v23 DDL from a v22 fixture; (c) run the embedding diagnosis before mpf conversion; (d) confirm `last_completed_session` return type + the `_step_charts` asof var; (e) operate the binding visual gate with the operator as gate owner. SINGLE Codex chain at executing-plans (OQ-chain LOCK). No blockers; no escalations (the OHLC-bar-shape escalation trigger did NOT fire — bars already carry OHLC).

---

*End of return report. Phase 14 Sub-bundle 3 writing-plans COMPLETE: plan written + committed + Codex single chain converged at R4 (0C/20M/6m all resolved in-place); worktree clean + retained for orchestrator merge.*
