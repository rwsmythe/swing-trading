# Phase 14 Sub-bundle 4 -- Review + Journal UX -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 4 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan derived from the Sub-bundle 4 brainstorm spec. Plan lives at `docs/superpowers/plans/2026-05-30-phase14-sub-bundle-4-review-journal-ux-plan.md` (or operator-paired date). The plan decomposes the spec into bite-sized TDD slices with per-task acceptance criteria, file-level diff projections, test scope, an **HTMX + matplotlib operator-witnessed visual-gate runbook**, and an executing-plans dispatch-readiness package.

**Brief:** `docs/phase14-sub-bundle-4-review-journal-ux-writing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; SB1 SHIPPED at `e323339`; SB2 SHIPPED end-to-end at `27f8007` (v22 live); SB3 SHIPPED end-to-end at `edd098d` (v23 live); **Sub-bundle 4 brainstorm SHIPPED at `2cf30f9`** (spec 1277 lines; GENUINE copowers v2.0.2 WSL Codex chain CONVERGED Re-R4 0C/8M); housekeeping at `5ddd936`. Main HEAD at writing-plans dispatch: `5ddd936`.

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (compressed in CLAUDE.md; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~655+ cumulative ZERO Co-Authored-By trailer drift; **Schema v23 LOCKED -- Sub-bundle 4 introduces NO schema change** (the brainstorm's load-bearing render-direct decision eliminates the only candidate v24 trigger; §1.3 OQ-2 LOCK); L2 LOCK preserved.

**Expected duration:** ~2-4 hours writing-plans + 1 Codex chain. Plan line target **~1800-3000 lines** (CR.1 review enrichment + the LARGEST single Phase 14 item P14.N6 across 6 slices: journal listing + sort/filter + thumbnails + drill-down chronology + annotated chart + the BULZ row-expand rewire + a shared `trade_charts.py` helper + a process-wide matplotlib render lock).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief.
- **Codex chain count: SINGLE chain** per the operator-LOCKed OQ-8 disposition (§1.3) + Sec 9.1 Q7 + gotcha #36 caveat (pure UX/wiring; the §5.4 chronology is a read-only timestamp merge, not analysis). **Run to CONVERGENCE** (zero new criticals AND zero new majors) -- the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); the chain may exceed 5 rounds; do NOT stop while majors still surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.2 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension (hardcoded ~1s `MCP_CONNECTION_NONBLOCKING` deadline). **Do NOT attempt the MCP tools or the launcher/settings angle (exhausted).** The `adversarial-critic` skill auto-routes to a WSL Codex fallback that reads the worktree from disk (no inline-size limit), appends per-round findings to `.copowers-findings.md`, and stays read-only. **Preferred: invoke `copowers:writing-plans` normally and let it drive the WSL fallback.** If driving Codex directly: R1 `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-4-review-journal-ux-writing-plans - < <promptfile>'`; R2+ `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -`. WSL is fully provisioned (Node 22, codex-cli 0.135.0) -- no setup. See memory `feedback_copowers_codex_mcp_windows_launcher`.
- Output: plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-4-review-journal-ux-plan.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/specs/2026-05-30-phase14-sub-bundle-4-review-journal-ux-design.md`** -- the brainstorm spec (1277 lines; AUTHORITATIVE; copowers v2.0.2 WSL Codex CONVERGED Re-R4). Especially §1 architecture (the central render-direct window-anchoring finding), §2 pre-locked decisions + the OD-1..OD-6 items, §3 module touch list, §4 CR.1, §5 P14.N6 (incl. §5.4 chronology), §6 BULZ row-expand, §7 reuse-vs-enum decision, §8 HTMX disciplines, §9 6-slice decomposition, §10 fixtures + visual-gate ladder, §11 schema impact (NO change), §12 V1/V2, §13 OQ table, §14 discipline compliance, §15 Codex round log.

3. **`.copowers-findings.md`** (repo root) -- the persistent v2.0.2 WSL Codex findings record (8 majors, all resolved-via-code). The 8 catches are exact-column/production-signature corrections the prior blind chain couldn't make -- read them; they are the binding production-truth corrections the plan MUST honor.

4. **`docs/phase14-sub-bundle-4-review-journal-ux-brainstorming-dispatch-brief.md`** §1 LOCKs (L1-L8) + §5 watch items.

5. **`docs/phase14-commissioning-brief.md`** Sec 2.3 + Sec 9.1 LOCKs (Q1/Q2/Q5/Q6/Q7).

6. **`CLAUDE.md`** -- the compressed gotchas. Most relevant: **HTMX browser-only failure-surface trinity** (4xx-swap config; `hx-headers HX-Request`; `204`+`HX-Redirect` not `303`; table-row-free fragment root + OOB tbody swap; HX-Redirect target registered) + **shared `base.html.j2` VM-field defaults on ALL base VMs**; **matplotlib mathtext** (ASCII annotation text; manual visual verification non-optional); **Cache + executor race** + **External-API empty-result transient (F6)** + **Shared cache returns FULL archive; consumers slice** + **OHLCV fetch scope** (chart bar sourcing); **Weather lookup must NOT query by action_session** (if any weather surface is touched). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature verify; re-grep at plan time), **#4** (SQL column verify -- the journal entry-flags + chronology field-maps depend on REAL columns), **Expansion #10c** (renderer-kwargs uniformity if a chart reuses a surface).

7. **Production code surfaces** (re-grep at plan-authoring per #2; ORCHESTRATOR-VERIFIED at `5ddd936` during SB4 QA -- the anchors below held):
   - **Review (CR.1; EXISTS -- enrichment not greenfield):** `review_form_page` (`swing/web/routes/trades.py:2590`), `review_post` (`:2610`), `ReviewVM` (`swing/web/view_models/trades.py:1106`), `build_review_vm` (`:1183`); `complete_trade_review` (`swing/trades/review.py:550`, write contract UNCHANGED -- L2); templates `swing/web/templates/review.html.j2` + `partials/review_form.html.j2`. Exit data is a FILLS derivation (no `exit_price`/`exit_date` column on `trades`).
   - **Journal (P14.N6):** `journal_page` (`swing/web/routes/journal.py:15`; `period` is currently a FastAPI `Literal[...]` -> Codex major: 422s before the in-page error fragment can render -> the plan types it `str` + allowlist-checks); `JournalVM` + `build_journal` (`swing/web/view_models/journal.py:98` / `:136`); template `swing/web/templates/journal.html.j2`.
   - **Chronology sources (NEW assembly `swing/web/view_models/trade_chronology.py` per spec §3):** `trade_events` (`swing/data/migrations/0003_phase2_pipeline_trades.sql:88`; payload in `payload_json`/`notes`); `fills` + `swing/data/repos/fills.py` (`list_fills_for_trade:168`, `list_all_fills:185`, `get_authoritative_entry_fill:148`; `Fill` has `action`/`quantity`, NOT `side`/`qty`); per-trade review on `trades` columns (`reviewed_at`/`lesson_learned`/grades; `review_log` is the CADENCE table -- NO `trade_id`); `daily_management_records` (Phase 8; `record_type` discriminates `daily_snapshot` vs `event_log` -- split + field-map per Codex major #5; stop fields live in `stop_changed`/`prior_stop`/`new_stop`). MFE/MAE are R-multiples, NOT %.
   - **Entry flags (OQ-4 V1 fields):** `has_hyprec_link` derived from `trade_origin == 'pipeline_watch_hyp_recs'` (`swing/trades/origin.py:71`), NOT `candidate_id is not None`; `hypothesis_label` (the "which"); `chart_pattern_algo`/`chart_pattern_operator`; A+ bucket; `candidate_id`/`pattern_evaluation_id` backlinks; `initial_shares`/`initial_stop`/`entry_price`/`planned_target_R` (Trade; for total_risk + BULZ target).
   - **BULZ row-expand (in-scope rewire):** `swing/web/templates/partials/open_positions_expanded.html.j2:38-44` (legacy static `/charts/{date}/{ticker}.png`) -> the SB3 `position_detail` SVG; `GET /trades/open/{trade_id}/expand` (`swing/web/routes/trades.py:2555`) -> `build_open_positions_expanded` (`swing/web/view_models/open_positions_row.py`); the trade-detail page already embeds `vm.position_chart_svg_bytes` (`swing/web/templates/trades/detail.html.j2:65`) via `get_cached_chart_svg(surface='position_detail')` in `build_trade_detail_vm` (`swing/web/view_models/trades.py:1722`). Renderer: `render_position_detail_svg` (`swing/web/charts.py:628`); `_draw_bulz_zones` (`:701`); `_bulz_target_price` (`:620`).
   - **Render path / load-bearing anchor:** `swing/web/chart_jit.py:117` `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)` + `swing/web/ohlcv_cache.py:131` (trailing-today, ticker-keyed, run-agnostic) -- this is WHY closed-trade charts must render-direct (OQ-1) and only open-trade row-expand may reuse the cache.
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`); highest migration `0023_*`. **The plan adds NO migration.**

8. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` (MCP dead in VS Code ext; WSL fallback is the path; v2.0.2), `feedback_codex_round_limit_suspended` (run to convergence; no 5-round cap), `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose; verify `%(trailers)`), `feedback_verify_regression_test_arithmetic` (exit-VWAP / total_risk / final_R single- vs multi-leg), `project_capital_risk_floor` (NOTE: OQ-6 LOCKed total_risk = DOLLAR risk at open, so the capital floor is NOT consumed by this column).

---

## §1 LOCKs inherited (BINDING through writing-plans; DO NOT re-litigate)

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = data-wiring -> temporal log -> charts -> **review + journal UX (THIS)** -> metrics; **Q2** SERIAL
- **Q5** matplotlib SVG only (reuse the SB3 mplfinance renderers; NO JS charting library)
- **Q6** operator browser-witnessed verification at merge (the rendered surface is the BINDING visual gate -- HTMX + matplotlib)
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** (operator-LOCKed OQ-8, §1.3)

### §1.2 Brainstorm spec §2 + L1-L8 LOCKs
- **L1** scope = CR.1 + P14.N6 + the in-scope BULZ row-expand wiring ONLY
- **L2** **read-mostly; NO new trade-mutation path.** The review POST + `complete_trade_review` write contract is UNCHANGED; journal + drill-down + all charts perform ZERO trade/fill/review/`chart_renders` writes. **Scope clarification (Codex R1 M#1):** "read-mostly" governs the TRADE domain; the OHLCV archive read-through (`read_or_fetch_archive`) is the app's existing shared cache -- SB4 chart helpers invoke it on the SAME terms (read existing; refresh on the existing cadence; degrade to chart-unavailable on empty per F6). That is permitted/pre-existing, NOT a new mutation path.
- **L3** **NO schema change** (render-direct eliminates the only v24 trigger; OQ-2 LOCK). Verdict v23-unchanged; §K asserts ZERO migration. (Gotcha #11/#9 are N/A this sub-bundle -- do NOT add a migration.)
- **L4** HTMX browser-only failure-surface trinity applies to journal sort/filter/drill-down/thumbnail (spec §8); operator-witnessed browser verification BINDING
- **L5** matplotlib visual-gate discipline; ASCII-only annotations; REUSE the SB3 renderers (no candlestick re-implementation)
- **L6** L2 Schwab LOCK preserved; ZERO new `schwabdev.Client.*` call sites; source-grep test stays green. The Schwab daily-bar wiring (banked #4) stays OUT.
- **L7** record the chart-access UX brief §2 reversal when the row-expand inlines the `position_detail` SVG (spec §6)
- **L8** market_weather 200MA fix banked standalone (OQ-7 LOCK), NOT in SB4

### §1.3 Operator-LOCKed OQ dispositions (operator-paired triage 2026-05-30; BINDING)

| OQ | LOCKed disposition |
|---|---|
| **OQ-1 CR.1 chart window** | **Render-direct** closed-trade chart over `entry-30d .. exit+10d` (padding days operator-tunable); NOT a reused trailing-today `position_detail` cache. |
| **OQ-2 chart surface / schema** | **NO new `chart_renders` surface enum; NO schema (v23 held).** Reuse the SB3 renderer render-direct. |
| **OQ-3 thumbnail breadth** | **Journal listing ONLY.** Bank the broader dashboard open-positions/hyp-rec thumbnail wiring (P14.N1) as a separate follow-up. |
| **OQ-4 hyp-rec "(and which)"** | **V1 derived fields, NO schema:** `has_hyprec_link` (`trade_origin=='pipeline_watch_hyp_recs'`) + `hypothesis_label` + pattern_class + A+ bucket. No hyp-rec FK. |
| **OQ-5 chronology shape** | **Unified timestamp-merged chronology** (single stream), NOT per-source sections. Plan LOCKs the source-precedence tiebreak order. |
| **OQ-6 total_risk semantics** | **Dollar risk at open** = `initial_shares * (entry_price - initial_stop)`. (Capital floor NOT consumed; no %-of-capital column in V1.) |
| **OQ-7 market_weather 200MA** | **Bank standalone** (Phase 14 polish); do NOT fold into SB4. |
| **OQ-8 Codex chain count** | **SINGLE chain** at writing-plans (run to convergence; cap suspended). |
| **OQ-9 sort/filter fragment** | **Whole-`<table>` `outerHTML` swap** (spec §8); confirm-only, do not re-punt. |

---

## §2 Architectural surface for the plan (BINDING substrate)

### §2.1 Per-task slicing (plan §G; the spec §9 6-slice decomposition; each task 3-5 commits max)
The spec LOCKs a 6-slice order; slices 0-1 are independent of 2-5; 2->3->4->5 are serial. The plan refines per-task:
- **Slice 0 -- CR.1 review enrichment** -- exit-data fields on `ReviewVM` (derive exit legs from fills; exit VWAP per Codex M#4 reducing-fill classification, long-only positive-qty) + a closed-trade chart on the review surface (render-direct, OQ-1; lazy-load route `GET /trades/{id}/review/chart` per Codex M#2 failure-isolation). **Builds the shared `swing/web/charts.py`-adjacent helper (`trade_charts.py` per spec §3) + the process-wide matplotlib render lock** that the later slices reuse.
- **Slice 1 -- BULZ row-expand rewire** -- `open_positions_expanded.html.j2` from the legacy static PNG to the SB3 `position_detail` SVG via the SAME read-only `get_cached_chart_svg` path `build_trade_detail_vm` uses (Codex R3 M#1: NO JIT, NO write); the one-open-trade-per-ticker invariant + refresh test (Codex M#12); record the §2-page reversal (L7). Independent of slices 2-5.
- **Slice 2 -- journal listing substrate** -- `JournalRowVM` (open_price/shares/total_risk[dollar, OQ-6]/closing_price/final_R/entry-flags[OQ-4 V1 fields]); `build_journal` enrichment; the rich row table.
- **Slice 3 -- sort/filter** -- whole-`<table>` `outerHTML` swap (OQ-9); HTMX trinity (L4); `filter_state` "reviewed" = `state=='reviewed'`.
- **Slice 4 -- thumbnails** -- candlestick thumbnails on journal listing rows ONLY (OQ-3); lazy-load on scroll via `hx-trigger="revealed"` + page size ~20-25 (Codex R4 M#2 + R5 M#2: VERIFY window-scroll layout, NOT overflow-container, or `revealed` won't fire -- use `hx-trigger="intersect"` with explicit root if overflow).
- **Slice 5 -- drill-down + chronology** -- `build_trade_drilldown_vm` + `TradeDrilldownVM`; NEW `swing/web/view_models/trade_chronology.py` (`build_trade_chronology` unified merge of fills + trade_events + per-trade review + daily_management_records; OQ-5 precedence); annotated full chart (render-direct, reuse `render_position_detail_svg`); full-page drill-down 404s on missing trade, only HTMX fragments return 200+unavailable (Codex M#6).

### §2.2 Per-task acceptance criteria (plan §G.X.acceptance)
Files modified/added (exact paths); functions/VMs added + signatures verified (#2); discriminating tests (name + assertion shape); cumulative discipline preservation per task; Sec 9.1 + L1-L8 + the §1.3 OQ-LOCK preservation per task; the render-lock no-deadlock test per chart path (see §2.4).

### §2.3 Test surface (plan §H)
Distributed across the 6 slices (rough: CR.1 enrichment + render lock ~12-18; BULZ rewire ~6-10; listing substrate ~10-16; sort/filter ~8-14; thumbnails ~8-12; drill-down + chronology ~16-24). **Plan sum-checks** in §H (trust pytest per gotcha #1). Mandatory: the **chronology per-source contract tests** (field-map per source, supersession, timestamp-normalization, malformed-payload isolation -- Codex R1 M#9; the one substantive artifact); the **render-lock no-deadlock test per chart path**; the **exit-VWAP / total_risk / final_R single- vs multi-leg arithmetic tests** (`feedback_verify_regression_test_arithmetic` -- compute under BOTH leg shapes); the HTMX swap-contract + thumbnail-trigger tests; the missing-trade 404-vs-fragment-200 test. **0 slow tests** (charts render from fixture bars; assemblies from planted rows).

### §2.4 The process-wide matplotlib render lock (HIGHEST-RISK item; plan MUST specify)
SB4 adds 2 NEW render-direct chart paths (CR.1 review chart + drill-down annotated chart) into the SB3-shared `charts.py`, which uses pyplot global state with NO existing lock (Codex R3 M#2 -> R4 M#1 -> R5 M#1). The plan SHALL specify: a **process-wide render lock at the SHARED `charts.py` render boundary** so EVERY web render path serializes (not SB4-only -- R4 M#1); a **single outer acquisition per render** (`RLock` if nesting is unavoidable -- R5 M#1 self-deadlock guard); and a **no-deadlock test per chart path**. Pair with thumbnail load-on-scroll + smaller page size so the lock cannot queue ~50 renders into a DoS (R4 M#2).

### §2.5 Operator-witnessed visual + HTMX gate runbook (plan §I)
The BINDING gate is the RENDERED surface in a REAL browser (matplotlib + HTMX; byte/string tests insufficient; TestClient cannot catch the HTMX trinity):
- **S1** pytest + ruff; **S2** schema = NO migration (`schema_version=23`; assert ZERO new `chart_renders` rows from SB4 paths); **S3** CR.1 review surface (exit data + render-direct closed-trade chart, correct trade-window); **S4** BULZ row-expand shows the SB3 candlestick+zones SVG (not the legacy `<img>`); **S5** journal listing (rows + flags + dollar total_risk + lazy thumbnails); **S6** sort/filter `outerHTML` swap (focus/scroll/control persistence); **S7** drill-down (unified chronology + annotated chart; missing-trade 404). DB-scriptable where possible; the prior-sub-bundle fallback (operator-driven browser + orchestrator DB-side probes; OR orchestrator renders to PNG + reads it) applies. Re-confirm the SB4 gate split with the operator at executing-plans (`feedback_visual_gate_both_render_and_browser`).

### §2.6 Codex single-chain placement + schema (plan §J + §K)
- SINGLE chain at end (OQ-8 LOCK); run to CONVERGENCE (no fixed round cap; zero new crit/major is the stop criterion).
- Plan §K: **NO new migration.** `EXPECTED_SCHEMA_VERSION` stays 23. Assert ZERO `00XX` added. The render-direct decision (OQ-1/OQ-2) is what keeps SB4 schema-free; the plan documents that load-bearing linkage.

---

## §3 Residual OQs (Codex SHOULD lock in the plan)
1. The CR.1 + drill-down chart-window padding (entry-30d .. exit+10d) -- exact slice bounds + bar-source (render-direct OHLCV window).
2. The shared `trade_charts.py` helper API (render-direct figure construction reused by CR.1 + drill-down) + the render-lock acquisition shape.
3. The unified chronology source-precedence tiebreak order (OQ-5) + the per-source field-map (fills/trade_events/review/daily_management_records).
4. The `JournalRowVM` field list + the entry-flag derivations (OQ-4 V1 fields) -- exact column reads (#4 verify).
5. The lazy-thumbnail trigger (`revealed` vs `intersect`) pending the journal layout's scroll model.
6. Commit cadence preface (§G.0; cascade audit each round).

---

## §4 OUT OF SCOPE (do not design into the plan)
- Metrics overview (SB5); the broader P14.N1 dashboard open-positions/hyp-rec thumbnail wiring (OQ-3 banked); the market_weather 200MA fix (OQ-7 banked); the Schwab daily-bar web wiring (banked #4; L6); any new schema/migration (L3); any new trade-mutation path (L2); temporal-log/v22 or chart-rename/v23 substrate changes; JS charting (Q5); Phase 15+; production code NOT in the plan's file map.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. Signature/column verify (#2/#4) -- the review/journal routes + VMs; the chronology source columns (`Fill.action`/`quantity`; `review_log` has no `trade_id`; `daily_management_records.record_type`; MFE/MAE R-multiples); `trade_origin` enum; re-grep at plan time. The 8 `.copowers-findings.md` corrections MUST be honored.
2. Read-mostly (L2) -- ZERO new trade/fill/review/`chart_renders` writes; the OHLCV archive read-through is the only permitted I/O.
3. NO schema (L3) -- assert ZERO migration; the render-direct linkage that keeps it schema-free is documented.
4. Render lock (§2.4) -- process-wide at the shared boundary; single outer acquisition / RLock; no-deadlock test per chart path; thumbnail-DoS guard.
5. HTMX trinity (L4) -- sort/filter/drill-down/thumbnail: 4xx-swap config, `hx-headers HX-Request`, `204`+`HX-Redirect`, table-row-free fragment root + OOB tbody swap, HX-Redirect target registered, `revealed`-vs-overflow; shared-`base.html.j2` VM-field defaults on ALL base VMs.
6. Matplotlib mathtext + visual-gate (L5) -- ASCII annotation text; per-surface operator-witnessed gate declared; byte/string insufficient; reuse SB3 renderers.
7. Chronology contracts (§2.3) -- per-source field-map + supersession + timestamp-normalization + malformed-payload isolation tested.
8. total_risk / exit-VWAP / final_R single- vs multi-leg arithmetic (`feedback_verify_regression_test_arithmetic`).
9. L2 Schwab source-grep continues passing; ASCII discipline (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` empty). The return report EVIDENCES the chain ran genuinely via WSL (cite `.copowers-findings.md` rounds).

---

## §6 Deliverable shape
Plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-4-review-journal-ux-plan.md`: §A Goals/non-goals · §B File map · §C Surface-by-surface integration · §D Out-of-scope · §E LOCK reverification (Sec 9.1 + L1-L8 + the §1.3 OQ dispositions) · §F Discipline + watch items per task · §G Per-slice tasks (Slice 0-5) + §G.0 commit cadence · §H Test surface (sum-check) · §I Operator-witnessed visual + HTMX gate runbook · §J Codex single-chain placement (run-to-convergence) · §K Schema impact (NO change) · §L Test fixture strategy · §M Forward-binding lessons · §N Self-review checklist. **Target ~1800-3000 lines.** Commit stem: `docs(phase14-sub-bundle-4-plan): writing-plans -- ...` (final `-m` paragraph plain prose).

---

## §7 If you get stuck
- If CR.1 or P14.N6 appears to need a new write/mutation path OR a schema change, ESCALATE -- L2/L3 forbid both in V1 (the render-direct decision is the schema-free guarantee).
- If production drifted since the brainstorm merge (`2cf30f9`) and a spec-cited file:line no longer matches, ESCALATE.
- HOLD THE LINE: the 9 §1.3 OQ dispositions; matplotlib/mplfinance no-JS (Q5); SINGLE chain run-to-convergence (OQ-8 + cap suspended); render-direct closed-trade charts / cache-reuse only for open-trade row-expand (OQ-1).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT attempt the Codex MCP tools (dead in the VS Code extension); use the WSL Codex fallback (reads the worktree from disk; copowers v2.0.2 auto-routes).
- DO NOT widen scope to SB5 / the banked P14.N1 dashboard breadth / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §8 Return report shape
Mirror prior writing-plans return reports (15 items): final HEAD + commit breakdown (Codex round attribution); Codex chain + convergent shape (EVIDENCE it ran genuinely via WSL -- cite `.copowers-findings.md` rounds; NOT a silent no-op, NOT a premature stop while majors remained); plan line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L8 + the §1.3 OQ dispositions); residual OQs locked; Codex Major accepted (ZERO preferred); per-slice acceptance summary; test surface (sum-check); forward-binding lessons for executing-plans (esp. the render-lock no-deadlock + the chronology per-source contracts -- the two highest-risk items); schema impact verdict (NO change); cumulative gotcha application; worktree teardown; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness summary.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-4-review-journal-ux-writing-plans`. Dir `.worktrees/phase14-sub-bundle-4-review-journal-ux-writing-plans/`. Branch from main HEAD `5ddd936`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain (OQ-8 LOCK), run to convergence via the WSL Codex fallback (copowers v2.0.2; MCP dead in the VS Code extension).
- **Expected duration:** ~2-4 hours writing-plans + a Codex chain run to convergence.

---

*End of brief. Phase 14 Sub-bundle 4 writing-plans dispatch -- produce a per-slice implementation plan from the 1277-line brainstorm spec (CR.1 review exit-data + render-direct chart enrichment; P14.N6 browse-the-database journal across 6 slices: listing + sort/filter + journal-only thumbnails + drill-down unified-chronology + annotated chart; BULZ row-expand rewire to the SB3 position_detail SVG; a shared trade_charts.py helper + a process-wide matplotlib render lock; ~1800-3000 lines; SINGLE Codex chain run to convergence). The 9 operator-LOCKed OQ dispositions are in §1.3; HOLD THE LINE. NO schema change (render-direct keeps SB4 schema-free). The rendered surface in a real browser is the BINDING operator-witnessed gate (HTMX + matplotlib). OUTPUT: an implementation plan the executing-plans phase can dispatch directly.*
