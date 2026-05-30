# Phase 14 Sub-bundle 4 -- Review + Journal UX -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 4 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **review + journal UX** sub-bundle -- the per-trade close-the-loop workflow surfaces carried in the Phase 14 commissioning brief Sec 2.3: **CR.1** (closeout-review surface enhancement -- surface exit data + a chart snapshot at the post-trade review surface) + **P14.N6** (journal-page redesign -- a "browse-the-database" surface with rich per-trade rows, clickable per-trade drill-down to an annotated chart + the entries filled at open, and small candlestick thumbnails). The unifying thread: both surfaces consume the Phase 13 T2.SB6 `chart_renders` cache + the Phase 14 SB3 candlestick renderers + the existing review/journal/fills/trade_events data, and both are **read-mostly over already-shipped data** -- this is a UX + wiring sub-bundle, not a new-data-path sub-bundle.

**Brief:** `docs/phase14-sub-bundle-4-review-journal-ux-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`. **Sub-bundle 1 (data-wiring) SHIPPED end-to-end at `e323339`**; **Sub-bundle 2 (temporal log V1+; v22) SHIPPED end-to-end at `27f8007`** (v22 live); **Sub-bundle 3 (chart-surface uniformity; v23) SHIPPED end-to-end at `edd098d`** (operator-witnessed gate PASS; v23 live in the operator's real DB; the 4 detail renderers got mplfinance candlesticks; `hyprec_detail`->`ticker_detail` rename; BULZ risk/reward zones; P14.N1 thumbnail substrate shipped substrate-only with consuming-surface wiring deferred to THIS sub-bundle). Main HEAD at Sub-bundle 4 brainstorming dispatch: `604211e`.

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (the Gotchas section is compressed to trigger+fix; the "Expansion #N" process/review + brief-authoring disciplines were RELOCATED to `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~648+ cumulative ZERO Co-Authored-By trailer drift; **Schema v23 LOCKED** (operator's live DB migrated v22->v23 at SB3 ship; `swing` reinstalled, expects v23); L2 LOCK preserved (multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py`). **SB4 likely introduces NO schema change** -- if one is needed (a `chart_renders` surface-enum widening is the only realistic trigger) it would be **v24, STRICT backup-gate `pre_version == 23`** per gotcha #11 + #9.

**Expected duration:** ~3-5 hours brainstorming + 2-4 Codex rounds. Spec line target **~600-1000 lines** (CR.1 is small/template-extension; P14.N6 is the LARGEST single Phase 14 item -- a multi-surface "browse-the-database" redesign -- and dominates the spec; the BULZ row-expand wiring is a small in-scope rider).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` with adversarial Codex MCP review after the spec is written.
- **Codex chain count: SINGLE chain at end** for THIS brainstorming phase per Sec 9.1 Q7 LOCK + gotcha #36 caveat (pure UX/wiring sub-bundle, no substantive analytical artifact). Reconsider at writing-plans if P14.N6's "browse-the-database" assembly surfaces a substantive analytical/aggregation artifact warranting the two-chain default.
- **Codex transport (FB-N1) -- RESOLVED 2026-05-30; copowers v2.0.2 + a WSL Codex CLI fallback that reads the repo FROM DISK:** the copowers Codex MCP `codex`/`codex-reply` tools are **PERMANENTLY DEAD in the VS Code extension** (hardcoded ~1s `MCP_CONNECTION_NONBLOCKING` fire-and-forget deadline; the server is healthy, the transport is the wall; gh #43791 + #47076). **Do NOT attempt the MCP tools or the launcher/marketplace/settings angle (exhausted).** copowers is now GitHub-sourced (`copowers@copowers` from rwsmythe/copowers; **v2.0.2**; dev clone `C:\Users\rwsmy\copowers-sync`) and its `adversarial-critic` skill now **AUTO-ROUTES to a WSL Codex CLI fallback on MCP failure** -- the prior skill silently treated an MCP timeout as a clean `NO_NEW_CRITICAL_MAJOR` round (a **false-green now FIXED in v2.0.2**). **Preferred path: invoke `copowers:brainstorming` normally and let it drive the WSL fallback for you.** The fallback runs Linux Codex `-s read-only` and **reads the spec + the repo FROM DISK -- no inline prompt-size limit (the old inline-paste constraint is GONE)** -- appending each round's findings to `.copowers-findings.md` in the (worktree) repo root and re-reading the tree each round (Option A: Codex stays read-only, never modifies the tree). **Canonical WSL invocation if driving Codex directly (point `-C` at THIS worktree so Codex reviews the right tree):**
  - R1: `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-4-review-journal-ux-brainstorming - < <promptfile>'`
  - R2+: `wsl -e bash -c '... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check - < <promptfile>'`
  WSL is fully provisioned (Node 22, codex-cli 0.135.0, Windows auth reused, bubblewrap, PATH) -- no setup needed; `resume --last` carries thread continuity (delta-only prompts rounds 2+). See memory `feedback_copowers_codex_mcp_windows_launcher` for the full verified writeup.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-4-review-journal-ux-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase14-commissioning-brief.md`** -- especially **Sec 2.3** (review + journal UX sub-bundle architectural notes: CR.1 extends T2.SB6 `chart_renders`; P14.N6 is the LARGEST single item; both require small-chart integration per P14.N1; "Order this AFTER chart-surface uniformity bundle since both consume the thumbnail substrate") + **Sec 6** (cross-cutting watch items) + **Sec 9.1 LOCKs** (Q1 sequencing, Q2 serial, Q5 matplotlib-SVG graphics, Q6 operator-witnessed close-out, Q7 Codex chain discretion).

3. **`docs/phase3e-todo.md`** -- the Phase 14 scope roll-up:
   - The **2026-05-27 PM operator-identified operational backlog** entry (CR.1 detail: "surface (a) exit data (price at exit) and (b) a snapshot of the chart at exit/close to help the operator identify notes to add to the journal"; touch points; reuse T2.SB6 chart_renders; ZERO new schema; ZERO new Schwab API calls).
   - The **2026-05-27 PM #2** 5-field detail blocks for **P14.N6** (the journal redesign -- read the full operator framing verbatim: rich trade rows with open_price/shares/total_risk/closing_price/final_R/entry-flags + clickable drill-down to entries + annotated chart + candlestick thumbnails) and **P14.N1** (thumbnail consuming surfaces).
   - The **2026-05-30 SB3 EXECUTING-PLANS SHIPPED top entry** -- the SB3 ship record + the **4 banked follow-ups** (BULZ row-expand wiring -> IN-SCOPE for SB4; market_weather 200MA fetch-window; theme2 vcp cosmetic crowding; the separate Schwab daily-bar wiring item).

4. **CLAUDE.md** (compressed gotchas) -- especially:
   - **HTMX browser-only failure surfaces** (the binding trinity for any new HTMX-driven journal sort/filter/drill-down): 4xx-swap config override; embedded forms need `hx-headers '{"HX-Request":"true"}'`; success = `204` + `HX-Redirect` (NOT `303`); HTMX response leading with `<tr>` triggers synthetic-table-wrap (keep fragment root table-row-free, deliver rows via OOB swap into tbody); HX-Redirect target route must be registered. **Operator-witnessed browser verification is BINDING for HTMX work.**
   - **`base.html.j2` is shared** -- a new `vm.foo` field requires adding it (with a safe default) to EVERY base-layout VM (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) or Jinja 500s unrelated routes.
   - **Matplotlib mathtext** fires on `$` `^` `_` and unbalanced `\` -> omit metacharacters from titles/labels/annotations; **manual visual verification of rendered text is non-optional** (the binding operator-witnessed gate for any chart surfaced by CR.1 / P14.N6 / BULZ row-expand).
   - **(#11)** Schema-CHECK + Python-constant + dataclass-validator + read-path `_row_to_*` mapper paired (same task) IF any `chart_renders` surface-enum value is added (the only realistic SB4 schema trigger) -> v24 migration, backup-gate STRICT `pre_version == 23`; **(#9)** executescript implicit COMMIT -> explicit BEGIN/COMMIT/ROLLBACK.
   - **Cache + executor race** (workers must not write shared state on deadline miss) + **External-API empty-result transient (F6)** + **Shared-infrastructure cache hooks must return the FULL archive; consumers slice** + **OHLCV fetch scope = open-trade tickers** (chart bar sourcing for any journal/closed-trade chart).
   - **`chart_renders` cache-key shape** + **renderer-kwargs uniformity (Expansion #10c)** if a journal/review chart reuses an existing surface enum.
   - AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- especially **Expansion #10** (architecture-location audit + (c) renderer-kwargs uniformity / cache-collision discriminating tests when a surface enum is reused), **#2** (brief-vs-signature; re-grep at writing-plans), **#4** (SQL column verification -- P14.N6's "entry-time flags" depend on real `trades` backlink columns), **#11** (taxonomy propagation if a surface enum is added).

5. **Production code surfaces to read BEFORE drafting (architectural anchors -- VERIFIED by the orchestrator at dispatch; re-grep at writing-plans per #2).** **IMPORTANT brief-vs-reality correction: the CR.1 review web form ALREADY EXISTS and is fully wired** -- CR.1 is an ENHANCEMENT of that surface (surface exit data + a chart snapshot), NOT a greenfield form build. Confirm this at brainstorm and scope CR.1 as the delta.
   - **Review surface (CR.1; EXISTS):** `GET`/`POST /trades/{trade_id}/review` at `swing/web/routes/trades.py:2589` (`review_form_page`) + `:2609` (`review_post`); `build_review_vm` + `ReviewVM` at `swing/web/view_models/trades.py:1183` / `:1106`; templates `swing/web/templates/review.html.j2` + `swing/web/templates/partials/review_form.html.j2`. The review service `complete_trade_review` at `swing/trades/review.py:550` (state transition closed->reviewed; **do NOT change this write contract** -- CR.1 is read-surface enrichment). The current review surface displays trade entry date+price + actual realized R + mistake-cost/lucky-violation + MFE/MAE + priors -- it does **NOT** currently surface exit_price/exit_date prominently, nor a chart. That gap IS the CR.1 delta.
   - **Journal surface (P14.N6; EXISTS, minimal):** `GET /journal?period=...` at `swing/web/routes/journal.py:15` (`journal_page`); `JournalVM` + `build_journal` at `swing/web/view_models/journal.py:98` / `:136`; template `swing/web/templates/journal.html.j2`. Current `build_journal` reads `list_open_trades` + `list_closed_trades` + `_list_all_exitshape_via_fills` + `list_weather_runs`, computes period-filtered `compute_stats` + behavioral `compute_flags`. P14.N6 is a REDESIGN layering a rich browse-the-database surface on top.
   - **Journal chronology data sources:** `trade_events` table (`swing/data/migrations/0003_phase2_pipeline_trades.sql:88`; event_type CHECK widened by 0014 + 0019); `fills` table + `swing/data/repos/fills.py` (`list_fills_for_trade:168`, `list_all_fills:185`, `get_authoritative_entry_fill:148`); `review_log` table (`swing/data/migrations/0013_phase6_post_trade_review.sql`); `daily_management_records` (Phase 8). **No existing timeline/chronology assembly helper** -- P14.N6's per-trade drill-down narrative is a NEW assembly over these (read-only).
   - **Entry-time flags for the journal listing (P14.N6):** the Phase 13 T2.SB6c trade backlinks (`candidate_id` + `pattern_evaluation_id` on the `trades` table) supply chart-pattern-class + A+ tier + hyp-rec linkage. **VERIFY the exact column names + which table holds pattern_class/aplus/hyp-rec via #4 SQL-column verification at brainstorm** -- do NOT assume.
   - **BULZ row-expand wiring (banked follow-up #1; IN-SCOPE):** the dashboard open-positions row-expand `swing/web/templates/partials/open_positions_expanded.html.j2:38-44` still embeds the **legacy static** `/charts/{date}/{ticker}.png` (rendered by `swing/rendering/charts.py:render_chart`); the trade-detail page `swing/web/templates/trades/detail.html.j2:65` already embeds the SB3 `vm.position_chart_svg_bytes` (the candlestick + BULZ-zone SVG from `swing/web/charts.py:render_position_detail_svg:628`, cached via `get_cached_chart_svg(surface='position_detail')`). SB4 should wire the row-expand (and the CR.1/P14.N6 chart surfaces) at the SB3 `position_detail` SVG so the P14.N4 BULZ zones + candlesticks are visible in the operator's primary workflow. Handler: `GET /trades/open/{trade_id}/expand` at `routes/trades.py:2555` -> `build_open_positions_expanded` (`swing/web/view_models/open_positions_row.py`).
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51`; highest migration `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql`.

6. **`docs/superpowers/specs/2026-05-29-phase14-sub-bundle-3-chart-surface-uniformity-design.md`** (the SB3 spec -- REFERENCE for the candlestick renderer + chart_renders cache contract you're consuming) + the SB2 + SB1 specs (spec shape + Codex-catch documentation precedent).

7. **`docs/orchestrator-context.md`** §"Currently in-flight work" + §"Pre-Codex review + brief-authoring disciplines".

8. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_copowers_codex_mcp_windows_launcher` (FB-N1 CLI backstop + read-only-sandbox inline-paste wrinkle; the MCP is being separately debugged -- off your purview)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`)
   - `feedback_visual_gate_both_render_and_browser` (the SB3 operator-witnessed gate preference: operator-driven browser + orchestrator DB-side probes; re-confirm for SB4)
   - `project_capital_risk_floor` (BINDING for P14.N6's "total risk" column -- risk uses max($7500 floor, actual balance))

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)
- **Q1** sequencing = data-wiring (SHIPPED) -> temporal log (SHIPPED) -> chart-surface uniformity (SHIPPED) -> **review + journal UX (THIS SUB-BUNDLE)** -> metrics overview
- **Q2** execution = SERIAL
- **Q5** graphics library = **matplotlib SVG** (no JS charting lib; consistent with `chart_renders`) -- any chart/thumbnail in CR.1 + P14.N6 uses the SB3 mplfinance renderers, not a new dependency
- **Q6** close-out = operator browser-witnessed verification at merge (the rendered surface is the BINDING visual gate)
- **Q7** Codex chain count = orchestrator discretion; **SINGLE chain** for THIS brainstorming (pure UX/wiring)

### §1.2 Sub-bundle 4 phase-specific LOCKs (this brief)
- **L1** Scope = **CR.1** (review-surface exit-data + chart-snapshot enhancement) + **P14.N6** (journal redesign) + the **in-scope BULZ row-expand wiring** (banked follow-up #1) ONLY. Do NOT widen to metrics overview (Sub-bundle 5), Phase 15+, or any item outside this set. P14.N1's thumbnail consuming-surface wiring is in-scope **only where it serves the journal listing** (P14.N6 explicitly asks for journal thumbnails); broader dashboard open-positions/hyp-rec thumbnail wiring is an OQ (see §3).
- **L2** **Read-mostly; NO new trade-mutation paths.** The review POST + `complete_trade_review` state machine already exist and must NOT change their write contract (CR.1 is read-surface enrichment). The journal + journal-drill-down + chart snapshots are pure READ surfaces. If brainstorming surfaces any apparent need for a new write/mutation, ESCALATE -- do not design it into V1.
- **L3** **Likely NO schema change.** If (and only if) a NEW `chart_renders` surface-enum value is required (e.g. a `journal_trade_chart` surface) -- the only realistic SB4 schema trigger -- it lands as a **v24 migration** (gotcha #11 paired: CHECK enum + Python constants + any `Literal`/frozenset mirror + read-path `_row_to_*` mapper, ALL one task; gotcha #9 explicit BEGIN/COMMIT/ROLLBACK; backup-gate STRICT `pre_version == 23`). **Recommend reusing an existing surface enum (`position_detail`/`ticker_detail`) to avoid schema entirely; confirm at brainstorm.** Do NOT touch the v22 (temporal-log) or v23 (chart-surface-rename) substrate.
- **L4** **HTMX browser-only failure surfaces** -- any new HTMX-driven journal sort/filter/drill-down inherits the full trinity (4xx-swap config; `hx-headers HX-Request` on embedded forms; `204`+`HX-Redirect` not `303`; table-row-free fragment root + OOB swap into tbody; HX-Redirect target route registered) + the shared-`base.html.j2`-VM-field discipline. TestClient cannot catch these -> operator-witnessed browser verification is BINDING.
- **L5** **Matplotlib visual-gate discipline** -- byte/string-equality tests are INSUFFICIENT for chart-render correctness; the spec MUST enumerate an operator-witnessed visual gate (rendered SVG/PNG) for each chart surfaced (CR.1 chart snapshot, P14.N6 annotated drill-down chart + thumbnails, BULZ row-expand). ASCII-only annotation text. **Reuse the SB3 mplfinance shared helpers + `render_position_detail_svg` / `render_ticker_detail_svg`; do NOT re-implement candlestick logic.**
- **L6** **L2 LOCK (Schwab) preserved** -- ZERO new `schwabdev.Client.*` call sites; the source-grep test MUST continue passing. The **Schwab daily-bar wiring (banked follow-up #4) is a SEPARATE Phase 14 item, explicitly OUT of SB4** (it touches the L2-locked Schwab call surface).
- **L7** **BULZ row-expand reversal note** -- the chart-access UX brief §2 deliberately put position-detail on a SEPARATE page. If SB4 inlines the `position_detail` SVG into the dashboard row-expand, RECORD the reversal in that brief (per banked follow-up #1).
- **L8** **Banked-rider triage** -- the market_weather 200MA fetch-window (follow-up #2) is NOT SB4-specific; brainstorm ASSESSES whether to fold it in as a small ride-along fix or bank as standalone Phase 14 polish (recommend: bank unless trivially co-located). The theme2 vcp 5-contraction cosmetic crowding (follow-up #3) is lowest-priority cosmetic -- bank; do NOT design in.

---

## §2 Spec scope to design

### §2.1 CR.1 -- closeout-review surface enhancement (exit data + chart snapshot)
- Confirm the EXISTING review surface (`GET /trades/{trade_id}/review` + `review.html.j2` + `review_form.html.j2` + `ReviewVM`/`build_review_vm`). Design the DELTA: prominently surface **exit_price + exit_date** (data likely already on the trade VM / derivable from fills -- verify) + a **chart snapshot at exit/close** reusing the T2.SB6 `chart_renders` cache (the SB3 `position_detail` candlestick + BULZ-zone SVG is the natural source). Likely template-extension + VM-field-addition scope; ZERO new schema if it reuses an existing chart surface.
- Decide: does the review chart reuse the cached `position_detail` SVG (run-agnostic cache key), or render a closed-trade-specific snapshot? (recommend reuse; OQ if the closed-trade chart needs a different window/markers).

### §2.2 P14.N6 -- journal-page redesign (browse-the-database)
This is the LARGEST item -- design it carefully and recommend a writing-plans sub-decomposition (slices). Two surfaces:
- **(a) Main listing:** a rich, sortable/filterable per-trade table. Each row: open_price + shares + **total_risk** (cfg capital-floor-aware per `project_capital_risk_floor`) + closing_price + final_R + entry-time flags (chart_pattern_class + A+ tier + hyp-rec linkage + hypothesis_label via the Phase 13 T2.SB6c trade backlinks -- VERIFY columns per #4) + a small **candlestick thumbnail** (P14.N1 substrate; consuming-surface wiring here). Database-browsing affordance = filter + sort; HTMX-driven without full page reload (L4 disciplines).
- **(b) Click-through per-trade drill-down:** the entries filled at open (Phase 6 review_log + Phase 7 fills + Phase 8 daily_management_records + trade_events) assembled into a per-trade narrative/chronology (NEW read-only assembly; no existing helper) + an **annotated full chart** with entry/stop/target/fills marked (the SB3 `position_detail` renderer already plots fills + BULZ zones -- reuse).
- Define the VM(s), the route(s) (extend `GET /journal` and/or add a `GET /journal/trades/{id}` drill-down), the template(s) + partials, and the thumbnail plumbing. Resolve the chart-surface reuse-vs-new-enum decision (L3).

### §2.3 BULZ row-expand wiring (in-scope rider)
- Wire `open_positions_expanded.html.j2` (and any peer row-expand) from the legacy static `/charts/{date}/{ticker}.png` to the SB3 `position_detail` SVG (`vm.position_chart_svg_bytes` via `get_cached_chart_svg(surface='position_detail')`), so candlesticks + BULZ zones appear in the dashboard workflow. Record the §2-page reversal per L7. Define the VM-field plumbing + a discriminating test asserting the row-expand response contains the SVG (not the legacy `<img src=/charts/...>`).

### §2.4 Operator-witnessed gate enumeration
- S1 fast suite + ruff; S2 schema (assert NO unexpected migration unless the v24 surface-enum decision is taken, in which case `schema_version=24` + backup + reused-vs-new-surface verified); S3+ per-surface visual gates (CR.1 exit-data + chart snapshot; P14.N6 listing + thumbnails + drill-down annotated chart; BULZ row-expand SVG) -- the rendered surface in a REAL browser is the BINDING gate (matplotlib + HTMX). For surfaces with no live data to exercise them, the orchestrator-render-to-PNG + Read fallback (used for SB3 S6) is the documented substitute.

---

## §3 Open questions (Codex SHOULD surface answers; operator triage at writing-plans dispatch)

1. **CR.1 scope reconciliation** -- the review web form already exists; confirm CR.1 = exit-data + chart-snapshot delta only (vs any larger redesign the operator intends). Does the review surface need the closed-trade chart, or a reused `position_detail` cache hit?
2. **P14.N6 chart surface** -- reuse `position_detail`/`ticker_detail` (no schema) vs NEW `journal_trade_chart` surface enum (v24 migration)? (recommend reuse).
3. **P14.N6 thumbnail wiring breadth** -- journal listing ONLY (clearly in P14.N6 scope), or ALSO the dashboard open-positions + hyp-rec rows (the broader P14.N1 ask, arguably outside the review+journal L1 LOCK)? The BULZ row-expand (in-scope) already touches the dashboard -- does that widen the door, or stay surgical?
4. **P14.N6 entry-time flags** -- exact `trades` (and backlink) columns for chart_pattern_class / A+ tier / hyp-rec linkage / hypothesis_label (#4 verification at brainstorm).
5. **P14.N6 drill-down assembly** -- the per-trade chronology spans review_log + fills + trade_events + daily_management_records; is a unified chronology helper warranted, or per-source sections? Ordering/precedence rules?
6. **P14.N6 sub-decomposition** -- the writing-plans slice boundaries (listing substrate first; thumbnails; drill-down; annotated chart)?
7. **Banked rider #2** -- fold the market_weather 200MA fetch-window fix into SB4, or bank standalone? (L8).
8. **Codex chain count at writing-plans** -- single (pure-UX) vs two-chain (if P14.N6's browse-the-database assembly is substantive enough)?

---

## §4 OUT OF SCOPE (do not design into V1)
- Metrics overview (Sub-bundle 5; P14.N5) -- per Sec 9.1 Q1 serial LOCK
- The Schwab daily-bar web-wiring (banked follow-up #4) -- a SEPARATE Phase 14 item touching the L2-locked Schwab surface
- Any new trade-mutation path / change to the review-write or fills-write contract (L2)
- Schema migrations beyond a single optional v24 surface-enum widening (and only if §3-Q2 lands "new surface")
- Temporal-log (v22) or chart-surface-rename (v23) substrate changes
- NEW analytical artifacts / ruleset changes
- JS-based charting libraries (matplotlib SVG only, Sec 9.1 Q5)
- The theme2 vcp cosmetic crowding (follow-up #3) -- bank, do not design
- Phase 15+ scope (incl. P14.N7 schwabdev checker-thread resilience)

---

## §5 Adversarial review (Codex) -- watch items

Invoked by `copowers:brainstorming` after the spec draft. SINGLE chain (Q7); 2-4 round target.

1. **Brief-vs-production-signature verification (#2)** -- cite real route/VM/renderer/repo names + signatures (`review_post`, `build_review_vm`, `build_journal`, `render_position_detail_svg`, `list_fills_for_trade`, `get_cached_chart_svg`); re-grep at writing-plans. CONFIRM the CR.1-form-already-exists correction.
2. **SQL-column verification (#4)** -- P14.N6 entry-time flags + total_risk + final_R depend on REAL columns; verify against migrations, do not assume backlink column names.
3. **HTMX browser-only failure surfaces (L4)** -- any new sort/filter/drill-down: 4xx-swap config, `hx-headers HX-Request`, `204`+`HX-Redirect`, table-row-free fragment root + OOB tbody swap, HX-Redirect target registered; shared-`base.html.j2`-VM-field defaults on ALL base VMs.
4. **Matplotlib mathtext + visual-gate discipline (L5)** -- ASCII annotation text; per-surface operator-witnessed visual gate; byte/string tests declared INSUFFICIENT; reuse SB3 renderers (no candlestick re-implementation).
5. **Schema discipline (L3; #11/#9)** -- IF a surface enum is added: CHECK + constants + read-path mapper one task; backup-gate STRICT `pre_version == 23`; explicit BEGIN/COMMIT/ROLLBACK. Otherwise assert ZERO migration.
6. **chart_renders cache-key + renderer-kwargs uniformity (Expansion #10c)** -- reused surfaces pass identical kwargs; cache-collision discriminating tests.
7. **No-new-mutation-path (L2)** -- the review-write + fills-write contracts unchanged; journal/drill-down are read-only.
8. **L2 LOCK source-grep** -- continues passing; ZERO new `schwabdev.Client.*` call sites.
9. **ASCII discipline (#16/#32)** -- declare scope across NEW files/templates.
10. **Co-Authored-By footer suppression** + the trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` empty).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-4-review-journal-ux-design.md`** (mirror the SB3 brainstorm spec format):
§1 Architecture overview · §2 Pre-locked operator decisions (Sec 9.1 + L1-L8) · §3 Module touch list (review route/VM/templates; journal route/VM/templates + new partials; open_positions_expanded; fills/trade_events/review_log repos consumed; charts.py renderers reused; optional v24 migration + db.py IF surface enum) · §4 CR.1 design (exit-data + chart-snapshot delta) · §5 P14.N6 design (listing + thumbnails + drill-down + annotated chart) · §6 BULZ row-expand wiring · §7 Chart-surface reuse-vs-new-enum decision (schema impact) · §8 HTMX surface disciplines applied · §9 Sub-bundle decomposition recommendation (writing-plans slices for P14.N6) · §10 Test fixture strategy (+ visual-gate enumeration) · §11 Schema impact analysis (NO change, or v24) · §12 V1 simplifications + V2 candidates · §13 Operator decision items (OQs) · §14 Cumulative discipline compliance summary.

**Target line count: ~600-1000 lines.** **Commit message stem:** `docs(phase14-sub-bundle-4-spec): brainstorm <draft|R1|...> -- ...` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If CR.1 or P14.N6 appears to need a NEW write/mutation path, ESCALATE -- L2 forbids it in V1.
- If the chart-surface decision forces a schema change you can avoid by reusing `position_detail`/`ticker_detail`, PREFER reuse (L3).
- If Codex pushes for a JS charting lib, HOLD THE LINE -- Sec 9.1 Q5.
- If Codex pushes to fold the Schwab daily-bar wiring (follow-up #4) into SB4, HOLD THE LINE -- it's a separate L2-touching Phase 14 item (L6/§4).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose.
- DO NOT modify the v22/v23 substrate.
- DO NOT attempt the Codex MCP tools or its launcher/settings (permanently dead in the VS Code extension); the `copowers:brainstorming` skill (v2.0.2) auto-routes to the WSL Codex CLI fallback, which reads the worktree from disk -- let it run, or drive the canonical WSL invocation directly (§ skill posture).

---

## §8 Return report shape

Mirror the SB3 brainstorm return report (15 items): final HEAD + commit breakdown; Codex round chain + convergent shape (EVIDENCE the chain ran genuinely via the WSL fallback -- cite the `.copowers-findings.md` per-round content -- NOT a silent MCP no-op; the orchestrator QAs this); spec line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L8); OQs resolved + deferred; Codex Major findings accepted (ZERO preferred); the CR.1-form-already-exists correction + any other brief-vs-production corrections; V1 simplifications + V2 candidates; forward-binding lessons for writing-plans; sub-bundle decomposition recommendation (P14.N6 slices); schema impact verdict (NO change, or v24); cumulative gotcha application summary; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness summary.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-4-review-journal-ux-brainstorming`. Dir `.worktrees/phase14-sub-bundle-4-review-journal-ux-brainstorming/`. Branch from main HEAD `604211e`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain at end (Sec 9.1 Q7), run via copowers' **WSL Codex CLI fallback** (v2.0.2 auto-routes on MCP failure; Codex reads the worktree from disk, findings -> `.copowers-findings.md`). The MCP tools are permanently dead in the VS Code extension -- do not attempt them (FB-N1).
- **Expected duration:** ~3-5 hours brainstorming + ~30-90 min Codex chain.

---

*End of brief. Phase 14 Sub-bundle 4 brainstorming dispatch -- produce a design spec for the review + journal UX (CR.1 exit-data + chart-snapshot enhancement + P14.N6 browse-the-database journal redesign + the in-scope BULZ row-expand wiring; ~600-1000 lines; single Codex chain). Read-mostly over already-shipped data; the CR.1 review form ALREADY EXISTS (enhancement, not greenfield); likely NO schema change (v24 only if a chart_renders surface enum is added). The rendered surface in a real browser is the BINDING operator-witnessed gate (matplotlib + HTMX). v22/v23 substrates are LOCKED. OUTPUT: a design spec the writing-plans phase can derive an implementation plan from.*
