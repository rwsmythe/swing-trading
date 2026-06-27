# Phase 14 Sub-bundle 4 -- Review + Journal UX -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 4 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed implementation plan to ship the **review + journal UX** to production code + tests: **CR.1** review-surface enrichment (exit-data fields + a render-direct closed-trade chart) + **P14.N6** the browse-the-database journal redesign (rich per-trade listing + sort/filter + journal-only candlestick thumbnails + clickable per-trade drill-down with a unified chronology + annotated chart) + the in-scope **BULZ row-expand rewire** (the dashboard open-positions row-expand from the legacy static `/charts/{date}/{ticker}.png` to the SB3 `position_detail` SVG). This is a **read-mostly UX + wiring sub-bundle: NO new trade-mutation path, NO schema change** (the render-direct decision keeps SB4 schema-free; v23 held). Plan is dispatch-ready per the writing-plans return report §15.

**Brief:** `docs/phase14-sub-bundle-4-review-journal-ux-executing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; SB1 SHIPPED at `e323339`; SB2 SHIPPED end-to-end at `27f8007` (v22 live); SB3 SHIPPED end-to-end at `edd098d` (v23 LIVE in the operator's real DB); **SB4 brainstorm SHIPPED at `2cf30f9`** (spec 1277 lines; genuine v2.0.2 WSL Codex CONVERGED Re-R4); **writing-plans SHIPPED at `573bcb3`** (plan 2089 lines; genuine v2.0.2 WSL Codex CONVERGED WP-R6, 0C/17M all resolved-in-place); housekeeping at `52b1156`. **Main HEAD at executing-plans dispatch: `52b1156`.**

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (compressed to trigger+fix; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~660+ cumulative ZERO Co-Authored-By trailer drift**; **Schema v23 LOCKED -- SB4 introduces NO migration** (do NOT add a `0024`; do NOT touch the v22 temporal-log or v23 chart-rename substrate); L2 LOCK preserved (source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

**Expected duration:** ~5-8 hours executing-plans implementation + 1 Codex chain. Plan §G enumerates 6 slices (~25 tasks); **~25-34 commits + ~70-105 fast tests** projected (trust `pytest -m "not slow" -q` over the estimate per gotcha #1; **capture the exact baseline at branch creation**). Operator-paced; SHIPS production code + tests under `swing/` + `tests/` with **ZERO new migration**.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief.
- `copowers:executing-plans` wraps `superpowers:subagent-driven-development` with adversarial Codex review after all tasks complete.
- **Codex chain count: ONE chain** per the operator-LOCKed OQ-8 disposition (§1.3) + Sec 9.1 Q7 + the brainstorm/writing-plans precedent (single chain, converged). **Run to CONVERGENCE** (zero new criticals AND zero new majors) -- the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); may exceed 5 rounds; do NOT stop while majors surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.2 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt the MCP tools or the launcher/settings angle.** The `adversarial-critic` skill auto-routes to a WSL Codex fallback that reads the worktree from disk (no inline-size limit), appends per-round findings to `.copowers-findings.md`, read-only. **Preferred: invoke `copowers:executing-plans` normally and let it drive the WSL fallback.** If driving directly: R1 `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-4-review-journal-ux-executing-plans - < <promptfile>'`; R2+ `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -`. WSL is fully provisioned. See memory `feedback_copowers_codex_mcp_windows_launcher`.
- Output: production code + tests + return report at `docs/phase14-sub-bundle-4-review-journal-ux-executing-plans-return-report.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/plans/2026-05-30-phase14-sub-bundle-4-review-journal-ux-plan.md`** -- the LOCKed plan (2089 lines; AUTHORITATIVE for implementation; v2.0.2 WSL Codex CONVERGED WP-R6). Especially: §A Goals/non-goals; §B File map (+ the verified-anchor table); §C Surface integration; §E LOCK reverification (Sec 9.1 + L1-L8 + the §1.3 OQ dispositions); §F Discipline hooks; **§G 6 slices / ~25 tasks (+ §G.0 commit cadence; step-checkbox TDD)** (BINDING); §H Test surface (sum-check); **§I Operator-witnessed visual + HTMX gate runbook**; §J Codex placement; §K Schema (NO change); §L Fixtures; §M Forward-binding lessons; §N Self-review; §O Handoff.

3. **`.copowers-findings.md`** (repo root) -- the persistent v2.0.2 WSL Codex findings ("WRITING-PLANS review" section: 17 majors, all resolved-via-code, + the "BRAINSTORMING review" section: 8 majors). These are the binding production-truth corrections the implementation MUST honor (see §3).

4. **`docs/phase14-sub-bundle-4-review-journal-ux-writing-plans-dispatch-brief.md`** §1.3 (the 9 operator-LOCKed OQ dispositions) + §2.4 (the render lock) + §5 watch items -- carry forward.

5. **`docs/superpowers/specs/2026-05-30-phase14-sub-bundle-4-review-journal-ux-design.md`** -- brainstorm spec (reference for architectural rationale; §1.2 the render-direct window-anchoring finding; §4 CR.1; §5 P14.N6 + §5.4 chronology; §6 BULZ row-expand; §8 HTMX disciplines).

6. **`CLAUDE.md`** -- the compressed gotchas. Most relevant: **HTMX browser-only failure-surface trinity** (4xx-swap config; `hx-headers '{"HX-Request":"true"}'`; `204`+`HX-Redirect` not `303`; HTMX response leading with `<tr>` triggers synthetic-table-wrap -> table-row-free fragment root + OOB tbody swap; HX-Redirect target registered) + **shared `base.html.j2` -- a new `vm.foo` field needs a safe default on EVERY base VM** (`DashboardVM`/`PipelineVM`/`JournalVM`/`WatchlistVM`/`PageErrorVM`); **matplotlib mathtext** (ASCII annotation text; manual visual verification non-optional); **Cache + executor race** (workers must not write shared state on deadline miss) + **External-API empty-result transient F6** + **Shared cache returns FULL archive; consumers slice** + **OHLCV fetch scope**; **Weather lookup must NOT query by action_session** (if touched); **Windows cp1252** (ASCII discipline; renderers/CLI return bytes). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature verify; re-grep at STEP 0), **#4** (SQL column verify -- the chronology/entry-flag columns), **#13** (cascade audit each task).

7. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_copowers_codex_mcp_windows_launcher` (MCP dead in VS Code ext; WSL fallback is the path; v2.0.2)
   - `feedback_codex_round_limit_suspended` (run to convergence; no 5-round cap)
   - `feedback_verify_regression_test_arithmetic` (compute exit-VWAP / total_risk / final_R under BOTH single- and multi-leg)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`)
   - `feedback_worktree_cli_invocation` (`python -m swing.cli`, NOT bare `swing`)
   - `feedback_visual_gate_both_render_and_browser` (the SB3 gate pattern: operator-driven browser + orchestrator DB-side probes; re-confirm the SB4 split)

8. **Production code surfaces** cited in plan §B. **RE-VERIFY at executing-plans STEP 0** to catch drift since the writing-plans merge (the plan re-grepped on its worktree; main is now `52b1156`). The orchestrator re-verified the core anchors at SB4 QA (§3 "Verified anchors"); re-confirm per #2/#4.

---

## §1 LOCKs inherited (BINDING through executing-plans; DO NOT re-litigate)

All LOCKs preserved verbatim through 1 brainstorm + 1 writing-plans Codex chain per plan §E.

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = data-wiring -> temporal log -> charts -> **review + journal UX (THIS)** -> metrics; **Q2** SERIAL
- **Q5** matplotlib SVG only -- reuse the SB3 mplfinance renderers; **NO JS charting library**
- **Q6** operator browser-witnessed verification at merge (the rendered surface is the BINDING visual gate -- HTMX + matplotlib)
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** (operator-LOCKed OQ-8, §1.3)

### §1.2 Brainstorm spec §2 + L1-L8 LOCKs
- **L1** scope = CR.1 + P14.N6 + the in-scope BULZ row-expand wiring ONLY
- **L2** **read-mostly; NO new trade-mutation path.** The review POST + `complete_trade_review` write contract is UNCHANGED; journal + drill-down + all charts perform ZERO trade/fill/review/`chart_renders` writes. **Scope clarification (Codex R1 M#1):** "read-mostly" governs the TRADE domain; the OHLCV archive read-through (`read_or_fetch_archive`) is the app's existing shared cache invoked on the SAME terms (read; refresh on existing cadence; degrade per F6) -- permitted/pre-existing, NOT a new mutation path. **Escalate if any task appears to need a trade/fill/review/chart_renders write** (none does).
- **L3** **NO schema change** (render-direct eliminates the only v24 trigger; OQ-2 LOCK). `EXPECTED_SCHEMA_VERSION` stays 23. **Add NO migration.** (Gotcha #11/#9 N/A this sub-bundle.)
- **L4** HTMX browser-only failure-surface trinity applies to journal sort/filter/drill-down/thumbnail (spec §8); operator-witnessed browser verification BINDING (TestClient cannot catch these)
- **L5** matplotlib visual-gate discipline; ASCII-only annotations; **REUSE the SB3 renderers** (no candlestick re-implementation)
- **L6** L2 Schwab LOCK preserved; ZERO new `schwabdev.Client.*` call sites; source-grep test stays green. The Schwab daily-bar wiring (banked #4) stays OUT.
- **L7** record the chart-access UX brief §2 reversal when the row-expand inlines the `position_detail` SVG (spec §6; Slice 1)
- **L8** market_weather 200MA fix banked standalone (OQ-7 LOCK), NOT in SB4

### §1.3 The 9 operator-LOCKed OQ dispositions (BINDING; operator-paired triage 2026-05-30)

| OQ | LOCKed disposition |
|---|---|
| **OQ-1 CR.1 chart window** | **Render-direct** closed-trade chart over `entry-30d .. exit+10d` (padding operator-tunable); NOT a reused trailing-today `position_detail` cache. |
| **OQ-2 chart surface / schema** | **NO new `chart_renders` surface enum; NO schema (v23 held).** Reuse the SB3 renderer render-direct. |
| **OQ-3 thumbnail breadth** | **Journal listing ONLY.** Bank the dashboard open-positions/hyp-rec thumbnail wiring (P14.N1) separately. |
| **OQ-4 hyp-rec "(and which)"** | **V1 derived fields, NO schema:** `has_hyprec_link` (`trade_origin=='pipeline_watch_hyp_recs'`, `swing/trades/origin.py:71`) + `hypothesis_label` + pattern_class + A+ bucket. No hyp-rec FK. |
| **OQ-5 chronology shape** | **Unified timestamp-merged chronology** (single stream); precedence **`fill < daily_management < trade_event < review`**; NOT per-source sections. |
| **OQ-6 total_risk semantics** | **Dollar risk at open** = `initial_shares * (entry_price - initial_stop)`. (No %-of-capital column in V1; capital floor NOT consumed.) |
| **OQ-7 market_weather 200MA** | **Bank standalone**; do NOT fold into SB4. |
| **OQ-8 Codex chain count** | **SINGLE chain** (run to convergence; cap suspended). |
| **OQ-9 sort/filter fragment** | **Whole-`<table>` `outerHTML` swap.** |

---

## §2 Scope inheritance from plan §G (BINDING substrate)

Plan §G is AUTHORITATIVE. Implement task-by-task in the locked order; **3-5 commits/task; cascade-audit (Expansion #13) after each task; verify `%(trailers)` is `[]` after each commit** (§G.0). 6 slices: **Slice 0 + Slice 1 are independent (Slice 0 must precede 4/5 -- it builds `trade_charts.py` + the render lock); Slice 2 -> 3 -> 4 -> 5 are serial.**

| Slice | Scope | ~Tasks |
|---|---|---|
| **Slice 0 -- CR.1 + shared helper + render lock** | Exit-data fields on `ReviewVM` (derive exit legs from fills; exit VWAP per reducing-fill classification, long-only positive-qty) + a render-direct closed-trade chart on the review surface (OQ-1; lazy-load route `GET /trades/{id}/review/chart` with failure-isolation). **Builds the shared `trade_charts.py` helper + the process-wide matplotlib render lock** (§2.1 below) that Slices 4/5 reuse. | ~6 |
| **Slice 1 -- BULZ row-expand rewire** | `open_positions_expanded.html.j2` from the legacy static PNG to the SB3 `position_detail` SVG via the SAME read-only `get_cached_chart_svg` path `build_trade_detail_vm` uses (NO JIT, NO write); cache-miss -> chart-unavailable state (NOT a blank render -- WP M#3); one-open-trade-per-ticker invariant + refresh test; record the §2-page reversal (L7). | ~3 |
| **Slice 2 -- journal listing substrate** | `JournalRowVM` (open_price/shares/dollar-total_risk[OQ-6]/closing_price/final_R/entry-flags[OQ-4 V1 fields]); `build_journal` enrichment; rich row table. | ~3 |
| **Slice 3 -- sort/filter** | Whole-`<table>` `outerHTML` swap (OQ-9); HTMX trinity (L4); `filter_state` "reviewed" = `state=='reviewed'`; focus/scroll/control persistence on swap. | ~2 |
| **Slice 4 -- thumbnails** | Candlestick thumbnails on journal listing rows ONLY (OQ-3); lazy-load on scroll via `hx-trigger="revealed"` + page size ~20-25 (**VERIFY window-scroll layout, NOT overflow-container, or `revealed` won't fire -> `hx-trigger="intersect"` with explicit root if overflow**). | ~3 |
| **Slice 5 -- drill-down + chronology** | `build_trade_drilldown_vm` + `TradeDrilldownVM`; NEW `swing/web/view_models/trade_chronology.py` (`build_trade_chronology` unified merge of fills + trade_events + per-trade review + daily_management_records; OQ-5 precedence + `_normalize_ts`); annotated full chart (render-direct, reuse `render_position_detail_svg`); full-page drill-down 404s on missing trade, HTMX fragments return 200+unavailable (two distinct contracts). | ~6 |

**Total: ~70-105 fast tests** projected (trust pytest per gotcha #1; **0 slow tests** -- charts render from fixture bars; assemblies from planted rows). **Do NOT widen task scope** beyond plan §G acceptance criteria + step-checkbox TDD.

### §2.1 The process-wide matplotlib render lock (HIGHEST-RISK item; plan §M lesson (a))
SB4 adds 2 NEW render-direct chart paths (CR.1 review chart + drill-down annotated chart) into the SB3-shared `charts.py`, which uses pyplot global state with NO existing lock. **Implement:** an `RLock` at the SHARED `charts.py` render boundary; **decorate ALL 5 public `render_*_svg` renderers + the 2 NEW helpers** so EVERY web render path serializes; **single outer acquisition per render** (RLock guards the self-deadlock if a path nests); a **no-deadlock test per chart path** (parametrized over all 5 public renderers + the 2 new) + an all-wrapped guard test. Pair with thumbnail load-on-scroll + smaller page size so the lock cannot queue ~50 renders into a DoS.

### §2.2 The unified chronology (substantive artifact; plan §M lesson (b))
NEW `swing/web/view_models/trade_chronology.py`. **Production-verified columns (WP corrections -- honor exactly):** `trade_events` payload is `payload_json` + `rationale`, NOT `notes`; `daily_management_records` `record_type` splits `daily_snapshot` vs `event_log` (detail columns at `0016*.sql:60-72,84-94`; stop fields in `stop_changed`/`prior_stop`/`new_stop`); MFE/MAE are R-multiples NOT %; **`review_log` is EXCLUDED** (it is the cadence table -- NO `trade_id`; per-trade review is on the `trades` columns). `_normalize_ts` handles malformed/missing timestamps; OQ-5 precedence `fill < daily_management < trade_event < review` is the tiebreak. Dedicated tests: per-source field-map, supersession-with-unique-markers, `_normalize_ts` malformed-last, `review_log`-never-leaks.

---

## §3 Production corrections + verified anchors + watch items (BINDING)

### The .copowers-findings.md production corrections (carry into implementation; honor exactly)
- `_render_candles_fig` is a **3-tuple with NO title kwarg** (`swing/web/charts.py:412-419`) -- the render-direct helper composes title separately (ASCII; mathtext discipline).
- There are **5 public `render_*_svg`**, not 2 -- the render lock decorates all 5 + the 2 new helpers.
- BULZ row-expand cache-miss could render BLANK because `chart_reason_message` is legacy-PNG scope -- the rewire MUST resolve cache-miss to an explicit chart-unavailable state.
- `build_review_vm` is **closed-only** (`swing/web/view_models/trades.py:1223`) -- CR.1 enrichment respects that (review is a closed-trade surface).
- `journal_page` `period` is a FastAPI `Literal[...]` that 422s before the in-page error fragment -> type it `str` + allowlist-check.
- `Fill` has `action`/`quantity` (NOT `side`/`qty`); `review_log` has NO `trade_id`; MFE/MAE are R-multiples (NOT %).

### Verified anchors (orchestrator re-grep at SB4 QA; re-confirm at STEP 0 per #2)
- **Review (EXISTS -- enrichment):** `review_form_page` (`swing/web/routes/trades.py:2590`), `review_post` (`:2610`), `ReviewVM` (`swing/web/view_models/trades.py:1106`), `build_review_vm` (`:1183`, closed-only `:1223`), `complete_trade_review` (`swing/trades/review.py:550`, contract UNCHANGED).
- **Journal (EXISTS -- redesign):** `journal_page` (`swing/web/routes/journal.py:15`), `JournalVM`/`build_journal` (`swing/web/view_models/journal.py:98`/`:136`).
- **BULZ row-expand:** `open_positions_expanded.html.j2:38-44` (legacy PNG); `GET /trades/open/{trade_id}/expand` (`swing/web/routes/trades.py:2555`); `build_open_positions_expanded` (`swing/web/view_models/open_positions_row.py`); `trades/detail.html.j2:65` (`position_chart_svg_bytes`); `build_trade_detail_vm` (`swing/web/view_models/trades.py:1722`); `render_position_detail_svg` (`swing/web/charts.py:628`).
- **Render path / load-bearing anchor:** `swing/web/chart_jit.py:117` `get_or_fetch(window_days=200)` + `swing/web/ohlcv_cache.py:131` (trailing-today, ticker-keyed) -- WHY closed-trade charts render-direct (OQ-1).
- **Entry flags:** `trade_origin == 'pipeline_watch_hyp_recs'` (`swing/trades/origin.py:71`); `hypothesis_label`; `chart_pattern_algo`/`operator`; `candidate_id`/`pattern_evaluation_id`; `initial_shares`/`initial_stop`/`entry_price`/`planned_target_R` (Trade).
- **Schema:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`); highest migration `0023_*`. **Add NO migration.**

### Cumulative gotchas (plan §F)
HTMX browser-only trinity (4xx-swap config; `hx-headers HX-Request`; `204`+`HX-Redirect`; table-row-free fragment root + OOB tbody swap; HX-Redirect target registered) + shared-`base.html.j2` VM-field defaults on ALL base VMs (factor a `_base_banner_fields` helper) / matplotlib mathtext (ASCII; manual visual verification non-optional) / Cache+executor race + render-lock / F6 empty-result transient + full-archive-slice + OHLCV-scope / `feedback_verify_regression_test_arithmetic` (exit-VWAP / total_risk / final_R single- AND multi-leg) / L2 source-grep / **#16/#32 ASCII** (em-dash etc.; renderers/CLI return bytes -> Windows cp1252).

**Streaks to preserve:** ~660+ ZERO `Co-Authored-By` (verify `%(trailers)` per commit; final `-m` paragraph plain prose); **NO new migration (v23 held; no v24; v22/v23 substrates UNTOUCHED)**; L2 LOCK (source-grep continues passing); ASCII discipline; gotcha #33 banned-terms across narrative.

---

## §4 Codex SINGLE-chain placement (OQ-8 LOCK; plan §J)

Run ONE chain at the end of executing-plans, after ALL code + tests land + green, BEFORE the operator-witnessed gate. **Run to CONVERGENCE** (`NO_NEW_CRITICAL_MAJOR`; cap suspended -- may exceed 5 rounds).

**Lens:** production-signature/column correctness (the WP corrections honored); read-mostly (ZERO new trade/fill/review/`chart_renders` writes; assert it); NO migration; the render lock (process-wide; single outer acquisition; no-deadlock per path; DoS guard); the chronology per-source contracts; HTMX trinity (sort/filter/drill-down/thumbnail; shared-base VM defaults); matplotlib ASCII + visual-gate declared binding; total_risk/exit-VWAP/final_R single- vs multi-leg; L2 source-grep continues passing; no placeholders; cascade-regression audit.

**Transport:** the WSL Codex fallback reads the worktree from disk (copowers v2.0.2; MCP dead). Aim for ZERO Major accepted-as-rationale (brainstorm + writing-plans both resolved all in-place). **If Codex finds a defect requiring a schema change OR a new write path:** STOP + escalate (do NOT add a migration; do NOT add a trade-domain write).

---

## §5 Operator-witnessed gate (plan §I; HTMX + matplotlib; BINDING)

After the chain converges + return report drafted, the orchestrator returns to the operator. **The BINDING gate is the RENDERED surface in a REAL browser** -- and SB4 is MORE browser-dependent than SB3: the matplotlib charts can be PNG-fallback-verified (render to PNG + Read), but the **HTMX behaviors (sort/filter `outerHTML` swap; drill-down navigation; lazy thumbnail `revealed` trigger; 404-vs-fragment-200) REQUIRE a real browser** -- TestClient cannot catch them (L4). **Re-confirm the gate split with the operator** (`feedback_visual_gate_both_render_and_browser`: operator-driven browser for the HTMX/visual behaviors + orchestrator DB-side probes for S1/S2).

| Step | Surface | What to verify |
|---|---|---|
| **S1** | pytest + ruff | full fast suite green (baseline + ~70-105 NEW) + `ruff check swing/` clean |
| **S2** | schema | **NO migration** (`schema_version=23`; assert ZERO new `chart_renders` rows from SB4 paths; ZERO trade/fill/review writes) |
| **S3** | CR.1 review | exit data surfaced + render-direct closed-trade chart over the correct TRADE window (entry-30d..exit+10d), lazy-loaded |
| **S4** | BULZ row-expand | dashboard open-positions row-expand shows the SB3 candlestick+zones SVG (NOT the legacy `<img>`); cache-miss -> chart-unavailable (not blank) |
| **S5** | journal listing | rich rows + entry-flags + dollar total_risk + lazy candlestick thumbnails (journal only) |
| **S6** | sort/filter | whole-`<table>` `outerHTML` swap; focus/scroll/control persistence |
| **S7** | drill-down | unified chronology (correct precedence/fields) + annotated chart; missing-trade full-page 404 vs HTMX fragment 200+unavailable |

**Gate-pass triggers** ("all surfaces pass" / "gate passed" / equivalent) -> orchestrator merges per `feedback_orchestrator_performs_merge` BINDING. **After merge: re-run the fast suite ON THE MERGED HEAD and READ the result before claiming green** (`feedback_no_false_green_claim`).

---

## §6 Done criteria

1. All 6 slices shipped (Slice 0-5)
2. Codex SINGLE chain CONVERGED at NO_NEW_CRITICAL_MAJOR (run to convergence; cap suspended); `.copowers-findings.md` evidences it ran genuinely via WSL
3. fast suite green on branch (baseline + ~70-105 NEW); `python -m pytest -m "not slow" -q`
4. `ruff check swing/` clean
5. ZERO Co-Authored-By trailer drift (verify `%(trailers)`); final `-m` paragraphs plain prose
6. **NO migration; `EXPECTED_SCHEMA_VERSION` stays 23; ZERO new `chart_renders` rows + ZERO trade/fill/review writes from SB4 paths** (escalate if a migration or write seems needed)
7. L2 LOCK preserved (source-grep test PASSES against `bf7e071`)
8. The render lock wraps all 5 public renderers + the 2 new helpers (no-deadlock test per path); the chronology per-source contracts tested
9. Return report at `docs/phase14-sub-bundle-4-review-journal-ux-executing-plans-return-report.md` complete per §7
10. Branch pushed to origin; ready for orchestrator QA + operator-witnessed gate

---

## §7 Return report shape

1. Final HEAD + commit count breakdown (per-commit Codex round attribution)
2. Codex round chain (single chain; summary table + convergent shape; EVIDENCE genuine via WSL -- cite `.copowers-findings.md`)
3. Per-slice completion summary (Slice 0-5)
4. Test surface verification (~70-105 fast projected; per-slice actual; total before + after)
5. Pre-locked decisions verbatim verification (Sec 9.1 + L1-L8 + the 9 OQ dispositions)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO preferred)
7. Production-code citations verified at task completion (#2/#4 re-grep; the WP corrections honored)
8. Schema impact verdict (**NO migration**; v23 held; the read-mostly assertion -- ZERO new chart_renders/trade/fill/review writes)
9. The render lock (all 5 + 2 wrapped; no-deadlock per path) + the chronology contracts verification
10. L2 LOCK verification (source-grep PASSES against `bf7e071`; cite test name + result)
11. **Operator-witnessed gate readiness (S1-S7; HTMX behaviors flagged as browser-only; PNG-fallback artifacts for the matplotlib charts)**
12. NEW forward-binding lessons banked (for SB5 + CLAUDE.md gotcha consideration)
13. ASCII discipline scope (gotcha #32; enumerate NEW + MODIFIED files)
14. Cumulative gotcha set application summary (per slice)
15. Worktree teardown status
16. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits + merge-candidate)
17. CLAUDE.md status-line refresh draft text
18. Operator-witnessed gate handback summary

---

## §8 OUT OF SCOPE (do not implement)

- Metrics overview (SB5; Sec 9.1 Q1 serial LOCK)
- The broader P14.N1 dashboard open-positions/hyp-rec thumbnail wiring (OQ-3 banked)
- The market_weather 200MA fetch-window fix (OQ-7 banked)
- The `_bulz_*` -> general helper rename (operator-banked 2026-05-30 "proceed as-is"; future cosmetic refactor)
- The Schwab daily-bar web wiring (banked #4; L6)
- Any new schema/migration (L3; no v24) OR new trade-mutation path (L2)
- A %-of-capital total_risk column (OQ-6 = dollar only)
- A hyp-rec FK (OQ-4 = V1 derived fields)
- Temporal-log (v22) or chart-rename (v23) substrate changes
- JS charting (matplotlib SVG only; Q5)
- Schwab API changes (L2 LOCK)
- Production code modifications NOT in plan §B file map
- Phase 15+

---

## §9 If you get stuck

- If production drifted since the writing-plans merge (`573bcb3`) and a plan-cited file:line no longer matches, ESCALATE (do NOT silently patch). Orchestrator re-verified core anchors at SB4 QA (§3); re-grep at STEP 0.
- If any task appears to need a NEW write path (trade/fill/review/`chart_renders`) OR a schema change, STOP + escalate -- L2/L3 forbid both (the render-direct decision is the schema-free guarantee).
- If the journal listing layout is an overflow-container (not window-scroll), the `revealed` thumbnail trigger won't fire -> use `hx-trigger="intersect"` with an explicit root (document the choice; do NOT silently ship a non-firing trigger).
- HOLD THE LINE if Codex pushes back on: render-direct closed-trade charts / cache-reuse only for open-trade row-expand (OQ-1); NO schema (OQ-2); journal-only thumbnails (OQ-3); single chain run-to-convergence (OQ-8); matplotlib/mplfinance no-JS (Q5); the OQ-5 chronology precedence; dollar total_risk (OQ-6).
- If a Codex finding needs a schema change or a write path, STOP + escalate.
- If the Codex MCP times out, do NOT attempt to fix it (dead in the VS Code extension); use the WSL Codex fallback (reads the worktree from disk; copowers v2.0.2 auto-routes).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT widen scope to SB5 / the banked P14.N1 dashboard breadth / the `_bulz_*` rename / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §10 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface for production code + tests).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-4-review-journal-ux-executing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-4-review-journal-ux-executing-plans/`. Branch from main HEAD `52b1156`.
- **Model:** defer to harness default.
- **CLI invocation in the worktree:** `python -m swing.cli` (NOT bare `swing` -- the editable install points at main, not the worktree).
- **Expected duration:** ~5-8 hours implementation + ~30-90 min for the single Codex chain (run to convergence). Operator-paced.
- **Codex chain count:** ONE chain (OQ-8 LOCK + plan §J), run to convergence via the WSL Codex fallback (copowers v2.0.2; MCP dead in the VS Code extension).
- **Production surface (plan §B):** `swing/web/view_models/trades.py` (ReviewVM enrichment + TradeDetailVM/drilldown) + `swing/web/view_models/journal.py` (JournalVM + JournalRowVM + build_journal) + NEW `swing/web/view_models/trade_chronology.py` + NEW `swing/web/charts.py`-adjacent `trade_charts.py` helper + the render lock in `swing/web/charts.py` + `swing/web/routes/trades.py` + `swing/web/routes/journal.py` + templates (`review.html.j2`, `partials/review_form.html.j2`, `journal.html.j2` + new partials, `partials/open_positions_expanded.html.j2`). **NO migration.** **Test surface:** `tests/web/` + `tests/web/view_models/` + `tests/integration/`.

---

*End of brief. Phase 14 Sub-bundle 4 executing-plans dispatch -- execute the LOCKed 2089-line plan (CR.1 review exit-data + render-direct chart; P14.N6 journal across 6 slices: listing + sort/filter + journal-only thumbnails + drill-down unified-chronology + annotated chart; BULZ row-expand rewire to the SB3 position_detail SVG; a shared trade_charts.py helper + a process-wide matplotlib render lock; ~25-34 commits + ~70-105 fast tests); ONE Codex chain run to convergence; the operator-witnessed S1-S7 gate per plan §I. NO schema change (v23 held); NO new trade-mutation path. The rendered surface in a real browser is the BINDING gate (HTMX + matplotlib). OUTPUT: production code + tests + return report; ready for orchestrator merge + operator-witnessed gate + post-merge housekeeping (re-run the suite on merged HEAD per feedback_no_false_green_claim).*
