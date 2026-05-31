# Cross-Phase Operational Backlog

> **Filename note (2026-05-01):** this file is named `phase3e-todo.md` for historical reasons (it was created at the end of the Phase 3d walkthrough as the Phase 3e backlog). It has since accumulated cross-phase items (Phase 4 / 4.5 / 6-9 + standalone bundles + Tier-3 deferrals + research-branch followups). The filename is preserved to keep ~46 cross-references in shipped briefs valid; the canonical title is "Cross-Phase Operational Backlog." Not a commitment, just a trackable list.

> **Archive companion (2026-05-05):** SHIPPED + closed entries previously inline have moved to `docs/phase3e-todo-archive.md`. Fresh-orchestrator bootstrap reads only this active file; grep the archive on demand for historical context (commit hashes, prior dispatches). Retention discipline + archive-split trigger are documented in `docs/orchestrator-context.md` §"Maintenance: retention discipline."

> **Archive companion (2026-05-18 Phase 12.5 #3 T-3.2 split):** Additional SHIPPED entries dated 2026-05-12 and earlier moved to [`docs/phase3e-todo-archive.md`](docs/phase3e-todo-archive.md) (boundary 2026-05-12 inclusive; SHIPPED-only predicate). 23 sections moved this pass; archive doc gained an "Appended Phase 12.5 #3 archive-split" appendix at its end. Grep both files for full history.

---

## 2026-05-30 #5 Phase 14 close-out + NEW Sub-bundle 5.5 (Schwab-focused) punch-list -- banked-items consolidation (operator-decided 2026-05-30)

**Purpose:** consolidate every banked/orphaned Phase-14-scope item into ONE close-out tracker so nothing is lost. Compiled via a full sweep of the commissioning brief (Sec 1 deferred-list + Sec 8 forward-look) + the 4 SB executing-plans return reports + the SB1-SB4 phase3e-todo entries. Operator bucketing decisions dated 2026-05-30.

**Updated Phase 14 forward sequence:** SB5 (metrics overview; P14.N5; brainstorm in progress) -> **NEW SB5.5 (Schwab-focused)** -> Phase 14 close-out polish batch + B-7 final touch -> Phase 14 close-out review (Sec 9.1 Q6: all sub-bundles merged + operator browser-witnessed cross-sub-bundle integration).

**NEW Sub-bundle 5.5 -- Schwab-focused (operator-decided 2026-05-30):**
- **A-3 Schwab daily-bar web wiring** (SB3 follow-up #4): the web-side SMA/daily-bar path (`OhlcvCache`/`PriceCache` constructed plain in `swing/web/app.py`) is yfinance-only by wiring; the Schwab market-data ladder (`swing/integrations/schwab/marketdata_ladder.py`, gated `env==production AND marketdata_ladder_enabled`) is pipeline-side + NOT installed on the web caches. Wire it onto the web SMA path. **Touches the L2-locked Schwab surface** -- A-3 installs the EXISTING ladder (intended ZERO new `schwabdev.Client.*` call SITES beyond the ladder's own); confirm the L2 framing at SB5.5 brainstorm.
- **P14.N7 schwabdev background `checker`-thread resilience**: schwabdev's background token-refresh `checker` thread dies with uncaught `ConnectionError`/`NameResolutionError` under sleep/wake/DNS-failure cycles -> silent token-refresh degradation until `swing web` restart. Wrap/replace the checker loop with exception-isolation + retry-with-backoff; add an operator-visible degraded-health surface (`swing schwab status` checker-liveness); discriminating test simulates DNS failure during refresh.
- Coheres around the Schwab integration surface; both infrastructure/resilience; L2 LOCK discipline central. Its own copowers cycle.

**Phase 14 close-out polish batch (small, Phase-14-scope; sequence after SB5/SB5.5):**
- **P14.N1 (dashboard portion -- the orphaned bit)** -- open-positions + hyp-rec TABLE thumbnails. Substrate + the render-direct helper `render_trade_window_thumbnail_svg` (`swing/web/trade_charts.py:87`) exist; SB4 proved the journal-listing VM->row-template pattern; wire onto `open_positions_row.html.j2` + `hypothesis_recommendations_row.html.j2` + their VMs. Banked at SB4 OQ-3 (operator chose "journal listing only"). (P14.N1 substrate [SB3] + journal-listing thumbnails [SB4] already SHIPPED; this is the remaining dashboard-table portion.)
- **A-1 market_weather 200MA fetch-window** (SB3 #2) -- widen the benchmark fetch window to >=200 trading bars (~300 calendar days) at both sites (pipeline `_bars_or_none(window_days=200)` + the refresh handler's `get_or_fetch(ticker=benchmark)`) + a regression asserting >=200 bars reach `render_market_weather_svg`.
- **A-2 theme2_annotated vcp 5-contraction label crowding** (SB3 #3) -- cosmetic; reposition the right-edge labels off the price y-axis ticks.
- **A-4 `_bulz_*` -> general rename** (SB4) -- cosmetic; rename `_bulz_target_price`/`_draw_bulz_zones` (`swing/web/charts.py:609,701`) -> general (`_rr_target_price`/`_draw_risk_reward_zones`) + comments/WARN text; the zones are a GENERAL open-long-position feature, NOT BULZ-specific.
- **Group (a) open minor advisories (operator-added to the close-out batch 2026-05-30; C-1/C-2/C-3/C-5/C-6/C-19):** (1) `DailyManagementTileVM` PROVISIONAL flag defaults to `True` -> flip to `False` or make the field required (SB1); (2) daily-management tooltip "covers today" -> "covers this row's session date" (SB1); (3) backfill CLI artifact-write `OSError` -> wrap to `ClickException` instead of a raw traceback (SB1); (4) strengthen the `BEGIN IMMEDIATE` ordering regression test to assert lock-vs-SELECT/UPDATE order (SB1); (5) narrow the backfill apply-path write-lock so it is NOT held during the restore-artifact filesystem write (SB1); (6) harden the cross-SB `test_ohlcv_reader_re_export_identity` xdist co-residency flake (e.g. `@pytest.mark.xdist_group`; passes in isolation). All small; sources in the SB1 executing-plans return report §2 + the cross-SB flake note.

**B-7 operator failure-mode classification UI -- Phase 14 FINAL TOUCH (operator-decided 2026-05-30):** extend the CR.1 review surface to capture operator-annotated failure reasons (e.g. "stopped out on volatility", "thesis invalidated", "execution issue") for outcome-attribution analysis. Likely a small dedicated cycle (new review field(s) + UI) -- assess schema impact at its brainstorm (may add a nullable review column -> v24 STRICT `pre_version`, or reuse existing). Sequenced as the LAST Phase 14 feature before close-out review.

**A-5 styled full-page 404 (SB4 FIX-5) -- CLOSED (operator 2026-05-30, "no intention to revisit").** The JSON 404 stands. Removed from the punch-list.

**Phase 15+ (tracked; NOT Phase 14; depend on temporal-log accumulation / strategic decisions):** B-1 substrate-size augmentation; B-2 Finviz filter widening; B-3 cohort-stability LOCK (gotcha #37 -- already eliminated-by-construction in the v22 temporal log); B-4 D2 survival-rate remediation; B-5 real-time prospective tracking; B-6 multi-pattern composites; B-8 other-gates market-regime investigation.

**Minor V2 items (C-1..C-19):** **Group (a) -- the ~6 genuinely-open minor advisories -- MOVED INTO the close-out polish batch above (operator 2026-05-30).** Remaining OUT of close-out: ~3 accepted-as-LOCKed-by-design (SB2 schema-version test NAMES for grep-history; observe read-then-write benign under single-lease; repo fixture `ohlc_today_json` shape nit) + ~10 already-fixed forward-binding lessons captured for reference (mpf x-axis padding `margins(x=0)` / volume-label auto-scale; `last_completed_session` returns `date`; post-close read-connection; fill-marker nearest-forward x-placement; index-coercion-rejects-numeric; synthetic-bars-use-planted-detections; derived-duration state-predicate). Full detail in the per-SB executing-plans return reports §"V2 candidates" / §"forward-binding lessons". Groups (b)+(c) require NO close-out action.

**Forward action:**

- [ ] SB5 (metrics overview; P14.N5) brainstorm (IN PROGRESS) -> writing-plans -> executing-plans
- [ ] **SB5.5 (Schwab-focused: A-3 + P14.N7) brainstorm dispatch brief** when sequenced (after SB5)
- [ ] Phase 14 close-out polish batch (P14.N1-dashboard + A-1 + A-2 + A-4 + group-(a) minor advisories)
- [ ] B-7 operator failure-mode classification (Phase 14 final touch)
- [ ] Phase 14 close-out review (Sec 9.1 Q6: all merged + operator browser-witnessed cross-sub-bundle integration)

---

## 2026-05-30 #4 Phase 14 Sub-bundle 4 (review + journal UX) EXECUTING-PLANS SHIPPED end-to-end at `31da4a5` -- operator-witnessed gate PASS (S3-S7); 32 impl + 6 gate-fix commits; two GENUINE copowers v2.0.2 WSL Codex chains CONVERGED (EP-R2 + GF-R2); 6905 fast tests green on MERGED main; NO schema change (v23 held); read-mostly; 9 OQs operator-LOCKed; `_bulz_*` rename banked; FIX-5 (styled 404) operator-skipped

**Sub-bundle 4 executing-plans SHIPPED end-to-end 2026-05-30 #4** at integration merge `31da4a5` of `phase14-sub-bundle-4-review-journal-ux-executing-plans` via `--no-ff`. 32 implementation commits (6 slices) + 6 gate-fix commits + merge. 18 swing/ files (NEW `swing/web/trade_charts.py` + `swing/web/view_models/trade_chronology.py` + render lock in `charts.py` + journal route/VM + 8 templates) + ~30 NEW test files; ZERO swing-domain writes. Schema **v23 LOCKED** (NO migration; render-direct keeps SB4 schema-free; v22/v23 substrates UNTOUCHED). ZERO Co-Authored-By across all branch commits + merge (`%(trailers)` empty). Merge-base `b17efc0`.

**What shipped:** CR.1 review enrichment (exit-data fields + a render-direct closed-trade chart over `entry-30d..exit+10d`, lazy-loaded). P14.N6 browse-the-database journal: rich per-trade listing (open/shares/dollar-total_risk/closing/final_R/entry-flags[`trade_origin`-derived hyp-rec] + **Exit-date + Days-open** columns) + server-side sort (13 keys, None-safe) + filter (every option value-contract-verified; open trades in scope) + journal-only lazy candlestick thumbnails + clickable drill-down (unified chronology merging fills/trade_events/daily_management/review with precedence `fill<daily_management<trade_event<review`; `review_log` excluded [no `trade_id`]; annotated render-direct chart). BULZ row-expand rewired (legacy static PNG -> SB3 `position_detail` SVG via read-only `get_cached_chart_svg`; L7 reversal recorded in the chart-access UX brief). Process-wide matplotlib **render lock** (`RLock` at the shared `charts.py` boundary; all 5 public renderers + 2 helpers; no-deadlock test per path).

**Two GENUINE WSL Codex chains CONVERGED** (copowers v2.0.2; WSL `codex exec` reads the worktree from disk; MCP dead in the VS Code ext): main chain EP-R1 (1M -- a browser-only malformed journal `<thead>` `<tr>` loss only the from-disk transport could see) -> EP-R2 NO_NEW_CRITICAL_MAJOR; gate-fix chain GF-R1 (1M -- `days_open` anchored to today for terminal-no-exit trades) -> GF-R2 NO_NEW_CRITICAL_MAJOR. ALL resolved-via-code, ZERO accepted. `.copowers-findings.md` holds both chains.

**Operator-witnessed gate PASS (orchestrator-run server on :8081 from the worktree against the live v23 DB; read-only):** S3 CR.1 (covered mechanically + chart confirmed live via S7 -- the review FORM is closed-AND-unreviewed-only so it 404s for reviewed trades by design; all closed trades reviewed -> not live-reachable, SB1-S5a precedent). S4 BULZ row-expand SVG + cross-check vs trade-detail PASS. S5 listing + thumbnails PASS. S6 sort/filter PASS (after the gate-fix). S7 drill-down chronology + annotated chart + JSON-404 PASS. **Gate found defects on first walk** (S5 wanted Exit-date+Days-open columns; S6 sort broken on 6 columns + filter "Invalid filter, showing all" + 'Open' empty; S7 chronology verbiage duplicated) -> consolidated **gate-fix cycle** (FIX-1..FIX-4; FIX-5 styled-404 operator-skipped) -> re-gate S5/S6/S7 all PASS.

**Brief-vs-reality at the gate (operator-verified):** PTEN/VSAT blank hypothesis is CORRECT (`trade_origin='manual_off_pipeline'`, no `hypothesis_label`) -- validates the OQ-4 `trade_origin` (not `candidate_id`) derivation. The BULZ risk/reward zones are a GENERAL open-long-position feature, NOT ticker-special-cased (`_bulz_*` helper naming is misleading -> rename banked as future cosmetic work, operator "proceed as-is").

**Verified green (`feedback_no_false_green_claim`):** the orchestrator re-ran `python -m pytest -m "not slow" -q` ON THE MERGED HEAD (`31da4a5`) and READ the result: **6905 passed, 3 skipped, 0 failed** (155.98s). `ruff check swing/` clean. NOT carried from the branch.

**Forward action sequence (orchestrator-side; THIS pass):**

- [x] QA per `feedback_orchestrator_qa_implementer_product` (both the 32-commit ship + the 6-commit gate-fix: ZERO Co-Authored-By; code-phase scope clean; NO `0024`; read-mostly [no write SQL/repo calls]; render lock `RLock` verified at `charts.py:83`; `_SORT_KEYS` 5->13; FIX-3 empty-string->None + `list_open_trades` scope; FIX-4 chronology kind/summary non-overlap; chronology `review_log`-excluded)
- [x] Operator-witnessed gate (orchestrator-run :8081 server; operator-driven browser S3-S7; gate-fix cycle; re-gate PASS) + server killed (PID verified dead, port free, no stragglers)
- [x] Merge `--no-ff` at `31da4a5` + push origin/main + reinstall `swing` from main + worktree/branch teardown
- [x] BINDING suite re-run on merged main (6905 green, READ) + phase3e-todo top entry (THIS) + CLAUDE.md line-3 refresh
- [ ] **Sub-bundle 5 (metrics overview; P14.N5) brainstorming dispatch brief** (matplotlib SVG per Sec 9.1 Q5; the LAST sub-bundle) + inline prompt
- [ ] SB5 brainstorm -> writing-plans -> executing-plans cycle, then **Phase 14 close-out review (Sec 9.1 Q6: all 5 sub-bundles merged + operator browser-witnessed cross-sub-bundle integration)** + sequence the banked Schwab-daily-bar-wiring item (follow-up #4) with the operator

---

## 2026-05-30 #3 Phase 14 Sub-bundle 4 (review + journal UX) WRITING-PLANS SHIPPED at `573bcb3` -- plan 2089 lines (§A-§O; 6 slices / ~25 tasks); GENUINE copowers v2.0.2 WSL Codex chain (reads the tree) CONVERGED WP-R6 (0C/17M/6m; narrowed 6->5->4->2->0); 9 OQs operator-LOCKed; NO schema change (v23 held); executing-plans dispatch NEXT

**Sub-bundle 4 writing-plans SHIPPED 2026-05-30 #3** at merge `573bcb3` of `phase14-sub-bundle-4-review-journal-ux-writing-plans` via `--no-ff`. 7 branch commits (draft `bd6bf86` + WP-R1..R6 fix/record `88eddc8`/`837eadd`/`7701cae`/`775623c`/`8e9b7ed`/`76b4dd0`) + merge. Docs-only (plan `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-4-review-journal-ux-plan.md` 2089 lines + `.copowers-findings.md` writing-plans section appended; ZERO swing/ + tests/ writes). Schema v23 LOCKED (no `0024`; render-direct keeps SB4 schema-free). ZERO Co-Authored-By across branch + merge (`%(trailers)` empty). Merge-base `0d5c0a3`.

**GENUINE v2.0.2 WSL Codex chain (single, OQ-8 LOCK; run to convergence):** WP-R1 0C/6M/2m -> R2 0C/5M/1m -> R3 0C/4M/0m -> R4 0C/2M/1m -> R5 0C/0M/2m (NO_NEW_CRITICAL_MAJOR) -> R6 0C/0M/0m CLEAN. Cumulative 0C/17M/6m; ALL 17 majors resolved-via-code, ZERO accepted. The chain READ THE TREE every round (WSL `codex exec` + `resume --last`, read-only) -> caught production-truth errors at finer granularity than the orchestrator-verified anchors: `_render_candles_fig` is a 3-tuple with no title kwarg (`charts.py:412-419`); FIVE public `render_*_svg` not 2; BULZ cache-miss-renders-blank risk (`chart_reason_message` is legacy-PNG scope); `build_review_vm` is closed-only (`trades.py:1223`); `trade_events` payload is `payload_json`+`rationale` NOT `notes`; `daily_management_records` detail columns at `0016*.sql:60-72,84-94`. Persisted at `.copowers-findings.md` ("WRITING-PLANS review" section).

**9 OQs operator-LOCKed (triage 2026-05-30; in the writing-plans dispatch brief §1.3):** OQ-1 render-direct closed charts (`entry-30d..exit+10d`) / OQ-2 no enum, no schema / OQ-3 journal-listing thumbnails ONLY (dashboard breadth banked) / OQ-4 `trade_origin`-derived hyp-rec flags (no FK) / OQ-5 unified chronology, precedence `fill < daily_management < trade_event < review` / OQ-6 dollar total_risk / OQ-7 market_weather 200MA banked standalone / OQ-8 single chain / OQ-9 whole-`<table>` outerHTML swap.

**Two highest-risk executing-plans items (plan §M):** (a) process-wide matplotlib **render lock** (RLock at the shared `charts.py` boundary; decorate all 5 public renderers + the 2 new helpers; single outer acquisition; no-deadlock test per chart path; thumbnail-DoS guard); (b) the unified **chronology** per-source contracts (production-verified columns; `_normalize_ts` malformed-timestamp handling; `review_log` excluded as it has no `trade_id`). 6 slices: 0 (CR.1 + `trade_charts.py` + render lock) + 1 (BULZ rewire) independent; 2->3->4->5 serial. ~70-105 new tests / ~25-34 commits / 0 new slow.

**Banked follow-up (operator-confirmed 2026-05-30, "proceed as-is, bank rename"):** the SB3 `_bulz_target_price` + `_draw_bulz_zones` helpers (`swing/web/charts.py:609,701`) + their comments/WARN text are MISLEADINGLY NAMED -- the risk/reward shaded zones are a GENERAL open-long-position feature (computed from `planned_target_R`/`entry_price`/`initial_stop`; per-ticker `%s` skip+WARN), NOT BULZ-specific (no `if ticker=='BULZ'` anywhere; BULZ was just the example position when P14.N4 was flagged). Future cosmetic refactor: rename `_bulz_*` -> general (e.g. `_rr_target_price` / `_draw_risk_reward_zones`) + update comments/WARN strings. Out of SB4 scope; private-helper rename; low-risk; NOT urgent.

**Forward action sequence (orchestrator-side; THIS pass):**

- [x] QA per `feedback_orchestrator_qa_implementer_product` (7-commit ZERO Co-Authored-By; docs-only; plan 2089 lines; v23 held / no `0024`; genuine WSL chain confirmed via `.copowers-findings.md` monotonic-narrowing signature + code-grounded catches; BULZ-generality verified by grep -> answered the operator's question)
- [x] Merge `--no-ff` at `573bcb3` + push origin/main + worktree/branch teardown (only main worktree remains)
- [x] phase3e-todo new top entry (THIS) + CLAUDE.md line-3 refresh + `_bulz_*` rename banked
- [ ] **Sub-bundle 4 executing-plans dispatch brief** (consume plan §G 6 slices + the §1.3 OQ LOCKs + the render-lock + chronology highest-risk items + the operator-witnessed S3-S6 browser gate; re-confirm the gate split per `feedback_visual_gate_both_render_and_browser`) + commit BEFORE inline prompt
- [ ] SB4 executing-plans ship + QA + single Codex chain (run to convergence) + operator-witnessed gate + merge + housekeeping
- [ ] SB5 (metrics overview; P14.N5) then Phase 14 close-out review (Sec 9.1 Q6: all 5 sub-bundles merged + operator browser-witnessed)

---

## 2026-05-30 #2 Phase 14 Sub-bundle 4 (review + journal UX) BRAINSTORM SHIPPED at `2cf30f9` -- spec 1277 lines; GENUINE copowers v2.0.2 WSL Codex chain (reads the tree) CONVERGED Re-R4 (0C/8M/8m); 8 code-grounded majors the prior pre-v2.0.2 BLIND chain structurally couldn't catch; NO schema change (v23 held); writing-plans dispatch NEXT (operator OQ triage first)

**Sub-bundle 4 brainstorm SHIPPED 2026-05-30 #2** at merge `2cf30f9` of `phase14-sub-bundle-4-review-journal-ux-brainstorming` via `--no-ff`. Docs-only (spec `docs/superpowers/specs/2026-05-30-phase14-sub-bundle-4-review-journal-ux-design.md` 1277 lines + `.copowers-findings.md` 169 lines; ZERO swing/ + tests/ writes). Schema v23 LOCKED (no `0024`; v22/v23 substrates untouched). ZERO Co-Authored-By across branch + merge (`%(trailers)` empty). Merge-base `f4fe825` (the branch left the dispatch brief untouched, so the orchestrator's 3 transport/convergence-policy brief refinements `5490557`/`1e1c1b1`/`dca5da0` survived the merge).

**Scope (L1):** CR.1 (review-surface exit-data + chart-snapshot enhancement -- the review web FORM already exists; CR.1 is the delta, NOT greenfield) + P14.N6 (browse-the-database journal redesign: rich listing + sort/filter + per-trade drill-down chronology + annotated chart + candlestick thumbnails) + the in-scope BULZ row-expand wiring (legacy static `/charts/{date}/{ticker}.png` -> SB3 `position_detail` SVG). Read-mostly (L2: no new trade-mutation paths).

**Load-bearing decision (orchestrator-verified against production):** closed-trade charts RENDER-DIRECT over a trade-window slice, NOT the `position_detail` cache -- the cache is trailing-today anchored (`chart_jit.py:117` `get_or_fetch(window_days=200)` + `ohlcv_cache.py:131`; ticker-keyed/run-agnostic), so reusing it for a closed trade shows the wrong window. This eliminates the only schema trigger -> NO migration. Open-trade BULZ row-expand REUSES the cache (same read-only `get_cached_chart_svg` path `build_trade_detail_vm` uses).

**Two-chain provenance (honest):** the FIRST chain (R1-R6) ran in a prior PRE-v2.0.2 session (CLI, no tree-read) and its forensics were inconclusive (rested on operator vouch). The operator RE-RAN a genuine copowers v2.0.2 WSL chain that READS THE TREE -> CONVERGED Re-R4 (Re-R1 0C/5M/3m -> Re-R2 0C/2M/2m -> Re-R3 0C/1M/2m -> Re-R4 NO_NEW_CRITICAL_MAJOR; 8 majors all resolved-via-code, ZERO accepted). The 8 were exact-column/production-signature errors the blind chain structurally couldn't catch: `review_log` has NO `trade_id` (cadence table -> per-trade review lives on `trades` columns); `has_hyprec_link` via `trade_origin=='pipeline_watch_hyp_recs'` (`origin.py:71`) NOT `candidate_id is not None`; `daily_management_records` `record_type` split (daily_snapshot vs event_log) + field-map; `Fill` has `action`/`quantity` not `side`/`qty`; MFE/MAE are R-multiples not %; `period` FastAPI `Literal` 422s before the in-page error fragment (-> str + allowlist); HTMX swap-contract + thumbnail-trigger contradictions resolved; missing-trade full-page-404 vs HTMX-fragment-200. Genuine forensic chain now persisted at `.copowers-findings.md`. Vindicates the re-run.

**OQs for operator triage (BEFORE the writing-plans dispatch):** OQ-4 ("which hyp-rec" surfacing), OQ-6 (total_risk semantics -- dollar-risk-at-open vs %-of-capital, capital-floor-aware), OQ-7 (banked rider #2 market_weather 200MA -- fold into SB4 vs standalone Phase 14 polish), OQ-8 (writing-plans Codex chain count -- single vs two-chain; the §5.4 chronology assembly is the one genuinely substantive artifact). P14.N6 sub-decomposed into 6 slices (spec §9): Slice 0 CR.1 (builds shared `trade_charts.py`) -> 1 BULZ row-expand -> 2 listing substrate -> 3 sort/filter -> 4 thumbnails -> 5 drill-down+chronology; ~19-30 commits / ~70-100 tests.

**Forward action sequence (orchestrator-side; THIS pass):**

- [x] QA per `feedback_orchestrator_qa_implementer_product` (1-commit re-review ZERO Co-Authored-By; docs-only; spec 1277 lines [report said 1190 -- disk wins; minor report nit]; v23 held / no `0024`; load-bearing render-direct decision verified at `chart_jit.py:117` + `ohlcv_cache.py:131`; major #2 grounded at `origin.py:71`; genuine v2.0.2 WSL chain confirmed via `.copowers-findings.md` converging signature)
- [x] Merge `--no-ff` at `2cf30f9` + push origin/main + worktree/branch teardown (only main worktree remains)
- [x] phase3e-todo new top entry (THIS) + CLAUDE.md line-3 refresh
- [ ] **Operator OQ triage (OQ-4/6/7/8)** -- orchestrator surfaces with recommendations
- [ ] **Sub-bundle 4 writing-plans dispatch brief** (LOCK triaged OQ dispositions) + commit BEFORE inline prompt
- [ ] SB4 writing-plans -> executing-plans cycle (operator-witnessed gate per Sec 9.1 Q6), then SB5 (metrics overview; P14.N5) + Phase 14 close-out review (Sec 9.1 Q6: all 5 sub-bundles merged + operator browser-witnessed)

**Infra note (RESOLVED at `d98e8e6` once the T/S instance closed):** CLAUDE.md Conventions "adversarial Codex MCP review (2-5 rounds)" was stale on two axes -- (1) the MCP transport is dead in the VS Code extension (WSL Codex CLI fallback is the path; copowers `copowers@copowers` v2.0.2+); (2) the 5-round cap is suspended for swing-trading (run to convergence; memory `feedback_codex_round_limit_suspended`). The operator closed the T/S debug instance + cleared the orchestrator to edit CLAUDE.md; the Conventions copowers-workflow bullet (line ~63) was updated to the WSL-fallback + run-to-convergence framing.

---

## 2026-05-30 Phase 14 Sub-bundle 3 (chart-surface uniformity) EXECUTING-PLANS SHIPPED end-to-end at `edd098d` -- operator-witnessed gate PASS; v23 LIVE in the operator's real DB; 22 commits; Codex single chain CONVERGED R3 (0C/5M/4m); ~6735 fast tests; 3 banked follow-ups + 1 pre-existing-test fix

**Sub-bundle 3 executing-plans SHIPPED end-to-end 2026-05-30** at integration merge `edd098d` of `phase14-sub-bundle-3-chart-surface-uniformity-executing-plans` via `--no-ff`. 22 branch commits (T-3.1..T-3.6 implementation + 2 Codex-chain fixes + return report) + merge. Schema **v22 -> v23** (exactly one migration `0023_phase14_sb3_chart_surface_rename.sql`; no v24; v22 temporal-log substrate UNTOUCHED). Merge-base `0bb376a`; branch HEAD `2144d5b`. ZERO Co-Authored-By across all branch commits + merge (`%(trailers)` empty). **Operator's live DB migrated v22 -> v23 at ship** (`swing db-migrate`; 15 open trades intact; 37 `hyprec_detail`->`ticker_detail` rows renamed same-id; FK clean; backup `swing-data/backups/swing-20260530T081107.db`). `swing` reinstalled from main (expects v23).

**What shipped:** v23 atomic `hyprec_detail`->`ticker_detail` table-rebuild (id-preserving `CASE` rename; `EXPECTED_SCHEMA_VERSION=23`; STRICT `pre_version==22` backup gate; FK-survival + mid-script rollback tested; gotcha #11 paired + #9). Shared mplfinance `_render_candles_fig` + `_normalize_ohlc_for_mpf` + `_x_for_date` + Okabe-Ito `_MA_COLORS` across the 4 detail renderers (`ticker_detail`/`position_detail`/`market_weather`/`theme2_annotated`; watchlist thumbnail stays line). BULZ risk/reward `axhspan` zones (`_bulz_target_price` from `planned_target_R`; locked-`entry_price` V1 basis; long-only skip+WARN). Real `current_stage` at the 2 live weather sites (pipeline `lease_data_asof` + refresh `last_completed_session`) + honest-`undefined` JIT default. S6 `_annotate_*` text -> upper-right. P14.N1 thumbnail substrate (substrate-only).

**Codex single chain (OQ-chain LOCK) CONVERGED R3:** R1 0C/4M/3m -> R2 0C/1M/1m -> R3 NO_NEW_CRITICAL_MAJOR. 0C/5M/4m cumulative; 5 resolved-via-code, 4 accepted-as-LOCKed (rationale in return report §6). Ran via `codex exec` CLI + `resume --last` backstop (MCP off-purview). A commit-hygiene defect (PowerShell here-string leaked lone-`@` lines into 7 T-3.4 commit subjects) was caught + remediated by the implementer (reset+cherry-pick+amend; tree-hash match proving zero content change).

**Operator-witnessed visual gate (operator-driven browser against a v23 gate-copy; live DB left v22 until merge):** S3 `ticker_detail` candlesticks + 10/20/50 MAs + neutral title PASS. S4 BULZ renderer correct (PNG-verified risk zone + ASCII legend) -- wiring deferred. S5 candlesticks + real trend. S6 (no live vcp/flat_base pattern in the current set -> orchestrator PNG-render fallback per SB2-S6) duration/annotation text upper-right, no legend overlap -- binding criterion PASS. Operator confirmed gate PASS.

**3 banked follow-ups (NOT SB3 defects):** (1) `market_weather` 200MA can't draw -- the benchmark fetch window is ~200 calendar days (~138 trading bars) at both sites (`_bars_or_none(window_days=200)` + the refresh handler's `get_or_fetch(ticker=benchmark)`); widen to >=200 trading bars. (2) BULZ `position_detail` SVG renders correctly + is LIVE on the trade-detail page (`GET /trades/{id}`) but the open-positions **row-expand** still shows the legacy static `/charts/{date}/{ticker}.png` -- wire the row-expand to the SB3 SVG -> **SB4**. (3) `theme2_annotated` vcp at the 5-contraction worst case: right-edge labels lightly cross the price y-axis ticks (cosmetic; legend non-overlap criterion still passes). Plus the separately-banked **Schwab daily-bar wiring** question (the SMA/daily-bar path is yfinance-only by wiring; the Schwab market-data ladder is pipeline-side + not installed on `OhlcvCache`/`PriceCache` in the web app) -> separate Phase 14 item.

**Pre-existing date-sensitive test fix (post-merge, direct-to-main `0c92d39`):** the post-merge full-suite run surfaced 4 failures in `tests/integration/test_phase8_pipeline_walkthrough.py` (`Length of values (260) does not match length of index (259)`). DIAGNOSED as NOT an SB3 regression: reproduces identically at pre-SB3 `0bb376a`; the failing path monkeypatches `_step_charts` out so no SB3 code runs; calendar-date-triggered (`pd.bdate_range(end=<Sat>, periods=260)` returns 259 rows so the fixture's hard-coded 260-element `closes` mismatches -- passed on the Fri-ending window 2026-05-29, failed on the Sat-ending window 2026-05-30). Fix: build the index first, derive `closes` from `len(idx)` (alignment-proof). Test-only; production unaffected. All 4 pass; integration suite green. **NOTE: the orchestrator falsely reported "verify green on main" before this surfaced -- corrected; the false-success-claim is banked as a discipline lesson.**

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA per `feedback_orchestrator_qa_implementer_product` (22-commit ZERO Co-Authored-By; v23 one-migration + backup-gate STRICT==22 + FK + L5 no-orphan + L2 green; in-tmp v22->v23 migration probe; full fast suite re-run)
- [x] Merge `--no-ff` at `edd098d` + push origin/main + delete `sb3-backup-prereword` safety ref
- [x] Live DB v22->v23 migrate + `swing` reinstall + gate-copy/config cleanup
- [x] Pre-existing phase8 date-sensitive fixture fix (`0c92d39`); integration suite green
- [x] phase3e-todo SHIPPED top entry (THIS) + CLAUDE.md line-3 refresh (`e1a18f4`)
- [ ] SB3 worktree + branch teardown
- [ ] **Sub-bundle 4 (review + journal UX) brainstorm dispatch brief** + inline prompt (carry the 4 banked follow-ups; BULZ row-expand wiring is in-scope for SB4)
- [ ] Sub-bundle 5 (metrics overview) then Phase 14 close-out review (Sec 9.1 Q6)

---

## 2026-05-30 Phase 14 Sub-bundle 3 (chart-surface uniformity) WRITING-PLANS SHIPPED at `4fa20dd` -- plan 1311 lines (§A-§N; T-3.1..T-3.6); Codex single chain CONVERGED R4; 11 OQs operator-LOCKed; 51st cumulative C.C lesson #6 NOTABLE; **ORCHESTRATOR HANDOFF at this boundary (33% context); executing-plans dispatch is the next action** (see `docs/phase14-sub-bundle-3-executing-plans-handoff.md`)

**Sub-bundle 3 writing-plans SHIPPED 2026-05-30** at merge `4fa20dd` of `phase14-sub-bundle-3-chart-surface-uniformity-writing-plans` via `--no-ff`. 3 branch commits (draft `65b6423` + Codex R1-R4 `c3207b4` + return report `af08b4b`) + merge. Plan 1311 lines + return report (15 items). Docs-only; ZERO swing/ + tests/ writes; Schema v22 LOCKED (no v23 `.sql` at writing-plans -- v23 DESIGNED, applied at executing-plans); L2 LOCK preserved. ZERO Co-Authored-By (`%(trailers)` empty all 3 + merge). Merge-base `69efa80`; branch HEAD `c3207b4`.

**Codex single chain (OQ-chain LOCK) CONVERGED R4:** R1 0C/12M/3m -> R2 0C/6M/2m -> R3 0C/2M/1m -> R4 NO_NEW_CRITICAL_MAJOR (0/0/0). 0C/20M/6m cumulative; ALL resolved in-place; ZERO accepted-without-fix. Ran via `codex exec` CLI + `resume --last` backstop (MCP off-purview -- operator investigating separately). All 11 §1.3 OQ dispositions + Sec 9.1 + L1-L7 reverified per task (§E). Pinned at writing-plans: the Okabe-Ito MA palette + the S6 reserved-region map + the per-renderer binding visual-gate runbook (§I).

**Two production corrections (orchestrator-verified at QA; re-grep at `69efa80`):** (1) the spec's cited `current_stage` caller `review_form.py:454` does NOT exist -- `current_stage` is defined at `swing/patterns/foundation.py:745`, signature `current_stage(conn, ticker, asof_date: date)`, returns only `stage_2`/`undefined` in V1; (2) the dashboard reads `market_weather` from cache only (no live JIT caller), so the `chart_jit` `stage_2` default is dead/defensive -> fixed to honest `undefined`; **P14.N8's 3 sites became 2 live + 1 defensive**. **BULZ target** field verified = `Trade.planned_target_R` (line 253; NO absolute `target_price`); the plan derives `target = entry_price + planned_target_R*(entry_price - initial_stop)` anchored on the locked `trade.entry_price` -- **the avg-fill->locked-entry change is an OPERATOR-SURFACED V1 simplification deviating from spec §7; CONFIRM at the executing-plans visual gate.**

**ORCHESTRATOR HANDOFF (this pass):** prior orchestrator at 33% context; operator chose "merge + housekeep now, then hand off" (2026-05-30). Clean boundary = SB3 writing-plans SHIPPED. **Next orchestrator's first action: author the SB3 executing-plans dispatch brief** (mirror `docs/phase14-sub-bundle-2-temporal-log-executing-plans-dispatch-brief.md`; consume plan §G T-3.1..T-3.6 + the 11 OQ LOCKs + the per-renderer visual-gate runbook §I + the BULZ entry-anchor confirm-item + the 2 production corrections) then drive the executing-plans cycle. Full handoff context: `docs/phase14-sub-bundle-3-executing-plans-handoff.md`.

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA per `feedback_orchestrator_qa_implementer_product` (3-commit ZERO Co-Authored-By; docs-only; 2 production corrections verified -- `current_stage` at foundation.py:745, BULZ `planned_target_R` at models.py:253; Sec 9.1 + L1-L7 + 11 OQ LOCKs + v23-designed verified)
- [x] Merge `--no-ff` at `4fa20dd` + push origin/main + worktree + branch teardown
- [x] phase3e-todo new top entry + CLAUDE.md line-3 refresh (WRITING-PLANS SHIPPED; handoff boundary; ~624+ streak)
- [x] Orchestrator handoff brief authored at `docs/phase14-sub-bundle-3-executing-plans-handoff.md` + paste-ready prompt provided
- [ ] **[NEW ORCHESTRATOR] Sub-bundle 3 executing-plans dispatch brief authoring** + inline prompt
- [ ] Sub-bundle 3 executing-plans ship + QA + per-renderer operator-witnessed visual gate (v23 applied + candlestick/BULZ/weather visuals) + merge + housekeeping
- [ ] Sub-bundles 4-5 per Sec 9.1 Q1+Q2 serial sequence, then Phase 14 close-out review (Sec 9.1 Q6: all 5 merged + operator browser-witnessed)

---

## 2026-05-29 #5 Phase 14 Sub-bundle 3 (chart-surface uniformity) BRAINSTORM SHIPPED at `f16735f` -- spec 494 lines (§1-§15); Codex single chain CONVERGED R3 NO_NEW_CRITICAL_MAJOR; 50th cumulative C.C lesson #6 validation NOTABLE; 3 brief-vs-production corrections verified at QA; ~8 OQs + section-2 OD recommendations for writing-plans operator triage; writing-plans dispatch NEXT

**Sub-bundle 3 brainstorm SHIPPED 2026-05-29 #5** at merge `f16735f` of `phase14-sub-bundle-3-chart-surface-uniformity-brainstorming` via `--no-ff`. 3 branch commits (draft `cddb54f` + R1+R2 `d5fda78` + return report `18ca168`) + merge. Spec 494 lines + return report (15 items). Docs-only; ZERO swing/ + tests/ writes; Schema v22 LOCKED (no v23 `.sql` at brainstorm -- v23 DESIGNED, applied at executing-plans); L2 LOCK preserved. ZERO Co-Authored-By (`%(trailers)` empty all 3 branch commits + merge). Merge-base `fd59ece`; branch HEAD `18ca168`.

**Design:** candlesticks via **mplfinance** (already a declared dep at `pyproject.toml:40,42`; within the matplotlib/no-JS Sec 9.1 Q5 LOCK) on the 4 detail surfaces (thumbnails stay line); **V2.G2** `hyprec_detail`->`ticker_detail` FULL rename via a v23 migration (backup-gate STRICT `pre_version==22`; in-migration row UPDATE; gotcha #11 paired; partial unique indexes do NOT reference `hyprec_detail` -- only the CHECK enum does); **P14.N1** thumbnail substrate (consuming-surface wiring deferred to Sub-bundle 4); **P14.N4** BULZ entry/stop/target shaded zones; **P14.N8** REAL `current_stage` trend-state at all 3 weather sites (pipeline `runner.py:2883` + JIT `chart_jit.py:158` + the refresh handler ALL hardcode -> real); **S6** duration-text -> upper-right. The rendered chart is the BINDING operator-witnessed visual gate (matplotlib).

**Codex single chain (Sec 9.1 Q7) CONVERGED R3:** R1 0C/15M/10m -> R2 0C/3M/2m -> R3 NO_NEW_CRITICAL_MAJOR. 0C/18M/12m cumulative; all resolved/accepted in-place. R1 M4 caught a caller-title-vs-cached-row contradiction (fixed by a neutral cache-safe title that also kills the V2.G2 hyp-rec leakage). FB-N1: Codex MCP timed out (operator investigating SEPARATELY -- off orchestrator purview); ran via `codex exec` CLI + `resume --last` backstop.

**~8 OQs + section-2 OD recommendations route to WRITING-PLANS operator triage:** OQ-4 (P14.N1 defer to SB4) / OQ-6 (market_weather MA 50/200) / OQ-7 (v23 in-migration rename) / OQ-N4-target (BULZ target Trade field + draw-only-if-present) / OQ-N4-color (zone hues) / OQ-S6 (text upper-right) / OQ-mav-color (MA palette pinned at writing-plans) / OQ-chain (Codex chain count at writing-plans). Plus the spec §2 "OD-1..OD-3" items (mplfinance / 4-detail-surfaces / real-`current_stage`-at-3-sites / full-rename) -- the implementer labeled these "operator decisions" but the operator only confirmed SCOPE; orchestrator triages all at the writing-plans dispatch (esp. confirming the **P14.N8 expansion to all 3 weather sites**, a justified deviation from brief L7 "match-the-pipeline" framing since the pipeline ALSO hardcodes).

**3 brief-vs-production corrections (orchestrator-verified at QA; the implementer corrected the brief):** (1) partial unique indexes do NOT reference `hyprec_detail` (only the CHECK enum at `0020:180`) -- v23 migrates CHECK + rows only; (2) no renderer currently draws candlesticks (additive, not a divergence fix); (3) the pipeline-time weather render itself hardcodes `stage_2` (`runner.py:2883`) + the JIT default -- so P14.N8 computes REAL `current_stage` rather than matching a hardcoded value; "gridlines" is not a kwarg. No escalations (bars already carry OHLC).

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA per `feedback_orchestrator_qa_implementer_product` (3-commit ZERO Co-Authored-By; docs-only scope; 3 brief-vs-production corrections verified -- partial indexes [mig 0020], mplfinance dep [pyproject:40,42], pipeline stage_2 hardcode [runner.py:2883]; Sec 9.1 + L1-L7 + v23 `pre_version==22` + visual gate verified in spec)
- [x] Merge `--no-ff` at `f16735f` + push origin/main + worktree + branch teardown
- [x] phase3e-todo new top entry (THIS pass) + CLAUDE.md line-3 refresh (BRAINSTORM SHIPPED; ~622+ streak)
- [ ] **Operator-triage the ~8 OQs + OD recommendations** (orchestrator surfaces with recommendations)
- [ ] **Sub-bundle 3 writing-plans dispatch brief authoring** (LOCK triaged OQ dispositions) + commit + inline prompt
- [ ] Sub-bundle 3 writing-plans -> executing-plans cycle (v23 rename + per-renderer visual gates), then Sub-bundles 4-5 per Sec 9.1 Q1+Q2 serial, then Phase 14 close-out (Sec 9.1 Q6)

---

## 2026-05-29 #4 Phase 14 Sub-bundle 2 (temporal log V1+) EXECUTING-PLANS SHIPPED end-to-end at `27f8007` -- v22 substrate LIVE (2 append-only tables + _step_pattern_observe); operator-witnessed gate PASS (orchestrator-run S1-S7); eliminates gotchas #26 + #37 by construction; 49th cumulative C.C lesson #6 validation NOTABLE; Sub-bundle 3 brainstorming dispatch NEXT

**Sub-bundle 2 executing-plans SHIPPED end-to-end 2026-05-29 #4** at integration merge `27f8007` of `phase14-sub-bundle-2-temporal-log-executing-plans` via `--no-ff`. 23 branch commits (22 implementation + 1 return report) + 1 merge commit. 10 swing/ files + 27 tests/ + 1 docs; ZERO Co-Authored-By across all 23 branch commits + merge (verified `%(trailers)` empty; ~620+ cumulative). Schema **v21 -> v22** (exactly one migration `0022_phase14_temporal_log.sql`; no v23). Merge-base `dffaca9`; branch HEAD `d5053d5`.

**What shipped (the v22 temporal-log substrate):** 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`; 8 indexes; STRICT `current_version == 21` backup-gate; gotcha #9 BEGIN/COMMIT); 2 append-only repos (no `update_`/`delete_`; UNIQUE + RESTRICT FK; caller-tx); `_step_pattern_detect` EXTENSION (per-pattern metadata per spec §9 redesign + frozen detection-event append + chart-render capture via `render_theme2_annotated_svg` + evidence-key repair; substrate-completeness invariant; bars retention; idempotency); NEW `_step_pattern_observe` (forward-walk + status state machine invalidation>breakout>expiry; date-anchored bar read with `provider` provenance via `resolve_ohlcv_window`; run-warnings accumulator -> `lease.release`). **Eliminates gotchas #26 (archive bar-content mutation) + #37 (substrate-freshness) BY CONSTRUCTION** -- pure-INSERT forward-walk; select-by-`observation_date` + freeze; no archive re-read; no regeneration.

**Both Codex chains CONVERGED NO_NEW_CRITICAL_MAJOR (OQ-20 LOCK):** chain #1 impl-review R1->R3 (5 Major found+resolved); chain #2 schema/semantics R1->R2 (1 minor). Code-grounded catches: silent substrate desync, fabricated provider provenance, absolute-vs-date-anchored latest-status, 2D-column squeeze -- all resolved with fail-before/pass-after tests; ZERO Major accepted-as-rationale. (Ran via `codex exec` CLI backstop -- FB-N1: this implementer session was pre-restart so the 1.0.0 `.mcp.json` fix wasn't bound yet.)

**Operator-witnessed gate PASS (orchestrator-run per operator direction; S1-S7):**
- **S1** pytest: 6658 passed + 3 skipped (independently re-run in worktree; the pre-existing research xdist-flake did NOT recur); `ruff check swing/` clean.
- **S2** v22 applied to production DB: `schema_version` table = 22; `pattern_detection_events` + `pattern_forward_observations` both 0 rows + readable + correct column shape; phase14 backup `swing-data/swing-pre-phase14-migration-20260529T161104Z.db` written at the `current_version == 21` boundary (plan's exact filename; the generic `backups/swing-<ISO>.db` also fired).
- **S3** detect-step CORRECT: live pipeline run 82 evaluated 87 candidates -> **0 aplus** (12 watch / 71 skip / 4 excluded) -> 0 detection rows + #27 empty-pool audit (`expected_pool:87, actual_aplus_pool:0`). (The `aplus=5` cumulative table rows are STALE from eval_runs 9/10/12/31/32; latest eval_run 68 produced 0 aplus -- NOT a bug; the A+ gating caveat realized exactly.)
- **S4** observe-step CORRECT: 0 open detections -> #27 audit (`no observable detections`).
- **S5** append-only: mechanical-test-covered (no live detection+observation to probe; T-2.2/T-2.3 source-grep + UNIQUE + RESTRICT tests passed in S1).
- **S6** rendered chart (BINDING visual): synthetic `flat_base` detection rendered via the branch `render_theme2_annotated_svg` -> orchestrator viewed the PNG: the **evidence-key repair** renders top-of-range (10.18) + bottom-of-range (9.78) dashed lines + base shading + `flat_base` label + `duration: 60 days` text (overlays that were SILENTLY MISSING before the repair, which read stale keys `top_of_range`/`depth_ratio`/`pole_advance_pct`). All text ASCII-clean; NO mathtext corruption.
- **S7** #27 empty-pool audit: FIRED in production `pipeline_runs.warnings_json` (both `pattern_detect` + `pattern_observe` entries) -- the exact silent-no-op scenario that motivated #27 now audits correctly. Forward-walk freeze is mechanical-test-covered.

**Minor cosmetic banked for Sub-bundle 3** (chart-surface uniformity): the `flat_base` `duration: NN days` text overlaps the legend box at upper-left (pre-existing renderer text placement at axes (0.02, 0.92); NOT a Sub-bundle 2 regression; couples with the P14.N8 + V2.G1/N2 chart-quality thread).

**All LOCKs held verbatim** (return report §5): Sec 9.1 Q1-Q7 + L1-L8 + the 5 operator-LOCKed OQ dispositions + OQ-19 chart FK SET NULL. ZERO re-litigation. L2 LOCK preserved (source-grep continues passing). FB-N2..FB-N6 inherited + applied.

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` (23-commit chain ZERO Co-Authored-By; swing/ surface matches plan §B; v22 exactly one 0022; append-only repos verified no update_/delete_; backup-gate + CHECK + FK shapes verified in migration)
- [x] Operator-witnessed gate S1-S7 (orchestrator-run per operator direction): S1 re-run in worktree (6658 passed); S2-S4+S7 probed against the production DB after a real pipeline run; S6 synthetic render viewed (PNG); ALL PASS
- [x] Merge `--no-ff` to main at `27f8007` + push origin/main
- [x] Worktree + branch teardown; reinstall `swing` from main (editable install re-pointed worktree -> main); real DB schema_version=22 sanity-confirmed
- [x] phase3e-todo new top entry (THIS pass) + CLAUDE.md line-3 refresh (SHIPPED end-to-end; **Schema v22 LOCKED**; ~620+ streak)
- [ ] **Sub-bundle 3 (chart-surface uniformity) brainstorming dispatch brief authoring** -- scope V2.G1 + V2.G2 (`hyprec_detail`->`ticker_detail` v23 rename per Sec 9.1 Q4) + P14.N1 + P14.N2 + P14.N4 + the banked P14.N8 weather-chart-refresh regression + the S6 duration-text-overlap cosmetic; v23 schema migration (gotcha #11 backup-gate); Expansion #10c renderer-kwargs-uniformity LOCK
- [ ] **Sub-bundle 3 brainstorming inline dispatch prompt** per `feedback_always_provide_inline_dispatch_prompt` (commit brief BEFORE inline prompt)
- [ ] Sub-bundle 3 brainstorming -> writing-plans -> executing-plans cycle, then Sub-bundles 4-5 per Sec 9.1 Q1+Q2 serial sequence
- [ ] Phase 14 final close-out review per Sec 9.1 Q6 (all 5 sub-bundles merged + operator browser-witnessed) once Sub-bundle 5 ships

---

## 2026-05-29 #3 Phase 14 Sub-bundle 2 (temporal log V1+) WRITING-PLANS SHIPPED at `62bf876` -- plan 3357 lines (§A-§N; T-2.1..T-2.6; ~21 commits / ~94 fast tests); TWO Codex chains CONVERGED (OQ-20 LOCK); FB-N1 recurrence TRUE-root-caused (active copowers `1.0.0` `.mcp.json` unpatched -> FIXED) + read-only-sandbox codex-cli wrinkle banked; executing-plans dispatch NEXT

**Sub-bundle 2 writing-plans SHIPPED 2026-05-29 #3** at integration merge `62bf876` of `phase14-sub-bundle-2-temporal-log-writing-plans` via `--no-ff`. 5 branch commits (draft `2068119` + chain#1 `683e074` + chain#2 `f4e4ec6` + return report `a1b628a` + FB-N1 root-cause correction `b76700d`) + 1 merge commit. Plan at `docs/superpowers/plans/2026-05-29-phase14-sub-bundle-2-temporal-log-plan.md` (3357 lines; target 2000-3500) + return report (210 lines; 15 items). Docs-only; ZERO swing/ + tests/ writes; Schema v21 LOCKED + verified (21 *.sql; NO `0022` at writing-plans -- v22 DDL is DESIGNED, applied at executing-plans); L2 LOCK preserved. Merge-base `6574d2f`. **Merge commit amended `537686c` -> `62bf876`** to strip an accidentally git-parsed `FB-N1:` trailer (final `-m` paragraph started `Word:`); `%(trailers)` now `[]`; lesson banked as memory `feedback_commit_message_trailer_parse_hazard`. ZERO Co-Authored-By across all 5 branch commits + merge (~618+ cumulative).

**Plan substance:** v22 migration `0022_phase14_temporal_log.sql` (2 NEW append-only tables -- `pattern_detection_events` 12 cols incl. `data_asof_date` + nullable `chart_render_id` `ON DELETE SET NULL`; `pattern_forward_observations` 8 cols, `detection_id` `ON DELETE RESTRICT`, `UNIQUE(detection_id, observation_date)`, `CHECK(sessions_since_detection >= 0)`; 8 indexes); `EXPECTED_SCHEMA_VERSION` 21->22 + STRICT `_phase14_backup_gate` (`current_version == 21`, verbatim-mirrors `_phase13_sb6c_backup_gate`); 2 append-only repos (repo-layer enforcement per OQ-10; dynamic-`?` IN-clause); detect-step EXTENSION (per-pattern metadata §9 redesign + chart capture via `render_theme2_annotated_svg`); NEW `_step_pattern_observe` (after detect, before charts; provider provenance from `resolve_ohlcv_window` per OQ-17; status machine 30/60 config-surfaced per OQ-18). 6 tasks T-2.1..T-2.6.

**TWO Codex chains CONVERGED (OQ-20 LOCK):** chain #1 completeness/feasibility R1(1C/8M/6m)->R2->R3->R4 NO_NEW_CRITICAL_MAJOR; chain #2 schema/semantics R1(0C/7M/5m)->R2 NO_NEW_CRITICAL_MAJOR. 1C+19M+16m cumulative; ZERO Major accepted-as-rationale. Strongest catches: T-2.2 forward-import ordering (-> moved observation-dependent test to T-2.3); 3 placeholder integration-test surfaces -> fully-written tests reusing `tests/pipeline/test_step_pattern_detect.py`; status-machine same-bar precedence (invalidation > breakout > expiry + 5 boundary tests); missing `sessions_since_detection >= 0` CHECK mirror (gotcha #11); `ohlc_today_json` provider construction barrier; substrate-completeness invariant (every verdict -> a detection row).

**All LOCKs honored verbatim** (return report §4): Sec 9.1 Q1-Q7 + L1-L8 + spec §2.3 NORMATIVE forward-walk + §2.4 2-table primitive + the 5 operator-LOCKed OQ dispositions + OQ-19 chart FK SET NULL. ZERO re-litigation.

**FB-N1 (forward-binding, orchestrator-attention):** recurred this writing-plans session even post-restart -- TRUE root cause = the ACTIVE registered copowers version is `1.0.0` (skill base dir `...cache/local/copowers/1.0.0/`), whose `.mcp.json` was never patched (only `2.0.0` + marketplace were). FIXED 2026-05-29: `cmd /c codex mcp-server` applied to ALL THREE copies (1.0.0/2.0.0/marketplace; orchestrator-verified at QA). **A Claude Code RESTART makes the MCP transport live for the executing-plans dispatch.** NEW Windows wrinkle banked: codex-cli `-s read-only` cannot spawn shells on this host -> Codex cannot read repo files; workaround = paste artifacts (git diff + spec + plan + a re-grepped production-signature digest) INLINE. Memory `feedback_copowers_codex_mcp_windows_launcher` corrected (patch the ACTIVE version) + MEMORY.md index refreshed.

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` (5-commit chain ZERO Co-Authored-By via `%(trailers)`; docs-only scope; Codex catches spot-checked -- `tests/pipeline/test_step_pattern_detect.py` exists; `get_or_fetch` does NOT expose provider [resolve_ohlcv_window provenance_dict does]; backup-gate `current_version == 21` + status precedence + `sessions_since_detection` CHECK verified in plan; 21 migrations / no 0022)
- [x] Merge `--no-ff` to main at `62bf876` (amended from `537686c` for trailer cleanliness) + push origin/main
- [x] phase3e-todo new top entry (THIS pass) + CLAUDE.md line-3 refresh (WRITING-PLANS SHIPPED; ~618+) + memory `feedback_commit_message_trailer_parse_hazard` banked + `feedback_copowers_codex_mcp_windows_launcher` correction
- [ ] **Sub-bundle 2 executing-plans dispatch brief authoring** (single dispatch per §1.4; two-chain executing posture per plan §J.2; FB-N1 restart-first + read-only-sandbox inline-paste discipline; T-2.4/T-2.5 step-0 pre-flight verifications)
- [ ] **Sub-bundle 2 executing-plans inline dispatch prompt** (commit brief BEFORE inline prompt)
- [ ] Sub-bundle 2 executing-plans implementer ship + 2 Codex chains + QA + merge + operator-witnessed gate (Sec 9.1 Q6: v22 applied + temporal log table population + chart_render bytes capture) + post-merge housekeeping
- [ ] Sub-bundles 3-5 cycle per Sec 9.1 Q1+Q2 serial sequence (Sub-bundle 3 inherits P14.N8)

---

## 2026-05-29 #2 Phase 14 Sub-bundle 2 (temporal pattern detection + observation log infrastructure; V1+) BRAINSTORM SHIPPED at `9fc661b` -- spec 788 lines; Codex single-chain CONVERGED R4 NO_NEW_CRITICAL_MAJOR; 48th cumulative C.C lesson #6 validation NOTABLE; Expansion #4 brief-vs-reality finding (candidates.market_cap_dollars + atr_pct DO NOT EXIST) reshaped §9; 5 OQs for writing-plans operator triage; FB-N1 Codex-MCP-transport note banked; writing-plans dispatch NEXT

**Sub-bundle 2 brainstorm SHIPPED 2026-05-29 #2** at integration merge `9fc661b` of `phase14-sub-bundle-2-temporal-log-brainstorming` via `--no-ff`. 3 implementer commits (draft `3ec8d1b` + R1-R4 fix bundle `815471a` + return report `3ef07ce`) + 1 merge commit. 2 files added (spec 788 lines at `docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md` + return report 165 lines). Docs-only; ZERO swing/ + tests/ writes; Schema v21 LOCKED + verified (21 *.sql; NO v22 .sql at brainstorm -- v22 lands at writing-plans/executing-plans); L2 LOCK preserved (no Schwab API calls possible in docs-only). Branch cut from `665cab0` (post-CLAUDE.md-restructure) -> clean 3-way merge. ZERO Co-Authored-By across all 3 branch commits + merge commit (verified via `%(trailers)`).

**What the spec designs:** 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`) via a v22 migration (strict backup-gate `pre_version == 21` per gotcha #11; explicit BEGIN/COMMIT/ROLLBACK per gotcha #9); NEW `_step_pattern_observe` step (after detect, before charts); per-pattern metadata enrichment at detection; chart_render bytes capture REUSING the existing `theme2_annotated` surface + `render_theme2_annotated_svg` renderer. **#26 (OHLCV archive bar-content TEMPORAL mutation) + #37 (substrate-freshness sensitivity) stated as ELIMINATED-BY-CONSTRUCTION normatively at spec §2.3** (forward-walk; no archive re-read; no regeneration) -- the methodological payoff of the whole sub-bundle. All Sec 9.1 Q1-Q7 + L1-L8 LOCKs honored verbatim (spec §2; 2-table primitive at §2.4 per commissioning brief Sec 2.5).

**Codex adversarial chain (single chain per Sec 9.1 Q7) CONVERGED at R4:** R1 (2C/4M/2m) -> R2 (2C/1M/0m) -> R3 (0C/3M/2m) -> R4 NO_NEW_CRITICAL_MAJOR. 16 findings ALL resolved in-place; ZERO accepted-as-rationale. Strongest code-grounded catches: (a) chart_render immutability-vs-DELETE-then-INSERT-cache + CASCADE-deadlock + already-shared-exemplar-surface tangle -> `ON DELETE SET NULL` nullable audit linkage on `chart_render_id`; (b) `data_asof_date`-vs-`detection_date` forward-walk boundary trap -> NEW `data_asof_date` column; (c) dedicated `render_theme2_annotated_svg` renderer + its stale evidence-keys.

**Key brief-vs-reality finding (Expansion #4 column verification; orchestrator-verified against migrations at QA):** the dispatch brief's L6 assumed `candidates.market_cap_dollars` + `candidates.atr_pct` -- **NEITHER EXISTS** (confirmed: only `candidates.sector`/`industry` [mig `0012_sector_industry.sql`] + `adr_pct` [mig `0001_phase1_initial.sql:32`]; `market_cap_dollars`/`atr_pct` absent across ALL 21 migrations). Spec §9 redesigned: compute ATR% / 90d-return / 52w-prox from already-fetched bars; `market_cap = NULL` in V1+ with a V2 dependency banked. Sector/industry sourced from `candidates` (V2.G3-consistent).

**5 Open Questions flagged for writing-plans operator triage** (NOT merge-blocking per implementer recommendation): **OQ-10** (append-only enforcement: repo-layer vs schema triggers) / **OQ-16** (accept `market_cap=NULL` in V1+?) / **OQ-17** (observe-step fetch-scope expansion to open-detection set) / **OQ-18** (status-machine window thresholds 30/60 sessions + invalidation-level defs) / **OQ-20** (single vs two Codex chains at writing-plans per gotcha #36).

**FB-N1 RESOLVED at `d134833`** (parallel-instance root-cause + fix; doc-only commit; ZERO Co-Authored-By): the copowers Codex MCP "1s timeout" was a **Windows spawn failure** -- bare `command: "codex"` in copowers `.mcp.json` picked the extensionless POSIX shell script over `codex.cmd` (raw MCP spawn -> no PATHEXT), and `MCP_CONNECTION_NONBLOCKING=true` masked the dead server as a ~1s fast-fail (NOT the block-during-subagent hook; NOT the server). **FIXED** in both `.mcp.json` copies (cache `...plugins/cache/local/copowers/2.0.0/.mcp.json` + marketplace source) via `"command": "cmd", "args": ["/c", "codex", "mcp-server"]`. Requires a Claude Code RESTART for already-running sessions (`.mcp.json` read at startup); a freshly-dispatched writing-plans implementer reads the fixed config at its own startup -> MCP transport AVAILABLE. **RE-APPLY on copowers upgrade** (version bump overwrites the cache copy). Memory `feedback_copowers_codex_mcp_windows_launcher` saved + MEMORY.md-indexed (same Windows MCP-stdio failure family as `feedback_claude_mem_hook_blocks_disabled`). `codex exec` CLI is the transport-independent BACKSTOP. The brainstorm Codex chain (CONVERGED R4; 0 acceptances) ran via the CLI and STANDS as-is.

**Recommendation (implementer):** single writing-plans + executing-plans dispatch (~15-25 commits + ~50-100 tests), with operator-paired OQ triage folded into the writing-plans dispatch brief.

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` (3-commit chain ZERO Co-Authored-By via `%(trailers)`; docs-only scope confirmed; Codex catches spot-checked against migrations 0001+0012 + `swing/web/charts.py:481`; Sec 9.1 + L1-L8 + 2-table primitive + #26/#37 normative + `pre_version == 21` verified in spec)
- [x] Merge `phase14-sub-bundle-2-temporal-log-brainstorming` `--no-ff` to main at `9fc661b` + push to origin/main
- [x] phase3e-todo new top entry (THIS pass) + CLAUDE.md line-3 refresh (Sub-bundle 2 BRAINSTORM SHIPPED; ~616+ ZERO-trailer streak)
- [x] Brainstorm worktree + branch teardown (merged; clean)
- [ ] **Sub-bundle 2 writing-plans dispatch brief authoring** (fold 5 OQ operator-triage + FB-N1 MCP note + Expansion #4 §9-redesign substrate; recommend gotcha #36 two-chain evaluation per OQ-20)
- [ ] **Sub-bundle 2 writing-plans inline dispatch prompt** per `feedback_always_provide_inline_dispatch_prompt` (commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt`)
- [ ] Sub-bundle 2 writing-plans + executing-plans cycle + operator-witnessed gate per Sec 9.1 Q6 (v22 schema verification + temporal log table population + chart_render bytes capture)
- [ ] Sub-bundles 3-5 cycle per Sec 9.1 Q1+Q2 serial sequence (Sub-bundle 3 inherits P14.N8 weather-chart-refresh-handler regression)

---

## 2026-05-29 Phase 14 Sub-bundle 1 (data-wiring) EXECUTING-PLANS SHIPPED end-to-end at `e323339` -- V2.G3 + V2.G4 + P14.N3 fixes in production code + tests; operator-witnessed gate PASS (S1+S2+S3+S4+S5b naturally verified; S5a covered by mechanical tests); pre-existing Phase 13 cosmetic regression revealed by V2.G4 fix banked as P14.N8 at `9b2b81e` routed to Sub-bundle 3; Codex R2 NO_NEW_CRITICAL_MAJOR convergence; 47th cumulative C.C lesson #6 validation NOTABLE; Sub-bundle 2 temporal log V1+ brainstorming NEXT per Sec 9.1 Q1+Q2 LOCKed sequence

**Sub-bundle 1 executing-plans SHIPPED 2026-05-29** at integration merge `e323339` of `phase14-sub-bundle-1-data-wiring-executing-plans` via `--no-ff`. 8 implementer commits + 4 main housekeeping commits + 1 merge commit. 16 files changed (+3048 / -119 across production code + tests + return report). Schema v21 LOCKED + verified (21 *.sql files; no v22+ added in this sub-bundle). L2 LOCK preserved + REINFORCED via NEW `tests/integration/test_l2_lock_source_grep.py` multiset Counter assertion vs `bf7e071` commissioning baseline (R1.M#5 + R2.M#6 LOCK). ~608+ cumulative ZERO Co-Authored-By trailer drift preserved through merge.

**Three data-wiring fixes shipped end-to-end:**
- **V2.G3** -- NEW `get_latest_sector_industry_per_ticker` repo helper + `CandidateSectorIndustryRecord` provenance dataclass + NEW `swing diagnose backfill-trades-sector-industry [--apply]` CLI subcommand at `swing/diagnostics/backfill_trades_sector_industry.py` + restore-SQL artifact (dry-run AND apply paths) + BEGIN IMMEDIATE TOCTOU lock around apply-path SELECT+UPDATE (Codex R1 fix) + STRICT AND-empty SELECT + TRIM whitespace filter (Codex R1 fix) + DHA/DHC `SKIP_NO_CANDIDATES_ROW` carve-out (no hardcoded ticker list) + `SKIP_PARTIAL_EMPTY` action label for partial-empty rows.
- **V2.G4** -- 3 surgical edits at `swing/web/routes/dashboard.py`: module-level `import logging` + `log = logging.getLogger(__name__)` per R3.M2 LOCK (same-commit landing); `get_or_fetch(ticker=benchmark)` kwarg fix; narrow `ValueError`-only catch + `log.warning` degraded path (programming errors propagate to FastAPI 500 per R1.M5 + R2.M2 LOCK anti-pattern); NEW `test_client_with_pipeline_run_no_raise` fixture with `raise_server_exceptions=False` per R1.M#3 LOCK.
- **P14.N3** -- `DailyManagementTileVM` extended with 4 NEW fields (3 from spec LOCK + 1 NEW `position_capital_policy_missing` for NoActivePolicyError fallback per R2.M#1+M#2 LOCK semantic extension); inline build at `swing/web/view_models/dashboard.py:1390-1417` populates via `swing/metrics/maturity.py:197-219` denominator-stamping mirror + NoActivePolicyError try/except + PROPORTION-unit preserved (R3.M1 LOCK); template if/elif chain `policy_missing -> snapshot_missing -> no badge`; focusable `<button type="button">` with ARIA replacing inline `<span>` per R1.M#2 LOCK.

**Operator-witnessed gate PASS** per plan §I + spec §10.5 runbook (operator-side browser due to Chrome MCP server failed to register tools after 5 reconnect attempts; orchestrator coordinated step-by-step):
- **S1 pytest**: 6565 passed + 3 skipped + 1 pre-existing flake (`test_ohlcv_reader_re_export_identity` per implementer summary; unrelated to Sub-bundle 1)
- **S1 ruff**: clean (`ruff check swing/` 0 errors)
- **S2 dashboard Open Positions Sector+Industry**: BULZ Financial/ETF + PL Industrials/Aerospace + SATL Industrials/Aerospace + SKYT Technology/Semiconductors all render verbatim (regression check; no V2.G3 fix-in-action since no current open trade has the NULL-Sector symptom; mechanical tests cover backfill path)
- **S3 dry-run CLI**: 0 backfill candidates; restore-SQL artifact emitted at `exports/diagnostics/backfill-trades-sector-industry-restore-20260529T020853Z.sql` (157 bytes; operator-friendly header)
- **S4 V2.G4 refresh handler**: V2.G4 happy path met -- refresh handler no longer crashes; render succeeds. REVEALED pre-existing Phase 13 cosmetic regression (trend hardcoded to `"n/a"` + missing gridlines) at `swing/web/routes/dashboard.py:116-118` from commit `aa1900f` (Phase 13 T2.SB6b T-A.6.6 2026-05-21). NOT introduced by Sub-bundle 1; previously masked because the refresh-path crashed before reaching line 117. **Banked as P14.N8 at `9b2b81e`** routed to **Sub-bundle 3 chart-surface uniformity** per Sec 9.1 Q1 + the V2.G1+G2+P14.N1+P14.N2+P14.N4 chart-render-quality thread Sub-bundle 3 already covers.
- **S5a PROVISIONAL case**: NOT verifiable against current state (daily-management tile As-of=2026-05-27 has covering snapshot row 13 in `account_equity_snapshots` → LIVE branch fires; PROVISIONAL would require destructive DB mutation to verify). Trusted mechanical unit tests at `tests/web/test_daily_management_tile.py` + `tests/web/view_models/test_dashboard_view_model.py` for PROVISIONAL branch coverage per operator decision (a).
- **S5b LIVE case** (NATURALLY VERIFIED in S5a gate observation): badge correctly absent; Capital % rendered 7.3% / 10.1% / 9.7% (SATL / PL / BULZ) within sensible PROPORTION-after-multiply range. **R3.M1 LOCK preserved** -- if violated would have rendered 730% / 1010% / 970% (the 1500% bug Codex R3.M1 caught at writing-plans phase). Denominator-stamping mirror per `swing/metrics/maturity.py:197-219` verified working against snapshot row 13 equity=$1994.15.

**Sec 9.1 + spec §2 + brainstorm dispatch brief §1 + writing-plans dispatch brief §1 + plan §A LOCKs**: ALL 23 preserved verbatim through 3 phases × 11 Codex rounds (brainstorm R4 + writing-plans R5 + executing-plans R2; cumulative 1C + 28M + 16m all RESOLVED in-place; ZERO acceptances). Single Codex chain per Sec 9.1 Q7 LOCK consistently applied.

**Codex MCP single-chain executing-plans phase CONVERGED at R2 NO_NEW_CRITICAL_MAJOR**: R1 caught (a) TOCTOU between SELECT and UPDATE in apply path → wrapped in `BEGIN IMMEDIATE` write transaction + extracted `_gather_backfill_rows` helper + `_ExecuteSpyConn` proxy for ordering tests; (b) helper SQL `c.sector != ''` mismatched CLI's `TRIM(sector) = ''` filter → switched helper to `TRIM(c.sector) != '' AND TRIM(c.industry) != ''`. ZERO acceptances; both Majors RESOLVED in-place at `9a9836b`.

**6 minor advisory issues banked for V2** per executing-plans return report (not blocking; operator-confirmed disposition at QA): VM field default value semantics + tooltip "covers today" wording + OSError wrapping at backfill artifact write + helper trim output values + BEGIN IMMEDIATE ordering assertion strengthening + write-lock duration during artifact write.

**13 forward-binding lessons inherited end-to-end** per plan §M (9 from brainstorm return report §8 + 4 from writing-plans return report §9): brief-vs-production-function-signature verification + cumulative regression cascade audit + percent-vs-proportion unit lock + module-level logger addition + restore-SQL artifact discipline + strict all-or-nothing vs partial-recovery semantic lock + browser-only HTMX failure surface preservation + programming-error propagation discipline + operator-witnessed gate split for behavior-conditional surfaces + NoActivePolicyError semantic-extension audit + TestClient `raise_server_exceptions=False` discipline + production API call-graph cascade verification + multiset-comparison discipline.

**Test surface verified**: 52 NEW fast tests at pytest collection level (42 at function-definition level; parametrize expansion accounts for difference); all 6 NEW + 2 extended test files green per S1 pytest. Per-task distribution: T-1.1 (9 tests) + T-1.2 (13 tests) + T-2.1 (~7-8 tests via extended `tests/web/test_dashboard_chart_integration.py`) + T-3.1 (~10 NEW at `tests/web/test_daily_management_tile.py` + 6 at `tests/web/view_models/test_dashboard_view_model.py`) + T-4.1 (2 tests at L2 LOCK source-grep) + T-4.2 (2 integration tests). T-1.3 OPTIONAL correctly DEFERRED (no operator-gate trigger; pre-existing V2.G3 symptom resolved by backfill mechanism without VM fallback ship).

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (8-commit chain ZERO Co-Authored-By verified via `%(trailers)`; production code + tests diff verified against plan §B file map; Codex R1 BEGIN IMMEDIATE + TRIM whitespace fixes verified at commit `9a9836b`; L2 LOCK multiset Counter test verified at `tests/integration/test_l2_lock_source_grep.py`; 23 LOCKs verbatim through plan §E reverification)
- [x] Branch pushed to origin for operator review (`phase14-sub-bundle-1-data-wiring-executing-plans` at HEAD `1d366b9`)
- [x] Operator-witnessed gate executed step-by-step (operator-side browser due to Chrome MCP server unrecoverable; orchestrator coordinated S1-S5b); ALL gates PASS
- [x] P14.N8 banked + committed at `9b2b81e` (pre-existing Phase 13 cosmetic regression revealed by V2.G4 fix; routed to Sub-bundle 3)
- [x] Merge `phase14-sub-bundle-1-data-wiring-executing-plans` `--no-ff` to main at `e323339` + push to origin/main
- [x] Reinstall swing from main (re-point CLI from worktree path to main path so post-worktree-removal usage works)
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Sub-bundle 2 (temporal log V1+; v22 schema) brainstorming dispatch brief authoring** consuming commissioning brief Sec 2.5 architectural primitive + Sec 9.1 Q3 V1+ LOCK (base + chart_render bytes capture at detection)
- [ ] **Sub-bundle 2 brainstorming inline dispatch prompt** provided per `feedback_always_provide_inline_dispatch_prompt` BINDING (commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING)
- [ ] Sub-bundle 2 brainstorming implementer ship + Codex chain convergence + QA + merge + housekeeping
- [ ] Sub-bundle 2 writing-plans + executing-plans cycle
- [ ] Sub-bundle 2 operator-witnessed gate per Sec 9.1 Q6 LOCK (v22 schema migration verification + temporal log table population + chart_render bytes capture)
- [ ] Sub-bundles 3-5 cycle per Sec 9.1 Q1+Q2 serial sequence (Sub-bundle 3 inherits P14.N8 weather-chart-refresh-handler quality regression)

---

## 2026-05-28 #2 Phase 14 Sub-bundle 1 (data-wiring) WRITING-PLANS SHIPPED at `b2546d5` -- plan at `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` (3851 lines; 8 per-task slices T-1.1+T-1.2+T-1.3-OPTIONAL+T-2.1+T-3.1+T-4.1+T-4.2); Codex MCP single-chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR (5 rounds; 0C+18M+11m cumulative; ALL M resolved in-place); 46th cumulative C.C lesson #6 validation NOTABLE; Sub-bundle 1 executing-plans dispatch authorization NEXT per plan dispatch-readiness summary; memory `feedback_orchestrator_performs_merge` HARDENED to cover all 3 copowers phases

**Sub-bundle 1 writing-plans SHIPPED 2026-05-28 #2** at integration merge `b2546d5` of `phase14-sub-bundle-1-data-wiring-writing-plans` via `--no-ff`. 7 implementer commits (1 draft + 5 Codex fix bundles + 1 return report) + 1 merge commit. 2 files added (plan 3851 lines + return report 279 lines). ZERO production swing/ + tests/ writes (docs-only writing-plans phase); ZERO new Schwab API calls; L2 LOCK preserved + REINFORCED via NEW multiset Counter source-grep test designed at T-4.1 (Codex R1.M#5 + R2.M#6 LOCKs); Schema v21 LOCKED + verified (21 *.sql files; no v22+ added). ~598+ cumulative ZERO Co-Authored-By trailer drift preserved through this merge.

**Production-code spot-checks against plan citations PASSED at orchestrator-side QA**:
- `insert_trade_with_event` at `swing/data/repos/trades.py:155` per Codex R2.M#3+R3.M#1 LOCK
- `NoActivePolicyError` + `get_active_policy(conn)` at `swing/data/repos/risk_policy.py:28+98` per R1.M#1 + R2.M#1+M#2 LOCK
- `DailyManagementTileVM` at `swing/web/view_models/trades.py` (NOT `daily_management.py`)
- `build_dashboard` constructs tile inline at line 1390 (matches plan citation)
- `CandidateSectorIndustryRecord` provenance fields (`sector + industry + candidate_id + evaluation_run_id`) per R1.M#6 LOCK
- `TestClient(raise_server_exceptions=False)` fixture for FastAPI 500 propagation assertions per R1.M#3 LOCK
- Multiset Counter L2 LOCK source-grep asserts HEAD multiset SUBSET of `bf7e071` baseline per R1.M#5 + R2.M#6 LOCKs

**Semantic extension at P14.N3**: plan extends spec's locked 3-field VM contract to 4 fields (adds `position_capital_policy_missing` for NoActivePolicyError edge case per Codex R2.M#1+M#2 LOCK). Plan §E reverification + return report §4 explicitly characterize this as a SEMANTIC EXTENSION consistent with spec §6.4 second bullet (which anticipates a NoActivePolicyError caveat), NOT a scope re-litigation.

**Sec 9.1 + brainstorm spec §2 + brainstorm dispatch brief §1 + writing-plans dispatch brief §1 LOCKs**: ALL 23 preserved verbatim per return report §4 table. ZERO deviations.

**Per-task slicing locked** per plan §G: T-1.1 (`get_latest_sector_industry_per_ticker` repo helper + `CandidateSectorIndustryRecord` dataclass; ~2-3 commits + ~5 tests) + T-1.2 (`swing diagnose backfill-trades-sector-industry` CLI + restore-SQL artifact; ~2-3 commits + ~9 tests) + T-1.3 OPTIONAL (VM fallback Fix-1b; defer to operator-gate trigger) + T-2.1 (V2.G4 3 surgical edits + `test_client_with_pipeline_run_no_raise` fixture; ~1-2 commits + ~7-8 tests) + T-3.1 (P14.N3 4-field VM extension + denominator-stamping + PROVISIONAL/LIVE/policy-missing template chain + ARIA affordance; ~2-3 commits + ~12-14 tests) + T-4.1 (L2 LOCK multiset source-grep; ~1 commit + ~2 tests) + T-4.2 (integration + return report; ~1 commit + ~2 tests). **Total ~8-12 commits + ~42-46 fast tests projected** (slightly above brief's 34-36 estimate due to denominator-stamping + 4th field + policy-missing fixture coverage).

**4 NEW forward-binding lessons banked at return report §9** (carry forward to executing-plans):
- #10 NoActivePolicyError fallback semantic-extension audit (4-round cumulative; R1.M#1 + R2.M#1+M#2 + R4.M#1)
- #11 TestClient `raise_server_exceptions=False` discipline for propagation-to-500 tests (R1.M#3 LOCK)
- #12 Production API call-graph cascade verification at every Codex round (4-round cumulative; refines gotcha #19)
- #13 Multiset-comparison discipline for source-grep regression tests (2-round cumulative; R1.M#5 + R2.M#6 LOCKs)

**Orchestrator-side memory hardening at THIS housekeeping**: `feedback_orchestrator_performs_merge` HARDENED to cover all 3 copowers phases (brainstorm + writing-plans + executing-plans). The prior text scoped the override narrowly to operator-witnessed-gate (executing-plans only); brainstorm + writing-plans merges lack an operator-witnessed gate and were silently defaulting back to system-prompt baseline asking-for-confirmation. MEMORY.md index updated.

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (7-commit chain ZERO Co-Authored-By verified via `%(trailers)`; docs-only diff scope; Codex catches spot-checked against production code at `swing/data/repos/trades.py:155` + `swing/data/repos/risk_policy.py:28+98` + `swing/web/view_models/trades.py` + `swing/web/view_models/dashboard.py:1390`; multiset Counter L2 LOCK design verified; Schema v21 LOCKED verified via direct migration file count)
- [x] Merge `phase14-sub-bundle-1-data-wiring-writing-plans` `--no-ff` to main at `b2546d5` + push to origin/main
- [x] phase3e-todo new top entry (THIS pass)
- [x] Memory `feedback_orchestrator_performs_merge` HARDENED + MEMORY.md index updated
- [ ] **Sub-bundle 1 executing-plans dispatch brief authoring** consuming plan §G per-task slicing + return report §9 forward-binding lessons #10-#13 + dispatch-readiness summary §15
- [ ] **Sub-bundle 1 executing-plans inline dispatch prompt** provided per `feedback_always_provide_inline_dispatch_prompt` BINDING (commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING)
- [ ] Worktree teardown for `phase14-sub-bundle-1-data-wiring-writing-plans` (operator-side OR per cleanup-script; not orchestrator-blocking)
- [ ] Sub-bundle 1 executing-plans implementer ship + Codex chain convergence + QA + merge + operator-witnessed gate + post-merge housekeeping
- [ ] Sub-bundles 2-5 cycle per Sec 9.1 Q1+Q2 serial sequence

---

## 2026-05-28 Phase 14 Sub-bundle 1 (data-wiring) BRAINSTORM SHIPPED at `9104bb8` -- spec at `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md` (~810 lines); Codex MCP single-chain CONVERGED at R4 NO_NEW_CRITICAL_MAJOR (4 rounds; 1C + 10M + 11m cumulative; ALL C+M resolved in-place); 45th cumulative C.C lesson #6 validation NOTABLE; Sub-bundle 1 writing-plans dispatch authorization NEXT per spec Sec 10.1 single-dispatch recommendation

**Sub-bundle 1 brainstorm SHIPPED 2026-05-28** at integration merge `9104bb8` of `phase14-sub-bundle-1-data-wiring-brainstorm` via `--no-ff`. 6 implementer commits (1 draft + 4 Codex fix bundles + 1 return report) + 1 merge commit. 3 files added (spec 724 lines + return report 215 lines; merge produced no phase3e-todo conflict per pre-merge 3-way analysis -- branch's merge base `3648e56` predated P14.N7 banking at `22874f2`, but the branch never touched phase3e-todo so 3-way merge cleanly preserved P14.N7 from main). ZERO production swing/ + tests/ writes (docs-only brainstorm phase); ZERO new Schwab API calls; L2 LOCK preserved; Schema v21 LOCKED + verified via direct migration file read (21 *.sql files; no v22+ added). ~588+ cumulative ZERO Co-Authored-By trailer drift preserved through this merge.

**Five substantive Codex catches verified against production code at orchestrator-side QA**:
1. **R1.C1**: P14.N3 spec initially cited non-existent `equity_resolver.resolve_live_capital(...)` + non-existent `tile.review_date` field. Production reality: `resolve_live_capital_denominator_dollars` at `swing/metrics/equity_resolver.py:32` + `snap.data_asof_session` anchor. Fix LOCKED both.
2. **R3.M1**: percent-vs-proportion unit mismatch on the daily-management Capital % rendering path. Initial R1 fix recommended `_compute_position_util_pct` from `swing/metrics/maturity.py:296` (returns percent already × 100); but the daily-management template multiplies by 100 again. Would have rendered 1500.0% on a 15% utilization. Final R3 fix LOCKED `swing/trades/daily_management.py:compute_position_capital_utilization` (returns PROPORTION 0.0-1.0+) per the existing template contract.
3. **R3.M2**: `swing/web/routes/dashboard.py` has no module-level logger pre-fix; spec's R1-locked `log.warning(...)` would NameError. Fix LOCKED `import logging; log = logging.getLogger(__name__)` addition at module top.
4. **R1.M5 + R2.M2**: V2.G4 fix initially preserved broad-Exception-then-409 pattern that HID the original V2.G4 root cause. Anti-pattern LOCKED: narrow `ValueError`-only catch (empty-archive expected) -> degrade to 409 + log.warning; let `TypeError`, `AttributeError`, `KeyError`, `RuntimeError`, ... propagate to FastAPI default 500. Discriminating test asserts programming-error propagation.
5. **R1.M3 + R2.M3**: V2.G3 backfill design LOCKED with STRICT all-or-nothing semantic (dry-run SELECT uses AND-empty filter; partial-empty rows excluded from UPDATE + surfaced via separate SKIP_PARTIAL_EMPTY diagnostic) + restore-SQL artifact emission (defense-in-depth survives crash post-UPDATE) + DHA/DHC legacy-NULL carve-out via SKIP_NO_CANDIDATES_ROW action label (no hardcoded ticker list).

**Sec 9.1 LOCKs preserved verbatim** at the spec (Q1 sequence + Q2 serial + Q6 operator-witnessed gate + Q7 single Codex chain + §1.1-§1.6 sub-bundle locks; return report §4 table cites each). Sub-bundle decomposition per spec §10.1: **single writing-plans + executing-plans dispatch** recommended for all three items (cohere on dashboard + daily-management surfaces; no inter-item dependencies; ~8-12 commits + ~34-36 tests within dispatch brief estimates).

**Return report bankings** at `docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md`:
- §7: 8 V2 candidates banked (e.g., V2.G3 Fix B/C/D variants; V2.G4 hydrate-then-fetch defense-in-depth; P14.N3 schema CHECK enum widening to descriptive values)
- §8: 8 forward-binding writing-plans lessons (consume at writing-plans dispatch brief authoring)

**Forward action sequence (orchestrator-side; THIS pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (6-commit chain ZERO Co-Authored-By verified via `%(trailers)`; 3-dot diff confirms docs-only scope; Codex catches spot-checked against production code at `swing/metrics/equity_resolver.py` + `swing/trades/daily_management.py` + `swing/metrics/maturity.py` + `swing/web/routes/dashboard.py`)
- [x] Merge `phase14-sub-bundle-1-data-wiring-brainstorm` `--no-ff` to main at `9104bb8` + push to origin/main
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Sub-bundle 1 writing-plans dispatch brief authoring** consuming spec §10.1 single-dispatch recommendation + return report §8 forward-binding lessons
- [ ] **Sub-bundle 1 writing-plans inline dispatch prompt** provided per `feedback_always_provide_inline_dispatch_prompt` BINDING (commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING)
- [ ] Worktree teardown for `phase14-sub-bundle-1-data-wiring-brainstorm` (operator-side OR per cleanup-script; not orchestrator-blocking)
- [ ] Sub-bundle 1 writing-plans implementer ship + Codex chain convergence + QA + merge + housekeeping
- [ ] Sub-bundle 1 executing-plans phase (after writing-plans merged)
- [ ] Sub-bundle 1 operator-witnessed gate per Sec 9.1 Q6 LOCK
- [ ] Sub-bundles 2-5 cycle per Sec 9.1 Q1+Q2 serial sequence

---

## 2026-05-27 PM #3 Turn H: G2 W-bottom-derived ruleset backtest SHIPPED at `31fa281` -- joint hypothesis NOT supported at tested scale (ALL 9 cells expectancy_R < 0); G_bulkowski tight-stop partially validated on avg_loss_R lever; D2 EXPANDED N=71->N=42 substrate-freshness reframe is itself a methodology finding (candidate gotcha #37); 44th cumulative C.C lesson #6 validation NOTABLE (gotcha #36 two-Codex-chain FIRST canonical application validated)

**G2 SHIPPED 2026-05-27 PM #3** at integration merge `31fa281` of `applied-research-g2-w-bottom-ruleset-backtest` via `--no-ff` (with brief Amendment-namespace merge conflict resolved: orchestrator Amendment 0 renamed + retained alongside implementer's Brief Amendments 1-4). 16 implementer commits + 1 merge commit. 28 files changed (3-dot scope: G2-specific only; ZERO orchestrator-file edits). 113 fast tests + 1 self-skip green; ZERO production swing/ writes; ZERO new Schwab API calls; L2 LOCK preserved + REINFORCED; Schema v21 unchanged.

**Substantive finding (descriptive per gotcha #33 LOCK):** H_joint NOT supported at this substrate scale. All 9 (ruleset, substrate) cells expectancy_R range [-3.13R, -0.146R]. Three substantive sub-findings:
1. G_bulkowski's TIGHT-STOP HYPOTHESIS partially validated on avg_loss_R lever (R2-A G 0.618R vs E 1.550R; D2 G 0.560R vs E 1.576R) but offset by win-rate drop (G 2%/0% vs E 23%/28%) + trigger conv drop (G 0.85/0.69 vs E 0.95/0.90); net expectancy NOT flipped above zero.
2. H_oneil DOMINATED (worst avg_loss + lowest trigger conv on both substrates); 8% entry-relative + SMA50 combination not competitive.
3. **D2 EXPANDED substrate-freshness sensitivity** -- Brief Amendment 1 LOCKED N=71->N=42 via SHA-locked filter; E's prior D2 Amendment 5 +1.220R does NOT reproduce on actual SHA-locked fixture (now -0.800R). This is a methodology finding in itself: prior-arc expectancy anchors are sensitive to cohort fixture freshness; re-runs against drifted fixtures may diverge.

**Per-(ruleset, substrate) cell summary (descriptive; from scorecard.csv):**

| Substrate | E (existing) | G_bulkowski | H_oneil | I_edwards_magee |
|---|---|---|---|---|
| R2-A N=65 | -1.086R / 22.5% / 1.550R | -X.XR / 2% / 0.618R | (worst) / large negative | middling |
| D2 N=42 | -0.800R / 28% / 1.576R | similar profile | (worst) / 2.14R avg_loss | middling |

(Full 9-metric scorecard at `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/scorecard.csv`; findings doc at `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md`; return report at `docs/g2-w-bottom-ruleset-backtest-return-report.md`.)

**Codex MCP two-chain pattern (gotcha #36 FIRST canonical application) VALIDATED**:
- Chain #1 pre-smoke (post-Slice-4): 5 rounds; **3 CRITICAL + 13 MAJOR + 12 MINOR caught BEFORE smoke artifact emission**; converged R5 NO_NEW_CRITICAL_MAJOR. Without two-chain pattern these would have been caught AFTER smoke + required re-emission.
- Chain #2 post-smoke (post-Slice-6): 2 rounds; 0 CRITICAL + 3 MAJOR + 5 MINOR (narrative-discipline scrub); converged R7.
- Cumulative both chains: 3C + 16M + 17m; ALL CRITICAL + MAJOR resolved or accepted-with-rationale. **44th cumulative C.C lesson #6 validation NOTABLE** (slot spans both chains; gotcha #36 two-Codex-chain default is validated as the new normal for applied research).

**4 Brief Amendments banked in-brief during pre-smoke chain** (preserved at merge):
1. D2 EXPANDED substrate actual N=42 (NOT N=71) -- SHA-locked fixture authoritative per gotcha #34
2. Entry/exit price semantic CONFIRMED brief-literal (entry-at-trigger-close vs entry-at-next-bar-open; G/H/I diverge from A-F execution semantic; methodological caveat for cross-ruleset comparison)
3. Target measured-move formula PATTERN-ANCHORED (center_peak + height) NOT entry-relative -- W-bottom literature canonical
4. Brief Sec 2.1 internal inconsistency on 1.3x volume boundary (strict `>` honored; line 168 sketch had boundary error)

**Candidate gotcha #37 BANKING DEFERRED to operator decision**: D2 EXPANDED substrate-freshness sensitivity is a substantive methodology finding (prior-arc expectancy anchors may not reproduce against fixture-drifted re-runs). Possible bankings: (a) NEW gotcha #37 extending gotcha #26 archive bar-content TEMPORAL mutation from per-bar to per-COHORT-fixture mutation; (b) gotcha #35 extension covering anchor numerical reproducibility, not just metric definition; (c) defer to operator framing at next housekeeping. Operator-paired decision pending.

**Forward action sequence (orchestrator-side; Turn H post-merge housekeeping pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (16-commit chain; ZERO Co-Authored-By verified via `%(trailers)` inspection + 1 narrative-mention; 3-dot diff confirms branch only touched G2-specific files + .gitignore; ZERO swing/ writes; L2 LOCK source-grep clean; 113+1 fast tests pass; gotcha #33 + #35 LOCKs preserved; smoke artifact + findings doc + return report present + content-verified)
- [x] Merge `applied-research-g2-w-bottom-ruleset-backtest` `--no-ff` to main at `31fa281` (with Amendment-namespace merge-conflict resolved: orchestrator Amendment 0 + implementer Brief Amendments 1-4 preserved alongside each other) + push to origin/main
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Operator-paired gotcha #37 banking decision** (substrate-freshness sensitivity; deferred to operator framing)
- [ ] **Operator-paired next-arc decision** post-G2 SHIP. Existing Turn H V2-mechanic enumeration items remain candidates; the G2 NOT-SUPPORTED result eliminates some + reweights others:
  - **Substrate-size augmentation experiment** (V2 candidate; aggregate watch->aplus flips across multiple V2 binding variables for T>=20 cohort): G2 result motivates this LESS strongly than V2-mechanic alone did (W-bottom rulesets don't pan out at any tested scale; the issue may be ruleset-fit not substrate-size).
  - **D2 baseline canonical_survival_rate L4 remediation**: still methodologically useful.
  - **Phase 14 commissioning consideration** (operator early-planning in parallel; comprehensive scope roll-up in PM #2 entry below).
  - **Finviz filter adjustment investigation for W candidates** (banked Turn H PM #3): G2 result eliminates the gating condition; not actionable as standalone arc.
  - **Other-gates-not-enumerated market-conditions investigation**: banked.
  - **Temporal wait** -- 1-3 months for data tail advance + re-test against fresher substrate; potentially revisit gotcha #37 candidate.

Likely operator framing: G2's NOT-SUPPORTED result + V2-mechanic's "V2 substrates are SMALL not THIN" finding + R2-A's NEGATIVE on E + R2-D's INSUFFICIENT SAMPLE collectively suggest the applied research arc on V2-binding-variable-cohort + W-bottom rulesets has reached a methodological end-point at current substrate scale. Phase 14 commissioning or temporal wait are the likely next moves.

---

## 2026-05-27 PM #2 Phase 14 preliminary scope roll-up (pre-commissioning; PRUNE AT FORMAL PLANNING)

**Status:** PRELIMINARY decision per operator request Turn H 2026-05-27 PM #2 — close out all currently-open Phase-14-eligible items (V2.G1-G4 + closeout review + 6 NEW operator items banked THIS pass). NOT a commissioning commitment; the formal brainstorming brief will operator-pair through this list with `AskUserQuestion` triage + prune-as-necessary semantics. Phase 14 is still DEFERRED per locked decision 2026-05-23 PM (`docs/phase13-closer-next-phase-triage.md` §"OPERATOR DECISION LOCKED") pending Applied Research cross-cohort robustness establishment — but accumulating the scope list NOW lets brainstorming fire immediately when the operator clears the deferral.

**Items in scope (preliminary; subject to prune at brainstorming):**

| ID | Title | Severity | Source | Note |
|---|---|---|---|---|
| **CR.1** | Closeout review exit data + chart snapshot surfacing | Medium | Turn H 2026-05-27 PM (below) | Template-extension scope; reuses T2.SB6 chart_renders cache |
| **V2.G1** | Hyp-rec + watchlist expanded charts not rendering candlesticks | Medium | Post-T4.SB gate 2026-05-23 | Couples with P14.N2 (candlestick discipline) |
| **V2.G2** | Watchlist expanded chart title shows "hyp-rec detail" (surface-name leakage) | Cosmetic | Post-T4.SB gate 2026-05-23 | Maps to T4.SB writing-plans V1 simplification #8 (rename `hyprec_detail` to `ticker_detail` + v22 schema) |
| **V2.G3** | VSAT lost Sector + Industry values in open-positions table | Data wiring | Post-T4.SB gate 2026-05-23 | Same gotcha family as PriceCache `_last_close` ticker-rotation |
| **V2.G4** | "Refresh weather chart" reports "no OHLCV bars available for SPY" post-pipeline | Medium | Post-T4.SB gate 2026-05-23 | Possibly same root cause as V2.G1 |
| **P14.N1** | Small dashboard-watchlist-style thumbnail charts on open-positions + hyp-rec tables | Medium-UX | Turn H 2026-05-27 PM #2 (NEW; below) | Bundles with V2.G1 + P14.N2 chart-surface uniformity thread |
| **P14.N2** | All charts MUST be candlesticks (extends V2.G1); consider 10 + 20 MA overlays | Medium | Turn H 2026-05-27 PM #2 (NEW; below) | Likely a renderer-uniformity audit; subsumes V2.G1 fix |
| **P14.N3** | Daily management Capital % "PROVISIONAL" suffix unexplained | Cosmetic / UX | Turn H 2026-05-27 PM #2 (NEW; below) | Surface explanation OR remove flag; investigate flip-condition |
| **P14.N4** | BULZ open-positions chart shows undescribed green + yellow shaded region | Cosmetic / UX | Turn H 2026-05-27 PM #2 (NEW; below) | Legend/annotation missing; suspect entry/stop/target shaded zones |
| **P14.N5** | Metrics overview dashboard + graphics-driven surfaces (currently text-heavy navigation) | Medium-UX | Turn H 2026-05-27 PM #2 (NEW; below) | Significant scope; potentially multi-bundle |
| **P14.N6** | Journal page redesign — browse-the-database surface + rich trade entries + clickable per-trade drill-down + annotated chart + small thumbnails | High-UX | Turn H 2026-05-27 PM #2 (NEW; below) | Largest single scope item; likely sub-bundle-decomposed at brainstorming |
| **P14.N7** | schwabdev background `checker` threads die under sleep/wake DNS-failure cycles (silent token-refresh degradation) | Medium-resilience | Turn H 2026-05-27 PM #5 (NEW; below) | NOT in Sub-bundle 1 (scope LOCKED at brief §1.1); future sub-bundle slot OR Phase 15+; banked AFTER Sec 9.1 LOCK so does NOT alter sub-bundle 1-5 decomposition |
| **P14.N8** | Weather chart refresh-handler renders divergent from pipeline-time render (trend hardcoded to "n/a" + gridlines missing) | Cosmetic / UX | Sub-bundle 1 S4 operator-witnessed gate 2026-05-29 (NEW; below) | Pre-existing Phase 13 code at `aa1900f` line 117; REVEALED (not introduced) by Sub-bundle 1 V2.G4 fix; routes to **Sub-bundle 3 chart-surface uniformity** per Sec 9.1 Q1 (natural home for chart-render quality thread) |

**Likely sub-bundle decomposition at formal planning (informational; brainstorming will lock):**
1. **Chart-surface uniformity bundle** — V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + BULZ-shaded-region explanation. Coheres around the chart-render + chart_jit substrate; renderer-kwargs uniformity LOCK per Expansion #10 sub-discipline (c).
2. **Data-wiring bundle** — V2.G3 + V2.G4 + P14.N3 PROVISIONAL flag investigation. Coheres around persistence/JOIN/cfg-resolution debugging. **P14.N7 is RELATED (infrastructure resilience theme) but BANKED OUTSIDE Sub-bundle 1 active dispatch per Sec 9.1 LOCK; candidate Sub-bundle 1.5 follow-up OR Phase 15+.**
3. **Review + journal UX bundle** — CR.1 + P14.N6 + small-chart integration. Coheres around per-trade close-the-loop workflow.
4. **Metrics overview bundle** — P14.N5 standalone (depends on metrics-wiring audit landed at T-T4.SB.2; potentially largest scope; may split further).

**Cross-cutting watch items (likely BINDING at brainstorming):**
- L2 LOCK (zero new Schwab API calls; preserve through Phase 14)
- V2.G2 rename `hyprec_detail` → `ticker_detail` is a v22 schema migration — backup-gate equality form per gotcha #11 LOCK applies
- Renderer-kwargs uniformity per Expansion #10 (c); cache-collision discriminating tests
- Browser-only HTMX failure surfaces (Phase 5 R1 M1 + M2 + Phase 6 I3 trinity) for any new HTMX-driven journal/metrics surface
- Cumulative gotcha set (currently #1-#36) BINDING for Nth validation onwards at dispatch time

**Forward action:** Phase 14 deferral REMAINS locked until operator clears it; this section accumulates scope so brainstorming brief can be drafted immediately on de-deferral. Following the same `project_phase13_t4_sb_pause_for_list_additions` pattern that gated T4.SB — operator drives reopening + adds further items until list closes.

---

## 2026-05-27 PM operator-identified operational backlog (not for immediate investigation; banked for future dispatch)

**Closeout review surface enhancement** -- operator feedback during Turn H session 2026-05-27 (post-G2 dispatch); rolled up as Phase 14 item **CR.1**:

When doing the per-trade closeout review, surface (a) exit data (price at exit) and (b) a snapshot of the chart at exit/close to help the operator identify notes to add to the journal.

Likely scope when commissioned:
- Touch points: `swing/web/templates/review.html.j2` + `swing/web/templates/partials/review_form.html.j2` + `swing/trades/review.py` + relevant review-related view-model under `swing/web/view_models/`
- Reuse Phase 13 T2.SB6 chart-render infrastructure (`chart_renders` table + cache + `swing/web/chart_jit.py`); aligns with the T2.SB6b banked V1 simplification "hyp-rec/position detail VM chart bytes per-page VM wire-up" extended to closeout review surface
- Verify exit_price + exit_date are prominently surfaced (may require template-render extension only per CLAUDE.md gotcha #11 template-rendering-surface audit discipline; data likely already populated in trade VM)
- Small-to-medium production dispatch when commissioned; ZERO new schema; ZERO new Schwab API calls; sibling-module strategy for any NEW view-model surfaces

Source: operator Turn H feedback 2026-05-27 PM. Not blocking G2 ship; banked to operational backlog for future commissioning.

---

## 2026-05-27 PM #2 NEW Phase 14 operator items (banked this pass; 6 items; 5-field templates)

Operator-supplied additions via Turn H PM #2 follow-up post-G2 housekeeping. Rolled up under Phase 14 preliminary scope (above) as **P14.N1** through **P14.N6**.

### P14.N1 — Small dashboard-watchlist-style thumbnail charts on open-positions + hyp-rec tables

| Field | Value |
|---|---|
| **Issue title** | Open-positions table + hyp-rec table SHOULD display small thumbnail charts mirroring the dashboard watchlist top-5 pattern |
| **Surface** | `/dashboard` open-positions table rows + `/dashboard` hyp-rec table rows + corresponding partial templates (`swing/web/templates/partials/open_positions_row.html.j2` + `swing/web/templates/partials/hypothesis_recommendations_row.html.j2`); thumbnail rendering currently lives at `swing/web/templates/partials/watchlist_row.html.j2:9-16` (`_thumb_bytes` fragment) |
| **Frequency** | Every dashboard render with any open position OR any hyp-rec |
| **Severity** | Medium-UX — operator framing explicitly cites the watchlist thumbnails as "very useful" + wants the affordance everywhere |
| **Operator framing (2026-05-27 PM #2)** | "I have found the small charts on the dashboard watchlist very useful and would like those to display for the open positions and hyp-rec tables." |
| **Proposed resolution** | Extend `_thumb_bytes` partial inclusion to open-positions row + hyp-rec row templates; VM extension to plumb thumbnail SVG bytes per ticker through the open-positions + hyp-rec VMs (matches T2.SB6b banked V1 simplification "hyp-rec/position detail VM chart bytes per-page VM wire-up"). Cache-key shape per chart_renders surface enum may need NEW values (`open_position_thumbnail`, `hyprec_thumbnail`) OR may reuse `watchlist_row` surface with adjusted scope per Expansion #10 sub-discipline (c) renderer-kwargs uniformity LOCK. CANDLESTICK requirement per P14.N2 applies. Discriminating test: render dashboard with N open positions + M hyp-recs + assert N+M+top5 thumbnail SVGs present in response body. |
| **Cross-reference** | T2.SB6a substrate (`chart_renders` table + `get_cached_chart_svg` + `refresh_chart_render` + chart_jit cache-miss live-render hook); T2.SB6b V1 simplification #7 (per-page VM wire-up); P14.N2 candlestick requirement subsumes V2.G1 |

### P14.N2 — All charts MUST be candlesticks (extends V2.G1); consider 10 + 20 day MA overlays

| Field | Value |
|---|---|
| **Issue title** | All chart surfaces must render as candlesticks (extends V2.G1's hyp-rec + watchlist scope to ALL surfaces); optionally add 10 + 20 day MA overlays |
| **Surface** | All chart-render surfaces under `swing/web/charts.py` + `swing/web/chart_jit.py`: `render_market_weather_svg`, `render_position_detail_svg`, `render_hyprec_detail_svg`, `render_watchlist_thumbnail_svg`, future `render_*_thumbnail_svg` per P14.N1 |
| **Frequency** | Every chart render across the dashboard + drilldown surfaces |
| **Severity** | Medium — chart-type uniformity is core UX expectation; V2.G1 already escalated for hyp-rec + watchlist subset |
| **Operator framing (2026-05-27 PM #2)** | "All charts need to be candlesticks (as noted in V2.G1). Potentially also should 10 and 20 MAs." |
| **Proposed resolution** | Renderer-uniformity audit across the 4+ render functions: verify each invokes mplfinance candlestick rendering (or equivalent) AND identical MA-line set per renderer-kwargs uniformity LOCK (Expansion #10 sub-discipline (c)). Wire 10d + 20d SMA into `ma_lines` kwarg propagation per existing `render_watchlist_thumbnail_svg(ma_lines=...)` precedent. Discriminating test: byte-parity OR pixel-diff test asserting all 4+ render functions emit candlestick chart geometry under identical input bars. V2.G1 root-cause investigation (renderer divergence vs renderer-kwargs vs CSS clipping per V2.G1 disposition table) folds into this item. |
| **Cross-reference** | V2.G1 (subsumed); Expansion #10 sub-discipline (c) renderer-kwargs uniformity; CLAUDE.md gotcha #12 "matplotlib mathtext" discipline applies to any new title/legend strings |

### P14.N3 — Daily management Capital % column "PROVISIONAL" suffix unexplained

| Field | Value |
|---|---|
| **Issue title** | Daily management Capital % column appends "PROVISIONAL" with no UI affordance explaining the flag OR what would clear it |
| **Surface** | Daily management surface — likely `/daily-management` view + `swing/web/view_models/daily_management.py` + `swing/web/templates/daily_management.html.j2`; backing data at `daily_management_records` table per Phase 8 ship + per Phase 9 risk_policy ratification |
| **Frequency** | Every daily management surface render that includes a PROVISIONAL-flagged row (frequency unknown without investigation) |
| **Severity** | Cosmetic / UX — operator cannot diagnose state without external context |
| **Operator framing (2026-05-27 PM #2)** | "Daily management Capital % column shows 'PROVISIONAL' appended, not clear why or what would remove that flag" |
| **Proposed resolution** | Two-step investigation: (1) `Grep "PROVISIONAL"` across `swing/` to identify the flip-condition + state-machine semantics (likely a placeholder pre-reconciliation OR pre-equity-snapshot-finalization); (2) add UI affordance per CLAUDE.md gotcha #11 template-rendering-surface audit — tooltip OR explanation text OR pre-empty-state messaging. May also be a CHECK enum widening if "PROVISIONAL" should be replaced with descriptive enum values. Discriminating test: plant a row in each known state + assert UI renders the correct affordance (tooltip text OR description OR no flag if condition no longer applies). |
| **Cross-reference** | Phase 8 daily-management ship (Codex R1-R5 family per CLAUDE.md gotcha collection); Phase 9 risk_policy ratification single-fire semantic per gotcha (V17 ratification) |

### P14.N4 — BULZ open-positions chart green + yellow shaded region undescribed

| Field | Value |
|---|---|
| **Issue title** | BULZ chart in open-positions table renders green + yellow shaded regions with no legend or annotation explaining the semantic |
| **Surface** | `/dashboard` open-positions BULZ chart row — rendered via `render_position_detail_svg` (or equivalent) at `swing/web/charts.py` |
| **Frequency** | Every dashboard render with BULZ as an open position (and presumably any open position with the same shaded-region semantic) |
| **Severity** | Cosmetic / UX — operator cannot interpret the visual annotation |
| **Operator framing (2026-05-27 PM #2)** | "BULZ chart (in open positions table) shows a green and yellow shaded area with no description of what that means." |
| **Proposed resolution** | Investigate `render_position_detail_svg` (and any peer renderer) for `axhspan` / `axvspan` / `fill_between` calls; likely candidates are (a) entry-to-stop risk zone shaded yellow; (b) entry-to-target reward zone shaded green; (c) trail-MA distance shaded. Add inline legend OR title/subtitle annotation describing the semantic. Apply CLAUDE.md gotcha #12 matplotlib-mathtext discipline (no `$`/`^`/`_` in title strings) + ASCII-only per gotcha #32. Discriminating test: snapshot rendered SVG + assert legend text present; visual gate at operator-witnessed review. |
| **Cross-reference** | CLAUDE.md gotcha #12 (matplotlib mathtext); P14.N2 candlestick uniformity audit (likely touches same renderer family) |

### P14.N5 — Metrics page needs overview dashboard with graphics (currently text-heavy navigation)

| Field | Value |
|---|---|
| **Issue title** | `/metrics/*` surfaces require an overview/dashboard surface so individual metric pages are drill-downs not primary navigation; prefer graphical visualizations over current pure-text rendering |
| **Surface** | `/metrics/*` route family (9 surface routes per Phase 10 dashboard metric surfaces; `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/web/routes/metrics.py` + `swing/web/templates/metrics/*.html.j2`) |
| **Frequency** | Every operator visit to the metrics surfaces |
| **Severity** | Medium-UX — operator workflow regression cited; navigation friction reduces metric utility |
| **Operator framing (2026-05-27 PM #2)** | "Metrics page needs to show some kind of overall dashboard so the pages don't need to be navigated to except as a drill down. Ideally some kind of graphics would help display the information better rather than the current pure text." |
| **Proposed resolution** | Significant scope; brainstorming will operator-pair through. Likely structure: (a) NEW `/metrics` index route rendering overview cards summarizing each of the 9 surfaces with sparkline/mini-chart graphics; (b) drill-down clickthrough preserves current per-surface routes; (c) graphics library choice — likely matplotlib SVG (consistent with existing chart_renders pattern) OR a JS-based charting library (introduces new dependency surface). Discriminating tests per overview card: plant N representative metric rows + assert card renders the expected sparkline + summary stat. Couples with P14.N6 (journal-page-as-database-browser) at the visualization-library decision point. Likely sub-bundle decomposed at brainstorming (overview substrate first; per-surface card extensions follow). |
| **Cross-reference** | Phase 10 metrics dashboard ship (5 bundles); T2.SB6b pattern-outcomes 9th tile at `6ec989e`; Item 7 metrics-wiring audit at T-T4.SB.2 (Option 7C delimiter-aware fix; 4 surfaces) |

### P14.N6 — Journal page redesign (browse-the-database; rich trade entries + clickable drill-down + annotated chart + small thumbnails)

| Field | Value |
|---|---|
| **Issue title** | Journal page (`/journal`) is not very useful as-is; needs comprehensive redesign as a database-browsing surface with rich trade-entry rows, clickable drill-down to per-trade entries + annotated chart, and small thumbnail charts in the main listing |
| **Surface** | `/journal` route + `swing/web/routes/journal.py` (or equivalent) + `swing/web/view_models/journal.py` + `swing/web/templates/journal.html.j2` + related partials |
| **Frequency** | Every operator visit to the journal surface |
| **Severity** | High-UX — operator framing explicitly states "not very useful as-is" + requests comprehensive expansion; the journal surface is the post-trade analysis substrate which is core to the closed-loop review workflow |
| **Operator framing (2026-05-27 PM #2)** | "Journal page is not very useful as-is. More information should be included. This should be a page I can go to to essentially browse the database. The trade entries table should provide indication of how the trade went (open price, shares, total risk, closing price, final R, any flags at opening (chart shapes, A+, hyp-rec (and which), etc... And be clickable to reveal any specific entries associated with that trade (the entries filled out at opening) as well as an annotated chart. Main journal page should have the small charts present as well (the ones currently populating the watchlist on the dashboard, except using candlesticks)." |
| **Proposed resolution** | Largest single Phase 14 scope; brainstorming will sub-decompose. Listed required surfaces: (a) **Main listing**: each trade row shows open_price + shares + total_risk (cfg.capital_floor-aware per `project_capital_risk_floor` BINDING memory) + closing_price + final_R + entry-time flags (chart_pattern_class + aplus tier + hyp-rec linkage + hypothesis_label per Phase 13 T2.SB6c backlinks) + thumbnail chart (candlestick per P14.N2); (b) **Click-through detail**: surfaces all entries filled at trade open (Phase 6 review_log + Phase 7 fills + Phase 8 daily_management_records + any related event_log rows) + annotated full chart with entry/stop/target/fills marked. Database-browsing affordance suggests filterable + sortable table; HTMX-driven sort/filter without page reload. Cache-key shape considerations per chart_renders surface enum may need NEW `journal_trade_chart` surface. Discriminating tests: plant N trades with various close states + assert main listing renders all N rows with correct flag set + click-through reveals all attached entries + chart shows entry/stop/target markers. |
| **Cross-reference** | Phase 6 review_log ship; Phase 7 fills + Phase 8 daily_management_records ship; Phase 13 T2.SB6c trade backlinks (candidate_id + pattern_evaluation_id; trades table extension); CLAUDE.md gotcha #25 + #26 dropdown discipline; P14.N1 + P14.N2 thumbnail + candlestick subsumed in main listing scope |

### P14.N7 — schwabdev background `checker` threads die under sleep/wake DNS-failure cycles (silent token-refresh degradation)

| Field | Value |
|---|---|
| **Issue title** | schwabdev's background `checker` thread (spawned per schwabdev `Client.__init__`) dies with uncaught `requests.exceptions.ConnectionError` / `urllib3.exceptions.NameResolutionError` (`socket.gaierror: [Errno 11001] getaddrinfo failed`) under sleep/wake / network-disconnect cycles; auto-refresh of Schwab `access_token` stops working silently until the `swing web` process is restarted |
| **Surface** | `swing web` background; schwabdev `client.py:52 checker` thread calls `tokens.update_tokens()` → `update_access_token()` → `_post_oauth_token('refresh_token', ...)` → `requests.post('https://api.schwabapi.com/v1/oauth/token')`; thread dies when DNS resolution fails. Project surfaces: `swing/integrations/schwab/auth.py` + `swing/integrations/schwab/client.py` (`SchwabClient` wraps API calls but NOT the background thread); `swing/cli_schwab.py:status` reports token expiry but does NOT report checker-thread liveness |
| **Frequency** | Every sleep/wake / network-disconnect cycle while `swing web` is running. Operator-observed stack trace shows 7+ Thread-N "checker" deaths in a single capture (schwabdev appears to spawn replacement threads that ALSO die on the next cycle) |
| **Severity** | **MEDIUM-resilience** — NOT immediately user-visible; degrades over time. Failure cascade: (a) checker threads die → schwabdev auto-refresh stops; (b) `access_token` expires after ~30 min validity; (c) next Schwab API call returns 401 / auth error → project's `_classify_schwab_error` converts to typed `SchwabAuthError`; (d) `schwab_api_calls` audit rows accumulate `status='auth_failed'`; (e) eventually surfaces at `swing schwab status` + briefing banner "Schwab integration: degraded" (per existing CLAUDE.md gotcha "Typed SchwabApiError audit-row close discipline"). Workaround: restart `swing web`. NOT a data-corruption risk; NOT a Schwab-credential-leak risk; resilience-only |
| **Operator framing (2026-05-27 PM #5)** | "There is an issue with the webserver. I believe it happens when the computer is locked/standby/sleeping (unsure which)" — stack trace pasted; 7 "Thread-N (checker)" entries all dying with identical `NameResolutionError`/`ConnectionError` against `api.schwabapi.com` |
| **Proposed resolution** | Investigation paths (brainstorm will assess + recommend): (a) **Wrap schwabdev's checker thread**: monkey-patch OR subclass `schwabdev.Client` to install an exception-isolating wrapper around the `checker` thread's loop body; catch `ConnectionError` / `NameResolutionError` / `socket.gaierror` + treat as transient + retry-with-backoff (e.g., 30s/2min/10min exponential cap); preserve thread life. (b) **Disable schwabdev's checker thread + own the schedule**: verify schwabdev exposes an option to disable the auto-refresh background thread (recent schwabdev versions may have this); replace with a project-owned background thread that uses the same exception isolation + classifies failures via `_classify_schwab_error` per existing discipline. (c) **Add operator-visible degraded-health surface**: count live threads named `checker` at `swing schwab status` + warn if 0 (or below the expected count); surface in briefing banner. (d) **Document workaround as interim**: short-term operator playbook = `swing web` restart on resume-from-sleep. **Discriminating test**: simulate DNS failure during `checker` invocation (monkeypatch `socket.getaddrinfo` to raise `gaierror`); assert (1) thread survives + retries on backoff; (2) `schwab_api_calls` audit row records the transient failure if appropriate; (3) post-DNS-recovery, the thread successfully refreshes the token without operator intervention. **Project precedent**: existing CLAUDE.md gotchas "Typed SchwabApiError audit-row close discipline" + "schwabdev silent-failure-mode discipline" already establish that schwabdev vendor surfaces require project-side resilience wrappers; P14.N7 extends that discipline to BACKGROUND thread exception handling |
| **Cross-reference** | CLAUDE.md gotcha "Typed SchwabApiError audit-row close discipline" (extension target — extend from foreground API calls to background checker thread); "schwabdev silent-failure-mode discipline — `update_tokens()` does NOT raise on auth failure" (related vendor unreliability lesson); `swing/integrations/schwab/auth.py` + `swing/integrations/schwab/client.py` likely fix surface; `swing/cli_schwab.py:status` likely degraded-health surface extension target. **Not in Sub-bundle 1 dispatched scope** (Sub-bundle 1 §1.1 LOCK = V2.G3 + V2.G4 + P14.N3 only); landing options at future triage: (i) Sub-bundle 1.5 follow-up arc post Sub-bundle 1 ship; (ii) fold into Sub-bundle 2 if temporal log brainstorm surfaces affinity (UNLIKELY); (iii) Phase 15+ infrastructure resilience candidate per commissioning brief Sec 8 forward-look |

### P14.N8 — Weather chart refresh-handler renders divergent from pipeline-time render (trend "n/a" + missing gridlines)

| Field | Value |
|---|---|
| **Issue title** | `POST /dashboard/weather-chart/refresh` produces a chart that differs from the pipeline-time render: trend label hardcoded to "n/a" (vs. "stage_2" pipeline-time) + horizontal gridlines disappear |
| **Surface** | `/dashboard` Market Weather chart re-render via the "Refresh weather chart" button → `POST /dashboard/weather-chart/refresh` handler at `swing/web/routes/dashboard.py:116-118` invokes `render_market_weather_svg(bars=bars, trend_template_state="n/a")` with HARDCODED `"n/a"` literal + no styling kwargs |
| **Frequency** | Every "Refresh weather chart" click |
| **Severity** | **Cosmetic / UX** — chart still renders + V2.G4 happy path is unblocked; operator-visible regression vs pipeline-time chart appearance; pre-existing code that was previously masked because the refresh-path crashed before this line ran |
| **Operator framing (2026-05-29 S4 gate)** | Operator-supplied screenshot diff: pre-refresh trend="stage_2" + horizontal gridlines visible; post-refresh trend="n/a" + gridlines disappeared |
| **Proposed resolution** | (1) Thread the actual `trend_template_state` through the refresh handler — read from `weather_runs` or compute via `current_stage(conn, benchmark, asof_date)` per the pipeline-time render path; (2) Pass any gridline / styling kwargs the pipeline-time render uses to match output verbatim per Expansion #10 sub-discipline (c) renderer-kwargs uniformity LOCK. Discriminating test: snapshot pipeline-time render bytes + snapshot refresh-handler render bytes against identical bars + assert visual equivalence (or byte-identity if deterministic). Couples with Sub-bundle 3 chart-surface uniformity work (P14.N2 candlestick discipline + Expansion #10 (c) renderer-kwargs uniformity already in scope). |
| **Cross-reference** | Pre-existing code from commit `aa1900f` "Phase 13 T2.SB6b T-A.6.6 Theme 1 chart surfaces + dashboard market weather" 2026-05-21; REVEALED (not introduced) by Sub-bundle 1 V2.G4 fix at `phase14-sub-bundle-1-data-wiring-executing-plans` HEAD `1d366b9`; operator-witnessed gate S4 disposition 2026-05-29 routed P14.N8 to **Sub-bundle 3 chart-surface uniformity** per Phase 14 commissioning Sec 9.1 Q1 sequencing LOCK + the V2.G1+G2+P14.N1+P14.N2+P14.N4 chart-render-quality thread Sub-bundle 3 already covers. Pattern complement to Expansion #10 sub-discipline (c) renderer-kwargs uniformity LOCK + V2.G1 surface-name leakage family. |

---

## 2026-05-27 Turn H: V2-selection-mechanic ANALYTICAL investigation SHIPPED at `64e0099` -- 5 V2 binding variables characterized via per-variable 3-axis profile tags (productivity / size / survival); D_filt = 7.2x-70x baseline 0.138 confirms V2 substrates are ENRICHED for W-pattern productivity on per-ticker basis (substrate "thinness" framing in R2-A/R2-D was small-T not low-W-incidence); 43rd cumulative C.C lesson #6 validation NOTABLE; NEW gotcha #35 banked (substrate density metric disambiguation; Expansion #19 promotion); Brief Amendments 1-4 appended orchestrator-side

**V2-selection-mechanic SHIPPED 2026-05-27** at integration merge `64e0099` of `applied-research-v2-selection-mechanic-investigation` via `--no-ff`. 15 implementer commits + 1 merge commit. 40 files changed; +8491 insertions. 3 NEW `research/harness/v2_{tightness_range_factor,proximity_max_pct,orderliness_max_bar_ratio}/` cohort extractor module sets (3 modules each = 9 files) + 1 NEW `research/harness/v2_selection_mechanic/` analytical orchestration set (5 modules: `__init__` + `substrate_characterization` + `w_density_analysis` + `synthesis` + `run`) + 3 NEW cohort CSVs at `exports/research/cohorts/v2_*_sp*.csv` + 3 sibling audit JSONs + 1 NEW smoke artifact directory at `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/` (manifest + summary + 3 CSVs + synthesis MD; 6 files) + 1 NEW first-class study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md` (310 lines) + findings doc + return report. ZERO production swing/ writes (R2-A + R2-D + `pattern_cohort_evaluator` + D2 harness REUSE VERBATIM via byte-stability tests).

**Codex MCP adversarial-critic chains CONVERGED in two distinct rounds** per implementer's two-Codex-chain refinement (Brief Amendment 1). Chain #1 post-Slice-4 (implementation review): 5 rounds; 2 CRITICAL + 12 MAJOR + 3 MINOR cumulative; converged R5 NO_NEW_CRITICAL_MAJOR. Chain #2 post-Slice-6 (study writeup methodology review): 2 rounds; 0 CRITICAL + 3 MAJOR + 2 MINOR cumulative; converged R2 NO_NEW_CRITICAL_MAJOR. Cumulative across both chains: 2C + 15M + 5m; 21 closed in-place + 1 MINOR banked V2. **43rd cumulative C.C lesson #6 validation NOTABLE** (spans BOTH chains; chain-split was orchestrator-approved at the Slice 0 pre-flight checkpoint).

**Per-variable 3-axis profile tags LOCK** (smoke artifact ground truth at `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/per_variable_signals.csv`):

| Variable | D_filt = F/T | profile |
|---|---|---|
| vcp.tightness_range_factor | 9.13 | ENRICHED + MARGINAL(T=15) + DEGRADED(5.5%) |
| vcp.tightness_days_required | 9.14 | ENRICHED + MARGINAL(T=7) + SUPPRESSED(3.9%) |
| vcp.adr_min_pct | 1.00 | TYPICAL + INSUFFICIENT(T=4) + SUPPRESSED(2.3%) |
| vcp.proximity_max_pct | 9.67 | ENRICHED + INSUFFICIENT(T=3) + COMPARABLE(12.0%) |
| vcp.orderliness_max_bar_ratio | 3.00 | ENRICHED + INSUFFICIENT(T=1) + COMPARABLE(15.8%) |
| D2 baseline (REFERENCE) | 0.138 | T=516; F=71 |

**Headline finding**: V2 OHLCV binding-variable cohort selection ENRICHES for W-pattern productivity on per-ticker basis (D_filt 7.2x-70x baseline); the "substrate thinness" framing in R2-A + R2-D findings docs was a function of small substrate size (T<=15 in all 5 V2 cases; T<5 in 3 of 5; baseline T=516), NOT low per-ticker W incidence. R2-A's prior NEGATIVE on Ruleset E + R2-D's INSUFFICIENT SAMPLE reflect substrate-size + survival-quality limitations rather than W-pattern depletion. V2 substrates are METHODOLOGICALLY INFORMATIVE for W-pattern identification but actionable trade outcome QUALITY on V2-selected tickers requires substrate-size-aware verdict gating.

**Brief Amendments 1-4 banked orchestrator-side** (appended to dispatch brief at `docs/v2-selection-mechanic-investigation-dispatch-brief.md`):
1. Two-Codex-chain refinement (chain #1 implementation; chain #2 study writeup)
2. D2 baseline universe 88 -> 516 correction (orchestrator-side brief mischaracterization at Sec 1.4)
3. Substrate density metric disambiguation (3 metric families: D_filt + absolute F + dual-composite survival rates) -- drove NEW gotcha #35
4. Compatibility verdict structure clarification (per-variable 3-axis profile tags replace single global label)

**NEW CLAUDE.md gotcha #35 BANKED at THIS housekeeping (Expansion #19 promotion)**: Substrate density metric disambiguation -- dispatch briefs referencing prior-arc "density" numerical anchors MUST cite exact denominator + numerator definitions; ambiguous re-framing invites methodological conflation. Pattern complement to gotcha #34 (brief-prescription cross-table verification for SAME-arc data) -- extended to prior-arc-anchor vs new-brief metric-definition disambiguation across different arcs. Forward-binding for any future dispatch carrying forward numerical anchors from prior arcs.

**Discipline preservation**: ZERO Co-Authored-By footer drift (~575+ cumulative streak through `64e0099`; 15 V2-mechanic commits all clean per `%(trailers)` inspection + 0 `noreply@anthropic.com` matches); L2 LOCK preserved + REINFORCED via parametric source-grep tests across NEW v2_selection_mechanic module set; Schema v21 UNCHANGED; ASCII discipline COMPLETE per gotcha #32; ZERO new Schwab API calls; ZERO new yfinance runtime fetches (substrate characterization uses direct `pd.read_parquet` on legacy archives; pre-flight refresh of SSRM + SLDB by orchestrator 2026-05-26 before slice 1; other 16 substrate tickers acceptable per R2-A precedent at 1-4 day archive freshness); 192 NEW fast tests verified green via orchestrator-side pytest sweep (implementer reports 196; minor 4-test accounting drift); broader project fast suite deferred (research-branch-only; ZERO production writes per R2-A + R2-D precedent).

**Forward action sequence (orchestrator-side; Turn H post-merge housekeeping pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (15-commit chain; ZERO Co-Authored-By verified via `%(trailers)`; diff scope research-only; L2 LOCK source-grep clean; 192 fast tests pass; gotcha #34 FIRST + SECOND canonical applications verified via `test_binding_signals_table_cross_check.py`; gotcha #33 banned-terms test verified in `test_synthesis_and_run.py`; smoke artifact + study writeup + findings doc + return report all present + content-verified)
- [x] Merge `applied-research-v2-selection-mechanic-investigation` `--no-ff` to main at `64e0099` + push to origin/main
- [x] CLAUDE.md NEW gotcha #35 banked (substrate density metric disambiguation; Expansion #19 promotion; BINDING for 43rd validation onwards)
- [x] Brief Amendments 1-4 appended to dispatch brief at `docs/v2-selection-mechanic-investigation-dispatch-brief.md`
- [x] phase3e-todo new top entry (THIS pass)
- [x] **Operator-paired next-arc decision** post-V2-selection-mechanic SHIP — **CLOSED 2026-05-27 PM #3** by operator decision post-G2 SHIPPED at `31fa281`: applied research arc closed end-to-end (NO tested ruleset across A-I produces robust positive expectancy at current substrate scale; canonical closure at [`research/studies/2026-05-27-applied-research-arc-closure.md`](research/studies/2026-05-27-applied-research-arc-closure.md)); Phase 14 commissioned at `bf7e071` with NEW temporal pattern detection + observation log infrastructure as the operator-stated forward path. Options below are HISTORICAL ENUMERATION as of the V2-selection-mechanic merge time; superseded by [`docs/phase14-commissioning-brief.md`](docs/phase14-commissioning-brief.md) (Phase 14 scope) + the arc closure document (research forward-look). Phase 15+ research-branch candidates accumulate at the arc closure Sec 7 future-revisit predicates + commissioning brief Sec 8 forward-look enumeration.
  - **Substrate-size augmentation experiment** (V2 candidate #4 from return report Sec 6): aggregate watch->aplus flips across multiple V2 binding variables to construct substrate-size-sufficient (T>=20) V2-style cohort for defensible per-ruleset evaluation. Directly responsive to the per-variable T<=15 limitation surfaced by Turn H. Cost: ~4-8h impl + ~1-2h Codex. (HISTORICAL; superseded by temporal log infrastructure per arc closure Sec 7)
  - **D2 baseline canonical_survival_rate L4 remediation** (V2 candidate #1 from return report Sec 6): re-run D2 EXPANDED with results.csv emission enabled to complete the missing baseline survival rate anchor; closes L4-style limitation. Cost: ~1-2h compute + 1h docs. (HISTORICAL; banked as Phase 15+ low-priority per commissioning brief Sec 1 "Phase 14 does NOT include")
  - **R2-E (vcp.proximity_max_pct +5) backtest**: 3-ticker substrate (T=3); INSUFFICIENT SAMPLE forecast per Turn H profile (INSUFFICIENT + COMPARABLE survival); not informative as a standalone backtest given Turn H finding. (HISTORICAL; arc closed; not recommended)
  - **R2-F (vcp.orderliness_max_bar_ratio +1) backtest**: 1-ticker substrate (T=1); INSUFFICIENT SAMPLE forecast; not informative. (HISTORICAL; arc closed; not recommended)
  - **Option C real-time prospective tracking** for E on operator's pipeline outputs -- banked V2 candidate from D2; multi-month timeline. (HISTORICAL; arc closure Sec 7 retains as future-revisit option; subsumed by temporal log forward-walk semantics for any future ruleset)
  - **D + E hybrid ruleset variant** -- banked V2 candidate from D2; cost: ~2-4h impl. (HISTORICAL; arc closed; ruleset deployment-class work is OUT of Phase 14 per commissioning brief Sec 1)
  - **Phase 14 commissioning consideration** -- **SELECTED + COMMISSIONED** at `bf7e071`. See [`docs/phase14-commissioning-brief.md`](docs/phase14-commissioning-brief.md).
  - **Market-conditions investigation** -- banked alternative; analytical pivot to other-gates-not-enumerated per V2 sensitivity Sec B.3. (HISTORICAL; arc closure Sec 7 retains as Phase 15+ candidate)
  - **W-shape entry/exit rules extension (production arc) + downstream Finviz filter re-eval (short branch)** -- operator-banked Turn H 2026-05-27 PM #3 as the anticipated post-round-1 sequence (CORRECTED 2026-05-27 PM #4 — supersedes the earlier framing of this bullet). **SUPERSEDED 2026-05-27 PM #3 post-G2 SHIPPED**: the G2 backtest result (joint hypothesis NOT supported; ALL 9 ruleset/substrate cells expectancy_R<0 including W-bottom-derived rulesets G/H/I) negated the assumption that a W-bottom-derived production rule extension would be evidence-justified. Operator-stated forward path per Turn H PM #3 is the Phase 14 temporal log infrastructure (Sec 2.5 of commissioning brief), NOT a W-shape production-rule extension. Finviz filter widening is enumerated as Phase 15+ candidate per commissioning brief Sec 8 forward-look. Original bullet text retained for historical traceability of the framing arc. Citation: `research/studies/2026-05-27-applied-research-arc-closure.md` Findings 1+5+7.
  - **Temporal wait** -- 1-3 months for data tail advance; sequential-evidence path. (HISTORICAL; subsumed by temporal log forward-walk semantics which accumulate observations continuously from commissioning forward)

---

## 2026-05-26 PM #2 Turn G: R2-D V2 OHLCV `vcp.adr_min_pct +11` cohort 6-ruleset backtest SHIPPED at `7330628` — INSUFFICIENT SAMPLE verdict on canonical evaluation cohort (N=4 STNG-only; substrate ~4x thinner than peer cohorts); cross-cohort systemic-vs-cohort-specific test DEFERRED; gotcha #33 third canonical application + NEW gotcha #34 banked (brief-prescription cross-table verification; Expansion #18 candidate)

**R2-D SHIPPED 2026-05-26 PM #2** at integration merge `7330628` of `applied-research-r2d-adr-min-pct-cohort-backtest` via `--no-ff`. 6 implementer commits (2 slices + 2 Codex fix bundles + 1 smoke artifact + 1 docs) + 1 merge commit. 3 NEW `research/harness/r2d_adr_min_pct/` modules (sibling architecture LOCK observed; DO NOT refactor R2-A's cohort_csv into shared base — banked V2 candidate) + 4 NEW test files at `tests/research/r2d_adr_min_pct/` (59 fast tests) + 1 NEW `tests/fixtures/research/r2d_adr_min_pct/cohort.json` (N=4 canonical PrimaryVerdict entries; STNG-only) + 2 NEW smoke artifact directories + 1 NEW cohort CSV at `exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` (4 unique rows; sp2_0 naming reflects Amendment 1 sp=1 → sp=2.0 reconciliation). ZERO production swing/ writes (D2 + R2-A harnesses REUSED VERBATIM via byte-stability tests).

**Codex MCP adversarial-critic chain CONVERGED at R2 NO_NEW_CRITICAL_MAJOR after 2 rounds.** Cumulative: 0 CRITICAL + 6 MAJOR + 6 MINOR. ALL CRITICAL + MAJOR RESOLVED in-place; 4 of 6 MINOR resolved in-place; 2 BANKED V2 candidates. **41st cumulative C.C lesson #6 validation NOTABLE.** Codex caught 6 REAL MAJOR defects despite pre-Codex application of all 17 cumulative expansions: R1.M#1 brief sweep_point reconciliation (sp=1 prescription vs actual sp=2.0 binding signal per V2 sensitivity SUMMARY TABLE; orchestrator-side brief-authoring error → **gotcha #34 BANKED THIS HOUSEKEEPING**); R1.M#2 INSUFFICIENT SAMPLE pre-commit per gotcha #33; R1.M#3 fixture identity lock (N=4 + STNG-only + exact trough/peak dates); R1.M#4 audit JSON cohort_selection_method + v2_binding_variable; R1.M#5 canonical source SHA/size validation in wrapper; R1.M#6 --allow-non-canonical-paths CLI flag.

**R2-D canonical evaluation cohort** (composite>=0.5 + recency<=365d; mirrors D2 Amendment 5 EXPANDED filter + R2-A Amendment 6 LOCK): **N=4 W primary verdicts, ALL from a single ticker (STNG)**. Substrate density ~3% (raw 132 W primaries collapse to 4 post 5-BD adjacency merge + recency<=365d filter; AMX/GLNG/XENE have ZERO W primaries within 365 days of their respective asof_dates). Substrate ~4x thinner than R2-A (~13%) + D2 EXPANDED (~12%). **Per-ruleset detail (4 patterns x 6 rulesets = 24 trades; 100% trigger rate):** Ruleset E 1 of 1 closed-and-profitable @ +0.800R (3 still open at data tail; STNG-2025-05-22 highest-composite hit measured-move target at 5 sessions); Ruleset F 3 of 3 closed-and-profitable @ +0.122R mean / 100% win-rate (momentum-gate fail at session 6); Rulesets A/B/C/D ALL 4 patterns still open at data tail (no trail-MA / fixed-R / close-below-50d / Stage-2-progression-failure exits fired in 18-19 sessions).

**Headline verdict: INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color)** per gotcha #33 BINDING (third canonical application). F's technical PARTIAL POSITIVE on N=4 STNG-only EXPLICITLY REJECTED as cohort substitution per Amendment 1 A1.2 LOCK + gotcha #33's "headline-verdict-must-match-research-question-fit" rule. The cross-cohort systemic-vs-cohort-specific test (was R2-A's NEGATIVE unique to tightness_days_required OR systemic across V2 binding variables?) CANNOT be answered with N=4 vs N=65; sampling variance dominates systematic effect.

**Cross-cohort 5-way comparison (load-bearing):**

| Cohort | N pat | E closed-and-profitable | E mean R | E verdict |
|---|---|---|---|---|
| D1 post-refresh | 12 | n/a (E not tested) | n/a | NEGATIVE-strict (close_below_50d via DK + TROX) |
| D2 Companion 2 | 26 | 3 (100% wr) | +1.208R | PARTIAL POSITIVE (degenerate) |
| D2 EXPANDED | 71 | 5 | +1.220R | PARTIAL POSITIVE (6 of 7 statistical-defensibility tests PASS) |
| R2-A canonical | 65 | 9 (22.5% wr) | -1.086R | NEGATIVE |
| **R2-D canonical** | **4** | **1 (100% wr; N=1)** | **+0.800R** | **INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color)** |

**Cross-cohort discrimination test status: DEFERRED.** A future R2-* dispatch against a thicker V2 binding-variable substrate is required. Recommended: **R2-E (vcp.proximity_max_pct +5)** — next-largest remaining binding variable per dispatch brief §11.2 ordering. Pre-flight cohort_size analysis at slice 1 of any future R2-* dispatch is now CANONICAL (banked from R2-D's substrate-thinness surprise).

**NEW CLAUDE.md gotcha #34 BANKED at THIS housekeeping (Expansion #18 candidate)**: Brief-prescription cross-table verification — when authoring a dispatch brief prescribing a specific (sweep_point + count) tuple from V2 sensitivity artifacts OR analogous (parameter, threshold) pairs, the orchestrator-side brief-authoring MUST cross-check the SUMMARY TABLE (artifact top) AS WELL AS the per-variable drill-down section header. The brief's COUNT contract is authoritative; the SUMMARY TABLE's binding-signal sweep_point overrides the drill-down section header if the two disagree. Forward-binding for any future R2-* dispatch (R2-E proximity_max_pct +5; R2-F orderliness_max_bar_ratio +1) + any future dispatch referencing artifact-derived (parameter, threshold) pairs.

**Discipline preservation**: ZERO Co-Authored-By footer drift (~559+ cumulative streak through `7330628`); L2 LOCK preserved + REINFORCED via 3 NEW R2-D source-grep tests (parametrized over r2d_adr_min_pct module set; R2-A modules byte-stable + frozen); Schema v21 UNCHANGED; ASCII discipline COMPLETE per gotcha #32; ZERO new Schwab API calls (all 4 STNG tickers + 13 exemplars use legacy `.parquet`; V2 reader Shape A → legacy fallback); ZERO new yfinance fetches at backtest time (pre-flight refresh for AMX/GLNG/STNG/XENE via yfinance `period='max'` 2026-05-26 pre-dispatch); 98 R2-A + R2-D fast tests pass; ~6111 broader project tests estimated.

**Forward action sequence (orchestrator-side; Turn G SECOND-SESSION housekeeping pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (6-commit chain; ZERO Co-Authored-By; diff scope research-only; L2 LOCK 3 BINDING tests + R2-A modules byte-stable; 39+59=98 fast tests pass; cohort-validity discipline per gotcha #33 verified as third canonical application + F PARTIAL POSITIVE explicitly rejected as cohort substitution)
- [x] Merge `applied-research-r2d-adr-min-pct-cohort-backtest` `--no-ff` to main at `7330628` + push to origin/main
- [x] CLAUDE.md NEW gotcha #34 banked (brief-prescription cross-table verification; Expansion #18 candidate; BINDING for 42nd validation onwards)
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Operator-paired next-arc decision** post-R2-D SHIP. Options enumerated:
  - **R2-E**: `vcp.proximity_max_pct +5` cohort backtest. Tests cross-cohort systemic-vs-cohort-specific against a 3rd V2 binding variable. Pre-flight cohort_size analysis MANDATORY at slice 1 per R2-D substrate-thinness surprise. Cost: ~4-6h impl + ~1-2h Codex. (RECOMMENDED — direct continuation of R2-A→R2-D arc; tests whether R2-D's INSUFFICIENT SAMPLE is unique-to-adr_min_pct OR systemic across remaining V2 binding variables)
  - **R2-F**: `vcp.orderliness_max_bar_ratio +1` cohort backtest. Last remaining V2 binding variable; substrate may also be thin (only +1 max_delta_aplus signal); could be combined with R2-E for parallel-evidence cohort
  - **V2-selection-mechanic investigation** (RECOMMENDED if R2-E ALSO INSUFFICIENT SAMPLE): WHY are V2-binding-variable-selected substrates W-pattern-thin? Hypothesis: V2 selection mechanic correlates with chart regimes where W patterns are scarce (e.g., tightness criteria select tickers in flat/declining trends with few V-bottoms forming Ws). Investigation could illuminate fundamental compatibility between V2 cohort selection + W pattern detection
  - **Option C (real-time prospective tracking)** — banked V2 candidate from D2; validates D2's bias-free PARTIAL POSITIVE in forward deployment; appropriate while R2-D + future R2-* substrate analysis continues; multi-month timeline
  - **D + E hybrid ruleset** — banked V2 candidate; combines D's BE arm + tight trail with E's measured-move target hit; cost: ~2-4h impl
  - **Phase 14 commissioning consideration** — gated on cross-cohort robustness establishment (NOT established for any single ruleset across V2 binding variables given R2-D INSUFFICIENT SAMPLE)
  - **Temporal wait** — 1-3 months for data tail to advance; zero work; sequential-evidence path; preserves N>=10 bootstrap defensibility goal

---

## 2026-05-26 PM Turn G: R2-A V2 OHLCV `vcp.tightness_days_required +16` cohort 6-ruleset backtest SHIPPED at `634cc9f` — NEGATIVE verdict on canonical evaluation cohort; D2 Ruleset E PARTIAL POSITIVE does NOT generalize across cohort definitions (cross-cohort cohort-specific finding)

**R2-A SHIPPED 2026-05-26 PM** at integration merge `634cc9f` of `applied-research-r2a-tightness-days-required-cohort-backtest` via `--no-ff`. 8 implementer commits (2 implementation slices + 5 Codex MCP fix bundles R1-R5 + 1 final docs commit) + 1 merge commit. +4353 lines / 16 files; 3 NEW `research/harness/r2a_tightness_days_required/` modules (`cohort_csv.py` 536 lines + `regenerate_cohort.py` 62 lines + `__init__.py` 23 lines) + 1 NEW `tests/fixtures/research/r2a_tightness_days_required/cohort.json` (N=65 canonical PrimaryVerdict entries) + 3 NEW test files at `tests/research/r2a_tightness_days_required/` (39 fast tests: 19 cohort generation + 12 harness-reuse/L2-LOCK + 4 committed-artifact-canonical lock + 4 file structure) + 1 NEW cohort CSV at `exports/research/cohorts/r2a_tightness_days_required_sp1.csv` (7 unique rows) + sibling audit JSON at `r2a_tightness_days_required_sp1.flips_audit.json` (15 raw flips with eval_run_id + source SHA-256) + 2 NEW smoke artifact directories at `exports/research/pattern-cohort-detection-20260526T081400Z/` (manifest.json + summary.md) + `exports/research/w-bottom-ruleset-comparison-20260525T224203Z/` (manifest.json + summary.md) + findings doc at `docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md` + return report at `docs/r2a-tightness-days-required-cohort-backtest-return-report.md`. ZERO production swing/ writes (D2 harness REUSED VERBATIM; 6 byte-stability tests pass).

**Codex MCP adversarial-critic chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds.** Cumulative: 0 CRITICAL + 26 MAJOR + 21 MINOR. ALL CRITICAL + MAJOR RESOLVED in-place or ACCEPTED with documented rationale; 2 R5 MINOR banked as V2 candidates. **40th cumulative C.C lesson #6 validation NOTABLE.** Real defects Codex caught at the cohort-extraction surface: R1.M#2 silent under-extraction on parser permissiveness; R1.M#4 hardcoded column positions vulnerable to schema reorder; R2.M#3 section-boundary bug when no h3 follows; R2.M#4 line-anchored heading regex requirement for prose-defense; R2.M#1+M#2 per-triple identity verification (not just aggregate counts). **0 NEW gotchas banked at THIS housekeeping** — parser-robustness findings are localized to markdown-table extraction patterns; gotcha #33 cohort-validity-vs-verdict-criteria first canonical application post-D2-Amendment-3 banking.

**R2-A canonical evaluation cohort** (composite>=0.5 + recency<=365d; mirrors D2 Amendment 5 EXPANDED filter): N=65 historical W patterns across 7 tickers (FRO=7, KOD=14, NAT=7, OII=5, RLMD=11, SEI=10, TROX=11); 62 of 65 patterns triggered (95% trigger rate). **Ruleset E: 9 closed-and-profitable / 40 closed / 22.5% win-rate / mean R closed -1.086R / 95% CI [-1.377R, -0.782R] / P(mean>0)=0.0000**. ALL of {D, E, F} fail PARTIAL POSITIVE thresholds per dispatch brief §6.5 -> **NEGATIVE verdict**. Asymmetric P&L distribution: R2-A E winners average +0.512R; R2-A E losers average -1.550R. Per-ticker concentration: 4 of 7 tickers produce closed E winners (FRO/KOD/OII/RLMD); KOD+RLMD+TROX drive 36 of 40 closed E trades; NAT+SEI contribute zero closed trades (recent asof boundary 2026-05-08/12; insufficient forward bars for trigger search OR trail-exit).

**Cross-cohort consistency check (the load-bearing finding):**

| Cohort | Selection mechanism | N pat | E closed-and-profitable | E mean R closed | E 95% CI | E verdict |
|---|---|---|---|---|---|---|
| D2 Companion 2 canonical | bias-free S&P 500; recency<=120d | 26 | 3 | +1.208R | [+0.464R, +2.026R] | PARTIAL POSITIVE (degenerate) |
| D2 EXPANDED Amendment 5 | bias-free S&P 500; recency<=365d | 71 | 5 | +1.220R | [+0.753R, +1.704R] | PARTIAL POSITIVE (6 of 7 tests PASS) |
| **R2-A canonical** | **V2 binding-variable flips; recency<=365d** | **65** | **9 (22.5% wr)** | **-1.086R** | **[-1.377R, -0.782R]** | **NEGATIVE** |

**Cross-cohort verdict: COHORT-SPECIFIC**. D2 E's PARTIAL POSITIVE on bias-free cohort does NOT generalize to V2-binding-variable-selection-biased cohort. Per scenario row 2 of Turn G handoff brief §3.3: E appears to be cohort-specific to bias-free S&P 500 W's; V2-binding-variable mechanism selects tickers with intrinsically different P&L distributions. D2's bias-free PARTIAL POSITIVE remains valid for the specific S&P 500 universe it tested; D2 EXPANDED's 6-of-7 statistical defensibility holds intact. R2-A finding does NOT REFUTE D2's verdict on its own cohort; it **bounds the verdict's generalization scope**.

**D1 + R2-A directional consistency**: 5-ticker overlap between R2-A and D1 (KOD/NAT/OII/RLMD/TROX); 2 NEW vs D1 (FRO + SEI). D1's NEGATIVE-strict (7/12 triggered; 0 closed-and-profitable; -0.708R mean closed via DK + TROX close_below_50d) is DIRECTIONALLY CONSISTENT with R2-A NEGATIVE on the broader composite>=0.5 + recency<=365d filter. E does NOT save the 5 overlap tickers' poor P&L distribution.

**Cohort-validity discipline (gotcha #33 second canonical application):** R2-A held the canonical evaluation cohort FIXED at composite>=0.5 + recency<=365d (mirrors D2 Amendment 5 EXPANDED). Alternative scopes (composite>=0.7 -> N=17; recency<=60d -> N=13; recency<=120d -> N=21) documented at R2-A findings §5 but NOT used to substitute the verdict. Discipline observed throughout implementation + Codex chain.

**Discipline preservation**: ZERO Co-Authored-By footer drift (~553+ cumulative streak through `634cc9f`); L2 LOCK preserved + REINFORCED via 2 BINDING R2-A source-grep tests parametrized over r2a_tightness_days_required module set; Schema v21 UNCHANGED; ASCII discipline COMPLETE; ZERO new Schwab API calls (all 7 tickers use legacy `.parquet` files; V2 reader Shape A fallback to legacy); ZERO new yfinance fetches at backtest time (pre-flight refresh for FRO + NAT via yfinance `period='max'` on 2026-05-25 PM pre-dispatch); V1 persisted state ZERO writes; 39 R2-A fast tests pass; ~6111 broader project tests estimated (baseline ~6054 + 57 D2 + 39 R2-A = small overlap due to 4 R2-A file structure tests).

**Forward action sequence (orchestrator-side; Turn G FIRST SESSION housekeeping pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (8-commit chain; ZERO Co-Authored-By trailers; diff scope research-only; L2 LOCK 2 BINDING tests + 5 D2-cumulative tests preserved; 39 R2-A fast tests pass; cohort-validity discipline per gotcha #33 verified in manifest + findings doc + dispatch brief; cross-cohort comparison vs D2 + D1 documented in findings §2)
- [x] Merge `applied-research-r2a-tightness-days-required-cohort-backtest` `--no-ff` to main at `634cc9f` + push to origin/main
- [x] D2 findings Amendment 6 (cross-cohort consistency check; R2-A NEGATIVE on V2-binding-variable cohort bounds D2 EXPANDED PARTIAL POSITIVE generalization scope; gotcha #33 second canonical application; next-arc options banked)
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Operator-paired next-arc decision** post-R2-A SHIP. Options enumerated:
  - **Option C (real-time prospective tracking)** — banked V2 candidate from D2; validates D2's bias-free PARTIAL POSITIVE in forward deployment; appropriate now that cross-cohort generalization is BOUNDED (cohort-specific finding makes prospective tracking more valuable than additional historical backtests on artificial cohorts)
  - **R2-C** different chart-shape detector (cup_with_handle / flat_base) on D2's bias-free S&P 500 cohort + 6-ruleset comparison — tests whether ANY chart-shape × E ruleset combination generalizes; tests whether E's success is W-bottom-specific OR chart-shape-agnostic
  - **R2-D** different V2 binding variable (`vcp.adr_min_pct +11` / `vcp.proximity_max_pct +5` / `vcp.orderliness_max_bar_ratio +1`) — tests whether the cohort-specific-NEGATIVE pattern is unique to tightness_days_required OR systemic to all V2 binding variables; cost: ~4-6h implementer + ~1-2h Codex (harness REUSED again)
  - **D + E hybrid ruleset** — combines D's BE arm + tight trail with E's measured-move target hit; banked V2 candidate; cost: ~2-4h implementer
  - **Phase 14 commissioning consideration** — gated on cross-cohort robustness establishment; R2-A's cohort-specific finding indicates premature for E specifically (NOT established for any single ruleset across cohorts)
  - **Temporal wait** — 1-3 months for data tail to advance + EXPANDED-cohort re-run for N>=10 bootstrap defensibility; zero work; sequential-evidence path
  - **Pivot to market-conditions investigation** per CLAUDE.md operator-paired next-arc enumeration

---

## 2026-05-25 PM #4 Turn F EXTENDED: D2 W-bottom ruleset comparison SHIPPED at `d7387b8` — FIRST substantive PARTIAL POSITIVE verdict in V2 -> D1 -> D2 arc (per Amendment 3 reclassification)

**D2 W-bottom ruleset comparison backtest SHIPPED 2026-05-25 PM #4** at `d7387b8` (integration merge of `applied-research-w-bottom-ruleset-comparison` via `--no-ff`; 9 commits = 5 implementation slices + 3 Codex MCP fix bundles + 1 docs commit; +7910 lines across 27 files; 5 NEW research/harness/w_bottom_ruleset_comparison/ modules + 1 MODIFIED swing/cli.py +78 lines OQ-13-mirror CLI carve-out + 6 NEW test files + 3 smoke artifacts + cohort CSV + findings + return report).

**Codex MCP adversarial-critic chain CONVERGED at R3 NO_NEW_CRITICAL_MAJOR after 3 rounds.** Cumulative: 0 CRITICAL + 6 MAJOR + 9 MINOR. ALL MAJORS resolved in-place OR ACCEPTED with rationale + scope clarification. Real defects Codex caught: R1.M1 Ruleset F session-6 OPEN gate pre-emption; R1.M2 F ATR14 None auto-fail; R1.M3 D/F trail check-then-raise ordering doc lock; R1.M5 manifest provenance + V1 source-ladder consistency; R2.M1 L2 LOCK scope clarification. **39th cumulative C.C lesson #6 validation NOTABLE.** 5 NEW pre-Codex review scope expansion candidates banked at return report §7.5 (banking discipline preserved).

**3 smoke artifacts emitted** (all post-Codex-R3-convergence):
- Primary recency-60d / composite>=0.7; **N=5**; 30 trade rows -- sample insufficient
- Companion 1 no-recency-filter / composite>=0.7; **N=89**; 534 trade rows -- structural-artifact reference cohort (old-W trivial-trigger mode per implementer §7.1 self-disclosure)
- Companion 2 recency-120d / composite>=0.5; **N=26**; 156 trade rows -- canonical evaluation cohort per Amendment 3

**2 DEVIATIONS banked + accepted** (per Codex R1.M4 + dispatch brief §1.2 step 3 implicit permission):
1. Asof schedule shifted from brief's Feb-Apr 2026 to Apr-May 2026 (production DB evaluation_runs start 2026-04-20; brief's dates pre-date production runs -> detector Stage-2 hard gate returns 'undefined' for ALL pre-2026-04-20 entries; verified empirically 0 verdicts at composite>=0.5)
2. Cohort size N=5 (Primary; composite>=0.7 + recency<=60d) vs brief expected N=50-200 (bias-free S&P 500 W-bottom population is structurally smaller; only 7 distinct tickers across 516-universe; 1.36% incidence: ON / HPE / OXY / DOW / MCHP / CNC / INTC)

**Canonical verdict per orchestrator Amendment 3 (post-merge housekeeping commit)**: **PARTIAL POSITIVE for Ruleset E (O'Neil cup-with-handle + Bulkowski measured-move target)** on Companion 2's N=26 cohort (3 closed-and-profitable / +1.208R mean R closed / 100% win-rate). PARTIAL POSITIVE directional for Ruleset D (1 winner / +1.685R; needs larger sample). Implementer's original POSITIVE classification on Companion 1 was technically correct per brief §6.5 criteria but Companion 1 is structurally artifact-driven (old-W trivial-trigger mode; entries with days_t2_to_asof of 1320-1577+ days; measured-move target trivially reachable on ancient W neckline observations). Per `feedback_orchestrator_qa_implementer_product` BINDING: orchestrator Amendment 3 reclassifies headline verdict from POSITIVE-on-Companion-1 to PARTIAL POSITIVE-on-Companion-2 (canonical evaluation cohort closest to brief's recency-filtered intent). D1's close-below-50d mis-calibration finding CORROBORATED on bias-free cohort (A and C close 5 each via close_below_50d at mean -0.143R; same mechanism as D1 Amendment 2 §11.4). E's measured-move target avoids SMA-exit family entirely.

**NEW CLAUDE.md gotcha #33 banked at THIS housekeeping (Expansion #17 candidate)**: Cohort-validity-vs-verdict-criteria distinction. Brief verdict thresholds that are CRITERION-based but COHORT-AGNOSTIC let an implementer technically meet thresholds on any cohort; verdict interpretation MUST validate the evaluation cohort actually tests the brief's research question. Pre-empt at writing-plans phase: bind verdict to canonical cohort definition + sample-insufficient escape hatch + cohort-substitution prohibition. BINDING for 40th cumulative validation onwards.

**Discipline preservation**: ZERO Co-Authored-By footer drift (~542+ cumulative streak through `d7387b8` + Amendment 3 commit); L2 LOCK preserved + REINFORCED via 2 BINDING tests; Schema v21 UNCHANGED; ASCII discipline COMPLETE; production swing/ scope = 77 lines (CLI subcommand only); V1 persisted state ZERO writes; ZERO new Schwab API calls; ZERO new yfinance fetches at backtest time.

**D1 -> D2 cohort overlap**: ZERO (operator-curation + detector-bias-free-selection select for different ticker populations).

**Forward action sequence (orchestrator-side; THIS Amendment 3 housekeeping pass)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (9-commit chain; ZERO Co-Authored-By; diff scope research-only; L2 LOCK + Schema + ASCII all preserved; 57 D2 fast tests + ~6111 total fast tests pass)
- [x] Surface verdict-interpretation concern to operator + ratify Option 4 (merge AS-IS + post-merge Amendment) at AskUserQuestion 2026-05-25 PM #4
- [x] Merge `applied-research-w-bottom-ruleset-comparison` `--no-ff` to main at `d7387b8` (preserving implementer's narrative verbatim)
- [x] Amendment 3 to findings doc + Amendment 3 to return report (reclassify canonical verdict; promote Companion 2 to canonical evaluation cohort)
- [x] CLAUDE.md gotcha #33 banked (cohort-validity-vs-verdict-criteria distinction; Expansion #17 candidate)
- [x] phase3e-todo new top entry (THIS pass)
- [ ] **Operator-paired next-dispatch direction decision** post-Amendment-3. Options enumerated:
  - **Option A**: Bootstrap CI on E's Companion 2 +1.208R mean (N=3 winners) before R2 dispatch. Quantifies statistical robustness of PARTIAL POSITIVE finding. Cost: 4-8 hours. If lower-bound at 95% confidence is positive, R2 dispatch defensible; if not, hold pending more data.
  - **Option B**: R2 path per-variable cohort smoke + 6-ruleset backtest for `vcp.tightness_days_required +16` (next-largest binding variable). Tests whether E's PARTIAL POSITIVE generalizes to other chart shapes. Now WITH cohort-validity discipline per gotcha #33: canonical evaluation cohort MUST be recency-filtered. Cost: 8-16 hours.
  - **Option C**: Real-time prospective tracking for E on operator's pipeline outputs. Validates historical-backtest result in forward deployment. Operator-only after setup; multi-month timeline.
  - **Option D**: Phase 14 commissioning consideration for E's measured-move target as production trade advisory. Premature without bootstrap + R2 validation; deferred.
  - **Option E**: D + E hybrid ruleset (D's BE arm + tight trail UNTIL E's measured-move target hits). Combines downside-protection with target-based capture. Cost: 2-4 hours; reuses D2 harness.



**V2 OHLCV reader asof_date str-vs-date type coercion fix SHIPPED 2026-05-25 PM** at `1dc15f8` (integration merge of `applied-research-v2-reader-asof-date-str-coercion-fix` via `--no-ff`; 3 commits per TDD slice = RED `f7e816b` + GREEN `c5612be` + docs `94447c8`; +297 lines / -2 lines / 3 files; return report at `docs/v2-reader-asof-date-str-coercion-fix-return-report.md`).

**Fix scope (per dispatch brief §1.2 + §1.3 LOCK):** Reader-side boundary coercion at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:read_yfinance_shape_a_sliced`. Widened parameter type `asof_date: date → date | str`; coerce str via `date.fromisoformat` at function entry; re-raise malformed ISO inputs as `OhlcvCoverageError` so callers' broad try/except shape stays consistent with other reader failure modes (missing-archive + below-min-bars).

**Tests**: 3 NEW discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` per brief §2.1-2.3 (str-input positive path + malformed-ISO error wrap + date↔str equivalence regression-defense). 17/17 reader tests green (existing 14 + 3 new); 411 research fast tests green; 1 skipped (env-var-guarded). L2 LOCK preserved + REINFORCED (5 BINDING tests still green; no new imports / file-open paths / module dependencies).

**Discipline preservation:** ZERO Co-Authored-By footer drift (~530+ cumulative streak preserved through branch HEAD `94447c8` + merge `1dc15f8`); ZERO production swing/ writes; Schema v21 unchanged; ZERO new Schwab API calls; reader-side defense-in-depth at boundary per §1.2 LOCK; no new typed exception class per §1.3 LOCK. Codex MCP NOT invoked per pre-dispatch operator-paired decision; 38th cumulative C.C lesson #6 validation slot REMAINS RESERVED.

**Bug #3 NEWLY EXPOSED (gotcha #29 banked at THIS housekeeping):** Post-fix smoke at `exports/research/pattern-cohort-detection-20260525T190514Z/` STILL shows 100% `template_match_score=(none)` for a SEPARATE reason — all 13 unique exemplar tickers' legacy parquet archives start 2021-05-18 (yfinance default 5y window from operator's Turn E inline pre-fetch); ALL exemplar `end_date` values per `pattern_exemplars` are 2017-2021 (e.g., SNAP 2020-09-30, AMD 2018-08-31, NVDA 2017-03-30). ALL exemplar end_dates PRE-DATE the archive's first bar. Reader correctly raises `OhlcvCoverageError: sliced=0 < min_bars=1` (graceful, expected); `detector_invoker.py:201` swallows the per-exemplar failure (correct per cumulative T2.SB5 isolation discipline); template Pass 2 still no-ops with empty `bundles_by_class`. This is gotcha #28 family extended from archive-MISSING-ENTIRELY to archive-PRESENT-but-DEPTH-INSUFFICIENT. **NEW gotcha #29 banked at CLAUDE.md** at THIS housekeeping (BINDING for 39th cumulative validation onwards). Two-bug-chain (type-bug + depth-bug) was OBSERVATIONALLY INDISTINGUISHABLE pre-fix because both manifested as 100% `template_match_score=(none)`; only sequential remediation surfaced the second bug. Forward-binding lesson per gotcha #29: stage-by-stage counter discipline at manifest level is required when verifying a fix unblocks a multi-stage code path (load → match → emit).

**Substantive smoke findings (independent of all 3 template-Pass-2 blockers):** The geometric-score-only per-class breakdown from any of the 3 smoke runs reveals the +67 cohort is DOMINATED by `double_bottom_w` (2659 windows at composite>=0.5 = 30.7%; 670 at >=0.7; max 0.933) NOT `vcp` (128 at >=0.5 = 1.5%; 55 at >=0.7; max 0.857). **Operator's "Phase 13 detector over-filters loosened-A+ candidates" hypothesis FALSIFIED in instructive way**: Phase 13 detectors do NOT over-filter; they correctly identify the loosened-A+ cohort as the WRONG SHAPE for VCP analysis. Loosening `vcp.tightness_range_factor=1.005` admits double-bottom-w patterns into the numerically-A+ bucket. This explains the V2 OHLCV backtest's 29% breakout rate at merge `e0a9edd` — wrong entry rules (close > pivot) for the underlying chart shape (W-bottom recovery).

**Forward action sequence (orchestrator-side; remaining Turn F)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (verified branch HEAD `94447c8`; 4-commit chain; ZERO Co-Authored-By trailers; diff scope research-only; L2 LOCK 5 BINDING tests preserved; smoke artifact left untracked per brief §3.3 default).
- [x] Merge `applied-research-v2-reader-asof-date-str-coercion-fix` `--no-ff` to main at `1dc15f8`.
- [x] Post-merge housekeeping bundle THIS pass (CLAUDE.md gotcha #29 banked at file tail + phase3e-todo NEW top entry + [x] marks on cohort CSV + first-cohort smoke run lines).
- [x] **Operator decision on bug #3 (archive depth-insufficiency) handling**: Option (a) operational fix LOCKED at Turn F session re-engagement. Orchestrator-executed inline at `tmp/bug-3-exemplar-ohlcv-deep-fetch.py` (yfinance `period="max"` for 13 exemplar tickers; results: SNAP 2017-03-02+ / AMD 1980-03-17+ / TGT 1973-02-21+ / NVDA 1999-01-22+ / etc.; all 13 first_dates verified < earliest pattern_exemplars.end_date). Path-mismatch discovered + corrected mid-iteration (prices_cache underscore vs prices-cache hyphen — banked as L8 / method-record L6).
- [x] **Turn F A: smoke output tracking** SHIPPED at commit `9ee4e71`. .gitignore amendment per `exports/diagnostics/` pattern (negate broader exports/research/ exclusion for pattern-cohort-detection-<iso>/*.{summary.md,manifest.json}; results.csv excluded due to ~275 MB GitHub limit; substantive trail preserved via summary + manifest). 3 prior smoke runs committed (164425Z + 175553Z + 190514Z) for bug-discovery-sequence traceability.
- [x] **Turn F B: study writeup Results-section amendment** at `research/studies/2026-05-24-pattern-cohort-detection.md`: SHIPPED THIS pass (replaces PLACEHOLDER Results with actual headline + drill-down + S4 chart-shape MISMATCH scenario added to Interpretation + 3 reframing options R1/R2/R3 + L7 three-bug-chain + L8 cache_dir path-naming-convention + Conclusion ratifying promotion-gate conditions 1+2+3 SATISFIED with condition 4 PENDING operator review + Amendments section documenting the Turn F bug-chain). Method-record bumped v0.1.0 → v0.1.1 with mirror L5 (exemplar OHLCV provisioning per gotchas #28+#29) + L6 (cache_dir path) added.
- [x] **Post-bug-#3-fix smoke artifact**: `exports/research/pattern-cohort-detection-20260525T201617Z/` (runtime 22.5 min / 1350s; 43,370 verdicts; template_match_score populated; substantive verdict UNCHANGED from geometric-only — double_bottom_w dominant 2665+86 / vcp minor 167+63; template Pass 2 refined composite distribution with vcp +30% relative at >=0.5 / max_composite 0.8571 → 0.8799 the largest relative shift). Cohort is chart-shape DOMINATED by double_bottom_w not VCP; operator's "Phase 13 over-filters" hypothesis FALSIFIED in instructive S4 chart-shape MISMATCH way. Tracks via gitignore exception THIS commit.
- [x] **Turn F D1: double_bottom_w-specific backtest dispatch** SHIPPED at merge `99b672d` 2026-05-25 PM (9 commits: 5 implementation slices + 4 Codex fix bundles; +10148 lines; 5 NEW research/harness/double_bottom_w_backtest/ modules + 1 MODIFIED swing/cli.py +80 lines OQ-13-mirror CLI carve-out). **Codex MCP adversarial chain CONVERGED at R4 NO_NEW_CRITICAL_MAJOR** (0C + 14M + 11m cumulative; ALL 14 majors RESOLVED in-place; ZERO accepted-as-rationale). **38th cumulative C.C lesson #6 validation NOTABLE**; 5 NEW pre-Codex review scope expansion candidates banked (Expansions #14 + #15 + #16 promoted to CLAUDE.md gotchas #30 + #31 + #32 at THIS housekeeping; Expansion candidates #17 + #18 banked at return report §7.5 + applicable for future validations). 57 D1 fast tests / 6054 total / 2 skipped / 0 failed. **Substantive verdict NEGATIVE strict** (7/12 triggered = 58.3%; 0 closed-and-profitable; -0.708R mean closed via DK + TROX close_below_50d); **R1 hypothesis PARTIALLY VALIDATED + PARTIALLY REFUTED** (trigger-rate component DIRECTIONALLY SUPPORTED at +98% relative vs V2 baseline's 29%; profitability REFUTED via 0 closed-and-profitable). Recommended next dispatch options at return report §9.4: (A) pivot to `vcp.tightness_days_required +16` cohort smoke + backtest per R2 (~8-16h); (B) operator-paired archive refresh + D1 re-run (~30 min); (C) market-conditions investigation (substantial). Primary smoke at `exports/research/double-bottom-w-backtest-20260525T123753Z/` (36 trade rows; 27-column CSV); companion no-recency at `20260525T123756Z/` (516 trade rows).
- [x] **Turn F arc CLOSURE 2026-05-25 PM** — Turn F sequence A+B+D1+bug-#2-fix+bug-#3-fix COMPLETE end-to-end across 8 cumulative commits (`43c84ae` → `99b672d`): bug #2 fix brief + merge / housekeeping with NEW gotcha #29 / A gitignore + 3 smoke runs / bug #3 operational fix + B amendment + post-fix smoke + method-record v0.1.1 / D1 brief + merge + housekeeping with NEW gotchas #30 + #31 + #32. **SECOND Applied Research arc post-Phase-13-FULLY-CLOSED post-Option-D-3-phase-arc COMPLETE end-to-end** (THIRD substantial sub-arc post-Phase-13). ~530+ cumulative ZERO Co-Authored-By trailer drift preserved. THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments cumulative discipline signal preserved (Option D arc). Schema v21 LOCKED through entire Turn F. L2 LOCK preserved + REINFORCED multiple times. **R1 hypothesis verdict ratified**: chart-shape-appropriate trigger rules are NECESSARY but NOT SUFFICIENT for actionable expectancy on the V2 OHLCV cohort.

---



**V2 OHLCV criterion-evaluator harness EXECUTING-PLANS SHIPPED 2026-05-23 #3** at `a43a921` (integration merge of `applied-research-v2-ohlcv-criterion-evaluator-executing-plans` via `--no-ff`; 44 implementer commits = 5 sub-bundle tasks T-V2.1..T-V2.5 + 10 Codex MCP fix bundles R1-R4 + 1 return report). **THIRD of three Applied Research Tranche 1 arc commits** (brainstorming SHIPPED at `362fe18` 2026-05-23; writing-plans SHIPPED at `34f177c` 2026-05-23 #2; executing-plans SHIPPED THIS pass). **FIRST Applied Research arc post-Phase-13-FULLY-CLOSED is now COMPLETE end-to-end.** Return report at `docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md`.

**Codex MCP adversarial-critic chain converged at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (R1: 1C/4M/1m; R2: 0C/2M/1m; R3: 0C/1M/1m; R4: 0C/1M/0m; R5: 0C/0M/1m; **1 CRITICAL + 8 MAJOR + 4 MINOR cumulative; ALL CRITICAL + MAJOR RESOLVED in-place via 10 fix commits**; 1 R5 MINOR banked as V2 candidate). **Codex caught REAL defects against actual production code** — notable: R1.C1 `classify_candidate_tier` docstring-vs-implementation drift (TT-gate skip candidates with `risk_result=None` misclassified as tier-2 instead of tier-1; affected baseline parity attribution for LARGEST candidate subset in any real universe); R1.M1 `substitute_cfg` had no range validation; R1.M2 baseline parity counter inflation by factor of N_variables=17 (per-variable accumulation when should be per-candidate; arithmetic bug); R1.M3 per-ticker OHLCV cache architecture broken (`build_eval_run_cohort` read parquet directly via `read_yfinance_shape_a_sliced` for every (eval_run, universe ticker) pair, bypassing the cache claim; would multiply I/O cost ~63x on full operator run); R2.M2+R3.M1+R4.M1 flip-attribution provenance 3-instance cascade (FlippedCandidate.variable_name missing → drill-down recording elided post-fix → old_bucket comparing wrong baseline post-fix).

**5 NEW writing-plans-phase patterns banked at return report §4** (per cumulative V1-simplification discipline; each cites a discriminating-test pattern):
1. Tier classification semantics under spec ambiguity — when a docstring documents a richer semantic than the code implements, treat the docstring as the BINDING contract and audit all callsites against the docstring (Codex R1.C1).
2. Counter-double-counting risk in variable-sweep loops — when extracting baseline computation from a per-variable loop, audit ALL counters that accumulate inside the loop (Codex R1.M2).
3. Cache architecture full-graph audit — when claiming "per-X cache" architecture, audit ALL callsites that read X to verify the cache wraps them all (Codex R1.M3).
4. Flip attribution provenance — when a dataclass represents an outcome with attribution metadata, ensure (a) field required for downstream rendering; (b) rendering uses the attribution field NOT a value-matching heuristic; (c) old_value source matches new_value source. 3-instance lesson across Codex R2.M2 + R3.M1 + R4.M1.
5. Cumulative regression cascade in adversarial-review fix loops — a single Codex MAJOR fix can introduce a NEW MAJOR finding in the next round; happened TWICE in this dispatch (R1.M2 fix → R3.M1; R3.M1 fix → R4.M1). Banked as Expansion #13 candidate.

**33rd cumulative C.C lesson #6 validation NOTABLE** — pre-Codex orchestrator-side + implementer-side reviews + spec-compliance + code-quality reviewers applied ALL 7 expansions + 5 NEW candidate refinements + 2 NEW sub-refinements (#19 + #20) BINDING AND Codex still surfaced 1 CRITICAL + 8 MAJOR. **2 NEW Expansion sub-refinement REINFORCEMENTS**: Expansion #2 sub-refinement (#19) reinforced at R1.C1 — docstring-vs-implementation drift verification (docstring as BINDING spec contract); Expansion #4 sub-refinement (#20) reinforced at R1.M3 — dependency-injection-vs-direct-call audit for cache/wrapper architectures.

**3 NEW CLAUDE.md gotchas appended this housekeeping** (#21 + #22 + #23):
- **#21 NEW Expansion #13 candidate**: cumulative regression cascade audit in adversarial-review fix loops (BINDING for 34th cumulative validation onwards). When a Codex MAJOR is fixed by RESTRUCTURING code, the orchestrator-side post-fix review MUST include an "imagined Codex next-round" pass that audits the fix for second-order regressions BEFORE the next round invokes. Discriminating-test pattern: any post-fix commit that restructures control flow MUST include 2 layers of discriminating tests — (a) the original Codex finding's discriminating test; (b) tests for the NEW invariants the restructure creates.
- **#22 NEW Expansion #8 promotion**: per-counter-accumulation audit applies to ANY counter, not just SQL aggregates (BINDING for 34th cumulative validation onwards). Existing #9 (Expansion #8 SQL aggregation UNIT audit) was framed for SQL GROUP BY/COUNT/SUM, but V2's R1.M2 surfaced THE SAME arithmetic-unit-correctness failure mode in a Python variable-sweep loop. Pre-empt for any new counter accumulation (SQL aggregates AND Python loops): enumerate per-counter (a) what unit the counter is counting; (b) what loop/aggregation level the counter accumulates at; (c) verify counter increment is at the CORRECT unit level vs the intended unit; (d) post-extraction audit: if extracting a counter pass from a loop, audit that the extracted pass accumulates at the correct unit.
- **#23 NEW Expansion #11 promotion**: dataclass attribution metadata audit applies to ALL attribution-bearing dataclasses, not just enum-bearing (BINDING for 34th cumulative validation onwards). Existing #15 (Expansion #11 taxonomy propagation audit) was framed for enum-typed fields, but V2's R2.M2 surfaced THE SAME propagation-discipline failure for a NON-enum attribution metadata field (FlippedCandidate.variable_name). Pre-empt for any new dataclass with attribution metadata: enumerate per-attribution-field (a) is the field required?; (b) does ALL downstream rendering use the attribution field NOT a value-matching heuristic?; (c) for paired old/new fields, do `old_X` and `new_X` source from the SAME baseline?; (d) for chained-helper pipelines, does each layer preserve the attribution field through the chain?

**18 OQ dispositions LOCKED verbatim through brainstorming → writing-plans → executing-plans phases (ZERO amendments)** — strong validation signal for cumulative discipline.

**Discipline deviations BANKED at return report §3**:
- T-V2.2 single-commit mega-consolidation (1 commit for sweep.py + 18 tests vs §G.0 per-test cadence; substance verified; 5 fix commits subsequently restored proper artifact trail)
- OQ-17 line count 71 vs 35-60 target (V1-mirror patterns; no new scope)
- T-V2.4 minimal commits (2 vs ~10; TDD red phase committed separately so artifact trail preserved at coarser granularity)
- Partial implementer smoke (5 eval_runs / 120s cap / 516 universe / 351 candidates vs full operator 63 eval_runs / 5681 candidates; full operator reproduction enumerated in research/phase-0-tasks.md "Next")
- Closer commit message undercounted L2 LOCK tests (3 vs canonical 5; reconciled in study Amendments)

**Smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.{csv,md}` SURFACED REAL OPERATOR-ATTENTION FINDINGS**:
- **CRITERION DRIFT DETECTED — DK:62 BLOCKING Tier-1 parity FAIL**: V2 baseline (current-value sweep recompute) does NOT match V1 persisted for DK ticker at eval_run_id=62; investigation required BEFORE trusting V2 sensitivity results.
- 16 both-exist tickers warning (AESI + PL + DK among them; per-ticker affected list)
- No binding variables in partial smoke (delta_aplus == 0 across all 5 eval_runs / 351 candidates); full 63-eval-run reproduction needed for canonical operator-paired binding-variable identification.

**Tier-1 baseline parity invariant**: FAIL (DK:62 CRITERION DRIFT). **Tier-2 baseline parity reporting**: 30 match / 45 mismatch (surrogate-flagged; non-blocking per OQ-15).

Schema v21 UNCHANGED through executing-plans (ZERO files in `swing/data/migrations/`); 115 NEW V2 fast tests + 1 skipped env-var-guarded (315 V2 tests pass; broader project baseline 5778 + 115 = ~5893 estimate); ZERO new Schwab API calls (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` covering 4 file-open boundaries `pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table` + 4-module import sentinel graph `yfinance` + `schwabdev` + `swing.integrations.schwab` + `swing.data.ohlcv_archive`); ZERO production `swing/` writes beyond OQ-17 CLI carve-out (`git diff main -- swing/` shows ONLY `swing/cli.py` +71 lines for `diagnose aplus-sensitivity-v2` registration; mirror of V1 precedent at `swing/cli.py:4748-4787`); ZERO Co-Authored-By footer drift across all 44 branch commits + 1 merge commit (~492+ cumulative streak preserved per fresh forward-binding lesson #7 Phase 12 Sub-sub-bundle C.B 2026-05-15 discipline).

**Forward action sequence (orchestrator-side; THIS handback)**:

- [x] QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (verified against reality on disk: branch HEAD `2085546` (return report); 44-commit chain; ZERO Co-Authored-By trailers; diff scope clean; L2 LOCK 5 BINDING tests present in test file; git diff swing/ shows ONLY swing/cli.py)
- [x] Merge `applied-research-v2-ohlcv-criterion-evaluator-executing-plans` `--no-ff` to main at `a43a921` (handoff-brief revert reconciliation auto-resolved by git ort strategy — main's deletion taken since branch didn't oppose)
- [x] Post-merge housekeeping bundle THIS pass (CLAUDE.md line 3 refresh + 2 NEW gotchas #21 + #22 + #23 + phase3e-todo NEW top entry + orchestrator-context current state pivot + Prior demote + archive-split per size-check trigger archiving T3.SB3 container)
- [x] **DK:62 CRITERION DRIFT investigation SHIPPED 2026-05-23 #4** at merge `4afab36` (1-commit branch at `5a43508`; investigation findings doc + return report bundled). Root cause: **ARCHITECTURAL DATA-FRESHNESS DESYNC** between Shape A (`DK.yfinance.parquet` mtime 2026-05-21 07:39; last bar 2026-05-20) + legacy (`DK.parquet` mtime 2026-05-21 20:28; last bar 2026-05-21 Close=42.10 -5.7% intraday drop). V1 evaluated with boundary bar (canonical); V2 reads stale Shape A and misses it (2 criterion flips TT5_above_50 + proximity_20ma promote skip→watch incorrectly). 4 hypotheses: H1+H2+H4 FALSIFIED via git log + cfg audit + V1 audit-trail review; H3 characterized as ARCHITECTURAL not V2-code bug (V2 per-spec correct per OQ-18). Drift scope ISOLATED to DK:62 (3 both-exist tickers cache-wide; only DK Shape A stale; only eval_run 62 lands on missing date; 822 legacy-only tickers unaffected). **Counter-test confirmed V1 canonical**: evaluate_one with legacy bars reproduces V1 bucket=skip + every criterion value EXACTLY. **NEW CLAUDE.md gotcha #24 banked** (parallel-archive freshness desync invalidates baseline-parity claims for V2-style readers that consume ONE of two parallel archive shapes; BINDING for 34th cumulative validation onwards). 5 forward-binding lessons banked at investigation §5.
- [x] **OPTION D REMEDIATION (Turn D inline 2026-05-24)** per investigation §4:
  - [x] (D.1) **Shape A refresh** for the 3 both-exist tickers (AESI/DK/PL) via Turn D inline `resolve_ohlcv_window` invocation 2026-05-24: DK Shape A refreshed (mtime May 21 07:39 → May 24 06:06; 1260 → 1262 rows; 2026-05-21 boundary bar now present at Close=42.10); AESI + PL Shape A already current (idempotency-skipped).
  - [x] (D.2) **V2 smoke re-run** via Turn D inline `swing diagnose aplus-sensitivity-v2 --eval-runs 5 --max-runtime-seconds 120` 2026-05-24; smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.{csv,md}`: **DK:62 RESOLVED ✓** (no longer in CRITERION DRIFT list); tier-2 dramatically improved (75/45 → 10/0 fully consistent); BUT 15 NEW tier-1 drift entries surfaced (DHC/UCO/VSAT × eval_runs 60-64) hidden by pre-R3.M1 buggy flip-recording — anticipated by DK:62 investigation §5.3 lesson #3.
- [x] **SECOND INVESTIGATION DHC/UCO/VSAT × 60-64 SHIPPED 2026-05-24** at merge `d7cdd51` (1-commit branch at `019dc6e`; investigation findings doc + return report bundled). Root cause: **V2 HARNESS FALSE-POSITIVE** at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605` (`_compute_baseline_parity`); NOT V2 evaluator bug. V1 production at `swing/pipeline/runner.py:1105-1141` short-circuits criterion evaluation for excluded-ticker classes (open positions + ETF blocklist) writing `bucket='excluded'` directly; V2 naively invokes `evaluate_one`; `bucket_for` returns only `{aplus, watch, skip}` — never `'excluded'`. Codex R1.C1 fix promoted these from silent tier-2 → BLOCKING tier-1 (15 entries have `risk_result=None` + 0 candidate_criteria rows). All 4 narrowed hypotheses (H1 reader / H2 RS universe / H3 OHLCV slicing / H4 BatchContext) FALSIFIED; H5 V2 harness comparison gap CONFIRMED. Decisive counter-test passed DHC:60 / UCO:62 / VSAT:64 (V2 returns skip/watch/skip matching smoke; **V2 EVALUATOR IS CORRECT**). Drift scope SYSTEMIC across open-position + ETF-blocklist populations (DHC/VSAT open trades; UCO sole ETF blocklist entry); ~100-200 entries projected at full 63-eval-run reproduction. **NEW CLAUDE.md gotcha #25 banked** (sentinel-bucket parity-comparison discipline; BINDING for 34th cumulative validation onwards).
- [x] **OPTION A FIX SHIPPED 2026-05-24** at merge `b7f70ff` (4 fix/test/smoke commits + 1 return report at `b92bf87`; branch `applied-research-v2-baseline-parity-excluded-filter`): +17 lines in `_compute_baseline_parity` (1-line filter `if cand_row.persisted_bucket in {"excluded", "error"}: continue` + 13-line comment block citing gotcha #25 + investigation source-of-truth); 3 NEW discriminating tests at `tests/research/test_aplus_v2_ohlcv_sweep.py` (open-position-and-blocklist + error-bucket + negative-control); Fix #3 drill-down COUNT filter DEFERRED V2-candidate per implementer analysis that flip-recording is already transitively prevented via `baseline_bucket_map.get is None` guard; Codex MCP NOT invoked per operator-paired choice; 34th cumulative C.C lesson #6 validation CLEAN; 0 NEW gotchas; gotcha #25 first canonical application; ZERO production swing/ writes; ZERO V1 changes; L2 LOCK preserved (14 reader tests still green); ~501+ ZERO Co-Authored-By streak preserved.
- [x] **V2 smoke re-run (post-Option-A) — Tier-1 FULL PASS verified** at `exports/diagnostics/aplus-sensitivity-v2-20260524T181554Z.{csv,md}` (5 eval_runs / 121s runtime / 516 universe / 351 candidates; 15 false-positive entries → 0; CRITERION DRIFT DETECTED section OMITTED entirely; tier-2 unchanged at 10/0; sensitivity matrix counts identical; both-exist banner AESI/DK/PL unchanged orthogonal).
  - [x] (D.3) **Method-record amended v0.2.0 → v0.2.1 at commit `58e6879` 2026-05-24** (inline doc edit per operator decision; +34/-4 lines): frontmatter bump + NEW "Known limitations of V2 baseline-parity claims (v0.2.1 addendum)" subsection added within "V2 OHLCV harness shipped" section. **L4 (parallel-archive freshness desync per investigation `4afab36` §5.4 + gotcha #24)** + **L5 (V2 harness sentinel-bucket filter discipline per investigation `d7cdd51` §5.3 + gotcha #25 + Option A fix `b7f70ff`)** entries with full per-Limitation evidence + remediation citations. Promotion criteria research→shadow condition 1 SATISFIED claim REINFORCED via L4 D.1 + L5 Option A remediation citations.
  - [x] (D.4) **V2 candidates banked at D.3 amendment (absorbed into L4 + L5 entries):** (a) V2 reader "prefer-fresher of (Shape A, legacy)" by mtime tiebreaker (V2.5/V3; in L4 banked candidate); (b) sentinel-bucket parity-comparison discipline as research-branch BINDING template for future V1-vs-V2 parity harnesses (in L5 banked candidate); (c) Fix #3 drill-down COUNT filter extension (in L5 banked candidate; default recommendation FILTER per investigation §9.3).
- [x] **Full 63-eval-run operator reproduction SHIPPED 2026-05-24 PM** at smoke `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}` (86 min runtime / 5172s / not truncated / 63 eval_runs ids 2..64 / 5666 candidates / 516 universe / 88 OHLCV coverage skips / tier-2 clean 120/0). **5 BINDING VARIABLES IDENTIFIED — all VCP-family**: `vcp.tightness_range_factor` +75 / `vcp.tightness_days_required` +16 / `vcp.adr_min_pct` +11 / `vcp.proximity_max_pct` +5 / `vcp.orderliness_max_bar_ratio` +1. 14 tier-1 drift entries surfaced (CNTA × 2 + ECVT + APLS × 3 + FTI × 2 + STNG × 3 + PL × 3 spanning eval_runs 6-43).
- [x] **Third investigation SHIPPED 2026-05-24 PM** at merge `c8f9612` (branch `applied-research-v2-full-reproduction-drift-triage`; 1 investigation commit + findings doc 539 lines + return report 183 lines): **H6 NEW root cause CONFIRMED** = OHLCV archive bar-content TEMPORAL mutation between V1's eval_run persistence time + V2's current-archive read time (`swing/data/ohlcv_archive.py:write_window:358-360` drop_duplicates `keep='last'` semantics; intervening pipeline runs progressively overwrite historical bars when yfinance returns slightly different values from late-reporting + retroactive adjustments). All 5 narrowed hypotheses (H1 L4-extension / H2 OQ-14 / H3 source-ladder / H4 L5-extension / H5 coverage threshold) FALSIFIED with concrete evidence. Per-criterion divergence: 11/14 vcp_volume_contraction (V2 cons_avg +0.62% to +2.65% higher); 3/14 (PL only) tightness (V2 0-day streak vs V1 2-day streak). Decisive counter-test reproduces V2's bucket='skip' EXACTLY for all 14 → **V2 evaluator CORRECT given inputs** (THIRD investigation confirming V2 evaluator correctness after DK:62 + DHC/UCO/VSAT). Drift L4-style; 14 candidates flip skip→watch (NOT skip→aplus); max_delta_aplus UNAFFECTED; **all 5 binding variables ROBUST**. **Study publication UNBLOCKED** with caveat language at investigation findings §5.4.
- [x] **Post-investigation housekeeping bundle THIS pass** (sub-event scale; in-place amendments): CLAUDE.md line 3 current state pivot (DOUBLE → TRIPLE-INVESTIGATED + L6-CHARACTERIZED) + Note 2026-05-24 PM (e) entry + NEW CLAUDE.md gotcha #26 (archive bar-content TEMPORAL mutation; complements #24 + #25 — three-piece V1-vs-V2 parity discipline family); method-record v0.2.1 → v0.2.2 with NEW Limitation L6 + Promotion criteria research→shadow condition-1 OPERATOR-PAIRED interpretation note + condition-3 SATISFIED; orchestrator-context.md Last-updated header bumped + "Currently in-flight" amended; phase3e-todo top entry [x] marks.
- [x] **Operator decision D1 LOCKED 2026-05-24 PM** (research → shadow promotion gate condition-1 interpretation): option (a) — "baseline parity green to the extent V2 evaluator's correctness is verifiable against V1, with 3 documented L4 + L5 + L6 architectural limitations" → **gate SATISFIED on all 3 conditions**. Method-record promoted research → shadow (v0.2.2 → v0.3.0) at commit `c672af1`. V2 evaluator correctness verified 3x via decisive counter-tests across DK:62 + DHC/UCO/VSAT + full-reproduction investigations. Banked V2.5/V3 candidate (option b path): immutable archive snapshot before V2 run to eliminate L6 temporal-mutation drift class.
- [x] **Operator decision D2 LOCKED 2026-05-24 PM** (study writeup amendment vehicle): inline edit at commit `c672af1`. Study writeup updated at `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`: status header refreshed (harness shipped + full-reproduction SHIPPED + method-record SHADOW + 3 architectural limitations); operator full-reproduction findings section REPLACED implementer-smoke section (authoritative); 15 TBD threshold-variable rows + 2 gate rows REPLACED with full-reproduction data; Conclusion section populated with 5 binding variables ranked by max_delta_aplus + substantive finding (VCP-family threshold relaxation is most-actionable lever) + bidirectional sensitivity + catastrophic gate edge behavior + forward-action sequence; NEW Amendment 2 appended (full-reproduction + 3-investigation arc completion).
- [x] **V2 `vcp.tightness_range_factor=1.005` walk-forward backtest SHIPPED 2026-05-24 PM** at merge `e0a9edd` (4 commits; 6 backtest modules + 16 fast tests; 3 exit rulesets executed; +1987 lines of analytical surface). **NEGATIVE cfg-policy substrate verdict**: of 17 unique VCP patterns from 67 watch→aplus flips, only 5 triggered breakout (29% rate); 10 reached only 86-99% of pivot (genuine no-breakout); 0 closed trades; mean unrealized R = -0.18R across 5 open positions. All 3 exit rulesets (Minervini trail-MA / Fixed R / Close-below-50d) emit IDENTICAL pattern-level outcomes (post-trigger divergence never fires). Cross-cohort control: baseline 0.67 cohort 2 patterns / 1 triggered (50% rate) / 1 open. **Substantive lesson**: V2 classification +75 max_delta_aplus headline does NOT equal +75 actionable trades — breakout-trigger conversion is a separate gating mechanism upstream of pattern verification. **Operator hypothesis** (Phase 13 pattern detector over-filters loosened candidates) remains UNTESTED — the cohort dies at the breakout-trigger stage BEFORE pattern verification can apply. L6 archive-mutation impact: ZERO (none of 14 L6-drifted tickers intersect this cohort). Findings at [`docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md`](docs/v2-tightness-range-factor-backtest-findings-2026-05-24.md); return report at [`docs/v2-tightness-range-factor-backtest-return-report.md`](docs/v2-tightness-range-factor-backtest-return-report.md); study writeup amended with "Walk-forward backtest validation" section.
- [x] **Stage 2 detector-confirmation reconnaissance SHIPPED 2026-05-24 PM** (orchestrator-side ad-hoc query at `tmp/stage2_detector_confirmation_query.py`): pattern_evaluations table EMPTY (0 rows across 78 pipeline runs). Surfaced unexpected operational finding → triggered Path A investigation dispatch.
- [x] **Phase 13 `_step_pattern_detect` silent no-op investigation SHIPPED 2026-05-24 PM** at merge `54bd9c6` (1 commit at `e02463b`; 2 docs / +385 lines; diagnostic-only). Root cause: **H7 NEW (expanded from brief's 6-hypothesis space per superpowers Phase 1.4)** — empty-pool early-return at `swing/pipeline/runner.py:1485-1490`; detector gated on `bucket == 'aplus'`; ZERO aplus across 7 post-T2.SB3 runs (brief framing 78 runs CORRECTED to 7 post-ship). Detector code itself FULLY OPERATIONAL (BULZ.high_tight_flag scored 0.667 in direct invocation). H5 confirmed CONTRIBUTING (silent-skip-without-audit operational gap). **CRITICAL ARCHITECTURAL INSIGHT**: Phase 13 production detector by design only runs on bucket='aplus' candidates → operator's earlier hypothesis (Phase 13 detector over-filters loosened-A+ candidates) cannot be tested via production pipeline because production detector never sees non-aplus candidates. NEW CLAUDE.md gotcha #27 banked (silent-skip-without-audit pattern in pipeline steps). 4 remediation options enumerated.
- [x] **Operator decisions 2026-05-24 PM**: (1) pursue Option A + D; (2) promote gotcha #27 to CLAUDE.md; (3) concur on brief-framing accuracy lesson to orchestrator-context.md.
- [ ] **Option A dispatch**: ~10-15 line warnings_json visibility patch at `swing/pipeline/runner.py:1485-1490` per investigation §6 banked candidate. Small operator-approved production code fix; emits pattern_detect step outcome to warnings_json when pool is empty (silent-skip becomes operator-visible). Addresses H5 contributing cause; does NOT address H7 root cause. Generalization: brief should also enumerate ALL existing pipeline steps with early-return guards + extend warnings_json discipline per gotcha #27 pattern. Branch suggestion: `swing-pipeline-pattern-detect-warnings-json-visibility-fix`.
- [x] **Option D Phase 1 brainstorming SHIPPED 2026-05-24 PM** at merge `18cb49e` (2 commits at fb5522a + ddd2756; 996-line spec at `docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md` + 187-line return report; 14 sections + 13 OQs). Operator-paired Turn D triage 2026-05-24 PM: **ALL 13 OQ dispositions LOCKED verbatim with ZERO amendments** (mirrors V2 OHLCV brainstorming's 18-OQ-LOCKED precedent; strong cumulative discipline signal). Codex MCP NOT invoked at brainstorming per operator-paired discretion (38th cumulative C.C lesson #6 validation slot reserved for writing-plans / executing-plans). Architectural answer to operator's research question about Phase 13 detector filtering performance.
- [x] **Option D Phase 2 writing-plans SHIPPED 2026-05-24 PM** at merge `4d8b35e` (2 commits at 69bb89d + 3d25c79; 2948-line plan + 240-line return report). ALL 13 brainstorming OQs LOCKED + carried forward verbatim with ZERO amendments (mirrors V2 OHLCV 18-OQ-LOCKED precedent; TWO-IN-A-ROW operator-triage discipline). 1 plan-phase disposition at §I.3: `--max-runtime-seconds` V1 DEFERRED → V2.5+ candidate. 6 NEW research/ modules + 1 MODIFIED `swing/cli.py` per OQ-13. 5 BINDING L2 LOCK discriminating tests at plan §F + §K. 8 production functions verified via inspect.signature + typing.get_type_hints + cascade-call-graph audit per gotchas #17 + #19. 5 sub-bundles (T-PC.1.1 + T-PC.1.2 + T-PC.2 + T-PC.3 + T-PC.4 + T-PC.5); ~56-67 commits projected; ~61 fast tests (~50-55 parametrize-consolidated; baseline ~5893 → ~5944-5954 post-ship). Codex NOT commissioned (38th C.C lesson #6 validation slot reserved for Phase 3). Operator-paired plan review default = ZERO amendments per V2 OHLCV precedent.
- [x] **Option D Phase 3 executing-plans SHIPPED 2026-05-25** at merge `eddeb73` (6 sub-bundle commits 4b9f185 + 665058e + 7a3db9c + ecf75a8 + 7b87309 + 58d1830; +4069 lines across 18 files; 6 NEW research/harness/pattern_cohort_evaluator/ modules + 1 MODIFIED swing/cli.py +84 lines OQ-13 sole carve-out + 6 NEW test files + method-record v0.1.0 + study writeup + return report). 80 NEW tests (79 pass + 1 skip pending operator cohort CSV). **THREE-IN-A-ROW OQ-LOCKED-with-ZERO-amendments cumulative discipline signal** (brainstorming 13/13 + writing-plans 13/13 + plan-phase 1/1 + executing-plans 14/14 preserved). Codex MCP NOT commissioned at executing-plans per operator-paired discretion (38th cumulative C.C lesson #6 validation slot REMAINS RESERVED). Discipline deviations BANKED in merge commit (6 vs ~56-67 commits per-sub-bundle consolidation; +84 vs 35-60 CLI line count; 80 vs ~50-55 tests). **SECOND Applied Research arc post-Phase-13-FULLY-CLOSED COMPLETE end-to-end** (mirrors V2 OHLCV three-phase precedent).
- [x] **Operator-paired cohort CSV substrate authoring**: SHIPPED 2026-05-25 at commit `71e59f5` (67 entries; 15 unique tickers; 16 unique asof_dates; tracked via gitignore exception at exports/research/cohorts/).
- [x] **Operator-paired first-cohort smoke run**: SHIPPED Turn E + Turn F (three smoke artifacts at `exports/research/pattern-cohort-detection-{20260525T164425Z, 20260525T175553Z, 20260525T190514Z}/`). All three runs exhibited 100% `template_match_score=(none)` for 43,370 verdicts each — but for THREE distinct upstream blockers progressively closed: (1) 164425Z = bug #1 exemplar OHLCV cache miss (operator inline-resolved via `read_or_fetch_archive` for 13 exemplar tickers; gotcha #28 banked); (2) 175553Z = bug #2 V2 reader str-vs-date TypeError (CLOSED at merge `1dc15f8` THIS Turn F; gotcha lineage cited inline); (3) 190514Z = bug #3 NEWLY EXPOSED archive depth-insufficiency (yfinance default 5y window covers 2021-05-18+ but exemplar end_dates are 2017-2021; gotcha #29 banked at THIS housekeeping). Substantive smoke findings from geometric-score-only verdicts (independent of all 3 template Pass 2 blockers): the +67 cohort is DOMINATED by double_bottom_w (30.7% windows at composite>=0.5; max 0.933) NOT vcp (1.5%; max 0.857). **Operator's "Phase 13 detector over-filters loosened-A+ candidates" hypothesis FALSIFIED in instructive way**: Phase 13 detectors correctly identify the loosened-A+ cohort as the WRONG SHAPE for VCP analysis — the loosening admits double-bottom-w patterns into the numerically-A+ bucket. Explains V2 OHLCV backtest's 29% breakout rate — wrong entry rules (close > pivot) for the underlying chart shape (W-bottom recovery).
- [ ] **Study writeup Results-section amendment**: append findings to `research/studies/2026-05-24-pattern-cohort-detection.md` post-smoke-run.
- [ ] **Research → shadow promotion gate review** per spec §K.3 + V2.1 §IV.D: 4 conditions enumerated; gate fires post first-cohort smoke + actionable-finding ratification.
- [ ] **Optional retroactive Codex MCP adversarial review**: 38th cumulative C.C lesson #6 validation slot available at any future inflection point.
- [ ] **Pivot-to-next-binding-variable decision** (after A + D land + assessed): alternatives banked from prior cfg-policy substrate triage: (a) pivot to `vcp.tightness_days_required +16` backtest; (b) market-conditions investigation per V2.1 §III; (c) Phase 14 commissioning per Path B; (d) execute originally-banked Stage 3 (AI second-opinion eval) on Option D's cohort-detector output if winners-without-detection cell is populated.
- [ ] **Periodic V2 OHLCV sensitivity re-run for long-term baseline-method trend analysis** (operator-banked 2026-05-24 PM). Rationale: V2 harness output is **independent of operator's personal trading execution** — running it on a recurring cadence produces a regime-independent baseline trend of (a) binding-variable stability (does `vcp.tightness_range_factor` stay the top binding variable across regime shifts? OR does the binding rank order shift?); (b) A+ candidate count baseline (are we generating more/fewer A+ candidates over time as universe + market conditions shift?); (c) sensitivity-matrix shape drift across cycles. **Frequency recommendation: quarterly** — aligns with broader market regime cycles + index reconstitution cadence; budget cost ~3-4 hours per cycle (1.5h harness runtime + 1.5-2.5h operator review of output / amendment to study writeup); ~12-16 hours per year. Monthly cadence consumes too much research budget (phase-0-tasks.md line 3 caps research at 1-2 hrs/week ≈ 50-100 hrs/year); semi-annual loses too much regime-shift resolution. Operator finalizes cadence. Each cycle produces a NEW smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}` + a delta-vs-prior-cycle entry in the study writeup `## Periodic re-run log` section (to be added on first cycle execution). L6 caveat applies to every cycle (each re-run reads CURRENT archive; expected; document but don't remediate). Synergistic with the cfg-policy proposal pathway — if cfg-policy lands a binding-variable threshold change, periodic re-runs validate the new policy's stability over time independent of operator's discretionary execution.
- [ ] Optional next-arc: cfg-policy method-record if binding thresholds identified post full-reproduction; OR pivot to market-conditions (cause 2) / other-gates-not-enumerated (cause 3) per spec §B.3 if all 15 declared non-binding with operator-paired sign-off; OR Phase 14 commissioning consideration per Path B sequencing post-V2-output review

---

## 2026-05-23 #2 Applied Research Tranche 1: V2 OHLCV criterion-evaluator harness WRITING-PLANS SHIPPED at `34f177c` — SECOND of three Applied Research Tranche 1 arc commits

**V2 OHLCV criterion-evaluator harness WRITING-PLANS SHIPPED 2026-05-23 #2** at `34f177c` (integration merge of `applied-research-v2-ohlcv-criterion-evaluator-writing-plans` via `--no-ff`; 8 implementer commits = initial plan at `ef66feb` + R1 fix at `21cc950` + R2 fix at `947552d` + R3 fix at `7b20fd4` + R4 fix at `08322ac` + R5 fix at `f39b62f` + R6 minor doc-drift sweep at `41831a7` + return report at `75a2649`). Plan at `docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md` (2602 lines NEW; 15 sections §A-§O including self-review). Return report at `docs/v2-ohlcv-criterion-evaluator-writing-plans-return-report.md` (191 lines NEW). **Codex MCP adversarial-critic chain converged at R6 NO_NEW_CRITICAL_MAJOR after 6 rounds** (R1: 0C/7M/2m; R2: 0C/3M/3m; R3: 0C/3M/2m; R4: 0C/2M/1m; R5: 0C/1M/3m; R6: 0C/0M/2m doc-drift sweep; **0 CRITICAL + 16 MAJOR + 13 MINOR ALL RESOLVED in-place**; ZERO accepted-as-rationale). **Codex caught real defects against actual production code** — notable: SQL IN-clause dynamic placeholder binding (R1.M1; sqlite3 cannot bind list to single `:name` placeholder; V1 precedent at `research/harness/aplus_sensitivity/sweep.py:89-95` uses dynamic `?` expansion); `cfg.archive` vs `cfg.paths` drift (R1.M2; actual config path is `cfg.paths.prices_cache_dir` per `swing/config.py:17+456`; `cfg.archive` only holds `archive_history_days`); L2 LOCK 4-module import sentinel + 4-boundary file-open mock (R1.M3+M4; spec spied only `pd.read_parquet`; missed indirect yfinance via `swing.data.ohlcv_archive` import at line 47 + 3 other file-open boundaries `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table`); `evaluate_one` return-annotation lock via `typing.get_type_hints` under postponed annotations (R1.M5; raw `inspect.signature(...).return_annotation` is STRING form under `from __future__ import annotations` at `swing/evaluation/evaluator.py:2`; MUST use `typing.get_type_hints` to resolve to class object); commit-cadence preface (R1.M6; original 1-commit-per-task = 7 commits violates brief §2.1 prescribed ~42-65; recalibrated to ~50-69 via parametrize-consolidation); test budget recalibrated +12 (R1.M7; ~68 → ~84); candidate-not-in-universe BatchContext returns (R2.M1; production `compute_rs` at `swing/evaluation/rs.py:65-85` returns `'fallback_spy'` not `'unavailable'` for ticker absent from universe but with returns data; TT8 at `swing/evaluation/criteria/trend_template.py:125-145` consumes that fallback; V2 plan now requires `candidate_tickers` param to `build_eval_run_cohort`); sqlite3 URI mode=ro hardening (R2.M2; V1 precedent uses plain `sqlite3.connect(str(db_path))` read/write; V2 plan now requires URI `mode=ro` for defense-in-depth — any accidental INSERT raises `sqlite3.OperationalError "attempt to write a readonly database"`); `Config.from_defaults` purity claim correction (R2.M3 + R3.M2; reads tracked `swing.config.toml` per `swing/config.py:399-407+437-438`; was claimed PURE; only `swing/cli.py` Click-handler entry points invoke `swing/config_overrides.py` user-config cascade); `horizon_weeks`-scaled `bars_needed` (R3.M1; `_RS_FALLBACK_MIN_BARS = 60` hardcoded — wrong for `rs.horizon_weeks=14` substitution which should be 70 trading days; production uses `bars_needed = horizon_weeks * 5` per `swing/pipeline/runner.py:1060-1077`); empty-eval-runs short-circuit (R3.M3; would generate `IN ()` invalid SQL post dynamic-`IN` fix; V1 precedent at `sweep.py:81` has explicit empty guard); empty-DB return shape consistency (R4.M2 + R5.M1; `v2_universe_hash="empty_no_eval_runs"` sentinel for required dataclass field on empty short-circuit return).

**5 NEW writing-plans-phase patterns banked at return report §4** (per cumulative V1-simplification discipline; each cites V2/V3 dependency or BINDING-template promotion candidate):
1. sqlite3 URI mode=ro hardening as defense-in-depth for any future research-branch harness reading operator's swing.db (consider promoting to research-branch BINDING pattern when 2nd research harness lands).
2. Dynamic `?` IN-clause expansion as cumulative pattern for ALL Python sqlite3 multi-row queries (consider adding to CLAUDE.md SQLite gotcha family alongside existing `INSERT OR REPLACE` cascade-wipe + `executescript` implicit-COMMIT lessons).
3. 4-boundary file-open mock + 4-module import sentinel pattern as cumulative L2 LOCK reinforcement template (consider promoting to BINDING template for any future research-branch arc that touches OHLCV archive).
4. `typing.get_type_hints` over `inspect.signature` for return-annotation locks under `from __future__ import annotations` (Python 3.10+) — consider extending Expansion #2 refinement (NEW gotcha #17) to mention this postponed-annotation interaction.
5. Empty-result-set short-circuit + `v2_universe_hash` sentinel pattern as harness empty-DB return discipline.

**18 OQ dispositions LOCKED per RECOMMEND with ZERO amendments** at operator-paired Turn D triage 2026-05-23 PM (strong validation signal for brainstorming-phase Codex chain crispness — when brainstorming converges crisply at NO_NEW_CRITICAL_MAJOR with ALL findings resolved in-place + ZERO accepted-as-rationale, the writing-plans-phase OQ triage often surfaces zero amendments).

**32nd cumulative C.C lesson #6 validation NOTABLE** — pre-Codex review applied ALL 7 expansions + 5 NEW candidate refinements per NEW gotchas #17 + #18 BINDING AND Codex still surfaced 16 MAJOR findings, mostly cross-substrate verification gaps + dataclass shape consistency + sqlite3 binding/URI semantics + commit-cadence discipline. **2 NEW Expansion sub-refinements banked for 33rd cumulative validation onwards**: Expansion #2 sub-refinement (cascade-call-graph verification — when production function A has documented sibling B, verify A invokes / does NOT invoke B per actual code; do NOT infer from naming or docstring; cf. `Config.from_defaults` does NOT invoke `swing/config_overrides.py` user-config cascade despite the existence of the sibling) + Expansion #4 sub-refinement (runtime-binding-shape + empty-result-set audit — verify sqlite3 binding semantics + empty-input handling for every iteration / IN-clause / aggregate). **2 NEW CLAUDE.md gotchas appended this housekeeping** (#19 cascade-call-graph verification + #20 runtime-binding-shape + empty-result-set audit).

**Plan §B file map** enumerates 5 NEW research/ modules (`exceptions.py` + `ohlcv_reader.py` + `cfg_substitution.py` + `context_builder.py` + `sweep.py` + `output.py` + `run.py`) + 1 MODIFIED `swing/cli.py` (SOLE production write per OQ-17 carve-out; 35-60 lines mirroring V1 at `swing/cli.py:4748-4787`) + method-record extension (version bump 0.1.0 → 0.2.0 with NEW sections per spec §K.2 + §K.3 + §K.4 + §K.5) + first study writeup at `research/studies/2026-MM-DD-v2-ohlcv-criterion-evaluator.md` (date stamped at V2 ship) + `research/phase-0-tasks.md` "Next" update reflecting V2 SHIPPED status + operator smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}`. **Plan §B dependency graph**: T-V2.1 → T-V2.2 → T-V2.3 → T-V2.4 → T-V2.5 sequential per spec §M.2 RECOMMEND (NO concurrent dispatch).

**Plan §F + §K enumerate 5 BINDING discriminating tests** for L2 LOCK reinforcement (3 BINDING + 2 defensive; covers 4 file-open boundaries `pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table` + 4-module import sentinel graph `yfinance` + `schwabdev` + `swing.integrations.schwab` + `swing.data.ohlcv_archive`).

**Plan §G.0 commit-cadence preface** BINDING per dispatch brief §2.1 (Codex R1.M6 RESOLVED): each logical TDD slice (test + minimal implementation expansion + passing test) is ONE commit; parametrize-consolidation lands at ~50-69 commits; raw 1-commit-per-test ceiling ~84-91.

**Plan §H test budget recalibrated to ~84 fast tests** (per Codex R5; from initial ~68) distributed: T-V2.1 ~30 (ohlcv_reader ~12 + context_builder ~12 + cfg_substitution ~6); T-V2.2 ~14; T-V2.3 ~10; T-V2.4 ~8; T-V2.5 ~6 (integration). Baseline 5778 → ~5862 post-V2-ship.

Schema v21 UNCHANGED through writing-plans (docs only); baseline 5778 fast tests UNCHANGED; ZERO new Schwab API calls (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests); ZERO production `swing/` code changes (CLI subcommand registration BANKED for executing-plans per OQ-17 LOCK); ZERO Co-Authored-By footer drift across all 8 branch commits + 1 merge commit (~447+ cumulative streak preserved per fresh forward-binding lesson #7 Phase 12 Sub-sub-bundle C.B 2026-05-15 discipline).

**Forward action sequence (orchestrator-side; THIS handoff)**:

- [x] Post-merge housekeeping bundle THIS pass (CLAUDE.md line 3 refresh + 2 NEW gotchas #19 + #20 + phase3e-todo NEW top entry + orchestrator-context current pivot + Prior demote + archive-split per size-check trigger)
- [ ] V2 OHLCV executing-plans dispatch brief authored (Turn D continues; consumes writing-plans plan §B-§O BINDING substrate + 18 OQ dispositions)
- [ ] Inline implementer dispatch prompt provided for executing-plans phase (per `feedback_always_provide_inline_dispatch_prompt` BINDING; commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING)
- [ ] V2 executing-plans implementer ships 5 sub-bundles T-V2.1..T-V2.5 (~50-69 commits) + operator smoke run + closer
- [ ] V2 OHLCV harness output → operator review → optional cfg-policy method-record + Phase 14 commissioning consideration per Path B sequencing

---

## 2026-05-23 Applied Research Tranche 1: V2 OHLCV criterion-evaluator harness BRAINSTORMING SHIPPED at `362fe18` — FIRST Applied Research arc post-Phase-13-FULLY-CLOSED

**V2 OHLCV criterion-evaluator harness BRAINSTORMING SHIPPED 2026-05-23** at `362fe18` (integration merge of `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` via `--no-ff`; 7 implementer commits = initial spec at `dd6beac` + R1 fix at `c7f2a3c` + R2 fix at `5bb2640` + R3 fix at `5be32d2` + R4 fix at `c9e540e` + R5 minor doc-drift sweep at `1efec56` + return report at `8532949`). Spec at `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md` (1086 lines NEW; 14 sections §A-§N). Return report at `docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md` (221 lines NEW). **Codex MCP adversarial-critic chain converged at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (R1: 2C/6M/1m; R2: 1C/6M/2m; R3: 0C/2M/3m; R4: 0C/3M/3m; R5: 0C/0M/2m doc-drift; **3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place**; ZERO accepted-as-rationale). **Codex caught real defects against actual code/schema** — notable: candidate-only-vs-full-RS-universe (R1.C1); `current_equity` not persisted (R1.C2); `read_or_fetch_archive` has no `prefer_source` AND actively fetches (R1.M1+M2); Shape A lowercase OHLCV vs production capitalized (R2.C1); 5 stale references across spec sections (R2.M1); both-exist legacy/Shape A policy unspecified (R3.M1); post-cleanup universe re-check missing (R4.M2). **5 architectural recommendations LOCKED** in spec: (1) OHLCV reader = NEW read-only `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` bypasses `read_or_fetch_archive`; reads Shape A `{ticker}.yfinance.parquet` directly (legacy `{ticker}.parquet` fallback); NEVER opens `schwab_api` parquet (L2 LOCK preserved + REINFORCED by file-open mock discriminating test); (2) Interface = cfg-substitution via `dataclasses.replace` + production `evaluate_one(ctx)` end-to-end; `vcp.watch_max_fails` special-case mirrors V1; (3) Sweep = V1 5-point grid inherited; 1D per V2.1 §IV.B parsimony; (4) Output = hybrid V1 12-col matrix + headline + per-variable drill-down + V1↔V2 parity section + both-exist diagnostic banner; (5) Scope = ALL 15 inert threshold variables in one dispatch; reuse S3's 5681/63 universe. **18 OQs surfaced for operator-paired triage** (8 from dispatch brief §1.1 + 5 NEW from substrate analysis: OQ-9 perf budget + OQ-10 CLI name + OQ-11 `vcp.watch_max_fails` hardcode + OQ-12 Schwab L2 + OQ-13 coverage failure; + 4 NEW from Codex R1: OQ-14 RS universe reconstruction + OQ-15 `current_equity` surrogate + OQ-16 OHLCV read strategy + OQ-17 CLI carve-out; + 1 NEW from Codex R3: OQ-18 both-exist legacy/Shape A policy). **31st cumulative C.C lesson #6 validation NOTABLE** — Expansions #10 + #11 verified CLEAN at brainstorming tier; **2 NEW expansion refinements banked** for 32nd cumulative validation onwards: Expansion #2 refinement (brief-vs-actual-production-function-signature verification — extend from schema/column to function signatures + parameter shapes + side-effect contracts) + Expansion #4 refinement (SQL skeleton JOIN-cardinality + downstream-sufficiency audit — extend from column-existence to JOIN-cardinality 1:1 vs 1:N + sufficiency for downstream evaluator requirements + post-mutation universe re-check). **2 NEW CLAUDE.md gotchas appended this housekeeping** (#17 + #18). **Baseline parity discipline shipped in spec**: 2-tier (non-risk-gated EXACT + risk-gate-dependent CONDITIONAL with `current_equity` surrogate). **Promotion ladder shipped in spec**: 3-tier research→shadow→production ladder for the existing `aplus-criteria-calibration` method-record. Schema v21 UNCHANGED through brainstorming (docs only); baseline 5778 fast tests UNCHANGED (V2 ship projection +68 tests at executing-plans); ZERO new Schwab API calls (L2 LOCK preserved + REINFORCED); ZERO production `swing/` code changes (CLI subcommand registration BANKED for executing-plans per OQ-17); ZERO Co-Authored-By footer drift across all 7 branch commits + 1 merge commit (~437+ cumulative streak preserved).

**Forward action sequence (orchestrator-side; THIS handoff)**:
1. Post-merge housekeeping bundle (THIS pass): CLAUDE.md line-3 pivot (V2 OHLCV brainstorming current state; Phase 13 FULLY CLOSED demoted to compact previous state reference) + 2 NEW CLAUDE.md gotchas appended (#17 Expansion #2 refinement + #18 Expansion #4 refinement) + phase3e-todo.md NEW top entry (THIS section) + orchestrator-context.md current state pivot + Prior demote (T4.SB executing-plans + Phase 13 FULLY CLOSED current → Prior #1) + archive-split per size-check trigger (oldest Prior archived to docs/orchestrator-context-archive.md 2026-05-23 appendix).
2. **Turn D orchestrator handoff brief** authored at `docs/orchestrator-handoff-2026-05-23-post-v2-ohlcv-brainstorm-merge-pre-oq-triage.md` for fresh-context orchestrator to drive 18-OQ operator-paired triage session + V2 OHLCV writing-plans dispatch brief authoring + inline implementer prompt provision.
3. Turn D: operator-paired 18-OQ triage session via AskUserQuestion → V2 OHLCV writing-plans dispatch brief authored consuming operator-affirmed brainstorming spec + 18 OQ dispositions → inline implementer prompt for writing-plans phase.
4. V2 OHLCV writing-plans phase ships plan doc + per-task acceptance criteria → executing-plans dispatch → V2 OHLCV harness output → operator review → optional cfg-policy method-record + Phase 14 commissioning consideration.

**V2.G1-G4 operator gate bugs (banked at §"Post-T4.SB-SHIPPED operator gate feedback")**: STILL DEFERRED per operator decision 2026-05-23 PM (work AFTER Applied Research tasking completes). No action required at this pass.

---

## Phase 13 SHIPPED 2026-05-22 PM #4; FULLY CLOSED (12 of 12 sub-bundles)

**Phase 13 SHIPPED 2026-05-22 PM #4** — FULLY CLOSED. T4.SB closer arc lands at T-T4.SB.6 commit; 4 closer commits per plan §B.6 (fast E2E + main plan §H.3 row 13 + triage-agenda stub + docs sweep). Cross-bundle pin row 13 GREEN at all 4 surfaces.

**Next:** post-T4.SB triage agenda at `docs/phase13-closer-next-phase-triage.md`. Operator-paired triage meeting (Phase 14 trigger / Applied Research focus / idle monitoring decision per spec §1.5.2 amendment / OQ-CL.2 deferred disposition).

**T4.SB items 1-7 disposition (per closer arc):**

- [x] **Item 1** — A+ sensitivity diagnostic SHIPPED at T-T4.SB.1 (research harness under `research/harness/aplus_sensitivity/` + CLI `swing diagnose aplus-sensitivity` + study writeup + method record stub).
- [x] **Item 2** — Path A labeler `rule_criteria` + envelope `narrative` alias SHIPPED at T-T4.SB.4 (subagent contract widened; envelope alias persisted; corpus-all re-label operator-paired CLI surface).
- [x] **Item 3** — Market weather chart volume y-tick labels stripped SHIPPED at T-T4.SB.5 (`render_market_weather_svg` + `render_hyprec_detail_svg`; commit `3cb9d44`).
- [x] **Item 4** — Watchlist row lightning glyph removed SHIPPED at T-T4.SB.5 (commit `49258a5`).
- [x] **Item 5** — JIT chart cache-miss hook SHIPPED at T-T4.SB.3 (`swing/web/chart_jit.py:get_or_render_surface` NEW module + chart_scope LOCKED read-only; wired through /hyp-recs/{ticker}/expand + /watchlist/{ticker}/row + /watchlist/{ticker}/expand).
- [x] **Item 6** — Watchlist row thumbnail preservation on collapse SHIPPED at T-T4.SB.5 (`chart_svg_bytes_for_row` explicit param Option 6B; commit `7c6fe4c`).
- [x] **Item 7** — Hypothesis label delimiter-aware match invariant SHIPPED at T-T4.SB.2 (broader metrics wiring audit + Option 7C delimiter-aware fix at 4 surfaces; cross-bundle pin row 13 plant). Promoted GREEN at T-T4.SB.6 closer.

---

## Post-T4.SB-SHIPPED operator gate feedback (V2 backlog; 2026-05-23)

**Surfaced at**: post-T4.SB-executing-plans-merge S2-S5 operator-witnessed gate session 2026-05-23 (orchestrator-driven gates PASSED algorithmically; operator browser session surfaced 4 NEW visual/data issues NOT covered by gate criteria). Banked here as V2 investigation/resolution backlog. Operator decision 2026-05-23: bank-don't-fix; investigate in V2.

### V2.G1 — Hyp-rec + watchlist expanded charts not rendered (only open-positions table shows candlesticks)

| Field | Value |
|---|---|
| **Issue title** | Hyp-rec table expanded rows + watchlist expanded rows do NOT render candlestick charts; only the open-positions table displays them |
| **Surface** | `/dashboard` hyp-rec table expanded (via `/hyp-recs/{ticker}/expand`) + watchlist expanded (via `/watchlist/{ticker}/expand`) — algorithmic verification at S2.3 + S2.4 showed inline `<svg>` in fetch response (67KB), but operator's browser session reports the candlestick visualization is absent. Open-positions table chart surface (likely `position_detail`) renders correctly. |
| **Frequency** | Every hyp-rec or watchlist expand on operator's dashboard post-merge `2a56158` |
| **Severity** | **MEDIUM** — algorithmic gate PASSED on inline-SVG presence; operator-observed visual-render gap suggests the rendered SVG may not display as candlesticks (e.g., rendered as line chart, or rendered SVG bytes don't carry candlestick path geometry, OR template-side CSS/scaling hides candles). Cosmetic-but-UX-meaningful. |
| **Operator framing (2026-05-23)** | "The only candlestick graphs I see are in the open positions table. The hyp-rec and watchlist tables both do not show candlestick plots." |
| **Proposed V2 resolution** | **Visual diff investigation** between open-positions chart bytes (working) vs hyp-rec/watchlist expand chart bytes (broken). Three candidate root-cause buckets: (a) **renderer divergence** — `render_position_detail_svg` produces candlesticks; `get_or_render_surface` for `hyprec_detail` invokes a different rendering helper that produces a different chart type (line/area); (b) **renderer-kwargs uniformity** broken per Expansion #10 sub-discipline (c) — `hyprec_detail` surface ms-be invoked with different `ma_lines` or `chart_type` kwargs across callsites; (c) **template embedding** — the inline SVG is present but CSS/sizing in `hypothesis_recommendations_expanded.html.j2` + `watchlist_expanded.html.j2` clips/scales-out the candles. Discriminating test: render each surface against the SAME ticker + diff byte content + visual diff via Playwright/Selenium. |
| **Cross-reference** | S2.3 + S2.4 PASSED algorithmically (inline `<svg>` content length 67KB; no "chart unavailable" banner); V2.G1 captures the algorithmic-vs-visual gap. Related to T4.SB return report Lesson #4 (template-scraping E2E assertions MUST fail-closed on missing element — same JS-test-harness-gap family). |

### V2.G2 — Watchlist expanded chart title shows "hyp-rec detail" (surface-name leakage)

| Field | Value |
|---|---|
| **Issue title** | Watchlist expanded chart titles render the text "hyp-rec detail" — surface-name semantic leakage |
| **Surface** | `/watchlist/{ticker}/expand` rendered chart title (matplotlib `title=` or similar). Reported by operator at 2026-05-23 gate session. |
| **Frequency** | Every watchlist row expand |
| **Severity** | Cosmetic / labeling |
| **Operator framing (2026-05-23)** | "Title of the plots in the watchlist show 'hyp-rec detail'" |
| **Proposed V2 resolution** | **Directly maps to existing V1 simplification banked at writing-plans return report §4 item 8**: `hyprec_detail` surface-name grandfathered as CANONICAL "full-ticker detail chart" across MULTIPLE UI surfaces. V2 fix per return report: rename `hyprec_detail` → `ticker_detail` (or surface-distinct names `hyprec_detail` vs `watchlist_expanded_detail`) + v22 schema migration to widen `chart_renders.surface` CHECK enum + per-surface title-formatter that derives title from the CALLER context (not the surface enum value). Cosmetic-only; LOW priority per writing-plans banking. **Confirmation that the operator does notice this** elevates priority to MEDIUM-cosmetic. |
| **Cross-reference** | Writing-plans return report §4 V1 simplification #8 — predicted exactly this user-visible drift at banking time; operator observation confirms the V2 candidate is needed. Expansion #10 sub-discipline (c) cache-key + renderer-kwargs uniformity LOCK relevant. |

### V2.G3 — VSAT lost Sector and Industry values in open-positions table

| Field | Value |
|---|---|
| **Issue title** | VSAT row in open-positions table is missing Sector + Industry values; DHA (DHC?) never had them (legacy pre-feature) |
| **Surface** | `/dashboard` open-positions table Sector + Industry columns; rendered via `swing/web/view_models/dashboard.py` or `partials/open_positions_row.html.j2`. |
| **Frequency** | Persistent for VSAT row; legacy for DHA (DHC?) |
| **Severity** | Data wiring / regression — VSAT once had values (pre-T4.SB?) and lost them; new finviz CSV ingest path may have failed to persist OR a join condition lost the row mid-pipeline |
| **Operator framing (2026-05-23)** | "In the open positions table, VSAT lost Sector and Industry values. DHA never had them as that position was opened prior to them being included." |
| **Proposed V2 resolution** | **Investigation path**: (a) check `candidates` table for VSAT's latest row — is Sector/Industry persisted? (b) check `trades` table — does the trade row carry Sector/Industry directly (denormalized at entry-form time) or via JOIN to `candidates`? (c) if VSAT is no longer in today's finviz CSV (post-T4.SB pipeline rotation), the JOIN may return NULL for the open trade. Mirror existing CLAUDE.md gotcha "PriceCache `_last_close` only sees tickers in today's `candidates` table" pattern — Sector/Industry may suffer the same fate. **Fix candidate**: union open-trade tickers into `_step_evaluate` Sector/Industry persistence OR denormalize Sector/Industry onto `trades` at entry-form time OR cache last-known values per-ticker. DHA (DHC?) is acknowledged-legacy (pre-feature; no backfill required per operator). |
| **Cross-reference** | Same gotcha family as "PriceCache `_last_close` only sees tickers in today's candidates table" (CLAUDE.md) — applies to Sector/Industry surface. Also related to v21 schema (T2.SB6c added `trades.candidate_id` backlink which could be the JOIN path for Sector/Industry inheritance). |

### V2.G4 — "Refresh weather chart" reports "no OHLCV bars available for benchmark 'SPY'; run the pipeline first" even immediately post-pipeline-run

| Field | Value |
|---|---|
| **Issue title** | `POST /dashboard/weather-chart/refresh` consistently returns "no OHLCV bars available for benchmark 'SPY'; run the pipeline first" even when triggered shortly after a successful pipeline run that populates SPY bars |
| **Surface** | `/dashboard` "Refresh weather chart" button → HTMX POST to `/dashboard/weather-chart/refresh` → handler invokes chart_jit OR direct renderer → renderer needs SPY OHLCV bars from `OhlcvCache` or `read_or_fetch_archive`. |
| **Frequency** | Every "Refresh weather chart" click |
| **Severity** | **MEDIUM** — feature broken end-to-end. Pipeline writes SPY OHLCV bars to one cache path; refresh handler reads from different cache path OR reads from cache that wasn't populated by pipeline OR has stale cfg-resolved SPY symbol. |
| **Operator framing (2026-05-23)** | "Clicking 'Refresh weather chart' shows 'no OHLCV bars available for benchmark SPY; run the pipeline first' even if it is clicked shortly after doing a pipeline run." |
| **Proposed V2 resolution** | **Investigation path**: (a) verify pipeline's SPY-bar write path — is it `OhlcvCache.refresh_archive(ticker='SPY')` or `_step_evaluate`'s yfinance fetch into `OhlcvArchive`? (b) verify refresh-handler's SPY-bar read path — does it consume the SAME cache surface as the write path? (c) check `cfg.rs.benchmark_ticker` resolution — is the refresh handler reading the cfg value at handler-init time vs request-time? (d) check whether the JIT helper `get_or_render_surface(surface='market_weather')` falls back to live yfinance fetch on cache-miss OR fails with the "run the pipeline first" message. **Likely root cause**: `chart_jit.get_or_render_surface` invokes `_RENDERERS['market_weather']` which calls `render_market_weather_svg(...)` requiring `bars: pd.DataFrame` parameter; the handler may be passing an empty DataFrame OR not invoking the OHLCV cache hydration step. Discriminating test: plant SPY bars in `OhlcvCache` directly → invoke handler → assert render succeeds; plant empty bars → invoke → assert specific error message. |
| **Cross-reference** | Related to T-T4.SB.3 Item 5 architecture (chart_jit.py NEW module) + T-T4.SB.5 Item 3 market_weather chart rendering. Possibly tied to V2.G1 (broken candlestick rendering) — if `market_weather` and `hyprec_detail` share the same broken cache-hydration path, V2.G1 + V2.G4 are the SAME bug with two surface symptoms. Worth checking jointly. |

---

## T4.SB triage items (operator-supplied; PAUSE-FOR-LIST-ADDITIONS accumulation; pre-dispatch-brief)

Per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory: T4.SB dispatch brief is BLOCKED until operator-supplied usability triage items are enumerated. Spec §7.3 5-field template: Issue title / Surface / Frequency / Severity / Operator framing / Proposed resolution. Items accumulate here as operator surfaces them in conversation; orchestrator drafts T4.SB dispatch brief once the list closes.

### Item 1 — 0 A+ candidates diagnostic (2026-05-22 PM; surfaced at T2.SB6c executing-plans operator-witnessed gate)

| Field | Value |
|---|---|
| **Issue title** | 0 A+ candidates produced across all 63 evaluation runs since v20 detector chain landed |
| **Surface** | `/dashboard` hyp-rec table (shows only Sub-A+ tickers) + `/patterns/queue` (empty) + `/patterns/{id}/review` (404 for all candidates) + `/metrics/pattern-outcomes` reached_1R/hit_stop columns (suppressed: "no trade pairing or n<5") + chart_renders `hyprec_detail` surface (0 rows; A+ gated per `swing/pipeline/runner.py:2371`) |
| **Frequency** | Continuous since v20 landed at T-A.1.1 (~12+ sub-bundles ago); confirmed at 2026-05-22 PM operator-witnessed gate run |
| **Severity** | **HIGH** (operator-confirmed 2026-05-22 PM; concurred with orchestrator triage) — blocks closed-loop review surface AND research-branch first-method-record selection |
| **Operator framing** | "Purpose is to enter trades and make profit. No candidates = no trades. Conservative answer, but does not meet mission (ships are designed to go to sea...)" (verbatim 2026-05-22 PM) |
| **Proposed resolution** | Diagnostic V2 dispatch: instrument `bucket_for` gating order + capture which Stage-2 / RS-rank / tightness criteria are blocking candidates in the watch→aplus transition; report blocking-criterion distribution for an N-day window. Mirror the Tranche C candidate-sparsity diagnostic pattern (orchestrator-context lessons captured 2026-04-25). If calibration miss confirmed, propose threshold loosening via cfg policy. If market-output confirmed, no code change but document in cycle-checklist. |
| **Cross-reference** | Surfaced in S2-S11 gate report 2026-05-22 PM §"Key new findings" #1; operator action signal "T4.SB triage" |

### Item 2 — Path A labeler subagent contract widening (2026-05-22 PM; surfaced at T2.SB6c S11 backfill execution)

| Field | Value |
|---|---|
| **Issue title** | Path A labeler subagent emit contract widening — fresh exemplars need `rule_criteria` + `narrative` keys at emit time (Path C backfill is effective no-op against hand-labeled corpus) |
| **Surface** | `/patterns/exemplars` enhanced-rendering surface (34 "no rule_criteria" + 34 "no narrative" placeholders persist post-S11 backfill); `pattern_exemplars.labeler_evidence_json` shape contract |
| **Frequency** | Every render of `/patterns/exemplars` against the 34 existing operator exemplars (all from T-A.1.7 hand-labeled corpus; all carry `geometric_score_json IS NULL` which blocks Path C synthesis) |
| **Severity** | **MEDIUM** (operator-confirmed 2026-05-22 PM; concurred with orchestrator triage) |
| **Operator framing** | "Similar to 1. Potentially too limiting, making it more difficult to identify good entry opportunities." (verbatim 2026-05-22 PM) — operator framing rhymes with Item 1 framing; both items represent restrictions on operator's setup-discovery workflow |
| **Proposed resolution** | Extend pattern-labeler subagent emit contract (per `tools/silver_labeler_subagent.md` or equivalent) to emit `rule_criteria` array (per-rule pass/fail + threshold + tolerance) + `narrative` key at silver-label time. Then re-run labeler against operator's existing 34 exemplars (operator-paired silver-tier review) OR let new exemplars accumulate naturally as A+ candidates materialize. Path C backfill script retained as fallback for future cohort-import scenarios. Coupled with Item 1 above: while 0 A+ candidates persist, fresh exemplars also won't accumulate, so Path A widening is the only realistic unblock path. |
| **Cross-reference** | Brief §1.5.2 Path A V2-bank decision (preserved); S11 execution `Augmented: 0; Skipped: 34` 2026-05-22 PM; operator action signal "Concur, T4.SB" |

### Item 3 — Market weather chart volume-axis noise (2026-05-22 PM; surfaced by operator post-S2-S11 gate run)

| Field | Value |
|---|---|
| **Issue title** | Market weather chart volume subplot axis labels (0 / 1 / 1e8) add no value and distract |
| **Surface** | `/dashboard` market weather chart (rendered via `swing/web/charts.py:render_market_weather_svg` → cached at `chart_renders.surface='market_weather'`) |
| **Frequency** | Every dashboard render (only 1 cached row but it's the always-visible TOP chart) |
| **Severity** | Cosmetic / readability (no functional impact) |
| **Operator framing** | "the volume portion does not need axis values (0, 1, 1e8). They add no real value and are distracting and should be stripped." |
| **Proposed resolution** | In `render_market_weather_svg` (or equivalent volume-subplot helper), strip y-axis tick labels on the volume subplot via `ax_vol.set_yticks([])` (or `ax_vol.set_yticklabels([])` + preserve gridline if desired). Apply matplotlib-mathtext-safe per existing CLAUDE.md gotcha. Visual verification at S2 post-fix. Mirror to position_detail + hyprec_detail + watchlist_row volume subplots if they have the same issue (audit per `swing/web/charts.py` render functions). |

### Item 4 — Lightning icon on watchlist offsets thumbnails (2026-05-22 PM; surfaced by operator post-S2-S11 gate run)

| Field | Value |
|---|---|
| **Issue title** | Remove lightning glyph from watchlist rows — thumbnails are sufficient + glyph causes layout offset |
| **Surface** | `/watchlist` table rows + dashboard top-5 watchlist section. Rendered at `swing/web/templates/partials/watchlist_row.html.j2:14`: `{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}` |
| **Frequency** | Every dashboard + watchlist render where any ticker is within 1% of entry_target |
| **Severity** | Cosmetic / UX |
| **Operator framing** | "Let's completely remove the lightning icon from the watchlist. The thumbnails are much better and the lightning icon causes them to be offset." |
| **Proposed resolution** | Delete line 14 of `swing/web/templates/partials/watchlist_row.html.j2`. Audit for any companion CSS targeting the glyph (likely none). The "1% from entry_target" signal can be re-surfaced via `% to pivot` column (already present) — no replacement glyph needed. Visual verification post-fix on `/watchlist` + dashboard top-5. Note: brief should also audit `_thumb_bytes` template fragment at lines 9-16 to verify thumbnail rendering doesn't depend on the glyph's flexbox/inline-block layout space. |

### Item 5 — Chart scope too narrow + JIT-vs-flat-file architectural question (2026-05-22 PM; surfaced by operator post-S2-S11 gate run)

| Field | Value |
|---|---|
| **Issue title** | Chart-unavailable banner fires for any hyp-rec outside (A+ + open + watchlist top-10) scope; ALL hyp-recs + ALL watchlist items should be charted |
| **Surface** | `/dashboard` hyp-rec expanded row banner text at `swing/web/chart_scope.py:130-131` ("Chart unavailable — this ticker isn't in today's charting scope (A+ candidates, open positions, and tag-aware watchlist top-10)."). UCTT example observed today: shown as Sub-A+ hyp-rec, not in A+ set, not in top-10 watchlist, falls through to the unavailable banner. |
| **Frequency** | Every hyp-rec expand on a sub-A+ ticker outside the scope set; every watchlist row beyond top-10 (currently 47 of 57 watchlist rows have no chart) |
| **Severity** | **MEDIUM** (operator-confirmed 2026-05-22 PM; concurred with orchestrator triage) |
| **Operator framing** | (a) UX framing already verbatim: "UCTT in today's hyp-rec table lists 'Chart unavailable — ...' in lieu of a chart. This is incorrect, ALL hyp-recs should be charted. Additionally, ALL watchlist items should be charted." (b) Architecture-Q framing verbatim 2026-05-22 PM: "Only concern is eventual archive constraints. Generation of charts for every watchlist/rec/open trade on every trading day will build up. Likely not an issue for modern hardware for a very, very long time but just worth a question. Additionally, minor concern about collisions if the pipeline is re-run multiple times in a day. How is that handled WRT to the raster charts? Charts dynamically created would not have this issue (simply use the most recent data in the cache)." |
| **Operator question** | "Given the cache we are now retaining, should the mainline charts be generated on a JIT basis when a line is expanded or is it best to stick with creating flat files during runtime?" |
| **Orchestrator recommendation (REVISED 2026-05-22 PM post-operator framing)** | **JIT-primary with minimal pre-gen for dashboard first-paint critical set (market_weather + position_detail only).** Originally proposed hybrid with pre-gen for the broader "fast-render set" (A+ + open + dashboard top-5 watchlist); operator's archive-bloat + re-run-collision concerns tilt the recommendation strongly toward JIT-primary. The substrate landed at T2.SB6a (`chart_renders` cache + `get_cached_chart_svg` + `refresh_chart_render`) makes JIT clean: first expand of UCTT triggers render-on-cache-miss → writes to cache → all subsequent renders are instant cache hits. **Why JIT-primary**: (i) no archive bloat — only viewed charts populate cache; (ii) re-run collision benign — fresh expand always uses latest cache state + can re-render if stale; (iii) operator's framing explicitly endorses JIT semantics; (iv) closes the V1 simplification "exemplar cache-miss write-through skips when no completed pipeline run exists" (T2.SB6c return report §4.1 row 4) by making cache-miss live-render the canonical fallback path uniformly. **Why minimal pre-gen retained**: market_weather chart is ALWAYS visible at dashboard top — putting first-render latency there is operator-visible regression. position_detail charts are likely accessed within a few seconds of dashboard load if operator has open trades. These 2 surfaces stay pre-gen; everything else (watchlist thumbnails, hyp-rec detail, exemplar charts) shifts to JIT cache-miss. **Open question for brainstorming phase**: cache retention policy — should chart_renders rows older than N pipeline_runs be evicted? (Today the table grows unbounded; operator's concern surfaces an explicit V2 V1 dispatch decision.) |
| **Proposed resolution** | (1) Widen `_step_charts` pre-gen scope: keep A+ + open positions as pipeline-time guaranteed; reduce watchlist_row scope from "top-10" to "dashboard top-5 visible-by-default" (smaller fast-render set). (2) Add JIT cache-miss live-render hook on the chart_scope predicate path: when banner text would fire, instead invoke the per-surface SVG renderer + write to chart_renders cache + return the rendered bytes. (3) Audit `chart_scope.py:130-131` consumers to consume the new path. (4) Discriminating tests: plant a sub-A+ hyp-rec (UCTT today) + expand → assert chart_renders cache populated after first expand + identical render on second expand. (5) Re-cite §1.5.1 amendment scope-widening in the dispatch brief. Wall-clock concern: matplotlib first-render is typically 200-500ms per chart; the operator's expand-then-view UX expects sub-second responsiveness; verify under realistic OHLCV cache state. |
| **Cross-reference** | Couples with Item 1 (0 A+ candidates) — if Item 1 stays unresolved, the pre-gen `hyprec_detail` surface continues to write 0 rows (A+ gated per `runner.py:2371`); JIT cache-miss path is the ONLY path that gets sub-A+ hyp-recs charted under current market conditions. |

### Item 6 — Dashboard watchlist expand-then-collapse loses thumbnail (2026-05-22 PM; surfaced by operator post-S2-S11 gate run)

| Field | Value |
|---|---|
| **Issue title** | Dashboard watchlist row thumbnail disappears after expand-then-collapse cycle |
| **Surface** | `/dashboard` watchlist-near-trigger top-5 section rows (HTMX-driven expand/collapse) |
| **Frequency** | Every expand-then-collapse on a watchlist row that has a thumbnail (10 of 10 cached rows today) |
| **Severity** | UX (functional regression from default-render state) |
| **Operator framing** | "When expanding and then collapsing a dashboard watchlist item, the thumbnail disappears." |
| **Proposed resolution** | This is the canonical HTMX OOB-swap drift pattern documented in CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently" (2026-04-29 + later restatements). The COLLAPSE response handler likely emits a partial that hand-duplicates the watchlist row markup WITHOUT the thumbnail span at `watchlist_row.html.j2:9-16`. Fix pattern: the collapse-response template MUST `{% include %}` the same `watchlist_row.html.j2` partial as the default render path, not hand-duplicate. Audit candidates: `swing/web/routes/dashboard.py` collapse handler + any HTMX `hx-swap` target on watchlist expand/collapse. Discriminating test: render dashboard → snapshot watchlist row HTML → click expand → click collapse → assert row HTML matches snapshot byte-for-byte (or at minimum, thumbnail span present). Same gotcha family as Phase 5 R1 M2 (HX-Redirect-vs-303-swap) + entry_post Bug B (`<tr>`-leading makeFragment): HTMX failure surfaces are browser-only, often invisible to TestClient. |
| **Cross-reference** | Existing CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently" (2026-04-29) — applies directly. |

### Item 7 — Metrics wiring audit (specific defect: hypothesis-progress card reports 0 for all hypotheses) (2026-05-22 PM; surfaced by operator post-S2-S11 gate run)

| Field | Value |
|---|---|
| **Issue title** | Hypothesis-progress card reports 0 for ALL hypotheses despite 8 trades with non-NULL hypothesis_label persisted; broader scope = full metrics-wiring audit to catch similar surface-vs-data disconnects |
| **Surface** | Dashboard "hypothesis progress" card (rendered via `swing/web/view_models/metrics/hypothesis_progress_card.py:build_hypothesis_progress_card_vm` at line 404; backed by `swing/journal/stats.py:compute_hypothesis_progress_breakdown` line 325). Also consumed at CLI `swing/cli.py:1604` via `progress_rows = compute_hypothesis_progress_breakdown(...)` + rendered via `render_hypothesis_progress` line 1659. |
| **Frequency** | Every dashboard render; CLI hyp-rec progress subcommand; metrics surface |
| **Severity** | **HIGH** (operator-confirmed 2026-05-22 PM; concurred with orchestrator triage) — closed-loop trade analysis is core operator workflow; a metric reporting 0 while reality is 8 trades is silent-lying, which is worse than crashing |
| **Operator framing** | "The metrics need a thorough review to ensure they are properly hooked up. Specific example: the hypothesis progress card is reporting 0 for all hypothesis which is incorrect, several sub-A+ VCP not formed having been executed. two wins are running, several losses have been closed." |
| **Diagnostic evidence (2026-05-22 PM DB query)** | 8 of 10 trade rows have non-NULL `hypothesis_label`: 2 closed + 3 reviewed (`"Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness"`) + 1 closed (`"Sub-A+ VCP-not-formed (watch); failed: tightness, vcp_volume_contraction"`) + 1 partial_exited (`"sub-A+ VCP-not-formed test (proximity_20ma + tightness fails)"`) + 1 reviewed (`"A+ baseline (aplus)"`) + 1 reviewed (`"inaugural trade test"`). 2 trades with NULL hypothesis_label (legacy pre-Phase-7). Card likely matches against canonical hypothesis label set that does NOT exist on these rows (no `hypotheses` table; labels stored verbatim on `trades.hypothesis_label` TEXT column). |
| **Root-cause hypothesis** | Three candidate root causes (need investigation): (a) **string drift / lack of canonicalization at persistence**: trade rows carry the FULL hyp-rec card label including "(watch); failed: ..." suffix which varies per failed-criterion-set — the card's matching logic likely expects the canonical short form "Sub-A+ VCP-not-formed" without the suffix; existing CLAUDE.md gotcha "Grouping-key fields need canonicalization-at-persistence-boundary, not just display safety" (orchestrator-context archive Tranche B-ops hypothesis_label work R1/R2 lesson) applies directly — the operator's prior fix landed for the trade-entry path but the dashboard hyp-rec table "Enter" link populates the FULL formatted label including "(watch); failed: ..." suffix as the persisted hypothesis_label per `swing/web/view_models/dashboard.py` (today's evidence). (b) **state filter**: card may filter to `state='active'` or `state IN ('entered', 'managing')` only — missing `closed` + `reviewed` + `partial_exited`. (c) **ID-based join missing**: card may join via a `hypothesis_id` FK that's NULL on these trades. |
| **Broader scope (operator-supplied)** | "The metrics need a thorough review to ensure they are properly hooked up." T4.SB should commission a metrics-wiring audit covering ALL dashboard cards + `/metrics/*` surfaces. Today's S2-S11 gate observed at least 2 other metric surfaces showing "0 / no data" placeholders that COULD be wiring issues vs genuinely-empty data (S7 reached_1R/hit_stop "no trade pairing or n<5"; queue empty). Spec §7.3 5-field item template for the audit subitem: enumerate every metric surface in `swing/metrics/` + `swing/web/view_models/metrics/` + dashboard cards; for each, verify (i) data source query against current operator DB row distribution; (ii) state-filter scope vs operator expectation; (iii) join semantics vs persisted FK reality; (iv) discriminating round-trip test that plants the canonical N-row fixture + asserts the metric reflects N (currently the gate-run observed false-zero pattern). |
| **Proposed resolution** | (1) **Immediate diagnostic** (V2 dispatch precursor; could fold into T4.SB or fire earlier as a focused fix): instrument `compute_hypothesis_progress_breakdown` with a per-trade-row log entry showing the trade.hypothesis_label string + the card's matching key + the match outcome — surface in CLI subcommand + run against operator DB to identify which of (a)/(b)/(c) above is the root cause. (2) **Fix the root cause** per diagnostic outcome — most likely path is canonicalization-at-persistence-boundary fix mirroring the orchestrator-context Tranche B-ops precedent: strip "(watch); failed: ..." suffix at the entry-form POST handler + add a canonicalization round-trip integration test. (3) **Broader audit per operator framing**: enumerate metric surfaces; one-line audit per surface in T4.SB dispatch brief; for each, plant a discriminating round-trip test that defends against the false-zero failure family. (4) **Discriminating test pattern**: plant N trades with hypothesis_label='Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness' → render dashboard → assert hypothesis-progress card shows N (not 0). |
| **Cross-reference** | Existing CLAUDE.md gotcha "Grouping-key fields need canonicalization-at-persistence-boundary" (orchestrator-context archive, Tranche B-ops 2026-04-something) directly applies. Also: existing operator's "0 A+ candidates diagnostic" (Item 1) is structurally similar (closed-loop surface reporting 0 vs reality) but root cause differs (Item 1 = market output gate; Item 7 = surface-vs-data wiring). |

---

## 2026-05-22 PM #3 Phase 13 T4.SB WRITING-PLANS (closer arc SECOND sub-bundle; 6 sub-bundle tasks T-T4.SB.1..T-T4.SB.6 LOCKED in plan §G with 149 bite-sized TDD step-checkboxes; 18 OQ dispositions + 4 §1.5 amendments encoded per dispatch brief) SHIPPED at `9b2a4db` — SECOND sub-bundle of the Phase 13 closer arc (T4.SB brainstorming → writing-plans → executing-plans). Plan at `docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md` (4184 lines NEW; 14 sections §A-§N with §A-§L per dispatch-brief done criteria + §M references + §N self-review). Return report at `docs/phase13-t4-sb-writing-plans-return-report.md`. 6-commit dispatch (1 initial plan at `8ac4687` + 4 Codex MCP fix bundles at `7cc5775` + `0023df7` + `600313f` + `711637e` + 1 return report at `c8d21b9`). **Codex MCP adversarial-critic chain converged at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (R1: 2C+6M+3m; R2: 0C+3M+3m; R3: 0C+3M+3m; R4: 0C+2M+3m; R5: 0C+0M+0m convergence; **2 CRITICAL + 14 MAJOR + 12 MINOR ALL RESOLVED in-place**; ZERO advisory-only). **Codex caught real defects against actual code/schema** (validates implementer rigor + Codex effectiveness): placeholder variable enumeration (R1.C1: `_emit_*_thresholds` placeholders + sweep only handled 2 vars → REPLACED with 17-row concrete enumeration from real `Config` dataclass shapes); missing `allowed_miss_names` invariant in `bucket_for` mirror (R1.C2: `_bucket_for_substituted` REWRITE faithfully mirrors `bucket_for`; cfg threaded through); non-existent `hypothesis_registry.description` column (R1.M1: switched test fixtures to actual v8 schema columns); wrong `ChartRender` field set (R1.M2: missing 4 required fields per `swing/data/models.py:1907-1924`); renderer signature mismatches (R1.M3: `render_market_weather_svg` doesn't take ticker; `render_position_detail_svg` needs `fills`; `render_watchlist_thumbnail_svg` needs `ma_lines`); `pipeline_runs.state='completed'` not in CHECK enum→'complete' (R1.M4); undefined `_latest_completed_pipeline_run` (R4.M1: imports actual `latest_completed_pipeline_run` from `swing.web.chart_scope:82` without underscore prefix); nonexistent `request.app.state.db_conn` (R2.M3: switched to per-request `sqlite3.connect(cfg.paths.db_path)` pattern from `account.py`/`charts.py` route precedent). **29th cumulative C.C lesson #6 validation NOTABLE — Expansion #10 (architecture-location 5-sub-discipline) ran CLEAN at writing-plans tier** (FIRST clean-on-arrival validation post-brainstorming; brainstorming spec's architecture-location discipline carried forward correctly; Codex R1-R5 surfaced ZERO architecture-location regressions). **NEW Expansion #11 CANDIDATE banked for 30th cumulative validation onwards**: taxonomy propagation audit — when an enum-typed field (`kind`/`status`/`type`) is added to one dataclass, audit all downstream dataclasses + serializers + test fixtures for consumption. Surfaced via R1+R3+R4 `kind` enum propagation 3-instance lesson (T-T4.SB.1 sensitivity-harness `{additive, gate, threshold}` taxonomy required 3 Codex rounds to fully scrub across `SweepEntry` dataclass + CSV header + markdown matrix Kind column + test fixtures). **1 NEW CLAUDE.md gotcha appended this housekeeping** (Expansion #11 candidate; taxonomy propagation audit). **10 V1 simplifications banked with V2 dependency cited** per return report §4: (1) sensitivity-harness threshold variables 15-of-17 V1 deltas-0 (V2 OHLCV criterion-evaluator harness consuming original bars at `candidate.data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end); (2) `cfg.trend_template.allowed_miss_names` EXCLUDED from V1 (tuple-set; V2 set-membership sweep variant); (3) `cfg.rs.benchmark_ticker` EXCLUDED from V1 (string identifier; V2 likely cross-coupled with RS module rewrite); (4) `metrics_wiring_audit._KNOWN_SURFACES` hand-maintained registry 4 entries V1 (V2 codegen from decorator-marked surface registry); (5) Item 2 `--corpus-all` re-label flag operator-paired V1 (V2 batched-async re-label OR triggered automatically post-cfg-policy-loosening); (6) OQ-5.1 R4 manual prune CLI + R1 default unbounded growth ~300 MB/year per spec §B.5 (V2 automated retention R2 N pipeline_runs OR R3 >60 days); (7) OQ-5.2 synchronous JIT no-timeout worst-case ~1-2s cold (V2 async-render with HTMX placeholder swap if operator observes UX regression); (8) `hyprec_detail` surface name grandfathered as CANONICAL "full-ticker detail chart" across MULTIPLE UI surfaces (V2 rename to `ticker_detail` + v22 schema migration; low priority cosmetic); (9) OHLCV cache validity at original `data_asof_date` not guaranteed for sensitivity harness (V2 OHLCV archive reconstruction at arbitrary historical asof_date per cross-bundle V2 work; implied by V2 dependency #1); (10) `_known_surfaces` audit dispositions seeded with R1 best-guess + flipped to LIVE by T-T4.SB.2 implementer after fix (V2 auto-derivation from grep/static analysis). **5 forward-binding lessons banked in return report §5** for executing-plans phase + future T4-style closer arcs: (1) Pre-Codex Expansion #10 confirmed CORRECT for writing-plans phase (first clean-on-arrival); (2) writing-plans-phase test fixtures MUST grep actual migration files for column names BEFORE writing INSERT row strings (refinement to Expansion #4 BINDING for writing-plans-phase test scaffolds); (3) taxonomy propagation audit (Expansion #11 CANDIDATE); (4) plan-callsite Python identifier verification BEFORE writing the callsite (refinement to Expansion #4); (5) `request.app.state.<attr>` audit lesson (refinement to Expansion #4 BINDING for any plan touching web routes). **Sub-bundle dispatch decomposition LOCKED per plan §G (BINDING for executing-plans)**: T-T4.SB.1 (Item 1 sensitivity harness under `research/harness/aplus_sensitivity/` per §1.5.4 research-branch placement + Item 7 specific-defect diagnostic combined) + T-T4.SB.2 (Item 7 broader metrics audit + cross-bundle pin row 13 parametrize 4 surfaces per plan §E) + T-T4.SB.3 (Item 5 architecture work with NEW `swing/web/chart_jit.py` module + chart_scope LOCKED read-only per §1.5.3 Option A dashboard-anchor LOCK) + T-T4.SB.4 (Item 2 additive `rule_criteria` shape `{name, status, evidence_value, threshold, tolerance}` + envelope alias `narrative` key) + T-T4.SB.5 (Items 3 + 4 + 6 cosmetic/UX bundled per OQ-X.1 LOCK) + T-T4.SB.6 (closer + Phase 13 FULLY CLOSED marker per spec §K + post-T4.SB triage agenda artifact at `docs/phase13-closer-next-phase-triage.md` per §1.5.2 amendment). **Concurrent dispatch potential per plan §H**: T-T4.SB.4 + T-T4.SB.5 can run concurrent with investigation tasks (T-T4.SB.1 + T-T4.SB.2); T-T4.SB.3 sequential after substrate decisions in T-T4.SB.1; T-T4.SB.6 closer sequential after all. Schema v21 UNCHANGED through writing-plans (docs only); baseline 5670 fast tests UNCHANGED; ZERO new Schwab API calls (L2 LOCK preserved); ruff `swing/` 0 E501; ZERO Co-Authored-By footer drift across all 6 branch commits + 1 merge commit (~385+ cumulative streak preserved per fresh forward-binding lesson #7 Phase 12 Sub-sub-bundle C.B 2026-05-15 discipline).

**Integration-merge at `9b2a4db`** (branch `phase13-t4-sb-writing-plans` via `--no-ff`; 6 implementer commits = initial plan at `8ac4687` + R1 fix at `7cc5775` + R2 fix at `0023df7` + R3 fix at `600313f` + R4 fix at `711637e` + return report at `c8d21b9`).

**Forward action sequence (orchestrator-side; THIS handoff)**:
1. Post-merge housekeeping bundle (THIS pass): CLAUDE.md line-3 refresh + 1 NEW gotcha appended (Expansion #11 candidate; taxonomy propagation audit) + phase3e-todo.md NEW top entry (THIS section) + orchestrator-context.md current state refresh + Prior demote (T4.SB brainstorming current → Prior #1) + archive-split per size-check trigger (Prior count 10 at cap; demote brings to 11; archive oldest "T2.SB3 SHIPPED" container at line 138 region to `docs/orchestrator-context-archive.md` 2026-05-22 PM #3 appendix).
2. T4.SB executing-plans dispatch brief authored at `docs/phase13-t4-sb-executing-plans-dispatch-brief.md` (12 sections §0-§8) consuming the writing-plans plan + 18 OQ dispositions + 4 §1.5 amendments + 10 V1 simplifications + cumulative gotcha set BINDING for 30th cumulative validation.
3. T4.SB executing-plans phase ships 6 task commits T-T4.SB.1..T-T4.SB.6 + 0-5 Codex fix bundles + 1 return report (baseline 5670 → ~5760-5805 fast + 1 fast E2E per plan §F).
4. Post-executing-plans housekeeping bundle (Turn C orchestrator if context-budget watch fires; otherwise Turn B continuation) + Phase 13 FULLY CLOSED marker per spec §K + post-T4.SB-SHIPPED operator-paired triage meeting (Phase 14 trigger / Applied Research focus / idle monitoring decision per §1.5.2 amendment).

---

## 2026-05-22 PM #2 Phase 13 T4.SB BRAINSTORMING (closer arc; 7 operator-supplied triage items scoped + 18 OQs surfaced + sub-bundle decomposition LOCKED) SHIPPED at `4299340` — FIRST sub-bundle of the Phase 13 closer arc (T4.SB brainstorming → writing-plans → executing-plans). Spec at `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` (1045 lines NEW; 13 sections §A-§M). Return report at `docs/phase13-t4-sb-brainstorm-return-report.md`. 7-commit dispatch (1 initial spec at `0072a5b` + 4 Codex MCP fix bundles at `3ae42af` + `608345c` + `d9d5cd3` + `74d0238` + 1 R5 MINOR closure at `2e34e97` + 1 return report at `05101bb`). **Codex MCP adversarial-critic chain converged at R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (ZERO CRITICAL entire chain; **17 MAJOR ALL RESOLVED in-place**; 10 MINOR with 9 RESOLVED + 1 advisory closed in R5 fix bundle). **17 MAJOR findings clustered across 5 thematic sub-categories** (all 5 → NEW Expansion #10 candidate): (a) wrong-module architecture-location for cross-cutting JIT helper (R1.M2 + R1.M3 + R1.M7 — `chart_scope.py` LOCKED read-only; NEW `swing/web/chart_jit.py:get_or_render_surface` accepts conn + ohlcv_cache + surface explicitly; invoked from route handlers / VM builders); (b) template-vs-VM-parser-vs-emitter triangulation gap (R1.M6 + R3.M2 — Item 2 narrative-rendering gap at emit/persist NOT template; envelope-ALIAS pattern persists both `geometric_evidence_narrative` + `narrative` keys); (c) cache-key shape + renderer-kwargs uniformity LOCK (R4.M3 — `hyprec_detail` surface name LOCKED as CANONICAL "full-ticker detail chart" for ALL UI surfaces; cache-collision discriminating test with mock renderer + assert `call_count == 1`); (d) SQL LIKE wildcard escape + raw-vs-escaped binding-param asymmetry (R4.M2 — helper returns 3-tuple `(where_fragment, [raw_lowercased, escaped_lowercased, escaped_lowercased])`); (e) orphan-label preservation when refactoring exact-match groupings to delimiter-aware (R4.M1 — second-query orphan-fallback). **28th cumulative C.C lesson #6 validation NOTABLE — Expansion #7 PARTIAL FAIL** on architecture-location wrong-module placement (Codex R1 caught 3 sub-instances at chart_scope + missing OHLCV plumbing + WatchlistRowVM over-extension). **NEW Expansion #10 CANDIDATE banked for 29th cumulative validation onwards**: architecture-location audit + template-vs-VM-parser-vs-emitter triangulation + cache-key+renderer-kwargs LOCK + SQL-LIKE-binding-asymmetry + orphan-preservation under refactor. **1 NEW CLAUDE.md gotcha appended this housekeeping**: Architecture-location audit + 4 sub-disciplines (Expansion #10 candidate; 5-sub-discipline cluster). **14 V1 simplifications banked with V2 dependency cited** per return report §4.1 — notable: Item 1 diagnostic consumes PERSISTED candidate_criteria (schema does not persist OHLCV snapshots; V2 enhanced diagnostic deferred); Item 5 retention policy R1 unbounded + R4 manual prune CLI (R2/R3 automated retention V2-deferred); Item 7 Option 7C READ-time delimiter-aware match (NOT canonicalize-at-persistence; preserves operator's per-trade suffix). **18 OQs surfaced in §J** for operator-paired triage before T4.SB writing-plans dispatch: Item 1 (4) + Item 2 (3) + Item 5 (5) + Item 7 (3) + Phase 13 closure (3) + cross-item (1). **Sub-bundle decomposition LOCKED per spec §G** (BINDING for executing-plans): T-T4.SB.1 (Item 1 + Item 7 specific-defect diagnostics combined) + T-T4.SB.2 (Item 7 broader metrics audit with cross-bundle pin row 13 parametrized over 4 surfaces) + T-T4.SB.3 (Item 5 architecture work with NEW `swing/web/chart_jit.py` module + chart_scope LOCKED read-only) + T-T4.SB.4 (Item 2 additive `rule_criteria` + envelope alias `narrative` key — schema LOCKED to existing VM parser shape `{name, status (pass|fail), evidence_value, threshold, tolerance}`) + T-T4.SB.5 (Items 3 + 4 + 6 cosmetic/UX bundled) + T-T4.SB.6 (closer + Phase 13 FULLY CLOSED marker per spec §K closure-marker procedure). Schema v21 UNCHANGED through brainstorming (docs only); baseline 5670 fast tests UNCHANGED; ZERO new Schwab API calls (L2 LOCK preserved); ruff clean (0 E501); ZERO Co-Authored-By footer drift across all 7 branch commits + 1 merge commit (~377+ cumulative streak preserved).

**Integration-merge at `4299340`** (branch `phase13-t4-sb-brainstorming` via `--no-ff`; 7 implementer commits = initial spec at `0072a5b` + R1 fix at `3ae42af` + R2 fix at `608345c` + R3 fix at `d9d5cd3` + R4 fix at `74d0238` + R5 MINOR closure at `2e34e97` + return report at `05101bb`).

**Forward action sequence (orchestrator-side; THIS handoff)**:
1. Post-merge housekeeping bundle (THIS pass): CLAUDE.md line-3 refresh (compact format preserved — 5461 chars on line 3 down from 9750 after structural-edit drift; well under the 10K-char monitoring threshold + below the 6528 pre-restructure baseline) + 1 NEW gotcha appended (Expansion #10 candidate; 5-sub-discipline cluster) + phase3e-todo.md NEW top entry (THIS section) + orchestrator-context.md current state refresh + Prior demote (T2.SB6c executing-plans current → Prior #1) + archive-split per size-check trigger (Prior count 10 at cap; demote brings to 11; archive oldest "T2.SB2 + T-PT9 SHIPPED" container).
2. Operator-paired OQ triage (18 OQs across 6 categories; spec §J).
3. T4.SB writing-plans dispatch brief authored consuming the brainstorming spec + operator-confirmed OQ dispositions.
4. T4.SB writing-plans phase ships plan doc + per-task acceptance criteria.
5. T4.SB executing-plans dispatch (6 sub-bundle tasks T-T4.SB.1..T-T4.SB.6; concurrent dispatch potential noted in spec).
6. Operator-witnessed gates per spec §G per-task acceptance.
7. Merge T4.SB executing-plans branch --no-ff + post-merge housekeeping bundle + Phase 13 FULLY CLOSED marker per spec §K (CLAUDE.md + orchestrator-context "Currently in-flight work" updates announcing "Phase 13 FULLY CLOSED — 12 of 12 sub-bundles SHIPPED including closer T4.SB").
8. Post-Phase-13 transition decision (operator-paired): Phase 14 commissioning OR Applied Research branch focus per V2.1 §X tranche progression — pending OQ-CL.2 resolution.
9. Research-branch first-method-record selection meeting (depends on T-T4.SB.1 Item 1 diagnostic output landing).

**Operator-pending post-merge items** (NOT orchestrator-blocking):
- T4.SB OQ triage (18 OQs; required before writing-plans dispatch).
- Phase 14 trigger decision (OQ-CL.2; post-T4.SB-SHIPPED).
- Research-branch first-method-record selection (per `research/phase-0-tasks.md` "Later (deferred)"; depends on T-T4.SB.1 Item 1 diagnostic output).
- Worktree husks (5 pre-existing + 1 new `.worktrees/phase13-t4-sb-brainstorming`): operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.
- Schwab refresh-token clock: renew via `swing schwab logout` → `swing schwab setup` when ≤24h remaining.

**Phase 13 sub-bundle ship count: 11 of 11 SHIPPED**; T4.SB brainstorming SHIPPED THIS pass advances the closer arc but does NOT yet flip Phase 13 to fully closed. T4.SB writing-plans + executing-plans remain; Phase 13 FULLY CLOSED marker fires at T-T4.SB.6 executing-plans SHIPPED.

---

## 2026-05-22 PM Phase 13 T2.SB6c EXECUTING-PLANS (v21 schema atomic landing + SB6 completion-gap closure + §1.5.1+§1.5.2+§1.5.4 amendments) SHIPPED at `f30ceed` — **Phase 13 sub-bundle ship count: 11 of 11 (CLOSURE!)**; only T4.SB remains (paused per `project_phase13_t4_sb_pause_for_list_additions` memory). 9-commit dispatch (5 task commits T-A.6c.1..T-A.6c.5 at `7ee5a4a` + `7cac0f7` + `a61dd5a` + `b13ce7f` + `81eede2` + 3 Codex MCP fix bundles R1+R2+R3 at `cc8f5a0` + `c826791` + `0fb4d0e` + 1 return report at `4708543`); **Codex MCP adversarial-critic chain converged at R4 NO_NEW_CRITICAL_MAJOR after 4 rounds** (**ZERO CRITICAL entire chain**; 6 MAJOR ALL RESOLVED in-place via 3 fix bundles; 5 MINOR with 4 RESOLVED + 1 ACCEPTED-COSMETIC — R1 MINOR #1 WilsonCI format string `(Wilson CI 12.3-45.6; n=5)` vs brief's `{n: N, Wilson CI L.LL-U.UU}` accepted as cosmetic). **Schema v20 → v21 LANDED at T-A.6c.1 (`7ee5a4a`)** via migration `0021_phase13_t2_sb6c_trades_backlinks.sql` (Delta A `trades.candidate_id` NULLable INTEGER FK to `candidates(id)` ON DELETE SET NULL + idx_trades_candidate_id + Delta B `trades.pattern_evaluation_id` NULLable INTEGER FK to `pattern_evaluations(id)` ON DELETE SET NULL + idx_trades_pattern_evaluation_id + UPDATE schema_version SET version=21; atomic BEGIN/COMMIT per `executescript() implicit COMMIT` gotcha). **v20 LOCKED streak ENDED at this landing** (was 12+ sub-bundles since T-A.1.1 v20 atomic). **§A.14 paired discipline honored**: schema CHECK + dataclass field extension + read-path mapper extension (`_row_to_trade` row[52] + row[53] per OQ-9 LOCK) + write-path INSERT SVAI branch via `PRAGMA table_info` (T3.SB1 `fills.py:51-53` precedent extended to trades) + 26 paired discriminating tests in ONE atomic commit. Backup-gate strict equality `pre_version == 20 AND target >= 21` per OQ-3 LOCK; backup filename `swing-pre-phase13-sb6c-migration-<ISO>.db` per OQ-8 LOCK. **§1.5 amendments shipped**: §1.5.1 chart_renders cache write-through for 4 surfaces (watchlist_row + hyprec_detail + position_detail + market_weather) at `_step_charts` per T-A.6c.2; §1.5.2 labeler_evidence_json one-shot Path C backfill script at `swing/cli.py:patterns_exemplars_backfill_labeler_evidence` per T-A.6c.3; **§1.5.4 Gap B.5 WilsonCI surfacing CLOSURE-COMMITTED at T-A.6c.4 per operator decision 2026-05-22 AM** (template extension at `swing/web/templates/metrics/pattern_outcomes.html.j2` + 3 discriminating tests; closes V1 simplification entirely; ZERO V2 banking). **27th cumulative C.C lesson #6 validation NOTABLE — FIRST RUN APPLYING ALL 7 EXPANSIONS + 2 NEW REFINEMENTS + 4 NEW gotchas AT EXECUTING-PLANS PHASE**: Expansions #1+#2+#3+#4+#5+#6+#8 CLEAN; **Expansion #7 PARTIAL FAIL** on B.5 SQL ignoring `trades.pattern_evaluation_id` direct backlink (Codex R1 MAJOR #4 caught + RESOLVED at `cc8f5a0`). **NEW lesson category surfaced via Codex R1-R3 escalations: form-render anchor lifecycle 4-defect family** banked Expansion #9 candidate (soft-warn confirm `form_values` round-trip + GET-time query param consumption + candidate-snapshot consistency across pipeline runs + explicit-anchor-vs-latest-snapshot validation order). **1 NEW CLAUDE.md gotcha appended this housekeeping**: form-render anchor lifecycle audit (Expansion #9 candidate). **8 T2.SB6b §6 V1 simplifications ALL RESOLVED** (existing pre-v21 trades NULL backlinks → LIVE via v21 + NULL backfill per OQ-1; multi-pattern_class single anchor → LIVE; volume profile fetch-on-cache-miss → LIVE per OQ-14; backup-gate strict-equality → LIVE per OQ-3; `pattern_evaluations.candidate_id` direct column → LIVE via two-table JOIN; Phase 6 chart_pattern_algo enum disjoint → preserved; Path C labeler_evidence backfill → LIVE at T-A.6c.3; Gap B.5 WilsonCI → CLOSURE-COMMITTED at T-A.6c.4 per operator decision). **8 NEW V1 simplifications banked with V2 dependency cited** per return report §4.1: (1) Gap B.4 outcome distribution uses `realized_R_if_plan_followed >= 1.0 / < 0` surrogate vs OQ-6 spec text `max(daily_high since entry)` — V2 OHLCV-aware cohort-statistics with intraday-touch detection; (2) TradeEntryFormVM PE anchor lookup ORDER BY composite_score DESC fallback when no explicit query param — V2 explicit pattern_class context OR canonicalized PE-id query-param; (3) `VolumeProfileRow.__post_init__` rejects negatives but NOT NaN/inf — V2 `math.isfinite()` validator at dataclass barrier; (4) Exemplar cache-miss write-through skips when no completed pipeline run exists (legacy seeded-corpus) — V2 pipeline-run-agnostic exemplar cache key shape; (5) `market_weather` chart_renders embeds `trend_template_state="stage_2"` literal in `_step_charts` — V2 live `current_stage()` threading; (6) B.5 outer `n` field overridden to use B.5 denominator (preserves ratio correctness) — V2 separate `triggered_n` + `b5_denom_n` rendering fields; (7) `_latest_complete_evaluation_run_id` private-prefixed but consumed cross-module from `swing/trades/entry.py` — V2 rename without underscore OR document package-private convention; (8) R4 MINOR: explicit-anchor validation duplicated in `build_entry_form_vm` — V2 local helper extraction. NO new V1 STUBs on §5.10 8-item checklist. Cross-bundle pin row 12 PLANTED + GREEN at `tests/data/test_phase13_t2_sb6c_cross_bundle_pin_row_12.py` (parametrized over 2 deltas); Phase 13 main plan §H.3 row 12 appended (`test_phase13_t2_sb6c_v21_trade_backlinks_schema_atomic`). Test count: **baseline 5559 → 5670 fast (+111 net)** + 1 NEW fast E2E (`test_phase13_t2_sb6c_v21_closure_e2e.py`); ruff clean (0 E501); 2 skipped unchanged; ZERO new Schwab API calls (L2 LOCK preserved); ZERO Co-Authored-By footer drift across all 9 branch commits + 1 merge commit (~370+ project-cumulative streak preserved).

**Integration-merge at `f30ceed`** (branch `phase13-t2-sb6c-executing-plans` via `--no-ff`; 9 implementer commits = T-A.6c.1 v21 atomic landing at `7ee5a4a` + T-A.6c.2 Gap A + chart_renders write-through at `7cac0f7` + T-A.6c.3 Gap B no-schema + labeler backfill at `a61dd5a` + T-A.6c.4 Gap B v21-dep + anchor threading + WilsonCI at `b13ce7f` + T-A.6c.5 closer + cross-bundle pin row 12 at `81eede2` + R1 fix at `cc8f5a0` + R2 fix at `c826791` + R3 fix at `0fb4d0e` + return report at `4708543`).

**Operator-witnessed S2-S11 gate plan (per return report §9; PENDING operator-paired session post-merge)**:
- S2 (browser): `/patterns/{candidate_id}/review` — confirm all 8 spec §5.10 checklist items LIVE
- S3 (browser): hyp-rec detail page — confirm 800x500 SVG renders (Gap A.1)
- S4 (browser): position detail page — confirm 800x500 SVG with fill markers (Gap A.2)
- S5 (browser): `/watchlist` — confirm thumbnail charts render inline per row (Gap A.3)
- S6 (browser): `/patterns/exemplars` — cache-miss + write-through (Gap A.4)
- S6b (DB query): after pipeline run, `chart_renders` populated for all 4 surfaces (§1.5.1)
- S7 (browser): `/metrics/pattern-outcomes` — `reached_1r_n / n` + `hit_stop_n / n` ratio + WilsonCI for n≥5 (Gap B.5 + §1.5.4)
- S8 (browser): `/patterns/queue` — criterion 3 ranking matches current weather state (Gap B.6)
- S9 (browser): fresh hyp-rec trade entry → trade row gets BOTH `candidate_id` AND `pattern_evaluation_id` populated; manual_off_pipeline entry → NULL backlinks
- S10 (browser): `confirm` decision → `pattern_exemplars` gets `label_source='organic_trade_history'`
- S11 (operator-paired): `python -m swing.cli patterns-exemplars-backfill-labeler-evidence` runs cleanly + populates rule_criteria + narrative

**Forward action sequence (orchestrator-side)**:
1. Post-merge housekeeping bundle (4 files; THIS pass): CLAUDE.md line-3 refresh + 1 NEW gotcha appended (form-render anchor lifecycle audit Expansion #9 candidate) + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote (T2.SB6c writing-plans current → Prior #1) + archive-split per size-check trigger (Prior count was 10 at cap; demote brings to 11; archive oldest container "2026-05-20 Phase 13 T2.SB1 + T3.SB1 BOTH SHIPPED" verbatim to docs/orchestrator-context-archive.md).
2. **[PAUSE FOR OPERATOR LIST ADDITIONS]** per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory — operator-supplied usability triage items required BEFORE T4.SB dispatch brief commissioning per spec §7.3 5-field template (Issue title / Surface / Frequency / Severity / Operator framing / Proposed resolution). Q4 close-tracking flag schema already in v20 per migration 0020:262-307; T4.SB scope shrinks to Theme 4 usability work only.
3. T4.SB dispatch brief commissioning (operator-paired session; Phase 13 closer; pending operator items).
4. T4.SB brainstorming → writing-plans → executing-plans dispatch sequence (3-phase copowers chain per cumulative precedent).

**Operator-pending post-merge items** (NOT orchestrator-blocking):
- T2.SB6c operator-witnessed S2-S11 browser gates (PENDING; operator MUST restart `swing web` post-T2.SB6c merge so new VMs + templates load).
- T4.SB usability triage list (PAUSE-FOR-LIST-ADDITIONS BINDING; required before T4.SB dispatch brief commissioning).
- Worktree husks (5): `.worktrees/phase13-t2-sb6-closed-loop-surface` + `.worktrees/phase13-t2-sb6b-closed-loop-routes` + `.worktrees/phase13-t2-sb6c-v21-closure-brainstorm` + `.worktrees/phase13-t2-sb6c-writing-plans` + `.worktrees/phase13-t2-sb6c-executing-plans`. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.
- Schwab refresh-token clock: renew via `swing schwab logout` → `swing schwab setup` when ≤24h remaining.

**Phase 13 sub-bundle ship count: 11 of 11 (CLOSURE)**: T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 + T3.SB3 + T2.SB6a + T2.SB6b + T2.SB6c. Only T4.SB closer remains; paused per binding memory until operator-supplied usability triage items arrive.

---

## 2026-05-22 AM Phase 13 T2.SB6c WRITING-PLANS (v21 schema + SB6 completion-gap closure plan) SHIPPED at `e26bb0a` — 8-commit dispatch (1 initial plan at `4568d69` + 5 Codex R1-R5 fix bundles at `b085f15` + `dc810f8` + `d3b28db` + `104550f` + `3644d55` + 1 return report at `3087d5d` + 1 merge); **Codex MCP adversarial-critic chain converged at R6 NO_NEW_CRITICAL_MAJOR after 6 rounds** (1 CRITICAL: Gap B.4 SQL skeleton used `pe.evaluation_id` but canonical column is `pe.id` per migration `0020_phase13_charts_patterns_autofill_usability.sql:230-250`; Gap B.6 referenced non-existent `pattern_exemplars.weather_state_at_labeling` column; both column-verified at R1 closure mirroring brainstorm-phase Expansion #4 catch family; + 16 MAJOR + 4 MINOR cumulative findings; ALL RESOLVED in-place; ZERO ACCEPT-WITH-RATIONALE — closure dispatch intent preserved). Plan at `docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md` (1820 lines NEW; covers §A-§J done criteria from dispatch brief §5 verbatim; 5-task decomposition with bite-sized step structure per OQ-10 affirmed; per-task acceptance criteria + commit message templates; §1.5.1 chart_renders write-through + §1.5.2 labeler backfill amendments folded into plan §C.3 + §C.4 + §G.2 + §G.3). **26th cumulative C.C lesson #6 validation NOTABLE — FIRST RUN APPLYING ALL 7 EXPANSIONS AT WRITING-PLANS PHASE**: Expansions #1+#2+#3+#5+#6 CLEAN; **Expansion #4 (SQL skeleton column verification) PARTIAL FAIL** — pre-Codex missed 3 column-correctness defects (`pe.evaluation_id` non-existent; `pattern_exemplars.weather_state_at_labeling` non-existent; `current_stage` Phase-13-vs-Phase-8 module misattribution); R1 CRITICAL + R2 MAJOR #2 + R3 MAJOR #2 caught all three; **Expansion #7 (cross-row semantic) PARTIAL FAIL on unit-vs-scope distinction** — pre-Codex enumerated SCOPE per Gap B.3/B.4/B.5 explicitly but did NOT catch per-trade vs per-evaluation UNIT issues; R2 MAJOR #1 + R3 MAJOR #1 + R4 MAJOR #1 caught all three (B.5 denominator over-count via COUNT(*) inflation; B.5 numerator counting trades not evaluations; B.4 LIMIT on trade rows not evaluation rows). **4 NEW gotchas banked for 27th cumulative validation at T2.SB6c executing-plans** + appended to CLAUDE.md in this housekeeping pass: (9) SQL aggregation UNIT audit (NEW Expansion #8 candidate — per-COUNT/SUM/GROUP-BY the counting unit + DISTINCT need + LIMIT unit); (10) Existing-field reuse audit before claiming new dataclass fields (R4 MAJOR #2 caught `PatternOutcomeRow.reached_1r_n + _ci + hit_stop_n + _ci` fields ALREADY exist as None per T2.SB6b V1 simplification; plan claimed NEW `*_pct` fields which would have created field-duplication); (11) Template-rendering surface audit before claiming "no template edit needed" (R5 MAJOR #2 caught `PatternOutcomeRow._ci` fields populated but NOT rendered by `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` — only the ratio renders); (12) `date.fromisoformat()` discipline for cross-type-boundary calls (R3 MAJOR #2 caught `current_stage(conn, ticker, asof_date)` requires `date` but `pattern_evaluations.window_end_date` is TEXT). **5-task decomposition T-A.6c.1..T-A.6c.5 LOCKED in plan §G** with concurrent dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 recommended (~30-40% wall-clock savings); T-A.6c.4 sequential after T-A.6c.1; T-A.6c.5 closer; ~92-95 fast tests + 1 fast E2E projected (post-§1.5.1+§1.5.2 amendment bump from ~81 original; further bump to ~94-98 expected per executing-plans §1.5.4 WilsonCI surfacing amendment per operator decision 2026-05-22 AM). **All 14 OQs from brainstorm spec §7 AFFIRMED VERBATIM** per orchestrator-paired triage 2026-05-21 PM #5; writing-plans phase encodes spec §7 dispositions BINDING; no divergence; no operator-paired re-triage required. **Operator decision 2026-05-22 AM** (captured in handoff brief §3.2): Gap B.5 WilsonCI surfacing CLOSURE-COMMITTED via T-A.6c.4 template extension (NOT V2-deferred; ~2-3 additional tests = template render test + format string per Phase 10 honesty.wilson_ci convention + suppression-at-n<5 test; closes V1 simplification entirely; ZERO V2 banking; bumps test projection to ~94-98 fast + 1 fast E2E). This closure is itself a manifestation of NEW gotcha #11 (template-rendering surface audit) — the Codex R5 MAJOR #2 caught the rendering gap during writing-plans; operator-paired triage decided to CLOSE it at executing-plans rather than V2-bank it. **8 forward-binding lessons banked in return report §7** = 4 inherited from T2.SB6c brainstorming (brief-vs-actual schema; SQL skeleton column verification refinement; function name verification; hidden-anchor missing-value semantics) + 4 NEW (SQL aggregation UNIT audit Expansion #8 candidate; existing-field reuse audit; template-rendering surface audit; `date.fromisoformat()` discipline). **8 V1 simplifications + V2 candidates banked in return report §6** (closure-committed; ZERO new V1 STUBs introduced by T2.SB6c executing-plans per content-completeness audit at plan §D.4): existing pre-v21 trades persist NULL backlinks (OQ-1 LOCK; V2 enrichment if surfaced) + multi-pattern_class trade backlink single anchor (V2 many-to-many `trade_pattern_evaluations` link table) + volume profile fetch-on-cache-miss accepted (OQ-14 LOCK; V2 `get_cached_only` variant) + backup-gate strict-equality skips backup on multi-version jump (V2 `--enforce-stepwise` flag) + `pattern_evaluations.candidate_id` direct column (V2 schema dispatch if Phase 13.5+ needs) + Phase 6 `chart_pattern_algo` enum disjoint from Phase 13 detector enum (V2 schema migration) + Path C labeler_evidence backfill (V2 Path A labeler subagent emit contract widening for FRESH exemplars) + Gap B.1 trend-template state V1 returns only `'stage_2' | 'undefined'` per `current_stage` wrapper (V2 full Weinstein 4-stage labeling per spec §5.1.5 LOCK line 523 "thin wrapper"). **Gap B.5 WilsonCI row REMOVED from V2 bank per 2026-05-22 AM operator decision** (closure-committed at T-A.6c.4 instead). Schema v20 UNCHANGED through this writing-plans merge (docs only; v20 LOCKED streak ENDS at T-A.6c.1 executing-plans landing); 5559 fast tests baseline UNCHANGED; ZERO new Schwab API calls; ZERO Co-Authored-By footer drift across all 7 writing-plans branch commits + 1 merge commit (~360+ cumulative streak preserved).

**Integration-merge at `e26bb0a`** (branch `phase13-t2-sb6c-writing-plans` via `--no-ff`; 7 implementer commits = initial plan at `4568d69` + 5 Codex fix bundles at `b085f15` + `dc810f8` + `d3b28db` + `104550f` + `3644d55` + return report at `3087d5d`).

**Forward action sequence (orchestrator-side; THIS handoff)**:
1. Post-merge housekeeping bundle (4 files; THIS pass): CLAUDE.md line-3 refresh + 4 NEW gotchas appended + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote (T2.SB6c brainstorming current → Prior #1) + archive-split per size-check trigger (Prior count was 10 at cap; demote brings to 11; archive oldest container "2026-05-19 Phase 13 T1.SB0 gate-fix SHIPPED" verbatim to docs/orchestrator-context-archive.md).
2. Executing-plans dispatch brief authored at `docs/phase13-t2-sb6c-executing-plans-dispatch-brief.md` consuming the writing-plans plan + operator's §1.5.4 WilsonCI surfacing amendment per handoff brief §3.2.
3. Inline implementer dispatch prompt provided to operator per `feedback_always_provide_inline_dispatch_prompt`.
4. Executing-plans phase ships 5 task commits + 0-3 Codex fix bundles + 1 return report (~94-98 fast tests + 1 fast E2E expected; baseline 5559 → ~5651-5654 fast).
5. Post-executing-plans housekeeping bundle.
6. **[PAUSE FOR OPERATOR LIST ADDITIONS]** per `project_phase13_t4_sb_pause_for_list_additions` memory.
7. T4.SB dispatch brief commissioning (operator-supplied usability triage items required per spec §7.3 5-field template).

**Operator-pending post-merge items** (NOT orchestrator-blocking):
- T2.SB6b S2-S8 operator-paired browser gates from prior session — operator already ran the gates with prior orchestrator; findings drove the §1.5.1 + §1.5.2 amendments. Re-run S2-S8 post-T2.SB6c-executing-plans-ship to verify the closures land.
- T4.SB usability triage list (PAUSE-FOR-LIST-ADDITIONS binding; required before T4.SB dispatch brief commissioning).
- Worktree husks (4): `.worktrees/phase13-t2-sb6-closed-loop-surface` + `.worktrees/phase13-t2-sb6b-closed-loop-routes` + `.worktrees/phase13-t2-sb6c-v21-closure-brainstorm` + `.worktrees/phase13-t2-sb6c-writing-plans`. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.
- Schwab refresh-token clock: ~1d remaining at handoff (expires ~2026-05-24T06:40). Renew via `swing schwab logout` → `swing schwab setup`.

T2.SB6c executing-plans dispatch remaining in Phase 13 dispatch sequence; then **[PAUSE FOR OPERATOR LIST ADDITIONS]** → T4.SB closer. 10 of 11 Phase 13 sub-bundles SHIPPED; T2.SB6c executing-plans + T4.SB remaining.

---

## 2026-05-21 PM #5 Phase 13 T2.SB6c BRAINSTORMING (v21 schema + SB6 completion-gap closure design) SHIPPED at `fb177e3` — 11-commit dispatch (1 spec + 8 Codex R1-R8 fix bundles + 1 return report + 1 merge); **Codex MCP adversarial-critic chain converged at R8 NO_NEW_CRITICAL_MAJOR after 8 rounds** (1 CRITICAL: `candidates` table keyed on `evaluation_run_id` NOT `pipeline_run_id` per migration `0001_phase1_initial.sql:26` — Codex caught the SQL skeleton column error in the brainstorm spec before the implementer would have hit it at runtime; + 22 MAJOR + 11 MINOR cumulative findings; ALL RESOLVED in-place; ZERO ACCEPT-WITH-RATIONALE). **Brief-vs-actual schema correction (Expansion #2 catch at brainstorm phase)**: orchestrator brief §2.3 proposed `watchlist_close_track_flags` as v21 delta C — OBSOLETE; the table ALREADY exists in v20 per migration `0020_phase13_charts_patterns_autofill_usability.sql:262-307` + Phase 13 spec §7.2 line 986 LOCK. v21 scope correctly reduced from 3 deltas to 2 deltas: **Delta A = `trades.candidate_id`** NULLable FK to `candidates(candidate_id)` (unblocks organic_trade_history label_source split + reached_1r/hit_stop metric tile + outcome distribution full bucketing) + **Delta B = `trades.pattern_evaluation_id`** NULLable FK to `pattern_evaluations(evaluation_id)` (forward-binding closed-loop quality tracking). Spec at `docs/superpowers/specs/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-design.md` (659 lines NEW; 10 §-sections). **25th cumulative C.C lesson #6 validation NOTABLE — FIRST RUN APPLYING ALL 7 EXPANSIONS BINDING** (5 original + 2 NEW #6 content-completeness + #7 cross-row semantic scope from T2.SB6b banking). Pre-Codex 7-expansion discipline ran CLEAN at orchestrator-side audit; Codex R1 CRITICAL caught a SQL JOIN column error that pre-Codex Expansion #4 (specific-scenario gotcha trace) did NOT trace against migration files. **Expansion #6 + #7 effectiveness CONFIRMED**: spec §3.3 enumerates each §5.10 8-item checklist item with per-field disposition (LIVE / V1 PARTIAL / V1 STUB); post-SB6c ZERO V1 STUBs remain — closure-committed; spec §3.2 enumerates cross-row lookup SCOPE per Gap (per-candidate for Gap B.3; per-candidate cohort for Gap B.4; per-pattern_class cohort for Gap B.5) with discriminating ticker-proxy regression tests planted. **2 NEW expansion-discipline lessons banked for 26th cumulative validation at T2.SB6c executing-plans**: (1) Expansion #4 refinement — every SQL skeleton's columns MUST be verified against actual `swing/data/migrations/*.sql` files; (2) Expansion #7 boundary clarification — cross-row semantic SCOPE audit (per-candidate vs per-ticker) does NOT subsume column/JOIN correctness; Expansion #4 (or new sub-expansion) owns that. **5-task decomposition T-A.6c.1..T-A.6c.5 proposed**: T-A.6c.1 v21 migration atomic landing (~17 paired tests + 3 backup-gate tests + 1 cross-bundle pin) + T-A.6c.2 Gap A chart-surface wiring (~11 tests; no schema dep) + T-A.6c.3 Gap B no-schema review form data-completeness (~13 tests) + T-A.6c.4 Gap B v21-dependent + entry-form anchor threading + entry-path mapping fix + VM/builder extensions (31 tests; consumes Delta A + B) + T-A.6c.5 closer E2E + ruff. **Concurrent dispatch T-A.6c.1 + T-A.6c.2 + T-A.6c.3 recommended (~30-40% wall-clock savings)**; T-A.6c.4 sequential after T-A.6c.1; T-A.6c.5 sequential after all. ~81 fast tests + 1 fast E2E projected (within brief's ~+80-150 range). **14 OQs with brainstorm-recommended dispositions** (10 from brief + 4 NEW): OQ-1 NULL backfill; OQ-2 NO Q4 surfaces in SB6c (T4.SB owns Q4 surfaces only — schema already in v20); OQ-3 strict `pre_version == 20 AND target >= 21` backup-gate; OQ-4 + OQ-5 N/A (Q4 schema already in v20); OQ-6 reached_1r/hit_stop bucketing thresholds locked; OQ-9 row[52] = candidate_id + row[53] = pattern_evaluation_id column positions; OQ-12 closure-committed anchor-threading at T-A.6c.4 (NOT V2-deferred — pattern_evaluation_id lifecycle threads via hidden form input + 5-tier rejection + claim consistency-check gate; manual_off_pipeline persists NULL). **OQ triage pending operator-paired session before writing-plans dispatch**. **8 forward-binding lessons banked** in return report §7: (1) brief-vs-actual schema verification; (2) SQL skeleton column verification (NEW Expansion #4 refinement); (3) function name verification (R6 caught `resolve_trade_origin` vs canonical `derive_trade_origin` at `swing/trades/origin.py:52`); (4) hidden-anchor missing-value semantics; (5) server-derived vs form-submitted value-domain discipline; (6) EntryPath mapping load-bearing for trade_origin derivation (`swing/web/routes/trades.py:1095` hardcodes EntryPath.MANUAL_WEB_FORM; SB6c T-A.6c.4 fixes as side-effect of anchor-threading); (7) VM/builder fields as part of anchor-threading scope; (8) schema-version-aware INSERT for nullable columns (R1 expansion to T3.SB1 precedent). **6 V1 simplifications + V2 candidates banked** in return report §6 — closure dispatch intent honored; ZERO new V1 STUBs introduced by SB6c; all T2.SB6b §6 V1 simplifications targeted by SB6c are RESOLVED (closure-committed) or kept-explicit-in-V2-bank. **1 NEW CLAUDE.md gotcha** appended in this housekeeping pass: brief-vs-actual schema reality check + SQL skeleton column verification (Expansion #4 refinement BINDING for 26th onwards). Schema v20 UNCHANGED through this brainstorming merge (docs only); 5559 fast tests baseline UNCHANGED; ZERO new Schwab API calls; ZERO Co-Authored-By footer drift across all 10 brainstorming commits + 1 merge commit (~360+ cumulative streak preserved).

**Integration-merge at `fb177e3`** (branch `phase13-t2-sb6c-v21-closure-brainstorm` via `--no-ff`; 10 implementer commits = initial spec at `743075d` + 8 Codex fix bundles at `923961f` + `02afd9a` + `722eb77` + `7578d16` + `6d2a0c7` + `41c7457` + `161733e` + `be77115` + return report at `deb76d7`).

**Forward action sequence (orchestrator-side)**:
1. Operator-paired triage of 14 OQs in spec §7 — refine brainstorm-recommended dispositions into BINDING decisions; spec updates in-place if triage diverges.
2. Writing-plans dispatch brief authored consuming the brainstorm spec + operator-paired OQ decisions.
3. Writing-plans phase ships plan doc + per-task acceptance criteria.
4. Executing-plans dispatch (5 sub-tasks; concurrent T-A.6c.1 + T-A.6c.2 + T-A.6c.3; sequential T-A.6c.4 + T-A.6c.5).
5. T4.SB UNBLOCKED post-SB6c-executing-plans SHIPPED — PAUSE-FOR-LIST-ADDITIONS still binding per `project_phase13_t4_sb_pause_for_list_additions` memory; operator's added usability triage items required before T4.SB dispatch brief commissioning per spec §7.3 5-field template.

**Operator-pending post-merge items** (NOT orchestrator-blocking):
- T2.SB6b S2-S8 operator-paired browser gates (pending; operator MUST restart `swing web` post-T2.SB6b merge).
- T4.SB usability triage list (PAUSE-FOR-LIST-ADDITIONS binding; required before T4.SB dispatch brief commissioning).
- Worktree husks: `.worktrees/phase13-t2-sb6-closed-loop-surface` + `.worktrees/phase13-t2-sb6b-closed-loop-routes` + `.worktrees/phase13-t2-sb6c-v21-closure-brainstorm`. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.
- Schwab refresh-token clock: ~1d remaining at handoff (expires ~2026-05-24T06:40). Renew via `swing schwab logout` → `swing schwab setup`.

T2.SB6c writing-plans + executing-plans dispatches remaining in Phase 13 dispatch sequence (post OQ triage); then **[PAUSE FOR OPERATOR LIST ADDITIONS]** → T4.SB closer. 10 of 11 Phase 13 sub-bundles SHIPPED; T2.SB6c executing-plans + T4.SB remaining.

---

## 2026-05-21 PM #4 Phase 13 T2.SB6b (closed-loop routes + Theme 1 chart integration + T-A.1.6 Deficiency 1 fold-in; 6 deferred T2.SB6 tasks consuming T2.SB6a FROZEN substrate verbatim) SHIPPED at `6ec989e` — 10-commit dispatch (6 task commits T-A.6.3 + T-A.6.4 + T-A.6.5 + T-A.6.6 + T-A.6.6b + T-A.6.7 + 1 Codex R1 fix bundle + 1 Codex R2 minor docstring closure + 1 return report + 1 merge); **Codex MCP adversarial-critic chain converged at R2 NO_NEW_CRITICAL_MAJOR** (R1: **0 CRITICAL** + 7 MAJOR + 3 ACCEPT-WITH-RATIONALE; 3 fixed at `94e4418` (MAJOR #3 label_source ticker-proxy → closed_loop_review-only; MAJOR #6 cache-miss renderer not invoked → bars_fetcher injection + assert_called_once test; MAJOR #7 ASCII em-dash slip) + 1 minor docstring drift at `34ddfb7`; 4 ACCEPT-WITH-RATIONALE V1-banked per return report §6 (MAJOR #1 review form checklist placeholders + MAJOR #2 metric tile reached_1r/hit_stop + MAJOR #4 queue weather-state proxy + MAJOR #5 partial Theme 1 integration); R2: 0 Critical + 0 Major + 0 Minor new findings); **24th cumulative C.C lesson #6 validation NOTABLE — FIRST RUN APPLYING ALL 5 SCOPE EXPANSIONS BINDING**: pre-Codex 5-expansion discipline ran CLEAN at orchestrator-side audit on all 5 expansions (#1 hardcoded-duplicate + #2 brief-vs-spec source-of-truth + #3 schema-CHECK-vs-semantic-contract + #4 specific-scenario gotcha trace + #5 cross-section spec inventory grep); Codex caught 7 MAJOR findings (no CRITICAL) surfacing 2 NEW gap classes: (1) CONTENT-completeness gaps (4 of 7 — spec checklist items rendered as stubs vs live data; queue criterion 3 weather-state V1 proxy; metric tile reached_1r/hit_stop=None; Theme 1 integration partial completeness); (2) cross-row semantic scope drift (1 of 7 — label_source ticker-vs-candidate proxy on organic_trade_history per spec §5.10 lines 785-790). **2 NEW scope expansion proposals banked for 25th cumulative validation at T4.SB**: #6 content-completeness audit (for each spec data-surface checklist item, the implementer's per-field disposition must be enumerated explicitly LIVE / V1 PLACEHOLDER / V1 STUB BEFORE Codex review); #7 cross-row semantic audit on operator-input flows (for any new POST handler that consumes operator input AND looks up cross-row state, implementer must enumerate the SCOPE of the lookup ticker / pattern_class / candidate / pipeline_run and cross-check against spec wording). **NEW CLAUDE.md gotcha banked**: V1 simplification banking discipline (every V1 placeholder / V1 stub / V1 simplification the implementer ships MUST be enumerated in the return report §6 WITH the V2 dependency cited; T2.SB6b banked 9 such V1 simplifications verbatim per return report §6 covering trend-template stub + volume profile + outcome distribution + reached_1r/hit_stop trade-backlink + closed_loop_review-only + queue criterion 3 proxy + hyp-rec/position detail VM chart bytes + WatchlistVM template wiring + exemplar cache-miss write-through). **L7 substrate FROZEN LOCK verified** via empty `git diff` on `swing/web/charts.py` + `swing/data/repos/chart_renders.py` + `swing/data/models.py` (T2.SB6a Codex R1 fixes preserved verbatim). **L9 server-recompute LOCK at POST**: `/patterns/{candidate_id}/review` POST RECOMPUTES `proposed_pattern_class` from canonical `pattern_evaluations.pattern_class` at POST time per T3.SB3 R1 M#2 LOCK; discriminating test planted. **L10 ADDITIVE composition**: `/metrics/pattern-outcomes` 9th metric tile composes with Phase 10 cohort/honesty/RiskPolicy/Wilson-CI (NOT replacement); existing 8 Phase 10 tiles unchanged. **L12 HTMX 3-surface discipline** preserved across both new POST routes (`/patterns/{id}/review` POST + `/dashboard/weather-chart/refresh`): `hx-headers='{"HX-Request": "true"}'` propagation + 204 + HX-Redirect (NOT 303) + target route registered. **L13 dashboard market weather TOP placement** per spec §C.3 LOCK; E2E asserts weather_idx < status_idx. **L15 CriterionRow.status Literal['pass','fail'] runtime validation** via `__post_init__` frozenset; discriminating test planted. **L16 ASCII-only narrative text**; em-dash slip caught at Codex R1 MAJOR #7 + closed at `94e4418`. **L17 reuse `render_theme2_annotated_svg` from T2.SB6a substrate** verbatim via cache-miss path. **Cross-bundle pin row 11 PLANTED + GREEN** at `tests/data/test_repo_caller_tx_contract_invariant.py` with 4 parametrized passes (per Phase 13 NEW repo module) per brief L4 acceptance ("un-skip OR plant + un-skip per plan precedent"). +69 net fast tests (5490 → 5559: +24 T-A.6.3 + +10 T-A.6.4 + +8 T-A.6.5 + +10 T-A.6.6 + +11 T-A.6.6b + +4 cross-bundle pin row 11 + +1 E2E + +1 R1 fix bundle; 0 failed; 2 skipped unchanged: `test_flag_classifier_integration` V2 + v20 schema-CHECK pin row T4.SB) / 0 ruff E501 / schema v20 UNCHANGED; **ZERO new Schwab API calls** (L2 LOCK preserved); ZERO Co-Authored-By footer drift across all 9 T2.SB6b branch commits + 1 merge commit (~360+ cumulative streak preserved). **S2-S8 operator-paired gates DEFERRED to post-merge session** per `feedback_orchestrator_qa_implementer_product` precedent (S2 `/dashboard` market weather TOP; S3 `/patterns/queue` active-learning prioritization; S4 `/patterns/{id}/review` 8-item checklist + decision form; S4b `/patterns/exemplars` chart + criteria + narrative; S5 `/metrics/pattern-outcomes` per-pattern-class outcome distributions; S6-S7 hyp-rec/position detail V2-DEFERRED per return report §7; S8 visual mathtext verification). **Operator MUST restart `swing web` after T2.SB6b merge** so new VMs + templates load (T3.SB3 S2 stale-server lesson; banked at `4e71787`).

**Integration-merge at `6ec989e`** (branch `phase13-t2-sb6b-closed-loop-routes` via `--no-ff`; 9 implementer commits = T-A.6.3 at `3020fc8` + T-A.6.4 at `90769fb` + T-A.6.5 at `e56f462` + T-A.6.6 at `aa1900f` + T-A.6.6b at `c853ee2` + T-A.6.7 at `d8241a9` + Codex R1 fix at `94e4418` + Codex R2 minor at `34ddfb7` + return report at `cf1ea9f`).

**Forward-binding lessons banked for T4.SB inheritance** (per return report §5):
1. **25th cumulative C.C lesson #6 validation expected at T4.SB** with ALL 5 ORIGINAL EXPANSIONS + 2 NEW PROPOSALS (#6 content-completeness audit + #7 cross-row semantic scope audit) BINDING. T2.SB6b 24th run revealed CONTENT-completeness + cross-row-semantic-scope are 2 gap classes the existing 5 expansions don't cover.
2. **V1 simplification banking discipline**: return reports MUST enumerate each V1 placeholder/stub with V2 dependency cited (9 such enumerated in T2.SB6b §6; the pattern is binding for every future implementer return report).
3. **9 V1 simplifications banked → V2 candidates ledger growing**: trade.candidate_id backlink V2 migration unlocks 3 of 9 (organic_trade_history label_source split; reached_1r/hit_stop metric tile data; outcome distribution 1R+stop bucketing); weather-state-aware queue ranking unlocks 1; per-page VM wire-ups (hyp-rec detail + position detail) unlock 2; partial template extension + cache key shape extension unlock 2.
4. **Web server restart after VM/template-affecting merges** preserved (T3.SB3 S2 stale-server lesson; T2.SB6b operator-paired gates inherit).

**4 ACCEPT-WITH-RATIONALE banks** (forward-binding for T4.SB + V2):
1. Review form checklist placeholders (4 stub fields: trend-template state, volume profile, outcome distribution, MFE/MAE) — Codex R1 MAJOR #1; V2 wires live data per spec §5.10.
2. Metric tile reached_1r + hit_stop = None — Codex R1 MAJOR #2; requires trade.candidate_id backlink V2 migration.
3. Queue criterion 3 underrepresented_regime proxy = total exemplar count — Codex R1 MAJOR #4; V2 weather-state-aware variant per spec §5.10 line 799.
4. Theme 1 chart integration partial (hyp-rec + position detail VM chart bytes deferred) — Codex R1 MAJOR #5; V2 per-page sub-bundles.

**Operator-pending post-merge items** (NOT orchestrator-blocking; awaiting operator action):
- S2-S8 operator-paired browser gates listed above.
- T4.SB usability triage items per spec §7.3 5-field structured template — **PAUSE-FOR-LIST-ADDITIONS BINDING** per `project_phase13_t4_sb_pause_for_list_additions` memory.
- Worktree husks cleanup: `.worktrees/phase13-t2-sb6b-closed-loop-routes` (T2.SB6b) + `.worktrees/phase13-t2-sb6-closed-loop-surface` (T2.SB6a husk). Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient.
- Schwab refresh-token clock: ~1d 18h remaining at handoff (expires 2026-05-24T06:40). Renew via `swing schwab logout` → `swing schwab setup` when ≤24h.

**T4.SB dispatch BLOCKED on operator list additions per banked memory**. Phase 13 dispatch sequence remaining: **[PAUSE FOR OPERATOR LIST ADDITIONS]** → T4.SB closer. 10 of 11 Phase 13 sub-bundles SHIPPED; 1 remaining (T4.SB).

---

## 2026-05-21 PM #3 Phase 13 T2.SB6a (substrate Codex completion; closed-loop charts + cache helpers SUBSTRATE slice of T2.SB6 8-task scope) SHIPPED at `340f868` — 7-commit dispatch (2 substrate task commits T-A.6.1 + T-A.6.2 from prior partial-completion + 1 partial-completion return report + 2 Codex fix-bundles + 1 substrate Codex-completion return report + 1 merge); **Codex MCP adversarial-critic chain converged at R2 NO_NEW_CRITICAL_MAJOR** (R1: **1 CRITICAL** + 2 MAJOR + 1 ACCEPT-WITH-RATIONALE; ALL findings RESOLVED at `54fb531` + `77eb280`; R2: 0 Critical + 0 Major + 0 Minor); **23rd cumulative C.C lesson #6 validation NOTABLE — FIRST BREAK in 22-cumulative CLEAN streak**: pre-Codex orchestrator-side review verdict was CLEAN across 12 checklist items BUT Codex caught 3 findings at R1 surfacing 3 gap classes: (1) schema-CHECK-vs-semantic-contract gap (CRITICAL #1 — `chart_renders` schema CHECK permitted `(surface='watchlist_row', pipeline_run_id=NULL)` invisible to canonical reader because plan §C.2 SEMANTIC cache key contract extends beyond schema CHECK); (2) F6 lesson applicability scan gap (MAJOR #2 — `refresh_chart_render` unconditional DELETE-then-INSERT would blank cache on transient empty SVG; pre-Codex examined F6 generically but didn't trace SPECIFIC scenario through the DELETE-then-INSERT path); (3) cross-section spec inventory grep gap (MAJOR #3 — watchlist + market_weather missing volume bars per plan §C.5 line 449+452; pre-Codex covered LOCK'd sections §C.1 + §C.2 + §A.9 + §A.12 + §A.13 + §A.15 but didn't extend to §C.5 inventory which IS the source-of-truth for renderer content). **3 NEW scope expansion proposals banked for 24th cumulative validation at T2.SB6b**: #3 schema-CHECK-vs-semantic-contract gap audit; #4 CLAUDE.md gotcha specific-scenario trace; #5 spec inventory cross-section grep. **2 NEW CLAUDE.md gotchas** surfaced + banked (§A.14 paired discipline EXTENDS to semantic contracts beyond schema CHECK — cache key shapes; partial-index existence semantics; cross-column uniqueness via partial UNIQUE only; F6 write-through-cache transient empty defense applies at CONSTRUCTION barrier when helper accepts dataclass parameter, NOT at refresh wrapper). **NEW V2 brief-drafting candidate banked**: "if brief estimate exceeds 8h operator-paced, consider pre-emptive split at dispatch-time rather than reactive split at partial-completion-time" — original T2.SB6 brief estimated 12-18h and hit single-session budget wall; substrate-vs-downstream natural cleavage was visible in original brief §3 file scope (T-A.6.1 + T-A.6.2 pure-function/data-layer vs T-A.6.3-T-A.6.6b route handlers); V2 dispatch heuristic could pre-empt this kind of partial completion. +27 net fast tests (5463 → 5490: +21 substrate + +6 fix-bundles; 0 failed; 2 skipped unchanged) / 0 ruff E501 / schema v20 UNCHANGED; **ZERO new Schwab API calls** (L2 LOCK preserved); cross-bundle pin row 10 (`test_theme1_theme2_shared_renderer_handles_5_v1_patterns`) GREEN preserved post-Codex; **T2.SB6 partial-completion architecture**: 6 of 8 tasks DEFERRED to separate T2.SB6b dispatch (review form + queue + metric tile + chart-surface integration + exemplars enhancement + closer); substrate API surface FROZEN post-substrate-Codex; T2.SB6b consumes verbatim. **S2-S8 deferred to T2.SB6b** (substrate has no route surfaces — operator-paired browser gates not runnable at substrate-merge alone). S0 (orchestrator-driven): main HEAD picks up substrate via `--no-ff` merge — verified via `swing.web.charts` + `swing.data.repos.chart_renders` clean imports + `swing.data.models.ChartRender` accepts canonical-shape inserts + rejects non-canonical shapes. ZERO Co-Authored-By footer drift across all 6 branch commits + 1 merge commit (~340+ cumulative streak preserved).

**Integration-merge at `340f868`** (branch `phase13-t2-sb6-closed-loop-surface` SUBSTRATE SLICE via `--no-ff`; 6 branch commits = renderers at `e80101a` + cache helpers at `255823b` + partial-completion return report at `a9838a7` + Codex R1 CRITICAL #1 + MAJOR #2 fix at `54fb531` + Codex R1 MAJOR #3 fix at `77eb280` + substrate Codex-completion return report at `63d5593`).

**Forward-binding lessons banked for T2.SB6b + T4.SB + future arc work** (per return report §6):
1. Plan §C.5 spec inventory table is BINDING — extend §C.1 LOCK to cover CONTENT not just SIGNATURES (T2.SB6b dispatch brief should LOCK §C.5 explicitly).
2. Volume-bar gridspec pattern is reusable across 3 of 5 surfaces (watchlist + hyp-rec detail + market_weather); position-detail + theme2-annotated intentionally diverge per §C.5 + §C.4 — T2.SB6b could extract private `_split_price_volume_axes` helper if position-detail introduces similar MFE/MAE shading.
3. 23rd cumulative C.C lesson #6 validation NOTABLE BREAK + 3 NEW scope expansion proposals for 24th at T2.SB6b — pre-Codex review template extension required.
4. Substrate API surface FROZEN — T2.SB6b consumes 5 renderer functions + 2 cache helpers verbatim; no signature changes.

**Operator-pending post-merge items** (NOT orchestrator-blocking; awaiting operator action):
- T2.SB6b dispatch follows housekeeping (6 deferred tasks: review form + queue + metric tile + chart-surface integration + exemplars enhancement + closer).
- Worktree husk cleanup: `.worktrees/phase13-t2-sb6-closed-loop-surface` (operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient).
- Schwab refresh-token clock: ~1d 18h remaining at handoff (expires 2026-05-24T06:40). Renew via `swing schwab logout` → `swing schwab setup` when ≤24h.

**T2.SB6b dispatch UNBLOCKED** next per plan §H.1 (6 deferred tasks; branches from main HEAD `340f868` AFTER T2.SB6a merge; consumes substrate API surface frozen). 24th cumulative C.C lesson #6 validation expected with BOTH SCOPE EXPANSIONS + 3 NEW PROPOSALS (#3 schema-CHECK-vs-semantic-contract + #4 specific-scenario gotcha trace + #5 cross-section spec inventory grep) BINDING. **PAUSE-FOR-LIST-ADDITIONS BINDING** at T2.SB6b SHIPPED + housekeeping boundary BEFORE T4.SB dispatch.

---

## 2026-05-21 PM Phase 13 T3.SB3 (review auto-fill: priors + MFE/MAE from OhlcvCache; 5 tasks per plan §G.8) SHIPPED at `352bd83` — 10-commit dispatch (5 task T-B.3.1..T-B.3.5 + 1 pre-Codex fix + 2 Codex fix bundles + 1 return report + 1 merge); **Codex MCP adversarial-critic chain converged at R2 NO_NEW_CRITICAL_MAJOR** (R1: 0 Critical + 2 MAJOR + 1 ACCEPT-WITH-RATIONALE; BOTH Majors RESOLVED at `cab65d8` — (a) read-path `_row_to_review_log` extended for v20 `auto_populated_field_keys_json` column per Codex R1 M#1; (b) `cadence_complete_post` switched from GET-trusted hidden form input to POST server-recompute per Codex R1 M#2; R2: 0 Critical + 0 Major + 1 Minor RESOLVED at `3173fce` defensive row-length fallback removed); **22nd cumulative C.C lesson #6 BANKED CLEAN with BOTH SCOPE EXPANSIONS applied**: Expansion #1 (hardcoded-duplicate audit) — `REVIEW_PRIORS_DEFAULT_N=5` canonical site; ZERO duplicates in `swing/`; Expansion #2 (cross-check brief vs spec source-of-truth) — byte-fidelity verified across spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 (n=5 default; source-ladder Phase 8 FIRST + OhlcvCache FALLBACK; grade encoding A=4..F=0; period helper signatures; ZERO Schwab gate; ZERO schema changes); **pre-Codex orchestrator-side review caught 1 MAJOR + 2 MINORs BEFORE Codex invocation** (closed inline at `d3af86b`): pre-Codex MAJOR #1 (`build_review_vm` emitted `json.dumps([])` while cadence path emitted `None`; unified to `None` to defend the `... or None` SQL-nullability gotcha); pre-Codex MINOR #3 (`compute_mfe_mae_from_ohlcv_cache` used `date.today()` instead of `last_completed_session(datetime.now())`); the 21st+22nd cumulative pre-Codex disciplines now consistently catching what would have been Codex Critical/Major findings — chain converged at R2 (matches T2.SB5 R2; faster than T2.SB4 R5); **3 NEW CLAUDE.md gotchas** surfaced + banked (read-path mapping must keep pace with write-path on widened columns; "server-stamped" hidden inputs are STILL tampering surfaces unless POST RECOMPUTES; audit envelope empty-state representation must be uniform across emit + persist paths); +51 net fast tests + 1 un-skip via cross-bundle pin closure (5412 → 5463; 3 → 2 skipped; 0 failed); 0 NEW slow tests / 0 ruff E501 / schema v20 UNCHANGED; **ZERO new Schwab API calls** (L2 LOCK preserved per spec §6.3); **cross-bundle pin closure** at T-B.3.5: UN-SKIP `test_ohlcv_cache_get_or_fetch_invariant` at `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py:203` per plan §H.3 row 1 (T2.SB2 + T2.SB3 closer did NOT un-skip despite schedule; T3.SB3 closes the lag with behavioral surface — ladder-bars-fetcher injection asserting DatetimeIndex + capitalized OHLCV columns; offline); **S2-S4 disposition** algorithmic coverage via fast E2E `test_phase13_t3_sb3_review_auto_fill_e2e.py` (203 lines) + 4 unit-test files (~1588 lines cumulative) PASS at S1; operator-paired browser + round-trip + period review gates DEFERRED to post-merge session per `feedback_orchestrator_qa_implementer_product` precedent; ZERO Co-Authored-By footer drift across all 9 T3.SB3 commits + 1 merge commit (~318+ cumulative streak preserved).

**Integration-merge at `352bd83`** (branch `phase13-t3-sb3-review-auto-fill` via `--no-ff`; 9 implementer commits = priors at `1dd3b47` + MFE/MAE at `a2ce145` + review_form_page at `26df94e` + review_post + period helpers at `452cadd` + closer at `72fd96d` + pre-Codex fix at `d3af86b` + Codex R1 fix at `cab65d8` + Codex R2 fix at `3173fce` + return report at `664502a`).

**Forward-binding lessons banked for T2.SB6 + T4.SB inheritance** (per return report §6):
1. Read-path mapping must keep pace with write-path on widened columns — when widening a dataclass with a new field, grep ALL `_row_to_<table>` mapper functions in the same module + extend them in the SAME task with column-position comments + add discriminating round-trip persist→read tests.
2. "Server-stamped" hidden form inputs are STILL tampering surfaces unless POST RECOMPUTES rather than ACCEPTS — semantic clarification of Phase 8 R2-R5 server-stamping LOCK extended with GET-vs-POST recompute discipline.
3. Audit envelope empty-state representation must be uniform across emit + persist paths (emit `None` not `"[]"`) — defense for the `... or None` SQL-nullability gotcha only works if upstream emitter cooperates.
4. Pre-Codex orchestrator-side review with BOTH scope expansions applied is now load-bearing — 22nd cumulative validation surfaced 1 MAJOR + 2 MINORs that would otherwise have cost a Codex round; 23rd expected at T2.SB6 dispatch.

**3 ACCEPT-WITH-RATIONALE banks** (forward-binding):
1. Per-trade review form's hidden `auto_populated_field_keys_json` input is forward-binding scaffolding (v20 schema has the column on `review_log` only — period reviews; no `trades`-level audit column; future v21 migration could add).
2. `mfe_pct != 0.0` audit-keys gate conflates "no data" with "exactly-zero excursion" — V2 candidate to return explicit `MfeMaeResult` dataclass with `source: Literal['phase8', 'ohlcv', 'none']` tag for richer auditability.
3. GET/POST recompute drift for cadence audit envelope is acceptable as new ground truth — spec §6.3 doesn't lock the GET-side display value as authoritative; T2.SB6 could switch to signed nonce if operator-visible GET-side becomes truth surface.

**Operator-pending post-merge items** (NOT orchestrator-blocking; awaiting operator action):
- S2 (browser): open `/reviews/{id}/complete` for an open trade → confirm MFE/MAE values match operator's expectation; priors populated from prior reviews.
- S3 (round-trip): operator submits review; confirms `auto_populated_field_keys_json` audit trail persisted (visible via DB inspection or audit query).
- S4 (period review): operator triggers period review form; confirms section text auto-populated from `get_period_lessons_summary` + `get_period_mistake_tag_aggregate` + `get_period_cohort_health_deltas`.
- Worktree husks cleanup: `.worktrees/phase13-t3-sb3-review-auto-fill` (T3.SB3) + any residual from prior sessions. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient.
- Schwab refresh-token clock: per prior handoff ~2d remaining at 2026-05-24T06:40 (now ~2d 1h remaining). Renew via `swing schwab logout` → `swing schwab setup` when ≤24h.

**T2.SB6 dispatch UNBLOCKED** next per plan §H.1 (closed-loop surface + Theme 1 annotated charts + T-A.6.6b Deficiency 1 fold-in; 8 tasks per plan §G.9; branches from main HEAD `352bd83` AFTER T3.SB3 merge; consumes pattern_evaluations + template_match_nearest_exemplar_ids_json + auto_populated_field_keys_json audit trail + chart_renders cache). **PAUSE-FOR-LIST-ADDITIONS BINDING** per `project_phase13_t4_sb_pause_for_list_additions` memory at T2.SB6 SHIPPED + housekeeping boundary BEFORE T4.SB dispatch.

---

## 2026-05-21 Phase 13 T2.SB5 (template matching DTW + composite scoring; 6 tasks per plan §G.7) SHIPPED at `409d209` — 8-commit dispatch (6 task T-A.5.1..T-A.5.6 + 1 Codex R1 fix + 1 return report); **Codex MCP adversarial-critic chain converged at R2 NO_NEW_CRITICAL_MAJOR** (R1: 0 Critical + 0 Major + 2 Minor with 1 RESOLVED at `5534cc6` (bad-exemplar isolation in `match_forward` — per-element try/except in cohort iteration; skip bad element + continue rather than letting exception bubble up + suppress whole call) + 1 ACCEPT-WITH-RATIONALE banked (loose benchmark hit-count sanity; V2 candidate to tighten if synthetic universe shape changes such that band-infeasibility is guaranteed not to suppress all hits); **21st cumulative C.C lesson #6 BANKED CLEAN with BOTH SCOPE EXPANSIONS applied**: Expansion #1 (T3.SB2 hotfix `cf3c489` discipline; hardcoded-duplicate audit) — grep `swing/` for hardcoded duplicates of T2.SB5 constants (`SAKOE_CHIBA_WINDOW_RATIO` + `GEOMETRIC_SCORE_PREGATE_THRESHOLD` + `MAX_WINDOWS_PER_TICKER` + `EXEMPLAR_CORPUS_SUBSAMPLE_*` + `COMPOSITE_*_WEIGHT` + `COMPOSITE_SCORE_MAX`) returned ZERO duplicates; Expansion #2 (T2.SB4 R1 M1 lesson; cross-check brief vs spec source-of-truth) — byte-fidelity verified across spec §5.7 (lines 667-706 incl. 4-item pruning LOCK at 700-704) + §5.8 (lines 708-724) BINDING text (plan-side §D.4 + §D.5 references confirmed reference drift; spec has NO §D section); **3 NEW CLAUDE.md gotchas** surfaced + banked (bad-exemplar isolation in retrieval functions; DTW Sakoe-Chiba band infeasibility on asymmetric series — correct skip-as-no-match semantic; universe histogram must reflect POST-template composite); +35 net fast tests + 1 cross-bundle pin un-skip (5376 → 5412; 4 → 3 skipped; 0 failed) + 1 NEW slow benchmark (`test_template_matching_benchmark.py`; pytest-benchmark mean **8.18s** independently verified vs implementer's 8.33s; both << 120s gate per spec §5.7 line 706 — ~14.7× under budget; ~62,500 DTW pair-computations); **2 cross-bundle pins CLOSED at T-A.5.6 closer**: (1) UN-SKIP `test_pattern_exemplars_schema_shape_invariant` at `tests/data/test_v20_migration.py:833` (T2.SB3 closer did NOT un-skip despite plan §H.3 row 7 schedule; T2.SB5 closes the lag); (2) PLANT + UN-SKIP `test_pattern_evaluations_template_match_score_persistable` at `tests/data/test_v20_migration.py:880` per plan §H.3 row 8 (test did NOT exist on main pre-T2.SB5; planted with round-trip INSERT/SELECT body verifying NULL accept + float-in-[0.0,1.0] accept + parseable nearest_exemplar_ids_json); **S2 PASS via orchestrator-driven verification** (pytest-benchmark mean 8.18s independently re-run on main HEAD); **S3 + S4 disposition**: algorithmic coverage via fast E2E `test_phase13_t2_sb5_template_matching_e2e.py` (288 lines) + 3 pipeline integration tests at `test_step_pattern_detect_template_matching.py` PASS at S1; CLI integration probe + visual cross-check on known historical pattern DEFERRED to operator-paired post-merge session (T-A.1.7 corpus carries metadata-only; orchestrator-driven probe requires fresh yfinance/Schwab fetch for ~10-20 tickers — not undertaken); ZERO Co-Authored-By footer drift across all 8 T2.SB5 commits + 1 merge commit (~302+ cumulative streak preserved).

**Integration-merge at `409d209`** (branch `phase13-t2-sb5-template-matching` via `--no-ff`; 8 implementer commits = DTW core at `f532ed8` + retrieval at `58dfaea` + composite scoring at `730fa07` + pipeline integration at `1798c2f` + benchmark at `689ec36` + closer at `a105df7` + Codex R1 fix at `5534cc6` + return report at `5b41efb`).

**Forward-binding lessons banked for T3.SB3 + T2.SB6 + T4.SB inheritance** (per return report §8):
1. Bad-exemplar isolation in retrieval-style functions: any future function consuming a cohort + delegating per-element work to a normalization/transformation helper that can raise MUST use per-element try/except (skip bad element; continue cohort) rather than letting exception bubble up + suppress whole call. Aligns with existing "per-row failure isolation" discipline in pipeline step runners.
2. DTW Sakoe-Chiba band infeasibility on asymmetric series — correct skip-as-no-match semantic documented at `template_matching.py:202-208`; V2 length-stratified exemplar selection candidate banked.
3. Universe histogram must reflect POST-template composite — any future pipeline step that mutates a column AFTER the universe-snapshot point must rebuild histogram from post-mutation values. Pre-empt: explicitly enumerate which column the universe histogram should reflect + verify universe-build happens AFTER all mutations.
4. Evidence-tier vs composite-tier score cap distinction (inherited from T2.SB4 R2 C1) PRESERVED VERBATIM via L5 LOCK + `compute_composite_score` clamp on BOTH paths (full formula at composite.py:106 + template=None fallback at composite.py:98). Future scoring layers MUST preserve this discipline.

**NEW V2 candidates banked** (3 fresh + cumulative inherited):
- Tighten benchmark hit-count assertion if synthetic universe shape changes (Codex R1 M#2 ACCEPT-WITH-RATIONALE; current `assert result >= 0` is non-discriminating but acceptable given band-infeasibility cases).
- Length-stratified exemplar selection (NEW gotcha #2 banking; V2 candidate to address asymmetric series band-infeasibility).
- Adaptive Sakoe-Chiba band based on series-length ratio (V2 candidate complementing length-stratified selection).
- [Inherited from T2.SB4 chain]: §10.5 worked-example arithmetic inconsistency (V2.1 §VII.F amendment candidate); Plan §G.6 line 2671 stale DBW summary update; DBW `_RECENT_STAGE_VALUES` consolidation; HTF empirical calibration; DBW undercut bonus distribution; foundation primitive `volume_trend_through_swings` consolidation; multi-anchor candidate window iteration.

**Operator-pending post-merge items** (NOT orchestrator-blocking; awaiting operator action):
- S3 CLI integration probe: `python -m swing.cli pipeline run` against operator's production candidate pool; verify `pattern_evaluations` rows for aplus tickers with `geometric_score >= 0.4` carry non-NULL `template_match_score` in [0.0, 1.0] + `template_match_nearest_exemplar_ids_json` parseable JSON list of 1-3 exemplar IDs + `composite_score` in [0.0, 1.0]. DBW row spot-check: `geometric_score = 1.10` + `composite_score = min(1.0, 0.60 × 1.10 + 0.40 × template_match_score) ≤ 1.0`.
- S4 visual cross-check on known historical pattern: operator selects a known historical VCP (or any pattern with corpus coverage) + verifies `match_forward(candidate_window, exemplar_corpus, top_k=3)` returns plausible historical bases as top-3 hits. Requires fresh OHLCV fetch via OhlcvCache for candidate's ticker + each exemplar's ticker (~10-20 fetches per probe).
- Worktree husks cleanup (1 husk: `.worktrees/phase13-t2-sb5-template-matching`; previous husk `.worktrees/phase13-t2-sb4-detectors-batch2` may also remain from prior session). Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`.

**T3.SB3 dispatch UNBLOCKED** next per plan §H.1 (review auto-fill consuming OhlcvCache; 5 tasks per plan §G.8; branches from main HEAD `409d209` AFTER T2.SB5 merge; inherits T3.SB1 + T3.SB2 hidden-anchor + 4-tier rejection ladder + recovery anchor-clear discipline verbatim + Phase 13 detector substrate + template matching layer for "top-3 similar prior reviews" pre-population per spec §6.3).

---

## 2026-05-21 Phase 13 T2.SB4 (detectors batch 2: high_tight_flag + double_bottom_w; 7 tasks per plan §G.6) SHIPPED at `3b28d92` — 13-commit dispatch (7 task + 1 ASCII fix + 4 Codex fix bundles R1-R4 + 1 return report); 5 Codex rounds NO_NEW_CRITICAL_MAJOR at R5 with **1 RESOLVED Critical** (R2 C1 composite cap `min(1.0, geometric_score)` at runner.py:1677 — DBW evidence may reach 1.10 per spec §5.8 line 718 + §10.5 line 1325 undercut bonus; EVIDENCE preserved at 1.10 in `structural_evidence_json` + DB `geometric_score` column unconstrained; COMPOSITE caps at 1.0 to satisfy drift_logging `_composite_score_histogram` §5.11 [0.0, 1.0] LOCK) + 6 Major all RESOLVED + 8 Minor (6 fixed + 2 banked); **20th cumulative C.C lesson #6 BANKED CLEAN with SCOPE-EXPANDED discipline applied** (pre-Codex grep `swing/` for hardcoded 3-tuple/3-frozenset of pre-T2.SB4 `("vcp","flat_base","cup_with_handle")` returned ZERO duplicates beyond canonical sites already widened at T-A.1.1 atomic landing — the post-T3.SB2-hotfix scope expansion paid off); **5-detector V1 set COMPLETE per L2 LOCK** (vcp + flat_base + cup_with_handle + high_tight_flag + double_bottom_w; pattern detection substrate feature-complete for V1; T2.SB5 template matching + T2.SB6 closed-loop now layer on top); +48 fast tests (5328 → 5376; net 0 NEW skips beyond inherited 4 forward-looking pins) + 0 NEW slow E2E (fast E2E only per plan §G.6 T-A.4.6 `test_phase13_t2_sb4_detectors_e2e.py` 508 lines); **4 NEW CLAUDE.md gotchas** surfaced + banked (evidence-tier vs composite-tier score cap distinction R1 M1 + R2 C1 + R3 M1 lesson family; bounded backward-slice search for anchor-relative detectors R2 M2; DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")` R1 M2; pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches R1 M1 lesson — the dispatch brief was WRONG on the cap; spec §5.8 line 718 + §10.5 line 1325 BINDING text was authoritative); cross-bundle pin EXTENSIONS at T-A.4.7 closer (foundation introspection 3→5 detectors via `inspect.getsource` at `tests/patterns/test_foundation_integration.py:231-256`; drift_logging schema test 3→5 detectors via in-place extension at `tests/patterns/test_drift_logging.py:375-445`); **S2 PASS via orchestrator-driven probe** (main HEAD picks up T2.SB4 modules; `_pattern_detect_registry()` returns 5 detectors; composite cap verified at runner.py:1677; `_DETECTOR_CLASS_VALUES` 5-value frozenset preserved per L9; pipeline run substituted with direct runtime invocation given 0-aplus pool would produce 0 pattern_evaluations rows anyway, matching T2.SB3 S2 baseline); **S3 disposition**: algorithmic coverage via fast E2E PASS at S1; visual cross-check on a known historical HTF + DBW setup DEFERRED to operator-paired post-merge session (T-A.1.7 corpus carries metadata-only for HTF/DBW exemplars — no embedded OHLCV bars; orchestrator-driven probe would require fresh yfinance/Schwab fetch for 6 tickers — not undertaken); ZERO Co-Authored-By footer drift across 13 commits (~295+ cumulative streak preserved)

**Integration-merge at `3b28d92`** (branch `phase13-t2-sb4-detectors-batch2` via `--no-ff`; 13 implementer commits = HTF at `b9decf5` + DBW at `f3c2107` + pipeline 3→5 extension at `7685090` + drift_logging extension at `d73b50b` + Codex high-stakes activation at `f413a6b` + E2E at `d744a9e` + closer at `82050fd` + ASCII fix at `52ee630` + 4 Codex fix bundles R1-R4 at `6f735db` / `4768ee3` / `499c5ab` / `16f21d2` + return report at `7dfe1da`).

**Forward-binding lessons banked for T2.SB5 + T3.SB3 + T2.SB6 inheritance** (per return report §7):
1. Evidence-tier vs composite-tier score cap distinction LOCKED — any future scoring system implementation MUST enumerate evidence-tier vs composite-tier upper bounds explicitly + verify downstream consumers consume correctly-bounded tier (T2.SB5 DTW composite scoring at spec §5.7 + §5.8 inherits this VERBATIM)
2. Bounded backward-slice search discipline (any future detector consuming `(bars, anchor_date)` MUST bound the search window by spec's max-duration constraints; T2.SB5 template matching anchors may need similar discipline)
3. DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")` — explicit guard added to T2.SB4 DBW; T2.SB5 + T2.SB6 detectors consuming `CandidateWindow` SHOULD adopt the same guard or implement per-mode handling
4. Pre-Codex review SCOPE EXPANSION #2: cross-check dispatch brief prescriptions against spec source-of-truth at cited sections (complement to T3.SB2 hotfix scope expansion #1: grep for hardcoded duplicates of widened constants); BOTH expansions BINDING for 21st cumulative C.C lesson #6 validation at T2.SB5 dispatch

**NEW V2 candidates banked** (7 fresh + 5 cumulative inherited):
- §10.5 worked-example arithmetic inconsistency (center_peak=$23 vs 60% retracement requires $24.00; banked V2.1 §VII.F amendment)
- Plan §G.6 line 2671 stale DBW summary update ("undercut bonus + geometric_score capped at 1.0" → "geometric_score 1.10; composite capped at 1.0")
- DBW `_RECENT_STAGE_VALUES` consolidation (duplicate of `_STAGE_VALUES`; V2 either inline or document distinct forward-compat purpose)
- Foundation primitive `volume_trend_through_swings` consolidation (HTF + DBW compute their own per-segment volume aggregates inline; V2 consolidate if future detector demands)
- HTF empirical calibration (if S3 operator-witnessed gate shows §10.6 STRICT bound NONE rejects > 50% of operator-recognized HTF setups, V2 calibration territory)
- DBW empirical undercut bonus distribution (if S3 shows undercut bonus fires < 10% of operator-recognized DBW setups, V2 calibration may loosen the undercut threshold)
- Multi-anchor candidate window iteration (inherited T2.SB3 §6.4; spec §3.6 v21+ territory)
- [Inherited from T3.SB2 chain]: V2 hidden-anchor architectural hardening; V2 VM inheritance refactor; V2 Schwab Trader API lookback widening; V2 execution timestamp in candidate ordering + dedupe tuple; V2 cassette runbook live-recording infrastructure

**T2.SB5 dispatch UNBLOCKED next per plan §H.1** (template matching DTW + composite scoring; 6 tasks per plan §G.7; inherits 5-detector substrate; 120s/run benchmark gate per spec §5.7). Phase 13 dispatch sequence remaining: T2.SB5 → T3.SB3 → T2.SB6 → **[PAUSE FOR OPERATOR LIST ADDITIONS]** → T4.SB closer.

## 2026-05-20 PM #3 Phase 13 T3.SB2 (exit auto-fill via Schwab Trader API; 5 tasks per plan §G.5) + hotfix `cf3c489` SHIPPED — merge `7059945` (17 commits) + hotfix `cf3c489` (1 commit closes Critical `_call_endpoint` surface-guard defect discovered at operator-witnessed S2 gate); SELL-side mirror of T3.SB1 entry auto-fill with multi-partial-exit handling via server-side authoritative `candidates_map` envelope as NEW architectural dimension; 5 Codex rounds NO_NEW_CRITICAL_MAJOR at R5 + 1 FLAGGED L1 DEVIATION (R1 M3 ACCEPT unbounded lookback bounded-by-entry_date vs spec literal 7-day window — operationally robust; V2 spec amendment recommended) + 6 cumulative ACCEPT-WITH-RATIONALE banks + 10 V2 candidates documented + **4 NEW CLAUDE.md gotchas** (surface-guard scope discipline from hotfix; `selected_X_audit_id` audit-trail-vs-dedupe-key R2 M3; price-precision parity R4 M2; `extended.pop` for optional envelope keys R4 M1); cross-bundle pin un-skip CONFIRMED at `tests/data/test_v20_migration.py:907` (`test_fill_origin_enum_complete_after_v20`; net 1 skip recovery 5→4); **19th cumulative C.C lesson #6 BANKED-WITH-CAVEAT** (pre-Codex APPROVED_FOR_CODEX with 0C/0M/2m banked; operator-witnessed S2 caught the surface-guard defect that 5 Codex rounds + slow E2E + cross-bundle pin all MISSED; discipline scope expansion required); +71 fast tests (5257 → 5328 net: +69 from T3.SB2 + +2 from hotfix discriminating tests `test_19` + `test_20`) + 3 NEW slow Schwab E2E tests; ZERO Co-Authored-By footer drift across 17 T3.SB2 commits + 1 hotfix commit (~282+ cumulative streak preserved); operator-witnessed S2 + S3 + S5 gates PASS post-hotfix via Claude-in-Chrome browser automation (S2: DHC populated + VSAT empty paths; S3: DHC fill_id=20 with `fill_origin='schwab_auto_then_operator_corrected'` after 1-cent edit 8.59→8.60 triggering R4 M2 precision-parity comparison — subsequently CLEANED UP per operator approval to restore pre-S3 baseline; S5: 5 trade_exit audit rows status='success'); S4 multi-partial fieldset NOT EXERCISED in current Schwab broker state (algorithmic coverage via T-B.2.4 hybrid mode slow E2E)

**Integration-merge at `7059945`** (branch `phase13-t3-sb2-exit-auto-fill` via `--no-ff`; 17 implementer commits = 5 task-impl T-B.2.1..T-B.2.5 + reviewer-fix follow-ups + 4 Codex R1-R4 fix bundles + return report).

**Hotfix `cf3c489` forensic** — `_call_endpoint` Python-side surface guard at `swing/integrations/schwab/trader.py:527` was hardcoded to `("pipeline", "cli")`; rejected `'trade_entry'`/`'trade_exit'` with `SchwabApiError` BEFORE `record_call_start`. T-A.1.1 v20 atomic landing widened the DB CHECK + 1 of 4 Python-side guards (`audit_service._SCHWAB_API_SURFACE_VALUES`); missed 3 others (trader.py ACTIVE blocker — silently short-circuited BOTH T3.SB1 entry auto-fill AND T3.SB2 exit auto-fill in production for 1+ day; 0 audit rows written for either surface + marketdata.py inert + models.py SchwabApiCallRecord dead-code). Slow Schwab E2E tests passed because they mock at `trader.get_account_orders` boundary so never exercise `_call_endpoint` with new surfaces against real guard. Hotfix scope: 3-site widening (use canonical `_SCHWAB_API_SURFACE_VALUES` 4-tuple via `audit_service` import for trader/marketdata; hoist module-level constant in models.py) + 2 discriminating tests (`test_19_call_endpoint_accepts_surface_trade_entry` + `test_20_call_endpoint_accepts_surface_trade_exit` exercise `get_account_orders` against v20 conn + assert audit row written with correct surface + status='success'). Fast suite 5326 → 5328 (+2; ZERO regressions); ruff clean across 4 touched files.

**NEW V2 candidates banked** (10 cumulative across T3.SB2 + hotfix + S3 testing finding):
1. V2 hidden-anchor architectural hardening (replace JSON transport with `schwab_api_call_id` server-side audit-row lookup per R2 M1 ACCEPT; inherited from T3.SB1)
2. VM inheritance refactor (sweep all 7+ base-layout VMs to inherit from `BaseLayoutVM` per R1 M4 inherited from T3.SB1)
3. Schwab Trader API lookback widening per R1 M3 ACCEPT (spec amendment for explicit `lookback_days` kwarg semantics)
4. Execution timestamp in candidate ordering + dedupe tuple per R1 M5 + R3 M2 ACCEPT
5. Provenance-stamping branch helper extraction per R4 minor ACCEPT
6. Client-side JS rebinding visible inputs on radio change per R2 minor closure (multi-partial UX V1 workaround is operator-instruction text)
7. Fallback tuple-matched candidates as "possible duplicate" soft-warn per R3 M2 alternative
8. Cassette runbook live-recording infrastructure per T-B.2.4 hybrid mode dependency
9. "Reset to Schwab values" button on rejection-recovery form per T3.SB1 R4 M2 ACCEPT
10. **Dedupe-vs-operator-typed-historical gap demonstrated in production at S3 testing** — operator's existing `operator_typed` trim (no `schwab_order_id`) is NOT excluded from auto-fill candidates because `existing_fill_order_ids` keys off Schwab order_id; Schwab re-surfaces the same SELL the operator already journaled, creating risk of duplicate fill on submit; V2 fix: extend exclusion to also key off `(date, price ±epsilon, quantity)` fallback tuple when `schwab_order_id IS NULL`

**Plus the hotfix-derived V2 candidate**: hoist `_SCHWAB_API_SURFACE_VALUES` into a shared schema-constants module so `audit_service.py` + `models.py` import from a single source (avoids the duplication introduced by this hotfix).

## 2026-05-20 PM #2 Phase 13 T2.SB3 (detectors batch 1: VCP + flat_base + cup_with_handle) SHIPPED at `e3d34a9` — 14-commit dispatch (9 task + 4 Codex fix bundles + 1 return report); 5 Codex rounds NO_NEW_CRITICAL_MAJOR at R5; 1 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE bank (defensive lease.fenced_write branches test-harness-only); 18th cumulative C.C lesson #6 BANKED CLEAN; +73 fast tests (5184 → 5257; cross-bundle pin un-skip at tests/patterns/test_foundation_integration.py:231 CONFIRMED at T-A.3.9 closer); 1 slow E2E PASS (VCP geometric_score=1.0 on spec §10.1 synthesized fixture); S2 + S3 operator-paired gates PASS (orchestrator-driven); ZERO Co-Authored-By footer drift across 14 commits (~263+ cumulative streak preserved)

**Integration-merge at `e3d34a9`** (branch `phase13-t2-sb3-detectors-batch1` via `--no-ff`; 14 implementer commits = 1 pipeline integration recon at `2df314a` + 3 detectors (VCP at `e4370e8` + flat_base at `653cf7b` + cup_with_handle at `151a487`) + drift_logging at `d608f55` + `_step_pattern_detect` pipeline integration at `2300dd4` + retroactive Codex T2.SB3 evaluation at `2773aec` + fast+slow E2E at `c87dfda` + closer + pin un-skip at `1e2962e` + 4 Codex-fix bundles (R1 + R2 + R3 + R4 at `9ceb37f` / `693a5b4` / `9364533` / `403aa1c`) + return report at `14e29fe`).

**Codex chain shape (5 rounds; ZERO Critical entire chain)**: pre-Codex APPROVED_FOR_CODEX (18th cumulative C.C lesson #6 validation; CLEAN) → R1 0C/3M/2m (3 Majors RESOLVED at `9ceb37f` — CWH window clip + asof_date provenance + drift histogram two-pass + sanitize column check + retroactive recompute bounds; 2 Minors RESOLVED) → R2 0C/3M/1m (3 Majors RESOLVED at `693a5b4` — lock-duration regression + partial-retry histogram + eval_run fallback hardening + sanitize message; 1 Minor RESOLVED) → R3 0C/1M/1m (1 Major RESOLVED at `9364533` — Pass-2 concurrent-insert histogram amendment; 1 Minor ACCEPT-WITH-RATIONALE — defensive lease.fenced_write branches test-harness-only) → R4 0C/2M/0m (2 Majors RESOLVED at `403aa1c` — Pass-2 final-universe semantics + reconciliation-before-serialize via JOINT architectural restructure) → R5 0C/0M/1m **NO_NEW_CRITICAL_MAJOR** (1 Minor advisory ONLY — stale comments at runner.py:1510-1519; banked V2 candidate).

**Pipeline integration recon decision at T-A.3.1**: NEW `_step_pattern_detect` step (NOT extend `_step_evaluate`); positioned between `_step_recommendations` (runner.py:806-817) and `_step_schwab_snapshot` (runner.py:835-862); best-effort failure wrapper mirroring `_step_watchlist` + `_step_recommendations` + `_step_charts`. Sandbox gating decision: NO sandbox gating (bars already ladder-routed via OhlcvCache; pattern_evaluations not Schwab-derived integrity surface). Per-mode `anchor_date` contract: each of 3 detectors implements its OWN backward-slice helper (swing-LOW for VCP + flat_base; swing-HIGH for cup_with_handle).

**Cross-bundle pin un-skip CONFIRMED at T-A.3.9 closer**: `test_foundation_primitives_consumed_by_detectors_invariant` at `tests/patterns/test_foundation_integration.py:231-256` — Option (a) chosen (`inspect.getsource` introspection of 3 detector modules + verify references to expected foundation primitives `CandidateWindow` + `current_stage` + `extract_zigzag_swings` + `adaptive_initial_threshold_pct` + additionally `volume_trend_through_swings` for VCP). T2.SB4 detectors (HTF + DBW) will EXTEND this test when they ship.

**S2 + S3 operator-paired gates PASS (orchestrator-driven 2026-05-20 PM)**:
- **S2 (pipeline integration)**: pipeline run 73 at `2026-05-20T15:58:05 → 16:10:49` (12m 44s; +3m over baseline 9m 22s — consistent with new `_step_pattern_detect` execution). All status fields `ok`; ZERO error_message; ZERO warnings_json. 2 Schwab→yfinance fallbacks (PL + DK) — known pattern banked from T1.SB0 gate-fix as V2-PL-fallback-diagnostic-logging candidate; not new. **0 pattern_evaluations rows for run 73 IS CORRECT BEHAVIOR**: pool today was 51 skip + 10 watch + 4 excluded + **0 aplus**; `_step_pattern_detect` filter predicate (`bucket == 'aplus'` verified at `swing/pipeline/runner.py:1370` + `:1439`) correctly skipped empty pool. Pipeline ran T2.SB3 code (verified via `swing.pipeline.runner.__file__` resolution + `hasattr(r, '_step_pattern_detect') = True`; CWD=worktree priority over pip-editable `.pth` via `sys.path[0]=''`).
- **S3 (gold corpus cross-check)**: 7 gold exemplars probed (3 VCP + 1 flat_base + 3 cup_with_handle; HTF + DBW deferred to T2.SB4). All 7 detector invocations completed without exceptions; all produced structurally-valid `<Detector>Evidence` objects. **4-of-7 score ≥0.4** on operator-validated gold bases (AMD vcp 0.429 + NVDA vcp 0.429 + TGT flat_base 0.571 + NFLX cup_with_handle 0.525 with `rounded_cup_passes=True` on 3 marginal bars). **3-of-7 algorithmic misses (SNAP vcp 0.000 + COST cwh 0.000 + MSFT cwh 0.000)** match T2.SB1 forward-binding lesson #8 cup-with-handle rounded-vs-V hard-gate empirical observation; V2 calibration territory not bugs. §10.7 rounded-vs-V LOCK demonstrably exercised (NFLX HARD PASS w/ 3 bars marginal vs COST/MSFT HARD FAIL w/ 2 bars).

**3 forward-binding lessons banked for T3.SB2/T2.SB4 inheritance**:
1. **Two-pass-then-reconcile-then-serialize architectural pattern** — any future cache-or-write step that emits multiple rows with cross-row dependencies inherits (T2.SB4 HTF + DBW detectors + T2.SB6 closed-loop). Pass 1 emits queued tuples + Pass 2 (inside fenced_write) re-reads canonical existing once → reconciles emit queue → builds FINAL universe → serializes every surviving row with the same universe → INSERTs.
2. **`EvalRunResolutionError` typed-exception precedent** — any step that must DERIVE asof_date from a pipeline-run anchor (NOT wall-clock) inherits this pattern: raise on missing/malformed via `_resolve_eval_run_action_session_date(conn, eval_run_id)`; defensive best-effort wrapper catches + skips. T3.SB2 exit auto-fill MUST honor this when deriving exit-anchor session_date.
3. **Bar-clipping discipline at detector entry** — clip `bars` to `bars.index <= candidate_window.end_date` BEFORE anchor identification; applies to ALL pattern detectors consuming `candidate_window` + any exit-time bar-consuming logic in T3.SB2.

**2 NEW V2 candidates banked from R5 + S3 gates**:
- **R5 minor advisory: stale comments at `swing/pipeline/runner.py:1510-1519`** (banked from Codex R5; ZERO blocking impact). Comments in `universe_context` block say "scores are then appended during pass 1" but R4 restructure removed Pass-1 appends; documentation drift only. Cleanup candidate for future maintenance pass; could fold into T4.SB usability triage closer OR into any subsequent runner.py modification.
- **Cup-with-handle criterion_2 sub-condition investigation** (banked from S3 gold corpus cross-check 2026-05-20 PM). COST cup_depth 18.4% + MSFT cup_depth 17.2% — both IN spec §5.4 criterion #2 range [12%, 35%] — yet algorithmic `criteria_pass[criterion_2] = False` causing geometric_score=0.000 hard-zeroing. Detector evidently checks SUB-CONDITIONS beyond raw depth (e.g., depth-from-cup-left-edge specifically, or duration interaction). Worth investigating at T2.SB6 closed-loop OR T2.SB5 template-matching dispatch. Could surface as a §5.4 spec amendment or criterion #2 sub-criteria documentation enhancement. Operator + implementer noted at T2.SB1 forward-binding lesson #8 ("cup rounded-vs-V hard gate caused 4 of 5 cup dispatches sub-1% margin failure") — this S3 finding REINFORCES the same family with NEW depth-criterion observation alongside the existing rounded-cup gate observation.

**Pure-function discipline preserved** (LOCK L2 verbatim from brief): ZERO DB writes inside `swing/patterns/vcp.py` + `flat_base.py` + `cup_with_handle.py` (verified via grep `conn.execute|conn.commit|cursor()` returning 0 matches in all 3 detector files). `current_stage` is the only DB call from any detector + it's READ-ONLY via `swing/patterns/foundation.py:current_stage` SELECT into Phase 4 evaluation surface.

**L3 LOCK preserved**: NO `INSERT OR REPLACE` on `pattern_evaluations` writes (verified via grep; 2 hits in codebase are defensive comments citing LOCK L3, not actual SQL). Repo uses plain `INSERT INTO pattern_evaluations` at `swing/data/repos/pattern_evaluations.py:70-72` with SELECT-then-INSERT idempotency check at `_step_pattern_detect` per runner.py:1484-1493.

**L7 LOCK preserved**: `VCPEvidence` + `Contraction` + `FlatBaseEvidence` + `CupWithHandleEvidence` + `FeatureDistributionLog` ALL carry `__post_init__` Literal[...] frozenset validation with explicit CLAUDE.md gotcha "`Literal[...]` not runtime-enforced" citations in docstrings (verified via grep showing per-class `_*_VALUES` frozensets + `__post_init__` invariant checks).

**V1 known limitation banked** (per return report §6.4): `_step_pattern_detect` selects `windows[-1]` (most-recent candidate window per ticker per detector). Pipeline-path candidate windows often produce too-short base context that fails criterion #6 (base_duration ≥ 21d for VCP) → score 0.0. Fast E2E asserts SHAPE contracts; slow E2E exercises `detect_vcp` DIRECTLY with synthesized §10.1 fixture (achieves 1.0). V2 candidate: multi-anchor candidate window iteration (iterate ALL windows per ticker, pick highest-scoring per pattern_class). Spec §3.6 v21+ territory; NOT in T2.SB3 scope.

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across all 14 commits (~263+ project-cumulative; verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches).
- C.C lesson #6 18th cumulative validation: CLEAN.
- Schema v20 UNCHANGED (T2.SB3 is pure consumer logic; NO migration work).
- Baseline 5184 → 5257 fast (+73 net; +60 new tests + +15 R1-R4 Codex discriminating tests + cross-bundle pin un-skip net 0 new skips beyond inherited).
- Ruff 0 E501 preserved.
- 1 slow E2E PASS (VCP geometric_score=1.0 on §10.1 fixture).

---

## 2026-05-20 PM Phase 13 T2.SB2 (foundation primitives) + T-PT9 (Phase-9 calendar-drift test fixture fix) BOTH SHIPPED at `c15633d` — 11-commit batched dispatch; 2 Codex rounds NO_NEW_CRITICAL_MAJOR at R2; 3 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks (all flagged for T2.SB3 spec amendments); 17th cumulative C.C lesson #6 BANKED CLEAN; +35 fast tests (5149 → 5184 net); 0 failures (2 previously-failing Phase-9 calendar-drift tests now PASS via T-PT9); cross-bundle pin planted at `tests/patterns/test_foundation_integration.py:231` for T2.SB3+T2.SB4 detector consumption; ZERO Co-Authored-By footer drift across 11 commits (~249+ cumulative streak preserved); `is_back_recorded` LOCK L3 UNTOUCHED — empirical recon FALSIFIED the prior orchestrator boundary-semantic hypothesis

**Integration-merge at `c15633d`** (branch `phase13-t2-sb2-foundation-primitives` via `--no-ff`; 11 implementer commits = 5 task-impl T-A.2.1 → T-A.2.5 (smoothing at `83f6d13` + zigzag at `20ad818` + candidate windows at `66f8db9` + volume at `384bbf2` + current_stage at `9eeedf2`) + 1 code-quality follow-up at `c46170c` + 1 T-PT9 fix at `ce091a6` + 1 closer T-A.2.6 at `2f79207` + 2 Codex-fix bundles (R1 at `cb3119d` + R2 at `6392e0c`) + 1 return report at `63a66de`). Operator-paired S2 gate PASS at `c15633d` post-merge (orchestrator-driven REPL smoke against real CVGI bars; all 5 primitives produce finite outputs + plausible swing/volume sequences + `monotonic_narrow=True` mode demonstrably differs from `False` on real noisy data).

**Codex chain shape**: pre-Codex CLEAN (17th cumulative validation; APPROVED_FOR_CODEX verdict) → R1 0C/5M/5m (3 Majors RESOLVED + 3 Majors ACCEPT-WITH-RATIONALE + 5 Minors mixed) → R2 0C/0M/4m **NO_NEW_CRITICAL_MAJOR** (4 Minors closed inline at `6392e0c`). Final verdict: **NO_NEW_CRITICAL_MAJOR at R2** (within MIN..MAX rounds band). **3 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks (all V2-bankable spec amendments)**:
- **R1 M#1** `current_stage(conn, ticker, asof_date)` signature widening — DB-backed wrapper requires `conn` per Phase 4 evaluation surface read; spec §5.1.5 line 526 API sketch omits it. Spec amendment flagged for T2.SB3 brainstorming.
- **R1 M#2** `generate_candidate_windows(..., *, ticker, timeframe)` keyword-only widening — `CandidateWindow` dataclass requires both per spec lines 498-499; spec §5.1.3 line 494 API sketch omits. Spec amendment flagged for T2.SB3.
- **R1 M#4** `current_stage 'undefined'` collapses 4 conditions — V1 LOCK per spec line 523 "thin wrapper"; V2 can distinguish.

**T-PT9 (Phase-9 calendar-drift fix) — recon-first VERIFIED orchestrator hypothesis**:
- Brief §1.2 hypothesis (calendar-drift, NOT `is_back_recorded` boundary semantic): CONFIRMED at implementer Step 1 recon. Today 2026-05-20 minus hardcoded `"2026-05-12"` = 8 days > 7-day threshold; `is_back_recorded` strict-`>` IS correct as written.
- Fix scope: 2 test files (`tests/integration/test_phase9_full_happy_path.py:291` + `tests/integration/test_phase9_end_to_end.py:401,753`) replace hardcoded date with `(date.today() - timedelta(days=2)).isoformat()` dynamic anchor.
- NEW calendar-drift-proof regression test at `tests/integration/test_phase9_end_to_end.py:729` (`test_account_snapshot_today_minus_2_days_is_not_back_recorded`) — calendar-drift-proof via `date.today()` arithmetic; passes regardless of wall-clock run day.
- `swing/trades/account_equity_snapshots.py:49-63` `is_back_recorded` function UNTOUCHED per LOCK L3.
- Same lesson family as L-E2 banked at Phase 12.5 #3 T-3.5 ("time-dependent fixture calendar-buffer ≥7d"); no NEW CLAUDE.md gotcha needed (existing L-E2 covers).

**Pure-function discipline preserved** (`swing/patterns/foundation.py` LOCK L2): all 4 DB-token occurrences are in `current_stage` wrapper (lines 746/763/778) — all READS via SELECT on Phase 4 evaluation surface; ZERO writes; ZERO global state; ZERO side-effects.

**3 frozen dataclasses with `__post_init__` Literal[...] frozenset validation** preserved (honoring cumulative CLAUDE.md gotcha "`Literal[...]` not runtime-enforced" forward-binding from T-A.1.5b R3 M#1): `Swing` (`_SWING_DIRECTIONS`) + `CandidateWindow` (`_CANDIDATE_TIMEFRAMES`) + `VolumeSegment` (`_ANCHOR_SEARCH_METHODS` indirect at function entry).

**Cross-bundle pin planted**: `test_foundation_primitives_consumed_by_detectors_invariant` at `tests/patterns/test_foundation_integration.py:231-256` per plan §H.3 line 2617 + brief §4.1 #8. Un-skip schedule: T2.SB3 (VCP + flat_base + cup_with_handle detector dispatch) + T2.SB4 (high_tight_flag + double_bottom_w). Test body raises `pytest.fail` so accidental un-skip without implementing detector wiring fails loudly.

**7 forward-binding lessons banked for T2.SB3 inheritance** (per return report §4):
1. **Vectorize EMA + ma_crossover hot-paths** — Codex R1 Important #3 + #7 deferred. EMA via `pandas.Series.ewm(span=window, adjust=False).mean()`; ma_crossover via boolean mask. Both O(n) algorithmically but current Python loops will dominate detector wall-clock at T2.SB3 scale.
2. **Per-mode `anchor_date` contract** — `generate_candidate_windows` emits 3 modes with DIFFERENT anchor_date semantics: `zigzag_pivot` = inferred base START; `ma_crossover` = trigger event date (NOT base start); `high_low_breakout` = breakout confirmation bar (NOT base start). T2.SB3 detectors consuming non-zigzag_pivot modes MUST perform their own backward-slicing from anchor_date to assemble base context.
3. **Shared NaN sanitizer** at `swing/patterns/_sanitize.py` (or extend an existing helper) — yfinance/Schwab archives carry NaN holiday-adjacent rows; foundation primitives reject NaN at entry; T2.SB3 ships a shared sanitizer to drop NaN bars before invoking primitives.
4. **Realistic OHLC fixtures** — some foundation unit tests use H==L==Close shortcuts; T2.SB3 detector tests MUST use realistic OHLC fixtures with H > Close > L divergence + Volume > 0. T-A.1.7 silver corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` supplies real-shape fixtures.
5. **Spec amendment for `current_stage` + `generate_candidate_windows` signatures** — Codex R1 Major #1 + #2 ACCEPT. T2.SB3 brainstorming proposes spec amendments to §5.1.3 + §5.1.5 to acknowledge implementer-faithful widened signatures.
6. **Cross-bundle pin un-skip discipline** — T2.SB3 dispatch brief checklist MUST cite the pin + un-skip step (remove `@pytest.mark.skip` decorator; add detector module imports; assert call-args).
7. **`VolumeSegment.swing_index` provisional** — Codex R1 Minor #5. Field is implementer-added (not spec-defined); T2.SB3 confirms whether detector evidence-trail needs it or it should be stripped.

**1 NEW V2 candidate banked** (per operator-orchestrator scope conversation 2026-05-20 PM post-merge):
- **`swing data fetch <ticker> --period <p> --window-days <n>` convenience CLI** — wraps `OhlcvCache.get_or_fetch(conn, ticker, window_days=n)` for ad-hoc operator data access. Centralizes the source-routing decision (Schwab production ladder → yfinance fallback under sandbox/degraded) at the cache layer; one-off REPL/script work doesn't bypass production-routing via direct `yfinance.Ticker().history()` calls. Banked from S2 gate retrospective where the orchestrator-driven smoke script took the yfinance-direct shortcut; future ad-hoc smokes should route through the ladder. Operator-paced; standalone V2 dispatch when prioritized.

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across all 11 commits (~249+ project-cumulative; verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches).
- C.C lesson #6 17th cumulative validation: CLEAN (pre-Codex orchestrator-side review APPROVED_FOR_CODEX before Codex MCP invocation).
- Schema v20 UNCHANGED (T2.SB2 + T-PT9 are pure-logic + test-only; no migration work).
- Baseline 5149 → 5184 fast (+35 net; +60 new tests minus 2-previously-failing-now-passing minus net delta from fix iterations).
- Ruff 0 E501 preserved.

**`is_back_recorded` gotcha framing REVISION (carried in this housekeeping commit)**: the CLAUDE.md line-3 mention of "2 pre-existing Phase-9 TZ-drift failures banked" added at `2746bbb` HEAD is REMOVED (now CLOSED via T-PT9). The mis-framing of root cause as `is_back_recorded` UTC-vs-HST boundary inequality is RETRACTED — the function is correct as written; root cause was test-fixture calendar-drift only. No NEW CLAUDE.md gotcha added (existing L-E2 banked at Phase 12.5 #3 T-3.5 covers the lesson family).

---

## 2026-05-20 Phase 13 T3.SB1 SHIPPED at `48c6bc6` — entry auto-fill via Schwab Trader API at trade-entry form-render time; fill_origin enum widened from 2 → 5 values; hidden audit anchors with 4-tier rejection ladder + `claimed_auto_fill` anti-forgery gate; 5 Codex rounds NO_NEW_CRITICAL_MAJOR at R5 with 4 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks; 14th cumulative C.C lesson #6 BANKED CLEAN; +67 fast tests (4939 → 5006 on branch; final on-main post-T2.SB1-merge 5149 with cross-bundle pin un-skip); +2 slow Schwab E2E tests; ZERO Co-Authored-By footer drift across 10 commits; T3.SB1 branched off T2.SB1's T-A.1.1 commit `4cfd5f2` per OQ-12 Option E (verified at `tests/data/test_phase13_t3_sb1_prerequisite.py:test_t_a_1_1_sha_is_branch_base`)

**Integration-merge at `48c6bc6`** (branch `phase13-t3-sb1-entry-auto-fill` via `--no-ff`; 10 implementer commits = 1 recon+prerequisite test (T-B.1.1 at `2f987a9`) + 5 task-impl (T-B.1.2 service module + T-B.1.3 form-render integration + T-B.1.4 entry_post audit columns + T-B.1.5 slow E2E + T-B.1.6 closer at `9f77871` / `e86658b` / `b8de30e` / `cf16cea` / `d20d801`) + 4 Codex-fix bundles (R1 + R2 + R3 + R4 at `1908d7f` / `a966a57` / `1ad24a1` / `ea067f7`)).

**Codex chain shape**: pre-Codex CLEAN (14th cumulative validation; 1 V2-bankable observation) → R1 1C/5M/2m (1 Accepted V1 threat model + 3 Resolved + 2 Accepted project convention) → R2 0C/3M/1m (3 Resolved + 1 Resolved) → R3 0C/2M/1m (2 Resolved + 1 Resolved) → R4 0C/2M/1m (1 Resolved + 1 Accepted + 1 Resolved) → R5 **NO_NEW_CRITICAL_MAJOR** with 0C/0M/2m V2-banked. Final verdict: **NO_NEW_CRITICAL_MAJOR at R5**. **4 TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks**: R1 Critical (V1 threat model — hidden anchor JSON transport is acceptable for single-operator deployment; V2 architectural hardening banked) + R1 Major #4 (VM does NOT inherit `BaseLayoutVM`; project convention is field-duplication per CLAUDE.md gotcha; 5 prior VMs all duplicate — V2 VM-inheritance refactor banked) + R1 Major #5 (Schwab Trader API lookback width; V2 widen-to-GTC/staged-orders banked) + R4 Major (specific to project convention).

**3 NEW CLAUDE.md gotchas added this housekeeping** (per T3.SB1 forward-binding lessons): schema-version-aware INSERT for newly-widened columns + hidden anchor 4-tier rejection ladder + recovery form anchor-clear discipline. Each banked with file:line references to the canonical implementation pattern (`swing/data/repos/fills.py:51-53` for schema-version-aware INSERT; `swing/web/routes/trades.py:899-910` for `_reject_anchor` helper; `swing/web/routes/trades.py` recovery-form path for anchor-clear).

**Schwab integration discipline verified** (per brief §"Schwab integration discipline" watch items): (a) `apply_overrides(cfg)` at handler entry; (b) `resolve_credentials_env_or_prompt(allow_prompt=False)` BINDING (form-render-time prompts would block HTTP handler); (c) `construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature; (d) `trader.get_account_orders(surface='trade_entry')` (surface CHECK widened at v20 to include `trade_entry` + `trade_exit`); (e) HTMX gotcha trinity preserved (hx-headers propagation); (f) base-layout VM banner pin populated; (g) Sandbox + DEGRADED + PROVISIONAL short-circuits BEFORE Schwab client construction.

**`fill_origin` enum all 5 V1 values exercised end-to-end**: `schwab_auto` + `schwab_auto_then_operator_corrected` + `operator_typed` + `tos_import` + `imported_legacy` (last 2 existing pre-Phase-13; first 3 new at T-A.1.1 v20 migration).

**Cross-bundle pin un-skip at T3.SB1 merge**: `test_schema_version_v20_invariant` at `tests/data/test_v20_migration.py:817` un-skipped per plan §H.3 row 2 (skip count 6 → 5).

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across all 10 commits (~221+ cumulative; verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches).
- C.C lesson #6 14th cumulative validation: CLEAN.
- Schema v20 UNCHANGED across T3.SB1 chain (T-A.1.1 landed v20 at T2.SB1's first commit `4cfd5f2`).
- Baseline 4939 → 5149 cumulative across T2.SB1 + T3.SB1 + cross-bundle pin un-skip; ruff 0 E501 preserved.

**5 V2 candidates banked from T3.SB1 Codex rounds**:
- **V2 hidden-anchor architectural hardening** (R1 Critical #1 ACCEPT) — replace hidden `schwab_source_value_json` JSON transport with `schwab_api_call_id` server-side audit-row lookup. 30-50 LOC dispatch. Closes the V2 threat model where a contributor implementing similar surfaces could trip on the hidden-JSON anti-pattern.
- **VM inheritance refactor** (R1 Major #4 ACCEPT) — all 6 base-layout VMs inherit from `BaseLayoutVM` in a single sweep. Closes the field-duplication tax across `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`, and now `TradeEntryFormVM`.
- **Schwab Trader API lookback widening** (R1 Major #5 ACCEPT) — expand `get_account_orders` lookback to cover GTC orders + staged orders for entry auto-fill matching against the operator's pending-order book.
- **Fractional-share support** (R1 Minor #1 banked) — replace `int(quantity)` truncation in 6+ adapters; preserve operator-entered fractional positions through Schwab quantity normalization.
- **R5 banked observations** (R5 0C/0M/2m) — 2 minor V2 observations; specific text in return report §"Codex review history" R5 entry.

---

## 2026-05-20 Phase 13 T2.SB1 SHIPPED at `b00597c` — dev-time labeling infrastructure + v20 schema migration + Codex 2nd-reviewer subagent definition + operator-paired T-A.1.7 corpus (13 gold / 21 silver across 5 V1 pattern classes); 3 Codex rounds NO_NEW_CRITICAL_MAJOR at R2 + R3 CLEAN with ZERO Critical entire chain; 16th cumulative C.C lesson #6 BANKED CLEAN; +153 fast tests (4939 → 5092 pre-T3.SB1-merge; cumulative 5149 post-T3.SB1); ZERO ACCEPT-WITH-RATIONALE on R1+R2+R3 technical findings; ZERO Co-Authored-By footer drift across full T-A.1.1 → T-A.1.8 + T-A.1.5b hotfix + T-A.1.7 corpus chain (~32 commits); T-A.1.7 corpus commit at `bd0775f` operator-acknowledged 13/25 deviation accepted

**Integration-merge at `b00597c`** (branch `phase13-t2-sb1-dev-time-labeling-infra` via `--no-ff`; full T-A.1.1 → T-A.1.8 + T-A.1.5b hotfix + T-A.1.7 corpus chain). **Full commit chain** spans T-A.1.1 (`4cfd5f2` v20 migration; the OQ-12 Option E branch-base SHA for T3.SB1) → T-A.1.1b (`25eb4b3` repo CRUD modules) → T-A.1.2 (pattern-labeler Claude Code subagent definition) → T-A.1.3 (labeling + Codex glue) → T-A.1.4 (cassette infrastructure) → T-A.1.5 (`swing patterns label-exemplars` CLI subcommand) → T-A.1.6 (`/patterns/exemplars` web surface) → T-A.1.7 operator-paired labeling session (briefing at `caa628f`; corpus commit at `bd0775f`) → T-A.1.5b hotfix (4 commits at `3144978` / `cc2f7cc` / `4b92e05` / `43385b0` closing 3 defects + 1 scaffolding gap surfaced at T-A.1.7 abort; 4-round Codex closure at `ee595aa` / `846fc8b` / `54a0490` / `abc8411` then return report at `b461f03`) → T-A.1.8 closer (brief at `15579eb` with amendment at `67be64d` banking precursor 3-dip pattern; random-15% Codex 2nd-reviewer dispatch wiring at `f799eec`; cassette-mode E2E at `1c99262`; Deficiency 2 + 3 fixes at `8c650b6` / `85cb6fa`; full-suite verification at `79a3816`; Codex R1 + R2 fixes at `8066a74` / `211bdae`; final return report at `9904e8a`).

**Codex chain shape (T-A.1.8 closer; ZERO Critical entire chain)**: pre-Codex CLEAN (16th cumulative validation; 2 Minor observations — Deficiency 2 semantic pivot well-documented + brute-force RNG probe simplified inline at `7d5c4c1` saving a Codex round) → R1 0C/3M/2m (ALL closed inline at `8066a74`) → R2 0C/0M/2m **NO_NEW_CRITICAL_MAJOR** with both Minors closed at `211bdae` → R3 0C/0M/0m CLEAN verification round. Final verdict: **NO_NEW_CRITICAL_MAJOR at R2; R3 CLEAN.** ZERO Critical findings entire T-A.1.8 chain. (T-A.1.5b separately ran 4 Codex rounds; combined total across T-A.1.5b + T-A.1.8 = 7 Codex rounds.)

**Three highest-leverage T-A.1.8 fixes** (per return report §"Codex review history"): (1) R1 Major #1 strict bool check — `bool(response_raw["agreed"])` at CLI silently coerced truthy non-bool (`"false"` string → True); fixed with strict `isinstance(..., bool)` check at CLI boundary + `CodexReviewResponse.__post_init__` runtime-validate (defense-in-depth per T-A.1.5b R3 M#1 `Literal[...]` family); (2) R1 Major #2 audit-trail preservation in COALESCE pivot — relabel-to-gold COALESCE clobbered original `proposed_pattern_class`; fixed via SELECT-then-branched-UPDATE in caller's `with conn:` block (no TOCTOU); relabel-present branch captures `gold_promotion_original_proposed_pattern_class` + `gold_promotion_corrected_pattern_class` + `gold_promotion_at` into `labeler_evidence_json` BEFORE the COALESCE; (3) R1 Major #3 filter-chain exercise — cassette E2E test only ran the sentinel-leak audit; the `codex_mcp_vcr_config()` filter chain was never actually exercised; fixed with new `test_codex_mcp_vcr_filter_chain_redacts_planted_sentinels` constructing synthetic request+response carrying every sentinel shape + asserting all redacted (pre-empts the V2 regression where a contributor records a real-MCP-HTTP cassette without the filter chain attached).

**Schema v20 LANDED at T-A.1.1** (`4cfd5f2`; OQ-12 Option E branch-base SHA for T3.SB1). Migration at `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql`. New tables + widenings: `pattern_exemplars` (3-column refactor with 5 numbered cross-column CHECK invariants schema-defending the labeling matrix) + `chart_renders` (cache table) + `pattern_evaluations` (detector run output cache) + `watchlist_close_track_flags` + widenings `fills.fill_origin` 2 → 5 values + `schwab_api_calls.surface` widening to include `trade_entry` + `trade_exit`. **8 v20 schema-CHECK + Python-constant + dataclass-validator atomic triples preserved** (per cross-bundle pin at `test_v20_atomic_landing_python_constants_validators_paired` un-skipping at T4.SB closer per plan §H.3).

**Defect closures (T-A.1.8)**:
- **Deficiency 1 (T-A.1.6 template rendering)** — DEFERRED per closer brief §1.2 at T2.SB1 ship; **operator chose Option B 2026-05-20: FOLDED INTO T2.SB6 as NEW task T-A.6.6b** (plan §G.9 amended same day; T2.SB6 task count 7 → 8; closer S4b gate added). Closes the open operator-decision item from T-A.1.8 brief.
- **Deficiency 2 (relabel-to-gold preserves `final_pattern_class`)** — CLOSED via semantic-equivalent COALESCE-into-related-column pivot at state transition (`UPDATE pattern_exemplars SET proposed_pattern_class = COALESCE(final_pattern_class, proposed_pattern_class), final_pattern_class = NULL ...`); operator's class choice survives gold promotion + Invariant #1 holds (`final_decision='confirmed' AND final_pattern_class IS NOT NULL` precluded by CHECK) + NO schema migration. Brief's literal `preserve final_pattern_class as-is` prescription was schema-incompatible per CHECK constraint at migration line 109-114; closer brief §1.2 implementer-VERIFIES + may-revise allowance honored. **NEW CLAUDE.md gotcha**: brief-prescription-vs-schema-CHECK collision.
- **Deficiency 3 (HTF + flat_base structural_evidence_schema sub-window fields)** — CLOSED. Spec §5.5 names the post-pole HTF sub-window `consolidation_*` per criterion #3 + #4 lock strings (NOT `flag_*` as operator's colloquial terminology). Locked at `tests/patterns/test_spec_static.py::test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming`. **NEW CLAUDE.md gotcha**: HTF naming `consolidation_*` not `flag_*`.

**T-A.1.7 operator-paired corpus disposition**: 34 rows in operator's local `~/swing-data/swing.db` (13 gold / 21 silver across 5 V1 classes); committed to repo at `bd0775f`. Manifest at `data/phase13-t2-sb1-corpus/README.md`; JSONL dump at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl`. **Operator-acknowledged deviation**: 13/25 gold (52% of target). Orchestrator accepted: all 5 V1 classes have positive exemplars; corpus sufficient bootstrap material for T2.SB3+/SB4 detector calibration. Operator's local DB ran `swing db-migrate` during T-A.1.7 paired session; backup at `~/swing-data/backups/swing-20260519T070446.db`; production DB now aligned with main at schema v20.

**Cross-bundle pin disposition for `test_flag_classifier_integration.py:21`** (banked V2 dispatch): the fixture loader at `tests/evaluation/patterns/_fixtures.py:load_labeled_fixtures` expects paired `<name>.csv` + `<name>.json` files at `tests/evaluation/patterns/fixtures/` with labels `"flag"` or `"none"` (older Phase 3e/7 chart-pattern flag-v1 classifier infrastructure). The T-A.1.7 corpus has a DIFFERENT shape (JSONL with 5 V1 detector pattern classes; no paired OHLCV CSVs). **NEW CLAUDE.md gotcha**: cross-bundle pin fixture-shape mismatch silently extends the pin window. V2 disposition options: (a) port the Phase 3e flag-v1 classifier to consume the Phase 13 corpus shape (likely T2.SB3+/SB4 territory); OR (b) retire `test_flag_classifier_integration.py` as superseded by Phase 13 detector test suite.

**9 forward-binding lessons banked** (per T2.SB1 final return report §"Forward-binding lessons banked"):
1. **Synthetic-fixture-vs-production-emitter shape drift** — FOURTH CUMULATIVE INSTANCE (T-A.1.5b CLI dict→str + T-A.1.8 cassette filter chain). NEW CLAUDE.md gotcha promoted.
2. **`Literal[...]` type hints are NOT runtime-enforced** (T-A.1.5b R3 M#1). NEW CLAUDE.md gotcha promoted.
3. **Service-layer ValueErrors must be wrapped at CLI boundary** (T-A.1.5b R4 M#1). NEW CLAUDE.md gotcha promoted.
4. **Cup-with-handle rounded-vs-V hard gate** caused 4 of 5 cup dispatches to fail by sub-1% margins. T2.SB3 should widen OR downgrade to scoring penalty.
5. **HTF consolidation tightness** — widen for high-magnitude-pole cases.
6. **VCP monotonic-tightening hard gate** — consider 1-violation tolerance.
7. **SNAP reproducibility variance** — subagent non-determinism; Codex 2nd-reviewer SHOULD catch.
8. **TSM 4-framing exhausted** — V2 detector enrichment candidate.
9. **Precursor 3-dip "early identifier" pattern** — banked at T-A.1.8 brief amendment per operator TSM/TGT/SNAP chart references. Two surfaces: (a) labeling-window-scoped-to-base contract for T2.SB3+/SB4 detector specs; (b) NEW V2 detector surface.

**4 V2 candidates banked from T2.SB1 Codex rounds + dispatch**:
- **Precursor 3-dip "early identifier" detector** — banked at T-A.1.8 brief amendment per operator's TSM/TGT/SNAP annotated chart references. Two design surfaces: (a) labeling-window-vs-setup-quality separation as detector-spec contract; (b) NEW V2 detector surface scoring precursor uptrend + dip-stair-step quality. For T2.SB3+/SB4 detector calibration OR late-Phase-13 sub-bundle.
- **Deficiency 1 (T-A.1.6 template rendering: chart + per-criterion table + narrative)** — **FOLDED INTO T2.SB6 as NEW task T-A.6.6b per operator decision 2026-05-20.** Reuses `swing/web/charts.py:render_theme2_annotated_svg` renderer + `chart_renders` cache landed at T-A.6.1 + T-A.6.2; strictly VM + template enhancement consuming existing infrastructure. T2.SB6 task count 7 → 8; plan §G.9 amended in same commit. No standalone V2 dispatch needed.
- **`sort_keys` byte-original preservation** (T-A.1.5b R1 Minor #1) — V2 audit-trail enhancement if byte-identical preservation later required.
- **Schwab cassette runbook for pattern-labeler** — `scripts/record_pattern_labeler_cassettes.py` scaffold exists but not invoked at T2.SB1 ship. V2 dispatch when operator-paired session enables Schwab API live recording.
- **Weekly timeframe auto-fetch** in labeling CLI — V1 supports `daily` only; V2 widening for weekly bars when detectors land that need weekly context.

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across full T-A.1.1 → T-A.1.8 + T-A.1.5b hotfix + T-A.1.7 corpus chain (~32 commits) (~221+ cumulative).
- C.C lesson #6 16th cumulative validation: CLEAN (T-A.1.8 closer dispatch); 15th = T-A.1.5b hotfix dispatch.
- Schema v20 LANDED at T-A.1.1; unchanged through T-A.1.8.
- Baseline 4939 → 5092 fast (+153 cumulative across T2.SB1 chain) + 3 slow E2E / 0 ruff E501 / production ZERO open discrepancies (post-merge predicate; 2 TZ-drift failures are pre-existing Phase 9 territory).

---

## 2026-05-20 Metrics dashboard hooked-up audit TODO — FOLDED INTO T4.SB as NEW task T-D.6b (operator decision 2026-05-20)

**Disposition:** Operator decision 2026-05-20 (same day as bug surfacing): FOLDED INTO T4.SB usability triage closer as NEW task T-D.6b (plan §G.10 amended; T4.SB task count 7 → 8; closer S2b gate added; dispatch sequence diagram + total task count 72 → 73 updated). T4.SB chosen over standalone or T2.SB6 fold-in because (a) T4.SB is the explicit "usability triage + audit" closer per Theme 4; (b) metrics-page bug fits the audit pattern; (c) T2.SB6 already absorbs Deficiency 1 fold-in + 9th metric tile landing — minimal cross-bundle scope creep; (d) T4.SB's per-tile audit covers the 9th tile from T2.SB6 in the same sweep.

**Bug surfaced 2026-05-20** (operator-witnessed at metrics dashboard inspection; preserved verbatim for T-D.6b implementer recon): On `/metrics` dashboard the **hypothesis-progress card** shows "Sub-A+ VCP-Not-Formed" at **0/5**, but the main `/dashboard` page reports the same hypothesis at **5/5**. Discrepancy = metrics-page card is NOT hooked up to the same DB query (or filter predicate) as the dashboard's hypothesis surface — the metrics-page query returns 0 where the dashboard query returns 5.

**Scope of investigation + fix dispatch** (operator-paced; recon-first; ABSORBED INTO T-D.6b task spec at plan §G.10):
1. **Specific bug fix**: trace the hypothesis-progress card's query path at `swing/web/routes/metrics.py` + `swing/web/view_models/metrics/` + `swing/metrics/` consumer; identify why the count diverges from `/dashboard`'s. Likely candidates: (a) different session-anchor predicate (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`); (b) different `bucket`/`status` filter; (c) different join key (e.g., joining via stale `evaluation_run_id` vs latest); (d) joining `pattern_evaluations` instead of the canonical hypothesis-status source. Compare line-by-line with the dashboard's hypothesis VM query.
2. **Audit ALL metric tiles on `/metrics`**: enumerate every metric surface (8 existing + 9th planned at T2.SB6 `/metrics/pattern-outcomes` per OQ-10); for each, locate the DB query, compare against the canonical equivalent on dashboard/CLI; document any divergences. Per operator: "Probably worth a review of all of the metrics to ensure they are correctly hooked up to the DB."
3. **Add discriminating regression tests**: per-metric round-trip integration test asserting metric tile count equals canonical-source count for known-good fixture state (mirrors the Phase 8 `cfacbc5` round-trip test pattern that closes session-anchor read/write mismatches; same family as the existing CLAUDE.md gotcha "Session-anchor read/write mismatch").

**Forward-binding lesson family hypothesis** (pre-recon): session-anchor read/write mismatch family — recurring across weather lookup + Phase 8 daily-mgmt badge + Phase 13 T1.SB0 in-progress-bar inequality. Metrics-page query may consume a different session anchor or stale `evaluation_run_id` / `pipeline_run_id` than the dashboard surface. Implementer recon will VERIFY before fixing.

**Operator decision RESOLVED 2026-05-20**: batch with T4.SB usability triage closer as NEW task T-D.6b. Closes the open operator-decision item from the bug-surfacing moment same day. T-D.6b task spec at plan §G.10 contains the full implementer-facing recon-first + 6-step workflow + watch items + acceptance criteria. No standalone dispatch needed.

**Files likely in scope** (pre-recon best guess; implementer VERIFIES):
- `swing/web/routes/metrics.py`
- `swing/web/view_models/metrics/*.py` (including the `hypothesis_progress.py` VM if one exists OR the metric tile assembly point)
- `swing/web/templates/metrics/*.html.j2`
- `swing/metrics/*.py` (consumer layer)
- `swing/web/view_models/dashboard.py` (canonical comparator)
- `tests/web/test_routes/test_metrics.py` (extend with audit regression tests)

**Pre-empt forward-binding**: Phase 13's T2.SB6 plan §G.9 T-A.6.5 already mandates `PatternOutcomesVM` extends `BaseLayoutVM` + populates banner pin fields + composes with Phase 10 cohort architecture; this audit MAY surface as a forward-binding watch item for T2.SB6 that propagates to all existing metric tiles.

---

## 2026-05-19 Phase 13 T1.SB0 gate-fix SHIPPED at `d772f23` — closes Schwab `price_history` minute-default footgun discovered at S3 visual gate; brief hypothesis EMPIRICALLY FALSIFIED at T-GF1 recon against operator's real CVGI archive; root cause at Schwab ladder layer NOT `read_or_fetch_archive`; 3 Codex rounds NO_NEW_CRITICAL_MAJOR with ZERO Critical + ZERO Major entire chain; 6 minors all wording-precision V2-bank doc clarifications (4 resolved + 2 banked V2-F); +4 fast tests = 4935→4939; T1.SB0's 2 banked ACCEPTs preserved untouched; C.C lesson #6 12th cumulative validation CLEAN; ZERO Co-Authored-By footer drift across 6 gate-fix commits; S3 PASS post-merge via operator-paired session; auto-recovery of contaminated `*.schwab_api.parquet` proceeds on next Schwab daily fetch; T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED with dispatch briefs already committed at `4a52f3a`

**Integration-merge at `d772f23`** (branch `phase13-t1-sb0-gate-fix` via `--no-ff`; 6 implementer commits = 1 recon (T-GF1 at `d440578`) + 2 task-impl (T-GF2.1 at `69da867` + T-GF2.2/T-GF3 at `6f5615d`) + 2 Codex-fix doc clarifications (R1 recovery-posture clarification at `b329cf8` + R2 wording precision at `5fb3d58`) + 1 return report (`2dea0a9`)).

**Codex chain shape (ZERO Critical + ZERO Major entire chain)**: R1 0C/0M/2m (#1 recovery-posture wording → FIX `b329cf8`; #2 T-GF3 doesn't pin write_window cleanup → ACCEPTED V1-scope) → R2 0C/0M/2m (#1 yfinance-fallback persistence-path wording → FIX `5fb3d58`; #2 V2-F multi-signal heuristic → FIX `5fb3d58`) → R3 0C/0M/2m (#1 row/date-count ratio caveat for collapsed remnants → BANKED in V2-F; #2 audit-history feasibility caveat → BANKED in V2-F). Final verdict: **NO_NEW_CRITICAL_MAJOR R1 + R2 + R3 all clean**. **ZERO Critical + ZERO Major findings entire 3-round Codex chain** — brief §2.5 "ZERO ACCEPT-WITH-RATIONALE preferred" target met; all 6 minor findings were wording-precision nits on recon doc's recovery posture (§4.C) and V2-F bank (§4.D) — both V1-out-of-scope concerns. The actual production fix (T-GF2.1 + T-GF2.2) and discriminating regression test (T-GF3) emerged from Codex review WITHOUT a single Critical or Major finding.

**Brief hypothesis EMPIRICALLY FALSIFIED at T-GF1** (recon §1). Brief §1.2 hypothesis (`read_or_fetch_archive` weekly-refresh / `archive_history_days` semantic divergence) FALSIFIED by side-by-side inspection of operator's actual CVGI archive files at `~/swing-data/prices-cache/`: legacy `CVGI.parquet` had **1260 unique daily bars correctly fresh** + ending 2026-05-18; Shape A `CVGI.schwab_api.parquet` had **2780 rows × only 10 unique dates** (~278 minute-bars per date). The legacy `read_or_fetch_archive` was functioning correctly; the regression was downstream of it. Brief §1.2 "implementer VERIFIES + may revise" allowance was load-bearing — had implementer skipped T-GF1 + jumped to fix-shape A/B/C from brief, the fix would have landed on WRONG code path and the regression would persist.

**Real root cause at Schwab ladder layer** (recon §2):
- `swing/integrations/schwab/marketdata_ladder.py:417-426` — `fetch_window_via_ladder` invoked `get_price_history(client, conn, ticker, start_dt=None, end_dt=None, ...)` WITHOUT period/frequency kwargs.
- `swing/integrations/schwab/marketdata.py:329-405` — `get_price_history` forwards all-None to schwabdev.
- `reference/schwabdev/api-calls.md:425-435` — Schwab API server-side defaults to `(periodType=day, period=10, frequencyType=minute, frequency=1)` when kwargs unspecified — returns 10 days of 1-minute intraday candles.
- `swing/integrations/schwab/mappers.py:817-828` — mapper bucketizes each per-minute candle via `.date().isoformat()` → ~278 bars per date.
- `swing/data/ohlcv_archive.py:281-369` — `write_window`'s `drop_duplicates(subset=["asof_date"], keep="last")` silently overwrites daily Shape A archive content with last-minute-of-day intraday bar.
- `swing/cli_schwab.py:1100-1111` — CLI verify path ALREADY explicitly passes `period_type='month', period=1, frequency_type='daily', frequency=1` — proving architectural intent IS daily bars; `_bars_hook` callsite simply forgot to mirror.

**Fix shape D applied** (revises brief §1.3 A/B/C alternatives per §1.2 implementer-VERIFIES + may revise allowance):
1. `swing/integrations/schwab/marketdata_ladder.py` — extend `fetch_window_via_ladder` signature with `period_type` / `period` / `frequency_type` / `frequency` kwargs (default `None`; backward-compatible); forward verbatim to `get_price_history`.
2. `swing/pipeline/runner.py:_bars_hook` — pass `period_type="year", period=5, frequency_type="daily", frequency=1` ("5 years of daily bars" matching `cfg.archive.archive_history_days ≈ 1260 trading days`).
3. `tests/pipeline/test_yf_window_fallback_returns_full_archive.py` — absorb new kwargs via `**_extra_kwargs` (additive-stub backward compat).
4. `swing/web/ohlcv_cache.py` / `swing/data/ohlcv_archive.py` / `swing/integrations/schwab/marketdata.py:get_price_history` — UNCHANGED.

**T1.SB0 banked ACCEPTs preserved untouched** per §6 watch item #3:
- R1 M#1 OHLCV scope-clarification (CLAUDE.md gotcha scoped to dashboard) — UNCHANGED. Fix touches `_bars_hook` only; chart-target composition at `_step_charts` unchanged.
- R1 M#2 V2-A breaker non-participation — UNCHANGED + V2-A bank still valid. Fix does NOT add breaker participation to the bars path.

**CLAUDE.md gotchas honored**:
- "Hook fallback window-completeness" (NEW per T1.SB0 housekeeping `dc0cfea`) — preserved. Hook returns full Schwab/yfinance archive; consumer (cache) slices to `window_days=200` unchanged.
- "Session-anchor inequality discipline" (NEW per T1.SB0 housekeeping `dc0cfea`) — preserved. `_fetch_bars_window` strict-`>` predicate for backward-looking `last_completed_session(now())` anchor untouched.

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across all 6 gate-fix commits (~211+ project-cumulative streak preserved; verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches).
- C.C lesson #6 12th cumulative validation: **CLEAN — 0 pre-Codex findings absorbed; 1 advisory docstring nit no-fix** (pattern continues durably effective; matches Phase 12.5 + Phase 13 T1.SB0 precedent).
- Schema v19 UNCHANGED (gate-fix consumer-side wiring only).
- Baseline `4935 → 4939 fast` (+4; within brief §7 +1-3 envelope plus 1 additional discriminating test).
- Ruff 0 E501 on `swing/` preserved.

**Operator's contaminated `CVGI.schwab_api.parquet` auto-recovers** (recon §4.C; Codex R1 Minor #1 clarification at `b329cf8`): on next pipeline run's first successful Schwab daily fetch, `write_window`'s `drop_duplicates(subset=["asof_date"], keep="last")` causes fresh daily bars to win the 10 overlapping dates + appends ~1250 prior dates. **Recovery conditioning**: auto-cleanup REQUIRES a successful Schwab daily fetch — if Schwab is degraded for an extended period and the ladder falls back to yfinance, the contaminated `*.schwab_api.parquet` remains on disk in its minute-frequency shape until Schwab recovers. **`_bars_hook`'s return-to-cache path is UNAFFECTED** in this scenario (returns yfinance-fallback DataFrame directly to OhlcvCache; chart-step renders correctly). Operators may proactively delete contaminated `*.schwab_api.parquet` for forced re-fetch.

**S2 + S3 operator-paired gate PASS** post-merge via operator-paired session (chart rendering verified visually; no operator manual cleanup of `CVGI.schwab_api.parquet` required prior to gate; auto-recovery confirmed working). **T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED** with dispatch briefs already committed at `4a52f3a` (T2.SB1 = 267 lines; T3.SB1 = 258 lines branches off T2.SB1's T-A.1.1 first-commit SHA per OQ-12 Option E).

**NEW T-GF3 regression test** at `tests/pipeline/test_bars_hook_requests_daily_frequency.py` (2 tests; closes byte-parity test's blind spot which exercised bare `read_or_fetch_archive` branch ONLY):
- `test_bars_hook_invokes_ladder_with_daily_period_frequency_kwargs` — T-GF2.2 spy on `fetch_window_via_ladder`; asserts recorded kwargs `period_type='year', period=5, frequency_type='daily', frequency=1`. FAILS pre-fix; PASSES post-fix.
- `test_bars_hook_production_path_returns_daily_shaped_frame_no_duplicate_dates` — T-GF3 end-to-end: shape-aware stub returns daily Schwab window IF `frequency_type='daily'`, else intraday; asserts `bars_df.index.is_unique`. FAILS pre-fix; PASSES post-fix.

**NEW T-GF2.1 contract test** at `tests/integrations/test_schwab_window_ladder_daily_kwargs.py` (2 tests pinning `fetch_window_via_ladder` kwarg forwarding contract).

**2 new CLAUDE.md gotchas added in this housekeeping commit** (per recon §7 banked CAPTURE-NEED + return report §"Capture-needs" #1 + #2; operator decision 2026-05-18 PM):
1. **Schwab `price_history` minute-default footgun** — `client.price_history(symbol)` with no `periodType` / `frequencyType` kwargs defaults to 10 days of 1-MINUTE intraday bars (NOT daily); Schwab API consumers MUST explicitly pass `(year, N, daily, 1)` or `(month, N, daily, 1)`; mapper bucketizes per-minute candles into duplicate `asof_date` values; `write_window` merge `keep='last'` silently overwrites daily content. Forward-binding for T3.SB1 + T3.SB2 entry/exit auto-fill paths.
2. **Byte-parity test as algorithmic substitute for operator-visual gate is INSUFFICIENT when test fixtures bypass production data-derivation paths** — chart-bytes byte-parity test was cited as "STRONG algorithmic substitute" during T1.SB0 pre-merge QA but missed the regression because BOTH test paths consumed IDENTICAL stub fixtures via `monkeypatch.setattr("swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read)` — exercising bare `read_or_fetch_archive` branch ONLY; ladder path never invoked; test asserts "identical inputs → identical outputs" but regression is in HOW INPUTS ARE DERIVED. Same gotcha family as synthetic-fixture-vs-production-emitter shape drift (Phase 12 C.D + Phase 12.5 #2 + Phase 12.5 Q2) but with fetch-semantics drift instead of envelope-shape drift. NEVER characterize an algorithmic substitute as "STRONG" for visual gates without verifying it exercises production data-derivation path.

**V2 banks (forward-binding from gate-fix; orchestrator carries forward into V2 candidate roster)**:
- **V2-D (NEW): Defensive kwarg validation at `get_price_history`** — raise on `(start_dt=None, end_dt=None, period_type=None, period=None)` combination since it triggers Schwab's minute-default footgun. Skipped in V1 to keep gate-fix surgical.
- **V2-E (NEW): Mapper-side duplicate-`asof_date` rejection** — `map_price_history_to_window` could raise `SchwabSchemaParityError` when it observes >1 candle for same `asof_date` (signaling "caller forgot daily kwarg"). Defense-in-depth.
- **V2-F (NEW): Shape A archive backfill cleanup** — operator-paced cleanup utility for contaminated Shape A archives beyond conditional auto-recovery. Multi-signal heuristic (duplicate `asof_date` rows / row-count vs unique-date-count ratio anomalies / volume-scale per-row vs nearby legacy `.parquet` values / optional audit `schwab_api_calls` history for `endpoint='marketdata.pricehistory'` calls that omitted period/frequency kwargs). Operator-friendly UX for sustained-Schwab-outage scenarios. Codex R2 + R3 refined the multi-signal heuristic across the V2-F bank doc clarifications.

**V2 banks (NEW; surfaced 2026-05-19 at S2 post-gate-fix from operator-paired session)**:
- **PL fallback diagnostic logging** — `fetch_window_via_ladder: unexpected error from T-C.1 wrapper for PL; falling back to yfinance` is generic; needs Schwab response code + body excerpt for diagnosability. Operator-paced; could fold into Theme 4 usability triage at T4.SB.

**V2 banks (preserved from T1.SB0; carried forward)**:
- V2-A: breaker participation for the bars path (R1 M#2 ACCEPT defer).
- V2-B: per-key in-flight dedup (recon §4.B).
- V2-C: async `get_or_fetch` variant via executor for batch chart rendering at scale (recon §4.B).

**6 forward-binding lessons banked at return report §"Forward-binding lessons" for downstream sub-bundles**:
1. **Brief hypothesis verification discipline pays off.** When brief offers "implementer VERIFIES + may revise" allowance, FIRST diagnostic task MUST do real-archive inspection / shape-comparison, NOT fix-shape selection from the brief's pre-vetted options.
2. **Schwab `price_history` minute-default footgun** — CLAUDE.md gotcha promoted in this housekeeping commit.
3. **Byte-parity test as algorithmic substitute INSUFFICIENT when fixtures bypass production data-derivation** — CLAUDE.md gotcha promoted in this housekeeping commit.
4. **Pre-Codex orchestrator-side review = 12th cumulative validation, durably effective** (C.C lesson #6 CARRY). Pattern is DURABLE; continue applying.
5. **Brief-vs-implementation hypothesis divergence is a feature, not a bug, when "implementer VERIFIES" is in scope.** Brief STRUCTURE held; only the hypothesis turned out to be wrong. Future briefs SHOULD include articulated hypotheses + fix-shape options + verify-and-revise allowance.
6. **`grep <function>(` audit is reusable for any "single-callsite fix" verification.** Closing the ladder-side bug at the single callsite + extending wrapper additively was sufficient. Pattern: any "wrapper-extension + single-callsite fix" should include the grep audit as explicit pre-Codex watch item.

**Post-merge housekeeping in this commit**:
- CLAUDE.md line 3 "Current state" refresh (1,919 chars; under 2,000 threshold per size-check discipline).
- **CLAUDE.md gotchas: ADD 2 new entries** (Schwab minute-default footgun + byte-parity-test-algorithmic-substitute insufficiency).
- phase3e-todo.md new top entry (this entry).
- orchestrator-context.md current-state pointer refresh (Phase 13 T1.SB0 SHIPPED state demoted to Prior state).
- **orchestrator-context.md size-check trigger fired** (Prior state count was 10 AT cap; T1.SB0 gate-fix housekeeping demote brought count to 11; archived oldest Prior state container at original line 140 region "pre-Phase-12.5-#2-brainstorm" / Phase 12.5 #1 executing-plans SHIPPED to `docs/orchestrator-context-archive.md`).

**T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED** with dispatch briefs already committed at `4a52f3a`. T3.SB1 worktree branches off T2.SB1's T-A.1.1 first-commit SHA per OQ-12 Option E. Merge ordering T2.SB1 first; T3.SB1 second.

Worktree husk at `.worktrees/phase13-t1-sb0-gate-fix/` matches cleanup-script regex `phase\d+[-_]` — operator-paced cleanup pass post-merge.

### Predecessor (2026-05-18 PM; T1.SB0 SHIPPED)

## 2026-05-18 Phase 13 T1.SB0 SHIPPED at `418bcc8` — OhlcvCache → `_step_charts` wiring (4-task sub-bundle); closes Phase 11 Sub-bundle C R1 M#5 V1 deferral; 5 Codex rounds NO_NEW_CRITICAL_MAJOR; 2 ACCEPT-WITH-RATIONALE banks both TECHNICALLY SOUND; C.C lesson #6 11th cumulative validation CLEAN (0 pre-Codex findings); ZERO Co-Authored-By footer drift; T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED pending S2+S3 operator-paired gate

**Integration-merge at `418bcc8`** (branch `phase13-t1-sb0-ohlcv-charts-wiring` via `--no-ff`; 9 implementer commits = 1 recon (T-T1.SB0.1) + 3 task-impl (T-T1.SB0.2 + T-T1.SB0.3 + T-T1.SB0.4) + 4 Codex-fix bundles (R1+R2+R3+R4) + 1 return report).

**Codex chain shape (convergent monotonic Major taper)**: R1 0C/3M/1m → R2 0C/1M/0m → R3 0C/1M/1m → R4 0C/0M/1m → R5 0C/0M/0m NO_NEW_CRITICAL_MAJOR. ZERO Critical findings entire chain.

**Streaks preserved**:
- ZERO Co-Authored-By footer trailer drift across all 9 commits (~203+ project-cumulative streak preserved; verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches).
- C.C lesson #6 11th cumulative validation: **CLEAN — 0 pre-Codex findings absorbed** (pattern is durably effective; implementer's recon §9 pre-emptions correctly anticipated reviewer concerns; matches Phase 12.5 #3 + Phase 13 brainstorm + Phase 13 writing-plans precedent of pre-Codex catching less as project discipline matures).
- Schema v19 UNCHANGED (per L6; consumer-side wiring only; v20 lands at T2.SB1 task T-A.1.1 migration-only commit per OQ-12 Option E).
- Baseline `4925 → 4935 fast` (+10 within +20-40 plan §K projection envelope; slightly conservative because Codex-driven discriminating-test plants went into existing test files (3 modified) + 5 new test files).
- Ruff 0 E501 on `swing/` preserved.

**2 ACCEPT-WITH-RATIONALE banks — both TECHNICALLY SOUND per orchestrator-side QA review** (first ACCEPTs in Phase 13 arc but match Phase 12.5 Q2 sound-ACCEPT precedent — not blind absorption; legitimate scope-clarification + V2 deferral banking):

1. **R1 M#1 OHLCV scope = open-trade only**: the CLAUDE.md gotcha text is scoped verbatim to `build_dashboard` SMA-advisory surface (text references `build_dashboard` + trail-MA/exit-below-MA advisories + watchlist union prohibition). Pipeline `_step_charts` is NOT in the gotcha's scope; `_step_charts` has always fetched OHLCV for ALL chart targets (A+ + open + watchlist top-N) — that's the existing chart-rendering contract. T1.SB0 wires the same scope through OhlcvCache.get_or_fetch instead of legacy fetcher.get; scope unchanged. Under no-Schwab env, fallback `OhlcvCache(cfg)` is identical to legacy `read_or_fetch_archive` path. **ACCEPT banked legitimately**.

2. **R1 M#2 breaker non-participation (V2-A bank)**: chart-step never had a sliding-window breaker pre-Phase-13 (legacy `PriceFetcher.get` is direct archive read with no breaker semantics). T1.SB0 maintains parity with that pre-existing semantic. Bundle-path breaker (dashboard SMA-advisory traffic) unchanged + preserved. Per-ticker `except Exception` clause at `swing/pipeline/runner.py:1326` absorbs failures with `chart_status='fetcher_failed'`. V2-A bank carries forward for breaker participation if operator surfaces meaningful Schwab/yfinance outage modes not well-handled by per-ticker fallback. Dispatch brief watch item #7 "Sliding-window breaker preservation" wording was orchestrator-side ambiguous (preserve what? breaker for chart-step or bundle-path?); implementer correctly interpreted preserve-as-pre-Phase-13. **ACCEPT banked legitimately**.

**Codex R3 fix bundle (`bfcc2b6`) closed 2 latent defects in cache infrastructure** (both forward-binding for downstream cache work):
- `_yf_window_fallback` truncated to 60 rows under Schwab-fallback (would cap chart window depth); fixed to call `read_or_fetch_archive` directly returning full archive; discriminating test planted.
- Cached DataFrame was reference-returned creating consumer-mutation poisoning across consumers within TTL; fixed with defensive copy on BOTH store AND read; discriminating test planted.

**Plan deliverable**: 4 production-touched files + 5 NEW test files + recon doc + return report. Net delta: +154 prod LOC (runner.py +20 / ohlcv_cache.py +134 / pyproject.toml +8) + +1018 test LOC. Schema v19 UNCHANGED.

**Key shipped artifacts**:
- `swing/pipeline/runner.py` — `_step_charts` signature change (`fetcher` → `ohlcv_cache`); legacy `fetcher.get` calls replaced with `ohlcv_cache.get_or_fetch`.
- `swing/web/ohlcv_cache.py` — new `get_or_fetch(*, ticker, window_days)` public method; defensive copy on store+read; per-cache locking via `threading.RLock`; `_yf_window_fallback` calls `read_or_fetch_archive` directly returning full archive.
- `pyproject.toml` — `mplfinance>=0.12` added to `[project.optional-dependencies].dev` for chart-bytes parity gate honesty (R2 fix).
- `docs/phase13-t1-sb0-recon.md` (355 lines; recon doc with V1/V2 scope decisions + per-cache-locking discipline + shape semantics).
- 5 new test files: shape parity / wiring discriminating / concurrent-fetch no-race / chart-bytes parity / yf-window-fallback full-archive.
- 1 cross-bundle pin planted at `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py:203` (un-skips at T2.SB2 + T2.SB3 + T3.SB3 consumers per plan §H.3).

**Operator-witnessed gate**:
- **S1 (inline pytest + ruff)**: **PASS** via implementer (4935 fast pass + 0 ruff E501).
- **S2 (operator-paired `python -m swing.cli pipeline run` against production)**: **PENDING** — orchestrator drives post-merge; cassette-mode acceptable for CI; live-mode under operator-paired session.
- **S3 (chart output visual parity against pre-Phase-13 baseline)**: **PENDING** — orchestrator drives post-merge. **STRONG algorithmic substitute**: `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py::test_chart_bytes_match_between_ohlcv_cache_and_legacy_price_fetcher` PASSES asserting byte-identical PNG output between OhlcvCache + legacy paths.

S2 + S3 require operator-paired session (production data + visual chart comparison). Merge proceeds first per Phase 12.5 Q2 precedent (merge first; operator-paired gate post-merge); algorithmic chart-bytes parity test provides strong evidence the wiring is correct under both no-Schwab + with-Schwab production environments.

**7 forward-binding lessons banked at return report §"Forward-binding lessons" for downstream sub-bundles**:
1. Plan-template parameter-name drift (writing-plans dispatches should verify signatures via `inspect.signature` or grep — paraphrase from memory drifts).
2. Plan-template hardcoded literals drift (window_days=180 vs actual lookback_days=200; should reference project constant OR grep-verify against actual callsite).
3. **Backward-looking vs forward-looking session-anchor inequality** (`>` strict for backward-looking; `>=` for forward-looking). **CLAUDE.md gotcha promoted in this housekeeping commit**.
4. **Hook fallback window-completeness** — shared-infrastructure cache hooks return FULL archive; consumers slice. **CLAUDE.md gotcha promoted in this housekeeping commit**.
5. Mutable DataFrame in cache = corruption risk across consumers within TTL — defensive-copy discipline at every new cache layer.
6. Module-level binding vs source-module binding — monkeypatch at consumer namespace not source.
7. C.C lesson #6 pre-Codex review pattern: 11th cumulative validation CLEAN — pattern is DURABLE; continue applying at every executing-plans dispatch.

**Capture-needs for next sub-bundle dispatch (T2.SB1 ∥ T3.SB1 concurrent per OQ-12 Option E)**:
- T2.SB1's first-commit SHA needed by T3.SB1 worktree branch-base coordination (T3.SB1 worktree branches OFF T2.SB1's first commit, typically the v20 migration-only commit at T-A.1.1 per plan §G.1).
- Schema v20 migration lands at T2.SB1 task T-A.1.1 (atomic per plan §B.4; backup-gate `pre_version == 19` strict equality form per Phase 9 Sub-bundle A precedent).
- OhlcvCache.get_or_fetch surface stable, ready for T2.SB2 + T2.SB3 + T3.SB3 consumers.
- Defensive-copy contract: `get_or_fetch` returns a defensive copy; detector consumers can mutate freely without poisoning cache.

**V2 banks**:
- V2-A: breaker participation for the bars path (R1 M#2 ACCEPT defer).
- V2-B: per-key in-flight dedup (recon §4.B).
- V2-C: async `get_or_fetch` variant via executor for batch chart rendering at scale (recon §4.B).

**Post-merge housekeeping in this commit**:
- CLAUDE.md line 3 "Current state" refresh (1,318 → 1,878 chars; under 2,000 threshold per size-check discipline).
- **CLAUDE.md gotchas: ADD 2 new entries** (session-anchor inequality discipline by anchor direction + hook fallback window-completeness for shared cache infrastructure).
- phase3e-todo.md new top entry (this entry).
- orchestrator-context.md current-state pointer refresh (Phase 13 writing-plans SHIPPED state demoted to Prior state).
- **orchestrator-context.md size-check trigger fired** (Prior state count was 10 AT cap; T1.SB0 housekeeping demote would bring count to 11; archived oldest Prior state container (line 148, 2026-05-17 PM pre-executing-plans; ~163 lines) to `docs/orchestrator-context-archive.md`).

**T2.SB1 ∥ T3.SB1 concurrent dispatch UNBLOCKED** pending S2 + S3 operator-paired gate PASS post-merge.

Worktree husk at `.worktrees/phase13-t1-sb0-ohlcv-charts-wiring/` matches cleanup-script regex `phase\d+[-_]` — operator-paced cleanup pass post-merge.

### Predecessor (2026-05-18 PM; writing-plans)

## 2026-05-18 Phase 13 WRITING-PLANS SHIPPED at `08ce852` — 2810-line plan; 11 sub-bundles + 71 tasks; 5 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; C.C lesson #6 BINDING 10th cumulative validation (pre-Codex caught OQ-7 brief vs spec drift); ZERO Co-Authored-By footer drift; orchestrator-side QA review PASS-CLEAN; T1.SB0 executing-plans dispatch UNBLOCKED

**Integration-merge at `08ce852`** (branch `phase13-writing-plans` via `--no-ff`; 7 implementer commits = 1 initial draft (2711 lines) + 1 pre-Codex orchestrator-side review-fix (1 Critical absorbed: OQ-7 spec >> brief reconciliation) + 4 Codex-fix bundles (R1+R2+R3+R4) + 1 return report).

**Codex chain shape (convergent non-strictly-monotonic Major taper)**: R1 0C/5M/3m → R2 0C/3M/4m → R3 0C/1M/3m → R4 0C/2M/2m → R5 0C/0M/0m NO_NEW_CRITICAL_MAJOR. R3→R4 rebound from 1M to 2M because R3 fix-bundle introduced a `PHASE13_TEST_MOCK_SUBAGENT` env gate that itself surfaced as a production-data-integrity footgun; R4 collapsed by removing the gate entirely (subprocess tests are `--help`-only). Convergent shape overall.

**Streaks preserved**:
- ZERO Critical findings entire Codex chain (pre-Codex Critical absorbed at C.C lesson #6 review; not a Codex chain finding).
- **ZERO ACCEPT-WITH-RATIONALE banked across all 11 Major + 12 Minor findings** — cleanest writing-plans chain in Phase 12.5/13 arcs; continues streak with Phase 12.5 #1+#2+#3 brainstorms + Phase 13 brainstorm all ZERO banks (cumulative arc ZERO ACCEPT-WITH-RATIONALE).
- **ZERO Co-Authored-By footer trailer drift across all 7 commits** (verified via `%(trailers:key=Co-Authored-By)` extraction returning 0 matches; ~194+ project-cumulative streak preserved).
- Schema v19 UNCHANGED (writing-plans is doc-only; v20 lands at T-A.1.1 migration-only commit per OQ-12 Option E).
- Baseline `4924 fast / 0 ruff E501 / schema v19` UNCHANGED.

**Pre-Codex orchestrator-side review (C.C lesson #6 BINDING 10th cumulative validation)** absorbed 1 Critical at `25ac9bd`: OQ-7 `fill_origin` enum + backfill values diverged between dispatch brief §1.3 (orchestrator-side paraphrase: `migration_backfill` / `import_csv` with backfill target `migration_backfill`) and spec §3.4 + §6.4 authoritative (`tos_import` / `imported_legacy` with backfill target `operator_typed`). Plan reconciles spec >> brief; brief is historical-artifact (dispatch one-shot; spec authoritative). **This was an orchestrator-side defect introduced during OQ-7 walkthrough** (paraphrase substitution rather than verbatim spec citation); C.C lesson #6 BINDING pre-Codex review caught + reconciled cleanly before reaching Codex chain. Future writing-plans dispatch briefs paraphrasing OQ dispositions should cite spec §X line numbers verbatim.

**Plan deliverable**: 2810-line plan at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` covering 11 sub-bundles + 71 tasks.

**Key locked-shape elements**:

- **§A 20 general architectural decisions** (sub-bundle decomposition + module placement + view-model placement + route placement + OhlcvCache wiring + Codex SELECTIVE policy + pattern labeler subagent + ASCII-only + matplotlib + cassette infrastructure + Schwab integration + transactional discipline + session-anchor predicate + schema-CHECK + Python-constant + dataclass-validator paired discipline + NO INSERT OR REPLACE + empty-cohort rendering + operator-witnessed gates + discrepancies helper hand-off + pre-Codex orchestrator-side review BINDING + test fixture USERPROFILE+HOME monkeypatch).

- **§A.14 Constant-placement LOCK** (Codex R2 M#1 closure): ALL v20 enum constants live in `swing/data/models.py` (file exists pre-Phase-13 + houses dataclass `__post_init__` validators). `swing/patterns/__init__.py` re-exports `DETECTOR_PATTERN_CLASSES` for namespace convenience. `swing/web/charts.py` (T2.SB6) + `swing/trades/watchlist_close_track.py` (T4.SB) IMPORT from `swing/data/models.py` — they do NOT redefine constants. 11-row table maps every CHECK construct to primary location + re-export + validator. Preserves Phase 12 C.A T-A.2 paired atomic landing without forcing T-A.1.1 to create modules from later sub-bundles.

- **§B v20 migration mechanics (OQ-12 Option E)**: T-A.1.1 = migration-only commit on T2.SB1 worktree branch (SQL + EXPECTED_SCHEMA_VERSION bump + Python constants + dataclass validators + Schwab audit-service widening; 10-item v20 atomic-landing roster). T-A.1.1b = NEW repo CRUD modules land separately AFTER T-A.1.1 (per Codex R1 M#1 + R2 M#2 closure preserving migration-only boundary). T3.SB1 worktree branches off T-A.1.1's first-commit SHA (NOT T-A.1.1b's) explicitly. Merge ordering T2.SB1 first then T3.SB1. Cross-bundle pin `test_schema_version_v20_invariant` planted at T-A.1.1 + un-skipped at T3.SB1 merge.

- **§B.6 v20 escalation rule**: "This plan introduces ZERO additional schema beyond spec §3" (forward-binding lesson #17 BINDING; per writing-plans dispatch brief §5 W17).

- **§C-F Theme 1/2/3/4 architectural decisions**: matplotlib SVG inline + `chart_renders` cache + 5 V1 detector specs (VCP + flat_base + cup_with_handle + high_tight_flag + double_bottom_w) + DTW Sakoe-Chiba with 120s benchmark gate + composite scoring 0.60×geometric + 0.40×template + closed-loop surface at T2.SB6 + drift logging baseline at `pattern_evaluations.feature_distribution_log_json` + Theme 3 entry/exit/review auto-fill with `construct_authenticated_client` 4-arg signature + Theme 4 Q4 close-tracking flag with 7 architectural sub-decisions D-Q4.1..D-Q4.7.

- **§G per-sub-bundle task decomposition** (71 tasks across 11 sub-bundles):

| Sub-bundle | Task count | Test delta projection (fast) | Test delta (slow) | LOC projection (prod + test) |
|---|---|---|---|---|
| T1.SB0 | 4 | +20-40 | 0 | +50-100 prod / +200-350 test |
| T2.SB1 | 9 | +50-90 | 0 (cassette-mode) | +500-800 prod / +600-900 test |
| T3.SB1 | 6 | +40-70 | +1 (Schwab E2E) | +200-300 prod / +300-500 test |
| T2.SB2 | 6 | +60-100 | 0 | +400-600 prod / +500-800 test |
| T2.SB3 | 9 | +90-150 | +1 (operator-fixture detector) | +800-1200 prod / +1000-1500 test |
| T3.SB2 | 5 | +40-70 | +1 (Schwab E2E) | +200-300 prod / +300-500 test |
| T2.SB4 | 7 | +70-120 | 0 | +500-800 prod / +700-1100 test |
| T2.SB5 | 6 | +60-100 | +1 (pytest-benchmark) | +400-600 prod / +500-800 test |
| T3.SB3 | 5 | +50-90 | 0 | +200-400 prod / +400-700 test |
| T2.SB6 | 7 | +70-120 | +1 (full closed-loop E2E) | +700-1100 prod / +900-1400 test |
| T4.SB | 7 | +40-70 | 0 | +250-400 prod / +400-700 test |
| **Cumulative** | **71 tasks** | **+590-1020 fast** | **+4 slow E2E** | **+4200-6600 prod LOC / +5800-9250 test LOC** |

- **§H.3 Cross-bundle pin schedule**: 11 pins enumerated (`test_ohlcv_cache_get_or_fetch_invariant` through `test_v20_atomic_landing_python_constants_validators_paired`) with planted-at + un-skipped-at + verifies columns.

- **§L 30 forward-binding lessons** for executing-plans dispatches (20 inherited from spec §11 + 10 Phase-13-specific surfaced during writing-plans authoring).

**Three highest-leverage plan decisions** (per return report §"Three highest-leverage plan decisions"):
1. **T-A.1.1 + T-A.1.1b split** (Codex R1 M#1 + R2 M#2) — preserves OQ-12 Option E migration-only boundary; T3.SB1 branches off T-A.1.1's SHA.
2. **Constant-placement LOCK at §A.14** (Codex R2 M#1) — all v20 enum constants in `swing/data/models.py`; later modules IMPORT not REDEFINE; closes Phase 12 C.A T-A.2 paired atomic landing.
3. **Hermetic subprocess cp1252 validation** (Codex R3 M#1 + R4 M#1+M#2) — subprocess tests `--help`-only; R4 caught `PHASE13_TEST_MOCK_SUBAGENT` env-gate as production-data-integrity footgun; deeper coverage via in-process monkeypatch.

**Orchestrator-side QA review PASS-CLEAN** across all coverage dimensions:
- §6 done criteria 14/14 met (spec at expected path + 5 Codex rounds NO_NEW_CRITICAL_MAJOR + section structure mirrors Phase 10 plan format + 11-sub-bundle decomposition with per-task acceptance criteria + v20 OQ-12 Option E migration encoded at §B + §G T-A.1.1 + 12 OQ dispositions cross-referenced + 5 cross-column CHECK invariants schema-defended at §A.14 + DETECTOR_PATTERN_CLASSES enum LOCK + T2.SB1 mid-dispatch pause at T-A.1.7 + T4.SB Q4-only + forward-binding lessons inherited + cross-bundle pin discipline at §H.3 + landing+fixes split + return report).
- §5 18 watch items all honored (most notably W2 OQ-12 Option E + W3 DETECTOR_PATTERN_CLASSES + W4 paired-atomic-landing + W11 T-A.1.1 migration-only + W17 plan-author schema escalation explicit at §B.6).
- 11 cross-bundle pins enumerated at §H.3 (verified directly).

**11-sub-bundle executing-plans dispatch loop UNBLOCKED** per §H.1 dispatch sequence:

```
T1.SB0 → T2.SB1 ∥ T3.SB1 (concurrent off T2.SB1's first-commit SHA per OQ-12 Option E)
       → T2.SB2 → T2.SB3 → T3.SB2 → T2.SB4 → T2.SB5 → T3.SB3 → T2.SB6 → T4.SB → CLOSED
```

**Next dispatch**: T1.SB0 (OhlcvCache → `_step_charts` wiring; 4 tasks; +20-40 fast tests; releases Phase 11 Sub-bundle C R1 M#5 V1 deferral).

Worktree husk at `.worktrees/phase13-writing-plans/` matches cleanup-script regex `phase\d+[-_]` — operator-paced cleanup pass post-merge.

### Predecessor (2026-05-18 PM; brainstorm)

**Integration-merge at `b5e62c5`** (branch `phase13-brainstorm` via `--no-ff`; 10 implementer commits = 1 initial draft (1343 lines) + 1 pre-Codex orchestrator-side review-fix (5 LOCK-divergences absorbed pre-chain; C.C lesson #6 BINDING validated 9th cumulative time) + 7 Codex-fix bundles + 1 return report).

**Codex chain shape (convergent non-strictly-monotonic Major taper)**: R1 0C/10M/3m → R2 0C/7M/2m → R3 0C/5M/2m → R4 0C/3M/2m → R5 0C/2M/2m → R6 0C/2M/2m → R7 0C/0M/1m advisory. R5+R6 plateau at 2M before R7 closes; convergent shape overall. Operator-override past MAX_ROUNDS=5 invoked at R6+R7 per project precedent (Phase 10 writing-plans + Phase 12.5 #1+#2 brainstorm + post-Phase-12 writing-plans).

**Streaks preserved**:
- ZERO Critical findings entire chain.
- ZERO ACCEPT-WITH-RATIONALE banked across all 32 Major + 14 Minor findings — cleanest brainstorm chain in Phase 12.5/13 arcs (continues streak with Phase 12.5 #1+#2+#3 brainstorms all 0 banks).
- ZERO Co-Authored-By footer drift across all 10 commits (~185+ project-cumulative streak preserved).
- Schema v19 UNCHANGED (brainstorm is doc-only spec; v20 lands at T2.SB1 task 1 per §8.3 Option E LOCK).
- Baseline `4924 fast / 0 ruff E501 / schema v19` UNCHANGED.

**Spec deliverable**: 1483-line spec at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` covering 4-theme architectural arc + Q4 fold-in.

**Key locked-shape elements**:

- **§1 11 operator-locked binding decisions L1-L11** captured verbatim with rationale (Q4 amendment absorbed into L11).
- **§3 v19→v20 schema delta**:
  - §3.0 `DETECTOR_PATTERN_CLASSES` enum LOCK (5 V1 values: `vcp` / `flat_base` / `cup_with_handle` / `high_tight_flag` / `double_bottom_w`); referenced by 4 columns across 3 new tables.
  - §3.1 NEW `pattern_exemplars` 3-column refactor (`proposed_pattern_class` + `final_decision` + `final_pattern_class`) with 5 numbered cross-column CHECK invariants schema-defending the matrix (relabel-vs-non-relabel coherence + source-vs-decision matrix + parent_exemplar_id linkage + geometric_score_json nullability + labeler_evidence_json source coherence).
  - §3.2 NEW `chart_renders` cache table.
  - §3.3 NEW `pattern_evaluations` detector run output cache.
  - §3.4 widenings: `fills.fill_origin` (Theme 3) + `schwab_api_calls.surface` enum.
  - §3.5 migration mechanics LOCK (backup-gate `pre_version == 19`).
- **§4 Theme 1**: T1.SB0 prerequisite OhlcvCache→_step_charts wiring (releases Phase 11 Sub-bundle C R1 M#5 V1 deferral) + 5 chart surfaces + matplotlib SVG inline LOCK (per Phase 10 §A.10 precedent avoiding mathtext gotcha) + `chart_renders` cache + market weather mini-chart + Theme 2 annotated chart deliverable at T2.SB6.
- **§5 Theme 2 HEADLINE**: foundation primitives (EMA smoothing + zigzag adaptive-threshold extrema + variable-window candidate generator) + 5 detector specs §5.2-§5.6 with rule-based geometric criteria + tolerance bands per criterion + composite scoring 0.60×geometric + 0.40×template + DTW Sakoe-Chiba template matching (window=0.1×series length) + dev-time labeling infra at T2.SB1 (Claude Code subagent + selective Codex 15%-random + high-stakes-disagreement) + closed-loop surface T2.SB6 + drift logging baseline substrate per L5 (LOGGING only; monitoring SPLIT to Phase 13.5).
- **§6 Theme 3**: T3.SB1 entry auto-fill (Schwab Trader API at form render; `fill_origin` + audit columns) + T3.SB2 exit auto-fill + T3.SB3 review auto-fill (priors + MFE/MAE from OhlcvCache via T1.SB0) + `fill_origin` enum widening.
- **§7 Theme 4**: operator-elicited usability list DEFERRED to orchestrator-pre-writing-plans operator-paired elicitation per §8 fallback with structured §7.3 5-field template (Issue title + Surface + Frequency + Severity + Operator framing + Proposed resolution) + Q4 §7.2 7 architectural sub-decisions D-Q4.1..D-Q4.7 with brainstorm-default recommendations (NEW table `watchlist_close_track_flags` + Web + CLI both + persistent-until-cleared-or-position-open + badge inline + UNION'd with pipeline output + watchlist-surface-only + per-flag-event audit row); PTEN canonical use case verbatim; v20-folds-in LOCK preserving L6 single-migration discipline; PARTIAL UNIQUE INDEX on active flags only closes Codex R1 M#9 re-flag-same-ticker defect.
- **§8 11-sub-bundle decomposition refinement** (per scope-brainstorm §0.5.2 LOCK; +1 vs dispatch brief §1.5):
  - T1.SB0 → T2.SB1 ∥ T3.SB1 → T2.SB2 → T2.SB3 → T3.SB2 → T2.SB4 → T2.SB5 → T3.SB3 → T2.SB6 → T4.SB.
  - §8.3 Option E v20 migration landing (T2.SB1 task 1 + T3.SB1 branches off T2.SB1's first-commit SHA preserves operator-locked concurrency at scope-brainstorm §0.5.2; closes duplicate-write-set conflict Option C would have created; 5 options A/B/C/D/E enumerated; Option E recommended BINDING).
  - §8.4 cross-bundle pin discipline.
  - Cumulative test delta projection: +590-1020 fast tests + 4 slow E2E across Phase 13 arc; Phase 13 close projection ~5500-5940 fast.
- **§9 12 OQs with brainstorm-recommendations** (OQ-1..OQ-12; OQ-11 + OQ-12 added beyond projected 10 for substantive coordination needs): sub-bundle count drift / chart rendering tech / pattern_class enum scope / template matching distance / Codex SELECTIVE policy / exemplar bootstrap workflow / fill_origin enum + backfill / MFE/MAE candle-data source / drift logging shape / closed-loop surface route location / pattern-labeler subagent definition location / v20 migration landing timing.
- **§10 5-pattern discriminating walkthroughs**: §10.1 VCP CVGI + §10.2 Flat base YOU + §10.3 Cup-with-handle XYZ + §10.4 High-tight flag WXYZ + §10.5 Double-bottom-W UVWX + §10.6 tolerance-semantics uniformity LOCK + §10.7 cup curvature definition LOCK (centered on cup_bottom_date ±10 days).

**Three highest-leverage design decisions** (per return report §3):
1. **pattern_exemplars 3-column labeling refactor** (R2 M#4 / R3 M#2 / R4 M#1 cascade) closes single-pattern_class-enum-with-`none`-sentinel pollution that would have leaked into pattern_evaluations + chart_renders downstream cohort queries.
2. **T1.SB0 OhlcvCache→_step_charts wiring as Phase 13 prerequisite Sub-bundle** releases Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral; enables Theme 2 detector cache substrate without yfinance dependency.
3. **Option E v20 migration landing** preserves operator-locked T2.SB1/T3.SB1 concurrency while closing duplicate-write-set conflict (Option C explicitly REJECTED at Codex R2 M#2).

**Defense-in-depth catches at §1.2**: 2 factual errors in dispatch brief surfaced (`candidates.pattern_class` column does NOT exist per migration 0001..0019 grep; `fill_origin` not on `fills` schema) — routed through OQ-3 + Theme 3 schema sketch rather than silently absorbed.

**Orchestrator-side QA review PASS-CLEAN** across all coverage dimensions:
- §6 done criteria all met (spec at expected path; 7 Codex rounds NO_NEW_CRITICAL_MAJOR; section-numbered format; all 5 patterns walked end-to-end; 12 OQs with dispositions; 11-sub-bundle decomposition; Theme 4 list deferred with structured template).
- §5 watch items all honored (11 §1.1 LOCKS preserved; v2 brief §1 introspection HARD constraint enforced; sell-side + ML re-ranker + drift monitoring scope-banking respected; `construct_authenticated_client` 4-arg discipline cited; HTMX gotcha trinity + base-layout VM banner pin called out).
- Scope-banking integrity intact (L1 no run-time AI; L3 sell-side Phase 14; L4 ML re-ranker indefinitely deferred; L5 drift monitoring Phase 13.5).
- Q4 7 sub-decisions all present with brainstorm-defaults + rationale.
- 5 cross-column CHECK invariants on pattern_exemplars all numbered + schema-defended.
- Option E v20 migration timing recommended over A/B/C/D/REJECTED.
- §10.6 + §10.7 tolerance + cup curvature LOCKs preserved.
- ZERO Co-Authored-By footer drift verified via grep on all 10 commits.

**Writing-plans dispatch UNBLOCKED post orchestrator-pre-writing-plans operator-paired triage of 12 OQs + §7.1 usability-list elicitation per §7.3 5-field structured template.**

Worktree husk at `.worktrees/phase13-brainstorm/` matches cleanup-script regex `phase\d+[-_]` — operator-paced cleanup pass post-merge.

---

## 2026-05-18 Phase 12.5 #3 (Project Hygiene Maintenance Pass) SHIPPED at `b436067` — CLOSES Phase 12.5 arc; 3 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; orchestrator-side QA review PASS-CLEAN across 13 watch items + Q3 skipped-test audit completed; T-3.5 Bucket A landed (3 Phase 8 tests promoted to PASSING); Ruff 18 E501 → 0; schema v19 UNCHANGED; 4847 → 4850 fast pass

**Integration-merge at `b436067`** (branch `phase12-5-bundle-3-project-hygiene-executing-plans` via `--no-ff`; 11 task-branch commits = 7 task-impl (T-3.1..T-3.7) + 3 Codex-fix (R1+R2+R3) + 1 return-report). 3 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/5M/2m → R2 0C/2M/1m → R3 0C/0M/1m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Major findings (all 7 cumulative Major resolved with code-content fixes). ZERO Co-Authored-By footer drift across all 11 commits (~165+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review APPROVED_AS_IS** (C.C lesson #6 BINDING; 8th cumulative validation).

**Orchestrator-side QA review PASS-CLEAN** across 13 watch items: T-3.7 3-site amendments verified file:line accurate + accurately describe shipped helper SQL semantic; T-3.5 Bucket A fix verified `datetime.now() + timedelta(days=7)` anchor at `tests/integration/test_phase8_pipeline_walkthrough.py:57` with L-E2 lesson citation + 7-day buffer per Codex R1 M#5 hardening; T-3.5 test pass verified 3 previously-failing tests promoted to PASSING (4847 → 4850 fast pass); T-3.6 Ruff cleanup verified zero E501 + zero other error classes; T-3.6 ASCII preservation honored on runtime CLI paths (1 em-dash at cli.py L1142 is in docstring NOT runtime print/echo per L-W4 scope); T-3.4 amendment inventory verified 74 rows + spot-checks resolved to correct source docs; T-3.1 CLAUDE.md status-line archive-split verified (47 entries → 18 archived; 29 retained active within plan [15,30] band); T-3.2 phase3e-todo verified (3768 lines + archive 1372 lines); T-3.3 orchestrator-context verified (715 → 698 lines + 20 lessons archived); 4 operator-locks preserved verbatim; cross-document consistency verified; ZERO red flags.

**Operator-driven Q3 skipped-test audit COMPLETED** (5 skipped roster classified):
- **1 LEGITIMATE-DEFERRED**: `tests/evaluation/patterns/test_flag_classifier_integration.py:21` "No labeled fixtures committed yet (Task 7.3 operator-only)" — Phase 13 Theme 2 territory; auto-un-skips when fixtures land.
- **4 POTENTIALLY-STALE**: `tests/journal/test_account_summary_net_liq_extraction.py:43` parametrized over `thinkorswim/2026-04-15/-04-30/-05-08/-05-12-AccountStatement.csv` (gitignored privacy-sensitive). Sanitized fixtures exist at `tests/fixtures/tos/schwab-real-world-2026-04-15..2026-05-12.csv` (per Phase 9 Sub-bundle E ship; account-number sanitization preserves Net Liq Value).
- **Operator-pending disposition for #2-5**: (a) UPDATE tests to use sanitized fixtures → 4 skips become PASS (baseline 4850 + 5 → 4854 + 1); (b) KEEP AS-IS as operator-environment-only smoke tests.
- **ZERO prunable. ZERO Bucket-C-style** (T-3.5 landed Bucket A; no new skips added).

**Test count**: 4847 → **4850 fast pass** (the +3 are T-3.5 promotions; ZERO new skips).
**Ruff**: 18 E501 → **0** (acceptance LOCK met).
**Schema**: v19 UNCHANGED.

**Key shipped artifacts:**
- `docs/v2-1-section-7f-amendments-2026-05-18.md` (NEW; 74 amendments).
- `docs/CLAUDE.md-archive.md` (NEW; 18 entries).
- `docs/phase3e-todo-archive.md` (extended; +23 sections via 2026-05-18 appendix).
- `docs/orchestrator-context-archive.md` (extended; +20 lessons).
- 3-site amendment on Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104.
- T-3.5 fix at `tests/integration/test_phase8_pipeline_walkthrough.py:57`.
- T-3.6 18-site E501 fixes across 11 swing/ files.

**Operator-paired post-merge S2-S4 gate UNBLOCKED** (S1 already PASS at 4850/5/0 + ruff 0; S2 visual archive-split boundaries + S3 amendment doc readability + S4 amendment 3-site verification — orchestrator-driven post-merge).

**4 NEW forward-binding lessons L-E1..L-E4** banked at return report §9:
- L-E1: operational-follow-through vs amendment classification.
- L-E2: time-dependent fixture calendar-buffer ≥7d (the Bucket A fix lesson).
- L-E3: operator-runtime-override + post-hoc audit transparency pattern.
- L-E4: row-contract grep-verification pre-Codex.

**Phase 12.5 arc CLOSED.** Aggregate across Phase 12.5 (#1 + finviz-fix + #2 + #3): ~7-8 total executing-plans dispatches if you count the brainstorm + writing-plans + executing-plans triplets; ~5 Codex chains total. **Phase 13 dispatch UNBLOCKED post**: operator-witnessed S2-S4 gate + Q1 reconciliation walkthrough + Q2 tabularize web+CLI + Q3 skipped-test disposition closures.

### Predecessor (2026-05-18 AM; writing-plans)

## 2026-05-18 Queued post-Phase-12.5-#3 / pre-Phase-13 cleanup items (operator-added 2026-05-18 post-Phase-12.5-#3-writing-plans-merge)

Two cleanup items operator queued for post-Phase-12.5-#3 closure, BEFORE Phase 13 commissioning. Both are bounded scope; neither is in Phase 12.5 #3 plan (intentionally separated to keep Phase 12.5 #3 scope narrow).

### Item Q1: Open reconciliation discrepancy walkthrough — investigate suspected Schwab API response parser bug

**Posture:** Orchestrator-paired walkthrough first; investigation dispatch second IF walkthrough surfaces a real bug.

**Trigger:** Operator suspects the Schwab API response parser may have a bug surfaced by the pattern of open discrepancies currently pending (54+55+56+57 + any newer Pass-1 `unmatched_open_fill` re-emissions from runs #67/#68). Operator wants to step through each open discrepancy with orchestrator, examine the source `schwab_api_calls.response_body_json` (or raw response if logged elsewhere) vs the journal-side fill row vs the emitted discrepancy shape, and identify whether the parser is misreading a Schwab response field.

**Scope (walkthrough)**:
- Read each open `reconciliation_discrepancies` row (resolution='unresolved' OR resolution='pending_ambiguity_resolution' OR resolution NULL).
- For each: surface the linked `schwab_api_calls` row's audit metadata + the journal-side fill row (`fills` table) + the discrepancy's `expected_value_json` + `actual_value_json` envelope.
- Compare against operator's actual TOS / Schwab broker-statement reality (operator brings broker-statement evidence to the walkthrough).
- Identify pattern: random / per-fill / per-order-shape / per-discrepancy-type / parser-specific.

**Scope (investigation dispatch — IF walkthrough surfaces bug)**:
- Investigation-first dispatch shape (precedent: 3e.12 tos-import diagnostic at `a9541d2`; post-Phase-12 Sub-bundle 1.5 diagnostic at `a7c1016`).
- Diagnostic script bypasses `_audited_get_account_orders` audit wrapper to capture pre-parser raw shape (precedent: `scripts/diagnose_schwab_executionlegs.py` at Sub-bundle 1.5).
- Operator-paired diagnostic run against production (recovery sequence + redacted output).
- Fix dispatch after root cause identified.
- Expected dispatch shape: 2-4 Codex rounds; gate 3-5 surfaces; schema likely v19 unchanged.

**Cross-references:**
- CLAUDE.md gotcha "Synthetic-fixture-vs-production-emitter shape drift" (Phase 12 Sub-sub-bundle C.D gate finding family).
- CLAUDE.md gotcha "Pass-2-tier-1-FORBIDDEN + Pass-1-tier-1 — V2-RESOLVED for Pass-1; Pass-2 STAYS tier-2-always".
- Post-Phase-12 Sub-bundle 1.5 diagnostic precedent (4 placeholder shapes identified + 5 real FILLED LIMIT orders).
- Phase 12.5 #1 ship verified architectural fix HOLDS positive sense (production run #15 ZERO false-positive Pass-1; but Pass-2 still tier-2-always per OQ-F V2-deferred).

**Decision-pending at walkthrough time**:
- Whether suspected bug is real (vs operator-perceived pattern that's actually correct).
- Whether fix is V1 dispatch OR V2-deferred (depends on severity + workaround availability).
- Whether parser fix sequencing should go BEFORE or AFTER Phase 12.5 #3 close.

**Status**: ✅ **CLOSED 2026-05-18** (operator-paired walkthrough post-Phase-12.5-#3-merge). **Diagnosis**: NOT a Schwab API response parser bug. Root cause is an **architectural window-mismatch** — reconciliation flow checks open-trade fills (any age) against Schwab orders fetched within a 7-day window (`period_end - cfg.integrations.schwab.lookback_days`). Fills with `fill_datetime < period_start` emit `unmatched_open_fill` with `ambiguity_kind='unsupported'` + `_pass_2_required=True`. 7 open discrepancies dispositioned: 4 from runs #17+#18 (54+55+56+57 → correction_ids 20+21+22+23) + 3 from run #19 fired during the cfg-edit-in-flight window (58+59+60 → correction_ids 24+25+26); all `acknowledge` per C.D-precedent. **Fix shipped (Option B near-term)**: cfg-bumped `integrations.schwab.lookback_days` from 7 to 30 in `~/swing-data/user-config.toml`. DHC (21d back) + VSAT (12d back) + CVGI (10d back) all now within new 30-day window; next pipeline run will pull fresh orders + match cleanly. **NEW V2 candidate banked** (architectural; below): dynamic lookback (auto-widen to cover oldest open-trade.entry_date) OR Schwab inception-CSV ingestion (banked since 2026-05-12) — supersedes the cfg-bump near-term workaround when operator opens a trade held >30 days. **Forward-binding lesson**: pipeline subprocess snapshots cfg at process-start (`load()` + `apply_overrides()`); cfg edits made DURING an in-flight pipeline run do NOT apply until the NEXT subprocess starts. Mid-flight cfg edits + concurrent pipeline runs can emit a "transition cohort" of discrepancies that still need dispositioning even after the cfg fix lands (this Q1 closure dispositioned 7 = 4 old-cohort + 3 transition-cohort).

### NEW V2 candidate (Q1 disposition; banked 2026-05-18):

**Dynamic Schwab orders-fetch window** — auto-widen `lookback_days` to cover the oldest open-trade entry_date (plus reasonable buffer) instead of a static 7/30-day default. Current static cfg works for typical hold periods but fails when operator opens a trade held longer than the configured window. Dispatch shape (when commissioned): brainstorm + writing-plans + executing-plans; touches `swing/integrations/schwab/pipeline_steps.py:_step_schwab_orders` + `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` window-derivation logic + new helper `_compute_dynamic_lookback_days(conn, cfg)` reading earliest open-trade.entry_date. Defense pattern: bound the dynamic value at a reasonable upper limit (e.g., 180 days; Schwab API supports it) to prevent pathological multi-year holds from generating very-slow API calls. Alternative or complementary: Schwab inception-CSV ingestion (banked at CLAUDE.md status-line 2026-05-12) seeds historical orders from one-time operator-paired CSV import → reconciliation matches against the inception-seeded history regardless of API window. Operator-paced; not currently blocking.

### Item Q2: Discrepancy resolution — render journal/Schwab value comparison as table on BOTH web AND CLI (presentation-only)

**Status**: ✅ **SHIPPED 2026-05-18 at `e45a64f`** (integration merge of `phase12-5-q2-discrepancy-tabularize` via `--no-ff`; 10 task-branch commits = 4 task-impl T-Q2.1..T-Q2.4 + 1 pre-Codex review-fix + 1 Codex R1 + 1 Codex R2 + 1 R3 advisory + 1 return-report; 3 Codex rounds NO_NEW_CRITICAL_MAJOR; 2 ACCEPT-WITH-RATIONALE banked on Majors — FIRST in Phase 12.5 arc; both technically sound per orchestrator-side QA review; +70 fast tests 4854→4924; ruff 0 E501 preserved; schema v19 UNCHANGED; brief-as-plan dispatch shape demonstrated). **4 distinct pre-existing Phase 12.5 #2 envelope-shape drift bugs SURFACED + RESOLVED IN-TREE** (equity_delta + stop_mismatch + position_qty_mismatch + unmatched_*_fill; same CLAUDE.md `synthetic-fixture-vs-production-emitter shape drift` gotcha family). NEW production surfaces: `swing/trades/reconciliation_render.py` (neutral pure-function module with ASCII helper + `build_compared_pairs` builder + ASCII-only invariant assert) + `swing/web/view_models/reconcile.py:compared_pairs` field + `swing/web/templates/reconcile_discrepancy_resolve.html.j2` HTML `<table>` + `swing/cli.py:show_ambiguity` ASCII table integration. 6 V2.1 §VII.F amendments + 5 NEW forward-binding lessons banked. **Operator-witnessed S2-S4 gate ALL PASS 2026-05-18** (planted-discrepancy walkthrough via direct DB INSERT of synthetic `entry_price_mismatch` discrepancy_id=61 (DHC; ambiguity_kind=unsupported; expected `{price:7.58, qty:39, ticker, date}` vs actual `{price:7.62, qty:39, ticker, date, schwab_order_id:SYN-GATE-PLANT}`): S3 PASS — CLI emits ASCII table `Field | Journal | Schwab` + `------------+---------+-------` + `entry price | 7.58 | 7.62`; PowerShell-safe (no cp1252 crash). S2 PASS — web `/reconcile/discrepancy/61/resolve` renders `<table class="reconcile-comparison-table" aria-label="Journal vs Schwab comparison for entry_price_mismatch">` + `<thead>` Field/Journal/Schwab columns + `<tbody>` `entry price | 7.58 | 7.62` row; rendered ABOVE the single-side `<dl class="context-pairs">` context list per brief §A.3. S4 PASS — same field label + same values + same ordering across web + CLI; builder correctly filtered to surface only the MISMATCHED field (price); equal fields (qty + date) suppressed. Planted disc#61 DELETED post-gate; production state restored: ZERO open discrepancies. **Phase 12.5 arc CLOSES.**

### Original scope (pre-ship; preserved for historical context)

**Scope amended 2026-05-18 (operator)**: CLI parity is IN SCOPE — `swing journal discrepancy show-ambiguity` (and any other discrepancy CLI surfaces that emit the comparison) MUST output a similar table for operator-readability purposes.

**Posture:** Small executing-plans-shape dispatch (or inline-fix if simple enough; orchestrator chooses at commission time).

**Trigger:** Phase 12.5 #2 shipped `/reconcile/discrepancy/{id}/resolve` form page with pre-resolution context section ABOVE choice menu. Current rendering uses list format for the journal-side vs Schwab-side value comparison on BOTH web AND CLI (`swing journal discrepancy show-ambiguity <id>` emits list-shape output). Operator wants this rendered as a TABLE on both surfaces (2 columns: journal-side | Schwab-side; rows per compared field) — VM data is already structured; only the rendering paths need adjustment + possibly a shared helper.

**Scope (web)**:
- MODIFY `swing/web/templates/reconcile_discrepancy_resolve.html.j2` — replace list rendering of pre-resolution context with `<table>` (2-column journal-side | Schwab-side; ARIA-compliant; ASCII-only per F20 LOCK from Phase 12.5 #2).
- MAYBE MODIFY `swing/web/view_models/reconcile.py` — if `pre_resolution_context_pairs` field shape needs restructuring from `list[tuple[str, str]]` to `list[tuple[str, Any, Any]]` (field-label + journal-value + Schwab-value) for cleaner table rendering. Spec §5.2 ReconcilePreResolutionContext (15 fields per Phase 12.5 #2 A3 amendment) — verify existing shape suits table rendering.
- Per-discrepancy-type render helpers may need touch-up (10 helpers in `reconcile.py` per Phase 12.5 #2 plan).
- NEW discriminating tests asserting `<table>` element + `<th>` headers + correct row count per discrepancy type.

**Scope (CLI)**:
- MODIFY `swing/cli.py` (or wherever the discrepancy CLI subcommands render the comparison; the C.D-shipped surfaces include `discrepancy show-ambiguity` + possibly `discrepancy show` + `discrepancy show-correction`). Locate via `grep -n "def show_ambiguity\|def show_discrepancy\|def show_correction" swing/cli.py`.
- Replace list output (likely `click.echo()` lines) with an ASCII-only tabular renderer. **BINDING per CLAUDE.md cp1252 stdout gotcha**: table-drawing characters MUST be plain ASCII (`+`, `-`, `|`) — do NOT use Unicode box-drawing characters (`┌`, `─`, `│`, `┐`, etc.) since they crash on Windows PowerShell cp1252 stdout. Optional: lightweight 2-line border using `|` and `-`. NO third-party dependencies (no `rich`, no `tabulate`) — render inline.
- Shared rendering helper between CLI + web preferred IF VM field-shape restructure lands (e.g., a `render_journal_schwab_comparison_table_ascii(pairs)` helper that returns a plain-text table; web template wraps the same pairs in HTML `<table>`). This is operator-decision at commission time vs duplication.
- NEW discriminating tests asserting CLI output contains tabular pattern (e.g., `|` column separator + per-row content correctness) + subprocess test capturing stdout through PowerShell to validate cp1252 encoding doesn't crash (per CLAUDE.md "Discriminating-test gap" note on subprocess vs capsys).

**Out of scope:**
- Behavioral changes — POST handler + service-layer + classifier untouched.
- Schema changes (v19 LOCK).
- Adding new discrepancy types or comparison fields.

**Operator-locks (anticipated; operator confirms at commission)**:
- Per-discrepancy-type table column headers (Journal | Schwab vs Ours | Theirs vs etc.) — operator-decision at commission. Suggested default: "Journal" | "Schwab".
- Whether VM field-shape changes (suggesting yes for clarity + cleaner CLI/web shared helper) OR template/CLI render-only restructure (extract fields by name from existing shape) — operator decides based on dispatch-author proposal.
- Whether CLI shared helper lives in `swing/web/view_models/reconcile.py` (web has it; CLI imports) OR a NEW neutral location (e.g., `swing/trades/reconciliation_render.py`) — operator decides.

**Expected dispatch shape:**
- 2-4 tasks (web template rewrite + CLI render rewrite + shared helper + tests).
- 1-2 Codex rounds.
- **3-4 surface operator-witnessed gate**: S1 inline pytest + ruff; S2 visual verification of `/reconcile/discrepancy/{id}/resolve` page renders table on browser; S3 visual verification across the 10 per-type render helpers (web); S4 CLI table rendering verified on PowerShell terminal (`python -m swing.cli journal discrepancy show-ambiguity <id>` against real production discrepancy) — operator confirms readability + ZERO cp1252 crash.
- Schema v19 unchanged.

**Cross-references:**
- Phase 12.5 #2 plan A3 amendment (15-field ReconcilePreResolutionContext drift).
- Phase 12.5 #2 spec §5.2 + spec §6.
- CLAUDE.md gotcha "Windows PowerShell stdout defaults to cp1252" — ASCII-only table-drawing constraint.
- Phase 12 Sub-bundle C.D ship — `swing journal discrepancy {list-pending-ambiguities, show-ambiguity, resolve-ambiguity, override-correction}` CLI subcommands (and post-Phase-12 Sub-bundle 1 added `show-correction`).

**Status**: QUEUED; commission timing operator-paced.

### Item Q3: Skipped-test inventory audit — investigate + prune (orchestrator-driven; in spirit of Phase 12.5 #3 T-3.5 failing-test triage)

**Posture:** Orchestrator-driven investigation at Phase 12.5 #3 executing-plans return time. NOT a separate dispatch unless triage surfaces work that warrants one.

**Trigger:** Operator-added 2026-05-18 — Phase 12.5 #3 audits the 3 pre-existing Phase 8 walkthrough FAILING tests (T-3.5 bucket triage); in the same spirit, the SKIPPED-test inventory deserves audit. Skipped tests carry an implicit "deferred-work" cost that compounds over time; some skips become stale (the original blocker resolved but the skip decorator was never removed); some skips mask deferred-but-still-pending work; some are legitimate operator-only fixtures.

**Baseline at brief drafting time (2026-05-18 fresh pytest run on main HEAD `9407dad`)**: **5 skipped** (4847 fast pass + 3 pre-existing phase8 walkthrough failures + 5 skipped + 1 known enumerated):
- `tests/evaluation/patterns/test_flag_classifier_integration.py:21` "No labeled fixtures committed yet (Task 7.3 operator-only)" — legitimate-deferred per operator commit posture.
- 4 OTHERS not yet enumerated at brief time; investigation surfaces the full roster.

**Skipped-count growth scenario**: if Phase 12.5 #3 T-3.5 lands **Bucket C** (skip-pattern with operator approval), skip count grows from 5 → 8 (3 Phase 8 walkthrough tests added). The Bucket C disposition is itself a deliberate skip; this Q3 audit covers it identically (legitimate-deferred per operator approval; standalone-dispatch entry banked).

**Scope (orchestrator-driven; ~10-30 min):**
1. **Enumerate every currently-skipped test**: `python -m pytest -m "not slow" -rs -q -n 0 2>&1 | grep -E "^SKIPPED"` to get the full roster with skip reasons.
2. **For each skip**, surface:
   - File:line + test name + skip decorator (`@pytest.mark.skip(reason=...)` vs `@pytest.mark.skipif(...)` vs runtime `pytest.skip(...)`).
   - Skip rationale text (verbatim).
   - Date the skip was introduced (`git log -p --diff-filter=A -- <file> | grep -B5 "pytest.mark.skip"` or similar; approximate via blame).
   - Cross-bundle pin status if applicable (e.g., Phase 10 T-A.7 + T-E.3 cross-bundle pin pattern — un-skip happens at later sub-bundle; verify the un-skip already landed).
3. **Classify per skip** as one of:
   - **Legitimate-deferred** (e.g., operator-only labeled fixtures pending; cross-bundle pin awaiting later sub-bundle that hasn't landed yet; slow-marked test requiring live API access).
   - **Stale** (the original blocker has resolved but the skip decorator was never removed; un-skip + verify-passes is the action).
   - **Prunable** (the test itself is no longer needed; the surface it exercised was removed/refactored; DELETE the test).
   - **Bucket-C-style** (Phase 12.5 #3 T-3.5 disposition; legitimate-deferred per operator approval + standalone-dispatch entry banked).
4. **Propose per-skip disposition** + operator-paired decision per skip.

**Operator-locks (anticipated; operator confirms at audit time)**:
- Whether any reclassification + per-skip action lands inline (small orchestrator-driven commit) OR requires a separate dispatch (if e.g. multiple un-skips reveal real test failures requiring fixes).
- Whether the audit-summary doc itself is durably tracked (e.g., new `docs/skipped-test-inventory-2026-05-18.md` companion to T-3.4's V2.1 §VII.F amendment inventory pattern) OR ephemeral (banked inline in this phase3e-todo entry).

**Likely outcomes (per audit pattern history)**:
- 1-2 legitimate-deferred (operator-only fixtures + cross-bundle pin awaiting later phase).
- 1-3 stale (project moved past the original blocker; un-skip + verify-passes).
- 0-1 prunable (rare; tests rarely become unnecessary).
- 0-3 Bucket-C-style if Phase 12.5 #3 T-3.5 lands Bucket C.

**Out of scope:**
- Auditing FAILING tests beyond the 3 Phase 12.5 #3 T-3.5 targets (Phase 12.5 #3 owns that).
- Adding NEW tests to cover gaps revealed by un-skipping.
- Test-runtime profiling beyond skip-resolution work.

**Status**: ✅ **CLOSED 2026-05-18** at `416865f` (post-Phase-12.5-#3-merge orchestrator-paired audit). 5-skipped roster enumerated + classified: 1 LEGITIMATE-DEFERRED (`test_flag_classifier_integration.py:21` operator-only labeled fixtures pending Phase 13 Theme 2) + 4 POTENTIALLY-STALE (`test_account_summary_net_liq_extraction.py:43` parametrized over `thinkorswim/2026-*-AccountStatement.csv`). Operator-decided disposition: **update fixture paths to sanitized `tests/fixtures/tos/schwab-real-world-*.csv`** (Option A). Inline orchestrator commit at `416865f`; baseline shifts 4850/5 → 4854/1 (only Skip #1 remains). ZERO prunable; ZERO Bucket-C-style.

**Cross-references:**
- Phase 12.5 #3 T-3.5 failing-test triage (same spirit; complementary discipline).
- Phase 10 T-A.7 + T-E.3 cross-bundle pin un-skip pattern (precedent for legitimate-deferred → un-skip at later sub-bundle).
- Phase 12.5 #2 cross-bundle pin (1 of the 5 baseline skipped; un-skipped during writing-plans but may or may not have landed via executing-plans merge — audit verifies).
- `feedback_orchestrator_qa_implementer_product.md` (orchestrator QA discipline; Q3 is QA-adjacent triage).

### Item Q4: Operator close-tracking flag for watchlist symbols (feature; backlog-banked 2026-05-18)

**Posture:** Future feature. NOT a Phase 12.5 cleanup; not Phase 13 scope (Phase 13 is LOCKED at chart pattern detection + auto-fill themes). Could fold into Phase 13 Theme 4 (usability triage) OR be a standalone post-Phase-12.5 dispatch. **Operator-decision pending at commission**: phasing + scope.

**Trigger (operator framing 2026-05-18):** Operator looking at PTEN as top watchlist symbol for 5/19 process run; PTEN just closed past its pivot value → high-probability of opening a position when markets open. NOT flagged by hyp-rec (the existing algorithm doesn't elect it as a recommendation) but visually looks like a good candidate. Operator wants a visual mechanism to flag such symbols for personal close-tracking, persisting across pipeline runs even if the watchlist algorithm decides the symbol no longer meets criteria (false-negative guard).

**Two sub-use-cases**:
1. **At-breakout** (PTEN today): symbol just crossed its pivot/trigger; immediate-action candidate; flag retains it as visually-prominent on watchlist.
2. **Approaching-breakout**: symbol trending in correct direction but not yet at pivot; flag breaks it out from the rest of the watchlist visually + ensures it's not dropped from the surface if the watchlist algorithm next-run decides it doesn't meet criteria.

**Architectural decisions (operator-decision-pending at commission)**:
- **Schema**: NEW column on existing table (likely `candidates` or `evaluation_results`) OR NEW table for operator-flag metadata. Implications: schema v19 → v20 migration (would need to be lifted from current LOCK).
- **Setting / unsetting UI**: web UI toggle button on watchlist row? CLI command `swing watchlist flag <ticker> --close-track`? Both? Operator preference at commission.
- **Persistence semantics**:
  - Per-session (operator clears at end of session)?
  - Per-pipeline-run (auto-expire after next pipeline run)?
  - Persistent until operator explicitly clears?
  - Auto-expire after N days (e.g., 7-day lookback)?
  - Auto-clear when operator opens a position in the flagged ticker (state transition triggers)?
- **Visual rendering**:
  - Badge on the watchlist row (e.g., 🎯 or `[FLAGGED]` ASCII marker)?
  - Separate "Actively tracked" section above the main watchlist?
  - Bold/colored row background?
- **Filtering interaction**: if symbol is operator-flagged but the watchlist algorithm would drop it (no longer meets criteria), the symbol MUST be retained on the watchlist surface (false-negative guard). Per-row badge "operator-retained" to distinguish from algorithm-elected.
- **Relation to hyp-rec**: do flagged symbols get hyp-rec treatment too (forced through the hyp-rec scoring + expanded panel)? Or is the flag purely a watchlist-surface concept separate from hyp-rec?
- **Audit trail**: per-flag-event row (operator set/cleared timestamp + ticker + reason text)?

**Estimated scope (rough; pending operator-decisions)**:
- Schema migration (v19 → v20): 1 new column on `candidates` OR new `watchlist_close_track_flags` table.
- Web UI: 1 new toggle action on watchlist row + 1 visual surface (badge or section).
- CLI: 1 new subcommand under `swing watchlist` (or equivalent).
- Tests: ~+15-30 fast tests (toggle + render + persistence + false-negative-guard).
- Documentation: cycle-checklist additions + CLAUDE.md gotcha if any.
- Codex chain: 2-4 rounds (brainstorm + writing-plans + executing-plans full triplet recommended given schema + UI surfaces).

**Cross-references**:
- `swing/data/repos/watchlist.py` (or wherever watchlist persistence lives) — primary touch point.
- `swing/web/view_models/dashboard.py` + `partials/watchlist_top5_section.html.j2` — visual surface targets.
- `swing/recommendations/hyp_recs.py` — relation-to-hyp-rec decision point.
- Phase 13 Theme 4 usability triage scope at `docs/phase13-scope-brainstorm.md` §0.5 (potential fold-in candidate).

**Status**: ✅ **FOLDED INTO PHASE 13 THEME 4** (operator-decided 2026-05-18 post-Q2-gate-PASS). Q4 scope amended into `docs/phase13-brainstorm-dispatch-brief.md` §2.4 with the 7 architectural-decision items (schema; UI; persistence; visual; filtering; relation-to-hyp-rec; audit) surfaced for brainstorm Codex chain to propose + operator confirmation at brainstorm-output. Q4 absorbed into T4.SB closer sub-bundle. Phase 13 brainstorm Codex chain expected to add 1-2 rounds vs pre-amendment baseline. Estimated additional scope: ~+15-30 fast tests + likely schema work (column on `candidates` OR new `watchlist_close_track_flags` table; v20 → v21 OR fold into v20). No longer a separate dispatch.

### Sequencing relative to Phase 12.5 #3 + Phase 13

- **Phase 12.5 #3 executing-plans** — ✅ SHIPPED 2026-05-18 at `b436067` + S1-S4 operator-paired post-merge gate ALL PASS.
- **Item Q3 skipped-test audit** — ✅ CLOSED 2026-05-18 at `416865f` (Option A: 4 skips → 4 PASS via sanitized-fixture redirect; baseline shifted 4850/5 → 4854/1).
- **Item Q1 walkthrough** — ✅ CLOSED 2026-05-18 (NOT a parser bug; window-mismatch architectural; cfg-bumped lookback_days 7→30; 7 dispositions correction_ids 20-26; NEW V2 candidate banked for dynamic-lookback).
- **Item Q2** — ✅ SHIPPED 2026-05-18 at `e45a64f`; operator-witnessed S2-S4 gate ALL PASS 2026-05-18 (planted disc#61 walkthrough; web HTML + CLI ASCII + round-trip consistency all verified; planted row reverted).
- **Item Q4** — ✅ FOLDED INTO PHASE 13 THEME 4 (operator-decided 2026-05-18 post-Q2-gate-PASS). Brainstorm scope amended in `docs/phase13-brainstorm-dispatch-brief.md` §2.4 with 7 architectural decisions surfaced for Codex chain to propose + operator confirmation.
- **Phase 13** — **🚀 FULLY UNBLOCKED** (Phase 12.5 #3 ✅ + Q3 ✅ + Q1 ✅ + Q2 ✅ + Q2 gate ✅). **Phase 12.5 arc CLOSED 2026-05-18 with Q2 S2-S4 gate PASS.** Q4 is NOT a gate item (operator-decided phasing at commission). Phase 13 scope LOCKED at `docs/phase13-scope-brainstorm.md` §0.5; brainstorm dispatch brief ready at `docs/phase13-brainstorm-dispatch-brief.md`.

---

## 2026-05-18 Phase 12.5 #3 writing-plans SHIPPED at `fb27be2` — project-hygiene maintenance pass plan; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; orchestrator-side QA review PASS-CLEAN; schema v19 UNCHANGED; executing-plans dispatch UNBLOCKED

**Integration-merge at `fb27be2`** (branch `phase12-5-bundle-3-project-hygiene-writing-plans` via `--no-ff`; 1 task-branch commit at `63f1943` combined plan-write + return-report). 6 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/4M/4m → R2 0C/3M/3m → R3 0C/3M/2m → R4 0C/1M/2m → R5 0C/1M/2m → R6 0C/0M/1m; operator-override past default MAX_ROUNDS=5 at R6 per Phase 12.5 #1+#2 brainstorm precedent). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Major findings (all 12 cumulative Major resolved with code-content fixes). 2 Minor accepted as advisory (line count overshoot 1101 vs 400-700 brief target + section letter drift collapsed-gate precedent). ZERO Co-Authored-By footer drift (~165+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review APPROVED_AS_IS** (NEW C.C lesson #6 BINDING; 7th cumulative validation; brief tight enough that pre-review absorbed nothing pre-chain).

**Orchestrator-side QA review PASS-CLEAN** across all 10 watch items: T-3.7 amendment-target file:line accuracy verified at plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 + amendment text accurately describes shipped helper SQL semantic; T-3.5 Phase 8 walkthrough inventory verified 3-fail/1-pass via fresh pytest; T-3.6 18-row E501 roster byte-for-byte matches `ruff check swing/`; T-3.4 amendment-scope spot-check passed on Phase 12.5 #2 R-R §7 cross-references; T-3.1/T-3.2/T-3.3 archive-split boundary discipline coherent; 4 operator-locks preserved verbatim; schema v19 UNCHANGED LOCK + escalation rule encoded; footer suppression cited in every commit stem; cross-document consistency verified; ZERO red flags beyond known runtime-pairing points (T-3.5 Bucket C HARD STOP + T-3.3 pre-flight roster operator review).

**Test count baseline correction**: 4847 fast (NOT 4851 per dispatch brief; L-W3 NEW lesson banked captures brief-baseline-vs-fresh-baseline drift family).

**1101-line plan** at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (above 400-700 brief target; matches Phase 12.5 #1 1230 + #2 1082 overshoot precedent driven by Codex chain rigor + per-task acceptance specificity + 18-row Ruff roster verbatim + 33-file return-report grouped roster verbatim + 4-test Phase 8 walkthrough inventory verbatim).

**7 tasks T-3.1..T-3.7 single-sub-bundle decomposition**:
1. **T-3.7** (FIRST since smallest + de-risks downstream) — amend Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104 amendment text (3 sites; banner clears immediately on tier-3 override per shipped helper SQL semantic).
2. **T-3.5** Phase 8 walkthrough triage with 3-bucket disposition (Bucket A trivial fixture fix / Bucket B small runner-side adjustment / Bucket C HARD STOP requires operator approval BEFORE skip-pattern + standalone-dispatch entry).
3. **T-3.6** Ruff 18 E501 cleanup with full 18-row roster (file:line specific) + ASCII-preservation contract on runtime-path string literals; ZERO `# noqa` without rationale.
4. **T-3.4** V2.1 §VII.F amendment inventory at NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` with canonical 33-file return-report grouped roster + grep supplement.
5. **T-3.1** CLAUDE.md status-line archive-split (boundary 2026-05-12-inclusive + PROCEED_WITH_WRITE count gate at 15-30 active-retain band).
6. **T-3.2** phase3e-todo archive-split (SHIPPED-only predicate + pre-write roster gate).
7. **T-3.3** orchestrator-context archive-split (pre-flight roster + operator review BEFORE script-write).

**2 operator-locks preserved verbatim**: skip-brainstorm; amend-text-only for item #5 (NO code fix to preserve banner mid-window — shipped helper SQL semantic accepted).

**Schema v19 UNCHANGED LOCK** preserved (F1 + F5 + T-3.5 STOP-and-escalate rule).

**4-surface operator-witnessed gate plan** (per plan §H): S1 inline pytest+ruff+per-task post-conditions; S2 visual verification of archive-split boundaries; S3 V2.1 §VII.F amendment doc readability + cross-reference accuracy; S4 Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment verification.

**4 NEW forward-binding lessons L-W1..L-W4** banked at return report §9 for executing-plans inheritance:
- L-W1: Bucket-classification math requires explicit test-inventory table (compute expected counts FROM the table, NOT memory).
- L-W2: Pre-write gate pattern for archive-split scripts (`PROCEED_WITH_WRITE = False` until operator reviews roster).
- L-W3: Brief-baseline-vs-fresh-baseline drift verification (plan-author MUST re-verify pytest baseline at plan-write time).
- L-W4: ASCII-only invariant scope discipline (runtime CLI paths only; documentation freely uses em-dashes + § glyphs).

**Test projection** (per plan §E): ~+0 to ~+5 fast tests (most tasks text-edit zero-test-delta; possible +1-3 if T-3.5 lands fixes that need new regression pins); ~+50-200 LOC moves across archive-companion files; ruff baseline expected → 0 E501 post-T-3.6.

**Executing-plans dispatch UNBLOCKED** post operator-paired plan review.

### Predecessor (2026-05-18 PM; Phase 12.5 #2 executing-plans)

## 2026-05-18 Phase 12.5 #2 (Web Tier-2 discrepancy-resolution surface) SHIPPED at `0cecf28` — 5 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; +135 fast tests + 1 slow E2E; schema v19 UNCHANGED; 6-surface operator-witnessed gate ALL PASS; Sub-bundle B T-B.7 PROMISE FULFILLED

**Integration-merge at `0cecf28`** (branch `phase12-5-bundle-2-web-tier2-executing-plans` via `--no-ff`; 17 task-branch commits = 11 task-impl + 1 orchestrator-inline gate-fix `25f4554` (4th cumulative inline gate-fix; /dashboard route alias closing Phase 6 I3 HX-Redirect-target-unrouted gotcha) + 4 Codex-fix bundles + 1 return-report). 5 Codex rounds NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (R1 0C/2M/1m → R2 0C/2M/0m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE on Majors (all 6 cumulative resolved with code-content fixes); 1 Minor accepted as advisory (L-W5 LOCK forbids `error_kind Literal` tightening). ZERO Co-Authored-By footer drift across 17 commits (~163+ project-cumulative streak preserved).

**First operator-visible web Tier-2 surface ships** — dedicated GET/POST `/reconcile/discrepancy/{id}/resolve` form page mirrors `swing journal discrepancy resolve-ambiguity` CLI 1:1; same service entry `apply_tier2_resolution`; same choice menu; same audit shape; distinguishable via `resolved_by IN ('operator', 'operator_web')`. Dashboard banner links directly to the resolve form for the oldest pending-ambiguity discrepancy (ORDER BY ASC per LOCK #6).

**Sub-bundle B T-B.7 PROMISE FULFILLED** — Phase 12 Sub-bundle B's deferred T-B.7 web counterpart to CLI Tier-2 is now SHIPPED.

**6-surface operator-witnessed gate ALL PASS**: S1 inline pytest+ruff+slow E2E (4847 fast + 18 ruff + 10.59s E2E); S2 banner-link nav (/reconcile/discrepancy/52/resolve oldest ASC); S3 form-render with 10 context pairs + hidden `ambiguity_kind_at_render` anchor + custom-value textarea + F20 ASCII-only; S4 POST disc #52 → 204 + `HX-Redirect: /dashboard?reconcile_resolved=18` + correction_id=18 + `resolved_by='operator_web'` (F17 server-stamp LOCK preserved); S5 banner-clears 6 → 5 + link advances 52 → 53; S6 CLI/web parity disc 53 CLI `resolved_by='operator'` vs disc 52 web `resolved_by='operator_web'` (LOCK #3 distinguishability verified) + banner 5 → 4 post-S6.

**Test delta**: +135 fast tests (4712 → 4847; vs +81 plan projection — overshoot from parametrize granularity + Codex regression pins). +1 slow E2E (Phase 12.5 #2 happy-path PASS). Ruff 18 E501 unchanged. Schema v19 UNCHANGED (F1 LOCK preserved).

**3 V2.1 §VII.F amendment candidates banked** (A1 plan §C.1 class-name drift + A2 plan §K projection +81 vs actual +135 + A3 plan §A T-2.2 acceptance 14-vs-15 fields drift).

**5 NEW forward-binding lessons L-E1..L-E5**: L-E1 pre-Codex orchestrator-side review absorbed 1 Major-class finding pre-chain (/dashboard unrouted) — C.C lesson #6 validated 3rd time; L-E2 `OperationalError` pre-flight scope cascades — R1 wrap revealed adjacent paths R2-R4 incrementally (Python sibling-except clauses do NOT cascade); L-E3 Builder `ValueError` cause classification belongs in shared helper — extracted at R4; L-E4 Plan-class-name drift surfaces via Pass A AST grep at task time; L-E5 Pass B grep count drifts +N during dispatch as new code lands (21 → 24; F11/F21 contract handled).

**Production state post-gate**: 4 pending-ambiguity discreps remaining (54+55+56+57); operator continues dispositioning per C.D-cleanup precedent.

**Phase 12.5 #3 dispatch UNBLOCKED.**

### Predecessor (2026-05-18 AM; writing-plans)

## 2026-05-18 Phase 12.5 #2 writing-plans SHIPPED at `9220dac` — 5 Codex rounds + R5 confirmation NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; 1082-line plan; 11-task single-sub-bundle decomposition; 12 operator-locks + 21 invariants F1-F21 + 8+5 forward-binding lessons; schema v19 UNCHANGED; executing-plans dispatch UNBLOCKED

**Writing-plans-merge at `9220dac`** (branch `phase12-5-bundle-2-web-tier2-writing-plans` via `--no-ff`; 7 commits = 1 draft + 1 pre-Codex-review-fix + 4 Codex-fix + 1 return-report). 5 Codex rounds + 1 R5 confirmation NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper (pre-Codex 0C/3M/2m → R1 0C/3M/4m → R2 0C/2M/3m → R3 0C/1M/4m → R4 0C/0M/4m → R5 0C/0M/0m). ZERO Critical findings entire chain. ZERO ACCEPT-WITH-RATIONALE (all 6 Major + 15 Minor resolved with code-content fixes). ZERO Co-Authored-By footer drift across 7 commits (~147+ project-cumulative streak preserved).

**Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING) absorbed 3M+2m before R1** — validated again across Phase 12 C.C+C.D + Sub-bundle 1 + Phase 12.5 #1 brainstorm + writing-plans + Phase 12.5 #2 brainstorm precedent.

**Highest-value Codex catches:**
- **R1 M#1** task-ordering would break T-2.5/T-2.6 green-ship contract — fixed via stub-then-extend reorder (T-2.5 stubs 2 error-template branches; T-2.6 extends 3 more inline; T-2.10 polish-only). Each task ships green standalone.
- **R1 M#2** POST-service `ValueError` uniformly mapped to 400 + re-render would have looped operator through internal-error state on concurrent-resolve race — Branch 14 split into 14a (400 if re-read confirms pending) + 14b (409 if re-read shows terminal state). New discriminating test pinned via separate-connection + commit semantics. +1 fast test from projection.
- **R2 M#2** spec sections out of sync with R1+R2 plan fixes — banked J2 + J3 amendments with explicit "Plan supersedes spec" notes so executing-plans implementer treats plan as binding without spec rewrite.

**Key plan elements**: 1082-line plan at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`. 11 tasks T-2.1..T-2.11 single-sub-bundle decomposition (1 GET + 1 POST route + 1 VM module + 2 templates + 13-VM standalone-field retrofit + 21-callsite Pass B retrofit). 12 operator-locks verbatim-encoded at §D (4 spec §2 + 8 §16 ACCEPTED at brainstorm defaults). 21 invariants F1-F21 at §F. Schema v19 UNCHANGED (F1 LOCK). 3 V2.1 §VII.F amendments banked at §J (J1 builder kwarg + J2 ValueError 14a/14b split + J3 parametric valid_choices). 13 V2 candidates mirrored from spec §15 at §Z. 6-surface operator-witnessed gate at §H verbatim per LOCK §1.2 #12.

**Refined projection** post-Codex chain: ~+81 fast tests (+1 race regression from R1 M#2) + 1 slow E2E + ~+970 production LOC + ~+1145 test LOC. Ruff 18 E501 baseline preserved. Baseline 4712 fast → projected ~4793 post-executing-plans-merge.

**5 NEW writing-plans-surfaced forward-binding lessons L-W1..L-W5** (8 inherited from brainstorm + 5 new = 13 total for executing-plans): L-W1 stub-then-extend ordering for shared templates; L-W2 service ValueError requires re-read disambiguation in concurrent-write callers; L-W3 F# cross-reference accuracy audit at sealing time; L-W4 spec-out-of-sync requires explicit "Plan supersedes" notes + §J amendment banking; L-W5 late VM-validator additions risk breaking already-green callers.

**Executing-plans dispatch UNBLOCKED.**

### Predecessor (2026-05-18 AM; brainstorm)

## 2026-05-18 Phase 12.5 #2 brainstorm SHIPPED at `ac6eb88` — Web Tier-2 discrepancy-resolution surface design; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked (R1 M#4 surface attribution literal naming — schema v19 UNCHANGED; brief §2.7 conjecture corrected); 721-line spec; 8 §16 operator-decision items ALL accepted at brainstorm defaults; writing-plans dispatch UNBLOCKED

**Brainstorm-merge at `ac6eb88`** (branch `phase12-5-bundle-2-web-tier2-brainstorm` via `--no-ff`; 3 commits = 1 draft + 1 Codex-R1-R6-fix-bundle + 1 return-report). 6 Codex rounds convergent monotonic-Major taper (R1 0C/5M/3m → R2 0C/3M/2m → R3 0C/3M/2m → R4 0C/1M/3m → R5 0C/1M/2m → R6 0C/0M/2m); operator-override past default MAX_ROUNDS=5 invoked at R6 per Phase 12.5 #1 brainstorm + Phase 10 writing-plans precedent given clean convergent shape. ZERO Critical findings entire chain. ZERO Co-Authored-By footer drift across 3 commits.

**Key catch (R3):** brief §2.7 conjectured that `reconciliation_corrections.surface` column would need CHECK widening to permit `'web'`. **WRONG** — brainstorm verified by reading migration 0019 directly: there is NO `surface` column on `reconciliation_corrections`. Attribution achieved via existing free-TEXT `reconciliation_discrepancies.resolved_by` column with NEW value `'operator_web'`. ZERO schema work. ZERO new Python constant. ZERO new validator. **Forward-binding lesson banked**: brief-conjecture-vs-actual-schema gap → grep verify any column reference at brainstorm time (L-W1 family reapplication).

**4 operator pre-locks baked verbatim** (spec §2.1-§2.4): dedicated `/reconcile/discrepancy/{id}/resolve` form page + HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` on success + CLI preservation AS-IS (`surface='cli'` vs `surface='web'` distinguishable via `resolved_by`) + pre-resolution context section ABOVE choice menu.

**8 §16 operator-decision items ALL ACCEPTED at brainstorm defaults** (operator-orchestrator scope conversation 2026-05-18 post-merge): (1) banner navigation target → first-pending; (2) ORDER BY ASC oldest-first; (3) NO V1 dashboard per-discrepancy list (banked V2); (4) HX-Redirect query token `?reconcile_resolved={id}` included; (5) uniform `/dashboard` HX-Redirect target; (6) 12-line inline `<script>` for custom-value toggle; (7) `_parse_parametric_pick_count` helper duplicated private in web VM (CLI refactor V2-deferred); (8) 6-surface operator-witnessed gate (S1 inline pytest+ruff + S2 banner-link nav + S3 form-render with context + S4 successful POST + HX-Redirect + S5 banner-clears + S6 CLI/web parity).

**Sub-bundle decomposition recommended**: SINGLE sub-bundle with 11 tasks (T-2.1..T-2.11). Projection ~+45-75 fast tests + 1 slow E2E; 3-5 Codex rounds for executing-plans; ~6-10 hours operator-paced. Schema v19 UNCHANGED end-to-end.

**13 V2 candidates banked** (§15): audit-chain show page; success toast renderer; web Tier-3 override surface; web Tier-1 auto-correct undo; `/reconcile/pending` list page; pipeline-active exclusion on Tier-2; explicit `surface` column V2 migration; etc.

**8 forward-binding lessons banked** for writing-plans (return report §8): brief-conjecture-vs-actual-schema gap; BaseLayoutVM-inheritance asymmetric (13 existing VMs DO NOT inherit; carry standalone fields); hidden state anchors distinct from hidden audit fields; OriginGuard strict-vs-non-strict 303-fallback shapes; banner-link targets derive from canonical helper; audit-row parity tests use semantic-shape projection; grep-driven audits split by intent (field-declaration vs call-site); retrofit completeness is a discriminating test.

**Writing-plans dispatch UNBLOCKED.**

---

## 2026-05-18 Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect) SHIPPED at `6109261` — 4 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked (R1 M#3 banner-vs-briefing wording false-positive); ~+132 fast tests net (4575 → 4712); ruff/schema unchanged; 6-surface gate ALL PASS

**Integration-merge at `6109261`** (branch `phase12-5-bundle-1-oqf-executing-plans` via `--no-ff`; 18 task-branch commits = 11 task-impl + 2 task-review-fixes + 1 cross-bundle-pin follow-up + 2 Codex-fix + 2 return-report + 1 in-branch merge-of-finviz-fix). Includes orchestrator-driven 6-surface operator-witnessed gate PASS: S1 4712 fast + ruff 18 + slow E2E; S2 spec §10 cases A/C/E/I + determinism × 10 identical; S3 production run #15 ZERO multi-leg fires + ZERO false-positive Pass-1 (architectural fix HOLDS in negative sense); S4 banner-fires `data-banner-count="1"` + verbatim §8.3 wording + banner-clears via planted run #16 + ASCII-only + full revert; S5 `--resolved-by` filter operational; S6 pipeline #68 from empty inbox → `briefing.md` `## Reconciliation status` section + multi-leg line correctly omitted (count=0; F22 omit-when-zero works end-to-end through T-1.11).

**Highlights:**
- **Codex R2 surfaced a Sub-bundle C.C latent defect** — `_handle_split_into_partials` hardcoded `action="entry"` would have corrupted close-fill discrepancies via the new auto-routing path; fixed at handler (benefits both new auto-redirect path AND existing manual operator-resolved menu path) with 2 discriminating regression tests.
- **Sandbox-skipped path infrastructure deletion** — Codex R2 Major #1 surfaced + deleted unreachable `auto_redirect_skipped_sandbox` backfill counter (collides with Sub-bundle C.D §9.7 LOCK upstream which short-circuits sandbox BEFORE classification). T-1.6 service-layer + pivot-loop counter PRESERVED per F20 + spec §7.6 LOCK.
- **1 V2.1 §VII.F amendment candidate banked** (plan §A T-1.5.B 3-line drift after the deletion above).
- **1 new forward-binding lesson L-X1** (handler-extension audit pattern when auto-routing widens a handler's reach).
- **1 architectural inconsistency banked for Phase 12.5 #3** (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL — orchestrator-spotted during S4 gate sub-test planning: shipped helper SQL queries `rd.resolved_by = 'auto_tier1_multi_leg'` directly, so `apply_tier3_override` flipping parent disc `resolved_by` to `'operator'` WOULD clear the banner immediately, contradicting plan §H.4's "STILL present + count unchanged" claim. Reasonable operator semantic, but plan wording is imprecise. Phase 12.5 #3 watch-item).
- **Mid-gate dispatch: empty-finviz-inbox auto-fetch fix** — Phase 12.5 #1 S6 surfaced the pre-existing `phase3e-todo:940-958` bug (3rd gate-blocker occurrence). Inline-fix dispatched + shipped at `7a84942`; Phase 12.5 #1 branch merged main back in via `c406817` (in-branch merge); S6 re-ran successfully on merged state.
- **Phase 12.5 #2 dispatch UNBLOCKED.**

### Original entry (2026-05-17 PM; pre-executing-plans; superseded by SHIPPED outcome above)

## 2026-05-17 PM Phase 12.5 #1 writing-plans SHIPPED — OQ-F multi-leg tier-1 auto-redirect single-sub-bundle decomposition (11 tasks; ~+102 fast tests + 1 slow E2E + ~+435 LOC; schema v19 unchanged) — 5 Codex rounds NO_NEW_CRITICAL_MAJOR — 1 Critical + 12 Major + 8 Minor ALL RESOLVED; ZERO ACCEPT-WITH-RATIONALE

**Writing-plans SHIPPED 2026-05-17** at `2e8b10a` (integration merge of `phase12-5-bundle-1-oqf-writing-plans` via `--no-ff`; 2 plan commits = 1 initial + 1 Codex-fix bundle; **5 Codex rounds → NO_NEW_CRITICAL_MAJOR** non-monotonic-Major shape (R1 1C/4M/1m → R2 0C/3M/1m → R3 0C/4M/2m → R4 0C/1M/2m → R5 0C/0M/2m sealed; R3 bump above R2 driven by downstream drift the R2 fixes themselves surfaced); **ZERO ACCEPT-WITH-RATIONALE banked** — all 1 Critical + 12 Major + 8 distinct Minor resolved with code-content fixes; ZERO Critical findings post-R1 resolution; ZERO Co-Authored-By footer drift across 2 commits.

### Deliverable

- **Plan doc**: `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (1230 lines; grew from 1008 absorbing Codex chain; ~330 above 600-900 brief target — driven by R1 Critical #1 backfill-consumer scope expansion + R2-R4 acceptance-criteria depth).
- **Return report**: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md`.

### R1 Critical #1 — highest-value Codex catch (dead-code dispatcher prevention)

Initial draft would have shipped a dead-code dispatcher — multi-leg auto-redirect can only fire on the BACKFILL Pass-2 path (`reconciliation_backfill.py:_handle_pass_2`), NOT the initial pivot (which reads persisted `actual_value_json={"matched": null}` for `unmatched_*_fill` sentinels). T-1.5 scope widened to wire BOTH consumers; slow E2E moved to the operational firing site (backfill). Initial pivot stays as defensive future-proofing.

**Backfill consumer surface identified**:
- `reconciliation_backfill.py:_handle_pass_2`
- `reconciliation_backfill.py:run_backfill` orchestrator
- `reconciliation_backfill.py:format_summary_block` renderer
- `BackfillOutcome` dataclass
- `BackfillSummary` dataclass

### Single-sub-bundle decomposition LOCKED

- **11 tasks T-1.1..T-1.11** per plan §A
- **~+102 fast tests + 1 slow E2E** (refined from ~+85 pre-Codex)
- **~+435 LOC** (refined from ~+320 pre-Codex)
- **Schema v19 UNCHANGED** (F1 invariant + F19 plan-author schema additions escalation rule NOT triggered)

### 14 pre-locked decisions verbatim-encoded in plan §D

- 4 spec §2.1-§2.4 operator-locks (auto-redirect ON; all-match-within-tolerance; reuse apply_tier2_resolution; banner advisory only)
- 3 spec §15.B operator-locks (price_tolerance=$0.01 absolute; qty_tolerance asymmetry preserved; NO N-legs cap V1)
- 7 spec §15.A brainstorm-locks (n=1 multi-leg path; --resolved-by CLI filter; sandbox short-circuit gated; service API overrides; briefing.md +1 line; canary observability; resolved_by free TEXT)

### 25 binding invariants F1-F25

19 inherited + 6 NEW F20-F25 surfaced this dispatch:
- F20+F21 backfill-consumer wiring
- F22 service API override-parameter contracts
- F23 dataclass→dict boundary ownership
- F24 helper-function key-set stability
- F25 spec-locked rendering text verbatim

### 18 forward-binding lessons in plan §M (executing-plans inheritance)

**12 inherited from brainstorm** (8 spec §16 + 4 return report §8):
1-8. recipe-field discipline; override-parameter threading; free-text vs CHECK-enum distinction; cross-column CHECK invariants; sandbox short-circuit ALWAYS in inner; helper invocation completeness; ASCII-only banner text; discriminating-test patterns
9-12. 4 chain-surfaced lessons in brainstorm return report §8

**6 NEW writing-plans-surfaced L-W1..L-W6:**
- L-W1 (R1 Critical #1): When designing a dispatcher pattern + recipe consumption, enumerate EVERY dispatcher consumer; initial pivot's source_payload derivation matters; if it returns None for unmatched sentinel, the dispatcher in that path is dead-code; operational consumer lives ELSEWHERE.
- L-W2 (R1 Major #1): Spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering in plan tasks, NOT as "PLAN DECISION" overrides.
- L-W3 (R1 Major #2): Spec-locked rendering text MUST be verbatim-asserted in tests; don't lift adjacent patterns without checking the new lock.
- L-W4 (R1 Major #3): Retrofit scope predicates MUST be enumerated by canonical mechanism (template-mount), NOT proxy field-presence.
- L-W5 (R1 Major #4): Helper functions producing normalized dicts MUST emit stable key-set across ALL input branches.
- L-W6 (R1 minor #1): Conversion seams (dataclass→dict at module boundary) MUST be owned by ONE task with clear contract.

### Comparison to precedents

1C/12M mid-pack for project history:
- C.B was 1C/6M
- C.D was 0C/6M
- post-Phase-12 mapper-widening ~6 rounds
- Phase 12.5 #1 brainstorm 0C/15M (cleanest)

R1 Critical was high-value architectural catch; R2-R4 absorbed downstream drift from R1 fixes themselves; R5 cleaned up final stale text.

### Executing-plans dispatch UNBLOCKED

Orchestrator's next deliverable: draft executing-plans dispatch brief encoding plan §A T-1.1..T-1.11 + plan §D 14 locks + plan §F 25 invariants + plan §M 18 forward-binding lessons. Per plan §L scaffold.

### Worktree teardown status

- Branch `phase12-5-bundle-1-oqf-writing-plans` merged via `--no-ff` at `2e8b10a`; on-disk husk at `.worktrees/phase12-5-bundle-1-oqf-writing-plans/` matches cleanup-script regex `phase\d+[-_]` — operator-paired cleanup pass post-merge.

### Cross-references

- Writing-plans dispatch brief: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md` (`5c988d2`).
- Plan doc: `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (in `2e8b10a` merge).
- Return report: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md` (in `2e8b10a` merge).
- Integration merge: `2e8b10a`.
- Brainstorm spec (predecessor): `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (at `a1582c0`).

---

## 2026-05-17 PM Phase 12.5 #1 brainstorm SHIPPED — OQ-F multi-leg tier-1 auto-redirect (V2 follow-up from post-Phase-12 mapper-widening spec §6.6) — 7 Codex rounds NO_NEW_CRITICAL_MAJOR — ZERO ACCEPT-WITH-RATIONALE banked across 15 Major + 10 Minor (cleanest brainstorm chain in project history)

**Brainstorm SHIPPED 2026-05-17** at `a1582c0` (integration merge of `phase12-5-bundle-1-oqf-brainstorm` via `--no-ff`; 8 implementer commits = 1 draft + 6 Codex-fix + 1 return-report; **7 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 5M/2m → R2 3M/2m → R3 2M/2m → R4 2M/2m → R5 2M/1m → R6 1M/1m → R7 0); **ZERO ACCEPT-WITH-RATIONALE banked across all 15 Major + 10 Minor findings — cleanest brainstorm chain in project history**; ZERO Critical findings entire chain; ZERO Co-Authored-By footer drift across 8 commits.

### Deliverables

- **Spec doc**: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (1236 lines; mirrors Sub-bundle C spec format §0-§17).
- **Return report**: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md`.
- **Session state**: `%TEMP%/.copowers-session-0ca8f15d6677.json`.

### 4 operator-locked decisions (§2.1-§2.4 verbatim binding clauses; preserved through all 7 Codex rounds)

1. Auto-redirect posture = ON
2. Confidence threshold = all-match-within-tolerance per spec §4.4 determinism principle
3. Auto-correct handler shape = reuse `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied')`
4. Operator-facing UX = banner advisory only

### Brainstorm-locked at §15.A (Codex chain resolved during 7 rounds)

- §6.5 n=1 single-order multi-leg path LOCKED YES via ambiguity_kind reclassification (Codex R1 M2)
- §8.6 `--resolved-by <value>` CLI filter LOCKED IN-BUNDLE at T-1.10 (Codex R1 M5; banner template cites filter; both land together)
- §7.6 sandbox short-circuit gated-on-auto-redirect + SAVEPOINT ROLLBACK pattern (Codex R1 M3)
- §7.4 service API LOCKED to `operator_custom_payload` (existing kwarg) + new `applied_by_override` / `correction_action_override` / `resolved_by_override` overrides (Codex R1 M4)
- §11.2 briefing.md +1 line per run for `tier1_multi_leg_redirected_count` when > 0
- §12.3 canary observability for empty-executions case (~+5 LOC + 1 test; Sub-bundle 1.5 canary precedent)
- §13.3 Brief §2.4 amendment banked — no `_RESOLVED_BY_VALUES` constant exists; resolved_by is free TEXT; brief writer error caught by Codex R1 M4

### Schema v19 UNCHANGED LOCK

Corrections + discrepancies CHECK enums already accommodate `auto_applied` + `auto` + new free-TEXT `resolved_by='auto_tier1_multi_leg'`. NO migration required.

### 3 still-open operator-decision items at §15.B (writing-plans handoff)

Brainstorm proposes defaults; operator may override at writing-plans-brief drafting:

1. **§4.4 `price_tolerance` threshold** — brainstorm default: LOCK $0.01 absolute (matches spec §4.4 inheritance + existing codebase). Operator may override toward `max($0.01, abs(journal_price) * 0.001)` for higher-priced stocks.
2. **§6.3 `qty_tolerance` mismatch** — brainstorm default: LOCK predicate=1e-9 (handler uses 1e-6; strictness asymmetry is safe — predicate stricter than handler).
3. **§6.4 defensive cap on N legs** — brainstorm default: NO cap V1 (production evidence supports unbounded; mapper-coherence-check already filters pathological shapes). Operator may impose cap (e.g., 50) for memory hygiene.

### Single sub-bundle ship recommended

**NOT** 2-3 sub-bundle decomposition originally projected. Brainstorm consolidated to:
- ~+320 LOC across 11 tasks
- ~+85 fast tests + 1 slow E2E
- 3-5 Codex rounds projected for executing-plans

### 12 V2 candidates banked at §14

(further widening; per-leg surfacing; multi-account variants; etc.)

### 12 forward-binding lessons for writing-plans

8 from spec §16 + 4 Codex-chain-surfaced in return report §8:
1. Recipe-field discipline (auto_redirect_recipe=None default preserves existing emit paths)
2. Override-parameter threading with verbatim-existing default values
3. Free-text columns vs CHECK enum columns (pre-flight `grep -n CHECK` for every new string value)
4. Cross-column CHECK invariants (`(ambiguity_kind, resolution)` pairing through service-layer)
5. Sandbox short-circuit ALWAYS in inner (C.C lesson #2 carry-forward)
6. Helper invocation completeness + grep retrofit test discipline (Phase 10 T-E.3 + Sub-bundle 2 precedent)
7. ASCII-only banner text (CLAUDE.md cp1252 gotcha pre-emption)
8. Discriminating-test patterns for predicate edge cases (Codex R2 M2 + R3 M1)
9-12. 4 Codex-chain-surfaced lessons per return report §8

### Writing-plans dispatch UNBLOCKED

Consumes locked spec (§2 operator-locks + §15.A brainstorm-locks) + 12 forward-binding lessons + 3 still-open §15.B items. Expected 3-5 Codex rounds; output plan doc decomposing into 11 tasks for single-sub-bundle executing-plans dispatch.

### Worktree teardown status

- Branch `phase12-5-bundle-1-oqf-brainstorm` merged via `--no-ff` at `a1582c0`; on-disk husk matches cleanup-script regex `phase\d+[-_]` — operator-paired `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass post-merge.

### Cross-references

- Brainstorm dispatch brief: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (`37b584d`).
- Spec doc: `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (in `a1582c0` merge).
- Return report: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md` (in `a1582c0` merge).
- Integration merge: `a1582c0`.
- Spec §6.6 OQ-F V2 LOCK (predecessor): `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md:561-590`.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 2 SHIPPED — /schwab/status web counterpart (T-B.7 follow-up from Phase 12 Sub-bundle B) — 5-surface orchestrator-witnessed GATE ALL PASS — CLOSES post-Phase-12 mapper-widening arc

**Sub-bundle 2 SHIPPED 2026-05-17** at `690aed0` (integration merge of `schwab-mapper-bundle-2` via `--no-ff`; 13 implementer commits = 7 task-impl (T-2.0..T-2.6) + 3 Codex-fix (R1 Critical #1 + Major #1 + R2 Major #1 + R3 Minor #1) + 1 return-report + 1 merge; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/1M → R2 0C/1M → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 findings resolved with code-content fixes; ZERO Co-Authored-By footer drift; **+52 fast tests** (4523 → 4575); ruff 18 unchanged; schema v19 unchanged consumer-side.

### Architectural surface (deferred Phase 12 Sub-bundle B T-B.7 task — read-only web mirror of `swing schwab status` CLI)

1. **`swing/web/view_models/schwab.py`** — NEW `SchwabStatusVM` + `SchwabCallSummary` frozen dataclasses with `__post_init__` validators (LIVE/PROVISIONAL/DEGRADED triplet per plan §A.0.1 D3 + shipped CLI; `state_reason is None iff state == 'LIVE'` invariant; 5-field base-layout VM banner pin per Phase 10 T-E.3 retrofit).
2. **`swing/web/routes/schwab.py`** — NEW `GET /schwab/status` route handler with `apply_overrides(cfg)` discipline + case-insensitive `?environment=` query-param override + PlainTextResponse for invalid env (Codex R1 Major #7 + R2 Major #1 XSS-safe primitive) + sentinel-leak audit + `_redact_error_message_for_audit` read-time re-redactor at `build_schwab_status_vm`. EXISTING `POST /schwab/setup` HX-Redirect retarget `/config?schwab_setup=ok` → `/schwab/status` with passive no-op consumer retention one release window (Codex R1 m#2 LOCK).
3. **`swing/web/templates/schwab_status.html.j2`** — NEW template extending `base.html.j2` + 3-state LIVE/PROVISIONAL/DEGRADED color-coded badge (`state-ok` green / `state-warn` yellow / `state-error` red) + refresh-token TTL countdown with severity styling + recent-calls table + environment switcher (`?environment=production` / `?environment=sandbox` plain anchor links) + re-auth link to `/schwab/setup` when state != LIVE + Jinja2 autoescape regression test + 4-sentinel audit-trail coverage.
4. **`swing/web/templates/config.html.j2`** — ONE-LINE addition: second `<a>` in "External integrations" `<ul>` section linking to `/schwab/status`.

### Codex chain convergence

- **R1 Critical #1 (error_excerpt sentinel leakage)**: template rendered `vm.error_excerpt` directly + sentinel-leak test exempted audit `error_message` sentinel "operator-visible by design". If any historical or future audit row contained unredacted token bytes, `/schwab/status` would disclose them. **Two-layer fix**: (a) drop `error_excerpt` rendering from template per spec §7.4 OQ-D CLI 1:1 LOCK (CLI `_render_recent_calls` shows endpoint + status + http only); (b) re-redact `c.error_message` at read time in `build_schwab_status_vm` via `_redact_error_message_for_audit` (idempotent; defense-in-depth); strengthen sentinel-leak test to assert ALL 4 sentinels absent.
- **R1 Major #1 (status enum narrower than CLI)**: `_SCHWAB_CALL_STATUSES = {'success', 'auth_failed', 'rate_limited', 'error'}` (4) silently dropped `in_flight` + `concurrent_refresh` rows. CLI renders every row regardless of status. **Fix**: widen frozenset to all 6 schema CHECK values per migration 0018 + drop now-no-op filter.
- **R2 Major #1 (tokens_db_path leak)**: VM stored `str(tokens_path)` rendering operator's full local home (Windows `C:\Users\rwsmy\swing-data\...` / POSIX `/home/<username>/swing-data/...`). Spec §7.1 explicitly requires "display-only, masked if path contains user-profile prefix". **Fix**: mask via `Path.relative_to(home).as_posix()` prefixed with `~/` when under `_user_home()`; falls back to full path defensively. NEW discriminating regression test plants tokens DB in `tmp_path`, asserts masked form rendered + absolute form NOT in body.
- **R3 Minor #1 (template sentinel audit narrower)**: template-surface ratchet planted tokens-DB sentinels only; plan §B T-2.2 test #10 requires both tokens DB AND `schwab_api_calls.error_message` row sentinels. Route-level T-2.1 test 13 already covers broader scope. **Fix**: extend template sentinel list to 4 (add `LEAK_TPL_AUDIT_ERROR_MESSAGE_SENTINEL`); plant via direct INSERT; assert ZERO substring matches for ALL 4.

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM via curl + grep on worktree web server port 8081)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4575 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~85s wall-clock).
- **S2 PASS** — `/schwab/status` HTTP 200 / 8765 bytes — `class="schwab-status-badge state-ok"` + `data-state="LIVE"` discriminating CSS marker + H1 "Schwab integration status (production)" + Refresh token TTL section + env switcher links (production + sandbox) + 6-row Recent API calls `<table class="schwab-recent-calls">` + **masked tokens_db_path (ZERO `C:\Users` occurrences in response body — Codex R2 Major #1 fix HOLDS)** + ZERO Jinja UndefinedError / TemplateSyntaxError leaks + base-layout integration intact (Metrics nav link + theme toggle).
- **S3 PASS** — `/config` HTTP 200 / 11362 bytes — "External integrations" section + BOTH `href="/schwab/setup"` + `href="/schwab/status"` nav-links present (count=1 each; T-2.3 acceptance MET).
- **S4 SKIPPED** per brief §3 default (refresh-token clock healthy ~5 days remaining at gate time; T-2.4 retarget covers via test).
- **S5 PASS** — ruff 18 E501 unchanged.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0** (preserved through Sub-bundle 1+1.5+2 ships).
- `/schwab/status` renders LIVE for production environment with masked path; visible-only fields are derived metadata (no raw token bytes ever surface).
- 4 historical correction chains preserved unchanged.

### Post-Phase-12 mapper-widening arc CLOSED — Phase 12.5 dispatches UNBLOCKED

**Arc-cumulative aggregate** (Sub-bundle 1 + 1.5 + 2):
- ~24 + 14 + 11 = **49 commits** (28 task-impl + 13 Codex-fix + 3 return-reports + 3 merges + 2 housekeeping)
- 5 + 4 + 3 = **12 Codex rounds total** (NO_NEW_CRITICAL_MAJOR all rounds)
- +115 + 48 + 52 = **+215 cumulative fast tests** (~4360 → 4575)
- 0 + 2 + 0 = **2 ACCEPT-WITH-RATIONALE banked** (both Sub-bundle 1.5; T-1.5.4 sequence + canary minimal scope)
- 0 + 0 + 0 = **ZERO Co-Authored-By footer drift**
- 0 + 0 + 4 = **4 V2.1 §VII.F amendments banked** (all Sub-bundle 2; spec §7.1)
- 0 + 0 + 2 = **2 CLAUDE.md gotcha promotion candidates banked** (all Sub-bundle 2; for Phase 12.5 #3)
- Schema v19 unchanged across entire arc

**Next dispatches** (Phase 12.5; operator-locked 2026-05-17 sequencing):
1. **Phase 12.5 #1: OQ-F multi-leg tier-1 auto-redirect** — direct V2-mapper-widening successor; consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers + Sub-bundle 1.5's confirmed-firing extraction path. **RECOMMENDED FIRST.**
2. **Phase 12.5 #2: Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2; web counterpart of C.D's CLI surface.
3. **Phase 12.5 #3: Project hygiene maintenance pass** (5 sub-items per operator-requested 2026-05-17 expansion) — (a) CLAUDE.md archive-split + (b) orchestrator-context archive-split + (c) V2.1 §VII.F amendment batch processing + (d) Phase 8 walkthrough failing-test triage/fix + (e) Ruff 18 E501 cleanup.

**Phase 13 scope LOCKED** at `docs/phase13-scope-brainstorm.md` §0.5 (operator-decided 2026-05-17); dispatch gated on Phase 12.5 close.

### Worktree teardown status

- Branch `schwab-mapper-bundle-2` merged via `--no-ff` at `690aed0`; on-disk husk at `.worktrees/schwab-mapper-bundle-2/` **CLEANED by operator post-merge** (`cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass; branch matches `schwab(?:-\w+)?-bundle-` regex). All 3 post-Phase-12 husks (`schwab-mapper-bundle-1` + `schwab-mapper-bundle-1.5` + `schwab-mapper-bundle-2`) cleared in single operator pass.

### S2 visual confirmation closed

- The 5-surface gate was orchestrator-driven via curl + grep (per phase3e-todo gate-outcome §"GATE OUTCOME"). **S2 visual confirmation closed post-merge by operator** via Chrome MCP-equivalent browser inspection of `/schwab/status` page (LIVE state-ok badge color rendering + recent-calls table + env switcher behavior + base-layout integration all OK end-to-end). The curl+grep gate caveat from Sub-bundle 2 gate-outcome message is RESOLVED.

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-2-schwab-status-web-counterpart-executing-plans-dispatch-brief.md` (`01d2e11`).
- Return report: `docs/post-phase12-schwab-mapper-bundle-2-return-report.md` (in `690aed0` merge).
- Plan §B: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md:624-857` (T-2.0..T-2.6).
- Integration merge: `690aed0`.

### 4 V2.1 §VII.F amendments banked (return report §7)

1. Spec §7.1 state-triplet misnamed (CONFIGURED/PROVISIONAL/NOT_CONFIGURED → actual LIVE/PROVISIONAL/DEGRADED per shipped CLI).
2. Status enum widening (4 → 6 values matching schema CHECK constraint per migration 0018).
3. `tokens_db_path` masking pattern (display-only; mask under user-home prefix; Path.relative_to fallback discipline).
4. `error_excerpt` rendering scope per OQ-D CLI 1:1 LOCK (drop from template + read-time re-redact at VM build).

### 2 CLAUDE.md gotcha promotion candidates banked for Phase 12.5 #3 triage

1. **Read-time re-redactor discipline**: when a VM rendering surface exposes audit fields that flow from `*.error_message` rows, the VM-build helper MUST re-invoke the redactor at read-time (defense-in-depth against pre-redaction-discipline rows OR future write-time redactor bugs). Pattern: `vm.error_message_for_audit = _redact_error_message_for_audit(row.error_message)` at the VM construction step.
2. **`tokens_db_path` masking pattern**: file-path fields rendered in operator-facing UI MUST mask paths under `_user_home()` prefix via `Path.relative_to(home).as_posix()` prefixed with `~/`; fall back to full path defensively when `relative_to` raises (defense against unexpected paths). Pre-empt in any new file-path-in-VM design.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 1.5 SHIPPED — Schwab mapper validator-drop fix (filledQuantity==0 early-exit gate + observability canary + diagnostic script + production-shape regression tests) — 5-surface operator-witnessed GATE ALL PASS — CLOSES Sub-bundle 1's validator-drop defect; post-Phase-12 architectural arc CLOSED

**Sub-bundle 1.5 SHIPPED 2026-05-17** at `a7c1016` (integration merge of `schwab-mapper-bundle-1.5` via `--no-ff`; 13 implementer commits + 1 return-report + 1 merge; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/6M/2m → R2 0C/2M/2m → R3 0C/0M/2m → R4 0C/0M/1m); **2 ACCEPT-WITH-RATIONALE banked** (R1 M#2 T-1.5.4 sequence-by-design + R2 M#1 canary intentionally minimal — `price > 0` strongest signal + widening false-positives on placeholder `quantity > 0`); ZERO Co-Authored-By footer drift; **+48 fast tests** (4475 → 4523); ruff 18 unchanged; schema v19 unchanged.

### Architectural fix lands across 2 surfaces

1. **`swing/integrations/schwab/mappers.py:_extract_executions_from_order_raw`** — 12-line additive early-exit gate when `filled_qty == 0` (EXPLICIT zero only; preserves "filledQuantity absent: permissive" stance for legacy V1 path). Returns `None` pre-empting drop+warn cascade across STOP-typed placeholder family.
2. **`swing/integrations/schwab/mappers.py:_has_non_placeholder_leg`** — NEW module-level canary helper emits WARN inside gate when any leg in `activityType=EXECUTION` activity has `price > 0` (anomalous-shape canary for future Schwab regression where real-fill sentinel surfaces despite `filledQuantity=0`).

**T-1.5.1 diagnostic infrastructure (FOLDED)**:
- `scripts/diagnose_schwab_executionlegs.py` (859 lines + 25 tests with 5-sentinel sentinel-leak audit; 3-layer redaction Layer 0 exact-replace + Layer 1a JSON-key regex + Layer 1b 32+ hex + Layer 1c 40+ base64; ASCII-only stdout for cp1252 safety; bypasses `_audited_get_account_orders` to capture pre-validator raw shape).
- Generalizable diagnostic-script pattern for any future Schwab API-shape investigation (forward-binding lesson #1).

### Root cause (CONFIRMED via T-1.5.1 against operator's production 2026-05-17 16:52:48 UTC)

H1-H5 from brief §0.1 ALL FALSIFIED. Actual root cause = **H1-extended (UNANTICIPATED family)**: Schwab emits placeholder `executionLegs[]` on STOP-typed orders that NEVER executed (status REPLACED/CANCELED/PENDING_ACTIVATION) — `filledQuantity=0` AND `executionLegs[0].price=0.0` (sentinel placeholder) AND `executionLegs[0].quantity>0` (reflects order's intended size).

**Production data distribution (30-day window)**:
- 22 total orders inspected
- 17 with `executionLegs[]` present
- **12 of 17 are placeholder shapes** (filledQuantity=0 / leg.price=0.0) — STOP/REPLACED/CANCELED/PENDING_ACTIVATION family
- **5 of 17 are real FILLED LIMIT orders with `price > 0`**:
  - CVGI @ $12.6999 (filled 2026-05-15; 18 shares)
  - LION @ $8.585 (filled 2026-05-14; 9 shares)
  - VIR @ $55.5337 (filled 2026-05-13; 2 shares)
  - YOU @ $10.78 (filled 2026-05-13; 7 shares)
  - YOU @ $11.7066 (filled 2026-05-08; 7 shares)

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM via implementer-paired session)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4523 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~93s wall-clock).
- **S2 PASS** — 4 new test files 23/23 regression coverage PASS.
- **S3 PRODUCTION FETCH PASS** — `python -m swing.cli schwab fetch --orders` (worktree-side per `feedback_worktree_cli_invocation.md`) emitted reconciliation_run #14 (state=completed; tier1_applied_count=0; tier2_pending_count=2; schwab_orders_checked=30 vs Sub-bundle 1's 18; ZERO validator-drop warnings in stderr/audit; ZERO false-positive entry/close_price_mismatch — architectural fix HOLDS both negative sense AND positive sense [executions flow through extraction; 4 FILLED LIMIT orders matched cleanly via Shape A/B without needing Shape C tier-1 corrections because operator's journal prices already align]).
- **S4 PASS** — Phase 10 banner cleared to 0 after 2 dispositions (run #14 ids 50+51 — same Pass-1-NO-MATCH DHC+VSAT family run #13 handled identically; `acknowledge` per C.D-precedent for `ambiguity_kind=unsupported`; correction_ids 15+16).
- **S5 PASS** — ruff 18 E501 unchanged.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0** (preserved).
- System EXITS safe-degraded mode. V2 mapper widening's positive lift now confirmed firing on production data via Shape A/B paths.
- 4 historical correction chains preserved (correction_ids 11+12+13+14 from Sub-bundle 1 gate + 15+16 from Sub-bundle 1.5 gate — all acknowledge-only no-mutation entries for DHC+VSAT unmatched-fill family).

### Post-Phase-12 architectural arc CLOSED — Sub-bundle 2 + Phase 12.5 dispatches UNBLOCKED

**Next dispatches** (Phase 12.5; operator-locked 2026-05-17):
1. **Phase 12.5 #1: OQ-F multi-leg tier-1 auto-redirect** — direct V2-mapper-widening successor; consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers + Sub-bundle 1.5's confirmed-firing extraction path. Highest operator-fit value.
2. **Phase 12.5 #2: Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2; web counterpart of C.D's `swing journal discrepancy resolve-ambiguity` + `override-correction` CLIs.
3. **Phase 12.5 #3: CLAUDE.md + orchestrator-context.md maintenance pass** — addresses cap-drift (~50+ entries vs ~30 cap).

**Phase 13 scope LOCKED** at `docs/phase13-scope-brainstorm.md` §0.5 (operator-decided 2026-05-17); dispatch gated on Phase 12.5 close.

### Worktree teardown status

- Branch `schwab-mapper-bundle-1.5` merged via `--no-ff` at `a7c1016`; on-disk husk at `.worktrees/schwab-mapper-bundle-1.5/` ACL-locked pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (branch matches `schwab(?:-\w+)?-bundle-` regex per `cleanup-locked-scratch-dirs.ps1:156`).

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-1.5-validator-drop-fix-executing-plans-dispatch-brief.md` (`aec3019`).
- Return report: `docs/post-phase12-schwab-mapper-bundle-1.5-return-report.md` (in `a7c1016` merge).
- Integration merge: `a7c1016`.
- Sub-bundle 1 SHIPPED entry below: predecessor (PASS-WITH-FINDING; closes the validator-drop defect routing).

### 5 forward-binding lessons (return report §11)

1. **Diagnostic-script pattern generalizable** to any future Schwab API-shape investigation (3-layer redaction + ASCII-only stdout + thin-seam helpers for mock-testability + sentinel-leak audit pattern).
2. **TYPE-only "would_pass_validator" labels are misleading** — always discriminate type vs value-range. Codex R1 M#5 caught the diagnostic script's misleading `legs_would_pass_validator` metric → renamed `legs_would_pass_type_shape_only`.
3. **Canary observability hooks for silently-suppressed code paths require explicit design-decision documentation** — minimal-canary + ACCEPT-WITH-RATIONALE pattern (documented inline in helper docstring) is project-canonical approach for "silent skip" semantics.
4. **Codex-chain brittleness around line-number references** — prefer function/block names + descriptive English over file:line citations in docstrings/comments. AI-generated docstrings often pin line numbers that become stale within months.
5. **T-1.5.4 / S3 operator-witnessed gate sequencing is post-Codex-by-design** — include "operator-witnessed gate sequencing" explicitly in §0.5 BINDING contracts of future briefs to pre-empt Codex Major finding family.

### 1 V2 candidate banked

1. **Separate canary helper for malformed-shape detection** (R2 Minor #2 banked V2). Current `_has_non_placeholder_leg` returns False on malformed (non-coercible) leg prices, preserving no-false-positive contract. Future hardening: separate helper / result enum distinguishing "anomalous positive-price" from "malformed/uncoercible". Documented inline in `_has_non_placeholder_leg` docstring.

---

## 2026-05-17 PM Post-Phase-12 Sub-bundle 1 SHIPPED — V2 Schwab mapper execution-grain widening + classifier consumer + comparator + housekeeping (FOLDED) — GATE PASS-WITH-FINDING; Sub-bundle 1.5 follow-up dispatch UNBLOCKED

**Sub-bundle 1 SHIPPED 2026-05-17** at `120c992` (integration merge of `schwab-mapper-bundle-1` via `--no-ff`; ~24 implementer commits + 1 orchestrator handoff brief at `54c7b9d`; 26 files / 5225 insertions). 5 Codex rounds NO_NEW_CRITICAL_MAJOR; **ZERO ACCEPT-WITH-RATIONALE banked**; ZERO Co-Authored-By footer drift; +115 fast tests (4360 → 4475); ruff 18 unchanged; schema v19 unchanged.

### Architectural fix lands across 4 surfaces

1. **`swing/integrations/schwab/models.py`** — NEW `SchwabExecutionLeg` frozen dataclass (6 fields; `__post_init__` validators rejecting bool/NaN/inf/zero/negative) + `SchwabOrderResponse.executions: list[SchwabExecutionLeg] | None = None` tri-valued tail field (8-positional backward compat preserved).
2. **`swing/integrations/schwab/mappers.py`** — `map_orders_to_fill_candidates` widened via NEW `_extract_executions_from_order_raw` helper with defensive parsing (non-EXECUTION skip; non-dict skip+warn; leg-validator drop+warn; empty→None collapse; `sum(legs.qty) == filledQuantity` coherence check else collapse; R2 pre-coercion bool/non-str-time rejection).
3. **`swing/trades/schwab_reconciliation.py`** — NEW helpers `_compute_execution_price` (single-leg → leg.price; multi-leg → VWAP), `_resolve_match_quantity` (execution-grain quantity), `_is_execution_bearing_candidate` (candidate-pool widening for MARKET-with-price=None + CANCELED/REPLACED partials). Comparator switched to execution-grain price + Path B `execution_unavailable=true` sentinel emit + Shape C `actual_value_json` shape + 4dp delta_text precision.
4. **`swing/trades/reconciliation_classifier.py`** — NEW `_EXECUTION_AUDIT_KEYS` + `_SHAPE_C_EXPECTED_KEYS` constants. Shape C branch added to `_classify_entry_price_mismatch` + `_classify_close_price_mismatch` (ADDITIVE; Shape A + B preserved). `_classify_unmatched_fill_shared` Path B sentinel recognition (V1 Pass-2 LIFT scope = Pass-1 only; OQ-F V2 deferred).

**Housekeeping FOLDED** per operator decision 2026-05-17:
- CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amended V2-RESOLVED for Pass-1 family.
- CVGI date typo verified ZERO matches in CLAUDE.md (no-op-with-note).
- NEW `swing journal discrepancy show-correction <id>` CLI subcommand + generic ID-free `_HISTORICAL_CORRECTION_NOTE` epilog (per spec §8.3 OQ-G + plan §A.0.1 D1).

**Infrastructure**: T-1.0 cassette runbook at `docs/runbooks/schwab-cassette-recording.md` + NEW `scripts/record_schwab_cassettes.py` (686 lines) + `tests/conftest.py:vcr_config` sanitization filter extension. Operator-paired cassette session `ec498fe` recorded 3 of 4 REQUIRED order types (MARKET BUY + STOP_LIMIT FIRED hand-rolled per operator history absence). Codex R3 Critical accountNumber leak + R4 over-redaction both fixed in-place across the 3 committed cassettes at `tests/integrations/cassettes/schwab/`.

**E2E test (T-1.13; `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py`):** 6 slow tests exercising 3 cassette-driven + 3 hand-rolled fixtures end-to-end through the mapper → comparator → classifier → audit-row persistence pipeline.

### GATE OUTCOME (orchestrator-driven 2026-05-17 PM)

- **S1 PASS** — inline `pytest -m "not slow" -q -n auto` 4475 fast + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (~93s wall-clock).
- **S2 PASS** — 6 slow E2E tests via cassette + hand-rolled fixtures (4.35s).
- **S3 PASS-WITH-FINDING** — `python -m swing.cli schwab fetch --orders` from worktree emitted reconciliation_run #13 (state=completed; discrepancies_emitted=2; tier1_applied_count=0; tier2_pending_count=2). **ZERO false-positive entry/close_price_mismatch** confirms architectural fix HOLDS in negative sense. **CRITICAL FINDING (routes to Sub-bundle 1.5)**: ALL 18 production orders had `orderActivityCollection[0].executionLegs[0]` uniformly rejected by `SchwabExecutionLeg.__post_init__` validator at mapper drop+warn. Positive lift NEVER FIRED on production despite cassette + hand-rolled E2E tests all passing. Root cause unknown — `schwab_api_calls` does NOT capture `response_body_json`. Hypothesis: synthetic-fixture-vs-production-emitter shape drift family (C.D-arc lesson #2 + #4 inheritance).
- **S4 SKIPPED** operator preference (S3 sufficient).
- **S5 PASS** — Phase 10 banner cleared to 0 after 4 dispositions (run #12 ids 46+47 + run #13 ids 48+49 — all DHC+VSAT unmatched_open_fill; `acknowledge` per C.D-precedent for `ambiguity_kind='unsupported'`; correction_ids 11+12+13+14). 4 dispositioned because run #12 fired ~3 min before our gate (per-run-vs-per-fill re-emission family).
- **S6 + S7** deferred operator-async review (CLAUDE.md gotcha amendment text + `show-correction --help` epilog).
- **S8 PASS** — ruff 18 E501 unchanged.
- **S9 SKIPPED** optional.

### Production state post-gate

- **ZERO unresolved-material discrepancies; banner count=0.**
- System operating in safe-degraded mode (V1-equivalent behavior + Path B sentinel emit; no false-positives; positive lift gated on Sub-bundle 1.5 fix).
- 4 historical correction chains preserved (correction_ids 11+12+13+14 are acknowledge-only no-mutation entries for DHC fill_id=2 + VSAT fill_id=6).

### Sub-bundle 1.5 follow-up dispatch UNBLOCKED — NEXT ORCHESTRATOR FIRST DELIVERABLE

**Scope**: validator-drop defect investigation + fix.
- **Diagnostic phase**: capture raw Schwab response shape for one failing order (options: temp debug logging at mapper drop-point + re-run schwab fetch; OR one-shot direct API call via schwabdev bypassing mapper; OR schema extension to capture `response_body_json` — implementer picks).
- **Fix phase**: amend validator OR amend mapper pre-coercion OR amend field-extraction to match actual Schwab production shape. Discriminating regression test landing in cassette form.
- **Re-verification**: re-run S3 against production; verify `tier1_applied_count > 0` IF eligible discrepancies, OR at minimum NO validator-drop warnings logged.

**Dispatch metadata**:
- Branch: `schwab-mapper-bundle-1.5` (matches cleanup-script regex `schwab(?:-\w+)?-bundle-`)
- Worktree: `.worktrees/schwab-mapper-bundle-1.5/`
- Codex chain budget: 2-4 rounds (focused defect fix)
- Gate: 3-5 surfaces (S1 fast tests + S2 cassette + S3 production re-run + S4 banner + S5 ruff)
- Schema impact: likely v19 unchanged unless schema extension chosen for diagnostic capture

### Worktree teardown status

- Branch `schwab-mapper-bundle-1` merged via `--no-ff` at `120c992`; on-disk husk at `.worktrees/schwab-mapper-bundle-1/` ACL-locked pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass.

### Cross-references

- Dispatch brief: `docs/post-phase12-schwab-mapper-bundle-1-execution-grain-widening-executing-plans-dispatch-brief.md` (`e2a11bf`).
- Plan: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (`cc6fd2d`).
- Spec: `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (`dda8730`).
- Integration merge: `120c992`.
- Handoff brief: `docs/orchestrator-handoff-2026-05-17-post-sub-bundle-1.md` (`54c7b9d`).

---

## 2026-05-17 Phase 12.5 RESCOPED — 3-item bundle (operator-locked scope; queued post-Sub-bundle-2 ship of post-Phase-12 mapper-widening arc; item #2 fill auto-population FOLDED INTO Phase 13 Theme 3 per operator decision 2026-05-17)

**Scope (operator-locked 2026-05-17; rescoped 2026-05-17 to drop fill auto-population → moved to Phase 13 Theme 3 which absorbs entries + exits + reviews coherently):**

1. **OQ-F multi-leg tier-1 auto-redirect** — direct successor to V2 mapper widening. When V2 mapper exposes execution-grain data for multi-leg fills (sum of `executionLegs[].quantity` matches journal qty + per-leg VWAPs align within `price_tolerance`), classifier auto-redirects tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` instead of forcing operator menu disposition. Spec §6.6 V2 LOCK + writing-plans §Z #1 V2 candidate. Cascade analysis required: confidence threshold; classifier dispatch state; auto-correct handler shape (consumes Sub-bundle C.C `apply_tier2_resolution(..., choice_code='split_into_partials', payload=...)` with operator-derived payload synthesized from execution-leg data); operator-decided UX (does the auto-redirect emit a banner advisory? Surface for review?). **Estimated 2-3 sub-bundles** (brainstorm + writing-plans + 1-2 executing-plans dispatches); **schema v19 likely unchanged** (auto-redirect consumes existing handler registry).
2. **Web Tier-2 discrepancy-resolution surface** — Sub-bundle C plan §I.3 V2. Web counterpart of C.D's `swing journal discrepancy resolve-ambiguity` + `override-correction` CLIs. Operator-facing HTMX form for tier-2 menu selection + `--custom-value` shape entry + tier-3 override workflow. Inherits Sub-bundle B + 2 web architecture (apply_overrides cascade; HTMX gotcha trinity; base-layout VM banner pin; Phase 6 I3 target-route-registered check). **Estimated 1-2 sub-bundles**; consumes existing C.C service entries + C.D CLI menu helper unchanged.
3. **Project hygiene maintenance pass** — addresses cap-drift + test stability + ruff cleanup in one focused dispatch (operator-requested scope expansion 2026-05-17 post-Sub-bundle-1.5-merge). Five sub-items:
   - **(a) CLAUDE.md archive-split** — active status-line paragraph cap-drift (~52 entries vs ~30 cap); archive SHIPPED phase entries to `CLAUDE.md.archive` following 2026-05-05 archive-companion precedent; preserve index/cross-references in active file.
   - **(b) orchestrator-context.md archive-split** — active "Lessons captured" section growing past retention discipline cap (~52 entries vs ~30); archive older lessons to `docs/orchestrator-context-archive.md` (already present); preserve in-flight + recent-lesson framing.
   - **(c) V2.1 §VII.F amendment batch processing** — ~17 cumulative amendments pending across Phase 9/10/12 + post-Phase-12 brainstorm + writing-plans (per Phase 13 scope-brainstorm §3 OQ-6 disposition). Process the batch atomically; commit amended spec/plan/brief documents through V2.1 §VII.F correction-protocol routing.
   - **(d) Phase 8 walkthrough failing-test triage + fix** — 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` unchanged since Phase 8 ship (`test_phase8_pipeline_emits_snapshots_for_open_trades_only` + `test_phase8_pipeline_second_same_day_run_upserts` + `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id`). Operator-requested review + correction (post-Sub-bundle-1.5 2026-05-17). Root cause investigation first (was banked at Phase 8 ship without immediate fix); decide whether to fix the tests (test-side drift) OR fix the production behavior (real regression) OR mark `xfail` with documented rationale.
   - **(e) Ruff 18 E501 cleanup** — long-line warnings accumulated across Phase 11/12 + post-Phase-12 ship; banked since polish-bundle-2026-05-10 N818 sweep. Manual review + targeted wraps (favor variable extraction over noqa) to bring baseline back toward zero. Operator-requested cleanup (post-Sub-bundle-1.5 2026-05-17).

   **Estimated 1-2 dispatches** (docs+test+style; mostly docs/test hygiene; ZERO production-architecture surface). (d) may need 1 Codex round if root-cause investigation surfaces real production-behavior drift; (a)+(b)+(c)+(e) are zero-Codex.

**Sequencing rationale (orchestrator-recommended):**
- **1 first** because it's the direct architectural successor to V2 mapper widening; closes the OQ-F V2 LOCK that Sub-bundle 1 explicitly defers; Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers are the load-bearing primitives auto-redirect consumes. Highest operator-fit value.
- **2 second** because it's smaller scope + consumes already-shipped C.C/C.D surfaces; standalone web-counterpart work.
- **3 third** because (a)+(b)+(c)+(e) are docs/style-only (cheap; opportunistically schedulable; prevents cap-drift compounding) AND (d) phase8 walkthrough triage is operator-paced investigation (cheap if test-side drift; bounded Codex round if real production-behavior drift surfaces).

**Rescope note (2026-05-17):** Original Phase 12.5 #2 (Fill auto-population at trade-entry time) MOVED to Phase 13 Theme 3 (Auto-fill deepening across entries + exits + reviews) per operator decision. The broader Phase 13 auto-fill scope (entries + exits + reviews + period reviews) would have required Phase 12.5 #2 to be refactored once Phase 13 lands; folding it into Phase 13 from the start avoids that refactor cost.

**Pre-flight check before Phase 12.5 dispatch:**
- Post-Phase-12 mapper-widening arc (Sub-bundle 1 + 2) MUST be SHIPPED + integration-merged. Phase 12.5 #1 (OQ-F auto-redirect) consumes Sub-bundle 1's `_compute_execution_price` + `_resolve_match_quantity` helpers; cannot dispatch before.
- Operator confirms Phase 12.5 scope is still LIVE at dispatch time (~weeks-to-months out depending on Phase 13 sequencing decisions); may want to adjust per learnings from Sub-bundle 1+2 gates.
- V2.1 §VII.F amendment batch processing may benefit from being folded into Phase 12.5 #4 maintenance pass — operator decision.

**Cross-references:**
- Spec §6.6 OQ-F V2 LOCK: `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md`
- Sub-bundle C plan §I.3 (web Tier-2 V2): `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`
- Phase 12 Sub-bundle C brainstorm §1.6 (fill auto-population at entry): `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`
- Writing-plans §Z V2 candidates: `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §Z

---

## 2026-05-17 Phase 13 scope-brainstorm DOC IN PROGRESS — formal scope development while Sub-bundle 1 implementer is in execution

See `docs/phase13-scope-brainstorm.md` for the surveying-categories + candidate-options + discriminating-questions doc. Operator-paced. Phase 13 candidate triage is the strategic conversation post-Phase-12 mapper-widening arc + Phase 12.5 closure.

---

## 2026-05-17 Phase 12 Sub-sub-bundle C.D SHIPPED — Tier-2 CLI + reconcile-backfill + Phase 10 banner widening (CLOSES Sub-bundle C; 4 Codex rounds + 3 orchestrator-inline gate-fixes + 7 production-discrepancy dispositions; 10-surface operator-witnessed gate THE BIG ONE — largest in project history; ZERO ACCEPT-WITH-RATIONALE banked; ~33 commits; CRITICAL ARCHITECTURAL FINDING: Pass-1 tier-1 entry_price_mismatch shares limit-vs-fill defect with Pass-2-tier-1-FORBIDDEN — V2 mapper widening priority bumped)

**Sub-sub-bundle C.D SHIPPED 2026-05-17** at `bd1a62b` (integration merge of `phase12-bundle-C-D-tier2-cli-and-backfill` via `--no-ff`). Branch HEAD `32812f7` (~33 commits = 15 task-impl (T-D.1..T-D.14 + T-D.6.1) + 1 pre-Codex review fix + 10 Codex-driven fixes (4 R1 + 4 R2 + 1 R3 + 1 R4) + 3 ORCHESTRATOR-INLINE GATE-FIXES + 1 return-report). Operator-dispatched implementer per orchestrator brief at `047e3db`.

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/3M/2m → R2 0C/3M/1m → R3 0C/0M/1m → R4 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 14 findings resolved with code-content fixes (ties cleanest sub-sub-bundle in Phase 12 arc); ZERO Co-Authored-By footer drift across all ~33 commits (C.B forward-binding lesson #7 carry-forward worked for 2nd time); pre-Codex orchestrator-side review absorbed 1 Major + 1 Minor (NEW C.C lesson #6 validated for 2nd time).

**+156 fast tests** (4204 → 4360 worktree-side; ~4363 main HEAD post-merge); ruff 18 unchanged; schema v19 unchanged consumer-side.

### 10-surface operator-witnessed gate ALL PASS (orchestrator-driven 2026-05-17 — THE BIG ONE)

S1 fast suite ✅ 4360 pass; S2 dry-run ✅ classification matrix showed 7 unresolved-material (4 more than handoff brief expected — Run #11 emerged between C.B+C.C merges + included NEW LION not in handoff); S3a CVGI tier-1 + S3b LION tier-1 ⚠️ APPLIED-THEN-OVERRIDE per critical operator pushback (limit-vs-fill defect surfaced — see architectural finding below); RECOVERY A1+A2+B2 via `override-correction` restored fills.price to operator's TOS Net Price values; S4a/S4b DHC+VSAT tier-2 stamps ✅; S5 show-ambiguity 39 ✅ (post-gate-fix-#3 § glyph restored); S6a synthetic-fixture acceptance ✅ 18/18 PASS in 5.64s; S6b operator-real DHC 39 `mark_unmatched` + S6b.dup DHC 42 `acknowledge`; S7 VSAT 40+43 `acknowledge`; S8 Phase 10 banner clears to ZERO ✅ via `swing web --port 8081` curl-grep; S9 ruff 18 ✅; S10 cycle-checklist + 6 CLAUDE.md gotcha additions verified ✅.

### 3 ORCHESTRATOR-INLINE GATE-FIXES (committed on worktree branch + merged)

1. **Gate-fix #1 `a542f65`**: swap U+2192 `→` to ASCII `->` in `_format_pass_2_line` at `swing/trades/reconciliation_backfill.py:512` — Windows PowerShell stdout cp1252 crash during S2 dry-run.
2. **Gate-fix #2 `34d74f7`**: `_handle_no_mutation_audit` handles synthetic `field_name='fill_match'` for `unmatched_open_fill`/`unmatched_close_fill` discrepancies — `_DiscrepancyInfo` extended with `expected_value_json`; helper branches on `discrepancy_type` to skip column read.
3. **Gate-fix #3 `32812f7`**: force UTF-8 on `sys.stdout`/`sys.stderr` at `swing/cli.py` entry — defense-in-depth covering all non-ASCII glyphs.

### 7 production-discrepancy dispositions (post-gate: banner count=0)

- **41 CVGI** + **44 CVGI** → `operator_overridden` chain heads correction_ids 3+4 (S3a wrong tier-1 → A1+A2 override-back to $5.23 per operator's TOS Net Price $5.2244)
- **45 LION** → `operator_overridden` chain head correction_id 6 (B1 wrong tier-1 → B2 override-back to $12.70 per operator's TOS Net Price $12.6999)
- **39 DHC** → `mark_unmatched` correction_id 7
- **42 DHC**, **40 VSAT**, **43 VSAT** → `acknowledge` correction_ids 8+9+10 (pre-Phase-11 entries; Schwab order-history incomplete; journal canonical per operator's TOS context)

Production fills.price restored: CVGI fill 9 = $5.23; LION fill 15 = $12.70.

### CRITICAL architectural finding: Pass-1 tier-1 entry_price_mismatch limit-vs-fill defect

V1 Schwab mapper at `swing/integrations/schwab/mappers.py:223-230` reads `order.price` (LIMIT or STOP TRIGGER) — NOT `orderActivityCollection[].executionLegs[].price` (EXECUTION). Reconciliation comparator at `swing/trades/schwab_reconciliation.py:693` compares `so.price` (limit) vs journal `f.price` (execution); when limit ≠ execution (typical for slippage / VWAP / partial fills), emits false `entry_price_mismatch`. Both CVGI ($5.30 limit vs $5.2244 fill) + LION ($12.75 limit vs $12.6999 fill) empirically falsified the operator-locked Pass-1 "order/limit ≈ execution" assumption. **CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha AMENDED at integration housekeeping to cover Pass-1 family.** `close_price_mismatch` has same defect (same code path). `stop_mismatch` is architecturally sound (trigger-vs-trigger comparison).

### V2 mapper widening: priority BUMPED (operator-locked next-architectural-dispatch slot)

Per OQ-4 + plan §I.1: widen mapper to expose `orderActivityCollection[].executionLegs[].price` for execution-grain comparison. Already operator-locked as next dispatch; today's gate evidence demonstrates the assumption breaks operationally + bumps priority. Pre-V2 operator workflow: `reconcile-backfill --apply` then manual TOS-audit + tier-3 `override-correction` on any wrong tier-1 corrections. **Brainstorm dispatch needed.**

### 2 NEW CLAUDE.md gotcha promotions

1. **Windows PowerShell stdout cp1252 family** — non-ASCII glyphs (`§`/`→`/etc.) in CLI output paths crash on Windows; canonical fix is ASCII swap + defense-in-depth UTF-8 stdout reconfigure.
2. **Synthetic-fixture-vs-production-emitter shape drift** — test fixtures planting real column names pass; production emitter using synthetic field labels (e.g., `field_name='fill_match'`) breaks; pre-empt via discriminating tests using production-shape values.

### Sub-bundle C arc closer aggregate (4 sub-sub-bundles SHIPPED 2026-05-15 → 2026-05-17)

- **Cumulative commits**: ~88 (A=16 + B=26 + C=23 + D=33 - merge overhead)
- **Cumulative Codex rounds**: 14 (A=2 + B=5 + C=3 + D=4)
- **Cumulative fast tests**: +494 (104 + 139 + 95 + 156)
- **Cumulative ACCEPT-WITH-RATIONALE**: 1 (C.A backup-gate; ZERO in B+C+D)
- **Cumulative Co-Authored-By footer drift**: 0 (C.B caught + rebase-stripped pre-merge; C.C + C.D held the line via explicit dispatch-prompt citation)
- **Schema v18 → v19** at C.A T-A.1 atomic single-file landing; consumer-side only through B+C+D
- **CLAUDE.md gotchas promoted**: ~8 across arc (3 C.A + 1 C.B + 4 C.C + 3 C.D)
- **V2.1 §VII.F amendments pending**: ~17 across arc (5 C.A + 6 C.B + 6 C.C + ~5 C.D)
- **V2 candidates banked**: ~25 across arc; **headline V2 = mapper widening** (operator-locked next architectural dispatch; priority BUMPED per today's gate evidence)

### Worktree teardown status

Branch `phase12-bundle-C-D-tier2-cli-and-backfill` pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`. On-disk husk at `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/` ACL-locked; cleanup-script regex matches cleanly. **4 phase12-bundle-c-* husks total pending** (A+B+C+D).

---

## 2026-05-16 Phase 12 Sub-sub-bundle C.C SHIPPED — Auto-correction service + reconciliation flow pivot (4 public service fns + 17+1 handlers + savepoint-per-discrepancy pivot at BOTH Schwab + TOS reconciliation; 3 Codex rounds NO_NEW_CRITICAL_MAJOR — ties C.A for fastest Phase 12 chain; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; 23 commits; THIRD Phase 12 Sub-bundle C sub-sub-bundle; Sub-bundle C 75% shipped)

**Sub-sub-bundle C.C SHIPPED 2026-05-16** at `0b9d253` (integration merge of `phase12-bundle-C-C-auto-correction-service-and-flow-pivot` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `97fc8b9` (23 commits = 12 task-impl T-C.1..T-C.11 + T-C.3.1 + 1 UP035/UP017/I001/F401/SIM118/B905/N802 ruff baseline-restore + 3 pre-Codex review fixes (SC-1 sandbox-threading + SC-2 T-C.11 E2E scope + SC-1 follow-up sandbox-precedence) + 4 Codex-R1-fix + 1 Codex-R2-fix + 1 Codex-R3-polish + 1 return-report on top of dispatch brief `5ed3e74`). Operator-dispatched implementer per orchestrator brief at `5ed3e74`.

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/0m → R2 0C/1M/0m → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 R1 Major + 1 R2 Major + 1 R3 Minor resolved with code-content fixes. **Ties Phase 12 Sub-sub-bundle C.A's 2-round chain for FASTEST Phase 12 chain** (C.A=2, C.B=5, C.C=3; Sub-bundle C-arc average so far = 3.3 rounds). **ZERO Co-Authored-By footer drift** entire 23-commit chain — C.B forward-binding lesson #7 carry-forward worked. The dispatch prompt's explicit citation of CLAUDE.md "No Claude co-author footer" convention with reference to the C.B R1 fix-bundle recurrence-prevention pattern prevented the drift. **Pre-Codex orchestrator-side review absorbed 2 Major findings** (SC-1 sandbox threading + SC-2 T-C.11 E2E scope) saving an estimated 1-2 Codex rounds (NEW lesson #6 banked at return report §10).

### Operator-witnessed gate (2026-05-16 post-merge-prep; orchestrator-driven; 4 surfaces ALL PASS)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 4200 fast pass on C.C branch (88.70s wall-clock) + 3 pre-existing phase8 walkthrough failures unchanged + 5 skipped (the 2 C.A cross-bundle pin tests un-skipped at C.B T-B.14 still PASS post-rebase) |
| S2 production-env walkthrough | ✅ | Explicit `python -c` harness invoked `apply_tier1_correction(env='production')` against CVGI 41 fixture seeded via test helper `_seed_cvgi_world`; BEFORE state `fills.price=$5.23` + `discrepancy.resolution='unresolved'` + 0 correction rows + 0 trade_events → CALL returned `correction_id=1`/`action='auto_applied'`/`affected_table='fills'`/`field='price'` → AFTER state `fills.price=$5.30` + `discrepancy.resolution='auto_corrected_from_schwab'`/`resolved_by='auto'` + 1 correction row + 1 `trade_events.event_type='reconciliation_auto_correct'` row; full spec §10.1 end-to-end mutation verified |
| S3 sandbox-env walkthrough | ✅ | Same harness invoked `apply_tier1_correction(env='sandbox')` against fresh CVGI fixture; CALL returned `correction_id=None` + `notes='sandbox: domain write short-circuited'` + WARNING log line `_apply_tier1_correction_inner short-circuited under sandbox environment for discrepancy_id=41` emitted per spec §5.9; AFTER state byte-for-byte identical to BEFORE — ZERO journal mutation, ZERO audit rows, discrepancy stays `unresolved` |
| S4 ruff baseline | ✅ | 18 E501 unchanged |

### Code deltas (no schema; pure service + flow-pivot + briefing extension per dispatch brief §0.5 #1 LOCK)

1. **NEW MODULE `swing/trades/reconciliation_auto_correct.py`** — 4 public service functions (`apply_tier1_correction` + `apply_tier2_resolution` + `apply_tier3_override` + `stamp_pending_ambiguity`) + 4 caller-tx inner variants + 3 exception classes (`CallerHeldTransactionError` / `ValidatorRejectedError` / `AlreadySupersededError`) + `CorrectionResult` dataclass + 17+1 per-(`ambiguity_kind`, `choice_code`) handler registry with `_PICK_SCHWAB_RECORD_PREFIX` parametric entry + savepoint-per-discrepancy pivot helper `_pivot_classify_and_dispatch_for_run` shared across Schwab+TOS via lazy import. Per spec §5 + §7 + §10 LOCKs preserved verbatim.
2. **MODIFIED `swing/trades/schwab_reconciliation.py`** — flow pivot at `run_schwab_reconciliation` Step 2 classify+dispatch loop with savepoint-per-discrepancy discipline (spec §7.1 LOCK; fresh-savepoint fallback for tier-2 stamp on validator-rejection path per writing-plans R2 Minor #1 LOCK) + `summary_json` counters (`tier1_applied_count` / `tier2_pending_count` / `tier3_overridden_count` ZERO at run-time) + post-pivot `unresolved_discrepancies_count` recompute (R1 M#3 fix).
3. **MODIFIED `swing/trades/reconciliation.py`** — TOS flow pivot mirror at `run_tos_reconciliation` per OQ-2 PIVOT BOTH; consumes shared pivot helper via lazy import (NEW lesson #5 banked).
4. **MODIFIED `swing/rendering/briefing.py`** + **`swing/rendering/briefing_md.py`** — `BriefingInputs` extended with `reconciliation_pending_count` + `reconciliation_tier1_recent_count` fields; "Reconciliation status" section emits when counters non-zero per spec §7.5.
5. **MODIFIED `swing/pipeline/runner.py:_step_export`** — wires counters via inline SQL.
6. **MODIFIED `swing/data/repos/reconciliation.py` (RESOLUTION_TYPES Python constant)** — widened 5→9 values mirroring `_RESOLUTION_VALUES` per R1 M#4 (schema-CHECK + Python-constant + dataclass-validator paired discipline gotcha applied to a SECOND Python-side mirror; the manual `resolve_discrepancy` CLI surface accepted the new service-owned states which it should NOT) + tightened `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist per R2 M#1 (4 service-owned states route through canonical service entries NOT manual `resolve_discrepancy`; NEW lesson #1 banked).
7. **12 NEW TEST FILES** under `tests/trades/` + `tests/rendering/` + `tests/pipeline/` + `tests/integration/` covering transactional discipline, atomic flows for all 3 tiers, savepoint regression suite, flow pivot at both reconciliation entry points, briefing extension, _step_export wire, and T-C.11 slow E2E `test_phase12_bundle_c_cvgi_41_end_to_end` (mirrors Phase 11 D R1 M#4 ACCEPT-WITH-RATIONALE precedent at scope; tests service-composition + `_step_export` invocation per pre-Codex SC-2 widening).

### NEW V2.1 §VII.F amendment candidates banked (6 items per return report §5)

1. **D1 pivot helper relocation candidate** — `_pivot_classify_and_dispatch_for_run` currently lives in `reconciliation_auto_correct.py` but is consumed by both `schwab_reconciliation.py` + `reconciliation.py` via lazy import; V2 candidate to relocate to neutral module (NEW lesson #5 watch item).
2. **D2 sentinel rule wording** — spec §3.1.1 `__delete__`/`__insert__` sentinel handling could be clarified at writing-plans level (multi-fill split-into-partials handler is the only V1 consumer).
3. **D3 test-side adjustments dependency on C.D filter widening** — Phase 9 Sub-bundle B unresolved-material list filter currently keys on `resolution='unresolved'` only; C.D banner predicate widening to include `pending_ambiguity_resolution` cascades to filter widening too (transitive helper effect; documented for C.D dispatch).
4. **D4 SAVEPOINT-uniqueness test mechanic** — current uniqueness assertion relies on PK autoincrement; V2 candidate for explicit unique-name discriminating test.
5. **D5 inline SQL vs repo helpers** — `_step_export` uses inline SQL for the new counters rather than introducing repo helpers; V2 candidate to formalize as `count_discrepancies_pending_ambiguity` / `count_corrections_tier1_recent` repo functions.
6. **D6 T-C.11 scope** + **D7 view_models.py touch** — both are scope-boundary clarifications for the cross-bundle interaction with Phase 10 (deferred until C.D Phase 10 banner widening lands).

### Three highest-leverage SHIPPED deliverables

1. **Auto-correction service layer as the canonical INSERT-time enforcement boundary.** Lifecycle invariants on `reconciliation_corrections` rows (`correction_action='auto_applied'` implies `applied_by='auto'`; tier-3 override requires non-null `operator_truth_value_json`; tier-1 cannot land with non-NULL `ambiguity_kind`) enforced at C.C `apply_*_inner` INSERT time per spec §5.4 + C.B forward-binding lesson #1. SELECT-first idempotency precedes payload validation per R1 M#2 (NEW lesson #3 banked). Outer transaction discipline UNIFORM regardless of sandbox per R1 M#1 (NEW lesson #2 banked) — outer ALWAYS `BEGIN IMMEDIATE`; inner short-circuits sandbox cases internally.
2. **Savepoint-per-discrepancy pivot enables graceful degradation under per-discrepancy classifier/apply failures.** Spec §7.1 LOCK preserved verbatim: `SAVEPOINT correction_sp_<discrepancy_id>` per iteration; RELEASE on success; ROLLBACK TO + RELEASE on failure; validator-rejection fallback uses FRESH `correction_fallback_sp_<discrepancy_id>` (writing-plans R2 Minor #1 fix). Outer reconciliation_run transaction survives per-discrepancy failures with WARNING-logged failures captured in `summary_json.tier_errored` counter. T-C.7 savepoint discipline regression suite locks the invariant.
3. **Production reconciliation flow pivot landed at BOTH Schwab + TOS entry points per OQ-2 PIVOT BOTH.** `_pivot_classify_and_dispatch_for_run` extracted as shared helper (NEW lesson #5 DRY discipline) via lazy import to break circular dependencies. Briefing.md "Reconciliation status" section + counter wires in `_step_export` mean every future pipeline run emits operator-visible state about pending tier-2 ambiguities + recent tier-1 auto-corrects. **3 unresolved material discrepancies (39 DHC + 40 VSAT + 41 CVGI) LEFT UNRESOLVED BY DESIGN** pending C.D backfill operation — production reconciliation flow will dispatch tier-1/tier-2 inline on next run, but existing discrepancies (`resolution='unresolved'`) aren't re-classified by the flow pivot which only acts on freshly-emitted rows.

### Forward-binding lessons for C.D dispatch (per return report §10)

1. **Schema-coverage constant ≠ manual-resolver allowlist.** When widening a Python enum to mirror schema CHECK, audit every existing manual callsite that validates against the constant. Service-owned values (requiring routing through specific service entries) MUST have a separate tighter allowlist for the manual path. Discriminating test: per-service-owned-value rejection with routing hint substring in error message.
2. **Outer transaction discipline UNIFORM regardless of sandbox.** Sandbox short-circuit MUST live in the inner (caller-tx) function, NOT the outer (own-tx) function. Outer ALWAYS issues `BEGIN IMMEDIATE` → call inner → `COMMIT` (or ROLLBACK). Inner short-circuits internally. Prevents (a) outer-skip bypassing caller-held-tx check + (b) nonexistent discrepancy_id succeeding as silent no-op.
3. **SELECT-first idempotency must precede payload validation.** Reorder: (1) sandbox short-circuit, (2) SELECT + None-check, (3) terminal-state idempotent return, (4) payload validation, (5) atomic flow. Terminal discrepancy returns existing `correction_id` even with stale/malformed/None payload.
4. **Counter staleness after inline state mutation requires post-loop recompute.** When a flow emits rows incrementing counters THEN mutates those rows' states, the run-summary counter MUST be recomputed via `SELECT COUNT(*)` post-loop. Inline mutation invalidates emit-time counters.
5. **DRY helper extraction across pivot mirror sites with lazy import.** When plan says "mirrors T-X verbatim" + mirror is non-trivial (100+ lines), extract a private helper; lazy-import to break circular dependencies. Watch item: asymmetric import direction = V2 candidate to relocate to neutral module.
6. **Pre-Codex orchestrator-side review catches LOCK divergences cheaply.** Orchestrator-side spec-compliance + code-quality review BEFORE invoking adversarial-critic saves an estimated 1-2 Codex rounds. Pattern: dispatch a focused reviewer subagent with the plan acceptance criteria + brief BINDING contracts as anchors, ask for a deviation list ≤600 words.
7. **Implementer self-report accuracy gate.** Implementer self-report MUST cite specific file:line evidence for each fix claim; orchestrator-side review MUST verify the cited lines actually match the claim (regression tests pinning wrong behavior can pass while violating the LOCK).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) ~4-5 days remaining (expires 2026-05-22). C.D dispatch likely consumes 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md` (`5ed3e74`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans) §D C.C section (lines 1604-2569).
- Return report: `docs/phase12-bundle-C-C-return-report.md` (`97fc8b9`).
- Integration merge: `0b9d253`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner predicate widening — CLOSES Sub-bundle C) UNBLOCKED.** Per plan §E decomposition: 16 tasks (T-D.1..T-D.14 + T-D.6.1 + T-D.11); +55-80 fast tests projected; 4-6 Codex rounds expected; **10-surface operator-witnessed gate per plan §G.4** including S6 synthetic-fixture-only acceptance test for `--custom-value` payload contract per brainstorm lesson "synthetic-fixture-only acceptance test for production-write-contract surfaces" + S6b operator-real-disposition of DHC 39 (per spec §15.5 LOCKED revised mechanic). Will consume `apply_tier2_resolution` + `apply_tier3_override` + `stamp_pending_ambiguity` from C.C + `classify_discrepancy` + `default_validator_chain` from C.B + `insert_correction` from C.A. **Production backfill of 39 DHC + 40 VSAT + 41 CVGI** via `swing journal reconcile-backfill --apply` is the operator-witnessed gate centerpiece at S3+S4+S6+S7 — CVGI 41 → auto-correct tier-1; DHC 39 + VSAT 40 → pending_ambiguity_resolution; operator dispositions per real data. **Phase 10 dashboard banner predicate widening** to include `pending_ambiguity_resolution` alongside `unresolved` retrofits 10 base-layout VMs (per spec §A.5; 14 VM-instance regression tests for defense-in-depth). **Recommended timing: dispatched post-handoff-or-when-operator-commissions** per operator-paced cadence.

---

## 2026-05-15 Phase 12 Sub-sub-bundle C.B SHIPPED — Classifier + validator-shim modules (pure logic; ZERO journal mutations; 5 Codex rounds NO_NEW_CRITICAL_MAJOR; 26 commits; ZERO ACCEPT-WITH-RATIONALE — cleanest finding-disposition in Phase 12 arc; SECOND Phase 12 Sub-bundle C sub-sub-bundle)

**Sub-sub-bundle C.B SHIPPED 2026-05-15** at `aacd1cd` (integration merge of `phase12-bundle-C-B-classifier-and-validator-shim` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `c48188a` post orchestrator-side rebase (26 commits = 14 task-impl + 1 UP035 ruff style + 4 Codex-R1-fix + 2 Codex-R2-fix + 1 R2-N806-style + 2 Codex-R3-fix + 1 Codex-R4-fix + 1 return-report on top of dispatch brief `fdb4276`). Operator-dispatched implementer per orchestrator brief at `fdb4276`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/3M/0m → R2 0C/1M/1m → R3 0C/1M/1m → R4 0C/1M/0m → R5 0C/0M/0m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 1 Critical + 6 Major + 2 Minor resolved with code-content fixes. **Cleanest finding-disposition record in Phase 12 arc to date** (C.A had 1 ACCEPT-WITH-RATIONALE; Sub-bundle B had 0 but with 7 Major; C.B closes 1 Critical + 6 Major + 2 Minor with zero deferrals). R1 C#1 + R2 M#1 + R3 M#1 + R4 M#1 form a single **determinism-principle-tightening sequence on `entry_price_mismatch`** Shape B predicate — each round tightened further; R5 converged.

### Orchestrator-side rebase (Co-Authored-By footer strip; operator-decision 2026-05-15)

R1 fix-bundle 4 commits accidentally carried `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer (CLAUDE.md says "No Claude co-author footer"). Implementer surfaced as deviation #3 in return report §5 with two options: rebase-strip pre-merge OR accept-drift into history. Operator elected **rebase-strip via AskUserQuestion 2026-05-15**. Orchestrator performed `git rebase -i fdb4276` with `GIT_SEQUENCE_EDITOR` marking the 4 commits as `reword` + `GIT_EDITOR` Python one-liner stripping the footer line + rstripping trailing whitespace. SHAs shifted (`6e4bd30→a14401c` / `fcff4d3→63909f5` / `180838e→1cd5951` / `78d98b2→69a2cc8`); 26-commit count preserved; content unchanged; ZERO footer matches on `fdb4276..HEAD` post-rebase confirmed via grep. CLAUDE.md `No Claude co-author footer` convention preserved on integrated history. **Forward-binding lesson #7 banked**: future dispatch prompts MUST explicitly suppress the footer in subagent context (passive inheritance from CLAUDE.md is insufficient because subagents have isolated context).

### Code deltas (no schema; pure logic per dispatch brief §0.5 #1 LOCK)

1. **NEW MODULE `swing/trades/reconciliation_classifier.py`** — 10 per-discrepancy-type sub-classifiers + dispatch table + `ClassificationResult` `@dataclass(frozen=True)` + public `classify_discrepancy(...)` entry with validator-respecting-downgrade dispatcher + 4 shared `_candidate_choices_*` helpers. Per spec §4 + §6.2.1 + §8.4 LOCKS preserved verbatim.
2. **NEW MODULE `swing/trades/reconciliation_validators.py`** — 4 dry-run validators `validate_fill_correction` + `validate_trade_correction` + `validate_cash_movement_correction` + `validate_snapshot_correction` with `math.isfinite()` guard on all 5 numeric fields (mirrors `swing/data/models.py` REAL-field discipline) + `default_validator_chain(conn)` dispatcher composing on `affected_table` partial-application. Per spec §5.5 LOCKS preserved verbatim. SELECT-only against the conn passed in; NEVER mutates the DB.
3. **12 NEW TEST FILES** under `tests/trades/` — one per sub-classifier + one for shim validators + one for default chain + public-entry tests + cross-bundle pin strengthening.
4. **2 cross-bundle pin tests un-skipped at T-B.14** at `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` — both strengthened at R1 M#3 (`78d98b2`→`69a2cc8` post-rebase) to discriminatingly pin classifier + validator-chain behavior end-to-end via tmp_path schema-v19 fixture.

### Operator-witnessed gate (2026-05-15 post-merge-prep; orchestrator-driven; 3 surfaces ALL PASS)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 4110 fast pass on rebased C.B branch + 3 pre-existing phase8 walkthrough failures (unchanged from main baseline) + 5 skipped (the 2 C.A cross-bundle pin tests un-skipped at T-B.14 now PASS; 4 Schwab-fixture-not-present skips + 1 Task 7.3 flag-classifier remain) |
| S2 classifier walkthrough | ✅ | Explicit `python -c` walkthrough invoked `classify_discrepancy` against CVGI 41 + DHC 39 + VSAT 40 fixtures per spec §10; ASSERTED expected `ClassificationResult` shapes — CVGI tier=1 `correction_target={'price': 5.30}` with reason matching spec §10.1 verbatim; DHC + VSAT both tier=2 `ambiguity_kind='unsupported'` with `_pass_2_required=True` signal in `correction_reason` matching spec §10.2/10.3 Pass-1 OUTPUT; determinism principle spot-check (CVGI fixture × 100 invocations) byte-for-byte identical via frozen dataclass equality |
| S3 ruff baseline | ✅ | 18 E501 unchanged |

### NEW V2.1 §VII.F amendment candidates banked (6 items per return report §6)

1. **Spec §4.3.1 entry_price_mismatch source_payload shape** — enumerate Shape A persisted-JSON-only `{'price'}` OR Shape B full match-tuple (ticker+date+quantity) explicitly.
2. **Spec §4.3.1 contradictory date evidence** — neither source-side nor journal-side internal date/fill_datetime divergence is addressed; C.B rejects both as tier-2 unsupported per determinism §4.4.
3. **Plan §C.3** — pin `:.2f` rendering format for currency in `correction_reason` strings.
4. **Plan §C.9** — enumerate canonical 4-field comparison vector (`'date'`, `'kind'`, `'amount'`, `'ref'`) for `cash_movement_mismatch` tier-1 multi-field correction.
5. **Spec §5.5** — document `functools.partial` composition requirement between `default_validator_chain` + `classify_discrepancy` explicitly.
6. **Spec §6.2.1** — already locks `pick_schwab_record_<N>` `requires_custom_value=True` per Codex R7 M#2; banked only for cross-reference completeness.

### Three highest-leverage SHIPPED deliverables

1. **Classifier + validator-shim modules as pure-logic foundation for the entire auto-correct reconciliation architecture.** ZERO journal mutations + ZERO Schwab API calls + ZERO transaction management. Sub-sub-bundle C.C will consume `classify_discrepancy` + `default_validator_chain` to build the auto-correction service; Sub-sub-bundle C.D will consume them at backfill time. Spec §4 + §5.5 LOCKS preserved verbatim.
2. **Determinism principle enforcement (spec §4.4) discriminatingly tested.** `entry_price_mismatch` Shape A/B predicate LOCKED through 4-round Codex tightening sequence — partial-tuple OR contradictory-date-evidence (source-side OR journal-side internal inconsistency) → tier-2 `unsupported`. CVGI 100×-invocation determinism test pins reproducibility. Pass-2-tier-1-FORBIDDEN LOCK at T-B.4/T-B.5 parametrized over 6 distinct input shapes; classifier NEVER emits tier-1 from V1 order-grain mapper data.
3. **Cross-bundle pin discipline operational** — both T-A.7 pins un-skipped at T-B.14 + strengthened to discriminatingly pin end-to-end behavior via tmp_path schema-v19 fixture. Demonstrates the project-wide "pin test ships SKIPPED at producer task; un-skips at consumer task landing" discipline working as designed for the C.A→C.B handoff.

### Forward-binding lessons for C.C dispatch (per return report §11)

1. Classifier output is C.B → service-layer enforcement is C.C boundary (lifecycle invariants enforced at `apply_tier1_correction` INSERT time, NOT classifier-output time).
2. Validator chain MUST be re-invoked at C.C apply time (defense-in-depth per spec §4.6 + §5.5 BINDING — schema state may shift between classifier run + apply call).
3. `functools.partial` composition between `default_validator_chain` + `classify_discrepancy` is non-obvious (chain's `(correction_target, *, affected_table, affected_row_id)` signature must be partial-applied to match dispatcher's `validator_chain(correction_target)` single-arg invocation). Pre-empt in C.C dispatch brief.
4. `_pass_2_required=True` is a free-form-string convention in `correction_reason` (NOT a typed field on `ClassificationResult`). C.D backfill reads via substring match. Document exact substring in C.D dispatch brief.
5. Shape predicate tightening discipline (R1 C#1 → R2 M#1 → R3 M#1 → R4 M#1 sequence) — C.C handlers that classify operator-supplied `--custom-value` payloads will face the same scrutiny; implement input-shape checks EXPLICITLY at handler entry; reject unrecognized key sets; reject contradictory evidence within the payload.
6. Same-source-keys-on-source-and-journal evidence convergence pattern — when both `source_payload` AND `journal_row` carry an information field in MULTIPLE forms (e.g., `date` + `fill_datetime`), determinism principle requires each side's internal forms must agree AND both sides must agree with each other.
7. Co-Authored-By footer drift requires EXPLICIT suppression in dispatch prompts (CLAUDE.md passive inheritance is insufficient because subagents have isolated context).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) ~5 days remaining (expires 2026-05-22T17:05:00+00:00). C.C dispatch likely consumes 3-5 days; C.D 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-B-classifier-and-validator-shim-executing-plans-dispatch-brief.md` (`fdb4276`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans) §C C.B section (lines 1068-1601).
- Return report: `docs/phase12-bundle-C-B-return-report.md` (`c48188a` post-rebase).
- Integration merge: `aacd1cd`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.C (Auto-correction service + reconciliation flow pivot) UNBLOCKED.** Per plan §D decomposition: 12 tasks (T-C.1..T-C.11 + T-C.3.1); +65-115 fast tests projected; 4-6 Codex rounds expected. Will consume `classify_discrepancy` + `default_validator_chain` from C.B + `insert_correction` from C.A schema. Transactional discipline (reject caller-held tx; BEGIN IMMEDIATE / COMMIT / ROLLBACK); validator chain re-invocation at apply time; surface-aware audit attribution; flow pivot at `run_schwab_reconciliation` AND `run_tos_reconciliation` callsites. **Recommended timing: dispatched post-handoff-or-when-operator-commissions** per operator-paced cadence.

---

## 2026-05-15 Phase 12 Sub-sub-bundle C.A SHIPPED — Foundation (schema v18→v19 atomic migration + minimal repos for auto-correct reconciliation; 2 Codex rounds NO_NEW_CRITICAL_MAJOR; 16 commits; FIRST Phase 12 Sub-bundle C sub-sub-bundle)

**Sub-sub-bundle C.A SHIPPED 2026-05-15** at `354b6c0` (integration merge of `phase12-bundle-C-A-foundation` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `56e6993` (16 commits = 9 task-impl (T-A.1..T-A.8 + T-A.7 cross-bundle pin) + 4 Codex-fix (R1 + R2) + 2 docs + 1 return-report on top of dispatch brief `3cb334d`). Operator-dispatched implementer per orchestrator brief at `3cb334d`.

**2 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/2m → R2 0C/0M/2m); **ZERO Critical findings** entire chain; **1 ACCEPT-WITH-RATIONALE banked** (R1 Major #1 — backup-gate narrowness; matches Phase 9 Sub-bundle A precedent; documenting test + extended docstring). **Ties Phase 12 Sub-bundle A precedent for fastest Phase 12 chain.**

### Schema deltas (atomic v18→v19 migration at `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql`)

1. **NEW TABLE `reconciliation_corrections`** (20 columns; audit-history forensic trail). Preserves pre-correction journal value + Schwab-said value + applied correction + operator-truth value (if any) + lifecycle metadata + per-row policy stamp `risk_policy_id_at_correction` nullable + `ON DELETE SET NULL` per Phase 9 §3.1.1 trades.risk_policy_id_at_lock precedent. Self-reference chain via `superseded_by_correction_id` for override-of-override edge case.
2. **NEW COLUMN `reconciliation_discrepancies.ambiguity_kind`** (TEXT NULL CHECK enum) + cross-column CHECK with `resolution` enforcing tier-1 (NULL kind + auto_corrected_from_schwab resolution) vs tier-2 (non-NULL kind + pending_ambiguity_resolution OR operator_resolved_ambiguity) vs tier-3 (NULL kind + operator_overridden) invariants schema-defended.
3. **WIDENING `reconciliation_discrepancies.resolution`** CHECK enum 5 → 9 values via table-rebuild (`+ 'auto_corrected_from_schwab' / 'pending_ambiguity_resolution' / 'operator_resolved_ambiguity' / 'operator_overridden'`; PRAGMA foreign_keys=OFF during rebuild per Phase 7 hotfix `283d4fa` discipline; preserves all 30+ existing rows).
4. **NEW COLUMN `review_log.superseded_by_correction_id`** (INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL). Phase 6 freezing audit per spec §9.1 RETAIN-and-mark-superseded.
5. **WIDENING `trade_events.event_type`** CHECK enum + `'reconciliation_auto_correct'` via table-rebuild.
6. **NEW COLUMN `schwab_api_calls.linked_correction_id`** (INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL). Bidirectional provenance chase with `reconciliation_corrections` per Phase 11 source-artifact reference shape gotcha.

### Operator-witnessed gate (2026-05-15 post-merge-prep; orchestrator-driven; SKIPPED-with-test-coverage per polish-bundle-2026-05-10 precedent)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 3966 fast pass on main HEAD post-merge + 3 pre-existing failures (3 phase8 walkthrough; the 4th sentinel-leak failure at `test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` no longer surfacing post-merge — flaky pre-existing per writing-plans return report §7 #2) + 3 skipped (flag-classifier + C.A cross-bundle pin + 1 other) |
| S2 db-migrate fresh DB | ✅ SKIPPED-with-test-coverage | Inline migration runner tests cover fresh-DB migration end-to-end; no new discovery via standalone CLI run |
| S3 db-migrate production-snapshot | ✅ SKIPPED-with-test-coverage | T-A.8 slow-marked `test_migration_0019_against_production_snapshot.py` already exercised against operator's real v18 DB (full run_migrations flow including backup-gate fire); dynamic snapshot equality preserved all 30+ existing rows |
| S4 ruff baseline | ✅ | 18 E501 unchanged |

### NEW V2.1 §VII.F amendment candidates banked (per return report)

1. **Spec §3.1 column-count header drift (§I.16):** header text says "Column count: 19 columns" but table-row enumeration is 20 (correction_id through notes). Plan T-A.1 LOCKED 20-column count from the table verbatim.
2. **Plan §A.12 Phase 11 backup-gate precedent claim:** writing-plans plan referenced a Phase 11 backup-gate that does NOT exist (Codex R1 Major #1 surfaced); the actual backup-gate precedent is Phase 9 Sub-bundle A. Plan §A.12 wording amendment candidate.
3. **Plan §B.4 SHA256 byte-equality impossibility with SQLite Connection.backup:** plan §B.4 proposed SHA256 byte-equality verification but SQLite's `Connection.backup()` API doesn't preserve bytewise SHA256 (Codex R2 Minor #1 correction at `0e26d2b`).
4. **Dispatch brief §0.5 pre_version <= 18 vs == 18 equality form:** orchestrator brief §0.5 used `pre_version <= 18` but Phase 9 precedent uses `pre_version == (target - 1)` strict equality.
5. **Plan §B.2 _RESOLUTION_VALUES widening fold-into T-A.2:** plan §B.2 proposed widening the Python `_RESOLUTION_VALUES` constant in a separate task; should have folded into T-A.2 dataclass task for atomic consistency.

### Three highest-leverage SHIPPED deliverables

1. **Schema v19 foundation** — 5 schema deltas under one atomic `BEGIN IMMEDIATE; ... COMMIT;` envelope; new audit-history table + 4 column extensions + 2 CHECK enum widenings via table-rebuild; backup-gate fires correctly at `pre_version == 18 AND post_version >= 19` boundary; 30+ existing rows preserved; `EXPECTED_SCHEMA_VERSION = 19` bumped same commit.
2. **Cross-column CHECK schema-defended** — tier-1 / tier-2 / tier-3 invariants between `(ambiguity_kind, resolution)` enforced at schema CHECK time; app-layer enforcement in C.C service-layer is the secondary defense.
3. **ZERO behavioral changes to existing surfaces** — C.A is consumer-side passive. Existing 30+ discrepancies + fills + trades + review_log + schwab_api_calls all preserved unchanged. New schema sits idle until C.B/C.C/C.D consumers ship.

### Forward-binding lessons for C.B dispatch (per return report §11)

1. Schema-CHECK + Python-validator paired work (any new column with CHECK enum at schema time + Python constant + validator in dataclass MUST land in same task for atomic consistency).
2. Cross-column CHECK precedence at schema vs app layer (schema CHECK is defense-in-depth; app-layer enforcement in service-time is primary path).
3. Backup-gate equality form (`pre_version == (target - 1)` strict equality NOT `pre_version <= (target - 1)`).
4. UPDATE-self-reference anchor (`correction_set_id` two-step pattern at T-A.3 + T-C.3.4).
5. 20-column LOCK on `reconciliation_corrections` (spec drift §I.16 documented).
6. Lifecycle invariants as C.C service-layer concern (NOT C.B classifier; classifier produces ClassificationResult; service-layer enforces invariants).
7. Plan-author schema additions escalation (matches NEW orchestrator-context lesson at `657b8a0`; if C.B implementer encounters need for schema element NOT in plan + spec, STOP + escalate; do NOT bank-after-write).

### Production tokens DB clock awareness

Refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00) is currently at ~5-6 days remaining (expires 2026-05-22). C.B dispatch likely consumes 2-3 days; C.C 3-5 days; C.D 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md` (`3cb334d`).
- Spec: `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; LOCKED post-9-round brainstorm).
- Plan: `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; LOCKED post-6-round writing-plans).
- Return report: `docs/phase12-bundle-C-A-return-report.md` (`56e6993`).
- Integration merge: `354b6c0`.

### Next dispatch

**Phase 12 Sub-sub-bundle C.B (Classifier + validator-shim modules) UNBLOCKED.** Per plan §C decomposition: 14 tasks (T-B.1..T-B.14); +55-95 fast tests projected; classifier consumes the C.A schema; validator-shim mirrors Phase 7 fills schema invariants as importable Python predicates (per spec §5.5 LOCK + §14.OQ-14). Un-skips 2 cross-bundle pin tests at C.B T-B.1 + T-B.2. Pure logic; no journal mutations. **Recommended timing: dispatched by new-orchestrator post-handoff** per operator's session-context-budget-management decision 2026-05-15.

---

## 2026-05-15 Phase 12 Sub-bundle B SHIPPED — Schwab web-UI-friendliness mini-bundle (credentials-in-file + web OAuth paste-back form; Outcome B manual token exchange; 4 Codex rounds NO_NEW_CRITICAL_MAJOR; 16 commits + 1 orchestrator-inline gate-fix; SECOND Phase 12 sub-bundle)

**Sub-bundle B SHIPPED 2026-05-15** at `b09eb06` (integration merge of `phase12-bundle-B-schwab-web-ui-friendliness` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `7b75d4a` (16 implementer commits + 1 orchestrator-inline gate-fix on top of dispatch brief). Operator-dispatched implementer per orchestrator brief at `fc86b8e`.

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/5M/3m → R2 0C/1M/2m → R3 0C/1M/1m → R4 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE on Critical+Major banked** (all 1 Critical + 7 Major resolved with code-content fixes); **+1 orchestrator-inline gate-fix at `7b75d4a`** (operator-paired gate caught a UX gap — `/schwab/setup` was reachable only by typing the URL; orchestrator added "External integrations" section on `/config` page with link to `/schwab/setup` + 1 regression test; mirrors 12A `e2c0384` + 11B `34be84e` precedent — **now 3 inline gate-fix instances cumulatively**).

**The two preceding 2026-05-15 phase3e-todo entries are NOW FULFILLED by this dispatch:** "Web-UI OAuth paste-back form" → T-B.4 `GET/POST /schwab/setup` Outcome B; "Schwab CLIENT_ID + CLIENT_SECRET in user-config.toml" → T-B.1 (cascade) + T-B.2 (cfg dataclass + FIELD_REGISTRY) + T-B.3 (CLI). Both entries are retained below for one-phase-cooldown per orchestrator-context.md retention discipline; will migrate to archive at next Sub-bundle ship.

### Operator-paired gate (2026-05-15 post-merge-prep; orchestrator-driven)

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite | ✅ | 3862 fast pass on main HEAD post-merge + 4 pre-existing failures (3 phase8 walkthrough + 1 schwab_setup_cli sentinel — return report §7 #2 banked separately) + 1 skipped |
| S2 `swing config set integrations.schwab.client_id\|client_secret` | ✅ | Operator's REAL Developer Portal credentials written to user-config.toml; `swing config show` renders masked `6m6***l7` / `2jp***T5` with `source=override` badge |
| S3 cascade resolution (env vars cleared) | ✅ | `swing schwab status --environment production` renders LIVE with NO prompt fired — cfg-tier resolves end-to-end through `apply_overrides` at status callsite (closes Codex R1 Critical fix `e418d56`'s post-conditions) |
| S4 web GET /schwab/setup | ✅ | Worktree-side `swing web --port 8081`; form renders 4 elements (authorize URL link + callback URL paste input + submit button + existing-tokens-DB advisory) + zero console errors |
| S5 web POST /schwab/setup (destructive) | ✅ | Outcome B manual token exchange — operator pastes Schwab callback URL → handler extracts `code` via raw-`&`-split → POSTs to `/v1/oauth/token` → tokens DB rewritten atomically via T-A.2 self-healing rename to `*.deleted-20260515T170457` → HX-Redirect to `/config?schwab_setup=ok` → fresh 7-day refresh-token clock starting 2026-05-15T17:05:00+00:00 (expires 2026-05-22T17:05:00+00:00) + 3 new audit rows (call_id=39 `oauth.code_exchange` self-healing rename http=— + call_id=40 `oauth.code_exchange` actual exchange http=200 + call_id=41 `accounts.linked` http=200) |
| Gate-caught UX gap | ✅ resolved inline at `7b75d4a` | Operator surfaced "no link to navigate to `/schwab/setup`"; orchestrator-inline gate-fix added link on `/config` + regression test |
| S7 ruff baseline | ✅ | 18 E501 unchanged |
| S8 + S9 sentinel-leak + masked rendering | ✅ via S1 pytest | Both covered by T-B.6 + T-B.2 + T-B.3 tests in the fast suite |

### Three highest-leverage SHIPPED deliverables

1. **Credentials-in-file cfg-cascade** — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` join the cfg-cascade as middle tier between env vars and prompt. Persistent across shells; mirrors Finviz token precedent. Asymmetry locked: partial env-tier RAISES (Sub-bundle A LOCK preserved — operator-typo signal); partial cfg-tier FALLS THROUGH (file-tier is operator-friendly per phase3e-todo "Cascade design" intent). Forward-binding lesson #1 for Sub-bundle C.
2. **Web `GET/POST /schwab/setup`** — Outcome B locked (manual token exchange since schwabdev's `Client.__init__` blocks on stdin paste-back). New `setup_paste_flow_with_callback_url` service helper mirrors schwabdev's `Tokens._post_oauth_token` HTTP shape + `Tokens._set_tokens` JSON file format byte-for-byte. HTMX patterns preserved (HX-Request propagation + HX-Redirect success + route-table assertion). Eliminates PowerShell drop-out for weekly Schwab OAuth re-auth.
3. **Orchestrator-inline gate-fix precedent extension to 3 instances** — `/schwab/setup` nav link on `/config` page closes operator-surfaced UX gap; the brief's mandated T-B.4 route-level integration test caught Sub-bundle A T-A.3 implementer-gap-class defects pre-emptively (Codex R1 Critical `apply_overrides` missing at 5 entry points resolved at `e418d56`).

### NEW V2 candidates banked

1. **T-B.7 `/schwab/status` web counterpart** — deferred per Outcome B decision rule. When this ships in a follow-up dispatch, the T-B.4 HX-Redirect target retargets from `/config?schwab_setup=ok` to `/schwab/status`.
2. **`surface='web'` CHECK enum widening** — schema v18 → v19 migration. Resolves T-B.4 audit-row ambiguity (currently `surface='cli'` for web audit rows per v18 CHECK constraint). V2.1 §VII.F amendment candidate.
3. **Option B HTTPS callback handler** — eliminates paste-back entirely. Substantial complexity: local self-signed HTTPS cert, browser security warning, Schwab Developer Portal callback URL reconfiguration. Separate dispatch.
4. **Per-environment-namespaced credentials** — separate `[integrations.schwab.sandbox]` / `[integrations.schwab.production]` tables. V2 candidate.
5. **Web multi-account picker** — V1 raises `SchwabConfigMissingError` for multi-account on web; V2 adds picker UI.
6. **Token encryption-at-rest** — schwabdev's optional `encryption=<key>` Fernet wrapper. Q2 from Phase 11 brainstorm. Operator-paired key management.
7. **Promote `masked_writeable` to `FieldSpec` attribute** — replace `_MASKED_WRITEABLE_PATHS` frozenset allowlist with per-FieldSpec attribute when the catalog grows beyond 2-3 entries. T-B.3 forward-binding lesson #4.
8. **`/config?schwab_setup=ok` query-param consumer** — currently dead query param; future enhancement could surface "Schwab setup successful" toast on `/config` page.
9. **schwabdev version pin + extended compat test** — Outcome B mirrors schwabdev's private API byte-for-byte; defensive `schwabdev==2.5.1` pin in pyproject.toml + extended regression test that constructs a real `schwabdev.Client` (not just `Tokens`) against the written file.
10. **T-B.2 stale-comment cleanup** at `swing/config_validation.py:91-93` + `swing/config_overrides.py:25-26` — comments saying client_id/client_secret are "NOT editable via `swing config set`" are now factually incorrect post-T-B.3. Banked here for next polish-bundle dispatch.

### 12 forward-binding lessons for Sub-bundle C dispatch (return report §10)

1. Three-tier credential cascade asymmetry pattern (env partial RAISES; cfg partial FALLS THROUGH)
2. Outcome A vs B SDK-wrapping recipe — manual token-exchange byte-for-byte mirror + atomic tokens-file write + SDK construction reads back
3. `surface='X'` CHECK constraint workaround pattern — when enum widens at v_N but schema migrations out-of-scope, document deviation in code comment + bank V2.1 §VII.F amendment
4. `_MASKED_WRITEABLE_PATHS` allowlist + `_FIELD_PATHS` filter pattern (canonical way to gate masked CLI fields)
5. N-part dotted-path generalization at write/read/delete (all 3 call sites touch together: `config_user.py:delete_user_override` + `cli_config.py:_write_override_nested` + `config_overrides.py:get_field_source`)
6. **`apply_overrides()` discipline at Schwab entry points** — Codex R1 Critical surfaced — project-wide invariant candidate: consider moving `apply_overrides` into `load_config` itself OR into the FastAPI lifespan hook
7. `parse_qs` vs `unquote` for OAuth code parsing — `parse_qs` applies `application/x-www-form-urlencoded` semantics; OAuth codes are opaque; use raw query-string split + `urllib.parse.unquote` (NOT `unquote_plus` or `parse_qs`)
8. Atomic file-write fsync discipline — match `swing/config_user.py:write_user_overrides` pattern (tempfile same-dir → write → flush → fsync → os.replace → best-effort parent-dir fsync)
9. Real-SDK compat regression test pattern — when mirroring an external SDK's private API byte-for-byte, the regression test MUST invoke the real SDK's loader
10. Cross-bundle base-layout VM pin discipline — every new VM extending `base.html.j2` MUST populate `unresolved_material_discrepancies_count` (Phase 10 T-E.3 pin)
11. HTMX gotcha trinity preserved for any new form-driven route (HX-Request propagation + 204+HX-Redirect + HX-Redirect target route exists)
12. Sub-bundle A T-A.3 implementer gap pre-emption discipline — for any new entry point that threads credentials through multiple call sites, the route-level integration test MUST mock the service function + assert the EXACT cascade-resolved credential values were threaded through

### Cross-references

- Dispatch brief: `docs/phase12-bundle-B-schwab-web-ui-friendliness-executing-plans-dispatch-brief.md` (`fc86b8e`).
- Return report: `docs/phase12-bundle-B-return-report.md` (on main post-merge).
- Orchestrator-inline gate-fix: `7b75d4a` (on worktree branch + merged via `--no-ff`).
- Integration merge: `b09eb06`.

### Next dispatch

**Phase 12 Sub-bundle C (auto-correct journal-from-Schwab service) UNBLOCKED.** Per the architectural pivot banked at `28a7d01` + `75b876c`. Substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected. Operator-paced. Three-tier resolution model (auto-correct unambiguous + ambiguity surfaced + operator override); magnitude is the WRONG axis (determinism is the axis); closes the 3 unresolved-material discrepancies (39 DHC + 40 VSAT + 41 CVGI) + future categorical fiction-vs-truth divergences.

---

## 2026-05-15 Web-UI OAuth paste-back form (`GET/POST /schwab/setup`) — operator-stated UX gap; bundle with credentials-in-file as Phase 12 Sub-bundle B

**Operator UX gap (2026-05-15 during Phase 12 Sub-bundle A close discussion):** `swing schwab setup` is CLI-only. Operator's normal mode is the web interface (`swing web` on 127.0.0.1:8080). Weekly OAuth re-auth currently forces operator to drop to a separate PowerShell session for the paste-back flow. No web-side equivalent exists.

**Proposed Option A (simpler; recommended for V1):** new web route `GET /schwab/setup` renders a simple form:
- Step 1: pre-populated clickable link to the Schwab authorize URL (opens in new tab via `target="_blank"`).
- Step 2: text input for "paste your callback URL here".
- Step 3: submit button.

`POST /schwab/setup` handler runs the same `setup_paste_flow` service-layer function from Sub-bundle A T-A.4 (NOT a re-implementation). T-A.2 self-healing (auto-rename stale tokens DB before invoking schwabdev) applies identically. Operator interaction: navigate to `/schwab/setup` → click authorize link (new tab) → complete OAuth → copy callback URL from address bar → paste into form on original tab → submit. Same number of paste actions as CLI flow but stays inside web UI context — operator never leaves browser.

Web-form must use HTMX patterns per Phase 5+ HTMX failure-surface gotchas: embedded form `hx-headers='{"HX-Request": "true"}'` for OriginGuard strict-mode propagation; success-path `204 No Content` + `HX-Redirect: /schwab/status` (NOT 303 swap-target); HX-Redirect target route must exist (verify via TestClient route-table assertion). Server-stamping discipline applies (operator-supplied = the callback URL; everything else server-stamped).

**Option B (V2 candidate; eliminates paste-back entirely):** local HTTPS callback handler at e.g. `https://127.0.0.1:8443/schwab/oauth/callback`. Browser hits handler directly after Schwab redirects; server extracts `code` from URL params; completes exchange automatically. Pros: zero paste-back. Cons: requires local self-signed HTTPS cert (browser security warning; operator must accept cert), separate HTTPS port listener, Schwab Developer Portal app callback URL must be reconfigured. Substantial complexity for the UX win — banked V2 candidate.

### Bundle with credentials-in-file (preceding phase3e-todo entry) as Phase 12 Sub-bundle B

Both target the same operator pain — "make Schwab setup work without dropping to PowerShell":
- **Credentials-in-file** (`user-config.toml` cascade): CLI + web both read app credentials from one place; no per-shell env vars.
- **Web OAuth setup form** (`GET/POST /schwab/setup`): operator never leaves browser for weekly re-auth.

Bundled scope: ~12-18 fast tests; 2-3 Codex rounds; 1-2 days. Shared infrastructure (`construct_authenticated_client` cascade for credentials; `setup_paste_flow` for OAuth) makes bundling efficient. Combined dispatch as "Phase 12 Sub-bundle B — Schwab web-UI-friendliness mini-bundle."

### Architectural changes required (web-form portion)

1. **New route at `swing/web/routes/schwab.py`** (or co-located in existing routes module). `GET /schwab/setup` renders the form template; `POST /schwab/setup` runs `setup_paste_flow(cfg, environment, client_id, client_secret, callback_url=<operator-pasted>)`. Credentials sourced from the cascade (env vars > user-config.toml > prompt — except prompt path is N/A in web context; if neither env vars nor file values present, render an error pointing operator at `/config` or `swing config set`).
2. **New template at `swing/web/templates/schwab_setup.html.j2`** following base.html.j2 extension pattern (must add any new VM fields to ALL base-layout VMs per CLAUDE.md gotcha).
3. **New view model `SchwabSetupVM`** with the standard base-layout fields + setup-specific fields (authorize URL, optional success/error message, optional pre-existing-tokens-DB warning).
4. **CycleChecklist update** to reference the web URL (`http://127.0.0.1:8080/schwab/setup`) as the primary weekly re-auth path; CLI command remains as fallback.
5. **`swing schwab status` web counterpart at `GET /schwab/status`** — V2 candidate (smaller; not load-bearing for OAuth flow); could ship in same Sub-bundle B if operator wants the status surface in the web UI too.
6. **CLAUDE.md gotcha addition** — "Schwab OAuth web setup flow" documents Option A's HTMX requirements (embedded form HX-Request propagation; HX-Redirect success path; T-A.2 self-healing applies identically; route table must include `/schwab/setup` GET + POST).

### Sequencing within Sub-bundle B

If bundled with credentials-in-file:
- Task 1: credentials-in-file cascade extension (T-A.1 helper extends; SchwabConfig dataclass extends).
- Task 2: `swing config set integrations.schwab.client_id` + `client_secret` cascade emitter wires.
- Task 3: web `GET/POST /schwab/setup` form + POST handler integration.
- Task 4: cycle-checklist + CLAUDE.md updates.
- Task 5: optional `GET /schwab/status` web counterpart.
- Task 6: end-to-end happy-path integration test.

### Cross-references

- Sub-bundle A T-A.4 setup_paste_flow CLI implementation: `swing/integrations/schwab/auth.py:setup_paste_flow`.
- Sub-bundle A T-A.2 self-healing logic (applies identically to web POST): same file.
- Phase 5 HTMX failure-surface gotchas: CLAUDE.md HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted gotchas.
- Phase 8 server-stamping discipline gotcha (relevant to web POST: operator-supplied = callback URL only; everything else server-stamped).

---

## 2026-05-15 Schwab CLIENT_ID + CLIENT_SECRET in user-config.toml (Finviz precedent; operator-stated UX gap during Phase 12 Sub-bundle A S6 gate)

**Operator UX clarification (2026-05-15):** Phase 12 Sub-bundle A T-A.1 env-var path is "better than copying and pasting" but not great from a user perspective:
- Each shell session needs `$env:SCHWAB_CLIENT_ID` + `$env:SCHWAB_CLIENT_SECRET` set (PowerShell shell for CLI; separate shell for `swing web`; etc.). Operator could set in PowerShell profile but that's per-shell-application.
- Operator initially worried about weekly reset — **clarification: app credentials (CLIENT_ID + CLIENT_SECRET) are STABLE from Schwab Developer Portal app registration; do NOT weekly-rotate.** What rotates weekly is the OAuth refresh_token (managed by schwabdev's tokens DB; rotated via paste-back; separate concern). So env vars only need to be set ONCE per Schwab Developer Portal credential rotation (rare — only when operator regenerates app credentials from the portal).

**Operator's intended UX:** file-based credential storage in `~/swing-data/user-config.toml` under `[integrations.schwab]` (mirrors Finviz precedent — Finviz token already lives here under `[integrations.finviz]`; per CLAUDE.md gotcha "Finviz Elite API token storage": user-config.toml is `%USERPROFILE%/swing-data/user-config.toml` — operator's home dir, NOT in repo, NOT git-tracked, per-machine, plaintext). Operator edits ONCE per app credential rotation; every shell automatically picks up the same values; no per-shell setup required.

### Cascade design

Three-tier credential resolution (extend the T-A.1 helper):
1. **Env vars** (highest priority) — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`. Useful for: scripted ops; CI/CD; per-invocation override of file-stored values; security-conscious operators who don't want plaintext on disk.
2. **`user-config.toml` `[integrations.schwab].client_id` + `.client_secret`** (middle priority) — file-stored; persists across shells + reboots; operator edits once per credential rotation. The DEFAULT operator path.
3. **Interactive prompt** (lowest priority; fallback) — current Sub-bundle A T-A.2 behavior preserved when neither env vars nor file values present. Useful for: first-run operators; one-off CLI invocations on a fresh machine.

`construct_authenticated_client(cfg, environment)` consults in this order; first non-empty pair wins. Both-or-neither at each tier (partial → next tier) — UNLIKE T-A.1 partial-rejects-with-error, since file-tier may have CLIENT_ID set without CLIENT_SECRET (rare but valid as the operator may want to fall through to env vars or prompt for the secret).

### Architectural changes required

1. **Extend `SchwabConfig` dataclass** (`swing/config.py`) with `client_id: str | None = None` + `client_secret: str | None = None` fields. ADD to `FIELD_REGISTRY` with `masked=True` (first-3 + *** + last-2 per existing FIELD_REGISTRY pattern). `swing config show` displays masked values.
2. **Extend `resolve_credentials_env_or_prompt`** (T-A.1 helper at `swing/integrations/schwab/auth.py`) with the three-tier cascade. Currently env-var-or-prompt; becomes env-var-or-cfg-or-prompt.
3. **`swing config set integrations.schwab.client_id <value>`** + `client_secret <value>` paths via existing `swing config set` cascade emitter. Mirrors existing finviz token-set path.
4. **CLAUDE.md gotcha addition** — "Schwab CLIENT_ID + CLIENT_SECRET storage" mirrors existing "Finviz Elite API token storage" entry. Tracked `swing.config.toml` MUST NOT contain the values (sensitive); only `~/swing-data/user-config.toml`. `.gitignore` patterns for `user-config.toml*` should already cover (verify).
5. **Sentinel-leak audit extension** — env-var sentinel-leak coverage exists post-Sub-bundle-A; extend to cfg-cascade-sourced credentials so Layer 0 redactor's known-secret registry picks them up at SchwabClient construction time.
6. **Backwards-compat** — operators relying on env vars continue to work unchanged (env vars are highest-priority tier).

### Sequencing — could ship BEFORE Sub-bundle B (auto-correct service)

This is a small Tier 1.5 polish dispatch (smaller than Sub-bundle B's architectural pivot). ~6-10 fast tests; 1-2 Codex rounds; 1 day. Could ship as Phase 12 Sub-bundle B (re-scoped) OR as a fast-follow before the auto-correct service work.

### Cross-references

- Finviz precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` + CLAUDE.md "Finviz Elite API token storage" gotcha.
- Sub-bundle A T-A.1 implementation: `swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt`.
- Sub-bundle A T-A.2 design rationale (credentials NOT in cfg cascade): security posture per dispatch brief; this entry SUPERSEDES with a more nuanced cascade design.

---

## 2026-05-15 ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab, not surface for operator-triage (Phase 12 Sub-bundle B headline candidate)

**Surfaced (operator-stated 2026-05-15 during Phase 12 Sub-bundle A S5 gate):** the current Phase 9 + Phase 11 reconciliation model surfaces journal-vs-Schwab discrepancies for operator-triage with resolutions of `acknowledged_immaterial` / `journal_corrected` / `mistake_corrected`. Operator pushed back: when Schwab data is available, **Schwab IS truth — there is no "immaterial" price magnitude**. Operator-action loop is the wrong design. The fact that 3 discrepancies re-emerged on pipeline #63 after operator "resolved" 7 of 8 yesterday demonstrates this concretely: yesterday's resolutions only marked OLD discrepancy ROWS as resolved; they did NOT update the underlying fills. Each fresh `reconciliation_run` re-detects the same mismatches because journal data still diverges from Schwab.

**Operator's intended model — three-tier resolution (operator clarification 2026-05-15):**

1. **Unambiguous auto-correct (the common case):** reconciliation detects a journal-vs-Schwab mismatch where the correction is deterministic — single Schwab record maps to single journal fill, single field differs, clear "set journal field to Schwab value." System auto-corrects journal to match Schwab + writes audit row capturing pre/post values. No operator involvement needed. Example: CVGI disc 41 (journal $5.23 vs Schwab $5.30 on a single matching fill) — system can unambiguously resolve.

2. **Ambiguity surfaced for operator decision (operationally important — second most common):** system detects mismatch but cannot deterministically decide the correction. Examples:
   - Schwab shows multiple partial fills (e.g., DHC entry as 20+19 partials at slightly different prices) + journal has single consolidated entry — system cannot decide whether to (a) split journal into matching partials, (b) keep journal consolidated + use Schwab's volume-weighted avg price, (c) pick a representative fill, (d) something operator-specific.
   - Multiple Schwab transactions could match the same journal fill within a window — which is the "right" match?
   - Schwab data shape doesn't fit existing journal schema (e.g., new transaction subtype not in CHECK enum).
   - Data shape transformation requires operator judgment (intraday timestamps preserved vs rolled to EOD; fee allocation across split fills).
   
   Surfaced to operator with **clear message: what the discrepancy is + what the ambiguity is + what the resolution choices are**. Operator picks (or provides custom). System then auto-applies the chosen resolution + audits.

3. **Operator overrides an auto-correction (the rare edge case):** operator has ground-truth knowledge that Schwab itself is wrong (known broker error; reporting glitch; operator caught it before it propagated). Operator marks an applied correction as `operator_overridden` + provides ground-truth value + reason. Audit chain preserves all three values: pre-correction journal / Schwab-said / operator-override.

The current Phase 9 + 11 model collapses tiers (1) + (2) into a single "operator triages everything" loop, which is the wrong default. The new architecture must distinguish: **deterministic correction → auto-apply silently** vs **ambiguous case → surface with clear choices** vs **rare override case → preserve all three values in audit**.

### Concrete current-state evidence

Discrepancies 39/40/41 from pipeline #63 (run_id=10) are LITERALLY IDENTICAL to siblings 32/36/37/34/38 from runs 8+9 (same fill_id, same expected_value_json, same actual_value_json):

- **disc 41 CVGI entry_price_mismatch:** journal `fills.fill_id=9` price=$5.23, Schwab=$5.30, **delta $+0.07** (yesterday's resolution claimed "~$0.01 off" — wrong magnitude AND no actual correction made).
- **disc 39 DHC unmatched_open_fill:** journal `fills.fill_id=2` entry @$7.58 × 39 on 2026-04-27, Schwab `actual={"matched": null}` (likely Schwab split entry into multiple partial fills with different timestamps/prices; operator's single-row journal entry can't match).
- **disc 40 VSAT unmatched_open_fill:** journal `fills.fill_id=6` entry @$65.69 × 2 on 2026-05-06, `manual_entry_confidence='low'` (operator flagged as uncertain at entry time!), Schwab `actual={"matched": null}`.

**All three fills carry `reconciliation_status='unreconciled'` + `tos_match_id=NULL`** — they were operator-typed-from-memory and never linked to a Schwab/TOS source record at entry time. Reconciliation correctly identifies them as fiction-vs-truth divergences.

### Architectural changes required

1. **New ambiguity classifier** at the reconciliation layer. For every detected mismatch, classify as:
   - `auto_correctable` — single journal fill + single Schwab record + single field differs + clear target value → tier 1 auto-apply.
   - `ambiguous` — multiple-to-one mapping, shape mismatch, missing-field-on-one-side, schema-doesn't-fit, or any case where multiple deterministic resolutions exist → tier 2 surface for operator. Classifier MUST emit a structured `ambiguity_kind` enum (e.g., `multi_partial_vs_consolidated`, `multi_match_within_window`, `unknown_schwab_subtype`, `field_shape_incompatible`, `schwab_returned_no_match`) so the operator-facing UI can render type-specific resolution choices.
   - `unsupported` — system genuinely cannot reason about the mismatch (e.g., new Schwab API field shape; cassette-fixture-only edge case) → tier 2 with explicit "system needs code update; please report" message.
2. **New service-layer auto-correction module** at `swing/trades/reconciliation_auto_correct.py` (or similar). Transactional (BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject caller-held tx per Phase 8 lesson family). Validator-respecting (Phase 7 fills validators; Phase 9 risk_policy). Audit-aware. Handles tier-1 auto-correctable cases only; tier-2 cases get queued for operator decision (do NOT auto-apply ambiguous cases).
3. **New audit-history table** OR extension of `event_log` to preserve pre-correction journal values (forensic trail; "what did the operator originally enter; what did Schwab show; what action was taken; when").
4. **Tier-2 ambiguity-resolution UI/CLI** — operator-facing surface that renders the discrepancy + ambiguity_kind + resolution choices specific to the kind. E.g., `multi_partial_vs_consolidated` choices: (a) split journal into matching partials; (b) keep consolidated + use Schwab volume-weighted avg price; (c) keep journal as-is + mark schwab_partial_fill_aggregation_acknowledged; (d) operator-custom value. Each choice maps to a deterministic action; operator pick → service auto-applies + audits.
5. **Reconciliation flow pivot:** discrepancy emission becomes a multi-tier dispatch — tier-1 cases auto-apply silently; tier-2 cases surface for operator decision; tier-3 (operator override of an applied tier-1 correction) is a separate post-hoc UI surface. Discrepancy table semantics shift: rows represent classification + (for tier-2) pending operator decision OR (for tier-1+tier-3) audit history.
6. **`fills.reconciliation_status` enum change:** `unreconciled` → `auto_matched` / `auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`. `tos_match_id` populated for auto-matched + auto-corrected + operator-resolved.
7. **No magnitude-based auto-vs-surface threshold** — magnitude is the WRONG axis (operator clarification: $0.07 isn't "small"; the question is whether the correction is deterministic, not whether the delta is big). Ambiguity classifier replaces threshold gates.
8. **Backfill path** for existing unresolved-material discrepancies (39/40/41 + any future): when the auto-correction service ships, run the classifier across all currently-unresolved discrepancies. Tier-1 cases auto-apply + audit. Tier-2 cases get queued for operator decision via the new UI.
9. **Fill auto-population at trade-entry time** (the unstated V2 candidate): create fills directly from Schwab Trader API responses at trade-entry handler time instead of operator-typing-from-memory. Closes the entire discrepancy stream as a CATEGORY (not just one-at-a-time). Fills get `tos_match_id` populated from start; no future fiction-vs-truth divergence possible. Probably a separate sub-bundle (Sub-bundle B vs Sub-bundle C decision; brainstorm should determine ordering).

### Per-discrepancy classification of the current 3 unresolved (illustrative — informs the new architecture's expected workload)

- **disc 41 CVGI entry_price_mismatch** → likely **`auto_correctable` (tier 1)**: single journal fill `fill_id=9` matches single Schwab transaction by date+ticker+qty; only `price` field differs ($5.23 vs $5.30). System sets journal price to $5.30 + writes audit row + done. No operator involvement.
- **disc 39 DHC unmatched_open_fill** → likely **`ambiguous` (tier 2)** with `ambiguity_kind=multi_partial_vs_consolidated`: journal has single fill `qty=39 @ $7.58`; Schwab almost certainly has partial fills (e.g., 20 + 19 at slightly different prices). Operator picks split-into-partials vs keep-consolidated + average + audit.
- **disc 40 VSAT unmatched_open_fill** → either `ambiguous` (`multi_partial_vs_consolidated` if Schwab split entry) OR `auto_correctable` (if Schwab has single fill at slightly different price/qty). Classifier determines which on a per-row basis.

### What this is NOT

- NOT a polish/observability bundle (those were the Tier 2 items I originally outlined).
- NOT a Sub-bundle A scope expansion (Sub-bundle A's env-var + setup-self-healing + pipeline-env-var changes are still independently valuable; merge as planned).
- NOT a quick fix (touches reconciliation core + introduces new audit semantics + requires careful migration of existing data; substantial brainstorm + writing-plans + multi-bundle executing-plans cycle).

### Recommended sequence

1. **Finish Sub-bundle A gate (S6 + S7) + merge** — Tier 1 ops-pain fixes ship as scoped.
2. **Leave the 3 current unresolved-material discrepancies (39/40/41) alone for now.** They're correct signal; operator-action would just mark-as-resolved without fixing the underlying fiction-vs-truth divergence. Phase 10 dashboard banner shows "3 unresolved" until auto-correction ships — that's accurate state.
3. **Phase 12 Sub-bundle B = brainstorm + writing-plans + executing-plans for the auto-correction pivot.** Operator-paced; substantial dispatch.

### Cross-references

- Phase 9 Sub-bundle B reconciliation_run shape: `swing/trades/reconciliation.py` (`run_tos_reconciliation` mirror used by `run_schwab_reconciliation`).
- Phase 11 Sub-bundle B `swing_schwab_reconciliation` service.
- Phase 8 transactional-discipline pattern (caller-rejection + BEGIN IMMEDIATE) for the new auto-correction service.
- Phase 7 single-write-path discipline + audit-trail patterns.
- Phase 10 Sub-bundle E §A.18 dashboard banner consumer (continues to read `count(unresolved-material)` predicate; semantics shift when that count drops to ~0 once auto-correction is the norm).

---

## 2026-05-15 `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex too narrow — `phase\d+-*` doesn't match `schwab-bundle-*`

**Symptom (operator-surfaced 2026-05-15 during Sub-bundle D post-merge cleanup):** the cleanup script's `-DeregisterFirst` safety filter regex `phase\d+-*` does NOT match the Schwab arc's worktree naming convention `schwab-bundle-*`. Result: all 4 Schwab worktrees were skipped during the deregister scan; operator + orchestrator had to manually invoke `git worktree remove --force` for each + then re-run the script to clean ACL-locked dirs.

**Root cause:** the script was authored at post-Phase-10 infrastructure bundle SHIPPED (commit `27ce96f`) when ALL prior worktree branches had `phase\d+-*` naming (phase8/phase9/phase10 bundles). The Schwab arc's `schwab-bundle-A/B/C/D-...` naming was the first deviation; the regex didn't follow.

**Fix candidate:** widen the safety filter regex to `(phase\d+|schwab(?:-\w+)?)-bundle-` OR introduce a configurable filter (e.g., `-BranchPattern` parameter; default `phase\d+-*` for backward compat). Operator-paced; bundle into the next polish dispatch OR address inline at next worktree-husk cleanup cycle.

**Defense-in-depth:** orchestrator briefs for future arc-style dispatches MUST either (a) use `phase{NN}-bundle-*` naming convention to match the existing regex, OR (b) explicitly thread the cleanup-script regex extension into the dispatch brief as a watch item.

**Cross-reference:** Phase 10 infrastructure bundle SHIPPED entry at `27ce96f` — the original `-DeregisterFirst` switch addition (Codex R1 Critical #1 confirm-before-deregister gate landed in that bundle).

---

## 2026-05-15 Pipeline run on empty finviz inbox should auto-trigger `_step_finviz_fetch` — **SHIPPED 2026-05-18 at `7a84942`** (3rd gate-blocker occurrence closed; 3 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; ZERO Co-Authored-By footer drift; +6 fast tests; ruff/schema unchanged)

**SHIPPED 2026-05-18** at integration merge `7a84942` (branch `phase12-5-finviz-inbox-auto-fetch-fix`; 5 commits = 1 task-impl + 3 Codex-fix + 1 return-report). Fix at `swing/pipeline/runner.py:525-602` splits the combined catch — `NoFilesError` triggers ONE inline `_step_finviz_fetch` attempt + retry `select_csv`; `AmbiguousInboxError` stays fail-fast. Site 2 (line 638) gated on `not finviz_fetched_inline` to prevent double-fire (would persist 2 `finviz_api_calls` audit rows per run). 2 new private helpers: `_read_finviz_call_max_id_snapshot` (causal anchor) + `_read_latest_finviz_call_diagnostic` (scoped read of audit row inserted by THIS call). Combined error message now surfaces the real Finviz cause (missing token / auth / rate-limit / schema parity) instead of redundant "No CSV files" twice. Operator-witnessed 2-surface gate PASS: S1 4581 fast + ruff 18; S2 pipeline #67 complete from empty inbox in 45s (F5 audit-row contract verified — 1 finviz_api_calls row, no double-fire). 3 forward-binding lessons banked (audit-row contract tests require lower-level monkeypatch; `_read_latest_*` helpers in multi-surface code must scope by PK snapshot; USERPROFILE/HOME read-side pollution symmetric to existing write-side gotcha).

### Original entry (2026-05-15; pre-dispatch; superseded by SHIPPED outcome above)

**Symptom (operator-surfaced 2026-05-15 during Phase 12 Sub-bundle A S5 gate):** `swing pipeline run` against an empty `data/finviz-inbox/` (folder exists but contains no CSV — common in fresh worktrees per yesterday's #3 fix that auto-creates the dir but doesn't populate it) errors with `No CSV files in <dir>` + state=failed. Should instead invoke the Finviz Elite API fetch path (`_step_finviz_fetch` semantics) to auto-populate the inbox + then proceed.

**Root cause:** at `swing/pipeline/runner.py:run_pipeline_internal` L425+, `select_csv(cfg.paths.finviz_inbox_dir)` runs FIRST + raises `NoFilesError` on empty dir → pipeline fails. `_step_finviz_fetch` (which DOES auto-fetch via Finviz API) is registered as a pipeline step at L499, AFTER `select_csv` has already errored. The architectural intent appears to have been "pipeline reads existing CSV from prior `swing finviz fetch` invocation" — but on first-run empty-inbox state, there's no prior CSV.

**Fix candidate:** when `select_csv` raises `NoFilesError`, attempt a synchronous `_step_finviz_fetch` (or extracted core helper `_finviz_fetch_core(cfg)`) inline + retry `select_csv`. If the auto-fetch ALSO produces no CSV (Finviz API rate-limited, Finviz Elite credentials missing, etc.) → THEN fail with combined error message ("inbox empty + auto-fetch failed: <reason>"). Preserves the existing select-then-error path for AmbiguousInboxError; only the empty-inbox path is widened.

**Discriminating-test pattern:** plant empty inbox dir (after yesterday's #3 mkdir bootstrap fix) + monkeypatch `_finviz_fetch_core` to write a known CSV + invoke `run_pipeline_internal` + assert (a) auto-fetch fired, (b) CSV present in inbox post-call, (c) pipeline state != "failed" on the inbox-empty cause (may still fail later on yfinance / Schwab / etc. — that's fine; the empty-inbox cause is the specific axis under test).

**Defer-or-fix-soon disposition:** small-scope bug; bundle into next polish dispatch (could be next Phase 12 sub-bundle OR standalone). Operator-paced.

**Cross-references:**
- 2026-05-15 yesterday's missing-folder fix at commit `6ea94f7` (closed the missing-FOLDER case; this is the empty-FOLDER follow-up).
- `_step_finviz_fetch` definition at `swing/pipeline/runner.py:1956` + `_finviz_fetch_core` helper at L1791.
- `select_csv` at `swing/pipeline/finviz_select.py:50`.

---

## 2026-05-15 Pipeline run errors out on missing `data/finviz-inbox/` folder — **SHIPPED 2026-05-15 at `6ea94f7`** (missing-FOLDER case closed; companion empty-FOLDER case shipped 2026-05-18 at `7a84942` — see entry above)

**SHIPPED 2026-05-15** at commit `6ea94f7` (mkdir bootstrap in `_step_finviz_fetch` + mirrored in `run_pipeline_internal:510` per Codex R1 Major-2 fix family). Closed the missing-FOLDER case (`data/finviz-inbox/` directory absent). The companion empty-FOLDER case (`data/finviz-inbox/` exists but contains no CSV) shipped 2026-05-18 at `7a84942` (see entry above).

### Original entry (2026-05-15; pre-fix; superseded by SHIPPED outcome above)

**Symptom (operator-surfaced 2026-05-15 during Sub-bundle D operator-witnessed gate):** `swing pipeline run` errors out with "no csv found" when `data/finviz-inbox/` directory does not exist on the operator's filesystem.

**Expected behavior:** pipeline should check for folder existence first + create the folder via `os.makedirs(..., exist_ok=True)` if missing. The directory is operator-data convention (configured in `swing.config.toml`) — its absence is the natural first-run state, not an error condition.

**Likely fix location:** `swing/pipeline/runner.py:_step_finviz_fetch` (the step that consumes the inbox). Add `Path(cfg.paths.finviz_inbox_dir).mkdir(parents=True, exist_ok=True)` near the top of the step.

**Discriminating-test pattern:** delete `data/finviz-inbox/` (or use a tmp_path with the dir absent) + invoke pipeline run + assert directory was auto-created + step completed (or surfaced "no manual CSV; using API fallback" path correctly per existing `_step_finviz_fetch` semantics).

**Defer-or-fix-soon disposition:** trivial fix; bundle into a near-term polish dispatch OR address inline. NOT Schwab-arc-related; banked here for orchestrator triage.

---

## 2026-05-15 Phase 12 Sub-bundle A SHIPPED — Schwab API operational-pain mini-bundle (env vars + setup self-healing + pipeline env-var wiring + cleanup-script regex; 3 Codex rounds + 1 orchestrator-inline gate-fix; 12 commits; FIRST Phase 12 dispatch)

**Sub-bundle A SHIPPED 2026-05-15** at `123d27a` (integration merge of `phase12-bundle-A-schwab-operational-pain` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `e2c0384` (12 commits = 4 task-impl + 2 pre-Codex review fixes + 5 Codex-fix + 1 orchestrator-inline gate-fix on top of return report `2cbb8c4`). Operator-dispatched implementer per orchestrator brief at `892e3e3`.

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 1C/2M → R2 0C/1M → R3 0C/0M); **ZERO ACCEPT-WITH-RATIONALE banked**; **+1 orchestrator-inline gate-fix at `e2c0384`** (closed T-A.3 acceptance #4 gap that operator-paired S5 surfaced — implementer's T-A.3 wired the env-var-constructed schwab_client into the market-data ladder hook but LEFT both `_step_schwab_snapshot` + `_step_schwab_orders` callsites with `client=None` HARDCODED; orchestrator-inline fix wired schwab_client through both callsites + added discriminating regression test).

**Why no brainstorm + no writing-plans:** Per operator scope decision 2026-05-15, V2 candidates from Phase 11 arc were well-defined; this bundle went straight to executing-plans dispatch as a focused operational-pain mini-bundle.

### Operator-paired live gate (Option A; 2026-05-15)

Full S2-S7 live verification against operator's production-tier Schwab account + worktree-side inline S1+S8+S9 PASS:

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite (worktree) | ✅ | 3786 → 3787 passed (post-orchestrator-inline gate-fix); 3 pre-existing phase8 failures unchanged |
| S2 status with env vars | ✅ | NO credential prompt (T-A.1); LIVE indicator + token TTL 6d 18h + recent calls (24-28); ZERO token bytes |
| S3 fetch --verify-marketdata with env vars | ✅ | NO prompt; calls 30 + 31 success against live Schwab Market Data API |
| S4 setup self-healing | ✅ | T-A.2 atomic rename of existing tokens DB to `*.deleted-20260515T095338` + audit row at call 32 + fresh paste-back; same hashValue=E8F...0676 auto-picked; **fresh 7-day clock started 2026-05-15T03:59:25 UTC** |
| S5 pipeline with env vars | ❌→✅ post-fix `e2c0384` | Initial pipeline #62 ran with ZERO new schwab_api_calls (T-A.3 implementer-side gap caught at gate). **Orchestrator-inline gate-fix** wired schwab_client through both Sub-bundle B step callsites + added regression test. Re-run pipeline #63 completed in 11s with 4 new schwab_api_calls (calls 35-38; surface=pipeline; endpoints accounts.details + accounts.orders.list + accounts.transactions.list) + new reconciliation_run #10 + 3 fresh discrepancies (39 DHC + 40 VSAT + 41 CVGI). **BONUS validation: Sub-bundle B same-day-replay UPSERT path NOW operationally validated** (snapshot_id=5 from yesterday preserved; call 35 linked via linked_snapshot_id=5 — closes one of the three V2-deferred validations from Phase 11 Sub-bundle B SHIPPED entry). |
| S6 pipeline without env vars | ✅ | Pipeline #64 in 9s; ZERO new schwab_api_calls + ZERO new domain rows (T-A.3 silent-skip path preserved per acceptance #2) |
| S7 cleanup-script regex | ✅ via test coverage | 11 cleanup-script regex unit tests inline GREEN at `tests/scripts/test_cleanup_script_regex.py` (skip destructive plant-fake-worktree path) |
| S8 ruff baseline | ✅ | 18 E501 unchanged |
| S9 sentinel-leak audit | ✅ | New T-A.1 + T-A.3 paths covered by existing `tests/integrations/test_schwab_token_redaction_audit.py` patterns |

### Orchestrator-inline gate-fix at `e2c0384` (mirrors Sub-bundle B's `34be84e` precedent)

**Defect:** runner.py L728-738 + L747-757 hardcoded `client=None` at both Sub-bundle B `_step_schwab_snapshot` + `_step_schwab_orders` callsites. T-A.3 implementer wired env-var helper into `_install_pipeline_marketdata_caches` (market-data ladder) but missed parallel wiring into snapshot/orders callsites. Implementer's +5 helper-return-contract tests didn't integration-test the runner-level wiring through to Sub-bundle B's pipeline steps.

**Fix:** pass `client=schwab_client` instead of `client=None` at both callsites. Single-line per callsite + 1 discriminating regression test (`test_runner_threads_schwab_client_into_snapshot_and_orders_steps` does source-level pattern matching on runner.py to assert `client=schwab_client, surface="pipeline"` shape; explicitly rejects pre-fix `client=None, surface="pipeline"` shape).

### Three highest-leverage SHIPPED deliverables

1. **Credential entry UX** — `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` env vars supersede interactive prompt at `construct_authenticated_client`. Both-or-neither resolution (partial → SchwabConfigMissingError with actionable message). Operator can now `$env:SCHWAB_CLIENT_ID = "..."; $env:SCHWAB_CLIENT_SECRET = "..."` once per shell session (or in PowerShell profile) → every Schwab CLI invocation runs without prompts. Daily-use unblock.
2. **`swing schwab setup` self-healing** — auto-detects + atomically renames stale tokens DB to `*.deleted-<ts>` (24h recovery window) BEFORE invoking schwabdev. Closes Sub-bundle C operator-paired-gate finding from yesterday (`logout → setup` recovery sequence is no longer needed; `setup` now handles it in one shot).
3. **Pipeline env-var path** — `_construct_pipeline_schwab_client(cfg)` reads same env vars; both-or-neither (partial → return None + log WARNING). Pipeline now actually fires Schwab steps end-to-end when operator has env vars set. Closes T-C.6 D1 ACCEPT-WITH-RATIONALE V1 graceful-degradation gap.

### NEW V2.1 §VII.F amendment candidates banked (per implementer return report)

1. `oauth.tokens_db_rename` dedicated endpoint enum value for T-A.2 audit row (currently uses `oauth.code_exchange` with descriptive error_message; would require schema v18→v19 to add new enum value).
2. Unify `logout` `revoke_and_delete` timestamp to UTC.

### Tests + ruff + schema deltas

- Tests: 3752 → 3787 (+35 net = +34 implementer + 1 inline gate-fix regression). Within +20..+40 brief projection.
- Ruff baseline: 18 E501 unchanged.
- Schema version: v18 unchanged (Sub-bundle A is consumer-side only).

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **3 unresolved material discrepancies (39/40/41) from pipeline #63 are LEFT UNRESOLVED by design** — they're correct signal of fiction-vs-truth divergences; will be auto-corrected categorically when Phase 12 Sub-bundle B (auto-correct service) ships. Phase 10 dashboard banner shows "3 unresolved" until then — that's accurate state.
2. **Worktree husk pending operator cleanup-script** — branch `phase12-bundle-A-schwab-operational-pain` deleted post-merge; on-disk husk at `.worktrees/phase12-bundle-A-schwab-operational-pain/` ACL-locked per all prior-phase precedent. **The cleanup-script's regex (post T-A.4 fix) DOES match `phase12-*` so `-DeregisterFirst` should pick it up cleanly without any manual `git worktree remove --force` workaround.** Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` at convenience.
3. **7-day refresh-token clock** restarted 2026-05-15T03:59:25 UTC during S4; expires ~2026-05-22.

### Cross-references

- Dispatch brief: `docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md` (`892e3e3`).
- Return report: `docs/phase12-bundle-A-return-report.md` (worktree branch).
- Orchestrator-inline gate-fix: `e2c0384` (worktree branch).
- Integration merge: `123d27a`.

### Next dispatch

**Phase 12 Sub-bundle B (auto-correct journal-from-Schwab service) UNBLOCKED.** Per the architectural pivot banked in the 2026-05-15 entry above (top of phase3e-todo). Substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected; operator-paced.

---

## 2026-05-14 Schwab API Sub-bundle D SHIPPED + Phase 11 CLOSED — status surface full + briefing degraded banner + cycle-checklist + CLAUDE.md gotchas + E2E + migration verification + review-form polish (3 Codex rounds; 14 commits; CLOSES THE SCHWAB ARC)

**Sub-bundle D SHIPPED 2026-05-14** at branch tip `cae6e7f` (integration merge to main pending operator-witnessed gate; baseline `23161a0`). 14 commits = 7 task-impl (T-D.1 `9ff7967` status surface; T-D.2 `3f462c8` cycle-checklist; T-D.3 `6aa8f44` E2E; T-D.4 `0cf2ade` CLAUDE.md gotchas; T-D.5 `4b6153e` briefing degraded banner; T-D.7 `7339957` migration verification; T-D.elective.1 `1f30cb3` review-form Phase-7 stale-promise replacement) + 2 pre-Codex review fixes (§J.5 cassette reword `37084bf`; cycle-checklist TTL alignment `edf0e43`) + 5 Codex-fix (R1 M#1+M#2 PROVISIONAL + tokens-parse `a0d618d`; R1 M#3 setup message `0327845`; R1 M#4 docstring `9341fd9`; R1 m#1 cycle-checklist `2703341`; R2 bundled `cae6e7f`).

### Post-merge addendum (orchestrator) 2026-05-15

**Integration merged to main at `e51e6eb`** via `--no-ff` per Sub-bundle B + C precedent (preserves Codex-fix chain visibility). Branch HEAD `6f943db` (return report `6f943db` + Phase 11 SHIPPED entry `9028ab6`); 16 commits since baseline 23161a0 (the implementer count of 14 above omitted the final 2 — return report + this Phase 11 entry).

**Operator-witnessed gate ALL PASS** (5 operator-driven + 4 inline = 9 surfaces):
- S1+S5+S6+S9 inline PASS (3747 fast pass per implementer; T-D.3 E2E + T-D.7 migration atomicity + ruff baseline GREEN).
- **S2 PASS** — `swing schwab status --environment production` rendered LIVE indicator + "expired 2h 30m ago" access token + "6d 20h remaining" refresh token + recent calls (24-28) + masked account_hash (`E8F***76`) + recent errors (8 in 24h, 10 in 7d from C gate's expired-token attempts) + ZERO credential prompt + ZERO token bytes.
- **S3 PASS** — `--environment sandbox` rendered DEGRADED indicator on call 29 (HTTP 401 from C gate); banner predicate fires correctly.
- **S4 PASS** — pipeline #60 + briefing.md emits the degraded banner verbatim per spec §3.4.4: `> **Schwab integration: degraded** — most recent API call to \`marketdata.quotes\` did not succeed. Run \`swing schwab status\` to diagnose.` Banner is GENERIC (no token bytes / no error_message body content) + endpoint-named + remediation hint + Markdown-blockquote-formatted at top of briefing.md.
- **S7 PASS** — cycle-checklist review by operator clean.
- **S8 PASS via template inspection** — `swing/web/templates/partials/review_form.html.j2:67` reads "plan exactly? Auto-derivation from Fills is a future enhancement; manual entry V1." — stale "(Phase 7 will auto-derive this from Fills.)" parenthetical GONE; new phrasing matches brief recommendation verbatim.

**Production state delta from gate** (post-merge):
- `schwab_api_calls`: 29 → 30+ (small delta from S2/S3 status surface NOT writing audit rows — pure read-side; only pipeline #60 which silent-skipped Schwab steps per T-C.6 D1 added zero rows; no new rows expected from D scope).
- Domain rows unchanged (D scope is read-side only).
- `~/swing-data/schwab-tokens.production.db` clock started 2026-05-15T03:59:25+00:00; expires ~2026-05-22.
- `~/swing-data/schwab-tokens.sandbox.db` clock started 2026-05-14T20:30:55+00:00; expires ~2026-05-21.
- D worktree husk: 4th in cleanup-script queue (A + B + C + D pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`).

**Operator-paired-gate brief inaccuracies banked for V2.1 §VII.F amendment routing:**
- Brief §4 surface table referenced `/reviews` route for S8; actual routes are `/reviews/pending` (listing) + `/reviews/{review_id}/complete` (form).
- Brief §0.7 referenced "3 pre-existing failures"; actual baseline is 4 (per Sub-bundle C SHIPPED entry banking; xdist-flaky setup CLI test).

**Operator-reported NEW bug surfaced during S4 gate** — pipeline run errors on missing `data/finviz-inbox/` folder; banked as separate entry above (2026-05-15).

**3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/4M/2m → R2 0C/2M/2m → R3 0C/0M/1m); **ZERO Critical findings** entire chain; **1 ACCEPT-WITH-RATIONALE banked** (R1 M#4 — E2E test scope service-composition-driven not CLI-driven; per-CLI tests already cover the CLI surfaces; banked at return report).

### Test count + style + schema deltas

- **+30 fast tests** (3717 → 3747; brief projected +19; overshoot from R1+R2 defensive coverage + parametrize)
- 3 pre-existing failures unchanged (`tests/integration/test_phase8_pipeline_walkthrough.py`)
- 5 skipped (1 flag-classifier only — baseline preserved)
- Ruff baseline 18 E501 unchanged
- Schema version 18 unchanged (consumer-side; v18 landed by Sub-bundle A); ZERO new schema work in D scope

### Sub-bundle D operator-visible deliverables

1. **`swing schwab status` full per-environment surface** (T-D.1) — three-state determination (CONFIGURED / PROVISIONAL / NOT_CONFIGURED) per environment; refresh-token TTL with severity escalation (≤24hr WARN; ≤2hr ERROR + bold red); recent-call audit summary. R1 M#1 + M#2 restored PROVISIONAL state (narrowly scoped to "tokens DB missing on disk" per R2 M#2) + consults tokens-DB `parse_err` / `refresh_token_issued`. R2 M#1 closed `token_dictionary` bypass; R2 M#2 narrowed PROVISIONAL strictly; R2 m#1 aligned expiry boundary; R2 m#2 refreshed 3-state docstring.
2. **Briefing.md degraded banner** (T-D.5) — emits "Schwab integration: degraded" when most-recent `schwab_api_calls.status != 'success'`. V1 ships banner-only (NOT always-present section per spec §7.2 + cycle-checklist initially claimed; cycle-checklist narrowed post-R1 m#1).
3. **Cycle-checklist updates** (T-D.2) — weekly re-auth reminder + 7-day refresh-token TTL aligned with operator-paired-gate observation (pre-Codex review fix `edf0e43`).
4. **CLAUDE.md gotchas promotion** (T-D.4) — 12 entries (6 brief §3 + 6 plan §J supplementary; §J.5 reworded as V2-PLANNED per spec-review fix). Covers: schwabdev camelCase kwarg discipline; typed `SchwabApiError` audit-row close discipline; `swing schwab setup` clean-state requirement; 7-day refresh-token clock; `Schwabdev` capital-S logger prefix; silent-failure-mode discipline; tokens DB plaintext-at-rest; pipeline-active CLI exclusion; sandbox short-circuit gating; `setLogRecordFactory` content-redaction wrapper; cassette runbook V2-PLANNED; source-artifact reference shape.
5. **E2E happy-path integration test** (T-D.3) — service-composition-driven (NOT CLI-driven per ACCEPT-WITH-RATIONALE R1 M#4); per-CLI tests cover the CLI surfaces.
6. **Migration 0018 BEGIN/COMMIT discipline + manual-backup warning verification** (T-D.7).
7. **Review-form polish (T-D.elective.1)** — replaced stale Phase-7-auto-derive parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67` with forward-looking phrasing per orchestrator default — "Auto-derivation from Fills is a future enhancement; manual entry V1." Closes the 2026-05-13 polish task entry below.

### Schwab arc closer aggregate (4-bundle Phase 11 closure)

| Sub-bundle | Merge SHA | Codex rounds | Commits |
|---|---|---:|---:|
| **A** (foundational) | `5b6e5ba` | 4 | 19 |
| **B** (trader API + snapshot) | `df29232` | 5 + 1 orchestrator-inline gate-fix at `34be84e` | ~24 |
| **C** (market data + cache ladder) | `fd457de` | 5 | 26 |
| **D** (arc-closer; this bundle) | (pending integration merge) | 3 | 14 |

**Arc total: ~17 Codex rounds across 4 bundles; ~83 commits; ZERO Critical findings entire arc.**

**5 ACCEPT-WITH-RATIONALE banked across arc:**
- Sub-bundle A: 1
- Sub-bundle B: 1 (lease status fields V2-deferred)
- Sub-bundle C: 2 (R1 M#5 `_step_charts` ladder V2; R4 M#1 file-level mtime V1 best-effort)
- Sub-bundle D: 1 (R1 M#4 E2E test scope — service-composition vs CLI-driven)

### V2 candidates banked across arc

**Operator-visible Q-deferrals from spec §10:** Q2 token encryption-at-rest (schwabdev `encryption=<key>`); Q3 multi-account support; Q4 WebSocket streaming; Q5 web UI for Schwab integration (status surface only V1); Q6 Schwab inception-CSV ingestion (separate dispatch per phase3e-todo 2026-05-12 entry); Q7 TOS reconciliation deprecation milestone.

**Sub-bundle C return report §7 + Sub-bundle D V2 banks:**

1. `_step_charts` ladder wiring (R1 M#5 from C).
2. `read_or_fetch_archive` Shape A read-path extension.
3. `empty_flag is True` pattern review across other JSON-boolean Schwab response flags.
4. `_yfinance_window_to_shape_a_df` heuristic conversion → explicit fallback contract.
5. Legacy parquet cleanup pass (after all consumers refactor to Shape A).
6. REPLACE-mode `write_window` for explicit archive reset.
7. Per-row `recorded_at` column as freshness signal alternative to filesystem mtime (R4 M#1 family).
8. Pipeline `client_id`/`client_secret` env-var path (T-C.6 D1).
9. `swing schwab setup` self-healing (detect-and-rename stale tokens DB; gotcha #3 candidate from D T-D.4).
10. Briefing always-present "Schwab integration" section (D R1 Minor #1 — currently banner-only).
11. Future Schwab live-test cassette infrastructure + cassette staleness runbook (D T-D.4 §J.5 V2-PLANNED).
12. **(D NEW) `swing config set integrations.schwab.environment` CLI surface** — currently FIELD_REGISTRY doesn't include the env field; operators must hand-edit `user-config.toml` (caught by T-D.2 + adapted CLI message at R1 M#3).
13. **(D NEW) Briefing always-present "Schwab integration" section** — V1 ships banner-only; spec §7.2 + cycle-checklist initially claimed always-present section; cycle-checklist narrowed to banner-only post-R1 m#1.

### Plan-text amendments pending V2.1 §VII.F routing

- ~17 from Sub-bundle A.
- ~5 from Sub-bundle B.
- ~18 from Sub-bundle C.
- **(D NEW) `swing schwab setup` success message wording (R1 M#3)** — plan §I.1 referenced `swing config set integrations.schwab.environment` command which doesn't exist.
- **(D NEW) Refresh-token TTL claim** (90d/7d split → 7d uniform per operator-paired-gate observation 2026-05-14; pre-Codex review fix).
- **(D NEW) E2E test scope wording (R1 M#4)** — plan §Tasks-D T-D.3 said "cassette-driven" but no Schwab cassettes exist; implementation is MagicMock-driven service-composition E2E.
- **(D NEW) PROVISIONAL state narrowed** strictly to "tokens DB missing on disk" per Codex R2 Major #2.
- **(D NEW) Briefing always-present "Schwab integration" section** was specified but ships banner-only V1.

### Production state delta from D scope

- ZERO new domain rows from D operator-witnessed gate surfaces (S2-S8 are inline tests OR read-only operator-driven CLI/filesystem/browser surfaces).
- Operator's Schwab tokens DB clock still on the fresh 7-day cycle from Sub-bundle C gate recovery (refreshed 2026-05-14; expires ~2026-05-21).

### Closure

- Phase 11 (Schwab API integration) **CLOSED** — 4 sub-bundles A → B → C → D all SHIPPED in strict dispatch order.
- **Phase 12+ candidate triage UNBLOCKED** for orchestrator-paced dispatching.
- Worktree teardown: branch `schwab-bundle-D-arc-closer` ready for integration merge to main; on-disk husk will be 4th in operator's cleanup-script queue (after A, B, C still pending per Sub-bundle C SHIPPED entry).

---

## 2026-05-13 Trade exit review form — stale "Phase 7 will auto-derive" promise + counterfactual still operator-input

**Symptom (operator-surfaced 2026-05-13):** trade exit review form's "Counterfactual (optional)" fieldset displays helper text:

> "What R would you have realized if you'd followed your original plan exactly? (Phase 7 will auto-derive this from Fills.)"

Source: [`swing/web/templates/partials/review_form.html.j2:66-67`](../swing/web/templates/partials/review_form.html.j2#L66-L67). The promise is from Phase 6 design (form authored before Phase 7 shipped); Phase 7 SHIPPED 2026-05-05 at `c617777` (per CLAUDE.md status line) but did NOT wire counterfactual auto-derivation. The `realized_R_if_plan_followed` field remains an operator-input column on `trades` (per `swing/data/repos/trades.py:427+445`); only the DOWNSTREAM `mistake_cost_R` + `lucky_violation_R` are derived (per `swing/trades/review.py:158-174`) — but only IF operator manually fills in `realized_R_if_plan_followed`.

**Phase 7 deliverables actually shipped** (per CLAUDE.md status + grep): state machine (`swing/trades/state.py`), origin tracking (`swing/trades/origin.py`), derived-metrics infrastructure (`swing/trades/derived_metrics.py`), Fills first-class (`fills` table + repo). **Counterfactual auto-derivation NOT in scope of any shipped Phase 7 task.**

### Two-part fix candidate

**(a) Immediate polish (trivial; ~5-line change in one template):**

Update `swing/web/templates/partials/review_form.html.j2:66-67` to remove the stale Phase 7 reference. Replace with current-state-honest helper text. Two phrasing options:

- Minimal: drop the parenthetical entirely. Helper text becomes just "What R would you have realized if you'd followed your original plan exactly?"
- Forward-looking: "What R would you have realized if you'd followed your original plan exactly? (Auto-derivation from Fills is a future enhancement; manual entry V1.)"

Operator preference TBD; orchestrator default = forward-looking phrasing (preserves the deferred-derivation intent for future implementer).

**(b) V2 design dispatch (actual auto-derivation):**

Define what "R if plan followed" means when plan-followed conditions can take multiple shapes:
- Trade stopped via violation: counterfactual = R at original planned stop (operator EXITED above-stop manually).
- Trade target hit but operator exited early: counterfactual = R at planned target.
- Trade trailed out: counterfactual = R at planned trail-MA exit.
- Trade closed for non-plan reason: counterfactual = ?

Each scenario needs a deterministic mapping from `Fills` + `trades.planned_*` columns + `trade_events` history → counterfactual R. Likely a new helper in `swing/trades/derived_metrics.py` consuming the existing infrastructure.

**Schwab API arc adjacency:** Schwab API integration may strengthen this — Schwab returns authoritative fill timing/price granular enough to support more sophisticated counterfactual computations (e.g., "R if you had exited at the same intraday timestamp where you actually exited but at the planned-stop price"). Could be V2-bundled with Schwab market-data ladder OR remain standalone.

### Disposition

- **(a) Polish — LOCKED 2026-05-13:** bundled into Schwab API executing-plans **last sub-bundle** (likely Sub-bundle E "polish" per writing-plans dispatch brief §0.7 guidance, but plan author picks final shape; orchestrator threads this task into whichever sub-bundle ships last). **Orchestrator action item:** when writing-plans implementer returns the plan, amend the LAST sub-bundle's executing-plans dispatch brief to include the polish task — update `swing/web/templates/partials/review_form.html.j2:66-67` to drop the stale "(Phase 7 will auto-derive this from Fills.)" parenthetical; replace with forward-looking phrasing per orchestrator default ("Auto-derivation from Fills is a future enhancement; manual entry V1.") OR per operator preference at that triage. NOT added to writing-plans dispatch brief mid-flight (writing-plans implementer dispatched ~2026-05-13 +20min before this triage; mid-flight scope changes cause re-runs).
- **(b) Design** = standalone V2 dispatch (not Schwab-arc-bundled; needs its own brainstorm to lock the counterfactual semantics across stopped/target/trailed/non-plan exit shapes). Operator-paced.

### Cross-references

- Phase 6 source-of-promise: `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md`.
- Phase 7 actual deliverables: `swing/trades/state.py` + `swing/trades/derived_metrics.py` + migration `0014_phase7_state_machine_and_fills.sql`.
- Existing manual-entry consumer: `swing/trades/review.py:158-174` (`compute_mistake_cost_R` + `compute_lucky_violation_R`).

---

## 2026-05-14 Schwab API Sub-bundle C SHIPPED — Market Data API + Shape A cache ladder + PriceCache/OhlcvCache integration + sandbox short-circuit + --verify-marketdata CLI + cross-bundle pin closure (5 Codex rounds; 26 commits; LARGEST NOVEL SCOPE of the arc)

**Sub-bundle C SHIPPED 2026-05-14** at `fd457de` (integration merge of `schwab-bundle-C-marketdata-and-cache-ladder` worktree branch via `--no-ff` to preserve Codex-fix chain per Sub-bundle B precedent at `df29232`). Branch HEAD `88267fd` (26 commits = 1 recon + 7 task-impl + 17 Codex-fix + 1 return-report). Operator-dispatched implementer per orchestrator brief at `8356b34`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0/6/2 → R2 0/2/2 → R3 0/1/2 → R4 0/1/2 → R5 0/0/2); **ZERO Critical findings** entire chain; **2 ACCEPT-WITH-RATIONALE banked** (R1 M#5 `_step_charts` ladder wiring V2; R4 M#1 file-level mtime V1 best-effort awaiting V2 per-row `recorded_at` column); 8 Major resolved with code-content fixes + discriminating regression tests.

### Operator-paired live gate (Option A; 2026-05-14)

Full S2-S5 live verification against operator's production-tier Schwab account + worktree-side inline S1+S6+S7+S8+S9 PASS:

| Surface | Result | Key observation |
|---|---|---|
| S1 fast suite (worktree) | ✅ | 3713 passed; 4 pre-existing failures (3 Phase 8 walkthrough + 1 xdist-flaky setup CLI test); 5 skipped. **Main-HEAD post-merge:** 3717 passed; 3 failed (Phase 8 walkthrough only; xdist-flaky setup test passed this time); 1 skipped (only flag-classifier) — both cross-bundle pins (T-C.5 + T-C.7) un-skipped + GREEN. |
| S2 `--verify-marketdata` prod | ❌→✅ post-recovery | First attempt failed: 7-day refresh-token expired (anticipated per dispatch brief §0.7). Recovery via `logout → setup` paste-back. Re-run: calls 27 (`marketdata.quotes` AAPL) + 28 (`marketdata.pricehistory` AAPL bars=23) BOTH success / HTTP 200 / signature_hash present / linked_* NULL ✓. **First live Schwab Market Data API success in production.** |
| S3 `--verify-marketdata --environment sandbox` | ✅ via demonstration | Stale sandbox tokens DB triggered same auto-refresh failure → call 29 audit landed with `status='error'` / `http_status=401` / redacted `error_message` (no token bytes) + ZERO new domain rows. **Production-only-domain-writes contract per spec §3.6.3 holds even on auth failure.** |
| S4 `swing pipeline run` (production env) | ✅ | Pipeline run #58 complete in 47s. Per T-C.6 D1 ACCEPT-WITH-RATIONALE: `_construct_pipeline_schwab_client` returned `None` (cfg has no `client_id`/`client_secret`) → both Sub-bundle B's snapshot/orders steps + Sub-bundle C's ladder warming silent-skipped per Sub-bundle B M#1 surface-aware advisory pattern. ZERO new `schwab_api_calls` rows from pipeline; ZERO domain-row deltas. **V1-shipped behavior; V2 enhancement banked.** |
| S5 backward-compat copy-not-move | ✅-with-inspection-only | V1 ladder silent-skip (S4) blocks live trigger of `_backward_compat_rename`. Archive at `~/swing-data/prices-cache/` has 776 legacy `{TICKER}.parquet` files; ZERO Shape A files yet. T-C.2 unit tests (+18) cover Shape A persistence + backward-compat-rename comprehensively (R1 M#6 + R2 M#1 + R2 M#2 + R3 M#1 + R4 M#1 fixes all landed discriminating regression coverage). |
| S6 sentinel-leak audit Bundle C | ✅ | `tests/integrations/test_schwab_token_redaction_audit.py` GREEN; un-skipped Market Data API portions covered + 2 NEW tests using `MagicMock.side_effect` emitting Schwabdev-logger sentinels FROM INSIDE actual `quotes`/`price_history` calls (R1 M#6 fix discriminating against pre-fix BEFORE-the-call pattern). |
| S7 `SchwabPipelineActiveError` exclusion | ✅ | `test_b6_10_fetch_verify_marketdata_NOT_protected` un-skipped at T-C.5 + GREEN. |
| S8 E2E pipeline production-only gate | ✅ | Bundle B suite unchanged by C (cache-layer integration does NOT regress). |
| S9 ruff baseline | ✅ | 18 E501 unchanged. |

**Sub-bundle C is operationally validated end-to-end against live Schwab Market Data API in production.** First live `marketdata.quotes` + `marketdata.pricehistory` calls; first Shape A parquet-per-(ticker, provider) persistence layer + ladder fetcher infrastructure.

### Anticipated failure: 7-day refresh-token recovery sequence

S2 attempt 1 failed exactly per dispatch brief §0.7 prediction (7-day clock from Sub-bundle A phase-2 OAuth setup expired). Recovery sequence:

1. `swing schwab refresh` — failed (refresh attempted but operator's refresh_token is dead).
2. `swing schwab setup` — **also failed** (auto-refresh fires on stale tokens DB before paste-back; bails out hard with `unsupported_token_type`).
3. `swing schwab logout` — atomically renamed `~/swing-data/schwab-tokens.production.db` → `*.deleted-20260514T175833` (24h recovery window) per A T-A.5 design even though revoke best-effort failed.
4. `swing schwab setup` against now-empty path — clean paste-back; same `hashValue=E8F...0676` auto-selected; fresh 7-day clock started.

**NEW gotcha-promotion candidate (Sub-bundle D T-D.4):** `swing schwab setup` requires clean tokens DB state; auto-refresh fires on stale tokens DB and bails before paste-back code path. Recovery sequence is `logout → setup`, NOT `setup` standalone. **Possible V2 self-healing:** make `setup` detect-and-rename stale tokens DB itself.

### Three highest-leverage SHIPPED deliverables

1. **Market Data API endpoint methods** at `swing/integrations/schwab/marketdata.py` (646 lines; `get_quotes_batch` + `get_price_history` + 4 helpers + `_call_endpoint` shared wrapper). camelCase kwarg trap (B's `34be84e` defect family) PRE-EMPTED via `inspect.signature(schwabdev.Client.price_history)` discriminating test landing in T-C.1 BEFORE code; ZERO defects of that family caught by Codex chain.
2. **OHLCV archive Shape A persistence** at `swing/data/ohlcv_archive.py` (extended +500 lines): `write_window` empty-window-guard + `resolve_ohlcv_window` window-filter + `_backward_compat_rename` 4-case copy-not-move (R2 M#1) with both-files-exist merge-and-quarantine + mtime-based freshness winner (R3 M#1) with nanosecond-precision (R4 m#2). 1512-line test file at `tests/data/test_ohlcv_archive_shape_a.py` covers ALL Codex-caught edge cases.
3. **Market-data ladder fetcher** at `swing/integrations/schwab/marketdata_ladder.py` (455 lines; `fetch_quote_via_ladder` + `fetch_window_via_ladder` + 7 helpers). Sandbox short-circuit per spec §3.6.3 + §H.6.1; yfinance fallback discipline preserved; per-provider tagging through `provider` field on `PriceSnapshot` (NOT plan's hypothetical `PriceCacheEntry` class — actual class name preserved per T-C.4 D1).

### High-leverage Codex fixes worth flagging at integration triage

- **R1 M#1:** `_backward_compat_rename` not wired into ladder hot path — fixed in `1a5e099`.
- **R1 M#3:** Schwab bars NOT persisted to Shape A archive — fixed in `700265c` (write-side) + R3 M#1 / R4 M#1 partial wiring on read-side (chart step deferred V2).
- **R1 M#6:** Sentinel-leak audit tests stubbed sentinels OUTSIDE schwabdev call (would silently pass even without redaction) — fixed at `3663d2c` with `MagicMock.side_effect` pattern.
- **R2 M#1:** Backward-compat rename should COPY-NOT-MOVE the legacy parquet (preserve operator's V1 reads via legacy path) — fixed at `26efbae`.
- **R3 M#1 / R4 M#1:** mtime-based freshness winner for both-files-exist merge — banked as V1 best-effort + V2 candidate #7 (per-row `recorded_at` column closes both staleness + rollback failure modes).

### 2 ACCEPT-WITH-RATIONALE family

1. **R1 M#5** (`_step_charts` ladder wiring V2): chart step still uses legacy `read_or_fetch_archive` path (does NOT consult Shape A files); full wiring requires `fetcher.get()` refactor + weekly-refresh + archive_history_days reconciliation. V1 behavior unchanged for chart-step downstream consumers; ladder ships persistence infrastructure + V2 read-path extension closes the loop.
2. **R4 M#1** (file-level mtime as row-level conflict signal V1 best-effort): coarse signal for fine-grained question. V2 per-row `recorded_at` column closes both directions. V1 impact bounded — `read_or_fetch_archive` consumers read legacy directly; Shape A merge state does NOT affect their reads.

### Production state delta (post-gate)

- `schwab_api_calls`: 17 → **29** (+12 net: failed pre-recovery attempts at calls 18-26 + S2 success calls 27+28 + S3 sandbox auth-failed call 29). All audit rows correctly classified per Sub-bundle B M#3 typed-SchwabApiError discipline.
- `account_equity_snapshots`: **5 unchanged** (no Schwab snapshot writes from V1 pipeline; B-shipped step silent-skipped per T-C.6 D1).
- `reconciliation_runs`: **9 unchanged** (no Schwab orders reconciliation from V1 pipeline; same path).
- `reconciliation_discrepancies`: **38 unchanged**.
- `~/swing-data/prices-cache/`: 776 legacy `{TICKER}.parquet` files unchanged; ZERO Shape A files yet (V1 ladder silent-skip blocks live trigger).
- Tokens DB: fresh 7-day clock started 2026-05-14 (post `logout → setup` recovery).

### NEW gotcha-promotion candidates (Sub-bundle D T-D.4 candidates)

1. **`swing schwab setup` requires clean tokens DB state** (operator-witnessed gate finding) — see "Anticipated failure" section above.
2. **schwabdev camelCase kwarg discipline reinforced** — Sub-bundle B's gate-caught defect (`account_orders(maxResults=...)`) was the precedent; Sub-bundle C pre-empted via `inspect.signature` discriminating test on `Client.price_history`. Both belong in CLAUDE.md.
3. **Pre-existing flaky test baseline correction** — `test_setup_auth_failure_audit_status_and_sentinel_redaction` (Sub-bundle A's T-A.4 setup CLI suite) is xdist-flaky and confirmed pre-existing on main `8356b34` (deterministic-fails serial too). Brief §0.7 said "3 pre-existing failures" — actual is **4**. Doc correction; not a regression.

### V2 candidates banked (7)

Per return report §7.2:

1. `_step_charts` ladder wiring (R1 M#5 follow-up).
2. `read_or_fetch_archive` Shape A read-path extension.
3. `empty_flag is True` pattern review across other JSON-boolean Schwab response flags.
4. `_yfinance_window_to_shape_a_df` heuristic conversion → explicit fallback contract.
5. Legacy parquet cleanup pass (after all consumers refactor to Shape A).
6. REPLACE-mode `write_window` for explicit archive reset.
7. Per-row `recorded_at` column as freshness signal alternative to filesystem mtime.

Plus pipeline `client_id`/`client_secret` env-var path for V2 (T-C.6 D1).

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **Sub-bundle A + B + C worktree husks pending operator cleanup-script** — branches A + B + C all deleted post-merge; on-disk husks at `.worktrees/` ACL-locked. **C is 3rd in cleanup-script queue.** Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (elevated PowerShell) at convenience.
2. **Refresh sandbox tokens DB** (optional V2 work) — sandbox path has stale tokens; `swing schwab fetch --verify-marketdata --environment sandbox` will continue to surface auth-failure-with-correct-discipline until refreshed via paste-back.
3. **8 material discrepancies from Sub-bundle B's gate — ALL RESOLVED** (operator action 2026-05-14 → 2026-05-15: 7 resolved as `journal_corrected` during D-gate window — DHC 9-share trim recorded as fill + VSAT/CVGI/DHC entry-prices corrected — + 1 final stale-re-emission cleanup at disc 37 post-D-merge per VSAT entry-price companion to disc 33). Final state: 30 `acknowledged_immaterial` + 8 `journal_corrected` + 0 `unresolved`. Phase 10 dashboard banner now clear.

### Cross-bundle pin status

**ZERO cross-bundle pins remaining for Sub-bundle D.** Both T-C.5 (`test_b6_10_fetch_verify_marketdata_NOT_protected`) + T-C.7 (Market Data API sentinel-coverage) un-skipped at branch tip + GREEN.

### 18 plan-text deviations banked (V2.1 §VII.F amendment candidates)

Per return report §5: 8 cosmetic + 6 architectural + 4 scope. Includes:
- T-C.1 D3: `_finish_hook` parameter on marketdata `_call_endpoint` (architectural — supports quotes partial-response audit messaging).
- T-C.2 D1: `cache_dir` kwarg threading (matches existing `read_or_fetch_archive` API).
- T-C.3 D2: ladder signatures take `conn` + `surface` kwargs.
- T-C.4 D1: cache layer uses INJECTABLE FETCHER HOOK pattern (rationale: keeps cache env-agnostic; avoids fixture-rewrite cascades).
- T-C.5 D1: sandbox-vs-production interpretation (b) — both envs invoke schwabdev; orchestrator-decision pending Sub-bundle D `swing schwab status` revisit.
- T-C.6 D1: pipeline `_construct_pipeline_schwab_client(cfg)` returns `None` (cfg lacks credentials; V1 graceful degradation).

Plus 5 plan-text deviations from T-C.0.b recon (§A camelCase / §B datetime permissiveness / §C `PriceCacheEntry`→`PriceSnapshot` / §D archive path / §E `OhlcvCacheEntry` existence).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle C executing-plans dispatch brief: `docs/schwab-bundle-C-marketdata-and-cache-ladder-executing-plans-dispatch-brief.md` (`8356b34`).
- Sub-bundle C return report: `docs/schwab-bundle-C-return-report.md` (`88267fd`).
- Sub-bundle C T-C.0.b recon doc: `docs/schwab-bundle-C-task-C0b-recon.md` (`9d1e3e4`).
- Integration merge: `fd457de`.
- Branch HEAD: `88267fd`.

### Next dispatch

**Sub-bundle D executing-plans dispatch UNBLOCKED.** D closes the Schwab arc. Operator-paced. Brief drafting MUST consume:
1. Sub-bundle C return report §9 (5 NEW forward-binding lessons): camelCase signature pinning; dual empty-signal defense-in-depth; injectable fetcher hook architectural pattern; mtime-based freshness V1 best-effort; `construct_authenticated_client` requires sensitive secrets NOT in cfg (V1 pipeline silent-skip).
2. Sub-bundles A + B + C cumulative forward-binding lessons (still BINDING).
3. Plan §Tasks-D at line 2214+ (7 tasks T-D.1..T-D.7; +19 fast tests projected; 2-3 Codex rounds estimated; smallest sub-bundle of the arc).
4. **3 NEW gotcha-promotion candidates** banked above for T-D.4.
5. Review-form polish task (drop stale "(Phase 7 will auto-derive...)" per phase3e-todo 2026-05-13 entry).
6. 7-day refresh-token expiry alert design + `unsupported_token_type` recovery surface design per spec §3.5.
7. `reference/schwabdev/api-calls.md` already pre-checked for all V1 wrappers — no live verification expected at T-D.x.

---

**Sub-bundle B SHIPPED 2026-05-14** at `df29232` (integration merge of `schwab-bundle-B-trader-and-snapshot` worktree branch via `--no-ff` to preserve Codex-fix chain). Branch HEAD `34be84e` (11 commits = 10 implementer + 1 orchestrator-inline gate-caught fix). Operator-dispatched implementer per orchestrator brief at `19622b6`.

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR**; **0 Critical / 15 Major** (14 resolved + 1 ACCEPT-WITH-RATIONALE family — see below); +92 fast tests projected by implementer (will land closer to +94 with the 5 added orchestrator gate-fix tests).

### Operator-paired live gate (Option A; 2026-05-14)

Full S2-S5 live verification against operator's production-tier Schwab account:

| Surface | Result | Key observation |
|---|---|---|
| Refresh (bonus A.S4 close) | ✅ | Call 5 `auth_failed` + call 6 `success` retry — honest audit log |
| S2 `--snapshot` prod | ✅ | **First live source-ladder write**: snapshot_id=4 / NLV $2034.78 / `source='schwab_api'` / `schwab_account_hash` populated / call_id=7 |
| S3 `--orders` prod | ❌→✅ post-fix `34be84e` | Caught real defect (see below); reconciliation_run_id=8 with 4 real material discrepancies |
| S4 `--all` prod | ✅ | snapshot_id=5 / NLV $2036.04 / `snapshot_date` rolled to 2026-05-14 between S2 and S4; **same-day-replay UPSERT path NOT exercised live** (cassette unit test covers); reconciliation_run_id=9 with same 4 discrepancies re-emitted |
| S5 `--snapshot --environment sandbox` | ✅ | call_id=17 / `environment='sandbox'` / `linked_snapshot_id=NULL` / **ZERO new domain rows** — production-only domain writes per spec §3.6.3 verified |

**Sub-bundle B is operationally validated end-to-end against live Schwab Trader API in production.** First Schwab API write to source-ladder; first Schwab-sourced reconciliation_run; first sandbox-gating verified.

### Gate-caught defect + orchestrator-inline fix (commit `34be84e`)

**Defect:** trader.py:362 used snake_case `max_results=max_results` but schwabdev 2.5.1 `Client.account_orders` signature uses camelCase `maxResults=`. Cassette tests didn't catch because they stub the entire schwabdev call (any kwargs accepted).

**Audit + degradation worked correctly** per Sub-bundle A T-A.9 typed-SchwabApiError discipline + R1 M#3 audit-success-fire ordering — both error rows landed with `status='error'`, `http_status=None`, error_message redact-truncated. The defect was JUST the kwarg name.

**Fix:** rename to `maxResults=max_results` + 5 NEW discriminating tests at `tests/integrations/test_schwab_trader_kwarg_signatures.py`:
- `test_account_linked_no_kwargs_required` — pins zero-param signature.
- `test_account_details_kwargs_match_schwabdev` — pins `{accountHash, fields}`.
- `test_account_orders_kwargs_match_schwabdev` — pins `{accountHash, fromEnteredTime, toEnteredTime, maxResults, status}` — the post-fix camelCase.
- `test_transactions_kwargs_match_schwabdev` — pins `{accountHash, startDate, endDate, types, symbol}`.
- `test_no_snake_case_kwarg_in_trader_calls` — source-level grep regression defense.

Other 3 trader methods cross-checked + already correct: `account_linked()` no-kwargs; `account_details(account_hash, fields=fields)` where 'fields' matches; `transactions(...)` all positional + `symbol=symbol` matches. **ONLY `account_orders` had the camelCase mismatch.** Skip Codex re-review (mechanical fix; 5-test discipline pin substitutes).

### Three highest-leverage SHIPPED deliverables

1. **Trader API endpoint methods** at `swing/integrations/schwab/trader.py` (4 methods + mappers + models): `get_accounts_linked` / `get_account_details` / `get_account_orders` / `get_account_transactions`. Each wrapped via `_call_endpoint` with audit-row INSERT-then-UPDATE lifecycle from Sub-bundle A T-A.9.
2. **Pipeline steps** at `swing/integrations/schwab/pipeline_steps.py`: `_step_schwab_snapshot` (production-only via spec §3.6.3 gate) + `_step_schwab_orders` (calls trader methods + invokes new `run_schwab_reconciliation` service). Wired into `swing/pipeline/runner.py` AFTER `_step_recommendations` BEFORE `_step_charts`.
3. **`run_schwab_reconciliation` service** at `swing/trades/schwab_reconciliation.py`: mirrors Phase 9 Sub-bundle B `run_tos_reconciliation` shape; reuses `MATERIAL_BY_TYPE` lookup + 5 discrepancy types verbatim; failure-path PRESERVES run row (UPDATE state='failed' per spec §3.3.3).

### High-leverage Codex fixes worth flagging at integration triage

- **R1 M#3:** typed `SchwabApiError` audit-row close discipline (`auth_failed`/`rate_limited`/`error` classification before re-raise) — NEW gotcha family.
- **R1 M#7:** single-Client-instance discipline enforced via new `construct_authenticated_client()` in `auth.py` (cli_schwab now delegates).
- **R1 M#8:** same-day account_hash-flip guard (refuses on differing non-NULL hash).
- **R2 M#1:** pipeline-internal silent-skip (log only, NO audit row) for `client=None` — diverges from CLI surface which writes advisory rows.
- **R5 M#1:** CLI fetch preflight account_hash check before credentials prompt.

### 1 ACCEPT-WITH-RATIONALE family (R2 M#2 + R3 M#2)

**Lease status fields deferred to V2.** Bundle B's ZERO-new-schema scope precluded adding a dedicated `schwab_step_status` lease column; audit row status + `lease.step()` breadcrumb sufficient for V1. Banked for V2.

### Production state delta (post-gate)

- `schwab_api_calls`: 4 → **17** (+13 net: 1 success + 1 auth_failed + 1 success refresh + 1 success snapshot + 2 error orders + 3 success orders re-run + 4 success --all + 1 success sandbox)
- `account_equity_snapshots`: 3 → **5** (+2: snapshot_id=4 NLV $2034.78 / snapshot_date='2026-05-13'; snapshot_id=5 NLV $2036.04 / snapshot_date='2026-05-14'; both `source='schwab_api'`, both `schwab_account_hash` populated)
- `reconciliation_runs`: 7 → **9** (+2: runs 8+9 both `source='schwab_api'`, both `schwab_api_call_id` populated, 7-day windows shifted by 1 day)
- `reconciliation_discrepancies`: 30 → **38** (+8 NEW: 4 each on runs 8+9, same shape — DHC `position_qty_mismatch` + DHC `unmatched_open_fill` + VSAT `entry_price_mismatch` + CVGI `entry_price_mismatch`)

### ⚠ 4 unresolved material discrepancies pending operator triage (with operator-supplied explanations)

These are **real broker-vs-journal divergences** the system surfaced against operator's actual Schwab account (NOT bugs — Phase 9 emit machinery working as designed). Will appear on the dashboard's reconciliation banner per Phase 10 Sub-bundle E T-E.3. Operator-supplied explanations 2026-05-14:

- **DHC `position_qty_mismatch`** + **DHC `unmatched_open_fill`** (rows on runs 8 + 9): operator sold 9 shares today (2026-05-14) as ~25% position reduction (sell into strength). **NOT YET in journal — expected divergence.** Operator-action sequence: (1) record the trim fill via journal CLI; (2) resolve discrepancies as `mistake_corrected`. Sub-bundle B reconciliation correctly surfaced the journal-lag-behind-broker state.
- **VSAT `entry_price_mismatch`** + **CVGI `entry_price_mismatch`** (rows on runs 8 + 9): probably off by ~$0.01; **journal entry-price misreading mistake** (operator misread actual purchase price at original journal entry). Operator-action sequence: (1) update entry price in journal to match Schwab broker record; (2) resolve discrepancies as `mistake_corrected`.

**8 row IDs total / 4 distinct issues / 2 root causes** (1 NEW operator action not yet journaled + 1 OLD journal-entry-data mistake). All 4 represent EXACTLY the kind of operational signal the source-ladder + reconciliation system was built to surface — Sub-bundle B is doing its job. Resolution is operator-action via journal CLI + `swing journal discrepancy resolve <id> --resolution=mistake_corrected --reason="..."`.

### NEW gotcha-promotion candidate (Sub-bundle D T-D.4 candidate)

**schwabdev camelCase parameter names vs project snake_case convention.** schwabdev uses `accountHash`, `fromEnteredTime`, `toEnteredTime`, `maxResults`, `startDate`, `endDate`, etc. — project convention is snake_case throughout. Wrapper kwargs MUST match schwabdev's camelCase exactly OR they fail at runtime with `TypeError: got an unexpected keyword argument`. Sub-bundle A's lesson #5 ("schwabdev 2.5.1 actual surfaces") covered response shapes but missed this kwarg-naming dimension; B's gate exposed it. **CLAUDE.md gotcha promotion at Sub-bundle D T-D.4:** discriminating-test pattern is to pin every wrapper's kwarg names against `inspect.signature(schwabdev.Client.X)` (Sub-bundle B established the pattern at `tests/integrations/test_schwab_trader_kwarg_signatures.py`); replicate for any future schwabdev wrapper additions.

### NEW V2 candidate banked

**Credential entry UX** (`SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` env-var fallback OR session-cached prompt OR `--client-id` / `--client-secret` CLI flags). Operator prompted for `client_id` + `client_secret` on every CLI invocation in the gate session — by Sub-bundle A T-A.2 design (security posture; not in cfg cascade). Acceptable for V1 but friction-heavy for ops use. Matches Q2 V2 token encryption hardening family.

### Same-day-replay-provenance live-validation deferred

Sub-bundle B same-day-replay-provenance test (plan T-B.3 + T-B.4 R3 Major #4 ACCEPT-WITH-RATIONALE family) pins UPSERT-preserves-snapshot_id + LATEST-writer-wins-source_artifact_path semantics. Live gate (S2 + S4) didn't exercise this path because `last_completed_session(now())` rolled from 2026-05-13 to 2026-05-14 between S2 (12:30 PM PT) and S4 (1:27 PM PT) — `(snapshot_date, source)` UNIQUE INDEX correctly inserted a NEW row instead of UPSERTing. **Cassette unit test in T-B.3 stubs dates to force the same-day path; provenance discipline still locked at unit-test level.** Note for operator: date-resolution semantics may surprise — both gate snapshots resolved to different sessions during your active market hours; worth verifying the `last_completed_session` cutoff if it surprises you.

### Cross-bundle pin status

T-B.8 cross-bundle pin un-skipped at branch-tip (Trader API portion of sentinel-leak audit). 1 cross-bundle pin remaining (T-C.7 Market Data API portion).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle B executing-plans dispatch brief: `docs/schwab-bundle-B-executing-plans-dispatch-brief.md` (`19622b6`).
- Sub-bundle B return report: `docs/schwab-bundle-B-return-report.md` (`0124a76`).
- Sub-bundle B T-B.0.b recon doc: `docs/schwab-bundle-B-task-B0b-recon.md`.
- Orchestrator-inline gate-fix: `34be84e` (trader.py:362 maxResults camelCase + 5 discriminating tests).
- Sub-bundle C executing-plans dispatch brief: TBD (orchestrator drafts; operator-paced).

### Next dispatch

**Sub-bundle C executing-plans dispatch UNBLOCKED.** Operator-paced. Brief drafting MUST consume:
1. Recon doc §6 + §6.bis as binding LOCKED inputs.
2. Sub-bundle A's 5 forward-binding lessons (still BINDING for C).
3. Sub-bundle B's NEW lessons (camelCase kwarg discipline + R1 M#3 typed-SchwabApiError audit-row close + R1 M#7 single-Client-instance via construct_authenticated_client + R1 M#8 same-day account_hash-flip guard + R2 M#1 pipeline-internal silent-skip vs CLI advisory rows + R5 M#1 CLI preflight account_hash check).
4. `reference/schwabdev/api-calls.md` pre-check for Market Data API method-name + signature pre-answers (Q12 + Q17 likely pre-answerable).
5. `reference/schwab-api/market-data-{documentation,specification}.md` Schwab Developer Portal canonical docs.
6. Cross-bundle pin (un-skip at T-C.7).

---

## 2026-05-14 Schwab API Sub-bundle A SHIPPED — schwabdev wrap + auth + migration 17→18 + audit infrastructure (4 Codex rounds; 19 commits; phase-2 live OAuth executed end-to-end against production)

**Sub-bundle A SHIPPED 2026-05-14** at `5b6e5ba` (integration merge of `schwab-bundle-A-foundational` worktree branch — preserved Codex-fix chain via `--no-ff` per operator note). Operator-dispatched implementer per orchestrator brief at `bd166c5`. Branch HEAD `6550494` (19 commits = 11 task-impl + 1 hotfix bdf82da + 1 phase-2 addendum + 3 Codex-fix + 1 cleanup-script-help-escape + 1 return-report).

**4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent shape (R1 0C/5M → R2 0C/1M/1m → R3 0C/1M/1m → R4 0C/0M); **ZERO Critical findings**; **1 ACCEPT-WITH-RATIONALE banked** (R2 Minor #2 `force_refresh` unchanged-token integrity check per plan §H.2 step 6 — operator-facing error already distinguishes "<not rotated>" from "<raised>").

### Three highest-leverage SHIPPED deliverables

1. **Schema migration 17 → 18** (T-A.7) with file-level explicit `BEGIN;`/`COMMIT;` discipline per plan §C.4 — `schwab_api_calls` table (14 columns + 4 indexes + 3 FKs `ON DELETE SET NULL`) + ALTER `account_equity_snapshots.schwab_account_hash TEXT NULL` + ALTER `reconciliation_runs.schwab_api_call_id INTEGER NULL`. Counter-example test locks the discipline (canonical-minus-BEGIN-fixture FAILS rollback). **Forward-binding for migrations 0019+** until runner is updated.

2. **Three-layer token redactor** (T-A.10): Layer 0 known-secret exact-replace from process-global registry (5 long-lived slots: client_id/client_secret/access_token/refresh_token/account_hash) + Layer 1 heuristic regex (hex 32+ / base64 24+) + Layer 2 `logging.setLogRecordFactory()` with recursion guard + factory-replacement defense via `ensure_*` re-wrap. **Logger prefix `"Schwabdev"` (capital S — live schwabdev 2.5.1 deviation from plan §H.8 lowercase)**. R7-R10 chain hardenings encoded with discriminating tests. Cross-bundle pins added for B/C surfaces (`@pytest.mark.skip(reason='un-skip at T-B.8 + T-C.7')`).

3. **`swing/integrations/schwab/` sub-package** with composition over `schwabdev.Client`: 8 typed exception classes; `_suppress_transport_debug_logs` covering 4 transport-debug loggers; audit-service caller-held-tx-rejecting transactional wrappers (`record_call_start`, `record_call_finish`, `link_snapshot_and_stamp_account_hash` combined-tx2, `link_reconciliation_run`).

### CLI subcommands SHIPPED

`swing schwab {setup, refresh, logout, status}` with audit lifecycle wrapping; pipeline-active exclusion (`--force` overrides on setup/logout; refresh has NO `--force` per Codex R1 Minor #3 concurrent-safe); schema-check-fail-fast (T-A.4 hotfix `bdf82da` from phase-2 findings); server-stamped audit timestamps; `account_hash` masking via FIELD_REGISTRY (first-3 + `***` + last-2).

### Phase-2 live verification (2026-05-14; operator-paired end-to-end against production)

OAuth paste-back flow executed end-to-end against operator's production-tier Schwab Developer Portal app:
- Tokens DB persisted at `~/swing-data/schwab-tokens.production.db` (957-byte JSON despite `.db` extension; valid access + refresh tokens).
- 64-char `account_hash` auto-picked from `client.account_linked()` + cfg-cascade-written to `~/swing-data/user-config.toml` `[integrations.schwab].account_hash`.
- 4 production `schwab_api_calls` rows: 2 corrected to `status='auth_failed'` via `scripts/fix_phase2_misleading_audit_rows.py` (idempotent; safe to re-run) + 2 `status='success'`.
- **7-day refresh-token clock started 2026-05-14** — operator must re-auth by ~2026-05-21 per recon §2.11 (will be threaded into Sub-bundle D status alert design + cycle-checklist update + CLAUDE.md gotcha promotion).

### Tests + ruff + schema deltas

- Tests: ~3287 baseline → expected ~3413 main HEAD (+126 net per return report §3; pending fast-suite run completion to confirm).
- Ruff: 18 E501 unchanged.
- Schema: v17 → **v18** (verified `EXPECTED_SCHEMA_VERSION=18` post-merge).

### Operator-witnessed verification gate state

Per dispatch brief §3 + return report §4:

- **S1 pytest fast-suite** PASSED (Codex required green to converge across 4 rounds).
- **S2 Migration 0018 lands cleanly** PASSED via phase-2 live verification (production swing.db migrated successfully; `schwab_api_calls` table + 2 ALTERs verified).
- **S3 `swing schwab setup` paste-back** PASSED via phase-2 live verification (end-to-end against operator's production-tier app; tokens DB persisted; `account_hash` cfg-cascade-written).
- **S4 `swing schwab refresh`** NOT EXPLICITLY DRIVEN — operator-elective (return report notes code-path coverage may be sufficient OR drive at follow-up gate session).
- **S5 `swing schwab status` skeleton** NOT EXPLICITLY DRIVEN — same operator-elective.
- **S6 `swing schwab logout`** NOT EXPLICITLY DRIVEN — same operator-elective.
- **S7 Sentinel-token-leak audit** PASSED inline (24 assertions per T-A.10 GREEN).
- **S8 ruff baseline** PASSED inline (18 E501 unchanged).

### 13 V2.1 §VII.F amendment candidates banked

8 recon-doc-banked plan deviations (§5.1) + 5 NEW Codex-chain deviations (§5.2). Cumulative pending arc total: **40** entering Sub-bundle B (was 27 at Phase 10 close + 13 from this dispatch). Detailed in return report §5.

### 5 forward-binding lessons for Sub-bundle B (return report §8)

1. **schwabdev's silent-failure-mode discipline** — `Client.__init__` + `update_tokens()` do NOT raise on auth failure; they print + retry + return silently. Wrappers MUST verify post-call state (`client.tokens.access_token` populated + rotated). Discriminating-test pattern: stub schwabdev call to NOT mutate `tokens.access_token`; assert wrapper raises `SchwabAuthError` + audit row `status='auth_failed'`.
2. **Audit-success-fire ordering** — `record_call_finish(status='success', ...)` MUST fire ONLY after all validation passes (R1 M#3 family). Pattern: validate response shape → validate response content → validate operator-pickable state → fire success audit. Each pre-success rejection path fires `record_call_finish(status='auth_failed')` with redacted `error_message` + raises.
3. **Pre-call factory-replacement defense** — `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev API call. Discriminating-test pattern: install third-party factory between two schwab calls; assert second call re-wraps the factory before invoking schwabdev.
4. **Redact-then-truncate audit-error ordering** — `_redacted_excerpt` MUST redact on FULL `str(exc)` THEN truncate to audit-column-budget. Discriminating-test pattern: register a sentinel that straddles the truncation boundary; assert no partial-prefix survives.
5. **schwabdev 2.5.1 actual surfaces** (banked from phase-2 live verification):
   - `Client` ctor: 8 params (`app_key, app_secret, callback_url='https://127.0.0.1', tokens_file='tokens.json', timeout=10, capture_callback=False, use_session=True, call_on_notify=None`).
   - Tokens DB content: **JSON (NOT SQLite)**; content shape `{access_token_issued, refresh_token_issued, token_dictionary: {access_token, refresh_token, id_token, expires_in: 1800, token_type, scope}}`.
   - `client.account_linked()` success: list of dicts `[{accountNumber, hashValue}, ...]`.
   - `client.account_linked()` failure: dict error envelope (NOT a list).
   - Force-refresh kwarg: `client.update_tokens(force_access_token=True)` (NOT `force_refresh_token=True` which triggers full OAuth dance).
   - Schwab `code` expiry window: ~30 seconds from redirect.
   - Logger name: `"Schwabdev"` (capital S).
   - NO `revoke()` method exposed; use manual `POST /v1/oauth/revoke` (Basic auth + `token=<refresh_token>&token_type_hint=refresh_token` form body).

### Production state post-merge (per return report §6 #4)

- Schema: **v18**.
- 4 rows in `schwab_api_calls` (2 corrected-to-auth_failed + 2 success).
- `~/swing-data/schwab-tokens.production.db` exists (JSON, 957 bytes; valid access + refresh tokens).
- `~/swing-data/user-config.toml` has `[integrations.schwab].account_hash` = 64-char `hashValue`.
- 7-day refresh-token clock started 2026-05-14 (operator must re-auth by ~2026-05-21).

### Post-merge housekeeping items

1. **`pip install -e .` shim rebuild — COSMETIC only; post-merge code already reachable.** Per return report §6 #2: editable install pointer was already at MAIN (T-A.1 failed to repoint to worktree, so install stayed at main throughout). Merge automatically updated the code under the pointer. Orchestrator attempted post-merge `pip install -e .` for shim refresh; hit the same `swing.exe`-locked `WinError 32` (`c:\users\rwsmy\appdata\roaming\python\python314\scripts\swing.exe` held by another process). **This is a Windows-Python entry-point-shim rebuild blocker, NOT a code-pointer problem.** Operator already used `python -m swing.cli ...` workaround during phase-2 OAuth setup successfully; post-merge invocations via `python -m swing.cli ...` from main repo dir hit the post-merge Sub-bundle A code. The `swing` shim may also work (if it was rebuilt with the post-merge entry-point definition at any prior `pip install -e .` cycle). If operator wants to refresh the shim cleanly, stop the locking process (likely a running `swing web` instance) + re-run `pip install -e .` — but it's not blocking any functionality.
2. **Worktree husk pending operator cleanup-script** — branch `schwab-bundle-A-foundational` deleted post-merge; on-disk husk at `.worktrees/schwab-bundle-A-foundational/` will be ACL-locked per Phase 6+7+8+9+10 precedent. **9th pending husk** in cleanup-script queue per return report §7. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` post-merge to clean up.
3. **Optional gate completion S4/S5/S6** — operator-elective per return report §6 #1; sub-second-cost CLI invocations against operator's existing production tokens DB. Code-path coverage may be sufficient.
4. **Production audit-row cleanup script** at `scripts/fix_phase2_misleading_audit_rows.py` is idempotent; banked at return report §6 #3 for future archeologists.

### Cross-bundle reminders for B/C/D dispatch brief drafting

- **Single-Client-instance discipline:** B/C/D MUST consume the SAME `SchwabClient` instance from A; MUST NOT create additional `schwabdev.Client(...)` instances elsewhere (per Finding 2 in 2026-05-13 schwabdev distillation entry).
- **`Schwabdev` capital-S logger prefix:** any logger filtering/inspection in B/C/D MUST use the live capital-S form, NOT the lowercase plan §H.8 assumption.
- **`ensure_schwab_log_redaction_factory_installed()`** pre-call defense BINDING for every schwabdev API call (Sub-bundle B + C wrappers).
- **`reference/schwab-bundle-A-task-A0b-recon.md`** (recon doc §6 + §6.bis) is LOCKED input for Sub-bundle B dispatch brief drafting per return report §6 #6.
- **`ReconciliationRun.schwab_api_call_id`** field already exists at branch-tip (R1 M#5 landed it); Sub-bundle B's `run_schwab_reconciliation` populates it (no re-implement).
- **Codex chain pre-emption table** (return report §12 #6): Sub-bundle B brief should pre-empt the 4 patterns Sub-bundle A Codex caught — silent-failure post-call validation (M#1 family); audit-success-fire ordering (M#3 family); factory-replacement defense (M#2 family); redact-then-truncate (R3 M#1 family).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- Sub-bundle A executing-plans dispatch brief: `docs/schwab-bundle-A-executing-plans-dispatch-brief.md` (`bd166c5`).
- Sub-bundle A return report: `docs/schwab-bundle-A-return-report.md` (`6550494`).
- Sub-bundle A T-A.0.b recon doc: `docs/schwab-bundle-A-task-A0b-recon.md` (Phase 1 pre-check + Phase 2 operator-paired live verification observations).
- Production audit-row cleanup script: `scripts/fix_phase2_misleading_audit_rows.py`.
- Distilled refs consumed: `reference/schwab-api/{account,market-data}-{documentation,specification}.md` + `reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md`.

### Next dispatch

**Sub-bundle B executing-plans dispatch UNBLOCKED.** Operator-paced. Orchestrator drafts the executing-plans brief when operator commissions. Brief drafting MUST consume:
1. Recon doc §6 + §6.bis as binding LOCKED inputs.
2. The 5 forward-binding lessons in this entry's "5 forward-binding lessons for Sub-bundle B" section.
3. Confirmed schwabdev 2.5.1 surfaces (lesson #5 above) — Sub-bundle B's `trader.py` consumes these.
4. Cross-bundle pins (un-skip-at-T-B.8).
5. Codex chain pre-emption table (4 patterns to pre-empt).
6. `reference/schwabdev/api-calls.md` pre-check for Trader API method-name + signature pre-answers (3 accounts + 7 orders + 2 transactions endpoints documented).
7. `reference/schwab-api/account-{documentation,specification}.md` pre-check for Trader API endpoint shape pre-answers.

---

## 2026-05-13 schwabdev library distillation SHIPPED — 7 tracked refs at `reference/schwabdev/` + 3 operator-flagged cross-bundle findings

**Distillation SHIPPED 2026-05-13** at `62f5dde` (single commit on main; `docs(schwabdev): distill 7 schwabdev library docs pages into reference/schwabdev/`). Operator-driven via parallel instance, post-Sub-bundle-A-dispatch-brief (`bd166c5`). Sub-bundle A implementer is aware + has taken the findings into account; impacts will be noted in the A return report.

### Tracked distillation files at `reference/schwabdev/`

| File | Size | Coverage highlight |
|---|---|---|
| `setup-guide.md` | 6 KB | App registration on developer.schwab.com (callback URL, scopes, "Ready for use" gate); 3-positional `Client` init; first-run paste-back-URL flow |
| `examples.md` | 35 KB | 8 example files verbatim incl. `capture_callback.py` (custom OAuth flow) + `encrypted_db_setup.py` (Fernet token store) + async variant |
| `client.md` | 14 KB | Full `Client`/`ClientAsync` constructors (all 8 params); access-token 30-min + refresh-token 7-day lifecycle; auto-refresh scheduling; **rate limits 120/min + 4000 orders/day** |
| `api-calls.md` | 25 KB | **23 wrapper methods → 23 Schwab REST endpoints with verbatim mapping** (3 accounts + 7 orders + 2 transactions + 1 prefs + 2 quotes + 2 chains + 1 history + 1 movers + 2 markets + 2 instruments) |
| `streaming.md` | 32 KB | 22 Stream methods incl. 13 subscription helpers; LOGIN handshake captured verbatim; **field-ID translation gap flagged** (no helper in schwabdev; defers to our `reference/schwab-api/market-data-documentation.md`) |
| `orders.md` | 15 KB | 5 order helpers + 10 payload recipes (schwabdev adds 3 beyond Schwab's 7: Limit Buy stock, Sell Options open-short, Iron Condor 4-leg) — **NOT V1 SCOPE** (order placement is explicit OUT-OF-SCOPE per spec §1.2 + §3.3.3) |
| `troubleshooting.md` | 8 KB | `unsupported_token_type` → `update_tokens(force_refresh_token=True)`; trailing-slash callback fix; macOS SSL cert; permessage-deflate DNS/proxy fix |

### 3 operator-flagged findings (BINDING for cross-bundle dispatch brief drafting)

**Finding 1: `tokens_file` vs `tokens_db` kwarg name discrepancy.** Setup Guide narrative uses `tokens_file=` parameter name; examples in `examples.md` use `tokens_db=`. **Sub-bundle A T-A.4 + T-A.5 implementer must verify the FINAL kwarg name against schwabdev source before integration** (likely `tokens_db` per examples; setup-guide may be stale doc). Implementer is aware per operator's note; Sub-bundle A return report will record the verified name.

**Cross-bundle impact:** none for B/C/D (they consume the `Client` instance constructed in A; no direct kwarg usage).

**Finding 2: Multi-Client-instance file-locking semantics not documented.** schwabdev's only guidance is "share the same `tokens_db`." Concurrent Client instances with the same `tokens_db` rely on schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` per the writing-plans research, but the multi-instance behavior is integration-layer concern.

**Cross-bundle impact:** Sub-bundles B + C + D MUST consume the SAME `Client` instance constructed in Sub-bundle A's wrapper (`swing/integrations/schwab/client.py:SchwabClient`); MUST NOT create additional `schwabdev.Client(...)` instances elsewhere. This is a binding constraint for B/C/D dispatch brief drafting — orchestrator threads it explicitly into each brief.

**Finding 3: 7-day refresh-token expiry forces full re-auth; no programmatic workaround.** schwabdev's auto-refresh covers the 30-min access_token; refresh_token's 7-day TTL means operator must re-run `swing schwab setup` paste-back at minimum every 7 days. No way to extend programmatically.

**Cross-bundle impact across entire arc:**
- **Sub-bundle A:** T-A.6 `swing schwab status` skeleton SHOULD surface refresh_token validity time-remaining (Sub-bundle A scope per plan §Tasks-A T-A.6 already includes "refresh_token validity displayed").
- **Sub-bundle D:** `swing schwab status` full surface MUST clearly alert operator when refresh_token expiry is approaching (e.g., ≤24 hr remaining = WARN; ≤2 hr = ERROR + bold red). Bundle D dispatch brief explicitly calls this out.
- **Sub-bundle D briefing banner:** the `briefing.md` "Schwab integration: degraded" banner per plan §0.1 SHOULD include refresh_token expiry warning when applicable.
- **Cycle-checklist update:** plan §I.X cycle-checklist additions in Bundle D MUST include "weekly: re-run `swing schwab setup` paste-back if refresh_token approaching 7-day expiry."
- **CLAUDE.md gotcha promotion in Bundle D T-D.4:** add a Schwab-specific gotcha about the 7-day refresh ceiling.

### Cross-bundle orchestrator-action items (BINDING for Sub-bundle B/C/D dispatch brief drafting)

When orchestrator drafts each subsequent dispatch brief, BIND these:

1. **Include `reference/schwabdev/` in §0 reads** (mirroring the existing `reference/schwab-api/` orchestrator-action item from `abb6177`). Both reference dirs are now binding §0 reads for ALL Sub-bundle B/C/D briefs. `reference/schwabdev/` is the SECOND-tier source-of-truth (library wrapping behavior); `reference/schwab-api/` is the FIRST-tier source-of-truth (Schwab Developer Portal canonical docs).

2. **Pre-check `reference/schwabdev/api-calls.md` for Bundle B + C method-name + signature pre-answers.** 23 wrapper methods documented with verbatim Schwab REST endpoint mappings. Many Bundle B + C `[VERIFY]` tags from plan §E (Trader API + Market Data API) may already be answered there — implementer skips the operator-paired live verification for items already in api-calls.md.

3. **Pre-check `reference/schwabdev/client.md` for Bundle A + B + C rate-limit assumptions.** Documented 120/min + 4000 orders/day. Reduces or pre-answers Q17 (Market Data API rate limits independent of Trader API).

4. **Pre-check `reference/schwabdev/troubleshooting.md` for Bundle D status-surface alert design.** `unsupported_token_type` → `update_tokens(force_refresh_token=True)` is operationally critical for the status surface — should surface as actionable alert with the exact remediation command.

5. **Single-Client-instance discipline (Finding 2):** B/C/D dispatch briefs explicitly enumerate that the SchwabClient instance is constructed in A + consumed (NOT re-constructed) by B/C/D. Discriminating test pattern: search `swing/integrations/schwab/` + assert `schwabdev.Client(...)` is invoked ZERO times outside `client.py:SchwabClient.__init__`.

6. **7-day refresh expiry (Finding 3):** Bundle D dispatch brief MUST include the status-surface alert design + cycle-checklist weekly re-auth reminder + CLAUDE.md gotcha promotion. Operator-attention item across entire arc — surface in operator-witnessed gate criteria for each subsequent bundle ("verify status surface refresh_token validity displayed correctly").

### `streaming.md` content disposition (V2 candidate)

Streaming WebSocket support is **NOT V1 SCOPE** per Q4 disposition (V1 batch-poll). However, the field-ID translation gap flagged in `streaming.md` (no helper in schwabdev; would need `reference/schwab-api/market-data-documentation.md` as a manual translation source) is a **V2 design constraint** — when streaming is added in V2, the field-ID translation layer is a NEW design surface NOT covered by schwabdev's API. Bank for V2 streaming dispatch.

### `orders.md` content disposition (OUT-OF-SCOPE)

Order placement (5 helpers + 10 payload recipes) is **explicit OUT-OF-SCOPE** per spec §1.2 + §3.3.3 (project is operator-discretion-trade-execution; automated order placement out of scope). The orders.md distillation is informational only; NOT consumed by any V1 dispatch.

### Cross-references

- Distillation: `reference/schwabdev/` (7 files; commit `62f5dde`).
- Sub-bundle A dispatch brief: `docs/schwab-bundle-A-executing-plans-dispatch-brief.md` (`bd166c5`; Sub-bundle A implementer aware of these findings per operator's note).
- Companion distilled refs: `reference/schwab-api/` (4 files; commit `829dffd`).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).

### Next dispatch

**Sub-bundle A executing-plans dispatch UNCHANGED** (already commissioned per operator; brief at `bd166c5`; implementer aware of findings per operator's note). Sub-bundle B/C/D dispatch briefs (drafted post-A-ship) will consume these findings as binding §0 reads + cross-bundle constraints.

---

## 2026-05-13 Schwab API integration writing-plans SHIPPED — 2447-line plan + ZERO open orchestrator-triage questions + 11 Codex rounds (most in project history)

**Plan SHIPPED 2026-05-13** at `7faab72` (single commit on main; `docs(schwab-api): integration writing-plans implementation plan`). Operator-dispatched implementer per orchestrator-drafted brief at `5bf425d` + COA B amendment at `9fd50e6`. Plan at `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (2447 lines; above 1500-2500 brief budget upper-bound by 0%; acceptable due to 11-round adversarial chain producing additional plan content).

**11 Codex rounds → NO_NEW_CRITICAL_MAJOR** (most in project history; Phase 9 = 19 across 5 bundles; Phase 10 = 13 across 5 bundles; Schwab single plan = 11). Cumulative findings 2C + 26M + 23m all RESOLVED inline; **1 ACCEPT-WITH-RATIONALE banked** (R3 Major #4 same-day-UPSERT provenance asymmetry — explicit S7 wording covers).

### Two Critical-class finds (both Codex-discovered + RESOLVED in-tree)

1. **R1 Critical #1 — migration atomicity claim contradicted actual runner.** Plan author misread CLAUDE.md's `executescript() implicit COMMIT` gotcha + assumed `_apply_migration` issues explicit BEGIN. It does not. Migration 0018 SQL file now opens with `BEGIN;` + closes with `COMMIT;` to compensate (file-level discipline; runner-level update banked for V2). Forward-binding for migrations 0019+: mirror this pattern until runner is updated.
2. **R7 Critical #1 — token-redaction filter design based on FALSE Python logging assumption.** Plan author's Layer 2 redactor used `logging.Filter` on root logger; Codex caught that `Logger.callHandlers()` does NOT re-apply ancestor filters during propagation. Fix: switched to `logging.setLogRecordFactory()` approach which catches records at creation time regardless of which logger emits or which handler captures (covers pytest caplog + third-party handlers + lazily-created schwabdev sub-loggers). R7-R10 chain hardened against factory-chaining recursion + reset-fixture contamination + LogRecord direct-call fallback. **One of the deepest design-fix sequences in project history.**

### Sub-bundle decomposition (final shape — 4 sub-bundles per §0.1)

| # | Sub-bundle | Tasks | Tests projected | Inter-bundle deps |
|---|---|---:|---:|---|
| **A** | schwabdev wrap + auth + migration 0018 + audit infra + CLI setup/refresh/logout/status skeleton | 11 (T-A.0..T-A.10) | +126 (range +100..+135) | NONE (foundational) |
| **B** | Trader API + `_step_schwab_snapshot` + `_step_schwab_orders` + `run_schwab_reconciliation` + sandbox-gating + CLI fetch + `SchwabPipelineActiveError` | 9 (T-B.0.b..T-B.8) | +80 (range +75..+95) | A (audit infra + auth + migration) |
| **C** | Market Data API + Shape A parquet-per-(ticker, provider) + `PriceCache` provider field + cache integration + `--verify-marketdata` CLI + sandbox short-circuit | 8 (T-C.0.b..T-C.7) | +68 (range +60..+80) | A (audit infra + auth); independent of B |
| **D** | `swing schwab status` full surface + briefing banner + E2E + cycle-checklist + CLAUDE.md + Phase 11 hand-off | 7 (T-D.1..T-D.7) | +19 (range +15..+30) | A + B + C |
| **Total** | | **35** | **+293 (range +250..+340)** | |

**Strict dispatch ordering: A → B → C → D.** A is BLOCKING for B+C (migration + audit contract); B+C are functionally independent but share files (cli/schwab.py + integrations/schwab/mappers.py — sequential B→C avoids merge conflicts trivially); D is BLOCKING on all three (E2E + handoff).

### Schema posture decisions (§C)

- **Migration 0018:** single atomic file with explicit `BEGIN;` / `COMMIT;` discipline. Creates `schwab_api_calls` table (14 columns + 4 CHECK enums + 4 indexes + 3 FKs `ON DELETE SET NULL`). ALTERs: `account_equity_snapshots ADD COLUMN schwab_account_hash TEXT NULL` (Q16 forward-prep multi-account); `reconciliation_runs ADD COLUMN schwab_api_call_id INTEGER NULL REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL`. UPDATE schema_version 17→18.
- **EXPECTED_SCHEMA_VERSION bump:** 17 → 18 (T-A.7 implements).
- **Backup gate:** does NOT auto-fire for 17→18 (R1 Major #1 corrected — existing gate is version-specific to 13→14/15→16/16→17). **Operator-manual backup recommended per §I.1 cycle-checklist update** before first `swing db-migrate` lands 0018.
- **CHECK enums already permit `'schwab_api'`** (Phase 9 Sub-bundle B + C foresight): `reconciliation_runs.source` line 194 + `account_equity_snapshots.source` line 332 of migration 0017. NO ALTER on either CHECK enum needed.

### Market-data ladder persistence shape decision (V1 INCLUDE branch per Q11)

**Shape A LOCKED** (parquet-per-(ticker, provider)) per spec §3.8.2 default. Justification: cleanest separation; no SQL migration for OHLCV path; resolver code is small (~50 LOC merge); per-provider files operator-greppable; matches Phase 9 source-ladder pattern. Downstream impact: filename change `{TICKER}.parquet` → `{TICKER}.{PROVIDER}.parquet`; new `resolve_ohlcv_window(ticker, start, end)` resolver; `PriceCacheEntry` gains `provider` field DISTINCT from existing `source` TTL-state field; backward-compat handles 4 cases including both-files-exist via MERGE-AND-QUARANTINE.

### Q1-Q18 disposition wiring + plan §D Task 0.b items

**ZERO open questions for orchestrator triage.** All 18 dispositions (Q1-Q18) wired through plan §A.1 + §A.2 acceptance criteria. The 6 §D entries are operator-paired Task 0.b live verification items (NOT open questions for the orchestrator):

- §D.1 Q8 sandbox-vs-production HTTP-layer differentiation (base URL / path / scope / TTL).
- §D.2 Q12 premium-tier Schwab Market Data endpoint access vs operator's actual subscription tier.
- §D.3 Q13 residual paste-back UX verification.
- §D.4 Q14 OAuth scope-string composition (default `readonly`; verify exact format).
- §D.5 Q15 refresh-token rotation behavior.
- §D.6 Q17 Market Data API rate limits independent of Trader API.

These BLOCK each downstream sub-bundle dispatch until completed (operator-paired live verification).

### Three highest-leverage plan decisions (return report §3)

1. **Migration 0018 explicit `BEGIN;`/`COMMIT;` discipline at the SQL file level** — corrects the misreading of CLAUDE.md's `executescript()` gotcha; future migrations 0019+ MUST mirror this discipline until the runner is updated.
2. **Three-layer token redactor with `logging.setLogRecordFactory()` (NOT `logging.Filter`)** — corrects a fundamental Python logging misunderstanding (filters on ancestor loggers do NOT fire during propagation); the factory approach catches records at creation time regardless of which logger emits or which handler captures, covering pytest caplog + third-party handlers + lazily-created schwabdev sub-loggers.
3. **Production-only domain writes gating matrix across 5 distinct surfaces** — Trader API call-with-audit-no-domain in sandbox; market-data pipeline SKIPs Schwab entirely in sandbox; `--verify-marketdata` env-independent. Prevents sandbox responses from poisoning production metrics via the source-ladder.

### Inherited disciplines from Phase 9 + Phase 10 + Finviz (per return report)

- Source-ladder consumer (no re-design): §A.4 enumerates verbatim consumption; new `run_schwab_reconciliation()` service mirrors `run_tos_reconciliation` shape; reuses Phase 9 Sub-bundle B `MATERIAL_BY_TYPE` lookup.
- Service-layer transaction discipline: §A.9 #2 + §H.4.1 step 8d combined-tx2 + new audit service `link_snapshot_and_stamp_account_hash` all OWN BEGIN IMMEDIATE; REJECT caller-held tx.
- Token redaction layering: §G.3 cassette filters + §H.8 three-layer redactor (Layer 0 known-value exact-replace; Layer 1 heuristic regex; Layer 2 setLogRecordFactory wrapper with thread-local recursion guard + ensure_* re-install defense).
- Server-stamping: §A.9 #4 + §H.1 setup + §H.2 refresh.
- USERPROFILE+HOME monkeypatch: §A.9 #8 covers BOTH user-config.toml write path AND schwabdev Tokens DB path resolution.
- Session-anchor read/write alignment: §A.9 #9 uses `last_completed_session(now())` matching Phase 10 capital-friction read predicate.

### Brief deviations from dispatch brief (per return report; ONE flagged)

- Brief §0.7 estimated "Likely Sub-bundle D: Audit trail + observability + `swing schwab status`". Plan FOLDS audit-infra into Sub-bundle A (must land before B+C consume) + leaves status-full-surface in Sub-bundle D-polish. Justified: A must land the audit-row contract that B+C consume; splitting it from B+C would require A to ship a stub-only audit and then re-touch A's files during D, breaking file-isolation discipline. Acceptable deviation; orchestrator concurs.

### Operator-attention items (per return report)

- **`schwabdev>=2.4.0,<3.0.0` version pin** synthesized; T-A.1 pins exact version + verifies method signatures match §E at Task 0.b. Operator-actionable verification item.
- **6 deferred Task 0.b verification items** enumerated in plan §D — operator-paired live verification BLOCKS each sub-bundle dispatch until completed (Q8 + Q12 + Q13-residual + Q14 + Q15 + Q17).
- **Operator-manual DB backup** before first `swing db-migrate` run that lands 0018 (no auto-gate fires per §C.5; cycle-checklist update covers).
- **NO CLAUDE.md gotchas promoted YET** — plan §J.1-§J.6 enumerate 6 entries that Bundle D T-D.4 will land at executing-plans time.

### Operator-provided distilled Schwab API references (tracked at `reference/schwab-api/`)

Operator created 2026-05-13 via parallel instance: 4 distilled markdown files derived from saved Schwab Developer Portal HTML pages (raw HTML at `reference/SchwabAPI/`, gitignored as bulk reference per same posture as `reference/Books/`). The distilled MDs are tracked + small + canonical:

- `reference/schwab-api/account-documentation.md` — Trader API account/order/transaction documentation digest.
- `reference/schwab-api/account-specification.md` — Trader API account/order/transaction OpenAPI / response-shape specification.
- `reference/schwab-api/market-data-documentation.md` — Market Data API quotes/pricehistory documentation digest.
- `reference/schwab-api/market-data-specification.md` — Market Data API OpenAPI / response-shape specification.

**Orchestrator action item — BINDING for ALL future Schwab API executing-plans dispatch briefs (Sub-bundle A through D):** include `reference/schwab-api/` in the brief's §0 reads list. These distilled references are HIGHER-FIDELITY than the synthesized §E endpoint catalog in the spec/plan because they're derived directly from Schwab's published documentation. **Implications for Task 0.b verification gates:**

- May materially reduce operator-paired live verification burden for Q8 (HTTP-layer differentiation: base URL / path / scope), Q14 (OAuth scope-string composition), Q17 (Market Data API rate limits), and the §E synthesized endpoint shapes flagged with `[VERIFY]` tags.
- Implementer should consult `reference/schwab-api/` FIRST during Task 0.b — many `[VERIFY]` items may already be answered in the distilled references; only items NOT covered need live API verification.
- Spec + plan §E + §D do NOT cite these references (operator created them after writing-plans shipped). The executing-plans dispatch briefs are the right surface to thread them in.

**Plan + spec amendment posture:** spec §E + plan §E + plan §D §D.1-§D.6 may benefit from a future amendment-pass to cite the distilled refs explicitly. Operator-paced; not blocking executing-plans dispatch (the executing-plans brief threading + Task 0.b runbook update is sufficient).

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Writing-plans dispatch brief: `docs/schwab-api-writing-plans-dispatch-brief.md` (`5bf425d` + `9fd50e6` COA B amendment).
- Plan: `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`).
- **Operator-provided Schwab API distilled references:** `reference/schwab-api/{account,market-data}-{documentation,specification}.md` (4 files).
- Sub-bundle A executing-plans dispatch brief: TBD (orchestrator drafts; operator-paced).

### Next dispatch

**Sub-bundle A executing-plans dispatch UNBLOCKED.** Operator-paced. Orchestrator drafts the executing-plans brief when operator commissions. Plan §K T-A.0.b runbook covers the operator-paired Task 0.b live API verification gate that blocks Sub-bundle A dispatch start. **`reference/schwab-api/` distilled refs go into the dispatch brief's §0 reads + may pre-answer several §D items** (orchestrator pre-checks at draft time).

**Threading reminder:** review-form polish task (per phase3e-todo entry "Trade exit review form — stale Phase 7 will auto-derive promise") goes into Sub-bundle D's executing-plans dispatch brief at draft time per operator-locked 2026-05-13 disposition.

---

## 2026-05-13 Schwab API Q18 build-vs-buy disposition LOCKED — COA B = `schwabdev`

**Brainstorm-spec gap surfaced post-triage.** The 2026-05-13 brainstorm spec at `585556f` implicitly chose COA C (roll our own) by enumerating `swing/integrations/schwab/` sub-package + `SchwabClient` + sidecar JSON token storage + custom file-lock + custom OAuth flow as the V1 architecture, **without ever explicitly comparing against the two community-maintained Python wrappers it lists in §12 references** (`schwab-py`, `schwabdev`). Operator surfaced the gap immediately after orchestrator drafted the writing-plans dispatch brief at `5bf425d`; orchestrator researched both libraries' OAuth implementations + presented tradeoff matrix; operator confirmed COA B on 2026-05-13.

### Three-way comparison (orchestrator research findings)

Library OAuth + token-handling implementation comparison (sourced from `alexgolec/schwab-py:schwab/auth.py` + `tylerebowers/Schwabdev:schwabdev/{client,tokens}.py` direct fetch):

| Dimension | schwab-py (COA A) | schwabdev (COA B) | Wins |
|---|---|---|---|
| Storage | JSON file; **no atomicity** (raw `open(..., 'w')`) | SQLite with `BEGIN EXCLUSIVE` transaction; atomic replacement across processes | **schwabdev** — matches our spec §3.2.4 file-lock intent with stronger semantics |
| Refresh strategy | Lazy only (authlib-driven) | Hybrid: lazy per-request `update_tokens()` + proactive async `_checker()` every 30s | **schwabdev** — matches spec §3.2.3 design intent exactly |
| Safety margin | 300s leeway (authlib `leeway=300`) | 61s access threshold + 3630s refresh threshold (separate tracking; tunable) | **schwabdev** — explicit + testable thresholds |
| Refresh-token rotation | Opaque passthrough (whatever authlib gives the callback) | Explicit `if new_refresh_token: self.refresh_token = new_refresh_token` + immediate persist | **schwabdev** — explicit handling simplifies spec Q15 verification |
| Concurrency | **None** (no file locks, no thread locks) | `threading.RLock` (in-process) + SQLite `BEGIN EXCLUSIVE` (cross-process) | **schwabdev** — solves spec §3.2.4 file-lock requirement out of box |
| Encryption at rest | Not visible | Optional Fernet cipher (operator provides 32-byte URL-safe base64 key; `enc:` prefix in DB) | **schwabdev** — spec Q2 V2 hardening optionally available V1 |
| Callback flow | Both: localhost (Flask listener) + paste-back fallback + Jupyter auto-detect | Paste-back only (with optional `webbrowser.open()`) | **schwab-py** — both modes; schwabdev requires paste-once at setup |
| Token logging audit | `register_redactions(token)` registered after fetch (extent unclear beyond fetched code) | No tokens logged directly; one caveat: `tokens.py:~338` logs `response.text` on auth failure (could include token-related error details) | schwab-py has explicit redaction call site; both need our wrapping audit |
| Maturity | ~1.5k stars; Alex Golec's tda-api lineage; battle-tested | Newer; smaller community; less battle-tested | **schwab-py** — wider user base |

**Streaming use case clarification:** Both libraries support Schwab's WebSocket streaming API. Per community consensus, streaming is primarily a day-trading feature (low-latency tick data, Level-I/II order books, real-time order push notifications). For this project's daily-pipeline-cadence swing trading, streaming is V2-deferrable (Q4 disposition: V1 batch-poll). Neither library forecloses streaming — both make it available if V2 wants intraday position monitoring or real-time stop-violation alerts.

### LOCKED disposition: COA B (schwabdev)

Operator decision rationale: spec §3.2.2-3.2.4 design intent (atomic storage + cross-process locking + hybrid refresh + explicit rotation handling) is exactly what schwabdev already ships. Re-implementing those from scratch in COA C is high implementation risk for security-critical OAuth code; using a library where the maintainer cares about exactly the right details + has SQLite-backed atomic storage is more defensible than rolling our own. COA A's wider community is offset by COA A's design gaps (no concurrency protection; opaque rotation; lazy-only refresh).

**Tradeoff accepted:** schwabdev's paste-only callback flow (no localhost listener) — operator pastes once at `swing schwab setup` per env, never again. Spec Q13 disposition simplifies to paste-back V1; localhost listener becomes V2 candidate if operator surfaces friction post-V1.

### Spec sections SUPERSEDED by COA B

Per writing-plans dispatch brief §0.3a (commit `<post-COA-B-update>`): plan author re-derives in plan §A or §H —

- §3.1 module layout: still `swing/integrations/schwab/` sub-package; now thin wrapper around `schwabdev.Client`.
- §3.2.1 setup flow: paste-back only V1 (was both modes).
- §3.2.2 token storage: per-environment SQLite DB at `%USERPROFILE%/swing-data/schwab-tokens.{sandbox,production}.db` (was JSON sidecar).
- §3.2.3 refresh strategy: schwabdev's hybrid lazy + proactive 30s `_checker()` + 61s/3630s thresholds (better than spec).
- §3.2.4 concurrency: schwabdev's `RLock` + SQLite `BEGIN EXCLUSIVE` (custom file-lock shim NOT NEEDED).
- §3.3.1 + §3.3.2 endpoint catalogs: call schwabdev `Client` methods (`account_details`, `account_orders`, `transactions`, `quotes`, `price_history`); raw HTTP details deferred to schwabdev docs.
- §3.5 CLI subcommand bodies: wrap schwabdev's auth flow (paste-back) + `update_tokens(force_refresh_token=True)`.
- §5 token redaction: cassette discipline + DEBUG-log suppression context manager STILL apply; sentinel-token-leak audit STILL required + extends to verifying schwabdev's loggers don't leak (one known caveat: `tokens.py:~338` `response.text` on auth failure).
- §10 Q2 token encryption: optional Fernet now AVAILABLE V1 if operator wants (default V1 plaintext per spec disposition; operator may elect Fernet at writing-plans review).
- §10 Q13 callback localhost vs paste: paste-only V1 (schwabdev constraint; operator confirmed acceptable).
- §10 Q15 refresh-token rotation: schwabdev handles explicitly; Task 0.b verification simplifies to "observe rotation behavior + record one cassette per case."

### Spec sections UNAFFECTED by COA B

- §3.4 pipeline integration architecture (steps + ordering + failure tolerance + `SchwabPipelineActiveError`).
- §3.6 audit trail (`schwab_api_calls` table + INSERT/UPDATE lifecycle).
- §3.6.2 audit-write surface boundary.
- §3.6.3 production-only domain writes.
- §3.7 source-ladder write path.
- §3.8 market-data ladder design (V1 INCLUDE branch).
- §4 schema candidates (`schwab_api_calls` table + ALTERs).
- §6 failure-mode catalog.
- §7 operator setup flow + cycle-checklist.
- §9 watch items.

### Plan-scope impact

- New runtime dependency: `schwabdev>=<version>` added to `[project.dependencies]` (NOT dev-extras).
- Sub-bundle scopes shrink relative to spec §0.7 estimate — Sub-bundle A no longer designs OAuth from scratch; auth + token storage become "wrap schwabdev's `Tokens` class with our gotcha discipline."
- Plan §B file map removes the file-lock module (no longer needed).
- New plan §K verification gate: schwabdev's own logger output verified token-redaction-safe at integration-test level.

### Brief-template improvement candidate (orchestrator-side learning)

Future brainstorm dispatch briefs for any "integrate external system X" scope MUST include an explicit build-vs-buy question (Q18-equivalent) in §1 strategic-context OR §2 brainstorm scope. The Schwab brainstorm brief silently assumed "we'll roll our own per Finviz precedent" without surfacing the question. The Finviz precedent itself was COA C because no Finviz Elite Python wrapper existed at brainstorm time; Schwab has TWO mature wrappers + the question deserved first-class treatment. Brief author (orchestrator) caught this only after operator pushback post-brainstorm.

### Cross-references

- Brainstorm spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Writing-plans dispatch brief (updated with §0.3a Q18 disposition): `docs/schwab-api-writing-plans-dispatch-brief.md` (`<post-COA-B-update>`).
- schwabdev source consulted: `tylerebowers/Schwabdev:schwabdev/{client,tokens}.py` (raw GitHub fetch via WebFetch 2026-05-13).
- schwab-py source consulted: `alexgolec/schwab-py:schwab/auth.py` (raw GitHub fetch via WebFetch 2026-05-13).

### Next dispatch

**Operator-paced.** Writing-plans dispatch brief now reflects Q18 = COA B; operator dispatches when ready.

---

## 2026-05-13 Schwab API integration brainstorm SHIPPED — 939-line spec + 17 open questions for orchestrator triage (operator-paced)

**Brainstorm SHIPPED 2026-05-13** at `585556f` (single commit on main; `docs(schwab-api): integration brainstorm spec`). Operator-dispatched implementer per orchestrator-drafted brief at `c4252d3` (`docs/schwab-api-brainstorm-dispatch-brief.md`, 390 lines). Spec at `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (939 lines; within 600-1100 brief budget).

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/10M/5m → R2 0C/6M/3m → R3 1C/3M/2m → R4 0C/2M/2m → R5 0C/0M/0m); cumulative 1C + 21M + 12m all RESOLVED inline; **ZERO ACCEPT-WITH-RATIONALE banked** — matches Phase 10 cleanest-arc precedent. Terminated within MAX_ROUNDS=5; no operator-override past default needed.

### Three highest-leverage design decisions

1. **§3.6.3 production-only domain writes (R3 Critical resolution).** `cfg.integrations.schwab.environment` gates `record_snapshot()` + `run_schwab_reconciliation()`; sandbox is verification-only (audit rows written; ZERO domain rows; market-data ladder short-circuits). Prevents synthetic Schwab data from winning the source-ladder (Schwab is precedence 0) and silently contaminating Phase 10 metrics + reconciliation discrepancies + cohort analysis. **Critical-class find Codex R3 surfaced; brief did not anticipate.**
2. **§3.8 market-data ladder rewrite scope honestly enumerated for writing-plans.** Brief recommended V1 INCLUDE (per operator §1.9 preference); spec writes the INCLUDE branch. Honestly admits current `PriceCache`/`OhlcvCache` do NOT have multi-source semantics today. Writing-plans picks persistence shape A (parquet-per-(ticker, provider)) / B (SQLite table) / C (provider column inside parquet). Default recommendation: A.
3. **§3.6.2 audit-write surface boundary.** Pipeline + CLI surfaces SYNCHRONOUS audit; web-page-render path is EXPLICITLY-UNAUDITED V1 (logs-only). Prevents SQLite contention from web cache misses + cardinality explosion. V2 candidates (batched-summary writer; `/admin/schwab-counters` debug endpoint) enumerated.

### Auth + token storage decisions LOCKED in spec

- **Initial-setup flow:** two first-class variants — `--callback localhost` default (one-shot HTTPS listener on 127.0.0.1:8765 with self-signed cert) + `--callback paste` V1 IF Task 0.b verifies one of three OOB mechanisms; else DROPPED V1.
- **Token storage:** per-environment sidecar JSON file at `%USERPROFILE%/swing-data/schwab-state.{sandbox,production}.json` — NOT user-config.toml.
- **Refresh strategy:** lazy-on-first-API-call with 60s proactive safety margin; file-lock on sidecar during refresh.
- **Encrypted at rest:** V1 plaintext, disclosed as **HIGHER-RISK deviation from Finviz precedent** (client_secret + long-TTL refresh_token co-stored). V2 hardening (`keyring` / DPAPI) promoted to high priority (§10 Q2).
- **Active env selection:** `cfg.integrations.schwab.environment` is SoT (default production); CLI `--environment` override per-invocation; pipeline cfg-only.
- **Revocation:** `swing schwab logout` revokes via Schwab endpoint + atomically renames sidecar to `schwab-state.{env}.json.deleted-<ts>` + unlinks.

### Pipeline integration LOCKED

- **New steps:** `_step_schwab_snapshot` + `_step_schwab_orders` (two new pipeline steps). Market-data path is NOT a separate step; integrated into `_step_evaluate`/`_step_charts` cache fetch boundaries.
- **Step ordering:** AFTER `_step_recommendations`, BEFORE `_step_charts` (briefing-includes-Schwab-data + charts-can-feed-back-on-stop-drift).
- **Failure tolerance:** continue-with-error (mirror Finviz precedent at `swing/pipeline/runner.py:285-294`).
- **CLI surface:** `swing schwab {setup, refresh, fetch [--snapshot|--orders|--all|--verify-marketdata], status, logout}`.
- **Concurrency:** `SchwabPipelineActiveError` hard exclusion for `fetch --snapshot/--orders/--all` (UPSERT-provenance race + INSERT-only duplication); `logout`/`setup` refused unless `--force`; `refresh`/`status` concurrent-safe (sidecar file-lock handles refresh).

### Schema candidates DEFERRED to writing-plans

- **New table:** `schwab_api_calls` (14 columns enumerated in spec §4.1).
- **ALTER candidates:** `account_equity_snapshots.schwab_account_hash TEXT NULL` (V1 ADD per §10 Q16 default; forward-prep multi-account V2); `reconciliation_runs.schwab_api_call_id INTEGER NULL` (FK candidate).
- **Market-data persistence:** writing-plans picks Shape A/B/C per §3.8.2 (default A: parquet-per-(ticker, provider) — no new SQL table).
- **EXPECTED_SCHEMA_VERSION bump:** 17 → 18 (driven by `schwab_api_calls` + ALTERs; Shape B would also drive a bump from market-data side).

### 17 open questions for orchestrator triage (operator-paced)

Orchestrator-grouped by triage urgency for operator review:

**A. Operator-decide-NOW (impacts writing-plans scope; 4 items):**
- Q1: Schwab Developer Portal app status — **OPERATOR-CONFIRMED 2026-05-13: production-tier approval already in hand.** Updated disposition: production-only V1; sandbox registration deferred to Task 0.b (operator decides at executing-plans whether sandbox cassette-recording adds value — depends on whether Schwab requires distinct sandbox app registration vs unified credentials, which Task 0.b verifies).
- Q3: Multi-account support — orchestrator default: V1 single-primary-account; V2 multi-account.
- Q11: Market-data ladder V1 INCLUDE vs EXCLUDE — orchestrator default: **V1 INCLUDE** (operator-flagged at brief time; spec writes INCLUDE branch).
- Q6: Schwab inception-CSV ingestion — orchestrator default: **separate dispatch** (per phase3e-todo 2026-05-12 entry; keep this arc focused).

**B. Operator-confirm-defaults (orchestrator-can-take; 6 items):**
- Q2: Token encryption — V1 plaintext (Finviz precedent + risk disclosed; V2 keyring/DPAPI = high-priority hardening).
- Q5: Operator UI — V1 CLI-only.
- Q7: TOS CSV deprecation — stays as V1 fallback.
- Q9: Cash-basis manual snapshot retention — yes (source-ladder resolves at read time).
- Q10: Pipeline step ordering — after `_step_recommendations`, before `_step_charts` (architectural).
- Q16: `account_hash` column on `account_equity_snapshots` — V1 ADD (NULL-permissible; forward-prep multi-account; cheap insurance).

**C. Defer-to-Task-0.b live verification (5 items; operator-paired at executing-plans):**
- Q4: Streaming vs batch-poll — V1 batch-poll; V2 streaming.
- Q8: Sandbox vs production HTTP-layer differentiation (per-env sidecar LOCKED; HTTP-layer base URL / path / scope / TTL OPEN).
- Q12: Premium-tier Market Data endpoint access (default: V1 default-tier delayed quotes).
- Q13: OAuth callback localhost vs paste — localhost default + `--paste` flag fallback if Task 0.b reveals env block.
- Q14: OAuth scope-string composition — synthesize default; live-verify exact format.
- Q15: Refresh-token rotation behavior — design handles both rotate-every and rotate-near-expiry; cassette+test fixtures need known canonical case from operator-witnessed verification.
- Q17: Market Data API rate limits independent of Trader API — synthesized "~Trader API limits or looser"; flag Task 0.b verification.

(Note: Q14 + Q15 + Q17 are 3 of the 5 in C; total = Q4+Q8+Q12+Q13+Q14+Q15+Q17 = 7 items — orchestrator counts 5+7+4 = 16 not 17 due to Q4 fitting both B confirm + C verify; numerically 17 questions total.)

### Inherited disciplines from Finviz precedent (verbatim)

- urllib3 + requests-bundled-urllib3 DEBUG-log suppression context manager (`_suppress_transport_debug_logs`).
- Cassette `filter_headers=['authorization']` + EXTENDED `filter_query_parameters=['code', 'refresh_token', 'client_id', 'client_secret', 'redirect_uri', 'access_token']` + `filter_post_data_parameters` + custom body redactor for token/secret substrings.
- Sentinel-token-leak audit test pattern (`tests/integrations/test_schwab_token_redaction_audit.py`).
- Exception `__str__` no-token contract on every Schwab exception class.
- CLI vs pipeline concurrency exclusion via `SchwabPipelineActiveError` — INHERITED from Finviz's `FinvizPipelineActiveError` (V1 decision REVERSED implementer's R1 initial framing per brief watch-item #17 reversal; R2 Major-3 surfaced UPSERT-provenance race + reconciliation_runs INSERT-only duplication risk — **brief watch-item #17 was technically violated by final design BUT the rationale is Codex-discovered + documented**).
- Single-retry-on-429 semantics with `Retry-After` cap at 30s.

### Capture-needs feedback

- For Phase 6/7/8/9/10: **None.** All consumer surfaces already in place (Phase 9 source-ladder + Phase 10 metrics consume transparently; capital-friction LIVE badge gap closes automatically).
- **For writing-plans dispatch (12 firm-up items):** §3.3.1 endpoint shapes via Task 0.b; §3.3.1 scope strings via Task 0.b; §3.5 CLI subcommand body design; §3.6 `schwab_api_calls` DDL; §3.2.4 file-lock cross-platform shim; §3.2.1 callback HTTPS-vs-HTTP; §7 cycle-checklist updates; test fixtures + Task 0.b runbook; integration test E2E mirroring Phase 9 Sub-bundle E pattern; market-data persistence shape A/B/C choice; account_hash column V1/V2; `schwab_account_hash` + `reconciliation_runs.schwab_api_call_id` ALTERs.

### Brief deviations flagged for orchestrator awareness

1. **Amended single commit instead of one-shot commit at end of all rounds.** Brief §4 listed "no amending" alongside "single commit ... no rogue commits" — orchestrator-author-side phrasing was internally contradictory because Codex iteration produces multiple rounds of fixes that must all land in ONE commit. Implementer committed prematurely at R0 (`da30045`) before adversarial loop, then amended through R1-R5 fixes; final SHA `585556f`. Local-only history (no push); does not violate published-commit safety the "no amending" guard targets. **Brief-template improvement to orchestrator-side authoring:** future brainstorm-dispatch briefs should phrase as "defer commit until all Codex rounds complete + commit once at end" — explicit prescription removes the apparent conflict between "single commit" and "no amending."
2. **Brief watch-item #17 reversed during R2 (NORMAL TRIAGE FLOW; not a special case).** Initial spec at R0 followed brief watch-item recommendation (no hard exclusion; file-lock-only). R2 Major-3 surfaced UPSERT-provenance race (snapshot UPSERT preserves PK but overwrites `source_artifact_path` + audit row pointing to the OTHER writer's call_id — real audit-trail integrity break) + reconciliation_runs INSERT-only duplication risk. Implementer reversed to "HARD exclusion via `SchwabPipelineActiveError` on `fetch --snapshot/--orders/--all`" + escalated via return-report deviation note. **Triage outcome: orchestrator ACCEPTS reversal (rationale is sound; UPSERT-provenance race is real; final design correctly inherits Finviz precedent).** This is the elevation-via-return-report flow operating as designed — Codex catches brief-author errors + implementer surfaces them + orchestrator dispositions at triage. Not a "lesson" to bank; the system is doing what it's supposed to.

### Cross-references

- Brainstorm dispatch brief: `docs/schwab-api-brainstorm-dispatch-brief.md` (`c4252d3`).
- Spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Closest API integration precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (Finviz; merged `002338a`) + `swing/integrations/finviz_api.py`.
- Source-ladder consumer (binding inheritance per spec §3.7): `swing/data/repos/account_equity_snapshots.py:_SOURCE_PRECEDENCE` + `get_latest_snapshot_on_or_before(with_provenance=True)`; `swing/trades/account_equity_snapshots.py:record_snapshot`.
- Spec format precedent: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines).
- Post-Phase-10-close handoff: `docs/orchestrator-handoff-2026-05-13-schwab-api.md`.

### Next dispatch

**Operator-paced.** Triage 17 open questions (C-bucket items can defer to Task 0.b at executing-plans; A+B-bucket items decide-now-or-rubber-stamp orchestrator defaults). Once triage complete, orchestrator dispatches Schwab API writing-plans via separate brief.

---

## 2026-05-13 Post-Phase-10 infrastructure bundle SHIPPED — cleanup-script `-DeregisterFirst` + pytest-xdist baseline (6.56× speedup)

**Bundle SHIPPED 2026-05-13** at `27ce96f` (integration merge of `post-phase10-infra-bundle`). 5 commits = 3 task-impl (T-2 + T-3 + T-6) + 1 Codex-fix (R1 Critical #1 confirm-before-deregister) + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR**. ZERO ACCEPT-WITH-RATIONALE. **ZERO production code touched** (binding lock from dispatch brief §0; read-side / infrastructure-only).

Tests: 3255 → 3283 worktree-side (+28 net). Ruff 18 unchanged. Schema v17 unchanged.

### Key deliverables

**1. `cleanup-locked-scratch-dirs.ps1` `-DeregisterFirst` switch** (default OFF; opt-in):
- Pre-pass scans `git worktree list` for paths matching `^.+\.worktrees[\\/]+phase\d+.*` OR `^.+\.claude[\\/]+worktrees[\\/]+phase\d+.*`.
- Presents candidate list to operator + prompts for confirmation BEFORE invoking `git worktree remove --force` (R1 Critical #1 defense-in-depth gate).
- After deregister loop, existing orphan-discovery pass picks up resulting orphans.
- Safety filter: BINDING regex strict `phase\d+-*` prefix; rejects non-matching branches.
- `test_safety_filter_rejects_own_worktree_explicitly` pins that `post-phase10-infra-bundle` itself is REJECTED.
- DryRun compatibility preserved.

**2. pytest-xdist baseline integration:**
- Added `pytest-xdist>=3.5.0` to `[project.optional-dependencies].dev`.
- Configured `[tool.pytest.ini_options].addopts = "-n auto"` (operator override via `-n 0` / `-n logical` / `-n N`).
- All 3283 tests pass under `-n auto` across 3 independent runs (zero xdist-unsafe state-leak failures).

### Measurement (BINDING per dispatch brief §0.7)

- Serial baseline: **415.17s** (3255 tests).
- Parallel median (`-n auto`; 3 runs): **63.24s** (3276 tests; #1 60.82s, #2 76.07s, #3 63.24s).
- **Speedup ratio: 6.56×** (well above 2× minimum + 3-5× projection).
- Post-R1-fix final sweep: 60.96s at 3283 tests + 5 skipped + 3 pre-existing fails.

### T-1 recon findings + conditional-task disposition

**T-4 (session-scoped schema fixtures) SKIPPED:**
- `ensure_schema` NOT in `--durations` top-30 (called 254 times but aggregate <0.3% of serial baseline).
- Risk asymmetry: migration tests + rollback-semantics tests + pre/post-v17 ratify tests would silently break if schema state shared across tests.

**T-5 (TestClient lifespan audit) SKIPPED:**
- Lifespan footprint is microsecond-level (`ThreadPoolExecutor` constructor + `shutdown(wait=False)`).
- Top-30 cost is route-execution time, NOT lifespan startup.
- Audit cost (per-test app.state reachability analysis) exceeds savings.

Both remain backlog-eligible if operator surfaces a specific hotspot later.

### 5 deviations from brief (none require V2.1 §VII.F)

1. §6.1 — 1+3 serial+parallel readings instead of 3+3 (6.56× speedup unambiguous from one baseline + three readings).
2. §6.2 — Python-side tests reading `.ps1` source (NOT PowerShell Pester); 26 admit/reject corpus tests + 5 source-invariants at zero PowerShell infrastructure cost.
3. §6.3 — `-n auto` in addopts default (NOT opt-in via CLI); matches operator's stated goal.
4. §6.4 — integration test file created (was optional per brief).
5. R1 Critical #1 — confirm-before-deregister gate added in `cdea854` (not in brief; surfaced by Codex as defense-in-depth for the new destructive surface).

### Operator-witnessed gate S2 PENDING

Elevated PowerShell run of `-DeregisterFirst` against the 7 pre-merge husks + 1 new infra-bundle orphan = **8 husks to clear**. Operator-driven — orchestrator surfaces to operator post-merge for plain-chat authorization. Run:

```powershell
cd c:\Users\rwsmy\swing-trading
.\cleanup-locked-scratch-dirs.ps1 -DeregisterFirst
```

### Cross-references

- Return report: `docs/post-phase10-infra-bundle-return-report.md`.
- Dispatch brief: `docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md`.
- Cleanup script: `cleanup-locked-scratch-dirs.ps1` (extended with `-DeregisterFirst` switch).

### Next dispatch

Post-bundle handoff to NEW ORCHESTRATOR INSTANCE for Schwab API integration (multi-day brainstorm + writing-plans + executing-plans cycle). Operator-decided sequencing.

---

## 2026-05-13 Phase 10 Sub-bundle E ship: CLOSES Phase 10 — arc closer aggregate

**Sub-bundle E SHIPPED 2026-05-13** at `38dbac3` (integration merge of `phase10-bundle-E-process-grade-trend-and-polish`). 8 commits = 6 task-impl (T-E.1..T-E.6 + T-E.4 closer) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (matches Sub-bundle B + C + Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3147 worktree-side → 3254 (+107 net; ~3257 main HEAD post-merge). Ruff 18 unchanged. Schema v17 unchanged.

**Cross-bundle T-A.7 pin UN-SKIPPED at T-E.3 SAME COMMIT** (`fb6e48a`) — `test_existing_dashboard_vm_has_unresolved_material_field` no longer carries `@pytest.mark.skip` decorator + passes against retrofitted DashboardVM. Plan §H named 6 base-layout VMs to retrofit; implementation retrofitted **10** (defense-in-depth catching 4 additional VMs that extend base.html.j2 per CLAUDE.md gotcha — ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM).

### 7-surface operator-witnessed gate ALL PASS via Chrome MCP on port 8081

- **S1 inline** pytest+ruff+verify_phase10 PASS at 3254 tests.
- **S2** `/metrics/process-grade-trend` PASS — spec §4.8 reference + numeric encoding A=4..F=0 visible per lesson #19 + N=10 window + 3 closed-reviewed trades + 7-metric Class column per §A.21 matrix; all 7 metrics suppressed at n=3<5 per spec §5.4; ZERO console errors.
- **S3 banner FIRES** PASS — planted discrepancy id=1 (DHC #2 stop_mismatch material) → dashboard shows §A.18 banner "1 unresolved material reconciliation discrepancy" + "Resolve via CLI" CLI hint.
- **S4 banner CLEARS** PASS — reverted discrepancy to acknowledged_immaterial → banner absent from DOM; count=0 restored.
- **S5** `/metrics` umbrella PASS — 8 tile descriptions verified.
- **S6 T-E.5 form POST** PASS — `equity_dollars=2000` + note "S6 gate test 2026-05-13" submitted via curl (form_input + computer click did not trigger HTMX events; curl with HX-Request header reproduced operator browser submit semantics) → HTTP 204 + `HX-Redirect: /metrics/capital-friction` per Phase 5 R1 M2 LOCK; snapshot #3 created in DB with server-stamped `snapshot_date='2026-05-13'` per lesson #4 + Phase 8 server-stamping discipline; HX-Redirect target resolves to capital-friction with LIVE badge $2000.00; multi-run trend shows $1800 → $2000 transition by date correctly; ZERO console errors.
- **S7 T-E.6 trade detail indicator** PASS — DHC #2 with planted discrepancy shows "⚠ Unresolved reconciliation discrepancy (1)" at top per electives §2 Task E.6 acceptance; after revert, indicator section hidden entirely per "hide when empty" rule.

### Production state post-gate

- Snapshot #3 left in production as valid operator cash-basis reading per dispatch brief §7 #11 default (operator can update via CLI any time).
- Discrepancy id=1 reverted to `acknowledged_immaterial` with reason "post-S3/S4/S7 gate cleanup 2026-05-13".
- 30 reconciliation_discrepancies all resolved (production state restored).

### Phase 10 arc closer aggregate (return report §9)

| Sub-bundle | Commits | Codex rounds | Tests delta | Critical-resolved | Major-resolved | ACCEPT-WITH-RATIONALE | CLAUDE.md gotchas |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 15 | 4 | +128 | 0 | 3 | 0 | 0 |
| B | 9 | 2 | +73 | 0 | 2 | 0 | 0 |
| C | 8 | 2 | +84 | 0 | 2 | 0 | 0 |
| D | 12 | 3 | +102 | 0 | 5 | 0 | 0 |
| E | 8 | 2 | +107 | 0 | 1 | 0 | 0 |
| **Total** | **52** | **13** | **+494** | **0** | **13** | **0** | **0** |

**Phase 10 closer highlights:**

- **52 commits across A+B+C+D+E** (34 task-impl + 12 Codex-fix + 5 return-reports + 1 ruff).
- **13 Codex rounds total** (4+2+2+3+2).
- **+494 cumulative fast tests** (final 3254 worktree-side / ~3257 main HEAD; from pre-Phase-9 baseline 1957 → +1297 across Phase 9 + Phase 10).
- **ZERO Critical findings entire arc.**
- **ZERO ACCEPT-WITH-RATIONALE banked** — **cleanest 5-bundle arc-final state in project history.** Phase 9 had 4 banked (2 A + 1 B-later-resolved-C + 1 C; D + E clean).
- **ZERO CLAUDE.md gotchas promoted** — every defect class hit during Phase 10 was already covered by existing gotchas. Phase 9 promoted 6.
- **27 V2.1 §VII.F amendments pending** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 + 3 elsewhere). See T-E.4 "Phase 10 closer" section near end of file for full enumeration.
- **3 post-Phase-10 standalone dispatches unblocked** (cleanup-script `-DeregisterFirst` + test-runtime xdist + §8.4 Corporate_Actions MVP).
- **§A.0 ZERO-new-schema LOCK preserved** through entire arc — schema v17 unchanged through Phase 10 V1.

### 8 operator-visible Phase 10 surfaces shipped

1. `GET /metrics` (A T-A.8) — umbrella index.
2. `GET /metrics/trade-process` (B T-B.3) — 7 cohort tabs × 22 §3.1 metrics.
3. `GET /metrics/hypothesis-progress` (B T-B.5) — 4 cohort row + tripwire + transition timeline.
4. `GET /metrics/tier-comparison` (C T-C.2) — 4-cohort Wilson + bootstrap CIs + descriptor.
5. `GET /metrics/deviation-outcome` (C T-C.3) — doctrine deviation class + decision criterion.
6. `GET /metrics/capital-friction` (D T-D.2) — 6 §3.4 metrics + PROVISIONAL/LIVE dynamic badge + trend.
7. `GET /metrics/maturity-stage` (D T-D.4) — per-open-position table.
8. `GET /metrics/identification-funnel` (D T-D.6) — per-run + 30-trading-session trend.
9. `GET /metrics/process-grade-trend` (E T-E.2) — per-trade markers + rolling lines per §A.21.

Plus 4 cross-bundle integrations:
- Reconciliation banner on 10 base-layout pages (E T-E.3 retrofit; A-D inheritance).
- T-B.7 lucky_violation_R on Phase 6 review form (B elective).
- T-E.5 web-form snapshot capture at `/account/snapshot` (E elective).
- T-E.6 per-trade discrepancy indicator on `/trades/{id}` (E elective).

### Phase 11 candidate triage UNBLOCKED

Phase 11 triage owned by operator+orchestrator at next session. Pre-banked candidates enumerated at T-E.4 closer section (line 1788+):
- §8.4 Corporate_Actions MVP (standalone post-Phase-10).
- Schwab API Phase A integration.
- `mistake_cost_R_rolling_N_total` sum-class with bootstrap CI.
- Schwab inception-CSV ingestion.
- `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM semantic formalization.
- Orphan discrepancy detail surface.
- Per-cohort paused-interval filter (T-C.5 UI pattern reuse).
- 27 V2.1 §VII.F amendments triage.

### Cross-references

- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Phase 10 closer details (T-E.4 commit 4a666d1): bottom of this file at line 1788+.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md`.
- Post-Phase-10 standalone dispatch backlog: 2026-05-13 entries below (cleanup-script + test-runtime).

---

## 2026-05-13 Phase 10 Sub-bundle D ship: 5 spec amendments + 4 forward-binding lessons (FIRST PROVISIONAL/LIVE dynamic contract)

**Sub-bundle D SHIPPED 2026-05-13** at `a71cc24` (integration merge of `phase10-bundle-D-capital-maturity-funnel`). 12 commits = 7 task-impl (T-D.1..T-D.7) + 3 Codex-fix (R1+R2+R3) + 2 return-report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering. ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3045 worktree-side → 3147 (+102 net; upper end of +67..+104 projection; matches Sub-bundle A +128 / B +73 / C +84 overshoot precedent). S1 inline gate ~6:00 wall-clock. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **D1: Dispatch brief §0.8 PROVISIONAL/LIVE math wording.** Brief said `LIVE: denominator = max(capital_floor_constant_dollars, snapshot.equity_dollars)`. Plan §A.6 line 222 + the shipped `resolve_live_capital_denominator_dollars` (Sub-bundle A) return `snapshot.equity_dollars` directly (NO max-with-floor). Implementation followed plan + shipped code. **Amendment:** brief §0.8 wording should remove the `max()` qualifier.

2. **D2: Plan §A.19 SQL references `criterion_results.criterion_name`; actual schema is `candidate_criteria`.** Plan §A.19 lines 463-490 use `criterion_results cr ON cr.candidate_id ...` in the worked SQL example. Actual schema table (migration 0001:48) is `candidate_criteria` with the same column names. Implementation uses `candidate_criteria`. **Amendment:** plan §A.19 should match actual table name OR clarify the example is logical pseudo-schema.

3. **D3: Capital-friction trend window size not explicitly pinned.** Plan §G T-D.1 + spec §4.4 do not explicitly pin the multi-run trend window size for capital-friction (spec §4.4 only specifies "≥5 runs"). Implementation reused the funnel surface's 30-trading-session window for operator-readability parity. **Amendment:** plan §G T-D.1 wording — add explicit window-size lock.

4. **D4: `MaturityStageRow` carries `capital_denominator_dollars` + `capital_denominator_badge_text` fields not in plan §G T-D.3 acceptance.** Per Codex R1 M#1 + R2 M#1 fixes (verbatim plan §A.6 line 233 inline-text LOCK required visibility per-row), the dataclass gains both fields beyond what plan §G T-D.3 enumerated. **Amendment:** plan §G T-D.3 acceptance criteria.

5. **D5: `IdentificationFunnelPoint.aplus_take_rate_per_run` is NOT clamped to [0, 1].** Per Codex R1 M#3 fix, the rate is honestly emitted as `aplus_taken / aplus_id` without bounding. Plan §G T-D.5 + spec §3.6 say "proportion" implying [0, 1] in typical reading. **Amendment:** clarify "≥0; values >1 surface as data-quality anomaly signals (not clamped)" — see lesson #25.

### 4 forward-binding lessons for Sub-bundle E dispatch (return report §9; #23-#26 in cumulative catalog)

1. **#23 (NEW from D R1 M#1):** Plan-prescribed verbatim explanatory text MUST surface through a dedicated dataclass FIELD + template rendering target (NOT a `title="..."` hover-only attribute, which fails mobile + non-mouse usage AND loses audit-trail intent). Discriminating-test pattern: assert `data-{marker}=` substring in body PLUS assert `title="{format_prefix}"` substring absent. Forward-relevance for Sub-bundle E: process-grade-trend chart annotations + reconciliation badge text MUST follow this pattern.

2. **#24 (NEW from D R1 M#2):** Session-anchor read/write mismatch family extension — when a plan pins per-run aggregation on `pipeline_runs.started_ts.date()`, the implementation MUST use exactly that column (NOT `data_asof_date`, NOT `action_session_date`). These diverge on weekend/holiday runs in ways that silently drop or misbucket historical data points. Discriminating-test pattern: seed a row with `started_ts` and `data_asof_date` divergent, assert correct inclusion.

3. **#25 (NEW from D R1 M#3):** Bounded-range metrics MUST distinguish mathematically-bounded cases (e.g., `num <= denom` by SQL construction → rate ∈ [0, 1] guaranteed) from two-source aggregates (numerator + denominator independently computed → ratio can exceed 1 in anomaly cases). Clamping the latter HIDES data-quality issues. Pattern: bounded-by-construction → assert bounds; two-source → allow honest values + add anomaly badge surface. Forward-relevance for Sub-bundle E: process_grade aggregates may face the same.

4. **#26 (NEW from D R3 m#1):** SQL `ORDER BY` clauses on potentially-tied columns MUST include a deterministic tiebreaker (typically `id DESC`). Plan + Codex consistently catch nondeterminism in latest-record queries.

### Production-state observation (not blocking)

Maturity-stage surface renders 4 of 5 open positions (DHC/YOU/VSAT/CVGI shown; **LAR missing**). Production has 5 open trades per Phase 9 + Phase 10 prior gates. Root cause: `swing/data/repos/daily_management.list_open_position_active_snapshots(conn)` clamps to latest `data_asof_session` per trade; LAR has no recent daily_management snapshot covering current session. This is a **daily-management capture gap** at the operator-flow level, NOT a code regression. Operator may record fresh LAR snapshot via daily-management surface to surface LAR in maturity-stage.

### Post-merge state

- HEAD on main: `a71cc24` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (unchanged through Sub-bundles A+B+C+D).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle E executing-plans dispatch UNBLOCKED (CLOSES Phase 10).
- Cumulative pending V2.1 §VII.F amendment candidates: **22** entering Sub-bundle E (was 17 entering D; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (cleanest 4-bundle arc state in project history).
- 6 worktree husks pending cleanup-script (4 Phase 9 still-registered + 1 Sub-bundle C orphan + 1 Sub-bundle D orphan).

### Cross-references

- Sub-bundle D return report: `docs/phase10-bundle-D-return-report.md`.
- Sub-bundle D dispatch brief: `docs/phase10-bundle-D-executing-plans-dispatch-brief.md`.
- Plan §G (lines 1354-1550) consumed; AMENDED §A.6 + §A.7 + §A.18 + §A.19 + §A.20 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.

---

## 2026-05-13 Phase 10 Sub-bundle C ship: 5 spec amendments + 3 forward-binding lessons + cleanup-script gap surfaced

**Sub-bundle C SHIPPED 2026-05-13** at `a814006` (integration merge of `phase10-bundle-C-tier-and-deviation`). 8 commits = 5 task-impl (T-C.1..T-C.5) + 1 Codex-fix + 2 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (B + Phase 9 E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2961 worktree-side → 3045 (+84 new; ~3048 main post-merge from 2964 baseline; above projection +34..+56; matches Sub-bundle A +128 + B +73 overshoot precedent). Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **T-C.1 `cohort_relative_to_aplus` rendering.** Spec §3.3 row 147 defines as `cohort_expectancy_R / aplus_expectancy_R - 1` (delta proportion); dispatch brief §0.9 LOCK specified PERCENT raw-ratio `cohort_expectancy / aplus_expectancy * 100`. Implementation followed brief (binding implementer-facing artifact). Two semantically distinct metrics exist at the same numeric value: §3.3's "what fraction of A+ does this cohort achieve?" (0–200% typical) vs §3.7's "how far above/below A+" (-100% to +∞%). **Amendment:** spec §3.3 + §3.7 text should explicitly state rendering-unit semantics + the two-metric split.

2. **T-C.1 `cohort_doctrine_deviation_class` baseline enum value.** Spec §3.7 row 205 uses `"0"` as A+ baseline cohort's deviation class; implementation uses `"baseline"` string. Rationale: text field rendering; integer "0" would visually collide with the descriptive enum strings + operator's mental model that baseline IS a class label. Test pins `"baseline"` for A+. **Amendment:** cosmetic spec wording.

3. **T-C.5 filter SQL predicate.** Electives amendment §2 specified `resolution IS NULL`; schema reality (Phase 9 migration 0017) stores resolution as NOT NULL with sentinel `'unresolved'` enum default. Implementation uses `resolution = 'unresolved'` matching `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` Phase 9 Sub-bundle B convention. **Amendment:** electives amendment §2 wording.

4. **T-C.5 filter threading.** Amendment specified `CohortFilter` enum OR new bool param on tier + deviation VMs. Implementation chose bool throughout (compute + VM + route layers). Filter applied AT COMPUTE LAYER (before classification) so surface-locked cohort suppression cascade fires correctly when filter brings n<5. **Amendment:** minor; aligns with "new bool param" alternative.

5. **T-C.5 toggle href shape.** Amendment showed `<a href="/metrics/tier-comparison?exclude_discrepancies=1">` (absolute path). Implementation uses relative query href `<a href="?exclude_discrepancies=1">` + `<a href="?">` (Codex R1 M#1 fix). Relative form is more robust under mounted-app / root-path deployments. **Amendment:** illustrative-vs-binding-shape clarification.

### 3 forward-binding lessons for Sub-bundle D dispatch (return report §9; #20-#22 in cumulative catalog)

1. **#20: body-wide unit-substring assertions are non-discriminating when seed text contains the same substring** (e.g., decision-criteria contains literal `%` from "win rate > 30%"). Discriminating-test pattern: seed a specific worked example + assert the EXACT rendered numeric+unit substring at the cell location, NOT a body-wide `unit_string in body` check. Forward-relevance for Sub-bundle D: capital-friction percent-unit metrics + PROVISIONAL/LIVE badge text should follow this pattern.

2. **#21: toggle/filter links use relative query href** (`href="?key=value"` to set + `href="?"` to clear) rather than absolute path hrefs. Survives mounted-app / root-path deployments. Forward-relevance: capital-friction + identification-funnel + maturity-stage surfaces may need similar per-cohort or per-stage filter toggles.

3. **#22: per-cohort filters affecting cell suppression MUST be applied at compute layer** (before surface-locked suppression cascade fires). Applying at VM-layer post-compute would require duplicating suppression logic. Discriminating test: seed cohort with N>=5 where K trades have filter-trigger condition; filter-active brings cohort to (N-K) AND re-triggers suppression if (N-K) < surface floor.

### Cleanup-script gap surfaced (operator-decided 2026-05-13)

Operator verified the cleanup-script (`cleanup-locked-scratch-dirs.ps1`) catches **only orphaned** worktree dirs (deregistered from `git worktree list` but on-disk dir remains). Currently registered worktrees are by-design skipped (lines 215-234 short-circuit on `$isRegistered = $true`). The 4 remaining Phase 9 husks (B/C/D/E) are still registered and require `git worktree remove --force` first (deregisters; likely fails at on-disk delete due to ACL lock → produces orphan → script catches on next run). **Operator concurred with option 2: extend script with `-DeregisterFirst` switch** that drives `git worktree remove --force` against matched paths before orphan-discovery. **DEFERRED as separate orchestrator dispatch on `main`** (read-side, non-blocking, separate PR from Phase 10 sub-bundles). 5 husks pending after this dispatch (4 Phase 9 + new Phase 10 Sub-bundle C).

### Test-runtime concern surfaced 2026-05-13

Fast pytest suite at 3045 tests is 5:15 wall-clock (~103ms/test average; slow for unit-style). Orchestrator recommendation queued: (1) `pytest --durations=30` profile pass; (2) `pytest-xdist -n auto` parallelization (highest ROI; ~3-5x wall-clock reduction at zero coverage cost); (3) session-scoped schema fixtures audit. **DEFERRED as separate orchestrator dispatch.** Reduce-tests-with-coverage-preservation is the WRONG frame — each test exists as a discriminating-pin; the real lever is eliminating per-test fixture overhead.

### Post-merge state

- HEAD on main: `a814006` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B + C).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle D executing-plans dispatch UNBLOCKED.
- Pending V2.1 §VII.F amendment candidates cumulative: **17** entering Sub-bundle D (was 12 entering C; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (A+B+C clean record).

### Cross-references

- Sub-bundle C return report: `docs/phase10-bundle-C-return-report.md`.
- Sub-bundle C dispatch brief: `docs/phase10-bundle-C-executing-plans-dispatch-brief.md`.
- Plan §F (lines 1257-1334) consumed verbatim; AMENDED §A.7 + §A.18 + §A.5.1 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2 Task C.5: `docs/phase10-electives-amendment.md`.

---

## 2026-05-13 Post-Phase-10 standalone dispatches (deferred per operator decision; sequence AFTER Phase 10 Sub-bundles D + E ship)

Operator decision 2026-05-13 (mid-Phase-10, post-Sub-bundle-C-ship): two operational improvements surfaced during the Sub-bundle C dispatch + post-ship triage. Both are **read-side / infrastructure-side**, non-blocking for Sub-bundles D + E, and **DEFERRED as separate orchestrator dispatches AFTER Phase 10 completes** (Sub-bundle E ship closes the phase).

### Item 1 — Extend `cleanup-locked-scratch-dirs.ps1` with `-DeregisterFirst` switch

**Problem:** the script's worktree-orphan discovery (lines 215-234) currently catches ONLY orphaned worktree dirs (deregistered from `git worktree list` but on-disk dir remains due to Windows `.tmp/pytest-of-rwsmy/` ACL-lock pattern). Worktrees that are still registered in `git worktree list` are by-design skipped. The standard post-merge workflow is two-step: (a) operator/orchestrator runs `git worktree remove --force`; (b) if on-disk delete fails (ACL lock), the dir is now orphaned + the cleanup-script catches it on next run. Workflow gap: between step (a) and step (b), the operator's environment carries registered husks indefinitely if step (a) is skipped.

**Evidence:** at handoff 2026-05-13 mid-Phase-10, 11 worktree husks were pending operator cleanup-script per the handoff brief enumeration. After the operator's cleanup pass, 4 Phase 9 husks remained (B/C/D/E) because they were still git-registered (step (a) was never run on them). Operator confirmed cleanup-script-as-shipped does not catch them.

**Proposed extension:** add a `-DeregisterFirst` switch that drives `git worktree remove --force` against paths matching `^.worktrees/phase\d+-.*` (or accepts an explicit list) before the orphan-discovery pass. After deregistration completes, the existing orphan-discovery pass picks up the now-orphaned dirs + cleans them.

**Estimated effort:** ~30-45 min orchestrator-or-implementer dispatch on `main`. Read-side / infrastructure-side; no production-code impact; cannot conflict with Phase 10 sub-bundle worktrees (D + E will run on their own worktree branches with their own husks).

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids worktree-management changes mid-arc.

### Item 2 — Test-runtime analysis + improvements (zero-coverage-loss interventions)

**Problem:** fast pytest suite is at 3045 tests / ~5:15 wall-clock on Windows + Python 3.14 (Sub-bundle C post-ship). Per-test overhead average is ~103ms which is slow for unit-style tests (typical: 10-30ms). Going to ~3100+ tests at Sub-bundle D + E ship pushes past 6 min wall-clock. Operator surfaced 2026-05-13 the concern that approaching 3000 tests is making the dev-loop test-feedback latency painful.

**Wrong frame:** "reduce tests to retain coverage" — each test exists as a discriminating-pin for a Codex finding or regression-prevention assertion; deletion re-opens closed risks. The right frame is **eliminate per-test fixture overhead**, not test count.

**Recommended interventions in order of ROI (zero coverage loss):**

1. **Profile first (5 min, zero risk):** `pytest --durations=30` to identify the 80/20 hotspots. Without profiling, every other intervention is guessing.
2. **`pytest-xdist` parallelization (highest ROI; estimated ~3-5x wall-clock reduction):** single-line dependency add + `-n auto` in pyproject. With 8+ cores this is a 5 min → ~90s win at zero coverage cost. Risks: SQLite contention (file-based DBs need per-worker tmp dirs — `tmp_path_factory` already gives this); shared `pipeline_runs` lease tests need careful scoping. Most of the suite is already worker-safe by construction.
3. **Session/module-scoped schema fixtures:** large fraction of tests do `tmp_path → ensure_schema(conn) → seed → assert`. `ensure_schema` walks all 17 migrations on every call. Caching a fresh-DB template at session scope + `shutil.copy()` per test is ~10-50ms saved per test × thousands of tests = several minutes recovered. Medium-impact; fixture refactor required.
4. **TestClient lifespan audit:** `with TestClient(app) as client:` enters lifespan (starts `price_fetch_executor`); plain `TestClient(app)` does not. Many web tests use the `with` form even when they don't need the executor. Mechanical sweep.
5. **Audit duplicate discriminating-tests:** some Phase 9 + 10 Codex rounds added 2-3 tests pinning the same invariant via different fixtures. Manual audit; small wins; some risk of removing a real pin (requires careful per-test review).
6. **Move E2E integration tests behind `slow` marker:** `tests/integration/test_phase8_pipeline_walkthrough.py` already slow-marked. Audit `tests/integration/` for others. Doesn't reduce coverage, just reduces fast-suite footprint.

**Expected outcome:** profile + xdist together likely 5 min → ~1-1.5 min with zero coverage loss. Fixture-scope refactor adds another 30-60s reduction.

**Estimated effort:** ~1-2 hr orchestrator profile pass + ~30 min xdist integration + ~2-4 hr fixture-scope refactor if profile evidence warrants. Dispatch as a standalone read-side / infrastructure-side bundle.

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids test-runner / fixture changes mid-arc that could mask Codex-detectable regressions in Sub-bundle D + E.

### Cross-references

- Sub-bundle C return report §7 #7-#8 (this bundle surfaced the gap).
- Cleanup-script: `cleanup-locked-scratch-dirs.ps1` lines 215-234 (orphan-only discovery branch).
- Test-runtime baseline: 2964 → 3045 worktree-side at Sub-bundle C ship (~5:15 wall-clock).

---

## 2026-05-13 Phase 10 Sub-bundle B ship: 5 spec amendments + 2 forward-binding lessons + 4 V2 candidates banked

**Sub-bundle B SHIPPED 2026-05-13** at `6ed0f35` (integration merge of `phase10-bundle-B-trade-process-and-hypothesis-progress`). 9 commits = 7 task-impl (T-B.1..T-B.7 incl. T-B.7 elective) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — FASTEST Phase 10 chain (matches Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2895 worktree-side → 2951 (+73 new tests; +56 net; matches +46..+75 dispatch brief projection); 2899 → 2960 main HEAD. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (4 from return report §5 + 1 surfaced at orchestrator-driven gate)

1. **Plan §E Task B.1 acceptance text — `mistake_cost_R` aggregator source.** Plan said "prefer `review_log.total_mistake_cost_R` aggregate when present; fall back to per-trade compute when absent"; implementation always recomputes per-trade because `review_log` is **CADENCE-grain** (one row per daily/weekly/monthly review window covering N trades) with NO per-trade foreign key. The cadence aggregate CANNOT be cleanly mapped onto a cohort-grain sum at the metrics layer. Discriminating regression test `test_mistake_cost_R_recomputes_per_trade_ignoring_review_log_aggregate` pins the per-trade-recompute behavior. **Amendment:** plan §E Task B.1 should say "always re-compute via Phase 6 helpers; cohort-grain sum is reproducible from per-trade fields." V2 candidate: add `review_log_trade_links` audit table; cohort aggregator could then prefer frozen review-time values for already-reviewed trades + recompute only for unreviewed.

2. **Plan §E Task B.2 acceptance text — sentinel value for "All closed trades" toggle.** Plan didn't specify a URL-parameter sentinel. Implementation uses `__all__` as the sentinel (`?cohort=__all__`) to avoid collision with any legitimate cohort name containing the literal "all". Documented in the module docstring. **Amendment:** plan §E Task B.2 should include the sentinel choice explicitly.

3. **Plan §A.5.1 + spec §3.2 `cumulative_R_pct_of_capital` rendering unit.** Plan §A.5.1 specifies the metric as "proportion" (dimensionless); implementation stores + surfaces in **PERCENT units** (e.g., `-1.667` means `-1.667%`, NOT `-1.667 ratio` = `-166.7%`) because spec §3.2 `distance_to_absolute_loss_tripwire = absolute_loss_tripwire_pct - abs(min(0, cumulative_R_pct_of_capital))` requires comparing against `absolute_loss_tripwire_pct` which is in percent units per migration 0008 (e.g., `5.0` = `5%`). Conversion `sum(dimensionless ratios) * 100` happens inside `_build_cohort_vm`. **Amendment:** plan §A.5.1 + spec §3.2 should explicitly state the rendering unit.

4. **Electives amendment §2 Task B.7 acceptance text — existing display assumption.** Amendment said the new field renders "symmetrically alongside the existing `mistake_cost_R` display." Empirical verification of the Phase 6 template showed there was **NO pre-existing `mistake_cost_R` display** — only the operator-input form for `realized_R_if_plan_followed`. Implementation surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived display values in a new `<dl class="counterfactual-pair">` block placed BEFORE the existing form. Symmetric rendering criterion is met WITHIN the new block. **Amendment:** electives amendment §2 should be corrected: "the new block surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived per-trade display values; the existing form is unchanged."

5. **(GATE-SURFACED 2026-05-13)** **Plan §E Task B.2 acceptance text — cohort-tab enumeration scope.** Plan said `test_vm_renders_4_cohort_tabs_plus_all_toggle` expecting "5 tabs total" (4 registered + "all"). Implementation surfaces 7 tabs at production gate (4 pre-registered + 2 orphan-label + "All") because production has 2 orphan-labeled closed trades ("inaugural trade test" with 1 closed VIR + "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness" with 2 closed). Hiding orphan-labeled cohorts would hide closed-trade data from the operator. **Sensible deviation; not banked in return report but caught at orchestrator-driven S2 gate via Chrome MCP read_page.** **Amendment:** plan §E Task B.2 should say "render tabs for ALL distinct `hypothesis_label` values across closed trades (registered + orphan) + "All" toggle; default-active is FIRST registered cohort regardless of orphan presence."

### 2 forward-binding lessons for Sub-bundle C dispatch (return report §8)

1. **Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK.** Sub-bundle B R1 Major #1 surfaced the mismatch between `review_log` (cadence-grain, no trade FK) and cohort-grain `mistake_cost_R` sum. If Sub-bundle C (tier-comparison + deviation-outcome) or future sub-bundles encounter similar cadence-grain audit columns (e.g., `reconciliation_runs.summary_json` for cohort-grain "data-quality" gating), document the mismatch + always re-compute from per-trade source data. **Discriminating-test pattern** (canonical regression-pin): plant a conflicting cadence row + assert metric reflects per-trade compute, NOT the planted aggregate. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #18.

2. **Unit-semantic precision needs explicit rendering pin (percent vs proportion).** Sub-bundle B's `cumulative_R_pct_of_capital` rendered in PERCENT units to match the `absolute_loss_tripwire_pct` comparison. Future tier-comparison metrics (`cohort_relative_to_aplus`, `cohort_expectancy_relative_to_aplus_pct`) likely face the same: explicit rendering-unit pin in the VM + template + discriminating test is required at writing-plans time. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #19.

### 4 V2 candidates banked (return report §7)

1. **`review_log_trade_links` audit table** — would unlock cadence-prefer for already-reviewed trades; recompute only for unreviewed. Connects to Phase 11 candidate scoping.
2. **Per-cohort "exclude paused-interval trades" filter** — same UI pattern as Sub-bundle C's T-C.5 "exclude trades with unresolved discrepancies" filter family. Sub-bundle C may surface the reuse pattern when T-C.5 lands.
3. **`mistake_cost_R_per_trade` Class B representation alongside cohort sum** — implementation surfaces BOTH `MetricCellB` (Class B mean) AND `PointMetricCell` (cohort sum); spec §3.1 only enumerates "cohort sum." V2 candidate: clarify spec or drop the Class B representation if redundant.
4. **`canonicalize_hypothesis_label` query-time canonicalization** — `list_trades_for_cohort` already canonicalizes; verify that `count_per_cohort` orphan-label fallback path also canonicalizes (current implementation uses the registry's stored name directly + the orphan label as-is from `trades.hypothesis_label`). Edge case: an orphan trade with a non-canonicalized stored label might appear separately from a canonicalized-form match. Low risk in V1 (writer canonicalizes at persist time); banked for V2 audit.

### Post-merge state

- HEAD on main: `6ed0f35` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle C executing-plans dispatch UNBLOCKED.
- Sub-bundle B added 4 new sub-VM exclusions to `tests/web/test_view_models/test_base_layout_vm_coverage.py::_SUB_VM_EXCLUSIONS`: `CohortTabVM`, `CohortProgressVM`, plus the existing `ConfidenceBadgeVM` / `ProvisionalBadgeVM` / `SuppressionRowVM`. Sub-bundle C dispatch brief should propagate the pattern: new sub-VMs ending in `VM` that compose into a page VM (not BaseLayoutVM-extending) should be added to the exclusion set in the same commit.

### Cross-references

- Sub-bundle B return report: `docs/phase10-bundle-B-return-report.md`.
- Plan §E (lines 1063-1254; AMENDED at integration triage per amendments #1, #2, #5 above + §A.5.1 percent-unit clarification #3).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2: `docs/phase10-electives-amendment.md` (amendment #4 above corrects "existing display" assumption).
- Sub-bundle C dispatch brief: TBD (orchestrator drafts post-merge; will propagate T-C.5 elective + 2 NEW forward-binding lessons + Sub-bundle A AMENDED §A.7 interface).
- Pending V2.1 §VII.F spec amendments cumulative count: **12** (2 Phase 9 D/E + 3 Sub-bundle A + 4 Sub-bundle B return-report + 1 Sub-bundle B gate-surfaced + 2 Sub-bundle A return-report orphans-from-Phase-10-spec).

---

## 2026-05-13 Phase 10 Sub-bundle A ship: spec amendments + forward-binding lessons + V2 candidates banked

**Sub-bundle A SHIPPED 2026-05-13** at `096de83` (integration merge of `phase10-bundle-A-shared-honesty-utility`). 15 commits = 11 task-impl + 3 Codex-fix + 1 return-report; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR; ZERO Critical + ZERO ACCEPT-WITH-RATIONALE; +128 fast tests (2767 → 2895); ruff 18 unchanged; schema v17 unchanged.

### 3 V2.1 §VII.F amendment candidates (plan-text corrections; banked from return report §8)

1. **Plan §D Task A.1 Wilson CI reference value drift.** Plan acceptance criterion locked `k=2,n=4 → [0.094, 0.901]` (Wilson-with-continuity-correction); implementation chose standard Wilson (yields `[0.150, 0.850]`); plan's other two reference values `k=0,n=20 → [0.000, 0.161]` + `k=20,n=20 → [0.839, 1.000]` match standard Wilson exactly. Plan §D Task A.1 should be amended to either (a) correct the k=2,n=4 reference to `[0.150, 0.850]` (matches standard Wilson; downstream comparable to `statsmodels.stats.proportion_confint(method='wilson')`); OR (b) explicitly require Wilson-with-continuity-correction + update implementation. Implementer chose (a) per Wikipedia primary formula + statsmodels-default alignment. **V2.1 §VII.F routing recommended:** standalone amendment dispatch or fold into Phase 10 plan revision.

2. **Plan §A.5 `read_at_trade_time_policy` signature.** Plan signature `read_at_trade_time_policy(conn, *, trade: Trade) -> RiskPolicy` assumes `Trade` dataclass carries `risk_policy_id_at_lock` field. Phase 9 Sub-bundle A added the column via ALTER but did NOT extend `Trade` dataclass (`_TRADE_SELECT_COLS` in `swing/data/repos/trades.py` omits it). Implementation signature is `read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` with two convenience accessors `get_trade_policy_id_stamp(conn, *, trade_id: int)` + `get_review_policy_id_stamp(conn, *, review_id: int)` added in `swing/metrics/policy.py`. Sub-bundle B consumers fetch the stamp from DB then pass into resolver. Plan §A.5 to be amended to match implementation; OR alternatively V2-disruptive option: extend `Trade` dataclass to include `risk_policy_id_at_lock` (every existing consumer accepts new field).

3. **Plan §A.6 `BaseLayoutVM.stale_banner` type.** Plan says `stale_banner: bool = False`; implementation chose `stale_banner: str | None = None` to match existing base-layout VM pattern (`DashboardVM`/`PipelineVM`/`JournalVM`/`WatchlistVM`/`ConfigVM` all use `str | None`). `base.html.j2` renders `{% if vm.stale_banner %}` + included partial does `{{ vm.stale_banner }}` (substitutes banner text). With `bool = False` the rendered banner would be literal "True"/"False" text. Plan §A.6 to be amended to `str | None = None`.

### Plan §A.7 + §D Task A.1 amendments ALREADY APPLIED in-tree

Codex R2 + R3 caught the SAME failure-mode twice (plan-text drift from code interface changes). Implementer amended plan §A.7 + §D Task A.1 IN THE WORKTREE during Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). These are NOT pending amendments — they LANDED at merge `096de83`. The 3 candidates above are SEPARATE from those (plan-text-vs-impl divergences caught at return-report-time, not at Codex-time).

### 2 forward-binding lessons for Sub-bundle B+ dispatch (banked from return report §10)

1. **Plan §A.7 binding-interface amendments flow into plan text in SAME commit as code change.** Codex R2 Major #1 + R3 Major #1 in Sub-bundle A caught the SAME failure-mode twice: code-level interface changes (adding `HonestyBadges.window_not_full_warning` in R1; making `badges_for_n` public in R1) were NOT reflected in binding plan §A.7 text, even though Sub-bundles B-E read §A.7 as binding. **Pre-empt for Sub-bundle B+ dispatch brief §0.5:** when implementer changes any §A.7-listed interface element (HonestyBadges fields, function signatures, Decoupling discipline assignment), update plan §A.7 IN THE SAME COMMIT. Brief watch item: "if implementer adds new public function / dataclass field / signature param in `swing/metrics/honesty.py`, plan §A.7 binding interface MUST update in-tree to match."

2. **Statistical helpers with multiple textbook-correct variants need explicit spec pin at writing-plans time.** Wilson CI standard-vs-continuity-correction divergence (deviation #1 above) is a textbook ambiguity. Plan §A.7 cited "Wikipedia formula" but Wikipedia documents BOTH variants; plan's reference values mixed the two. **Pre-empt for future writing-plans dispatches:** any statistical helper that has multiple textbook-correct implementations (Wilson CI, bootstrap CI tail-handling, bias-correction, Wilson-vs-Agresti-Coull, etc.) needs an EXPLICIT formula pin in the plan with a citation to Wikipedia section, scipy/statsmodels function name, or equivalent. Add to writing-plans §5 watch items: "for statistical helpers, plan §A.7 names the SPECIFIC variant + cites Wikipedia/scipy/statsmodels function name to disambiguate."

### 2 V2 candidates banked (from return report §7)

1. **`count_unresolved_material` widen to include orphan-emit discrepancies.** Current implementation returns ONLY trade-attributed discrepancies (underlying repo helpers JOIN on trades). Orphan-emit discrepancies (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id from Phase 9 Sub-bundle D's sector_tamper audit + Sub-bundle C's equity_delta) are EXCLUDED from the count. Discriminating regression test `tests/metrics/test_discrepancies.py::test_count_unresolved_material_excludes_orphan_emit_no_trade` pins V1 behavior. V2 could widen via separate sub-query joining on the run-attribution side.

2. **`render_class_d` "point" branch hardcodes sum semantics.** Implementation hardcodes sum semantics per §A.21 + §J.1.1 for `mistake_cost_R_rolling_N_total`. Other future "point" callers (if any) needing mean semantics would need a new helper or a parameter to switch aggregation. Banked at the §A.21 V2.1 §VII.F amendment candidate; consider when Sub-bundle E lands the §3.8 process-grade-trend surface.

### Post-merge state

- HEAD on main: `096de83` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert; `max_account_risk_per_trade_pct=0.5` cfg-aligned per operator decision 2026-05-13). Policy chain: 1 (seed) → 2 (operator test) → 3 (S2.bis divergence) → 4 (S2.bis revert) → **5 (Option C revert; ACTIVE)**.
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle B executing-plans dispatch UNBLOCKED.

### Cross-references

- Sub-bundle A return report: `docs/phase10-bundle-A-return-report.md`.
- Plan §A.7 + §D Task A.1 (AMENDED in-tree at `e32f71c` + `75dd63f`).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md` (Sub-bundle B will propagate T-B.7 elective).

---

## 2026-05-13 §8.4 Corporate_Actions MVP — standalone post-Phase-10 dispatch (deferred per Phase 10 electives amendment)

**Decision (operator 2026-05-13 post-Phase-10-writing-plans-merge):** §8.4 Corporate_Actions MVP defers to a standalone post-Phase-10 dispatch. Phase 10 plan §A.0 ZERO-new-schema lock preserved; Phase 10 V1 arc shape stays at 5 sub-bundles A→B→C→D→E with 39 tasks (4 other electives propagated; see `docs/phase10-electives-amendment.md`).

**Scope when dispatched (per Phase 10 spec §8.4 + plan §A.4 cost estimate):**
- New `corporate_actions` table: columns approximately `(id, ticker, action_type, action_date, ratio_numerator, ratio_denominator, notes, recorded_at, source)`. Action types: `split`, `dividend`, `ticker_change`, `delisting`. `0018_*.sql` migration bumping `EXPECTED_SCHEMA_VERSION` 17 → 18.
- New CLI surface: `swing corporate-action {record,list,resolve}` group (mirrors Phase 9 `swing journal discrepancy` shape).
- Manual reconcile flow: operator-driven; defensive logging only; NO automated price-adjustment in V1 (per spec §8.4 recommendation).
- Estimated ~3-6hr executing-plans wall-clock; brainstorm + writing-plans + executing-plans full cycle since schema work merits independent Codex rigor.

**Rationale for standalone (not Phase 10 V1):**
- Phase 10 V1 is read-side dominant (metrics dashboard atop v17 schema); §A.0 ZERO-new-schema lock was a Codex-converged 6-round decision.
- Bundling §8.4 into Phase 10 V1 as "Sub-bundle F" would break the §A.0 lock + add ~3-6hr + 1 new table + 1 CLI surface to the executing-plans arc. Operator chose to preserve §A.0 lock + preserve Phase 10 arc shape.
- §8.4 ships first among Phase 11 candidates (along with Schwab API Phase A, inception-CSV ingestion, snapshot semantics formalization — see Phase 10 plan §10 hand-off + return-report §10).

**Sequencing:** standalone dispatch unblocks AFTER Phase 10 V1 closes (all 5 sub-bundles A→B→C→D→E integrated). Standalone dispatch may run in parallel with other Phase 11 candidates per orchestrator + operator triage.

**Cross-references:**
- Phase 10 spec §8.4 (orchestrator-decision open question; brainstorm recommendation = DEFENSIVE log-only).
- Phase 10 plan §A.4 disposition (default DEFER; operator decision 2026-05-13 confirms defer-as-standalone).
- Phase 10 electives amendment `docs/phase10-electives-amendment.md` §5.
- v1.1-alternate F-019 corporate-action interaction concern (anchored spec §8.4 risk framing).

---

## 2026-05-12 Phase 9 closer: Sub-bundle E lessons banked + Phase 10 writing-plans hand-off note

**Phase 9 arc SHIPPED 2026-05-12** (Sub-bundles A → B → C → D → E). Bundle E shipped as `phase9-bundle-E-polish-and-phase10-handoff` worktree dispatch (T-E.0 combined E2E happy path + T-E.1 CLAUDE.md gotcha promotion ratification + T-E.2 this hand-off note + T-E.3 cross-bundle Account Order History multi-line parser fix). Plan §H Task E.2 acceptance verified: `ruff check swing/ --statistics` returns 18 E501 (unchanged from Sub-bundle A baseline; zero new violations across A+B+C+D+E).

### Phase 10 writing-plans hand-off (binding inputs from Phase 9 spec §11)

Phase 10 writing-plans dispatch follows Phase 9 close. Phase 9 design choices Phase 10 needs to know about:

**§11.1 Risk_Policy as the source for metric defaults at dashboard read-time.** Phase 10 dashboard reads LIVE policy (`risk_policy.is_active=1`) for: `low_sample_size_threshold_class_*_n` (suppression at render); `global_confidence_floor_n` (n=20 floor); `bootstrap_resample_count` (CI computation); `process_grade_weight_*` (weight reconstitution if stamp absent on legacy review_log rows). Phase 10 dashboard reads AT-TRADE-TIME policy (`trades.risk_policy_id_at_lock`) for: `capital_floor_constant_dollars` (preserves historical-trade interpretation under capital-floor change); `scratch_epsilon_R` (preserves win/loss/scratch classification under threshold change); trade-grain metrics that need policy-as-of-trade-time semantics. Locked decision per spec §3.1.1: the per-row stamp on trades + review_log enables this at-trade-time vs live-time distinction. **Schema ready; Phase 10 wires the queries.**

**§11.2 Reconciliation discrepancy surface for metrics-data-quality reporting.** Phase 9 ships `reconciliation_runs` + `reconciliation_discrepancies` + the canonical query `list_unresolved_material_for_active_trades` (with closed-trade companion). Phase 10+ writing-plans may add a "reconciliation status" badge on dashboard / journal review surfaces. Recommended Phase 10+ surfaces: (a) dashboard top "N unresolved material discrepancies" badge (links to discrepancy list); (b) per-trade detail "Trade X has unresolved reconciliation discrepancies" indicator; (c) per-cohort metrics view optional filter "exclude trades with unresolved discrepancies" for sample-purity. **Schema scopes the LEFT JOIN pattern per spec §5.3; Phase 10+ implements the rendering.**

**§11.3 Hypothesis status history surfaces.** Phase 10 §3.2 surfaces "single most-recent transition only" in V1; full history requires Phase 9's `hypothesis_status_history` audit table. Phase 10 writing-plans uses the new table to render: (a) per-hypothesis transition timeline (active → paused → active → closed-target-met); (b) cohort-level "active period" calculations (excludes paused intervals from rate-metric numerators if operator opts in). **Schema sufficient; Phase 10 wires the queries via `list_history_for_hypothesis` + cohort-aggregation helpers.**

**§11.4 account_equity_snapshots resolution for `live_capital_denominator_dollars`.** Phase 10 §6.2 + §3.4 capital-friction metrics depend on a unified denominator. Phase 9 ships the table + the source-ladder discipline (schwab_api > tos_csv > manual). Phase 10 metric layer resolves:

```sql
live_capital_denominator_dollars(asof_date) :=
  COALESCE(
    (SELECT equity_dollars FROM account_equity_snapshots
       WHERE snapshot_date <= asof_date
       ORDER BY snapshot_date DESC,
                CASE source WHEN 'schwab_api' THEN 1
                            WHEN 'tos_csv' THEN 2
                            WHEN 'manual' THEN 3 END ASC
       LIMIT 1),
    (SELECT capital_floor_constant_dollars FROM risk_policy WHERE is_active = 1)
  )
```

Source ladder enforces broker-authoritative > csv > manual when same date has multiple rows. Fallback to `risk_policy.capital_floor_constant_dollars` when no snapshot exists at-or-before asof_date (Phase 10 §2 split-policy PROVISIONAL). **`get_latest_snapshot_on_or_before` already implements the source-ladder + provenance; Phase 10 consumes it.**

**§11.5 Phase 9 capture-needs already accommodated for Phase 10.** Phase 10 §6.3 enumerated capture-needs beyond Phase 8/9 plans: (a) per-pipeline-run capital-utilization aggregate — Phase 10+ writing-plans territory; uses Phase 9 `account_equity_snapshots` for live denominator; NOT a Phase 9 column; (b) benchmark series capture (Phase 10 §8.3 open question) — OUT of Phase 9 scope; orchestrator triages separately; (c) Corporate_Actions MVP (Phase 10 §8.4 open question) — OUT of Phase 9 scope; orchestrator triages separately; (d) daily account equity capture (Phase 10 §8.2 open question) — SATISFIED by Phase 9 `account_equity_snapshots`.

### Phase 9 final ruff sweep (T-E.2 acceptance criterion 1)

`ruff check swing/ --statistics` returns **18 E501** (line-too-long only). Unchanged from:
- Pre-Phase-9 baseline at HEAD `622c669` (verified 2026-05-11 in Phase 9 writing-plans return report §6).
- Sub-bundle A landing at `6c8f3a9`.
- Sub-bundle B landing at `e96834a`.
- Sub-bundle C landing at `e5d5892`.
- Sub-bundle D landing at `4894688` + housekeeping `6ba1925`.
- Sub-bundle E task family commits.

**Phase 9 introduces ZERO new ruff violations** across +500+ lines of consumer-side code + 5 new tables' worth of repo functions + 4 new service modules + ~430+ new fast tests.

### Phase 9 closing summary (for orchestrator)

- 5 sub-bundles SHIPPED across 2026-05-12 (one calendar day end-to-end).
- ~430+ new fast tests across the arc; cumulative fast suite 2462 → ~2766 at Bundle E close.
- Schema version v16 → v17 in atomic landing at Sub-bundle A T-A.1; v17 unchanged through B/C/D/E (consumer-side only).
- 1 single ACCEPT-WITH-RATIONALE position banked across the arc (Sub-bundle C R1 M#1 equity_delta sign convention; brief-vs-spec cosmetic — implementation correctly followed spec).
- 6 CLAUDE.md gotchas promoted (3 Sub-bundle A at `de10601` + 2 Sub-bundle D at `6ba1925` + 1 Sub-bundle E at T-E.1).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle D's §7 supersession to chart_pattern-mirror hidden-anchor pattern; recon doc `docs/phase9-bundle-D-task-D0-recon.md` carries the binding design).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle E T-E.3's §6.2 supersession to multi-line group parser; recon doc `docs/phase9-bundle-E-task-E3-parser-recon.md` carries the binding design).
- 2 V2 candidates banked at this file (Schwab inception-CSV ingestion; account_equity_snapshots semantic formalization).

**Phase 10 writing-plans dispatch is unblocked.** Orchestrator queues Phase 10 writing-plans next per spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-dashboard-design.md`. Brainstorm already SHIPPED 2026-05-06 at `fe6cb45`. Phase 10 reads this hand-off note's binding inputs.

---

## 2026-05-12 Phase 9 Sub-bundle D/E candidate: Schwab "since-inception" Account Statement ingestion

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Operator's "since-inception" Schwab Account Statement export `thinkorswim/2026-05-12-AccountStatementInception.csv` is structurally richer than the 7-day Account Statement Bundle B's `extract_account_summary_net_liq` (T-C.6) consumes. The inception export's full section inventory:

| Section | Bundle B/C consumes | V2 ingestion candidate use |
|---|---|---|
| Cash Balance (full inception history) | partially (cash_movements only) | seed `cash_movements` retroactively from inception; reconcile against existing rows for any pre-Phase-7 gaps |
| Account Order History | yes (Bundle B `extract_stop_orders` — banked Bundle E parser-gap fix pending) | richer inception sample for the Bundle E parser fix's regression corpus |
| Account Trade History | partially (Bundle B's `extract_stock_fills`) | full-history fill reconciliation against the journal's `fills` table for any pre-Phase-7 gaps |
| Equities (current open positions snapshot) | no | could seed `position_qty_mismatch` baselines or feed Phase 10 dashboard's open-position MTM |
| Profits and Losses (per-position YTD aggregates) | no | could seed `realized_R` cross-checks against Phase 6 `review_log` aggregates |
| Account Summary (current Net Liq + buying power) | yes (Bundle C T-C.6 `extract_account_summary_net_liq`) | unchanged |

**Concrete use cases:**

1. **Cash movements historical seed.** Bundle B's reconciliation already extracts cash_movements from any TOS export. The inception export covers the full history; ingesting it would seed the `cash_movements` table with deposits/withdrawals since account inception (verified via the operator-witnessed gate: 2 deposits of $100 each on 3/30/26 + 4/29/26 totaling $200 are in the production cash_movements; inception export would surface the same + any prior we missed).
2. **Account equity snapshots historical series.** Per-statement Net Liq values from prior monthly statements could seed an `account_equity_snapshots` historical series, giving Phase 10 metrics dashboard a real cash-basis vs MTM trajectory rather than just current point-in-time.
3. **Fills audit against the journal.** Account Trade History since inception could audit the `fills` table for any pre-Phase-7 fills missing from the journal (especially historical trades where operator may not have manually backfilled).
4. **Equity_delta historical baseline.** Bundle C's T-C.6 wires equity_delta for present-day reconciliation; an inception ingestion could backfill equity_delta history.

**Scope notes:**

- The existing `swing/journal/tos_import.py` parsing infrastructure is already there for the 7-day export shape. The inception export uses the same column structures + section headers (verified during operator-witnessed gate); the diff is the date range (full inception vs 7 days). The parser may "just work" against the inception export with minor section-specific handling.
- Section "Profits and Losses" is NEW to consume — not currently parsed. Would need a new extractor.
- Section "Equities" (current open positions snapshot) is NEW to consume — not currently parsed (Bundle B's `extract_equity_positions` parses ONLY the qty column for `position_qty_mismatch`; the Trade Price + Mark + Mark Value columns are not extracted).
- The 4 prior sample exports in `thinkorswim/` are 7-day; the inception export is the first multi-month sample. Bundle D/E or post-Phase-9 work could leverage it.

**Cross-references:**
- Schwab inception export: `thinkorswim/2026-05-12-AccountStatementInception.csv` (untracked, ~20 KB).
- Operator-witnessed gate Sub-bundle C 2026-05-12 — equity reconciliation discussion that surfaced this candidate.
- Bundle B's `extract_stop_orders` + `extract_stock_fills` + `extract_equity_positions` + Bundle C's `extract_account_summary_net_liq` in `swing/journal/tos_import.py`.
- Phase 10 metrics dashboard (brainstorm `fe6cb45`; writing-plans pending post-Phase-9) §3 `live_capital_denominator_dollars` (R1 M2 + R3 M1 lock) — would benefit directly from historical cash basis + MTM series.
- V2.1 §VII.F source-of-truth correction protocol (if ingestion changes invariants).

**Operator-paced; not orchestrator-blocking.** Phase 9 Sub-bundles D + E + Phase 10 brainstorm are higher-priority; this ingestion candidate sequences behind in-flight phases.

---

## 2026-05-12 Phase 9 / V2 candidate: account_equity_snapshots semantic formalization (cash-basis vs net-liq)

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Bundle C's T-C.6 equity_delta wiring revealed a semantic ambiguity in `account_equity_snapshots.equity_dollars`. The operator stored `$2000` representing "cash basis since inception" (deposits − withdrawals); Schwab's Account Summary reports `$2014.36` as Net Liquidating Value (cash basis + realized P&L + unrealized MTM). The equity_delta column then surfaces as ≈ -(YTD P/L) which is informative but ambiguous — the operator must mentally distinguish what `equity_dollars` meant when each snapshot was taken.

**Concrete impact:**

If Bundle C had stored `$2014.36` (MTM), equity_delta would be near zero and the comparison would surface only Schwab-vs-journal drift (e.g., parser-gap stops, missing fills). If it stored `$2000` (cash basis), equity_delta ≈ Schwab's YTD P/L — informative for "where is my P&L?" but not the spec's apparent intent (which is "where do my equity numbers disagree?").

The operator's clarification post-gate established that V1 stored cash basis, not MTM — but V1's spec/CLI doesn't force the disambiguation. Future operator could store either value at different times, producing inconsistent equity_delta interpretation.

**V2 hardening options:**

1. **Add `kind` discriminator** to `account_equity_snapshots` (`'cash_basis'` / `'net_liq'` / `'cash_balance'` — 3-value CHECK enum). Bundle B's reconciliation T-C.6 then compares like-to-like: if snapshot is `kind='net_liq'`, compare directly to Schwab's Net Liq; if `kind='cash_basis'`, compute expected_net_liq = cash_basis + realized + unrealized (using journal-computed P&L) and compare to Schwab's Net Liq. Equity_delta becomes meaningful regardless of kind.
2. **Distinct columns** instead of `kind` discriminator: `equity_cash_basis_dollars`, `equity_net_liq_dollars`, `equity_cash_balance_dollars`. Operator inputs whichever they have visibility into; reconciliation does multi-axis comparison.
3. **Auto-derive cash basis from `cash_movements`.** If `cash_movements` is fully populated (deposit / withdrawal kinds), cash basis = SUM(deposit amounts) − SUM(withdrawal amounts). Then operator doesn't even need to input cash basis — only MTM observations. Requires the Schwab inception-CSV ingestion above to seed cash_movements fully.
4. **Defer / accept V1.** Keep `equity_dollars` ambiguous; document operator convention in CLI help text + operator-facing reference; resolve via Phase 10 metrics dashboard's prescribed convention.

**Recommendation:** option 3 (auto-derive cash basis from `cash_movements`) sequenced AFTER the Schwab inception-CSV ingestion task above. Cleanest data model + lowest operator burden. Option 1 (kind discriminator) is a fallback if cash_movements completeness can't be guaranteed.

**Cross-references:**
- Bundle C return report §6 (R1 M#1 equity_delta sign convention ACCEPT-WITH-RATIONALE).
- Bundle C operator-witnessed gate S6 + post-gate equity reconciliation discussion 2026-05-12.
- Spec `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` §3.5 + §3.2 + §3.3.1 equity_delta JSON shape.
- Phase 10 metrics dashboard `live_capital_denominator_dollars` spec (R1 M2 + R3 M1 lock) — uses similar split semantic (constant vs live).

**Operator-paced; not orchestrator-blocking.** Sequences behind Schwab inception-CSV ingestion (above) for option 3 path.

---

## 2026-05-12 Phase 9 Sub-bundle E polish: Account Order History multi-line parser gap (operator-witnessed gate finding)

**Observation (operator-witnessed gate finding 2026-05-12):** Phase 9 Sub-bundle B's `stop_mismatch` detection emitted 5 false-positive discrepancies during the operator-witnessed gate when reconciling the operator's real-world Schwab/TOS export `thinkorswim/2026-05-12-AccountStatement.csv` against the production journal. All 5 open trades (DHC/YOU/VSAT/CVGI/LAR) were flagged "no broker working stop" despite working stops being placed at Schwab with prices matching journal `current_stop` values exactly.

**Root cause:** Bundle B's `extract_stop_orders` in `swing/journal/tos_import.py` per spec §6.2 looks narrowly for `STP` in the order_type column. Real-world Schwab/TOS Account Order History exports use a **2-line group** structure per working order:

```
,,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,CVGI,,,STOCK,~,MKT,GTC,WORKING
,,,RE #1006290692715,,,,,,,,4.36,STP,STD,
```

The header line carries `order_type=MKT` + `price=~` + `time_in_force=GTC` + `status=WORKING`. The continuation row carries the STP trigger price + `STP STD` qualifier. The parser only sees the header line and concludes "no STP order" — missing the actual trigger price in the continuation row.

Additional patterns observed across the 4 sample exports in `thinkorswim/`:

| File | Pattern | Notes |
|---|---|---|
| 2026-04-15 | (no Account Order History rows) | empty section — operator had no working orders on that date |
| 2026-04-30 (CC) | 3-line group: header + `TRG BY #ID BASE-6.74 STP STD` + `20.51 STP` | Conditional trigger (base-price relative) chained with absolute stop trigger |
| 2026-05-08 (DHC) | header `MKT GTC WAIT TRG` (no continuation) | Conditional order not yet armed; status `WAIT TRG` not `WORKING` |
| 2026-05-08 + 2026-05-12 | header `MKT GTC WORKING` + continuation `<price> STP STD` | Canonical 2-line stop-market group |
| various | header `MKT GTC CANCELED` | Correctly skipped (not WORKING) |

**Bundle E acceptance criteria:**

1. **Multi-line grouping.** Rewrite `extract_stop_orders` (or introduce a streaming-grouper) to read the Account Order History section as **order groups** — header row + N continuation rows until the next dated header row OR section boundary.
2. **Stop trigger extraction from continuation.** When the continuation row contains `STP STD` (or just `STP` per Schwab's column conventions), read the trigger price from the price column. Handle both simple absolute (`4.36 STP STD`) and conditional `TRG BY #ID BASE-X.XX STP STD` + absolute trigger row variants.
3. **Status filter widening.** Include `WAIT TRG` alongside `WORKING` — both indicate a placed-but-not-yet-filled stop. `CANCELED` and `FILLED` correctly remain excluded.
4. **Backwards compatibility.** Existing fixture-based discriminating tests (boundary delta=0/0.005/0.01/0.02 + 3 stop_mismatch sub-cases) MUST still pass. Add new fixture CSVs at `tests/fixtures/tos/` capturing the multi-line pattern variants observed in the operator's 4 sample exports.
5. **Regression test against operator's real-world exports.** Add a new fast-test that reconciles `thinkorswim/2026-05-12-AccountStatement.csv` against a fixture journal with the matching open trades + asserts ZERO stop_mismatch discrepancies emitted (the matching path). Mirror for the 2026-05-08 export (with `WAIT TRG` DHC).
6. **Spec §6.2 amendment.** Update spec text to reflect the 2-line group structure (currently spec assumes 1-row STP rows). Brief explicitly notes the spec text was a brainstorm-time approximation; the migration + production reality require the 2-line parse.

**Scope:** ~3-4 hr implementation. Single-task dispatch suitable for inline orchestrator OR a small implementer dispatch. Sub-bundle E's existing scope (E2E happy path + CLAUDE.md gotcha promotion + Phase 10 hand-off prep per plan §H) absorbs this naturally as a new task T-E.0.bis or T-E.3.

**Operator-side action items pending parser fix:**

- The 5 `acknowledged_immaterial` resolutions on discrepancies 1-5 in production DB stand as the V1 disposition. Operator should re-reconcile after Bundle E ships to confirm the matching path produces zero stop_mismatch findings.
- Real-world fixture corpus at `thinkorswim/*.csv` is currently untracked (in project root, not in `data/finviz-inbox/` or `tests/fixtures/tos/`); Bundle E should formalize the corpus location (copy a subset to `tests/fixtures/tos/schwab-real-world-*.csv` for the regression tests; keep the originals untracked at the operator's working location).

**Cross-references:**

- Sub-bundle B return report `docs/phase9-bundle-B-return-report.md` (merge `e96834a`).
- Operator-witnessed gate findings: §S4 of Sub-bundle B gate, 2026-05-12.
- Spec §6.2 + §3.3.1 expected_value/actual_value JSON shapes for `stop_mismatch`.
- Bundle B parser current implementation: `swing/journal/tos_import.py` (the `extract_stop_orders` function — verified single-line per the current spec; gap is the multi-line group recognition).
- Prior 3e.12 tos-import diagnostic fixed multi-day `Exec Time` parsing (commit `a9541d2`) — similar real-world-export-structure investigation pattern.

---

## 2026-05-12 Low priority: Minervini + body-of-knowledge reference review vs current strategy implementation

**Observation (operator-surfaced 2026-05-12; SCOPE EXPANDED 2026-05-13):** New methodology reference artifacts landed in two locations:

`reference/minervini/`:
- `896159773-Minervini-Trading-Strategy-Deep-Dive.txt` — 91 KB summary of SEPA.
- `Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf` — Minervini's second book (~6 MB).
- `think-and-trade-like-a-champion.md` — pymupdf4llm conversion of the PDF (415 KB markdown + 87 figures in `reference/minervini/figures/`).

`reference/Books/` (operator-added; **currently untracked in git** — operator decides tracking posture; orchestrator notes for visibility): 14 PDFs each with a converted `<slug>/<slug>.md` + `figures/` subdirectory (pymupdf4llm output). Files:
- `Trade Like a Stock Market Wizard (2013).pdf` (Minervini PRIME — already cited in 3e.8 investigation as TLSMW Ch 13 p. 296 anchor for M.2 R-multiple stop-tighten).
- `Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf` (Minervini PRIME; duplicate of `reference/minervini/` copy).
- `Mind Secrets for Winning - Mark Minervini.pdf` (Minervini PRIME; psychology + discipline emphasis).
- `momentum_masters mark minirvani.pdf` (Minervini contributor + Boucher + Minervini + Ryan + Zanger; PRIME on momentum-trading patterns + multi-author confirmation).
- `Stan-Weinstein-Stan-Weinsteins-Secrets-For-Profiting-in-Bull-and-Bear-Markets-McGraw-Hill-1988.pdf` (CONFIRMING — Stage Analysis is the doctrine predecessor underlying both Minervini's trend template + O'Neill's CAN SLIM stage methodology).
- `trade-like-an-o-neill-disciple-2010.pdf` (Morales/Kacher; CONFIRMING — O'Neill lineage; pivot/pocket-pivot/buyable-gap-up entry doctrine; sister to TLSMW VCP).
- `In the trading cockpit with the O'Neil disciples ...18,000% in the stock market.pdf` (CONFIRMING/EXTENDING — Morales/Kacher; trade-journal cadence + post-trade analysis discipline).
- `Insider Buy - Superstocks (2013).pdf` (CONFIRMING — Morales; insider-buying signal as VCP confirmation; sizing emphasis).
- `Mark Douglas - Trading in the Zone_New.pdf` + `Trading in the Zone - Master the Market with Confidence, Discipline and a Winning Attitude 2000.pdf` (DISCIPLINE/PSYCHOLOGY axis; primary source for "trade the plan not the P&L" framing).
- `Stock Market Wizards_ Interviews ...Top Stock Traders_1.pdf` + `_2.pdf` + `The New Market Wizards_ Conversations with America's Top Traders.pdf` + `The Little Book of Market Wizards.pdf` (Schwager; BREADTH/ALTERNATIVE — cross-doctrine validation; surfacing where Minervini's posture aligns with vs diverges from broader top-trader consensus).
- `Trading for a Living - Psychology, Trading Tactics, Money Management 1993.pdf` (Elder; ALTERNATIVE — different framework (technical indicators + triple-screen); useful for surfacing ALTERNATIVES to Minervini's pure-price-action posture).
- `The Big Secret To Trading Success.pdf` (BREADTH; uncategorized until skim).

These supplement the existing `reference/methodology/minervini-trend-template.md` + `reference/methodology/minervini-sell-side-rules.md` source-of-truth extracts + the Qullamaggie commentary KB at MCP server `localhost:9871` (per memory `reference_qullamaggie_mcp.md`) but contain broader doctrine + commentary not yet reconciled against current implementation.

**Body-of-knowledge hierarchy (operator-locked 2026-05-13):**
- **PRIME sources:** Minervini (TLSMW + TTLAC + Mind Secrets + Momentum Masters) + Qullamaggie (MCP commentary KB).
- **CONFIRMING / ADDITIONAL DETAIL sources:** Stan Weinstein (Stage Analysis foundation); O'Neill lineage (Morales/Kacher books).
- **ALTERNATIVE sources:** Schwager Market Wizards series (cross-doctrine breadth); Elder Trading for a Living (different technical framework); Mark Douglas Trading in the Zone (psychology baseline); The Big Secret To Trading Success.

The hierarchy means: review-dispatch findings classify reference disagreement by source role. **A PRIME-source prescription that current implementation lacks = GAP.** **A PRIME-source prescription that current implementation diverges from = DIVERGES (rationale required).** **A CONFIRMING source aligning with PRIME = strengthens the finding.** **A CONFIRMING source diverging from PRIME = surface as UNCLEAR for operator adjudication.** **An ALTERNATIVE source presenting a different approach = surface as POTENTIAL-ALTERNATIVE (NOT a GAP unless operator wants to consider adopting; informational only).**

**Regime-priority qualifier (operator-locked 2026-05-13):** sources may be DE-PRIORITIZED when their content is focused on non-swing-trading regimes (day trading; long-term position investing; intraday scalping; futures/options-specific tactics). Project trades the swing-trading regime (multi-day to multi-week holds; pivot-based entries; trend-following exits). De-prioritization is per-source-or-per-chapter at review-dispatch time — implementer surfaces the regime classification per source and operator confirms the de-prioritization OR the implementer applies the qualifier when the source's regime is unambiguously non-swing. **Per-book regime triage is review-dispatch work** (NOT pre-locked here); high-level rule is captured for review-dispatch implementer to apply.

**Scope of review (operator-locked focus: entry/exit/stop; NOT limited to these):**

- **Entry criteria.** Current implementation: `swing/evaluation/` (A+ criteria); `swing/web/routes/trades.py` entry form; `swing/trades/entry.py:entry_create` lock-time service; sector/industry tamper hardening (Phase 9 Bundle D queued). Compare to: Trend Template threshold logic; VCP / pivot pattern requirements; volume-confirmation rules; relative-strength minimums; sector-leadership posture.
- **Exit criteria.** Current implementation: `swing/trades/exit.py`; advisory rules in `swing/trades/advisory.py` (3e.8 Bundle 2 = `suggest_trim_into_strength` + `suggest_planned_target_r_hit` + `suggest_parabolic_trim`); Phase 6 review-completion outcome bucketing. Compare to: profit-take rules; +20% / +25% targets; parabolic / blow-off climax exits; "violation of the line" exits.
- **Stop criteria.** Current implementation: `swing/trades/stop_adjust.py`; trail-MA advisories (3e.8 Bundle 3 = `suggest_maturity_stage_trail_ma_hint` + `suggest_r_multiple_stop_tighten`); R-multiple stop tightening per TLSMW Ch 13 p. 296. Compare to: maximum-loss rule (-7%/-8% absolute floor); breakeven-stop timing; trailing-stop discipline; sell on first violation vs second.
- **Position sizing + risk per trade.** Current: `swing/recommendations/compute_shares` + capital floor convention ($7500 floor; user memory `project_capital_risk_floor.md`); Phase 9 risk_policy `max_account_risk_per_trade_pct` (currently 0.75 inherited from S3 test). Compare to: 1.25-2.5% baseline per Minervini; concentration vs diversification stance; pyramid-up rules.
- **Portfolio-level risk.** Current: Phase 9 risk_policy `max_concurrent_positions` + `max_portfolio_heat_pct` + `max_sector_concentration_positions` (foundation landed Sub-bundle A; consumption queued). Compare to: Minervini's portfolio-heat convention; pause-on-drawdown thresholds; consecutive-loss exit-the-market discipline.
- **Trade journal cadence + post-trade review.** Current: Phase 6 review_log + cadence card; Phase 8 daily_management_records (event_log + daily_snapshot); MFE/MAE precision tiers. Compare to: Minervini's "post-analysis" prescription (Chapter 8 of TLSMW; chapters in TTLAC); win/loss size asymmetry tracking; batting-average framing.
- **Mental model / discipline (not limited).** Compare current advisory + cadence surfaces to Minervini's psychological framework — pre-trade plan locking, batting-average framing, "trade the plan not the P&L" discipline, post-loss review cadence.

**Output target:** `docs/methodology-review-body-of-knowledge-2026-MM-DD.md` (or per-axis split if scope warrants — see dispatch shape below) enumerating divergences + gaps with citations to source role (PRIME / CONFIRMING / ALTERNATIVE) + current-code surfaces. Memo classifies each finding:
- **MATCHES** (current implementation aligns with PRIME source; CONFIRMING sources also align; no action).
- **DIVERGES** (current implementation deliberately differs from PRIME; document rationale or escalate via V2.1 §VII.F).
- **GAP** (PRIME source prescribes something current implementation lacks; potential V1+ candidate; route through V2.1 §VII.F if production-touching).
- **UNCLEAR** (PRIME source ambiguous OR PRIME-vs-CONFIRMING disagreement; flag for operator adjudication).
- **POTENTIAL-ALTERNATIVE** (ALTERNATIVE source presents a different approach; informational only; operator decides whether to consider adopting).

**Suggested dispatch shape (when sequenced):**

Original 3-source scope (~2-4 hr) is now SUPERSEDED by the body-of-knowledge expansion (~14 books + 2 Minervini/methodology source-extracts + Qullamaggie MCP). Single dispatch would burn excessive context + produce an unwieldy memo. **Recommend modular per-axis dispatch:**

1. **Axis dispatch 1 — Entry criteria reconciliation.** PRIME inputs: TLSMW Ch 5-7 + TTLAC entry chapters + Momentum Masters + Qullamaggie episodic-breakout commentary. CONFIRMING: Trade Like an O'Neil Disciple + In the Trading Cockpit + Stan Weinstein Stage 2 entry criteria. Compare: `swing/evaluation/` A+ rules + entry form + sector/industry tamper hardening.
2. **Axis dispatch 2 — Exit criteria reconciliation.** PRIME inputs: TLSMW Ch 11-13 + TTLAC exit chapters + Qullamaggie sell-side commentary + 3e.8 investigation as prior-art baseline. CONFIRMING: O'Neill disciple sell rules. Compare: `swing/trades/exit.py` + 3e.8 Bundle 2 advisories + Phase 6 review-completion bucketing. **Largely covered by 3e.8 investigation; this axis is the smallest incremental dispatch.**
3. **Axis dispatch 3 — Stop criteria reconciliation.** PRIME inputs: TLSMW Ch 13 (R-multiple stop-tighten anchor already cited in 3e.8 Bundle 3) + TTLAC stop chapters + Qullamaggie trail-MA commentary. CONFIRMING: O'Neill disciple stop discipline. Compare: `swing/trades/stop_adjust.py` + 3e.8 Bundle 3 advisories. **Largely covered by 3e.8 investigation; smallest incremental dispatch.**
4. **Axis dispatch 4 — Position sizing + portfolio-level risk reconciliation.** PRIME inputs: TLSMW Ch 9 (1.25-2.5% baseline) + TTLAC sizing + Insider Buy Superstocks (sizing emphasis) + Momentum Masters portfolio heat. CONFIRMING: O'Neill disciple position-sizing. ALTERNATIVE: Elder triple-screen sizing (different framework). Compare: `swing/recommendations/compute_shares` + $7500 capital floor + Phase 9 risk_policy fields (`max_account_risk_per_trade_pct`, `max_concurrent_positions`, `max_portfolio_heat_pct`, `max_sector_concentration_positions`).
5. **Axis dispatch 5 — Trade journal + post-trade review reconciliation.** PRIME inputs: TLSMW Ch 8 ("post-analysis" prescription) + TTLAC review chapters + In the Trading Cockpit (O'Neil disciples journal cadence). CONFIRMING: Trading in the Zone (review discipline). Compare: Phase 6 review_log + Phase 8 daily_management_records + MFE/MAE precision tiers + Phase 10 metrics surfaces.
6. **Axis dispatch 6 — Mental model + discipline reconciliation.** PRIME inputs: TLSMW + TTLAC mental-game chapters + Mind Secrets for Winning. CONFIRMING: Trading in the Zone (Douglas) + Trading for a Living (Elder) psychology chapters + Schwager Market Wizards interview anti-patterns. Compare: current advisory + cadence surfaces.

Dispatch shape per axis: single research-subagent dispatch (Explore or general-purpose agent), NOT orchestrator-inline. Implementer brief per axis: read PRIME sources for that axis + skim CONFIRMING sources for alignment + spot-check ALTERNATIVE sources + grep current implementation surfaces + produce per-axis memo. Adjudicate findings with operator after each axis ships.

**Operator can elect:** (a) full 6-axis sequence (largest scope; most thorough; ~4-12 hr per axis); (b) skip axes 2 + 3 since 3e.8 investigation already covered them at PRIME-source depth (smallest incremental scope; defer 2+3 unless TTLAC fills 3e.8-deferred items M.1, M.4, §4.A full, §4.C/§4.C.bis); (c) bundled "TTLAC-incremental + body-of-knowledge confirmation" pass (1 dispatch covering only what's NEW since 3e.8 investigation; smallest credible scope; ~4-6 hr).

**Operator-paced; not orchestrator-blocking.** Schwab API arc (in-flight 2026-05-13) + post-Schwab next-arc (TBD) are higher-priority; this review is durable reference work that should sequence behind code-shipping arcs. Capturing here so the body-of-knowledge artifacts don't sit unreconciled.

**Tracking posture for `reference/Books/`:** currently untracked; orchestrator surfaces for operator decision. Options: (a) commit (preserves doctrine-anchor reproducibility for future review-dispatches; +110 MB to repo + figures); (b) keep untracked (smaller repo + assumes operator-local stability of the corpus; review-dispatches need operator's local copy); (c) commit MD-only + .gitignore PDFs (mid-ground; preserves text reference at modest size; figures still tracked since they're cited inline). Operator-paced decision; not orchestrator-blocking.

**Cross-references:**
- `reference/minervini/think-and-trade-like-a-champion.md` (converted 2026-05-12 via pymupdf4llm).
- `reference/methodology/minervini-trend-template.md` + `minervini-sell-side-rules.md` (existing source-of-truth extracts).
- `reference/Books/<slug>/<slug>.md` + `figures/` (14 books pymupdf4llm-converted 2026-05-11; operator-added).
- Qullamaggie commentary KB at MCP server `localhost:9871` (per memory `reference_qullamaggie_mcp.md`; PRIME source).
- `docs/3e8-sell-side-advisories-investigation.md` (746-line survey of sell-side advisory surface vs Minervini SEPA + DST + Qullamaggie doctrine; SHIPPED 2026-05-10 at `63350ad`; **substantially covers axes 2 + 3** — exit + stop reconciliation; the body-of-knowledge expansion's incremental value over 3e.8 is axes 1 + 4 + 5 + 6 plus TTLAC-fills-3e.8-deferred-items check).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F (source-of-truth correction protocol; routes production-touching findings).
- CLAUDE.md "Strategy" section — `reference/methodology/` is reference-only; any production change driven by methodology reference routes through V2.1 §VII.F.

---

## 2026-05-07 Research candidate: risk level vs earnings proximity correlation

**Observation (operator-surfaced 2026-05-07):** There appears to be a correlation between risk level and proximity to earnings announcements. Pattern not yet quantified; surfacing for future research-branch investigation.

**Possible mechanisms (NON-exhaustive; investigation should disambiguate):**

1. **Stop-overshoot magnitude.** Earnings gaps (overnight 10-30% moves) blow through stops; realized loss exceeds planned -1R. Correlation = "trades held through earnings have higher realized-R variance than trades closed before earnings."
2. **Implied volatility expansion.** ATR-based position sizing reads pre-earnings ATR as elevated; risk_per_share inflates; planned_risk_budget_dollars allocates differently. Correlation = "trades entered N days before earnings have wider initial stops AND higher position-size variance."
3. **Per-cohort earnings exposure imbalance.** Sub-A+ VCP-not-formed cohort may attract more pre-earnings trades than A+ baseline (operator hasn't waited for clean post-earnings setups). Correlation = "hypothesis cohort × earnings-proximity is non-uniform."
4. **Pipeline criteria-pass interaction.** Some trend-template / VCP criteria are MORE forgiving in the post-earnings window (e.g., gap-up creates new pivot context); correlation = "criteria pass-rate × earnings-proximity is non-uniform."
5. **Discretionary-confirmation drift.** Operator-perceived risk correlates with earnings calendar awareness (operator may take MORE / FEWER trades pre-earnings based on framing). Confounds outcome attribution.

**Existing infrastructure that could feed investigation:**

- `research/studies/earnings-proximity-exclusion.md` (Tranche B-research Sessions 2a/b/c; methodology established; canonical applied-research study format).
- `research/method-records/` (V2.1 §IV.B minimum viable field list).
- Phase 6 + Phase 7 + queued Phase 8 schema captures `mistake_cost_R` + `lucky_violation_R` + per-day MFE/MAE + outcome bucketing — enables per-cohort × earnings-proximity outcome aggregation when sample size matures.
- `swing/data/ohlcv_archive.py` historical OHLCV archive (Phase 3 consolidation; 696 tickers).
- External earnings-calendar data source: undecided. yfinance `Ticker.calendar` exists but reliability is unverified for historical earnings dates. Schwab API Phase B (queued) may surface fundamentals incl. earnings; alternative paid sources exist (Earnings Whispers, Zacks, EOD historical-earnings APIs).

**Suggested dispatch shape (when sequenced):**

1. **Brainstorm** to lock the research question — which mechanism (or set) is the primary investigative target. Per V2.1 §X pre-registration discipline, decision tiers + thresholds committed before viewing data.
2. **Replay-harness extension** to per-trade-window earnings-proximity binning (mirror earnings-proximity-exclusion study's binning).
3. **Applied-research dispatch** to compute per-cohort × earnings-proximity outcome distributions over operator's actual closed trades (n=2 today; usable for n≥10 baseline).
4. **Tier-3 outcome adjudication** per V2.1 promotion path. If pattern is robust, eventual policy change candidate routes through V2.1 §VII.F source-of-truth correction protocol.

**Operator-paced; not orchestrator-blocking.** Sample size today (n=2 closed) is insufficient for any quantitative investigation; the right time to dispatch is when n≥10 closed trades accumulate AND the operator has spare research-branch time. Capturing here so the observation doesn't decay; signal-tracking only until investigation triggers.

**Cross-references:**
- `research/studies/earnings-proximity-exclusion.md` (existing study; methodology baseline).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §IV.B (research-branch method-record format) + §VII.F (source-of-truth correction protocol).
- `docs/orchestrator-context.md` §"Three-branch architecture" (Applied Research is the right home).
- 2026-04-25 Hypothesis 5 (Production-vs-replay parity check) — establishes the harness pattern.

---

## Dashboard / UX enhancements

> **Archived:** 3e.1 (mark-to-market on Account card; SHIPPED 2026-04-26 `2b5cded`) + 3e.3 (`POST /prices/refresh` clears OHLCV breaker; SHIPPED 2026-04-26 `5b56a2d`). See archive.

### 3e.9 — Market weather chart surface (INVESTIGATION; operator-surfaced 2026-05-08)

**Operator question:** evaluate for a good way to display a chart of market weather. Today the UI surfaces only a one-word label (Bullish / Caution / Bearish / STALE) on the dashboard `status_strip` + pipeline progress + open-positions row VMs. The classifier at `swing/weather/classifier.py:53` already computes close + 10MA + 20MA + 50MA + slope20_5bar + slope10_5bar from 180-day OHLCV on `cfg.rs.benchmark_ticker`; all values are persisted per run in `weather_runs`. The visual signal is absent.

**Investigation scope:**

1. **Survey current state** (above; ground truth captured in this entry).
2. **Display options to evaluate:**
   - **Option A — Benchmark price chart with MA overlays.** Mirror the per-trade chart-rendering pattern (`swing/rendering/charts.py` if applicable; matplotlib/mplfinance pipeline). 180-day candles + 10MA + 20MA + 50MA lines; current close annotation. Static PNG generated by pipeline alongside per-trade charts; rendered as `<img>` in dashboard `status_strip` or a dedicated `market_weather` section. Pre-empts mathtext gotcha (CLAUDE.md — no `$` / `^` / `_` in title format).
   - **Option B — Historical weather-status timeline.** Render `weather_runs` history (last N days) as a horizontal color-coded ribbon (green=Bullish / amber=Caution / red=Bearish). Lightweight; no new chart-rendering pipeline. Could be inline SVG or HTML divs colored via CSS.
   - **Option C — Combined.** A above with a B-style ribbon below the chart showing classification history.
   - **Option D — Trader-style breadth/regime mini-dashboard.** Beyond benchmark — add SPY/QQQ/IWM relative strength, ADL/breadth proxies if data sourceable. Higher scope; potential research-branch territory.
3. **Recommend.** Match recommendation to operator's actual decision-making cadence. Daily-prep-only? Daily-prep + intra-day glance? At-trade-entry? Each cadence implies different latency tolerance + chart freshness expectations.
4. **Implementation sketch.** Once option is locked: VM extension (likely `MarketWeatherChartVM`); rendering surface (pipeline-time chart-render OR runtime SSR); template wire-up; cache discipline (matches existing weather-run cadence — daily). Estimated 2-4 hr implementation depending on option.

**Out-of-scope until investigation completes:** what specific chart library, where in the dashboard layout, frequency of refresh, mobile-friendliness considerations.

**Cross-references:**
- `swing/weather/classifier.py:53` — current classification logic (binding; do NOT reinvent).
- `swing/data/repos/weather.py:get_latest`, `list_weather_runs` — historical data source for Option B/C ribbon.
- `swing/rendering/charts.py` (if exists) — per-trade chart-rendering pipeline pattern to mirror for Option A/C.
- `swing/web/templates/partials/status_strip.html.j2` — current weather label rendering (the surface to extend or replace).
- CLAUDE.md gotcha "Matplotlib mathtext fires on `$` / `^` / `_`" — applies to any new chart titles.
- CLAUDE.md gotcha "yfinance `interval='1d'` includes in-progress bar" — applies to any benchmark-OHLCV fetch in the new chart pipeline.
- Phase 10 metrics-dashboard spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` — may have overlapping regime-display requirements; investigate during scoping.

### 3e.2 — Include realized-from-partial-exits in journal stats total

**Observed:** `swing journal review --period month` shows 0 trades / $0.00 total
when you have 1 partial exit recorded on a still-open trade. The realized $0.74
is in the DB and in the Account card, but not in the journal stats.

**Proposed:** Split the journal stats into two figures:
- **Closed-trade metrics** (existing): win rate, expectancy, avg win/loss, R multiples
  — require a full trade cycle to compute
- **Cash-realized total** (new): sum of `realized_pnl` across ALL exits in period,
  regardless of whether the trade is closed

**Rationale:** "What have I made this month?" should include locked-in partial
exits even on open trades. R-multiple math doesn't fit a partial, but dollar
P&L does.

**Scope:** Journal stats computation + review output. Phase 2 untouched.

---

## Tranche B-ops deferred items (2026-04-24)

Items surfaced during Tranche B-ops sessions 1 (design) and 2 (execution) that were deliberately deferred. See the session-1 design spec §8 (`docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md`) for full context on items marked (§8).

### From design (§8):

- **Pipeline-linkage bundle** — add `evaluation_run_id` FK on `pipeline_runs` + new `pipeline_chart_targets` table keyed on `(run_id, ticker)`. Would eliminate both chart-scope drift modes documented in spec §4 AND subsume the `insufficient-data` → `fetcher-failed` / `too-few-bars` split. Estimated ~1 pipeline-layer session. Phase 2 carve-out required.
- **Exit-form field preservation** — `TradeExitFormVM` has the same latent preservation gap as the stop form. No live bug; the spec scopes preservation specifically to the stop form. Low-effort follow-up.
- **ExitRationale enum distinct from ExitReason** — revisit when journal analysis produces evidence that `reason=partial|manual` rows corrupt downstream queries.
- **Total-book risk cap config** — `cfg.risk.max_total_risk_pct` + warn-coloring on the Open-risk tile. Deferred until evidence about the right default.
- **Book-equity-based Open-risk percent** — requires live prices in risk math. Current denominator is realized equity.
- **Chart-reason split: `insufficient-data` → `fetcher-failed` vs `too-few-bars`** — needs pipeline-layer per-ticker chart-status persistence. Subsumed by the pipeline-linkage bundle above.

### From Session 2 adversarial review:

- **Session-gating propagation for read-only surfaces** — `DashboardVM.stale_banner` currently does not propagate to watchlist/expand and other non-dashboard surfaces. Chart-scope resolver accepts the weekend/holiday drift for this reason. A future brainstorming session would design strict cross-UI session-gating. Spec-level decision required.
- **Transport/decode img failure fallback** — Session 2 C3 intentionally dropped `<img onerror>` per spec §4 rationale (transient static-mount errors "should page someone"). If real operational experience argues for a narrow client-side fallback distinct from the server-side intentional-absence states, reconsider. Low priority; monitor.

### From Session 3 adversarial review:

- **`TradeEntryFormVM.force` pre-existing dead field** — symmetric to the `TradeStopFormVM.force` removal shipped in Session 3 C5. No template consumer; no re-render usage. Session 3 declined to touch it mid-session per scope discipline. ~5-minute cleanup commit.
- **`(str, Enum)` → `StrEnum` migration across three enums** — `ExitReason`, `EntryRationale`, `StopAdjustRationale` all currently use the `(str, Enum)` pattern and carry `# noqa: UP042`. A single-commit migration clears all three `noqa` comments at once. Cohesive, small, low-priority.

---

## Tranche C deferred items (2026-04-25)

Items surfaced during Tranche C sessions (pipeline-linkage bundle, commits `f45dae8..1cfc117`; candidate-sparsity diagnostic, commits `1b33e21..bd0dae6`) that were deliberately deferred per scope discipline.

### From pipeline-linkage bundle:

- **`build_watchlist` mixed-anchor fix.** Same disease as today_decisions / candidates_by_ticker / _step_export had pre-Tranche-C; the standalone `/watchlist` page still reads via "latest eval" rather than `pipeline_run.evaluation_run_id`. Small commit (~30-60 min) now that the FK exists. File: `swing/web/view_models/watchlist.py:50-53` (the `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` query).
- **Stale `pipeline_chart_targets` rows on lease revoke.** When `_step_charts` writes `'pending'` rows then crashes / is force-cleared, those rows persist for the now-force_cleared `pipeline_runs` row. Resolver only reads `state='complete'` so they're inert, but accumulate over many failed runs. Worth a `sweep_stale_artifacts`-style addition if they grow.
- **"no-run" chart-reason wording inconsistency.** Pre-existing message says "for this session" but resolver is no longer session-gated. Revisit only if operators report confusion.
- **Per-ticker `fenced_write` granularity in `_step_charts`.** Each ticker outcome is its own `lease.fenced_write()` transaction (~15 small transactions per pipeline run). Acceptable now; if chart-step performance becomes a bottleneck, batching the per-ticker UPDATEs into a single fenced commit at end-of-step is straightforward.

### From candidate-sparsity diagnostic:

- **Hypothesis 5 — Production-vs-replay parity check.** The diagnostic's most-permissive matrix cell (Russell 3000 5×) reaches 0.0098%; production observation (Session 2a) is ~0.5%. **~50× residual gap unexplained** by universe + capital combined. Cheapest applied-research follow-on: side-by-side comparison of harness `evaluate_one` output vs production pipeline output for same inputs over the same window. Surfaces any silent code drift between research-branch reuse and production execution. Estimated ~1 session, applied-research scope.
- **Hypothesis 6 — Finviz universe reconstruction.** Most explanatory route to closing the residual gap but multi-week scope. Reconstructs the time-series of operator's actual Finviz-filtered universes to test universe-source hypothesis. Out of scope absent specific reason and time budget.
- **Newcombe interval on cross-universe rate difference.** Diagnostic R2 review noted the disjoint-CI rule has anti-conservative properties; a formal Newcombe interval on (p_C − p_A) would be the proper instrument. The qualitative-direction conclusion is robust to choice of test; nice-to-have refinement, not load-bearing.
- **Supplementary `--base-capital 100000 --capital-multiplier 1.0` parity run.** Would reproduce Session 2c's 11 A+ count (or surface a parity drift) and close the matrix's third capital interval [$37.5k, $100k]. Pre-authorized as thin follow-on if hypothesis-5 work happens.
- **`recompute_binding_prod_gated.py` parameterization.** Currently hardcoded against `build_harness_config()`. If a future diagnostic uses different criteria configurations, parameterize. Defer until that need arises (registry-maximalism risk per V2.1 anti-patterns).
- **Methodology lesson — production-gating-aware instrumentation as standing pattern.** Captured durably in `docs/orchestrator-context.md` §"Lessons captured." When instrumenting production logic for diagnostic measurement, mimic production's gating order, not criteria emission order. Future diagnostic instrumentation should adopt this pattern from the start.

### Capital-sensitivity finding disposition (informational):

The diagnostic established that risk_feasibility blocking is highly capital-sensitive in proportional terms but modest in deterministic A+ count terms. Operator (2026-04-25) declined to act: "the amount of money available is the amount of money available; without proven history, doesn't make sense to raise capital 2 orders of magnitude to go from 5 months to 2.5 months per A+ candidate." Recorded here so future operator/orchestrator sessions don't re-litigate.

---

## 2026-04-25 parallel-work follow-ups

Items surfaced during the parallel `build_watchlist` mixed-anchor fix (commit `77877c1`) and harness-vs-production parity check (commits `c47a783..1a88fb7`) that were deliberately deferred per scope discipline.

### From `build_watchlist` mixed-anchor fix:

- **Stale banner on `/watchlist`.** `WatchlistVM.stale_banner` is currently always `None` on the standalone `/watchlist` page despite being declared. On "new day, no fresh pipeline yet" workflows the page can render today's session_date alongside flag tags from the previous completed pipeline. Moderate-scope follow-on: touches `WatchlistVM`, `build_watchlist`, watchlist template; coordinates with the base-layout shared-VM gotcha listed in CLAUDE.md (every base-layout VM must gain new fields). Mirror `build_dashboard`'s stale_banner derivation at `dashboard.py:154-165`. Genuine UX gap; defer until you want to scope a session for it.
- **Deterministic tiebreaker on `ORDER BY finished_ts DESC LIMIT 1` (class-level pattern).** Several query sites in `swing/web/` (dashboard.py:107-111, 143-147, 155-159; watchlist.py uses the new pattern in `build_watchlist` post-`77877c1`; `build_watchlist_expanded` separately) use second-precision timestamp ordering without a deterministic tiebreaker. **Recommendation: defer indefinitely.** SQLite second-precision collision requires two pipeline completions in the same second — essentially impossible given pipeline runtime. Pre-existing across the layer; cost is small but value is theoretical until we see an actual collision in the wild. Capture here so a future session doesn't accidentally pick it up as urgent.

### From harness-vs-production parity check:

- **Multi-run parity characterization.** The Tier 1 result is on n=1 production run (eval_15, action_session 2026-04-25). For tighter inference, run the parity comparator across the last 5–6 production runs with preserved Finviz CSVs. Operator-decision gated; not urgent given the Tier 1 single-run result.
- **A+-surface-exercising parity run.** The n=80 eval_15 produced zero A+ candidates, so parity at A+ classification level is empirically unverified. Pick a historical production run that produced ≥1 A+; verify parity at A+ level. Not urgent given Tier 1 already verifies the watch/skip-level classification logic.
- **Parity comparator as periodic regression check.** Open question whether to run the parity comparator on every release or never again. **Recommendation: never-again unless a future change to `swing/evaluation/` or `research/harness/` specifically warrants it** (any change to the production scoring chain or the harness's evaluator wrapper). The comparator is durable in `research/parity/`; re-running is ~30 min when the question recurs.
- **`PriceFetcher` cache-stat introspection.** Production's `swing.prices.PriceFetcher` does not expose hit/miss counts; the parity comparator wrapped it in `_CountingPriceFetcher` (in `research/parity/run.py`) to report cache stats in the D3 manifest. Minor architectural gap; backlog item for if cache observability becomes operationally valuable elsewhere in the production layer.

---

## 2026-04-25 Bug 1 follow-ups (watchlist Enter-button event-propagation)

Items raised by Codex during Bug 1's adversarial review (commit `9aabe8b` shipped) and accepted-with-rationale per scope-bounded brief. Captured here for future-session pickup; not urgent but real architectural concerns.

- **Watchlist row HTMX trigger architecture refactor.** The current row design — `<tr hx-get="/watchlist/<ticker>/expand">` makes the entire row a click target — means any interactive child added to the row (button, input, link) has to remember `onclick="event.stopPropagation()"`. Bug 1's fix is a point-fix at the Enter button; it doesn't prevent recurrence with future interactive children (e.g., when Phase 3e §3e.5's "Log entry" button replaces the existing CLI placeholder in `watchlist_expanded.html.j2:33`). Two architectural alternatives:
  - **Option A: dedicated chevron cell** — move the expand trigger from the row to a leftmost `<td class="expand-trigger">` chevron. Visual UI change; explicit affordance for expand.
  - **Option B: scope the trigger** — use `hx-trigger="click from:td.row-trigger"` to limit the row's expand trigger to a specific cell or class. Invisible to user; same effect as Option A.
  - **Recommendation when scoped:** Option B unless operator wants the chevron UI affordance. Estimated ~1-2 sessions including tests. Picks itself up when more row-level controls ship.
- **JS-execution test harness gap.** Project currently uses FastAPI TestClient + assertion on rendered HTML strings for web-layer tests. Sufficient for server-side rendering correctness; INSUFFICIENT for JavaScript event behavior, HTMX runtime swap targeting, DOM updates after script execution, and CSS-driven visual states. Bug 1's fix test (string-match `stopPropagation`) confirms the attribute is present but does NOT confirm the runtime behavior is correct — operator manual verification is the actual confidence source. Adding a JS test harness (Playwright or Selenium) would close this gap but adds: heavy dependency (chromium driver), slow tests (browser startup overhead), flakiness risk (timing-dependent failures), CI complexity. **Recommendation: defer** until either (a) 5+ event-handling-related bugs accumulate, (b) chart-pattern algorithm or other rich-UI work approaches and would benefit, or (c) manual verification becomes a bottleneck. When scoped: ~2-4 sessions for harness setup + CI integration + re-architecture of test patterns. For now, manual verification remains the JS-behavior testing surface for the project.

---

## 2026-04-25 Bug 2 follow-ups (trade entry form vanishes mid-typing)

Items flagged by the Bug 2 investigation (commits `04ef355` → `20d2cab` shipped) as defense-in-depth opportunities and pre-existing degradations not in the fix scope.

- ~~**`_handle_any` HX-Target-awareness (defense-in-depth).**~~ SHIPPED 2026-04-26 as Session 1 T7 of the QoL UI-polish bundle (commit `d9603c9`). `_handle_any` now uses `_is_row_swap_target(request)` and `_ROW_TARGET_PREFIXES`-aware fragment selection, mirroring `_handle_http_exc`. Latent risk for unhandled non-HTTPException raised inside row-target routes is closed.
- **Sizing-hint hx-trigger parsing bug (pre-existing behavioral degradation).** Current trigger string in `partials/trade_entry_form.html.j2` (sizing-hint span): `change from:input[name=entry_price],input[name=initial_stop] delay:200ms`. Per HTMX 2.0.3's tokenizer, this parses as TWO separate triggers because HTMX splits on top-level commas: (1) `change` event from `input[name=entry_price]` with NO delay (delay:200ms attaches to the second trigger only); (2) `input` event with broken filter expression `[name=initial_stop]` which compiles into `event.name = (event.initial_stop ?? window.initial_stop)` — always evaluates undefined → never fires. Net effect: sizing-hint fires correctly on entry_price changes (without intended debounce) but NEVER fires on initial_stop changes. **Recommendation:** likely fix is HTMX's parens-grouped from-selector syntax: `change from:(input[name=entry_price],input[name=initial_stop]) delay:200ms`. Verify against HTMX 2.0.3 behavior (test in browser; check HTMX docs). ~30 min including a smoke test that asserts both fields trigger sizing-hint requests with debounce. Behavioral degradation; affects sizing feedback UX but not correctness. **2026-04-29 update:** investigation-first bug-fix dispatch's DevTools capture confirmed `htmx:syntax:error: Invalid left-hand side in assignment` fires on EVERY entry-form render at `partials/trade_entry_form.html.j2:22-23` from the same selector. Severity confirmed; fix is the parens-grouped syntax above. Form still works because HTMX recovers from the syntax error, but every form open logs a JS error. Prioritize bundling with other entry-form-touching dispatches (reuses operator-witnessed-verification overhead) OR pick up standalone if a CLAUDE.md gotcha entry isn't sufficient.

### Bug 2 root-cause fix history note (informational, not a follow-up)

Bug 2's actual root cause was **not** the form-submit ValueError path that the first fix attempt (`04ef355` → `20d2cab`) addressed. The actual mechanism was sizing-hint span `hx-target` inheritance from parent `<form>`: the span had no explicit `hx-target`, so it inherited `hx-target="closest tr"` from the form, causing every sizing-hint hx-get response to swap into the entry-form `<tr>` position — replacing the entire form with just the sizing-hint span. Real fix: `2a167d1` adds explicit `hx-target="this"` to the sizing-hint span (one-line). The first fix is preserved as defense-in-depth (correct behavior for actual form submission with stop≥entry). Lesson captured in `docs/orchestrator-context.md` anti-patterns: "Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction"; mitigation in operating-processes via investigation-phase operator-confirmation gate for INVESTIGATION-FIRST bug-fix briefs.

---

## 2026-04-25 hypothesis-engine + analyze + backup follow-ups

Items surfaced from the Monday-prep operational batch (commits `4a565c6` → `fe270a6`).

### From hypothesis-recommendation engine work:

- **WatchlistVM extension for active recommendations** (optional). hyp2 declined per scope discipline — dashboard + CLI pre-fill cover the primary loop; the watchlist page already shows flag tags. If operator wants the standalone `/watchlist` page to also list active recommendations, clean follow-up: add `active_recommendations` field to `WatchlistVM`; render the same partial in the watchlist template. ~30 min work.
- **Monitor for first hypothesis closure → revisit longer-horizon planning.** Per orchestrator-context.md 2026-04-25 entry: when the first hypothesis closes (target sample met OR tripwire-fired escape), revisit the longer-horizon planning question with operator. Likely first to close: Sub-A+ VCP-not-formed (5-sample target; VIR is sample 1) or A+ baseline (20-sample) depending on operator's actual identification + take pace.
- **Hypothesis registry-mutation discipline (operator-facing).** Per pre-registration discipline, only `status` is mutable via `swing hypothesis update`. To add a NEW hypothesis or change target_sample / tripwire / decision_criteria of existing hypotheses requires a formal new migration (e.g., `0009_hypothesis_v0.2_amendment.sql`). This boundary is a feature, not a limitation; preserves anti-rationalization integrity. If operator decides to add hypothesis 5 (e.g., post-first-closure planning), it's a small Phase 2 carve-out: new migration + seed.

### From `swing trade analyze` CLI work:

- **Cross-contamination commit-title misattribution.** Commits `375344f` (titled "feat(pipeline): trigger weekly DB backup...") and `43b4d35` (titled "feat(cli): add db-backup subcommand...") accidentally bundled trade-analyze implementer's work due to parallel `git add` race. Code is correct; commit titles are misattributed. Could be addressed via git notes if attribution preservation matters; recommendation per orchestrator-context.md 2026-04-25 lesson is to leave as-is (the lesson is durable; archaeology fix is administrative overhead). Future parallel dispatches should use git worktrees to prevent this class of issue.

### From weekly DB backup work:

- (No follow-ups; clean implementation.)

---

## 2026-04-26 QoL bundle + watchlist sort follow-ups

Items surfaced during the QoL UI-polish bundle (Session 1, commits `4c264b2..d9603c9` + adversarial fixes `61424f2`, `20ecc70`, `d9ab7ff`) and the watchlist sort-by-tags session (Session 2, commits `1d6ed42..e613f39`) that were deliberately deferred per scope discipline. Adversarial review reached `NO_NEW_CRITICAL_MAJOR` in both sessions (Session 1 R3, Session 2 R5).

### From Session 1 (QoL UI-polish bundle):

- **Target-family-aware error fragments (Session 1 R1 Major 2 — accepted, not fixed).** `partials/trade_form_error.html.j2` hardcodes `colspan="8"`; watchlist row tables use 7 cells. Affects both `_handle_any` (T7 just shipped) and `_handle_http_exc` (pre-existing) symmetrically. Browsers tolerate `colspan` greater than column count, so functionally non-blocking; structural correctness would pick a fragment per `_ROW_TARGET_PREFIXES` family. Cheap follow-up when a future row-target table gains a different cell count or when a stricter validator complains.
- **Alternating-row CSS scoping (Session 1 R1 Minor 2 — accepted with rationale).** Global `tbody tr:nth-child(even) td` rule may bleed striping into future tables that don't want it. Currently relies on source-order vs `tr.tripwire-fired`. If a future class needs to override, increase its specificity (e.g., `tr.expanded > td`) or scope the alternating rule to specific tables (`#open-positions tbody tr:nth-child(even) td`). Operator manually verified that `tr.expanded` rows currently inherit the underlying stripe color naturally — no awkward mid-table jump.
- **`build_watchlist_row` single-ticker performance (Session 1 R2 Minor 1 — accepted with rationale).** `swing/web/view_models/watchlist.py:build_watchlist_row` scans the full active watchlist and full candidates list to render one row. Acceptable today; **trigger threshold: watchlist > ~100 rows**, at which point add a single-ticker variant of `list_active_watchlist`.
- **Close-button server-round-trip failure model (Session 1 R2 Major 1 — accepted with rationale per Option-A spec).** A transient backend failure on `/watchlist/<ticker>/row` (collapse) can leave the row temporarily stuck expanded or replaced with an error fragment. Identical failure model to `/expand`. If operator-visible failures occur, evaluate Option B (client-side stash + collapse via cached compact-row HTML).

### From Session 2 (watchlist sort-by-tags):

- **Centralize eval-anchor resolver (Session 2 R2 Minor 3 — accepted, out of scope).** The same ~10-line `pipeline_runs.evaluation_run_id`-with-fallback block now lives in three places: `swing/web/view_models/dashboard.py:73-86` (already factored as `latest_evaluation_run_id`), `swing/web/view_models/watchlist.py:59-66`, and `swing/web/routes/pipeline.py` `/prices/refresh` route. The dashboard module already exports `latest_evaluation_run_id`; the other two sites should consume it. ~30-min DRY refactor.
- **Extract `swing/web/watchlist_ranking.py` module (Session 2 R1 Minor 1 — accepted, out of scope).** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, and `_flag_tags` currently live in `swing/web/view_models/dashboard.py` and are imported from `watchlist.py` and `routes/pipeline.py`. Module extraction would clarify ownership; minor cleanup.
- **Decouple `_TAG_PRECEDENCE` from UI label strings (Session 2 R1 Minor 3 — accepted, out of scope).** `_TAG_PRECEDENCE` is keyed on the same presentation strings (`"TT✓"`, `"VCP✓"`, `"A+"`) that templates render. A future label rename would silently zero out precedence (unknown keys score 0 because the fallback for unknown tags is `0`). Decoupling: introduce a tag-id enum or constants like `TAG_TT_PASS = "TT✓"` referenced from both the precedence map and the templates. Not urgent; current state is correct.
- **(2026-04-28 sector dispatch follow-up) Factor non-web utility helpers out of `swing.web.view_models.dashboard` once 3+ cross-imports exist.** Surfaced during sector-capture writing-plans dispatch return report. Pattern observation: `latest_evaluation_run_id()` is now imported by CLI for sector auto-resolution (sector dispatch Task 7), making it the second cross-import from `swing.web.view_models.dashboard` (first precedent: `_lookup_active_recommendation_label` for hypothesis pre-fill). Currently fine — two consumers is below the refactor threshold. **Trigger:** when a third non-web call-site needs to consume one of these helpers, factor them into a non-web-bound module (likely `swing/data/utils.py` or similar). Picks itself up naturally.
- **(2026-04-29 journal-flag fix follow-up) Emit a dedicated "all winners closed same-day" behavioral flag instead of silently skipping the losers-held-too-long ratio.** Current behavior post-2026-04-29 fix: when `avg_w == 0` (all winners are same-day-open-and-close), `_losers_held_too_long` returns None (silent skip). The same-day-winner pattern is itself a behavioral signal worth surfacing — operator may be cutting winners short by closing same-day instead of letting them run. Proposed flag: code `winners_closed_same_day`, title "All winners closed same-day", detail along the lines of "{N} winners closed same-day; consider letting winners run multi-day for trend continuation." Defer until operator confirms the signal is operator-relevant (currently the losers-held flag is the canonical "behavioral concern" surface; adding a parallel flag is a UX decision). Small dispatch when picked up: extend `_losers_held_too_long` OR add a sibling `_winners_closed_same_day` function in `swing/journal/flags.py`; add discriminating regression test mirroring the just-shipped guard test.

- **(2026-04-29 production-verification investigation dispatch follow-up) `/watchlist` standalone entry-flow polish (R1 Critical 1 ACCEPTED).** Trade records correctly via the `/watchlist` standalone page; UX is silent (no confirmation banner; no on-page open-positions table; no toast). Operator confirms trade was recorded by navigating to dashboard. Operator workflow is dashboard-centric so low-priority. Proposed enhancement: toast notification on success + status-strip rendering + open-positions section parity with dashboard flow on the standalone `/watchlist` page. Investigation evidence at `C:/tmp/bug-probe/` (2026-04-29; may decay; reproduce on demand). ~1-2 dispatch cycles when picked up.

- **(2026-04-29 production-verification investigation dispatch follow-up) Shared protocol/dataclass for `hypothesis_recommendations.html.j2` partial (R3 Minor 1 ACCEPTED).** Duck-typed VM contract — `vm=dashboard_vm` and `vm=HypRecsSectionVM` both work today because the partial only reads `vm.active_recommendations`. Future template edit reading another field could break one consumer. Long-term hardening: introduce a shared protocol (e.g., `class HypRecsConsumerVM(Protocol)`) with the partial's required fields; both consuming VMs implement it; partial template-typed against the protocol. Discipline currently documented in source comments at the call sites. Pick up when (a) the partial gains a new field reference OR (b) a third consumer joins.

- **(2026-04-30 OHLCV archive Phase 3 follow-up) `research/parity/run.py:178` references removed `_cache_path` method on `PriceFetcher`.** Phase 3's PriceFetcher refactor removed the `_cache_path` method (replaced by per-ticker archive helper). `research/parity/run.py:178` still calls it — research-branch CLI code (per CLAUDE.md bifurcated architecture); not in fast suite; runtime-fails if invoked. Not used in production `swing/` flow. **Bundle into Phase 4 cleanup-remainder dispatch** (or fold into the eventual `_CountingPriceFetcher` rewrite that the new archive directory shape requires for cache-stat introspection).

- **(2026-04-30 OHLCV archive Phase 3 follow-up) Parallel cold-start test with today-aligned archive (R1 Minor 1 advisory).** Current OhlcvCache cold-start test mocks `yf.download` empty as a safety guard against test-suite network calls; this weakens the "no network call" claim because the discriminating contract is verified via `helper_calls == ["AAPL"]` + bundle reflects archive content. Future improvement: add a parallel cold-start test using a today-aligned archive (no gap fetch needed) to assert TRUE zero-yfinance behavior end-to-end. Small additive test; ~30 min when picked up. Bundle into Phase 4 cleanup-remainder.

- **(2026-04-30 OHLCV archive Phase 3 process-meta) Task 5/6 scope co-dependency observation.** Phase 3 plan partitioned `swing/web/ohlcv_cache.py` kwargs wiring under Task 6, but the wiring had to land in Task 5 commit (`9a61d19`) to keep the fast suite green during the `fetch_daily_bars` signature change. Task 6 commit (`75526fe`) became pure test-additive. **Generalization:** task-by-task plan partitioning can have "gotcha co-dependencies" where a downstream task's wiring must land co-temporal with an upstream task's signature change to preserve test-green throughout. Writing-plans phase should anticipate these by tracing signature-change ripple effects across consumer files; task partitioning that splits a signature change from its consumer wiring across tasks should explicitly call out the co-temporal-landing requirement. Add to writing-plans phase as a checklist item for any plan modifying a function signature that's consumed by other plan-affected files.

- **(2026-04-30 hypothesis_label web-form gap) ARCHITECTURAL: web entry form does not capture `hypothesis_label`.** Latent since 2026-04-25 hypothesis-recommendation-engine ship; surfaced by operator's CC trade entry on 2026-04-30 (per-row "Take this trade" button on hyp-recs expansion). **Concrete failure mode:** every web-form trade entry persists `hypothesis_label = NULL` (then empty string at canonicalization) → progress count never increments → tripwire never fires from web entries. Verified in `swing/web/`: ZERO references to `hypothesis_label` in views, view_models, routes, templates. CLI has full pre-fill machinery (`swing/cli.py:415-501`); web has none. VIR (id=1) only has its label because backfilled via SQL UPDATE 2026-04-25; CC (id=3) backfilled the same way 2026-04-30. **Operator workflow tax:** every hypothesis-tagged trade taken via the web form requires a SQL UPDATE backfill to attribute it correctly. Bearable at current ~50-trades/year ceiling, but real friction. **Fix scope:** small-medium dispatch (~3-5 tasks): (a) add `hypothesis_label` field to `TradeEntryFormVM` populated via the same matcher logic the CLI uses (`_lookup_active_recommendation_label` from `swing.web.view_models.dashboard` already exists; matches the cross-import note); (b) add hidden input + read-only display rows in `partials/trade_entry_form.html.j2` (mirrors the sector/industry pattern from sector capture Phase 1); (c) add `Form(...)` param + thread through `EntryRequest.hypothesis_label` in `swing/web/routes/trades.py entry_post`; (d) discriminating tests + soft-warn round-trip preserves the label (per the multi-path-ingestion lesson 2026-04-29). **Sequencing:** sequence after Phase 4 cleanup-remainder ships (operator-paced; not Phase-4-blocking). OR inline into Phase 4 if implementer has bandwidth — but operator decided Phase 4 plan continues separately, so default to standalone follow-up dispatch post-Phase-4. **Cross-references:** orchestrator-context.md "Recent decisions and framings" 2026-04-25 (hypothesis-recommendation engine framing — "dashboard PROPOSES, operator DISPOSES"); 2026-04-25 "Prefix-label convention" (operator-facing — manual labels start with canonical hypothesis name); CLI precedent at `swing/cli.py:486-501` (pre-fill logic to mirror in web). _Note: 2026-04-30 SHIPPED as Phase 4.5 hypothesis_label web-form gap fix at `f9a07bf` per orchestrator-context in-flight ledger; entry retained here for cross-reference._

- **(2026-04-30 entry-form stop-value observation; defer-investigate)** Operator reported during CC entry (Take-this-trade button on hyp-recs expansion, 2026-04-30): "the table did not have the stop values correctly populated; potentially others." Operator instruction: "we do not need to investigate further" until another instance reproduces. Logged for memory; if a second observation surfaces with screenshots or specific field values, dispatch investigation-first. **Possible mechanisms (NON-exhaustive; do NOT design fixes against these without empirical reproduction):** (a) sell-stop snapshot field reads from the wrong source (Candidate.initial_stop vs SizingResult.stop_loss vs computed-fallback); (b) origin-aware re-resolution at form-render time loses snapshot context; (c) PriceFetcher stale archive returning wrong reference price (Phase 3 just shipped; not yet operator-verified end-to-end); (d) ToCToU window between expansion-render and form-render. **No action until reproducer.**

---

## 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups

Items surfaced during the chart-pattern flag-v1 brainstorm dispatch (commit chain `9583f19..081f689`, spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, 5 adversarial Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`). Implementation Phase 1-7 SHIPPED via the per-phase dispatch chain (archived); these items are explicitly out of V1 scope.

### V2+ pattern coverage (deferred per locked-constraint #1):

- **Pennant pattern.** Same shape geometry as flag but with converging trendlines. V2 adds to `pattern` IN-list via new migration; classifier adds geometric gates for trendline convergence.
- **Cup-with-handle pattern.** Multi-month U-shape + shallow pullback near pivot. Larger geometric definition surface; likely benefits from multi-timeframe consideration.
- **Flat base pattern.** ≥5 weeks, range ≤~15%. Simpler than flag; mostly range-CV + duration check.
- **Tight channel pattern.** 2+ weeks of converging highs/lows. Variant of flag with stricter parallel-line geometry. **Methodology-reference candidate:** Lo, Mamaysky, Wang (2000) covers "rectangle" (RTOP/RBOT) which is the academic-finance name for tight-channel geometry — kernel-regression-smoothed local-extrema definitions in their §II.A are a starting point for V2 spec drafting.
- **Qullamaggie taxonomy patterns.** episodic_pivot, power_earnings_gap, parabolic_short, gap_and_go, base_breakout, ipo_breakout — all available as reference layer via the qullamaggie MCP; some require external context (earnings calendar, IPO date) and are not pure-shape classifications.

### Methodology reference for future pattern-catalog expansion (added 2026-04-28):

- **Lo, Mamaysky, Wang (2000) — "Foundations of Technical Analysis"** (Journal of Finance 55(4), pp. 1705–1765; PDF at `https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf`; full reference entry in `reference/Future Work/QuantEcon/external-references.md`). Canonical academic paper on algorithmic chart-pattern detection via Nadaraya-Watson kernel regression + geometric detection on local extrema. Pattern catalog: HS/IHS, broadening top/bottom, triangle top/bottom, rectangle top/bottom, double top/bottom — 10 patterns, NOT including flag/pennant/cup-handle/base. **Use as starting-point methodology reference if V2+ pattern scope ever expands beyond the current operator V2+ list to include head-and-shoulders, triangle, rectangle, or double-top patterns.** Replication caveats: 0.3×h* bandwidth is admitted ad-hoc tuning; effect sizes small (information, not profit); sample period 1962–1996 pre-modern-microstructure. Treatment: reference-only per V2.1 §VII.F; the operator-drives-agent-serves discipline (QuantEcon companion) flags academic methodology homogenization as a risk — Lo et al. is evidence base + methodology reference, NOT prescription.

### V2 capability extensions:

- **Sort-PARTICIPATING flag tag (operator-decision; affects production UX-priority).** V1 keeps `_sort_watchlist` byte-for-byte unchanged; flag tag is parallel render-only data via `pattern_tags`. Promoting to sort-participation would change watchlist ordering — affects production UX-priority surface and would require V2.1 §VII.F protocol.
- **Calibration study (algo vs operator agreement-rate).** Gated on 20+ overrides accumulated. Compares `chart_pattern_algo` vs `chart_pattern_operator` to surface algorithm bias / blind spots / threshold-mis-calibration. Output: tuning recommendations for `cfg.classifier.*` defaults and `cfg.web.flag_pattern_display_threshold`.
- **Slow-test live-fetch suite (`tests/evaluation/patterns/test_flag_classifier_live.py`, `@pytest.mark.slow`).** Exercises classifier against live yfinance pulls for upstream-data-format-drift detection. Deferred per V1 scope; useful when yfinance API changes or pandas/numpy upgrades land.
- **Tuning-history versioning.** Record `cfg.classifier.*` values per pipeline run alongside the cached classification. Currently `components_json` captures clearances but not the threshold values themselves; without history, retroactive analysis can't distinguish "operator override during low-tightness window" from "operator override after we tuned tightness threshold." Modest scope: extend cache schema, capture threshold dict at compute time.
- **Manual-trade fallback for out-of-chart-scope tickers.** V1 explicitly does not handle this — operator entering a trade for a ticker not in chart-scope sees "Not classified" stub with override surface hidden. V2 adds synchronous classifier fetch on form load (single-ticker yfinance pull + classifier run + persist). Adds entry-time latency (~1-3s for cold fetch); needs cache-warm check + circuit-breaker discipline.
- **Multi-timeframe classification (weekly + daily).** V1 is daily-only. Some patterns (cup-with-handle, long bases) are more naturally weekly. V2 extension: classifier accepts both timeframes; gates can require confirmation across timeframes.
- **Real-time / intraday classification.** Out of V1 scope; classifier runs on completed-bar daily data. V2 candidate if intraday execution becomes operator-relevant (currently it's not — daily-cycle workflow).

### V2 schema / hardening:

- **Schema-layer hardening for trades cross-column constraint.** V1 enforces the `chart_pattern_algo='flag' iff confidence IS NOT NULL` invariant at the repo layer (`insert_trade_with_event` raises `ValueError`). Schema-layer enforcement requires CREATE-COPY-DROP-RENAME migration — heavyweight. **Bundle with the next column-change migration on `trades`** to amortize the cost. Risk in the meantime: non-repo writers (raw SQL via sqlite3 CLI, future migrations) can violate the invariant.
- **Hidden form-field tampering hardening for chart_pattern_classification_pipeline_run_id.** V1 accepts the field as operator-claimed input from a hidden form field (per §3.6 threat model: "operator-claimed input, not server-verified provenance"). For personal-use single-operator scope this is acceptable residual risk. V2 hardening: re-resolve cache at submit + validate against form-supplied pipeline_run_id; refuse if mismatched.
- **Dashboard banner for classifier-error count per pipeline run.** V1 emits `logger.warning` per-ticker on classifier exception + end-of-step error count summary log line. Dashboard surface deferred — pipeline logs cover the operational visibility gap. V2 surface = banner showing "Pipeline N had X classifier errors" with drill-down to which tickers.

### Process / lessons-derivative:

- **`swing/web/watchlist_ranking.py` module extraction (per 2026-04-26 deferred item) — natural place to land flag-tag separation if extracted.** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, `_flag_tags` currently in `swing/web/view_models/dashboard.py`; flag-tag rendering also lives in `_pattern_tags`. Bundling all tag/sort logic in one module clarifies ownership and provides a single edit point for future pattern additions.
- **§1.2 doc inconsistency fix.** Spec §1.2 item 2 originally said "three trade columns" but R4 added a 4th (audit anchor). Fixed in this housekeeping commit; preserved as a lesson on doc/spec drift across adversarial review rounds.
- **d266e5f commit message says "R3 fixes" but is actually R4 fixes.** Implementer flagged; preserved per no-amend rule. Commit substance is correct; only the message header is inaccurate.

---

## 2026-04-27 chart-pattern flag-v1 V1-ship gates (operator-paced; long-horizon)

> Tasks 7.1 + 7.2 SHIPPED via Phase 7 implementer-side dispatch (archived). Tasks 7.3 + 7.4 retained here as operator-paced; cross-referenced from `docs/orchestrator-context.md` §"Currently in-flight work."

- **Task 7.3 (operator-paced fixture labeling, ≥15 fixtures)** — operator's earlier framing: blocked more by external constraints (figuring out best way to label) than by orchestrator-side bandwidth. No urgency. Loader + parametrized test infrastructure shipped at `tests/evaluation/patterns/fixtures/README.md` + `test_flag_classifier_integration.py`.
- **Task 7.4 (FP-biased classifier tuning checkpoint)** — gated on Task 7.3. Per Q2 (2026-04-27): operator does manual FP/FN classification from pytest output; no automated aggregator added in V1. Tune `cfg.classifier.*` if FP > FN per spec §3.1.4.

---

## 2026-04-27 chart-pattern flag-v1 manual verification round 1 — Tier 3 operator-design questions (retained)

> Tier 1 (mathtext fix) + Tier 2 (chart-image route + open-positions expand + chart-scope alignment) + Tier 4 (verification doc fixes) all SHIPPED — see archive. Tier 3 items retained here; also cross-referenced from `docs/orchestrator-context.md` §"Operator-paced items."

5. **Lightning icon trigger logic re-evaluation.** Current rule: `price >= 0.99 × entry_target`. Operator surfaced concern that simple "near pivot" indicator may not be the right "actionability" signal post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine). Options enumerated in `docs/chart-pattern-flag-v1-manual-verification-results.md`.
6. **Multiple concurrent advisories vs single price-stop field.** Open positions can show multiple trail-stop advisories (e.g., 10MA + 20MA based) but trade row supports only one stop value. Reconciliation needed: state-machine when stop adjusted to satisfy one but not all advisories. Phase 3d follow-up. _Operator framing recorded 2026-04-27 (verification-results doc §#6): maximum-communication principle — annotate, don't suppress; trade-maturity gating concept (default 20MA early, upgrade to 10MA after ~+1.5-2R)._

---

## 2026-04-28 chart-scope policy v3 (4th tier `hypothesis_rec`) — operator-paced deferral

> Chart-scope policy v2 SHIPPED 2026-04-28 (`c4820d0..527e334`); follow-up V1-deferred items + hyp-recs trade-prep expansion design — all archived. v3 retained as the only OPEN item.

**Original deferral per hyp-recs trade-prep expansion brainstorm Q2 (2026-04-28):** "Chart unavailable message for now is fine. We may eventually adjust the rules for when charts are created, that will be explicit direction from me if/when I feel the workflow needs it."

**2026-04-30 reaffirm-deferral signal:** operator took CC trade (hyp-rec; Sub-A+ VCP-not-formed); chart was unavailable per design (CC not in `aplus + open_position + tag_aware_top_n`). Operator wanted to view chart for hyp-rec trade-decision; "Chart unavailable" was working as designed but cost was real. **Operator decided to keep deferring** rather than dispatch v3 now. Trigger condition was nearly hit; track future occurrences as accumulating signal.

**Fix scope when picked up:** mirrors chart-scope policy v2 cycle structurally — migration 0013 extends `pipeline_chart_targets.source` CHECK to allow `'hypothesis_rec'`; resolver gains 4th tier (`aplus > open_position > tag_aware_top_n > hypothesis_rec`); pipeline `_step_charts` enumerates hyp-recs and renders charts. Cost: +5-15 chart renders per pipeline run (bounded by hyp-recs panel size). With Phase 3 OHLCV archive shipped, the yfinance cost is mostly archive cache hits. Brainstorm-skip viable when picked up — Q1-Q6-equivalent of v2 already known.

---

## 2026-04-30 Phase 4 cleanup-remainder follow-up

- **(2026-04-30 Phase 4 Task 7 follow-up) Promote 7-day staleness threshold to a public constant in `swing/data/ohlcv_archive.py`.** Phase 4 Task 7 inlined a `_STALENESS_THRESHOLD_DAYS = 7` class constant in `research/parity/run.py:_CountingPriceFetcher` because the data-layer's predicate is inlined at line 205-210 with no public symbol; promoting it would have required a `swing/data/` carve-out beyond Phase 4 scope (research-branch rewrite). **Risk:** if the data-layer threshold ever changes from 7, the wrapper's duplicate must be updated in lockstep — easy to miss. Promote when a `swing/data/ohlcv_archive` touch becomes natural (next archive-related dispatch).

## 2026-04-30 TOS reconciliation depth follow-ups (BUNDLED — single dispatch)

Surfaced after operator dry-ran + reconciled the 4/30 Schwab/TOS export against the production DB. Current `reconcile_tos` only verifies a SUBSET of the disagreement surface; three concrete gaps where TOS-vs-DB drift would pass reconciliation silently. **Operator decision 2026-05-01: bundle all three as a single dispatch ("real reconciliation depth").** Estimated half-day; not orchestrator-blocking; pick up when operator-prioritized vs Phase 5 / Tier-3 #6 / chart-scope-v3.

### What `reconcile_tos` verifies today (audit-trail anchor):

- **OPEN fill (BUY TO OPEN):** ticker + entry_date + qty matched against `find_open_trade_by_match`; entry_price compared with `price_tolerance` (default $0.01). Mismatches surface in `price_mismatch_fills`.
- **CLOSE fill (SELL TO CLOSE):** ticker matched against `find_any_open_trade`; cumulative qty across the batch ≤ `initial_shares`. **No price comparison.** No-match attempts a historical-claim against unclaimed recorded exits before falling through to `unmatched_close_fills`.
- **`Account Order History` section:** parsed by `parse_tos_export` but NEVER consumed by `reconcile_tos`. Working orders, stops, OCO triggers — all silently dropped.
- **`Equities` section, `Profits and Losses` section, `Account Summary` net-liq:** not parsed at all (sections aren't in `_SECTION_LABELS`).

### Gaps to address:

- **(1) CLOSE-fill price-mismatch detection.** Symmetric to the OPEN-fill check at `swing/journal/tos_import.py:193-194`. If TOS reports `SLD -5 X @42.50` but the recorded exit's `exit_price = 42.30`, surface to `price_mismatch_fills` (or a sibling `close_price_mismatch_fills` field if separate categories matter). Small fix (~30 min): in the CLOSE branch (line 208-244), after a successful match, compare `f.price` to the matching exit's price and route to the mismatch list. Need to identify WHICH exit row matched the fill — currently the live-allocation branch doesn't track that explicitly. Likely need to refactor the within_batch_alloc tracking or add an exit-id lookup. **Test:** seed an open trade with a recorded partial exit at $42.30; pass a TOS CSV with a CLOSE fill at $42.50; assert it surfaces as price_mismatch.

- **(2) Stop-order reconciliation against `Account Order History`.** TOS exports include WORKING SELL TO CLOSE stop orders in this section (e.g., the operator's 4/30 CSV has CC stop at `20.51` and DHC stop at `7.06`). `reconcile_tos` currently parses but ignores the section. Add an extractor for the STP rows + a new report category `stop_mismatches: list[(ticker, db_stop, tos_stop)]`. For each open trade, look up the corresponding TOS WORKING stop; compare `current_stop` with the TOS stop price within `price_tolerance`. Surface mismatches. ~1-2 hr including parser + reconciliation logic + tests. **Notable parser challenge:** the Order History section has variable columns + the stop value lives across two row types (`TRG BY #ref` parent row + child row with the actual stop price); needs careful parsing. **Test:** seed open trade with current_stop=20.00; pass TOS CSV with WORKING stop at 20.51; assert mismatch surfaces.

- **(3) Position-level holdings reconciliation against `Equities` section.** TOS lists current open quantities per ticker (e.g., operator's 4/30 CSV shows `CC +5` and `DHC +39`). DB's `list_open_trades` should agree, factoring partial exits. Add `Equities` to `_SECTION_LABELS` + an extractor + a new report category `position_mismatches: list[(ticker, db_qty, tos_qty)]`. Catches "TOS shows 5 shares CC; DB shows 0 shares CC" (or vice versa) — most likely cause is an unrecorded partial exit OR a missed entry. ~1-2 hr including parser + tests. **Test:** seed open trade with 5 shares + 0 exits; pass TOS CSV showing only 3 shares for that ticker; assert mismatch surfaces.

### Bundle dispatch shape (when scoped):

Single brainstorm-skip writing-plans dispatch covering all three gaps; one schema-free implementation across `swing/journal/tos_import.py` + `tests/journal/test_tos_import.py`. Real-world fixture base: operator's 4/30 Schwab/TOS export at `thinkorswim/2026-04-30-AccountStatement.csv` exercises stops + Equities; pair with synthetic permutations for edge cases (qty mismatch, price mismatch, missing stop, ticker-not-in-DB). Per-gap tasks roughly: Task 1 close-fill price-mismatch (cheapest symmetric fix); Task 2 Order-History parser + stop reconciliation; Task 3 Equities-section parser + position-qty reconciliation; Task 4 CLI report integration (display the new mismatch categories). Done criteria includes operator-witnessed dry-run against the 4/30 CSV showing all three new categories surface zero mismatches (production DB is correctly reconciled today; the new checks should confirm the existing matched state, not flag false positives).

### Cross-references:
- `swing/journal/tos_import.py:reconcile_tos` (current verification surface).
- `swing/journal/tos_import.py:_SECTION_LABELS` (parsed sections; extend for Equities + others).
- 2026-04-30 TRD-as-withdrawal fix (`c9159c7`) — same module; same operator-surfaced via 4/30 export.
- `tests/fixtures/tos/synthetic-tos.csv` — current synthetic fixture only covers entry+exit fills + DEP/WD cash flow. Bundle dispatch should extend it.
- 2026-05-04 Schwab API integration entry below — Phase A subsumes this bundle (API surfaces close-price + stop + position-qty natively).

## 2026-05-01 Journal v1.2 incorporation (Phases 6-9)

> **Phase 6 SHIPPED 2026-05-04 at `51c79ed`** + **Phase 7 SHIPPED 2026-05-05 at `c617777`** — full per-phase detail in archive. This active entry retains cross-cutting framing + Phase 8/9 (gated on Phase 7) + sequencing alternatives + modification rationale.

Sourced from operator-commissioned research at `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` (and the v1.0 → v1.1 → v1.2 evolution chain at `reference/Future Work/Trading Journal/swing_trading_journal_*.md`). v1.2 is a discretionary-trader's journal spec; OUR platform is a framework-research-loop. The phases below adopt v1.2's discipline scaffold WHERE it adds value over our existing infrastructure, modify it WHERE its assumptions conflict with our framework-driven flow, and DROP elements we don't need (pyramiding, Setup_Playbook as DB rows, Screen_Definitions versioning).

**Umbrella sequencing decision (operator 2026-05-01):** Decompose into four phases by value × independence; ship Phase 6 first as the cheapest highest-value piece, re-evaluate before committing to Phase 7's larger schema disruption. Phase 6 + Phase 7 SHIPPED; Phase 8 + 9 unblocked, operator-paced.

### Cross-cutting framing (applies to all four phases):

- **v1.2 assumes self-rated quality scoring.** Drop self-rated components that the pipeline asserts (valid setup, regime supportive, sector supportive). Keep operator-only fields (emotional_state, confidence_score, manual override-of-doctrine).
- **v1.2 assumes operator-composed thesis.** Adapt to "thesis = pipeline bucket + criteria tags + hypothesis_label" + operator-added context (why_now, invalidation_condition).
- **v1.2's `trade_origin` enum** maps onto our actual ingestion paths: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` (4-value, NOT v1.2's 7-value discretionary enum).
- **Setup_Playbook as DB entity:** DROP. Our setups are encoded in `swing/evaluation/scoring.py` + `criteria.py`; v1.2's setup_id maps to our `hypothesis_id` + doctrine layer.
- **Screen_Definitions versioning:** DROP. `finviz_schema.py` is git-versioned; explicit screen-version entity adds friction without value.
- **Pyramiding R-views (R_initial / R_effective / R_campaign):** DROP. Operator at $7,500 capital, 5 concurrent, no pyramiding plan.
- **Drawdown circuit breaker:** v1.2 defaults this opt-in disabled; align (do not enable by default).

### Sequencing alternatives (for future re-evaluation):

- **(A) Phase 6 only, defer 7-9 indefinitely.** Operator stops journal extension at the cheapest piece. Acceptable if Phase 6 turns out sufficient.
- **(B) Phase 6 + 9, defer 7 + 8.** "Journal Lite" — post-trade review + risk policy + reconciliation depth. Skips state-machine + Daily_Management.
- **(C) Full sequence 6 → 7 → 8 → 9.** Multi-month commitment to full v1.2 equivalence.
- **(D) Defer all of v1.2 until first hypothesis closure.** Per orchestrator-context lesson: "the actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence." If journal-discipline-measurement isn't bottlenecking the loop today, defer engagement until a hypothesis closes and "did the framework work?" requires deeper retrospective tooling.

**Outcome (2026-05-05):** Phase 6 + Phase 7 shipped along path (C). Phase 8/9 sequencing decision pending evaluation soak of Phase 7 production behavior.

### Modification rationale (why we don't adopt v1.2 verbatim):

v1.2 was authored agnostic of our platform. Several design choices encode discretionary-trader assumptions that don't fit our framework-research-loop:

| v1.2 assumption | Why it doesn't fit | Our adaptation |
|---|---|---|
| Trader independently composes thesis per trade | Our framework asserts thesis via bucket + criteria + hypothesis_label | Keep thesis as text field but auto-pre-fill from candidate row + hypothesis matcher; operator adds context |
| Self-rated `pre_trade_quality_score` 0-10 | Pipeline already computes A+/watch/skip + criteria pass/fail; self-rating duplicates and conflicts | Drop self-rated framework components; keep emotional_state, confidence_score, manual override |
| Setup_Playbook as DB rows with status active/pilot/paused/retired | Our setups are encoded in `swing/evaluation/`; trader doesn't manage setups as data | DROP; reference hypothesis_id when setup-attribution needed |
| Pyramiding R_views | Operator at $7,500 capital with 5 concurrent doesn't pyramid | DROP indefinitely |
| `trade_origin` 7-value discretionary enum | Our ingestion is pipeline-driven (4 paths) | 4-value pipeline-aware enum: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` |
| Drawdown circuit breaker | v1.2 default opt-in disabled (matches our caution) | Align: opt-in disabled by default |

---

## 2026-05-06 Phase 10 metrics dashboard — **brainstorm SHIPPED 2026-05-06 at `fe6cb45`**

> **Outcome:** Operator-commissioned external research at `reference/Future Work/Metrics/` (5 docs: v1.0 baseline + v1.1 + v1.1-alternate + findings + rebuttal-determinations) — orchestrator-thread analysis confirmed v1.1-alternate as structural baseline + identified framework-fit gaps requiring NEW design (hypothesis-cohort as primary axis; tier-comparison; capital-friction; maturity-stage; identification-vs-trade-funnel; deviation-outcome; process-grade-trend). Brainstorm-dispatched 2026-05-06; brief at `docs/phase10-metrics-brainstorm-brief.md` (`3ad5ea2`). Spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` (641 lines; commits `a46b458` + `fe6cb45`; 5 substantive Codex rounds + R6 confirmation → `NO_NEW_CRITICAL_MAJOR`). Three highest-leverage locked decisions: (1) **capital-denominator split-policy** — governance metrics lock to constant `$7,500`; operational/live-state metrics PROVISIONAL with `$7,500` fallback until §8.2 resolves; (2) **global statistical-confidence floor** `n=20` decoupled from cohort target; (3) **tier-comparison view** explicitly avoids false-significance signals (text-only `cohort_ci_overlap_descriptor`; no boolean flag). Mistake-cost formula DECISION: brainstorm AFFIRMS Phase 6's already-shipped v1.1-alternate / v1.2 §8.8 formula (the brief's §1.5 premise that Phase 6 ships v1.1-main was empirically wrong; Phase 6 already ships the correct formula at `swing/trades/review.py:157-174`). Spec §11 enumerates capture-needs feedback for Phase 8 (consumed) + Phase 9 + Phase 10+. **Sequencing locked: brainstorms 10 → 8 → 9; execution order 8 → 9 → 10.** RESEARCH-posture (no schema/code; only metric definitions + dashboard sketches + capture-needs feedback). Per retention discipline, this entry stays in active until next phase ship.

### Open follow-ups from Phase 10 brainstorm (operator-paced)

- **§8.6 — Surface `lucky_violation_R` on Phase 6 review form.** Phase 6 already computes + persists `total_lucky_violation_R` (per migration 0013); review form does NOT surface the per-trade or cohort field. Operator concurred with implementer's recommendation: small standalone follow-up dispatch (~30 min), separate from Phase 10 writing-plans. Not bundled with Phase 10 because it's Phase-6-surface-extension, not metrics-dashboard scope. Pick up when bandwidth allows.
- Other open questions (§8.1 fills.action enum gap; §8.2 daily equity capture; §8.3 benchmark series location; §8.4 Corporate_Actions MVP; §8.5 process_grade_rolling_N window; §8.7 decision-criteria automation) — operator concurred with implementer's recommendations across all 7. Bundled with Phase 10+ writing-plans + execution unless re-litigated.

### Open follow-ups from Phase 8 writing-plans dispatch (operator-paced)

- **V2 CLI `swing trade event-log` follow-up.** Phase 8 plan §A.2 deferred CLI per Phase 6 review surface web-only-V1 precedent. Schema + service are CLI-agnostic; landing wire-up estimated ~1-2 hours. Pick up when convenient post-Phase-8-ship; dispatch shape: small standalone CLI dispatch (mirror Phase 6 review CLI pattern at `swing/cli.py` review-command region; reuse Phase 8's `record_event_log` service helper).

### Phase 8 V1 follow-ups (operator-witnessed gate observations 2026-05-07)

> **Status: BOTH SHIPPED to main 2026-05-08 at integration merge `24b3e9a`** (worktree branch `worktree-phase8-v1-polish` → main; 16 commits = 12 task-impl + 4 adversarial-fix). Plan: `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`. Test count delta: 2079 → 2090 (+11 fast tests). Ruff baseline 78 preserved. Schema unchanged at v16. Writing-plans 2 Codex rounds + executing-plans 3 Codex rounds → both NO_NEW_CRITICAL_MAJOR; convergent shape (executing-plans tapered 3→1→0 majors; sort-key tiebreak hardened in `7c08f12` from R1 finding). 4-surface operator-witnessed gate PASS via Chrome MCP walkthrough 2026-05-08 (Surface 1 Detail button on every open-position row; Surface 2 timeline union surfaces orphan stop-adjusts on DHC chronologically; Surface 3 dedup via `linked_trade_event_id` correctly suppresses Phase-8-form-written trade_events; Surface 4 regression-spot-check across all 7 routes). Three V2 advisory items captured at the §"Phase 8 V2 advisory items" subsection below. Per retention discipline this entry stays in active until next phase ship.

- **Phase 7 stop-adjust legacy path doesn't surface in Phase 8 timeline (Surface 6 finding).** ~~When operator uses the dashboard's "Adjust stop" button (Phase 7 route at `/trades/<id>/stop`), the resulting `trade_events` row IS audit-trailed but does NOT appear in Phase 8's per-trade `daily-management-timeline` view~~ — **SHIPPED.** Took path (a): VM-level read-side union. `build_daily_management_timeline_vm` now unions Phase 7 orphan `trade_events` of `event_type='stop_adjust'` (those NOT linked via `daily_management_records.linked_trade_event_id`) into the timeline, rendered as `record_type='trade_event_legacy'` with badge "Stop adjustment (legacy quick-adjust)".
- **No dashboard → bare detail page navigation link.** ~~Operator can navigate to `/trades/<id>` only via direct URL~~ — **SHIPPED.** `partials/open_positions_row.html.j2` now emits `<a href="/trades/{id}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>` after the existing Exit + Adjust stop buttons.
- **emotional_state form preserves stale checkbox state across browser visit cycles.** When operator visually toggles checkboxes during inspection (without submitting), those checkmarks persist in browser form state through subsequent navigations away + back to the detail page. Cosmetic; potentially confusing for next-time submission. **Fix:** form re-render on detail-page GET should explicitly clear any preserved checkbox state (re-initialize `vm.emotional_state_set` to `()`). May require deeper investigation of where the persistence comes from (server-side render OR browser autofill). Defer until operator confirms confusion; not a correctness issue.
- **Spec wording vs implementation: "GAP-FLAGGED" → "gap-by-absence".** Phase 8 spec §2.2 + Surface 5 brief-language said gap-handling would "flag missed-day in §7.2 timeline as `(no snapshot — pipeline did not run)`"; actual implementation is gap-by-absence (no row written for missed days; operator infers gap from row-date discontinuity in timeline). Functionally equivalent (operator sees the gap visually) but spec-vs-impl wording mismatch. **Fix:** Phase 8 V2 adds explicit placeholder rows in timeline for missed days OR spec amended to match gap-by-absence. Defer until operator naturally encounters a gap workflow + confirms whether explicit placeholders would be useful. Cosmetic.
- ~~**Worktree husk `.worktrees/phase8-daily-management/` ACL-locked at integration merge.**~~ **RESOLVED 2026-05-07** (operator-elevated cleanup performed). Same Windows ACL pattern as Phase 6/7 cleanup leftovers; cleared via existing `cleanup-locked-scratch-dirs.ps1` extension landed at `5430c1c`.

### Phase 8 V2 advisory items (surfaced 2026-05-07 writing-plans + executing-plans phase8-v1-polish)

Three non-blocking advisories surfaced during phase8-v1-polish dispatches (2026-05-07; plan at `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`). All noted as out-of-scope for V1 polish; surfaced here so they don't decay.

- **Audit-chain symmetry: legacy `/trades/{id}/stop` route also writes Phase 8 event_log row.** V1 polish surfaces legacy stop-adjusts via read-side VM union; does NOT write Phase 8 audit rows for them. If operator eventually wants the timeline uniformly Phase-8-shaped (every stop-change has both a `trade_events` row AND an `event_log` row with `linked_trade_event_id`), the legacy route should be refactored to call `record_event_log` atomically instead of writing only `trade_events` directly. ~3-4 hr standalone dispatch (route + tests + audit-chain alignment). Defer until operator surfaces a workflow gap that this would close.
- **Template `data-trade-event-id` attribute for orphan rows.** Plan §A.2 sort-tiebreak uses `-trade_events.id` for orphan rows; the template currently exposes `data-timeline-record-id="-{event.id}"` (negative-int-from-positive-PK). If a future feature deep-links to a specific orphan row (e.g., notification → "your stop-adjust on AAPL was logged as legacy"), parsing the negative ID is awkward. A dedicated `data-trade-event-id` attribute on `trade_event_legacy` rows would be cleaner. ~15 min cosmetic; defer until first deep-link consumer surfaces.
- **Read-side snapshot consistency for `build_daily_management_timeline_vm` (R2 acceptance, 2026-05-07).** Surfaced by adversarial-critic R1 Major 2 + clarified by R2 Major 1. The VM build issues two sequential SELECTs (`list_for_trade_timeline` then `list_events_for_trade`) without a wrapping read transaction. Python's default `sqlite3` isolation does NOT escalate SELECT-only flows to a snapshot read; `with conn:` only manages commit/rollback on exit. If a `record_event_log` COMMIT lands BETWEEN the two reads, the timeline VM can compute `linked_event_ids` from a pre-commit `records` view while seeing the post-commit `trade_events` row in `events` — producing a false "(legacy quick-adjust)" row that omits the canonical Phase 8 `event_log` row for the same change. Impact framing (R2-corrected): NOT a microsecond UI flash; the rendered HTML page persists with the wrong content until the operator refreshes or navigates. Underlying tables stay correct (no data corruption). Probability: very low on a single-operator desktop app (Windows, journal_mode=delete, single FastAPI worker process; the operator must submit the Phase 8 form AND view the same trade's detail page via separate concurrent requests AT exactly the moment the read interleaves with the commit). Fix options: (a) collapse the union into a single SQL query JOIN (clean V2 refactor); (b) manually `BEGIN DEFERRED + COMMIT` around both reads (requires `conn.isolation_level=None` manipulation that ripples through the function's call chain). Both options exceed V1-polish dispatch scope; banked here for V2.

---

## 2026-05-04 Finviz Elite API integration — **SHIPPED 2026-05-06 at `002338a`** (V1)

> **Outcome:** Brainstorm-skipped per operator + orchestrator in-thread design lock 2026-05-05 (Q1-Q8 from the original queued entry below answered + locked + Q-bonus on file-collision policy). Writing-plans dispatch shipped plan `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (5 Codex rounds → NO_NEW_CRITICAL_MAJOR; HEAD `734ba6f`). Executing-plans dispatch on worktree branch `finviz-api-integration` (BASELINE_SHA `734ba6f`); 17 task-anchored commits + 5 Codex-fix commits; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR. Operator-witnessed verification gate 2026-05-06: 1 mid-verification fix (`code-review I1` at `0e02ed6` — `swing/data/repos/finviz_api_calls.py:insert_call` removed internal `conn.commit()` that was breaking `lease.fenced_write()` contract on the pipeline path; CLI raw-conn path now commits explicitly); all 8 surfaces PASS post-fix. Integration merge `002338a`. Test count delta: +63 fast (1877 → 1940) + 2 slow live tests; ruff baseline 78 preserved. Production DB at schema_version 15 with new `finviz_api_calls` audit table. New `swing/integrations/` namespace established as pattern for future Schwab API integration. New CLI: `swing finviz fetch` + `swing finviz status`. Drift-detection signature-hash + WARNING emission verified via DB-tamper test (Finviz API URL params fully define the screen — no saved-screen-handle to edit on UI side per writing-plans research finding). Two new lessons captured in `docs/orchestrator-context.md` §"Lessons captured": subprocess cfg-propagation (Codex R2 finding; child-process CLI body is binding override point) + repo-functions-must-not-commit (operator-witnessed I1 finding). Per retention discipline, this entry stays in active until next phase ship; original queued content retained below for historical reference.

### Current state (orchestrator survey 2026-05-04):

- **Manual ingestion:** operator exports a Finviz screen as CSV with 13 specific columns (`No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`); names file `finvizDDMmmYYYY.csv`; drops in `data/finviz-inbox/`.
- **Validator:** `swing/pipeline/finviz_schema.py:12` checks 13-column schema; missing columns → reject to `data/finviz-inbox/rejected/` with sidecar JSON.
- **Pipeline consumption:** `_step_evaluate` reads the CSV, ingests rows as candidates, drops Sector/Industry until Phase 4 wired them.
- **Cadence:** daily (operator's actual workflow per `docs/cycle-checklist.md`).
- **Failure modes today:** wrong column count (rejected); wrong filename pattern (silently skipped); operator forgot to export (pipeline runs against stale or empty inbox).

### V1 scope (sketch — pre-brainstorm):

1. **`swing/integrations/finviz_api.py`** — auth (API token from a new `cfg.integrations.finviz.token` field; persist in user-config TOML per Phase 5 infrastructure, NOT tracked toml). Wraps the Finviz Elite REST endpoint with the operator's saved-screen-id parameter.
2. **Pipeline ingestion path** — new `_step_finviz_fetch` runs BEFORE `_step_evaluate`; pulls latest screen results; emits to the same 13-column CSV format in `data/finviz-inbox/` (preserves the existing validator + rejected-fallback pattern). Manual CSV drop remains supported as fallback if API unavailable.
3. **Structured logging** — per-call: timestamp, screen_id, row count, response time, rate-limit consumed, rate-limit remaining; persisted to a new `finviz_api_calls` table (or appended to `pipeline_runs.notes`); surfaced on dashboard pipeline-status surface.
4. **CLI parity** — `swing finviz fetch` command for ad-hoc invocation outside the pipeline; `swing finviz status` for rate-limit + recent-call inspection.
5. **Config surface** — add `[integrations.finviz]` section with token + screen_id + (optional) timeout/retry params; surface in Phase 5 config page in V2 if operator wants edit access.

### Open design questions (for brainstorm dispatch):

1. **Cost confirmation.** Finviz Elite is a paid subscription (~$40/mo). Confirm operator is on Elite OR plans to subscribe before any work commits. If not, this entry stays QUEUED indefinitely.
2. **Screen-id management.** The screen is currently a saved Finviz user-screen (operator-created). API likely requires a screen_id reference. Persist as cfg field; surface in config page as V2.
3. **Rate-limit handling.** Finviz Elite API documents rate limits (TBD: needs operator-confirmed quota). Pipeline cadence is daily so likely fine; ad-hoc CLI invocations need backoff.
4. **Schema-parity verification.** Verify Finviz API response fields map 1:1 to the 13-column CSV schema. If API returns different column set, the integration layer normalizes before emitting to the canonical schema (same validator runs).
5. **Failure fallback.** If API returns error / rate-limit-exceeded / network failure, pipeline should LOG and skip — not fail the entire run. Operator can drop a manual CSV as backup.
6. **Token storage.** API token is sensitive; persist in user-config TOML (per Phase 5 infrastructure, outside Drive) NOT in tracked `swing.config.toml`. Revisit if Phase 9 introduces a secrets-management layer.
7. **Sector/industry consistency.** Phase 4 wired Sector/Industry from the CSV; API-emitted CSV must preserve same field names + values to avoid breaking the existing pipeline ingestion.
8. **Screen-version drift.** The operator's saved screen on Finviz can be edited; API call would silently start returning different rows. Capture screen-id + (if available) screen-version-hash on each fetch; surface drift detection on dashboard.

### V1-deferred / V2:

- **Multi-screen support** (operator currently runs one screen; future: A+ screen + watchlist screen + research screen).
- **Backfill mode** — pull historical screen results for evidence-loop research (depends on Finviz Elite API supporting historical-screen endpoints; unverified).
- **Real-time price feed** (Finviz Elite has a price stream; out-of-V1; redundant with potential Schwab API integration below).

### Cross-references:

- `swing/pipeline/finviz_schema.py:12` (validator — preserve schema contract).
- `data/finviz-inbox/` (canonical drop directory; preserve as fallback).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.finviz` section).
- `docs/cycle-checklist.md` (daily operator workflow — fetch step replaces manual export).
- 2026-05-04 Schwab API integration entry below (may share `swing/integrations/` namespace + secrets-management approach).

---

## 2026-05-04 Schwab API integration (QUEUED; Large effort; multi-phase; brainstorm needed)

Operator-surfaced 2026-05-04. Three concurrent uses of the official Charles Schwab Trader API (https://developer.schwab.com/): (1) automate account reconciliation (replace TOS-CSV-import workflow + subsume the queued 2026-04-30 TOS reconciliation depth bundle); (2) potentially automate trade entry/exit/stop-management; (3) provide an alternative data source to yfinance (real-time prices + intraday OHLCV + fundamentals — addresses 4+ yfinance gotchas in CLAUDE.md). This is a comparable-to-Phase-7-9-scope multi-phase commitment; not a single dispatch.

### Current state (orchestrator survey 2026-05-04):

- **Operator already on Schwab.** `thinkorswim/2026-04-30-AccountStatement.csv` is the manual TOS export; production DB has 3 trades reconciled against it.
- **TOS-CSV reconciliation:** `swing journal import-tos` reads the CSV; `reconcile_tos` verifies a SUBSET of disagreement surface (entry-fill price-mismatch only; gaps for close-price, stop-orders, position-qty per the queued 2026-04-30 TOS bundle).
- **yfinance is the SOLE production data source** — historical OHLCV (consolidated archive at `swing/data/ohlcv_archive.py` after Phase 3 OHLCV consolidation 2026-04-30); price fetcher (`swing/prices.py PriceFetcher`); `_step_charts` chart fetch. Multiple production-impacting yfinance API regressions captured in CLAUDE.md gotchas.
- **No trade automation today** — all entry / exit / stop-adjust go through manual CLI or web form; trader places orders manually in Schwab/TOS UI.

### V1 scope (sketch — pre-brainstorm; multi-phase decomposition):

**Candidate library:** [Schwabdev](https://github.com/tylerebowers/Schwabdev) — unofficial Python wrapper for the Schwab Trader API; covers OAuth 3-legged flow + account/positions/orders/quotes/streamer endpoints. Evaluate at brainstorm time vs build-from-scratch (see design question 1 below).

**Phase A — OAuth + read-only account access (cheapest first):**
1. **Schwab Developer Portal app registration** (operator action; production-access approval can take days).
2. **`swing/integrations/schwab/auth.py`** — OAuth 3-legged flow; refresh-token persistence in user-config TOML (parallel to Phase 5 infrastructure). If Schwabdev adopted, this layer is a thin wrapper around Schwabdev's auth handling rather than rolling our own.
3. **`swing/integrations/schwab/account.py`** — read-only: positions, balances, transactions. Maps to current `tos_import` data shape.
4. **`swing journal reconcile-schwab`** CLI — replaces `swing journal import-tos` for the API-available account-state surfaces. CSV import path remains supported as fallback.
5. **Subsumes the 2026-04-30 TOS reconciliation depth bundle** (close-price + stop + position-qty mismatch detection) — API surfaces these natively; no CSV-parsing edge cases.

**Phase B — Alternative data source (highest-value second):**
6. **`swing/integrations/schwab/market_data.py`** — quote, OHLCV (daily + intraday), fundamentals. Wrap with same interface as `swing/prices.py PriceFetcher` so caller code is data-source-agnostic.
7. **`cfg.data_source.primary`** = `"yfinance" | "schwab"` (default `"yfinance"` for V1; flip to `"schwab"` after parity verification). Per-call fallback if primary errors.
8. **Parity verification harness** — research-branch dispatch comparing yfinance vs Schwab on N tickers × M sessions; document divergence (price + dividend-adjustment + corporate-action handling).
9. **Replaces multiple yfinance gotchas** — `Ticker.history` `threads=` regression; `group_by='column'` MultiIndex; `interval=1d` partial-bar inclusion; rate-limit pressure.

**Phase C — Trade automation (highest-risk last; opt-in only):**
10. **`swing/integrations/schwab/orders.py`** — place stop-buy entry (per hypothesis-tagged trade discipline); place initial stop; modify stop on advisory-trail trigger.
11. **`cfg.trade_automation.enabled`** = `false` default; explicit operator opt-in per trade.
12. **Dry-run mode** — emit the order JSON without submitting; operator reviews + confirms manually OR commits to live submission.
13. **Audit log** — every API call logged with request + response + timestamp; persisted to a new `schwab_orders` table joined to `trades` for full audit trail.
14. **Bilateral verification** — every automated order followed by a Schwab API position-state read to confirm the order landed; mismatch → halt automation + alert operator.

### Open design questions (for brainstorm dispatch):

1. **Library choice: three candidates surfaced 2026-05-06.** Evaluate at brainstorm time:
   - **Schwabdev** (https://github.com/tylerebowers/Schwabdev) — wraps entire Schwab Trader API surface (auth/account/orders/market data/streamer); single-author; newer trajectory.
   - **schwab-py** (https://github.com/alexgolec/schwab-py) — by alexgolec who previously authored `tda-api` for the TD Ameritrade API; multi-year community-usage lineage; broker-API client design experience.
   - **Build-from-scratch** — direct Schwab Trader API integration in `swing/integrations/schwab/`; max control + max maintenance burden.
   Operator leaning toward schwabdev (2026-05-06) but explicitly evaluating at brainstorm time. Risks: unofficial wrappers can break on Schwab API changes; maintainer-bus-factor; supply-chain trust. For any wrapper choice, recommend vendored / version-pinned dependency + thin abstraction layer (`swing/integrations/schwab/client.py`) so swap-to-direct-API is bounded if the wrapper goes stale.
2. **Phase A vs Phase B vs Phase C ordering — operator preference.** Recommendation: A (account reconciliation) → B (data source) → C (trade automation). A is cheapest; B has highest yfinance-pain-relief value; C is highest-risk + lowest urgency at $7,500 capital with 1-2 trades/month pace.
3. **OAuth refresh-token storage location.** User-config TOML (per Phase 5)? New encrypted store? Operator's risk preference.
4. ~~**Schwab Developer Portal production-access approval time.**~~ **RESOLVED 2026-05-06.** Operator confirms Dev Portal app registration + production-access approval are both COMPLETE. The long-pole approval friction is gone — when Phase A is sequenced, brainstorm + writing-plans + executing-plans can dispatch immediately without external approval gating.
5. **Schwab API entitlements scope.** Read-only account vs trading entitlements require separate Schwab approvals; operator decides per-phase.
6. **yfinance vs Schwab data parity.** Adjusted vs unadjusted prices; corporate-action handling; dividend treatment; intraday-bar timestamping. Need a parity study before flipping `cfg.data_source.primary`.
7. **Trade automation safety gates.** Hard maximums (per-trade size; daily order count; circuit breaker on N consecutive failed orders); operator-defined override path.
8. **Subsumption of TOS-CSV bundle.** When Schwab API account access works, does the 2026-04-30 TOS reconciliation depth bundle get DROPPED or RETAINED as fallback for offline-mode? Recommendation: retain CSV path as fallback (defense-in-depth); but the queued depth-bundle work becomes lower priority since the API surfaces the same data natively.
9. **Sequencing vs Phase 9 (Risk_Policy + reconciliation depth).** Phase 9 from journal v1.2 covers reconciliation depth + Risk_Policy entity. Schwab API Phase A IS the reconciliation-depth implementation; logical merger is "Phase 9 ships using Schwab API as the data layer." Re-evaluate when both items ripen.
10. **Cost.** Schwab API access is free for account holders; no subscription cost like Finviz Elite. Approval friction is the primary cost.
11. **Failure fallback.** Trade-automation failure modes are operationally severe (failed entry on a hypothesis-tagged trade = lost evidence). Phase C MUST have explicit fallback-to-manual semantics + clear operator alerting.

### V1-deferred / V2:

- **Multi-account support** (operator has one trading account; future: separate research / paper-trading accounts).
- **Options trading** (out of framework scope; equity swing-trade only).
- **Schwab StreamerAPI** (real-time quotes via WebSocket; future if dashboard real-time price ticks become valuable).

### Cross-references:

- `thinkorswim/2026-04-30-AccountStatement.csv` (current manual reconciliation source; replaced by Phase A).
- `swing/journal/tos_import.py` (`reconcile_tos` + `extract_cash_movements`; CSV path retained as fallback).
- 2026-04-30 TOS reconciliation depth follow-ups bundle (subsumed by Phase A; lower priority once API works).
- 2026-05-01 Journal v1.2 incorporation Phase 9 (Risk_Policy + reconciliation depth — logical merger with Schwab API Phase A).
- `swing/prices.py PriceFetcher` (current yfinance interface; Phase B mirrors).
- `swing/data/ohlcv_archive.py` (Phase 3 consolidated archive; Phase B fetch path writes here for parity).
- CLAUDE.md gotchas (4+ yfinance regressions Phase B replaces).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.schwab` section).
- 2026-05-04 Finviz API integration entry above (shared `swing/integrations/` namespace + secrets-management approach).
- Schwabdev unofficial Python wrapper: https://github.com/tylerebowers/Schwabdev (candidate library; see V1 sketch + design question 1).

---

## 2026-05-05 Sector/industry tamper vector hardening (BACKLOG; SCHEDULED for Phase 9; low-stakes)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R3 Minor 2** (accepted-deferred per operator triage 2026-05-05; **operator-decided Phase 9 inclusion**). Sub-C C.3 entry route hardened the chart_pattern_algo + classification_pipeline_run_id round-trip with route-layer enum + FK existence + cache-content match validation (Codex R1 M1 + R2 M1 fixes). The sector + industry hidden-form snapshots have NO analogous server-side cache/content validation — a forged form POST could persist arbitrary sector/industry strings.

**Why low-stakes (today):** sector + industry are descriptive metadata only; they do NOT feed gating logic, A+ identification, hypothesis attribution, or trade-decision algorithms (per spec §11.3 + observations across `swing/evaluation/`). Compromising them produces wrong dashboard labels but does not corrupt correctness-critical paths.

**Why scheduled for Phase 9:** Phase 9 Risk_Policy entity introduces sector concentration limits (`max_sector_concentration_positions` per v1.2 §7.8). Once sector becomes a gating dimension, the tamper vector becomes correctness-critical — same severity as the chart_pattern_algo concern. Bundling the hardening into Phase 9 aligns the fix with the criticality elevation.

**V1 scope (executed within Phase 9):**
1. Route-layer Finviz-snapshot existence check at trade entry POST (mirror chart_pattern pattern in `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`).
2. Reject if `(ticker, action_session)` sector/industry snapshot doesn't match cached candidate row.
3. Same-shape route + test pattern as chart_pattern hardening.

**Estimated effort if triggered:** 1-2 hours (mechanical mirror of chart_pattern route-layer pattern).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R3 Minor 2 accepted-deferred + operator decision to schedule for Phase 9).
- `swing/web/routes/trades.py` chart_pattern hardening (commits `117dc97` + `2b9d6f3`) — fix-pattern template.
- Phase 9 Risk_Policy entity (sector concentration limits = trigger).
- v1.2 §7.8 `max_sector_concentration_positions` field.

---

## 2026-05-05 Fill.quantity fractional-share forward-compat (BACKLOG; gated on fractional-share feature)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R1 Major 3** (accepted-with-rationale per operator triage). `Fill.quantity` is REAL in schema (Sub-A migration 0014); ~7 modules currently truncate to int via `_ExitShape` adapters because all current production code paths produce integer-share fills (`compute_shares()` returns int; CLI/web/trim/exit all submit `shares: int`). Forward-compat concern: when fractional-share trading lands, the int truncation across 7 modules becomes a bug surface.

**Trigger:** future feature work introducing fractional-share trading. Most likely path: Schwab API integration Phase B (broker fills can be fractional in modern broker APIs) OR an explicit operator decision to trade fractional shares.

**V1 scope when triggered:**
1. Audit the 7 modules with `_ExitShape` int-truncation (enumerated in code comment at `swing/web/view_models/trades.py:_ExitShape` declaration per Sub-C R1 M3 ACCEPTED-with-rationale).
2. Refactor each consumer to handle REAL `quantity` correctly (display formatting; aggregation arithmetic; CLI parsing; web form input).
3. Update `compute_shares()` to optionally return float when fractional flag set.
4. Add Fractional-share-specific test coverage.

**Estimated effort if triggered:** 3-5 hours (mechanical type widening across 7 modules + format polish + tests).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R1 Major 3 accepted-with-rationale).
- `swing/web/view_models/trades.py:_ExitShape` declaration — code comment enumerates the 7 affected modules.
- Schwab API integration Phase B (`docs/phase3e-todo.md` 2026-05-04 entry) — likely activation trigger.

---

## 2026-05-04 Future schema migration: trade.entry_date datetime promotion (BACKLOG)

**Surfaced 2026-05-04 by Phase 7 Sub-B Codex R5 finding** (open question 2). Phase 7 keeps `trades.entry_date` as YYYY-MM-DD date-only TEXT column. The B.1 atomic-flow refactor's `_normalize_trade_event_date_to_iso` helper accepts the date-only `entry_date` + synthesizes the `T<HH:MM:SS>` portion for the entry-fill `fill_datetime`. Many downstream consumers call `date.fromisoformat(trade.entry_date)` directly (CLI hold-duration; `swing/journal/{flags,analyze}.py`; `swing/trades/advisory.py`; `swing/pipeline/briefing.py`; `swing/cli.py`).

**Why this is in the backlog:** any future schema migration that wants to promote `trades.entry_date` to ISO datetime (e.g., for sub-second precision; for tz-aware tracking; for richer chronology in research-branch back-tests) would need to migrate every `date.fromisoformat(trade.entry_date)` consumer. Scope is bounded but cross-cutting.

**Trigger:** future phase that has a use case for sub-day entry datetime precision (likely Phase 9 if Schwab API integration ships and broker fill timestamps become canonical) OR research-branch needs (intraday entry timing studies).

**Estimated dispatches if triggered:** 1 brainstorm (operator decides whether to promote vs keep date-only) + 1 writing-plans + 1 executing-plans (consumer audit + migration + per-consumer rewrite + tests).

**Cross-references:**
- Phase 7 Sub-B return report 2026-05-04 (open question 2).
- `swing/cli.py`, `swing/journal/flags.py`, `swing/journal/analyze.py`, `swing/trades/advisory.py`, `swing/pipeline/briefing.py` — current consumers of `date.fromisoformat(trade.entry_date)`.
- Phase 7 Sub-B `_normalize_trade_event_date_to_iso` helper (commits `e6541fe..71ddb95`) — established pattern for trade-chronology canonicalization at service boundary; likely the migration's API surface.
- 2026-05-04 Schwab API integration entry (Phase B market_data integration may surface intraday-precision needs).

## 2026-05-09 Chart pattern detection v2 — research captured (RESEARCH-CAPTURED; greenfield expansion; brainstorm-needed)

**Operator-surfaced 2026-05-09**: dropped three reference documents into `reference/Future Work/Chart Pattern Detection/` (committed `6b40292`). These describe research informing potential paths forward for expanding chart-pattern detection from the shipped flag-v1 classifier to a full swing-trading setup detector.

### Reference documents

- **`stock_chart_pattern_detection_ai_ingestion.md`** (v1.0) — generic original; surveys 9 mathematical approaches across all chart-pattern families.
- **`stock_chart_pattern_detection_delta_review.md`** — section-by-section critical review re-scoping for swing trading (Minervini/CANSLIM); adds VCP as headline pattern, Development Data Strategy, Drift Detection, Small ML Model Decision Analysis with G1-G7 implementation gates.
- **`stock_chart_pattern_detection_ai_ingestion_v2.md`** (v2.0; **canonical** — supersedes v1.0 per its frontmatter) — merged swing-trading-scoped analysis brief; 8-phase roadmap; rule-based + template-matching as production primary; ML re-ranker deferred 12-18 months gated on G1-G7.

### Trigger and effort estimate

**Trigger:** operator decision to expand beyond flag-v1 classifier scope. Likely sequence-locked after Phase 9 (risk_policy + reconciliation) + Phase 10 (metrics dashboard) ship, since outcome-distribution surfaces in the review interface depend on the metrics infrastructure being in place.

**Effort estimate (pre-brainstorm; speculative):** comparable-to-Phase-7-or-larger multi-phase commitment. Universe pipeline (Phase 0 in v2's roadmap) is potentially valuable on its own and could be the first dispatchable slice — runs once daily, gates pattern detection, surfaces useful trend-template state independent of any pattern detector.

**Brainstorm gate:** v2 doc is research-quality — explicit + introspectable but not project-scoped. Brainstorm dispatch would translate the 8-phase roadmap into project-specific phase decomposition (likely "Phase 11+ chart-pattern detection v2" or similar) with concrete schema + CLI + web surfaces, reconciliation against shipped flag-v1 module, and integration points with shipped Phase 6 (review_log) + Phase 7 (state machine + fills) + Phase 9 (risk_policy) + Phase 10 (metrics).

### Cross-references

- `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` — canonical v2 analysis brief.
- 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups (above) — flag-v1-specific, narrower scope; calibration study + schema-layer hardening + hidden-form-field tampering hardening remain valid for flag-v1 itself even under v2.
- 2026-04-27 chart-pattern flag-v1 V1-ship gates — operator-paced gates for shipping flag-v1 V1 (precedes any v2 work).
- `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` — flag-v1 brainstorm spec (subsumed under v2's broader scope but flag-v1 implementation choices remain authoritative for the pole-and-flag pattern).
- 2026-05-06 Phase 10 metrics dashboard entry (above) — outcome-distribution surfaces in v2's review interface depend on Phase 10 infrastructure.
- 2026-05-04 Schwab API integration entry (above) — v2's "delisted-stock data is essential" requirement may surface in Schwab Phase B market-data integration scope.

## 2026-05-10 Ruff residual cleanup (BACKLOG; **N818 SHIPPED 2026-05-10 at `44ac760`**; E501 still open)

> **N818 outcome (2026-05-10):** SHIPPED as Task family C in polish bundle 2026-05-10 (commit `efd3e15`). All 8 exception class renames landed in one mechanical commit: `SchemaVersionMismatch`, `LeaseRevoked`, `WatchlistEntryNotFound`, `ConcurrentRunBlocked`, `ChartingUnavailable`, `SoftWarnException`, `HardCapException`, `DuplicateOpenPositionException` → `…Error` suffixed. ~284 lines changed across `swing/` + `tests/` + `docs/` (the docs/ touches were spec/plan/backlog historical-reference renames; Codex R1 Minor #1 surfaced that the phase3e-todo N818 table cells got reflowed by the sed pass and the audit trail was restored via parenthetical). Ruff baseline 26 → 18 (matches expectation). 18 E501 still open per below.

**Surfaced 2026-05-10** during a ruff sweep that took the `swing/` baseline from 78 → 26 across three commits (`e99047f` safe auto-fixes 78→44, `33338f7` unsafe auto-fixes 44→34, `9c9b57c` manual B904+E741+SIM115-noqa batch 34→26). The 26 remaining are deferred for bundling with other minor fixes rather than a dedicated dispatch.

### Remaining ruff issues in `swing/`

| Code | Count | Description | Effort | Risk |
|---|---:|---|---|---|
| **N818** | 8 | Exception class names lacking `Error` suffix | ~10 min mechanical rename + verify | Medium — cross-cutting (~79 file references across swing/ + tests/) |
| **E501** | 18 | Lines exceeding 100-char `line-length` | ~30 min judgment work | Low per-site; no mechanical fix |

### N818 — exception class renames (8 classes)

Each rename is a sed-style global replace; names are distinctive enough that no substring false-positives are likely.

| Old | New | swing/ files | tests/ files |
|---|---|---:|---:|
| `SchemaVersionMismatch` (renamed to `SchemaVersionMismatchError`) | `SchemaVersionMismatchError` | 4 | 4 |
| `LeaseRevoked` (renamed to `LeaseRevokedError`) | `LeaseRevokedError` | 10 | 12 |
| `WatchlistEntryNotFound` (renamed to `WatchlistEntryNotFoundError`) | `WatchlistEntryNotFoundError` | 2 | 2 |
| `ConcurrentRunBlocked` (renamed to `ConcurrentRunBlockedError`) | `ConcurrentRunBlockedError` | 4 | 4 |
| `ChartingUnavailable` (renamed to `ChartingUnavailableError`) | `ChartingUnavailableError` | 4 | 2 |
| `SoftWarnException` (renamed to `SoftWarnError`) | `SoftWarnError` | 6 | 4 |
| `HardCapException` (renamed to `HardCapError`) | `HardCapError` | 7 | 2 |
| `DuplicateOpenPositionException` (renamed to `DuplicateOpenPositionError`) | `DuplicateOpenPositionError` | 7 | 5 |

(Note: this table was a planning artifact pre-2026-05-10 polish bundle rename. Both columns originally read identically because the planner left the "Old" cell as a TODO mirror of "New"; the polish-bundle-2026-05-10 sed pass through `docs/` reflowed the still-pending TODO mirrors. The old-name parenthetical above restores the audit trail.)

**Approach when attempted:** `git grep -l <OldName> | xargs sed -i 's/<OldName>/<NewName>/g'` per class; run `pytest -m "not slow"` after each batch (or after the full set) to verify; commit as a single rename pass.

**Watch-item:** verify no test asserts on the OLD class name as a string literal (e.g., `pytest.raises(ValueError, match="WatchlistEntryNotFound")` would have to become `match="WatchlistEntryNotFoundError"`). If found, those test assertions need the new name too — sed handles that uniformly since the match string contains the class name.

### E501 — line-too-long (18 lines)

`line-length = 100` is already configured (per `pyproject.toml`). The 18 violators exceed even that. No mechanical fix; each needs an editorial choice (break the string literal, extract a variable, accept a `# noqa: E501` for a justified comment). Would benefit from looking at all 18 sites and grouping by category (long log strings, long expressions, long comments) before deciding.

### Bundling guidance

These are good candidates to fold into ANY future small-scope dispatch as out-of-band cleanup, e.g.:
- A backlog UX-polish bundle (3e.4 + 3e.7) — add the N818 rename as a separate commit in the same dispatch
- A future tooling/lint pass — bundle with any pyproject.toml or CI configuration work
- Phase 9 writing-plans/executing-plans dispatch — N818 may surface naturally if any new exception classes get added (single batch commit at that point covers both new + legacy)

Per project baseline-tracking convention: when bundled in, update `docs/orchestrator-context.md`'s "ruff baseline" line in the track-record summary to the post-fix count. (CLAUDE.md does not currently track a ruff baseline; the living-state mention is in orchestrator-context.md.)

### Cross-references

- Sweep commits: `e99047f`, `33338f7`, `9c9b57c` on `main` (2026-05-10).
- `docs/orchestrator-context.md` track-record summary still reads "ruff baseline 78 preserved" (anchored to HEAD `b4bb9dd` polish-bundle ship — historical narrative). The live state at HEAD `9c9b57c` is **26**; orchestrator-context.md track-record summary line should be updated to the new live count at next housekeeping commit, OR when this backlog item is attempted (whichever comes first).

---

## 2026-05-10 Formalize orchestrator-vs-implementer execution-mode policy (PROCESS; below current backlog priority)

**Operator-surfaced 2026-05-10** during the 3e.16 dispatch design-question round. Operator clarified the principle: **default to implementer-dispatch over orchestrator-inline; minimize orchestrator context growth; crossover where inline beats dispatch is when orchestrator's token cost is less than the implementer's spinup-plus-task cost.** Captured as auto-memory at `feedback_orchestrator_vs_implementer_execution.md`. This entry tracks the formalization work to make the policy operationally enforceable across future sessions.

### Why formalize

- Auto-memory captures the principle but is fuzzy on the cost-estimation method. Without a heuristic the orchestrator can run pre-task, the default-to-dispatch rule will erode under orchestrator-side optimism ("this one is small enough").
- This session already had orchestrator-inline drift (operator-gate I1 + 3e.15 both inline) before the principle was made explicit. Recurrence likely without a checklist.
- Brief-drafting checklist + orchestrator-context Conventions section both lack a "decide execution mode" step — currently implicit in operator-driven choice (which means the orchestrator carries the cognitive load each time).

### Scope (what "formalize" likely means)

1. **Cost-estimation heuristic.** A back-of-envelope rubric the orchestrator runs before each task:
   - Estimate orchestrator token cost: file reads + file edits + tests written + commit drafting + housekeeping. Use ~prior-session anchors as benchmarks (3e.15 was ~5-8k orchestrator tokens; operator-gate I1 was ~3-4k; polish-bundle-2026-05-10 brief authorship was ~12-15k orchestrator tokens for the dispatch path).
   - Estimate implementer spinup cost: bootstrap (CLAUDE.md + orch-context + brief read) ≈ 30-50k tokens; plus task-implementation cost (~similar to orchestrator-inline since same code surface).
   - Crossover: if estimated orchestrator-inline < ~30k AND task is single-file + no TDD discipline benefit + no adversarial-review benefit, INLINE; else DISPATCH.

2. **Brief-drafting checklist addition.** Add a §0 "execution mode decision" line: orchestrator records the chosen mode + rationale BEFORE drafting brief content. Forces explicit consideration.

3. **Orchestrator-context Conventions update.** Promote the auto-memory feedback into a Conventions §-level entry (with cap-rotation if needed). Future fresh-orchestrator sessions read it at bootstrap.

4. **Telemetry-style retrospective.** After each ship, capture in the return report: actual orchestrator tokens consumed (estimable from the conversation log) vs the pre-task estimate. Builds a feedback loop on the heuristic's calibration.

5. **Edge cases worth enumerating:**
   - Mid-gate operator-driven scope changes (operator-gate I1 pattern) — defaults to inline regardless because dispatch overhead doesn't make sense for a 30-min mid-gate hotfix on an active worktree branch
   - Housekeeping commits (orchestrator-context updates, phase3e-todo SHIPPED markers, post-merge memory captures) — always inline
   - Brief-author-error mid-dispatch fixes — could be either path; operator's call

### Effort estimate

~1-2 hr orchestrator-thread work to draft the checklist + heuristic + memory→conventions promotion + brief-template addition. No code; pure process-doc work. Can be done by orchestrator inline in a quiet moment between dispatches OR queued as a thinking-session task.

**NOT a dispatch candidate** — this is orchestrator-doctrine work that lives in orchestrator-context + brief templates; an implementer doesn't have the cross-session orchestrator-perspective to do it well. (And this very item demonstrates the principle: process-doc work IS the kind of thing where orchestrator-inline beats implementer-dispatch on the cost-crossover.)

### Cross-references

- `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_orchestrator_vs_implementer_execution.md` — the auto-memory entry capturing the principle
- `docs/orchestrator-context.md` Conventions section — target home for the formalized policy
- `feedback_orchestrator_performs_merge.md` — pattern complement (both about scoping orchestrator actions to high-leverage edges)

---

## 2026-05-10 3e.8 disposition + commission bundles (derived from sell-side advisories investigation)

**Operator-orchestrator walkthrough 2026-05-10** of the 14 operator-decision items in [`docs/3e8-sell-side-advisories-investigation.md`](3e8-sell-side-advisories-investigation.md) §6 produced the dispositions below. Three commission bundles + three deferred-with-gate items + one in-flight operator-action (§4.G transcription) + two banked-without-gate items.

### Disposition matrix (14 items)

| # | §3e.8 item | Disposition | Workstream / trigger |
|---|---|---|---|
| 1 | §4.A trail-MA gating | §4.A.bis commissioned (advisory-only); §4.A deferred (V2.1 §VII.F-routed; gated on §4.G) | Bundle 3 below |
| 2 | §4.B trim/sell-into-strength | Commission V1 (single hint at +1R; default 25%) | Bundle 2 below |
| 3 | §4.C / §4.C.bis time-stop | Defer both; revisit at n≥10 closed sub-A+ trades OR §4.G-driven Minervini 7-week confirmation | Banked — see "Banked without gate" below |
| 4 | §4.D parabolic detector | Commission, bundled with §4.B + §4.K (sell-side bundle) | Bundle 2 below |
| 5 | §4.E briefing advisories | Commission, bundled with §4.F (parity bundle) | Bundle 1 below |
| 6 | §4.F detail+expanded advisory column | Commission, bundled with §4.E | Bundle 1 below |
| 7 | §4.G Minervini SEPA + DST sell-side transcription | Commission as immediate priority — operator-action; PRECEDES Bundles 1-3 | In-flight — scaffolding files at `reference/methodology/minervini-sell-side-rules.md` + `reference/methodology/dst-take-profit-and-trail.md` |
| 8 | §4.H sector RS check | Defer with second-source gate | Deferred-with-gate below |
| 9 | §4.I volume-confirmed exit | Defer with §4.G-completion-gate-trichotomy | Deferred-with-gate below |
| 10 | §4.J combined-violation | Defer with second-source gate | Deferred-with-gate below |
| 11 | §4.K planned_target_R hit | Commission, bundled with §4.B + §4.D | Bundle 2 below |
| 12 | DHC §6.2 decision | Case A confirmed 2026-05-10 (snapshot 2026-05-08T11:24:23: open_R=0.85, MFE=0.88R, maturity_stage=pre_+1.5R) — keep 20MA trail; ignore 10MA suggestion | Resolved |
| 13 | §6.3 sequencing | Approved as 4-step: §4.G transcription → Bundle 1 → Bundle 2 → Bundle 3 | Resolved |
| 14 | §6.4 [UNVERIFIED] flags (13 items) | Triage folded into §4.G transcription work | In-flight — see scaffolding files |

### §4.G transcription — **COMPLETE 2026-05-10 within available sources**

**DST file** (`reference/methodology/dst-take-profit-and-trail.md`): `~ PARTIAL` — 3/5 CONFIRMED-with-correction; 2/5 NOT-PRESENT-IN-SOURCE; 2 NEW rules surfaced (D.6 intraday-EMA parabolic + D.7 ADR-extension trim). Orchestrator pre-filled via PyMuPDF extraction of the DST PDF.

**Minervini file** (`reference/methodology/minervini-sell-side-rules.md`): `~ PARTIAL` — 1/7 CONFIRMED-QUANTITATIVE (M.2 sell-into-strength with R-multiple-of-stop-loss anchor); 4/7 BRIEF-MENTION-NO-DETAIL; 2/7 NOT-PRESENT-IN-AVAILABLE-SOURCES (M.1, M.4). Operator reviewed TLSMW (2013) on 2026-05-10. Think & Trade Like a Champion (2017) is NOT available — M.4 7-week rule remains unverifiable.

**Triggered post-completion (resolutions):**

- **§4.I gate-trichotomy → OUTCOME 2 (escalate to second-source gate).** M.6 is qualitative-without-threshold in TLSMW. §4.I now in same bucket as §4.H + §4.J (deferred-with-second-source-gate).
- **§4.A full + §4.C/§4.C.bis deferrals REINFORCED.** No quantitative anchor for either in available sources. §4.C/§4.C.bis: doctrine landscape on time-stops favors the AGGRESSIVE end (Q.1 3-5 day) — opposite of original 3e.8 framing.
- **Bundle 2 §4.B trim defaults need re-anchoring.** Doctrine = DST D.2 (50% on Day 3-5 calendar window) OR Minervini M.2 (R-multiple stop-tighten, NOT trim). The 3e.8 default (+1R first-time / 25% trim) is operator-policy hybrid. Implementation brief should support EITHER trigger pattern OR keep operator-policy hybrid with explicit annotation.
- **Bundle 2 §4.D parabolic defaults need re-anchoring.** Doctrine = DST D.7 (>7x ADR above 50SMA per Realsimpleariel). The 3e.8 defaults (25%/5d/15%) are arbitrary. Implementation brief should re-anchor.
- **Bundle 3 reframed to Option δ (hybrid α + β-LITE).** Operator-locked 2026-05-10. TWO complementary advisories: (a) §4.A.bis maturity-stage MA hint (operator-policy per Tier-3 #6); (b) M.2 R-multiple stop-tighten hint (doctrine per TLSMW Ch 13 p. 296). Different triggers (MFE-anchored stage vs live R-multiple); complementary signals. ~4-5 hr bundled.
- **13 [UNVERIFIED] flags in `docs/3e8-sell-side-advisories-investigation.md` §6.4 — dispositions captured in methodology files.** Future doc-update pass can refresh §6.4 inline if/when operator wants the investigation doc to reflect the post-transcription state.

### Deferred §4.H — Sector RS check (second-source gate)

**Trigger to revisit:** A doctrine-confluent sector-lag exit rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only) is structural weakness; no Minervini or DST analog in surveyed sources. Cost-benefit (10-14 hr + V2.1 §VII.F) doesn't change with trade-volume scale. Drop-equivalent for now; gate preserves optionality.

**Cross-refs:** §3e.8 §4.H + §3.H.

### Deferred §4.I — Volume-confirmed exit overlay (§4.G-completion-gate-trichotomy)

**Trigger to revisit:** §4.G transcription completes. Then THREE possible dispositions per M.6 outcome:
- M.6 carries **specific** volume threshold in source → commission §4.I with confirmed defaults (~2-3 hr; advisory-message-only)
- M.6 is **qualitative** without numerical threshold → escalate to second-source gate (mirror §4.H pattern)
- M.6 **doesn't exist** in source → drop §4.I

**Rationale:** Threshold-tuning friction without doctrine anchor; premature optimization. Gate ties revisit to concrete trichotomy.

**Cross-refs:** §3e.8 §4.I + §3.I.

### Deferred §4.J — Combined-violation rule (second-source gate)

**Trigger to revisit:** A doctrine-confluent combined-violation rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only); cosmetic refinement (operator already sees both messages). Same gate-pattern as §4.H for matrix consistency.

**Cross-refs:** §3e.8 §4.J + §3.J.

### Banked without gate — §4.A full + §4.C / §4.C.bis

**§4.A full** (classification-altering trail-MA gating with suppression): Banked. Trigger to revisit = sufficient evidence accumulation from Bundle 3's §4.A.bis hint adoption (n≥10 closed trades where operator's actual stop adjustments consistently follow the maturity-stage-recommended MA). At that point, the §4.A.bis behavioral evidence IS the shadow-mode-equivalent that V2.1 §VII.F would otherwise require.

**§4.C / §4.C.bis** (time-stop discipline change): Banked. Triggers to revisit = either (a) n≥10 closed sub-A+ hypothesis trades giving statistical signal on whether 10/0.5R is too aggressive, OR (b) operator surfaces a specific trade time-stopped prematurely with hypothesis still under evaluation, OR (c) §4.G Minervini transcription confirms 7-week rule context that justifies an informed default change.

### Cross-references for this disposition

- `docs/3e8-sell-side-advisories-investigation.md` — full investigation analysis (746 lines)
- `reference/methodology/minervini-sell-side-rules.md` — §4.G scaffolding (Minervini)
- `reference/methodology/dst-take-profit-and-trail.md` — §4.G scaffolding (DST)
- Earlier 3e.8 entry above (line 311) — investigation entry summary

---

## 2026-05-11 V2 watch items banked from 3e.8 Bundle 1 ship

### V2 — Extract shared advisory composer (drift-risk reduction)

**Banked from:** Bundle 1 Codex R1 Minor #1 (orchestrator triage 2026-05-11).

**Symptom:** Advisory composition is now hand-duplicated across 5 paths post-Bundle-1 ship: `build_dashboard`, `build_open_positions_row`, `build_trade_detail_vm`, `build_open_positions_expanded`, briefing helper (`compose_open_trade_advisories_for_briefing`). Future drift risk if `AdvisoryContext` inputs change — every change to advisory composition needs to be propagated to all 5 sites independently.

**Brief-locked deferral:** Bundle 1 brief §0.3 #2 explicitly locks "mirror dashboard composition" for V1 to avoid scope-creep. The hand-duplication is a known trade-off accepted at brief time.

**Proposed V2:** Extract a shared "compose advisory VMs for trade" web-side helper + a separate data_asof-pinned pipeline-side helper. Both consume a common `AdvisoryContext` constructor; both produce the same `tuple[AdvisorySuggestionVM, ...]` shape. Single source of truth for advisory composition logic.

**Effort estimate:** ~3-4 hr (refactor + update 5 call sites + verify all existing tests still pass).

**Trigger:** When `AdvisoryContext` inputs change OR a third advisory-rendering surface gets added OR a Codex round on a future bundle flags drift.

### V2 — `build_open_positions_expanded` cache I/O during SQLite read-snapshot

**Banked from:** Bundle 1 Codex R1 Minor #2 (orchestrator triage 2026-05-11).

**Symptom:** `build_open_positions_expanded` performs cache I/O (PriceCache.get_many) while the route holds a SQLite read-snapshot transaction. Lock window is bounded by `cfg.web.price_fetch_deadline_seconds` (typically 5-8s) but the pattern diverges from `build_dashboard`'s open-own-conn-DB-phase-then-cache-phase canonical pattern.

**Operational impact:** Under sustained load (many concurrent expand requests), the SQLite read-snapshot lock window blocks other read transactions for the cache-I/O duration. At single-operator scale this is invisible; it surfaces if/when the project ever supports concurrent operator sessions or background read-heavy workloads.

**Proposed V2:** Refactor `build_open_positions_expanded` to mirror `build_dashboard`'s pattern — open own connection, complete DB phase, close connection, then enter cache phase. Symmetric with the canonical pattern.

**Effort estimate:** ~2-3 hr (refactor + verify expand-route tests still pass).

**Trigger:** When concurrent-session support becomes a project goal OR when operator surfaces lock-related latency on the expand route.

### Cross-references

- Bundle 1 SHIPPED entry above (line ~417 post-housekeeping)
- `docs/3e8-bundle-1-advisory-parity-brief.md` §0.3 #2 (mirror-dashboard-composition lock)
- `swing/web/view_models/dashboard.py:build_dashboard` — canonical open-own-conn pattern reference

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 2 ship

### V2 — Brief composition-surface enumeration: grep, don't memory-enumerate

**Banked from:** Bundle 2 Codex R1 Major #1 (orchestrator triage 2026-05-11).

**Symptom:** Bundle 2 dispatch brief §0.2 enumerated 5 advisory-composition surfaces (4 web VMs + 1 pipeline briefing composer). The actual surface count is **6** — `swing/cli.py:trade_advisory_cmd` was the 6th, missed by orchestrator recon. Without Codex's discovery in R1 Major #1, the CLI `swing trade advisory` command would have emitted `trim_into_strength` advisories on already-trimmed trades because `has_been_trimmed` defaulted to `False` at the CLI composition site (no fill-loading wired through). Fixed in same Codex round with new `--adr-pct` flag + fill loading + 3 CLI tests.

**Generalized lesson:** When writing a dispatch brief that lists N composition / hand-mirroring sites for a new feature, the orchestrator MUST grep the codebase for ALL invocations of the canonical composition target — never enumerate from memory. Bundle 1 also listed 5 surfaces (same memory enumeration); Bundle 2 inherited the count without re-grepping. The CLI command lives outside the obvious web + pipeline namespaces and gets missed.

**Pre-empt in future dispatches:** writing-plans phase grep target = the function name or class name of the composition target (e.g., `compose_open_trade_advisories`, `AdvisorySuggestion`, `build_open_positions_row`). Cross-reference grep output against the brief's surface list before approving for dispatch.

**Effort estimate:** N/A — process change, not a code change. Lesson encoded in this entry + applied to all future bundle briefs.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory composition has 6 sites (web ×4 + pipeline ×1 + CLI ×1) — grep for invocations, don't memory-enumerate" as a gotcha if a third bundle adds new rules. For now, lesson lives here.

### Inherited from Bundle 1 (unchanged)

The two V2 watch items banked at the 2026-05-11 Bundle 1 section above carry forward unchanged — Bundle 2 incremented the hand-duplication surface count from 5 → 6 (CLI added) but did NOT extract a shared composer. Same accept-with-rationale on the drift risk. Same trigger for V2 composer extract.

### Cross-references

- Bundle 2 SHIPPED entry above (line ~1108)
- `docs/3e8-bundle-2-sell-side-advisories-brief.md` §0.2 (5-site enumeration that missed CLI; §0.3 #4 V2 hand-duplication acceptance)
- `swing/cli.py:trade_advisory_cmd` — the 6th composition site

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 3 ship

### V2 — Price-independent vs price-dependent advisory degradation pathways differ

**Banked from:** Bundle 3 Codex R1 Major #2 (`compute_price_independent_suggestions` helper introduction; orchestrator triage 2026-05-11).

**Symptom:** Before R1 fix, when PriceCache was degraded (live price unavailable), ALL advisory rules silently no-opped because the entire advisory composition was gated on having a valid `current_price`. But §4.A.bis (maturity_stage_trail_ma_hint) reads `maturity_stage` from DB and does NOT consume `ctx.current_price` — so it should still fire even when PriceCache fails. The original composition path conflated "price unavailable" with "skip ALL advisories", which masked DB-sourced advisories like §4.A.bis.

**Architectural fix (Bundle 3 R1 M#2):** `compute_price_independent_suggestions` helper splits the rule set into two tiers:
- **Price-independent rules** (e.g., §4.A.bis): fire when `AdvisoryContext` has the relevant DB-sourced fields populated; do NOT require valid `current_price`.
- **Price-dependent rules** (existing breakeven, trail_*, exit_below_*, weather, time_stop, Bundle 2's trim_into_strength + planned_target_r_hit + parabolic_trim): require valid `current_price`; no-op when PriceCache is degraded.

**Generalized lesson:** When adding new advisory rules in future bundles, classify the rule by data dependencies:
- If the rule's predicate consumes ONLY DB-sourced fields (from `AdvisoryContext` or `trade` model), it's price-independent — must remain visible under PriceCache degradation.
- If the rule's predicate consumes `ctx.current_price` (directly or via `r_so_far`), it's price-dependent — correctly no-ops under degradation.

The current 11-rule advisory surface is:
- Price-independent: §4.A.bis maturity_stage_trail_ma_hint (1 rule).
- Price-dependent: breakeven, trail_10ma, trail_20ma, exit_below_10ma, exit_below_20ma, exit_below_50ma, weather, time_stop, trim_into_strength, planned_target_r_hit, parabolic_trim, r_multiple_stop_tighten (12 rules including Bundle 3's M.2 trigger via `r_so_far`).

**Pre-empt in future dispatches:** writing-plans phase classifies each new rule + verifies it lands in the appropriate composition tier. Discriminating test: simulate PriceCache degradation; assert price-independent rules still fire while price-dependent rules no-op.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory degradation must differentiate price-independent vs price-dependent rules — the `compute_price_independent_suggestions` split is the canonical pattern" as a gotcha if a third bundle adds a price-independent rule. For now, lesson lives here.

### V2 — Orchestrator brief composition-surface enumeration must use `def build_*` grep, not caller-site grep

**Banked from:** Bundle 3 brief §0.2 file-attribution error (orchestrator triage 2026-05-11).

**Symptom:** Bundle 3 brief §0.2 listed `build_open_positions_expanded` as living in `swing/web/view_models/dashboard.py`. Actual location: `swing/web/view_models/open_positions_row.py`. The implementer addressed the function at its actual location without surfacing the discrepancy. Brief inaccuracy did not block dispatch but creates rot-risk for future bundles that grep the brief looking for canonical surface enumerations.

**Root cause:** orchestrator's grep in §0.2 of Bundle 3 was scoped too broadly (matched any file referencing the function NAME) rather than the file containing the function DEFINITION. The brief recorded a CALLER location, not a DEFINITION location.

**Generalized lesson:** When orchestrator briefs enumerate function locations, the grep MUST scope to definitions:
```
grep -rn "^def build_" swing/web/view_models/
# Or, more targeted:
grep -rn "def build_open_positions_expanded" swing/
```
NOT:
```
grep -rn "build_open_positions_expanded" swing/  # matches both definitions AND callers
```

**Pre-empt in future dispatches:** writing-plans phase enumeration step uses `^def` anchored patterns for function locations; verify each location is a definition (the line starts with `def` or `class`, not a call).

### Cross-references

- Bundle 3 SHIPPED entry above (line ~1152)
- `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md` §0.2 (file-attribution error documented; addressed at actual location by implementer)
- `docs/3e8-bundle-3-return-report.md` §7 (process deviation: inline TDD per task family; not surfaced to orchestrator mid-flight)
- `swing/trades/advisory.py:compute_price_independent_suggestions` — canonical pattern for advisory-degradation split
- `swing/web/view_models/open_positions_row.py:build_open_positions_expanded` — corrected location (NOT dashboard.py as brief §0.2 stated)

---

## 2026-05-13 Phase 10 closer — Phase 11 hand-off

Sub-bundle E SHIPPED (T-E.0..T-E.4 + T-E.5 + T-E.6 electives). Phase 10 CLOSED.

### Capture-needs surfaced during Phase 10 implementation (V2.1 §VII.F amendments pending)

Cumulative pending V2.1 §VII.F amendments at Phase 10 close (27+):

- (A T-A.7 + R2/R3) plan §A.7 binding-interface amendments (3): Wilson CI standard-vs-continuity-correction; `read_at_trade_time_policy` policy_id_stamp shape; `BaseLayoutVM.stale_banner` `str | None` vs `bool` (matches existing pattern).
- (B) plan-text deviations (5): T-B.1 `mistake_cost_R` cadence-grain rejection; T-B.2 `ALL_COHORTS_KEY='__all__'`; T-B.4 `cumulative_R_pct_of_capital` PERCENT units; T-B.7 display-block placement; T-B.2 7 cohort tabs (4 pre-registered + 2 orphan-label + "All").
- (C) plan-text deviations (5): T-C.1 cohort_relative_to_aplus rendering; T-C.1 doctrine_deviation_class baseline enum; T-C.5 filter SQL predicate; T-C.5 threading; T-C.5 toggle href shape.
- (D) plan-text deviations (5): D1 PROVISIONAL/LIVE math; D2 `candidate_criteria` vs `criterion_results.criterion_name`; D3 capital-friction trend window size; D4 `MaturityStageRow` per-row badge fields; D5 `aplus_take_rate_per_run` un-clamped.
- (E NEW) plan-text deviations (4):
  1. T-E.3 `ConfigPageVM` (not `ConfigVM` per brief §0.11).
  2. T-E.3 retrofitted 10 base-layout VMs (6 plan-named + 4 additional whose templates extend base.html.j2: ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM). Defense-in-depth per CLAUDE.md "base.html.j2 is shared" gotcha.
  3. T-E.5 service function is `record_snapshot` (NOT `record_snapshot_with_audit` per brief §0.5); Phase 9 Sub-bundle C ship-time naming preserved.
  4. T-E.1 N=10 + global_confidence_floor_n=20 + spec §5.4 "drops at n>=20": with the §A.4 N=10 LOCK the confidence-floor warning NEVER drops via the production callsite by construction. Implementation matches the locked behavior; spec wording could be amended to make the conditional dependence explicit. Discriminating test exercises window_size=20 to verify the band semantics are reachable.

- (D R2 M#1 banked at D) Phase 9 §7 sector_industry anchor + Phase 9 §6.2 multi-line parser amendments still pending.

**Total V2.1 §VII.F amendments pending: 27** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 = 24 Phase 10 + Phase 9 amendments banked).

### Operator-decision items pending Phase 11

1. **§8.4 Corporate_Actions MVP** — DEFERRED at Phase 10 electives triage (electives amendment §5). Banked at this section's existing 2026-05-13 entry. Phase 11 candidate.

2. **Schwab API Phase A** — operational metrics in Sub-bundle D (capital-friction + maturity-stage PROVISIONAL/LIVE) consume the Phase 9 Sub-bundle C `account_equity_snapshots` table. Schwab API integration (future phase) would write `source='schwab_api'` snapshots that outrank `source='manual'` per the spec §A.9 source ladder. Pre-Phase-11 triage decision: operator-paced.

3. **`mistake_cost_R_rolling_N_total` sum-class with bootstrap CI** — §A.21 spec-conformance deviation banked at writing-plans + carried through E T-E.1. Sub-bundle E ships "point" class (bare float); V2 may add sum-class with bootstrap CI on the window sum.

4. **Schwab inception-CSV ingestion** + **`account_equity_snapshots.equity_dollars` cash-basis vs MTM semantic formalization** (both banked at 2026-05-12 Phase 9 Sub-bundle C entry). Phase 11 candidates.

### Post-Phase-10 standalone dispatches (UNBLOCKED by Phase 10 close)

Per dispatch brief §1 + §7 watch items:

1. **Cleanup-script `-DeregisterFirst` extension** — Phase 9 husks (B/C/D/E) + Phase 10 Sub-bundle C/D/E orphan husks remain still-registered. Standalone dispatch will extend cleanup-script with a `-DeregisterFirst` switch + clear all pending husks.
2. **Test-runtime xdist + fixture-scope analysis** — fast suite at ~6:45 wall-clock at 3300+ tests; recommendation: profile → pytest-xdist → fixture-scope refactor for ~3-5x wall-clock reduction at zero coverage cost.
3. **§8.4 Corporate_Actions MVP** — schema-introducing standalone dispatch (new `corporate_actions` table + `0018_*.sql` migration + CLI surface + manual reconcile flow). Preserves Phase 10 §A.0 ZERO-new-schema lock; Phase 9 Sub-bundle A precedent (schema-introducing bundles get their own scoped review).

### V2 candidates banked at Phase 10 ship

1. **Orphan-emit discrepancy attribution surface** — Phase 9 Sub-bundle B per-run dedup allows orphan emits (discrepancies not attributed to a specific trade_id). Global discrepancy badge (T-E.3) counts these; per-trade indicator (T-E.6) does NOT. V2: "orphan discrepancy detail page" surfacing trade-less discrepancies.
2. **`render_class_d` "point" branch mean-semantics switch** (banked from Sub-bundle A return report §7). V2 may add sum-class semantics with bootstrap CI.
3. **Per-cohort "exclude trades stamped during paused intervals" filter** (banked from Sub-bundle B + electives amendment §7). Same UI shape as T-C.5; same VM pattern. Phase 11 candidate.

### Cross-references

- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (HEAD `a34c00d`).
- Phase 10 electives amendment: `docs/phase10-electives-amendment.md`.
- Phase 10 spec: `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
