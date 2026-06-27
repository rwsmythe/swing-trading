# Phase 14 Sub-bundle 3 — Chart-Surface Uniformity — Executing-Plans Return Report

**Phase:** 14 Sub-bundle 3 (chart-surface uniformity) — EXECUTING-PLANS.
**Branch:** `phase14-sub-bundle-3-chart-surface-uniformity-executing-plans` (cut from main HEAD `0bb376a`, the executing-plans dispatch-brief commit).
**Date:** 2026-05-30.
**Deliverable:** production code + tests + the v23 migration on the branch + this report; ready for orchestrator QA + the operator-witnessed visual gate (S1–S7) + merge.

---

## 1. Final HEAD + commit-count breakdown

**Branch HEAD: `f59bdff`. 21 commits ahead of `0bb376a`** (19 task commits + 2 Codex-chain fix commits). All trailers empty (zero `Co-Authored-By`); all subjects clean prose (a mid-execution `@`-subject pollution defect was found + fully remediated — see §16).

| Task | Commits | SHAs |
|---|---|---|
| **T-3.1** v23 rename + migration + backup gate + atomic rename + L5 gate | 4 | `c059c9a` feat(data) v23 migration; `adfd574` refactor(web) rename + neutral title; `a376259` test(web) L5 grep gate; `a1ed824` test(pipeline) walk temporal fixture to HEAD |
| **T-3.2** candle helper + ticker_detail + theme2 | 3 | `e10411b` feat(web) candle infra; `97abb85` feat(web) convert ticker_detail+theme2; `9aa79d9` fix(web) volume-axis-by-role (per-task review fix) |
| **T-3.3** position_detail + BULZ zones | 2 | `b1f04fe` feat(web) _bulz_target_price; `b2c767c` feat(web) position_detail candles + BULZ zones |
| **T-3.4** market_weather + real current_stage + 50/200 MAs | 7 | `52017ad` convert weather; `78efa24` failing trend-state tests; `f4e1423` feat(pipeline) real state; `6389502` feat(web) refresh real state; `4629eef` honest JIT default; `a39e288` ruff/ASCII; `41974be` volume-ytick/ascii test updates |
| **T-3.5** thumbnail substrate + S6 reposition | 2 | `f711160` feat(web) S6 upper-right; `e4177ac` test(web) thumbnail substrate proof |
| **T-3.6** closer (pyproject + import smoke + L2 + artifacts) | 1 | `e3e05c9` build(web) mplfinance in [web] extra + smoke/metadata tests |
| **Codex chain fixes** | 2 | `bfaa5a8` fix(web) fill markers nearest-forward + harden candle helpers (R1-M2 + R1-m1/m3); `f59bdff` fix(web) reject numeric/NaT OHLC index (R2-M1 + R2-m1) |

---

## 2. Codex round chain (SINGLE chain; converged R3)

Per OQ-chain LOCK + Sec 9.1 Q7 — a SINGLE chain at the end of executing-plans. **Converged at Round 3** (within the 2–4 target).

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 4 | 3 | ISSUES_FOUND |
| R2 | 0 | 1 (new) | 1 (new) | ISSUES_FOUND |
| R3 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**Cumulative: 0 Critical, 5 Major, 4 Minor. 5 RESOLVED via code; 4 ACCEPTED as plan-LOCKed (rationale §6).**

**Transport (FB-N1):** the Codex MCP times out at 1s on this host (operator investigating separately — NOT touched). Backstop = `codex exec` CLI with INLINE artifacts; R1 via stdin (header digest of the LOCKs/corrections/signatures/review-lens + the full production git diff, ~8150 words). R2/R3 via `codex exec resume --last -c sandbox_mode="read-only"` (thread continuity preserved — Codex remembered prior rounds; delta-only prompts). The read-only sandbox emitted `windows sandbox: spawn setup refresh` errors when Codex tried to shell-read files, but Codex reasoned substantively from the inline diff (5 majors + 4 minors, all codebase-aware). `-c sandbox_mode="read-only"` used (not `-s`) on resume per the prior-implementer note.

---

## 3. Per-task completion summary (T-3.1 .. T-3.6)

- **T-3.1** — v23 migration `0023_phase14_sb3_chart_surface_rename.sql` (id-preserving single-table rebuild; `CASE`-rename `hyprec_detail`→`ticker_detail`; 3 partial indexes + cross-column CHECK recreated verbatim from the live v22 schema; explicit `BEGIN;…COMMIT;`). `EXPECTED_SCHEMA_VERSION=23`; `_phase14_sb3_backup_gate` STRICT `current==22`; `PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES`. Atomic Python/template rename (renderer fn, size constant, VM field, CSS class, surface literals, chart_jit dispatch, comments); neutral cache-safe title (dropped "hyp-rec detail" descriptor). L5 zero-orphan grep gate. gotcha #11 paired + #9 honored.
- **T-3.2** — `_render_candles_fig` + `_normalize_ohlc_for_mpf` + `_x_for_date` + `_MA_COLORS` (Okabe-Ito) + `OhlcNormalizationError`; converted `render_ticker_detail_svg` (vol ON) + `render_theme2_annotated_svg` (vol OFF); volume axis resolved by Volume-ylabel ROLE (live role match, geometry fallback); mpf x-margin pinned (`margins(x=0)`); conditional legend guard.
- **T-3.3** — `render_position_detail_svg` → candlesticks (MA 10/20/50); `_bulz_target_price` (= entry + planned_target_R*(entry−initial_stop)); risk/reward `axhspan` zones (target-only-if-present; invalid-long-shape skip+WARN; off-range drawn); fill markers re-attached.
- **T-3.4** — `render_market_weather_svg` → candlesticks (vol ON, MA 50/200, gridlines, ASCII trend badge); REAL `current_stage` at pipeline (short-lived read conn, asof=`lease_data_asof`) + refresh handler (asof=`last_completed_session(now)`, passed DIRECTLY — returns a `date`, no `.date()`); JIT default → honest `"undefined"`; fail-soft to `"undefined"` (pipeline no-abort); `current_stage` imported into both module namespaces.
- **T-3.5** — S6: `_annotate_*` family text moved to upper-right (x=0.98, ha="right"); P14.N1 thumbnail substrate proof (watchlist_row reuse for a non-watchlist ticker via the JIT; no new enum; no template change; row VMs already expose the (ticker, run) binding — zero production change needed).
- **T-3.6** — `mplfinance>=0.12` added to the `[web]` install extra; import-smoke + pyproject-metadata tests; L2 grep verified; per-surface visual-gate artifacts rendered.

Each task passed a two-stage review (spec compliance, then code quality) before the next; the T-3.2 review surfaced + fixed an Important issue (volume-axis "by role" was dead → made the role match live with geometry fallback).

---

## 4. Test surface verification

| Milestone | `pytest -m "not slow"` passed | Δ |
|---|---|---|
| Baseline (pre-SB3, `0bb376a`) | 6658 | — |
| After T-3.1 | 6673 | +15 |
| After T-3.2 (+ vol-axis fix) | 6696 | +23 |
| After T-3.3 | 6707 | +11 |
| After T-3.4 | 6717 | +10 |
| After T-3.5 | 6723 | +6 |
| After T-3.6 | 6726 | +3 |
| After Codex R1-M2 fix | 6733 | +7 |
| After Codex R2-M1 fix | **6735** | +2 |

**Net: +77 new/updated tests; 3 skipped (pre-existing); 0 slow tests added.** Final authoritative run: **6735 passed, 3 skipped**. `ruff check swing/` clean (0 E501 preserved). Within the spec §10 envelope (~40–80) — broader because the discriminating tests carry full assertions.

**Known unrelated flake:** `tests/research/test_pattern_cohort_evaluator_reader.py::test_ohlcv_reader_re_export_identity` intermittently fails under xdist worker ordering (an `importlib.reload` cross-module identity artifact). Confirmed: it passes in isolation (1 passed), imports only `research.harness.*` (no chart-surface file), and the SB3 diff touches ZERO research/cohort/ohlcv_reader files. Not an SB3 regression; reported by every task implementer.

**Mandatory discriminating tests present:** `mpf.plot(type="candle")` spy per converted surface; `_x_for_date` normalized-order-not-raw; `_normalize_ohlc_for_mpf` rejections (missing col / titlecase collision / multi-ticker / numeric index / NaT); single-cached-row-across-two-callers (L3); BULZ zone-bounds distinguish swapped/absent + target-from-R==120 + off-range drawn + invalid-shape skip+WARN; weather non-literal sentinel reaching the renderer at pipeline+refresh + fail-soft-to-undefined + pipeline-no-abort + JIT-default-undefined (behavioral); v23 schema-parity normalized-SQL + FK-restore success+rollback + mid-script rollback; L5 no-orphan grep; mplfinance `[web]`-extra metadata test; fill-marker nearest-forward placement.

---

## 5. Pre-locked decisions — verbatim verification

**Sec 9.1 (all honored):** Q1 (charts after temporal log = this SB), Q2 (serial tasks), Q4 (v23 rename THIS SB), Q5 (matplotlib/mplfinance, no JS), Q6 (operator browser-witnessed gate = §11), Q7 (SINGLE chain). **L1–L7 (all honored):** L1 (7-item scope only), L2 (v23 #11-paired + #9 + STRICT `pre_version==22`), L3 (renderer-kwargs uniformity + cache-collision tests), L4 (visual-gate binding; byte/string insufficient), L5 (two-tier zero-orphan grep), L6 (L2 preserved; `current_stage` reads candidate/eval rows only), L7 (P14.N8 computes real state, not suppress). **The 11 §1.3 OQ dispositions (all honored):** real `current_stage` at the 2 live sites + honest-undefined JIT default; 4 detail surfaces candlesticks / thumbnail-line; SINGLE chain; P14.N1 substrate-only; weather 50/200 MAs; v23 in-migration `CASE` rename; S6 text upper-right; pinned Okabe-Ito palette; BULZ `planned_target_R`-derived target-only-if-present; zone semantics binding / hues at gate; full renderer-fn rename.

---

## 6. Codex Major findings — resolutions + accepts (rationale)

**RESOLVED via code (5):**
- **R1-M2 (fill-marker exact-match regression):** the candle conversion placed fill markers via exact `df.index.get_loc`, silently dropping fills stamped on non-trading-day/tz-shifted dates (the pre-conversion code clamped to the next bar). Added `_x_for_fill_date(df, fill_date)` = first normalized-df bar with date ≥ fill_date, clamping to the last bar; only unparseable fills skipped. Exact-date overlays (window band) still use `_x_for_date`. Regression tests added. (`bfaa5a8`)
- **R1-m1 (`_MA_COLORS[window]` bare KeyError):** `_render_candles_fig` now raises a clear `ValueError` early for an unpinned window. (`bfaa5a8`)
- **R1-m3 (`_normalize_ohlc_for_mpf` index coercion):** non-`DatetimeIndex` now attempts `pd.to_datetime`, raising `OhlcNormalizationError` at the barrier. (`bfaa5a8`)
- **R2-M1 (coercion too permissive — numeric index → 1970 epoch):** the barrier now rejects numeric indexes BEFORE coercion (`is_numeric_dtype` → raise). (`f59bdff`)
- **R2-m1 (NaT survives coercion):** unconditional post-branch `df.index.isna().any()` → raise (covers both coercion + a DatetimeIndex arriving with NaT). (`f59bdff`)

**ACCEPTED as plan-LOCKed (4; ZERO silent accepts — each carries explicit rationale):**
- **R1-M1 (BULZ risk zone on `current_stop` vs target off `initial_stop`):** the LOCKed plan §C.3a geometry — risk band = entry→LIVE current_stop (coherent with the existing dashed current-stop line), reward = entry→FIXED planned target (inverse of the canonical r_mult formula). A trailed stop ≥ entry correctly skips the risk band (the invalid-long-shape skip+WARN). This locked-entry/live-stop basis is the explicit operator-surfaced V1 simplification (deviation from spec §7's avg-fill anchor, banked to V2) — **flagged for operator confirmation at the visual gate (confirm-item, §11).**
- **R1-M3 (refresh handler asof = `last_completed_session(now)`):** plan §C.4a LOCKed this for the refresh site BECAUSE it matches that handler's own `ChartRender.data_asof_date` write on the adjacent line (same anchor → consistent). The pipeline site uses the run's `lease_data_asof`. Each live site uses its correct context anchor.
- **R1-M4 (migration relies on runner FK-off):** by design + tested — `_apply_migration` sets `PRAGMA foreign_keys=OFF` during `executescript` and restores in `finally` on success+rollback (covered by `test_apply_migration_restores_foreign_keys_after_v23` / `_after_rollback` / the FK-survival test asserting `PRAGMA foreign_key_check == []`). Migrations run only through the runner.
- **R1-m2 (`_x_for_date` unused `price_ax`):** intentional single-coupling-point marker; keeping it makes a future mpf date-coords upgrade a one-function change touching all overlay sites uniformly.

---

## 7. Production-code citations verified at task completion

- 5 renderers at `swing/web/charts.py` (pre-rename `180/226/284/334/481`); `render_hyprec_detail_svg`→`render_ticker_detail_svg`, `_HYPREC_DETAIL_SIZE_PX`→`_TICKER_DETAIL_SIZE_PX`.
- `current_stage(conn, ticker, asof_date: date) -> str` at `swing/patterns/foundation.py:745` (returns `"stage_2"`/`"undefined"`; SELECT-only). The spec's cited `review_form.py:454` caller does NOT exist — used the detector pattern (correction 1, confirmed).
- `last_completed_session(now_local: datetime) -> date` at `swing/evaluation/dates.py:21` — **returns a `date`; the `.date()` suffix was DROPPED at the refresh site** (forward-binding lesson #1, confirm-item resolved).
- `lease_data_asof(cfg, lease) -> str` at `swing/pipeline/runner.py`; pipeline asof = `date.fromisoformat(lease_data_asof(...))`.
- **Pipeline weather site:** the function-level `conn` is CLOSED earlier in `_step_charts`; the implementation opens a SHORT-LIVED read connection (`connect()` / `finally: close()`) for `current_stage` — NOT a reuse of the closed conn (a plan-anchor inaccuracy caught + handled correctly).
- `Trade.entry_price/initial_stop/current_stop/planned_target_R` verified at `swing/data/models.py`.
- **Anchor-list reconciliation:** the dispatch brief §3 anchor list erroneously cited `routes/patterns.py` / `_pattern_card.html.j2` / `view_models/patterns/detail.py` as `hyprec_detail`-bearing — a re-grep at HEAD showed they do NOT contain the token; the actual 10-file set matched plan §B (authoritative). Implementers used the ground-truth grep.

No production-drift escalation fired. The OHLC-bar-shape escalation trigger did NOT fire (bars already carry OHLC).

---

## 8. Schema impact verdict (v23 applied)

Single-table rebuild of `chart_renders` (`0023_phase14_sb3_chart_surface_rename.sql`): CHECK enum `hyprec_detail`→`ticker_detail` via CREATE-COPY(id-preserving `CASE`)-DROP-RENAME; 3 partial indexes + cross-column CHECK recreated verbatim (derived from the live v22 `sqlite_schema`, not hand-transcribed); `INSERT…SELECT` row migration; `EXPECTED_SCHEMA_VERSION=23`; `_phase14_sb3_backup_gate` STRICT `current==22 AND target>=23`. FK `pattern_detection_events.chart_render_id` (`ON DELETE SET NULL`) preserved via id-preserving copy + FK-off-during-rebuild + `_apply_migration` FK-restore in `finally` (success + rollback). **Exactly ONE `0023_*.sql`; NO v24; `EXPECTED_SCHEMA_VERSION == 23`; the v22 temporal-log substrate (`pattern_detection_events`, `pattern_forward_observations`) UNTOUCHED.** Test coverage: rename-rows-same-id, FK-survival (`foreign_key_check == []`), normalized schema-parity (differs by exactly the one enum token), backup-gate fires-strict-22 / skips-pre-v22, migrate-twice no-op, **mid-script rollback through the real runner** (`_BROKEN_0023_BEFORE_COMMIT` raises pre-COMMIT, version stays 22), FK-restore on success + rollback, dataclass rejects `'hyprec_detail'`.

---

## 9. Atomic-rename verification (L5)

L5 two-tier zero-orphan grep gate (`tests/web/test_chart_renderer_rename_no_orphans.py`) PASSES: scans `swing/**/*.py|*.sql`, templates, static `.css/.js`; forbids `hyprec_detail / render_hyprec_detail_svg / hyprec-detail-chart / _HYPREC_DETAIL_SIZE_PX / "hyp-rec detail"`; allows only the `0020_*.sql` + `0023_*.sql` globs. Independent grep at HEAD: the forbidden tokens appear ONLY in `0020_*.sql` (frozen historical) + `0023_*.sql` (the `CASE` source token) — both allowlisted. Zero runtime orphans. The neutral-title regression (`test_ticker_detail_title_is_neutral_no_surface_descriptor`) confirms the leaked "hyp-rec detail" prose is gone.

---

## 10. L2 LOCK verification

`tests/integration/test_l2_lock_source_grep.py` PASSES (2/2) — no new `schwabdev.Client.*` call site across the sub-bundle. `current_stage` reads `candidates`/`candidate_criteria`/`evaluation_runs` rows only (no Schwab/yfinance); the weather state derivation added no broker/market-data calls. L6 preserved.

---

## 11. Operator-witnessed gate readiness (S1–S7) + artifacts

**The BINDING correctness check is the RENDERED chart (matplotlib; byte/string tests insufficient — L4).** The operator is the named gate owner.

**Per-surface visual-gate artifacts** (rendered, deterministic, no-network) — on disk in the worktree at `exports/diagnostics/phase14-sb3/` (the dir is `.gitignore`d, so the artifacts + repro script are untracked-by-design; regen below):

| Surface | Artifact | Bytes |
|---|---|---|
| S3 ticker_detail | `ticker_detail-TST.svg` | 142241 |
| S4 position_detail (BULZ) | `position_detail-TST.svg` | 156242 |
| S5 market_weather (stage_2) | `market_weather-stage_2.svg` | 130441 |
| S5 market_weather (undefined) | `market_weather-undefined.svg` | 129458 |
| S6 theme2 (flat_base) | `theme2_annotated-flat_base-TST.svg` | 119917 |
| S6 theme2 (vcp) | `theme2_annotated-vcp-TST.svg` | 117496 |
| watchlist_row (line baseline) | `watchlist_row-TST.svg` | 36663 |

**Regen command** (from the worktree root): `python exports/diagnostics/phase14-sb3/render_sb3_surfaces.py` (PNG generation is best-effort — `cairosvg` not installed → SVG-only; the operator's browser renders SVG directly).

**S1–S7 ladder:**
- **S1** pytest + ruff — 6735 passed / 3 skipped (1 unrelated xdist flake), ruff clean. ✓ (automated)
- **S2** v23 schema — apply on a real v22 DB: `schema_version==23`; rows migrated same-id; backup `swing-pre-phase14-sb3-migration-<ISO>.db`; `foreign_key_check` clean. ✓ (tested; operator may re-verify on the live DB)
- **S3** ticker_detail — candlesticks + 10/20/50/150/200 MAs (Okabe-Ito) + neutral title `{ticker} | last N bars`. **OPERATOR BROWSER.**
- **S4** position_detail — candlesticks + risk (entry→stop) + reward (entry→target) zones + ASCII legend. **OPERATOR BROWSER. ⚠ CONFIRM-ITEM:** the BULZ zones anchor on the LOCKED `trade.entry_price` (V1 simplification, deviation from spec §7's avg-fill anchor) and the risk band uses the LIVE `current_stop` while the target derives from `initial_stop` — confirm this basis is acceptable, or it goes to V2 (avg-fill entry + re-derived target).
- **S5** market_weather — candlesticks + 50/200 MAs + REAL trend badge (`trend: stage_2`/`trend: undefined`, NOT `n/a`); pre/post-refresh visually equivalent. **OPERATOR BROWSER.**
- **S6** theme2_annotated flat_base — duration text upper-right, no legend overlap; vcp worst-case (full contraction list + 5 MAs) no overrun. **OPERATOR BROWSER.**
- **S7** L2 + L5 grep gates green. ✓ (automated)

---

## 12. NEW forward-binding lessons (for SB4 + CLAUDE.md gotcha consideration)

1. **mpf pads the positional x-axis (~7 bars/side)** — defeat it with `price_ax.margins(x=0)` (+ vol_ax) or the integer-extent contract breaks and gutters appear.
2. **mplfinance labels the volume panel `"Volume  $10^{6}$"` (auto scale-factor suffix)** — an exact `ylabel == "Volume"` role match is DEAD; use a normalized prefix match (`startswith("volume")`), geometry as fallback.
3. **A PowerShell here-string (`@'…'@`) piped through the Bash tool leaks lone `@` lines into commit message subject/body** — git's `%s` joins them with a space (masking the defect); use `git commit -m "…"` directly, never a here-string via bash. (See §16; candidate CLAUDE.md gotcha.)
4. **`git filter-branch --msg-filter` silently no-ops on Git-for-Windows in this setup** — use reset + cherry-pick + `git commit --amend -F -` to reword mid-branch commits; verify with a tree-hash match.
5. **`last_completed_session` returns a `date`, not a datetime** — never append `.date()`.
6. **In `_step_charts`, the function-level `conn` is closed before the market_weather block** — open a short-lived read connection for any post-close read (mirrors the fills lookup pattern).
7. **An mplfinance candle conversion is additive over a close-line** — but the fill-marker x-placement must preserve nearest-forward-bar clamping, not switch to exact `get_loc` (which silently drops off-bar-date fills).
8. **A defensive index coercion (`pd.to_datetime`) is too permissive for numeric indexes** (→ 1970 epoch) — reject numeric + NaT explicitly at the barrier.

---

## 13. ASCII discipline scope (gotcha #32)

NEW files: `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql`, `tests/data/test_v23_migration.py`, `tests/web/test_chart_renderer_rename_no_orphans.py`, `tests/web/test_weather_trend_state.py`, `tests/web/test_web_charts_import_smoke.py`, `tests/web/conftest.py` (fixtures). MODIFIED: `swing/web/charts.py`, `swing/web/chart_jit.py`, `swing/web/routes/dashboard.py`, `swing/pipeline/runner.py`, `swing/data/db.py`, `swing/data/models.py`, `swing/data/repos/chart_renders.py`, `swing/web/view_models/dashboard.py`, `swing/web/view_models/watchlist.py`, `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2`, `pyproject.toml`. All user-facing strings (renderer titles, trend badge, BULZ legend, WARN logs, CLI/stdout paths) are ASCII; renderers return bytes. `§`/em-dash appear ONLY in code COMMENTS/docstrings (consistent with the pre-existing codebase convention — 2186 `§` + 2309 em-dash occurrences across `swing/`); the ASCII gotcha targets user-facing OUTPUT, not comments — zero runtime cp1252 risk; full suite green confirms.

---

## 14. Cumulative gotcha application (per task)

matplotlib mathtext (title vs body two-gate; `mpf.plot` title→suptitle suppressed, our `_set_suptitle_no_math`) — T-3.2/3/4/5; #11 paired (CHECK+constant+validator+`_row_to_*`+renderer+routes+VMs+templates+tests in T-3.1); #9 BEGIN/COMMIT/ROLLBACK + mid-script rollback-through-runner; #11 STRICT backup gate `==22` + migrate-twice; Expansion #10c kwargs uniformity (shared `_render_candles_fig` + cache-collision single-row + 2-live-site weather tests); #11 taxonomy two-tier zero-orphan grep (static + prose); byte-parity insufficiency (non-literal sentinel + `mpf.plot` candle spy + behavioral JIT default + binding visual gate); session-anchor read/write (weather `lease_data_asof`/`last_completed_session`, not `action_session`); #4 SQL/field verification (BULZ `planned_target_R`; `last_completed_session` return-type); #27 fail-soft WARN no-silent-skip; L2 source-grep; #16/#32 ASCII + renderers return bytes; ZERO Co-Authored-By + trailer-parse-hazard (plain-prose final paragraphs, `%(trailers)` `[]`).

---

## 15. Worktree teardown status

**Worktree RETAINED + CLEAN** for orchestrator merge + the operator-witnessed gate. `git status --porcelain` empty. Branch at `f59bdff`, 21 commits ahead of `0bb376a`. A safety ref `sb3-backup-prereword` (pointing at the pre-commit-hygiene-fix tip) was created during the §16 rewrite — **the orchestrator should delete it (`git branch -D sb3-backup-prereword`) before/at merge.** The `exports/diagnostics/phase14-sb3/` artifacts + repro script remain on disk (gitignored) for the gate.

---

## 16. ZERO Co-Authored-By + commit-subject hygiene

**Zero `Co-Authored-By` / `noreply@anthropic.com` across all 21 commits** (`git log 0bb376a..HEAD --format='%(trailers)'` empty everywhere; final `-m` paragraphs plain prose). Streak preserved.

**Mid-execution defect found + remediated:** the T-3.4 implementer authored 7 commits via a PowerShell here-string piped through the Bash tool, which leaked a lone `@` line at the START and END of each of those 7 commit messages (git's `%s` masked it by joining the `@` to the real subject with a space; trailers stayed empty so the Co-Authored-By streak was never at risk). The orchestrator detected it at the T-3.6 whole-branch audit and remediated via reset-to-T-3.3-HEAD + cherry-pick + `git commit --amend -F -` (deleting every lone-`@` line with `sed '/^@$/d'`), **verified by a tree-hash match (zero content change) + a zero-lone-`@` scan across all branch messages.** (`git filter-branch --msg-filter` silently no-op'd on this Git-for-Windows setup — see lesson §12.4.) All subjects are now clean conventional-commit prose.

---

## 17. CLAUDE.md status-line refresh draft (for orchestrator at merge)

> **Sub-bundle 3 (chart-surface uniformity; V2.G1 + V2.G2 v23 rename + P14.N1/N2/N4 + P14.N8 + S6) EXECUTING-PLANS SHIPPED at `<merge-sha>`** — 6 tasks (T-3.1..T-3.6), 21 commits, Codex single chain CONVERGED R3 (0C+5M+4m; 5 resolved-via-code, 4 accepted-as-LOCKed). v23 atomic `hyprec_detail`→`ticker_detail` table-rebuild APPLIED (`EXPECTED_SCHEMA_VERSION=23`; STRICT `pre_version==22` backup gate; FK-survival + mid-script rollback tested); shared mplfinance `_render_candles_fig` across the 4 detail renderers (thumbnail stays line); BULZ risk/reward zones (target from `planned_target_R`, locked-entry V1 basis); real `current_stage` at 2 live weather sites + honest-undefined JIT default; 50/200 weather MAs; S6 text upper-right; P14.N1 thumbnail substrate (wiring deferred to SB4). ~6735 fast tests green (+77; baseline 6658) + ruff 0 E501; L2 + L5 green. **Schema v23 LIVE. Sub-bundle 4 (review + journal UX) NEXT (serial).** Operator-witnessed visual gate S3–S6 (browser) + the BULZ entry-anchor confirm-item are the remaining merge-blockers.

---

## 18. Operator-witnessed gate handback summary

All 6 tasks shipped; Codex single chain converged R3 at NO_NEW_CRITICAL_MAJOR; full fast suite green (6735 passed, +77; 1 unrelated xdist flake) + ruff clean; v23 applied (one `0023_*.sql`, no v24, v22 substrate untouched); L2 + L5 gates green; ZERO Co-Authored-By + clean subjects. **Remaining merge-blockers (orchestrator → operator):** the binding operator-witnessed visual gate S3–S6 (real browser through ticker_detail / position_detail / market_weather / theme2 surfaces), and the **BULZ entry-anchor confirm-item** (S4): the zones anchor on the LOCKED `trade.entry_price` with the risk band on the LIVE `current_stop` and the target derived from `initial_stop` — an explicit V1 simplification surfaced for operator confirmation (re-adding avg-fill anchoring is a V2 change requiring BOTH the entry swap AND a target re-derivation). On gate-pass the orchestrator merges per the orchestrator-performs-merge discipline.

---

*End of return report. Phase 14 Sub-bundle 3 executing-plans COMPLETE: v23 atomic `hyprec_detail`→`ticker_detail` table-rebuild + shared mplfinance `_render_candles_fig` across 4 detail renderers + BULZ risk/reward zones + real `current_stage` at 2 live weather sites + honest-undefined JIT default + 50/200 weather MAs + S6 reposition + P14.N1 thumbnail substrate; 21 commits; Codex single chain converged R3 (5 resolved / 4 accepted-as-LOCKed); ~6735 fast tests green; per-renderer visual-gate artifacts ready. Branch pushed; ready for orchestrator QA + operator-witnessed gate + merge.*
